---
title: 'PCI/TSM: PCIe Link Encryption Establishment via TDX platform services'
date: 2026-03-28
last_reply: 2026-04-27
message_count: 140
participants: ['Xu Yilun', 'Edgecombe, Rick P', 'Dan Williams', 'kernel test robot', 'Nikolay Borisov', 'Dave Hansen', 'Tony Lindgren', 'Baolu Lu', 'Huang, Kai', 'Tian, Kevin', 'Dan Williams']
---

## [1] Xu Yilun — 2026-03-28

This series is based on mainline v7.0-rc2 and targets v7.1 (quite
aggressive though). The merge path will be through tsm.git with tip.git
acks where needed. I know there are several parallel series on the fly,
so Dave you can wait for Dan to review, or ack/nak as you have time,
thanks.  No KVM change, no acks from kvm.git is needed.

== Overview ==

This series adds a PCI/TSM low-level driver implementation for TDX
Connect (the TEE I/O architecture for Intel platforms). PCI/TSM is the
Linux PCI core subsystem [1][2] that supports Link Encryption & trust
establishment between CoCo-VM and assigned devices, allowing CoCo-VM to
accept devices for private memory access (private DMA). This series
only implements Link Encryption. It is a pre-requisite for trusted
device assignment in TDX system.

Two protocols, SPDM (Security Protocol and Data Model) and PCI
IDE (Integrity and Data Encryption) work together to establish the Link
Encryption. SPDM creates trust on untrusted transit for key exchanging.
IDE performs the actual real-time encryption for data traffic. In TSM
world, they are managed by secure firmwares, e.g. TDX Module.

To manage these protocols, TDX Module introduces Extensions to support
long running / hard-irq preemptible flows inside. Host invokes these
flows via Extension-SEAMCALLs.

This series has 2 distinct parts:

  Patches  1-13: TDX core cleanups and TDX Module Extensions enabling
  Patches 14-31: tdx_host TSM driver for PCIe Link Encryption

[1]: https://lore.kernel.org/linux-coco/20251031212902.2256310-1-dan.j.williams@intel.com/
[2]: https://lore.kernel.org/linux-coco/20251105040055.2832866-1-dan.j.williams@intel.com/

== Merge notes ==

 - Merge conflicts with parallel series:
   Sean's VMXON: https://lore.kernel.org/all/20260214012702.2368778-1-seanjc@google.com/
   Chao's runtime update: https://lore.kernel.org/all/20260326084448.29947-1-chao.gao@intel.com/

 - Picked several patches from parallel series:
   Patch  1: https://lore.kernel.org/all/20260323-fuller_tdx_kexec_support-v2-1-87a36409e051@intel.com/
   Patch 14: https://lore.kernel.org/all/20260303000207.1836586-2-dan.j.williams@intel.com/
   Patch 15: https://lore.kernel.org/all/20260326084448.29947-3-chao.gao@intel.com/

== Changelog ==
v2:
- Subject change. previously it was:
  "PCI/TSM: TDX Connect: SPDM Session and IDE Establishment"
- Remove __free() for core TDX and refactor all tdx_ext functions
- Use kzalloc(PAGE_SIZE, ...) instead of alloc_page() in TDX core
- Check feature0 support before reading optional global metadata
- Split the TDX Module Extensions enabling into small patches
- Enable TDX Module Extensions along with Basic TDX enabling
- Refactor SEAMCALL version handling
- For tdx_page_array, make page allocation method configurable
  - For TDX Module Extensions, use contiguous page allocation
  - For IOMMU_MT, use a custom page allocation
- Print TDX Extensions memory usage
- Various Changelog & comments refine

v1: https://lore.kernel.org/all/20251117022311.2443900-1-yilun.xu@linux.intel.com/
- No tdx_enable() needed in tdx-host
- Simplify tdx_page_array kAPI, no singleton mode input
- Refactor the handling of TDX_INTERRUPTED_RESUMABLE
- Refine the usage of scope-based cleanup in tdx-host
- Set nr_stream_id in tdx-host, not in PCI ACPI initialization
- Use KEYP table + ECAP bit50 to decide Domain ID reservation
- Refactor IDE Address Association Register setup
- Remove prototype patches
- Refactor tdx_enable_ext() locking because of Sean's change
- Pick ACPICA KEYP patch from ACPICA repo
- Select TDX Connect feature for TDH.SYS.CONFIG, remove temporary
  solution for TDH.SYS.INIT
- Use Rick's tdx_errno.h movement patch [6]
- Factor out scope-based cleanup patches in mm
- Remove redunant header files, add header files only when first used
- Use dev_err_probe() when possible
- keyp_info_match() refactor
- Use bitfield.h macros for PAGE_LIST_INFO & HPA_ARRAY_T raw value
- Remove reserved fields for spdm_config_info_t
- Simplify return for tdh_ide_stream_block()
- Other small fixes for Jonathan's comments

RFC: https://lore.kernel.org/linux-coco/20250919142237.418648-1-dan.j.williams@intel.com/


Chao Gao (1):
  coco/tdx-host: Introduce a "tdx_host" device

Dan Williams (1):
  PCI/TSM: Report active IDE streams per host bridge

Dave Jiang (1):
  acpi: Add KEYP support to fw_table parsing

Kiryl Shutsemau (1):
  x86/tdx: Move all TDX error defines into <asm/shared/tdx_errno.h>

Lu Baolu (2):
  iommu/vt-d: Cache max domain ID to avoid redundant calculation
  iommu/vt-d: Reserve the MSB domain ID bit for the TDX module

Xu Yilun (21):
  x86/virt/tdx: Move bit definitions of TDX_FEATURES0 to public header
  x86/virt/tdx: Add tdx_page_array helpers for new TDX Module objects
  x86/virt/tdx: Support allocating contiguous pages for tdx_page_array
  x86/virt/tdx: Extend tdx_page_array to support IOMMU_MT
  x86/virt/tdx: Read global metadata for TDX Module Extensions/Connect
  x86/virt/tdx: Embed version info in SEAMCALL leaf function definitions
  x86/virt/tdx: Configure TDX Module with optional TDX Connect feature
  x86/virt/tdx: Move tdx_clflush_page() up in the file
  x86/virt/tdx: Add extra memory to TDX Module for Extensions
  x86/virt/tdx: Make TDX Module initialize Extensions
  x86/virt/tdx: Enable the Extensions after basic TDX Module init
  x86/virt/tdx: Extend tdx_clflush_page() to handle compound pages
  coco/tdx-host: Support Link TSM for TDX host
  x86/virt/tdx: Add a helper to loop on TDX_INTERRUPTED_RESUMABLE
  iommu/vt-d: Export a helper to do function for each dmar_drhd_unit
  coco/tdx-host: Setup all trusted IOMMUs on TDX Connect init
  mm: Add __free() support for __free_page()
  coco/tdx-host: Parse ACPI KEYP table to init IDE for PCI host bridges
  x86/virt/tdx: Add SEAMCALL wrappers for IDE stream management
  coco/tdx-host: Implement IDE stream setup/teardown
  coco/tdx-host: Finally enable SPDM session and IDE Establishment

Zhenzhong Duan (4):
  x86/virt/tdx: Add SEAMCALL wrappers for trusted IOMMU setup and clear
  coco/tdx-host: Add a helper to exchange SPDM messages through DOE
  x86/virt/tdx: Add SEAMCALL wrappers for SPDM management
  coco/tdx-host: Implement SPDM session setup

 drivers/virt/coco/Kconfig                     |   2 +
 drivers/virt/coco/tdx-host/Kconfig            |  16 +
 drivers/virt/coco/Makefile                    |   1 +
 drivers/virt/coco/tdx-host/Makefile           |   1 +
 Documentation/ABI/testing/sysfs-class-tsm     |  13 +
 arch/x86/include/asm/shared/tdx.h             |   1 +
 .../vmx => include/asm/shared}/tdx_errno.h    |  30 +-
 arch/x86/include/asm/tdx.h                    |  95 +-
 arch/x86/include/asm/tdx_global_metadata.h    |  14 +
 arch/x86/kvm/vmx/tdx.h                        |   1 -
 arch/x86/virt/vmx/tdx/tdx.h                   |  42 +-
 drivers/iommu/intel/iommu.h                   |   2 +
 include/linux/acpi.h                          |   3 +
 include/linux/dmar.h                          |   2 +
 include/linux/fw_table.h                      |   1 +
 include/linux/gfp.h                           |   1 +
 include/linux/pci-ide.h                       |   4 +
 include/linux/tsm.h                           |   3 +
 arch/x86/virt/vmx/tdx/tdx.c                   | 839 ++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c   |  36 +
 drivers/acpi/tables.c                         |  12 +-
 drivers/iommu/intel/dmar.c                    |  67 ++
 drivers/iommu/intel/iommu.c                   |  10 +-
 drivers/pci/ide.c                             |   9 +-
 drivers/virt/coco/tdx-host/tdx-host.c         | 952 ++++++++++++++++++
 drivers/virt/coco/tsm-core.c                  |  97 ++
 lib/fw_table.c                                |   9 +
 27 files changed, 2202 insertions(+), 61 deletions(-)
 create mode 100644 drivers/virt/coco/tdx-host/Kconfig
 create mode 100644 drivers/virt/coco/tdx-host/Makefile
 rename arch/x86/{kvm/vmx => include/asm/shared}/tdx_errno.h (61%)
 create mode 100644 drivers/virt/coco/tdx-host/tdx-host.c


base-commit: 11439c4635edd669ae435eec308f4ab8a0804808

---

## [2] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 01/31] x86/tdx: Move all TDX error defines into <asm/shared/tdx_errno.h>*

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

Also, adjust BITUL() -> _BITULL() to address 32 bit build errors after the
move.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[enhance log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Vishal Verma <vishal.l.verma@intel.com>
Reviewed-by: Chao Gao <chao.gao@intel.com>
---
 arch/x86/include/asm/shared/tdx.h             |  1 +
 .../vmx => include/asm/shared}/tdx_errno.h    | 28 +++++++++++++++----
 arch/x86/include/asm/tdx.h                    | 21 --------------
 arch/x86/kvm/vmx/tdx.h                        |  1 -
 4 files changed, 23 insertions(+), 28 deletions(-)
 rename arch/x86/{kvm/vmx => include/asm/shared}/tdx_errno.h (64%)

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
similarity index 64%
rename from arch/x86/kvm/vmx/tdx_errno.h
rename to arch/x86/include/asm/shared/tdx_errno.h
index 6ff4672c4181..8bf6765cf082 100644
--- a/arch/x86/kvm/vmx/tdx_errno.h
+++ b/arch/x86/include/asm/shared/tdx_errno.h
@@ -1,14 +1,15 @@
 /* SPDX-License-Identifier: GPL-2.0 */
-/* architectural status code for SEAMCALL */
-
-#ifndef __KVM_X86_TDX_ERRNO_H
-#define __KVM_X86_TDX_ERRNO_H
+#ifndef _ASM_X86_SHARED_TDX_ERRNO_H
+#define _ASM_X86_SHARED_TDX_ERRNO_H
+#include <asm/trapnr.h>
 
+/* Upper 32 bit of the TDX error code encodes the status */
 #define TDX_SEAMCALL_STATUS_MASK		0xFFFFFFFF00000000ULL
 
 /*
- * TDX SEAMCALL Status Codes (returned in RAX)
+ * TDX Status Codes (returned in RAX)
  */
+#define TDX_SUCCESS				0ULL
 #define TDX_NON_RECOVERABLE_VCPU		0x4000000100000000ULL
 #define TDX_NON_RECOVERABLE_TD			0x4000000200000000ULL
 #define TDX_NON_RECOVERABLE_TD_NON_ACCESSIBLE	0x6000000500000000ULL
@@ -17,6 +18,7 @@
 #define TDX_OPERAND_INVALID			0xC000010000000000ULL
 #define TDX_OPERAND_BUSY			0x8000020000000000ULL
 #define TDX_PREVIOUS_TLB_EPOCH_BUSY		0x8000020100000000ULL
+#define TDX_RND_NO_ENTROPY			0x8000020300000000ULL
 #define TDX_PAGE_METADATA_INCORRECT		0xC000030000000000ULL
 #define TDX_VCPU_NOT_ASSOCIATED			0x8000070200000000ULL
 #define TDX_KEY_GENERATION_FAILED		0x8000080000000000ULL
@@ -28,6 +30,20 @@
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
@@ -37,4 +53,4 @@
 #define TDX_OPERAND_ID_SEPT			0x92
 #define TDX_OPERAND_ID_TD_EPOCH			0xa9
 
-#endif /* __KVM_X86_TDX_ERRNO_H */
+#endif /* _ASM_X86_SHARED_TDX_ERRNO_H */
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 6b338d7f01b7..e040e0467ae4 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -9,29 +9,8 @@
 
 #include <asm/errno.h>
 #include <asm/ptrace.h>
-#include <asm/trapnr.h>
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

## [3] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 02/31] x86/virt/tdx: Move bit definitions of TDX_FEATURES0 to public header*

Move bit definitions of TDX_FEATURES0 to TDX core public header.

Kernel users get TDX_FEATURES0 bitmap via tdx_get_sysinfo(). It is
reasonable to also public the definitions of each bit. TDX Connect (a
new TDX feature to enable Trusted I/O virtualization) will add new bits
and check them in separate kernel modules.

Take the opportunity to change its type to BIT_ULL since TDX_FEATURES0
is explicitly defined as 64-bit in both TDX Module Specification and
TDX core code.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/include/asm/tdx.h  | 4 ++++
 arch/x86/virt/vmx/tdx/tdx.h | 3 ---
 2 files changed, 4 insertions(+), 3 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index e040e0467ae4..65c4da396450 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -127,6 +127,10 @@ static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
 int tdx_cpu_enable(void);
 int tdx_enable(void);
 const char *tdx_dump_mce_info(struct mce *m);
+
+/* Bit definitions of TDX_FEATURES0 metadata field */
+#define TDX_FEATURES0_NO_RBP_MOD	BIT_ULL(18)
+
 const struct tdx_sys_info *tdx_get_sysinfo(void);
 
 int tdx_guest_keyid_alloc(void);
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 82bb82be8567..c641b4632826 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -84,9 +84,6 @@ struct tdmr_info {
 	DECLARE_FLEX_ARRAY(struct tdmr_reserved_area, reserved_areas);
 } __packed __aligned(TDMR_INFO_ALIGNMENT);
 
-/* Bit definitions of TDX_FEATURES0 metadata field */
-#define TDX_FEATURES0_NO_RBP_MOD	BIT(18)
-
 /*
  * Do not put any hardware-defined TDX structure representations below
  * this comment!

---

## [4] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 03/31] x86/virt/tdx: Add tdx_page_array helpers for new TDX Module objects*

Add struct tdx_page_array definition for new TDX Module object
types - HPA_ARRAY_T and HPA_LIST_INFO. They are used as input/output
parameters in newly defined SEAMCALLs. Also define some helpers to
allocate, setup and free tdx_page_array.

HPA_ARRAY_T and HPA_LIST_INFO are similar in most aspects. They both
represent a list of pages for TDX Module accessing. There are several
use cases for these 2 structures:

 - As SEAMCALL inputs. They are claimed by TDX Module as control pages.
   Control pages are private pages for TDX Module to hold its internal
   control structures or private data. TDR, TDCS, TDVPR... are existing
   control pages, just not added via tdx_page_array.
 - As SEAMCALL outputs. They were TDX Module control pages and now are
   released.
 - As SEAMCALL inputs. They are just temporary buffers for exchanging
   data blobs in one SEAMCALL. TDX Module will not hold them for long
   time.

The 2 structures both need a 'root page' which contains a list of HPAs.
They collapse the HPA of the root page and the number of valid HPAs
into a 64 bit raw value for SEAMCALL parameters. The root page is
always a medium for passing data pages, TDX Module never keeps the
root page.

A main difference is HPA_ARRAY_T requires singleton mode when
containing just 1 functional page (page0). In this mode the root page is
not needed and the HPA field of the raw value directly points to the
page0. But in this patch, root page is always allocated for user
friendly kAPIs.

Another small difference is HPA_LIST_INFO contains a 'first entry' field
which could be filled by TDX Module. This simplifies host by providing
the same structure when re-invoke the interrupted SEAMCALL. No need for
host to touch this field.

Typical usages of the tdx_page_array:

1. Add control pages:
 - struct tdx_page_array *array = tdx_page_array_create(nr_pages);
 - seamcall(TDH_XXX_CREATE, array, ...);

2. Release control pages:
 - seamcall(TDX_XXX_DELETE, array, &nr_released, &released_hpa);
 - tdx_page_array_ctrl_release(array, nr_released, released_hpa);

3. Exchange data blobs:
 - struct tdx_page_array *array = tdx_page_array_create(nr_pages);
 - seamcall(TDX_XXX, array, ...);
 - Read data from array.
 - tdx_page_array_free(array);

4. Note the root page contains 512 HPAs at most, if more pages are
   required, re-populate the tdx_page_array is needed.

 - struct tdx_page_array *array = tdx_page_array_alloc(nr_pages);
 - for each 512-page bulk
   - tdx_page_array_populate(array, offset);
   - seamcall(TDH_XXX_ADD, array, ...);

In case 2, SEAMCALLs output the released page array in the form of
HPA_ARRAY_T or PAGE_LIST_INFO. Use tdx_page_array_ctrl_release() to
check if the output pages match the original input pages. If failed,
TDX Module is buggy. In this case the safer way is to leak the
control pages, call tdx_page_array_ctrl_leak().

The usage of tdx_page_array will be in following patches.

Co-developed-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/include/asm/tdx.h  |  37 +++++
 arch/x86/virt/vmx/tdx/tdx.c | 299 ++++++++++++++++++++++++++++++++++++
 2 files changed, 336 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 65c4da396450..9173a432b312 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -139,6 +139,43 @@ void tdx_guest_keyid_free(unsigned int keyid);
 
 void tdx_quirk_reset_page(struct page *page);
 
+/**
+ * struct tdx_page_array - Represents a list of pages for TDX Module access
+ * @nr_pages: Total number of data pages in the collection
+ * @pages: Array of data page pointers containing all the data
+ *
+ * @offset: Internal: The starting index in @pages, positions the currently
+ *	    populated page window in @root.
+ * @nents: Internal: Number of valid HPAs for the page window in @root
+ * @root: Internal: A single 4KB page holding the 8-byte HPAs of the page
+ *	  window. The page window max size is constrained by the root page,
+ *	  which is 512 HPAs.
+ *
+ * This structure abstracts several TDX Module defined object types, e.g.,
+ * HPA_ARRAY_T and HPA_LIST_INFO. Typically they all use a "root page" as the
+ * medium to exchange a list of data pages between host and TDX Module. This
+ * structure serves as a unified parameter type for SEAMCALL wrappers, where
+ * these hardware object types are needed.
+ */
+struct tdx_page_array {
+	/* public: */
+	unsigned int nr_pages;
+	struct page **pages;
+
+	/* private: */
+	unsigned int offset;
+	unsigned int nents;
+	u64 *root;
+};
+
+void tdx_page_array_free(struct tdx_page_array *array);
+DEFINE_FREE(tdx_page_array_free, struct tdx_page_array *, if (_T) tdx_page_array_free(_T))
+struct tdx_page_array *tdx_page_array_create(unsigned int nr_pages);
+void tdx_page_array_ctrl_leak(struct tdx_page_array *array);
+int tdx_page_array_ctrl_release(struct tdx_page_array *array,
+				unsigned int nr_released,
+				u64 released_hpa);
+
 struct tdx_td {
 	/* TD root structure: */
 	struct page *tdr_page;
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 8b8e165a2001..a3021e7e2490 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -30,6 +30,7 @@
 #include <linux/suspend.h>
 #include <linux/idr.h>
 #include <linux/kvm_types.h>
+#include <linux/bitfield.h>
 #include <asm/page.h>
 #include <asm/special_insns.h>
 #include <asm/msr-index.h>
@@ -258,6 +259,304 @@ static int build_tdx_memlist(struct list_head *tmb_list)
 	return ret;
 }
 
+#define TDX_PAGE_ARRAY_MAX_NENTS	(PAGE_SIZE / sizeof(u64))
+
+static int tdx_page_array_populate(struct tdx_page_array *array,
+				   unsigned int offset)
+{
+	u64 *entries;
+	int i;
+
+	if (offset >= array->nr_pages)
+		return 0;
+
+	array->offset = offset;
+	array->nents = umin(array->nr_pages - offset,
+			    TDX_PAGE_ARRAY_MAX_NENTS);
+
+	entries = array->root;
+	for (i = 0; i < array->nents; i++)
+		entries[i] = page_to_phys(array->pages[offset + i]);
+
+	return array->nents;
+}
+
+static void tdx_free_pages_bulk(unsigned int nr_pages, struct page **pages)
+{
+	int i;
+
+	for (i = 0; i < nr_pages; i++)
+		__free_page(pages[i]);
+}
+
+static int tdx_alloc_pages_bulk(unsigned int nr_pages, struct page **pages)
+{
+	unsigned int filled, done = 0;
+
+	do {
+		filled = alloc_pages_bulk(GFP_KERNEL, nr_pages - done,
+					  pages + done);
+		if (!filled) {
+			tdx_free_pages_bulk(done, pages);
+			return -ENOMEM;
+		}
+
+		done += filled;
+	} while (done != nr_pages);
+
+	return 0;
+}
+
+/**
+ * tdx_page_array_free() - Free all memory for a tdx_page_array
+ * @array: The tdx_page_array to be freed.
+ *
+ * Free all associated pages and the container itself.
+ */
+void tdx_page_array_free(struct tdx_page_array *array)
+{
+	if (!array)
+		return;
+
+	tdx_free_pages_bulk(array->nr_pages, array->pages);
+	kfree(array->pages);
+	kfree(array->root);
+	kfree(array);
+}
+EXPORT_SYMBOL_GPL(tdx_page_array_free);
+
+static struct tdx_page_array *
+tdx_page_array_alloc(unsigned int nr_pages)
+{
+	struct tdx_page_array *array = NULL;
+	struct page **pages = NULL;
+	u64 *root = NULL;
+	int ret;
+
+	if (!nr_pages)
+		return NULL;
+
+	array = kzalloc_obj(*array);
+	if (!array)
+		goto out_free;
+
+	root = kzalloc(PAGE_SIZE, GFP_KERNEL);
+	if (!root)
+		goto out_free;
+
+	pages = kcalloc(nr_pages, sizeof(*pages), GFP_KERNEL);
+	if (!pages)
+		goto out_free;
+
+	ret = tdx_alloc_pages_bulk(nr_pages, pages);
+	if (ret)
+		goto out_free;
+
+	array->nr_pages = nr_pages;
+	array->pages = pages;
+	array->root = root;
+
+	return array;
+
+out_free:
+	kfree(pages);
+	kfree(root);
+	kfree(array);
+
+	return NULL;
+}
+
+/**
+ * tdx_page_array_create() - Create a small tdx_page_array (up to 512 pages)
+ * @nr_pages: Number of pages to allocate (must be <= 512).
+ *
+ * Allocate and populate a tdx_page_array in a single step. This is intended
+ * for small collections that fit within a single root page. The allocated
+ * pages are all order-0 pages. This is the most common use case for a list of
+ * TDX control pages.
+ *
+ * If more pages are required, use tdx_page_array_alloc() and
+ * tdx_page_array_populate() to build tdx_page_array chunk by chunk.
+ *
+ * Return: Fully populated tdx_page_array or NULL on failure.
+ */
+struct tdx_page_array *tdx_page_array_create(unsigned int nr_pages)
+{
+	struct tdx_page_array *array;
+	int populated;
+
+	if (nr_pages > TDX_PAGE_ARRAY_MAX_NENTS)
+		return NULL;
+
+	array = tdx_page_array_alloc(nr_pages);
+	if (!array)
+		return NULL;
+
+	populated = tdx_page_array_populate(array, 0);
+	if (populated != nr_pages)
+		goto out_free;
+
+	return array;
+
+out_free:
+	tdx_page_array_free(array);
+	return NULL;
+}
+EXPORT_SYMBOL_GPL(tdx_page_array_create);
+
+/**
+ * tdx_page_array_ctrl_leak() - Leak data pages and free the container
+ * @array: The tdx_page_array to be leaked.
+ *
+ * Call this function when failed to reclaim the control pages. Free the root
+ * page and the holding structures, but orphan the data pages, to prevent the
+ * host from re-allocating and accessing memory that the hardware may still
+ * consider private.
+ */
+void tdx_page_array_ctrl_leak(struct tdx_page_array *array)
+{
+	if (!array)
+		return;
+
+	kfree(array->pages);
+	kfree(array->root);
+	kfree(array);
+}
+EXPORT_SYMBOL_GPL(tdx_page_array_ctrl_leak);
+
+static bool tdx_page_array_validate_release(struct tdx_page_array *array,
+					    unsigned int offset,
+					    unsigned int nr_released,
+					    u64 released_hpa)
+{
+	unsigned int nents;
+
+	if (offset >= array->nr_pages)
+		return false;
+
+	nents = umin(array->nr_pages - offset, TDX_PAGE_ARRAY_MAX_NENTS);
+
+	if (nents != nr_released) {
+		pr_err("%s nr_released [%d] doesn't match page array nents [%d]\n",
+		       __func__, nr_released, nents);
+		return false;
+	}
+
+	/*
+	 * Unfortunately TDX has multiple page allocation protocols, check the
+	 * "singleton" case required for HPA_ARRAY_T.
+	 */
+	if (page_to_phys(array->pages[0]) == released_hpa &&
+	    array->nr_pages == 1)
+		return true;
+
+	/* Then check the "non-singleton" case */
+	if (virt_to_phys(array->root) == released_hpa) {
+		u64 *entries = array->root;
+		int i;
+
+		for (i = 0; i < nents; i++) {
+			struct page *page = array->pages[offset + i];
+			u64 val = page_to_phys(page);
+
+			if (val != entries[i]) {
+				pr_err("%s entry[%d] [0x%llx] doesn't match page hpa [0x%llx]\n",
+				       __func__, i, entries[i], val);
+				return false;
+			}
+		}
+
+		return true;
+	}
+
+	pr_err("%s failed to validate, released_hpa [0x%llx], root page hpa [0x%llx], page0 hpa [%#llx], number pages %u\n",
+	       __func__, released_hpa, virt_to_phys(array->root),
+	       page_to_phys(array->pages[0]), array->nr_pages);
+
+	return false;
+}
+
+/**
+ * tdx_page_array_ctrl_release() - Verify and release TDX control pages
+ * @array: The tdx_page_array used to originally create control pages.
+ * @nr_released: Number of HPAs the TDX Module reported as released.
+ * @released_hpa: The HPA list the TDX Module reported as released.
+ *
+ * TDX Module can at most release 512 control pages, so this function only
+ * accepts small tdx_page_array (up to 512 pages), usually created by
+ * tdx_page_array_create().
+ *
+ * Return: 0 on success, -errno on page release protocol error.
+ */
+int tdx_page_array_ctrl_release(struct tdx_page_array *array,
+				unsigned int nr_released,
+				u64 released_hpa)
+{
+	int i;
+
+	/*
+	 * The only case where ->nr_pages is allowed to be >
+	 * TDX_PAGE_ARRAY_MAX_NENTS is a case where those pages are never
+	 * expected to be released by this function.
+	 */
+	if (WARN_ON(array->nr_pages > TDX_PAGE_ARRAY_MAX_NENTS))
+		return -EINVAL;
+
+	if (WARN_ONCE(!tdx_page_array_validate_release(array, 0, nr_released,
+						       released_hpa),
+		      "page release protocol error, consider reboot and replace TDX Module.\n"))
+		return -EFAULT;
+
+	for (i = 0; i < array->nr_pages; i++) {
+		u64 r;
+
+		r = tdh_phymem_page_wbinvd_hkid(tdx_global_keyid,
+						array->pages[i]);
+		if (WARN_ON(r))
+			return -EFAULT;
+	}
+
+	tdx_page_array_free(array);
+	return 0;
+}
+EXPORT_SYMBOL_GPL(tdx_page_array_ctrl_release);
+
+#define HPA_LIST_INFO_FIRST_ENTRY	GENMASK_U64(11, 3)
+#define HPA_LIST_INFO_PFN		GENMASK_U64(51, 12)
+#define HPA_LIST_INFO_LAST_ENTRY	GENMASK_U64(63, 55)
+
+static u64 __maybe_unused hpa_list_info_assign_raw(struct tdx_page_array *array)
+{
+	return FIELD_PREP(HPA_LIST_INFO_FIRST_ENTRY, 0) |
+	       FIELD_PREP(HPA_LIST_INFO_PFN,
+			  PFN_DOWN(virt_to_phys(array->root))) |
+	       FIELD_PREP(HPA_LIST_INFO_LAST_ENTRY, array->nents - 1);
+}
+
+#define HPA_ARRAY_T_PFN		GENMASK_U64(51, 12)
+#define HPA_ARRAY_T_SIZE	GENMASK_U64(63, 55)
+
+static u64 __maybe_unused hpa_array_t_assign_raw(struct tdx_page_array *array)
+{
+	unsigned long pfn;
+
+	if (array->nents == 1)
+		pfn = page_to_pfn(array->pages[array->offset]);
+	else
+		pfn = PFN_DOWN(virt_to_phys(array->root));
+
+	return FIELD_PREP(HPA_ARRAY_T_PFN, pfn) |
+	       FIELD_PREP(HPA_ARRAY_T_SIZE, array->nents - 1);
+}
+
+static u64 __maybe_unused hpa_array_t_release_raw(struct tdx_page_array *array)
+{
+	if (array->nents == 1)
+		return 0;
+
+	return virt_to_phys(array->root);
+}
+
 static int read_sys_metadata_field(u64 field_id, u64 *data)
 {
 	struct tdx_module_args args = {};

---

## [5] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 04/31] x86/virt/tdx: Support allocating contiguous pages for tdx_page_array*

The current tdx_page_array implementation allocates scattered order-0
pages. However, some TDX Module operations benefit from contiguous
physical memory. E.g. Enabling TDX Module Extensions (an optional TDX
feature) requires ~50MB memory and never returns. Such allocation
would at worst cause ~25GB permanently fragmented memory if each
allocated page is from a different 2M region.

Support allocating contiguous pages for tdx_page_array by making the
allocation method configurable. Change the tdx_page_array_alloc() to
accept a custom allocation function pointer and a context parameter.
Wrap the specific allocation into a tdx_page_array_alloc_contig()
helper.

The foreseeable caller will allocate ~50MB memory with this helper,
exceeding the maximum HPAs (512) a root page can hold, the typical usage
will be:

 - struct tdx_page_array *array = tdx_page_array_alloc_contig(nr_pages);
 - for each 512-page bulk
   - tdx_page_array_populate(array, offset);
   - seamcall(TDH_XXX_ADD, array, ...);

The configurable allocation method would also benefit more
tdx_page_array usages. TDX Module may require more specific memory
layouts encoded in the root page. Will introduce them in following
patches.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 42 +++++++++++++++++++++++++++++++++----
 1 file changed, 38 insertions(+), 4 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index a3021e7e2490..6c4ed80e8e5a 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -289,7 +289,8 @@ static void tdx_free_pages_bulk(unsigned int nr_pages, struct page **pages)
 		__free_page(pages[i]);
 }
 
-static int tdx_alloc_pages_bulk(unsigned int nr_pages, struct page **pages)
+static int tdx_alloc_pages_bulk(unsigned int nr_pages, struct page **pages,
+				void *data)
 {
 	unsigned int filled, done = 0;
 
@@ -326,7 +327,10 @@ void tdx_page_array_free(struct tdx_page_array *array)
 EXPORT_SYMBOL_GPL(tdx_page_array_free);
 
 static struct tdx_page_array *
-tdx_page_array_alloc(unsigned int nr_pages)
+tdx_page_array_alloc(unsigned int nr_pages,
+		     int (*alloc_fn)(unsigned int nr_pages,
+				     struct page **pages, void *data),
+		     void *data)
 {
 	struct tdx_page_array *array = NULL;
 	struct page **pages = NULL;
@@ -348,7 +352,7 @@ tdx_page_array_alloc(unsigned int nr_pages)
 	if (!pages)
 		goto out_free;
 
-	ret = tdx_alloc_pages_bulk(nr_pages, pages);
+	ret = alloc_fn(nr_pages, pages, data);
 	if (ret)
 		goto out_free;
 
@@ -388,7 +392,7 @@ struct tdx_page_array *tdx_page_array_create(unsigned int nr_pages)
 	if (nr_pages > TDX_PAGE_ARRAY_MAX_NENTS)
 		return NULL;
 
-	array = tdx_page_array_alloc(nr_pages);
+	array = tdx_page_array_alloc(nr_pages, tdx_alloc_pages_bulk, NULL);
 	if (!array)
 		return NULL;
 
@@ -521,6 +525,36 @@ int tdx_page_array_ctrl_release(struct tdx_page_array *array,
 }
 EXPORT_SYMBOL_GPL(tdx_page_array_ctrl_release);
 
+static int tdx_alloc_pages_contig(unsigned int nr_pages, struct page **pages,
+				  void *data)
+{
+	struct page *page;
+	int i;
+
+	page = alloc_contig_pages(nr_pages, GFP_KERNEL, numa_mem_id(),
+				  &node_online_map);
+	if (!page)
+		return -ENOMEM;
+
+	for (i = 0; i < nr_pages; i++)
+		pages[i] = page + i;
+
+	return 0;
+}
+
+/*
+ * For holding large number of contiguous pages, usually larger than
+ * TDX_PAGE_ARRAY_MAX_NENTS (512).
+ *
+ * Similar to tdx_page_array_alloc(), after allocating with this
+ * function, call tdx_page_array_populate() to populate the tdx_page_array.
+ */
+static __maybe_unused struct tdx_page_array *
+tdx_page_array_alloc_contig(unsigned int nr_pages)
+{
+	return tdx_page_array_alloc(nr_pages, tdx_alloc_pages_contig, NULL);
+}
+
 #define HPA_LIST_INFO_FIRST_ENTRY	GENMASK_U64(11, 3)
 #define HPA_LIST_INFO_PFN		GENMASK_U64(51, 12)
 #define HPA_LIST_INFO_LAST_ENTRY	GENMASK_U64(63, 55)

---

## [6] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 05/31] x86/virt/tdx: Extend tdx_page_array to support IOMMU_MT*

IOMMU_MT is another TDX Module defined structure similar to HPA_ARRAY_T
and HPA_LIST_INFO. The difference is it requires multi-order contiguous
pages for some entries. It adds an additional NUM_PAGES field for every
multi-order page entry.

Add a dedicated allocation helper for IOMMU_MT. Fortunately put_page()
works well for both single pages and multi-order folios, simplifying the
cleanup logic for all allocation methods.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/include/asm/tdx.h  |  2 +
 arch/x86/virt/vmx/tdx/tdx.c | 90 +++++++++++++++++++++++++++++++++++--
 2 files changed, 89 insertions(+), 3 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 9173a432b312..d5f1d7b7d1e7 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -175,6 +175,8 @@ void tdx_page_array_ctrl_leak(struct tdx_page_array *array);
 int tdx_page_array_ctrl_release(struct tdx_page_array *array,
 				unsigned int nr_released,
 				u64 released_hpa);
+struct tdx_page_array *
+tdx_page_array_create_iommu_mt(unsigned int iq_order, unsigned int nr_mt_pages);
 
 struct tdx_td {
 	/* TD root structure: */
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 6c4ed80e8e5a..2b17e0f73dac 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -275,8 +275,15 @@ static int tdx_page_array_populate(struct tdx_page_array *array,
 			    TDX_PAGE_ARRAY_MAX_NENTS);
 
 	entries = array->root;
-	for (i = 0; i < array->nents; i++)
-		entries[i] = page_to_phys(array->pages[offset + i]);
+	for (i = 0; i < array->nents; i++) {
+		struct page *page = array->pages[offset + i];
+
+		entries[i] = page_to_phys(page);
+
+		/* Now only for iommu_mt */
+		if (compound_nr(page) > 1)
+			entries[i] |= compound_nr(page);
+	}
 
 	return array->nents;
 }
@@ -286,7 +293,7 @@ static void tdx_free_pages_bulk(unsigned int nr_pages, struct page **pages)
 	int i;
 
 	for (i = 0; i < nr_pages; i++)
-		__free_page(pages[i]);
+		put_page(pages[i]);
 }
 
 static int tdx_alloc_pages_bulk(unsigned int nr_pages, struct page **pages,
@@ -463,6 +470,10 @@ static bool tdx_page_array_validate_release(struct tdx_page_array *array,
 			struct page *page = array->pages[offset + i];
 			u64 val = page_to_phys(page);
 
+			/* Now only for iommu_mt */
+			if (compound_nr(page) > 1)
+				val |= compound_nr(page);
+
 			if (val != entries[i]) {
 				pr_err("%s entry[%d] [0x%llx] doesn't match page hpa [0x%llx]\n",
 				       __func__, i, entries[i], val);
@@ -555,6 +566,79 @@ tdx_page_array_alloc_contig(unsigned int nr_pages)
 	return tdx_page_array_alloc(nr_pages, tdx_alloc_pages_contig, NULL);
 }
 
+static int tdx_alloc_pages_iommu_mt(unsigned int nr_pages, struct page **pages,
+				    void *data)
+{
+	unsigned int iq_order = (unsigned int)(long)data;
+	struct folio *t_iq, *t_ctxiq;
+	int ret;
+
+	/* TODO: folio_alloc_node() is preferred, but need numa info */
+	t_iq = folio_alloc(GFP_KERNEL | __GFP_ZERO, iq_order);
+	if (!t_iq)
+		return -ENOMEM;
+
+	t_ctxiq = folio_alloc(GFP_KERNEL | __GFP_ZERO, iq_order);
+	if (!t_ctxiq) {
+		ret = -ENOMEM;
+		goto out_t_iq;
+	}
+
+	ret = tdx_alloc_pages_bulk(nr_pages - 2, pages + 2, NULL);
+	if (ret)
+		goto out_t_ctxiq;
+
+	pages[0] = folio_page(t_iq, 0);
+	pages[1] = folio_page(t_ctxiq, 0);
+
+	return 0;
+
+out_t_ctxiq:
+	folio_put(t_ctxiq);
+out_t_iq:
+	folio_put(t_iq);
+
+	return ret;
+}
+
+/**
+ * tdx_page_array_create_iommu_mt() - Create a page array for IOMMU Memory Tables
+ * @iq_order: The allocation order for the IOMMU Invalidation Queue.
+ * @nr_mt_pages: Number of additional order-0 pages for the MT.
+ *
+ * Allocate and populate a specialized tdx_page_array for IOMMU_MT structures.
+ * The resulting array consists of two multi-order folios (at index 0 and 1)
+ * followed by the requested number of order-0 pages.
+ *
+ * Return: Fully populated tdx_page_array or NULL on failure.
+ */
+struct tdx_page_array *
+tdx_page_array_create_iommu_mt(unsigned int iq_order, unsigned int nr_mt_pages)
+{
+	unsigned int nr_pages = nr_mt_pages + 2;
+	struct tdx_page_array *array;
+	int populated;
+
+	if (nr_pages > TDX_PAGE_ARRAY_MAX_NENTS)
+		return NULL;
+
+	array = tdx_page_array_alloc(nr_pages, tdx_alloc_pages_iommu_mt,
+				     (void *)(long)iq_order);
+	if (!array)
+		return NULL;
+
+	populated = tdx_page_array_populate(array, 0);
+	if (populated != nr_pages)
+		goto out_free;
+
+	return array;
+
+out_free:
+	tdx_page_array_free(array);
+	return NULL;
+}
+EXPORT_SYMBOL_GPL(tdx_page_array_create_iommu_mt);
+
 #define HPA_LIST_INFO_FIRST_ENTRY	GENMASK_U64(11, 3)
 #define HPA_LIST_INFO_PFN		GENMASK_U64(51, 12)
 #define HPA_LIST_INFO_LAST_ENTRY	GENMASK_U64(63, 55)

---

## [7] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 06/31] x86/virt/tdx: Read global metadata for TDX Module Extensions/Connect*

Add reading of the global metadata for TDX Module Extensions & TDX
Connect. Add them in a batch as TDX Connect is currently the only user
of TDX Module Extensions and no way to initialize TDX Module Extensions
without firstly enabling TDX Connect.

TDX Module Extensions & TDX Connect are optional features enumerated by
TDX_FEATURES0. Check the TDX_FEATURES0 before reading these metadata to
avoid failing the whole TDX initialization.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/include/asm/tdx.h                  |  2 ++
 arch/x86/include/asm/tdx_global_metadata.h  | 14 ++++++++
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c | 36 +++++++++++++++++++++
 3 files changed, 52 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index d5f1d7b7d1e7..d7605235aa9b 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -129,7 +129,9 @@ int tdx_enable(void);
 const char *tdx_dump_mce_info(struct mce *m);
 
 /* Bit definitions of TDX_FEATURES0 metadata field */
+#define TDX_FEATURES0_TDXCONNECT	BIT_ULL(6)
 #define TDX_FEATURES0_NO_RBP_MOD	BIT_ULL(18)
+#define TDX_FEATURES0_EXT		BIT_ULL(39)
 
 const struct tdx_sys_info *tdx_get_sysinfo(void);
 
diff --git a/arch/x86/include/asm/tdx_global_metadata.h b/arch/x86/include/asm/tdx_global_metadata.h
index 060a2ad744bf..e7948bca671a 100644
--- a/arch/x86/include/asm/tdx_global_metadata.h
+++ b/arch/x86/include/asm/tdx_global_metadata.h
@@ -34,11 +34,25 @@ struct tdx_sys_info_td_conf {
 	u64 cpuid_config_values[128][2];
 };
 
+struct tdx_sys_info_ext {
+	u16 memory_pool_required_pages;
+	u8 ext_required;
+};
+
+struct tdx_sys_info_connect {
+	u16 ide_mt_page_count;
+	u16 spdm_mt_page_count;
+	u16 iommu_mt_page_count;
+	u16 spdm_max_dev_info_pages;
+};
+
 struct tdx_sys_info {
 	struct tdx_sys_info_features features;
 	struct tdx_sys_info_tdmr tdmr;
 	struct tdx_sys_info_td_ctrl td_ctrl;
 	struct tdx_sys_info_td_conf td_conf;
+	struct tdx_sys_info_ext ext;
+	struct tdx_sys_info_connect connect;
 };
 
 #endif
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index 13ad2663488b..a07f1e7b18e8 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -85,6 +85,36 @@ static int get_tdx_sys_info_td_conf(struct tdx_sys_info_td_conf *sysinfo_td_conf
 	return ret;
 }
 
+static int get_tdx_sys_info_ext(struct tdx_sys_info_ext *sysinfo_ext)
+{
+	int ret = 0;
+	u64 val;
+
+	if (!ret && !(ret = read_sys_metadata_field(0x3100000100000000, &val)))
+		sysinfo_ext->memory_pool_required_pages = val;
+	if (!ret && !(ret = read_sys_metadata_field(0x3100000100000001, &val)))
+		sysinfo_ext->ext_required = val;
+
+	return ret;
+}
+
+static int get_tdx_sys_info_connect(struct tdx_sys_info_connect *sysinfo_connect)
+{
+	int ret = 0;
+	u64 val;
+
+	if (!ret && !(ret = read_sys_metadata_field(0x3000000100000001, &val)))
+		sysinfo_connect->ide_mt_page_count = val;
+	if (!ret && !(ret = read_sys_metadata_field(0x3000000100000002, &val)))
+		sysinfo_connect->spdm_mt_page_count = val;
+	if (!ret && !(ret = read_sys_metadata_field(0x3000000100000003, &val)))
+		sysinfo_connect->iommu_mt_page_count = val;
+	if (!ret && !(ret = read_sys_metadata_field(0x3000000100000007, &val)))
+		sysinfo_connect->spdm_max_dev_info_pages = val;
+
+	return ret;
+}
+
 static int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 {
 	int ret = 0;
@@ -94,5 +124,11 @@ static int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 	ret = ret ?: get_tdx_sys_info_td_ctrl(&sysinfo->td_ctrl);
 	ret = ret ?: get_tdx_sys_info_td_conf(&sysinfo->td_conf);
 
+	if (sysinfo->features.tdx_features0 & TDX_FEATURES0_EXT)
+		ret = ret ?: get_tdx_sys_info_ext(&sysinfo->ext);
+
+	if (sysinfo->features.tdx_features0 & TDX_FEATURES0_TDXCONNECT)
+		ret = ret ?: get_tdx_sys_info_connect(&sysinfo->connect);
+
 	return ret;
 }

---

## [8] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 07/31] x86/virt/tdx: Embed version info in SEAMCALL leaf function definitions*

Embed version information in SEAMCALL leaf function definitions rather
than let the caller open code them. For now, only TDH.VP.INIT is
involved.

Don't bother the caller to choose the SEAMCALL version if unnecessary.
New version SEAMCALLs are guaranteed to be backward compatible, so
ideally kernel doesn't need to keep version history and only uses the
latest version SEAMCALLs.

The concern is some old TDX Modules don't recognize new version
SEAMCALLs. Multiple SEAMCALL versions co-exist when kernel should
support these old Modules. As time goes by, the old Modules deprecate
and old version SEAMCALL definitions should disappear.

The old TDX Modules that only support TDH.VP.INIT v0 are all deprecated,
so only provide the latest (v1) definition.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.h | 23 ++++++++++++++---------
 arch/x86/virt/vmx/tdx/tdx.c |  4 ++--
 2 files changed, 16 insertions(+), 11 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index c641b4632826..e5a9331df451 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -2,6 +2,7 @@
 #ifndef _X86_VIRT_TDX_H
 #define _X86_VIRT_TDX_H
 
+#include <linux/bitfield.h>
 #include <linux/bits.h>
 
 /*
@@ -11,6 +12,18 @@
  * architectural definitions come first.
  */
 
+/*
+ * SEAMCALL leaf:
+ *
+ * Bit 15:0	Leaf number
+ * Bit 23:16	Version number
+ */
+#define SEAMCALL_LEAF			GENMASK(15, 0)
+#define SEAMCALL_VER			GENMASK(23, 16)
+
+#define SEAMCALL_LEAF_VER(l, v)		(FIELD_PREP(SEAMCALL_LEAF, l) | \
+					 FIELD_PREP(SEAMCALL_VER, v))
+
 /*
  * TDX module SEAMCALL leaf functions
  */
@@ -31,7 +44,7 @@
 #define TDH_VP_CREATE			10
 #define TDH_MNG_KEY_FREEID		20
 #define TDH_MNG_INIT			21
-#define TDH_VP_INIT			22
+#define TDH_VP_INIT			SEAMCALL_LEAF_VER(22, 1)
 #define TDH_PHYMEM_PAGE_RDMD		24
 #define TDH_VP_RD			26
 #define TDH_PHYMEM_PAGE_RECLAIM		28
@@ -47,14 +60,6 @@
 #define TDH_VP_WR			43
 #define TDH_SYS_CONFIG			45
 
-/*
- * SEAMCALL leaf:
- *
- * Bit 15:0	Leaf number
- * Bit 23:16	Version number
- */
-#define TDX_VERSION_SHIFT		16
-
 /* TDX page types */
 #define	PT_NDA		0x0
 #define	PT_RSVD		0x1
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 2b17e0f73dac..130214933c2f 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2202,8 +2202,8 @@ u64 tdh_vp_init(struct tdx_vp *vp, u64 initial_rcx, u32 x2apicid)
 		.r8 = x2apicid,
 	};
 
-	/* apicid requires version == 1. */
-	return seamcall(TDH_VP_INIT | (1ULL << TDX_VERSION_SHIFT), &args);
+	/* apicid requires version == 1. See TDH_VP_INIT definition.*/
+	return seamcall(TDH_VP_INIT, &args);
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_vp_init);

---

## [9] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 08/31] x86/virt/tdx: Configure TDX Module with optional TDX Connect feature*

TDX Module supports optional TDX features (e.g. TDX Connect & TDX Module
Extensions) that won't be enabled by default. It extends TDH.SYS.CONFIG
for host to choose to enable them on bootup.

Call TDH.SYS.CONFIG with a new bitmap input parameter to specify which
features to enable. The bitmap uses the same definitions as
TDX_FEATURES0. But note not all bits in TDX_FEATURES0 are valid for
configuration, e.g. TDX Module Extensions is a service that supports TDX
Connect, it is implicitly enabled when TDX Connect is enabled. Setting
TDX_FEATURES0_EXT in the bitmap has no effect.

TDX Module advances the version of TDH.SYS.CONFIG for the change, so
use the latest version (v1) for optional feature enabling. But
supporting existing Modules which only support v0 is still necessary
until they are deprecated, enumerate via TDX_FEATURES0 to decide which
version to use.

TDX Module updates global metadata when optional features are enabled.
Host should update the cached tdx_sysinfo to reflect these changes.

Co-developed-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.h |  3 ++-
 arch/x86/virt/vmx/tdx/tdx.c | 16 +++++++++++++++-
 2 files changed, 17 insertions(+), 2 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index e5a9331df451..870bb75da3ba 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -58,7 +58,8 @@
 #define TDH_PHYMEM_CACHE_WB		40
 #define TDH_PHYMEM_PAGE_WBINVD		41
 #define TDH_VP_WR			43
-#define TDH_SYS_CONFIG			45
+#define TDH_SYS_CONFIG_V0		45
+#define TDH_SYS_CONFIG			SEAMCALL_LEAF_VER(TDH_SYS_CONFIG_V0, 1)
 
 /* TDX page types */
 #define	PT_NDA		0x0
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 130214933c2f..0c5d6bdd810f 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1353,6 +1353,7 @@ static int construct_tdmrs(struct list_head *tmb_list,
 static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
 {
 	struct tdx_module_args args = {};
+	u64 seamcall_fn = TDH_SYS_CONFIG_V0;
 	u64 *tdmr_pa_array;
 	size_t array_sz;
 	int i, ret;
@@ -1377,7 +1378,15 @@ static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
 	args.rcx = __pa(tdmr_pa_array);
 	args.rdx = tdmr_list->nr_consumed_tdmrs;
 	args.r8 = global_keyid;
-	ret = seamcall_prerr(TDH_SYS_CONFIG, &args);
+
+	if (tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_TDXCONNECT) {
+		args.r9 |= TDX_FEATURES0_TDXCONNECT;
+		args.r11 = ktime_get_real_seconds();
+		/* These parameters requires version >= 1 */
+		seamcall_fn = TDH_SYS_CONFIG;
+	}
+
+	ret = seamcall_prerr(seamcall_fn, &args);
 
 	/* Free the array as it is not required anymore. */
 	kfree(tdmr_pa_array);
@@ -1537,6 +1546,11 @@ static int init_tdx_module(void)
 	if (ret)
 		goto err_free_pamts;
 
+	/* configuration to tdx module may change tdx_sysinfo, update it */
+	ret = get_tdx_sys_info(&tdx_sysinfo);
+	if (ret)
+		goto err_reset_pamts;
+
 	/* Config the key of global KeyID on all packages */
 	ret = config_global_keyid();
 	if (ret)

---

## [10] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 09/31] x86/virt/tdx: Move tdx_clflush_page() up in the file*

Prepare to add more callers earlier in this file, so move this
function up in advance.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 22 +++++++++++-----------
 1 file changed, 11 insertions(+), 11 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 0c5d6bdd810f..4fb56bb442f0 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1502,6 +1502,17 @@ static int init_tdmrs(struct tdmr_info_list *tdmr_list)
 	return 0;
 }
 
+/*
+ * The TDX module exposes a CLFLUSH_BEFORE_ALLOC bit to specify whether
+ * a CLFLUSH of pages is required before handing them to the TDX module.
+ * Be conservative and make the code simpler by doing the CLFLUSH
+ * unconditionally.
+ */
+static void tdx_clflush_page(struct page *page)
+{
+	clflush_cache_range(page_to_virt(page), PAGE_SIZE);
+}
+
 static int init_tdx_module(void)
 {
 	int ret;
@@ -1936,17 +1947,6 @@ static inline u64 tdx_tdr_pa(struct tdx_td *td)
 	return page_to_phys(td->tdr_page);
 }
 
-/*
- * The TDX module exposes a CLFLUSH_BEFORE_ALLOC bit to specify whether
- * a CLFLUSH of pages is required before handing them to the TDX module.
- * Be conservative and make the code simpler by doing the CLFLUSH
- * unconditionally.
- */
-static void tdx_clflush_page(struct page *page)
-{
-	clflush_cache_range(page_to_virt(page), PAGE_SIZE);
-}
-
 noinstr u64 tdh_vp_enter(struct tdx_vp *td, struct tdx_module_args *args)
 {
 	args->rcx = td->tdvpr_pa;

---

## [11] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 10/31] x86/virt/tdx: Add extra memory to TDX Module for Extensions*

Adding more memory to TDX Module is the first step to enable Extensions.

Currently, TDX Module memory use is relatively static. But, some new
features (called "TDX Module Extensions") need to use memory more
dynamically. While 'static' here means the kernel provides necessary
amount of memory to TDX Module for its basic functionalities, 'dynamic'
means extra memory is needed only if new optional features are to be
enabled. So add a new memory feeding process backed by a new SEAMCALL
TDH.EXT.MEM.ADD.

The process is mostly the same as adding PAMT. The kernel queries TDX
Module how much memory needed, allocates it, hands it over, and never
gets it back.

TDH.EXT.MEM.ADD uses tdx_page_array to provide control (private) pages
to TDX Module. Introduce a tdx_clflush_page_array() helper to flush
shared cache before SEAMCALL, to avoid shared cache write back damages
these private pages.

For now, TDX Module Extensions consume relatively large amount of
memory (~50MB). Use contiguous page allocation to avoid permanently
fragment too much memory. Print this readout value on TDX Module
Extensions initialization for visibility.

Co-developed-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.h |  1 +
 arch/x86/virt/vmx/tdx/tdx.c | 92 ++++++++++++++++++++++++++++++++++++-
 2 files changed, 91 insertions(+), 2 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 870bb75da3ba..31ccdfcf518c 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -60,6 +60,7 @@
 #define TDH_VP_WR			43
 #define TDH_SYS_CONFIG_V0		45
 #define TDH_SYS_CONFIG			SEAMCALL_LEAF_VER(TDH_SYS_CONFIG_V0, 1)
+#define TDH_EXT_MEM_ADD			61
 
 /* TDX page types */
 #define	PT_NDA		0x0
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 4fb56bb442f0..5fae17c13191 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -560,7 +560,7 @@ static int tdx_alloc_pages_contig(unsigned int nr_pages, struct page **pages,
  * Similar to tdx_page_array_alloc(), after allocating with this
  * function, call tdx_page_array_populate() to populate the tdx_page_array.
  */
-static __maybe_unused struct tdx_page_array *
+static struct tdx_page_array *
 tdx_page_array_alloc_contig(unsigned int nr_pages)
 {
 	return tdx_page_array_alloc(nr_pages, tdx_alloc_pages_contig, NULL);
@@ -643,7 +643,7 @@ EXPORT_SYMBOL_GPL(tdx_page_array_create_iommu_mt);
 #define HPA_LIST_INFO_PFN		GENMASK_U64(51, 12)
 #define HPA_LIST_INFO_LAST_ENTRY	GENMASK_U64(63, 55)
 
-static u64 __maybe_unused hpa_list_info_assign_raw(struct tdx_page_array *array)
+static u64 hpa_list_info_assign_raw(struct tdx_page_array *array)
 {
 	return FIELD_PREP(HPA_LIST_INFO_FIRST_ENTRY, 0) |
 	       FIELD_PREP(HPA_LIST_INFO_PFN,
@@ -1513,6 +1513,94 @@ static void tdx_clflush_page(struct page *page)
 	clflush_cache_range(page_to_virt(page), PAGE_SIZE);
 }
 
+static void tdx_clflush_page_array(struct tdx_page_array *array)
+{
+	for (int i = 0; i < array->nents; i++)
+		tdx_clflush_page(array->pages[array->offset + i]);
+}
+
+static int tdx_ext_mem_add(struct tdx_page_array *ext_mem)
+{
+	struct tdx_module_args args = {
+		.rcx = hpa_list_info_assign_raw(ext_mem),
+	};
+	u64 r;
+
+	tdx_clflush_page_array(ext_mem);
+
+	do {
+		r = seamcall_ret(TDH_EXT_MEM_ADD, &args);
+		cond_resched();
+	} while (r == TDX_INTERRUPTED_RESUMABLE);
+
+	if (r != TDX_SUCCESS)
+		return -EFAULT;
+
+	return 0;
+}
+
+static int tdx_ext_mem_setup(struct tdx_page_array *ext_mem)
+{
+	unsigned int populated, offset = 0;
+	int ret;
+
+	/*
+	 * tdx_page_array's root page can hold 512 HPAs at most. We have ~50MB
+	 * memory to add, re-populate the array and add pages bulk by bulk.
+	 */
+	while (1) {
+		populated = tdx_page_array_populate(ext_mem, offset);
+		if (!populated)
+			break;
+
+		ret = tdx_ext_mem_add(ext_mem);
+		if (ret)
+			return ret;
+
+		offset += populated;
+	}
+
+	return 0;
+}
+
+static int __maybe_unused init_tdx_ext(void)
+{
+	struct tdx_page_array *ext_mem = NULL;
+	unsigned int nr_pages;
+	int ret;
+
+	if (!(tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_EXT))
+		return 0;
+
+	nr_pages = tdx_sysinfo.ext.memory_pool_required_pages;
+	/*
+	 * memory_pool_required_pages == 0 means no need to add more pages,
+	 * skip the memory setup.
+	 */
+	if (nr_pages) {
+		ext_mem = tdx_page_array_alloc_contig(nr_pages);
+		if (!ext_mem)
+			return -ENOMEM;
+
+		ret = tdx_ext_mem_setup(ext_mem);
+		if (ret)
+			goto out_ext_mem;
+	}
+
+	/* Extension memory is never reclaimed once assigned */
+	tdx_page_array_ctrl_leak(ext_mem);
+
+	pr_info("%lu KB allocated for TDX Module Extensions\n",
+		nr_pages * PAGE_SIZE / 1024);
+
+	return 0;
+
+out_ext_mem:
+	tdx_page_array_free(ext_mem);
+
+	return ret;
+}
+
 static int init_tdx_module(void)
 {
 	int ret;

---

## [12] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 11/31] x86/virt/tdx: Make TDX Module initialize Extensions*

After providing all required memory to TDX Module, initialize the
Extensions via TDH.EXT.INIT, and then Extension-SEAMCALLs can be used.

The initialization of Extensions touches the required memory (previously
provided by TDH.EXT.MEM.ADD) in private manner. If failed, flush cache
before freeing these memory, to avoid private cache write back damages
the shared pages.

TDX should use movdir64b to clear private pages when reclaiming them on
older platforms with the X86_BUG_TDX_PW_MCE erratum. For simplicity,
don't expect this errata on any TDX Extensions supported platform. So
TDX Extensions & all features that require TDX Extensions (e.g. TDX
Connect) will not call the clearing helpers.

Note the "ext_required" global metadata specifies if TDH.EXT.INIT call
is needed. If 0, the Extensions are already working, so skip the SEAMCALL.

Co-developed-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.h |  1 +
 arch/x86/virt/vmx/tdx/tdx.c | 45 +++++++++++++++++++++++++++++++++++++
 2 files changed, 46 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 31ccdfcf518c..a26fe94c07ff 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -60,6 +60,7 @@
 #define TDH_VP_WR			43
 #define TDH_SYS_CONFIG_V0		45
 #define TDH_SYS_CONFIG			SEAMCALL_LEAF_VER(TDH_SYS_CONFIG_V0, 1)
+#define TDH_EXT_INIT			60
 #define TDH_EXT_MEM_ADD			61
 
 /* TDX page types */
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 5fae17c13191..4134f92425da 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1519,6 +1519,23 @@ static void tdx_clflush_page_array(struct tdx_page_array *array)
 		tdx_clflush_page(array->pages[array->offset + i]);
 }
 
+/* Initialize the TDX Module Extensions then Extension-SEAMCALLs can be used */
+static int tdx_ext_init(void)
+{
+	struct tdx_module_args args = {};
+	u64 r;
+
+	do {
+		r = seamcall(TDH_EXT_INIT, &args);
+		cond_resched();
+	} while (r == TDX_INTERRUPTED_RESUMABLE);
+
+	if (r != TDX_SUCCESS)
+		return -EFAULT;
+
+	return 0;
+}
+
 static int tdx_ext_mem_add(struct tdx_page_array *ext_mem)
 {
 	struct tdx_module_args args = {
@@ -1572,6 +1589,17 @@ static int __maybe_unused init_tdx_ext(void)
 	if (!(tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_EXT))
 		return 0;
 
+	/*
+	 * With this errata, TDX should use movdir64b to clear private pages
+	 * when reclaiming them. See tdx_quirk_reset_paddr().
+	 *
+	 * Don't expect this errata on any TDX Extensions supported platform.
+	 * All features require TDX Extensions (including TDX Extensions
+	 * itself) will never call tdx_quirk_reset_paddr().
+	 */
+	if (boot_cpu_has_bug(X86_BUG_TDX_PW_MCE))
+		return -ENXIO;
+
 	nr_pages = tdx_sysinfo.ext.memory_pool_required_pages;
 	/*
 	 * memory_pool_required_pages == 0 means no need to add more pages,
@@ -1587,6 +1615,20 @@ static int __maybe_unused init_tdx_ext(void)
 			goto out_ext_mem;
 	}
 
+	/*
+	 * ext_required == 0 means no need to call TDH.EXT.INIT, the Extensions
+	 * are already working.
+	 */
+	if (tdx_sysinfo.ext.ext_required) {
+		ret = tdx_ext_init();
+		/*
+		 * Some pages may have been touched by the TDX module.
+		 * Flush cache before returning these pages to kernel.
+		 */
+		if (ret)
+			goto out_flush;
+	}
+
 	/* Extension memory is never reclaimed once assigned */
 	tdx_page_array_ctrl_leak(ext_mem);
 
@@ -1595,6 +1637,9 @@ static int __maybe_unused init_tdx_ext(void)
 
 	return 0;
 
+out_flush:
+	if (ext_mem)
+		wbinvd_on_all_cpus();
 out_ext_mem:
 	tdx_page_array_free(ext_mem);

---

## [13] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 12/31] x86/virt/tdx: Enable the Extensions after basic TDX Module init*

The detailed initialization flow for TDX Module Extensions has been
fully implemented. Enable the flow after basic TDX Module
initialization.

Theoretically, the Extensions can be initialized later when the first
usage of the Extension-SEAMCALL comes. That would save or postpone the
usage of ~50M memory. But it isn't worth the complexity, the needs for
Extensions are vast but the savings are little for a typical TDX capable
system (about 0.001% of memory). So just enable it along with the basic
TDX.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 6 +++++-
 1 file changed, 5 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 4134f92425da..0e1ad793e648 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1580,7 +1580,7 @@ static int tdx_ext_mem_setup(struct tdx_page_array *ext_mem)
 	return 0;
 }
 
-static int __maybe_unused init_tdx_ext(void)
+static int init_tdx_ext(void)
 {
 	struct tdx_page_array *ext_mem = NULL;
 	unsigned int nr_pages;
@@ -1705,6 +1705,10 @@ static int init_tdx_module(void)
 	if (ret)
 		goto err_reset_pamts;
 
+	ret = init_tdx_ext();
+	if (ret)
+		goto err_reset_pamts;
+
 	pr_info("%lu KB allocated for PAMT\n", tdmrs_count_pamt_kb(&tdx_tdmr_list));
 
 out_put_tdxmem:

---

## [14] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 13/31] x86/virt/tdx: Extend tdx_clflush_page() to handle compound pages*

Use page_size() to correctly flush the range that a compound page
covers.

Recall that TDX Module requires VMM to provide IOMMU metadata known as
IOMMU_MT, which contains some multi-order pages. Like all other
metadata, TDX Module will convert these multi-order pages to private so
VMM should flush the shared cache beforehand. Extend tdx_clflush_page()
to handle this case.

The usage of tdx_clflush_page() for IOMMU_MT will be introduced later,
but the change stands as a valid improvement on its own.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 0e1ad793e648..e7d47fbe7057 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1510,7 +1510,7 @@ static int init_tdmrs(struct tdmr_info_list *tdmr_list)
  */
 static void tdx_clflush_page(struct page *page)
 {
-	clflush_cache_range(page_to_virt(page), PAGE_SIZE);
+	clflush_cache_range(page_to_virt(page), page_size(page));
 }
 
 static void tdx_clflush_page_array(struct tdx_page_array *array)

---

## [15] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 14/31] PCI/TSM: Report active IDE streams per host bridge*

From: Dan Williams <dan.j.williams@intel.com>

The first attempt at an ABI for this failed to account for naming
collisions across host bridges:

Commit a4438f06b1db ("PCI/TSM: Report active IDE streams")

Revive this ABI with a per host bridge link that appears at first stream
creation for a given host bridge and disappears after the last stream is
removed.

For systems with many host bridge objects it allows:

    ls /sys/class/tsm/tsmN/pci*/stream*

...to find all the host bridges with active streams without first iterating
over all host bridges. Yilun notes that is handy to have this short cut [1]
and from an administrator perspective it helps with inventory for
constrained stream resources.

Link: http://lore.kernel.org/aXLtILY85oMU5qlb@yilunxu-OptiPlex-7050 [1]
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 Documentation/ABI/testing/sysfs-class-tsm | 13 +++
 include/linux/pci-ide.h                   |  2 +
 include/linux/tsm.h                       |  3 +
 drivers/pci/ide.c                         |  4 +
 drivers/virt/coco/tsm-core.c              | 97 +++++++++++++++++++++++
 5 files changed, 119 insertions(+)

diff --git a/Documentation/ABI/testing/sysfs-class-tsm b/Documentation/ABI/testing/sysfs-class-tsm
index 2949468deaf7..1ddb8f357961 100644
--- a/Documentation/ABI/testing/sysfs-class-tsm
+++ b/Documentation/ABI/testing/sysfs-class-tsm
@@ -7,3 +7,16 @@ Description:
 		signals when the PCI layer is able to support establishment of
 		link encryption and other device-security features coordinated
 		through a platform tsm.
+
+What:		/sys/class/tsm/tsmN/pciDDDD:BB
+Contact:	linux-pci@vger.kernel.org
+Description:
+		(RO) When a PCIe host bridge has established a secure connection
+		via a TSM to an endpoint, this symlink appears. It facilitates a
+		TSM instance scoped view of PCIe Link Encryption and Secure
+		Session resource consumption across host bridges. The symlink
+		appears when a host bridge has 1 or more IDE streams established
+		with this TSM, and disappears when that number returns to 0. See
+		Documentation/ABI/testing/sysfs-devices-pci-host-bridge for the
+		description of the pciDDDD:BB/streamH.R.E symlink and the
+		pciDDDD:BB/available_secure_streams attribute.
diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
index ae07d9f699c0..381a1bf22a95 100644
--- a/include/linux/pci-ide.h
+++ b/include/linux/pci-ide.h
@@ -82,6 +82,7 @@ struct pci_ide_regs {
  * @host_bridge_stream: allocated from host bridge @ide_stream_ida pool
  * @stream_id: unique Stream ID (within Partner Port pairing)
  * @name: name of the established Selective IDE Stream in sysfs
+ * @tsm_dev: For TSM established IDE, the TSM device context
  *
  * Negative @stream_id values indicate "uninitialized" on the
  * expectation that with TSM established IDE the TSM owns the stream_id
@@ -93,6 +94,7 @@ struct pci_ide {
 	u8 host_bridge_stream;
 	int stream_id;
 	const char *name;
+	struct tsm_dev *tsm_dev;
 };
 
 /*
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 381c53244c83..7f72a154b6b2 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -123,4 +123,7 @@ int tsm_report_unregister(const struct tsm_report_ops *ops);
 struct tsm_dev *tsm_register(struct device *parent, struct pci_tsm_ops *ops);
 void tsm_unregister(struct tsm_dev *tsm_dev);
 struct tsm_dev *find_tsm_dev(int id);
+struct pci_ide;
+int tsm_ide_stream_register(struct pci_ide *ide);
+void tsm_ide_stream_unregister(struct pci_ide *ide);
 #endif /* __TSM_H */
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index be74e8f0ae21..b35e8aba7ecb 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -11,6 +11,7 @@
 #include <linux/pci_regs.h>
 #include <linux/slab.h>
 #include <linux/sysfs.h>
+#include <linux/tsm.h>
 
 #include "pci.h"
 
@@ -372,6 +373,9 @@ void pci_ide_stream_release(struct pci_ide *ide)
 	if (ide->partner[PCI_IDE_EP].enable)
 		pci_ide_stream_disable(pdev, ide);
 
+	if (ide->tsm_dev)
+		tsm_ide_stream_unregister(ide);
+
 	if (ide->partner[PCI_IDE_RP].setup)
 		pci_ide_stream_teardown(rp, ide);
 
diff --git a/drivers/virt/coco/tsm-core.c b/drivers/virt/coco/tsm-core.c
index 98dcf7d836df..ece7cd7ea9d8 100644
--- a/drivers/virt/coco/tsm-core.c
+++ b/drivers/virt/coco/tsm-core.c
@@ -4,10 +4,12 @@
 #define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
 
 #include <linux/tsm.h>
+#include <linux/pci.h>
 #include <linux/device.h>
 #include <linux/module.h>
 #include <linux/cleanup.h>
 #include <linux/pci-tsm.h>
+#include <linux/pci-ide.h>
 
 static struct class *tsm_class;
 static DEFINE_IDA(tsm_ida);
@@ -104,6 +106,100 @@ void tsm_unregister(struct tsm_dev *tsm_dev)
 }
 EXPORT_SYMBOL_GPL(tsm_unregister);
 
+static DEFINE_XARRAY(tsm_ide_streams);
+static DEFINE_MUTEX(tsm_ide_streams_lock);
+
+/* tracker for the bridge symlink when the bridge has any streams */
+struct tsm_ide_stream {
+	struct tsm_dev *tsm_dev;
+	struct pci_host_bridge *bridge;
+	struct kref kref;
+};
+
+static struct tsm_ide_stream *create_streams(struct tsm_dev *tsm_dev,
+					    struct pci_host_bridge *bridge)
+{
+	int rc;
+
+	struct tsm_ide_stream *streams __free(kfree) =
+		kzalloc(sizeof(*streams), GFP_KERNEL);
+	if (!streams)
+		return NULL;
+
+	streams->tsm_dev = tsm_dev;
+	streams->bridge = bridge;
+	kref_init(&streams->kref);
+	rc = xa_insert(&tsm_ide_streams, (unsigned long)bridge, streams,
+		       GFP_KERNEL);
+	if (rc)
+		return NULL;
+
+	rc = sysfs_create_link(&tsm_dev->dev.kobj, &bridge->dev.kobj,
+			       dev_name(&bridge->dev));
+	if (rc) {
+		xa_erase(&tsm_ide_streams, (unsigned long)bridge);
+		return NULL;
+	}
+
+	return no_free_ptr(streams);
+}
+
+int tsm_ide_stream_register(struct pci_ide *ide)
+{
+	struct tsm_ide_stream *streams;
+	struct pci_dev *pdev = ide->pdev;
+	struct pci_tsm *tsm = pdev->tsm;
+	struct tsm_dev *tsm_dev = tsm->tsm_dev;
+	struct pci_host_bridge *bridge = pci_find_host_bridge(pdev->bus);
+
+	guard(mutex)(&tsm_ide_streams_lock);
+	streams = xa_load(&tsm_ide_streams, (unsigned long)bridge);
+	if (streams)
+		kref_get(&streams->kref);
+	else
+		streams = create_streams(tsm_dev, bridge);
+
+	if (!streams)
+		return -ENOMEM;
+	ide->tsm_dev = tsm_dev;
+
+	return 0;
+}
+EXPORT_SYMBOL_GPL(tsm_ide_stream_register);
+
+static void destroy_streams(struct kref *kref)
+{
+	struct tsm_ide_stream *streams =
+		container_of(kref, struct tsm_ide_stream, kref);
+	struct tsm_dev *tsm_dev = streams->tsm_dev;
+	struct pci_host_bridge *bridge = streams->bridge;
+
+	lockdep_assert_held(&tsm_ide_streams_lock);
+	sysfs_remove_link(&tsm_dev->dev.kobj, dev_name(&bridge->dev));
+	xa_erase(&tsm_ide_streams, (unsigned long)bridge);
+	kfree(streams);
+}
+
+void tsm_ide_stream_unregister(struct pci_ide *ide)
+{
+	struct tsm_ide_stream *streams;
+	struct tsm_dev *tsm_dev = ide->tsm_dev;
+	struct pci_dev *pdev = ide->pdev;
+	struct pci_host_bridge *bridge = pci_find_host_bridge(pdev->bus);
+
+	guard(mutex)(&tsm_ide_streams_lock);
+	streams = xa_load(&tsm_ide_streams, (unsigned long)bridge);
+	/* catch API abuse */
+	if (dev_WARN_ONCE(&tsm_dev->dev,
+			  !streams || streams->tsm_dev != tsm_dev,
+			  "no IDE streams associated with %s\n",
+			  dev_name(&bridge->dev)))
+		return;
+	kref_put(&streams->kref, destroy_streams);
+	ide->tsm_dev = NULL;
+}
+EXPORT_SYMBOL_GPL(tsm_ide_stream_unregister);
+
 static void tsm_release(struct device *dev)
 {
 	struct tsm_dev *tsm_dev = container_of(dev, typeof(*tsm_dev), dev);
@@ -126,6 +222,7 @@ module_init(tsm_init)
 static void __exit tsm_exit(void)
 {
 	class_destroy(tsm_class);
+	xa_destroy(&tsm_ide_streams);
 }
 module_exit(tsm_exit)

---

## [16] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 15/31] coco/tdx-host: Introduce a "tdx_host" device*

From: Chao Gao <chao.gao@intel.com>

TDX depends on a platform firmware module that is invoked via instructions
similar to vmenter (i.e. enter into a new privileged "root-mode" context to
manage private memory and private device mechanisms). It is a software
construct that depends on the CPU vmxon state to enable invocation of
TDX module ABIs. Unlike other Trusted Execution Environment (TEE) platform
implementations that employ a firmware module running on a PCI device with
an MMIO mailbox for communication, TDX has no hardware device to point to
as the TEE Secure Manager (TSM).

Create a virtual device not only to align with other implementations but
also to make it easier to

 - expose metadata (e.g., TDX module version, seamldr version etc) to
   the userspace as device attributes

 - implement firmware uploader APIs which are tied to a device. This is
   needed to support TDX module runtime updates

 - enable TDX Connect which will share a common infrastructure with other
   platform implementations. In the TDX Connect context, every
   architecture has a TSM, represented by a PCIe or virtual device. The
   new "tdx_host" device will serve the TSM role.

A faux device is used for TDX because the TDX module is singular within
the system and lacks associated platform resources. Using a faux device
eliminates the need to create a stub bus.

The call to tdx_get_sysinfo() ensures that the TDX module is ready to
provide services.

Note that AMD has a PCI device for the PSP for SEV and ARM CCA will
likely have a faux device [1].

Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Link: https://lore.kernel.org/all/2025073035-bulginess-rematch-b92e@gregkh/ # [1]
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/virt/coco/Kconfig             |  2 ++
 drivers/virt/coco/tdx-host/Kconfig    | 10 +++++++
 drivers/virt/coco/Makefile            |  1 +
 drivers/virt/coco/tdx-host/Makefile   |  1 +
 arch/x86/virt/vmx/tdx/tdx.c           |  2 +-
 drivers/virt/coco/tdx-host/tdx-host.c | 43 +++++++++++++++++++++++++++
 6 files changed, 58 insertions(+), 1 deletion(-)
 create mode 100644 drivers/virt/coco/tdx-host/Kconfig
 create mode 100644 drivers/virt/coco/tdx-host/Makefile
 create mode 100644 drivers/virt/coco/tdx-host/tdx-host.c

diff --git a/drivers/virt/coco/Kconfig b/drivers/virt/coco/Kconfig
index df1cfaf26c65..f7691f64fbe3 100644
--- a/drivers/virt/coco/Kconfig
+++ b/drivers/virt/coco/Kconfig
@@ -17,5 +17,7 @@ source "drivers/virt/coco/arm-cca-guest/Kconfig"
 source "drivers/virt/coco/guest/Kconfig"
 endif
 
+source "drivers/virt/coco/tdx-host/Kconfig"
+
 config TSM
 	bool
diff --git a/drivers/virt/coco/tdx-host/Kconfig b/drivers/virt/coco/tdx-host/Kconfig
new file mode 100644
index 000000000000..d35d85ef91c0
--- /dev/null
+++ b/drivers/virt/coco/tdx-host/Kconfig
@@ -0,0 +1,10 @@
+config TDX_HOST_SERVICES
+	tristate "TDX Host Services Driver"
+	depends on INTEL_TDX_HOST
+	default m
+	help
+	  Enable access to TDX host services like module update and
+	  extensions (e.g. TDX Connect).
+
+	  Say y or m if enabling support for confidential virtual machine
+	  support (CONFIG_INTEL_TDX_HOST). The module is called tdx_host.ko.
diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
index cb52021912b3..b323b0ae4f82 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -6,6 +6,7 @@ obj-$(CONFIG_EFI_SECRET)	+= efi_secret/
 obj-$(CONFIG_ARM_PKVM_GUEST)	+= pkvm-guest/
 obj-$(CONFIG_SEV_GUEST)		+= sev-guest/
 obj-$(CONFIG_INTEL_TDX_GUEST)	+= tdx-guest/
+obj-$(CONFIG_INTEL_TDX_HOST)	+= tdx-host/
 obj-$(CONFIG_ARM_CCA_GUEST)	+= arm-cca-guest/
 obj-$(CONFIG_TSM) 		+= tsm-core.o
 obj-$(CONFIG_TSM_GUEST)		+= guest/
diff --git a/drivers/virt/coco/tdx-host/Makefile b/drivers/virt/coco/tdx-host/Makefile
new file mode 100644
index 000000000000..e61e749a8dff
--- /dev/null
+++ b/drivers/virt/coco/tdx-host/Makefile
@@ -0,0 +1 @@
+obj-$(CONFIG_TDX_HOST_SERVICES) += tdx-host.o
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index e7d47fbe7057..cd0948794b6c 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2057,7 +2057,7 @@ const struct tdx_sys_info *tdx_get_sysinfo(void)
 
 	return p;
 }
-EXPORT_SYMBOL_FOR_KVM(tdx_get_sysinfo);
+EXPORT_SYMBOL_FOR_MODULES(tdx_get_sysinfo, "kvm-intel,tdx-host");
 
 u32 tdx_get_nr_guest_keyids(void)
 {
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
new file mode 100644
index 000000000000..c77885392b09
--- /dev/null
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -0,0 +1,43 @@
+// SPDX-License-Identifier: GPL-2.0
+/*
+ * TDX host user interface driver
+ *
+ * Copyright (C) 2025 Intel Corporation
+ */
+
+#include <linux/device/faux.h>
+#include <linux/module.h>
+#include <linux/mod_devicetable.h>
+
+#include <asm/cpu_device_id.h>
+#include <asm/tdx.h>
+
+static const struct x86_cpu_id tdx_host_ids[] = {
+	X86_MATCH_FEATURE(X86_FEATURE_TDX_HOST_PLATFORM, NULL),
+	{}
+};
+MODULE_DEVICE_TABLE(x86cpu, tdx_host_ids);
+
+static struct faux_device *fdev;
+
+static int __init tdx_host_init(void)
+{
+	if (!x86_match_cpu(tdx_host_ids) || !tdx_get_sysinfo())
+		return -ENODEV;
+
+	fdev = faux_device_create(KBUILD_MODNAME, NULL, NULL);
+	if (!fdev)
+		return -ENODEV;
+
+	return 0;
+}
+module_init(tdx_host_init);
+
+static void __exit tdx_host_exit(void)
+{
+	faux_device_destroy(fdev);
+}
+module_exit(tdx_host_exit);
+
+MODULE_DESCRIPTION("TDX Host Services");
+MODULE_LICENSE("GPL");

---

## [17] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 16/31] coco/tdx-host: Support Link TSM for TDX host*

Register a Link TSM instance to support host side TSM operations for
TDISP, when the TDX Connect support bit is set by TDX Module in
tdx_feature0.

This is the main purpose of an independent tdx-host module out of TDX
core. Recall that a TEE Security Manager (TSM) is a platform agent that
speaks the TEE Device Interface Security Protocol (TDISP) to PCIe
devices and manages private memory resources for the platform. An
independent tdx-host module allows for device-security enumeration and
initialization flows to be deferred from other TDX Module initialization
requirements. Crucially, when / if TDX Module init moves earlier in x86
initialization flow this driver is still guaranteed to run after IOMMU
and PCI init (i.e. subsys_initcall() vs device_initcall()).

The ability to unload the module, or unbind the driver is also useful
for debug and coarse grained transitioning between PCI TSM operation and
PCI CMA operation (native kernel PCI device authentication).

For now only verify TDX Connect support in TDX Module and enable TDX
Module Extentions. The TSM support are basic boilerplate with operation
flows to be added later.

Co-developed-by: Dan Williams <dan.j.williams@intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/virt/coco/tdx-host/Kconfig    |   5 +
 drivers/virt/coco/tdx-host/tdx-host.c | 138 +++++++++++++++++++++++++-
 2 files changed, 141 insertions(+), 2 deletions(-)

diff --git a/drivers/virt/coco/tdx-host/Kconfig b/drivers/virt/coco/tdx-host/Kconfig
index d35d85ef91c0..32add81b7d56 100644
--- a/drivers/virt/coco/tdx-host/Kconfig
+++ b/drivers/virt/coco/tdx-host/Kconfig
@@ -8,3 +8,8 @@ config TDX_HOST_SERVICES
 
 	  Say y or m if enabling support for confidential virtual machine
 	  support (CONFIG_INTEL_TDX_HOST). The module is called tdx_host.ko.
+
+config TDX_CONNECT
+	def_bool y
+	depends on TDX_HOST_SERVICES
+	depends on PCI_TSM
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index c77885392b09..5ea35a514865 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -8,9 +8,13 @@
 #include <linux/device/faux.h>
 #include <linux/module.h>
 #include <linux/mod_devicetable.h>
+#include <linux/pci.h>
+#include <linux/pci-tsm.h>
+#include <linux/tsm.h>
 
 #include <asm/cpu_device_id.h>
 #include <asm/tdx.h>
+#include <asm/tdx_global_metadata.h>
 
 static const struct x86_cpu_id tdx_host_ids[] = {
 	X86_MATCH_FEATURE(X86_FEATURE_TDX_HOST_PLATFORM, NULL),
@@ -18,14 +22,144 @@ static const struct x86_cpu_id tdx_host_ids[] = {
 };
 MODULE_DEVICE_TABLE(x86cpu, tdx_host_ids);
 
+/*
+ * The global pointer is for features which won't be affected by tdx_sysinfo
+ * change after TDX Module update, e.g. TDX Connect, so could cache it. A
+ * counterexample is the TDX Module version.
+ */
+static const struct tdx_sys_info *tdx_sysinfo;
+
+struct tdx_tsm_link {
+	struct pci_tsm_pf0 pci;
+};
+
+static struct tdx_tsm_link *to_tdx_tsm_link(struct pci_tsm *tsm)
+{
+	return container_of(tsm, struct tdx_tsm_link, pci.base_tsm);
+}
+
+static int tdx_tsm_link_connect(struct pci_dev *pdev)
+{
+	return -ENXIO;
+}
+
+static void tdx_tsm_link_disconnect(struct pci_dev *pdev)
+{
+}
+
+static struct pci_tsm *tdx_tsm_link_pf0_probe(struct tsm_dev *tsm_dev,
+					      struct pci_dev *pdev)
+{
+	int rc;
+
+	struct tdx_tsm_link *tlink __free(kfree) = kzalloc_obj(*tlink);
+	if (!tlink)
+		return NULL;
+
+	rc = pci_tsm_pf0_constructor(pdev, &tlink->pci, tsm_dev);
+	if (rc)
+		return NULL;
+
+	return &no_free_ptr(tlink)->pci.base_tsm;
+}
+
+static void tdx_tsm_link_pf0_remove(struct pci_tsm *tsm)
+{
+	struct tdx_tsm_link *tlink = to_tdx_tsm_link(tsm);
+
+	pci_tsm_pf0_destructor(&tlink->pci);
+	kfree(tlink);
+}
+
+static struct pci_tsm *tdx_tsm_link_fn_probe(struct tsm_dev *tsm_dev,
+					     struct pci_dev *pdev)
+{
+	int rc;
+
+	struct pci_tsm *pci_tsm __free(kfree) = kzalloc_obj(*pci_tsm);
+	if (!pci_tsm)
+		return NULL;
+
+	rc = pci_tsm_link_constructor(pdev, pci_tsm, tsm_dev);
+	if (rc)
+		return NULL;
+
+	return no_free_ptr(pci_tsm);
+}
+
+static struct pci_tsm *tdx_tsm_link_probe(struct tsm_dev *tsm_dev,
+					  struct pci_dev *pdev)
+{
+	if (is_pci_tsm_pf0(pdev))
+		return tdx_tsm_link_pf0_probe(tsm_dev, pdev);
+
+	return tdx_tsm_link_fn_probe(tsm_dev, pdev);
+}
+
+static void tdx_tsm_link_remove(struct pci_tsm *tsm)
+{
+	if (is_pci_tsm_pf0(tsm->pdev)) {
+		tdx_tsm_link_pf0_remove(tsm);
+		return;
+	}
+
+	/* for sub-functions */
+	kfree(tsm);
+}
+
+static struct pci_tsm_ops tdx_tsm_link_ops = {
+	.probe = tdx_tsm_link_probe,
+	.remove = tdx_tsm_link_remove,
+	.connect = tdx_tsm_link_connect,
+	.disconnect = tdx_tsm_link_disconnect,
+};
+
+static void unregister_link_tsm(void *link)
+{
+	tsm_unregister(link);
+}
+
+static int __maybe_unused tdx_connect_init(struct device *dev)
+{
+	struct tsm_dev *link;
+	int ret;
+
+	if (!IS_ENABLED(CONFIG_TDX_CONNECT))
+		return 0;
+
+	if (!(tdx_sysinfo->features.tdx_features0 & TDX_FEATURES0_TDXCONNECT))
+		return 0;
+
+	link = tsm_register(dev, &tdx_tsm_link_ops);
+	if (IS_ERR(link))
+		return dev_err_probe(dev, PTR_ERR(link),
+				     "failed to register TSM\n");
+
+	return devm_add_action_or_reset(dev, unregister_link_tsm, link);
+}
+
+static int tdx_host_probe(struct faux_device *fdev)
+{
+	/* TODO: do tdx_connect_init() when it is fully implemented. */
+	return 0;
+}
+
+static struct faux_device_ops tdx_host_ops = {
+	.probe = tdx_host_probe,
+};
+
 static struct faux_device *fdev;
 
 static int __init tdx_host_init(void)
 {
-	if (!x86_match_cpu(tdx_host_ids) || !tdx_get_sysinfo())
+	if (!x86_match_cpu(tdx_host_ids))
+		return -ENODEV;
+
+	tdx_sysinfo = tdx_get_sysinfo();
+	if (!tdx_sysinfo)
 		return -ENODEV;
 
-	fdev = faux_device_create(KBUILD_MODNAME, NULL, NULL);
+	fdev = faux_device_create(KBUILD_MODNAME, NULL, &tdx_host_ops);
 	if (!fdev)
 		return -ENODEV;

---

## [18] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 17/31] acpi: Add KEYP support to fw_table parsing*

From: Dave Jiang <dave.jiang@intel.com>

KEYP ACPI table can be parsed using the common fw_table handlers. Add
additional support to detect and parse the table.

Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dave Jiang <dave.jiang@intel.com>
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>
---
 include/linux/acpi.h     |  3 +++
 include/linux/fw_table.h |  1 +
 drivers/acpi/tables.c    | 12 +++++++++++-
 lib/fw_table.c           |  9 +++++++++
 4 files changed, 24 insertions(+), 1 deletion(-)

diff --git a/include/linux/acpi.h b/include/linux/acpi.h
index 4d2f0bed7a06..e5b51bd46600 100644
--- a/include/linux/acpi.h
+++ b/include/linux/acpi.h
@@ -247,6 +247,9 @@ int acpi_table_parse_madt(enum acpi_madt_type id,
 int __init_or_acpilib
 acpi_table_parse_cedt(enum acpi_cedt_type id,
 		      acpi_tbl_entry_handler_arg handler_arg, void *arg);
+int __init_or_acpilib
+acpi_table_parse_keyp(enum acpi_keyp_type id,
+		      acpi_tbl_entry_handler_arg handler_arg, void *arg);
 
 int acpi_parse_mcfg (struct acpi_table_header *header);
 void acpi_table_print_madt_entry (struct acpi_subtable_header *madt);
diff --git a/include/linux/fw_table.h b/include/linux/fw_table.h
index 9bd605b87c4c..293252cb0b7e 100644
--- a/include/linux/fw_table.h
+++ b/include/linux/fw_table.h
@@ -36,6 +36,7 @@ union acpi_subtable_headers {
 	struct acpi_prmt_module_header prmt;
 	struct acpi_cedt_header cedt;
 	struct acpi_cdat_header cdat;
+	struct acpi_keyp_common_header keyp;
 };
 
 int acpi_parse_entries_array(char *id, unsigned long table_size,
diff --git a/drivers/acpi/tables.c b/drivers/acpi/tables.c
index 4286e4af1092..8dc60632faf3 100644
--- a/drivers/acpi/tables.c
+++ b/drivers/acpi/tables.c
@@ -299,6 +299,16 @@ acpi_table_parse_cedt(enum acpi_cedt_type id,
 }
 EXPORT_SYMBOL_ACPI_LIB(acpi_table_parse_cedt);
 
+int __init_or_acpilib
+acpi_table_parse_keyp(enum acpi_keyp_type id,
+		      acpi_tbl_entry_handler_arg handler_arg, void *arg)
+{
+	return __acpi_table_parse_entries(ACPI_SIG_KEYP,
+					  sizeof(struct acpi_table_keyp), id,
+					  NULL, handler_arg, arg, 0);
+}
+EXPORT_SYMBOL_ACPI_LIB(acpi_table_parse_keyp);
+
 int __init acpi_table_parse_entries(char *id, unsigned long table_size,
 				    int entry_id,
 				    acpi_tbl_entry_handler handler,
@@ -408,7 +418,7 @@ static const char table_sigs[][ACPI_NAMESEG_SIZE] __nonstring_array __initconst
 	ACPI_SIG_PSDT, ACPI_SIG_RSDT, ACPI_SIG_XSDT, ACPI_SIG_SSDT,
 	ACPI_SIG_IORT, ACPI_SIG_NFIT, ACPI_SIG_HMAT, ACPI_SIG_PPTT,
 	ACPI_SIG_NHLT, ACPI_SIG_AEST, ACPI_SIG_CEDT, ACPI_SIG_AGDI,
-	ACPI_SIG_NBFT, ACPI_SIG_SWFT, ACPI_SIG_MPAM};
+	ACPI_SIG_NBFT, ACPI_SIG_SWFT, ACPI_SIG_MPAM, ACPI_SIG_KEYP};
 
 #define ACPI_HEADER_SIZE sizeof(struct acpi_table_header)
 
diff --git a/lib/fw_table.c b/lib/fw_table.c
index 16291814450e..147e3895e94c 100644
--- a/lib/fw_table.c
+++ b/lib/fw_table.c
@@ -20,6 +20,7 @@ enum acpi_subtable_type {
 	ACPI_SUBTABLE_PRMT,
 	ACPI_SUBTABLE_CEDT,
 	CDAT_SUBTABLE,
+	ACPI_SUBTABLE_KEYP,
 };
 
 struct acpi_subtable_entry {
@@ -41,6 +42,8 @@ acpi_get_entry_type(struct acpi_subtable_entry *entry)
 		return entry->hdr->cedt.type;
 	case CDAT_SUBTABLE:
 		return entry->hdr->cdat.type;
+	case ACPI_SUBTABLE_KEYP:
+		return entry->hdr->keyp.type;
 	}
 	return 0;
 }
@@ -61,6 +64,8 @@ acpi_get_entry_length(struct acpi_subtable_entry *entry)
 		__le16 length = (__force __le16)entry->hdr->cdat.length;
 
 		return le16_to_cpu(length);
+	case ACPI_SUBTABLE_KEYP:
+		return entry->hdr->keyp.length;
 	}
 	}
 	return 0;
@@ -80,6 +85,8 @@ acpi_get_subtable_header_length(struct acpi_subtable_entry *entry)
 		return sizeof(entry->hdr->cedt);
 	case CDAT_SUBTABLE:
 		return sizeof(entry->hdr->cdat);
+	case ACPI_SUBTABLE_KEYP:
+		return sizeof(entry->hdr->keyp);
 	}
 	return 0;
 }
@@ -95,6 +102,8 @@ acpi_get_subtable_type(char *id)
 		return ACPI_SUBTABLE_CEDT;
 	if (strncmp(id, ACPI_SIG_CDAT, 4) == 0)
 		return CDAT_SUBTABLE;
+	if (strncmp(id, ACPI_SIG_KEYP, 4) == 0)
+		return ACPI_SUBTABLE_KEYP;
 	return ACPI_SUBTABLE_COMMON;
 }

---

## [19] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 18/31] iommu/vt-d: Cache max domain ID to avoid redundant calculation*

From: Lu Baolu <baolu.lu@linux.intel.com>

The cap_ndoms() helper calculates the maximum available domain ID from
the value of capability register, which can be inefficient if called
repeatedly. Cache the maximum supported domain ID in max_domain_id field
during initialization to avoid redundant calls to cap_ndoms() throughout
the IOMMU driver.

No functionality change.

Signed-off-by: Lu Baolu <baolu.lu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/iommu/intel/iommu.h |  1 +
 drivers/iommu/intel/dmar.c  |  1 +
 drivers/iommu/intel/iommu.c | 10 +++++-----
 3 files changed, 7 insertions(+), 5 deletions(-)

diff --git a/drivers/iommu/intel/iommu.h b/drivers/iommu/intel/iommu.h
index 599913fb65d5..4a21ab6a311d 100644
--- a/drivers/iommu/intel/iommu.h
+++ b/drivers/iommu/intel/iommu.h
@@ -705,6 +705,7 @@ struct intel_iommu {
 	/* mutex to protect domain_ida */
 	struct mutex	did_lock;
 	struct ida	domain_ida; /* domain id allocator */
+	unsigned long	max_domain_id;
 	unsigned long	*copied_tables; /* bitmap of copied tables */
 	spinlock_t	lock; /* protect context, domain ids */
 	struct root_entry *root_entry; /* virtual address */
diff --git a/drivers/iommu/intel/dmar.c b/drivers/iommu/intel/dmar.c
index d68c06025cac..93efd1a5dc5b 100644
--- a/drivers/iommu/intel/dmar.c
+++ b/drivers/iommu/intel/dmar.c
@@ -1099,6 +1099,7 @@ static int alloc_iommu(struct dmar_drhd_unit *drhd)
 	spin_lock_init(&iommu->lock);
 	ida_init(&iommu->domain_ida);
 	mutex_init(&iommu->did_lock);
+	iommu->max_domain_id = cap_ndoms(iommu->cap);
 
 	ver = readl(iommu->reg + DMAR_VER_REG);
 	pr_info("%s: reg_base_addr %llx ver %d:%d cap %llx ecap %llx\n",
diff --git a/drivers/iommu/intel/iommu.c b/drivers/iommu/intel/iommu.c
index ef7613b177b9..9a57f78647ed 100644
--- a/drivers/iommu/intel/iommu.c
+++ b/drivers/iommu/intel/iommu.c
@@ -1043,7 +1043,7 @@ int domain_attach_iommu(struct dmar_domain *domain, struct intel_iommu *iommu)
 	}
 
 	num = ida_alloc_range(&iommu->domain_ida, IDA_START_DID,
-			      cap_ndoms(iommu->cap) - 1, GFP_KERNEL);
+			      iommu->max_domain_id - 1, GFP_KERNEL);
 	if (num < 0) {
 		pr_err("%s: No free domain ids\n", iommu->name);
 		goto err_unlock;
@@ -1107,7 +1107,7 @@ static void copied_context_tear_down(struct intel_iommu *iommu,
 	did_old = context_domain_id(context);
 	context_clear_entry(context);
 
-	if (did_old < cap_ndoms(iommu->cap)) {
+	if (did_old < iommu->max_domain_id) {
 		iommu->flush.flush_context(iommu, did_old,
 					   PCI_DEVID(bus, devfn),
 					   DMA_CCMD_MASK_NOBIT,
@@ -1505,7 +1505,7 @@ static int copy_context_table(struct intel_iommu *iommu,
 			continue;
 
 		did = context_domain_id(&ce);
-		if (did >= 0 && did < cap_ndoms(iommu->cap))
+		if (did >= 0 && did < iommu->max_domain_id)
 			ida_alloc_range(&iommu->domain_ida, did, did, GFP_KERNEL);
 
 		set_context_copied(iommu, bus, devfn);
@@ -2425,7 +2425,7 @@ static ssize_t domains_supported_show(struct device *dev,
 				      struct device_attribute *attr, char *buf)
 {
 	struct intel_iommu *iommu = dev_to_intel_iommu(dev);
-	return sysfs_emit(buf, "%ld\n", cap_ndoms(iommu->cap));
+	return sysfs_emit(buf, "%ld\n", iommu->max_domain_id);
 }
 static DEVICE_ATTR_RO(domains_supported);
 
@@ -2436,7 +2436,7 @@ static ssize_t domains_used_show(struct device *dev,
 	unsigned int count = 0;
 	int id;
 
-	for (id = 0; id < cap_ndoms(iommu->cap); id++)
+	for (id = 0; id < iommu->max_domain_id; id++)
 		if (ida_exists(&iommu->domain_ida, id))
 			count++;

---

## [20] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 19/31] iommu/vt-d: Reserve the MSB domain ID bit for the TDX module*

From: Lu Baolu <baolu.lu@linux.intel.com>

The Intel TDX Connect Architecture Specification defines some enhancements
for the VT-d architecture to introduce IOMMU support for TEE-IO requests.
Section 2.2, 'Trusted DMA' states that:

"I/O TLB and DID Isolation – When IOMMU is enabled to support TDX
Connect, the IOMMU restricts the VMM’s DID setting, reserving the MSB bit
for the TDX module. The TDX module always sets this reserved bit on the
trusted DMA table. IOMMU tags IOTLB, PASID cache, and context entries to
indicate whether they were created from TEE-IO transactions, ensuring
isolation between TEE and non-TEE requests in translation caches."

Reserve the MSB in the domain ID for the TDX module's use if the
enhancement is required, which is detected if the ECAP.TDXCS bit in the
VT-d extended capability register is set and the TVM Usable field of the
ACPI KEYP table is set.

Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Lu Baolu <baolu.lu@linux.intel.com>
---
 drivers/iommu/intel/iommu.h |  1 +
 drivers/iommu/intel/dmar.c  | 52 ++++++++++++++++++++++++++++++++++++-
 2 files changed, 52 insertions(+), 1 deletion(-)

diff --git a/drivers/iommu/intel/iommu.h b/drivers/iommu/intel/iommu.h
index 4a21ab6a311d..0c2b4e38dee7 100644
--- a/drivers/iommu/intel/iommu.h
+++ b/drivers/iommu/intel/iommu.h
@@ -192,6 +192,7 @@
  */
 
 #define ecap_pms(e)		(((e) >> 51) & 0x1)
+#define ecap_tdxc(e)		(((e) >> 50) & 0x1)
 #define ecap_rps(e)		(((e) >> 49) & 0x1)
 #define ecap_smpwc(e)		(((e) >> 48) & 0x1)
 #define ecap_flts(e)		(((e) >> 47) & 0x1)
diff --git a/drivers/iommu/intel/dmar.c b/drivers/iommu/intel/dmar.c
index 93efd1a5dc5b..4f9571eee1d4 100644
--- a/drivers/iommu/intel/dmar.c
+++ b/drivers/iommu/intel/dmar.c
@@ -1033,6 +1033,56 @@ static int map_iommu(struct intel_iommu *iommu, struct dmar_drhd_unit *drhd)
 	return err;
 }
 
+static int keyp_config_unit_tvm_usable(union acpi_subtable_headers *header,
+				       void *arg, const unsigned long end)
+{
+	struct acpi_keyp_config_unit *acpi_cu =
+		(struct acpi_keyp_config_unit *)&header->keyp;
+	int *tvm_usable = arg;
+
+	if (acpi_cu->flags & ACPI_KEYP_F_TVM_USABLE)
+		*tvm_usable = 1;
+
+	return 0;
+}
+
+static bool platform_is_tdxc_enhanced(void)
+{
+	static int tvm_usable = -1;
+	int ret;
+
+	/* only need to parse once */
+	if (tvm_usable != -1)
+		return !!tvm_usable;
+
+	tvm_usable = 0;
+	ret = acpi_table_parse_keyp(ACPI_KEYP_TYPE_CONFIG_UNIT,
+				    keyp_config_unit_tvm_usable, &tvm_usable);
+	if (ret < 0)
+		tvm_usable = 0;
+
+	return !!tvm_usable;
+}
+
+static unsigned long iommu_max_domain_id(struct intel_iommu *iommu)
+{
+	unsigned long ndoms = cap_ndoms(iommu->cap);
+
+	/*
+	 * Intel TDX Connect Architecture Specification, Section 2.2 Trusted DMA
+	 *
+	 * When IOMMU is enabled to support TDX Connect, the IOMMU restricts
+	 * the VMM’s DID setting, reserving the MSB bit for the TDX module. The
+	 * TDX module always sets this reserved bit on the trusted DMA table.
+	 */
+	if (ecap_tdxc(iommu->ecap) && platform_is_tdxc_enhanced()) {
+		pr_info_once("Most Significant Bit of domain ID reserved.\n");
+		return ndoms >> 1;
+	}
+
+	return ndoms;
+}
+
 static int alloc_iommu(struct dmar_drhd_unit *drhd)
 {
 	struct intel_iommu *iommu;
@@ -1099,7 +1149,7 @@ static int alloc_iommu(struct dmar_drhd_unit *drhd)
 	spin_lock_init(&iommu->lock);
 	ida_init(&iommu->domain_ida);
 	mutex_init(&iommu->did_lock);
-	iommu->max_domain_id = cap_ndoms(iommu->cap);
+	iommu->max_domain_id = iommu_max_domain_id(iommu);
 
 	ver = readl(iommu->reg + DMAR_VER_REG);
 	pr_info("%s: reg_base_addr %llx ver %d:%d cap %llx ecap %llx\n",

---

## [21] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 20/31] x86/virt/tdx: Add a helper to loop on TDX_INTERRUPTED_RESUMABLE*

Add a helper to handle SEAMCALL return code TDX_INTERRUPTED_RESUMABLE.

SEAMCALL returns TDX_INTERRUPTED_RESUMABLE to avoid stalling host for
long time. After host has handled the interrupt, it calls the
interrupted SEAMCALL again and TDX Module continues to execute. TDX
Module made progress in this case and would eventually finish. An
infinite loop in host should be safe.

The helper is for SEAMCALL wrappers which output information by using
seamcall_ret() or seamcall_saved_ret(). The 2 functions overwrite input
arguments by outputs but much SEAMCALLs expect the same inputs to
resume.

The helper is not for special cases where the SEAMCALL expects modified
inputs to resume. The helper is also not for SEAMCALLs with no output,
do {...} while (r == TDX_INTERRUPTED_RESUMABLE) just works.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 23 +++++++++++++++++++++++
 1 file changed, 23 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index cd0948794b6c..294f36048c03 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2084,6 +2084,29 @@ static inline u64 tdx_tdr_pa(struct tdx_td *td)
 	return page_to_phys(td->tdr_page);
 }
 
+static u64 __maybe_unused __seamcall_ir_resched(sc_func_t sc_func, u64 fn,
+						struct tdx_module_args *args)
+{
+	struct tdx_module_args _args;
+	u64 r;
+
+	while (1) {
+		_args = *(args);
+		r = sc_retry(sc_func, fn, &_args);
+		if (r != TDX_INTERRUPTED_RESUMABLE)
+			break;
+
+		cond_resched();
+	}
+
+	*args = _args;
+
+	return r;
+}
+
+#define seamcall_ret_ir_resched(fn, args)	\
+	__seamcall_ir_resched(__seamcall_ret, fn, args)
+
 noinstr u64 tdh_vp_enter(struct tdx_vp *td, struct tdx_module_args *args)
 {
 	args->rcx = td->tdvpr_pa;

---

## [22] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 21/31] x86/virt/tdx: Add SEAMCALL wrappers for trusted IOMMU setup and clear*

From: Zhenzhong Duan <zhenzhong.duan@intel.com>

Add SEAMCALLs to setup/clear trusted IOMMU for TDX Connect.

Enable TEE I/O support for a target device requires to setup trusted IOMMU
for the related IOMMU device first, even only for enabling physical secure
links like SPDM/IDE.

TDH.IOMMU.SETUP takes the register base address (VTBAR) to position an
IOMMU device, and outputs an IOMMU_ID as the trusted IOMMU identifier.
TDH.IOMMU.CLEAR takes the IOMMU_ID to reverse the setup.

More information see Intel TDX Connect ABI Specification [1]
Section 3.2 TDX Connect Host-Side (SEAMCALL) Interface Functions.

[1]: https://cdrdv2.intel.com/v1/dl/getContent/858625

Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
---
 arch/x86/include/asm/tdx.h  |  2 ++
 arch/x86/virt/vmx/tdx/tdx.h |  2 ++
 arch/x86/virt/vmx/tdx/tdx.c | 32 ++++++++++++++++++++++++++++++--
 3 files changed, 34 insertions(+), 2 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index d7605235aa9b..a59e0e43e465 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -245,6 +245,8 @@ u64 tdh_mem_page_remove(struct tdx_td *td, u64 gpa, u64 level, u64 *ext_err1, u6
 u64 tdh_phymem_cache_wb(bool resume);
 u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td);
 u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page);
+u64 tdh_iommu_setup(u64 vtbar, struct tdx_page_array *iommu_mt, u64 *iommu_id);
+u64 tdh_iommu_clear(u64 iommu_id, struct tdx_page_array *iommu_mt);
 #else
 static inline void tdx_init(void) { }
 static inline int tdx_cpu_enable(void) { return -ENODEV; }
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index a26fe94c07ff..b25c418f6e61 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -62,6 +62,8 @@
 #define TDH_SYS_CONFIG			SEAMCALL_LEAF_VER(TDH_SYS_CONFIG_V0, 1)
 #define TDH_EXT_INIT			60
 #define TDH_EXT_MEM_ADD			61
+#define TDH_IOMMU_SETUP			128
+#define TDH_IOMMU_CLEAR			129
 
 /* TDX page types */
 #define	PT_NDA		0x0
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 294f36048c03..790713881f1f 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2084,8 +2084,8 @@ static inline u64 tdx_tdr_pa(struct tdx_td *td)
 	return page_to_phys(td->tdr_page);
 }
 
-static u64 __maybe_unused __seamcall_ir_resched(sc_func_t sc_func, u64 fn,
-						struct tdx_module_args *args)
+static u64 __seamcall_ir_resched(sc_func_t sc_func, u64 fn,
+				 struct tdx_module_args *args)
 {
 	struct tdx_module_args _args;
 	u64 r;
@@ -2478,3 +2478,31 @@ void tdx_cpu_flush_cache_for_kexec(void)
 }
 EXPORT_SYMBOL_FOR_KVM(tdx_cpu_flush_cache_for_kexec);
 #endif
+
+u64 tdh_iommu_setup(u64 vtbar, struct tdx_page_array *iommu_mt, u64 *iommu_id)
+{
+	struct tdx_module_args args = {
+		.rcx = vtbar,
+		.rdx = virt_to_phys(iommu_mt->root),
+	};
+	u64 r;
+
+	tdx_clflush_page_array(iommu_mt);
+
+	r = seamcall_ret_ir_resched(TDH_IOMMU_SETUP, &args);
+
+	*iommu_id = args.rcx;
+	return r;
+}
+EXPORT_SYMBOL_FOR_MODULES(tdh_iommu_setup, "tdx-host");
+
+u64 tdh_iommu_clear(u64 iommu_id, struct tdx_page_array *iommu_mt)
+{
+	struct tdx_module_args args = {
+		.rcx = iommu_id,
+		.rdx = virt_to_phys(iommu_mt->root),
+	};
+
+	return seamcall_ret_ir_resched(TDH_IOMMU_CLEAR, &args);
+}
+EXPORT_SYMBOL_FOR_MODULES(tdh_iommu_clear, "tdx-host");

---

## [23] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 22/31] iommu/vt-d: Export a helper to do function for each dmar_drhd_unit*

Enable the tdx-host module to get VTBAR address for every IOMMU device.
The VTBAR address is for TDX Module to identify the IOMMU device and
setup its trusted configuraion.

Suggested-by: Lu Baolu <baolu.lu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 include/linux/dmar.h       |  2 ++
 drivers/iommu/intel/dmar.c | 16 ++++++++++++++++
 2 files changed, 18 insertions(+)

diff --git a/include/linux/dmar.h b/include/linux/dmar.h
index 692b2b445761..cd8d9f440975 100644
--- a/include/linux/dmar.h
+++ b/include/linux/dmar.h
@@ -86,6 +86,8 @@ extern struct list_head dmar_drhd_units;
 				dmar_rcu_check())			\
 		if (i=drhd->iommu, 0) {} else 
 
+int do_for_each_drhd_unit(int (*fn)(struct dmar_drhd_unit *));
+
 static inline bool dmar_rcu_check(void)
 {
 	return rwsem_is_locked(&dmar_global_lock) ||
diff --git a/drivers/iommu/intel/dmar.c b/drivers/iommu/intel/dmar.c
index 4f9571eee1d4..eea9ba691f99 100644
--- a/drivers/iommu/intel/dmar.c
+++ b/drivers/iommu/intel/dmar.c
@@ -2452,3 +2452,19 @@ bool dmar_platform_optin(void)
 	return ret;
 }
 EXPORT_SYMBOL_GPL(dmar_platform_optin);
+
+int do_for_each_drhd_unit(int (*fn)(struct dmar_drhd_unit *))
+{
+	struct dmar_drhd_unit *drhd;
+	int ret;
+
+	guard(rwsem_read)(&dmar_global_lock);
+
+	for_each_drhd_unit(drhd) {
+		ret = fn(drhd);
+		if (ret)
+			return ret;
+	}
+	return 0;
+}
+EXPORT_SYMBOL_GPL(do_for_each_drhd_unit);

---

## [24] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 23/31] coco/tdx-host: Setup all trusted IOMMUs on TDX Connect init*

Setup all trusted IOMMUs on TDX Connect initialization and clear all on
TDX Connect removal.

Trusted IOMMU setup is the pre-condition for all following TDX Connect
operations such as SPDM/IDE setup. It is more of a platform
configuration than a standalone IOMMU configuration, so put the
implementation in tdx-host driver.

There is no dedicated way to enumerate which IOMMU devices support
trusted operations. The host has to call TDH.IOMMU.SETUP on all IOMMU
devices and tell their trusted capability by the return value.

Suggested-by: Lu Baolu <baolu.lu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/virt/coco/tdx-host/Kconfig    |  1 +
 drivers/virt/coco/tdx-host/tdx-host.c | 85 +++++++++++++++++++++++++++
 2 files changed, 86 insertions(+)

diff --git a/drivers/virt/coco/tdx-host/Kconfig b/drivers/virt/coco/tdx-host/Kconfig
index 32add81b7d56..24e872f8953e 100644
--- a/drivers/virt/coco/tdx-host/Kconfig
+++ b/drivers/virt/coco/tdx-host/Kconfig
@@ -13,3 +13,4 @@ config TDX_CONNECT
 	def_bool y
 	depends on TDX_HOST_SERVICES
 	depends on PCI_TSM
+	depends on INTEL_IOMMU
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 5ea35a514865..98ed93ac0153 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -6,6 +6,7 @@
  */
 
 #include <linux/device/faux.h>
+#include <linux/dmar.h>
 #include <linux/module.h>
 #include <linux/mod_devicetable.h>
 #include <linux/pci.h>
@@ -119,6 +120,82 @@ static void unregister_link_tsm(void *link)
 	tsm_unregister(link);
 }
 
+static DEFINE_XARRAY(tlink_iommu_xa);
+
+static void tdx_iommu_clear(u64 iommu_id, struct tdx_page_array *iommu_mt)
+{
+	u64 r;
+
+	r = tdh_iommu_clear(iommu_id, iommu_mt);
+	if (r) {
+		pr_err("fail to clear tdx iommu 0x%llx\n", r);
+		goto leak;
+	}
+
+	if (tdx_page_array_ctrl_release(iommu_mt, iommu_mt->nr_pages,
+					virt_to_phys(iommu_mt->root))) {
+		pr_err("fail to release iommu_mt pages\n");
+		goto leak;
+	}
+
+	return;
+
+leak:
+	tdx_page_array_ctrl_leak(iommu_mt);
+}
+
+static int tdx_iommu_enable_one(struct dmar_drhd_unit *drhd)
+{
+	unsigned int nr_pages = tdx_sysinfo->connect.iommu_mt_page_count;
+	u64 r, iommu_id;
+	int ret;
+
+	struct tdx_page_array *iommu_mt __free(tdx_page_array_free) =
+		tdx_page_array_create_iommu_mt(1, nr_pages);
+	if (!iommu_mt)
+		return -ENOMEM;
+
+	r = tdh_iommu_setup(drhd->reg_base_addr, iommu_mt, &iommu_id);
+	/* This drhd doesn't support tdx mode, skip. */
+	if ((r & TDX_SEAMCALL_STATUS_MASK)  == TDX_OPERAND_INVALID)
+		return 0;
+
+	if (r) {
+		pr_err("fail to enable tdx mode for DRHD[0x%llx]\n",
+		       drhd->reg_base_addr);
+		return -EFAULT;
+	}
+
+	ret = xa_insert(&tlink_iommu_xa, (unsigned long)iommu_id,
+			no_free_ptr(iommu_mt), GFP_KERNEL);
+	if (ret) {
+		tdx_iommu_clear(iommu_id, iommu_mt);
+		return ret;
+	}
+
+	return 0;
+}
+
+static void tdx_iommu_disable_all(void *data)
+{
+	struct tdx_page_array *iommu_mt;
+	unsigned long iommu_id;
+
+	xa_for_each(&tlink_iommu_xa, iommu_id, iommu_mt)
+		tdx_iommu_clear(iommu_id, iommu_mt);
+}
+
+static int tdx_iommu_enable_all(void)
+{
+	int ret;
+
+	ret = do_for_each_drhd_unit(tdx_iommu_enable_one);
+	if (ret)
+		tdx_iommu_disable_all(NULL);
+
+	return ret;
+}
+
 static int __maybe_unused tdx_connect_init(struct device *dev)
 {
 	struct tsm_dev *link;
@@ -130,6 +207,14 @@ static int __maybe_unused tdx_connect_init(struct device *dev)
 	if (!(tdx_sysinfo->features.tdx_features0 & TDX_FEATURES0_TDXCONNECT))
 		return 0;
 
+	ret = tdx_iommu_enable_all();
+	if (ret)
+		return dev_err_probe(dev, ret, "Enable tdx iommu failed\n");
+
+	ret = devm_add_action_or_reset(dev, tdx_iommu_disable_all, NULL);
+	if (ret)
+		return ret;
+
 	link = tsm_register(dev, &tdx_tsm_link_ops);
 	if (IS_ERR(link))
 		return dev_err_probe(dev, PTR_ERR(link),

---

## [25] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 24/31] coco/tdx-host: Add a helper to exchange SPDM messages through DOE*

From: Zhenzhong Duan <zhenzhong.duan@intel.com>

TDX host uses this function to exchange TDX Module encrypted data with
devices via SPDM. It is unfortunate that TDX passes raw DOE frames with
headers included and the PCI DOE core wants payloads separated from
headers.

This conversion code is about the same amount of work as teaching the PCI
DOE driver to support raw frames. Unless and until another raw frame use
case shows up, just do this conversion in the TDX TSM driver.

Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>
---
 drivers/virt/coco/tdx-host/tdx-host.c | 61 +++++++++++++++++++++++++++
 1 file changed, 61 insertions(+)

diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 98ed93ac0153..06f3d194e0a8 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -5,11 +5,13 @@
  * Copyright (C) 2025 Intel Corporation
  */
 
+#include <linux/bitfield.h>
 #include <linux/device/faux.h>
 #include <linux/dmar.h>
 #include <linux/module.h>
 #include <linux/mod_devicetable.h>
 #include <linux/pci.h>
+#include <linux/pci-doe.h>
 #include <linux/pci-tsm.h>
 #include <linux/tsm.h>
 
@@ -39,6 +41,65 @@ static struct tdx_tsm_link *to_tdx_tsm_link(struct pci_tsm *tsm)
 	return container_of(tsm, struct tdx_tsm_link, pci.base_tsm);
 }
 
+#define PCI_DOE_DATA_OBJECT_HEADER_1_OFFSET	0
+#define PCI_DOE_DATA_OBJECT_HEADER_2_OFFSET	4
+#define PCI_DOE_DATA_OBJECT_HEADER_SIZE		8
+#define PCI_DOE_DATA_OBJECT_PAYLOAD_OFFSET	PCI_DOE_DATA_OBJECT_HEADER_SIZE
+
+#define PCI_DOE_PROTOCOL_SECURE_SPDM		2
+
+static int __maybe_unused tdx_spdm_msg_exchange(struct tdx_tsm_link *tlink,
+						void *request, size_t request_sz,
+						void *response, size_t response_sz)
+{
+	struct pci_dev *pdev = tlink->pci.base_tsm.pdev;
+	void *req_pl_addr, *resp_pl_addr;
+	size_t req_pl_sz, resp_pl_sz;
+	u32 data, len;
+	u16 vendor;
+	u8 type;
+	int ret;
+
+	/*
+	 * pci_doe() accept DOE PAYLOAD only but request carries DOE HEADER so
+	 * shift the buffers, skip DOE HEADER in request buffer, and fill DOE
+	 * HEADER in response buffer manually.
+	 */
+
+	data = le32_to_cpu(*(__le32 *)(request + PCI_DOE_DATA_OBJECT_HEADER_1_OFFSET));
+	vendor = FIELD_GET(PCI_DOE_DATA_OBJECT_HEADER_1_VID, data);
+	type = FIELD_GET(PCI_DOE_DATA_OBJECT_HEADER_1_TYPE, data);
+
+	data = le32_to_cpu(*(__le32 *)(request + PCI_DOE_DATA_OBJECT_HEADER_2_OFFSET));
+	len = FIELD_GET(PCI_DOE_DATA_OBJECT_HEADER_2_LENGTH, data);
+
+	req_pl_sz = len * sizeof(__le32) - PCI_DOE_DATA_OBJECT_HEADER_SIZE;
+	resp_pl_sz = response_sz - PCI_DOE_DATA_OBJECT_HEADER_SIZE;
+	req_pl_addr = request + PCI_DOE_DATA_OBJECT_HEADER_SIZE;
+	resp_pl_addr = response + PCI_DOE_DATA_OBJECT_HEADER_SIZE;
+
+	ret = pci_tsm_doe_transfer(pdev, type, req_pl_addr, req_pl_sz,
+				   resp_pl_addr, resp_pl_sz);
+	if (ret < 0) {
+		pci_err(pdev, "spdm msg exchange fail %d\n", ret);
+		return ret;
+	}
+
+	data = FIELD_PREP(PCI_DOE_DATA_OBJECT_HEADER_1_VID, vendor) |
+	       FIELD_PREP(PCI_DOE_DATA_OBJECT_HEADER_1_TYPE, type);
+	*(__le32 *)(response + PCI_DOE_DATA_OBJECT_HEADER_1_OFFSET) = cpu_to_le32(data);
+
+	len = (ret + PCI_DOE_DATA_OBJECT_HEADER_SIZE) / sizeof(__le32);
+	data = FIELD_PREP(PCI_DOE_DATA_OBJECT_HEADER_2_LENGTH, len);
+	*(__le32 *)(response + PCI_DOE_DATA_OBJECT_HEADER_2_OFFSET) = cpu_to_le32(data);
+
+	ret += PCI_DOE_DATA_OBJECT_HEADER_SIZE;
+
+	pci_dbg(pdev, "%s complete: vendor 0x%x type 0x%x rsp_sz %d\n",
+		__func__, vendor, type, ret);
+	return ret;
+}
+
 static int tdx_tsm_link_connect(struct pci_dev *pdev)
 {
 	return -ENXIO;

---

## [26] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 25/31] x86/virt/tdx: Add SEAMCALL wrappers for SPDM management*

From: Zhenzhong Duan <zhenzhong.duan@intel.com>

Add several SEAMCALL wrappers for SPDM management. TDX Module requires
HPA_ARRAY_T structure as input/output parameters for these SEAMCALLs.
So use tdx_page_array for these wrappers.

- TDH.SPDM.CREATE creates SPDM session metadata buffers for TDX Module.
- TDH.SPDM.DELETE destroys SPDM session metadata and returns these
  buffers to host, after checking no reference attached to the metadata.
- TDH.SPDM.CONNECT establishes a new SPDM session with the device.
- TDH.SPDM.DISCONNECT tears down the SPDM session with the device.
- TDH.SPDM.MNG supports three SPDM runtime operations: HEARTBEAT,
  KEY_UPDATE and DEV_INFO_RECOLLECTION.

Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
---
 arch/x86/include/asm/tdx.h  |  13 ++++
 arch/x86/virt/vmx/tdx/tdx.h |   5 ++
 arch/x86/virt/vmx/tdx/tdx.c | 114 +++++++++++++++++++++++++++++++++++-
 3 files changed, 130 insertions(+), 2 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index a59e0e43e465..8abdad084972 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -247,6 +247,19 @@ u64 tdh_phymem_page_wbinvd_tdr(struct tdx_td *td);
 u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page);
 u64 tdh_iommu_setup(u64 vtbar, struct tdx_page_array *iommu_mt, u64 *iommu_id);
 u64 tdh_iommu_clear(u64 iommu_id, struct tdx_page_array *iommu_mt);
+u64 tdh_spdm_create(u64 func_id, struct tdx_page_array *spdm_mt, u64 *spdm_id);
+u64 tdh_spdm_delete(u64 spdm_id, struct tdx_page_array *spdm_mt,
+		    unsigned int *nr_released, u64 *released_hpa);
+u64 tdh_exec_spdm_connect(u64 spdm_id, struct page *spdm_conf,
+			  struct page *spdm_rsp, struct page *spdm_req,
+			  struct tdx_page_array *spdm_out,
+			  u64 *spdm_req_or_out_len);
+u64 tdh_exec_spdm_disconnect(u64 spdm_id, struct page *spdm_rsp,
+			     struct page *spdm_req, u64 *spdm_req_len);
+u64 tdh_exec_spdm_mng(u64 spdm_id, u64 spdm_op, struct page *spdm_param,
+		      struct page *spdm_rsp, struct page *spdm_req,
+		      struct tdx_page_array *spdm_out,
+		      u64 *spdm_req_or_out_len);
 #else
 static inline void tdx_init(void) { }
 static inline int tdx_cpu_enable(void) { return -ENODEV; }
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index b25c418f6e61..4784db2d1d92 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -64,6 +64,11 @@
 #define TDH_EXT_MEM_ADD			61
 #define TDH_IOMMU_SETUP			128
 #define TDH_IOMMU_CLEAR			129
+#define TDH_SPDM_CREATE			130
+#define TDH_SPDM_DELETE			131
+#define TDH_SPDM_CONNECT		142
+#define TDH_SPDM_DISCONNECT		143
+#define TDH_SPDM_MNG			144
 
 /* TDX page types */
 #define	PT_NDA		0x0
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 790713881f1f..02882c2ad177 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -654,7 +654,7 @@ static u64 hpa_list_info_assign_raw(struct tdx_page_array *array)
 #define HPA_ARRAY_T_PFN		GENMASK_U64(51, 12)
 #define HPA_ARRAY_T_SIZE	GENMASK_U64(63, 55)
 
-static u64 __maybe_unused hpa_array_t_assign_raw(struct tdx_page_array *array)
+static u64 hpa_array_t_assign_raw(struct tdx_page_array *array)
 {
 	unsigned long pfn;
 
@@ -667,7 +667,7 @@ static u64 __maybe_unused hpa_array_t_assign_raw(struct tdx_page_array *array)
 	       FIELD_PREP(HPA_ARRAY_T_SIZE, array->nents - 1);
 }
 
-static u64 __maybe_unused hpa_array_t_release_raw(struct tdx_page_array *array)
+static u64 hpa_array_t_release_raw(struct tdx_page_array *array)
 {
 	if (array->nents == 1)
 		return 0;
@@ -2107,6 +2107,15 @@ static u64 __seamcall_ir_resched(sc_func_t sc_func, u64 fn,
 #define seamcall_ret_ir_resched(fn, args)	\
 	__seamcall_ir_resched(__seamcall_ret, fn, args)
 
+/*
+ * seamcall_ret_ir_exec() aliases seamcall_ret_ir_resched() for
+ * documentation purposes. It documents the TDX Module extension
+ * seamcalls that are long running / hard-irq preemptible flows that
+ * generate events. The calls using seamcall_ret_ir_resched() are long
+ * running flows, that periodically yield.
+ */
+#define seamcall_ret_ir_exec seamcall_ret_ir_resched
+
 noinstr u64 tdh_vp_enter(struct tdx_vp *td, struct tdx_module_args *args)
 {
 	args->rcx = td->tdvpr_pa;
@@ -2506,3 +2515,104 @@ u64 tdh_iommu_clear(u64 iommu_id, struct tdx_page_array *iommu_mt)
 	return seamcall_ret_ir_resched(TDH_IOMMU_CLEAR, &args);
 }
 EXPORT_SYMBOL_FOR_MODULES(tdh_iommu_clear, "tdx-host");
+
+u64 tdh_spdm_create(u64 func_id, struct tdx_page_array *spdm_mt, u64 *spdm_id)
+{
+	struct tdx_module_args args = {
+		.rcx = func_id,
+		.rdx = hpa_array_t_assign_raw(spdm_mt)
+	};
+	u64 r;
+
+	tdx_clflush_page_array(spdm_mt);
+
+	r = seamcall_ret(TDH_SPDM_CREATE, &args);
+
+	*spdm_id = args.rcx;
+
+	return r;
+}
+EXPORT_SYMBOL_FOR_MODULES(tdh_spdm_create, "tdx-host");
+
+u64 tdh_spdm_delete(u64 spdm_id, struct tdx_page_array *spdm_mt,
+		    unsigned int *nr_released, u64 *released_hpa)
+{
+	struct tdx_module_args args = {
+		.rcx = spdm_id,
+		.rdx = hpa_array_t_release_raw(spdm_mt),
+	};
+	u64 r;
+
+	r = seamcall_ret(TDH_SPDM_DELETE, &args);
+	if (r != TDX_SUCCESS)
+		return r;
+
+	*nr_released = FIELD_GET(HPA_ARRAY_T_SIZE, args.rcx) + 1;
+	*released_hpa = FIELD_GET(HPA_ARRAY_T_PFN, args.rcx) << PAGE_SHIFT;
+
+	return r;
+}
+EXPORT_SYMBOL_FOR_MODULES(tdh_spdm_delete, "tdx-host");
+
+u64 tdh_exec_spdm_connect(u64 spdm_id, struct page *spdm_conf,
+			  struct page *spdm_rsp, struct page *spdm_req,
+			  struct tdx_page_array *spdm_out,
+			  u64 *spdm_req_or_out_len)
+{
+	struct tdx_module_args args = {
+		.rcx = spdm_id,
+		.rdx = page_to_phys(spdm_conf),
+		.r8 = page_to_phys(spdm_rsp),
+		.r9 = page_to_phys(spdm_req),
+		.r10 = hpa_array_t_assign_raw(spdm_out),
+	};
+	u64 r;
+
+	r = seamcall_ret_ir_exec(TDH_SPDM_CONNECT, &args);
+
+	*spdm_req_or_out_len = args.rcx;
+
+	return r;
+}
+EXPORT_SYMBOL_FOR_MODULES(tdh_exec_spdm_connect, "tdx-host");
+
+u64 tdh_exec_spdm_disconnect(u64 spdm_id, struct page *spdm_rsp,
+			     struct page *spdm_req, u64 *spdm_req_len)
+{
+	struct tdx_module_args args = {
+		.rcx = spdm_id,
+		.rdx = page_to_phys(spdm_rsp),
+		.r8 = page_to_phys(spdm_req),
+	};
+	u64 r;
+
+	r = seamcall_ret_ir_exec(TDH_SPDM_DISCONNECT, &args);
+
+	*spdm_req_len = args.rcx;
+
+	return r;
+}
+EXPORT_SYMBOL_FOR_MODULES(tdh_exec_spdm_disconnect, "tdx-host");
+
+u64 tdh_exec_spdm_mng(u64 spdm_id, u64 spdm_op, struct page *spdm_param,
+		      struct page *spdm_rsp, struct page *spdm_req,
+		      struct tdx_page_array *spdm_out,
+		      u64 *spdm_req_or_out_len)
+{
+	struct tdx_module_args args = {
+		.rcx = spdm_id,
+		.rdx = spdm_op,
+		.r8 = spdm_param ? page_to_phys(spdm_param) : -1,
+		.r9 = page_to_phys(spdm_rsp),
+		.r10 = page_to_phys(spdm_req),
+		.r11 = spdm_out ? hpa_array_t_assign_raw(spdm_out) : -1,
+	};
+	u64 r;
+
+	r = seamcall_ret_ir_exec(TDH_SPDM_MNG, &args);
+
+	*spdm_req_or_out_len = args.rcx;
+
+	return r;
+}
+EXPORT_SYMBOL_FOR_MODULES(tdh_exec_spdm_mng, "tdx-host");

---

## [27] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 26/31] mm: Add __free() support for __free_page()*

Allow for the declaration of struct page * variables that trigger
__free_page() when they go out of scope.

A example usage would be in the following patch:

  static struct pci_tsm *tdx_tsm_link_pf0_probe(...)
  {
	...

	struct page *in_msg_page __free(__free_page) =
		alloc_page(GFP_KERNEL | __GFP_ZERO);
	if (!in_msg_page)
		return NULL;

	struct page *out_msg_page __free(__free_page) =
		alloc_page(GFP_KERNEL | __GFP_ZERO);
	if (!out_msg_page)
		return NULL;

	...

	tlink->in_msg = no_free_ptr(in_msg_page);
	tlink->out_msg = no_free_ptr(out_msg_page);

	...
  }

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>
---
 include/linux/gfp.h | 1 +
 1 file changed, 1 insertion(+)

diff --git a/include/linux/gfp.h b/include/linux/gfp.h
index 51ef13ed756e..d37e5564234e 100644
--- a/include/linux/gfp.h
+++ b/include/linux/gfp.h
@@ -391,6 +391,7 @@ extern void free_pages_nolock(struct page *page, unsigned int order);
 extern void free_pages(unsigned long addr, unsigned int order);
 
 #define __free_page(page) __free_pages((page), 0)
+DEFINE_FREE(__free_page, struct page *, if (_T) __free_page(_T))
 #define free_page(addr) free_pages((addr), 0)
 
 void page_alloc_init_cpuhp(void);

---

## [28] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 27/31] coco/tdx-host: Implement SPDM session setup*

From: Zhenzhong Duan <zhenzhong.duan@intel.com>

Implementation for a most straightforward SPDM session setup, using all
default session options. Retrieve device info data from TDX Module which
contains the SPDM negotiation results.

TDH.SPDM.CONNECT/DISCONNECT are TDX Module Extension introduced
SEAMCALLs which can run for longer periods and interruptible. But there
is resource constraints that limit how many SEAMCALLs of this kind can
run simultaneously. The current situation is One SEAMCALL at a time.
Otherwise TDX_OPERAND_BUSY is returned. To avoid "broken indefinite"
retry, a tdx_ext_lock is used to guard these SEAMCALLs.

Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
---
 arch/x86/include/asm/shared/tdx_errno.h |   2 +
 drivers/virt/coco/tdx-host/tdx-host.c   | 301 +++++++++++++++++++++++-
 2 files changed, 299 insertions(+), 4 deletions(-)

diff --git a/arch/x86/include/asm/shared/tdx_errno.h b/arch/x86/include/asm/shared/tdx_errno.h
index 8bf6765cf082..7db04fe30378 100644
--- a/arch/x86/include/asm/shared/tdx_errno.h
+++ b/arch/x86/include/asm/shared/tdx_errno.h
@@ -29,6 +29,8 @@
 #define TDX_EPT_WALK_FAILED			0xC0000B0000000000ULL
 #define TDX_EPT_ENTRY_STATE_INCORRECT		0xC0000B0D00000000ULL
 #define TDX_METADATA_FIELD_NOT_READABLE		0xC0000C0200000000ULL
+#define TDX_SPDM_SESSION_KEY_REQUIRE_REFRESH	0xC0000F4500000000ULL
+#define TDX_SPDM_REQUEST			0xC0000F5700000000ULL
 
 /*
  * SW-defined error codes.
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 06f3d194e0a8..4d127b7c2591 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -14,6 +14,7 @@
 #include <linux/pci-doe.h>
 #include <linux/pci-tsm.h>
 #include <linux/tsm.h>
+#include <linux/vmalloc.h>
 
 #include <asm/cpu_device_id.h>
 #include <asm/tdx.h>
@@ -32,8 +33,43 @@ MODULE_DEVICE_TABLE(x86cpu, tdx_host_ids);
  */
 static const struct tdx_sys_info *tdx_sysinfo;
 
+#define TDISP_FUNC_ID		GENMASK(15, 0)
+#define TDISP_FUNC_ID_SEGMENT		GENMASK(23, 16)
+#define TDISP_FUNC_ID_SEG_VALID		BIT(24)
+
+static inline u32 tdisp_func_id(struct pci_dev *pdev)
+{
+	u32 func_id;
+
+	func_id = FIELD_PREP(TDISP_FUNC_ID_SEGMENT, pci_domain_nr(pdev->bus));
+	if (func_id)
+		func_id |= TDISP_FUNC_ID_SEG_VALID;
+	func_id |= FIELD_PREP(TDISP_FUNC_ID,
+			      PCI_DEVID(pdev->bus->number, pdev->devfn));
+
+	return func_id;
+}
+
+struct spdm_config_info_t {
+	u32 vmm_spdm_cap;
+#define SPDM_CAP_HBEAT          BIT(13)
+#define SPDM_CAP_KEY_UPD        BIT(14)
+	u8 spdm_session_policy;
+	u8 certificate_slot_mask;
+	u8 raw_bitstream_requested;
+} __packed;
+
 struct tdx_tsm_link {
 	struct pci_tsm_pf0 pci;
+	u32 func_id;
+	struct page *in_msg;
+	struct page *out_msg;
+
+	u64 spdm_id;
+	struct page *spdm_conf;
+	struct tdx_page_array *spdm_mt;
+	unsigned int dev_info_size;
+	void *dev_info_data;
 };
 
 static struct tdx_tsm_link *to_tdx_tsm_link(struct pci_tsm *tsm)
@@ -48,9 +84,9 @@ static struct tdx_tsm_link *to_tdx_tsm_link(struct pci_tsm *tsm)
 
 #define PCI_DOE_PROTOCOL_SECURE_SPDM		2
 
-static int __maybe_unused tdx_spdm_msg_exchange(struct tdx_tsm_link *tlink,
-						void *request, size_t request_sz,
-						void *response, size_t response_sz)
+static int tdx_spdm_msg_exchange(struct tdx_tsm_link *tlink,
+				 void *request, size_t request_sz,
+				 void *response, size_t response_sz)
 {
 	struct pci_dev *pdev = tlink->pci.base_tsm.pdev;
 	void *req_pl_addr, *resp_pl_addr;
@@ -100,18 +136,246 @@ static int __maybe_unused tdx_spdm_msg_exchange(struct tdx_tsm_link *tlink,
 	return ret;
 }
 
+static int tdx_spdm_session_keyupdate(struct tdx_tsm_link *tlink);
+
+static int tdx_tsm_link_event_handler(struct tdx_tsm_link *tlink,
+				      u64 tdx_ret, u64 out_msg_sz)
+{
+	int ret;
+
+	if (tdx_ret == TDX_SUCCESS)
+		return 0;
+
+	if (tdx_ret == TDX_SPDM_REQUEST) {
+		ret = tdx_spdm_msg_exchange(tlink,
+					    page_address(tlink->out_msg),
+					    out_msg_sz,
+					    page_address(tlink->in_msg),
+					    PAGE_SIZE);
+		if (ret < 0)
+			return ret;
+
+		return -EAGAIN;
+	}
+
+	if (tdx_ret == TDX_SPDM_SESSION_KEY_REQUIRE_REFRESH) {
+		/* keyupdate won't trigger this error again, no recursion risk */
+		ret = tdx_spdm_session_keyupdate(tlink);
+		if (ret)
+			return ret;
+
+		return -EAGAIN;
+	}
+
+	return -EFAULT;
+}
+
+/*
+ * TDX Module extension introduced SEAMCALLs work like a request queue.
+ * The caller is responsible for grabbing a queue slot before SEAMCALL,
+ * otherwise will fail with TDX_OPERAND_BUSY. Currently the queue depth is 1.
+ * So a mutex could work for simplicity.
+ */
+static DEFINE_MUTEX(tdx_ext_lock);
+
+enum tdx_spdm_mng_op {
+	TDX_SPDM_MNG_HEARTBEAT = 0,
+	TDX_SPDM_MNG_KEY_UPDATE = 1,
+	TDX_SPDM_MNG_RECOLLECT = 2,
+};
+
+static int tdx_spdm_session_mng(struct tdx_tsm_link *tlink,
+				enum tdx_spdm_mng_op op)
+{
+	u64 r, out_msg_sz;
+	int ret;
+
+	guard(mutex)(&tdx_ext_lock);
+	do {
+		r = tdh_exec_spdm_mng(tlink->spdm_id, op, NULL, tlink->in_msg,
+				      tlink->out_msg, NULL, &out_msg_sz);
+		ret = tdx_tsm_link_event_handler(tlink, r, out_msg_sz);
+	} while (ret == -EAGAIN);
+
+	return ret;
+}
+
+static int tdx_spdm_session_keyupdate(struct tdx_tsm_link *tlink)
+{
+	return tdx_spdm_session_mng(tlink, TDX_SPDM_MNG_KEY_UPDATE);
+}
+
+static void *tdx_dup_array_data(struct tdx_page_array *array,
+				unsigned int data_size)
+{
+	unsigned int npages = (data_size + PAGE_SIZE - 1) / PAGE_SIZE;
+	void *data, *dup_data;
+
+	if (npages > array->nr_pages)
+		return NULL;
+
+	data = vm_map_ram(array->pages, npages, -1);
+	if (!data)
+		return NULL;
+
+	dup_data = kmemdup(data, data_size, GFP_KERNEL);
+	vm_unmap_ram(data, npages);
+
+	return dup_data;
+}
+
+static struct tdx_tsm_link *
+tdx_spdm_session_connect(struct tdx_tsm_link *tlink,
+			 struct tdx_page_array *dev_info)
+{
+	u64 r, out_msg_sz;
+	int ret;
+
+	guard(mutex)(&tdx_ext_lock);
+	do {
+		r = tdh_exec_spdm_connect(tlink->spdm_id, tlink->spdm_conf,
+					  tlink->in_msg, tlink->out_msg,
+					  dev_info, &out_msg_sz);
+		ret = tdx_tsm_link_event_handler(tlink, r, out_msg_sz);
+	} while (ret == -EAGAIN);
+
+	if (ret)
+		return ERR_PTR(ret);
+
+	tlink->dev_info_size = out_msg_sz;
+	return tlink;
+}
+
+static void tdx_spdm_session_disconnect(struct tdx_tsm_link *tlink)
+{
+	u64 r, out_msg_sz;
+	int ret;
+
+	guard(mutex)(&tdx_ext_lock);
+	do {
+		r = tdh_exec_spdm_disconnect(tlink->spdm_id, tlink->in_msg,
+					     tlink->out_msg, &out_msg_sz);
+		ret = tdx_tsm_link_event_handler(tlink, r, out_msg_sz);
+	} while (ret == -EAGAIN);
+
+	WARN_ON(ret);
+}
+
+DEFINE_FREE(tdx_spdm_session_disconnect, struct tdx_tsm_link *,
+	    if (!IS_ERR_OR_NULL(_T)) tdx_spdm_session_disconnect(_T))
+
+static struct tdx_tsm_link *tdx_spdm_create(struct tdx_tsm_link *tlink)
+{
+	unsigned int nr_pages = tdx_sysinfo->connect.spdm_mt_page_count;
+	u64 spdm_id, r;
+
+	struct tdx_page_array *spdm_mt __free(tdx_page_array_free) =
+		tdx_page_array_create(nr_pages);
+	if (!spdm_mt)
+		return ERR_PTR(-ENOMEM);
+
+	r = tdh_spdm_create(tlink->func_id, spdm_mt, &spdm_id);
+	if (r)
+		return ERR_PTR(-EFAULT);
+
+	tlink->spdm_id = spdm_id;
+	tlink->spdm_mt = no_free_ptr(spdm_mt);
+	return tlink;
+}
+
+static void tdx_spdm_delete(struct tdx_tsm_link *tlink)
+{
+	struct pci_dev *pdev = tlink->pci.base_tsm.pdev;
+	unsigned int nr_released;
+	u64 released_hpa, r;
+
+	r = tdh_spdm_delete(tlink->spdm_id, tlink->spdm_mt, &nr_released, &released_hpa);
+	if (r) {
+		pci_err(pdev, "fail to delete spdm 0x%llx\n", r);
+		goto leak;
+	}
+
+	if (tdx_page_array_ctrl_release(tlink->spdm_mt, nr_released, released_hpa)) {
+		pci_err(pdev, "fail to release spdm_mt pages\n");
+		goto leak;
+	}
+
+	return;
+
+leak:
+	tdx_page_array_ctrl_leak(tlink->spdm_mt);
+}
+
+DEFINE_FREE(tdx_spdm_delete, struct tdx_tsm_link *, if (!IS_ERR_OR_NULL(_T)) tdx_spdm_delete(_T))
+
+static struct tdx_tsm_link *tdx_spdm_session_setup(struct tdx_tsm_link *tlink)
+{
+	unsigned int nr_pages = tdx_sysinfo->connect.spdm_max_dev_info_pages;
+
+	struct tdx_tsm_link *tlink_create __free(tdx_spdm_delete) =
+		tdx_spdm_create(tlink);
+	if (IS_ERR(tlink_create))
+		return tlink_create;
+
+	struct tdx_page_array *dev_info __free(tdx_page_array_free) =
+		tdx_page_array_create(nr_pages);
+	if (!dev_info)
+		return ERR_PTR(-ENOMEM);
+
+	struct tdx_tsm_link *tlink_connect __free(tdx_spdm_session_disconnect) =
+		tdx_spdm_session_connect(tlink, dev_info);
+	if (IS_ERR(tlink_connect))
+		return tlink_connect;
+
+	tlink->dev_info_data = tdx_dup_array_data(dev_info,
+						  tlink->dev_info_size);
+	if (!tlink->dev_info_data)
+		return ERR_PTR(-ENOMEM);
+
+	retain_and_null_ptr(tlink_create);
+	retain_and_null_ptr(tlink_connect);
+
+	return tlink;
+}
+
+static void tdx_spdm_session_teardown(struct tdx_tsm_link *tlink)
+{
+	kfree(tlink->dev_info_data);
+
+	tdx_spdm_session_disconnect(tlink);
+	tdx_spdm_delete(tlink);
+}
+
+DEFINE_FREE(tdx_spdm_session_teardown, struct tdx_tsm_link *,
+	    if (!IS_ERR_OR_NULL(_T)) tdx_spdm_session_teardown(_T))
+
 static int tdx_tsm_link_connect(struct pci_dev *pdev)
 {
-	return -ENXIO;
+	struct tdx_tsm_link *tlink = to_tdx_tsm_link(pdev->tsm);
+
+	struct tdx_tsm_link *tlink_spdm __free(tdx_spdm_session_teardown) =
+		tdx_spdm_session_setup(tlink);
+	if (IS_ERR(tlink_spdm)) {
+		pci_err(pdev, "fail to setup spdm session\n");
+		return PTR_ERR(tlink_spdm);
+	}
+
+	retain_and_null_ptr(tlink_spdm);
+
+	return 0;
 }
 
 static void tdx_tsm_link_disconnect(struct pci_dev *pdev)
 {
+	struct tdx_tsm_link *tlink = to_tdx_tsm_link(pdev->tsm);
+
+	tdx_spdm_session_teardown(tlink);
 }
 
 static struct pci_tsm *tdx_tsm_link_pf0_probe(struct tsm_dev *tsm_dev,
 					      struct pci_dev *pdev)
 {
+	struct spdm_config_info_t *spdm_conf;
 	int rc;
 
 	struct tdx_tsm_link *tlink __free(kfree) = kzalloc_obj(*tlink);
@@ -122,6 +386,32 @@ static struct pci_tsm *tdx_tsm_link_pf0_probe(struct tsm_dev *tsm_dev,
 	if (rc)
 		return NULL;
 
+	tlink->func_id = tdisp_func_id(pdev);
+
+	struct page *in_msg_page __free(__free_page) =
+		alloc_page(GFP_KERNEL | __GFP_ZERO);
+	if (!in_msg_page)
+		return NULL;
+
+	struct page *out_msg_page __free(__free_page) =
+		alloc_page(GFP_KERNEL | __GFP_ZERO);
+	if (!out_msg_page)
+		return NULL;
+
+	struct page *spdm_conf_page __free(kfree) =
+		alloc_page(GFP_KERNEL | __GFP_ZERO);
+	if (!spdm_conf_page)
+		return NULL;
+
+	/* use a default configuration, may require user input later */
+	spdm_conf = page_address(spdm_conf_page);
+	spdm_conf->vmm_spdm_cap = SPDM_CAP_KEY_UPD;
+	spdm_conf->certificate_slot_mask = 0xff;
+
+	tlink->in_msg = no_free_ptr(in_msg_page);
+	tlink->out_msg = no_free_ptr(out_msg_page);
+	tlink->spdm_conf = no_free_ptr(spdm_conf_page);
+
 	return &no_free_ptr(tlink)->pci.base_tsm;
 }
 
@@ -129,6 +419,9 @@ static void tdx_tsm_link_pf0_remove(struct pci_tsm *tsm)
 {
 	struct tdx_tsm_link *tlink = to_tdx_tsm_link(tsm);
 
+	__free_page(tlink->spdm_conf);
+	__free_page(tlink->out_msg);
+	__free_page(tlink->in_msg);
 	pci_tsm_pf0_destructor(&tlink->pci);
 	kfree(tlink);
 }

---

## [29] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 28/31] coco/tdx-host: Parse ACPI KEYP table to init IDE for PCI host bridges*

Parse the KEYP Key Configuration Units (KCU), to decide the max IDE
streams supported for each host bridge.

The KEYP table points to a number of KCU structures that each associates
with a list of root ports (RP) via segment, bus, and devfn. Sanity check
the KEYP table, ensure all RPs listed for each KCU are included in one
host bridge. Then extact the max IDE streams supported to
pci_host_bridge via pci_ide_set_nr_streams().

Co-developed-by: Dave Jiang <dave.jiang@intel.com>
Signed-off-by: Dave Jiang <dave.jiang@intel.com>
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/virt/coco/tdx-host/tdx-host.c | 111 ++++++++++++++++++++++++++
 1 file changed, 111 insertions(+)

diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 4d127b7c2591..d5072a68b81a 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -5,6 +5,7 @@
  * Copyright (C) 2025 Intel Corporation
  */
 
+#include <linux/acpi.h>
 #include <linux/bitfield.h>
 #include <linux/device/faux.h>
 #include <linux/dmar.h>
@@ -12,6 +13,7 @@
 #include <linux/mod_devicetable.h>
 #include <linux/pci.h>
 #include <linux/pci-doe.h>
+#include <linux/pci-ide.h>
 #include <linux/pci-tsm.h>
 #include <linux/tsm.h>
 #include <linux/vmalloc.h>
@@ -474,6 +476,111 @@ static void unregister_link_tsm(void *link)
 	tsm_unregister(link);
 }
 
+#define KCU_STR_CAP_NUM_STREAMS		GENMASK(8, 0)
+
+/* The bus_end is inclusive */
+struct keyp_hb_info {
+	/* input */
+	u16 segment;
+	u8 bus_start;
+	u8 bus_end;
+	/* output */
+	u8 nr_ide_streams;
+};
+
+static bool keyp_info_match(struct acpi_keyp_rp_info *rp,
+			    struct keyp_hb_info *hb)
+{
+	return rp->segment == hb->segment && rp->bus >= hb->bus_start &&
+	       rp->bus <= hb->bus_end;
+}
+
+static int keyp_config_unit_handler(union acpi_subtable_headers *header,
+				    void *arg, const unsigned long end)
+{
+	struct acpi_keyp_config_unit *acpi_cu =
+		(struct acpi_keyp_config_unit *)&header->keyp;
+	struct keyp_hb_info *hb_info = arg;
+	int rp_size, rp_count, i;
+	void __iomem *addr;
+	bool match = false;
+	u32 cap;
+
+	rp_size = acpi_cu->header.length - sizeof(*acpi_cu);
+	if (rp_size % sizeof(struct acpi_keyp_rp_info))
+		return -EINVAL;
+
+	rp_count = rp_size / sizeof(struct acpi_keyp_rp_info);
+	if (!rp_count || rp_count != acpi_cu->root_port_count)
+		return -EINVAL;
+
+	for (i = 0; i < rp_count; i++) {
+		struct acpi_keyp_rp_info *rp_info = &acpi_cu->rp_info[i];
+
+		if (i == 0) {
+			match = keyp_info_match(rp_info, hb_info);
+			/* The host bridge already matches another KCU */
+			if (match && hb_info->nr_ide_streams)
+				return -EINVAL;
+
+			continue;
+		}
+
+		if (match ^ keyp_info_match(rp_info, hb_info))
+			return -EINVAL;
+	}
+
+	if (!match)
+		return 0;
+
+	addr = ioremap(acpi_cu->register_base_address, sizeof(cap));
+	if (!addr)
+		return -ENOMEM;
+	cap = ioread32(addr);
+	iounmap(addr);
+
+	hb_info->nr_ide_streams = FIELD_GET(KCU_STR_CAP_NUM_STREAMS, cap) + 1;
+
+	return 0;
+}
+
+static u8 keyp_find_nr_ide_stream(u16 segment, u8 bus_start, u8 bus_end)
+{
+	struct keyp_hb_info hb_info = {
+		.segment = segment,
+		.bus_start = bus_start,
+		.bus_end = bus_end,
+	};
+	int rc;
+
+	rc = acpi_table_parse_keyp(ACPI_KEYP_TYPE_CONFIG_UNIT,
+				   keyp_config_unit_handler, &hb_info);
+	if (rc < 0)
+		return 0;
+
+	return hb_info.nr_ide_streams;
+}
+
+static void keyp_setup_nr_ide_stream(struct pci_bus *bus)
+{
+	struct pci_host_bridge *hb = pci_find_host_bridge(bus);
+	u8 nr_ide_streams;
+
+	nr_ide_streams = keyp_find_nr_ide_stream(pci_domain_nr(bus),
+						 bus->busn_res.start,
+						 bus->busn_res.end);
+
+	pci_ide_set_nr_streams(hb, nr_ide_streams);
+}
+
+static void tdx_setup_nr_ide_stream(void)
+{
+	struct pci_bus *bus = NULL;
+
+	while ((bus = pci_find_next_bus(bus)))
+		keyp_setup_nr_ide_stream(bus);
+}
+
 static DEFINE_XARRAY(tlink_iommu_xa);
 
 static void tdx_iommu_clear(u64 iommu_id, struct tdx_page_array *iommu_mt)
@@ -569,6 +676,8 @@ static int __maybe_unused tdx_connect_init(struct device *dev)
 	if (ret)
 		return ret;
 
+	tdx_setup_nr_ide_stream();
+
 	link = tsm_register(dev, &tdx_tsm_link_ops);
 	if (IS_ERR(link))
 		return dev_err_probe(dev, PTR_ERR(link),
@@ -612,5 +721,7 @@ static void __exit tdx_host_exit(void)
 }
 module_exit(tdx_host_exit);
 
+MODULE_IMPORT_NS("ACPI");
+MODULE_IMPORT_NS("PCI_IDE");
 MODULE_DESCRIPTION("TDX Host Services");
 MODULE_LICENSE("GPL");

---

## [30] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 29/31] x86/virt/tdx: Add SEAMCALL wrappers for IDE stream management*

Add several SEAMCALL wrappers for IDE stream management.

- TDH.IDE.STREAM.CREATE creates IDE stream metadata buffers for TDX
  Module, and does root port side IDE configuration.
- TDH.IDE.STREAM.BLOCK clears the root port side IDE configuration.
- TDH.IDE.STREAM.DELETE releases the IDE stream metadata buffers.
- TDH.IDE.STREAM.KM deals with the IDE Key Management protocol (IDE-KM)

More information see Intel TDX Connect ABI Specification [1]
Section 3.2 TDX Connect Host-Side (SEAMCALL) Interface Functions.

[1]: https://cdrdv2.intel.com/v1/dl/getContent/858625

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/include/asm/tdx.h  | 14 ++++++
 arch/x86/virt/vmx/tdx/tdx.h |  4 ++
 arch/x86/virt/vmx/tdx/tdx.c | 86 +++++++++++++++++++++++++++++++++++++
 3 files changed, 104 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 8abdad084972..7bdd66acda5b 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -260,6 +260,20 @@ u64 tdh_exec_spdm_mng(u64 spdm_id, u64 spdm_op, struct page *spdm_param,
 		      struct page *spdm_rsp, struct page *spdm_req,
 		      struct tdx_page_array *spdm_out,
 		      u64 *spdm_req_or_out_len);
+u64 tdh_ide_stream_create(u64 stream_info, u64 spdm_id,
+			  struct tdx_page_array *stream_mt, u64 stream_ctrl,
+			  u64 rid_assoc1, u64 rid_assoc2,
+			  u64 addr_assoc1, u64 addr_assoc2,
+			  u64 addr_assoc3,
+			  u64 *stream_id,
+			  u64 *rp_ide_id);
+u64 tdh_ide_stream_block(u64 spdm_id, u64 stream_id);
+u64 tdh_ide_stream_delete(u64 spdm_id, u64 stream_id,
+			  struct tdx_page_array *stream_mt,
+			  unsigned int *nr_released, u64 *released_hpa);
+u64 tdh_ide_stream_km(u64 spdm_id, u64 stream_id, u64 operation,
+		      struct page *spdm_rsp, struct page *spdm_req,
+		      u64 *spdm_req_len);
 #else
 static inline void tdx_init(void) { }
 static inline int tdx_cpu_enable(void) { return -ENODEV; }
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 4784db2d1d92..d0a9694432de 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -66,6 +66,10 @@
 #define TDH_IOMMU_CLEAR			129
 #define TDH_SPDM_CREATE			130
 #define TDH_SPDM_DELETE			131
+#define TDH_IDE_STREAM_CREATE		132
+#define TDH_IDE_STREAM_BLOCK		133
+#define TDH_IDE_STREAM_DELETE		134
+#define TDH_IDE_STREAM_KM		135
 #define TDH_SPDM_CONNECT		142
 #define TDH_SPDM_DISCONNECT		143
 #define TDH_SPDM_MNG			144
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 02882c2ad177..72d836b25bd6 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2616,3 +2616,89 @@ u64 tdh_exec_spdm_mng(u64 spdm_id, u64 spdm_op, struct page *spdm_param,
 	return r;
 }
 EXPORT_SYMBOL_FOR_MODULES(tdh_exec_spdm_mng, "tdx-host");
+
+u64 tdh_ide_stream_create(u64 stream_info, u64 spdm_id,
+			  struct tdx_page_array *stream_mt, u64 stream_ctrl,
+			  u64 rid_assoc1, u64 rid_assoc2,
+			  u64 addr_assoc1, u64 addr_assoc2,
+			  u64 addr_assoc3,
+			  u64 *stream_id,
+			  u64 *rp_ide_id)
+{
+	struct tdx_module_args args = {
+		.rcx = stream_info,
+		.rdx = spdm_id,
+		.r8 = hpa_array_t_assign_raw(stream_mt),
+		.r9 = stream_ctrl,
+		.r10 = rid_assoc1,
+		.r11 = rid_assoc2,
+		.r12 = addr_assoc1,
+		.r13 = addr_assoc2,
+		.r14 = addr_assoc3,
+	};
+	u64 r;
+
+	tdx_clflush_page_array(stream_mt);
+
+	r = seamcall_saved_ret(TDH_IDE_STREAM_CREATE, &args);
+
+	*stream_id = args.rcx;
+	*rp_ide_id = args.rdx;
+
+	return r;
+}
+EXPORT_SYMBOL_FOR_MODULES(tdh_ide_stream_create, "tdx-host");
+
+u64 tdh_ide_stream_block(u64 spdm_id, u64 stream_id)
+{
+	struct tdx_module_args args = {
+		.rcx = spdm_id,
+		.rdx = stream_id,
+	};
+
+	return seamcall(TDH_IDE_STREAM_BLOCK, &args);
+}
+EXPORT_SYMBOL_FOR_MODULES(tdh_ide_stream_block, "tdx-host");
+
+u64 tdh_ide_stream_delete(u64 spdm_id, u64 stream_id,
+			  struct tdx_page_array *stream_mt,
+			  unsigned int *nr_released, u64 *released_hpa)
+{
+	struct tdx_module_args args = {
+		.rcx = spdm_id,
+		.rdx = stream_id,
+		.r8 = hpa_array_t_release_raw(stream_mt),
+	};
+	u64 r;
+
+	r = seamcall_ret(TDH_IDE_STREAM_DELETE, &args);
+	if (r != TDX_SUCCESS)
+		return r;
+
+	*nr_released = FIELD_GET(HPA_ARRAY_T_SIZE, args.rcx) + 1;
+	*released_hpa = FIELD_GET(HPA_ARRAY_T_PFN, args.rcx) << PAGE_SHIFT;
+
+	return r;
+}
+EXPORT_SYMBOL_FOR_MODULES(tdh_ide_stream_delete, "tdx-host");
+
+u64 tdh_ide_stream_km(u64 spdm_id, u64 stream_id, u64 operation,
+		      struct page *spdm_rsp, struct page *spdm_req,
+		      u64 *spdm_req_len)
+{
+	struct tdx_module_args args = {
+		.rcx = spdm_id,
+		.rdx = stream_id,
+		.r8 = operation,
+		.r9 = page_to_phys(spdm_rsp),
+		.r10 = page_to_phys(spdm_req),
+	};
+	u64 r;
+
+	r = seamcall_ret_ir_resched(TDH_IDE_STREAM_KM, &args);
+
+	*spdm_req_len = args.rcx;
+
+	return r;
+}
+EXPORT_SYMBOL_FOR_MODULES(tdh_ide_stream_km, "tdx-host");

---

## [31] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 30/31] coco/tdx-host: Implement IDE stream setup/teardown*

Implementation for a most straightforward Selective IDE stream setup.
Hard code all parameters for Stream Control Register. And no IDE Key
Refresh support.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 include/linux/pci-ide.h               |   2 +
 drivers/pci/ide.c                     |   5 +-
 drivers/virt/coco/tdx-host/tdx-host.c | 226 ++++++++++++++++++++++++++
 3 files changed, 231 insertions(+), 2 deletions(-)

diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
index 381a1bf22a95..f0c6975fd429 100644
--- a/include/linux/pci-ide.h
+++ b/include/linux/pci-ide.h
@@ -106,6 +106,8 @@ struct pci_ide {
 void pci_ide_set_nr_streams(struct pci_host_bridge *hb, u16 nr);
 struct pci_ide_partner *pci_ide_to_settings(struct pci_dev *pdev,
 					    struct pci_ide *ide);
+void pci_ide_stream_to_regs(struct pci_dev *pdev, struct pci_ide *ide,
+			    struct pci_ide_regs *regs);
 struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev);
 void pci_ide_stream_free(struct pci_ide *ide);
 int  pci_ide_stream_register(struct pci_ide *ide);
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index b35e8aba7ecb..1337608448c2 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -556,8 +556,8 @@ static void mem_assoc_to_regs(struct pci_bus_region *region,
  * @ide: registered IDE settings descriptor
  * @regs: output register values
  */
-static void pci_ide_stream_to_regs(struct pci_dev *pdev, struct pci_ide *ide,
-				   struct pci_ide_regs *regs)
+void pci_ide_stream_to_regs(struct pci_dev *pdev, struct pci_ide *ide,
+			    struct pci_ide_regs *regs)
 {
 	struct pci_ide_partner *settings = pci_ide_to_settings(pdev, ide);
 	int assoc_idx = 0;
@@ -586,6 +586,7 @@ static void pci_ide_stream_to_regs(struct pci_dev *pdev, struct pci_ide *ide,
 
 	regs->nr_addr = assoc_idx;
 }
+EXPORT_SYMBOL_GPL(pci_ide_stream_to_regs);
 
 /**
  * pci_ide_stream_setup() - program settings to Selective IDE Stream registers
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index d5072a68b81a..0f6056945788 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -72,6 +72,10 @@ struct tdx_tsm_link {
 	struct tdx_page_array *spdm_mt;
 	unsigned int dev_info_size;
 	void *dev_info_data;
+
+	struct pci_ide *ide;
+	struct tdx_page_array *stream_mt;
+	unsigned int stream_id;
 };
 
 static struct tdx_tsm_link *to_tdx_tsm_link(struct pci_tsm *tsm)
@@ -351,6 +355,219 @@ static void tdx_spdm_session_teardown(struct tdx_tsm_link *tlink)
 DEFINE_FREE(tdx_spdm_session_teardown, struct tdx_tsm_link *,
 	    if (!IS_ERR_OR_NULL(_T)) tdx_spdm_session_teardown(_T))
 
+enum tdx_ide_stream_km_op {
+	TDX_IDE_STREAM_KM_SETUP = 0,
+	TDX_IDE_STREAM_KM_REFRESH = 1,
+	TDX_IDE_STREAM_KM_STOP = 2,
+};
+
+static int tdx_ide_stream_km(struct tdx_tsm_link *tlink,
+			     enum tdx_ide_stream_km_op op)
+{
+	u64 r, out_msg_sz;
+	int ret;
+
+	do {
+		r = tdh_ide_stream_km(tlink->spdm_id, tlink->stream_id, op,
+				      tlink->in_msg, tlink->out_msg,
+				      &out_msg_sz);
+		ret = tdx_tsm_link_event_handler(tlink, r, out_msg_sz);
+	} while (ret == -EAGAIN);
+
+	return ret;
+}
+
+static struct tdx_tsm_link *
+tdx_ide_stream_key_program(struct tdx_tsm_link *tlink)
+{
+	int ret;
+
+	ret = tdx_ide_stream_km(tlink, TDX_IDE_STREAM_KM_SETUP);
+	if (ret)
+		return ERR_PTR(ret);
+
+	return tlink;
+}
+
+static void tdx_ide_stream_key_stop(struct tdx_tsm_link *tlink)
+{
+	tdx_ide_stream_km(tlink, TDX_IDE_STREAM_KM_STOP);
+}
+
+DEFINE_FREE(tdx_ide_stream_key_stop, struct tdx_tsm_link *,
+	    if (!IS_ERR_OR_NULL(_T)) tdx_ide_stream_key_stop(_T))
+
+static void sel_stream_block_regs(struct pci_dev *pdev, struct pci_ide *ide,
+				  struct pci_ide_regs *regs)
+{
+	struct pci_dev *rp = pcie_find_root_port(pdev);
+	struct pci_ide_partner *setting = pci_ide_to_settings(rp, ide);
+
+	/* only support address association for prefetchable memory */
+	setting->mem_assoc = (struct pci_bus_region) { 0, -1 };
+	pci_ide_stream_to_regs(rp, ide, regs);
+}
+
+#define STREAM_INFO_RP_DEVFN		GENMASK_ULL(7, 0)
+#define STREAM_INFO_TYPE		BIT_ULL(8)
+#define  STREAM_INFO_TYPE_LINK		0
+#define  STREAM_INFO_TYPE_SEL		1
+
+static struct tdx_tsm_link *tdx_ide_stream_create(struct tdx_tsm_link *tlink,
+						  struct pci_ide *ide)
+{
+	u64 stream_info, stream_ctrl;
+	u64 stream_id, rp_ide_id;
+	unsigned int nr_pages = tdx_sysinfo->connect.ide_mt_page_count;
+	struct pci_dev *pdev = tlink->pci.base_tsm.pdev;
+	struct pci_dev *rp = pcie_find_root_port(pdev);
+	struct pci_ide_regs regs;
+	u64 r;
+
+	struct tdx_page_array *stream_mt __free(tdx_page_array_free) =
+		tdx_page_array_create(nr_pages);
+	if (!stream_mt)
+		return ERR_PTR(-ENOMEM);
+
+	stream_info = FIELD_PREP(STREAM_INFO_RP_DEVFN, rp->devfn);
+	stream_info |= FIELD_PREP(STREAM_INFO_TYPE, STREAM_INFO_TYPE_SEL);
+
+	/*
+	 * For Selective IDE stream, below values must be 0:
+	 *   NPR_AGG/PR_AGG/CPL_AGG/CONF_REQ/ALGO/DEFAULT/STREAM_ID
+	 *
+	 * below values are configurable but now hardcode to 0:
+	 *   PCRC/TC
+	 */
+	stream_ctrl = FIELD_PREP(PCI_IDE_SEL_CTL_EN, 0) |
+		      FIELD_PREP(PCI_IDE_SEL_CTL_TX_AGGR_NPR, 0) |
+		      FIELD_PREP(PCI_IDE_SEL_CTL_TX_AGGR_PR, 0) |
+		      FIELD_PREP(PCI_IDE_SEL_CTL_TX_AGGR_CPL, 0) |
+		      FIELD_PREP(PCI_IDE_SEL_CTL_PCRC_EN, 0) |
+		      FIELD_PREP(PCI_IDE_SEL_CTL_CFG_EN, 0) |
+		      FIELD_PREP(PCI_IDE_SEL_CTL_ALG, 0) |
+		      FIELD_PREP(PCI_IDE_SEL_CTL_TC, 0) |
+		      FIELD_PREP(PCI_IDE_SEL_CTL_ID, 0);
+
+	sel_stream_block_regs(pdev, ide, &regs);
+	if (regs.nr_addr != 1)
+		return ERR_PTR(-EFAULT);
+
+	r = tdh_ide_stream_create(stream_info, tlink->spdm_id,
+				  stream_mt, stream_ctrl,
+				  regs.rid1, regs.rid2, regs.addr[0].assoc1,
+				  regs.addr[0].assoc2, regs.addr[0].assoc3,
+				  &stream_id, &rp_ide_id);
+	if (r)
+		return ERR_PTR(-EFAULT);
+
+	tlink->stream_id = stream_id;
+	tlink->stream_mt = no_free_ptr(stream_mt);
+
+	pci_dbg(pdev, "%s stream id 0x%x rp ide_id 0x%llx\n", __func__,
+		tlink->stream_id, rp_ide_id);
+	return tlink;
+}
+
+static void tdx_ide_stream_delete(struct tdx_tsm_link *tlink)
+{
+	struct pci_dev *pdev = tlink->pci.base_tsm.pdev;
+	unsigned int nr_released;
+	u64 released_hpa, r;
+
+	r = tdh_ide_stream_block(tlink->spdm_id, tlink->stream_id);
+	if (r) {
+		pci_err(pdev, "ide stream block fail 0x%llx\n", r);
+		goto leak;
+	}
+
+	r = tdh_ide_stream_delete(tlink->spdm_id, tlink->stream_id,
+				  tlink->stream_mt, &nr_released,
+				  &released_hpa);
+	if (r) {
+		pci_err(pdev, "ide stream delete fail 0x%llx\n", r);
+		goto leak;
+	}
+
+	if (tdx_page_array_ctrl_release(tlink->stream_mt, nr_released,
+					released_hpa)) {
+		pci_err(pdev, "fail to release IDE stream_mt pages\n");
+		goto leak;
+	}
+
+	return;
+
+leak:
+	tdx_page_array_ctrl_leak(tlink->stream_mt);
+}
+
+DEFINE_FREE(tdx_ide_stream_delete, struct tdx_tsm_link *,
+	    if (!IS_ERR_OR_NULL(_T)) tdx_ide_stream_delete(_T))
+
+static struct tdx_tsm_link *tdx_ide_stream_setup(struct tdx_tsm_link *tlink)
+{
+	struct pci_dev *pdev = tlink->pci.base_tsm.pdev;
+	int ret;
+
+	struct pci_ide *ide __free(pci_ide_stream_release) =
+		pci_ide_stream_alloc(pdev);
+	if (!ide)
+		return ERR_PTR(-ENOMEM);
+
+	/* Configure IDE capability for RP & get stream_id */
+	struct tdx_tsm_link *tlink_create __free(tdx_ide_stream_delete) =
+		tdx_ide_stream_create(tlink, ide);
+	if (IS_ERR(tlink_create))
+		return tlink_create;
+
+	ide->stream_id = tlink->stream_id;
+	ret = pci_ide_stream_register(ide);
+	if (ret)
+		return ERR_PTR(ret);
+
+	/*
+	 * Configure IDE capability for target device
+	 *
+	 * Some test devices work only with DEFAULT_STREAM enabled. For
+	 * simplicity, enable DEFAULT_STREAM for all devices. A future decent
+	 * solution may be to have a quirk table to specify which devices need
+	 * DEFAULT_STREAM.
+	 */
+	ide->partner[PCI_IDE_EP].default_stream = 1;
+	pci_ide_stream_setup(pdev, ide);
+
+	/* Key Programming for RP & target device, enable IDE stream for RP */
+	struct tdx_tsm_link *tlink_program __free(tdx_ide_stream_key_stop) =
+		tdx_ide_stream_key_program(tlink);
+	if (IS_ERR(tlink_program))
+		return tlink_program;
+
+	ret = tsm_ide_stream_register(ide);
+	if (ret)
+		return ERR_PTR(ret);
+
+	/* Enable IDE stream for target device */
+	ret = pci_ide_stream_enable(pdev, ide);
+	if (ret)
+		return ERR_PTR(ret);
+
+	retain_and_null_ptr(tlink_create);
+	retain_and_null_ptr(tlink_program);
+	tlink->ide = no_free_ptr(ide);
+
+	return tlink;
+}
+
+static void tdx_ide_stream_teardown(struct tdx_tsm_link *tlink)
+{
+	tdx_ide_stream_key_stop(tlink);
+	tdx_ide_stream_delete(tlink);
+	pci_ide_stream_release(tlink->ide);
+}
+
+DEFINE_FREE(tdx_ide_stream_teardown, struct tdx_tsm_link *,
+	    if (!IS_ERR_OR_NULL(_T)) tdx_ide_stream_teardown(_T))
+
 static int tdx_tsm_link_connect(struct pci_dev *pdev)
 {
 	struct tdx_tsm_link *tlink = to_tdx_tsm_link(pdev->tsm);
@@ -362,7 +579,15 @@ static int tdx_tsm_link_connect(struct pci_dev *pdev)
 		return PTR_ERR(tlink_spdm);
 	}
 
+	struct tdx_tsm_link *tlink_ide __free(tdx_ide_stream_teardown) =
+		tdx_ide_stream_setup(tlink);
+	if (IS_ERR(tlink_ide)) {
+		pci_err(pdev, "fail to setup ide stream\n");
+		return PTR_ERR(tlink_ide);
+	}
+
 	retain_and_null_ptr(tlink_spdm);
+	retain_and_null_ptr(tlink_ide);
 
 	return 0;
 }
@@ -371,6 +596,7 @@ static void tdx_tsm_link_disconnect(struct pci_dev *pdev)
 {
 	struct tdx_tsm_link *tlink = to_tdx_tsm_link(pdev->tsm);
 
+	tdx_ide_stream_teardown(tlink);
 	tdx_spdm_session_teardown(tlink);
 }

---

## [32] Xu Yilun — 2026-03-28
*Subject: [PATCH v2 31/31] coco/tdx-host: Finally enable SPDM session and IDE Establishment*

The basic SPDM session and IDE functionalities are all implemented,
enable them.

Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/virt/coco/tdx-host/tdx-host.c | 5 ++---
 1 file changed, 2 insertions(+), 3 deletions(-)

diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 0f6056945788..7800afb0893d 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -883,7 +883,7 @@ static int tdx_iommu_enable_all(void)
 	return ret;
 }
 
-static int __maybe_unused tdx_connect_init(struct device *dev)
+static int tdx_connect_init(struct device *dev)
 {
 	struct tsm_dev *link;
 	int ret;
@@ -914,8 +914,7 @@ static int __maybe_unused tdx_connect_init(struct device *dev)
 
 static int tdx_host_probe(struct faux_device *fdev)
 {
-	/* TODO: do tdx_connect_init() when it is fully implemented. */
-	return 0;
+	return tdx_connect_init(&fdev->dev);
 }
 
 static struct faux_device_ops tdx_host_ops = {

---

## [33] Edgecombe, Rick P — 2026-03-27
*Subject: Re: [PATCH v2 01/31] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

On Sat, 2026-03-28 at 00:01 +0800, Xu Yilun wrote:
> From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
> 

I think it is missing Kai's RB from sys disable v1, and your sign off.

This patch is in three series now, hence the long SOB chain. And I think it is
also the only KVM touch point in the series. If sys disable gets merged ahead of
time it can be dropped. But if there is any lag there we should see if Dave will
just take it instead of trying to keep it in sync.

---

## [34] Edgecombe, Rick P — 2026-03-27
*Subject: Re: [PATCH v2 02/31] x86/virt/tdx: Move bit definitions of
 TDX_FEATURES0 to public header*

On Sat, 2026-03-28 at 00:01 +0800, Xu Yilun wrote:
> Move bit definitions of TDX_FEATURES0 to TDX core public header.

Patch seems reasonable, but not sure about the "public header" language. Maybe
more widely accessibly header? Or a better name?

> 
> Kernel users get TDX_FEATURES0 bitmap via tdx_get_sysinfo(). It is

---

## [35] Dan Williams — 2026-03-27
*Subject: Re: [PATCH v2 01/31] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

Edgecombe, Rick P wrote:
> On Sat, 2026-03-28 at 00:01 +0800, Xu Yilun wrote:
> > From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

Thanks for the heads up.

I think if we are committed to the idea that some TDX related sets may
go through different upstreams and some of those sets have a small
handful of common infrastructure patches then there are a few options.
Either have someone keep an eye for these and publish stable-commits for
folks to share, accept that duplication collisions will happen and
rebase when they do, or accept that duplication collisions be ok with
that small bit of mess showing up in the history.

In this case, for the tsm.git#staging branch, I will replace this with a
fresh application of this:

https://lore.kernel.org/all/20260323-fuller_tdx_kexec_support-v2-1-87a36409e051@intel.com/

Yilun, going forward, if you borrow a patch from another set, be sure to
both add your own signed-off-by, but also a:

Link: https://patch.msgid.link/20260323-fuller_tdx_kexec_support-v2-1-87a36409e051@intel.com

...to make it extra clear you are including a patch that is already on
the list in another set.

I suspect that by the time this set is ready to move from
tsm.git#staging to tsm.git#next a stable commit-id may be available for
a rebase.

---

## [36] Edgecombe, Rick P — 2026-03-28
*Subject: Re: [PATCH v2 03/31] x86/virt/tdx: Add tdx_page_array helpers for new
 TDX Module objects*

Hi,

In general I'm struggling to understand the design decisions. It seems a very
specific design and quite a bit of code to manage an array of pages. Questions
below.

On Sat, 2026-03-28 at 00:01 +0800, Xu Yilun wrote:
> Add struct tdx_page_array definition for new TDX Module object
> types - HPA_ARRAY_T and HPA_LIST_INFO. 

This is unfortunate. I see you agree in the comments.

> 
> They are used as input/output

This is kind of verbose for what it seems to be trying to say. It's just that
these types can be input or output params. The TDX module could hold on to the
pages for a long time, or just transiently. For that latter part I think you are
trying to say sometimes they need flushing and sometimes they don't?

> 
> The 2 structures both need a 'root page' which contains a list of HPAs.

"singleton mode"? What is it? If it's the case of not needing populate loop, it
probably deserves more explanation. I'm not sure, but the populate loop seems to
drive a lot of the struct design?

> 
> Another small difference is HPA_LIST_INFO contains a 'first entry' field

Not clear what this is talking about. But I'm starting to wonder if we should be
so bold to claim that the differences between the types really simplify the
host. 

> 
> Typical usages of the tdx_page_array:

So release is mostly needed because of the need to do the wbvind seamcall? And
unlike tdx_page_array_free() it returns an error in case that fails. Or other
sanity checking. But all the callers do the same thing on error, call
tdx_page_array_ctrl_leak().

Just wondering if we could simplify it somehow. There are two helpers and the
caller has to know which one to call based on SEAMCALL specifics. What if the
seamcall wrapper set a bit in the page array while passing it out. The bit would
specify to the helper if it needs to do wbinvd or not. Then the wrappers could
encapsulate the type of free needed and not rely on the caller to know. And we
only need to have one function for it instead of two.


BTW, do we expect errors from the tdh_phymem_page_wbinvd_hkid() calls here? How
could the BUSY happen? If we don't think it can happen in normal runtime, we
could just warn and skip the special leak logic. In KVM side there is a place
where we can't really handle it for the wbinvd calls. And one where we can. If
we need a ton of code to handle a bug somewhere (on kernel side or TDX module),
it seems too defensive to me. At least it's not in sync with the rest of TDX.

Especially the quite large tdx_page_array_validate_release() logic should need a
justification that there is something very tricky that needs all this checking.

But maybe you can explain what the special risk is.

> 
> 3. Exchange data blobs:

pages is going to be an array of struct pointers, and root is a single page of
PA's that gets re-used to copy and pass the PA's to the TDX module. Why do we
need both? Like just keep an array of PA's that would be the same size as the
struct page array. And not need the populate loop? 

Pausing for now. Still looking through the callers and it's the end of the day.

---

## [37] kernel test robot — 2026-03-29
*Subject: Re: [PATCH v2 19/31] iommu/vt-d: Reserve the MSB domain ID bit for
 the TDX module*

Hi Xu,

kernel test robot noticed the following build warnings:

[auto build test WARNING on 11439c4635edd669ae435eec308f4ab8a0804808]

url:    https://github.com/intel-lab-lkp/linux/commits/Xu-Yilun/x86-tdx-Move-all-TDX-error-defines-into-asm-shared-tdx_errno-h/20260328-151524
base:   11439c4635edd669ae435eec308f4ab8a0804808
patch link:    https://lore.kernel.org/r/20260327160132.2946114-20-yilun.xu%40linux.intel.com
patch subject: [PATCH v2 19/31] iommu/vt-d: Reserve the MSB domain ID bit for the TDX module
config: i386-randconfig-141-20260328 (https://download.01.org/0day-ci/archive/20260329/202603290006.za7iiDgF-lkp@intel.com/config)
compiler: clang version 20.1.8 (https://github.com/llvm/llvm-project 87f0227cb60147a26a1eeb4fb06e3b505e9c7261)
smatch: v0.5.0-9004-gb810ac53
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20260329/202603290006.za7iiDgF-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202603290006.za7iiDgF-lkp@intel.com/

All warnings (new ones prefixed by >>, old ones prefixed by <<):

>> WARNING: modpost: vmlinux: section mismatch in reference: iommu_max_domain_id+0x55 (section: .text.iommu_max_domain_id) -> acpi_table_parse_keyp (section: .init.text)

---

## [38] kernel test robot — 2026-03-29
*Subject: Re: [PATCH v2 19/31] iommu/vt-d: Reserve the MSB domain ID bit for
 the TDX module*

Hi Xu,

kernel test robot noticed the following build warnings:

[auto build test WARNING on 11439c4635edd669ae435eec308f4ab8a0804808]

url:    https://github.com/intel-lab-lkp/linux/commits/Xu-Yilun/x86-tdx-Move-all-TDX-error-defines-into-asm-shared-tdx_errno-h/20260328-151524
base:   11439c4635edd669ae435eec308f4ab8a0804808
patch link:    https://lore.kernel.org/r/20260327160132.2946114-20-yilun.xu%40linux.intel.com
patch subject: [PATCH v2 19/31] iommu/vt-d: Reserve the MSB domain ID bit for the TDX module
config: x86_64-defconfig (https://download.01.org/0day-ci/archive/20260329/202603290317.BVIn0aoy-lkp@intel.com/config)
compiler: gcc-14 (Debian 14.2.0-19) 14.2.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20260329/202603290317.BVIn0aoy-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202603290317.BVIn0aoy-lkp@intel.com/

All warnings (new ones prefixed by >>, old ones prefixed by <<):

>> WARNING: modpost: vmlinux: section mismatch in reference: alloc_iommu.cold+0x49 (section: .text.unlikely) -> acpi_table_parse_keyp (section: .init.text)

---

## [39] Xu Yilun — 2026-03-30
*Subject: Re: [PATCH v2 01/31] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

> In this case, for the tsm.git#staging branch, I will replace this with a
> fresh application of this:

This is the exact patch I picked, but Kai's RB is in previous version

https://lore.kernel.org/all/20260307010358.819645-2-rick.p.edgecombe@intel.com/

and b4 didn't catch it. I think should add his RB manually.

> 
> Yilun, going forward, if you borrow a patch from another set, be sure to

Yes. I listed the link in cover letter, but yes add it here should be
clearer and necessary.

> 
> I suspect that by the time this set is ready to move from

---

## [40] Xu Yilun — 2026-03-30
*Subject: Re: [PATCH v2 01/31] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

> I think it is missing Kai's RB from sys disable v1, and your sign off.

Ah, yes. I picked from the latest post:

https://lore.kernel.org/all/20260323-fuller_tdx_kexec_support-v2-1-87a36409e051@intel.com/

But didn't realize the older thread has different RB set and b4 didn't
catch, will add it manually.

I'll also add my sign off.

Thanks

---

## [41] Xu Yilun — 2026-03-30
*Subject: Re: [PATCH v2 02/31] x86/virt/tdx: Move bit definitions of
 TDX_FEATURES0 to public header*

On Fri, Mar 27, 2026 at 11:45:39PM +0000, Edgecombe, Rick P wrote:
> On Sat, 2026-03-28 at 00:01 +0800, Xu Yilun wrote:
> > Move bit definitions of TDX_FEATURES0 to TDX core public header.

Yes, I try to make it more explicit, is it better:

    x86/virt/tdx: Move TDX_FEATURES0 bit defines to arch x86 header

    Move TDX_FEATURES0 bit definitions to arch x86 header.

    ...

---

## [42] Xu Yilun — 2026-03-30
*Subject: Re: [PATCH v2 03/31] x86/virt/tdx: Add tdx_page_array helpers for
 new TDX Module objects*

> On Sat, 2026-03-28 at 00:01 +0800, Xu Yilun wrote:
> > Add struct tdx_page_array definition for new TDX Module object

Yes, basically they are defining the same concept, behave mostly the same
but some differences...

> 
> > 

I assume if you feel the explanation of "what is control page" is off
track. I added it cause the term firstly appears in x86 (only in KVM
TDX previously), and people ask the definition:

https://lore.kernel.org/all/cfcfb160-fcd2-4a75-9639-5f7f0894d14b@intel.com/

> these types can be input or output params. The TDX module could hold on to the
> pages for a long time, or just transiently.

Mm.. I'm trying to ramp up on the kernel API level flow:

For control pages, it would be hold by TDX Module long time, so host
inputs the page array, later TDX Module outputs the page array back.
Host need to verify the outputs.

For shared pages, TDX Module's accessing is transient in one SEAMCALL,
so only as input, TDX Module never needs to output the array.

I think the verboseness makes the following pseudo code easier to
understand.

> For that latter part I think you are
> trying to say sometimes they need flushing and sometimes they don't?

Yeah.
control pages => long term => host verifies and releases => flush on release
shared pages => transient => no verify and releases => no flush

Maybe I should mention the flushing is already covered by releasing
kAPI.
> 
> > 

It is the SEAMCALL level detail for HPA_ARRAY_T. It is literally as
explained above - the HPA field should be filled by page0, not root page.

> probably deserves more explanation. I'm not sure, but the populate loop seems to
> drive a lot of the struct design?

The caller is not aware of singleton mode. Actually, I'm trying to make
the tdx_page_array independent of HPA_ARRAY_T or HPA_LIST_INFO details
when allocating/populating, root page is still populated even not needed
for singleton mode. The differences only happen when collaping the struct
into u64 SEAMCALL parameters.

> 
> > 

I'm talking about another SEAMCALL level detail. Sometimes TDX Module
got interrupted in the middle of page array processing, it needs an
anchor to resuming from where it stops, TDX Module record the anchor
in the 'first entry'.

By illustrating these SEAMCALL level differences, I want to explain
they don't impact the general SW flow and kAPI cares about them
internally.

Yes in POC code we do write dedicated code for each type, but it ends up
with plenty of similar logics on caller side about root page
manipulation. By now, the differences are not much, but I think we
should not write copies for every type, we should stop new types.

Please allow me to stop here, will continue later...

Thanks.

---

## [43] Nikolay Borisov — 2026-03-30
*Subject: Re: [PATCH v2 03/31] x86/virt/tdx: Add tdx_page_array helpers for new
 TDX Module objects*

On 27.03.26 г. 18:01 ч., Xu Yilun wrote:
<snip>

> +/**
> + * tdx_page_array_ctrl_leak() - Leak data pages and free the container

This instantly raises a red flag if by design an API has the ability to 
simply leak memory. Under what conditions this might be required, can't 
we do something to gracefully handle the case when pages cannot be freed 
instantly, i.e queued freeing or some such ? Simply leaking them is a 
big NO.

> +
> +static bool tdx_page_array_validate_release(struct tdx_page_array *array,

This function is only ever called with offset of 0, if it's intended to 
be used later then I'd rather see this argument added in an explicit 
patch with rationale why it's needed.

> +					    unsigned int nr_released,
> +					    u64 released_hpa)


> +<snip>

---

## [44] Nikolay Borisov — 2026-03-30
*Subject: Re: [PATCH v2 04/31] x86/virt/tdx: Support allocating contiguous
 pages for tdx_page_array*

On 27.03.26 г. 18:01 ч., Xu Yilun wrote:
> The current tdx_page_array implementation allocates scattered order-0
> pages. However, some TDX Module operations benefit from contiguous

This interface seems cumbersome, since you will always have separate 
allocation paths:

Contig, Bulk and Iommu mt pages let's just keep them separate. I.e the 
flow should be:

1. Do common allocation by calling tdx_page_array_alloc (you aren't 
passing the alloc function) you just get a bare-bones tdx_page_array struct

2. Do the specific allocation in either :

tdx_page_array_create - for the bulk case
tdx_page_array_alloc_contig - for the contig case
tdx_page_array_create_iommu_mt - for the iommu case. Here you can open 
code tdx_alloc_pages_iommu_mt.

And keep the specific clearly separate in each function.

>   {
>   	struct tdx_page_array *array = NULL;

---

## [45] Nikolay Borisov — 2026-03-30
*Subject: Re: [PATCH v2 06/31] x86/virt/tdx: Read global metadata for TDX
 Module Extensions/Connect*

On 27.03.26 г. 18:01 ч., Xu Yilun wrote:
> Add reading of the global metadata for TDX Module Extensions & TDX
> Connect. Add them in a batch as TDX Connect is currently the only user

nit: This is likely generated by a script/llm because I see no other 
explanation why !ret is being checked here...

> +		sysinfo_ext->memory_pool_required_pages = val;
> +	if (!ret && !(ret = read_sys_metadata_field(0x3100000100000001, &val)))

Ditto
<snip>

---

## [46] Xu Yilun — 2026-03-30
*Subject: Re: [PATCH v2 03/31] x86/virt/tdx: Add tdx_page_array helpers for
 new TDX Module objects*

> > Typical usages of the tdx_page_array:
> > 

I like the idea, I can have a try.

But we may need more than a bit to finish the release. On release some
SEAMCALLs return the released HPA list and host checks they are sane,
otherwise leak. We need to also record these info in the struct.

> 
> 

No, it can't happen in normal runtime.

> could the BUSY happen? If we don't think it can happen in normal runtime, we
> could just warn and skip the special leak logic. In KVM side there is a place

But we do leak control pages when wbinvd fails, or even when
tdh_phymem_page_reclaim() fails. So anyway we need leak logic, is it?
Is it a little insane if we failed to reclaim and return the private
page to kernel?

> we need a ton of code to handle a bug somewhere (on kernel side or TDX module),
> it seems too defensive to me. At least it's not in sync with the rest of TDX.

I don't see the special risk, actually I don't even see the releasing
failed once.

But we do check the return value of tdh_phymem_page_reclaim() for a
single ctrl page releasing. It is just we also check a list of ctrl
pages releasing. The check becomes naturally complex, e.g., if the
released number matches, if every HPA in the list matches ...

...

> > +struct tdx_page_array {
> > +	/* public: */

We need Linux language, struct page *, for alloc and free. Also need
TDX Module language - PA list - for SEAMCALLs. So IIUC, the page to PA
populating won't disappear on allocation, the PA to page populating
would appear on free.

Besides, host may need to vmap and access the (shared) pages.

Thanks,
Yilun

---

## [47] Edgecombe, Rick P — 2026-03-30
*Subject: Re: [PATCH v2 03/31] x86/virt/tdx: Add tdx_page_array helpers for new
 TDX Module objects*

On Mon, 2026-03-30 at 18:25 +0800, Xu Yilun wrote:
> > On Sat, 2026-03-28 at 00:01 +0800, Xu Yilun wrote:
> > > Add struct tdx_page_array definition for new TDX Module object

I meant it more generally.

> 
> > these types can be input or output params. The TDX module could hold on to

I hear:
 1. Long time vs short time
 2. Accessed as private vs "shared"

I think (2) is the important point, right? Why does (1) matter?

> > 
> > > 

It seems tdx_page_array combines two concepts. An array of pages, and the method
that the pages get handed to the TDX module. What if we broke apart these
concepts?

> 
> > 

Hmm, doesn't it seem like this is quickly becoming complicated though, to
combine all the different types together? And it seems there are more coming
that people want to add to this.

> 
> Please allow me to stop here, will continue later...

---

## [48] Edgecombe, Rick P — 2026-03-30
*Subject: Re: [PATCH v2 11/31] x86/virt/tdx: Make TDX Module initialize
 Extensions*

On Sat, 2026-03-28 at 00:01 +0800, Xu Yilun wrote:
> After providing all required memory to TDX Module, initialize the
> Extensions via TDH.EXT.INIT, and then Extension-SEAMCALLs can be used.

I don't know if we are going to want to sprinkle these over every new feature
until the end of time. If this feature will only show up on the platforms with
this erratum, then I say we just drop the check.

> +
>  	nr_pages = tdx_sysinfo.ext.memory_pool_required_pages;

How does this scenario happen exactly? And why not check it above at the
beginning? Before the allocation, so it doesn't need to free.

Is there a scenario where the memory needs to be given, but the extension is
already inited?

> +	 */
> +	if (tdx_sysinfo.ext.ext_required) {

For the error path we don't need to be efficient. But also why does it assume
tdx_ext_init() can touch the pages, but tdx_ext_mem_add() can't?


> +		wbinvd_on_all_cpus();
>  out_ext_mem:

---

## [49] Edgecombe, Rick P — 2026-03-30
*Subject: Re: [PATCH v2 10/31] x86/virt/tdx: Add extra memory to TDX Module for
 Extensions*

On Sat, 2026-03-28 at 00:01 +0800, Xu Yilun wrote:
> Adding more memory to TDX Module is the first step to enable Extensions.
> 

It doesn't clflush the page array, it clflushes the current populate chunk. Hmm.
Does it suggest that the page array and the format for handing them to the TDX
module are two different things?

> +{
> +	for (int i = 0; i < array->nents; i++)

For this case of populate it seems like it would be ok to keep an array of PA's
instead of an array of struct pages. Not sure on it yet.

> +
> +		ret = tdx_ext_mem_add(ext_mem);

Is this ever expected? Extensions are supported, but require no pages?

> +	if (nr_pages) {
> +		ext_mem = tdx_page_array_alloc_contig(nr_pages);

This looks very weird to call "leak" in the success path.

> +
> +	pr_info("%lu KB allocated for TDX Module Extensions\n",

---

## [50] Edgecombe, Rick P — 2026-03-30
*Subject: Re: [PATCH v2 05/31] x86/virt/tdx: Extend tdx_page_array to support
 IOMMU_MT*

On Sat, 2026-03-28 at 00:01 +0800, Xu Yilun wrote:
> IOMMU_MT is another TDX Module defined structure similar to HPA_ARRAY_T
> and HPA_LIST_INFO. The difference is it requires multi-order contiguous

To me it seems like this can't really be called a page array any more. The first
two u64's are too special. Instead it's a special one-off ABI format passed via
a page.

BTW, I can't find TDH.IOMMU.SETUP in the docs. Any pointers?

> +
> +	return 0;

Consider the amount of tricks that are needed to coax the tdx_page_array to
populate the handoff page as needed. It adds 2 pages here, then subtracts them
later in the callback. Then tweaks the pa in tdx_page_array_populate() to add
the length...

> +	struct tdx_page_array *array;
> +	int populated;

---

## [51] Edgecombe, Rick P — 2026-03-30
*Subject: Re: [PATCH v2 03/31] x86/virt/tdx: Add tdx_page_array helpers for new
 TDX Module objects*

On Mon, 2026-03-30 at 23:47 +0800, Xu Yilun wrote:
> > pages is going to be an array of struct pointers, and root is a single page
> > of

Not sure what you mean by this.

> 
> Besides, host may need to vmap and access the (shared) pages.

Some code someday may need to convert a PA to another format? Is that it?
Doesn't seem like big problem.

But I'm not sure about this idea yet.

---

## [52] Dave Hansen — 2026-03-30
*Subject: Re: [PATCH v2 01/31] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

On 3/27/26 09:01, Xu Yilun wrote:
> Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
> [enhance log]

This is missing a SoB from the person sending the patch.

Honestly, for something coming all from one company, I'd just prefer
that folks simplify the tale of woe about how a patch came to be
written. Just axe the SoB's and put one on it. Credit folks with a blurb
in the changelog if you have to.

---

## [53] Tony Lindgren — 2026-03-31
*Subject: Re: [PATCH v2 03/31] x86/virt/tdx: Add tdx_page_array helpers for
 new TDX Module objects*

On Mon, Mar 30, 2026 at 11:25:08PM +0000, Edgecombe, Rick P wrote:
> On Mon, 2026-03-30 at 18:25 +0800, Xu Yilun wrote:
> > Yes in POC code we do write dedicated code for each type, but it ends up

Most of the list entry types are the same with just some bits unused.

Regards,

Tony

---

## [54] Baolu Lu — 2026-03-31
*Subject: Re: [PATCH v2 19/31] iommu/vt-d: Reserve the MSB domain ID bit for
 the TDX module*

On 3/29/26 00:57, kernel test robot wrote:
> kernel test robot noticed the following build warnings:
> 


acpi_table_parse_keyp() is marked as __init. But this patch causes the
intel iommu driver to call it from a runtime function.

int __init_or_acpilib
acpi_table_parse_keyp(enum acpi_keyp_type id,
                       acpi_tbl_entry_handler_arg handler_arg, void *arg)
{
         return __acpi_table_parse_entries(ACPI_SIG_KEYP,
                                           sizeof(struct 
acpi_table_keyp), id,
                                           NULL, handler_arg, arg, 0);
}

One way to solve this might be parsing the table once in the __init
context and store the result in variable that could be used after boot.

How about the following additional change (untested)?

diff --git a/drivers/iommu/intel/dmar.c b/drivers/iommu/intel/dmar.c
index 097c4a90302f..0b384a58a3a0 100644
--- a/drivers/iommu/intel/dmar.c
+++ b/drivers/iommu/intel/dmar.c
@@ -63,6 +63,7 @@ LIST_HEAD(dmar_drhd_units);
  struct acpi_table_header * __initdata dmar_tbl;
  static int dmar_dev_scope_status = 1;
  static DEFINE_IDA(dmar_seq_ids);
+static bool tdx_tvm_usable __ro_after_init;

  static int alloc_iommu(struct dmar_drhd_unit *drhd);
  static void free_iommu(struct intel_iommu *iommu);
@@ -915,6 +916,17 @@ dmar_validate_one_drhd(struct acpi_dmar_header 
*entry, void *arg)
  	return 0;
  }

+static void __init intel_iommu_check_tdxc_enhancement(void)
+{
+	int tvm_usable = 0;
+	int ret;
+
+	ret = acpi_table_parse_keyp(ACPI_KEYP_TYPE_CONFIG_UNIT,
+				    keyp_config_unit_tvm_usable, &tvm_usable);
+	if (ret >= 0)
+		tdx_tvm_usable = !!tvm_usable;
+}
+
  void __init detect_intel_iommu(void)
  {
  	int ret;
@@ -923,6 +935,8 @@ void __init detect_intel_iommu(void)
  		.ignore_unhandled = true,
  	};

+	intel_iommu_check_tdxc_enhancement();
+
  	down_write(&dmar_global_lock);
  	ret = dmar_table_detect();
  	if (!ret)
@@ -1046,24 +1060,6 @@ static int keyp_config_unit_tvm_usable(union 
acpi_subtable_headers *header,
  	return 0;
  }

-static bool platform_is_tdxc_enhanced(void)
-{
-	static int tvm_usable = -1;
-	int ret;
-
-	/* only need to parse once */
-	if (tvm_usable != -1)
-		return !!tvm_usable;
-
-	tvm_usable = 0;
-	ret = acpi_table_parse_keyp(ACPI_KEYP_TYPE_CONFIG_UNIT,
-				    keyp_config_unit_tvm_usable, &tvm_usable);
-	if (ret < 0)
-		tvm_usable = 0;
-
-	return !!tvm_usable;
-}
-
  static unsigned long iommu_max_domain_id(struct intel_iommu *iommu)
  {
  	unsigned long ndoms = cap_ndoms(iommu->cap);
@@ -1075,7 +1071,7 @@ static unsigned long iommu_max_domain_id(struct 
intel_iommu *iommu)
  	 * the VMM’s DID setting, reserving the MSB bit for the TDX module. The
  	 * TDX module always sets this reserved bit on the trusted DMA table.
  	 */
-	if (ecap_tdxc(iommu->ecap) && platform_is_tdxc_enhanced()) {
+	if (ecap_tdxc(iommu->ecap) && tdx_tvm_usable) {
  		pr_info_once("Most Significant Bit of domain ID reserved.\n");
  		return ndoms >> 1;
  	}

Thanks,
baolu

---

## [55] Xu Yilun — 2026-03-31
*Subject: Re: [PATCH v2 03/31] x86/virt/tdx: Add tdx_page_array helpers for
 new TDX Module objects*

On Mon, Mar 30, 2026 at 11:57:11PM +0000, Edgecombe, Rick P wrote:
> On Mon, 2026-03-30 at 23:47 +0800, Xu Yilun wrote:
> > > pages is going to be an array of struct pointers, and root is a single page

I mean host use struct page * for memory allocation and free. If we only
keep the PA list, we still need to convert PAs back to struct page * and
free.

> 
> > 

No, I don't convert a PA to something else. PA list is only for
SEAMCALLs.

Now we use vm_map_ram(array->pages, ...) to map the shared pages,
that's another reason I want to keep the struct page ** in
struct tdx_page_array.

Anyway we use struct page ** for kernel memory management in several
cases, keeping the struct page ** avoids PA -> page populating.

> Doesn't seem like big problem.
>

---

## [56] Nikolay Borisov — 2026-03-31
*Subject: Re: [PATCH v2 08/31] x86/virt/tdx: Configure TDX Module with optional
 TDX Connect feature*

On 27.03.26 г. 18:01 ч., Xu Yilun wrote:
> TDX Module supports optional TDX features (e.g. TDX Connect & TDX Module
> Extensions) that won't be enabled by default. It extends TDH.SYS.CONFIG

Since newer versions of tdx module apis are backwards compatible with 
older ones, and v0 are actually deprecated why have both definitions?


<snip>

---

## [57] Nikolay Borisov — 2026-03-31
*Subject: Re: [PATCH v2 10/31] x86/virt/tdx: Add extra memory to TDX Module for
 Extensions*

On 27.03.26 г. 18:01 ч., Xu Yilun wrote:
> Adding more memory to TDX Module is the first step to enable Extensions.
> 

shouldn't the actual number of entries be adjusted as per offset, 
similarly to how 'nents' in tdx_page_array_validate_release is calculated?


<snip>

---

## [58] Xu Yilun — 2026-03-31
*Subject: Re: [PATCH v2 03/31] x86/virt/tdx: Add tdx_page_array helpers for
 new TDX Module objects*

On Mon, Mar 30, 2026 at 04:31:43PM +0300, Nikolay Borisov wrote:
> 
> 

OK. With the discussion in this thread, I tend to remove this leak API.

> simply leak memory. Under what conditions this might be required, can't we
> do something to gracefully handle the case when pages cannot be freed

It was intended to be called when failing to reclaim pages from secure
firmware, maybe because of firmware bug. In this case kernel has no idea
what to do. Leaking is a last resort here, don't expect things still work.

---

## [59] Xu Yilun — 2026-03-31
*Subject: Re: [PATCH v2 04/31] x86/virt/tdx: Support allocating contiguous
 pages for tdx_page_array*

> >   static struct tdx_page_array *
> > -tdx_page_array_alloc(unsigned int nr_pages)

Thank for the suggestion. There are also other concerns in this thread,
but I'll take this into consideration.

---

## [60] Xu Yilun — 2026-03-31
*Subject: Re: [PATCH v2 05/31] x86/virt/tdx: Extend tdx_page_array to support
 IOMMU_MT*

> > +static int tdx_alloc_pages_iommu_mt(unsigned int nr_pages, struct page **pages,
> > +				    void *data)

https://cdrdv2.intel.com/v1/dl/getContent/858625

> 
> > +

mm.. The tricky part is the specific memory requirement/allocation, the
common part is the pa list contained in a root page. Maybe we only model
the later, let the specific user does the memory allocation. Is that
closer to your "break concepts apart" idea?

> 
> > +	struct tdx_page_array *array;

---

## [61] Xu Yilun — 2026-03-31
*Subject: Re: [PATCH v2 06/31] x86/virt/tdx: Read global metadata for TDX
 Module Extensions/Connect*

> > +static int get_tdx_sys_info_ext(struct tdx_sys_info_ext *sysinfo_ext)
> > +{

Yes, the file was generated by script at the beginning.

---

## [62] Xu Yilun — 2026-03-31
*Subject: Re: [PATCH v2 11/31] x86/virt/tdx: Make TDX Module initialize
 Extensions*

> >  static int tdx_ext_mem_add(struct tdx_page_array *ext_mem)
> >  {

Make sense.

> 
> > +

mm.. you are right. It leads to something absurd.

I checked with TDX Module team again. The correct understanding is:

 - TDX_FEATURES0_EXT bit shows Extensions is supported.
 - optional feature bits are selected on TDH_SYS_CONFIG
 - If one of the optional feature (e.g. TDX CONNECT) requires Extention,
   memory_pool_required_pages > 0 && ext_required == 1. Otherwise no
   need to initialize Extension.

So yes, I should check memory_pool_required_pages && ext_required at the
beginning.

> 
> > +	 */

The tdx_ext_mem_add() only collects memory, tdx_ext_init() does the
actual initialization for Extensions and touches the memory. But the
detail of when touching the pages is not specified in SPEC, do you think
host doesn't have to tell the difference, just flush when any one of
ext-SEAMCALLs is called?

> 
>

---

## [63] Edgecombe, Rick P — 2026-04-01
*Subject: Re: [PATCH v2 05/31] x86/virt/tdx: Extend tdx_page_array to support
 IOMMU_MT*

On Tue, 2026-03-31 at 22:19 +0800, Xu Yilun wrote:
> > Consider the amount of tricks that are needed to coax the tdx_page_array to
> > populate the handoff page as needed. It adds 2 pages here, then subtracts

I haven't wrapped my head around this enough to suggest anything is definitely
the right approach.

But yes, the idea would be that the allocation of the list of pages to give to
the TDX module would be a separate allocation and set of management functions.
And the the allocation of the pages that are used to communicate the list of
pages (and in this case other args) with the module would be another set. So
each type of TDX module arg page format (IOMMU_MT, etc) would be separable, but
share the page list allocation part only. It looks like Nikolay was probing
along the same path. Not sure if he had the same solution in mind.

So for this:
1. Allocate a list or array of pages using a generic method.
2. Allocate these two IOMMU special pages.
3. Allocate memory needed for the seamcall (root pages)

Hand all three to the wrapper and have it shove them all through in the special
way it prefers.

Maybe... Can you write something about the similarities and differences with the
three types of lists in that series? Like in a compact form?

Also, how much of the earlier code duplication you wanted to avoid was the
leaking and special error handling stuff?

---

## [64] Tony Lindgren — 2026-04-01
*Subject: Re: [PATCH v2 03/31] x86/virt/tdx: Add tdx_page_array helpers for
 new TDX Module objects*

On Mon, Mar 30, 2026 at 11:25:08PM +0000, Edgecombe, Rick P wrote:
> On Mon, 2026-03-30 at 18:25 +0800, Xu Yilun wrote:
> > The caller is not aware of singleton mode. Actually, I'm trying to make

We could add an enum for the LIST_INFO type to intialized the tdx_page_array?

Then the code using the tdx_page_array could initialize the root page based on
the LIST_INFO type for the SEAMCALL.

Regards,

Tony

---

## [65] Huang, Kai — 2026-04-01
*Subject: Re: [PATCH v2 08/31] x86/virt/tdx: Configure TDX Module with optional
 TDX Connect feature*

> 
> TDX Module updates global metadata when optional features are enabled.
[...]

>  static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
>  {

How about put this into config_tdx_module()?

In this way you can only update global metadata when there's new feature
being opted in, and at the meantime, avoid making init_tdx_module() more
complicated.

---

## [66] Huang, Kai — 2026-04-01
*Subject: Re: [PATCH v2 11/31] x86/virt/tdx: Make TDX Module initialize
 Extensions*

On Tue, 2026-03-31 at 22:58 +0800, Xu Yilun wrote:
> > > +	/*
> > > +	 * ext_required == 0 means no need to call TDH.EXT.INIT, the Extensions

My understanding is different:

Per spec, the 'EXT_REQUIRED' global metadata just means "Return true if the
TDH.EXT.INIT is required to be called", so I think, architecturally, it's
possible that one particular feature only requires additional memory pool
but doesn't explicitly need to call TDH.EXT.INIT.  Or some feature may not
require any additional memory pool but needs TDH.EXT.INIT.  Or require both
(such as TDX Connect I presume).

We can safely assume 2) and 3) are not required if no feature is configured
in 1) (backward compatibility).  But when there is, I think we can just:

1) If 'MEMORY_POOL_REQUIRED_PAGES' is not zero, do TDH.EXT.MEM.ADD
2) If 'EXT_REQUIRED' is true, do TDH.EXT.INIT

---

## [67] Huang, Kai — 2026-04-01
*Subject: Re: [PATCH v2 06/31] x86/virt/tdx: Read global metadata for TDX
 Module Extensions/Connect*

On Sat, 2026-03-28 at 00:01 +0800, Xu Yilun wrote:
> Add reading of the global metadata for TDX Module Extensions & TDX
> Connect. Add them in a batch as TDX Connect is currently the only user

Maybe it's better to split this patch into two, one to read generic "TDX
Module Extension" related global metadata, and the other to read TDX Connect
specific ones?

They are logically two separate things anyway.  And there are other features
also need to enable TDX Module Extensions (e.g., NRX for migration), and we
can just reuse the generic metadata patch from this series.

---

## [68] Huang, Kai — 2026-04-01
*Subject: Re: [PATCH v2 08/31] x86/virt/tdx: Configure TDX Module with optional
 TDX Connect feature*

>  static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
>  {

Maybe a more generic comment:

I don't quite like hard-coding opt-in TDX_FEATURES0_TDXCONNECT inside
config_tdx_module(), especially currently we just unconditionally opt it in
if the module support this feature.

Initializing TDX Connect (and other features via TDX Module Extensions)
consumes more memory.  It would be better if we can choose to opt-in when
the kernel has enabled TDX Connect (or any other feature via TDX module
Extensions) in the Kconfig.

Unfortunately we need to opt-in all these features together during module
initialization, so we cannot make tdx_enable() to accept the additional
features to enable, and in each in-kernel TDX user, call tdx_enable() with
the new feature that that TDX user concerns.

But I think it makes sense to have a dedicated place to calculate all opt-in
features.  E.g., assuming we eventually are going to support TDX Connect and
live migration:

static u64 get_ext_features_tdx_connect(struct tdx_sys_info * sysinfo)
{
	if (!IS_ENABLED(TDX_CONNECT))
		return 0;

	return sysinfo->features.tdx_features0 & TDX_FEATURES0_TDXCONNECT ?
		TDX_FEATURES0_TDXCONNECT : 0;
}

static u64 get_ext_features_live_migration(struct tdx_sys_info *sysinfo)
{
	u64 mig_features = TDX_FEATURES0_NRX | TDX_FEATURES0_NON_BLOCKING;

	if (!IS_ENABLED(TDX_LIVE_MIGRATION))
		return 0;

	return sysinfo->features.tdx_features0 & mig_features;
}

static u64 calculate_ext_features(struct tdx_sys_info *sysinfo)
{
	u64 ext_features = 0;

	ext_features |= get_ext_features_tdx_connect(sysinfo);

	ext_features |= get_ext_features_live_migration(sysinfo);

	return ext_features;
}

int init_tdx_module()
{
	u64 ext_features = calculate_ext_features(&tdx_sysinfo);

	ret = config_tdx_module(&tdx_tdmr_list, &tdx_global_keyid,
				ext_features);

	/* do other initializations like TDH.SYS.KEY.CONFIG */
	...
	/*
	 * TDX Module Extension features must be initialized
	 * after TDH.SYS.KEY.CONFIG.
	 */
	if (ext_features)
		ret = init_tdx_ext();	

	...
}

One nasty thing is per public spec R11 of TDH.SYS.CONFIG needs to be RTC if
TDX_CONNECT is on, so we still need some special handing in
config_tdx_module():

	if (ext_features & TDX_RFEAURES0_TDXCONNECT)
		args.r11 = ktime_get_real_seconds();

But I think this is acceptable.

---

## [69] Edgecombe, Rick P — 2026-04-01
*Subject: Re: [PATCH v2 08/31] x86/virt/tdx: Configure TDX Module with optional
 TDX Connect feature*

On Wed, 2026-04-01 at 23:42 +0000, Huang, Kai wrote:
> Maybe a more generic comment:
> 

Better how? TDX uses a lot of memory. There are many possible optimizations to
reduce this. Why focus on this one? Do we think any TDX users would actually
reconfigure there kernel for this reason?

I mean, I don't actually know how much memory this is, but to me the reasoning
doesn't seem in balance with the wider TDX situation.

---

## [70] Huang, Kai — 2026-04-02
*Subject: Re: [PATCH v2 05/31] x86/virt/tdx: Extend tdx_page_array to support
 IOMMU_MT*

On Sat, 2026-03-28 at 00:01 +0800, Xu Yilun wrote:
> IOMMU_MT is another TDX Module defined structure similar to HPA_ARRAY_T
> and HPA_LIST_INFO. The difference is it requires multi-order contiguous

Well I guess you can have a 'free_fn' to free the pages you allocated via
'alloc_fn'?  Will this simplify the code and at least keep tdx_page_array
implementation cleaner?

It's strange that you only have a 'alloc_fn' but doesn't have a 'free_fn'
anyway.

---

## [71] Huang, Kai — 2026-04-02
*Subject: Re: [PATCH v2 08/31] x86/virt/tdx: Configure TDX Module with optional
 TDX Connect feature*

On Wed, 2026-04-01 at 23:53 +0000, Edgecombe, Rick P wrote:
> On Wed, 2026-04-01 at 23:42 +0000, Huang, Kai wrote:
> > Maybe a more generic comment:

In another patch, Yilun said:

  For now, TDX Module Extensions consume relatively large amount of
  memory (~50MB).

Distros tend to enable all I assume.  I guess the CSPs tend to enable all as
well, but I am not sure whether CSPs can also choose to only enable basic
TDX w/o other features like runtime update, TDX Connect etc, depending on
how they want to "sell" TDX VMs.

E.g., I assume a TD without GPU passthrough could be cheaper the one which
has, right?  Can the CSPs host such TDs on dedicated machine pools?  Can
they choose to disable TDX Connect on these machines?

They might not care about losing ~50M memory, though, but that's a different
story, and it could be more in the future.

My thinking is, this series actually introduced a new "TDX_CONNNECT"
Kconfig, so why not only consume the memory when it's on?

At last, just my 2cents, I kinda overall don't agree we always assume
"everything will be on" but neglect avoiding unnecessary code/cost that is
not reachable when some option is off.  That would defeat the purpose of
having Kconfig option.

---

## [72] Dave Hansen — 2026-04-01
*Subject: Re: [PATCH v2 08/31] x86/virt/tdx: Configure TDX Module with optional
 TDX Connect feature*

On 4/1/26 17:40, Huang, Kai wrote:
...
> They might not care about losing ~50M memory, though, but that's a different
> story, and it could be more in the future.

If anyone _does_ care about 50MB of memory, I expect they'll speak up.
Until they do, could we please err on the side of least complexity?

I'm not even sure the Kconfig is worth it to be honest.

---

## [73] Huang, Kai — 2026-04-02
*Subject: Re: [PATCH v2 08/31] x86/virt/tdx: Configure TDX Module with optional
 TDX Connect feature*

On Wed, 2026-04-01 at 17:48 -0700, Dave Hansen wrote:
> On 4/1/26 17:40, Huang, Kai wrote:
> ...

Yeah agreed.

> 
> I'm not even sure the Kconfig is worth it to be honest.

I am not sure either.

My main comment is to make the code more friendly to opt-in more features,
actually.

---

## [74] Nikolay Borisov — 2026-04-02
*Subject: Re: [PATCH v2 27/31] coco/tdx-host: Implement SPDM session setup*

On 27.03.26 г. 18:01 ч., Xu Yilun wrote:
> From: Zhenzhong Duan <zhenzhong.duan@intel.com>
> 

This check implies pci_domain_nr returning 0 is considered invalid. 
Other callers in the kernel seem to not care, they just use the domain 
nr, so is this check spurious or intentional ?

> +	func_id |= FIELD_PREP(TDISP_FUNC_ID,
> +			      PCI_DEVID(pdev->bus->number, pdev->devfn));

nit: move those defines above the struct definition, they just break the 
reading flow as it is.

> +	u8 spdm_session_policy;
> +	u8 certificate_slot_mask;

<snip>

> +
> +static void *tdx_dup_array_data(struct tdx_page_array *array,

nit: There's DIV_ROUND_UP

> +	void *data, *dup_data;
> +

<snip>

> +
> +DEFINE_FREE(tdx_spdm_session_teardown, struct tdx_tsm_link *,

Is the free() really needed here, either the session is correctly setup 
and tlink_spdm is returned. But if session_setup() files then what about 
calling spdm_session_disconnect() on an unestablished session?


> +	if (IS_ERR(tlink_spdm)) {
> +		pci_err(pdev, "fail to setup spdm session\n");

<snip>

---

## [75] Xu Yilun — 2026-04-08
*Subject: Re: [PATCH v2 05/31] x86/virt/tdx: Extend tdx_page_array to support
 IOMMU_MT*

On Wed, Apr 01, 2026 at 12:17:45AM +0000, Edgecombe, Rick P wrote:
> On Tue, 2026-03-31 at 22:19 +0800, Xu Yilun wrote:
> > > Consider the amount of tricks that are needed to coax the tdx_page_array to


The common part:
   
         64bit obj type                 root page
   +----------+----------------+    +---------------------+     
   | ...      |  ...           |    | page0 HPA(bit12-51) |--> page0
   +----------+----------------+    +---------------------+     
   |bit 12-51 | root page HPA  |--->| page1 HPA           |--> page1
   +----------+----------------+    +---------------------+
   | ...      |  ...           |    | pageX HPA           |--> pageX
   +----------+----------------+    +---------------------+



The specific objects:

         HPA_LIST_INFO                 root page
   +----------+----------------+    +---------------------+
   |bit 3-11  | first entry    |    | page0 HPA(bit12-51) |
   +----------+----------------+    +---------------------+
   |bit 12-51 | root page HPA  |--->| page1 HPA           |
   +----------+----------------+    +---------------------+
   |bit 55-63 | last entry     |    | pageX HPA           |
   +----------+----------------+    +---------------------+



         HPA_ARRAY_T                   root page                  HPA_ARRAY_T(singleton mode)
   +----------+----------------+    +---------------------+      +----------+----------------+
   |bit 3-11  | Reserved 0     |    | page0 HPA(bit12-51) |      |bit 3-11  | Reserved 0     |
   +----------+----------------+    +---------------------+      +----------+----------------+
   |bit 12-51 | root page HPA  |--->| page1 HPA           |      |bit 12-51 | page0 HPA      |--> page0
   +----------+----------------+    +---------------------+      +----------+----------------+
   |bit 55-63 | last entry     |    | pageX HPA           |      |bit 55-63 | last entry     |
   +----------+----------------+    +---------------------+      +----------+----------------+



         MMIOMT                       root page
   +----------+----------------+    +-----------------------------+-------------------+
   |bit 3-11  | Reserved 0     |    | 2^order page0 HPA(bit12-51) |num pages(bit 0-11)|
   +----------+----------------+    +-----------------------------+-------------------+
   |bit 12-51 | root page HPA  |--->| 2^order page1 HPA           |num pages          |
   +----------+----------------+    +-----------------------------+-------------------+
   |bit 55-63 | Reserved 0     |    | page2 HPA                   |0                  |
   +----------+----------------+    +-----------------------------+-------------------+
                                    | page3 HPA                   |0                  |
                                    +-----------------------------+-------------------+
                                    | pageX HPA                   |0                  |
                                    +-----------------------------+-------------------+



The same thing is they all have root_page_hpa->root_page->page_hpa_list structure.

The differences:

		HPA_LIST_INFO	HPA_ARRAY_T	IOMMU_MT	Note
first entry     Y		N		N		start entry in root page
last entry	Y		Y		N		last entry in root page
num pages	always 0	always 0	Y		for multi-order page
singleton	N		Y		N		try to save a root page


> 
> Also, how much of the earlier code duplication you wanted to avoid was the

This is indeed a large part, and now we don't need them anymore.

Others are:
 - the root_page allocation/population/free
 - Too much parameters (struct page **, num_pages, struct page *root...)
   for seamcall wrappers. Or 3 newly defined structures which looks
   pretty much the same and need same implementations like
   tdx_clflush_page().

Thanks,
Yilun

---

## [76] Xu Yilun — 2026-04-08
*Subject: Re: [PATCH v2 05/31] x86/virt/tdx: Extend tdx_page_array to support
 IOMMU_MT*

On Thu, Apr 02, 2026 at 12:05:43AM +0000, Huang, Kai wrote:
> On Sat, 2026-03-28 at 00:01 +0800, Xu Yilun wrote:
> > IOMMU_MT is another TDX Module defined structure similar to HPA_ARRAY_T

mm.. I think code would be simplified with less callbacks.

But anyway, the need for the alloc_fn becomes a sign for me to think
about separating the memory allocation and struct tdx_page_array
construction. Especially that the IOMMU_MT needs specialized memory
layout so better managed by the kernel driver who really uses IOMMU_MT.

> 
> It's strange that you only have a 'alloc_fn' but doesn't have a 'free_fn'

---

## [77] Xu Yilun — 2026-04-08
*Subject: Re: [PATCH v2 06/31] x86/virt/tdx: Read global metadata for TDX
 Module Extensions/Connect*

On Wed, Apr 01, 2026 at 09:36:18PM +0000, Huang, Kai wrote:
> On Sat, 2026-03-28 at 00:01 +0800, Xu Yilun wrote:
> > Add reading of the global metadata for TDX Module Extensions & TDX

Will do.

---

## [78] Xu Yilun — 2026-04-08
*Subject: Re: [PATCH v2 08/31] x86/virt/tdx: Configure TDX Module with
 optional TDX Connect feature*

On Wed, Apr 01, 2026 at 10:13:33AM +0000, Huang, Kai wrote:
> 
> > 

mm.. personally I don't like such subtle control, especially when

 - We expect one or more features are doomed to be enabled.
 - We are pursuing simple TDX enabling process.
 - This is still not the exact control. If we really want to be precise,
   should check feature by feature, that's not worth it.

> being opted in, and at the meantime, avoid making init_tdx_module() more
> complicated.

---

## [79] Xu Yilun — 2026-04-08
*Subject: Re: [PATCH v2 08/31] x86/virt/tdx: Configure TDX Module with
 optional TDX Connect feature*

On Tue, Mar 31, 2026 at 01:38:16PM +0300, Nikolay Borisov wrote:
> 
> 

No, for this TDH_SYS_CONFIG SEAMCALL, the situation is different. There
is no public TDX Module release yet to support TDH_SYS_CONFIG_V1. So I
can't say v0 is deprecated.

> 
>

---

## [80] Xu Yilun — 2026-04-08
*Subject: Re: [PATCH v2 10/31] x86/virt/tdx: Add extra memory to TDX Module
 for Extensions*

> > @@ -643,7 +643,7 @@ EXPORT_SYMBOL_GPL(tdx_page_array_create_iommu_mt);
> >   #define HPA_LIST_INFO_PFN		GENMASK_U64(51, 12)

Actually array->nents is calculated the same way:

  static int tdx_page_array_populate(struct tdx_page_array *array,
				   unsigned int offset)
  {
	...

	array->offset = offset;
	array->nents = umin(array->nr_pages - offset,
			    TDX_PAGE_ARRAY_MAX_NENTS);
	...
  }

so IIUC we are good here.

---

## [81] Xu Yilun — 2026-04-08
*Subject: Re: [PATCH v2 11/31] x86/virt/tdx: Make TDX Module initialize
 Extensions*

On Wed, Apr 01, 2026 at 11:42:36AM +0000, Huang, Kai wrote:
> On Tue, 2026-03-31 at 22:58 +0800, Xu Yilun wrote:
> > > > +	/*

Maybe these text should be improved. They just literally tell how, so leads
to our disagreement.

> possible that one particular feature only requires additional memory pool
> but doesn't explicitly need to call TDH.EXT.INIT.  Or some feature may not

This is different from what I've been told by TDX Module team. Do you
have a real setup like that?

My gut feeling also tells me there is little chance that:

 1. The Extensions is already working (cause no need to call
    TDH.EXT.INIT) while we are still adding memory.
 2. The Extensions could enable long running / hard-irq preemptible
    flows with no memory consumption.

---

## [82] Huang, Kai — 2026-04-08
*Subject: Re: [PATCH v2 08/31] x86/virt/tdx: Configure TDX Module with optional
 TDX Connect feature*

> > > +	/* configuration to tdx module may change tdx_sysinfo, update it */
> > > +	ret = get_tdx_sys_info(&tdx_sysinfo);

The new kernel may also run on old hardware where no ext features can be
supported.

>  - We are pursuing simple TDX enabling process.
>  - This is still not the exact control. If we really want to be precise,

For the record I am not wanting "exact control".  It's totally fine to me to
get global metadata again if there's any ext feature enabled.

And my main comment actually is that init_tdx_module() is already having
many steps, so when the new code could logically fit somewhere else we
should stop making init_tdx_module() more complicated.

But no strong opinion, will leave to you.

---

## [83] Xu Yilun — 2026-04-08
*Subject: Re: [PATCH v2 19/31] iommu/vt-d: Reserve the MSB domain ID bit for
 the TDX module*

On Tue, Mar 31, 2026 at 03:20:44PM +0800, Baolu Lu wrote:
> On 3/29/26 00:57, kernel test robot wrote:
> > kernel test robot noticed the following build warnings:

Is it better we configure ACPI table as library, so that drivers could
use it freely at runtime? tdx-host also uses this function.

--------8<--------

diff --git a/drivers/iommu/intel/Kconfig b/drivers/iommu/intel/Kconfig
index 5471f814e073..55188d6d38bb 100644
--- a/drivers/iommu/intel/Kconfig
+++ b/drivers/iommu/intel/Kconfig
@@ -1,6 +1,7 @@
 # SPDX-License-Identifier: GPL-2.0-only
 # Intel IOMMU support
 config DMAR_TABLE
+       select ACPI_TABLE_LIB
        bool

 config DMAR_PERF

---

## [84] Huang, Kai — 2026-04-08
*Subject: Re: [PATCH v2 11/31] x86/virt/tdx: Make TDX Module initialize
 Extensions*

On Wed, 2026-04-08 at 16:24 +0800, Xu Yilun wrote:
> On Wed, Apr 01, 2026 at 11:42:36AM +0000, Huang, Kai wrote:
> > On Tue, 2026-03-31 at 22:58 +0800, Xu Yilun wrote:

I don't think we need to guess here.  We need to understand what the
architecture behaviour is and then write code based on that.  If there's
anything not clear on architecture, we need to ask the module team to
clarify.

Back to the architecture behaviour, the spec "4.4 TDX Module Extension
Initialization" says:

  1. The host VMM configures the desired TDX features ...

  2. Based on the enabled features, the TDX Module checks whether a memory 
     pool is required and if so, calculates its required size.

  3. The host VMM reads MEMORY_POOL_REQUIRED_PAGES, the number of missing
     TDX Module’s memory pool pages, using TDH.SYS.RD.

  4. Once the TDX Module has been initialized (TDH.SYS.KEY.CONFIG was 
     called on all packages), the host VMM can call TDH.EXT.MEM.ADD  
     multiple times to add the required number of memory pages to the TDX
     Module’s memory pool.

  5. The host VMM reads EXT_REQUIRED, which indicates whether the TDX
     Module extension is required to be initialized, using TDH.SYS.RD.
     If required, the host VMM can then call TDH.EXT.INIT to initialize
     the TDX Module extension.

So to me it's clear that we need to do things in following:

  1. Opt-in ext features in TDH.SYS.CONFIG
  2. Read MEMORY_POOL_REQUIRED_PAGES and EXT_REQUIRED
  3. After TDH.SYS.KEY.CONFIG, initialize the module extension:
    a. If MEMORY_POOL_REQUIRED_PAGES is not zero, do TDH.EXT.MEM.ADD
    b. If EXT_REQUIRED is not zero, do TDH.EXT.INIT

To me there's no need to make any other assumption here.

---

## [85] Edgecombe, Rick P — 2026-04-09
*Subject: Re: [PATCH v2 11/31] x86/virt/tdx: Make TDX Module initialize
 Extensions*

On Wed, 2026-04-08 at 21:24 +0000, Huang, Kai wrote:
> I don't think we need to guess here.  We need to understand what the
> architecture behaviour is and then write code based on that.  If

A general comment...I think this is the wrong attitude. If we have some
assumptions that can simplify the kernel code, let's get them in the
spec. Or otherwise get an agreement from the TDX module to make them no
longer assumptions.

Just silently hoping our assumptions are true is not great either. But
uncritically implementing the architecture that is handed down is
totally wrong.

---

## [86] Huang, Kai — 2026-04-09
*Subject: Re: [PATCH v2 11/31] x86/virt/tdx: Make TDX Module initialize
 Extensions*

On Thu, 2026-04-09 at 00:49 +0000, Edgecombe, Rick P wrote:
> On Wed, 2026-04-08 at 21:24 +0000, Huang, Kai wrote:
> > I don't think we need to guess here.  We need to understand what the

Yes agree in principle.

Maybe I am missing something, but I don't see any big issue for this
particular architecture behaviour.  If you have any good idea to improve
this flow then great.

---

## [87] Baolu Lu — 2026-04-09
*Subject: Re: [PATCH v2 19/31] iommu/vt-d: Reserve the MSB domain ID bit for
 the TDX module*

On 4/8/26 20:07, Xu Yilun wrote:
> On Tue, Mar 31, 2026 at 03:20:44PM +0800, Baolu Lu wrote:
>> On 3/29/26 00:57, kernel test robot wrote:

This looks better.

Thanks,
baolu

---

## [88] Tian, Kevin — 2026-04-09
*Subject: RE: [PATCH v2 18/31] iommu/vt-d: Cache max domain ID to avoid
 redundant calculation*

> From: Xu Yilun <yilun.xu@linux.intel.com>
> Sent: Saturday, March 28, 2026 12:01 AM

Reviewed-by: Kevin Tian <kevin.tian@intel.com>

---

## [89] Tian, Kevin — 2026-04-09
*Subject: RE: [PATCH v2 19/31] iommu/vt-d: Reserve the MSB domain ID bit for
 the TDX module*

> From: Xu Yilun <yilun.xu@linux.intel.com>
> Sent: Saturday, March 28, 2026 12:01 AM

platform_support_tdxc()

> +{
> +	static int tvm_usable = -1;

this is useless. tvm_usable is already set to '0' before the function call.

> +
> +	return !!tvm_usable;

'... reserved for TDX Connect'

> +		return ndoms >> 1;
> +	}

Here we need more words to explain the strategy here.

The comment says "When IOMMU is *enabled*...", but the code here
just checks the static capability. It's probably a design choice that you
don't want to add complexity on recycling DIDs when TDX connect
is actually enabled, but it's worth a note here.

btw in patch23 commit msg:

"
There is no dedicated way to enumerate which IOMMU devices support
trusted operations. The host has to call TDH.IOMMU.SETUP on all IOMMU
devices and tell their trusted capability by the return value.
"

which implies that ecap_tdxc() alone doesn't really report the capability?

anyway all of those need a better explanation here...

---

## [90] Tian, Kevin — 2026-04-09
*Subject: RE: [PATCH v2 20/31] x86/virt/tdx: Add a helper to loop on
 TDX_INTERRUPTED_RESUMABLE*

> From: Xu Yilun <yilun.xu@linux.intel.com>
> Sent: Saturday, March 28, 2026 12:01 AM

'ir' sounds redundant with the trailing 'resched'?

not big deal, just a bit confusing when seeing it in IOMMU side where
'ir' also refers to 'interrupt remapping' and is frequently used in 
irq_remapping.c... :)

---

## [91] Tian, Kevin — 2026-04-09
*Subject: RE: [PATCH v2 21/31] x86/virt/tdx: Add SEAMCALL wrappers for trusted
 IOMMU setup and clear*

> From: Xu Yilun <yilun.xu@linux.intel.com>
> Sent: Saturday, March 28, 2026 12:01 AM

what is 'trusted IOMMU'? a new hardware, or some sensitive resource in
the IOMMU which is only visible to TDX module?

If the latter it's clearer to say "trusted configuration in IOMMU".

> 
> Enable TEE I/O support for a target device requires to setup trusted IOMMU

this series is just about SPDM/IDE. then the first part about TEE I/O is not
really relevant.

> 
> TDH.IOMMU.SETUP takes the register base address (VTBAR) to position an

Intel IOMMU is called VT-d. It has a register block but not a PCI device so
there is no BAR resource related.

let's just call it 'reg_base'

intel-iommu driver already has its own 'id' definition for each iommu device.
It's clearer to add a prefix to this new id, e.g. tdx_iommu_id?

---

## [92] Tian, Kevin — 2026-04-09
*Subject: RE: [PATCH v2 22/31] iommu/vt-d: Export a helper to do function for
 each dmar_drhd_unit*

> From: Xu Yilun <yilun.xu@linux.intel.com>
> Sent: Saturday, March 28, 2026 12:01 AM

It's a bit weird to insert it here. Move it to follow for_each_iommu().

> +
> +int do_for_each_drhd_unit(int (*fn)(struct dmar_drhd_unit *))

use for_each_active_drhd_unit(). or is there need to setup the trusted
configuration even on ignored iommu?

---

## [93] Tian, Kevin — 2026-04-09
*Subject: RE: [PATCH v2 23/31] coco/tdx-host: Setup all trusted IOMMUs on TDX
 Connect init*

> From: Xu Yilun <yilun.xu@linux.intel.com>
> Sent: Saturday, March 28, 2026 12:01 AM

not sure what above tries to tell. why is it a platform configuration
when you have seamcalls on each IOMMU?

---

## [94] Tian, Kevin — 2026-04-09
*Subject: RE: [PATCH v2 24/31] coco/tdx-host: Add a helper to exchange SPDM
 messages through DOE*

> From: Xu Yilun <yilun.xu@linux.intel.com>
> Sent: Saturday, March 28, 2026 12:01 AM

call it pci_spdm_msg_exchange() and pass in struct pci_dev directly.

there is no other use of tlink in this function. could add a note that
this should be moved to pci core when a 2nd user of raw frame comes.

---

## [95] Tian, Kevin — 2026-04-09
*Subject: RE: [PATCH v2 25/31] x86/virt/tdx: Add SEAMCALL wrappers for SPDM
 management*

> From: Xu Yilun <yilun.xu@linux.intel.com>
> Sent: Saturday, March 28, 2026 12:01 AM

here ...

> - TDH.SPDM.MNG supports three SPDM runtime operations: HEARTBEAT,
>   KEY_UPDATE and DEV_INFO_RECOLLECTION.

... but the actual helper just pass whatever ops to TDX module 

> +u64 tdh_exec_spdm_mng(u64 spdm_id, u64 spdm_op, struct page
> *spdm_param,

---

## [96] Tian, Kevin — 2026-04-09
*Subject: RE: [PATCH v2 30/31] coco/tdx-host: Implement IDE stream
 setup/teardown*

> From: Xu Yilun <yilun.xu@linux.intel.com>
> Sent: Saturday, March 28, 2026 12:02 AM

'more straightforward', compared to what?

---

## [97] Dan Williams — 2026-04-11
*Subject: Re: [PATCH v2 03/31] x86/virt/tdx: Add tdx_page_array helpers for new
 TDX Module objects*

Xu Yilun wrote:
> Add struct tdx_page_array definition for new TDX Module object
> types - HPA_ARRAY_T and HPA_LIST_INFO. They are used as input/output

I think this undersells the fact that "singleton mode" is a premature
optimization that requires complication to take advantage of the benefit
(sometimes save a single page allocation). The Linux implementation
forfeits that small benefit for the larger gain of cleaner kAPIs.

> Another small difference is HPA_LIST_INFO contains a 'first entry' field
> which could be filled by TDX Module. This simplifies host by providing

It is simply a bug if TDH_XXX_DELETE does not return every resource
passed to TDH_XXX_CREATE. The only "leak" case to worry about is that
TDH_XXX_DELETE fails. In that case it should be "fatal" (TDX_BUG_ON,
system can keep hobbling along, but panic_on_warn() would not be
unreasonable). If TDH_XXX_DELETE fails it indicates some catastrophic
misunderstanding between Linux and the TDX Module.

So the seamcall in this case has no need for @nr_released or
@released_hpa, those should already be known to the kernel.

What is missing is an architectural guarantee that TDH_XXX_DELETE
success == "all resources you arranged at TDH_XXX_CREATE time are free".
I would hope that is already the case and AUX_PAGE_PA is only an
unfortunate distraction. If it can ever be the case that CREATE and
DELETE are asymmetric on success then that needs to be corrected and
Linux will wait for a future module that can make that guarantee.

I think that cleans up a bulk of the logic here to abandon caring that
the module tries to remind us what we are releasing.

---

## [98] Xu Yilun — 2026-04-14
*Subject: Re: [PATCH v2 05/31] x86/virt/tdx: Extend tdx_page_array to support
 IOMMU_MT*

On Wed, Apr 01, 2026 at 12:17:45AM +0000, Edgecombe, Rick P wrote:
> On Tue, 2026-03-31 at 22:19 +0800, Xu Yilun wrote:
> > > Consider the amount of tricks that are needed to coax the tdx_page_array to

I'm drafting some changes and make the tdx_page_array look like:

  struct tdx_page_array {
	/* public: */
	unsigned int nr_pages;
	struct page **pages;

	/* private: */
	u64 *root;
	bool flush_on_free;
  };

  - I removed the page allocations for tdx_page_array kAPIs. Now the
    caller needs to allocate the struct page **pages and the page list,
    then create the tdx_page_array by providing these pages.

    struct tdx_page_array *tdx_page_array_create(struct page **pages,
						 unsigned int nr_pages)

    This also means tdx_page_array doesn't have to hold more than 512
    pages anymore, it now an exact descriptor for the TDX Module's
    definitions rather than a manager. It's a chunk of the required
    memory when we need more than 512 pages. This eliminates the need
    for 'offset' field and the slide window operations so make the
    helpers simpler.

  - I still keep the generic struct tdx_page_array to represent all
    kinds of object types (HPA_ARRAY_T, HPA_LIST_INFO, IOMMU_MT), and
    provide the tdx_page_array to SEAMCALL helpers as parameters. I
    think this structure is generally good enough to represent a list of
    pages, keeps type safety compared to a list of HPAs.

  - I still record both the page list (struct page **pages) and the HPA
    list (in u64 *root). struct page **pages works with kernel memory
    management (e.g. vmap) well while the populated root works with
    SEAMCALLs.

  - I'm not introducing more structures each for an object type, like 
    struct hpa_array, struct hpa_list_info, struct iommu_metadata. They
    are conceptually the same thing. The iommu_mt supports multi-order
    pages, hpa_array_t & hpa_list_info don't support. But their bit
    definitions don't conflict. I can use the same piece of code to
    populate their root page content.

  - Add a flush_on_free field to mark if a cache write back is needed on
    tdx_page_array_free(), then we don't need 2 free APIs.

I want to clean up my code, then post an incremental patch for preview.

Thanks.

---

## [99] Xu Yilun — 2026-04-16
*Subject: Re: [PATCH v2 05/31] x86/virt/tdx: Extend tdx_page_array to support
 IOMMU_MT*

On Tue, Apr 14, 2026 at 05:57:35PM +0800, Xu Yilun wrote:
> On Wed, Apr 01, 2026 at 12:17:45AM +0000, Edgecombe, Rick P wrote:
> > On Tue, 2026-03-31 at 22:19 +0800, Xu Yilun wrote:

Hi, I end up made the following changes on top of this series:

-------8<--------

 arch/x86/include/asm/tdx.h            |  32 +-
 arch/x86/virt/vmx/tdx/tdx.c           | 561 ++++++++------------------
 drivers/virt/coco/tdx-host/tdx-host.c | 179 ++++++--
 3 files changed, 316 insertions(+), 456 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 7bdd66acda5b..31d1101a4f45 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -143,15 +143,12 @@ void tdx_quirk_reset_page(struct page *page);
 
 /**
  * struct tdx_page_array - Represents a list of pages for TDX Module access
- * @nr_pages: Total number of data pages in the collection
- * @pages: Array of data page pointers containing all the data
+ * @nr_pages: Number of data pages in the collection (up to 512)
+ * @pages: Array of data page pointers
  *
- * @offset: Internal: The starting index in @pages, positions the currently
- *	    populated page window in @root.
- * @nents: Internal: Number of valid HPAs for the page window in @root
- * @root: Internal: A single 4KB page holding the 8-byte HPAs of the page
- *	  window. The page window max size is constrained by the root page,
- *	  which is 512 HPAs.
+ * @root: Internal: A single 4KB page holding the 8-byte HPAs of the @pages
+ * @flush_on_free: Internal: whether to flush cache when @pages are to be
+ *		   freed.
  *
  * This structure abstracts several TDX Module defined object types, e.g.,
  * HPA_ARRAY_T and HPA_LIST_INFO. Typically they all use a "root page" as the
@@ -165,20 +162,13 @@ struct tdx_page_array {
 	struct page **pages;
 
 	/* private: */
-	unsigned int offset;
-	unsigned int nents;
 	u64 *root;
+	bool flush_on_free;
 };
 
 void tdx_page_array_free(struct tdx_page_array *array);
-DEFINE_FREE(tdx_page_array_free, struct tdx_page_array *, if (_T) tdx_page_array_free(_T))
-struct tdx_page_array *tdx_page_array_create(unsigned int nr_pages);
-void tdx_page_array_ctrl_leak(struct tdx_page_array *array);
-int tdx_page_array_ctrl_release(struct tdx_page_array *array,
-				unsigned int nr_released,
-				u64 released_hpa);
-struct tdx_page_array *
-tdx_page_array_create_iommu_mt(unsigned int iq_order, unsigned int nr_mt_pages);
+struct tdx_page_array *tdx_page_array_create(struct page **pages,
+					     unsigned int nr_pages);
 
 struct tdx_td {
 	/* TD root structure: */
@@ -248,8 +238,7 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page);
 u64 tdh_iommu_setup(u64 vtbar, struct tdx_page_array *iommu_mt, u64 *iommu_id);
 u64 tdh_iommu_clear(u64 iommu_id, struct tdx_page_array *iommu_mt);
 u64 tdh_spdm_create(u64 func_id, struct tdx_page_array *spdm_mt, u64 *spdm_id);
-u64 tdh_spdm_delete(u64 spdm_id, struct tdx_page_array *spdm_mt,
-		    unsigned int *nr_released, u64 *released_hpa);
+u64 tdh_spdm_delete(u64 spdm_id, struct tdx_page_array *spdm_mt);
 u64 tdh_exec_spdm_connect(u64 spdm_id, struct page *spdm_conf,
 			  struct page *spdm_rsp, struct page *spdm_req,
 			  struct tdx_page_array *spdm_out,
@@ -269,8 +258,7 @@ u64 tdh_ide_stream_create(u64 stream_info, u64 spdm_id,
 			  u64 *rp_ide_id);
 u64 tdh_ide_stream_block(u64 spdm_id, u64 stream_id);
 u64 tdh_ide_stream_delete(u64 spdm_id, u64 stream_id,
-			  struct tdx_page_array *stream_mt,
-			  unsigned int *nr_released, u64 *released_hpa);
+			  struct tdx_page_array *stream_mt);
 u64 tdh_ide_stream_km(u64 spdm_id, u64 stream_id, u64 operation,
 		      struct page *spdm_rsp, struct page *spdm_req,
 		      u64 *spdm_req_len);
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 72d836b25bd6..04f47c5eb2a5 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -262,21 +262,27 @@ static int build_tdx_memlist(struct list_head *tmb_list)
 #define TDX_PAGE_ARRAY_MAX_NENTS	(PAGE_SIZE / sizeof(u64))
 
 static int tdx_page_array_populate(struct tdx_page_array *array,
-				   unsigned int offset)
+				   struct page **pages, unsigned int nr_pages)
 {
-	u64 *entries;
+	u64 *entries = array->root;
 	int i;
 
-	if (offset >= array->nr_pages)
-		return 0;
+	if (!pages || !nr_pages || nr_pages > TDX_PAGE_ARRAY_MAX_NENTS)
+		return -EINVAL;
+
+	/*
+	 * When re-populating, the old pages are no longer tracked.
+	 * Theoretically they require cache flushing similar to
+	 * tdx_page_array_free(). Since there is no use case for this yet,
+	 * just warn to prompt future improvement.
+	 */
+	WARN_ON_ONCE(array->pages && array->flush_on_free);
 
-	array->offset = offset;
-	array->nents = umin(array->nr_pages - offset,
-			    TDX_PAGE_ARRAY_MAX_NENTS);
+	for (i = 0; i < nr_pages; i++) {
+		struct page *page = pages[i];
 
-	entries = array->root;
-	for (i = 0; i < array->nents; i++) {
-		struct page *page = array->pages[offset + i];
+		if (!page)
+			return -EINVAL;
 
 		entries[i] = page_to_phys(page);
 
@@ -285,359 +291,96 @@ static int tdx_page_array_populate(struct tdx_page_array *array,
 			entries[i] |= compound_nr(page);
 	}
 
-	return array->nents;
-}
-
-static void tdx_free_pages_bulk(unsigned int nr_pages, struct page **pages)
-{
-	int i;
-
-	for (i = 0; i < nr_pages; i++)
-		put_page(pages[i]);
-}
-
-static int tdx_alloc_pages_bulk(unsigned int nr_pages, struct page **pages,
-				void *data)
-{
-	unsigned int filled, done = 0;
-
-	do {
-		filled = alloc_pages_bulk(GFP_KERNEL, nr_pages - done,
-					  pages + done);
-		if (!filled) {
-			tdx_free_pages_bulk(done, pages);
-			return -ENOMEM;
-		}
-
-		done += filled;
-	} while (done != nr_pages);
+	array->pages = pages;
+	array->nr_pages = nr_pages;
 
 	return 0;
 }
 
 /**
- * tdx_page_array_free() - Free all memory for a tdx_page_array
+ * tdx_page_array_free() - Free the tdx_page_array
  * @array: The tdx_page_array to be freed.
  *
- * Free all associated pages and the container itself.
+ * Free this page array decriptor. Note the associated pages are not
+ * freed, their lifecycles are not controlled by tdx_page_array.
+ *
+ * TDX Module may consume page array for private accessing, flush cache before
+ * this tracking decriptor is freed, to avoid private cache write back
+ * damages these pages which may further be returned to kernel and reused.
+ * Specific SEAMCALL helpers should indicate the flushing by setting this flag.
  */
 void tdx_page_array_free(struct tdx_page_array *array)
 {
 	if (!array)
 		return;
 
-	tdx_free_pages_bulk(array->nr_pages, array->pages);
-	kfree(array->pages);
-	kfree(array->root);
-	kfree(array);
-}
-EXPORT_SYMBOL_GPL(tdx_page_array_free);
-
-static struct tdx_page_array *
-tdx_page_array_alloc(unsigned int nr_pages,
-		     int (*alloc_fn)(unsigned int nr_pages,
-				     struct page **pages, void *data),
-		     void *data)
-{
-	struct tdx_page_array *array = NULL;
-	struct page **pages = NULL;
-	u64 *root = NULL;
-	int ret;
-
-	if (!nr_pages)
-		return NULL;
-
-	array = kzalloc_obj(*array);
-	if (!array)
-		goto out_free;
-
-	root = kzalloc(PAGE_SIZE, GFP_KERNEL);
-	if (!root)
-		goto out_free;
-
-	pages = kcalloc(nr_pages, sizeof(*pages), GFP_KERNEL);
-	if (!pages)
-		goto out_free;
-
-	ret = alloc_fn(nr_pages, pages, data);
-	if (ret)
-		goto out_free;
+	if (array->flush_on_free) {
+		int i;
 
-	array->nr_pages = nr_pages;
-	array->pages = pages;
-	array->root = root;
+		for (i = 0; i < array->nr_pages; i++) {
+			u64 r;
 
-	return array;
+			r = tdh_phymem_page_wbinvd_hkid(tdx_global_keyid,
+							array->pages[i]);
+			WARN_ON_ONCE(r);
+		}
+	}
 
-out_free:
-	kfree(pages);
-	kfree(root);
+	kfree(array->root);
 	kfree(array);
-
-	return NULL;
 }
+EXPORT_SYMBOL_GPL(tdx_page_array_free);
 
-/**
- * tdx_page_array_create() - Create a small tdx_page_array (up to 512 pages)
- * @nr_pages: Number of pages to allocate (must be <= 512).
- *
- * Allocate and populate a tdx_page_array in a single step. This is intended
- * for small collections that fit within a single root page. The allocated
- * pages are all order-0 pages. This is the most common use case for a list of
- * TDX control pages.
- *
- * If more pages are required, use tdx_page_array_alloc() and
- * tdx_page_array_populate() to build tdx_page_array chunk by chunk.
- *
- * Return: Fully populated tdx_page_array or NULL on failure.
- */
-struct tdx_page_array *tdx_page_array_create(unsigned int nr_pages)
+static struct tdx_page_array *tdx_page_array_alloc(void)
 {
 	struct tdx_page_array *array;
-	int populated;
 
-	if (nr_pages > TDX_PAGE_ARRAY_MAX_NENTS)
-		return NULL;
-
-	array = tdx_page_array_alloc(nr_pages, tdx_alloc_pages_bulk, NULL);
+	array = kzalloc_obj(*array);
 	if (!array)
 		return NULL;
 
-	populated = tdx_page_array_populate(array, 0);
-	if (populated != nr_pages)
-		goto out_free;
-
-	return array;
-
-out_free:
-	tdx_page_array_free(array);
-	return NULL;
-}
-EXPORT_SYMBOL_GPL(tdx_page_array_create);
-
-/**
- * tdx_page_array_ctrl_leak() - Leak data pages and free the container
- * @array: The tdx_page_array to be leaked.
- *
- * Call this function when failed to reclaim the control pages. Free the root
- * page and the holding structures, but orphan the data pages, to prevent the
- * host from re-allocating and accessing memory that the hardware may still
- * consider private.
- */
-void tdx_page_array_ctrl_leak(struct tdx_page_array *array)
-{
-	if (!array)
-		return;
-
-	kfree(array->pages);
-	kfree(array->root);
-	kfree(array);
-}
-EXPORT_SYMBOL_GPL(tdx_page_array_ctrl_leak);
-
-static bool tdx_page_array_validate_release(struct tdx_page_array *array,
-					    unsigned int offset,
-					    unsigned int nr_released,
-					    u64 released_hpa)
-{
-	unsigned int nents;
-
-	if (offset >= array->nr_pages)
-		return false;
-
-	nents = umin(array->nr_pages - offset, TDX_PAGE_ARRAY_MAX_NENTS);
-
-	if (nents != nr_released) {
-		pr_err("%s nr_released [%d] doesn't match page array nents [%d]\n",
-		       __func__, nr_released, nents);
-		return false;
-	}
-
-	/*
-	 * Unfortunately TDX has multiple page allocation protocols, check the
-	 * "singleton" case required for HPA_ARRAY_T.
-	 */
-	if (page_to_phys(array->pages[0]) == released_hpa &&
-	    array->nr_pages == 1)
-		return true;
-
-	/* Then check the "non-singleton" case */
-	if (virt_to_phys(array->root) == released_hpa) {
-		u64 *entries = array->root;
-		int i;
-
-		for (i = 0; i < nents; i++) {
-			struct page *page = array->pages[offset + i];
-			u64 val = page_to_phys(page);
-
-			/* Now only for iommu_mt */
-			if (compound_nr(page) > 1)
-				val |= compound_nr(page);
-
-			if (val != entries[i]) {
-				pr_err("%s entry[%d] [0x%llx] doesn't match page hpa [0x%llx]\n",
-				       __func__, i, entries[i], val);
-				return false;
-			}
-		}
-
-		return true;
+	array->root = kzalloc(PAGE_SIZE, GFP_KERNEL);
+	if (!array->root) {
+		kfree(array);
+		return NULL;
 	}
 
-	pr_err("%s failed to validate, released_hpa [0x%llx], root page hpa [0x%llx], page0 hpa [%#llx], number pages %u\n",
-	       __func__, released_hpa, virt_to_phys(array->root),
-	       page_to_phys(array->pages[0]), array->nr_pages);
-
-	return false;
+	return array;
 }
 
 /**
- * tdx_page_array_ctrl_release() - Verify and release TDX control pages
- * @array: The tdx_page_array used to originally create control pages.
- * @nr_released: Number of HPAs the TDX Module reported as released.
- * @released_hpa: The HPA list the TDX Module reported as released.
+ * tdx_page_array_create() - Create a populated tdx_page_array (up to 512 pages)
+ * @pages: Pointer to struct page array for tdx_page_array populating
+ * @nr_pages: Size of @pages array.
  *
- * TDX Module can at most release 512 control pages, so this function only
- * accepts small tdx_page_array (up to 512 pages), usually created by
- * tdx_page_array_create().
+ * Create a populated tdx_page_array in a single step. This is intended for
+ * small collections that fit within a single root page. This is the most
+ * common use case for a list of TDX control pages.
  *
- * Return: 0 on success, -errno on page release protocol error.
- */
-int tdx_page_array_ctrl_release(struct tdx_page_array *array,
-				unsigned int nr_released,
-				u64 released_hpa)
-{
-	int i;
-
-	/*
-	 * The only case where ->nr_pages is allowed to be >
-	 * TDX_PAGE_ARRAY_MAX_NENTS is a case where those pages are never
-	 * expected to be released by this function.
-	 */
-	if (WARN_ON(array->nr_pages > TDX_PAGE_ARRAY_MAX_NENTS))
-		return -EINVAL;
-
-	if (WARN_ONCE(!tdx_page_array_validate_release(array, 0, nr_released,
-						       released_hpa),
-		      "page release protocol error, consider reboot and replace TDX Module.\n"))
-		return -EFAULT;
-
-	for (i = 0; i < array->nr_pages; i++) {
-		u64 r;
-
-		r = tdh_phymem_page_wbinvd_hkid(tdx_global_keyid,
-						array->pages[i]);
-		if (WARN_ON(r))
-			return -EFAULT;
-	}
-
-	tdx_page_array_free(array);
-	return 0;
-}
-EXPORT_SYMBOL_GPL(tdx_page_array_ctrl_release);
-
-static int tdx_alloc_pages_contig(unsigned int nr_pages, struct page **pages,
-				  void *data)
-{
-	struct page *page;
-	int i;
-
-	page = alloc_contig_pages(nr_pages, GFP_KERNEL, numa_mem_id(),
-				  &node_online_map);
-	if (!page)
-		return -ENOMEM;
-
-	for (i = 0; i < nr_pages; i++)
-		pages[i] = page + i;
-
-	return 0;
-}
-
-/*
- * For holding large number of contiguous pages, usually larger than
- * TDX_PAGE_ARRAY_MAX_NENTS (512).
- *
- * Similar to tdx_page_array_alloc(), after allocating with this
- * function, call tdx_page_array_populate() to populate the tdx_page_array.
- */
-static struct tdx_page_array *
-tdx_page_array_alloc_contig(unsigned int nr_pages)
-{
-	return tdx_page_array_alloc(nr_pages, tdx_alloc_pages_contig, NULL);
-}
-
-static int tdx_alloc_pages_iommu_mt(unsigned int nr_pages, struct page **pages,
-				    void *data)
-{
-	unsigned int iq_order = (unsigned int)(long)data;
-	struct folio *t_iq, *t_ctxiq;
-	int ret;
-
-	/* TODO: folio_alloc_node() is preferred, but need numa info */
-	t_iq = folio_alloc(GFP_KERNEL | __GFP_ZERO, iq_order);
-	if (!t_iq)
-		return -ENOMEM;
-
-	t_ctxiq = folio_alloc(GFP_KERNEL | __GFP_ZERO, iq_order);
-	if (!t_ctxiq) {
-		ret = -ENOMEM;
-		goto out_t_iq;
-	}
-
-	ret = tdx_alloc_pages_bulk(nr_pages - 2, pages + 2, NULL);
-	if (ret)
-		goto out_t_ctxiq;
-
-	pages[0] = folio_page(t_iq, 0);
-	pages[1] = folio_page(t_ctxiq, 0);
-
-	return 0;
-
-out_t_ctxiq:
-	folio_put(t_ctxiq);
-out_t_iq:
-	folio_put(t_iq);
-
-	return ret;
-}
-
-/**
- * tdx_page_array_create_iommu_mt() - Create a page array for IOMMU Memory Tables
- * @iq_order: The allocation order for the IOMMU Invalidation Queue.
- * @nr_mt_pages: Number of additional order-0 pages for the MT.
- *
- * Allocate and populate a specialized tdx_page_array for IOMMU_MT structures.
- * The resulting array consists of two multi-order folios (at index 0 and 1)
- * followed by the requested number of order-0 pages.
+ * If more pages are required, use tdx_page_array_alloc() and
+ * tdx_page_array_populate() to build tdx_page_array chunk by chunk.
  *
- * Return: Fully populated tdx_page_array or NULL on failure.
+ * Return: Populated tdx_page_array or NULL on failure.
  */
 struct tdx_page_array *
-tdx_page_array_create_iommu_mt(unsigned int iq_order, unsigned int nr_mt_pages)
+tdx_page_array_create(struct page **pages, unsigned int nr_pages)
 {
-	unsigned int nr_pages = nr_mt_pages + 2;
 	struct tdx_page_array *array;
-	int populated;
-
-	if (nr_pages > TDX_PAGE_ARRAY_MAX_NENTS)
-		return NULL;
+	int ret;
 
-	array = tdx_page_array_alloc(nr_pages, tdx_alloc_pages_iommu_mt,
-				     (void *)(long)iq_order);
+	array = tdx_page_array_alloc();
 	if (!array)
 		return NULL;
 
-	populated = tdx_page_array_populate(array, 0);
-	if (populated != nr_pages)
-		goto out_free;
+	ret = tdx_page_array_populate(array, pages, nr_pages);
+	if (ret) {
+		tdx_page_array_free(array);
+		return NULL;
+	}
 
 	return array;
-
-out_free:
-	tdx_page_array_free(array);
-	return NULL;
 }
-EXPORT_SYMBOL_GPL(tdx_page_array_create_iommu_mt);
+EXPORT_SYMBOL_GPL(tdx_page_array_create);
 
 #define HPA_LIST_INFO_FIRST_ENTRY	GENMASK_U64(11, 3)
 #define HPA_LIST_INFO_PFN		GENMASK_U64(51, 12)
@@ -648,7 +391,7 @@ static u64 hpa_list_info_assign_raw(struct tdx_page_array *array)
 	return FIELD_PREP(HPA_LIST_INFO_FIRST_ENTRY, 0) |
 	       FIELD_PREP(HPA_LIST_INFO_PFN,
 			  PFN_DOWN(virt_to_phys(array->root))) |
-	       FIELD_PREP(HPA_LIST_INFO_LAST_ENTRY, array->nents - 1);
+	       FIELD_PREP(HPA_LIST_INFO_LAST_ENTRY, array->nr_pages - 1);
 }
 
 #define HPA_ARRAY_T_PFN		GENMASK_U64(51, 12)
@@ -658,18 +401,18 @@ static u64 hpa_array_t_assign_raw(struct tdx_page_array *array)
 {
 	unsigned long pfn;
 
-	if (array->nents == 1)
-		pfn = page_to_pfn(array->pages[array->offset]);
+	if (array->nr_pages == 1)
+		pfn = page_to_pfn(array->pages[0]);
 	else
 		pfn = PFN_DOWN(virt_to_phys(array->root));
 
 	return FIELD_PREP(HPA_ARRAY_T_PFN, pfn) |
-	       FIELD_PREP(HPA_ARRAY_T_SIZE, array->nents - 1);
+	       FIELD_PREP(HPA_ARRAY_T_SIZE, array->nr_pages - 1);
 }
 
 static u64 hpa_array_t_release_raw(struct tdx_page_array *array)
 {
-	if (array->nents == 1)
+	if (array->nr_pages == 1)
 		return 0;
 
 	return virt_to_phys(array->root);
@@ -1515,8 +1258,8 @@ static void tdx_clflush_page(struct page *page)
 
 static void tdx_clflush_page_array(struct tdx_page_array *array)
 {
-	for (int i = 0; i < array->nents; i++)
-		tdx_clflush_page(array->pages[array->offset + i]);
+	for (int i = 0; i < array->nr_pages; i++)
+		tdx_clflush_page(array->pages[i]);
 }
 
 /* Initialize the TDX Module Extensions then Extension-SEAMCALLs can be used */
@@ -1536,14 +1279,14 @@ static int tdx_ext_init(void)
 	return 0;
 }
 
-static int tdx_ext_mem_add(struct tdx_page_array *ext_mem)
+static int tdx_ext_mem_add(struct tdx_page_array *mem)
 {
 	struct tdx_module_args args = {
-		.rcx = hpa_list_info_assign_raw(ext_mem),
+		.rcx = hpa_list_info_assign_raw(mem),
 	};
 	u64 r;
 
-	tdx_clflush_page_array(ext_mem);
+	tdx_clflush_page_array(mem);
 
 	do {
 		r = seamcall_ret(TDH_EXT_MEM_ADD, &args);
@@ -1556,33 +1299,86 @@ static int tdx_ext_mem_add(struct tdx_page_array *ext_mem)
 	return 0;
 }
 
-static int tdx_ext_mem_setup(struct tdx_page_array *ext_mem)
+struct tdx_ext_mem {
+	struct page **pages;
+	unsigned int nr_pages;
+	struct tdx_page_array *chunk;
+};
+
+static void tdx_ext_mem_remove(struct tdx_ext_mem *ext_mem)
 {
-	unsigned int populated, offset = 0;
-	int ret;
+	int i;
 
-	/*
-	 * tdx_page_array's root page can hold 512 HPAs at most. We have ~50MB
-	 * memory to add, re-populate the array and add pages bulk by bulk.
-	 */
-	while (1) {
-		populated = tdx_page_array_populate(ext_mem, offset);
-		if (!populated)
-			break;
+	tdx_page_array_free(ext_mem->chunk);
+
+	for (i = 0; i < ext_mem->nr_pages; i++)
+		__free_page(ext_mem->pages[i]);
+
+	kfree(ext_mem->pages);
+}
+
+static int tdx_ext_mem_setup(unsigned int nr_pages,
+			     struct tdx_ext_mem *ext_mem)
+{
+	struct tdx_page_array *chunk;
+	struct page **pages;
+	struct page *page;
+	int i, ret;
 
-		ret = tdx_ext_mem_add(ext_mem);
+	pages = kmalloc_objs(*pages, nr_pages);
+	if (!pages)
+		return -ENOMEM;
+
+	page = alloc_contig_pages(nr_pages, GFP_KERNEL, numa_mem_id(),
+				  &node_online_map);
+	if (!page) {
+		ret = -ENOMEM;
+		goto out_free_pages;
+	}
+
+	for (i = 0; i < nr_pages; i++)
+		pages[i] = page + i;
+
+	chunk = tdx_page_array_alloc();
+	if (!chunk) {
+		ret = -ENOMEM;
+		goto out_free_contig;
+	}
+
+	for (i = 0; i < nr_pages;) {
+		int nents = min(nr_pages - i, TDX_PAGE_ARRAY_MAX_NENTS);
+
+		ret = tdx_page_array_populate(chunk, pages + i, nents);
 		if (ret)
-			return ret;
+			goto out_free_chunk;
+
+		ret = tdx_ext_mem_add(chunk);
+		if (ret)
+			goto out_free_chunk;
 
-		offset += populated;
+		i += nents;
 	}
 
+	ext_mem->nr_pages = nr_pages;
+	ext_mem->pages = pages;
+	ext_mem->chunk = chunk;
+
 	return 0;
+
+out_free_chunk:
+	tdx_page_array_free(chunk);
+out_free_contig:
+	for (i = 0; i < nr_pages; i++)
+		__free_page(pages[i]);
+out_free_pages:
+	kfree(pages);
+
+	return ret;
 }
 
 static int init_tdx_ext(void)
 {
-	struct tdx_page_array *ext_mem = NULL;
+	struct tdx_ext_mem ext_mem;
 	unsigned int nr_pages;
 	int ret;
 
@@ -1600,48 +1396,48 @@ static int init_tdx_ext(void)
 	if (boot_cpu_has_bug(X86_BUG_TDX_PW_MCE))
 		return -ENXIO;
 
+	/* No feature requires TDX Module Extensions. */
+	if (!tdx_sysinfo.ext.ext_required)
+		return 0;
+
 	nr_pages = tdx_sysinfo.ext.memory_pool_required_pages;
 	/*
 	 * memory_pool_required_pages == 0 means no need to add more pages,
 	 * skip the memory setup.
 	 */
 	if (nr_pages) {
-		ext_mem = tdx_page_array_alloc_contig(nr_pages);
-		if (!ext_mem)
-			return -ENOMEM;
-
-		ret = tdx_ext_mem_setup(ext_mem);
+		ret = tdx_ext_mem_setup(nr_pages, &ext_mem);
 		if (ret)
-			goto out_ext_mem;
+			return ret;
 	}
 
+	ret = tdx_ext_init();
+	if (ret)
+		goto out_remove_ext_mem;
+
 	/*
-	 * ext_required == 0 means no need to call TDH.EXT.INIT, the Extensions
-	 * are already working.
+	 * Extensions memory is never reclaimed once assigned, stop tracking it
+	 * and free the tracking structures.
 	 */
-	if (tdx_sysinfo.ext.ext_required) {
-		ret = tdx_ext_init();
-		/*
-		 * Some pages may have been touched by the TDX module.
-		 * Flush cache before returning these pages to kernel.
-		 */
-		if (ret)
-			goto out_flush;
-	}
-
-	/* Extension memory is never reclaimed once assigned */
-	tdx_page_array_ctrl_leak(ext_mem);
+	tdx_page_array_free(ext_mem.chunk);
+	kfree(ext_mem.pages);
 
 	pr_info("%lu KB allocated for TDX Module Extensions\n",
 		nr_pages * PAGE_SIZE / 1024);
 
 	return 0;
 
-out_flush:
-	if (ext_mem)
+out_remove_ext_mem:
+	if (nr_pages) {
+		/*
+		 * TDH.EXT.MEM.ADD only collects required memory. TDX.EXT.INIT
+		 * does the actual initialization so if it fails some pages may
+		 * have been touched by the TDX module, flush cache before
+		 * returning these pages to kernel.
+		 */
 		wbinvd_on_all_cpus();
-out_ext_mem:
-	tdx_page_array_free(ext_mem);
+		tdx_ext_mem_remove(&ext_mem);
+	}
 
 	return ret;
 }
@@ -2497,6 +2293,7 @@ u64 tdh_iommu_setup(u64 vtbar, struct tdx_page_array *iommu_mt, u64 *iommu_id)
 	u64 r;
 
 	tdx_clflush_page_array(iommu_mt);
+	iommu_mt->flush_on_free = true;
 
 	r = seamcall_ret_ir_resched(TDH_IOMMU_SETUP, &args);
 
@@ -2525,6 +2322,7 @@ u64 tdh_spdm_create(u64 func_id, struct tdx_page_array *spdm_mt, u64 *spdm_id)
 	u64 r;
 
 	tdx_clflush_page_array(spdm_mt);
+	spdm_mt->flush_on_free = true;
 
 	r = seamcall_ret(TDH_SPDM_CREATE, &args);
 
@@ -2534,23 +2332,14 @@ u64 tdh_spdm_create(u64 func_id, struct tdx_page_array *spdm_mt, u64 *spdm_id)
 }
 EXPORT_SYMBOL_FOR_MODULES(tdh_spdm_create, "tdx-host");
 
-u64 tdh_spdm_delete(u64 spdm_id, struct tdx_page_array *spdm_mt,
-		    unsigned int *nr_released, u64 *released_hpa)
+u64 tdh_spdm_delete(u64 spdm_id, struct tdx_page_array *spdm_mt)
 {
 	struct tdx_module_args args = {
 		.rcx = spdm_id,
 		.rdx = hpa_array_t_release_raw(spdm_mt),
 	};
-	u64 r;
-
-	r = seamcall_ret(TDH_SPDM_DELETE, &args);
-	if (r != TDX_SUCCESS)
-		return r;
 
-	*nr_released = FIELD_GET(HPA_ARRAY_T_SIZE, args.rcx) + 1;
-	*released_hpa = FIELD_GET(HPA_ARRAY_T_PFN, args.rcx) << PAGE_SHIFT;
-
-	return r;
+	return seamcall_ret(TDH_SPDM_DELETE, &args);
 }
 EXPORT_SYMBOL_FOR_MODULES(tdh_spdm_delete, "tdx-host");
 
@@ -2639,6 +2428,7 @@ u64 tdh_ide_stream_create(u64 stream_info, u64 spdm_id,
 	u64 r;
 
 	tdx_clflush_page_array(stream_mt);
+	stream_mt->flush_on_free = true;
 
 	r = seamcall_saved_ret(TDH_IDE_STREAM_CREATE, &args);
 
@@ -2661,24 +2451,15 @@ u64 tdh_ide_stream_block(u64 spdm_id, u64 stream_id)
 EXPORT_SYMBOL_FOR_MODULES(tdh_ide_stream_block, "tdx-host");
 
 u64 tdh_ide_stream_delete(u64 spdm_id, u64 stream_id,
-			  struct tdx_page_array *stream_mt,
-			  unsigned int *nr_released, u64 *released_hpa)
+			  struct tdx_page_array *stream_mt)
 {
 	struct tdx_module_args args = {
 		.rcx = spdm_id,
 		.rdx = stream_id,
 		.r8 = hpa_array_t_release_raw(stream_mt),
 	};
-	u64 r;
 
-	r = seamcall_ret(TDH_IDE_STREAM_DELETE, &args);
-	if (r != TDX_SUCCESS)
-		return r;
-
-	*nr_released = FIELD_GET(HPA_ARRAY_T_SIZE, args.rcx) + 1;
-	*released_hpa = FIELD_GET(HPA_ARRAY_T_PFN, args.rcx) << PAGE_SHIFT;
-
-	return r;
+	return seamcall_ret(TDH_IDE_STREAM_DELETE, &args);
 }
 EXPORT_SYMBOL_FOR_MODULES(tdh_ide_stream_delete, "tdx-host");
 
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 7800afb0893d..3a37e78dbc89 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -83,6 +83,119 @@ static struct tdx_tsm_link *to_tdx_tsm_link(struct pci_tsm *tsm)
 	return container_of(tsm, struct tdx_tsm_link, pci.base_tsm);
 }
 
+static void tdx_free_pages_bulk(unsigned int nr_pages, struct page **pages)
+{
+	int i;
+
+	for (i = 0; i < nr_pages; i++)
+		put_page(pages[i]);
+}
+
+static int tdx_alloc_pages_bulk(unsigned int nr_pages, struct page **pages)
+{
+	unsigned int filled, done = 0;
+
+	do {
+		filled = alloc_pages_bulk(GFP_KERNEL, nr_pages - done,
+					  pages + done);
+		if (!filled) {
+			tdx_free_pages_bulk(done, pages);
+			return -ENOMEM;
+		}
+
+		done += filled;
+	} while (done != nr_pages);
+
+	return 0;
+}
+
+static void tdx_page_array_mt_free(struct tdx_page_array *array_mt)
+{
+	struct page **pages = array_mt->pages;
+	unsigned int nr_pages = array_mt->nr_pages;
+
+	tdx_page_array_free(array_mt);
+	tdx_free_pages_bulk(nr_pages, pages);
+	kfree(pages);
+}
+
+DEFINE_FREE(tdx_page_array_mt_free, struct tdx_page_array *, if (_T) tdx_page_array_mt_free(_T))
+
+static struct tdx_page_array *tdx_page_array_mt_create(unsigned int nr_pages)
+{
+	struct tdx_page_array *array;
+	struct page **pages;
+	int ret;
+
+	pages = kzalloc_objs(*pages, nr_pages);
+	if (!pages)
+		return NULL;
+
+	ret = tdx_alloc_pages_bulk(nr_pages, pages);
+	if (ret)
+		goto out_free_pages;
+
+	array = tdx_page_array_create(pages, nr_pages);
+	if (!array)
+		goto out_free_bulk;
+
+	return array;
+
+out_free_bulk:
+	tdx_free_pages_bulk(nr_pages, pages);
+out_free_pages:
+	kfree(pages);
+
+	return NULL;
+}
+
+static struct tdx_page_array *
+tdx_page_array_iommu_mt_create(unsigned int iq_order, unsigned int nr_mt_pages)
+{
+	unsigned int nr_pages = nr_mt_pages + 2;
+	struct tdx_page_array *array;
+	struct folio *t_iq, *t_ctxiq;
+	struct page **pages;
+	int ret;
+
+	pages = kzalloc_objs(*pages, nr_pages);
+	if (!pages)
+		return NULL;
+
+	/* TODO: folio_alloc_node() is preferred, but need numa info */
+	t_iq = folio_alloc(GFP_KERNEL | __GFP_ZERO, iq_order);
+	if (!t_iq)
+		goto out_free_pages;
+
+	t_ctxiq = folio_alloc(GFP_KERNEL | __GFP_ZERO, iq_order);
+	if (!t_ctxiq)
+		goto out_free_t_iq;
+
+	pages[0] = folio_page(t_iq, 0);
+	pages[1] = folio_page(t_ctxiq, 0);
+
+	ret = tdx_alloc_pages_bulk(nr_mt_pages, pages + 2);
+	if (ret)
+		goto out_free_t_ctxiq;
+
+	array = tdx_page_array_create(pages, nr_pages);
+	if (!array)
+		goto out_free_bulk;
+
+	return array;
+
+out_free_bulk:
+	tdx_free_pages_bulk(nr_mt_pages, pages + 2);
+out_free_t_ctxiq:
+	folio_put(t_ctxiq);
+out_free_t_iq:
+	folio_put(t_iq);
+out_free_pages:
+	kfree(pages);
+
+	return NULL;
+}
+
 #define PCI_DOE_DATA_OBJECT_HEADER_1_OFFSET	0
 #define PCI_DOE_DATA_OBJECT_HEADER_2_OFFSET	4
 #define PCI_DOE_DATA_OBJECT_HEADER_SIZE		8
@@ -275,8 +388,8 @@ static struct tdx_tsm_link *tdx_spdm_create(struct tdx_tsm_link *tlink)
 	unsigned int nr_pages = tdx_sysinfo->connect.spdm_mt_page_count;
 	u64 spdm_id, r;
 
-	struct tdx_page_array *spdm_mt __free(tdx_page_array_free) =
-		tdx_page_array_create(nr_pages);
+	struct tdx_page_array *spdm_mt __free(tdx_page_array_mt_free) =
+		tdx_page_array_mt_create(nr_pages);
 	if (!spdm_mt)
 		return ERR_PTR(-ENOMEM);
 
@@ -292,24 +405,18 @@ static struct tdx_tsm_link *tdx_spdm_create(struct tdx_tsm_link *tlink)
 static void tdx_spdm_delete(struct tdx_tsm_link *tlink)
 {
 	struct pci_dev *pdev = tlink->pci.base_tsm.pdev;
-	unsigned int nr_released;
-	u64 released_hpa, r;
+	u64 r;
 
-	r = tdh_spdm_delete(tlink->spdm_id, tlink->spdm_mt, &nr_released, &released_hpa);
+	r = tdh_spdm_delete(tlink->spdm_id, tlink->spdm_mt);
 	if (r) {
+		/* leak the metadata pages */
 		pci_err(pdev, "fail to delete spdm 0x%llx\n", r);
-		goto leak;
+		return;
 	}
 
-	if (tdx_page_array_ctrl_release(tlink->spdm_mt, nr_released, released_hpa)) {
-		pci_err(pdev, "fail to release spdm_mt pages\n");
-		goto leak;
-	}
+	tdx_page_array_mt_free(tlink->spdm_mt);
 
 	return;
-
-leak:
-	tdx_page_array_ctrl_leak(tlink->spdm_mt);
 }
 
 DEFINE_FREE(tdx_spdm_delete, struct tdx_tsm_link *, if (!IS_ERR_OR_NULL(_T)) tdx_spdm_delete(_T))
@@ -323,8 +430,8 @@ static struct tdx_tsm_link *tdx_spdm_session_setup(struct tdx_tsm_link *tlink)
 	if (IS_ERR(tlink_create))
 		return tlink_create;
 
-	struct tdx_page_array *dev_info __free(tdx_page_array_free) =
-		tdx_page_array_create(nr_pages);
+	struct tdx_page_array *dev_info __free(tdx_page_array_mt_free) =
+		tdx_page_array_mt_create(nr_pages);
 	if (!dev_info)
 		return ERR_PTR(-ENOMEM);
 
@@ -424,8 +531,8 @@ static struct tdx_tsm_link *tdx_ide_stream_create(struct tdx_tsm_link *tlink,
 	struct pci_ide_regs regs;
 	u64 r;
 
-	struct tdx_page_array *stream_mt __free(tdx_page_array_free) =
-		tdx_page_array_create(nr_pages);
+	struct tdx_page_array *stream_mt __free(tdx_page_array_mt_free) =
+		tdx_page_array_mt_create(nr_pages);
 	if (!stream_mt)
 		return ERR_PTR(-ENOMEM);
 
@@ -472,33 +579,23 @@ static struct tdx_tsm_link *tdx_ide_stream_create(struct tdx_tsm_link *tlink,
 static void tdx_ide_stream_delete(struct tdx_tsm_link *tlink)
 {
 	struct pci_dev *pdev = tlink->pci.base_tsm.pdev;
-	unsigned int nr_released;
-	u64 released_hpa, r;
+	u64 r;
 
 	r = tdh_ide_stream_block(tlink->spdm_id, tlink->stream_id);
 	if (r) {
+		/* leak the metadata pages */
 		pci_err(pdev, "ide stream block fail 0x%llx\n", r);
-		goto leak;
+		return;
 	}
 
 	r = tdh_ide_stream_delete(tlink->spdm_id, tlink->stream_id,
-				  tlink->stream_mt, &nr_released,
-				  &released_hpa);
+				  tlink->stream_mt);
 	if (r) {
 		pci_err(pdev, "ide stream delete fail 0x%llx\n", r);
-		goto leak;
-	}
-
-	if (tdx_page_array_ctrl_release(tlink->stream_mt, nr_released,
-					released_hpa)) {
-		pci_err(pdev, "fail to release IDE stream_mt pages\n");
-		goto leak;
+		return;
 	}
 
-	return;
-
-leak:
-	tdx_page_array_ctrl_leak(tlink->stream_mt);
+	tdx_page_array_mt_free(tlink->stream_mt);
 }
 
 DEFINE_FREE(tdx_ide_stream_delete, struct tdx_tsm_link *,
@@ -815,20 +912,14 @@ static void tdx_iommu_clear(u64 iommu_id, struct tdx_page_array *iommu_mt)
 
 	r = tdh_iommu_clear(iommu_id, iommu_mt);
 	if (r) {
+		/* leak the metadata pages */
 		pr_err("fail to clear tdx iommu 0x%llx\n", r);
-		goto leak;
+		return;
 	}
 
-	if (tdx_page_array_ctrl_release(iommu_mt, iommu_mt->nr_pages,
-					virt_to_phys(iommu_mt->root))) {
-		pr_err("fail to release iommu_mt pages\n");
-		goto leak;
-	}
+	tdx_page_array_mt_free(iommu_mt);
 
 	return;
-
-leak:
-	tdx_page_array_ctrl_leak(iommu_mt);
 }
 
 static int tdx_iommu_enable_one(struct dmar_drhd_unit *drhd)
@@ -837,8 +928,8 @@ static int tdx_iommu_enable_one(struct dmar_drhd_unit *drhd)
 	u64 r, iommu_id;
 	int ret;
 
-	struct tdx_page_array *iommu_mt __free(tdx_page_array_free) =
-		tdx_page_array_create_iommu_mt(1, nr_pages);
+	struct tdx_page_array *iommu_mt __free(tdx_page_array_mt_free) =
+		tdx_page_array_iommu_mt_create(1, nr_pages);
 	if (!iommu_mt)
 		return -ENOMEM;

---

## [100] Xu Yilun — 2026-04-16
*Subject: Re: [PATCH v2 03/31] x86/virt/tdx: Add tdx_page_array helpers for
 new TDX Module objects*

> > A main difference is HPA_ARRAY_T requires singleton mode when
> > containing just 1 functional page (page0). In this mode the root page is

Yes, it is already the case.

> unfortunate distraction. If it can ever be the case that CREATE and
> DELETE are asymmetric on success then that needs to be corrected and

Agree. Thanks for this summary as well as the singleton-mode one.

> 
> I think that cleans up a bulk of the logic here to abandon caring that

Yes, I'll delete all these "released page matching" logic.

---

## [101] Dan Williams — 2026-04-17
*Subject: Re: [PATCH v2 03/31] x86/virt/tdx: Add tdx_page_array helpers for new
 TDX Module objects*

Xu Yilun wrote:
[..]
> The usage of tdx_page_array will be in following patches.
> 
[..]
> +static struct tdx_page_array *
> +tdx_page_array_alloc(unsigned int nr_pages)

This should now be:

    kzalloc_objs(struct page *, nr_pages);

...oh nevermind you caught that in your incremental fixup. ...but a
couple more comments below:

[..]
> +
> +#define HPA_LIST_INFO_FIRST_ENTRY	GENMASK_U64(11, 3)

2 quick comments:

* I do not understand shipping a __maybe_unused helper in patch 3 that
  does not get used until patch10.

* The "assign_raw" verb feels strange. I think this probably just want
  to be called: to_hpa_list_info(struct tdx_page_array *)

> +{
> +	return FIELD_PREP(HPA_LIST_INFO_FIRST_ENTRY, 0) |

to_hpa_array_t()

> +{
> +	unsigned long pfn;

It seems too subtle that this function sometimes returns zero and
sometimes returns a page that the TDX module will clobber with data that
we do not care about.

It is also not clear that "0" is what the module considers a valid value
that meets "checks its validity for forward compatibility". I guess we
get lucky because all of the calls that need this presently are
multi-page cases?

I would feel better if this always returned the root HPA and was called
something like:

    to_output_clobber(), or to_aux_clobber()

...to make it clear that whatever was there before gets destroyed.

---

## [102] Dan Williams — 2026-04-17
*Subject: Re: [PATCH v2 05/31] x86/virt/tdx: Extend tdx_page_array to support
 IOMMU_MT*

Xu Yilun wrote:
[..]
> > 
> > I'm drafting some changes and make the tdx_page_array look like:

How about "need_phymem_page_wbinvd"?

That makes it a bit more greppable and not to be confused with other
flushing.

[..]
> Hi, I end up made the following changes on top of this series:
> 

Wait, these pages belong to the module now, they can't be freed, or I am
missing something?

> +	kfree(ext_mem.pages);

Releasing this makes sense.

>  
>  	pr_info("%lu KB allocated for TDX Module Extensions\n",

This only releases the last populated chunk, not all previous chunks,
right?

---

## [103] Dan Williams — 2026-04-17
*Subject: Re: [PATCH v2 04/31] x86/virt/tdx: Support allocating contiguous
 pages for tdx_page_array*

Xu Yilun wrote:
> The current tdx_page_array implementation allocates scattered order-0
> pages. However, some TDX Module operations benefit from contiguous

Will skip this one as I see it gets massively reworked in your
incremental update. The change to make the caller responsible for
creating the page array is great.

---

## [104] Xu Yilun — 2026-04-19
*Subject: Re: [PATCH v2 05/31] x86/virt/tdx: Extend tdx_page_array to support
 IOMMU_MT*

On Fri, Apr 17, 2026 at 04:58:43PM -0700, Dan Williams wrote:
> Xu Yilun wrote:
> [..]

Yes.

> 
> That makes it a bit more greppable and not to be confused with other

With this new solution, tdx_page_array is downgraded to a descriptor,
doesn't manage the actual data pages/memory any more. So
tdx_page_array_free() will not free data pages, only frees the
tdx_page_array descriptor.

> 
> > +	kfree(ext_mem.pages);

Not true. ext_mem stores all the data pages and the reusable descriptor
'chunk' for SEAMCALL. tdx_ext_mem_remove() removes all the data pages
and the 'chunk'.

---

## [105] Xu Yilun — 2026-04-19
*Subject: Re: [PATCH v2 03/31] x86/virt/tdx: Add tdx_page_array helpers for
 new TDX Module objects*

> > +#define HPA_LIST_INFO_FIRST_ENTRY	GENMASK_U64(11, 3)
> > +#define HPA_LIST_INFO_PFN		GENMASK_U64(51, 12)

You once had a comment wanting to see how a tdx_page_array collapses to
a 64-bit raw value for SEAMCALLs in the same patch. So I move the
helpers earlier. Do you want to change them back?

Personally, I'd like to keep them here, to better align with the
illustration in commit log about why we need the tdx_page_array.

> 
> * The "assign_raw" verb feels strange. I think this probably just want

It's a better name, thanks.

[...]

> > +{
> > +	unsigned long pfn;

It is the TDX Module's requirement, which is 'too subtle'. TDX Module
tries to keep align with the singleton definition for its output
hpa_array_t. If TDX Module wants to output multiple released pages, it
requires VMM to provide a root page HPA (in input register) so it can
write HPA list on the root page. But if it outputs one released page, it
directly writes page0 HPA in output register, and doesn't need a root
page HPA in input register and enforce its value 0.

That's why we return 0 on singleton mode, otherwise a root page HPA.

> get lucky because all of the calls that need this presently are
> multi-page cases?

Let me experiment, see if we have chance to simplify things.

> 
> I would feel better if this always returned the root HPA and was called

No, we can't. We must provide 0 for singleton mode. So I think maybe

      to_hpa_array_t_released()


Anyway, Linux doesn't need the output hpa_array_t. I've already raised
to Module team that don't enforce the medium page input. If VMM doesn't
provide the page, don't bother fill it.

> something like:
>

---

## [106] Dan Williams — 2026-04-21
*Subject: Re: [PATCH v2 05/31] x86/virt/tdx: Extend tdx_page_array to support
 IOMMU_MT*

Xu Yilun wrote:
> On Fri, Apr 17, 2026 at 04:58:43PM -0700, Dan Williams wrote:
> > Xu Yilun wrote:

Oh, I was confused by the fact that tdx_page_array_free() still loops
through array->pages in the need_wbinvd case. In the case of "never
reclaim" it will also "never wbinvd". ...and this why populate has that
"WARN_ON_ONCE(array->pages && array->flush_on_free);".

A couple recommendations come to mind:

* s/tdx_page_array_free/tdx_page_array_destroy/

  ...since "destroy" mirrors create and matches other cases where only
  metadata is managed.

* Create a new tdx_page_array_repopulate() helper to make it clear which
  paths depend on being able to repopulate and move the WARN_ON_ONCE() out of
  the common path that does not repopulate. "repopulate" can have
  "realloc" semantics where it allocates on first use, but otherwise
  "populate" gets to not care about the corner cases. Make the WARN case
  fail repopulate.

> > >  	pr_info("%lu KB allocated for TDX Module Extensions\n",
> > >  		nr_pages * PAGE_SIZE / 1024);

Yes, see that now.

---

## [107] Dan Williams — 2026-04-21
*Subject: Re: [PATCH v2 06/31] x86/virt/tdx: Read global metadata for TDX
 Module Extensions/Connect*

Xu Yilun wrote:
> Add reading of the global metadata for TDX Module Extensions & TDX
> Connect. Add them in a batch as TDX Connect is currently the only user

I think it is important to distinguish "optional" module features vs
required Linux features. Linux requires all features that a module
advertises to succeed at core TDX init time.

Otherwise, this looks ok / consistent with other metadata reading. It 
sets the precedent that if TDX Connect is advertised it must succeed all
core initialization.

---

## [108] Dan Williams — 2026-04-21
*Subject: Re: [PATCH v2 08/31] x86/virt/tdx: Configure TDX Module with optional
 TDX Connect feature*

Xu Yilun wrote:
> TDX Module supports optional TDX features (e.g. TDX Connect & TDX Module
> Extensions) that won't be enabled by default.

So this is another place where "optional" is misleading. For simplicity
there is no mechanism to fallback from TDX Connect operation if present,
at least in the core. The only optional aspects would be the mechanism
that could be unloaded through the tdx_host driver.

.../me notices that other comments on this patch say the same, but do
read on, another important detail about ktime_get_real_seconds() below.

> It extends TDH.SYS.CONFIG for host to choose to enable them on bootup.
> 

I would say this differently, it will always be the case that new
kernels are needed to enable new features, but it is unlikely that
TDH.SYS.CONFIG ever needs to change again. The v0 -> v1 transition means
that feature bits are to be used here on out. So there is little value
in worrying about deprecating v0 to save a couple lines of code in 5-7
years when these original TDX platforms sunset.

> TDX Module updates global metadata when optional features are enabled.
> Host should update the cached tdx_sysinfo to reflect these changes.

Mainline has reason to not entertain this module requirement. The fact
that passing zero is an error is useful to detect unsupported modules.
An updated module would accept zero as indicating "VMM requests module
disable all policy and mechanisms related to untrusted wall clock time".
Specifically, there are several problems with this:

1/ No other TSM implementation requires the VMM to pass in an untrusted time
2/ The wall time may change and may require hooks to keep the module time
   up to date, but see point 1/, this would be a TDX special flower hook.
3/ Presumably this allows the module or the guest to do certificate expiration
   checks, but that is the responsibility of the relying party. The
   relying party may have reason to accept an "expired" cert as determined
   by VMM wall clock, and the guest presumably already has mechanisms to
   determine untrusted wall clock time from the VMM if it wants. Guests
   do not need TDX ABI for that.

So I think Linux wants to pass 0 here and wait for modules that accept
that as the start of TDX Connect support. As you said, given there are
no released modules with TDX Connect there is time to make that first
release drop this requirement.

---

## [109] Xu Yilun — 2026-04-22
*Subject: Re: [PATCH v2 19/31] iommu/vt-d: Reserve the MSB domain ID bit for
 the TDX module*

> Here we need more words to explain the strategy here.
> 

Yes, that's the rationale. I'll add it to comments.

> 
> btw in patch23 commit msg:

Ah, good catch. Let me explain:

ecap_tdxc does report the capability. This bit is special cause both
trusted part & untrusted part access it.

For IOMMU driver (which now handles the untrusted part), it can directly
query to this bit and decide what to do.

But for tdx-host driver which handles the trusted part, it shouldn't
speculate into the IOMMU for capability enumeration. TDX Module has more
concerns about trusted capability, including the related I/O stack
capabilities e.g. SPDM/IDE cap...  So in patch23 I actually mean we
don't have an enumeration SEAMCALL for trusted capability, I will
refactor that message:

    There is no dedicated *SEAMCALL* to enumerate which IOMMU devices support
    trusted operations...

> 
> anyway all of those need a better explanation here...

---

## [110] Xu Yilun — 2026-04-22
*Subject: Re: [PATCH v2 20/31] x86/virt/tdx: Add a helper to loop on
 TDX_INTERRUPTED_RESUMABLE*

On Thu, Apr 09, 2026 at 07:21:48AM +0000, Tian, Kevin wrote:
> > From: Xu Yilun <yilun.xu@linux.intel.com>
> > Sent: Saturday, March 28, 2026 12:01 AM

Mm.. I want to 'ir' to reflect the loop-retry is dedicated for
INTERRUPTED_RESUMABLE in TDX context. When you say not big deal, I
assume I can keep the naming?

> 
> not big deal, just a bit confusing when seeing it in IOMMU side where

---

## [111] Xu Yilun — 2026-04-22
*Subject: Re: [PATCH v2 21/31] x86/virt/tdx: Add SEAMCALL wrappers for trusted
 IOMMU setup and clear*

On Thu, Apr 09, 2026 at 07:30:32AM +0000, Tian, Kevin wrote:
> > From: Xu Yilun <yilun.xu@linux.intel.com>
> > Sent: Saturday, March 28, 2026 12:01 AM

Some extended HW resources in IOMMU so I think the later.

> 
> If the latter it's clearer to say "trusted configuration in IOMMU".

Yeah. And I realized there are more configuration except IOMMU, so I
would say:

  Add SEAMCALLs to setup/clear the IOMMU device and related I/O stack to
  work in trusted (TDX) mode.

> 
> > 

This is truely obscure. I want to clarify some potential concern about
why we need to setup IOMMU when only to enable PCIe link encryption, my
re-phase:

    With the setup SEAMCALL, TDX Module ensures that related resources in
    the IOMMU device & I/O stack are in expected state and protected from
    further untrusted access, so that subsequent SPDM/IDE enabling is
    secure.

> 
> > 

Yes.

> 
> intel-iommu driver already has its own 'id' definition for each iommu device.

Yes.

---

## [112] Xu Yilun — 2026-04-22
*Subject: Re: [PATCH v2 22/31] iommu/vt-d: Export a helper to do function for
 each dmar_drhd_unit*

On Thu, Apr 09, 2026 at 07:49:46AM +0000, Tian, Kevin wrote:
> > From: Xu Yilun <yilun.xu@linux.intel.com>
> > Sent: Saturday, March 28, 2026 12:01 AM

Sorry, it is following for_each_iommu(), is it?

> 
> > +

No, for_each_active_drhd_unit() is good.

---

## [113] Xu Yilun — 2026-04-22
*Subject: Re: [PATCH v2 23/31] coco/tdx-host: Setup all trusted IOMMUs on TDX
 Connect init*

On Thu, Apr 09, 2026 at 07:51:56AM +0000, Tian, Kevin wrote:
> > From: Xu Yilun <yilun.xu@linux.intel.com>
> > Sent: Saturday, March 28, 2026 12:01 AM

This is to say the TDH.IOMMU.SETUP relates to PCIe SPDM/IDE, it is not
just about IOMMU. By identifying the

  for_each_iommu(iommu)
	tdh.iommu.setup(iommu)

as a platform configuration, it justifies why we trigger this
configuration at tdx-host driver probe, rather than in some
IOMMU/IOMMUFD API.

---

## [114] Xu Yilun — 2026-04-22
*Subject: Re: [PATCH v2 24/31] coco/tdx-host: Add a helper to exchange SPDM
 messages through DOE*

On Thu, Apr 09, 2026 at 07:56:06AM +0000, Tian, Kevin wrote:
> > From: Xu Yilun <yilun.xu@linux.intel.com>
> > Sent: Saturday, March 28, 2026 12:01 AM

I don't think so. There is kernel managed spdm transfer support WIP,
which is another topic.  We don't want to mix the namespace with that
one.

And we also don't name it tsm_spdm_msg_exchange, cause TSM firmwares
output different blobs for vendor TSM drivers to transfer. E.g. TDX
Module outputs buffers with DOE header & SPDM header, other vendors
(AMD IIRC) outputs buffers with only SPDM header. So this function is
TDX specific.

> 
> there is no other use of tlink in this function. could add a note that

---

## [115] Xu Yilun — 2026-04-22
*Subject: Re: [PATCH v2 25/31] x86/virt/tdx: Add SEAMCALL wrappers for SPDM
 management*

On Thu, Apr 09, 2026 at 07:59:33AM +0000, Tian, Kevin wrote:
> > From: Xu Yilun <yilun.xu@linux.intel.com>
> > Sent: Saturday, March 28, 2026 12:01 AM

Ah, yes. But only tdx-host driver which implements link encryption cares
about these operation code. My preference is only define general the
SEAMCALL wrapper format in TDX core as other SEAMCALL do. And leave the
specific op code definition in tdx-host driver.

I can revise the commit log as:

   - TDH.SPDM.MNG supports various SPDM runtime operations: HEARTBEAT,
     KEY_UPDATE, DEV_INFO_RECOLLECTION... These operation codes are defined
     in tdx-host driver.
 
Thanks.

> 
> > +u64 tdh_exec_spdm_mng(u64 spdm_id, u64 spdm_op, struct page

---

## [116] Xu Yilun — 2026-04-22
*Subject: Re: [PATCH v2 27/31] coco/tdx-host: Implement SPDM session setup*

> > +#define TDISP_FUNC_ID		GENMASK(15, 0)
> > +#define TDISP_FUNC_ID_SEGMENT		GENMASK(23, 16)

This is the func_id format defined in TDISP SPEC, bit 24 is a must. It
is not the linux defined SBDF format.

> 
> > +	func_id |= FIELD_PREP(TDISP_FUNC_ID,

Yes.

...

> > +static void *tdx_dup_array_data(struct tdx_page_array *array,
> > +				unsigned int data_size)

Yes.

...

> > +DEFINE_FREE(tdx_spdm_session_teardown, struct tdx_tsm_link *,
> > +	    if (!IS_ERR_OR_NULL(_T)) tdx_spdm_session_teardown(_T))

Ah, we have more steps to add, the __free() will take function when the
following steps fail.

We may add __free() when we add more steps, but I think that makes the
diff harder to read, so I want to keep this style.

Thanks.

> 
>

---

## [117] Xu Yilun — 2026-04-22
*Subject: Re: [PATCH v2 30/31] coco/tdx-host: Implement IDE stream
 setup/teardown*

On Thu, Apr 09, 2026 at 08:02:33AM +0000, Tian, Kevin wrote:
> > From: Xu Yilun <yilun.xu@linux.intel.com>
> > Sent: Saturday, March 28, 2026 12:02 AM

Actually it is " *most* straightforward", I just mean "very".

---

## [118] Huang, Kai — 2026-04-23
*Subject: Re: [PATCH v2 20/31] x86/virt/tdx: Add a helper to loop on
 TDX_INTERRUPTED_RESUMABLE*

On Sat, 2026-03-28 at 00:01 +0800, Xu Yilun wrote:
> +static u64 __maybe_unused __seamcall_ir_resched(sc_func_t sc_func, u64 fn,
> +						struct tdx_module_args *args)

Since commit 7dadeaa6e851e ("sched: Further restrict the preemption modes")
for x86 only PREEMPT (full) and PREEMPT_LAZY are possible, even when
PREEMPT_DYNAMIC is on.

cond_resched() is useful in PREEMPT_NONE and PREEMPT_VOLUNTARY, but it is
basically a RET0 in both PREEMPT_LAZY and PREEMPT.  My understanding is we
shouldn't add any more cond_resched() for x86 now (see the aforementioned
commit changelog for more info).

---

## [119] Huang, Kai — 2026-04-23
*Subject: Re: [PATCH v2 10/31] x86/virt/tdx: Add extra memory to TDX Module for
 Extensions*

On Sat, 2026-03-28 at 00:01 +0800, Xu Yilun wrote:
> +static int tdx_ext_mem_add(struct tdx_page_array *ext_mem)
> +{


Ditto here.  I don't think we should introduce any more cond_resched().

Btw, I think technically we can reuse the seamcall_ir_resched() you introduced
later, albeit in which a local '_args' is used as a copy of the original 'args',
but that has no harm for the case where we can just use the 'args' to loop.

I am wondering whether we can just use that here, or we just get rid of that
helper (then open retry by the callers of these SEAMCALL wrappers), since there
will be more cases where we need to manually set 'resume=1' in the SEAMCALL
input 'args' when retrying TDX_INTERRUPTED_RESUMABLE.

Unless you have good idea to unify them all?

E.g., we have something like below in our internal KVM code, using macros to do
'resume=1' and retry as the caller wishes.  But my understanding is Dave
probably won't like macros.  :-)

(you may see broken indent/text due to text wrapper and sorry for that.) 

/*
 * ...
 *
 * The retry_func and update_args allow the SEAMCALL to be retried in a loop if
 * it can still return other error code when there's no race from both KVM and 
 * vCPUs and can be "retried" until it succeeds.                               
 */
#define tdh_do_no_vcpus_retry(tdh_func, kvm, retry_func, update_args, args...)\
({                                                                            \
        struct kvm_tdx *__kvm_tdx = to_kvm_tdx(kvm);                          \
        u64 __err;                                                            \
                                                                              \
        lockdep_assert_held_write(&kvm->mmu_lock);                            \
                                                                              \
        __err = retry_func(tdh_func, update_args, args);                      \
        if (unlikely(tdx_operand_busy(__err))) {                              \
                WRITE_ONCE(__kvm_tdx->wait_for_sept_zap, true);               \
                kvm_make_all_cpus_request(kvm, KVM_REQ_OUTSIDE_GUEST_MODE);   \
                                                                              \
                __err = retry_func(tdh_func, update_args, args);              \
                                                                              \
                WRITE_ONCE(__kvm_tdx->wait_for_sept_zap, false);              \
        }                                                                     \
        __err;                                                                \
})                                                                             

#define tdh_intr_retry(tdh_func, update_args, args...)                        \
({                                                                            \
        u64 ____err;                                                          \
                                                                              \
        do {                                                                  \
                ____err = tdh_func(args);                                     \
                                                                              \
                if ((____err & TDX_SEAMCALL_STATUS_MASK) !=		      \
				TDX_INTERRUPTED_RESUMABLE)                   
\	                       
                        break;                                                \
                                                                              \
                update_args;                                                  \
        } while (1);                                                          \
        ____err;                                                              \
})

#define tdh_no_retry(tdh_func, update_args, args...)    tdh_func(args)

#define tdh_do_no_vcpus(tdh_func, kvm, args...) \
        tdh_do_no_vcpus_retry(tdh_func, kvm, tdh_no_retry, ;, args)

#define tdh_do_no_vcpus_intr_retry(tdh_func, kvm, update_args, args...) \
        tdh_do_no_vcpus_retry(tdh_func, kvm, tdh_intr_retry, update_args, args)

---

## [120] Xu Yilun — 2026-04-23
*Subject: Re: [PATCH v2 05/31] x86/virt/tdx: Extend tdx_page_array to support
 IOMMU_MT*

> A couple recommendations come to mind:
> 

Agree. I end up add a function like that:


/**
 * tdx_page_array_repopulate() - repopulate a tdx_page_array
 * @array: The array descriptor to reallocate for.
 * @pages: Pointer to struct page array for tdx_page_array populating
 * @nr_pages: Size of @pages array.
 * 
 * Re-populate the tdx_page_array. If @array is %NULL, it behaves exactly like
 * tdx_page_array_create().
 *
 * Return: Re-populated tdx_page_array or NULL on failure.
 */
static struct tdx_page_array *
tdx_page_array_repopulate(struct tdx_page_array *array, struct page **pages,
			  unsigned int nr_pages)
{
	struct tdx_page_array *tmp = array;
	int ret;

	if (tmp) {
		/* Don't pass in something partially initialized */
		if (!tmp->root || !tmp->pages || !tmp->nr_pages)
			return NULL;

		/*
		 * When re-populating, the old pages are no longer tracked.
		 * Theoretically they require cache flushing before reclaiming
		 * for other kernel usage, similar to tdx_page_array_destroy().
		 * Since there is no use case to repopulate and then reclaim
		 * old pages yet, just warn to prompt future improvement.
		 */
		if (WARN_ON_ONCE(tmp->need_phymem_page_wbinvd))
			return NULL;
	} else {
		tmp = tdx_page_array_alloc();
		if (!tmp)
			return NULL;
	}

	ret = tdx_page_array_populate(tmp, pages, nr_pages);
	if (ret) {
		/* Only destroy newly allocated object */
		if (!array)
			tdx_page_array_destroy(tmp);

		return NULL;
	}

	return tmp;
}

---

## [121] Xu Yilun — 2026-04-23
*Subject: Re: [PATCH v2 06/31] x86/virt/tdx: Read global metadata for TDX
 Module Extensions/Connect*

On Tue, Apr 21, 2026 at 03:19:52PM -0700, Dan Williams wrote:
> Xu Yilun wrote:
> > Add reading of the global metadata for TDX Module Extensions & TDX

Agree. But I want to reduce the scope to only about metadata reading in
this patch. So:

    TDX Module Extensions is an optional features enumerated by
    TDX_FEATURES0. But in the implementation, Linux requires that all
    features that a Module advertises must have a complete, valid set of
    metadata, and the check must succeed at core TDX initialization time.

    Check TDX_FEATURES0 before reading these metadata. If a feature is
    advertised, a failure in reading associated metadata causes the whole
    TDX initialization to fail, otherwise skip.

> 
> Otherwise, this looks ok / consistent with other metadata reading. It

---

## [122] Xu Yilun — 2026-04-23
*Subject: Re: [PATCH v2 08/31] x86/virt/tdx: Configure TDX Module with
 optional TDX Connect feature*

On Tue, Apr 21, 2026 at 06:19:59PM -0700, Dan Williams wrote:
> Xu Yilun wrote:
> > TDX Module supports optional TDX features (e.g. TDX Connect & TDX Module

I see. I think I should use 'extra' instead of 'optional' in all places.
I'll rephase the comments.

> 
> .../me notices that other comments on this patch say the same, but do

OK. I'll use your rationale.

> 
> > TDX Module updates global metadata when optional features are enabled.

Ah, it is "useful"...  :)

> An updated module would accept zero as indicating "VMM requests module
> disable all policy and mechanisms related to untrusted wall clock time".

I see. Actually the Module is about to remove the r11 RTC.

https://cdrdv2.intel.com/v1/dl/getContent/871617

I'll remove this r11.

---

## [123] Xu Yilun — 2026-04-24
*Subject: Re: [PATCH v2 10/31] x86/virt/tdx: Add extra memory to TDX Module
 for Extensions*

On Thu, Apr 23, 2026 at 12:59:55AM +0000, Huang, Kai wrote:
> On Sat, 2026-03-28 at 00:01 +0800, Xu Yilun wrote:
> > +static int tdx_ext_mem_add(struct tdx_page_array *ext_mem)

Good to me.

> 
> Btw, I think technically we can reuse the seamcall_ir_resched() you introduced

No we can't. TDH_EXT_MEM_ADD is designed to use output parameter RCX
to override/update input parameter RCX, so the caller doesn't have to
do manual parameter update on retry call. Using seamcall_ir_resched()
makes each retry use the original RCX, not the updated one.

> 
> I am wondering whether we can just use that here, or we just get rid of that

I'd like to know why some SEAMCALLs needs resume flag but others don't.
If there is chance we don't introduce too much variants for the same thing,
that's most friendly to OS. And "no resume flag" is my best preference.

For now, I can see only one SEAMCALL with resume flag in mainline,
tdh_phymem_cache_wb(). I'd rather we treat it as an exception and no
resume flag any more if possible.

Then we don't have to make all following efforts, they are complex...

> 
> Unless you have good idea to unify them all?

---

## [124] Edgecombe, Rick P — 2026-04-23
*Subject: Re: [PATCH v2 10/31] x86/virt/tdx: Add extra memory to TDX Module for
 Extensions*

On Thu, 2026-04-23 at 00:59 +0000, Huang, Kai wrote:
> Ditto here.  I don't think we should introduce any more cond_resched().
> 

I kind of like the latter option to open code more of this stuff. The stacks of
seamcall wrapper macros is already too much.

---

## [125] Huang, Kai — 2026-04-23
*Subject: Re: [PATCH v2 10/31] x86/virt/tdx: Add extra memory to TDX Module for
 Extensions*

> 
> > 

OK I wish there's a comment saying there's additional output besides error code
via RAX and we just need to feed the output as input again when retrying the
SEAMCALL.

> 
> > 

I don't know either.

> 
> For now, I can see only one SEAMCALL with resume flag in mainline,

Right, but there will be more, and setting 'resumed=1' is even different from
how tdh_phymem_cache_wb() does.

---

## [126] Huang, Kai — 2026-04-23
*Subject: Re: [PATCH v2 10/31] x86/virt/tdx: Add extra memory to TDX Module for
 Extensions*

On Thu, 2026-04-23 at 17:05 +0000, Edgecombe, Rick P wrote:
> On Thu, 2026-04-23 at 00:59 +0000, Huang, Kai wrote:
> > Ditto here.  I don't think we should introduce any more cond_resched().

Agreed.

And SEAMCALL *users* can actually come up with their own version of wrapper(s)
to do the retry.  E.g., currently seamcall_ir_resched() is only used for IOMMU
SEAMCALLs, and we can put this wrapper in the IOMMU code or coco/tdx-host.

---

## [127] Xu Yilun — 2026-04-24
*Subject: Re: [PATCH v2 10/31] x86/virt/tdx: Add extra memory to TDX Module
 for Extensions*

On Thu, Apr 23, 2026 at 10:29:31PM +0000, Huang, Kai wrote:
> On Thu, 2026-04-23 at 17:05 +0000, Edgecombe, Rick P wrote:
> > On Thu, 2026-04-23 at 00:59 +0000, Huang, Kai wrote:

After we have introduced TDX Module Extension, irq preemptable
EXT-SEAMCALLs become a common concept. It is irq preemptable so that the
secure world remembers and resumes the context, no need for host to
remind via resume lag.

Today there are 3 EXT-SEAMCALLs, TDH_SPDM_CONNECT/DISCONNECT/MNG,
irq preemption handling is a general requirement for them, and I think
it is still true for any further EXT-SEAMCALLs.

So I think a general helper for EXT-SEAMCALLs makes sense.

TDH.IOMMU.SETUP, however, is another case. It is not a EXT-SEAMCALL but
happened to follow the same irq-retry handling process. To avoid code
duplication we have:

 /*
  * seamcall_ret_ir_exec() aliases seamcall_ret_ir_resched() for
  * documentation purposes. It documents the TDX Module extension
  * seamcalls that are long running / hard-irq preemptible flows that
  * generate events. The calls using seamcall_ret_ir_resched() are long
  * running flows, that periodically yield.
  */
 #define seamcall_ret_ir_exec seamcall_ret_ir_resched

TDH.IOMMU.SETUP uses seamcall_ret_ir_resched(), and EXT-SEAMCALLs use
seamcall_ret_ir_exec().

How do you think?

---

## [128] Tian, Kevin — 2026-04-24
*Subject: RE: [PATCH v2 19/31] iommu/vt-d: Reserve the MSB domain ID bit for
 the TDX module*

> From: Xu Yilun <yilun.xu@linux.intel.com>
> Sent: Wednesday, April 22, 2026 2:01 PM

btw halving the DID space permanently on any platforms supporting
TDX connect doesn't sound a good design. It may break usages which
already uses more than 50% of the DID space but have no business
to do with TDX connect.

It makes more sense to cut it down in-fly when tdx connect is initialized.
If the higher half DIDs have been used then fail TDX connect. otherwise
adjust the max domain id.

> 
> >

I guess "more concerns" means that there are more conditions for
TDX module to look at beyond ecap_tdxc(), so it's not appropriate
for tdx-host driver to check ecap alone.

> capabilities e.g. SPDM/IDE cap...  So in patch23 I actually mean we
> don't have an enumeration SEAMCALL for trusted capability, I will

---

## [129] Tian, Kevin — 2026-04-24
*Subject: RE: [PATCH v2 22/31] iommu/vt-d: Export a helper to do function for
 each dmar_drhd_unit*

> From: Xu Yilun <yilun.xu@linux.intel.com>
> Sent: Wednesday, April 22, 2026 2:34 PM

yeah, I misread it.

---

## [130] Tian, Kevin — 2026-04-24
*Subject: RE: [PATCH v2 23/31] coco/tdx-host: Setup all trusted IOMMUs on TDX
 Connect init*

> From: Xu Yilun <yilun.xu@linux.intel.com>
> Sent: Wednesday, April 22, 2026 5:27 PM

iommu drivers also involve PCI, e.g. call pci_enable_ats(), etc.

so having relation to PCIe SPDM/IDE is not an argument of
platform vs. IOMMU.

Actually I'm OK to put that logic in tdx-host. Just the explanation
here doesn't make much sense...

---

## [131] Tian, Kevin — 2026-04-24
*Subject: RE: [PATCH v2 20/31] x86/virt/tdx: Add a helper to loop on
 TDX_INTERRUPTED_RESUMABLE*

> From: Xu Yilun <yilun.xu@linux.intel.com>
> Sent: Wednesday, April 22, 2026 2:05 PM

that's ok

---

## [132] Tian, Kevin — 2026-04-24
*Subject: RE: [PATCH v2 24/31] coco/tdx-host: Add a helper to exchange SPDM
 messages through DOE*

> From: Xu Yilun <yilun.xu@linux.intel.com>
> Sent: Wednesday, April 22, 2026 5:41 PM

pci_spdm_raw_msg_exchange() then, since you said currently only
one user i.e. tdx?

If the kernel managed spdm doesn't support the raw format, then there
won't be conflict.

if it supports (i.e. the 2nd user), then this should be moved to pci core.

> 
> And we also don't name it tsm_spdm_msg_exchange, cause TSM firmwares

TDX is just an user of that. All the logic here is about handling the
raw format, nothing specific to tdx.

---

## [133] Tian, Kevin — 2026-04-24
*Subject: RE: [PATCH v2 30/31] coco/tdx-host: Implement IDE stream
 setup/teardown*

> From: Xu Yilun <yilun.xu@linux.intel.com>
> Sent: Wednesday, April 22, 2026 5:58 PM

a typo.

> 
> Actually it is " *most* straightforward", I just mean "very".

When you say "most straightforward", then I want to know what are
other options to compare. If you think that the thought practice
leading to the 'most' definition is important, then please elaborate.

otherwise I'd just remove that sentence.

---

## [134] Huang, Kai — 2026-04-24
*Subject: Re: [PATCH v2 10/31] x86/virt/tdx: Add extra memory to TDX Module for
 Extensions*

On Fri, 2026-04-24 at 11:07 +0800, Xu Yilun wrote:
> On Thu, Apr 23, 2026 at 10:29:31PM +0000, Huang, Kai wrote:
> > On Thu, 2026-04-23 at 17:05 +0000, Edgecombe, Rick P wrote:

It has been a concept since before the EXT-SEAMCALLs actually.  For instance,
TDX live migration using blocking export doesn't need any opt-in via module
extension (only the non-blocking way needs), but the SEAMCALLs to export/import
TD/vCPU/memory are all interruptible.

In fact, they had the "latency requirement" behind the INTERRUPT_RESUMABLE in
mind at the very beginning.  It's just at that point all SEAMCALLs were not that
heavy.

> It is irq preemptable so that the
> secure world remembers and resumes the context, no need for host to

The fact is the aforementioned live migration related export/import SEAMCALLs 
(there are 8 at least, but maybe more) all requires the explicit setting of
'resume=1' (plus using the SEAMCALL output as input for retry).  I don't know
the story behind this, though.  There might be some tricky thing here for the
module to remember and manage (e.g., migration has a concept of "migration
stream", and the resume is per-stream).

> 
> Today there are 3 EXT-SEAMCALLs, TDH_SPDM_CONNECT/DISCONNECT/MNG,

Yes conceptually I agree, but not need to distinguish EXT-SEAMCALLs or not IMHO.

The problem is there isn't a common rule to follow.

E.g., let's say "the module can remember thus no resume flag is needed", how
about the SEAMCALL inputs?  Can the "output" args be directly used as input for
retry, or the original input should always be used?

Not to mention there's existing SEAMCALLs which require explicitly setting
'resume=1'.

I believe we can use some smart hack to implement a common one to cover all
cases above, but I am not sure whether it's worth to do (maybe we can have a try
to see how does it look like, though, I think).

Given the SEAMCALLs for TDX Connect seem to follow one rule to retry, and live
migration SEAMCALLs follow another rule, it seems for now the simplest way is to
introduce the needed retry helper in the layer of SEAMCALL *user* (TDX Connect
and migration).

> TDH.IOMMU.SETUP, however, is another case. It is not a EXT-SEAMCALL but
> happened to follow the same irq-retry handling process. To avoid code

Sorry I don't quite get.  What does "exec" postfix mean?

From patch 25, they are all in TDX core, so I don't quite get why we need to
distinguish EXT-SEAMCALLs vs normal ones.  IMHO it's an additional layer which
doesn't actually help address any problem.

Btw, we should really get rid of the "resched()" postfix from the function name
since cond_resched() is no longer needed and possibility of rescheduling is
implied pretty much all places in the kernel code now (except some special code
such as code in IRQ context).

---

## [135] Huang, Kai — 2026-04-24
*Subject: Re: [PATCH v2 10/31] x86/virt/tdx: Add extra memory to TDX Module for
 Extensions*

On Fri, 2026-04-24 at 08:09 +0000, Huang, Kai wrote:
> I believe we can use some smart hack to implement a common one to cover all
> cases above, but I am not sure whether it's worth to do (maybe we can have a try

So the problem is use what as input when retry, and one way is to provide a
callback to allow the user to provide a specific function to update the 'args'
before retrying.

Something like below?  I am not sure I like it though, because as Rick said
there's too much SEAMCALL wrapper/macros already.

typedef void (*args_update_func_t)(struct tdx_module_args *args,
                                   struct tdx_module_args *ori);

static __always_inline u64 sc_retry_intr(sc_func_t func, u64 fn,
                                         struct tdx_module_args *args,
                                         args_update_func_t update_args)
{
        struct tdx_module_args _args = *args;
        u64 ret;

        do {
                ret = sc_retry(func, fn, &_args);

                if (ret != TDX_INTERRUPT_RESUMABLE)
                        break;
        
                update_args(&_args, args);
        } while (1);
        
        *args = _args;

        return ret;
}                                        

#define seamcall_ret_intr(_fn, _args, _args_update_f)   \
        sc_retry_intr(__seamcall_ret, (_fn), (_args), (_args_update_f))

---

## [136] Xu Yilun — 2026-04-24
*Subject: Re: [PATCH v2 10/31] x86/virt/tdx: Add extra memory to TDX Module
 for Extensions*

On Fri, Apr 24, 2026 at 08:09:16AM +0000, Huang, Kai wrote:
> On Fri, 2026-04-24 at 11:07 +0800, Xu Yilun wrote:
> > On Thu, Apr 23, 2026 at 10:29:31PM +0000, Huang, Kai wrote:

No, they look similar but different. EXT-SEAMCALLs are truly irq
preemptable and resumable to its context. Other SEAMCALLs just
periodically yield and don't have a generic way to save/resume their
context. Sometime you need to pass in resume flag on 2nd time, which
means the secure world forget where they were and can't really resume
all by itself.

What I mean is, EXT-SEAMCALLs should never need to play tricks on
input parameters. Just input what is originally inputted, the secure
world doesn't need hint to resume itself. So the int-retry process
should be common.

> TDX live migration using blocking export doesn't need any opt-in via module
> extension (only the non-blocking way needs), but the SEAMCALLs to export/import

Yes, so they are not truly interrupt resumable and should be specially
treated.

> the story behind this, though.  There might be some tricky thing here for the
> module to remember and manage (e.g., migration has a concept of "migration

Since EXT-SEAMCALLs don't depend on input tricks to resume, there could
be a common rule, now it is defined as "the original input should always
be used".

> 
> Not to mention there's existing SEAMCALLs which require explicitly setting

It is 'execution', means EXT-SEAMCALLs can resume their execution. But
since you have concern, maybe some better name?

> 
> From patch 25, they are all in TDX core, so I don't quite get why we need to

EXT-SEAMCALLs have generic way to resume, while others don't. So we need
a helper for EXT-SEAMCALLs. For other SEAMCALLs that happens to process
the same way, we are avoiding code duplication, but should clearly
distinguish the purpose so make another name as documentation.

But if any concern, we could delete the int-retry support for normal
SEAMCALLs, they are not generic as you said.

> doesn't actually help address any problem.
> 

Yes, thanks to remind me again.

---

## [137] Xu Yilun — 2026-04-27
*Subject: Re: [PATCH v2 19/31] iommu/vt-d: Reserve the MSB domain ID bit for
 the TDX module*

> > > btw in patch23 commit msg:
> > >

Exactly. 

> 
> > capabilities e.g. SPDM/IDE cap...  So in patch23 I actually mean we

---

## [138] Xu Yilun — 2026-04-27
*Subject: Re: [PATCH v2 23/31] coco/tdx-host: Setup all trusted IOMMUs on TDX
 Connect init*

On Fri, Apr 24, 2026 at 06:54:54AM +0000, Tian, Kevin wrote:
> > From: Xu Yilun <yilun.xu@linux.intel.com>
> > Sent: Wednesday, April 22, 2026 5:27 PM

OK, I think I could delete the platform vs. IOMMU thing in commit log.

> 
> Actually I'm OK to put that logic in tdx-host. Just the explanation

---

## [139] Xu Yilun — 2026-04-27
*Subject: Re: [PATCH v2 24/31] coco/tdx-host: Add a helper to exchange SPDM
 messages through DOE*

On Fri, Apr 24, 2026 at 07:01:32AM +0000, Tian, Kevin wrote:
> > From: Xu Yilun <yilun.xu@linux.intel.com>
> > Sent: Wednesday, April 22, 2026 5:41 PM

I think kernel managed spdm APIs should not support the raw format (with
DOE header). SPDM protocol could be run on various transit so make no
sense to have special care for DOE.

So this "raw_msg_exchange" is dedicated for PCI/TSM. Yes there won't be
conflict, but it's important "pci_spdm_" prefix only serve kernel
managed spdm. PCI_TSM managed SPDM has fundamental logical differences
with the kernel managed one.

> 
> if it supports (i.e. the 2nd user), then this should be moved to pci core.

It is special, kernel managed spdm won't expect an all-in-one format,
other vendors either. It is TDX's decision to output this all-in-one
format for OS to transfer.

---

## [140] Xu Yilun — 2026-04-27
*Subject: Re: [PATCH v2 30/31] coco/tdx-host: Implement IDE stream
 setup/teardown*

On Fri, Apr 24, 2026 at 07:05:32AM +0000, Tian, Kevin wrote:
> > From: Xu Yilun <yilun.xu@linux.intel.com>
> > Sent: Wednesday, April 22, 2026 5:58 PM

OK, I think the use of "a most" is somewhat misleading. I don't want to
emphasize on comparison.  I just want to give a summary about the
implementation: hard code all parameters, give no option for
configurations, no optional features supported e.g. KEY Refresh.

So is it better I just s/most/very:

 Implementation for a very straightforward Selective IDE stream setup...

> leading to the 'most' definition is important, then please elaborate.
>

---
