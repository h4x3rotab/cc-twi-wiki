---
title: 'Fuller TDX kexec support'
date: 2026-03-23
last_reply: 2026-04-01
message_count: 33
participants: ['Vishal Verma', 'Huang, Kai', 'Chao Gao', 'Kiryl Shutsemau', 'Edgecombe, Rick P', 'Sean Christopherson', 'Dave Hansen', 'H. Peter Anvin']
---

## [1] Vishal Verma — 2026-03-23

Hi,

This series adds a couple of cool things -
 1. Allow kexec and kdump on systems with the partial write errata
 2. Allow using TDX in the second (kexec'ed) kernel

It has been waiting for VMXON refactor to land because the implementation
is much cleaner on top of that.

KVM folks, just a few deletions on your side and the long discussed moving
of tdx_errno.h. Tip folks and reviewers, the changes here are pretty small.
Optimistically, I'm hoping we can iterate this quickly and see it off the
list in the next few weeks.

Background
==========
Some early TDX-capable platforms have an erratum where a partial write
to TDX private memory can cause a machine check on a subsequent read.
Currently, kexec and kdump are disabled on these platforms because the
new (or kdump) kernel may trip over these, causing a machine check.

Future TDX modules will support TDH.SYS.DISABLE SEAMCALL, which disables
the TDX module and reclaims all memory resources allocated to TDX, and
cleans up any poison. After this SEAMCALL succeeds, the new kernel
can also re-initialize the TDX module from scratch via the normal bring-up
sequence.

It is probably worth mentioning that this is a different kind of cleanup
than the WBINVD stuff that was the cause of all the fuss in the earlier
kexec enabling. The WBINVD is flushing private keyid cachelines so they
are not later written back over the new kernels memory. It needs to happen
after the last SEAMCALL that might have produced them. So this new
SEAMCALL is for something else, but also needs to be slotted with respect
to WBINVD.

Implementation
==============
The series adds:

 1. A pre-requisite patch to move TDX error code definitions to a
    shared location so that TDX_INTERRUPTED_RESUMABLE etc. are
    accessible from arch/x86/virt/vmx/tdx/. This comes from the Dynamic
    PAMT series [0], but is also needed by some other series, and can
    benefit them all from an early merge.

 2. A preparatory patch to move some straggling stuff into arch/x86 in the
    wake of the VMXON series.

 3. A tdx_sys_disable() helper that wraps calls TDH.SYS.DISABLE with a
    retry loop to handle TDX_INTERRUPTED_RESUMABLE.

 4. Integration into the kexec path: Remove the check for partial write
    errata platforms as this is addressed by the SEAMCALL clearing any
    poisoned memory locations. Call tdx_sys_disable() in tdx_shutdown
    which is called via syscore ops in the kexec path. Call
    tdx_sys_disable() in native_machine_crash_shutdown() to cover the
    crash (kdump) path.

 5. A patch to update (remove) the kexec section in TDX docs.

Testing
=======
The implementation is based on the draft TDX module spec available at
[1], and was smoke tested with an engineering build of the TDX module
that supports the new SEAMCALL. The new kernel was able to initialize
the TDX module successfully:

  kvm: exiting hardware virtualization
  kexec_core: Starting new kernel
  Linux version 7.0.0-rc2-g0077f702b21c...
  ...
  virt/tdx: 1034220 KB allocated for PAMT
  virt/tdx: TDX-Module initialized

All the other TDX CI tests pass, and some other scenarios that were
manually tested and also pass or behave as expected:
 - Running on a completely non-TDX system
 - Running on a TDX capable system with an old module
 - Running on a TDX capable system where the module hasn't been
   initialized

During development further testing was done by mocking up the new
SEAMCALL to introduce delays and exercise the retry loops, combined with
kexec, kdump, reboot and shutdown flows.

Base
====
This series is based on the vmxon branch Sean pushed to kvm_x86,
kvm-x86-vmxon-2026.03.05.

[0]: https://lore.kernel.org/kvm/20260129011517.3545883-11-seanjc@google.com/
[1]: https://cdrdv2.intel.com/v1/dl/getContent/871617

---
Changes in v2:
- Use patch 1 from the DPAMT series with other feedback (Kai)
- Fix commit message typo (s/adjust_/adjust /)
- In patch 2, drop "too late to be helpful" in favor of something more
  explicit (Kai)
- Fix commit message typo in patch 2 (s/both/bother/)
- In patch 2, add a bit about dropping the TDX specific WBINVD (Kai)
- Reword some commit logs to use the imperative mood (Chao)
- Kai raised offline that TDH.SYS.DISABLE can return TDX_SYS_BUSY too.
  In theory this could happen if another SEAMCALL happens concurrently,
  however that contention should be short lived. Update the loop to
  continue on a TDX_SYS_BUSY error code too. (Kai)
- Patch 3: Add a print for SEAMCALL errors reported by the TDX module
  (excluding SW errors like #UD and #GP) (Kiryl)
- Patch 3: Add a sentence to the log about skipping enumeration for the
  new SEAMCALL (Kiryl)
- Adjust the patch 4 subject (Chao)
- Add a new patch to update the docs (Chao)
- Smoke test with TDX module engineering build with the new SEAMCALL.

Kiryl Shutsemau (1):
      x86/tdx: Move all TDX error defines into <asm/shared/tdx_errno.h>

Rick Edgecombe (2):
      x86/virt/tdx: Pull kexec cache flush logic into arch/x86
      x86/virt/tdx: Remove kexec docs

Vishal Verma (2):
      x86/virt/tdx: Add SEAMCALL wrapper for TDH.SYS.DISABLE
      x86/tdx: Disable the TDX module during kexec and kdump

 Documentation/arch/x86/tdx.rst                       |  7 -------
 arch/x86/include/asm/shared/tdx.h                    |  1 +
 arch/x86/{kvm/vmx => include/asm/shared}/tdx_errno.h | 29 +++++++++++++++++++++++------
 arch/x86/include/asm/tdx.h                           | 30 +++---------------------------
 arch/x86/kvm/vmx/tdx.h                               |  1 -
 arch/x86/virt/vmx/tdx/tdx.h                          |  1 +
 arch/x86/kernel/crash.c                              |  2 ++
 arch/x86/kernel/machine_kexec_64.c                   | 16 ----------------
 arch/x86/kvm/vmx/tdx.c                               | 10 ----------
 arch/x86/virt/vmx/tdx/tdx.c                          | 54 ++++++++++++++++++++++++++++++++++++++++++------------
 10 files changed, 72 insertions(+), 79 deletions(-)

--
2.53.0

---
Kiryl Shutsemau (1):
      x86/tdx: Move all TDX error defines into <asm/shared/tdx_errno.h>

Rick Edgecombe (2):
      x86/virt/tdx: Pull kexec cache flush logic into arch/x86
      x86/virt/tdx: Remove kexec docs

Vishal Verma (2):
      x86/virt/tdx: Add SEAMCALL wrapper for TDH.SYS.DISABLE
      x86/tdx: Disable the TDX module during kexec and kdump

 Documentation/arch/x86/tdx.rst                     |  7 ---
 arch/x86/include/asm/shared/tdx.h                  |  1 +
 .../{kvm/vmx => include/asm/shared}/tdx_errno.h    | 29 +++++++++---
 arch/x86/include/asm/tdx.h                         | 30 ++----------
 arch/x86/kvm/vmx/tdx.h                             |  1 -
 arch/x86/virt/vmx/tdx/tdx.h                        |  1 +
 arch/x86/kernel/crash.c                            |  2 +
 arch/x86/kernel/machine_kexec_64.c                 | 16 -------
 arch/x86/kvm/vmx/tdx.c                             | 10 ----
 arch/x86/virt/vmx/tdx/tdx.c                        | 54 +++++++++++++++++-----
 10 files changed, 72 insertions(+), 79 deletions(-)
---
base-commit: f630de1f8d70d7e29e12bc25dc63f9c5f771dc59
change-id: 20260317-fuller_tdx_kexec_support-bc79694678be

Best regards,
--  
Vishal Verma <vishal.l.verma@intel.com>

---

## [2] Vishal Verma — 2026-03-23
*Subject: [PATCH v2 1/5] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

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
---
 arch/x86/include/asm/shared/tdx.h                  |  1 +
 .../{kvm/vmx => include/asm/shared}/tdx_errno.h    | 28 +++++++++++++++++-----
 arch/x86/include/asm/tdx.h                         | 21 ----------------
 arch/x86/kvm/vmx/tdx.h                             |  1 -
 4 files changed, 23 insertions(+), 28 deletions(-)

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
index a149740b24e8..2917b3451491 100644
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
index b5cd2ffb303e..ac8323a68b16 100644
--- a/arch/x86/kvm/vmx/tdx.h
+++ b/arch/x86/kvm/vmx/tdx.h
@@ -3,7 +3,6 @@
 #define __KVM_X86_VMX_TDX_H
 
 #include "tdx_arch.h"
-#include "tdx_errno.h"
 
 #ifdef CONFIG_KVM_INTEL_TDX
 #include "common.h"

---

## [3] Vishal Verma — 2026-03-23
*Subject: [PATCH v2 2/5] x86/virt/tdx: Pull kexec cache flush logic into
 arch/x86*

From: Rick Edgecombe <rick.p.edgecombe@intel.com>

KVM tries to take care of some required cache flushing earlier in the
kexec path in order to be kind to some long standing races that can occur
later in the operation. Until recently, VMXOFF was handled within KVM.
Since VMX being enabled is required to make a SEAMCALL, it had the best
per-cpu scoped operation to plug the flushing into. So it is kicked off
from there.

This early kexec cache flushing in KVM happens via a syscore shutdown
callback. Now that VMX enablement control has moved to arch/x86, which has
grown its own syscore shutdown callback, it no longer make sense for it to
live in KVM. It fits better with the TDX enablement managing code.

In addition, future changes will add a SEAMCALL that happens immediately
before VMXOFF, which means the cache flush in KVM will be too late to
flush the cache before the last SEAMCALL. So move it to the newly added TDX
arch/x86 syscore shutdown handler.

Since tdx_cpu_flush_cache_for_kexec() is no longer needed by KVM, make it
static and remove the export. Since it is also not part of an operation
spread across disparate components, remove the redundant comments and
verbose naming.

In the existing KVM based code, CPU offline also funnels through
tdx_cpu_flush_cache_for_kexec(). So the centralization to the arch/x86
syscore shutdown callback elides this CPU offline time behavior. However,
WBINVD is already generally done at CPU offline as matter of course. So
don't bother adding TDX specific logic for this, and rely on the normal
WBINVD to handle it.

Acked-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Vishal Verma <vishal.l.verma@intel.com>
---
 arch/x86/include/asm/tdx.h  |  6 ------
 arch/x86/kvm/vmx/tdx.c      | 10 ----------
 arch/x86/virt/vmx/tdx/tdx.c | 39 ++++++++++++++++++++-------------------
 3 files changed, 20 insertions(+), 35 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 2917b3451491..7674fc530090 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -205,11 +205,5 @@ static inline const char *tdx_dump_mce_info(struct mce *m) { return NULL; }
 static inline const struct tdx_sys_info *tdx_get_sysinfo(void) { return NULL; }
 #endif	/* CONFIG_INTEL_TDX_HOST */
 
-#ifdef CONFIG_KEXEC_CORE
-void tdx_cpu_flush_cache_for_kexec(void);
-#else
-static inline void tdx_cpu_flush_cache_for_kexec(void) { }
-#endif
-
 #endif /* !__ASSEMBLER__ */
 #endif /* _ASM_X86_TDX_H */
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index b7264b533feb..50a5cfdbd33e 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -440,16 +440,6 @@ void tdx_disable_virtualization_cpu(void)
 		tdx_flush_vp(&arg);
 	}
 	local_irq_restore(flags);
-
-	/*
-	 * Flush cache now if kexec is possible: this is necessary to avoid
-	 * having dirty private memory cachelines when the new kernel boots,
-	 * but WBINVD is a relatively expensive operation and doing it during
-	 * kexec can exacerbate races in native_stop_other_cpus().  Do it
-	 * now, since this is a safe moment and there is going to be no more
-	 * TDX activity on this CPU from this point on.
-	 */
-	tdx_cpu_flush_cache_for_kexec();
 }
 
 #define TDX_SEAMCALL_RETRIES 10000
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index cb9b3210ab71..0802d0fd18a4 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -224,8 +224,28 @@ static int tdx_offline_cpu(unsigned int cpu)
 	return 0;
 }
 
+static void tdx_cpu_flush_cache(void)
+{
+	lockdep_assert_preemption_disabled();
+
+	if (!this_cpu_read(cache_state_incoherent))
+		return;
+
+	wbinvd();
+	this_cpu_write(cache_state_incoherent, false);
+}
+
 static void tdx_shutdown_cpu(void *ign)
 {
+	/*
+	 * Flush cache now if kexec is possible: this is necessary to avoid
+	 * having dirty private memory cachelines when the new kernel boots,
+	 * but WBINVD is a relatively expensive operation and doing it during
+	 * kexec can exacerbate races in native_stop_other_cpus().  Do it
+	 * now, since this is a safe moment and there is going to be no more
+	 * TDX activity on this CPU from this point on.
+	 */
+	tdx_cpu_flush_cache();
 	x86_virt_put_ref(X86_FEATURE_VMX);
 }
 
@@ -1920,22 +1940,3 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
 	return seamcall(TDH_PHYMEM_PAGE_WBINVD, &args);
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_phymem_page_wbinvd_hkid);
-
-#ifdef CONFIG_KEXEC_CORE
-void tdx_cpu_flush_cache_for_kexec(void)
-{
-	lockdep_assert_preemption_disabled();
-
-	if (!this_cpu_read(cache_state_incoherent))
-		return;
-
-	/*
-	 * Private memory cachelines need to be clean at the time of
-	 * kexec.  Write them back now, as the caller promises that
-	 * there should be no more SEAMCALLs on this CPU.
-	 */
-	wbinvd();
-	this_cpu_write(cache_state_incoherent, false);
-}
-EXPORT_SYMBOL_FOR_KVM(tdx_cpu_flush_cache_for_kexec);
-#endif

---

## [4] Vishal Verma — 2026-03-23
*Subject: [PATCH v2 3/5] x86/virt/tdx: Add SEAMCALL wrapper for
 TDH.SYS.DISABLE*

Some early TDX-capable platforms have an erratum where a partial write
to TDX private memory can cause a machine check on a subsequent read.
On these platforms, kexec and kdump have been disabled in these cases,
because the old kernel cannot safely hand off TDX state to the new
kernel. Later TDX modules support the TDH.SYS.DISABLE SEAMCALL, which
provides a way to cleanly disable TDX and allow kexec to proceed.

The new SEAMCALL has an enumeration bit, but that is ignored. It is
expected that users will be using the latest TDX module, and the failure
mode for running the missing SEAMCALL on an older module is not fatal.

This can be a long running operation, and the time needed largely
depends on the amount of memory that has been allocated to TDs. If all
TDs have been destroyed prior to the sys_disable call, then it is fast,
with only needing to override the TDX module memory.

After the SEAMCALL completes, the TDX module is disabled and all memory
resources allocated to TDX are freed and reset. The next kernel can then
re-initialize the TDX module from scratch via the normal TDX bring-up
sequence.

The SEAMCALL can return two different error codes that expect a retry.
 - TDX_INTERRUPTED_RESUMABLE can be returned in the case of a host
   interrupt. However, it will not return until it makes some forward
   progress, so we can expect to complete even in the case of interrupt
   storms.
 - TDX_SYS_BUSY will be returned on contention with other TDH.SYS.*
   SEAMCALLs, however a side effect of TDH.SYS.DISABLE is that it will
   block other SEAMCALLs once it gets going. So this contention will be
   short lived.

So loop infinitely on either of these error codes, until success or other
error.

Co-developed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Vishal Verma <vishal.l.verma@intel.com>
---
 arch/x86/include/asm/shared/tdx_errno.h |  1 +
 arch/x86/include/asm/tdx.h              |  3 +++
 arch/x86/virt/vmx/tdx/tdx.h             |  1 +
 arch/x86/virt/vmx/tdx/tdx.c             | 28 ++++++++++++++++++++++++++++
 4 files changed, 33 insertions(+)

diff --git a/arch/x86/include/asm/shared/tdx_errno.h b/arch/x86/include/asm/shared/tdx_errno.h
index 8bf6765cf082..246b4fd54a48 100644
--- a/arch/x86/include/asm/shared/tdx_errno.h
+++ b/arch/x86/include/asm/shared/tdx_errno.h
@@ -15,6 +15,7 @@
 #define TDX_NON_RECOVERABLE_TD_NON_ACCESSIBLE	0x6000000500000000ULL
 #define TDX_NON_RECOVERABLE_TD_WRONG_APIC_MODE	0x6000000700000000ULL
 #define TDX_INTERRUPTED_RESUMABLE		0x8000000300000000ULL
+#define TDX_SYS_BUSY				0x8000020200000000ULL
 #define TDX_OPERAND_INVALID			0xC000010000000000ULL
 #define TDX_OPERAND_BUSY			0x8000020000000000ULL
 #define TDX_PREVIOUS_TLB_EPOCH_BUSY		0x8000020100000000ULL
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 7674fc530090..a0a4a15142fc 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -172,6 +172,8 @@ static inline int pg_level_to_tdx_sept_level(enum pg_level level)
         return level - 1;
 }
 
+void tdx_sys_disable(void);
+
 u64 tdh_vp_enter(struct tdx_vp *vp, struct tdx_module_args *args);
 u64 tdh_mng_addcx(struct tdx_td *td, struct page *tdcs_page);
 u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, struct page *page, struct page *source, u64 *ext_err1, u64 *ext_err2);
@@ -203,6 +205,7 @@ static inline void tdx_init(void) { }
 static inline u32 tdx_get_nr_guest_keyids(void) { return 0; }
 static inline const char *tdx_dump_mce_info(struct mce *m) { return NULL; }
 static inline const struct tdx_sys_info *tdx_get_sysinfo(void) { return NULL; }
+static inline void tdx_sys_disable(void) { }
 #endif	/* CONFIG_INTEL_TDX_HOST */
 
 #endif /* !__ASSEMBLER__ */
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index dde219c823b4..e2cf2dd48755 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -46,6 +46,7 @@
 #define TDH_PHYMEM_PAGE_WBINVD		41
 #define TDH_VP_WR			43
 #define TDH_SYS_CONFIG			45
+#define TDH_SYS_DISABLE			69
 
 /*
  * SEAMCALL leaf:
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 0802d0fd18a4..3a76000dec7a 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -37,6 +37,7 @@
 #include <asm/msr.h>
 #include <asm/cpufeature.h>
 #include <asm/tdx.h>
+#include <asm/shared/tdx_errno.h>
 #include <asm/cpu_device_id.h>
 #include <asm/processor.h>
 #include <asm/mce.h>
@@ -1940,3 +1941,30 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
 	return seamcall(TDH_PHYMEM_PAGE_WBINVD, &args);
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_phymem_page_wbinvd_hkid);
+
+void tdx_sys_disable(void)
+{
+	struct tdx_module_args args = {};
+	u64 ret;
+
+	/*
+	 * Don't loop forever.
+	 *  - TDX_INTERRUPTED_RESUMABLE guarantees forward progress between
+	 *    calls.
+	 *  - TDX_SYS_BUSY could transiently contend with TDH.SYS.* SEAMCALLs,
+	 *    but will lock out future ones.
+	 *
+	 * This is a 'destructive' SEAMCALL, in that no other SEAMCALL can be
+	 * run after this until a full reinitialization is done.
+	 */
+	do {
+		ret = seamcall(TDH_SYS_DISABLE, &args);
+	} while (ret == TDX_INTERRUPTED_RESUMABLE || ret == TDX_SYS_BUSY);
+
+	/*
+	 * Print SEAMCALL failures, but not SW-defined error codes
+	 * (SEAMCALL faulted with #GP/#UD, TDX not supported).
+	 */
+	if (ret && (ret & TDX_SW_ERROR) != TDX_SW_ERROR)
+		pr_err("TDH.SYS.DISABLE failed: 0x%016llx\n", ret);
+}

---

## [5] Vishal Verma — 2026-03-23
*Subject: [PATCH v2 4/5] x86/tdx: Disable the TDX module during kexec and
 kdump*

Use the TDH.SYS.DISABLE SEAMCALL, which disables the TDX module,
reclaims all memory resources assigned to TDX, and clears any
partial-write induced poison, to allow kexec and kdump on platforms with
the partial write errata.

On TDX-capable platforms with the partial write erratum, kexec has been
disabled because the new kernel could hit a machine check reading a
previously poisoned memory location.

Later TDX modules support TDH.SYS.DISABLE, which disables the module and
reclaims all TDX memory resources, allowing the new kernel to re-initialize
TDX from scratch. This operation also clears the old memory, cleaning up
any poison.

Add tdx_sys_disable() to tdx_shutdown(), which is called in the
syscore_shutdown path for kexec. This is done just before tdx_shutdown()
disables VMX on all CPUs.

For kdump, call tdx_sys_disable() in the crash path before
x86_virt_emergency_disable_virtualization_cpu() does VMXOFF.

Since this clears any poison on TDX-managed memory, remove the
X86_BUG_TDX_PW_MCE check in machine_kexec() that blocked kexec on
partial write errata platforms.

Co-developed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Vishal Verma <vishal.l.verma@intel.com>
---
 arch/x86/kernel/crash.c            |  2 ++
 arch/x86/kernel/machine_kexec_64.c | 16 ----------------
 arch/x86/virt/vmx/tdx/tdx.c        |  1 +
 3 files changed, 3 insertions(+), 16 deletions(-)

diff --git a/arch/x86/kernel/crash.c b/arch/x86/kernel/crash.c
index cd796818d94d..623d4474631a 100644
--- a/arch/x86/kernel/crash.c
+++ b/arch/x86/kernel/crash.c
@@ -38,6 +38,7 @@
 #include <linux/kdebug.h>
 #include <asm/cpu.h>
 #include <asm/reboot.h>
+#include <asm/tdx.h>
 #include <asm/intel_pt.h>
 #include <asm/crash.h>
 #include <asm/cmdline.h>
@@ -112,6 +113,7 @@ void native_machine_crash_shutdown(struct pt_regs *regs)
 
 	crash_smp_send_stop();
 
+	tdx_sys_disable();
 	x86_virt_emergency_disable_virtualization_cpu();
 
 	/*
diff --git a/arch/x86/kernel/machine_kexec_64.c b/arch/x86/kernel/machine_kexec_64.c
index 0590d399d4f1..c3f4a389992d 100644
--- a/arch/x86/kernel/machine_kexec_64.c
+++ b/arch/x86/kernel/machine_kexec_64.c
@@ -347,22 +347,6 @@ int machine_kexec_prepare(struct kimage *image)
 	unsigned long reloc_end = (unsigned long)__relocate_kernel_end;
 	int result;
 
-	/*
-	 * Some early TDX-capable platforms have an erratum.  A kernel
-	 * partial write (a write transaction of less than cacheline
-	 * lands at memory controller) to TDX private memory poisons that
-	 * memory, and a subsequent read triggers a machine check.
-	 *
-	 * On those platforms the old kernel must reset TDX private
-	 * memory before jumping to the new kernel otherwise the new
-	 * kernel may see unexpected machine check.  For simplicity
-	 * just fail kexec/kdump on those platforms.
-	 */
-	if (boot_cpu_has_bug(X86_BUG_TDX_PW_MCE)) {
-		pr_info_once("Not allowed on platform with tdx_pw_mce bug\n");
-		return -EOPNOTSUPP;
-	}
-
 	/* Setup the identity mapped 64bit page table */
 	result = init_pgtable(image, __pa(control_page));
 	if (result)
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 3a76000dec7a..aaf22a87717a 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -252,6 +252,7 @@ static void tdx_shutdown_cpu(void *ign)
 
 static void tdx_shutdown(void *ign)
 {
+	tdx_sys_disable();
 	on_each_cpu(tdx_shutdown_cpu, NULL, 1);
 }

---

## [6] Vishal Verma — 2026-03-23
*Subject: [PATCH v2 5/5] x86/virt/tdx: Remove kexec docs*

From: Rick Edgecombe <rick.p.edgecombe@intel.com>

Recent changes have removed the hard limitations for using kexec and
TDX together. So remove the section in the TDX docs.

Users on partial write erratums will need an updated TDX module to
handle the rare edge cases. The docs do not currently provide any
guidance on recommended TDX module versions, so don't keep a whole
section around to document this interaction.

Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Vishal Verma <vishal.l.verma@intel.com>
---
 Documentation/arch/x86/tdx.rst | 7 -------
 1 file changed, 7 deletions(-)

diff --git a/Documentation/arch/x86/tdx.rst b/Documentation/arch/x86/tdx.rst
index ff6b110291bc..1a3b5bac1021 100644
--- a/Documentation/arch/x86/tdx.rst
+++ b/Documentation/arch/x86/tdx.rst
@@ -138,13 +138,6 @@ If the platform has such erratum, the kernel prints additional message in
 machine check handler to tell user the machine check may be caused by
 kernel bug on TDX private memory.
 
-Kexec
-~~~~~~~
-
-Currently kexec doesn't work on the TDX platforms with the aforementioned
-erratum.  It fails when loading the kexec kernel image.  Otherwise it
-works normally.
-
 Interaction vs S3 and deeper states
 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

---

## [7] Verma, Vishal L — 2026-03-23
*Subject: Re: [PATCH v2 3/5] x86/virt/tdx: Add SEAMCALL wrapper for
 TDH.SYS.DISABLE*

On Mon, 2026-03-23 at 14:59 -0600, Vishal Verma wrote:
> 
[..]
> +void tdx_sys_disable(void)
> +{

Note - old TDX modules that don't implement this SEAMCALL produce a
message like:

  virt/tdx: TDH.SYS.DISABLE failed: 0xc000010000000000

Where that code translates to TDX_OPERAND_INVALID.
This also serves as a nudge that the module should be updated.

It might be worth including a blurb about this in the commit message -
something like below. This could be included when applying, or I can
send an updated version with this if it is acceptable.

---

An error is printed if the SEAMCALL fails with anything other than the
error codes that cause retries, or 'synthesized' error codes produced
for #GP or #UD. e.g., an old module that has been properly initialized,
that doesn't implement SYS_DISABLE, returns TDX_OPERAND_INVALID. This
prints:

  virt/tdx: TDH.SYS.DISABLE failed: 0xc000010000000000

But a system that doesn't have any TDX support at all doesn't print
anything.

---

## [8] Huang, Kai — 2026-03-23
*Subject: Re: [PATCH v2 3/5] x86/virt/tdx: Add SEAMCALL wrapper for
 TDH.SYS.DISABLE*

On Mon, 2026-03-23 at 14:59 -0600, Vishal Verma wrote:
> Some early TDX-capable platforms have an erratum where a partial write
> to TDX private memory can cause a machine check on a subsequent read.

Acked-by: Kai Huang <kai.huang@intel.com>

---

## [9] Huang, Kai — 2026-03-23
*Subject: Re: [PATCH v2 4/5] x86/tdx: Disable the TDX module during kexec and
 kdump*

On Mon, 2026-03-23 at 14:59 -0600, Vishal Verma wrote:
> Use the TDH.SYS.DISABLE SEAMCALL, which disables the TDX module,
> reclaims all memory resources assigned to TDX, and clears any

Acked-by: Kai Huang <kai.huang@intel.com>

---

## [10] Huang, Kai — 2026-03-23
*Subject: Re: [PATCH v2 5/5] x86/virt/tdx: Remove kexec docs*

On Mon, 2026-03-23 at 14:59 -0600, Vishal Verma wrote:
> From: Rick Edgecombe <rick.p.edgecombe@intel.com>
> 

Acked-by: Kai Huang <kai.huang@intel.com>

---

## [11] Chao Gao — 2026-03-24
*Subject: Re: [PATCH v2 1/5] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

On Mon, Mar 23, 2026 at 02:59:04PM -0600, Vishal Verma wrote:
>From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
>

Reviewed-by: Chao Gao <chao.gao@intel.com>

---

## [12] Chao Gao — 2026-03-24
*Subject: Re: [PATCH v2 2/5] x86/virt/tdx: Pull kexec cache flush logic into
 arch/x86*

On Mon, Mar 23, 2026 at 02:59:05PM -0600, Vishal Verma wrote:
>From: Rick Edgecombe <rick.p.edgecombe@intel.com>
>

Reviewed-by: Chao Gao <chao.gao@intel.com>

---

## [13] Chao Gao — 2026-03-24
*Subject: Re: [PATCH v2 3/5] x86/virt/tdx: Add SEAMCALL wrapper for
 TDH.SYS.DISABLE*

On Mon, Mar 23, 2026 at 02:59:06PM -0600, Vishal Verma wrote:
>Some early TDX-capable platforms have an erratum where a partial write
>to TDX private memory can cause a machine check on a subsequent read.

Reviewed-by: Chao Gao <chao.gao@intel.com>

---

## [14] Kiryl Shutsemau — 2026-03-30
*Subject: Re: [PATCH v2 2/5] x86/virt/tdx: Pull kexec cache flush logic into
 arch/x86*

On Mon, Mar 23, 2026 at 02:59:05PM -0600, Vishal Verma wrote:
> From: Rick Edgecombe <rick.p.edgecombe@intel.com>
> 

Acked-by: Kiryl Shutsemau (Meta) <kas@kernel.org>

---

## [15] Kiryl Shutsemau — 2026-03-30
*Subject: Re: [PATCH v2 3/5] x86/virt/tdx: Add SEAMCALL wrapper for
 TDH.SYS.DISABLE*

On Mon, Mar 23, 2026 at 02:59:06PM -0600, Vishal Verma wrote:
> Some early TDX-capable platforms have an erratum where a partial write
> to TDX private memory can cause a machine check on a subsequent read.

Nit: Add a new line here.

> +	 *  - TDX_INTERRUPTED_RESUMABLE guarantees forward progress between
> +	 *    calls.

And here.

> +	 *  - TDX_SYS_BUSY could transiently contend with TDH.SYS.* SEAMCALLs,
> +	 *    but will lock out future ones.

Locked out by who? Is it TDX module contract? I don't see it documented in
the spec.

I assumed that if the SEAMCALL fails other SEAMCALLs suppose to be
functional. Hm?

> +	 *
> +	 * This is a 'destructive' SEAMCALL, in that no other SEAMCALL can be

---

## [16] Kiryl Shutsemau — 2026-03-30
*Subject: Re: [PATCH v2 4/5] x86/tdx: Disable the TDX module during kexec and
 kdump*

On Mon, Mar 23, 2026 at 02:59:07PM -0600, Vishal Verma wrote:
> Use the TDH.SYS.DISABLE SEAMCALL, which disables the TDX module,
> reclaims all memory resources assigned to TDX, and clears any

Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>

---

## [17] Kiryl Shutsemau — 2026-03-30
*Subject: Re: [PATCH v2 5/5] x86/virt/tdx: Remove kexec docs*

On Mon, Mar 23, 2026 at 02:59:08PM -0600, Vishal Verma wrote:
> From: Rick Edgecombe <rick.p.edgecombe@intel.com>
> 

Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>

---

## [18] Edgecombe, Rick P — 2026-03-30
*Subject: Re: [PATCH v2 3/5] x86/virt/tdx: Add SEAMCALL wrapper for
 TDH.SYS.DISABLE*

On Mon, 2026-03-30 at 11:58 +0000, Kiryl Shutsemau wrote:
> > +	 *  - TDX_SYS_BUSY could transiently contend with
> > TDH.SYS.* SEAMCALLs,

Yea, by the TDX module.

We relayed that we need this specific behavior around TDX_SYS_BUSY
contention, but the implementation isn't done. That spec is actually
still in draft form. Which is refreshing, because we can actually tweak
things like this based on what the kernel needs.

> 
> I assumed that if the SEAMCALL fails other SEAMCALLs suppose to be

The behavior should be that once you make this seamcall (assuming it's
supported) that no other seamcalls can be made. They will return an
error. Do you think something else would be better? If it's an old TDX
module, nothing happens of course.

So let's change the module if we see a problem. What should it be?

---

## [19] Kiryl Shutsemau — 2026-03-31
*Subject: Re: [PATCH v2 3/5] x86/virt/tdx: Add SEAMCALL wrapper for
 TDH.SYS.DISABLE*

On Mon, Mar 30, 2026 at 07:25:22PM +0000, Edgecombe, Rick P wrote:
> > I assumed that if the SEAMCALL fails other SEAMCALLs suppose to be
> > functional. Hm?

I guess the actual behaviour is dependant on the return code. It is
obviously going to be the case for TDX_SUCCESS. And from the discussion,
I guess that's true for TDX_SYS_BUSY and TDX_INTERRUPTED_RESUMABLE.

What about other cases? The spec draft also lists TDX_SYS_NOT_READY and
TDX_SYS_SHUTDOWN.

I wounder if it can affect the kernel. Consider the case when kexec
(crash kernel start) happens due to crash on TDX module.

Will we be able to shutdown TDX module cleanly and make kexec safe?

---

## [20] Verma, Vishal L — 2026-03-31
*Subject: Re: [PATCH v2 3/5] x86/virt/tdx: Add SEAMCALL wrapper for
 TDH.SYS.DISABLE*

On Tue, 2026-03-31 at 13:18 +0100, Kiryl Shutsemau wrote:
> On Mon, Mar 30, 2026 at 07:25:22PM +0000, Edgecombe, Rick P wrote:
> > > I assumed that if the SEAMCALL fails other SEAMCALLs suppose to be

I think these are safe too - TDX_SYS_SHUTDOWN means the module has
already been shutdown, which this seamcall would've done, so things
should be in the same state either way.

TDX_SYS_NOT_READY means the module hasn't been initialized yet. This
seamcall should just exit, and the module is already blocking any
seamcall that need the module to be initialized. The seamcalls to
initialize the module will be allowed, as they are after a sys_disable
call anyway.

> 
> I wounder if it can affect the kernel. Consider the case when kexec

Hm  -are the semantics for what happens if there is a crash in the
module defined? I think Linux should expect that sys_disable should
either start doing its shutdown work, or exit with one of the other
defined exit statuses. Anything else would be considered a module bug.

---

## [21] Sean Christopherson — 2026-03-31
*Subject: Re: [PATCH v2 2/5] x86/virt/tdx: Pull kexec cache flush logic into arch/x86*

On Mon, Mar 23, 2026, Vishal Verma wrote:
> From: Rick Edgecombe <rick.p.edgecombe@intel.com>
> 

Ingoring the potential fixup needed for the existing bug...

Acked-by: Sean Christopherson <seanjc@google.com>

> ---
>  arch/x86/include/asm/tdx.h  |  6 ------

Is there a pre-existing bug here that gets propagate to tdx_shutdown_cpu()?  When
called from kvm_offline_cpu(), preemption won't be fully disabled, but per-CPU
access are fine because the task is pinned to the target CPU.

See https://lore.kernel.org/all/aUVx20ZRjOzKgKqy@google.com

> -
> -	if (!this_cpu_read(cache_state_incoherent))

---

## [22] Sean Christopherson — 2026-03-31
*Subject: Re: [PATCH v2 1/5] x86/tdx: Move all TDX error defines into <asm/shared/tdx_errno.h>*

On Mon, Mar 23, 2026, Vishal Verma wrote:
> diff --git a/arch/x86/kvm/vmx/tdx_errno.h b/arch/x86/include/asm/shared/tdx_errno.h
> similarity index 64%

I don't think the host's SW-defined error codes should be used by the guest.  The
guest can't even make SEAMCALLs.  So unless I'm misunderstanding the purpose, I
don't think it makes sense to move these into tdx_errno.h.

Regardless, please split this up into two patches:

 1. Move tdx_errno.h
 2. Land more #defines in tdx_errno.h

Because IIUC, tdx_errno.h holds *only* architecturally defined values, which makes
(1) super duper trivial to review and ack.

---

## [23] Edgecombe, Rick P — 2026-03-31
*Subject: Re: [PATCH v2 3/5] x86/virt/tdx: Add SEAMCALL wrapper for
 TDH.SYS.DISABLE*

On Tue, 2026-03-31 at 18:22 +0000, Verma, Vishal L wrote:
> > 
> > I guess the actual behaviour is dependant on the return code. It is

Should the seamcall return success in the case where it would return
TDX_SYS_NOT_READY? It is in basically a reset state right? The errors we care
about are actual errors (TDX_SW_ERROR), so it makes no difference to the code in
the patch. But it might be a nicer API for the seamcall?

> 
> > 

We often have the question come up about how much we should to guard against
bugs in the TDX module. I tend to also think we should not do defensive
programming, same as we do for the kernel. If it's easy to handle something or
emit a warning it's nice, but otherwise the solution for such cases should be to
fix the TDX module bug.

But for the kdump case, we don't actually need sys disable to succeed. The kdump
kernel will not load the TDX module. And as for the errata, this already needs a
special situation to be a problem. But even if it happens, I'd think better to
try to the kdump. Not sure what the fix would be for that scenario, even if we
allowed for a large complexity budget. So best effort seems good.

Does it seem reasonable?

---

## [24] Edgecombe, Rick P — 2026-03-31
*Subject: Re: [PATCH v2 1/5] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

On Tue, 2026-03-31 at 12:30 -0700, Sean Christopherson wrote:
>  +#define TDX_SW_ERROR			(TDX_ERROR | GENMASK_ULL(47, 40))
> > +#define TDX_SEAMCALL_VMFAILINVALID	(TDX_SW_ERROR | _ULL(0xFFFF0000))

Seems reasonable.

> 
> Regardless, please split this up into two patches:

Thanks!

---

## [25] Edgecombe, Rick P — 2026-03-31
*Subject: Re: [PATCH v2 2/5] x86/virt/tdx: Pull kexec cache flush logic into
 arch/x86*

On Tue, 2026-03-31 at 12:22 -0700, Sean Christopherson wrote:
> > -
> > -#ifdef CONFIG_KEXEC_CORE

Yes. And actually it got hit during development of this series. This patch will
conflict with the fix:
https://lore.kernel.org/lkml/20260312100009.924136-1-kai.huang@intel.com/

Oh, you acked it actually. But I was under the impression that after this patch
here, the splat wouldn't be triggered. So it inadvertently fixes it. But that
other patch is much more backport friendly.

---

## [26] Sean Christopherson — 2026-03-31
*Subject: Re: [PATCH v2 2/5] x86/virt/tdx: Pull kexec cache flush logic into arch/x86*

On Tue, Mar 31, 2026, Rick P Edgecombe wrote:
> On Tue, 2026-03-31 at 12:22 -0700, Sean Christopherson wrote:
> > > -

Ah, that's why I was a bit confused.  I was assuming tdx_shutdown_cpu() was a
cpuhp callback, but it's actually an IPI callback.

Hmm, isn't this patch wrong then?  Ah, no, the changelog says:

  However, WBINVD is already generally done at CPU offline as matter of course.
  So don't bother adding TDX specific logic for this, and rely on the normal
  WBINVD to handle it.

What's the "normal" WBINVD?  At the very least, tdx_offline_cpu() should have a
comment that explicitly calls out where that WBVIND is.  I assume you're referring
to the wbinvd() calls in things like hlt_play_dead()?

But unless the WBINVD is actually costly, why bother getting fancy?

> But that other patch is much more backport friendly.

---

## [27] Edgecombe, Rick P — 2026-03-31
*Subject: Re: [PATCH v2 2/5] x86/virt/tdx: Pull kexec cache flush logic into
 arch/x86*

On Tue, 2026-03-31 at 16:04 -0700, Sean Christopherson wrote:
> > Oh, you acked it actually. But I was under the impression that after this
> > patch here, the splat wouldn't be triggered. So it inadvertently fixes it.

I guess we could add one in tdx_offline_cpu(). Seems reasonable.

>   I assume you're
> referring to the wbinvd() calls in things like hlt_play_dead()?

Yea.

> 
> But unless the WBINVD is actually costly, why bother getting fancy?

What is the suggestion to make it less fancy? Just put the wbinvd in
tdx_offline_cpu()? Yea that works too. Probably will get a comment either way.

---

## [28] Kiryl Shutsemau — 2026-04-01
*Subject: Re: [PATCH v2 3/5] x86/virt/tdx: Add SEAMCALL wrapper for
 TDH.SYS.DISABLE*

On Tue, Mar 31, 2026 at 09:36:03PM +0000, Edgecombe, Rick P wrote:
> On Tue, 2026-03-31 at 18:22 +0000, Verma, Vishal L wrote:
> > > 

I am not sure. TDX_SYS_NOT_READY can be useful as might indicate
mismatch of system state understanding between kernel and TDX module.

> > > I wounder if it can affect the kernel. Consider the case when kexec
> > > (crash kernel start) happens due to crash on TDX module.

I meant kernel crash around/before TDX module initialization. Sorry for
confusion.

> > I think Linux should expect that sys_disable should
> > either start doing its shutdown work, or exit with one of the other

AFAIK, it is possible to start a normal kernel after kdump is done with
kexec (requires memmap= tricks). And the normal kernel might want to use
TDX again.

Not sure if it is done in practice. I would rather go full reboot path
after crash.

> And as for the errata, this already needs a
> special situation to be a problem. But even if it happens, I'd think better to

I am probably too picky here. We want to start from make basic kexec
functionality to work for start.

Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>

---

## [29] Dave Hansen — 2026-04-01
*Subject: Re: [PATCH v2 3/5] x86/virt/tdx: Add SEAMCALL wrapper for
 TDH.SYS.DISABLE*

On 3/31/26 14:36, Edgecombe, Rick P wrote:
> On Tue, 2026-03-31 at 18:22 +0000, Verma, Vishal L wrote:
>>> I guess the actual behaviour is dependant on the return code. It is

The problem is that the module doesn't have *a* reset state.
TDX_SYS_NOT_READY gets returned before the module is initialized and
initialization is a long, arduous process.

For instance, I believe the module stays "not ready" in the middle of
giving it PAMT memory and a keyID and all that jazz.

TDX_SYS_NOT_READY is a way of saying it can't easily *make* it to the
actual reset state that TDH.SYS.DISABLE wants it to be in.

It's arguable that the module should be made more resilient to stop
returning TDX_SYS_NOT_READY. But it's not as simple as just changing a
return code in the module.

I'm OK with it continuing to return TDX_SYS_NOT_READY for now. I think
it's a useful indicator. Maybe the kernel can't do much with it, but
it's a little window into what went wrong.

---

## [30] Dave Hansen — 2026-04-01
*Subject: Re: [PATCH v2 2/5] x86/virt/tdx: Pull kexec cache flush logic into
 arch/x86*

On 3/31/26 16:04, Sean Christopherson wrote:
> But unless the WBINVD is actually costly, why bother getting fancy?

WBINVD might be the most expensive single instruction in the whole ISA.

That said, I'd much rather have a potentially unnecessary WBINVD than
miss one. The thing I'd be worried about would be something wonky like:

	1. CPU offline does WBINVD
	2. Some other TDX call gets made, dirties caches again
	3. tdx_offline_cpu() skips WBINVD

So, let's just do both for now: Do WBINVD in tdx_offline_cpu() and
comment that it might be redundant with other things in the CPU offline
procedure.

This really needs to be solved with infrastructure and keeping data
about the reasons for needing WBINVD, not relying on code ordering or
fragile semantics.

---

## [31] H. Peter Anvin — 2026-04-01
*Subject: Re: [PATCH v2 2/5] x86/virt/tdx: Pull kexec cache flush logic into arch/x86*

On April 1, 2026 8:03:02 AM PDT, Dave Hansen <dave.hansen@intel.com> wrote:
>On 3/31/26 16:04, Sean Christopherson wrote:
>> But unless the WBINVD is actually costly, why bother getting fancy?

It is, *by far*, the most expensive *uninterruptible* instruction in the ISA. REP string instructions can of course be arbitrarily long, but are interruptible and so don't really count.

Some MSRs used during very early (pre-OS) initialization might be even slower on some implementations, but that's not visible to Linux and no workload of any kind is running.

---

## [32] Sean Christopherson — 2026-04-01
*Subject: Re: [PATCH v2 2/5] x86/virt/tdx: Pull kexec cache flush logic into arch/x86*

On Wed, Apr 01, 2026, H. Peter Anvin wrote:
> On April 1, 2026 8:03:02 AM PDT, Dave Hansen <dave.hansen@intel.com> wrote:
> >On 3/31/26 16:04, Sean Christopherson wrote:

Sorry, "costly" wasn't the right word.  I know WBINVD super expensive, but unless
someone cares deeply about the latency of offlining a CPU after its down TDX stuff,
the "cost" is effectively zero.

---

## [33] Dave Hansen — 2026-04-01
*Subject: Re: [PATCH v2 2/5] x86/virt/tdx: Pull kexec cache flush logic into
 arch/x86*

On 4/1/26 11:12, Sean Christopherson wrote:
> Sorry, "costly" wasn't the right word.  I know WBINVD super
> expensive, but unless someone cares deeply about the latency of

I once increased the CPU online/offline latency once and got nastygrams
from folks. IIRC, I added a synchronize_rcu() which incurs way more
latency than WBINVD, but folks _do_ care about CPU online/offline
latency surprisingly.

In this case, though, I'm happy to add the WBINVD for simplicity and
wait for a possible repeat of the torches an pitchforks.

---
