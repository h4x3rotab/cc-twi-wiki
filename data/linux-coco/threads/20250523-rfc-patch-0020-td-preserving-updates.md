---
title: '[RFC PATCH 00/20] TD-Preserving updates'
date: 2025-05-23
last_reply: 2025-08-06
message_count: 64
participants: ['Chao Gao', 'Huang, Kai', 'Nikolay Borisov', 'Dave Hansen', 'Sagi Shahar', 'Sean Christopherson', 'Paul E. McKenney', 'Xu Yilun', 'dan.j.williams@intel.com']
---

## [1] Chao Gao — 2025-05-23

Hi Reviewers,

This series adds support for runtime TDX module updates that preserve
running TDX guests (a.k.a, TD-Preserving updates). The goal is to gather
feedback on the feature design. Please pay attention to the following items:

1. TD-Preserving updates are done in stop_machine() context. it copy-pastes
   part of multi_cpu_stop() to guarantee step-locked progress on all CPUs.
   But, there are a few differences between them. I am wondering whether
   these differences have reached a point where abstracting a common
   function might do more harm than good. See more details in patch 10.

2. P-SEAMLDR seamcalls (specificially SEAMRET from P-SEAMLDR) clear current
   VMCS pointers, which may disrupt KVM. To prevent VMX instructions in IRQ
   context from encountering NULL current-VMCS pointers, P-SEAMLDR
   seamcalls are called with IRQ disabled. I'm uncertain if NMIs could
   cause a problem, but I believe they won't. See more information in patch 3.

3. Two helpers, cpu_vmcs_load() and cpu_vmcs_store(), are added in patch 3
   to save and restore the current VMCS. KVM has a variant of cpu_vmcs_load(),
   i.e., vmcs_load(). Extracting KVM's version would cause a lot of code
   churn, and I don't think that can be justified for reducing ~16 LoC
   duplication. Please let me know if you disagree.

== Background ==

Intel TDX isolates Trusted Domains (TDs), or confidential guests, from the
host. A key component of Intel TDX is the TDX module, which enforces
security policies to protect the memory and CPU states of TDs from the
host. However, the TDX module is software that require updates, it is not
device firmware in the typical sense.

== Problems ==

Currently, the TDX module is loaded by the BIOS at boot time, and the only
way to update it is through a reboot, which results in significant system
downtime. Users expect the TDX module to be updatable at runtime without
disrupting TDX guests.

== Solution ==

On TDX platforms, P-SEAMLDR[1] is a component within the protected SEAM
range. It is loaded by the BIOS and provides the host with functions to
install a TDX module at runtime.

Implement a TDX Module update facility via the fw_upload mechanism. Given
that there is variability in which module update to load based on features,
fix levels, and potentially reloading the same version for error recovery
scenarios, the explicit userspace chosen payload flexibility of fw_upload
is attractive.

This design allows the kernel to accept a bitstream instead of loading a
named file from the filesystem, as the module selection and policy
enforcement for TDX modules are quite complex (see more in patch 8). By
doing so, much of this complexity is shifted out of the kernel. The kernel
need to expose information, such as the TDX module version, to userspace.
The userspace tool must understand the TDX module versioning scheme and
update policy to select the appropriate TDX module (see "TDX Module
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

 # git clone https://github.com/intel/tdx-module-binaries
 # cd tdx-module-binaries
 # python version_select_and_load.py --update


This series is based on Sean's kvm-x86/next branch

  https://github.com/kvm-x86/linux.git next


== Other information relevant to TD-Preserving updates == 

=== TDX module versioning ===

Each TDX module is assigned a version number x.y.z, where x represents the
"major" version, y the "minor" version, and z the "update" version.

TD-Preserving updates are restricted to Z-stream releases.

Note that Z-stream releases do not necessarily guarantee compatibility. A
new release may not be compatible with all previous versions. To address this,
Intel provides a separate file containing compatibility information, which
specifies the minimum module version required for a particular update. This
information is referenced by the tool to determine if two modules are
compatible.

=== TCB Stability ===

Updates change the TCB as viewed by attestation reports. In TDX there is a
distinction between launch-time version and current version where TD-preserving
updates cause that latter version number to change, subject to Z-stream
constraints. The need for runtime updates and the implications of that version
change in the attestation was previously discussed in [3].

=== TDX Module Distribution Model ===

At a high level, Intel publishes all TDX modules on the github [2], along with
a mapping_file.json which documents the compatibility information about each
TDX module and a script to install the TDX module. OS vendors can package
these modules and distribute them. Administrators install the package and
use the script to select the appropriate TDX module and install it via the
interfaces exposed by this series.

[1]: https://cdrdv2.intel.com/v1/dl/getContent/733584
[2]: https://github.com/intel/tdx-module-binaries
[3]: https://lore.kernel.org/all/5d1da767-491b-4077-b472-2cc3d73246d6@amazon.com/


Chao Gao (20):
  x86/virt/tdx: Print SEAMCALL leaf numbers in decimal
  x86/virt/tdx: Prepare to support P-SEAMLDR SEAMCALLs
  x86/virt/seamldr: Introduce a wrapper for P-SEAMLDR SEAMCALLs
  x86/virt/tdx: Introduce a "tdx" subsystem and "tsm" device
  x86/virt/tdx: Export tdx module attributes via sysfs
  x86/virt/seamldr: Add a helper to read P-SEAMLDR information
  x86/virt/tdx: Expose SEAMLDR information via sysfs
  x86/virt/seamldr: Implement FW_UPLOAD sysfs ABI for TD-Preserving
    Updates
  x86/virt/seamldr: Allocate and populate a module update request
  x86/virt/seamldr: Introduce skeleton for TD-Preserving updates
  x86/virt/seamldr: Abort updates if errors occurred midway
  x86/virt/seamldr: Shut down the current TDX module
  x86/virt/tdx: Reset software states after TDX module shutdown
  x86/virt/seamldr: Install a new TDX module
  x86/virt/seamldr: Handle TD-Preserving update failures
  x86/virt/seamldr: Do TDX cpu init after updates
  x86/virt/tdx: Establish contexts for the new module
  x86/virt/tdx: Update tdx_sysinfo and check features post-update
  x86/virt/seamldr: Verify availability of slots for TD-Preserving
    updates
  x86/virt/seamldr: Enable TD-Preserving Updates

 Documentation/ABI/testing/sysfs-devices-tdx |  32 ++
 MAINTAINERS                                 |   1 +
 arch/x86/Kconfig                            |  12 +
 arch/x86/include/asm/tdx.h                  |  20 +-
 arch/x86/include/asm/tdx_global_metadata.h  |  12 +
 arch/x86/virt/vmx/tdx/Makefile              |   1 +
 arch/x86/virt/vmx/tdx/seamldr.c             | 443 ++++++++++++++++++++
 arch/x86/virt/vmx/tdx/seamldr.h             |  16 +
 arch/x86/virt/vmx/tdx/tdx.c                 | 248 ++++++++++-
 arch/x86/virt/vmx/tdx/tdx.h                 |  12 +
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |  29 ++
 arch/x86/virt/vmx/vmx.h                     |  40 ++
 12 files changed, 862 insertions(+), 4 deletions(-)
 create mode 100644 Documentation/ABI/testing/sysfs-devices-tdx
 create mode 100644 arch/x86/virt/vmx/tdx/seamldr.c
 create mode 100644 arch/x86/virt/vmx/tdx/seamldr.h
 create mode 100644 arch/x86/virt/vmx/vmx.h

---

## [2] Chao Gao — 2025-05-23
*Subject: [RFC PATCH 01/20] x86/virt/tdx: Print SEAMCALL leaf numbers in decimal*

Both TDX spec and kernel defines SEAMCALL leaf numbers as decimal. Printing
them in hex makes no sense. Correct it.

Suggested-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index f5e2a937c1e7..49267c865f18 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -62,7 +62,7 @@ typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);
 
 static inline void seamcall_err(u64 fn, u64 err, struct tdx_module_args *args)
 {
-	pr_err("SEAMCALL (0x%016llx) failed: 0x%016llx\n", fn, err);
+	pr_err("SEAMCALL (%lld) failed: 0x%016llx\n", fn, err);
 }
 
 static inline void seamcall_err_ret(u64 fn, u64 err,

---

## [3] Chao Gao — 2025-05-23
*Subject: [RFC PATCH 02/20] x86/virt/tdx: Prepare to support P-SEAMLDR SEAMCALLs*

P-SEAMLDR is another component alongside the TDX module within the
protected SEAM range. Software can invoke its functions by executing the
SEAMCALL instruction with the 63 bit of RAX set to 1. P-SEAMLDR SEAMCALLs
differ from those of the TDX module in terms of error codes and the
handling of the current VMCS.

In preparation for calling P-SEAMLDR functions to update the TDX module,
adjust the SEAMCALL infrastructure to support P-SEAMLDR SEAMCALLs and
expose a helper function.

Specifically,
1) P-SEAMLDR SEAMCALLs use a different error code for lack of entropy.
   Tweak sc_retry() to handle this difference.

2) Add a separate function to log the SEAMCALL leaf number and the error
   code.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
checking bit63 in sc_need_retry() may be suboptimal. An alternative is to
pass the "NO ENTROPY" error code from seamcall_prerr* and seamldr_prerr()
to sc_retry(). but this would need more code changes. I am not sure if it
is worthwhile.
---
 arch/x86/include/asm/tdx.h  | 20 +++++++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx.c | 16 ++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h |  4 ++++
 3 files changed, 39 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 26ffc792e673..b507d5233b03 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -32,6 +32,11 @@
 #define TDX_SUCCESS		0ULL
 #define TDX_RND_NO_ENTROPY	0x8000020300000000ULL
 
+/* SEAMLDR SEAMCALL leaf function error codes */
+#define SEAMLDR_RND_NO_ENTROPY	0x8000000000030001ULL
+
+#define SEAMLDR_SEAMCALL_MASK	_BITUL(63)
+
 #ifndef __ASSEMBLER__
 
 #include <uapi/asm/mce.h>
@@ -104,6 +109,19 @@ void tdx_init(void);
 
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
 static inline u64 sc_retry(sc_func_t func, u64 fn,
 			   struct tdx_module_args *args)
 {
@@ -112,7 +130,7 @@ static inline u64 sc_retry(sc_func_t func, u64 fn,
 
 	do {
 		ret = func(fn, args);
-	} while (ret == TDX_RND_NO_ENTROPY && --retry);
+	} while (sc_need_retry(fn, ret) && --retry);
 
 	return ret;
 }
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 49267c865f18..b586329dd87d 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -65,6 +65,17 @@ static inline void seamcall_err(u64 fn, u64 err, struct tdx_module_args *args)
 	pr_err("SEAMCALL (%lld) failed: 0x%016llx\n", fn, err);
 }
 
+static inline void seamldr_err(u64 fn, u64 err, struct tdx_module_args *args)
+{
+	/*
+	 * Get the actual leaf number. No need to print the bit used to
+	 * differentiate between SEAMLDR and TDX module as the "SEAMLDR"
+	 * string in the error message already provides that information.
+	 */
+	fn &= ~SEAMLDR_SEAMCALL_MASK;
+	pr_err("SEAMLDR (%lld) failed: 0x%016llx\n", fn, err);
+}
+
 static inline void seamcall_err_ret(u64 fn, u64 err,
 				    struct tdx_module_args *args)
 {
@@ -102,6 +113,11 @@ static inline int sc_retry_prerr(sc_func_t func, sc_err_func_t err_func,
 #define seamcall_prerr_ret(__fn, __args)					\
 	sc_retry_prerr(__seamcall_ret, seamcall_err_ret, (__fn), (__args))
 
+int seamldr_prerr(u64 fn, struct tdx_module_args *args)
+{
+	return sc_retry_prerr(__seamcall, seamldr_err, fn, args);
+}
+
 /*
  * Do the module global initialization once and return its result.
  * It can be done on any cpu.  It's always called with interrupts
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 82bb82be8567..48c0a850c621 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -4,6 +4,8 @@
 
 #include <linux/bits.h>
 
+#include <asm/tdx.h>
+
 /*
  * This file contains both macros and data structures defined by the TDX
  * architecture and Linux defined software data structures and functions.
@@ -118,4 +120,6 @@ struct tdmr_info_list {
 	int max_tdmrs;	/* How many 'tdmr_info's are allocated */
 };
 
+int seamldr_prerr(u64 fn, struct tdx_module_args *args);
+
 #endif

---

## [4] Chao Gao — 2025-05-23
*Subject: [RFC PATCH 03/20] x86/virt/seamldr: Introduce a wrapper for P-SEAMLDR SEAMCALLs*

P-SEAMLDR is another component alongside the TDX module within the
protected SEAM range. Software can invoke its functions by executing the
SEAMCALL instruction with the 63 bit of RAX set to 1. P-SEAMLDR SEAMCALLs
differ from those of the TDX module in terms of error codes and the
handling of the current VMCS.

Add a wrapper for P-SEAMLDR SEAMCALLs based on the SEAMCALL infrastructure.

Intel® Trust Domain CPU Architectural Extensions (May 2021 edition)
Chapter 2.3 states:

SEAMRET from the P-SEAMLDR clears the current VMCS structure pointed to by
the current-VMCS pointer. A VMM that invokes the P-SEAMLDR using SEAMCALL
must reload the current-VMCS, if required, using the VMPTRLD instruction.

So, save and restore the current-VMCS pointer using VMPTRST and VMPTRLD
instructions to avoid breaking KVM, which manages the current-VMCS.

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
---
 arch/x86/Kconfig                | 10 ++++++++
 arch/x86/virt/vmx/tdx/Makefile  |  1 +
 arch/x86/virt/vmx/tdx/seamldr.c | 44 +++++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/vmx.h         | 40 ++++++++++++++++++++++++++++++
 4 files changed, 95 insertions(+)
 create mode 100644 arch/x86/virt/vmx/tdx/seamldr.c
 create mode 100644 arch/x86/virt/vmx/vmx.h

diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
index 4b9f378e05f6..8b1e0986b7f8 100644
--- a/arch/x86/Kconfig
+++ b/arch/x86/Kconfig
@@ -1932,6 +1932,16 @@ config INTEL_TDX_HOST
 
 	  If unsure, say N.
 
+config INTEL_TDX_MODULE_UPDATE
+	bool "Intel TDX module runtime update"
+	depends on INTEL_TDX_HOST
+	help
+	  This enables the kernel to support TDX module runtime update. This allows
+	  the admin to upgrade the TDX module to a newer one without the need to
+	  terminate running TDX guests.
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
index 000000000000..a252f1ae3483
--- /dev/null
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -0,0 +1,44 @@
+// SPDX-License-Identifier: GPL-2.0
+/*
+ * Copyright(c) 2025 Intel Corporation.
+ *
+ * Intel TDX module runtime update
+ */
+#define pr_fmt(fmt)	"seamldr: " fmt
+
+#include <linux/cleanup.h>
+
+#include "tdx.h"
+#include "../vmx.h"
+
+static __maybe_unused int seamldr_call(u64 fn, struct tdx_module_args *args)
+{
+	u64 vmcs;
+	int ret;
+
+	if (!is_seamldr_call(fn))
+		return -EINVAL;
+
+	/*
+	 * SEAMRET from P-SEAMLDR invalidates the current-VMCS pointer.
+	 * Save/restore current-VMCS pointer across P-SEAMLDR SEAMCALLs so
+	 * that VMX instructions won't fail due to an invalid current-VMCS.
+	 *
+	 * Disable interrupt to prevent SMP call functions from seeing the
+	 * invalid current-VMCS.
+	 */
+	guard(irqsave)();
+
+	ret = cpu_vmcs_store(&vmcs);
+	if (ret)
+		return ret;
+
+	ret = seamldr_prerr(fn, args);
+
+	/* Restore current-VMCS pointer */
+#define INVALID_VMCS   -1ULL
+	if (vmcs != INVALID_VMCS)
+	       WARN_ON_ONCE(cpu_vmcs_load(vmcs));
+
+	return ret;
+}
diff --git a/arch/x86/virt/vmx/vmx.h b/arch/x86/virt/vmx/vmx.h
new file mode 100644
index 000000000000..51e6460fd1fd
--- /dev/null
+++ b/arch/x86/virt/vmx/vmx.h
@@ -0,0 +1,40 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+#ifndef ARCH_X86_VIRT_VMX_H
+#define ARCH_X86_VIRT_VMX_H
+
+#include <linux/printk.h>
+
+static inline int cpu_vmcs_load(u64 vmcs_pa)
+{
+	asm goto("1: vmptrld %0\n\t"
+			  ".byte 0x2e\n\t" /* branch not taken hint */
+			  "jna %l[error]\n\t"
+			  _ASM_EXTABLE(1b, %l[fault])
+			  : : "m" (vmcs_pa) : "cc" : error, fault);
+	return 0;
+
+error:
+	pr_err_once("vmptrld failed: %llx\n", vmcs_pa);
+	return -EIO;
+fault:
+	pr_err_once("vmptrld faulted\n");
+	return -EIO;
+}
+
+static inline int cpu_vmcs_store(u64 *vmcs_pa)
+{
+	int ret = -EIO;
+
+	asm volatile("1: vmptrst %0\n\t"
+		     "mov $0, %1\n\t"
+		     "2:\n\t"
+		     _ASM_EXTABLE(1b, 2b)
+		     : "=m" (*vmcs_pa), "+r" (ret) : :);
+
+	if (ret)
+		pr_err_once("vmptrst faulted\n");
+
+	return ret;
+}
+
+#endif

---

## [5] Chao Gao — 2025-05-23
*Subject: [RFC PATCH 04/20] x86/virt/tdx: Introduce a "tdx" subsystem and "tsm" device*

TDX depends on a platform firmware module that is invoked via
instructions similar to vmenter (i.e. enter into a new privileged
"root-mode" context to manage private memory and private device
mechanisms). It is a software construct that depends on the CPU vmxon
state to enable invocation of TDX-module ABIs. Unlike other
Trusted Execution Environment (TEE) platform implementations that employ
a firmware module running on a PCI device with an MMIO mailbox for
communication, TDX has no hardware device to point to as the "TSM".

The "/sys/devices/virtual" hierarchy is intended for "software
constructs which need sysfs interface", which aligns with what TDX
needs.

The new tdx_subsys will export global attributes populated by the
TDX-module "sysinfo". A tdx_tsm device is published on this bus to
enable a typical driver model for the low level "TEE Security Manager"
(TSM) flows that talk TDISP to capable PCIe devices.

For now, this is only the base tdx_subsys and tdx_tsm device
registration with attribute definition and TSM driver to follow later.

Co-developed-by: Dan Williams <dan.j.williams@intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 75 +++++++++++++++++++++++++++++++++++++
 1 file changed, 75 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index b586329dd87d..9719df2f2634 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -28,6 +28,8 @@
 #include <linux/log2.h>
 #include <linux/acpi.h>
 #include <linux/suspend.h>
+#include <linux/device.h>
+#include <linux/cleanup.h>
 #include <linux/idr.h>
 #include <asm/page.h>
 #include <asm/special_insns.h>
@@ -1080,6 +1082,77 @@ static int init_tdmrs(struct tdmr_info_list *tdmr_list)
 	return 0;
 }
 
+static const struct bus_type tdx_subsys = {
+	.name = "tdx",
+};
+
+struct tdx_tsm {
+	struct device dev;
+};
+
+static struct tdx_tsm *alloc_tdx_tsm(void)
+{
+	struct tdx_tsm *tsm = kzalloc(sizeof(*tsm), GFP_KERNEL);
+	struct device *dev;
+
+	if (!tsm)
+		return ERR_PTR(-ENOMEM);
+
+	dev = &tsm->dev;
+	dev->bus = &tdx_subsys;
+	device_initialize(dev);
+
+	return tsm;
+}
+
+DEFINE_FREE(tdx_tsm_put, struct tdx_tsm *,
+	    if (!IS_ERR_OR_NULL(_T)) put_device(&_T->dev))
+static struct tdx_tsm *init_tdx_tsm(void)
+{
+	struct device *dev;
+	int ret;
+
+	struct tdx_tsm *tsm __free(tdx_tsm_put) = alloc_tdx_tsm();
+	if (IS_ERR(tsm))
+		return tsm;
+
+	dev = &tsm->dev;
+	ret = dev_set_name(dev, "tdx_tsm");
+	if (ret)
+		return ERR_PTR(ret);
+
+	ret = device_add(dev);
+	if (ret)
+		return ERR_PTR(ret);
+
+	return no_free_ptr(tsm);
+}
+
+static void tdx_subsys_init(void)
+{
+	struct tdx_tsm *tdx_tsm;
+	int err;
+
+	/* Establish subsystem for global TDX module attributes */
+	err = subsys_virtual_register(&tdx_subsys, NULL);
+	if (err) {
+		pr_err("failed to register tdx_subsys %d\n", err);
+		return;
+	}
+
+	/* Register 'tdx_tsm' for driving optional TDX Connect functionality */
+	tdx_tsm = init_tdx_tsm();
+	if (IS_ERR(tdx_tsm)) {
+		pr_err("failed to initialize TSM device (%pe)\n", tdx_tsm);
+		goto err_bus;
+	}
+
+	return;
+
+err_bus:
+	bus_unregister(&tdx_subsys);
+}
+
 static int init_tdx_module(void)
 {
 	int ret;
@@ -1136,6 +1209,8 @@ static int init_tdx_module(void)
 
 	pr_info("%lu KB allocated for PAMT\n", tdmrs_count_pamt_kb(&tdx_tdmr_list));
 
+	tdx_subsys_init();
+
 out_put_tdxmem:
 	/*
 	 * @tdx_memlist is written here and read at memory hotplug time.

---

## [6] Chao Gao — 2025-05-23
*Subject: [RFC PATCH 05/20] x86/virt/tdx: Export tdx module attributes via sysfs*

TD-Preserving updates depend on a userspace tool to select the appropriate
module to load. To facilitate this decision-making process, expose the
necessary information to userspace.

Expose the current module versions so that userspace can verify
compatibility with new modules. version information is also valuable for
debugging, as knowing the exact module version can help reproduce
TDX-related issues.

Attach the TDX module attributes to the virtual TDX_TSM device, which
represents the TDX module and its features, such as TDX Connect.

Note changes to tdx_global_metadata.{hc} are auto-generated by following
the instructions detailed in [1], after modifying "version" to "versions"
in the TDX_STRUCT of tdx.py to accurately reflect that it is a collection
of versions.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
Link: https://lore.kernel.org/kvm/20250226181453.2311849-12-pbonzini@redhat.com/ [1]
---
 Documentation/ABI/testing/sysfs-devices-tdx |  8 ++++++++
 MAINTAINERS                                 |  1 +
 arch/x86/include/asm/tdx_global_metadata.h  |  7 +++++++
 arch/x86/virt/vmx/tdx/tdx.c                 | 19 +++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c | 16 ++++++++++++++++
 5 files changed, 51 insertions(+)
 create mode 100644 Documentation/ABI/testing/sysfs-devices-tdx

diff --git a/Documentation/ABI/testing/sysfs-devices-tdx b/Documentation/ABI/testing/sysfs-devices-tdx
new file mode 100644
index 000000000000..ccbe6431241e
--- /dev/null
+++ b/Documentation/ABI/testing/sysfs-devices-tdx
@@ -0,0 +1,8 @@
+What:		/sys/devices/virtual/tdx/tdx_tsm/version
+Date:		March 2025
+KernelVersion:	v6.15
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) Report the version of the loaded TDX module. The TDX module
+		version is formatted as x.y.z, where "x" is the major version,
+		"y" is the minor version and "z" is the update version. Versions
+		are used for bug reporting, TD-Preserving updates and etc.
diff --git a/MAINTAINERS b/MAINTAINERS
index c59316109e3f..0d58256c765b 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -26227,6 +26227,7 @@ L:	x86@kernel.org
 L:	linux-coco@lists.linux.dev
 S:	Supported
 T:	git git://git.kernel.org/pub/scm/linux/kernel/git/tip/tip.git x86/tdx
+F:	Documentation/ABI/testing/sysfs-devices-tdx
 F:	arch/x86/boot/compressed/tdx*
 F:	arch/x86/coco/tdx/
 F:	arch/x86/include/asm/shared/tdx.h
diff --git a/arch/x86/include/asm/tdx_global_metadata.h b/arch/x86/include/asm/tdx_global_metadata.h
index 060a2ad744bf..ce0370f4a5b9 100644
--- a/arch/x86/include/asm/tdx_global_metadata.h
+++ b/arch/x86/include/asm/tdx_global_metadata.h
@@ -5,6 +5,12 @@
 
 #include <linux/types.h>
 
+struct tdx_sys_info_versions {
+	u16 minor_version;
+	u16 major_version;
+	u16 update_version;
+};
+
 struct tdx_sys_info_features {
 	u64 tdx_features0;
 };
@@ -35,6 +41,7 @@ struct tdx_sys_info_td_conf {
 };
 
 struct tdx_sys_info {
+	struct tdx_sys_info_versions versions;
 	struct tdx_sys_info_features features;
 	struct tdx_sys_info_tdmr tdmr;
 	struct tdx_sys_info_td_ctrl td_ctrl;
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 9719df2f2634..5f1f463ddfe1 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1090,6 +1090,24 @@ struct tdx_tsm {
 	struct device dev;
 };
 
+static ssize_t version_show(struct device *dev, struct device_attribute *attr,
+			    char *buf)
+{
+	const struct tdx_sys_info_versions *v = &tdx_sysinfo.versions;
+
+	return sysfs_emit(buf, "%u.%u.%u\n", v->major_version,
+					     v->minor_version,
+					     v->update_version);
+}
+
+static DEVICE_ATTR_RO(version);
+
+static struct attribute *tdx_module_attrs[] = {
+	&dev_attr_version.attr,
+	NULL,
+};
+ATTRIBUTE_GROUPS(tdx_module);
+
 static struct tdx_tsm *alloc_tdx_tsm(void)
 {
 	struct tdx_tsm *tsm = kzalloc(sizeof(*tsm), GFP_KERNEL);
@@ -1117,6 +1135,7 @@ static struct tdx_tsm *init_tdx_tsm(void)
 		return tsm;
 
 	dev = &tsm->dev;
+	dev->groups = tdx_module_groups;
 	ret = dev_set_name(dev, "tdx_tsm");
 	if (ret)
 		return ERR_PTR(ret);
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index 13ad2663488b..088e5bff4025 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -7,6 +7,21 @@
  * Include this file to other C file instead.
  */
 
+static int get_tdx_sys_info_versions(struct tdx_sys_info_versions *sysinfo_versions)
+{
+	int ret = 0;
+	u64 val;
+
+	if (!ret && !(ret = read_sys_metadata_field(0x0800000100000003, &val)))
+		sysinfo_versions->minor_version = val;
+	if (!ret && !(ret = read_sys_metadata_field(0x0800000100000004, &val)))
+		sysinfo_versions->major_version = val;
+	if (!ret && !(ret = read_sys_metadata_field(0x0800000100000005, &val)))
+		sysinfo_versions->update_version = val;
+
+	return ret;
+}
+
 static int get_tdx_sys_info_features(struct tdx_sys_info_features *sysinfo_features)
 {
 	int ret = 0;
@@ -89,6 +104,7 @@ static int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 {
 	int ret = 0;
 
+	ret = ret ?: get_tdx_sys_info_versions(&sysinfo->versions);
 	ret = ret ?: get_tdx_sys_info_features(&sysinfo->features);
 	ret = ret ?: get_tdx_sys_info_tdmr(&sysinfo->tdmr);
 	ret = ret ?: get_tdx_sys_info_td_ctrl(&sysinfo->td_ctrl);

---

## [7] Chao Gao — 2025-05-23
*Subject: [RFC PATCH 06/20] x86/virt/seamldr: Add a helper to read P-SEAMLDR information*

Add a helper function to retrieve P-SEAMLDR information, including its
version and features, using the dedicated P_SEAMLDR_INFO API. This is in
preparation for exposing this information to userspace. Userspace will
utilize the version number to verify the compatibility of TDX modules
with the P-SEAMLDR

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/virt/vmx/tdx/seamldr.c | 28 +++++++++++++++++++++++++++-
 1 file changed, 27 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index a252f1ae3483..c2771323729c 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -11,7 +11,26 @@
 #include "tdx.h"
 #include "../vmx.h"
 
-static __maybe_unused int seamldr_call(u64 fn, struct tdx_module_args *args)
+ /* P-SEAMLDR SEAMCALL leaf function */
+#define P_SEAMLDR_INFO			0x8000000000000000
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
+static struct seamldr_info seamldr_info __aligned(256);
+
+static inline int seamldr_call(u64 fn, struct tdx_module_args *args)
 {
 	u64 vmcs;
 	int ret;
@@ -42,3 +61,10 @@ static __maybe_unused int seamldr_call(u64 fn, struct tdx_module_args *args)
 
 	return ret;
 }
+
+static __maybe_unused int get_seamldr_info(void)
+{
+	struct tdx_module_args args = { .rcx = __pa(&seamldr_info) };
+
+	return seamldr_call(P_SEAMLDR_INFO, &args);
+}

---

## [8] Chao Gao — 2025-05-23
*Subject: [RFC PATCH 07/20] x86/virt/tdx: Expose SEAMLDR information via sysfs*

TD-Preserving updates depend on a userspace tool to select the appropriate
module to load. To facilitate this decision-making process, expose the
necessary information to userspace.

SEAMLDR version information can be used for compatibility check and
num_remaining_updates indicates how many updates can still be performed.

SEAMLDR serves as the foundation of TDX, as it is responsible for loading
the TDX module and, in other words, enabling the entire TDX system.
Therefore, attach its attributes to the root device of the new TDX virtual
subsystem.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 Documentation/ABI/testing/sysfs-devices-tdx | 24 ++++++++++++++
 arch/x86/virt/vmx/tdx/seamldr.c             | 35 ++++++++++++++++++++-
 arch/x86/virt/vmx/tdx/seamldr.h             | 14 +++++++++
 arch/x86/virt/vmx/tdx/tdx.c                 | 14 ++++++++-
 4 files changed, 85 insertions(+), 2 deletions(-)
 create mode 100644 arch/x86/virt/vmx/tdx/seamldr.h

diff --git a/Documentation/ABI/testing/sysfs-devices-tdx b/Documentation/ABI/testing/sysfs-devices-tdx
index ccbe6431241e..112f0738253b 100644
--- a/Documentation/ABI/testing/sysfs-devices-tdx
+++ b/Documentation/ABI/testing/sysfs-devices-tdx
@@ -6,3 +6,27 @@ Description:	(RO) Report the version of the loaded TDX module. The TDX module
 		version is formatted as x.y.z, where "x" is the major version,
 		"y" is the minor version and "z" is the update version. Versions
 		are used for bug reporting, TD-Preserving updates and etc.
+
+What:		/sys/devices/virtual/tdx/seamldr/version
+Date:		March 2025
+KernelVersion:	v6.15
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) Reports the version of the loaded SEAM loader. The SEAM
+		loader version is formatted as x.y.z, where "x" is the major
+		version, "y" is the minor version and "z" is the update version.
+		Versions are used for bug reporting and compatibility check.
+
+What:		/sys/devices/virtual/tdx/seamldr/num_remaining_updates
+Date:		March 2025
+KernelVersion:	v6.15
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) Reports the number of remaining updates that can be
+		performed via TD-Preserving updates. It is always zero if
+		SEAMLDR doesn't TD-Preserving updates. Otherwise, it is an
+		arch-specific value after bootup. This value decreases by one
+		after each successful TD-Preserving update. Once it reaches
+		zero, further TD-Preserving updates will fail until next reboot.
+
+		See Intel® Trust Domain Extensions - SEAM Loader (SEAMLDR)
+		Interface Specification Chapter 3.3 "SEAMLDR_INFO" and Chapter
+		4.2 "SEAMLDR.INSTALL" for more information.
diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index c2771323729c..b628555daf55 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -7,9 +7,13 @@
 #define pr_fmt(fmt)	"seamldr: " fmt
 
 #include <linux/cleanup.h>
+#include <linux/device.h>
+#include <linux/kobject.h>
+#include <linux/sysfs.h>
 
 #include "tdx.h"
 #include "../vmx.h"
+#include "seamldr.h"
 
  /* P-SEAMLDR SEAMCALL leaf function */
 #define P_SEAMLDR_INFO			0x8000000000000000
@@ -62,7 +66,36 @@ static inline int seamldr_call(u64 fn, struct tdx_module_args *args)
 	return ret;
 }
 
-static __maybe_unused int get_seamldr_info(void)
+static ssize_t version_show(struct device *dev, struct device_attribute *attr,
+			    char *buf)
+{
+	return sysfs_emit(buf, "%u.%u.%u\n", seamldr_info.major_version,
+					     seamldr_info.minor_version,
+					     seamldr_info.update_version);
+}
+
+static ssize_t num_remaining_updates_show(struct device *dev,
+					  struct device_attribute *attr,
+					  char *buf)
+{
+	return sysfs_emit(buf, "%u\n", seamldr_info.num_remaining_updates);
+}
+
+static DEVICE_ATTR_RO(version);
+static DEVICE_ATTR_RO(num_remaining_updates);
+
+static struct attribute *seamldr_attrs[] = {
+	&dev_attr_version.attr,
+	&dev_attr_num_remaining_updates.attr,
+	NULL,
+};
+
+struct attribute_group seamldr_group = {
+	.name = "seamldr",
+	.attrs = seamldr_attrs,
+};
+
+int get_seamldr_info(void)
 {
 	struct tdx_module_args args = { .rcx = __pa(&seamldr_info) };
 
diff --git a/arch/x86/virt/vmx/tdx/seamldr.h b/arch/x86/virt/vmx/tdx/seamldr.h
new file mode 100644
index 000000000000..15597cb5036d
--- /dev/null
+++ b/arch/x86/virt/vmx/tdx/seamldr.h
@@ -0,0 +1,14 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+#ifndef _X86_VIRT_VMX_TDX_SEAMLDR_H
+#define _X86_VIRT_VMX_TDX_SEAMLDR_H
+
+#ifdef CONFIG_INTEL_TDX_MODULE_UPDATE
+extern struct attribute_group seamldr_group;
+#define SEAMLDR_GROUP (&seamldr_group)
+int get_seamldr_info(void);
+#else
+#define SEAMLDR_GROUP NULL
+static inline int get_seamldr_info(void) { return 0; }
+#endif
+
+#endif
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 5f1f463ddfe1..aa6a23d46494 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -41,6 +41,7 @@
 #include <asm/processor.h>
 #include <asm/mce.h>
 #include "tdx.h"
+#include "seamldr.h"
 
 static u32 tdx_global_keyid __ro_after_init;
 static u32 tdx_guest_keyid_start __ro_after_init;
@@ -1147,13 +1148,24 @@ static struct tdx_tsm *init_tdx_tsm(void)
 	return no_free_ptr(tsm);
 }
 
+static const struct attribute_group *tdx_subsys_groups[] = {
+	SEAMLDR_GROUP,
+	NULL,
+};
+
 static void tdx_subsys_init(void)
 {
 	struct tdx_tsm *tdx_tsm;
 	int err;
 
+	err = get_seamldr_info();
+	if (err) {
+		pr_err("failed to get seamldr info %d\n", err);
+		return;
+	}
+
 	/* Establish subsystem for global TDX module attributes */
-	err = subsys_virtual_register(&tdx_subsys, NULL);
+	err = subsys_virtual_register(&tdx_subsys, tdx_subsys_groups);
 	if (err) {
 		pr_err("failed to register tdx_subsys %d\n", err);
 		return;

---

## [9] Chao Gao — 2025-05-23
*Subject: [RFC PATCH 08/20] x86/virt/seamldr: Implement FW_UPLOAD sysfs ABI for TD-Preserving Updates*

Implement a fw_upload interface to coordinate TD-Preserving updates. The
explicit file selection capabilities of fw_upload is preferred over the
implicit file selection of request_firmware() for the following reasons:

a. Intel distributes all versions of the TDX module, allowing admins to
load any version rather than always defaulting to the latest. This
flexibility is necessary because future extensions may require reverting to
a previous version to clear fatal errors.

b. Some module version series are platform-specific. For example, the 1.5.x
series is for certain platform generations, while the 2.0.x series is
intended for others.

c. The update policy for TD-Preserving is non-linear at times. The latest
TDX module may not be TD-Preserving capable. For example, TDX module
1.5.x may be updated to 1.5.y but not to 1.5.y+1. This policy is documented
separately in a file released along with each TDX module release.

So, the default policy of "request_firmware()" of "always load latest", is
not suitable for TDX. Userspace needs to deploy a more sophisticated policy
check (i.e. latest may not be TD-Preserving capable), and there is
potential operator choice to consider.

Just have userspace pick rather than add kernel mechanism to change the
default policy of request_firmware().

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/Kconfig                |  2 +
 arch/x86/virt/vmx/tdx/seamldr.c | 77 +++++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/seamldr.h |  2 +
 arch/x86/virt/vmx/tdx/tdx.c     |  4 ++
 4 files changed, 85 insertions(+)

diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
index 8b1e0986b7f8..31385104a6ee 100644
--- a/arch/x86/Kconfig
+++ b/arch/x86/Kconfig
@@ -1935,6 +1935,8 @@ config INTEL_TDX_HOST
 config INTEL_TDX_MODULE_UPDATE
 	bool "Intel TDX module runtime update"
 	depends on INTEL_TDX_HOST
+	select FW_LOADER
+	select FW_UPLOAD
 	help
 	  This enables the kernel to support TDX module runtime update. This allows
 	  the admin to upgrade the TDX module to a newer one without the need to
diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index b628555daf55..da862e71ebce 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -8,6 +8,8 @@
 
 #include <linux/cleanup.h>
 #include <linux/device.h>
+#include <linux/firmware.h>
+#include <linux/gfp.h>
 #include <linux/kobject.h>
 #include <linux/sysfs.h>
 
@@ -32,6 +34,15 @@ struct seamldr_info {
 	u8	reserved1[224];
 } __packed;
 
+
+#define TDX_FW_STATE_BITS	32
+#define TDX_FW_CANCEL		0
+struct tdx_status {
+	DECLARE_BITMAP(fw_state, TDX_FW_STATE_BITS);
+};
+
+struct fw_upload *tdx_fwl;
+static struct tdx_status tdx_status;
 static struct seamldr_info seamldr_info __aligned(256);
 
 static inline int seamldr_call(u64 fn, struct tdx_module_args *args)
@@ -101,3 +112,69 @@ int get_seamldr_info(void)
 
 	return seamldr_call(P_SEAMLDR_INFO, &args);
 }
+
+static int seamldr_install_module(const u8 *data, u32 size)
+{
+	return -EOPNOTSUPP;
+}
+
+static enum fw_upload_err tdx_fw_prepare(struct fw_upload *fwl,
+					 const u8 *data, u32 size)
+{
+	struct tdx_status *status = fwl->dd_handle;
+
+	if (test_and_clear_bit(TDX_FW_CANCEL, status->fw_state))
+		return FW_UPLOAD_ERR_CANCELED;
+
+	return FW_UPLOAD_ERR_NONE;
+}
+
+static enum fw_upload_err tdx_fw_write(struct fw_upload *fwl, const u8 *data,
+				       u32 offset, u32 size, u32 *written)
+{
+	struct tdx_status *status = fwl->dd_handle;
+
+	if (test_and_clear_bit(TDX_FW_CANCEL, status->fw_state))
+		return FW_UPLOAD_ERR_CANCELED;
+
+	/*
+	 * No partial write will be returned to callers so @offset should
+	 * always be zero.
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
+	return FW_UPLOAD_ERR_NONE;
+}
+
+static void tdx_fw_cancel(struct fw_upload *fwl)
+{
+	struct tdx_status *status = fwl->dd_handle;
+
+	set_bit(TDX_FW_CANCEL, status->fw_state);
+}
+
+static const struct fw_upload_ops tdx_fw_ops = {
+	.prepare = tdx_fw_prepare,
+	.write = tdx_fw_write,
+	.poll_complete = tdx_fw_poll_complete,
+	.cancel = tdx_fw_cancel,
+};
+
+void seamldr_init(struct device *dev)
+{
+	int ret;
+
+	tdx_fwl = firmware_upload_register(THIS_MODULE, dev, "seamldr_upload",
+					   &tdx_fw_ops, &tdx_status);
+	ret = PTR_ERR_OR_ZERO(tdx_fwl);
+	if (ret)
+		pr_err("failed to register module uploader %d\n", ret);
+}
diff --git a/arch/x86/virt/vmx/tdx/seamldr.h b/arch/x86/virt/vmx/tdx/seamldr.h
index 15597cb5036d..00fa3a4e9155 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.h
+++ b/arch/x86/virt/vmx/tdx/seamldr.h
@@ -6,9 +6,11 @@
 extern struct attribute_group seamldr_group;
 #define SEAMLDR_GROUP (&seamldr_group)
 int get_seamldr_info(void);
+void seamldr_init(struct device *dev);
 #else
 #define SEAMLDR_GROUP NULL
 static inline int get_seamldr_info(void) { return 0; }
+static inline void seamldr_init(struct device *dev) { }
 #endif
 
 #endif
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index aa6a23d46494..22ffc15b4299 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1178,6 +1178,10 @@ static void tdx_subsys_init(void)
 		goto err_bus;
 	}
 
+	struct device *dev_root __free(put_device) = bus_get_dev_root(&tdx_subsys);
+	if (dev_root)
+		seamldr_init(dev_root);
+
 	return;
 
 err_bus:

---

## [10] Chao Gao — 2025-05-23
*Subject: [RFC PATCH 09/20] x86/virt/seamldr: Allocate and populate a module update request*

Allocate and populate a module update request, i.e., struct seamldr_params,
as defined in "SEAM Loader (SEAMLDR) Interface Specification" [1],
Revision 343755-004, Section 3.2.

struct seamldr_params includes a module binary, a sigstruct file, and an
update scenario. Parse the bitstream format, as defined by Intel, to
extract the binary and the sigstruct.

Currently, only the "UPDATE" scenario is supported.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
Link: https://cdrdv2.intel.com/v1/dl/getContent/733584 [1]
---
 arch/x86/virt/vmx/tdx/seamldr.c | 145 +++++++++++++++++++++++++++++++-
 1 file changed, 144 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index da862e71ebce..cdf85dff6d69 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -11,6 +11,8 @@
 #include <linux/firmware.h>
 #include <linux/gfp.h>
 #include <linux/kobject.h>
+#include <linux/mm.h>
+#include <linux/slab.h>
 #include <linux/sysfs.h>
 
 #include "tdx.h"
@@ -41,6 +43,26 @@ struct tdx_status {
 	DECLARE_BITMAP(fw_state, TDX_FW_STATE_BITS);
 };
 
+/* SEAMLDR can accept up to 496 4KB pages for TDX module binary */
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
 struct fw_upload *tdx_fwl;
 static struct tdx_status tdx_status;
 static struct seamldr_info seamldr_info __aligned(256);
@@ -113,9 +135,130 @@ int get_seamldr_info(void)
 	return seamldr_call(P_SEAMLDR_INFO, &args);
 }
 
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
+	/* current seamldr_params accepts one 4KB-page for sigstruct */
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
+	params->num_module_pages = DIV_ROUND_UP(module_size, SZ_4K);
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
+/* Verify that the checksum of the entire blob is zero */
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
+	const void *sig, *module;
+	int module_size, sig_size;
+
+	/* Split the given blob into a sigstruct and a module */
+	sig = blob->data;
+	sig_size = blob->offset_of_module - sizeof(struct tdx_blob);
+	module = data + blob->offset_of_module;
+	module_size = size - blob->offset_of_module;
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
+/*
+ * Temporary flag to guard TD-Preserving updates. This will be removed once
+ * all necessary components for its support are integrated.
+ */
+static bool td_preserving_ready;
+
+DEFINE_FREE(free_seamldr_params, struct seamldr_params *,
+	    if (!IS_ERR_OR_NULL(_T)) free_seamldr_params(_T))
+
 static int seamldr_install_module(const u8 *data, u32 size)
 {
-	return -EOPNOTSUPP;
+	if (!td_preserving_ready)
+		return -EOPNOTSUPP;
+
+	struct seamldr_params *params __free(free_seamldr_params) =
+						init_seamldr_params(data, size);
+	if (IS_ERR(params))
+		return PTR_ERR(params);
+
+	/* TODO: Install and initialize the new TDX module */
+
+	return 0;
 }
 
 static enum fw_upload_err tdx_fw_prepare(struct fw_upload *fwl,

---

## [11] Chao Gao — 2025-05-23
*Subject: [RFC PATCH 10/20] x86/virt/seamldr: Introduce skeleton for TD-Preserving updates*

To perform TD-Preserving updates, the kernel must stop invoking any TDX
module SEAMCALLs. Currently, these SEAMCALLs can be invoked in various
contexts and in parallel across CPUs. Additionally, considering the need to
force all vCPUs out of guest mode, no single lock primitive, except for
stop_machine(), can meet this requirement.

A failed attempt is to lock all KVM entry points and kick all vCPUs. But it
cannot be done within KVM TDX code. And it needs to introduce new
infrastructure and maintenance burden outside of tdx for questionable
benefits.

Perform TD-Preserving updates within stop_machine() as it achieves the
seamldr requirements and is an existing well understood mechanism.

TD-Preserving updates consist of several steps: shutting down the old
module, installing the new module, and initializing the new one and etc.
Some steps must be executed on a single CPU, others serially across all
CPUs, and some can be performed concurrently on all CPUs and there are
ordering requirements between steps. So, all CPUs need to perform the work
in a step-locked manner.

In preparation for adding concrete steps for TD-Preserving updates,
establish the framework by mimicking multi_cpu_stop(). Specifically, use a
global state machine to control the work done on each CPU and require all
CPUs to acknowledge completion before proceeding to the next stage.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
instead of copy-pasting multi_cpu_stop(), would it be better to
abstract a common function and adapt it for TD-Preserving updates?
---
 arch/x86/virt/vmx/tdx/seamldr.c | 63 +++++++++++++++++++++++++++++++--
 1 file changed, 60 insertions(+), 3 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index cdf85dff6d69..01dc2b0bc4a5 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -12,7 +12,9 @@
 #include <linux/gfp.h>
 #include <linux/kobject.h>
 #include <linux/mm.h>
+#include <linux/nmi.h>
 #include <linux/slab.h>
+#include <linux/stop_machine.h>
 #include <linux/sysfs.h>
 
 #include "tdx.h"
@@ -237,6 +239,62 @@ static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
 	return alloc_seamldr_params(module, module_size, sig, sig_size);
 }
 
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
+static void set_state(enum tdp_state state)
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
+		set_state(tdp_data.state + 1);
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
+		}
+		rcu_momentary_eqs();
+	} while (curstate != TDP_DONE);
+
+	return ret;
+}
+
 /*
  * Temporary flag to guard TD-Preserving updates. This will be removed once
  * all necessary components for its support are integrated.
@@ -256,9 +314,8 @@ static int seamldr_install_module(const u8 *data, u32 size)
 	if (IS_ERR(params))
 		return PTR_ERR(params);
 
-	/* TODO: Install and initialize the new TDX module */
-
-	return 0;
+	set_state(TDP_START + 1);
+	return stop_machine(do_seamldr_install_module, params, cpu_online_mask);
 }
 
 static enum fw_upload_err tdx_fw_prepare(struct fw_upload *fwl,

---

## [12] Chao Gao — 2025-05-23
*Subject: [RFC PATCH 11/20] x86/virt/seamldr: Abort updates if errors occurred midway*

The update process is divided into multiple stages, each of which may
encounter failures. However, the current state machine for updates proceeds
to the next stage regardless of errors.

Continuing updates when errors occur midway is pointless.

Implement a mechanism that transitions directly to the final stage,
effectively aborting the update and skipping all remaining stages when an
error is detected.

This is in preparation for adding the first stage that may fail.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/virt/vmx/tdx/seamldr.c | 17 +++++++++++++++--
 1 file changed, 15 insertions(+), 2 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 01dc2b0bc4a5..9d0d37a92bfd 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -247,6 +247,7 @@ enum tdp_state {
 static struct {
 	enum tdp_state state;
 	atomic_t thread_ack;
+	atomic_t failed;
 } tdp_data;
 
 static void set_state(enum tdp_state state)
@@ -261,8 +262,16 @@ static void set_state(enum tdp_state state)
 /* Last one to ack a state moves to the next state. */
 static void ack_state(void)
 {
-	if (atomic_dec_and_test(&tdp_data.thread_ack))
-		set_state(tdp_data.state + 1);
+	if (atomic_dec_and_test(&tdp_data.thread_ack)) {
+		/*
+		 * If an error occurred, abort the update by skipping to
+		 * the final state
+		 */
+		if (atomic_read(&tdp_data.failed))
+			set_state(TDP_DONE);
+		else
+			set_state(tdp_data.state + 1);
+	}
 }
 
 /*
@@ -285,6 +294,9 @@ static int do_seamldr_install_module(void *params)
 			default:
 				break;
 			}
+
+			if (ret)
+				atomic_inc(&tdp_data.failed);
 			ack_state();
 		} else {
 			touch_nmi_watchdog();
@@ -314,6 +326,7 @@ static int seamldr_install_module(const u8 *data, u32 size)
 	if (IS_ERR(params))
 		return PTR_ERR(params);
 
+	atomic_set(&tdp_data.failed, 0);
 	set_state(TDP_START + 1);
 	return stop_machine(do_seamldr_install_module, params, cpu_online_mask);
 }

---

## [13] Chao Gao — 2025-05-23
*Subject: [RFC PATCH 12/20] x86/virt/seamldr: Shut down the current TDX module*

TD-Preserving updates request shutting down the existing TDX module.
During this shutdown, the module generates hand-off data, which captures
the module's states essential for preserving running TDs. The new TDX
module can utilize this hand-off data to establish its states.

Invoke the TDH_SYS_SHUTDOWN API on one CPU to perform the shutdown. This
API requires a hand-off module version. Use the module's own hand-off
version, as it is the highest version the module can produce and is more
likely to be compatible with new modules.

Changes to tdx_global_metadata.{hc} are auto-generated by following the
instructions detailed in [1], after adding the following section to the
tdx.py script:

    "handoff": [
       "MODULE_HV",
    ],

Add a check to ensure that module_hv is guarded by the TDX module's
support for TD-Preserving.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
Link: https://lore.kernel.org/kvm/20250226181453.2311849-12-pbonzini@redhat.com/ [1]
---
 arch/x86/include/asm/tdx_global_metadata.h  |  5 +++++
 arch/x86/virt/vmx/tdx/seamldr.c             | 11 +++++++++++
 arch/x86/virt/vmx/tdx/tdx.c                 | 18 ++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h                 |  4 ++++
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c | 13 +++++++++++++
 5 files changed, 51 insertions(+)

diff --git a/arch/x86/include/asm/tdx_global_metadata.h b/arch/x86/include/asm/tdx_global_metadata.h
index ce0370f4a5b9..a2011a3575ff 100644
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
 	struct tdx_sys_info_versions versions;
 	struct tdx_sys_info_features features;
 	struct tdx_sys_info_tdmr tdmr;
 	struct tdx_sys_info_td_ctrl td_ctrl;
 	struct tdx_sys_info_td_conf td_conf;
+	struct tdx_sys_info_handoff handoff;
 };
 
 #endif
diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 9d0d37a92bfd..11c0c5a93c32 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -241,6 +241,7 @@ static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
 
 enum tdp_state {
 	TDP_START,
+	TDP_SHUTDOWN,
 	TDP_DONE,
 };
 
@@ -281,8 +282,12 @@ static void ack_state(void)
 static int do_seamldr_install_module(void *params)
 {
 	enum tdp_state newstate, curstate = TDP_START;
+	int cpu = smp_processor_id();
+	bool primary;
 	int ret = 0;
 
+	primary = !!(cpumask_first(cpu_online_mask) == cpu);
+
 	do {
 		/* Chill out and ensure we re-read tdp_data. */
 		cpu_relax();
@@ -291,6 +296,12 @@ static int do_seamldr_install_module(void *params)
 		if (newstate != curstate) {
 			curstate = newstate;
 			switch (curstate) {
+			case TDP_SHUTDOWN:
+				if (!primary)
+					break;
+
+				ret = tdx_module_shutdown();
+				break;
 			default:
 				break;
 			}
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 22ffc15b4299..fa6b3f1eb197 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -295,6 +295,11 @@ static int read_sys_metadata_field(u64 field_id, u64 *data)
 	return 0;
 }
 
+static bool tdx_has_td_preserving(void)
+{
+	return tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_TD_PRESERVING;
+}
+
 #include "tdx_global_metadata.c"
 
 static int check_features(struct tdx_sys_info *sysinfo)
@@ -1341,6 +1346,19 @@ int tdx_enable(void)
 }
 EXPORT_SYMBOL_GPL(tdx_enable);
 
+int tdx_module_shutdown(void)
+{
+	struct tdx_module_args args = {};
+
+	/*
+	 * Shut down TDX module and prepare handoff data for the next TDX module.
+	 * Following a successful TDH_SYS_SHUTDOWN, further TDX module APIs will
+	 * fail.
+	 */
+	args.rcx = tdx_sysinfo.handoff.module_hv;
+	return seamcall_prerr(TDH_SYS_SHUTDOWN, &args);
+}
+
 static bool is_pamt_page(unsigned long phys)
 {
 	struct tdmr_info_list *tdmr_list = &tdx_tdmr_list;
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 48c0a850c621..3830dee4da91 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -48,6 +48,7 @@
 #define TDH_PHYMEM_PAGE_WBINVD		41
 #define TDH_VP_WR			43
 #define TDH_SYS_CONFIG			45
+#define TDH_SYS_SHUTDOWN		52
 
 /*
  * SEAMCALL leaf:
@@ -87,6 +88,7 @@ struct tdmr_info {
 } __packed __aligned(TDMR_INFO_ALIGNMENT);
 
 /* Bit definitions of TDX_FEATURES0 metadata field */
+#define TDX_FEATURES0_TD_PRESERVING	BIT(1)
 #define TDX_FEATURES0_NO_RBP_MOD	BIT(18)
 
 /*
@@ -122,4 +124,6 @@ struct tdmr_info_list {
 
 int seamldr_prerr(u64 fn, struct tdx_module_args *args);
 
+int tdx_module_shutdown(void);
+
 #endif
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index 088e5bff4025..a17cbb82e6b8 100644
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
+	if (!ret && tdx_has_td_preserving() &&
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

## [14] Chao Gao — 2025-05-23
*Subject: [RFC PATCH 13/20] x86/virt/tdx: Reset software states after TDX module shutdown*

Reset all software states used to track and guard TDX global and per-CPU
initialization (i.e. TDH.SYS.INIT and TDH.SYS.LP.INIT). the kernel needs to
do them again after TD-Preserving updates.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 24 +++++++++++++++++++++---
 1 file changed, 21 insertions(+), 3 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index fa6b3f1eb197..4cdeec0a4128 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -56,6 +56,9 @@ static struct tdmr_info_list tdx_tdmr_list;
 static enum tdx_module_status_t tdx_module_status;
 static DEFINE_MUTEX(tdx_module_lock);
 
+static bool sysinit_done;
+static int sysinit_ret;
+
 /* All TDX-usable memory regions.  Protected by mem_hotplug_lock. */
 static LIST_HEAD(tdx_memlist);
 
@@ -130,8 +133,6 @@ static int try_init_module_global(void)
 {
 	struct tdx_module_args args = {};
 	static DEFINE_RAW_SPINLOCK(sysinit_lock);
-	static bool sysinit_done;
-	static int sysinit_ret;
 
 	lockdep_assert_irqs_disabled();
 
@@ -1346,9 +1347,22 @@ int tdx_enable(void)
 }
 EXPORT_SYMBOL_GPL(tdx_enable);
 
+static void tdx_module_reset_state(void)
+{
+	int cpu;
+
+	tdx_module_status = TDX_MODULE_UNINITIALIZED;
+	sysinit_done = false;
+	sysinit_ret = 0;
+
+	for_each_online_cpu(cpu)
+		per_cpu(tdx_lp_initialized, cpu) = false;
+}
+
 int tdx_module_shutdown(void)
 {
 	struct tdx_module_args args = {};
+	int ret;
 
 	/*
 	 * Shut down TDX module and prepare handoff data for the next TDX module.
@@ -1356,7 +1370,11 @@ int tdx_module_shutdown(void)
 	 * fail.
 	 */
 	args.rcx = tdx_sysinfo.handoff.module_hv;
-	return seamcall_prerr(TDH_SYS_SHUTDOWN, &args);
+	ret = seamcall_prerr(TDH_SYS_SHUTDOWN, &args);
+	if (!ret)
+		tdx_module_reset_state();
+
+	return ret;
 }
 
 static bool is_pamt_page(unsigned long phys)

---

## [15] Chao Gao — 2025-05-23
*Subject: [RFC PATCH 14/20] x86/virt/seamldr: Install a new TDX module*

Invoke the P_SEAMLDR_INSTALL API serially on all online CPUs to install a
new TDX module. "Serially" is a requirement of P-SEAMLDR and is enforced by
a new spinlock.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/virt/vmx/tdx/seamldr.c | 8 ++++++++
 1 file changed, 8 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 11c0c5a93c32..1ecb5d3088af 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -23,6 +23,7 @@
 
  /* P-SEAMLDR SEAMCALL leaf function */
 #define P_SEAMLDR_INFO			0x8000000000000000
+#define P_SEAMLDR_INSTALL		0x8000000000000001
 
 struct seamldr_info {
 	u32	version;
@@ -68,6 +69,7 @@ struct seamldr_params {
 struct fw_upload *tdx_fwl;
 static struct tdx_status tdx_status;
 static struct seamldr_info seamldr_info __aligned(256);
+static DEFINE_RAW_SPINLOCK(seamldr_lock);
 
 static inline int seamldr_call(u64 fn, struct tdx_module_args *args)
 {
@@ -242,6 +244,7 @@ static struct seamldr_params *init_seamldr_params(const u8 *data, u32 size)
 enum tdp_state {
 	TDP_START,
 	TDP_SHUTDOWN,
+	TDP_CPU_INSTALL,
 	TDP_DONE,
 };
 
@@ -281,6 +284,7 @@ static void ack_state(void)
  */
 static int do_seamldr_install_module(void *params)
 {
+	struct tdx_module_args args = { .rcx = __pa(params) };
 	enum tdp_state newstate, curstate = TDP_START;
 	int cpu = smp_processor_id();
 	bool primary;
@@ -302,6 +306,10 @@ static int do_seamldr_install_module(void *params)
 
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

## [16] Chao Gao — 2025-05-23
*Subject: [RFC PATCH 15/20] x86/virt/seamldr: Handle TD-Preserving update failures*

Failure encounterred after the module shutdown are unrecoverable. All
subsequent SEAMCALLs will fail and TDs will be killed.

Report the error through sysfs attributes and log a message to clarify that
SEAMCALL errors are expected in this situation.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/virt/vmx/tdx/seamldr.c | 15 ++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx.c     | 13 +++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h     |  1 +
 3 files changed, 28 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 1ecb5d3088af..a18df08a5528 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -278,6 +278,14 @@ static void ack_state(void)
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
@@ -314,8 +322,13 @@ static int do_seamldr_install_module(void *params)
 				break;
 			}
 
-			if (ret)
+			if (ret) {
 				atomic_inc(&tdp_data.failed);
+				if (curstate >= TDP_CPU_INSTALL) {
+					tdx_module_set_error();
+					print_update_failure_message();
+				}
+			}
 			ack_state();
 		} else {
 			touch_nmi_watchdog();
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 4cdeec0a4128..331c86eeddcf 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1102,6 +1102,13 @@ static ssize_t version_show(struct device *dev, struct device_attribute *attr,
 {
 	const struct tdx_sys_info_versions *v = &tdx_sysinfo.versions;
 
+	/*
+	 * Inform userspace that the TDX module isn't in a usable state,
+	 * possibly due to a failed update.
+	 */
+	if (tdx_module_status != TDX_MODULE_INITIALIZED)
+		return -ENXIO;
+
 	return sysfs_emit(buf, "%u.%u.%u\n", v->major_version,
 					     v->minor_version,
 					     v->update_version);
@@ -1377,6 +1384,12 @@ int tdx_module_shutdown(void)
 	return ret;
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
index 3830dee4da91..ed3d74c991f6 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -125,5 +125,6 @@ struct tdmr_info_list {
 int seamldr_prerr(u64 fn, struct tdx_module_args *args);
 
 int tdx_module_shutdown(void);
+void tdx_module_set_error(void);
 
 #endif

---

## [17] Chao Gao — 2025-05-23
*Subject: [RFC PATCH 16/20] x86/virt/seamldr: Do TDX cpu init after updates*

For the newly loaded module, the global initialization and per-CPU
initialization are also needed. Do them on all CPU concurrently.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/virt/vmx/tdx/seamldr.c | 4 ++++
 1 file changed, 4 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index a18df08a5528..c4e1b7540a43 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -245,6 +245,7 @@ enum tdp_state {
 	TDP_START,
 	TDP_SHUTDOWN,
 	TDP_CPU_INSTALL,
+	TDP_CPU_INIT,
 	TDP_DONE,
 };
 
@@ -318,6 +319,9 @@ static int do_seamldr_install_module(void *params)
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

## [18] Chao Gao — 2025-05-23
*Subject: [RFC PATCH 17/20] x86/virt/tdx: Establish contexts for the new module*

TD-Preserving doesn't need to re-configure the global HKID, TDMRs or PAMTs.
The new module can import the handoff data created by the old module to
establish all necessary contexts. The TDH.SYS.UPDATE API is introduced for
the import process

Once the import is done, the module update is complete, and the new module
is ready to handle requests from the VMM and guests.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/virt/vmx/tdx/seamldr.c |  7 +++++++
 arch/x86/virt/vmx/tdx/tdx.c     | 16 ++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h     |  2 ++
 3 files changed, 25 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index c4e1b7540a43..168fd2afd0c9 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -246,6 +246,7 @@ enum tdp_state {
 	TDP_SHUTDOWN,
 	TDP_CPU_INSTALL,
 	TDP_CPU_INIT,
+	TDP_RUN_UPDATE,
 	TDP_DONE,
 };
 
@@ -322,6 +323,12 @@ static int do_seamldr_install_module(void *params)
 			case TDP_CPU_INIT:
 				ret = tdx_cpu_enable();
 				break;
+			case TDP_RUN_UPDATE:
+				if (!primary)
+					break;
+
+				ret = tdx_module_run_update();
+				break;
 			default:
 				break;
 			}
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 331c86eeddcf..5f678c9da4ee 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1390,6 +1390,22 @@ void tdx_module_set_error(void)
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
+	return ret;
+}
+
 static bool is_pamt_page(unsigned long phys)
 {
 	struct tdmr_info_list *tdmr_list = &tdx_tdmr_list;
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index ed3d74c991f6..a05e3c21e7f5 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -49,6 +49,7 @@
 #define TDH_VP_WR			43
 #define TDH_SYS_CONFIG			45
 #define TDH_SYS_SHUTDOWN		52
+#define TDH_SYS_UPDATE		53
 
 /*
  * SEAMCALL leaf:
@@ -126,5 +127,6 @@ int seamldr_prerr(u64 fn, struct tdx_module_args *args);
 
 int tdx_module_shutdown(void);
 void tdx_module_set_error(void);
+int tdx_module_run_update(void);
 
 #endif

---

## [19] Chao Gao — 2025-05-23
*Subject: [RFC PATCH 18/20] x86/virt/tdx: Update tdx_sysinfo and check features post-update*

tdx_sysinfo contains all metadata of the active TDX module, including
versions, supported features, and TDMR/TDCS/TDVPS information. These
elements may change over updates. Blindly refreshing the entire tdx_sysinfo
could disrupt running software, as it may subtly rely on the previous state
unless proven otherwise.

Adopt a conservative approach, like microcode updates, by only refreshing
version information that does not affect functionality, while ignoring
all other changes. This is acceptable as TD-Preserving-capable modules are
required to maintain backward compatibility.

Any updates to metadata beyond versions should be justified and reviewed on
a case-by-case basis.

Note that preallocating a tdx_sys_info buffer before updates is to avoid
having to handle -ENOMEM when updating tdx_sysinfo after a successful
update.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/virt/vmx/tdx/seamldr.c | 13 ++++++++-
 arch/x86/virt/vmx/tdx/tdx.c     | 51 +++++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h     |  1 +
 3 files changed, 64 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 168fd2afd0c9..93385db56281 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -361,9 +361,16 @@ DEFINE_FREE(free_seamldr_params, struct seamldr_params *,
 
 static int seamldr_install_module(const u8 *data, u32 size)
 {
+	struct tdx_sys_info *info __free(kfree) = kzalloc(sizeof(*info),
+							  GFP_KERNEL);
+	int ret;
+
 	if (!td_preserving_ready)
 		return -EOPNOTSUPP;
 
+	if (!info)
+		return -ENOMEM;
+
 	struct seamldr_params *params __free(free_seamldr_params) =
 						init_seamldr_params(data, size);
 	if (IS_ERR(params))
@@ -371,7 +378,11 @@ static int seamldr_install_module(const u8 *data, u32 size)
 
 	atomic_set(&tdp_data.failed, 0);
 	set_state(TDP_START + 1);
-	return stop_machine(do_seamldr_install_module, params, cpu_online_mask);
+	ret = stop_machine(do_seamldr_install_module, params, cpu_online_mask);
+	if (ret)
+		return ret;
+
+	return tdx_module_post_update(info);
 }
 
 static enum fw_upload_err tdx_fw_prepare(struct fw_upload *fwl,
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 5f678c9da4ee..55bdc99818a1 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1406,6 +1406,57 @@ int tdx_module_run_update(void)
 	return ret;
 }
 
+/*
+ * Update tdx_sysinfo and check if any TDX module features changed after
+ * updates
+ */
+static void tdx_module_sysinfo_update_and_check(struct tdx_sys_info *info)
+{
+	struct tdx_sys_info_versions *old, *new;
+
+	guard(mutex)(&tdx_module_lock);
+
+	old = &tdx_sysinfo.versions;
+	new = &info->versions;
+	pr_info("version %d.%d.%d -> %d.%d.%d\n", old->major_version,
+						  old->minor_version,
+						  old->update_version,
+						  new->major_version,
+						  new->minor_version,
+						  new->update_version);
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
+	tdx_sysinfo.versions	= info->versions;
+	tdx_sysinfo.handoff	= info->handoff;
+
+	if (!memcmp(&tdx_sysinfo, info, sizeof(*info)))
+		return;
+
+	pr_info("TDX module features have changed after updates, but might not take effect.\n");
+	pr_info("Please consider a potential BIOS update.\n");
+}
+
+int tdx_module_post_update(struct tdx_sys_info *info)
+{
+	int ret;
+
+	/* Shouldn't fail as the update has succeeded */
+	ret = get_tdx_sys_info(info);
+	if (WARN_ON_ONCE(ret))
+		return ret;
+
+	tdx_module_sysinfo_update_and_check(info);
+	return 0;
+}
+
 static bool is_pamt_page(unsigned long phys)
 {
 	struct tdmr_info_list *tdmr_list = &tdx_tdmr_list;
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index a05e3c21e7f5..57ccceba5406 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -128,5 +128,6 @@ int seamldr_prerr(u64 fn, struct tdx_module_args *args);
 int tdx_module_shutdown(void);
 void tdx_module_set_error(void);
 int tdx_module_run_update(void);
+int tdx_module_post_update(struct tdx_sys_info *info);
 
 #endif

---

## [20] Chao Gao — 2025-05-23
*Subject: [RFC PATCH 19/20] x86/virt/seamldr: Verify availability of slots for TD-Preserving updates*

Before initiating TD-Preserving updates, ensure that the limit on
successive TD-Preserving updates has not been exceeded. This is a cheap
check to prevent update failure.

Refresh SEAMLDR info after each update so that userspace can read the
correct value of remaining updates.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/virt/vmx/tdx/seamldr.c | 5 +++++
 1 file changed, 5 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index 93385db56281..fe8f98701429 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -371,6 +371,9 @@ static int seamldr_install_module(const u8 *data, u32 size)
 	if (!info)
 		return -ENOMEM;
 
+	if (!seamldr_info.num_remaining_updates)
+		return -ENOSPC;
+
 	struct seamldr_params *params __free(free_seamldr_params) =
 						init_seamldr_params(data, size);
 	if (IS_ERR(params))
@@ -382,6 +385,8 @@ static int seamldr_install_module(const u8 *data, u32 size)
 	if (ret)
 		return ret;
 
+	WARN_ON_ONCE(get_seamldr_info());
+
 	return tdx_module_post_update(info);
 }

---

## [21] Chao Gao — 2025-05-23
*Subject: [RFC PATCH 20/20] x86/virt/seamldr: Enable TD-Preserving Updates*

All necessary steps for TD-Preserving updates have been integrated.
Remove the temporary guard to enable TD-Preserving updates.

Signed-off-by: Chao Gao <chao.gao@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
---
 arch/x86/virt/vmx/tdx/seamldr.c | 9 ---------
 1 file changed, 9 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/seamldr.c b/arch/x86/virt/vmx/tdx/seamldr.c
index fe8f98701429..c6e40a7418d3 100644
--- a/arch/x86/virt/vmx/tdx/seamldr.c
+++ b/arch/x86/virt/vmx/tdx/seamldr.c
@@ -350,12 +350,6 @@ static int do_seamldr_install_module(void *params)
 	return ret;
 }
 
-/*
- * Temporary flag to guard TD-Preserving updates. This will be removed once
- * all necessary components for its support are integrated.
- */
-static bool td_preserving_ready;
-
 DEFINE_FREE(free_seamldr_params, struct seamldr_params *,
 	    if (!IS_ERR_OR_NULL(_T)) free_seamldr_params(_T))
 
@@ -365,9 +359,6 @@ static int seamldr_install_module(const u8 *data, u32 size)
 							  GFP_KERNEL);
 	int ret;
 
-	if (!td_preserving_ready)
-		return -EOPNOTSUPP;
-
 	if (!info)
 		return -ENOMEM;

---

## [22] Huang, Kai — 2025-06-02
*Subject: Re: [RFC PATCH 04/20] x86/virt/tdx: Introduce a "tdx" subsystem and
 "tsm" device*

>  static int init_tdx_module(void)
>  {

The error handling of init_module_module() is already very heavy.  Although
tdx_subsys_init() doesn't return any error, I would prefer to putting
tdx_subsys_init() to __tdx_enable() (the caller of init_tdx_module()) so that
init_tdx_module() can just focus on initializing the TDX module.

---

## [23] Huang, Kai — 2025-06-02
*Subject: Re: [RFC PATCH 01/20] x86/virt/tdx: Print SEAMCALL leaf numbers in
 decimal*

On Fri, 2025-05-23 at 02:52 -0700, Gao, Chao wrote:
> Both TDX spec and kernel defines SEAMCALL leaf numbers as decimal. Printing
> them in hex makes no sense. Correct it.

Reviewed-by: Kai Huang <kai.huang@intel.com>

> ---
>  arch/x86/virt/vmx/tdx/tdx.c | 2 +-

---

## [24] Huang, Kai — 2025-06-02
*Subject: Re: [RFC PATCH 05/20] x86/virt/tdx: Export tdx module attributes via
 sysfs*

> 
> Note changes to tdx_global_metadata.{hc} are auto-generated by following

[...]

> +static ssize_t version_show(struct device *dev, struct device_attribute *attr,
> +			    char *buf)

Then for this attribute, I think it is better to name it 'versions' as well?

---

## [25] Nikolay Borisov — 2025-06-03
*Subject: Re: [RFC PATCH 03/20] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On 5/23/25 12:52, Chao Gao wrote:
> P-SEAMLDR is another component alongside the TDX module within the
> protected SEAM range. Software can invoke its functions by executing the

WHy should this be conditional?

---

## [26] Nikolay Borisov — 2025-06-03
*Subject: Re: [RFC PATCH 11/20] x86/virt/seamldr: Abort updates if errors
 occurred midway*

On 5/23/25 12:52, Chao Gao wrote:
> The update process is divided into multiple stages, each of which may
> encounter failures. However, the current state machine for updates proceeds

Should there be some explicit ordering requirement between setting an 
error and reading it in ack_state by a different CPU?


  < snip>

---

## [27] Nikolay Borisov — 2025-06-03
*Subject: Re: [RFC PATCH 12/20] x86/virt/seamldr: Shut down the current TDX
 module*

On 5/23/25 12:52, Chao Gao wrote:
> TD-Preserving updates request shutting down the existing TDX module.
> During this shutdown, the module generates hand-off data, which captures

nit: the !! is not needed here, as the check is clearly boolean.

 > +>   	do {
>   		/* Chill out and ensure we re-read tdp_data. */
>   		cpu_relax();

nit: That first !ret is redundant since it's always true.

<snip>

---

## [28] Huang, Kai — 2025-06-04
*Subject: Re: [RFC PATCH 02/20] x86/virt/tdx: Prepare to support P-SEAMLDR
 SEAMCALLs*

> diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
> index 49267c865f18..b586329dd87d 100644

Given there will be a dedicated seamldr.c, I don't quite like having
seamldr_prerr() in "tdx.h" and tdx.c.

Now for all SEAMCALLs used by KVM, we have a dedicated wrapper implemented
in tdx.c and exported for KVM to use.  I think we can move seamcall*() out
of <asm/tdx.h> to TDX host local since no other kernel code except the TDX
host core is supposed to use seamcall*().

This also cleans up <asm/tdx.h> a little bit, which in general makes code
cleaner IMHO.

E.g., how about we do below patch, and then you can do changes to support
P-SEAMLDR on top of it?

---

From 1cba17cf832d87a6ea34cc4db1798902e54d7577 Mon Sep 17 00:00:00 2001
From: Kai Huang <kai.huang@intel.com>
Date: Tue, 3 Jun 2025 12:55:53 +1200
Subject: [PATCH] x86/virt/tdx: Move low level SEAMCALL helpers out of
 <asm/tdx.h>

Now for all the SEAMCALL leaf functions that used by KVM, each has a
dedicated wrapper function implemented in TDX host core tdx.c and
exported for KVM to use.  In the future, if KVM or any other kernel
component needs more SEAMCALL, the TDX host core tdx.c should provide a
wrapper.  In other words, other than TDX host core code, seamcall*() are
not supposed to be used by other kernel components thus don't need to be
in <asm/tdx.h>.

Move seamcall*() and related code out of <asm/tdx.h> and put them to TDX
aost local.  This also cleans up <asm/tdx.h> a little bit, which is
getting bigger and bigger.

Don't just put seamcall*() to tdx.c since it is already very heavy, but
put seamcall*() to a new local "seamcall.h" which is more readable.
Also, currently tdx.c has seamcall_prerr*() helpers which additionally
prints error message when calling seamcall*() fails.  Move them and the
related code to "seamcall.h" too.  In such way all low level SEAMCALL
helpers and related code are in a dedicated place, which is much more
readable.

Signed-off-by: Kai Huang <kai.huang@intel.com>
---
 arch/x86/include/asm/tdx.h       | 24 -----------
 arch/x86/virt/vmx/tdx/seamcall.h | 71 ++++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.c      | 46 +--------------------
 3 files changed, 72 insertions(+), 69 deletions(-)
 create mode 100644 arch/x86/virt/vmx/tdx/seamcall.h

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 8b19294600c4..a45323118b7e 100644
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
-static inline u64 sc_retry(sc_func_t func, u64 fn,
-                          struct tdx_module_args *args)
-{
-       int retry = RDRAND_RETRY_LOOPS;
-       u64 ret;
-
-       do {
-               ret = func(fn, args);
-       } while (ret == TDX_RND_NO_ENTROPY && --retry);
-
-       return ret;
-}
-
-#define seamcall(_fn, _args)           sc_retry(__seamcall, (_fn), (_args))
-#define seamcall_ret(_fn, _args)       sc_retry(__seamcall_ret, (_fn), (_args))
-#define seamcall_saved_ret(_fn, _args) sc_retry(__seamcall_saved_ret, (_fn), (_args))
 int tdx_cpu_enable(void);
 int tdx_enable(void);
 const char *tdx_dump_mce_info(struct mce *m);
diff --git a/arch/x86/virt/vmx/tdx/seamcall.h b/arch/x86/virt/vmx/tdx/seamcall.h
new file mode 100644
index 000000000000..54922f7bda3a
--- /dev/null
+++ b/arch/x86/virt/vmx/tdx/seamcall.h
@@ -0,0 +1,71 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+/* Copyright (C) 2025 Intel Corporation */
+#include <asm/tdx.h>
+#include <asm/archrandom.h>
+
+u64 __seamcall(u64 fn, struct tdx_module_args *args);
+u64 __seamcall_ret(u64 fn, struct tdx_module_args *args);
+u64 __seamcall_saved_ret(u64 fn, struct tdx_module_args *args);
+
+typedef u64 (*sc_func_t)(u64 fn, struct tdx_module_args *args);
+
+static inline u64 sc_retry(sc_func_t func, u64 fn,
+                          struct tdx_module_args *args)
+{
+       int retry = RDRAND_RETRY_LOOPS;
+       u64 ret;
+
+       do {
+               ret = func(fn, args);
+       } while (ret == TDX_RND_NO_ENTROPY && --retry); 
+ 
+       return ret;
+}
+
+#define seamcall(_fn, _args)           sc_retry(__seamcall, (_fn), (_args))
+#define seamcall_ret(_fn, _args)       sc_retry(__seamcall_ret, (_fn), (_args))
+#define seamcall_saved_ret(_fn, _args) sc_retry(__seamcall_saved_ret, (_fn), (_args))
+
+typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);
+
+static inline void seamcall_err(u64 fn, u64 err, struct tdx_module_args *args)
+{
+       pr_err("SEAMCALL (0x%016llx) failed: 0x%016llx\n", fn, err);
+}
+
+static inline void seamcall_err_ret(u64 fn, u64 err,
+                                   struct tdx_module_args *args)
+{
+       seamcall_err(fn, err, args);
+       pr_err("RCX 0x%016llx RDX 0x%016llx R08 0x%016llx\n",
+                       args->rcx, args->rdx, args->r8);
+       pr_err("R09 0x%016llx R10 0x%016llx R11 0x%016llx\n",
+                       args->r9, args->r10, args->r11);
+}
+
+static inline int sc_retry_prerr(sc_func_t func, sc_err_func_t err_func,
+                                u64 fn, struct tdx_module_args *args)
+{
+       u64 sret = sc_retry(func, fn, args);
+
+       if (sret == TDX_SUCCESS)
+               return 0;
+
+       if (sret == TDX_SEAMCALL_VMFAILINVALID)
+               return -ENODEV;
+
+       if (sret == TDX_SEAMCALL_GP)
+               return -EOPNOTSUPP;
+
+       if (sret == TDX_SEAMCALL_UD)
+               return -EACCES;
+
+       err_func(fn, sret, args);
+       return -EIO;
+}
+
+#define seamcall_prerr(__fn, __args)                                           \
+       sc_retry_prerr(__seamcall, seamcall_err, (__fn), (__args))
+
+#define seamcall_prerr_ret(__fn, __args)                                       \
+       sc_retry_prerr(__seamcall_ret, seamcall_err_ret, (__fn), (__args))
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 2457d13c3f9e..b963e2d75713 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -38,6 +38,7 @@
 #include <asm/cpu_device_id.h>
 #include <asm/processor.h>
 #include <asm/mce.h>
+#include "seamcall.h"
 #include "tdx.h"

 static u32 tdx_global_keyid __ro_after_init;
@@ -57,51 +58,6 @@ static DEFINE_MUTEX(tdx_module_lock);
 static LIST_HEAD(tdx_memlist);

 static struct tdx_sys_info tdx_sysinfo;
-
-typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);
-
-static inline void seamcall_err(u64 fn, u64 err, struct tdx_module_args *args)
-{
-       pr_err("SEAMCALL (0x%016llx) failed: 0x%016llx\n", fn, err);
-}
-
-static inline void seamcall_err_ret(u64 fn, u64 err,
-                                   struct tdx_module_args *args)
-{
-       seamcall_err(fn, err, args);
-       pr_err("RCX 0x%016llx RDX 0x%016llx R08 0x%016llx\n",
-                       args->rcx, args->rdx, args->r8);
-       pr_err("R09 0x%016llx R10 0x%016llx R11 0x%016llx\n",
-                       args->r9, args->r10, args->r11);
-}
-
-static inline int sc_retry_prerr(sc_func_t func, sc_err_func_t err_func,
-                                u64 fn, struct tdx_module_args *args)
-{
-       u64 sret = sc_retry(func, fn, args);
-
-       if (sret == TDX_SUCCESS)
-               return 0;
-
-       if (sret == TDX_SEAMCALL_VMFAILINVALID)
-               return -ENODEV;
-
-       if (sret == TDX_SEAMCALL_GP)
-               return -EOPNOTSUPP;
-
-       if (sret == TDX_SEAMCALL_UD)
-               return -EACCES;
-
-       err_func(fn, sret, args);
-       return -EIO;
-}
-
-#define seamcall_prerr(__fn, __args)                                           \
-       sc_retry_prerr(__seamcall, seamcall_err, (__fn), (__args))
-
-#define seamcall_prerr_ret(__fn, __args)                                       \
-       sc_retry_prerr(__seamcall_ret, seamcall_err_ret, (__fn), (__args))
-
 /*
  * Do the module global initialization once and return its result.
  * It can be done on any cpu.  It's always called with interrupts

---

## [29] Chao Gao — 2025-06-04
*Subject: Re: [RFC PATCH 02/20] x86/virt/tdx: Prepare to support P-SEAMLDR
 SEAMCALLs*

>Given there will be a dedicated seamldr.c, I don't quite like having
>seamldr_prerr() in "tdx.h" and tdx.c.

looks good to me. I'd like to incorporate this patch into my series if
Kirill and Dave have no objections to this cleanup. I assume
seamldr_prerr() can be added to the new seamcall.h

Thanks for this suggestion.

>diff --git a/arch/x86/virt/vmx/tdx/seamcall.h b/arch/x86/virt/vmx/tdx/seamcall.h
>new file mode 100644

If seamcall.h is intended to provide low-level helpers, including
<asm/tdx.h>, which is meant to offer high-level APIs for other components
such as KVM, seems a bit odd to me. But I suppose we can live with this.

---

## [30] Huang, Kai — 2025-06-05
*Subject: Re: [RFC PATCH 02/20] x86/virt/tdx: Prepare to support P-SEAMLDR
 SEAMCALLs*

On Wed, 2025-06-04 at 21:14 +0800, Gao, Chao wrote:
> > Given there will be a dedicated seamldr.c, I don't quite like having
> > seamldr_prerr() in "tdx.h" and tdx.c.

Seems we both think this is a good cleanup.  My TDX host kexec series also
conflicts with this so I think I can send this patch out first to see how
things will go.  At the meantime, yeah please carry it in your series.

> 
> > diff --git a/arch/x86/virt/vmx/tdx/seamcall.h b/arch/x86/virt/vmx/tdx/seamcall.h

Kinda agree, I can remove it and do:

struct tdx_module_args;

explicitly.

But we also need to include <asm/archrandom.h> etc, so I think I will just
leave it as-is until other people coming out to complain.

---

## [31] Chao Gao — 2025-06-05
*Subject: Re: [RFC PATCH 04/20] x86/virt/tdx: Introduce a "tdx" subsystem and
 "tsm" device*

On Tue, Jun 03, 2025 at 07:44:08AM +0800, Huang, Kai wrote:
>
>>  static int init_tdx_module(void)

Sounds good. Will do.

btw, I think we can use guard() to simplify the error-handling a bit, e.g.,

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index a755cdef69d2..0b93064b9e0f 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1218,11 +1218,11 @@ static int init_tdx_module(void)
	 * holding mem_hotplug_lock read-lock as the memory hotplug code
	 * path reads the @tdx_memlist to reject any new memory.
	 */
-	get_online_mems();
+	guard(online_mems)();
 
	ret = build_tdx_memlist(&tdx_memlist);
	if (ret)
-		goto out_put_tdxmem;
+		return ret;
 
	/* Allocate enough space for constructing TDMRs */
	ret = alloc_tdmr_list(&tdx_tdmr_list, &tdx_sysinfo.tdmr);
@@ -1253,13 +1253,7 @@ static int init_tdx_module(void)
 
	tdx_subsys_init();
 
-out_put_tdxmem:
-	/*
-	 * @tdx_memlist is written here and read at memory hotplug time.
-	 * Lock out memory hotplug code while building it.
-	 */
-	put_online_mems();
-	return ret;
+	return 0;
 
 err_reset_pamts:
	/*
@@ -1283,7 +1277,7 @@ static int init_tdx_module(void)
	free_tdmr_list(&tdx_tdmr_list);
 err_free_tdxmem:
	free_tdx_memlist(&tdx_memlist);
-	goto out_put_tdxmem;
+	return ret;
 }
 
 static int __tdx_enable(void)
diff --git a/include/linux/memory_hotplug.h b/include/linux/memory_hotplug.h
index eaac5ae8c05c..a0c0535a9122 100644
--- a/include/linux/memory_hotplug.h
+++ b/include/linux/memory_hotplug.h
@@ -2,6 +2,7 @@
 #ifndef __LINUX_MEMORY_HOTPLUG_H
 #define __LINUX_MEMORY_HOTPLUG_H
 
+#include <linux/cleanup.h>
 #include <linux/mmzone.h>
 #include <linux/spinlock.h>
 #include <linux/notifier.h>
@@ -172,6 +173,7 @@ int add_pages(int nid, unsigned long start_pfn, unsigned long nr_pages,
 
 void get_online_mems(void);
 void put_online_mems(void);
+DEFINE_LOCK_GUARD_0(online_mems, get_online_mems(), put_online_mems())
 
 void mem_hotplug_begin(void);
 void mem_hotplug_done(void);

---

## [32] Chao Gao — 2025-06-09
*Subject: Re: [RFC PATCH 12/20] x86/virt/seamldr: Shut down the current TDX
 module*

>> @@ -281,8 +282,12 @@ static void ack_state(void)
>>   static int do_seamldr_install_module(void *params)

Thanks. I will remove it.

<snip>
>> +static int get_tdx_sys_info_handoff(struct tdx_sys_info_handoff *sysinfo_handoff)
>> +{

Yes, this code is generated by a script [*] and other existing functions in
this file have the same issue. I will try to improve the script to remove the
redundant "!ret".

---

## [33] Chao Gao — 2025-06-09
*Subject: Re: [RFC PATCH 11/20] x86/virt/seamldr: Abort updates if errors
 occurred midway*

>>   static void ack_state(void)
>>   {

Only the last CPU that calls ack_state() will change the global state, either
advancing to the next state or setting it to TDP_DONE on error. so, we only
need to ensure that the last CPU can see the error. This is guaranteed because
the error is set before the call to ack_state().

+			if (ret)
+				atomic_inc(&tdp_data.failed);
			ack_state();

---

## [34] Chao Gao — 2025-06-09
*Subject: Re: [RFC PATCH 03/20] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

>> +config INTEL_TDX_MODULE_UPDATE
>> +	bool "Intel TDX module runtime update"

Good question. I don't have a strong reason, but here are my considerations:

1. Runtime updates aren't strictly necessary for TDX functionalities. Users can
   update the TDX module via BIOS updates and reboot if service downtime isn't
   a concern.

2. Selecting TDX module updates requires selecting FW_UPLOAD and FW_LOADER,
   which I think will significantly increase the kernel size if FW_UPLOAD/LOADER
   won't otherwise be selected.

It may or may not be wise to assume that most TDX users will enable TDX module
updates. so, I'm taking a conservative approach by making it optional. The
resulting code isn't that complex, as CONFIG_INTEL_TDX_MODULE_UPDATE
appears in only two places:

1. in the Makefile:

  obj-y += seamcall.o tdx.o
  obj-$(CONFIG_INTEL_TDX_MODULE_UPDATE) += seamldr.o

2. in the seamldr.h:

  #ifdef CONFIG_INTEL_TDX_MODULE_UPDATE
  extern struct attribute_group seamldr_group;
  #define SEAMLDR_GROUP (&seamldr_group)
  int get_seamldr_info(void);
  void seamldr_init(struct device *dev);
  #else
  #define SEAMLDR_GROUP NULL
  static inline int get_seamldr_info(void) { return 0; }
  static inline void seamldr_init(struct device *dev) { }
  #endif

That said, I'm open to keeping or dropping the Kconfig option.

---

## [35] Nikolay Borisov — 2025-06-09
*Subject: Re: [RFC PATCH 03/20] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On 6/9/25 10:53, Chao Gao wrote:
>>> +config INTEL_TDX_MODULE_UPDATE
>>> +	bool "Intel TDX module runtime update"

If size is a consideration (but given the size of machines that are 
likely to run CoCo guests I'd say it's not) then don't make this a 
user-configurable option but rather make it depend on TDX being selected 
and FW_UPLOAD/FW_LOADER being selected.

I'd rather keep the user visible options to a minimum, especially 
something such as this update functionality.

But in any case I'd like to hear other opinions as well.


> 
> It may or may not be wise to assume that most TDX users will enable TDX module

---

## [36] Chao Gao — 2025-06-10
*Subject: Re: [RFC PATCH 03/20] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On Mon, Jun 09, 2025 at 11:02:49AM +0300, Nikolay Borisov wrote:
>
>

But in almost all existing cases, 'select FW_UPLOAD/LOADER' is used rather than
'depends on FW_UPLOAD/LOADER'. You can verify this by running

	find . -name 'Kconfig' -exec grep -E 'FW_UPLOAD|FW_LOADER$' {} +

>
>I'd rather keep the user visible options to a minimum, especially something

Yeah, let's see what others think.

<snip>

---

## [37] Chao Gao — 2025-06-10
*Subject: Re: [RFC PATCH 05/20] x86/virt/tdx: Export tdx module attributes via
 sysfs*

On Tue, Jun 03, 2025 at 07:49:17AM +0800, Huang, Kai wrote:
>
>> 

Using 'versions' for sysfs might be confusing, as it could imply multiple TDX
modules. It makes more sense to me that each module has __a version__ in the
x.y.z format.

And the convention for sysfs file names is to use 'version'. E.g.,

# find . -type f -exec grep 'version_show' {} + |wc -l
185
# find . -type f -exec grep 'versions_show' {} + |wc -l
0

Concatenating major_version/minor_version is kinda common inside the kernel,
but 'versions' is not typically used as a sysfs name.

---

## [38] Nikolay Borisov — 2025-06-10
*Subject: Re: [RFC PATCH 03/20] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On 6/10/25 04:03, Chao Gao wrote:
> On Mon, Jun 09, 2025 at 11:02:49AM +0300, Nikolay Borisov wrote:
>>


Then just have TDX select FW_UPLOAD/FW_LOADER and be done with it. 
Still, let's hear other opinions but in this case I'd say size 
considerations aren't major so let's make it simpler for the user.

> 
>>

---

## [39] Dave Hansen — 2025-06-10
*Subject: Re: [RFC PATCH 03/20] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On 6/9/25 23:52, Nikolay Borisov wrote:
> Then just have TDX select FW_UPLOAD/FW_LOADER and be done with it.
> Still, let's hear other opinions but in this case I'd say size

In general, those of us at hardware companies like to mint lots of
Kconfig options. Folks like Nikolay at the distros have to deal with
fallout from the piles of Kconfig options.

I tend to be pretty deferential to the distro guys on matters like this.

I haven't heard anything even remotely compelling that we need a
user-visible Kconfig option for this.

---

## [40] Huang, Kai — 2025-06-11
*Subject: Re: [RFC PATCH 05/20] x86/virt/tdx: Export tdx module attributes via
 sysfs*

On Tue, 2025-06-10 at 09:37 +0800, Chao Gao wrote:
> On Tue, Jun 03, 2025 at 07:49:17AM +0800, Huang, Kai wrote:
> > 

Sure.

But then should we just use 'version' in the names of the structure and the
variable generated via the script?

It doesn't make a lot sense to me to have this inconsistency.

---

## [41] Chao Gao — 2025-06-11
*Subject: Re: [RFC PATCH 05/20] x86/virt/tdx: Export tdx module attributes via
 sysfs*

On Wed, Jun 11, 2025 at 10:09:35AM +0800, Huang, Kai wrote:
>> Using 'versions' for sysfs might be confusing, as it could imply multiple TDX
>> modules. It makes more sense to me that each module has __a version__ in the

Agreed. I will fix the struct name.

---

## [42] Sagi Shahar — 2025-06-11
*Subject: Re: [RFC PATCH 00/20] TD-Preserving updates*

On Fri, May 23, 2025 at 4:53 AM Chao Gao <chao.gao@intel.com> wrote:
>
> Hi Reviewers,

Tested-by: Sagi Shahar <sagis@google.com>

I was able to update the module while several VMs were running on the
machine using a modified version of the tdx selftests. Measuring the
update time shows less than 10ms for update regardless of the number
of VMs running.

---

## [43] Sagi Shahar — 2025-06-16
*Subject: Re: [RFC PATCH 08/20] x86/virt/seamldr: Implement FW_UPLOAD sysfs ABI
 for TD-Preserving Updates*

On Fri, May 23, 2025 at 4:55 AM Chao Gao <chao.gao@intel.com> wrote:
>
> Implement a fw_upload interface to coordinate TD-Preserving updates. The

dev_root definition here causes compilation error:

arch/x86/virt/vmx/tdx/tdx.c:1181:3: error: cannot jump from this goto
statement to its label
                goto err_bus;
                ^
arch/x86/virt/vmx/tdx/tdx.c:1184:17: note: jump bypasses
initialization of variable with __attribute__((cleanup))
        struct device *dev_root __free(put_device) =
bus_get_dev_root(&tdx_subsys);

> +       if (dev_root)
> +               seamldr_init(dev_root);

---

## [44] Chao Gao — 2025-06-17
*Subject: Re: [RFC PATCH 08/20] x86/virt/seamldr: Implement FW_UPLOAD sysfs
 ABI for TD-Preserving Updates*

On Mon, Jun 16, 2025 at 05:55:50PM -0500, Sagi Shahar wrote:
>> diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
>> index aa6a23d46494..22ffc15b4299 100644

Thank you for reporting this. The goto label is unnecessary, and I'll remove it
from patch 4 (which adds this goto).

I'm curious about which compiler you are using because I don't encounter this
error with "gcc version 11.5.0 20240719 (Red Hat 11.5.0-5) (GCC)".

>
>> +       if (dev_root)

---

## [45] Chao Gao — 2025-07-11
*Subject: Re: [RFC PATCH 00/20] TD-Preserving updates*

On Fri, May 23, 2025 at 02:52:23AM -0700, Chao Gao wrote:
>Hi Reviewers,
>

Gentle ping!

There are three open issues: one regarding stop_machine() and two related to
interactions with KVM.

Sean and Paul, do you have any preferences or insights on these matters?

---

## [46] Sean Christopherson — 2025-07-11
*Subject: Re: [RFC PATCH 03/20] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

On Fri, May 23, 2025, Chao Gao wrote:
> +static __maybe_unused int seamldr_call(u64 fn, struct tdx_module_args *args)
> +{

I'd rather this use human-friendly language as opposed to the SDM's pedantic
terminology, e.g. just "current VMCS".

> +	 * Save/restore current-VMCS pointer across P-SEAMLDR SEAMCALLs so
> +	 * that VMX instructions won't fail due to an invalid current-VMCS.

I would rather we establish a rule that KVM is allowed to do VMREAD/VMWRITE in
IRQ context, i.e. don't single out SMP function calls.

> +	 * invalid current-VMCS.
> +	 */


Heh, don't copy paste the crappy indentation, that was a result of Linus' tree-wide
changes from 4356e9f841f7 ("work around gcc bugs with 'asm goto' with outputs"),
i.e. not intentional.

Regarding question #3 from the cover letter:

  3. Two helpers, cpu_vmcs_load() and cpu_vmcs_store(), are added in patch 3
     to save and restore the current VMCS. KVM has a variant of cpu_vmcs_load(),
     i.e., vmcs_load(). Extracting KVM's version would cause a lot of code
     churn, and I don't think that can be justified for reducing ~16 LoC
     duplication. Please let me know if you disagree.

I'm fine with the SEAMLDR code having its own code, because I agree it's not worth
extracting KVM's macro maze just to get at VMPTRLD.  But I'm not fine with creating
a new, inferior framework.  So if we elect to leave KVM alone for the time being,
I would prefer to simply open code VMPTRST and VMPTRLD in seamldr.c, e.g.

static inline int seamldr_call(u64 fn, struct tdx_module_args *args)
{
	u64 vmcs;
	int ret;

	if (!is_seamldr_call(fn))
		return -EINVAL;

	/*
	 * SEAMRET from P-SEAMLDR invalidates the current VMCS.  Save/restore
	 * the VMCS across P-SEAMLDR SEAMCALLs to avoid clobbering KVM state.
	 * Disable interrupts as KVM is allowed to do VMREAD/VMWRITE in IRQ
	 * context (but not NMI context).
	 */
	guard(irqsave)();

	asm goto("1: vmptrst %0\n\t"
		 _ASM_EXTABLE(1b, %l[error])
		 : "=m" (&vmcs) : "cc" : error);

	ret = seamldr_prerr(fn, args);

	/*
	 * Restore the current VMCS pointer.  VMPTSTR "returns" all ones if the
	 * current VMCS is invalid.
	 */
	if (vmcs != -1ULL) {
		asm goto("1: vmptrld %0\n\t"
			 "jna %l[error]\n\t"
			 _ASM_EXTABLE(1b, %l[error])
			 : : "m" (&vmcs) : "cc" : error);
	}

	return ret;

error:
	WARN_ONCE(1, "Failed to save/restore the current VMCS");
	return -EIO;
}

---

## [47] Sean Christopherson — 2025-07-11
*Subject: Re: [RFC PATCH 00/20] TD-Preserving updates*

On Fri, Jul 11, 2025, Chao Gao wrote:
> >2. P-SEAMLDR seamcalls (specificially SEAMRET from P-SEAMLDR) clear current
> >   VMCS pointers, which may disrupt KVM. To prevent VMX instructions in IRQ

NMIs shouldn't be a problem.  KVM does access the current VMCS in NMI context
(to do VMREAD(GUEST_RIP) in response to a perf NMI), but only when KVM knows the
NMI occurred in KVM's run loop.  So in effect, only in KVM_RUN context, which I
gotta image is mutually exclusive with tdx_fw_write().

It'd be nice if we could make the P-SEAMLDR calls completely NMI safe, but
practically speaking, if KVM (or any other hypervisor) is playing with the VMCS
in arbitrary NMI handlers, then we've probably got bigger issues.

---

## [48] Chao Gao — 2025-07-14
*Subject: Re: [RFC PATCH 03/20] x86/virt/seamldr: Introduce a wrapper for
 P-SEAMLDR SEAMCALLs*

>Regarding question #3 from the cover letter:
>

Agreed. And the code below makes perfect sense to me, so I will incorporate it
into my next version.

Thanks for your prompt feedback.

>
>static inline int seamldr_call(u64 fn, struct tdx_module_args *args)

---

## [49] Chao Gao — 2025-07-14
*Subject: Re: [RFC PATCH 00/20] TD-Preserving updates*

On Fri, Jul 11, 2025 at 07:06:21AM -0700, Sean Christopherson wrote:
>On Fri, Jul 11, 2025, Chao Gao wrote:
>> >2. P-SEAMLDR seamcalls (specificially SEAMRET from P-SEAMLDR) clear current

Yes. I also think the guest NMI handler is the only case where VMREAD/VMWRITE is
done in NMI context.

>NMI occurred in KVM's run loop.  So in effect, only in KVM_RUN context, which I
>gotta image is mutually exclusive with tdx_fw_write().

Just a heads-up: P-SEAMLDR may gain other functions and be called from other
code paths, but they won't interfere with the guest NMI handler or KVM_RUN
context.

>
>It'd be nice if we could make the P-SEAMLDR calls completely NMI safe, but

Agreed.

It's a little late to change the CPU behavior about SEAMRET, as several CPU
generations have already been shipped. Implementing new behavior would require
a new feature bit, which could complicate the host kernel code because the
kernel would need to perform save/restore VMCS conditionally based on this new
feature. So, let's pursue a hardware change unless it becomes a practical issue
for hypervisors.

---

## [50] Paul E. McKenney — 2025-07-14
*Subject: Re: [RFC PATCH 00/20] TD-Preserving updates*

On Fri, Jul 11, 2025 at 04:04:48PM +0800, Chao Gao wrote:
> On Fri, May 23, 2025 at 02:52:23AM -0700, Chao Gao wrote:
> >Hi Reviewers,

Please note that multi_cpu_stop() is used by a number of functions,
so it is a good example of common code.  But you are within your rights
to create your own function to pass to stop_machine(), and quite a
few call sites do just that.  Most of them expect this function to be
executed on only one CPU, but these run on multiple CPUs:

o	__apply_alternatives_multi_stop(), which has CPU 0 do the
	work and the rest wati on it.

o	cpu_enable_non_boot_scope_capabilities(), which works on
	a per-CPU basis.

o	do_join(), which is similar to your do_seamldr_install_module().
	Somewhat similar, anyway.

o	__ftrace_modify_code(), of which there are several, some of
	which have some vague resemblance to your code.

o	cache_rendezvous_handler(), which works on a per-CPU basis.

o	panic_stop_irqoff_fn(), which is a simple barrier-wait, with
	the last CPU to arrive doing the work.

I strongly recommend looking at these functions.  They might
suggest an improved way to do what you are trying to accomplish with
do_seamldr_install_module().

> >2. P-SEAMLDR seamcalls (specificially SEAMRET from P-SEAMLDR) clear current
> >   VMCS pointers, which may disrupt KVM. To prevent VMX instructions in IRQ

I do not believe that I was CCed on the original.  Just in case you
were wondering why I did not respond.  ;-)

> There are three open issues: one regarding stop_machine() and two related to
> interactions with KVM.

Again, you are within your rights to create a new function and pass
it to stop_machine().  But it seems quite likely that there is a much
simpler way to get your job done.

Either way, please add a header comment stating what your function
is trying to do, which appears to be to wait for all CPUs to enter
do_seamldr_install_module() and then just leave?  Sort of like
multi_cpu_stop(), except leaving interrupts enabled and not executing a
"msdata->fn(msdata->data);", correct?

If so, something like panic_stop_irqoff_fn() might be a simpler model,
perhaps with the touch_nmi_watchdog() and rcu_momentary_eqs() added.

Oh, and one bug:  You must have interrupts disabled when you call
rcu_momentary_eqs().  Please fix this.

							Thanx, Paul

---

## [51] Chao Gao — 2025-07-16
*Subject: Re: [RFC PATCH 00/20] TD-Preserving updates*

On Mon, Jul 14, 2025 at 05:21:47PM -0700, Paul E. McKenney wrote:
>On Fri, Jul 11, 2025 at 04:04:48PM +0800, Chao Gao wrote:
>> On Fri, May 23, 2025 at 02:52:23AM -0700, Chao Gao wrote:

Hi Paul,

Thanks for your feedback.

Let me clarify what do_seamldr_install_module() does. Patch 10 just adds the
skeleton (sorry for only directing you to patch 10). More functions are added by
subsequent patches. Specifically:

 * TDP_SHUTDOWN (Patch 12)
	Shut down the running TDX module on any CPU while other CPUs must be idle
 * TDP_CPU_INSTALL (Patch 14)
	Load a new TDX module on all CPUs serially
 * TDP_CPU_INIT (patch 16)
	Initialize the new module on all CPUs in parallel
 * TDP_RUN_UPDATE (Patch 17)
	Import metadata from the old module on any CPU while other CPUs must be idle

And there are two requirements:
1. These steps must be executed in a lock-stepped manner, meaning all CPUs must
   complete step X before any CPU proceeds to step X+1.
2. If any CPU encounters an error, all CPUs should bail out rather than proceed
   to the next step.

>
>> >2. P-SEAMLDR seamcalls (specificially SEAMRET from P-SEAMLDR) clear current

My bad :(. I forgot to CC you when posting the series.

Btw, it seems that stop_machine.c isn't listed under any entry in MAINTAINERS.
I found your name by checking who submitted pull requests related to
stop_machine.c to Linus.

>
>> There are three open issues: one regarding stop_machine() and two related to

Sure. Will do.

>which appears to be to wait for all CPUs to enter
>do_seamldr_install_module() and then just leave?

Emm, do_seamldr_install_module() does more than just a simple barrier-wait at
the end of the series.

>Sort of like
>multi_cpu_stop(), except leaving interrupts enabled and not executing a

As said above, lockstep is a key requirement. panic_stop_irqoff_fn()-like
simple model cannot meet our needs here.

>
>Oh, and one bug:  You must have interrupts disabled when you call

Actually, interrupts are disabled in multi_cpu_stop() before it calls
msdata->fn (i.e., do_seamldr_install_module())

In this context, there are two state machines involved. The MULTI_STOP_RUN
state, part of the outer state machine, includes an inner state machine with
the following stages:
 * TDP_START
 * TDP_SHUTDOWN
 * TDP_CPU_INSTALL
 * TDP_CPU_INIT
 * TDP_RUN_UPDATE
 * TDP_DONE

I am concerned about the code duplication between do_seamldr_install_module()
and multi_cpu_stop(). But, I don't see a good way to eliminate the duplication
without adding more complexity. It seems you can also live with the duplication
if do_seamldr_install_module() truly requires another state machine, right?

---

## [52] Xu Yilun — 2025-07-29
*Subject: Re: [RFC PATCH 07/20] x86/virt/tdx: Expose SEAMLDR information via
 sysfs*

> +static const struct attribute_group *tdx_subsys_groups[] = {
> +	SEAMLDR_GROUP,

As mentioned, TDX Connect also uses this virtual TSM device. And I tend
to extend it to TDX guest, also make the guest TSM management run on
the virtual device which represents the TDG calls and TDG_VP_VM calls.

So I'm considering extract the common part of tdx_subsys_init() out of
TDX host and into a separate file, e.g.

---

+source "drivers/virt/coco/tdx-tsm/Kconfig"
+
 config TSM
        bool
diff --git a/drivers/virt/coco/Makefile b/drivers/virt/coco/Makefile
index c0c3733be165..a54d3cb5b4e9 100644
--- a/drivers/virt/coco/Makefile
+++ b/drivers/virt/coco/Makefile
@@ -10,3 +10,4 @@ obj-$(CONFIG_INTEL_TDX_GUEST) += tdx-guest/
 obj-$(CONFIG_ARM_CCA_GUEST)    += arm-cca-guest/
 obj-$(CONFIG_TSM)              += tsm-core.o
 obj-$(CONFIG_TSM_GUEST)                += guest/
+obj-y                          += tdx-tsm/
diff --git a/drivers/virt/coco/tdx-tsm/Kconfig b/drivers/virt/coco/tdx-tsm/Kconfig
new file mode 100644
index 000000000000..768175f8bb2c
--- /dev/null
+++ b/drivers/virt/coco/tdx-tsm/Kconfig
@@ -0,0 +1,2 @@
+config TDX_TSM_BUS
+       bool
diff --git a/drivers/virt/coco/tdx-tsm/Makefile b/drivers/virt/coco/tdx-tsm/Makefile
new file mode 100644
index 000000000000..09f0ac08988a
--- /dev/null
+++ b/drivers/virt/coco/tdx-tsm/Makefile
@@ -0,0 +1 @@
+obj-$(CONFIG_TDX_TSM_BUS) += tdx-tsm-bus.o

---

And put the tdx_subsys_init() in tdx-tsm-bus.c. We need to move host
specific initializations out of tdx_subsys_init(), e.g. seamldr_group &
seamldr fw upload.

Thanks,
Yilun

---

## [53] Chao Gao — 2025-07-29
*Subject: Re: [RFC PATCH 07/20] x86/virt/tdx: Expose SEAMLDR information via
 sysfs*

>As mentioned, TDX Connect also uses this virtual TSM device. And I tend
>to extend it to TDX guest, also make the guest TSM management run on

Sounds good. I assume you'll update the TDX TSM framework patch* directly.
Please share the updated patch once it's ready, and I'll take care of all the
seamldr stuff.

[*]: https://lore.kernel.org/kvm/20250523095322.88774-5-chao.gao@intel.com/

---

## [54] dan.j.williams@intel.com — 2025-07-31
*Subject: Re: [RFC PATCH 04/20] x86/virt/tdx: Introduce a "tdx" subsystem and
 "tsm" device*

Chao Gao wrote:
> On Tue, Jun 03, 2025 at 07:44:08AM +0800, Huang, Kai wrote:
> >

In cleanup.h I wrote:

    Lastly, given that the benefit of cleanup helpers is removal of
    "goto", and that the "goto" statement can jump between scopes, the
    expectation is that usage of "goto" and cleanup helpers is never
    mixed in the same function. I.e. for a given routine, convert all
    resources that need a "goto" cleanup to scope-based cleanup, or
    convert none of them.

...because it leaves a minefield for the next person to keep a mental
map of the cleanup scopes vs goto.

In this case all of the cleanup functions take a pointer argument, so it
is a straightforward conversion to track those individual cleanup steps
in local pointer variables with something like below (compile tested
only).

So either convert the entire function, or none of the function to scope
based cleanup.

-- 8< --
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index c7a9a087ccaf..029db95982f7 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -28,6 +28,7 @@
 #include <linux/log2.h>
 #include <linux/acpi.h>
 #include <linux/suspend.h>
+#include <linux/cleanup.h>
 #include <linux/idr.h>
 #include <asm/page.h>
 #include <asm/special_insns.h>
@@ -225,7 +226,7 @@ static void free_tdx_memlist(struct list_head *tmb_list)
  * ranges off in a secondary structure because memblock is modified
  * in memory hotplug while TDX memory regions are fixed.
  */
-static int build_tdx_memlist(struct list_head *tmb_list)
+static struct list_head *build_tdx_memlist(struct list_head *tmb_list)
 {
 	unsigned long start_pfn, end_pfn;
 	int i, nid, ret;
@@ -251,10 +252,10 @@ static int build_tdx_memlist(struct list_head *tmb_list)
 			goto err;
 	}
 
-	return 0;
+	return tmb_list;
 err:
 	free_tdx_memlist(tmb_list);
-	return ret;
+	return ERR_PTR(ret);
 }
 
 static int read_sys_metadata_field(u64 field_id, u64 *data)
@@ -306,8 +307,9 @@ static int tdmr_size_single(u16 max_reserved_per_tdmr)
 	return ALIGN(tdmr_sz, TDMR_INFO_ALIGNMENT);
 }
 
-static int alloc_tdmr_list(struct tdmr_info_list *tdmr_list,
-			   struct tdx_sys_info_tdmr *sysinfo_tdmr)
+static struct tdmr_info_list *
+alloc_tdmr_list(struct tdmr_info_list *tdmr_list,
+		struct tdx_sys_info_tdmr *sysinfo_tdmr)
 {
 	size_t tdmr_sz, tdmr_array_sz;
 	void *tdmr_array;
@@ -323,7 +325,7 @@ static int alloc_tdmr_list(struct tdmr_info_list *tdmr_list,
 	tdmr_array = alloc_pages_exact(tdmr_array_sz,
 			GFP_KERNEL | __GFP_ZERO);
 	if (!tdmr_array)
-		return -ENOMEM;
+		return ERR_PTR(-ENOMEM);
 
 	tdmr_list->tdmrs = tdmr_array;
 
@@ -335,7 +337,7 @@ static int alloc_tdmr_list(struct tdmr_info_list *tdmr_list,
 	tdmr_list->max_tdmrs = sysinfo_tdmr->max_tdmrs;
 	tdmr_list->nr_consumed_tdmrs = 0;
 
-	return 0;
+	return tdmr_list;
 }
 
 static void free_tdmr_list(struct tdmr_info_list *tdmr_list)
@@ -888,9 +890,9 @@ static int tdmrs_populate_rsvd_areas_all(struct tdmr_info_list *tdmr_list,
  * to cover all TDX memory regions in @tmb_list based on the TDX module
  * TDMR global information in @sysinfo_tdmr.
  */
-static int construct_tdmrs(struct list_head *tmb_list,
-			   struct tdmr_info_list *tdmr_list,
-			   struct tdx_sys_info_tdmr *sysinfo_tdmr)
+static struct tdmr_info_list *
+construct_tdmrs(struct list_head *tmb_list, struct tdmr_info_list *tdmr_list,
+		struct tdx_sys_info_tdmr *sysinfo_tdmr)
 {
 	u16 pamt_entry_size[TDX_PS_NR] = {
 		sysinfo_tdmr->pamt_4k_entry_size,
@@ -901,11 +903,11 @@ static int construct_tdmrs(struct list_head *tmb_list,
 
 	ret = fill_out_tdmrs(tmb_list, tdmr_list);
 	if (ret)
-		return ret;
+		return ERR_PTR(ret);
 
 	ret = tdmrs_set_up_pamt_all(tdmr_list, tmb_list, pamt_entry_size);
 	if (ret)
-		return ret;
+		return ERR_PTR(ret);
 
 	ret = tdmrs_populate_rsvd_areas_all(tdmr_list, tmb_list,
 			sysinfo_tdmr->max_reserved_per_tdmr);
@@ -919,10 +921,11 @@ static int construct_tdmrs(struct list_head *tmb_list,
 	 */
 	smp_wmb();
 
-	return ret;
+	return tdmr_list;
 }
 
-static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
+static struct tdmr_info_list *
+config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
 {
 	struct tdx_module_args args = {};
 	u64 *tdmr_pa_array;
@@ -941,7 +944,7 @@ static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
 
 	tdmr_pa_array = kzalloc(array_sz, GFP_KERNEL);
 	if (!tdmr_pa_array)
-		return -ENOMEM;
+		return ERR_PTR(-ENOMEM);
 
 	for (i = 0; i < tdmr_list->nr_consumed_tdmrs; i++)
 		tdmr_pa_array[i] = __pa(tdmr_entry(tdmr_list, i));
@@ -954,7 +957,10 @@ static int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
 	/* Free the array as it is not required anymore. */
 	kfree(tdmr_pa_array);
 
-	return ret;
+	if (ret)
+		return ERR_PTR(ret);
+
+	return tdmr_list;
 }
 
 static int do_global_key_config(void *unused)
@@ -1065,6 +1071,34 @@ static int init_tdmrs(struct tdmr_info_list *tdmr_list)
 	return 0;
 }
 
+DEFINE_FREE(free_tdx_memlist, struct list_head *,
+	    if (!IS_ERR_OR_NULL(_T)) free_tdx_memlist(_T))
+DEFINE_FREE(free_tdmr_list, struct tdmr_info_list *,
+	    if (!IS_ERR_OR_NULL(_T)) free_tdmr_list(_T))
+DEFINE_FREE(free_pamt_all, struct tdmr_info_list *,
+	    if (!IS_ERR_OR_NULL(_T)) tdmrs_free_pamt_all(_T))
+DEFINE_FREE(
+	reset_pamt_all, struct tdmr_info_list *,
+	if (!IS_ERR_OR_NULL(_T)) {
+		/*
+		 * Part of PAMTs may already have been initialized by the
+		 * TDX module.  Flush cache before returning PAMTs back
+		 * to the kernel.
+		 */
+
+		wbinvd_on_all_cpus();
+		/*
+		 * According to the TDX hardware spec, if the platform
+		 * doesn't have the "partial write machine check"
+		 * erratum, any kernel read/write will never cause #MC
+		 * in kernel space, thus it's OK to not convert PAMTs
+		 * back to normal.  But do the conversion anyway here
+		 * as suggested by the TDX spec.
+		 */
+		tdmrs_reset_pamt_all(_T);
+	}
+)
+
 static int init_tdx_module(void)
 {
 	int ret;
@@ -1088,70 +1122,49 @@ static int init_tdx_module(void)
 	 * holding mem_hotplug_lock read-lock as the memory hotplug code
 	 * path reads the @tdx_memlist to reject any new memory.
 	 */
-	get_online_mems();
+	guard(online_mems)();
 
-	ret = build_tdx_memlist(&tdx_memlist);
-	if (ret)
-		goto out_put_tdxmem;
+	struct list_head *memlist __free(free_tdx_memlist) =
+		build_tdx_memlist(&tdx_memlist);
+	if (IS_ERR(memlist))
+		return PTR_ERR(memlist);
 
 	/* Allocate enough space for constructing TDMRs */
-	ret = alloc_tdmr_list(&tdx_tdmr_list, &tdx_sysinfo.tdmr);
-	if (ret)
-		goto err_free_tdxmem;
+	struct tdmr_info_list *tdmrlist __free(free_tdmr_list) =
+		alloc_tdmr_list(&tdx_tdmr_list, &tdx_sysinfo.tdmr);
+	if (IS_ERR(tdmrlist))
+		return PTR_ERR(tdmrlist);
 
 	/* Cover all TDX-usable memory regions in TDMRs */
-	ret = construct_tdmrs(&tdx_memlist, &tdx_tdmr_list, &tdx_sysinfo.tdmr);
-	if (ret)
-		goto err_free_tdmrs;
+	struct tdmr_info_list *tdmrpamt __free(free_pamt_all) = construct_tdmrs(
+		&tdx_memlist, &tdx_tdmr_list, &tdx_sysinfo.tdmr);
+	if (IS_ERR(tdmrpamt))
+		return PTR_ERR(tdmrpamt);
 
 	/* Pass the TDMRs and the global KeyID to the TDX module */
-	ret = config_tdx_module(&tdx_tdmr_list, tdx_global_keyid);
-	if (ret)
-		goto err_free_pamts;
+	struct tdmr_info_list *tdmrconfig __free(reset_pamt_all) =
+		config_tdx_module(&tdx_tdmr_list, tdx_global_keyid);
+	if (IS_ERR(tdmrconfig))
+		return PTR_ERR(tdmrconfig);
 
 	/* Config the key of global KeyID on all packages */
 	ret = config_global_keyid();
 	if (ret)
-		goto err_reset_pamts;
+		return ret;
 
 	/* Initialize TDMRs to complete the TDX module initialization */
 	ret = init_tdmrs(&tdx_tdmr_list);
 	if (ret)
-		goto err_reset_pamts;
+		return ret;
 
-	pr_info("%lu KB allocated for PAMT\n", tdmrs_count_pamt_kb(&tdx_tdmr_list));
+	retain_and_null_ptr(tdmrconfig);
+	retain_and_null_ptr(tdmrpamt);
+	retain_and_null_ptr(tdmrlist);
+	retain_and_null_ptr(memlist);
 
-out_put_tdxmem:
-	/*
-	 * @tdx_memlist is written here and read at memory hotplug time.
-	 * Lock out memory hotplug code while building it.
-	 */
-	put_online_mems();
-	return ret;
+	pr_info("%lu KB allocated for PAMT\n", tdmrs_count_pamt_kb(&tdx_tdmr_list));
 
-err_reset_pamts:
-	/*
-	 * Part of PAMTs may already have been initialized by the
-	 * TDX module.  Flush cache before returning PAMTs back
-	 * to the kernel.
-	 */
-	wbinvd_on_all_cpus();
-	/*
-	 * According to the TDX hardware spec, if the platform
-	 * doesn't have the "partial write machine check"
-	 * erratum, any kernel read/write will never cause #MC
-	 * in kernel space, thus it's OK to not convert PAMTs
-	 * back to normal.  But do the conversion anyway here
-	 * as suggested by the TDX spec.
-	 */
-	tdmrs_reset_pamt_all(&tdx_tdmr_list);
-err_free_pamts:
-	tdmrs_free_pamt_all(&tdx_tdmr_list);
-err_free_tdmrs:
-	free_tdmr_list(&tdx_tdmr_list);
-err_free_tdxmem:
-	free_tdx_memlist(&tdx_memlist);
-	goto out_put_tdxmem;
+	return 0;
 }
 
 static int __tdx_enable(void)
diff --git a/include/linux/memory_hotplug.h b/include/linux/memory_hotplug.h
index eaac5ae8c05c..6d3f997c7fe8 100644
--- a/include/linux/memory_hotplug.h
+++ b/include/linux/memory_hotplug.h
@@ -6,6 +6,7 @@
 #include <linux/spinlock.h>
 #include <linux/notifier.h>
 #include <linux/bug.h>
+#include <linux/cleanup.h>
 
 struct page;
 struct zone;
@@ -239,6 +240,8 @@ static inline void pgdat_kswapd_unlock(pg_data_t *pgdat) {}
 static inline void pgdat_kswapd_lock_init(pg_data_t *pgdat) {}
 #endif /* ! CONFIG_MEMORY_HOTPLUG */
 
+DEFINE_LOCK_GUARD_0(online_mems, get_online_mems(), put_online_mems())
+
 /*
  * Keep this declaration outside CONFIG_MEMORY_HOTPLUG as some
  * platforms might override and use arch_get_mappable_range()

---

## [55] dan.j.williams@intel.com — 2025-07-31
*Subject: Re: [RFC PATCH 07/20] x86/virt/tdx: Expose SEAMLDR information via
 sysfs*

Xu Yilun wrote:
> > +static const struct attribute_group *tdx_subsys_groups[] = {
> > +	SEAMLDR_GROUP,

Just name it bus.c.

> ---
> 

Just to be clear on the plan here as I think this TD Preserving set
should land before we start upstreamming any TDX Connect bits.

- Create drivers/virt/coco/tdx-tsm/bus.c for registering the tdx_subsys.
  The tdx_subsys has sysfs attributes like "version" (host and guest
  need this, but have different calls to get at the information) and
  "firmware" (only host needs that). So the common code will take sysfs
  groups passed as a parameter.

- The "tdx_tsm" device which is unused in this patch set can be
  registered on the "tdx" bus to move feature support like TDX Connect
  into a typical driver model.

So the change for this set is create a bus.c that is host/guest
agnostic, drop the tdx_tsm device and leave that to the TDX Connect
patches to add back. 

The TDX Connect pathes will register the tdx_tsm device near where the
bus is registered for the host and guest cases.

Concerns?

In the meantime, until this set lands in tip we can work out the
organization in tsm.git#staging.

---

## [56] Xu Yilun — 2025-08-01
*Subject: Re: [RFC PATCH 07/20] x86/virt/tdx: Expose SEAMLDR information via
 sysfs*

On Thu, Jul 31, 2025 at 02:01:21PM -0700, dan.j.williams@intel.com wrote:
> Xu Yilun wrote:
> > > +static const struct attribute_group *tdx_subsys_groups[] = {

I'm about to make the change but I see there is already tdx-guest misc
virtual device in Guest OS:

  What:		/sys/devices/virtual/misc/tdx_guest/xxxx

And if we add another tdx_subsys, we have:

  What:		/sys/devices/virtual/tdx/xxxx

Do we really want 2 virtual devices? What's their relationship? I can't
figure out.

So I'm considering reuse the misc/tdx_guest device as a tdx root device
in guest. And that removes the need to have a common tdx tsm bus.

What do you think?

> 
> > ---

It is used in this patch, Chao creates tdx module 'version' attr on this
device. But I assume you have different opinion: tdx_subsys represents
the whole tdx_module and should have the 'version', and tdx_tsm is a
sub device dedicate for TDX Connect, is it?

Thanks,
Yilun

>   registered on the "tdx" bus to move feature support like TDX Connect
>   into a typical driver model.

---

## [57] dan.j.williams@intel.com — 2025-08-01
*Subject: Re: [RFC PATCH 07/20] x86/virt/tdx: Expose SEAMLDR information via
 sysfs*

Xu Yilun wrote:
[..]
> > > diff --git a/drivers/virt/coco/tdx-tsm/Makefile b/drivers/virt/coco/tdx-tsm/Makefile
> > > new file mode 100644

True, do not need tdx_subsys on the guest side. The tdx_guest driver
is sufficient. This was the approach taken with the RTMR enabling, just
append the sysfs attributes to the existing guest device.

> > > And put the tdx_subsys_init() in tdx-tsm-bus.c. We need to move host
> > > specific initializations out of tdx_subsys_init(), e.g. seamldr_group &

The main reason for a tdx_tsm device in addition to the subsys is to
allow for deferred attachment.

Now, that said, the faux_device infrastructure has arrived since this
all started and *could* replace tdx_subsys. The only concern is whether
the tdx_tsm driver ever needs to do probe deferral to wait for IOMMU or
PCI initialization to happen first.

If probe deferral is needed that requires a bus, if probe can always be
synchronous with TDX module init then faux_device could work.

---

## [58] Xu Yilun — 2025-08-04
*Subject: Re: [RFC PATCH 07/20] x86/virt/tdx: Expose SEAMLDR information via
 sysfs*

> > > - Create drivers/virt/coco/tdx-tsm/bus.c for registering the tdx_subsys.
> > >   The tdx_subsys has sysfs attributes like "version" (host and guest

I've found another reason, to dynamic control tdx tsm's lifecycle.
tdx_tsm driver uses seamcalls so its functionality relies on tdx module
initialization & vmxon. The former is a one way path but vmxon can be
dynamic off by KVM. vmxoff is fatal to tdx_tsm driver especially on some
can-not-fail destroy path.

So my idea is to remove tdx_tsm device (thus disables tdx_tsm driver) on
vmxoff.

  KVM                TDX core            TDX TSM driver
  -----------------------------------------------------
  tdx_disable()
                     tdx_tsm dev del
                                         driver.remove()
  vmxoff()

An alternative is to move vmxon/off management out of KVM, that requires
a lot of complex work IMHO, Chao & I both prefer not to touch it.


That said, we still want to "deal with bus/driver binding logic" so faux
is not a good fit.

> 
> Now, that said, the faux_device infrastructure has arrived since this

The tdx_tsm driver needs to wait for IOMMU/PCI initialization...

> 
> If probe deferral is needed that requires a bus, if probe can always be

... but doesn't see need for TDX Module early init now. Again TDX Module
init requires vmxon, so it can't be earlier than KVM init, nor the
IOMMU/PCI init. So probe synchronous with TDX module init should be OK.

But considering the tdx tsm's lifecycle concern, I still don't prefer
faux.

Thanks,
Yilun

---

## [59] dan.j.williams@intel.com — 2025-08-04
*Subject: Re: [RFC PATCH 07/20] x86/virt/tdx: Expose SEAMLDR information via
 sysfs*

Xu Yilun wrote:
> > > > - Create drivers/virt/coco/tdx-tsm/bus.c for registering the tdx_subsys.
> > > >   The tdx_subsys has sysfs attributes like "version" (host and guest

It is fine to require that vmxon/off management remain within KVM, and
tie the lifetime of the device to the lifetime of the kvm_intel module*.

However, I think it is too violent to add/remove the device on async
vmxon/vmxoff.

Are there more sources of async vmxoff besides CPU offline, system
suspend, or system shutdown?

The suspend and shutdown cases can be handled with suspend and shutdown
callbacks in the tdx_tsm driver. Those will be called before KVM's
vmxoff. For CPU offline, is it safe to assume that the driver will not
be invoked from those CPUs?

Are there other sources of vmxoff?

> That said, we still want to "deal with bus/driver binding logic" so faux
> is not a good fit.

Faux device gives you a bus / driver-binding flow, it just expects that
the driver is always ready to bind immediately upon device create.

> > Now, that said, the faux_device infrastructure has arrived since this
> > all started and *could* replace tdx_subsys. The only concern is whether

Intel IOMMU can not be modular and arrives at rootfs_initcall(). PCI
arrives at subsys_initcall(). The earliest that KVM arrives is
late_initcall() when it is built-in.

Hmm, so faux_device could work, all dependencies are resolved before the
device is created.

> > If probe deferral is needed that requires a bus, if probe can always be
> > synchronous with TDX module init then faux_device could work.

If there are other sources of async vmxoff that are not handled by
'suspend' and 'shutdown' handlers in the tdx_tsm driver, then perhaps a
flag that gets toggled to fail requests. Otherwise it feels like the
tdx_tsm device should only end life at vt_exit() / tdx_cleanup().

> Thanks,
> Yilun

* It would be unfortunate if userspace needed to manually probe for TDX
  Connect when KVM is not built-in. We might add a simple module that
  requests kvm_intel in that case:

static const struct x86_cpu_id tdx_connect_autoprobe_ids[] = {
        X86_MATCH_FEATURE(X86_FEATURE_TDX_HOST_PLATFORM, NULL),
        {}
};
MODULE_DEVICE_TABLE(x86cpu, tdx_connect_autoprobe_ids);

...to allow for userspace to have dependencies on TDX Connect services
arriving automatically without needing to manually demand load
kvm_intel. That module would just immediately exit if TDX Connect
capability is not found.

---

## [60] Sean Christopherson — 2025-08-04
*Subject: Re: [RFC PATCH 07/20] x86/virt/tdx: Expose SEAMLDR information via sysfs*

On Mon, Aug 04, 2025, dan.j.williams@intel.com wrote:
> Xu Yilun wrote:
> > So my idea is to remove tdx_tsm device (thus disables tdx_tsm driver) on

Eh, it's complex, but not _that_ complex.

> It is fine to require that vmxon/off management remain within KVM, and
> tie the lifetime of the device to the lifetime of the kvm_intel module*.

Nah, let's do this right.  Speaking from experience; horrible, make-your-eyes-bleed
experience; playing games with kvm-intel.ko to try to get and keep CPUs post-VMXON
will end in tears.

And it's not just TDX-feature-of-the-day that needs VMXON to be handled outside
of KVM, I'd also like to do so to allow out-of-tree hypervisors to do the "right
thing"[*].  Not because I care deeply about out-of-tree hypervisors, but because
the lack of proper infrastructure for utilizing virtualization hardware irks me.

The basic gist is to extract system-wide resources out of KVM and into a separate
module, so that e.g. tdx_tsm or whatever can take a dependency on _that_ module
and elevate refcounts as needed.  All things considered, there aren't so many
system-wide resources that it's an insurmountable task.

I can provide some rough patches to kickstart things.  It'll probably take me a
few weeks to extract them from an old internal branch, and I can't promise they'll
compile.  But they should be good enough to serve as an RFC.

https://lore.kernel.org/all/ZwQjUSOle6sWARsr@google.com

> * It would be unfortunate if userspace needed to manually probe for TDX
>   Connect when KVM is not built-in. We might add a simple module that

Oh hell no :-)

We have internal code that "requests" vendor module, and it might just be my least
favorite thing.  Juggling the locks and module lifetimes is just /shudder.

---

## [61] dan.j.williams@intel.com — 2025-08-04
*Subject: Re: [RFC PATCH 07/20] x86/virt/tdx: Expose SEAMLDR information via
 sysfs*

Sean Christopherson wrote:
> On Mon, Aug 04, 2025, dan.j.williams@intel.com wrote:
> > Xu Yilun wrote:

Sounds reasonable to me.

Not clear on how it impacts tdx_tsm implementation. The lifetime of this
tdx_tsm device can still be bound by tdx_enable() / tdx_cleanup(). The
refactor removes the need for the autoprobe hack below. It may also
preclude async vmxoff cases by pinning? Or does pinning still not solve
the reasons for bouncing vmx on suspend/shutdown?

> > * It would be unfortunate if userspace needed to manually probe for TDX
> >   Connect when KVM is not built-in. We might add a simple module that

Oh, indeed, if there were locks and lifetime entanglements with
kvm_intel involved then it would indeed be a mess. Effectively this was
just looking for somewhere to drop a MODULE_SOFTDEP() since there is no
good way to autoload "TEE I/O" for TDX.

However, that indeed gets dropped / simpler if all of TDX's system-wide
bits can just autoprobe and light up features without needing to load
all of kvm.

---

## [62] Sean Christopherson — 2025-08-05
*Subject: Re: [RFC PATCH 07/20] x86/virt/tdx: Expose SEAMLDR information via sysfs*

On Mon, Aug 04, 2025, dan.j.williams@intel.com wrote:
> Sean Christopherson wrote:
> > On Mon, Aug 04, 2025, dan.j.williams@intel.com wrote:

What exactly is the concern with suspend/shutdown?

Suspend should be a non-issue, as userspace tasks need to be frozen before the
kernel fires off the suspend notifiers.  Ditto for a normal shutdown.

Forced shutdown will be asynchronous with respect to running vCPUs, but all bets
are off on a forced shutdown.  Ditto for disabling VMX via NMI shootdown on a
crash.

---

## [63] Xu Yilun — 2025-08-06
*Subject: Re: [RFC PATCH 07/20] x86/virt/tdx: Expose SEAMLDR information via
 sysfs*

On Mon, Aug 04, 2025 at 09:02:51PM -0700, dan.j.williams@intel.com wrote:
> Sean Christopherson wrote:
> > On Mon, Aug 04, 2025, dan.j.williams@intel.com wrote:

I assume with VMXON outside of KVM, tdx tsm driver could actively call
tdx_bringup(), which includes VMXON, tdx_enable() and cpuhp handling.
I.e, tdx_tsm device lifetime won't have to be bound to any other
component, it could keep living until tdx_tsm module ends.

> refactor removes the need for the autoprobe hack below. It may also
> preclude async vmxoff cases by pinning? Or does pinning still not solve

not by pinning, by cpuhp handling async vmxoff won't affect seamcall
execution.

> the reasons for bouncing vmx on suspend/shutdown?

Thanks,
Yilun

---

## [64] dan.j.williams@intel.com — 2025-08-06
*Subject: Re: [RFC PATCH 07/20] x86/virt/tdx: Expose SEAMLDR information via
 sysfs*

Sean Christopherson wrote:
[..]
> > Sounds reasonable to me.
> > 

I was confused by Yilun's diagram that suggested vmxoff scenarios while
kvm_intel is still loaded.

> Suspend should be a non-issue, as userspace tasks need to be frozen before the
> kernel fires off the suspend notifiers.  Ditto for a normal shutdown.

Yes, tdx_tsm can stay registered over those events.

> Forced shutdown will be asynchronous with respect to running vCPUs, but all bets
> are off on a forced shutdown.  Ditto for disabling VMX via NMI shootdown on a

Ok, to repeat back the implications: async vmxoff is not something that
needs to gracefully shutdown the tdx_tsm device or system-wide TDX
services. Those are already going to error out in the force shutdown
case.

tdx_tsm is a module for system-wide tdx_tsm services. Its lifetime
starts at tdx_enable() and ends at tdx_cleanup(). Until a refactor
completes tdx_enable() is called from the kvm_intel init path. Post
refactor, tdx_enable() is in a system-wide TDX services module that
depends on a shared module, not kvm_intel, to manage vmxon. kvm_intel is
a peer client of this shared vmx module.

While the TDX TEE I/O (device security) RFC is in flight the
implementation will go through a phase of userspace needing to
demand-load kvm_intel. The final implementation for mainline will have
broken tdx_tsm's dependency on kvm_intel.

---
