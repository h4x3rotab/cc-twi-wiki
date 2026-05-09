---
title: 'Fuller TDX kexec support'
date: 2026-04-02
last_reply: 2026-04-02
message_count: 8
participants: ['Vishal Verma', 'Sean Christopherson']
---

## [1] Vishal Verma — 2026-04-02

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
    benefit them all from an early merge. This has now also been reduced
    to a simple header move, since the new additions in the original
    patch aren't needed here.

 2. A preparatory patch to move some straggling stuff into arch/x86 in the
    wake of the VMXON series. As noted in the discussion in v2, this
    may need coordination with Kai's patch [1] as they will cause a
    conflict depending on which is merged first.

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
[2], and was smoke tested with an engineering build of the TDX module
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
[1]: https://lore.kernel.org/lkml/20260312100009.924136-1-kai.huang@intel.com/
[2]: https://cdrdv2.intel.com/v1/dl/getContent/871617

---
Changes in v3:
- Various: Collect tags (Kai, Chao, Kiryl, Sean)
- Patch 1: Collapse to a simple header move, drop new defines, and
  non-architectural software defines. (Sean)
- Patch 2: Add WBINVD in the tdx_offline_cpu() path (Sean, Dave)
- Add a paragraph to the seamcall wrapper commit message talking about
  printed errors for seamcall failures (Rick)
- Patch 2: Reword comment in tdx_shutdown_cpu (Chao)
- Patch 3: Reword comment about the TDX_SYS_BUSY error case (Chao)
- Patch 3: Formatting fixes in comments (Kiryl)
- Link to v2: https://patch.msgid.link/20260323-fuller_tdx_kexec_support-v2-0-87a36409e051@intel.com

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
      x86/tdx: Move TDX architectural error codes into <asm/shared/tdx_errno.h>

Rick Edgecombe (2):
      x86/virt/tdx: Pull kexec cache flush logic into arch/x86
      x86/virt/tdx: Remove kexec docs

Vishal Verma (2):
      x86/virt/tdx: Add SEAMCALL wrapper for TDH.SYS.DISABLE
      x86/tdx: Disable the TDX module during kexec and kdump

 Documentation/arch/x86/tdx.rst                       |  7 -------
 arch/x86/include/asm/shared/tdx.h                    |  1 +
 arch/x86/{kvm/vmx => include/asm/shared}/tdx_errno.h |  8 +++----
 arch/x86/include/asm/tdx.h                           |  9 +++-----
 arch/x86/kvm/vmx/tdx.h                               |  1 -
 arch/x86/virt/vmx/tdx/tdx.h                          |  1 +
 arch/x86/kernel/crash.c                              |  2 ++
 arch/x86/kernel/machine_kexec_64.c                   | 16 --------------
 arch/x86/kvm/vmx/tdx.c                               | 10 ---------
 arch/x86/virt/vmx/tdx/tdx.c                          | 64 +++++++++++++++++++++++++++++++++++++++++++++-----------
 10 files changed, 63 insertions(+), 56 deletions(-)

--
2.53.0

---
Kiryl Shutsemau (1):
      x86/tdx: Move TDX architectural error codes into <asm/shared/tdx_errno.h>

Rick Edgecombe (2):
      x86/virt/tdx: Pull kexec cache flush logic into arch/x86
      x86/virt/tdx: Remove kexec docs

Vishal Verma (2):
      x86/virt/tdx: Add SEAMCALL wrapper for TDH.SYS.DISABLE
      x86/tdx: Disable the TDX module during kexec and kdump

 Documentation/arch/x86/tdx.rst                     |  7 ---
 arch/x86/include/asm/shared/tdx.h                  |  1 +
 .../{kvm/vmx => include/asm/shared}/tdx_errno.h    |  8 +--
 arch/x86/include/asm/tdx.h                         |  9 +--
 arch/x86/kvm/vmx/tdx.h                             |  1 -
 arch/x86/virt/vmx/tdx/tdx.h                        |  1 +
 arch/x86/kernel/crash.c                            |  2 +
 arch/x86/kernel/machine_kexec_64.c                 | 16 ------
 arch/x86/kvm/vmx/tdx.c                             | 10 ----
 arch/x86/virt/vmx/tdx/tdx.c                        | 64 ++++++++++++++++++----
 10 files changed, 63 insertions(+), 56 deletions(-)
---
base-commit: f630de1f8d70d7e29e12bc25dc63f9c5f771dc59
change-id: 20260317-fuller_tdx_kexec_support-bc79694678be

Best regards,
--  
Vishal Verma <vishal.l.verma@intel.com>

---

## [2] Vishal Verma — 2026-04-02
*Subject: [PATCH v3 1/5] x86/tdx: Move TDX architectural error codes into
 <asm/shared/tdx_errno.h>*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

Today there are two separate locations where TDX error codes are defined:

  arch/x86/include/asm/tdx.h
  arch/x86/kvm/vmx/tdx_errno.h

They have some overlap that is already defined similarly. Reduce the
duplication by unifying the architectural error codes at:

  asm/shared/tdx_errno.h

...and update the headers that contained the duplicated definitions to
include the new unified header.

"asm/shared" is used for sharing TDX code between the early compressed
code and the normal kernel code. While the compressed code for the guest
doesn't use these error code header definitions today, it does make the
types of calls that return the values they define. So place the defines in
"shared" location so that it can, but leave such cleanups for future
changes.

[Rick: enhance log]
[Vishal: reduce to a simple move of architectural defines only]
Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Vishal Verma <vishal.l.verma@intel.com>
Reviewed-by: Chao Gao <chao.gao@intel.com>
---
 arch/x86/include/asm/shared/tdx.h                    | 1 +
 arch/x86/{kvm/vmx => include/asm/shared}/tdx_errno.h | 7 +++----
 arch/x86/kvm/vmx/tdx.h                               | 1 -
 3 files changed, 4 insertions(+), 5 deletions(-)

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
similarity index 92%
rename from arch/x86/kvm/vmx/tdx_errno.h
rename to arch/x86/include/asm/shared/tdx_errno.h
index 6ff4672c4181..3c1e8ce716e3 100644
--- a/arch/x86/kvm/vmx/tdx_errno.h
+++ b/arch/x86/include/asm/shared/tdx_errno.h
@@ -1,8 +1,7 @@
 /* SPDX-License-Identifier: GPL-2.0 */
 /* architectural status code for SEAMCALL */
-
-#ifndef __KVM_X86_TDX_ERRNO_H
-#define __KVM_X86_TDX_ERRNO_H
+#ifndef _ASM_X86_SHARED_TDX_ERRNO_H
+#define _ASM_X86_SHARED_TDX_ERRNO_H
 
 #define TDX_SEAMCALL_STATUS_MASK		0xFFFFFFFF00000000ULL
 
@@ -37,4 +36,4 @@
 #define TDX_OPERAND_ID_SEPT			0x92
 #define TDX_OPERAND_ID_TD_EPOCH			0xa9
 
-#endif /* __KVM_X86_TDX_ERRNO_H */
+#endif /* _ASM_X86_SHARED_TDX_ERRNO_H */
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

## [3] Vishal Verma — 2026-04-02
*Subject: [PATCH v3 2/5] x86/virt/tdx: Pull kexec cache flush logic into
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
tdx_cpu_flush_cache_for_kexec(). Add an explicit WBINVD in
tdx_offline_cpu() as well, even though it may be redundant with WBINVD
done elsewhere during CPU offline (e.g. hlt_play_dead()). This avoids
relying on fragile code ordering for cache coherency safety.

[Vishal: add explicit WBINVD in tdx_offline_cpu()]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Vishal Verma <vishal.l.verma@intel.com>
Reviewed-by: Chao Gao <chao.gao@intel.com>
Acked-by: Kai Huang <kai.huang@intel.com>
Acked-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Acked-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/tdx.h  |  6 ------
 arch/x86/kvm/vmx/tdx.c      | 10 ----------
 arch/x86/virt/vmx/tdx/tdx.c | 46 ++++++++++++++++++++++++++-------------------
 3 files changed, 27 insertions(+), 35 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index a149740b24e8..bf83a974a0d5 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -226,11 +226,5 @@ static inline const char *tdx_dump_mce_info(struct mce *m) { return NULL; }
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
index cb9b3210ab71..1b2d854ba664 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -184,6 +184,17 @@ static int tdx_online_cpu(unsigned int cpu)
 	return ret;
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
 static int tdx_offline_cpu(unsigned int cpu)
 {
 	int i;
@@ -220,12 +231,28 @@ static int tdx_offline_cpu(unsigned int cpu)
 	return -EBUSY;
 
 done:
+	/*
+	 * Flush cache on the CPU going offline to ensure no dirty
+	 * cachelines of TDX private memory remain. This may be
+	 * redundant with WBINVD done elsewhere during CPU offline
+	 * (e.g. hlt_play_dead()), but do it explicitly for safety.
+	 */
+	tdx_cpu_flush_cache();
 	x86_virt_put_ref(X86_FEATURE_VMX);
 	return 0;
 }
 
 static void tdx_shutdown_cpu(void *ign)
 {
+	/*
+	 * Flush cache in preparation for kexec - this is necessary to avoid
+	 * having dirty private memory cachelines when the new kernel boots,
+	 * but WBINVD is a relatively expensive operation and doing it during
+	 * kexec can exacerbate races in native_stop_other_cpus().  Do it
+	 * now, since this is a safe moment and there is going to be no more
+	 * TDX activity on this CPU from this point on.
+	 */
+	tdx_cpu_flush_cache();
 	x86_virt_put_ref(X86_FEATURE_VMX);
 }
 
@@ -1920,22 +1947,3 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
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

## [4] Vishal Verma — 2026-04-02
*Subject: [PATCH v3 3/5] x86/virt/tdx: Add SEAMCALL wrapper for
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

An error is printed if the SEAMCALL fails with anything other than the
error codes that cause retries, or 'synthesized' error codes produced
for #GP or #UD. e.g., an old module that has been properly initialized,
that doesn't implement SYS_DISABLE, returns TDX_OPERAND_INVALID. This
prints:

  virt/tdx: TDH.SYS.DISABLE failed: 0xc000010000000000

But a system that doesn't have any TDX support at all doesn't print
anything.

Co-developed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Vishal Verma <vishal.l.verma@intel.com>
Reviewed-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Acked-by: Kai Huang <kai.huang@intel.com>
---
 arch/x86/include/asm/shared/tdx_errno.h |  1 +
 arch/x86/include/asm/tdx.h              |  3 +++
 arch/x86/virt/vmx/tdx/tdx.h             |  1 +
 arch/x86/virt/vmx/tdx/tdx.c             | 31 +++++++++++++++++++++++++++++++
 4 files changed, 36 insertions(+)

diff --git a/arch/x86/include/asm/shared/tdx_errno.h b/arch/x86/include/asm/shared/tdx_errno.h
index 3c1e8ce716e3..ee411b360e20 100644
--- a/arch/x86/include/asm/shared/tdx_errno.h
+++ b/arch/x86/include/asm/shared/tdx_errno.h
@@ -13,6 +13,7 @@
 #define TDX_NON_RECOVERABLE_TD_NON_ACCESSIBLE	0x6000000500000000ULL
 #define TDX_NON_RECOVERABLE_TD_WRONG_APIC_MODE	0x6000000700000000ULL
 #define TDX_INTERRUPTED_RESUMABLE		0x8000000300000000ULL
+#define TDX_SYS_BUSY				0x8000020200000000ULL
 #define TDX_OPERAND_INVALID			0xC000010000000000ULL
 #define TDX_OPERAND_BUSY			0x8000020000000000ULL
 #define TDX_PREVIOUS_TLB_EPOCH_BUSY		0x8000020100000000ULL
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index bf83a974a0d5..15eac89b0afb 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -193,6 +193,8 @@ static inline int pg_level_to_tdx_sept_level(enum pg_level level)
         return level - 1;
 }
 
+void tdx_sys_disable(void);
+
 u64 tdh_vp_enter(struct tdx_vp *vp, struct tdx_module_args *args);
 u64 tdh_mng_addcx(struct tdx_td *td, struct page *tdcs_page);
 u64 tdh_mem_page_add(struct tdx_td *td, u64 gpa, struct page *page, struct page *source, u64 *ext_err1, u64 *ext_err2);
@@ -224,6 +226,7 @@ static inline void tdx_init(void) { }
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
index 1b2d854ba664..1ae558bcca3a 100644
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
@@ -1947,3 +1948,33 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, struct page *page)
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
+	 *
+	 *  - TDX_INTERRUPTED_RESUMABLE guarantees forward progress between
+	 *    calls.
+	 *
+	 *  - TDX_SYS_BUSY could be returned due to contention with other
+	 *    TDH.SYS.* SEAMCALLs, but will lock out *new* TDH.SYS.* SEAMCALLs,
+	 *    so that SYS.DISABLE can eventually make progress.
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

## [5] Vishal Verma — 2026-04-02
*Subject: [PATCH v3 4/5] x86/tdx: Disable the TDX module during kexec and
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
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Acked-by: Kai Huang <kai.huang@intel.com>
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
index 1ae558bcca3a..c0c6281b08a5 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -259,6 +259,7 @@ static void tdx_shutdown_cpu(void *ign)
 
 static void tdx_shutdown(void *ign)
 {
+	tdx_sys_disable();
 	on_each_cpu(tdx_shutdown_cpu, NULL, 1);
 }

---

## [6] Vishal Verma — 2026-04-02
*Subject: [PATCH v3 5/5] x86/virt/tdx: Remove kexec docs*

From: Rick Edgecombe <rick.p.edgecombe@intel.com>

Recent changes have removed the hard limitations for using kexec and
TDX together. So remove the section in the TDX docs.

Users on partial write erratums will need an updated TDX module to
handle the rare edge cases. The docs do not currently provide any
guidance on recommended TDX module versions, so don't keep a whole
section around to document this interaction.

Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Vishal Verma <vishal.l.verma@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Acked-by: Kai Huang <kai.huang@intel.com>
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

## [7] Sean Christopherson — 2026-04-02
*Subject: Re: [PATCH v3 1/5] x86/tdx: Move TDX architectural error codes into <asm/shared/tdx_errno.h>*

On Thu, Apr 02, 2026, Vishal Verma wrote:
> From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
> 

Nit, when calling out minor amendments, IMO the blurb in the square braces should
be after the previous SoB so that there's a clear, consistent chain of handling
and ordering.  I.e.

  Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
  [Rick: enhance log]
  Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
  [Vishal: reduce to a simple move of architectural defines only]
  Signed-off-by: Vishal Verma <vishal.l.verma@intel.com>

That makes it clear the Kirill signed off on something, then Rick tweaked the
changelog and signed off on _that_, and Vishal came along and simplified the
path.

Acked-by: Sean Christopherson <seanjc@google.com>

> Reviewed-by: Chao Gao <chao.gao@intel.com>
> ---

For the record, the defines in tdx_errno.h are only ever used by arch/x86/kvm/vmx/tdx.c,
and that file already included asm/shared/tdx.h by way of arch/x86/include/asm/tdx.h.

>  #ifdef CONFIG_KVM_INTEL_TDX
>  #include "common.h"

---

## [8] Verma, Vishal L — 2026-04-02
*Subject: Re: [PATCH v3 1/5] x86/tdx: Move TDX architectural error codes into
 <asm/shared/tdx_errno.h>*

On Thu, 2026-04-02 at 10:47 -0700, Sean Christopherson wrote:
> On Thu, Apr 02, 2026, Vishal Verma wrote:
> > From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
That is indeed what I'm used to seeing/doing as well, I changed it to
this style after re-reading the tag ordering guidelines in maintainer-
tip.rst:

https://docs.kernel.org/process/maintainer-tip.html#ordering-of-commit-tags

   If the handler made modifications to the patch or the changelog,
   then this should be mentioned after the changelog text and above all
   commit tags in the following format:
   
   ... changelog text ends.
   
   [ handler: Replaced foo by bar and updated changelog ]
   
   First-tag: .....
   
Although now I see I screwed even that up slightly - it calls for a blank
line after the [ ... ] notes.

---
