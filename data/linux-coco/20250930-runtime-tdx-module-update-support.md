---
title: 'Runtime TDX Module update support'
date: 2025-09-30
last_reply: 2026-01-26
message_count: 120
participants: ['Chao Gao', 'Vishal Annapurve', 'Reshetova, Elena', 'Dave Hansen', 'dan.j.williams@intel.com', 'Sean Christopherson', 'Erdem Aktas', 'Sagi Shahar', 'Binbin Wu', 'Edgecombe, Rick P', 'Xu Yilun', 'Duan, Zhenzhong', 'H. Peter Anvin']
---

## [1] Chao Gao — 2025-09-30

Changelog:
v1->v2:
 - Replace tdx subsystem with a "tdx-host" device implementation
 - Reorder patches to reduce reviewer's mental "list of things to look out for"
 - Replace "TD-Preserving update" with "runtime TDX Module Update"
 - Drop the temporary "td_preserving_ready" flag
 - Move low-level SEAMCALL helpers to its own header file
 - Don't create a new, inferior framework to save/restore VMCS
 - Minor cleanups and changelog improvements for clarity and consistency
 - Collect review tags
 - I didn't add Sagi Shahar's Tested-by due to various changes/reorder etc.
 - v1: https://lore.kernel.org/kvm/20250523095322.88774-1-chao.gao@intel.com/

Hi Reviewers,

This series adds support for runtime TDX Module updates that preserve
running TDX guests.

== Background ==

Intel TDX isolates Trusted Domains (TDs), or confidential guests, from the
host. A key component of Intel TDX is the TDX Module, which enforces
security policies to protect the memory and CPU states of TDs from the
host. However, the TDX Module is software that require updates.

== Problems ==

Currently, the TDX Module is loaded by the BIOS at boot time, and the only
way to update it is through a reboot, which results in significant system
downtime. Users expect the TDX Module to be updatable at runtime without
disrupting TDX guests.

== Solution ==

On TDX platforms, P-SEAMLDR[1] is a component within the protected SEAM
range. It is loaded by the BIOS and provides the host with functions to
install a TDX Module at runtime.

Implement a TDX Module update facility via the fw_upload mechanism. Given
that there is variability in which module update to load based on features,
fix levels, and potentially reloading the same version for error recovery
scenarios, the explicit userspace chosen payload flexibility of fw_upload
is attractive.

This design allows the kernel to accept a bitstream instead of loading a
named file from the filesystem, as the module selection and policy
enforcement for TDX Modules are quite complex (see more in patch 8). By
doing so, much of this complexity is shifted out of the kernel. The kernel
need to expose information, such as the TDX Module version, to userspace.
Userspace must understand the TDX Module versioning scheme and update
policy to select the appropriate TDX Module (see "TDX Module Versioning"
below).

In the unlikely event the update fails, for example userspace picks an
incompatible update image, or the image is otherwise corrupted, all TDs
will experience SEAMCALL failures and be killed. The recovery of TD
operation from that event requires a reboot.

Given there is no mechanism to quiesce SEAMCALLs, the TDs themselves must
pause execution over an update. The most straightforward way to meet the
'pause TDs while update executes' constraint is to run the update in
stop_machine() context. All other evaluated solutions export more
complexity to KVM, or exports more fragility to userspace.

== How to test this series ==

This series can be tested using the userspace tool that is able to
select the appropriate TDX module and install it via the interfaces
exposed by this series:

 # git clone https://github.com/intel/tdx-module-binaries
 # cd tdx-module-binaries
 # python version_select_and_load.py --update

== Base commit ==

This series is based on:
https://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git/commit/?h=tdx&id=9332e088937f

and the TDX Module version series at:
https://lore.kernel.org/linux-coco/20251001022309.277238-1-chao.gao@intel.com


== Other information relevant to Runtime TDX Module updates == 

=== TDX Module versioning ===

Each TDX Module is assigned a version number x.y.z, where x represents the
"major" version, y the "minor" version, and z the "update" version.

Runtime TDX Module updates are restricted to Z-stream releases.

Note that Z-stream releases do not necessarily guarantee compatibility. A
new release may not be compatible with all previous versions. To address this,
Intel provides a separate file containing compatibility information, which
specifies the minimum module version required for a particular update. This
information is referenced by the tool to determine if two modules are
compatible.

=== TCB Stability ===

Updates change the TCB as viewed by attestation reports. In TDX there is
a distinction between launch-time version and current version where
runtime TDX Module updates cause that latter version number to change,
subject to Z-stream constraints.

The concern that a malicious host may attack confidential VMs by loading
insecure updates was addressed by Alex in [3]. Similarly, the scenario
where some "theoretical paranoid tenant" in the cloud wants to audit
updates and stop trusting the host after updates until audit completion
was also addressed in [4]. Users not in the cloud control the host machine
and can manage updates themselves, so they don't have these concerns.

See more about the implications of current TCB version changes in
attestation as summarized by Dave in [5].

=== TDX Module Distribution Model ===

At a high level, Intel publishes all TDX Modules on the github [2], along
with a mapping_file.json which documents the compatibility information
about each TDX Module and a userspace tool to install the TDX Module. OS
vendors can package these modules and distribute them. Administrators
install the package and use the tool to select the appropriate TDX Module
and install it via the interfaces exposed by this series.

[1]: https://cdrdv2.intel.com/v1/dl/getContent/733584
[2]: https://github.com/intel/tdx-module-binaries
[3]: https://lore.kernel.org/all/665c5ae0-4b7c-4852-8995-255adf7b3a2f@amazon.com/
[4]: https://lore.kernel.org/all/5d1da767-491b-4077-b472-2cc3d73246d6@amazon.com/
[5]: https://lore.kernel.org/all/94d6047e-3b7c-4bc1-819c-85c16ff85abf@intel.com/


Chao Gao (20):
  x86/virt/tdx: Print SEAMCALL leaf numbers in decimal
  x86/virt/tdx: Use %# prefix for hex values in SEAMCALL error messages
  x86/virt/tdx: Prepare to support P-SEAMLDR SEAMCALLs
  x86/virt/seamldr: Introduce a wrapper for P-SEAMLDR SEAMCALLs
  x86/virt/seamldr: Retrieve P-SEAMLDR information
  coco/tdx-host: Expose P-SEAMLDR information via sysfs
  coco/tdx-host: Implement FW_UPLOAD sysfs ABI for TDX Module updates
  x86/virt/seamldr: Block TDX Module updates if any CPU is offline
  x86/virt/seamldr: Verify availability of slots for TDX Module updates
  x86/virt/seamldr: Allocate and populate a module update request
  x86/virt/seamldr: Introduce skeleton for TDX Module updates
  x86/virt/seamldr: Abort updates if errors occurred midway
  x86/virt/seamldr: Shut down the current TDX module
  x86/virt/tdx: Reset software states after TDX module shutdown
  x86/virt/seamldr: Handle TDX Module update failures
  x86/virt/seamldr: Install a new TDX Module
  x86/virt/seamldr: Do TDX per-CPU initialization after updates
  x86/virt/tdx: Establish contexts for the new TDX Module
  x86/virt/tdx: Update tdx_sysinfo and check features post-update
  x86/virt/tdx: Enable TDX Module runtime updates

Kai Huang (1):
  x86/virt/tdx: Move low level SEAMCALL helpers out of <asm/tdx.h>

 .../ABI/testing/sysfs-devices-faux-tdx-host   |  25 ++
 arch/x86/Kconfig                              |  12 +
 arch/x86/include/asm/seamldr.h                |  29 ++
 arch/x86/include/asm/tdx.h                    |  38 +-
 arch/x86/include/asm/tdx_global_metadata.h    |   5 +
 arch/x86/virt/vmx/tdx/Makefile                |   1 +
 arch/x86/virt/vmx/tdx/seamcall.h              | 106 +++++
 arch/x86/virt/vmx/tdx/seamldr.c               | 382 ++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.c                   | 149 ++++---
 arch/x86/virt/vmx/tdx/tdx.h                   |  12 +-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c   |  13 +
 drivers/virt/coco/tdx-host/tdx-host.c         | 189 ++++++++-
 12 files changed, 884 insertions(+), 77 deletions(-)
 create mode 100644 arch/x86/include/asm/seamldr.h
 create mode 100644 arch/x86/virt/vmx/tdx/seamcall.h
 create mode 100644 arch/x86/virt/vmx/tdx/seamldr.c

---

## [2] Chao Gao — 2025-09-30
*Subject: [PATCH v2 01/21] x86/virt/tdx: Print SEAMCALL leaf numbers in decimal*

Both TDX spec and kernel defines SEAMCALL leaf numbers as decimal. Printing
them in hex makes no sense. Correct it.

Suggested-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
---
v2:
 - print leaf numbers with %llu
---
 arch/x86/virt/vmx/tdx/tdx.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index ada2fd4c2d54..e406edd28687 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -62,7 +62,7 @@ typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);
 
 static inline void seamcall_err(u64 fn, u64 err, struct tdx_module_args *args)
 {
-	pr_err("SEAMCALL (0x%016llx) failed: 0x%016llx\n", fn, err);
+	pr_err("SEAMCALL (%llu) failed: 0x%016llx\n", fn, err);
 }
 
 static inline void seamcall_err_ret(u64 fn, u64 err,

---

## [3] Chao Gao — 2025-09-30
*Subject: [PATCH v2 02/21] x86/virt/tdx: Use %# prefix for hex values in SEAMCALL error messages*

"%#" format specifier automatically adds the "0x" prefix and has one less
character than "0x%".

For conciseness, replace "0x%" with "%#" when printing hexadecimal values
in SEAMCALL error messages.

Suggested-by: Dan Williams <dan.j.williams@intel.com>
Signed-off-by: Chao Gao <chao.gao@intel.com>
---
"0x%" is also used to print TDMR ranges. I didn't convert them to reduce
code churn, but if they should be converted for consistency, I'm happy
to do that.

v2: new
---
 arch/x86/virt/vmx/tdx/tdx.c | 6 +++---
 1 file changed, 3 insertions(+), 3 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index e406edd28687..f429a5fdced2 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -62,16 +62,16 @@ typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);
 
 static inline void seamcall_err(u64 fn, u64 err, struct tdx_module_args *args)
 {
-	pr_err("SEAMCALL (%llu) failed: 0x%016llx\n", fn, err);
+	pr_err("SEAMCALL (%llu) failed: %#016llx\n", fn, err);
 }
 
 static inline void seamcall_err_ret(u64 fn, u64 err,
 				    struct tdx_module_args *args)
 {
 	seamcall_err(fn, err, args);
-	pr_err("RCX 0x%016llx RDX 0x%016llx R08 0x%016llx\n",
+	pr_err("RCX %#016llx RDX %#016llx R08 %#016llx\n",
 			args->rcx, args->rdx, args->r8);
-	pr_err("R09 0x%016llx R10 0x%016llx R11 0x%016llx\n",
+	pr_err("R09 %#016llx R10 %#016llx R11 %#016llx\n",
 			args->r9, args->r10, args->r11);
 }

---

## [4] Chao Gao — 2025-09-30
*Subject: [PATCH v2 03/21] x86/virt/tdx: Move low level SEAMCALL helpers out of <asm/tdx.h>*

From: Kai Huang <kai.huang@intel.com>

TDX host core code implements three seamcall*() helpers to make SEAMCALL
to the TDX module.  Currently, they are implemented in <asm/tdx.h> and
are exposed to other kernel code which includes <asm/tdx.h>.

However, other than the TDX host core, seamcall*() are not expected to
be used by other kernel code directly.  For instance, for all SEAMCALLs
that are used by KVM, the TDX host core exports a wrapper function for
each of them.

Move seamcall*() and related code out of <asm/tdx.h> and make them only
visible to TDX host core.

Since TDX host core tdx.c is already very heavy, don't put low level
seamcall*() code there but to a new dedicated "seamcall.h".  Also,
currently tdx.c has seamcall_prerr*() helpers which additionally print
error message when calling seamcall*() fails.  Move them to "seamcall.h"
as well.  In such way all low level SEAMCALL helpers are in a dedicated
place, which is much more readable.

Signed-off-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Chao Gao <chao.gao@intel.com>
---
v2:
 - new
---
 arch/x86/include/asm/tdx.h       | 24 ----------
 arch/x86/virt/vmx/tdx/seamcall.h | 79 ++++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.c      | 46 +------------------
 3 files changed, 80 insertions(+), 69 deletions(-)
 create mode 100644 arch/x86/virt/vmx/tdx/seamcall.h

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index cbea169b5fa0..e872a411a359 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -97,31 +97,7 @@ static inline long tdx_kvm_hypercall(unsigned int nr, unsigned long p1,
 #endif /* CONFIG_INTEL_TDX_GUEST && CONFIG_KVM_GUEST */
 
 #ifdef CONFIG_INTEL_TDX_HOST
-u64 __seamcall(u64 fn, struct tdx_module_args *args);
-u64 __seamcall_ret(u64 fn, struct tdx_module_args *args);
-u64 __seamcall_saved_ret(u64 fn, struct tdx_module_args *args);
 void tdx_init(void);
-
-#include <asm/archrandom.h>
-
-typedef u64 (*sc_func_t)(u64 fn, struct tdx_module_args *args);
-
-static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
-			   struct tdx_module_args *args)
-{
-	int retry = RDRAND_RETRY_LOOPS;
-	u64 ret;
-
-	do {
-		ret = func(fn, args);
-	} while (ret == TDX_RND_NO_ENTROPY && --retry);
-
-	return ret;
-}
-
-#define seamcall(_fn, _args)		sc_retry(__seamcall, (_fn), (_args))
-#define seamcall_ret(_fn, _args)	sc_retry(__seamcall_ret, (_fn), (_args))
-#define seamcall_saved_ret(_fn, _args)	sc_retry(__seamcall_saved_ret, (_fn), (_args))
 int tdx_enable(void);
 const char *tdx_dump_mce_info(struct mce *m);
 const struct tdx_sys_info *tdx_get_sysinfo(void);
diff --git a/arch/x86/virt/vmx/tdx/seamcall.h b/arch/x86/virt/vmx/tdx/seamcall.h
new file mode 100644
index 000000000000..71b6ffddfa40
--- /dev/null
+++ b/arch/x86/virt/vmx/tdx/seamcall.h
@@ -0,0 +1,79 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+/* Copyright (C) 2025 Intel Corporation */
+#ifndef _X86_VIRT_SEAMCALL_H
+#define _X86_VIRT_SEAMCALL_H
+
+#include <linux/printk.h>
+#include <linux/types.h>
+#include <asm/archrandom.h>
+#include <asm/tdx.h>
+
+u64 __seamcall(u64 fn, struct tdx_module_args *args);
+u64 __seamcall_ret(u64 fn, struct tdx_module_args *args);
+u64 __seamcall_saved_ret(u64 fn, struct tdx_module_args *args);
+
+typedef u64 (*sc_func_t)(u64 fn, struct tdx_module_args *args);
+
+static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
+			   struct tdx_module_args *args)
+{
+	int retry = RDRAND_RETRY_LOOPS;
+	u64 ret;
+
+	do {
+		ret = func(fn, args);
+	} while (ret == TDX_RND_NO_ENTROPY && --retry);
+
+	return ret;
+}
+
+#define seamcall(_fn, _args)		sc_retry(__seamcall, (_fn), (_args))
+#define seamcall_ret(_fn, _args)	sc_retry(__seamcall_ret, (_fn), (_args))
+#define seamcall_saved_ret(_fn, _args)	sc_retry(__seamcall_saved_ret, (_fn), (_args))
+
+typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);
+
+static inline void seamcall_err(u64 fn, u64 err, struct tdx_module_args *args)
+{
+	pr_err("SEAMCALL (%llu) failed: %#016llx\n", fn, err);
+}
+
+static inline void seamcall_err_ret(u64 fn, u64 err,
+				    struct tdx_module_args *args)
+{
+	seamcall_err(fn, err, args);
+	pr_err("RCX %#016llx RDX %#016llx R08 %#016llx\n",
+			args->rcx, args->rdx, args->r8);
+	pr_err("R09 %#016llx R10 %#016llx R11 %#016llx\n",
+			args->r9, args->r10, args->r11);
+}
+
+static __always_inline int sc_retry_prerr(sc_func_t func,
+					  sc_err_func_t err_func,
+					  u64 fn, struct tdx_module_args *args)
+{
+	u64 sret = sc_retry(func, fn, args);
+
+	if (sret == TDX_SUCCESS)
+		return 0;
+
+	if (sret == TDX_SEAMCALL_VMFAILINVALID)
+		return -ENODEV;
+
+	if (sret == TDX_SEAMCALL_GP)
+		return -EOPNOTSUPP;
+
+	if (sret == TDX_SEAMCALL_UD)
+		return -EACCES;
+
+	err_func(fn, sret, args);
+	return -EIO;
+}
+
+#define seamcall_prerr(__fn, __args)						\
+	sc_retry_prerr(__seamcall, seamcall_err, (__fn), (__args))
+
+#define seamcall_prerr_ret(__fn, __args)					\
+	sc_retry_prerr(__seamcall_ret, seamcall_err_ret, (__fn), (__args))
+
+#endif
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index f429a5fdced2..b367bb1d94ed 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -38,6 +38,7 @@
 #include <asm/cpu_device_id.h>
 #include <asm/processor.h>
 #include <asm/mce.h>
+#include "seamcall.h"
 #include "tdx.h"
 
 static u32 tdx_global_keyid __ro_after_init;
@@ -58,51 +59,6 @@ static LIST_HEAD(tdx_memlist);
 
 static struct tdx_sys_info tdx_sysinfo;
 
-typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);
-
-static inline void seamcall_err(u64 fn, u64 err, struct tdx_module_args *args)
-{
-	pr_err("SEAMCALL (%llu) failed: %#016llx\n", fn, err);
-}
-
-static inline void seamcall_err_ret(u64 fn, u64 err,
-				    struct tdx_module_args *args)
-{
-	seamcall_err(fn, err, args);
-	pr_err("RCX %#016llx RDX %#016llx R08 %#016llx\n",
-			args->rcx, args->rdx, args->r8);
-	pr_err("R09 %#016llx R10 %#016llx R11 %#016llx\n",
-			args->r9, args->r10, args->r11);
-}
-
-static __always_inline int sc_retry_prerr(sc_func_t func,
-					  sc_err_func_t err_func,
-					  u64 fn, struct tdx_module_args *args)
-{
-	u64 sret = sc_retry(func, fn, args);
-
-	if (sret == TDX_SUCCESS)
-		return 0;
-
-	if (sret == TDX_SEAMCALL_VMFAILINVALID)
-		return -ENODEV;
-
-	if (sret == TDX_SEAMCALL_GP)
-		return -EOPNOTSUPP;
-
-	if (sret == TDX_SEAMCALL_UD)
-		return -EACCES;
-
-	err_func(fn, sret, args);
-	return -EIO;
-}
-
-#define seamcall_prerr(__fn, __args)						\
-	sc_retry_prerr(__seamcall, seamcall_err, (__fn), (__args))
-
-#define seamcall_prerr_ret(__fn, __args)					\
-	sc_retry_prerr(__seamcall_ret, seamcall_err_ret, (__fn), (__args))
-
 /*
  * Do the module global initialization once and return its result.
  * It can be done on any cpu.  It's always called with interrupts

---

## [5] Chao Gao — 2025-09-30
*Subject: [PATCH v2 04/21] x86/virt/tdx: Prepare to support P-SEAMLDR SEAMCALLs*

P-SEAMLDR is another component alongside the TDX module within the
protected SEAM range. P-SEAMLDR can update the TDX module at runtime.
Software can talk with P-SEAMLDR via SEAMCALLs with the bit 63 of RAX
(leaf number) set to 1 (a.k.a P-SEAMLDR SEAMCALLs).

P-SEAMLDR SEAMCALLs differ from SEAMCALLs of the TDX module in terms of
error codes and the handling of the current VMCS.

In preparation for adding support for P-SEAMLDR SEAMCALLs, do the two
following changes to SEAMCALL low-level helpers:

1) Tweak sc_retry() to retry on "lack of entropy" errors reported by
   P-SEAMLDR because it uses a different error code.

2) Add seamldr_err() to log error messages on P-SEAMLDR SEAMCALL failures.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
Add seamldr_prerr() as a macro to be consistent with existing code. If
maintainers would like to switch these to static inline functions then I
would be happy to add a new patch to convert existing macros to static
inline functions and build on that.

v2:
 - use a macro rather than an inline function for seamldr_err() for
   consistency.
---
 arch/x86/include/asm/tdx.h       |  5 +++++
 arch/x86/virt/vmx/tdx/seamcall.h | 29 ++++++++++++++++++++++++++++-
 2 files changed, 33 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index e872a411a359..7ad026618a23 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -32,6 +32,11 @@
 #define TDX_SUCCESS		0ULL
 #define TDX_RND_NO_ENTROPY	0x8000020300000000ULL
 
+/* P-SEAMLDR SEAMCALL leaf function error codes */
+#define SEAMLDR_RND_NO_ENTROPY	0x8000000000030001ULL
+
+#define SEAMLDR_SEAMCALL_MASK	_BITUL(63)
+
 #ifndef __ASSEMBLER__
 
 #include <uapi/asm/mce.h>
diff --git a/arch/x86/virt/vmx/tdx/seamcall.h b/arch/x86/virt/vmx/tdx/seamcall.h
index 71b6ffddfa40..3f462e58d68e 100644
--- a/arch/x86/virt/vmx/tdx/seamcall.h
+++ b/arch/x86/virt/vmx/tdx/seamcall.h
@@ -14,6 +14,19 @@ u64 __seamcall_saved_ret(u64 fn, struct tdx_module_args *args);
 
 typedef u64 (*sc_func_t)(u64 fn, struct tdx_module_args *args);
 
+static inline bool is_seamldr_call(u64 fn)
+{
+	return fn & SEAMLDR_SEAMCALL_MASK;
+}
+
+static inline bool sc_need_retry(u64 fn, u64 error_code)
+{
+	if (is_seamldr_call(fn))
+		return error_code == SEAMLDR_RND_NO_ENTROPY;
+	else
+		return error_code == TDX_RND_NO_ENTROPY;
+}
+
 static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
 			   struct tdx_module_args *args)
 {
@@ -22,7 +35,7 @@ static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
 
 	do {
 		ret = func(fn, args);
-	} while (ret == TDX_RND_NO_ENTROPY && --retry);
+	} while (sc_need_retry(fn, ret) && --retry);
 
 	return ret;
 }
@@ -48,6 +61,17 @@ static inline void seamcall_err_ret(u64 fn, u64 err,
 			args->r9, args->r10, args->r11);
 }
 
+static inline void seamldr_err(u64 fn, u64 err, struct tdx_module_args *args)
+{
+	/*
+	 * Get the actual leaf number. No need to print the bit used to
+	 * differentiate between P-SEAMLDR and TDX module as the "P-SEAMLDR"
+	 * string in the error message already provides that information.
+	 */
+	fn &= ~SEAMLDR_SEAMCALL_MASK;
+	pr_err("P-SEAMLDR (%lld) failed: 0x%016llx\n", fn, err);
+}
+
 static __always_inline int sc_retry_prerr(sc_func_t func,
 					  sc_err_func_t err_func,
 					  u64 fn, struct tdx_module_args *args)
@@ -76,4 +100,7 @@ static __always_inline int sc_retry_prerr(sc_func_t func,
 #define seamcall_prerr_ret(__fn, __args)					\
 	sc_retry_prerr(__seamcall_ret, seamcall_err_ret, (__fn), (__args))
 
+#define seamldr_prerr(__fn, __args)						\
+	sc_retry_prerr(__seamcall, seamldr_err, (__fn), (__args))
+
 #endif

---

## [6] Chao Gao — 2025-09-30
*Subject: [PATCH v2 05/21] x86/virt/seamldr: Introduce a wrapper for P-SEAMLDR SEAMCALLs*

Software needs to talk with P-SEAMLDR via P-SEAMLDR SEAMCALLs. So, add a
wrapper for P-SEAMLDR SEAMCALLs.

Save and restore the current VMCS using VMPTRST and VMPTRLD instructions
to avoid breaking KVM. Doing so is because P-SEAMLDR SEAMCALLs would
invalidate the current VMCS as documented in Intel® Trust Domain CPU
Architectural Extensions (May 2021 edition) Chapter 2.3 [1]:

  SEAMRET from the P-SEAMLDR clears the current VMCS structure pointed
  to by the current-VMCS pointer. A VMM that invokes the P-SEAMLDR using
  SEAMCALL must reload the current-VMCS, if required, using the VMPTRLD
  instruction.

Disable interrupts to prevent KVM code from interfering with P-SEAMLDR
SEAMCALLs. For example, if a vCPU is scheduled before the current VMCS is
restored, it may encounter an invalid current VMCS, causing its VMX
instruction to fail. Additionally, if KVM sends IPIs to invalidate a
current VMCS and the invalidation occurs right after the current VMCS is
saved, that VMCS will be reloaded after P-SEAMLDR SEAMCALLs, leading to
unexpected behavior.

NMIs are not a problem, as the only scenario where instructions relying on
the current-VMCS are used is during guest PMI handling in KVM. This occurs
immediately after VM exits with IRQ and NMI disabled, ensuring no
interference with P-SEAMLDR SEAMCALLs.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
Link: https://cdrdv2.intel.com/v1/dl/getContent/733582 # [1]
---
v2:
 - don't create a new, inferior framework to save/restore VMCS
 - use human-friendly language, just "current VMCS" rather than
   SDM term "current-VMCS pointer"
 - don't mix guard() with goto
---
 arch/x86/Kconfig                | 10 ++++++
 arch/x86/virt/vmx/tdx/Makefile  |  1 +
 arch/x86/virt/vmx/tdx/seamldr.c | 56 +++++++++++++++++++++++++++++++++
 3 files changed, 67 insertions(+)
 create mode 100644 arch/x86/virt/vmx/tdx/seamldr.c

diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
index 58d890fe2100..6b47383d2958 100644
--- a/arch/x86/Kconfig
+++ b/arch/x86/Kconfig
@@ -1905,6 +1905,16 @@ config INTEL_TDX_HOST
 
 	  If unsure, say N.
 
+config INTEL_TDX_MODULE_UPDATE
+	bool "Intel TDX module runtime update"
+	depends on TDX_HOST_SERVICES
+	help
+	  This enables the kernel to support TDX module runtime update. This
+	  allows the admin to update the TDX module to the same or any newer
+	  version without the need to terminate running TDX guests.
+
+	  If unsure, say N.
+
 config EFI
 	bool "EFI runtime service support"
 	depends on ACPI
diff --git a/arch/x86/virt/vmx/tdx/Makefile b/arch/x86/virt/vmx/tdx/Makefile
index 90da47eb85ee..26aea3531c36 100644
--- a/arch/x86/virt/vmx/tdx/Makefile
+++ b/arch/x86/virt/vmx/tdx/Makefile
@@ -1,2 +1,3 @@
 # SPDX-License-Identifier: GPL-2.0-only
 obj-y += seamcall.o tdx.o
+obj-$(CONFIG_INTEL_TDX_MODULE_UPDATE) += seamldr.o
diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
new file mode 100644
index 000000000000..b99d73f7bb08
--- /dev/null
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -0,0 +1,56 @@
+// SPDX-License-Identifier: GPL-2.0
+/*
+ * Copyright(c) 2025 Intel Corporation.
+ *
+ * Intel TDX module runtime update
+ */
+#define pr_fmt(fmt)	"seamldr: " fmt
+
+#include <linux/irqflags.h>
+#include <linux/types.h>
+
+#include "seamcall.h"
+
+static __maybe_unused int seamldr_call(u64 fn, struct tdx_module_args *args)
+{
+	unsigned long flags;
+	u64 vmcs;
+	int ret;
+
+	if (!is_seamldr_call(fn))
+		return -EINVAL;
+
+	/*
+	 * SEAMRET from P-SEAMLDR invalidates the current VMCS.  Save/restore
+	 * the VMCS across P-SEAMLDR SEAMCALLs to avoid clobbering KVM state.
+	 * Disable interrupts as KVM is allowed to do VMREAD/VMWRITE in IRQ
+	 * context (but not NMI context).
+	 */
+	local_irq_save(flags);
+
+	asm goto("1: vmptrst %0\n\t"
+		 _ASM_EXTABLE(1b, %l[error])
+		 : "=m" (vmcs) : : "cc" : error);
+
+	ret = seamldr_prerr(fn, args);
+
+	/*
+	 * Restore the current VMCS pointer.  VMPTSTR "returns" all ones if the
+	 * current VMCS is invalid.
+	 */
+	if (vmcs != -1ULL) {
+		asm goto("1: vmptrld %0\n\t"
+			 "jna %l[error]\n\t"
+			 _ASM_EXTABLE(1b, %l[error])
+			 : : "m" (vmcs) : "cc" : error);
+	}
+
+	local_irq_restore(flags);
+	return ret;
+
+error:
+	local_irq_restore(flags);
+
+	WARN_ONCE(1, "Failed to save/restore the current VMCS");
+	return -EIO;
+}

---

## [7] Chao Gao — 2025-09-30
*Subject: [PATCH v2 06/21] x86/virt/seamldr: Retrieve P-SEAMLDR information*

P-SEAMLDR returns its information e.g., version and supported features, in
response to the SEAMLDR.INFO SEAMCALL.

This information is useful for userspace. For example, the admin can decide
which TDX module versions are compatible with the P-SEAMLDR according to
the P-SEAMLDR version.

Add and export seamldr_get_info() which retrieves P-SEAMLDR information by
invoking SEAMLDR.INFO SEAMCALL in preparation for exposing P-SEAMLDR
version and other necessary information to userspace.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/include/asm/seamldr.h  | 27 +++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/seamldr.c | 17 ++++++++++++++++-
 2 files changed, 43 insertions(+), 1 deletion(-)
 create mode 100644 arch/x86/include/asm/seamldr.h

diff --git a/arch/x86/include/asm/seamldr.h b/arch/x86/include/asm/seamldr.h
new file mode 100644
index 000000000000..d1e9f6e16e8d
--- /dev/null
+++ b/arch/x86/include/asm/seamldr.h
@@ -0,0 +1,27 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+#ifndef _ASM_X86_SEAMLDR_H
+#define _ASM_X86_SEAMLDR_H
+
+#include <linux/types.h>
+
+struct seamldr_info {
+	u32	version;
+	u32	attributes;
+	u32	vendor_id;
+	u32	build_date;
+	u16	build_num;
+	u16	minor_version;
+	u16	major_version;
+	u16	update_version;
+	u8	reserved0[4];
+	u32	num_remaining_updates;
+	u8	reserved1[224];
+} __packed;
+
+#ifdef CONFIG_INTEL_TDX_MODULE_UPDATE
+const struct seamldr_info *seamldr_get_info(void);
+#else
+static inline const struct seamldr_info *seamldr_get_info(void) { return NULL; }
+#endif
+
+#endif
diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index b99d73f7bb08..08c2e3fe6071 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -9,9 +9,16 @@
 #include <linux/irqflags.h>
 #include <linux/types.h>
 
+#include <asm/seamldr.h>
+
 #include "seamcall.h"
 
-static __maybe_unused int seamldr_call(u64 fn, struct tdx_module_args *args)
+/* P-SEAMLDR SEAMCALL leaf function */
+#define P_SEAMLDR_INFO			0x8000000000000000
+
+static struct seamldr_info seamldr_info __aligned(256);
+
+static inline int seamldr_call(u64 fn, struct tdx_module_args *args)
 {
 	unsigned long flags;
 	u64 vmcs;
@@ -54,3 +61,11 @@ static __maybe_unused int seamldr_call(u64 fn, struct tdx_module_args *args)
 	WARN_ONCE(1, "Failed to save/restore the current VMCS");
 	return -EIO;
 }
+
+const struct seamldr_info *seamldr_get_info(void)
+{
+	struct tdx_module_args args = { .rcx = __pa(&seamldr_info) };
+
+	return seamldr_call(P_SEAMLDR_INFO, &args) ? NULL : &seamldr_info;
+}
+EXPORT_SYMBOL_GPL_FOR_MODULES(seamldr_get_info, "tdx-host");

---

## [8] Chao Gao — 2025-09-30
*Subject: [PATCH v2 07/21] coco/tdx-host: Expose P-SEAMLDR information via sysfs*

TDX Module updates require userspace to select the appropriate module
to load. Expose necessary information to facilitate this decision. Two
values are needed:

- P-SEAMLDR version: for compatibility checks between TDX Module and
		     P-SEAMLDR
- num_remaining_updates: indicates how many updates can be performed

Expose them as tdx-host device attributes.

Note that P-SEAMLDR sysfs nodes are hidden when INTEL_TDX_MODULE_UPDATE
isn't enabled or when P-SEAMLDR isn't loaded by BIOS, both of which
cause seamldr_get_info() to return NULL.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 .../ABI/testing/sysfs-devices-faux-tdx-host   | 25 ++++++++
 drivers/virt/coco/tdx-host/tdx-host.c         | 63 ++++++++++++++++++-
 2 files changed, 87 insertions(+), 1 deletion(-)

diff --git a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
index 18d4a4a71b80..13c1f4f9909c 100644
--- a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
+++ b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
@@ -4,3 +4,28 @@ Description:	(RO) Report the version of the loaded TDX module. The TDX module
 		version is formatted as x.y.z, where "x" is the major version,
 		"y" is the minor version and "z" is the update version. Versions
 		are used for bug reporting, TD-Preserving updates and etc.
+
+What:		/sys/devices/faux/tdx_host/seamldr/version
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) Report the version of the loaded SEAM loader. The SEAM
+		loader version is formatted as x.y.z, where "x" is the major
+		version, "y" is the minor version and "z" is the update version.
+		Versions are used for bug reporting and compatibility check.
+
+What:		/sys/devices/faux/tdx_host/seamldr/num_remaining_updates
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) Report the number of remaining updates that can be performed.
+		The CPU keeps track of TCB versions for each TDX Module that
+		has been loaded. Since this tracking database has finite
+		capacity, there's a maximum number of module updates that can
+		be performed.
+
+		After each successful update, the number reduces by one. Once it
+		reaches zero, further updates will fail until next reboot. The
+		number is always zero if P-SEAMLDR doesn't support updates.
+
+		See Intel® Trust Domain Extensions - SEAM Loader (SEAMLDR)
+		Interface Specification Chapter 3.3 "SEAMLDR_INFO" and Chapter
+		4.2 "SEAMLDR.INSTALL" for more information. The documentation is
+		available at:
+		https://cdrdv2-public.intel.com/739045/intel-tdx-seamldr-interface-specification.pdf
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 968a19f4e01a..42570c5b221b 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -11,6 +11,7 @@
 #include <linux/sysfs.h>
 #include <linux/device/faux.h>
 #include <asm/cpu_device_id.h>
+#include <asm/seamldr.h>
 #include <asm/tdx.h>
 #include <asm/tdx_global_metadata.h>
 
@@ -43,7 +44,67 @@ static struct attribute *tdx_host_attrs[] = {
 	&dev_attr_version.attr,
 	NULL,
 };
-ATTRIBUTE_GROUPS(tdx_host);
+
+struct attribute_group tdx_host_group = {
+	.attrs = tdx_host_attrs,
+};
+
+static ssize_t seamldr_version_show(struct device *dev, struct device_attribute *attr,
+				    char *buf)
+{
+	const struct seamldr_info *info = seamldr_get_info();
+
+	if (!info)
+		return -ENXIO;
+
+	return sysfs_emit(buf, "%u.%u.%u\n", info->major_version,
+					     info->minor_version,
+					     info->update_version);
+}
+
+static ssize_t num_remaining_updates_show(struct device *dev,
+					  struct device_attribute *attr,
+					  char *buf)
+{
+	const struct seamldr_info *info = seamldr_get_info();
+
+	if (!info)
+		return -ENXIO;
+
+	return sysfs_emit(buf, "%u\n", info->num_remaining_updates);
+}
+
+/*
+ * Open-code DEVICE_ATTR_RO to specify a different 'show' function for
+ * P-SEAMLDR version as version_show() is used for the TDX Module version.
+ */
+static struct device_attribute dev_attr_seamldr_version =
+	__ATTR(version, 0444, seamldr_version_show, NULL);
+static DEVICE_ATTR_RO(num_remaining_updates);
+
+static struct attribute *seamldr_attrs[] = {
+	&dev_attr_seamldr_version.attr,
+	&dev_attr_num_remaining_updates.attr,
+	NULL,
+};
+
+static umode_t seamldr_group_is_visible(struct kobject *kobj,
+					struct attribute *attr, int n)
+{
+	return seamldr_get_info() ? attr->mode : 0;
+}
+
+static struct attribute_group seamldr_group = {
+	.name = "seamldr",
+	.attrs = seamldr_attrs,
+	.is_visible = seamldr_group_is_visible,
+};
+
+static const struct attribute_group *tdx_host_groups[] = {
+	&tdx_host_group,
+	&seamldr_group,
+	NULL,
+};
 
 static int __init tdx_host_init(void)
 {

---

## [9] Chao Gao — 2025-09-30
*Subject: [PATCH v2 08/21] coco/tdx-host: Implement FW_UPLOAD sysfs ABI for TDX Module updates*

The firmware upload framework provides a standard mechanism for firmware
updates by allowing device drivers to expose sysfs interfaces for
user-initiated updates.

Register with this framework to expose sysfs interfaces for TDX Module
updates and implement operations to process data blobs supplied by
userspace.

Note that:
1. P-SEAMLDR processes the entire update at once rather than
   chunk-by-chunk, so .write() is called only once per update; so the
   offset should be always 0.
2. TDX Module Updates complete synchronously within .write(), meaning
   .poll_complete() is only called after successful updates and therefore
   always returns success

Why fw_upload instead of request_firmware()?
============================================
The explicit file selection capabilities of fw_upload is preferred over
the implicit file selection of request_firmware() for the following
reasons:

a. Intel distributes all versions of the TDX Module, allowing admins to
load any version rather than always defaulting to the latest. This
flexibility is necessary because future extensions may require reverting to
a previous version to clear fatal errors.

b. Some module version series are platform-specific. For example, the 1.5.x
series is for certain platform generations, while the 2.0.x series is
intended for others.

c. The update policy for TDX Module updates is non-linear at times. The
latest TDX Module may not be compatible. For example, TDX Module 1.5.x
may be updated to 1.5.y but not to 1.5.y+1. This policy is documented
separately in a file released along with each TDX Module release.

So, the default policy of "request_firmware()" of "always load latest", is
not suitable for TDX. Userspace needs to deploy a more sophisticated policy
check (e.g., latest may not be compatible), and there is potential
operator choice to consider.

Just have userspace pick rather than add kernel mechanism to change the
default policy of request_firmware().

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/Kconfig                      |   2 +
 arch/x86/include/asm/seamldr.h        |   2 +
 arch/x86/include/asm/tdx.h            |   5 ++
 arch/x86/virt/vmx/tdx/seamldr.c       |   7 ++
 drivers/virt/coco/tdx-host/tdx-host.c | 122 +++++++++++++++++++++++++-
 5 files changed, 137 insertions(+), 1 deletion(-)

diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
index 6b47383d2958..2bf4bb3dfe71 100644
--- a/arch/x86/Kconfig
+++ b/arch/x86/Kconfig
@@ -1908,6 +1908,8 @@ config INTEL_TDX_HOST
 config INTEL_TDX_MODULE_UPDATE
 	bool "Intel TDX module runtime update"
 	depends on TDX_HOST_SERVICES
+	select FW_LOADER
+	select FW_UPLOAD
 	help
 	  This enables the kernel to support TDX module runtime update. This
 	  allows the admin to update the TDX module to the same or any newer
diff --git a/arch/x86/include/asm/seamldr.h b/arch/x86/include/asm/seamldr.h
index d1e9f6e16e8d..692bde5e9bb4 100644
--- a/arch/x86/include/asm/seamldr.h
+++ b/arch/x86/include/asm/seamldr.h
@@ -20,8 +20,10 @@ struct seamldr_info {
 
 #ifdef CONFIG_INTEL_TDX_MODULE_UPDATE
 const struct seamldr_info *seamldr_get_info(void);
+int seamldr_install_module(const u8 *data, u32 size);
 #else
 static inline const struct seamldr_info *seamldr_get_info(void) { return NULL; }
+static inline int seamldr_install_module(const u8 *data, u32 size) { return -EOPNOTSUPP; }
 #endif
 
 #endif
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 7ad026618a23..2422904079a3 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -107,6 +107,11 @@ int tdx_enable(void);
 const char *tdx_dump_mce_info(struct mce *m);
 const struct tdx_sys_info *tdx_get_sysinfo(void);
 
+static inline bool tdx_supports_runtime_update(const struct tdx_sys_info *sysinfo)
+{
+	return false; /* To be enabled when kernel is ready */
+}
+
 int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 08c2e3fe6071..69c059194c61 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -69,3 +69,10 @@ const struct seamldr_info *seamldr_get_info(void)
 	return seamldr_call(P_SEAMLDR_INFO, &args) ? NULL : &seamldr_info;
 }
 EXPORT_SYMBOL_GPL_FOR_MODULES(seamldr_get_info, "tdx-host");
+
+int seamldr_install_module(const u8 *data, u32 size)
+{
+	/* TODO: Update TDX Module here */
+	return 0;
+}
+EXPORT_SYMBOL_GPL_FOR_MODULES(seamldr_install_module, "tdx-host");
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 42570c5b221b..418e90797689 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -10,6 +10,7 @@
 #include <linux/mod_devicetable.h>
 #include <linux/sysfs.h>
 #include <linux/device/faux.h>
+#include <linux/firmware.h>
 #include <asm/cpu_device_id.h>
 #include <asm/seamldr.h>
 #include <asm/tdx.h>
@@ -21,6 +22,13 @@ static const struct x86_cpu_id tdx_host_ids[] = {
 };
 MODULE_DEVICE_TABLE(x86cpu, tdx_host_ids);
 
+struct tdx_fw_upload_status {
+	bool cancel_request;
+};
+
+struct fw_upload *tdx_fwl;
+static struct tdx_fw_upload_status tdx_fw_upload_status;
+
 static struct faux_device *fdev;
 
 static ssize_t version_show(struct device *dev, struct device_attribute *attr,
@@ -106,6 +114,118 @@ static const struct attribute_group *tdx_host_groups[] = {
 	NULL,
 };
 
+static enum fw_upload_err tdx_fw_prepare(struct fw_upload *fwl,
+					 const u8 *data, u32 size)
+{
+	struct tdx_fw_upload_status *status = fwl->dd_handle;
+
+	if (status->cancel_request) {
+		status->cancel_request = false;
+		return FW_UPLOAD_ERR_CANCELED;
+	}
+
+	return FW_UPLOAD_ERR_NONE;
+}
+
+static enum fw_upload_err tdx_fw_write(struct fw_upload *fwl, const u8 *data,
+				       u32 offset, u32 size, u32 *written)
+{
+	struct tdx_fw_upload_status *status = fwl->dd_handle;
+
+	if (status->cancel_request) {
+		status->cancel_request = false;
+		return FW_UPLOAD_ERR_CANCELED;
+	}
+
+	/*
+	 * tdx_fw_write() always processes all data on the first call with
+	 * offset == 0. Since it never returns partial success (it either
+	 * succeeds completely or fails), there is no subsequent call with
+	 * non-zero offsets.
+	 */
+	WARN_ON_ONCE(offset);
+	if (seamldr_install_module(data, size))
+		return FW_UPLOAD_ERR_FW_INVALID;
+
+	*written = size;
+	return FW_UPLOAD_ERR_NONE;
+}
+
+static enum fw_upload_err tdx_fw_poll_complete(struct fw_upload *fwl)
+{
+	/*
+	 * TDX Module updates are completed in the previous phase
+	 * (tdx_fw_write()). If any error occurred, the previous phase
+	 * would return an error code to abort the update process. In
+	 * other words, reaching this point means the update succeeded.
+	 */
+	return FW_UPLOAD_ERR_NONE;
+}
+
+static void tdx_fw_cancel(struct fw_upload *fwl)
+{
+	struct tdx_fw_upload_status *status = fwl->dd_handle;
+
+	status->cancel_request = true;
+}
+
+static const struct fw_upload_ops tdx_fw_ops = {
+	.prepare = tdx_fw_prepare,
+	.write = tdx_fw_write,
+	.poll_complete = tdx_fw_poll_complete,
+	.cancel = tdx_fw_cancel,
+};
+
+static int seamldr_init(struct device *dev)
+{
+	const struct seamldr_info *seamldr_info = seamldr_get_info();
+	const struct tdx_sys_info *tdx_sysinfo = tdx_get_sysinfo();
+	int ret;
+
+	if (!tdx_sysinfo || !seamldr_info)
+		return -ENXIO;
+
+	if (!tdx_supports_runtime_update(tdx_sysinfo)) {
+		pr_info("Current TDX Module cannot be updated. Consider BIOS updates\n");
+		return -EOPNOTSUPP;
+	}
+
+	if (!seamldr_info->num_remaining_updates) {
+		pr_info("P-SEAMLDR doesn't support TDX Module updates\n");
+		return -EOPNOTSUPP;
+	}
+
+	tdx_fwl = firmware_upload_register(THIS_MODULE, dev, "seamldr_upload",
+					   &tdx_fw_ops, &tdx_fw_upload_status);
+	ret = PTR_ERR_OR_ZERO(tdx_fwl);
+	if (ret)
+		pr_err("failed to register module uploader %d\n", ret);
+
+	return ret;
+}
+
+static void seamldr_deinit(void)
+{
+	if (tdx_fwl)
+		firmware_upload_unregister(tdx_fwl);
+}
+
+static int tdx_host_probe(struct faux_device *fdev)
+{
+	/* Only support TDX Module updates now. More TDX features could be added here. */
+	return seamldr_init(&fdev->dev);
+}
+
+static void tdx_host_remove(struct faux_device *fdev)
+{
+	seamldr_deinit();
+}
+
+static struct faux_device_ops tdx_host_ops = {
+	.probe		= tdx_host_probe,
+	.remove		= tdx_host_remove,
+};
+
 static int __init tdx_host_init(void)
 {
 	int r;
@@ -118,7 +238,7 @@ static int __init tdx_host_init(void)
 	if (r)
 		return r;
 
-	fdev = faux_device_create_with_groups(KBUILD_MODNAME, NULL, NULL, tdx_host_groups);
+	fdev = faux_device_create_with_groups(KBUILD_MODNAME, NULL, &tdx_host_ops, tdx_host_groups);
 	if (!fdev)
 		return -ENODEV;

---

## [10] Chao Gao — 2025-09-30
*Subject: [PATCH v2 09/21] x86/virt/seamldr: Block TDX Module updates if any CPU is offline*

P-SEAMLDR requires every CPU to call the SEAMLDR.INSTALL SEAMCALL during
updates.  So, every CPU should be online.

Check if all CPUs are online and abort the update if any CPU is offline at
the very beginning. Without this check, P-SEAMLDR will report failure at a
later phase where the old TDX module is gone and TDs have to be killed.

Signed-off-by: Chao Gao <chao.gao@intel.com>
---
 arch/x86/virt/vmx/tdx/seamldr.c | 8 ++++++++
 1 file changed, 8 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 69c059194c61..b9e025d0f0bc 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -6,6 +6,8 @@
  */
 #define pr_fmt(fmt)	"seamldr: " fmt
 
+#include <linux/cpuhplock.h>
+#include <linux/cpumask.h>
 #include <linux/irqflags.h>
 #include <linux/types.h>
 
@@ -72,6 +74,12 @@ EXPORT_SYMBOL_GPL_FOR_MODULES(seamldr_get_info, "tdx-host");
 
 int seamldr_install_module(const u8 *data, u32 size)
 {
+	guard(cpus_read_lock)();
+	if (!cpumask_equal(cpu_online_mask, cpu_present_mask)) {
+		pr_err("Cannot update TDX module if any CPU is offline\n");
+		return -EBUSY;
+	}
+
 	/* TODO: Update TDX Module here */
 	return 0;
 }

---

## [11] Chao Gao — 2025-09-30
*Subject: [PATCH v2 10/21] x86/virt/seamldr: Verify availability of slots for TDX Module updates*

The CPU keeps track of TCB versions for each TDX Module that has been
loaded. Since this tracking database has finite capacity, there's a maximum
number of module updates that can be performed. After each successful
update, the number reduces by one. Once it reaches zero, further updates
will fail until next reboot.

Before updating the TDX Module, ensure that the limit on TDX Module updates
has not been exceeded to prevent update failures in a later phase where TDs
have to be killed.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/virt/vmx/tdx/seamldr.c | 8 ++++++++
 1 file changed, 8 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index b9e025d0f0bc..9f7d96ca8b2f 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -74,6 +74,14 @@ EXPORT_SYMBOL_GPL_FOR_MODULES(seamldr_get_info, "tdx-host");
 
 int seamldr_install_module(const u8 *data, u32 size)
 {
+	const struct seamldr_info *info = seamldr_get_info();
+
+	if (!info)
+		return -EIO;
+
+	if (!info->num_remaining_updates)
+		return -ENOSPC;
+
 	guard(cpus_read_lock)();
 	if (!cpumask_equal(cpu_online_mask, cpu_present_mask)) {
 		pr_err("Cannot update TDX module if any CPU is offline\n");

---

## [12] Chao Gao — 2025-09-30
*Subject: [PATCH v2 11/21] x86/virt/seamldr: Allocate and populate a module update request*

A module update request is a struct used to describe information about
the TDX module to install. It is part of the P-SEAMLDR <-> kernel ABI
and is accepted by the SEAMLDR_INSTALL SEAMCALL.

The request includes pointers to pages that contain the module binary, a
pointer to a sigstruct file, and an update scenario.

Define the request struct according to the P-SEAMLDR spec [1], and parse
the bitstream from userspace to populate that struct for later module
updates.

Note that the bitstream format is specified in [2]. It consists of a
header, a sigstruct, a module binary, and reserved fields for future
extensions. The header includes fields like a simple checksum and a
signature for error detection.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
Link: https://cdrdv2.intel.com/v1/dl/getContent/733584 # [1]
Link: https://github.com/intel/tdx-module-binaries/blob/main/blob_structure.txt # [2]
---
v2:
 - Add a high level description of the bitstream in changelog
 - Document where the bitstream format is defined in comments
 - Add checks for the version and reserved fields in tdx_blob
---
 arch/x86/virt/vmx/tdx/seamldr.c | 155 ++++++++++++++++++++++++++++++++
 1 file changed, 155 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 9f7d96ca8b2f..00a01acc15fd 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -6,9 +6,12 @@
  */
 #define pr_fmt(fmt)	"seamldr: " fmt
 
+#include <linux/cleanup.h>
 #include <linux/cpuhplock.h>
 #include <linux/cpumask.h>
 #include <linux/irqflags.h>
+#include <linux/mm.h>
+#include <linux/slab.h>
 #include <linux/types.h>
 
 #include <asm/seamldr.h>
@@ -18,6 +21,26 @@
 /* P-SEAMLDR SEAMCALL leaf function */
 #define P_SEAMLDR_INFO			0x8000000000000000
 
+/* P-SEAMLDR can accept up to 496 4KB pages for TDX module binary */
+#define SEAMLDR_MAX_NR_MODULE_4KB_PAGES	496
+
+/* scenario field in struct seamldr_params */
+#define SEAMLDR_SCENARIO_UPDATE		1
+
+/*
+ * Passed to P-SEAMLDR to describe information about the TDX module to install.
+ * Defined in "SEAM Loader (SEAMLDR) Interface Specification", Revision
+ * 343755-003, Section 3.2.
+ */
+struct seamldr_params {
+	u32	version;
+	u32	scenario;
+	u64	sigstruct_pa;
+	u8	reserved[104];
+	u64	num_module_pages;
+	u64	mod_pages_pa_list[SEAMLDR_MAX_NR_MODULE_4KB_PAGES];
+} __packed;
+
 static struct seamldr_info seamldr_info __aligned(256);
 
 static inline int seamldr_call(u64 fn, struct tdx_module_args *args)
@@ -72,6 +95,133 @@ const struct seamldr_info *seamldr_get_info(void)
 }
 EXPORT_SYMBOL_GPL_FOR_MODULES(seamldr_get_info, "tdx-host");
 
+static void free_seamldr_params(struct seamldr_params *params)
+{
+	free_page((unsigned long)params);
+}
+
+/* Allocate and populate a seamldr_params */
+static struct seamldr_params *alloc_seamldr_params(const void *module, int module_size,
+						   const void *sig, int sig_size)
+{
+	struct seamldr_params *params;
+	const u8 *ptr;
+	int i;
+
+	BUILD_BUG_ON(sizeof(struct seamldr_params) != SZ_4K);
+	if (module_size > SEAMLDR_MAX_NR_MODULE_4KB_PAGES * SZ_4K)
+		return ERR_PTR(-EINVAL);
+
+	if (!IS_ALIGNED(module_size, SZ_4K) || !IS_ALIGNED(sig_size, SZ_4K) ||
+	    !IS_ALIGNED((unsigned long)module, SZ_4K) ||
+	    !IS_ALIGNED((unsigned long)sig, SZ_4K))
+		return ERR_PTR(-EINVAL);
+
+	/* seamldr_params accepts one 4KB-page for sigstruct */
+	if (sig_size != SZ_4K)
+		return ERR_PTR(-EINVAL);
+
+	params = (struct seamldr_params *)get_zeroed_page(GFP_KERNEL);
+	if (!params)
+		return ERR_PTR(-ENOMEM);
+
+	params->scenario = SEAMLDR_SCENARIO_UPDATE;
+	params->sigstruct_pa = (vmalloc_to_pfn(sig) << PAGE_SHIFT) +
+			       ((unsigned long)sig & ~PAGE_MASK);
+	params->num_module_pages = module_size / SZ_4K;
+
+	ptr = module;
+	for (i = 0; i < params->num_module_pages; i++) {
+		params->mod_pages_pa_list[i] = (vmalloc_to_pfn(ptr) << PAGE_SHIFT) +
+					       ((unsigned long)ptr & ~PAGE_MASK);
+		ptr += SZ_4K;
+	}
+
+	return params;
+}
+
+/*
+ * Intel TDX Module blob. Its format is defined at:
+ * https://github.com/intel/tdx-module-binaries/blob/main/blob_structure.txt
+ */
+struct tdx_blob {
+	u16	version;
+	u16	checksum;
+	u32	offset_of_module;
+	u8	signature[8];
+	u32	len;
+	u32	resv1;
+	u64	resv2[509];
+	u8	data[];
+} __packed;
+
+/*
+ * Verify that the checksum of the entire blob is zero. The checksum is
+ * calculated by summing up all 16-bit words, with carry bits dropped.
+ */
+static bool verify_checksum(const struct tdx_blob *blob)
+{
+	u32 size = blob->len;
+	u16 checksum = 0;
+	const u16 *p;
+	int i;
+
+	/* Handle the last byte if the size is odd */
+	if (size % 2) {
+		checksum += *((const u8 *)blob + size - 1);
+		size--;
+	}
+
+	p = (const u16 *)blob;
+	for (i = 0; i < size; i += 2) {
+		checksum += *p;
+		p++;
+	}
+
+	return !checksum;
+}
+
+static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
+{
+	const struct tdx_blob *blob = (const void *)data;
+	int module_size, sig_size;
+	const void *sig, *module;
+
+	if (blob->version != 0x100) {
+		pr_err("unsupported blob version: %u\n", blob->version);
+		return ERR_PTR(-EINVAL);
+	}
+
+	if (blob->resv1 || memchr_inv(blob->resv2, 0, sizeof(blob->resv2))) {
+		pr_err("non-zero reserved fields\n");
+		return ERR_PTR(-EINVAL);
+	}
+
+	/* Split the given blob into a sigstruct and a module */
+	sig		= blob->data;
+	sig_size	= blob->offset_of_module - sizeof(struct tdx_blob);
+	module		= data + blob->offset_of_module;
+	module_size	= size - blob->offset_of_module;
+
+	if (sig_size <= 0 || module_size <= 0 || blob->len != size)
+		return ERR_PTR(-EINVAL);
+
+	if (memcmp(blob->signature, "TDX-BLOB", 8)) {
+		pr_err("invalid signature\n");
+		return ERR_PTR(-EINVAL);
+	}
+
+	if (!verify_checksum(blob)) {
+		pr_err("invalid checksum\n");
+		return ERR_PTR(-EINVAL);
+	}
+
+	return alloc_seamldr_params(module, module_size, sig, sig_size);
+}
+
+DEFINE_FREE(free_seamldr_params, struct seamldr_params *,
+	    if (!IS_ERR_OR_NULL(_T)) free_seamldr_params(_T))
+
 int seamldr_install_module(const u8 *data, u32 size)
 {
 	const struct seamldr_info *info = seamldr_get_info();
@@ -82,6 +232,11 @@ int seamldr_install_module(const u8 *data, u32 size)
 	if (!info->num_remaining_updates)
 		return -ENOSPC;
 
+	struct seamldr_params *params __free(free_seamldr_params) =
+						init_seamldr_params(data, size);
+	if (IS_ERR(params))
+		return PTR_ERR(params);
+
 	guard(cpus_read_lock)();
 	if (!cpumask_equal(cpu_online_mask, cpu_present_mask)) {
 		pr_err("Cannot update TDX module if any CPU is offline\n");

---

## [13] Chao Gao — 2025-09-30
*Subject: [PATCH v2 12/21] x86/virt/seamldr: Introduce skeleton for TDX Module updates*

The P-SEAMLDR requires that no TDX Module SEAMCALLs are invoked during a
runtime TDX Module update.

But currently, TDX Module SEAMCALLs are invoked in various contexts and in
parallel across CPUs. Additionally, considering the need to force all vCPUs
out of guest mode, no single lock primitive, except for stop_machine(), can
meet this requirement.

Perform TDX Module updates within stop_machine() as it achieves the
P-SEAMLDR requirements and is an existing well understood mechanism.

TDX Module updates consist of several steps: shutting down the old
module, installing the new module, and initializing the new one and etc.
Some steps must be executed on a single CPU, others serially across all
CPUs, and some can be performed concurrently on all CPUs and there are
ordering requirements between steps. So, all CPUs need to perform the work
in a step-locked manner.

In preparation for adding concrete steps for TDX Module updates,
establish the framework by mimicking multi_cpu_stop(). Specifically, use a
global state machine to control the work done on each CPU and require all
CPUs to acknowledge completion before proceeding to the next stage.

Potential alternative to stop_machine()
=======================================
An alternative approach is to lock all KVM entry points and kick all
vCPUs.  Here, KVM entry points refer to KVM VM/vCPU ioctl entry points,
implemented in KVM common code (virt/kvm). Adding a locking mechanism
there would affect all architectures. And to lock only TDX vCPUs, new
logic would be needed to identify TDX vCPUs, which the common code
currently lacks. This would add significant complexity and maintenance
overhead for a TDX-specific use case.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
v2:
 - refine the changlog to follow context-problem-solution structure
 - move alternative discussions at the end of the changelog
 - add a comment about state machine transition
 - Move rcu_momentary_eqs() call to the else branch.
---
 arch/x86/virt/vmx/tdx/seamldr.c | 71 ++++++++++++++++++++++++++++++++-
 1 file changed, 70 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 00a01acc15fd..b074630d42e3 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -11,7 +11,9 @@
 #include <linux/cpumask.h>
 #include <linux/irqflags.h>
 #include <linux/mm.h>
+#include <linux/nmi.h>
 #include <linux/slab.h>
+#include <linux/stop_machine.h>
 #include <linux/types.h>
 
 #include <asm/seamldr.h>
@@ -219,12 +221,75 @@ static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
 	return alloc_seamldr_params(module, module_size, sig, sig_size);
 }
 
+/*
+ * During a TDX Module update, all CPUs start from TDP_START and progress
+ * to TDP_DONE. Each state is associated with certain work. For some
+ * states, just one CPU needs to perform the work, while other CPUs just
+ * wait during those states.
+ */
+enum tdp_state {
+	TDP_START,
+	TDP_DONE,
+};
+
+static struct {
+	enum tdp_state state;
+	atomic_t thread_ack;
+} tdp_data;
+
+static void set_target_state(enum tdp_state state)
+{
+	/* Reset ack counter. */
+	atomic_set(&tdp_data.thread_ack, num_online_cpus());
+	/* Ensure thread_ack is updated before the new state */
+	smp_wmb();
+	WRITE_ONCE(tdp_data.state, state);
+}
+
+/* Last one to ack a state moves to the next state. */
+static void ack_state(void)
+{
+	if (atomic_dec_and_test(&tdp_data.thread_ack))
+		set_target_state(tdp_data.state + 1);
+}
+
+/*
+ * See multi_cpu_stop() from where this multi-cpu state-machine was
+ * adopted, and the rationale for touch_nmi_watchdog()
+ */
+static int do_seamldr_install_module(void *params)
+{
+	enum tdp_state newstate, curstate = TDP_START;
+	int ret = 0;
+
+	do {
+		/* Chill out and ensure we re-read tdp_data. */
+		cpu_relax();
+		newstate = READ_ONCE(tdp_data.state);
+
+		if (newstate != curstate) {
+			curstate = newstate;
+			switch (curstate) {
+			default:
+				break;
+			}
+			ack_state();
+		} else {
+			touch_nmi_watchdog();
+			rcu_momentary_eqs();
+		}
+	} while (curstate != TDP_DONE);
+
+	return ret;
+}
+
 DEFINE_FREE(free_seamldr_params, struct seamldr_params *,
 	    if (!IS_ERR_OR_NULL(_T)) free_seamldr_params(_T))
 
 int seamldr_install_module(const u8 *data, u32 size)
 {
 	const struct seamldr_info *info = seamldr_get_info();
+	int ret;
 
 	if (!info)
 		return -EIO;
@@ -243,7 +308,11 @@ int seamldr_install_module(const u8 *data, u32 size)
 		return -EBUSY;
 	}
 
-	/* TODO: Update TDX Module here */
+	set_target_state(TDP_START + 1);
+	ret = stop_machine_cpuslocked(do_seamldr_install_module, params, cpu_online_mask);
+	if (ret)
+		return ret;
+
 	return 0;
 }
 EXPORT_SYMBOL_GPL_FOR_MODULES(seamldr_install_module, "tdx-host");

---

## [14] Chao Gao — 2025-09-30
*Subject: [PATCH v2 13/21] x86/virt/seamldr: Abort updates if errors occurred midway*

The TDX Module update process has multiple stages, each of which may
encounter failures.

The current state machine of updates proceeds to the next stage
regardless of errors. But continuing updates when errors occur midway
is pointless.

Add support of transitioning directly to the final stage on errors,
effectively aborting the update and skipping all remaining stages.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/virt/vmx/tdx/seamldr.c | 17 +++++++++++++++--
 1 file changed, 15 insertions(+), 2 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index b074630d42e3..fca558b90f72 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -235,6 +235,7 @@ enum tdp_state {
 static struct {
 	enum tdp_state state;
 	atomic_t thread_ack;
+	atomic_t failed;
 } tdp_data;
 
 static void set_target_state(enum tdp_state state)
@@ -249,8 +250,16 @@ static void set_target_state(enum tdp_state state)
 /* Last one to ack a state moves to the next state. */
 static void ack_state(void)
 {
-	if (atomic_dec_and_test(&tdp_data.thread_ack))
-		set_target_state(tdp_data.state + 1);
+	if (atomic_dec_and_test(&tdp_data.thread_ack)) {
+		/*
+		 * If an error occurred, abort the update by skipping to
+		 * the final state
+		 */
+		if (atomic_read(&tdp_data.failed))
+			set_target_state(TDP_DONE);
+		else
+			set_target_state(tdp_data.state + 1);
+	}
 }
 
 /*
@@ -273,6 +282,9 @@ static int do_seamldr_install_module(void *params)
 			default:
 				break;
 			}
+
+			if (ret)
+				atomic_inc(&tdp_data.failed);
 			ack_state();
 		} else {
 			touch_nmi_watchdog();
@@ -308,6 +320,7 @@ int seamldr_install_module(const u8 *data, u32 size)
 		return -EBUSY;
 	}
 
+	atomic_set(&tdp_data.failed, 0);
 	set_target_state(TDP_START + 1);
 	ret = stop_machine_cpuslocked(do_seamldr_install_module, params, cpu_online_mask);
 	if (ret)

---

## [15] Chao Gao — 2025-09-30
*Subject: [PATCH v2 14/21] x86/virt/seamldr: Shut down the current TDX module*

TDX Module updates request shutting down the existing TDX module.
During this shutdown, the module generates hand-off data, which captures
the module's states essential for preserving running TDs. The new TDX
Module can utilize this hand-off data to establish its states.

Invoke the TDH_SYS_SHUTDOWN SEAMCALL on one CPU to perform the shutdown.
This SEAMCALL requires a hand-off module version. Use the module's own
hand-off version, as it is the highest version the module can produce and
is more likely to be compatible with new modules as new modules likely have
higher hand-off version.

Generate changes to tdx_global_metadata.{hc} by following the
instructions detailed in [1], after adding the following section to the
tdx.py script:

    "handoff": [
       "MODULE_HV",
    ],

Manually add a check in get_tdx_sys_info_handoff() to guard reading the
"module_hv" field with TDX Module update support as otherwise the field
doesn't exist.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
Link: https://lore.kernel.org/kvm/20250226181453.2311849-12-pbonzini@redhat.com/ # [1]
---
v2:
 - add a comment about how handoff version is chosen.
 - remove the first !ret in get_tdx_sys_info_handoff() as we edited the
   auto-generated code anyway
 - remove !! when determining whether a CPU is the primary one
 - remove unnecessary if-break nesting in TDP_SHUTDOWN
---
 arch/x86/include/asm/tdx_global_metadata.h  |  5 +++++
 arch/x86/virt/vmx/tdx/seamldr.c             | 10 ++++++++++
 arch/x86/virt/vmx/tdx/tdx.c                 | 16 ++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h                 |  3 +++
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c | 13 +++++++++++++
 5 files changed, 47 insertions(+)

diff --git a/arch/x86/include/asm/tdx_global_metadata.h b/arch/x86/include/asm/tdx_global_metadata.h
index 40689c8dc67e..8a9ebd895e70 100644
--- a/arch/x86/include/asm/tdx_global_metadata.h
+++ b/arch/x86/include/asm/tdx_global_metadata.h
@@ -40,12 +40,17 @@ struct tdx_sys_info_td_conf {
 	u64 cpuid_config_values[128][2];
 };
 
+struct tdx_sys_info_handoff {
+	u16 module_hv;
+};
+
 struct tdx_sys_info {
 	struct tdx_sys_info_version version;
 	struct tdx_sys_info_features features;
 	struct tdx_sys_info_tdmr tdmr;
 	struct tdx_sys_info_td_ctrl td_ctrl;
 	struct tdx_sys_info_td_conf td_conf;
+	struct tdx_sys_info_handoff handoff;
 };
 
 #endif
diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index fca558b90f72..b9daf11e1064 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -19,6 +19,7 @@
 #include <asm/seamldr.h>
 
 #include "seamcall.h"
+#include "tdx.h"
 
 /* P-SEAMLDR SEAMCALL leaf function */
 #define P_SEAMLDR_INFO			0x8000000000000000
@@ -229,6 +230,7 @@ static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
  */
 enum tdp_state {
 	TDP_START,
+	TDP_SHUTDOWN,
 	TDP_DONE,
 };
 
@@ -269,8 +271,12 @@ static void ack_state(void)
 static int do_seamldr_install_module(void *params)
 {
 	enum tdp_state newstate, curstate = TDP_START;
+	int cpu = smp_processor_id();
+	bool primary;
 	int ret = 0;
 
+	primary = cpumask_first(cpu_online_mask) == cpu;
+
 	do {
 		/* Chill out and ensure we re-read tdp_data. */
 		cpu_relax();
@@ -279,6 +285,10 @@ static int do_seamldr_install_module(void *params)
 		if (newstate != curstate) {
 			curstate = newstate;
 			switch (curstate) {
+			case TDP_SHUTDOWN:
+				if (primary)
+					ret = tdx_module_shutdown();
+				break;
 			default:
 				break;
 			}
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index b367bb1d94ed..89b51e270274 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1191,6 +1191,22 @@ int tdx_enable(void)
 }
 EXPORT_SYMBOL_GPL(tdx_enable);
 
+int tdx_module_shutdown(void)
+{
+	struct tdx_module_args args = {};
+
+	/*
+	 * Shut down the TDX Module and prepare handoff data for the next
+	 * TDX Module. This SEAMCALL requires a hand-off module version.
+	 * Use the module's own hand-off version, as it is the highest
+	 * version the module can produce and is more likely to be
+	 * compatible with new modules as new modules likely have higher
+	 * hand-off version.
+	 */
+	args.rcx = tdx_sysinfo.handoff.module_hv;
+	return seamcall_prerr(TDH_SYS_SHUTDOWN, &args);
+}
+
 static bool is_pamt_page(unsigned long phys)
 {
 	struct tdmr_info_list *tdmr_list = &tdx_tdmr_list;
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 82bb82be8567..1c4da9540ae0 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -46,6 +46,7 @@
 #define TDH_PHYMEM_PAGE_WBINVD		41
 #define TDH_VP_WR			43
 #define TDH_SYS_CONFIG			45
+#define TDH_SYS_SHUTDOWN		52
 
 /*
  * SEAMCALL leaf:
@@ -118,4 +119,6 @@ struct tdmr_info_list {
 	int max_tdmrs;	/* How many 'tdmr_info's are allocated */
 };
 
+int tdx_module_shutdown(void);
+
 #endif
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index 0454124803f3..3fdd5cbc21d8 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -100,6 +100,18 @@ static int get_tdx_sys_info_td_conf(struct tdx_sys_info_td_conf *sysinfo_td_conf
 	return ret;
 }
 
+static int get_tdx_sys_info_handoff(struct tdx_sys_info_handoff *sysinfo_handoff)
+{
+	int ret = 0;
+	u64 val;
+
+	if (tdx_supports_runtime_update(&tdx_sysinfo) &&
+	    !(ret = read_sys_metadata_field(0x8900000100000000, &val)))
+		sysinfo_handoff->module_hv = val;
+
+	return ret;
+}
+
 static int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 {
 	int ret = 0;
@@ -109,6 +121,7 @@ static int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 	ret = ret ?: get_tdx_sys_info_tdmr(&sysinfo->tdmr);
 	ret = ret ?: get_tdx_sys_info_td_ctrl(&sysinfo->td_ctrl);
 	ret = ret ?: get_tdx_sys_info_td_conf(&sysinfo->td_conf);
+	ret = ret ?: get_tdx_sys_info_handoff(&sysinfo->handoff);
 
 	return ret;
 }

---

## [16] Chao Gao — 2025-09-30
*Subject: [PATCH v2 15/21] x86/virt/tdx: Reset software states after TDX module shutdown*

The TDX module requires a one-time global initialization (TDH.SYS.INIT) and
per-CPU initialization (TDH.SYS.LP.INIT) before use. These initializations
are guarded by software flags to prevent repetition.

After TDX module updates, the new TDX module requires the same global and
per-CPU initializations, but the existing software flags prevent
re-initialization.

Reset all software flags guarding the initialization flows to allow the
global and per-CPU initializations to be triggered again after updates.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 18 +++++++++++++++---
 1 file changed, 15 insertions(+), 3 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 89b51e270274..7019a149ec4b 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -54,6 +54,9 @@ static struct tdmr_info_list tdx_tdmr_list;
 static enum tdx_module_status_t tdx_module_status;
 static DEFINE_MUTEX(tdx_module_lock);
 
+static bool sysinit_done;
+static int sysinit_ret;
+
 /* All TDX-usable memory regions.  Protected by mem_hotplug_lock. */
 static LIST_HEAD(tdx_memlist);
 
@@ -68,8 +71,6 @@ static int try_init_module_global(void)
 {
 	struct tdx_module_args args = {};
 	static DEFINE_RAW_SPINLOCK(sysinit_lock);
-	static bool sysinit_done;
-	static int sysinit_ret;
 
 	lockdep_assert_irqs_disabled();
 
@@ -1194,6 +1195,7 @@ EXPORT_SYMBOL_GPL(tdx_enable);
 int tdx_module_shutdown(void)
 {
 	struct tdx_module_args args = {};
+	int ret, cpu;
 
 	/*
 	 * Shut down the TDX Module and prepare handoff data for the next
@@ -1204,7 +1206,17 @@ int tdx_module_shutdown(void)
 	 * hand-off version.
 	 */
 	args.rcx = tdx_sysinfo.handoff.module_hv;
-	return seamcall_prerr(TDH_SYS_SHUTDOWN, &args);
+	ret = seamcall_prerr(TDH_SYS_SHUTDOWN, &args);
+	if (ret)
+		return ret;
+
+	tdx_module_status = TDX_MODULE_UNINITIALIZED;
+	sysinit_done = false;
+	sysinit_ret = 0;
+
+	for_each_online_cpu(cpu)
+		per_cpu(tdx_lp_initialized, cpu) = false;
+	return 0;
 }
 
 static bool is_pamt_page(unsigned long phys)

---

## [17] Chao Gao — 2025-09-30
*Subject: [PATCH v2 16/21] x86/virt/seamldr: Handle TDX Module update failures*

Failures encountered after a successful module shutdown are unrecoverable,
e.g., there is no way to restore the old TDX Module.

All subsequent SEAMCALLs to the TDX Module will fail and so TDs have to be
killed.

Report failures through sysfs attributes and log a message to clarify that
SEAMCALL errors are expected in this situation.

To prevent TDX Module update failures, admins are encouraged to use the
user space tool [1] that will perform compatibility and integrity checks
that guarantee TDX Module update success (unless the system's update limit
is exceeded, but the kernel will prevent an update attempt in this case).

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
Link: https://github.com/intel/tdx-module-binaries/blob/main/version_select_and_load.py # [1]
---
 arch/x86/virt/vmx/tdx/seamldr.c       | 15 ++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx.c           |  6 ++++++
 arch/x86/virt/vmx/tdx/tdx.h           |  1 +
 drivers/virt/coco/tdx-host/tdx-host.c |  4 ++++
 4 files changed, 25 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index b9daf11e1064..a5aff04a85b9 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -264,6 +264,14 @@ static void ack_state(void)
 	}
 }
 
+static void print_update_failure_message(void)
+{
+	static atomic_t printed = ATOMIC_INIT(0);
+
+	if (atomic_inc_return(&printed) == 1)
+		pr_err("update failed, SEAMCALLs will report failure until TDs killed\n");
+}
+
 /*
  * See multi_cpu_stop() from where this multi-cpu state-machine was
  * adopted, and the rationale for touch_nmi_watchdog()
@@ -293,8 +301,13 @@ static int do_seamldr_install_module(void *params)
 				break;
 			}
 
-			if (ret)
+			if (ret) {
 				atomic_inc(&tdp_data.failed);
+				if (curstate > TDP_SHUTDOWN) {
+					tdx_module_set_error();
+					print_update_failure_message();
+				}
+			}
 			ack_state();
 		} else {
 			touch_nmi_watchdog();
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 7019a149ec4b..26357be18fa9 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1219,6 +1219,12 @@ int tdx_module_shutdown(void)
 	return 0;
 }
 
+void tdx_module_set_error(void)
+{
+	/* Called from stop_machine(). no need to hold tdx_module_lock */
+	tdx_module_status = TDX_MODULE_ERROR;
+}
+
 static bool is_pamt_page(unsigned long phys)
 {
 	struct tdmr_info_list *tdmr_list = &tdx_tdmr_list;
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 1c4da9540ae0..5b9a2d63808c 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -120,5 +120,6 @@ struct tdmr_info_list {
 };
 
 int tdx_module_shutdown(void);
+void tdx_module_set_error(void);
 
 #endif
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 418e90797689..47c5ba115993 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -37,6 +37,10 @@ static ssize_t version_show(struct device *dev, struct device_attribute *attr,
 	const struct tdx_sys_info *tdx_sysinfo = tdx_get_sysinfo();
 	const struct tdx_sys_info_version *ver;
 
+	/*
+	 * Inform userspace that the TDX module isn't in a usable state,
+	 * possibly due to a failed update.
+	 */
 	if (!tdx_sysinfo)
 		return -ENXIO;

---

## [18] Chao Gao — 2025-09-30
*Subject: [PATCH v2 17/21] x86/virt/seamldr: Install a new TDX Module*

After shutting down the running TDX module, the next step is to install the
new TDX Module supplied by userspace.

P-SEAMLDR provides the SEAMLDR.INSTALL SEAMCALL for that. The SEAMCALL
accepts the seamldr_params struct and should be called serially on all
CPUs.

Invoke the SEAMLDR.INSTALL SEAMCALL serially on all CPUs and add a new
spinlock to enforce serialization.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/virt/vmx/tdx/seamldr.c | 9 +++++++++
 1 file changed, 9 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index a5aff04a85b9..1bb4ae5ccb0a 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -13,6 +13,7 @@
 #include <linux/mm.h>
 #include <linux/nmi.h>
 #include <linux/slab.h>
+#include <linux/spinlock.h>
 #include <linux/stop_machine.h>
 #include <linux/types.h>
 
@@ -23,6 +24,7 @@
 
 /* P-SEAMLDR SEAMCALL leaf function */
 #define P_SEAMLDR_INFO			0x8000000000000000
+#define P_SEAMLDR_INSTALL		0x8000000000000001
 
 /* P-SEAMLDR can accept up to 496 4KB pages for TDX module binary */
 #define SEAMLDR_MAX_NR_MODULE_4KB_PAGES	496
@@ -45,6 +47,7 @@ struct seamldr_params {
 } __packed;
 
 static struct seamldr_info seamldr_info __aligned(256);
+static DEFINE_RAW_SPINLOCK(seamldr_lock);
 
 static inline int seamldr_call(u64 fn, struct tdx_module_args *args)
 {
@@ -231,6 +234,7 @@ static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
 enum tdp_state {
 	TDP_START,
 	TDP_SHUTDOWN,
+	TDP_CPU_INSTALL,
 	TDP_DONE,
 };
 
@@ -278,6 +282,7 @@ static void print_update_failure_message(void)
  */
 static int do_seamldr_install_module(void *params)
 {
+	struct tdx_module_args args = { .rcx = __pa(params) };
 	enum tdp_state newstate, curstate = TDP_START;
 	int cpu = smp_processor_id();
 	bool primary;
@@ -297,6 +302,10 @@ static int do_seamldr_install_module(void *params)
 				if (primary)
 					ret = tdx_module_shutdown();
 				break;
+			case TDP_CPU_INSTALL:
+				scoped_guard(raw_spinlock, &seamldr_lock)
+					ret = seamldr_call(P_SEAMLDR_INSTALL, &args);
+				break;
 			default:
 				break;
 			}

---

## [19] Chao Gao — 2025-09-30
*Subject: [PATCH v2 18/21] x86/virt/seamldr: Do TDX per-CPU initialization after updates*

After installing the new TDX module, each CPU should be initialized
again to make the CPU ready to run any other SEAMCALLs. So, call
tdx_cpu_enable() on all CPUs.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/virt/vmx/tdx/seamldr.c | 4 ++++
 arch/x86/virt/vmx/tdx/tdx.c     | 2 +-
 arch/x86/virt/vmx/tdx/tdx.h     | 1 +
 3 files changed, 6 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 1bb4ae5ccb0a..75bb650d8a16 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -235,6 +235,7 @@ enum tdp_state {
 	TDP_START,
 	TDP_SHUTDOWN,
 	TDP_CPU_INSTALL,
+	TDP_CPU_INIT,
 	TDP_DONE,
 };
 
@@ -306,6 +307,9 @@ static int do_seamldr_install_module(void *params)
 				scoped_guard(raw_spinlock, &seamldr_lock)
 					ret = seamldr_call(P_SEAMLDR_INSTALL, &args);
 				break;
+			case TDP_CPU_INIT:
+				ret = tdx_cpu_enable();
+				break;
 			default:
 				break;
 			}
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 26357be18fa9..280c2a9f3211 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -106,7 +106,7 @@ static int try_init_module_global(void)
  *
  * Return 0 on success, otherwise errors.
  */
-static int tdx_cpu_enable(void)
+int tdx_cpu_enable(void)
 {
 	struct tdx_module_args args = {};
 	int ret;
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 5b9a2d63808c..b903e479e46a 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -121,5 +121,6 @@ struct tdmr_info_list {
 
 int tdx_module_shutdown(void);
 void tdx_module_set_error(void);
+int tdx_cpu_enable(void);
 
 #endif

---

## [20] Chao Gao — 2025-09-30
*Subject: [PATCH v2 19/21] x86/virt/tdx: Establish contexts for the new TDX Module*

After being installed, the new TDX Module shouldn't re-configure the
global HKID, TDMRs or PAMTs. Instead, to preserve running TDs, it should
import the handoff data from the old module to establish all necessary
contexts.

Once the import is done, the TDX Module update is complete, and the new
module is ready to handle requests from the VMM and guests.

Call the TDH.SYS.UPDATE SEAMCALL to import the handoff data from the old
module.

Note that the location and the format of handoff data is defined by the
TDX Module. The new module knows where to get the handoff data and how to
parse it. The kernel doesn't need to provide its location, format etc.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/virt/vmx/tdx/seamldr.c |  5 +++++
 arch/x86/virt/vmx/tdx/tdx.c     | 16 ++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h     |  2 ++
 3 files changed, 23 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 75bb650d8a16..a8ca6966beac 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -236,6 +236,7 @@ enum tdp_state {
 	TDP_SHUTDOWN,
 	TDP_CPU_INSTALL,
 	TDP_CPU_INIT,
+	TDP_RUN_UPDATE,
 	TDP_DONE,
 };
 
@@ -310,6 +311,10 @@ static int do_seamldr_install_module(void *params)
 			case TDP_CPU_INIT:
 				ret = tdx_cpu_enable();
 				break;
+			case TDP_RUN_UPDATE:
+				if (primary)
+					ret = tdx_module_run_update();
+				break;
 			default:
 				break;
 			}
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 280c2a9f3211..7613fd16a0ce 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1225,6 +1225,22 @@ void tdx_module_set_error(void)
 	tdx_module_status = TDX_MODULE_ERROR;
 }
 
+int tdx_module_run_update(void)
+{
+	struct tdx_module_args args = {};
+	int ret;
+
+	ret = seamcall(TDH_SYS_UPDATE, &args);
+	if (ret) {
+		tdx_module_status = TDX_MODULE_ERROR;
+		pr_info("module update failed: %d\n", ret);
+		return ret;
+	}
+
+	tdx_module_status = TDX_MODULE_INITIALIZED;
+	return 0;
+}
+
 static bool is_pamt_page(unsigned long phys)
 {
 	struct tdmr_info_list *tdmr_list = &tdx_tdmr_list;
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index b903e479e46a..983c01c6949a 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -47,6 +47,7 @@
 #define TDH_VP_WR			43
 #define TDH_SYS_CONFIG			45
 #define TDH_SYS_SHUTDOWN		52
+#define TDH_SYS_UPDATE		53
 
 /*
  * SEAMCALL leaf:
@@ -122,5 +123,6 @@ struct tdmr_info_list {
 int tdx_module_shutdown(void);
 void tdx_module_set_error(void);
 int tdx_cpu_enable(void);
+int tdx_module_run_update(void);
 
 #endif

---

## [21] Chao Gao — 2025-09-30
*Subject: [PATCH v2 20/21] x86/virt/tdx: Update tdx_sysinfo and check features post-update*

tdx_sysinfo contains all metadata of the active TDX module, including
versions, supported features, and TDMR/TDCS/TDVPS information. These
elements may change over updates. Blindly refreshing the entire tdx_sysinfo
could disrupt running software, as it may subtly rely on the previous state
unless proven otherwise.

Adopt a conservative approach, like microcode updates, by only refreshing
version information that does not affect functionality, while ignoring
all other changes. This is acceptable as new modules are required to
maintain backward compatibility.

Any updates to metadata beyond versions should be justified and reviewed on
a case-by-case basis.

Note that preallocating a tdx_sys_info buffer before updates is to avoid
having to handle -ENOMEM when updating tdx_sysinfo after a successful
update.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
v2:
 - don't add a separate function for version and feature checks. Do them
   directly in tdx_module_post_update()
 - add a comment about preallocating a tdx_sys_info buffer in
   seamldr_install_module().
---
 arch/x86/virt/vmx/tdx/seamldr.c | 12 ++++++++-
 arch/x86/virt/vmx/tdx/tdx.c     | 47 +++++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h     |  2 ++
 3 files changed, 60 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index a8ca6966beac..a72f6b0b27e9 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -350,6 +350,16 @@ int seamldr_install_module(const u8 *data, u32 size)
 	if (!info->num_remaining_updates)
 		return -ENOSPC;
 
+	/*
+	 * Preallocating a tdx_sys_info buffer before updates is to avoid having to
+	 * handle -ENOMEM when updating tdx_sysinfo after a successful update.
+	 */
+	struct tdx_sys_info *sysinfo __free(kfree) = kzalloc(sizeof(*sysinfo),
+							     GFP_KERNEL);
+	if (!sysinfo)
+		return -ENOMEM;
+
+
 	struct seamldr_params *params __free(free_seamldr_params) =
 						init_seamldr_params(data, size);
 	if (IS_ERR(params))
@@ -367,6 +377,6 @@ int seamldr_install_module(const u8 *data, u32 size)
 	if (ret)
 		return ret;
 
-	return 0;
+	return tdx_module_post_update(sysinfo);
 }
 EXPORT_SYMBOL_GPL_FOR_MODULES(seamldr_install_module, "tdx-host");
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 7613fd16a0ce..128e6ffba736 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1241,6 +1241,53 @@ int tdx_module_run_update(void)
 	return 0;
 }
 
+/*
+ * Update tdx_sysinfo and check if any TDX module features changed after
+ * updates
+ */
+int tdx_module_post_update(struct tdx_sys_info *info)
+{
+	struct tdx_sys_info_version *cur, *new;
+	int ret;
+
+	/* Shouldn't fail as the update has succeeded */
+	ret = get_tdx_sys_info(info);
+	if (ret) {
+		WARN_ONCE(1, "version retrieval failed after update, replace TDX Module\n");
+		return ret;
+	}
+
+	guard(mutex)(&tdx_module_lock);
+
+	cur = &tdx_sysinfo.version;
+	new = &info->version;
+	pr_info("version %u.%u.%02u -> %u.%u.%02u\n", cur->major_version,
+						      cur->minor_version,
+						      cur->update_version,
+						      new->major_version,
+						      new->minor_version,
+						      new->update_version);
+
+	/*
+	 * Blindly refreshing the entire tdx_sysinfo could disrupt running
+	 * software, as it may subtly rely on the previous state unless
+	 * proven otherwise.
+	 *
+	 * Only refresh version information (including handoff version)
+	 * that does not affect functionality, and ignore all other
+	 * changes.
+	 */
+	tdx_sysinfo.version	= info->version;
+	tdx_sysinfo.handoff	= info->handoff;
+
+	if (!memcmp(&tdx_sysinfo, info, sizeof(*info)))
+		return 0;
+
+	pr_info("TDX module features have changed after updates, but might not take effect.\n");
+	pr_info("Please consider a potential BIOS update.\n");
+	return 0;
+}
+
 static bool is_pamt_page(unsigned long phys)
 {
 	struct tdmr_info_list *tdmr_list = &tdx_tdmr_list;
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 983c01c6949a..ca76126880ee 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -3,6 +3,7 @@
 #define _X86_VIRT_TDX_H
 
 #include <linux/bits.h>
+#include <asm/tdx_global_metadata.h>
 
 /*
  * This file contains both macros and data structures defined by the TDX
@@ -124,5 +125,6 @@ int tdx_module_shutdown(void);
 void tdx_module_set_error(void);
 int tdx_cpu_enable(void);
 int tdx_module_run_update(void);
+int tdx_module_post_update(struct tdx_sys_info *info);
 
 #endif

---

## [22] Chao Gao — 2025-09-30
*Subject: [PATCH v2 21/21] x86/virt/tdx: Enable TDX Module runtime updates*

All pieces of TDX Module runtime updates are in place. Enable it if it
is supported.

Signed-off-by: Chao Gao <chao.gao@intel.com>
---
 arch/x86/include/asm/tdx.h  | 6 +++++-
 arch/x86/virt/vmx/tdx/tdx.h | 3 ---
 2 files changed, 5 insertions(+), 4 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 2422904079a3..94aa1237fef4 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -32,6 +32,10 @@
 #define TDX_SUCCESS		0ULL
 #define TDX_RND_NO_ENTROPY	0x8000020300000000ULL
 
+/* Bit definitions of TDX_FEATURES0 metadata field */
+#define TDX_FEATURES0_TD_PRESERVING	BIT(1)
+#define TDX_FEATURES0_NO_RBP_MOD	BIT(18)
+
 /* P-SEAMLDR SEAMCALL leaf function error codes */
 #define SEAMLDR_RND_NO_ENTROPY	0x8000000000030001ULL
 
@@ -109,7 +113,7 @@ const struct tdx_sys_info *tdx_get_sysinfo(void);
 
 static inline bool tdx_supports_runtime_update(const struct tdx_sys_info *sysinfo)
 {
-	return false; /* To be enabled when kernel is ready */
+	return sysinfo->features.tdx_features0 & TDX_FEATURES0_TD_PRESERVING;
 }
 
 int tdx_guest_keyid_alloc(void);
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index ca76126880ee..1965adb63f1f 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -87,9 +87,6 @@ struct tdmr_info {
 	DECLARE_FLEX_ARRAY(struct tdmr_reserved_area, reserved_areas);
 } __packed __aligned(TDMR_INFO_ALIGNMENT);
 
-/* Bit definitions of TDX_FEATURES0 metadata field */
-#define TDX_FEATURES0_NO_RBP_MOD	BIT(18)
-
 /*
  * Do not put any hardware-defined TDX structure representations below
  * this comment!

---

## [23] Vishal Annapurve — 2025-10-14
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Tue, Sep 30, 2025 at 7:54 PM Chao Gao <chao.gao@intel.com> wrote:
>
> === TDX Module Distribution Model ===

[2] mentions about a limitation of doing runtime TDX module update:

"Performing TD Preserving during a TD Build operation might result in
a corrupted TD hash in the TD attestation report. Until fixed in a
future Intel TDX module update, a host VMM can avoid the problem by
not conducting a TD Preserving Update while TD Build operation is in
progress."

Do you know if this issue is fixed already? If so, what version of TDX
module fixes this issue?

> vendors can package these modules and distribute them. Administrators
> install the package and use the tool to select the appropriate TDX Module

---

## [24] Reshetova, Elena — 2025-10-15
*Subject: RE: [PATCH v2 00/21] Runtime TDX Module update support*

> On Tue, Sep 30, 2025 at 7:54 PM Chao Gao <chao.gao@intel.com> wrote:
> >

It is not fixed, because the limitation comes from the internal crypto context
maintained by the IPP crypto library. Different versions of TDX module can
use different versions of IPP library (as any good SW that aims to take latest and
greatest version of its dependencies) and IPP library (as any library) does not
provide any compatibility guarantees on its runtime data structures.
So, the problem can show up if the old and new TDX module (prior and post
TD preserving update) use different IPP versions and IPP happened to change
internal data structure format in between these versions. There is nothing
TDX module can really do in this case. 
But the situation can be avoided fully, if TD preserving update is not conducted
during the TD build time. 

Best Regards,
Elena.

---

## [25] Vishal Annapurve — 2025-10-15
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Wed, Oct 15, 2025 at 1:54 AM Reshetova, Elena
<elena.reshetova@intel.com> wrote:
>
>

Few questions:
1) How is TD build time defined in this scenario?
2) IIUC, this series doesn't add any protection of TDX module update
against ongoing TD build steps, is that supposed to be the
responsibility of userspace VMM?
    - If so, what prevents the series from building in this protection
in the kernel?

>
> Best Regards,

---

## [26] Dave Hansen — 2025-10-15
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On 10/15/25 01:54, Reshetova, Elena wrote:
...
>> "Performing TD Preserving during a TD Build operation might result in
>> a corrupted TD hash in the TD attestation report. Until fixed in a

Does the TD attestation report contain information about the TDX module?
Isn't that information in flux during a module update?

...
> But the situation can be avoided fully, if TD preserving update is not conducted
> during the TD build time. 

Sure, and the TDX module itself could guarantee this as well as much as
the kernel could. It could decline to allow module updates during TD
builds, or error out the TD build if it collides with an update.

---

## [27] Reshetova, Elena — 2025-10-16
*Subject: RE: [PATCH v2 00/21] Runtime TDX Module update support*

> -----Original Message-----
> From: Hansen, Dave <dave.hansen@intel.com>

Yes, of course. 

> Isn't that information in flux during a module update?

If you mean that the attestation after a TD preserving update will show a different
TDX module, it depends if SVN has changed (if yes, then it will be visible).
But I fail to see how this relates to the problem we are discussing. 
Here, the attestation of a TD that was build during the TD preserving update
will fail, because the end crypto hash would not match. 
It would look like a random failure to CSP, because VMM did everything correctly
(build a TD), but TD's attestation will fail.
Not a very good situation to debug. 


> 
> ...

TDX module has a functionality to decline going into SHUTDOWN state
(pre-requisite for TD preserving update) if TD build or any problematic
operation is in progress. It requires VMM to opt-in into this feature.

---

## [28] Reshetova, Elena — 2025-10-16
*Subject: RE: [PATCH v2 00/21] Runtime TDX Module update support*

> -----Original Message-----
> From: Vishal Annapurve <vannapurve@google.com>

TD build that has started by TDH.MNG.INIT will end must end by TDH.MR.FINALIZE
or by tearing down the TD; otherwise the TDX module will still count it as in-progress.

Best Regards,
Elena.

---

## [29] Vishal Annapurve — 2025-10-16
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Wed, Oct 15, 2025 at 11:46 PM Reshetova, Elena
<elena.reshetova@intel.com> wrote:
>
> > ...

Is this opt-in enabled as part of this series? If not, what is the
mechanism to enable this opt-in?

---

## [30] Reshetova, Elena — 2025-10-17
*Subject: RE: [PATCH v2 00/21] Runtime TDX Module update support*

> -----Original Message-----
> From: Vishal Annapurve <vannapurve@google.com>

For the information about how it works on TDX module side, 
please consult the latest ABI spec, definition of TDH.SYS.SHUTDOWN leaf,
page 321:
https://cdrdv2.intel.com/v1/dl/getContent/733579

---

## [31] Vishal Annapurve — 2025-10-17
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Fri, Oct 17, 2025 at 3:08 AM Reshetova, Elena
<elena.reshetova@intel.com> wrote:
>
>

Thanks Elena. Should the patch [1] from this series be modified to
handle the TDX module shutdown as per:
"If supported by the TDX Module, the host VMM can set the
AVOID_COMPAT_SENSITIVE flag to request the TDX Module to fail
TDH.SYS.UPDATE if any of the TDs are currently in a state that is
impacted by the update-sensitive cases"

The documentation below doesn't make sense to me:
"The compatibility checks done by TDH.SYS.UPDATE do not include the
following cases:
* If any TD was initialized by an older TDX Module that did enumerate
TDX_FEATURES0.UPDATE_COMPATIBLITY as 1, TDH.SYS.SHUTDOWN does not
check for a TD build in progress condition for that TD.
* If any TD migration session is in progress, it was initialized by an
older TDX Module that did enumerate TDX_FEATURES0.UPDATE_COMPATIBLITY
as 1"

Was it supposed to say below?
"If any TD was initialized by an older TDX Module that did enumerate
TDX_FEATURES0.UPDATE_COMPATIBLITY as 0, TDH.SYS.SHUTDOWN does not
check for a TD build in progress condition for that TD"

[1] https://lore.kernel.org/all/20251001025442.427697-15-chao.gao@intel.com/

---

## [32] Reshetova, Elena — 2025-10-21
*Subject: RE: [PATCH v2 00/21] Runtime TDX Module update support*

> -----Original Message-----
> From: Vishal Annapurve <vannapurve@google.com>

Yes, the spec error, thank you for catching this. Will be fixed. 
The correct text should say:

" If any TD was initialized by an older TDX Module that did *not* enumerate
TDX_FEATURES0.UPDATE_COMPATIBLITY as 1, TDH.SYS.SHUTDOWN does
not check for a TD build in progress condition for that TD.
If any TD migration session is in progress, and it was initialized by an older
TDX Module that did *not* enumerate TDX_FEATURES0.UPDATE_COMPATIBLITY as 1,
TDH.SYS.SHUTDOWN does not check for an interrupted TD migration function
condition for that TD."

Best Regards,
Elena.

---

## [33] Chao Gao — 2025-10-22
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Fri, Oct 17, 2025 at 05:01:55PM -0700, Vishal Annapurve wrote:
>On Fri, Oct 17, 2025 at 3:08 AM Reshetova, Elena
><elena.reshetova@intel.com> wrote:

Hi Vishal,

I will fix this issue in the next version.

The plan is to opt in post-update compatibility detection in the TDX
Module. If incompatibilities are found, the module will return errors to
any TD build or migration operations that were initiated prior to the
updates. Please refer to the TDH.SYS.UPDATE leaf definition in the ABI
spec above for details.

I prefer this approach because:

a. it guarantees forward progress. In contrast, failing updates would
   require admins to retry TDX Module updates, and no progress would be
   made unless they can successfully avoid race conditions between TDX
   module updates and TD build/migration operations. However, if such race
   conditions could be reliably prevented, this issue wouldn't require a
   fix in the first place.

b. it eliminates false alarms that could occur with the "block update"
   approach. Under the "block update" approach, updates would be rejected
   whenever TD build operations are running, regardless of whether the new
   module is actually compatible (e.g., when using the same crypto library as
   the current module). In contrast, the post-update detection approach only
   fails TD build or migration operations when genuine incompatibilities
   exist.

---

## [34] Vishal Annapurve — 2025-10-22
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Wed, Oct 22, 2025 at 12:15 AM Chao Gao <chao.gao@intel.com> wrote:
>
> On Fri, Oct 17, 2025 at 05:01:55PM -0700, Vishal Annapurve wrote:

TD build operations are much more frequent than TDX module update
operations. Retrying TD build operation will need additional KVM and
userspace VMM changes IIUC (assuming TD build process needs to be
restarted from the scratch). IMO, it would be simpler to handle TDX
module update failures by retrying.

Admin logic to update TDX modules can be designed to either retry
failed TDX module updates or to be more robust, adds some
synchronization with VM creation attempts on the host. i.e. I think
it's fine to punt this problem of ensuring the forward progress to
user-space admin logic on the host.

>
> b. it eliminates false alarms that could occur with the "block update"

---

## [35] Vishal Annapurve — 2025-10-23
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Wed, Oct 22, 2025 at 8:42 AM Vishal Annapurve <vannapurve@google.com> wrote:
>
> On Wed, Oct 22, 2025 at 12:15 AM Chao Gao <chao.gao@intel.com> wrote:

Discussed offline with Erdem Aktas on this. From Google's perspective
"Avoid updates during updatesensitive times" seems a better option as
I mentioned above.

To avoid having to choose which policy to enforce in kernel, a better
way could be to:
* Allow user space opt-in for "Avoid updates during updatesensitive times" AND
* Allow user space opt-in for "Detect incompatibility after update" as well OR
* Keep "Detect incompatibility after update" enabled by default based
on the appetite for avoiding silent corruption scenarios.

>
> >

---

## [36] Dave Hansen — 2025-10-23
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On 10/23/25 13:31, Vishal Annapurve wrote:
...
>> Admin logic to update TDX modules can be designed to either retry
>> failed TDX module updates or to be more robust, adds some

I'd really prefer to keep this simple. Adding new opt-in ABIs up the
wazoo doesn't seem great.

I think I've heard three requirements in the end:

1. Guarantee module update forward progress
2. Avoid "corrupt" TD build processes by letting the build/update
   race happen
3. Don't complicate the build process by forcing it to error out
   if a module update clobbers a build

One thing I don't think I've heard anyone be worried about is how timely
the update process is. So how about this: Updates wait for any existing
builds to complete. But, new builds wait for updates. That can be done
with a single rwsem:

struct rw_semaphore update_rwsem;

tdx_td_init()
{
	...
+	down_read_interruptible(&update_rwsem);
	kvm_tdx->state = TD_STATE_INITIALIZED;

tdx_td_finalize()
{
	...
+	up_read(&update_rwsem);
	kvm_tdx->state = TD_STATE_RUNNABLE;

A module update does:

	down_write_interruptible(&update_rwsem);
	do_actual_update();
	up_write(&update_rwsem);

There would be no corruption issues, no erroring out of the build
process, and no punting to userspace to ensure forward progress.

The big downside is that both the build process and update process can
appear to hang for a long time. It'll also be a bit annoying to ensure
that there are up_read(&update_rwsem)'s if the kvm_tdx object gets torn
down during a build.

But the massive upside is that there's no new ABI and all the
consistency and forward progress guarantees are in the kernel. If we
want new ABIs around it that give O_NONBLOCK semantics to build or
update, that can be added on after the fact.

Plus, if userspace *WANTS* to coordinate the whole shebang, they're free
to. They'd never see long hangs because they would be coordinating.

Thoughts?

---

## [37] Vishal Annapurve — 2025-10-23
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Thu, Oct 23, 2025 at 2:10 PM Dave Hansen <dave.hansen@intel.com> wrote:
>
> On 10/23/25 13:31, Vishal Annapurve wrote:

Yeah, this approach sounds reasonable.

---

## [38] Chao Gao — 2025-10-24
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

>One thing I don't think I've heard anyone be worried about is how timely
>the update process is. So how about this: Updates wait for any existing

Hi Dave,

Thanks for this summary and suggestion.

Beyond "the kvm_tdx object gets torn down during a build," I see two potential
issues:

1. TD Build and TDX migration aren't purely kernel processes -- they span multiple
   KVM ioctls. Holding a read-write lock throughout the entire process would
   require exiting to userspace while the lock is held. I think this is
   irregular, but I'm not sure if it's acceptable for read-write semaphores.

2. The kernel may need to hold this read-write lock for operations not yet
   defined in the future. The TDX Module Base spec [*] notes on page 55:

   : Future TDX Module versions may have different or additional update-sensitive
   : cases. By design, such cases apply to a small portion of the overall TD
   : lifecycle.

[*]: https://cdrdv2.intel.com/v1/dl/getContent/733575

Given these concerns, I'm not sure whether implementing a read-write lock in
the kernel is the right approach.

Since Google prefers to "avoid updates during update-sensitive times," we can
implement that approach for now. If other Linux users find this insufficient
and prefer failing TD build/migration operations with strong justification, we
can enable that functionality in the future.

What do you think?

---

## [39] Dave Hansen — 2025-10-24
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On 10/24/25 00:43, Chao Gao wrote:
...
> Beyond "the kvm_tdx object gets torn down during a build," I see two potential
> issues:

Sure, I guess it's irregular. But look at it this way: let's say we
concocted some scheme to use a TD build refcount and a module update
flag, had them both wait_event_interruptible() on each other, and then
did wakeups. That would get the same semantics without an rwsem.

So is your issue with the rwsem, or the idea that one bit of userspace
can block another bit of userspace from doing something for arbitrary
lengths of time?

The one thing that worries me is solidly tying the build-side
down_read() to the lifetime of kvm_tdx. But that shouldn't be rocket
science. There also isn't a down_write_interruptible(), only
down_write_killable().

> 2. The kernel may need to hold this read-write lock for operations not yet
>    defined in the future. The TDX Module Base spec [*] notes on page 55:
Sure... But that's not a license for the TDX module to do completely
silly things. Elena is on cc here for a reason and I'm sure she'll
ensure that nothing silly gets put into the TDX module that will cause
problems here.

---

## [40] dan.j.williams@intel.com — 2025-10-24
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

Dave Hansen wrote:
> On 10/24/25 00:43, Chao Gao wrote:
> ...

This sounds unworkable to me.

First, you cannot return to userspace while holding a lock. Lockdep will
rightfully scream:

    "WARNING: lock held when returning to user space!"

The complexity of ensuring that a multi-stage ABI transaction completes
from the kernel side is painful. If that process dies in the middle of
its ABI sequence who cleans up these references?

The operational mechanism to make sure that one process flow does not
mess up another process flow is for those process to communicate with
*userspace* file locks, or for those process to check for failures after
the fact and retry. Unless you can make the build side an atomic ABI,
this is a documentation + userspace problem, not a kernel problem.

---

## [41] Sean Christopherson — 2025-10-24
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Fri, Oct 24, 2025, dan.j.williams@intel.com wrote:
> Dave Hansen wrote:
> > On 10/24/25 00:43, Chao Gao wrote:

C'mon people (especially the Google folks), this is the ***exact*** same problem
as certificate updates for SNP[1].  Y'all suggested holding a lock across a userspace
exit back then, and Dan's analysis confirms my reaction from back then that
"Holding a lock across an exit to userspace seems wildly unsafe."[2]

In the end, it took more time to understand the problem then to sketch out and
test a solution[3]. 

Unless this somehow puts the host (kernel) at risk, this is a userspace problem.

[1] https://lore.kernel.org/all/20240426173515.6pio42iqvjj2aeac@amd.com
[2] https://lore.kernel.org/all/Zx_V5SHwzDAl8ZQR@google.com
[3] https://lore.kernel.org/all/ZixCYlKn5OYUFWEq@google.com

---

## [42] Dave Hansen — 2025-10-24
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On 10/24/25 12:40, dan.j.williams@intel.com wrote:
> Dave Hansen wrote:
>> On 10/24/25 00:43, Chao Gao wrote:

Well, yup, it sure does look that way for normal lockdep-annotated lock
types. It does seem like a sane rule to have for most things.

But, just to be clear, this is a lockdep thing and a good, solid
semantic to have. It's not a rule that no kernel locking structure can
ever be held when returning to userspace.

> The complexity of ensuring that a multi-stage ABI transaction completes
> from the kernel side is painful. If that process dies in the middle of

The 'struct kvm_tdx' has to get destroyed at some point. It also has a
'kvm_tdx_state' field that could be tied very tightly to the build
status. The reference gets cleaned up before the point when the
kvm_tdx->state memory is freed.

> The operational mechanism to make sure that one process flow does not
> mess up another process flow is for those process to communicate with

Yeah, that's a totally valid take on it.

My only worry is that the module update is going to be off in another
world from the thing building TDs. We had a similar set of challenges
around microcode updates, CPUSVN and SGX enclaves.

The guy doing "echo 1 > /sys/.../whatever" wasn't coordinating with
every entity on the system that might run an SGX enclave. It certainly
didn't help that enclave creation is typically done by unprivileged
users. Maybe the KVM/TDX world is a _bit_ more narrow and they will be
talking to each other, or the /dev/kvm permissions will be a nice funnel
to get them talking to each other.

The SGX solution, btw, was to at least ensure forward progress (CPUSVN
update) when the last enclave goes away. So new enclaves aren't
*prevented* from starting but the window when the first one starts
(enclave count going from 0->1) is leveraged to do the update.

---

## [43] Dave Hansen — 2025-10-24
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On 10/24/25 13:00, Sean Christopherson wrote:
> C'mon people (especially the Google folks), this is the ***exact***
> same problem as certificate updates for SNP[1].  Y'all suggested

If there's an similar SEV-SNP problem and accepted solution punted to
userspace that TDX can leverage, I'm 100% on board with that. Let's do that.

---

## [44] Vishal Annapurve — 2025-10-24
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Fri, Oct 24, 2025 at 1:14 PM Dave Hansen <dave.hansen@intel.com> wrote:
>
> On 10/24/25 13:00, Sean Christopherson wrote:

So IIUC, the current stance is that the kernel can rely on userspace
to ensure forward progress of TDX module update.

I still vote for the "Avoid updates during update sensitive times"
approach to be enabled in the host kernel to ensure userspace can't
mess up the TDX module state.

---

## [45] dan.j.williams@intel.com — 2025-10-24
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

Dave Hansen wrote:
> On 10/24/25 12:40, dan.j.williams@intel.com wrote:
> > Dave Hansen wrote:

Sure, but I would submit that the lesser known cousin of the common
suggestion "do not write your own locking primitives" is "do not invent
locking schemes that involve holding locks over return to userspace". It
is rarely a good idea to the point that lockdep warns about it by
default.

> > The complexity of ensuring that a multi-stage ABI transaction completes
> > from the kernel side is painful. If that process dies in the middle of

Indefinite hangs because a process goes out to lunch and fails to
destroy kvm_tdx in a reasonable timeframe now has knock-on effects.

[..]
> > The operational mechanism to make sure that one process flow does not
> > mess up another process flow is for those process to communicate with

The status quo does ensure forward progress. The TD does get built and
the update does complete, just the small matter of TD attestation
failures, right?

Note, we had a similar problem with the tsm_report interface which,
because it is configfs and not an ioctl, is a multi-stage ABI to build a
report. If 2 threads collide in building an object, userspace indeed
gets to keep the pieces, but there is:

1/ Documentation of the potential for collisions

2/ A mechanism to detect collisions. See
   /sys/kernel/config/tsm/report/$name/generation in
   Documentation/ABI/testing/configfs-tsm-report

I really would not worry about the "off in another world" problem, it is
par for the course for datacenter operations. I encountered prolific use
of file locks in operations scripts at my time at Facebook. Think of
problems like coordinating disk partitioning across various provisioning
flows. The kernel happily lets 2 fdisk processes race to write a
partition table. The only way to ensure a consistent result in that case
is userspace sequencing, not a kernel lock while some process has a
partition table open.

---

## [46] Dave Hansen — 2025-10-24
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On 10/24/25 14:12, dan.j.williams@intel.com wrote:
>> The SGX solution, btw, was to at least ensure forward progress (CPUSVN
>> update) when the last enclave goes away. So new enclaves aren't

Oh, yeah, for sure.

If we do _nothing_ in the kernel (no build vs. module update
synchronization), then the downside is being exposed to attestation
failures if userspace either also does nothing or has bugs.

That's actually, by far, my preferred solution to this whole mess:
Userspace plays stupid games, userspace wins stupid prizes.

---

## [47] Vishal Annapurve — 2025-10-24
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Fri, Oct 24, 2025 at 2:19 PM Dave Hansen <dave.hansen@intel.com> wrote:
>
> On 10/24/25 14:12, dan.j.williams@intel.com wrote:

I would think that it's not a "small" problem if confidential
workloads on the hosts are not able to pass attestation.

>
> Oh, yeah, for sure.

IIUC, enforcing "Avoid updates during update sensitive times" is not
that complex and will ensure to avoid any issues with user space
logic.

---

## [48] dan.j.williams@intel.com — 2025-10-24
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

Vishal Annapurve wrote:
> On Fri, Oct 24, 2025 at 2:19 PM Dave Hansen <dave.hansen@intel.com> wrote:
> >

"Small" as in "not the kernel's problem". Userspace asked for the
update, update is documented to clobber build sometimes, userspace ran
an update anyway. Userspace asked for the clobber.

It would be lovely if this clobbering does not happen at all and the
update mechanism did not come with this misfeature. Otherwise, the kernel
has no interface to solve that problem. The best it can do is document
that this new update facility has this side effect.

Userspace always has the choice to not update, coordinate update with
build, or do nothing and let tenants try to launch again.  Userspace
could even retry the build and hide the tenant failure if it knew about
the clobber, but be clear that the problem is the clobber not the kernel
doing what userspace asked.

The clobber, as I understand, is also limited to cases where the update
includes crypto library changes. I am not sure how often that happens in
practice. Suffice to say, the fact that the clobber is conditioned on
the contents of the update also puts it further away from being a kernel
problem. The clobber does not corrupt kernel state.

> > Oh, yeah, for sure.
> >

Userspace logic avoids issues by honoring the documentation that these
ABIs sequences need synchronization. Otherwise, kernel blocking update
during build just trades one error for another.

Treat this like any other userspace solution for requiring "atomic"
semantics when the kernel mechanisms are not themselves designed to be
atomic, wrap it in userspace synchronization.

---

## [49] Vishal Annapurve — 2025-10-25
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Fri, Oct 24, 2025 at 6:42 PM <dan.j.williams@intel.com> wrote:
>
> Vishal Annapurve wrote:

In this case, host kernel has a way to ensure that userspace can't
trigger such clobbering at all. That IIUC is "Avoid updates during
update sensitive times". Best kernel can do is prevent userspace from
screwing up the state of TDs.

>
> Userspace always has the choice to not update, coordinate update with

IIUC host userspace has no way to know if the TD state got clobbered.

> but be clear that the problem is the clobber not the kernel
> doing what userspace asked.

The knowledge of things getting clobbered are well much further away
from userspace.

> problem. The clobber does not corrupt kernel state.
>

Kernel blocking update during build makes the production systems much
safer and prevents userspace from screwing up the state that it has no
way to detect after the fact.

>
> Treat this like any other userspace solution for requiring "atomic"

In general if this is something userspace detectable I would agree,
TDX module is the closest entity that can detect the problematic
sequence and the host kernel has a very simple way to ensure that such
a problematic sequence is not at all allowed to happen by toggling
some seamcall controls. It would be very helpful IMO to ensure that
userspace is not able to screw up production workloads especially if
the mess is not all visible to userspace.

---

## [50] Vishal Annapurve — 2025-10-25
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Sat, Oct 25, 2025 at 4:55 AM Vishal Annapurve <vannapurve@google.com> wrote:
>
> On Fri, Oct 24, 2025 at 6:42 PM <dan.j.williams@intel.com> wrote:

Detecting is one thing, undoing the mess is disruptive and not easy to
orchestrate in this case.

---

## [51] dan.j.williams@intel.com — 2025-10-26
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

Vishal Annapurve wrote:
> On Fri, Oct 24, 2025 at 6:42 PM <dan.j.williams@intel.com> wrote:
> >

Unless the clobber condition can be made atomic with respect to update
so that both succeed, the kernel needs to punt the syncrhonization
problem to userspace.

A theoretical TDX Module change could ensure that atomicity. A
theoretical change to the kernel's build ABI could effect that as well,
or notify the collision. I.e. a flag at the finalization stage that an
update happened during the build sequence needs a restart. This is the
role of "generation" in the tsm_report ABI. As far as I understand
userspace just skips that ABI and arranges for userspace synchronized
access to tsm_report.

At the point where the solution is "change existing build flows" might
as well just have userspace wrap the flows with userspace exclusion.

> That IIUC is "Avoid updates during update sensitive times". Best
> kernel can do is prevent userspace from screwing up the state of TDs.

"Avoid updates during update sensitive times" is the documentation for
the update userspace ABI.

> > Userspace always has the choice to not update, coordinate update with
> > build, or do nothing and let tenants try to launch again.  Userspace

Correct, today it can only assume that both flows need to be mutually
exclusive.

> > but be clear that the problem is the clobber not the kernel
> > doing what userspace asked.

The possibility is documented as part of the update ABI. Another
documentation possibility is that updates that change the crypto library
are by definition not "runtime update" capable. A possible TDX Module
change to remove this collision. A menu of options before complicating
the kernel.

---

## [52] Vishal Annapurve — 2025-10-26
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Sun, Oct 26, 2025 at 2:30 PM <dan.j.williams@intel.com> wrote:
>
> Vishal Annapurve wrote:

IIUC TDX module already supports avoiding this clobber based on the
TDH.SYS.SHUTDOWN documentation from section 5.4.73 of TDX ABI Spec
[1].

Host kernel needs to set bit 16 of rcx when invoking TDH.SYS.SHUTDOWN
is available.

"If supported by the TDX Module, the host VMM can set the
AVOID_COMPAT_SENSITIVE flag to request the TDX Module to fail
TDH.SYS.UPDATE if any of the TDs are currently in a state that is
impacted by the update-sensitive cases."

I think the above documentation should replace TDH.SYS.UPDATE with
TDH.SYS.SHUTDOWN IIUC.

[1] https://cdrdv2.intel.com/v1/dl/getContent/733579

> A
> theoretical change to the kernel's build ABI could effect that as well,

---

## [53] dan.j.williams@intel.com — 2025-10-27
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

Vishal Annapurve wrote:
[..]
> > A theoretical TDX Module change could ensure that atomicity.
> 

That is not a fix. That just shifts the complexity from build to update.
It still leaves update in a state where it is not guaranteed to make
forward progress. The way to ensure forward progress is the same as
ensuring build consistency, i.e. sequence build with respect to update.
The kernel sheds complexity by ether making userspace solve that
problem, or motivating a real fix in the TDX Module that obviates the
AVOID_COMPAT_SENSITIVE case.

---

## [54] Vishal Annapurve — 2025-10-27
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Mon, Oct 27, 2025 at 11:53 AM <dan.j.williams@intel.com> wrote:
>
> Vishal Annapurve wrote:

IMO, there are two problems here:
1) Giving a consistent ABI that leaves the responsibility of ensuring
forward progress by sequencing TD update with TD build steps with
userspace.
2) Ensuring that userspace can't screw up the in-progress TD VM
metadata if userspace doesn't adhere to the sequence above.

Problem 2 should be solved in the TDX module as it is the state owner
and should be given a chance to ensure that nothing else can affect
it's state. Kernel is just opting-in to toggle the already provided
TDX module ABI. I don't think this is adding complexity to the kernel.

> forward progress. The way to ensure forward progress is the same as
> ensuring build consistency, i.e. sequence build with respect to update.

---

## [55] dan.j.williams@intel.com — 2025-10-27
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

Vishal Annapurve wrote:
[..]
> Problem 2 should be solved in the TDX module as it is the state owner
> and should be given a chance to ensure that nothing else can affect

It makes the interface hard to reason about, that is complexity.

Consider an urgent case where update is more important than the
consistency of ongoing builds. The kernel's job is its own self
consistency and security model, when that remains in tact root is
allowed to make informed decisions.

You might say, well add a --force option for that, and that is also
userspace prerogative to perform otherwise destructive operations with
the degrees of freedom the kernel allows.

I think we have reached the useful end of this thread. I support moving
ahead with the dead simple, "this may clobber your builds", for now. We
can always circle back to add more complexity later if that proves "too
simple" in practice.

---

## [56] Chao Gao — 2025-10-28
*Subject: Re: [PATCH v2 16/21] x86/virt/seamldr: Handle TDX Module update
 failures*

> /*
>  * See multi_cpu_stop() from where this multi-cpu state-machine was

I found a bug here.

If an error is non-fatal (e.g., occurs before shutting down the TDX module),
the TDX Module remains functional and TDs can continue to run. So, there's no
need to set the TDX module status to erorr or print the error message.

But, in this implementation, a failing CPU doesn't exit the do-while() loop in
do_seamldr_install_module(). Instead, all CPUs fast-forward to the TDP_DONE
state and execute the do-while() body once more. Then, the failing CPU reaches
the above if() statement again with a non-zero "ret" and "curstate=TDP_DONE",
causing it to incorrectly set the module to error and print the error message.

To fix this issue, apply the following diff:

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index a72f6b0b27e9..e525bbd16610 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -258,16 +258,8 @@ static void set_target_state(enum tdp_state state)
 /* Last one to ack a state moves to the next state. */
 static void ack_state(void)
 {
-	if (atomic_dec_and_test(&tdp_data.thread_ack)) {
-		/*
-		 * If an error occurred, abort the update by skipping to
-		 * the final state
-		 */
-		if (atomic_read(&tdp_data.failed))
-			set_target_state(TDP_DONE);
-		else
-			set_target_state(tdp_data.state + 1);
-	}
+	if (atomic_dec_and_test(&tdp_data.thread_ack))
+		set_target_state(tdp_data.state + 1);
 }
 
 static void print_update_failure_message(void)
@@ -331,7 +323,7 @@ static int do_seamldr_install_module(void *params)
			touch_nmi_watchdog();
			rcu_momentary_eqs();
		}
-	} while (curstate != TDP_DONE);
+	} while (curstate != TDP_DONE && !atomic_read(&tdp_data.failed));
 
	return ret;
 }

---

## [57] Erdem Aktas — 2025-10-28
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Mon, Oct 27, 2025 at 7:14 PM <dan.j.williams@intel.com> wrote:
>
> Vishal Annapurve wrote:

Could you clarify what you mean here? What interface do you need to
reason about? TDX module has a feature as described in its spec, this
is nothing to do with the kernel. Kernel executes the TDH.SYS.SHUTDOWN
and if it fails, it will return the error code back to the user space.
There is nothing here to reason about and it is not clear how it is
adding the complexity to the kernel.

>
> Consider an urgent case where update is more important than the
The whole update is initiated by the userspace, imo, it is not the
kernel's job to decide what to do. It should try to update the TDX
module and return error code back to the userspace if it fails. it is
up to the userspace to resolve the conflict and retry the
installation. If you are saying that the userspace is not trusted for
such a critical action, again the whole process is initiated and
controlled by the userspace so there is an inherent trust there.

Consistency? How does td preserve failure impact the kernel
consistency? On the contrary, bypassing AVOID_COMPAT_SENSITIVE will
break the consistency for some TDs.

> You might say, well add a --force option for that, and that is also
> userspace prerogative to perform otherwise destructive operations with

IMO, It is something userspace should decide, kernel's job is to
provide the necessary interface about it.

>
> I think we have reached the useful end of this thread. I support moving
It is not clear how you reached that conclusion. We are one of the
users for this feature and we have multiple times explained that we
prefer failure on update if there is any risk of corrupting some TD
states. I did not see any other feedback/preference from other users
and I did not see any reasonable argument why you are preferring the
"clobber your builds" option.

Also the "clobber your builds" option will impact the TDX live
migration, considering the TDX live migration is WIP, it will be
definitely very hard to foresee the challenges there you are
introducing with this decision. How about TDX connect? Are we going to
come back and keep updating this every time we find an issue?

Since the update process is initiated and controlled by userspace, it
is the userspace application's prerogative to make the informed
decision on whether an urgent update warrants potentially destructive
actions. The kernel's role is to provide a reliable mechanism to
interact with the TDX Module and report outcomes accurately.
 Ideally,  ABI should allow userpace to provide flags which can be
also used to configure the TD preserve update option. If you do not
want to change ABI, you can make those as module param so userspace
can make a decision by itself.


To address some of your previous concerns:
It shifts complexity to userspace which is something everyone here
seems to prefer. The problem is that the TD Preserve update would
corrupt the TDs who are in the build stage (also impacts TDX LM  and
possibly some TDX connect functionalities) and since the TDX module
would know about it,  this will make sure that they will not be
corrupted hence it is a fix for a problem.

TDH.SYS.SHUTDOWN may not succeed due to multiple reasons like
TDX_SYS_BUSY  therefore it needs to handle the error cases anyway and
should return the error to the userspace.
Now userspace can decide whatever logic it has to finish/cancel the
existing tdbuilds and retry the tdpreserve update.

You might be concerned about forward progress. As I said above, there
might be some other cases which might prevent the td preserve update
to succeed so forward progress is not guaranteed anyway and it is not
the kernel's job to figure it out. It will return the error code back
to userspace and let the userspace resolve the conflict.

---

## [58] dan.j.williams@intel.com — 2025-10-28
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

Vishal Annapurve wrote:
> On Mon, Oct 27, 2025 at 11:53 AM <dan.j.williams@intel.com> wrote:
> >

That gives update a transient error to handle

---

## [59] dan.j.williams@intel.com — 2025-10-28
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

dan.j.williams@ wrote:
[..]
> That gives update a transient error to handle

Apologies, this was a draft sent in error.

---

## [60] Vishal Annapurve — 2025-10-28
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Mon, Oct 27, 2025 at 7:13 PM <dan.j.williams@intel.com> wrote:
>
> Vishal Annapurve wrote:

I would consider the TDX module as more privileged than the kernel
itself in certain aspects. So it's not fine to expose an ABI to
userspace which affects kernel state consistency, but it's fine to
expose an ABI that can affect TDX module state consistency?

> when that remains in tact root is allowed to make informed decisions.
>

---

## [61] Sean Christopherson — 2025-10-28
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Tue, Oct 28, 2025, Erdem Aktas wrote:
> On Mon, Oct 27, 2025 at 7:14 PM <dan.j.williams@intel.com> wrote:
> >

Userspace needs to reason about error codes and potential sources of those error
codes.  That said, I agree that having the kernel set AVOID_COMPAT_SENSITIVE by
default (I vote for setting it unconditionally), doesn't add meaningful
complexity; the kernel would just need to document that the update mechanism can
return -EBUSY (or whatever), and why/when.

For me, that seems far less daunting/complex than attempting to document what all
can go wrong if the kernel _doesn't_ set AVOID_COMPAT_SENSITIVE.  Because IMO,
regardless of whether or not the kernel sets AVOID_COMPAT_SENSITIVE, the kernel
is making a decision and defining behavior, and that behavior needs to be
documented.  If AVOID_COMPAT_SENSITIVE didn't exist, then I would agree this is
purely a userspace vs. TDX-Module problem, but it does exist, and not setting the
flag defines ABI just as much as setting the flag does.

The failure mode also matters, a lot.  "Sorry dear customer, we corrupted your VM"
is very, very different than "A handful of machines in our fleet haven't completed
an (optional?) update".

> > Consider an urgent case where update is more important than the
> > consistency of ongoing builds. The kernel's job is its own self

I think you and Dan are in violent agreement.  I _think_ what Dan is saying that
the kernel needs to protect itself, e.g. by rejecting an update if the kernel knows
the system is in a bad state.  But other than that, userspace can do whatever.

AFAICT, the only disagreement is whether or not to set AVOID_COMPAT_SENSITIVE.

> It should try to update the TDX module and return error code back to the
> userspace if it fails.

+1.  Unless there's a wrinkle I'm missing, failing with -EBUSY seems like the
obvious choice.
 
> > You might say, well add a --force option for that, and that is also
> > userspace prerogative to perform otherwise destructive operations with

I disagree, I don't think userspace should even get the option.  IMO, not setting
AVOID_COMPAT_SENSITIVE is all kinds of crazy.

---

## [62] dan.j.williams@intel.com — 2025-10-28
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

Sean Christopherson wrote:
[..]
> > IMO, It is something userspace should decide, kernel's job is to
> > provide the necessary interface about it.

Do see Table 4.4: "Comparison of Update Incompatibility Detection and/or
Avoidance Methods" from the latest base architecture specification [1].
It lists out the pros and cons of not setting AVOID_COMPAT_SENSITIVE.
This thread has only argued the merits of "None" and "Avoid updates
during update- sensitive times". It has not discussed "Detect
incompatibility after update", but let us not do that. You can just
assume the Module has multiple solutions to this awkward problem
precisely because different VMMs came to different conclusions.

I want this thread to end so I am not going to argue past what Dave and
Sean want to do here.

[1]: https://www.intel.com/content/www/us/en/content-details/865787/intel-tdx-module-base-architecture-specification.html

---

## [63] Sean Christopherson — 2025-10-29
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Tue, Oct 28, 2025, dan.j.williams@intel.com wrote:
> Sean Christopherson wrote:
> [..]

But we already are discussing that, because the "None" option is just punting
"Detect incompatibility after update" to something other than the VMM.  Doing
literally nothing isn't an option.  The fact that it's even listed in the table,
not to mention has "Simplest." listed as a pro, makes me question whether or not
the authors actually understand how software built around the TDX-Module is used
in practice.

If an update causes a TD build to fail, or to generate the wrong measurement, or
whatever "Failures due to incompatibilities" means, *something* eventually needs
to take action.  Doing nothing is certainly the simplest option for the hypervisor
and VMM, but when looking at the entire stack/ecosystem, it's the most complex
option as it bleeds the damage into multiple, potentially-unknown components of
the stack.  Either that, or I'm grossly misunderstanding what "Failures" means.

That section also states:

  Future TDX Module versions may have different or additional update-sensitive cases.

Which means that from an ABI perspective, "Avoid updates during update-sensitive
times" is the _ONLY_ viable option.  My read of that is that future TDX-Modules
can effectively change the failure modes for a existing KVM ioctls.  That is an
ABI change and will break userspace, e.g. if userspace is sane and expects certain
operations to succeed.

---

## [64] Vishal Annapurve — 2025-10-30
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Wed, Oct 29, 2025 at 6:48 AM Sean Christopherson <seanjc@google.com> wrote:
>
> On Tue, Oct 28, 2025, dan.j.williams@intel.com wrote:

A reference patch we tested for "Avoid updates during update-sensitive
times" and one caveat was that
/sys/devices/virtual/tdx/tdx_tsm/version was not available post update
failure until a subsequent successful update:

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index e00650b83f08..96ae7c679e4e 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -22,6 +22,7 @@
 #define TDX_FEATURES0_NO_RBP_MOD               BIT_ULL(18)
 #define TDX_FEATURES0_CLFLUSH_BEFORE_ALLOC     BIT_ULL(23)
 #define TDX_FEATURES0_DYNAMIC_PAMT             BIT_ULL(36)
+#define TDX_FEATURES0_UPDATE_COMPATIBILITY     BIT_ULL(47)

 #ifndef __ASSEMBLY__

@@ -129,6 +130,11 @@ static inline bool
tdx_supports_dynamic_pamt(const struct tdx_sys_info *sysinfo)
        return sysinfo->features.tdx_features0 & TDX_FEATURES0_DYNAMIC_PAMT;
 }

+static inline bool tdx_supports_update_compatibility(const struct
tdx_sys_info *sysinfo)
+{
+       return sysinfo->features.tdx_features0 &
TDX_FEATURES0_UPDATE_COMPATIBILITY;
+}
+
 int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index f6199f8ce411..95deb1146a79 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1523,6 +1523,10 @@ int tdx_module_shutdown(void)
         * fail.
         */
        args.rcx = tdx_sysinfo.handoff.module_hv;
+
+       if (tdx_supports_update_compatibility(&tdx_sysinfo))
+               args.rcx |= TDX_SYS_SHUTDOWN_AVOID_COMPAT_SENSITIVE;
+
        ret = seamcall_prerr(TDH_SYS_SHUTDOWN, &args);
        if (!ret)
                tdx_module_reset_state();
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 0cd9140620f9..772c714de2bc 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -94,6 +94,8 @@ struct tdmr_info {
 /* Bit definitions of TDX_FEATURES0 metadata field */
 #define TDX_FEATURES0_TD_PRESERVING    BIT(1)

+#define TDX_SYS_SHUTDOWN_AVOID_COMPAT_SENSITIVE                BIT(16)
+
 /*
  * Do not put any hardware-defined TDX structure representations below
  * this comment!

---

## [65] Sagi Shahar — 2025-10-30
*Subject: Re: [PATCH v2 07/21] coco/tdx-host: Expose P-SEAMLDR information via sysfs*

On Tue, Sep 30, 2025 at 9:55 PM Chao Gao <chao.gao@intel.com> wrote:
>
> TDX Module updates require userspace to select the appropriate module

Trying to apply this patch locally fails because
sysfs-devices-faux-tdx-host does not exist. There are also conflicts
around drivers/virt/coco/tdx-host/tdx-host.c.

I'm looking at the base commit specified in the cover letter [1] but
even the current head of the tsm/tdx tree [2] doesn't have the
sysfs-devices-faux-tdx-host file. Are there any other dependencies for
this series?

[1] https://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git/commit/?h=tdx&id=9332e088937f
[2] https://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git/tree/Documentation/ABI/testing?h=tdx

> index 18d4a4a71b80..13c1f4f9909c 100644
> --- a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host

---

## [66] dan.j.williams@intel.com — 2025-10-30
*Subject: Re: [PATCH v2 07/21] coco/tdx-host: Expose P-SEAMLDR information via
 sysfs*

Sagi Shahar wrote:
> On Tue, Sep 30, 2025 at 9:55 PM Chao Gao <chao.gao@intel.com> wrote:
> >

I hit the same head scratcher, but then realized that Chao did say that
you also need to apply:

https://lore.kernel.org/linux-coco/20251001022309.277238-1-chao.gao@intel.com

...so:

git checkout -b $branch 9332e088937f
b4 shazam 20251001022309.277238-1-chao.gao@intel.com
b4 shazam 20251001025442.427697-1-chao.gao@intel.com

...works for me.

---

## [67] Chao Gao — 2025-10-31
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

>A reference patch we tested for "Avoid updates during update-sensitive
>times" and one caveat was that

I also tested this. It works well to prevent updates during TD build, so,

  Tested-by: Chao Gao <chao.gao@intel.com>

And I can integrate this change into my next version if you don't object.

Regarding the caveat, could you check if the diff [*] I posted earlier this
week can fix it?

[1]: https://lore.kernel.org/linux-coco/aQAwRrvYMcaMsu02@intel.com/

---

## [68] Sagi Shahar — 2025-10-31
*Subject: Re: [PATCH v2 07/21] coco/tdx-host: Expose P-SEAMLDR information via sysfs*

On Thu, Oct 30, 2025 at 6:05 PM <dan.j.williams@intel.com> wrote:
>
> Sagi Shahar wrote:

Thanks, I missed that one. It's working now

---

## [69] Sagi Shahar — 2025-10-31
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Tue, Sep 30, 2025 at 9:54 PM Chao Gao <chao.gao@intel.com> wrote:
>
> Changelog:

Can you clarify which patches are needed from this tree? Is it just
"coco/tdx-host: Introduce a "tdx_host" device" or is this series also
depends on other patches?

More specifically, does this series depend on "Move VMXON/VMXOFF
handling from KVM to CPU lifecycle"?

>
> and the TDX Module version series at:

---

## [70] Vishal Annapurve — 2025-10-31
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Fri, Oct 31, 2025 at 9:55 AM Sagi Shahar <sagis@google.com> wrote:
>
> On Tue, Sep 30, 2025 at 9:54 PM Chao Gao <chao.gao@intel.com> wrote:

Hi Chao,

Is this non-RFC series dependent on RFC patches?

What's the intended order of upstreaming the features and dependencies
being discussed here?

---

## [71] Chao Gao — 2025-11-01
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

>> == How to test this series ==
>>

Yes. I meant checkout to that specific commit. both "tdx_host" device and
"Move VMXOFF handling from KVM to CPU lifecycle" are needed to apply this
series.

---

## [72] Chao Gao — 2025-11-01
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

>> > == Base commit ==
>> >

Features are expected to be merged in this order:
1. Move VMXON out of KVM
2. tdx-host device
3. TDX Module version exposure, i.e., https://lore.kernel.org/linux-coco/20251001022309.277238-1-chao.gao@intel.com/
4. TDX Module runtime update

---

## [73] Chao Gao — 2025-11-12
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Tue, Sep 30, 2025 at 07:52:44PM -0700, Chao Gao wrote:
>Hi Reviewers,
>

Hi Kirill and Rick,

Would you be able to take a look at this series when you get a chance?
I'd appreciate your feedback.

---

## [74] Sagi Shahar — 2025-11-19
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Thu, Oct 30, 2025 at 9:53 PM Chao Gao <chao.gao@intel.com> wrote:
>
> >A reference patch we tested for "Avoid updates during update-sensitive

[Now in plaintext]

I tried testing it with the 1.5.24 TDX module and it sometimes fails,
but the failure does not appear consistent.

I added a local change to add the
TDX_SYS_SHUTDOWN_AVOID_COMPAT_SENSITIVE flag when calling
TDH_SYS_SHUTDOWN and TDH_SYS_SHUTDOWN fails as expected if a VM is
under build:
[ 1224.571177] virt/tdx: SEAMCALL (52) failed: 0x8000051200010000

But then sometimes trying to finalize the VM fail with the following error:
[ 1230.915145] kvm_intel: SEAMCALL TDH_MR_FINALIZE failed: 0x8000ff00ffff0000
[ 1230.948264] kvm_intel: tdh_mng_vpflushdone() failed. HKID 3 is leaked.

At this point the module seems to be in a broken state and trying to
create more TDs will fail:
[ 1543.745606] kvm_intel: SEAMCALL TDH_MNG_CREATE failed: 0x8000ff00ffff0000

Trying to update the module will fail shutdown with -ENODEV

---

## [75] Chao Gao — 2025-11-20
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Wed, Nov 19, 2025 at 04:44:50PM -0600, Sagi Shahar wrote:
>On Thu, Oct 30, 2025 at 9:53 PM Chao Gao <chao.gao@intel.com> wrote:
>>

Can you apply this incremental change to see if the issue gets fixed?

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index e525bbd16610..f0bea1fecc52 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -317,8 +317,9 @@ static int do_seamldr_install_module(void *params)
					tdx_module_set_error();
					print_update_failure_message();
				}
+			} else {
+				ack_state();
			}
-			ack_state();
		} else {
			touch_nmi_watchdog();
			rcu_momentary_eqs();


The problem is if the failing CPU is the last one to ack the TDP_SHUTDOWN
state, the state will move to TDP_CPU_INSTALL state. Other CPUs may proceed to
install the new module before seeing tdp_data.failed. This disables TDX ISA, so
any subsequent SEAMCALLs get 0x8000ff00ffff0000.

---

## [76] Sagi Shahar — 2025-11-20
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Wed, Nov 19, 2025 at 8:47 PM Chao Gao <chao.gao@intel.com> wrote:
>
> On Wed, Nov 19, 2025 at 04:44:50PM -0600, Sagi Shahar wrote:

Thanks, I ran a couple dozen updates while TD was being built and
couldn't reproduce the issue with the new fix

---

## [77] Binbin Wu — 2025-11-21
*Subject: Re: [PATCH v2 04/21] x86/virt/tdx: Prepare to support P-SEAMLDR
 SEAMCALLs*

On 10/1/2025 10:52 AM, Chao Gao wrote:
> P-SEAMLDR is another component alongside the TDX module within the
> protected SEAM range. P-SEAMLDR can update the TDX module at runtime.

Comparing to TDX module seamcall, seamldr seamcall should be much less.
Maybe unlikely()?

> +		return error_code == SEAMLDR_RND_NO_ENTROPY;
> +	else

%lld -> %llu ?

And 0x% -> %# to align with seamcall_err().



> +}
> +

---

## [78] Binbin Wu — 2025-11-21
*Subject: Re: [PATCH v2 05/21] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On 10/1/2025 10:52 AM, Chao Gao wrote:
[...]
>   
> +config INTEL_TDX_MODULE_UPDATE

any newer -> any compatible newer ?

> +	  version without the need to terminate running TDX guests.
> +

---

## [79] Binbin Wu — 2025-11-24
*Subject: Re: [PATCH v2 08/21] coco/tdx-host: Implement FW_UPLOAD sysfs ABI for
 TDX Module updates*

On 10/1/2025 10:52 AM, Chao Gao wrote:
[...]
>   
> +static enum fw_upload_err tdx_fw_prepare(struct fw_upload *fwl,

Since the execution of the work is not protected by the mutex, if userspace
requests cancellation after this point, after the TDX module update finished,
it seems that the cancel value is left over and it could impact the next update?

> +
> +	/*
[...]

---

## [80] Binbin Wu — 2025-11-27
*Subject: Re: [PATCH v2 11/21] x86/virt/seamldr: Allocate and populate a module
 update request*

On 10/1/2025 10:52 AM, Chao Gao wrote:
[...]
> +
> +/* Allocate and populate a seamldr_params */
According to the link [2] you provided above, it seems that the layout of
tdx_blob as following:
tdx_blob
|- u16      version
|- u16      checksum
|- u32      offset_of_module  --------------------------------------|
|- u8       signature[8]  |
|- u32      len                                     8KB + (N * 4KB) |
|- u32      resv1 |
|- u64      resv2[509]  |
|- u8       data[]  |
             |- _u64 sigstruct[256]   //2KB sigstruct  |
             |- _u64 reserved2[256]  |
             |- _u64 reserved3[N*512] //4KB aligned, optional, N >=0  |
             |- _u8  module[]  //<-----------------------------|

If N is not 0 for reserved3, then the sig_size passed will not be 4KB.


> +		return ERR_PTR(-EINVAL);
> +

Since sig is 4KB aligned, is ((unsigned long)sig & ~PAGE_MASK) needed?

> +	params->num_module_pages = module_size / SZ_4K;
> +

Ditto for ptr, very ptr is 4KB aligned.

> +		ptr += SZ_4K;
> +	}

Based on the link [2], 0x100 stands for version 1.0, Using hexadecimal seems
more readable.

> +		return ERR_PTR(-EINVAL);
> +	}

---

## [81] Binbin Wu — 2025-11-27
*Subject: Re: [PATCH v2 11/21] x86/virt/seamldr: Allocate and populate a module
 update request*

On 11/27/2025 4:30 PM, Binbin Wu wrote:
> 
> 

Sorry about the mess.

tdx_blob
|- u16      version
|- u16      checksum
|- u32      offset_of_module   --------------------------------------|
|- u8       signature[8]                                             |
|- u32      len                                     8KB + (N * 4KB)  |
|- u32      resv1                                                    |
|- u64      resv2[509]                                               |
|- u8       data[]                                                   |
             |- _u64 sigstruct[256]   //2KB sigstruct                 |
             |- _u64 reserved2[256]                                   |
             |- _u64 reserved3[N*512] //4KB aligned, optional, N >=0  |
             |- _u8  module[]         //<-----------------------------|

> 
> If N is not 0 for reserved3, then the sig_size passed will not be 4KB.

---

## [82] Chao Gao — 2025-12-02
*Subject: Re: [PATCH v2 11/21] x86/virt/seamldr: Allocate and populate a
 module update request*

On Thu, Nov 27, 2025 at 04:30:41PM +0800, Binbin Wu wrote:
>
>

The "reserved3[N*512]" is there for future extension.

The current P-SEAMLDR ABI only supports one 4KB page, so if a blob's sig_size
is larger, the kernel has to reject it. The P-SEAMLDR ABI should be extended
first, and then we can add kernel support accordingly.

>
>

This is done intentionally. Otherwise, we would need to assume PAGE_SIZE is
4KB. Although this is true for x86, just in case it changes in the future and
subtly breaks this code, I use SZ_4K and apply PAGE_MASK here.

<snip>

>> +static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
>> +{

Makes sense. Will do.

---

## [83] Chao Gao — 2025-12-02
*Subject: Re: [PATCH v2 08/21] coco/tdx-host: Implement FW_UPLOAD sysfs ABI
 for TDX Module updates*

On Mon, Nov 24, 2025 at 03:49:34PM +0800, Binbin Wu wrote:
>
>

Yes, I think this is a bug. A few other drivers just clear "cancel_request" in
the "prepare" phase, e.g., pd692x0_fw_prepare(), mpfs_auto_update_prepare(),
m10bmc_sec_prepare(). I will follow that approach.

---

## [84] Chao Gao — 2025-12-02
*Subject: Re: [PATCH v2 04/21] x86/virt/tdx: Prepare to support P-SEAMLDR
 SEAMCALLs*

>> +static inline bool is_seamldr_call(u64 fn)
>> +{

Makes sense.

>
>> +		return error_code == SEAMLDR_RND_NO_ENTROPY;

Sure. Will Do.

---

## [85] Binbin Wu — 2025-12-03
*Subject: Re: [PATCH v2 14/21] x86/virt/seamldr: Shut down the current TDX
 module*

On 10/1/2025 10:52 AM, Chao Gao wrote:
> TDX Module updates request shutting down the existing TDX module.
> During this shutdown, the module generates hand-off data, which captures

According to the TDX module base spec (348549006), each TDX module is built with
TDX Module Handoff Constants, including No-Downgrade Flag. If the current TDX
module is built with NO_DOWNGRADE=1, the hand-off module version must be the
current TDX module's HV.

This patch series doesn't seems to handle No-Downgrade Flag, IIUC it needs
to use the current TDX module's HV to avoid failures.

About "hand-off version" and "No-Downgrade Flag", I still have some questions.
Is it possible that two TDX module versions have the same hand-off version?
If the newer TDX module built with NO_DOWNGRADE=1, is it possible to downgrade
to the older TDX module when they are using the same hand-off version?

> 
> Generate changes to tdx_global_metadata.{hc} by following the

[...]

---

## [86] Binbin Wu — 2025-12-03
*Subject: Re: [PATCH v2 19/21] x86/virt/tdx: Establish contexts for the new TDX
 Module*

On 10/1/2025 10:53 AM, Chao Gao wrote:
> After being installed, the new TDX Module shouldn't re-configure the
> global HKID, TDMRs or PAMTs. Instead, to preserve running TDs, it should

Since it's a seamcall error, shouldn't it be u64?

> +	if (ret) {
> +		tdx_module_status = TDX_MODULE_ERROR;

pr_info -> pr_err?
Also, use 0x%016llx as the format.

> +		return ret;
> +	}

---

## [87] Binbin Wu — 2025-12-03
*Subject: Re: [PATCH v2 20/21] x86/virt/tdx: Update tdx_sysinfo and check
 features post-update*

On 10/1/2025 10:53 AM, Chao Gao wrote:

[...]
>  
> +/*

Nit:
Could be if (WARN_ONCE(ret, "..."))

> +		return ret;
> +	}

Nit:
After update, the current TDX module is the new TDX module already, may be
better to use old instead of cur.

> +	new = &info->version;
> +	pr_info("version %u.%u.%02u -> %u.%u.%02u\n", cur->major_version,


BIOS update?
I guess it's "TDX module update via BIOS"?

Does it mean after a system reboot, the change done by TD preserving update will
be gone? If we want the TDX module upgrade to be permanent, it needs to replace
the TDX module binary the BIOS will load, right?

So the scenario of TD preserving update seems to be limited to security fixes?
(I guess the security fixes will take effect directly after TD preserving
update?)


> +	return 0;
> +}

---

## [88] Edgecombe, Rick P — 2026-01-02
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Wed, 2025-11-12 at 22:09 +0800, Chao Gao wrote:
> On Tue, Sep 30, 2025 at 07:52:44PM -0700, Chao Gao wrote:
> > Hi Reviewers,

I can't apply it. The source commit is gone from the tsm repo, but
besides that it requires applying a bunch of dependencies.

Can you push a branch somewhere? When there is a stack like this, it is
kind of needed to ease review.

---

## [89] Dave Hansen — 2026-01-02
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On 1/2/26 12:52, Edgecombe, Rick P wrote:>> Would you be able to take a
look at this series when you get a
>> chance? I'd appreciate your feedback.
> I can't apply it. The source commit is gone from the tsm repo, but 
If there are dependencies, is this the right thing for reviewers to be
spending time on? Shouldn't they be making sure the dependencies are
reviewed and merged first?

---

## [90] Chao Gao — 2026-01-04
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Sat, Jan 03, 2026 at 04:52:43AM +0800, Edgecombe, Rick P wrote:
>On Wed, 2025-11-12 at 22:09 +0800, Chao Gao wrote:
>> On Tue, Sep 30, 2025 at 07:52:44PM -0700, Chao Gao wrote:

Sure. Here is the branch:

https://github.com/gaochaointel/linux-dev/commits/tdx-module-update-v2/

---

## [91] Chao Gao — 2026-01-05
*Subject: Re: [PATCH v2 00/21] Runtime TDX Module update support*

On Fri, Jan 02, 2026 at 01:15:33PM -0800, Dave Hansen wrote:
>On 1/2/26 12:52, Edgecombe, Rick P wrote:>> Would you be able to take a
>look at this series when you get a

Agreed. Please review the dependencies first.

TDX Module update series has three dependencies:

1. Sean's VMXON series:

https://lore.kernel.org/kvm/20251206011054.494190-1-seanjc@google.com/#t

2. TDX host virtual device (the first patch in the series below)

https://lore.kernel.org/kvm/20251117022311.2443900-2-yilun.xu@linux.intel.com/

3. TDX Module version reporting

https://lore.kernel.org/linux-coco/20260105074350.98564-1-chao.gao@intel.com/

---

## [92] Xu Yilun — 2026-01-13
*Subject: Re: [PATCH v2 04/21] x86/virt/tdx: Prepare to support P-SEAMLDR
 SEAMCALLs*

> diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
> index e872a411a359..7ad026618a23 100644

If we do want Patch #3 [*], I think no need to expose this bit in
public, define it in your newly added arch/x86/virt/vmx/tdx/seamcall.h

[*]: https://lore.kernel.org/all/20251001025442.427697-4-chao.gao@intel.com/

[...]

> +static inline bool sc_need_retry(u64 fn, u64 error_code)
> +{

Maybe we can remove this single-use wrapper and integrate it in
sc_retry?

>  static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
>  			   struct tdx_module_args *args)

	u64 retry_code = TDX_RND_NO_ENTROPY;

	if (is_seamldr_call(fn))
		retry_code = SEAMLDR_RND_NO_ENTROPY;

> @@ -22,7 +35,7 @@ static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
>  

	} while (ret == retry_code && --retry);

Seems more straightforward to me.

>  
>  	return ret;

Why we must strip the bit from leaf number? See from P-seamldr SPEC [*],
all leaf definitions are with this bit, same for your C code:

  +/* P-SEAMLDR SEAMCALL leaf function */
  +#define P_SEAMLDR_INFO			0x8000000000000000

So my feeling is, log readability reduces without this bit. We don't
have to make all developers understand this bit, just expose the whole
leaf as magic number.

[*] https://cdrdv2.intel.com/v1/dl/getContent/733584

> +	pr_err("P-SEAMLDR (%lld) failed: 0x%016llx\n", fn, err);

I see no problem we keep both "P-SEAMLDR" string & SEAMLDR bit printed.


And could we handle it the same as sc_retry(), something like:

 static inline void seamcall_err(u64 fn, u64 err, struct tdx_module_args *args)
 {
-       pr_err("SEAMCALL (0x%016llx) failed: 0x%016llx\n", fn, err);
+       char *call = "SEAMCALL";
+
+       if (is_seamldr_call(fn))
+               call = "P-SEAMLDR";
+
+       pr_err("%s (0x%016llx) failed: 0x%016llx\n", call, fn, err);
 }

And the benifit is ...

> +}
> +

... we don't need this definition anymore, just use seamcall_prerr()

---

## [93] Xu Yilun — 2026-01-13
*Subject: Re: [PATCH v2 05/21] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

> diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
> index 58d890fe2100..6b47383d2958 100644

I'm wondering if it is better to put this option in
drivers/virt/coco/tdx-host. Just as TDX Connect, the
functionalities/uAPIs are exposed in /sys/devices/faux/tdx_host. Better
the 2 features could have aligned config pattern. The TDX Connect
configuration is here:

  https://lore.kernel.org/all/20251117022311.2443900-4-yilun.xu@linux.intel.com/

> +
> +	  If unsure, say N.

And I'm wondering if we must disable seamldr core helpers if Update
uAPIs are not selected. TDX core now are expected to expose various
helpers for different features and is it necessary we have to mask
in/out all helpers in such a fine granularity? For example we may not
disable tdh_mem_sept_xx() helpers if KVM_INTEL is not selected.

BTW: We may finally get rid of the dependency between KVM_INTEL & TDX_HOST

-----8<-----
diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
index 80527299f859..e3e90d1fcad3 100644
--- a/arch/x86/Kconfig
+++ b/arch/x86/Kconfig
@@ -1898,7 +1898,6 @@ config INTEL_TDX_HOST
        bool "Intel Trust Domain Extensions (TDX) host support"
        depends on CPU_SUP_INTEL
        depends on X86_64
-       depends on KVM_INTEL
        depends on X86_X2APIC
        select ARCH_KEEP_MEMBLOCK
        depends on CONTIG_ALLOC

[...]

> +static __maybe_unused int seamldr_call(u64 fn, struct tdx_module_args *args)
> +{

As I mentioned, just use seamcall_prerr(). This perfectly illustrates the
main difference between normal seamcalls & seamldr_calls - the additional
VMCS handling.

> +
> +	/*

---

## [94] Xu Yilun — 2026-01-14
*Subject: Re: [PATCH v2 07/21] coco/tdx-host: Expose P-SEAMLDR information via
 sysfs*

On Tue, Sep 30, 2025 at 07:52:51PM -0700, Chao Gao wrote:
> TDX Module updates require userspace to select the appropriate module
> to load. Expose necessary information to facilitate this decision. Two

I don't think we need to worry about whether P-SEAMLDR is loaded or not.
The tdx-host device exists only if TDX Module is loaded, and in turn
P-SEAMLDR is loaded.

> cause seamldr_get_info() to return NULL.
> 

[...]

> +static ssize_t seamldr_version_show(struct device *dev, struct device_attribute *attr,
> +				    char *buf)

I feel it is a little wierd here, need some explaination why use
seamldr_get_info() for visibility. At first glance, I get the impression
that we don't expose the attributes on 1st seamldr_get_info() failure,
and if 1st read success we expose the attributes, then we return read
failure on 2nd seamldr_get_info() failure. That's the motivation I'm
trying to make the logic simpler.

As you said, the purpose of using seamldr_get_info() here is for the 2
checks:

  1. If INTEL_TDX_MODULE_UPDATE is selected.
  2. If P-SEAMLOAD exists.

But P-SEAMLOAD must exist in tdx-host device context. The chain of
dependency is P-SEAMLOAD->TDX Module->tdx host device.

So the logic could be simplified as "if INTEL_TDX_MODULE_UPDATE
selected, expose seamldr sysfs". A common practice maybe:


#ifdef INTEL_TDX_MODULE_UPDATE
> +static struct attribute_group seamldr_group = {
> +	.name = "seamldr",

drop is_visible()

> +};
#endif
> +
> +static const struct attribute_group *tdx_host_groups[] = {

#ifdef INTEL_TDX_MODULE_UPDATE
> +	&seamldr_group,
#endif

The #ifdef should be added for several places, which seems annoying but
may be fine for the first optional feature. Later, could solve this by
splitting the file into tdx-host/main.c tdx-host/update.c
tdx-host/connect.c ...

> +	NULL,
> +};

---

## [95] Xu Yilun — 2026-01-14
*Subject: Re: [PATCH v2 08/21] coco/tdx-host: Implement FW_UPLOAD sysfs ABI
 for TDX Module updates*

On Tue, Sep 30, 2025 at 07:52:52PM -0700, Chao Gao wrote:
> The firmware upload framework provides a standard mechanism for firmware
> updates by allowing device drivers to expose sysfs interfaces for

Make the fdev declaration right before tdx_host_init(), try best to keep
the update stuff in one bluk.

[...]

> +static int seamldr_init(struct device *dev)
> +{

I don't think we fail out the whole tdx-host here. We should skip the
optional feature if it is not supported to allow other features work.
E.g. the TDX Module version, the P-SEAMLOAD version, TDX Connect.

> +	}
> +

Ditto. And keeping num_remaining_updates sysfs node visible and returning 0
is valuable, it clearly tells why update is impossible and aligns with
the situation when the user keeps on updating and exhausts the available
updates.

> +
> +	tdx_fwl = firmware_upload_register(THIS_MODULE, dev, "seamldr_upload",

---

## [96] Xu Yilun — 2026-01-14
*Subject: Re: [PATCH v2 11/21] x86/virt/seamldr: Allocate and populate a
 module update request*

> +/* Allocate and populate a seamldr_params */
> +static struct seamldr_params *alloc_seamldr_params(const void *module, int module_size,

Why we check both IS_ALIGNED(sig_size, SZ_4K) and sig_size != SZ_4K, I
assume the former is redundant.

> +		return ERR_PTR(-EINVAL);
> +

This void * buffer comes from FW_UPLOAD callback, which is a kvmalloc
buffer, so we do vmalloc_to_pfn() here. But that knowledge resides in
FW_UPLOAD driver context, the kAPI entry, seamldr_install_module()
doesn't say that. So could we add the kernel-doc to specify this
"const u8 *data" at ...

... here
>  int seamldr_install_module(const u8 *data, u32 size)
>  {

---

## [97] Duan, Zhenzhong — 2026-01-14
*Subject: Re: [PATCH v2 01/21] x86/virt/tdx: Print SEAMCALL leaf numbers in
 decimal*

On 10/1/2025 10:52 AM, Chao Gao wrote:
> Both TDX spec and kernel defines SEAMCALL leaf numbers as decimal. Printing
> them in hex makes no sense. Correct it.

Reviewed-by: Zhenzhong Duan <zhenzhong.duan@intel.com>

> ---
> v2:

---

## [98] Duan, Zhenzhong — 2026-01-14
*Subject: Re: [PATCH v2 03/21] x86/virt/tdx: Move low level SEAMCALL helpers
 out of <asm/tdx.h>*

On 10/1/2025 10:52 AM, Chao Gao wrote:
> From: Kai Huang <kai.huang@intel.com>
>

Reviewed-by: Zhenzhong Duan <zhenzhong.duan@intel.com>

> ---
> v2:

---

## [99] Duan, Zhenzhong — 2026-01-14
*Subject: Re: [PATCH v2 04/21] x86/virt/tdx: Prepare to support P-SEAMLDR
 SEAMCALLs*

On 10/1/2025 10:52 AM, Chao Gao wrote:
> P-SEAMLDR is another component alongside the TDX module within the
> protected SEAM range. P-SEAMLDR can update the TDX module at runtime.

Do we need to have this check, can TDX module seamcall return

value SEAMLDR_RND_NO_ENTROPY but for different reason?

> +		return error_code == SEAMLDR_RND_NO_ENTROPY;
> +	else

---

## [100] Duan, Zhenzhong — 2026-01-14
*Subject: Re: [PATCH v2 05/21] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On 10/1/2025 10:52 AM, Chao Gao wrote:
> Software needs to talk with P-SEAMLDR via P-SEAMLDR SEAMCALLs. So, add a
> wrapper for P-SEAMLDR SEAMCALLs.

Not clear if seamldr will support other features besides TDX module update,

if yes, maybe more general name CONFIG_INTEL_SEAMLDR?

> diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
> new file mode 100644

---

## [101] Duan, Zhenzhong — 2026-01-14
*Subject: Re: [PATCH v2 06/21] x86/virt/seamldr: Retrieve P-SEAMLDR information*

On 10/1/2025 10:52 AM, Chao Gao wrote:
> P-SEAMLDR returns its information e.g., version and supported features, in
> response to the SEAMLDR.INFO SEAMCALL.
We can trigger seamldr call once and cache the result except seamldr 
itself could be updated.

---

## [102] Xu Yilun — 2026-01-14
*Subject: Re: [PATCH v2 13/21] x86/virt/seamldr: Abort updates if errors
 occurred midway*

On Tue, Sep 30, 2025 at 07:52:57PM -0700, Chao Gao wrote:
> The TDX Module update process has multiple stages, each of which may
> encounter failures.

Could we immediately move to TDP_DONE once the error happens, i.e. no
need to get all ack for current state?

> +		else
> +			set_target_state(tdp_data.state + 1);

----8<-----
  static void ack_state(void)
  {
        if (atomic_read(&tdp_data.failed)) {
                set_target_state(TDP_DONE);
		return;
	}

        if (atomic_dec_and_test(&tdp_data.thread_ack))
                 set_target_state(tdp_data.state + 1);
  }

---

## [103] Xu Yilun — 2026-01-15
*Subject: Re: [PATCH v2 16/21] x86/virt/seamldr: Handle TDX Module update
 failures*

>  static void print_update_failure_message(void)
> @@ -331,7 +323,7 @@ static int do_seamldr_install_module(void *params)

Ah, yes. That's idea of immediate error out I'm thinking of, your
implementation is better.

>  
> 	return ret;

---

## [104] Chao Gao — 2026-01-15
*Subject: Re: [PATCH v2 04/21] x86/virt/tdx: Prepare to support P-SEAMLDR
 SEAMCALLs*

>> diff --git a/arch/x86/virt/vmx/tdx/seamcall.h b/arch/x86/virt/vmx/tdx/seamcall.h
>> index 71b6ffddfa40..3f462e58d68e 100644

Currently, The TDX module doesn't return SEAMLDR_RND_NO_ENTROPY for any reason,
and I think it probably won't in the future. But it isn't ruled out by the
spec. It's the same situation for P-SEAMLDR returning TDX_RND_NO_ENTROPY. So I
slightly prefer to keep this check.

---

## [105] Xu Yilun — 2026-01-15
*Subject: Re: [PATCH v2 17/21] x86/virt/seamldr: Install a new TDX Module*

>  static int do_seamldr_install_module(void *params)
>  {

Is it better we put the definition, or at least the value assignment in
case TDP_CPU_INSTALL? This pattern always appears here for a seamcall
wrapper but this function is far more complex than that.

And the .rcx = __pa(params) also confuse me a bit. Better we name it
e.g. seamldr_params which looks reasonable for seamcall arguments.

>  	enum tdp_state newstate, curstate = TDP_START;
>  	int cpu = smp_processor_id();

---

## [106] Xu Yilun — 2026-01-15
*Subject: Re: [PATCH v2 16/21] x86/virt/seamldr: Handle TDX Module update
 failures*

On Tue, Sep 30, 2025 at 07:53:00PM -0700, Chao Gao wrote:
> Failures encountered after a successful module shutdown are unrecoverable,
> e.g., there is no way to restore the old TDX Module.

"e.g." is obscure. To me, the following sentence is explaining the
reason why the failure is not recoverable. Maybe "i.e." or "because"?

---

## [107] Chao Gao — 2026-01-15
*Subject: Re: [PATCH v2 04/21] x86/virt/tdx: Prepare to support P-SEAMLDR
 SEAMCALLs*

On Tue, Jan 13, 2026 at 05:48:56PM +0800, Xu Yilun wrote:
>> diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
>> index e872a411a359..7ad026618a23 100644

Makes sense.

>
>[*]: https://lore.kernel.org/all/20251001025442.427697-4-chao.gao@intel.com/

I am ok with this change. Will do.

>
>>  

Agree. Printing P-SEAMLDR leaf numbers in hex without removing bit 63 is
better, so the values shown in the logs can match code and spec.

>
>[*] https://cdrdv2.intel.com/v1/dl/getContent/733584

It's doable, but the conditional is unnecessary ...

>
>And the benifit is ...

Having this seamldr_prerr() (and seamldr_err()) is to eliminate that conditional.

---

## [108] Chao Gao — 2026-01-15
*Subject: Re: [PATCH v2 05/21] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On Tue, Jan 13, 2026 at 07:08:37PM +0800, Xu Yilun wrote:
>> diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
>> index 58d890fe2100..6b47383d2958 100644

Agreed. TDX Connect and Module update should align in this matter.
I will move this kconfig under drivers/virt/coco/tdx-host.

>
>> +

I would rather keep this. seamldr.c will have other facilities that are for
updates only. It's better to compile them out if there are no kernel users of
them. I would agree with you if we needed to sprinkle a few #ifdef/#endif
throughout the C file, but that isn't the case as the whole file won't be
compiled.

---

## [109] Chao Gao — 2026-01-15
*Subject: Re: [PATCH v2 05/21] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

>> diff --git a/arch/x86/virt/vmx/tdx/Makefile b/arch/x86/virt/vmx/tdx/Makefile
>> index 90da47eb85ee..26aea3531c36 100644

Currently, no other features. So, CONFIG_INTEL_TDX_MODULE_UPDATE should be
good for now. If some new feature emerges, we can add CONFIG_INTEL_SEAMLDR and
make CONFIG_INTEL_TDX_MODULE_UPDATE and new features select it.

---

## [110] Chao Gao — 2026-01-16
*Subject: Re: [PATCH v2 07/21] coco/tdx-host: Expose P-SEAMLDR information via
 sysfs*

On Wed, Jan 14, 2026 at 09:50:33AM +0800, Xu Yilun wrote:
>On Tue, Sep 30, 2025 at 07:52:51PM -0700, Chao Gao wrote:
>> TDX Module updates require userspace to select the appropriate module

Yes, you are right.

<snip>

>> +static umode_t seamldr_group_is_visible(struct kobject *kobj,
>> +					struct attribute *attr, int n)

Indeed, and the suggested changes below look good to me.

Thanks.

---

## [111] Chao Gao — 2026-01-16
*Subject: Re: [PATCH v2 08/21] coco/tdx-host: Implement FW_UPLOAD sysfs ABI
 for TDX Module updates*

>> +struct tdx_fw_upload_status {
>> +	bool cancel_request;

ok.

>
>[...]

Yes. How about making seamldr_init() return void? Then any failure in setting
up TDX module update won't impact other features of the tdx-host device. e.g.,

diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 540f9af7f81c..d653c594bb94 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -176,32 +176,22 @@ static const struct fw_upload_ops tdx_fw_ops = {
	.cancel = tdx_fw_cancel,
 };
 
-static int seamldr_init(struct device *dev)
+static void seamldr_init(struct device *dev)
 {
-	const struct seamldr_info *seamldr_info = seamldr_get_info();
	const struct tdx_sys_info *tdx_sysinfo = tdx_get_sysinfo();
	int ret;
 
-	if (!tdx_sysinfo || !seamldr_info)
-		return -ENXIO;
+	if (WARN_ON_ONCE(!tdx_sysinfo))
+		return;
 
-	if (!tdx_supports_runtime_update(tdx_sysinfo)) {
+	if (!tdx_supports_runtime_update(tdx_sysinfo))
		pr_info("Current TDX Module cannot be updated. Consider BIOS updates\n");
-		return -EOPNOTSUPP;
-	}
-
-	if (!seamldr_info->num_remaining_updates) {
-		pr_info("P-SEAMLDR doesn't support TDX Module updates\n");
-		return -EOPNOTSUPP;
-	}
 
	tdx_fwl = firmware_upload_register(THIS_MODULE, dev, "seamldr_upload",
					   &tdx_fw_ops, &tdx_fw_upload_status);
	ret = PTR_ERR_OR_ZERO(tdx_fwl);
	if (ret)
		pr_err("failed to register module uploader %d\n", ret);
-
-	return ret;
 }
 
 static void seamldr_deinit(void)
@@ -212,8 +202,8 @@ static void seamldr_deinit(void)
 
 static int tdx_host_probe(struct faux_device *fdev)
 {
-	/* Only support TDX Module updates now. More TDX features could be added here. */
-	return seamldr_init(&fdev->dev);
+	seamldr_init(&fdev->dev);
+	return 0;
 }
 
 static void tdx_host_remove(struct faux_device *fdev)


>
>> +	}

Makes sense. I will drop this check.

>
>> +

---

## [112] Chao Gao — 2026-01-16
*Subject: Re: [PATCH v2 11/21] x86/virt/seamldr: Allocate and populate a
 module update request*

On Wed, Jan 14, 2026 at 02:45:02PM +0800, Xu Yilun wrote:
>> +/* Allocate and populate a seamldr_params */
>> +static struct seamldr_params *alloc_seamldr_params(const void *module, int module_size,

Yes. it is redundant.

But in the next version, I will implement an extension that increases the
sigstruct size limit from a single 4KB page to four 4KB pages, so this will
become:

	/* P-SEAMLDR accepts up to 4 4KB pages for sigstruct */
	if (sig_size > 4 * SZ_4K)
		return ERR_PTR(-EINVAL);

>
>> +		return ERR_PTR(-EINVAL);

Good suggestion. Will do.

---

## [113] Chao Gao — 2026-01-19
*Subject: Re: [PATCH v2 17/21] x86/virt/seamldr: Install a new TDX Module*

On Thu, Jan 15, 2026 at 02:15:31PM +0800, Xu Yilun wrote:
>>  static int do_seamldr_install_module(void *params)
>>  {

Sounds good. I will do the following changes:

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index a0b59d6c53c9..f2933c7e3852 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -313,10 +313,10 @@ static void print_update_failure_message(void)
  * See multi_cpu_stop() from where this multi-cpu state-machine was
  * adopted, and the rationale for touch_nmi_watchdog()
  */
-static int do_seamldr_install_module(void *params)
+static int do_seamldr_install_module(void *seamldr_params)
 {
-	struct tdx_module_args args = { .rcx = __pa(params) };
	enum tdp_state newstate, curstate = TDP_START;
+	struct tdx_module_args args = {};
	int cpu = smp_processor_id();
	bool primary;
	int ret = 0;
@@ -336,6 +336,7 @@ static int do_seamldr_install_module(void *params)
					ret = tdx_module_shutdown();
				break;
			case TDP_CPU_INSTALL:
+				args.rcx = __pa(seamldr_params);
				scoped_guard(raw_spinlock, &seamldr_lock)
					ret = seamldr_call(P_SEAMLDR_INSTALL, &args);
				break;

---

## [114] H. Peter Anvin — 2026-01-18
*Subject: Re: [PATCH v2 16/21] x86/virt/seamldr: Handle TDX Module update failures*

On January 14, 2026 10:24:22 PM PST, Xu Yilun <yilun.xu@linux.intel.com> wrote:
>On Tue, Sep 30, 2025 at 07:53:00PM -0700, Chao Gao wrote:
>> Failures encountered after a successful module shutdown are unrecoverable,

"e.g." (for example) means the following list is non-exhaustive.

---

## [115] Chao Gao — 2026-01-19
*Subject: Re: [PATCH v2 16/21] x86/virt/seamldr: Handle TDX Module update
 failures*

On Sun, Jan 18, 2026 at 08:55:22PM -0800, H. Peter Anvin wrote:
>On January 14, 2026 10:24:22 PM PST, Xu Yilun <yilun.xu@linux.intel.com> wrote:
>>On Tue, Sep 30, 2025 at 07:53:00PM -0700, Chao Gao wrote:

Yes, 'i.e.' or 'because' would be more appropriate since the next sentence
explains 'unrecoverable'.

---

## [116] Chao Gao — 2026-01-19
*Subject: Re: [PATCH v2 14/21] x86/virt/seamldr: Shut down the current TDX
 module*

On Wed, Dec 03, 2025 at 10:24:58AM +0800, Binbin Wu wrote:
>
>

Note: this patch always uses the current TDX module's HV. So, it won't fail
regardlss of No-Downgrade flag.

>
>About "hand-off version" and "No-Downgrade Flag", I still have some questions.

Yes.

>If the newer TDX module built with NO_DOWNGRADE=1, is it possible to downgrade
>to the older TDX module when they are using the same hand-off version?

AFAIK, this is possible in TDX architecture as long as the SEAMSVN (TDX
module's SVN) doesn't downgrade.

But for now, there is no plan to support downgrade (or roll-back) in any case
as it may result in lost features and cause compatibility issues. so, the
userspace tool [1] now rejects any downgrade attempts

[1]: https://github.com/intel/confidential-computing.tdx.tdx-module.binaries/blob/28a4baabc268b1998ec553ab9009f4fd3efd309d/version_select_and_load.py#L301

---

## [117] Chao Gao — 2026-01-19
*Subject: Re: [PATCH v2 19/21] x86/virt/tdx: Establish contexts for the new
 TDX Module*

>> +int tdx_module_run_update(void)
>> +{

Good catch. I will use seamcall_prerr(), which returns an int.

>
>> +	if (ret) {

Yes.

---

## [118] Chao Gao — 2026-01-19
*Subject: Re: [PATCH v2 20/21] x86/virt/tdx: Update tdx_sysinfo and check
 features post-update*

On Wed, Dec 03, 2025 at 03:41:50PM +0800, Binbin Wu wrote:
>
>

ack.

>
>> +		return ret;

Indeed.

>
>> +	new = &info->version;

ok. I will update the log message.

>
>Does it mean after a system reboot, the change done by TD preserving update will

Yes. After reboot, the update will be gone. The (old) TDX module will be
reloaded by the BIOS.

>If we want the TDX module upgrade to be permanent, it needs to replace
>the TDX module binary the BIOS will load, right?

Yes.

>
>So the scenario of TD preserving update seems to be limited to security fixes?

Yes. Fixes (whether security, performance, or functional) will take effect. New
features won't. This series takes a minimalist approach, updating only the
module version and handoff-version while leaving all other TDX metadata
unchanged.

I think this conservative approach is appropriate for initial support. New
features can be gradually enabled later as we prove that other components
(e.g., KVM) are ready for new features introduced via runtime updates.

This enabling approach is aligned with current microcode updates.

---

## [119] Dave Hansen — 2026-01-19
*Subject: Re: [PATCH v2 16/21] x86/virt/seamldr: Handle TDX Module update
 failures*

On 1/18/26 21:34, Chao Gao wrote:
> On Sun, Jan 18, 2026 at 08:55:22PM -0800, H. Peter Anvin wrote:
>> On January 14, 2026 10:24:22 PM PST, Xu Yilun <yilun.xu@linux.intel.com> wrote:

FWIW, I very much prefer plain words. "i.e." and "e.g." are really only
useful if you and all your readers know how they work.

I don't feel the need to be draconian about it, but I frankly *wish*
folks would just remove them from their written vocabulary.

---

## [120] dan.j.williams@intel.com — 2026-01-26
*Subject: Re: [PATCH v2 20/21] x86/virt/tdx: Update tdx_sysinfo and check
 features post-update*

Chao Gao wrote:
[..]
> I think this conservative approach is appropriate for initial support. New
> features can be gradually enabled later as we prove that other components

New features over updates, and revised software contracts (broken
contracts) over updates are not "compatible updates". So it is not a
"conservative approach" to start, it is more a hard barrier that updates
of that nature are out-of-scope via this interface. The Documentation
needs to be clear that the problems caused by update are the Module's
problems, not new kernel problems.

If you look at other platform mutating update mechanisms like ACPI
runtime update and CXL runtime update, the class of updates that expose
new features / contracts require reset. TDX is not special in this
regard.

---
