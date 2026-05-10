---
title: 'Runtime TDX Module update support'
date: 2026-02-12
last_reply: 2026-03-13
message_count: 115
participants: ['Chao Gao', 'dan.j.williams@intel.com', 'Huang, Kai', 'Xu Yilun', 'Binbin Wu', 'Dave Hansen', 'Yan Zhao', 'Edgecombe, Rick P', 'Vishal Annapurve']
---

## [1] Chao Gao — 2026-02-12

Hi Reviewers,

With this posting, I'm hoping to collect more Reviewed-by or Acked-by tags.
In the last round of review, the first 6 patches received thorough reviews
from Dave and others. I believe they are in good shape after incorporating
all feedback, so I'm hoping to get more reviews on patch 7 and beyond.

Kai, please take a look at patch 10, which has been updated per your
suggestions.

Note that like v3, this v4 is not based on Sean's VMXON series to make this
series more reviewable.

For transparency, I should note that I used an Intel-operated AI tool to
help proofread this cover-letter and commit messages.

Changelog:
v3->v4:
 - Drop INTEL_TDX_MODULE_UPDATE kconfig [Dave]
 - Drop two unnecessary cleanup patches [Dave]
 - Drop VMCS save/restore across P-SEAMLDR calls [Dave]
   (We are pursuing microcode changes to preserve the current VMCS
    across P-SEAMLDR calls. Until then, we still need the last patch in
    this series which wraps P-SEAMLDR calls with VMCS save/restore for
    testing)
 - Don't handle P-SEAMLDR's "no_entropy" error [Dave]
 - Put seamldr_info on stack and change seamldr attributes permission
   to 0x400 [Dave]
 - Correct copyright notices [Dave]
 - Document TDX Module updates in tdx.rst 
 - Improve changelogs and comments [Dave, Kai]
 - Rename the TDX Module update sysfs directory from "seamldr_upload" to
 "tdx_module" [Cedric]
 - Merge the patch that support 16KB sigstruct to a previous patch [Kai]
 - Update tdx_blob definition to match this series' implementation [Kai]
 - Remove tdx_blob checksum verification as it is really optional
 - Don't support update canceling [Yilun]
 - Other minor code changes and changelog improvements
 - Collect review tags from Tony and Yilun
 - v3: https://lore.kernel.org/kvm/20260123145645.90444-1-chao.gao@intel.com/

This series adds support for runtime TDX Module updates that preserve
running TDX guests. It is also available at:

  https://github.com/gaochaointel/linux-dev/commits/tdx-module-updates-v4/

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

Chao Gao (23):
  coco/tdx-host: Introduce a "tdx_host" device
  coco/tdx-host: Expose TDX Module version
  x86/virt/seamldr: Introduce a wrapper for P-SEAMLDR SEAMCALLs
  x86/virt/seamldr: Retrieve P-SEAMLDR information
  coco/tdx-host: Expose P-SEAMLDR information via sysfs
  coco/tdx-host: Implement firmware upload sysfs ABI for TDX Module
    updates
  x86/virt/seamldr: Block TDX Module updates if any CPU is offline
  x86/virt/seamldr: Check update limit before TDX Module updates
  x86/virt/seamldr: Allocate and populate a module update request
  x86/virt/seamldr: Introduce skeleton for TDX Module updates
  x86/virt/seamldr: Abort updates if errors occurred midway
  x86/virt/seamldr: Shut down the current TDX module
  x86/virt/tdx: Reset software states during TDX Module shutdown
  x86/virt/seamldr: Log TDX Module update failures
  x86/virt/seamldr: Install a new TDX Module
  x86/virt/seamldr: Do TDX per-CPU initialization after updates
  x86/virt/tdx: Restore TDX Module state
  x86/virt/tdx: Update tdx_sysinfo and check features post-update
  x86/virt/tdx: Enable TDX Module runtime updates
  x86/virt/tdx: Avoid updates during update-sensitive operations
  coco/tdx-host: Document TDX Module update expectations
  x86/virt/tdx: Document TDX Module updates
  [NOT-FOR-REVIEW] x86/virt/seamldr: Save and restore current VMCS

Kai Huang (1):
  x86/virt/tdx: Move low level SEAMCALL helpers out of <asm/tdx.h>

 .../ABI/testing/sysfs-devices-faux-tdx-host   |  82 ++++
 Documentation/arch/x86/tdx.rst                |  34 ++
 arch/x86/include/asm/seamldr.h                |  37 ++
 arch/x86/include/asm/special_insns.h          |  22 ++
 arch/x86/include/asm/tdx.h                    |  66 +---
 arch/x86/include/asm/tdx_global_metadata.h    |   5 +
 arch/x86/kvm/vmx/tdx_errno.h                  |   2 -
 arch/x86/virt/vmx/tdx/Makefile                |   2 +-
 arch/x86/virt/vmx/tdx/seamcall_internal.h     | 107 ++++++
 arch/x86/virt/vmx/tdx/seamldr.c               | 360 ++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.c                   | 153 +++++---
 arch/x86/virt/vmx/tdx/tdx.h                   |  11 +-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c   |  15 +
 drivers/virt/coco/Kconfig                     |   2 +
 drivers/virt/coco/Makefile                    |   1 +
 drivers/virt/coco/tdx-host/Kconfig            |  12 +
 drivers/virt/coco/tdx-host/Makefile           |   1 +
 drivers/virt/coco/tdx-host/tdx-host.c         | 240 ++++++++++++
 18 files changed, 1050 insertions(+), 102 deletions(-)
 create mode 100644 Documentation/ABI/testing/sysfs-devices-faux-tdx-host
 create mode 100644 arch/x86/include/asm/seamldr.h
 create mode 100644 arch/x86/virt/vmx/tdx/seamcall_internal.h
 create mode 100644 arch/x86/virt/vmx/tdx/seamldr.c
 create mode 100644 drivers/virt/coco/tdx-host/Kconfig
 create mode 100644 drivers/virt/coco/tdx-host/Makefile
 create mode 100644 drivers/virt/coco/tdx-host/tdx-host.c

---

## [2] Chao Gao — 2026-02-12
*Subject: [PATCH v4 01/24] x86/virt/tdx: Move low level SEAMCALL helpers out of <asm/tdx.h>*

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

Copy the copyright notice from the original files and consolidate the
date ranges to:

	Copyright (C) 2021-2023 Intel Corporation

Signed-off-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Acked-by: Dave Hansen <dave.hansen@linux.intel.com>
---
v4:
 - Collect reviews
 - add "internal" to the new header file [Dave]
 - document the scope of the new header file [Dave]
 - correct the copyright notice [Dave]
v2:
 - new
---
 arch/x86/include/asm/tdx.h                |  47 ----------
 arch/x86/virt/vmx/tdx/seamcall_internal.h | 107 ++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.c               |  47 +---------
 3 files changed, 109 insertions(+), 92 deletions(-)
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
index 000000000000..70c3cf1f4adc
--- /dev/null
+++ b/arch/x86/virt/vmx/tdx/seamcall_internal.h
@@ -0,0 +1,107 @@
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
index 5ce4ebe99774..ddcc1a8c743f 100644
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

## [3] Chao Gao — 2026-02-12
*Subject: [PATCH v4 02/24] coco/tdx-host: Introduce a "tdx_host" device*

TDX depends on a platform firmware module that is invoked via instructions
similar to vmenter (i.e. enter into a new privileged "root-mode" context to
manage private memory and private device mechanisms). It is a software
construct that depends on the CPU vmxon state to enable invocation of
TDX-module ABIs. Unlike other Trusted Execution Environment (TEE) platform
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

A faux device is used as for TDX because the TDX module is singular within
the system and lacks associated platform resources. Using a faux device
eliminates the need to create a stub bus.

The call to tdx_get_sysinfo() ensures that the TDX Module is ready to
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
Link: https://lore.kernel.org/all/2025073035-bulginess-rematch-b92e@gregkh/ # [1]
---
v3:
 - add Jonathan's reviewed-by
 - add tdx_get_sysinfo() in module_init() to ensure the TDX Module is up
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
index ddcc1a8c743f..b65b2a609e81 100644
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
index 000000000000..e58bad148a35
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
+	  support (CONFIG_INTEL_TDX_HOST). The module is called tdx_host.ko
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

## [4] Chao Gao — 2026-02-12
*Subject: [PATCH v4 03/24] coco/tdx-host: Expose TDX Module version*

For TDX Module updates, userspace needs to select compatible update
versions based on the current module version. This design delegates
module selection complexity to userspace because TDX Module update
policies are complex and version series are platform-specific.

For example, the 1.5.x series is for certain platform generations, while
the 2.0.x series is intended for others. And TDX Module 1.5.x may be
updated to 1.5.y but not to 1.5.y+1.

Expose the TDX Module version to userspace via sysfs to aid module
selection. Since the TDX faux device will drive module updates, expose
the version as its attribute.

One bonus of exposing TDX Module version via sysfs is: TDX Module
version information remains available even after dmesg logs are cleared.

== Background ==

The "faux device + device attribute" approach compares to other update
mechanisms as follows:

1. AMD SEV leverages an existing PCI device for the PSP to expose
   metadata. TDX uses a faux device as it doesn't have PCI device
   in its architecture.

2. Microcode uses per-CPU virtual devices to report microcode revisions
   because CPUs can have different revisions. But, there is only a
   single TDX Module, so exposing the TDX Module version through a global
   TDX faux device is appropriate

3. ARM's CCA implementation isn't in-tree yet, but will likely follow a
   similar faux device approach [1], though it's unclear whether they need
   to expose firmware version information

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Link: https://lore.kernel.org/all/2025073035-bulginess-rematch-b92e@gregkh/ # [1]
---
v4:
 - collect reviews
 - Explain other version exposure implementations and why tdx's approach differs
   from them
v3:
 - Justify the sysfs ABI choice and expand background on other CoCo
   implementations.
---
 .../ABI/testing/sysfs-devices-faux-tdx-host   |  6 +++++
 drivers/virt/coco/tdx-host/tdx-host.c         | 26 ++++++++++++++++++-
 2 files changed, 31 insertions(+), 1 deletion(-)
 create mode 100644 Documentation/ABI/testing/sysfs-devices-faux-tdx-host

diff --git a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
new file mode 100644
index 000000000000..901abbae2e61
--- /dev/null
+++ b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
@@ -0,0 +1,6 @@
+What:		/sys/devices/faux/tdx_host/version
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) Report the version of the loaded TDX Module. The TDX Module
+		version is formatted as x.y.z, where "x" is the major version,
+		"y" is the minor version and "z" is the update version. Versions
+		are used for bug reporting, TDX Module updates and etc.
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index c77885392b09..0424933b2560 100644
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
+	return sysfs_emit(buf, "%u.%u.%02u\n", ver->major_version,
+					       ver->minor_version,
+					       ver->update_version);
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

## [5] Chao Gao — 2026-02-12
*Subject: [PATCH v4 04/24] x86/virt/seamldr: Introduce a wrapper for P-SEAMLDR SEAMCALLs*

The TDX architecture uses the "SEAMCALL" instruction to communicate with
SEAM mode software. Right now, the only SEAM mode software that the kernel
communicates with is the TDX module. But, there is actually another
component that runs in SEAM mode but it is separate from the TDX module:
the persistent SEAM loader or "P-SEAMLDR". Right now, the only component
that communicates with it is the BIOS which loads the TDX module itself at
boot. But, to support updating the TDX module, the kernel now needs to be
able to talk to it.

P-SEAMLDR SEAMCALLs differ from TDX Module SEAMCALLs in areas such as
concurrency requirements. Add a P-SEAMLDR wrapper to handle these
differences and prepare for implementing concrete functions.

Note that unlike P-SEAMLDR, there is also a non-persistent SEAM loader
("NP-SEAMLDR"). This is an authenticated code module (ACM) that is not
callable at runtime. Only BIOS launches it to load P-SEAMLDR at boot;
the kernel does not interact with it.

For details of P-SEAMLDR SEAMCALLs, see Intel® Trust Domain CPU
Architectural Extensions, Revision 343754-002, Chapter 2.3 "INSTRUCTION
SET REFERENCE".

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
Link: https://cdrdv2.intel.com/v1/dl/getContent/733582 # [1]
---
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
 arch/x86/virt/vmx/tdx/seamldr.c | 27 +++++++++++++++++++++++++++
 2 files changed, 28 insertions(+), 1 deletion(-)
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
index 000000000000..fb59b3e2aa37
--- /dev/null
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -0,0 +1,27 @@
+// SPDX-License-Identifier: GPL-2.0
+/*
+ * P-SEAMLDR support for TDX Module management features like runtime updates
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
+ * interact with P-SEAMLDR simultaneously.
+ */
+static DEFINE_RAW_SPINLOCK(seamldr_lock);
+
+static __maybe_unused int seamldr_call(u64 fn, struct tdx_module_args *args)
+{
+	/*
+	 * Serialize P-SEAMLDR calls and disable interrupts as the calls
+	 * can be made from IRQ context.
+	 */
+	guard(raw_spinlock_irqsave)(&seamldr_lock);
+	return seamcall_prerr(fn, args);
+}

---

## [6] Chao Gao — 2026-02-12
*Subject: [PATCH v4 05/24] x86/virt/seamldr: Retrieve P-SEAMLDR information*

P-SEAMLDR returns its information such as version number, in response to
the SEAMLDR.INFO SEAMCALL.

This information is useful for userspace. For example, the admin can decide
which TDX module versions are compatible with the P-SEAMLDR according to
the P-SEAMLDR version.

Retrieve P-SEAMLDR information in preparation for exposing P-SEAMLDR
version and other necessary information to userspace. Export the new kAPI
for use by tdx-host.ko.

Note that there are two distinct P-SEAMLDR APIs with similar names:

  SEAMLDR.INFO: Returns a SEAMLDR_INFO structure containing SEAMLDR
                information such as version and remaining updates.

  SEAMLDR.SEAMINFO: Returns a SEAMLDR_SEAMINFO structure containing SEAM
                    and system information such as Convertible Memory
		    Regions (CMRs) and number of CPUs and sockets.

The former is used here.

For details, see "Intel® Trust Domain Extensions - SEAM Loader (SEAMLDR)
Interface Specification" revision 343755-003.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
v4:
 - put seamldr_info on stack [Dave]
 - improve changelogs to explain SEAMLDR.INFO and SEAMLDR.SEAMINFO [Dave]
 - add SEAMLDR spec information in the changelog [Dave]
 - add proper comments above ABI structure definition [Dave]
 - add unused ABI structure fields rather than marking them as reserved
   to better align with the specc [Dave] (I omitted "not used by kernel"
   tags since there are 5-6 such fields and maintaining these tags would
   be tedious.)
---
 arch/x86/include/asm/seamldr.h  | 36 +++++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/seamldr.c | 15 +++++++++++++-
 2 files changed, 50 insertions(+), 1 deletion(-)
 create mode 100644 arch/x86/include/asm/seamldr.h

diff --git a/arch/x86/include/asm/seamldr.h b/arch/x86/include/asm/seamldr.h
new file mode 100644
index 000000000000..954d850e34e3
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
+ * This called the "SEAMLDR_INFO" data structure and is defined
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
index fb59b3e2aa37..d17db3c0151e 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -8,15 +8,20 @@
 
 #include <linux/spinlock.h>
 
+#include <asm/seamldr.h>
+
 #include "seamcall_internal.h"
 
+/* P-SEAMLDR SEAMCALL leaf function */
+#define P_SEAMLDR_INFO			0x8000000000000000
+
 /*
  * Serialize P-SEAMLDR calls since the hardware only allows a single CPU to
  * interact with P-SEAMLDR simultaneously.
  */
 static DEFINE_RAW_SPINLOCK(seamldr_lock);
 
-static __maybe_unused int seamldr_call(u64 fn, struct tdx_module_args *args)
+static int seamldr_call(u64 fn, struct tdx_module_args *args)
 {
 	/*
 	 * Serialize P-SEAMLDR calls and disable interrupts as the calls
@@ -25,3 +30,11 @@ static __maybe_unused int seamldr_call(u64 fn, struct tdx_module_args *args)
 	guard(raw_spinlock_irqsave)(&seamldr_lock);
 	return seamcall_prerr(fn, args);
 }
+
+int seamldr_get_info(struct seamldr_info *seamldr_info)
+{
+	struct tdx_module_args args = { .rcx = slow_virt_to_phys(seamldr_info) };
+
+	return seamldr_call(P_SEAMLDR_INFO, &args);
+}
+EXPORT_SYMBOL_FOR_MODULES(seamldr_get_info, "tdx-host");

---

## [7] Chao Gao — 2026-02-12
*Subject: [PATCH v4 06/24] coco/tdx-host: Expose P-SEAMLDR information via sysfs*

TDX Module updates require userspace to select the appropriate module
to load. Expose necessary information to facilitate this decision. Two
values are needed:

- P-SEAMLDR version: for compatibility checks between TDX Module and
		     P-SEAMLDR
- num_remaining_updates: indicates how many updates can be performed

Expose them as tdx-host device attributes.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
v4:
 - Make seamldr attribute permission "0400" [Dave]
 - Don't include implementation details in OS ABI docs [Dave]
 - Tag tdx_host_group as static [Kai]

v3:
 - use #ifdef rather than .is_visible() to control P-SEAMLDR sysfs
   visibility [Yilun]
---
 .../ABI/testing/sysfs-devices-faux-tdx-host   | 23 +++++++
 drivers/virt/coco/tdx-host/tdx-host.c         | 63 ++++++++++++++++++-
 2 files changed, 85 insertions(+), 1 deletion(-)

diff --git a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
index 901abbae2e61..88a9c0b2bdfe 100644
--- a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
+++ b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
@@ -4,3 +4,26 @@ Description:	(RO) Report the version of the loaded TDX Module. The TDX Module
 		version is formatted as x.y.z, where "x" is the major version,
 		"y" is the minor version and "z" is the update version. Versions
 		are used for bug reporting, TDX Module updates and etc.
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
+		log about each TDX Module which has been loaded. This log has
+		a finite size which limits the number of TDX Module updates
+		which can be performed.
+
+		After each successful update, the number reduces by one. Once it
+		reaches zero, further updates will fail until next reboot. The
+		number is always zero if the P-SEAMLDR doesn't support updates.
+
+		See Intel® Trust Domain Extensions - SEAM Loader (SEAMLDR)
+		Interface Specification, Revision 343755-003, Chapter 3.3
+		"SEAMLDR_INFO" and Chapter 4.2 "SEAMLDR.INSTALL" for more
+		information.
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 0424933b2560..fd6ffb4f2ff1 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -11,6 +11,7 @@
 #include <linux/sysfs.h>
 
 #include <asm/cpu_device_id.h>
+#include <asm/seamldr.h>
 #include <asm/tdx.h>
 
 static const struct x86_cpu_id tdx_host_ids[] = {
@@ -40,7 +41,67 @@ static struct attribute *tdx_host_attrs[] = {
 	&dev_attr_version.attr,
 	NULL,
 };
-ATTRIBUTE_GROUPS(tdx_host);
+
+static struct attribute_group tdx_host_group = {
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
+	return sysfs_emit(buf, "%u.%u.%02u\n", info.major_version,
+					       info.minor_version,
+					       info.update_version);
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
+ * for P-SEAMLDR version as version_show() is used for TDX Module version.
+ *
+ * admin-only readable as reading these attributes calls into P-SEAMLDR,
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
+static struct attribute_group seamldr_group = {
+	.name = "seamldr",
+	.attrs = seamldr_attrs,
+};
+
+static const struct attribute_group *tdx_host_groups[] = {
+	&tdx_host_group,
+	&seamldr_group,
+	NULL,
+};
 
 static struct faux_device *fdev;

---

## [8] Chao Gao — 2026-02-12
*Subject: [PATCH v4 07/24] coco/tdx-host: Implement firmware upload sysfs ABI for TDX Module updates*

Linux kernel supports two primary firmware update mechanisms:
  - request_firmware()
  - firmware upload (or fw_upload)
The former is used by microcode updates, SEV firmware updates, etc. The
latter is used by CXL and FPGA firmware updates.

One key difference between them is: request_firmware() loads a named
file from the filesystem, while fw_upload accepts a bitstream directly
from userspace.

Use fw_upload for TDX Module updates as loading a named file isn't
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
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
---
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
 arch/x86/include/asm/seamldr.h        |   1 +
 arch/x86/include/asm/tdx.h            |   5 ++
 arch/x86/virt/vmx/tdx/seamldr.c       |  19 +++++
 drivers/virt/coco/tdx-host/Kconfig    |   2 +
 drivers/virt/coco/tdx-host/tdx-host.c | 114 +++++++++++++++++++++++++-
 5 files changed, 140 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/seamldr.h b/arch/x86/include/asm/seamldr.h
index 954d850e34e3..e354d0bfc9f8 100644
--- a/arch/x86/include/asm/seamldr.h
+++ b/arch/x86/include/asm/seamldr.h
@@ -32,5 +32,6 @@ struct seamldr_info {
 static_assert(sizeof(struct seamldr_info) == 256);
 
 int seamldr_get_info(struct seamldr_info *seamldr_info);
+int seamldr_install_module(const u8 *data, u32 size);
 
 #endif /* _ASM_X86_SEAMLDR_H */
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index cb2219302dfc..ffadbf64d0c1 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -103,6 +103,11 @@ int tdx_enable(void);
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
index d17db3c0151e..4d40b08f9bed 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -6,6 +6,7 @@
  */
 #define pr_fmt(fmt)	"seamldr: " fmt
 
+#include <linux/mm.h>
 #include <linux/spinlock.h>
 
 #include <asm/seamldr.h>
@@ -38,3 +39,21 @@ int seamldr_get_info(struct seamldr_info *seamldr_info)
 	return seamldr_call(P_SEAMLDR_INFO, &args);
 }
 EXPORT_SYMBOL_FOR_MODULES(seamldr_get_info, "tdx-host");
+
+/**
+ * seamldr_install_module - Install a new TDX module
+ * @data: Pointer to the TDX module update blob. It should be vmalloc'd
+ *        memory.
+ * @size: Size of the TDX module update blob
+ *
+ * Returns 0 on success, negative error code on failure.
+ */
+int seamldr_install_module(const u8 *data, u32 size)
+{
+	if (WARN_ON_ONCE(!is_vmalloc_addr(data)))
+		return -EINVAL;
+
+	/* TODO: Update TDX Module here */
+	return 0;
+}
+EXPORT_SYMBOL_FOR_MODULES(seamldr_install_module, "tdx-host");
diff --git a/drivers/virt/coco/tdx-host/Kconfig b/drivers/virt/coco/tdx-host/Kconfig
index e58bad148a35..3d580d783106 100644
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
index fd6ffb4f2ff1..9ade3028a5bd 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -6,6 +6,7 @@
  */
 
 #include <linux/device/faux.h>
+#include <linux/firmware.h>
 #include <linux/module.h>
 #include <linux/mod_devicetable.h>
 #include <linux/sysfs.h>
@@ -20,6 +21,8 @@ static const struct x86_cpu_id tdx_host_ids[] = {
 };
 MODULE_DEVICE_TABLE(x86cpu, tdx_host_ids);
 
+static struct fw_upload *tdx_fwl;
+
 static ssize_t version_show(struct device *dev, struct device_attribute *attr,
 			    char *buf)
 {
@@ -103,6 +106,115 @@ static const struct attribute_group *tdx_host_groups[] = {
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
+	case -ENOSPC:
+		return FW_UPLOAD_ERR_WEAROUT;
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
+	 * TDX Module updates are completed in the previous phase
+	 * (tdx_fw_write()). If any error occurred, the previous phase
+	 * would return an error code to abort the update process. In
+	 * other words, reaching this point means the update succeeded.
+	 */
+	return FW_UPLOAD_ERR_NONE;
+}
+
+/*
+ * TDX Module updates cannot be cancelled. Provide a stub function since
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
+static void seamldr_init(struct device *dev)
+{
+	const struct tdx_sys_info *tdx_sysinfo = tdx_get_sysinfo();
+	int ret;
+
+	if (WARN_ON_ONCE(!tdx_sysinfo))
+		return;
+
+	if (!tdx_supports_runtime_update(tdx_sysinfo)) {
+		pr_info("Current TDX Module cannot be updated. Consider BIOS updates\n");
+		return;
+	}
+
+	tdx_fwl = firmware_upload_register(THIS_MODULE, dev, "tdx_module",
+					   &tdx_fw_ops, NULL);
+	ret = PTR_ERR_OR_ZERO(tdx_fwl);
+	if (ret)
+		pr_err("failed to register module uploader %d\n", ret);
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
+	/*
+	 * P-SEAMLDR capabilities are optional. Don't fail the entire
+	 * device probe if initialization fails.
+	 */
+	seamldr_init(&fdev->dev);
+
+	return 0;
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
 static struct faux_device *fdev;
 
 static int __init tdx_host_init(void)
@@ -110,7 +222,7 @@ static int __init tdx_host_init(void)
 	if (!x86_match_cpu(tdx_host_ids) || !tdx_get_sysinfo())
 		return -ENODEV;
 
-	fdev = faux_device_create_with_groups(KBUILD_MODNAME, NULL, NULL, tdx_host_groups);
+	fdev = faux_device_create_with_groups(KBUILD_MODNAME, NULL, &tdx_host_ops, tdx_host_groups);
 	if (!fdev)
 		return -ENODEV;

---

## [9] Chao Gao — 2026-02-12
*Subject: [PATCH v4 08/24] x86/virt/seamldr: Block TDX Module updates if any CPU is offline*

P-SEAMLDR requires every CPU to call SEAMLDR.INSTALL during updates. So,
every CPU should be online during updates.

Check if all CPUs are online and abort the update if any CPU is offline at
the very beginning. Without this check, P-SEAMLDR will report failure at a
later phase where the old TDX module is gone and TDs have to be killed.

Hold cpus_read_lock to avoid races between CPU hotplug and TDX Module
updates.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/seamldr.c | 8 ++++++++
 1 file changed, 8 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 4d40b08f9bed..694243f1f220 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -6,6 +6,8 @@
  */
 #define pr_fmt(fmt)	"seamldr: " fmt
 
+#include <linux/cpuhplock.h>
+#include <linux/cpumask.h>
 #include <linux/mm.h>
 #include <linux/spinlock.h>
 
@@ -53,6 +55,12 @@ int seamldr_install_module(const u8 *data, u32 size)
 	if (WARN_ON_ONCE(!is_vmalloc_addr(data)))
 		return -EINVAL;
 
+	guard(cpus_read_lock)();
+	if (!cpumask_equal(cpu_online_mask, cpu_present_mask)) {
+		pr_err("Cannot update the TDX Module if any CPU is offline\n");
+		return -EBUSY;
+	}
+
 	/* TODO: Update TDX Module here */
 	return 0;
 }

---

## [10] Chao Gao — 2026-02-12
*Subject: [PATCH v4 09/24] x86/virt/seamldr: Check update limit before TDX Module updates*

TDX maintains a log about each TDX Module which has been loaded. This
log has a finite size which limits the number of TDX Module updates
which can be performed.

After each successful update, the remaining updates reduces by one. Once
it reaches zero, further updates will fail until next reboot.

Before updating the TDX Module, verify that the update limit has not been
exceeded. Otherwise, P-SEAMLDR will detect this violation after the old TDX
Module is gone and all TDs will be killed.

Note that userspace should perform this check before updates. Perform this
check in kernel as well to make the update process more robust.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/seamldr.c | 10 ++++++++++
 1 file changed, 10 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 694243f1f220..733b13215691 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -52,6 +52,16 @@ EXPORT_SYMBOL_FOR_MODULES(seamldr_get_info, "tdx-host");
  */
 int seamldr_install_module(const u8 *data, u32 size)
 {
+	struct seamldr_info info;
+	int ret;
+
+	ret = seamldr_get_info(&info);
+	if (ret)
+		return ret;
+
+	if (!info.num_remaining_updates)
+		return -ENOSPC;
+
 	if (WARN_ON_ONCE(!is_vmalloc_addr(data)))
 		return -EINVAL;

---

## [11] Chao Gao — 2026-02-12
*Subject: [PATCH v4 10/24] x86/virt/seamldr: Allocate and populate a module update request*

P-SEAMLDR uses the SEAMLDR_PARAMS structure to describe TDX Module
update requests. This structure contains physical addresses pointing to
the module binary and its signature file (or sigstruct), along with an
update scenario field.

TDX Modules are distributed in the tdx_blob format defined at [1]. A
tdx_blob contains a header, sigstruct, and module binary. This is also
the format supplied by the userspace to the kernel.

Parse the tdx_blob format and populate a SEAMLDR_PARAMS structure
accordingly. This structure will be passed to P-SEAMLDR to initiate the
update.

Note that the sigstruct_pa field in SEAMLDR_PARAMS has been extended to
a 4-element array. The updated "SEAM Loader (SEAMLDR) Interface
Specification" will be published separately. The kernel does not
validate P-SEAMLDR compatibility (for example, whether it supports 4KB
or 16KB sigstruct); userspace must ensure the P-SEAMLDR version is
compatible with the selected TDX Module by checking the minimum
P-SEAMLDR version requirements at [2].

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Link: https://github.com/intel/confidential-computing.tdx.tdx-module.binaries/blob/main/blob_structure.txt # [1]
Link: https://github.com/intel/confidential-computing.tdx.tdx-module.binaries/blob/main/mapping_file.json # [2]
---
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
 arch/x86/virt/vmx/tdx/seamldr.c | 152 ++++++++++++++++++++++++++++++++
 1 file changed, 152 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 733b13215691..718cb8396057 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -6,9 +6,11 @@
  */
 #define pr_fmt(fmt)	"seamldr: " fmt
 
+#include <linux/cleanup.h>
 #include <linux/cpuhplock.h>
 #include <linux/cpumask.h>
 #include <linux/mm.h>
+#include <linux/slab.h>
 #include <linux/spinlock.h>
 
 #include <asm/seamldr.h>
@@ -18,6 +20,33 @@
 /* P-SEAMLDR SEAMCALL leaf function */
 #define P_SEAMLDR_INFO			0x8000000000000000
 
+#define SEAMLDR_MAX_NR_MODULE_4KB_PAGES	496
+#define SEAMLDR_MAX_NR_SIG_4KB_PAGES	4
+
+/*
+ * The seamldr_params "scenario" field specifies the operation mode:
+ * 0: Install TDX Module from scratch (not used by kernel)
+ * 1: Update existing TDX Module to a compatible version
+ */
+#define SEAMLDR_SCENARIO_UPDATE		1
+
+/*
+ * This is called the "SEAMLDR_PARAMS" data structure and is defined
+ * in "SEAM Loader (SEAMLDR) Interface Specification".
+ *
+ * It describes the TDX Module that will be installed.
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
  * interact with P-SEAMLDR simultaneously.
@@ -42,6 +71,124 @@ int seamldr_get_info(struct seamldr_info *seamldr_info)
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
+	if (WARN_ON_ONCE(!is_vmalloc_addr(module) || !is_vmalloc_addr(sig)))
+		return ERR_PTR(-EINVAL);
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
+	params->scenario = SEAMLDR_SCENARIO_UPDATE;
+
+	ptr = sig;
+	for (i = 0; i < sig_size / SZ_4K; i++) {
+		/*
+		 * Don't assume @sig is page-aligned although it is 4KB-aligned.
+		 * Always add the in-page offset to get the physical address.
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
+ * Intel TDX Module blob. Its format is defined at:
+ * https://github.com/intel/tdx-module-binaries/blob/main/blob_structure.txt
+ *
+ * Note this structure differs from the reference above: the two variable-length
+ * fields "@sigstruct" and "@module" are represented as a single "@data" field
+ * here and split programmatically using the offset_of_module value.
+ */
+struct tdx_blob {
+	u16	version;
+	u16	checksum;
+	u32	offset_of_module;
+	u8	signature[8];
+	u32	length;
+	u32	resv0;
+	u64	resv1[509];
+	u8	data[];
+} __packed;
+
+static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
+{
+	const struct tdx_blob *blob = (const void *)data;
+	int module_size, sig_size;
+	const void *sig, *module;
+
+	if (size < sizeof(struct tdx_blob) || blob->offset_of_module >= size)
+		return ERR_PTR(-EINVAL);
+
+	if (blob->version != 0x100) {
+		pr_err("unsupported blob version: %x\n", blob->version);
+		return ERR_PTR(-EINVAL);
+	}
+
+	if (blob->resv0 || memchr_inv(blob->resv1, 0, sizeof(blob->resv1))) {
+		pr_err("non-zero reserved fields\n");
+		return ERR_PTR(-EINVAL);
+	}
+
+	/* Split the blob into a sigstruct and a module */
+	sig		= blob->data;
+	sig_size	= blob->offset_of_module - sizeof(struct tdx_blob);
+	module		= data + blob->offset_of_module;
+	module_size	= size - blob->offset_of_module;
+
+	if (sig_size <= 0 || module_size <= 0 || blob->length != size)
+		return ERR_PTR(-EINVAL);
+
+	if (memcmp(blob->signature, "TDX-BLOB", 8)) {
+		pr_err("invalid signature\n");
+		return ERR_PTR(-EINVAL);
+	}
+
+	return alloc_seamldr_params(module, module_size, sig, sig_size);
+}
+
+DEFINE_FREE(free_seamldr_params, struct seamldr_params *,
+	    if (!IS_ERR_OR_NULL(_T)) free_seamldr_params(_T))
+
 /**
  * seamldr_install_module - Install a new TDX module
  * @data: Pointer to the TDX module update blob. It should be vmalloc'd
@@ -65,6 +212,11 @@ int seamldr_install_module(const u8 *data, u32 size)
 	if (WARN_ON_ONCE(!is_vmalloc_addr(data)))
 		return -EINVAL;
 
+	struct seamldr_params *params __free(free_seamldr_params) =
+						init_seamldr_params(data, size);
+	if (IS_ERR(params))
+		return PTR_ERR(params);
+
 	guard(cpus_read_lock)();
 	if (!cpumask_equal(cpu_online_mask, cpu_present_mask)) {
 		pr_err("Cannot update the TDX Module if any CPU is offline\n");

---

## [12] Chao Gao — 2026-02-12
*Subject: [PATCH v4 11/24] x86/virt/seamldr: Introduce skeleton for TDX Module updates*

TDX Module updates require careful synchronization with other TDX
operations on the host. During updates, only update-related SEAMCALLs are
permitted; all other SEAMCALLs must be blocked.

However, SEAMCALLs can be invoked from different contexts (normal and IRQ
context) and run in parallel across CPUs. And, all TD vCPUs must remain
out of guest mode during updates. No single lock primitive can satisfy
all these synchronization requirements, so stop_machine() is used as the
only well-understood mechanism that can meet them all.

The TDX Module update process consists of several steps as described in
Intel® Trust Domain Extensions (Intel® TDX) Module Base Architecture
Specification, Revision 348549-007, Chapter 4.5 "TD-Preserving TDX Module
Update"

  - shut down the old module
  - install the new module
  - global and per-CPU initialization
  - restore state information

Some steps must execute on a single CPU, others must run serially across
all CPUs, and some can run concurrently on all CPUs. There are also
ordering requirements between steps, so all CPUs must work in a step-locked
manner.

In summary, TDX Module updates create two requirements:

1. The entire update process must use stop_machine() to synchronize with
   other TDX workloads
2. Update steps must be performed in a step-locked manner

To prepare for implementing concrete TDX Module update steps, establish
the framework by mimicking multi_cpu_stop(), which is a good example of
performing a multi-step task in step-locked manner. Specifically, use a
global state machine to control each CPU's work and require all CPUs to
acknowledge completion before proceeding to the next step.

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
---
v2:
 - refine the changlog to follow context-problem-solution structure
 - move alternative discussions at the end of the changelog
 - add a comment about state machine transition
 - Move rcu_momentary_eqs() call to the else branch.
---
 arch/x86/virt/vmx/tdx/seamldr.c | 70 ++++++++++++++++++++++++++++++++-
 1 file changed, 69 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 718cb8396057..21d572d75769 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -10,8 +10,10 @@
 #include <linux/cpuhplock.h>
 #include <linux/cpumask.h>
 #include <linux/mm.h>
+#include <linux/nmi.h>
 #include <linux/slab.h>
 #include <linux/spinlock.h>
+#include <linux/stop_machine.h>
 
 #include <asm/seamldr.h>
 
@@ -186,6 +188,68 @@ static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
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
+		/* Chill out and re-read tdp_data */
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
 
@@ -223,7 +287,11 @@ int seamldr_install_module(const u8 *data, u32 size)
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
 EXPORT_SYMBOL_FOR_MODULES(seamldr_install_module, "tdx-host");

---

## [13] Chao Gao — 2026-02-12
*Subject: [PATCH v4 12/24] x86/virt/seamldr: Abort updates if errors occurred midway*

The TDX Module update process has multiple steps, each of which may
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
---
v3:
 - Instead of fast-forward to the final stage, exit the execution loop
   directly.
---
 arch/x86/virt/vmx/tdx/seamldr.c | 10 ++++++++--
 1 file changed, 8 insertions(+), 2 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 21d572d75769..70bc577e5957 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -202,6 +202,7 @@ enum tdp_state {
 static struct {
 	enum tdp_state state;
 	atomic_t thread_ack;
+	atomic_t failed;
 } tdp_data;
 
 static void set_target_state(enum tdp_state state)
@@ -240,12 +241,16 @@ static int do_seamldr_install_module(void *params)
 			default:
 				break;
 			}
-			ack_state();
+
+			if (ret)
+				atomic_inc(&tdp_data.failed);
+			else
+				ack_state();
 		} else {
 			touch_nmi_watchdog();
 			rcu_momentary_eqs();
 		}
-	} while (curstate != TDP_DONE);
+	} while (curstate != TDP_DONE && !atomic_read(&tdp_data.failed));
 
 	return ret;
 }
@@ -287,6 +292,7 @@ int seamldr_install_module(const u8 *data, u32 size)
 		return -EBUSY;
 	}
 
+	atomic_set(&tdp_data.failed, 0);
 	set_target_state(TDP_START + 1);
 	ret = stop_machine_cpuslocked(do_seamldr_install_module, params, cpu_online_mask);
 	if (ret)

---

## [14] Chao Gao — 2026-02-12
*Subject: [PATCH v4 13/24] x86/virt/seamldr: Shut down the current TDX module*

The first step of TDX Module updates is shutting down the current TDX
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
Extensions (Intel® TDX) Module Base Architecture Specification, Revision
348549-007, Chapter 4.5.3 "Handoff Versioning".

Ideally, the kernel needs to retrieve the handoff versions supported by
the current module and the new module and select a version supported by
both. But, since the Linux kernel only supports module upgrades, simply
request the current module to generate handoff data using its highest
supported version, expecting that the new module will likely support it.

Note that only one CPU needs to call the TDX Module's shutdown API.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
---
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
 arch/x86/virt/vmx/tdx/seamldr.c             | 10 ++++++++++
 arch/x86/virt/vmx/tdx/tdx.c                 | 15 +++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h                 |  3 +++
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c | 15 +++++++++++++++
 5 files changed, 48 insertions(+)

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
index 70bc577e5957..c59cdd5b1fe4 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -18,6 +18,7 @@
 #include <asm/seamldr.h>
 
 #include "seamcall_internal.h"
+#include "tdx.h"
 
 /* P-SEAMLDR SEAMCALL leaf function */
 #define P_SEAMLDR_INFO			0x8000000000000000
@@ -196,6 +197,7 @@ static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
  */
 enum tdp_state {
 	TDP_START,
+	TDP_SHUTDOWN,
 	TDP_DONE,
 };
 
@@ -228,8 +230,12 @@ static void ack_state(void)
 static int do_seamldr_install_module(void *params)
 {
 	enum tdp_state newstate, curstate = TDP_START;
+	int cpu = smp_processor_id();
+	bool primary;
 	int ret = 0;
 
+	primary = cpumask_first(cpu_online_mask) == cpu;
+
 	do {
 		/* Chill out and re-read tdp_data */
 		cpu_relax();
@@ -238,6 +244,10 @@ static int do_seamldr_install_module(void *params)
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
index b65b2a609e81..f911c8c63800 100644
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
+	 * Shut down the TDX Module and prepare handoff data for the next
+	 * TDX Module. This SEAMCALL requires a handoff version. Use the
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
index 4c9917a9c2c3..6aee10c36489 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -100,6 +100,20 @@ static int get_tdx_sys_info_td_conf(struct tdx_sys_info_td_conf *sysinfo_td_conf
 	return ret;
 }
 
+static int get_tdx_sys_info_handoff(struct tdx_sys_info_handoff *sysinfo_handoff)
+{
+	int ret = 0;
+	u64 val;
+
+	if (!tdx_supports_runtime_update(&tdx_sysinfo))
+		return 0;
+
+	if (!ret && !(ret = read_sys_metadata_field(0x8900000100000000, &val)))
+		sysinfo_handoff->module_hv = val;
+
+	return ret;
+}
+
 static int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 {
 	int ret = 0;
@@ -115,6 +129,7 @@ static int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 	ret = ret ?: get_tdx_sys_info_tdmr(&sysinfo->tdmr);
 	ret = ret ?: get_tdx_sys_info_td_ctrl(&sysinfo->td_ctrl);
 	ret = ret ?: get_tdx_sys_info_td_conf(&sysinfo->td_conf);
+	ret = ret ?: get_tdx_sys_info_handoff(&sysinfo->handoff);
 
 	return ret;
 }

---

## [15] Chao Gao — 2026-02-12
*Subject: [PATCH v4 14/24] x86/virt/tdx: Reset software states during TDX Module shutdown*

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
---
 arch/x86/virt/vmx/tdx/tdx.c | 17 ++++++++++++++---
 1 file changed, 14 insertions(+), 3 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index f911c8c63800..a1193efc1156 100644
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
 	 * Shut down the TDX Module and prepare handoff data for the next
@@ -1188,7 +1189,17 @@ int tdx_module_shutdown(void)
 	 * modules as new modules likely have higher handoff version.
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

## [16] Chao Gao — 2026-02-12
*Subject: [PATCH v4 15/24] x86/virt/seamldr: Log TDX Module update failures*

Currently, there is no way to restore a TDX Module from shutdown state to
running state. This means if errors occur after a successful module
shutdown, they are unrecoverable since the old module is gone but the new
module isn't installed. All subsequent SEAMCALLs to the TDX Module will
fail, so TDs will be killed due to SEAMCALL failures.

Log a message to clarify that SEAMCALL errors are expected in this
scenario. This ensures that after update failures, the first message in
dmesg explains the situation rather than showing confusing call traces from
various code paths.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
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
index c59cdd5b1fe4..4e0a98404c7f 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -223,6 +223,11 @@ static void ack_state(void)
 		set_target_state(tdp_data.state + 1);
 }
 
+static void print_update_failure_message(void)
+{
+	pr_err_once("update failed, SEAMCALLs will report failure until TDs killed\n");
+}
+
 /*
  * See multi_cpu_stop() from where this multi-cpu state-machine was
  * adopted, and the rationale for touch_nmi_watchdog()
@@ -252,10 +257,13 @@ static int do_seamldr_install_module(void *params)
 				break;
 			}
 
-			if (ret)
+			if (ret) {
 				atomic_inc(&tdp_data.failed);
-			else
+				if (curstate > TDP_SHUTDOWN)
+					print_update_failure_message();
+			} else {
 				ack_state();
+			}
 		} else {
 			touch_nmi_watchdog();
 			rcu_momentary_eqs();

---

## [17] Chao Gao — 2026-02-12
*Subject: [PATCH v4 16/24] x86/virt/seamldr: Install a new TDX Module*

Following the shutdown of the existing TDX Module, the update process
continues with installing the new module. P-SEAMLDR provides the
SEAMLDR.INSTALL SEAMCALL to perform this installation, which must be
executed serially across all CPUs.

Implement SEAMLDR.INSTALL and execute it on every CPU.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/seamldr.c | 9 ++++++++-
 1 file changed, 8 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 4e0a98404c7f..4537311780b1 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -22,6 +22,7 @@
 
 /* P-SEAMLDR SEAMCALL leaf function */
 #define P_SEAMLDR_INFO			0x8000000000000000
+#define P_SEAMLDR_INSTALL		0x8000000000000001
 
 #define SEAMLDR_MAX_NR_MODULE_4KB_PAGES	496
 #define SEAMLDR_MAX_NR_SIG_4KB_PAGES	4
@@ -198,6 +199,7 @@ static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
 enum tdp_state {
 	TDP_START,
 	TDP_SHUTDOWN,
+	TDP_CPU_INSTALL,
 	TDP_DONE,
 };
 
@@ -232,9 +234,10 @@ static void print_update_failure_message(void)
  * See multi_cpu_stop() from where this multi-cpu state-machine was
  * adopted, and the rationale for touch_nmi_watchdog()
  */
-static int do_seamldr_install_module(void *params)
+static int do_seamldr_install_module(void *seamldr_params)
 {
 	enum tdp_state newstate, curstate = TDP_START;
+	struct tdx_module_args args = {};
 	int cpu = smp_processor_id();
 	bool primary;
 	int ret = 0;
@@ -253,6 +256,10 @@ static int do_seamldr_install_module(void *params)
 				if (primary)
 					ret = tdx_module_shutdown();
 				break;
+			case TDP_CPU_INSTALL:
+				args.rcx = __pa(seamldr_params);
+				ret = seamldr_call(P_SEAMLDR_INSTALL, &args);
+				break;
 			default:
 				break;
 			}

---

## [18] Chao Gao — 2026-02-12
*Subject: [PATCH v4 17/24] x86/virt/seamldr: Do TDX per-CPU initialization after updates*

After installing the new TDX module, each CPU should be initialized
again to make the CPU ready to run any other SEAMCALLs. So, call
tdx_cpu_enable() on all CPUs.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/seamldr.c | 4 ++++
 1 file changed, 4 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 4537311780b1..e29e6094c80b 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -200,6 +200,7 @@ enum tdp_state {
 	TDP_START,
 	TDP_SHUTDOWN,
 	TDP_CPU_INSTALL,
+	TDP_CPU_INIT,
 	TDP_DONE,
 };
 
@@ -260,6 +261,9 @@ static int do_seamldr_install_module(void *seamldr_params)
 				args.rcx = __pa(seamldr_params);
 				ret = seamldr_call(P_SEAMLDR_INSTALL, &args);
 				break;
+			case TDP_CPU_INIT:
+				ret = tdx_cpu_enable();
+				break;
 			default:
 				break;
 			}

---

## [19] Chao Gao — 2026-02-12
*Subject: [PATCH v4 18/24] x86/virt/tdx: Restore TDX Module state*

TDX Module state was packed as handoff data during module shutdown. After
per-CPU initialization, the new module can restore TDX Module state from
handoff data to preserve running TDs.

Once the restoration is done, the TDX Module update is complete, which
means the new module is ready to handle requests from the host and guests.

Implement the new TDH.SYS.UPDATE SEAMCALL to restore TDX Module state
and invoke it for one CPU.

Note that Intel® Trust Domain Extensions (Intel® TDX) Module Base
Architecture Specification, Revision 348549-007, Chapter 4.5.5 states:

  If TDH.SYS.UPDATE returns an error, then the host VMM can continue
  with the non-update sequence (TDH.SYS.CONFIG, 15 TDH.SYS.KEY.CONFIG
  etc.). In this case all existing TDs are lost. Alternatively, the host
  VMM can request the P-SEAMLDR to update to another TDX Module. If that
  update is successful, existing TDs are preserved

The two alternative error handling approaches are not implemented due to
their complexity and unclear benefits.

Also note that the location and the format of handoff data is defined by
the TDX Module. The new module knows where to get handoff data and how
to parse it. The kernel doesn't need to provide its location, format etc.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
---
v3:
 - use seamcall_prerr() rather than raw seamcall() [Binbin]
 - use pr_err() to print error message [Binbin]
---
 arch/x86/virt/vmx/tdx/seamldr.c |  5 +++++
 arch/x86/virt/vmx/tdx/tdx.c     | 16 ++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h     |  2 ++
 3 files changed, 23 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index e29e6094c80b..0ca802234695 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -201,6 +201,7 @@ enum tdp_state {
 	TDP_SHUTDOWN,
 	TDP_CPU_INSTALL,
 	TDP_CPU_INIT,
+	TDP_RUN_UPDATE,
 	TDP_DONE,
 };
 
@@ -264,6 +265,10 @@ static int do_seamldr_install_module(void *seamldr_params)
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
index a1193efc1156..a8adb2c97e2f 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1202,6 +1202,22 @@ int tdx_module_shutdown(void)
 	return 0;
 }
 
+int tdx_module_run_update(void)
+{
+	struct tdx_module_args args = {};
+	int ret;
+
+	ret = seamcall_prerr(TDH_SYS_UPDATE, &args);
+	if (ret) {
+		pr_err("TDX-Module update failed (%d)\n", ret);
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
index 1c4da9540ae0..0887debfd139 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -47,6 +47,7 @@
 #define TDH_VP_WR			43
 #define TDH_SYS_CONFIG			45
 #define TDH_SYS_SHUTDOWN		52
+#define TDH_SYS_UPDATE		53
 
 /*
  * SEAMCALL leaf:
@@ -120,5 +121,6 @@ struct tdmr_info_list {
 };
 
 int tdx_module_shutdown(void);
+int tdx_module_run_update(void);
 
 #endif

---

## [20] Chao Gao — 2026-02-12
*Subject: [PATCH v4 19/24] x86/virt/tdx: Update tdx_sysinfo and check features post-update*

tdx_sysinfo contains all metadata of the active TDX module, including
versions, supported features, and TDMR/TDCS/TDVPS information. These
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

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
---
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
 arch/x86/virt/vmx/tdx/seamldr.c | 11 ++++++++-
 arch/x86/virt/vmx/tdx/tdx.c     | 43 +++++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h     |  3 +++
 3 files changed, 56 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 0ca802234695..3f37cc6c68ff 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -315,6 +315,15 @@ int seamldr_install_module(const u8 *data, u32 size)
 	if (WARN_ON_ONCE(!is_vmalloc_addr(data)))
 		return -EINVAL;
 
+	/*
+	 * Preallocating a tdx_sys_info buffer before updates is to avoid having to
+	 * handle -ENOMEM when updating tdx_sysinfo after a successful update.
+	 */
+	struct tdx_sys_info *sysinfo __free(kfree) = kzalloc(sizeof(*sysinfo),
+							     GFP_KERNEL);
+	if (!sysinfo)
+		return -ENOMEM;
+
 	struct seamldr_params *params __free(free_seamldr_params) =
 						init_seamldr_params(data, size);
 	if (IS_ERR(params))
@@ -332,6 +341,6 @@ int seamldr_install_module(const u8 *data, u32 size)
 	if (ret)
 		return ret;
 
-	return 0;
+	return tdx_module_post_update(sysinfo);
 }
 EXPORT_SYMBOL_FOR_MODULES(seamldr_install_module, "tdx-host");
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index a8adb2c97e2f..3f5edbc33a4f 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1218,6 +1218,49 @@ int tdx_module_run_update(void)
 	return 0;
 }
 
+/*
+ * Update tdx_sysinfo and check if any TDX module features changed after
+ * updates
+ */
+int tdx_module_post_update(struct tdx_sys_info *info)
+{
+	struct tdx_sys_info_version *old, *new;
+	int ret;
+
+	/* Shouldn't fail as the update has succeeded */
+	ret = get_tdx_sys_info(info);
+	if (WARN_ONCE(ret, "version retrieval failed after update, replace TDX Module\n"))
+		return ret;
+
+	old = &tdx_sysinfo.version;
+	new = &info->version;
+	pr_info("version %u.%u.%02u -> %u.%u.%02u\n", old->major_version,
+						      old->minor_version,
+						      old->update_version,
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
+	pr_info("Please consider updating your BIOS to install the TDX Module.\n");
+	return 0;
+}
+
 static bool is_pamt_page(unsigned long phys)
 {
 	struct tdmr_info_list *tdmr_list = &tdx_tdmr_list;
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 0887debfd139..d1807a476d3b 100644
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

## [21] Chao Gao — 2026-02-12
*Subject: [PATCH v4 20/24] x86/virt/tdx: Enable TDX Module runtime updates*

All pieces of TDX Module runtime updates are in place. Enable it if it
is supported.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
---
v4:
 - s/BIT/BIT_ULL [Tony]
---
 arch/x86/include/asm/tdx.h  | 5 ++++-
 arch/x86/virt/vmx/tdx/tdx.h | 3 ---
 2 files changed, 4 insertions(+), 4 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index ffadbf64d0c1..ad62a7be0443 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -32,6 +32,9 @@
 #define TDX_SUCCESS		0ULL
 #define TDX_RND_NO_ENTROPY	0x8000020300000000ULL
 
+/* Bit definitions of TDX_FEATURES0 metadata field */
+#define TDX_FEATURES0_TD_PRESERVING	BIT_ULL(1)
+#define TDX_FEATURES0_NO_RBP_MOD	BIT_ULL(18)
 #ifndef __ASSEMBLER__
 
 #include <uapi/asm/mce.h>
@@ -105,7 +108,7 @@ const struct tdx_sys_info *tdx_get_sysinfo(void);
 
 static inline bool tdx_supports_runtime_update(const struct tdx_sys_info *sysinfo)
 {
-	return false; /* To be enabled when kernel is ready */
+	return sysinfo->features.tdx_features0 & TDX_FEATURES0_TD_PRESERVING;
 }
 
 int tdx_guest_keyid_alloc(void);
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index d1807a476d3b..749f4d74cb2c 100644
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

## [22] Chao Gao — 2026-02-12
*Subject: [PATCH v4 21/24] x86/virt/tdx: Avoid updates during update-sensitive operations*

TDX Module updates may cause TD management operations to fail if they
occur during phases of the TD lifecycle that are sensitive to update
compatibility.

Currently, there are two update-sensitive scenarios:
 - TD build, where TD Measurement Register (TDMR) accumulates over multiple
   TDH.MEM.PAGE.ADD, TDH.MR.EXTEND and TDH.MR.FINALIZE calls.

 - TD migration, where an intermediate crypto state is saved if a state
   migration function (TDH.EXPORT.STATE.* or TDH.IMPORT.STATE.*) is
   interrupted and restored when the function is resumed.

For example, if an update races with TD build operations, the TD
Measurement Register will become incorrect, causing the TD to fail
attestation.

The TDX Module offers two solutions:

1. Avoid updates during update-sensitive times

   The host VMM can instruct TDH.SYS.SHUTDOWN to fail if any of the TDs
   are currently in any update-sensitive cases.

2. Detect incompatibility after updates

   On TDH.SYS.UPDATE, the host VMM can configure the TDX Module to detect
   actual incompatibility cases. The TDX Module will then return a special
   error to signal the incompatibility, allowing the host VMM to restart
   the update-sensitive operations.

Implement option #1 to fail updates if the feature is available. Also,
distinguish this update failure from other failures by returning -EBUSY,
which will be converted to a firmware update error code indicating that the
firmware is busy.

Options like "do nothing" or option #2 are not viable [1] because the
former allows damage to propagate to multiple, potentially unknown
components (adding significant complexity to the whole ecosystem), while
the latter may make existing KVM ioctls unstable.

Based on a reference patch by Vishal [2].

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>
Link: https://lore.kernel.org/linux-coco/aQIbM5m09G0FYTzE@google.com/ # [1]
Link: https://lore.kernel.org/linux-coco/CAGtprH_oR44Vx9Z0cfxvq5-QbyLmy_+Gn3tWm3wzHPmC1nC0eg@mail.gmail.com/ # [2]
---
 arch/x86/include/asm/tdx.h   | 13 +++++++++++--
 arch/x86/kvm/vmx/tdx_errno.h |  2 --
 arch/x86/virt/vmx/tdx/tdx.c  | 23 +++++++++++++++++++----
 3 files changed, 30 insertions(+), 8 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index ad62a7be0443..50a58160deef 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -26,15 +26,19 @@
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
 
 /* Bit definitions of TDX_FEATURES0 metadata field */
 #define TDX_FEATURES0_TD_PRESERVING	BIT_ULL(1)
 #define TDX_FEATURES0_NO_RBP_MOD	BIT_ULL(18)
+#define TDX_FEATURES0_UPDATE_COMPAT	BIT_ULL(47)
 #ifndef __ASSEMBLER__
 
 #include <uapi/asm/mce.h>
@@ -111,6 +115,11 @@ static inline bool tdx_supports_runtime_update(const struct tdx_sys_info *sysinf
 	return sysinfo->features.tdx_features0 & TDX_FEATURES0_TD_PRESERVING;
 }
 
+static inline bool tdx_supports_update_compatibility(const struct tdx_sys_info *sysinfo)
+{
+	return sysinfo->features.tdx_features0 & TDX_FEATURES0_UPDATE_COMPAT;
+}
+
 int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
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
index 3f5edbc33a4f..2cf3a01d0b9c 100644
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
 	 * Shut down the TDX Module and prepare handoff data for the next
@@ -1189,9 +1192,21 @@ int tdx_module_shutdown(void)
 	 * modules as new modules likely have higher handoff version.
 	 */
 	args.rcx = tdx_sysinfo.handoff.module_hv;
-	ret = seamcall_prerr(TDH_SYS_SHUTDOWN, &args);
-	if (ret)
-		return ret;
+
+	if (tdx_supports_update_compatibility(&tdx_sysinfo))
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
+	else if (ret)
+		return -EIO;
 
 	tdx_module_status = TDX_MODULE_UNINITIALIZED;
 	sysinit_done = false;

---

## [23] Chao Gao — 2026-02-12
*Subject: [PATCH v4 22/24] coco/tdx-host: Document TDX Module update expectations*

The TDX Module update protocol facilitates compatible runtime updates.

Document the compatibility criteria and indicators of various update
failures, including violations of the compatibility criteria.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Dan Williams <dan.j.williams@intel.com>
---
v4
 - Drop "compat_capable" kernel ABI [Dan]
 - Document Linux compatibility expectations and results of violating
   them [Dan]
---
 .../ABI/testing/sysfs-devices-faux-tdx-host   | 53 +++++++++++++++++++
 1 file changed, 53 insertions(+)

diff --git a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
index 88a9c0b2bdfe..fefe762998db 100644
--- a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
+++ b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
@@ -27,3 +27,56 @@ Description:	(RO) Report the number of remaining updates. TDX maintains a
 		Interface Specification, Revision 343755-003, Chapter 3.3
 		"SEAMLDR_INFO" and Chapter 4.2 "SEAMLDR.INSTALL" for more
 		information.
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
+		compatibility check failures and how to prevent them.
+
+What:		/sys/devices/faux/tdx_host/firmware/tdx_module/error
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) See Documentation/ABI/testing/sysfs-class-firmware for
+		baseline expectations for this file. The <ERROR> part in the
+		<STATUS>:<ERROR> format can be:
+
+		   "device-busy": Compatibility checks failed or not all CPUs
+		                  are online
+
+		   "flash-wearout": The number of updates reached the limit.
+
+		   "read-write-error": Memory allocation failed.
+
+		   "hw-error": Cannot communicate with P-SEAMLDR or TDX Module.
+
+		   "firmware-invalid": The provided TDX Module update is invalid
+		                       or other unexpected errors occurred.
+
+		"hw-error" or "firmware-invalid" may be fatal, causing all TDs
+		and the TDX Module to be lost and preventing further TDX
+		operations. This occurs when reading
+		/sys/devices/faux/tdx_host/version returns -ENXIO. For other
+		errors, TDs and the (previous) TDX Module stay running.
+
+		See tdxctl [1] documentation for how to detect compatible
+		updates and whether the current platform components catch errors
+		or let them leak and cause potential TD attestation failures.
+		[1]: <TBD - tdxctl link>

---

## [24] Chao Gao — 2026-02-12
*Subject: [PATCH v4 23/24] x86/virt/tdx: Document TDX Module updates*

Document TDX Module updates as a subsection of "TDX Host Kernel Support" to
provide background information and cover key points that developers and
users may need to know, for example:

 - update is done in stop_machine() context
 - update instructions and results
 - update policy and tooling

Signed-off-by: Chao Gao <chao.gao@intel.com>
---
 Documentation/arch/x86/tdx.rst | 34 ++++++++++++++++++++++++++++++++++
 1 file changed, 34 insertions(+)

diff --git a/Documentation/arch/x86/tdx.rst b/Documentation/arch/x86/tdx.rst
index 61670e7df2f7..01ae560c7f66 100644
--- a/Documentation/arch/x86/tdx.rst
+++ b/Documentation/arch/x86/tdx.rst
@@ -99,6 +99,40 @@ initialize::
 
   [..] virt/tdx: module initialization failed ...
 
+TDX Module Runtime Updates
+--------------------------
+
+The TDX architecture includes a persistent SEAM loader (P-SEAMLDR) that
+runs in SEAM mode separately from the TDX Module. The kernel can
+communicate with P-SEAMLDR to perform runtime updates of the TDX Module.
+
+During updates, the TDX Module becomes unresponsive to other TDX
+operations. To prevent components using TDX (such as KVM) from experiencing
+unexpected errors during updates, updates are performed in stop_machine()
+context.
+
+TDX Module updates have complex compatibility requirements; the new module
+must be compatible with the current CPU, P-SEAMLDR, and running TDX Module.
+Rather than implementing complex module selection and policy enforcement
+logic in the kernel, userspace is responsible for auditing and selecting
+appropriate updates.
+
+Updates use the standard firmware upload interface. See
+Documentation/driver-api/firmware/fw_upload.rst for detailed instructions
+
+Successful updates are logged in dmesg:
+  [..] virt/tdx: version 1.5.20 -> 1.5.24
+
+If updates failed, running TDs may be killed and further TDX operations may
+be not possible until reboot. For detailed error information, see
+Documentation/ABI/testing/sysfs-devices-faux-tdx-host.
+
+Given the risk of losing existing TDs, userspace should verify that the update
+is compatible with the current system and properly validated before applying it.
+A reference userspace tool that implements necessary checks is available at:
+
+  https://github.com/intel/confidential-computing.tdx.tdx-module.binaries
+
 TDX Interaction to Other Kernel Components
 ------------------------------------------

---

## [25] Chao Gao — 2026-02-12
*Subject: [PATCH v4 24/24] [NOT-FOR-REVIEW] x86/virt/seamldr: Save and restore current VMCS*

P-SEAMLDR calls clobber the current VMCS as documented in Intel® Trust
Domain CPU Architectural Extensions (May 2021 edition) Chapter 2.3 [1]:

  SEAMRET from the P-SEAMLDR clears the current VMCS structure pointed
  to by the current-VMCS pointer. A VMM that invokes the P-SEAMLDR using
  SEAMCALL must reload the current-VMCS, if required, using the VMPTRLD
  instruction.

Save and restore the current VMCS using VMPTRST and VMPTRLD instructions
to avoid breaking KVM.

Signed-off-by: Chao Gao <chao.gao@intel.com>
---
This patch is needed for testing until microcode is updated to preserve
the current VMCS across P-SEAMLDR calls. Otherwise, if some normal VMs
are running before TDX Module updates, vmread/vmwrite errors may occur
immediately after updates.
---
 arch/x86/include/asm/special_insns.h | 22 ++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/seamldr.c      | 16 +++++++++++++++-
 2 files changed, 37 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/special_insns.h b/arch/x86/include/asm/special_insns.h
index 46aa2c9c1bda..a3e9a139b669 100644
--- a/arch/x86/include/asm/special_insns.h
+++ b/arch/x86/include/asm/special_insns.h
@@ -303,6 +303,28 @@ static __always_inline void tile_release(void)
 	asm volatile(".byte 0xc4, 0xe2, 0x78, 0x49, 0xc0");
 }
 
+static inline int vmptrst(u64 *vmcs_pa)
+{
+	asm goto("1: vmptrst %0\n\t"
+		 _ASM_EXTABLE(1b, %l[error])
+		 : "=m" (*vmcs_pa) : : "cc" : error);
+
+	return 0;
+error:
+	return -EIO;
+}
+
+static inline int vmptrld(u64 vmcs_pa)
+{
+	asm goto("1: vmptrld %0\n\t"
+		 "jna %l[error]\n\t"
+		 _ASM_EXTABLE(1b, %l[error])
+		 : : "m" (vmcs_pa) : "cc" : error);
+	return 0;
+error:
+	return -EIO;
+}
+
 #endif /* __KERNEL__ */
 
 #endif /* _ASM_X86_SPECIAL_INSNS_H */
diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 3f37cc6c68ff..02695307b8a0 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -16,6 +16,7 @@
 #include <linux/stop_machine.h>
 
 #include <asm/seamldr.h>
+#include <asm/special_insns.h>
 
 #include "seamcall_internal.h"
 #include "tdx.h"
@@ -59,12 +60,25 @@ static DEFINE_RAW_SPINLOCK(seamldr_lock);
 
 static int seamldr_call(u64 fn, struct tdx_module_args *args)
 {
+	u64 current_vmcs = -1ULL;
+	int ret;
+
 	/*
 	 * Serialize P-SEAMLDR calls and disable interrupts as the calls
 	 * can be made from IRQ context.
 	 */
 	guard(raw_spinlock_irqsave)(&seamldr_lock);
-	return seamcall_prerr(fn, args);
+
+	/*
+	 * P-SEAMLDR calls clobber the current VMCS. Save and restore it.
+	 * -1 indicates invalid VMCS and no restoration is needed.
+	 */
+	WARN_ON_ONCE(vmptrst(&current_vmcs));
+	ret = seamcall_prerr(fn, args);
+	if (current_vmcs != -1ULL)
+		WARN_ON_ONCE(vmptrld(current_vmcs));
+
+	return ret;
 }
 
 int seamldr_get_info(struct seamldr_info *seamldr_info)

---

## [26] Chao Gao — 2026-02-12
*Subject: Re: [PATCH v4 00/24] Runtime TDX Module update support*

On Thu, Feb 12, 2026 at 06:35:03AM -0800, Chao Gao wrote:
>
>Note that like v3, this v4 is not based on Sean's VMXON series to make this

There are some conflicts between Sean's VMXON v2 and this TDX module update series:

1. tdx_cpu_enable() is unexported in the VMXON series but used in this series.
2. tdx_module_status is removed in the VMXON series but accessed in this series.
3. Several functions are tagged as __init but called in this series at runtime

Below is a sample diff showing how to resolve the conflicts. This series is not
ready for merge yet. The diff is posted just to give you a sense of how these
two series intersect:

diff --cc arch/x86/include/asm/tdx.h
index a149740b24e8,50a58160deef..000000000000
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@@ -97,57 -104,22 +104,21 @@@ static inline long tdx_kvm_hypercall(un
  #endif /* CONFIG_INTEL_TDX_GUEST && CONFIG_KVM_GUEST */
  
  #ifdef CONFIG_INTEL_TDX_HOST
- u64 __seamcall(u64 fn, struct tdx_module_args *args);
- u64 __seamcall_ret(u64 fn, struct tdx_module_args *args);
- u64 __seamcall_saved_ret(u64 fn, struct tdx_module_args *args);
  void tdx_init(void);
+ int tdx_cpu_enable(void);
 -int tdx_enable(void);
+ const char *tdx_dump_mce_info(struct mce *m);
+ const struct tdx_sys_info *tdx_get_sysinfo(void);
  
- #include <linux/preempt.h>
- #include <asm/archrandom.h>
- #include <asm/processor.h>
- 
- typedef u64 (*sc_func_t)(u64 fn, struct tdx_module_args *args);
- 
- static __always_inline u64 __seamcall_dirty_cache(sc_func_t func, u64 fn,
-						  struct tdx_module_args *args)
+ static inline bool tdx_supports_runtime_update(const struct tdx_sys_info *sysinfo)
  {
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
+	return sysinfo->features.tdx_features0 & TDX_FEATURES0_TD_PRESERVING;
  }
  
- static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
-			   struct tdx_module_args *args)
+ static inline bool tdx_supports_update_compatibility(const struct tdx_sys_info *sysinfo)
  {
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
+	return sysinfo->features.tdx_features0 & TDX_FEATURES0_UPDATE_COMPAT;
  }
  
- #define seamcall(_fn, _args)		sc_retry(__seamcall, (_fn), (_args))
- #define seamcall_ret(_fn, _args)	sc_retry(__seamcall_ret, (_fn), (_args))
- #define seamcall_saved_ret(_fn, _args)	sc_retry(__seamcall_saved_ret, (_fn), (_args))
- const char *tdx_dump_mce_info(struct mce *m);
- const struct tdx_sys_info *tdx_get_sysinfo(void);
- 
  int tdx_guest_keyid_alloc(void);
  u32 tdx_get_nr_guest_keyids(void);
  void tdx_guest_keyid_free(unsigned int keyid);
diff --cc arch/x86/virt/vmx/tdx/tdx.c
index 55d3463e0e93,2cf3a01d0b9c..000000000000
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@@ -40,7 -39,8 +40,9 @@@
  #include <asm/cpu_device_id.h>
  #include <asm/processor.h>
  #include <asm/mce.h>
 +#include <asm/virt.h>
+ 
+ #include "seamcall_internal.h"
  #include "tdx.h"
  
  static u32 tdx_global_keyid __ro_after_init;
@@@ -53,57 -53,16 +55,15 @@@ static DEFINE_PER_CPU(bool, tdx_lp_init
  
  static struct tdmr_info_list tdx_tdmr_list;
  
 -static enum tdx_module_status_t tdx_module_status;
 -static DEFINE_MUTEX(tdx_module_lock);
+ static bool sysinit_done;
+ static int sysinit_ret;
+ 
  /* All TDX-usable memory regions.  Protected by mem_hotplug_lock. */
  static LIST_HEAD(tdx_memlist);
  
 -static struct tdx_sys_info tdx_sysinfo;
 +static struct tdx_sys_info tdx_sysinfo __ro_after_init;
 +static bool tdx_module_initialized __ro_after_init;
  
- typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);
- 
- static inline void seamcall_err(u64 fn, u64 err, struct tdx_module_args *args)
- {
-	pr_err("SEAMCALL (0x%016llx) failed: 0x%016llx\n", fn, err);
- }
- 
- static inline void seamcall_err_ret(u64 fn, u64 err,
-				    struct tdx_module_args *args)
- {
-	seamcall_err(fn, err, args);
-	pr_err("RCX 0x%016llx RDX 0x%016llx R08 0x%016llx\n",
-			args->rcx, args->rdx, args->r8);
-	pr_err("R09 0x%016llx R10 0x%016llx R11 0x%016llx\n",
-			args->r9, args->r10, args->r11);
- }
- 
- static __always_inline int sc_retry_prerr(sc_func_t func,
-					  sc_err_func_t err_func,
-					  u64 fn, struct tdx_module_args *args)
- {
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
- }
- 
- #define seamcall_prerr(__fn, __args)						\
-	sc_retry_prerr(__seamcall, seamcall_err, (__fn), (__args))
- 
- #define seamcall_prerr_ret(__fn, __args)					\
-	sc_retry_prerr(__seamcall_ret, seamcall_err_ret, (__fn), (__args))
- 
  /*
   * Do the module global initialization once and return its result.
   * It can be done on any cpu.  It's always called with interrupts
@@@ -142,11 -99,17 +100,11 @@@ out
  }
  
  /**
 - * tdx_cpu_enable - Enable TDX on local cpu
 - *
 - * Do one-time TDX module per-cpu initialization SEAMCALL (and TDX module
 - * global initialization SEAMCALL if not done) on local cpu to make this
 - * cpu be ready to run any other SEAMCALLs.
 - *
 - * Always call this function via IPI function calls.
 - *
 - * Return 0 on success, otherwise errors.
 + * Enable VMXON and then do one-time TDX module per-cpu initialization SEAMCALL
 + * (and TDX module global initialization SEAMCALL if not done) on local cpu to
 + * make this cpu be ready to run any other SEAMCALLs.
   */
- static int tdx_cpu_enable(void)
+ int tdx_cpu_enable(void)
  {
	struct tdx_module_args args = {};
	int ret;
@@@ -1236,51 -1114,168 +1194,150 @@@ err_free_tdxmem
	goto out_put_tdxmem;
  }
  
 -static int __tdx_enable(void)
 +static __init int tdx_enable(void)
  {
 +	enum cpuhp_state state;
	int ret;
  
 -	ret = init_tdx_module();
 -	if (ret) {
 -		pr_err("module initialization failed (%d)\n", ret);
 -		tdx_module_status = TDX_MODULE_ERROR;
 -		return ret;
 +	if (!cpu_feature_enabled(X86_FEATURE_TDX_HOST_PLATFORM)) {
 +		pr_err("TDX not supported by the host platform\n");
 +		return -ENODEV;
	}
  
 -	pr_info("module initialized\n");
 -	tdx_module_status = TDX_MODULE_INITIALIZED;
 -
 -	return 0;
 -}
 +	if (!cpu_feature_enabled(X86_FEATURE_XSAVE)) {
 +		pr_err("XSAVE is required for TDX\n");
 +		return -EINVAL;
 +	}
  
 -/**
 - * tdx_enable - Enable TDX module to make it ready to run TDX guests
 - *
 - * This function assumes the caller has: 1) held read lock of CPU hotplug
 - * lock to prevent any new cpu from becoming online; 2) done both VMXON
 - * and tdx_cpu_enable() on all online cpus.
 - *
 - * This function requires there's at least one online cpu for each CPU
 - * package to succeed.
 - *
 - * This function can be called in parallel by multiple callers.
 - *
 - * Return 0 if TDX is enabled successfully, otherwise error.
 - */
 -int tdx_enable(void)
 -{
 -	int ret;
 +	if (!cpu_feature_enabled(X86_FEATURE_MOVDIR64B)) {
 +		pr_err("MOVDIR64B is required for TDX\n");
 +		return -EINVAL;
 +	}
  
 -	if (!boot_cpu_has(X86_FEATURE_TDX_HOST_PLATFORM))
 +	if (!cpu_feature_enabled(X86_FEATURE_SELFSNOOP)) {
 +		pr_err("Self-snoop is required for TDX\n");
		return -ENODEV;
 +	}
  
 -	lockdep_assert_cpus_held();
 -
 -	mutex_lock(&tdx_module_lock);
 +	state = cpuhp_setup_state(CPUHP_AP_ONLINE_DYN, "virt/tdx:online",
 +				  tdx_online_cpu, tdx_offline_cpu);
 +	if (state < 0)
 +		return state;
  
 -	switch (tdx_module_status) {
 -	case TDX_MODULE_UNINITIALIZED:
 -		ret = __tdx_enable();
 -		break;
 -	case TDX_MODULE_INITIALIZED:
 -		/* Already initialized, great, tell the caller. */
 -		ret = 0;
 -		break;
 -	default:
 -		/* Failed to initialize in the previous attempts */
 -		ret = -EINVAL;
 -		break;
 +	ret = init_tdx_module();
 +	if (ret) {
 +		pr_err("TDX-Module initialization failed (%d)\n", ret);
 +		cpuhp_remove_state(state);
 +		return ret;
	}
  
 -	mutex_unlock(&tdx_module_lock);
 +	register_syscore(&tdx_syscore);
  
 -	return ret;
 +	tdx_module_initialized = true;
 +	pr_info("TDX-Module initialized\n");
 +	return 0;
  }
 -EXPORT_SYMBOL_FOR_KVM(tdx_enable);
 +subsys_initcall(tdx_enable);
  
+ #define TDX_SYS_SHUTDOWN_AVOID_COMPAT_SENSITIVE BIT(16)
+ 
+ int tdx_module_shutdown(void)
+ {
+	struct tdx_module_args args = {};
+	u64 ret;
+	int cpu;
+ 
+	/*
+	 * Shut down the TDX Module and prepare handoff data for the next
+	 * TDX Module. This SEAMCALL requires a handoff version. Use the
+	 * module's handoff version, as it is the highest version the
+	 * module can produce and is more likely to be supported by new
+	 * modules as new modules likely have higher handoff version.
+	 */
+	args.rcx = tdx_sysinfo.handoff.module_hv;
+ 
+	if (tdx_supports_update_compatibility(&tdx_sysinfo))
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
+	else if (ret)
+		return -EIO;
+ 
 -	tdx_module_status = TDX_MODULE_UNINITIALIZED;
++	tdx_module_initialized = false;
+	sysinit_done = false;
+	sysinit_ret = 0;
+ 
+	for_each_online_cpu(cpu)
+		per_cpu(tdx_lp_initialized, cpu) = false;
+	return 0;
+ }
+ 
+ int tdx_module_run_update(void)
+ {
+	struct tdx_module_args args = {};
+	int ret;
+ 
+	ret = seamcall_prerr(TDH_SYS_UPDATE, &args);
+	if (ret) {
+		pr_err("TDX-Module update failed (%d)\n", ret);
 -		tdx_module_status = TDX_MODULE_ERROR;
+		return ret;
+	}
+ 
 -	tdx_module_status = TDX_MODULE_INITIALIZED;
++	tdx_module_initialized = true;
+	return 0;
+ }
+ 
+ /*
+  * Update tdx_sysinfo and check if any TDX module features changed after
+  * updates
+  */
+ int tdx_module_post_update(struct tdx_sys_info *info)
+ {
+	struct tdx_sys_info_version *old, *new;
+	int ret;
+ 
+	/* Shouldn't fail as the update has succeeded */
+	ret = get_tdx_sys_info(info);
+	if (WARN_ONCE(ret, "version retrieval failed after update, replace TDX Module\n"))
+		return ret;
+ 
+	old = &tdx_sysinfo.version;
+	new = &info->version;
+	pr_info("version %u.%u.%02u -> %u.%u.%02u\n", old->major_version,
+						      old->minor_version,
+						      old->update_version,
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
+	pr_info("Please consider updating your BIOS to install the TDX Module.\n");
+	return 0;
+ }
+ 
  static bool is_pamt_page(unsigned long phys)
  {
	struct tdmr_info_list *tdmr_list = &tdx_tdmr_list;
@@@ -1530,12 -1525,17 +1587,12 @@@ void __init tdx_init(void
  
  const struct tdx_sys_info *tdx_get_sysinfo(void)
  {
 -	const struct tdx_sys_info *p = NULL;
 -
 -	/* Make sure all fields in @tdx_sysinfo have been populated */
 -	mutex_lock(&tdx_module_lock);
 -	if (tdx_module_status == TDX_MODULE_INITIALIZED)
 -		p = (const struct tdx_sys_info *)&tdx_sysinfo;
 -	mutex_unlock(&tdx_module_lock);
 +	if (!tdx_module_initialized)
 +		return NULL;
  
 -	return p;
 +	return (const struct tdx_sys_info *)&tdx_sysinfo;
  }
- EXPORT_SYMBOL_FOR_KVM(tdx_get_sysinfo);
+ EXPORT_SYMBOL_FOR_MODULES(tdx_get_sysinfo, "kvm-intel,tdx-host");
  
  u32 tdx_get_nr_guest_keyids(void)
  {
diff --cc arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index c7db393a9cfb,6aee10c36489..000000000000
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c

---

## [27] dan.j.williams@intel.com — 2026-02-12
*Subject: Re: [PATCH v4 22/24] coco/tdx-host: Document TDX Module update
 expectations*

Chao Gao wrote:
> The TDX Module update protocol facilitates compatible runtime updates.
> 
[..]
> +
> +		See tdxctl [1] documentation for how to detect compatible

Delete this paragraph. Do not carry dead documentation in the tree. You
might clarify in the changelog that until tooling arrives it is an
"update at your own risk" scenario in terms of encountering incompatible
updates.  Otherwise, no point in documenting tdxctl vaporware in the
tree.

---

## [28] Huang, Kai — 2026-02-19
*Subject: Re: [PATCH v4 10/24] x86/virt/seamldr: Allocate and populate a module
 update request*

On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
> P-SEAMLDR uses the SEAMLDR_PARAMS structure to describe TDX Module
> update requests. This structure contains physical addresses pointing to

Nit:

This sounds like the kernel can validate but chooses not to.  But I thought
the fact is the kernel cannot validate because there's no P-SEAMLDR ABI to
enumerate such compatibility?

> userspace must ensure the P-SEAMLDR version is
> compatible with the selected TDX Module by checking the minimum

Nit:

As mentioned in v3, can the link be considered as "stable", e.g., won't
disappear couple of years later?

Not sure we should just have a documentation patch for 'tdx_blob' layout.  I
suspect the content won't be changed in the future anyway, at least for
foreseeable future, given you have already updated the sigstruct part.

We can include the links to the actual doc too, and if necessarily, point
out the links may get updated in the future.  We can actually update the
links if they are in some doc.

[...]

> +/*
> + * Intel TDX Module blob. Its format is defined at:

Nit:

It appeared you said you will s/resv/rsvd in v3.

I don't quite mind if other people are fine with 'resv'.  Or you can spell
out 'reserved' in full to match the one in 'struct seamldr_params' above.

Up to you.

The rest LGTM.

---

## [29] Huang, Kai — 2026-02-20
*Subject: Re: [PATCH v4 02/24] coco/tdx-host: Introduce a "tdx_host" device*

> 
> A faux device is used as for TDX because the TDX module is singular within
			^
"as" should be removed.

> the system and lacks associated platform resources. Using a faux device
> eliminates the need to create a stub bus.

Reviewed-by: Kai Huang <kai.huang@intel.com>

A nit below ..


[...]

> +config TDX_HOST_SERVICES
> +	tristate "TDX Host Services Driver"

.. Missing period at the end of the last sentence.

---

## [30] Huang, Kai — 2026-02-20
*Subject: Re: [PATCH v4 03/24] coco/tdx-host: Expose TDX Module version*

On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
> For TDX Module updates, userspace needs to select compatible update
> versions based on the current module version. This design delegates

This "faux device + device attribute" approach seems to be a wider design
choice instead of how to expose module version (which is the scope of this
patch).  Overall, shouldn't this be in the changelog of the previous patch
which actually introduces "faux device" (albeit no attribute is introduced
in that patch)?
 
> 
> 1. AMD SEV leverages an existing PCI device for the PSP to expose

E.g., this sounds to justify "why to use faux device for TDX", but not "to
expose module version via faux device attributes".

> 
> 2. Microcode uses per-CPU virtual devices to report microcode revisions

This is related to exposing module version, but to me "there's only a single
TDX module" is also more like a justification to use "one faux device",
which should belong to changelog of previous patch too.

With "there's only a single TDX module" being said in previous patch
changelog, I think we can safely deduce that there's only "one module
version" but not per-cpu (thus I don't think we even need to call this out
in _this_ patch).

> 
> 3. ARM's CCA implementation isn't in-tree yet, but will likely follow a

Again, I don't feel "follow a similar faux device approach" for ARM CCA
should be a justification of "exposing module version via faux attributes".
It should be a justification of "using faux device for TDX".

> 
> Signed-off-by: Chao Gao <chao.gao@intel.com>

[...]

> +Description:	(RO) Report the version of the loaded TDX Module. The TDX Module
> +		version is formatted as x.y.z, where "x" is the major version,
							       ^

Nit: No need to use "and" before "etc".

Consulting google:

  No, it is not correct to say or write "and etc." Because etc. is an 
  abbreviation for the Latin phrase et cetera, which translates to "and
  other things" or "and the rest," including "and" makes the phrase 
  redundant. Using "and etc." is equivalent to saying "and and the rest".


> diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
> index c77885392b09..0424933b2560 100644

[...]

The actual code LGTM.

---

## [31] Huang, Kai — 2026-02-20
*Subject: Re: [PATCH v4 04/24] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
> The TDX architecture uses the "SEAMCALL" instruction to communicate with
> SEAM mode software. Right now, the only SEAM mode software that the kernel

[...]

> the kernel does not interact with it.

Nit:

Again, to me this only describes what does the kernel do today.  It doesn't
describe what the kernel needs to do for runtime updating.

Maybe it can just be something like:

  The kernel does not need to interact with it for runtime update.

But I don't know why do you even need to talk about NP-SEAMLDR.

> 
> For details of P-SEAMLDR SEAMCALLs, see Intel® Trust Domain CPU

[...]

> + * Serialize P-SEAMLDR calls since the hardware only allows a single CPU to
> + * interact with P-SEAMLDR simultaneously.

Why do you need to disable IRQ?  A plain raw_spinlock should work with both
cases where seamldr_call() is called from IRQ disabled context and normal
task context? 

> +	return seamcall_prerr(fn, args);
> +}

---

## [32] Huang, Kai — 2026-02-20
*Subject: Re: [PATCH v4 05/24] x86/virt/seamldr: Retrieve P-SEAMLDR information*

> +int seamldr_get_info(struct seamldr_info *seamldr_info)
> +{

Should we have a comment for slow_virt_to_phys()?  This patch alone doesn't
really tell where is the memory from.

Btw, it it were me, I would just merge this patch with the next one.  Then
it's clear the memory comes from tdx-host module's stack.  The merged patch
won't be too big to review either (IMHO).  You can then have this
seamldr_get_info() and its user together in one patch, with one changelog to
tell the full story.

But just my 2cents, feel free to ignore. 

> +
> +	return seamldr_call(P_SEAMLDR_INFO, &args);

---

## [33] Huang, Kai — 2026-02-23
*Subject: Re: [PATCH v4 21/24] x86/virt/tdx: Avoid updates during
 update-sensitive operations*

> 
> The TDX Module offers two solutions:

[...]

>  
> +#define TDX_SYS_SHUTDOWN_AVOID_COMPAT_SENSITIVE BIT(16)

The changelog says "doing nothing" isn't an option, and we need to depend on
TDH.SYS.SHUTDOWN to catch such incompatibilities.

To me this means we cannot support module update if TDH.SYS.SHUTDOWN doesn't
support this "AVOID_COMPAT_SENSITIVE" feature, because w/o it we cannot tell
whether the update is happening during any sensitive operation.

But the code above proceeds to TDH.SYS.SHUTDOWN anyway when this feature
isn't supported.  I don't think we should do that?

---

## [34] Huang, Kai — 2026-02-23
*Subject: Re: [PATCH v4 20/24] x86/virt/tdx: Enable TDX Module runtime updates*

On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
> All pieces of TDX Module runtime updates are in place. Enable it if it
> is supported.

Nit:

Strictly speaking, moving this "NO_RBP_MOD" isn't required to "enable TDX
module runtime updates".  So I think it's better to call out in changelog
that this is trying to centralize the bit definitions.

Anyway, I think we have multiple series doing this so I guess things will
just sort out eventually.

---

## [35] Huang, Kai — 2026-02-23
*Subject: Re: [PATCH v4 11/24] x86/virt/seamldr: Introduce skeleton for TDX
 Module updates*

>  
> +/*

Nit:  start from TDP_START or TDP_START + 1 ?

The code below says:

+	set_target_state(TDP_START + 1);
+	ret = stop_machine_cpuslocked(do_seamldr_install_module, params,
cpu_online_mask);

> + * to TDP_DONE. Each state is associated with certain work. For some
> + * states, just one CPU needs to perform the work, while other CPUs just

Nit:  just curious, what does "TDP" mean?

Maybe something more obvious?

> +
> +static struct {

Nit:  perhaps add "so that ..." part to the comment?

> +	smp_wmb();
> +	WRITE_ONCE(tdp_data.state, state);

Nit:  add a period to the end of the sentence.

(btw, I found using period or not isn't consistent even among the 'one-line-
sentence' comments, maybe you want to make that consistent.)

---

## [36] Chao Gao — 2026-02-24
*Subject: Re: [PATCH v4 02/24] coco/tdx-host: Introduce a "tdx_host" device*

On Fri, Feb 20, 2026 at 08:15:20AM +0800, Huang, Kai wrote:
>> 
>> A faux device is used as for TDX because the TDX module is singular within

Sure. Will fix this.

>
>> the system and lacks associated platform resources. Using a faux device

Thanks.

>
>A nit below ..

Will do and apply this to the whole series.

---

## [37] Chao Gao — 2026-02-24
*Subject: Re: [PATCH v4 03/24] coco/tdx-host: Expose TDX Module version*

On Fri, Feb 20, 2026 at 08:40:13AM +0800, Huang, Kai wrote:
>On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
>> For TDX Module updates, userspace needs to select compatible update

Yes, it's mentioned briefly in the previous patch:

"""
Create a virtual device not only to align with other implementations but
also to make it easier to

 - expose metadata (e.g., TDX module version, seamldr version etc) to
   the userspace as device attributes

 ...
"""

The previous patch doesn't provide details for version information
exposure, as version attributes are just one of several purposes for the
virtual device.

> 
>> 

This provides additional context as suggested by Dave:

https://lore.kernel.org/kvm/aa3f026b-ad69-4070-8433-8950e5250edb@intel.com/

Dave asked:

"""
What are other CPU vendors doing for this? SEV? CCA? S390? How are their
firmware versions exposed? What about other things in the Intel world
like CPU microcode or the billion other chunks of firmware? ...
"""

>
>> 

The previous patch already includes this justification:

"""
A faux device is used as for TDX because the TDX module is singular within
the system ...
"""

>
>With "there's only a single TDX module" being said in previous patch

Agreed. I repeated this information here under "== Background ==" to give
broader context for the overall approach.

>
>> 

Thanks. Will fix this.

---

## [38] Chao Gao — 2026-02-24
*Subject: Re: [PATCH v4 04/24] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On Fri, Feb 20, 2026 at 09:12:29AM +0800, Huang, Kai wrote:
>On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
>> The TDX architecture uses the "SEAMCALL" instruction to communicate with

I am fine with this. Will do.

>
>But I don't know why do you even need to talk about NP-SEAMLDR.

I included this because Dave had some confusion about NP-SEAMLDR [1], so I
wanted to clarify it.

[1]: https://lore.kernel.org/kvm/aXt0+lRvpvf5knKP@intel.com/

And, since NP-SEAMLDR and P-SEAMLDR have similar names, I thought it would be
helpful to clarify the difference. This follows Dave's earlier suggestion to
explain SEAM_INFO and SEAM_SEAMINFO SEAMCALLs for clarity [2].

[2]: https://lore.kernel.org/kvm/b2e2fd5e-8aff-4eda-a648-9ae9f8234d25@intel.com/

>
>> 

No, that's not safe. Without _irqsave, a deadlock can occur if an interrupt
fires while a task context already holds the lock, and the interrupt handler
also tries to acquire the same lock.

>
>> +	return seamcall_prerr(fn, args);

---

## [39] Chao Gao — 2026-02-24
*Subject: Re: [PATCH v4 05/24] x86/virt/seamldr: Retrieve P-SEAMLDR information*

On Fri, Feb 20, 2026 at 05:36:33PM +0800, Huang, Kai wrote:
>
>> +int seamldr_get_info(struct seamldr_info *seamldr_info)

How about:

	/*
	 * Use slow_virt_to_phys() since @seamldr_info may be allocated on
	 * the stack.
	 */

I was hesitant to add a comment since most existing slow_virt_to_phys() usage
lacks comments.


>
>Btw, it it were me, I would just merge this patch with the next one.  Then

I'm fine with this. But let's see what others think about merging the patches.

>
>> +

---

## [40] Chao Gao — 2026-02-24
*Subject: Re: [PATCH v4 10/24] x86/virt/seamldr: Allocate and populate a
 module update request*

On Fri, Feb 20, 2026 at 06:31:24AM +0800, Huang, Kai wrote:
>On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
>> P-SEAMLDR uses the SEAMLDR_PARAMS structure to describe TDX Module

Emm, the kernel could validate this by parsing mapping_file.json, but the
complexity wouldn't be worth it.

>
>> userspace must ensure the P-SEAMLDR version is

I'm not sure when this link will be outdated, but we'll definitely have a TDX
Module release repository with a blob_structure.txt file describing the format.

>
>Not sure we should just have a documentation patch for 'tdx_blob' layout.  I

Regarding the documentation patch, I don't see the value in adding one. It
would just mirror the code and become outdated when 'tdx_blob' layout is
updated.

If the concern is that tdx_blob layout changes could cause incompatibilities,
that's not the kernel's responsibility to prevent; the kernel has no control
over external format changes.

If the issue is simply that links may become outdated, that's a common problem.
We can address this by referring to blob_structure.txt in the "Intel TDX Module
Binaries Repository" and dropping the specific link. For example:

  TDX Modules are distributed in the tdx_blob format defined in
  blob_structure.txt from the "Intel TDX Module Binaries Repository". A
  tdx_blob contains a header, sigstruct, and module binary. This is also the
  format supplied by the userspace to the kernel.

>
>[...]

I will drop this link as well.

>> + *
>> + * Note this structure differs from the reference above: the two variable-length

Sorry, I missed this feedback. I'll use "reserved".

I even updated "len" to "length" and changed the index to start from 0 (to match
blob_structure.txt) but somehow missed updating "resv."

---

## [41] Chao Gao — 2026-02-24
*Subject: Re: [PATCH v4 11/24] x86/virt/seamldr: Introduce skeleton for TDX
 Module updates*

On Mon, Feb 23, 2026 at 05:25:53PM +0800, Huang, Kai wrote:
>
>>  

TDP_START. See:

+static int do_seamldr_install_module(void *params)
+{
+       enum tdp_state newstate, curstate = TDP_START;
				 ^^^^^^^^^^^^^^^^^^^^

>
>The code below says:

set_target_state() sets a global target (or next) state for all CPUs. Each CPU
compares its current state to the target. If they don't match, the CPU performs
the required task and then acks the state.

The global target state must be reset at the start of each update to trigger
the do-while loop in do_seamldr_install_module().

>+	ret = stop_machine_cpuslocked(do_seamldr_install_module, params,
>cpu_online_mask);

It stands for TD Preserving. Since this term isn't commonly used outside
Intel, "TDX Module updates" is clearer. I'll change this enum to:

enum module_update_state {
	MODULE_UPDATE_START,
	MODULE_UPDATE_SHUTDOWN,
	MODULE_UPDATE_CPU_INSTALL,
	MODULE_UPDATE_CPU_INIT,
	MODULE_UPDATE_RUN_UPDATE,
	MODULE_UPDATE_DONE,
};

>
>> +

how about:

	/*
	 * Ensure thread_ack is updated before the new state.
	 * Otherwise, other CPUs may see the new state and ack
	 * it before thread_ack is reset. An ack before reset
	 * is effectively lost, causing the system to wait
	 * forever for thread_ack to become zero.
	 */
	
>
>> +	smp_wmb();

Will do. Thanks for this suggestion.

---

## [42] Chao Gao — 2026-02-24
*Subject: Re: [PATCH v4 20/24] x86/virt/tdx: Enable TDX Module runtime updates*

On Mon, Feb 23, 2026 at 01:09:10PM +0800, Huang, Kai wrote:
>On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
>> All pieces of TDX Module runtime updates are in place. Enable it if it

Sure. Will do.

---

## [43] Huang, Kai — 2026-02-24
*Subject: Re: [PATCH v4 03/24] coco/tdx-host: Expose TDX Module version*

On Tue, 2026-02-24 at 10:02 +0800, Chao Gao wrote:
> On Fri, Feb 20, 2026 at 08:40:13AM +0800, Huang, Kai wrote:
> > On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:

I fully agree with this.  We need justification of why we need to expose TDX
module version to somewhere in /sysfs, and the choice of that somewhere is
the faux device attributes.

But my interpretation is Dave is asking to provide such justification in
general, but not specifically in _this_ patch.

In this patch, you have already adequately put why to expose version info
via /sysfs.  The "background" is really explaining why to choose "faux
device" as the /sysfs entry.

But you have already made the choice to use faux device (and mentioned
exposing version is one purpose) in the previous patch, so to me the
"background" part is a bit weird to be here, but not in previous patch.

But I also see there's some connection here -- and anyway this is just my
interpretation, so feel free to ignore :-)

---

## [44] Huang, Kai — 2026-02-24
*Subject: Re: [PATCH v4 04/24] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

> 
> > 

I thought that was under assumption both NP-SEAMLDR and P-SEAMLDR are SEAM
software (which is why both of them are mentioned).  But only P-SEAMLDR is,
so I thought we can skip NP-SEAMLDR.

> 
> And, since NP-SEAMLDR and P-SEAMLDR have similar names, I thought it would be

Sure.  If you feel that helps.

[...]

> 
> > > + * Serialize P-SEAMLDR calls since the hardware only allows a single CPU to

I thought that's not possible to happen because during module update we have
a machine state to serialize these P-SEAMLDR SEAMCALLs.

But I agree making it IRQ safe is the simplest way so that we don't need to
worry about the deadlock.


Sorry about the noise.

---

## [45] Huang, Kai — 2026-02-24
*Subject: Re: [PATCH v4 05/24] x86/virt/seamldr: Retrieve P-SEAMLDR information*

On Tue, 2026-02-24 at 10:59 +0800, Chao Gao wrote:
> On Fri, Feb 20, 2026 at 05:36:33PM +0800, Huang, Kai wrote:
> > 

Perhaps this is because in these existing usages "where the memory comes
from" and the "use of slow_virt_to_phys()" are closely together so no
comment is needed?

(disclaimer: I was looking at kvm_register_steal_time().)

So I am fine with either way -- feel free to ignore.

---

## [46] Huang, Kai — 2026-02-24
*Subject: Re: [PATCH v4 10/24] x86/virt/seamldr: Allocate and populate a module
 update request*

On Tue, 2026-02-24 at 13:15 +0800, Chao Gao wrote:
> On Fri, Feb 20, 2026 at 06:31:24AM +0800, Huang, Kai wrote:
> > On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:

Oh making kernel parse JSON file is beyond my imagination, but I see you
have a point here :-)

I think my real comment is the sentence 

  The kernel does not validate ...

only describes what does the kernel do today, which is not the case here.

Instead, we are making a design choice here, so I think the sentence should
at least be something like:

  Don't make the kernel validate ...

> 
> > 

Sure.

> 
> If the concern is that tdx_blob layout changes could cause incompatibilities,

No that's not the main concern.

> 
> If the issue is simply that links may become outdated, that's a common problem.

I think I prefer this instead of using the Links.

My concern is the links in the changelog won't be stable.  If that is
acceptable, then that's fine too.

But in the patch 23, you will update the doc anyway, so I think we can just
provide the link there (you already mentioned the repo link there anyway).

> 
> > 

I am fine keeping it here.  We need a link "somewhere in _this_ patch" to
review the code I think.

It's in the comment so we can change in the future if it changes.

---

## [47] Huang, Kai — 2026-02-24
*Subject: Re: [PATCH v4 11/24] x86/virt/seamldr: Introduce skeleton for TDX
 Module updates*

On Tue, 2026-02-24 at 14:00 +0800, Chao Gao wrote:
> On Mon, Feb 23, 2026 at 05:25:53PM +0800, Huang, Kai wrote:
> > 

OK thanks for clarification.

> 
> > +	ret = stop_machine_cpuslocked(do_seamldr_install_module, params,

Thanks.

> 
> > 

LGTM.

> > 
> > > +	smp_wmb();

---

## [48] Chao Gao — 2026-02-26
*Subject: Re: [PATCH v4 21/24] x86/virt/tdx: Avoid updates during
 update-sensitive operations*

>>  int tdx_module_shutdown(void)
>>  {

Good point.

I'm fine with disabling updates in this case. The only concern is that it would
block even perfectly compatible updates, but this only impacts a few older
modules, so it shouldn't be a big problem. And the value of supporting old
modules will also diminish over time.

But IMO, the kernel's incompatibility check is intentionally best effort, not a
guarantee. For example, the kernel doesn't verify if the module update is
compatible with the CPU or P-SEAMLDR. So non-compatible updates may slip through
anyway, and the expectation for users is "run non-compatible updates at their
own risk". Given this, allowing updates when one incompatibility check is
not supported (i.e., AVOID_COMPAT_SENSITIVE) is also acceptable. At minimum,
users can choose not to perform updates if the module lacks
AVOID_COMPAT_SENSITIVE support.

I'm fine with either approach, but slightly prefer disabling updates in
this case. Let's see if anyone has strong opinions on this.

---

## [49] dan.j.williams@intel.com — 2026-02-25
*Subject: Re: [PATCH v4 21/24] x86/virt/tdx: Avoid updates during
 update-sensitive operations*

Chao Gao wrote:
> >>  int tdx_module_shutdown(void)
> >>  {

Doing nothing in the kernel is fine. This is a tooling problem.

> >To me this means we cannot support module update if TDH.SYS.SHUTDOWN doesn't
> >support this "AVOID_COMPAT_SENSITIVE" feature, because w/o it we cannot tell

Do not make Linux carry short lived one-off complexity. Make userspace
do a "if $module_version < $min_module_version_for_compat_detect" and
tell the user to update at their own risk if that minimum version is not
met. Linux should be encouraging the module to be better, not
accommodate every early generation miss like this with permanent hacks.

---

## [50] Chao Gao — 2026-02-26
*Subject: Re: [PATCH v4 21/24] x86/virt/tdx: Avoid updates during
 update-sensitive operations*

>> >The changelog says "doing nothing" isn't an option, and we need to depend on
>> >TDH.SYS.SHUTDOWN to catch such incompatibilities.

I realize there's a potential issue with this update sequence:

old module (no compat detection) -> newer module (has compat detection) -> latest module

The problem arises during the second update. Userspace checks the currently
loaded module version and sees it supports compatibility detection, so it
expects the kernel to perform these checks. However, the kernel still thinks
the module lacks this capability because it never refreshes the module's
features after the first update.

Regarding disabling updates, I was thinking of an approach like the one below.
Do you think this is a workaround/hack?

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 2cf3a01d0b9c..50fe6373984d 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1192,9 +1192,7 @@ int tdx_module_shutdown(void)
	 * modules as new modules likely have higher handoff version.
	 */
	args.rcx = tdx_sysinfo.handoff.module_hv;
-
-	if (tdx_supports_update_compatibility(&tdx_sysinfo))
-		args.rcx |= TDX_SYS_SHUTDOWN_AVOID_COMPAT_SENSITIVE;
+	args.rcx |= TDX_SYS_SHUTDOWN_AVOID_COMPAT_SENSITIVE;
 
	ret = seamcall(TDH_SYS_SHUTDOWN, &args);
 
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 9ade3028a5bd..c7f0853e8ce5 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -181,6 +181,11 @@ static void seamldr_init(struct device *dev)
		return;
	}
 
+	if (!tdx_supports_update_compatibility(tdx_sysinfo)) {
+		pr_info("Current TDX Module does not support update compatibility\n");
+		return;
+	}
+
	tdx_fwl = firmware_upload_register(THIS_MODULE, dev, "tdx_module",
					   &tdx_fw_ops, NULL);
	ret = PTR_ERR_OR_ZERO(tdx_fwl);

---

## [51] dan.j.williams@intel.com — 2026-02-26
*Subject: Re: [PATCH v4 21/24] x86/virt/tdx: Avoid updates during
 update-sensitive operations*

Chao Gao wrote:
[..]
> >Do not make Linux carry short lived one-off complexity. Make userspace
> >do a "if $module_version < $min_module_version_for_compat_detect" and

Do not include logic to disable updates, document the expectation in the
tool. The general Linux expectation is administrator does not need to be
protected from themselves. The tool documentation can communicate best
practices that "time begins with module version X, only loading a
version X+ module from boot enables the safety protocol, runtime update
to X is insufficient". Administrator always has the option to proceed
and does not need the kernel to do extra hand holding.

Presumably this gap in the ecosystem is short lived and the deployment
of module versions < X drops precipitously and kernel does not need to
carry "disable updates" logic in perpetuity.

---

## [52] Xu Yilun — 2026-02-27
*Subject: Re: [PATCH v4 07/24] coco/tdx-host: Implement firmware upload sysfs
 ABI for TDX Module updates*

> v3:
>  - clear "cancel_request" in the "prepare" phase [Binbin]

Sorry I didn't continue the discussion in that thread, but I meant to
just skip -EOPNOTSUPP, but not hide real problems.

Not sure if it makes sense to other people, if yes, some changes below:

...

> +static void seamldr_init(struct device *dev)
> +{
                return -ENXIO;

> +
> +	if (!tdx_supports_runtime_update(tdx_sysinfo)) {
                return -EOPNOTSUPP;

> +	}
> +

        return ret;
> +}

...

> +
> +static int tdx_host_probe(struct faux_device *fdev)

I think no need the comments, all features are optional unless
explicitly required. So only exceptions need comments. Instead the code
may explain better.

> +	 */
> +	seamldr_init(&fdev->dev);

	ret = seamldr_init(&fdev->dev);
	if (ret && ret != -EOPNOTSUPP)
		return ret;

I imagine TDX Connect could follow the same pattern right below.

> +
> +	return 0;

---

## [53] Xu Yilun — 2026-02-27
*Subject: Re: [PATCH v4 07/24] coco/tdx-host: Implement firmware upload sysfs
 ABI for TDX Module updates*

> +static void seamldr_init(struct device *dev)
> +{

You could use devm_add_action_or_reset() in seamldr_init():

 1. to delete tdx_host_remove().
 2. to delete the global tdx_fwl;

> +
> +static int tdx_host_probe(struct faux_device *fdev)

---

## [54] Chao Gao — 2026-03-02
*Subject: Re: [PATCH v4 01/24] x86/virt/tdx: Move low level SEAMCALL helpers
 out of <asm/tdx.h>*

>-static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
>-			   struct tdx_module_args *args)

...

>-	} while (ret == TDX_RND_NO_ENTROPY && --retry);
>-

<snip>

>+
>+static __always_inline u64 sc_retry(sc_func_t func, u64 fn,

Here should be:

		preempt_disable();
		ret = __seamcall_dirty_cache(func, fn, args);
		preempt_enable();

This looks like a bug I introduced when resolving conflicts with

  commit 10df8607bf1a ("x86/virt/tdx: Mark memory cache state incoherent when making SEAMCALL")

Sorry for this issue. I will fix it in the next version.


>+	} while (ret == TDX_RND_NO_ENTROPY && --retry);
>+

---

## [55] Huang, Kai — 2026-03-04
*Subject: Re: [PATCH v4 12/24] x86/virt/seamldr: Abort updates if errors
 occurred midway*

On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
> The TDX Module update process has multiple steps, each of which may
> encounter failures.

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [56] Huang, Kai — 2026-03-04
*Subject: Re: [PATCH v4 13/24] x86/virt/seamldr: Shut down the current TDX
 module*

On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
> The first step of TDX Module updates is shutting down the current TDX
> Module. This step also packs state information that needs to be

Nit:

Again, ".. the Linux kernel only supports module upgrades ..." sounds like
describing the behaviour of the current kernel, but for now runtime update
is not supported yet.

I would change to " .. this implementation chooses to only support module
upgrades".


> request the current module to generate handoff data using its highest
> supported version, expecting that the new module will likely support it.

[...]

> diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
> index 82bb82be8567..1c4da9540ae0 100644

This (and future patches) makes couple of tdx_xx() functions visible out of
tdx.c.  The alternative is to move the main "module update" function out of
seamldr.c to tdx.c, but that would require making couple of seamldr_xx()s
(and data structures probably) visible to tdx.c too.

I don't know which is better, so to make this series move forward:

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [57] Huang, Kai — 2026-03-04
*Subject: Re: [PATCH v4 14/24] x86/virt/tdx: Reset software states during TDX
 Module shutdown*

> @@ -1179,6 +1179,7 @@ EXPORT_SYMBOL_FOR_KVM(tdx_enable);
>  int tdx_module_shutdown(void)

Maybe add a comment like:

	/*
	 * By reaching here CPUHP is disabled and all present CPUs
	 * are online.  It's safe to just loop all online CPUs and
	 * and reset the per-cpu flag.
	 */


And maybe a helper function like reset_tdx_kernel_states() would be nice,
but it's also fine to me as-is:

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [58] Huang, Kai — 2026-03-04
*Subject: Re: [PATCH v4 15/24] x86/virt/seamldr: Log TDX Module update failures*

On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
> Currently, there is no way to restore a TDX Module from shutdown state to
> running state. This means if errors occur after a successful module

Acked-by: Kai Huang <kai.huang@intel.com>

---

## [59] Huang, Kai — 2026-03-04
*Subject: Re: [PATCH v4 16/24] x86/virt/seamldr: Install a new TDX Module*

On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
> Following the shutdown of the existing TDX Module, the update process
> continues with installing the new module. P-SEAMLDR provides the

Nit:

Since you mentioned "serially" here, perhaps just add a sentence to mention
that it is guaranteed by the raw spinlock inside seamldr_call()?

> 
> Implement SEAMLDR.INSTALL and execute it on every CPU.

Reviewed-by: Kai Huang <kai.huang@intel.com>

Also a nit below ...

> ---
>  arch/x86/virt/vmx/tdx/seamldr.c | 9 ++++++++-

Nit:

IMHO such renaming is just a noise to this patch, since in patch 10/11 it's
clear that the 'params' you passed in is seamldr_params.  No?

Perhaps just name it 'seamldr_params' at patch 11?

>  {
>  	enum tdp_state newstate, curstate = TDP_START;

---

## [60] Huang, Kai — 2026-03-04
*Subject: Re: [PATCH v4 17/24] x86/virt/seamldr: Do TDX per-CPU initialization
 after updates*

On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
> After installing the new TDX module, each CPU should be initialized

Nit:

"should be" -> "needs to be" ?

> again to make the CPU ready to run any other SEAMCALLs. So, call
> tdx_cpu_enable() on all CPUs.

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [61] Huang, Kai — 2026-03-04
*Subject: Re: [PATCH v4 18/24] x86/virt/tdx: Restore TDX Module state*

On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
> TDX Module state was packed as handoff data during module shutdown. After
> per-CPU initialization, the new module can restore TDX Module state from

Nit:

"for one CPU" -> "on one CPU since it only needs to be called once".

> 
> Note that Intel® Trust Domain Extensions (Intel® TDX) Module Base

Nit: use imperative mode:

Don't implement the two alternative ... due to ...
 
> 
> Also note that the location and the format of handoff data is defined by

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [62] Huang, Kai — 2026-03-04
*Subject: Re: [PATCH v4 19/24] x86/virt/tdx: Update tdx_sysinfo and check
 features post-update*

On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
> tdx_sysinfo contains all metadata of the active TDX module, including
> versions, supported features, and TDMR/TDCS/TDVPS information. 

Nit: add "etc", since there are more staff besides the 3 things you listed.

> These
> values may change over updates. Blindly refreshing the entire tdx_sysinfo

Reviewed-by: Kai Huang <kai.huang@intel.com>

One bit below ...

[...]

>  
> +/*

s/updates/update?  I don't see more than one update.

And it's more than "check module features being changed" since there are
other metadata fields which may have different values after update, right?

I would just remove this comment since I don't see it says more than just
repeating the code below (which also has comments saying the same thing, in
a more elaborated way).

> + */
> +int tdx_module_post_update(struct tdx_sys_info *info)

---

## [63] Huang, Kai — 2026-03-04
*Subject: Re: [PATCH v4 23/24] x86/virt/tdx: Document TDX Module updates*

On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
> Document TDX Module updates as a subsection of "TDX Host Kernel Support" to
> provide background information and cover key points that developers and

During "updates" or "update"?  The module only becomes unresponsive during
"one module runtime update", correct?

> +
> +TDX Module updates have complex compatibility requirements; the new module

I think I've confused what you mean by "updates" or "update".

Perhaps you mean the "steps" during module update as "updates"?

But to me you indeed said "update" in the changelog:

"
 - update is done in stop_machine() context
 - update instructions and results
 - update policy and tooling
"

Please make this consistent at least.

With this clarified/addressed, feel free to add:

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [64] Xu Yilun — 2026-03-05
*Subject: Re: [PATCH v4 09/24] x86/virt/seamldr: Check update limit before TDX
 Module updates*

On Thu, Feb 12, 2026 at 06:35:12AM -0800, Chao Gao wrote:
> TDX maintains a log about each TDX Module which has been loaded. This
> log has a finite size which limits the number of TDX Module updates

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

---

## [65] Xu Yilun — 2026-03-05
*Subject: Re: [PATCH v4 10/24] x86/virt/seamldr: Allocate and populate a
 module update request*

On Thu, Feb 12, 2026 at 06:35:13AM -0800, Chao Gao wrote:
> P-SEAMLDR uses the SEAMLDR_PARAMS structure to describe TDX Module
> update requests. This structure contains physical addresses pointing to

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

---

## [66] Xu Yilun — 2026-03-05
*Subject: Re: [PATCH v4 13/24] x86/virt/seamldr: Shut down the current TDX
 module*

On Thu, Feb 12, 2026 at 06:35:16AM -0800, Chao Gao wrote:
> The first step of TDX Module updates is shutting down the current TDX
> Module. This step also packs state information that needs to be

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

---

## [67] Xu Yilun — 2026-03-05
*Subject: Re: [PATCH v4 15/24] x86/virt/seamldr: Log TDX Module update failures*

On Thu, Feb 12, 2026 at 06:35:18AM -0800, Chao Gao wrote:
> Currently, there is no way to restore a TDX Module from shutdown state to
> running state. This means if errors occur after a successful module

The wrapper seems redundant but maybe too much indent if put the print
in the loop. Anyway, either is good to me, up to you.

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

---

## [68] Xu Yilun — 2026-03-05
*Subject: Re: [PATCH v4 16/24] x86/virt/seamldr: Install a new TDX Module*

> > -static int do_seamldr_install_module(void *params)
> > +static int do_seamldr_install_module(void *seamldr_params)

Agree. Otherwise

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

> clear that the 'params' you passed in is seamldr_params.  No?
>

---

## [69] Huang, Kai — 2026-03-05
*Subject: Re: [PATCH v4 08/24] x86/virt/seamldr: Block TDX Module updates if
 any CPU is offline*

On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
> P-SEAMLDR requires every CPU to call SEAMLDR.INSTALL during updates. So,
> every CPU should be online during updates.

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [70] Huang, Kai — 2026-03-05
*Subject: Re: [PATCH v4 09/24] x86/virt/seamldr: Check update limit before TDX
 Module updates*

On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
> TDX maintains a log about each TDX Module which has been loaded. This
> log has a finite size which limits the number of TDX Module updates

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [71] Binbin Wu — 2026-03-05
*Subject: Re: [PATCH v4 01/24] x86/virt/tdx: Move low level SEAMCALL helpers
 out of <asm/tdx.h>*

On 2/12/2026 10:35 PM, Chao Gao wrote:
> From: Kai Huang <kai.huang@intel.com>
> 

Nit:
seamcall.h is now seamcall_internal.h in this version.

> currently tdx.c has seamcall_prerr*() helpers which additionally print
> error message when calling seamcall*() fails.  Move them to "seamcall.h"

Ditto.

> as well.  In such way all low level SEAMCALL helpers are in a dedicated
> place, which is much more readable.

[...]

---

## [72] Binbin Wu — 2026-03-05
*Subject: Re: [PATCH v4 02/24] coco/tdx-host: Introduce a "tdx_host" device*

On 2/12/2026 10:35 PM, Chao Gao wrote:
> TDX depends on a platform firmware module that is invoked via instructions
> similar to vmenter (i.e. enter into a new privileged "root-mode" context to

Nit:
There are "TDX module", "TDX-module" and "TDX Module" in the cover letter.
Better to align the style.

> provide services.
> 

[...]

> diff --git a/drivers/virt/coco/tdx-host/Kconfig b/drivers/virt/coco/tdx-host/Kconfig
> new file mode 100644

Nit:
A slight repetition: support for ... support.

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

> The module is called tdx_host.ko

[...]

---

## [73] Binbin Wu — 2026-03-05
*Subject: Re: [PATCH v4 04/24] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On 2/12/2026 10:35 PM, Chao Gao wrote:
> The TDX architecture uses the "SEAMCALL" instruction to communicate with
> SEAM mode software. Right now, the only SEAM mode software that the kernel

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

> ---
> v4:

---

## [74] Chao Gao — 2026-03-06
*Subject: Re: [PATCH v4 02/24] coco/tdx-host: Introduce a "tdx_host" device*

>> The call to tdx_get_sysinfo() ensures that the TDX Module is ready to
>

You are right. The terminology is inconsistent and confusing.

Different Intel specifications use different formats: the CPU Architectural
Extensions spec uses "TDX module" (lowercase 'm'), while the Module Base
Architecture Specification uses "TDX Module" (capital 'M'). I'm not sure where
"TDX-module" comes from, and Sean's VMXON series [*] adds to the confusion by
using "TDX-Module" in log messages.

*: https://lore.kernel.org/kvm/20260214012702.2368778-12-seanjc@google.com/

I don't have a strong preference, but I'll standardize on "TDX Module" since it
matches the Base Architecture Specification, which I think is the most
authoritative source about TDX Module features/terms.

---

## [75] Dave Hansen — 2026-03-05
*Subject: Re: [PATCH v4 02/24] coco/tdx-host: Introduce a "tdx_host" device*

On 3/5/26 18:13, Chao Gao wrote:
> I don't have a strong preference, but I'll standardize on "TDX
> Module" since it matches the Base Architecture Specification, which
How about doing what the Linux kernel does -- and has been doing --
instead of trying to pick a new policy a few years into the kernel
dealing with TDX?

"TDX module" was the first and it's 20x more common in the history than
the next closest one:

$ git log -p arch/x86/ | grep -i -o 'tdx[- ]module' | sort | uniq -c |
sort -n
      2 TDX-module
     21 TDX-Module
     26 TDX Module
    501 TDX module

If you don't have a strong preference, why are you arguing for change now?

---

## [76] Chao Gao — 2026-03-06
*Subject: Re: [PATCH v4 02/24] coco/tdx-host: Introduce a "tdx_host" device*

On Thu, Mar 05, 2026 at 08:17:34PM -0800, Dave Hansen wrote:
>On 3/5/26 18:13, Chao Gao wrote:
>> I don't have a strong preference, but I'll standardize on "TDX

Makes sense to me.

>
>"TDX module" was the first and it's 20x more common in the history than

I was just explaining what I would do for this series and my reasoning (if no
one had a strong preference and no one responded). I wasn't arguing that "TDX
module" is worse in any way.

---

## [77] Chao Gao — 2026-03-06
*Subject: Re: [PATCH v4 13/24] x86/virt/seamldr: Shut down the current TDX
 module*

>> Ideally, the kernel needs to retrieve the handoff versions supported by
>> the current module and the new module and select a version supported by

ack. 

>
>I would change to " .. this implementation chooses to only support module

looks good to me. Will do.

>> --- a/arch/x86/virt/vmx/tdx/tdx.h
>> +++ b/arch/x86/virt/vmx/tdx/tdx.h

Yes. I'll keep this organization unless someone strongly prefers moving the
main "module update" function and related data structures to tdx.c.

If neither approach is acceptable, a third option would be to remove seamldr.c
entirely and merge it into tdx.c. This would mean adding ~360 LoC to an
existing file that already has ~1900 LoC.

---

## [78] Chao Gao — 2026-03-06
*Subject: Re: [PATCH v4 19/24] x86/virt/tdx: Update tdx_sysinfo and check
 features post-update*

>>  
>> +/*

By "updates" I meant the update process in general, not multiple updates. Since
"update" is countable, it needs an article. I'll change it to "after an update"
for clarity.

>
>And it's more than "check module features being changed" since there are

Good point.

>
>I would just remove this comment since I don't see it says more than just

I added the comment because the function name isn't immediately clear about
what it does. I'd like people to understand the function's purpose without
reading the implementation (I also couldn't find a self-explanatory name for
the function). So I'd prefer to revise the comment rather than remove it.

Thanks.

---

## [79] Binbin Wu — 2026-03-06
*Subject: Re: [PATCH v4 06/24] coco/tdx-host: Expose P-SEAMLDR information via
 sysfs*

On 2/12/2026 10:35 PM, Chao Gao wrote:
> TDX Module updates require userspace to select the appropriate module
> to load. Expose necessary information to facilitate this decision. Two


Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

Some nits below.

> ---
> v4:
                                            ^
                                          that
> +		a finite size which limits the number of TDX Module updates
                             ^
                             ,
> +		which can be performed.
                  ^
                that
> +
> +		After each successful update, the number reduces by one. Once it
      ^
      Admin-only
> + * which may have potential performance and system impact.
> + */

---

## [80] Huang, Kai — 2026-03-06
*Subject: Re: [PATCH v4 19/24] x86/virt/tdx: Update tdx_sysinfo and check
 features post-update*

> > 
> > I would just remove this comment since I don't see it says more than just

It says "post_update", so it is clear to me that it is for "all last steps"
need to be done in the kernel after module is updated.

> I'd like people to understand the function's purpose without
> reading the implementation (I also couldn't find a self-explanatory name for

We can see exactly what is done as "post update" in the code.

And if you add more functionalities in the future to this function, you
don't have to modify the comment of the function to expand.

Anyway, up to you :-)

---

## [81] Yan Zhao — 2026-03-10
*Subject: Re: [PATCH v4 07/24] coco/tdx-host: Implement firmware upload sysfs
 ABI for TDX Module updates*

On Thu, Feb 12, 2026 at 06:35:10AM -0800, Chao Gao wrote:
> diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
> index cb2219302dfc..ffadbf64d0c1 100644
Nit: Tail comments are not preferred.

---

## [82] Chao Gao — 2026-03-11
*Subject: Re: [PATCH v4 24/24] [NOT-FOR-REVIEW] x86/virt/seamldr: Save and
 restore current VMCS*

On Thu, Feb 12, 2026 at 06:35:27AM -0800, Chao Gao wrote:
>P-SEAMLDR calls clobber the current VMCS as documented in Intel� Trust
>Domain CPU Architectural Extensions (May 2021 edition) Chapter 2.3 [1]:

The agreed approach is to fix the CPU behavior rather than work around the
issue in the kernel. So, I'll include the following patch to handle this
erratum. Please let me know if you have any concerns.

From 04b53e83dc9daee1866e1c8f26e3d027e1a0be6a Mon Sep 17 00:00:00 2001
From: Chao Gao <chao.gao@intel.com>
Date: Tue, 10 Mar 2026 18:49:41 -0700
Subject: [PATCH] coco/tdx-host: Don't expose P-SEAMLDR features on CPUs with
 erratum
MIME-Version: 1.0
Content-Type: text/plain; charset=UTF-8
Content-Transfer-Encoding: 8bit

Some TDX-capable CPUs have an erratum, as documented in Intel� Trust
Domain CPU Architectural Extensions (May 2021 edition) Chapter 2.3:

  SEAMRET from the P-SEAMLDR clears the current VMCS structure pointed
  to by the current-VMCS pointer. A VMM that invokes the P-SEAMLDR using
  SEAMCALL must reload the current-VMCS, if required, using the VMPTRLD
  instruction.

Clearing the current VMCS behind KVM's back will break KVM.

This erratum is not present when IA32_VMX_BASIC[60] is set. Check for
the erratum and refuse to expose P-SEAMLDR features (e.g., TDX module
updates) on affected CPUs.

== Alternatives ==
Two workarounds were considered but both were rejected:

1. Save/restore the current VMCS around P-SEAMLDR calls. This produces ugly
   assembly code [1] and doesn't play well with #MCE or #NMI if they
   need to use the current VMCS.

2. Move KVM's VMCS tracking logic to the TDX core code, which would break
   the boundary between KVM and the TDX core code [2].

Signed-off-by: Chao Gao <chao.gao@intel.com>
Link: https://lore.kernel.org/kvm/fedb3192-e68c-423c-93b2-a4dc2f964148@intel.com/ # [1]
Link: https://lore.kernel.org/kvm/aYIXFmT-676oN6j0@google.com/ # [2]
---
 arch/x86/include/asm/vmx.h            |  1 +
 drivers/virt/coco/tdx-host/tdx-host.c | 12 ++++++++++++
 2 files changed, 13 insertions(+)

diff --git a/arch/x86/include/asm/vmx.h b/arch/x86/include/asm/vmx.h
index c85c50019523..d066c50b9051 100644
--- a/arch/x86/include/asm/vmx.h
+++ b/arch/x86/include/asm/vmx.h
@@ -135,6 +135,7 @@
 #define VMX_BASIC_INOUT				BIT_ULL(54)
 #define VMX_BASIC_TRUE_CTLS			BIT_ULL(55)
 #define VMX_BASIC_NO_HW_ERROR_CODE_CC		BIT_ULL(56)
+#define VMX_BASIC_PRESERVE_CURRENT_VMCS		BIT_ULL(60)
 
 static inline u32 vmx_basic_vmcs_revision_id(u64 vmx_basic)
 {
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 891cc6a083e0..13c23769d09d 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -12,8 +12,10 @@
 #include <linux/sysfs.h>
 
 #include <asm/cpu_device_id.h>
+#include <asm/msr.h>
 #include <asm/seamldr.h>
 #include <asm/tdx.h>
+#include <asm/vmx.h>
 
 static const struct x86_cpu_id tdx_host_ids[] = {
	X86_MATCH_FEATURE(X86_FEATURE_TDX_HOST_PLATFORM, NULL),
@@ -175,6 +177,7 @@ static int seamldr_init(struct device *dev)
 {
	const struct tdx_sys_info *tdx_sysinfo = tdx_get_sysinfo();
	struct fw_upload *tdx_fwl;
+	u64 basic_msr;
 
	if (WARN_ON_ONCE(!tdx_sysinfo))
		return -EIO;
@@ -182,6 +185,15 @@ static int seamldr_init(struct device *dev)
	if (!tdx_supports_runtime_update(tdx_sysinfo))
		return 0;
 
+	/*
+	 * Some TDX-capable CPUs have an erratum where the current VMCS may
+	 * be cleared after calling into P-SEAMLDR. Ensure no such erratum
+	 * exists before exposing any P-SEAMLDR functions.
+	 */
+	rdmsrq(MSR_IA32_VMX_BASIC, basic_msr);
+	if (!(basic_msr & VMX_BASIC_PRESERVE_CURRENT_VMCS))
+		return 0;
+
	tdx_fwl = firmware_upload_register(THIS_MODULE, dev, "tdx_module",
					   &tdx_fw_ops, NULL);
	if (IS_ERR(tdx_fwl))

---

## [83] Huang, Kai — 2026-03-11
*Subject: Re: [PATCH v4 24/24] [NOT-FOR-REVIEW] x86/virt/seamldr: Save and
 restore current VMCS*

>  static const struct x86_cpu_id tdx_host_ids[] = {
> 	X86_MATCH_FEATURE(X86_FEATURE_TDX_HOST_PLATFORM, NULL),

IIUC this silently disables runtime update and user won't be able to have
any clue to tell what went wrong (while the user can see the module supports
this feature and apparently the kernel should support it)?

Since we already have a X86_BUG_TDX_PW_MCE which is detected during kernel
boot in tdx_init(), shouldn't we just follow so that the user can at least
see the CPU has this erratum?

Another advantage is, if in the future some other kernel code needs to know
this erratum, it can just consult this flag.

And btw,

Which code base was this patch generated?  If I read correctly, in this
series seamldr_init() is a void function but doesn't return anything.

---

## [84] Edgecombe, Rick P — 2026-03-12
*Subject: Re: [PATCH v4 11/24] x86/virt/seamldr: Introduce skeleton for TDX
 Module updates*

On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
> TDX Module updates require careful synchronization with other TDX
> operations on the host. During updates, only update-related SEAMCALLs are

Above it says only update-related SEAMCALLs are permitted. Does that not already
exclude SEAMCALLs that might allow entering the TD?

>  No single lock primitive can satisfy
> all these synchronization requirements, so stop_machine() is used as the

Does the fact that they can run on other CPUs add any synchronization
requirements? If not I'd leave it off.

> 
> In summary, TDX Module updates create two requirements:

The stop_machine() part seems more like a solution then a requirement.

> 
> 1. The entire update process must use stop_machine() to synchronize with

Offline Chao pointed that Paul suggested this after considering refactoring out
the common code. I think it might still be worth mentioning why you can't use
multi_cpu_stop() directly. I guess there are some differences. what are they.

>  Specifically, use a
> global state machine to control each CPU's work and require all CPUs to

Maybe add a bit more about the reasoning for requiring the other steps to ack.
Tie it back to the lockstep part.

> 
> Potential alternative to stop_machine()

Maybe a little comment here like "todo add the steps".

> +			default:
> +				break;

---

## [85] Edgecombe, Rick P — 2026-03-12
*Subject: Re: [PATCH v4 13/24] x86/virt/seamldr: Shut down the current TDX
 module*

On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
> The first step of TDX Module updates is shutting down the current TDX
> Module. This step also packs state information that needs to be

DPAMT has a similar need to conditionally fetch metadata. The thing that is ugly
about this is it refers to the global copy while populating the tdx_sys_info
passed as a pointer. That is how DPAMT worked previously. I was going to change
it to something like this for DPAMT:

diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index 13ad2663488b..13e68d375065 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -1,6 +1,6 @@
 // SPDX-License-Identifier: GPL-2.0
 /*
- * Automatically generated functions to read TDX global metadata.
+ * Functions to read TDX global metadata.
  *
  * This file doesn't compile on its own as it lacks of inclusion
  * of SEAMCALL wrapper primitive which reads global metadata.
@@ -18,6 +18,17 @@ static int get_tdx_sys_info_features(struct
tdx_sys_info_features *sysinfo_featu
        return ret;
 }
 
+static int get_tdx_sys_info_tdmr_dpamt(struct tdx_sys_info_tdmr *sysinfo_tdmr)
+{
+       int ret = 0;
+       u64 val;
+
+       if (!ret && !(ret = read_sys_metadata_field(0x9100000100000013, &val)))
+               sysinfo_tdmr->pamt_page_bitmap_entry_bits = val;
+
+       return ret;
+}
+
 static int get_tdx_sys_info_tdmr(struct tdx_sys_info_tdmr *sysinfo_tdmr)
 {
        int ret = 0;
@@ -94,5 +105,12 @@ static int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
        ret = ret ?: get_tdx_sys_info_td_ctrl(&sysinfo->td_ctrl);
        ret = ret ?: get_tdx_sys_info_td_conf(&sysinfo->td_conf);
 
+       /*
+        * Don't treat a module that doesn't support Dynamic PAMT
+        * as a failure. Only read the metadata optionally.
+        */
+       if (tdx_supports_dynamic_pamt(sysinfo))
+               ret = ret ?: get_tdx_sys_info_tdmr_dpamt(&sysinfo->tdmr);
+
        return ret;
 }


Wait, looking at the later patches, in the post update caller it will refer to
the old sysinfo instead of the new one? It assumes a new module will not lose
runtime update ability?

Rest of the patch LGTM.

> +
> +	if (!ret && !(ret = read_sys_metadata_field(0x8900000100000000, &val)))

---

## [86] Yan Zhao — 2026-03-12
*Subject: Re: [PATCH v4 10/24] x86/virt/seamldr: Allocate and populate a
 module update request*

On Thu, Feb 12, 2026 at 06:35:13AM -0800, Chao Gao wrote:
> P-SEAMLDR uses the SEAMLDR_PARAMS structure to describe TDX Module
> update requests. This structure contains physical addresses pointing to
Calculate this size (i.e., 80) from 4096 - xxx ?

> +	u64	num_module_pages;
> +	u64	mod_pages_pa_list[SEAMLDR_MAX_NR_MODULE_4KB_PAGES];

Add a comment for why params->version isn't initialized explicitly?

> +	ptr = sig;
> +	for (i = 0; i < sig_size / SZ_4K; i++) {
Do we need a macro for this 0x100?

> +		pr_err("unsupported blob version: %x\n", blob->version);
> +		return ERR_PTR(-EINVAL);

---

## [87] Edgecombe, Rick P — 2026-03-12
*Subject: Re: [PATCH v4 13/24] x86/virt/seamldr: Shut down the current TDX
 module*

On Fri, 2026-03-06 at 16:14 +0800, Chao Gao wrote:
> > This (and future patches) makes couple of tdx_xx() functions visible out of
> > tdx.c.  The alternative is to move the main "module update" function out of

tdx.c will only get bigger, but the breakdown between these files in this series
is not super clear to me. I think the headers are not a problem. But the fact
that seamldr.c is making seamcalls indirectly is a bit strange.

I'd maybe vote to put it all into tdx.c at this stage of the enabling, but
leaving it seems ok to me too. Someday when TDX is more implemented we can see
what borders make more sense.

---

## [88] Yan Zhao — 2026-03-12
*Subject: Re: [PATCH v4 09/24] x86/virt/seamldr: Check update limit before TDX
 Module updates*

On Thu, Feb 12, 2026 at 06:35:12AM -0800, Chao Gao wrote:
> TDX maintains a log about each TDX Module which has been loaded. This
> log has a finite size which limits the number of TDX Module updates
seamldr_install_module() is invoked by tdx_fw_write().
Why don't we put the check of info.num_remaining_updates in tdx_fw_prepare()?

>  	if (WARN_ON_ONCE(!is_vmalloc_addr(data)))
>  		return -EINVAL;

---

## [89] Edgecombe, Rick P — 2026-03-12
*Subject: Re: [PATCH v4 23/24] x86/virt/tdx: Document TDX Module updates*

On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
> +
> +Given the risk of losing existing TDs, userspace should verify that the update

Maybe a new line here.

> +A reference userspace tool that implements necessary checks is available at:
> +

It looks good in general. My only question is if we know what kind of
persistence this repo will have. These things can move around unfortunately.

---

## [90] Chao Gao — 2026-03-12
*Subject: Re: [PATCH v4 13/24] x86/virt/seamldr: Shut down the current TDX
 module*

>> +static int get_tdx_sys_info_handoff(struct tdx_sys_info_handoff *sysinfo_handoff)
>> +{

Looks good. I will follow this approach.

<snip>

>Wait, looking at the later patches, in the post update caller it will refer to
>the old sysinfo instead of the new one? It assumes a new module will not lose

Yes, no features should be removed during an update to avoid compatibility
issues. TDX module releases must guarantee this, and users should verify
compatibility before an update. If users load incompatible modules, that's
user error: the kernel doesn't prevent users from shooting themselves in
the foot.

---

## [91] Chao Gao — 2026-03-12
*Subject: Re: [PATCH v4 24/24] [NOT-FOR-REVIEW] x86/virt/seamldr: Save and
 restore current VMCS*

On Thu, Mar 12, 2026 at 06:06:22AM +0800, Huang, Kai wrote:
>
>>  static const struct x86_cpu_id tdx_host_ids[] = {

I'll add some logging.

>
>Since we already have a X86_BUG_TDX_PW_MCE which is detected during kernel

Thanks!

I didn't do that because I wasn't sure if adding a bug bit was justified
without another use case (i.e., this is a one-off check).

But I agree that following the X86_BUG_TDX_PW_MCE is better in consistency
and extensibility. So, here is the refined patch:


From 46e89a50803d6568eb60bd8ec866ac3fd9f6e6da Mon Sep 17 00:00:00 2001
From: Chao Gao <chao.gao@intel.com>
Date: Tue, 10 Mar 2026 18:49:41 -0700
Subject: [PATCH] coco/tdx-host: Don't expose P-SEAMLDR features on CPUs with
 erratum
MIME-Version: 1.0
Content-Type: text/plain; charset=UTF-8
Content-Transfer-Encoding: 8bit

Some TDX-capable CPUs have an erratum, as documented in Intel� Trust
Domain CPU Architectural Extensions (May 2021 edition) Chapter 2.3:

  SEAMRET from the P-SEAMLDR clears the current VMCS structure pointed
  to by the current-VMCS pointer. A VMM that invokes the P-SEAMLDR using
  SEAMCALL must reload the current-VMCS, if required, using the VMPTRLD
  instruction.

Clearing the current VMCS behind KVM's back will break KVM.

This erratum is not present when IA32_VMX_BASIC[60] is set. Add a CPU
bug bit for this erratum and refuse to expose P-SEAMLDR features (e.g.,
TDX module updates) on affected CPUs. Also, emit a message to clarify
why P-SEAMLDR features are disabled for affected CPUs.

== Alternatives ==
Two workarounds were considered but both were rejected:

1. Save/restore the current VMCS around P-SEAMLDR calls. This produces ugly
   assembly code [1] and doesn't play well with #MCE or #NMI if they
   need to use the current VMCS.

2. Move KVM's VMCS tracking logic to the TDX core code, which would break
   the boundary between KVM and the TDX core code [2].

Signed-off-by: Chao Gao <chao.gao@intel.com>
Link: https://lore.kernel.org/kvm/fedb3192-e68c-423c-93b2-a4dc2f964148@intel.com/ # [1]
Link: https://lore.kernel.org/kvm/aYIXFmT-676oN6j0@google.com/ # [2]
---
 arch/x86/include/asm/cpufeatures.h    |  1 +
 arch/x86/include/asm/vmx.h            |  1 +
 arch/x86/virt/vmx/tdx/tdx.c           | 12 ++++++++++++
 drivers/virt/coco/tdx-host/tdx-host.c |  5 +++++
 4 files changed, 19 insertions(+)

diff --git a/arch/x86/include/asm/cpufeatures.h b/arch/x86/include/asm/cpufeatures.h
index c3b53beb1300..dab518122946 100644
--- a/arch/x86/include/asm/cpufeatures.h
+++ b/arch/x86/include/asm/cpufeatures.h
@@ -570,4 +570,5 @@
 #define X86_BUG_ITS_NATIVE_ONLY		X86_BUG( 1*32+ 8) /* "its_native_only" CPU is affected by ITS, VMX is not affected */
 #define X86_BUG_TSA			X86_BUG( 1*32+ 9) /* "tsa" CPU is affected by Transient Scheduler Attacks */
 #define X86_BUG_VMSCAPE			X86_BUG( 1*32+10) /* "vmscape" CPU is affected by VMSCAPE attacks from guests */
+#define X86_BUG_SEAMRET_INVD_VMCS	X86_BUG( 1*32+11) /* "seamret_invd_vmcs" SEAMRET may clear the current VMCS */
 #endif /* _ASM_X86_CPUFEATURES_H */
diff --git a/arch/x86/include/asm/vmx.h b/arch/x86/include/asm/vmx.h
index c85c50019523..a467b681e62d 100644
--- a/arch/x86/include/asm/vmx.h
+++ b/arch/x86/include/asm/vmx.h
@@ -135,6 +135,7 @@
 #define VMX_BASIC_INOUT				BIT_ULL(54)
 #define VMX_BASIC_TRUE_CTLS			BIT_ULL(55)
 #define VMX_BASIC_NO_HW_ERROR_CODE_CC		BIT_ULL(56)
+#define VMX_BASIC_NO_SEAMRET_INVD_VMCS		BIT_ULL(60)
 
 static inline u32 vmx_basic_vmcs_revision_id(u64 vmx_basic)
 {
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 2caedc985fbd..06c8f957a6db 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -39,6 +39,7 @@
 #include <asm/cpu_device_id.h>
 #include <asm/processor.h>
 #include <asm/mce.h>
+#include <asm/vmx.h>
 
 #include "seamcall_internal.h"
 #include "tdx.h"
@@ -1453,6 +1454,8 @@ static struct notifier_block tdx_memory_nb = {
 
 static void __init check_tdx_erratum(void)
 {
+	u64 basic_msr;
+
	/*
	 * These CPUs have an erratum.  A partial write from non-TD
	 * software (e.g. via MOVNTI variants or UC/WC mapping) to TDX
@@ -1464,6 +1467,15 @@ static void __init check_tdx_erratum(void)
	case INTEL_EMERALDRAPIDS_X:
		setup_force_cpu_bug(X86_BUG_TDX_PW_MCE);
	}
+
+	/*
+	 * Some TDX-capable CPUs have an erratum where the current VMCS may
+	 * be cleared after calling into P-SEAMLDR. Ensure no such erratum
+	 * exists before exposing any P-SEAMLDR functions.
+	 */
+	rdmsrq(MSR_IA32_VMX_BASIC, basic_msr);
+	if (!(basic_msr & VMX_BASIC_NO_SEAMRET_INVD_VMCS))
+		setup_force_cpu_bug(X86_BUG_SEAMRET_INVD_VMCS);
 }
 
 void __init tdx_init(void)
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 891cc6a083e0..7e9496e215f6 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -182,6 +182,11 @@ static int seamldr_init(struct device *dev)
	if (!tdx_supports_runtime_update(tdx_sysinfo))
		return 0;
 
+	if (boot_cpu_has_bug(X86_BUG_SEAMRET_INVD_VMCS)) {
+		pr_info("Cannot talk with P-SEAMLDR due to seamret_invd_vmcs bug\n");
+		return 0;
+	}
+
	tdx_fwl = firmware_upload_register(THIS_MODULE, dev, "tdx_module",
					   &tdx_fw_ops, NULL);
	if (IS_ERR(tdx_fwl))

---

## [92] Huang, Kai — 2026-03-12
*Subject: Re: [PATCH v4 24/24] [NOT-FOR-REVIEW] x86/virt/seamldr: Save and
 restore current VMCS*

> 
> But I agree that following the X86_BUG_TDX_PW_MCE is better in consistency

The user can actually see this new bug flag in /proc/cpuinfo, so the error
message may not be mandatory.  It's fine to me anyway, so will leave to
others.

> 
> == Alternatives ==

LGTM:

Reviewed-by: Kai Huang <kai.huang@intel.com>

One nit below:


[...]

> +#define X86_BUG_SEAMRET_INVD_VMCS	X86_BUG( 1*32+11) /* "seamret_invd_vmcs" SEAMRET may clear the current VMCS */

"may clear" -> "clears" ?

---

## [93] Chao Gao — 2026-03-12
*Subject: Re: [PATCH v4 11/24] x86/virt/seamldr: Introduce skeleton for TDX
 Module updates*

On Thu, Mar 12, 2026 at 10:00:20AM +0800, Edgecombe, Rick P wrote:
>On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
>> TDX Module updates require careful synchronization with other TDX

Those SEAMCALLs would return errors, and TDs would be killed if those errors
aren't handled properly.

One may argue that we can handle errors and retry after updates. But this just
provides a new form of synchronization, which is not as clean as the
well-defined synchronization provided by the kernel.

>
>>  No single lock primitive can satisfy

I'm not sure I understand the concern.

Lockstep synchronization is needed specifically because we have both multiple
CPUs and multiple steps.

If updates only required a single CPU, stop_machine() would be sufficient.

>
>> 

To be clear, Paul didn't actually suggest this approach. His feedback indicated
he wasn't concerned about duplicating some of multi_cpu_stop()'s code, i.e., no
need to refactor out some common code.

https://lore.kernel.org/all/a7affba9-0cea-4493-b868-392158b59d83@paulmck-laptop/#t

We can't use multi_cpu_stop() directly because it only provides lockstep
execution for its own infrastructure, not for the function it runs. If we
passed a function that performs steps A, B, and C to multi_cpu_stop(), there's
no guarantee that all CPUs complete step A before any CPU begins step B.

>
>>  Specifically, use a

Ok. How about:

Specifically, add a global state machine where each state represents a step in
the above update flow. The state advances only after all CPUs acknowledge
completing their work in the current state. This acknowledgment mechanism is
what ensures lockstep execution.

<snip>

>> +static int do_seamldr_install_module(void *params)
>> +{

Sure.

---

## [94] Chao Gao — 2026-03-12
*Subject: Re: [PATCH v4 09/24] x86/virt/seamldr: Check update limit before TDX
 Module updates*

On Thu, Mar 12, 2026 at 10:35:53AM +0800, Yan Zhao wrote:
>On Thu, Feb 12, 2026 at 06:35:12AM -0800, Chao Gao wrote:
>> TDX maintains a log about each TDX Module which has been loaded. This

Putting sanity checks in a preparatory step makes sense. Will do.

---

## [95] Chao Gao — 2026-03-12
*Subject: Re: [PATCH v4 10/24] x86/virt/seamldr: Allocate and populate a
 module update request*

>> +static struct seamldr_params *alloc_seamldr_params(const void *module, unsigned int module_size,
>> +						   const void *sig, unsigned int sig_size)

Because the page is zero-allocated, the version is implicitly 0.

But I just found that 16KB sigstructs require version 1, so I'll make the
version explicit:

	/* Only version 1 supports >4KB sigstruct */
	if (sig_size > SZ_4K)
		params->version = 1;
	else
		params->version = 0;

Note that we can't always use version 1 since existing P-SEAMLDR versions don't
support it.

<snip>

>> +static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
>> +{

Maybe not, as this is a one-off check (i.e., the version/macro won't be used
anywhere else). If someone has a strong opinion on this, I can add one.

---

## [96] Vishal Annapurve — 2026-03-12
*Subject: Re: [PATCH v4 24/24] [NOT-FOR-REVIEW] x86/virt/seamldr: Save and
 restore current VMCS*

On Thu, Mar 12, 2026 at 1:48 AM Chao Gao <chao.gao@intel.com> wrote:
> But I agree that following the X86_BUG_TDX_PW_MCE is better in consistency
> and extensibility. So, here is the refined patch:

I see that significant discussion has already occurred regarding this.

My question intends to better understand the current state, Do we have
a known scenario today in upstream implementation where #MCE/#NMI need
to use the current VMCS?

>
> 2. Move KVM's VMCS tracking logic to the TDX core code, which would break

---

## [97] Dave Hansen — 2026-03-12
*Subject: Re: [PATCH v4 24/24] [NOT-FOR-REVIEW] x86/virt/seamldr: Save and
 restore current VMCS*

On 3/12/26 08:26, Vishal Annapurve wrote:
>> 1. Save/restore the current VMCS around P-SEAMLDR calls. This produces ugly
>>    assembly code [1] and doesn't play well with #MCE or #NMI if they

Nope, no known cases.

But, to be honest, it's not even something we should have to reason
about on the software side. It's foisting too much complexity and future
burden on software, so it's getting fixed.

---

## [98] Edgecombe, Rick P — 2026-03-12
*Subject: Re: [PATCH v4 10/24] x86/virt/seamldr: Allocate and populate a module
 update request*

On Thu, 2026-03-12 at 22:36 +0800, Chao Gao wrote:
> > > +	if (blob->version != 0x100) {
> > Do we need a macro for this 0x100?

Seems like kind of a magic number as it is. What would the macro name be, and
would it make the code more understandable?

---

## [99] Edgecombe, Rick P — 2026-03-12
*Subject: Re: [PATCH v4 11/24] x86/virt/seamldr: Introduce skeleton for TDX
 Module updates*

On Thu, 2026-03-12 at 22:09 +0800, Chao Gao wrote:
> On Thu, Mar 12, 2026 at 10:00:20AM +0800, Edgecombe, Rick P wrote:
> > On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:

Ah ok, so it's not about the SEAMCALL resulting in entering the TD, it's about
SEAMCALLs that are operating on TDs. That makes sense. But probably don't focus
on the TD entering part then. It's just any seamcalls that are not allowed
should not be called and they need to be excluded. It's simpler.

> 
> > 

The last part "some can run concurrently on all CPUs", how does it affect the
design? They can run concurrently, but don't have to... So it's a non-
requirement?

It seems the main argument here is, this thing has lots of complex ordering
requirements. So we do it lockstep as a simple pattern to bring sanity. It's a
fine fuzzy argument I think. The way you list the types of requirements all
specifically has me trying to find the connection between each requirement and
lockstep. That is where I get lost. If the reader doesn't need to do the work of
understanding, don't ask them. And if they do, it probably needs to be clearer.

> 
> > 

Right, sorry for oversimplifying.

> 
> https://lore.kernel.org/all/a7affba9-0cea-4493-b868-392158b59d83@paulmck-laptop/#t

If it could be said more concisely, it seems relevant.

> 
> > 

Looks good.

> 
> <snip>

---

## [100] Edgecombe, Rick P — 2026-03-12
*Subject: Re: [PATCH v4 19/24] x86/virt/tdx: Update tdx_sysinfo and check
 features post-update*

On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
> > tdx_sysinfo contains all metadata of the active TDX module, including
> > versions, supported features, and TDMR/TDCS/TDVPS information. These

Ahh, late day reviewing this yesterday, I read this as memcpy(). This seems like
a good approach. I'd only wonder if this should either be a stronger warning, or
we can skip checking the TDX module is behaving. We rely on a lot already. But
feel free to disregard it.

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

> > +
> > +	pr_info("TDX module features have changed after updates, but might not take effect.\n");

---

## [101] Edgecombe, Rick P — 2026-03-12
*Subject: Re: [PATCH v4 09/24] x86/virt/seamldr: Check update limit before TDX
 Module updates*

On Thu, 2026-02-12 at 06:35 -0800, Chao Gao wrote:
> TDX maintains a log about each TDX Module which has been loaded. This
> log has a finite size which limits the number of TDX Module updates

What happens if we drop this patch? The IIUC the idea is userspace needs to know
what they are doing already.

> 
> Signed-off-by: Chao Gao <chao.gao@intel.com>

---

## [102] Dave Hansen — 2026-03-12
*Subject: Re: [PATCH v4 04/24] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On 2/12/26 06:35, Chao Gao wrote:
> +static __maybe_unused int seamldr_call(u64 fn, struct tdx_module_args *args)
> +{

What SEAMLDR calls are getting made from IRQ context?

Why does this need to be raw_?

---

## [103] Dave Hansen — 2026-03-12
*Subject: Re: [PATCH v4 04/24] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On 2/24/26 02:25, Huang, Kai wrote:
> But I agree making it IRQ safe is the simplest way so that we don't need to
> worry about the deadlock.

Uh, we don't just disable interrupts so we don't have to worry about
things. We disable them when we *need* to functionally.

---

## [104] Dave Hansen — 2026-03-12
*Subject: Re: [PATCH v4 08/24] x86/virt/seamldr: Block TDX Module updates if
 any CPU is offline*

On 2/12/26 06:35, Chao Gao wrote:
> P-SEAMLDR requires every CPU to call SEAMLDR.INSTALL during updates. So,
> every CPU should be online during updates.

Gah, how did another one of these creep in? We've already fixed like a
half dozen of these.

There needs to be a *LONG* justification why there is no other choice
here. There are very good reasons to leave CPUs offline forever.

---

## [105] Dave Hansen — 2026-03-12
*Subject: Re: [PATCH v4 07/24] coco/tdx-host: Implement firmware upload sysfs
 ABI for TDX Module updates*

On 2/12/26 06:35, Chao Gao wrote:
> + * @data: Pointer to the TDX module update blob. It should be vmalloc'd
> + *        memory.

Why?!?! What does it matter? Why enforce this?

---

## [106] Dave Hansen — 2026-03-12
*Subject: Re: [PATCH v4 09/24] x86/virt/seamldr: Check update limit before TDX
 Module updates*

On 2/12/26 06:35, Chao Gao wrote:
> Note that userspace should perform this check before updates. Perform this
> check in kernel as well to make the update process more robust.

How many of these patches are to be "more robust"?

If you don't need it to "turn the lights on", I say kick it out.

---

## [107] Dave Hansen — 2026-03-12
*Subject: Re: [PATCH v4 11/24] x86/virt/seamldr: Introduce skeleton for TDX
 Module updates*

On 2/12/26 06:35, Chao Gao wrote:
> +static void set_target_state(enum tdp_state state)
> +{

This looks overly complicated.

If it doesn't need to be scalable, just make it stupid and simple. Why
not just protect the whole thing with a spinlock and be done with it?

---

## [108] Chao Gao — 2026-03-13
*Subject: Re: [PATCH v4 04/24] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On Thu, Mar 12, 2026 at 01:14:33PM -0700, Dave Hansen wrote:
>On 2/12/26 06:35, Chao Gao wrote:
>> +static __maybe_unused int seamldr_call(u64 fn, struct tdx_module_args *args)

No, I confused IRQ context with interrupt-disabled context.

SEAMLDR calls happen in two scenarios:

1. Userspace reads num_remaining_updates/seamldr version (interrupts enabled)
2. stop_machine() calls SEAMLDR to install updates (interrupts disabled)

Both run in process context, just with different interrupt states.
(I mistakenly thought case 2 was IRQ context)

>
>Why does this need to be raw_?

In RT kernel, a plain spinlock becomes sleeping lock. it cannot be called when
interrupt disabled (in case 2). I verified this by changing the lock to a plain
spinlock, I got this splat regardless of _irqsave version is used or not:

  BUG: sleeping function called from invalid context at kernel/locking/spinlock_rt.c:48
  in_atomic(): 1, irqs_disabled(): 1, non_block: 0, pid: 1772, name: migration/192
  preempt_count: 1, expected: 0
  RCU nest depth: 0, expected: 0
  1 lock held by migration/192/1772:
   #0: ffffffff834747e0 (seamldr_lock){+.+.}-{3:3}, at: seamldr_call+0x3a/0x1c0
  irq event stamp: 1070
  hardirqs last  enabled at (1069): [<ffffffff828ea7e8>] _raw_spin_unlock_irq+0x28/0x60
  hardirqs last disabled at (1070): [<ffffffff814a1ae0>] multi_cpu_stop+0xc0/0x140
  softirqs last  enabled at (0): [<ffffffff81313dcf>] copy_process+0xaaf/0x22a0
  softirqs last disabled at (0): [<0000000000000000>] 0x0
  Preemption disabled at:
  [<ffffffff814a1397>] cpu_stopper_thread+0x97/0x140

So, I will use:

	guard(raw_spinlock)(&seamldr_lock);

---

## [109] Chao Gao — 2026-03-13
*Subject: Re: [PATCH v4 08/24] x86/virt/seamldr: Block TDX Module updates if
 any CPU is offline*

On Thu, Mar 12, 2026 at 01:20:27PM -0700, Dave Hansen wrote:
>On 2/12/26 06:35, Chao Gao wrote:
>> P-SEAMLDR requires every CPU to call SEAMLDR.INSTALL during updates. So,

I will drop this patch.

For the record:

This patch was added in v2 after testing revealed that module updates with offline
CPUs would fail and kill all TDs. I attempted to provide graceful handling in the
kernel.

But "all-CPUs-online" is a temporary TDX module limitation that will be
resolved in future releases.

So, adding kernel complexity for this isn't warranted. Admins can verify all
CPUs are online before updating. This is consistent with how this series
already expects users to do compatibility verification.

---

## [110] Chao Gao — 2026-03-13
*Subject: Re: [PATCH v4 07/24] coco/tdx-host: Implement firmware upload sysfs
 ABI for TDX Module updates*

On Thu, Mar 12, 2026 at 01:20:59PM -0700, Dave Hansen wrote:
>On 2/12/26 06:35, Chao Gao wrote:
>> + * @data: Pointer to the TDX module update blob. It should be vmalloc'd

The firmware upload framework stores firmware from userspace in vmalloc memory.
I added this check because a later patch uses vmalloc_to_pfn() to obtain
physical addresses.

As we discussed offline, I'll remove all is_vmalloc_addr() checks. Since
vmalloc_to_pfn/page() already has a BUG_ON, future implementation changes
of firmware upload framework will produce a call trace anyway. So, no need
to duplicate the debug code.

---

## [111] Chao Gao — 2026-03-13
*Subject: Re: [PATCH v4 09/24] x86/virt/seamldr: Check update limit before TDX
 Module updates*

On Thu, Mar 12, 2026 at 01:23:04PM -0700, Dave Hansen wrote:
>On 2/12/26 06:35, Chao Gao wrote:
>> Note that userspace should perform this check before updates. Perform this

Only patch 8 and this patch fall into this category. I'll drop them.

---

## [112] Chao Gao — 2026-03-13
*Subject: Re: [PATCH v4 11/24] x86/virt/seamldr: Introduce skeleton for TDX
 Module updates*

On Thu, Mar 12, 2026 at 01:40:44PM -0700, Dave Hansen wrote:
>On 2/12/26 06:35, Chao Gao wrote:
>> +static void set_target_state(enum tdp_state state)

Good suggestion. I copied this from multi_cpu_stop() without considering
whether it could be simplified.

Regarding scalability, I compared the update time and didn't see a
meaningful difference on a system with 240 CPUs.

I will make changes like this:

(Note: I'm also renaming tdp_data/tdp_state to update_data and
 module_update_state for clarity, since "tdp" isn't obvious as Kai pointed
 out.)

 static struct {
	enum module_update_state state;
-	atomic_t thread_ack;
-	atomic_t failed;
+	int thread_ack;
+	int failed;
+	raw_spinlock_t lock;
 } update_data;
 
 static void set_target_state(enum module_update_state state)
 {
	/* Reset ack counter. */
-	atomic_set(&update_data.thread_ack, num_online_cpus());
-	/*
-	 * Ensure thread_ack is updated before the new state.
-	 * Otherwise, other CPUs may see the new state and ack
-	 * it before thread_ack is reset. An ack before reset
-	 * is effectively lost, causing the system to wait
-	 * forever for thread_ack to become zero.
-	 */
-	smp_wmb();
-	WRITE_ONCE(update_data.state, state);
+	update_data.thread_ack = num_online_cpus();
+	update_data.state = state;
 }
 
 /* Last one to ack a state moves to the next state. */
 static void ack_state(void)
 {
-	if (atomic_dec_and_test(&update_data.thread_ack))
+	guard(raw_spinlock)(&update_data.lock);
+	update_data.thread_ack--;
+	if (!update_data.thread_ack)
		set_target_state(update_data.state + 1);
 }

---

## [113] Chao Gao — 2026-03-13
*Subject: Re: [PATCH v4 10/24] x86/virt/seamldr: Allocate and populate a
 module update request*

On Fri, Mar 13, 2026 at 12:56:19AM +0800, Edgecombe, Rick P wrote:
>On Thu, 2026-03-12 at 22:36 +0800, Chao Gao wrote:
>> > > +	if (blob->version != 0x100) {

Yes. Adding a macro can improve readability. So, will do.

Thanks, Yan and Rick.

---

## [114] Chao Gao — 2026-03-13
*Subject: Re: [PATCH v4 11/24] x86/virt/seamldr: Introduce skeleton for TDX
 Module updates*

>> > > 
>> > > The TDX Module update process consists of several steps as described in

Got it. I'll keep it simple:

  The TDX Module update process consists of several steps as described in
  Intel� Trust Domain Extensions (Intel� TDX) Module Base Architecture
  Specification, Revision 348549-007, Chapter 4.5 "TD-Preserving TDX Module
  Update"
  
    - shut down the old module
    - install the new module
    - global and per-CPU initialization
    - restore state information
  
  There are ordering requirements between steps which mandate lockstep
  synchronization across all CPUs.

Or the step details might be irrelevant. Perhaps:

  TDX module update consists of several steps. Ordering requirements between
  steps mandate lockstep synchronization across all CPUs.

>> > > 1. The entire update process must use stop_machine() to synchronize with
>> > >    other TDX workloads

How about:

multi_cpu_stop() executes in lockstep but doesn't synchronize steps within the
callback function it takes. So, implement one based on its pattern.

---

## [115] Edgecombe, Rick P — 2026-03-13
*Subject: Re: [PATCH v4 11/24] x86/virt/seamldr: Introduce skeleton for TDX
 Module updates*

On Fri, 2026-03-13 at 21:54 +0800, Chao Gao wrote:
> Or the step details might be irrelevant. Perhaps:
> 

It seems like enough to understand this patch. Then would you put a little blurb
about the ordering of each step in the later patches?

> 
> > > > > 1. The entire update process must use stop_machine() to synchronize with

Yea.

---
