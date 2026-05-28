---
title: 'Runtime TDX module update support'
date: 2026-04-27
last_reply: 2026-05-08
message_count: 49
participants: ['Chao Gao', 'Vishal Annapurve', 'Dave Hansen', 'Edgecombe, Rick P']
---

## [1] Chao Gao — 2026-04-27

Hi Reviewers,

This v8 mainly addresses issues raised by Rick and collects his Reviewed-by
tags.

The most notable changes are removing pieces that are not strictly needed
for the basic runtime update support and tightening several commit messages
to make them more direct and to the point. In particular, patches 08 and 15
were substantially rewritten, and commit messages for patches 16 and 17 were
reworked, so those would benefit from another review. The rest of the
series has only minor changes. I'm hoping this series can be merged for 7.2.

Changelog:
v7->v8:
- rebase onto v7.1-rc1 to resolve conflicts with the merged VMXON series
- flatten the P-SEAMLDR sysfs ABI by exposing seamldr_version and
  num_remaining_updates directly under /sys/devices/faux/tdx_host/,
  and clarify when they are visible
- don't preemptively handle "PAGE_SIZE != 4KB" case
- tighten the fw_upload ABI: return FW_UPLOAD_ERR_BUSY for TD-build
  contention and collapse other update failures to firmware-invalid
- consolidate tdx_blob validation in a separate function and clarify
  what is validated by the kernel vs. P-SEAMLDR
- rework the changelog of aborting updates on any failure; always use
  READ_ONCE()/WRITE_ONCE() for the shared "failed" flag access
- rewrite the changelog of handling the race between updates and TD
  builds; always pass the compat flag to TDH.SYS.SHUTDOWN
- refresh only the TDX module update_version after a successful update;
  drop the broader post-update metadata/feature checks
- explain the kernel's role and responsibilities in TDX module updates
  in the cover letter
- collect new review/ack tags
- minor typo and wording fixes
- v7: https://lore.kernel.org/kvm/20260331124214.117808-1-chao.gao@intel.com/

(For transparency, note that I used AI tools to help proofread this
cover-letter and commit messages)

This series adds support for runtime TDX module updates that preserve
running TDX guests. It is also available at:

  https://github.com/gaochaointel/linux-dev/commits/tdx-module-updates-v8/

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

Use the userspace tool below to select the appropriate TDX module and
install it via the interfaces exposed by this series:

 # git clone https://github.com/intel/tdx-module-binaries
 # cd tdx-module-binaries
 # python version_select_and_load.py --update

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


Chao Gao (20):
  coco/tdx-host: Introduce a "tdx_host" device
  coco/tdx-host: Expose TDX module version
  x86/virt/seamldr: Introduce a wrapper for P-SEAMLDR SEAMCALLs
  x86/virt/seamldr: Add a helper to retrieve P-SEAMLDR information
  coco/tdx-host: Expose P-SEAMLDR information via sysfs
  coco/tdx-host: Implement firmware upload sysfs ABI for TDX module
    updates
  x86/virt/seamldr: Allocate and populate a module update request
  x86/virt/seamldr: Introduce skeleton for TDX module updates
  x86/virt/seamldr: Shut down the current TDX module
  x86/virt/tdx: Reset software states during TDX module shutdown
  x86/virt/seamldr: Install a new TDX module
  x86/virt/seamldr: Do TDX per-CPU initialization after module
    installation
  x86/virt/tdx: Restore TDX module state
  x86/virt/tdx: Refresh TDX module version after update
  x86/virt/tdx: Reject updates during concurrent TD build
  x86/virt/seamldr: Abort updates on failure
  coco/tdx-host: Don't expose P-SEAMLDR features on CPUs with erratum
  x86/virt/tdx: Enable TDX module runtime updates
  coco/tdx-host: Document TDX module update compatibility criteria
  x86/virt/tdx: Document TDX module update

Kai Huang (1):
  x86/virt/tdx: Move low level SEAMCALL helpers out of <asm/tdx.h>

 .../ABI/testing/sysfs-devices-faux-tdx-host   |  67 ++++
 Documentation/arch/x86/tdx.rst                |  36 ++
 arch/x86/include/asm/cpufeatures.h            |   1 +
 arch/x86/include/asm/seamldr.h                |  37 ++
 arch/x86/include/asm/tdx.h                    |  69 ++--
 arch/x86/include/asm/tdx_global_metadata.h    |   4 +
 arch/x86/include/asm/vmx.h                    |   1 +
 arch/x86/kvm/vmx/tdx_errno.h                  |   2 -
 arch/x86/virt/vmx/tdx/Makefile                |   2 +-
 arch/x86/virt/vmx/tdx/seamcall_internal.h     | 109 ++++++
 arch/x86/virt/vmx/tdx/seamldr.c               | 330 ++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.c                   | 157 ++++++---
 arch/x86/virt/vmx/tdx/tdx.h                   |   9 +-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c   |  17 +-
 drivers/virt/coco/Kconfig                     |   2 +
 drivers/virt/coco/Makefile                    |   1 +
 drivers/virt/coco/tdx-host/Kconfig            |  12 +
 drivers/virt/coco/tdx-host/Makefile           |   1 +
 drivers/virt/coco/tdx-host/tdx-host.c         | 221 ++++++++++++
 19 files changed, 970 insertions(+), 108 deletions(-)
 create mode 100644 Documentation/ABI/testing/sysfs-devices-faux-tdx-host
 create mode 100644 arch/x86/include/asm/seamldr.h
 create mode 100644 arch/x86/virt/vmx/tdx/seamcall_internal.h
 create mode 100644 arch/x86/virt/vmx/tdx/seamldr.c
 create mode 100644 drivers/virt/coco/tdx-host/Kconfig
 create mode 100644 drivers/virt/coco/tdx-host/Makefile
 create mode 100644 drivers/virt/coco/tdx-host/tdx-host.c


base-commit: 254f49634ee16a731174d2ae34bc50bd5f45e731

---

## [2] Chao Gao — 2026-04-27
*Subject: [PATCH v8 01/21] x86/virt/tdx: Move low level SEAMCALL helpers out of <asm/tdx.h>*

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
Acked-by: Dave Hansen <dave.hansen@linux.intel.com>
---
v8:
 - s/SEAMCALL/SEAMCALLs [Rick]
---
 arch/x86/include/asm/tdx.h                |  47 ----------
 arch/x86/virt/vmx/tdx/seamcall_internal.h | 109 ++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.c               |  47 +---------
 3 files changed, 111 insertions(+), 92 deletions(-)
 create mode 100644 arch/x86/virt/vmx/tdx/seamcall_internal.h

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index a149740b24e8..31e01ab8b01a 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -97,54 +97,7 @@ static inline long tdx_kvm_hypercall(unsigned int nr, unsigned long p1,
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
index cb9b3210ab71..7fe4b9234c72 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -41,6 +41,8 @@
 #include <asm/processor.h>
 #include <asm/mce.h>
 #include <asm/virt.h>
+
+#include "seamcall_internal.h"
 #include "tdx.h"
 
 static u32 tdx_global_keyid __ro_after_init;
@@ -59,51 +61,6 @@ static LIST_HEAD(tdx_memlist);
 static struct tdx_sys_info tdx_sysinfo __ro_after_init;
 static bool tdx_module_initialized __ro_after_init;
 
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

## [3] Chao Gao — 2026-04-27
*Subject: [PATCH v8 02/21] coco/tdx-host: Introduce a "tdx_host" device*

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
index 7fe4b9234c72..05d241626e48 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1487,7 +1487,7 @@ const struct tdx_sys_info *tdx_get_sysinfo(void)
 
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

## [4] Chao Gao — 2026-04-27
*Subject: [PATCH v8 03/21] coco/tdx-host: Expose TDX module version*

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
index 31e01ab8b01a..2afa8dde72e0 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -38,6 +38,12 @@
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

## [5] Chao Gao — 2026-04-27
*Subject: [PATCH v8 04/21] x86/virt/seamldr: Introduce a wrapper for P-SEAMLDR SEAMCALLs*

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

## [6] Chao Gao — 2026-04-27
*Subject: [PATCH v8 05/21] x86/virt/seamldr: Add a helper to retrieve P-SEAMLDR information*

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

## [7] Chao Gao — 2026-04-27
*Subject: [PATCH v8 06/21] coco/tdx-host: Expose P-SEAMLDR information via sysfs*

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
index 2afa8dde72e0..1c5981453ff8 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -107,6 +107,12 @@ void tdx_init(void);
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

## [8] Chao Gao — 2026-04-27
*Subject: [PATCH v8 07/21] coco/tdx-host: Implement firmware upload sysfs ABI for TDX module updates*

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

v8:
 - don't preemptively handle bugs that never occurs, i.e., drop the
 WARN_ON_ONCE(offset). [Dave]
 - tighten up the comment in .poll_complete() [Dave]
 - make the error-code mapping reviewable [Rick]
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
index 7269a239bc22..650c0f097aac 100644
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
+ * @data: Pointer to the TDX module update blob.
+ * @size: Size of the TDX module update blob.
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
index 079913dcc888..d9bb1e7ef795 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -6,6 +6,7 @@
  */
 
 #include <linux/device/faux.h>
+#include <linux/firmware.h>
 #include <linux/module.h>
 #include <linux/mod_devicetable.h>
 #include <linux/sysfs.h>
@@ -84,14 +85,19 @@ static struct attribute *seamldr_attrs[] = {
 	NULL,
 };
 
-static umode_t seamldr_group_visible(struct kobject *kobj, struct attribute *attr, int idx)
+static bool can_expose_seamldr(void)
 {
 	const struct tdx_sys_info *sysinfo = tdx_get_sysinfo();
 
 	if (!sysinfo)
 		return 0;
 
-	return tdx_supports_runtime_update(sysinfo) ? attr->mode : 0;
+	return tdx_supports_runtime_update(sysinfo);
+}
+
+static umode_t seamldr_group_visible(struct kobject *kobj, struct attribute *attr, int idx)
+{
+	return can_expose_seamldr() ? attr->mode : 0;
 }
 
 static const struct attribute_group seamldr_group = {
@@ -105,6 +111,81 @@ static const struct attribute_group *tdx_host_groups[] = {
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
+	if (!can_expose_seamldr())
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
@@ -112,7 +193,7 @@ static int __init tdx_host_init(void)
 	if (!x86_match_cpu(tdx_host_ids) || !tdx_get_sysinfo())
 		return -ENODEV;
 
-	fdev = faux_device_create_with_groups(KBUILD_MODNAME, NULL, NULL, tdx_host_groups);
+	fdev = faux_device_create_with_groups(KBUILD_MODNAME, NULL, &tdx_host_ops, tdx_host_groups);
 	if (!fdev)
 		return -ENODEV;

---

## [9] Chao Gao — 2026-04-27
*Subject: [PATCH v8 08/21] x86/virt/seamldr: Allocate and populate a module update request*

P-SEAMLDR uses the SEAMLDR_PARAMS structure to describe TDX module
update requests. This structure contains physical addresses pointing to
the module binary and its signature file (or sigstruct), along with an
update scenario field.

TDX modules are distributed in the tdx_blob format defined in
blob_structure.txt from the "Intel TDX module Binaries Repository". A
tdx_blob contains a header, sigstruct, and module binary. This is also the
format supplied by the userspace to the kernel.

Parse the tdx_blob format and populate a SEAMLDR_PARAMS structure. The
header is consumed solely by the kernel to extract the sigstruct and
module, so validate it before processing to protect the kernel ABI. The
sigstruct and module are passed to and validated by P-SEAMLDR, so don't
duplicate any validation in the kernel.

Note: the sigstruct_pa field in SEAMLDR_PARAMS has been extended to
a 4-element array. The updated "SEAM Loader (SEAMLDR) Interface
Specification" will be published separately.

Signed-off-by: Chao Gao <chao.gao@intel.com>
---
v8:
 - Consolidate all tdx_blob validation into a dedicated helper instead of
 scattering checks across two functions. [Rick]
 - Clarify which validations are performed by the kernel and which are
 intentionally left to P-SEAMLDR/userspace. [Rick]
 - Drop free_seamldr_params() helper [Rick]
 - Change params->version assignment to a single sig_size > 4K expression
 [Rick]
 - Don't preemptively handle "PAGE_SIZE != 4KB" [Dave]
---
 arch/x86/virt/vmx/tdx/seamldr.c | 155 ++++++++++++++++++++++++++++++++
 1 file changed, 155 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 650c0f097aac..f70be8e2a07b 100644
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
+#define SEAMLDR_MAX_NR_SIG_PAGES	4
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
+	u64	sigstruct_pa[SEAMLDR_MAX_NR_SIG_PAGES];
+	u8	reserved[80];
+	u64	num_module_pages;
+	u64	mod_pages_pa_list[SEAMLDR_MAX_NR_MODULE_PAGES];
+} __packed;
+
+static_assert(sizeof(struct seamldr_params) == 4096);
+
 /*
  * Serialize P-SEAMLDR calls since the hardware only allows a single CPU to
  * interact with P-SEAMLDR simultaneously. Use raw version as the calls can
@@ -43,6 +71,128 @@ int seamldr_get_info(struct seamldr_info *seamldr_info)
 }
 EXPORT_SYMBOL_FOR_MODULES(seamldr_get_info, "tdx-host");
 
+/*
+ * Intel TDX module blob. Its format is defined at:
+ * https://github.com/intel/tdx-module-binaries/blob/main/blob_structure.txt
+ *
+ * Note this structure differs from the reference above: the two variable-length
+ * fields "@sigstruct" and "@module" are represented as a single "@data" field
+ * here and split programmatically using the offset_of_module value.
+ *
+ * Note @offset_of_module is relative to the start of struct tdx_blob, not
+ * @data, and @length is the total length of the blob, not the length of
+ * @data.
+ */
+struct tdx_blob {
+	u16	version;
+	u16	checksum;
+	u32	offset_of_module;
+	u8	signature[8];
+	u32	length;
+	u32	reserved0;
+	u64	reserved1[509];
+	u8	data[];
+} __packed;
+
+/* Supported versions of the tdx_blob */
+#define TDX_BLOB_VERSION_1	0x100
+
+/*
+ * Blob fields are processed by the kernel and the payloads
+ * are passed to the TDX module. Do normal user input type
+ * check for any fields that don't get passed to the TDX module.
+ */
+static const struct tdx_blob *get_and_check_blob(const u8 *data, u32 size)
+{
+	const struct tdx_blob *blob = (const void *)data;
+
+	/*
+	 * Ensure the size is valid otherwise reading any field from the
+	 * blob may overflow.
+	 */
+	if (size <= sizeof(struct tdx_blob))
+		return ERR_PTR(-EINVAL);
+
+	/*
+	 * Don't care about user passing the wrong file, but protect
+	 * kernel ABI by preventing accepting garbage.
+	 */
+	if (memcmp(blob->signature, "TDX-BLOB", 8))
+		return ERR_PTR(-EINVAL);
+
+	/*
+	 * Ensure the offset of the module is within valid bounds and
+	 * page-aligned.
+	 */
+	if (blob->offset_of_module >= size || blob->offset_of_module <= sizeof(struct tdx_blob))
+		return ERR_PTR(-EINVAL);
+	if (!IS_ALIGNED(blob->offset_of_module, PAGE_SIZE))
+		return ERR_PTR(-EINVAL);
+
+	if (blob->version != TDX_BLOB_VERSION_1)
+		return ERR_PTR(-EINVAL);
+
+	if (blob->reserved0 || memchr_inv(blob->reserved1, 0, sizeof(blob->reserved1)))
+		return ERR_PTR(-EINVAL);
+
+	return blob;
+}
+
+static struct seamldr_params *alloc_seamldr_params(const struct tdx_blob *blob, unsigned int blob_size)
+{
+	struct seamldr_params *params;
+	int module_pg_cnt, sig_pg_cnt;
+	const u8 *sig, *module;
+	int i;
+
+	params = (struct seamldr_params *)get_zeroed_page(GFP_KERNEL);
+	if (!params)
+		return ERR_PTR(-ENOMEM);
+
+	/*
+	 * Split the blob into a sigstruct and a module. Assume all
+	 * size/offsets are within bounds of blob_size due to prior checks.
+	 */
+	sig		= blob->data;
+	sig_pg_cnt	= (blob->offset_of_module - sizeof(struct tdx_blob)) >> PAGE_SHIFT;
+	module		= (const u8 *)blob + blob->offset_of_module;
+	module_pg_cnt	= (blob_size - blob->offset_of_module) >> PAGE_SHIFT;
+
+	/*
+	 * Only use version 1 when required (sigstruct > 4KB) for backward
+	 * compatibility with P-SEAMLDR that lacks version 1 support.
+	 */
+	params->version = sig_pg_cnt > 1;
+	params->scenario = SEAMLDR_SCENARIO_UPDATE;
+
+	for (i = 0; i < MIN(sig_pg_cnt, SEAMLDR_MAX_NR_SIG_PAGES); i++) {
+		params->sigstruct_pa[i] = vmalloc_to_pfn(sig) << PAGE_SHIFT;
+		sig += PAGE_SIZE;
+	}
+
+	params->num_module_pages = MIN(module_pg_cnt, SEAMLDR_MAX_NR_MODULE_PAGES);
+	for (i = 0; i < params->num_module_pages; i++) {
+		params->mod_pages_pa_list[i] = vmalloc_to_pfn(module) << PAGE_SHIFT;
+		module += PAGE_SIZE;
+	}
+
+	return params;
+}
+
+static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
+{
+	const struct tdx_blob *blob;
+
+	blob = get_and_check_blob(data, size);
+	if (IS_ERR(blob))
+		return ERR_CAST(blob);
+
+	return alloc_seamldr_params(blob, size);
+}
+
+DEFINE_FREE(free_seamldr_params, struct seamldr_params *,
+	    if (!IS_ERR_OR_NULL(_T)) free_page((unsigned long)_T))
+
 /**
  * seamldr_install_module - Install a new TDX module.
  * @data: Pointer to the TDX module update blob.
@@ -52,6 +202,11 @@ EXPORT_SYMBOL_FOR_MODULES(seamldr_get_info, "tdx-host");
  */
 int seamldr_install_module(const u8 *data, u32 size)
 {
+	struct seamldr_params *params __free(free_seamldr_params) =
+						init_seamldr_params(data, size);
+	if (IS_ERR(params))
+		return PTR_ERR(params);
+
 	/* TODO: Update TDX module here */
 	return 0;
 }

---

## [10] Chao Gao — 2026-04-27
*Subject: [PATCH v8 09/21] x86/virt/seamldr: Introduce skeleton for TDX module updates*

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

multi_cpu_stop() is a good example of performing a multi-step task in
lockstep. But it doesn't synchronize steps within the callback function
it takes. So, implement one based on its pattern to establish the
skeleton for TDX module updates. Specifically, add a global state
machine where each state represents a step in the update flow. The state
advances only after all CPUs acknowledge completing their work in the
current state. This acknowledgment mechanism is what ensures lockstep
execution.

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
v8:
 - Add a "so don't take this approach" after alternative solution
 discussion in the changelog [Rick]
 - Use imperative mood for a comment [Dave]
---
 arch/x86/virt/vmx/tdx/seamldr.c | 79 ++++++++++++++++++++++++++++++++-
 1 file changed, 77 insertions(+), 2 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index f70be8e2a07b..aa839aaeb79d 100644
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
 
@@ -190,6 +192,77 @@ static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
 	return alloc_seamldr_params(blob, size);
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
+static struct {
+	enum module_update_state state;
+	int thread_ack;
+	/*
+	 * Protect update_data. Raw spinlock as it will be acquired from
+	 * interrupt-disabled contexts.
+	 */
+	raw_spinlock_t lock;
+} update_data = {
+	.lock = __RAW_SPIN_LOCK_UNLOCKED(update_data.lock)
+};
+
+static void set_target_state(enum module_update_state state)
+{
+	/* Reset ack counter. */
+	update_data.thread_ack = num_online_cpus();
+	update_data.state = state;
+}
+
+/* Last one to ack a state moves to the next state. */
+static void ack_state(void)
+{
+	guard(raw_spinlock)(&update_data.lock);
+	update_data.thread_ack--;
+	if (!update_data.thread_ack)
+		set_target_state(update_data.state + 1);
+}
+
+/*
+ * See multi_cpu_stop() from where this multi-cpu state-machine was
+ * adopted, and the rationale for touch_nmi_watchdog().
+ */
+static int do_seamldr_install_module(void *seamldr_params)
+{
+	enum module_update_state newstate, curstate = MODULE_UPDATE_START;
+	int ret = 0;
+
+	do {
+		/* Chill out and re-read update_data. */
+		cpu_relax();
+		newstate = READ_ONCE(update_data.state);
+
+		if (newstate != curstate) {
+			curstate = newstate;
+			switch (curstate) {
+			/* TODO: add the update steps. */
+			default:
+				break;
+			}
+
+			ack_state();
+		} else {
+			touch_nmi_watchdog();
+			rcu_momentary_eqs();
+		}
+	} while (curstate != MODULE_UPDATE_DONE);
+
+	return ret;
+}
+
 DEFINE_FREE(free_seamldr_params, struct seamldr_params *,
 	    if (!IS_ERR_OR_NULL(_T)) free_page((unsigned long)_T))
 
@@ -207,7 +280,9 @@ int seamldr_install_module(const u8 *data, u32 size)
 	if (IS_ERR(params))
 		return PTR_ERR(params);
 
-	/* TODO: Update TDX module here */
-	return 0;
+	/* Ensure a stable set of online CPUs for the update process. */
+	guard(cpus_read_lock)();
+	set_target_state(MODULE_UPDATE_START + 1);
+	return stop_machine_cpuslocked(do_seamldr_install_module, params, cpu_online_mask);
 }
 EXPORT_SYMBOL_FOR_MODULES(seamldr_install_module, "tdx-host");

---

## [11] Chao Gao — 2026-04-27
*Subject: [PATCH v8 10/21] x86/virt/seamldr: Shut down the current TDX module*

The first step of TDX module updates is shutting down the current TDX
Module. This step also packs state information that needs to be
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
v8:
 - Enhance the changelog to also talk about what the patch does instead
 of just "why". [Rick]
 - For simplicity, don't cache handoff version in tdx_sysinfo
---
 arch/x86/include/asm/tdx_global_metadata.h  |  4 ++++
 arch/x86/virt/vmx/tdx/seamldr.c             | 11 ++++++++++-
 arch/x86/virt/vmx/tdx/tdx.c                 | 19 ++++++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx.h                 |  3 +++
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c | 13 +++++++++++++
 5 files changed, 48 insertions(+), 2 deletions(-)

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
index aa839aaeb79d..f995153f24b9 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -15,6 +15,7 @@
 #include <asm/seamldr.h>
 
 #include "seamcall_internal.h"
+#include "tdx.h"
 
 /* P-SEAMLDR SEAMCALL leaf function */
 #define P_SEAMLDR_INFO			0x8000000000000000
@@ -200,6 +201,7 @@ static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
  */
 enum module_update_state {
 	MODULE_UPDATE_START,
+	MODULE_UPDATE_SHUTDOWN,
 	MODULE_UPDATE_DONE,
 };
 
@@ -238,8 +240,12 @@ static void ack_state(void)
 static int do_seamldr_install_module(void *seamldr_params)
 {
 	enum module_update_state newstate, curstate = MODULE_UPDATE_START;
+	int cpu = smp_processor_id();
+	bool primary;
 	int ret = 0;
 
+	primary = cpumask_first(cpu_online_mask) == cpu;
+
 	do {
 		/* Chill out and re-read update_data. */
 		cpu_relax();
@@ -248,7 +254,10 @@ static int do_seamldr_install_module(void *seamldr_params)
 		if (newstate != curstate) {
 			curstate = newstate;
 			switch (curstate) {
-			/* TODO: add the update steps. */
+			case MODULE_UPDATE_SHUTDOWN:
+				if (primary)
+					ret = tdx_module_shutdown();
+				break;
 			default:
 				break;
 			}
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 05d241626e48..d28421ac4180 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -287,7 +287,7 @@ static __init int build_tdx_memlist(struct list_head *tmb_list)
 	return ret;
 }
 
-static __init int read_sys_metadata_field(u64 field_id, u64 *data)
+static int read_sys_metadata_field(u64 field_id, u64 *data)
 {
 	struct tdx_module_args args = {};
 	int ret;
@@ -1233,6 +1233,23 @@ static __init int tdx_enable(void)
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
index dde219c823b4..36afebf0e04b 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -46,6 +46,7 @@
 #define TDH_PHYMEM_PAGE_WBINVD		41
 #define TDH_VP_WR			43
 #define TDH_SYS_CONFIG			45
+#define TDH_SYS_SHUTDOWN		52
 
 /*
  * SEAMCALL leaf:
@@ -110,4 +111,6 @@ struct tdmr_info_list {
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

## [12] Chao Gao — 2026-04-27
*Subject: [PATCH v8 11/21] x86/virt/tdx: Reset software states during TDX module shutdown*

The TDX module requires a one-time global initialization (TDH.SYS.INIT) and
per-CPU initialization (TDH.SYS.LP.INIT) before use. These initializations
are guarded by software flags to prevent repetition.

After TDX module updates, the new TDX module requires the same global and
per-CPU initializations, but the existing software flags prevent
re-initialization.

Reset all software flags guarding the initialization flows to allow the
global and per-CPU initializations to be triggered again after updates.

As tdx_module_initialized is changed at runtime, drop its "__ro_after_init"
tag.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v8:
 - drop "__ro_after_init" from tdx_module_initialized.
---
 arch/x86/virt/vmx/tdx/tdx.c | 26 +++++++++++++++++++++-----
 1 file changed, 21 insertions(+), 5 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index d28421ac4180..ff5644f5daa4 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -55,11 +55,14 @@ static DEFINE_PER_CPU(bool, tdx_lp_initialized);
 
 static struct tdmr_info_list tdx_tdmr_list;
 
+static bool sysinit_done;
+static int sysinit_ret;
+
 /* All TDX-usable memory regions.  Protected by mem_hotplug_lock. */
 static LIST_HEAD(tdx_memlist);
 
 static struct tdx_sys_info tdx_sysinfo __ro_after_init;
-static bool tdx_module_initialized __ro_after_init;
+static bool tdx_module_initialized;
 
 /*
  * Do the module global initialization once and return its result.
@@ -69,8 +72,6 @@ static int try_init_module_global(void)
 {
 	struct tdx_module_args args = {};
 	static DEFINE_RAW_SPINLOCK(sysinit_lock);
-	static bool sysinit_done;
-	static int sysinit_ret;
 
 	raw_spin_lock(&sysinit_lock);
 
@@ -1237,7 +1238,7 @@ int tdx_module_shutdown(void)
 {
 	struct tdx_sys_info_handoff handoff = {};
 	struct tdx_module_args args = {};
-	int ret;
+	int ret, cpu;
 
 	ret = get_tdx_sys_info_handoff(&handoff);
 	WARN_ON_ONCE(ret);
@@ -1247,7 +1248,22 @@ int tdx_module_shutdown(void)
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
+	tdx_module_initialized = false;
+	sysinit_done = false;
+	sysinit_ret = 0;
+	for_each_possible_cpu(cpu)
+		per_cpu(tdx_lp_initialized, cpu) = false;
+	return 0;
 }
 
 static bool is_pamt_page(unsigned long phys)

---

## [13] Chao Gao — 2026-04-27
*Subject: [PATCH v8 12/21] x86/virt/seamldr: Install a new TDX module*

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
v8:
 - Standardize tdx_module_args initialization. For consistency, initialize
 each field on separate lines after declaration, instead of initializing
 them in the declaration.
---
 arch/x86/virt/vmx/tdx/seamldr.c | 13 +++++++++++++
 1 file changed, 13 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index f995153f24b9..317b38c4aa19 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -19,6 +19,7 @@
 
 /* P-SEAMLDR SEAMCALL leaf function */
 #define P_SEAMLDR_INFO			0x8000000000000000
+#define P_SEAMLDR_INSTALL		0x8000000000000001
 
 #define SEAMLDR_MAX_NR_MODULE_PAGES	496
 #define SEAMLDR_MAX_NR_SIG_PAGES	4
@@ -74,6 +75,14 @@ int seamldr_get_info(struct seamldr_info *seamldr_info)
 }
 EXPORT_SYMBOL_FOR_MODULES(seamldr_get_info, "tdx-host");
 
+static int seamldr_install(const struct seamldr_params *params)
+{
+	struct tdx_module_args args = {};
+
+	args.rcx = __pa(params);
+	return seamldr_call(P_SEAMLDR_INSTALL, &args);
+}
+
 /*
  * Intel TDX module blob. Its format is defined at:
  * https://github.com/intel/tdx-module-binaries/blob/main/blob_structure.txt
@@ -202,6 +211,7 @@ static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
 enum module_update_state {
 	MODULE_UPDATE_START,
 	MODULE_UPDATE_SHUTDOWN,
+	MODULE_UPDATE_CPU_INSTALL,
 	MODULE_UPDATE_DONE,
 };
 
@@ -258,6 +268,9 @@ static int do_seamldr_install_module(void *seamldr_params)
 				if (primary)
 					ret = tdx_module_shutdown();
 				break;
+			case MODULE_UPDATE_CPU_INSTALL:
+				ret = seamldr_install(seamldr_params);
+				break;
 			default:
 				break;
 			}

---

## [14] Chao Gao — 2026-04-27
*Subject: [PATCH v8 13/21] x86/virt/seamldr: Do TDX per-CPU initialization after module installation*

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
v8:
 - export tdx_cpu_enable(). it is unexported by VMXON series.
---
 arch/x86/include/asm/tdx.h      | 1 +
 arch/x86/virt/vmx/tdx/seamldr.c | 4 ++++
 arch/x86/virt/vmx/tdx/tdx.c     | 2 +-
 3 files changed, 6 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 1c5981453ff8..de822ed9ef0b 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -104,6 +104,7 @@ static inline long tdx_kvm_hypercall(unsigned int nr, unsigned long p1,
 
 #ifdef CONFIG_INTEL_TDX_HOST
 void tdx_init(void);
+int tdx_cpu_enable(void);
 const char *tdx_dump_mce_info(struct mce *m);
 const struct tdx_sys_info *tdx_get_sysinfo(void);
 
diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 317b38c4aa19..04c7a87ac7df 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -212,6 +212,7 @@ enum module_update_state {
 	MODULE_UPDATE_START,
 	MODULE_UPDATE_SHUTDOWN,
 	MODULE_UPDATE_CPU_INSTALL,
+	MODULE_UPDATE_CPU_INIT,
 	MODULE_UPDATE_DONE,
 };
 
@@ -271,6 +272,9 @@ static int do_seamldr_install_module(void *seamldr_params)
 			case MODULE_UPDATE_CPU_INSTALL:
 				ret = seamldr_install(seamldr_params);
 				break;
+			case MODULE_UPDATE_CPU_INIT:
+				ret = tdx_cpu_enable();
+				break;
 			default:
 				break;
 			}
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index ff5644f5daa4..3bbb12aefb4b 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -101,7 +101,7 @@ static int try_init_module_global(void)
  * (and TDX module global initialization SEAMCALL if not done) on local cpu to
  * make this cpu be ready to run any other SEAMCALLs.
  */
-static int tdx_cpu_enable(void)
+int tdx_cpu_enable(void)
 {
 	struct tdx_module_args args = {};
 	int ret;

---

## [15] Chao Gao — 2026-04-27
*Subject: [PATCH v8 14/21] x86/virt/tdx: Restore TDX module state*

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
v8:
 - don't add a duplicate error code as seamcal_prerr() will do that
 - don't reset tdx module status to ERORR on error
---
 arch/x86/virt/vmx/tdx/seamldr.c |  5 +++++
 arch/x86/virt/vmx/tdx/tdx.c     | 13 +++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h     |  2 ++
 3 files changed, 20 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 04c7a87ac7df..98a8d9d3ae25 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -213,6 +213,7 @@ enum module_update_state {
 	MODULE_UPDATE_SHUTDOWN,
 	MODULE_UPDATE_CPU_INSTALL,
 	MODULE_UPDATE_CPU_INIT,
+	MODULE_UPDATE_RUN_UPDATE,
 	MODULE_UPDATE_DONE,
 };
 
@@ -275,6 +276,10 @@ static int do_seamldr_install_module(void *seamldr_params)
 			case MODULE_UPDATE_CPU_INIT:
 				ret = tdx_cpu_enable();
 				break;
+			case MODULE_UPDATE_RUN_UPDATE:
+				if (primary)
+					ret = tdx_module_run_update();
+				break;
 			default:
 				break;
 			}
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 3bbb12aefb4b..9e4085a1e683 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1266,6 +1266,19 @@ int tdx_module_shutdown(void)
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
+	tdx_module_initialized = true;
+	return 0;
+}
+
 static bool is_pamt_page(unsigned long phys)
 {
 	struct tdmr_info_list *tdmr_list = &tdx_tdmr_list;
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 36afebf0e04b..5fef813002c2 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -47,6 +47,7 @@
 #define TDH_VP_WR			43
 #define TDH_SYS_CONFIG			45
 #define TDH_SYS_SHUTDOWN		52
+#define TDH_SYS_UPDATE			53
 
 /*
  * SEAMCALL leaf:
@@ -112,5 +113,6 @@ struct tdmr_info_list {
 };
 
 int tdx_module_shutdown(void);
+int tdx_module_run_update(void);
 
 #endif

---

## [16] Chao Gao — 2026-04-27
*Subject: [PATCH v8 15/21] x86/virt/tdx: Refresh TDX module version after update*

The kernel exposes the TDX module version through sysfs so userspace can
check update compatibility. That information needs to remain accurate
across runtime updates.

A runtime update may change the module's update_version, so refresh the
cached version after a successful update and emit a log message to show
the version change.

Drop __ro_after_init from tdx_sysinfo because it is now updated at runtime.

Perform the refresh outside of stop_machine() since printk() within
stop_machine() would add significant latency.

Do not refresh the rest of tdx_sysinfo. Refreshing them at runtime could
disrupt running software that relies on the previously reported values.

Note that major and minor versions are not refreshed because runtime updates
are supported only between releases with identical major and minor versions.

Signed-off-by: Chao Gao <chao.gao@intel.com>
---
Sashiko flagged a potential torn-read concern: update_version is read
via sysfs while it is refreshed post-update. But, update_version is a
naturally-aligned u16, and on x86, the compiler won't split aligned u16
accesses. So READ_ONCE/WRITE_ONCE() aren't needed for update_version.

v8:
- drop the unnecessary old/new metadata comparison
- do not refresh the handoff version, since it is no longer cached
- rename the helper to reflect its purpose instead of using the generic
  tdx_module_post_update()
---
 arch/x86/virt/vmx/tdx/seamldr.c             |  8 +++++++-
 arch/x86/virt/vmx/tdx/tdx.c                 | 21 ++++++++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx.h                 |  1 +
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |  2 +-
 4 files changed, 29 insertions(+), 3 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 98a8d9d3ae25..c81b26c4bac1 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -306,6 +306,8 @@ DEFINE_FREE(free_seamldr_params, struct seamldr_params *,
  */
 int seamldr_install_module(const u8 *data, u32 size)
 {
+	int ret;
+
 	struct seamldr_params *params __free(free_seamldr_params) =
 						init_seamldr_params(data, size);
 	if (IS_ERR(params))
@@ -314,6 +316,10 @@ int seamldr_install_module(const u8 *data, u32 size)
 	/* Ensure a stable set of online CPUs for the update process. */
 	guard(cpus_read_lock)();
 	set_target_state(MODULE_UPDATE_START + 1);
-	return stop_machine_cpuslocked(do_seamldr_install_module, params, cpu_online_mask);
+	ret = stop_machine_cpuslocked(do_seamldr_install_module, params, cpu_online_mask);
+	if (ret)
+		return ret;
+
+	return tdx_module_refresh_version();
 }
 EXPORT_SYMBOL_FOR_MODULES(seamldr_install_module, "tdx-host");
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 9e4085a1e683..a7dfa4ee8813 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -61,7 +61,7 @@ static int sysinit_ret;
 /* All TDX-usable memory regions.  Protected by mem_hotplug_lock. */
 static LIST_HEAD(tdx_memlist);
 
-static struct tdx_sys_info tdx_sysinfo __ro_after_init;
+static struct tdx_sys_info tdx_sysinfo;
 static bool tdx_module_initialized;
 
 /*
@@ -1279,6 +1279,25 @@ int tdx_module_run_update(void)
 	return 0;
 }
 
+int tdx_module_refresh_version(void)
+{
+	struct tdx_sys_info_version *old, new;
+	int ret;
+
+	/* Shouldn't fail as the update has succeeded. */
+	ret = get_tdx_sys_info_version(&new);
+	WARN_ON_ONCE(ret);
+
+	old = &tdx_sysinfo.version;
+	pr_info("version " TDX_VERSION_FMT " -> " TDX_VERSION_FMT "\n",
+		old->major_version, old->minor_version, old->update_version,
+		new.major_version, new.minor_version, new.update_version);
+
+	/* Major/minor versions should not change across updates. */
+	tdx_sysinfo.version.update_version	= new.update_version;
+	return 0;
+}
+
 static bool is_pamt_page(unsigned long phys)
 {
 	struct tdmr_info_list *tdmr_list = &tdx_tdmr_list;
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 5fef813002c2..d0e8cac9c1d5 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -114,5 +114,6 @@ struct tdmr_info_list {
 
 int tdx_module_shutdown(void);
 int tdx_module_run_update(void);
+int tdx_module_refresh_version(void);
 
 #endif
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

## [17] Chao Gao — 2026-04-27
*Subject: [PATCH v8 16/21] x86/virt/tdx: Reject updates during concurrent TD build*

tl;dr: A TDX module erratum can silently corrupt TD measurement state if a
module update races with TD build. Handle that by rejecting the update,
instead of introducing new TD-build ioctl failure paths.

Long Version:

Updates must not break unrelated operations. For TDX module updates,
this means an update must not interfere with other TDX flows.

A TDX module erratum violates that expectation: if an update races with
TD build, TD build output can be corrupted, e.g. the measurement hash,
which later causes attestation failure.

The TDX module provides two independent, opt-in mitigations for this
erratum:

1. Reject updates while TD build is in progress. This mitigation can be
   requested via TDH.SYS.SHUTDOWN.

2. Do not reject the update for this race, but instead fail later
   SEAMCALLs in the overlapping TD build flow. This mitigation can be
   requested via TDH.SYS.UPDATE.

The kernel can choose option 1, option 2, or neither.

Choose option 1 to confine failures to the update path and preserve
existing TD build and KVM ioctl behavior. Userspace already controls
update timing, and retrying a rejected update is straightforward.

Option 2 would make TD build failures explicit, but it would also
introduce new error paths in existing KVM ioctls. That complicates KVM
error handling and risks ABI instability. Sean previously rejected that
approach [1].

Choosing neither option was also considered and rejected. Leaving this
erratum unhandled would allow an update racing with TD build to silently
corrupt TD build output. That violates the requirement that TDX module
updates must not interfere with unrelated TDX flows.

Request race detection during TDH.SYS.SHUTDOWN and map a detected race
to -EBUSY, and report it to userspace as FW_UPLOAD_ERR_BUSY. This lets
userspace distinguish the race from other failures and retry the update.

Do not pre-check support for this race-detection capability. If it is
unsupported, rely on the TDX module to reject module shutdown.

This implementation is based on a reference patch by Vishal [2].

Note: moving NO_RBP_MOD definition is to centralize the bit definitions.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Acked-by: Sean Christopherson <seanjc@google.com>
Link: https://lore.kernel.org/linux-coco/aQIbM5m09G0FYTzE@google.com/ # [1]
Link: https://lore.kernel.org/linux-coco/CAGtprH_oR44Vx9Z0cfxvq5-QbyLmy_+Gn3tWm3wzHPmC1nC0eg@mail.gmail.com/ # [2]
---
v8:
 - rewrite the changelog [Rick]
 - alway pass the compat flag to the TDX module [Rick]
---
 arch/x86/include/asm/tdx.h            | 11 +++++++++--
 arch/x86/kvm/vmx/tdx_errno.h          |  2 --
 arch/x86/virt/vmx/tdx/tdx.c           | 26 +++++++++++++++++++++++---
 arch/x86/virt/vmx/tdx/tdx.h           |  3 ---
 drivers/virt/coco/tdx-host/tdx-host.c |  2 ++
 5 files changed, 34 insertions(+), 10 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index de822ed9ef0b..b063aabe2554 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -26,11 +26,18 @@
 #define TDX_SEAMCALL_GP			(TDX_SW_ERROR | X86_TRAP_GP)
 #define TDX_SEAMCALL_UD			(TDX_SW_ERROR | X86_TRAP_UD)
 
+#define TDX_SEAMCALL_STATUS_MASK		0xFFFFFFFF00000000ULL
+
 /*
  * TDX module SEAMCALL leaf function error codes
  */
-#define TDX_SUCCESS		0ULL
-#define TDX_RND_NO_ENTROPY	0x8000020300000000ULL
+#define TDX_SUCCESS			0ULL
+#define TDX_RND_NO_ENTROPY		0x8000020300000000ULL
+#define TDX_UPDATE_COMPAT_SENSITIVE	0x8000051200000000ULL
+
+/* Bit definitions of TDX_FEATURES0 metadata field */
+#define TDX_FEATURES0_NO_RBP_MOD	BIT_ULL(18)
+#define TDX_FEATURES0_UPDATE_COMPAT	BIT_ULL(47)
 
 #ifndef __ASSEMBLER__
 
diff --git a/arch/x86/kvm/vmx/tdx_errno.h b/arch/x86/kvm/vmx/tdx_errno.h
index 6ff4672c4181..215c00d76a94 100644
--- a/arch/x86/kvm/vmx/tdx_errno.h
+++ b/arch/x86/kvm/vmx/tdx_errno.h
@@ -4,8 +4,6 @@
 #ifndef __KVM_X86_TDX_ERRNO_H
 #define __KVM_X86_TDX_ERRNO_H
 
-#define TDX_SEAMCALL_STATUS_MASK		0xFFFFFFFF00000000ULL
-
 /*
  * TDX SEAMCALL Status Codes (returned in RAX)
  */
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index a7dfa4ee8813..7864ab68f4e3 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1234,10 +1234,13 @@ static __init int tdx_enable(void)
 }
 subsys_initcall(tdx_enable);
 
+#define TDX_SYS_SHUTDOWN_AVOID_COMPAT_SENSITIVE BIT(16)
+
 int tdx_module_shutdown(void)
 {
 	struct tdx_sys_info_handoff handoff = {};
 	struct tdx_module_args args = {};
+	u64 err;
 	int ret, cpu;
 
 	ret = get_tdx_sys_info_handoff(&handoff);
@@ -1248,9 +1251,26 @@ int tdx_module_shutdown(void)
 	 * module can produce and most likely supported by newer modules.
 	 */
 	args.rcx = handoff.module_hv;
-	ret = seamcall_prerr(TDH_SYS_SHUTDOWN, &args);
-	if (ret)
-		return ret;
+
+	/*
+	 * Mitigate the erratum where updates can break concurrent TD
+	 * build. Do not pre-check support for this flag. If unsupported,
+	 * rely on the TDX module to reject shutdown requests.
+	 */
+	args.rcx |= TDX_SYS_SHUTDOWN_AVOID_COMPAT_SENSITIVE;
+
+	err = seamcall(TDH_SYS_SHUTDOWN, &args);
+
+	/*
+	 * Return -EBUSY to signal that some ongoing flows are incompatible
+	 * with updates so that userspace can retry.
+	 */
+	if ((err & TDX_SEAMCALL_STATUS_MASK) == TDX_UPDATE_COMPAT_SENSITIVE)
+		return -EBUSY;
+	if (err) {
+		seamcall_err(TDH_SYS_SHUTDOWN, err, &args);
+		return -EIO;
+	}
 
 	/*
 	 * Clear global and per-CPU initialization flags so the new module
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index d0e8cac9c1d5..2c8b64eeea8e 100644
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
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index d9bb1e7ef795..14f861c03be4 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -127,6 +127,8 @@ static enum fw_upload_err tdx_fw_write(struct fw_upload *fwl, const u8 *data,
 	case 0:
 		*written = size;
 		return FW_UPLOAD_ERR_NONE;
+	case -EBUSY:
+		return FW_UPLOAD_ERR_BUSY;
 	default:
 		return FW_UPLOAD_ERR_FW_INVALID;
 	}

---

## [18] Chao Gao — 2026-04-27
*Subject: [PATCH v8 17/21] x86/virt/seamldr: Abort updates on failure*

TDX module update is a multi-step process, and each step can fail.

The current update flow continues to later steps after an error.
Continuing after failure leaves the TDX module in an unrecoverable
state.

One failure case must remain recoverable: update contention with an ongoing
TD build. The agreed kernel behavior for this case is to fail the update
with -EBUSY so userspace can retry later.

Abort the update on any failure. For the contention case, this provides
a recoverable failure mode because the failure occurs before any TDX
module state is changed. Use the same rule for all errors to avoid
special-casing -EBUSY.

Introduce a shared "failed" flag. When a CPU fails, set the flag and force
all CPUs to exit the update loop. A failing CPU does not acknowledge the
current step, so other CPUs remain at that step until they observe the
"failed" flag and exit.

Use READ_ONCE()/WRITE_ONCE() for the flag because it is used for lockless
communication between stop_machine workers. Also use WRITE_ONCE() for the
initial clear to keep accesses to the flag uniform and explicit.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
---
v8:
 - Explain why aborting updates is necessary. [Rick]
 - always use READ_ONCE()/WRITE_ONCE() for the "failed" flag.
---
 arch/x86/virt/vmx/tdx/seamldr.c | 9 +++++++--
 1 file changed, 7 insertions(+), 2 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index c81b26c4bac1..9b8f571eb03f 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -220,6 +220,7 @@ enum module_update_state {
 static struct {
 	enum module_update_state state;
 	int thread_ack;
+	bool failed;
 	/*
 	 * Protect update_data. Raw spinlock as it will be acquired from
 	 * interrupt-disabled contexts.
@@ -284,12 +285,15 @@ static int do_seamldr_install_module(void *seamldr_params)
 				break;
 			}
 
-			ack_state();
+			if (ret)
+				WRITE_ONCE(update_data.failed, true);
+			else
+				ack_state();
 		} else {
 			touch_nmi_watchdog();
 			rcu_momentary_eqs();
 		}
-	} while (curstate != MODULE_UPDATE_DONE);
+	} while (curstate != MODULE_UPDATE_DONE && !READ_ONCE(update_data.failed));
 
 	return ret;
 }
@@ -315,6 +319,7 @@ int seamldr_install_module(const u8 *data, u32 size)
 
 	/* Ensure a stable set of online CPUs for the update process. */
 	guard(cpus_read_lock)();
+	WRITE_ONCE(update_data.failed, false);
 	set_target_state(MODULE_UPDATE_START + 1);
 	ret = stop_machine_cpuslocked(do_seamldr_install_module, params, cpu_online_mask);
 	if (ret)

---

## [19] Chao Gao — 2026-04-27
*Subject: [PATCH v8 18/21] coco/tdx-host: Don't expose P-SEAMLDR features on CPUs with erratum*

Some TDX-capable CPUs have an erratum, as documented in Intel® Trust
Domain CPU Architectural Extensions (May 2021 edition) Chapter 2.3:

  SEAMRET from the P-SEAMLDR clears the current VMCS structure pointed
  to by the current-VMCS pointer. A VMM that invokes the P-SEAMLDR using
  SEAMCALL must reload the current-VMCS, if required, using the VMPTRLD
  instruction.

Clearing the current VMCS behind KVM's back will break KVM.

This erratum is not present when IA32_VMX_BASIC[60] is set. Add a CPU
bug bit for this erratum and refuse to expose P-SEAMLDR features (e.g.,
TDX module updates) on affected CPUs.

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
index 7864ab68f4e3..23c5403b3691 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -41,6 +41,7 @@
 #include <asm/processor.h>
 #include <asm/mce.h>
 #include <asm/virt.h>
+#include <asm/vmx.h>
 
 #include "seamcall_internal.h"
 #include "tdx.h"
@@ -1495,6 +1496,8 @@ static struct notifier_block tdx_memory_nb = {
 
 static void __init check_tdx_erratum(void)
 {
+	u64 basic_msr;
+
 	/*
 	 * These CPUs have an erratum.  A partial write from non-TD
 	 * software (e.g. via MOVNTI variants or UC/WC mapping) to TDX
@@ -1506,6 +1509,14 @@ static void __init check_tdx_erratum(void)
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
index 14f861c03be4..24bd660ca2cd 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -92,6 +92,14 @@ static bool can_expose_seamldr(void)
 	if (!sysinfo)
 		return 0;
 
+	/*
+	 * Calling P-SEAMLDR on CPUs with the seamret_invd_vmcs bug clears
+	 * the current VMCS, which breaks KVM. Verify the erratum is not
+	 * present before exposing P-SEAMLDR features.
+	 */
+	if (boot_cpu_has_bug(X86_BUG_SEAMRET_INVD_VMCS))
+		return false;
+
 	return tdx_supports_runtime_update(sysinfo);
 }

---

## [20] Chao Gao — 2026-04-27
*Subject: [PATCH v8 19/21] x86/virt/tdx: Enable TDX module runtime updates*

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
index b063aabe2554..b9eb1da4f36c 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -36,6 +36,7 @@
 #define TDX_UPDATE_COMPAT_SENSITIVE	0x8000051200000000ULL
 
 /* Bit definitions of TDX_FEATURES0 metadata field */
+#define TDX_FEATURES0_TD_PRESERVING	BIT_ULL(1)
 #define TDX_FEATURES0_NO_RBP_MOD	BIT_ULL(18)
 #define TDX_FEATURES0_UPDATE_COMPAT	BIT_ULL(47)
 
@@ -117,8 +118,7 @@ const struct tdx_sys_info *tdx_get_sysinfo(void);
 
 static inline bool tdx_supports_runtime_update(const struct tdx_sys_info *sysinfo)
 {
-	/* To be enabled when kernel is ready. */
-	return false;
+	return sysinfo->features.tdx_features0 & TDX_FEATURES0_TD_PRESERVING;
 }
 
 int tdx_guest_keyid_alloc(void);

---

## [21] Chao Gao — 2026-04-27
*Subject: [PATCH v8 20/21] coco/tdx-host: Document TDX module update compatibility criteria*

The TDX module update protocol facilitates compatible runtime updates.

Document the compatibility criteria and indicators of update failures.

Note that runtime TDX module updates are an "update at your own risk"
operation; userspace is responsible for ensureing that the update meets
the compatibility criteria.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Dan Williams <dan.j.williams@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
---
v8:
 - Do not map -EIO and -ENOMEM to separate fw_upload errors. There is no
   current need to distinguish them in the userspace ABI, and fw_upload
   has no matching error code for -ENOMEM.
 - some wording changes.
---
 .../ABI/testing/sysfs-devices-faux-tdx-host   | 39 +++++++++++++++++++
 1 file changed, 39 insertions(+)

diff --git a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
index 65897fe6abc0..ff585c79aa6e 100644
--- a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
+++ b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
@@ -26,3 +26,42 @@ Description:	(RO) Report the number of remaining updates. TDX maintains a
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
+		   "device-busy": The update conflicts with an in-progress TDX
+		   operation.
+
+		   "firmware-invalid": The update failed for any other reason.
+
+		A "firmware-invalid" result may be fatal. If the TDX module is
+		lost, further TDX operation is not possible, and reading
+		/sys/devices/faux/tdx_host/version returns -ENXIO.

---

## [22] Chao Gao — 2026-04-27
*Subject: [PATCH v8 21/21] x86/virt/tdx: Document TDX module update*

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
 Documentation/arch/x86/tdx.rst | 36 ++++++++++++++++++++++++++++++++++
 1 file changed, 36 insertions(+)

diff --git a/Documentation/arch/x86/tdx.rst b/Documentation/arch/x86/tdx.rst
index ff6b110291bc..de6b99d9afa7 100644
--- a/Documentation/arch/x86/tdx.rst
+++ b/Documentation/arch/x86/tdx.rst
@@ -73,6 +73,42 @@ initialize::
 
   [..] virt/tdx: TDX-Module initialization failed ...
 
+TDX module Runtime Update
+-------------------------
+
+The TDX architecture includes a persistent SEAM loader (P-SEAMLDR) that
+runs in SEAM mode separately from the TDX module. The kernel can
+communicate with P-SEAMLDR to perform runtime updates of the TDX module.
+
+During update, the TDX module becomes unresponsive to other TDX operations.
+To prevent components using TDX (such as KVM) from experiencing unexpected
+errors during updates, updates are performed in stop_machine() context.
+
+TDX module update has complex compatibility requirements; the new module
+must be compatible with the current CPU, P-SEAMLDR, and running TDX module.
+Rather than implementing complex module selection and policy enforcement
+logic in the kernel, userspace is responsible for auditing and selecting
+appropriate updates.
+
+Updates use the standard firmware upload interface. See
+Documentation/driver-api/firmware/fw_upload.rst for detailed instructions.
+
+Successful updates are logged in dmesg:
+  [..] virt/tdx: version 1.5.20 -> 1.5.24
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

## [23] Vishal Annapurve — 2026-04-27
*Subject: Re: [PATCH v8 01/21] x86/virt/tdx: Move low level SEAMCALL helpers
 out of <asm/tdx.h>*

On Mon, Apr 27, 2026 at 8:30 AM Chao Gao <chao.gao@intel.com> wrote:
>
> From: Kai Huang <kai.huang@intel.com>

Reviewed-by: Vishal Annapurve <vannapurve@google.com>

---

## [24] Dave Hansen — 2026-04-29
*Subject: Re: [PATCH v8 07/21] coco/tdx-host: Implement firmware upload sysfs
 ABI for TDX module updates*

On 4/27/26 08:28, Chao Gao wrote:
> Linux kernel supports two primary firmware update mechanisms:
>   - request_firmware()

All the stuff here is good info, but it was hard to extract the
implementation information from the background.

I think this would do:

	Select fw_upload for doing TDX module updates. The process of
	selecting among available update images is complicated and
	nuanced. Punt the selection policy out to userspace.

...
> +static int seamldr_init(struct device *dev)
> +{

can_expose_seamldr() has a not great name.

Why not just have naming that says:

	if (supports_runtime_update())
		...

Why abstract this out to what can or can't be exposed?

---

## [25] Dave Hansen — 2026-04-29
*Subject: Re: [PATCH v8 08/21] x86/virt/seamldr: Allocate and populate a module
 update request*

On 4/27/26 08:28, Chao Gao wrote:
> P-SEAMLDR uses the SEAMLDR_PARAMS structure to describe TDX module
> update requests. This structure contains physical addresses pointing to

These changelogs have all the right info, but I find them really hard to
parse. For instance, if you're going to have a 'struct seamldr_params',
then just stick with that name. Don't use the "SEAMLDR_PARAMS" name too.

Start with the data structures:

There are two important ABIs here:

'struct tdx_blob'       - the on-disk and in-memory format for a TDX
 		          module update image.
'struct seamldr_params' - The in-memory ABI passed to the TDX module
			  loader. Points to a single 'struct tdx_blob'

> diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
> index 650c0f097aac..f70be8e2a07b 100644

Gah. All this complexity for the variable-length sigstruct to save a
maximum of 4 pages. Wow.

This whole thing could have been:

struct tdx_image {
	u16	version; // This ABI is always 0x100
	u16	checksum;
	u8	signature[8];
	u32	length;
	u8	reserved[4076];
	u8	sigstruct[SIGSTRUCT_SIZE];
	u8	module[];
}

One variable array. No module offset calculations or munging.

Why do we do this to ourselves for 3 measly pages? ;)

> +/*
> + * The seamldr_params "scenario" field specifies the operation mode:

Heh, so URLs are not OK in changelogs because they go stale, but they're
fine in the code?

> + * Note this structure differs from the reference above: the two variable-length
> + * fields "@sigstruct" and "@module" are represented as a single "@data" field

This is good info. But, it's copied and pasted between the changelog and
here. I'd choose one, honestly.

> + * Note @offset_of_module is relative to the start of struct tdx_blob, not
> + * @data, and @length is the total length of the blob, not the length of

Out of line comments aren't great. Do these in the data structure if at
all possible. Or, in the code. For instance:

> +struct tdx_blob {
> +	u16	version; // This ABI is always 0x100

That's probably _better_ than the two duplicated comments that are there
now.

Also, why bother having two reserved arrays instead of:

	u8 reserved[4076];

?

> +/* Supported versions of the tdx_blob */
> +#define TDX_BLOB_VERSION_1	0x100

The comment here doesn't help much.

> +/*
> + * Blob fields are processed by the kernel and the payloads

I made it this far, but I rather despise the 'blob' terminology. It's
just bad naming. We should really just call it 'tdx_update_image' or
'tdx_image' everywhere and stop saying 'blob'. Blob is one of those
names that people throw at things when they give up on naming.

> +static const struct tdx_blob *get_and_check_blob(const u8 *data, u32 size)
> +{

Couple of things here:

First, using sizeof() on a type with a variable-length array is a big
warning sign. It needs commenting. It's especially subtle because this
will go on and parse patently invalid 'data' images that don't even have
room for sigstruct[] or module[].

This is *specifically* about the pre-data[] fields that are going to be
read below.

> +	/*
> +	 * Don't care about user passing the wrong file, but protect

Is there really no helper in the kernel anywhere that can safely do the
8-byte compare against two known-to-the-compiler 8-byte-wide fields
without hard-coding the 8?

> +	/*
> +	 * Ensure the offset of the module is within valid bounds and

Again, the sizeof(struct tdx_blob) is wonky. Why does this disallow
pointing blob->offset_of_module at reserved1[508] but not sigstruct[]?

> +	if (!IS_ALIGNED(blob->offset_of_module, PAGE_SIZE))
> +		return ERR_PTR(-EINVAL);

Wait a sec. Unless blob->offset_of_module==0, how could this check pass
and "blob->offset_of_module <= sizeof(struct tdx_blob)" fail?

> +	if (blob->version != TDX_BLOB_VERSION_1)
> +		return ERR_PTR(-EINVAL);

This should be the first check, IMNHO. If this doesn't pass then the
rest of the fields are invalid. No?

> +	if (blob->reserved0 || memchr_inv(blob->reserved1, 0, sizeof(blob->reserved1)))
> +		return ERR_PTR(-EINVAL);

There should not be two reserved, must-be-0 fields. There should be 1.
There must be 1.

Also I don't like the proposed data structure. It would make a lot more
sense to me if it were:

struct tdx_image_header {
	u16	version; // This ABI is always 0x100
	u16	checksum;
	u32	offset_of_module; // from start of the header
	u8	signature[8];
	u32	length;
	u8	reserved[4076];
}

struct p {
	u8[PAGE_SIZE];
};

struct tdx_image {
	struct tdx_image_header h;
	struct p pages[];
};

Then you can do things like check if sizeof(struct tdx_image_header) ==
PAGE_SIZE. Or whether offset_of_module points past the header.

That stuff only makes sense if you separate out the header structure
from the payloads which are the page-aligned sigstruct and module image
itself.

But exposing the double-variable-length arrays seems really wonky to me.

> +	return blob;
> +}

This does far more than "alloc" something.

> +	struct seamldr_params *params;
> +	int module_pg_cnt, sig_pg_cnt;

kzmalloc(PAGE_SIZE, GFP_KERNEL) will save you a cast.

> +	/*
> +	 * Split the blob into a sigstruct and a module. Assume all

Of course, the size of the first thing is defined by the offset of the
second thing.

This really should just be called ->end_of_sig.

> +	module		= (const u8 *)blob + blob->offset_of_module;
> +	module_pg_cnt	= (blob_size - blob->offset_of_module) >> PAGE_SHIFT;

This looks halfway sane:

	 /* adjust for size of the header: */
	sig_size    = blob->end_of_sig - PAGE_SIZE;
	module_size = module_image_size - blob->end_of_sig;

Then, page-adjust it later. One bit of magic at a time, please.

> +	/*
> +	 * Only use version 1 when required (sigstruct > 4KB) for backward

Ewwww.

But what do we do if we're on an old P-SEAMLDR but get a big sigstruct?
It'll just fail?

How many old P-SEAMLDRs are there in the wild? Do we even care about this?

> +	params->scenario = SEAMLDR_SCENARIO_UPDATE;
> +

Same for the MIN(). Do all the calculations separate from the loop.

> +		params->sigstruct_pa[i] = vmalloc_to_pfn(sig) << PAGE_SHIFT;
> +		sig += PAGE_SIZE;

Really what you want here is a helper. Have it take the module or
sigstruct pointer, a pointer to the pa_list[] and a maximum size.

Then call the helper twice.

> +	return params;
> +}

Is this really worth it?

>  /**
>   * seamldr_install_module - Install a new TDX module.

IMNHO, this patch has way too much going on. It took well over an hour
to go through it. That's problematic.

---

## [26] Dave Hansen — 2026-04-30
*Subject: Re: [PATCH v8 10/21] x86/virt/seamldr: Shut down the current TDX
 module*

On 4/27/26 08:28, Chao Gao wrote:
>  static int do_seamldr_install_module(void *seamldr_params)
>  {

Isn't cpumask_first(cpu_online_mask)==0, always? I thought CPU 0 could
never be offlined.

---

## [27] Dave Hansen — 2026-04-30
*Subject: Re: [PATCH v8 11/21] x86/virt/tdx: Reset software states during TDX
 module shutdown*

On 4/27/26 08:28, Chao Gao wrote:
> +	/*
> +	 * Clear global and per-CPU initialization flags so the new module

This speaks to needing refactoring.

If there's global TDX state, it needs to be in a global TDX state
structure, not scattered across random global variables.

Imagine the structure is:

struct tdx_module_config foo;

That's 0's at boot. You have to init the TDX module to bring it out of
0's to valid state. It actually means something if you do:

	memset(&foo, 0, sizeof(foo));

Because it takes it right back to its bss state. That ^ is also handy
because it naturally just works if new state gets added.

Guess what will happen the next time someone adds:

	int sysinit_new_fancy_thing;

Someone will forget to add it to this code. Then the module gets updated
and breaks things in fun ways.

---

## [28] Dave Hansen — 2026-04-30
*Subject: Re: [PATCH v8 12/21] x86/virt/seamldr: Install a new TDX module*

On 4/27/26 08:28, Chao Gao wrote:
> +			case MODULE_UPDATE_CPU_INSTALL:
> +				ret = seamldr_install(seamldr_params);

I really despise this naming. Could you please clarify with comments?

This reads like it is installing a seamldr, not telling a seamldr to
perform an install.

---

## [29] Dave Hansen — 2026-04-30
*Subject: Re: [PATCH v8 15/21] x86/virt/tdx: Refresh TDX module version after
 update*

On 4/27/26 08:28, Chao Gao wrote:
> The kernel exposes the TDX module version through sysfs so userspace can
> check update compatibility. That information needs to remain accurate

This needs more explanation. I think the reasoning is quite nuanced.

tdx_sysinfo is just a cache of what the TDX module is and can do. If
that changes, it means the TDX module changed. So you somehow need to
argue why it's OK to hide those changes from the tdx_sysinfo users.

Why would they be confused by tdx_sysinfo changes but not by the TDX
module *itself* changing?

> Note that major and minor versions are not refreshed because runtime updates
> are supported only between releases with identical major and minor versions.

I'd rather have this in code than a changelog comment.

If they can't change then warn if they do.

> diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
> index 98a8d9d3ae25..c81b26c4bac1 100644

This is one reason I rather dislike guard().

Does tdx_module_refresh_version() need to be guarded by 'cpus_read_lock'?

> +int tdx_module_refresh_version(void)
> +{

Two variable definitions, please. IMNHO pointers and plain variables are
different types. Even if you can, they should not be defined together.

> +	int ret;
> +

Having 'new' and 'old' be different types is really wonky. What's wrong
with:

	struct tdx_sys_info_version old = tdx_sysinfo.version;

?


> +	/* Major/minor versions should not change across updates. */
> +	tdx_sysinfo.version.update_version	= new.update_version;

					   ^ very odd tab

Also, how much of this do you *NEED*? You don't need to print the old
version. You don't really need to _print_ the new version either.

Isn't this arguably all fluff?

If the fluff went away would we even be talking about the funky pointer
versus plain type gunk?

Second, this is all open-coded and completely discrete from the code
that originally sets 'tdx_sysinfo.version'. Can it be unified?

---

## [30] Dave Hansen — 2026-04-30
*Subject: Re: [PATCH v8 16/21] x86/virt/tdx: Reject updates during concurrent
 TD build*

On 4/27/26 08:28, Chao Gao wrote:
> tl;dr: A TDX module erratum can silently corrupt TD measurement state if a
> module update races with TD build. Handle that by rejecting the update,

The downside of this needs to be discussed. Namely that module updates
can be blocked forever.

> Long Version:
...

This explanation is confusing.

Focus on what the patch *does* and its features and downsides.

*Then* broach the alternatives. But, please, clearly separate out this
patch from other opining.

> diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
> index de822ed9ef0b..b063aabe2554 100644

Refactor first. Add new features second.

>  #ifndef __ASSEMBLER__
>  

"Mitigate the erratum..." is a strange way to start this.

This would be a much better format I think:

	/*
	 * This flag will <say what it does> if <triggering event>
	 * happens. That eliminates exposure to a TDX erratum which
	 * can <explain bad things here>.
	 *
	 * This flag is not supported by all TDX modules and may cause
	 * the shutdown (and subsequent update procedure) to fail.
	 */

> +	err = seamcall(TDH_SYS_SHUTDOWN, &args);
> +

	/*
	 * The shutdown ran into a "sensitive" ongoing operation, like
	 * TD build. Signal to userspace that it can retry.
	 */

> +	if ((err & TDX_SEAMCALL_STATUS_MASK) == TDX_UPDATE_COMPAT_SENSITIVE)
> +		return -EBUSY;

Whitespace between the if()s please.

---

## [31] Dave Hansen — 2026-04-30
*Subject: Re: [PATCH v8 09/21] x86/virt/seamldr: Introduce skeleton for TDX
 module updates*

On 4/27/26 08:28, Chao Gao wrote:
> +static struct {
> +	enum module_update_state state;

multi_stop_data has an atomic_t for this.

You have an int.

Which one is right?

---

## [32] Dave Hansen — 2026-04-30
*Subject: Re: [PATCH v8 17/21] x86/virt/seamldr: Abort updates on failure*

I don't like how this is being done.

 1. Introduce this do{}while() loop
 2. Do 20 other patches
 3. Introduce a thing that can make it change
 4. Change the fundamental flow of the loop, to fix #3

I'd much rather have:

 1. Introduce this do{}while() loop
 2. Tweak fundamental flow of the loop from the last patch when I can
    remember it. Allude to future failures.
 3. Do 20 other patches
 4. Introduce a thing that uses #2


> diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
> index c81b26c4bac1..9b8f571eb03f 100644

I don't like how this is turning out either. I don't like all the nested
conditions or ack_state() that hides its mucking with update data while
its caller mucks with it directly. It's just all hacked together.

Defer all of the acking, and *failed* acking to the ack_state() helper.

Also, I'm kinda peeved that you copied and pasted the  		
touch_nmi_watchdog()/rcu_momentary_eqs() bits and none of the comments.
This is a rather subtle use of both. If you want this to be a normal
"spinning in stop machine" idiom, then create a helper and put the
comments there.

Also, this is a case where:

	do {
		cpu_relax();
		newstate = READ_ONCE(update_data.state);

		if (newstate == curstate) {
			// can cpu_relax() just go in here??
			touch_nmi_watchdog();
			rcu_momentary_eqs();
			continue;
		}
	
		switch() {
			// state changing here
		}
	} while (...);

is a much more sane setup. You're not paying the if() indentation cost
for the entire state transition block. You're also putting the "shut up
the warnings" code out of the way where you can forget about it.


> -	} while (curstate != MODULE_UPDATE_DONE);
> +	} while (curstate != MODULE_UPDATE_DONE && !READ_ONCE(update_data.failed));
I kinda wish this 'update_data.failed' set was named. This is trying to
bring 'update_data' into some initial state. Let's _call_ it that.
Honestly, I wouldn't hate if that function just also did the spinlock
init since it's so ugly do to statically.

---

## [33] Dave Hansen — 2026-04-30
*Subject: Re: [PATCH v8 18/21] coco/tdx-host: Don't expose P-SEAMLDR features
 on CPUs with erratum*

On 4/27/26 08:28, Chao Gao wrote:
> Some TDX-capable CPUs have an erratum, as documented in Intel® Trust
> Domain CPU Architectural Extensions (May 2021 edition) Chapter 2.3:

This seems totally random.

Shouldn't this be way back when can_expose_seamldr() got defined in the
first place?
> +#define X86_BUG_SEAMRET_INVD_VMCS	X86_BUG( 1*32+11) /* "seamret_invd_vmcs" SEAMRET from P-SEAMLDR clears the current VMCS */

I find myself wondering if this is worth a bug bit.

---

## [34] Edgecombe, Rick P — 2026-04-30
*Subject: Re: [PATCH v8 08/21] x86/virt/seamldr: Allocate and populate a module
 update request*

On Wed, 2026-04-29 at 17:45 -0700, Dave Hansen wrote:
> > +/*
> > + * Intel TDX module blob. Its format is defined at:

Hmm, we usually could refer to a document by name. But this is just a txt in a
github repo... Maybe just:

Intel TDX module blob is a format for distributing TDX module updates. It is
parsed by the host before internal bits are passed to the TDX module. For
details, see the latest TDX module update repository.


To me the confusing part in all of this is that there is a format that the host
has to parse and then pass different bits into the TDX module. Usually something
would just take the format it defines. So I think that is probably good context
to have around it.

---

## [35] Dave Hansen — 2026-04-30
*Subject: Re: [PATCH v8 08/21] x86/virt/seamldr: Allocate and populate a module
 update request*

On 4/30/26 14:23, Edgecombe, Rick P wrote:
> On Wed, 2026-04-29 at 17:45 -0700, Dave Hansen wrote:
>>> +/*

Just say:

/* Intel TDX module update ABI structure. aka. "TDX module blob" */

We don't need to tell folks how to use Google. Just give them the right
keywords to dump in there.

---

## [36] Edgecombe, Rick P — 2026-04-30
*Subject: Re: [PATCH v8 15/21] x86/virt/tdx: Refresh TDX module version after
 update*

On Thu, 2026-04-30 at 12:14 -0700, Dave Hansen wrote:
> > Do not refresh the rest of tdx_sysinfo. Refreshing them at runtime could
> > disrupt running software that relies on the previously reported values.

We shouldn't refresh them because they don't change, right Chao? It's not
because we are hiding things?

> 
> > Note that major and minor versions are not refreshed because runtime updates

---

## [37] Edgecombe, Rick P — 2026-04-30
*Subject: Re: [PATCH v8 12/21] x86/virt/seamldr: Install a new TDX module*

On Thu, 2026-04-30 at 12:00 -0700, Dave Hansen wrote:
> On 4/27/26 08:28, Chao Gao wrote:
> > +			case MODULE_UPDATE_CPU_INSTALL:

Yea it does read that way. We kind of have a convention around the seamcall
wrappers matching the tdx docs name. tdh_foo_bar() is pretty clear.
Unfortunately the seamldr calls are defined like SEAMLDR.INSTALL.

We don't need to make matching the wrappers name match the tdx docs be a rule. I
just considered trying to make a seamldr name schema to make it clear that these
are seamldr call names. But it is probably better to just special case this one
with a clearer name we give it, like seamldr_tdx_module_install(). Which is
slightly long, but both clear on the purpose and that it is in the family of
seamldr_() functions.

---

## [38] Dave Hansen — 2026-04-30
*Subject: Re: [PATCH v8 12/21] x86/virt/seamldr: Install a new TDX module*

On 4/30/26 14:48, Edgecombe, Rick P wrote:
> On Thu, 2026-04-30 at 12:00 -0700, Dave Hansen wrote:
>> On 4/27/26 08:28, Chao Gao wrote:

The naming convention is fine, really. It does make thing easier to look
up in the documentation.

In this case, just comment it, please. It's only a single site.

---

## [39] Chao Gao — 2026-05-06
*Subject: Re: [PATCH v8 07/21] coco/tdx-host: Implement firmware upload sysfs
 ABI for TDX module updates*

On Wed, Apr 29, 2026 at 04:17:10PM -0700, Dave Hansen wrote:
>On 4/27/26 08:28, Chao Gao wrote:
>> Linux kernel supports two primary firmware update mechanisms:

Agreed. I'll add that as a TL;DR.

>
>...

Sure, I'll use supports_runtime_update().

I originally used can_expose_seamldr() because I was focused on the
VMCS-clobbering erratum, where SEAMLDR sysfs cannot be exposed to
userspace.

---

## [40] Chao Gao — 2026-05-06
*Subject: Re: [PATCH v8 10/21] x86/virt/seamldr: Shut down the current TDX
 module*

On Thu, Apr 30, 2026 at 11:52:50AM -0700, Dave Hansen wrote:
>On 4/27/26 08:28, Chao Gao wrote:
>>  static int do_seamldr_install_module(void *seamldr_params)

Not always. On x86, CPU 0 can be offlined at runtime if the kernel is booted
with the cpu0_hotplug command-line option. See cpu_hotplug.rst.

---

## [41] Chao Gao — 2026-05-06
*Subject: Re: [PATCH v8 11/21] x86/virt/tdx: Reset software states during TDX
 module shutdown*

On Thu, Apr 30, 2026 at 11:58:12AM -0700, Dave Hansen wrote:
>On 4/27/26 08:28, Chao Gao wrote:
>> +	/*

Makes sense. I will slot in a patch like this:

From 1578bd211c732f7773475819cbf145fe9fedfcb5 Mon Sep 17 00:00:00 2001
From: Chao Gao <chao.gao@intel.com>
Date: Tue, 5 May 2026 22:46:39 -0700
Subject: [PATCH] x86/virt/tdx: Consolidate TDX global initialization state

The kernel uses several global flags to guard one-time TDX initialization
flows and prevent them from being repeated.

When the TDX module is updated, all of this state must be reset so that
the module can be initialized again. Today those flags are kept as separate
global variables, which makes the reset path awkward and easy to miss when
new state is added.

Group the flags into a single structure so they can be reset together, for
example with memset(), and so future state that needs the same handling is
easier to manage.

Drop the __ro_after_init annotation from tdx_module_initialized to make it
consistent with the other two flags.

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

## [42] Chao Gao — 2026-05-06
*Subject: Re: [PATCH v8 15/21] x86/virt/tdx: Refresh TDX module version after
 update*

On Thu, Apr 30, 2026 at 12:14:32PM -0700, Dave Hansen wrote:
>On 4/27/26 08:28, Chao Gao wrote:
>> The kernel exposes the TDX module version through sysfs so userspace can

Good point. The key assumption here is that module updates are fully backward
compatible, so running software can continue to work without seeing the new
tdx_sysinfo. I will revise the changelog. See below.

>
>> Note that major and minor versions are not refreshed because runtime updates

Maybe I can just drop the note as I don't want to add code to preemptively
catch theoretical module bugs.

I added it because Sashiko pointed out that assigning the whole version struct
outside stop_machine() could allow sysfs readers to observe a partially updated
version. As we don't need to print new module version, I will move that
assignment into stop_machine(), which addresses that issue. After that, there
is no need to mention that major/minor versions are identical across updates.

>
>> diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c

No. It can be moved out of 'cpus_read_lock'.

>
>?

I initially kept tdx module update similar to the microcode update. But yes,
printing the new version is not strictly needed. Once the unnecessary
complexity is dropped, the patch becomes quite small:

commit 90e5a66b3f54af96d5895f6707ecdeef4bc4a3ed
Author: Chao Gao <chao.gao@intel.com>
Date:   Tue Mar 31 05:41:29 2026 -0700

    x86/virt/tdx: Refresh TDX module version after update
    
    The kernel exposes the TDX module version through sysfs so userspace can
    check update compatibility. That information needs to remain accurate
    across runtime updates.
    
    A runtime update may change the module's update_version, so refresh the
    cached version after a successful update.
    
    Drop __ro_after_init from tdx_sysinfo because it is now updated at runtime.
    
    Do not refresh the rest of tdx_sysinfo even if those values change. Current
    tdx_sysinfo users (e.g., KVM) can continue to work across module updates
    without seeing the new values because module updates are required to be
    backward compatible. And those users are not written to re-validate
    tdx_sysinfo values after an update, so refreshing them could be risky.
    
    For example, a user may decide both setup and teardown behavior purely
    based on the reported capabilities. If refreshed tdx_sysinfo starts
    reporting a newly gained capability, later code may assume the
    corresponding setup exists and try to use or tear it down, even though no
    such setup was done before the update.
    
    Signed-off-by: Chao Gao <chao.gao@intel.com>
    ---
    v9:
    - don't print old and new version [Dave]
    - explain why it's OK to hide changes from the tdx_sysinfo users [Dave]
    - update versions in stop_machine context
    - don't mention major/minor versions are idential across updates. That fact is
      not relevant here.

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index deb1470185ce..ab350b705910 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -66,7 +66,7 @@ static struct tdmr_info_list tdx_tdmr_list;
 /* All TDX-usable memory regions.  Protected by mem_hotplug_lock. */
 static LIST_HEAD(tdx_memlist);
 
-static struct tdx_sys_info tdx_sysinfo __ro_after_init;
+static struct tdx_sys_info tdx_sysinfo;
 
 /*
  * Do the module global initialization once and return its result.
@@ -1305,6 +1305,10 @@ int tdx_module_run_update(void)
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

## [43] Chao Gao — 2026-05-06
*Subject: Re: [PATCH v8 09/21] x86/virt/seamldr: Introduce skeleton for TDX
 module updates*

On Thu, Apr 30, 2026 at 01:03:53PM -0700, Dave Hansen wrote:
>On 4/27/26 08:28, Chao Gao wrote:
>> +static struct {

You pointed out that using atomic_t and memory barriers for synchronization was
overly complicated. So, I switched to use a spinlock, and thread_ack can now be
a plain int.

See https://lore.kernel.org/kvm/31936a20-929f-489a-9dc6-0f8fcb9307f1@intel.com/

---

## [44] Dave Hansen — 2026-05-06
*Subject: Re: [PATCH v8 09/21] x86/virt/seamldr: Introduce skeleton for TDX
 module updates*

On 5/6/26 06:00, Chao Gao wrote:
> On Thu, Apr 30, 2026 at 01:03:53PM -0700, Dave Hansen wrote:
>> On 4/27/26 08:28, Chao Gao wrote:

Good point.

Could you make this a bit more obvious, please?

I honestly don't like guard(). Maybe I'm old-fashioned, but I really,
really like critical sections to be, well, explicit *sections* of code.

Second, you have two functions defined next to each other with similar
names:

static void ack_state(void)

static void set_target_state(enum module_update_state state)

Both of which manipulate the same data. One takes the lock. One doesn't.
That could be fixed with comments.

---

## [45] Dave Hansen — 2026-05-06
*Subject: Re: [PATCH v8 10/21] x86/virt/seamldr: Shut down the current TDX
 module*

On 5/5/26 19:56, Chao Gao wrote:
> On Thu, Apr 30, 2026 at 11:52:50AM -0700, Dave Hansen wrote:
>> On 4/27/26 08:28, Chao Gao wrote:

See e59e74dc48a309cb848ffc3d76a0d61aa6803c05.

Yes, the docs are stale.

---

## [46] Chao Gao — 2026-05-07
*Subject: Re: [PATCH v8 08/21] x86/virt/seamldr: Allocate and populate a
 module update request*

>> header is consumed solely by the kernel to extract the sigstruct and
>> module, so validate it before processing to protect the kernel ABI. The

Thanks for the thorough review.

Your comments all make sense to me. I just want to confirm two points
below.


>> +	/*
>> +	 * Don't care about user passing the wrong file, but protect

I couldn't find a helper that automatically derives the comparison
length from the operands.  'strcmp()' is not suitable here because
'blob->signature' is not NUL-terminated.

Do you mean just avoiding the hard-coded 8, e.g.

	if (memcmp(blob->signature, "TDX-BLOB", sizeof(blob->signature)))
		return ERR_PTR(-EINVAL);

or define the 'u8 signature[8]' as a u64 and compare it with a constant, like

/* Little-endian encoding of "TDX-BLOB" string */
#define TDX_IMAGE_SIGNATURE	0x424f4c422d584454ULL

	if (blob->signature != TDX_IMAGE_SIGNATURE)
		return ERR_PTR(-EINVAL);

>> +	struct seamldr_params *params;
>> +	int module_pg_cnt, sig_pg_cnt;

I noticed that 'kzalloc_obj()' can be used here, which avoids spelling out
the size and GFP flags explicitly.  So I ended up with:

    params = kzalloc_obj(*params);

If you would prefer 'kzalloc(PAGE_SIZE, GFP_KERNEL)', I can switch to that.

---

## [47] Chao Gao — 2026-05-08
*Subject: Re: [PATCH v8 17/21] x86/virt/seamldr: Abort updates on failure*

On Thu, Apr 30, 2026 at 01:06:38PM -0700, Dave Hansen wrote:
>I don't like how this is being done.
>

OK, that makes sense. I'll reorder the series so this patch comes immediately
after the skeleton patch.

>
>

OK. I'll fold both normal and failed acking into ack_state().


>
>Also, I'm kinda peeved that you copied and pasted the  		

Those two calls were added in stop_machine() to improve debuggability.

The issue they address is that a stop_machine() callback can hang on one
CPU. Without touch_nmi_watchdog() and rcu_momentary_eqs(), the other CPUs
that are merely spinning in the wait loop can also report hard lockup and
RCU stall warnings, which obscures the actual stuck CPU.

I agree that this behavior makes sense in stop_machine() as common
infrastructure. But this update path does not take an arbitrary callback
function, so that that debuggability is not strictly necessary here. I'll
drop those calls from this path unless there is an objection.

>
>Also, this is a case where:

Agreed. Will do.

---

## [48] Chao Gao — 2026-05-08
*Subject: Re: [PATCH v8 18/21] coco/tdx-host: Don't expose P-SEAMLDR features
 on CPUs with erratum*

On Thu, Apr 30, 2026 at 01:09:30PM -0700, Dave Hansen wrote:
>On 4/27/26 08:28, Chao Gao wrote:
>> Some TDX-capable CPUs have an erratum, as documented in Intel� Trust

I split this out because the erratum needs a longer changelog and some
discussion of alternatives. I also wanted the initial can_expose_seamldr()
patch to focus on introducing the gating mechanism, without bundling in
every detailed check from the start. The update do-while loop and the uABI
stuff are the core of this series, while this erratum check is not, so I
placed this patch later.

That said, I am perfectly fine with moving this patch to immediately follow
the patch that introduces can_expose_seamldr().

>> +#define X86_BUG_SEAMRET_INVD_VMCS	X86_BUG( 1*32+11) /* "seamret_invd_vmcs" SEAMRET from P-SEAMLDR clears the current VMCS */
>

The bug bit was added in v5:

https://lore.kernel.org/all/d664ac9445b1c7cc864dead103086341c374b094.camel@intel.com/#t

Kai suggested this approach for two reasons:

1. It is consistent with how X86_BUG_TDX_PW_MCE is handled.
2. It gives userspace a clue as to why the module update feature is
   unavailable.

That reasoning made sense to me, and I do not see a strong reason not to
use the "bug bit" infrastructure. If there is no objection to it, I will
add a short explanation to the changelog.

---

## [49] Dave Hansen — 2026-05-08
*Subject: Re: [PATCH v8 08/21] x86/virt/seamldr: Allocate and populate a module
 update request*

On 5/7/26 06:19, Chao Gao wrote:
...
>>> +	/*
>>> +	 * Don't care about user passing the wrong file, but protect

Either one of those is fine with me. I'd probably do the sizeof()
variant, but no strong preference.

>>> +	struct seamldr_params *params;
>>> +	int module_pg_cnt, sig_pg_cnt;

That's fine too.

---
