---
title: 'TDX: Enable Dynamic PAMT'
date: 2025-06-09
last_reply: 2025-09-16
message_count: 97
participants: ['Kirill A. Shutemov', 'Chao Gao', 'Dave Hansen', 'Edgecombe, Rick P', 'Sean Christopherson', 'Huang, Kai', 'Adrian Hunter', 'kas@kernel.org', 'Vishal Annapurve', 'Sagi Shahar', 'Kiryl Shutsemau']
---

## [1] Kirill A. Shutemov — 2025-06-09

This patchset enables Dynamic PAMT in TDX. Please review.

Previously, we thought it can get upstreamed after huge page support, but
huge pages require support on guestmemfd side which might take time to hit
upstream. Dynamic PAMT doesn't have dependencies.

The patchset can be found here:

git://git.kernel.org/pub/scm/linux/kernel/git/kas/linux.git tdx/dpamt

==========================================================================

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

PAMT memory is dynamically allocated as pages gain TDX protections.
It is reclaimed when TDX protections have been removed from all
pages in a contiguous area.

Dynamic PAMT support in TDX module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Dynamic PAMT is a TDX feature that allows VMM to allocate PAMT_4K as
needed. PAMT_1G and PAMT_2M are still allocated statically at the time of
TDX module initialization. At init stage allocation of PAMT_4K is replaced
with PAMT_PAGE_BITMAP which currently requires one bit of memory per 4k.

VMM is responsible for allocating and freeing PAMT_4K. There's a couple of
new SEAMCALLs for this: TDH.PHYMEM.PAMT.ADD and TDH.PHYMEM.PAMT.REMOVE.
They add/remove PAMT memory in form of page pair. There's no requirement
for these pages to be contiguous.

Page pair supplied via TDH.PHYMEM.PAMT.ADD will cover specified 2M region.
It allows any 4K from the region to be usable by TDX module.

With Dynamic PAMT, a number of SEAMCALLs can now fail due to missing PAMT
memory (TDX_MISSING_PAMT_PAGE_PAIR):

 - TDH.MNG.CREATE
 - TDH.MNG.ADDCX
 - TDH.VP.ADDCX
 - TDH.VP.CREATE
 - TDH.MEM.PAGE.ADD
 - TDH.MEM.PAGE.AUG
 - TDH.MEM.PAGE.DEMOTE
 - TDH.MEM.PAGE.RELOCATE

Basically, if you supply memory to a TD, this memory has to backed by PAMT
memory.

Once no TD uses the 2M range, the PAMT page pair can be reclaimed with
TDH.PHYMEM.PAMT.REMOVE.

TDX module track PAMT memory usage and can give VMM a hint that PAMT
memory can be removed. Such hint is provided from all SEAMCALLs that
removes memory from TD:

 - TDH.MEM.SEPT.REMOVE
 - TDH.MEM.PAGE.REMOVE
 - TDH.MEM.PAGE.PROMOTE
 - TDH.MEM.PAGE.RELOCATE
 - TDH.PHYMEM.PAGE.RECLAIM

With Dynamic PAMT, TDH.MEM.PAGE.DEMOTE takes PAMT page pair as additional
input to populate PAMT_4K on split. TDH.MEM.PAGE.PROMOTE returns no longer
needed PAMT page pair.

PAMT memory is global resource and not tied to a specific TD. TDX modules
maintains PAMT memory in a radix tree addressed by physical address. Each
entry in the tree can be locked with shared or exclusive lock. Any
modification of the tree requires exclusive lock.

Any SEAMCALL that takes explicit HPA as an argument will walk the tree
taking shared lock on entries. It required to make sure that the page
pointed by HPA is of compatible type for the usage.

TDCALLs don't take PAMT locks as none of the take HPA as an argument.

Dynamic PAMT enabling in kernel
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Kernel maintains refcounts for every 2M regions with two helpers
tdx_pamt_get() and tdx_pamt_put().

The refcount represents number of users for the PAMT memory in the region.
Kernel calls TDH.PHYMEM.PAMT.ADD on 0->1 transition and
TDH.PHYMEM.PAMT.REMOVE on transition 1->0.

The function tdx_alloc_page() allocates a new page and ensures that it is
backed by PAMT memory. Pages allocated in this manner are ready to be used
for a TD. The function tdx_free_page() frees the page and releases the
PAMT memory for the 2M region if it is no longer needed.

PAMT memory gets allocated as part of TD init, VCPU init, on populating
SEPT tree and adding guest memory (both during TD build and via AUG on
accept). Splitting 2M page into 4K also requires PAMT memory.

PAMT memory removed on reclaim of control pages and guest memory.

Populating PAMT memory on fault and on split is tricky as kernel cannot
allocate memory from the context where it is needed. These code paths use
pre-allocated PAMT memory pools.

Previous attempt on Dynamic PAMT enabling
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The initial attempt at kernel enabling was quite different. It was built
around lazy PAMT allocation: only trying to add a PAMT page pair if a
SEAMCALL fails due to a missing PAMT and reclaiming it based on hints
provided by the TDX module.

The motivation was to avoid duplicating the PAMT memory refcounting that
the TDX module does on the kernel side.

This approach is inherently more racy as there is no serialization of
PAMT memory add/remove against SEAMCALLs that add/remove memory for a TD.
Such serialization would require global locking, which is not feasible.

This approach worked, but at some point it became clear that it could not
be robust as long as the kernel avoids TDX_OPERAND_BUSY loops.
TDX_OPERAND_BUSY will occur as a result of the races mentioned above.

This approach was abandoned in favor of explicit refcounting.

v2:
 - Drop phys_prepare/clenup. Use kvm_get_running_vcpu() to reach per-VCPU PAMT
   memory pool from TDX code instead.
 - Move code that allocates/frees PAMT out of KVM;
 - Allocate refcounts per-memblock, not per-TDMR;
 - Fix free_pamt_metadata() for machines without Dynamic PAMT;
 - Fix refcounting in tdx_pamt_put() error path;
 - Export functions where they are used;
 - Consolidate TDX error handling code;
 - Add documentation for Dynamic PAMT;
 - Mark /proc/meminfo patch [NOT-FOR-UPSTREAM];
Kirill A. Shutemov (12):
  x86/tdx: Consolidate TDX error handling
  x86/virt/tdx: Allocate page bitmap for Dynamic PAMT
  x86/virt/tdx: Allocate reference counters for PAMT memory
  x86/virt/tdx: Add tdx_alloc/free_page() helpers
  KVM: TDX: Allocate PAMT memory in __tdx_td_init()
  KVM: TDX: Allocate PAMT memory in tdx_td_vcpu_init()
  KVM: TDX: Preallocate PAMT pages to be used in page fault path
  KVM: TDX: Handle PAMT allocation in fault path
  KVM: TDX: Reclaim PAMT memory
  [NOT-FOR-UPSTREAM] x86/virt/tdx: Account PAMT memory and print it in
    /proc/meminfo
  x86/virt/tdx: Enable Dynamic PAMT
  Documentation/x86: Add documentation for TDX's Dynamic PAMT

 Documentation/arch/x86/tdx.rst              | 108 ++++++
 arch/x86/coco/tdx/tdx.c                     |   6 +-
 arch/x86/include/asm/kvm_host.h             |   2 +
 arch/x86/include/asm/set_memory.h           |   3 +
 arch/x86/include/asm/tdx.h                  |  40 ++-
 arch/x86/include/asm/tdx_errno.h            |  96 +++++
 arch/x86/include/asm/tdx_global_metadata.h  |   1 +
 arch/x86/kvm/mmu/mmu.c                      |   7 +
 arch/x86/kvm/vmx/tdx.c                      | 102 ++++--
 arch/x86/kvm/vmx/tdx.h                      |   1 -
 arch/x86/kvm/vmx/tdx_errno.h                |  40 ---
 arch/x86/mm/Makefile                        |   2 +
 arch/x86/mm/meminfo.c                       |  11 +
 arch/x86/mm/pat/set_memory.c                |   2 +-
 arch/x86/virt/vmx/tdx/tdx.c                 | 380 +++++++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx.h                 |   5 +-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |   3 +
 virt/kvm/kvm_main.c                         |   1 +
 18 files changed, 702 insertions(+), 108 deletions(-)
 create mode 100644 arch/x86/include/asm/tdx_errno.h
 delete mode 100644 arch/x86/kvm/vmx/tdx_errno.h
 create mode 100644 arch/x86/mm/meminfo.c

---

## [2] Kirill A. Shutemov — 2025-06-09
*Subject: [PATCHv2 01/12] x86/tdx: Consolidate TDX error handling*

Move all (host, kvm, guest) code related to TDX error handling into
<asm/tdx_errno.h>.

Add inline functions to check errors.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/coco/tdx/tdx.c                       |  6 +-
 arch/x86/include/asm/tdx.h                    | 21 +------
 arch/x86/{kvm/vmx => include/asm}/tdx_errno.h | 60 +++++++++++++++++--
 arch/x86/kvm/vmx/tdx.c                        | 18 ++----
 arch/x86/kvm/vmx/tdx.h                        |  1 -
 5 files changed, 63 insertions(+), 43 deletions(-)
 rename arch/x86/{kvm/vmx => include/asm}/tdx_errno.h (52%)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index edab6d6049be..6505bfcd2a0d 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -33,10 +33,6 @@
 #define VE_GET_PORT_NUM(e)	((e) >> 16)
 #define VE_IS_IO_STRING(e)	((e) & BIT(4))
 
-/* TDX Module call error codes */
-#define TDCALL_RETURN_CODE(a)	((a) >> 32)
-#define TDCALL_INVALID_OPERAND	0xc0000100
-
 #define TDREPORT_SUBTYPE_0	0
 
 static atomic_long_t nr_shared;
@@ -127,7 +123,7 @@ int tdx_mcall_get_report0(u8 *reportdata, u8 *tdreport)
 
 	ret = __tdcall(TDG_MR_REPORT, &args);
 	if (ret) {
-		if (TDCALL_RETURN_CODE(ret) == TDCALL_INVALID_OPERAND)
+		if (tdx_operand_invalid(ret))
 			return -EINVAL;
 		return -EIO;
 	}
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 26ffc792e673..9649308bd9c0 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -10,28 +10,9 @@
 #include <asm/errno.h>
 #include <asm/ptrace.h>
 #include <asm/trapnr.h>
+#include <asm/tdx_errno.h>
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
diff --git a/arch/x86/kvm/vmx/tdx_errno.h b/arch/x86/include/asm/tdx_errno.h
similarity index 52%
rename from arch/x86/kvm/vmx/tdx_errno.h
rename to arch/x86/include/asm/tdx_errno.h
index 6ff4672c4181..d418934176e2 100644
--- a/arch/x86/kvm/vmx/tdx_errno.h
+++ b/arch/x86/include/asm/tdx_errno.h
@@ -1,14 +1,13 @@
 /* SPDX-License-Identifier: GPL-2.0 */
 /* architectural status code for SEAMCALL */
 
-#ifndef __KVM_X86_TDX_ERRNO_H
-#define __KVM_X86_TDX_ERRNO_H
-
-#define TDX_SEAMCALL_STATUS_MASK		0xFFFFFFFF00000000ULL
+#ifndef _X86_TDX_ERRNO_H
+#define _X86_TDX_ERRNO_H
 
 /*
  * TDX SEAMCALL Status Codes (returned in RAX)
  */
+#define TDX_SUCCESS				0ULL
 #define TDX_NON_RECOVERABLE_VCPU		0x4000000100000000ULL
 #define TDX_NON_RECOVERABLE_TD			0x4000000200000000ULL
 #define TDX_NON_RECOVERABLE_TD_NON_ACCESSIBLE	0x6000000500000000ULL
@@ -17,6 +16,7 @@
 #define TDX_OPERAND_INVALID			0xC000010000000000ULL
 #define TDX_OPERAND_BUSY			0x8000020000000000ULL
 #define TDX_PREVIOUS_TLB_EPOCH_BUSY		0x8000020100000000ULL
+#define TDX_RND_NO_ENTROPY			0x8000020300000000ULL
 #define TDX_PAGE_METADATA_INCORRECT		0xC000030000000000ULL
 #define TDX_VCPU_NOT_ASSOCIATED			0x8000070200000000ULL
 #define TDX_KEY_GENERATION_FAILED		0x8000080000000000ULL
@@ -37,4 +37,54 @@
 #define TDX_OPERAND_ID_SEPT			0x92
 #define TDX_OPERAND_ID_TD_EPOCH			0xa9
 
-#endif /* __KVM_X86_TDX_ERRNO_H */
+#define TDX_STATUS_MASK				0xFFFFFFFF00000000ULL
+
+/*
+ * SW-defined error codes.
+ *
+ * Bits 47:40 == 0xFF indicate Reserved status code class that never used by
+ * TDX module.
+ */
+#define TDX_ERROR				_BITULL(63)
+#define TDX_NON_RECOVERABLE			_BITULL(62)
+#define TDX_SW_ERROR				(TDX_ERROR | GENMASK_ULL(47, 40))
+#define TDX_SEAMCALL_VMFAILINVALID		(TDX_SW_ERROR | _UL(0xFFFF0000))
+
+#define TDX_SEAMCALL_GP				(TDX_SW_ERROR | X86_TRAP_GP)
+#define TDX_SEAMCALL_UD				(TDX_SW_ERROR | X86_TRAP_UD)
+
+#ifndef __ASSEMBLER__
+#include <linux/bits.h>
+#include <linux/types.h>
+
+static inline u64 tdx_status(u64 err)
+{
+	return err & TDX_STATUS_MASK;
+}
+
+static inline bool tdx_sw_error(u64 err)
+{
+	return (err & TDX_SW_ERROR) == TDX_SW_ERROR;
+}
+
+static inline bool tdx_success(u64 err)
+{
+	return tdx_status(err) == TDX_SUCCESS;
+}
+
+static inline bool tdx_rnd_no_entropy(u64 err)
+{
+	return tdx_status(err) == TDX_RND_NO_ENTROPY;
+}
+
+static inline bool tdx_operand_invalid(u64 err)
+{
+	return tdx_status(err) == TDX_OPERAND_INVALID;
+}
+
+static inline bool tdx_operand_busy(u64 err)
+{
+	return tdx_status(err) == TDX_OPERAND_BUSY;
+}
+#endif /* __ASSEMBLER__ */
+#endif /* _X86_TDX_ERRNO_H */
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index b952bc673271..7a48bd901536 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -202,12 +202,6 @@ static DEFINE_MUTEX(tdx_lock);
 
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
@@ -895,7 +889,7 @@ static __always_inline u32 tdx_to_vmx_exit_reason(struct kvm_vcpu *vcpu)
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
 	u32 exit_reason;
 
-	switch (tdx->vp_enter_ret & TDX_SEAMCALL_STATUS_MASK) {
+	switch (tdx_status(tdx->vp_enter_ret)) {
 	case TDX_SUCCESS:
 	case TDX_NON_RECOVERABLE_VCPU:
 	case TDX_NON_RECOVERABLE_TD:
@@ -1957,7 +1951,7 @@ int tdx_handle_exit(struct kvm_vcpu *vcpu, fastpath_t fastpath)
 	 * Handle TDX SW errors, including TDX_SEAMCALL_UD, TDX_SEAMCALL_GP and
 	 * TDX_SEAMCALL_VMFAILINVALID.
 	 */
-	if (unlikely((vp_enter_ret & TDX_SW_ERROR) == TDX_SW_ERROR)) {
+	if (tdx_sw_error(vp_enter_ret)) {
 		KVM_BUG_ON(!kvm_rebooting, vcpu->kvm);
 		goto unhandled_exit;
 	}
@@ -1982,7 +1976,7 @@ int tdx_handle_exit(struct kvm_vcpu *vcpu, fastpath_t fastpath)
 	}
 
 	WARN_ON_ONCE(exit_reason.basic != EXIT_REASON_TRIPLE_FAULT &&
-		     (vp_enter_ret & TDX_SEAMCALL_STATUS_MASK) != TDX_SUCCESS);
+		     !tdx_success(vp_enter_ret));
 
 	switch (exit_reason.basic) {
 	case EXIT_REASON_TRIPLE_FAULT:
@@ -2428,7 +2422,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 	err = tdh_mng_create(&kvm_tdx->td, kvm_tdx->hkid);
 	mutex_unlock(&tdx_lock);
 
-	if (err == TDX_RND_NO_ENTROPY) {
+	if (tdx_rnd_no_entropy(err)) {
 		ret = -EAGAIN;
 		goto free_packages;
 	}
@@ -2470,7 +2464,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 	kvm_tdx->td.tdcs_pages = tdcs_pages;
 	for (i = 0; i < kvm_tdx->td.tdcs_nr_pages; i++) {
 		err = tdh_mng_addcx(&kvm_tdx->td, tdcs_pages[i]);
-		if (err == TDX_RND_NO_ENTROPY) {
+		if (tdx_rnd_no_entropy(err)) {
 			/* Here it's hard to allow userspace to retry. */
 			ret = -EAGAIN;
 			goto teardown;
@@ -2483,7 +2477,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 	}
 
 	err = tdh_mng_init(&kvm_tdx->td, __pa(td_params), &rcx);
-	if ((err & TDX_SEAMCALL_STATUS_MASK) == TDX_OPERAND_INVALID) {
+	if (tdx_operand_invalid(err)) {
 		/*
 		 * Because a user gives operands, don't warn.
 		 * Return a hint to the user because it's sometimes hard for the
diff --git a/arch/x86/kvm/vmx/tdx.h b/arch/x86/kvm/vmx/tdx.h
index 51f98443e8a2..dba23f1d21cb 100644
--- a/arch/x86/kvm/vmx/tdx.h
+++ b/arch/x86/kvm/vmx/tdx.h
@@ -3,7 +3,6 @@
 #define __KVM_X86_VMX_TDX_H
 
 #include "tdx_arch.h"
-#include "tdx_errno.h"
 
 #ifdef CONFIG_KVM_INTEL_TDX
 #include "common.h"

---

## [3] Kirill A. Shutemov — 2025-06-09
*Subject: [PATCHv2 02/12] x86/virt/tdx: Allocate page bitmap for Dynamic PAMT*

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

With Dynamic PAMT, the kernel no longer needs to allocate PAMT_4K on
boot, but instead must allocate a page bitmap. The TDX module determines
how many bits per page need to be allocated (currently it is 1).

Allocate the bitmap if the kernel boots on a machine with Dynamic PAMT.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/include/asm/tdx.h                  |  5 +++++
 arch/x86/include/asm/tdx_global_metadata.h  |  1 +
 arch/x86/virt/vmx/tdx/tdx.c                 | 23 ++++++++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |  3 +++
 4 files changed, 31 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 9649308bd9c0..583d6fe66821 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -106,6 +106,11 @@ int tdx_enable(void);
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
index 2457d13c3f9e..18179eb26eb9 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -470,6 +470,18 @@ static unsigned long tdmr_get_pamt_sz(struct tdmr_info *tdmr, int pgsz,
 	return pamt_sz;
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
  * Locate a NUMA node which should hold the allocation of the @tdmr
  * PAMT.  This node will have some memory covered by the TDMR.  The
@@ -522,7 +534,16 @@ static int tdmr_set_up_pamt(struct tdmr_info *tdmr,
 	 * and the total PAMT size.
 	 */
 	tdmr_pamt_size = 0;
-	for (pgsz = TDX_PS_4K; pgsz < TDX_PS_NR; pgsz++) {
+	pgsz = TDX_PS_4K;
+
+	/* With Dynamic PAMT, PAMT_4K is replaced with a bitmap */
+	if (tdx_supports_dynamic_pamt(&tdx_sysinfo)) {
+		pamt_size[pgsz] = tdmr_get_pamt_bitmap_sz(tdmr);
+		tdmr_pamt_size += pamt_size[pgsz];
+		pgsz++;
+	}
+
+	for (; pgsz < TDX_PS_NR; pgsz++) {
 		pamt_size[pgsz] = tdmr_get_pamt_sz(tdmr, pgsz,
 					pamt_entry_size[pgsz]);
 		tdmr_pamt_size += pamt_size[pgsz];
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

## [4] Kirill A. Shutemov — 2025-06-09
*Subject: [PATCHv2 03/12] x86/virt/tdx: Allocate reference counters for PAMT memory*

The PAMT memory holds metadata for TDX-protected memory. With Dynamic
PAMT, PAMT_4K is allocated on demand. The kernel supplies the TDX module
with a page pair that covers 2M of host physical memory.

The kernel must provide this page pair before using pages from the range
for TDX. If this is not done, any SEAMCALL that attempts to use the
memory will fail.

Allocate reference counters for every 2M range to track PAMT memory
usage. This is necessary to accurately determine when PAMT memory needs
to be allocated and when it can be freed.

This allocation will consume 2MiB for every 1TiB of physical memory.

Tracking PAMT memory usage on the kernel side duplicates what TDX module
does.  It is possible to avoid this by lazily allocating PAMT memory on
SEAMCALL failure and freeing it based on hints provided by the TDX
module when the last user of PAMT memory is no longer present.

However, this approach complicates serialization.

The TDX module takes locks when dealing with PAMT: a shared lock on any
SEAMCALL that uses explicit HPA and an exclusive lock on PAMT.ADD and
PAMT.REMOVE. Any SEAMCALL that uses explicit HPA as an operand may fail
if it races with PAMT.ADD/REMOVE.

Since PAMT is a global resource, to prevent failure the kernel would
need global locking (per-TD is not sufficient). Or, it has to retry on
TDX_OPERATOR_BUSY.

Both options are not ideal, and tracking PAMT usage on the kernel side
seems like a reasonable alternative.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 112 +++++++++++++++++++++++++++++++++++-
 1 file changed, 111 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 18179eb26eb9..ad9d7a30989d 100644
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
@@ -50,6 +51,8 @@ static DEFINE_PER_CPU(bool, tdx_lp_initialized);
 
 static struct tdmr_info_list tdx_tdmr_list;
 
+static atomic_t *pamt_refcounts;
+
 static enum tdx_module_status_t tdx_module_status;
 static DEFINE_MUTEX(tdx_module_lock);
 
@@ -182,6 +185,102 @@ int tdx_cpu_enable(void)
 }
 EXPORT_SYMBOL_GPL(tdx_cpu_enable);
 
+static atomic_t *tdx_get_pamt_refcount(unsigned long hpa)
+{
+	return &pamt_refcounts[hpa / PMD_SIZE];
+}
+
+static int pamt_refcount_populate(pte_t *pte, unsigned long addr, void *data)
+{
+	unsigned long vaddr;
+	pte_t entry;
+
+	if (!pte_none(ptep_get(pte)))
+		return 0;
+
+	vaddr = __get_free_page(GFP_KERNEL | __GFP_ZERO);
+	if (!vaddr)
+		return -ENOMEM;
+
+	entry = pfn_pte(PFN_DOWN(__pa(vaddr)), PAGE_KERNEL);
+
+	spin_lock(&init_mm.page_table_lock);
+	if (pte_none(ptep_get(pte)))
+		set_pte_at(&init_mm, addr, pte, entry);
+	else
+		free_page(vaddr);
+	spin_unlock(&init_mm.page_table_lock);
+
+	return 0;
+}
+
+static int pamt_refcount_depopulate(pte_t *pte, unsigned long addr,
+				    void *data)
+{
+	unsigned long vaddr;
+
+	vaddr = (unsigned long)__va(PFN_PHYS(pte_pfn(ptep_get(pte))));
+
+	spin_lock(&init_mm.page_table_lock);
+	if (!pte_none(ptep_get(pte))) {
+		pte_clear(&init_mm, addr, pte);
+		free_page(vaddr);
+	}
+	spin_unlock(&init_mm.page_table_lock);
+
+	return 0;
+}
+
+static int alloc_pamt_refcount(unsigned long start_pfn, unsigned long end_pfn)
+{
+	unsigned long start, end;
+
+	start = (unsigned long)tdx_get_pamt_refcount(PFN_PHYS(start_pfn));
+	end = (unsigned long)tdx_get_pamt_refcount(PFN_PHYS(end_pfn + 1));
+	start = round_down(start, PAGE_SIZE);
+	end = round_up(end, PAGE_SIZE);
+
+	return apply_to_page_range(&init_mm, start, end - start,
+				   pamt_refcount_populate, NULL);
+}
+
+static int init_pamt_metadata(void)
+{
+	size_t size = max_pfn / PTRS_PER_PTE * sizeof(*pamt_refcounts);
+	struct vm_struct *area;
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return 0;
+
+	/*
+	 * Reserve vmalloc range for PAMT reference counters. It covers all
+	 * physical address space up to max_pfn. It is going to be populated
+	 * from init_tdmr() only for present memory that available for TDX use.
+	 */
+	area = get_vm_area(size, VM_IOREMAP);
+	if (!area)
+		return -ENOMEM;
+
+	pamt_refcounts = area->addr;
+	return 0;
+}
+
+static void free_pamt_metadata(void)
+{
+	size_t size = max_pfn / PTRS_PER_PTE * sizeof(*pamt_refcounts);
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return;
+
+	size = round_up(size, PAGE_SIZE);
+	apply_to_existing_page_range(&init_mm,
+				     (unsigned long)pamt_refcounts,
+				     size, pamt_refcount_depopulate,
+				     NULL);
+	vfree(pamt_refcounts);
+	pamt_refcounts = NULL;
+}
+
 /*
  * Add a memory region as a TDX memory block.  The caller must make sure
  * all memory regions are added in address ascending order and don't
@@ -248,6 +347,10 @@ static int build_tdx_memlist(struct list_head *tmb_list)
 		ret = add_tdx_memblock(tmb_list, start_pfn, end_pfn, nid);
 		if (ret)
 			goto err;
+
+		ret = alloc_pamt_refcount(start_pfn, end_pfn);
+		if (ret)
+			goto err;
 	}
 
 	return 0;
@@ -1110,10 +1213,15 @@ static int init_tdx_module(void)
 	 */
 	get_online_mems();
 
-	ret = build_tdx_memlist(&tdx_memlist);
+	/* Reserve vmalloc range for PAMT reference counters */
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
@@ -1171,6 +1279,8 @@ static int init_tdx_module(void)
 	free_tdmr_list(&tdx_tdmr_list);
 err_free_tdxmem:
 	free_tdx_memlist(&tdx_memlist);
+err_free_pamt_metadata:
+	free_pamt_metadata();
 	goto out_put_tdxmem;
 }

---

## [5] Kirill A. Shutemov — 2025-06-09
*Subject: [PATCHv2 04/12] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

The new helpers allocate and free pages that can be used for a TDs.

Besides page allocation and freeing, these helpers also take care about
managing PAMT memory, if kernel runs on a platform with Dynamic PAMT
supported.

tdx_pamt_get()/put() helpers take care of PAMT allocation/freeing and
its refcounting.

PAMT memory is allocated when refcount for the 2M range crosses from 0
to 1 and gets freed back on when it is dropped to zero. These
transitions can happen concurrently and pamt_lock spinlock serializes
them.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/include/asm/tdx.h       |   3 +
 arch/x86/include/asm/tdx_errno.h |   6 +
 arch/x86/virt/vmx/tdx/tdx.c      | 205 +++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h      |   2 +
 4 files changed, 216 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 583d6fe66821..d9a77147412f 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -115,6 +115,9 @@ int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
 
+struct page *tdx_alloc_page(void);
+void tdx_free_page(struct page *page);
+
 struct tdx_td {
 	/* TD root structure: */
 	struct page *tdr_page;
diff --git a/arch/x86/include/asm/tdx_errno.h b/arch/x86/include/asm/tdx_errno.h
index d418934176e2..0b3332c2d6b2 100644
--- a/arch/x86/include/asm/tdx_errno.h
+++ b/arch/x86/include/asm/tdx_errno.h
@@ -18,6 +18,7 @@
 #define TDX_PREVIOUS_TLB_EPOCH_BUSY		0x8000020100000000ULL
 #define TDX_RND_NO_ENTROPY			0x8000020300000000ULL
 #define TDX_PAGE_METADATA_INCORRECT		0xC000030000000000ULL
+#define TDX_HPA_RANGE_NOT_FREE			0xC000030400000000ULL
 #define TDX_VCPU_NOT_ASSOCIATED			0x8000070200000000ULL
 #define TDX_KEY_GENERATION_FAILED		0x8000080000000000ULL
 #define TDX_KEY_STATE_INCORRECT			0xC000081100000000ULL
@@ -86,5 +87,10 @@ static inline bool tdx_operand_busy(u64 err)
 {
 	return tdx_status(err) == TDX_OPERAND_BUSY;
 }
+
+static inline bool tdx_hpa_range_not_free(u64 err)
+{
+	return tdx_status(err) == TDX_HPA_RANGE_NOT_FREE;
+}
 #endif /* __ASSEMBLER__ */
 #endif /* _X86_TDX_ERRNO_H */
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index ad9d7a30989d..c514c60e8c8d 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2000,3 +2000,208 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
 	return seamcall(TDH_PHYMEM_PAGE_WBINVD, &args);
 }
 EXPORT_SYMBOL_GPL(tdh_phymem_page_wbinvd_hkid);
+
+static int tdx_nr_pamt_pages(void)
+{
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return 0;
+
+	return tdx_sysinfo.tdmr.pamt_4k_entry_size * PTRS_PER_PTE / PAGE_SIZE;
+}
+
+static u64 tdh_phymem_pamt_add(unsigned long hpa,
+			       struct list_head *pamt_pages)
+{
+	struct tdx_module_args args = {
+		.rcx = hpa,
+	};
+	struct page *page;
+	u64 *p;
+
+	WARN_ON_ONCE(!IS_ALIGNED(hpa & PAGE_MASK, PMD_SIZE));
+
+	p = &args.rdx;
+	list_for_each_entry(page, pamt_pages, lru) {
+		*p = page_to_phys(page);
+		p++;
+	}
+
+	return seamcall(TDH_PHYMEM_PAMT_ADD, &args);
+}
+
+static u64 tdh_phymem_pamt_remove(unsigned long hpa,
+				  struct list_head *pamt_pages)
+{
+	struct tdx_module_args args = {
+		.rcx = hpa,
+	};
+	struct page *page;
+	u64 *p, ret;
+
+	WARN_ON_ONCE(!IS_ALIGNED(hpa & PAGE_MASK, PMD_SIZE));
+
+	ret = seamcall_ret(TDH_PHYMEM_PAMT_REMOVE, &args);
+	if (ret)
+		return ret;
+
+	p = &args.rdx;
+	for (int i = 0; i < tdx_nr_pamt_pages(); i++) {
+		page = phys_to_page(*p);
+		list_add(&page->lru, pamt_pages);
+		p++;
+	}
+
+	return ret;
+}
+
+static DEFINE_SPINLOCK(pamt_lock);
+
+static void tdx_free_pamt_pages(struct list_head *pamt_pages)
+{
+	struct page *page;
+
+	while ((page = list_first_entry_or_null(pamt_pages, struct page, lru))) {
+		list_del(&page->lru);
+		__free_page(page);
+	}
+}
+
+static int tdx_alloc_pamt_pages(struct list_head *pamt_pages)
+{
+	for (int i = 0; i < tdx_nr_pamt_pages(); i++) {
+		struct page *page = alloc_page(GFP_KERNEL);
+		if (!page)
+			goto fail;
+		list_add(&page->lru, pamt_pages);
+	}
+	return 0;
+fail:
+	tdx_free_pamt_pages(pamt_pages);
+	return -ENOMEM;
+}
+
+static int tdx_pamt_add(atomic_t *pamt_refcount, unsigned long hpa,
+			struct list_head *pamt_pages)
+{
+	u64 err;
+
+	guard(spinlock)(&pamt_lock);
+
+	hpa = ALIGN_DOWN(hpa, PMD_SIZE);
+
+	/* Lost race to other tdx_pamt_add() */
+	if (atomic_read(pamt_refcount) != 0) {
+		atomic_inc(pamt_refcount);
+		return 1;
+	}
+
+	err = tdh_phymem_pamt_add(hpa | TDX_PS_2M, pamt_pages);
+
+	/*
+	 * tdx_hpa_range_not_free() is true if current task won race
+	 * against tdx_pamt_put().
+	 */
+	if (err && !tdx_hpa_range_not_free(err)) {
+		pr_err("TDH_PHYMEM_PAMT_ADD failed: %#llx\n", err);
+		return -EIO;
+	}
+
+	atomic_set(pamt_refcount, 1);
+
+	if (tdx_hpa_range_not_free(err))
+		return 1;
+
+	return 0;
+}
+
+static int tdx_pamt_get(struct page *page, enum pg_level level)
+{
+	unsigned long hpa = page_to_phys(page);
+	atomic_t *pamt_refcount;
+	LIST_HEAD(pamt_pages);
+	int ret;
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return 0;
+
+	if (level != PG_LEVEL_4K)
+		return 0;
+
+	pamt_refcount = tdx_get_pamt_refcount(hpa);
+	WARN_ON_ONCE(atomic_read(pamt_refcount) < 0);
+
+	if (atomic_inc_not_zero(pamt_refcount))
+		return 0;
+
+	if (tdx_alloc_pamt_pages(&pamt_pages))
+		return -ENOMEM;
+
+	ret = tdx_pamt_add(pamt_refcount, hpa, &pamt_pages);
+	if (ret)
+		tdx_free_pamt_pages(&pamt_pages);
+
+	return ret >= 0 ? 0 : ret;
+}
+
+static void tdx_pamt_put(struct page *page, enum pg_level level)
+{
+	unsigned long hpa = page_to_phys(page);
+	atomic_t *pamt_refcount;
+	LIST_HEAD(pamt_pages);
+	u64 err;
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return;
+
+	if (level != PG_LEVEL_4K)
+		return;
+
+	hpa = ALIGN_DOWN(hpa, PMD_SIZE);
+
+	pamt_refcount = tdx_get_pamt_refcount(hpa);
+	if (!atomic_dec_and_test(pamt_refcount))
+		return;
+
+	scoped_guard(spinlock, &pamt_lock) {
+		/* Lost race against tdx_pamt_add()? */
+		if (atomic_read(pamt_refcount) != 0)
+			return;
+
+		err = tdh_phymem_pamt_remove(hpa | TDX_PS_2M, &pamt_pages);
+
+		if (err) {
+			atomic_inc(pamt_refcount);
+			pr_err("TDH_PHYMEM_PAMT_REMOVE failed: %#llx\n", err);
+			return;
+		}
+	}
+
+	tdx_free_pamt_pages(&pamt_pages);
+}
+
+struct page *tdx_alloc_page(void)
+{
+	struct page *page;
+
+	page = alloc_page(GFP_KERNEL);
+	if (!page)
+		return NULL;
+
+	if (tdx_pamt_get(page, PG_LEVEL_4K)) {
+		__free_page(page);
+		return NULL;
+	}
+
+	return page;
+}
+EXPORT_SYMBOL_GPL(tdx_alloc_page);
+
+void tdx_free_page(struct page *page)
+{
+	if (!page)
+		return;
+
+	tdx_pamt_put(page, PG_LEVEL_4K);
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

## [6] Kirill A. Shutemov — 2025-06-09
*Subject: [PATCHv2 05/12] KVM: TDX: Allocate PAMT memory in __tdx_td_init()*

Allocate PAMT memory for TDH.MNG.CREATE and TDH.MNG.ADDCX.

PAMT memory that is associated with pages successfully added to the TD
with TDH.MNG.ADDCX will be removed in tdx_reclaim_page() on
tdx_reclaim_control_page().

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/kvm/vmx/tdx.c | 16 ++++++----------
 1 file changed, 6 insertions(+), 10 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 7a48bd901536..13796b9a4bc5 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2370,7 +2370,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 
 	atomic_inc(&nr_configured_hkid);
 
-	tdr_page = alloc_page(GFP_KERNEL);
+	tdr_page = tdx_alloc_page();
 	if (!tdr_page)
 		goto free_hkid;
 
@@ -2383,7 +2383,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 		goto free_tdr;
 
 	for (i = 0; i < kvm_tdx->td.tdcs_nr_pages; i++) {
-		tdcs_pages[i] = alloc_page(GFP_KERNEL);
+		tdcs_pages[i] = tdx_alloc_page();
 		if (!tdcs_pages[i])
 			goto free_tdcs;
 	}
@@ -2504,10 +2504,8 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
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
@@ -2523,15 +2521,13 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 
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

## [7] Kirill A. Shutemov — 2025-06-09
*Subject: [PATCHv2 06/12] KVM: TDX: Allocate PAMT memory in tdx_td_vcpu_init()*

Allocate PAMT memory for TDH.VP.CREATE and TDH.VP.ADDCX.

PAMT memory that is associated with pages successfully added to the TD
with TDH.VP.ADDCX will be removed in tdx_reclaim_page() on
tdx_reclaim_control_page().

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/kvm/vmx/tdx.c | 13 ++++++-------
 1 file changed, 6 insertions(+), 7 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 13796b9a4bc5..36c3c9f8a62c 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2829,7 +2829,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 	int ret, i;
 	u64 err;
 
-	page = alloc_page(GFP_KERNEL);
+	page = tdx_alloc_page();
 	if (!page)
 		return -ENOMEM;
 	tdx->vp.tdvpr_page = page;
@@ -2842,7 +2842,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 	}
 
 	for (i = 0; i < kvm_tdx->td.tdcx_nr_pages; i++) {
-		page = alloc_page(GFP_KERNEL);
+		page = tdx_alloc_page();
 		if (!page) {
 			ret = -ENOMEM;
 			goto free_tdcx;
@@ -2866,7 +2866,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 			 * method, but the rest are freed here.
 			 */
 			for (; i < kvm_tdx->td.tdcx_nr_pages; i++) {
-				__free_page(tdx->vp.tdcx_pages[i]);
+				tdx_free_page(tdx->vp.tdcx_pages[i]);
 				tdx->vp.tdcx_pages[i] = NULL;
 			}
 			return -EIO;
@@ -2885,16 +2885,15 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 
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
+
 	tdx->vp.tdvpr_page = 0;
 
 	return ret;

---

## [8] Kirill A. Shutemov — 2025-06-09
*Subject: [PATCHv2 07/12] KVM: TDX: Preallocate PAMT pages to be used in page fault path*

Preallocate a page to be used in the link_external_spt() and
set_external_spte() paths.

In the worst-case scenario, handling a page fault might require a
tdx_nr_pamt_pages() pages for each page table level.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/include/asm/kvm_host.h | 2 ++
 arch/x86/include/asm/tdx.h      | 2 ++
 arch/x86/kvm/mmu/mmu.c          | 7 +++++++
 arch/x86/virt/vmx/tdx/tdx.c     | 3 ++-
 4 files changed, 13 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 330cdcbed1a6..02dbbf848182 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -849,6 +849,8 @@ struct kvm_vcpu_arch {
 	 */
 	struct kvm_mmu_memory_cache mmu_external_spt_cache;
 
+	struct kvm_mmu_memory_cache pamt_page_cache;
+
 	/*
 	 * QEMU userspace and the guest each have their own FPU state.
 	 * In vcpu_run, we switch between the user and guest FPU contexts.
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index d9a77147412f..47092eb13eb3 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -115,6 +115,7 @@ int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
 
+int tdx_nr_pamt_pages(void);
 struct page *tdx_alloc_page(void);
 void tdx_free_page(struct page *page);
 
@@ -188,6 +189,7 @@ static inline int tdx_enable(void)  { return -ENODEV; }
 static inline u32 tdx_get_nr_guest_keyids(void) { return 0; }
 static inline const char *tdx_dump_mce_info(struct mce *m) { return NULL; }
 static inline const struct tdx_sys_info *tdx_get_sysinfo(void) { return NULL; }
+static inline int tdx_nr_pamt_pages(void) { return 0; }
 #endif	/* CONFIG_INTEL_TDX_HOST */
 
 #endif /* !__ASSEMBLER__ */
diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index cbc84c6abc2e..d99bb27b5b01 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -616,6 +616,12 @@ static int mmu_topup_memory_caches(struct kvm_vcpu *vcpu, bool maybe_indirect)
 		if (r)
 			return r;
 	}
+
+	r = kvm_mmu_topup_memory_cache(&vcpu->arch.pamt_page_cache,
+				       tdx_nr_pamt_pages() * PT64_ROOT_MAX_LEVEL);
+	if (r)
+		return r;
+
 	return kvm_mmu_topup_memory_cache(&vcpu->arch.mmu_page_header_cache,
 					  PT64_ROOT_MAX_LEVEL);
 }
@@ -626,6 +632,7 @@ static void mmu_free_memory_caches(struct kvm_vcpu *vcpu)
 	kvm_mmu_free_memory_cache(&vcpu->arch.mmu_shadow_page_cache);
 	kvm_mmu_free_memory_cache(&vcpu->arch.mmu_shadowed_info_cache);
 	kvm_mmu_free_memory_cache(&vcpu->arch.mmu_external_spt_cache);
+	kvm_mmu_free_memory_cache(&vcpu->arch.pamt_page_cache);
 	kvm_mmu_free_memory_cache(&vcpu->arch.mmu_page_header_cache);
 }
 
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index c514c60e8c8d..4f9eaba4af4a 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2001,13 +2001,14 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
 }
 EXPORT_SYMBOL_GPL(tdh_phymem_page_wbinvd_hkid);
 
-static int tdx_nr_pamt_pages(void)
+int tdx_nr_pamt_pages(void)
 {
 	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
 		return 0;
 
 	return tdx_sysinfo.tdmr.pamt_4k_entry_size * PTRS_PER_PTE / PAGE_SIZE;
 }
+EXPORT_SYMBOL_GPL(tdx_nr_pamt_pages);
 
 static u64 tdh_phymem_pamt_add(unsigned long hpa,
 			       struct list_head *pamt_pages)

---

## [9] Kirill A. Shutemov — 2025-06-09
*Subject: [PATCHv2 08/12] KVM: TDX: Handle PAMT allocation in fault path*

There are two distinct cases when the kernel needs to allocate PAMT
memory in the fault path: for SEPT page tables in tdx_sept_link_private_spt()
and for leaf pages in tdx_sept_set_private_spte().

These code paths run in atomic context. Use a pre-allocated per-VCPU
pool for memory allocations.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/include/asm/tdx.h  |  4 ++++
 arch/x86/kvm/vmx/tdx.c      | 40 ++++++++++++++++++++++++++++++++-----
 arch/x86/virt/vmx/tdx/tdx.c | 21 +++++++++++++------
 virt/kvm/kvm_main.c         |  1 +
 4 files changed, 55 insertions(+), 11 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 47092eb13eb3..39f8dd7e0f06 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -116,6 +116,10 @@ u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
 
 int tdx_nr_pamt_pages(void);
+int tdx_pamt_get(struct page *page, enum pg_level level,
+		 struct page *(alloc)(void *data), void *data);
+void tdx_pamt_put(struct page *page, enum pg_level level);
+
 struct page *tdx_alloc_page(void);
 void tdx_free_page(struct page *page);
 
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 36c3c9f8a62c..bc9bc393f866 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1537,11 +1537,26 @@ static int tdx_mem_page_record_premap_cnt(struct kvm *kvm, gfn_t gfn,
 	return 0;
 }
 
+static struct page *tdx_alloc_pamt_page_atomic(void *data)
+{
+	struct kvm_vcpu *vcpu = data;
+	void *p;
+
+	p = kvm_mmu_memory_cache_alloc(&vcpu->arch.pamt_page_cache);
+	return virt_to_page(p);
+}
+
 int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 			      enum pg_level level, kvm_pfn_t pfn)
 {
+	struct kvm_vcpu *vcpu = kvm_get_running_vcpu();
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 	struct page *page = pfn_to_page(pfn);
+	int ret;
+
+	ret = tdx_pamt_get(page, level, tdx_alloc_pamt_page_atomic, vcpu);
+	if (ret)
+		return ret;
 
 	/* TODO: handle large pages. */
 	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
@@ -1562,10 +1577,16 @@ int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
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
+		tdx_pamt_put(page, level);
+
+	return ret;
 }
 
 static int tdx_sept_drop_private_spte(struct kvm *kvm, gfn_t gfn,
@@ -1622,17 +1643,26 @@ int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
 			      enum pg_level level, void *private_spt)
 {
 	int tdx_level = pg_level_to_tdx_sept_level(level);
-	gpa_t gpa = gfn_to_gpa(gfn);
+	struct kvm_vcpu *vcpu = kvm_get_running_vcpu();
 	struct page *page = virt_to_page(private_spt);
+	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 err, entry, level_state;
+	int ret;
+
+	ret = tdx_pamt_get(page, PG_LEVEL_4K, tdx_alloc_pamt_page_atomic, vcpu);
+	if (ret)
+		return ret;
 
 	err = tdh_mem_sept_add(&to_kvm_tdx(kvm)->td, gpa, tdx_level, page, &entry,
 			       &level_state);
-	if (unlikely(tdx_operand_busy(err)))
+	if (unlikely(tdx_operand_busy(err))) {
+		tdx_pamt_put(page, PG_LEVEL_4K);
 		return -EBUSY;
+	}
 
 	if (KVM_BUG_ON(err, kvm)) {
 		pr_tdx_error_2(TDH_MEM_SEPT_ADD, err, entry, level_state);
+		tdx_pamt_put(page, PG_LEVEL_4K);
 		return -EIO;
 	}
 
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 4f9eaba4af4a..d4b50b6428fa 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2067,10 +2067,16 @@ static void tdx_free_pamt_pages(struct list_head *pamt_pages)
 	}
 }
 
-static int tdx_alloc_pamt_pages(struct list_head *pamt_pages)
+static int tdx_alloc_pamt_pages(struct list_head *pamt_pages,
+				 struct page *(alloc)(void *data), void *data)
 {
 	for (int i = 0; i < tdx_nr_pamt_pages(); i++) {
-		struct page *page = alloc_page(GFP_KERNEL);
+		struct page *page;
+
+		if (alloc)
+			page = alloc(data);
+		else
+			page = alloc_page(GFP_KERNEL);
 		if (!page)
 			goto fail;
 		list_add(&page->lru, pamt_pages);
@@ -2115,7 +2121,8 @@ static int tdx_pamt_add(atomic_t *pamt_refcount, unsigned long hpa,
 	return 0;
 }
 
-static int tdx_pamt_get(struct page *page, enum pg_level level)
+int tdx_pamt_get(struct page *page, enum pg_level level,
+		 struct page *(alloc)(void *data), void *data)
 {
 	unsigned long hpa = page_to_phys(page);
 	atomic_t *pamt_refcount;
@@ -2134,7 +2141,7 @@ static int tdx_pamt_get(struct page *page, enum pg_level level)
 	if (atomic_inc_not_zero(pamt_refcount))
 		return 0;
 
-	if (tdx_alloc_pamt_pages(&pamt_pages))
+	if (tdx_alloc_pamt_pages(&pamt_pages, alloc, data))
 		return -ENOMEM;
 
 	ret = tdx_pamt_add(pamt_refcount, hpa, &pamt_pages);
@@ -2143,8 +2150,9 @@ static int tdx_pamt_get(struct page *page, enum pg_level level)
 
 	return ret >= 0 ? 0 : ret;
 }
+EXPORT_SYMBOL_GPL(tdx_pamt_get);
 
-static void tdx_pamt_put(struct page *page, enum pg_level level)
+void tdx_pamt_put(struct page *page, enum pg_level level)
 {
 	unsigned long hpa = page_to_phys(page);
 	atomic_t *pamt_refcount;
@@ -2179,6 +2187,7 @@ static void tdx_pamt_put(struct page *page, enum pg_level level)
 
 	tdx_free_pamt_pages(&pamt_pages);
 }
+EXPORT_SYMBOL_GPL(tdx_pamt_put);
 
 struct page *tdx_alloc_page(void)
 {
@@ -2188,7 +2197,7 @@ struct page *tdx_alloc_page(void)
 	if (!page)
 		return NULL;
 
-	if (tdx_pamt_get(page, PG_LEVEL_4K)) {
+	if (tdx_pamt_get(page, PG_LEVEL_4K, NULL, NULL)) {
 		__free_page(page);
 		return NULL;
 	}
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index eec82775c5bf..6add012532a0 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -436,6 +436,7 @@ void *kvm_mmu_memory_cache_alloc(struct kvm_mmu_memory_cache *mc)
 	BUG_ON(!p);
 	return p;
 }
+EXPORT_SYMBOL_GPL(kvm_mmu_memory_cache_alloc);
 #endif
 
 static void kvm_vcpu_init(struct kvm_vcpu *vcpu, struct kvm *kvm, unsigned id)

---

## [10] Kirill A. Shutemov — 2025-06-09
*Subject: [PATCHv2 09/12] KVM: TDX: Reclaim PAMT memory*

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
---
 arch/x86/kvm/vmx/tdx.c | 15 ++++++++++++---
 1 file changed, 12 insertions(+), 3 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index bc9bc393f866..0aed7e73cd6b 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -353,7 +353,7 @@ static void tdx_reclaim_control_page(struct page *ctrl_page)
 	if (tdx_reclaim_page(ctrl_page))
 		return;
 
-	__free_page(ctrl_page);
+	tdx_free_page(ctrl_page);
 }
 
 struct tdx_flush_vp_arg {
@@ -584,7 +584,7 @@ static void tdx_reclaim_td_control_pages(struct kvm *kvm)
 	}
 	tdx_clear_page(kvm_tdx->td.tdr_page);
 
-	__free_page(kvm_tdx->td.tdr_page);
+	tdx_free_page(kvm_tdx->td.tdr_page);
 	kvm_tdx->td.tdr_page = NULL;
 }
 
@@ -1635,6 +1635,7 @@ static int tdx_sept_drop_private_spte(struct kvm *kvm, gfn_t gfn,
 		return -EIO;
 	}
 	tdx_clear_page(page);
+	tdx_pamt_put(page, level);
 	tdx_unpin(kvm, page);
 	return 0;
 }
@@ -1724,6 +1725,7 @@ static int tdx_sept_zap_private_spte(struct kvm *kvm, gfn_t gfn,
 	if (tdx_is_sept_zap_err_due_to_premap(kvm_tdx, err, entry, level) &&
 	    !KVM_BUG_ON(!atomic64_read(&kvm_tdx->nr_premapped), kvm)) {
 		atomic64_dec(&kvm_tdx->nr_premapped);
+		tdx_pamt_put(page, level);
 		tdx_unpin(kvm, page);
 		return 0;
 	}
@@ -1788,6 +1790,8 @@ int tdx_sept_free_private_spt(struct kvm *kvm, gfn_t gfn,
 			      enum pg_level level, void *private_spt)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
+	struct page *page = virt_to_page(private_spt);
+	int ret;
 
 	/*
 	 * free_external_spt() is only called after hkid is freed when TD is
@@ -1804,7 +1808,12 @@ int tdx_sept_free_private_spt(struct kvm *kvm, gfn_t gfn,
 	 * The HKID assigned to this TD was already freed and cache was
 	 * already flushed. We don't have to flush again.
 	 */
-	return tdx_reclaim_page(virt_to_page(private_spt));
+	ret = tdx_reclaim_page(virt_to_page(private_spt));
+	if (ret)
+		return ret;
+
+	tdx_pamt_put(page, PG_LEVEL_4K);
+	return 0;
 }
 
 int tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,

---

## [11] Kirill A. Shutemov — 2025-06-09
*Subject: [PATCHv2 10/12] [NOT-FOR-UPSTREAM] x86/virt/tdx: Account PAMT memory and print it in /proc/meminfo*

PAMT memory can add up to substantial portion of system memory.

Account these pages and print them into /proc/meminfo as TDX.

When no TD running PAMT memory consumption suppose to be zero.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

---

The patch proved to be extremely useful to catch PAMT memory leaks,
but putting this counter in /proc/meminfo is probably overkill.

Any suggestion for better way to expose this counter is welcome.
---
 arch/x86/include/asm/set_memory.h |  3 +++
 arch/x86/include/asm/tdx.h        |  3 +++
 arch/x86/mm/Makefile              |  2 ++
 arch/x86/mm/meminfo.c             | 11 +++++++++++
 arch/x86/mm/pat/set_memory.c      |  2 +-
 arch/x86/virt/vmx/tdx/tdx.c       | 26 ++++++++++++++++++++++++--
 6 files changed, 44 insertions(+), 3 deletions(-)
 create mode 100644 arch/x86/mm/meminfo.c

diff --git a/arch/x86/include/asm/set_memory.h b/arch/x86/include/asm/set_memory.h
index 8d9f1c9aaa4c..66b37bff61e5 100644
--- a/arch/x86/include/asm/set_memory.h
+++ b/arch/x86/include/asm/set_memory.h
@@ -90,6 +90,9 @@ int set_direct_map_default_noflush(struct page *page);
 int set_direct_map_valid_noflush(struct page *page, unsigned nr, bool valid);
 bool kernel_page_present(struct page *page);
 
+struct seq_file;
+void direct_pages_meminfo(struct seq_file *m);
+
 extern int kernel_set_to_readonly;
 
 #endif /* _ASM_X86_SET_MEMORY_H */
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 39f8dd7e0f06..853471e1eda1 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -186,6 +186,8 @@ u64 tdh_mem_page_remove(struct tdx_td *td, u64 gpa, u64 level, u64 *ext_err1, u6
 u64 tdh_phymem_cache_wb(bool resume);
 u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td);
 u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page);
+
+void tdx_meminfo(struct seq_file *m);
 #else
 static inline void tdx_init(void) { }
 static inline int tdx_cpu_enable(void) { return -ENODEV; }
@@ -194,6 +196,7 @@ static inline u32 tdx_get_nr_guest_keyids(void) { return 0; }
 static inline const char *tdx_dump_mce_info(struct mce *m) { return NULL; }
 static inline const struct tdx_sys_info *tdx_get_sysinfo(void) { return NULL; }
 static inline int tdx_nr_pamt_pages(void) { return 0; }
+static inline void tdx_meminfo(struct seq_file *m) {}
 #endif	/* CONFIG_INTEL_TDX_HOST */
 
 #endif /* !__ASSEMBLER__ */
diff --git a/arch/x86/mm/Makefile b/arch/x86/mm/Makefile
index 32035d5be5a0..311d60801871 100644
--- a/arch/x86/mm/Makefile
+++ b/arch/x86/mm/Makefile
@@ -38,6 +38,8 @@ CFLAGS_fault.o := -I $(src)/../include/asm/trace
 
 obj-$(CONFIG_X86_32)		+= pgtable_32.o iomap_32.o
 
+obj-$(CONFIG_PROC_FS)		+= meminfo.o
+
 obj-$(CONFIG_HUGETLB_PAGE)	+= hugetlbpage.o
 obj-$(CONFIG_PTDUMP)		+= dump_pagetables.o
 obj-$(CONFIG_PTDUMP_DEBUGFS)	+= debug_pagetables.o
diff --git a/arch/x86/mm/meminfo.c b/arch/x86/mm/meminfo.c
new file mode 100644
index 000000000000..7bdb5df014de
--- /dev/null
+++ b/arch/x86/mm/meminfo.c
@@ -0,0 +1,11 @@
+#include <linux/proc_fs.h>
+#include <linux/seq_file.h>
+
+#include <asm/set_memory.h>
+#include <asm/tdx.h>
+
+void arch_report_meminfo(struct seq_file *m)
+{
+	direct_pages_meminfo(m);
+	tdx_meminfo(m);
+}
diff --git a/arch/x86/mm/pat/set_memory.c b/arch/x86/mm/pat/set_memory.c
index def3d9284254..59432b92e80e 100644
--- a/arch/x86/mm/pat/set_memory.c
+++ b/arch/x86/mm/pat/set_memory.c
@@ -118,7 +118,7 @@ static void collapse_page_count(int level)
 	direct_pages_count[level - 1] -= PTRS_PER_PTE;
 }
 
-void arch_report_meminfo(struct seq_file *m)
+void direct_pages_meminfo(struct seq_file *m)
 {
 	seq_printf(m, "DirectMap4k:    %8lu kB\n",
 			direct_pages_count[PG_LEVEL_4K] << 2);
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index d4b50b6428fa..4dcba7bf4ab9 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -51,6 +51,8 @@ static DEFINE_PER_CPU(bool, tdx_lp_initialized);
 
 static struct tdmr_info_list tdx_tdmr_list;
 
+static atomic_long_t tdx_pamt_count = ATOMIC_LONG_INIT(0);
+
 static atomic_t *pamt_refcounts;
 
 static enum tdx_module_status_t tdx_module_status;
@@ -2010,6 +2012,19 @@ int tdx_nr_pamt_pages(void)
 }
 EXPORT_SYMBOL_GPL(tdx_nr_pamt_pages);
 
+void tdx_meminfo(struct seq_file *m)
+{
+	unsigned long usage;
+
+	if (!cpu_feature_enabled(X86_FEATURE_TDX_HOST_PLATFORM))
+		return;
+
+	usage = atomic_long_read(&tdx_pamt_count) *
+		tdx_nr_pamt_pages() * PAGE_SIZE / SZ_1K;
+
+	seq_printf(m, "TDX:		%8lu kB\n", usage);
+}
+
 static u64 tdh_phymem_pamt_add(unsigned long hpa,
 			       struct list_head *pamt_pages)
 {
@@ -2017,7 +2032,7 @@ static u64 tdh_phymem_pamt_add(unsigned long hpa,
 		.rcx = hpa,
 	};
 	struct page *page;
-	u64 *p;
+	u64 *p, ret;
 
 	WARN_ON_ONCE(!IS_ALIGNED(hpa & PAGE_MASK, PMD_SIZE));
 
@@ -2027,7 +2042,12 @@ static u64 tdh_phymem_pamt_add(unsigned long hpa,
 		p++;
 	}
 
-	return seamcall(TDH_PHYMEM_PAMT_ADD, &args);
+	ret = seamcall(TDH_PHYMEM_PAMT_ADD, &args);
+
+	if (!ret)
+		atomic_long_inc(&tdx_pamt_count);
+
+	return ret;
 }
 
 static u64 tdh_phymem_pamt_remove(unsigned long hpa,
@@ -2045,6 +2065,8 @@ static u64 tdh_phymem_pamt_remove(unsigned long hpa,
 	if (ret)
 		return ret;
 
+	atomic_long_dec(&tdx_pamt_count);
+
 	p = &args.rdx;
 	for (int i = 0; i < tdx_nr_pamt_pages(); i++) {
 		page = phys_to_page(*p);

---

## [12] Kirill A. Shutemov — 2025-06-09
*Subject: [PATCHv2 11/12] x86/virt/tdx: Enable Dynamic PAMT*

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
---
 arch/x86/include/asm/tdx.h  | 6 +++++-
 arch/x86/virt/vmx/tdx/tdx.c | 8 ++++++++
 arch/x86/virt/vmx/tdx/tdx.h | 3 ---
 3 files changed, 13 insertions(+), 4 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 853471e1eda1..8897c7416309 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -13,6 +13,10 @@
 #include <asm/tdx_errno.h>
 #include <asm/shared/tdx.h>
 
+/* Bit definitions of TDX_FEATURES0 metadata field */
+#define TDX_FEATURES0_NO_RBP_MOD		BIT_ULL(18)
+#define TDX_FEATURES0_DYNAMIC_PAMT		BIT_ULL(36)
+
 #ifndef __ASSEMBLER__
 
 #include <uapi/asm/mce.h>
@@ -108,7 +112,7 @@ const struct tdx_sys_info *tdx_get_sysinfo(void);
 
 static inline bool tdx_supports_dynamic_pamt(const struct tdx_sys_info *sysinfo)
 {
-	return false; /* To be enabled when kernel is ready */
+	return sysinfo->features.tdx_features0 & TDX_FEATURES0_DYNAMIC_PAMT;
 }
 
 int tdx_guest_keyid_alloc(void);
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 4dcba7bf4ab9..d9f27647424d 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1047,6 +1047,8 @@ static int construct_tdmrs(struct list_head *tmb_list,
 	return ret;
 }
 
+#define TDX_SYS_CONFIG_DYNAMIC_PAMT	BIT(16)
+
 static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
 {
 	struct tdx_module_args args = {};
@@ -1074,6 +1076,12 @@ static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
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

## [13] Kirill A. Shutemov — 2025-06-09
*Subject: [PATCHv2 12/12] Documentation/x86: Add documentation for TDX's Dynamic PAMT*

Expand TDX documentation to include information on the Dynamic PAMT
feature.

The new section explains PAMT support in the TDX module and how it is
enabled on the kernel side.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 Documentation/arch/x86/tdx.rst | 108 +++++++++++++++++++++++++++++++++
 1 file changed, 108 insertions(+)

diff --git a/Documentation/arch/x86/tdx.rst b/Documentation/arch/x86/tdx.rst
index 719043cd8b46..a1dc50dd6f57 100644
--- a/Documentation/arch/x86/tdx.rst
+++ b/Documentation/arch/x86/tdx.rst
@@ -99,6 +99,114 @@ initialize::
 
   [..] virt/tdx: module initialization failed ...
 
+Dynamic PAMT
+------------
+
+Dynamic PAMT support in TDX module
+~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
+
+Dynamic PAMT is a TDX feature that allows VMM to allocate PAMT_4K as
+needed. PAMT_1G and PAMT_2M are still allocated statically at the time of
+TDX module initialization. At init stage allocation of PAMT_4K is replaced
+with PAMT_PAGE_BITMAP which currently requires one bit of memory per 4k.
+
+VMM is responsible for allocating and freeing PAMT_4K. There's a couple of
+new SEAMCALLs for this: TDH.PHYMEM.PAMT.ADD and TDH.PHYMEM.PAMT.REMOVE.
+They add/remove PAMT memory in form of page pair. There's no requirement
+for these pages to be contiguous.
+
+Page pair supplied via TDH.PHYMEM.PAMT.ADD will cover specified 2M region.
+It allows any 4K from the region to be usable by TDX module.
+
+With Dynamic PAMT, a number of SEAMCALLs can now fail due to missing PAMT
+memory (TDX_MISSING_PAMT_PAGE_PAIR):
+
+ - TDH.MNG.CREATE
+ - TDH.MNG.ADDCX
+ - TDH.VP.ADDCX
+ - TDH.VP.CREATE
+ - TDH.MEM.PAGE.ADD
+ - TDH.MEM.PAGE.AUG
+ - TDH.MEM.PAGE.DEMOTE
+ - TDH.MEM.PAGE.RELOCATE
+
+Basically, if you supply memory to a TD, this memory has to backed by PAMT
+memory.
+
+Once no TD uses the 2M range, the PAMT page pair can be reclaimed with
+TDH.PHYMEM.PAMT.REMOVE.
+
+TDX module track PAMT memory usage and can give VMM a hint that PAMT
+memory can be removed. Such hint is provided from all SEAMCALLs that
+removes memory from TD:
+
+ - TDH.MEM.SEPT.REMOVE
+ - TDH.MEM.PAGE.REMOVE
+ - TDH.MEM.PAGE.PROMOTE
+ - TDH.MEM.PAGE.RELOCATE
+ - TDH.PHYMEM.PAGE.RECLAIM
+
+With Dynamic PAMT, TDH.MEM.PAGE.DEMOTE takes PAMT page pair as additional
+input to populate PAMT_4K on split. TDH.MEM.PAGE.PROMOTE returns no longer
+needed PAMT page pair.
+
+PAMT memory is global resource and not tied to a specific TD. TDX modules
+maintains PAMT memory in a radix tree addressed by physical address. Each
+entry in the tree can be locked with shared or exclusive lock. Any
+modification of the tree requires exclusive lock.
+
+Any SEAMCALL that takes explicit HPA as an argument will walk the tree
+taking shared lock on entries. It required to make sure that the page
+pointed by HPA is of compatible type for the usage.
+
+TDCALLs don't take PAMT locks as none of the take HPA as an argument.
+
+Dynamic PAMT enabling in kernel
+~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
+
+Kernel maintains refcounts for every 2M regions with two helpers
+tdx_pamt_get() and tdx_pamt_put().
+
+The refcount represents number of users for the PAMT memory in the region.
+Kernel calls TDH.PHYMEM.PAMT.ADD on 0->1 transition and
+TDH.PHYMEM.PAMT.REMOVE on transition 1->0.
+
+The function tdx_alloc_page() allocates a new page and ensures that it is
+backed by PAMT memory. Pages allocated in this manner are ready to be used
+for a TD. The function tdx_free_page() frees the page and releases the
+PAMT memory for the 2M region if it is no longer needed.
+
+PAMT memory gets allocated as part of TD init, VCPU init, on populating
+SEPT tree and adding guest memory (both during TD build and via AUG on
+accept). Splitting 2M page into 4K also requires PAMT memory.
+
+PAMT memory removed on reclaim of control pages and guest memory.
+
+Populating PAMT memory on fault and on split is tricky as kernel cannot
+allocate memory from the context where it is needed. These code paths use
+pre-allocated PAMT memory pools.
+
+Previous attempt on Dynamic PAMT enabling
+~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
+
+The initial attempt at kernel enabling was quite different. It was built
+around lazy PAMT allocation: only trying to add a PAMT page pair if a
+SEAMCALL fails due to a missing PAMT and reclaiming it based on hints
+provided by the TDX module.
+
+The motivation was to avoid duplicating the PAMT memory refcounting that
+the TDX module does on the kernel side.
+
+This approach is inherently more racy as there is no serialization of
+PAMT memory add/remove against SEAMCALLs that add/remove memory for a TD.
+Such serialization would require global locking, which is not feasible.
+
+This approach worked, but at some point it became clear that it could not
+be robust as long as the kernel avoids TDX_OPERAND_BUSY loops.
+TDX_OPERAND_BUSY will occur as a result of the races mentioned above.
+
+This approach was abandoned in favor of explicit refcounting.
+
 TDX Interaction to Other Kernel Components
 ------------------------------------------

---

## [14] Chao Gao — 2025-06-10
*Subject: Re: [PATCHv2 04/12] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

>+static int tdx_alloc_pamt_pages(struct list_head *pamt_pages)
>+{

this goto isn't needed. it is used only once. so we can just free the pages and
return -ENOMEM here.

>+		list_add(&page->lru, pamt_pages);
>+	}

I think this needs a comment for the return values 0/1/-EIO above the function.

>+
>+	return 0;

This also needs a comment. i.e., why return success directly for large pages?

<snip>

---

## [15] Kirill A. Shutemov — 2025-06-10
*Subject: [PATCHv2.1 04/12] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

The new helpers allocate and free pages that can be used for a TDs.

Besides page allocation and freeing, these helpers also take care about
managing PAMT memory, if kernel runs on a platform with Dynamic PAMT
supported.

tdx_pamt_get()/put() helpers take care of PAMT allocation/freeing and
its refcounting.

PAMT memory is allocated when refcount for the 2M range crosses from 0
to 1 and gets freed back on when it is dropped to zero. These
transitions can happen concurrently and pamt_lock spinlock serializes
them.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/include/asm/tdx.h       |   3 +
 arch/x86/include/asm/tdx_errno.h |   6 +
 arch/x86/virt/vmx/tdx/tdx.c      | 224 +++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h      |   2 +
 4 files changed, 235 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 583d6fe66821..d9a77147412f 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -115,6 +115,9 @@ int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
 
+struct page *tdx_alloc_page(void);
+void tdx_free_page(struct page *page);
+
 struct tdx_td {
 	/* TD root structure: */
 	struct page *tdr_page;
diff --git a/arch/x86/include/asm/tdx_errno.h b/arch/x86/include/asm/tdx_errno.h
index d418934176e2..0b3332c2d6b2 100644
--- a/arch/x86/include/asm/tdx_errno.h
+++ b/arch/x86/include/asm/tdx_errno.h
@@ -18,6 +18,7 @@
 #define TDX_PREVIOUS_TLB_EPOCH_BUSY		0x8000020100000000ULL
 #define TDX_RND_NO_ENTROPY			0x8000020300000000ULL
 #define TDX_PAGE_METADATA_INCORRECT		0xC000030000000000ULL
+#define TDX_HPA_RANGE_NOT_FREE			0xC000030400000000ULL
 #define TDX_VCPU_NOT_ASSOCIATED			0x8000070200000000ULL
 #define TDX_KEY_GENERATION_FAILED		0x8000080000000000ULL
 #define TDX_KEY_STATE_INCORRECT			0xC000081100000000ULL
@@ -86,5 +87,10 @@ static inline bool tdx_operand_busy(u64 err)
 {
 	return tdx_status(err) == TDX_OPERAND_BUSY;
 }
+
+static inline bool tdx_hpa_range_not_free(u64 err)
+{
+	return tdx_status(err) == TDX_HPA_RANGE_NOT_FREE;
+}
 #endif /* __ASSEMBLER__ */
 #endif /* _X86_TDX_ERRNO_H */
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index ad9d7a30989d..3830fbc06397 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2000,3 +2000,227 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
 	return seamcall(TDH_PHYMEM_PAGE_WBINVD, &args);
 }
 EXPORT_SYMBOL_GPL(tdh_phymem_page_wbinvd_hkid);
+
+static int tdx_nr_pamt_pages(void)
+{
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return 0;
+
+	return tdx_sysinfo.tdmr.pamt_4k_entry_size * PTRS_PER_PTE / PAGE_SIZE;
+}
+
+static u64 tdh_phymem_pamt_add(unsigned long hpa,
+			       struct list_head *pamt_pages)
+{
+	struct tdx_module_args args = {
+		.rcx = hpa,
+	};
+	struct page *page;
+	u64 *p;
+
+	WARN_ON_ONCE(!IS_ALIGNED(hpa & PAGE_MASK, PMD_SIZE));
+
+	p = &args.rdx;
+	list_for_each_entry(page, pamt_pages, lru) {
+		*p = page_to_phys(page);
+		p++;
+	}
+
+	return seamcall(TDH_PHYMEM_PAMT_ADD, &args);
+}
+
+static u64 tdh_phymem_pamt_remove(unsigned long hpa,
+				  struct list_head *pamt_pages)
+{
+	struct tdx_module_args args = {
+		.rcx = hpa,
+	};
+	struct page *page;
+	u64 *p, ret;
+
+	WARN_ON_ONCE(!IS_ALIGNED(hpa & PAGE_MASK, PMD_SIZE));
+
+	ret = seamcall_ret(TDH_PHYMEM_PAMT_REMOVE, &args);
+	if (ret)
+		return ret;
+
+	p = &args.rdx;
+	for (int i = 0; i < tdx_nr_pamt_pages(); i++) {
+		page = phys_to_page(*p);
+		list_add(&page->lru, pamt_pages);
+		p++;
+	}
+
+	return ret;
+}
+
+static DEFINE_SPINLOCK(pamt_lock);
+
+static void tdx_free_pamt_pages(struct list_head *pamt_pages)
+{
+	struct page *page;
+
+	while ((page = list_first_entry_or_null(pamt_pages, struct page, lru))) {
+		list_del(&page->lru);
+		__free_page(page);
+	}
+}
+
+static int tdx_alloc_pamt_pages(struct list_head *pamt_pages)
+{
+	for (int i = 0; i < tdx_nr_pamt_pages(); i++) {
+		struct page *page = alloc_page(GFP_KERNEL);
+		if (!page) {
+			tdx_free_pamt_pages(pamt_pages);
+			return -ENOMEM;
+		}
+		list_add(&page->lru, pamt_pages);
+	}
+	return 0;
+}
+
+/*
+ * Returns >=0 on success. -errno on failure.
+ *
+ * Non-zero return value indicates that the pamt_pages unused and can be freed.
+ */
+static int tdx_pamt_add(atomic_t *pamt_refcount, unsigned long hpa,
+			struct list_head *pamt_pages)
+{
+	u64 err;
+
+	guard(spinlock)(&pamt_lock);
+
+	hpa = ALIGN_DOWN(hpa, PMD_SIZE);
+
+	/*
+	 * Lost race to other tdx_pamt_add(). Other task has already allocated
+	 * PAMT memory for the HPA.
+	 *
+	 * Return 1 to indicate that pamt_pages is unused and can be freed.
+	 */
+	if (atomic_read(pamt_refcount) != 0) {
+		atomic_inc(pamt_refcount);
+		return 1;
+	}
+
+	err = tdh_phymem_pamt_add(hpa | TDX_PS_2M, pamt_pages);
+
+	/*
+	 * tdx_hpa_range_not_free() is true if current task won race
+	 * against tdx_pamt_put().
+	 */
+	if (err && !tdx_hpa_range_not_free(err)) {
+		pr_err("TDH_PHYMEM_PAMT_ADD failed: %#llx\n", err);
+		return -EIO;
+	}
+
+	atomic_set(pamt_refcount, 1);
+
+	/*
+	 * Current task won race against tdx_pamt_put() and prevented it
+	 * from freeing PAMT memory.
+	 *
+	 * Return 1 to indicate that pamt_pages is unused and can be freed.
+	 */
+	if (tdx_hpa_range_not_free(err))
+		return 1;
+
+	return 0;
+}
+
+static int tdx_pamt_get(struct page *page, enum pg_level level)
+{
+	unsigned long hpa = page_to_phys(page);
+	atomic_t *pamt_refcount;
+	LIST_HEAD(pamt_pages);
+	int ret;
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return 0;
+
+	/*
+	 * Only PAMT_4K is allocated dynamically. PAMT_2M and PAMT_1G is
+	 * allocated statically on TDX module initialization.
+	 */
+	if (level != PG_LEVEL_4K)
+		return 0;
+
+	pamt_refcount = tdx_get_pamt_refcount(hpa);
+	WARN_ON_ONCE(atomic_read(pamt_refcount) < 0);
+
+	if (atomic_inc_not_zero(pamt_refcount))
+		return 0;
+
+	if (tdx_alloc_pamt_pages(&pamt_pages))
+		return -ENOMEM;
+
+	ret = tdx_pamt_add(pamt_refcount, hpa, &pamt_pages);
+	if (ret)
+		tdx_free_pamt_pages(&pamt_pages);
+
+	return ret >= 0 ? 0 : ret;
+}
+
+static void tdx_pamt_put(struct page *page, enum pg_level level)
+{
+	unsigned long hpa = page_to_phys(page);
+	atomic_t *pamt_refcount;
+	LIST_HEAD(pamt_pages);
+	u64 err;
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return;
+
+	if (level != PG_LEVEL_4K)
+		return;
+
+	hpa = ALIGN_DOWN(hpa, PMD_SIZE);
+
+	pamt_refcount = tdx_get_pamt_refcount(hpa);
+	if (!atomic_dec_and_test(pamt_refcount))
+		return;
+
+	scoped_guard(spinlock, &pamt_lock) {
+		/* Lost race against tdx_pamt_add()? */
+		if (atomic_read(pamt_refcount) != 0)
+			return;
+
+		err = tdh_phymem_pamt_remove(hpa | TDX_PS_2M, &pamt_pages);
+
+		if (err) {
+			atomic_inc(pamt_refcount);
+			pr_err("TDH_PHYMEM_PAMT_REMOVE failed: %#llx\n", err);
+			return;
+		}
+	}
+
+	tdx_free_pamt_pages(&pamt_pages);
+}
+
+struct page *tdx_alloc_page(void)
+{
+	struct page *page;
+
+	page = alloc_page(GFP_KERNEL);
+	if (!page)
+		return NULL;
+
+	if (tdx_pamt_get(page, PG_LEVEL_4K)) {
+		__free_page(page);
+		return NULL;
+	}
+
+	return page;
+}
+EXPORT_SYMBOL_GPL(tdx_alloc_page);
+
+void tdx_free_page(struct page *page)
+{
+	if (!page)
+		return;
+
+	tdx_pamt_put(page, PG_LEVEL_4K);
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

## [16] Chao Gao — 2025-06-12
*Subject: Re: [PATCHv2 08/12] KVM: TDX: Handle PAMT allocation in fault path*

> int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
> 			      enum pg_level level, kvm_pfn_t pfn)

nit: hoist this before the tdx_pamt_get() above. otherwise, tdx_pamt_put()
should be called in this error path.

>@@ -1562,10 +1577,16 @@ int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
> 	 * barrier in tdx_td_finalize().

<snip>

---

## [17] Kirill A. Shutemov — 2025-06-12
*Subject: [PATCHv2.1 08/12] KVM: TDX: Handle PAMT allocation in fault path*

There are two distinct cases when the kernel needs to allocate PAMT
memory in the fault path: for SEPT page tables in tdx_sept_link_private_spt()
and for leaf pages in tdx_sept_set_private_spte().

These code paths run in atomic context. Use a pre-allocated per-VCPU
pool for memory allocations.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/include/asm/tdx.h  |  4 ++++
 arch/x86/kvm/vmx/tdx.c      | 40 ++++++++++++++++++++++++++++++++-----
 arch/x86/virt/vmx/tdx/tdx.c | 23 +++++++++++++++------
 virt/kvm/kvm_main.c         |  1 +
 4 files changed, 57 insertions(+), 11 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 47092eb13eb3..39f8dd7e0f06 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -116,6 +116,10 @@ u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
 
 int tdx_nr_pamt_pages(void);
+int tdx_pamt_get(struct page *page, enum pg_level level,
+		 struct page *(alloc)(void *data), void *data);
+void tdx_pamt_put(struct page *page, enum pg_level level);
+
 struct page *tdx_alloc_page(void);
 void tdx_free_page(struct page *page);
 
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 36c3c9f8a62c..2f058e17fd73 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1537,16 +1537,31 @@ static int tdx_mem_page_record_premap_cnt(struct kvm *kvm, gfn_t gfn,
 	return 0;
 }
 
+static struct page *tdx_alloc_pamt_page_atomic(void *data)
+{
+	struct kvm_vcpu *vcpu = data;
+	void *p;
+
+	p = kvm_mmu_memory_cache_alloc(&vcpu->arch.pamt_page_cache);
+	return virt_to_page(p);
+}
+
 int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 			      enum pg_level level, kvm_pfn_t pfn)
 {
+	struct kvm_vcpu *vcpu = kvm_get_running_vcpu();
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 	struct page *page = pfn_to_page(pfn);
+	int ret;
 
 	/* TODO: handle large pages. */
 	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
 		return -EINVAL;
 
+	ret = tdx_pamt_get(page, level, tdx_alloc_pamt_page_atomic, vcpu);
+	if (ret)
+		return ret;
+
 	/*
 	 * Because guest_memfd doesn't support page migration with
 	 * a_ops->migrate_folio (yet), no callback is triggered for KVM on page
@@ -1562,10 +1577,16 @@ int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
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
+		tdx_pamt_put(page, level);
+
+	return ret;
 }
 
 static int tdx_sept_drop_private_spte(struct kvm *kvm, gfn_t gfn,
@@ -1622,17 +1643,26 @@ int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
 			      enum pg_level level, void *private_spt)
 {
 	int tdx_level = pg_level_to_tdx_sept_level(level);
-	gpa_t gpa = gfn_to_gpa(gfn);
+	struct kvm_vcpu *vcpu = kvm_get_running_vcpu();
 	struct page *page = virt_to_page(private_spt);
+	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 err, entry, level_state;
+	int ret;
+
+	ret = tdx_pamt_get(page, PG_LEVEL_4K, tdx_alloc_pamt_page_atomic, vcpu);
+	if (ret)
+		return ret;
 
 	err = tdh_mem_sept_add(&to_kvm_tdx(kvm)->td, gpa, tdx_level, page, &entry,
 			       &level_state);
-	if (unlikely(tdx_operand_busy(err)))
+	if (unlikely(tdx_operand_busy(err))) {
+		tdx_pamt_put(page, PG_LEVEL_4K);
 		return -EBUSY;
+	}
 
 	if (KVM_BUG_ON(err, kvm)) {
 		pr_tdx_error_2(TDH_MEM_SEPT_ADD, err, entry, level_state);
+		tdx_pamt_put(page, PG_LEVEL_4K);
 		return -EIO;
 	}
 
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 0cbf052c64e9..4fc9f4ae8165 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2067,14 +2067,22 @@ static void tdx_free_pamt_pages(struct list_head *pamt_pages)
 	}
 }
 
-static int tdx_alloc_pamt_pages(struct list_head *pamt_pages)
+static int tdx_alloc_pamt_pages(struct list_head *pamt_pages,
+				 struct page *(alloc)(void *data), void *data)
 {
 	for (int i = 0; i < tdx_nr_pamt_pages(); i++) {
-		struct page *page = alloc_page(GFP_KERNEL);
+		struct page *page;
+
+		if (alloc)
+			page = alloc(data);
+		else
+			page = alloc_page(GFP_KERNEL);
+
 		if (!page) {
 			tdx_free_pamt_pages(pamt_pages);
 			return -ENOMEM;
 		}
+
 		list_add(&page->lru, pamt_pages);
 	}
 	return 0;
@@ -2130,7 +2138,8 @@ static int tdx_pamt_add(atomic_t *pamt_refcount, unsigned long hpa,
 	return 0;
 }
 
-static int tdx_pamt_get(struct page *page, enum pg_level level)
+int tdx_pamt_get(struct page *page, enum pg_level level,
+		 struct page *(alloc)(void *data), void *data)
 {
 	unsigned long hpa = page_to_phys(page);
 	atomic_t *pamt_refcount;
@@ -2153,7 +2162,7 @@ static int tdx_pamt_get(struct page *page, enum pg_level level)
 	if (atomic_inc_not_zero(pamt_refcount))
 		return 0;
 
-	if (tdx_alloc_pamt_pages(&pamt_pages))
+	if (tdx_alloc_pamt_pages(&pamt_pages, alloc, data))
 		return -ENOMEM;
 
 	ret = tdx_pamt_add(pamt_refcount, hpa, &pamt_pages);
@@ -2162,8 +2171,9 @@ static int tdx_pamt_get(struct page *page, enum pg_level level)
 
 	return ret >= 0 ? 0 : ret;
 }
+EXPORT_SYMBOL_GPL(tdx_pamt_get);
 
-static void tdx_pamt_put(struct page *page, enum pg_level level)
+void tdx_pamt_put(struct page *page, enum pg_level level)
 {
 	unsigned long hpa = page_to_phys(page);
 	atomic_t *pamt_refcount;
@@ -2198,6 +2208,7 @@ static void tdx_pamt_put(struct page *page, enum pg_level level)
 
 	tdx_free_pamt_pages(&pamt_pages);
 }
+EXPORT_SYMBOL_GPL(tdx_pamt_put);
 
 struct page *tdx_alloc_page(void)
 {
@@ -2207,7 +2218,7 @@ struct page *tdx_alloc_page(void)
 	if (!page)
 		return NULL;
 
-	if (tdx_pamt_get(page, PG_LEVEL_4K)) {
+	if (tdx_pamt_get(page, PG_LEVEL_4K, NULL, NULL)) {
 		__free_page(page);
 		return NULL;
 	}
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index eec82775c5bf..6add012532a0 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -436,6 +436,7 @@ void *kvm_mmu_memory_cache_alloc(struct kvm_mmu_memory_cache *mc)
 	BUG_ON(!p);
 	return p;
 }
+EXPORT_SYMBOL_GPL(kvm_mmu_memory_cache_alloc);
 #endif
 
 static void kvm_vcpu_init(struct kvm_vcpu *vcpu, struct kvm *kvm, unsigned id)

---

## [18] Kirill A. Shutemov — 2025-06-25
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Mon, Jun 09, 2025 at 10:13:28PM +0300, Kirill A. Shutemov wrote:
> This patchset enables Dynamic PAMT in TDX. Please review.

Gentle ping?

The patchset is crucial to get TDX adopted. The upfront memory cost of
enabling TDX for the machine is too high, especially if you don't know in
advance if the machine will run TDX guests.

---

## [19] Dave Hansen — 2025-06-25
*Subject: Re: [PATCHv2 01/12] x86/tdx: Consolidate TDX error handling*

On 6/9/25 12:13, Kirill A. Shutemov wrote:
> Move all (host, kvm, guest) code related to TDX error handling into
> <asm/tdx_errno.h>.

I really prefer that code moves and introduction of new things be done
_separately_.

It's a lot easier to check for errors in the move when it's the on

...
>  	ret = __tdcall(TDG_MR_REPORT, &args);
>  	if (ret) {

That said, the resulting code here is a lot nicer that what you started
with.

...
> -/*
> - * TDX module SEAMCALL leaf function error codes

Kai, you were responsible for this nugget. What do you think of this patch?


> --- a/arch/x86/kvm/vmx/tdx.c
> +++ b/arch/x86/kvm/vmx/tdx.c

Isaku, this one was yours (along with the whitespace damage). What do
you think of this patch?

---

## [20] Dave Hansen — 2025-06-25
*Subject: Re: [PATCHv2.1 04/12] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

Kirill (and anybody else reading this),

Please stop doing these vXXX.1 patches. b4 can't deal with them. I don't
know if it's _supposed_ to be able to, but I'm not sure I even want
Konstantin spending time on making b4 handle this kind of thing. I
honestly don't want to make my scripts deal with them either.

It's one thing to post a whole new series 2 hours after the old one.
It's a very different thing to resend a series in the 2 *weeks* since
you updated it.

I'd much rather you resend the series than just leave these tangles for
the maintainers to unwind.

---

## [21] Dave Hansen — 2025-06-25
*Subject: Re: [PATCHv2 02/12] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

>  /*
>   * Locate a NUMA node which should hold the allocation of the @tdmr

This is the wrong place to do this.

Hide it in tdmr_get_pamt_sz(). Don't inject it in the main code flow
here and complicate the for loop.

---

## [22] Dave Hansen — 2025-06-25
*Subject: Re: [PATCHv2 03/12] x86/virt/tdx: Allocate reference counters for
 PAMT memory*

On 6/9/25 12:13, Kirill A. Shutemov wrote:
> The PAMT memory holds metadata for TDX-protected memory. With Dynamic
> PAMT, PAMT_4K is allocated on demand. The kernel supplies the TDX module

... and yes, this is another boot-time allocation that seems to be
counter to the goal of reducing the boot-time TDX memory footprint.

Please mention the 0.4%=>0.0004% overhead here in addition to the cover
letter. It's important.

> Tracking PAMT memory usage on the kernel side duplicates what TDX module
> does.  It is possible to avoid this by lazily allocating PAMT memory on

Just a nit on changelog formatting: It would be ideal if you could make
it totally clear that you are transitioning from "what this patch does"
to "alternate considered designs".

> --- a/arch/x86/virt/vmx/tdx/tdx.c
> +++ b/arch/x86/virt/vmx/tdx/tdx.c

Comments, please. How big is this? When is it allocated?

In this case, it's even sparse, right? That's *SUPER* unusual for a
kernel data structure.

>  static enum tdx_module_status_t tdx_module_status;
>  static DEFINE_MUTEX(tdx_module_lock);

"get refcount" usually means "get a reference". This is looking up the
location of the refcount.

I think this needs a better name.

> +static int pamt_refcount_populate(pte_t *pte, unsigned long addr, void *data)
> +{

This is getting to be severely under-commented.

I also got this far into the patch and I'd forgotten about the sparse
allocation and was scratching my head about what pte's have to do with
dynamically allocating part of the PAMT.

That point to a pretty severe deficit in the cover letter, changelogs
and comments leading up to this point.

> +	unsigned long vaddr;
> +	pte_t entry;

This ^ is an optimization, right? Could it be comment appropriately, please?

> +	vaddr = __get_free_page(GFP_KERNEL | __GFP_ZERO);
> +	if (!vaddr)

Gah, we really need a kpte_to_vaddr() helper here. This is really ugly.
How many of these are in the tree?

> +	spin_lock(&init_mm.page_table_lock);
> +	if (!pte_none(ptep_get(pte))) {

Is there really a case where this gets called on unpopulated ptes? How?

> +		pte_clear(&init_mm, addr, pte);
> +		free_page(vaddr);

Please try to vertically align these:

	start = (...)tdx_get_pamt_refcount(PFN_PHYS(start_pfn));
	end   = (...)tdx_get_pamt_refcount(PFN_PHYS(end_pfn + 1));
	start = round_down(start, PAGE_SIZE);
	end   = round_up(    end, PAGE_SIZE);

> +	return apply_to_page_range(&init_mm, start, end - start,
> +				   pamt_refcount_populate, NULL);

But, I've staring at these for maybe 5 minutes. I think I've made sense
of it.

alloc_pamt_refcount() is taking a relatively arbitrary range of pfns.
Those PFNs come from memory map and NUMA layout so they don't have any
real alignment guarantees.

This code translates the memory range into a range of virtual addresses
in the *virtual* refcount table. That table is sparse and might not be
allocated. It is populated 4k at a time and since the start/end_pfn
don't have any alignment guarantees, there's no telling onto which page
they map into the refcount table. This has to be conservative and round
'start' down and 'end' up. This might overlap with previous refcount
table populations.

Is that all correct?

That seems ... medium to high complexity to me. Is there some reason
none of it is documented or commented? Like, I think it's not been
mentioned a single time anywhere.

> +static int init_pamt_metadata(void)
> +{
Finally, we get to a description of what's actually going on. But, still
nothing has told me why this is necessary directly.

If it were me, I'd probably split this up into two patches. The first
would just do:

	area = vmalloc(size);

The second would do all the fancy sparse population.

But either way, I've hit a wall on this. This is too impenetrable as it
stands to review further. I'll eagerly await a more approachable v3.

---

## [23] Dave Hansen — 2025-06-25
*Subject: Re: [PATCHv2 04/12] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On 6/9/25 12:13, Kirill A. Shutemov wrote:
>  arch/x86/include/asm/tdx.h       |   3 +
>  arch/x86/include/asm/tdx_errno.h |   6 +

Please go through this whole series and add appropriate comments and
explanations.

There are 4 lines of comments in the 216 lines of new code.

I'll give some examples:

> +static int tdx_nr_pamt_pages(void)

Despite the naming this function does not return the number of TDX
PAMT pages. It returns the number of pages needed for each *dynamic*
PAMT granule.

The naming is not consistent with something used only for dynamic PAMT
support. This kind of comment would help, but is not a replacement for
good naming:

/*
 * How many pages are needed for the TDX
 * dynamic page metadata for a 2M region?
 */

Oh, and what the heck is with the tdx_supports_dynamic_pamt() check?
Isn't it illegal to call these functions without dynamic PAMT in
place? Wouldn't the TDH_PHYMEM_PAMT_ADD blow up if you hand it 0's
in args.rdx?

> +static int tdx_nr_pamt_pages(void)
> +{

This is sheer voodoo. Voodoo on its own is OK. But uncommented voodoo
is not.

Imagine what would happen if, for instance, someone got confused and did:

	tdx_alloc_pamt_pages(&pamd_pages);
	tdx_alloc_pamt_pages(&pamd_pages);
	tdx_alloc_pamt_pages(&pamd_pages);

It would *work* because the allocation function would just merrily
shove lots of pages on the list. But when it's consumed you'd run off
the end of the data structure in this function far, far away from the
bug site.

The least you can do here is comment what's going on. Because treating
a structure like an array is obtuse at best.

Even better would be to have a check to ensure that the pointer magic
doesn't run off the end of the struct:

	if (p - &args.rcx >= sizeof(args)/sizeof(u64)) {
		WARN_ON_ONCE(1);
		break;
	}

or some other pointer voodoo.

> +
> +	return seamcall(TDH_PHYMEM_PAMT_ADD, &args);

---

## [24] Dave Hansen — 2025-06-25
*Subject: Re: [PATCHv2 04/12] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On 6/9/25 19:36, Chao Gao wrote:
>> +static int tdx_alloc_pamt_pages(struct list_head *pamt_pages)
>> +{

<shrug>

There's no rule saying that gotos need to be used more than once. It's
idiomatic kernel C to use a goto as an error landing site. In fact, I
*prefer* this because it lets me read the main, non-error-case flow
through the function. Then, at my leisure, I can review the error handling.

This is also, IMNHO, less error-prone to someone adding code and doing a
plain return without freeing the pages.

Third, the goto keeps the indentation down.

So, the suggestion here is well intended, but I think it's flawed in
multiple ways. If you write your code this way (free of one-use gotos),
I won't complain too much. But if you suggest other folks get rid of the
gotos, I'm not super happy.

So, Kirill, do it whatever way you want.

But, Chao, please don't keep suggesting things like this at least in
junk I've got to merge.

>> +	if (tdx_hpa_range_not_free(err))
>> +		return 1;

You and I are in full agreement that this series is gloriously
unencumbered by comments at this point.

---

## [25] Edgecombe, Rick P — 2025-06-25
*Subject: Re: [PATCHv2 01/12] x86/tdx: Consolidate TDX error handling*

On Wed, 2025-06-25 at 10:58 -0700, Dave Hansen wrote:
> > --- a/arch/x86/kvm/vmx/tdx.c
> > +++ b/arch/x86/kvm/vmx/tdx.c

I think this actually got added by Paolo, suggested by Binbin. I like these
added helpers a lot. KVM code is often open coded for bitwise stuff, but since
Paolo added tdx_operand_busy(), I like the idea of following the pattern more
broadly. I'm on the fence about tdx_status() though.

---

## [26] Sean Christopherson — 2025-06-25
*Subject: Re: [PATCHv2 01/12] x86/tdx: Consolidate TDX error handling*

On Wed, Jun 25, 2025, Rick P Edgecombe wrote:
> On Wed, 2025-06-25 at 10:58 -0700, Dave Hansen wrote:
> > > --- a/arch/x86/kvm/vmx/tdx.c

Can we turn them into macros that make it super obvious they are checking if the
error code *is* xyz?  E.g.

#define IS_TDX_ERR_OPERAND_BUSY
#define IS_TDX_ERR_OPERAND_INVALID
#define IS_TDX_ERR_NO_ENTROPY
#define IS_TDX_ERR_SW_ERROR

As is, it's not at all clear that things like tdx_success() are simply checks,
as opposed to commands.

---

## [27] Edgecombe, Rick P — 2025-06-25
*Subject: Re: [PATCHv2 01/12] x86/tdx: Consolidate TDX error handling*

On Wed, 2025-06-25 at 14:27 -0700, Sean Christopherson wrote:
> Can we turn them into macros that make it super obvious they are checking if the
> error code *is* xyz?  E.g.

Good idea.

---

## [28] Edgecombe, Rick P — 2025-06-25
*Subject: Re: [PATCHv2 08/12] KVM: TDX: Handle PAMT allocation in fault path*

On Mon, 2025-06-09 at 22:13 +0300, Kirill A. Shutemov wrote:
> There are two distinct cases when the kernel needs to allocate PAMT
> memory in the fault path: for SEPT page tables in tdx_sept_link_private_spt()

This log is way to thin. It should explain the design, justify the function
pointer, excuse the export, etc.

> 
> Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

level is known to be PG_LEVEL_4K if you swap the order of these. I'm guessing
left over from order swap.

> @@ -1562,10 +1577,16 @@ int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
>  	 * barrier in tdx_td_finalize().

tdx_mem_page_record_premap_cnt() doesn't need tdx_pamt_get(). I think it could
be skipped if the order is re-arranged.

> +
> +	if (ret)

It's not great I think. A branch between a function pointer and alloc_page,
where there is only ever one value for the function pointer. There has to be a
better way?

>  		if (!page)
>  			goto fail;

Did you consider pre-allocating a page and returning it to the cache if it's not
needed. Or moving kvm_mmu_memory_cache_alloc() to a static inline in a header
that core x86 can use.

They all seem bad in different ways.

>  #endif
>

---

## [29] Edgecombe, Rick P — 2025-06-25
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Mon, 2025-06-09 at 22:13 +0300, Kirill A. Shutemov wrote:
> This patchset enables Dynamic PAMT in TDX. Please review.
> 

Did you run this through the latest TDX selftests? Specifically Reinette's WIP
MMU stress test would be real good to test on this.

---

## [30] Huang, Kai — 2025-06-26
*Subject: Re: [PATCHv2 01/12] x86/tdx: Consolidate TDX error handling*

On Wed, 2025-06-25 at 10:58 -0700, Hansen, Dave wrote:
> > -/*
> > - * TDX module SEAMCALL leaf function error codes

(sorry for getting into this late)

I am 100% with consolidating TDX definitions across KVM and the core kernel,
so thanks Kirill for doing this.

But as you suggested, I think it's better to split this patch into two:

 - One patch to just move error code from tdx_error.h in KVM and TDX guest
code to <asm/tdx_error.h>.
 - One patch to further introduce those helpers (tdx_rnd_no_entropy() etc)
and actually use them in the code.

It will be easier to review anyway.

---

## [31] Chao Gao — 2025-06-26
*Subject: Re: [PATCHv2 04/12] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Wed, Jun 25, 2025 at 01:09:05PM -0700, Dave Hansen wrote:
>On 6/9/25 19:36, Chao Gao wrote:
>>> +static int tdx_alloc_pamt_pages(struct list_head *pamt_pages)

Sure. I am still trying to develop a sense of good code. Thank you, Dave, for
correcting me and the detailed explanation.

---

## [32] Huang, Kai — 2025-06-26
*Subject: Re: [PATCHv2 03/12] x86/virt/tdx: Allocate reference counters for
 PAMT memory*

> +static int init_pamt_metadata(void)
> +{
		^
		build_tdx_memlist()

> +	 */
> +	area = get_vm_area(size, VM_IOREMAP);

I am not sure why VM_IOREMAP is used?  Or should we just use vmalloc()?

> +	if (!area)
> +		return -ENOMEM;

So this would goto the error path, which only calls free_tdx_memlist(),
which frees all existing TDX memory blocks that have already created.

Logically, it would be great to also free PAMT refcount pages too, but they
all can be freed at free_pamt_metadata() eventually, so it's OK.

But I think it would still be helpful to put a comment before
free_tdx_memlist() in the error path to call out.  Something like:

err:
	/*
	 * This only frees all TDX memory blocks that have been created.
	 * All PAMT refcount pages will be freed when init_tdx_module() 
	 * calls free_pamt_metadata() eventually.
	 */
	free_tdx_memlist(tmb_list);
	return ret;

> 
>

---

## [33] Huang, Kai — 2025-06-26
*Subject: Re: [PATCHv2 03/12] x86/virt/tdx: Allocate reference counters for
 PAMT memory*

On Thu, 2025-06-26 at 00:53 +0000, Huang, Kai wrote:
> > +	 */
> > +	area = get_vm_area(size, VM_IOREMAP);

Sorry please ignore the vmalloc() part.  I lost my brain a while :-(

---

## [34] kirill.shutemov@linux.intel.com — 2025-06-26
*Subject: Re: [PATCHv2 01/12] x86/tdx: Consolidate TDX error handling*

On Wed, Jun 25, 2025 at 02:27:21PM -0700, Sean Christopherson wrote:
> On Wed, Jun 25, 2025, Rick P Edgecombe wrote:
> > On Wed, 2025-06-25 at 10:58 -0700, Dave Hansen wrote:

I remember Dave explicitly asked for inline functions over macros where
possible.

Can we keep them as functions, but give the naming scheme you proposing
(but lowercase)?

---

## [35] Kirill A. Shutemov — 2025-06-26
*Subject: Re: [PATCHv2 02/12] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On Wed, Jun 25, 2025 at 11:06:16AM -0700, Dave Hansen wrote:
> >  /*
> >   * Locate a NUMA node which should hold the allocation of the @tdmr

Okay, makes sense.

---

## [36] Huang, Kai — 2025-06-26
*Subject: Re: [PATCHv2 02/12] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On Mon, 2025-06-09 at 22:13 +0300, Kirill A. Shutemov wrote:
> With Dynamic PAMT, the kernel no longer needs to allocate PAMT_4K on
> boot, but instead must allocate a page bitmap. 

PAMTs are not allocated on boot, but when module gets initialized.

So perhaps:

"on boot" -> "when TDX module gets initialized"

---

## [37] Huang, Kai — 2025-06-26
*Subject: Re: [PATCHv2 07/12] KVM: TDX: Preallocate PAMT pages to be used in
 page fault path*

On Mon, 2025-06-09 at 22:13 +0300, Kirill A. Shutemov wrote:
> Preallocate a page to be used in the link_external_spt() and
> set_external_spte() paths.

"a page" -> "required PAMT pages"?

> 
> In the worst-case scenario, handling a page fault might require a

"a tdx_nr_pamt_pages() pages" -> "tdx_nr_pamt_pages() pages".

---

## [38] Dave Hansen — 2025-06-26
*Subject: Re: [PATCHv2 01/12] x86/tdx: Consolidate TDX error handling*

On 6/26/25 02:25, kirill.shutemov@linux.intel.com wrote:
>> Can we turn them into macros that make it super obvious they are checking if the
>> error code *is* xyz?  E.g.

Macros versus function isn't super important. I think Sean was asking if
we could do:

	if (err == IS_TDX_ERR_OPERAND_BUSY)
		...

instead of:

	if (tdx_operand_busy(err))
		...

We can do that, bu we first need to know that the whole bottom of the
return code register is empty. Unfortunately, a quick grep of the TDX
module source shows a bunch of these:

>     return_val = api_error_with_operand_id(TDX_OPERAND_BUSY, OPERAND_ID_MIGSC);

I'll refrain from casting judgement on why the TDX module needs such
fancy, fine-grained error codes and our little hobby kernel over here
mostly gets by on a couple errno's ... but I digress.

Those fancy pants error codes are why we need:

static inline u64 tdx_status(u64 err)
{
	return err & TDX_STATUS_MASK;
}

and can't just check the err directly. We need to mask out the fancy
pants bits first.

To get to what Sean is asking for, we'd have to do the tdx_status()
masking in the low-level SEAMCALL helpers and have them all return a
masked error code. Or maybe just bite the bullet and mostly move over to
errno's.

That wouldn't be horrible. For errno's or a masked TDX-format err,
callers could always go digging in tdx_module_args if they need the bits
that got masked out. But it would take some work.

---

## [39] Sean Christopherson — 2025-06-26
*Subject: Re: [PATCHv2 01/12] x86/tdx: Consolidate TDX error handling*

On Thu, Jun 26, 2025, Dave Hansen wrote:
> On 6/26/25 02:25, kirill.shutemov@linux.intel.com wrote:
> >> Can we turn them into macros that make it super obvious they are checking if the

I don't care about function versus macro, but I'd prefer uppercase.  As Linus
pointed out[*], upper vs. lower case is about the usage and semantics as much as
it's about whether or not the thingie is literally a macro vs. function.

[*] https://lore.kernel.org/all/CAHk-=whGWM50Qq3Dgha8ByU7t_dqvrCk3JFBSw2+X0KUAWuT1g@mail.gmail.com

> Macros versus function isn't super important. I think Sean was asking if
> we could do:

No, I was thinking:

	if (IS_TDX_ERR_OPERAND_BUSY(err))

e.g. to so that it looks like IS_ERR(), which is a familiar pattern.

---

## [40] Dave Hansen — 2025-06-26
*Subject: Re: [PATCHv2 01/12] x86/tdx: Consolidate TDX error handling*

On 6/26/25 08:51, Sean Christopherson wrote:
> No, I was thinking:
> 

That would be a more more compelling if IS_ERR() worked on integers. It
works on pointers, so I'm not sure it's a pattern we want to apply to
integers here.

I kind of hate all of this. I'd kinda prefer that we just shove the TDX
error codes as far up into the helpers as possible rather than making
them easier to deal with in random code.

---

## [41] Adrian Hunter — 2025-06-27
*Subject: Re: [PATCHv2 04/12] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On 09/06/2025 22:13, Kirill A. Shutemov wrote:
> +static void tdx_pamt_put(struct page *page, enum pg_level level)
> +{

Won't any pages that have been used need to be cleared
before being freed.

> +	tdx_free_pamt_pages(&pamt_pages);
> +}

---

## [42] kirill.shutemov@linux.intel.com — 2025-06-27
*Subject: Re: [PATCHv2 01/12] x86/tdx: Consolidate TDX error handling*

On Thu, Jun 26, 2025 at 09:59:47AM -0700, Dave Hansen wrote:
> On 6/26/25 08:51, Sean Christopherson wrote:
> > No, I was thinking:

IS_ERR_VALUE() works on integers.

> I kind of hate all of this. I'd kinda prefer that we just shove the TDX
> error codes as far up into the helpers as possible rather than making

Stripping info from error code early in handling can backfire if we ever
would need this inf (like need to know which argument is problematic). We
suddenly can suddenly be in position to rework all callers.

---

## [43] kirill.shutemov@linux.intel.com — 2025-06-27
*Subject: Re: [PATCHv2 02/12] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On Thu, Jun 26, 2025 at 11:08:07AM +0000, Huang, Kai wrote:
> On Mon, 2025-06-09 at 22:13 +0300, Kirill A. Shutemov wrote:
> > With Dynamic PAMT, the kernel no longer needs to allocate PAMT_4K on
 
Ack.

---

## [44] Kirill A. Shutemov — 2025-06-27
*Subject: Re: [PATCHv2 03/12] x86/virt/tdx: Allocate reference counters for
 PAMT memory*

On Wed, Jun 25, 2025 at 12:26:09PM -0700, Dave Hansen wrote:
> On 6/9/25 12:13, Kirill A. Shutemov wrote:
> > The PAMT memory holds metadata for TDX-protected memory. With Dynamic

Okay.

> > Tracking PAMT memory usage on the kernel side duplicates what TDX module
> > does.  It is possible to avoid this by lazily allocating PAMT memory on

Will do.

> > --- a/arch/x86/virt/vmx/tdx/tdx.c
> > +++ b/arch/x86/virt/vmx/tdx/tdx.c

Will do.

> >  static enum tdx_module_status_t tdx_module_status;
> >  static DEFINE_MUTEX(tdx_module_lock);

tdx_get_pamt_ref_ptr()?

> > +static int pamt_refcount_populate(pte_t *pte, unsigned long addr, void *data)
> > +{

Ack.

> > +	unsigned long vaddr;
> > +	pte_t entry;

Not optimization.

Calls of apply_to_page_range() can overlap by one page due to
round_up()/round_down() in alloc_pamt_refcount(). We don't need to
populate these pages again if they are already populated.

Will add a comment.

> > +	vaddr = __get_free_page(GFP_KERNEL | __GFP_ZERO);
> > +	if (!vaddr)

I only found such chain in KASAN code.

What about this?

      pte_t entry = ptep_get(pte);
      struct page *page = pte_page(entry);

and use __free_page(page) instead free_page(vaddr)?

The similar thing can be don on allocation side.

> 
> > +	spin_lock(&init_mm.page_table_lock);

On error, we free metadata from the whole range that covers upto max_pfn.
There's no tracking which portion is populated.

> > +		pte_clear(init_mm, addr, pte);
> > +		free_page(vaddr);

Okay.

> > +	return apply_to_page_range(&init_mm, start, end - start,
> > +				   pamt_refcount_populate, NULL);

Yes.

> That seems ... medium to high complexity to me. Is there some reason
> none of it is documented or commented? Like, I think it's not been

I found it understandable when I wrote it, but it is misjudgement on my
part.

Will work on readability and comments.

> > +static int init_pamt_metadata(void)
> > +{

Makes sense.

> But either way, I've hit a wall on this. This is too impenetrable as it
> stands to review further. I'll eagerly await a more approachable v3.

Got it.

---

## [45] kirill.shutemov@linux.intel.com — 2025-06-27
*Subject: Re: [PATCHv2 03/12] x86/virt/tdx: Allocate reference counters for
 PAMT memory*

On Thu, Jun 26, 2025 at 12:53:29AM +0000, Huang, Kai wrote:
> 
> > +static int init_pamt_metadata(void)

Ack.

> 
> > +	 */

It follows vmap_pfn() pattern as usage is similar.

It seems the flag allows vread_iter() to work correct on sparse mappings.

> > +	if (!area)
> > +		return -ENOMEM;

Okay.

---

## [46] Kirill A. Shutemov — 2025-06-27
*Subject: Re: [PATCHv2 04/12] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Wed, Jun 25, 2025 at 01:02:38PM -0700, Dave Hansen wrote:
> On 6/9/25 12:13, Kirill A. Shutemov wrote:
> >  arch/x86/include/asm/tdx.h       |   3 +

Will do.

> I'll give some examples:
> 

tdx_nr_dpamt_pages_per_2m()? This gets ugly.

> The naming is not consistent with something used only for dynamic PAMT
> support. This kind of comment would help, but is not a replacement for

Returning zero for !tdx_supports_dynamic_pamt() helps to avoid branches in
mmu_topup_memory_caches(). This way we pre-allocate zero pages in PAMPT
page cache.

> > +static int tdx_nr_pamt_pages(void)
> > +{

I think tdx_alloc_pamt_pages() has to flag non-empty pamt_pages list.

> It would *work* because the allocation function would just merrily
> shove lots of pages on the list. But when it's consumed you'd run off

Will do.

---

## [47] Kirill A. Shutemov — 2025-06-27
*Subject: Re: [PATCHv2 04/12] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Fri, Jun 27, 2025 at 10:49:34AM +0300, Adrian Hunter wrote:
> On 09/06/2025 22:13, Kirill A. Shutemov wrote:
> > +static void tdx_pamt_put(struct page *page, enum pg_level level)

Good point. I missed that.

---

## [48] kirill.shutemov@linux.intel.com — 2025-06-27
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Wed, Jun 25, 2025 at 10:49:16PM +0000, Edgecombe, Rick P wrote:
> On Mon, 2025-06-09 at 22:13 +0300, Kirill A. Shutemov wrote:
> > This patchset enables Dynamic PAMT in TDX. Please review.

I didn't. Will do.

---

## [49] Dave Hansen — 2025-06-27
*Subject: Re: [PATCHv2 03/12] x86/virt/tdx: Allocate reference counters for
 PAMT memory*

On 6/27/25 04:27, Kirill A. Shutemov wrote:
> On Wed, Jun 25, 2025 at 12:26:09PM -0700, Dave Hansen wrote:
>>> +static atomic_t *tdx_get_pamt_refcount(unsigned long hpa)

How about:

	tdx_find_pamt_refcount()

>>> +	unsigned long vaddr;
>>> +	pte_t entry;

But don't you check it again under the lock?

>>> +	vaddr = __get_free_page(GFP_KERNEL | __GFP_ZERO);
>>> +	if (!vaddr)

Right there ^

>>> +		set_pte_at(&init_mm, addr, pte, entry);
>>> +	else

That does look better.

---

## [50] kirill.shutemov@linux.intel.com — 2025-07-09
*Subject: Re: [PATCHv2 08/12] KVM: TDX: Handle PAMT allocation in fault path*

On Wed, Jun 25, 2025 at 10:38:42PM +0000, Edgecombe, Rick P wrote:
> On Mon, 2025-06-09 at 22:13 +0300, Kirill A. Shutemov wrote:
> > There are two distinct cases when the kernel needs to allocate PAMT

Ack.

> > 
> > Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

We would need to pass actual level when huge pages are supported. It is
better to keep it this way to avoid patching in the future.

> 
> > @@ -1562,10 +1577,16 @@ int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,

We need to deposit PAMT memory for PAGE.ADD at some point. I think having
it consolidated here for both PAGE.ADD and PAGE.AUG is better.

> > +
> > +	if (ret)

I guess we can do something like this (but I am not sure it is better):

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index baa791ea5fd7..58a3066be6fc 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2141,11 +2141,7 @@ static int tdx_alloc_pamt_pages(struct list_head *pamt_pages,
 	for (int i = 0; i < tdx_nr_pamt_pages(); i++) {
 		struct page *page;
 
-		if (alloc)
-			page = alloc(data);
-		else
-			page = alloc_page(GFP_KERNEL);
-
+		page = alloc(data);
 		if (!page) {
 			tdx_free_pamt_pages(pamt_pages);
 			return -ENOMEM;
@@ -2208,6 +2204,11 @@ static int tdx_pamt_add(atomic_t *pamt_refcount, unsigned long hpa,
 	return 0;
 }
 
+static struct page *alloc_kernel_page(void *dummy)
+{
+	return alloc_page(GFP_KERNEL);
+}
+
 /* Bump PAMT refcount for the given page and allocate PAMT memory if needed */
 int tdx_pamt_get(struct page *page, enum pg_level level,
 		 struct page *(alloc)(void *data), void *data)
@@ -2233,6 +2234,9 @@ int tdx_pamt_get(struct page *page, enum pg_level level,
 	if (atomic_inc_not_zero(pamt_refcount))
 		return 0;
 
+	if (!alloc)
+		alloc = alloc_kernel_page;
+
 	if (tdx_alloc_pamt_pages(&pamt_pages, alloc, data))
 		return -ENOMEM;
 
> 
> >  		if (!page)

I am not sure how returning object back to pool helps anything.

Or do you mean to invent a new memory pool mechanism just for PAMT. Seems
excessive.


> Or moving kvm_mmu_memory_cache_alloc() to a static inline in a header
> that core x86 can use.

mmu_memory_cache_alloc_obj() need to be pulled into header too. At this
point we might as well pull all KVM_ARCH_NR_OBJS_PER_MEMORY_CACHE stuff
there. 

It seems too extreme to avoid export.

> They all seem bad in different ways.
>

---

## [51] Edgecombe, Rick P — 2025-07-10
*Subject: Re: [PATCHv2 08/12] KVM: TDX: Handle PAMT allocation in fault path*

On Mon, 2025-06-09 at 22:13 +0300, Kirill A. Shutemov wrote:
>  int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
>  			      enum pg_level level, kvm_pfn_t pfn)

This is unfortunate. In practice, all of the callers will be in a vCPU context,
but __tdp_mmu_set_spte_atomic() can be called for zap's which is why there is no
vCPU.

We don't want to split the tdp mmu calling code to introduce a variant that has
a vCPU. 

What about a big comment? Or checking for NULL and returning -EINVAL like
PG_LEVEL_4K below? I guess in this case a NULL pointer will be plenty loud. So
probably a comment is enough.

Hmm, the only reason we need the vCPU here is to get at the the per-vCPU pamt
page cache. This is also the reason for the strange callback scheme I was
complaining about in the other patch. It kind of seems like there are two
friction points in this series:
1. How to allocate dpamt pages
2. How to serialize the global DPAMT resource inside a read lock

I'd like to try to figure out a better solution for (1). (2) seems good. But I'm
still processing.

>  	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
>  	struct page *page = pfn_to_page(pfn);

---

## [52] Edgecombe, Rick P — 2025-07-10
*Subject: Re: [PATCHv2 07/12] KVM: TDX: Preallocate PAMT pages to be used in
 page fault path*

On Mon, 2025-06-09 at 22:13 +0300, Kirill A. Shutemov wrote:
> diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
> index cbc84c6abc2e..d99bb27b5b01 100644

Shouldn't this be only for TD vCPUs?

---

## [53] kirill.shutemov@linux.intel.com — 2025-07-10
*Subject: Re: [PATCHv2 07/12] KVM: TDX: Preallocate PAMT pages to be used in
 page fault path*

On Thu, Jul 10, 2025 at 01:34:19AM +0000, Edgecombe, Rick P wrote:
> On Mon, 2025-06-09 at 22:13 +0300, Kirill A. Shutemov wrote:
> > diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c

Ah. Good point. I didn't consider legacy VMs on TDX-enabled host.

---

## [54] kirill.shutemov@linux.intel.com — 2025-07-10
*Subject: Re: [PATCHv2 08/12] KVM: TDX: Handle PAMT allocation in fault path*

On Thu, Jul 10, 2025 at 01:33:41AM +0000, Edgecombe, Rick P wrote:
> On Mon, 2025-06-09 at 22:13 +0300, Kirill A. Shutemov wrote:
> > �int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,

IIUC, __tdp_mmu_set_spte_atomic() to zap, only for shared case which is
!is_mirror_sptep() and will not get us here. !shared case get to
tdx_sept_remove_private_spte().

> We don't want to split the tdp mmu calling code to introduce a variant that has
> a vCPU.�

Yes, comment is helpful here

> Hmm, the only reason we need the vCPU here is to get at the the per-vCPU pamt
> page cache. This is also the reason for the strange callback scheme I was

I tried few different approached to address the problem. See phys_prepare
and phys_cleanup in v1.

> 
> > �	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);

---

## [55] Edgecombe, Rick P — 2025-07-30
*Subject: Re: [PATCHv2 01/12] x86/tdx: Consolidate TDX error handling*

On Thu, 2025-06-26 at 09:59 -0700, Dave Hansen wrote:
> On 6/26/25 08:51, Sean Christopherson wrote:
> > No, I was thinking:

Hi,

Picking this up from Kirill. At a high level Dave seems to want to encapsulate
the TDX error code stuff more, and Sean wants something more lightweight. This
seems to be partly a style difference between arch/x86 and KVM, but also a
tension between how much TDX interface to wrap (i.e. the SEAMCALL wrapper
layer).

But at a code level, the helpers have basically identical logic. The difference
between IS_TDX_ERR_OPERAND_BUSY() and tdx_operand_busy() seems more about
whether they look more raw. Since KVM side has many more users of error code
parsing, I'll lean towards Sean's preference of the all caps macro-like
signature. Since Dave points out IS_ERR() operates on pointers, I'll go with
something else. TDX docs call these "Completion Status Codes", so maybe:
STATUS_OPERAND_BUSY()?

As far as leaking TDX bits out of the SEAMCALL wrappers. I did consider trying
to convert the error codes into errno codes at the wrapper level, which arch/x86
side already does internally. I think we could mostly do that for the wrappers
that KVM uses, but there would be few cases (VCPU_NOT_ASSOCIATED) where you
would have to look at the code to see which errno matches to which TDX concept.

The other problem with translating it to errno would be that we print out the
TDX error codes in a lot of warning cases (KVM_BUG_ON(), etc). We already went
through this somewhat with the TDX extended error codes. The bits of the normal
error code could be very useful for debugging too, and only the KVM callers
knows whether to print them out or not. So we would need to return the TDX
format error code anyway, and at that point the TDX->errno conversion would seem
like superfluous complexity.

So STATUS_OPERAND_BUSY() seems like an ok thing to try next for v3 of this
series at least. Unless anyone has any strong objections ahead of time.

Thanks,

Rick

---

## [56] Edgecombe, Rick P — 2025-07-30
*Subject: Re: [PATCHv2 01/12] x86/tdx: Consolidate TDX error handling*

On Thu, 2025-06-26 at 00:05 +0000, Huang, Kai wrote:
> But as you suggested, I think it's better to split this patch into two:
> 

Agree, this patch tries to do too much.

---

## [57] Edgecombe, Rick P — 2025-07-31
*Subject: Re: [PATCHv2 02/12] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On Wed, 2025-06-25 at 11:06 -0700, Dave Hansen wrote:
> This is the wrong place to do this.
> 

I'm finding this tdmr_get_pamt_sz() maybe too strange to build on top of. 
It iterates through these special TDX page sizes once, and calls into 
tdmr_get_pamt_sz() for each, which in turn has a case statement for each 
index. So the loop doesn't add much - each index still has its own line 
of code inside tdmr_get_pamt_sz(). And then despite prepping the base/size 
in an array via the loop, it has to be packed manually at the end for each 
index. So I'm not sure if the general wisdom of doing things in a single way 
is really adding much here.

I'm wondering if something like the below might be a better base to build 
on. For dpamt the "tdmr->pamt_4k_size =" line could just branch on 
tdx_supports_dynamic_pamt(). Any thoughts on it as an alternative to the 
suggestion to add the dpamt logic to tdmr_get_pamt_sz()?

 arch/x86/virt/vmx/tdx/tdx.c | 69 ++++++++++++++++++---------------------------------------------------
 1 file changed, 18 insertions(+), 51 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index c7a9a087ccaf..8de6fa3e5773 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -445,30 +445,16 @@ static int fill_out_tdmrs(struct list_head *tmb_list,
  * PAMT size is always aligned up to 4K page boundary.
  */
 static unsigned long tdmr_get_pamt_sz(struct tdmr_info *tdmr, int pgsz,
-                                     u16 pamt_entry_size)
+                                     u16 pamt_entry_size[])
 {
        unsigned long pamt_sz, nr_pamt_entries;
+       const int tdx_pg_size_shift[] = { PAGE_SHIFT, PMD_SHIFT, PUD_SHIFT };
 
-       switch (pgsz) {
-       case TDX_PS_4K:
-               nr_pamt_entries = tdmr->size >> PAGE_SHIFT;
-               break;
-       case TDX_PS_2M:
-               nr_pamt_entries = tdmr->size >> PMD_SHIFT;
-               break;
-       case TDX_PS_1G:
-               nr_pamt_entries = tdmr->size >> PUD_SHIFT;
-               break;
-       default:
-               WARN_ON_ONCE(1);
-               return 0;
-       }
+       nr_pamt_entries = tdmr->size >> tdx_pg_size_shift[pgsz];
+       pamt_sz = nr_pamt_entries * pamt_entry_size[pgsz];
 
-       pamt_sz = nr_pamt_entries * pamt_entry_size;
        /* TDX requires PAMT size must be 4K aligned */
-       pamt_sz = ALIGN(pamt_sz, PAGE_SIZE);
-
-       return pamt_sz;
+       return PAGE_ALIGN(pamt_sz);
 }
 
 /*
@@ -509,25 +495,19 @@ static int tdmr_set_up_pamt(struct tdmr_info *tdmr,
                            struct list_head *tmb_list,
                            u16 pamt_entry_size[])
 {
-       unsigned long pamt_base[TDX_PS_NR];
-       unsigned long pamt_size[TDX_PS_NR];
-       unsigned long tdmr_pamt_base;
        unsigned long tdmr_pamt_size;
        struct page *pamt;
-       int pgsz, nid;
-
+       int nid;
        nid = tdmr_get_nid(tdmr, tmb_list);
 
        /*
         * Calculate the PAMT size for each TDX supported page size
         * and the total PAMT size.
         */
-       tdmr_pamt_size = 0;
-       for (pgsz = TDX_PS_4K; pgsz < TDX_PS_NR; pgsz++) {
-               pamt_size[pgsz] = tdmr_get_pamt_sz(tdmr, pgsz,
-                                       pamt_entry_size[pgsz]);
-               tdmr_pamt_size += pamt_size[pgsz];
-       }
+       tdmr->pamt_4k_size = tdmr_get_pamt_sz(tdmr, TDX_PS_4K, pamt_entry_size);
+       tdmr->pamt_2m_size = tdmr_get_pamt_sz(tdmr, TDX_PS_2M, pamt_entry_size);
+       tdmr->pamt_1g_size = tdmr_get_pamt_sz(tdmr, TDX_PS_1G, pamt_entry_size);
+       tdmr_pamt_size = tdmr->pamt_4k_size + tdmr->pamt_2m_size + tdmr->pamt_1g_size;
 
        /*
         * Allocate one chunk of physically contiguous memory for all
@@ -535,26 +515,16 @@ static int tdmr_set_up_pamt(struct tdmr_info *tdmr,
         * in overlapped TDMRs.
         */
        pamt = alloc_contig_pages(tdmr_pamt_size >> PAGE_SHIFT, GFP_KERNEL,
-                       nid, &node_online_map);
-       if (!pamt)
+                                 nid, &node_online_map);
+       if (!pamt) {
+               /* Zero base so that the error path will skip freeing. */
+               tdmr->pamt_4k_base = 0;
                return -ENOMEM;
-
-       /*
-        * Break the contiguous allocation back up into the
-        * individual PAMTs for each page size.
-        */
-       tdmr_pamt_base = page_to_pfn(pamt) << PAGE_SHIFT;
-       for (pgsz = TDX_PS_4K; pgsz < TDX_PS_NR; pgsz++) {
-               pamt_base[pgsz] = tdmr_pamt_base;
-               tdmr_pamt_base += pamt_size[pgsz];
        }
 
-       tdmr->pamt_4k_base = pamt_base[TDX_PS_4K];
-       tdmr->pamt_4k_size = pamt_size[TDX_PS_4K];
-       tdmr->pamt_2m_base = pamt_base[TDX_PS_2M];
-       tdmr->pamt_2m_size = pamt_size[TDX_PS_2M];
-       tdmr->pamt_1g_base = pamt_base[TDX_PS_1G];
-       tdmr->pamt_1g_size = pamt_size[TDX_PS_1G];
+       tdmr->pamt_4k_base = page_to_phys(pamt);
+       tdmr->pamt_2m_base = tdmr->pamt_4k_base + tdmr->pamt_4k_size;
+       tdmr->pamt_1g_base = tdmr->pamt_2m_base + tdmr->pamt_2m_size;
 
        return 0;
 }
@@ -585,10 +555,7 @@ static void tdmr_do_pamt_func(struct tdmr_info *tdmr,
        tdmr_get_pamt(tdmr, &pamt_base, &pamt_size);
 
        /* Do nothing if PAMT hasn't been allocated for this TDMR */
-       if (!pamt_size)
-               return;
-
-       if (WARN_ON_ONCE(!pamt_base))
+       if (!pamt_base)
                return;
 
        pamt_func(pamt_base, pamt_size);

---

## [58] Huang, Kai — 2025-07-31
*Subject: Re: [PATCHv2 02/12] x86/virt/tdx: Allocate page bitmap for Dynamic
 PAMT*

On Thu, 2025-07-31 at 01:06 +0000, Edgecombe, Rick P wrote:
> On Wed, 2025-06-25 at 11:06 -0700, Dave Hansen wrote:
> > This is the wrong place to do this.

The code change LGTM, albeit I am not sure whether it is definitely
better.

For where to add dynamic PAMT logic, I think it's reasonable to put such
logic into tdmr_get_pamt_sz() because it changes the amount of memory that
we need to allocate for 4K page size.  If we do dynamic PAMT logic at
higher level, the code logic in tdmr_get_pamt_sz() to calculate PAMT size
for 4K page will not be accurate, i.e., it is only correct w/o dynamic
PAMT.

---

## [59] Sean Christopherson — 2025-07-31
*Subject: Re: [PATCHv2 01/12] x86/tdx: Consolidate TDX error handling*

On Wed, Jul 30, 2025, Rick P Edgecombe wrote:
> So STATUS_OPERAND_BUSY() seems like an ok thing to try next for v3 of this
> series at least. Unless anyone has any strong objections ahead of time.

Can you make it IS_TDX_STATUS_OPERAND_BUSY() so that it's obviously a check and
not a statement/value, and to scope it to TDX?

---

## [60] Edgecombe, Rick P — 2025-07-31
*Subject: Re: [PATCHv2 01/12] x86/tdx: Consolidate TDX error handling*

On Thu, 2025-07-31 at 16:31 -0700, Sean Christopherson wrote:
> On Wed, Jul 30, 2025, Rick P Edgecombe wrote:
> > So STATUS_OPERAND_BUSY() seems like an ok thing to try next for v3 of this

It's a mouthful, but I can live with it. Yea, it def should have TDX in the name.

---

## [61] Sean Christopherson — 2025-07-31
*Subject: Re: [PATCHv2 01/12] x86/tdx: Consolidate TDX error handling*

On Thu, Jul 31, 2025, Rick P Edgecombe wrote:
> On Thu, 2025-07-31 at 16:31 -0700, Sean Christopherson wrote:
> > On Wed, Jul 30, 2025, Rick P Edgecombe wrote:

IS_TDX_STATUS_OP_BUSY?

---

## [62] Edgecombe, Rick P — 2025-08-01
*Subject: Re: [PATCHv2 01/12] x86/tdx: Consolidate TDX error handling*

On Thu, 2025-07-31 at 16:53 -0700, Sean Christopherson wrote:
> On Thu, Jul 31, 2025, Rick P Edgecombe wrote:
> > On Thu, 2025-07-31 at 16:31 -0700, Sean Christopherson wrote:

Ehh, would nicer to have it closer to what is in the TDX docs. The worst would be to read
TDX_STATUS_OP_BUSY, then have to look at the value to figure out which error code it actually was.

Maybe just drop STATUS and have IS_TDX_OPERAND_BUSY()? It still loses the ERR part, which made it look
like IS_ERR().

---

## [63] Sean Christopherson — 2025-08-06
*Subject: Re: [PATCHv2 01/12] x86/tdx: Consolidate TDX error handling*

On Fri, Aug 01, 2025, Rick P Edgecombe wrote:
> On Thu, 2025-07-31 at 16:53 -0700, Sean Christopherson wrote:
> > On Thu, Jul 31, 2025, Rick P Edgecombe wrote:

Any of the IS_TDX_xxx options work for me.

---

## [64] Edgecombe, Rick P — 2025-08-08
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Mon, 2025-06-09 at 22:13 +0300, Kirill A. Shutemov wrote:
> Dynamic PAMT enabling in kernel
> ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

On closer inspection this new solution also has global locking. It
opportunistically checks to see if there is already a refcount, but otherwise
when a PAMT page actually has to be added there is a global spinlock while the
PAMT add/remove SEAMCALL is made. I guess this is going to get taken somewhere
around once per 512 4k private pages, but when it does it has some less ideal
properties:
 - Cache line bouncing of the lock between all TDs on the host
 - An global exclusive lock deep inside the TDP MMU shared lock fault path
 - Contend heavily when two TD's shutting down at the same time?

As for why not only do the lock as a backup option like the kick+lock solution
in KVM, the problem would be losing the refcount race and ending up with a PAMT
page getting released early.

As far as TDX module locking is concerned (i.e. BUSY error codes from pamt
add/remove), it seems this would only happen if pamt add/remove operate
simultaneously on the same 2MB HPA region. That is completely prevented by the
refcount and global lock, but it's a bit heavyweight. It prevents simultaneously
adding totally separate 2MB regions when we only would need to prevent
simultaneously operating on the same 2MB region.

I don't see any other reason for the global spin lock, Kirill was that it? Did
you consider also adding a lock per 2MB region, like the refcount? Or any other
granularity of lock besides global? Not saying global is definitely the wrong
choice, but seems arbitrary if I got the above right.

---

## [65] kas@kernel.org — 2025-08-11
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Fri, Aug 08, 2025 at 11:18:40PM +0000, Edgecombe, Rick P wrote:
> On Mon, 2025-06-09 at 22:13 +0300, Kirill A. Shutemov wrote:
> > Dynamic PAMT enabling in kernel

We have discussed this before[1]. Global locking is problematic when you
actually hit contention. Let's not complicate things until we actually
see it. I failed to demonstrate contention without huge pages. With huge
pages it is even more dubious that we ever see it.

[1] https://lore.kernel.org/all/4bb2119a-ff6d-42b6-acf4-86d87b0e9939@intel.com/

---

## [66] Edgecombe, Rick P — 2025-08-11
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Mon, 2025-08-11 at 07:31 +0100, kas@kernel.org wrote:
> > I don't see any other reason for the global spin lock, Kirill was that it?
> > Did

Ah, I see.

I just did a test of simultaneously starting 10 VMs with 16GB of ram (non huge
pages) and then shutting them down. I saw 701 contentions on startup, and 53
more on shutdown. Total wait time 2ms. Not horrible but not theoretical either.
But it probably wasn't much of a cacheline bouncing worse case. And I guess this
is on my latest changes not this exact v2, but it shouldn't have changed.

But hmm, it seems Dave's objection about maintaining the lock allocations would
apply to the refcounts too? But the hotplug concerns shouldn't actually be an
issue for TDX because they gets rejected if the allocations are not already
there. So complexity of a per-2MB lock should be minimal, at least
incrementally. The difference seems more about memory use vs performance.

What gives me pause is in the KVM TDX work we have really tried hard to not take
exclusive locks in the shared MMU lock path. Admittedly that wasn't backed by
hard numbers. But an enormous amount of work went into lettings KVM faults
happen under the shared lock for normal VMs. So on one hand, yes it's premature
optimization. But on the other hand, it's a maintainability concern about
polluting the existing way things work in KVM with special TDX properties.

I think we need to at least call out loudly that the decision was to go with the
simplest possible solution, and the impact to KVM. I'm not sure what Sean's
opinion is, but I wouldn't want him to first learn of it when he went digging
and found a buried global spin lock in the fault path.

---

## [67] Sean Christopherson — 2025-08-11
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Mon, Aug 11, 2025, Rick P Edgecombe wrote:
> On Mon, 2025-08-11 at 07:31 +0100, kas@kernel.org wrote:
> > > I don't see any other reason for the global spin lock, Kirill was that

How many vCPUs?  And were the VMs actually accepting/faulting all 16GiB?

There's also a noisy neighbor problem lurking.  E.g. malicious/buggy VM spams
private<=>shared conversions and thus interferes with PAMT allocations for other
VMs.

> pages) and then shutting them down. I saw 701 contentions on startup, and 53
> more on shutdown. Total wait time 2ms. Not horrible but not theoretical either.

Isn't the SEAMCALL done while holding the spinlock?  I assume the latency of the
SEAMCALL is easily the long pole in the flow.

> And I guess this is on my latest changes not this exact v2, but it shouldn't
> have changed.

Maybe not for TDX, but we have lots and lots of hard numbers for why taking mmu_lock
for write is problematic.  Even if TDX VMs don't exhibit the same patterns *today*
as "normal" VMs, i.e. don't suffer the same performance blips, nothing guarantees
that will always hold true.
 
> But an enormous amount of work went into lettings KVM faults happen under the
> shared lock for normal VMs. So on one hand, yes it's premature optimization.

Heh, too late, I saw it when this was first posted.  And to be honest, my initial
reaction was very much "absolutely not" (though Rated R, not PG).  Now that I've
had time to think things through, I'm not _totally_ opposed to having a spinlock
in the page fault path, but my overall sentiment remains the same.

For mmu_lock and related SPTE operations, I was super adamant about not taking
exclusive locks because based on our experience with the TDP MMU, converting flows
from exclusive to shared is usually significantly more work than developing code
for "shared mode" straightaway (and you note above, that wasn't trivial for TDX).
And importantly, those code paths were largely solved problems.  I.e. I didn't
want to get into a situation where TDX undid the parallelization of the TDP MMU,
and then had to add it back after the fact.

I think the same holds true here.  I'm not completely opposed to introducing a
spinlock, but I want to either have a very high level of confidence that the lock
won't introduce jitter/delay (I have low confidence on this front, at least in
the proposed patches), or have super clear line of sight to making the contention
irrelevant, without having to rip apart the code.

My biggest question at this point is: why is all of this being done on-demand?
IIUC, we swung from "allocate all PAMT_4K pages upfront" to "allocate all PAMT_4K
pages at the last possible moment".  Neither of those seems ideal.

E.g. for things like TDCS pages and to some extent non-leaf S-EPT pages, on-demand
PAMT management seems reasonable.  But for PAMTs that are used to track guest-assigned
memory, which is the vaaast majority of PAMT memory, why not hook guest_memfd?
I.e. setup PAMT crud when guest_memfd is populated, not when the memory is mapped
into the guest.  That way setups that cares about guest boot time can preallocate
guest_memfd in order to get the PAMT stuff out of the way.

You could do the same thing by prefaulting guest memory, but TDX has limitations
there, and I see very little value in precisely reclaiming PAMT memory when a
leaf S-EPT is zapped, i.e. when a page is converted from private=>shared.  As
above, that's just asking for noisy neighbor issues.

The complaints with static PAMT are that it required burning 0.4% of memory even
if the host isn't actively running TDX VMs.  Burning 0.4% of the memory assigned
to a guest, regardless of whether it's map private or shared, seems acceptable,
and I think would give us a lot more flexibility in avoiding locking issues.

Similarly, we could bind a PAMT to non-leaf S-EPT pages during mmu_topup_memory_caches(),
i.e. when arch.mmu_external_spt_cache is filled.  Then there would be no need for
a separate vcpu->arch.pamt_page_cache, and more work would be done outside of
mmu_lock.  Freeing SPTs would still be done under mmu_lock (I think), but that
should be a much rarer operation.

---

## [68] Vishal Annapurve — 2025-08-11
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Mon, Aug 11, 2025 at 7:02 PM Sean Christopherson <seanjc@google.com> wrote:
>
> On Mon, Aug 11, 2025, Rick P Edgecombe wrote:

This seems fine for 4K page backing. But when TDX VMs have huge page
backing, the vast majority of private memory memory wouldn't need PAMT
allocation for 4K granularity.

IIUC guest_memfd allocation happening at 2M granularity doesn't
necessarily translate to 2M mapping in guest EPT entries. If the DPAMT
support is to be properly utilized for huge page backings, there is a
value in not attaching PAMT allocation with guest_memfd allocation.

> I.e. setup PAMT crud when guest_memfd is populated, not when the memory is mapped
> into the guest.  That way setups that cares about guest boot time can preallocate

---

## [69] kas@kernel.org — 2025-08-12
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Mon, Aug 11, 2025 at 07:02:10PM -0700, Sean Christopherson wrote:
> On Mon, Aug 11, 2025, Rick P Edgecombe wrote:
> > On Mon, 2025-08-11 at 07:31 +0100, kas@kernel.org wrote:

I don't see jump to per-2MB locking remotely justified. We can scale
number of locks gradually with the amount of memory in the system: have
a power-of-2 set of locks and 2MB range to the lock with %.

Note that it is trivial thing to add later on and doesn't need to be
part of initial design.

> > What gives me pause is in the KVM TDX work we have really tried hard to not take
> > exclusive locks in the shared MMU lock path. Admittedly that wasn't backed by

I think there is a big difference with mmu_lock.

mmu_lock is analogous to mmap_lock in core-mm. It serializes page fault
against other mmu operation and have inherently vast scope.

pamt_lock on other hand is at very bottom of callchain and with very
limited scope. It is trivially scalable by partitioning.

Translating problems you see with mmu_lock onto pamt_lock seems like an
overreaction.

---

## [70] kas@kernel.org — 2025-08-12
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Mon, Aug 11, 2025 at 07:31:26PM -0700, Vishal Annapurve wrote:
> On Mon, Aug 11, 2025 at 7:02 PM Sean Christopherson <seanjc@google.com> wrote:
> >

Right.

It also requires special handling in many places in core-mm. Like, what
happens if THP in guest memfd got split. Who would allocate PAMT for it?
Migration will be more complicated too (when we get there).

---

## [71] Edgecombe, Rick P — 2025-08-12
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Tue, 2025-08-12 at 09:04 +0100, kas@kernel.org wrote:
> > > E.g. for things like TDCS pages and to some extent non-leaf S-EPT pages,
> > > on-demand

I actually went down this path too, but the problem I hit was that TDX module
wants the PAMT page size to match the S-EPT page size. And the S-EPT size will
depend on runtime behavior of the guest. I'm not sure why TDX module requires
this though. Kirill, I'd be curious to understand the constraint more if you
recall.

But in any case, it seems there are multiple reasons.

---

## [72] Sean Christopherson — 2025-08-12
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Tue, Aug 12, 2025, Rick P Edgecombe wrote:
> On Tue, 2025-08-12 at 09:04 +0100, kas@kernel.org wrote:
> > > > E.g. for things like TDCS pages and to some extent non-leaf S-EPT

I don't disagree, but the host needs to plan for the worst, especially since the
guest can effectively dictate the max page size of S-EPT mappings.  AFAIK, there
are no plans to support memory overcommit for TDX guests, so unless a deployment
wants to roll the dice and hope TDX guests will use hugepages for N% of their
memory, the host will want to reserve 0.4% of guest memory for PAMTs to ensure
it doesn't unintentionally DoS the guest with an OOM condition.

Ditto for any use case that wants to support dirty logging (ugh), because dirty
logging will require demoting all of guest memory to 4KiB mappings.

> > Right.
> > 

guest_memfd?  I don't see why core-mm would need to get involved.  And I definitely
don't see how handling page splits in guest_memfd would be more complicated than
handling them in KVM's MMU.

> > Migration will be more complicated too (when we get there).

Which type of migration?  Live migration or page migration?

> I actually went down this path too, but the problem I hit was that TDX module
> wants the PAMT page size to match the S-EPT page size. 

Right, but over-populating the PAMT would just result in "wasted" memory, correct?
I.e. KVM can always provide more PAMT entries than are needed.  Or am I
misunderstanding how dynamic PAMT works?

In other words, IMO, reclaiming PAMT pages on-demand is also a premature optimization
of sorts, as it's not obvious to me that the host would actually be able to take
advantage of the unused memory.

> And the S-EPT size will depend on runtime behavior of the guest. I'm not sure
> why TDX module requires this though. Kirill, I'd be curious to understand the

---

## [73] Edgecombe, Rick P — 2025-08-12
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Tue, 2025-08-12 at 09:15 -0700, Sean Christopherson wrote:
> > I actually went down this path too, but the problem I hit was that TDX
> > module wants the PAMT page size to match the S-EPT page size. 

Demote needs DPAMT pages in order to split the DPAMT. But "needs" is what I was
hoping to understand better.

I do think though, that we should consider premature optimization vs re-
architecting DPAMT only for the sake of a short term KVM design. As in, if fault
path managed DPAMT is better for the whole lazy accept way of things, it
probably makes more sense to just do it upfront with the existing architecture.

BTW, I think I untangled the fault path DPAMT page allocation code in this
series. I basically moved the existing external page cache allocation to
kvm/vmx/tdx.c. So the details of the top up and external page table cache
happens outside of x86 mmu code. The top up structure comes from arch/x86 side
of tdx code, so the cache can just be passed into tdx_pamt_get(). And from the
MMU code's perspective there is just one type "external page tables". It doesn't
know about DPAMT at all.

So if that ends up acceptable, I think the main problem left is just this global
lock. And it seems we have a simple solution for it if needed.

> 
> In other words, IMO, reclaiming PAMT pages on-demand is also a premature

I was imagining some guestmemfd callback to setup DPAMT backing for all the
private memory. Just leave it when it's shared for simplicity. Then cleanup
DPAMT when the pages are freed from guestmemfd. The control pages could have
their own path like it does in this series. But it doesn't seem supported.

---

## [74] Vishal Annapurve — 2025-08-12
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Tue, Aug 12, 2025 at 9:15 AM Sean Christopherson <seanjc@google.com> wrote:
>
> On Tue, Aug 12, 2025, Rick P Edgecombe wrote:

Reasonable guest VMs (e.g. Linux) will generally map things mostly at
hugepage granularity, I don't think there is a reason here to be more
conservative and just increase the cost for the well behaved guests.
That being said, The scenario of an unreasonable guest could be
covered in future by modifying how PAMT allocation is
accounted/charged.

Guests are generally free to use the lazy pvalidate/accept features so
the host can't guarantee the needed PAMT memory to be always there
anyways.

---

## [75] Vishal Annapurve — 2025-08-12
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

> On Tue, Aug 12, 2025 at 11:39 AM Edgecombe, Rick P <rick.p.edgecombe@intel.com> wrote:
>

IMO, tieing lifetime of guest_memfd folios with that of KVM ownership
beyond the memslot lifetime is leaking more state into guest_memfd
than needed. e.g. This will prevent usecases where guest_memfd needs
to be reused while handling reboot of a confidential VM [1].

IMO, if avoidable, its better to not have DPAMT or generally other KVM
arch specific state tracking hooked up to guest memfd folios specially
with hugepage support and whole folio splitting/merging that needs to
be done. If you still need it, guest_memfd should be stateless as much
as possible just like we are pushing for SNP preparation tracking [2]
to happen within KVM SNP and IMO any such tracking should ideally be
cleaned up on memslot unbinding.

[1] https://lore.kernel.org/kvm/CAGtprH9NbCPSwZrQAUzFw=4rZPA60QBM2G8opYo9CZxRiYihzg@mail.gmail.com/
[2] https://lore.kernel.org/kvm/20250613005400.3694904-2-michael.roth@amd.com/

---

## [76] Edgecombe, Rick P — 2025-08-12
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Tue, 2025-08-12 at 15:00 -0700, Vishal Annapurve wrote:
> IMO, tieing lifetime of guest_memfd folios with that of KVM ownership
> beyond the memslot lifetime is leaking more state into guest_memfd

How does it prevent this? If you really want to re-use guest memory in a fast
way then I think you would want the DPAMT to remain in place actually. It sounds
like an argument to trigger the add/remove from guestmemfd actually.

But I really question with all the work to rebuild S-EPT, and if you propose
DPAMT too, how much work is really gained by not needing to reallocate hugetlbfs
pages. Do you see how it could be surprising? I'm currently assuming there is
some missing context.

> 
> IMO, if avoidable, its better to not have DPAMT or generally other KVM

I'm not sure gmemfd would need to track state. It could be a callback. But it
may be academic anyway. Below...

> 
> [1] https://lore.kernel.org/kvm/CAGtprH9NbCPSwZrQAUzFw=4rZPA60QBM2G8opYo9CZxRiYihzg@mail.gmail.com/

Looking into that more, from the code it seems it's not quite so
straightforward. Demote will always require new DPAMT pages to be passed, and
promote will always remove the 4k DPAMT entries and pass them back to the host.
But on early reading, 2MB PAGE.AUG looks like it can handle the DPAMT being
mapped at 4k. So maybe there is some wiggle room there? But before I dig
further, I think I've heard 4 possible arguments for keeping the existing
design:

1. TDX module may require or at least push the caller to have S-EPT match DPAMT
size (confirmation TBD)
2. Mapping DPAMT all at 4k requires extra memory for TD huge pages
3. It *may* slow TD boots because things can't be lazily installed via the fault
path. (testing not done)
4. While the global lock is bad, there is an easy fix for that if it is needed.

It seems Vishal cares a lot about (2). So I'm wondering if we need to keep going
down this path.

In the meantime, I'm going to try to get some better data on the global lock
contention (Sean's question about how much of the memory was actually faulted
in).

---

## [77] Vishal Annapurve — 2025-08-12
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Tue, Aug 12, 2025 at 4:35 PM Edgecombe, Rick P
<rick.p.edgecombe@intel.com> wrote:
>
> On Tue, 2025-08-12 at 15:00 -0700, Vishal Annapurve wrote:

With the reboot usecase, a new VM may start with it's own new HKID so
I don't think we can preserve any state that's specific to the
previous instance. We can only reduce the amount of state to be
maintained in SEPTs/DPAMTs by using hugepages wherever possible.

>
> But I really question with all the work to rebuild S-EPT, and if you propose

I would not limit the reboot usecase to just hugepage backing
scenario. guest_memfd folios (and ideally the guest_memfd files
themselves) simply should be reusable outside the VM lifecycle
irrespective of whether it's used to back CoCo VMs or not.

---

## [78] Edgecombe, Rick P — 2025-08-13
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Tue, 2025-08-12 at 17:18 -0700, Vishal Annapurve wrote:
> On Tue, Aug 12, 2025 at 4:35 PM Edgecombe, Rick P
> <rick.p.edgecombe@intel.com> wrote:

This is saying that the S-EPT can't be preserved, which doesn't really help me
understand why page allocations are such a big source of the work. I guess you
are saying it's the only thing possible to do?

Hmm, I'm not sure why the S-EPT couldn't be preserved, especially when you allow
for changes to KVM or the TDX module.

But if we are trying to solve the problem of making TD reboot faster, let's
figure out the biggest things that are making it slow first and work on that.
Like it's missing a lot of context on why this turned out to be the right
optimization to do.

Disclaimer: This optimization may be great for other types of VMs and that is
all well and good, but the points are about TDX here and the justification of
the TD reboot optimization is relevant to how we implement DPAMT.

> 
> > 

Still surprised that host page allocations turned out to be the biggest thing
sticking out.

---

## [79] Kiryl Shutsemau — 2025-08-13
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Tue, Aug 12, 2025 at 03:12:52PM +0000, Edgecombe, Rick P wrote:
> On Tue, 2025-08-12 at 09:04 +0100, kas@kernel.org wrote:
> > > > E.g. for things like TDCS pages and to some extent non-leaf S-EPT pages,

With DPAMT, when you pass page pair to PAMT.ADD they will be stored in the
PAMT_2M entry. So PAMT_2M entry cannot be used as a leaf entry anymore.

In theory, TDX module could stash them somewhere else, like generic memory
pool to be used for PAMT_4K when needed. But it is significantly different
design to what we have now with different set of problems.

---

## [80] Kiryl Shutsemau — 2025-08-13
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Tue, Aug 12, 2025 at 09:15:16AM -0700, Sean Christopherson wrote:
> On Tue, Aug 12, 2025, Rick P Edgecombe wrote:
> > On Tue, 2025-08-12 at 09:04 +0100, kas@kernel.org wrote:

Page migration.

But I think after some reading, it can be manageable.

---

## [81] Edgecombe, Rick P — 2025-08-13
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Mon, 2025-08-11 at 19:02 -0700, Sean Christopherson wrote:
> > I just did a test of simultaneously starting 10 VMs with 16GB of ram (non
> > huge

4 vCPUs.

I redid the test. Boot 10 TDs with 16GB of ram, run userspace to fault in memory
from 4 threads until OOM, then shutdown. TDs were split between two sockets. It
ended up with 1136 contentions of the global lock, 4ms waiting.

It still feels very wrong, but also not something that is a very measurable in
the real world. Like Kirill was saying, the global lock is not held very long.
I'm not sure if this may still hit scalability issues from cacheline bouncing on
bigger multisocket systems. But we do have a path forwards if we hit this.
Depending on the scale of the problem that comes up we could decide whether to
do the lock per-2MB region with more memory usage, or a hashed table of N locks
like Dave suggested.

So I'll plan to keep the existing single lock for now unless anyone has any
strong objections.

> 
> There's also a noisy neighbor problem lurking.  E.g. malicious/buggy VM spams

Hmm, as long as it doesn't block it completely, it seems ok?

---

## [82] Dave Hansen — 2025-08-13
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On 8/13/25 15:43, Edgecombe, Rick P wrote:
> I redid the test. Boot 10 TDs with 16GB of ram, run userspace to fault in memory
> from 4 threads until OOM, then shutdown. TDs were split between two sockets. It

4ms out of how much CPU time?

Also, contention is *NOT* necessarily bad here. Only _false_ contention.

The whole point of the lock is to ensure that there aren't two different
CPUs trying to do two different things to the same PAMT range at the
same time.

If there are, one of them *HAS* to wait. It can wait lots of different
ways, but it has to wait. That wait will show up as spinlock contention.

Even if the global lock went away, that 4ms of spinning might still be
there.

---

## [83] Edgecombe, Rick P — 2025-08-14
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Wed, 2025-08-13 at 16:31 -0700, Dave Hansen wrote:
> On 8/13/25 15:43, Edgecombe, Rick P wrote:
> > I redid the test. Boot 10 TDs with 16GB of ram, run userspace to fault in memory

The whole test took about 60s wall time (minus the time of some manual steps).
I'll have to automate it a bit more. But 4ms seemed safely in the "small"
category.

> 
> Also, contention is *NOT* necessarily bad here. Only _false_ contention.

I assumed it was mostly real contention because the the refcount check outside
the lock should prevent the majority of "two threads operating on the same 2MB
region" collisions. The code is roughly:

1:
   if (atomic_inc_not_zero(2mb_pamt_refcount))
	return <it's mapped>;
2:
   <global lock>
   if (atomic_read(2mb_pamt_refcount) != 0) {
3:
	atomic_inc(2mb_pamt_refcount);
	<global unlock>
	return <it's mapped>;
   }
   <seamcall>
   <global unlock>
4:

(similar pattern on the unmapping)

So it will only be valid contention if two threads try to fault in the *same* 2MB
DPAMT region *and* lose that race around 1-3, but invalid contention if threads try
to execute 2-4 at the same time for any different 2MB regions.

Let me go verify.

---

## [84] Kiryl Shutsemau — 2025-08-14
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Thu, Aug 14, 2025 at 12:14:40AM +0000, Edgecombe, Rick P wrote:
> On Wed, 2025-08-13 at 16:31 -0700, Dave Hansen wrote:
> > On 8/13/25 15:43, Edgecombe, Rick P wrote:

Note that in absence of the global lock here, concurrent PAMT.ADD would
also trigger some cache bouncing during pamt_walk() on taking shared
lock on 1G PAMT entry and exclusive lock on 2M entries in the same
cache (4 PAMT_2M entries per cache line). This is hidden by the global
lock.

You would not recover full contention time by removing the global lock.

---

## [85] Edgecombe, Rick P — 2025-08-15
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Thu, 2025-08-14 at 11:55 +0100, Kiryl Shutsemau wrote:
> > > > (similar pattern on the unmapping)
> > > > 

It lost the race only once over a couple runs. So it seems mostly invalid
contention.

> > 
> > Note that in absence of the global lock here, concurrent PAMT.ADD would

Hmm, yea. Another consideration is that performance sensitive users will
probably be using huge pages, in which case 4k PAMT will be mostly skipped.

But man, the number and complexity of the locks is getting a bit high across the
whole stack. I don't have any easy ideas.

---

## [86] Sean Christopherson — 2025-08-20
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Fri, Aug 15, 2025, Rick P Edgecombe wrote:
> On Thu, 2025-08-14 at 11:55 +0100, Kiryl Shutsemau wrote:
> > > > > (similar pattern on the unmapping)

FWIW, I'm not concerned about bouncing cachelines, I'm concerned about the cost
of the SEAMCALLs.  The latency due to bouncing a cache line due to "false"
contention is probably in the noise compared to waiting thousands of cycles for
other SEAMCALLs to complete.

That's also my concern with tying PAMT management to S-EPT population.  E.g. if
a use case triggers a decent amount S-EPT churn, then dynamic PAMT support will
exacerbate the S-EPT overhead.

But IIUC, that's a limitation of the TDX-Module design, i.e. there's no way to
hand it a pool of PAMT pages to manage.  And I suppose if a use case is churning
S-EPT, then it's probably going to be sad no matter what.  So, as long as the KVM
side of things isn't completely awful, I can live with on-demand PAMT management.

As for the global lock, I don't really care what we go with for initial support,
just so long as there's clear line of sight to an elegant solution _if_ we need
shard the lock.

---

## [87] Edgecombe, Rick P — 2025-08-20
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Wed, 2025-08-20 at 08:31 -0700, Sean Christopherson wrote:
> > But man, the number and complexity of the locks is getting a bit high across
> > the whole stack. I don't have any easy ideas.

I confirmed matching the page size is currently required. Having it work with
mismatched page sizes was considered, but assessed to require more memory use.
As in more pages needed per 2MB region, not just more memory usage due to the
pre-allocation of all memory. We can do it if we prefer the simplicity over
memory usage.

> 
> But IIUC, that's a limitation of the TDX-Module design, i.e. there's no way to

Ok, I'll leave it and we can look at whether the KVM side is simple enough.
Thanks for circling back.

---

## [88] Sagi Shahar — 2025-08-21
*Subject: Re: [PATCHv2 08/12] KVM: TDX: Handle PAMT allocation in fault path*

On Mon, Jun 9, 2025 at 2:16 PM Kirill A. Shutemov
<kirill.shutemov@linux.intel.com> wrote:
>
> There are two distinct cases when the kernel needs to allocate PAMT

tdx_pamt_get() can return non-zero value in case of success e.g.
returning 1 in case tdx_pamt_add() lost the race. Shouldn't we check
for (ret < 0) here and below cases?

>
>         /* TODO: handle large pages. */

---

## [89] Edgecombe, Rick P — 2025-08-21
*Subject: Re: [PATCHv2 08/12] KVM: TDX: Handle PAMT allocation in fault path*

On Thu, 2025-08-21 at 14:21 -0500, Sagi Shahar wrote:
> >   int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
> >                                enum pg_level level, kvm_pfn_t pfn)

No?

+static int tdx_pamt_get(struct page *page, enum pg_level level)
+{
+	unsigned long hpa = page_to_phys(page);
+	atomic_t *pamt_refcount;
+	LIST_HEAD(pamt_pages);
+	int ret;
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return 0;
+
+	if (level != PG_LEVEL_4K)
+		return 0;
+
+	pamt_refcount = tdx_get_pamt_refcount(hpa);
+	WARN_ON_ONCE(atomic_read(pamt_refcount) < 0);
+
+	if (atomic_inc_not_zero(pamt_refcount))
+		return 0;
+
+	if (tdx_alloc_pamt_pages(&pamt_pages))
+		return -ENOMEM;
+
+	ret = tdx_pamt_add(pamt_refcount, hpa, &pamt_pages);
+	if (ret)
+		tdx_free_pamt_pages(&pamt_pages);
+
+	return ret >= 0 ? 0 : ret;
+}

> Shouldn't we check
> for (ret < 0) here and below cases?

I think you are thinking of tdx_pamt_add().

---

## [90] Sagi Shahar — 2025-08-21
*Subject: Re: [PATCHv2 08/12] KVM: TDX: Handle PAMT allocation in fault path*

On Thu, Aug 21, 2025 at 2:35 PM Edgecombe, Rick P
<rick.p.edgecombe@intel.com> wrote:
>
> On Thu, 2025-08-21 at 14:21 -0500, Sagi Shahar wrote:

My bad.

---

## [91] Dave Hansen — 2025-09-08
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On 6/9/25 12:13, Kirill A. Shutemov wrote:
> The exact size of the required PAMT memory is determined by the TDX
> module and may vary between TDX module versions, but currently it is

I'm beginning to think that this series is barking up the wrong tree.

>  18 files changed, 702 insertions(+), 108 deletions(-)

I totally agree that saving 0.4% of memory on a gagillion systems saves
a gagillion dollars.

But this series seems to be marching down the path that the savings
needs to be down at page granularity: If a 2M page doesn't need PAMT
then it strictly shouldn't have any PAMT. While that's certainly a
high-utiltiy tact, I can't help but think it may be over complicated.

What if we just focused on three states:

1. System boots, has no DPAMT.
2. First TD starts up, all DPAMT gets allocated
3. Last TD shuts down, all DPAMT gets freed

The cases that leaves behind are when the system has a small number of
TDs packed into a relatively small number of 2M pages. That occurs
either because they're backing with real huge pages or that they are
backed with 4k and nicely compacted because memory wasn't fragmented.

I know our uberscaler buddies are quite fond of those cases and want to
minimize memory use. But are you folks really going to have that many
systems which deploy a very small number of small TDs?

In other words, can we simplify this? Or at least _start_ simpler with v1?

---

## [92] Kiryl Shutsemau — 2025-09-09
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Mon, Sep 08, 2025 at 12:17:58PM -0700, Dave Hansen wrote:
> On 6/9/25 12:13, Kirill A. Shutemov wrote:
> > The exact size of the required PAMT memory is determined by the TDX

You cannot give all DPAMT memory to TDX module at the start of the first
TD and forget about it. Well you can, if you give up ever mapping guest
memory with 2M pages.

Dynamic PAMT pages are stored into PAMT_2M entry and you cannot have 2M
page and have Dynamic 4K entries stored there at the same time.

You would need to handle at least for promotion/demotion and stash this
memory somewhere while 2M pages used.

And it is going to be very wasteful. With huge pages, in most cases, you
only need dynamic PAMT for control pages. You will have a lot of memory
sitting in stash with zero use.

---

## [93] Dave Hansen — 2025-09-09
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On 9/9/25 04:16, Kiryl Shutsemau wrote:
> Dynamic PAMT pages are stored into PAMT_2M entry and you cannot have 2M
> page and have Dynamic 4K entries stored there at the same time.

That sounds like a TDX module implementation bug to me.

Worst possible case, the TDX module could double the
'sysinfo_tdmr->pamt_2m_entry_size' and use the other half for more pointers.

> And it is going to be very wasteful. With huge pages, in most cases, you
> only need dynamic PAMT for control pages. You will have a lot of memory

I think it's going to be hard to convince me without actual data on this
one.

Even then, we're talking about 0.4% of system memory. So how much code
and complexity are we talking about in order to save a *maximum* of 0.4%
of system memory?

---

## [94] Vishal Annapurve — 2025-09-10
*Subject: Re: [PATCHv2 00/12] TDX: Enable Dynamic PAMT*

On Tue, Sep 9, 2025 at 8:24 AM Dave Hansen <dave.hansen@intel.com> wrote:
>
> On 9/9/25 04:16, Kiryl Shutsemau wrote:

* With 1G page backing and with DPAMT entries created only for 4K EPT mappings
- ~5MB of DPAMT memory usage for 704G guest memory size. We expect the
DPAMT memory usage to be in MBs even with 4096G guest memory size.

* With DPAMT entries created for all private memory irrespective of
mapping granularity
- DPAMT memory usage is around ~3GB for 704G guest memory size and
around ~16G for 4096G guest memory size.

For a 4TB guest memory size with 1G page backing, the DPAMT memory usage

> Even then, we're talking about 0.4% of system memory. So how much code
> and complexity are we talking about in order to save a *maximum* of 0.4%

---

## [95] Edgecombe, Rick P — 2025-09-16
*Subject: Re: [PATCHv2 04/12] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Mon, 2025-06-09 at 22:13 +0300, Kirill A. Shutemov wrote:
> +
> +static int tdx_pamt_add(atomic_t *pamt_refcount, unsigned long hpa,

Hey Kirill,

I couldn't figure out how this tdx_hpa_range_not_free() check helps. We are
already inside the lock also taken by any operation that might affect PAMT
state. Can you explain more about this? Otherwise I'm going to drop it for
inability to explain.

Rick

> +
> +	return 0;

---

## [96] Kiryl Shutsemau — 2025-09-16
*Subject: Re: [PATCHv2 04/12] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Tue, Sep 16, 2025 at 12:03:26AM +0000, Edgecombe, Rick P wrote:
> On Mon, 2025-06-09 at 22:13 +0300, Kirill A. Shutemov wrote:
> > +

My git has comment for the check:

https://git.kernel.org/pub/scm/linux/kernel/git/kas/linux.git/tree/arch/x86/virt/vmx/tdx/tdx.c?h=tdx/dpamt&id=375706fe73a8499dbdddb22c13d19d7286280ad6#n2160

Consider the following scenario

		CPU0					CPU1
tdx_pamt_put()
  atomic_dec_and_test() == true
  					tdx_pamt_get()
					  atomic_inc_not_zero() == false
					  tdx_pamt_add()
					    <takes pamt_lock>
					    // CPU0 never removed PAMT memory
					    tdh_phymem_pamt_add() == HPA_RANGE_NOT_FREE
					    atomic_set(1);
					    <drops pamt_lock>
  <takes pamt_lock>
  // Lost the race to CPU1
  atomic_read() > 0
  <drop pamt_lock>

Does it make sense?

---

## [97] Edgecombe, Rick P — 2025-09-16
*Subject: Re: [PATCHv2 04/12] x86/virt/tdx: Add tdx_alloc/free_page() helpers*

On Tue, 2025-09-16 at 10:22 +0100, Kiryl Shutsemau wrote:
> My git has comment for the check:
> 

Yes, I saw but wasn't enough for me.

> Consider the following scenario
> 

Ah, yes thanks. It falls out from the asymmetry of when the inc/dec happens
between get/put.

---
