---
title: 'Runtime TDX Module update support'
date: 2026-01-23
last_reply: 2026-02-06
message_count: 132
participants: ['Chao Gao', 'Tony Lindgren', 'dan.j.williams@intel.com', 'Huang, Kai', 'Binbin Wu', 'Dave Hansen', 'Sagi Shahar', 'Xu Yilun', 'Sean Christopherson', 'Xing, Cedric']
---

## [1] Chao Gao — 2026-01-23

Hi Reviewers,

With this posting, I'm hoping to collect more Reviewed-by or Acked-by tags.
Dave, since this version is still light on acks, it might not be ready for
your review.

Changelog:
v2->v3:
 - Make this series self-contained and independently runnable, testable and
   reviewable by

   * Including dependent patches such as TDX Module version exposure and TDX
     faux device creation

   * Removing dependency on Sean's VMXON cleanups for now, the tdx-host device
     simply checks that the TDX module is initialized, regardless of when or
     who performed the initialization.

     Note: If the KVM module is unloaded, all services exposed by the tdx-host
     device will fail. This shouldn't be a big issue since proper errors will
     be returned to userspace, similar to other failure cases.

 - Handle updates during update-sensitive times and documented expectations for
   TDX Module updates
 - Rework how updates are aborted when errors occur midway
 - Map Linux error codes to firmware upload error codes
 - Preserve bit 63 in P-SEAMLDR SEAMCALL leaf numbers and display them in hex
 - Do not fail the entire tdx-host device when update features encounter errors
 - Drop superfluous is_visible() function for P-SEAMLDR sysfs nodes
 - Add support for sigstruct sizes up to 16KB
 - Move CONFIG_INTEL_TDX_MODULE_UPDATE kconfig entry under TDX_HOST_SERVICES
 - Various cleanups and changelog improvements for clarity and consistency
 - Collect review tags from ZhenZhong and Jonathan
 - v2: https://lore.kernel.org/linux-coco/20251001025442.427697-1-chao.gao@intel.com/

This series adds support for runtime TDX Module updates that preserve
running TDX guests. It is also available at:

  https://github.com/gaochaointel/linux-dev/commits/tdx-module-updates-v3/

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

Chao Gao (25):
  x86/virt/tdx: Print SEAMCALL leaf numbers in decimal
  x86/virt/tdx: Use %# prefix for hex values in SEAMCALL error messages
  coco/tdx-host: Introduce a "tdx_host" device
  coco/tdx-host: Expose TDX Module version
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
  x86/virt/seamldr: Log TDX Module update failures
  x86/virt/seamldr: Install a new TDX Module
  x86/virt/seamldr: Do TDX per-CPU initialization after updates
  x86/virt/tdx: Establish contexts for the new TDX Module
  x86/virt/tdx: Update tdx_sysinfo and check features post-update
  x86/virt/tdx: Enable TDX Module runtime updates
  x86/virt/seamldr: Extend sigstruct to 16KB
  x86/virt/tdx: Avoid updates during update-sensitive operations
  coco/tdx-host: Set and document TDX Module update expectations

Kai Huang (1):
  x86/virt/tdx: Move low level SEAMCALL helpers out of <asm/tdx.h>

 .../ABI/testing/sysfs-devices-faux-tdx-host   |  76 ++++
 arch/x86/include/asm/seamldr.h                |  29 ++
 arch/x86/include/asm/tdx.h                    |  66 +--
 arch/x86/include/asm/tdx_global_metadata.h    |   5 +
 arch/x86/kvm/vmx/tdx_errno.h                  |   2 -
 arch/x86/virt/vmx/tdx/Makefile                |   1 +
 arch/x86/virt/vmx/tdx/seamcall.h              | 125 ++++++
 arch/x86/virt/vmx/tdx/seamldr.c               | 398 ++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.c                   | 153 ++++---
 arch/x86/virt/vmx/tdx/tdx.h                   |  11 +-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c   |  13 +
 drivers/virt/coco/Kconfig                     |   2 +
 drivers/virt/coco/Makefile                    |   1 +
 drivers/virt/coco/tdx-host/Kconfig            |  22 +
 drivers/virt/coco/tdx-host/Makefile           |   1 +
 drivers/virt/coco/tdx-host/tdx-host.c         | 260 ++++++++++++
 16 files changed, 1064 insertions(+), 101 deletions(-)
 create mode 100644 Documentation/ABI/testing/sysfs-devices-faux-tdx-host
 create mode 100644 arch/x86/include/asm/seamldr.h
 create mode 100644 arch/x86/virt/vmx/tdx/seamcall.h
 create mode 100644 arch/x86/virt/vmx/tdx/seamldr.c
 create mode 100644 drivers/virt/coco/tdx-host/Kconfig
 create mode 100644 drivers/virt/coco/tdx-host/Makefile
 create mode 100644 drivers/virt/coco/tdx-host/tdx-host.c

---

## [2] Chao Gao — 2026-01-23
*Subject: [PATCH v3 01/26] x86/virt/tdx: Print SEAMCALL leaf numbers in decimal*

Both TDX spec and kernel defines SEAMCALL leaf numbers as decimal. Printing
them in hex makes no sense. Correct it.

Suggested-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
---
v2:
 - print leaf numbers with %llu
---
 arch/x86/virt/vmx/tdx/tdx.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 5ce4ebe99774..dbc7cb08ca53 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -63,7 +63,7 @@ typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);
 
 static inline void seamcall_err(u64 fn, u64 err, struct tdx_module_args *args)
 {
-	pr_err("SEAMCALL (0x%016llx) failed: 0x%016llx\n", fn, err);
+	pr_err("SEAMCALL (%llu) failed: 0x%016llx\n", fn, err);
 }
 
 static inline void seamcall_err_ret(u64 fn, u64 err,

---

## [3] Chao Gao — 2026-01-23
*Subject: [PATCH v3 02/26] x86/virt/tdx: Use %# prefix for hex values in SEAMCALL error messages*

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
index dbc7cb08ca53..2218bb42af40 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -63,16 +63,16 @@ typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);
 
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

## [4] Chao Gao — 2026-01-23
*Subject: [PATCH v3 03/26] x86/virt/tdx: Move low level SEAMCALL helpers out of <asm/tdx.h>*

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
Reviewed-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
---
v2:
 - new
---
 arch/x86/include/asm/tdx.h       | 47 ---------------
 arch/x86/virt/vmx/tdx/seamcall.h | 99 ++++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.c      | 46 +--------------
 3 files changed, 100 insertions(+), 92 deletions(-)
 create mode 100644 arch/x86/virt/vmx/tdx/seamcall.h

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
diff --git a/arch/x86/virt/vmx/tdx/seamcall.h b/arch/x86/virt/vmx/tdx/seamcall.h
new file mode 100644
index 000000000000..0912e03fabfe
--- /dev/null
+++ b/arch/x86/virt/vmx/tdx/seamcall.h
@@ -0,0 +1,99 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+/* Copyright (C) 2025 Intel Corporation */
+#ifndef _X86_VIRT_SEAMCALL_H
+#define _X86_VIRT_SEAMCALL_H
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
index 2218bb42af40..b44723ef4a14 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -39,6 +39,7 @@
 #include <asm/cpu_device_id.h>
 #include <asm/processor.h>
 #include <asm/mce.h>
+#include "seamcall.h"
 #include "tdx.h"
 
 static u32 tdx_global_keyid __ro_after_init;
@@ -59,51 +60,6 @@ static LIST_HEAD(tdx_memlist);
 
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

## [5] Chao Gao — 2026-01-23
*Subject: [PATCH v3 04/26] coco/tdx-host: Introduce a "tdx_host" device*

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
index b44723ef4a14..a0990c5dd78d 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1434,7 +1434,7 @@ const struct tdx_sys_info *tdx_get_sysinfo(void)
 
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

## [6] Chao Gao — 2026-01-23
*Subject: [PATCH v3 05/26] coco/tdx-host: Expose TDX Module version*

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

This approach follows the pattern used by microcode updates and other
CoCo implementations:

1. AMD has a PCI device for the PSP for SEV which provides an existing
   place to hang their equivalent metadata.

2. ARM CCA will likely have a faux device (although it isn't obvious if
   they have a need to export version information there) [1]

3. Microcode revisions are exposed as CPU device attributes

One bonus of exposing TDX Module version via sysfs is: TDX Module
version information remains available even after dmesg logs are cleared.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Link: https://lore.kernel.org/all/2025073035-bulginess-rematch-b92e@gregkh/ # [1]
---
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

## [7] Chao Gao — 2026-01-23
*Subject: [PATCH v3 06/26] x86/virt/tdx: Prepare to support P-SEAMLDR SEAMCALLs*

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

v3:
 - print P-SEAMLDR leaf numbers in hex
 - use %# to print error code [Binbin]
 - mark the is_seamldr_call() call as unlikely [Binbin]
 - remove the function to get the error code for retry from leaf numbers
   [Yilun]
v2:
 - use a macro rather than an inline function for seamldr_err() for
   consistency.
---
 arch/x86/virt/vmx/tdx/seamcall.h | 28 +++++++++++++++++++++++++++-
 1 file changed, 27 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/seamcall.h b/arch/x86/virt/vmx/tdx/seamcall.h
index 0912e03fabfe..256f71d6ca70 100644
--- a/arch/x86/virt/vmx/tdx/seamcall.h
+++ b/arch/x86/virt/vmx/tdx/seamcall.h
@@ -34,15 +34,28 @@ static __always_inline u64 __seamcall_dirty_cache(sc_func_t func, u64 fn,
 	return func(fn, args);
 }
 
+#define SEAMLDR_RND_NO_ENTROPY	0x8000000000030001ULL
+
+#define SEAMLDR_SEAMCALL_MASK	_BITUL(63)
+
+static inline bool is_seamldr_call(u64 fn)
+{
+	return fn & SEAMLDR_SEAMCALL_MASK;
+}
+
 static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
 			   struct tdx_module_args *args)
 {
+	u64 retry_code = TDX_RND_NO_ENTROPY;
 	int retry = RDRAND_RETRY_LOOPS;
 	u64 ret;
 
+	if (unlikely(is_seamldr_call(fn)))
+		retry_code = SEAMLDR_RND_NO_ENTROPY;
+
 	do {
 		ret = func(fn, args);
-	} while (ret == TDX_RND_NO_ENTROPY && --retry);
+	} while (ret == retry_code && --retry);
 
 	return ret;
 }
@@ -68,6 +81,16 @@ static inline void seamcall_err_ret(u64 fn, u64 err,
 			args->r9, args->r10, args->r11);
 }
 
+static inline void seamldr_err(u64 fn, u64 err, struct tdx_module_args *args)
+{
+	/*
+	 * Note: P-SEAMLDR leaf numbers are printed in hex as they have
+	 * bit 63 set, making them hard to read and understand if printed
+	 * in decimal
+	 */
+	pr_err("P-SEAMLDR (%llx) failed: %#016llx\n", fn, err);
+}
+
 static __always_inline int sc_retry_prerr(sc_func_t func,
 					  sc_err_func_t err_func,
 					  u64 fn, struct tdx_module_args *args)
@@ -96,4 +119,7 @@ static __always_inline int sc_retry_prerr(sc_func_t func,
 #define seamcall_prerr_ret(__fn, __args)					\
 	sc_retry_prerr(__seamcall_ret, seamcall_err_ret, (__fn), (__args))
 
+#define seamldr_prerr(__fn, __args)						\
+	sc_retry_prerr(__seamcall, seamldr_err, (__fn), (__args))
+
 #endif

---

## [8] Chao Gao — 2026-01-23
*Subject: [PATCH v3 07/26] x86/virt/seamldr: Introduce a wrapper for P-SEAMLDR SEAMCALLs*

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
 arch/x86/virt/vmx/tdx/Makefile     |  1 +
 arch/x86/virt/vmx/tdx/seamldr.c    | 56 ++++++++++++++++++++++++++++++
 drivers/virt/coco/tdx-host/Kconfig | 10 ++++++
 3 files changed, 67 insertions(+)
 create mode 100644 arch/x86/virt/vmx/tdx/seamldr.c

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
diff --git a/drivers/virt/coco/tdx-host/Kconfig b/drivers/virt/coco/tdx-host/Kconfig
index e58bad148a35..6a9199e6c2c6 100644
--- a/drivers/virt/coco/tdx-host/Kconfig
+++ b/drivers/virt/coco/tdx-host/Kconfig
@@ -8,3 +8,13 @@ config TDX_HOST_SERVICES
 
 	  Say y or m if enabling support for confidential virtual machine
 	  support (CONFIG_INTEL_TDX_HOST). The module is called tdx_host.ko
+
+config INTEL_TDX_MODULE_UPDATE
+	bool "Intel TDX module runtime update"
+	depends on TDX_HOST_SERVICES
+	help
+	  This enables the kernel to support TDX module runtime update. This
+	  allows the admin to update the TDX module to another compatible
+	  version without the need to terminate running TDX guests.
+
+	  If unsure, say N.

---

## [9] Chao Gao — 2026-01-23
*Subject: [PATCH v3 08/26] x86/virt/seamldr: Retrieve P-SEAMLDR information*

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
index b99d73f7bb08..6a83ae405fac 100644
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
+EXPORT_SYMBOL_FOR_MODULES(seamldr_get_info, "tdx-host");

---

## [10] Chao Gao — 2026-01-23
*Subject: [PATCH v3 09/26] coco/tdx-host: Expose P-SEAMLDR information via sysfs*

TDX Module updates require userspace to select the appropriate module
to load. Expose necessary information to facilitate this decision. Two
values are needed:

- P-SEAMLDR version: for compatibility checks between TDX Module and
		     P-SEAMLDR
- num_remaining_updates: indicates how many updates can be performed

Expose them as tdx-host device attributes.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
v3:
 - use #ifdef rather than .is_visible() to control P-SEAMLDR sysfs
   visibility [Yilun]
---
 .../ABI/testing/sysfs-devices-faux-tdx-host   | 25 ++++++++
 drivers/virt/coco/tdx-host/tdx-host.c         | 60 ++++++++++++++++++-
 2 files changed, 84 insertions(+), 1 deletion(-)

diff --git a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
index 901abbae2e61..a3f155977016 100644
--- a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
+++ b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
@@ -4,3 +4,28 @@ Description:	(RO) Report the version of the loaded TDX Module. The TDX Module
 		version is formatted as x.y.z, where "x" is the major version,
 		"y" is the minor version and "z" is the update version. Versions
 		are used for bug reporting, TDX Module updates and etc.
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
+		capacity, there's a maximum number of Module updates that can
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
index 0424933b2560..f4ce89522806 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -11,6 +11,7 @@
 #include <linux/sysfs.h>
 
 #include <asm/cpu_device_id.h>
+#include <asm/seamldr.h>
 #include <asm/tdx.h>
 
 static const struct x86_cpu_id tdx_host_ids[] = {
@@ -40,7 +41,64 @@ static struct attribute *tdx_host_attrs[] = {
 	&dev_attr_version.attr,
 	NULL,
 };
-ATTRIBUTE_GROUPS(tdx_host);
+
+struct attribute_group tdx_host_group = {
+	.attrs = tdx_host_attrs,
+};
+
+#ifdef CONFIG_INTEL_TDX_MODULE_UPDATE
+static ssize_t seamldr_version_show(struct device *dev, struct device_attribute *attr,
+				    char *buf)
+{
+	const struct seamldr_info *info = seamldr_get_info();
+
+	if (!info)
+		return -ENXIO;
+
+	return sysfs_emit(buf, "%u.%u.%02u\n", info->major_version,
+					       info->minor_version,
+					       info->update_version);
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
+ * P-SEAMLDR version as version_show() is used for TDX Module version.
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
+static struct attribute_group seamldr_group = {
+	.name = "seamldr",
+	.attrs = seamldr_attrs,
+};
+#endif /* CONFIG_INTEL_TDX_MODULE_UPDATE */
+
+static const struct attribute_group *tdx_host_groups[] = {
+	&tdx_host_group,
+#ifdef CONFIG_INTEL_TDX_MODULE_UPDATE
+	&seamldr_group,
+#endif
+	NULL,
+};
 
 static struct faux_device *fdev;

---

## [11] Chao Gao — 2026-01-23
*Subject: [PATCH v3 10/26] coco/tdx-host: Implement FW_UPLOAD sysfs ABI for TDX Module updates*

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
v3:
 - clear "cancel_request" in the "prepare" phase [Binbin]
 - Don't fail the whole tdx-host device if seamldr_init() met an error
 [Yilun]
 - Add kdoc for seamldr_install_module() and verify that the input
   buffer is vmalloc'd. [Yilun]
---
 arch/x86/include/asm/seamldr.h        |   2 +
 arch/x86/include/asm/tdx.h            |   5 ++
 arch/x86/virt/vmx/tdx/seamldr.c       |  19 ++++
 drivers/virt/coco/tdx-host/Kconfig    |   2 +
 drivers/virt/coco/tdx-host/tdx-host.c | 124 +++++++++++++++++++++++++-
 5 files changed, 151 insertions(+), 1 deletion(-)

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
index 6a83ae405fac..af7a6621e5e0 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -7,6 +7,7 @@
 #define pr_fmt(fmt)	"seamldr: " fmt
 
 #include <linux/irqflags.h>
+#include <linux/mm.h>
 #include <linux/types.h>
 
 #include <asm/seamldr.h>
@@ -69,3 +70,21 @@ const struct seamldr_info *seamldr_get_info(void)
 	return seamldr_call(P_SEAMLDR_INFO, &args) ? NULL : &seamldr_info;
 }
 EXPORT_SYMBOL_FOR_MODULES(seamldr_get_info, "tdx-host");
+
+/**
+ * seamldr_install_module - Install a new TDX module
+ * @data: Pointer to the TDX module binary data. It should be vmalloc'd
+ *        memory.
+ * @size: Size of the TDX module binary data
+ *
+ * Returns 0 on success, negative error code on failure.
+ */
+int seamldr_install_module(const u8 *data, u32 size)
+{
+	if (!is_vmalloc_addr(data))
+		return -EINVAL;
+
+	/* TODO: Update TDX Module here */
+	return 0;
+}
+EXPORT_SYMBOL_FOR_MODULES(seamldr_install_module, "tdx-host");
diff --git a/drivers/virt/coco/tdx-host/Kconfig b/drivers/virt/coco/tdx-host/Kconfig
index 6a9199e6c2c6..59aaca2252b0 100644
--- a/drivers/virt/coco/tdx-host/Kconfig
+++ b/drivers/virt/coco/tdx-host/Kconfig
@@ -12,6 +12,8 @@ config TDX_HOST_SERVICES
 config INTEL_TDX_MODULE_UPDATE
 	bool "Intel TDX module runtime update"
 	depends on TDX_HOST_SERVICES
+	select FW_LOADER
+	select FW_UPLOAD
 	help
 	  This enables the kernel to support TDX module runtime update. This
 	  allows the admin to update the TDX module to another compatible
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index f4ce89522806..06487de2ebfe 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -6,6 +6,7 @@
  */
 
 #include <linux/device/faux.h>
+#include <linux/firmware.h>
 #include <linux/module.h>
 #include <linux/mod_devicetable.h>
 #include <linux/sysfs.h>
@@ -20,6 +21,13 @@ static const struct x86_cpu_id tdx_host_ids[] = {
 };
 MODULE_DEVICE_TABLE(x86cpu, tdx_host_ids);
 
+struct tdx_fw_upload_status {
+	bool cancel_request;
+};
+
+struct fw_upload *tdx_fwl;
+static struct tdx_fw_upload_status tdx_fw_upload_status;
+
 static ssize_t version_show(struct device *dev, struct device_attribute *attr,
 			    char *buf)
 {
@@ -100,6 +108,120 @@ static const struct attribute_group *tdx_host_groups[] = {
 	NULL,
 };
 
+static enum fw_upload_err tdx_fw_prepare(struct fw_upload *fwl,
+					 const u8 *data, u32 size)
+{
+	struct tdx_fw_upload_status *status = fwl->dd_handle;
+
+	status->cancel_request = false;
+
+	return FW_UPLOAD_ERR_NONE;
+}
+
+static enum fw_upload_err tdx_fw_write(struct fw_upload *fwl, const u8 *data,
+				       u32 offset, u32 size, u32 *written)
+{
+	struct tdx_fw_upload_status *status = fwl->dd_handle;
+	int ret;
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
+static void seamldr_init(struct device *dev)
+{
+	const struct tdx_sys_info *tdx_sysinfo = tdx_get_sysinfo();
+	int ret;
+
+	if (WARN_ON_ONCE(!tdx_sysinfo))
+		return;
+
+	if (!IS_ENABLED(CONFIG_INTEL_TDX_MODULE_UPDATE))
+		return;
+
+	if (!tdx_supports_runtime_update(tdx_sysinfo))
+		pr_info("Current TDX Module cannot be updated. Consider BIOS updates\n");
+
+	tdx_fwl = firmware_upload_register(THIS_MODULE, dev, "seamldr_upload",
+					   &tdx_fw_ops, &tdx_fw_upload_status);
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
+	seamldr_init(&fdev->dev);
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
@@ -107,7 +229,7 @@ static int __init tdx_host_init(void)
 	if (!x86_match_cpu(tdx_host_ids) || !tdx_get_sysinfo())
 		return -ENODEV;
 
-	fdev = faux_device_create_with_groups(KBUILD_MODNAME, NULL, NULL, tdx_host_groups);
+	fdev = faux_device_create_with_groups(KBUILD_MODNAME, NULL, &tdx_host_ops, tdx_host_groups);
 	if (!fdev)
 		return -ENODEV;

---

## [12] Chao Gao — 2026-01-23
*Subject: [PATCH v3 11/26] x86/virt/seamldr: Block TDX Module updates if any CPU is offline*

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
index af7a6621e5e0..88388aa0fb5f 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -6,6 +6,8 @@
  */
 #define pr_fmt(fmt)	"seamldr: " fmt
 
+#include <linux/cpuhplock.h>
+#include <linux/cpumask.h>
 #include <linux/irqflags.h>
 #include <linux/mm.h>
 #include <linux/types.h>
@@ -84,6 +86,12 @@ int seamldr_install_module(const u8 *data, u32 size)
 	if (!is_vmalloc_addr(data))
 		return -EINVAL;
 
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

## [13] Chao Gao — 2026-01-23
*Subject: [PATCH v3 12/26] x86/virt/seamldr: Verify availability of slots for TDX Module updates*

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
index 88388aa0fb5f..d1d4f96c4963 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -83,6 +83,14 @@ EXPORT_SYMBOL_FOR_MODULES(seamldr_get_info, "tdx-host");
  */
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
 	if (!is_vmalloc_addr(data))
 		return -EINVAL;

---

## [14] Chao Gao — 2026-01-23
*Subject: [PATCH v3 13/26] x86/virt/seamldr: Allocate and populate a module update request*

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
v3:
 - Print tdx_blob version in hex [Binbin]
 - Drop redundant sigstruct alignment check [Yilun]
 - Note buffers passed from firmware upload infrastructure are
   vmalloc()'d above alloc_seamldr_params()
---
 arch/x86/virt/vmx/tdx/seamldr.c | 158 ++++++++++++++++++++++++++++++++
 1 file changed, 158 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index d1d4f96c4963..d136ef89cd36 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -6,10 +6,12 @@
  */
 #define pr_fmt(fmt)	"seamldr: " fmt
 
+#include <linux/cleanup.h>
 #include <linux/cpuhplock.h>
 #include <linux/cpumask.h>
 #include <linux/irqflags.h>
 #include <linux/mm.h>
+#include <linux/slab.h>
 #include <linux/types.h>
 
 #include <asm/seamldr.h>
@@ -19,6 +21,26 @@
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
@@ -73,6 +95,137 @@ const struct seamldr_info *seamldr_get_info(void)
 }
 EXPORT_SYMBOL_FOR_MODULES(seamldr_get_info, "tdx-host");
 
+static void free_seamldr_params(struct seamldr_params *params)
+{
+	free_page((unsigned long)params);
+}
+
+/*
+ * Allocate and populate a seamldr_params.
+ * Note that both @module and @sig should be vmalloc'd memory.
+ */
+static struct seamldr_params *alloc_seamldr_params(const void *module, unsigned int module_size,
+						   const void *sig, unsigned int sig_size)
+{
+	struct seamldr_params *params;
+	const u8 *ptr;
+	int i;
+
+	BUILD_BUG_ON(sizeof(struct seamldr_params) != SZ_4K);
+	if (module_size > SEAMLDR_MAX_NR_MODULE_4KB_PAGES * SZ_4K)
+		return ERR_PTR(-EINVAL);
+
+	if (!IS_ALIGNED(module_size, SZ_4K) || sig_size != SZ_4K ||
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
+	/*
+	 * Don't assume @sig is page-aligned although it is 4KB-aligned.
+	 * Always add the in-page offset to get the physical address.
+	 */
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
+		pr_err("unsupported blob version: %x\n", blob->version);
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
 /**
  * seamldr_install_module - Install a new TDX module
  * @data: Pointer to the TDX module binary data. It should be vmalloc'd
@@ -94,6 +247,11 @@ int seamldr_install_module(const u8 *data, u32 size)
 	if (!is_vmalloc_addr(data))
 		return -EINVAL;
 
+	struct seamldr_params *params __free(free_seamldr_params) =
+						init_seamldr_params(data, size);
+	if (IS_ERR(params))
+		return PTR_ERR(params);
+
 	guard(cpus_read_lock)();
 	if (!cpumask_equal(cpu_online_mask, cpu_present_mask)) {
 		pr_err("Cannot update TDX module if any CPU is offline\n");

---

## [15] Chao Gao — 2026-01-23
*Subject: [PATCH v3 14/26] x86/virt/seamldr: Introduce skeleton for TDX Module updates*

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
index d136ef89cd36..06080c648b02 100644
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
@@ -223,6 +225,68 @@ static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
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
 
@@ -237,6 +301,7 @@ DEFINE_FREE(free_seamldr_params, struct seamldr_params *,
 int seamldr_install_module(const u8 *data, u32 size)
 {
 	const struct seamldr_info *info = seamldr_get_info();
+	int ret;
 
 	if (!info)
 		return -EIO;
@@ -258,7 +323,11 @@ int seamldr_install_module(const u8 *data, u32 size)
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

## [16] Chao Gao — 2026-01-23
*Subject: [PATCH v3 15/26] x86/virt/seamldr: Abort updates if errors occurred midway*

The TDX Module update process has multiple stages, each of which may
encounter failures.

The current state machine of updates proceeds to the next stage
regardless of errors. But continuing updates when errors occur midway
is pointless.

If a CPU encounters an error, abort the update by setting a flag and
exiting the execution loop. Note that this CPU doesn't acknowledge the
current stage. This will keep all other CPUs in the current stage until
they see the flag and exit the loop as well.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
v3:
 - Instead of fast-forward to the final stage, exit the execution loop
   directly.
---
 arch/x86/virt/vmx/tdx/seamldr.c | 10 ++++++++--
 1 file changed, 8 insertions(+), 2 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 06080c648b02..a13d526b38a7 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -239,6 +239,7 @@ enum tdp_state {
 static struct {
 	enum tdp_state state;
 	atomic_t thread_ack;
+	atomic_t failed;
 } tdp_data;
 
 static void set_target_state(enum tdp_state state)
@@ -277,12 +278,16 @@ static int do_seamldr_install_module(void *params)
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
@@ -323,6 +328,7 @@ int seamldr_install_module(const u8 *data, u32 size)
 		return -EBUSY;
 	}
 
+	atomic_set(&tdp_data.failed, 0);
 	set_target_state(TDP_START + 1);
 	ret = stop_machine_cpuslocked(do_seamldr_install_module, params, cpu_online_mask);
 	if (ret)

---

## [17] Chao Gao — 2026-01-23
*Subject: [PATCH v3 16/26] x86/virt/seamldr: Shut down the current TDX module*

TDX Module updates request shutting down the existing TDX module.
During this shutdown, the module generates hand-off data, which captures
the module's states essential for preserving running TDs. The new TDX
Module can utilize this hand-off data to establish its states.

Invoke the TDH_SYS_SHUTDOWN SEAMCALL on one CPU to perform the shutdown.
This SEAMCALL requires a hand-off module version. Use the module's own
hand-off version, as it is the highest version the module can produce and
is more likely to be compatible with new modules as new modules likely have
higher hand-off version.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
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
index a13d526b38a7..76f404d1115c 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -19,6 +19,7 @@
 #include <asm/seamldr.h>
 
 #include "seamcall.h"
+#include "tdx.h"
 
 /* P-SEAMLDR SEAMCALL leaf function */
 #define P_SEAMLDR_INFO			0x8000000000000000
@@ -233,6 +234,7 @@ static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
  */
 enum tdp_state {
 	TDP_START,
+	TDP_SHUTDOWN,
 	TDP_DONE,
 };
 
@@ -265,8 +267,12 @@ static void ack_state(void)
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
@@ -275,6 +281,10 @@ static int do_seamldr_install_module(void *params)
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
index a0990c5dd78d..8b36a80cf229 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1175,6 +1175,22 @@ int tdx_enable(void)
 }
 EXPORT_SYMBOL_FOR_KVM(tdx_enable);
 
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
index 4c9917a9c2c3..7f4ed9af1d8d 100644
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
@@ -115,6 +127,7 @@ static int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 	ret = ret ?: get_tdx_sys_info_tdmr(&sysinfo->tdmr);
 	ret = ret ?: get_tdx_sys_info_td_ctrl(&sysinfo->td_ctrl);
 	ret = ret ?: get_tdx_sys_info_td_conf(&sysinfo->td_conf);
+	ret = ret ?: get_tdx_sys_info_handoff(&sysinfo->handoff);
 
 	return ret;
 }

---

## [18] Chao Gao — 2026-01-23
*Subject: [PATCH v3 17/26] x86/virt/tdx: Reset software states after TDX module shutdown*

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
 arch/x86/virt/vmx/tdx/tdx.c | 17 ++++++++++++++---
 1 file changed, 14 insertions(+), 3 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 8b36a80cf229..2763c1869b78 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -54,6 +54,8 @@ static struct tdmr_info_list tdx_tdmr_list;
 
 static enum tdx_module_status_t tdx_module_status;
 static DEFINE_MUTEX(tdx_module_lock);
+static bool sysinit_done;
+static int sysinit_ret;
 
 /* All TDX-usable memory regions.  Protected by mem_hotplug_lock. */
 static LIST_HEAD(tdx_memlist);
@@ -69,8 +71,6 @@ static int try_init_module_global(void)
 {
 	struct tdx_module_args args = {};
 	static DEFINE_RAW_SPINLOCK(sysinit_lock);
-	static bool sysinit_done;
-	static int sysinit_ret;
 
 	lockdep_assert_irqs_disabled();
 
@@ -1178,6 +1178,7 @@ EXPORT_SYMBOL_FOR_KVM(tdx_enable);
 int tdx_module_shutdown(void)
 {
 	struct tdx_module_args args = {};
+	int ret, cpu;
 
 	/*
 	 * Shut down the TDX Module and prepare handoff data for the next
@@ -1188,7 +1189,17 @@ int tdx_module_shutdown(void)
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

## [19] Chao Gao — 2026-01-23
*Subject: [PATCH v3 18/26] x86/virt/seamldr: Log TDX Module update failures*

If failures occur after the TDX Module has been successfully shut down,
they are unrecoverable. The kernel cannot restore the previous TDX
Module to a running state. All subsequent SEAMCALLs to the TDX Module
will fail, so TDs cannot continue to run.

Log a message to clarify that SEAMCALL errors are expected in this case.

To prevent TDX Module update failures, admins are encouraged to use the
user space tool [1] that will perform compatibility and integrity checks
that guarantee TDX Module update success.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
Link: https://github.com/intel/tdx-module-binaries/blob/main/version_select_and_load.py # [1]
---
v3:
 - Rephrase the changelog to eliminate the confusing uses of 'i.e.' and 'e.g.'
   [Dave/Yilun]
---
 arch/x86/virt/vmx/tdx/seamldr.c | 15 +++++++++++++--
 1 file changed, 13 insertions(+), 2 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 76f404d1115c..b497fa72ebb6 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -260,6 +260,14 @@ static void ack_state(void)
 		set_target_state(tdp_data.state + 1);
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
@@ -289,10 +297,13 @@ static int do_seamldr_install_module(void *params)
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

## [20] Chao Gao — 2026-01-23
*Subject: [PATCH v3 19/26] x86/virt/seamldr: Install a new TDX Module*

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
 arch/x86/virt/vmx/tdx/seamldr.c | 12 +++++++++++-
 1 file changed, 11 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index b497fa72ebb6..13c34e6378e0 100644
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
@@ -235,6 +238,7 @@ static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
 enum tdp_state {
 	TDP_START,
 	TDP_SHUTDOWN,
+	TDP_CPU_INSTALL,
 	TDP_DONE,
 };
 
@@ -272,9 +276,10 @@ static void print_update_failure_message(void)
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
@@ -293,6 +298,11 @@ static int do_seamldr_install_module(void *params)
 				if (primary)
 					ret = tdx_module_shutdown();
 				break;
+			case TDP_CPU_INSTALL:
+				args.rcx = __pa(seamldr_params);
+				scoped_guard(raw_spinlock, &seamldr_lock)
+					ret = seamldr_call(P_SEAMLDR_INSTALL, &args);
+				break;
 			default:
 				break;
 			}

---

## [21] Chao Gao — 2026-01-23
*Subject: [PATCH v3 20/26] x86/virt/seamldr: Do TDX per-CPU initialization after updates*

After installing the new TDX module, each CPU should be initialized
again to make the CPU ready to run any other SEAMCALLs. So, call
tdx_cpu_enable() on all CPUs.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/virt/vmx/tdx/seamldr.c | 4 ++++
 1 file changed, 4 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 13c34e6378e0..ee672f381dd5 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -239,6 +239,7 @@ enum tdp_state {
 	TDP_START,
 	TDP_SHUTDOWN,
 	TDP_CPU_INSTALL,
+	TDP_CPU_INIT,
 	TDP_DONE,
 };
 
@@ -303,6 +304,9 @@ static int do_seamldr_install_module(void *seamldr_params)
 				scoped_guard(raw_spinlock, &seamldr_lock)
 					ret = seamldr_call(P_SEAMLDR_INSTALL, &args);
 				break;
+			case TDP_CPU_INIT:
+				ret = tdx_cpu_enable();
+				break;
 			default:
 				break;
 			}

---

## [22] Chao Gao — 2026-01-23
*Subject: [PATCH v3 21/26] x86/virt/tdx: Establish contexts for the new TDX Module*

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
v3:
 - use seamcall_prerr() rather than raw seamcall() [Binbin]
 - use pr_err() to print error message [Binbin]
---
 arch/x86/virt/vmx/tdx/seamldr.c |  5 +++++
 arch/x86/virt/vmx/tdx/tdx.c     | 16 ++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h     |  2 ++
 3 files changed, 23 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index ee672f381dd5..7fa68c0c6ce4 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -240,6 +240,7 @@ enum tdp_state {
 	TDP_SHUTDOWN,
 	TDP_CPU_INSTALL,
 	TDP_CPU_INIT,
+	TDP_RUN_UPDATE,
 	TDP_DONE,
 };
 
@@ -307,6 +308,10 @@ static int do_seamldr_install_module(void *seamldr_params)
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
index 2763c1869b78..2654aa169dda 100644
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

## [23] Chao Gao — 2026-01-23
*Subject: [PATCH v3 22/26] x86/virt/tdx: Update tdx_sysinfo and check features post-update*

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
index 7fa68c0c6ce4..d2d85114d6c4 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -357,6 +357,15 @@ int seamldr_install_module(const u8 *data, u32 size)
 	if (!is_vmalloc_addr(data))
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
@@ -374,6 +383,6 @@ int seamldr_install_module(const u8 *data, u32 size)
 	if (ret)
 		return ret;
 
-	return 0;
+	return tdx_module_post_update(sysinfo);
 }
 EXPORT_SYMBOL_FOR_MODULES(seamldr_install_module, "tdx-host");
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 2654aa169dda..5d3f3f3eeb7d 100644
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

## [24] Chao Gao — 2026-01-23
*Subject: [PATCH v3 23/26] x86/virt/tdx: Enable TDX Module runtime updates*

All pieces of TDX Module runtime updates are in place. Enable it if it
is supported.

Signed-off-by: Chao Gao <chao.gao@intel.com>
---
 arch/x86/include/asm/tdx.h  | 5 ++++-
 arch/x86/virt/vmx/tdx/tdx.h | 3 ---
 2 files changed, 4 insertions(+), 4 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index ffadbf64d0c1..0cd408f902f4 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -32,6 +32,9 @@
 #define TDX_SUCCESS		0ULL
 #define TDX_RND_NO_ENTROPY	0x8000020300000000ULL
 
+/* Bit definitions of TDX_FEATURES0 metadata field */
+#define TDX_FEATURES0_TD_PRESERVING	BIT(1)
+#define TDX_FEATURES0_NO_RBP_MOD	BIT(18)
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

## [25] Chao Gao — 2026-01-23
*Subject: [PATCH v3 24/26] x86/virt/seamldr: Extend sigstruct to 16KB*

Currently, each TDX Module has a 4KB sigstruct that is passed to the
P-SEAMLDR during module updates to authenticate the TDX Module binary.

Future TDX Module versions will pack additional information into the
sigstruct, which will exceed the current 4KB size limit.

To accommodate this, the sigstruct is being extended to support up to
16KB. Update seamldr_params and tdx-blob structures to handle the larger
sigstruct size.

Signed-off-by: Chao Gao <chao.gao@intel.com>
---
 arch/x86/virt/vmx/tdx/seamldr.c | 28 +++++++++++++++++++---------
 1 file changed, 19 insertions(+), 9 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index d2d85114d6c4..9e77b24f659c 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -29,6 +29,8 @@
 /* P-SEAMLDR can accept up to 496 4KB pages for TDX module binary */
 #define SEAMLDR_MAX_NR_MODULE_4KB_PAGES	496
 
+#define SEAMLDR_MAX_NR_SIG_4KB_PAGES	4
+
 /* scenario field in struct seamldr_params */
 #define SEAMLDR_SCENARIO_UPDATE		1
 
@@ -40,8 +42,8 @@
 struct seamldr_params {
 	u32	version;
 	u32	scenario;
-	u64	sigstruct_pa;
-	u8	reserved[104];
+	u64	sigstruct_pa[SEAMLDR_MAX_NR_SIG_4KB_PAGES];
+	u8	reserved[80];
 	u64	num_module_pages;
 	u64	mod_pages_pa_list[SEAMLDR_MAX_NR_MODULE_4KB_PAGES];
 } __packed;
@@ -121,7 +123,10 @@ static struct seamldr_params *alloc_seamldr_params(const void *module, unsigned
 	if (module_size > SEAMLDR_MAX_NR_MODULE_4KB_PAGES * SZ_4K)
 		return ERR_PTR(-EINVAL);
 
-	if (!IS_ALIGNED(module_size, SZ_4K) || sig_size != SZ_4K ||
+	if (sig_size > SEAMLDR_MAX_NR_SIG_4KB_PAGES * SZ_4K)
+		return ERR_PTR(-EINVAL);
+
+	if (!IS_ALIGNED(module_size, SZ_4K) || !IS_ALIGNED(sig_size, SZ_4K) ||
 	    !IS_ALIGNED((unsigned long)module, SZ_4K) ||
 	    !IS_ALIGNED((unsigned long)sig, SZ_4K))
 		return ERR_PTR(-EINVAL);
@@ -132,12 +137,17 @@ static struct seamldr_params *alloc_seamldr_params(const void *module, unsigned
 
 	params->scenario = SEAMLDR_SCENARIO_UPDATE;
 
-	/*
-	 * Don't assume @sig is page-aligned although it is 4KB-aligned.
-	 * Always add the in-page offset to get the physical address.
-	 */
-	params->sigstruct_pa = (vmalloc_to_pfn(sig) << PAGE_SHIFT) +
-			       ((unsigned long)sig & ~PAGE_MASK);
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
 	params->num_module_pages = module_size / SZ_4K;
 
 	ptr = module;

---

## [26] Chao Gao — 2026-01-23
*Subject: [PATCH v3 25/26] x86/virt/tdx: Avoid updates during update-sensitive operations*

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
Link: https://lore.kernel.org/linux-coco/aQIbM5m09G0FYTzE@google.com/ # [1]
Link: https://lore.kernel.org/linux-coco/CAGtprH_oR44Vx9Z0cfxvq5-QbyLmy_+Gn3tWm3wzHPmC1nC0eg@mail.gmail.com/ # [2]
---
 arch/x86/include/asm/tdx.h   | 13 +++++++++++--
 arch/x86/kvm/vmx/tdx_errno.h |  2 --
 arch/x86/virt/vmx/tdx/tdx.c  | 23 +++++++++++++++++++----
 3 files changed, 30 insertions(+), 8 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 0cd408f902f4..85746de7c528 100644
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
 #define TDX_FEATURES0_TD_PRESERVING	BIT(1)
 #define TDX_FEATURES0_NO_RBP_MOD	BIT(18)
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
index 5d3f3f3eeb7d..5b562255630b 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1175,10 +1175,13 @@ int tdx_enable(void)
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
 	 * hand-off version.
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

## [27] Chao Gao — 2026-01-23
*Subject: [PATCH v3 26/26] coco/tdx-host: Set and document TDX Module update expectations*

In rare cases, TDX Module updates may cause TD management operations to
fail if they occur during phases of the TD lifecycle that are sensitive
to update compatibility.

But not all combinations of P-SEAMLDR, kernel, and TDX Module have the
capability to detect and prevent said incompatibilities. Completely
disabling TDX Module updates on platforms without the capability would
be overkill, as these incompatibility cases are rare and can be
addressed by userspace through coordinated scheduling of updates and TD
management operations.

To set clear expectations for TDX Module updates, expose the capability
to detect and prevent these incompatibility cases via sysfs and
document the compatibility criteria and indications when those criteria
are violated.

Signed-off-by: Chao Gao <chao.gao@intel.com>
---
v3:
 - new, based on a reference patch from Dan Williams
---
 .../ABI/testing/sysfs-devices-faux-tdx-host   | 45 +++++++++++++++++++
 drivers/virt/coco/tdx-host/tdx-host.c         | 13 ++++++
 2 files changed, 58 insertions(+)

diff --git a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
index a3f155977016..81cb13e91f2a 100644
--- a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
+++ b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
@@ -29,3 +29,48 @@ Description:	(RO) Report the number of remaining updates that can be performed.
 		4.2 "SEAMLDR.INSTALL" for more information. The documentation is
 		available at:
 		https://cdrdv2-public.intel.com/739045/intel-tdx-seamldr-interface-specification.pdf
+
+What:		/sys/devices/faux/tdx_host/firmware/seamldr_upload
+Contact:	linux-coco@lists.linux.dev
+Description:	(Directory) The seamldr_upload directory implements the
+		fw_upload sysfs ABI, see
+		Documentation/ABI/testing/sysfs-class-firmware for the general
+		description of the attributes @data, @cancel, @error, @loading,
+		@remaining_size, and @status. This ABI facilitates "Compatible
+		TDX Module Updates". A compatible update is one that meets the
+		following criteria:
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
+		See tdx_host/compat_capable and
+		tdx_host/firmware/seamldr_upload/error. For details.
+
+What:		/sys/devices/faux/tdx_host/compat_capable
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) When present this attribute returns "1" to indicate that
+		the current seamldr, kernel, and TDX Module combination can
+		detect when an update conforms with the "Compatible TDX Module
+		Updates" criteria in the tdx_host/firmware/seamldr_upload description.
+		When this attribute is missing it is indeterminate whether an
+		update will violate the criteria.
+
+What:		/sys/devices/faux/tdx_host/firmware/seamldr_upload/error
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) See Documentation/ABI/testing/sysfs-class-firmware for
+		baseline expectations for this file. Updates that fail
+		compatibility checks end with the "device-busy" error in the
+		<STATUS>:<ERROR> format of this attribute. When this is
+		signalled current TDs and the current TDX Module stay running.
+		Other failures may result in all TDs being lost and further
+		TDX operations becoming impossible. This occurs when
+		/sys/devices/faux/tdx_host/version becomes unreadable.
diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 06487de2ebfe..8cc48e276533 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -45,8 +45,21 @@ static ssize_t version_show(struct device *dev, struct device_attribute *attr,
 }
 static DEVICE_ATTR_RO(version);
 
+static ssize_t compat_capable_show(struct device *dev, struct device_attribute *attr,
+				   char *buf)
+{
+	const struct tdx_sys_info *tdx_sysinfo = tdx_get_sysinfo();
+
+	if (!tdx_sysinfo)
+		return -ENXIO;
+
+	return sysfs_emit(buf, "%i\n", tdx_supports_update_compatibility(tdx_sysinfo));
+}
+static DEVICE_ATTR_RO(compat_capable);
+
 static struct attribute *tdx_host_attrs[] = {
 	&dev_attr_version.attr,
+	&dev_attr_compat_capable.attr,
 	NULL,
 };

---

## [28] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 04/26] coco/tdx-host: Introduce a "tdx_host" device*

On Fri, Jan 23, 2026 at 06:55:12AM -0800, Chao Gao wrote:
> --- /dev/null
> +++ b/drivers/virt/coco/tdx-host/tdx-host.c

Just a nit, the year has changed so could be updated.

Good to see the TDX host device get added:

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [29] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 05/26] coco/tdx-host: Expose TDX Module version*

On Fri, Jan 23, 2026 at 06:55:13AM -0800, Chao Gao wrote:
> Expose the TDX Module version to userspace via sysfs to aid module
> selection. Since the TDX faux device will drive module updates, expose

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [30] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 09/26] coco/tdx-host: Expose P-SEAMLDR information via
 sysfs*

On Fri, Jan 23, 2026 at 06:55:17AM -0800, Chao Gao wrote:
> TDX Module updates require userspace to select the appropriate module
> to load. Expose necessary information to facilitate this decision. Two

This is great to have:

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [31] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 10/26] coco/tdx-host: Implement FW_UPLOAD sysfs ABI
 for TDX Module updates*

On Fri, Jan 23, 2026 at 06:55:18AM -0800, Chao Gao wrote:
> The firmware upload framework provides a standard mechanism for firmware
> updates by allowing device drivers to expose sysfs interfaces for

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [32] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 01/26] x86/virt/tdx: Print SEAMCALL leaf numbers in
 decimal*

On Fri, Jan 23, 2026 at 06:55:09AM -0800, Chao Gao wrote:
> Both TDX spec and kernel defines SEAMCALL leaf numbers as decimal. Printing
> them in hex makes no sense. Correct it.

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [33] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 02/26] x86/virt/tdx: Use %# prefix for hex values in
 SEAMCALL error messages*

On Fri, Jan 23, 2026 at 06:55:10AM -0800, Chao Gao wrote:
> "%#" format specifier automatically adds the "0x" prefix and has one less
> character than "0x%".

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [34] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 03/26] x86/virt/tdx: Move low level SEAMCALL helpers
 out of <asm/tdx.h>*

On Fri, Jan 23, 2026 at 06:55:11AM -0800, Chao Gao wrote:
> From: Kai Huang <kai.huang@intel.com>
> 

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [35] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 06/26] x86/virt/tdx: Prepare to support P-SEAMLDR
 SEAMCALLs*

On Fri, Jan 23, 2026 at 06:55:14AM -0800, Chao Gao wrote:
> P-SEAMLDR is another component alongside the TDX module within the
> protected SEAM range. P-SEAMLDR can update the TDX module at runtime.

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [36] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 07/26] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On Fri, Jan 23, 2026 at 06:55:15AM -0800, Chao Gao wrote:
> --- a/drivers/virt/coco/tdx-host/Kconfig
> +++ b/drivers/virt/coco/tdx-host/Kconfig

How about leave out the first "This" above:

	 Enable the kernel to support TDX module runtime update. This
	 allows the admin to update the TDX module to another compatible
	 version without the need to terminate running TDX guests.

Other than that:

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [37] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 08/26] x86/virt/seamldr: Retrieve P-SEAMLDR information*

On Fri, Jan 23, 2026 at 06:55:16AM -0800, Chao Gao wrote:
> P-SEAMLDR returns its information e.g., version and supported features, in
> response to the SEAMLDR.INFO SEAMCALL.

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [38] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 11/26] x86/virt/seamldr: Block TDX Module updates if
 any CPU is offline*

On Fri, Jan 23, 2026 at 06:55:19AM -0800, Chao Gao wrote:
> P-SEAMLDR requires every CPU to call the SEAMLDR.INSTALL SEAMCALL during
> updates.  So, every CPU should be online.

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [39] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 12/26] x86/virt/seamldr: Verify availability of slots
 for TDX Module updates*

On Fri, Jan 23, 2026 at 06:55:20AM -0800, Chao Gao wrote:
> The CPU keeps track of TCB versions for each TDX Module that has been
> loaded. Since this tracking database has finite capacity, there's a maximum

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [40] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 13/26] x86/virt/seamldr: Allocate and populate a
 module update request*

On Fri, Jan 23, 2026 at 06:55:21AM -0800, Chao Gao wrote:
> A module update request is a struct used to describe information about
> the TDX module to install. It is part of the P-SEAMLDR <-> kernel ABI

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [41] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 14/26] x86/virt/seamldr: Introduce skeleton for TDX
 Module updates*

On Fri, Jan 23, 2026 at 06:55:22AM -0800, Chao Gao wrote:
> The P-SEAMLDR requires that no TDX Module SEAMCALLs are invoked during a
> runtime TDX Module update.

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [42] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 15/26] x86/virt/seamldr: Abort updates if errors
 occurred midway*

On Fri, Jan 23, 2026 at 06:55:23AM -0800, Chao Gao wrote:
> The TDX Module update process has multiple stages, each of which may
> encounter failures.

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [43] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 16/26] x86/virt/seamldr: Shut down the current TDX
 module*

On Fri, Jan 23, 2026 at 06:55:24AM -0800, Chao Gao wrote:
> TDX Module updates request shutting down the existing TDX module.
> During this shutdown, the module generates hand-off data, which captures

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [44] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 17/26] x86/virt/tdx: Reset software states after TDX
 module shutdown*

On Fri, Jan 23, 2026 at 06:55:25AM -0800, Chao Gao wrote:
> The TDX module requires a one-time global initialization (TDH.SYS.INIT) and
> per-CPU initialization (TDH.SYS.LP.INIT) before use. These initializations

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [45] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 18/26] x86/virt/seamldr: Log TDX Module update failures*

On Fri, Jan 23, 2026 at 06:55:26AM -0800, Chao Gao wrote:
> If failures occur after the TDX Module has been successfully shut down,
> they are unrecoverable. The kernel cannot restore the previous TDX

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [46] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 19/26] x86/virt/seamldr: Install a new TDX Module*

On Fri, Jan 23, 2026 at 06:55:27AM -0800, Chao Gao wrote:
> After shutting down the running TDX module, the next step is to install the
> new TDX Module supplied by userspace.

Maybe clarify the next step part a bit with something like "the next step
in upgrading the TDX module"?

Otherwise the description can  be a bit hard to follow if not seen in the
patch email thread context.

Other than that:

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [47] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 20/26] x86/virt/seamldr: Do TDX per-CPU initialization
 after updates*

On Fri, Jan 23, 2026 at 06:55:28AM -0800, Chao Gao wrote:
> After installing the new TDX module, each CPU should be initialized
> again to make the CPU ready to run any other SEAMCALLs. So, call

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [48] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 21/26] x86/virt/tdx: Establish contexts for the new
 TDX Module*

On Fri, Jan 23, 2026 at 06:55:29AM -0800, Chao Gao wrote:
> After being installed, the new TDX Module shouldn't re-configure the
> global HKID, TDMRs or PAMTs. Instead, to preserve running TDs, it should

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [49] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 22/26] x86/virt/tdx: Update tdx_sysinfo and check
 features post-update*

On Fri, Jan 23, 2026 at 06:55:30AM -0800, Chao Gao wrote:
> +int tdx_module_post_update(struct tdx_sys_info *info)
> +{
...
> +	/*
> +	 * Blindly refreshing the entire tdx_sysinfo could disrupt running

To me it seems that a Linux a TDX module loader recommending a BIOS module
loader is not very user friendly :)

Anyways that more stuff for future so:

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [50] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 23/26] x86/virt/tdx: Enable TDX Module runtime updates*

On Fri, Jan 23, 2026 at 06:55:31AM -0800, Chao Gao wrote:
> --- a/arch/x86/include/asm/tdx.h
> +++ b/arch/x86/include/asm/tdx.h

How about let's put these defines into arch/x86/include/asm/shared/tdx.h
instead? And use BIT_ULL?

This would allow cleaning up arch/x86/kvm/vmx/tdx.c in a follow-up patch
for MD_FIELD_ID_FEATURES0_TOPOLOGY_ENUM to use TDX_FEATURES0_TOPOLOGY_ENUM
BIT_ULL(20).

Of course it can be done later on too, so:

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [51] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 24/26] x86/virt/seamldr: Extend sigstruct to 16KB*

On Fri, Jan 23, 2026 at 06:55:32AM -0800, Chao Gao wrote:
> Currently, each TDX Module has a 4KB sigstruct that is passed to the
> P-SEAMLDR during module updates to authenticate the TDX Module binary.

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [52] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 25/26] x86/virt/tdx: Avoid updates during
 update-sensitive operations*

On Fri, Jan 23, 2026 at 06:55:33AM -0800, Chao Gao wrote:
> TDX Module updates may cause TD management operations to fail if they
> occur during phases of the TD lifecycle that are sensitive to update

Looks good to me:

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [53] Tony Lindgren — 2026-01-26
*Subject: Re: [PATCH v3 26/26] coco/tdx-host: Set and document TDX Module
 update expectations*

On Fri, Jan 23, 2026 at 06:55:34AM -0800, Chao Gao wrote:
> In rare cases, TDX Module updates may cause TD management operations to
> fail if they occur during phases of the TD lifecycle that are sensitive

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [54] dan.j.williams@intel.com — 2026-01-26
*Subject: Re: [PATCH v3 26/26] coco/tdx-host: Set and document TDX Module
 update expectations*

Chao Gao wrote:
> In rare cases, TDX Module updates may cause TD management operations to
> fail if they occur during phases of the TD lifecycle that are sensitive

No. The TDX Module wants to be able to claim that some updates are
compatible when they are not. If Linux takes on additional exclusions it
modestly increases the scope of changes that can be included in an
update. It is not possible to claim "rare" if module updates routinely
include that problematic scope.

> But not all combinations of P-SEAMLDR, kernel, and TDX Module have the
> capability to detect and prevent said incompatibilities. Completely

"Completely disabling" is not the tradeoff. The tradeoff is whether or
not the TDX Module meets Linux compatible update requirements or not.

> To set clear expectations for TDX Module updates, expose the capability
> to detect and prevent these incompatibility cases via sysfs and

Linux derives no benefit from a "compat_capable" kernel ABI. Yes, the
internals must export the error condition on collision. I am not
debating that nor revisiting the decision of pre-update-fail, vs
post-collision-notify. However, if the module violates the Linux
expectations that is the module's issue to document or preclude. The
fact that the compatibility contract is ambiguous to the kernel is a
feature. It puts the onus squarely on module updates to be documented
(or tools updated to understand) as meeting or violating Linux
compatibility expectations.

> Signed-off-by: Chao Gao <chao.gao@intel.com>
> ---

One of the details that is missing is the protocol (module documentation
or tooling) to determine ahead of time if an update is compatible. That
obviates the need for "compat_capable" ABI which serves no long term
purpose. Specifically, the expectation is "run non-compatible updates at
your own operational risk".

So, remove "compat_capable" ABI. Amend the "error" ABI documentation
with the details for avoiding failures and the risk of running updates
on configurations that support update but not collision avoidance.

> ---
>  .../ABI/testing/sysfs-devices-faux-tdx-host   | 45 +++++++++++++++++++
[..]
> 
> +What:		/sys/devices/faux/tdx_host/firmware/seamldr_upload/error

This wants something like
---
See version_select_and_load.py [1] documentation for how to detect
compatible updates and whether the current platform components catch
errors or let them leak and cause potential TD attestation failures.

[1]: https://github.com/intel/confidential-computing.tdx.tdx-module.binaries/blob/main/version_select_and_load.py
---

...although I do not immediately see any help text or Documentation for
that tool.

---

## [55] Huang, Kai — 2026-01-27
*Subject: Re: [PATCH v3 13/26] x86/virt/seamldr: Allocate and populate a module
 update request*

> +/*
> + * Allocate and populate a seamldr_params.

Based on the the blob format link below, we have 

struct tdx_blob
{
	...
	_u64 sigstruct[256]; // 2KB sigstruct,intel_tdx_module.so.sigstruct
	_u64 reserved2[256]; // Reserved space
	...
}

So it's clear SIGSTRUCT is just 2KB and the second half 2KB is "reserved
space".

Why is the "reserved space" treated as part of SIGSTRUCT here? 

> +
> +/*

Nit:  Perhaps s/resv/rsvd ?

"#grep rsvd arch/x86 -Rn" gave me a bunch of results but "#grep resv" gave
me much less (and part of the results were 'resvd' and 'resv_xx' instead of
plain 'resv').
  
> +	u8	data[];
> +} __packed;

For this structure, I need to click the link and open it in a browser to
understand where is the sigstruct and module, and ...

> +static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
> +{

... to see whether this code makes sense.

I understand the

	...
	u64	rsvd[N*512];
	u8	module[];

is painful to be declared explicitly in 'struct tdx_blob' because IIUC we
cannot put two flexible array members at the end of the structure.

But I think if we add 'sigstruct' to the 'struct tdx_blob', e.g.,

struct tdx_blob {
	u16	version;
	...
	u64	rsvd2[509];
	u64	sigstruct[256];
	u64	rsvd3[256];
	u64	data;
} __packed;

.. we can just use

	sig		= blob->sigstruct;
	sig_size	= 2K (or 4K I don't quite follow);

which is clearer to read IMHO?

> +	return alloc_seamldr_params(module, module_size, sig, sig_size);
> +}

---

## [56] Huang, Kai — 2026-01-27
*Subject: Re: [PATCH v3 24/26] x86/virt/seamldr: Extend sigstruct to 16KB*

On Fri, 2026-01-23 at 06:55 -0800, Gao, Chao wrote:
> Currently, each TDX Module has a 4KB sigstruct that is passed to the
> P-SEAMLDR during module updates to authenticate the TDX Module binary.

[...]

> Update seamldr_params and tdx-blob structures to handle the larger
> sigstruct size.

Nit: there's no update to 'struct tdx_blob' in this patch.

Btw, is there any spec/doc that mentions this publicly?

E.g., we do need some update to the TDX module blob doc, right?

---

## [57] Chao Gao — 2026-01-27
*Subject: Re: [PATCH v3 26/26] coco/tdx-host: Set and document TDX Module
 update expectations*

On Mon, Jan 26, 2026 at 02:14:18PM -0800, dan.j.williams@intel.com wrote:
>Chao Gao wrote:
>> In rare cases, TDX Module updates may cause TD management operations to

Agreed. We need to add metadata like crypto library version or equivalent
abstraction to the mapping file. This enables userspace to determine whether
module updates meet Linux compatibility requirements. I'll submit a request
for this metadata.

And actually, userspace can already determine if the TDX module supports
"collision avoidance" by reading the "tdx_features0" field from the mapping
file [1].

[1]: https://github.com/intel/confidential-computing.tdx.tdx-module.binaries/blob/main/mapping_file.json

>
>So, remove "compat_capable" ABI. Amend the "error" ABI documentation

Got it. I will modify this patch as follows:

diff --git a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
index a3f155977016..0a68e68375fa 100644
--- a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
+++ b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
@@ -29,3 +29,57 @@ Description:	(RO) Report the number of remaining updates that can be performed.
		4.2 "SEAMLDR.INSTALL" for more information. The documentation is
		available at:
		https://cdrdv2-public.intel.com/739045/intel-tdx-seamldr-interface-specification.pdf
+
+What:		/sys/devices/faux/tdx_host/firmware/seamldr_upload
+Contact:	linux-coco@lists.linux.dev
+Description:	(Directory) The seamldr_upload directory implements the
+		fw_upload sysfs ABI, see
+		Documentation/ABI/testing/sysfs-class-firmware for the general
+		description of the attributes @data, @cancel, @error, @loading,
+		@remaining_size, and @status. This ABI facilitates "Compatible
+		TDX Module Updates". A compatible update is one that meets the
+		following criteria:
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
+		See tdx_host/firmware/seamldr_upload/error for more details.
+
+What:		/sys/devices/faux/tdx_host/firmware/seamldr_upload/error
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) See Documentation/ABI/testing/sysfs-class-firmware for
+		baseline expectations for this file. The <ERROR> part in the
+		<STATUS>:<ERROR> format can be:
+
+		   "device-busy": Compatibility checks failed or not all CPUs
+		                  are online
+		   "flash-wearout": the number of updates reached the limit.
+		   "read-write-error": Memory allocation failed.
+		   "hw-error": Cannot communicate with P-SEAMLDR or TDX Module
+		   "firmware-invalid": The TDX Module to be installed is invalid
+		                       or other unexpected errors occurred.
+
+		"hw-error" or "firmware-invalid" may be fatal, causing all TDs
+		and the TDX Module to be lost and preventing further TDX
+		operations. This occurs when /sys/devices/faux/tdx_host/version
+		becomes unreadable after update failures. For other errors, TDs
+		and the (previous) TDX Module stay running.
+
+		On certain earlier TDX Module versions, incompatible updates may
+		not trigger "device-busy" errors but instead cause TD
+		attestation failures.
+
+		See version_select_and_load.py [1] documentation for how to
+		detect compatible updates and whether the current platform
+		components catch errors or let them leak and cause potential TD
+		attestation failures.
+		[1]: https://github.com/intel/confidential-computing.tdx.tdx-module.binaries/blob/main/version_select_and_load.py

---

## [58] dan.j.williams@intel.com — 2026-01-27
*Subject: Re: [PATCH v3 26/26] coco/tdx-host: Set and document TDX Module
 update expectations*

Chao Gao wrote:
[..]
> >So, remove "compat_capable" ABI. Amend the "error" ABI documentation
> >with the details for avoiding failures and the risk of running updates

Overall, looks good to me. You can add:

Reviewed-by: Dan Williams <dan.j.williams@intel.com>

...after a few additional fixups below:

> diff --git a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
> index a3f155977016..0a68e68375fa 100644

I would specify the exact unambiguous errno value that gets returned on
read when the version become indeterminate, like ENXIO.

> +		and the (previous) TDX Module stay running.
> +

I would just leave this out. It bitrots quickly and does not provide
any actionable information. This is not the kernel's responsibility...

> +
> +		See version_select_and_load.py [1] documentation for how to

...that detail about what happens when compat detection is missing
belongs in the tooling documentation. That documentation does not exist
yet, so this link needs to be replaced with a pointer to documentation
before this goes upstream. I am assuming that we want to create an
actual package that distributions can pick up as project? It might be
worth going through the exercise of packaging the binaries and the tool
as an rpm or deb to get that work bootstrapped.
"version_select_and_load" probably wants a better name like "tdxctl" or
similar.

Note that a tdxctl project would also attract features related to TDX
Connect to wrap common flows around the tdx_host device sysfs ABIs.

---

## [59] Binbin Wu — 2026-01-28
*Subject: Re: [PATCH v3 01/26] x86/virt/tdx: Print SEAMCALL leaf numbers in
 decimal*

On 1/23/2026 10:55 PM, Chao Gao wrote:
> Both TDX spec and kernel defines SEAMCALL leaf numbers as decimal. Printing
> them in hex makes no sense. Correct it.

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

> ---
> v2:

---

## [60] Binbin Wu — 2026-01-28
*Subject: Re: [PATCH v3 02/26] x86/virt/tdx: Use %# prefix for hex values in
 SEAMCALL error messages*

On 1/23/2026 10:55 PM, Chao Gao wrote:
> "%#" format specifier automatically adds the "0x" prefix and has one less
> character than "0x%".

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

> ---
> "0x%" is also used to print TDMR ranges. I didn't convert them to reduce

Generally, is there any preference for coding in Linux kernel about
"0x%" VS. "%#"? Or developers just make their own choices?


> 
> v2: new

---

## [61] Binbin Wu — 2026-01-28
*Subject: Re: [PATCH v3 03/26] x86/virt/tdx: Move low level SEAMCALL helpers
 out of <asm/tdx.h>*

On 1/23/2026 10:55 PM, Chao Gao wrote:
> From: Kai Huang <kai.huang@intel.com>
> 

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

One question below.

[...]

> diff --git a/arch/x86/virt/vmx/tdx/seamcall.h b/arch/x86/virt/vmx/tdx/seamcall.h
> new file mode 100644

Should this be updated to 2026?

---

## [62] Huang, Kai — 2026-01-28
*Subject: Re: [PATCH v3 09/26] coco/tdx-host: Expose P-SEAMLDR information via
 sysfs*

On Fri, 2026-01-23 at 06:55 -0800, Chao Gao wrote:
> -ATTRIBUTE_GROUPS(tdx_host);
> +

This 'tdx_host_group' can be static?

---

## [63] Binbin Wu — 2026-01-28
*Subject: Re: [PATCH v3 04/26] coco/tdx-host: Introduce a "tdx_host" device*

On 1/23/2026 10:55 PM, Chao Gao wrote:
[...]
> diff --git a/drivers/virt/coco/Kconfig b/drivers/virt/coco/Kconfig
> index df1cfaf26c65..f7691f64fbe3 100644

IIUC, the folder name "tdx-host" here stands for TDX host services?
Should it use CONFIG_TDX_HOST_SERVICES here?

>  obj-$(CONFIG_ARM_CCA_GUEST)	+= arm-cca-guest/
>  obj-$(CONFIG_TSM) 		+= tsm-core.o

Nit:
Update the year to 2026?

---

## [64] Huang, Kai — 2026-01-28
*Subject: Re: [PATCH v3 10/26] coco/tdx-host: Implement FW_UPLOAD sysfs ABI for
 TDX Module updates*

> 2. TDX Module Updates complete synchronously within .write(), meaning
>    .poll_complete() is only called after successful updates and therefore

Nit:

Why "updates" instead of "update"?  Is there multiple updates possible
within .write()?

[...]

> 
>  

Can 'tdx_fwl' be static?

[...]

> 
> +static void seamldr_init(struct device *dev)

What's the point of continuing if runtime update is not supported?

> +
> +	tdx_fwl = firmware_upload_register(THIS_MODULE, dev, "seamldr_upload",

IMHO you need a comment to explain why seamldr_init() doesn't return error
and tdx_host_probe() already returns success?

> +	return 0;
> +}

---

## [65] Binbin Wu — 2026-01-28
*Subject: Re: [PATCH v3 05/26] coco/tdx-host: Expose TDX Module version*

On 1/23/2026 10:55 PM, Chao Gao wrote:
> For TDX Module updates, userspace needs to select compatible update
> versions based on the current module version. This design delegates

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

---

## [66] Huang, Kai — 2026-01-28
*Subject: Re: [PATCH v3 13/26] x86/virt/seamldr: Allocate and populate a module
 update request*

> +/*
> + * Allocate and populate a seamldr_params.

Nit:

How about actually using is_vmalloc_addr() to check in the code rather than
documenting in the comment?

I see you have already checked the overall 'data' buffer is vmalloc()'ed in
seamldr_install_module() so the 'module' and 'sig' (part of 'data') must be
too.  But since is_vmalloc_addr() is cheap so I think it's also fine to do
the check here.  We can also WARN() so it can be used to catch bug.

> + */
> +static struct seamldr_params *alloc_seamldr_params(const void *module, unsigned int module_size,

[...]

> +	ptr = module;
> +	for (i = 0; i < params->num_module_pages; i++) {

[...]

> +/*
> + * Verify that the checksum of the entire blob is zero. The checksum is

[...]

> +	if (!verify_checksum(blob)) {
> +		pr_err("invalid checksum\n");

It's weird that we have do verify checksum manually, because hardware
normally catches that.

I suppose this is because we want to catch as many errors as possible before
actually asking P-SEAMLDR to do module update, since in order to do which we
have to shutdown the existing module first and there's no returning point
once we reach that?

If so a comment would be helpful.

Also, it's also weird that you have to write code for checksum on your own.
I guess the kernel should already have some library code for that.

I checked and it _seems_ the code in lib/checksum.c could be used?

I am not expert though, but I think we should use kernel lib code when we
can.

---

## [67] Binbin Wu — 2026-01-28
*Subject: Re: [PATCH v3 06/26] x86/virt/tdx: Prepare to support P-SEAMLDR
 SEAMCALLs*

On 1/23/2026 10:55 PM, Chao Gao wrote:
> P-SEAMLDR is another component alongside the TDX module within the
> protected SEAM range. P-SEAMLDR can update the TDX module at runtime.

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

---

## [68] Binbin Wu — 2026-01-28
*Subject: Re: [PATCH v3 07/26] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On 1/23/2026 10:55 PM, Chao Gao wrote:
> Software needs to talk with P-SEAMLDR via P-SEAMLDR SEAMCALLs. So, add a
> wrapper for P-SEAMLDR SEAMCALLs.

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

Two nits below.

> ---
> v2:

Update to 2026?

> + *
> + * Intel TDX module runtime update

s/VMPTSTR/VMPTRST

---

## [69] Binbin Wu — 2026-01-28
*Subject: Re: [PATCH v3 08/26] x86/virt/seamldr: Retrieve P-SEAMLDR information*

On 1/23/2026 10:55 PM, Chao Gao wrote:
> P-SEAMLDR returns its information e.g., version and supported features, in
> response to the SEAMLDR.INFO SEAMCALL.

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

One nit below.

[...]

> diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
> index b99d73f7bb08..6a83ae405fac 100644

No need to tag the local function with inline.

>  {
>  	unsigned long flags;

---

## [70] Chao Gao — 2026-01-28
*Subject: Re: [PATCH v3 13/26] x86/virt/seamldr: Allocate and populate a
 module update request*

On Tue, Jan 27, 2026 at 11:21:06AM +0800, Huang, Kai wrote:
>
>> +/*

Good question. Because the space is reserved for sigstruct expansion.

The __current__ SEAMLDR ABI accepts one 4KB page, but all __existing__
sigstructs are only 2KB. so, tdx_blob currently defines a 2KB sigstruct field
followed by 2KB of reserved space. We anticipate that sigstructs will
eventually exceed 4KB, so we added reserved3[N*512] to accommodate future
growth.

You're right. The current tdx_blob definition doesn't clearly indicate that
reserved2/3 are actually part of the sigstruct.

Does this revised tdx_blob definition make that clearer and better align with
this patch? The idea is to make tdx_blob generic enough to clearly represent:
a 4KB header, followed by 4KB-aligned sigstruct, followed by the TDX Module
binary. Current SEAMLDR ABI details or current sigstruct sizes are irrelevant.

struct tdx_blob
{
        _u16 version;              // Version number
        _u16 checksum;             // Checksum of the entire blob should be zero
        _u32 offset_of_module;     // Offset of the module binary intel_tdx_module.bin in bytes
        _u8  signature[8];         // Must be "TDX-BLOB"
        _u32 length;               // The length in bytes of the entire blob
        _u32 reserved0;            // Reserved space
        _u64 reserved1[509];       // Reserved space
        _u64 sigstruct[512 + N*512]; // sigstruct, 4KB aligned

	^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        _u8  module[];             // intel_tdx_module.bin, 4KB aligned, to the end of the file
}


>
>> +

Sure. Will do.

>"#grep rsvd arch/x86 -Rn" gave me a bunch of results but "#grep resv" gave
>me much less (and part of the results were 'resvd' and 'resv_xx' instead of

Yes.

>
>But I think if we add 'sigstruct' to the 'struct tdx_blob', e.g.,

The problem is hard-coding the sigstruct size to 2KB/4KB. This will soon no
longer hold.

But
	sig		= blob->data;
	sig_size	= blob->offset_of_module - sizeof(struct tdx_blob);

doesn't make that assumption, making it more future-proof.

>
>> +	return alloc_seamldr_params(module, module_size, sig, sig_size);

---

## [71] Chao Gao — 2026-01-28
*Subject: Re: [PATCH v3 02/26] x86/virt/tdx: Use %# prefix for hex values in
 SEAMCALL error messages*

On Wed, Jan 28, 2026 at 09:34:03AM +0800, Binbin Wu wrote:
>
>

There seems to be no clear guidance on "0x%x" vs. "%#x".

If anyone has strong objections to this change, I can definitely drop it. I
included this patch because Dan suggested it during his review, though I'm not
sure how strongly he feels about it.

I searched lore and found the example below where "%#x" is preferred in another
subsystem:

https://lore.kernel.org/all/20251202231352.GF1712166@ZenIV/

---

## [72] Chao Gao — 2026-01-28
*Subject: Re: [PATCH v3 03/26] x86/virt/tdx: Move low level SEAMCALL helpers
 out of <asm/tdx.h>*

On Wed, Jan 28, 2026 at 09:37:05AM +0800, Binbin Wu wrote:
>
>

Yes. And I may drop the copyright notice if it is not necessary.

According to [1][2], it seems to be optional or even discouraged.

[1]: https://lwn.net/Articles/912355/
[2]: https://www.linuxfoundation.org/blog/blog/copyright-notices-in-open-source-software-projects

---

## [73] Dave Hansen — 2026-01-28
*Subject: Re: [PATCH v3 02/26] x86/virt/tdx: Use %# prefix for hex values in
 SEAMCALL error messages*

On 1/23/26 06:55, Chao Gao wrote:
> "%#" format specifier automatically adds the "0x" prefix and has one less
> character than "0x%".

IMNHO, this is needless bikeshedding about existing code. It's only
function is going to be to distract reviewers from the parts of the set
that actually need review.

If this matters (it doesn't), send it as a separate patch, please.

---

## [74] Dave Hansen — 2026-01-28
*Subject: Re: [PATCH v3 01/26] x86/virt/tdx: Print SEAMCALL leaf numbers in
 decimal*

On 1/23/26 06:55, Chao Gao wrote:
> Both TDX spec and kernel defines SEAMCALL leaf numbers as decimal. Printing
> them in hex makes no sense. Correct it.

This patch has zero to do with "Runtime TDX Module update support". Why
is it in this series?

---

## [75] Dave Hansen — 2026-01-28
*Subject: Re: [PATCH v3 03/26] x86/virt/tdx: Move low level SEAMCALL helpers
 out of <asm/tdx.h>*

On 1/28/26 04:42, Chao Gao wrote:
>>> diff --git a/arch/x86/virt/vmx/tdx/seamcall.h b/arch/x86/virt/vmx/tdx/seamcall.h
>>> new file mode 100644

No.

The copyright is to document the timing of a creative action. Moving
code is not a creative action.

If you want to remove it, do it in another patch. If you move code, just
_move_ _the_ _code_. You can _maybe_ clean up whitespace if you want to
along the way. But that's it. Don't muck with it unless you have a
reason. A *good* reason.

---

## [76] Dave Hansen — 2026-01-28
*Subject: Re: [PATCH v3 03/26] x86/virt/tdx: Move low level SEAMCALL helpers
 out of <asm/tdx.h>*

On 1/23/26 06:55, Chao Gao wrote:
> +++ b/arch/x86/virt/vmx/tdx/seamcall.h

Moving the code to a local header is a good thing. The more private
these things are, the better.

I _do_ like when I see these things have a label in the filename like:

	internal.h

or even:

	seamcall_internal.h

That really catches your eye. It would also be ideal to have a small
blurb at the top of the file to say what its scope is, just to explain
what folks should be adding to it or not.

If you get a chance to add those, all the better. But either way:

Acked-by: Dave Hansen <dave.hansen@linux.intel.com>

---

## [77] Dave Hansen — 2026-01-28
*Subject: Re: [PATCH v3 04/26] coco/tdx-host: Introduce a "tdx_host" device*

On 1/26/26 01:52, Tony Lindgren wrote:
> On Fri, Jan 23, 2026 at 06:55:12AM -0800, Chao Gao wrote:
>> --- /dev/null

Folks, please stop this.

You can ask an patch author *if* this should be updated. But if they're
just last year's work, then the year needs to stay 2025. This isn't some
mechanical thing that you flip over when the year changes. You change it
when you meaningfully change the work.

---

## [78] Dave Hansen — 2026-01-28
*Subject: Re: [PATCH v3 05/26] coco/tdx-host: Expose TDX Module version*

On 1/23/26 06:55, Chao Gao wrote:
...
> This approach follows the pattern used by microcode updates and
> other CoCo implementations:

I kinda disagree with the idea that this follows existing patterns. It
uses a *NEW* pattern.

AMD doesn't use a faux device because they *HAVE* a PCI device in their
architecture. TDX doesn't have a PCI device in its hardware architecture.

ARM CCA doesn't exist in the tree.

CPU microcode doesn't use a faux device. For good reason. The microcode
version is *actually* per-cpu. It can differ between CPU cores. The TDX
module version is not per-cpu. There's one and only one global module.
This is the reason that we need a global, unique device for TDX.

I'm not saying that being new is a bad thing. But let's not pretend this
is following any kind of existing pattern. Let's explain *why* it needs
to be different.

---

## [79] Sagi Shahar — 2026-01-28
*Subject: Re: [PATCH v3 00/26] Runtime TDX Module update support*

On Fri, Jan 23, 2026 at 9:00 AM Chao Gao <chao.gao@intel.com> wrote:
>
> Hi Reviewers,

I see "x86/virt/tdx: Retrieve TDX module version" and "x86/virt/tdx:
Print TDX module version during init" in the github link but I don't
see them as part of this series. Were they posted/accepted as part of
a different series?

Trying to build this series without them fails since
tdx_sysinfo.version is undefined.

>
>    * Removing dependency on Sean's VMXON cleanups for now, the tdx-host device

---

## [80] Huang, Kai — 2026-01-28
*Subject: Re: [PATCH v3 13/26] x86/virt/seamldr: Allocate and populate a module
 update request*

On Wed, 2026-01-28 at 19:28 +0800, Gao, Chao wrote:
> On Tue, Jan 27, 2026 at 11:21:06AM +0800, Huang, Kai wrote:
> > 

Oh I see.

I think we have two perspectives here: 1) what P-SEAMLDR ABI requires for
module and sigstruct; 2) how does the kernel get them and pass to
alloc_seamldr_params().

IIUC, I now understand alloc_seamldr_params() is expecting the 'module',
'module_size', 'sig' and 'sig_size' to meet P-SEAMCALL's ABI.

Then would it be better to add a comment for the checks of 'module',
'module_size', 'sig' and 'sig_size' in alloc_seamldr_params() (below code)
that it is P-SEAMCALL ABI that has these requirement?

	if (!IS_ALIGNED(module_size, SZ_4K) || sig_size != SZ_4K ||
	    !IS_ALIGNED((unsigned long)module, SZ_4K) ||
	    !IS_ALIGNED((unsigned long)sig, SZ_4K))
		return ERR_PTR(-EINVAL);

Otherwise it's a bit confusing because these 4 arguments are passed to
alloc_seamldr_params() right from the layout of 'struct tdx_blob' which is a
"software-organized" structure which, theoretically, could have nothing to
do P-SEAMLDR ABI.


> so, tdx_blob currently defines a 2KB sigstruct field
> followed by 2KB of reserved space. We anticipate that sigstructs will

Yes it's clearer, from the perspective that how it matches your code to
calculate 'sig_size'.

> The idea is to make tdx_blob generic enough to clearly represent:
> a 4KB header, followed by 4KB-aligned sigstruct, followed by the TDX Module

A side topic:

I checked the SEAMLDR.INSTALL.  It appears the only requirement of the
SIGSTRUCT is it is 4K aligned.  There's no where in the ABI (certainly not
in SEAMLDR_PARAMS) to tell how does SEAMLDR.INSTALL verifies the size of
SIGSTRUCT.

Is this right?

When we bumping SIGSTRUCT to a larger size, do we have some kinda
enumeration that reports such?

From your patch 24, IIUC I don't see such enumeration or explicit opt-in,
because you just changes the layout of SEAMLDR_PARAM w/o even changing it's
version.

[...]

> > But I think if we add 'sigstruct' to the 'struct tdx_blob', e.g.,
> > 

Sure.  I am certainly fine with making it future-proof (albeit arguably you
could also change the way that how sig_size is calculated in the future,
i.e., in your patch 24).

But the real point is the code here needs to reflect the 'struct tdx_blob'
description in the doc.  But with the current doc I don't see they match to
each other:

  The doc says SIGSTRUCT is 2K but the code says it's 4K.

So I think you need to update the 'struct tdx_blob' description in the doc
to justify such code.

Btw, I think the link

  https://github.com/intel/tdx-module-binaries/blob/main/blob_structure.txt

is subject to change, both the link itself and it's content.

Do you think we should just make the layout of 'struct tdx_blob' as a
documentation patch and include that to this series?

---

## [81] Huang, Kai — 2026-01-28
*Subject: Re: [PATCH v3 24/26] x86/virt/seamldr: Extend sigstruct to 16KB*

On Fri, 2026-01-23 at 06:55 -0800, Chao Gao wrote:
> Currently, each TDX Module has a 4KB sigstruct that is passed to the
> P-SEAMLDR during module updates to authenticate the TDX Module binary.

Let's move the discussion here (from patch 13 -- sorry about that):

IIRC this patch just simply re-purposes couple of reserved space in
SEAMLDR_PARAMS (which is part of P-SEAMLDR ABI) w/o enumeration, explicit
opt-in whatever.  The code change here doesn't even bump up its version.

IIUC, if this code run on an old platform where SEAMLDR.INSTALL still only
works with 4K SIGSTRUCT, the SEAMLDR.INSTALL will only see part of the
SIGSTRUCT thus will likely fail.

How can we know whether a given 'struct tdx_blob' can work on an platform or
not?  Or am I missing anything?

---

## [82] Dave Hansen — 2026-01-28
*Subject: Re: [PATCH v3 06/26] x86/virt/tdx: Prepare to support P-SEAMLDR
 SEAMCALLs*

On 1/23/26 06:55, Chao Gao wrote:
> P-SEAMLDR is another component alongside the TDX module within the
> protected SEAM range. P-SEAMLDR can update the TDX module at runtime.

This text kinda bugs me. It's OK, but needs improvement.

First, don't explain the ABI in the changelog. Nobody cares that it's
bit 63.


Background:

	The TDX architecture uses the "SEAMCALL" instruction to
	communicate with SEAM mode software. Right now, the only SEAM
	mode software that the kernel communicates with is the TDX
	module. But, there are actually some components that run in SEAM
	mode but that are separate from the TDX module: that SEAM
	loaders. Right now, the only component that communicates with
	them is the BIOS which loads the TDX module itself at boot. But,
	to support updating the TDX module, the kernel now needs to be
	able to talk to one of the the SEAM loaders: the Persistent
	loader or "P-SEAMLDR".

Then do this part:

> P-SEAMLDR SEAMCALLs differ from SEAMCALLs of the TDX module in terms of
> error codes and the handling of the current VMCS.
Except I don't even know how the TDX module handles the current VMCS.
That probably needs to be in there. Or, it should be brought up in the
patch itself that implements this. Or, uplifted to the cover letter.

> In preparation for adding support for P-SEAMLDR SEAMCALLs, do the two
> following changes to SEAMCALL low-level helpers:



> diff --git a/arch/x86/virt/vmx/tdx/seamcall.h b/arch/x86/virt/vmx/tdx/seamcall.h
> index 0912e03fabfe..256f71d6ca70 100644

<sigh>

#define TDX_RND_NO_ENTROPY      0x8000020300000000ULL

So they're not even close values. They're not consistent or even a bit
off or anything.

Honestly, this needs a justification for why this was done this way. Why
can't "SEAM mode" be a monolithic thing from the kernel's perspective?

> +#define SEAMLDR_SEAMCALL_MASK	_BITUL(63)
> +

(un)likey() has two uses:

1. It's in performance critical code and compilers have been
   demonstrated to be generating bad code.
2. It's in code where it's not obvious what the fast path is
   and (un)likey() makes the code more readable.

Which one is this?

Second, this is nitpicky, but I'd rather this be:

	if (is_seamldr_call(fn))
		retry_code = SEAMLDR_RND_NO_ENTROPY;
	else
		retry_code = TDX_RND_NO_ENTROPY;

or even:

	retry_code = TDX_RND_NO_ENTROPY;
	if (is_seamldr_call(fn))
		retry_code = SEAMLDR_RND_NO_ENTROPY;

That makes it trivial that 'retry_code' can only have two values. It's
nitpicky because the original initialization is so close.

>  	do {
>  		ret = func(fn, args);

Oh, lovely.

Didn't you just propose changing the module SEAMCALL leaf numbers in
decimal? Isn't it a little crazy to do one in decimal and the other in hex?

I'd really rather just see the TDX documentation changed.

But, honestly, I'd probably just leave the thing in hex, drop this hunk,
and go thwack someone that writes TDX module documentation instead.

>  static __always_inline int sc_retry_prerr(sc_func_t func,
>  					  sc_err_func_t err_func,

So, honestly, for me, it's a NAK for this whole patch.

Go change the P-SEAMLDR to use the same error code as the TDX module,
and fix the documentation. No kernel changes, please.

---

## [83] Dave Hansen — 2026-01-28
*Subject: Re: [PATCH v3 07/26] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On 1/23/26 06:55, Chao Gao wrote:
> SEAMRET from the P-SEAMLDR clears the current VMCS structure pointed 
> to by the current-VMCS pointer. A VMM that invokes the P-SEAMLDR

That seems pretty mean.

This is going to need a lot more justification for why this is an
absolutely necessary requirement.

KVM folks, are you OK with this?

---

## [84] Dave Hansen — 2026-01-28
*Subject: Re: [PATCH v3 07/26] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On 1/23/26 06:55, Chao Gao wrote:
...
> +static __maybe_unused int seamldr_call(u64 fn, struct tdx_module_args *args)
> +{

Why is this here? We shouldn't be silently papering over kernel bugs.
This is a WARN_ON() at *best*, but it also begs the question of how a
non-SEAMLDR call even got here.

> +	/*
> +	 * SEAMRET from P-SEAMLDR invalidates the current VMCS.  Save/restore

I think you mean:

	WARN_ON(in_nmi());

> +	local_irq_save(flags);
> +

I'd much rather this be wrapped up in a helper function. We shouldn't
have to look at the horrors of inline assembly like this.

But this *REALLY* wants the KVM folks to look at it. One argument is
that with the inline assembly this is nice and self-contained. The other
argument is that this completely ignores all existing KVM infrastructure
and is parallel VMCS management.

I'd be shocked if this is the one and only place in the whole kernel
that can unceremoniously zap VMX state.

I'd *bet* that you don't really need to do the vmptrld and that KVM can
figure it out because it can vmptrld on demand anyway. Something along
the lines of:

	local_irq_disable();
	list_for_each(handwaving...)
		vmcs_clear();
	ret = seamldr_prerr(fn, args);
	local_irq_enable();	

Basically, zap this CPU's vmcs state and then make KVM reload it at some
later time.

I'm sure Sean and Paolo will tell me if I'm crazy.

> diff --git a/drivers/virt/coco/tdx-host/Kconfig b/drivers/virt/coco/tdx-host/Kconfig
> index e58bad148a35..6a9199e6c2c6 100644

... as opposed to the method that the kernel has to update the module
without terminating guests? ;)

> +	  If unsure, say N.

Let's call this:

 config
INTEL_TDX_ONLY_DISABLE_THIS_IF_YOU_HATE_SECURITY_AND_IF_YOU_DO_WHY_ARE_YOU_RUNNING_TDX?

Can we have question marks in config symbol names? ;)

But, seriously, what the heck? Who would disable security updates for
their confidential computing infrastructure? Is this some kind of
intelligence test for our users so that if someone disables it we can
just laugh at them?

---

## [85] Dave Hansen — 2026-01-28
*Subject: Re: [PATCH v3 08/26] x86/virt/seamldr: Retrieve P-SEAMLDR information*

On 1/23/26 06:55, Chao Gao wrote:
> P-SEAMLDR returns its information e.g., version and supported features, in
> response to the SEAMLDR.INFO SEAMCALL.

I don't need to know what the function name is. That's in the code.

> invoking SEAMLDR.INFO SEAMCALL in preparation for exposing P-SEAMLDR
> version and other necessary information to userspace.

I also want to know what spec you are getting this out of.

I think it's also worth calling out that there are SEAMLDR calls for both:

	SEAMLDR_INFO
and
	SEAMLDR_SEAMINFO

Which is astonishingly confusing. Please have mercy on folks that are
looking through the docs for the first time and explain this.

> diff --git a/arch/x86/include/asm/seamldr.h b/arch/x86/include/asm/seamldr.h
> new file mode 100644

/*
 * This called the "SEAMLDR_INFO" data structure and is defined
 * in "SEAM Loader (SEAMLDR) Interface Specification".
 */


> +	u32	version;
> +	u32	attributes;

Why not label this:

	u32	acm_x2apicid: /* unused by kernel */

?

> +	u32	num_remaining_updates;
> +	u8	reserved1[224];


/*
 * The SEAMLDR.INFO documentation requires
 * this to be aligned to a 256-byte boundary.
 */
> +static struct seamldr_info seamldr_info __aligned(256);
> +

I'd also prefer a

	BUILD_BUG_ON(sizeof(struct seamldr_info) != 2048);

just as a sanity check. It doesn't cost anything and it makes sure that
as you muck around with reserved fields and padding that there's at
least one check making sure it's OK.

---

## [86] Dave Hansen — 2026-01-28
*Subject: Re: [PATCH v3 08/26] x86/virt/seamldr: Retrieve P-SEAMLDR information*

On 1/23/26 06:55, Chao Gao wrote:
> +static struct seamldr_info seamldr_info __aligned(256);

I also wonder if this should be __read_mostly or even read-only after
boot. Is it ever modified?

---

## [87] Dave Hansen — 2026-01-28
*Subject: Re: [PATCH v3 09/26] coco/tdx-host: Expose P-SEAMLDR information via
 sysfs*

On 1/23/26 06:55, Chao Gao wrote:
...
> diff --git a/Documentation/ABI/testing/sysfs-devices-faux-tdx-host b/Documentation/ABI/testing/sysfs-devices-faux-tdx-host
> index 901abbae2e61..a3f155977016 100644

								checks ^

> +What:		/sys/devices/faux/tdx_host/seamldr/num_remaining_updates
> +Contact:	linux-coco@lists.linux.dev

Is it really the CPU? Or some SEAM software construct?

> +		After each successful update, the number reduces by one. Once it
> +		reaches zero, further updates will fail until next reboot. The

Zap the URL. It's just going bit rot. Keep the document name. That's
googleable.

> diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
> index 0424933b2560..f4ce89522806 100644

Uhh... seamldr_get_info() calls down into the SEAMLDR. It happily zaps
the VMCS and this is surely a slow thing. This also has 0444 permissions
which means *ANYONE* can call this. Constantly. As fast as they can make
a few syscalls.

Right?

Are there any concerns about making SEAMLDR calls? Are there any
system-wide performance implications? How long of an interrupt-blocking
blip is there for this?

Also, what's the locking around seamldr_get_info()? It writes into a
global, shared structure. I guess you disabled interrupts so it's
preempt safe at least. <sigh>

I guess it won't change *that* much. But, sheesh, it seems like an
awfully bad idea to have lots of CPUs writing into a common data
structure all at the same time.

---

## [88] Chao Gao — 2026-01-29
*Subject: Re: [PATCH v3 00/26] Runtime TDX Module update support*

On Wed, Jan 28, 2026 at 11:52:57AM -0600, Sagi Shahar wrote:
>On Fri, Jan 23, 2026 at 9:00 AM Chao Gao <chao.gao@intel.com> wrote:
>>

Yes. https://lore.kernel.org/kvm/20260109-tdx_print_module_version-v2-0-e10e4ca5b450@intel.com/

---

## [89] Chao Gao — 2026-01-29
*Subject: Re: [PATCH v3 01/26] x86/virt/tdx: Print SEAMCALL leaf numbers in
 decimal*

On Wed, Jan 28, 2026 at 08:26:43AM -0800, Dave Hansen wrote:
>On 1/23/26 06:55, Chao Gao wrote:
>> Both TDX spec and kernel defines SEAMCALL leaf numbers as decimal. Printing

Will drop it.

It was included because it came up during review of previous versions.

---

## [90] Xu Yilun — 2026-01-29
*Subject: Re: [PATCH v3 04/26] coco/tdx-host: Introduce a "tdx_host" device*

> > index cb52021912b3..b323b0ae4f82 100644
> > --- a/drivers/virt/coco/Makefile

Yes. But I think it is fine here to express "seach into the folder if
dependency meets".

For this patch,

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

> Should it use CONFIG_TDX_HOST_SERVICES here?

---

## [91] Xu Yilun — 2026-01-29
*Subject: Re: [PATCH v3 05/26] coco/tdx-host: Expose TDX Module version*

On Fri, Jan 23, 2026 at 06:55:13AM -0800, Chao Gao wrote:
> For TDX Module updates, userspace needs to select compatible update
> versions based on the current module version. This design delegates

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

---

## [92] Chao Gao — 2026-01-29
*Subject: Re: [PATCH v3 03/26] x86/virt/tdx: Move low level SEAMCALL helpers
 out of <asm/tdx.h>*

On Wed, Jan 28, 2026 at 08:37:35AM -0800, Dave Hansen wrote:
>On 1/23/26 06:55, Chao Gao wrote:
>> +++ b/arch/x86/virt/vmx/tdx/seamcall.h

Thanks.

I will rename it to "seamcall_internal.h" and add the following at the top:

/*
 * SEAMCALL utilities for TDX host-side operations.
 * 
 * Provides convenient wrappers around SEAMCALL assembly with retry logic,
 * error reporting and cache coherency tracking.
 */

---

## [93] Xu Yilun — 2026-01-29
*Subject: Re: [PATCH v3 06/26] x86/virt/tdx: Prepare to support P-SEAMLDR
 SEAMCALLs*

> >  static __always_inline int sc_retry_prerr(sc_func_t func,
> >  					  sc_err_func_t err_func,

I'm thinking of ways to avoid a new pseamldr version.

Could we just ask for a unified error code space for both SEAMCALL &
SEAMLDR CALL, eliminating overlaps. There is no overlap now, so this is
just another documentation fix.

Then with all the doc fixes, we only need minor code change:


@@ -127,7 +127,8 @@ static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
                preempt_disable();
                ret = __seamcall_dirty_cache(func, fn, args);
                preempt_enable();
-       } while (ret == TDX_RND_NO_ENTROPY && --retry);
+       } while ((ret == TDX_RND_NO_ENTROPY ||
+                 ret == SEAMLDR_RND_NO_ENTROPY) && --retry);


I think this is a balance. The existing error code philosophy for SEAM
is as informative as possible, e.g. all kinds of xxx_INVALID,
SEAMLDR_RND_NO_ENTROPY is not that evil among 200+ other error codes.

---

## [94] Chao Gao — 2026-01-29
*Subject: Re: [PATCH v3 03/26] x86/virt/tdx: Move low level SEAMCALL helpers
 out of <asm/tdx.h>*

On Wed, Jan 28, 2026 at 08:31:26AM -0800, Dave Hansen wrote:
>On 1/28/26 04:42, Chao Gao wrote:
>>>> diff --git a/arch/x86/virt/vmx/tdx/seamcall.h b/arch/x86/virt/vmx/tdx/seamcall.h

Sorry.  I am a bit confused..

>
>The copyright is to document the timing of a creative action. Moving

This sounds like we don't need to add copyright notices for moving code.

>
>If you want to remove it, do it in another patch. If you move code, just

But this sounds like the copyright notice should be kept.

Do you mean the copyright notices from the original files should be carried
over to the new file?

This patch extracts code from arch/x86/include/asm/tdx.h and
arch/x86/virt/vmx/tdx/tdx.c. They have:

	Copyright (C) 2021-2022 Intel Corporation
	Copyright(c) 2023 Intel Corporation.

So for the new file, the copyright notice should be

	Copyright (C) 2021-2023 Intel Corporation
?

---

## [95] Chao Gao — 2026-01-29
*Subject: Re: [PATCH v3 05/26] coco/tdx-host: Expose TDX Module version*

On Wed, Jan 28, 2026 at 09:01:35AM -0800, Dave Hansen wrote:
>On 1/23/26 06:55, Chao Gao wrote:
>...

Thanks. I understand your point. The pattern I was referring to is: using a
device (PCI device, virtual device, or faux device) and exposing
versions/metadata as device attributes.

You're right if we look at the details, they're not exactly the same pattern.
I'll revise the changelog to make this clearer.

---

## [96] Chao Gao — 2026-01-29
*Subject: Re: [PATCH v3 06/26] x86/virt/tdx: Prepare to support P-SEAMLDR
 SEAMCALLs*

On Wed, Jan 28, 2026 at 03:03:14PM -0800, Dave Hansen wrote:
>On 1/23/26 06:55, Chao Gao wrote:
>> P-SEAMLDR is another component alongside the TDX module within the

Thanks. This is much clearer than my version.

One tiny nit: NP-SEAMLDR isn't SEAM mode software. It is an authenticated code
module (ACM).

>
>Then do this part:

My logic was:

1. The kernel communicates with P-SEAMLDR via SEAMCALL, just like with the TDX
   Module.
2. But P-SEAMLDR SEAMCALLs and TDX Module SEAMCALLs are slightly different.

So we need some tweaks to the low-level helpers to add separate wrappers for
P-SEAMLDR SEAMCALLs.

To me, without mentioning #2, these tweaks in this patch (for separate wrappers
in the next patch) aren't justified.

<snip>

>>  static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
>>  			   struct tdx_module_args *args)

I think #2 although I am happy to drop "unlikely".

>
>Second, this is nitpicky, but I'd rather this be:

Will do.

<snip>

>> +static inline void seamldr_err(u64 fn, u64 err, struct tdx_module_args *args)
>> +{

Yes, that's crazy. I'll just reuse seamcall_err(), so leaf numbers will be
printed in hex for both the TDX Module and P-SEAMLDR

>
>I'd really rather just see the TDX documentation changed.

I'll submit a request for TDX documentation to display leaf numbers in both hex
and decimal.

>
>But, honestly, I'd probably just leave the thing in hex, drop this hunk,

This can be dropped if we don't need to add seamldr_err().

---

## [97] Dave Hansen — 2026-01-29
*Subject: Re: [PATCH v3 03/26] x86/virt/tdx: Move low level SEAMCALL helpers
 out of <asm/tdx.h>*

On 1/29/26 06:02, Chao Gao wrote:'
...
> But this sounds like the copyright notice should be kept.
> 

The most straightforward thing to do is to copy the gunk from the
original file:

	Copyright (C) 2021-2023 Intel Corporation

... which is as of today the "official" Intel way of doing it with the
"(C)" just like that.

along with:

	/* SPDX-License-Identifier: GPL-2.0 */

and a note in the changelog about what you did. There's no need to do
any more than that because that's what git is for.

---

## [98] Dave Hansen — 2026-01-29
*Subject: Re: [PATCH v3 06/26] x86/virt/tdx: Prepare to support P-SEAMLDR
 SEAMCALLs*

On 1/29/26 01:46, Xu Yilun wrote:
...
> Then with all the doc fixes, we only need minor code change:
> 

That's better than what was there in the past, but I do think even this
is pretty silly.

I mean, we (Intel) control all the components. These errors are for the
same dang thing. The people who wrote both components probably sit next
to each other. :)

I think I'd be a bit less grumpy if there was _anything_ else that
demanded a retry. So, let's try to extract the guarantee that the error
spaces are at least unified, in that a TDX module will never return
SEAMLDR_RND_NO_ENTROPY to mean something else and a SEAMLDR will never
return TDX_RND_NO_ENTROPY. Then, maybe talk them into doing a unified
thing from here on out.

But, for now, drop this patch. We'll just assume the P-SEAMLDR doesn't
have "no entropy" errors until this is sorted.

---

## [99] Dave Hansen — 2026-01-29
*Subject: Re: [PATCH v3 06/26] x86/virt/tdx: Prepare to support P-SEAMLDR
 SEAMCALLs*

On 1/29/26 06:55, Chao Gao wrote:
> On Wed, Jan 28, 2026 at 03:03:14PM -0800, Dave Hansen wrote:
...
> Thanks. This is much clearer than my version.
> 

Ahhh, thanks for the correction!

>> Then do this part:
>>

My objection is that you talk about the VMCS handling in here but
there's no actual VMCS handling. This is the changelog for patch 06/26,
not 07/26.

Don't talk about the VMCS handling here. When you do, make sure you give
enough background.

>>>  static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
>>>  			   struct tdx_module_args *args)

But why does it *MATTER*? Is it important to understand that SEAMLDR
calls are rarer than TDX module calls?

---

## [100] Xu Yilun — 2026-01-30
*Subject: Re: [PATCH v3 08/26] x86/virt/seamldr: Retrieve P-SEAMLDR information*

> I'd also prefer a
> 
                                                    ^
BUILD_BUG_ON(sizeof(struct seamldr_info) != 256);   is it?

> 
> just as a sanity check. It doesn't cost anything and it makes sure that

And I recently received a comments that "never __packed for naturally
aligned structures cause it leads to bad generated code and hurts
performance", but I really want to highlight nearby it is for a
formatted binary blob, so:

  struct seamldr_info {
	u32     version;
	u32     attributes;
	u32     vendor_id;
	u32     build_date;
	u16     build_num;
	u16     minor_version;
	u16     major_version;
	u16     update_version;
	u8      reserved0[4];
	u32     num_remaining_updates;
	u8      reserved1[224];
  };   //delete __packed here

 static_assert(sizeof(struct seamldr_info) == 256);

Is it better?

---

## [101] Chao Gao — 2026-01-30
*Subject: Re: [PATCH v3 07/26] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On Wed, Jan 28, 2026 at 03:04:55PM -0800, Dave Hansen wrote:
>On 1/23/26 06:55, Chao Gao wrote:
>> SEAMRET from the P-SEAMLDR clears the current VMCS structure pointed 

AFAIK, this is a CPU implementation issue. The actual requirement is to
evict (flush and invalidate) all VMCSs __cached in SEAM mode__, but big
cores implement this by evicting the __entire__ VMCS cache. So, the
current VMCS is invalidated and cleared.

>
>KVM folks, are you OK with this?

---

## [102] Chao Gao — 2026-01-30
*Subject: Re: [PATCH v3 07/26] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On Wed, Jan 28, 2026 at 03:36:49PM -0800, Dave Hansen wrote:
>On 1/23/26 06:55, Chao Gao wrote:
>...

Only SEAMLDR calls can get here. I will make it a WARN_ON_ONCE().

>
>> +	/*

This function only disables interrupts, not NMIs. Kirill questioned whether any
KVM operations might execute from NMI context and do VMREAD/VMWRITE. If such
operations exist and an NMI interrupts seamldr_call(), they could encounter
an invalid current VMCS.

The problematic scenario is:

	seamldr_call()			KVM code in NMI handler

1.	vmptrst // save current-vmcs
2.	seamcall // clobber current-vmcs
3.					// NMI handler start
					call into some KVM code and do vmread/vmwrite
					// consume __invalid__ current-vmcs
					// NMI handler end
4.	vmptrld // restore current-vmcs

The comment clarifies that KVM doesn't do VMREAD/VMWRITE during NMI handling.

>
>> +	local_irq_save(flags);

Exactly. Sean suggested this approach [*]. He prefers inline assembly rather than
adding new, inferior wrappers

*: https://lore.kernel.org/linux-coco/aHEYtGgA3aIQ7A3y@google.com/

>
>I'd be shocked if this is the one and only place in the whole kernel

The idea is feasible. But just calling vmcs_clear() won't work. We need to
reset all the tracking state associated with each VMCS. We should call
vmclear_local_loaded_vmcss() instead, similar to what's done before VMXOFF.

>
>I'm sure Sean and Paolo will tell me if I'm crazy.

To me, this approach needs more work since we need to either move 
vmclear_local_loaded_vmcss() to the kernel or allow KVM to register a callback.

I don't think it's as straightforward as just doing the save/restore.

>
>> diff --git a/drivers/virt/coco/tdx-host/Kconfig b/drivers/virt/coco/tdx-host/Kconfig

I will reduce this to:

	  This enables the kernel to update the TDX Module to another compatible
	  version.


>
>> +	  If unsure, say N.

Looks like I failed that test! ;) I'll change it to default to 'y' and
recommend 'Y' if unsure.

---

## [103] Chao Gao — 2026-01-30
*Subject: Re: [PATCH v3 08/26] x86/virt/seamldr: Retrieve P-SEAMLDR information*

On Wed, Jan 28, 2026 at 03:57:30PM -0800, Dave Hansen wrote:
>On 1/23/26 06:55, Chao Gao wrote:
>> +static struct seamldr_info seamldr_info __aligned(256);

This should be __read_mostly. num_remaining_updates changes after successful
updates.

---

## [104] Chao Gao — 2026-01-30
*Subject: Re: [PATCH v3 08/26] x86/virt/seamldr: Retrieve P-SEAMLDR information*

On Wed, Jan 28, 2026 at 03:54:38PM -0800, Dave Hansen wrote:
>On 1/23/26 06:55, Chao Gao wrote:
>> P-SEAMLDR returns its information e.g., version and supported features, in

Hi Dave,

Thank you for the thorough review.

I will go through the following patches to ensure they don't have the same
issues you have pointed out.

>> invoking SEAMLDR.INFO SEAMCALL in preparation for exposing P-SEAMLDR
>> version and other necessary information to userspace.

Will add a link in the changelog.

>
>I think it's also worth calling out that there are SEAMLDR calls for both:

Sorry about this. Will do.

>
>> diff --git a/arch/x86/include/asm/seamldr.h b/arch/x86/include/asm/seamldr.h

Will do.

>
>

Will do. Probably because I thought the kernel would never use it.

<snip>

>> +const struct seamldr_info *seamldr_get_info(void)
>> +{

ok.

---

## [105] Xu Yilun — 2026-01-30
*Subject: Re: [PATCH v3 10/26] coco/tdx-host: Implement FW_UPLOAD sysfs ABI
 for TDX Module updates*

> +static enum fw_upload_err tdx_fw_write(struct fw_upload *fwl, const u8 *data,
> +				       u32 offset, u32 size, u32 *written)

We don't allow partial write, we stop_machine while writing, so we
cannot possibly cancel the update in progress, so we only check the
cancel_request once before first write. That means cancel is useless for
our case. Is it better we delete all the cancel logic &
struct tdx_fw_upload_status?

> +	}
> +

...

> +static void tdx_fw_cancel(struct fw_upload *fwl)
> +{

Unfortunately fw_upload core doesn't allow .cancel unimplemented, leave
it as a dummy stub is OK, since this callback just request cancel,
doesn't care whether the cancel succeeds or fails in the end.

If you agree, add some comments in this function.

> +}
> +

We already does tdx_get_sysinfo() on module_init, is it better we have
a global tdx_sysinfo pointer in this driver, so that we don't have to
retrieve it again and again.

---

## [106] Chao Gao — 2026-01-30
*Subject: Re: [PATCH v3 24/26] x86/virt/seamldr: Extend sigstruct to 16KB*

>Let's move the discussion here (from patch 13 -- sorry about that):
>

Good question.

This is actually userspace's responsibility. The kernel exposes P-SEAMLDR
version to userspace, and for each module, the mapping file [*] lists the
module's minimum P-SEAMLDR version requirements. This allows userspace to
determine whether the existing P-SEAMLDR can load a specific TDX blob.

If the kernel cannot load a module using the current P-SEAMLDR, that's
userspace's fault.

*: https://github.com/intel/confidential-computing.tdx.tdx-module.binaries/blob/main/mapping_file.json

---

## [107] Chao Gao — 2026-01-30
*Subject: Re: [PATCH v3 09/26] coco/tdx-host: Expose P-SEAMLDR information via
 sysfs*

>> +What:		/sys/devices/faux/tdx_host/seamldr/num_remaining_updates
>> +Contact:	linux-coco@lists.linux.dev

It is the CPU. The CPU provides the database and gives instructions to
P-SEAMLDR for adding records or cleaning up the entire database.

<snip>

>> +#ifdef CONFIG_INTEL_TDX_MODULE_UPDATE
>> +static ssize_t seamldr_version_show(struct device *dev, struct device_attribute *attr,

You are absolutely right. 

>
>Are there any concerns about making SEAMLDR calls? Are there any

/facepalm. Sorry for missing these important considerations.

I overlooked a critical constraint: only one CPU can call P-SEAMLDR at a time;
any second CPU gets VMFailInvalid. Patch 19 adds a lock for SEAMLDR.INSTALL
serialization, but we actually need to serialize all P-SEAMLDR calls or handle
VMFailInvalid with retries.

I will make the following changes to see how they look:

1. Move the lock from patch 19 to seamldr_call() to serialize all P-SEAMLDR calls
2. Cache seamldr_info and only update it after successful updates
3. Make seamldr_get_info() return cached data instead of calling P-SEAMLDR every time

---

## [108] Chao Gao — 2026-01-30
*Subject: Re: [PATCH v3 13/26] x86/virt/seamldr: Allocate and populate a
 module update request*

On Wed, Jan 28, 2026 at 12:03:25PM +0800, Huang, Kai wrote:
>
>> +/*

Kai,

Thanks a lot.

Looks good to me. I think WARN() is always better than comments.

>> +	if (!verify_checksum(blob)) {
>> +		pr_err("invalid checksum\n");

Yes. Exactly.

>
>If so a comment would be helpful.

Will do.

>
>Also, it's also weird that you have to write code for checksum on your own.

Good point. After a quick review, lib/checksum.c uses a different algorithm
than tdx_blob's checksum. It adds the carry bit to the checksum, while tdx_blob
drops the carry bit.

*sigh* when I designed the checksum algorithm, I wasn't aware of lib/checksum.c.

---

## [109] Dave Hansen — 2026-01-30
*Subject: Re: [PATCH v3 09/26] coco/tdx-host: Expose P-SEAMLDR information via
 sysfs*

On 1/30/26 06:44, Chao Gao wrote:
>>> +What:		/sys/devices/faux/tdx_host/seamldr/num_remaining_updates
>>> +Contact:	linux-coco@lists.linux.dev

Either way, it's an implementation detail that doesn't need to be
litigated in the OS ABI docs.

	TDX maintains a log about each TDX module which has been loaded.
	This log has a finite size which limits the number of TDX module
	updates which can be performed.

	Report the number of updates remaining.

>>> +#ifdef CONFIG_INTEL_TDX_MODULE_UPDATE

...
> /facepalm. Sorry for missing these important considerations.
> 

Ack, yes, this is obviously required.

> 2. Cache seamldr_info and only update it after successful updates
> 3. Make seamldr_get_info() return cached data instead of calling P-SEAMLDR every time

To be honest, I'm not sure we need a cache. Why don't we just make the
permissions 400 and keep the info structure on the stack?

---

## [110] Dave Hansen — 2026-01-30
*Subject: Re: [PATCH v3 08/26] x86/virt/seamldr: Retrieve P-SEAMLDR information*

On 1/30/26 05:55, Chao Gao wrote:
...
>>> invoking SEAMLDR.INFO SEAMCALL in preparation for exposing P-SEAMLDR
>>> version and other necessary information to userspace.

Remember, as a general rule, links go stale. Document titles and Intel
document numbers stay valid for *much* longer.

>>> +	u32	version;
>>> +	u32	attributes;

It just makes me think that I'm looking at different documentation for
this data structure than you are. It literally costs nothing to give it
a real name. Maybe 5 bytes of code or something.

---

## [111] Dave Hansen — 2026-01-30
*Subject: Re: [PATCH v3 07/26] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On 1/30/26 05:21, Chao Gao wrote:
...
>>> +	/*
>>> +	 * SEAMRET from P-SEAMLDR invalidates the current VMCS.  Save/restore

How about something like:

	P-SEAMLDR calls invalidate the current VMCS. It must be saved
	and restored around the call. Exclude KVM access to the VMCS
	by disabling interrupts. This is not safe against VMCS use in
	NMIs, but there are none of those today.

Ideally, you'd also pair that with _some_ checks in the KVM code that
use lockdep or warnings to reiterate that NMI access to the VMCS is not OK.

>>> +	local_irq_save(flags);
>>> +

Get his explicit reviews on the patch, please.

Also, I 100% object to inline assembly in the main flow. Please at least
make a wrapper for these and stick them in:

	arch/x86/include/asm/special_insns.h

so the inline assembly spew is hidden from view.

>> I'd be shocked if this is the one and only place in the whole kernel
>> that can unceremoniously zap VMX state.

Could you please just do me a favor and spend 20 minutes to see what
this looks like in practice and if the KVM folks hate it?

>>> diff --git a/drivers/virt/coco/tdx-host/Kconfig b/drivers/virt/coco/tdx-host/Kconfig
>>> index e58bad148a35..6a9199e6c2c6 100644

I guess I'll be explicit: Remove this Kconfig prompt.

I think you should remove INTEL_TDX_MODULE_UPDATE entirely. But I'll
settle for:

	config INTEL_TDX_MODULE_UPDATE
		bool
		default TDX_HOST_SERVICES

so that users don't have to see it. Don't bother users with it. Period.

---

## [112] Dave Hansen — 2026-01-30
*Subject: Re: [PATCH v3 07/26] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On 1/30/26 00:08, Chao Gao wrote:
> On Wed, Jan 28, 2026 at 03:04:55PM -0800, Dave Hansen wrote:
>> On 1/23/26 06:55, Chao Gao wrote:

But why is this a P-SEAMLDR thing and not a TDX module thing?

It seems like a bug, or at least a P-SEAMLDR implementation issue the
needs to get fixed.

---

## [113] Dave Hansen — 2026-01-30
*Subject: Re: [PATCH v3 08/26] x86/virt/seamldr: Retrieve P-SEAMLDR information*

On 1/29/26 20:01, Xu Yilun wrote:
>> I'd also prefer a
>>
Whatever the documentation says. I might have been looking at the
seamldr_seaminfo.

>> just as a sanity check. It doesn't cost anything and it makes sure that
>> as you muck around with reserved fields and padding that there's at

I'm pretty sure __packed is used all over the place.

I'd be shocked if access to a __packed structure generated different
code than a non-packed one for the same layout. But it wouldn't be the
first time I was shocked by a compiler.

I think you might be confusing the fact that access to unaligned data
can really stink on some architectures. The code generation for *that*
can be garbage. But not on x86 really and not for data that's already
naturally aligned.

Plus, *this* data structure is far, far from being performance sensitive
anyway. So it doubly or triply doesn't matter here.

If nothing else, __packed is a good indicator that WYSIWYG for structure
layout because it's an ABI. I honestly don't see a lot of downsides.

---

## [114] Xu Yilun — 2026-02-02
*Subject: Re: [PATCH v3 08/26] x86/virt/seamldr: Retrieve P-SEAMLDR information*

> If nothing else, __packed is a good indicator that WYSIWYG for structure
> layout because it's an ABI. I honestly don't see a lot of downsides.

OK. So on x86 I can use it without worry. Thanks.

---

## [115] Xu Yilun — 2026-02-02
*Subject: Re: [PATCH v3 11/26] x86/virt/seamldr: Block TDX Module updates if
 any CPU is offline*

On Fri, Jan 23, 2026 at 06:55:19AM -0800, Chao Gao wrote:
> P-SEAMLDR requires every CPU to call the SEAMLDR.INSTALL SEAMCALL during
> updates.  So, every CPU should be online.

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

---

## [116] Xu Yilun — 2026-02-02
*Subject: Re: [PATCH v3 13/26] x86/virt/seamldr: Allocate and populate a
 module update request*

> +static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
> +{

You need to firstly check if size is big enough for the header before
offset into it.

	if (size < sizeof(struct tdx_blob))
		return XXX;

---

## [117] Xu Yilun — 2026-02-02
*Subject: Re: [PATCH v3 14/26] x86/virt/seamldr: Introduce skeleton for TDX
 Module updates*

On Fri, Jan 23, 2026 at 06:55:22AM -0800, Chao Gao wrote:
> The P-SEAMLDR requires that no TDX Module SEAMCALLs are invoked during a
> runtime TDX Module update.

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

---

## [118] Xu Yilun — 2026-02-02
*Subject: Re: [PATCH v3 15/26] x86/virt/seamldr: Abort updates if errors
 occurred midway*

On Fri, Jan 23, 2026 at 06:55:23AM -0800, Chao Gao wrote:
> The TDX Module update process has multiple stages, each of which may
> encounter failures.

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

---

## [119] Xu Yilun — 2026-02-02
*Subject: Re: [PATCH v3 16/26] x86/virt/seamldr: Shut down the current TDX
 module*

> +static int get_tdx_sys_info_handoff(struct tdx_sys_info_handoff *sysinfo_handoff)
> +{

Do all fields in sysinfo_handoff optional or just module_hv, if the
former, is it better:

	if (tdx_supports_runtime_update(&tdx_sysinfo)
		ret = ret ?: get_tdx_sys_info_handoff(&sysinfo->handoff);

>  
>  	return ret;

---

## [120] Xu Yilun — 2026-02-02
*Subject: Re: [PATCH v3 18/26] x86/virt/seamldr: Log TDX Module update failures*

> +static void print_update_failure_message(void)
> +{

Not sure why it can't be just pr_err_once()?

> +
>  /*

---

## [121] Xu Yilun — 2026-02-02
*Subject: Re: [PATCH v3 20/26] x86/virt/seamldr: Do TDX per-CPU initialization
 after updates*

On Fri, Jan 23, 2026 at 06:55:28AM -0800, Chao Gao wrote:
> After installing the new TDX module, each CPU should be initialized
> again to make the CPU ready to run any other SEAMCALLs. So, call

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

---

## [122] Xu Yilun — 2026-02-02
*Subject: Re: [PATCH v3 22/26] x86/virt/tdx: Update tdx_sysinfo and check
 features post-update*

On Fri, Jan 23, 2026 at 06:55:30AM -0800, Chao Gao wrote:
> tdx_sysinfo contains all metadata of the active TDX module, including
> versions, supported features, and TDMR/TDCS/TDVPS information. These

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

---

## [123] Xu Yilun — 2026-02-02
*Subject: Re: [PATCH v3 23/26] x86/virt/tdx: Enable TDX Module runtime updates*

>  static inline bool tdx_supports_runtime_update(const struct tdx_sys_info *sysinfo)
>  {

Frankly speak, I don't know why we need endless one-line wrappers like
this, we've already exposed all details of the tdx_sys_info to its
users.

But I'm still OK with them.

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

---

## [124] Huang, Kai — 2026-02-02
*Subject: Re: [PATCH v3 24/26] x86/virt/seamldr: Extend sigstruct to 16KB*

On Fri, 2026-01-30 at 22:25 +0800, Gao, Chao wrote:
> > Let's move the discussion here (from patch 13 -- sorry about that):
> > 

Thanks for the info.

In this case, I am not sure why do you need to implement code (patch 13) to
firstly support 4K less SIGSTRUCT (with a confusing doc of 'tdx_blob' layout
definition), but here extend it to 16K in a second patch?

How about just merge this one to patch 13 and point out this fact in
changelog if needed?

E.g.,:

  For a given TDX blob, not all SEAMLDR and TDX module versions support 
  runtime update for it.  Intel publishes the requirement of the minimal
  SEAMLDR and TDX module versions for it.

  There's no hardware/firmware interface that the kernel could use to
  detect and bail out early if such requirement is not met.  It's
  userspace's responsibility to make sure such requirement is met before
	 	
  performing runtime update.

Actually, assuming the new spec which reflects 16KB SIGSTRUCT in
SEAMLDR_PARAMS will be published, I _think_ the fact that "some old SEMALDR
versions only support upto 4K SIGSTRUCT" probably doesn't matter anymore,
especially if we add the above to the changelog.

So I don't quite see why we need to keep this "extend SIGSTRUCT to 16KB" as
a separate patch?

Btw, we also need the updated doc of TDX blob layout too, to reflect what
your code is doing (regarding to how to calculate SIGSTRUCT base/size).

And we need to make sure the TDX blob layout is architectural.

---

## [125] Chao Gao — 2026-02-03
*Subject: Re: [PATCH v3 07/26] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

>>> I'd be shocked if this is the one and only place in the whole kernel
>>> that can unceremoniously zap VMX state.

Sure. KVM tracks the current VMCS and only executes vmptrld for a new VMCS if
it differs from the current one. See arch/x86/kvm/vmx/vmx.c::vmx_vcpu_load_vmcs()

	prev = per_cpu(current_vmcs, cpu);
	if (prev != vmx->loaded_vmcs->vmcs) {
		per_cpu(current_vmcs, cpu) = vmx->loaded_vmcs->vmcs;
		vmcs_load(vmx->loaded_vmcs->vmcs);
	}

By resetting current_vmcs to NULL during P-SEAMLDR calls, KVM is forced to do a
vmptrld on the next VMCS load. So, we can implement seamldr_call() as:

static int seamldr_call(u64 fn, struct tdx_module_args *args)
{
	int ret;

	WARN_ON_ONCE(!is_seamldr_call(fn));

	/*
	 * Serialize P-SEAMLDR calls since only a single CPU is allowed to
	 * interact with P-SEAMLDR at a time.
	 *
	 * P-SEAMLDR calls invalidate the current VMCS. Exclude KVM access to
	 * the VMCS by disabling interrupts. This is not safe against VMCS use
	 * in NMIs, but there are none of those today.
	 *
	 * Set the per-CPU current_vmcs cache to NULL to force KVM to reload
	 * the VMCS.
	 */
	guard(raw_spinlock_irqsave)(&seamldr_lock);
	ret = seamcall_prerr(fn, args);
	this_cpu_write(current_vmcs, NULL);

	return ret;
}

This requires moving the per-CPU current_vmcs from KVM to the kernel, which
should be trivial with Sean's VMXON series.

And I tested this. Without this_cpu_write(), vmread/vmwrite errors occur after
TDX Module updates. But with it, no errors.

---

## [126] Sean Christopherson — 2026-02-03
*Subject: Re: [PATCH v3 07/26] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On Tue, Feb 03, 2026, Chao Gao wrote:
> >>> I'd be shocked if this is the one and only place in the whole kernel
> >>> that can unceremoniously zap VMX state.

I hate it :-)

> Sure. KVM tracks the current VMCS and only executes vmptrld for a new VMCS if
> it differs from the current one. See arch/x86/kvm/vmx/vmx.c::vmx_vcpu_load_vmcs()

Trivial in code, but I am very strongly opposed to moving current_vmcs out of KVM.
As stated in the cover letter of the initial VMXON RFC[*]:

 : Emphasis on "only", because leaving VMCS tracking and clearing in KVM is
 : another key difference from Xin's series.  The "light bulb" moment on that
 : front is that TDX isn't a hypervisor, and isn't trying to be a hypervisor.
 : Specifically, TDX should _never_ have it's own VMCSes (that are visible to the
 : host; the TDX-Module has it's own VMCSes to do SEAMCALL/SEAMRET), and so there
 : is simply no reason to move that functionality out of KVM.

TDX's "use" of a VMCS should be completely transparent to KVM, because otherwise
we are stepping over that line that says the TDX subsystem isn't a hypervisor.
I also really, really don't want to add a super special case rule to KVM's VMCS
tracking logic.

After reading through the rest of this discussion, I'm doubling down on that
stance, because I agree that this is decidely odd behavior.

Pulling in two other threads from this discussion:

On Wed, Jan 28, 2026 at 3:05 PM Dave Hansen <dave.hansen@intel.com> wrote:
>
> On 1/23/26 06:55, Chao Gao wrote:

As above, I'm definitely not ok with the current VMCS being zapped out from
underneath KVM.  As to whether or not I'm ok with the P-SEAMLDR behavior, I would
say that's more of a question for you, as it will fall on the TDX subsytem to
workaround the bug/quirk.

On Fri, Jan 30, 2026 at 8:23 AM Dave Hansen <dave.hansen@intel.com> wrote:
> On 1/30/26 00:08, Chao Gao wrote:
> > AFAIK, this is a CPU implementation issue. The actual requirement is to

My guess is that it's because the P-SEAMLDR code loads and prepares the new TDX-
Module by constructing the VMCS used for SEAMCALL using direct writes to memory
(unless that TDX behavior has changed in the last few years).  And so it needs
to ensure that in-memory representation is synchronized with the VMCS cache.

Hmm, but that doesn't make sense _if_ it really truly is SEAMRET that does the VMCS
cache invalidation, because flushing the VMCS cache would ovewrite the in-memory
state.

> It seems like a bug, or at least a P-SEAMLDR implementation issue the
> needs to get fixed.

Yeah, 'tis odd behavior.  IMO, that's all the more reason the TDX subsystem should
hide the quirk from the rest of the kernel.

[*] https://lore.kernel.org/all/20251010220403.987927-1-seanjc@google.com

---

## [127] Dave Hansen — 2026-02-03
*Subject: Re: [PATCH v3 07/26] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On 2/3/26 07:41, Sean Christopherson wrote:
>> It seems like a bug, or at least a P-SEAMLDR implementation issue the
>> needs to get fixed.

For now, I say treat it as a bug. Don't deal with it in the series.

If it truly is unfixable P-SEAMLDR behavior, then Intel can issue and
erratum for it and we can add (ugly) code to follow Sean's suggestion.

---

## [128] Chao Gao — 2026-02-04
*Subject: Re: [PATCH v3 07/26] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

>On Fri, Jan 30, 2026 at 8:23 AM Dave Hansen <dave.hansen@intel.com> wrote:
>> On 1/30/26 00:08, Chao Gao wrote:

My understanding is:

1. SEAMCALL/SEAMRET use VMCSs.

2. P-SEAMLDR is single-threaded (likely for simplicity). So, it uses a _single_
   global VMCS and only one CPU can call P-SEAMLDR calls at a time.

3. After SEAMRET from P-SEAMLDR, _if_ the global VMCS isn't flushed, other CPUs
   cannot enter P-SEAMLDR because the global VMCS would be corrupted. (note the
   global VMCS is cached by the original CPU).

4. To make P-SEAMLDR callable on all CPUs, SEAMRET instruction flush VMCSs.
   The flush cannot be performed by the host VMM since the global VMCS is not
   visible to it. P-SEAMLDR cannot do it either because SEAMRET is its final
   instruction and requires a valid VMCS.

The TDX Module has per-CPU VMCSs, so it doesn't has this problem.

I'll check if SEAM ISA architects can join to explain this in more detail.

>
>> It seems like a bug, or at least a P-SEAMLDR implementation issue the

---

## [129] Tony Lindgren — 2026-02-04
*Subject: Re: [PATCH v3 23/26] x86/virt/tdx: Enable TDX Module runtime updates*

On Mon, Jan 26, 2026 at 01:14:07PM +0200, Tony Lindgren wrote:
> On Fri, Jan 23, 2026 at 06:55:31AM -0800, Chao Gao wrote:
> > --- a/arch/x86/include/asm/tdx.h

Sorry I was confused. No need to move these defines to
arch/x86/include/asm/shared/tdx.h as far as I can tell.

The BIT_ULL comment still remains though.

Regards,

Tony

---

## [130] Sean Christopherson — 2026-02-05
*Subject: Re: [PATCH v3 07/26] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On Wed, Feb 04, 2026, Chao Gao wrote:
> >On Fri, Jan 30, 2026 at 8:23 AM Dave Hansen <dave.hansen@intel.com> wrote:
> >> On 1/30/26 00:08, Chao Gao wrote:

No, this isn't the explanation.  I found the explanation in the pseudocode for
SEAMRET.  The "successful VM-Entry" path says this:

  current-VMCS = current-VMCS.VMCS-link-pointer
  IF inP_SEAMLDR == 1; THEN
    If current-VMCS != FFFFFFFF_FFFFFFFFH; THEN
      Ensure data for VMCS referenced by current-VMC is in memory
      Initialize implementation-specific data in all VMCS referenced by current-VMCS
      Set launch state of VMCS referenced by current-VMCS to “clear”
      current-VMCS = FFFFFFFF_FFFFFFFFH
    FI;
    inP_SEAMLDR = 0
  FI;

I.e. my guess about firmware (probably XuCode?) doing direct writes was correct,
I just guessed wrong on which VMCS.  Or rather, I didn't guess "all".

> The TDX Module has per-CPU VMCSs, so it doesn't has this problem.
>

---

## [131] Dave Hansen — 2026-02-05
*Subject: Re: [PATCH v3 07/26] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On 2/5/26 08:29, Sean Christopherson wrote:
> No, this isn't the explanation.  I found the explanation in the pseudocode for
> SEAMRET.  The "successful VM-Entry" path says this:

Yes, in version 002 of the spec. It wasn't there in 001.

The basic problem is that the SEAM VMCSes need to get flushed when the
TDX module is being loaded. The TDX module never loads itself, thus the
"inP_SEAMLDR == 1" check. It sounds like there was already an existing
thing in microcode to just flush VMCSes and invalidate "current-VMCS".

It was much easier for microcode to just jump over to that existing
thing than to surgically target the SEAM VMCSes, or somehow avoid
zapping "current-VMCS". It makes total sense for the microcoders to have
gone this route.

I'm seeing if it can get changed back to the 001 version so we just
don't even have to deal with this whole mess.

---

## [132] Xing, Cedric — 2026-02-06
*Subject: Re: [PATCH v3 10/26] coco/tdx-host: Implement FW_UPLOAD sysfs ABI for
 TDX Module updates*

On 1/23/2026 8:55 AM, Chao Gao wrote:
[...]
> +
> +static void seamldr_init(struct device *dev)
I can't speak for others but the name "seamldr_upload" here doesn't look intuitive to me. Given this 
FW node will show up in /sys/class/firmware/, I'd name it "tdx_module" to indicate to the user 
clearly that this is for updating the TDX module.

-Cedric

---
