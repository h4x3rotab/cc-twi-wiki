---
title: 'Fuller TDX kexec support'
date: 2026-03-06
last_reply: 2026-03-17
message_count: 15
participants: ['Rick Edgecombe', 'Huang, Kai', 'Chao Gao', 'Kiryl Shutsemau']
---

## [1] Rick Edgecombe — 2026-03-06

Hi,

This series adds a couple of cool things -
 1. Allow kexec and kdump on systems with the partial write errata
 2. Allow using TDX in the second (kexec'ed) kernel
 
It has been waiting for VMXON refactor to land because the implementation 
is much cleaner on top of that. The series was mostly done by Vishal, 
however for scheduling reasons I'm posting it on his behalf. I can handle 
all questions/comments for the time being. So it's ready for review.

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

Testing
=======
The new SEAMCALL has NOT been implemented in a TDX module yet. The
implementation is based on the draft TDX module spec available at [1].

Testing was limited to the TDX CI, and a basic kexec test. The code needs 
to be robust to the TDX module not containing the feature, so this 
effectively serves as regression test. During development further testing 
was done by mocking up the new SEAMCALL to introduce delays and exercise 
the retry loops, combined with kexec, kdump, reboot and shutdown flows.

Base
====
This series is based on the vmxon branch Sean pushed to kvm_x86, 
kvm-x86-vmxon-2026.03.05.

[0]: https://lore.kernel.org/kvm/20260129011517.3545883-11-seanjc@google.com/
[1]: https://cdrdv2.intel.com/v1/dl/getContent/871617

Kiryl Shutsemau (1):
  x86/tdx: Move all TDX error defines into <asm/shared/tdx_errno.h>

Rick Edgecombe (1):
  x86/virt/tdx: Pull kexec cache flush logic into arch/x86

Vishal Verma (2):
  x86/virt/tdx: Add SEAMCALL wrapper for TDH.SYS.DISABLE
  KVM: x86: Disable the TDX module during kexec and kdump

 arch/x86/include/asm/shared/tdx.h             |  1 +
 .../vmx => include/asm/shared}/tdx_errno.h    | 27 +++++++++--
 arch/x86/include/asm/tdx.h                    | 29 ++----------
 arch/x86/kernel/crash.c                       |  2 +
 arch/x86/kernel/machine_kexec_64.c            | 16 -------
 arch/x86/kvm/vmx/tdx.c                        | 10 ----
 arch/x86/kvm/vmx/tdx.h                        |  1 -
 arch/x86/virt/vmx/tdx/tdx.c                   | 46 +++++++++++++------
 arch/x86/virt/vmx/tdx/tdx.h                   |  1 +
 9 files changed, 62 insertions(+), 71 deletions(-)
 rename arch/x86/{kvm/vmx => include/asm/shared}/tdx_errno.h (65%)

---

## [2] Rick Edgecombe — 2026-03-06
*Subject: [PATCH 1/4] x86/tdx: Move all TDX error defines into <asm/shared/tdx_errno.h>*

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

Place the new header in "asm/shared". While the compressed code for the
guest doesn't use these error code header definitions today, it does
make the types of calls that return the values they define. Place the
defines in "shared" location so that compressed code has the definitions
accessible, but leave cleanups to use proper error codes for future
changes.

Opportunistically massage some comments. Also, adjust
_BITUL()->_BITULL() to address 32 bit build errors after the move.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[enhance log]
Tested-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
Acked-by: Vishal Annapurve <vannapurve@google.com>
Signed-off-by: Vishal Verma <vishal.l.verma@intel.com>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
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
index a149740b24e8..0c1ae4954f17 100644
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

## [3] Rick Edgecombe — 2026-03-06
*Subject: [PATCH 2/4] x86/virt/tdx: Pull kexec cache flush logic into arch/x86*

KVM tries to take care of some required cache flushing earlier in the
kexec path in order to be kind to some long standing races that can occur
later in the operation. Until recently, VMXOFF was handled within KVM.
Since VMX being enabled is required to make a SEAMCALL, it had the best
per-cpu scoped operation to plug the flushing into.

This early kexec cache flushing in KVM happens via a syscore shutdown 
callback. Now that VMX enablement control has moved to arch/x86, which has 
grown its own syscore shutdown callback, it no longer make sense for it to 
live in KVM. It fits better with the TDX enablement managing code.

In addition, future changes will add a SEAMCALL that happens immediately
before VMXOFF, which means the cache flush in KVM will be too late to be
helpful. So move it to the newly added TDX arch/x86 syscore shutdown
handler.

Since tdx_cpu_flush_cache_for_kexec() is no longer needed by KVM, make it 
static and remove the export. Since it is also not part of an operation 
spread across disparate components, remove the redundant comments and 
verbose naming.

Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
 arch/x86/include/asm/tdx.h  |  6 ------
 arch/x86/kvm/vmx/tdx.c      | 10 ----------
 arch/x86/virt/vmx/tdx/tdx.c | 39 +++++++++++++++++++------------------
 3 files changed, 20 insertions(+), 35 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 0c1ae4954f17..f0826b0a512a 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -206,11 +206,5 @@ static inline const char *tdx_dump_mce_info(struct mce *m) { return NULL; }
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

## [4] Rick Edgecombe — 2026-03-06
*Subject: [PATCH 3/4] x86/virt/tdx: Add SEAMCALL wrapper for TDH.SYS.DISABLE*

From: Vishal Verma <vishal.l.verma@intel.com>

Some early TDX-capable platforms have an erratum where a partial write
to TDX private memory can cause a machine check on a subsequent read.
On these platforms, kexec and kdump have been disabled in these cases,
because the old kernel cannot safely hand off TDX state to the new
kernel. Later TDX modules support the TDH.SYS.DISABLE SEAMCALL, which
provides a way to cleanly disable TDX and allow kexec to proceed.

This can be a long running operation, and the time needed largely
depends on the amount of memory that has been allocated to TDs. If all
TDs have been destroyed prior to the sys_disable call, then it is fast,
with only needing to override the TDX module memory.

After the SEAMCALL completes, the TDX module is disabled and all memory
resources allocated to TDX are freed and reset. The next kernel can then
re-initialize the TDX module from scratch via the normal TDX bring-up
sequence.

The SEAMCALL may be interrupted by an interrupt. In this case, it
returns TDX_INTERRUPTED_RESUMABLE, and it must be retried in a loop
until the operation completes successfully.

Add a tdx_sys_disable() helper, which implements the retry loop around
the SEAMCALL to provide this functionality.

Signed-off-by: Vishal Verma <vishal.l.verma@intel.com>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
 arch/x86/include/asm/tdx.h  |  3 +++
 arch/x86/virt/vmx/tdx/tdx.c | 18 ++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h |  1 +
 3 files changed, 22 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index f0826b0a512a..baaf43a09e99 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -173,6 +173,8 @@ static inline int pg_level_to_tdx_sept_level(enum pg_level level)
         return level - 1;
 }
 
+void tdx_sys_disable(void);
+
 u64 tdh_vp_enter(struct tdx_vp *vp, struct tdx_module_args *args);
 u64 tdh_mng_addcx(struct tdx_td *td, struct page *tdcs_page);
 u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, struct page *page, struct page *source, u64 *ext_err1, u64 *ext_err2);
@@ -204,6 +206,7 @@ static inline void tdx_init(void) { }
 static inline u32 tdx_get_nr_guest_keyids(void) { return 0; }
 static inline const char *tdx_dump_mce_info(struct mce *m) { return NULL; }
 static inline const struct tdx_sys_info *tdx_get_sysinfo(void) { return NULL; }
+static inline void tdx_sys_disable(void) { }
 #endif	/* CONFIG_INTEL_TDX_HOST */
 
 #endif /* !__ASSEMBLER__ */
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 0802d0fd18a4..68bd2618dde4 100644
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
@@ -1940,3 +1941,20 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
 	return seamcall(TDH_PHYMEM_PAGE_WBINVD, &args);
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_phymem_page_wbinvd_hkid);
+
+void tdx_sys_disable(void)
+{
+	struct tdx_module_args args = {};
+
+	/*
+	 * SEAMCALLs that can return TDX_INTERRUPTED_RESUMABLE are guaranteed
+	 * to make forward progress between interrupts, so it is safe to loop
+	 * unconditionally here.
+	 *
+	 * This is a 'destructive' SEAMCALL, in that no other SEAMCALL can be
+	 * run after this until a full reinitialization is done.
+	 */
+	while (seamcall(TDH_SYS_DISABLE, &args) == TDX_INTERRUPTED_RESUMABLE)
+		;
+}
+
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

---

## [5] Rick Edgecombe — 2026-03-06
*Subject: [PATCH 4/4] KVM: x86: Disable the TDX module during kexec and kdump*

From: Vishal Verma <vishal.l.verma@intel.com>

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

Since this clears any poison on TDX-managed memory, the
X86_BUG_TDX_PW_MCE check in machine_kexec() that blocked kexec on
partial write errata platforms can be removed.

Signed-off-by: Vishal Verma <vishal.l.verma@intel.com>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
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
index 68bd2618dde4..b388fbce5d76 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -252,6 +252,7 @@ static void tdx_shutdown_cpu(void *ign)
 
 static void tdx_shutdown(void *ign)
 {
+	tdx_sys_disable();
 	on_each_cpu(tdx_shutdown_cpu, NULL, 1);
 }

---

## [6] Huang, Kai — 2026-03-08
*Subject: Re: [PATCH 1/4] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

On Fri, 2026-03-06 at 17:03 -0800, Rick Edgecombe wrote:
> From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
> 

Seems this patch was from your DPAMT v4.

I made couple of small comments to that:

https://lore.kernel.org/kvm/6968dcb446fb857b3f254030e487d889b464d7ce.camel@intel.com/
https://lore.kernel.org/kvm/af7c8f3ec86688709cce550a2fc17110e3fd12b7.camel@intel.com/

.. and seems you agreed to address them.

If you plan to address in the next version, free free to add:

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [7] Huang, Kai — 2026-03-09
*Subject: Re: [PATCH 2/4] x86/virt/tdx: Pull kexec cache flush logic into
 arch/x86*

On Fri, 2026-03-06 at 17:03 -0800, Rick Edgecombe wrote:
> KVM tries to take care of some required cache flushing earlier in the
> kexec path in order to be kind to some long standing races that can occur

[...]

> 
> In addition, future changes will add a SEAMCALL that happens immediately

Nit: I am not sure how to interpret "too late to be helpful".  I think we
can just get rid of this paragraph.

> 
> Since tdx_cpu_flush_cache_for_kexec() is no longer needed by KVM, make it 

Feel free to add:

Acked-by: Kai Huang <kai.huang@intel.com>

Btw, there's a functional change here, and perhaps we should call out in
changelog:

- Currently tdx_cpu_flush_cache_for_kexec() is done in
kvm_disable_virtualization_cpu(), which is also called by KVM's CPUHP
offline() callback.  So tdx_cpu_flush_cache_for_kexec() is explicitly done
in TDX code in CPU offline.

- With this change, tdx_cpu_flush_cache_for_kexec() is not explicitly done
in TDX code in CPU offline.

But AFAICT this is fine, since IIUC the WBINVD is always done when kernel
offlines one CPU (see [*]), i.e., the current
tdx_cpu_flush_cache_for_kexec() done in KVM's CPUHP is actually superfluous.

[*] See:

	native_play_dead() ->
		cpuidle_play_dead();                                                     
        	hlt_play_dead();

cpuidle_play_dead() can invoke different enter_dead() callbacks depending on
what idle driver is being used, but AFAICT eventually it ends up calling
either acpi_idle_play_dead() or mwait_play_dead(), both of which does WBINVD
before going to idle.

If cpuidle_play_dead() doesn't idle successfully, the hlt_play_dead() will
then WBINVD and hlt.

Actually, after looking at multiple commits around here, e.g.,

  ea53069231f93 ("x86, hotplug: Use mwait to offline a processor, fix the
legacy case")
  dfbba2518aac4 ("Revert "ACPI: processor: idle: Only flush cache on
entering C3")

... I believe it's a kernel policy to make sure cache is flushed when it
offlines a CPU (which makes sense anyway of course), I just couldn't find
the exact commit saying this (or I am not sure whether there's such commit).


Btw2, kinda related to this, could you help review:

https://lore.kernel.org/lkml/20260302102226.7459-1-kai.huang@intel.com/

---

## [8] Chao Gao — 2026-03-09
*Subject: Re: [PATCH 4/4] KVM: x86: Disable the TDX module during kexec and
 kdump*

A few nits below:

The scope "KVM: x86" is wrong as this doesn't touch any KVM code.

On Fri, Mar 06, 2026 at 05:03:58PM -0800, Rick Edgecombe wrote:
>From: Vishal Verma <vishal.l.verma@intel.com>
>

Use imperative mood here: "Since ..., remove the X86_BUG_TDX_PW_MCE check..."

>
>Signed-off-by: Vishal Verma <vishal.l.verma@intel.com>

With this series, we need to update the "Kexec" section in tdx.rst.

>-
> 	/* Setup the identity mapped 64bit page table */

---

## [9] Edgecombe, Rick P — 2026-03-09
*Subject: Re: [PATCH 1/4] x86/tdx: Move all TDX error defines into
 <asm/shared/tdx_errno.h>*

On Sun, 2026-03-08 at 23:47 +0000, Huang, Kai wrote:
> Seems this patch was from your DPAMT v4.
> 

Oops. Yea, I incorporated those changes DPAMT branch. But between
Vishal and I, it didn't make it over here. I'll pull that one in for
V2.

> 
> If you plan to address in the next version, free free to add:

Thanks.

---

## [10] Edgecombe, Rick P — 2026-03-09
*Subject: Re: [PATCH 2/4] x86/virt/tdx: Pull kexec cache flush logic into
 arch/x86*

On Mon, 2026-03-09 at 00:23 +0000, Huang, Kai wrote:
> Feel free to add:
> 

Yea that makes sense.

> 
> - Currently tdx_cpu_flush_cache_for_kexec() is done in
Thanks for the analysis.

> Btw2, kinda related to this, could you help review:
> 

Well I think I wrote the log for it. But I yea I'll add a tag.

---

## [11] Edgecombe, Rick P — 2026-03-09
*Subject: Re: [PATCH 4/4] KVM: x86: Disable the TDX module during kexec and
 kdump*

On Mon, 2026-03-09 at 16:15 +0800, Chao Gao wrote:
> > -	/*
> > -	 * Some early TDX-capable platforms have an erratum.  A

Nice catch, and I agree on the others. Will update it. Thanks.

---

## [12] Kiryl Shutsemau — 2026-03-16
*Subject: Re: [PATCH 3/4] x86/virt/tdx: Add SEAMCALL wrapper for
 TDH.SYS.DISABLE*

On Fri, Mar 06, 2026 at 05:03:57PM -0800, Rick Edgecombe wrote:
> From: Vishal Verma <vishal.l.verma@intel.com>
> 

Does it need to be enumerated?

I don't see this SEAMCALL be covered in the public documentation.
</me looking around>
Ah! Found it the the draft. So the feature is not yet finalized.

"Support of TDH.SYS.DISABLE is enumerated by TDX_FEATURES0. SYS_DISABLE
(bit 53)"

I am seeing the next patch calling it unconditionally. Is it okay?

> This can be a long running operation, and the time needed largely
> depends on the amount of memory that has been allocated to TDs. If all

Silently ignore any other errors?

> +}
> +

---

## [13] Edgecombe, Rick P — 2026-03-16
*Subject: Re: [PATCH 3/4] x86/virt/tdx: Add SEAMCALL wrapper for
 TDH.SYS.DISABLE*

On Mon, 2026-03-16 at 11:51 +0000, Kiryl Shutsemau wrote:
> On Fri, Mar 06, 2026 at 05:03:57PM -0800, Rick Edgecombe wrote:
> > From: Vishal Verma <vishal.l.verma@intel.com>

We debated checking the feature bit before allowing kexec, but decided it was
simpler to just blindly call and ignore the errors. The reasoning was that this
is already a somewhat exotic scenario being addressed, and future modules will
have the feature. So maintaining a check for the feature bit only helps a little
bit, for a short time. And then only if the user would rather have kexec blocked
than attempt it. Do you think it is worth it?

> 
> > This can be a long running operation, and the time needed largely

Do you think it's worth a warn? There are a couple other considerations.
  - Kai brought up offline that we should handle TDX_SYS_BUSY here too.
  - Previous kexec patches had trouble solving races around tdx enabling. So we
have to handle the seamcall failures.

So we have to exclude a few different errors in different ways. And then the
warn worthy error codes either don't impact anything, or the new kernel will
fail to initialize the TDX module and give notice there.

I don't have a strong objection. It seems to be a judgment call of whether the
complexity is worth the benefit.

---

## [14] Kiryl Shutsemau — 2026-03-17
*Subject: Re: [PATCH 3/4] x86/virt/tdx: Add SEAMCALL wrapper for
 TDH.SYS.DISABLE*

On Mon, Mar 16, 2026 at 09:15:13PM +0000, Edgecombe, Rick P wrote:
> On Mon, 2026-03-16 at 11:51 +0000, Kiryl Shutsemau wrote:
> > On Fri, Mar 06, 2026 at 05:03:57PM -0800, Rick Edgecombe wrote:

No, I see very limited reason to support stale TDX modules. Users are
expected to keep the module up-to-date, so skipping enumeration should
be okay. But it deserves explanation in the commit message or a comment.

> > > This can be a long running operation, and the time needed largely
> > > depends on the amount of memory that has been allocated to TDs. If all

The delayed error is harder to debug. It can be useful to leave a
breadcrumbs.

Also, do we want to make try_init_module_global() return failure after
tdx_sys_disable()? I guess, TDH_SYS_LP_INIT will fail anyway, so it
shouldn't matter.

---

## [15] Edgecombe, Rick P — 2026-03-17
*Subject: Re: [PATCH 3/4] x86/virt/tdx: Add SEAMCALL wrapper for
 TDH.SYS.DISABLE*

On Tue, 2026-03-17 at 09:47 +0000, Kiryl Shutsemau wrote:
>  We debated checking the feature bit before allowing kexec, but decided it was
> > simpler to just blindly call and ignore the errors. The reasoning was that this

Ok.

> 
> > > 

Ok, we can parse the errors.

> 
> Also, do we want to make try_init_module_global() return failure after

Yea, a side effect of TDH.SYS.DISABLE is that it blocks other seamcalls while it
is executing. I guess the scenario here is TDX init racing with kexec.

But in general if TDX is disabled while any TDX stuff is running, the seamcalls
will be surprised. This is not fully related to TDH.SYS.DISABLE, because VMXOFF
will also cause similar SEAMCALL failures. Each SEAMCALL path would need to
handle the rug pull. And probably we need to balance harmless noise against the
code it takes to be quieter.

try_init_module_global() is different in that it's kernel side code that gets
confused, but I'm not sure how it could be handled in a non-racy way either.
So... I'd think to leave it. Maybe what we really need is a big block comment
about TDX enable/disable lifecycle quirks.

---
