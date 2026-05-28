---
title: 'Runtime TDX module update support'
date: 2026-05-13
last_reply: 2026-05-20
message_count: 68
participants: ['Chao Gao', 'Dave Hansen', 'Edgecombe, Rick P', 'Binbin Wu']
---

## [1] Chao Gao — 2026-05-13

Hi Dave,

Thanks for your thorough review of v8. This v9 addresses the issues you
pointed out. In particular, it adopts the new tdx_blob format you
suggested, removes module version printing during updates, and reworks
the do-while loop in the update flow to improve readability. It also
adds the two cleanup patches you suggested as patches 1 and 2.

Please take a look at this new version. I hope it can still be merged
for 7.2.
---

(For transparency, note that I used AI tools to help proofread this
cover-letter and commit messages)

This series adds support for runtime TDX module updates that preserve
running TDX guests. It is also available at:

  https://github.com/gaochaointel/linux-dev/commits/tdx-module-updates-v9/

== Background ==

Intel TDX isolates Trusted Domains (TDs), or confidential guests, from the
host. A key component of Intel TDX is the TDX module, which enforces
security policies to protect the memory and CPU states of TDs from the
host. However, the TDX module is software that requires updates.

== Problems ==

Currently, the TDX module is loaded by the BIOS at boot time, and the only
way to update it is through a reboot, which results in significant system
downtime. Users expect the TDX module to be updatable at runtime without
disrupting TDX guests.

== Solution ==

On TDX platforms, P-SEAMLDR[1] is a component within the protected SEAM
range. It is loaded by the BIOS and provides the host with functions to
install a TDX module at runtime.

This series implements runtime TDX module updates through the fw_upload
mechanism. That interface is a good fit because TDX module selection is not
a simple "load a known file from disk" problem. The update image to load
depends on module versioning, compatibility rules. fw_upload lets userspace
choose the module explicitly while the kernel provides the update
mechanism.

This design intentionally keeps most update validation/policy in userspace.
The kernel exposes the information userspace needs, such as TDX module
version and P-SEAMLDR information, but userspace is responsible for
understanding TDX module's versioning and compatibility rules and for
choosing an appropriate update image (see "TDX module versioning" below).

The kernel still enforces the pieces that must be handled in-kernel:

1. Validate the tdx_blob header fields that are not passed through tothe
TDX module. Just the standard overflow and reserved bits defensive ABI stuff.

2. Make sure no non-update SEAMCALLs are called during the update.

3. Make sure SEAMCALLs are on the right CPU, for any the user has made
available to the kernel.

4. Handle the race between updates and concurrent TD builds by
returning -EBUSY to userspace.

Everything else remains a userspace responsibility.

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

NOTE: This v9 uses a new tdx_blob format. The scripts and module blobs in
https://github.com/intel/tdx-module-binaries have not yet been updated
to match this version. Those updates will be done separately later.

== Other information relevant to Runtime TDX module updates ==

=== TDX module versioning ===

Each TDX module is assigned a version number x.y.z, where x represents the
"major" version, y the "minor" version, and z the "update" version.

Runtime TDX module updates are restricted to Z-stream releases.

Note that Z-stream releases do not necessarily guarantee compatibility. A
new release may not be compatible with all previous versions. To address this,
Intel provides a separate file containing compatibility information, which
specifies the minimum module version required for a particular update. This
information is referenced by the tool to determine if two modules are
compatible.

=== TCB Stability ===

Updates change the TCB as viewed by attestation reports. In TDX there is
a distinction between launch-time version and current version where
runtime TDX module updates cause that latter version number to change,
subject to Z-stream constraints.

The concern that a malicious host may attack confidential VMs by loading
insecure updates was addressed by Alex in [3]. Similarly, the scenario
where some "theoretical paranoid tenant" in the cloud wants to audit
updates and stop trusting the host after updates until audit completion
was also addressed in [4]. Users not in the cloud control the host machine
and can manage updates themselves, so they don't have these concerns.

See more about the implications of current TCB version changes in
attestation as summarized by Dave in [5].

=== TDX module Distribution Model ===

At a high level, Intel publishes all TDX modules on the github [2], along
with a mapping_file.json which documents the compatibility information
about each TDX module and a userspace tool to install the TDX module. OS
vendors can package these modules and distribute them. Administrators
install the package and use the tool to select the appropriate TDX module
and install it via the interfaces exposed by this series.

[1]: https://cdrdv2.intel.com/v1/dl/getContent/733584
[2]: https://github.com/intel/tdx-module-binaries
[3]: https://lore.kernel.org/all/665c5ae0-4b7c-4852-8995-255adf7b3a2f@amazon.com/
[4]: https://lore.kernel.org/all/5d1da767-491b-4077-b472-2cc3d73246d6@amazon.com/
[5]: https://lore.kernel.org/all/94d6047e-3b7c-4bc1-819c-85c16ff85abf@intel.com/


Chao Gao (22):
  x86/virt/tdx: Consolidate TDX global initialization states
  x86/virt/tdx: Move TDX_FEATURES0 bits to asm/tdx.h
  coco/tdx-host: Introduce a "tdx_host" device
  coco/tdx-host: Expose TDX module version
  x86/virt/seamldr: Introduce a wrapper for P-SEAMLDR SEAMCALLs
  x86/virt/seamldr: Add a helper to retrieve P-SEAMLDR information
  coco/tdx-host: Expose P-SEAMLDR information via sysfs
  coco/tdx-host: Don't expose P-SEAMLDR information on CPUs with erratum
  coco/tdx-host: Implement firmware upload sysfs ABI for TDX module
    updates
  x86/virt/seamldr: Allocate and populate a module update request
  x86/virt/seamldr: Introduce skeleton for TDX module updates
  x86/virt/seamldr: Abort updates after a failed step
  x86/virt/seamldr: Shut down the current TDX module
  x86/virt/tdx: Reset software states during TDX module shutdown
  x86/virt/seamldr: Install a new TDX module
  x86/virt/seamldr: Do TDX per-CPU initialization after module
    installation
  x86/virt/tdx: Restore TDX module state
  x86/virt/tdx: Refresh TDX module version after update
  x86/virt/tdx: Reject updates during compatibility-sensitive operations
  x86/virt/tdx: Enable TDX module runtime updates
  coco/tdx-host: Document TDX module update compatibility criteria
  x86/virt/tdx: Document TDX module update

Kai Huang (1):
  x86/virt/tdx: Move low level SEAMCALL helpers out of <asm/tdx.h>

 .../ABI/testing/sysfs-devices-faux-tdx-host   |  68 ++++
 Documentation/arch/x86/tdx.rst                |  34 ++
 arch/x86/include/asm/cpufeatures.h            |   1 +
 arch/x86/include/asm/seamldr.h                |  37 +++
 arch/x86/include/asm/tdx.h                    |  67 ++--
 arch/x86/include/asm/tdx_global_metadata.h    |   4 +
 arch/x86/include/asm/vmx.h                    |   1 +
 arch/x86/virt/vmx/tdx/Makefile                |   2 +-
 arch/x86/virt/vmx/tdx/seamcall_internal.h     | 109 +++++++
 arch/x86/virt/vmx/tdx/seamldr.c               | 306 ++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.c                   | 162 ++++++----
 arch/x86/virt/vmx/tdx/tdx.h                   |   8 +-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c   |  17 +-
 drivers/virt/coco/Kconfig                     |   2 +
 drivers/virt/coco/Makefile                    |   1 +
 drivers/virt/coco/tdx-host/Kconfig            |  12 +
 drivers/virt/coco/tdx-host/Makefile           |   1 +
 drivers/virt/coco/tdx-host/tdx-host.c         | 221 +++++++++++++
 18 files changed, 940 insertions(+), 113 deletions(-)
 create mode 100644 Documentation/ABI/testing/sysfs-devices-faux-tdx-host
 create mode 100644 arch/x86/include/asm/seamldr.h
 create mode 100644 arch/x86/virt/vmx/tdx/seamcall_internal.h
 create mode 100644 arch/x86/virt/vmx/tdx/seamldr.c
 create mode 100644 drivers/virt/coco/tdx-host/Kconfig
 create mode 100644 drivers/virt/coco/tdx-host/Makefile
 create mode 100644 drivers/virt/coco/tdx-host/tdx-host.c

base-commit: 5209e5bfe5cab593476c3e7754e42c5e47ce36de

---

## [2] Chao Gao — 2026-05-13
*Subject: [PATCH v9 01/23] x86/virt/tdx: Consolidate TDX global initialization states*

The kernel uses several global flags to guard one-time TDX initialization
flows and prevent them from being repeated.

When the TDX module is updated, all of those states must be reset so that
the module can be initialized again. Today those states are kept as separate
global variables, which makes the reset path awkward and easy to miss when
a new state is added.

Group the states into a single structure so they can be reset together, for
example with memset(), and so a newly added state won't be missed.

Drop the __ro_after_init annotation from tdx_module_initialized because
the other two states do not have it. And with TDX module update support,
all the states need to be writable at runtime.

Signed-off-by: Chao Gao <chao.gao@intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 24 ++++++++++++++----------
 1 file changed, 14 insertions(+), 10 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index c0c6281b08a5..0172b432f229 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -44,6 +44,13 @@
 #include <asm/virt.h>
 #include "tdx.h"
 
+struct tdx_module_state {
+	bool initialized;
+	bool sysinit_done;
+	int sysinit_ret;
+};
+
+static struct tdx_module_state tdx_module_state;
 static u32 tdx_global_keyid __ro_after_init;
 static u32 tdx_guest_keyid_start __ro_after_init;
 static u32 tdx_nr_guest_keyids __ro_after_init;
@@ -58,7 +65,6 @@ static struct tdmr_info_list tdx_tdmr_list;
 static LIST_HEAD(tdx_memlist);
 
 static struct tdx_sys_info tdx_sysinfo __ro_after_init;
-static bool tdx_module_initialized __ro_after_init;
 
 typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);
 
@@ -113,30 +119,28 @@ static int try_init_module_global(void)
 {
 	struct tdx_module_args args = {};
 	static DEFINE_RAW_SPINLOCK(sysinit_lock);
-	static bool sysinit_done;
-	static int sysinit_ret;
 
 	raw_spin_lock(&sysinit_lock);
 
-	if (sysinit_done)
+	if (tdx_module_state.sysinit_done)
 		goto out;
 
 	/* RCX is module attributes and all bits are reserved */
 	args.rcx = 0;
-	sysinit_ret = seamcall_prerr(TDH_SYS_INIT, &args);
+	tdx_module_state.sysinit_ret = seamcall_prerr(TDH_SYS_INIT, &args);
 
 	/*
 	 * The first SEAMCALL also detects the TDX module, thus
 	 * it can fail due to the TDX module is not loaded.
 	 * Dump message to let the user know.
 	 */
-	if (sysinit_ret == -ENODEV)
+	if (tdx_module_state.sysinit_ret == -ENODEV)
 		pr_err("module not loaded\n");
 
-	sysinit_done = true;
+	tdx_module_state.sysinit_done = true;
 out:
 	raw_spin_unlock(&sysinit_lock);
-	return sysinit_ret;
+	return tdx_module_state.sysinit_ret;
 }
 
 /**
@@ -1299,7 +1303,7 @@ static __init int tdx_enable(void)
 
 	register_syscore(&tdx_syscore);
 
-	tdx_module_initialized = true;
+	tdx_module_state.initialized = true;
 	pr_info("TDX-Module initialized\n");
 	return 0;
 }
@@ -1554,7 +1558,7 @@ void __init tdx_init(void)
 
 const struct tdx_sys_info *tdx_get_sysinfo(void)
 {
-	if (!tdx_module_initialized)
+	if (!tdx_module_state.initialized)
 		return NULL;
 
 	return (const struct tdx_sys_info *)&tdx_sysinfo;

---

## [3] Chao Gao — 2026-05-13
*Subject: [PATCH v9 02/23] x86/virt/tdx: Move TDX_FEATURES0 bits to asm/tdx.h*

Move the TDX_FEATURES0 bit definitions from the private TDX header to
asm/tdx.h, and opportunistically switch to BIT_ULL() since TDX_FEATURES0 is
64-bit.

This prepares for TDX module update [1] and Dynamic PAMT [2] support. Both
add new TDX_FEATURES0 capability bits, and both need those capabilities to
be queried from code outside arch/x86/virt. The corresponding feature-query
helpers therefore need to live in the public asm/tdx.h header, so move the
existing bit definitions there first.

No functional change intended.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Link: https://lore.kernel.org/kvm/20260427152854.101171-17-chao.gao@intel.com/ # [1]
Link: https://lore.kernel.org/kvm/20251121005125.417831-16-rick.p.edgecombe@intel.com/ # [2]
---
 arch/x86/include/asm/tdx.h  | 3 +++
 arch/x86/virt/vmx/tdx/tdx.h | 3 ---
 2 files changed, 3 insertions(+), 3 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 15eac89b0afb..e2430dd0e4d5 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -32,6 +32,9 @@
 #define TDX_SUCCESS		0ULL
 #define TDX_RND_NO_ENTROPY	0x8000020300000000ULL
 
+/* Bit definitions of TDX_FEATURES0 metadata field */
+#define TDX_FEATURES0_NO_RBP_MOD	BIT_ULL(18)
+
 #ifndef __ASSEMBLER__
 
 #include <uapi/asm/mce.h>
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index e2cf2dd48755..76c5fb1e1ffe 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -85,9 +85,6 @@ struct tdmr_info {
 	DECLARE_FLEX_ARRAY(struct tdmr_reserved_area, reserved_areas);
 } __packed __aligned(TDMR_INFO_ALIGNMENT);
 
-/* Bit definitions of TDX_FEATURES0 metadata field */
-#define TDX_FEATURES0_NO_RBP_MOD	BIT(18)
-
 /*
  * Do not put any hardware-defined TDX structure representations below
  * this comment!

---

## [4] Chao Gao — 2026-05-13
*Subject: [PATCH v9 03/23] x86/virt/tdx: Move low level SEAMCALL helpers out of <asm/tdx.h>*

From: Kai Huang <kai.huang@intel.com>

TDX host core code implements three seamcall*() helpers to make SEAMCALLs
to the TDX module.  Currently, they are implemented in <asm/tdx.h> and
are exposed to other kernel code which includes <asm/tdx.h>.

However, other than the TDX host core, seamcall*() are not expected to
be used by other kernel code directly.  For instance, for all SEAMCALLs
that are used by KVM, the TDX host core exports a wrapper function for
each of them.

Move seamcall*() and related code out of <asm/tdx.h> and make them only
visible to TDX host core.

Since TDX host core tdx.c is already very heavy, don't put low level
seamcall*() code there but to a new dedicated "seamcall_internal.h".  Also,
currently tdx.c has seamcall_prerr*() helpers which additionally print
error message when calling seamcall*() fails.  Move them to
"seamcall_internal.h" as well. In such way all low level SEAMCALL helpers
are in a dedicated place, which is much more readable.

Copy the copyright notice from the original files and consolidate the
date ranges to:

	Copyright (C) 2021-2023 Intel Corporation

Signed-off-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>
Reviewed-by: Vishal Annapurve <vannapurve@google.com>
Acked-by: Dave Hansen <dave.hansen@linux.intel.com>
---
 arch/x86/include/asm/tdx.h                |  47 ----------
 arch/x86/virt/vmx/tdx/seamcall_internal.h | 109 ++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.c               |  47 +---------
 3 files changed, 111 insertions(+), 92 deletions(-)
 create mode 100644 arch/x86/virt/vmx/tdx/seamcall_internal.h

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index e2430dd0e4d5..8b739ac01479 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -100,54 +100,7 @@ static inline long tdx_kvm_hypercall(unsigned int nr, unsigned long p1,
 #endif /* CONFIG_INTEL_TDX_GUEST && CONFIG_KVM_GUEST */
 
 #ifdef CONFIG_INTEL_TDX_HOST
-u64 __seamcall(u64 fn, struct tdx_module_args *args);
-u64 __seamcall_ret(u64 fn, struct tdx_module_args *args);
-u64 __seamcall_saved_ret(u64 fn, struct tdx_module_args *args);
 void tdx_init(void);
-
-#include <linux/preempt.h>
-#include <asm/archrandom.h>
-#include <asm/processor.h>
-
-typedef u64 (*sc_func_t)(u64 fn, struct tdx_module_args *args);
-
-static __always_inline u64 __seamcall_dirty_cache(sc_func_t func, u64 fn,
-						  struct tdx_module_args *args)
-{
-	lockdep_assert_preemption_disabled();
-
-	/*
-	 * SEAMCALLs are made to the TDX module and can generate dirty
-	 * cachelines of TDX private memory.  Mark cache state incoherent
-	 * so that the cache can be flushed during kexec.
-	 *
-	 * This needs to be done before actually making the SEAMCALL,
-	 * because kexec-ing CPU could send NMI to stop remote CPUs,
-	 * in which case even disabling IRQ won't help here.
-	 */
-	this_cpu_write(cache_state_incoherent, true);
-
-	return func(fn, args);
-}
-
-static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
-			   struct tdx_module_args *args)
-{
-	int retry = RDRAND_RETRY_LOOPS;
-	u64 ret;
-
-	do {
-		preempt_disable();
-		ret = __seamcall_dirty_cache(func, fn, args);
-		preempt_enable();
-	} while (ret == TDX_RND_NO_ENTROPY && --retry);
-
-	return ret;
-}
-
-#define seamcall(_fn, _args)		sc_retry(__seamcall, (_fn), (_args))
-#define seamcall_ret(_fn, _args)	sc_retry(__seamcall_ret, (_fn), (_args))
-#define seamcall_saved_ret(_fn, _args)	sc_retry(__seamcall_saved_ret, (_fn), (_args))
 const char *tdx_dump_mce_info(struct mce *m);
 const struct tdx_sys_info *tdx_get_sysinfo(void);
 
diff --git a/arch/x86/virt/vmx/tdx/seamcall_internal.h b/arch/x86/virt/vmx/tdx/seamcall_internal.h
new file mode 100644
index 000000000000..be5f446467df
--- /dev/null
+++ b/arch/x86/virt/vmx/tdx/seamcall_internal.h
@@ -0,0 +1,109 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+/*
+ * SEAMCALL utilities for TDX host-side operations.
+ *
+ * Provides convenient wrappers around SEAMCALL assembly with retry logic,
+ * error reporting and cache coherency tracking.
+ *
+ * Copyright (C) 2021-2023 Intel Corporation
+ */
+
+#ifndef _X86_VIRT_SEAMCALL_INTERNAL_H
+#define _X86_VIRT_SEAMCALL_INTERNAL_H
+
+#include <linux/printk.h>
+#include <linux/types.h>
+#include <asm/archrandom.h>
+#include <asm/processor.h>
+#include <asm/tdx.h>
+
+u64 __seamcall(u64 fn, struct tdx_module_args *args);
+u64 __seamcall_ret(u64 fn, struct tdx_module_args *args);
+u64 __seamcall_saved_ret(u64 fn, struct tdx_module_args *args);
+
+typedef u64 (*sc_func_t)(u64 fn, struct tdx_module_args *args);
+
+static __always_inline u64 __seamcall_dirty_cache(sc_func_t func, u64 fn,
+						  struct tdx_module_args *args)
+{
+	lockdep_assert_preemption_disabled();
+
+	/*
+	 * SEAMCALLs are made to the TDX module and can generate dirty
+	 * cachelines of TDX private memory.  Mark cache state incoherent
+	 * so that the cache can be flushed during kexec.
+	 *
+	 * This needs to be done before actually making the SEAMCALL,
+	 * because kexec-ing CPU could send NMI to stop remote CPUs,
+	 * in which case even disabling IRQ won't help here.
+	 */
+	this_cpu_write(cache_state_incoherent, true);
+
+	return func(fn, args);
+}
+
+static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
+			   struct tdx_module_args *args)
+{
+	int retry = RDRAND_RETRY_LOOPS;
+	u64 ret;
+
+	do {
+		preempt_disable();
+		ret = __seamcall_dirty_cache(func, fn, args);
+		preempt_enable();
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
+	pr_err("SEAMCALL (0x%016llx) failed: 0x%016llx\n", fn, err);
+}
+
+static inline void seamcall_err_ret(u64 fn, u64 err,
+				    struct tdx_module_args *args)
+{
+	seamcall_err(fn, err, args);
+	pr_err("RCX 0x%016llx RDX 0x%016llx R08 0x%016llx\n",
+			args->rcx, args->rdx, args->r8);
+	pr_err("R09 0x%016llx R10 0x%016llx R11 0x%016llx\n",
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
+#endif /* _X86_VIRT_SEAMCALL_INTERNAL_H */
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 0172b432f229..a0f8cf5e10d7 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -42,6 +42,8 @@
 #include <asm/processor.h>
 #include <asm/mce.h>
 #include <asm/virt.h>
+
+#include "seamcall_internal.h"
 #include "tdx.h"
 
 struct tdx_module_state {
@@ -66,51 +68,6 @@ static LIST_HEAD(tdx_memlist);
 
 static struct tdx_sys_info tdx_sysinfo __ro_after_init;
 
-typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);
-
-static inline void seamcall_err(u64 fn, u64 err, struct tdx_module_args *args)
-{
-	pr_err("SEAMCALL (0x%016llx) failed: 0x%016llx\n", fn, err);
-}
-
-static inline void seamcall_err_ret(u64 fn, u64 err,
-				    struct tdx_module_args *args)
-{
-	seamcall_err(fn, err, args);
-	pr_err("RCX 0x%016llx RDX 0x%016llx R08 0x%016llx\n",
-			args->rcx, args->rdx, args->r8);
-	pr_err("R09 0x%016llx R10 0x%016llx R11 0x%016llx\n",
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
  * It can be done on any cpu, and from task or IRQ context.

---

## [5] Chao Gao — 2026-05-13
*Subject: [PATCH v9 04/23] coco/tdx-host: Introduce a "tdx_host" device*

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
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>
Link: https://lore.kernel.org/all/2025073035-bulginess-rematch-b92e@gregkh/ # [1]
---
 arch/x86/virt/vmx/tdx/tdx.c           |  2 +-
 drivers/virt/coco/Kconfig             |  2 ++
 drivers/virt/coco/Makefile            |  1 +
 drivers/virt/coco/tdx-host/Kconfig    | 10 +++++++
 drivers/virt/coco/tdx-host/Makefile   |  1 +
 drivers/virt/coco/tdx-host/tdx-host.c | 43 +++++++++++++++++++++++++++
 6 files changed, 58 insertions(+), 1 deletion(-)
 create mode 100644 drivers/virt/coco/tdx-host/Kconfig
 create mode 100644 drivers/virt/coco/tdx-host/Makefile
 create mode 100644 drivers/virt/coco/tdx-host/tdx-host.c

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index a0f8cf5e10d7..837e9b36e1ea 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1520,7 +1520,7 @@ const struct tdx_sys_info *tdx_get_sysinfo(void)
 
 	return (const struct tdx_sys_info *)&tdx_sysinfo;
 }
-EXPORT_SYMBOL_FOR_KVM(tdx_get_sysinfo);
+EXPORT_SYMBOL_FOR_MODULES(tdx_get_sysinfo, "kvm-intel,tdx-host");
 
 u32 tdx_get_nr_guest_keyids(void)
 {
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
diff --git a/drivers/virt/coco/tdx-host/Makefile b/drivers/virt/coco/tdx-host/Makefile
new file mode 100644
index 000000000000..e61e749a8dff
--- /dev/null
+++ b/drivers/virt/coco/tdx-host/Makefile
@@ -0,0 +1 @@
+obj-$(CONFIG_TDX_HOST_SERVICES) += tdx-host.o
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

## [6] Chao Gao — 2026-05-13
*Subject: [PATCH v9 05/23] coco/tdx-host: Expose TDX module version*

For TDX module updates, userspace needs to select compatible update
versions based on the current module version. This design delegates
module selection complexity to userspace because TDX module update
policies are complex and version series are platform-specific.

For example, the 1.5.x series is for certain platform generations, while
the 2.0.x series is intended for others. And TDX module 1.5.x may be
updated to 1.5.y but not to 1.5.y+1.

Expose the TDX module version to userspace via sysfs to aid module
selection. Since the TDX faux device will drive module updates, expose
the version as its attribute.

One bonus of exposing TDX module version via sysfs is: TDX module
version information remains available even after dmesg logs are cleared.

Define TDX_VERSION_FMT macro for the TDX version format since it will be
used multiple times. Also convert an existing print statement to use it.

== Background ==

The "faux device + device attribute" approach compares to other update
mechanisms as follows:

1. AMD SEV leverages an existing PCI device for the PSP to expose
   metadata. TDX uses a faux device as it doesn't have PCI device
   in its architecture.

2. Microcode uses per-CPU virtual devices to report microcode revisions
   because CPUs can have different revisions. But, there is only a
   single TDX module, so exposing the TDX module version through a global
   TDX faux device is appropriate

3. ARM's CCA implementation isn't in-tree yet, but will likely follow a
   similar faux device approach, though it's unclear whether they need
   to expose firmware version information

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>
Link: https://lore.kernel.org/all/2025073035-bulginess-rematch-b92e@gregkh/ # [1]
---
 .../ABI/testing/sysfs-devices-faux-tdx-host   |  6 +++++
 arch/x86/include/asm/tdx.h                    |  6 +++++
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c   |  2 +-
 drivers/virt/coco/tdx-host/tdx-host.c         | 26 ++++++++++++++++++-
 4 files changed, 38 insertions(+), 2 deletions(-)
 create mode 100644 Documentation/ABI/testing/sysfs-devices-faux-tdx-host

diff --git a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
new file mode 100644
index 000000000000..2cf682b65acf
--- /dev/null
+++ b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
@@ -0,0 +1,6 @@
+What:		/sys/devices/faux/tdx_host/version
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) Report the version of the loaded TDX module. The TDX module
+		version is formatted as x.y.z, where "x" is the major version,
+		"y" is the minor version and "z" is the update version. Versions
+		are used for bug reporting, TDX module updates etc.
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 8b739ac01479..b7f4396b5cc5 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -41,6 +41,12 @@
 #include <asm/tdx_global_metadata.h>
 #include <linux/pgtable.h>
 
+/*
+ * TDX module and P-SEAMLDR version convention: "major.minor.update"
+ * (e.g., "1.5.08") with zero-padded two-digit update field.
+ */
+#define TDX_VERSION_FMT "%u.%u.%02u"
+
 /*
  * Used by the #VE exception handler to gather the #VE exception
  * info from the TDX module. This is a software only structure
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index c7db393a9cfb..d54d4227990c 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -106,7 +106,7 @@ static __init int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 
 	ret = ret ?: get_tdx_sys_info_version(&sysinfo->version);
 
-	pr_info("Module version: %u.%u.%02u\n",
+	pr_info("Module version: " TDX_VERSION_FMT "\n",
 		sysinfo->version.major_version,
 		sysinfo->version.minor_version,
 		sysinfo->version.update_version);
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index c77885392b09..ef117a836b3a 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -8,6 +8,7 @@
 #include <linux/device/faux.h>
 #include <linux/module.h>
 #include <linux/mod_devicetable.h>
+#include <linux/sysfs.h>
 
 #include <asm/cpu_device_id.h>
 #include <asm/tdx.h>
@@ -18,6 +19,29 @@ static const struct x86_cpu_id tdx_host_ids[] = {
 };
 MODULE_DEVICE_TABLE(x86cpu, tdx_host_ids);
 
+static ssize_t version_show(struct device *dev, struct device_attribute *attr,
+			    char *buf)
+{
+	const struct tdx_sys_info *tdx_sysinfo = tdx_get_sysinfo();
+	const struct tdx_sys_info_version *ver;
+
+	if (!tdx_sysinfo)
+		return -ENXIO;
+
+	ver = &tdx_sysinfo->version;
+
+	return sysfs_emit(buf, TDX_VERSION_FMT "\n", ver->major_version,
+						     ver->minor_version,
+						     ver->update_version);
+}
+static DEVICE_ATTR_RO(version);
+
+static struct attribute *tdx_host_attrs[] = {
+	&dev_attr_version.attr,
+	NULL,
+};
+ATTRIBUTE_GROUPS(tdx_host);
+
 static struct faux_device *fdev;
 
 static int __init tdx_host_init(void)
@@ -25,7 +49,7 @@ static int __init tdx_host_init(void)
 	if (!x86_match_cpu(tdx_host_ids) || !tdx_get_sysinfo())
 		return -ENODEV;
 
-	fdev = faux_device_create(KBUILD_MODNAME, NULL, NULL);
+	fdev = faux_device_create_with_groups(KBUILD_MODNAME, NULL, NULL, tdx_host_groups);
 	if (!fdev)
 		return -ENODEV;

---

## [7] Chao Gao — 2026-05-13
*Subject: [PATCH v9 06/23] x86/virt/seamldr: Introduce a wrapper for P-SEAMLDR SEAMCALLs*

The TDX architecture uses the "SEAMCALL" instruction to communicate with
SEAM mode software. Right now, the only SEAM mode software that the kernel
communicates with is the TDX module. But, there is actually another
component that runs in SEAM mode but it is separate from the TDX module:
the persistent SEAM loader or "P-SEAMLDR". Right now, the only component
that communicates with it is the BIOS which loads the TDX module itself at
boot. But, to support updating the TDX module, the kernel now needs to be
able to talk to it.

P-SEAMLDR SEAMCALLs differ from TDX module SEAMCALLs in areas such as
concurrency requirements. Add a P-SEAMLDR wrapper to handle these
differences and prepare for implementing concrete functions.

Use seamcall_prerr() (not '_ret') because current P-SEAMLDR calls do not
use any output registers other than RAX.

Note that unlike P-SEAMLDR, there is also a non-persistent SEAM loader
("NP-SEAMLDR"). This is an authenticated code module (ACM) that is not
callable at runtime. Only BIOS launches it to load P-SEAMLDR at boot;
the kernel does not need to interact with it for runtime update.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Link: https://cdrdv2.intel.com/v1/dl/getContent/733582 # [1]
---
 arch/x86/virt/vmx/tdx/Makefile  |  2 +-
 arch/x86/virt/vmx/tdx/seamldr.c | 25 +++++++++++++++++++++++++
 2 files changed, 26 insertions(+), 1 deletion(-)
 create mode 100644 arch/x86/virt/vmx/tdx/seamldr.c

diff --git a/arch/x86/virt/vmx/tdx/Makefile b/arch/x86/virt/vmx/tdx/Makefile
index 90da47eb85ee..d1dbc5cc5697 100644
--- a/arch/x86/virt/vmx/tdx/Makefile
+++ b/arch/x86/virt/vmx/tdx/Makefile
@@ -1,2 +1,2 @@
 # SPDX-License-Identifier: GPL-2.0-only
-obj-y += seamcall.o tdx.o
+obj-y += seamcall.o seamldr.o tdx.o
diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
new file mode 100644
index 000000000000..65616dd2f4d2
--- /dev/null
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -0,0 +1,25 @@
+// SPDX-License-Identifier: GPL-2.0
+/*
+ * P-SEAMLDR support for TDX module management features like runtime updates
+ *
+ * Copyright (C) 2025 Intel Corporation
+ */
+#define pr_fmt(fmt)	"seamldr: " fmt
+
+#include <linux/spinlock.h>
+
+#include "seamcall_internal.h"
+
+/*
+ * Serialize P-SEAMLDR calls since the hardware only allows a single CPU to
+ * interact with P-SEAMLDR simultaneously. Use raw version as the calls can
+ * be made with interrupts disabled, where plain spinlocks are prohibited in
+ * PREEMPT_RT kernels as they become sleeping locks.
+ */
+static DEFINE_RAW_SPINLOCK(seamldr_lock);
+
+static __maybe_unused int seamldr_call(u64 fn, struct tdx_module_args *args)
+{
+	guard(raw_spinlock)(&seamldr_lock);
+	return seamcall_prerr(fn, args);
+}

---

## [8] Chao Gao — 2026-05-13
*Subject: [PATCH v9 07/23] x86/virt/seamldr: Add a helper to retrieve P-SEAMLDR information*

P-SEAMLDR reports its state via SEAMLDR.INFO, including its version and
the number of remaining runtime updates.

This information is useful for userspace. For example, the admin can use
the P-SEAMLDR version to determine whether a candidate TDX module is
compatible with the running loader, and can use the remaining update count
to determine whether another runtime update is still possible.

Add a helper to retrieve P-SEAMLDR information in preparation for
exposing P-SEAMLDR version and other necessary information to userspace.
Export the new kAPI for use by tdx-host.ko.

Note that there are two distinct P-SEAMLDR APIs with similar names:

  SEAMLDR.INFO: Returns a SEAMLDR_INFO structure containing SEAMLDR
                information such as version and remaining updates.

  SEAMLDR.SEAMINFO: Returns a SEAMLDR_SEAMINFO structure containing SEAM
                    and system information such as Convertible Memory
		    Regions (CMRs) and number of CPUs and sockets.

The former is used here.

For details, see "Intel® Trust Domain Extensions - SEAM Loader (SEAMLDR)
Interface Specification".

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
 arch/x86/include/asm/seamldr.h  | 36 +++++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/seamldr.c | 20 +++++++++++++++++-
 2 files changed, 55 insertions(+), 1 deletion(-)
 create mode 100644 arch/x86/include/asm/seamldr.h

diff --git a/arch/x86/include/asm/seamldr.h b/arch/x86/include/asm/seamldr.h
new file mode 100644
index 000000000000..c67e5bc910a9
--- /dev/null
+++ b/arch/x86/include/asm/seamldr.h
@@ -0,0 +1,36 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+#ifndef _ASM_X86_SEAMLDR_H
+#define _ASM_X86_SEAMLDR_H
+
+#include <linux/types.h>
+
+/*
+ * This is called the "SEAMLDR_INFO" data structure and is defined
+ * in "SEAM Loader (SEAMLDR) Interface Specification".
+ *
+ * The SEAMLDR.INFO documentation requires this to be aligned to a
+ * 256-byte boundary.
+ */
+struct seamldr_info {
+	u32	version;
+	u32	attributes;
+	u32	vendor_id;
+	u32	build_date;
+	u16	build_num;
+	u16	minor_version;
+	u16	major_version;
+	u16	update_version;
+	u32	acm_x2apicid;
+	u32	num_remaining_updates;
+	u8	seam_info[128];
+	u8	seam_ready;
+	u8	seam_debug;
+	u8	p_seam_ready;
+	u8	reserved[93];
+} __packed __aligned(256);
+
+static_assert(sizeof(struct seamldr_info) == 256);
+
+int seamldr_get_info(struct seamldr_info *seamldr_info);
+
+#endif /* _ASM_X86_SEAMLDR_H */
diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 65616dd2f4d2..7269a239bc22 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -8,8 +8,13 @@
 
 #include <linux/spinlock.h>
 
+#include <asm/seamldr.h>
+
 #include "seamcall_internal.h"
 
+/* P-SEAMLDR SEAMCALL leaf function */
+#define P_SEAMLDR_INFO			0x8000000000000000
+
 /*
  * Serialize P-SEAMLDR calls since the hardware only allows a single CPU to
  * interact with P-SEAMLDR simultaneously. Use raw version as the calls can
@@ -18,8 +23,21 @@
  */
 static DEFINE_RAW_SPINLOCK(seamldr_lock);
 
-static __maybe_unused int seamldr_call(u64 fn, struct tdx_module_args *args)
+static int seamldr_call(u64 fn, struct tdx_module_args *args)
 {
 	guard(raw_spinlock)(&seamldr_lock);
 	return seamcall_prerr(fn, args);
 }
+
+int seamldr_get_info(struct seamldr_info *seamldr_info)
+{
+	struct tdx_module_args args = {};
+
+	/*
+	 * Use slow_virt_to_phys() since @seamldr_info may be allocated on
+	 * the stack.
+	 */
+	args.rcx = slow_virt_to_phys(seamldr_info);
+	return seamldr_call(P_SEAMLDR_INFO, &args);
+}
+EXPORT_SYMBOL_FOR_MODULES(seamldr_get_info, "tdx-host");

---

## [9] Chao Gao — 2026-05-13
*Subject: [PATCH v9 08/23] coco/tdx-host: Expose P-SEAMLDR information via sysfs*

TDX module updates require userspace to select the appropriate module
to load. Expose necessary information to facilitate this decision. Two
values are needed:

- P-SEAMLDR version: for compatibility checks between TDX module and
		     P-SEAMLDR
- num_remaining_updates: indicates how many updates can be performed

Expose them as tdx-host device attributes. Make seamldr attributes
visible only when the update feature is supported, as that's their sole
purpose.

Note that the underlying P-SEAMLDR attributes are available regardless of
update support; this only restricts their visibility in Linux.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
---
v8:
 - explain when the two attributes are available and how they relate to TDX
 module update support [Rick]
 - drop erratum stuff [Rick, Dave]
 - drop the separate directory for p-seamldr attributes [Dave]
 - s/SEAM loader/P-SEAMLDR
 - don't use DEFINE_SIMPLE_SYSFS_GROUP_VISIBLE() as it doesn't work on
 an unnamed group.
---
 .../ABI/testing/sysfs-devices-faux-tdx-host   | 22 +++++++
 arch/x86/include/asm/tdx.h                    |  6 ++
 drivers/virt/coco/tdx-host/tdx-host.c         | 65 ++++++++++++++++++-
 3 files changed, 92 insertions(+), 1 deletion(-)

diff --git a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
index 2cf682b65acf..65897fe6abc0 100644
--- a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
+++ b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
@@ -4,3 +4,25 @@ Description:	(RO) Report the version of the loaded TDX module. The TDX module
 		version is formatted as x.y.z, where "x" is the major version,
 		"y" is the minor version and "z" is the update version. Versions
 		are used for bug reporting, TDX module updates etc.
+
+What:		/sys/devices/faux/tdx_host/seamldr_version
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) Report the version of the loaded P-SEAMLDR. The P-SEAMLDR
+		version is formatted as x.y.z, where "x" is the major version,
+		"y" is the minor version and "z" is the update version. Versions
+		are used for bug reporting and compatibility checks.
+
+What:		/sys/devices/faux/tdx_host/num_remaining_updates
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) Report the number of remaining updates. TDX maintains a
+		log about each TDX module that has been loaded. This log has
+		a finite size, which limits the number of TDX module updates
+		that can be performed.
+
+		After each successful update, the number reduces by one. Once it
+		reaches zero, further updates will fail until next reboot. The
+		number is always zero if the P-SEAMLDR doesn't support updates.
+
+		See Intel® Trust Domain Extensions - SEAM Loader (SEAMLDR)
+		Interface Specification, Chapter "SEAMLDR_INFO" and Chapter
+		"SEAMLDR.INSTALL" for more information.
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index b7f4396b5cc5..27376db7ddac 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -110,6 +110,12 @@ void tdx_init(void);
 const char *tdx_dump_mce_info(struct mce *m);
 const struct tdx_sys_info *tdx_get_sysinfo(void);
 
+static inline bool tdx_supports_runtime_update(const struct tdx_sys_info *sysinfo)
+{
+	/* To be enabled when kernel is ready. */
+	return false;
+}
+
 int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index ef117a836b3a..079913dcc888 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -11,6 +11,7 @@
 #include <linux/sysfs.h>
 
 #include <asm/cpu_device_id.h>
+#include <asm/seamldr.h>
 #include <asm/tdx.h>
 
 static const struct x86_cpu_id tdx_host_ids[] = {
@@ -40,7 +41,69 @@ static struct attribute *tdx_host_attrs[] = {
 	&dev_attr_version.attr,
 	NULL,
 };
-ATTRIBUTE_GROUPS(tdx_host);
+
+static const struct attribute_group tdx_host_group = {
+	.attrs = tdx_host_attrs,
+};
+
+static ssize_t seamldr_version_show(struct device *dev, struct device_attribute *attr,
+				    char *buf)
+{
+	struct seamldr_info info;
+	int ret;
+
+	ret = seamldr_get_info(&info);
+	if (ret)
+		return ret;
+
+	return sysfs_emit(buf, TDX_VERSION_FMT "\n", info.major_version,
+						     info.minor_version,
+						     info.update_version);
+}
+
+static ssize_t num_remaining_updates_show(struct device *dev,
+					  struct device_attribute *attr,
+					  char *buf)
+{
+	struct seamldr_info info;
+	int ret;
+
+	ret = seamldr_get_info(&info);
+	if (ret)
+		return ret;
+
+	return sysfs_emit(buf, "%u\n", info.num_remaining_updates);
+}
+
+static DEVICE_ATTR_ADMIN_RO(seamldr_version);
+static DEVICE_ATTR_ADMIN_RO(num_remaining_updates);
+
+static struct attribute *seamldr_attrs[] = {
+	&dev_attr_seamldr_version.attr,
+	&dev_attr_num_remaining_updates.attr,
+	NULL,
+};
+
+static umode_t seamldr_group_visible(struct kobject *kobj, struct attribute *attr, int idx)
+{
+	const struct tdx_sys_info *sysinfo = tdx_get_sysinfo();
+
+	if (!sysinfo)
+		return 0;
+
+	return tdx_supports_runtime_update(sysinfo) ? attr->mode : 0;
+}
+
+static const struct attribute_group seamldr_group = {
+	.attrs = seamldr_attrs,
+	.is_visible = seamldr_group_visible,
+};
+
+static const struct attribute_group *tdx_host_groups[] = {
+	&tdx_host_group,
+	&seamldr_group,
+	NULL,
+};
 
 static struct faux_device *fdev;

---

## [10] Chao Gao — 2026-05-13
*Subject: [PATCH v9 09/23] coco/tdx-host: Don't expose P-SEAMLDR information on CPUs with erratum*

Some TDX-capable CPUs have an erratum, as documented in Intel® Trust
Domain CPU Architectural Extensions (May 2021 edition) Chapter 2.3:

  SEAMRET from the P-SEAMLDR clears the current VMCS structure pointed
  to by the current-VMCS pointer. A VMM that invokes the P-SEAMLDR using
  SEAMCALL must reload the current-VMCS, if required, using the VMPTRLD
  instruction.

Clearing the current VMCS behind KVM's back will break KVM.

This erratum is not present when IA32_VMX_BASIC[60] is set. Add a CPU
bug bit for this erratum and refuse to expose P-SEAMLDR information
on affected CPUs, because even reading the P-SEAMLDR sysfs knobs would
enter and exit P-SEAMLDR.

Use a CPU bug bit to stay consistent with X86_BUG_TDX_PW_MCE. As a bonus,
the bug bit is visible to userspace, which allows userspace to determine
why these sysfs files are not exposed, and it can also be checked by other
kernel components in the future if needed.

== Alternatives ==
Two workarounds were considered but both were rejected:

1. Save/restore the current VMCS around P-SEAMLDR calls. This produces ugly
   assembly code [1] and doesn't play well with #MCE or #NMI if they
   need to use the current VMCS.

2. Move KVM's VMCS tracking logic to the TDX core code, which would break
   the boundary between KVM and the TDX core code [2].

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Link: https://lore.kernel.org/kvm/fedb3192-e68c-423c-93b2-a4dc2f964148@intel.com/ # [1]
Link: https://lore.kernel.org/kvm/aYIXFmT-676oN6j0@google.com/ # [2]
---
This is split into a separate patch rather than folded into the previous one,
because the erratum handling warrants a longer changelog and discussion of
the alternatives.
---
 arch/x86/include/asm/cpufeatures.h    |  1 +
 arch/x86/include/asm/vmx.h            |  1 +
 arch/x86/virt/vmx/tdx/tdx.c           | 11 +++++++++++
 drivers/virt/coco/tdx-host/tdx-host.c |  8 ++++++++
 4 files changed, 21 insertions(+)

diff --git a/arch/x86/include/asm/cpufeatures.h b/arch/x86/include/asm/cpufeatures.h
index 1d506e5d6f46..7b572bc24265 100644
--- a/arch/x86/include/asm/cpufeatures.h
+++ b/arch/x86/include/asm/cpufeatures.h
@@ -573,4 +573,5 @@
 #define X86_BUG_ITS_NATIVE_ONLY		X86_BUG( 1*32+ 8) /* "its_native_only" CPU is affected by ITS, VMX is not affected */
 #define X86_BUG_TSA			X86_BUG( 1*32+ 9) /* "tsa" CPU is affected by Transient Scheduler Attacks */
 #define X86_BUG_VMSCAPE			X86_BUG( 1*32+10) /* "vmscape" CPU is affected by VMSCAPE attacks from guests */
+#define X86_BUG_SEAMRET_INVD_VMCS	X86_BUG( 1*32+11) /* "seamret_invd_vmcs" SEAMRET from P-SEAMLDR clears the current VMCS */
 #endif /* _ASM_X86_CPUFEATURES_H */
diff --git a/arch/x86/include/asm/vmx.h b/arch/x86/include/asm/vmx.h
index 37080382df54..49d8551d285d 100644
--- a/arch/x86/include/asm/vmx.h
+++ b/arch/x86/include/asm/vmx.h
@@ -147,6 +147,7 @@ struct vmcs {
 #define VMX_BASIC_INOUT				BIT_ULL(54)
 #define VMX_BASIC_TRUE_CTLS			BIT_ULL(55)
 #define VMX_BASIC_NO_HW_ERROR_CODE_CC		BIT_ULL(56)
+#define VMX_BASIC_NO_SEAMRET_INVD_VMCS		BIT_ULL(60)
 
 static inline u32 vmx_basic_vmcs_revision_id(u64 vmx_basic)
 {
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 837e9b36e1ea..1621695d7561 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -42,6 +42,7 @@
 #include <asm/processor.h>
 #include <asm/mce.h>
 #include <asm/virt.h>
+#include <asm/vmx.h>
 
 #include "seamcall_internal.h"
 #include "tdx.h"
@@ -1443,6 +1444,8 @@ static struct notifier_block tdx_memory_nb = {
 
 static void __init check_tdx_erratum(void)
 {
+	u64 basic_msr;
+
 	/*
 	 * These CPUs have an erratum.  A partial write from non-TD
 	 * software (e.g. via MOVNTI variants or UC/WC mapping) to TDX
@@ -1454,6 +1457,14 @@ static void __init check_tdx_erratum(void)
 	case INTEL_EMERALDRAPIDS_X:
 		setup_force_cpu_bug(X86_BUG_TDX_PW_MCE);
 	}
+
+	/*
+	 * Some TDX-capable CPUs have an erratum where the current VMCS is
+	 * cleared after calling into P-SEAMLDR.
+	 */
+	rdmsrq(MSR_IA32_VMX_BASIC, basic_msr);
+	if (!(basic_msr & VMX_BASIC_NO_SEAMRET_INVD_VMCS))
+		setup_force_cpu_bug(X86_BUG_SEAMRET_INVD_VMCS);
 }
 
 void __init tdx_init(void)
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 079913dcc888..a540d658757b 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -91,6 +91,14 @@ static umode_t seamldr_group_visible(struct kobject *kobj, struct attribute *att
 	if (!sysinfo)
 		return 0;
 
+	/*
+	 * Calling P-SEAMLDR on CPUs with the seamret_invd_vmcs bug clears
+	 * the current VMCS, which breaks KVM. Verify the erratum is not
+	 * present before exposing P-SEAMLDR features.
+	 */
+	if (boot_cpu_has_bug(X86_BUG_SEAMRET_INVD_VMCS))
+		return 0;
+
 	return tdx_supports_runtime_update(sysinfo) ? attr->mode : 0;
 }

---

## [11] Chao Gao — 2026-05-13
*Subject: [PATCH v9 10/23] coco/tdx-host: Implement firmware upload sysfs ABI for TDX module updates*

tl;dr: Select fw_upload for doing TDX module updates. The process of
selecting among available update images is complicated and nuanced. Punt
the selection policy out to userspace.

Long Version:

Linux kernel supports two primary firmware update mechanisms:
  - request_firmware()
  - firmware upload (or fw_upload)

The former is used by microcode updates, SEV firmware updates, etc. The
latter is used by CXL and FPGA firmware updates.

One key difference between them is: request_firmware() loads a named
file from the filesystem where the filename is kernel-controlled, while
fw_upload accepts firmware data directly from userspace.

Use fw_upload for TDX module updates as loading a named file isn't
suitable for TDX (see below for more reasons). Specifically, register
TDX faux device with fw_upload framework to expose sysfs interfaces
and implement operations to process data blobs supplied by userspace.

Why fw_upload instead of request_firmware()?
============================================
The explicit file selection capabilities of fw_upload is preferred over
the implicit file selection of request_firmware() for the following
reasons:

a. Intel distributes all versions of the TDX module, allowing admins to
load any version rather than always defaulting to the latest. This
flexibility is necessary because future extensions may require reverting to
a previous version to clear fatal errors.

b. Some module version series are platform-specific. For example, the 1.5.x
series is for certain platform generations, while the 2.0.x series is
intended for others.

c. The update policy for TDX module updates is non-linear at times. The
latest TDX module may not be compatible. For example, TDX module 1.5.x
may be updated to 1.5.y but not to 1.5.y+1. This policy is documented
separately in a file released along with each TDX module release.

So, the default policy of "request_firmware()" of "always load latest", is
not suitable for TDX. Userspace needs to deploy a more sophisticated policy
check (e.g., latest may not be compatible), and there is potential
operator choice to consider.

Just have userspace pick rather than add kernel mechanism to change the
default policy of request_firmware().

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Link: https://lore.kernel.org/kvm/01fc8946-eb84-46fa-9458-f345dd3f6033@intel.com/
---
Dave also suggested making .poll_complete() optional in fw_upload_ops.
That will be handled in a separate series.

v9:
 - add a TL;DR to state the implementation choice up front [Dave]
 - s/can_expose_seamldr()/supports_runtime_update()/ [Dave]
---
 arch/x86/include/asm/seamldr.h        |  1 +
 arch/x86/virt/vmx/tdx/seamldr.c       | 15 +++++
 drivers/virt/coco/tdx-host/Kconfig    |  2 +
 drivers/virt/coco/tdx-host/tdx-host.c | 87 ++++++++++++++++++++++++++-
 4 files changed, 102 insertions(+), 3 deletions(-)

diff --git a/arch/x86/include/asm/seamldr.h b/arch/x86/include/asm/seamldr.h
index c67e5bc910a9..ac6f80f7208b 100644
--- a/arch/x86/include/asm/seamldr.h
+++ b/arch/x86/include/asm/seamldr.h
@@ -32,5 +32,6 @@ struct seamldr_info {
 static_assert(sizeof(struct seamldr_info) == 256);
 
 int seamldr_get_info(struct seamldr_info *seamldr_info);
+int seamldr_install_module(const u8 *data, u32 size);
 
 #endif /* _ASM_X86_SEAMLDR_H */
diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 7269a239bc22..7b345000d7c3 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -6,6 +6,7 @@
  */
 #define pr_fmt(fmt)	"seamldr: " fmt
 
+#include <linux/mm.h>
 #include <linux/spinlock.h>
 
 #include <asm/seamldr.h>
@@ -41,3 +42,17 @@ int seamldr_get_info(struct seamldr_info *seamldr_info)
 	return seamldr_call(P_SEAMLDR_INFO, &args);
 }
 EXPORT_SYMBOL_FOR_MODULES(seamldr_get_info, "tdx-host");
+
+/**
+ * seamldr_install_module - Install a new TDX module.
+ * @data: Pointer to the TDX module image.
+ * @size: Size of the TDX module image.
+ *
+ * Returns 0 on success, negative error code on failure.
+ */
+int seamldr_install_module(const u8 *data, u32 size)
+{
+	/* TODO: Update TDX module here */
+	return 0;
+}
+EXPORT_SYMBOL_FOR_MODULES(seamldr_install_module, "tdx-host");
diff --git a/drivers/virt/coco/tdx-host/Kconfig b/drivers/virt/coco/tdx-host/Kconfig
index d35d85ef91c0..ca600a39d97b 100644
--- a/drivers/virt/coco/tdx-host/Kconfig
+++ b/drivers/virt/coco/tdx-host/Kconfig
@@ -1,6 +1,8 @@
 config TDX_HOST_SERVICES
 	tristate "TDX Host Services Driver"
 	depends on INTEL_TDX_HOST
+	select FW_LOADER
+	select FW_UPLOAD
 	default m
 	help
 	  Enable access to TDX host services like module update and
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index a540d658757b..c4c099cf3de1 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -6,6 +6,7 @@
  */
 
 #include <linux/device/faux.h>
+#include <linux/firmware.h>
 #include <linux/module.h>
 #include <linux/mod_devicetable.h>
 #include <linux/sysfs.h>
@@ -84,7 +85,7 @@ static struct attribute *seamldr_attrs[] = {
 	NULL,
 };
 
-static umode_t seamldr_group_visible(struct kobject *kobj, struct attribute *attr, int idx)
+static bool supports_runtime_update(void)
 {
 	const struct tdx_sys_info *sysinfo = tdx_get_sysinfo();
 
@@ -99,7 +100,12 @@ static umode_t seamldr_group_visible(struct kobject *kobj, struct attribute *att
 	if (boot_cpu_has_bug(X86_BUG_SEAMRET_INVD_VMCS))
 		return 0;
 
-	return tdx_supports_runtime_update(sysinfo) ? attr->mode : 0;
+	return tdx_supports_runtime_update(sysinfo);
+}
+
+static umode_t seamldr_group_visible(struct kobject *kobj, struct attribute *attr, int idx)
+{
+	return supports_runtime_update() ? attr->mode : 0;
 }
 
 static const struct attribute_group seamldr_group = {
@@ -113,6 +119,81 @@ static const struct attribute_group *tdx_host_groups[] = {
 	NULL,
 };
 
+static enum fw_upload_err tdx_fw_prepare(struct fw_upload *fwl,
+					 const u8 *data, u32 size)
+{
+	return FW_UPLOAD_ERR_NONE;
+}
+
+static enum fw_upload_err tdx_fw_write(struct fw_upload *fwl, const u8 *data,
+				       u32 offset, u32 size, u32 *written)
+{
+	int ret;
+
+	ret = seamldr_install_module(data, size);
+	switch (ret) {
+	case 0:
+		*written = size;
+		return FW_UPLOAD_ERR_NONE;
+	default:
+		return FW_UPLOAD_ERR_FW_INVALID;
+	}
+}
+
+static enum fw_upload_err tdx_fw_poll_complete(struct fw_upload *fwl)
+{
+	/*
+	 * The upload completed during tdx_fw_write().
+	 * Never poll for completion.
+	 */
+	return FW_UPLOAD_ERR_NONE;
+}
+
+
+static void tdx_fw_cancel(struct fw_upload *fwl)
+{
+	/*
+	 * TDX module updates are not cancellable.
+	 * Provide a no-op callback to satisfy fw_upload_ops.
+	 */
+}
+
+static const struct fw_upload_ops tdx_fw_ops = {
+	.prepare	= tdx_fw_prepare,
+	.write		= tdx_fw_write,
+	.poll_complete	= tdx_fw_poll_complete,
+	.cancel		= tdx_fw_cancel,
+};
+
+static void seamldr_deinit(void *tdx_fwl)
+{
+	firmware_upload_unregister(tdx_fwl);
+}
+
+static int seamldr_init(struct device *dev)
+{
+	struct fw_upload *tdx_fwl;
+
+	if (!supports_runtime_update())
+		return 0;
+
+	tdx_fwl = firmware_upload_register(THIS_MODULE, dev, "tdx_module",
+					   &tdx_fw_ops, NULL);
+	if (IS_ERR(tdx_fwl))
+		return PTR_ERR(tdx_fwl);
+
+	return devm_add_action_or_reset(dev, seamldr_deinit, tdx_fwl);
+}
+
+static int tdx_host_probe(struct faux_device *fdev)
+{
+	return seamldr_init(&fdev->dev);
+}
+
+static const struct faux_device_ops tdx_host_ops = {
+	.probe		= tdx_host_probe,
+};
+
 static struct faux_device *fdev;
 
 static int __init tdx_host_init(void)
@@ -120,7 +201,7 @@ static int __init tdx_host_init(void)
 	if (!x86_match_cpu(tdx_host_ids) || !tdx_get_sysinfo())
 		return -ENODEV;
 
-	fdev = faux_device_create_with_groups(KBUILD_MODNAME, NULL, NULL, tdx_host_groups);
+	fdev = faux_device_create_with_groups(KBUILD_MODNAME, NULL, &tdx_host_ops, tdx_host_groups);
 	if (!fdev)
 		return -ENODEV;

---

## [12] Chao Gao — 2026-05-13
*Subject: [PATCH v9 11/23] x86/virt/seamldr: Allocate and populate a module update request*

There are two important ABIs here:

'struct tdx_image'	- The on-disk and in-memory format for a TDX
			  module update image.
'struct seamldr_params'	- The in-memory ABI passed to the TDX module
			  loader. Points to a single 'struct tdx_image'

Userspace supplies the update image in struct tdx_image format. The image
consists of a header followed by a sigstruct and the module binary.

P-SEAMLDR, however, consumes struct seamldr_params rather than the image
directly. Parse the struct tdx_image provided by userspace and populate a
matching struct seamldr_params.

Validate the struct tdx_image header before using it, because the header is
consumed solely by the kernel to locate the sigstruct and module within
the image. Do not validate the payload itself. The sigstruct and module
pages are passed through to P-SEAMLDR, which validates them as part of the
update flow.

Signed-off-by: Chao Gao <chao.gao@intel.com>
---
sigstruct_pages_pa_list currently has only one entry, but it will grow to
four pages in the future. Keep it as an array for symmetry with
module_pages_pa_list and for extensibility.

v9:
 - define a new format, basically don't use offset_of_module but use
   sigstruct/module_nr_pages if the offset should be paged-aligned. this
   saves alignment checks and bound checks.
 - add a tdx_image_header struct to avoid using sizeof() for a struct with
   variable array.
 - rewrite the changelog to call out that this patch is to convert an ABI from
   what userspace provides to an ABI the P-SEAMLDR consums.
 - minimize casts and shifts and weird math
---
 arch/x86/virt/vmx/tdx/seamldr.c | 126 +++++++++++++++++++++++++++++++-
 1 file changed, 125 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 7b345000d7c3..929203ec96f2 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -7,6 +7,7 @@
 #define pr_fmt(fmt)	"seamldr: " fmt
 
 #include <linux/mm.h>
+#include <linux/slab.h>
 #include <linux/spinlock.h>
 
 #include <asm/seamldr.h>
@@ -16,6 +17,33 @@
 /* P-SEAMLDR SEAMCALL leaf function */
 #define P_SEAMLDR_INFO			0x8000000000000000
 
+#define SEAMLDR_MAX_NR_MODULE_PAGES	496
+#define SEAMLDR_MAX_NR_SIG_PAGES	1
+
+/*
+ * The seamldr_params "scenario" field specifies the operation mode:
+ * 0: Install TDX module from scratch (not used by kernel)
+ * 1: Update existing TDX module to a compatible version
+ */
+#define SEAMLDR_SCENARIO_UPDATE		1
+
+/*
+ * This is called the "SEAMLDR_PARAMS" data structure and is defined
+ * in "SEAM Loader (SEAMLDR) Interface Specification".
+ *
+ * It describes the TDX module that will be installed.
+ */
+struct seamldr_params {
+	u32	version;
+	u32	scenario;
+	u64	sigstruct_pages_pa_list[SEAMLDR_MAX_NR_SIG_PAGES];
+	u8	reserved[104];
+	u64	module_nr_pages;
+	u64	module_pages_pa_list[SEAMLDR_MAX_NR_MODULE_PAGES];
+} __packed;
+
+static_assert(sizeof(struct seamldr_params) == 4096);
+
 /*
  * Serialize P-SEAMLDR calls since the hardware only allows a single CPU to
  * interact with P-SEAMLDR simultaneously. Use raw version as the calls can
@@ -43,6 +71,89 @@ int seamldr_get_info(struct seamldr_info *seamldr_info)
 }
 EXPORT_SYMBOL_FOR_MODULES(seamldr_get_info, "tdx-host");
 
+#define TDX_IMAGE_VERSION_2		0x200
+
+struct tdx_image_header {
+	u16	version; // This ABI is always 0x200
+	u16	checksum;
+	u8	signature[8];
+	u32	sigstruct_nr_pages;
+	u32	module_nr_pages;
+	u8	reserved[4076];
+} __packed;
+
+#define HEADER_SIZE sizeof(struct tdx_image_header)
+static_assert(HEADER_SIZE == 4096);
+
+/* Intel TDX module update ABI structure. aka. "TDX module blob". */
+struct tdx_image {
+	struct tdx_image_header header;
+	u8 payload[]; // Contains sigstruct pages followed by module pages
+};
+
+static void populate_pa_list(u64 *pa_list, u32 max_entries, const u8 *start, u32 nr_pages)
+{
+	int i;
+
+	nr_pages = MIN(nr_pages, max_entries);
+	for (i = 0; i < nr_pages; i++) {
+		pa_list[i] = vmalloc_to_pfn(start) << PAGE_SHIFT;
+		start += PAGE_SIZE;
+	}
+}
+
+static void populate_seamldr_params(struct seamldr_params *params,
+				    const u8 *sig, u32 sig_nr_pages,
+				    const u8 *mod, u32 mod_nr_pages)
+{
+	params->version			= 0;
+	params->scenario		= SEAMLDR_SCENARIO_UPDATE;
+	params->module_nr_pages		= mod_nr_pages;
+
+	populate_pa_list(params->sigstruct_pages_pa_list, SEAMLDR_MAX_NR_SIG_PAGES,
+			 sig, sig_nr_pages);
+	populate_pa_list(params->module_pages_pa_list, SEAMLDR_MAX_NR_MODULE_PAGES,
+			 mod, mod_nr_pages);
+}
+
+static int init_seamldr_params(struct seamldr_params *params, const u8 *data, u32 size)
+{
+	const struct tdx_image *image		= (const void *)data;
+	const struct tdx_image_header *header	= &image->header;
+
+	u32 sigstruct_len	= header->sigstruct_nr_pages * PAGE_SIZE;
+	u32 module_len		= header->module_nr_pages * PAGE_SIZE;
+
+	u8 *header_start	= (u8 *)header;
+	u8 *header_end		= header_start + HEADER_SIZE;
+
+	u8 *sigstruct_start	= header_end;
+	u8 *sigstruct_end	= sigstruct_start + sigstruct_len;
+
+	u8 *module_start	= sigstruct_end;
+
+	/* Check the calculated payload size against the data size. */
+	if (HEADER_SIZE + sigstruct_len + module_len != size)
+		return -EINVAL;
+
+	/*
+	 * Don't care about user passing the wrong file, but protect
+	 * kernel ABI by preventing accepting garbage.
+	 */
+	if (header->version != TDX_IMAGE_VERSION_2)
+		return -EINVAL;
+
+	if (memcmp(header->signature, "TDX-BLOB", sizeof(header->signature)))
+		return -EINVAL;
+
+	if (memchr_inv(header->reserved, 0, sizeof(header->reserved)))
+		return -EINVAL;
+
+	populate_seamldr_params(params, sigstruct_start, header->sigstruct_nr_pages,
+				module_start, header->module_nr_pages);
+	return 0;
+}
+
 /**
  * seamldr_install_module - Install a new TDX module.
  * @data: Pointer to the TDX module image.
@@ -52,7 +163,20 @@ EXPORT_SYMBOL_FOR_MODULES(seamldr_get_info, "tdx-host");
  */
 int seamldr_install_module(const u8 *data, u32 size)
 {
+	struct seamldr_params *params;
+	int ret;
+
+	params = kzalloc_obj(*params);
+	if (!params)
+		return -ENOMEM;
+
+	ret = init_seamldr_params(params, data, size);
+	if (ret)
+		goto out;
+
 	/* TODO: Update TDX module here */
-	return 0;
+out:
+	kfree(params);
+	return ret;
 }
 EXPORT_SYMBOL_FOR_MODULES(seamldr_install_module, "tdx-host");

---

## [13] Chao Gao — 2026-05-13
*Subject: [PATCH v9 12/23] x86/virt/seamldr: Introduce skeleton for TDX module updates*

TDX module updates require careful synchronization with other TDX
operations. The requirements are (#1/#2 reflect current behavior that
must be preserved):

1. SEAMCALLs need to be callable from both process and IRQ contexts.
2. SEAMCALLs need to be able to run concurrently across CPUs
3. During updates, only update-related SEAMCALLs are permitted; all
   other SEAMCALLs shouldn't be called.
4. During updates, all online CPUs must participate in the update work.

No single lock primitive satisfies all requirements. For instance,
rwlock_t handles #1/#2 but fails #4: CPUs spinning with IRQs disabled
cannot be directed to perform update work.

Use stop_machine() as it is the only well-understood mechanism that can
meet all requirements.

And TDX module updates consist of several steps (See Intel® Trust Domain
Extensions (Intel® TDX) Module Base Architecture Specification, Chapter
"TD-Preserving TDX module Update"). Ordering requirements between steps
mandate lockstep synchronization across all CPUs.

multi_cpu_stop() provides a good example of executing a multi-step task
in lockstep across CPUs, but it does not synchronize the individual
steps inside the callback itself.

Implement a similar state machine as the skeleton for TDX module
updates. Each state represents one step in the update flow, and the
state advances only after all CPUs acknowledge completion of the current
step. This acknowledgment mechanism provides the required lockstep
execution.

The update flow is intentionally simpler than multi_cpu_stop() in two ways:

  a) use a spinlock to protect the control data instead of atomic_t and
     explicit memory barriers.

  b) omit touch_nmi_watchdog() and rcu_momentary_eqs(), which exist
     there for debugging and are not strictly needed for this update flow

Potential alternative to stop_machine()
=======================================
An alternative approach is to lock all KVM entry points and kick all
vCPUs. Here, KVM entry points refer to KVM VM/vCPU ioctl entry points,
implemented in KVM common code (virt/kvm). Adding a locking mechanism
there would affect all architectures KVM supports. And to lock only TDX
vCPUs, new logic would be needed to identify TDX vCPUs, which the KVM
common code currently lacks. This would add significant complexity and
maintenance overhead to KVM for this TDX-specific use case, so don't take
this approach.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v9:
 - Extract control-data initialization into a separate helper. [Dave]
 - Drop touch_nmi_watchdog() and rcu_momentary_eqs(), as they are not
   needed here.
 - Rename thread_ack to num_ack to make it clear that it counts the
   number of acknowledgments.
 - Rename set_target_state() to __set_target_state() to mark it as an
   internal helper. Add a comment noting that __set_target_state()
   does not take the lock, unlike ack_state().
 - Update the changelog to explain why a spinlock is used instead of
   atomic_t plus memory barriers to protect the control data.
---
 arch/x86/virt/vmx/tdx/seamldr.c | 87 ++++++++++++++++++++++++++++++++-
 1 file changed, 86 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 929203ec96f2..7befe4a08f33 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -7,8 +7,10 @@
 #define pr_fmt(fmt)	"seamldr: " fmt
 
 #include <linux/mm.h>
+#include <linux/nmi.h>
 #include <linux/slab.h>
 #include <linux/spinlock.h>
+#include <linux/stop_machine.h>
 
 #include <asm/seamldr.h>
 
@@ -154,6 +156,84 @@ static int init_seamldr_params(struct seamldr_params *params, const u8 *data, u3
 	return 0;
 }
 
+/*
+ * During a TDX module update, all CPUs start from MODULE_UPDATE_START and
+ * progress to MODULE_UPDATE_DONE. Each state is associated with certain
+ * work. For some states, just one CPU needs to perform the work, while
+ * other CPUs just wait during those states.
+ */
+enum module_update_state {
+	MODULE_UPDATE_START,
+	MODULE_UPDATE_DONE,
+};
+
+static struct update_ctrl {
+	enum module_update_state state;
+	int num_ack;
+	/*
+	 * Protect update_ctrl. Raw spinlock as it will be acquired from
+	 * interrupt-disabled contexts.
+	 */
+	raw_spinlock_t lock;
+} update_ctrl;
+
+/* Called with ctrl->lock held or during initialization. */
+static void __set_target_state(struct update_ctrl *ctrl,
+			       enum module_update_state newstate)
+{
+	/* Reset ack counter. */
+	ctrl->num_ack = 0;
+	ctrl->state = newstate;
+}
+
+/* Last one to ack a state moves to the next state. */
+static void ack_state(struct update_ctrl *ctrl)
+{
+	raw_spin_lock(&ctrl->lock);
+
+	ctrl->num_ack++;
+	if (ctrl->num_ack == num_online_cpus())
+		__set_target_state(ctrl, ctrl->state + 1);
+
+	raw_spin_unlock(&ctrl->lock);
+}
+
+static void init_state(struct update_ctrl *ctrl)
+{
+	raw_spin_lock_init(&ctrl->lock);
+	__set_target_state(ctrl, MODULE_UPDATE_START + 1);
+}
+
+/*
+ * See multi_cpu_stop() from where this multi-cpu state-machine was
+ * adopted.
+ */
+static int do_seamldr_install_module(void *seamldr_params)
+{
+	enum module_update_state newstate, curstate = MODULE_UPDATE_START;
+	int ret = 0;
+
+	do {
+		newstate = READ_ONCE(update_ctrl.state);
+
+		if (curstate == newstate) {
+			cpu_relax();
+			continue;
+		}
+
+		curstate = newstate;
+		switch (curstate) {
+		/* TODO: add the update steps. */
+		default:
+			break;
+		}
+
+		ack_state(&update_ctrl);
+	} while (curstate != MODULE_UPDATE_DONE);
+
+	return ret;
+}
+
 /**
  * seamldr_install_module - Install a new TDX module.
  * @data: Pointer to the TDX module image.
@@ -174,7 +254,12 @@ int seamldr_install_module(const u8 *data, u32 size)
 	if (ret)
 		goto out;
 
-	/* TODO: Update TDX module here */
+	/* Ensure a stable set of online CPUs for the update process. */
+	cpus_read_lock();
+	init_state(&update_ctrl);
+	ret = stop_machine_cpuslocked(do_seamldr_install_module, params, cpu_online_mask);
+	cpus_read_unlock();
+
 out:
 	kfree(params);
 	return ret;

---

## [14] Chao Gao — 2026-05-13
*Subject: [PATCH v9 13/23] x86/virt/seamldr: Abort updates after a failed step*

A TDX module update is a multi-step process, and any step can fail.

The current update flow continues to later steps after an error.
Continuing after a failure can leave the TDX module in an unrecoverable
state.

One failure case must remain recoverable: update contention with an ongoing
TD build. The agreed kernel behavior for this case [1] is to fail the
update with -EBUSY so userspace can retry later.

Abort the update on any failure. This also makes the TD-build contention
case recoverable, because that failure occurs before any TDX module state
is changed. Apply the same rule to all errors instead of special-casing
-EBUSY.

Track per-step failures, stop the update loop once a failure is observed,
and do not advance the state machine to the next step.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Link: https://lore.kernel.org/linux-coco/aQFmOZCdw64z14cJ@google.com/ # [1]
---
v9:
  - Avoid nested if/else by deferring failure accounting to ack_state().
  - Reduce indentation of the main flow.
  - Convert the failed flag into a counter. This avoids a conditional
    update of the flag; the counter can simply accumulate failures.
---
 arch/x86/virt/vmx/tdx/seamldr.c | 11 +++++++----
 1 file changed, 7 insertions(+), 4 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 7befe4a08f33..48fe71319fea 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -170,6 +170,7 @@ enum module_update_state {
 static struct update_ctrl {
 	enum module_update_state state;
 	int num_ack;
+	int num_failed;
 	/*
 	 * Protect update_ctrl. Raw spinlock as it will be acquired from
 	 * interrupt-disabled contexts.
@@ -187,12 +188,13 @@ static void __set_target_state(struct update_ctrl *ctrl,
 }
 
 /* Last one to ack a state moves to the next state. */
-static void ack_state(struct update_ctrl *ctrl)
+static void ack_state(struct update_ctrl *ctrl, int result)
 {
 	raw_spin_lock(&ctrl->lock);
 
+	ctrl->num_failed += !!result;
 	ctrl->num_ack++;
-	if (ctrl->num_ack == num_online_cpus())
+	if (ctrl->num_ack == num_online_cpus() && !ctrl->num_failed)
 		__set_target_state(ctrl, ctrl->state + 1);
 
 	raw_spin_unlock(&ctrl->lock);
@@ -202,6 +204,7 @@ static void init_state(struct update_ctrl *ctrl)
 {
 	raw_spin_lock_init(&ctrl->lock);
 	__set_target_state(ctrl, MODULE_UPDATE_START + 1);
+	ctrl->num_failed = 0;
 }
 
 /*
@@ -228,8 +231,8 @@ static int do_seamldr_install_module(void *seamldr_params)
 			break;
 		}
 
-		ack_state(&update_ctrl);
-	} while (curstate != MODULE_UPDATE_DONE);
+		ack_state(&update_ctrl, ret);
+	} while (curstate != MODULE_UPDATE_DONE && !READ_ONCE(update_ctrl.num_failed));
 
 	return ret;
 }

---

## [15] Chao Gao — 2026-05-13
*Subject: [PATCH v9 14/23] x86/virt/seamldr: Shut down the current TDX module*

The first step of TDX module updates is shutting down the current TDX
module. This step also packs state information that needs to be
preserved across updates as handoff data, which will be consumed by the
updated module. The handoff data is stored internally in the SEAM range
and is hidden from the kernel.

To ensure a successful update, the new module must be able to consume
the handoff data generated by the old module. Since handoff data layout
may change between modules, the handoff data is versioned. Each module
has a native handoff version and provides backward support for several
older versions.

The complete handoff versioning protocol is complex as it supports both
module upgrades and downgrades. See details in Intel® Trust Domain
Extensions (Intel® TDX) Module Base Architecture Specification, Chapter
"Handoff Versioning".

Ideally, the kernel needs to retrieve the handoff versions supported by
the current module and the new module and select a version supported by
both. But, since this implementation chooses to only support module
upgrades, simply request the current module to generate handoff data
using its highest supported version, expecting that the new module will
likely support it.

Retrieve the module's handoff version from TDX global metadata and add an
update step to shut down the module. Module shutdown has global effect, so
it only needs to run on one CPU.

Note that the handoff information isn't cached in tdx_sysinfo. It is used
only for module shutdown, and is present only when the TDX module supports
updates. Caching it in get_tdx_sys_info() would require extra update-support
guards and refreshing the cached value across module updates.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
---
v9:
 - Use CPU0 as the primary CPU
---
 arch/x86/include/asm/tdx_global_metadata.h  |  4 ++++
 arch/x86/virt/vmx/tdx/seamldr.c             | 15 ++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx.c                 | 19 ++++++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx.h                 |  3 +++
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c | 13 +++++++++++++
 5 files changed, 52 insertions(+), 2 deletions(-)

diff --git a/arch/x86/include/asm/tdx_global_metadata.h b/arch/x86/include/asm/tdx_global_metadata.h
index 40689c8dc67e..41150d546589 100644
--- a/arch/x86/include/asm/tdx_global_metadata.h
+++ b/arch/x86/include/asm/tdx_global_metadata.h
@@ -40,6 +40,10 @@ struct tdx_sys_info_td_conf {
 	u64 cpuid_config_values[128][2];
 };
 
+struct tdx_sys_info_handoff {
+	u16 module_hv;
+};
+
 struct tdx_sys_info {
 	struct tdx_sys_info_version version;
 	struct tdx_sys_info_features features;
diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 48fe71319fea..6114cab46196 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -15,6 +15,7 @@
 #include <asm/seamldr.h>
 
 #include "seamcall_internal.h"
+#include "tdx.h"
 
 /* P-SEAMLDR SEAMCALL leaf function */
 #define P_SEAMLDR_INFO			0x8000000000000000
@@ -164,6 +165,7 @@ static int init_seamldr_params(struct seamldr_params *params, const u8 *data, u3
  */
 enum module_update_state {
 	MODULE_UPDATE_START,
+	MODULE_UPDATE_SHUTDOWN,
 	MODULE_UPDATE_DONE,
 };
 
@@ -214,8 +216,16 @@ static void init_state(struct update_ctrl *ctrl)
 static int do_seamldr_install_module(void *seamldr_params)
 {
 	enum module_update_state newstate, curstate = MODULE_UPDATE_START;
+	int cpu = smp_processor_id();
+	bool primary;
 	int ret = 0;
 
+	/*
+	 * Use CPU 0 to execute update steps that must run exactly once.
+	 * Note CPU 0 is always online.
+	 */
+	primary = cpu == 0;
+
 	do {
 		newstate = READ_ONCE(update_ctrl.state);
 
@@ -226,7 +236,10 @@ static int do_seamldr_install_module(void *seamldr_params)
 
 		curstate = newstate;
 		switch (curstate) {
-		/* TODO: add the update steps. */
+		case MODULE_UPDATE_SHUTDOWN:
+			if (primary)
+				ret = tdx_module_shutdown();
+			break;
 		default:
 			break;
 		}
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 1621695d7561..da3c1e857b26 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -321,7 +321,7 @@ static __init int build_tdx_memlist(struct list_head *tmb_list)
 	return ret;
 }
 
-static __init int read_sys_metadata_field(u64 field_id, u64 *data)
+static int read_sys_metadata_field(u64 field_id, u64 *data)
 {
 	struct tdx_module_args args = {};
 	int ret;
@@ -1267,6 +1267,23 @@ static __init int tdx_enable(void)
 }
 subsys_initcall(tdx_enable);
 
+int tdx_module_shutdown(void)
+{
+	struct tdx_sys_info_handoff handoff = {};
+	struct tdx_module_args args = {};
+	int ret;
+
+	ret = get_tdx_sys_info_handoff(&handoff);
+	WARN_ON_ONCE(ret);
+
+	/*
+	 * Use the module's handoff version as it is the highest the
+	 * module can produce and most likely supported by newer modules.
+	 */
+	args.rcx = handoff.module_hv;
+	return seamcall_prerr(TDH_SYS_SHUTDOWN, &args);
+}
+
 static bool is_pamt_page(unsigned long phys)
 {
 	struct tdmr_info_list *tdmr_list = &tdx_tdmr_list;
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 76c5fb1e1ffe..f0c20dea0388 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -46,6 +46,7 @@
 #define TDH_PHYMEM_PAGE_WBINVD		41
 #define TDH_VP_WR			43
 #define TDH_SYS_CONFIG			45
+#define TDH_SYS_SHUTDOWN		52
 #define TDH_SYS_DISABLE			69
 
 /*
@@ -108,4 +109,6 @@ struct tdmr_info_list {
 	int max_tdmrs;	/* How many 'tdmr_info's are allocated */
 };
 
+int tdx_module_shutdown(void);
+
 #endif
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index d54d4227990c..e793dec688ab 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -100,6 +100,19 @@ static __init int get_tdx_sys_info_td_conf(struct tdx_sys_info_td_conf *sysinfo_
 	return ret;
 }
 
+static int get_tdx_sys_info_handoff(struct tdx_sys_info_handoff *sysinfo_handoff)
+{
+	int ret;
+	u64 val;
+
+	ret = read_sys_metadata_field(0x8900000100000000, &val);
+	if (ret)
+		return ret;
+
+	sysinfo_handoff->module_hv = val;
+	return 0;
+}
+
 static __init int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 {
 	int ret = 0;

---

## [16] Chao Gao — 2026-05-13
*Subject: [PATCH v9 15/23] x86/virt/tdx: Reset software states during TDX module shutdown*

The TDX module requires a one-time global initialization (TDH.SYS.INIT) and
per-CPU initialization (TDH.SYS.LP.INIT) before use. These initializations
are guarded by software flags to prevent repetition.

After TDX module updates, the new TDX module requires the same global and
per-CPU initializations, but the existing software flags prevent
re-initialization.

Reset all software flags guarding the initialization flows to allow the
global and per-CPU initializations to be triggered again after updates.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v9:
 - use a global structure for TDX global state and use memset to
 zero the whole structure [Dave]
---
 arch/x86/virt/vmx/tdx/tdx.c | 18 ++++++++++++++++--
 1 file changed, 16 insertions(+), 2 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index da3c1e857b26..20b3b33e4677 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1271,7 +1271,7 @@ int tdx_module_shutdown(void)
 {
 	struct tdx_sys_info_handoff handoff = {};
 	struct tdx_module_args args = {};
-	int ret;
+	int ret, cpu;
 
 	ret = get_tdx_sys_info_handoff(&handoff);
 	WARN_ON_ONCE(ret);
@@ -1281,7 +1281,21 @@ int tdx_module_shutdown(void)
 	 * module can produce and most likely supported by newer modules.
 	 */
 	args.rcx = handoff.module_hv;
-	return seamcall_prerr(TDH_SYS_SHUTDOWN, &args);
+	ret = seamcall_prerr(TDH_SYS_SHUTDOWN, &args);
+	if (ret)
+		return ret;
+
+	/*
+	 * Clear global and per-CPU initialization flags so the new module
+	 * can be fully re-initialized after a successful update.
+	 *
+	 * No locks needed as no concurrent accesses can occur here.
+	 */
+	memset(&tdx_module_state, 0, sizeof(tdx_module_state));
+	for_each_possible_cpu(cpu)
+		per_cpu(tdx_lp_initialized, cpu) = false;
+
+	return 0;
 }
 
 static bool is_pamt_page(unsigned long phys)

---

## [17] Chao Gao — 2026-05-13
*Subject: [PATCH v9 16/23] x86/virt/seamldr: Install a new TDX module*

Following the shutdown of the existing TDX module, the update process
continues with installing the new module. P-SEAMLDR provides the
SEAMLDR.INSTALL SEAMCALL to perform this installation, which must be
executed on all CPUs.

Implement SEAMLDR.INSTALL and execute it on every CPU.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v9:
 - Add a comment above seamldr_install()
---
 arch/x86/virt/vmx/tdx/seamldr.c | 14 ++++++++++++++
 1 file changed, 14 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 6114cab46196..9d0e7e8c6c20 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -19,6 +19,7 @@
 
 /* P-SEAMLDR SEAMCALL leaf function */
 #define P_SEAMLDR_INFO			0x8000000000000000
+#define P_SEAMLDR_INSTALL		0x8000000000000001
 
 #define SEAMLDR_MAX_NR_MODULE_PAGES	496
 #define SEAMLDR_MAX_NR_SIG_PAGES	1
@@ -74,6 +75,15 @@ int seamldr_get_info(struct seamldr_info *seamldr_info)
 }
 EXPORT_SYMBOL_FOR_MODULES(seamldr_get_info, "tdx-host");
 
+/* Call into P-SEAMLDR to install a TDX module update */
+static int seamldr_install(const struct seamldr_params *params)
+{
+	struct tdx_module_args args = {};
+
+	args.rcx = __pa(params);
+	return seamldr_call(P_SEAMLDR_INSTALL, &args);
+}
+
 #define TDX_IMAGE_VERSION_2		0x200
 
 struct tdx_image_header {
@@ -166,6 +176,7 @@ static int init_seamldr_params(struct seamldr_params *params, const u8 *data, u3
 enum module_update_state {
 	MODULE_UPDATE_START,
 	MODULE_UPDATE_SHUTDOWN,
+	MODULE_UPDATE_CPU_INSTALL,
 	MODULE_UPDATE_DONE,
 };
 
@@ -240,6 +251,9 @@ static int do_seamldr_install_module(void *seamldr_params)
 			if (primary)
 				ret = tdx_module_shutdown();
 			break;
+		case MODULE_UPDATE_CPU_INSTALL:
+			ret = seamldr_install(seamldr_params);
+			break;
 		default:
 			break;
 		}

---

## [18] Chao Gao — 2026-05-13
*Subject: [PATCH v9 17/23] x86/virt/seamldr: Do TDX per-CPU initialization after module installation*

After installing the new TDX module, each CPU needs to be initialized
again to make the CPU ready to run any other SEAMCALLs. So, export and
call tdx_cpu_enable() on all CPUs.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
 arch/x86/include/asm/tdx.h      | 1 +
 arch/x86/virt/vmx/tdx/seamldr.c | 4 ++++
 arch/x86/virt/vmx/tdx/tdx.c     | 2 +-
 3 files changed, 6 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 27376db7ddac..5d750fe53669 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -107,6 +107,7 @@ static inline long tdx_kvm_hypercall(unsigned int nr, unsigned long p1,
 
 #ifdef CONFIG_INTEL_TDX_HOST
 void tdx_init(void);
+int tdx_cpu_enable(void);
 const char *tdx_dump_mce_info(struct mce *m);
 const struct tdx_sys_info *tdx_get_sysinfo(void);
 
diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 9d0e7e8c6c20..e4a3271051f6 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -177,6 +177,7 @@ enum module_update_state {
 	MODULE_UPDATE_START,
 	MODULE_UPDATE_SHUTDOWN,
 	MODULE_UPDATE_CPU_INSTALL,
+	MODULE_UPDATE_CPU_INIT,
 	MODULE_UPDATE_DONE,
 };
 
@@ -254,6 +255,9 @@ static int do_seamldr_install_module(void *seamldr_params)
 		case MODULE_UPDATE_CPU_INSTALL:
 			ret = seamldr_install(seamldr_params);
 			break;
+		case MODULE_UPDATE_CPU_INIT:
+			ret = tdx_cpu_enable();
+			break;
 		default:
 			break;
 		}
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 20b3b33e4677..5e54da302f2d 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -106,7 +106,7 @@ static int try_init_module_global(void)
  * (and TDX module global initialization SEAMCALL if not done) on local cpu to
  * make this cpu be ready to run any other SEAMCALLs.
  */
-static int tdx_cpu_enable(void)
+int tdx_cpu_enable(void)
 {
 	struct tdx_module_args args = {};
 	int ret;

---

## [19] Chao Gao — 2026-05-13
*Subject: [PATCH v9 18/23] x86/virt/tdx: Restore TDX module state*

TDX module state was packed as handoff data during module shutdown. After
per-CPU initialization, the new module can restore TDX module state from
handoff data to preserve running TDs.

Once the restoration is done, the TDX module update is complete, which
means the new module is ready to handle requests from the host and guests.

Implement the new TDH.SYS.UPDATE SEAMCALL to restore TDX module state
and invoke it on one CPU since it only needs to be called once.

For error handling, Intel® Trust Domain Extensions (Intel® TDX)
Module Base Architecture Specification, Chapter "Restore TDX Module
State after a TD-Preserving Update" states

  If TDH.SYS.UPDATE returns an error, then the host VMM can continue
  with the non-update sequence (TDH.SYS.CONFIG, TDH.SYS.KEY.CONFIG
  etc.). In this case all existing TDs are lost. Alternatively, the host
  VMM can request the P-SEAMLDR to update to another TDX module. If that
  update is successful, existing TDs are preserved.

Given the complexity and uncertain value of above recovery paths, simply
propagate errors.

Also note that the location and the format of handoff data is defined by
the TDX module. The new module knows where to get handoff data and how
to parse it. The kernel doesn't need to provide its location, format etc.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
 arch/x86/virt/vmx/tdx/seamldr.c |  5 +++++
 arch/x86/virt/vmx/tdx/tdx.c     | 13 +++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h     |  2 ++
 3 files changed, 20 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index e4a3271051f6..6a39c9e3ef7d 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -178,6 +178,7 @@ enum module_update_state {
 	MODULE_UPDATE_SHUTDOWN,
 	MODULE_UPDATE_CPU_INSTALL,
 	MODULE_UPDATE_CPU_INIT,
+	MODULE_UPDATE_RUN_UPDATE,
 	MODULE_UPDATE_DONE,
 };
 
@@ -258,6 +259,10 @@ static int do_seamldr_install_module(void *seamldr_params)
 		case MODULE_UPDATE_CPU_INIT:
 			ret = tdx_cpu_enable();
 			break;
+		case MODULE_UPDATE_RUN_UPDATE:
+			if (primary)
+				ret = tdx_module_run_update();
+			break;
 		default:
 			break;
 		}
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 5e54da302f2d..7eb1b67af656 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1298,6 +1298,19 @@ int tdx_module_shutdown(void)
 	return 0;
 }
 
+int tdx_module_run_update(void)
+{
+	struct tdx_module_args args = {};
+	int ret;
+
+	ret = seamcall_prerr(TDH_SYS_UPDATE, &args);
+	if (ret)
+		return ret;
+
+	tdx_module_state.initialized = true;
+	return 0;
+}
+
 static bool is_pamt_page(unsigned long phys)
 {
 	struct tdmr_info_list *tdmr_list = &tdx_tdmr_list;
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index f0c20dea0388..bdfd0e1e337a 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -47,6 +47,7 @@
 #define TDH_VP_WR			43
 #define TDH_SYS_CONFIG			45
 #define TDH_SYS_SHUTDOWN		52
+#define TDH_SYS_UPDATE			53
 #define TDH_SYS_DISABLE			69
 
 /*
@@ -110,5 +111,6 @@ struct tdmr_info_list {
 };
 
 int tdx_module_shutdown(void);
+int tdx_module_run_update(void);
 
 #endif

---

## [20] Chao Gao — 2026-05-13
*Subject: [PATCH v9 19/23] x86/virt/tdx: Refresh TDX module version after update*

The kernel exposes the TDX module version through sysfs so userspace can
check update compatibility. That information needs to remain accurate
across runtime updates.

A runtime update may change the module's update_version, so refresh the
cached version right after a successful update.

Drop __ro_after_init from tdx_sysinfo because it is now updated at runtime.

Do not refresh the rest of tdx_sysinfo, even if some values change across
updates. TDX module updates are backward compatible, so existing
tdx_sysinfo consumers, e.g. KVM, can continue to operate without seeing the
new values.

Refreshing the full structure would be risky. A tdx_sysinfo consumer may
initialize its TDX support based on the features originally reported in
tdx_sysinfo. If a runtime update adds new features and the full structure
is refreshed, that consumer could observe and use the newly reported
features without having performed the setup required to use them safely.

Signed-off-by: Chao Gao <chao.gao@intel.com>
---
v9:
- don't print old and new version [Dave]
- explain why it's OK to hide changes from the tdx_sysinfo users [Dave]
- update versions in stop_machine context
- don't mention major/minor versions are idential across updates. That fact is
  not relevant here.
---
 arch/x86/virt/vmx/tdx/tdx.c                 | 6 +++++-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c | 2 +-
 2 files changed, 6 insertions(+), 2 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 7eb1b67af656..a04b69f77c6e 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -67,7 +67,7 @@ static struct tdmr_info_list tdx_tdmr_list;
 /* All TDX-usable memory regions.  Protected by mem_hotplug_lock. */
 static LIST_HEAD(tdx_memlist);
 
-static struct tdx_sys_info tdx_sysinfo __ro_after_init;
+static struct tdx_sys_info tdx_sysinfo;
 
 /*
  * Do the module global initialization once and return its result.
@@ -1307,6 +1307,10 @@ int tdx_module_run_update(void)
 	if (ret)
 		return ret;
 
+	/* Shouldn't fail as the update has succeeded. */
+	ret = get_tdx_sys_info_version(&tdx_sysinfo.version);
+	WARN_ON_ONCE(ret);
+
 	tdx_module_state.initialized = true;
 	return 0;
 }
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index e793dec688ab..e49c300f23d4 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -7,7 +7,7 @@
  * Include this file to other C file instead.
  */
 
-static __init int get_tdx_sys_info_version(struct tdx_sys_info_version *sysinfo_version)
+static int get_tdx_sys_info_version(struct tdx_sys_info_version *sysinfo_version)
 {
 	int ret = 0;
 	u64 val;

---

## [21] Chao Gao — 2026-05-13
*Subject: [PATCH v9 20/23] x86/virt/tdx: Reject updates during compatibility-sensitive operations*

A TDX module erratum can corrupt TD state if a module update races with
a compatibility-sensitive operation. For example, if an update races
with TD build, the TD measurement hash may be corrupted, which can later
cause attestation failure.

Handle this by requesting the TDX module to detect such races during
TDH.SYS.SHUTDOWN and reject the update when one is found. Report the
failure to userspace as -EBUSY so the update can be retried.

The downside is that module updates can be blocked indefinitely if
compatibility-sensitive operations do not quiesce. In that case,
userspace must resolve the conflict and retry the update.

Do not pre-check whether the TDX module supports this race-detection
capability. If it does not, rely on the TDX module to reject module
shutdown.

== Alternatives ==

Two alternatives were considered and rejected [1]:

  a. Fail TD build when the race occurs. This would complicate KVM error
     handling and risk KVM uABI instability.

  b. Allow the issue to leak through. This would make the problem harder to
     detect and recover from.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Link: https://lore.kernel.org/linux-coco/aQIbM5m09G0FYTzE@google.com/ # [1]
---
v9:
 - Rewrite the changelog: focus on what the patch does and downsides then
   the alternatives [Dave]
 - Extract the movement of TDX_FEATURE0 bit definitions into a cleanup patch [Dave]
---
 arch/x86/include/asm/tdx.h            |  6 ++++--
 arch/x86/virt/vmx/tdx/tdx.c           | 30 ++++++++++++++++++++++++---
 drivers/virt/coco/tdx-host/tdx-host.c |  2 ++
 3 files changed, 33 insertions(+), 5 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 5d750fe53669..1e1bdc4ec9c8 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -29,11 +29,13 @@
 /*
  * TDX module SEAMCALL leaf function error codes
  */
-#define TDX_SUCCESS		0ULL
-#define TDX_RND_NO_ENTROPY	0x8000020300000000ULL
+#define TDX_SUCCESS			0ULL
+#define TDX_RND_NO_ENTROPY		0x8000020300000000ULL
+#define TDX_UPDATE_COMPAT_SENSITIVE	0x8000051200000000ULL
 
 /* Bit definitions of TDX_FEATURES0 metadata field */
 #define TDX_FEATURES0_NO_RBP_MOD	BIT_ULL(18)
+#define TDX_FEATURES0_UPDATE_COMPAT	BIT_ULL(47)
 
 #ifndef __ASSEMBLER__
 
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index a04b69f77c6e..2ab6f6efe6d1 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1267,11 +1267,14 @@ static __init int tdx_enable(void)
 }
 subsys_initcall(tdx_enable);
 
+#define TDX_SYS_SHUTDOWN_AVOID_COMPAT_SENSITIVE BIT(16)
+
 int tdx_module_shutdown(void)
 {
 	struct tdx_sys_info_handoff handoff = {};
 	struct tdx_module_args args = {};
 	int ret, cpu;
+	u64 err;
 
 	ret = get_tdx_sys_info_handoff(&handoff);
 	WARN_ON_ONCE(ret);
@@ -1281,9 +1284,30 @@ int tdx_module_shutdown(void)
 	 * module can produce and most likely supported by newer modules.
 	 */
 	args.rcx = handoff.module_hv;
-	ret = seamcall_prerr(TDH_SYS_SHUTDOWN, &args);
-	if (ret)
-		return ret;
+
+	/*
+	 * This flag tells the TDX module to reject shutdown if it races
+	 * with a "sensitive" ongoing operation. That eliminates exposure
+	 * to a TDX erratum which can corrupt TDX guest states.
+	 *
+	 * This flag is not supported by all TDX modules and may cause
+	 * the shutdown (and subsequent update procedure) to fail.
+	 */
+	args.rcx |= TDX_SYS_SHUTDOWN_AVOID_COMPAT_SENSITIVE;
+
+	err = seamcall(TDH_SYS_SHUTDOWN, &args);
+
+	/*
+	 * The shutdown ran into a "sensitive" ongoing operation. Signal
+	 * to userspace that it can retry.
+	 */
+	if ((err & TDX_SEAMCALL_STATUS_MASK) == TDX_UPDATE_COMPAT_SENSITIVE)
+		return -EBUSY;
+
+	if (err) {
+		seamcall_err(TDH_SYS_SHUTDOWN, err, &args);
+		return -EIO;
+	}
 
 	/*
 	 * Clear global and per-CPU initialization flags so the new module
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index c4c099cf3de1..ad116e56aa1a 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -135,6 +135,8 @@ static enum fw_upload_err tdx_fw_write(struct fw_upload *fwl, const u8 *data,
 	case 0:
 		*written = size;
 		return FW_UPLOAD_ERR_NONE;
+	case -EBUSY:
+		return FW_UPLOAD_ERR_BUSY;
 	default:
 		return FW_UPLOAD_ERR_FW_INVALID;
 	}

---

## [22] Chao Gao — 2026-05-13
*Subject: [PATCH v9 21/23] x86/virt/tdx: Enable TDX module runtime updates*

All pieces of TDX module runtime updates are in place. Enable it if it
is supported.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
 arch/x86/include/asm/tdx.h | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 1e1bdc4ec9c8..ac042b369843 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -34,6 +34,7 @@
 #define TDX_UPDATE_COMPAT_SENSITIVE	0x8000051200000000ULL
 
 /* Bit definitions of TDX_FEATURES0 metadata field */
+#define TDX_FEATURES0_TD_PRESERVING	BIT_ULL(1)
 #define TDX_FEATURES0_NO_RBP_MOD	BIT_ULL(18)
 #define TDX_FEATURES0_UPDATE_COMPAT	BIT_ULL(47)
 
@@ -115,8 +116,7 @@ const struct tdx_sys_info *tdx_get_sysinfo(void);
 
 static inline bool tdx_supports_runtime_update(const struct tdx_sys_info *sysinfo)
 {
-	/* To be enabled when kernel is ready. */
-	return false;
+	return sysinfo->features.tdx_features0 & TDX_FEATURES0_TD_PRESERVING;
 }
 
 int tdx_guest_keyid_alloc(void);

---

## [23] Chao Gao — 2026-05-13
*Subject: [PATCH v9 22/23] coco/tdx-host: Document TDX module update compatibility criteria*

The TDX module update protocol facilitates compatible runtime updates.

Document the compatibility criteria and indicators of update failures.

Note that runtime TDX module updates are an "update at your own risk"
operation; userspace is responsible for ensuring that the update meets
the compatibility criteria.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Dan Williams <dan.j.williams@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
---
v9:
 - Reword the update error descriptions.
---
 .../ABI/testing/sysfs-devices-faux-tdx-host   | 40 +++++++++++++++++++
 1 file changed, 40 insertions(+)

diff --git a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
index 65897fe6abc0..9e08db231da1 100644
--- a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
+++ b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
@@ -26,3 +26,43 @@ Description:	(RO) Report the number of remaining updates. TDX maintains a
 		See Intel® Trust Domain Extensions - SEAM Loader (SEAMLDR)
 		Interface Specification, Chapter "SEAMLDR_INFO" and Chapter
 		"SEAMLDR.INSTALL" for more information.
+
+What:		/sys/devices/faux/tdx_host/firmware/tdx_module
+Contact:	linux-coco@lists.linux.dev
+Description:	(Directory) The tdx_module directory implements the fw_upload
+		sysfs ABI, see Documentation/ABI/testing/sysfs-class-firmware
+		for the general description of the attributes @data, @cancel,
+		@error, @loading, @remaining_size, and @status. This ABI
+		facilitates "Compatible TDX module Updates". A compatible update
+		is one that meets the following criteria:
+
+		   Does not interrupt or interfere with any current TDX
+		   operation or TD VM.
+
+		   Does not invalidate any previously consumed module metadata
+		   values outside of the TEE_TCB_SVN_2 field (updated Security
+		   Version Number) in TD Quotes.
+
+		   Does not require validation of new module metadata fields. By
+		   implication, new module features and capabilities are only
+		   available by installing the module at reboot (BIOS or EFI
+		   helper loaded).
+
+		See tdx_host/firmware/tdx_module/error for information on
+		update failure indicators.
+
+What:		/sys/devices/faux/tdx_host/firmware/tdx_module/error
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) See Documentation/ABI/testing/sysfs-class-firmware for
+		baseline expectations for this file. The <ERROR> part in the
+		<STATUS>:<ERROR> format can be:
+
+		   "device-busy": The update conflicted with an ongoing
+		   compatibility-sensitive operation.
+
+		   "firmware-invalid": The update failed for any other reason.
+
+		"firmware-invalid" may be fatal, causing all TDs and the TDX
+		module to be lost and preventing further TDX operations. This
+		occurs when reading /sys/devices/faux/tdx_host/version returns
+		-ENXIO.

---

## [24] Chao Gao — 2026-05-13
*Subject: [PATCH v9 23/23] x86/virt/tdx: Document TDX module update*

Document TDX module update as a subsection of "TDX Host Kernel Support" to
provide background information and cover key points that developers and
users may need to know, for example:

 - update is done in stop_machine() context
 - update instructions and results
 - update policy and tooling

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
 Documentation/arch/x86/tdx.rst | 34 ++++++++++++++++++++++++++++++++++
 1 file changed, 34 insertions(+)

diff --git a/Documentation/arch/x86/tdx.rst b/Documentation/arch/x86/tdx.rst
index 1a3b5bac1021..9d2b7db166b5 100644
--- a/Documentation/arch/x86/tdx.rst
+++ b/Documentation/arch/x86/tdx.rst
@@ -73,6 +73,40 @@ initialize::
 
   [..] virt/tdx: TDX-Module initialization failed ...
 
+TDX module Runtime Update
+-------------------------
+
+The TDX architecture includes a persistent SEAM loader (P-SEAMLDR) that
+runs in SEAM mode separately from the TDX module. The kernel can
+communicate with P-SEAMLDR to perform runtime updates of the TDX module.
+
+During updates, the TDX module becomes unresponsive to other TDX
+operations. To prevent components using TDX (such as KVM) from
+experiencing unexpected errors during updates, updates are performed in
+stop_machine() context.
+
+TDX module updates have complex compatibility requirements; the new module
+must be compatible with the current CPU, P-SEAMLDR, and running TDX module.
+Rather than implementing complex module selection and policy enforcement
+logic in the kernel, userspace is responsible for auditing and selecting
+appropriate updates.
+
+Updates use the standard firmware upload interface. See
+Documentation/driver-api/firmware/fw_upload.rst for detailed instructions.
+
+If updates failed, running TDs may be killed and further TDX operations may
+not be possible until reboot. For detailed error information, see
+Documentation/ABI/testing/sysfs-devices-faux-tdx-host.
+
+Given the risk of losing existing TDs, userspace should verify that the
+update is compatible with the current system and properly validated before
+applying it.
+
+A reference userspace tool that implements necessary checks is available
+at:
+
+  https://github.com/intel/tdx-module-binaries
+
 TDX Interaction to Other Kernel Components
 ------------------------------------------

---

## [25] Chao Gao — 2026-05-15
*Subject: Re: [PATCH v9 11/23] x86/virt/seamldr: Allocate and populate a
 module update request*

>+static int init_seamldr_params(struct seamldr_params *params, const u8 *data, u32 size)
>+{

I looked at Sashiko's two reports here.

 (1) The header is dereferenced before validating that the input is large
     enough to contain a full header.

 (2) The page-count to byte-count multiplication could in principle
     overflow.

For (1), I agree the validation order should be fixed. Even if the input
buffer is page-backed in practice, the parser should still verify that
size is at least sizeof(struct tdx_image_header) before dereferencing the
header.

For (2), I think using u64 for the derived byte lengths is sufficient in
this case. That avoids overflow in the multiplication itself, and the later
size consistency check:

	HEADER_SIZE + sigstruct_len + module_len != size

will reject malformed inputs.

Below is the fix I plan to fold into this patch in the next revision:

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c
b/arch/x86/virt/vmx/tdx/seamldr.c
index 58ce39315b60..9f4350079477 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -148,8 +148,8 @@ static int init_seamldr_params(struct seamldr_params
*params, const u8 *data, u3
	const struct tdx_image *image		= (const void *)data;
	const struct tdx_image_header *header	= &image->header;
 
-	u32 sigstruct_len	= header->sigstruct_nr_pages * PAGE_SIZE;
-	u32 module_len		= header->module_nr_pages * PAGE_SIZE;
+	u64 sigstruct_len	= header->sigstruct_nr_pages * PAGE_SIZE;
+	u64 module_len		= header->module_nr_pages * PAGE_SIZE;
 
	u8 *header_start	= (u8 *)header;
	u8 *header_end		= header_start + HEADER_SIZE;
@@ -299,6 +299,9 @@ int seamldr_install_module(const u8 *data, u32 size)
	struct seamldr_params *params;
	int ret;
 
+	if (size <= HEADER_SIZE)
+		return -EINVAL;
+
	params = kzalloc_obj(*params);
	if (!params)
		return -ENOMEM;

---

## [26] Chao Gao — 2026-05-15
*Subject: Re: [PATCH v9 20/23] x86/virt/tdx: Reject updates during
 compatibility-sensitive operations*

> /* Bit definitions of TDX_FEATURES0 metadata field */
> #define TDX_FEATURES0_NO_RBP_MOD	BIT_ULL(18)

Sashiko pointed out that this definition is currently unused.

We do not pre-check this TDX_FEATURES0 bit. So, I will drop this definition
in the next revision.

---

## [27] Dave Hansen — 2026-05-15
*Subject: Re: [PATCH v9 01/23] x86/virt/tdx: Consolidate TDX global
 initialization states*

On 5/13/26 08:09, Chao Gao wrote:
...
> Group the states into a single structure so they can be reset together, for
> example with memset(), and so a newly added state won't be missed.
...
> +struct tdx_module_state {
> +	bool initialized;
...
> @@ -113,30 +119,28 @@ static int try_init_module_global(void)
>  {

This doesn't look right to me.

>  	raw_spin_lock(&sysinit_lock);
>  

But I think it's because 'sysinit_ret' is really a funky thing. It's
just here so that the module only _tries_ to be initialized once. That
one-time init records its error code in sysinit_ret and then secondary
callers pick it up.

Here's how you do that in a non-confusing way (some context chopped out):

static int try_init_module_global(void)
{
        struct tdx_module_args args = {};
        static DEFINE_RAW_SPINLOCK(sysinit_lock);
        int ret;

        raw_spin_lock(&sysinit_lock);

	/* Return the "cached" return code: */
        if (tdx_module_state.sysinit_done) {
		ret = tdx_module_state.sysinit_ret;
                goto out;
	}

        ret = seamcall_prerr(TDH_SYS_INIT, &args);

	/* Save the return code for later callers: */
	tdx_module_state.sysinit_ret  = ret;
        tdx_module_state.sysinit_done = true;
out:
        raw_spin_unlock(&sysinit_lock);
        return ret;
}

See how it sets the module state in _one_ place? It also only touches
the module state under the lock so it's more obvious that it is correct
and there are no races or tearing or other nonsense.

*That* is a proper refactoring.

I'm also not sure we need to be saving the return code. It seems a bit
much, but we don't have to fix that now.

---

## [28] Dave Hansen — 2026-05-15
*Subject: Re: [PATCH v9 02/23] x86/virt/tdx: Move TDX_FEATURES0 bits to
 asm/tdx.h*

On 5/13/26 08:09, Chao Gao wrote:
> This prepares for TDX module update [1] and Dynamic PAMT [2] support. Both
> add new TDX_FEATURES0 capability bits, and both need those capabilities to

Please don't add unnecessary changelog cruft. If you need this move for
this series, that's enough.

---

## [29] Dave Hansen — 2026-05-15
*Subject: Re: [PATCH v9 04/23] coco/tdx-host: Introduce a "tdx_host" device*

On 5/13/26 08:09, Chao Gao wrote:
> Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
> Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>

This SoB chain at _least_ needs a note. It looks quite bizarre.

> +config TDX_HOST_SERVICES
> +	tristate "TDX Host Services Driver"

In what world will anyone ever set INTEL_TDX_HOST=y, but turn this off?
Is this even worth a Kconfig prompt?

I guess we need it for the module or built in choice. But otherwise it
seems a bit silly.

---

## [30] Dave Hansen — 2026-05-15
*Subject: Re: [PATCH v9 05/23] coco/tdx-host: Expose TDX module version*

On 5/13/26 08:09, Chao Gao wrote:
> For TDX module updates, userspace needs to select compatible update
> versions based on the current module version. This design delegates

I'm not sure exactly what a "version series" is. Do you need to say more
than that the policy is complex?

> For example, the 1.5.x series is for certain platform generations, while
> the 2.0.x series is intended for others. And TDX module 1.5.x may be

That's not much of an example, IMNHO. How about:

	For example, the 1.5.x series runs on Sapphire Rapids but not
	Granite Rapids, which needs 2.0.x. Updates are also constrained
	by version distance, so a 1.5.6 module might permit updates to
	1.5.7 but not to 1.5.20.

> Expose the TDX module version to userspace via sysfs to aid module
> selection. Since the TDX faux device will drive module updates, expose

I honestly wouldn't even mention this bit. You don't need a bonus.

> +++ b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
> @@ -0,0 +1,6 @@

The "etc." is silly. Just zap it.

Description:	(RO) Report the version of the loaded TDX module.
		Formatted as "major.minor.update". Used by TDX module
		update tooling. Example: "1.2.03"

That's at least a wee bit of warning to folks about the leading 0 so if
they are parsing it they are a wee bit careful with it.

> diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
> index 8b739ac01479..b7f4396b5cc5 100644

I hate "e.g.". I'm not sure why, but maybe it it often misused, or that
it isn't allowed by the style guide I had to use in high school. Either
way, please stop using it.

You don't have to modify this patch for it, but please stop.

Second, this was an opportunity to peel out the creation of
"TDX_VERSION_FMT". It would have shrunk your series by ~10 lines and
made this patch more obvious.

Again, you don't have to go do it, but it was a missed opportunity.


With those updates:

Reviewed-by: Dave Hansen <dave.hansen@linux.intel.com>

---

## [31] Dave Hansen — 2026-05-15
*Subject: Re: [PATCH v9 06/23] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On 5/13/26 08:09, Chao Gao wrote:
> Note that unlike P-SEAMLDR, there is also a non-persistent SEAM loader
> ("NP-SEAMLDR"). This is an authenticated code module (ACM) that is not

The "unlike" is the wrong word to use here.

Here's a rewrite, with some Claude help:

Note: Despite the similar name, the NP-SEAMLDR ("Non-Persistent")
differs sharply from the P-SEAMLDR. It is an authenticated code module
(ACM) invoked exclusively by the BIOS at boot rather than a component
running in SEAM mode. The kernel cannot call it at runtime. It exposes
no SEAMCALL interface.

---

## [32] Dave Hansen — 2026-05-15
*Subject: Re: [PATCH v9 06/23] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On 5/13/26 08:09, Chao Gao wrote:
> The TDX architecture uses the "SEAMCALL" instruction to communicate with
> SEAM mode software. Right now, the only SEAM mode software that the kernel

Nit: the "main act" solution statement for this changelog is:

	Add a P-SEAMLDR wrapper to handle these differences and prepare
	for implementing concrete functions.

What's more important, that ^?

Or:

	Use seamcall_prerr() (not '_ret') because current P-SEAMLDR
	calls do not use any output registers other than RAX.

?

Now, what is in a more prominent place in the changelog?

Reviewed-by: Dave Hansen <dave.hansen@linux.intel.com>

---

## [33] Dave Hansen — 2026-05-15
*Subject: Re: [PATCH v9 07/23] x86/virt/seamldr: Add a helper to retrieve
 P-SEAMLDR information*

On 5/13/26 08:09, Chao Gao wrote:
> P-SEAMLDR reports its state via SEAMLDR.INFO, including its version and
> the number of remaining runtime updates.

What is "tdx-host.ko"? My kernel doesn't have that. Remember a few
patches ago, the "tristate" in Kconfig? ;)

You also called in the "tdx_host" device. Please be consistent with the
naming.

> Note that there are two distinct P-SEAMLDR APIs with similar names:
> 
This doesn't help.

"SEAMLDR.INFO" is metadata about the loader. It's metadata for the
update process.

"SEAMLDR.SEAMINFO" is metadata about the module. It is for the module
init process, not for the update process.

Right? Isn't that a billion times more useful and actually helps
differentiate them?

Also, more nits: I hate former/latter too. It makes me stop reading and
have to go back *EVER* *TIME*. I hate that particular english construct.
It's horrid.

Just say:

	Use SEAMLDR.INFO here.

It's even shorter than the passive "is used" and doesn't require me
going back and re-read the text.

> +++ b/arch/x86/include/asm/seamldr.h
> @@ -0,0 +1,36 @@

More succinct:

    * This is the "SEAMLDR_INFO" data structure defined in the
      "SEAM Loader (SEAMLDR) Interface Specification".

> + * The SEAMLDR.INFO documentation requires this to be aligned to a
> + * 256-byte boundary.

Just say:

 * Must be aligned to a 256-byte boundary.

With those fixed:

Reviewed-by: Dave Hansen <dave.hansen@linux.intel.com>

---

## [34] Dave Hansen — 2026-05-15
*Subject: Re: [PATCH v9 08/23] coco/tdx-host: Expose P-SEAMLDR information via
 sysfs*

> +What:		/sys/devices/faux/tdx_host/seamldr_version
> +Contact:	linux-coco@lists.linux.dev

Rather than a copy/paste, I'd just say the format is the same as the
main module version.

...
> +static ssize_t num_remaining_updates_show(struct device *dev,
> +					  struct device_attribute *attr,

I feel like we need to mention *somewhere* that these are kinda nasty.
tdx_get_sysinfo() is slow and single-threaded. These very much are and
need to stay 0400 for good reason.

Talk about the DEVICE_ATTR_ADMIN_RO() choice _somewhere_, please.

With those fixed:

Reviewed-by: Dave Hansen <dave.hansen@linux.intel.com>

---

## [35] Dave Hansen — 2026-05-15
*Subject: Re: [PATCH v9 09/23] coco/tdx-host: Don't expose P-SEAMLDR
 information on CPUs with erratum*

On 5/13/26 08:09, Chao Gao wrote:
> Some TDX-capable CPUs have an erratum, as documented in Intel® Trust
> Domain CPU Architectural Extensions (May 2021 edition) Chapter 2.3:

2021, eh?

>   SEAMRET from the P-SEAMLDR clears the current VMCS structure pointed
>   to by the current-VMCS pointer. A VMM that invokes the P-SEAMLDR using

Reviewed-by: Dave Hansen <dave.hansen@linux.intel.com>

---

## [36] Dave Hansen — 2026-05-15
*Subject: Re: [PATCH v9 08/23] coco/tdx-host: Expose P-SEAMLDR information via
 sysfs*

On 5/13/26 08:09, Chao Gao wrote:
> +static umode_t seamldr_group_visible(struct kobject *kobj, struct attribute *attr, int idx)
> +{

Axe the tertiary form.

	if (!tdx_supports_runtime_update(sysinfo))
		return 0;

	return attr->mode;

Please.

---

## [37] Dave Hansen — 2026-05-15
*Subject: Re: [PATCH v9 10/23] coco/tdx-host: Implement firmware upload sysfs
 ABI for TDX module updates*

On 5/13/26 08:09, Chao Gao wrote:
> tl;dr: Select fw_upload for doing TDX module updates. The process of
> selecting among available update images is complicated and nuanced. Punt

Shouldn't we also say that there is userspace out there to do this
today? Like it's not vaporware. Can we point to it?

> Long Version:
> 

Gah, another former/latter. Format it like this:

The kernel supports two primary firmware update mechanisms:
 1. request_firmware() - used by microcode, SEV firmware, hundreds of
			 other drivers
 2. 'struct fw_upload' - used by CXL, FPGA updates, dozens of others

Isn't that a billion times easier to parse?

> One key difference between them is: request_firmware() loads a named
> file from the filesystem where the filename is kernel-controlled, while

One more thing to remove from your changelogs: this "is: " construct.
It's horribly awkward for a reader.

This, please:

	The key difference between is that request_firmware() loads a
	named file from the filesystem where the filename is kernel-
	controlled, while fw_upload accepts firmware data directly from
	userspace.

> Use fw_upload for TDX module updates as loading a named file isn't
> suitable for TDX (see below for more reasons). Specifically, register

This is just noise for the justification. We can't do it because it's
not suitable? That's not a reason.

Isn't this better?

	TDX module firmware update selection policy is too complex for
	the kernel. Leave it to userspace and use fw_upload.

> Why fw_upload instead of request_firmware()?
> ============================================



> a. Intel distributes all versions of the TDX module, allowing admins to
> load any version rather than always defaulting to the latest. This

How about just: The fw_upload cleanly supports both upgrades and
reversions to earlier module versions. TDX users are expected to need to
do both.

> b. Some module version series are platform-specific. For example, the 1.5.x
> series is for certain platform generations, while the 2.0.x series is

Not "Some".


x. A given module image can be compatible with several platforms. 1.5.2
   runs on <example 1> and <example 2>
y. Not all modules images are compatible with all platforms. 2.0.x runs
   <example 3> but not <example 1>.
z. A filesystem will have TDX module images for many platforms, the same
   as how /lib/firmware/intel-ucode/ has ucode for many processor
   models.

> c. The update policy for TDX module updates is non-linear at times. The
> latest TDX module may not be compatible. For example, TDX module 1.5.x

Again, I'd just give an actual example.

> So, the default policy of "request_firmware()" of "always load latest", is
> not suitable for TDX. Userspace needs to deploy a more sophisticated policy

Here's a flow in userspace that I can imagine:

 1. Find all the available modules
 2. Filter out modules which are incompatible with this system
 3. Find the current running module version
 4. Decide which direction: upgrade or downgrade. Filter out modules
    which are not in the right direction
 5. Filter out modules which have a functionally too distant version
    (1.2.3=>1.2.4 is OK, but going to 1.2.999 is not)
 6. Optimize for fewest updates, or smallest updates. If allowed, go:
    1.2.3=>1.2.5, or 1.2.3=>1.2.4=>1.2.5?

Steps 4 and 6 are _pure_ policy.

> diff --git a/drivers/virt/coco/tdx-host/Kconfig b/drivers/virt/coco/tdx-host/Kconfig
> index d35d85ef91c0..ca600a39d97b 100644

Doesn't this break the compile if FW_LOADER can't be selected? Or does
it error out at Kconfig time. I always forget.

> diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
> index a540d658757b..c4c099cf3de1 100644

This is rather ugly for a single condition. Plus, it puts the error path
and the success path on the same footing. That's not great. How about:

	if (ret)
		return FW_UPLOAD_ERR_FW_INVALID;

	*written = size;
	return FW_UPLOAD_ERR_NONE;

---

## [38] Dave Hansen — 2026-05-15
*Subject: Re: [PATCH v9 11/23] x86/virt/seamldr: Allocate and populate a module
 update request*

On 5/13/26 08:09, Chao Gao wrote:
> There are two important ABIs here:
> 

	... broken up into 4k pages

> Userspace supplies the update image in struct tdx_image format. The image
> consists of a header followed by a sigstruct and the module binary.

This is doing it again. It's taking the key imperative and burying it.
It should be:

=>
Userspace supplies the update image in struct tdx_image format. The
image consists of a header followed by a sigstruct and the module
binary. P-SEAMLDR, however, consumes struct seamldr_params rather than
the image directly.

Parse the struct tdx_image provided by userspace and populate a matching
struct seamldr_params.
<=

> Validate the struct tdx_image header before using it, because the header is
> consumed solely by the kernel to locate the sigstruct and module within

That's a good note. It can go above the ---.

> + * The seamldr_params "scenario" field specifies the operation mode:
> + * 0: Install TDX module from scratch (not used by kernel)

Yeah, but that's not super useful.

	This is the in-memory ABI that the kernel passes to the P-
	SEAMLDR to update the TDX module. It breaks the TDX module image
	up in page-size pieces.

Better?

> + */
> +struct seamldr_params {

That comment reads strangely in here. Did I ask you to write that?

> +	u16	checksum;
> +	u8	signature[8];

The naming in there is painful. How about:

populate_pa_list(u64 *pa_list, u32 pa_list_len,
		 const u8 *vmalloc_addr, u32 vmalloc_len_pages)

> +{
> +	int i;

This seems wonky. Should it really be silently suppressing things if
either the allocation or source is too small? I get not wanting to
overflow, but this seems strange.

> +	for (i = 0; i < nr_pages; i++) {
> +		pa_list[i] = vmalloc_to_pfn(start) << PAGE_SHIFT;

At the point that you modify 'start', it's not 'start' any more. Use
another variable. This would do, for instance:

	for (i = 0; i < nr_pages; i++) {
		unsigned long offset = i * PAGE_SIZE;

		pa_list[i] = vmalloc_to_pfn(&start[offset]);
	}


> +static void populate_seamldr_params(struct seamldr_params *params,
> +				    const u8 *sig, u32 sig_nr_pages,

Yes, this is starting to look OK. Nit: vertically align the "*_PAGES" args:


	populate_pa_list(params->sigstruct_pages_pa_list, SEAMLDR_...,
			 sig, sig_nr_pages);
	populate_pa_list(params->module_pages_pa_list,    SEAMLDR_...,
			 mod, mod_nr_pages);


> +static int init_seamldr_params(struct seamldr_params *params, const u8 *data, u32 size)
> +{

How does this "protect kernel ABI"?

> +	if (header->version != TDX_IMAGE_VERSION_2)
> +		return -EINVAL;

Please work on the vertical alignment if there's a pattern. For
instance, it makes things pop if the two "header->"'s are vertically
aligned.

---

## [39] Edgecombe, Rick P — 2026-05-15
*Subject: Re: [PATCH v9 11/23] x86/virt/seamldr: Allocate and populate a module
 update request*

On Fri, 2026-05-15 at 11:24 -0700, Dave Hansen wrote:
> > +	/* Check the calculated payload size against the data size. */
> > +	if (HEADER_SIZE + sigstruct_len + module_len != size)

I think it means to not allow values in that field in case the kernel wants to
make them mean something new, later.

---

## [40] Dave Hansen — 2026-05-15
*Subject: Re: [PATCH v9 11/23] x86/virt/seamldr: Allocate and populate a module
 update request*

On 5/15/26 11:44, Edgecombe, Rick P wrote:
> On Fri, 2026-05-15 at 11:24 -0700, Dave Hansen wrote:
>>> +	/* Check the calculated payload size against the data size. */

Maybe I'm just being dense, but I don't have any idea what either of you
is saying. ;)

Could you try a concrete example, please?

---

## [41] Dave Hansen — 2026-05-15
*Subject: Re: [PATCH v9 11/23] x86/virt/seamldr: Allocate and populate a module
 update request*

On 5/13/26 08:09, Chao Gao wrote:
>  int seamldr_install_module(const u8 *data, u32 size)
>  {

Can we please do better than 'data' and 'size'? Even s/size/data_len/ is
better. This goes for the *entire* series.

Why not call it 'tdx_image' or '_tdx_image' or '_module_image'?

Second, I'm losing track of where these are in the process. Comments on
functions help. Here's how...

> +	struct seamldr_params *params;
> +	int ret;

init_seamldr_params() should have a comment like this:

	/*
	 * @data points to a vmalloc()'d 'struct tdx_image'. Transform
	 * it into @params which is the P-SEAMLDR ABI format.
	 */

Then this site can say:

	/* Populate 'params' from 'data' */

To at least show the flow of the code. Gunk flows from data=>params.
It's *NOT* otherwise obvious what's goign on here.

Please go through the whole series and make sure you're doing stuff like
this. Comment functions. Say what they are doing at a high level.
Comment their call sites when what they are doing is not clear.

> +	ret = init_seamldr_params(params, data, size);
> +	if (ret)

---

## [42] Chao Gao — 2026-05-18
*Subject: Re: [PATCH v9 01/23] x86/virt/tdx: Consolidate TDX global
 initialization states*

On Fri, May 15, 2026 at 09:14:02AM -0700, Dave Hansen wrote:
>On 5/13/26 08:09, Chao Gao wrote:
>...

Yes, that is a clear readability improvement.

To follow the "one change per patch" rule, I am inclined to do that as a
separate preparatory cleanup before moving all states into a structure.

commit 26bb389c5762fd6a496fbed1cc55e4978e99a5cb
Author: Chao Gao <chao.gao@intel.com>
Date:   Sun May 17 20:03:00 2026 -0700

    x86/virt/tdx: Clarify try_init_module_global() result caching
    
    TDX module global initialization is executed only once. The first call
    caches both the result and the "done" state, and later callers reuse the
    saved result. A lock protects that cached state.
    
    The current code is harder to read because sysinit_done is accessed under
    the lock, while sysinit_ret is not.
    
    To improve readability, move sysinit_ret accesses within the lock.
    
    Group sysinit_ret/sysinit_done updates right after initialization so
    Caching the result is separate from the initialization itself.
    
    Signed-off-by: Chao Gao <chao.gao@intel.com>

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index c0c6281b08a5..ad56f142dd0b 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -115,28 +115,34 @@ static int try_init_module_global(void)
	static DEFINE_RAW_SPINLOCK(sysinit_lock);
	static bool sysinit_done;
	static int sysinit_ret;
+	int ret;
 
	raw_spin_lock(&sysinit_lock);
 
-	if (sysinit_done)
+	/* Return the "cached" return code. */
+	if (sysinit_done) {
+		ret = sysinit_ret;
		goto out;
+	}
 
	/* RCX is module attributes and all bits are reserved */
	args.rcx = 0;
-	sysinit_ret = seamcall_prerr(TDH_SYS_INIT, &args);
+	ret = seamcall_prerr(TDH_SYS_INIT, &args);
 
	/*
	 * The first SEAMCALL also detects the TDX module, thus
	 * it can fail due to the TDX module is not loaded.
	 * Dump message to let the user know.
	 */
-	if (sysinit_ret == -ENODEV)
+	if (ret == -ENODEV)
		pr_err("module not loaded\n");
 
+	/* Save the return code for later callers. */
	sysinit_done = true;
+	sysinit_ret = ret;
 out:
	raw_spin_unlock(&sysinit_lock);
-	return sysinit_ret;
+	return ret;
 }
 
 /**

---

## [43] Chao Gao — 2026-05-18
*Subject: Re: [PATCH v9 02/23] x86/virt/tdx: Move TDX_FEATURES0 bits to
 asm/tdx.h*

On Fri, May 15, 2026 at 09:15:47AM -0700, Dave Hansen wrote:
>On 5/13/26 08:09, Chao Gao wrote:
>> This prepares for TDX module update [1] and Dynamic PAMT [2] support. Both

Sure. Will remove "Dynamic PAMT" stuff from the changelog.

---

## [44] Chao Gao — 2026-05-18
*Subject: Re: [PATCH v9 04/23] coco/tdx-host: Introduce a "tdx_host" device*

On Fri, May 15, 2026 at 09:21:36AM -0700, Dave Hansen wrote:
>On 5/13/26 08:09, Chao Gao wrote:
>> Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>

I will add a note.

This patch was originally written by me and then substantially revised
by Yilun, hence his Co-developed-by and Signed-off-by.

Then Dan made additional cleanups on top of Yilun's version and was the first
to post it at:

https://lore.kernel.org/all/20250919142237.418648-2-dan.j.williams@intel.com/

The current version is based on that posted patch, which is why the SoB
chain is unusual.

>
>> +config TDX_HOST_SERVICES

No, I do not think disabling TDX_HOST_SERVICES while INTEL_TDX_HOST=y makes
sense.

>Is this even worth a Kconfig prompt?
>

Yes. it is for the module vs built-in choice.

---

## [45] Chao Gao — 2026-05-18
*Subject: Re: [PATCH v9 05/23] coco/tdx-host: Expose TDX module version*

On Fri, May 15, 2026 at 09:53:59AM -0700, Dave Hansen wrote:
>On 5/13/26 08:09, Chao Gao wrote:
>> For TDX module updates, userspace needs to select compatible update

By "version series" I meant release lines such as 1.5.x, 2.0.x, and
3.0.x, but that is not clear from the changelog.

>Do you need to say more
>than that the policy is complex?

I will tighten it up and just say that the update policy is complex.

>
>> For example, the 1.5.x series is for certain platform generations, while

Yes, that is much better than my version.

>
>> Expose the TDX module version to userspace via sysfs to aid module

Sure, I will drop that part.

>
>> +++ b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host

Thanks, this wording is much better and more concise.

---

## [46] Chao Gao — 2026-05-18
*Subject: Re: [PATCH v9 07/23] x86/virt/seamldr: Add a helper to retrieve
 P-SEAMLDR information*

>> Note that there are two distinct P-SEAMLDR APIs with similar names:
>> 

Thanks for rewriting this.

One small nuance is that SEAMLDR.SEAMINFO is really about SEAM mode
rather than the loaded module itself. So I think this is a bit more
accurate:

SEAMLDR.SEAMINFO is metadata about SEAM mode. It is used for module
initialization, not for the update process.

>
>Right? Isn't that a billion times more useful and actually helps

I will avoid former/latter wording in future patches.

---

## [47] Chao Gao — 2026-05-18
*Subject: Re: [PATCH v9 08/23] coco/tdx-host: Expose P-SEAMLDR information via
 sysfs*

>> +static umode_t seamldr_group_visible(struct kobject *kobj, struct attribute *attr, int idx)
>> +{

I will add a comment to make the DEVICE_ATTR_ADMIN_RO() choice
explicit.

+/*
+ * These attributes are intended for admins managing TDX module updates.
+ * Reading them issues a slow, serialized P-SEAMLDR query, so keep them
+ * admin-only.
+ */
 static DEVICE_ATTR_ADMIN_RO(seamldr_version);
 static DEVICE_ATTR_ADMIN_RO(num_remaining_updates);

---

## [48] Chao Gao — 2026-05-18
*Subject: Re: [PATCH v9 09/23] coco/tdx-host: Don't expose P-SEAMLDR
 information on CPUs with erratum*

On Fri, May 15, 2026 at 10:26:19AM -0700, Dave Hansen wrote:
>On 5/13/26 08:09, Chao Gao wrote:
>> Some TDX-capable CPUs have an erratum, as documented in Intel� Trust

The TDX ISA document has not been updated since then; the May 2021
edition is still the latest revision. See:

https://www.intel.com/content/www/us/en/developer/tools/trust-domain-extensions/documentation.html

---

## [49] Chao Gao — 2026-05-18
*Subject: Re: [PATCH v9 11/23] x86/virt/seamldr: Allocate and populate a
 module update request*

>> +#define TDX_IMAGE_VERSION_2		0x200
>> +

I copied that from the example you suggested for this structure in v8. But
yes, it does read awkwardly here, so I will drop it.

>
>> +	u16	checksum;

Sure.

>
>> +{

Ok. I'll add explicit bounds checks and drop the MIN().

>
>> +	for (i = 0; i < nr_pages; i++) {

Good point.

>
>

"Protect kernel ABI" was imprecise here. The intent is to reject
obviously malformed headers.

If the kernel accepts garbage in header fields today, userspace can come
to rely on that behavior. Later, the kernel may start validating those
fields more strictly or assign meaning to fields that were previously
reserved. Rejecting the same image then could be seen as a kernel
regression.

I'll simplify the comment to:

	/* Reject obviously malformed image headers. */

---

## [50] Dave Hansen — 2026-05-18
*Subject: Re: [PATCH v9 11/23] x86/virt/seamldr: Allocate and populate a module
 update request*

On 5/18/26 07:15, Chao Gao wrote:
>>> +#define TDX_IMAGE_VERSION_2		0x200
>>> +

The point is that the code or comments needs to mention *somewhere* that
"This (header->version) ABI is always 0x200". I didn't mean for you to
literally put that ^ in there.

It's fine if it is in the code to. Just mention it somewhere.

>>> +static int init_seamldr_params(struct seamldr_params *params, const u8 *data, u32 size)
>>> +{

I'm still not following this at all.

I suspect that someone along the way said something in reviewing this
about ensuring that fields that are "reserved" are treated as "reserved
+ must be zero".

Somehow that recommendation got conflated with the version checking.

But the deeper point is that neither this patch nor its contributor is
quite able to articulate the reason for this line of code being here.

Let me try.

	The "tdx_image" ABI is versioned. However, there has only ever
	been one public versions of the structure: ->version==0x200. The
	kernel can only parse that version. Future versions of the
	module might be able to use the same ABIs (user/kernel and
	kernel/SEAMLDR) but they will not be able to use this kernel
	code.

	Reject module images without that specific version. This ensures
	that the kernel is able to understand the passed-in format.

---

## [51] Dave Hansen — 2026-05-18
*Subject: Re: [PATCH v9 09/23] coco/tdx-host: Don't expose P-SEAMLDR
 information on CPUs with erratum*

On 5/18/26 05:44, Chao Gao wrote:
> On Fri, May 15, 2026 at 10:26:19AM -0700, Dave Hansen wrote:
>> On 5/13/26 08:09, Chao Gao wrote:

I think you are saying that the CPUs have an erratum.

That erratum diverges their implementation from the spec: "Intel® Trust
Domain CPU Architectural Extensions (May 2021 edition) Chapter 2.3".

But when you combine those two things in one sentence, it's incredibly
confusing.

The erratum you are talking about is brand new. I just asked for it to
be created in the last month or two. Thus, my confusion when you say
there: "an erratum, as documented in ... May 2021".

Thus, I'm questioning the 2021 date. You probably also want to mention
that the erratum is, as of today, not publicly documented.

Can you rephrase this all and make it clearer, please?

---

## [52] Dave Hansen — 2026-05-18
*Subject: Re: [PATCH v9 12/23] x86/virt/seamldr: Introduce skeleton for TDX
 module updates*

On 5/13/26 08:09, Chao Gao wrote:
>   b) omit touch_nmi_watchdog() and rcu_momentary_eqs(), which exist
>      there for debugging and are not strictly needed for this update flow

Could you possibly start a thread with a suggested refactoring of this
code? The use of those helpers is really subtle and it would be great to
put them in one place and document the subtlety so that future users can
leverage the helper.

---

## [53] Edgecombe, Rick P — 2026-05-18
*Subject: Re: [PATCH v9 02/23] x86/virt/tdx: Move TDX_FEATURES0 bits to
 asm/tdx.h*

On Mon, 2026-05-18 at 15:52 +0800, Chao Gao wrote:
> On Fri, May 15, 2026 at 09:15:47AM -0700, Dave Hansen wrote:
> > On 5/13/26 08:09, Chao Gao wrote:

I think it should not link to old versions of this series to explain the
preparation. That is very confusing. We can just explain what will come in the
later patches of *this* series. I'll circle back and propose some verbiage.

---

## [54] Edgecombe, Rick P — 2026-05-18
*Subject: Re: [PATCH v9 01/23] x86/virt/tdx: Consolidate TDX global
 initialization states*

On Mon, 2026-05-18 at 15:43 +0800, Chao Gao wrote:
> commit 26bb389c5762fd6a496fbed1cc55e4978e99a5cb
> Author: Chao Gao <chao.gao@intel.com>
                          ^ harder then what? Maybe just "hard"
>     the lock, while sysinit_ret is not.
>     

This is a great improvement by itself, irrespective of this series. The original
code made my head hurt when I first saw it:
https://lore.kernel.org/all/726dccd6d46d0bd471ec0b2f6861f8e45bade26c.camel@intel.com/

The handling of things outside the lock is one thing, but also the function
scopes statics stood out to me as strange. So yea, maybe two patches, this one
and another to get rid of the function scoped statics?

> 
> diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c

---

## [55] Dave Hansen — 2026-05-18
*Subject: Re: [PATCH v9 04/23] coco/tdx-host: Introduce a "tdx_host" device*

On 5/18/26 04:18, Chao Gao wrote:
> On Fri, May 15, 2026 at 09:21:36AM -0700, Dave Hansen wrote:
>> On 5/13/26 08:09, Chao Gao wrote:

On some level, I just don't care how this bounced around within Intel or
any other company. I don't need to hear the tale of woe.

I'd frankly like to just see simplicity in the SoB chain:

	Thanks to Dan and Xu Yilun for all the help on this one.

	Signed-off-by: Chao

IMNHO, SoB should start when it leaves your company.

>>> +config TDX_HOST_SERVICES
>>> +	tristate "TDX Host Services Driver"

Can it just be this, then?

config TDX_HOST_SERVICES
	tristate
	depends on INTEL_TDX_HOST
	default m

That won't prompt people and it will set =m too. I think.

---

## [56] Dave Hansen — 2026-05-18
*Subject: Re: [PATCH v9 01/23] x86/virt/tdx: Consolidate TDX global
 initialization states*

On 5/18/26 11:00, Edgecombe, Rick P wrote:
> This is a great improvement by itself, irrespective of this series.

Agreed. If it came by itself, I'd probably apply it.

---

## [57] Edgecombe, Rick P — 2026-05-19
*Subject: Re: [PATCH v9 09/23] coco/tdx-host: Don't expose P-SEAMLDR
 information on CPUs with erratum*

On Mon, 2026-05-18 at 08:29 -0700, Dave Hansen wrote:
> On 5/18/26 05:44, Chao Gao wrote:
> > On Fri, May 15, 2026 at 10:26:19AM -0700, Dave Hansen wrote:

It actually is documented in that May 2021 spec as the architectural behavior.
But it looks like not earlier, because the doc said it is new verbiage on that
one.

> 
> But when you combine those two things in one sentence, it's incredibly

So I guess we want to explain:
1. The problematic VMCS clearing behavior
2. That the problematic behavior is only documented in later docs (right?)
3. That it will be documented as an erratum later, and checked via the bit

Maybe something like?

Some TDX-capable CPUs have an erratum where SEAMRET clears the current VMCS
pointer. The behavior relies on the VMM to reload the current VMCS pointer.
However, that is a problem for KVM because clearing the current VMCS pointer
behind KVM's back will break KVM. While the VMCS clearing is documented as the
actual architecture in later versions of the "Intel® Trust Domain CPU
Architectural Extensions"[0] documents, it is not present in the earlier ones. 

Future docs will describe this SEAMRET VMCS clearing behavior as being present
when IA32_VMX_BASIC[60] is set...

---

## [58] Edgecombe, Rick P — 2026-05-19
*Subject: Re: [PATCH v9 02/23] x86/virt/tdx: Move TDX_FEATURES0 bits to
 asm/tdx.h*

On Mon, 2026-05-18 at 09:57 -0700, Rick Edgecombe wrote:
> On Mon, 2026-05-18 at 15:52 +0800, Chao Gao wrote:
> > On Fri, May 15, 2026 at 09:15:47AM -0700, Dave Hansen wrote:

How about?

Future changes will add support for new TDX features exposed as TDX_FEATURES0
bits. The presence of these features will need to be checked outside of
arch/x86/virt. So the feature query helpers, and the TDX_FEATURES0 defines they
reference, will need to live in the widely accessible asm/tdx.h helper. Move the
existing TDX_FEATURES0 to asm/tdx.h so that they can all be kept together.


I ended up re-writing the whole thing. Not sure it was entirely necessary, but
lets def lose the links to the old patch versions.

---

## [59] Edgecombe, Rick P — 2026-05-19
*Subject: Re: [PATCH v9 13/23] x86/virt/seamldr: Abort updates after a failed
 step*

On Wed, 2026-05-13 at 08:09 -0700, Chao Gao wrote:
> A TDX module update is a multi-step process, and any step can fail.
> 

I get what you are saying here, but "continuing" vs "leaving" is a tiny bit
confusing to me. Maybe: Continuing with subsequent update steps after a failure
can cause the TDX module to enter an unrecoverable state?

> 
> One failure case must remain recoverable: update contention with an ongoing

The link to the discussion is nice, but the explanation of just that there was
an agreement is not saying much. But the reasoning around AVOID_COMPAT_SENSITIVE
*is* handled in later patch. So can we say future changes will want to return
errors to userspace for certain update failures? Then we can discuss the
specifics when code is actual error is added?

And why talk about EBUSY specifically? It is not in this patch. Stale log? 

> 
> Abort the update on any failure. This also makes the TD-build contention

Oh, maybe I didn't get what you meant above actually. The contention case is
only recoverable because we detect it at the first step? Does "Continuing after
a failure can leave the TDX module in an unrecoverable" really mean that any
failure after the first step is unrecoverable? Or can we put it in some other
more specific terms like that. Terms which are more specific but still not
overly complex description of TDX module update flows?

> Apply the same rule to all errors instead of special-casing
> -EBUSY.

It seems like actually it is not special cased...? The error returned is
whatever is returned from the step.

> 
> Track per-step failures, stop the update loop once a failure is observed,

Hmm, so this is actually a bunch of generic handling for each step, that really
only works for the first one? Is the generic handling really needed?

> 
> Signed-off-by: Chao Gao <chao.gao@intel.com>

Was there past discussion on why it keeps a failed count? All we need to know is
if anything failed right? So a bool is fine too?

>  	/*
>  	 * Protect update_ctrl. Raw spinlock as it will be acquired from

---

## [60] Edgecombe, Rick P — 2026-05-19
*Subject: Re: [PATCH v9 14/23] x86/virt/seamldr: Shut down the current TDX
 module*

On Wed, 2026-05-13 at 08:09 -0700, Chao Gao wrote:
> The first step of TDX module updates is shutting down the current TDX
> module. This step also packs state information that needs to be

kinda reads like handoff data is an existing term, but its the first reference
in this series.

Maybe packs state information that needs to be preserved across updates, called
"handoff data". This handoff data is consumed...

> which will be consumed by the
> updated module. The handoff data is stored internally in the SEAM range

Is it too obvious thing to state? Above you already say it's needed.

>  Since handoff data layout
> may change between modules, the handoff data is versioned. Each module

Hmm, "likely"? Is this trying to justify the kernel's policy? Dunno, stands out
as weird to me. Like "this will mostly work". Sounds incomplete, rather than a
reason of "this policy is the optimal initial implementation" or something like
that.

> 
> Retrieve the module's handoff version from TDX global metadata and add an

This is small patch with both things, but it's almost two changes.

>  Module shutdown has global effect, so
> it only needs to run on one CPU.

I wouldn't think having some global effect would necessarily exclude having to
run on multiple CPUs. Or at least I don't follow. Is it a TDX arch thing? I
guess it's ok.

> 
> Note that the handoff information isn't cached in tdx_sysinfo. It is used

Instead of being a "note", could this be just an imperative: Don't cache the
handoff information in tdx_sysinfo...

> 
> Signed-off-by: Chao Gao <chao.gao@intel.com>

Where does the term 'primary' come from? I'm guessing that the global steps must
each be run on the same CPU? Is that right? And we just pick the cpu that we
know much be online? Or can the global steps be run on different CPUs? Or they
*have* to be run on cpu 0? It might be worth some comments explaining, depending
on the answers to those questions.

>  	do {
>  		newstate = READ_ONCE(update_ctrl.state);

Take or leave it:

  Why not just WARN_ON_ONCE(get_tdx_sys_info_handoff(&handoff));
  And we can drop the ret var. Save 2 LOC.

> +
> +	/*

---

## [61] Edgecombe, Rick P — 2026-05-19
*Subject: Re: [PATCH v9 19/23] x86/virt/tdx: Refresh TDX module version after
 update*

On Wed, 2026-05-13 at 08:10 -0700, Chao Gao wrote:
> The kernel exposes the TDX module version through sysfs so userspace can
> check update compatibility. That information needs to remain accurate

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

The only thing I saw missing from Dave's last comments was:
---
> Note that major and minor versions are not refreshed because runtime updates
> are supported only between releases with identical major and minor versions.

I'd rather have this in code than a changelog comment.

If they can't change then warn if they do.
---

But I think we discussed offline to not do this, is it right?

---

## [62] Chao Gao — 2026-05-19
*Subject: Re: [PATCH v9 13/23] x86/virt/seamldr: Abort updates after a failed
 step*

On Tue, May 19, 2026 at 10:34:31AM +0800, Edgecombe, Rick P wrote:
>On Wed, 2026-05-13 at 08:09 -0700, Chao Gao wrote:
>> A TDX module update is a multi-step process, and any step can fail.

Yes. it is better.

>
>> 

yes. the main point is certain update failures should be recoverable so userspace
can retry.

>
>And why talk about EBUSY specifically? It is not in this patch. Stale log? 

Sure. there is no need to single out EBUSY.

>
>> 

You are right. Any failure after the initial module shutdown step is
unrecoverable.

> Or can we put it in some other
>more specific terms like that. Terms which are more specific but still not

We could special-case the first step, but that would add step-specific
error handling to the update loop. I think the simpler rule is to abort the
update on the first observed failure, regardless of which step reports it.

how about:

A TDX module update is a multi-step process, and any step can fail.

The current update flow continues to later steps after an error.
Continuing after a failure can cause the TDX module to enter an
unrecoverable state.

But certain failures during the initial module shutdown step should
simply return an error to userspace, so the update can be retried cleanly.

To preserve that recoverability, one option would be to abort the update
only for those failures, since they occur before any TDX module state is
changed. But special-casing specific failures in specific steps would
complicate the do-while() update loop for no benefit.

Simply abort update on any failure, at any step.

Track failures for each step, stop the update loop once a failure is
observed, and do not advance the state machine to the next step.

>
>> 

Kiryl suggested a boolean, and I used that in earlier versions.  In v9 I
moved the failure tracking next to the ack counting in ack_state(). A
boolean still works, but it needs an extra conditional to latch the failure
state.

static void ack_state(struct update_ctrl *ctrl, int result)
{
	raw_spin_lock(&ctrl->lock);

-	ctrl->num_failed += !!ret;
+	if (!ctrl->failed)
+		ctrl->failed = !!ret;
	ctrl->num_ack++;
	if (ctrl->num_ack == num_online_cpus())
	if (ctrl->num_ack == num_online_cpus() && !ctrl->num_failed)
		__set_target_state(ctrl, ctrl->state + 1);

Using an int mainly to keep the failure and ack tracking similar
and avoid the extra if. (I put a note under --- to explain this.)

If you prefer, I can switch it back to bool.

---

## [63] Chao Gao — 2026-05-19
*Subject: Re: [PATCH v9 02/23] x86/virt/tdx: Move TDX_FEATURES0 bits to
 asm/tdx.h*

On Tue, May 19, 2026 at 09:59:02AM +0800, Edgecombe, Rick P wrote:
>On Mon, 2026-05-18 at 09:57 -0700, Rick Edgecombe wrote:
>> On Mon, 2026-05-18 at 15:52 +0800, Chao Gao wrote:

Yes. This looks much clearer.

Thanks for helping me on this.

---

## [64] Chao Gao — 2026-05-19
*Subject: Re: [PATCH v9 19/23] x86/virt/tdx: Refresh TDX module version after
 update*

On Tue, May 19, 2026 at 11:16:35AM +0800, Edgecombe, Rick P wrote:
>On Wed, 2026-05-13 at 08:10 -0700, Chao Gao wrote:
>> The kernel exposes the TDX module version through sysfs so userspace can

I will use version instead of update_version there. There is no need to
distinguish it from the major/minor version fields.

>> 
>> Drop __ro_after_init from tdx_sysinfo because it is now updated at runtime.

We didn't reach a firm conclusion on that.

But I think there is good reason not to do that, as I explained in my v8
reply:

 : Maybe I can just drop the note as I don't want to add code to preemptively
 : catch theoretical module bugs.
 : 
 : I added it because Sashiko pointed out that assigning the whole version struct
 : outside stop_machine() could allow sysfs readers to observe a partially updated
 : version. As we don't need to print new module version, I will move that
 : assignment into stop_machine(), which addresses that issue. After that, there
 : is no need to mention that major/minor versions are identical across updates.

---

## [65] Chao Gao — 2026-05-19
*Subject: Re: [PATCH v9 14/23] x86/virt/seamldr: Shut down the current TDX
 module*

On Tue, May 19, 2026 at 11:00:54AM +0800, Edgecombe, Rick P wrote:
>On Wed, 2026-05-13 at 08:09 -0700, Chao Gao wrote:
>> The first step of TDX module updates is shutting down the current TDX

Sure. Will do.

>
>> which will be consumed by the

Ok. Let me drop it.

>
>>  Since handoff data layout

how about:

... But since this implementation only supports module upgrades, simply request
handoff data from the current module using its highest supported version.
That is sufficient for this upgrade-only implementation.

>
>> 

Yes. This comes from the TDX architecture. I will just say in the changelog
that module shutdown only needs to run on one CPU.

>
>> 

Sure. Will do.

>
>> @@ -214,8 +216,16 @@ static void init_state(struct update_ctrl *ctrl)

"primary" is just my name for the CPU that runs the global steps. There is
nothing special about CPU 0 beyond the fact that it is guaranteed to be
online, so it is a convenient choice.

I can rename it to something like 'is_primary_cpu' or 'is_global_step_cpu'
for clarity.

how about:

/*
 * Some steps must be run on exactly one CPU. Pick CPU 0 to execute those
 * steps because CPU 0 is always online.
 */

>
>>  	do {

Dave had a different preference here:

https://lore.kernel.org/kvm/8b9d7fa7-6534-48e7-a4fa-c21260b1c762@intel.com/

---

## [66] Dave Hansen — 2026-05-19
*Subject: Re: [PATCH v9 14/23] x86/virt/seamldr: Shut down the current TDX
 module*

On 5/19/26 05:05, Chao Gao wrote:
>>  Why not just WARN_ON_ONCE(get_tdx_sys_info_handoff(&handoff));
>>  And we can drop the ret var. Save 2 LOC.

I almost never optimize for lines of code.

The _only_ reason to worry about it is when you have a chunk of logic
that's having issues fitting on a "screen". There, squishing a few lines
together can mean the difference between seeing a whole loop on one
screen or having to page around.

But, at the point you're doing *that*, you probably need to think about
refactoring anyway.

---

## [67] Binbin Wu — 2026-05-20
*Subject: Re: [PATCH v9 10/23] coco/tdx-host: Implement firmware upload sysfs
 ABI for TDX module updates*

On 5/13/2026 11:09 PM, Chao Gao wrote:

> diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
> index 7269a239bc22..7b345000d7c3 100644

This is not needed in this patch.

>  #include <linux/spinlock.h>
>

---

## [68] Chao Gao — 2026-05-20
*Subject: Re: [PATCH v9 10/23] coco/tdx-host: Implement firmware upload sysfs
 ABI for TDX module updates*

On Wed, May 20, 2026 at 05:18:03PM +0800, Binbin Wu wrote:
>
>

Right. linux/mm.h is only needed for vmalloc_to_pfn() in the next
patch, so I will move it there.

---
