---
title: 'Runtime TDX module update support'
date: 2026-05-20
last_reply: 2026-05-27
message_count: 42
participants: ['Chao Gao', 'Dave Hansen', 'Xiaoyao Li', 'Kiryl Shutsemau']
---

## [1] Chao Gao — 2026-05-20

Hi Dave & Rick,

Thanks for your thorough review of v9. This v10 addresses the issues you
pointed out. The main changes in this version are polishing changelogs
and variable renames to improve readability. Specifically:
 
   - Patches 1-2 (new): Split the original "Consolidate TDX global
     initialization states" into two steps — first move the statics to
     file scope, then clarify the result-caching logic in
     try_init_module_global().
   - Patch 6: Removed user-facing Kconfig help text for TDX_HOST_SERVICES
     (now a silent tristate auto-selected by INTEL_TDX_HOST).
   - Patch 13: Renamed "size" to "data_len" in seamldr_install_module()
     and init_seamldr_params(); renamed "HEADER_SIZE" to
     "TDX_IMAGE_HEADER_SIZE"; renamed "primary" to "is_lead_cpu" in the
     update state machine.
   - Patch 13: Added early data_len validation and explicit bounds checks
     on sigstruct_nr_pages/module_nr_pages against SEAMLDR_MAX_NR_*
     limits, removing the implicit clamping in populate_pa_list().
   - Patch 22: Fixed BIT(16) -> BIT_ULL(16) for
     TDX_SYS_SHUTDOWN_AVOID_COMPAT_SENSITIVE.
   - Patch 22: Removed unused TDX_FEATURES0_UPDATE_COMPAT definition.
   - Various patches: Shortened sysfs ABI descriptions, tightened
     comments across seamldr.h and seamldr.c, and minor style fixes
     (return 0 -> return false, unfolded conditionals)

Please take a look at this new version. I hope it can still be merged
for 7.2.
---

(For transparency, note that I used AI tools to help proofread this
cover-letter and commit messages)

This series adds support for runtime TDX module updates that preserve
running TDX guests. It is also available at:

  https://github.com/gaochaointel/linux-dev/commits/tdx-module-updates-v10/

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

NOTE: This v10 uses a new tdx_blob format. The scripts and module blobs in
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
a distinction between "launch-time" version and "current" version where
runtime TDX module updates cause that "current" version number to change,
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



Chao Gao (24):
  x86/virt/tdx: Clarify try_init_module_global() result caching
  x86/virt/tdx: Move TDX global initialization states to file scope
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
  x86/virt/seamldr: Do TDX global and per-CPU init after module
    installation
  x86/virt/tdx: Restore TDX module state
  x86/virt/tdx: Refresh TDX module version after update
  x86/virt/tdx: Reject updates during compatibility-sensitive operations
  x86/virt/tdx: Enable TDX module runtime updates
  coco/tdx-host: Document TDX module update compatibility criteria
  x86/virt/tdx: Document TDX module update

Kai Huang (1):
  x86/virt/tdx: Move low level SEAMCALL helpers out of <asm/tdx.h>

 .../ABI/testing/sysfs-devices-faux-tdx-host   |  66 ++++
 Documentation/arch/x86/tdx.rst                |  34 ++
 arch/x86/include/asm/cpufeatures.h            |   1 +
 arch/x86/include/asm/seamldr.h                |  36 ++
 arch/x86/include/asm/tdx.h                    |  66 +---
 arch/x86/include/asm/tdx_global_metadata.h    |   4 +
 arch/x86/include/asm/vmx.h                    |   1 +
 arch/x86/virt/vmx/tdx/Makefile                |   2 +-
 arch/x86/virt/vmx/tdx/seamcall_internal.h     | 109 ++++++
 arch/x86/virt/vmx/tdx/seamldr.c               | 324 ++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.c                   | 169 +++++----
 arch/x86/virt/vmx/tdx/tdx.h                   |   8 +-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c   |  17 +-
 drivers/virt/coco/Kconfig                     |   2 +
 drivers/virt/coco/Makefile                    |   1 +
 drivers/virt/coco/tdx-host/Kconfig            |   6 +
 drivers/virt/coco/tdx-host/Makefile           |   1 +
 drivers/virt/coco/tdx-host/tdx-host.c         | 231 +++++++++++++
 18 files changed, 965 insertions(+), 113 deletions(-)
 create mode 100644 Documentation/ABI/testing/sysfs-devices-faux-tdx-host
 create mode 100644 arch/x86/include/asm/seamldr.h
 create mode 100644 arch/x86/virt/vmx/tdx/seamcall_internal.h
 create mode 100644 arch/x86/virt/vmx/tdx/seamldr.c
 create mode 100644 drivers/virt/coco/tdx-host/Kconfig
 create mode 100644 drivers/virt/coco/tdx-host/Makefile
 create mode 100644 drivers/virt/coco/tdx-host/tdx-host.c


base-commit: 5209e5bfe5cab593476c3e7754e42c5e47ce36de

---

## [2] Chao Gao — 2026-05-20
*Subject: [PATCH v10 01/25] x86/virt/tdx: Clarify try_init_module_global() result caching*

TDX module global initialization is executed only once. The first call
caches both the result and the "done" state, and later callers reuse the
saved result. A lock protects that cached state.

The current code is hard to read because sysinit_done is accessed under
the lock, while sysinit_ret is not.

To improve readability, move sysinit_ret accesses within the lock.

Group sysinit_ret/sysinit_done updates right after initialization so
Caching the result is separate from the initialization itself.

Signed-off-by: Chao Gao <chao.gao@intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 14 ++++++++++----
 1 file changed, 10 insertions(+), 4 deletions(-)

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

## [3] Chao Gao — 2026-05-20
*Subject: [PATCH v10 02/25] x86/virt/tdx: Move TDX global initialization states to file scope*

TDX module global initialization is executed only once. The first call
caches both the result and the "done" state, and later callers reuse the
saved result. A lock protects that cached states.

Those states and the lock are currently kept as function-local statics
because they are used only by try_init_module_global().

TDX module updates need to reset the cached states so TDX global
initialization can be run again after an update. That will add another
access site in the same file.

Move the cached states to file scope so it is accessible outside
try_init_module_global(), and move the lock along with the states it
protects.

No functional change intended.

Signed-off-by: Chao Gao <chao.gao@intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 7 ++++---
 1 file changed, 4 insertions(+), 3 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index ad56f142dd0b..40444a3c5cdd 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -105,6 +105,10 @@ static __always_inline int sc_retry_prerr(sc_func_t func,
 #define seamcall_prerr_ret(__fn, __args)					\
 	sc_retry_prerr(__seamcall_ret, seamcall_err_ret, (__fn), (__args))
 
+static DEFINE_RAW_SPINLOCK(sysinit_lock);
+static bool sysinit_done;
+static int sysinit_ret;
+
 /*
  * Do the module global initialization once and return its result.
  * It can be done on any cpu, and from task or IRQ context.
@@ -112,9 +116,6 @@ static __always_inline int sc_retry_prerr(sc_func_t func,
 static int try_init_module_global(void)
 {
 	struct tdx_module_args args = {};
-	static DEFINE_RAW_SPINLOCK(sysinit_lock);
-	static bool sysinit_done;
-	static int sysinit_ret;
 	int ret;
 
 	raw_spin_lock(&sysinit_lock);

---

## [4] Chao Gao — 2026-05-20
*Subject: [PATCH v10 03/25] x86/virt/tdx: Consolidate TDX global initialization states*

The kernel uses several global flags to guard one-time TDX initialization
flows and prevent them from being repeated.

When the TDX module is updated, all of those states must be reset so that
the module can be initialized again. Today those states are kept as
separate global variables, which makes the reset path awkward and easy to
miss when a new state is added.

Group the states into a single structure so they can be reset together, for
example with memset(), and so a newly added state won't be missed.

Drop the __ro_after_init annotation from tdx_module_initialized because
the other two states do not have it. And with TDX module update support,
all the states need to be writable at runtime.

Signed-off-by: Chao Gao <chao.gao@intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 22 +++++++++++++---------
 1 file changed, 13 insertions(+), 9 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 40444a3c5cdd..71d39a79ef3f 100644
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
 
@@ -106,8 +112,6 @@ static __always_inline int sc_retry_prerr(sc_func_t func,
 	sc_retry_prerr(__seamcall_ret, seamcall_err_ret, (__fn), (__args))
 
 static DEFINE_RAW_SPINLOCK(sysinit_lock);
-static bool sysinit_done;
-static int sysinit_ret;
 
 /*
  * Do the module global initialization once and return its result.
@@ -121,8 +125,8 @@ static int try_init_module_global(void)
 	raw_spin_lock(&sysinit_lock);
 
 	/* Return the "cached" return code. */
-	if (sysinit_done) {
-		ret = sysinit_ret;
+	if (tdx_module_state.sysinit_done) {
+		ret = tdx_module_state.sysinit_ret;
 		goto out;
 	}
 
@@ -139,8 +143,8 @@ static int try_init_module_global(void)
 		pr_err("module not loaded\n");
 
 	/* Save the return code for later callers. */
-	sysinit_done = true;
-	sysinit_ret = ret;
+	tdx_module_state.sysinit_done = true;
+	tdx_module_state.sysinit_ret = ret;
 out:
 	raw_spin_unlock(&sysinit_lock);
 	return ret;
@@ -1306,7 +1310,7 @@ static __init int tdx_enable(void)
 
 	register_syscore(&tdx_syscore);
 
-	tdx_module_initialized = true;
+	tdx_module_state.initialized = true;
 	pr_info("TDX-Module initialized\n");
 	return 0;
 }
@@ -1561,7 +1565,7 @@ void __init tdx_init(void)
 
 const struct tdx_sys_info *tdx_get_sysinfo(void)
 {
-	if (!tdx_module_initialized)
+	if (!tdx_module_state.initialized)
 		return NULL;
 
 	return (const struct tdx_sys_info *)&tdx_sysinfo;

---

## [5] Chao Gao — 2026-05-20
*Subject: [PATCH v10 04/25] x86/virt/tdx: Move TDX_FEATURES0 bits to asm/tdx.h*

Future changes will add support for new TDX features exposed as
TDX_FEATURES0 bits. The presence of these features will need to be checked
outside of arch/x86/virt. So the feature query helpers, and the
TDX_FEATURES0 defines they reference, will need to live in the widely
accessible asm/tdx.h header. Move the existing TDX_FEATURES0 to asm/tdx.h
so that they can all be kept together.

Opportunistically switch to BIT_ULL() since TDX_FEATURES0 is 64-bit.

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

## [6] Chao Gao — 2026-05-20
*Subject: [PATCH v10 05/25] x86/virt/tdx: Move low level SEAMCALL helpers out of <asm/tdx.h>*

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
index 71d39a79ef3f..b329791db9c2 100644
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
 static DEFINE_RAW_SPINLOCK(sysinit_lock);
 
 /*

---

## [7] Chao Gao — 2026-05-20
*Subject: [PATCH v10 06/25] coco/tdx-host: Introduce a "tdx_host" device*

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

Thanks to Dan and Yilun for all the help on this one.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>
Link: https://lore.kernel.org/all/2025073035-bulginess-rematch-b92e@gregkh/ # [1]
---
v10:
 - Drop Kconfig prompt [Dave]
---
 arch/x86/virt/vmx/tdx/tdx.c           |  2 +-
 drivers/virt/coco/Kconfig             |  2 ++
 drivers/virt/coco/Makefile            |  1 +
 drivers/virt/coco/tdx-host/Kconfig    |  4 +++
 drivers/virt/coco/tdx-host/Makefile   |  1 +
 drivers/virt/coco/tdx-host/tdx-host.c | 43 +++++++++++++++++++++++++++
 6 files changed, 52 insertions(+), 1 deletion(-)
 create mode 100644 drivers/virt/coco/tdx-host/Kconfig
 create mode 100644 drivers/virt/coco/tdx-host/Makefile
 create mode 100644 drivers/virt/coco/tdx-host/tdx-host.c

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index b329791db9c2..5fb0441a9ac6 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1527,7 +1527,7 @@ const struct tdx_sys_info *tdx_get_sysinfo(void)
 
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
index 000000000000..cfe81b9c0364
--- /dev/null
+++ b/drivers/virt/coco/tdx-host/Kconfig
@@ -0,0 +1,4 @@
+config TDX_HOST_SERVICES
+	tristate
+	depends on INTEL_TDX_HOST
+	default m
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

## [8] Chao Gao — 2026-05-20
*Subject: [PATCH v10 07/25] coco/tdx-host: Expose TDX module version*

For TDX module updates, userspace needs to select compatible update
versions based on the current module version. This design delegates
module selection complexity to userspace because compatibility must
satisfy constraints from both the CPU and the running TDX module
version.

For example, the 1.5.x series runs on Sapphire Rapids but not Granite
Rapids, which needs 2.0.x. Updates are also constrained by version
distance, so a 1.5.6 module might permit updates to 1.5.7 but not to
1.5.20.

Expose the TDX module version to userspace via sysfs to aid module
selection. Since the TDX faux device will drive module updates, expose
the version as its attribute.

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
Reviewed-by: Dave Hansen <dave.hansen@linux.intel.com>
Link: https://lore.kernel.org/all/2025073035-bulginess-rematch-b92e@gregkh/ # [1]
---
v10:
 - Improve clarity of the changelog and ABI documentation [Dave]
---
 .../ABI/testing/sysfs-devices-faux-tdx-host   |  5 ++++
 arch/x86/include/asm/tdx.h                    |  6 +++++
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c   |  2 +-
 drivers/virt/coco/tdx-host/tdx-host.c         | 26 ++++++++++++++++++-
 4 files changed, 37 insertions(+), 2 deletions(-)
 create mode 100644 Documentation/ABI/testing/sysfs-devices-faux-tdx-host

diff --git a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
new file mode 100644
index 000000000000..47d73cb89f1e
--- /dev/null
+++ b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
@@ -0,0 +1,5 @@
+What:		/sys/devices/faux/tdx_host/version
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) Report the version of the loaded TDX module.
+		Formatted as "major.minor.update". Used by TDX module
+		update tooling. Example: "1.2.03".
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

## [9] Chao Gao — 2026-05-20
*Subject: [PATCH v10 08/25] x86/virt/seamldr: Introduce a wrapper for P-SEAMLDR SEAMCALLs*

The TDX architecture uses the "SEAMCALL" instruction to communicate with
SEAM mode software. Right now, the only SEAM mode software that the kernel
communicates with is the TDX module. But, there is actually another
component that runs in SEAM mode but it is separate from the TDX module:
the persistent SEAM loader or "P-SEAMLDR". Right now, the only component
that communicates with it is the BIOS which loads the TDX module itself at
boot. But, to support updating the TDX module, the kernel now needs to be
able to talk to it.

P-SEAMLDR SEAMCALLs differ from TDX module SEAMCALLs in areas such as
concurrency requirements.

Add a P-SEAMLDR wrapper to handle these differences and prepare for
implementing concrete functions.

Use seamcall_prerr() (not '_ret') because current P-SEAMLDR calls do not
use any output registers other than RAX.

Note: Despite the similar name, the NP-SEAMLDR ("Non-Persistent")
differs sharply from the P-SEAMLDR. It is an authenticated code module
(ACM) invoked exclusively by the BIOS at boot rather than a component
running in SEAM mode. The kernel cannot call it at runtime. It exposes
no SEAMCALL interface.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Dave Hansen <dave.hansen@linux.intel.com>
Link: https://cdrdv2.intel.com/v1/dl/getContent/733582 # [1]
---
v10:
 - make "main act" solution statement in a prominent place [Dave]
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

## [10] Chao Gao — 2026-05-20
*Subject: [PATCH v10 09/25] x86/virt/seamldr: Add a helper to retrieve P-SEAMLDR information*

P-SEAMLDR reports its state via SEAMLDR.INFO, including its version and
the number of remaining runtime updates.

This information is useful for userspace. For example, the admin can use
the P-SEAMLDR version to determine whether a candidate TDX module is
compatible with the running loader, and can use the remaining update count
to determine whether another runtime update is still possible.

Add a helper to retrieve P-SEAMLDR information in preparation for
exposing P-SEAMLDR version and other necessary information to userspace.
Export the new kAPI for use by the "tdx_host" device.

Note that there are two distinct P-SEAMLDR APIs with similar names:

  "SEAMLDR.INFO" is metadata about the loader. It's metadata for the
  update process.

  "SEAMLDR.SEAMINFO" is metadata about SEAM mode. It is for the module
  init process, not for the update process.

Use SEAMLDR.INFO here.

For details, see "Intel® Trust Domain Extensions - SEAM Loader (SEAMLDR)
Interface Specification".

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Dave Hansen <dave.hansen@linux.intel.com>
---
v10:
 - Shorten the comment above the SEAMLDR_INFO structure [Dave]
 - Use tdx_host consistently when referring to the device [Dave]
 - Shorten the changelog description about SEAMLDR.{INFO,SEAMINFO} [Dave]
---
 arch/x86/include/asm/seamldr.h  | 35 +++++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/seamldr.c | 20 ++++++++++++++++++-
 2 files changed, 54 insertions(+), 1 deletion(-)
 create mode 100644 arch/x86/include/asm/seamldr.h

diff --git a/arch/x86/include/asm/seamldr.h b/arch/x86/include/asm/seamldr.h
new file mode 100644
index 000000000000..a74151b75599
--- /dev/null
+++ b/arch/x86/include/asm/seamldr.h
@@ -0,0 +1,35 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+#ifndef _ASM_X86_SEAMLDR_H
+#define _ASM_X86_SEAMLDR_H
+
+#include <linux/types.h>
+
+/*
+ * This is the "SEAMLDR_INFO" data structure defined in the
+ * "SEAM Loader (SEAMLDR) Interface Specification".
+ *
+ * Must be aligned to a 256-byte boundary.
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

## [11] Chao Gao — 2026-05-20
*Subject: [PATCH v10 10/25] coco/tdx-host: Expose P-SEAMLDR information via sysfs*

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
Reviewed-by: Dave Hansen <dave.hansen@linux.intel.com>
---
v10:
 - Describe the P-SEAMLDR version by referring to the TDX module
   version instead of copying the text [Dave]
 - add a comment for DEVICE_ATTR_ADMIN_RO() [Dave]
 - Avoid the tertiary operator [Dave]
---
 .../ABI/testing/sysfs-devices-faux-tdx-host   | 21 ++++++
 arch/x86/include/asm/tdx.h                    |  6 ++
 drivers/virt/coco/tdx-host/tdx-host.c         | 72 ++++++++++++++++++-
 3 files changed, 98 insertions(+), 1 deletion(-)

diff --git a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
index 47d73cb89f1e..69b4cfc99d87 100644
--- a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
+++ b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
@@ -3,3 +3,24 @@ Contact:	linux-coco@lists.linux.dev
 Description:	(RO) Report the version of the loaded TDX module.
 		Formatted as "major.minor.update". Used by TDX module
 		update tooling. Example: "1.2.03".
+
+What:		/sys/devices/faux/tdx_host/seamldr_version
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) Report the version of the loaded P-SEAMLDR.
+		Formatted as a TDX module version. Used by TDX module
+		update tooling.
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
index ef117a836b3a..2997311f72fa 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -11,6 +11,7 @@
 #include <linux/sysfs.h>
 
 #include <asm/cpu_device_id.h>
+#include <asm/seamldr.h>
 #include <asm/tdx.h>
 
 static const struct x86_cpu_id tdx_host_ids[] = {
@@ -40,7 +41,76 @@ static struct attribute *tdx_host_attrs[] = {
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
+/*
+ * These attributes are intended for managing TDX module updates. Reading
+ * them issues a slow, serialized P-SEAMLDR query, so keep them admin-only.
+ */
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
+	if (!tdx_supports_runtime_update(sysinfo))
+		return 0;
+
+	return attr->mode;
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

## [12] Chao Gao — 2026-05-20
*Subject: [PATCH v10 11/25] coco/tdx-host: Don't expose P-SEAMLDR information on CPUs with erratum*

TDX-capable CPUs clobber the current VMCS on return from P-SEAMLDR, as
documented in Intel® Trust Domain CPU Architectural Extensions:

  SEAMRET from the P-SEAMLDR clears the current VMCS structure pointed
  to by the current-VMCS pointer. A VMM that invokes the P-SEAMLDR using
  SEAMCALL must reload the current-VMCS, if required, using the VMPTRLD
  instruction.

Clearing the current VMCS behind KVM's back will break KVM.

Future CPUs will fix this by preserving the current VMCS across
P-SEAMLDR calls. A future specification update will describe the SEAMRET
VMCS-clearing behavior as an erratum and to state that it does not occur
when IA32_VMX_BASIC[60] is set.

Add a CPU bug bit for this erratum and refuse to expose P-SEAMLDR
information on affected CPUs, because even reading the P-SEAMLDR sysfs
knobs would enter and exit P-SEAMLDR.

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
Reviewed-by: Dave Hansen <dave.hansen@linux.intel.com>
Link: https://lore.kernel.org/kvm/fedb3192-e68c-423c-93b2-a4dc2f964148@intel.com/ # [1]
Link: https://lore.kernel.org/kvm/aYIXFmT-676oN6j0@google.com/ # [2]
---
This is split into a separate patch rather than folded into the previous one,
because the erratum handling warrants a longer changelog and discussion of
the alternatives.

v10:
 - Make it clear that clearing VMCS is the current architecture behavior.
   but will be fixed by a later doc update.
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
index 5fb0441a9ac6..53cf99c41dbb 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -42,6 +42,7 @@
 #include <asm/processor.h>
 #include <asm/mce.h>
 #include <asm/virt.h>
+#include <asm/vmx.h>
 
 #include "seamcall_internal.h"
 #include "tdx.h"
@@ -1450,6 +1451,8 @@ static struct notifier_block tdx_memory_nb = {
 
 static void __init check_tdx_erratum(void)
 {
+	u64 basic_msr;
+
 	/*
 	 * These CPUs have an erratum.  A partial write from non-TD
 	 * software (e.g. via MOVNTI variants or UC/WC mapping) to TDX
@@ -1461,6 +1464,14 @@ static void __init check_tdx_erratum(void)
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
index 2997311f72fa..2cd7be7bb404 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -98,6 +98,14 @@ static umode_t seamldr_group_visible(struct kobject *kobj, struct attribute *att
 	if (!tdx_supports_runtime_update(sysinfo))
 		return 0;
 
+	/*
+	 * Calling P-SEAMLDR on CPUs with the seamret_invd_vmcs bug clears
+	 * the current VMCS, which breaks KVM. Verify the erratum is not
+	 * present before exposing P-SEAMLDR features.
+	 */
+	if (boot_cpu_has_bug(X86_BUG_SEAMRET_INVD_VMCS))
+		return 0;
+
 	return attr->mode;
 }

---

## [13] Chao Gao — 2026-05-20
*Subject: [PATCH v10 12/25] coco/tdx-host: Implement firmware upload sysfs ABI for TDX module updates*

tl;dr: Select fw_upload for doing TDX module updates. The process of
selecting among available update images is complicated and nuanced. Punt
the selection process out to userspace. One existing userspace
implementation today is the script in the Intel TDX Module Binaries
repository.

Long Version:

The kernel supports two primary firmware update mechanisms:
 1. request_firmware() - used by microcode, SEV firmware, hundreds of
			 other drivers
 2. 'struct fw_upload' - used by CXL, FPGA updates, dozens of others

The key difference between is that request_firmware() loads a named file
from the filesystem where the filename is kernel-controlled, while
fw_upload accepts firmware data directly from userspace.

TDX module firmware update selection policy is too complex for the kernel.
Leave it to userspace and use fw_upload.

Why fw_upload instead of request_firmware()?
============================================

Selecting a TDX module update image is not a simple "load the latest"
decision. Userspace needs to choose an image that is compatible with both
the platform and the currently running module.

Some constraints are hard requirements:

a. Module version series are platform-specific. For example, the 1.5.x
   series runs on Sapphire Rapids but not Granite Rapids, which needs
   2.0.x.

b. Updates are also constrained by version distance. A 1.5.6 module
   might permit updates to 1.5.7 but not to 1.5.50.

There may also be userspace policy choices:

c. Decide the update direction: upgrade or downgrade

d. Choose whether to optimize for fewer updates or smaller version
   steps, for example, 1.2.3=>1.2.5 versus 1.2.3=>1.2.4=>1.2.5.

Given that complexity, leave module selection to userspace and use
fw_upload.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Link: https://lore.kernel.org/kvm/01fc8946-eb84-46fa-9458-f345dd3f6033@intel.com/
---
Future patches add more cases to the switch in tdx_fw_write(). With only two
cases, the switch looks a bit awkward right now.

v10:
 - Polish the changelog [Dave]
 - Point to one existing userspace implementation [Dave]
 - Separate hard compatibility requirements from userspace policy choices
 - Use true/false rather than 0/1 for bool return values.
 - s/size/data_len
---
 arch/x86/include/asm/seamldr.h        |  1 +
 arch/x86/virt/vmx/tdx/seamldr.c       | 14 ++++
 drivers/virt/coco/tdx-host/Kconfig    |  2 +
 drivers/virt/coco/tdx-host/tdx-host.c | 92 +++++++++++++++++++++++++--
 4 files changed, 105 insertions(+), 4 deletions(-)

diff --git a/arch/x86/include/asm/seamldr.h b/arch/x86/include/asm/seamldr.h
index a74151b75599..43084e2daa2d 100644
--- a/arch/x86/include/asm/seamldr.h
+++ b/arch/x86/include/asm/seamldr.h
@@ -31,5 +31,6 @@ struct seamldr_info {
 static_assert(sizeof(struct seamldr_info) == 256);
 
 int seamldr_get_info(struct seamldr_info *seamldr_info);
+int seamldr_install_module(const u8 *data, u32 data_len);
 
 #endif /* _ASM_X86_SEAMLDR_H */
diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 7269a239bc22..d3880b0f93aa 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -41,3 +41,17 @@ int seamldr_get_info(struct seamldr_info *seamldr_info)
 	return seamldr_call(P_SEAMLDR_INFO, &args);
 }
 EXPORT_SYMBOL_FOR_MODULES(seamldr_get_info, "tdx-host");
+
+/**
+ * seamldr_install_module - Install a new TDX module.
+ * @data: Pointer to the TDX module image.
+ * @data_len: Size of the TDX module image.
+ *
+ * Returns 0 on success, negative error code on failure.
+ */
+int seamldr_install_module(const u8 *data, u32 data_len)
+{
+	/* TODO: Update TDX module here */
+	return 0;
+}
+EXPORT_SYMBOL_FOR_MODULES(seamldr_install_module, "tdx-host");
diff --git a/drivers/virt/coco/tdx-host/Kconfig b/drivers/virt/coco/tdx-host/Kconfig
index cfe81b9c0364..57d0c01a4357 100644
--- a/drivers/virt/coco/tdx-host/Kconfig
+++ b/drivers/virt/coco/tdx-host/Kconfig
@@ -1,4 +1,6 @@
 config TDX_HOST_SERVICES
 	tristate
 	depends on INTEL_TDX_HOST
+	select FW_LOADER
+	select FW_UPLOAD
 	default m
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 2cd7be7bb404..b32ab595047f 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -6,6 +6,7 @@
  */
 
 #include <linux/device/faux.h>
+#include <linux/firmware.h>
 #include <linux/module.h>
 #include <linux/mod_devicetable.h>
 #include <linux/sysfs.h>
@@ -88,15 +89,15 @@ static struct attribute *seamldr_attrs[] = {
 	NULL,
 };
 
-static umode_t seamldr_group_visible(struct kobject *kobj, struct attribute *attr, int idx)
+static bool supports_runtime_update(void)
 {
 	const struct tdx_sys_info *sysinfo = tdx_get_sysinfo();
 
 	if (!sysinfo)
-		return 0;
+		return false;
 
 	if (!tdx_supports_runtime_update(sysinfo))
-		return 0;
+		return false;
 
 	/*
 	 * Calling P-SEAMLDR on CPUs with the seamret_invd_vmcs bug clears
@@ -104,6 +105,14 @@ static umode_t seamldr_group_visible(struct kobject *kobj, struct attribute *att
 	 * present before exposing P-SEAMLDR features.
 	 */
 	if (boot_cpu_has_bug(X86_BUG_SEAMRET_INVD_VMCS))
+		return false;
+
+	return true;
+}
+
+static umode_t seamldr_group_visible(struct kobject *kobj, struct attribute *attr, int idx)
+{
+	if (!supports_runtime_update())
 		return 0;
 
 	return attr->mode;
@@ -120,6 +129,81 @@ static const struct attribute_group *tdx_host_groups[] = {
 	NULL,
 };
 
+static enum fw_upload_err tdx_fw_prepare(struct fw_upload *fwl,
+					 const u8 *data, u32 data_len)
+{
+	return FW_UPLOAD_ERR_NONE;
+}
+
+static enum fw_upload_err tdx_fw_write(struct fw_upload *fwl, const u8 *data,
+				       u32 offset, u32 data_len, u32 *written)
+{
+	int ret;
+
+	ret = seamldr_install_module(data, data_len);
+	switch (ret) {
+	case 0:
+		*written = data_len;
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
@@ -127,7 +211,7 @@ static int __init tdx_host_init(void)
 	if (!x86_match_cpu(tdx_host_ids) || !tdx_get_sysinfo())
 		return -ENODEV;
 
-	fdev = faux_device_create_with_groups(KBUILD_MODNAME, NULL, NULL, tdx_host_groups);
+	fdev = faux_device_create_with_groups(KBUILD_MODNAME, NULL, &tdx_host_ops, tdx_host_groups);
 	if (!fdev)
 		return -ENODEV;

---

## [14] Chao Gao — 2026-05-20
*Subject: [PATCH v10 13/25] x86/virt/seamldr: Allocate and populate a module update request*

There are two important ABIs here:

'struct tdx_image'	- The on-disk and in-memory format for a TDX
			  module update image.
'struct seamldr_params'	- The in-memory ABI passed to the TDX module
			  loader. Points to a single 'struct tdx_image'
			  broken up into 4k pages.

Userspace supplies the update image in struct tdx_image format. The
image consists of a header followed by a sigstruct and the module
binary. P-SEAMLDR, however, consumes struct seamldr_params rather than
the image directly.

Parse the struct tdx_image provided by userspace and populate a matching
struct seamldr_params.

The 'tdx_image' ABI is versioned. Two public versions exist today: 0x100
and 0x200. This kernel only accepts 0x200. The older 0x100 format is being
deprecated and is intentionally not supported here. Future versions of the
module might be able to use the same ABIs (user/kernel and kernel/SEAMLDR)
but they will not be able to use this kernel code.

Reject module images without that specific version. This ensures that the
kernel is able to understand the passed-in format.

Validate the struct tdx_image header before using it, because the header is
consumed solely by the kernel to locate the sigstruct and module within
the image. Do not validate the payload itself. The sigstruct and module
pages are passed through to P-SEAMLDR, which validates them as part of the
update flow.

sigstruct_pages_pa_list currently has only one entry, but it will grow to
four pages in the future. Keep it as an array for symmetry with
module_pages_pa_list and for extensibility.

Signed-off-by: Chao Gao <chao.gao@intel.com>
---
v10:
 - Add comments for init_seamldr_params() and its call site [Dave]
 - Use data_len/image_len rather than size [Dave]
 - Do bounds check rather than implicitly truncat the update image [Dave]
 - Explain why the header version is checked in changelog [Dave]
 - make init_seamldr_params() accept a tdx_image pointer [Dave]
 - vertical alignment for code has a pattern [Dave]
---
 arch/x86/virt/vmx/tdx/seamldr.c | 145 +++++++++++++++++++++++++++++++-
 1 file changed, 144 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index d3880b0f93aa..11bd28e8370c 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -6,6 +6,8 @@
  */
 #define pr_fmt(fmt)	"seamldr: " fmt
 
+#include <linux/mm.h>
+#include <linux/slab.h>
 #include <linux/spinlock.h>
 
 #include <asm/seamldr.h>
@@ -15,6 +17,35 @@
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
+ * This is the "SEAMLDR_PARAMS" data structure defined in the
+ * "SEAM Loader (SEAMLDR) Interface Specification".
+ *
+ * It is the in-memory ABI that the kernel passes to the P-SEAMLDR
+ * to update the TDX module. It breaks the TDX module image up in
+ * page-size pieces.
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
@@ -42,6 +73,98 @@ int seamldr_get_info(struct seamldr_info *seamldr_info)
 }
 EXPORT_SYMBOL_FOR_MODULES(seamldr_get_info, "tdx-host");
 
+#define TDX_IMAGE_VERSION_2		0x200
+
+struct tdx_image_header {
+	u16	version;
+	u16	checksum;
+	u8	signature[8];
+	u32	sigstruct_nr_pages;
+	u32	module_nr_pages;
+	u8	reserved[4076];
+} __packed;
+
+#define TDX_IMAGE_HEADER_SIZE sizeof(struct tdx_image_header)
+static_assert(TDX_IMAGE_HEADER_SIZE == 4096);
+
+/*
+ * Intel TDX module update ABI structure. aka. "TDX module blob".
+ *
+ * @payload contains sigstruct pages followed by module pages.
+ */
+struct tdx_image {
+	struct tdx_image_header header;
+	u8 payload[];
+};
+
+static void populate_pa_list(u64 *pa_list, const u8 *vmalloc_addr, u32 vmalloc_len_pages)
+{
+	int i;
+
+	for (i = 0; i < vmalloc_len_pages; i++) {
+		unsigned long offset = i * PAGE_SIZE;
+		unsigned long pfn = vmalloc_to_pfn(&vmalloc_addr[offset]);
+
+		pa_list[i] = pfn << PAGE_SHIFT;
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
+	populate_pa_list(params->sigstruct_pages_pa_list, sig, sig_nr_pages);
+	populate_pa_list(params->module_pages_pa_list, mod, mod_nr_pages);
+}
+
+/*
+ * @image points to a vmalloc()'d 'struct tdx_image'. Transform
+ * it into @params which is the P-SEAMLDR ABI format.
+ */
+static int init_seamldr_params(struct seamldr_params *params,
+			       const struct tdx_image *image,
+			       u32 image_len)
+{
+	const struct tdx_image_header *header	= &image->header;
+
+	u32 sigstruct_len	= header->sigstruct_nr_pages * PAGE_SIZE;
+	u32 module_len		= header->module_nr_pages * PAGE_SIZE;
+
+	u8 *header_start	= (u8 *)header;
+	u8 *header_end		= header_start + TDX_IMAGE_HEADER_SIZE;
+
+	u8 *sigstruct_start	= header_end;
+	u8 *sigstruct_end	= sigstruct_start + sigstruct_len;
+
+	u8 *module_start	= sigstruct_end;
+
+	/* Check the calculated payload size against the image size. */
+	if (TDX_IMAGE_HEADER_SIZE + sigstruct_len + module_len != image_len)
+		return -EINVAL;
+
+	/* Reject unsupported tdx_image ABI versions. */
+	if (header->version != TDX_IMAGE_VERSION_2)
+		return -EINVAL;
+
+	if (header->sigstruct_nr_pages > SEAMLDR_MAX_NR_SIG_PAGES ||
+	    header->module_nr_pages > SEAMLDR_MAX_NR_MODULE_PAGES)
+		return -EINVAL;
+
+	if (memcmp(header->signature, "TDX-BLOB", sizeof(header->signature)))
+		return -EINVAL;
+
+	if (memchr_inv(header->reserved, 0, sizeof(header->reserved)))
+		return -EINVAL;
+
+	populate_seamldr_params(params, sigstruct_start, header->sigstruct_nr_pages,
+					module_start,    header->module_nr_pages);
+	return 0;
+}
+
 /**
  * seamldr_install_module - Install a new TDX module.
  * @data: Pointer to the TDX module image.
@@ -51,7 +174,27 @@ EXPORT_SYMBOL_FOR_MODULES(seamldr_get_info, "tdx-host");
  */
 int seamldr_install_module(const u8 *data, u32 data_len)
 {
+	struct seamldr_params *params;
+	const struct tdx_image *image;
+	int ret;
+
+	if (data_len < TDX_IMAGE_HEADER_SIZE)
+		return -EINVAL;
+
+	image = (const struct tdx_image *)data;
+
+	params = kzalloc_obj(*params);
+	if (!params)
+		return -ENOMEM;
+
+	/* Populate 'params' from 'image'. */
+	ret = init_seamldr_params(params, image, data_len);
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

## [15] Chao Gao — 2026-05-20
*Subject: [PATCH v10 14/25] x86/virt/seamldr: Introduce skeleton for TDX module updates*

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
 arch/x86/virt/vmx/tdx/seamldr.c | 87 ++++++++++++++++++++++++++++++++-
 1 file changed, 86 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 11bd28e8370c..db6c52f65995 100644
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
 
@@ -165,6 +167,84 @@ static int init_seamldr_params(struct seamldr_params *params,
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
@@ -192,7 +272,12 @@ int seamldr_install_module(const u8 *data, u32 data_len)
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

## [16] Chao Gao — 2026-05-20
*Subject: [PATCH v10 15/25] x86/virt/seamldr: Abort updates after a failed step*

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
index db6c52f65995..002cdae3b1ff 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -181,6 +181,7 @@ enum module_update_state {
 static struct update_ctrl {
 	enum module_update_state state;
 	int num_ack;
+	int num_failed;
 	/*
 	 * Protect update_ctrl. Raw spinlock as it will be acquired from
 	 * interrupt-disabled contexts.
@@ -198,12 +199,13 @@ static void __set_target_state(struct update_ctrl *ctrl,
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
@@ -213,6 +215,7 @@ static void init_state(struct update_ctrl *ctrl)
 {
 	raw_spin_lock_init(&ctrl->lock);
 	__set_target_state(ctrl, MODULE_UPDATE_START + 1);
+	ctrl->num_failed = 0;
 }
 
 /*
@@ -239,8 +242,8 @@ static int do_seamldr_install_module(void *seamldr_params)
 			break;
 		}
 
-		ack_state(&update_ctrl);
-	} while (curstate != MODULE_UPDATE_DONE);
+		ack_state(&update_ctrl, ret);
+	} while (curstate != MODULE_UPDATE_DONE && !READ_ONCE(update_ctrl.num_failed));
 
 	return ret;
 }

---

## [17] Chao Gao — 2026-05-20
*Subject: [PATCH v10 16/25] x86/virt/seamldr: Shut down the current TDX module*

The first step of TDX module updates is shutting down the current TDX
module. This step also packs state information that needs to be
preserved across updates, called "handoff data". This handoff data is
consumed by the updated module and stored internally in the SEAM range and
hidden from the kernel.

Since handoff data layout may change between modules, the handoff data is
versioned. Each module has a native handoff version and provides backward
support for several older versions.

The complete handoff versioning protocol is complex as it supports both
module upgrades and downgrades. See details in Intel® Trust Domain
Extensions (Intel® TDX) Module Base Architecture Specification, Chapter
"Handoff Versioning".

Ideally, the kernel needs to retrieve the handoff versions supported by
the current module and the new module and select a version supported by
both. But since this implementation only supports module upgrades, simply
request handoff data from the current module using its highest supported
version. That is sufficient for this upgrade-only implementation.

Retrieve the module's handoff version from TDX global metadata and add an
update step to shut down the module. Module shutdown only needs to run on
one CPU.

Don't cache the handoff information in tdx_sysinfo. It is used only for
module shutdown, and is present only when the TDX module supports updates.
Caching it in get_tdx_sys_info() would require extra update-support guards
and refreshing the cached value across module updates.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
---
v10:
 - Polish the changelog [Rick]
 - Rename "primary" to "is_lead_cpu" and polish the comment above it [Rick]
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
index 002cdae3b1ff..217b3c962aff 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -15,6 +15,7 @@
 #include <asm/seamldr.h>
 
 #include "seamcall_internal.h"
+#include "tdx.h"
 
 /* P-SEAMLDR SEAMCALL leaf function */
 #define P_SEAMLDR_INFO			0x8000000000000000
@@ -175,6 +176,7 @@ static int init_seamldr_params(struct seamldr_params *params,
  */
 enum module_update_state {
 	MODULE_UPDATE_START,
+	MODULE_UPDATE_SHUTDOWN,
 	MODULE_UPDATE_DONE,
 };
 
@@ -225,8 +227,16 @@ static void init_state(struct update_ctrl *ctrl)
 static int do_seamldr_install_module(void *seamldr_params)
 {
 	enum module_update_state newstate, curstate = MODULE_UPDATE_START;
+	int cpu = smp_processor_id();
+	bool is_lead_cpu;
 	int ret = 0;
 
+	/*
+	 * Some steps must be run on exactly one CPU. Pick a "lead" CPU to
+	 * execute those steps. Use CPU 0 because it is always online.
+	 */
+	is_lead_cpu = cpu == 0;
+
 	do {
 		newstate = READ_ONCE(update_ctrl.state);
 
@@ -237,7 +247,10 @@ static int do_seamldr_install_module(void *seamldr_params)
 
 		curstate = newstate;
 		switch (curstate) {
-		/* TODO: add the update steps. */
+		case MODULE_UPDATE_SHUTDOWN:
+			if (is_lead_cpu)
+				ret = tdx_module_shutdown();
+			break;
 		default:
 			break;
 		}
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 53cf99c41dbb..84d5df70a250 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -328,7 +328,7 @@ static __init int build_tdx_memlist(struct list_head *tmb_list)
 	return ret;
 }
 
-static __init int read_sys_metadata_field(u64 field_id, u64 *data)
+static int read_sys_metadata_field(u64 field_id, u64 *data)
 {
 	struct tdx_module_args args = {};
 	int ret;
@@ -1274,6 +1274,23 @@ static __init int tdx_enable(void)
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

## [18] Chao Gao — 2026-05-20
*Subject: [PATCH v10 17/25] x86/virt/tdx: Reset software states during TDX module shutdown*

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
index 84d5df70a250..01d0087180a0 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1278,7 +1278,7 @@ int tdx_module_shutdown(void)
 {
 	struct tdx_sys_info_handoff handoff = {};
 	struct tdx_module_args args = {};
-	int ret;
+	int ret, cpu;
 
 	ret = get_tdx_sys_info_handoff(&handoff);
 	WARN_ON_ONCE(ret);
@@ -1288,7 +1288,21 @@ int tdx_module_shutdown(void)
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

## [19] Chao Gao — 2026-05-20
*Subject: [PATCH v10 18/25] x86/virt/seamldr: Install a new TDX module*

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
index 217b3c962aff..afd8179e5c98 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -19,6 +19,7 @@
 
 /* P-SEAMLDR SEAMCALL leaf function */
 #define P_SEAMLDR_INFO			0x8000000000000000
+#define P_SEAMLDR_INSTALL		0x8000000000000001
 
 #define SEAMLDR_MAX_NR_MODULE_PAGES	496
 #define SEAMLDR_MAX_NR_SIG_PAGES	1
@@ -76,6 +77,15 @@ int seamldr_get_info(struct seamldr_info *seamldr_info)
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
@@ -177,6 +187,7 @@ static int init_seamldr_params(struct seamldr_params *params,
 enum module_update_state {
 	MODULE_UPDATE_START,
 	MODULE_UPDATE_SHUTDOWN,
+	MODULE_UPDATE_CPU_INSTALL,
 	MODULE_UPDATE_DONE,
 };
 
@@ -251,6 +262,9 @@ static int do_seamldr_install_module(void *seamldr_params)
 			if (is_lead_cpu)
 				ret = tdx_module_shutdown();
 			break;
+		case MODULE_UPDATE_CPU_INSTALL:
+			ret = seamldr_install(seamldr_params);
+			break;
 		default:
 			break;
 		}

---

## [20] Chao Gao — 2026-05-20
*Subject: [PATCH v10 19/25] x86/virt/seamldr: Do TDX global and per-CPU init after module installation*

After installing a new TDX module, the kernel must re-initialize TDX
before resuming TDX operations.

This post-update initialization differs from the initial boot-time
initialization. It only needs TDX global initialization, TDX per-CPU
initialization, and restoration of TDX state from the handoff data.

tdx_cpu_enable() covers the global and per-CPU initialization. Export it
and invoke it on all CPUs.

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
index afd8179e5c98..a026de7f7bcd 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -188,6 +188,7 @@ enum module_update_state {
 	MODULE_UPDATE_START,
 	MODULE_UPDATE_SHUTDOWN,
 	MODULE_UPDATE_CPU_INSTALL,
+	MODULE_UPDATE_CPU_INIT,
 	MODULE_UPDATE_DONE,
 };
 
@@ -265,6 +266,9 @@ static int do_seamldr_install_module(void *seamldr_params)
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
index 01d0087180a0..5292dd8d1e36 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -113,7 +113,7 @@ static int try_init_module_global(void)
  * (and TDX module global initialization SEAMCALL if not done) on local cpu to
  * make this cpu be ready to run any other SEAMCALLs.
  */
-static int tdx_cpu_enable(void)
+int tdx_cpu_enable(void)
 {
 	struct tdx_module_args args = {};
 	int ret;

---

## [21] Chao Gao — 2026-05-20
*Subject: [PATCH v10 20/25] x86/virt/tdx: Restore TDX module state*

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

No error is expected if the new module is fully compatible, and userspace
should enforce that as part of update image selection.  Given the
complexity and uncertain value of the recovery paths above, simply
propagate errors.

Note: the location and the format of handoff data is defined by
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
index a026de7f7bcd..ff95d8dd1162 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -189,6 +189,7 @@ enum module_update_state {
 	MODULE_UPDATE_SHUTDOWN,
 	MODULE_UPDATE_CPU_INSTALL,
 	MODULE_UPDATE_CPU_INIT,
+	MODULE_UPDATE_RUN_UPDATE,
 	MODULE_UPDATE_DONE,
 };
 
@@ -269,6 +270,10 @@ static int do_seamldr_install_module(void *seamldr_params)
 		case MODULE_UPDATE_CPU_INIT:
 			ret = tdx_cpu_enable();
 			break;
+		case MODULE_UPDATE_RUN_UPDATE:
+			if (is_lead_cpu)
+				ret = tdx_module_run_update();
+			break;
 		default:
 			break;
 		}
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 5292dd8d1e36..e3f5aa272850 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1305,6 +1305,19 @@ int tdx_module_shutdown(void)
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

## [22] Chao Gao — 2026-05-20
*Subject: [PATCH v10 21/25] x86/virt/tdx: Refresh TDX module version after update*

The kernel exposes the TDX module version through sysfs so userspace can
check update compatibility. That information needs to remain accurate
across runtime updates.

A runtime update may change the module's update_version, so refresh the
cached version right after a successful update.

Drop __ro_after_init from tdx_sysinfo because it is now updated at runtime.

Do not refresh the rest of tdx_sysinfo, even if some values change across
updates. TDX module updates are backward compatible, so existing
tdx_sysinfo consumers, such as KVM, can continue to operate without seeing
the new values.

Refreshing the full structure would be risky. A tdx_sysinfo consumer may
initialize its TDX support based on the features originally reported in
tdx_sysinfo. If a runtime update adds new features and the full structure
is refreshed, that consumer could observe and use the newly reported
features without having performed the setup required to use them safely.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
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
index e3f5aa272850..55670365a388 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -67,7 +67,7 @@ static struct tdmr_info_list tdx_tdmr_list;
 /* All TDX-usable memory regions.  Protected by mem_hotplug_lock. */
 static LIST_HEAD(tdx_memlist);
 
-static struct tdx_sys_info tdx_sysinfo __ro_after_init;
+static struct tdx_sys_info tdx_sysinfo;
 
 static DEFINE_RAW_SPINLOCK(sysinit_lock);
 
@@ -1314,6 +1314,10 @@ int tdx_module_run_update(void)
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

## [23] Chao Gao — 2026-05-20
*Subject: [PATCH v10 22/25] x86/virt/tdx: Reject updates during compatibility-sensitive operations*

A TDX module erratum can cause TD state corruption if a module update races
with a compatibility-sensitive operation. For example, if an update races
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
v10:
 - Don't add a "dead" TDX_FEATURE0 bit [Sashiko]
 - s/BIT/BIT_ULL
---
 arch/x86/include/asm/tdx.h            |  5 +++--
 arch/x86/virt/vmx/tdx/tdx.c           | 30 ++++++++++++++++++++++++---
 drivers/virt/coco/tdx-host/tdx-host.c |  2 ++
 3 files changed, 32 insertions(+), 5 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 5d750fe53669..282cb0e08b8e 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -29,8 +29,9 @@
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
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 55670365a388..0c5660c9ab45 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1274,11 +1274,14 @@ static __init int tdx_enable(void)
 }
 subsys_initcall(tdx_enable);
 
+#define TDX_SYS_SHUTDOWN_AVOID_COMPAT_SENSITIVE BIT_ULL(16)
+
 int tdx_module_shutdown(void)
 {
 	struct tdx_sys_info_handoff handoff = {};
 	struct tdx_module_args args = {};
 	int ret, cpu;
+	u64 err;
 
 	ret = get_tdx_sys_info_handoff(&handoff);
 	WARN_ON_ONCE(ret);
@@ -1288,9 +1291,30 @@ int tdx_module_shutdown(void)
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
index b32ab595047f..291464490fe0 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -145,6 +145,8 @@ static enum fw_upload_err tdx_fw_write(struct fw_upload *fwl, const u8 *data,
 	case 0:
 		*written = data_len;
 		return FW_UPLOAD_ERR_NONE;
+	case -EBUSY:
+		return FW_UPLOAD_ERR_BUSY;
 	default:
 		return FW_UPLOAD_ERR_FW_INVALID;
 	}

---

## [24] Chao Gao — 2026-05-20
*Subject: [PATCH v10 23/25] x86/virt/tdx: Enable TDX module runtime updates*

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
index 282cb0e08b8e..c848483d815f 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -34,6 +34,7 @@
 #define TDX_UPDATE_COMPAT_SENSITIVE	0x8000051200000000ULL
 
 /* Bit definitions of TDX_FEATURES0 metadata field */
+#define TDX_FEATURES0_TD_PRESERVING	BIT_ULL(1)
 #define TDX_FEATURES0_NO_RBP_MOD	BIT_ULL(18)
 
 #ifndef __ASSEMBLER__
@@ -114,8 +115,7 @@ const struct tdx_sys_info *tdx_get_sysinfo(void);
 
 static inline bool tdx_supports_runtime_update(const struct tdx_sys_info *sysinfo)
 {
-	/* To be enabled when kernel is ready. */
-	return false;
+	return sysinfo->features.tdx_features0 & TDX_FEATURES0_TD_PRESERVING;
 }
 
 int tdx_guest_keyid_alloc(void);

---

## [25] Chao Gao — 2026-05-20
*Subject: [PATCH v10 24/25] coco/tdx-host: Document TDX module update compatibility criteria*

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
index 69b4cfc99d87..5f18ac972468 100644
--- a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
+++ b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
@@ -24,3 +24,43 @@ Description:	(RO) Report the number of remaining updates. TDX maintains a
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

## [26] Chao Gao — 2026-05-20
*Subject: [PATCH v10 25/25] x86/virt/tdx: Document TDX module update*

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

## [27] Chao Gao — 2026-05-20
*Subject: Re: [PATCH v10 00/25] Runtime TDX module update support*

On Wed, May 20, 2026 at 06:38:03AM -0700, Chao Gao wrote:
>Hi Dave & Rick,
>

FYI, below is the diff between v9 and v10:

diff --git a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
index 9e08db231da1..5f18ac972468 100644
--- a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
+++ b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
@@ -1,16 +1,14 @@
 What:		/sys/devices/faux/tdx_host/version
 Contact:	linux-coco@lists.linux.dev
-Description:	(RO) Report the version of the loaded TDX module. The TDX module
-		version is formatted as x.y.z, where "x" is the major version,
-		"y" is the minor version and "z" is the update version. Versions
-		are used for bug reporting, TDX module updates etc.
+Description:	(RO) Report the version of the loaded TDX module.
+		Formatted as "major.minor.update". Used by TDX module
+		update tooling. Example: "1.2.03".
 
 What:		/sys/devices/faux/tdx_host/seamldr_version
 Contact:	linux-coco@lists.linux.dev
-Description:	(RO) Report the version of the loaded P-SEAMLDR. The P-SEAMLDR
-		version is formatted as x.y.z, where "x" is the major version,
-		"y" is the minor version and "z" is the update version. Versions
-		are used for bug reporting and compatibility checks.
+Description:	(RO) Report the version of the loaded P-SEAMLDR.
+		Formatted as a TDX module version. Used by TDX module
+		update tooling.
 
 What:		/sys/devices/faux/tdx_host/num_remaining_updates
 Contact:	linux-coco@lists.linux.dev
diff --git a/arch/x86/include/asm/seamldr.h b/arch/x86/include/asm/seamldr.h
index ac6f80f7208b..43084e2daa2d 100644
--- a/arch/x86/include/asm/seamldr.h
+++ b/arch/x86/include/asm/seamldr.h
@@ -5,11 +5,10 @@
 #include <linux/types.h>
 
 /*
- * This is called the "SEAMLDR_INFO" data structure and is defined
- * in "SEAM Loader (SEAMLDR) Interface Specification".
+ * This is the "SEAMLDR_INFO" data structure defined in the
+ * "SEAM Loader (SEAMLDR) Interface Specification".
  *
- * The SEAMLDR.INFO documentation requires this to be aligned to a
- * 256-byte boundary.
+ * Must be aligned to a 256-byte boundary.
  */
 struct seamldr_info {
	u32	version;
@@ -32,6 +31,6 @@ struct seamldr_info {
 static_assert(sizeof(struct seamldr_info) == 256);
 
 int seamldr_get_info(struct seamldr_info *seamldr_info);
-int seamldr_install_module(const u8 *data, u32 size);
+int seamldr_install_module(const u8 *data, u32 data_len);
 
 #endif /* _ASM_X86_SEAMLDR_H */
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index ac042b369843..c848483d815f 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -36,7 +36,6 @@
 /* Bit definitions of TDX_FEATURES0 metadata field */
 #define TDX_FEATURES0_TD_PRESERVING	BIT_ULL(1)
 #define TDX_FEATURES0_NO_RBP_MOD	BIT_ULL(18)
-#define TDX_FEATURES0_UPDATE_COMPAT	BIT_ULL(47)
 
 #ifndef __ASSEMBLER__
 
diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 6a39c9e3ef7d..ff95d8dd1162 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -32,10 +32,12 @@
 #define SEAMLDR_SCENARIO_UPDATE		1
 
 /*
- * This is called the "SEAMLDR_PARAMS" data structure and is defined
- * in "SEAM Loader (SEAMLDR) Interface Specification".
+ * This is the "SEAMLDR_PARAMS" data structure defined in the
+ * "SEAM Loader (SEAMLDR) Interface Specification".
  *
- * It describes the TDX module that will be installed.
+ * It is the in-memory ABI that the kernel passes to the P-SEAMLDR
+ * to update the TDX module. It breaks the TDX module image up in
+ * page-size pieces.
  */
 struct seamldr_params {
	u32	version;
@@ -87,7 +89,7 @@ static int seamldr_install(const struct seamldr_params *params)
 #define TDX_IMAGE_VERSION_2		0x200
 
 struct tdx_image_header {
-	u16	version; // This ABI is always 0x200
+	u16	version;
	u16	checksum;
	u8	signature[8];
	u32	sigstruct_nr_pages;
@@ -95,23 +97,28 @@ struct tdx_image_header {
	u8	reserved[4076];
 } __packed;
 
-#define HEADER_SIZE sizeof(struct tdx_image_header)
-static_assert(HEADER_SIZE == 4096);
+#define TDX_IMAGE_HEADER_SIZE sizeof(struct tdx_image_header)
+static_assert(TDX_IMAGE_HEADER_SIZE == 4096);
 
-/* Intel TDX module update ABI structure. aka. "TDX module blob". */
+/*
+ * Intel TDX module update ABI structure. aka. "TDX module blob".
+ *
+ * @payload contains sigstruct pages followed by module pages.
+ */
 struct tdx_image {
	struct tdx_image_header header;
-	u8 payload[]; // Contains sigstruct pages followed by module pages
+	u8 payload[];
 };
 
-static void populate_pa_list(u64 *pa_list, u32 max_entries, const u8 *start, u32 nr_pages)
+static void populate_pa_list(u64 *pa_list, const u8 *vmalloc_addr, u32 vmalloc_len_pages)
 {
	int i;
 
-	nr_pages = MIN(nr_pages, max_entries);
-	for (i = 0; i < nr_pages; i++) {
-		pa_list[i] = vmalloc_to_pfn(start) << PAGE_SHIFT;
-		start += PAGE_SIZE;
+	for (i = 0; i < vmalloc_len_pages; i++) {
+		unsigned long offset = i * PAGE_SIZE;
+		unsigned long pfn = vmalloc_to_pfn(&vmalloc_addr[offset]);
+
+		pa_list[i] = pfn << PAGE_SHIFT;
	}
 }
 
@@ -123,39 +130,43 @@ static void populate_seamldr_params(struct seamldr_params *params,
	params->scenario		= SEAMLDR_SCENARIO_UPDATE;
	params->module_nr_pages		= mod_nr_pages;
 
-	populate_pa_list(params->sigstruct_pages_pa_list, SEAMLDR_MAX_NR_SIG_PAGES,
-			 sig, sig_nr_pages);
-	populate_pa_list(params->module_pages_pa_list, SEAMLDR_MAX_NR_MODULE_PAGES,
-			 mod, mod_nr_pages);
+	populate_pa_list(params->sigstruct_pages_pa_list, sig, sig_nr_pages);
+	populate_pa_list(params->module_pages_pa_list, mod, mod_nr_pages);
 }
 
-static int init_seamldr_params(struct seamldr_params *params, const u8 *data, u32 size)
+/*
+ * @image points to a vmalloc()'d 'struct tdx_image'. Transform
+ * it into @params which is the P-SEAMLDR ABI format.
+ */
+static int init_seamldr_params(struct seamldr_params *params,
+			       const struct tdx_image *image,
+			       u32 image_len)
 {
-	const struct tdx_image *image		= (const void *)data;
	const struct tdx_image_header *header	= &image->header;
 
	u32 sigstruct_len	= header->sigstruct_nr_pages * PAGE_SIZE;
	u32 module_len		= header->module_nr_pages * PAGE_SIZE;
 
	u8 *header_start	= (u8 *)header;
-	u8 *header_end		= header_start + HEADER_SIZE;
+	u8 *header_end		= header_start + TDX_IMAGE_HEADER_SIZE;
 
	u8 *sigstruct_start	= header_end;
	u8 *sigstruct_end	= sigstruct_start + sigstruct_len;
 
	u8 *module_start	= sigstruct_end;
 
-	/* Check the calculated payload size against the data size. */
-	if (HEADER_SIZE + sigstruct_len + module_len != size)
+	/* Check the calculated payload size against the image size. */
+	if (TDX_IMAGE_HEADER_SIZE + sigstruct_len + module_len != image_len)
		return -EINVAL;
 
-	/*
-	 * Don't care about user passing the wrong file, but protect
-	 * kernel ABI by preventing accepting garbage.
-	 */
+	/* Reject unsupported tdx_image ABI versions. */
	if (header->version != TDX_IMAGE_VERSION_2)
		return -EINVAL;
 
+	if (header->sigstruct_nr_pages > SEAMLDR_MAX_NR_SIG_PAGES ||
+	    header->module_nr_pages > SEAMLDR_MAX_NR_MODULE_PAGES)
+		return -EINVAL;
+
	if (memcmp(header->signature, "TDX-BLOB", sizeof(header->signature)))
		return -EINVAL;
 
@@ -163,7 +174,7 @@ static int init_seamldr_params(struct seamldr_params *params, const u8 *data, u3
		return -EINVAL;
 
	populate_seamldr_params(params, sigstruct_start, header->sigstruct_nr_pages,
-				module_start, header->module_nr_pages);
+					module_start,    header->module_nr_pages);
	return 0;
 }
 
@@ -230,14 +241,14 @@ static int do_seamldr_install_module(void *seamldr_params)
 {
	enum module_update_state newstate, curstate = MODULE_UPDATE_START;
	int cpu = smp_processor_id();
-	bool primary;
+	bool is_lead_cpu;
	int ret = 0;
 
	/*
-	 * Use CPU 0 to execute update steps that must run exactly once.
-	 * Note CPU 0 is always online.
+	 * Some steps must be run on exactly one CPU. Pick a "lead" CPU to
+	 * execute those steps. Use CPU 0 because it is always online.
	 */
-	primary = cpu == 0;
+	is_lead_cpu = cpu == 0;
 
	do {
		newstate = READ_ONCE(update_ctrl.state);
@@ -250,7 +261,7 @@ static int do_seamldr_install_module(void *seamldr_params)
		curstate = newstate;
		switch (curstate) {
		case MODULE_UPDATE_SHUTDOWN:
-			if (primary)
+			if (is_lead_cpu)
				ret = tdx_module_shutdown();
			break;
		case MODULE_UPDATE_CPU_INSTALL:
@@ -260,7 +271,7 @@ static int do_seamldr_install_module(void *seamldr_params)
			ret = tdx_cpu_enable();
			break;
		case MODULE_UPDATE_RUN_UPDATE:
-			if (primary)
+			if (is_lead_cpu)
				ret = tdx_module_run_update();
			break;
		default:
@@ -276,20 +287,27 @@ static int do_seamldr_install_module(void *seamldr_params)
 /**
  * seamldr_install_module - Install a new TDX module.
  * @data: Pointer to the TDX module image.
- * @size: Size of the TDX module image.
+ * @data_len: Size of the TDX module image.
  *
  * Returns 0 on success, negative error code on failure.
  */
-int seamldr_install_module(const u8 *data, u32 size)
+int seamldr_install_module(const u8 *data, u32 data_len)
 {
	struct seamldr_params *params;
+	const struct tdx_image *image;
	int ret;
 
+	if (data_len < TDX_IMAGE_HEADER_SIZE)
+		return -EINVAL;
+
+	image = (const struct tdx_image *)data;
+
	params = kzalloc_obj(*params);
	if (!params)
		return -ENOMEM;
 
-	ret = init_seamldr_params(params, data, size);
+	/* Populate 'params' from 'image'. */
+	ret = init_seamldr_params(params, image, data_len);
	if (ret)
		goto out;
 
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 2ab6f6efe6d1..0c5660c9ab45 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -69,6 +69,8 @@ static LIST_HEAD(tdx_memlist);
 
 static struct tdx_sys_info tdx_sysinfo;
 
+static DEFINE_RAW_SPINLOCK(sysinit_lock);
+
 /*
  * Do the module global initialization once and return its result.
  * It can be done on any cpu, and from task or IRQ context.
@@ -76,29 +78,34 @@ static struct tdx_sys_info tdx_sysinfo;
 static int try_init_module_global(void)
 {
	struct tdx_module_args args = {};
-	static DEFINE_RAW_SPINLOCK(sysinit_lock);
+	int ret;
 
	raw_spin_lock(&sysinit_lock);
 
-	if (tdx_module_state.sysinit_done)
+	/* Return the "cached" return code. */
+	if (tdx_module_state.sysinit_done) {
+		ret = tdx_module_state.sysinit_ret;
		goto out;
+	}
 
	/* RCX is module attributes and all bits are reserved */
	args.rcx = 0;
-	tdx_module_state.sysinit_ret = seamcall_prerr(TDH_SYS_INIT, &args);
+	ret = seamcall_prerr(TDH_SYS_INIT, &args);
 
	/*
	 * The first SEAMCALL also detects the TDX module, thus
	 * it can fail due to the TDX module is not loaded.
	 * Dump message to let the user know.
	 */
-	if (tdx_module_state.sysinit_ret == -ENODEV)
+	if (ret == -ENODEV)
		pr_err("module not loaded\n");
 
+	/* Save the return code for later callers. */
	tdx_module_state.sysinit_done = true;
+	tdx_module_state.sysinit_ret = ret;
 out:
	raw_spin_unlock(&sysinit_lock);
-	return tdx_module_state.sysinit_ret;
+	return ret;
 }
 
 /**
@@ -1267,7 +1274,7 @@ static __init int tdx_enable(void)
 }
 subsys_initcall(tdx_enable);
 
-#define TDX_SYS_SHUTDOWN_AVOID_COMPAT_SENSITIVE BIT(16)
+#define TDX_SYS_SHUTDOWN_AVOID_COMPAT_SENSITIVE BIT_ULL(16)
 
 int tdx_module_shutdown(void)
 {
diff --git a/drivers/virt/coco/tdx-host/Kconfig b/drivers/virt/coco/tdx-host/Kconfig
index ca600a39d97b..57d0c01a4357 100644
--- a/drivers/virt/coco/tdx-host/Kconfig
+++ b/drivers/virt/coco/tdx-host/Kconfig
@@ -1,12 +1,6 @@
 config TDX_HOST_SERVICES
-	tristate "TDX Host Services Driver"
+	tristate
	depends on INTEL_TDX_HOST
	select FW_LOADER
	select FW_UPLOAD
	default m
-	help
-	  Enable access to TDX host services like module update and
-	  extensions (e.g. TDX Connect).
-
-	  Say y or m if enabling support for confidential virtual machine
-	  support (CONFIG_INTEL_TDX_HOST). The module is called tdx_host.ko.
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index ad116e56aa1a..291464490fe0 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -76,6 +76,10 @@ static ssize_t num_remaining_updates_show(struct device *dev,
	return sysfs_emit(buf, "%u\n", info.num_remaining_updates);
 }
 
+/*
+ * These attributes are intended for managing TDX module updates. Reading
+ * them issues a slow, serialized P-SEAMLDR query, so keep them admin-only.
+ */
 static DEVICE_ATTR_ADMIN_RO(seamldr_version);
 static DEVICE_ATTR_ADMIN_RO(num_remaining_updates);
 
@@ -90,7 +94,10 @@ static bool supports_runtime_update(void)
	const struct tdx_sys_info *sysinfo = tdx_get_sysinfo();
 
	if (!sysinfo)
-		return 0;
+		return false;
+
+	if (!tdx_supports_runtime_update(sysinfo))
+		return false;
 
	/*
	 * Calling P-SEAMLDR on CPUs with the seamret_invd_vmcs bug clears
@@ -98,14 +105,17 @@ static bool supports_runtime_update(void)
	 * present before exposing P-SEAMLDR features.
	 */
	if (boot_cpu_has_bug(X86_BUG_SEAMRET_INVD_VMCS))
-		return 0;
+		return false;
 
-	return tdx_supports_runtime_update(sysinfo);
+	return true;
 }
 
 static umode_t seamldr_group_visible(struct kobject *kobj, struct attribute *attr, int idx)
 {
-	return supports_runtime_update() ? attr->mode : 0;
+	if (!supports_runtime_update())
+		return 0;
+
+	return attr->mode;
 }
 
 static const struct attribute_group seamldr_group = {
@@ -120,20 +130,20 @@ static const struct attribute_group *tdx_host_groups[] = {
 };
 
 static enum fw_upload_err tdx_fw_prepare(struct fw_upload *fwl,
-					 const u8 *data, u32 size)
+					 const u8 *data, u32 data_len)
 {
	return FW_UPLOAD_ERR_NONE;
 }
 
 static enum fw_upload_err tdx_fw_write(struct fw_upload *fwl, const u8 *data,
-				       u32 offset, u32 size, u32 *written)
+				       u32 offset, u32 data_len, u32 *written)
 {
	int ret;
 
-	ret = seamldr_install_module(data, size);
+	ret = seamldr_install_module(data, data_len);
	switch (ret) {
	case 0:
-		*written = size;
+		*written = data_len;
		return FW_UPLOAD_ERR_NONE;
	case -EBUSY:
		return FW_UPLOAD_ERR_BUSY;

---

## [28] Dave Hansen — 2026-05-20
*Subject: Re: [PATCH v10 15/25] x86/virt/seamldr: Abort updates after a failed
 step*

On 5/20/26 06:38, Chao Gao wrote:
> +static void ack_state(struct update_ctrl *ctrl, int result)
>  {
*seamldr_params)
>  			break;
>  		}

The READ_ONCE() is cute. But it's not really effective. It's also
overly-complicated.

update_ctrl.num_failed is just a single. Nothing cares if it is 1 or 2
or 999. So why have a count?

Any reason this won't work?

	if (result)
		set_bit(0, ctrl->failed);

... and on the read side:

	test_bit(0, &update_ctrl.failed)

That's 100% non-ambiguous. It doesn't have a counter where one isn't
needed. It also can't even theoretically be messed up by the compiler.

---

## [29] Dave Hansen — 2026-05-20
*Subject: Re: [PATCH v10 24/25] coco/tdx-host: Document TDX module update
 compatibility criteria*

On 5/20/26 06:38, Chao Gao wrote:
> Note that runtime TDX module updates are an "update at your own risk"
> operation; userspace is responsible for ensuring that the update meets

I feel like this was copied right out of some TDX powerpoint
presentation. It's really hard to parse.

What does any of this mean to end users?

Who are they depending on getting this all right?

If it goes wrong, what happens?

This needs to be from the user's perspective.

---

## [30] Dave Hansen — 2026-05-20
*Subject: Re: [PATCH v10 22/25] x86/virt/tdx: Reject updates during
 compatibility-sensitive operations*

On 5/20/26 06:38, Chao Gao wrote:
>  int tdx_module_shutdown(void)
>  {

This function is pretty tidy. More or less:

 	ret = get_tdx_sys_info_handoff(&handoff);
	if (ret)
		return

	args.foo = handoff.bar;
	ret = seamcall_prerr(TDH_SYS_SHUTDOWN, &args);
	if (ret)
		return

	memset(&tdx_module_state, 0, sizeof(tdx_module_state));
	for_each_possible_cpu(cpu)
		per_cpu(tdx_lp_initialized, cpu) = false;

The logic's not bad, right? Get the handoff data, hand it off to
something, then go set some fields.

Then what does this patch do? It goes and globs a just huge blob of
TDH_SYS_SHUTDOWN errata handling and implementation details right smack
in the middle. Our tidy little function is no more.

I really with this would trigger folks' gag reflexes. It's *SO* easy to
fix. It's *so* easy to keep the code tidy and hide the dead bodies so
that the logic can still be followed.

I'm probably going to drop this for now.

---

## [31] Dave Hansen — 2026-05-20
*Subject: Re: [PATCH v10 00/25] Runtime TDX module update support*

So a little cat|sort|uniq says:

     11 Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
     17 Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>

We're on v10 here. There are 6 patches in here with no review tags:

M:      Kiryl Shutsemau <kas@kernel.org>
R:      Dave Hansen <dave.hansen@linux.intel.com>
R:      Rick Edgecombe <rick.p.edgecombe@intel.com>

Are all of those 6 new patches? Or do the reviewers still have some work
to do?

---

## [32] Xiaoyao Li — 2026-05-21
*Subject: Re: [PATCH v10 01/25] x86/virt/tdx: Clarify try_init_module_global()
 result caching*

On 5/20/2026 9:38 PM, Chao Gao wrote:
> TDX module global initialization is executed only once. The first call
> caches both the result and the "done" state, and later callers reuse the
Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>

---

## [33] Xiaoyao Li — 2026-05-21
*Subject: Re: [PATCH v10 02/25] x86/virt/tdx: Move TDX global initialization
 states to file scope*

On 5/20/2026 9:38 PM, Chao Gao wrote:
> TDX module global initialization is executed only once. The first call
> caches both the result and the "done" state, and later callers reuse the

Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>

---

## [34] Xiaoyao Li — 2026-05-21
*Subject: Re: [PATCH v10 03/25] x86/virt/tdx: Consolidate TDX global
 initialization states*

On 5/20/2026 9:38 PM, Chao Gao wrote:
> The kernel uses several global flags to guard one-time TDX initialization
> flows and prevent them from being repeated.
Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>

---

## [35] Xiaoyao Li — 2026-05-21
*Subject: Re: [PATCH v10 04/25] x86/virt/tdx: Move TDX_FEATURES0 bits to
 asm/tdx.h*

On 5/20/2026 9:38 PM, Chao Gao wrote:
> Future changes will add support for new TDX features exposed as
> TDX_FEATURES0 bits. The presence of these features will need to be checked
Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>

---

## [36] Chao Gao — 2026-05-21
*Subject: Re: [PATCH v10 22/25] x86/virt/tdx: Reject updates during
 compatibility-sensitive operations*

>This function is pretty tidy. More or less:
>

Apologies.

FWIW, we can add a tdh_sys_shutdown() helper and hide those details there.

From 987b7107d79e94d1d35be93bfc48cbeb9ce6741b Mon Sep 17 00:00:00 2001
From: Chao Gao <chao.gao@intel.com>
Date: Tue, 31 Mar 2026 05:41:30 -0700
Subject: [PATCH] x86/virt/tdx: Reject updates during compatibility-sensitive
 operations

A TDX module erratum can cause TD state corruption if a module update races
with a compatibility-sensitive operation. For example, if an update races
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
v10:
 - Don't add a "dead" TDX_FEATURE0 bit [Sashiko]
 - s/BIT/BIT_ULL
---
 arch/x86/include/asm/tdx.h            |  5 ++--
 arch/x86/virt/vmx/tdx/tdx.c           | 34 ++++++++++++++++++++++++++-
 drivers/virt/coco/tdx-host/tdx-host.c |  2 ++
 3 files changed, 38 insertions(+), 3 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index e5a9cf656c07..c848483d815f 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -29,8 +29,9 @@
 /*
  * TDX module SEAMCALL leaf function error codes
  */
-#define TDX_SUCCESS		0ULL
-#define TDX_RND_NO_ENTROPY	0x8000020300000000ULL
+#define TDX_SUCCESS			0ULL
+#define TDX_RND_NO_ENTROPY		0x8000020300000000ULL
+#define TDX_UPDATE_COMPAT_SENSITIVE	0x8000051200000000ULL
 
 /* Bit definitions of TDX_FEATURES0 metadata field */
 #define TDX_FEATURES0_TD_PRESERVING	BIT_ULL(1)
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index ce548400f7f5..ed974106ecfa 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1274,6 +1274,38 @@ static __init int tdx_enable(void)
 }
 subsys_initcall(tdx_enable);
 
+#define TDX_SYS_SHUTDOWN_AVOID_COMPAT_SENSITIVE BIT_ULL(16)
+
+static int tdh_sys_shutdown(struct tdx_module_args *args)
+{
+	u64 err;
+
+	/*
+	 * This flag tells the TDX module to reject shutdown if it races
+	 * with a "sensitive" ongoing operation. That eliminates exposure
+	 * to a TDX erratum which can corrupt TDX guest states.
+	 *
+	 * This flag is not supported by all TDX modules and may cause
+	 * the shutdown (and subsequent update procedure) to fail.
+	 */
+	args->rcx |= TDX_SYS_SHUTDOWN_AVOID_COMPAT_SENSITIVE;
+
+	err = seamcall(TDH_SYS_SHUTDOWN, args);
+	/*
+	 * The shutdown ran into a "sensitive" ongoing operation. Signal
+	 * to userspace that it can retry.
+	 */
+	if ((err & TDX_SEAMCALL_STATUS_MASK) == TDX_UPDATE_COMPAT_SENSITIVE)
+		return -EBUSY;
+
+	if (err) {
+		seamcall_err(TDH_SYS_SHUTDOWN, err, args);
+		return -EIO;
+	}
+
+	return 0;
+}
+
 int tdx_module_shutdown(void)
 {
	struct tdx_sys_info_handoff handoff = {};
@@ -1295,7 +1327,7 @@ int tdx_module_shutdown(void)
	 */
	args.rcx = handoff.module_hv;
 
-	ret = seamcall_prerr(TDH_SYS_SHUTDOWN, &args);
+	ret = tdh_sys_shutdown(&args);
	if (ret)
		return ret;
 
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index f8075efff11f..9f68a8aa5380 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -137,6 +137,8 @@ static enum fw_upload_err tdx_fw_write(struct fw_upload *fwl, const u8 *data,
	case 0:
		*written = data_len;
		return FW_UPLOAD_ERR_NONE;
+	case -EBUSY:
+		return FW_UPLOAD_ERR_BUSY;
	default:
		return FW_UPLOAD_ERR_FW_INVALID;
	}

---

## [37] Kiryl Shutsemau — 2026-05-27
*Subject: Re: [PATCH v10 01/25] x86/virt/tdx: Clarify try_init_module_global()
 result caching*

On Wed, May 20, 2026 at 06:38:04AM -0700, Chao Gao wrote:
> TDX module global initialization is executed only once. The first call
> caches both the result and the "done" state, and later callers reuse the

Have you considered using the guard for the lock. It would simplify the
flow.

---

## [38] Kiryl Shutsemau — 2026-05-27
*Subject: Re: [PATCH v10 02/25] x86/virt/tdx: Move TDX global initialization
 states to file scope*

On Wed, May 20, 2026 at 06:38:05AM -0700, Chao Gao wrote:
> TDX module global initialization is executed only once. The first call
> caches both the result and the "done" state, and later callers reuse the

Reviewed-by: Kiryl Shutsemau <kas@kernel.org>

---

## [39] Kiryl Shutsemau — 2026-05-27
*Subject: Re: [PATCH v10 03/25] x86/virt/tdx: Consolidate TDX global
 initialization states*

On Wed, May 20, 2026 at 06:38:06AM -0700, Chao Gao wrote:
> The kernel uses several global flags to guard one-time TDX initialization
> flows and prevent them from being repeated.

You still can use __read_mostly.

> Signed-off-by: Chao Gao <chao.gao@intel.com>

Reviewed-by: Kiryl Shutsemau <kas@kernel.org>

---

## [40] Kiryl Shutsemau — 2026-05-27
*Subject: Re: [PATCH v10 04/25] x86/virt/tdx: Move TDX_FEATURES0 bits to
 asm/tdx.h*

On Wed, May 20, 2026 at 06:38:07AM -0700, Chao Gao wrote:
> Future changes will add support for new TDX features exposed as
> TDX_FEATURES0 bits. The presence of these features will need to be checked

I don't have a problem with the patch, but it seems to be colliding with
DPAMT patchset that also moves the define around.

Rick, I assume this patchset going upstream first, right?

---

## [41] Kiryl Shutsemau — 2026-05-27
*Subject: Re: [PATCH v10 13/25] x86/virt/seamldr: Allocate and populate a
 module update request*

On Wed, May 20, 2026 at 06:38:16AM -0700, Chao Gao wrote:
> +static void populate_pa_list(u64 *pa_list, const u8 *vmalloc_addr, u32 vmalloc_len_pages)
> +{

I don't like that we need to assume how the image got allocated this
deep in the stack.

I can imagine situation in the future when we might want to load TDX
module to memory on boot, like initrd. And it won't be vmalloced in this
case.

Wouldn't be better to use a neutral way to get physical address that
doesn't have the assumption? Like, slow_virt_to_phys().

> +
> +		pa_list[i] = pfn << PAGE_SHIFT;

I am not sure what the value to have this as a separate function.

Having it directly in init_seamldr_params() would be easier to follow.

> +}
> +

---

## [42] Kiryl Shutsemau — 2026-05-27
*Subject: Re: [PATCH v10 21/25] x86/virt/tdx: Refresh TDX module version after
 update*

On Wed, May 20, 2026 at 06:38:24AM -0700, Chao Gao wrote:
> The kernel exposes the TDX module version through sysfs so userspace can
> check update compatibility. That information needs to remain accurate

__read_mostly?

> Do not refresh the rest of tdx_sysinfo, even if some values change across
> updates. TDX module updates are backward compatible, so existing

Warn, but pretend that everything is fine?

>  	tdx_module_state.initialized = true;
>  	return 0;

---
