---
title: 'Runtime TDX module update support'
date: 2026-03-31
last_reply: 2026-04-15
message_count: 85
participants: ['Chao Gao', 'Dave Hansen', 'Sean Christopherson', 'Edgecombe, Rick P', 'Dan Williams']
---

## [1] Chao Gao — 2026-03-31

Hi Reviewers,

This v7 is mainly to fix a few valid issues identified by Sashiko
(https://sashiko.dev/#/patchset/20260326084448.29947-1-chao.gao%40intel.com)

Patch 06/12/17 need a second review. All other patches have a few RBs.

I believe this series is quite mature and self-contained — it has no impact
on the rest of the kernel unless an update is triggered through the dedicated
sysfs ABIs. I'm hoping it can be merged for 7.1.

Changelog:
v6->v7:
 - rebase onto the latest tip/x86/tdx branch
 - move TDX_VERSION_FMT to <asm/tdx.h> and use it in all version prints
 - only refresh update_version post-update since major/minor don't change
   across updates
 - use TDX_MODULE_ERROR instead of TDX_MODULE_UNINITIALIZED after shutdown
   to prevent re-initialization
 - add error logging for TDH_SYS_SHUTDOWN failure
 - hold cpus_read_lock() before updates to prevent CPU hotplug race
 - validate blob signature, reserved fields, and 4KB alignment
 - fix documentation typos
 - other minor comment and changelog improvements
 - collect review tags from Kiryl/Xiaoyao
 - v6: https://lore.kernel.org/kvm/20260326084448.29947-1-chao.gao@intel.com/

(For transparency, note that I used AI tools to help proofread this
cover-letter and commit messages)

This series adds support for runtime TDX module updates that preserve
running TDX guests. It is also available at:

  https://github.com/gaochaointel/linux-dev/commits/tdx-module-updates-v7/

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

Implement a TDX module update facility via the fw_upload mechanism. Given
that there is variability in which module update to load based on features,
fix levels, and potentially reloading the same version for error recovery
scenarios, the explicit userspace chosen payload flexibility of fw_upload
is attractive.

This design allows the kernel to accept a bitstream instead of loading a
named file from the filesystem, as the module selection and policy
enforcement for TDX modules are quite complex (see patch "coco/tdx-host:
Implement firmware upload sysfs ABI for TDX module updates"). By doing
so, much of this complexity is shifted out of the kernel. The kernel
needs to expose information, such as the TDX module version, to
userspace.  Userspace must understand the TDX module versioning scheme
and update policy to select the appropriate TDX module (see "TDX module
Versioning" below).

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

First, load kvm-intel.ko and tdx-host.ko if they haven't been loaded:

 # modprobe -r kvm_intel
 # modprobe kvm_intel tdx=1
 # modprobe tdx-host

Then, use the userspace tool below to select the appropriate TDX module and
install it via the interfaces exposed by this series:

 # git clone https://github.com/intel/tdx-module-binaries
 # cd tdx-module-binaries
 # python version_select_and_load.py --update

this version changes the firmware directory name from seamldr_upload to
tdx_module, so, below change should be applied to version_select_and_load.py:

diff --git a/version_select_and_load.py b/version_select_and_load.py
index 2193bd8..6a3b604 100644
--- a/version_select_and_load.py
+++ b/version_select_and_load.py
@@ -38,7 +38,7 @@ except ImportError:
     print("Error: cpuid module is not installed. Please install it using 'pip install cpuid'")
     sys.exit(1)

-FIRMWARE_PATH = "/sys/class/firmware/seamldr_upload"
+FIRMWARE_PATH = "/sys/class/firmware/tdx_module"
 MODULE_PATH = "/sys/devices/faux/tdx_host"
 SEAMLDR_PATH = "/sys/devices/faux/tdx_host/seamldr"
 allow_debug = False


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


Chao Gao (21):
  coco/tdx-host: Introduce a "tdx_host" device
  coco/tdx-host: Expose TDX module version
  x86/virt/seamldr: Introduce a wrapper for P-SEAMLDR SEAMCALLs
  x86/virt/seamldr: Add a helper to retrieve P-SEAMLDR information
  coco/tdx-host: Expose P-SEAMLDR information via sysfs
  coco/tdx-host: Implement firmware upload sysfs ABI for TDX module
    updates
  x86/virt/seamldr: Allocate and populate a module update request
  x86/virt/seamldr: Introduce skeleton for TDX module updates
  x86/virt/seamldr: Abort updates if errors occurred midway
  x86/virt/seamldr: Shut down the current TDX module
  x86/virt/tdx: Reset software states during TDX module shutdown
  x86/virt/seamldr: Install a new TDX module
  x86/virt/seamldr: Do TDX per-CPU initialization after updates
  x86/virt/tdx: Restore TDX module state
  x86/virt/tdx: Update tdx_sysinfo and check features post-update
  x86/virt/tdx: Avoid updates during update-sensitive operations
  coco/tdx-host: Don't expose P-SEAMLDR features on CPUs with erratum
  x86/virt/tdx: Enable TDX module runtime updates
  coco/tdx-host: Document TDX module update compatibility criteria
  x86/virt/tdx: Document TDX module update
  x86/virt/seamldr: Log TDX module update failures

Kai Huang (1):
  x86/virt/tdx: Move low level SEAMCALL helpers out of <asm/tdx.h>

 .../ABI/testing/sysfs-devices-faux-tdx-host   |  75 ++++
 Documentation/arch/x86/tdx.rst                |  36 ++
 arch/x86/include/asm/cpufeatures.h            |   1 +
 arch/x86/include/asm/seamldr.h                |  37 ++
 arch/x86/include/asm/tdx.h                    |  70 +---
 arch/x86/include/asm/tdx_global_metadata.h    |   5 +
 arch/x86/include/asm/vmx.h                    |   1 +
 arch/x86/kvm/vmx/tdx_errno.h                  |   2 -
 arch/x86/virt/vmx/tdx/Makefile                |   2 +-
 arch/x86/virt/vmx/tdx/seamcall_internal.h     | 109 ++++++
 arch/x86/virt/vmx/tdx/seamldr.c               | 359 ++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.c                   | 173 ++++++---
 arch/x86/virt/vmx/tdx/tdx.h                   |  11 +-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c   |  22 +-
 drivers/virt/coco/Kconfig                     |   2 +
 drivers/virt/coco/Makefile                    |   1 +
 drivers/virt/coco/tdx-host/Kconfig            |  12 +
 drivers/virt/coco/tdx-host/Makefile           |   1 +
 drivers/virt/coco/tdx-host/tdx-host.c         | 244 ++++++++++++
 19 files changed, 1059 insertions(+), 104 deletions(-)
 create mode 100644 Documentation/ABI/testing/sysfs-devices-faux-tdx-host
 create mode 100644 arch/x86/include/asm/seamldr.h
 create mode 100644 arch/x86/virt/vmx/tdx/seamcall_internal.h
 create mode 100644 arch/x86/virt/vmx/tdx/seamldr.c
 create mode 100644 drivers/virt/coco/tdx-host/Kconfig
 create mode 100644 drivers/virt/coco/tdx-host/Makefile
 create mode 100644 drivers/virt/coco/tdx-host/tdx-host.c


base-commit: 87d034b5b9f36c66bf02af587fb6935af88ffbf1

---

## [2] Chao Gao — 2026-03-31
*Subject: [PATCH v7 01/22] x86/virt/tdx: Move low level SEAMCALL helpers out of <asm/tdx.h>*

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
v5:
 - s/seamcall.h/seamcall_internal.h [Binbin]
 - Fix an unintentional change to sc_retry() during code movement.
v4:
 - Collect reviews
 - add "internal" to the new header file [Dave]
 - document the scope of the new header file [Dave]
 - correct the copyright notice [Dave]
v2:
 - new
---
 arch/x86/include/asm/tdx.h                |  47 ----------
 arch/x86/virt/vmx/tdx/seamcall_internal.h | 109 ++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.c               |  47 +---------
 3 files changed, 111 insertions(+), 92 deletions(-)
 create mode 100644 arch/x86/virt/vmx/tdx/seamcall_internal.h

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 6b338d7f01b7..cb2219302dfc 100644
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
 int tdx_cpu_enable(void);
 int tdx_enable(void);
 const char *tdx_dump_mce_info(struct mce *m);
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
index 8b8e165a2001..06d9709ade85 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -39,6 +39,8 @@
 #include <asm/cpu_device_id.h>
 #include <asm/processor.h>
 #include <asm/mce.h>
+
+#include "seamcall_internal.h"
 #include "tdx.h"
 
 static u32 tdx_global_keyid __ro_after_init;
@@ -59,51 +61,6 @@ static LIST_HEAD(tdx_memlist);
 
 static struct tdx_sys_info tdx_sysinfo;
 
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
  * It can be done on any cpu.  It's always called with interrupts

---

## [3] Chao Gao — 2026-03-31
*Subject: [PATCH v7 02/22] coco/tdx-host: Introduce a "tdx_host" device*

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
v3:
 - add Jonathan's reviewed-by
 - add tdx_get_sysinfo() in module_init() to ensure the TDX module is up
   and running.
 - note in the changelog that both AMD and ARM have devices for coco
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
index 06d9709ade85..172f6d4133b5 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1435,7 +1435,7 @@ const struct tdx_sys_info *tdx_get_sysinfo(void)
 
 	return p;
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

## [4] Chao Gao — 2026-03-31
*Subject: [PATCH v7 03/22] coco/tdx-host: Expose TDX module version*

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
v7:
 - use TDX_VERSION_FMT and convert an existing case

v4:
 - collect reviews
 - Explain other version exposure implementations and why tdx's approach differs
   from them
v3:
 - Justify the sysfs ABI choice and expand background on other CoCo
   implementations.
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
index cb2219302dfc..85efc17e7660 100644
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
index 4c9917a9c2c3..34c050d74b56 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -106,7 +106,7 @@ static int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 
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

## [5] Chao Gao — 2026-03-31
*Subject: [PATCH v7 04/22] x86/virt/seamldr: Introduce a wrapper for P-SEAMLDR SEAMCALLs*

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
Link: https://cdrdv2.intel.com/v1/dl/getContent/733582 # [1]
---
v6:
 - Don't refer to Intel® Trust Domain CPU Architectural Extensions
   [Xiaoyao]
 - clarify the usage of seamcall_prerr() [Xiaoyao]
 - Improve the explanation for raw_spinlock [Kiryl]

v5:
 - Don't save/restore irq flags as P-SEAMLDR calls are made only in process
   context
 - clarify why raw_spinlock is used [Dave]
v4:
 - Give more background about P-SEAMLDR in changelog [Dave]
 - Don't handle P-SEAMLDR's "no_entropy" error [Dave]
 - Assume current VMCS is preserved across P-SEAMLDR calls [Dave]
 - I'm not adding Reviewed-by tags as the code has changed significantly.
v2:
 - don't create a new, inferior framework to save/restore VMCS
 - use human-friendly language, just "current VMCS" rather than
   SDM term "current-VMCS pointer"
 - don't mix guard() with goto
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

## [6] Chao Gao — 2026-03-31
*Subject: [PATCH v7 05/22] x86/virt/seamldr: Add a helper to retrieve P-SEAMLDR information*

P-SEAMLDR returns its information such as version number, in response to
the SEAMLDR.INFO SEAMCALL.

This information is useful for userspace. For example, the admin can decide
which TDX module versions are compatible with the P-SEAMLDR according to
the P-SEAMLDR version.

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
---
v6:
 - Clarify that this patch introduces a helper for retrieving info, not
   the retrieval itself [Xiaoyao]
v5:
 - add a comment for slow_virt_to_phys() [Kai]
v4:
 - put seamldr_info on stack [Dave]
 - improve changelogs to explain SEAMLDR.INFO and SEAMLDR.SEAMINFO [Dave]
 - add P-SEAMLDR spec information in the changelog [Dave]
 - add proper comments above ABI structure definition [Dave]
 - add unused ABI structure fields rather than marking them as reserved
   to better align with the specc [Dave] (I omitted "not used by kernel"
   tags since there are 5-6 such fields and maintaining these tags would
   be tedious.)
---
 arch/x86/include/asm/seamldr.h  | 36 +++++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/seamldr.c | 19 ++++++++++++++++-
 2 files changed, 54 insertions(+), 1 deletion(-)
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
index 65616dd2f4d2..8410df3a0bf4 100644
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
@@ -18,8 +23,20 @@
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
+	/*
+	 * Use slow_virt_to_phys() since @seamldr_info may be allocated on
+	 * the stack.
+	 */
+	struct tdx_module_args args = { .rcx = slow_virt_to_phys(seamldr_info) };
+
+	return seamldr_call(P_SEAMLDR_INFO, &args);
+}
+EXPORT_SYMBOL_FOR_MODULES(seamldr_get_info, "tdx-host");

---

## [7] Chao Gao — 2026-03-31
*Subject: [PATCH v7 06/22] coco/tdx-host: Expose P-SEAMLDR information via sysfs*

TDX module updates require userspace to select the appropriate module
to load. Expose necessary information to facilitate this decision. Two
values are needed:

- P-SEAMLDR version: for compatibility checks between TDX module and
		     P-SEAMLDR
- num_remaining_updates: indicates how many updates can be performed

Expose them as tdx-host device attributes. Make seamldr attributes
visible only when the update feature is supported, as that's their sole
purpose. Unconditional exposure is also problematic because reading them
triggers P-SEAMLDR calls that break KVM on CPUs with a specific erratum
(to be enumerated and handled in a later patch).

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
---
v7:
 - add a space after TDX_VERSION_FMT
v6:
 - use TDX_VERSION_FMT macro [Dave]
 - drop revision/chapter numbers [Kiryl/Xiaoyao]
 - use is_visible to control seamldr attribute visibility
   rather than do that manually during device probe. Due
   to this change, drop all RBs.
v5:
 - fix typos [Binbin]
 - register seamldr_group during device probe
v4:
 - Make seamldr attribute permission "0400" [Dave]
 - Don't include implementation details in OS ABI docs [Dave]
 - Tag tdx_host_group as static [Kai]

v3:
 - use #ifdef rather than .is_visible() to control P-SEAMLDR sysfs
   visibility [Yilun]
---
 .../ABI/testing/sysfs-devices-faux-tdx-host   | 22 ++++++
 arch/x86/include/asm/tdx.h                    |  6 ++
 drivers/virt/coco/tdx-host/tdx-host.c         | 76 ++++++++++++++++++-
 3 files changed, 103 insertions(+), 1 deletion(-)

diff --git a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
index 2cf682b65acf..f7221f2e5fec 100644
--- a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
+++ b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
@@ -4,3 +4,25 @@ Description:	(RO) Report the version of the loaded TDX module. The TDX module
 		version is formatted as x.y.z, where "x" is the major version,
 		"y" is the minor version and "z" is the update version. Versions
 		are used for bug reporting, TDX module updates etc.
+
+What:		/sys/devices/faux/tdx_host/seamldr/version
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) Report the version of the loaded SEAM loader. The SEAM
+		loader version is formatted as x.y.z, where "x" is the major
+		version, "y" is the minor version and "z" is the update version.
+		Versions are used for bug reporting and compatibility checks.
+
+What:		/sys/devices/faux/tdx_host/seamldr/num_remaining_updates
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
index 85efc17e7660..79733fdb35c6 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -109,6 +109,12 @@ int tdx_enable(void);
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
index ef117a836b3a..5a672126f372 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -11,6 +11,7 @@
 #include <linux/sysfs.h>
 
 #include <asm/cpu_device_id.h>
+#include <asm/seamldr.h>
 #include <asm/tdx.h>
 
 static const struct x86_cpu_id tdx_host_ids[] = {
@@ -40,7 +41,80 @@ static struct attribute *tdx_host_attrs[] = {
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
+ * Open-code DEVICE_ATTR_ADMIN_RO to specify a different 'show' function
+ * for P-SEAMLDR version as version_show() is used for TDX module version.
+ *
+ * Admin-only readable as reading these attributes calls into P-SEAMLDR,
+ * which may have potential performance and system impact.
+ */
+static struct device_attribute dev_attr_seamldr_version =
+	__ATTR(version, 0400, seamldr_version_show, NULL);
+static DEVICE_ATTR_ADMIN_RO(num_remaining_updates);
+
+static struct attribute *seamldr_attrs[] = {
+	&dev_attr_seamldr_version.attr,
+	&dev_attr_num_remaining_updates.attr,
+	NULL,
+};
+
+static bool seamldr_group_visible(struct kobject *kobj)
+{
+	const struct tdx_sys_info *sysinfo = tdx_get_sysinfo();
+
+	if (!sysinfo)
+		return false;
+
+	return tdx_supports_runtime_update(sysinfo);
+}
+
+DEFINE_SIMPLE_SYSFS_GROUP_VISIBLE(seamldr);
+
+static const struct attribute_group seamldr_group = {
+	.name = "seamldr",
+	.attrs = seamldr_attrs,
+	.is_visible = SYSFS_GROUP_VISIBLE(seamldr),
+};
+
+static const struct attribute_group *tdx_host_groups[] = {
+	&tdx_host_group,
+	&seamldr_group,
+	NULL,
+};
 
 static struct faux_device *fdev;

---

## [8] Chao Gao — 2026-03-31
*Subject: [PATCH v7 07/22] coco/tdx-host: Implement firmware upload sysfs ABI for TDX module updates*

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

Implementation notes:
1. P-SEAMLDR processes the entire update at once rather than
   chunk-by-chunk, so .write() is called only once per update; so the
   offset should be always 0.
2. An update completes synchronously within .write(), meaning
   .poll_complete() is only called after the update succeeds and so always
   returns success

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
---
v6:
 - Remove unused "-ENOSPC" error mapping—this series never returns it

v5:
 - remove a tail comment [Yan]
 - remove is_vmalloc_addr() check [Dave]
 - use devm_add_action_or_reset() for deinit [Yilun]
 - remove global tdx_fwl [Yilun]
 - clarify request_firmware() doesn't take filename from userspace
   [Rick]

v4:
 - make tdx_fwl static [Kai]
 - don't support update canceling [Yilun]
 - explain why seamldr_init() doesn't return an error [Kai]
 - bail out if TDX module updates are not supported [Kai]
 - name the firmware "tdx_module" instead of "seamldr_upload" [Cedric]

v3:
 - clear "cancel_request" in the "prepare" phase [Binbin]
 - Don't fail the whole tdx-host device if seamldr_init() met an error
 [Yilun]
 - Add kdoc for seamldr_install_module() and verify that the input
   buffer is vmalloc'd. [Yilun]
---
 arch/x86/include/asm/seamldr.h        |  1 +
 arch/x86/virt/vmx/tdx/seamldr.c       | 15 ++++
 drivers/virt/coco/tdx-host/Kconfig    |  2 +
 drivers/virt/coco/tdx-host/tdx-host.c | 99 ++++++++++++++++++++++++++-
 4 files changed, 115 insertions(+), 2 deletions(-)

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
index 8410df3a0bf4..e93a5d90a3ee 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -6,6 +6,7 @@
  */
 #define pr_fmt(fmt)	"seamldr: " fmt
 
+#include <linux/mm.h>
 #include <linux/spinlock.h>
 
 #include <asm/seamldr.h>
@@ -40,3 +41,17 @@ int seamldr_get_info(struct seamldr_info *seamldr_info)
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
index 5a672126f372..746a5eef004d 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -6,6 +6,7 @@
  */
 
 #include <linux/device/faux.h>
+#include <linux/firmware.h>
 #include <linux/module.h>
 #include <linux/mod_devicetable.h>
 #include <linux/sysfs.h>
@@ -92,7 +93,7 @@ static struct attribute *seamldr_attrs[] = {
 	NULL,
 };
 
-static bool seamldr_group_visible(struct kobject *kobj)
+static bool can_expose_seamldr(void)
 {
 	const struct tdx_sys_info *sysinfo = tdx_get_sysinfo();
 
@@ -102,6 +103,11 @@ static bool seamldr_group_visible(struct kobject *kobj)
 	return tdx_supports_runtime_update(sysinfo);
 }
 
+static bool seamldr_group_visible(struct kobject *kobj)
+{
+	return can_expose_seamldr();
+}
+
 DEFINE_SIMPLE_SYSFS_GROUP_VISIBLE(seamldr);
 
 static const struct attribute_group seamldr_group = {
@@ -116,6 +122,95 @@ static const struct attribute_group *tdx_host_groups[] = {
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
+	/*
+	 * tdx_fw_write() always processes all data on the first call with
+	 * offset == 0. Since it never returns partial success (it either
+	 * succeeds completely or fails), there is no subsequent call with
+	 * non-zero offsets.
+	 */
+	WARN_ON_ONCE(offset);
+	ret = seamldr_install_module(data, size);
+	switch (ret) {
+	case 0:
+		*written = size;
+		return FW_UPLOAD_ERR_NONE;
+	case -EBUSY:
+		return FW_UPLOAD_ERR_BUSY;
+	case -EIO:
+		return FW_UPLOAD_ERR_HW_ERROR;
+	case -ENOMEM:
+		return FW_UPLOAD_ERR_RW_ERROR;
+	default:
+		return FW_UPLOAD_ERR_FW_INVALID;
+	}
+}
+
+static enum fw_upload_err tdx_fw_poll_complete(struct fw_upload *fwl)
+{
+	/*
+	 * TDX module updates are completed in the previous phase
+	 * (tdx_fw_write()). If any error occurred, the previous phase
+	 * would return an error code to abort the update process. In
+	 * other words, reaching this point means the update succeeded.
+	 */
+	return FW_UPLOAD_ERR_NONE;
+}
+
+/*
+ * TDX module updates cannot be cancelled. Provide a stub function since
+ * the firmware upload framework requires a .cancel operation.
+ */
+static void tdx_fw_cancel(struct fw_upload *fwl)
+{
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
@@ -123,7 +218,7 @@ static int __init tdx_host_init(void)
 	if (!x86_match_cpu(tdx_host_ids) || !tdx_get_sysinfo())
 		return -ENODEV;
 
-	fdev = faux_device_create_with_groups(KBUILD_MODNAME, NULL, NULL, tdx_host_groups);
+	fdev = faux_device_create_with_groups(KBUILD_MODNAME, NULL, &tdx_host_ops, tdx_host_groups);
 	if (!fdev)
 		return -ENODEV;

---

## [9] Chao Gao — 2026-03-31
*Subject: [PATCH v7 08/22] x86/virt/seamldr: Allocate and populate a module update request*

P-SEAMLDR uses the SEAMLDR_PARAMS structure to describe TDX module
update requests. This structure contains physical addresses pointing to
the module binary and its signature file (or sigstruct), along with an
update scenario field.

TDX modules are distributed in the tdx_blob format defined in
blob_structure.txt from the "Intel TDX module Binaries Repository". A
tdx_blob contains a header, sigstruct, and module binary. This is also the
format supplied by the userspace to the kernel.

Parse the tdx_blob format and populate a SEAMLDR_PARAMS structure
accordingly. This structure will be passed to P-SEAMLDR to initiate the
update.

Note that the sigstruct_pa field in SEAMLDR_PARAMS has been extended to
a 4-element array. The updated "SEAM Loader (SEAMLDR) Interface
Specification" will be published separately. P-SEAMLDR compatibility
validation (such as 4KB vs 16KB sigstruct support) is left to userspace,
which must verify the P-SEAMLDR version meets the TDX module's minimum
requirements.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
---
v7:
 - add blob size/alignment validation. Ensure 4KB chunking is clearly
   correct: serves as both defense and documentation
 - split a long one-line comment [Kiryl]

v6:
 - clarify tdx_blob's @offset_of_module and @len fields [Kiryl]
 - clarify comment to explicitly call out the PAGE_SIZE != SZ_4K case
   [Kiryl]

v5:
 - use a macro for tdx_blob version (0x100) [Yan]
 - don't do alignment checking for the binary/sigstruct [Rick]
 - drop blob's sigstruct and validation checking
 - set seamldr_params.version to 1 when necessary
 - drop the link to blob_structure.txt which might be unstable [Kai]

v4:
 - Remove checksum verification as it is optional
 - Convert comments to is_vmalloc_addr() checks [Kai]
 - Explain size/alignment checks in alloc_seamldr_params() [Kai]

v3:
 - Print tdx_blob version in hex [Binbin]
 - Drop redundant sigstruct alignment check [Yilun]
 - Note buffers passed from firmware upload infrastructure are
   vmalloc()'d above alloc_seamldr_params()
---
 arch/x86/virt/vmx/tdx/seamldr.c | 163 ++++++++++++++++++++++++++++++++
 1 file changed, 163 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index e93a5d90a3ee..219a8e0c7127 100644
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
 
+#define SEAMLDR_MAX_NR_MODULE_4KB_PAGES	496
+#define SEAMLDR_MAX_NR_SIG_4KB_PAGES	4
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
+	u64	sigstruct_pa[SEAMLDR_MAX_NR_SIG_4KB_PAGES];
+	u8	reserved[80];
+	u64	num_module_pages;
+	u64	mod_pages_pa_list[SEAMLDR_MAX_NR_MODULE_4KB_PAGES];
+} __packed;
+
+static_assert(sizeof(struct seamldr_params) == 4096);
+
 /*
  * Serialize P-SEAMLDR calls since the hardware only allows a single CPU to
  * interact with P-SEAMLDR simultaneously. Use raw version as the calls can
@@ -42,6 +70,136 @@ int seamldr_get_info(struct seamldr_info *seamldr_info)
 }
 EXPORT_SYMBOL_FOR_MODULES(seamldr_get_info, "tdx-host");
 
+static void free_seamldr_params(struct seamldr_params *params)
+{
+	free_page((unsigned long)params);
+}
+
+static struct seamldr_params *alloc_seamldr_params(const void *module, unsigned int module_size,
+						   const void *sig, unsigned int sig_size)
+{
+	struct seamldr_params *params;
+	const u8 *ptr;
+	int i;
+
+	if (module_size > SEAMLDR_MAX_NR_MODULE_4KB_PAGES * SZ_4K)
+		return ERR_PTR(-EINVAL);
+
+	if (sig_size > SEAMLDR_MAX_NR_SIG_4KB_PAGES * SZ_4K)
+		return ERR_PTR(-EINVAL);
+
+	/*
+	 * Check that input buffers satisfy P-SEAMLDR's size and alignment
+	 * constraints so they can be passed directly to P-SEAMLDR without
+	 * relocation or copy.
+	 */
+	if (!IS_ALIGNED(module_size, SZ_4K) || !IS_ALIGNED(sig_size, SZ_4K) ||
+	    !IS_ALIGNED((unsigned long)module, SZ_4K) ||
+	    !IS_ALIGNED((unsigned long)sig, SZ_4K))
+		return ERR_PTR(-EINVAL);
+
+	params = (struct seamldr_params *)get_zeroed_page(GFP_KERNEL);
+	if (!params)
+		return ERR_PTR(-ENOMEM);
+
+	/*
+	 * Only use version 1 when required (sigstruct > 4KB) for backward
+	 * compatibility with P-SEAMLDR that lacks version 1 support.
+	 */
+	if (sig_size > SZ_4K)
+		params->version = 1;
+	else
+		params->version = 0;
+
+	params->scenario = SEAMLDR_SCENARIO_UPDATE;
+
+	ptr = sig;
+	for (i = 0; i < sig_size / SZ_4K; i++) {
+		/*
+		 * @sig is 4KB-aligned, but that does not imply PAGE_SIZE
+		 * alignment when PAGE_SIZE != SZ_4K. Always include the
+		 * in-page offset.
+		 */
+		params->sigstruct_pa[i] = (vmalloc_to_pfn(ptr) << PAGE_SHIFT) +
+					  ((unsigned long)ptr & ~PAGE_MASK);
+		ptr += SZ_4K;
+	}
+
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
+static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
+{
+	const struct tdx_blob *blob = (const void *)data;
+	int module_size, sig_size;
+	const void *sig, *module;
+
+	/*
+	 * Ensure the size is valid otherwise reading any field from the
+	 * blob may overflow.
+	 */
+	if (size <= sizeof(struct tdx_blob) || size <= blob->offset_of_module)
+		return ERR_PTR(-EINVAL);
+
+	if (blob->version != TDX_BLOB_VERSION_1)
+		return ERR_PTR(-EINVAL);
+
+	if (blob->reserved0 || memchr_inv(blob->reserved1, 0, sizeof(blob->reserved1)))
+		return ERR_PTR(-EINVAL);
+
+	/* Split the blob into a sigstruct and a module. */
+	sig		= blob->data;
+	sig_size	= blob->offset_of_module - sizeof(struct tdx_blob);
+	module		= data + blob->offset_of_module;
+	module_size	= size - blob->offset_of_module;
+
+	if (sig_size <= 0 || module_size <= 0 || blob->length != size)
+		return ERR_PTR(-EINVAL);
+
+	if (memcmp(blob->signature, "TDX-BLOB", 8))
+		return ERR_PTR(-EINVAL);
+
+	return alloc_seamldr_params(module, module_size, sig, sig_size);
+}
+
+DEFINE_FREE(free_seamldr_params, struct seamldr_params *,
+	    if (!IS_ERR_OR_NULL(_T)) free_seamldr_params(_T))
+
 /**
  * seamldr_install_module - Install a new TDX module.
  * @data: Pointer to the TDX module update blob.
@@ -51,6 +209,11 @@ EXPORT_SYMBOL_FOR_MODULES(seamldr_get_info, "tdx-host");
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

## [10] Chao Gao — 2026-03-31
*Subject: [PATCH v7 09/22] x86/virt/seamldr: Introduce skeleton for TDX module updates*

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
maintenance overhead to KVM for this TDX-specific use case.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
---
v7:
 - hold cpu hotplug lock before updates as the online cpu count should
   be stable otherwise forward progress isn't guaranteed.

v5:
 - rewrite the commit message [Rick]
 - use a lock to synchronize accesses to update_data [Dave]
 - rename tdp_state and tdp_data to module_update_state and update_data
   for clarity [Kai]

v2:
 - refine the changlog to follow context-problem-solution structure
 - move alternative discussions at the end of the changelog
 - add a comment about state machine transition
 - Move rcu_momentary_eqs() call to the else branch.
---
 arch/x86/virt/vmx/tdx/seamldr.c | 84 ++++++++++++++++++++++++++++++++-
 1 file changed, 82 insertions(+), 2 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 219a8e0c7127..3bcde3fd94a6 100644
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
 
@@ -197,6 +199,77 @@ static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
 	return alloc_seamldr_params(module, module_size, sig, sig_size);
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
 	    if (!IS_ERR_OR_NULL(_T)) free_seamldr_params(_T))
 
@@ -214,7 +287,14 @@ int seamldr_install_module(const u8 *data, u32 size)
 	if (IS_ERR(params))
 		return PTR_ERR(params);
 
-	/* TODO: Update TDX module here */
-	return 0;
+	/*
+	 * Prevent CPU hotplug. If a CPU goes offline after thread_ack
+	 * initialization, thread_ack will exceed the online count and
+	 * never decrement to zero, causing all CPUs spinning forever
+	 * with IRQs disabled.
+	 */
+	guard(cpus_read_lock)();
+	set_target_state(MODULE_UPDATE_START + 1);
+	return stop_machine_cpuslocked(do_seamldr_install_module, params, cpu_online_mask);
 }
 EXPORT_SYMBOL_FOR_MODULES(seamldr_install_module, "tdx-host");

---

## [11] Chao Gao — 2026-03-31
*Subject: [PATCH v7 10/22] x86/virt/seamldr: Abort updates if errors occurred midway*

The TDX module update process has multiple steps, each of which may
encounter failures.

The current state machine of updates proceeds to the next step regardless
of errors. But continuing updates when errors occur midway is pointless.

Abort the update by setting a flag to indicate that a CPU has encountered
an error, forcing all CPUs to exit the execution loop. Note that failing
CPUs do not acknowledge the current step. This keeps all other CPUs waiting
in the current step (since advancing to the next step requires all CPUs to
acknowledge the current step) until they detect the fault flag and exit the
loop.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
---
v6:
 - change failure indicator from int to boolean [Kiryl]
 - replace lock with WRITE_ONCE for @failed [Kiryl]
v5:
 - Replace failed count from atomic_t to int since it's now protected by
   a lock.

v3:
 - Instead of fast-forward to the final stage, exit the execution loop
   directly.
---
 arch/x86/virt/vmx/tdx/seamldr.c | 9 +++++++--
 1 file changed, 7 insertions(+), 2 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 3bcde3fd94a6..5964bbc67944 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -213,6 +213,7 @@ enum module_update_state {
 static struct {
 	enum module_update_state state;
 	int thread_ack;
+	bool failed;
 	/*
 	 * Protect update_data. Raw spinlock as it will be acquired from
 	 * interrupt-disabled contexts.
@@ -260,12 +261,15 @@ static int do_seamldr_install_module(void *seamldr_params)
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
@@ -294,6 +298,7 @@ int seamldr_install_module(const u8 *data, u32 size)
 	 * with IRQs disabled.
 	 */
 	guard(cpus_read_lock)();
+	update_data.failed = false;
 	set_target_state(MODULE_UPDATE_START + 1);
 	return stop_machine_cpuslocked(do_seamldr_install_module, params, cpu_online_mask);
 }

---

## [12] Chao Gao — 2026-03-31
*Subject: [PATCH v7 11/22] x86/virt/seamldr: Shut down the current TDX module*

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

Note that only one CPU needs to call the TDX module's shutdown API.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
---
v5:
 - Massage changelog [Kai]
 - Avoid "refers to the global copy while populating the tdx_sys_info
   passed as a pointer" [Rick/Yilun]

v4:
 - skip the whole handoff metadata if runtime updates are not supported
   [Yilun]
v3:
 - remove autogeneration stuff in the changelog
v2:
 - add a comment about how handoff version is chosen.
 - remove the first !ret in get_tdx_sys_info_handoff() as we edited the
   auto-generated code anyway
 - remove !! when determining whether a CPU is the primary one
 - remove unnecessary if-break nesting in TDP_SHUTDOWN
---
 arch/x86/include/asm/tdx_global_metadata.h  |  5 +++++
 arch/x86/virt/vmx/tdx/seamldr.c             | 11 ++++++++++-
 arch/x86/virt/vmx/tdx/tdx.c                 | 15 +++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h                 |  3 +++
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c | 20 ++++++++++++++++++++
 5 files changed, 53 insertions(+), 1 deletion(-)

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
index 5964bbc67944..a8bfa30ee55f 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -15,6 +15,7 @@
 #include <asm/seamldr.h>
 
 #include "seamcall_internal.h"
+#include "tdx.h"
 
 /* P-SEAMLDR SEAMCALL leaf function */
 #define P_SEAMLDR_INFO			0x8000000000000000
@@ -207,6 +208,7 @@ static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
  */
 enum module_update_state {
 	MODULE_UPDATE_START,
+	MODULE_UPDATE_SHUTDOWN,
 	MODULE_UPDATE_DONE,
 };
 
@@ -246,8 +248,12 @@ static void ack_state(void)
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
@@ -256,7 +262,10 @@ static int do_seamldr_install_module(void *seamldr_params)
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
index 172f6d4133b5..f87fad429f4e 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1176,6 +1176,21 @@ int tdx_enable(void)
 }
 EXPORT_SYMBOL_FOR_KVM(tdx_enable);
 
+int tdx_module_shutdown(void)
+{
+	struct tdx_module_args args = {};
+
+	/*
+	 * Shut down the TDX module and prepare handoff data for the next
+	 * TDX module. This SEAMCALL requires a handoff version. Use the
+	 * module's handoff version, as it is the highest version the
+	 * module can produce and is more likely to be supported by new
+	 * modules as new modules likely have higher handoff version.
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
index 34c050d74b56..225e157805e8 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -100,6 +100,19 @@ static int get_tdx_sys_info_td_conf(struct tdx_sys_info_td_conf *sysinfo_td_conf
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
 static int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 {
 	int ret = 0;
@@ -116,5 +129,12 @@ static int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 	ret = ret ?: get_tdx_sys_info_td_ctrl(&sysinfo->td_ctrl);
 	ret = ret ?: get_tdx_sys_info_td_conf(&sysinfo->td_conf);
 
+	/*
+	 * Don't treat a module that doesn't support update as a failure.
+	 * Only read the metadata optionally.
+	 */
+	if (tdx_supports_runtime_update(sysinfo))
+		ret = ret ?: get_tdx_sys_info_handoff(&sysinfo->handoff);
+
 	return ret;
 }

---

## [13] Chao Gao — 2026-03-31
*Subject: [PATCH v7 12/22] x86/virt/tdx: Reset software states during TDX module shutdown*

The TDX module requires a one-time global initialization (TDH.SYS.INIT) and
per-CPU initialization (TDH.SYS.LP.INIT) before use. These initializations
are guarded by software flags to prevent repetition.

After TDX module updates, the new TDX module requires the same global and
per-CPU initializations, but the existing software flags prevent
re-initialization.

Reset all software flags guarding the initialization flows to allow the
global and per-CPU initializations to be triggered again after updates.

Set tdx_module_status to ERROR to indicate the module is unavailable. This
is to prevent re-initialization/tdx_sysinfo reporting on a failed update.
Using ERROR instead of UNINITIALIZED as the latter implicitly depends on
get_tdx_sys_info() failing early to prevent re-init after successful
shutdown followed by failed update.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
---
v7:
 - Use ERROR instead of UNINITIALIZED for tdx_module_status. Both work,
   but UNINITIALIZED implicitly depends on get_tdx_sys_info() failing
   early to prevent re-initialization after successful shutdown followed
   by failed update

 - add a comment to explain why no lock is held and re-initialization
   isn't a problem.
v6:
 - reset tdx_lp_initialized for offlined CPUs and update the comment
   accordingly [Kai]
v5:
 - add a comment to clarify why state access doesn't require holding a
   lock. [Kai]
---
 arch/x86/virt/vmx/tdx/tdx.c | 31 ++++++++++++++++++++++++++++---
 1 file changed, 28 insertions(+), 3 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index f87fad429f4e..4c9565d507fe 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -55,6 +55,8 @@ static struct tdmr_info_list tdx_tdmr_list;
 
 static enum tdx_module_status_t tdx_module_status;
 static DEFINE_MUTEX(tdx_module_lock);
+static bool sysinit_done;
+static int sysinit_ret;
 
 /* All TDX-usable memory regions.  Protected by mem_hotplug_lock. */
 static LIST_HEAD(tdx_memlist);
@@ -70,8 +72,6 @@ static int try_init_module_global(void)
 {
 	struct tdx_module_args args = {};
 	static DEFINE_RAW_SPINLOCK(sysinit_lock);
-	static bool sysinit_done;
-	static int sysinit_ret;
 
 	lockdep_assert_irqs_disabled();
 
@@ -1179,6 +1179,7 @@ EXPORT_SYMBOL_FOR_KVM(tdx_enable);
 int tdx_module_shutdown(void)
 {
 	struct tdx_module_args args = {};
+	int ret, cpu;
 
 	/*
 	 * Shut down the TDX module and prepare handoff data for the next
@@ -1188,7 +1189,31 @@ int tdx_module_shutdown(void)
 	 * modules as new modules likely have higher handoff version.
 	 */
 	args.rcx = tdx_sysinfo.handoff.module_hv;
-	return seamcall_prerr(TDH_SYS_SHUTDOWN, &args);
+	ret = seamcall_prerr(TDH_SYS_SHUTDOWN, &args);
+	if (ret)
+		return ret;
+
+	/*
+	 * Mark the module is unavailable (in ERROR status) to prevent
+	 * re-initialization and tdx_sysinfo reporting. Note the status
+	 * will be restored after a successful update.
+	 *
+	 * No need to acquire tdx_module_lock here since this runs in
+	 * stop_machine() where no concurrent initialization can occur.
+	 */
+	tdx_module_status = TDX_MODULE_ERROR;
+	sysinit_done = false;
+	sysinit_ret = 0;
+
+	/*
+	 * Since the TDX module is shut down and gone, mark all CPUs
+	 * (including offlined ones) as uninitialized. This is called in
+	 * stop_machine() (where CPU hotplug is disabled), preventing
+	 * races with other tdx_lp_initialized accesses.
+	 */
+	for_each_possible_cpu(cpu)
+		per_cpu(tdx_lp_initialized, cpu) = false;
+	return 0;
 }
 
 static bool is_pamt_page(unsigned long phys)

---

## [14] Chao Gao — 2026-03-31
*Subject: [PATCH v7 13/22] x86/virt/seamldr: Install a new TDX module*

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
---
v6:
 - wrap seamldr_call(P_SEAMLDR_INSTALL..) in a helper [Kiryl]
v5:
 - drop "serially" from the changelog as it doesn't matter to
   this patch
---
 arch/x86/virt/vmx/tdx/seamldr.c | 12 ++++++++++++
 1 file changed, 12 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index a8bfa30ee55f..3e46f3bfaa8b 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -19,6 +19,7 @@
 
 /* P-SEAMLDR SEAMCALL leaf function */
 #define P_SEAMLDR_INFO			0x8000000000000000
+#define P_SEAMLDR_INSTALL		0x8000000000000001
 
 #define SEAMLDR_MAX_NR_MODULE_4KB_PAGES	496
 #define SEAMLDR_MAX_NR_SIG_4KB_PAGES	4
@@ -73,6 +74,13 @@ int seamldr_get_info(struct seamldr_info *seamldr_info)
 }
 EXPORT_SYMBOL_FOR_MODULES(seamldr_get_info, "tdx-host");
 
+static int seamldr_install(const struct seamldr_params *params)
+{
+	struct tdx_module_args args = { .rcx = __pa(params) };
+
+	return seamldr_call(P_SEAMLDR_INSTALL, &args);
+}
+
 static void free_seamldr_params(struct seamldr_params *params)
 {
 	free_page((unsigned long)params);
@@ -209,6 +217,7 @@ static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
 enum module_update_state {
 	MODULE_UPDATE_START,
 	MODULE_UPDATE_SHUTDOWN,
+	MODULE_UPDATE_CPU_INSTALL,
 	MODULE_UPDATE_DONE,
 };
 
@@ -266,6 +275,9 @@ static int do_seamldr_install_module(void *seamldr_params)
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

## [15] Chao Gao — 2026-03-31
*Subject: [PATCH v7 14/22] x86/virt/seamldr: Do TDX per-CPU initialization after updates*

After installing the new TDX module, each CPU needs to be initialized
again to make the CPU ready to run any other SEAMCALLs. So, call
tdx_cpu_enable() on all CPUs.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
---
 arch/x86/virt/vmx/tdx/seamldr.c | 4 ++++
 1 file changed, 4 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 3e46f3bfaa8b..bb1d1487c467 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -218,6 +218,7 @@ enum module_update_state {
 	MODULE_UPDATE_START,
 	MODULE_UPDATE_SHUTDOWN,
 	MODULE_UPDATE_CPU_INSTALL,
+	MODULE_UPDATE_CPU_INIT,
 	MODULE_UPDATE_DONE,
 };
 
@@ -278,6 +279,9 @@ static int do_seamldr_install_module(void *seamldr_params)
 			case MODULE_UPDATE_CPU_INSTALL:
 				ret = seamldr_install(seamldr_params);
 				break;
+			case MODULE_UPDATE_CPU_INIT:
+				ret = tdx_cpu_enable();
+				break;
 			default:
 				break;
 			}

---

## [16] Chao Gao — 2026-03-31
*Subject: [PATCH v7 15/22] x86/virt/tdx: Restore TDX module state*

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
propagate errors and log an error message on failures.

Also note that the location and the format of handoff data is defined by
the TDX module. The new module knows where to get handoff data and how
to parse it. The kernel doesn't need to provide its location, format etc.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
---
v6:
 - make clear how errors are handled in commit message [Kiryl]
v5:
 - Massage changelog [Kai]
v3:
 - use seamcall_prerr() rather than raw seamcall() [Binbin]
 - use pr_err() to print error message [Binbin]
---
 arch/x86/virt/vmx/tdx/seamldr.c |  5 +++++
 arch/x86/virt/vmx/tdx/tdx.c     | 16 ++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h     |  2 ++
 3 files changed, 23 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index bb1d1487c467..a907b34d40c5 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -219,6 +219,7 @@ enum module_update_state {
 	MODULE_UPDATE_SHUTDOWN,
 	MODULE_UPDATE_CPU_INSTALL,
 	MODULE_UPDATE_CPU_INIT,
+	MODULE_UPDATE_RUN_UPDATE,
 	MODULE_UPDATE_DONE,
 };
 
@@ -282,6 +283,10 @@ static int do_seamldr_install_module(void *seamldr_params)
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
index 4c9565d507fe..60caceb1baa7 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1216,6 +1216,22 @@ int tdx_module_shutdown(void)
 	return 0;
 }
 
+int tdx_module_run_update(void)
+{
+	struct tdx_module_args args = {};
+	int ret;
+
+	ret = seamcall_prerr(TDH_SYS_UPDATE, &args);
+	if (ret) {
+		pr_err("update failed (%d)\n", ret);
+		tdx_module_status = TDX_MODULE_ERROR;
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
index 1c4da9540ae0..c62874b87d7a 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -47,6 +47,7 @@
 #define TDH_VP_WR			43
 #define TDH_SYS_CONFIG			45
 #define TDH_SYS_SHUTDOWN		52
+#define TDH_SYS_UPDATE			53
 
 /*
  * SEAMCALL leaf:
@@ -120,5 +121,6 @@ struct tdmr_info_list {
 };
 
 int tdx_module_shutdown(void);
+int tdx_module_run_update(void);
 
 #endif

---

## [17] Chao Gao — 2026-03-31
*Subject: [PATCH v7 16/22] x86/virt/tdx: Update tdx_sysinfo and check features post-update*

tdx_sysinfo contains all metadata of the active TDX module, including
versions, supported features, and TDMR/TDCS/TDVPS information etc. These
values may change over updates. Blindly refreshing the entire tdx_sysinfo
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

Also note that TDX module updates are supported only between releases
with different update versions but identical major and minor versions.
So, major and minor versions are not refreshed.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
---
Sashiko flagged a potential torn-read concern: update_version is read
via sysfs while it is refreshed post-update. But, update_version is a
naturally-aligned u16, and on x86, the compiler won't split aligned u16
accesses. So READ_ONCE/WRITE_ONCE() aren't needed for update_version.

v7:
 - use TDX_VERSION_FMT
 - only update update_version and add a comment to explain why

v5:
 - Drop the comment above tdx_module_post_update() [Kai]

v3:
 - use 'old' instead of 'cur' as the local variable to represent the
   sysinfo of the previous module [Binbin]
 - combine if(ret) and WARN_ONCE(1, ...) to WARN_ONCE(ret, ...) [Binbin]
 - Improve the print log messages after detecting new features from updates.
   [Binbin]

v2:
 - don't add a separate function for version and feature checks. Do them
   directly in tdx_module_post_update()
 - add a comment about preallocating a tdx_sys_info buffer in
   seamldr_install_module().
---
 arch/x86/virt/vmx/tdx/seamldr.c | 18 ++++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx.c     | 36 +++++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h     |  3 +++
 3 files changed, 56 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index a907b34d40c5..b3f3b40627c3 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -316,6 +316,18 @@ DEFINE_FREE(free_seamldr_params, struct seamldr_params *,
  */
 int seamldr_install_module(const u8 *data, u32 size)
 {
+	int ret;
+
+	/*
+	 * Preallocating a tdx_sys_info buffer before an update is to avoid
+	 * having to handle -ENOMEM when updating tdx_sysinfo after a
+	 * successful update.
+	 */
+	struct tdx_sys_info *sysinfo __free(kfree) = kzalloc(sizeof(*sysinfo),
+							     GFP_KERNEL);
+	if (!sysinfo)
+		return -ENOMEM;
+
 	struct seamldr_params *params __free(free_seamldr_params) =
 						init_seamldr_params(data, size);
 	if (IS_ERR(params))
@@ -330,6 +342,10 @@ int seamldr_install_module(const u8 *data, u32 size)
 	guard(cpus_read_lock)();
 	update_data.failed = false;
 	set_target_state(MODULE_UPDATE_START + 1);
-	return stop_machine_cpuslocked(do_seamldr_install_module, params, cpu_online_mask);
+	ret = stop_machine_cpuslocked(do_seamldr_install_module, params, cpu_online_mask);
+	if (ret)
+		return ret;
+
+	return tdx_module_post_update(sysinfo);
 }
 EXPORT_SYMBOL_FOR_MODULES(seamldr_install_module, "tdx-host");
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 60caceb1baa7..08d9f4cb32f9 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1232,6 +1232,42 @@ int tdx_module_run_update(void)
 	return 0;
 }
 
+int tdx_module_post_update(struct tdx_sys_info *info)
+{
+	struct tdx_sys_info_version *old, *new;
+	int ret;
+
+	/* Shouldn't fail as the update has succeeded. */
+	ret = get_tdx_sys_info(info);
+	if (WARN_ONCE(ret, "version retrieval failed after update, replace the TDX module\n"))
+		return ret;
+
+	old = &tdx_sysinfo.version;
+	new = &info->version;
+	pr_info("version " TDX_VERSION_FMT " -> " TDX_VERSION_FMT "\n",
+		old->major_version, old->minor_version, old->update_version,
+		new->major_version, new->minor_version, new->update_version);
+
+	/*
+	 * Blindly refreshing the entire tdx_sysinfo could disrupt running
+	 * software, as it may subtly rely on the previous state unless
+	 * proven otherwise.
+	 *
+	 * Only refresh update_version and handoff version. They don't
+	 * affect TDX functionality. Major/minor versions do not change
+	 * across updates, so no refresh is needed.
+	 */
+	tdx_sysinfo.version.update_version	= info->version.update_version;
+	tdx_sysinfo.handoff			= info->handoff;
+
+	if (!memcmp(&tdx_sysinfo, info, sizeof(*info)))
+		return 0;
+
+	pr_info("TDX module features have changed after updates, but might not take effect.\n");
+	pr_info("Please consider updating your BIOS to install the TDX module.\n");
+	return 0;
+}
+
 static bool is_pamt_page(unsigned long phys)
 {
 	struct tdmr_info_list *tdmr_list = &tdx_tdmr_list;
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index c62874b87d7a..f8686247c660 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -4,6 +4,8 @@
 
 #include <linux/bits.h>
 
+#include <asm/tdx_global_metadata.h>
+
 /*
  * This file contains both macros and data structures defined by the TDX
  * architecture and Linux defined software data structures and functions.
@@ -122,5 +124,6 @@ struct tdmr_info_list {
 
 int tdx_module_shutdown(void);
 int tdx_module_run_update(void);
+int tdx_module_post_update(struct tdx_sys_info *info);
 
 #endif

---

## [18] Chao Gao — 2026-03-31
*Subject: [PATCH v7 17/22] x86/virt/tdx: Avoid updates during update-sensitive operations*

A runtime TDX module update can conflict with TD lifecycle operations that
are update-sensitive.

Today, update-sensitive operations include:

- TD build: TD measurement is accumulated across multiple
  TDH.MEM.PAGE.ADD, TDH.MR.EXTEND, and TDH.MR.FINALIZE calls.

- TD migration: intermediate crypto state is saved/restored across
  interrupted/resumed TDH.EXPORT.STATE.* and TDH.IMPORT.STATE.* flows.

If an update races TD build, for example, TD measurement can become
incorrect and attestation can fail.

The TDX architecture exposes two approaches:

1) Avoid updates during update-sensitive operations.
2) Detect incompatibility after update and recover.

Post-update detection (option #2) is not a good fit: as discussed in [1],
future module behavior may expand update-sensitive operations in ways that
make KVM ABIs unstable and will break userspace.

"Do nothing" is also not preferred: while it keeps kernel code simple, it
lets the issue leak into the broader stack, where both detection and
recovery require significantly more effort.

So, use option #1. Specifically, request "avoid update-sensitive" behavior
during TDX module shutdown and map the resulting failure to -EBUSY so
userspace can distinguish an update race from other failures.

When the "avoid update-sensitive" feature isn't supported, proceed with
updates. If a race occurs between module update and update-sensitive
operations, failures happen at a later stage (e.g., incorrect TD
measurements in attestation reports for TD build). Effectively, this
means "let userspace update at their own risk". Userspace can check if
the feature is supported or not. The alternative of blocking updates
entirely is rejected [2] as it introduces permanent kernel complexity to
accommodate limitations in early TDX module releases that userspace can
handle.

Note: this implementation is based on a reference patch by Vishal [3].
Note2: moving "NO_RBP_MOD" is just to centralize bit definitions.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Link: https://lore.kernel.org/linux-coco/aQIbM5m09G0FYTzE@google.com/ # [1]
Link: https://lore.kernel.org/kvm/699fe97dc212f_2f4a100b@dwillia2-mobl4.notmuch/ # [2]
Link: https://lore.kernel.org/linux-coco/CAGtprH_oR44Vx9Z0cfxvq5-QbyLmy_+Gn3tWm3wzHPmC1nC0eg@mail.gmail.com/ # [3]
---
v7:
 - add error logging otherwise it is dropped when we switch from
   seamcall_prerr() to seamcall().

v6:
 - Revise the changelog to clarify behavior when "avoid
   update-sensitive" isn't supported.
 - Drop unnecessary wrapper for feature capability check
---
 arch/x86/include/asm/tdx.h   | 11 +++++++++--
 arch/x86/kvm/vmx/tdx_errno.h |  2 --
 arch/x86/virt/vmx/tdx/tdx.c  | 25 +++++++++++++++++++++----
 arch/x86/virt/vmx/tdx/tdx.h  |  3 ---
 4 files changed, 30 insertions(+), 11 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 79733fdb35c6..00751506dd3c 100644
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
index 08d9f4cb32f9..d144860e17c2 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1176,10 +1176,13 @@ int tdx_enable(void)
 }
 EXPORT_SYMBOL_FOR_KVM(tdx_enable);
 
+#define TDX_SYS_SHUTDOWN_AVOID_COMPAT_SENSITIVE BIT(16)
+
 int tdx_module_shutdown(void)
 {
 	struct tdx_module_args args = {};
-	int ret, cpu;
+	u64 ret;
+	int cpu;
 
 	/*
 	 * Shut down the TDX module and prepare handoff data for the next
@@ -1189,9 +1192,23 @@ int tdx_module_shutdown(void)
 	 * modules as new modules likely have higher handoff version.
 	 */
 	args.rcx = tdx_sysinfo.handoff.module_hv;
-	ret = seamcall_prerr(TDH_SYS_SHUTDOWN, &args);
-	if (ret)
-		return ret;
+
+	if (tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_UPDATE_COMPAT)
+		args.rcx |= TDX_SYS_SHUTDOWN_AVOID_COMPAT_SENSITIVE;
+
+	ret = seamcall(TDH_SYS_SHUTDOWN, &args);
+
+	/*
+	 * Return -EBUSY to signal that there is one or more ongoing flows
+	 * which may not be compatible with an updated TDX module, so that
+	 * userspace can retry on this error.
+	 */
+	if ((ret & TDX_SEAMCALL_STATUS_MASK) == TDX_UPDATE_COMPAT_SENSITIVE)
+		return -EBUSY;
+	if (ret) {
+		seamcall_err(TDH_SYS_SHUTDOWN, ret, &args);
+		return -EIO;
+	}
 
 	/*
 	 * Mark the module is unavailable (in ERROR status) to prevent
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index f8686247c660..2435f88c6994 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -88,9 +88,6 @@ struct tdmr_info {
 	DECLARE_FLEX_ARRAY(struct tdmr_reserved_area, reserved_areas);
 } __packed __aligned(TDMR_INFO_ALIGNMENT);
 
-/* Bit definitions of TDX_FEATURES0 metadata field */
-#define TDX_FEATURES0_NO_RBP_MOD	BIT(18)
-
 /*
  * Do not put any hardware-defined TDX structure representations below
  * this comment!

---

## [19] Chao Gao — 2026-03-31
*Subject: [PATCH v7 18/22] coco/tdx-host: Don't expose P-SEAMLDR features on CPUs with erratum*

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
Link: https://lore.kernel.org/kvm/fedb3192-e68c-423c-93b2-a4dc2f964148@intel.com/ # [1]
Link: https://lore.kernel.org/kvm/aYIXFmT-676oN6j0@google.com/ # [2]
---
 arch/x86/include/asm/cpufeatures.h    |  1 +
 arch/x86/include/asm/vmx.h            |  1 +
 arch/x86/virt/vmx/tdx/tdx.c           | 11 +++++++++++
 drivers/virt/coco/tdx-host/tdx-host.c |  8 ++++++++
 4 files changed, 21 insertions(+)

diff --git a/arch/x86/include/asm/cpufeatures.h b/arch/x86/include/asm/cpufeatures.h
index dbe104df339b..377d009b7e2e 100644
--- a/arch/x86/include/asm/cpufeatures.h
+++ b/arch/x86/include/asm/cpufeatures.h
@@ -572,4 +572,5 @@
 #define X86_BUG_ITS_NATIVE_ONLY		X86_BUG( 1*32+ 8) /* "its_native_only" CPU is affected by ITS, VMX is not affected */
 #define X86_BUG_TSA			X86_BUG( 1*32+ 9) /* "tsa" CPU is affected by Transient Scheduler Attacks */
 #define X86_BUG_VMSCAPE			X86_BUG( 1*32+10) /* "vmscape" CPU is affected by VMSCAPE attacks from guests */
+#define X86_BUG_SEAMRET_INVD_VMCS	X86_BUG( 1*32+11) /* "seamret_invd_vmcs" SEAMRET from P-SEAMLDR clears the current VMCS */
 #endif /* _ASM_X86_CPUFEATURES_H */
diff --git a/arch/x86/include/asm/vmx.h b/arch/x86/include/asm/vmx.h
index b92ff87e3560..a5a5b373ec42 100644
--- a/arch/x86/include/asm/vmx.h
+++ b/arch/x86/include/asm/vmx.h
@@ -136,6 +136,7 @@
 #define VMX_BASIC_INOUT				BIT_ULL(54)
 #define VMX_BASIC_TRUE_CTLS			BIT_ULL(55)
 #define VMX_BASIC_NO_HW_ERROR_CODE_CC		BIT_ULL(56)
+#define VMX_BASIC_NO_SEAMRET_INVD_VMCS		BIT_ULL(60)
 
 static inline u32 vmx_basic_vmcs_revision_id(u64 vmx_basic)
 {
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index d144860e17c2..92ab1d98e1b8 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -39,6 +39,7 @@
 #include <asm/cpu_device_id.h>
 #include <asm/processor.h>
 #include <asm/mce.h>
+#include <asm/vmx.h>
 
 #include "seamcall_internal.h"
 #include "tdx.h"
@@ -1462,6 +1463,8 @@ static struct notifier_block tdx_memory_nb = {
 
 static void __init check_tdx_erratum(void)
 {
+	u64 basic_msr;
+
 	/*
 	 * These CPUs have an erratum.  A partial write from non-TD
 	 * software (e.g. via MOVNTI variants or UC/WC mapping) to TDX
@@ -1473,6 +1476,14 @@ static void __init check_tdx_erratum(void)
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
index 746a5eef004d..71ea94da8e22 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -100,6 +100,14 @@ static bool can_expose_seamldr(void)
 	if (!sysinfo)
 		return false;
 
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

## [20] Chao Gao — 2026-03-31
*Subject: [PATCH v7 19/22] x86/virt/tdx: Enable TDX module runtime updates*

All pieces of TDX module runtime updates are in place. Enable it if it
is supported.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
---
 arch/x86/include/asm/tdx.h | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 00751506dd3c..0c80e78ac665 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -36,6 +36,7 @@
 #define TDX_UPDATE_COMPAT_SENSITIVE	0x8000051200000000ULL
 
 /* Bit definitions of TDX_FEATURES0 metadata field */
+#define TDX_FEATURES0_TD_PRESERVING	BIT_ULL(1)
 #define TDX_FEATURES0_NO_RBP_MOD	BIT_ULL(18)
 #define TDX_FEATURES0_UPDATE_COMPAT	BIT_ULL(47)
 
@@ -118,8 +119,7 @@ const struct tdx_sys_info *tdx_get_sysinfo(void);
 
 static inline bool tdx_supports_runtime_update(const struct tdx_sys_info *sysinfo)
 {
-	/* To be enabled when kernel is ready. */
-	return false;
+	return sysinfo->features.tdx_features0 & TDX_FEATURES0_TD_PRESERVING;
 }
 
 int tdx_guest_keyid_alloc(void);

---

## [21] Chao Gao — 2026-03-31
*Subject: [PATCH v7 20/22] coco/tdx-host: Document TDX module update compatibility criteria*

The TDX module update protocol facilitates compatible runtime updates.

Document the compatibility criteria and indicators of various update
failures, including violations of the compatibility criteria.

Note that runtime TDX module updates are an "update at your own risk"
operation; userspace must enforce all of the above compatibility
criteria.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Dan Williams <dan.j.williams@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
---
v6:
 - improve the error scenario descriptions

v5:
 - drop "dead documentation" about tdxctl
 - add a note in the changelog clarifying that users update at their own risk
 - revise the error code for update limit exhaustion—it changed after
   dropping the related patch.
v4:
 - Drop "compat_capable" kernel ABI [Dan]
 - Document Linux compatibility expectations and results of violating
   them [Dan]
---
 .../ABI/testing/sysfs-devices-faux-tdx-host   | 47 +++++++++++++++++++
 1 file changed, 47 insertions(+)

diff --git a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
index f7221f2e5fec..e1a2f3b2ea65 100644
--- a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
+++ b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
@@ -26,3 +26,50 @@ Description:	(RO) Report the number of remaining updates. TDX maintains a
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
+		facilitates "Compatible TDX Module Updates". A compatible update
+		is one that meets the following criteria:
+
+		   Does not interrupt or interfere with any current TDX
+		   operation or TD VM.
+
+		   Does not invalidate any previously consumed Module metadata
+		   values outside of the TEE_TCB_SVN_2 field (updated Security
+		   Version Number) in TD Quotes.
+
+		   Does not require validation of new Module metadata fields. By
+		   implication, new Module features and capabilities are only
+		   available by installing the Module at reboot (BIOS or EFI
+		   helper loaded).
+
+		See tdx_host/firmware/tdx_module/error for information on
+		compatibility check failures.
+
+What:		/sys/devices/faux/tdx_host/firmware/tdx_module/error
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) See Documentation/ABI/testing/sysfs-class-firmware for
+		baseline expectations for this file. The <ERROR> part in the
+		<STATUS>:<ERROR> format can be:
+
+		   "device-busy": Conflicting operations are in progress, e.g., TD
+				  build or TD migration.
+
+		   "read-write-error": Memory allocation failed.
+
+		   "hw-error": Communication with P-SEAMLDR or TDX module failed
+			       or update limit exhausted.
+
+		   "firmware-invalid": The provided TDX module update is invalid,
+				       or other unexpected errors occurred.
+
+		"hw-error" or "firmware-invalid" may be fatal, causing all TDs
+		and the TDX module to be lost and preventing further TDX
+		operations. This occurs when reading
+		/sys/devices/faux/tdx_host/version returns -ENXIO. For other
+		errors, TDs and the (previous) TDX module stay running.

---

## [22] Chao Gao — 2026-03-31
*Subject: [PATCH v7 21/22] x86/virt/tdx: Document TDX module update*

Document TDX module update as a subsection of "TDX Host Kernel Support" to
provide background information and cover key points that developers and
users may need to know, for example:

 - update is done in stop_machine() context
 - update instructions and results
 - update policy and tooling

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
---
v5:
 - use "update" when refer to the update feature/concept [Kai]
---
 Documentation/arch/x86/tdx.rst | 36 ++++++++++++++++++++++++++++++++++
 1 file changed, 36 insertions(+)

diff --git a/Documentation/arch/x86/tdx.rst b/Documentation/arch/x86/tdx.rst
index 61670e7df2f7..fe9132d0f1fe 100644
--- a/Documentation/arch/x86/tdx.rst
+++ b/Documentation/arch/x86/tdx.rst
@@ -99,6 +99,42 @@ initialize::
 
   [..] virt/tdx: module initialization failed ...
 
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

## [23] Chao Gao — 2026-03-31
*Subject: [PATCH v7 22/22] x86/virt/seamldr: Log TDX module update failures*

Currently, there is no way to restore a TDX module from shutdown state to
running state. This means if errors occur after a successful module
shutdown, they are unrecoverable since the old module is gone but the new
module isn't installed. All subsequent SEAMCALLs to the TDX module will
fail, so TDs will be killed due to SEAMCALL failures.

Log a message to clarify that SEAMCALL errors are expected in this
scenario. This ensures that after update failures, the first message in
dmesg explains the situation rather than showing confusing call traces from
various code paths.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Acked-by: Kai Huang <kai.huang@intel.com>
---
v4:
 - Use pr_warn_once() instead of reinventing it [Yilun]
v3:
 - Rephrase the changelog to eliminate the confusing uses of 'i.e.' and 'e.g.'
   [Dave/Yilun]
---
 arch/x86/virt/vmx/tdx/seamldr.c | 12 ++++++++++--
 1 file changed, 10 insertions(+), 2 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index b3f3b40627c3..a972f9ba6877 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -252,6 +252,11 @@ static void ack_state(void)
 		set_target_state(update_data.state + 1);
 }
 
+static void print_update_failure_message(void)
+{
+	pr_err_once("update failed, SEAMCALLs will report failure until TDs killed\n");
+}
+
 /*
  * See multi_cpu_stop() from where this multi-cpu state-machine was
  * adopted, and the rationale for touch_nmi_watchdog().
@@ -291,10 +296,13 @@ static int do_seamldr_install_module(void *seamldr_params)
 				break;
 			}
 
-			if (ret)
+			if (ret) {
 				WRITE_ONCE(update_data.failed, true);
-			else
+				if (curstate > MODULE_UPDATE_SHUTDOWN)
+					print_update_failure_message();
+			} else {
 				ack_state();
+			}
 		} else {
 			touch_nmi_watchdog();
 			rcu_momentary_eqs();

---

## [24] Dave Hansen — 2026-03-31
*Subject: Re: [PATCH v7 06/22] coco/tdx-host: Expose P-SEAMLDR information via
 sysfs*

On 3/31/26 05:41, Chao Gao wrote:
> Expose them as tdx-host device attributes. Make seamldr attributes
> visible only when the update feature is supported, as that's their sole

The erratum is irrelevant, IMNHO. Or it *should* be irrelevant.

---

## [25] Dave Hansen — 2026-03-31
*Subject: Re: [PATCH v7 06/22] coco/tdx-host: Expose P-SEAMLDR information via
 sysfs*

On 3/31/26 05:41, Chao Gao wrote:
> +/*
> + * Open-code DEVICE_ATTR_ADMIN_RO to specify a different 'show' function

I don't like that these are really *exactly* the same, except for the
name but are defined so differently. I see three alternatives that are
better:

1. Open code *both* so they look the same
2. Define a macro that both can use that has a seamldr_## prefix
3. Move the code to a new file to avoid symbol conflicts.

I'd honestly be fine with any of those.

The other option is to just put the module information at the top
directory so the sysfs name differentiates things.

For real, how many things are going to be in the seamldr directory? If
it's just two, is it worth having a directory?

---

## [26] Dave Hansen — 2026-03-31
*Subject: Re: [PATCH v7 07/22] coco/tdx-host: Implement firmware upload sysfs
 ABI for TDX module updates*

On 3/31/26 05:41, Chao Gao wrote:
> +static enum fw_upload_err tdx_fw_write(struct fw_upload *fwl, const u8 *data,
> +				       u32 offset, u32 size, u32 *written)

How would this non-zero offset be triggered? Wouldn't it take a bug in
the firmware upload code? If so, why bother? It's not like something bad
happens here.

---

## [27] Dave Hansen — 2026-03-31
*Subject: Re: [PATCH v7 07/22] coco/tdx-host: Implement firmware upload sysfs
 ABI for TDX module updates*

On 3/31/26 05:41, Chao Gao wrote:
> +static enum fw_upload_err tdx_fw_poll_complete(struct fw_upload *fwl)
> +{

This will be the seventh 'fw_upload_ops' and the third that has this
pattern of not needing a ->poll_complete() implementation. It seems like
allowing a NULL ->poll_complete or having a common stub for this pattern
would be worthwhile.

I also don't think you need to be that verbose. This would be fine:

	/*
	 * The upload completed during tdx_fw_write().
	 * Never poll for completion.
	 */

---

## [28] Dave Hansen — 2026-03-31
*Subject: Re: [PATCH v7 08/22] x86/virt/seamldr: Allocate and populate a module
 update request*

On 3/31/26 05:41, Chao Gao wrote:
> +	ptr = sig;
> +	for (i = 0; i < sig_size / SZ_4K; i++) {

There are a billion things the mainline kernel _could_ do. Like a 32-bit
4/4 split or a non-4k PAGE_SIZE on x86. But the mainline kernel doesn't
*do* this.

Why add complexity to deal with something that doesn't exist?

---

## [29] Chao Gao — 2026-04-01
*Subject: Re: [PATCH v7 06/22] coco/tdx-host: Expose P-SEAMLDR information via
 sysfs*

On Tue, Mar 31, 2026 at 07:58:02AM -0700, Dave Hansen wrote:
>On 3/31/26 05:41, Chao Gao wrote:
>> Expose them as tdx-host device attributes. Make seamldr attributes

OK. I'll drop the erratum mention from the commit message.

---

## [30] Chao Gao — 2026-04-01
*Subject: Re: [PATCH v7 06/22] coco/tdx-host: Expose P-SEAMLDR information via
 sysfs*

On Tue, Mar 31, 2026 at 07:58:14AM -0700, Dave Hansen wrote:
>On 3/31/26 05:41, Chao Gao wrote:
>> +/*

Good question. There are two for this series, and I don't expect there will be
more soon.

The only reason to have a separate directory is that P-SEAMLDR is a different
component from the TDX module. But I think that's a bit weak. By renaming the
attribute to seamldr_version instead of version, there's no symbol conflict.

I will apply this incremental change:

diff --git a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
index f7221f2e5fec..1ace37b7f0e9 100644
--- a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
+++ b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
@@ -5,14 +5,14 @@ Description:	(RO) Report the version of the loaded TDX module. The TDX module
		"y" is the minor version and "z" is the update version. Versions
		are used for bug reporting, TDX module updates etc.
 
-What:		/sys/devices/faux/tdx_host/seamldr/version
+What:		/sys/devices/faux/tdx_host/seamldr_version
 Contact:	linux-coco@lists.linux.dev
 Description:	(RO) Report the version of the loaded SEAM loader. The SEAM
		loader version is formatted as x.y.z, where "x" is the major
		version, "y" is the minor version and "z" is the update version.
		Versions are used for bug reporting and compatibility checks.
 
-What:		/sys/devices/faux/tdx_host/seamldr/num_remaining_updates
+What:		/sys/devices/faux/tdx_host/num_remaining_updates
 Contact:	linux-coco@lists.linux.dev
 Description:	(RO) Report the number of remaining updates. TDX maintains a
		log about each TDX module that has been loaded. This log has
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 5a672126f372..cd84108094cf 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -75,15 +75,7 @@ static ssize_t num_remaining_updates_show(struct device *dev,
	return sysfs_emit(buf, "%u\n", info.num_remaining_updates);
 }
 
-/*
- * Open-code DEVICE_ATTR_ADMIN_RO to specify a different 'show' function
- * for P-SEAMLDR version as version_show() is used for TDX module version.
- *
- * Admin-only readable as reading these attributes calls into P-SEAMLDR,
- * which may have potential performance and system impact.
- */
-static struct device_attribute dev_attr_seamldr_version =
-	__ATTR(version, 0400, seamldr_version_show, NULL);
+static DEVICE_ATTR_ADMIN_RO(seamldr_version);
 static DEVICE_ATTR_ADMIN_RO(num_remaining_updates);
 
 static struct attribute *seamldr_attrs[] = {
@@ -105,7 +97,6 @@ static bool seamldr_group_visible(struct kobject *kobj)
 DEFINE_SIMPLE_SYSFS_GROUP_VISIBLE(seamldr);
 
 static const struct attribute_group seamldr_group = {
-	.name = "seamldr",
	.attrs = seamldr_attrs,
	.is_visible = SYSFS_GROUP_VISIBLE(seamldr),
 };

---

## [31] Chao Gao — 2026-04-01
*Subject: Re: [PATCH v7 07/22] coco/tdx-host: Implement firmware upload sysfs
 ABI for TDX module updates*

On Tue, Mar 31, 2026 at 08:04:19AM -0700, Dave Hansen wrote:
>On 3/31/26 05:41, Chao Gao wrote:
>> +static enum fw_upload_err tdx_fw_write(struct fw_upload *fwl, const u8 *data,

Yes, a bug in firmware upload code or tdx_fw_write() returns partial success.

>If so, why bother? It's not like something bad
>happens here.

the comment and WARN() was added to explain why @offset isn't used at all
in this function. But if you feel this detail is obvious or doesn't help
readability, let's drop it.

---

## [32] Chao Gao — 2026-04-01
*Subject: Re: [PATCH v7 07/22] coco/tdx-host: Implement firmware upload sysfs
 ABI for TDX module updates*

On Tue, Mar 31, 2026 at 08:11:22AM -0700, Dave Hansen wrote:
>On 3/31/26 05:41, Chao Gao wrote:
>> +static enum fw_upload_err tdx_fw_poll_complete(struct fw_upload *fwl)

Thanks for this suggestion. allowing a NULL ->poll_complete looks good.

I will post a separate series for this. the core change would be:

From b0d02c337db9df040b702f57a28e960da04bd9e3 Mon Sep 17 00:00:00 2001
From: Chao Gao <chao.gao@intel.com>
Date: Tue, 31 Mar 2026 22:17:36 -0700
Subject: [PATCH] firmware_loader: Make fw_upload_ops::poll_complete() optional

mpfs-auto-update.c and thp7312.c implement poll_complete() as a trivial
stub that simply returns FW_UPLOAD_ERR_NONE, because their write() is
synchronous and the upload completes before fw_upload_ops::write() returns.

Make poll_complete() optional so that drivers with synchronous write()
don't need to duplicate this trivial stub. When the callback is not
provided, assume the upload has completed and simply return
FW_UPLOAD_ERR_NONE.

An alternative would be defining and exporting a common stub, but
exporting a stub seems unnecessary and differs from the optional
fw_upload_ops::cleanup() handling.

Suggested-by: Dave Hansen <dave.hansen@linux.intel.com>
Signed-off-by: Chao Gao <chao.gao@intel.com>
Link: https://lore.kernel.org/kvm/01fc8946-eb84-46fa-9458-f345dd3f6033@intel.com/
---
 drivers/base/firmware_loader/sysfs_upload.c | 12 +++++++++---
 include/linux/firmware.h                    |  2 +-
 2 files changed, 10 insertions(+), 4 deletions(-)

diff --git a/drivers/base/firmware_loader/sysfs_upload.c b/drivers/base/firmware_loader/sysfs_upload.c
index f59a7856934c..06788a6d7227 100644
--- a/drivers/base/firmware_loader/sysfs_upload.c
+++ b/drivers/base/firmware_loader/sysfs_upload.c
@@ -158,6 +158,13 @@ static void fw_upload_prog_complete(struct fw_upload_priv *fwlp)
	mutex_unlock(&fwlp->lock);
 }
 
+static enum fw_upload_err fw_upload_poll_complete(struct fw_upload_priv *fwlp)
+{
+	if (!fwlp->ops->poll_complete)
+		return FW_UPLOAD_ERR_NONE;
+	return fwlp->ops->poll_complete(fwlp->fw_upload);
+}
+
 static void fw_upload_main(struct work_struct *work)
 {
	struct fw_upload_priv *fwlp;
@@ -197,7 +204,7 @@ static void fw_upload_main(struct work_struct *work)
	}
 
	fw_upload_update_progress(fwlp, FW_UPLOAD_PROG_PROGRAMMING);
-	ret = fwlp->ops->poll_complete(fwl);
+	ret = fw_upload_poll_complete(fwlp);
	if (ret != FW_UPLOAD_ERR_NONE)
		fw_upload_set_error(fwlp, ret);
 
@@ -306,8 +313,7 @@ firmware_upload_register(struct module *module, struct device *parent,
	if (!name || name[0] == '\0')
		return ERR_PTR(-EINVAL);
 
-	if (!ops || !ops->cancel || !ops->prepare ||
-	    !ops->write || !ops->poll_complete) {
+	if (!ops || !ops->cancel || !ops->prepare || !ops->write) {
		dev_err(parent, "Attempt to register without all required ops\n");
		return ERR_PTR(-EINVAL);
	}
diff --git a/include/linux/firmware.h b/include/linux/firmware.h
index aae1b85ffc10..c320e8b3e708 100644
--- a/include/linux/firmware.h
+++ b/include/linux/firmware.h
@@ -57,7 +57,7 @@ struct fw_upload {
  *			  size written or a negative error code. The write()
  *			  op will be called repeatedly until all data is
  *			  written.
- * @poll_complete:	  Required: Check for the completion of the
+ * @poll_complete:	  Optional: Check for the completion of the
  *			  HW authentication/programming process.
  * @cancel:		  Required: Request cancellation of update. This op
  *			  is called from the context of a different kernel

---

## [33] Chao Gao — 2026-04-01
*Subject: Re: [PATCH v7 08/22] x86/virt/seamldr: Allocate and populate a
 module update request*

On Tue, Mar 31, 2026 at 08:44:36AM -0700, Dave Hansen wrote:
>On 3/31/26 05:41, Chao Gao wrote:
>> +	ptr = sig;

The intent was to avoid sprinkling subtle assumptions that PAGE_SIZE == SZ_4K.
But I agree that on x86 that's not a realistic concern today. I will just
assume 4KB page size.

And I assume we don't need WARN_ON_ONCE(PAGE_SIZE != SZ_4K) since this is
unlikely to break soon and shouldn't be very hard to debug and fix if it
does.

---

## [34] Sean Christopherson — 2026-04-06
*Subject: Re: [PATCH v7 17/22] x86/virt/tdx: Avoid updates during
 update-sensitive operations*

On Tue, Mar 31, 2026, Chao Gao wrote:
> A runtime TDX module update can conflict with TD lifecycle operations that
> are update-sensitive.

For the STATUS_MASK movement:

Acked-by: Sean Christopherson <seanjc@google.com>

> ---
>  arch/x86/include/asm/tdx.h   | 11 +++++++++--

...

> diff --git a/arch/x86/kvm/vmx/tdx_errno.h b/arch/x86/kvm/vmx/tdx_errno.h
> index 6ff4672c4181..215c00d76a94 100644

---

## [35] Chao Gao — 2026-04-07
*Subject: Re: [PATCH v7 09/22] x86/virt/seamldr: Introduce skeleton for TDX
 module updates*

>@@ -214,7 +287,14 @@ int seamldr_install_module(const u8 *data, u32 size)
> 	if (IS_ERR(params))

Applying Dave's feedback to simplify comments across the series. I will change
this to:

/* The lockstep update needs a stable set of online CPUs. */

>+	guard(cpus_read_lock)();
>+	set_target_state(MODULE_UPDATE_START + 1);

---

## [36] Chao Gao — 2026-04-07
*Subject: Re: [PATCH v7 11/22] x86/virt/seamldr: Shut down the current TDX
 module*

>+int tdx_module_shutdown(void)
>+{

Will change this comment to:
	/*
	 * Use the module's handoff version as it is the highest the
	 * module can produce and most likely supported by newer modules.
	 */

>+	args.rcx = tdx_sysinfo.handoff.module_hv;
>+	return seamcall_prerr(TDH_SYS_SHUTDOWN, &args);

---

## [37] Chao Gao — 2026-04-07
*Subject: Re: [PATCH v7 12/22] x86/virt/tdx: Reset software states during TDX
 module shutdown*

> int tdx_module_shutdown(void)
> {

I would like to merge the two comments and make them more concise:

	/*
	 * Clear global and per-CPU initialization flags so the new module
	 * can be fully re-initialized after a successful update. The ERROR
	 * status prevents re-init if the update ultimately fails.
	 *
	 * No locks needed as no concurrent accesses can occur here.
	 */
	tdx_module_status = TDX_MODULE_ERROR;
	sysinit_done = false;
	sysinit_ret = 0;
	for_each_possible_cpu(cpu)
		per_cpu(tdx_lp_initialized, cpu) = false;

>+	return 0;
> }

---

## [38] Chao Gao — 2026-04-07
*Subject: Re: [PATCH v7 15/22] x86/virt/tdx: Restore TDX module state*

>+int tdx_module_run_update(void)
>+{

The pr_err() isn't needed as seamcall_prerr() will emit a
message. and no need to set tdx_module_status to ERROR on
failure as it is already done during shutdown.

so, this can be simplified to:

	ret = seamcall_prerr(TDH_SYS_UPDATE, &args);
	if (ret)
		return ret;

---

## [39] Chao Gao — 2026-04-07
*Subject: Re: [PATCH v7 16/22] x86/virt/tdx: Update tdx_sysinfo and check
 features post-update*

>+int tdx_module_post_update(struct tdx_sys_info *info)
>+{

Dave's comment on another patch applies here too: don't preemptively handle
errors that never occur. The custom error message is unnecessary, and
propagating the error isn't worth it. Will simplify it to:

	/* Shouldn't fail as the update has succeeded. */
	WARN_ON_ONCE(get_tdx_sys_info(info));

>+
>+	old = &tdx_sysinfo.version;

---

## [40] Dave Hansen — 2026-04-07
*Subject: Re: [PATCH v7 16/22] x86/virt/tdx: Update tdx_sysinfo and check
 features post-update*

On 4/7/26 05:15, Chao Gao wrote:
> Dave's comment on another patch applies here too: don't preemptively handle
> errors that never occur. The custom error message is unnecessary, and

This is nit territory, but I don't like that either.

Actual, important, normal-program-flow logic should stand on its own,
separate from warnings.

OK:
	ret = foo()
	WARN_ON(ret);

Not OK:
	WARN_ON(foo());

---

## [41] Dave Hansen — 2026-04-07
*Subject: Re: [PATCH v7 09/22] x86/virt/seamldr: Introduce skeleton for TDX
 module updates*

On 4/7/26 04:49, Chao Gao wrote:
> Applying Dave's feedback to simplify comments across the series. I will change
> this to:

Try to speak in imperative voice, please:

	/* Ensure a stable set of online CPUs for ...

---

## [42] Chao Gao — 2026-04-08
*Subject: Re: [PATCH v7 16/22] x86/virt/tdx: Update tdx_sysinfo and check
 features post-update*

On Tue, Apr 07, 2026 at 08:53:47AM -0700, Dave Hansen wrote:
>On 4/7/26 05:15, Chao Gao wrote:
>> Dave's comment on another patch applies here too: don't preemptively handle

Good point. Will separate the call from the warning. Thanks.

---

## [43] Edgecombe, Rick P — 2026-04-10
*Subject: Re: [PATCH v7 01/22] x86/virt/tdx: Move low level SEAMCALL helpers
 out of <asm/tdx.h>*

On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
> From: Kai Huang <kai.huang@intel.com>
> 

This patch already has Dave's ack. So nits are not really in order here. But it
bothers me that the very first sentence of the series has what looks like a
typo. Not the best first impression. Should be "SEAMCALLs"?

> to the TDX module.  Currently, they are implemented in <asm/tdx.h> and
> are exposed to other kernel code which includes <asm/tdx.h>.

---

## [44] Edgecombe, Rick P — 2026-04-10
*Subject: Re: [PATCH v7 04/22] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
> The TDX architecture uses the "SEAMCALL" instruction to communicate with
> SEAM mode software. Right now, the only SEAM mode software that the kernel

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [45] Edgecombe, Rick P — 2026-04-11
*Subject: Re: [PATCH v7 05/22] x86/virt/seamldr: Add a helper to retrieve
 P-SEAMLDR information*

On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
> P-SEAMLDR returns its information such as version number, in response to
> the SEAMLDR.INFO SEAMCALL.

We know what this will be used for, so it would have been nice to say it. Like:

This information is useful for userspace admins to decide.... Future changes
will expose it to userspace...

Plus the remaining updates part is not hinted at.

> 
> Add a helper to retrieve P-SEAMLDR information in preparation for

Either way,

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [46] Edgecombe, Rick P — 2026-04-11
*Subject: Re: [PATCH v7 07/22] coco/tdx-host: Implement firmware upload sysfs
 ABI for TDX module updates*

On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
> +static enum fw_upload_err tdx_fw_write(struct fw_upload *fwl, const u8 *data,
> +				       u32 offset, u32 size, u32 *written)

It's hard to review whether these error codes match because the function doesn't
return them yet. Why isn't this patch just done later in the series after
everything is in place?

> +	}
> +}

---

## [47] Edgecombe, Rick P — 2026-04-11
*Subject: Re: [PATCH v7 08/22] x86/virt/seamldr: Allocate and populate a module
 update request*

On Wed, 2026-04-01 at 16:27 +0800, Chao Gao wrote:
> And I assume we don't need WARN_ON_ONCE(PAGE_SIZE != SZ_4K) since this is
> unlikely to break soon and shouldn't be very hard to debug and fix if it

+1

---

## [48] Edgecombe, Rick P — 2026-04-11
*Subject: Re: [PATCH v7 08/22] x86/virt/seamldr: Allocate and populate a module
 update request*

On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
> P-SEAMLDR uses the SEAMLDR_PARAMS structure to describe TDX module
> update requests. This structure contains physical addresses pointing to

The thing that confused me about this earlier was the exact reason why we are
checking all the fields. We discussed that we need to check the fields that
kernel processes, but we don't need to double check data that the TDX module
processes.

Should we explain it? And how it explains the checks below?

> 
> Note that the sigstruct_pa field in SEAMLDR_PARAMS has been extended to

Do we really need this helper? This doesn't work?

DEFINE_FREE(free_seamldr_params, struct seamldr_params *,
	    if (!IS_ERR_OR_NULL(_T)) free_page((unsigned long)_T))


> +
> +static struct seamldr_params *alloc_seamldr_params(const void *module, unsigned int module_size,

I don't know if it's worth that much, but we could do a MIN thing here to
protect the loop, and lose the conditionals. If userspace passes a blob that is
out of spec they can deal with the module error, no?

> +
> +	/*

I thought you are going to reduce this checking to just to reject invalid input
that the kernel processes.

What happens if we don't check this? The vmallocs are all going to be page
aligned anyway. But even still, does it mess up the below loops somehow in a way
that hurts anything?

I might be confused, but it seems different then we discussed.

> +
> +	params = (struct seamldr_params *)get_zeroed_page(GFP_KERNEL);

I'm a bit confused by this part. What does it mean to support old P-SEAMLDRs?
But also could it be:

params->version = sig_size > SZ_4K;

> +
> +	params->scenario = SEAMLDR_SCENARIO_UPDATE;

Did you consider just passing the tdx_blob into alloc_seamldr_params()?
Basically, this function checks the blob fields, then alloc_seamldr_params()
turns blob into  struct seamldr_params without checks. The way it is, the work
seems kind of spread around two functions with various checks.

> +
> +	if (sig_size <= 0 || module_size <= 0 || blob->length != size)

---

## [49] Edgecombe, Rick P — 2026-04-11
*Subject: Re: [PATCH v7 09/22] x86/virt/seamldr: Introduce skeleton for TDX
 module updates*

On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
> Potential alternative to stop_machine()
> =======================================

I'd add a little imperative ending like ", so don't take this approach."

> 
> Signed-off-by: Chao Gao <chao.gao@intel.com>

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [50] Edgecombe, Rick P — 2026-04-11
*Subject: Re: [PATCH v7 10/22] x86/virt/seamldr: Abort updates if errors
 occurred midway*

On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
> The TDX module update process has multiple steps, each of which may
> encounter failures.

This kind of begs the question of how much it matters if some pointless work
happens in error condition during a rare operation. I'm thinking at this point,
aha!, do we need this?

> 
> Abort the update by setting a flag to indicate that a CPU has encountered

So is the point of the patch to prevent the operation from getting stuck? Or
saving the user experiencing a failed update a little time?

---

## [51] Edgecombe, Rick P — 2026-04-11
*Subject: Re: [PATCH v7 11/22] x86/virt/seamldr: Shut down the current TDX
 module*

On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
> The first step of TDX module updates is shutting down the current TDX
> Module. This step also packs state information that needs to be

I feel like somewhere it's missing what this patch does. It explains the
reasoning for the handoff version selection, but nothing about implement
"MODULE_UPDATE_SHUTDOWN" or anything like that.

> 
> Note that only one CPU needs to call the TDX module's shutdown API.

This one could probably be made less verbose too.

> +	args.rcx = tdx_sysinfo.handoff.module_hv;
> +	return seamcall_prerr(TDH_SYS_SHUTDOWN, &args);

---

## [52] Edgecombe, Rick P — 2026-04-11
*Subject: Re: [PATCH v7 11/22] x86/virt/seamldr: Shut down the current TDX
 module*

On Fri, 2026-04-10 at 18:35 -0700, Rick Edgecombe wrote:
> This one could probably be made less verbose too.

Doh! You already said this.

---

## [53] Edgecombe, Rick P — 2026-04-11
*Subject: Re: [PATCH v7 12/22] x86/virt/tdx: Reset software states during TDX
 module shutdown*

On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
> The TDX module requires a one-time global initialization (TDH.SYS.INIT) and
> per-CPU initialization (TDH.SYS.LP.INIT) before use. These initializations

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

The existing code around sysinit_done/ret is very strange to me. It makes this
patch seem a bit strained, but that is not it's fault.

---

## [54] Edgecombe, Rick P — 2026-04-11
*Subject: Re: [PATCH v7 13/22] x86/virt/seamldr: Install a new TDX module*

On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
> Following the shutdown of the existing TDX module, the update process
> continues with installing the new module. P-SEAMLDR provides the

It seems a pretty straight forward one. My only question would be if the log
needs a bit more info. Not sure what to put though...

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

> ---
> v6:

In an earlier patch you have a wrapper as:
struct tdx_module_args args = = {};
args.rxx = foo;

Why the style difference? It would be good to standardize, but the existing code
isn't standardized. What do you think about going with this style through the
series for the one arg ones?

> +
> +	return seamldr_call(P_SEAMLDR_INSTALL, &args);

---

## [55] Edgecombe, Rick P — 2026-04-11
*Subject: Re: [PATCH v7 14/22] x86/virt/seamldr: Do TDX per-CPU initialization
 after updates*

On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
> After installing the new TDX module, each CPU needs to be initialized
> again to make the CPU ready to run any other SEAMCALLs. So, call

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [56] Edgecombe, Rick P — 2026-04-11
*Subject: Re: [PATCH v7 15/22] x86/virt/tdx: Restore TDX module state*

On Tue, 2026-04-07 at 20:07 +0800, Chao Gao wrote:
> > +int tdx_module_run_update(void)
> > +{

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [57] Edgecombe, Rick P — 2026-04-13
*Subject: Re: [PATCH v7 06/22] coco/tdx-host: Expose P-SEAMLDR information via
 sysfs*

On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
> TDX module updates require userspace to select the appropriate module
> to load. Expose necessary information to facilitate this decision. Two

Can you explain how all of these overlap?
 - TDX module supports module update
 - SEAMLDR supports NUM_REMAINING_UPDATES info
 - SEAMLDR supports VERSION info

If the TDX module supports module update, do we know the SEAMLDR supports this
other stuff somehow? It might be worth a comment the reasoning.

> 
> Expose them as tdx-host device attributes. Make seamldr attributes

Since this is later handled with the errata check, what is the point being made
here?

> 
> Signed-off-by: Chao Gao <chao.gao@intel.com>

---

## [58] Edgecombe, Rick P — 2026-04-13
*Subject: Re: [PATCH v7 18/22] coco/tdx-host: Don't expose P-SEAMLDR features
 on CPUs with erratum*

On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
> Some TDX-capable CPUs have an erratum, as documented in Intel® Trust
> Domain CPU Architectural Extensions (May 2021 edition) Chapter 2.3:

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

> ---
>  arch/x86/include/asm/cpufeatures.h    |  1 +

---

## [59] Edgecombe, Rick P — 2026-04-13
*Subject: Re: [PATCH v7 19/22] x86/virt/tdx: Enable TDX module runtime updates*

On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
> All pieces of TDX module runtime updates are in place. Enable it if it
> is supported.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [60] Edgecombe, Rick P — 2026-04-13
*Subject: Re: [PATCH v7 21/22] x86/virt/tdx: Document TDX module update*

On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
> Document TDX module update as a subsection of "TDX Host Kernel Support" to
> provide background information and cover key points that developers and

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [61] Edgecombe, Rick P — 2026-04-13
*Subject: Re: [PATCH v7 22/22] x86/virt/seamldr: Log TDX module update failures*

On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
> Currently, there is no way to restore a TDX module from shutdown state to
> running state. This means if errors occur after a successful module

Why is this patch at the end? Is it not valid initial behavior?

> 
> Signed-off-by: Chao Gao <chao.gao@intel.com>

Ehh, it seems ok. But is very KVM specific. I guess TDX connect will need to
update the message. The sys disable will fail too. But it does communicate the
main current actionable step for users.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

> +
>  /*

---

## [62] Chao Gao — 2026-04-14
*Subject: Re: [PATCH v7 08/22] x86/virt/seamldr: Allocate and populate a
 module update request*

On Sat, Apr 11, 2026 at 09:14:36AM +0800, Edgecombe, Rick P wrote:
>On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
>> P-SEAMLDR uses the SEAMLDR_PARAMS structure to describe TDX module

Yes. how about adding the following in the changelog:

Parse the tdx_blob format and populate a SEAMLDR_PARAMS structure. The
header is consumed solely by the kernel to extract the sigstruct and
module, so validate it before processing. The sigstruct and module are
passed to and validated by P-SEAMLDR, so don't duplicate any validation
in the kernel.

>And how it explains the checks below?


>> +static void free_seamldr_params(struct seamldr_params *params)
>> +{

No. This works. Will do.

>
>DEFINE_FREE(free_seamldr_params, struct seamldr_params *,

I think we all agree: we need to do something to protect the loop. So, the
question is just how.

looks like you prefer:

	module_size = MIN(module_size, SEAMLDR_MAX_NR_MODULE_4KB_PAGES * SZ_4K);
	sig_size = MIN(sig_size, SEAMLDR_MAX_NR_SIG_4KB_PAGES * SZ_4K);

But I think the MIN approach actually requires more justification than a plain
bounds check.

With MIN, the reasoning chain is: we don't want conditionals -> userspace
can deal with the module error -> and that error won't be fatal to the
system (or even if it is, it's admin-initiated). That's a lot of assumptions
to validate.

With a bounds check and early return, the reasoning is simply: the input is out
of range -> reject it as invalid.

>
>> +

If the blob->offset_of_module or blob->size is misaligned, the loops
silently drop the unaligned portion. P-SEAMLDR will then reject the update
after module shutdown and TDs will be killed. Since this is admin-initiated
with an intentionally invalid blob, the consequence is acceptable.

>The vmallocs are all going to be page
>aligned anyway. But even still, does it mess up the below loops somehow in a way

I agree addresses/sizes are page-aligned for valid blobs, but they are not
guaranteed (e.g., if offset_of_module is misaligned) for all inputs. I
removed the check once in v6 and Sashiko questioned it, so I thought the
assumption isn't obviously correct to everyone.

Without the check, we'd need something like:

	/*
	 * Assume sig/module base addresses and sizes are page-aligned.
	 * If violated, P-SEAMLDR will reject the update.
	 */

It's a few lines of straightforward validation vs. a comment that requires
readers to verify the assumption chain (vmalloc internals, userspace
contract, P-SEAMLDR behavior). Not sure the trade is worth it.

If you think the comment is sufficient, I'm fine dropping the checks.

>
>I might be confused, but it seems different then we discussed.

All current P-SEAMLDRs only support version 0. Version 1 is a planned
extension but not yet implemented by any P-SEAMLDR. Always requiring
version 1 just saves us a conditional but disables updates for all existing
P-SEAMLDRs for no reason. I think it is not worthwhile.

>But also could it be:
>

ok with me. I just wanted to make it match with "version 1" in the
comment right above.

>> +static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
>> +{

Fine with merging them. How about:

static struct seamldr_params *alloc_seamldr_params(const u8 *data, u32 size)
{
	const struct tdx_blob *blob = (const void *)data;
	struct seamldr_params *params;
	int module_size, sig_size;
	const void *sig, *module;
	const u8 *ptr;
	int i;

	/*
	 * Ensure the size is valid otherwise reading any field from the
	 * blob may overflow.
	 */
	if (size <= sizeof(struct tdx_blob))
		return ERR_PTR(-EINVAL);

	if (blob->version != TDX_BLOB_VERSION_1)
		return ERR_PTR(-EINVAL);
	
	if (blob->length != size)
		return ERR_PTR(-EINVAL);

	if (memcmp(blob->signature, "TDX-BLOB", 8))
		return ERR_PTR(-EINVAL);

	if (blob->reserved0 || memchr_inv(blob->reserved1, 0, sizeof(blob->reserved1)))
		return ERR_PTR(-EINVAL);

	/* Split the blob into a sigstruct and a module. */
	sig		= blob->data;
	sig_size	= blob->offset_of_module - sizeof(struct tdx_blob);
	module		= data + blob->offset_of_module;
	module_size	= size - blob->offset_of_module;

	if (module_size > SEAMLDR_MAX_NR_MODULE_4KB_PAGES * SZ_4K || module_size <= 0)
		return ERR_PTR(-EINVAL);

	if (sig_size > SEAMLDR_MAX_NR_SIG_4KB_PAGES * SZ_4K || sig_size <= 0)
		return ERR_PTR(-EINVAL);

	params = (struct seamldr_params *)get_zeroed_page(GFP_KERNEL);
	if (!params)
		return ERR_PTR(-ENOMEM);

	/*
	 * Only use version 1 when required (sigstruct > 4KB) for backward
	 * compatibility with P-SEAMLDR that lacks version 1 support.
	 */
	params->version = sig_size > SZ_4K;
	params->scenario = SEAMLDR_SCENARIO_UPDATE;

	ptr = sig;
	/*
	 * Assume sig/module base addresses and sizes are page-aligned.
	 * If violated, P-SEAMLDR will reject the update.
	 */
	for (i = 0; i < sig_size / SZ_4K; i++) {
		params->sigstruct_pa[i] = vmalloc_to_pfn(ptr) << PAGE_SHIFT;
		ptr += SZ_4K;
	}

	params->num_module_pages = module_size / SZ_4K;

	ptr = module;
	for (i = 0; i < params->num_module_pages; i++) {
		params->mod_pages_pa_list[i] = vmalloc_to_pfn(ptr) << PAGE_SHIFT;
		ptr += SZ_4K;
	}

	return params;
}

---

## [63] Chao Gao — 2026-04-14
*Subject: Re: [PATCH v7 07/22] coco/tdx-host: Implement firmware upload sysfs
 ABI for TDX module updates*

On Sat, Apr 11, 2026 at 08:26:23AM +0800, Edgecombe, Rick P wrote:
>On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
>> +static enum fw_upload_err tdx_fw_write(struct fw_upload *fwl, const u8 *data,

Good point.

The series is ordered top-down (user interface first, implementation details
later). I could either move this patch later, or add each error mapping in the
patch that introduces the corresponding return value. I'd prefer the latter to
keep the top-down ordering. Would that work for you?

---

## [64] Chao Gao — 2026-04-14
*Subject: Re: [PATCH v7 10/22] x86/virt/seamldr: Abort updates if errors
 occurred midway*

On Sat, Apr 11, 2026 at 09:26:58AM +0800, Edgecombe, Rick P wrote:
>On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
>> The TDX module update process has multiple steps, each of which may

Good question.

The main point is correctness, not saving time.

If shutdown fails midway, the update is still recoverable — TDs can continue
running. But if we proceed to seamldr.install anyway, it becomes destructive.
Aborting early on shutdown failure preserves recoverability (this is needed to
handle races between updates and TD build/migration).

If seamldr.install itself fails, it's already destructive, so aborting early
there just saves time. But using the same abort mechanism for both keeps the
error handling uniform.

---

## [65] Chao Gao — 2026-04-14
*Subject: Re: [PATCH v7 11/22] x86/virt/seamldr: Shut down the current TDX
 module*

On Sat, Apr 11, 2026 at 09:35:32AM +0800, Edgecombe, Rick P wrote:
>On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
>> The first step of TDX module updates is shutting down the current TDX

Yes. How about:

Retrieve the module's handoff version from TDX global metadata and add an
update step to shut down the module. Module shutdown has global effect, so
it only needs to run on one CPU.

---

## [66] Chao Gao — 2026-04-14
*Subject: Re: [PATCH v7 13/22] x86/virt/seamldr: Install a new TDX module*

>> +static int seamldr_install(const struct seamldr_params *params)
>> +{

Sure, happy to standardize. To confirm, you prefer this style?

	struct tdx_module_args args = { .rcx = __pa(params) };

it looks more common than the other way.

---

## [67] Chao Gao — 2026-04-14
*Subject: Re: [PATCH v7 22/22] x86/virt/seamldr: Log TDX module update failures*

On Tue, Apr 14, 2026 at 04:04:05AM +0800, Edgecombe, Rick P wrote:
>On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
>> Currently, there is no way to restore a TDX module from shutdown state to

It's not strictly required for the update to function. It just improves
debuggability by explaining expected SEAMCALL errors after a failure.

I placed it last so maintainers can easily drop it if they consider it
non-essential, similar to the guidance in *.

*: https://lore.kernel.org/kvm/63082cd1-15ab-4aaf-83ad-f72d94b9bb8e@intel.com/

---

## [68] Chao Gao — 2026-04-14
*Subject: Re: [PATCH v7 06/22] coco/tdx-host: Expose P-SEAMLDR information via
 sysfs*

On Tue, Apr 14, 2026 at 03:08:33AM +0800, Edgecombe, Rick P wrote:
>On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
>> TDX module updates require userspace to select the appropriate module

VERSION and NUM_REMAINING_UPDATES are always available for any P-SEAMLDR. They
don't depend on TDX module's update support.

>
>> 

I will drop it. Dave also questioned mentioning the erratum here.

---

## [69] Edgecombe, Rick P — 2026-04-14
*Subject: Re: [PATCH v7 06/22] coco/tdx-host: Expose P-SEAMLDR information via
 sysfs*

On Tue, 2026-04-14 at 19:20 +0800, Chao Gao wrote:
> > Can you explain how all of these overlap?
> > - TDX module supports module update

The old seamldr's don't support them though, right? At least the docs I'm
looking at show NUM_REMAINING_UPDATES as a change in the spec. Oh this update is
from 2022. So quite old now.

---

## [70] Edgecombe, Rick P — 2026-04-14
*Subject: Re: [PATCH v7 07/22] coco/tdx-host: Implement firmware upload sysfs
 ABI for TDX module updates*

On Tue, 2026-04-14 at 17:50 +0800, Chao Gao wrote:
> > It's hard to review whether these error codes match because the function
> > doesn't

Either way sounds ok to me.

---

## [71] Edgecombe, Rick P — 2026-04-14
*Subject: Re: [PATCH v7 11/22] x86/virt/seamldr: Shut down the current TDX
 module*

On Tue, 2026-04-14 at 18:09 +0800, Chao Gao wrote:
> Retrieve the module's handoff version from TDX global metadata and add an
> update step to shut down the module. Module shutdown has global effect, so

Sure.

---

## [72] Edgecombe, Rick P — 2026-04-14
*Subject: Re: [PATCH v7 13/22] x86/virt/seamldr: Install a new TDX module*

On Tue, 2026-04-14 at 18:19 +0800, Chao Gao wrote:
> > Why the style difference? It would be good to standardize, but the existing
> > code

They both seem fine to me. And, yes, this is probably in the nit category. But
if it looks sloppy it can add doubts to the code for the final review.

---

## [73] Edgecombe, Rick P — 2026-04-14
*Subject: Re: [PATCH v7 08/22] x86/virt/seamldr: Allocate and populate a module
 update request*

On Tue, 2026-04-14 at 17:43 +0800, Chao Gao wrote:
> On Sat, Apr 11, 2026 at 09:14:36AM +0800, Edgecombe, Rick P wrote:
> > On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:

Looks good.

> 
> > And how it explains the checks below?

Hmm, I'm convinced. I think a lot of tip code elides conditionals. I'm not sure
which they would prefer.

I guess the problem I see is that all these conditionals seem like a lot for
something that is mostly just getting passed through. So they need to come
across better somehow.

> 
> > 

Seems like we could drop it then.

> 
> > The vmallocs are all going to be page

Haha, as impressed as I am with AI code review... are we already at the point of
adding comments to help the AI not get confused?

> 
> Without the check, we'd need something like:

The checks seem like too much. Any ideas on how to contain it more? It seems
like you are making the case for each one. But if we delete them all... does it
seem like a better tradeoff?

> 
> > 

Sorry, I still don't understand. Why does the kernel need to set this bit? It's
an opt-in for a format change? How many old TDX modules are we talking?

I think, connecting to the discussion in the later patches, that we should try
to keep the initial implementation as small as possible. Everything we add makes
things take a little bit longer. And while we spin new versions the kernel has
zero support. So I see that this is another non-critical enhancement.

> 
> > But also could it be:

I wasn't suggesting to merge them. I was suggesting to have them each do a
dedicated thing.

> How about:
>

---

## [74] Edgecombe, Rick P — 2026-04-14
*Subject: Re: [PATCH v7 22/22] x86/virt/seamldr: Log TDX module update failures*

On Tue, 2026-04-14 at 18:25 +0800, Chao Gao wrote:
> On Tue, Apr 14, 2026 at 04:04:05AM +0800, Edgecombe, Rick P wrote:
> > On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:

Dave says:
   If you don't need it to "turn the lights on", I say kick it out.
   
To me that says to drop non critical pieces. Not put it last with no explanation
that it is optional...

---

## [75] Edgecombe, Rick P — 2026-04-14
*Subject: Re: [PATCH v7 10/22] x86/virt/seamldr: Abort updates if errors
 occurred midway*

On Tue, 2026-04-14 at 17:59 +0800, Chao Gao wrote:
> The main point is correctness, not saving time.
> 

If it's non-required for "turning the lights on" it seems aligned with Dave's
suggestion you highlighted to drop it from the series.

---

## [76] Edgecombe, Rick P — 2026-04-14
*Subject: Re: [PATCH v7 17/22] x86/virt/tdx: Avoid updates during
 update-sensitive operations*

On Tue, 2026-03-31 at 05:41 -0700, Chao Gao wrote:
> A runtime TDX module update can conflict with TD lifecycle operations that
> are update-sensitive.

How exactly does this work? There is a new error I see:
TDX_INCOMPATIBLE_MRTD_CONTEXT. It gets returned by those seamcalls sometimes.

I think(?)... TDX_INCOMPATIBLE_MRTD_CONTEXT gets returned by those seamcalls if
the problematic type of tdx module update happens between TDH.MNG.INIT and
TDH.MR.FINALIZE. So if the compat flag is not passed into shutdown... then KVM
gets some new surprise error codes to handle deep in the MMU.

> 
> - TD migration: intermediate crypto state is saved/restored across

We don't need to consider migration for this change.

> 
> If an update races TD build, for example, TD measurement can become

This subject has had a lot of debate (as linked below in the log), but the way
this is written leaves a lot of questions. "do nothing" is not an option it
says, but the code does just that when UPDATE_COMPAT_SENSITIVE is not supported.

> 
> So, use option #1. Specifically, request "avoid update-sensitive" behavior

Above it says we can't just do nothing, we need the flag. And then this argues
that we can do nothing because we can rely on userspace to deal with the
issue... This log is maybe just trying to put a brave face on an imperfect
compromise?

So, while I don't want to re-open the debate, I'm not sure the patch
justification is going to pass scrutiny as is.

In the link [2], Dan says "Do not make Linux carry short lived one-off
complexity", and also "Do not include logic to disable updates, document the
expectation in the tool."

It seems this does not exclude the option to just to always pass the compat
flag. Basically assume that the TDX module will always support
UPDATE_COMPAT_SENSITIVE if it supports TDX module updates. Which I guess we
should expect should eventually be true.

In [2] Dan was also against checking the UPDATE_COMPAT_SENSITIVE feature0 bit to
gate the feature.


For the record, I don't like allowing the update without the compat bit set, and
my concern has nothing to do with userspace roles and responsibilities. Instead
it's because we are over budget on complexity for handling SEAMCALL errors
within KVM and this makes things worse to keep track of.

tdh_mem_page_add() does a KVM_BUG_ON() if it sees a non-busy error. Imagine
working on this code and considering if it is a valid KVM_BUG_ON()? After this
patch, the answer is...well sometimes. It depends on the previous modules
specific feature0 bits, an understanding on admins expectations, and the
behavior of some far away code in arch/x86. Gah.

Actually, the diff Dan objected to was checking and printing a specific helpful
error. Maybe he does not mind much more simply checking an extra bit in
tdx_supports_runtime_update()? Otherwise, I'd think to just unconditionally pass
UPDATE_COMPAT_SENSITIVE without checking for support. Essentially mandate that
it is always supported if TDX module update is supported.

>  Userspace can check if
> the feature is supported or not. The alternative of blocking updates

---

## [77] Dan Williams — 2026-04-14
*Subject: Re: [PATCH v7 17/22] x86/virt/tdx: Avoid updates during
 update-sensitive operations*

Edgecombe, Rick P wrote:
[..]
> > If an update races TD build, for example, TD measurement can become
> > incorrect and attestation can fail.

Right, but that is not the kernel's problem. If you run updates on
a module that does not support conflict detection, you get to keep the
pieces.

Like other cases of Linux not wanting to deal with the eccentricities of
early modules, just have userspace know about a minimum module version
where this protocol exists and accept the risk otherwise. No pressing
need to burden the kernel with carrying worry for early modules.

> > So, use option #1. Specifically, request "avoid update-sensitive" behavior
> > during TDX module shutdown and map the resulting failure to -EBUSY so

Not really, the log could be simplified to just say "module versions < X
are not safe for runtime update". In general if the kernel had a minimum
supported module version concept it could collect all of these early
deprecation conditions under one check.

> So, while I don't want to re-open the debate, I'm not sure the patch
> justification is going to pass scrutiny as is.

Right, assume a minimum module version.

> In [2] Dan was also against checking the UPDATE_COMPAT_SENSITIVE feature0 bit to
> gate the feature.

...because if it must be supported, why check?

> For the record, I don't like allowing the update without the compat bit set, and
> my concern has nothing to do with userspace roles and responsibilities. Instead

Why would it be variable? The user tried update on a module that the
kernel deemed unfit for update. "Doctor, it KVM_BUG_ON()s when I run
update".

> Actually, the diff Dan objected to was checking and printing a specific helpful
> error. Maybe he does not mind much more simply checking an extra bit in

In the end all of the hand wringing we are doing is misplaced. The root
of the problem is the TDX Module claiming "runtime update supported" to
include these corner cases of "but we corrupt things if the update tries
to replace the crypto library at the wrong time".

That problem is also solvable by not classifying those updates as
runtime compatible, or defining a protocol to mitigate the collisions.

Neither of those was chosen. Instead the module implemented 2 additional
complications Linux chose one that fails update, other VMMs chose one
that maximizes updates at the cost of needing to restart TD
construction.

I think the changelog is a bit non-commital trying to be diplomatic
about the mess. Simply, Linux wanted the easy button, all runtime
updates are safe. Instead, module exported complexity and optionality.
KVM voted for one flavor of that optionality to accommodate the module
complexity.

The solution, make modules with the option KVM wants the min requirement
and move on.

---

## [78] Edgecombe, Rick P — 2026-04-14
*Subject: Re: [PATCH v7 17/22] x86/virt/tdx: Avoid updates during
 update-sensitive operations*

On Tue, 2026-04-14 at 14:43 -0700, Dan Williams wrote:
> > tdh_mem_page_add() does a KVM_BUG_ON() if it sees a non-busy error. Imagine
> > working on this code and considering if it is a valid KVM_BUG_ON()? After

The objection is not an unprepared user having an issue. It's that this adds
burden to the TDX MMU developers who have to keep track of which errors are
valid and which are not. Doing that is maybe _the_ major challenge for
maintaining that code, that code is the trickiest of TDX KVM, and we have an
easy option here to not muddy it further.

> 
> > Actually, the diff Dan objected to was checking and printing a specific

Totally, agree. We might be talking past each other. Let's not put burden on the
kernel developers when we can assume some TDX module behavior (Compat is always
supported) that we need, right?

> 
> I think the changelog is a bit non-commital trying to be diplomatic

It doesn't pick a flavor. It tries to handle them both depending on TDX module
support. See:
 
+	if (tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_UPDATE_COMPAT)
+		args.rcx |= TDX_SYS_SHUTDOWN_AVOID_COMPAT_SENSITIVE;

So it sounds like you have no objection to only supporting the mode that is easy
(TDX_SYS_SHUTDOWN_AVOID_COMPAT_SENSITIVE). If we always pass this flag, then the
TDX MMU developers can have less details to keep in their heads.

I think Chao took this as an objection to unsupporting
!TDX_FEATURES0_UPDATE_COMPAT updates, when it really was an objection to the
kernel trying too hard to help the admin:
https://lore.kernel.org/kvm/69a0c3d24310_1cc5100d1@dwillia2-mobl4.notmuch/


> 
> The solution, make modules with the option KVM wants the min requirement

---

## [79] Dan Williams — 2026-04-14
*Subject: Re: [PATCH v7 17/22] x86/virt/tdx: Avoid updates during
 update-sensitive operations*

Edgecombe, Rick P wrote:
> On Tue, 2026-04-14 at 14:43 -0700, Dan Williams wrote:
> > > tdh_mem_page_add() does a KVM_BUG_ON() if it sees a non-busy error. Imagine

I think we are in violent agreement. If a runtime update causes
tdh_mem_page_add() failure then it is simply not a runtime update.

[..]
> > I think the changelog is a bit non-commital trying to be diplomatic
> > about the mess. Simply, Linux wanted the easy button, all runtime

Oh, you mean in the sense that it proceeds without compat support? Then
yes, agree.

> It tries to handle them both depending on TDX module support. See:
>  

Yes. Just pass that flag unconditionally and treat "operand invalid" as
another "can not do a compatible update" case.

> I think Chao took this as an objection to unsupporting
> !TDX_FEATURES0_UPDATE_COMPAT updates, when it really was an objection to the

Drop !TDX_FEATURES0_UPDATE_COMPAT accommodation is the intent. Be mean
to old modules if it saves comments and conditionals in the kernel.

---

## [80] Edgecombe, Rick P — 2026-04-15
*Subject: Re: [PATCH v7 17/22] x86/virt/tdx: Avoid updates during
 update-sensitive operations*

On Tue, 2026-04-14 at 17:36 -0700, Dan Williams wrote:
> Yes. Just pass that flag unconditionally and treat "operand invalid" as
> another "can not do a compatible update" case.

Great, thanks Dan.

---

## [81] Chao Gao — 2026-04-15
*Subject: Re: [PATCH v7 10/22] x86/virt/seamldr: Abort updates if errors
 occurred midway*

On Wed, Apr 15, 2026 at 01:41:06AM +0800, Edgecombe, Rick P wrote:
>On Tue, 2026-04-14 at 17:59 +0800, Chao Gao wrote:
>> The main point is correctness, not saving time.

It is required for the shutdown case. Without early abort, a shutdown
failure (recoverable) proceeds to seamldr.install, escalating it to a
destructive failure. The race handling between TD build and updates
depends on shutdown failures being non-destructive so users can retry.

---

## [82] Chao Gao — 2026-04-15
*Subject: Re: [PATCH v7 22/22] x86/virt/seamldr: Log TDX module update failures*

On Wed, Apr 15, 2026 at 01:39:07AM +0800, Edgecombe, Rick P wrote:
>On Tue, 2026-04-14 at 18:25 +0800, Chao Gao wrote:
>> On Tue, Apr 14, 2026 at 04:04:05AM +0800, Edgecombe, Rick P wrote:

Sure. Will drop this patch.

---

## [83] Chao Gao — 2026-04-15
*Subject: Re: [PATCH v7 08/22] x86/virt/seamldr: Allocate and populate a
 module update request*

>> > > +static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
>> > > +{

Ok. See the code snippet below. Most checks are in init_seamldr_params(),
except the limit checks on module_size and sig_size. Moving them there would
require duplicating the module_size/sig_size calculations. So, I just keep the
checks next to the calculations.

static struct seamldr_params *alloc_seamldr_params(const struct tdx_blob *blob)
{
	struct seamldr_params *params;
	int module_size, sig_size;
	const void *sig, *module;
	const u8 *ptr;
	int i;

	/* Split the blob into a sigstruct and a module. */
	sig		= blob->data;
	sig_size	= blob->offset_of_module - sizeof(struct tdx_blob);
	module		= (u8 *)blob + blob->offset_of_module;
	module_size	= blob->length - blob->offset_of_module;

	if (module_size > SEAMLDR_MAX_NR_MODULE_4KB_PAGES * SZ_4K)
		return ERR_PTR(-EINVAL);

	if (sig_size > SEAMLDR_MAX_NR_SIG_4KB_PAGES * SZ_4K)
		return ERR_PTR(-EINVAL);

	params = (struct seamldr_params *)get_zeroed_page(GFP_KERNEL);
	if (!params)
		return ERR_PTR(-ENOMEM);

	/*
	 * Only use version 1 when required (sigstruct > 4KB) for backward
	 * compatibility with P-SEAMLDR that lacks version 1 support.
	 */
	params->version = sig_size > SZ_4K;
	params->scenario = SEAMLDR_SCENARIO_UPDATE;

	ptr = sig;
	for (i = 0; i < sig_size / SZ_4K; i++) {
		params->sigstruct_pa[i] = vmalloc_to_pfn(ptr) << PAGE_SHIFT;
		ptr += SZ_4K;
	}

	params->num_module_pages = module_size / SZ_4K;

	ptr = module;
	for (i = 0; i < params->num_module_pages; i++) {
		params->mod_pages_pa_list[i] = vmalloc_to_pfn(ptr) << PAGE_SHIFT;
		ptr += SZ_4K;
	}

	return params;
}

static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
{
	const struct tdx_blob *blob = (const void *)data;

	/*
	 * Ensure the size is valid otherwise reading any field from the
	 * blob may overflow.
	 */
	if (size <= sizeof(struct tdx_blob))
		return ERR_PTR(-EINVAL);

	if (blob->version != TDX_BLOB_VERSION_1)
		return ERR_PTR(-EINVAL);

	if (blob->length != size)
		return ERR_PTR(-EINVAL);

	if (memcmp(blob->signature, "TDX-BLOB", 8))
		return ERR_PTR(-EINVAL);

	if (blob->reserved0 || memchr_inv(blob->reserved1, 0, sizeof(blob->reserved1)))
		return ERR_PTR(-EINVAL);

	/* Ensure the offset_of_module is within valid range and aligned. */
	if (blob->offset_of_module >= size ||
	    blob->offset_of_module <= sizeof(struct tdx_blob))
		return ERR_PTR(-EINVAL);

	if (!IS_ALIGNED(blob->offset_of_module, SZ_4K))
		return ERR_PTR(-EINVAL);

	return alloc_seamldr_params(blob);
}

---

## [84] Edgecombe, Rick P — 2026-04-15
*Subject: Re: [PATCH v7 10/22] x86/virt/seamldr: Abort updates if errors
 occurred midway*

On Wed, 2026-04-15 at 10:59 +0800, Chao Gao wrote:
> > If it's non-required for "turning the lights on" it seems aligned
> > with Dave's

Then what is the level of support of this series intends to achieve?
There is a lot of discussion about how the admin needs to make sure to
not screw things up. What is the level of screw up that is handled by
the kernel? We should spell this out in the cover letter or something.

---

## [85] Edgecombe, Rick P — 2026-04-15
*Subject: Re: [PATCH v7 08/22] x86/virt/seamldr: Allocate and populate a module
 update request*

On Wed, 2026-04-15 at 19:04 +0800, Chao Gao wrote:
> > I wasn't suggesting to merge them. I was suggesting to have them each do
> > a dedicated thing.

Like this. All checks are moved to get_and_check_blob(). alloc_seamldr_params()
loses all checks because it's about passing things to the TDX module. Also
alloc_seamldr_params() switches to handling page counts only and becomes
smaller.

Below is not even compile tested. Please verify that everything needed
is still checked if you take from it:

/*
 * Blob fields are processed by the kernel and the payloads
 * are passed to the TDX module. Do normal user input type
 * check for any fields that don't get passed to the TDX module.
 */
static void *get_and_check_blob(const u8 *data, u32 size)
{
	const struct tdx_blob *blob = (const void *)data;

	/*
	 * Ensure the size is valid otherwise reading any field from the
	 * blob may overflow.
	 */
	if (size <= sizeof(struct tdx_blob) || size <= blob->offset_of_module)
		return ERR_PTR(-EINVAL);

	if (blob->version != TDX_BLOB_VERSION_1)
		return ERR_PTR(-EINVAL);

	if (blob->reserved0 || memchr_inv(blob->reserved1, 0, sizeof(blob->reserved1)))
		return ERR_PTR(-EINVAL);

	/*
	 * Don't care about user passing the wrong file, but protect
	 * kernel ABI by preventing accepting garbage.
	 */
	if (memcmp(blob->signature, "TDX-BLOB", 8))
		return ERR_PTR(-EINVAL);

	return blob;
}

static struct seamldr_params *alloc_seamldr_params(const struct tdx_blob *blob, unsigned int blob_size)
{
	struct seamldr_params *params;
	int module_pg_cnt, sig_pg_cnt;
	const void *sig, *module;
	const u8 *ptr;
	int i;

	params = (struct seamldr_params *)get_zeroed_page(GFP_KERNEL);
	if (!params)
		return ERR_PTR(-ENOMEM);

	/*
	 * Split the blob into a sigstruct and a module. Assume all
	 * size/offsets are within bounds of blob_size due to prior checks.
	 */
	sig		= blob->data;
	sig_pg_cnt	= (blob->offset_of_module - sizeof(struct tdx_blob)) >> PAGE_SHIFT;
	module		= blob->data + blob->offset_of_module;
	module_pg_cnt	= (blob_size - blob->offset_of_module) >> PAGE_SHIFT;

	/*
	 * Only use version 1 when required (sigstruct > 4KB) for backward
	 * compatibility with P-SEAMLDR that lacks version 1 support.
	 */
	params->version = sig_pg_cnt > 1;
	params->scenario = SEAMLDR_SCENARIO_UPDATE;

	ptr = sig;
	for (i = 0; i < MIN(sig_pg_cnt, SEAMLDR_MAX_NR_SIG_4KB_PAGES); i++) {
		/*
		 * @sig is 4KB-aligned, but that does not imply PAGE_SIZE
		 * alignment when PAGE_SIZE != SZ_4K. Always include the
		 * in-page offset.
		 */
		params->sigstruct_pa[i] = vmalloc_to_pfn(ptr) << PAGE_SHIFT;
		ptr += SZ_4K;
	}

	params->num_module_pages = MIN(module_pg_cnt, SEAMLDR_MAX_NR_MODULE_4KB_PAGES);
	ptr = module;
	for (i = 0; i < params->num_module_pages; i++) {
		params->mod_pages_pa_list[i] = vmalloc_to_pfn(ptr) << PAGE_SHIFT;
		ptr += SZ_4K;
	}

	return params;
}

static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
{
	const struct tdx_blob *blob;

	blob = get_and_check_blob(data, size);
	if (IS_ERR(blob))
		return ERR_CAST(blob);

	return alloc_seamldr_params(blob, size);
}

---
