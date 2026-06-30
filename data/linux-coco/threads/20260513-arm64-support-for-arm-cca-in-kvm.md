---
title: 'arm64: Support for Arm CCA in KVM'
date: 2026-05-13
last_reply: 2026-06-28
message_count: 156
participants: ['Steven Price', 'Aneesh Kumar K.V', 'Gavin Shan', 'Suzuki K Poulose', 'Marc Zyngier', 'Wei-Lin Chang', 'Lorenzo Pieralisi', 'Dan Williams (nvidia)']
---

## [1] Steven Price — 2026-05-13

This series adds support for running protected VMs using KVM under the
Arm Confidential Compute Architecture (CCA).

This is rebased on v7.1-rc1, but still targets RMM v2.0-bet1[1].

The major updates from v13 remain but have been more fully implemented:
the RMM uses the host's page size, range based RMI APIs mean we don't
have to break everything down to base page sizes, the GIC state is
passed via system registers, and the uAPI has been simplified.

The main changes since v13 are:

 * The RMI definitions and wrappers have been fully updated for RMM
   v2.0-bet1. In particular the temporary RMM v1.0 SMC compatibility
   patch has been dropped.

 * The PSCI completion ioctl has been removed. RMM v2.0-bet1 still
   requires the host to provide the target REC for PSCI calls which
   name another vCPU, but KVM now performs the RMI PSCI completion
   automatically before entering the REC again. Userspace no longer
   needs to issue KVM_ARM_VCPU_RMI_PSCI_COMPLETE. A future spec should
   remove the need for the host to provide the MPIDR mapping.

 * The generic RMI init, RMM configuration, GPT setup,
   delegate/undelegate helpers and SRO infrastructure have moved out of
   KVM into arch/arm64/kernel/rmi.c. RMI is expected to be used by
   features outside KVM, so this code should be available even when KVM
   is not built.

 * RMI_GRANULE_TRACKING_GET has been updated to work on a range, this
   allows it to work when the region is not aligned to the tracking
   size. Solves the problem reported by Mathieu[2].

 * SRO support has been moved earlier in the series and improved. It
   provides a cleaner way for the host to provide the RMM with the extra
   memory it requires. However support is still incomplete where the
   TF-RMM code does not yet implement it. This is noted by FIXMEs in the
   code.

 * The ARM VM type encoding has been reworked to coexist with the
   upstream pKVM KVM_VM_TYPE_ARM_PROTECTED bit.

 * The private-memory documentation now notes that arm64 uses
   KVM_CAP_MEMORY_ATTRIBUTES.

 * PMU support is dropped for now. It will be added later in a separate
   series. Similarly for selecting the hash algorithm and RPV.

There are also the usual rebase updates and smaller fixes, including
changes to the RMM v2.0-bet1 range APIs, removal of REC auxiliary
granule handling, fixes to the address range descriptor encoding, and
cleanups around realm stage-2 teardown.

Stateful RMI Operations
-----------------------

The RMM v2.0 spec introduces Stateful RMI Operations (SROs), which allow
the RMM to complete an operation over several SMC calls while requesting
or returning memory to the host. This allows interrupts to be handled in
the middle of an operation and lets the RMM dynamically allocate memory
for internal tracking purposes. For example, RMI_REC_CREATE no longer
needs auxiliary granules to be provided up front, and can instead
request memory during the operation.

This series includes the generic SRO infrastructure in
arch/arm64/kernel/rmi.c and uses it for REC create/destroy. The other
cases are not yet used by TF-RMM and a future revision will be needed to
finish those paths in Linux.

This series is based on v7.1-rc1. It is also available as a git
repository:

https://gitlab.arm.com/linux-arm/linux-cca cca-host/v14

Work in progress changes for kvmtool are available from the git
repository below:

https://gitlab.arm.com/linux-arm/kvmtool-cca cca/v12

The TF-RMM has not yet merged the RMM v2.0 support, so you will need to
use a branch with RMM v2.0-bet1 support. At the time of writing the
following branch is being used:

https://git.trustedfirmware.org/TF-RMM/tf-rmm.git topics/rmm-v2.0-poc_2
(tested on commit 3340667a291a)

There is a kvm-unit-test branch which has been updated to support the
attestation used in RMMv2.0 available here:

https://gitlab.arm.com/linux-arm/kvm-unit-tests-cca cca/v4

[1] https://developer.arm.com/documentation/den0137/2-0bet1/
[2] https://lore.kernel.org/all/acrj-cKphy4hJsEG@p14s/

Jean-Philippe Brucker (6):
  arm64: RMI: Propagate number of breakpoints and watchpoints to
    userspace
  arm64: RMI: Set breakpoint parameters through SET_ONE_REG
  arm64: RMI: Propagate max SVE vector length from RMM
  arm64: RMI: Configure max SVE vector length for a Realm
  arm64: RMI: Provide register list for unfinalized RMI RECs
  arm64: RMI: Provide accurate register list

Joey Gouly (2):
  arm64: RMI: allow userspace to inject aborts
  arm64: RMI: support RSI_HOST_CALL

Steven Price (33):
  kvm: arm64: Avoid including linux/kvm_host.h in kvm_pgtable.h
  arm64: RME: Handle Granule Protection Faults (GPFs)
  arm64: RMI: Add SMC definitions for calling the RMM
  arm64: RMI: Add wrappers for RMI calls
  arm64: RMI: Check for RMI support at init
  arm64: RMI: Configure the RMM with the host's page size
  arm64: RMI: Ensure that the RMM has GPT entries for memory
  arm64: RMI: Provide functions to delegate/undelegate ranges of memory
  arm64: RMI: Add support for SRO
  arm64: RMI: Check for RMI support at KVM init
  arm64: RMI: Check for LPA2 support
  arm64: RMI: Define the user ABI
  arm64: RMI: Basic infrastructure for creating a realm.
  KVM: arm64: Allow passing machine type in KVM creation
  arm64: RMI: RTT tear down
  arm64: RMI: Activate realm on first VCPU run
  arm64: RMI: Allocate/free RECs to match vCPUs
  arm64: RMI: Support for the VGIC in realms
  KVM: arm64: Support timers in realm RECs
  arm64: RMI: Handle realm enter/exit
  arm64: RMI: Handle RMI_EXIT_RIPAS_CHANGE
  KVM: arm64: Handle realm MMIO emulation
  KVM: arm64: Expose support for private memory
  arm64: RMI: Allow populating initial contents
  arm64: RMI: Set RIPAS of initial memslots
  arm64: RMI: Create the realm descriptor
  arm64: RMI: Runtime faulting of memory
  KVM: arm64: Handle realm VCPU load
  KVM: arm64: Validate register access for a Realm VM
  KVM: arm64: Handle Realm PSCI requests
  KVM: arm64: WARN on injected undef exceptions
  arm64: RMI: Prevent Device mappings for Realms
  arm64: RMI: Enable realms to be created

Suzuki K Poulose (3):
  kvm: arm64: Include kvm_emulate.h in kvm/arm_psci.h
  kvm: arm64: Don't expose unsupported capabilities for realm guests
  arm64: RMI: Allow checking SVE on VM instance

 Documentation/virt/kvm/api.rst       |   62 +-
 arch/arm64/include/asm/kvm_emulate.h |   37 +
 arch/arm64/include/asm/kvm_host.h    |   13 +-
 arch/arm64/include/asm/kvm_pgtable.h |    5 +-
 arch/arm64/include/asm/kvm_pkvm.h    |    2 +-
 arch/arm64/include/asm/kvm_rmi.h     |  127 +++
 arch/arm64/include/asm/rmi_cmds.h    |  680 +++++++++++++
 arch/arm64/include/asm/rmi_smc.h     |  448 ++++++++
 arch/arm64/include/asm/virt.h        |    1 +
 arch/arm64/kernel/Makefile           |    2 +-
 arch/arm64/kernel/cpufeature.c       |    1 +
 arch/arm64/kernel/rmi.c              |  605 +++++++++++
 arch/arm64/kvm/Kconfig               |    2 +
 arch/arm64/kvm/Makefile              |    2 +-
 arch/arm64/kvm/arch_timer.c          |   28 +-
 arch/arm64/kvm/arm.c                 |  140 ++-
 arch/arm64/kvm/guest.c               |   93 +-
 arch/arm64/kvm/hyp/pgtable.c         |    1 +
 arch/arm64/kvm/hypercalls.c          |    4 +-
 arch/arm64/kvm/inject_fault.c        |    5 +-
 arch/arm64/kvm/mmio.c                |   16 +-
 arch/arm64/kvm/mmu.c                 |  197 +++-
 arch/arm64/kvm/psci.c                |   15 +-
 arch/arm64/kvm/reset.c               |   13 +-
 arch/arm64/kvm/rmi-exit.c            |  215 ++++
 arch/arm64/kvm/rmi.c                 | 1401 ++++++++++++++++++++++++++
 arch/arm64/kvm/sys_regs.c            |   47 +-
 arch/arm64/kvm/vgic/vgic-init.c      |    2 +-
 arch/arm64/mm/fault.c                |   28 +-
 include/kvm/arm_arch_timer.h         |    2 +
 include/kvm/arm_psci.h               |    2 +
 include/uapi/linux/kvm.h             |   20 +-
 32 files changed, 4122 insertions(+), 94 deletions(-)
 create mode 100644 arch/arm64/include/asm/kvm_rmi.h
 create mode 100644 arch/arm64/include/asm/rmi_cmds.h
 create mode 100644 arch/arm64/include/asm/rmi_smc.h
 create mode 100644 arch/arm64/kernel/rmi.c
 create mode 100644 arch/arm64/kvm/rmi-exit.c
 create mode 100644 arch/arm64/kvm/rmi.c

---

## [2] Steven Price — 2026-05-13
*Subject: [PATCH v14 01/44] kvm: arm64: Include kvm_emulate.h in kvm/arm_psci.h*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

Fix a potential build error (like below, when asm/kvm_emulate.h gets
included after the kvm/arm_psci.h) by including the missing header file
in kvm/arm_psci.h:

./include/kvm/arm_psci.h: In function ‘kvm_psci_version’:
./include/kvm/arm_psci.h:29:13: error: implicit declaration of function
   ‘vcpu_has_feature’; did you mean ‘cpu_have_feature’? [-Werror=implicit-function-declaration]
   29 |         if (vcpu_has_feature(vcpu, KVM_ARM_VCPU_PSCI_0_2)) {
	         |             ^~~~~~~~~~~~~~~~
			       |             cpu_have_feature

Reviewed-by: Gavin Shan <gshan@redhat.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 include/kvm/arm_psci.h | 2 ++
 1 file changed, 2 insertions(+)

diff --git a/include/kvm/arm_psci.h b/include/kvm/arm_psci.h
index cbaec804eb83..38dab7add79b 100644
--- a/include/kvm/arm_psci.h
+++ b/include/kvm/arm_psci.h
@@ -10,6 +10,8 @@
 #include <linux/kvm_host.h>
 #include <uapi/linux/psci.h>
 
+#include <asm/kvm_emulate.h>
+
 #define KVM_ARM_PSCI_0_1	PSCI_VERSION(0, 1)
 #define KVM_ARM_PSCI_0_2	PSCI_VERSION(0, 2)
 #define KVM_ARM_PSCI_1_0	PSCI_VERSION(1, 0)

---

## [3] Steven Price — 2026-05-13
*Subject: [PATCH v14 02/44] kvm: arm64: Avoid including linux/kvm_host.h in kvm_pgtable.h*

To avoid future include cycles, drop the linux/kvm_host.h include in
kvm_pgtable.h and include two _types.h headers for the types that are
actually used. Additionally provide a forward declaration for struct
kvm_s2_mmu as it's only used as a pointer in this file.

Both pgtable.c and kvm_pkvm.h relied on the indirect inclusion of
kvm_host.h, so make that explicit.

Signed-off-by: Steven Price <steven.price@arm.com>
---
New patch in v13
---
 arch/arm64/include/asm/kvm_pgtable.h | 5 ++++-
 arch/arm64/include/asm/kvm_pkvm.h    | 2 +-
 arch/arm64/kvm/hyp/pgtable.c         | 1 +
 3 files changed, 6 insertions(+), 2 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_pgtable.h b/arch/arm64/include/asm/kvm_pgtable.h
index 41a8687938eb..e4770ce2ccf6 100644
--- a/arch/arm64/include/asm/kvm_pgtable.h
+++ b/arch/arm64/include/asm/kvm_pgtable.h
@@ -8,9 +8,12 @@
 #define __ARM64_KVM_PGTABLE_H__
 
 #include <linux/bits.h>
-#include <linux/kvm_host.h>
+#include <linux/kvm_types.h>
+#include <linux/rbtree_types.h>
 #include <linux/types.h>
 
+struct kvm_s2_mmu;
+
 #define KVM_PGTABLE_FIRST_LEVEL		-1
 #define KVM_PGTABLE_LAST_LEVEL		3
 
diff --git a/arch/arm64/include/asm/kvm_pkvm.h b/arch/arm64/include/asm/kvm_pkvm.h
index 2954b311128c..1bc6a6a34ec9 100644
--- a/arch/arm64/include/asm/kvm_pkvm.h
+++ b/arch/arm64/include/asm/kvm_pkvm.h
@@ -9,7 +9,7 @@
 #include <linux/arm_ffa.h>
 #include <linux/memblock.h>
 #include <linux/scatterlist.h>
-#include <asm/kvm_host.h>
+#include <linux/kvm_host.h>
 #include <asm/kvm_pgtable.h>
 
 /* Maximum number of VMs that can co-exist under pKVM. */
diff --git a/arch/arm64/kvm/hyp/pgtable.c b/arch/arm64/kvm/hyp/pgtable.c
index 0c1defa5fb0f..0bcd6f06aafb 100644
--- a/arch/arm64/kvm/hyp/pgtable.c
+++ b/arch/arm64/kvm/hyp/pgtable.c
@@ -8,6 +8,7 @@
  */
 
 #include <linux/bitfield.h>
+#include <linux/kvm_host.h>
 #include <asm/kvm_pgtable.h>
 #include <asm/stage2_pgtable.h>

---

## [4] Steven Price — 2026-05-13
*Subject: [PATCH v14 03/44] arm64: RME: Handle Granule Protection Faults (GPFs)*

If the host attempts to access granules that have been delegated for use
in a realm these accesses will be caught and will trigger a Granule
Protection Fault (GPF).

A fault during a page walk signals a bug in the kernel and is handled by
oopsing the kernel. A non-page walk fault could be caused by user space
having access to a page which has been delegated to the kernel and will
trigger a SIGBUS to allow debugging why user space is trying to access a
delegated page.

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v10:
 * Don't call arm64_notify_die() in do_gpf() but simply return 1.
Changes since v2:
 * Include missing "Granule Protection Fault at level -1"
---
 arch/arm64/mm/fault.c | 28 ++++++++++++++++++++++------
 1 file changed, 22 insertions(+), 6 deletions(-)

diff --git a/arch/arm64/mm/fault.c b/arch/arm64/mm/fault.c
index 0f3c5c7ca054..6358ea4787ba 100644
--- a/arch/arm64/mm/fault.c
+++ b/arch/arm64/mm/fault.c
@@ -905,6 +905,22 @@ static int do_tag_check_fault(unsigned long far, unsigned long esr,
 	return 0;
 }
 
+static int do_gpf_ptw(unsigned long far, unsigned long esr, struct pt_regs *regs)
+{
+	const struct fault_info *inf = esr_to_fault_info(esr);
+
+	die_kernel_fault(inf->name, far, esr, regs);
+	return 0;
+}
+
+static int do_gpf(unsigned long far, unsigned long esr, struct pt_regs *regs)
+{
+	if (!is_el1_instruction_abort(esr) && fixup_exception(regs, esr))
+		return 0;
+
+	return 1;
+}
+
 static const struct fault_info fault_info[] = {
 	{ do_bad,		SIGKILL, SI_KERNEL,	"ttbr address size fault"	},
 	{ do_bad,		SIGKILL, SI_KERNEL,	"level 1 address size fault"	},
@@ -941,12 +957,12 @@ static const struct fault_info fault_info[] = {
 	{ do_bad,		SIGKILL, SI_KERNEL,	"unknown 32"			},
 	{ do_alignment_fault,	SIGBUS,  BUS_ADRALN,	"alignment fault"		},
 	{ do_bad,		SIGKILL, SI_KERNEL,	"unknown 34"			},
-	{ do_bad,		SIGKILL, SI_KERNEL,	"unknown 35"			},
-	{ do_bad,		SIGKILL, SI_KERNEL,	"unknown 36"			},
-	{ do_bad,		SIGKILL, SI_KERNEL,	"unknown 37"			},
-	{ do_bad,		SIGKILL, SI_KERNEL,	"unknown 38"			},
-	{ do_bad,		SIGKILL, SI_KERNEL,	"unknown 39"			},
-	{ do_bad,		SIGKILL, SI_KERNEL,	"unknown 40"			},
+	{ do_gpf_ptw,		SIGKILL, SI_KERNEL,	"Granule Protection Fault at level -1" },
+	{ do_gpf_ptw,		SIGKILL, SI_KERNEL,	"Granule Protection Fault at level 0" },
+	{ do_gpf_ptw,		SIGKILL, SI_KERNEL,	"Granule Protection Fault at level 1" },
+	{ do_gpf_ptw,		SIGKILL, SI_KERNEL,	"Granule Protection Fault at level 2" },
+	{ do_gpf_ptw,		SIGKILL, SI_KERNEL,	"Granule Protection Fault at level 3" },
+	{ do_gpf,		SIGBUS,  SI_KERNEL,	"Granule Protection Fault not on table walk" },
 	{ do_bad,		SIGKILL, SI_KERNEL,	"level -1 address size fault"	},
 	{ do_bad,		SIGKILL, SI_KERNEL,	"unknown 42"			},
 	{ do_translation_fault,	SIGSEGV, SEGV_MAPERR,	"level -1 translation fault"	},

---

## [5] Steven Price — 2026-05-13
*Subject: [PATCH v14 04/44] arm64: RMI: Add SMC definitions for calling the RMM*

The RMM (Realm Management Monitor) provides functionality that can be
accessed by SMC calls from the host.

The SMC definitions are based on DEN0137[1] version 2.0-bet1

[1] https://developer.arm.com/documentation/den0137/2-0bet1/

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v13:
 * Updated to RMM spec v2.0-bet1
Changes since v12:
 * Updated to RMM spec v2.0-bet0
Changes since v9:
 * Corrected size of 'ripas_value' in struct rec_exit. The spec states
   this is an 8-bit type with padding afterwards (rather than a u64).
Changes since v8:
 * Added RMI_PERMITTED_GICV3_HCR_BITS to define which bits the RMM
   permits to be modified.
Changes since v6:
 * Renamed REC_ENTER_xxx defines to include 'FLAG' to make it obvious
   these are flag values.
Changes since v5:
 * Sorted the SMC #defines by value.
 * Renamed SMI_RxI_CALL to SMI_RMI_CALL since the macro is only used for
   RMI calls.
 * Renamed REC_GIC_NUM_LRS to REC_MAX_GIC_NUM_LRS since the actual
   number of available list registers could be lower.
 * Provided a define for the reserved fields of FeatureRegister0.
 * Fix inconsistent names for padding fields.
Changes since v4:
 * Update to point to final released RMM spec.
 * Minor rearrangements.
Changes since v3:
 * Update to match RMM spec v1.0-rel0-rc1.
Changes since v2:
 * Fix specification link.
 * Rename rec_entry->rec_enter to match spec.
 * Fix size of pmu_ovf_status to match spec.
---
 arch/arm64/include/asm/rmi_smc.h | 448 +++++++++++++++++++++++++++++++
 1 file changed, 448 insertions(+)
 create mode 100644 arch/arm64/include/asm/rmi_smc.h

diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
new file mode 100644
index 000000000000..a09b7a631fef
--- /dev/null
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -0,0 +1,448 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+/*
+ * Copyright (C) 2023-2026 ARM Ltd.
+ *
+ * The values and structures in this file are from the Realm Management Monitor
+ * specification (DEN0137) version 2.0-bet1:
+ * https://developer.arm.com/documentation/den0137/2-0bet1/
+ */
+
+#ifndef __ASM_RMI_SMC_H
+#define __ASM_RMI_SMC_H
+
+#include <linux/arm-smccc.h>
+
+#define SMC_RMI_CALL(func)				\
+	ARM_SMCCC_CALL_VAL(ARM_SMCCC_FAST_CALL,		\
+			   ARM_SMCCC_SMC_64,		\
+			   ARM_SMCCC_OWNER_STANDARD,	\
+			   (func))
+
+#define SMC_RMI_VERSION				SMC_RMI_CALL(0x0150)
+
+#define SMC_RMI_RTT_DATA_MAP_INIT		SMC_RMI_CALL(0x0153)
+
+#define SMC_RMI_REALM_ACTIVATE			SMC_RMI_CALL(0x0157)
+#define SMC_RMI_REALM_CREATE			SMC_RMI_CALL(0x0158)
+#define SMC_RMI_REALM_DESTROY			SMC_RMI_CALL(0x0159)
+#define SMC_RMI_REC_CREATE			SMC_RMI_CALL(0x015a)
+#define SMC_RMI_REC_DESTROY			SMC_RMI_CALL(0x015b)
+#define SMC_RMI_REC_ENTER			SMC_RMI_CALL(0x015c)
+#define SMC_RMI_RTT_CREATE			SMC_RMI_CALL(0x015d)
+#define SMC_RMI_RTT_DESTROY			SMC_RMI_CALL(0x015e)
+
+#define SMC_RMI_RTT_READ_ENTRY			SMC_RMI_CALL(0x0161)
+
+#define SMC_RMI_RTT_DEV_VALIDATE		SMC_RMI_CALL(0x0163)
+#define SMC_RMI_PSCI_COMPLETE			SMC_RMI_CALL(0x0164)
+#define SMC_RMI_FEATURES			SMC_RMI_CALL(0x0165)
+#define SMC_RMI_RTT_FOLD			SMC_RMI_CALL(0x0166)
+
+#define SMC_RMI_RTT_INIT_RIPAS			SMC_RMI_CALL(0x0168)
+#define SMC_RMI_RTT_SET_RIPAS			SMC_RMI_CALL(0x0169)
+#define SMC_RMI_VSMMU_CREATE			SMC_RMI_CALL(0x016a)
+#define SMC_RMI_VSMMU_DESTROY			SMC_RMI_CALL(0x016b)
+#define SMC_RMI_RMM_CONFIG_SET			SMC_RMI_CALL(0x016e)
+#define SMC_RMI_PSMMU_IRQ_NOTIFY		SMC_RMI_CALL(0x016f)
+
+#define SMC_RMI_PDEV_ABORT			SMC_RMI_CALL(0x0174)
+#define SMC_RMI_PDEV_COMMUNICATE		SMC_RMI_CALL(0x0175)
+#define SMC_RMI_PDEV_CREATE			SMC_RMI_CALL(0x0176)
+#define SMC_RMI_PDEV_DESTROY			SMC_RMI_CALL(0x0177)
+#define SMC_RMI_PDEV_GET_STATE			SMC_RMI_CALL(0x0178)
+
+#define SMC_RMI_PDEV_STREAM_KEY_REFRESH		SMC_RMI_CALL(0x017a)
+#define SMC_RMI_PDEV_SET_PUBKEY			SMC_RMI_CALL(0x017b)
+#define SMC_RMI_PDEV_STOP			SMC_RMI_CALL(0x017c)
+#define SMC_RMI_RTT_AUX_CREATE			SMC_RMI_CALL(0x017d)
+#define SMC_RMI_RTT_AUX_DESTROY			SMC_RMI_CALL(0x017e)
+#define SMC_RMI_RTT_AUX_FOLD			SMC_RMI_CALL(0x017f)
+
+#define SMC_RMI_VDEV_ABORT			SMC_RMI_CALL(0x0185)
+#define SMC_RMI_VDEV_COMMUNICATE		SMC_RMI_CALL(0x0186)
+#define SMC_RMI_VDEV_CREATE			SMC_RMI_CALL(0x0187)
+#define SMC_RMI_VDEV_DESTROY			SMC_RMI_CALL(0x0188)
+#define SMC_RMI_VDEV_GET_STATE			SMC_RMI_CALL(0x0189)
+#define SMC_RMI_VDEV_UNLOCK			SMC_RMI_CALL(0x018a)
+#define SMC_RMI_RTT_SET_S2AP			SMC_RMI_CALL(0x018b)
+#define SMC_RMI_VDEV_COMPLETE			SMC_RMI_CALL(0x018e)
+
+#define SMC_RMI_VDEV_GET_INTERFACE_REPORT	SMC_RMI_CALL(0x01d0)
+#define SMC_RMI_VDEV_GET_MEASUREMENTS		SMC_RMI_CALL(0x01d1)
+#define SMC_RMI_VDEV_LOCK			SMC_RMI_CALL(0x01d2)
+#define SMC_RMI_VDEV_START			SMC_RMI_CALL(0x01d3)
+
+#define SMC_RMI_VSMMU_EVENT_NOTIFY		SMC_RMI_CALL(0x01d6)
+#define SMC_RMI_PSMMU_ACTIVATE			SMC_RMI_CALL(0x01d7)
+#define SMC_RMI_PSMMU_DEACTIVATE		SMC_RMI_CALL(0x01d8)
+
+#define SMC_RMI_PSMMU_ST_L2_CREATE		SMC_RMI_CALL(0x01db)
+#define SMC_RMI_PSMMU_ST_L2_DESTROY		SMC_RMI_CALL(0x01dc)
+#define SMC_RMI_DPT_L0_CREATE			SMC_RMI_CALL(0x01dd)
+#define SMC_RMI_DPT_L0_DESTROY			SMC_RMI_CALL(0x01de)
+#define SMC_RMI_DPT_L1_CREATE			SMC_RMI_CALL(0x01df)
+#define SMC_RMI_DPT_L1_DESTROY			SMC_RMI_CALL(0x01e0)
+#define SMC_RMI_GRANULE_TRACKING_GET		SMC_RMI_CALL(0x01e1)
+
+#define SMC_RMI_GRANULE_TRACKING_SET		SMC_RMI_CALL(0x01e3)
+
+#define SMC_RMI_RMM_CONFIG_GET			SMC_RMI_CALL(0x01ec)
+
+#define SMC_RMI_RMM_STATE_GET			SMC_RMI_CALL(0x01ee)
+
+#define SMC_RMI_PSMMU_EVENT_CONSUME		SMC_RMI_CALL(0x01f0)
+#define SMC_RMI_GRANULE_RANGE_DELEGATE		SMC_RMI_CALL(0x01f1)
+#define SMC_RMI_GRANULE_RANGE_UNDELEGATE	SMC_RMI_CALL(0x01f2)
+#define SMC_RMI_GPT_L1_CREATE			SMC_RMI_CALL(0x01f3)
+#define SMC_RMI_GPT_L1_DESTROY			SMC_RMI_CALL(0x01f4)
+#define SMC_RMI_RTT_DATA_MAP			SMC_RMI_CALL(0x01f5)
+#define SMC_RMI_RTT_DATA_UNMAP			SMC_RMI_CALL(0x01f6)
+#define SMC_RMI_RTT_DEV_MAP			SMC_RMI_CALL(0x01f7)
+#define SMC_RMI_RTT_DEV_UNMAP			SMC_RMI_CALL(0x01f8)
+#define SMC_RMI_RTT_ARCH_DEV_MAP		SMC_RMI_CALL(0x01f9)
+#define SMC_RMI_RTT_ARCH_DEV_UNMAP		SMC_RMI_CALL(0x01fa)
+#define SMC_RMI_RTT_UNPROT_MAP			SMC_RMI_CALL(0x01fb)
+#define SMC_RMI_RTT_UNPROT_UNMAP		SMC_RMI_CALL(0x01fc)
+#define SMC_RMI_RTT_AUX_PROT_MAP		SMC_RMI_CALL(0x01fd)
+#define SMC_RMI_RTT_AUX_PROT_UNMAP		SMC_RMI_CALL(0x01fe)
+#define SMC_RMI_RTT_AUX_UNPROT_MAP		SMC_RMI_CALL(0x01ff)
+#define SMC_RMI_RTT_AUX_UNPROT_UNMAP		SMC_RMI_CALL(0x0200)
+#define SMC_RMI_REALM_TERMINATE			SMC_RMI_CALL(0x0201)
+#define SMC_RMI_RMM_ACTIVATE			SMC_RMI_CALL(0x0202)
+#define SMC_RMI_OP_CONTINUE			SMC_RMI_CALL(0x0203)
+#define SMC_RMI_PDEV_STREAM_CONNECT		SMC_RMI_CALL(0x0204)
+#define SMC_RMI_PDEV_STREAM_DISCONNECT		SMC_RMI_CALL(0x0205)
+#define SMC_RMI_PDEV_STREAM_COMPLETE		SMC_RMI_CALL(0x0206)
+#define SMC_RMI_PDEV_STREAM_KEY_PURGE		SMC_RMI_CALL(0x0207)
+#define SMC_RMI_OP_MEM_DONATE			SMC_RMI_CALL(0x0208)
+#define SMC_RMI_OP_MEM_RECLAIM			SMC_RMI_CALL(0x0209)
+#define SMC_RMI_OP_CANCEL			SMC_RMI_CALL(0x020a)
+#define SMC_RMI_VSMMU_FEATURES			SMC_RMI_CALL(0x020b)
+#define SMC_RMI_VSMMU_CMD_GET			SMC_RMI_CALL(0x020c)
+#define SMC_RMI_VSMMU_CMD_COMPLETE		SMC_RMI_CALL(0x020d)
+#define SMC_RMI_PSMMU_INFO			SMC_RMI_CALL(0x020e)
+
+#define RMI_ABI_MAJOR_VERSION	2
+#define RMI_ABI_MINOR_VERSION	0
+
+#define RMI_ABI_VERSION_GET_MAJOR(version) ((version) >> 16)
+#define RMI_ABI_VERSION_GET_MINOR(version) ((version) & 0xFFFF)
+#define RMI_ABI_VERSION(major, minor)      (((major) << 16) | (minor))
+
+#define RMI_UNASSIGNED			0
+#define RMI_ASSIGNED			1
+#define RMI_TABLE			2
+
+#define RMI_RETURN_STATUS(ret)		((ret) & 0xFF)
+#define RMI_RETURN_INDEX(ret)		(((ret) >> 8) & 0xFF)
+#define RMI_RETURN_MEMREQ(ret)		(((ret) >> 8) & 0x3)
+#define RMI_RETURN_CAN_CANCEL(ret)	(((ret) >> 10) & 0x1)
+
+#define RMI_SUCCESS			0
+#define RMI_ERROR_INPUT			1
+#define RMI_ERROR_REALM			2
+#define RMI_ERROR_REC			3
+#define RMI_ERROR_RTT			4
+#define RMI_ERROR_NOT_SUPPORTED		5
+#define RMI_ERROR_DEVICE		6
+#define RMI_ERROR_RTT_AUX		7
+#define RMI_ERROR_PSMMU_ST		8
+#define RMI_ERROR_DPT			9
+#define RMI_BUSY			10
+#define RMI_ERROR_GLOBAL		11
+#define RMI_ERROR_TRACKING		12
+#define RMI_INCOMPLETE			13
+#define RMI_BLOCKED			14
+#define RMI_ERROR_GPT			15
+#define RMI_ERROR_GRANULE		16
+
+#define RMI_OP_MEM_REQ_NONE		0
+#define RMI_OP_MEM_REQ_DONATE		1
+#define RMI_OP_MEM_REQ_RECLAIM		2
+
+#define RMI_DONATE_SIZE(req)		((req) & 0x3)
+#define RMI_DONATE_COUNT_MASK		GENMASK(15, 2)
+#define RMI_DONATE_COUNT(req)		(((req) & RMI_DONATE_COUNT_MASK) >> 2)
+#define RMI_DONATE_CONTIG(req)		(!!((req) & BIT(16)))
+#define RMI_DONATE_STATE(req)		(!!((req) & BIT(17)))
+
+#define RMI_OP_MEM_DELEGATED		0
+#define RMI_OP_MEM_UNDELEGATED		1
+
+#define RMI_ADDR_TYPE_NONE		0
+#define RMI_ADDR_TYPE_SINGLE		1
+#define RMI_ADDR_TYPE_LIST		2
+
+#define RMI_ADDR_RANGE_SIZE_MASK	GENMASK(1, 0)
+#define RMI_ADDR_RANGE_COUNT_MASK	GENMASK(PAGE_SHIFT - 1, 2)
+#define RMI_ADDR_RANGE_ADDR_MASK	(PAGE_MASK & GENMASK(51, 0))
+#define RMI_ADDR_RANGE_STATE_MASK	BIT(63)
+
+#define RMI_ADDR_RANGE_SIZE(ar)		(FIELD_GET(RMI_ADDR_RANGE_SIZE_MASK, \
+						   (ar)))
+#define RMI_ADDR_RANGE_COUNT(ar)	(FIELD_GET(RMI_ADDR_RANGE_COUNT_MASK, \
+						   (ar)))
+#define RMI_ADDR_RANGE_ADDR(ar)		((ar) & RMI_ADDR_RANGE_ADDR_MASK)
+#define RMI_ADDR_RANGE_STATE(ar)	(FIELD_GET(RMI_ADDR_RANGE_STATE_MASK, \
+						   (ar)))
+
+enum rmi_ripas {
+	RMI_EMPTY = 0,
+	RMI_RAM = 1,
+	RMI_DESTROYED = 2,
+	RMI_DEV = 3,
+};
+
+#define RMI_NO_MEASURE_CONTENT	0
+#define RMI_MEASURE_CONTENT	1
+
+#define RMI_FEATURE_REGISTER_0_S2SZ		GENMASK(7, 0)
+#define RMI_FEATURE_REGISTER_0_LPA2		BIT(8)
+#define RMI_FEATURE_REGISTER_0_SVE		BIT(9)
+#define RMI_FEATURE_REGISTER_0_SVE_VL		GENMASK(13, 10)
+#define RMI_FEATURE_REGISTER_0_NUM_BPS		GENMASK(19, 14)
+#define RMI_FEATURE_REGISTER_0_NUM_WPS		GENMASK(25, 20)
+#define RMI_FEATURE_REGISTER_0_PMU		BIT(26)
+#define RMI_FEATURE_REGISTER_0_PMU_NUM_CTRS	GENMASK(31, 27)
+
+#define RMI_FEATURE_REGISTER_1_RMI_GRAN_SZ_4KB	BIT(0)
+#define RMI_FEATURE_REGISTER_1_RMI_GRAN_SZ_16KB	BIT(1)
+#define RMI_FEATURE_REGISTER_1_RMI_GRAN_SZ_64KB	BIT(2)
+#define RMI_FEATURE_REGISTER_1_HASH_SHA_256	BIT(3)
+#define RMI_FEATURE_REGISTER_1_HASH_SHA_384	BIT(4)
+#define RMI_FEATURE_REGISTER_1_HASH_SHA_512	BIT(5)
+#define RMI_FEATURE_REGISTER_1_MAX_RECS_ORDER	GENMASK(9, 6)
+#define RMI_FEATURE_REGISTER_1_L0GPTSZ		GENMASK(13, 10)
+#define RMI_FEATURE_REGISTER_1_PPS		GENMASK(16, 14)
+
+#define RMI_FEATURE_REGISTER_2_DA		BIT(0)
+#define RMI_FEATURE_REGISTER_2_DA_COH		BIT(1)
+#define RMI_FEATURE_REGISTER_2_VSMMU		BIT(2)
+#define RMI_FEATURE_REGISTER_2_ATS		BIT(3)
+#define RMI_FEATURE_REGISTER_2_MAX_VDEVS_ORDER	GENMASK(7, 4)
+#define RMI_FEATURE_REGISTER_2_VDEV_KROU	BIT(8)
+#define RMI_FEATURE_REGISTER_2_NON_TEE_STREAM	BIT(9)
+
+#define RMI_FEATURE_REGISTER_3_MAX_NUM_AUX_PLANES	GENMASK(3, 0)
+#define RMI_FEATURE_REGISTER_3_RTT_PLAN			GENMASK(5, 4)
+#define RMI_FEATURE_REGISTER_3_RTT_S2AP_INDIRECT	BIT(6)
+
+#define RMI_FEATURE_REGISTER_4_MEC_COUNT		GENMASK(63, 0)
+
+#define RMI_MEM_CATEGORY_CONVENTIONAL		0
+#define RMI_MEM_CATEGORY_DEV_NCOH		1
+#define RMI_MEM_CATEGORY_DEV_COH		2
+
+#define RMI_TRACKING_RESERVED			0
+#define RMI_TRACKING_NONE			1
+#define RMI_TRACKING_FINE			2
+#define RMI_TRACKING_COARSE			3
+
+#define RMI_GRANULE_SIZE_4KB	0
+#define RMI_GRANULE_SIZE_16KB	1
+#define RMI_GRANULE_SIZE_64KB	2
+
+/*
+ * Note many of these fields are smaller than u64 but all fields have u64
+ * alignment, so use u64 to ensure correct alignment.
+ */
+struct rmm_config {
+	union { /* 0x0 */
+		struct {
+			u64 tracking_region_size;
+			u64 rmi_granule_size;
+		};
+		u8 sizer[0x1000];
+	};
+};
+
+#define RMI_REALM_PARAM_FLAG_LPA2		BIT(0)
+#define RMI_REALM_PARAM_FLAG_SVE		BIT(1)
+#define RMI_REALM_PARAM_FLAG_PMU		BIT(2)
+
+struct realm_params {
+	union { /* 0x0 */
+		struct {
+			u64 flags;
+			u64 s2sz;
+			u64 sve_vl;
+			u64 num_bps;
+			u64 num_wps;
+			u64 pmu_num_ctrs;
+			u64 hash_algo;
+			u64 num_aux_planes;
+		};
+		u8 padding0[0x400];
+	};
+	union { /* 0x400 */
+		struct {
+			u8 rpv[64];
+			u64 ats_plane;
+		};
+		u8 padding1[0x400];
+	};
+	union { /* 0x800 */
+		struct {
+			u64 padding;
+			u64 rtt_base;
+			s64 rtt_level_start;
+			u64 rtt_num_start;
+			u64 flags1;
+			u64 aux_rtt_base[3];
+		};
+		u8 padding2[0x800];
+	};
+};
+
+/*
+ * The number of GPRs (starting from X0) that are
+ * configured by the host when a REC is created.
+ */
+#define REC_CREATE_NR_GPRS		8
+
+#define REC_PARAMS_FLAG_RUNNABLE	BIT_ULL(0)
+
+struct rec_params {
+	union { /* 0x0 */
+		u64 flags;
+		u8 padding0[0x100];
+	};
+	union { /* 0x100 */
+		u64 mpidr;
+		u8 padding1[0x100];
+	};
+	union { /* 0x200 */
+		u64 pc;
+		u8 padding2[0x100];
+	};
+	union { /* 0x300 */
+		u64 gprs[REC_CREATE_NR_GPRS];
+		u8 padding3[0xd00];
+	};
+};
+
+#define REC_ENTER_FLAG_EMULATED_MMIO	BIT(0)
+#define REC_ENTER_FLAG_INJECT_SEA	BIT(1)
+#define REC_ENTER_FLAG_TRAP_WFI		BIT(2)
+#define REC_ENTER_FLAG_TRAP_WFE		BIT(3)
+#define REC_ENTER_FLAG_RIPAS_RESPONSE	BIT(4)
+#define REC_ENTER_FLAG_S2AP_RESPONSE	BIT(5)
+#define REC_ENTER_FLAG_DEV_MEM_RESPONSE	BIT(6)
+#define REC_ENTER_FLAG_FORCE_P0		BIT(7)
+
+#define REC_RUN_GPRS			31
+#define REC_MAX_GIC_NUM_LRS		16
+
+#define RMI_PERMITTED_GICV3_HCR_BITS	(ICH_HCR_EL2_UIE |		\
+					 ICH_HCR_EL2_LRENPIE |		\
+					 ICH_HCR_EL2_NPIE |		\
+					 ICH_HCR_EL2_VGrp0EIE |		\
+					 ICH_HCR_EL2_VGrp0DIE |		\
+					 ICH_HCR_EL2_VGrp1EIE |		\
+					 ICH_HCR_EL2_VGrp1DIE |		\
+					 ICH_HCR_EL2_TDIR)
+
+struct rec_enter {
+	union { /* 0x000 */
+		u64 flags;
+		u8 padding0[0x200];
+	};
+	union { /* 0x200 */
+		u64 gprs[REC_RUN_GPRS];
+		u8 padding1[0x100];
+	};
+	u8 padding3[0x500];
+};
+
+#define RMI_EXIT_SYNC			0x00
+#define RMI_EXIT_IRQ			0x01
+#define RMI_EXIT_FIQ			0x02
+#define RMI_EXIT_PSCI			0x03
+#define RMI_EXIT_RIPAS_CHANGE		0x04
+#define RMI_EXIT_HOST_CALL		0x05
+#define RMI_EXIT_SERROR			0x06
+#define RMI_EXIT_S2AP_CHANGE		0x07
+#define RMI_EXIT_VDEV_REQUEST		0x08
+#define RMI_EXIT_VDEV_VALIDATE_MAPPING	0x09
+#define RMI_EXIT_VSMMU_COMMAND		0x0a
+
+struct rec_exit {
+	union { /* 0x000 */
+		u8 exit_reason;
+		u8 padding0[0x100];
+	};
+	union { /* 0x100 */
+		struct {
+			u64 esr;
+			u64 far;
+			u64 hpfar;
+			u64 rtt_tree;
+		};
+		u8 padding1[0x100];
+	};
+	union { /* 0x200 */
+		u64 gprs[REC_RUN_GPRS];
+		u8 padding2[0x100];
+	};
+	union { /* 0x300 */
+		u8 padding3[0x100];
+	};
+	union { /* 0x400 */
+		struct {
+			u64 cntp_ctl;
+			u64 cntp_cval;
+			u64 cntv_ctl;
+			u64 cntv_cval;
+		};
+		u8 padding4[0x100];
+	};
+	union { /* 0x500 */
+		struct {
+			u64 ripas_base;
+			u64 ripas_top;
+			u8 ripas_value;
+			u8 padding8[15];
+			u64 s2ap_base;
+			u64 s2ap_top;
+			u64 vdev_id_1;
+			u64 vdev_id_2;
+			u64 dev_mem_base;
+			u64 dev_mem_top;
+			u64 dev_mem_pa;
+		};
+		u8 padding5[0x100];
+	};
+	union { /* 0x600 */
+		struct {
+			u16 imm;
+			u16 padding9;
+			u64 plane;
+		};
+		u8 padding6[0x100];
+	};
+	union { /* 0x700 */
+		struct {
+			u8 pmu_ovf_status;
+			u8 padding10[15];
+			u64 vsmmu;
+		};
+		u8 padding7[0x100];
+	};
+};
+
+struct rec_run {
+	struct rec_enter enter;
+	struct rec_exit exit;
+};
+
+/* RMI_RTT_UNPROT_MAP_FLAGS definitions */
+#define RMI_RTT_UNPROT_MAP_FLAGS_OADDR_TYPE	GENMASK(1, 0)
+#define RMI_RTT_UNPROT_MAP_FLAGS_LIST_COUNT	GENMASK(15, 2)
+#define RMI_RTT_UNPROT_MAP_FLAGS_MEMATTR	GENMASK(18, 16)
+#define RMI_RTT_UNPROT_MAP_FLAGS_S2AP		GENMASK(22, 19)
+
+/* S2AP Direct Encodings, used in RMI_RTT_UNPROT_MAP_FLAGS_S2AP */
+#define RMI_S2AP_DIRECT_WRITE			BIT(0)
+#define RMI_S2AP_DIRECT_READ			BIT(1)
+
+#endif /* __ASM_RMI_SMC_H */

---

## [6] Steven Price — 2026-05-13
*Subject: [PATCH v14 05/44] arm64: RMI: Add wrappers for RMI calls*

The wrappers make the call sites easier to read and deal with the
boiler plate of handling the error codes from the RMM.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes from v13:
 * Update to RMM v2.0-bet1 spec including some SRO support (there still
   some FIXMEs where SRO support is incomplete).
Changes from v12:
 * Update to RMM v2.0 specification
Changes from v8:
 * Switch from arm_smccc_1_2_smc() to arm_smccc_1_2_invoke() in
   rmi_rtt_read_entry() for consistency.
Changes from v7:
 * Minor renaming of parameters and updated comments
Changes from v5:
 * Further improve comments
Changes from v4:
 * Improve comments
Changes from v2:
 * Make output arguments optional.
 * Mask RIPAS value rmi_rtt_read_entry()
 * Drop unused rmi_rtt_get_phys()
---
 arch/arm64/include/asm/rmi_cmds.h | 661 ++++++++++++++++++++++++++++++
 1 file changed, 661 insertions(+)
 create mode 100644 arch/arm64/include/asm/rmi_cmds.h

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
new file mode 100644
index 000000000000..04f7066894e9
--- /dev/null
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -0,0 +1,661 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+/*
+ * Copyright (C) 2023 ARM Ltd.
+ */
+
+#ifndef __ASM_RMI_CMDS_H
+#define __ASM_RMI_CMDS_H
+
+#include <linux/arm-smccc.h>
+
+#include <asm/rmi_smc.h>
+
+struct rtt_entry {
+	unsigned long walk_level;
+	unsigned long desc;
+	int state;
+	int ripas;
+};
+
+#define RMI_MAX_ADDR_LIST	256
+
+struct rmi_sro_state {
+	struct arm_smccc_1_2_regs regs;
+	unsigned long addr_count;
+	unsigned long addr_list[RMI_MAX_ADDR_LIST];
+};
+
+#define rmi_smccc(...) do {						\
+	arm_smccc_1_1_invoke(__VA_ARGS__);				\
+} while (RMI_RETURN_STATUS(res.a0) == RMI_BUSY ||			\
+	 RMI_RETURN_STATUS(res.a0) == RMI_BLOCKED)
+
+unsigned long rmi_sro_execute(struct rmi_sro_state *sro, gfp_t gfp);
+void rmi_sro_free(struct rmi_sro_state *sro);
+
+/**
+ * rmi_rmm_config_set() - Configure the RMM
+ * @cfg_ptr: PA of a struct rmm_config
+ *
+ * Sets configuration options on the RMM.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rmm_config_set(unsigned long cfg_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RMM_CONFIG_SET, cfg_ptr, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_rmm_activate() - Activate the RMM
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rmm_activate(void)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RMM_ACTIVATE, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_granule_tracking_get() - Get configuration of a Granule tracking region
+ * @start: Base PA of the tracking region
+ * @end: End of the PA region
+ * @out_category: Memory category
+ * @out_state: Tracking region state
+ * @out_top: Top of the memory region
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_granule_tracking_get(unsigned long start,
+					   unsigned long end,
+					   unsigned long *out_category,
+					   unsigned long *out_state,
+					   unsigned long *out_top)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_GRANULE_TRACKING_GET, start, end, &res);
+
+	if (out_category)
+		*out_category = res.a1;
+	if (out_state)
+		*out_state = res.a2;
+	if (out_top)
+		*out_top = res.a3;
+
+	return res.a0;
+}
+
+/**
+ * rmi_gpt_l1_create() - Create a Level 1 GPT
+ * @addr: Base of physical address region described by the L1GPT
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_gpt_l1_create(unsigned long addr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_GPT_L1_CREATE, addr, &res);
+
+	if (RMI_RETURN_STATUS(res.a0) == RMI_INCOMPLETE) {
+		/* FIXME */
+		return WARN_ON(res.a0);
+	}
+
+	return res.a0;
+}
+
+/**
+ * rmi_rtt_data_map_init() - Create a protected mapping with data contents
+ * @rd: PA of the RD
+ * @data: PA of the target granule
+ * @ipa: IPA at which the granule will be mapped in the guest
+ * @src: PA of the source granule
+ * @flags: RMI_MEASURE_CONTENT if the contents should be measured
+ *
+ * Create a mapping from Protected IPA space to conventional memory, copying
+ * contents from a Non-secure Granule provided by the caller.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rtt_data_map_init(unsigned long rd, unsigned long data,
+					unsigned long ipa, unsigned long src,
+					unsigned long flags)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_DATA_MAP_INIT, rd, data, ipa, src,
+			     flags, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_rtt_data_map() - Create mappings in protected IPA with unknown contents
+ * @rd: PA of the RD
+ * @base: Base of the target IPA range
+ * @top: Top of the target IPA range
+ * @flags: Flags
+ * @oaddr: Output address set descriptor
+ * @out_top: Top address of range which was processed.
+ *
+ * Return RMI return code
+ */
+static inline int rmi_rtt_data_map(unsigned long rd,
+				   unsigned long base,
+				   unsigned long top,
+				   unsigned long flags,
+				   unsigned long oaddr,
+				   unsigned long *out_top)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_DATA_MAP, rd, base, top, flags, oaddr,
+			     &res);
+
+	if (RMI_RETURN_STATUS(res.a0) == RMI_INCOMPLETE) {
+		/* FIXME */
+		return WARN_ON(res.a0);
+	}
+
+	if (out_top)
+		*out_top = res.a1;
+
+	return res.a0;
+}
+
+/**
+ * rmi_rtt_data_unmap() - Remove mappings to conventional memory
+ * @rd: PA of the RD for the target Realm
+ * @base: Base of the target IPA range
+ * @top: Top of the target IPA range
+ * @flags: Flags
+ * @oaddr: Output address set descriptor
+ * @out_top: Returns top IPA of range which has been unmapped
+ * @out_range: Output address range
+ * @out_count: Number of entries in output address list
+ *
+ * Removes mappings to convention memory with a target Protected IPA range.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rtt_data_unmap(unsigned long rd,
+				     unsigned long base,
+				     unsigned long top,
+				     unsigned long flags,
+				     unsigned long oaddr,
+				     unsigned long *out_top,
+				     unsigned long *out_range,
+				     unsigned long *out_count)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_DATA_UNMAP, rd, base, top, flags,
+			     oaddr, &res);
+
+	/* FIXME: Handle SRO */
+
+	if (out_top)
+		*out_top = res.a1;
+	if (out_range)
+		*out_range = res.a2;
+	if (out_count)
+		*out_count = res.a3;
+
+	return res.a0;
+}
+
+/**
+ * rmi_features() - Read feature register
+ * @index: Feature register index
+ * @out: Feature register value is written to this pointer
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_features(unsigned long index, unsigned long *out)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_FEATURES, index, &res);
+
+	if (out)
+		*out = res.a1;
+	return res.a0;
+}
+
+/**
+ * rmi_granule_range_delegate() - Delegate granules
+ * @base: PA of the first granule of the range
+ * @top: PA of the first granule after the range
+ * @out_top: PA of the first granule not delegated
+ *
+ * Delegate a range of granule for use by the realm world. If the entire range
+ * was delegated then @out_top == @top, otherwise the function should be called
+ * again with @base == @out_top.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_granule_range_delegate(unsigned long base,
+					     unsigned long top,
+					     unsigned long *out_top)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_GRANULE_RANGE_DELEGATE, base, top, &res);
+
+	if (RMI_RETURN_STATUS(res.a0) == RMI_INCOMPLETE) {
+		/* FIXME - Handle SRO */
+		return WARN_ON(res.a0);
+	}
+
+	if (out_top)
+		*out_top = res.a1;
+
+	return res.a0;
+}
+
+/**
+ * rmi_granule_range_undelegate() - Undelegate a range of granules
+ * @base: Base PA of the target range
+ * @top: Top PA of the target range
+ * @out_top: Returns the top PA of range whose state is undelegated
+ *
+ * Undelegate a range of granules to allow use by the normal world. Will fail if
+ * the granules are in use.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_granule_range_undelegate(unsigned long base,
+					       unsigned long top,
+					       unsigned long *out_top)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_GRANULE_RANGE_UNDELEGATE, base, top, &res);
+
+	if (RMI_RETURN_STATUS(res.a0) == RMI_INCOMPLETE) {
+		/* FIXME - Handle SRO */
+		return WARN_ON(res.a0);
+	}
+
+	if (out_top)
+		*out_top = res.a1;
+
+	return res.a0;
+}
+
+/**
+ * rmi_psci_complete() - Complete pending PSCI command
+ * @calling_rec: PA of the calling REC
+ * @target_rec: PA of the target REC
+ * @status: Status of the PSCI request
+ *
+ * Completes a pending PSCI command which was called with an MPIDR argument, by
+ * providing the corresponding REC.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_psci_complete(unsigned long calling_rec,
+				    unsigned long target_rec,
+				    unsigned long status)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PSCI_COMPLETE, calling_rec, target_rec,
+			     status, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_realm_activate() - Active a realm
+ * @rd: PA of the RD
+ *
+ * Mark a realm as Active signalling that creation is complete and allowing
+ * execution of the realm.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_realm_activate(unsigned long rd)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_REALM_ACTIVATE, rd, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_realm_create() - Create a realm
+ * @rd: PA of the RD
+ * @params: PA of realm parameters
+ *
+ * Create a new realm using the given parameters.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_realm_create(unsigned long rd, unsigned long params)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_REALM_CREATE, rd, params, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_realm_terminate() - Terminate a realm
+ * @rd: PA of the RD
+ *
+ * Terminates a realm, moving it into a ZOMBIE state
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_realm_terminate(unsigned long rd)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_REALM_TERMINATE, rd, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_realm_destroy() - Destroy a realm
+ * @rd: PA of the RD
+ *
+ * Destroys a realm, all objects belonging to the realm must be destroyed first.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_realm_destroy(unsigned long rd)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_REALM_DESTROY, rd, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_rec_create() - Create a REC
+ * @rd: PA of the RD
+ * @rec: PA of the target REC
+ * @params: PA of REC parameters
+ * @sro: Allocated SRO context to be used
+ *
+ * Create a REC using the parameters specified in the struct rec_params pointed
+ * to by @params.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rec_create(unsigned long rd,
+				 unsigned long rec,
+				 unsigned long params,
+				 struct rmi_sro_state *sro)
+{
+	int ret;
+
+	*sro = (struct rmi_sro_state){.regs = {
+		SMC_RMI_REC_CREATE, rd, rec, params
+	}};
+	ret = rmi_sro_execute(sro, GFP_KERNEL);
+	rmi_sro_free(sro);
+
+	return ret;
+}
+
+/**
+ * rmi_rec_destroy() - Destroy a REC
+ * @rec: PA of the target REC
+ * @sro: Allocated SRO context to be used
+ *
+ * Destroys a REC. The REC must not be running.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rec_destroy(unsigned long rec,
+				  struct rmi_sro_state *sro)
+{
+	int ret;
+
+	*sro = (struct rmi_sro_state){.regs = {
+		SMC_RMI_REC_DESTROY, rec
+	}};
+	ret = rmi_sro_execute(sro, GFP_KERNEL);
+	rmi_sro_free(sro);
+
+	return ret;
+}
+
+/**
+ * rmi_rec_enter() - Enter a REC
+ * @rec: PA of the target REC
+ * @run_ptr: PA of RecRun structure
+ *
+ * Starts (or continues) execution within a REC.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rec_enter(unsigned long rec, unsigned long run_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_REC_ENTER, rec, run_ptr, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_rtt_create() - Creates an RTT
+ * @rd: PA of the RD
+ * @rtt: PA of the target RTT
+ * @ipa: Base of the IPA range described by the RTT
+ * @level: Depth of the RTT within the tree
+ *
+ * Creates an RTT (Realm Translation Table) at the specified level for the
+ * translation of the specified address within the realm.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rtt_create(unsigned long rd, unsigned long rtt,
+				 unsigned long ipa, long level)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_CREATE, rd, rtt, ipa, level, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_rtt_destroy() - Destroy an RTT
+ * @rd: PA of the RD
+ * @ipa: Base of the IPA range described by the RTT
+ * @level: Depth of the RTT within the tree
+ * @out_rtt: Pointer to write the PA of the RTT which was destroyed
+ * @out_top: Pointer to write the top IPA of non-live RTT entries
+ *
+ * Destroys an RTT. The RTT must be non-live, i.e. none of the entries in the
+ * table are in ASSIGNED or TABLE state.
+ *
+ * Return: RMI return code.
+ */
+static inline int rmi_rtt_destroy(unsigned long rd,
+				  unsigned long ipa,
+				  long level,
+				  unsigned long *out_rtt,
+				  unsigned long *out_top)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_DESTROY, rd, ipa, level, &res);
+
+	if (out_rtt)
+		*out_rtt = res.a1;
+	if (out_top)
+		*out_top = res.a2;
+
+	return res.a0;
+}
+
+/**
+ * rmi_rtt_fold() - Fold an RTT
+ * @rd: PA of the RD
+ * @ipa: Base of the IPA range described by the RTT
+ * @level: Depth of the RTT within the tree
+ * @out_rtt: Pointer to write the PA of the RTT which was destroyed
+ *
+ * Folds an RTT. If all entries with the RTT are 'homogeneous' the RTT can be
+ * folded into the parent and the RTT destroyed.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rtt_fold(unsigned long rd, unsigned long ipa,
+			       long level, unsigned long *out_rtt)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_FOLD, rd, ipa, level, &res);
+
+	if (out_rtt)
+		*out_rtt = res.a1;
+
+	return res.a0;
+}
+
+/**
+ * rmi_rtt_init_ripas() - Set RIPAS for new realm
+ * @rd: PA of the RD
+ * @base: Base of target IPA region
+ * @top: Top of target IPA region
+ * @out_top: Top IPA of range whose RIPAS was modified
+ *
+ * Sets the RIPAS of a target IPA range to RAM, for a realm in the NEW state.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rtt_init_ripas(unsigned long rd, unsigned long base,
+				     unsigned long top, unsigned long *out_top)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_INIT_RIPAS, rd, base, top, &res);
+
+	if (out_top)
+		*out_top = res.a1;
+
+	return res.a0;
+}
+
+/**
+ * rmi_rtt_unprot_map() - Map unprotected granules into a realm
+ * @rd: PA of the RD
+ * @base: Base IPA of the mapping
+ * @top: Top of the target IPA range
+ * @flags: Flags
+ * @oaddr: Output address set descriptor
+ * @out_top: Top IPA of range which has been mapped
+ *
+ * Create mappings to memory within a target unprotected IPA range.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rtt_unprot_map(unsigned long rd,
+				     unsigned long base,
+				     unsigned long top,
+				     unsigned long flags,
+				     unsigned long oaddr,
+				     unsigned long *out_top)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_UNPROT_MAP, rd, base, top, flags,
+			     oaddr, &res);
+
+	/* FIXME: Handle SRO */
+
+	if (out_top)
+		*out_top = res.a1;
+
+	return res.a0;
+}
+
+/**
+ * rmi_rtt_set_ripas() - Set RIPAS for an running realm
+ * @rd: PA of the RD
+ * @rec: PA of the REC making the request
+ * @base: Base of target IPA region
+ * @top: Top of target IPA region
+ * @out_top: Pointer to write top IPA of range whose RIPAS was modified
+ *
+ * Completes a request made by the realm to change the RIPAS of a target IPA
+ * range.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rtt_set_ripas(unsigned long rd, unsigned long rec,
+				    unsigned long base, unsigned long top,
+				    unsigned long *out_top)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_SET_RIPAS, rd, rec, base, top, &res);
+
+	if (out_top)
+		*out_top = res.a1;
+
+	return res.a0;
+}
+
+/**
+ * rmi_rtt_unprot_unmap() - Remove mappings within an unprotected IPA range
+ * @rd: PA of the RD
+ * @base: Base IPA of the mapping
+ * @top: Top of the target IPA range
+ * @flags: Flags
+ * @oaddr: Output address set descriptor
+ * @out_top: Top IPA which has been unmapped
+ * @out_range: Output address range
+ * @out_count: Number of entries in output address list
+ *
+ * Removes mappings to memory within a target unprotected IPA range.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rtt_unprot_unmap(unsigned long rd,
+				       unsigned long base,
+				       unsigned long top,
+				       unsigned long flags,
+				       unsigned long oaddr,
+				       unsigned long *out_top,
+				       unsigned long *out_range,
+				       unsigned long *out_count)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_UNPROT_UNMAP, rd, base, top,
+			     flags, oaddr, &res);
+
+	/* FIXME: Handle SRO */
+
+	if (out_top)
+		*out_top = res.a1;
+	if (out_range)
+		*out_range = res.a2;
+	if (out_count)
+		*out_count = res.a3;
+
+	return res.a0;
+}
+
+#endif /* __ASM_RMI_CMDS_H */

---

## [7] Steven Price — 2026-05-13
*Subject: [PATCH v14 06/44] arm64: RMI: Check for RMI support at init*

Query the RMI version number and check if it is a compatible version.
The first two feature registers are read and exposed for future code to
use.

Signed-off-by: Steven Price <steven.price@arm.com>
---
v14:
 * This moves the basic RMI setup into the 'kernel' directory. This is
   because RMI will be used for some features outside of KVM so should
   be available even if KVM isn't compiled in.
---
 arch/arm64/include/asm/rmi_cmds.h |  3 ++
 arch/arm64/kernel/Makefile        |  2 +-
 arch/arm64/kernel/cpufeature.c    |  1 +
 arch/arm64/kernel/rmi.c           | 65 +++++++++++++++++++++++++++++++
 4 files changed, 70 insertions(+), 1 deletion(-)
 create mode 100644 arch/arm64/kernel/rmi.c

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 04f7066894e9..9179934925c5 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -10,6 +10,9 @@
 
 #include <asm/rmi_smc.h>
 
+extern unsigned long rmm_feat_reg0;
+extern unsigned long rmm_feat_reg1;
+
 struct rtt_entry {
 	unsigned long walk_level;
 	unsigned long desc;
diff --git a/arch/arm64/kernel/Makefile b/arch/arm64/kernel/Makefile
index 74b76bb70452..d68f351aae75 100644
--- a/arch/arm64/kernel/Makefile
+++ b/arch/arm64/kernel/Makefile
@@ -34,7 +34,7 @@ obj-y			:= debug-monitors.o entry.o irq.o fpsimd.o		\
 			   cpufeature.o alternative.o cacheinfo.o		\
 			   smp.o smp_spin_table.o topology.o smccc-call.o	\
 			   syscall.o proton-pack.o idle.o patching.o pi/	\
-			   rsi.o jump_label.o
+			   rsi.o jump_label.o rmi.o
 
 obj-$(CONFIG_COMPAT)			+= sys32.o signal32.o			\
 					   sys_compat.o
diff --git a/arch/arm64/kernel/cpufeature.c b/arch/arm64/kernel/cpufeature.c
index 6d53bb15cf7b..8bdd95a8c2de 100644
--- a/arch/arm64/kernel/cpufeature.c
+++ b/arch/arm64/kernel/cpufeature.c
@@ -292,6 +292,7 @@ static const struct arm64_ftr_bits ftr_id_aa64isar3[] = {
 static const struct arm64_ftr_bits ftr_id_aa64pfr0[] = {
 	ARM64_FTR_BITS(FTR_HIDDEN, FTR_NONSTRICT, FTR_LOWER_SAFE, ID_AA64PFR0_EL1_CSV3_SHIFT, 4, 0),
 	ARM64_FTR_BITS(FTR_HIDDEN, FTR_NONSTRICT, FTR_LOWER_SAFE, ID_AA64PFR0_EL1_CSV2_SHIFT, 4, 0),
+	ARM64_FTR_BITS(FTR_HIDDEN, FTR_NONSTRICT, FTR_LOWER_SAFE, ID_AA64PFR0_EL1_RME_SHIFT, 4, 0),
 	ARM64_FTR_BITS(FTR_VISIBLE, FTR_STRICT, FTR_LOWER_SAFE, ID_AA64PFR0_EL1_DIT_SHIFT, 4, 0),
 	ARM64_FTR_BITS(FTR_HIDDEN, FTR_NONSTRICT, FTR_LOWER_SAFE, ID_AA64PFR0_EL1_AMU_SHIFT, 4, 0),
 	ARM64_FTR_BITS(FTR_HIDDEN, FTR_STRICT, FTR_LOWER_SAFE, ID_AA64PFR0_EL1_MPAM_SHIFT, 4, 0),
diff --git a/arch/arm64/kernel/rmi.c b/arch/arm64/kernel/rmi.c
new file mode 100644
index 000000000000..99c1ccc35c11
--- /dev/null
+++ b/arch/arm64/kernel/rmi.c
@@ -0,0 +1,65 @@
+// SPDX-License-Identifier: GPL-2.0
+/*
+ * Copyright (C) 2023-2025 ARM Ltd.
+ */
+
+#include <linux/memblock.h>
+
+#include <asm/rmi_cmds.h>
+
+unsigned long rmm_feat_reg0;
+unsigned long rmm_feat_reg1;
+
+static int rmi_check_version(void)
+{
+	struct arm_smccc_res res;
+	unsigned short version_major, version_minor;
+	unsigned long host_version = RMI_ABI_VERSION(RMI_ABI_MAJOR_VERSION,
+						     RMI_ABI_MINOR_VERSION);
+	unsigned long aa64pfr0 = read_sanitised_ftr_reg(SYS_ID_AA64PFR0_EL1);
+
+	/* If RME isn't supported, then RMI can't be */
+	if (cpuid_feature_extract_unsigned_field(aa64pfr0, ID_AA64PFR0_EL1_RME_SHIFT) == 0)
+		return -ENXIO;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VERSION, host_version, &res);
+
+	if (res.a0 == SMCCC_RET_NOT_SUPPORTED)
+		return -ENXIO;
+
+	version_major = RMI_ABI_VERSION_GET_MAJOR(res.a1);
+	version_minor = RMI_ABI_VERSION_GET_MINOR(res.a1);
+
+	if (res.a0 != RMI_SUCCESS) {
+		unsigned short high_version_major, high_version_minor;
+
+		high_version_major = RMI_ABI_VERSION_GET_MAJOR(res.a2);
+		high_version_minor = RMI_ABI_VERSION_GET_MINOR(res.a2);
+
+		pr_err("Unsupported RMI ABI (v%d.%d - v%d.%d) we want v%d.%d\n",
+		       version_major, version_minor,
+		       high_version_major, high_version_minor,
+		       RMI_ABI_MAJOR_VERSION,
+		       RMI_ABI_MINOR_VERSION);
+		return -ENXIO;
+	}
+
+	pr_info("RMI ABI version %d.%d\n", version_major, version_minor);
+
+	return 0;
+}
+
+static int __init arm64_init_rmi(void)
+{
+	/* Continue without realm support if we can't agree on a version */
+	if (rmi_check_version())
+		return 0;
+
+	if (WARN_ON(rmi_features(0, &rmm_feat_reg0)))
+		return 0;
+	if (WARN_ON(rmi_features(1, &rmm_feat_reg1)))
+		return 0;
+
+	return 0;
+}
+subsys_initcall(arm64_init_rmi);

---

## [8] Steven Price — 2026-05-13
*Subject: [PATCH v14 07/44] arm64: RMI: Configure the RMM with the host's page size*

RMM v2.0 brings the ability to set the RMM's granule size. Check the
feature registers and configure the RMM so that it matches the host's
page size. This means that operations can be done with a granulatity
equal to PAGE_SIZE.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v13:
 * Moved out of KVM.
---
 arch/arm64/kernel/rmi.c | 42 +++++++++++++++++++++++++++++++++++++++++
 1 file changed, 42 insertions(+)

diff --git a/arch/arm64/kernel/rmi.c b/arch/arm64/kernel/rmi.c
index 99c1ccc35c11..a14ead5dedda 100644
--- a/arch/arm64/kernel/rmi.c
+++ b/arch/arm64/kernel/rmi.c
@@ -49,6 +49,45 @@ static int rmi_check_version(void)
 	return 0;
 }
 
+static int rmi_configure(void)
+{
+	struct rmm_config *config __free(free_page) = NULL;
+	unsigned long ret;
+
+	config = (struct rmm_config *)get_zeroed_page(GFP_KERNEL);
+	if (!config)
+		return -ENOMEM;
+
+	switch (PAGE_SIZE) {
+	case SZ_4K:
+		config->rmi_granule_size = RMI_GRANULE_SIZE_4KB;
+		break;
+	case SZ_16K:
+		config->rmi_granule_size = RMI_GRANULE_SIZE_16KB;
+		break;
+	case SZ_64K:
+		config->rmi_granule_size = RMI_GRANULE_SIZE_64KB;
+		break;
+	default:
+		pr_err("Unsupported PAGE_SIZE for RMM\n");
+		return -EINVAL;
+	}
+
+	ret = rmi_rmm_config_set(virt_to_phys(config));
+	if (ret) {
+		pr_err("RMM config set failed\n");
+		return -EINVAL;
+	}
+
+	ret = rmi_rmm_activate();
+	if (ret) {
+		pr_err("RMM activate failed\n");
+		return -ENXIO;
+	}
+
+	return 0;
+}
+
 static int __init arm64_init_rmi(void)
 {
 	/* Continue without realm support if we can't agree on a version */
@@ -60,6 +99,9 @@ static int __init arm64_init_rmi(void)
 	if (WARN_ON(rmi_features(1, &rmm_feat_reg1)))
 		return 0;
 
+	if (rmi_configure())
+		return 0;
+
 	return 0;
 }
 subsys_initcall(arm64_init_rmi);

---

## [9] Steven Price — 2026-05-13
*Subject: [PATCH v14 08/44] arm64: RMI: Ensure that the RMM has GPT entries for memory*

The RMM maintains the state of all the granules in the system to make
sure that the host is abiding by the rules. This state can be maintained
at different granularity, per page (TRACKING_FINE) or per region
(TRACKING_COARSE). The region size depends on the underlying
"RMI_GRANULE_SIZE". For a "coarse" region all pages in the region must
be of the same state, this implies we need to have "fine" tracking for
DRAM, so that we can delegated individual pages.

For now we only support a statically carved out memory for tracking
granules for the "fine" regions. This can be extended in the future to
allow modifying the tracking granularity and remove the need for a
static allocation.

Similarly, the firmware may create L0 GPT entries describing the total
address space. But if we change the "PAS" (Physical Address Space) of a
granule then the firmware may need to create L1 tables to track the PAS
at a finer granularity.

Note: support is currently missing for SROs which means that if the RMM
needs memory donating this will fail (and render CCA unusable in Linux).
This effectively means that the L1 GPT tables must be created before
Linux starts.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v13:
 * Moved out of KVM
---
 arch/arm64/include/asm/rmi_cmds.h |   2 +
 arch/arm64/kernel/rmi.c           | 103 ++++++++++++++++++++++++++++++
 2 files changed, 105 insertions(+)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 9179934925c5..9078a2920a7c 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -33,6 +33,8 @@ struct rmi_sro_state {
 } while (RMI_RETURN_STATUS(res.a0) == RMI_BUSY ||			\
 	 RMI_RETURN_STATUS(res.a0) == RMI_BLOCKED)
 
+bool rmi_is_available(void);
+
 unsigned long rmi_sro_execute(struct rmi_sro_state *sro, gfp_t gfp);
 void rmi_sro_free(struct rmi_sro_state *sro);
 
diff --git a/arch/arm64/kernel/rmi.c b/arch/arm64/kernel/rmi.c
index a14ead5dedda..52a415e99500 100644
--- a/arch/arm64/kernel/rmi.c
+++ b/arch/arm64/kernel/rmi.c
@@ -7,6 +7,8 @@
 
 #include <asm/rmi_cmds.h>
 
+static bool arm64_rmi_is_available;
+
 unsigned long rmm_feat_reg0;
 unsigned long rmm_feat_reg1;
 
@@ -88,6 +90,102 @@ static int rmi_configure(void)
 	return 0;
 }
 
+/*
+ * For now we set the tracking_region_size to 0 for RMI_RMM_CONFIG_SET().
+ * TODO: Support other tracking sizes (via Kconfig option).
+ */
+#ifdef CONFIG_PAGE_SIZE_4KB
+#define RMM_GRANULE_TRACKING_SIZE	SZ_1G
+#elif defined(CONFIG_PAGE_SIZE_16KB)
+#define RMM_GRANULE_TRACKING_SIZE	SZ_32M
+#elif defined(CONFIG_PAGE_SIZE_64KB)
+#define RMM_GRANULE_TRACKING_SIZE	SZ_512M
+#endif
+
+/*
+ * Make sure the area is tracked by RMM at FINE granularity.
+ * We do not support changing the tracking yet.
+ */
+static int rmi_verify_memory_tracking(phys_addr_t start, phys_addr_t end)
+{
+	while (start < end) {
+		unsigned long ret, category, state, next;
+
+		ret = rmi_granule_tracking_get(start, end, &category, &state, &next);
+		if (ret != RMI_SUCCESS ||
+		    state != RMI_TRACKING_FINE ||
+		    category != RMI_MEM_CATEGORY_CONVENTIONAL) {
+			/* TODO: Set granule tracking in this case */
+			pr_err("Granule tracking for region isn't fine/conventional: %llx",
+			       start);
+			return -ENODEV;
+		}
+		start = next;
+	}
+
+	return 0;
+}
+
+static unsigned long rmi_l0gpt_size(void)
+{
+	return 1UL << (30 + FIELD_GET(RMI_FEATURE_REGISTER_1_L0GPTSZ,
+				      rmm_feat_reg1));
+}
+
+static int rmi_create_gpts(phys_addr_t start, phys_addr_t end)
+{
+	unsigned long l0gpt_sz = rmi_l0gpt_size();
+
+	start = ALIGN_DOWN(start, l0gpt_sz);
+	end = ALIGN(end, l0gpt_sz);
+
+	while (start < end) {
+		int ret = rmi_gpt_l1_create(start);
+
+		/*
+		 * Make sure the L1 GPT tables are created for the region.
+		 * RMI_ERROR_GPT indicates the L1 table already exists.
+		 */
+		if (ret && ret != RMI_ERROR_GPT) {
+			/*
+			 * FIXME: Handle SRO so that memory can be donated for
+			 * the tables.
+			 */
+			pr_err("GPT Level1 table missing for %llx\n", start);
+			return -ENOMEM;
+		}
+		start += l0gpt_sz;
+	}
+
+	return 0;
+}
+
+static int rmi_init_metadata(void)
+{
+	phys_addr_t start, end;
+	const struct memblock_region *r;
+
+	for_each_mem_region(r) {
+		int ret;
+
+		start = memblock_region_memory_base_pfn(r) << PAGE_SHIFT;
+		end = memblock_region_memory_end_pfn(r) << PAGE_SHIFT;
+		ret = rmi_verify_memory_tracking(start, end);
+		if (ret)
+			return ret;
+		ret = rmi_create_gpts(start, end);
+		if (ret)
+			return ret;
+	}
+
+	return 0;
+}
+
+bool rmi_is_available(void)
+{
+	return arm64_rmi_is_available;
+}
+
 static int __init arm64_init_rmi(void)
 {
 	/* Continue without realm support if we can't agree on a version */
@@ -101,6 +199,11 @@ static int __init arm64_init_rmi(void)
 
 	if (rmi_configure())
 		return 0;
+	if (rmi_init_metadata())
+		return 0;
+
+	arm64_rmi_is_available = true;
+	pr_info("RMI configured");
 
 	return 0;
 }

---

## [10] Steven Price — 2026-05-13
*Subject: [PATCH v14 09/44] arm64: RMI: Provide functions to delegate/undelegate ranges of memory*

The RMM requires memory is 'delegated' to it so that it can be used
either for a realm guest or for various tracking purposes within the RMM
(e.g. for metadata or page tables). Memory that has been delegated
cannot be accessed by the host (it will result in a Granule Protection
Fault).

Undelegation may fail if the memory is still in use by the RMM. This
shouldn't happen (Linux should ensure it has destroyed the RMM objects
before attempting to undelegate). In the event that it does happen this
points to a programming bug and the only reasonable approach is for the
physical pages to be leaked - it is up to the caller of
rmi_undelegate_range() to handle this.

Signed-off-by: Steven Price <steven.price@arm.com>
---
v14:
 * Split into separate patch and moved out of KVM
---
 arch/arm64/include/asm/rmi_cmds.h | 13 +++++++++++
 arch/arm64/kernel/rmi.c           | 36 +++++++++++++++++++++++++++++++
 2 files changed, 49 insertions(+)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 9078a2920a7c..eb213c8e6f26 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -33,6 +33,19 @@ struct rmi_sro_state {
 } while (RMI_RETURN_STATUS(res.a0) == RMI_BUSY ||			\
 	 RMI_RETURN_STATUS(res.a0) == RMI_BLOCKED)
 
+int rmi_delegate_range(phys_addr_t phys, unsigned long size);
+int rmi_undelegate_range(phys_addr_t phys, unsigned long size);
+
+static inline int rmi_delegate_page(phys_addr_t phys)
+{
+	return rmi_delegate_range(phys, PAGE_SIZE);
+}
+
+static inline int rmi_undelegate_page(phys_addr_t phys)
+{
+	return rmi_undelegate_range(phys, PAGE_SIZE);
+}
+
 bool rmi_is_available(void);
 
 unsigned long rmi_sro_execute(struct rmi_sro_state *sro, gfp_t gfp);
diff --git a/arch/arm64/kernel/rmi.c b/arch/arm64/kernel/rmi.c
index 52a415e99500..08cef54acadb 100644
--- a/arch/arm64/kernel/rmi.c
+++ b/arch/arm64/kernel/rmi.c
@@ -12,6 +12,42 @@ static bool arm64_rmi_is_available;
 unsigned long rmm_feat_reg0;
 unsigned long rmm_feat_reg1;
 
+int rmi_delegate_range(phys_addr_t phys, unsigned long size)
+{
+	unsigned long ret = 0;
+	unsigned long top = phys + size;
+	unsigned long out_top;
+
+	while (phys < top) {
+		ret = rmi_granule_range_delegate(phys, top, &out_top);
+		if (ret == RMI_SUCCESS)
+			phys = out_top;
+		else if (ret != RMI_BUSY && ret != RMI_BLOCKED)
+			return ret;
+	}
+
+	return ret;
+}
+
+int rmi_undelegate_range(phys_addr_t phys, unsigned long size)
+{
+	unsigned long ret = 0;
+	unsigned long top = phys + size;
+	unsigned long out_top;
+
+	WARN_ON(size == 0);
+
+	while (phys < top) {
+		ret = rmi_granule_range_undelegate(phys, top, &out_top);
+		if (ret == RMI_SUCCESS)
+			phys = out_top;
+		else if (ret != RMI_BUSY && ret != RMI_BLOCKED)
+			return ret;
+	}
+
+	return ret;
+}
+
 static int rmi_check_version(void)
 {
 	struct arm_smccc_res res;

---

## [11] Steven Price — 2026-05-13
*Subject: [PATCH v14 10/44] arm64: RMI: Add support for SRO*

RMM v2.0 introduces the concept of "Stateful RMI Operations" (SRO). This
means that an SMC can return with an operation still in progress. The
host is excepted to continue the operation until is reaches a conclusion
(either success or failure). During this process the RMM can request
additional memory ('donate') or hand memory back to the host
('reclaim'). The host can request an in progress operation is cancelled,
but still continue the operation until it has completed (otherwise the
incomplete operation may cause future RMM operations to fail).

The SRO is tracked using a struct rmi_sro_state object which keeps track
of any memory which has been allocated but not yet consumed by the RMM
or reclaimed from the RMM. This allows the memory to be reused in a
future request within the same operation. It will also permit an
operation to be done in a context where memory allocation may be
difficult (e.g. atomic context) with the option to abort the operation
and retry the memory allocation outside of the atomic context. The
memory stored in the struct rmi_sro_state object can then be reused on
the subsequent attempt.

Signed-off-by: Steven Price <steven.price@arm.com>
---
v14:
 * SRO support has improved although is still not fully complete. The
   infrastructure has been moved out of KVM.
---
 arch/arm64/include/asm/rmi_cmds.h |   1 +
 arch/arm64/kernel/rmi.c           | 359 ++++++++++++++++++++++++++++++
 2 files changed, 360 insertions(+)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index eb213c8e6f26..1a7b0c8f1e38 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -35,6 +35,7 @@ struct rmi_sro_state {
 
 int rmi_delegate_range(phys_addr_t phys, unsigned long size);
 int rmi_undelegate_range(phys_addr_t phys, unsigned long size);
+int free_delegated_page(phys_addr_t phys);
 
 static inline int rmi_delegate_page(phys_addr_t phys)
 {
diff --git a/arch/arm64/kernel/rmi.c b/arch/arm64/kernel/rmi.c
index 08cef54acadb..a8107ca9bb6d 100644
--- a/arch/arm64/kernel/rmi.c
+++ b/arch/arm64/kernel/rmi.c
@@ -48,6 +48,365 @@ int rmi_undelegate_range(phys_addr_t phys, unsigned long size)
 	return ret;
 }
 
+static unsigned long donate_req_to_size(unsigned long donatereq)
+{
+	unsigned long unit_size = RMI_DONATE_SIZE(donatereq);
+
+	switch (unit_size) {
+	case 0:
+		return PAGE_SIZE;
+	case 1:
+		return PMD_SIZE;
+	case 2:
+		return PUD_SIZE;
+	case 3:
+		return P4D_SIZE;
+	}
+	unreachable();
+}
+
+static void rmi_smccc_invoke(struct arm_smccc_1_2_regs *regs_in,
+			     struct arm_smccc_1_2_regs *regs_out)
+{
+	struct arm_smccc_1_2_regs regs = *regs_in;
+	unsigned long status;
+
+	do {
+		arm_smccc_1_2_invoke(&regs, regs_out);
+		status = RMI_RETURN_STATUS(regs_out->a0);
+	} while (status == RMI_BUSY || status == RMI_BLOCKED);
+}
+
+int free_delegated_page(phys_addr_t phys)
+{
+	if (WARN_ON(rmi_undelegate_page(phys))) {
+		/* Undelegate failed: leak the page */
+		return -EBUSY;
+	}
+
+	free_page((unsigned long)phys_to_virt(phys));
+
+	return 0;
+}
+
+static int rmi_sro_ensure_capacity(struct rmi_sro_state *sro,
+				   unsigned long count)
+{
+	if (WARN_ON_ONCE(sro->addr_count > RMI_MAX_ADDR_LIST))
+		return -EOVERFLOW;
+
+	if (count > RMI_MAX_ADDR_LIST - sro->addr_count)
+		return -ENOSPC;
+
+	return 0;
+}
+
+static int rmi_sro_donate_contig(struct rmi_sro_state *sro,
+				 unsigned long sro_handle,
+				 unsigned long donatereq,
+				 struct arm_smccc_1_2_regs *out_regs,
+				 gfp_t gfp)
+{
+	unsigned long unit_size = RMI_DONATE_SIZE(donatereq);
+	unsigned long unit_size_bytes = donate_req_to_size(donatereq);
+	unsigned long count = RMI_DONATE_COUNT(donatereq);
+	unsigned long state = RMI_DONATE_STATE(donatereq);
+	unsigned long size = unit_size_bytes * count;
+	unsigned long addr_range;
+	int ret;
+	void *virt;
+	phys_addr_t phys;
+	struct arm_smccc_1_2_regs regs = {
+		SMC_RMI_OP_MEM_DONATE,
+		sro_handle
+	};
+
+	for (int i = 0; i < sro->addr_count; i++) {
+		unsigned long entry = sro->addr_list[i];
+
+		if (RMI_ADDR_RANGE_SIZE(entry) == unit_size &&
+		    RMI_ADDR_RANGE_COUNT(entry) == count &&
+		    RMI_ADDR_RANGE_STATE(entry) == state) {
+			sro->addr_count--;
+			swap(sro->addr_list[sro->addr_count],
+			     sro->addr_list[i]);
+
+			goto out;
+		}
+	}
+
+	ret = rmi_sro_ensure_capacity(sro, 1);
+	if (ret)
+		return ret;
+
+	virt = alloc_pages_exact(size, gfp);
+	if (!virt)
+		return -ENOMEM;
+	phys = virt_to_phys(virt);
+
+	if (state == RMI_OP_MEM_DELEGATED) {
+		if (rmi_delegate_range(phys, size)) {
+			free_pages_exact(virt, size);
+			return -ENXIO;
+		}
+	}
+
+	addr_range = phys & RMI_ADDR_RANGE_ADDR_MASK;
+	FIELD_MODIFY(RMI_ADDR_RANGE_SIZE_MASK, &addr_range, unit_size);
+	FIELD_MODIFY(RMI_ADDR_RANGE_COUNT_MASK, &addr_range, count);
+	FIELD_MODIFY(RMI_ADDR_RANGE_STATE_MASK, &addr_range, state);
+
+	sro->addr_list[sro->addr_count] = addr_range;
+
+out:
+	regs.a2 = virt_to_phys(&sro->addr_list[sro->addr_count]);
+	regs.a3 = 1;
+	rmi_smccc_invoke(&regs, out_regs);
+
+	unsigned long donated_granules = out_regs->a1;
+	unsigned long donated_size = donated_granules << PAGE_SHIFT;
+
+	if (donated_granules == 0) {
+		/* No pages used by the RMM */
+		sro->addr_count++;
+	} else if (donated_size < size) {
+		phys = sro->addr_list[sro->addr_count] & RMI_ADDR_RANGE_ADDR_MASK;
+
+		/* Not all granules used by the RMM, free the remaining pages */
+		for (long i = donated_size; i < size; i += PAGE_SIZE) {
+			if (state == RMI_OP_MEM_DELEGATED)
+				free_delegated_page(phys + i);
+			else
+				__free_page(phys_to_page(phys + i));
+		}
+	}
+
+	return 0;
+}
+
+static int rmi_sro_donate_noncontig(struct rmi_sro_state *sro,
+				    unsigned long sro_handle,
+				    unsigned long donatereq,
+				    struct arm_smccc_1_2_regs *out_regs,
+				    gfp_t gfp)
+{
+	unsigned long unit_size = RMI_DONATE_SIZE(donatereq);
+	unsigned long unit_size_bytes = donate_req_to_size(donatereq);
+	unsigned long count = RMI_DONATE_COUNT(donatereq);
+	unsigned long state = RMI_DONATE_STATE(donatereq);
+	unsigned long found = 0;
+	unsigned long addr_list_start = sro->addr_count;
+	int ret;
+	struct arm_smccc_1_2_regs regs = {
+		SMC_RMI_OP_MEM_DONATE,
+		sro_handle
+	};
+
+	for (int i = 0; i < addr_list_start && found < count; i++) {
+		unsigned long entry = sro->addr_list[i];
+
+		if (RMI_ADDR_RANGE_SIZE(entry) == unit_size &&
+		    RMI_ADDR_RANGE_COUNT(entry) == 1 &&
+		    RMI_ADDR_RANGE_STATE(entry) == state) {
+			addr_list_start--;
+			swap(sro->addr_list[addr_list_start],
+			     sro->addr_list[i]);
+			found++;
+			i--;
+		}
+	}
+
+	ret = rmi_sro_ensure_capacity(sro, count - found);
+	if (ret)
+		return ret;
+
+	while (found < count) {
+		unsigned long addr_range;
+		void *virt = alloc_pages_exact(unit_size_bytes, gfp);
+		phys_addr_t phys;
+
+		if (!virt)
+			return -ENOMEM;
+
+		phys = virt_to_phys(virt);
+
+		if (state == RMI_OP_MEM_DELEGATED) {
+			if (rmi_delegate_range(phys, unit_size_bytes)) {
+				free_pages_exact(virt, unit_size_bytes);
+				return -ENXIO;
+			}
+		}
+
+		addr_range = phys & RMI_ADDR_RANGE_ADDR_MASK;
+		FIELD_MODIFY(RMI_ADDR_RANGE_SIZE_MASK, &addr_range, unit_size);
+		FIELD_MODIFY(RMI_ADDR_RANGE_COUNT_MASK, &addr_range, 1);
+		FIELD_MODIFY(RMI_ADDR_RANGE_STATE_MASK, &addr_range, state);
+
+		sro->addr_list[sro->addr_count++] = addr_range;
+		found++;
+	}
+
+	regs.a2 = virt_to_phys(&sro->addr_list[addr_list_start]);
+	regs.a3 = found;
+	rmi_smccc_invoke(&regs, out_regs);
+
+	unsigned long donated_granules = out_regs->a1;
+
+	if (WARN_ON(donated_granules & ((unit_size_bytes >> PAGE_SHIFT) - 1))) {
+		/*
+		 * FIXME: RMM has only consumed part of a huge page, this leaks
+		 * the rest of the huge page
+		 */
+		donated_granules = ALIGN(donated_granules,
+					 (unit_size_bytes >> PAGE_SHIFT));
+	}
+	unsigned long donated_blocks = donated_granules / (unit_size_bytes >> PAGE_SHIFT);
+
+	if (WARN_ON(donated_blocks > found))
+		donated_blocks = found;
+
+	unsigned long undonated_blocks = found - donated_blocks;
+
+	while (donated_blocks && undonated_blocks) {
+		sro->addr_count--;
+		swap(sro->addr_list[addr_list_start],
+		     sro->addr_list[sro->addr_count]);
+		addr_list_start++;
+
+		donated_blocks--;
+		undonated_blocks--;
+	}
+	sro->addr_count -= donated_blocks;
+
+	return 0;
+}
+
+static int rmi_sro_donate(struct rmi_sro_state *sro,
+			  unsigned long sro_handle,
+			  unsigned long donatereq,
+			  struct arm_smccc_1_2_regs *regs,
+			  gfp_t gfp)
+{
+	unsigned long count = RMI_DONATE_COUNT(donatereq);
+
+	if (WARN_ON(!count))
+		return 0;
+
+	if (RMI_DONATE_CONTIG(donatereq)) {
+		return rmi_sro_donate_contig(sro, sro_handle, donatereq,
+					     regs, gfp);
+	} else {
+		return rmi_sro_donate_noncontig(sro, sro_handle, donatereq,
+						regs, gfp);
+	}
+}
+
+static int rmi_sro_reclaim(struct rmi_sro_state *sro,
+			   unsigned long sro_handle,
+			   struct arm_smccc_1_2_regs *out_regs)
+{
+	unsigned long capacity;
+	struct arm_smccc_1_2_regs regs;
+	int ret;
+
+	ret = rmi_sro_ensure_capacity(sro, 1);
+	if (ret)
+		rmi_sro_free(sro);
+
+	capacity = RMI_MAX_ADDR_LIST - sro->addr_count;
+
+	regs = (struct arm_smccc_1_2_regs){
+		SMC_RMI_OP_MEM_RECLAIM,
+		sro_handle,
+		virt_to_phys(&sro->addr_list[sro->addr_count]),
+		capacity
+	};
+	rmi_smccc_invoke(&regs, out_regs);
+
+	if (WARN_ON_ONCE(out_regs->a1 > capacity))
+		out_regs->a1 = capacity;
+
+	sro->addr_count += out_regs->a1;
+
+	return 0;
+}
+
+void rmi_sro_free(struct rmi_sro_state *sro)
+{
+	for (int i = 0; i < sro->addr_count; i++) {
+		unsigned long entry = sro->addr_list[i];
+		unsigned long addr = RMI_ADDR_RANGE_ADDR(entry);
+		unsigned long unit_size = RMI_ADDR_RANGE_SIZE(entry);
+		unsigned long count = RMI_ADDR_RANGE_COUNT(entry);
+		unsigned long state = RMI_ADDR_RANGE_STATE(entry);
+		unsigned long size = donate_req_to_size(unit_size) * count;
+
+		if (state == RMI_OP_MEM_DELEGATED) {
+			if (WARN_ON(rmi_undelegate_range(addr, size))) {
+				/* Leak the pages */
+				continue;
+			}
+		}
+		free_pages_exact(phys_to_virt(addr), size);
+	}
+
+	sro->addr_count = 0;
+}
+
+unsigned long rmi_sro_execute(struct rmi_sro_state *sro, gfp_t gfp)
+{
+	unsigned long sro_handle;
+	struct arm_smccc_1_2_regs regs;
+	struct arm_smccc_1_2_regs *regs_in = &sro->regs;
+
+	rmi_smccc_invoke(regs_in, &regs);
+
+	sro_handle = regs.a1;
+
+	while (RMI_RETURN_STATUS(regs.a0) == RMI_INCOMPLETE) {
+		bool can_cancel = RMI_RETURN_CAN_CANCEL(regs.a0);
+		int ret;
+
+		switch (RMI_RETURN_MEMREQ(regs.a0)) {
+		case RMI_OP_MEM_REQ_NONE:
+			regs = (struct arm_smccc_1_2_regs){
+				SMC_RMI_OP_CONTINUE, sro_handle, 0
+			};
+			rmi_smccc_invoke(&regs, &regs);
+			break;
+		case RMI_OP_MEM_REQ_DONATE:
+			ret = rmi_sro_donate(sro, sro_handle, regs.a2, &regs,
+					     gfp);
+			break;
+		case RMI_OP_MEM_REQ_RECLAIM:
+			ret = rmi_sro_reclaim(sro, sro_handle, &regs);
+			break;
+		default:
+			ret = WARN_ON(1);
+			break;
+		}
+
+		if (ret) {
+			if (can_cancel) {
+				/*
+				 * FIXME: Handle cancelling properly!
+				 *
+				 * If the operation has failed due to memory
+				 * allocation failure then the information on
+				 * the memory allocation should be saved, so
+				 * that the allocation can be repeated outside
+				 * of any context which prevented the
+				 * allocation.
+				 */
+			}
+			if (WARN_ON(ret))
+				return ret;
+		}
+	}
+
+	return regs.a0;
+}
+
 static int rmi_check_version(void)
 {
 	struct arm_smccc_res res;

---

## [12] Steven Price — 2026-05-13
*Subject: [PATCH v14 11/44] arm64: RMI: Check for RMI support at KVM init*

Check if the RMI support is sufficient for using in KVM. Specifically we
currently only support KVM in VHE mode when for creating realm VMs.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v13:
 * Most of the init has been moved out of the 'kvm' directory so this is
   much more basic now.
Changes since v12:
 * Drop check for 4k page size.
Changes since v11:
 * Reword slightly the comments on the realm states.
Changes since v10:
 * kvm_is_realm() no longer has a NULL check.
 * Rename from "rme" to "rmi" when referring to the RMM interface.
 * Check for RME (hardware) support before probing for RMI support.
Changes since v8:
 * No need to guard kvm_init_rme() behind 'in_hyp_mode'.
Changes since v6:
 * Improved message for an unsupported RMI ABI version.
Changes since v5:
 * Reword "unsupported" message from "host supports" to "we want" to
   clarify that 'we' are the 'host'.
Changes since v2:
 * Drop return value from kvm_init_rme(), it was always 0.
 * Rely on the RMM return value to identify whether the RSI ABI is
   compatible.
---
 arch/arm64/include/asm/kvm_host.h |  4 ++++
 arch/arm64/include/asm/kvm_rmi.h  | 17 +++++++++++++++++
 arch/arm64/include/asm/virt.h     |  1 +
 arch/arm64/kvm/Makefile           |  2 +-
 arch/arm64/kvm/arm.c              |  5 +++++
 arch/arm64/kvm/rmi.c              | 24 ++++++++++++++++++++++++
 6 files changed, 52 insertions(+), 1 deletion(-)
 create mode 100644 arch/arm64/include/asm/kvm_rmi.h
 create mode 100644 arch/arm64/kvm/rmi.c

diff --git a/arch/arm64/include/asm/kvm_host.h b/arch/arm64/include/asm/kvm_host.h
index 851f6171751c..3512696ed506 100644
--- a/arch/arm64/include/asm/kvm_host.h
+++ b/arch/arm64/include/asm/kvm_host.h
@@ -27,6 +27,7 @@
 #include <asm/fpsimd.h>
 #include <asm/kvm.h>
 #include <asm/kvm_asm.h>
+#include <asm/kvm_rmi.h>
 #include <asm/vncr_mapping.h>
 
 #define __KVM_HAVE_ARCH_INTC_INITIALIZED
@@ -424,6 +425,9 @@ struct kvm_arch {
 	/* Nested virtualization info */
 	struct dentry *debugfs_nv_dentry;
 #endif
+
+	bool is_realm;
+	struct realm realm;
 };
 
 struct kvm_vcpu_fault_info {
diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
new file mode 100644
index 000000000000..4936007947fd
--- /dev/null
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -0,0 +1,17 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+/*
+ * Copyright (C) 2023-2025 ARM Ltd.
+ */
+
+#ifndef __ASM_KVM_RMI_H
+#define __ASM_KVM_RMI_H
+
+/**
+ * struct realm - Additional per VM data for a Realm
+ */
+struct realm {
+};
+
+void kvm_init_rmi(void);
+
+#endif /* __ASM_KVM_RMI_H */
diff --git a/arch/arm64/include/asm/virt.h b/arch/arm64/include/asm/virt.h
index b546703c3ab9..92cec42952f4 100644
--- a/arch/arm64/include/asm/virt.h
+++ b/arch/arm64/include/asm/virt.h
@@ -87,6 +87,7 @@ void __hyp_reset_vectors(void);
 bool is_kvm_arm_initialised(void);
 
 DECLARE_STATIC_KEY_FALSE(kvm_protected_mode_initialized);
+DECLARE_STATIC_KEY_FALSE(kvm_rmi_is_available);
 
 static inline bool is_pkvm_initialized(void)
 {
diff --git a/arch/arm64/kvm/Makefile b/arch/arm64/kvm/Makefile
index 59612d2f277c..ed3cf30eb06e 100644
--- a/arch/arm64/kvm/Makefile
+++ b/arch/arm64/kvm/Makefile
@@ -16,7 +16,7 @@ CFLAGS_handle_exit.o += -Wno-override-init
 kvm-y += arm.o mmu.o mmio.o psci.o hypercalls.o pvtime.o \
 	 inject_fault.o va_layout.o handle_exit.o config.o \
 	 guest.o debug.o reset.o sys_regs.o stacktrace.o \
-	 vgic-sys-reg-v3.o fpsimd.o pkvm.o \
+	 vgic-sys-reg-v3.o fpsimd.o pkvm.o rmi.o \
 	 arch_timer.o trng.o vmid.o emulate-nested.o nested.o at.o \
 	 vgic/vgic.o vgic/vgic-init.o \
 	 vgic/vgic-irqfd.o vgic/vgic-v2.o \
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 176cbe8baad3..247e03b33035 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -41,6 +41,7 @@
 #include <asm/kvm_nested.h>
 #include <asm/kvm_pkvm.h>
 #include <asm/kvm_ptrauth.h>
+#include <asm/kvm_rmi.h>
 #include <asm/sections.h>
 #include <asm/stacktrace/nvhe.h>
 
@@ -109,6 +110,8 @@ long kvm_get_cap_for_kvm_ioctl(unsigned int ioctl, long *ext)
 	return -EINVAL;
 }
 
+DEFINE_STATIC_KEY_FALSE(kvm_rmi_is_available);
+
 DECLARE_KVM_HYP_PER_CPU(unsigned long, kvm_hyp_vector);
 
 DEFINE_PER_CPU(unsigned long, kvm_arm_hyp_stack_base);
@@ -2975,6 +2978,8 @@ static __init int kvm_arm_init(void)
 
 	in_hyp_mode = is_kernel_in_hyp_mode();
 
+	kvm_init_rmi();
+
 	if (cpus_have_final_cap(ARM64_WORKAROUND_DEVICE_LOAD_ACQUIRE) ||
 	    cpus_have_final_cap(ARM64_WORKAROUND_1508412))
 		kvm_info("Guests without required CPU erratum workarounds can deadlock system!\n" \
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
new file mode 100644
index 000000000000..1acc972a4b92
--- /dev/null
+++ b/arch/arm64/kvm/rmi.c
@@ -0,0 +1,24 @@
+// SPDX-License-Identifier: GPL-2.0
+/*
+ * Copyright (C) 2023-2025 ARM Ltd.
+ */
+
+#include <linux/kvm_host.h>
+
+#include <asm/rmi_cmds.h>
+#include <asm/virt.h>
+
+void kvm_init_rmi(void)
+{
+	/*
+	 * TODO: Support Realm guests in nVHE mode, this will require adding
+	 * EL2 stub(s) for REC entry and possibly other things.
+	 */
+	if (!is_kernel_in_hyp_mode())
+		return;
+
+	if (!rmi_is_available())
+		return;
+
+	/* Future patch will enable static branch kvm_rmi_is_available */
+}

---

## [13] Steven Price — 2026-05-13
*Subject: [PATCH v14 12/44] arm64: RMI: Check for LPA2 support*

If KVM has enabled LPA2 support then check that the RMM also supports
it. If there is a mismatch then disable support for realm guests as the
VMM may attempt to create a guest which is incompatible with the RMM.

Signed-off-by: Steven Price <steven.price@arm.com>
---
New patch for v13
---
 arch/arm64/kvm/rmi.c | 19 +++++++++++++++++++
 1 file changed, 19 insertions(+)

diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 1acc972a4b92..6e28b669ded2 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -5,9 +5,25 @@
 
 #include <linux/kvm_host.h>
 
+#include <asm/kvm_pgtable.h>
 #include <asm/rmi_cmds.h>
 #include <asm/virt.h>
 
+static bool rmi_has_feature(unsigned long feature)
+{
+	return !!u64_get_bits(rmm_feat_reg0, feature);
+}
+
+static int rmm_check_features(void)
+{
+	if (kvm_lpa2_is_enabled() && !rmi_has_feature(RMI_FEATURE_REGISTER_0_LPA2)) {
+		kvm_err("RMM doesn't support LPA2");
+		return -ENXIO;
+	}
+
+	return 0;
+}
+
 void kvm_init_rmi(void)
 {
 	/*
@@ -20,5 +36,8 @@ void kvm_init_rmi(void)
 	if (!rmi_is_available())
 		return;
 
+	if (rmm_check_features())
+		return;
+
 	/* Future patch will enable static branch kvm_rmi_is_available */
 }

---

## [14] Steven Price — 2026-05-13
*Subject: [PATCH v14 13/44] arm64: RMI: Define the user ABI*

There is one CAP which identified the presence of CCA, and one ioctl.
The ioctl is used to populate memory during creation of the realm as
this requires the RMM to copy data from an unprotected address to the
protected memory - CCA does not support memory conversion where the
memory contents is preserved as this is incompatible with memory
encryption.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v13:
 * KVM_ARM_VCPU_RMI_PSCI_COMPLETE removed.
 * KVM_ARM_RMI_POPULATE documentation updated to reflect that the
   structure is written by the kernel.
 * CAP number bumped.
Changes since v12:
 * Change KVM_ARM_RMI_POPULATE to update the structure with the amount
   that has been progressed rather than return the number of bytes
   populated.
 * Describe the flag KVM_ARM_RMI_POPULATE_FLAGS_MEASURE.
 * CAP number is bumped.
 * NOTE: The PSCI ioctl may be removed in a future spec release.
Changes since v11:
 * Completely reworked to be more implicit. Rather than having explicit
   CAP operations to progress the realm construction these operations
   are done when needed (on populating and on first vCPU run).
 * Populate and PSCI complete are promoted to proper ioctls.
Changes since v10:
 * Rename symbols from RME to RMI.
Changes since v9:
 * Improvements to documentation.
 * Bump the magic number for KVM_CAP_ARM_RME to avoid conflicts.
Changes since v8:
 * Minor improvements to documentation following review.
 * Bump the magic numbers to avoid conflicts.
Changes since v7:
 * Add documentation of new ioctls
 * Bump the magic numbers to avoid conflicts
Changes since v6:
 * Rename some of the symbols to make their usage clearer and avoid
   repetition.
Changes from v5:
 * Actually expose the new VCPU capability (KVM_ARM_VCPU_REC) by bumping
   KVM_VCPU_MAX_FEATURES - note this also exposes KVM_ARM_VCPU_HAS_EL2!
---
 Documentation/virt/kvm/api.rst | 40 ++++++++++++++++++++++++++++++++++
 include/uapi/linux/kvm.h       | 13 +++++++++++
 2 files changed, 53 insertions(+)

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index 52bbbb553ce1..ca68aae7faa2 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -6553,6 +6553,37 @@ KVM_S390_KEYOP_SSKE
   Sets the storage key for the guest address ``guest_addr`` to the key
   specified in ``key``, returning the previous value in ``key``.
 
+4.145 KVM_ARM_RMI_POPULATE
+--------------------------
+
+:Capability: KVM_CAP_ARM_RMI
+:Architectures: arm64
+:Type: vm ioctl
+:Parameters: struct kvm_arm_rmi_populate (in/out)
+:Returns: 0 on success, < 0 on error
+
+::
+
+  struct kvm_arm_rmi_populate {
+	__u64 base;
+	__u64 size;
+	__u64 source_uaddr;
+	__u32 flags;
+	__u32 reserved;
+  };
+
+Populate a region of protected address space by copying the data from the
+(non-protected) user space pointer provided into a protected region (backed by
+guestmem_fd). It implicitly sets the destination region to RIPAS RAM. This is
+only valid before any VCPUs have been run. The ioctl might not populate the
+entire region and in this case the kernel updates the fields `base`, `size` and
+`source_uaddr`. User space may have to repeatedly call it until `size` is 0 to
+populate the entire region.
+
+`flags` can be set to `KVM_ARM_RMI_POPULATE_FLAGS_MEASURE` to request that the
+populated data is hashed and added to the guest's Realm Initial Measurement
+(RIM).
+
 .. _kvm_run:
 
 5. The kvm_run structure
@@ -8904,6 +8935,15 @@ helpful if user space wants to emulate instructions which are not
 This capability can be enabled dynamically even if VCPUs were already
 created and are running.
 
+7.47 KVM_CAP_ARM_RMI
+--------------------
+
+:Architectures: arm64
+:Target: VM
+:Parameters: None
+
+This capability indicates that support for CCA realms is available.
+
 8. Other capabilities.
 ======================
 
diff --git a/include/uapi/linux/kvm.h b/include/uapi/linux/kvm.h
index 6c8afa2047bf..b8cff0938041 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -996,6 +996,7 @@ struct kvm_enable_cap {
 #define KVM_CAP_S390_USER_OPEREXEC 246
 #define KVM_CAP_S390_KEYOP 247
 #define KVM_CAP_S390_VSIE_ESAMODE 248
+#define KVM_CAP_ARM_RMI 249
 
 struct kvm_irq_routing_irqchip {
 	__u32 irqchip;
@@ -1669,4 +1670,16 @@ struct kvm_pre_fault_memory {
 	__u64 padding[5];
 };
 
+/* Available with KVM_CAP_ARM_RMI, only for VMs with KVM_VM_TYPE_ARM_REALM */
+#define KVM_ARM_RMI_POPULATE	_IOWR(KVMIO, 0xd7, struct kvm_arm_rmi_populate)
+#define KVM_ARM_RMI_POPULATE_FLAGS_MEASURE	(1 << 0)
+
+struct kvm_arm_rmi_populate {
+	__u64 base;
+	__u64 size;
+	__u64 source_uaddr;
+	__u32 flags;
+	__u32 reserved;
+};
+
 #endif /* __LINUX_KVM_H */

---

## [15] Steven Price — 2026-05-13
*Subject: [PATCH v14 14/44] arm64: RMI: Basic infrastructure for creating a realm.*

Introduce the skeleton functions for creating and destroying a realm.
The IPA size requested is checked against what the RMM supports.

The actual work of constructing the realm will be added in future
patches.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v13:
 * Rebased and updated to RMM-v2.0-bet1.
 * Auxiliary granules have been removed in RMM-v2.0-bet1
Changes since v12:
 * Drop the RMM_PAGE_{SHIFT,SIZE} defines - the RMM is now configured to
   be the same as the host's page size.
 * Rework delegate/undelegate functions to use the new RMI range based
   operations.
Changes since v11:
 * Major rework to drop the realm configuration and make the
   construction of realms implicit rather than driven by the VMM
   directly.
 * The code to create RDs, handle VMIDs etc is moved to later patches.
Changes since v10:
 * Rename from RME to RMI.
 * Move the stage2 cleanup to a later patch.
Changes since v9:
 * Avoid walking the stage 2 page tables when destroying the realm -
   the real ones are not accessible to the non-secure world, and the RMM
   may leave junk in the physical pages when returning them.
 * Fix an error path in realm_create_rd() to actually return an error value.
Changes since v8:
 * Fix free_delegated_granule() to not call kvm_account_pgtable_pages();
   a separate wrapper will be introduced in a later patch to deal with
   RTTs.
 * Minor code cleanups following review.
Changes since v7:
 * Minor code cleanup following Gavin's review.
Changes since v6:
 * Separate RMM RTT calculations from host PAGE_SIZE. This allows the
   host page size to be larger than 4k while still communicating with an
   RMM which uses 4k granules.
Changes since v5:
 * Introduce free_delegated_granule() to replace many
   undelegate/free_page() instances and centralise the comment on
   leaking when the undelegate fails.
 * Several other minor improvements suggested by reviews - thanks for
   the feedback!
Changes since v2:
 * Improved commit description.
 * Improved return failures for rmi_check_version().
 * Clear contents of PGD after it has been undelegated in case the RMM
   left stale data.
 * Minor changes to reflect changes in previous patches.
---
 arch/arm64/include/asm/kvm_emulate.h | 29 ++++++++++++++
 arch/arm64/include/asm/kvm_rmi.h     | 51 +++++++++++++++++++++++++
 arch/arm64/kvm/arm.c                 | 12 ++++++
 arch/arm64/kvm/mmu.c                 | 12 +++++-
 arch/arm64/kvm/rmi.c                 | 57 ++++++++++++++++++++++++++++
 5 files changed, 159 insertions(+), 2 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_emulate.h b/arch/arm64/include/asm/kvm_emulate.h
index 5bf3d7e1d92c..82fd777bd9bb 100644
--- a/arch/arm64/include/asm/kvm_emulate.h
+++ b/arch/arm64/include/asm/kvm_emulate.h
@@ -688,4 +688,33 @@ static inline void vcpu_set_hcrx(struct kvm_vcpu *vcpu)
 			vcpu->arch.hcrx_el2 |= HCRX_EL2_EnASR;
 	}
 }
+
+static inline bool kvm_is_realm(struct kvm *kvm)
+{
+	if (static_branch_unlikely(&kvm_rmi_is_available))
+		return kvm->arch.is_realm;
+	return false;
+}
+
+static inline enum realm_state kvm_realm_state(struct kvm *kvm)
+{
+	return READ_ONCE(kvm->arch.realm.state);
+}
+
+static inline void kvm_set_realm_state(struct kvm *kvm,
+				       enum realm_state new_state)
+{
+	WRITE_ONCE(kvm->arch.realm.state, new_state);
+}
+
+static inline bool kvm_realm_is_created(struct kvm *kvm)
+{
+	return kvm_is_realm(kvm) && kvm_realm_state(kvm) != REALM_STATE_NONE;
+}
+
+static inline bool vcpu_is_rec(const struct kvm_vcpu *vcpu)
+{
+	return false;
+}
+
 #endif /* __ARM64_KVM_EMULATE_H__ */
diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index 4936007947fd..9de34983ee52 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -6,12 +6,63 @@
 #ifndef __ASM_KVM_RMI_H
 #define __ASM_KVM_RMI_H
 
+#include <asm/rmi_smc.h>
+
+/**
+ * enum realm_state - State of a Realm
+ */
+enum realm_state {
+	/**
+	 * @REALM_STATE_NONE:
+	 *      Realm has not yet been created. rmi_realm_create() has not
+	 *      yet been called.
+	 */
+	REALM_STATE_NONE,
+	/**
+	 * @REALM_STATE_NEW:
+	 *      Realm is under construction, rmi_realm_create() has been
+	 *      called, but it is not yet activated. Pages may be populated.
+	 */
+	REALM_STATE_NEW,
+	/**
+	 * @REALM_STATE_ACTIVE:
+	 *      Realm has been created and is eligible for execution with
+	 *      rmi_rec_enter(). Pages may no longer be populated with
+	 *      rmi_data_create().
+	 */
+	REALM_STATE_ACTIVE,
+	/**
+	 * @REALM_STATE_DYING:
+	 *      Realm is in the process of being destroyed or has already been
+	 *      destroyed.
+	 */
+	REALM_STATE_DYING,
+	/**
+	 * @REALM_STATE_DEAD:
+	 *      Realm has been destroyed.
+	 */
+	REALM_STATE_DEAD
+};
+
 /**
  * struct realm - Additional per VM data for a Realm
+ *
+ * @state: The lifetime state machine for the realm
+ * @rd: Kernel mapping of the Realm Descriptor (RD)
+ * @params: Parameters for the RMI_REALM_CREATE command
+ * @ia_bits: Number of valid Input Address bits in the IPA
  */
 struct realm {
+	enum realm_state state;
+	void *rd;
+	struct realm_params *params;
+	unsigned int ia_bits;
 };
 
 void kvm_init_rmi(void);
+u32 kvm_realm_ipa_limit(void);
+
+int kvm_init_realm(struct kvm *kvm);
+void kvm_destroy_realm(struct kvm *kvm);
 
 #endif /* __ASM_KVM_RMI_H */
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 247e03b33035..18251e561524 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -264,6 +264,13 @@ int kvm_arch_init_vm(struct kvm *kvm, unsigned long type)
 
 	bitmap_zero(kvm->arch.vcpu_features, KVM_VCPU_MAX_FEATURES);
 
+	/* Initialise the realm bits after the generic bits are enabled */
+	if (kvm_is_realm(kvm)) {
+		ret = kvm_init_realm(kvm);
+		if (ret)
+			goto err_uninit_mmu;
+	}
+
 	return 0;
 
 err_uninit_mmu:
@@ -326,6 +333,8 @@ void kvm_arch_destroy_vm(struct kvm *kvm)
 	kvm_unshare_hyp(kvm, kvm + 1);
 
 	kvm_arm_teardown_hypercalls(kvm);
+	if (kvm_is_realm(kvm))
+		kvm_destroy_realm(kvm);
 }
 
 static bool kvm_has_full_ptr_auth(void)
@@ -486,6 +495,9 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 		else
 			r = kvm_supports_cacheable_pfnmap();
 		break;
+	case KVM_CAP_ARM_RMI:
+		r = static_key_enabled(&kvm_rmi_is_available);
+		break;
 
 	default:
 		r = 0;
diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index d089c107d9b7..ba8286472286 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -877,10 +877,14 @@ static struct kvm_pgtable_mm_ops kvm_s2_mm_ops = {
 
 static int kvm_init_ipa_range(struct kvm_s2_mmu *mmu, unsigned long type)
 {
+	struct kvm *kvm = kvm_s2_mmu_to_kvm(mmu);
 	u32 kvm_ipa_limit = get_kvm_ipa_limit();
 	u64 mmfr0, mmfr1;
 	u32 phys_shift;
 
+	if (kvm_is_realm(kvm))
+		kvm_ipa_limit = kvm_realm_ipa_limit();
+
 	phys_shift = KVM_VM_TYPE_ARM_IPA_SIZE(type);
 	if (is_protected_kvm_enabled()) {
 		phys_shift = kvm_ipa_limit;
@@ -974,6 +978,8 @@ int kvm_init_stage2_mmu(struct kvm *kvm, struct kvm_s2_mmu *mmu, unsigned long t
 		return -EINVAL;
 	}
 
+	mmu->arch = &kvm->arch;
+
 	err = kvm_init_ipa_range(mmu, type);
 	if (err)
 		return err;
@@ -982,7 +988,6 @@ int kvm_init_stage2_mmu(struct kvm *kvm, struct kvm_s2_mmu *mmu, unsigned long t
 	if (!pgt)
 		return -ENOMEM;
 
-	mmu->arch = &kvm->arch;
 	err = KVM_PGT_FN(kvm_pgtable_stage2_init)(pgt, mmu, &kvm_s2_mm_ops);
 	if (err)
 		goto out_free_pgtable;
@@ -1114,7 +1119,10 @@ void kvm_free_stage2_pgd(struct kvm_s2_mmu *mmu)
 	write_unlock(&kvm->mmu_lock);
 
 	if (pgt) {
-		kvm_stage2_destroy(pgt);
+		if (!kvm_is_realm(kvm))
+			kvm_stage2_destroy(pgt);
+		else
+			kvm_pgtable_stage2_destroy_pgd(pgt);
 		kfree(pgt);
 	}
 }
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 6e28b669ded2..f51ec667445e 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -5,6 +5,8 @@
 
 #include <linux/kvm_host.h>
 
+#include <asm/kvm_emulate.h>
+#include <asm/kvm_mmu.h>
 #include <asm/kvm_pgtable.h>
 #include <asm/rmi_cmds.h>
 #include <asm/virt.h>
@@ -14,6 +16,61 @@ static bool rmi_has_feature(unsigned long feature)
 	return !!u64_get_bits(rmm_feat_reg0, feature);
 }
 
+u32 kvm_realm_ipa_limit(void)
+{
+	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_S2SZ);
+}
+
+void kvm_destroy_realm(struct kvm *kvm)
+{
+	struct realm *realm = &kvm->arch.realm;
+	size_t pgd_size = kvm_pgtable_stage2_pgd_size(kvm->arch.mmu.vtcr);
+
+	if (realm->params) {
+		free_page((unsigned long)realm->params);
+		realm->params = NULL;
+	}
+
+	if (!kvm_realm_is_created(kvm))
+		return;
+
+	kvm_set_realm_state(kvm, REALM_STATE_DYING);
+
+	write_lock(&kvm->mmu_lock);
+	kvm_stage2_unmap_range(&kvm->arch.mmu, 0,
+			       BIT(realm->ia_bits - 1), true);
+	write_unlock(&kvm->mmu_lock);
+
+	if (realm->rd) {
+		phys_addr_t rd_phys = virt_to_phys(realm->rd);
+
+		if (WARN_ON(rmi_realm_terminate(rd_phys)))
+			return;
+
+		if (WARN_ON(rmi_realm_destroy(rd_phys)))
+			return;
+		free_delegated_page(rd_phys);
+		realm->rd = NULL;
+	}
+
+	if (WARN_ON(rmi_undelegate_range(kvm->arch.mmu.pgd_phys, pgd_size)))
+		return;
+
+	kvm_set_realm_state(kvm, REALM_STATE_DEAD);
+
+	/* Now that the Realm is destroyed, free the entry level RTTs */
+	kvm_free_stage2_pgd(&kvm->arch.mmu);
+}
+
+int kvm_init_realm(struct kvm *kvm)
+{
+	kvm->arch.realm.params = (void *)get_zeroed_page(GFP_KERNEL_ACCOUNT);
+
+	if (!kvm->arch.realm.params)
+		return -ENOMEM;
+	return 0;
+}
+
 static int rmm_check_features(void)
 {
 	if (kvm_lpa2_is_enabled() && !rmi_has_feature(RMI_FEATURE_REGISTER_0_LPA2)) {

---

## [16] Steven Price — 2026-05-13
*Subject: [PATCH v14 15/44] kvm: arm64: Don't expose unsupported capabilities for realm guests*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

RMM v2.0 provides no mechanism for the host to perform debug operations
on the guest. So limit the extensions that are visible to an allowlist
so that only those capabilities we can support are advertised.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v13:
 * Add missing check in kvm_vm_ioctl_enable_cap().
Changes since v10:
 * Add a kvm_realm_ext_allowed() function which limits which extensions
   are exposed to an allowlist. This removes the need for special casing
   various extensions.
Changes since v7:
 * Remove the helper functions and inline the kvm_is_realm() check with
   a ternary operator.
 * Rewrite the commit message to explain this patch.
---
 arch/arm64/kvm/arm.c | 25 +++++++++++++++++++++++++
 1 file changed, 25 insertions(+)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 18251e561524..c6ebc5913e40 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -133,6 +133,25 @@ int kvm_arch_vcpu_should_kick(struct kvm_vcpu *vcpu)
 	return kvm_vcpu_exiting_guest_mode(vcpu) == IN_GUEST_MODE;
 }
 
+static bool kvm_realm_ext_allowed(long ext)
+{
+	switch (ext) {
+	case KVM_CAP_IRQCHIP:
+	case KVM_CAP_ARM_PSCI:
+	case KVM_CAP_ARM_PSCI_0_2:
+	case KVM_CAP_NR_VCPUS:
+	case KVM_CAP_MAX_VCPUS:
+	case KVM_CAP_MAX_VCPU_ID:
+	case KVM_CAP_MSI_DEVID:
+	case KVM_CAP_ARM_VM_IPA_SIZE:
+	case KVM_CAP_ARM_PTRAUTH_ADDRESS:
+	case KVM_CAP_ARM_PTRAUTH_GENERIC:
+	case KVM_CAP_ARM_RMI:
+		return true;
+	}
+	return false;
+}
+
 int kvm_vm_ioctl_enable_cap(struct kvm *kvm,
 			    struct kvm_enable_cap *cap)
 {
@@ -144,6 +163,9 @@ int kvm_vm_ioctl_enable_cap(struct kvm *kvm,
 	if (is_protected_kvm_enabled() && !kvm_pkvm_ext_allowed(kvm, cap->cap))
 		return -EINVAL;
 
+	if (kvm && kvm_is_realm(kvm) && !kvm_realm_ext_allowed(cap->cap))
+		return -EINVAL;
+
 	switch (cap->cap) {
 	case KVM_CAP_ARM_NISV_TO_USER:
 		r = 0;
@@ -378,6 +400,9 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 	if (is_protected_kvm_enabled() && !kvm_pkvm_ext_allowed(kvm, ext))
 		return 0;
 
+	if (kvm && kvm_is_realm(kvm) && !kvm_realm_ext_allowed(ext))
+		return 0;
+
 	switch (ext) {
 	case KVM_CAP_IRQCHIP:
 		r = vgic_present;

---

## [17] Steven Price — 2026-05-13
*Subject: [PATCH v14 16/44] KVM: arm64: Allow passing machine type in KVM creation*

Previously machine type was used purely for specifying the physical
address size of the guest. Reserve the higher bits to specify an ARM
specific machine type and declare a new type 'KVM_VM_TYPE_ARM_REALM'
used to create a realm guest.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v13:
 * Rework to use the two top bits for the machine type now that pKVM has
   merged and used the top bit for KVM_VM_TYPE_ARM_PROTECTED.
 * Update the documentation to include KVM_VM_TYPE_ARM_PROTECTED as
   well.
Changes since v9:
 * Explictly set realm.state to REALM_STATE_NONE rather than rely on the
   zeroing of the structure.
Changes since v7:
 * Add some documentation explaining the new machine type.
Changes since v6:
 * Make the check for kvm_rme_is_available more visible and report an
   error code of -EPERM (instead of -EINVAL) to make it explicit that
   the kernel supports RME, but the platform doesn't.
---
 Documentation/virt/kvm/api.rst | 18 ++++++++++++++++--
 arch/arm64/kvm/arm.c           | 11 +++++++++++
 include/uapi/linux/kvm.h       |  7 ++++++-
 3 files changed, 33 insertions(+), 3 deletions(-)

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index ca68aae7faa2..31a5919d8d5f 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -181,8 +181,22 @@ flag KVM_VM_MIPS_VZ.
 ARM64:
 ^^^^^^
 
-On arm64, the physical address size for a VM (IPA Size limit) is limited
-to 40bits by default. The limit can be configured if the host supports the
+On arm64, the machine type identifier is used to encode a type and the
+physical address size for the VM. The lower byte (bits[7-0]) encode the
+address size and the upper bits[30-31] encode a machine type. The machine
+types that might be available are:
+
+ =========================   ============================================
+ KVM_VM_TYPE_ARM_NORMAL      A standard VM
+ KVM_VM_TYPE_ARM_REALM       A "Realm" VM using the Arm Confidential
+                             Compute extensions, the VM's memory is
+                             protected from the host.
+ KVM_VM_TYPE_ARM_PROTECTED   A "protected" VM using pKVM to isolate the
+                             VM from the host.
+ =========================   ============================================
+
+The physical address size for a VM (IPA Size limit) is limited to 40bits
+by default. The limit can be configured if the host supports the
 extension KVM_CAP_ARM_VM_IPA_SIZE. When supported, use
 KVM_VM_TYPE_ARM_IPA_SIZE(IPA_Bits) to set the size in the machine type
 identifier, where IPA_Bits is the maximum width of any physical
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index c6ebc5913e40..41d35b2d1dee 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -246,6 +246,17 @@ int kvm_arch_init_vm(struct kvm *kvm, unsigned long type)
 	mutex_unlock(&kvm->lock);
 #endif
 
+	if ((type & KVM_VM_TYPE_ARM_PROTECTED) &&
+	    (type & KVM_VM_TYPE_ARM_REALM))
+		return -EINVAL;
+
+	if (type & KVM_VM_TYPE_ARM_REALM) {
+		if (!static_branch_unlikely(&kvm_rmi_is_available))
+			return -EINVAL;
+		kvm_set_realm_state(kvm, REALM_STATE_NONE);
+		kvm->arch.is_realm = true;
+	}
+
 	kvm_init_nested(kvm);
 
 	ret = kvm_share_hyp(kvm, kvm + 1);
diff --git a/include/uapi/linux/kvm.h b/include/uapi/linux/kvm.h
index b8cff0938041..7b2507a3865e 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -700,14 +700,19 @@ struct kvm_enable_cap {
  * address size for the VM. Bits[7-0] are reserved for the guest
  * PA size shift (i.e, log2(PA_Size)). For backward compatibility,
  * value 0 implies the default IPA size, 40bits.
+ *
+ * Bits[30-31] are reserved for the VM type
  */
 #define KVM_VM_TYPE_ARM_IPA_SIZE_MASK	0xffULL
 #define KVM_VM_TYPE_ARM_IPA_SIZE(x)		\
 	((x) & KVM_VM_TYPE_ARM_IPA_SIZE_MASK)
 
+#define KVM_VM_TYPE_ARM_NORMAL		0
+#define KVM_VM_TYPE_ARM_REALM		(1UL << 30)
 #define KVM_VM_TYPE_ARM_PROTECTED	(1UL << 31)
 #define KVM_VM_TYPE_ARM_MASK		(KVM_VM_TYPE_ARM_IPA_SIZE_MASK | \
-					 KVM_VM_TYPE_ARM_PROTECTED)
+					 KVM_VM_TYPE_ARM_PROTECTED | \
+					 KVM_VM_TYPE_ARM_REALM)
 
 /*
  * ioctls for /dev/kvm fds:

---

## [18] Steven Price — 2026-05-13
*Subject: [PATCH v14 17/44] arm64: RMI: RTT tear down*

The RMM owns the stage 2 page tables for a realm, and KVM must request
that the RMM creates/destroys entries as necessary. The physical pages
to store the page tables are delegated to the realm as required, and can
be undelegated when no longer used.

Creating new RTTs is the easy part, tearing down is a little more
tricky. The result of realm_rtt_destroy() can be used to effectively
walk the tree and destroy the entries (undelegating pages that were
given to the realm).

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v13:
 * Avoid the double call of kvm_free_stage2_pgd() by splitting the work
   across that and a new function kvm_realm_uninit_stage2() which is
   only called for realm guests.
Changes since v12:
 * Simplify some functions now we know RMM page size is the same as the
   host's.
Changes since v11:
 * Moved some code from earlier in the series to this one so that it's
   added when it's first used.
Changes since v10:
 * RME->RMI rename.
 * Some code to handle freeing stage 2 PGD moved into this patch where
   it belongs.
Changes since v9:
 * Add a comment clarifying that root level RTTs are not destroyed until
   after the RD is destroyed.
Changes since v8:
 * Introduce free_rtt() wrapper which calls free_delegated_granule()
   followed by kvm_account_pgtable_pages(). This makes it clear where an
   RTT is being freed rather than just a delegated granule.
Changes since v6:
 * Move rme_rtt_level_mapsize() and supporting defines from kvm_rme.h
   into rme.c as they are only used in that file.
Changes since v5:
 * Rename some RME_xxx defines to do with page sizes as RMM_xxx - they are
   a property of the RMM specification not the RME architecture.
Changes since v2:
 * Moved {alloc,free}_delegated_page() and ensure_spare_page() to a
   later patch when they are actually used.
 * Some simplifications now rmi_xxx() functions allow NULL as an output
   parameter.
 * Improved comments and code layout.
---
 arch/arm64/include/asm/kvm_rmi.h |   7 ++
 arch/arm64/kvm/mmu.c             |  21 ++++-
 arch/arm64/kvm/rmi.c             | 148 +++++++++++++++++++++++++++++++
 3 files changed, 174 insertions(+), 2 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index 9de34983ee52..06ba0d4745c6 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -64,5 +64,12 @@ u32 kvm_realm_ipa_limit(void);
 
 int kvm_init_realm(struct kvm *kvm);
 void kvm_destroy_realm(struct kvm *kvm);
+void kvm_realm_destroy_rtts(struct kvm *kvm);
+
+static inline bool kvm_realm_is_private_address(struct realm *realm,
+						unsigned long addr)
+{
+	return !(addr & BIT(realm->ia_bits - 1));
+}
 
 #endif /* __ASM_KVM_RMI_H */
diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index ba8286472286..eb56d4e7f21a 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -1024,9 +1024,26 @@ int kvm_init_stage2_mmu(struct kvm *kvm, struct kvm_s2_mmu *mmu, unsigned long t
 	return err;
 }
 
+static void kvm_realm_uninit_stage2(struct kvm_s2_mmu *mmu)
+{
+	struct kvm *kvm = kvm_s2_mmu_to_kvm(mmu);
+	struct realm *realm = &kvm->arch.realm;
+
+	if (kvm_realm_state(kvm) != REALM_STATE_ACTIVE)
+		return;
+
+	write_lock(&kvm->mmu_lock);
+	kvm_stage2_unmap_range(mmu, 0, BIT(realm->ia_bits - 1), true);
+	write_unlock(&kvm->mmu_lock);
+	kvm_realm_destroy_rtts(kvm);
+}
+
 void kvm_uninit_stage2_mmu(struct kvm *kvm)
 {
-	kvm_free_stage2_pgd(&kvm->arch.mmu);
+	if (kvm_is_realm(kvm))
+		kvm_realm_uninit_stage2(&kvm->arch.mmu);
+	else
+		kvm_free_stage2_pgd(&kvm->arch.mmu);
 	kvm_mmu_free_memory_cache(&kvm->arch.mmu.split_page_cache);
 }
 
@@ -1103,7 +1120,7 @@ void stage2_unmap_vm(struct kvm *kvm)
 void kvm_free_stage2_pgd(struct kvm_s2_mmu *mmu)
 {
 	struct kvm *kvm = kvm_s2_mmu_to_kvm(mmu);
-	struct kvm_pgtable *pgt = NULL;
+	struct kvm_pgtable *pgt;
 
 	write_lock(&kvm->mmu_lock);
 	pgt = mmu->pgt;
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index f51ec667445e..5b00ccca4af3 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -11,6 +11,14 @@
 #include <asm/rmi_cmds.h>
 #include <asm/virt.h>
 
+static inline unsigned long rmi_rtt_level_mapsize(int level)
+{
+	if (WARN_ON(level > KVM_PGTABLE_LAST_LEVEL))
+		return PAGE_SIZE;
+
+	return (1UL << ARM64_HW_PGTABLE_LEVEL_SHIFT(level));
+}
+
 static bool rmi_has_feature(unsigned long feature)
 {
 	return !!u64_get_bits(rmm_feat_reg0, feature);
@@ -21,6 +29,144 @@ u32 kvm_realm_ipa_limit(void)
 	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_S2SZ);
 }
 
+static int get_start_level(struct realm *realm)
+{
+	return 4 - stage2_pgtable_levels(realm->ia_bits);
+}
+
+static void free_rtt(phys_addr_t phys)
+{
+	if (free_delegated_page(phys))
+		return;
+
+	kvm_account_pgtable_pages(phys_to_virt(phys), -1);
+}
+
+/*
+ * realm_rtt_destroy - Destroy an RTT at @level for @addr.
+ *
+ * Returns - Result of the RMI_RTT_DESTROY call, and:
+ * @rtt_granule:	RTT granule, if the RTT was destroyed.
+ * @next_addr:		IPA corresponding to the next possible valid entry we
+ *			can target
+ */
+static int realm_rtt_destroy(struct realm *realm, unsigned long addr,
+			     int level, phys_addr_t *rtt_granule,
+			     unsigned long *next_addr)
+{
+	unsigned long out_rtt;
+	int ret;
+
+	ret = rmi_rtt_destroy(virt_to_phys(realm->rd), addr, level,
+			      &out_rtt, next_addr);
+
+	*rtt_granule = out_rtt;
+
+	return ret;
+}
+
+static int realm_tear_down_rtt_level(struct realm *realm, int level,
+				     unsigned long start, unsigned long end)
+{
+	ssize_t map_size;
+	unsigned long addr, next_addr;
+
+	if (WARN_ON(level > KVM_PGTABLE_LAST_LEVEL))
+		return -EINVAL;
+
+	map_size = rmi_rtt_level_mapsize(level - 1);
+
+	for (addr = start; addr < end; addr = next_addr) {
+		phys_addr_t rtt_granule;
+		int ret;
+		unsigned long align_addr = ALIGN(addr, map_size);
+
+		next_addr = ALIGN(addr + 1, map_size);
+
+		if (next_addr > end || align_addr != addr) {
+			/*
+			 * The target range is smaller than what this level
+			 * covers, recurse deeper.
+			 */
+			ret = realm_tear_down_rtt_level(realm,
+							level + 1,
+							addr,
+							min(next_addr, end));
+			if (ret)
+				return ret;
+			continue;
+		}
+
+		ret = realm_rtt_destroy(realm, addr, level,
+					&rtt_granule, &next_addr);
+
+		switch (RMI_RETURN_STATUS(ret)) {
+		case RMI_SUCCESS:
+			free_rtt(rtt_granule);
+			break;
+		case RMI_ERROR_RTT:
+			if (next_addr > addr) {
+				/* Missing RTT, skip */
+				break;
+			}
+			/*
+			 * We tear down the RTT range for the full IPA
+			 * space, after everything is unmapped. Also we
+			 * descend down only if we cannot tear down a
+			 * top level RTT. Thus RMM must be able to walk
+			 * to the requested level. e.g., a block mapping
+			 * exists at L1 or L2.
+			 */
+			if (WARN_ON(RMI_RETURN_INDEX(ret) != level))
+				return -EBUSY;
+			if (WARN_ON(level == KVM_PGTABLE_LAST_LEVEL))
+				return -EBUSY;
+
+			/*
+			 * The table has active entries in it, recurse deeper
+			 * and tear down the RTTs.
+			 */
+			next_addr = ALIGN(addr + 1, map_size);
+			ret = realm_tear_down_rtt_level(realm,
+							level + 1,
+							addr,
+							next_addr);
+			if (ret)
+				return ret;
+			/*
+			 * Now that the child RTTs are destroyed,
+			 * retry at this level.
+			 */
+			next_addr = addr;
+			break;
+		default:
+			WARN_ON(1);
+			return -ENXIO;
+		}
+	}
+
+	return 0;
+}
+
+static int realm_tear_down_rtt_range(struct realm *realm,
+				     unsigned long start, unsigned long end)
+{
+	/*
+	 * Root level RTTs can only be destroyed after the RD is destroyed. So
+	 * tear down everything below the root level
+	 */
+	return realm_tear_down_rtt_level(realm, get_start_level(realm) + 1,
+					 start, end);
+}
+
+void kvm_realm_destroy_rtts(struct kvm *kvm)
+{
+	struct realm *realm = &kvm->arch.realm;
+	unsigned int ia_bits = realm->ia_bits;
+
+	realm_tear_down_rtt_range(realm, 0, (1UL << ia_bits));
+}
+
 void kvm_destroy_realm(struct kvm *kvm)
 {
 	struct realm *realm = &kvm->arch.realm;
@@ -47,6 +193,8 @@ void kvm_destroy_realm(struct kvm *kvm)
 		if (WARN_ON(rmi_realm_terminate(rd_phys)))
 			return;
 
+		kvm_realm_destroy_rtts(kvm);
+
 		if (WARN_ON(rmi_realm_destroy(rd_phys)))
 			return;
 		free_delegated_page(rd_phys);

---

## [19] Steven Price — 2026-05-13
*Subject: [PATCH v14 18/44] arm64: RMI: Activate realm on first VCPU run*

Use kvm_arch_vcpu_run_pid_change() to check if this is the first time
the realm guest has run. If this is the first run then activate the
realm.

Before the realm can be activated it must first be created, this is a
stub in this patch and will be filled in by a later patch.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v12:
 * Fix commit message
 * Change realm_state checks to be >= REALM_STATE_ACTIVE to avoid a dead
   guest being revived by kvm_activate_realm().
---
 arch/arm64/include/asm/kvm_rmi.h |  1 +
 arch/arm64/kvm/arm.c             |  6 +++++
 arch/arm64/kvm/rmi.c             | 39 ++++++++++++++++++++++++++++++++
 3 files changed, 46 insertions(+)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index 06ba0d4745c6..8bd743093ccf 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -63,6 +63,7 @@ void kvm_init_rmi(void);
 u32 kvm_realm_ipa_limit(void);
 
 int kvm_init_realm(struct kvm *kvm);
+int kvm_activate_realm(struct kvm *kvm);
 void kvm_destroy_realm(struct kvm *kvm);
 void kvm_realm_destroy_rtts(struct kvm *kvm);
 
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 41d35b2d1dee..eb2b61fe1f0a 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -1018,6 +1018,12 @@ int kvm_arch_vcpu_run_pid_change(struct kvm_vcpu *vcpu)
 			return ret;
 	}
 
+	if (kvm_is_realm(vcpu->kvm)) {
+		ret = kvm_activate_realm(kvm);
+		if (ret)
+			return ret;
+	}
+
 	mutex_lock(&kvm->arch.config_lock);
 	set_bit(KVM_ARCH_FLAG_HAS_RAN_ONCE, &kvm->arch.flags);
 	mutex_unlock(&kvm->arch.config_lock);
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 5b00ccca4af3..849111817af7 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -167,6 +167,45 @@ void kvm_realm_destroy_rtts(struct kvm *kvm)
 	realm_tear_down_rtt_range(realm, 0, (1UL << ia_bits));
 }
 
+static int realm_ensure_created(struct kvm *kvm)
+{
+	/* Provided in later patch */
+	return -ENXIO;
+}
+
+int kvm_activate_realm(struct kvm *kvm)
+{
+	struct realm *realm = &kvm->arch.realm;
+	int ret;
+
+	if (kvm_realm_state(kvm) >= REALM_STATE_ACTIVE)
+		return 0;
+
+	if (!irqchip_in_kernel(kvm)) {
+		/* Userspace irqchip not yet supported with realms */
+		return -EOPNOTSUPP;
+	}
+
+	guard(mutex)(&kvm->arch.config_lock);
+	/* Check again with the lock held */
+	if (kvm_realm_state(kvm) >= REALM_STATE_ACTIVE)
+		return 0;
+
+	ret = realm_ensure_created(kvm);
+	if (ret)
+		return ret;
+
+	/* Mark state as dead in case we fail */
+	kvm_set_realm_state(kvm, REALM_STATE_DEAD);
+
+	ret = rmi_realm_activate(virt_to_phys(realm->rd));
+	if (ret)
+		return -ENXIO;
+
+	kvm_set_realm_state(kvm, REALM_STATE_ACTIVE);
+	return 0;
+}
+
 void kvm_destroy_realm(struct kvm *kvm)
 {
 	struct realm *realm = &kvm->arch.realm;

---

## [20] Steven Price — 2026-05-13
*Subject: [PATCH v14 19/44] arm64: RMI: Allocate/free RECs to match vCPUs*

The RMM maintains a data structure known as the Realm Execution Context
(or REC). It is similar to struct kvm_vcpu and tracks the state of the
virtual CPUs. KVM must delegate memory and request the structures are
created when vCPUs are created, and suitably tear down on destruction.

RECs may require additional pages (e.g. for storing larger register
state for SVE). The RMM can request extra pages for this purpose using
the Stateful RMI Operations (SRO) functionality to request pages during
REC creation. These pages are then passed back to the host from the RMM
('reclaimed') when the REC is destroyed. The kernel tracking object
(struct rmi_sro_state) is stored in the realm_rec structure to avoid
memory allocation during the destruction path.

Note that only some of register state for the REC can be set by KVM, the
rest is defined by the RMM (zeroed). The register state then cannot be
changed by KVM after the REC is created (except when the guest
explicitly requests this e.g. by performing a PSCI call).

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v13:
 * Support SRO for REC creation/destruction instead of auxiliary
   granules.
Changes since v12:
 * Use the new range-based delegation RMI.
Changes since v11:
 * Remove the KVM_ARM_VCPU_REC feature. User space no longer needs to
   configure each VCPU separately, RECs are created on the first VCPU
   run of the guest.
Changes since v9:
 * Size the aux_pages array according to the PAGE_SIZE of the host.
Changes since v7:
 * Add comment explaining the aux_pages array.
 * Rename "undeleted_failed" variable to "should_free" to avoid a
   confusing double negative.
Changes since v6:
 * Avoid reporting the KVM_ARM_VCPU_REC feature if the guest isn't a
   realm guest.
 * Support host page size being larger than RMM's granule size when
   allocating/freeing aux granules.
Changes since v5:
 * Separate the concept of vcpu_is_rec() and
   kvm_arm_vcpu_rec_finalized() by using the KVM_ARM_VCPU_REC feature as
   the indication that the VCPU is a REC.
Changes since v2:
 * Free rec->run earlier in kvm_destroy_realm() and adapt to previous patches.
---
 arch/arm64/include/asm/kvm_emulate.h |   2 +-
 arch/arm64/include/asm/kvm_host.h    |   3 +
 arch/arm64/include/asm/kvm_rmi.h     |  17 +++++
 arch/arm64/kvm/arm.c                 |   6 ++
 arch/arm64/kvm/reset.c               |   1 +
 arch/arm64/kvm/rmi.c                 | 105 +++++++++++++++++++++++++++
 6 files changed, 133 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/kvm_emulate.h b/arch/arm64/include/asm/kvm_emulate.h
index 82fd777bd9bb..2e69fe494716 100644
--- a/arch/arm64/include/asm/kvm_emulate.h
+++ b/arch/arm64/include/asm/kvm_emulate.h
@@ -714,7 +714,7 @@ static inline bool kvm_realm_is_created(struct kvm *kvm)
 
 static inline bool vcpu_is_rec(const struct kvm_vcpu *vcpu)
 {
-	return false;
+	return kvm_is_realm(vcpu->kvm);
 }
 
 #endif /* __ARM64_KVM_EMULATE_H__ */
diff --git a/arch/arm64/include/asm/kvm_host.h b/arch/arm64/include/asm/kvm_host.h
index 3512696ed506..39b5de03d0fe 100644
--- a/arch/arm64/include/asm/kvm_host.h
+++ b/arch/arm64/include/asm/kvm_host.h
@@ -969,6 +969,9 @@ struct kvm_vcpu_arch {
 
 	/* Hyp-readable copy of kvm_vcpu::pid */
 	pid_t pid;
+
+	/* Realm meta data */
+	struct realm_rec rec;
 };
 
 /*
diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index 8bd743093ccf..d99bf4fc3c39 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -59,6 +59,22 @@ struct realm {
 	unsigned int ia_bits;
 };
 
+/**
+ * struct realm_rec - Additional per VCPU data for a Realm
+ *
+ * @mpidr: MPIDR (Multiprocessor Affinity Register) value to identify this VCPU
+ * @rec_page: Kernel VA of the RMM's private page for this REC
+ * @aux_pages: Additional pages private to the RMM for this REC
+ * @run: Kernel VA of the RmiRecRun structure shared with the RMM
+ * @sro: A preallocated SRO state context
+ */
+struct realm_rec {
+	unsigned long mpidr;
+	void *rec_page;
+	struct rec_run *run;
+	struct rmi_sro_state *sro;
+};
+
 void kvm_init_rmi(void);
 u32 kvm_realm_ipa_limit(void);
 
@@ -66,6 +82,7 @@ int kvm_init_realm(struct kvm *kvm);
 int kvm_activate_realm(struct kvm *kvm);
 void kvm_destroy_realm(struct kvm *kvm);
 void kvm_realm_destroy_rtts(struct kvm *kvm);
+void kvm_destroy_rec(struct kvm_vcpu *vcpu);
 
 static inline bool kvm_realm_is_private_address(struct realm *realm,
 						unsigned long addr)
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index eb2b61fe1f0a..93d34762db91 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -586,6 +586,8 @@ int kvm_arch_vcpu_create(struct kvm_vcpu *vcpu)
 	/* Force users to call KVM_ARM_VCPU_INIT */
 	vcpu_clear_flag(vcpu, VCPU_INITIALIZED);
 
+	vcpu->arch.rec.mpidr = INVALID_HWID;
+
 	vcpu->arch.mmu_page_cache.gfp_zero = __GFP_ZERO;
 
 	/* Set up the timer */
@@ -1651,6 +1653,10 @@ static int kvm_vcpu_init_check_features(struct kvm_vcpu *vcpu,
 	if (test_bit(KVM_ARM_VCPU_HAS_EL2, &features))
 		return -EINVAL;
 
+	/* Realms are incompatible with AArch32 */
+	if (vcpu_is_rec(vcpu))
+		return -EINVAL;
+
 	return 0;
 }
 
diff --git a/arch/arm64/kvm/reset.c b/arch/arm64/kvm/reset.c
index b963fd975aac..c18cdca7d125 100644
--- a/arch/arm64/kvm/reset.c
+++ b/arch/arm64/kvm/reset.c
@@ -161,6 +161,7 @@ void kvm_arm_vcpu_destroy(struct kvm_vcpu *vcpu)
 	free_page((unsigned long)vcpu->arch.ctxt.vncr_array);
 	kfree(vcpu->arch.vncr_tlb);
 	kfree(vcpu->arch.ccsidr);
+	kvm_destroy_rec(vcpu);
 }
 
 static void kvm_vcpu_reset_sve(struct kvm_vcpu *vcpu)
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 849111817af7..353a5ca45e78 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -173,9 +173,108 @@ static int realm_ensure_created(struct kvm *kvm)
 	return -ENXIO;
 }
 
+static int kvm_create_rec(struct kvm_vcpu *vcpu)
+{
+	struct user_pt_regs *vcpu_regs = vcpu_gp_regs(vcpu);
+	unsigned long mpidr = kvm_vcpu_get_mpidr_aff(vcpu);
+	struct realm *realm = &vcpu->kvm->arch.realm;
+	struct realm_rec *rec = &vcpu->arch.rec;
+	unsigned long rec_page_phys;
+	struct rec_params *params;
+	int r, i;
+
+	if (rec->run)
+		return -EBUSY;
+
+	/*
+	 * The RMM will report PSCI v1.0 to Realms and the KVM_ARM_VCPU_PSCI_0_2
+	 * flag covers v0.2 and onwards.
+	 */
+	if (!vcpu_has_feature(vcpu, KVM_ARM_VCPU_PSCI_0_2))
+		return -EINVAL;
+
+	BUILD_BUG_ON(sizeof(*params) > PAGE_SIZE);
+	BUILD_BUG_ON(sizeof(*rec->run) > PAGE_SIZE);
+
+	params = (struct rec_params *)get_zeroed_page(GFP_KERNEL);
+	rec->rec_page = (void *)__get_free_page(GFP_KERNEL);
+	rec->run = (void *)get_zeroed_page(GFP_KERNEL);
+	rec->sro = kmalloc_obj(*rec->sro);
+	if (!params || !rec->rec_page || !rec->run || !rec->sro) {
+		r = -ENOMEM;
+		goto out_free_pages;
+	}
+
+	for (i = 0; i < ARRAY_SIZE(params->gprs); i++)
+		params->gprs[i] = vcpu_regs->regs[i];
+
+	params->pc = vcpu_regs->pc;
+
+	if (vcpu->vcpu_id == 0)
+		params->flags |= REC_PARAMS_FLAG_RUNNABLE;
+
+	rec_page_phys = virt_to_phys(rec->rec_page);
+
+	if (rmi_delegate_page(rec_page_phys)) {
+		r = -ENXIO;
+		goto out_free_pages;
+	}
+
+	params->mpidr = mpidr;
+
+	if (rmi_rec_create(virt_to_phys(realm->rd), rec_page_phys,
+			   virt_to_phys(params), rec->sro)) {
+		r = -ENXIO;
+		goto out_undelegate_rmm_rec;
+	}
+
+	rec->mpidr = mpidr;
+
+	free_page((unsigned long)params);
+	return 0;
+
+out_undelegate_rmm_rec:
+	if (WARN_ON(rmi_undelegate_page(rec_page_phys)))
+		rec->rec_page = NULL;
+out_free_pages:
+	free_page((unsigned long)rec->run);
+	free_page((unsigned long)rec->rec_page);
+	free_page((unsigned long)params);
+	kfree(rec->sro);
+	rec->run = NULL;
+	return r;
+}
+
+void kvm_destroy_rec(struct kvm_vcpu *vcpu)
+{
+	struct realm_rec *rec = &vcpu->arch.rec;
+	unsigned long rec_page_phys;
+
+	if (!vcpu_is_rec(vcpu))
+		return;
+
+	if (!rec->run) {
+		/* Nothing to do if the VCPU hasn't been finalized */
+		return;
+	}
+
+	free_page((unsigned long)rec->run);
+
+	rec_page_phys = virt_to_phys(rec->rec_page);
+
+	if (WARN_ON(rmi_rec_destroy(rec_page_phys, rec->sro)))
+		return;
+
+	kfree(rec->sro);
+
+	free_delegated_page(rec_page_phys);
+}
+
 int kvm_activate_realm(struct kvm *kvm)
 {
 	struct realm *realm = &kvm->arch.realm;
+	struct kvm_vcpu *vcpu;
+	unsigned long i;
 	int ret;
 
 	if (kvm_realm_state(kvm) >= REALM_STATE_ACTIVE)
@@ -198,6 +297,12 @@ int kvm_activate_realm(struct kvm *kvm)
 	/* Mark state as dead in case we fail */
 	kvm_set_realm_state(kvm, REALM_STATE_DEAD);
 
+	kvm_for_each_vcpu(i, vcpu, kvm) {
+		ret = kvm_create_rec(vcpu);
+		if (ret)
+			return ret;
+	}
+
 	ret = rmi_realm_activate(virt_to_phys(realm->rd));
 	if (ret)
 		return -ENXIO;

---

## [21] Steven Price — 2026-05-13
*Subject: [PATCH v14 20/44] arm64: RMI: Support for the VGIC in realms*

The RMM provides emulation of a VGIC to the realm guest. With RMM v2.0
the registers are passed in the system registers so this works similar
to a normal guest, but kvm_arch_vcpu_put() need reordering to early out,
and realm guests don't support GICv2 even if the host does.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes from v12:
 * GIC registers are now passed in the system registers rather than via
   rec_entry/rec_exit which removes most of the changes.
Changes from v11:
 * Minor changes to align with the previous patches. Note that the VGIC
   handling will change with RMM v2.0.
Changes from v10:
 * Make sure we sync the VGIC v4 state, and only populate valid lrs from
   the list.
Changes from v9:
 * Copy gicv3_vmcr from the RMM at the same time as gicv3_hcr rather
   than having to handle that as a special case.
Changes from v8:
 * Propagate gicv3_hcr to from the RMM.
Changes from v5:
 * Handle RMM providing fewer GIC LRs than the hardware supports.
---
 arch/arm64/kvm/arm.c            | 11 ++++++++---
 arch/arm64/kvm/vgic/vgic-init.c |  2 +-
 2 files changed, 9 insertions(+), 4 deletions(-)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 93d34762db91..21d9dfdb1ea0 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -786,19 +786,24 @@ void kvm_arch_vcpu_put(struct kvm_vcpu *vcpu)
 		kvm_call_hyp_nvhe(__pkvm_vcpu_put);
 	}
 
+	kvm_timer_vcpu_put(vcpu);
+	kvm_vgic_put(vcpu);
+
+	vcpu->cpu = -1;
+
+	if (vcpu_is_rec(vcpu))
+		return;
+
 	kvm_vcpu_put_debug(vcpu);
 	kvm_arch_vcpu_put_fp(vcpu);
 	if (has_vhe())
 		kvm_vcpu_put_vhe(vcpu);
-	kvm_timer_vcpu_put(vcpu);
-	kvm_vgic_put(vcpu);
 	kvm_vcpu_pmu_restore_host(vcpu);
 	if (vcpu_has_nv(vcpu))
 		kvm_vcpu_put_hw_mmu(vcpu);
 	kvm_arm_vmid_clear_active();
 
 	vcpu_clear_on_unsupported_cpu(vcpu);
-	vcpu->cpu = -1;
 }
 
 static void __kvm_arm_vcpu_power_off(struct kvm_vcpu *vcpu)
diff --git a/arch/arm64/kvm/vgic/vgic-init.c b/arch/arm64/kvm/vgic/vgic-init.c
index 933983bb2005..a9db963dfd23 100644
--- a/arch/arm64/kvm/vgic/vgic-init.c
+++ b/arch/arm64/kvm/vgic/vgic-init.c
@@ -81,7 +81,7 @@ int kvm_vgic_create(struct kvm *kvm, u32 type)
 	 * the proper checks already.
 	 */
 	if (type == KVM_DEV_TYPE_ARM_VGIC_V2 &&
-		!kvm_vgic_global_state.can_emulate_gicv2)
+	    (!kvm_vgic_global_state.can_emulate_gicv2 || kvm_is_realm(kvm)))
 		return -ENODEV;
 
 	/*

---

## [22] Steven Price — 2026-05-13
*Subject: [PATCH v14 21/44] KVM: arm64: Support timers in realm RECs*

The RMM keeps track of the timer while the realm REC is running, but on
exit to the normal world KVM is responsible for handling the timers.

A later patch adds the support for propagating the timer values from the
exit data structure and calling kvm_realm_timers_update().

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v12:
 * Adapt to upstream changes.
Changes since v11:
 * Drop the kvm_is_realm() check from timer_set_offset(). We already
   ensure that the offset is 0 when calling the function.
Changes since v10:
 * KVM_CAP_COUNTER_OFFSET is now already hidden by a previous patch.
Changes since v9:
 * No need to move the call to kvm_timer_unblocking() in
   kvm_timer_vcpu_load().
Changes since v7:
 * Hide KVM_CAP_COUNTER_OFFSET for realm guests.
---
 arch/arm64/kvm/arch_timer.c  | 28 +++++++++++++++++++++++++---
 include/kvm/arm_arch_timer.h |  2 ++
 2 files changed, 27 insertions(+), 3 deletions(-)

diff --git a/arch/arm64/kvm/arch_timer.c b/arch/arm64/kvm/arch_timer.c
index cbea4d9ee955..88ed01edc136 100644
--- a/arch/arm64/kvm/arch_timer.c
+++ b/arch/arm64/kvm/arch_timer.c
@@ -470,6 +470,21 @@ static void kvm_timer_update_irq(struct kvm_vcpu *vcpu, bool new_level,
 			    timer_ctx);
 }
 
+void kvm_realm_timers_update(struct kvm_vcpu *vcpu)
+{
+	struct arch_timer_cpu *arch_timer = &vcpu->arch.timer_cpu;
+	int i;
+
+	for (i = 0; i < NR_KVM_EL0_TIMERS; i++) {
+		struct arch_timer_context *timer = &arch_timer->timers[i];
+		bool status = timer_get_ctl(timer) & ARCH_TIMER_CTRL_IT_STAT;
+		bool level = kvm_timer_irq_can_fire(timer) && status;
+
+		if (level != timer->irq.level)
+			kvm_timer_update_irq(vcpu, level, timer);
+	}
+}
+
 /* Only called for a fully emulated timer */
 static void timer_emulate(struct arch_timer_context *ctx)
 {
@@ -1079,7 +1094,7 @@ static void timer_context_init(struct kvm_vcpu *vcpu, int timerid)
 
 	ctxt->timer_id = timerid;
 
-	if (!kvm_vm_is_protected(vcpu->kvm)) {
+	if (!kvm_vm_is_protected(vcpu->kvm) && !kvm_is_realm(vcpu->kvm)) {
 		if (timerid == TIMER_VTIMER)
 			ctxt->offset.vm_offset = &kvm->arch.timer_data.voffset;
 		else
@@ -1110,7 +1125,7 @@ void kvm_timer_vcpu_init(struct kvm_vcpu *vcpu)
 		timer_context_init(vcpu, i);
 
 	/* Synchronize offsets across timers of a VM if not already provided */
-	if (!vcpu_is_protected(vcpu) &&
+	if (!vcpu_is_protected(vcpu) && !kvm_is_realm(vcpu->kvm) &&
 	    !test_bit(KVM_ARCH_FLAG_VM_COUNTER_OFFSET, &vcpu->kvm->arch.flags)) {
 		timer_set_offset(vcpu_vtimer(vcpu), kvm_phys_timer_read());
 		timer_set_offset(vcpu_ptimer(vcpu), 0);
@@ -1611,6 +1626,13 @@ int kvm_timer_enable(struct kvm_vcpu *vcpu)
 		return -EINVAL;
 	}
 
+	/*
+	 * We don't use mapped IRQs for Realms because the RMI doesn't allow
+	 * us setting the LR.HW bit in the VGIC.
+	 */
+	if (vcpu_is_rec(vcpu))
+		return 0;
+
 	get_timer_map(vcpu, &map);
 
 	ops = vgic_is_v5(vcpu->kvm) ? &arch_timer_irq_ops_vgic_v5 :
@@ -1740,7 +1762,7 @@ int kvm_vm_ioctl_set_counter_offset(struct kvm *kvm,
 	if (offset->reserved)
 		return -EINVAL;
 
-	if (kvm_vm_is_protected(kvm))
+	if (kvm_vm_is_protected(kvm) || kvm_is_realm(kvm))
 		return -EINVAL;
 
 	mutex_lock(&kvm->lock);
diff --git a/include/kvm/arm_arch_timer.h b/include/kvm/arm_arch_timer.h
index bf8cc9589bd0..ffdb90dcad58 100644
--- a/include/kvm/arm_arch_timer.h
+++ b/include/kvm/arm_arch_timer.h
@@ -113,6 +113,8 @@ int kvm_arm_timer_set_attr(struct kvm_vcpu *vcpu, struct kvm_device_attr *attr);
 int kvm_arm_timer_get_attr(struct kvm_vcpu *vcpu, struct kvm_device_attr *attr);
 int kvm_arm_timer_has_attr(struct kvm_vcpu *vcpu, struct kvm_device_attr *attr);
 
+void kvm_realm_timers_update(struct kvm_vcpu *vcpu);
+
 u64 kvm_phys_timer_read(void);
 
 void kvm_timer_vcpu_load(struct kvm_vcpu *vcpu);

---

## [23] Steven Price — 2026-05-13
*Subject: [PATCH v14 22/44] arm64: RMI: Handle realm enter/exit*

Entering a realm is done using a SMC call to the RMM. On exit the
exit-codes need to be handled slightly differently to the normal KVM
path so define our own functions for realm enter/exit and hook them
in if the guest is a realm guest.

Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
---
Chanegs since v13:
 * The RMM is now required to provide an ESR value with the correct
   information to emulate MMIO, so we no longer need to hardcode 0s in
   rec_exit_sys_reg().
 * The PSCI changes mean that there is a potential race when turning on
   a VCPU which can cause a RMI_ERROR_REC return. Exit to user space
   with -EAGAIN in this case.
Changes since v12:
 * Call guest_state_{enter,exit}_irqoff() around rmi_rec_enter().
 * Add handling of the IRQ exception case where IRQs need to be briefly
   enabled before exiting guest timing.
Changes since v8:
 * Introduce kvm_rec_pre_enter() called before entering an atomic
   section to handle operations that might require memory allocation
   (specifically completing a RIPAS change introduced in a later patch).
 * Updates to align with upstream changes to hpfar_el2 which now (ab)uses
   HPFAR_EL2_NS as a valid flag.
 * Fix exit reason when racing with PSCI shutdown to return
   KVM_EXIT_SHUTDOWN rather than KVM_EXIT_UNKNOWN.
Changes since v7:
 * A return of 0 from kvm_handle_sys_reg() doesn't mean the register has
   been read (although that can never happen in the current code). Tidy
   up the condition to handle any future refactoring.
Changes since v6:
 * Use vcpu_err() rather than pr_err/kvm_err when there is an associated
   vcpu to the error.
 * Return -EFAULT for KVM_EXIT_MEMORY_FAULT as per the documentation for
   this exit type.
 * Split code handling a RIPAS change triggered by the guest to the
   following patch.
Changes since v5:
 * For a RIPAS_CHANGE request from the guest perform the actual RIPAS
   change on next entry rather than immediately on the exit. This allows
   the VMM to 'reject' a RIPAS change by refusing to continue
   scheduling.
Changes since v4:
 * Rename handle_rme_exit() to handle_rec_exit()
 * Move the loop to copy registers into the REC enter structure from the
   to rec_exit_handlers callbacks to kvm_rec_enter(). This fixes a bug
   where the handler exits to user space and user space wants to modify
   the GPRS.
 * Some code rearrangement in rec_exit_ripas_change().
Changes since v2:
 * realm_set_ipa_state() now provides an output parameter for the
   top_iap that was changed. Use this to signal the VMM with the correct
   range that has been transitioned.
 * Adapt to previous patch changes.
---
 arch/arm64/include/asm/kvm_rmi.h |   4 +
 arch/arm64/kvm/Makefile          |   2 +-
 arch/arm64/kvm/arm.c             |  26 ++++-
 arch/arm64/kvm/rmi-exit.c        | 186 +++++++++++++++++++++++++++++++
 arch/arm64/kvm/rmi.c             |  42 +++++++
 5 files changed, 254 insertions(+), 6 deletions(-)
 create mode 100644 arch/arm64/kvm/rmi-exit.c

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index d99bf4fc3c39..feb534a6678e 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -84,6 +84,10 @@ void kvm_destroy_realm(struct kvm *kvm);
 void kvm_realm_destroy_rtts(struct kvm *kvm);
 void kvm_destroy_rec(struct kvm_vcpu *vcpu);
 
+int kvm_rec_enter(struct kvm_vcpu *vcpu);
+int kvm_rec_pre_enter(struct kvm_vcpu *vcpu);
+int handle_rec_exit(struct kvm_vcpu *vcpu, int rec_run_status);
+
 static inline bool kvm_realm_is_private_address(struct realm *realm,
 						unsigned long addr)
 {
diff --git a/arch/arm64/kvm/Makefile b/arch/arm64/kvm/Makefile
index ed3cf30eb06e..4a2d52fdb6a2 100644
--- a/arch/arm64/kvm/Makefile
+++ b/arch/arm64/kvm/Makefile
@@ -16,7 +16,7 @@ CFLAGS_handle_exit.o += -Wno-override-init
 kvm-y += arm.o mmu.o mmio.o psci.o hypercalls.o pvtime.o \
 	 inject_fault.o va_layout.o handle_exit.o config.o \
 	 guest.o debug.o reset.o sys_regs.o stacktrace.o \
-	 vgic-sys-reg-v3.o fpsimd.o pkvm.o rmi.o \
+	 vgic-sys-reg-v3.o fpsimd.o pkvm.o rmi.o rmi-exit.o \
 	 arch_timer.o trng.o vmid.o emulate-nested.o nested.o at.o \
 	 vgic/vgic.o vgic/vgic-init.o \
 	 vgic/vgic-irqfd.o vgic/vgic-v2.o \
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 21d9dfdb1ea0..ed88a203b892 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -1331,6 +1331,9 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 		if (ret > 0)
 			ret = check_vcpu_requests(vcpu);
 
+		if (ret > 0 && vcpu_is_rec(vcpu))
+			ret = kvm_rec_pre_enter(vcpu);
+
 		/*
 		 * Preparing the interrupts to be injected also
 		 * involves poking the GIC, which must be done in a
@@ -1378,7 +1381,10 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 		trace_kvm_entry(*vcpu_pc(vcpu));
 		guest_timing_enter_irqoff();
 
-		ret = kvm_arm_vcpu_enter_exit(vcpu);
+		if (vcpu_is_rec(vcpu))
+			ret = kvm_rec_enter(vcpu);
+		else
+			ret = kvm_arm_vcpu_enter_exit(vcpu);
 
 		vcpu->mode = OUTSIDE_GUEST_MODE;
 		vcpu->stat.exits++;
@@ -1424,7 +1430,9 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 		 * context synchronization event) is necessary to ensure that
 		 * pending interrupts are taken.
 		 */
-		if (ARM_EXCEPTION_CODE(ret) == ARM_EXCEPTION_IRQ) {
+		if (ARM_EXCEPTION_CODE(ret) == ARM_EXCEPTION_IRQ ||
+		    (vcpu_is_rec(vcpu) &&
+		     vcpu->arch.rec.run->exit.exit_reason == RMI_EXIT_IRQ)) {
 			local_irq_enable();
 			isb();
 			local_irq_disable();
@@ -1436,8 +1444,13 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 
 		trace_kvm_exit(ret, kvm_vcpu_trap_get_class(vcpu), *vcpu_pc(vcpu));
 
-		/* Exit types that need handling before we can be preempted */
-		handle_exit_early(vcpu, ret);
+		if (!vcpu_is_rec(vcpu)) {
+			/*
+			 * Exit types that need handling before we can be
+			 * preempted
+			 */
+			handle_exit_early(vcpu, ret);
+		}
 
 		kvm_nested_sync_hwstate(vcpu);
 
@@ -1462,7 +1475,10 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 			ret = ARM_EXCEPTION_IL;
 		}
 
-		ret = handle_exit(vcpu, ret);
+		if (vcpu_is_rec(vcpu))
+			ret = handle_rec_exit(vcpu, ret);
+		else
+			ret = handle_exit(vcpu, ret);
 	}
 
 	/* Tell userspace about in-kernel device output levels */
diff --git a/arch/arm64/kvm/rmi-exit.c b/arch/arm64/kvm/rmi-exit.c
new file mode 100644
index 000000000000..e7c51b6cf6ce
--- /dev/null
+++ b/arch/arm64/kvm/rmi-exit.c
@@ -0,0 +1,186 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2023 ARM Ltd.
+ */
+
+#include <linux/kvm_host.h>
+#include <kvm/arm_hypercalls.h>
+#include <kvm/arm_psci.h>
+
+#include <asm/rmi_smc.h>
+#include <asm/kvm_emulate.h>
+#include <asm/kvm_rmi.h>
+#include <asm/kvm_mmu.h>
+
+typedef int (*exit_handler_fn)(struct kvm_vcpu *vcpu);
+
+static int rec_exit_reason_notimpl(struct kvm_vcpu *vcpu)
+{
+	struct realm_rec *rec = &vcpu->arch.rec;
+
+	vcpu_err(vcpu, "Unhandled exit reason from realm (ESR: %#llx)\n",
+		 rec->run->exit.esr);
+	return -ENXIO;
+}
+
+static int rec_exit_sync_dabt(struct kvm_vcpu *vcpu)
+{
+	return kvm_handle_guest_abort(vcpu);
+}
+
+static int rec_exit_sync_iabt(struct kvm_vcpu *vcpu)
+{
+	struct realm_rec *rec = &vcpu->arch.rec;
+
+	vcpu_err(vcpu, "Unhandled instruction abort (ESR: %#llx).\n",
+		 rec->run->exit.esr);
+	return -ENXIO;
+}
+
+static int rec_exit_sys_reg(struct kvm_vcpu *vcpu)
+{
+	struct realm_rec *rec = &vcpu->arch.rec;
+	unsigned long esr = kvm_vcpu_get_esr(vcpu);
+	int rt = kvm_vcpu_sys_get_rt(vcpu);
+	bool is_write = (esr & ESR_ELx_SYS64_ISS_DIR_MASK) == ESR_ELx_SYS64_ISS_DIR_WRITE;
+	int ret;
+
+	if (is_write)
+		vcpu_set_reg(vcpu, rt, rec->run->exit.gprs[rt]);
+
+	ret = kvm_handle_sys_reg(vcpu);
+	if (!is_write)
+		rec->run->enter.gprs[rt] = vcpu_get_reg(vcpu, rt);
+
+	return ret;
+}
+
+static exit_handler_fn rec_exit_handlers[] = {
+	[0 ... ESR_ELx_EC_MAX]	= rec_exit_reason_notimpl,
+	[ESR_ELx_EC_SYS64]	= rec_exit_sys_reg,
+	[ESR_ELx_EC_DABT_LOW]	= rec_exit_sync_dabt,
+	[ESR_ELx_EC_IABT_LOW]	= rec_exit_sync_iabt
+};
+
+static int rec_exit_psci(struct kvm_vcpu *vcpu)
+{
+	struct realm_rec *rec = &vcpu->arch.rec;
+	int i;
+
+	for (i = 0; i < REC_RUN_GPRS; i++)
+		vcpu_set_reg(vcpu, i, rec->run->exit.gprs[i]);
+
+	return kvm_smccc_call_handler(vcpu);
+}
+
+static int rec_exit_ripas_change(struct kvm_vcpu *vcpu)
+{
+	struct kvm *kvm = vcpu->kvm;
+	struct realm *realm = &kvm->arch.realm;
+	struct realm_rec *rec = &vcpu->arch.rec;
+	unsigned long base = rec->run->exit.ripas_base;
+	unsigned long top = rec->run->exit.ripas_top;
+	unsigned long ripas = rec->run->exit.ripas_value;
+
+	if (!kvm_realm_is_private_address(realm, base) ||
+	    !kvm_realm_is_private_address(realm, top - 1)) {
+		vcpu_err(vcpu, "Invalid RIPAS_CHANGE for %#lx - %#lx, ripas: %#lx\n",
+			 base, top, ripas);
+		/* Set RMI_REJECT bit */
+		rec->run->enter.flags = REC_ENTER_FLAG_RIPAS_RESPONSE;
+		return -EINVAL;
+	}
+
+	/* Exit to VMM, the actual RIPAS change is done on next entry */
+	kvm_prepare_memory_fault_exit(vcpu, base, top - base, false, false,
+				      ripas == RMI_RAM);
+
+	/*
+	 * KVM_EXIT_MEMORY_FAULT requires an return code of -EFAULT, see the
+	 * API documentation
+	 */
+	return -EFAULT;
+}
+
+static void update_arch_timer_irq_lines(struct kvm_vcpu *vcpu)
+{
+	struct realm_rec *rec = &vcpu->arch.rec;
+
+	__vcpu_assign_sys_reg(vcpu, CNTV_CTL_EL0, rec->run->exit.cntv_ctl);
+	__vcpu_assign_sys_reg(vcpu, CNTV_CVAL_EL0, rec->run->exit.cntv_cval);
+	__vcpu_assign_sys_reg(vcpu, CNTP_CTL_EL0, rec->run->exit.cntp_ctl);
+	__vcpu_assign_sys_reg(vcpu, CNTP_CVAL_EL0, rec->run->exit.cntp_cval);
+
+	kvm_realm_timers_update(vcpu);
+}
+
+/*
+ * Return > 0 to return to guest, < 0 on error, 0 (and set exit_reason) on
+ * proper exit to userspace.
+ */
+int handle_rec_exit(struct kvm_vcpu *vcpu, int rec_run_ret)
+{
+	struct realm_rec *rec = &vcpu->arch.rec;
+	u8 esr_ec = ESR_ELx_EC(rec->run->exit.esr);
+	unsigned long status, index;
+
+	status = RMI_RETURN_STATUS(rec_run_ret);
+	index = RMI_RETURN_INDEX(rec_run_ret);
+
+	/*
+	 * If a PSCI_SYSTEM_OFF request raced with a vcpu executing, we might
+	 * see the following status code and index indicating an attempt to run
+	 * a REC when the RD state is SYSTEM_OFF.  In this case, we just need to
+	 * return to user space which can deal with the system event or will try
+	 * to run the KVM VCPU again, at which point we will no longer attempt
+	 * to enter the Realm because we will have a sleep request pending on
+	 * the VCPU as a result of KVM's PSCI handling.
+	 */
+	if (status == RMI_ERROR_REALM) {
+		vcpu->run->exit_reason = KVM_EXIT_SHUTDOWN;
+		return 0;
+	}
+
+	/*
+	 * If a VCPU has been turned on, but the REC state hasn't been updated
+	 * we may experience RMI_ERROR_REC. Exit to the userspace with -EAGAIN
+	 * for a retry.
+	 */
+	if (status == RMI_ERROR_REC)
+		return -EAGAIN;
+	if (rec_run_ret)
+		return -ENXIO;
+
+	vcpu->arch.fault.esr_el2 = rec->run->exit.esr;
+	vcpu->arch.fault.far_el2 = rec->run->exit.far;
+	/* HPFAR_EL2 is only valid for RMI_EXIT_SYNC */
+	vcpu->arch.fault.hpfar_el2 = 0;
+
+	update_arch_timer_irq_lines(vcpu);
+
+	/* Reset the emulation flags for the next run of the REC */
+	rec->run->enter.flags = 0;
+
+	switch (rec->run->exit.exit_reason) {
+	case RMI_EXIT_SYNC:
+		/*
+		 * HPFAR_EL2_NS is hijacked to indicate a valid HPFAR value,
+		 * see __get_fault_info()
+		 */
+		vcpu->arch.fault.hpfar_el2 = rec->run->exit.hpfar | HPFAR_EL2_NS;
+		return rec_exit_handlers[esr_ec](vcpu);
+	case RMI_EXIT_IRQ:
+	case RMI_EXIT_FIQ:
+	case RMI_EXIT_SERROR:
+		return 1;
+	case RMI_EXIT_PSCI:
+		return rec_exit_psci(vcpu);
+	case RMI_EXIT_RIPAS_CHANGE:
+		return rec_exit_ripas_change(vcpu);
+	}
+
+	kvm_pr_unimpl("Unsupported exit reason: %u\n",
+		      rec->run->exit.exit_reason);
+	vcpu->run->exit_reason = KVM_EXIT_INTERNAL_ERROR;
+	return 0;
+}
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 353a5ca45e78..d8a5fb12db2d 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -173,6 +173,48 @@ static int realm_ensure_created(struct kvm *kvm)
 	return -ENXIO;
 }
 
+/*
+ * kvm_rec_pre_enter - Complete operations before entering a REC
+ *
+ * Some operations require work to be completed before entering a realm. That
+ * work may require memory allocation so cannot be done in the kvm_rec_enter()
+ * call.
+ *
+ * Return: 1 if we should enter the guest
+ *	   0 if we should exit to userspace
+ *	   < 0 if we should exit to userspace, where the return value indicates
+ *	   an error
+ */
+int kvm_rec_pre_enter(struct kvm_vcpu *vcpu)
+{
+	struct realm_rec *rec = &vcpu->arch.rec;
+
+	if (kvm_realm_state(vcpu->kvm) != REALM_STATE_ACTIVE)
+		return -EINVAL;
+
+	switch (rec->run->exit.exit_reason) {
+	case RMI_EXIT_HOST_CALL:
+		for (int i = 0; i < REC_RUN_GPRS; i++)
+			rec->run->enter.gprs[i] = vcpu_get_reg(vcpu, i);
+		break;
+	}
+
+	return 1;
+}
+
+int noinstr kvm_rec_enter(struct kvm_vcpu *vcpu)
+{
+	struct realm_rec *rec = &vcpu->arch.rec;
+	int ret;
+
+	guest_state_enter_irqoff();
+	ret = rmi_rec_enter(virt_to_phys(rec->rec_page),
+			    virt_to_phys(rec->run));
+	guest_state_exit_irqoff();
+
+	return ret;
+}
+
 static int kvm_create_rec(struct kvm_vcpu *vcpu)
 {
 	struct user_pt_regs *vcpu_regs = vcpu_gp_regs(vcpu);

---

## [24] Steven Price — 2026-05-13
*Subject: [PATCH v14 23/44] arm64: RMI: Handle RMI_EXIT_RIPAS_CHANGE*

The guest can request that a region of it's protected address space is
switched between RIPAS_RAM and RIPAS_EMPTY (and back) using
RSI_IPA_STATE_SET. This causes a guest exit with the
RMI_EXIT_RIPAS_CHANGE code. We treat this as a request to convert a
protected region to unprotected (or back), exiting to the VMM to make
the necessary changes to the guest_memfd and memslot mappings. On the
next entry the RIPAS changes are committed by making RMI_RTT_SET_RIPAS
calls.

The VMM may wish to reject the RIPAS change requested by the guest. For
now it can only do this by no longer scheduling the VCPU as we don't
currently have a usecase for returning that rejection to the guest, but
by postponing the RMI_RTT_SET_RIPAS changes to entry we leave the door
open for adding a new ioctl in the future for this purpose.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v13:
 * Switch to the new RMI_RTT_UNPROT_UNMAP range-based API.
 * Drop ugly hack for RMM bug which errored when the RIPAS was already
   set to the desired value.
Changes since v12:
 * Switch to the new RMM v2.0 RMI_RTT_DATA_UNMAP which can unmap an
   address range.
Changes since v11:
 * Combine the "Allow VMM to set RIPAS" patch into this one to avoid
   adding functions before they are used.
 * Drop the CAP for setting RIPAS and adapt to changes from previous
   patches.
Changes since v10:
 * Add comment explaining the assignment of rec->run->exit.ripas_base in
   kvm_complete_ripas_change().
Changes since v8:
 * Make use of ripas_change() from a previous patch to implement
   realm_set_ipa_state().
 * Update exit.ripas_base after a RIPAS change so that, if instead of
   entering the guest we exit to user space, we don't attempt to repeat
   the RIPAS change (triggering an error from the RMM).
Changes since v7:
 * Rework the loop in realm_set_ipa_state() to make it clear when the
   'next' output value of rmi_rtt_set_ripas() is used.
New patch for v7: The code was previously split awkwardly between two
other patches.
---
 arch/arm64/include/asm/kvm_rmi.h |   6 +
 arch/arm64/kvm/mmu.c             |   8 +-
 arch/arm64/kvm/rmi.c             | 439 +++++++++++++++++++++++++++++++
 3 files changed, 450 insertions(+), 3 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index feb534a6678e..007249a13dbc 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -88,6 +88,12 @@ int kvm_rec_enter(struct kvm_vcpu *vcpu);
 int kvm_rec_pre_enter(struct kvm_vcpu *vcpu);
 int handle_rec_exit(struct kvm_vcpu *vcpu, int rec_run_status);
 
+void kvm_realm_unmap_range(struct kvm *kvm,
+			   unsigned long ipa,
+			   unsigned long size,
+			   bool unmap_private,
+			   bool may_block);
+
 static inline bool kvm_realm_is_private_address(struct realm *realm,
 						unsigned long addr)
 {
diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index eb56d4e7f21a..10ca9dbe40a0 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -319,6 +319,7 @@ static void invalidate_icache_guest_page(void *va, size_t size)
  * @start: The intermediate physical base address of the range to unmap
  * @size:  The size of the area to unmap
  * @may_block: Whether or not we are permitted to block
+ * @only_shared: If true then protected mappings should not be unmapped
  *
  * Clear a range of stage-2 mappings, lowering the various ref-counts.  Must
  * be called while holding mmu_lock (unless for freeing the stage2 pgd before
@@ -326,7 +327,7 @@ static void invalidate_icache_guest_page(void *va, size_t size)
  * with things behind our backs.
  */
 static void __unmap_stage2_range(struct kvm_s2_mmu *mmu, phys_addr_t start, u64 size,
-				 bool may_block)
+				 bool may_block, bool only_shared)
 {
 	struct kvm *kvm = kvm_s2_mmu_to_kvm(mmu);
 	phys_addr_t end = start + size;
@@ -343,7 +344,7 @@ void kvm_stage2_unmap_range(struct kvm_s2_mmu *mmu, phys_addr_t start,
 	if (kvm_vm_is_protected(kvm_s2_mmu_to_kvm(mmu)))
 		return;
 
-	__unmap_stage2_range(mmu, start, size, may_block);
+	__unmap_stage2_range(mmu, start, size, may_block, false);
 }
 
 void kvm_stage2_flush_range(struct kvm_s2_mmu *mmu, phys_addr_t addr, phys_addr_t end)
@@ -2418,7 +2419,8 @@ bool kvm_unmap_gfn_range(struct kvm *kvm, struct kvm_gfn_range *range)
 
 	__unmap_stage2_range(&kvm->arch.mmu, range->start << PAGE_SHIFT,
 			     (range->end - range->start) << PAGE_SHIFT,
-			     range->may_block);
+			     range->may_block,
+			     !(range->attr_filter & KVM_FILTER_PRIVATE));
 
 	kvm_nested_s2_unmap(kvm, range->may_block);
 	return false;
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index d8a5fb12db2d..a89873a5eb77 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -34,6 +34,91 @@ static int get_start_level(struct realm *realm)
 	return 4 - stage2_pgtable_levels(realm->ia_bits);
 }
 
+static int find_map_level(struct realm *realm,
+			  unsigned long start,
+			  unsigned long end)
+{
+	int level = KVM_PGTABLE_LAST_LEVEL;
+
+	while (level > get_start_level(realm)) {
+		unsigned long map_size = rmi_rtt_level_mapsize(level - 1);
+
+		if (!IS_ALIGNED(start, map_size) ||
+		    (start + map_size) > end)
+			break;
+
+		level--;
+	}
+
+	return level;
+}
+
+static unsigned long level_to_size(int level)
+{
+	switch (level) {
+	case 0:
+		return PAGE_SIZE;
+	case 1:
+		return PMD_SIZE;
+	case 2:
+		return PUD_SIZE;
+	case 3:
+		return P4D_SIZE;
+	}
+	WARN_ON(1);
+	return 0;
+}
+
+static int undelegate_range_desc(unsigned long desc)
+{
+	unsigned long size = level_to_size(RMI_ADDR_RANGE_SIZE(desc));
+	unsigned long count = RMI_ADDR_RANGE_COUNT(desc);
+	unsigned long addr = RMI_ADDR_RANGE_ADDR(desc);
+	unsigned long state = RMI_ADDR_RANGE_STATE(desc);
+
+	if (state == RMI_OP_MEM_UNDELEGATED)
+		return 0;
+
+	if (size * count == 0)
+		return 0;
+
+	return rmi_undelegate_range(addr, size * count);
+}
+
+static phys_addr_t alloc_delegated_granule(struct kvm_mmu_memory_cache *mc)
+{
+	phys_addr_t phys;
+	void *virt;
+
+	if (mc) {
+		virt = kvm_mmu_memory_cache_alloc(mc);
+	} else {
+		virt = (void *)__get_free_page(GFP_ATOMIC | __GFP_ZERO |
+					       __GFP_ACCOUNT);
+	}
+
+	if (!virt)
+		return PHYS_ADDR_MAX;
+
+	phys = virt_to_phys(virt);
+	if (rmi_delegate_page(phys)) {
+		free_page((unsigned long)virt);
+		return PHYS_ADDR_MAX;
+	}
+
+	return phys;
+}
+
+static phys_addr_t alloc_rtt(struct kvm_mmu_memory_cache *mc)
+{
+	phys_addr_t phys = alloc_delegated_granule(mc);
+
+	if (phys != PHYS_ADDR_MAX)
+		kvm_account_pgtable_pages(phys_to_virt(phys), 1);
+
+	return phys;
+}
+
 static void free_rtt(phys_addr_t phys)
 {
 	if (free_delegated_page(phys))
@@ -42,6 +127,32 @@ static void free_rtt(phys_addr_t phys)
 	kvm_account_pgtable_pages(phys_to_virt(phys), -1);
 }
 
+static int realm_rtt_create(struct realm *realm,
+			    unsigned long addr,
+			    int level,
+			    phys_addr_t phys)
+{
+	addr = ALIGN_DOWN(addr, rmi_rtt_level_mapsize(level - 1));
+	return rmi_rtt_create(virt_to_phys(realm->rd), phys, addr, level);
+}
+
+static int realm_rtt_fold(struct realm *realm,
+			  unsigned long addr,
+			  int level,
+			  phys_addr_t *rtt_granule)
+{
+	unsigned long out_rtt;
+	int ret;
+
+	addr = ALIGN_DOWN(addr, rmi_rtt_level_mapsize(level - 1));
+	ret = rmi_rtt_fold(virt_to_phys(realm->rd), addr, level, &out_rtt);
+
+	if (rtt_granule)
+		*rtt_granule = out_rtt;
+
+	return ret;
+}
+
 /*
  * realm_rtt_destroy - Destroy an RTT at @level for @addr.
  *
@@ -65,6 +176,38 @@ static int realm_rtt_destroy(struct realm *realm, unsigned long addr,
 	return ret;
 }
 
+static int realm_create_rtt_levels(struct realm *realm,
+				   unsigned long ipa,
+				   int level,
+				   int max_level,
+				   struct kvm_mmu_memory_cache *mc)
+{
+	while (level++ < max_level) {
+		phys_addr_t rtt = alloc_rtt(mc);
+		int ret;
+
+		if (rtt == PHYS_ADDR_MAX)
+			return -ENOMEM;
+
+		ret = realm_rtt_create(realm, ipa, level, rtt);
+		if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT &&
+		    RMI_RETURN_INDEX(ret) == level - 1) {
+			/* The RTT already exists, continue */
+			free_rtt(rtt);
+			continue;
+		}
+
+		if (ret) {
+			WARN(1, "Failed to create RTT at level %d: %d\n",
+			     level, ret);
+			free_rtt(rtt);
+			return -ENXIO;
+		}
+	}
+
+	return 0;
+}
+
 static int realm_tear_down_rtt_level(struct realm *realm, int level,
 				     unsigned long start, unsigned long end)
 {
@@ -159,6 +302,62 @@ static int realm_tear_down_rtt_range(struct realm *realm,
 					 start, end);
 }
 
+/*
+ * Returns 0 on successful fold, a negative value on error, a positive value if
+ * we were not able to fold all tables at this level.
+ */
+static int realm_fold_rtt_level(struct realm *realm, int level,
+				unsigned long start, unsigned long end)
+{
+	int not_folded = 0;
+	ssize_t map_size;
+	unsigned long addr, next_addr;
+
+	if (WARN_ON(level > KVM_PGTABLE_LAST_LEVEL))
+		return -EINVAL;
+
+	map_size = rmi_rtt_level_mapsize(level - 1);
+
+	for (addr = start; addr < end; addr = next_addr) {
+		phys_addr_t rtt_granule;
+		int ret;
+		unsigned long align_addr = ALIGN(addr, map_size);
+
+		next_addr = ALIGN(addr + 1, map_size);
+
+		ret = realm_rtt_fold(realm, align_addr, level, &rtt_granule);
+
+		switch (RMI_RETURN_STATUS(ret)) {
+		case RMI_SUCCESS:
+			free_rtt(rtt_granule);
+			break;
+		case RMI_ERROR_RTT:
+			if (level == KVM_PGTABLE_LAST_LEVEL ||
+			    RMI_RETURN_INDEX(ret) < level) {
+				not_folded++;
+				break;
+			}
+			/* Recurse a level deeper */
+			ret = realm_fold_rtt_level(realm,
+						   level + 1,
+						   addr,
+						   next_addr);
+			if (ret < 0) {
+				return ret;
+			} else if (ret == 0) {
+				/* Try again at this level */
+				next_addr = addr;
+			}
+			break;
+		default:
+			WARN_ON(1);
+			return -ENXIO;
+		}
+	}
+
+	return not_folded;
+}
+
 void kvm_realm_destroy_rtts(struct kvm *kvm)
 {
 	struct realm *realm = &kvm->arch.realm;
@@ -167,12 +366,249 @@ void kvm_realm_destroy_rtts(struct kvm *kvm)
 	realm_tear_down_rtt_range(realm, 0, (1UL << ia_bits));
 }
 
+static void realm_unmap_shared_range(struct kvm *kvm,
+				     unsigned long start,
+				     unsigned long end,
+				     bool may_block)
+{
+	struct realm *realm = &kvm->arch.realm;
+	unsigned long rd = virt_to_phys(realm->rd);
+	unsigned long next_addr, addr;
+	unsigned long shared_bit = BIT(realm->ia_bits - 1);
+
+	start |= shared_bit;
+	end |= shared_bit;
+
+	for (addr = start; addr < end; addr = next_addr) {
+		int ret;
+
+		ret = rmi_rtt_unprot_unmap(rd, addr, end, RMI_ADDR_TYPE_NONE,
+					   0, &next_addr, NULL, NULL);
+		switch (RMI_RETURN_STATUS(ret)) {
+		case RMI_SUCCESS:
+			break;
+		case RMI_ERROR_RTT: {
+			int err_level = RMI_RETURN_INDEX(ret);
+			int level = find_map_level(realm, addr, end);
+
+			if (err_level >= level) {
+				/* Nothing present, so skip */
+				next_addr = addr + rmi_rtt_level_mapsize(err_level);
+				break;
+			}
+
+			ret = realm_create_rtt_levels(realm, addr, err_level,
+						      level, NULL);
+			if (WARN_ON(ret))
+				return;
+			/* Retry with the RTT levels in place */
+			next_addr = addr;
+			break;
+		}
+		default:
+			WARN_ON(1);
+			return;
+		}
+
+		if (may_block)
+			cond_resched_rwlock_write(&kvm->mmu_lock);
+	}
+
+	realm_fold_rtt_level(realm, get_start_level(realm) + 1,
+			     start, end);
+}
+
+static void realm_unmap_private_range(struct kvm *kvm,
+				      unsigned long start,
+				      unsigned long end,
+				      bool may_block)
+{
+	struct realm *realm = &kvm->arch.realm;
+	unsigned long rd = virt_to_phys(realm->rd);
+	unsigned long next_addr, addr;
+	int ret;
+
+	for (addr = start; addr < end; addr = next_addr) {
+		unsigned long out_range;
+		unsigned long flags = RMI_ADDR_TYPE_SINGLE;
+		/* TODO: Optimise using RMI_ADDR_TYPE_LIST */
+
+retry:
+		ret = rmi_rtt_data_unmap(rd, addr, end, flags, 0,
+					 &next_addr, &out_range, NULL);
+
+		if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
+			phys_addr_t rtt;
+
+			if (next_addr > addr)
+				continue; /* UNASSIGNED */
+
+			rtt = alloc_rtt(NULL);
+			if (WARN_ON(rtt == PHYS_ADDR_MAX))
+				return;
+			ret = realm_rtt_create(realm, addr,
+					       RMI_RETURN_INDEX(ret) + 1, rtt);
+			if (WARN_ON(ret)) {
+				free_rtt(rtt);
+				return;
+			}
+			goto retry;
+		} else if (WARN_ON(ret)) {
+			continue;
+		}
+
+		ret = undelegate_range_desc(out_range);
+		if (WARN_ON(ret))
+			break;
+
+		if (may_block)
+			cond_resched_rwlock_write(&kvm->mmu_lock);
+	}
+
+	realm_fold_rtt_level(realm, get_start_level(realm) + 1,
+			     start, end);
+}
+
+void kvm_realm_unmap_range(struct kvm *kvm, unsigned long start,
+			   unsigned long size, bool unmap_private,
+			   bool may_block)
+{
+	unsigned long end = start + size;
+	struct realm *realm = &kvm->arch.realm;
+
+	if (!kvm_realm_is_created(kvm))
+		return;
+
+	end = min(BIT(realm->ia_bits - 1), end);
+
+	realm_unmap_shared_range(kvm, start, end, may_block);
+	if (unmap_private)
+		realm_unmap_private_range(kvm, start, end, may_block);
+}
+
+enum ripas_action {
+	RIPAS_INIT,
+	RIPAS_SET,
+};
+
+static int ripas_change(struct kvm *kvm,
+			struct kvm_vcpu *vcpu,
+			unsigned long ipa,
+			unsigned long end,
+			enum ripas_action action,
+			unsigned long *top_ipa)
+{
+	struct realm *realm = &kvm->arch.realm;
+	phys_addr_t rd_phys = virt_to_phys(realm->rd);
+	phys_addr_t rec_phys;
+	struct kvm_mmu_memory_cache *memcache = NULL;
+	int ret = 0;
+
+	if (vcpu) {
+		rec_phys = virt_to_phys(vcpu->arch.rec.rec_page);
+		memcache = &vcpu->arch.mmu_page_cache;
+
+		WARN_ON(action != RIPAS_SET);
+	} else {
+		WARN_ON(action != RIPAS_INIT);
+	}
+
+	while (ipa < end) {
+		unsigned long next = ~0;
+
+		switch (action) {
+		case RIPAS_INIT:
+			ret = rmi_rtt_init_ripas(rd_phys, ipa, end, &next);
+			break;
+		case RIPAS_SET:
+			ret = rmi_rtt_set_ripas(rd_phys, rec_phys, ipa, end,
+						&next);
+			break;
+		}
+
+		switch (RMI_RETURN_STATUS(ret)) {
+		case RMI_SUCCESS:
+			ipa = next;
+			break;
+		case RMI_ERROR_RTT: {
+			int err_level = RMI_RETURN_INDEX(ret);
+			int level = find_map_level(realm, ipa, end);
+
+			ret = realm_create_rtt_levels(realm, ipa, err_level,
+						      level, memcache);
+			if (ret)
+				return ret;
+			/* Retry with the RTT levels in place */
+			break;
+		}
+		default:
+			WARN_ON(1);
+			return -ENXIO;
+		}
+	}
+
+	if (top_ipa)
+		*top_ipa = ipa;
+
+	return 0;
+}
+
+static int realm_set_ipa_state(struct kvm_vcpu *vcpu,
+			       unsigned long start,
+			       unsigned long end,
+			       unsigned long ripas,
+			       unsigned long *top_ipa)
+{
+	struct kvm *kvm = vcpu->kvm;
+	int ret = ripas_change(kvm, vcpu, start, end, RIPAS_SET, top_ipa);
+
+	if (ripas == RMI_EMPTY && *top_ipa != start)
+		realm_unmap_private_range(kvm, start, *top_ipa, false);
+
+	return ret;
+}
+
 static int realm_ensure_created(struct kvm *kvm)
 {
 	/* Provided in later patch */
 	return -ENXIO;
 }
 
+static void kvm_complete_ripas_change(struct kvm_vcpu *vcpu)
+{
+	struct kvm *kvm = vcpu->kvm;
+	struct realm_rec *rec = &vcpu->arch.rec;
+	unsigned long base = rec->run->exit.ripas_base;
+	unsigned long top = rec->run->exit.ripas_top;
+	unsigned long ripas = rec->run->exit.ripas_value;
+	unsigned long top_ipa;
+	int ret;
+
+	do {
+		kvm_mmu_topup_memory_cache(&vcpu->arch.mmu_page_cache,
+					   kvm_mmu_cache_min_pages(vcpu->arch.hw_mmu));
+		write_lock(&kvm->mmu_lock);
+		ret = realm_set_ipa_state(vcpu, base, top, ripas, &top_ipa);
+		write_unlock(&kvm->mmu_lock);
+
+		if (WARN_RATELIMIT(ret && ret != -ENOMEM,
+				   "Unable to satisfy RIPAS_CHANGE for %#lx - %#lx, ripas: %#lx\n",
+				   base, top, ripas))
+			break;
+
+		base = top_ipa;
+	} while (base < top);
+
+	/*
+	 * If this function is called again before the REC_ENTER call then
+	 * avoid calling realm_set_ipa_state() again by changing to the value
+	 * of ripas_base for the part that has already been covered. The RMM
+	 * ignores the contains of the rec_exit structure so this doesn't
+	 * affect the RMM.
+	 */
+	rec->run->exit.ripas_base = base;
+}
+
 /*
  * kvm_rec_pre_enter - Complete operations before entering a REC
  *
@@ -197,6 +633,9 @@ int kvm_rec_pre_enter(struct kvm_vcpu *vcpu)
 		for (int i = 0; i < REC_RUN_GPRS; i++)
 			rec->run->enter.gprs[i] = vcpu_get_reg(vcpu, i);
 		break;
+	case RMI_EXIT_RIPAS_CHANGE:
+		kvm_complete_ripas_change(vcpu);
+		break;
 	}
 
 	return 1;

---

## [25] Steven Price — 2026-05-13
*Subject: [PATCH v14 24/44] KVM: arm64: Handle realm MMIO emulation*

MMIO emulation for a realm cannot be done directly with the VM's
registers as they are protected from the host. However, for emulatable
data aborts, the RMM uses GPRS[0] to provide the read/written value.
We can transfer this from/to the equivalent VCPU's register entry and
then depend on the generic MMIO handling code in KVM.

For a MMIO read, the value is placed in the shared RecExit structure
during kvm_handle_mmio_return() rather than in the VCPU's register
entry.

Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
---
Changes since v7:
 * New comment for rec_exit_sync_dabt() explaining the call to
   vcpu_set_reg().
Changes since v5:
 * Inject SEA to the guest is an emulatable MMIO access triggers a data
   abort.
 * kvm_handle_mmio_return() - disable kvm_incr_pc() for a REC (as the PC
   isn't under the host's control) and move the REC_ENTER_EMULATED_MMIO
   flag setting to this location (as that tells the RMM to skip the
   instruction).
---
 arch/arm64/kvm/inject_fault.c |  4 +++-
 arch/arm64/kvm/mmio.c         | 16 ++++++++++++----
 arch/arm64/kvm/rmi-exit.c     | 14 ++++++++++++++
 3 files changed, 29 insertions(+), 5 deletions(-)

diff --git a/arch/arm64/kvm/inject_fault.c b/arch/arm64/kvm/inject_fault.c
index 89982bd3345f..6492397b73d7 100644
--- a/arch/arm64/kvm/inject_fault.c
+++ b/arch/arm64/kvm/inject_fault.c
@@ -228,7 +228,9 @@ static void inject_abt32(struct kvm_vcpu *vcpu, bool is_pabt, u32 addr)
 
 static void __kvm_inject_sea(struct kvm_vcpu *vcpu, bool iabt, u64 addr)
 {
-	if (vcpu_el1_is_32bit(vcpu))
+	if (unlikely(vcpu_is_rec(vcpu)))
+		vcpu->arch.rec.run->enter.flags |= REC_ENTER_FLAG_INJECT_SEA;
+	else if (vcpu_el1_is_32bit(vcpu))
 		inject_abt32(vcpu, iabt, addr);
 	else
 		inject_abt64(vcpu, iabt, addr);
diff --git a/arch/arm64/kvm/mmio.c b/arch/arm64/kvm/mmio.c
index e2285ed8c91d..6a8cb927fcca 100644
--- a/arch/arm64/kvm/mmio.c
+++ b/arch/arm64/kvm/mmio.c
@@ -6,6 +6,7 @@
 
 #include <linux/kvm_host.h>
 #include <asm/kvm_emulate.h>
+#include <asm/rmi_smc.h>
 #include <trace/events/kvm.h>
 
 #include "trace.h"
@@ -138,14 +139,21 @@ int kvm_handle_mmio_return(struct kvm_vcpu *vcpu)
 		trace_kvm_mmio(KVM_TRACE_MMIO_READ, len, run->mmio.phys_addr,
 			       &data);
 		data = vcpu_data_host_to_guest(vcpu, data, len);
-		vcpu_set_reg(vcpu, kvm_vcpu_dabt_get_rd(vcpu), data);
+
+		if (vcpu_is_rec(vcpu))
+			vcpu->arch.rec.run->enter.gprs[0] = data;
+		else
+			vcpu_set_reg(vcpu, kvm_vcpu_dabt_get_rd(vcpu), data);
 	}
 
 	/*
 	 * The MMIO instruction is emulated and should not be re-executed
 	 * in the guest.
 	 */
-	kvm_incr_pc(vcpu);
+	if (vcpu_is_rec(vcpu))
+		vcpu->arch.rec.run->enter.flags |= REC_ENTER_FLAG_EMULATED_MMIO;
+	else
+		kvm_incr_pc(vcpu);
 
 	return 1;
 }
@@ -167,14 +175,14 @@ int io_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa)
 	 * No valid syndrome? Ask userspace for help if it has
 	 * volunteered to do so, and bail out otherwise.
 	 *
-	 * In the protected VM case, there isn't much userspace can do
+	 * In the protected/realm VM case, there isn't much userspace can do
 	 * though, so directly deliver an exception to the guest.
 	 */
 	if (!kvm_vcpu_dabt_isvalid(vcpu)) {
 		trace_kvm_mmio_nisv(*vcpu_pc(vcpu), esr,
 				    kvm_vcpu_get_hfar(vcpu), fault_ipa);
 
-		if (vcpu_is_protected(vcpu))
+		if (vcpu_is_protected(vcpu) || vcpu_is_rec(vcpu))
 			return kvm_inject_sea_dabt(vcpu, kvm_vcpu_get_hfar(vcpu));
 
 		if (test_bit(KVM_ARCH_FLAG_RETURN_NISV_IO_ABORT_TO_USER,
diff --git a/arch/arm64/kvm/rmi-exit.c b/arch/arm64/kvm/rmi-exit.c
index e7c51b6cf6ce..8ec0d179eba2 100644
--- a/arch/arm64/kvm/rmi-exit.c
+++ b/arch/arm64/kvm/rmi-exit.c
@@ -25,6 +25,20 @@ static int rec_exit_reason_notimpl(struct kvm_vcpu *vcpu)
 
 static int rec_exit_sync_dabt(struct kvm_vcpu *vcpu)
 {
+	struct realm_rec *rec = &vcpu->arch.rec;
+
+	/*
+	 * In the case of a write, copy over gprs[0] to the target GPR,
+	 * preparing to handle MMIO write fault. The content to be written has
+	 * been saved to gprs[0] by the RMM (even if another register was used
+	 * by the guest). In the case of normal memory access this is redundant
+	 * (the guest will replay the instruction), but the overhead is
+	 * minimal.
+	 */
+	if (kvm_vcpu_dabt_iswrite(vcpu) && kvm_vcpu_dabt_isvalid(vcpu))
+		vcpu_set_reg(vcpu, kvm_vcpu_dabt_get_rd(vcpu),
+			     rec->run->exit.gprs[0]);
+
 	return kvm_handle_guest_abort(vcpu);
 }

---

## [26] Steven Price — 2026-05-13
*Subject: [PATCH v14 25/44] KVM: arm64: Expose support for private memory*

Select KVM_GENERIC_MEMORY_ATTRIBUTES and provide the necessary support
functions.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v13:
 * Also update documentation to show that KVM_CAP_MEMORY_ATTRIBUTES is
   used on arm64.
Changes since v12:
 * Only define kvm_arch_has_private_mem() when
   CONFIG_KVM_GENERIC_MEMORY_ATTRIBUTES is set to avoid build issues
   when KVM is disabled.
Changes since v10:
 * KVM_GENERIC_PRIVATE_MEM replacd with KVM_GENERIC_MEMORY_ATTRIBUTES.
Changes since v9:
 * Drop the #ifdef CONFIG_KVM_PRIVATE_MEM guard from the definition of
   kvm_arch_has_private_mem()
Changes since v2:
 * Switch kvm_arch_has_private_mem() to a macro to avoid overhead of a
   function call.
 * Guard definitions of kvm_arch_{pre,post}_set_memory_attributes() with
   #ifdef CONFIG_KVM_GENERIC_MEMORY_ATTRIBUTES.
 * Early out in kvm_arch_post_set_memory_attributes() if the WARN_ON
   should trigger.
---
 Documentation/virt/kvm/api.rst    |  2 +-
 arch/arm64/include/asm/kvm_host.h |  4 ++++
 arch/arm64/kvm/Kconfig            |  1 +
 arch/arm64/kvm/mmu.c              | 24 ++++++++++++++++++++++++
 4 files changed, 30 insertions(+), 1 deletion(-)

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index 31a5919d8d5f..a47c60490475 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -6379,7 +6379,7 @@ Returns -EINVAL if called on a protected VM.
 -------------------------------
 
 :Capability: KVM_CAP_MEMORY_ATTRIBUTES
-:Architectures: x86
+:Architectures: x86, arm64
 :Type: vm ioctl
 :Parameters: struct kvm_memory_attributes (in)
 :Returns: 0 on success, <0 on error
diff --git a/arch/arm64/include/asm/kvm_host.h b/arch/arm64/include/asm/kvm_host.h
index 39b5de03d0fe..11e7b629c950 100644
--- a/arch/arm64/include/asm/kvm_host.h
+++ b/arch/arm64/include/asm/kvm_host.h
@@ -1531,6 +1531,10 @@ struct kvm *kvm_arch_alloc_vm(void);
 
 #define vcpu_is_protected(vcpu)		kvm_vm_is_protected((vcpu)->kvm)
 
+#ifdef CONFIG_KVM_GENERIC_MEMORY_ATTRIBUTES
+#define kvm_arch_has_private_mem(kvm) ((kvm)->arch.is_realm)
+#endif
+
 int kvm_arm_vcpu_finalize(struct kvm_vcpu *vcpu, int feature);
 bool kvm_arm_vcpu_is_finalized(struct kvm_vcpu *vcpu);
 
diff --git a/arch/arm64/kvm/Kconfig b/arch/arm64/kvm/Kconfig
index 449154f9a485..4e16719fda22 100644
--- a/arch/arm64/kvm/Kconfig
+++ b/arch/arm64/kvm/Kconfig
@@ -37,6 +37,7 @@ menuconfig KVM
 	select SCHED_INFO
 	select GUEST_PERF_EVENTS if PERF_EVENTS
 	select KVM_GUEST_MEMFD
+	select KVM_GENERIC_MEMORY_ATTRIBUTES
 	help
 	  Support hosting virtualized guest machines.
 
diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index 10ca9dbe40a0..ac2a0f0106b0 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -2684,6 +2684,30 @@ int kvm_arch_prepare_memory_region(struct kvm *kvm,
 	return ret;
 }
 
+#ifdef CONFIG_KVM_GENERIC_MEMORY_ATTRIBUTES
+bool kvm_arch_pre_set_memory_attributes(struct kvm *kvm,
+					struct kvm_gfn_range *range)
+{
+	WARN_ON_ONCE(!kvm_arch_has_private_mem(kvm));
+	return false;
+}
+
+bool kvm_arch_post_set_memory_attributes(struct kvm *kvm,
+					 struct kvm_gfn_range *range)
+{
+	if (WARN_ON_ONCE(!kvm_arch_has_private_mem(kvm)))
+		return false;
+
+	if (range->arg.attributes & KVM_MEMORY_ATTRIBUTE_PRIVATE)
+		range->attr_filter = KVM_FILTER_SHARED;
+	else
+		range->attr_filter = KVM_FILTER_PRIVATE;
+	kvm_unmap_gfn_range(kvm, range);
+
+	return false;
+}
+#endif
+
 void kvm_arch_free_memslot(struct kvm *kvm, struct kvm_memory_slot *slot)
 {
 }

---

## [27] Steven Price — 2026-05-13
*Subject: [PATCH v14 26/44] arm64: RMI: Allow populating initial contents*

The VMM needs to populate the realm with some data before starting (e.g.
a kernel and initrd). This is measured by the RMM and used as part of
the attestation later on.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v13:
 * Rename realm_create_protected_data_page() to realm_data_map_init().
Changes since v12:
 * The ioctl now updates the structure with the amount populated rather
   than returning this through the ioctl return code.
 * Use the new RMM v2.0 range based RMI calls.
 * Adapt to upstream changes in kvm_gmem_populate().
Changes since v11:
 * The multiplex CAP is gone and there's a new ioctl which makes use of
   the generic kvm_gmem_populate() functionality.
Changes since v7:
 * Improve the error codes.
 * Other minor changes from review.
Changes since v6:
 * Handle host potentially having a larger page size than the RMM
   granule.
 * Drop historic "par" (protected address range) from
   populate_par_region() - it doesn't exist within the current
   architecture.
 * Add a cond_resched() call in kvm_populate_realm().
Changes since v5:
 * Refactor to use PFNs rather than tracking struct page in
   realm_create_protected_data_page().
 * Pull changes from a later patch (in the v5 series) for accessing
   pages from a guest memfd.
 * Do the populate in chunks to avoid holding locks for too long and
   triggering RCU stall warnings.
---
 arch/arm64/include/asm/kvm_rmi.h |   4 ++
 arch/arm64/kvm/Kconfig           |   1 +
 arch/arm64/kvm/arm.c             |  13 ++++
 arch/arm64/kvm/rmi.c             | 106 +++++++++++++++++++++++++++++++
 4 files changed, 124 insertions(+)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index 007249a13dbc..a2b6bc412a22 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -88,6 +88,10 @@ int kvm_rec_enter(struct kvm_vcpu *vcpu);
 int kvm_rec_pre_enter(struct kvm_vcpu *vcpu);
 int handle_rec_exit(struct kvm_vcpu *vcpu, int rec_run_status);
 
+struct kvm_arm_rmi_populate;
+
+int kvm_arm_rmi_populate(struct kvm *kvm,
+			 struct kvm_arm_rmi_populate *arg);
 void kvm_realm_unmap_range(struct kvm *kvm,
 			   unsigned long ipa,
 			   unsigned long size,
diff --git a/arch/arm64/kvm/Kconfig b/arch/arm64/kvm/Kconfig
index 4e16719fda22..d0cd011cf672 100644
--- a/arch/arm64/kvm/Kconfig
+++ b/arch/arm64/kvm/Kconfig
@@ -38,6 +38,7 @@ menuconfig KVM
 	select GUEST_PERF_EVENTS if PERF_EVENTS
 	select KVM_GUEST_MEMFD
 	select KVM_GENERIC_MEMORY_ATTRIBUTES
+	select HAVE_KVM_ARCH_GMEM_POPULATE
 	help
 	  Support hosting virtualized guest machines.
 
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index ed88a203b892..073ba9181da9 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -2131,6 +2131,19 @@ int kvm_arch_vm_ioctl(struct file *filp, unsigned int ioctl, unsigned long arg)
 			return -EFAULT;
 		return kvm_vm_ioctl_get_reg_writable_masks(kvm, &range);
 	}
+	case KVM_ARM_RMI_POPULATE: {
+		struct kvm_arm_rmi_populate req;
+		int ret;
+
+		if (!kvm_is_realm(kvm))
+			return -ENXIO;
+		if (copy_from_user(&req, argp, sizeof(req)))
+			return -EFAULT;
+		ret = kvm_arm_rmi_populate(kvm, &req);
+		if (copy_to_user(argp, &req, sizeof(req)))
+			return -EFAULT;
+		return ret;
+	}
 	default:
 		return -EINVAL;
 	}
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index a89873a5eb77..209087bcf399 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -486,6 +486,75 @@ void kvm_realm_unmap_range(struct kvm *kvm, unsigned long start,
 		realm_unmap_private_range(kvm, start, end, may_block);
 }
 
+static int realm_data_map_init(struct kvm *kvm, unsigned long ipa,
+			       kvm_pfn_t dst_pfn, kvm_pfn_t src_pfn,
+			       unsigned long flags)
+{
+	struct realm *realm = &kvm->arch.realm;
+	phys_addr_t rd = virt_to_phys(realm->rd);
+	phys_addr_t dst_phys, src_phys;
+	int ret;
+
+	dst_phys = __pfn_to_phys(dst_pfn);
+	src_phys = __pfn_to_phys(src_pfn);
+
+	if (rmi_delegate_page(dst_phys))
+		return -ENXIO;
+
+	ret = rmi_rtt_data_map_init(rd, dst_phys, ipa, src_phys, flags);
+	if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
+		/* Create missing RTTs and retry */
+		int level = RMI_RETURN_INDEX(ret);
+
+		KVM_BUG_ON(level == KVM_PGTABLE_LAST_LEVEL, kvm);
+
+		ret = realm_create_rtt_levels(realm, ipa, level,
+					      KVM_PGTABLE_LAST_LEVEL, NULL);
+		if (!ret) {
+			ret = rmi_rtt_data_map_init(rd, dst_phys, ipa, src_phys,
+						    flags);
+		}
+	}
+
+	if (ret) {
+		if (WARN_ON(rmi_undelegate_page(dst_phys))) {
+			/* Undelegate failed, so we leak the page */
+			get_page(pfn_to_page(dst_pfn));
+		}
+	}
+
+	return ret;
+}
+
+static int populate_region_cb(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
+			      struct page *src_page, void *opaque)
+{
+	unsigned long data_flags = *(unsigned long *)opaque;
+	phys_addr_t ipa = gfn_to_gpa(gfn);
+
+	if (!src_page)
+		return -EOPNOTSUPP;
+
+	return realm_data_map_init(kvm, ipa, pfn, page_to_pfn(src_page),
+				   data_flags);
+}
+
+static long populate_region(struct kvm *kvm,
+			    gfn_t base_gfn,
+			    unsigned long pages,
+			    u64 uaddr,
+			    unsigned long data_flags)
+{
+	long ret = 0;
+
+	mutex_lock(&kvm->slots_lock);
+	ret = kvm_gmem_populate(kvm, base_gfn, u64_to_user_ptr(uaddr), pages,
+				populate_region_cb, &data_flags);
+	mutex_unlock(&kvm->slots_lock);
+
+	return ret;
+}
+
 enum ripas_action {
 	RIPAS_INIT,
 	RIPAS_SET,
@@ -574,6 +643,43 @@ static int realm_ensure_created(struct kvm *kvm)
 	return -ENXIO;
 }
 
+int kvm_arm_rmi_populate(struct kvm *kvm,
+			 struct kvm_arm_rmi_populate *args)
+{
+	unsigned long data_flags = 0;
+	unsigned long ipa_start = args->base;
+	unsigned long ipa_end = ipa_start + args->size;
+	long pages_populated;
+	int ret;
+
+	if (args->reserved ||
+	    (args->flags & ~KVM_ARM_RMI_POPULATE_FLAGS_MEASURE) ||
+	    !IS_ALIGNED(ipa_start, PAGE_SIZE) ||
+	    !IS_ALIGNED(ipa_end, PAGE_SIZE) ||
+	    !IS_ALIGNED(args->source_uaddr, PAGE_SIZE))
+		return -EINVAL;
+
+	ret = realm_ensure_created(kvm);
+	if (ret)
+		return ret;
+
+	if (args->flags & KVM_ARM_RMI_POPULATE_FLAGS_MEASURE)
+		data_flags |= RMI_MEASURE_CONTENT;
+
+	pages_populated = populate_region(kvm, gpa_to_gfn(ipa_start),
+					  args->size >> PAGE_SHIFT,
+					  args->source_uaddr, data_flags);
+
+	if (pages_populated < 0)
+		return pages_populated;
+
+	args->size -= pages_populated << PAGE_SHIFT;
+	args->source_uaddr += pages_populated << PAGE_SHIFT;
+	args->base += pages_populated << PAGE_SHIFT;
+
+	return 0;
+}
+
 static void kvm_complete_ripas_change(struct kvm_vcpu *vcpu)
 {
 	struct kvm *kvm = vcpu->kvm;

---

## [28] Steven Price — 2026-05-13
*Subject: [PATCH v14 27/44] arm64: RMI: Set RIPAS of initial memslots*

The memory which the realm guest accesses must be set to RIPAS_RAM.
Iterate over the memslots and set all gmem memslots to RIPAS_RAM.

Signed-off-by: Steven Price <steven.price@arm.com>
---
New patch for v12.
---
 arch/arm64/kvm/rmi.c | 36 ++++++++++++++++++++++++++++++++++++
 1 file changed, 36 insertions(+)

diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 209087bcf399..fb96bcaa73ed 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -637,12 +637,44 @@ static int realm_set_ipa_state(struct kvm_vcpu *vcpu,
 	return ret;
 }
 
+static int realm_init_ipa_state(struct kvm *kvm,
+				unsigned long gfn,
+				unsigned long pages)
+{
+	return ripas_change(kvm, NULL, gfn_to_gpa(gfn), gfn_to_gpa(gfn + pages),
+			    RIPAS_INIT, NULL);
+}
+
 static int realm_ensure_created(struct kvm *kvm)
 {
 	/* Provided in later patch */
 	return -ENXIO;
 }
 
+static int set_ripas_of_protected_regions(struct kvm *kvm)
+{
+	struct kvm_memslots *slots;
+	struct kvm_memory_slot *memslot;
+	int idx, bkt;
+	int ret = 0;
+
+	idx = srcu_read_lock(&kvm->srcu);
+
+	slots = kvm_memslots(kvm);
+	kvm_for_each_memslot(memslot, bkt, slots) {
+		if (!kvm_slot_has_gmem(memslot))
+			continue;
+
+		ret = realm_init_ipa_state(kvm, memslot->base_gfn,
+					   memslot->npages);
+		if (ret)
+			break;
+	}
+	srcu_read_unlock(&kvm->srcu, idx);
+
+	return ret;
+}
+
 int kvm_arm_rmi_populate(struct kvm *kvm,
 			 struct kvm_arm_rmi_populate *args)
 {
@@ -890,6 +922,10 @@ int kvm_activate_realm(struct kvm *kvm)
 			return ret;
 	}
 
+	ret = set_ripas_of_protected_regions(kvm);
+	if (ret)
+		return ret;
+
 	ret = rmi_realm_activate(virt_to_phys(realm->rd));
 	if (ret)
 		return -ENXIO;

---

## [29] Steven Price — 2026-05-13
*Subject: [PATCH v14 28/44] arm64: RMI: Create the realm descriptor*

Creating a realm involves first creating a realm descriptor (RD). This
involves passing the configuration information to the RMM. Do this as
part of realm_ensure_created() so that the realm is created when it is
first needed.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v13:
 * The RMM no longer uses AUX granules, so no need to ask it how many it
   needs.
 * Adapted to other changes.
Changes since v12:
 * Since RMM page size is now equal to the host's page size various
   calculations are simplified.
 * Switch to using range based APIs to delegate/undelegate.
 * VMID handling is now handled entirely by the RMM.
---
 arch/arm64/kvm/rmi.c | 88 +++++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 86 insertions(+), 2 deletions(-)

diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index fb96bcaa73ed..cae29fd3353c 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -418,6 +418,77 @@ static void realm_unmap_shared_range(struct kvm *kvm,
 			     start, end);
 }
 
+static int realm_create_rd(struct kvm *kvm)
+{
+	struct realm *realm = &kvm->arch.realm;
+	struct realm_params *params = realm->params;
+	void *rd = NULL;
+	phys_addr_t rd_phys, params_phys;
+	size_t pgd_size = kvm_pgtable_stage2_pgd_size(kvm->arch.mmu.vtcr);
+	int r;
+
+	realm->ia_bits = VTCR_EL2_IPA(kvm->arch.mmu.vtcr);
+
+	if (WARN_ON(realm->rd || !realm->params))
+		return -EEXIST;
+
+	rd = (void *)__get_free_page(GFP_KERNEL_ACCOUNT);
+	if (!rd)
+		return -ENOMEM;
+
+	rd_phys = virt_to_phys(rd);
+	if (rmi_delegate_page(rd_phys)) {
+		r = -ENXIO;
+		goto free_rd;
+	}
+
+	if (rmi_delegate_range(kvm->arch.mmu.pgd_phys, pgd_size)) {
+		r = -ENXIO;
+		goto out_undelegate_tables;
+	}
+
+	params->s2sz = VTCR_EL2_IPA(kvm->arch.mmu.vtcr);
+	params->rtt_level_start = get_start_level(realm);
+	params->rtt_num_start = pgd_size / PAGE_SIZE;
+	params->rtt_base = kvm->arch.mmu.pgd_phys;
+
+	if (kvm->arch.arm_pmu) {
+		params->pmu_num_ctrs = kvm->arch.nr_pmu_counters;
+		params->flags |= RMI_REALM_PARAM_FLAG_PMU;
+	}
+
+	if (kvm_lpa2_is_enabled())
+		params->flags |= RMI_REALM_PARAM_FLAG_LPA2;
+
+	params_phys = virt_to_phys(params);
+
+	if (rmi_realm_create(rd_phys, params_phys)) {
+		r = -ENXIO;
+		goto out_undelegate_tables;
+	}
+
+	realm->rd = rd;
+	kvm_set_realm_state(kvm, REALM_STATE_NEW);
+	/* The realm is up, free the parameters.  */
+	free_page((unsigned long)realm->params);
+	realm->params = NULL;
+
+	return 0;
+
+out_undelegate_tables:
+	if (WARN_ON(rmi_undelegate_range(kvm->arch.mmu.pgd_phys, pgd_size))) {
+		/* Leak the pages if they cannot be returned */
+		kvm->arch.mmu.pgt = NULL;
+	}
+	if (WARN_ON(rmi_undelegate_page(rd_phys))) {
+		/* Leak the page if it isn't returned */
+		return r;
+	}
+free_rd:
+	free_page((unsigned long)rd);
+	return r;
+}
+
 static void realm_unmap_private_range(struct kvm *kvm,
 				      unsigned long start,
 				      unsigned long end,
@@ -647,8 +718,21 @@ static int realm_init_ipa_state(struct kvm *kvm,
 
 static int realm_ensure_created(struct kvm *kvm)
 {
-	/* Provided in later patch */
-	return -ENXIO;
+	int ret;
+
+	switch (kvm_realm_state(kvm)) {
+	case REALM_STATE_NONE:
+		break;
+	case REALM_STATE_NEW:
+		return 0;
+	case REALM_STATE_DEAD:
+		return -ENXIO;
+	default:
+		return -EBUSY;
+	}
+
+	ret = realm_create_rd(kvm);
+	return ret;
 }
 
 static int set_ripas_of_protected_regions(struct kvm *kvm)

---

## [30] Steven Price — 2026-05-13
*Subject: [PATCH v14 29/44] arm64: RMI: Runtime faulting of memory*

At runtime if the realm guest accesses memory which hasn't yet been
mapped then KVM needs to either populate the region or fault the guest.

For memory in the lower (protected) region of IPA a fresh page is
provided to the RMM which will zero the contents. For memory in the
upper (shared) region of IPA, the memory from the memslot is mapped
into the realm VM non secure.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v13:
 * Numerous changes due to rebasing.
 * Fix addr_range_desc() to encode the correct block size.
Changes since v12:
 * Switch to RMM v2.0 range based APIs.
Changes since v11:
 * Adapt to upstream changes.
Changes since v10:
 * RME->RMI renaming.
 * Adapt to upstream gmem changes.
Changes since v9:
 * Fix call to kvm_stage2_unmap_range() in kvm_free_stage2_pgd() to set
   may_block to avoid stall warnings.
 * Minor coding style fixes.
Changes since v8:
 * Propagate the may_block flag.
 * Minor comments and coding style changes.
Changes since v7:
 * Remove redundant WARN_ONs for realm_create_rtt_levels() - it will
   internally WARN when necessary.
Changes since v6:
 * Handle PAGE_SIZE being larger than RMM granule size.
 * Some minor renaming following review comments.
Changes since v5:
 * Reduce use of struct page in preparation for supporting the RMM
   having a different page size to the host.
 * Handle a race when delegating a page where another CPU has faulted on
   a the same page (and already delegated the physical page) but not yet
   mapped it. In this case simply return to the guest to either use the
   mapping from the other CPU (or refault if the race is lost).
 * The changes to populate_par_region() are moved into the previous
   patch where they belong.
Changes since v4:
 * Code cleanup following review feedback.
 * Drop the PTE_SHARED bit when creating unprotected page table entries.
   This is now set by the RMM and the host has no control of it and the
   spec requires the bit to be set to zero.
Changes since v2:
 * Avoid leaking memory if failing to map it in the realm.
 * Correctly mask RTT based on LPA2 flag (see rtt_get_phys()).
 * Adapt to changes in previous patches.
---
 arch/arm64/include/asm/kvm_emulate.h |   8 ++
 arch/arm64/include/asm/kvm_rmi.h     |  12 ++
 arch/arm64/kvm/mmu.c                 | 128 ++++++++++++++++----
 arch/arm64/kvm/rmi.c                 | 173 +++++++++++++++++++++++++++
 4 files changed, 301 insertions(+), 20 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_emulate.h b/arch/arm64/include/asm/kvm_emulate.h
index 2e69fe494716..8b6f9d26b5d8 100644
--- a/arch/arm64/include/asm/kvm_emulate.h
+++ b/arch/arm64/include/asm/kvm_emulate.h
@@ -712,6 +712,14 @@ static inline bool kvm_realm_is_created(struct kvm *kvm)
 	return kvm_is_realm(kvm) && kvm_realm_state(kvm) != REALM_STATE_NONE;
 }
 
+static inline gpa_t kvm_gpa_from_fault(struct kvm *kvm, phys_addr_t ipa)
+{
+	if (!kvm_is_realm(kvm))
+		return ipa;
+
+	return ipa & ~BIT(kvm->arch.realm.ia_bits - 1);
+}
+
 static inline bool vcpu_is_rec(const struct kvm_vcpu *vcpu)
 {
 	return kvm_is_realm(vcpu->kvm);
diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index a2b6bc412a22..b65cfec10dee 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -6,6 +6,7 @@
 #ifndef __ASM_KVM_RMI_H
 #define __ASM_KVM_RMI_H
 
+#include <asm/kvm_pgtable.h>
 #include <asm/rmi_smc.h>
 
 /**
@@ -97,6 +98,17 @@ void kvm_realm_unmap_range(struct kvm *kvm,
 			   unsigned long size,
 			   bool unmap_private,
 			   bool may_block);
+int realm_map_protected(struct kvm *kvm,
+			unsigned long base_ipa,
+			kvm_pfn_t pfn,
+			unsigned long size,
+			struct kvm_mmu_memory_cache *memcache);
+int realm_map_non_secure(struct realm *realm,
+			 unsigned long ipa,
+			 kvm_pfn_t pfn,
+			 unsigned long size,
+			 enum kvm_pgtable_prot prot,
+			 struct kvm_mmu_memory_cache *memcache);
 
 static inline bool kvm_realm_is_private_address(struct realm *realm,
 						unsigned long addr)
diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index ac2a0f0106b0..776ffe56d17e 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -334,8 +334,15 @@ static void __unmap_stage2_range(struct kvm_s2_mmu *mmu, phys_addr_t start, u64
 
 	lockdep_assert_held_write(&kvm->mmu_lock);
 	WARN_ON(size & ~PAGE_MASK);
-	WARN_ON(stage2_apply_range(mmu, start, end, KVM_PGT_FN(kvm_pgtable_stage2_unmap),
-				   may_block));
+
+	if (kvm_is_realm(kvm)) {
+		kvm_realm_unmap_range(kvm, start, size, !only_shared,
+				      may_block);
+	} else {
+		WARN_ON(stage2_apply_range(mmu, start, end,
+					   KVM_PGT_FN(kvm_pgtable_stage2_unmap),
+					   may_block));
+	}
 }
 
 void kvm_stage2_unmap_range(struct kvm_s2_mmu *mmu, phys_addr_t start,
@@ -358,7 +365,10 @@ static void stage2_flush_memslot(struct kvm *kvm,
 	phys_addr_t addr = memslot->base_gfn << PAGE_SHIFT;
 	phys_addr_t end = addr + PAGE_SIZE * memslot->npages;
 
-	kvm_stage2_flush_range(&kvm->arch.mmu, addr, end);
+	if (kvm_is_realm(kvm))
+		kvm_realm_unmap_range(kvm, addr, end - addr, false, true);
+	else
+		kvm_stage2_flush_range(&kvm->arch.mmu, addr, end);
 }
 
 /**
@@ -1103,6 +1113,10 @@ void stage2_unmap_vm(struct kvm *kvm)
 	struct kvm_memory_slot *memslot;
 	int idx, bkt;
 
+	/* For realms this is handled by the RMM so nothing to do here */
+	if (kvm_is_realm(kvm))
+		return;
+
 	idx = srcu_read_lock(&kvm->srcu);
 	mmap_read_lock(current->mm);
 	write_lock(&kvm->mmu_lock);
@@ -1528,6 +1542,29 @@ static bool kvm_vma_mte_allowed(struct vm_area_struct *vma)
 	return vma->vm_flags & VM_MTE_ALLOWED;
 }
 
+static int realm_map_ipa(struct kvm *kvm, phys_addr_t ipa,
+			 kvm_pfn_t pfn, unsigned long map_size,
+			 enum kvm_pgtable_prot prot,
+			 struct kvm_mmu_memory_cache *memcache)
+{
+	struct realm *realm = &kvm->arch.realm;
+
+	/*
+	 * Write permission is required for now even though it's possible to
+	 * map unprotected pages (granules) as read-only. It's impossible to
+	 * map protected pages (granules) as read-only.
+	 */
+	if (WARN_ON(!(prot & KVM_PGTABLE_PROT_W)))
+		return -EFAULT;
+
+	ipa = ALIGN_DOWN(ipa, PAGE_SIZE);
+	if (!kvm_realm_is_private_address(realm, ipa))
+		return realm_map_non_secure(realm, ipa, pfn, map_size, prot,
+					    memcache);
+
+	return realm_map_protected(kvm, ipa, pfn, map_size, memcache);
+}
+
 static bool kvm_vma_is_cacheable(struct vm_area_struct *vma)
 {
 	switch (FIELD_GET(PTE_ATTRINDX_MASK, pgprot_val(vma->vm_page_prot))) {
@@ -1604,27 +1641,52 @@ static int gmem_abort(const struct kvm_s2_fault_desc *s2fd)
 	bool write_fault, exec_fault;
 	enum kvm_pgtable_walk_flags flags = KVM_PGTABLE_WALK_SHARED;
 	enum kvm_pgtable_prot prot = KVM_PGTABLE_PROT_R;
-	struct kvm_pgtable *pgt = s2fd->vcpu->arch.hw_mmu->pgt;
+	struct kvm_vcpu *vcpu = s2fd->vcpu;
+	struct kvm_pgtable *pgt = vcpu->arch.hw_mmu->pgt;
+	gpa_t gpa = kvm_gpa_from_fault(vcpu->kvm, s2fd->fault_ipa);
 	unsigned long mmu_seq;
 	struct page *page;
-	struct kvm *kvm = s2fd->vcpu->kvm;
+	struct kvm *kvm = vcpu->kvm;
 	void *memcache;
 	kvm_pfn_t pfn;
 	gfn_t gfn;
 	int ret;
 
-	memcache = get_mmu_memcache(s2fd->vcpu);
-	ret = topup_mmu_memcache(s2fd->vcpu, memcache);
+	if (kvm_is_realm(vcpu->kvm)) {
+		/* check for memory attribute mismatch */
+		bool is_priv_gfn = kvm_mem_is_private(kvm, gpa >> PAGE_SHIFT);
+		/*
+		 * For Realms, the shared address is an alias of the private
+		 * PA with the top bit set. Thus if the fault address matches
+		 * the GPA then it is the private alias.
+		 */
+		bool is_priv_fault = (gpa == s2fd->fault_ipa);
+
+		if (is_priv_gfn != is_priv_fault) {
+			kvm_prepare_memory_fault_exit(vcpu, gpa, PAGE_SIZE,
+						      kvm_is_write_fault(vcpu),
+						      false,
+						      is_priv_fault);
+			/*
+			 * KVM_EXIT_MEMORY_FAULT requires an return code of
+			 * -EFAULT, see the API documentation
+			 */
+			return -EFAULT;
+		}
+	}
+
+	memcache = get_mmu_memcache(vcpu);
+	ret = topup_mmu_memcache(vcpu, memcache);
 	if (ret)
 		return ret;
 
 	if (s2fd->nested)
 		gfn = kvm_s2_trans_output(s2fd->nested) >> PAGE_SHIFT;
 	else
-		gfn = s2fd->fault_ipa >> PAGE_SHIFT;
+		gfn = gpa >> PAGE_SHIFT;
 
-	write_fault = kvm_is_write_fault(s2fd->vcpu);
-	exec_fault = kvm_vcpu_trap_is_exec_fault(s2fd->vcpu);
+	write_fault = kvm_is_write_fault(vcpu);
+	exec_fault = kvm_vcpu_trap_is_exec_fault(vcpu);
 
 	VM_WARN_ON_ONCE(write_fault && exec_fault);
 
@@ -1634,7 +1696,7 @@ static int gmem_abort(const struct kvm_s2_fault_desc *s2fd)
 
 	ret = kvm_gmem_get_pfn(kvm, s2fd->memslot, gfn, &pfn, &page, NULL);
 	if (ret) {
-		kvm_prepare_memory_fault_exit(s2fd->vcpu, s2fd->fault_ipa, PAGE_SIZE,
+		kvm_prepare_memory_fault_exit(vcpu, gpa, PAGE_SIZE,
 					      write_fault, exec_fault, false);
 		return ret;
 	}
@@ -1654,14 +1716,20 @@ static int gmem_abort(const struct kvm_s2_fault_desc *s2fd)
 	kvm_fault_lock(kvm);
 	if (mmu_invalidate_retry(kvm, mmu_seq)) {
 		ret = -EAGAIN;
-		goto out_unlock;
+		goto out_release_page;
+	}
+
+	if (kvm_is_realm(kvm)) {
+		ret = realm_map_ipa(kvm, s2fd->fault_ipa, pfn,
+				    PAGE_SIZE, KVM_PGTABLE_PROT_R | KVM_PGTABLE_PROT_W, memcache);
+		goto out_release_page;
 	}
 
 	ret = KVM_PGT_FN(kvm_pgtable_stage2_map)(pgt, s2fd->fault_ipa, PAGE_SIZE,
 						 __pfn_to_phys(pfn), prot,
 						 memcache, flags);
 
-out_unlock:
+out_release_page:
 	kvm_release_faultin_page(kvm, page, !!ret, prot & KVM_PGTABLE_PROT_W);
 	kvm_fault_unlock(kvm);
 
@@ -1847,7 +1915,7 @@ static int kvm_s2_fault_get_vma_info(const struct kvm_s2_fault_desc *s2fd,
 	 * mapping size to ensure we find the right PFN and lay down the
 	 * mapping in the right place.
 	 */
-	s2vi->gfn = ALIGN_DOWN(s2fd->fault_ipa, s2vi->vma_pagesize) >> PAGE_SHIFT;
+	s2vi->gfn = kvm_gpa_from_fault(kvm, ALIGN_DOWN(s2fd->fault_ipa, s2vi->vma_pagesize)) >> PAGE_SHIFT;
 
 	s2vi->mte_allowed = kvm_vma_mte_allowed(vma);
 
@@ -2056,6 +2124,9 @@ static int kvm_s2_fault_map(const struct kvm_s2_fault_desc *s2fd,
 		prot &= ~KVM_NV_GUEST_MAP_SZ;
 		ret = KVM_PGT_FN(kvm_pgtable_stage2_relax_perms)(pgt, gfn_to_gpa(gfn),
 								 prot, flags);
+	} else if (kvm_is_realm(kvm)) {
+		ret = realm_map_ipa(kvm, s2fd->fault_ipa, pfn, mapping_size,
+				    prot, memcache);
 	} else {
 		ret = KVM_PGT_FN(kvm_pgtable_stage2_map)(pgt, gfn_to_gpa(gfn), mapping_size,
 							 __pfn_to_phys(pfn), prot,
@@ -2214,6 +2285,13 @@ int kvm_handle_guest_sea(struct kvm_vcpu *vcpu)
 	return 0;
 }
 
+static bool shared_ipa_fault(struct kvm *kvm, phys_addr_t fault_ipa)
+{
+	gpa_t gpa = kvm_gpa_from_fault(kvm, fault_ipa);
+
+	return (gpa != fault_ipa);
+}
+
 /**
  * kvm_handle_guest_abort - handles all 2nd stage aborts
  * @vcpu:	the VCPU pointer
@@ -2324,8 +2402,9 @@ int kvm_handle_guest_abort(struct kvm_vcpu *vcpu)
 		nested = &nested_trans;
 	}
 
-	gfn = ipa >> PAGE_SHIFT;
+	gfn = kvm_gpa_from_fault(vcpu->kvm, ipa) >> PAGE_SHIFT;
 	memslot = gfn_to_memslot(vcpu->kvm, gfn);
+
 	hva = gfn_to_hva_memslot_prot(memslot, gfn, &writable);
 	write_fault = kvm_is_write_fault(vcpu);
 	if (kvm_is_error_hva(hva) || (write_fault && !writable)) {
@@ -2368,7 +2447,7 @@ int kvm_handle_guest_abort(struct kvm_vcpu *vcpu)
 		 * of the page size.
 		 */
 		ipa |= FAR_TO_FIPA_OFFSET(kvm_vcpu_get_hfar(vcpu));
-		ret = io_mem_abort(vcpu, ipa);
+		ret = io_mem_abort(vcpu, kvm_gpa_from_fault(vcpu->kvm, ipa));
 		goto out_unlock;
 	}
 
@@ -2396,7 +2475,7 @@ int kvm_handle_guest_abort(struct kvm_vcpu *vcpu)
 				!write_fault &&
 				!kvm_vcpu_trap_is_exec_fault(vcpu));
 
-		if (kvm_slot_has_gmem(memslot))
+		if (kvm_slot_has_gmem(memslot) && !shared_ipa_fault(vcpu->kvm, fault_ipa))
 			ret = gmem_abort(&s2fd);
 		else
 			ret = user_mem_abort(&s2fd);
@@ -2433,6 +2512,10 @@ bool kvm_age_gfn(struct kvm *kvm, struct kvm_gfn_range *range)
 	if (!kvm->arch.mmu.pgt || kvm_vm_is_protected(kvm))
 		return false;
 
+	/* We don't support aging for Realms */
+	if (kvm_is_realm(kvm))
+		return true;
+
 	return KVM_PGT_FN(kvm_pgtable_stage2_test_clear_young)(kvm->arch.mmu.pgt,
 						   range->start << PAGE_SHIFT,
 						   size, true);
@@ -2449,6 +2532,10 @@ bool kvm_test_age_gfn(struct kvm *kvm, struct kvm_gfn_range *range)
 	if (!kvm->arch.mmu.pgt || kvm_vm_is_protected(kvm))
 		return false;
 
+	/* We don't support aging for Realms */
+	if (kvm_is_realm(kvm))
+		return true;
+
 	return KVM_PGT_FN(kvm_pgtable_stage2_test_clear_young)(kvm->arch.mmu.pgt,
 						   range->start << PAGE_SHIFT,
 						   size, false);
@@ -2628,10 +2715,11 @@ int kvm_arch_prepare_memory_region(struct kvm *kvm,
 		return -EFAULT;
 
 	/*
-	 * Only support guest_memfd backed memslots with mappable memory, since
-	 * there aren't any CoCo VMs that support only private memory on arm64.
+	 * Only support guest_memfd backed memslots with mappable memory,
+	 * unless the guest is a CCA realm guest.
 	 */
-	if (kvm_slot_has_gmem(new) && !kvm_memslot_is_gmem_only(new))
+	if (kvm_slot_has_gmem(new) && !kvm_memslot_is_gmem_only(new) &&
+	    !kvm_is_realm(kvm))
 		return -EINVAL;
 
 	hva = new->userspace_addr;
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index cae29fd3353c..761b38a4071c 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -597,6 +597,179 @@ static int realm_data_map_init(struct kvm *kvm, unsigned long ipa,
 	return ret;
 }
 
+static unsigned long addr_range_desc(unsigned long phys, unsigned long size)
+{
+	unsigned long out = 0;
+
+	switch (size) {
+	case P4D_SIZE:
+		out = 3 | (1 << 2);
+		break;
+	case PUD_SIZE:
+		out = 2 | (1 << 2);
+		break;
+	case PMD_SIZE:
+		out = 1 | (1 << 2);
+		break;
+	case PAGE_SIZE:
+		out = 0 | (1 << 2);
+		break;
+	default:
+		/*
+		 * Only support mapping at the page level granulatity when
+		 * it's an unusual length. This should get us back onto a larger
+		 * block size for the subsequent mappings.
+		 */
+		out = 0 | ((MIN(size >> PAGE_SHIFT, PTRS_PER_PTE - 1)) << 2);
+		break;
+	}
+
+	WARN_ON(phys & ~PAGE_MASK);
+
+	out |= phys & PAGE_MASK;
+
+	return out;
+}
+
+int realm_map_protected(struct kvm *kvm,
+			unsigned long ipa,
+			kvm_pfn_t pfn,
+			unsigned long map_size,
+			struct kvm_mmu_memory_cache *memcache)
+{
+	struct realm *realm = &kvm->arch.realm;
+	phys_addr_t phys = __pfn_to_phys(pfn);
+	phys_addr_t base_phys = phys;
+	phys_addr_t rd = virt_to_phys(realm->rd);
+	unsigned long base_ipa = ipa;
+	unsigned long ipa_top = ipa + map_size;
+	int ret = 0;
+
+	if (WARN_ON(!IS_ALIGNED(map_size, PAGE_SIZE) ||
+		    !IS_ALIGNED(ipa, map_size)))
+		return -EINVAL;
+
+	if (rmi_delegate_range(phys, map_size)) {
+		/*
+		 * It's likely we raced with another VCPU on the same
+		 * fault. Assume the other VCPU has handled the fault
+		 * and return to the guest.
+		 */
+		return 0;
+	}
+
+	while (ipa < ipa_top) {
+		unsigned long flags = RMI_ADDR_TYPE_SINGLE;
+		unsigned long range_desc = addr_range_desc(phys, ipa_top - ipa);
+		unsigned long out_top;
+
+		ret = rmi_rtt_data_map(rd, ipa, ipa_top, flags, range_desc,
+				       &out_top);
+
+		if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
+			/* Create missing RTTs and retry */
+			int level = RMI_RETURN_INDEX(ret);
+
+			WARN_ON(level == KVM_PGTABLE_LAST_LEVEL);
+			ret = realm_create_rtt_levels(realm, ipa, level,
+						      KVM_PGTABLE_LAST_LEVEL,
+						      memcache);
+			if (ret)
+				goto err_undelegate;
+
+			ret = rmi_rtt_data_map(rd, ipa, ipa_top, flags,
+					       range_desc, &out_top);
+		}
+
+		if (WARN_ON(ret))
+			goto err_undelegate;
+
+		phys += out_top - ipa;
+		ipa = out_top;
+	}
+
+	return 0;
+
+err_undelegate:
+	realm_unmap_private_range(kvm, base_ipa, ipa, true);
+	if (WARN_ON(rmi_undelegate_range(base_phys, map_size))) {
+		/* Page can't be returned to NS world so is lost */
+		get_page(phys_to_page(base_phys));
+	}
+	return -ENXIO;
+}
+
+int realm_map_non_secure(struct realm *realm,
+			 unsigned long ipa,
+			 kvm_pfn_t pfn,
+			 unsigned long size,
+			 enum kvm_pgtable_prot prot,
+			 struct kvm_mmu_memory_cache *memcache)
+{
+	unsigned long attr, flags = 0;
+	phys_addr_t rd = virt_to_phys(realm->rd);
+	phys_addr_t phys = __pfn_to_phys(pfn);
+	unsigned long ipa_top = ipa + size;
+	int ret;
+
+	if (WARN_ON(!IS_ALIGNED(size, PAGE_SIZE) ||
+		    !IS_ALIGNED(ipa, size)))
+		return -EINVAL;
+
+	switch (prot & (KVM_PGTABLE_PROT_DEVICE | KVM_PGTABLE_PROT_NORMAL_NC)) {
+	case KVM_PGTABLE_PROT_DEVICE | KVM_PGTABLE_PROT_NORMAL_NC:
+		return -EINVAL;
+	case KVM_PGTABLE_PROT_DEVICE:
+		attr = MT_S2_FWB_DEVICE_nGnRE;
+		break;
+	case KVM_PGTABLE_PROT_NORMAL_NC:
+		attr = MT_S2_FWB_NORMAL_NC;
+		break;
+	default:
+		attr = MT_S2_FWB_NORMAL;
+	}
+
+	flags |= FIELD_PREP(RMI_RTT_UNPROT_MAP_FLAGS_MEMATTR, attr);
+
+	if (prot & KVM_PGTABLE_PROT_R)
+		flags |= FIELD_PREP(RMI_RTT_UNPROT_MAP_FLAGS_S2AP, RMI_S2AP_DIRECT_READ);
+	if (prot & KVM_PGTABLE_PROT_W)
+		flags |= FIELD_PREP(RMI_RTT_UNPROT_MAP_FLAGS_S2AP, RMI_S2AP_DIRECT_WRITE);
+
+	flags |= RMI_ADDR_TYPE_SINGLE;
+
+	while (ipa < ipa_top) {
+		unsigned long range_desc = addr_range_desc(phys, ipa_top - ipa);
+		unsigned long out_top;
+
+		ret = rmi_rtt_unprot_map(rd, ipa, ipa_top, flags, range_desc,
+					 &out_top);
+
+		if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
+			/* Create missing RTTs and retry */
+			int level = RMI_RETURN_INDEX(ret);
+
+			WARN_ON(level == KVM_PGTABLE_LAST_LEVEL);
+			ret = realm_create_rtt_levels(realm, ipa, level,
+						      KVM_PGTABLE_LAST_LEVEL,
+						      memcache);
+			if (ret)
+				return ret;
+
+			ret = rmi_rtt_unprot_map(rd, ipa, ipa_top, flags,
+						 range_desc, &out_top);
+		}
+
+		if (WARN_ON(ret))
+			return ret;
+
+		phys += out_top - ipa;
+		ipa = out_top;
+	}
+
+	return 0;
+}
+
 static int populate_region_cb(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 			      struct page *src_page, void *opaque)
 {

---

## [31] Steven Price — 2026-05-13
*Subject: [PATCH v14 30/44] KVM: arm64: Handle realm VCPU load*

When loading a realm VCPU much of the work is handled by the RMM so only
some of the actions are required. Rearrange kvm_arch_vcpu_load()
slightly so we can bail out early for a realm guest.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/kvm/arm.c | 19 ++++++++++++-------
 1 file changed, 12 insertions(+), 7 deletions(-)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 073ba9181da9..495082e601a9 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -702,7 +702,7 @@ void kvm_arch_vcpu_load(struct kvm_vcpu *vcpu, int cpu)
 	struct kvm_s2_mmu *mmu;
 	int *last_ran;
 
-	if (is_protected_kvm_enabled())
+	if (is_protected_kvm_enabled() || kvm_is_realm(vcpu->kvm))
 		goto nommu;
 
 	if (vcpu_has_nv(vcpu))
@@ -746,12 +746,6 @@ void kvm_arch_vcpu_load(struct kvm_vcpu *vcpu, int cpu)
 	kvm_vgic_load(vcpu);
 	kvm_vcpu_load_debug(vcpu);
 	kvm_vcpu_load_fgt(vcpu);
-	if (has_vhe())
-		kvm_vcpu_load_vhe(vcpu);
-	kvm_arch_vcpu_load_fp(vcpu);
-	kvm_vcpu_pmu_restore_guest(vcpu);
-	if (kvm_arm_is_pvtime_enabled(&vcpu->arch))
-		kvm_make_request(KVM_REQ_RECORD_STEAL, vcpu);
 
 	if (kvm_vcpu_should_clear_twe(vcpu))
 		vcpu->arch.hcr_el2 &= ~HCR_TWE;
@@ -773,6 +767,17 @@ void kvm_arch_vcpu_load(struct kvm_vcpu *vcpu, int cpu)
 			     &vcpu->arch.vgic_cpu.vgic_v3);
 	}
 
+	/* No additional state needs to be loaded on Realmed VMs */
+	if (vcpu_is_rec(vcpu))
+		return;
+
+	if (has_vhe())
+		kvm_vcpu_load_vhe(vcpu);
+	kvm_arch_vcpu_load_fp(vcpu);
+	kvm_vcpu_pmu_restore_guest(vcpu);
+	if (kvm_arm_is_pvtime_enabled(&vcpu->arch))
+		kvm_make_request(KVM_REQ_RECORD_STEAL, vcpu);
+
 	if (!cpumask_test_cpu(cpu, vcpu->kvm->arch.supported_cpus))
 		vcpu_set_on_unsupported_cpu(vcpu);

---

## [32] Steven Price — 2026-05-13
*Subject: [PATCH v14 31/44] KVM: arm64: Validate register access for a Realm VM*

The RMM only allows setting the GPRS (x0-x30) and PC for a realm
guest. Check this in kvm_arm_set_reg() so that the VMM can receive a
suitable error return if other registers are written to.

The RMM makes similar restrictions for reading of the guest's registers
(this is *confidential* compute after all), however we don't impose the
restriction here. This allows the VMM to read (stale) values from the
registers which might be useful to read back the initial values even if
the RMM doesn't provide the latest version. For migration of a realm VM,
a new interface will be needed so that the VMM can receive an
(encrypted) blob of the VM's state.

Reviewed-by: Gavin Shan <gshan@redhat.com>
Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Reviewed-by: Joey Gouly <joey.gouly@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v5:
 * Upper GPRS can be set as part of a HOST_CALL return, so fix up the
   test to allow them.
---
 arch/arm64/kvm/guest.c | 41 +++++++++++++++++++++++++++++++++++++++++
 1 file changed, 41 insertions(+)

diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index 332c453b87cf..e6682019ef6d 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -73,6 +73,25 @@ static u64 core_reg_offset_from_id(u64 id)
 	return id & ~(KVM_REG_ARCH_MASK | KVM_REG_SIZE_MASK | KVM_REG_ARM_CORE);
 }
 
+static bool kvm_realm_validate_core_reg(u64 off)
+{
+	/*
+	 * Note that GPRs can only sometimes be controlled by the VMM.
+	 * For PSCI only X0-X6 are used, higher registers are ignored (restored
+	 * from the REC).
+	 * For HOST_CALL all of X0-X30 are copied to the RsiHostCall structure.
+	 * For emulated MMIO X0 is always used.
+	 * PC can only be set before the realm is activated.
+	 */
+	switch (off) {
+	case KVM_REG_ARM_CORE_REG(regs.regs[0]) ...
+	     KVM_REG_ARM_CORE_REG(regs.regs[30]):
+	case KVM_REG_ARM_CORE_REG(regs.pc):
+		return true;
+	}
+	return false;
+}
+
 static int core_reg_size_from_offset(const struct kvm_vcpu *vcpu, u64 off)
 {
 	int size;
@@ -716,12 +735,34 @@ int kvm_arm_get_reg(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg)
 	return kvm_arm_sys_reg_get_reg(vcpu, reg);
 }
 
+/*
+ * The RMI ABI only enables setting some GPRs and PC. The selection of GPRs
+ * that are available depends on the Realm state and the reason for the last
+ * exit.  All other registers are reset to architectural or otherwise defined
+ * reset values by the RMM, except for a few configuration fields that
+ * correspond to Realm parameters.
+ */
+static bool validate_realm_set_reg(struct kvm_vcpu *vcpu,
+				   const struct kvm_one_reg *reg)
+{
+	if ((reg->id & KVM_REG_ARM_COPROC_MASK) == KVM_REG_ARM_CORE) {
+		u64 off = core_reg_offset_from_id(reg->id);
+
+		return kvm_realm_validate_core_reg(off);
+	}
+
+	return false;
+}
+
 int kvm_arm_set_reg(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg)
 {
 	/* We currently use nothing arch-specific in upper 32 bits */
 	if ((reg->id & ~KVM_REG_SIZE_MASK) >> 32 != KVM_REG_ARM64 >> 32)
 		return -EINVAL;
 
+	if (kvm_is_realm(vcpu->kvm) && !validate_realm_set_reg(vcpu, reg))
+		return -EINVAL;
+
 	switch (reg->id & KVM_REG_ARM_COPROC_MASK) {
 	case KVM_REG_ARM_CORE:	return set_core_reg(vcpu, reg);
 	case KVM_REG_ARM_FW:

---

## [33] Steven Price — 2026-05-13
*Subject: [PATCH v14 32/44] KVM: arm64: Handle Realm PSCI requests*

The RMM needs to be informed of the target REC when a PSCI call is made
with an MPIDR argument.

This requirement will be removed in a future release of the RMM 2.0
specification but is still required for v2.0-bet1.

Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Chanegs since v13:
 * The ioctl KVM_ARM_VCPU_RMI_PSCI_COMPLETE has gone. The RMI call is
   made automatically just before entering the REC again.
Changes since v12:
 * Chance return code for non-realms to -ENXIO to better represent that
   the ioctl is invalid for non-realms (checkpatch is insistent that
   "ENOSYS means 'invalid syscall nr' and nothing else").
Changes since v11:
 * RMM->RMI renaming.
Changes since v6:
 * Use vcpu_is_rec() rather than kvm_is_realm(vcpu->kvm).
 * Minor renaming/formatting fixes.
---
 arch/arm64/include/asm/kvm_rmi.h |  3 ++
 arch/arm64/kvm/psci.c            | 15 ++++++++-
 arch/arm64/kvm/rmi.c             | 58 ++++++++++++++++++++++++++++++++
 3 files changed, 75 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index b65cfec10dee..eacf82a7467d 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -109,6 +109,9 @@ int realm_map_non_secure(struct realm *realm,
 			 unsigned long size,
 			 enum kvm_pgtable_prot prot,
 			 struct kvm_mmu_memory_cache *memcache);
+int realm_psci_complete(struct kvm_vcpu *source,
+			struct kvm_vcpu *target,
+			unsigned long status);
 
 static inline bool kvm_realm_is_private_address(struct realm *realm,
 						unsigned long addr)
diff --git a/arch/arm64/kvm/psci.c b/arch/arm64/kvm/psci.c
index 3b5dbe9a0a0e..a2cd55dc7b5b 100644
--- a/arch/arm64/kvm/psci.c
+++ b/arch/arm64/kvm/psci.c
@@ -103,7 +103,6 @@ static unsigned long kvm_psci_vcpu_on(struct kvm_vcpu *source_vcpu)
 
 	reset_state->reset = true;
 	kvm_make_request(KVM_REQ_VCPU_RESET, vcpu);
-
 	/*
 	 * Make sure the reset request is observed if the RUNNABLE mp_state is
 	 * observed.
@@ -142,6 +141,20 @@ static unsigned long kvm_psci_vcpu_affinity_info(struct kvm_vcpu *vcpu)
 	/* Ignore other bits of target affinity */
 	target_affinity &= target_affinity_mask;
 
+	if (vcpu_is_rec(vcpu)) {
+		struct kvm_vcpu *target_vcpu;
+
+		/* RMM supports only zero affinity level */
+		if (lowest_affinity_level != 0)
+			return PSCI_RET_INVALID_PARAMS;
+
+		target_vcpu = kvm_mpidr_to_vcpu(kvm, target_affinity);
+		if (!target_vcpu)
+			return PSCI_RET_INVALID_PARAMS;
+
+		return PSCI_RET_SUCCESS;
+	}
+
 	/*
 	 * If one or more VCPU matching target affinity are running
 	 * then ON else OFF
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 761b38a4071c..2b03e962ee41 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -3,6 +3,7 @@
  * Copyright (C) 2023-2025 ARM Ltd.
  */
 
+#include <uapi/linux/psci.h>
 #include <linux/kvm_host.h>
 
 #include <asm/kvm_emulate.h>
@@ -127,6 +128,25 @@ static void free_rtt(phys_addr_t phys)
 	kvm_account_pgtable_pages(phys_to_virt(phys), -1);
 }
 
+int realm_psci_complete(struct kvm_vcpu *source, struct kvm_vcpu *target,
+			unsigned long status)
+{
+	int ret;
+
+	/*
+	 * XXX: RMM-v2.0 doesn't require the target REC address for completing
+	 * PSCI requests. Temporary hack until RMM implementation catches up
+	 * to the full spec.
+	 */
+	ret = rmi_psci_complete(virt_to_phys(source->arch.rec.rec_page),
+				virt_to_phys(target->arch.rec.rec_page),
+				status);
+	if (ret)
+		return -EINVAL;
+
+	return 0;
+}
+
 static int realm_rtt_create(struct realm *realm,
 			    unsigned long addr,
 			    int level,
@@ -1004,6 +1024,41 @@ static void kvm_complete_ripas_change(struct kvm_vcpu *vcpu)
 	rec->run->exit.ripas_base = base;
 }
 
+static void kvm_rec_complete_psci(struct kvm_vcpu *vcpu)
+{
+	struct rec_run *run = vcpu->arch.rec.run;
+	unsigned long status = PSCI_RET_DENIED;
+	unsigned long ret = vcpu_get_reg(vcpu, 0);
+	struct kvm_vcpu *target;
+
+	switch (run->exit.gprs[0]) {
+	/*
+	 * XXX: RMM-v2.0 doesn't cause RMI_EXIT_PSCI for AFFINITY_INFO
+	 * Temporary hack until tf-RMM gets the REC to MPIDR mapping via
+	 * RD Auxiliary granules.
+	 * For now always report SUCCESS
+	 */
+	case PSCI_0_2_FN64_AFFINITY_INFO:
+		status = PSCI_RET_SUCCESS;
+		break;
+	case PSCI_0_2_FN64_CPU_ON: {
+		if (ret != PSCI_RET_SUCCESS &&
+		    ret != PSCI_RET_ALREADY_ON)
+			status = PSCI_RET_DENIED;
+		else
+			status = PSCI_RET_SUCCESS;
+		break;
+	}
+	default:
+		return;
+	}
+
+	target = kvm_mpidr_to_vcpu(vcpu->kvm, run->exit.gprs[1]);
+	/* RMM makes sure that we don't get RMI_EXIT_PSCI for invalid mpidrs */
+	if (target)
+		realm_psci_complete(vcpu, target, status);
+}
+
 /*
  * kvm_rec_pre_enter - Complete operations before entering a REC
  *
@@ -1028,6 +1083,9 @@ int kvm_rec_pre_enter(struct kvm_vcpu *vcpu)
 		for (int i = 0; i < REC_RUN_GPRS; i++)
 			rec->run->enter.gprs[i] = vcpu_get_reg(vcpu, i);
 		break;
+	case RMI_EXIT_PSCI:
+		kvm_rec_complete_psci(vcpu);
+		break;
 	case RMI_EXIT_RIPAS_CHANGE:
 		kvm_complete_ripas_change(vcpu);
 		break;

---

## [34] Steven Price — 2026-05-13
*Subject: [PATCH v14 33/44] KVM: arm64: WARN on injected undef exceptions*

The RMM doesn't allow injection of a undefined exception into a realm
guest. Add a WARN to catch if this ever happens.

Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
---
Changes since v6:
 * if (x) WARN(1, ...) makes no sense, just WARN(x, ...)!
---
 arch/arm64/kvm/inject_fault.c | 1 +
 1 file changed, 1 insertion(+)

diff --git a/arch/arm64/kvm/inject_fault.c b/arch/arm64/kvm/inject_fault.c
index 6492397b73d7..613f223bc7a3 100644
--- a/arch/arm64/kvm/inject_fault.c
+++ b/arch/arm64/kvm/inject_fault.c
@@ -327,6 +327,7 @@ void kvm_inject_size_fault(struct kvm_vcpu *vcpu)
  */
 void kvm_inject_undefined(struct kvm_vcpu *vcpu)
 {
+	WARN(vcpu_is_rec(vcpu), "Unexpected undefined exception injection to REC");
 	if (vcpu_el1_is_32bit(vcpu))
 		inject_undef32(vcpu);
 	else

---

## [35] Steven Price — 2026-05-13
*Subject: [PATCH v14 34/44] arm64: RMI: allow userspace to inject aborts*

From: Joey Gouly <joey.gouly@arm.com>

Extend KVM_SET_VCPU_EVENTS to support realms, where KVM cannot set the
system registers, and the RMM must perform it on next REC entry.

Signed-off-by: Joey Gouly <joey.gouly@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
---
 Documentation/virt/kvm/api.rst |  2 ++
 arch/arm64/kvm/guest.c         | 24 ++++++++++++++++++++++++
 2 files changed, 26 insertions(+)

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index a47c60490475..4e0dcca0d261 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -1314,6 +1314,8 @@ User space may need to inject several types of events to the guest.
 Set the pending SError exception state for this VCPU. It is not possible to
 'cancel' an Serror that has been made pending.
 
+User space cannot inject SErrors into Realms.
+
 If the guest performed an access to I/O memory which could not be handled by
 userspace, for example because of missing instruction syndrome decode
 information or because there is no device mapped at the accessed IPA, then
diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index e6682019ef6d..447674373426 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -827,6 +827,30 @@ int __kvm_arm_vcpu_set_events(struct kvm_vcpu *vcpu,
 	u64 esr = events->exception.serror_esr;
 	int ret = 0;
 
+	if (vcpu_is_rec(vcpu)) {
+		/* Cannot inject SError into a Realm. */
+		if (serror_pending)
+			return -EINVAL;
+
+		/*
+		 * If a data abort is pending, set the flag and let the RMM
+		 * inject an SEA when the REC is scheduled to be run.
+		 */
+		if (ext_dabt_pending) {
+			/*
+			 * Can only inject SEA into a Realm if the previous exit
+			 * was due to a data abort of an Unprotected IPA.
+			 */
+			if (!(vcpu->arch.rec.run->enter.flags & REC_ENTER_FLAG_EMULATED_MMIO))
+				return -EINVAL;
+
+			vcpu->arch.rec.run->enter.flags &= ~REC_ENTER_FLAG_EMULATED_MMIO;
+			vcpu->arch.rec.run->enter.flags |= REC_ENTER_FLAG_INJECT_SEA;
+		}
+
+		return 0;
+	}
+
 	/*
 	 * Immediately commit the pending SEA to the vCPU's architectural
 	 * state which is necessary since we do not return a pending SEA

---

## [36] Steven Price — 2026-05-13
*Subject: [PATCH v14 35/44] arm64: RMI: support RSI_HOST_CALL*

From: Joey Gouly <joey.gouly@arm.com>

Realm VMs can talk to the hypervisor using the RSI_HOST_CALL SMC. The
RMM forwards this to the host and KVM handles them as regular
hypercalls.

Signed-off-by: Joey Gouly <joey.gouly@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
---
Changes since v7:
 * Avoid turning a negative return from kvm_smccc_call_handler() into a
   error response to the guest. Instead propogate the error back to user
   space.
Changes since v4:
 * Setting GPRS is now done by kvm_rec_enter() rather than
   rec_exit_host_call() (see previous patch - arm64: RME: Handle realm
   enter/exit). This fixes a bug where the registers set by user space
   were being ignored.
---
 arch/arm64/kvm/rmi-exit.c | 15 +++++++++++++++
 1 file changed, 15 insertions(+)

diff --git a/arch/arm64/kvm/rmi-exit.c b/arch/arm64/kvm/rmi-exit.c
index 8ec0d179eba2..e5647aa004d3 100644
--- a/arch/arm64/kvm/rmi-exit.c
+++ b/arch/arm64/kvm/rmi-exit.c
@@ -116,6 +116,19 @@ static int rec_exit_ripas_change(struct kvm_vcpu *vcpu)
 	return -EFAULT;
 }
 
+static int rec_exit_host_call(struct kvm_vcpu *vcpu)
+{
+	int i;
+	struct realm_rec *rec = &vcpu->arch.rec;
+
+	vcpu->stat.hvc_exit_stat++;
+
+	for (i = 0; i < REC_RUN_GPRS; i++)
+		vcpu_set_reg(vcpu, i, rec->run->exit.gprs[i]);
+
+	return kvm_smccc_call_handler(vcpu);
+}
+
 static void update_arch_timer_irq_lines(struct kvm_vcpu *vcpu)
 {
 	struct realm_rec *rec = &vcpu->arch.rec;
@@ -191,6 +204,8 @@ int handle_rec_exit(struct kvm_vcpu *vcpu, int rec_run_ret)
 		return rec_exit_psci(vcpu);
 	case RMI_EXIT_RIPAS_CHANGE:
 		return rec_exit_ripas_change(vcpu);
+	case RMI_EXIT_HOST_CALL:
+		return rec_exit_host_call(vcpu);
 	}
 
 	kvm_pr_unimpl("Unsupported exit reason: %u\n",

---

## [37] Steven Price — 2026-05-13
*Subject: [PATCH v14 36/44] arm64: RMI: Allow checking SVE on VM instance*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

Given we have different types of VMs supported, check the
support for SVE for the given instance of the VM to accurately
report the status.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
Reviewed-by: Joey Gouly <joey.gouly@arm.com>
---
Changes since v10:
 * RME->RMI renaming.
 * Adapt to move CAP check to kvm_realm_ext_allowed().
---
 arch/arm64/include/asm/kvm_rmi.h | 2 ++
 arch/arm64/kvm/arm.c             | 2 ++
 arch/arm64/kvm/rmi.c             | 5 +++++
 3 files changed, 9 insertions(+)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index eacf82a7467d..d641748b5306 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -79,6 +79,8 @@ struct realm_rec {
 void kvm_init_rmi(void);
 u32 kvm_realm_ipa_limit(void);
 
+bool kvm_rmi_supports_sve(void);
+
 int kvm_init_realm(struct kvm *kvm);
 int kvm_activate_realm(struct kvm *kvm);
 void kvm_destroy_realm(struct kvm *kvm);
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 495082e601a9..aacbeb524b6a 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -148,6 +148,8 @@ static bool kvm_realm_ext_allowed(long ext)
 	case KVM_CAP_ARM_PTRAUTH_GENERIC:
 	case KVM_CAP_ARM_RMI:
 		return true;
+	case KVM_CAP_ARM_SVE:
+		return kvm_rmi_supports_sve();
 	}
 	return false;
 }
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 2b03e962ee41..678d775aa1c7 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -25,6 +25,11 @@ static bool rmi_has_feature(unsigned long feature)
 	return !!u64_get_bits(rmm_feat_reg0, feature);
 }
 
+bool kvm_rmi_supports_sve(void)
+{
+	return rmi_has_feature(RMI_FEATURE_REGISTER_0_SVE);
+}
+
 u32 kvm_realm_ipa_limit(void)
 {
 	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_S2SZ);

---

## [38] Steven Price — 2026-05-13
*Subject: [PATCH v14 37/44] arm64: RMI: Prevent Device mappings for Realms*

Physical device assignment is not yet supported. RMM v2.0 does add the
relevant APIs, but device assignment is a big topic so will be handled
in a future patch series. For now prevent device mappings when the guest
is a realm.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes from v6:
 * Fix the check in user_mem_abort() to prevent all pages that are not
   guest_memfd() from being mapped into the protected half of the IPA.
Changes from v5:
 * Also prevent accesses in user_mem_abort()
---
 arch/arm64/kvm/mmu.c | 4 ++++
 1 file changed, 4 insertions(+)

diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index 776ffe56d17e..7678226ffd38 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -1230,6 +1230,10 @@ int kvm_phys_addr_ioremap(struct kvm *kvm, phys_addr_t guest_ipa,
 	if (is_protected_kvm_enabled())
 		return -EPERM;
 
+	/* We don't support mapping special pages into a Realm */
+	if (kvm_is_realm(kvm))
+		return -EPERM;
+
 	size += offset_in_page(guest_ipa);
 	guest_ipa &= PAGE_MASK;

---

## [39] Steven Price — 2026-05-13
*Subject: [PATCH v14 38/44] arm64: RMI: Propagate number of breakpoints and watchpoints to userspace*

From: Jean-Philippe Brucker <jean-philippe@linaro.org>

The RMM describes the maximum number of BPs/WPs available to the guest
in the Feature Register 0. Propagate those numbers into ID_AA64DFR0_EL1,
which is visible to userspace. A VMM needs this information in order to
set up realm parameters.

Signed-off-by: Jean-Philippe Brucker <jean-philippe@linaro.org>
Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Reviewed-by: Joey Gouly <joey.gouly@arm.com>
---
 arch/arm64/include/asm/kvm_rmi.h |  2 ++
 arch/arm64/kvm/rmi.c             | 19 +++++++++++++++++++
 arch/arm64/kvm/sys_regs.c        |  3 +++
 3 files changed, 24 insertions(+)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index d641748b5306..568b0169ab46 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -79,6 +79,8 @@ struct realm_rec {
 void kvm_init_rmi(void);
 u32 kvm_realm_ipa_limit(void);
 
+u64 kvm_realm_reset_id_aa64dfr0_el1(const struct kvm_vcpu *vcpu, u64 val);
+
 bool kvm_rmi_supports_sve(void);
 
 int kvm_init_realm(struct kvm *kvm);
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 678d775aa1c7..64e8e50f86d6 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -35,6 +35,25 @@ u32 kvm_realm_ipa_limit(void)
 	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_S2SZ);
 }
 
+u64 kvm_realm_reset_id_aa64dfr0_el1(const struct kvm_vcpu *vcpu, u64 val)
+{
+	u32 bps = u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_NUM_BPS);
+	u32 wps = u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_NUM_WPS);
+	u32 ctx_cmps;
+
+	/* Ensure CTX_CMPs is still valid */
+	ctx_cmps = FIELD_GET(ID_AA64DFR0_EL1_CTX_CMPs, val);
+	ctx_cmps = min(bps, ctx_cmps);
+
+	val &= ~(ID_AA64DFR0_EL1_BRPs_MASK | ID_AA64DFR0_EL1_WRPs_MASK |
+		 ID_AA64DFR0_EL1_CTX_CMPs);
+	val |= FIELD_PREP(ID_AA64DFR0_EL1_BRPs_MASK, bps) |
+	       FIELD_PREP(ID_AA64DFR0_EL1_WRPs_MASK, wps) |
+	       FIELD_PREP(ID_AA64DFR0_EL1_CTX_CMPs, ctx_cmps);
+
+	return val;
+}
+
 static int get_start_level(struct realm *realm)
 {
 	return 4 - stage2_pgtable_levels(realm->ia_bits);
diff --git a/arch/arm64/kvm/sys_regs.c b/arch/arm64/kvm/sys_regs.c
index 148fc3400ea8..10d191f83bb0 100644
--- a/arch/arm64/kvm/sys_regs.c
+++ b/arch/arm64/kvm/sys_regs.c
@@ -2145,6 +2145,9 @@ static u64 sanitise_id_aa64dfr0_el1(const struct kvm_vcpu *vcpu, u64 val)
 	/* Hide BRBE from guests */
 	val &= ~ID_AA64DFR0_EL1_BRBE_MASK;
 
+	if (vcpu_is_rec(vcpu))
+		return kvm_realm_reset_id_aa64dfr0_el1(vcpu, val);
+
 	return val;
 }

---

## [40] Steven Price — 2026-05-13
*Subject: [PATCH v14 39/44] arm64: RMI: Set breakpoint parameters through SET_ONE_REG*

From: Jean-Philippe Brucker <jean-philippe@linaro.org>

Allow userspace to configure the number of breakpoints and watchpoints
of a Realm VM through KVM_SET_ONE_REG ID_AA64DFR0_EL1.

The KVM sys_reg handler checks the user value against the maximum value
given by RMM (arm64_check_features() gets it from the
read_sanitised_id_aa64dfr0_el1() reset handler).

Userspace discovers that it can write these fields by issuing a
KVM_ARM_GET_REG_WRITABLE_MASKS ioctl.

Signed-off-by: Jean-Philippe Brucker <jean-philippe@linaro.org>
Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
---
 arch/arm64/kvm/guest.c    |  7 +++++++
 arch/arm64/kvm/rmi.c      |  3 +++
 arch/arm64/kvm/sys_regs.c | 17 +++++++++++------
 3 files changed, 21 insertions(+), 6 deletions(-)

diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index 447674373426..fd7233e00215 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -735,6 +735,8 @@ int kvm_arm_get_reg(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg)
 	return kvm_arm_sys_reg_get_reg(vcpu, reg);
 }
 
+#define KVM_REG_ARM_ID_AA64DFR0_EL1	ARM64_SYS_REG(3, 0, 0, 5, 0)
+
 /*
  * The RMI ABI only enables setting some GPRs and PC. The selection of GPRs
  * that are available depends on the Realm state and the reason for the last
@@ -749,6 +751,11 @@ static bool validate_realm_set_reg(struct kvm_vcpu *vcpu,
 		u64 off = core_reg_offset_from_id(reg->id);
 
 		return kvm_realm_validate_core_reg(off);
+	} else {
+		switch (reg->id) {
+		case KVM_REG_ARM_ID_AA64DFR0_EL1:
+			return true;
+		}
 	}
 
 	return false;
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 64e8e50f86d6..251de0a3425c 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -469,6 +469,7 @@ static int realm_create_rd(struct kvm *kvm)
 	void *rd = NULL;
 	phys_addr_t rd_phys, params_phys;
 	size_t pgd_size = kvm_pgtable_stage2_pgd_size(kvm->arch.mmu.vtcr);
+	u64 dfr0 = kvm_read_vm_id_reg(kvm, SYS_ID_AA64DFR0_EL1);
 	int r;
 
 	realm->ia_bits = VTCR_EL2_IPA(kvm->arch.mmu.vtcr);
@@ -495,6 +496,8 @@ static int realm_create_rd(struct kvm *kvm)
 	params->rtt_level_start = get_start_level(realm);
 	params->rtt_num_start = pgd_size / PAGE_SIZE;
 	params->rtt_base = kvm->arch.mmu.pgd_phys;
+	params->num_bps = SYS_FIELD_GET(ID_AA64DFR0_EL1, BRPs, dfr0);
+	params->num_wps = SYS_FIELD_GET(ID_AA64DFR0_EL1, WRPs, dfr0);
 
 	if (kvm->arch.arm_pmu) {
 		params->pmu_num_ctrs = kvm->arch.nr_pmu_counters;
diff --git a/arch/arm64/kvm/sys_regs.c b/arch/arm64/kvm/sys_regs.c
index 10d191f83bb0..607396f378dc 100644
--- a/arch/arm64/kvm/sys_regs.c
+++ b/arch/arm64/kvm/sys_regs.c
@@ -2177,6 +2177,9 @@ static int set_id_aa64dfr0_el1(struct kvm_vcpu *vcpu,
 {
 	u8 debugver = SYS_FIELD_GET(ID_AA64DFR0_EL1, DebugVer, val);
 	u8 pmuver = SYS_FIELD_GET(ID_AA64DFR0_EL1, PMUVer, val);
+	u8 bps = SYS_FIELD_GET(ID_AA64DFR0_EL1, BRPs, val);
+	u8 wps = SYS_FIELD_GET(ID_AA64DFR0_EL1, WRPs, val);
+	u8 ctx_cmps = SYS_FIELD_GET(ID_AA64DFR0_EL1, CTX_CMPs, val);
 
 	/*
 	 * Prior to commit 3d0dba5764b9 ("KVM: arm64: PMU: Move the
@@ -2196,10 +2199,11 @@ static int set_id_aa64dfr0_el1(struct kvm_vcpu *vcpu,
 		val &= ~ID_AA64DFR0_EL1_PMUVer_MASK;
 
 	/*
-	 * ID_AA64DFR0_EL1.DebugVer is one of those awkward fields with a
-	 * nonzero minimum safe value.
+	 * ID_AA64DFR0_EL1.DebugVer, BRPs and WRPs all have to be greater than
+	 * zero. CTX_CMPs is never greater than BRPs.
 	 */
-	if (debugver < ID_AA64DFR0_EL1_DebugVer_IMP)
+	if (debugver < ID_AA64DFR0_EL1_DebugVer_IMP || !bps || !wps ||
+	    ctx_cmps > bps)
 		return -EINVAL;
 
 	if (ignore_feat_doublelock(vcpu, val)) {
@@ -2432,10 +2436,11 @@ static int set_id_reg(struct kvm_vcpu *vcpu, const struct sys_reg_desc *rd,
 	mutex_lock(&vcpu->kvm->arch.config_lock);
 
 	/*
-	 * Once the VM has started the ID registers are immutable. Reject any
-	 * write that does not match the final register value.
+	 * Once the VM has started or the Realm descriptor is created, the ID
+	 * registers are immutable. Reject any write that does not match the
+	 * final register value.
 	 */
-	if (kvm_vm_has_ran_once(vcpu->kvm)) {
+	if (kvm_vm_has_ran_once(vcpu->kvm) || kvm_realm_is_created(vcpu->kvm)) {
 		if (val != read_id_reg(vcpu, rd))
 			ret = -EBUSY;
 		else

---

## [41] Steven Price — 2026-05-13
*Subject: [PATCH v14 40/44] arm64: RMI: Propagate max SVE vector length from RMM*

From: Jean-Philippe Brucker <jean-philippe@linaro.org>

RMM provides the maximum vector length it supports for a guest in its
feature register. Make it visible to the rest of KVM and to userspace
via KVM_REG_ARM64_SVE_VLS.

Signed-off-by: Jean-Philippe Brucker <jean-philippe@linaro.org>
Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
---
 arch/arm64/include/asm/kvm_host.h |  2 +-
 arch/arm64/include/asm/kvm_rmi.h  |  1 +
 arch/arm64/kvm/guest.c            |  2 +-
 arch/arm64/kvm/reset.c            | 12 ++++++++++--
 arch/arm64/kvm/rmi.c              |  6 ++++++
 5 files changed, 19 insertions(+), 4 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_host.h b/arch/arm64/include/asm/kvm_host.h
index 11e7b629c950..94e83da160cc 100644
--- a/arch/arm64/include/asm/kvm_host.h
+++ b/arch/arm64/include/asm/kvm_host.h
@@ -78,9 +78,9 @@ enum kvm_mode kvm_get_mode(void);
 static inline enum kvm_mode kvm_get_mode(void) { return KVM_MODE_NONE; };
 #endif
 
-extern unsigned int __ro_after_init kvm_sve_max_vl;
 extern unsigned int __ro_after_init kvm_host_sve_max_vl;
 int __init kvm_arm_init_sve(void);
+unsigned int kvm_sve_get_max_vl(struct kvm *kvm);
 
 u32 __attribute_const__ kvm_target_cpu(void);
 void kvm_reset_vcpu(struct kvm_vcpu *vcpu);
diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index 568b0169ab46..de56330e08c6 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -78,6 +78,7 @@ struct realm_rec {
 
 void kvm_init_rmi(void);
 u32 kvm_realm_ipa_limit(void);
+unsigned int kvm_realm_sve_max_vl(void);
 
 u64 kvm_realm_reset_id_aa64dfr0_el1(const struct kvm_vcpu *vcpu, u64 val);
 
diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index fd7233e00215..a92bd07ef53a 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -375,7 +375,7 @@ static int set_sve_vls(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg)
 		if (vq_present(vqs, vq))
 			max_vq = vq;
 
-	if (max_vq > sve_vq_from_vl(kvm_sve_max_vl))
+	if (max_vq > sve_vq_from_vl(kvm_sve_get_max_vl(vcpu->kvm)))
 		return -EINVAL;
 
 	/*
diff --git a/arch/arm64/kvm/reset.c b/arch/arm64/kvm/reset.c
index c18cdca7d125..7b8681a602d4 100644
--- a/arch/arm64/kvm/reset.c
+++ b/arch/arm64/kvm/reset.c
@@ -46,7 +46,7 @@ unsigned int __ro_after_init kvm_host_sve_max_vl;
 #define VCPU_RESET_PSTATE_SVC	(PSR_AA32_MODE_SVC | PSR_AA32_A_BIT | \
 				 PSR_AA32_I_BIT | PSR_AA32_F_BIT)
 
-unsigned int __ro_after_init kvm_sve_max_vl;
+static unsigned int __ro_after_init kvm_sve_max_vl;
 
 int __init kvm_arm_init_sve(void)
 {
@@ -76,9 +76,17 @@ int __init kvm_arm_init_sve(void)
 	return 0;
 }
 
+unsigned int kvm_sve_get_max_vl(struct kvm *kvm)
+{
+	if (kvm_is_realm(kvm))
+		return kvm_realm_sve_max_vl();
+	else
+		return kvm_sve_max_vl;
+}
+
 static void kvm_vcpu_enable_sve(struct kvm_vcpu *vcpu)
 {
-	vcpu->arch.sve_max_vl = kvm_sve_max_vl;
+	vcpu->arch.sve_max_vl = kvm_sve_get_max_vl(vcpu->kvm);
 
 	/*
 	 * Userspace can still customize the vector lengths by writing
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 251de0a3425c..35ad65efa5db 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -35,6 +35,12 @@ u32 kvm_realm_ipa_limit(void)
 	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_S2SZ);
 }
 
+unsigned int kvm_realm_sve_max_vl(void)
+{
+	return sve_vl_from_vq(u64_get_bits(rmm_feat_reg0,
+					   RMI_FEATURE_REGISTER_0_SVE_VL) + 1);
+}
+
 u64 kvm_realm_reset_id_aa64dfr0_el1(const struct kvm_vcpu *vcpu, u64 val)
 {
 	u32 bps = u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_NUM_BPS);

---

## [42] Steven Price — 2026-05-13
*Subject: [PATCH v14 41/44] arm64: RMI: Configure max SVE vector length for a Realm*

From: Jean-Philippe Brucker <jean-philippe@linaro.org>

Obtain the max vector length configured by userspace on the vCPUs, and
write it into the Realm parameters. By default the vCPU is configured
with the max vector length reported by RMM, and userspace can reduce it
with a write to KVM_REG_ARM64_SVE_VLS.

Signed-off-by: Jean-Philippe Brucker <jean-philippe@linaro.org>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v6:
 * Rename max_vl/realm_max_vl to vl/last_vl - there is nothing "maximum"
   about them, we're just checking that all realms have the same vector
   length
---
 arch/arm64/kvm/guest.c |  3 ++-
 arch/arm64/kvm/rmi.c   | 37 +++++++++++++++++++++++++++++++++++++
 2 files changed, 39 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index a92bd07ef53a..5f451ee18649 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -361,7 +361,7 @@ static int set_sve_vls(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg)
 	if (!vcpu_has_sve(vcpu))
 		return -ENOENT;
 
-	if (kvm_arm_vcpu_sve_finalized(vcpu))
+	if (kvm_arm_vcpu_sve_finalized(vcpu) || kvm_realm_is_created(vcpu->kvm))
 		return -EPERM; /* too late! */
 
 	if (WARN_ON(vcpu->arch.sve_state))
@@ -754,6 +754,7 @@ static bool validate_realm_set_reg(struct kvm_vcpu *vcpu,
 	} else {
 		switch (reg->id) {
 		case KVM_REG_ARM_ID_AA64DFR0_EL1:
+		case KVM_REG_ARM64_SVE_VLS:
 			return true;
 		}
 	}
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 35ad65efa5db..732cecb11355 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -468,6 +468,39 @@ static void realm_unmap_shared_range(struct kvm *kvm,
 			     start, end);
 }
 
+static int realm_init_sve_param(struct kvm *kvm, struct realm_params *params)
+{
+	unsigned long i;
+	struct kvm_vcpu *vcpu;
+	int vl, last_vl = -1;
+
+	if (!kvm_has_sve(kvm))
+		return 0;
+
+	/*
+	 * Get the preferred SVE configuration, set by userspace with the
+	 * KVM_ARM_VCPU_SVE feature and KVM_REG_ARM64_SVE_VLS pseudo-register.
+	 */
+	kvm_for_each_vcpu(i, vcpu, kvm) {
+		if (!kvm_arm_vcpu_sve_finalized(vcpu))
+			return -EINVAL;
+
+		vl = vcpu->arch.sve_max_vl;
+
+		/* We need all vCPUs to have the same SVE config */
+		if (last_vl >= 0 && last_vl != vl)
+			return -EINVAL;
+
+		last_vl = vl;
+	}
+
+	if (last_vl > 0) {
+		params->sve_vl = sve_vq_from_vl(last_vl) - 1;
+		params->flags |= RMI_REALM_PARAM_FLAG_SVE;
+	}
+	return 0;
+}
+
 static int realm_create_rd(struct kvm *kvm)
 {
 	struct realm *realm = &kvm->arch.realm;
@@ -513,6 +546,10 @@ static int realm_create_rd(struct kvm *kvm)
 	if (kvm_lpa2_is_enabled())
 		params->flags |= RMI_REALM_PARAM_FLAG_LPA2;
 
+	r = realm_init_sve_param(kvm, params);
+	if (r)
+		goto out_undelegate_tables;
+
 	params_phys = virt_to_phys(params);
 
 	if (rmi_realm_create(rd_phys, params_phys)) {

---

## [43] Steven Price — 2026-05-13
*Subject: [PATCH v14 42/44] arm64: RMI: Provide register list for unfinalized RMI RECs*

From: Jean-Philippe Brucker <jean-philippe@linaro.org>

KVM_GET_REG_LIST should not be called before SVE is finalized. The ioctl
handler currently returns -EPERM in this case. But because it uses
kvm_arm_vcpu_is_finalized(), it now also rejects the call for
unfinalized REC even though finalizing the REC can only be done late,
after Realm descriptor creation.

Move the check to copy_sve_reg_indices(). One adverse side effect of
this change is that a KVM_GET_REG_LIST call that only probes for the
array size will now succeed even if SVE is not finalized, but that seems
harmless since the following KVM_GET_REG_LIST with the full array will
fail.

Signed-off-by: Jean-Philippe Brucker <jean-philippe@linaro.org>
Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
---
 arch/arm64/kvm/arm.c   |  4 ----
 arch/arm64/kvm/guest.c | 10 +++++-----
 2 files changed, 5 insertions(+), 9 deletions(-)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index aacbeb524b6a..902ca4cf4fa5 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -1944,10 +1944,6 @@ long kvm_arch_vcpu_ioctl(struct file *filp,
 		if (unlikely(!kvm_vcpu_initialized(vcpu)))
 			break;
 
-		r = -EPERM;
-		if (!kvm_arm_vcpu_is_finalized(vcpu))
-			break;
-
 		r = -EFAULT;
 		if (copy_from_user(&reg_list, user_list, sizeof(reg_list)))
 			break;
diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index 5f451ee18649..a55618cd7a27 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -617,8 +617,8 @@ static unsigned long num_sve_regs(const struct kvm_vcpu *vcpu)
 	if (!vcpu_has_sve(vcpu))
 		return 0;
 
-	/* Policed by KVM_GET_REG_LIST: */
-	WARN_ON(!kvm_arm_vcpu_sve_finalized(vcpu));
+	if (!kvm_arm_vcpu_sve_finalized(vcpu))
+		return 1; /* KVM_REG_ARM64_SVE_VLS */
 
 	return slices * (SVE_NUM_PREGS + SVE_NUM_ZREGS + 1 /* FFR */)
 		+ 1; /* KVM_REG_ARM64_SVE_VLS */
@@ -635,9 +635,6 @@ static int copy_sve_reg_indices(const struct kvm_vcpu *vcpu,
 	if (!vcpu_has_sve(vcpu))
 		return 0;
 
-	/* Policed by KVM_GET_REG_LIST: */
-	WARN_ON(!kvm_arm_vcpu_sve_finalized(vcpu));
-
 	/*
 	 * Enumerate this first, so that userspace can save/restore in
 	 * the order reported by KVM_GET_REG_LIST:
@@ -647,6 +644,9 @@ static int copy_sve_reg_indices(const struct kvm_vcpu *vcpu,
 		return -EFAULT;
 	++num_regs;
 
+	if (!kvm_arm_vcpu_sve_finalized(vcpu))
+		return num_regs;
+
 	for (i = 0; i < slices; i++) {
 		for (n = 0; n < SVE_NUM_ZREGS; n++) {
 			reg = KVM_REG_ARM64_SVE_ZREG(n, i);

---

## [44] Steven Price — 2026-05-13
*Subject: [PATCH v14 43/44] arm64: RMI: Provide accurate register list*

From: Jean-Philippe Brucker <jean-philippe@linaro.org>

Userspace can set a few registers with KVM_SET_ONE_REG (9 GP registers
at runtime, and 3 system registers during initialization). Update the
register list returned by KVM_GET_REG_LIST.

Signed-off-by: Jean-Philippe Brucker <jean-philippe@linaro.org>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v11:
 * Reworked due to upstream changes.
Changes since v8:
 * Minor type changes following review.
Changes since v7:
 * Reworked on upstream changes.
---
 arch/arm64/kvm/guest.c      |  6 ++++++
 arch/arm64/kvm/hypercalls.c |  4 ++--
 arch/arm64/kvm/sys_regs.c   | 27 +++++++++++++++++++++------
 3 files changed, 29 insertions(+), 8 deletions(-)

diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index a55618cd7a27..4f34eed9dbbb 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -620,6 +620,9 @@ static unsigned long num_sve_regs(const struct kvm_vcpu *vcpu)
 	if (!kvm_arm_vcpu_sve_finalized(vcpu))
 		return 1; /* KVM_REG_ARM64_SVE_VLS */
 
+	if (kvm_is_realm(vcpu->kvm))
+		return 1; /* KVM_REG_ARM64_SVE_VLS */
+
 	return slices * (SVE_NUM_PREGS + SVE_NUM_ZREGS + 1 /* FFR */)
 		+ 1; /* KVM_REG_ARM64_SVE_VLS */
 }
@@ -647,6 +650,9 @@ static int copy_sve_reg_indices(const struct kvm_vcpu *vcpu,
 	if (!kvm_arm_vcpu_sve_finalized(vcpu))
 		return num_regs;
 
+	if (kvm_is_realm(vcpu->kvm))
+		return num_regs;
+
 	for (i = 0; i < slices; i++) {
 		for (n = 0; n < SVE_NUM_ZREGS; n++) {
 			reg = KVM_REG_ARM64_SVE_ZREG(n, i);
diff --git a/arch/arm64/kvm/hypercalls.c b/arch/arm64/kvm/hypercalls.c
index 58c5fe7d7572..70ac7971416c 100644
--- a/arch/arm64/kvm/hypercalls.c
+++ b/arch/arm64/kvm/hypercalls.c
@@ -414,14 +414,14 @@ void kvm_arm_teardown_hypercalls(struct kvm *kvm)
 
 int kvm_arm_get_fw_num_regs(struct kvm_vcpu *vcpu)
 {
-	return ARRAY_SIZE(kvm_arm_fw_reg_ids);
+	return kvm_is_realm(vcpu->kvm) ? 0 : ARRAY_SIZE(kvm_arm_fw_reg_ids);
 }
 
 int kvm_arm_copy_fw_reg_indices(struct kvm_vcpu *vcpu, u64 __user *uindices)
 {
 	int i;
 
-	for (i = 0; i < ARRAY_SIZE(kvm_arm_fw_reg_ids); i++) {
+	for (i = 0; i < kvm_arm_get_fw_num_regs(vcpu); i++) {
 		if (put_user(kvm_arm_fw_reg_ids[i], uindices++))
 			return -EFAULT;
 	}
diff --git a/arch/arm64/kvm/sys_regs.c b/arch/arm64/kvm/sys_regs.c
index 607396f378dc..2887f90b3b4e 100644
--- a/arch/arm64/kvm/sys_regs.c
+++ b/arch/arm64/kvm/sys_regs.c
@@ -5547,18 +5547,18 @@ int kvm_arm_sys_reg_set_reg(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg
 				    sys_reg_descs, ARRAY_SIZE(sys_reg_descs));
 }
 
-static unsigned int num_demux_regs(void)
+static inline unsigned int num_demux_regs(struct kvm_vcpu *vcpu)
 {
-	return CSSELR_MAX;
+	return kvm_is_realm(vcpu->kvm) ? 0 : CSSELR_MAX;
 }
 
-static int write_demux_regids(u64 __user *uindices)
+static int write_demux_regids(struct kvm_vcpu *vcpu, u64 __user *uindices)
 {
 	u64 val = KVM_REG_ARM64 | KVM_REG_SIZE_U32 | KVM_REG_ARM_DEMUX;
 	unsigned int i;
 
 	val |= KVM_REG_ARM_DEMUX_ID_CCSIDR;
-	for (i = 0; i < CSSELR_MAX; i++) {
+	for (i = 0; i < num_demux_regs(vcpu); i++) {
 		if (put_user(val | i, uindices))
 			return -EFAULT;
 		uindices++;
@@ -5602,11 +5602,26 @@ static bool copy_reg_to_user(const struct sys_reg_desc *reg, u64 __user **uind)
 	return true;
 }
 
+static inline bool kvm_realm_sys_reg_hidden_user(const struct kvm_vcpu *vcpu,
+						 u64 reg)
+{
+	switch (reg) {
+	case SYS_ID_AA64DFR0_EL1:
+	case SYS_PMCR_EL0:
+		return false;
+	}
+	return true;
+}
+
 static int walk_one_sys_reg(const struct kvm_vcpu *vcpu,
 			    const struct sys_reg_desc *rd,
 			    u64 __user **uind,
 			    unsigned int *total)
 {
+	if (vcpu_is_rec(vcpu) &&
+	    kvm_realm_sys_reg_hidden_user(vcpu, reg_to_encoding(rd)))
+		return 0;
+
 	/*
 	 * Ignore registers we trap but don't save,
 	 * and for which no custom user accessor is provided.
@@ -5644,7 +5659,7 @@ static int walk_sys_regs(struct kvm_vcpu *vcpu, u64 __user *uind)
 
 unsigned long kvm_arm_num_sys_reg_descs(struct kvm_vcpu *vcpu)
 {
-	return num_demux_regs()
+	return num_demux_regs(vcpu)
 		+ walk_sys_regs(vcpu, (u64 __user *)NULL);
 }
 
@@ -5657,7 +5672,7 @@ int kvm_arm_copy_sys_reg_indices(struct kvm_vcpu *vcpu, u64 __user *uindices)
 		return err;
 	uindices += err;
 
-	return write_demux_regids(uindices);
+	return write_demux_regids(vcpu, uindices);
 }
 
 #define KVM_ARM_FEATURE_ID_RANGE_INDEX(r)			\

---

## [45] Steven Price — 2026-05-13
*Subject: [PATCH v14 44/44] arm64: RMI: Enable realms to be created*

All the pieces are now in place, so enable kvm_rmi_is_available when the
RMM is detected.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/kvm/rmi.c | 3 ++-
 1 file changed, 2 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 732cecb11355..67c1d1526b07 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -1396,5 +1396,6 @@ void kvm_init_rmi(void)
 	if (rmm_check_features())
 		return;
 
-	/* Future patch will enable static branch kvm_rmi_is_available */
+	kvm_info("Realm guests supported");
+	static_branch_enable(&kvm_rmi_is_available);
 }

---

## [46] Aneesh Kumar K.V — 2026-05-14
*Subject: Re: [PATCH v14 10/44] arm64: RMI: Add support for SRO*

Steven Price <steven.price@arm.com> writes:

> +unsigned long rmi_sro_execute(struct rmi_sro_state *sro, gfp_t gfp)
> +{

Can you also add support to return x1,x2 etc

This would help things like

static int rmi_rtt_dev_unmap(unsigned long rd_phys,
		unsigned long base, unsigned long top,
		unsigned long *out_ipa, unsigned long *out_desc,
		unsigned long *rmi_ret)
{
	unsigned long flags = RMI_ADDR_TYPE_SINGLE;
	struct rmi_sro_state *sro __free(sro) =
		rmi_sro_init(SMC_RMI_RTT_DEV_UNMAP, rd_phys, base, top, flags, NULL);
	if (!sro)
		return -ENOMEM;

	*rmi_ret = rmi_sro_execute(sro);
	if (*rmi_ret)
		return 0;

	*out_ipa = sro->regs.a1;
	*out_desc = sro->regs.a2;

	return 0;
}

-aneesh

---

## [47] Steven Price — 2026-05-14
*Subject: Re: [PATCH v14 10/44] arm64: RMI: Add support for SRO*

On 14/05/2026 09:01, Aneesh Kumar K.V wrote:
> Steven Price <steven.price@arm.com> writes:
> 

Indeed that's going to be needed. Looking at this function again I don't 
think we actually need the on-stack 'regs' any more. So the below (very 
lightly tested) diff would use the regs from sro which also means they 
will be there for the caller if it needs them.

Thanks,
Steve

---8<---
diff --git a/arch/arm64/kernel/rmi.c b/arch/arm64/kernel/rmi.c
index a8107ca9bb6d..58a0216be409 100644
--- a/arch/arm64/kernel/rmi.c
+++ b/arch/arm64/kernel/rmi.c
@@ -356,30 +356,29 @@ void rmi_sro_free(struct rmi_sro_state *sro)
 unsigned long rmi_sro_execute(struct rmi_sro_state *sro, gfp_t gfp)
 {
 	unsigned long sro_handle;
-	struct arm_smccc_1_2_regs regs;
-	struct arm_smccc_1_2_regs *regs_in = &sro->regs;
+	struct arm_smccc_1_2_regs *regs = &sro->regs;
 
-	rmi_smccc_invoke(regs_in, &regs);
+	rmi_smccc_invoke(regs, regs);
 
-	sro_handle = regs.a1;
+	sro_handle = regs->a1;
 
-	while (RMI_RETURN_STATUS(regs.a0) == RMI_INCOMPLETE) {
-		bool can_cancel = RMI_RETURN_CAN_CANCEL(regs.a0);
+	while (RMI_RETURN_STATUS(regs->a0) == RMI_INCOMPLETE) {
+		bool can_cancel = RMI_RETURN_CAN_CANCEL(regs->a0);
 		int ret;
 
-		switch (RMI_RETURN_MEMREQ(regs.a0)) {
+		switch (RMI_RETURN_MEMREQ(regs->a0)) {
 		case RMI_OP_MEM_REQ_NONE:
-			regs = (struct arm_smccc_1_2_regs){
+			*regs = (struct arm_smccc_1_2_regs){
 				SMC_RMI_OP_CONTINUE, sro_handle, 0
 			};
-			rmi_smccc_invoke(&regs, &regs);
+			rmi_smccc_invoke(regs, regs);
 			break;
 		case RMI_OP_MEM_REQ_DONATE:
-			ret = rmi_sro_donate(sro, sro_handle, regs.a2, &regs,
+			ret = rmi_sro_donate(sro, sro_handle, regs->a2, regs,
 					     gfp);
 			break;
 		case RMI_OP_MEM_REQ_RECLAIM:
-			ret = rmi_sro_reclaim(sro, sro_handle, &regs);
+			ret = rmi_sro_reclaim(sro, sro_handle, regs);
 			break;
 		default:
 			ret = WARN_ON(1);
@@ -404,7 +403,7 @@ unsigned long rmi_sro_execute(struct rmi_sro_state *sro, gfp_t gfp)
 		}
 	}
 
-	return regs.a0;
+	return regs->a0;
 }
 
 static int rmi_check_version(void)

---

## [48] Gavin Shan — 2026-05-18
*Subject: Re: [PATCH v14 04/44] arm64: RMI: Add SMC definitions for calling the
 RMM*

Hi Steven,

On 5/13/26 11:17 PM, Steven Price wrote:
> The RMM (Realm Management Monitor) provides functionality that can be
> accessed by SMC calls from the host.

Those definations are inconsistent to those defined in tf-rmm/lib/smc/include/smc-rmi.h
where their size are 64-bits. Also, other two definations are missed here and perhaps
worthy to be added here.

#define RMI_ASSIGNED_DEV        UL(3)
#define RMI_AUX_DESTROYED       UL(5)


> +#define RMI_RETURN_STATUS(ret)		((ret) & 0xFF)
> +#define RMI_RETURN_INDEX(ret)		(((ret) >> 8) & 0xFF)

The size of those definations are 32-bits, different to that of them defined
in tf-rmm/lib/smc/include/smc-rmi.h

#define RMI_OP_MEM_REQ_NONE             (0UL)
#define RMI_OP_MEM_REQ_DONATE           (1UL)
#define RMI_OP_MEM_REQ_RECLAIM          (2UL)

> +#define RMI_DONATE_SIZE(req)		((req) & 0x3)
> +#define RMI_DONATE_COUNT_MASK		GENMASK(15, 2)

As above, inconsistent size to those definations in tf-rmm/lib/smc/include/smc-rmi.h

> +#define RMI_ADDR_TYPE_NONE		0
> +#define RMI_ADDR_TYPE_SINGLE		1

As above, inconsistent size to those definations in tf-rmm/lib/smc/include/smc-rmi.h

> +#define RMI_ADDR_RANGE_SIZE_MASK	GENMASK(1, 0)
> +#define RMI_ADDR_RANGE_COUNT_MASK	GENMASK(PAGE_SHIFT - 1, 2)

Thanks,
Gavin

---

## [49] Aneesh Kumar K.V — 2026-05-19
*Subject: Re: [PATCH v14 05/44] arm64: RMI: Add wrappers for RMI calls*

Steven Price <steven.price@arm.com> writes:

> The wrappers make the call sites easier to read and deal with the
> boiler plate of handling the error codes from the RMM.

I guess this is not used. Also, that would require the call site to have a struct arm_smccc_res res.


-aneesh

---

## [50] Aneesh Kumar K.V — 2026-05-19
*Subject: Re: [PATCH v14 08/44] arm64: RMI: Ensure that the RMM has GPT
 entries for memory*

> +
> +bool rmi_is_available(void)

Can we rename to is_rmi_available(void) ?

-aneesh

---

## [51] Aneesh Kumar K.V — 2026-05-19
*Subject: Re: [PATCH v14 10/44] arm64: RMI: Add support for SRO*

Steven Price <steven.price@arm.com> writes:

> +static unsigned long donate_req_to_size(unsigned long donatereq)
> +{

Looking at above and the related code, I am wondering whether we should
use u64 instead of unsigned long for everything that the specification
defines as 64-bit.

-aneesh

---

## [52] Aneesh Kumar K.V — 2026-05-19
*Subject: Re: [PATCH v14 14/44] arm64: RMI: Basic infrastructure for creating
 a realm.*

Steven Price <steven.price@arm.com> writes:

> @@ -1114,7 +1119,10 @@ void kvm_free_stage2_pgd(struct kvm_s2_mmu *mmu)
>  	write_unlock(&kvm->mmu_lock);

Maybe add a comment here explaining the difference.

We now have:

kvm_arch_destroy_vm()
  -> kvm_uninit_stage2_mmu()
       -> kvm_realm_uninit_stage2()
            -> unmap_range(0, max_ipa)        // for Realm VMs
       -> kvm_free_stage2_pgd()
            -> unmap and free PGD             // for non-Realm VMs
  -> kvm_destroy_realm()                      // for Realm VMs
       -> kvm_free_stage2_pgd()
            -> free PGD                       // for Realm VMs

I wonder whether this can be simplified using different functions names?
(can we call kvm_pgtable_stage2_destroy_pgd() from kvm_destroy_realm()? )

-aneesh

---

## [53] Aneesh Kumar K.V — 2026-05-19
*Subject: Re: [PATCH v14 17/44] arm64: RMI: RTT tear down*

Steven Price <steven.price@arm.com> writes:
> +static void kvm_realm_uninit_stage2(struct kvm_s2_mmu *mmu)
> +{

We also call kvm_stage2_unmap_range in kvm_destroy_realm()

void kvm_destroy_realm(struct kvm *kvm)
{
...
	write_lock(&kvm->mmu_lock);
	kvm_stage2_unmap_range(&kvm->arch.mmu, 0,
			       BIT(realm->ia_bits - 1), true);
	write_unlock(&kvm->mmu_lock);
        
-aneesh

---

## [54] Aneesh Kumar K.V — 2026-05-19
*Subject: Re: [PATCH v14 23/44] arm64: RMI: Handle RMI_EXIT_RIPAS_CHANGE*

Steven Price <steven.price@arm.com> writes:

...

> +void kvm_realm_unmap_range(struct kvm *kvm, unsigned long start,
> +			   unsigned long size, bool unmap_private,
 
kvm_gmem_invalidate_begin() indicates a private-only invalidation. How
is that supported?

-aneesh

---

## [55] Aneesh Kumar K.V — 2026-05-19
*Subject: Re: [PATCH v14 27/44] arm64: RMI: Set RIPAS of initial memslots*

Steven Price <steven.price@arm.com> writes:

> The memory which the realm guest accesses must be set to RIPAS_RAM.
> Iterate over the memslots and set all gmem memslots to RIPAS_RAM.
 
 ...
 
> +static int set_ripas_of_protected_regions(struct kvm *kvm)
> +{

relam guest already does. 
	for_each_mem_range(i, &start, &end) {
		if (rsi_set_memory_range_protected_safe(start, end)) {
			panic("Failed to set memory range to protected: %pa-%pa",
			      &start, &end);
		}
	}

if so why is host required to do this ?

-aneesh

---

## [56] Suzuki K Poulose — 2026-05-19
*Subject: Re: [PATCH v14 27/44] arm64: RMI: Set RIPAS of initial memslots*

On 19/05/2026 11:02, Aneesh Kumar K.V wrote:
> Steven Price <steven.price@arm.com> writes:
> 

Ideally this should be a call from the VMM (i.e., user). Irrespective of
what the guest does (which the host has no knowledge about), the VMM/
user is better aware of what to do for a given guest. We have done this
implicitly in the KVM as a start, to keep the initial implementation
simple. This could be moved out to the VMM as UABI, if there is
sufficient demand for it.

TL,DR: This should be a host/deployer decision, not the Guest. There
may other guest OS, which do not do RIPAS_RAM early enough.

Suzuki

---

## [57] Aneesh Kumar K.V — 2026-05-19
*Subject: Re: [PATCH v14 37/44] arm64: RMI: Prevent Device mappings for Realms*

Steven Price <steven.price@arm.com> writes:

> Physical device assignment is not yet supported. RMM v2.0 does add the
> relevant APIs, but device assignment is a big topic so will be handled

The commit message suggests that this will need to be updated to support
Device Assignment, but that is not true. IIUC, this is only used by
GICv2?. Can we update the commit message?

-aneesh

---

## [58] Aneesh Kumar K.V — 2026-05-19
*Subject: Re: [PATCH v14 27/44] arm64: RMI: Set RIPAS of initial memslots*

Suzuki K Poulose <suzuki.poulose@arm.com> writes:

> On 19/05/2026 11:02, Aneesh Kumar K.V wrote:
>> Steven Price <steven.price@arm.com> writes:

Are we suggesting that when the guest is running out of DRAM initialized
via rmi_rtt_data_map_init(), it may need to access memory outside that
range before it gets a chance to set the RIPAS as RAM?

Does that mean the guest now has to trust the host for that?
rmi_rtt_init_ripas() is not added to the measurement details, right?

-aneesh

---

## [59] Suzuki K Poulose — 2026-05-19
*Subject: Re: [PATCH v14 27/44] arm64: RMI: Set RIPAS of initial memslots*

On 19/05/2026 13:55, Aneesh Kumar K.V wrote:
> Suzuki K Poulose <suzuki.poulose@arm.com> writes:
> 

It may. This was one of the review comments we got when we published
the Linux Guest patches. In fact, this is in the Linux booting
requirements. See :

Documentation/arch/arm64/booting.rst: Section 1


> 
> Does that mean the guest now has to trust the host for that?

No, this has been the case. We added the code in Linux to convert memory
as a back stop. The worse could happens is Guest crashing, without it
having any secrets receving from the Remote entity.

> rmi_rtt_init_ripas() is not added to the measurement details, right?

It is not (at least for now). It doesn't matter for security much.

Suzuki

> 
> -aneesh

---

## [60] Steven Price — 2026-05-20
*Subject: Re: [PATCH v14 04/44] arm64: RMI: Add SMC definitions for calling the
 RMM*

On 18/05/2026 08:08, Gavin Shan wrote:
> Hi Steven,
> 

Actually these should really be removed altogether (they are no longer
used in the code). The spec names for these have also changed, the new
names are:

0 VOID
1 DATA
2 TABLE
3 NARCH_DEV
4 AUX_DESTROYED
5 ARCH_DEV

> #define RMI_ASSIGNED_DEV        UL(3)
> #define RMI_AUX_DESTROYED       UL(5)

So this looks like the RMM versions are also out of date.

> 
> 

Well the size according to the spec is a 2 bit enumeration.
RMI_RETURN_MEMREQ() is used to extract it from the result. I can update
all (or at least most) of the integers in this file to have a UL suffix
if there's a good reason. Ultimately the values are passed in the 64 bit
registers which Linux uses unsigned long for so it does make some sense
- but it seems a little unneceesary to me when the values are known to
fix within the size of an int (32 bits).

Note that the TF-RMM project isn't the "truth" - it is just 'one
implementation' - the spec is the real arbiter on these matters.

> 
>> +#define RMI_DONATE_SIZE(req)        ((req) & 0x3)

As above these are enumerations that are 2 bits (well RMI_OP_MEM_xxx was
originally 1 bit and is now 2 bits in the 2.0-bet2 spec - I'll update to
include the new value when moving to the new spec).

Thanks,
Steve

>> +#define RMI_ADDR_RANGE_SIZE_MASK    GENMASK(1, 0)
>> +#define RMI_ADDR_RANGE_COUNT_MASK    GENMASK(PAGE_SHIFT - 1, 2)

---

## [61] Gavin Shan — 2026-05-21
*Subject: Re: [PATCH v14 05/44] arm64: RMI: Add wrappers for RMI calls*

Hi Steven,

On 5/13/26 11:17 PM, Steven Price wrote:
> The wrappers make the call sites easier to read and deal with the
> boiler plate of handling the error codes from the RMM.

[...]

> +
> +/**

In most cases, the parameters are well explained in RMM-v2.0-bet1 spec, I think
it's nice to keep the code and the spec synchronized. For those specific parameters
of this function, they're well explained in RMM-v2.0-bet1 spec as below.

    @rd: PA of the RD for the target realm
    @ipa: Base of the IPA range described by the RTT
    @level: RTT level
    @out_rtt: PA of the RTT which was destroyed
    @out_top: Top IPA of non-live RTT entries, from entry at which the RTT walk terminated

> + * Destroys an RTT. The RTT must be non-live, i.e. none of the entries in the
> + * table are in ASSIGNED or TABLE state.

[...]

Thanks,
Gavin

---

## [62] Gavin Shan — 2026-05-21
*Subject: Re: [PATCH v14 06/44] arm64: RMI: Check for RMI support at init*

Hi Steven,

On 5/13/26 11:17 PM, Steven Price wrote:
> Query the RMI version number and check if it is a compatible version.
> The first two feature registers are read and exposed for future code to

[...]

> diff --git a/arch/arm64/kernel/rmi.c b/arch/arm64/kernel/rmi.c
> new file mode 100644

Is this still a valid point that we have to return zero on errors returned
from rmi_check_version() or other other function calls like rmi_features()?
arm64_init_rmi() is triggered by subsys_initcall() where the return value
needs to indicate success or failure. It's fine to return error code from
arm64_init_rmi() in the path.

> +
> +	if (WARN_ON(rmi_features(0, &rmm_feat_reg0)))

Thanks,
Gavin

---

## [63] Gavin Shan — 2026-05-21
*Subject: Re: [PATCH v14 07/44] arm64: RMI: Configure the RMM with the host's
 page size*

Hi Steven,

On 5/13/26 11:17 PM, Steven Price wrote:
> RMM v2.0 brings the ability to set the RMM's granule size. Check the
> feature registers and configure the RMM so that it matches the host's

Looking at branch 'topics/rmm-v2.0-poc_2' of RMM implementation, the granule size
is fixed to be 4KB at present. I'm not sure if I have looked into correct RMM
implementation, but 'topics/rmm-v2.0-poc_2' is recommended one in the cover
letter.

Besides, there has checks in the handler of the RMI command to make sure that
struct rmm_config::tracking_region_size to be 1GB, indicated by zero. It maybe
worthy to set it before call to rmi_rmm_config_set().

	config.tracking_region_size = 0; /* 1GB */
	ret = rmi_rmm_config_set(virt_to_phys(config));


> +	ret = rmi_rmm_activate();
> +	if (ret) {

Thanks,
Gavin

---

## [64] Gavin Shan — 2026-05-21
*Subject: Re: [PATCH v14 08/44] arm64: RMI: Ensure that the RMM has GPT entries
 for memory*

Hi Steven,

On 5/13/26 11:17 PM, Steven Price wrote:
> The RMM maintains the state of all the granules in the system to make
> sure that the host is abiding by the rules. This state can be maintained

RMM_GRANULE_TRACKING_SIZE is never used in this series.

> +/*
> + * Make sure the area is tracked by RMM at FINE granularity.

rmi_l0gpt_size() is only used by rmi_create_gpts(), its logic can be
combined to that function.

> +static int rmi_create_gpts(phys_addr_t start, phys_addr_t end)
> +{

Thanks,
Gavin

---

## [65] Gavin Shan — 2026-05-21
*Subject: Re: [PATCH v14 10/44] arm64: RMI: Add support for SRO*

Hi Steven,

On 5/13/26 11:17 PM, Steven Price wrote:
> RMM v2.0 introduces the concept of "Stateful RMI Operations" (SRO). This
> means that an SMC can return with an operation still in progress. The

It's worthy to have 'inline'. {P4D, PUD, PMD}_SIZE can be equal if there are
no P4D and PUD, depending on CONFIG_PGTABLE_LEVELS. In this case, can the
'unit_size' be translated to wrong value?

> +static void rmi_smccc_invoke(struct arm_smccc_1_2_regs *regs_in,
> +			     struct arm_smccc_1_2_regs *regs_out)

alloc_pages_exact() will fail if the requested size exceeds the maximal allowed
size (1 << MAX_PAGE_ORDER). The maximal size is usually smaller than PUD_SIZE
but PUD_SIZE is allowed by the RMM.

> +	if (state == RMI_OP_MEM_DELEGATED) {
> +		if (rmi_delegate_range(phys, size)) {

'ret' isn't initialized for case RMI_OP_MEM_REQ_NONE.

> +		case RMI_OP_MEM_REQ_DONATE:
> +			ret = rmi_sro_donate(sro, sro_handle, regs.a2, &regs,

Thanks,
Gavin

---

## [66] Marc Zyngier — 2026-05-21
*Subject: Re: [PATCH v14 01/44] kvm: arm64: Include kvm_emulate.h in kvm/arm_psci.h*

On Wed, 13 May 2026 14:17:09 +0100,
Steven Price <steven.price@arm.com> wrote:
> 
> From: Suzuki K Poulose <suzuki.poulose@arm.com>

Unrelated to this patch, but really easy to fix: the standard prefix
for patches targeting KVM/arm64 is:

"KVM: arm64: [opt subsys:] Something starting with a capital letter"

where "opt subsys" could be "CCA" where applicable.

It'd be good to have some consistency.

Thanks,

	M.

---

## [67] Marc Zyngier — 2026-05-21
*Subject: Re: [PATCH v14 02/44] kvm: arm64: Avoid including linux/kvm_host.h in kvm_pgtable.h*

On Wed, 13 May 2026 14:17:10 +0100,
Steven Price <steven.price@arm.com> wrote:
> 
> To avoid future include cycles, drop the linux/kvm_host.h include in

I'm surprised by this. Where is the rbtree_type.h requirement coming
from?

Thanks,

	M.

---

## [68] Marc Zyngier — 2026-05-21
*Subject: Re: [PATCH v14 03/44] arm64: RME: Handle Granule Protection Faults (GPFs)*

On Wed, 13 May 2026 14:17:11 +0100,
Steven Price <steven.price@arm.com> wrote:
> 
> If the host attempts to access granules that have been delegated for use

It wouldn't hurt to align the textual description with what we have
for other fault syndromes:

	"level X granule protection fault (translation table walk)"

for the PTW-trigger faults, and

	"granule protection fault"

for the non PTW case.

Thanks,

	M.

---

## [69] Marc Zyngier — 2026-05-21
*Subject: Re: [PATCH v14 04/44] arm64: RMI: Add SMC definitions for calling the RMM*

On Wed, 13 May 2026 14:17:12 +0100,
Steven Price <steven.price@arm.com> wrote:
> 
> The RMM (Realm Management Monitor) provides functionality that can be

How long is this spec going to be available on the ARM web site, which
has a tendency of being reorganised every other week? And there is
already a beta2.

> + */
> +

Use FIELD_GET() and specify masks that define the actual fields.

> +
> +#define RMI_SUCCESS			0

FIELD_GET().

> +
> +#define RMI_OP_MEM_DELEGATED		0

SZ_4K?

> +	};
> +};

SZ_1K? And similarly all over the shop?

I haven't checked the details of the encodings (life is too short),
but I wonder how much of this exists as an MRS and could be
automatically generated?

Thanks,

	M.

---

## [70] Marc Zyngier — 2026-05-21
*Subject: Re: [PATCH v14 05/44] arm64: RMI: Add wrappers for RMI calls*

On Wed, 13 May 2026 14:17:13 +0100,
Steven Price <steven.price@arm.com> wrote:
> 
> The wrappers make the call sites easier to read and deal with the

Is that part of the SRO stuff you're talking about in the notes?
What is the ETA for fixing all these FIXMEs?

Thanks,

	M.

---

## [71] Marc Zyngier — 2026-05-21
*Subject: Re: [PATCH v14 06/44] arm64: RMI: Check for RMI support at init*

On Wed, 13 May 2026 14:17:14 +0100,
Steven Price <steven.price@arm.com> wrote:
> 
> Query the RMI version number and check if it is a compatible version.

What is the requirement for making those globally accessible? Can't
they be made static and use an accessor that returns them? Can the
variables be made __ro_after_init?

> +
> +static int rmi_check_version(void)

Is there any reliance on this being executed before or after KVM's own
initialisation? If so, this should be captured.

	M.

---

## [72] Marc Zyngier — 2026-05-21
*Subject: Re: [PATCH v14 07/44] arm64: RMI: Configure the RMM with the host's page size*

On Wed, 13 May 2026 14:17:15 +0100,
Steven Price <steven.price@arm.com> wrote:
> 
> RMM v2.0 brings the ability to set the RMM's granule size. Check the

This is the sort of buggy construct that is highlighted in
include/linux/cleanup.h: initialising the object for cleanup with
NULL, and only later assigning the expected value.

It may not matter here, but it will catch you (or more probably me) in
the future.

> +
> +	switch (PAGE_SIZE) {

Do you really anticipate PAGE_SIZE being any other value? This is 100%
dead code. If you want to be extra cautious, have a BUILD_BUg_ON().

> +		return -EINVAL;
> +	}

What is the live cycle of the page when the call succeeds? Is it
switched back to the NS PAS and allowed to be freed?

> +
> +	ret = rmi_rmm_activate();

Thanks,

	M.

---

## [73] Marc Zyngier — 2026-05-21
*Subject: Re: [PATCH v14 08/44] arm64: RMI: Ensure that the RMM has GPT entries for memory*

On Wed, 13 May 2026 14:17:16 +0100,
Steven Price <steven.price@arm.com> wrote:
> 
> The RMM maintains the state of all the granules in the system to make

Basically, a level 2 mapping. Which means this whole block really is:

#define RMM_GRANULE_TRAKING_SIZE	(2 * PAGE_SHIFT - 3)

(adjust for D128 as needed).

> +
> +/*

How is this triggered? Do we really need to spam the console with
this? A PA doesn't mean much, and there is no context (stack trace).

If that's not expected, turn this into a WARN_ONCE().

> +		}
> +		start = next;

If any of this fails, where is the cleanup done? Is that part of the
missing SRO support that's indicated in the commit message?

> +		}
> +		start += l0gpt_sz;

How does this work with, say, memory hotplug?

> +
> +	return 0;

Thanks,

	M.

---

## [74] Marc Zyngier — 2026-05-21
*Subject: Re: [PATCH v14 09/44] arm64: RMI: Provide functions to delegate/undelegate ranges of memory*

On Wed, 13 May 2026 14:17:17 +0100,
Steven Price <steven.price@arm.com> wrote:
> 
> The RMM requires memory is 'delegated' to it so that it can be used

I find it odd to warn on size = 0. After all, free(NULL) is not an
error. But even then, you continue feeding this to the RMM.

You also don't seem to be bothered with that on the delegation side...

> +
> +	while (phys < top) {

and size==0 doesn't violate any of the failure conditions listed in
B4.5.18.2 (beta2). Will you end-up looping around forever?

Same questions for the delegation, obviously.

	M.

---

## [75] Marc Zyngier — 2026-05-21
*Subject: Re: [PATCH v14 08/44] arm64: RMI: Ensure that the RMM has GPT entries for memory*

On Thu, 21 May 2026 14:47:55 +0100,
Marc Zyngier <maz@kernel.org> wrote:
> 
> On Wed, 13 May 2026 14:17:16 +0100,

Obviously wrong:

#define RMM_GRANULE_TRAKING_SIZE	BIT(2 * PAGE_SHIFT - 3)

	M.

---

## [76] Marc Zyngier — 2026-05-21
*Subject: Re: [PATCH v14 10/44] arm64: RMI: Add support for SRO*

On Wed, 13 May 2026 14:17:18 +0100,
Steven Price <steven.price@arm.com> wrote:
> 
> RMM v2.0 introduces the concept of "Stateful RMI Operations" (SRO). This

How does this work when we have folded levels? If this is supposed to
be the architected size, then it should actively express that:

	return BIT(unit_size * (PAGE_SHIFT - 3) + PAGE_SHIFT);

> +	}
> +	unreachable();

Please drop this WARN_ON(). Or at least make it ONCE. Everywhere.

> +		/* Undelegate failed: leak the page */
> +		return -EBUSY;

Shouldn't this be moved to a helper that ensures capacity, and returns
an error otherwise?

> +out:
> +	regs.a2 = virt_to_phys(&sro->addr_list[sro->addr_count]);

This could really do with context specific helpers that populate regs
based on a set of parameters. I have no idea what this 1 here is, and
the init is spread over too much code. Think of the children!

That's valid for the whole patch.

	M.
> +	rmi_smccc_invoke(&regs, out_regs);
> +

Honestly, this is the sort of stuff that I'd expect to be solved
*before* posting this code. Since this is so central to the whole
memory management, it needs to be correct from day-1.

If you can't make it work in time, then tone the supported features
down. But FIXMEs and WARN_ONs are not the way to go.

	M.

---

## [77] Suzuki K Poulose — 2026-05-21
*Subject: Re: [PATCH v14 04/44] arm64: RMI: Add SMC definitions for calling the
 RMM*

On 21/05/2026 13:40, Marc Zyngier wrote:
> On Wed, 13 May 2026 14:17:12 +0100,
> Steven Price <steven.price@arm.com> wrote:

Agreed to the comments above.

> 
> I haven't checked the details of the encodings (life is too short),

Good point. This is something that we can check and get back to you.

Thanks
Suzuki


> 
> Thanks,

---

## [78] Suzuki K Poulose — 2026-05-21
*Subject: Re: [PATCH v14 07/44] arm64: RMI: Configure the RMM with the host's
 page size*

On 21/05/2026 14:30, Marc Zyngier wrote:
> On Wed, 13 May 2026 14:17:15 +0100,
> Steven Price <steven.price@arm.com> wrote:

It always remains in the NS world. We relay some information in the
NS PAS page, which the RMM consumes. The checks are performed on
the values consumed by the RMM.

Kind regards
Suzuki

> 
>> +

---

## [79] Steven Price — 2026-05-21
*Subject: Re: [PATCH v14 01/44] kvm: arm64: Include kvm_emulate.h in
 kvm/arm_psci.h*

On 21/05/2026 11:19, Marc Zyngier wrote:
> On Wed, 13 May 2026 14:17:09 +0100,
> Steven Price <steven.price@arm.com> wrote:

Sure, I think back when I started this there wasn't great consistency so
I picked up something from git log. I'm happy to change this for the
next posting.

Thanks,
Steve

> 
> Thanks,

---

## [80] Steven Price — 2026-05-21
*Subject: Re: [PATCH v14 02/44] kvm: arm64: Avoid including linux/kvm_host.h in
 kvm_pgtable.h*

On 21/05/2026 11:26, Marc Zyngier wrote:
> On Wed, 13 May 2026 14:17:10 +0100,
> Steven Price <steven.price@arm.com> wrote:

struct kvm_pgtable has a "struct rb_root_cached" for pkvm_mappings.
There's definitely an argument that that's a bit ugly - but this seemed
the cleanest fix from a include perspective.

Thanks,
Steve

> 
> Thanks,

---

## [81] Steven Price — 2026-05-21
*Subject: Re: [PATCH v14 03/44] arm64: RME: Handle Granule Protection Faults
 (GPFs)*

On 21/05/2026 13:25, Marc Zyngier wrote:
> On Wed, 13 May 2026 14:17:11 +0100,
> Steven Price <steven.price@arm.com> wrote:

Sure, no problem.

Thanks,
Steve

> 
> Thanks,

---

## [82] Steven Price — 2026-05-21
*Subject: Re: [PATCH v14 04/44] arm64: RMI: Add SMC definitions for calling the
 RMM*

On 21/05/2026 13:40, Marc Zyngier wrote:
> On Wed, 13 May 2026 14:17:12 +0100,
> Steven Price <steven.price@arm.com> wrote:

Obviously I can't predict the next reorganisation - but at least it's a
link that could be fed into archive.org or similar.

There is a beta2 - that was released just after this series. I'll
obviously be updating to that shortly. Sadly the spec is still a bit of
a moving target, but hopefully all the major changes have already happened.

> 
>> + */

Sure, that makes sense.

>> +
>> +#define RMI_SUCCESS			0

I'm a bit less sure that makes the code more readable - these structures
are a bit of a pain because they are somewhat sparse. I've left a
comment where the beginning of each union is, and personally I find it
easier to see 0x0 + 0x400 == 0x400 rather than trying to work out what
SZ_1K is in hex. This is particularly the case in terms of:

> struct rec_params {
> 	union { /* 0x0 */

Where 0xd00 doesn't even have a correspoding SZ_ define.

The RMM deals with this with macro magic:

> struct rmi_rec_params {
>         /* Flags */

where the offsets are just directly encoded in the macro - but it's not
an especially robust macro and I'm not convinced it's more readable.

I'm happy to hear other suggestions on how to encode this neatly.

> I haven't checked the details of the encodings (life is too short),
> but I wonder how much of this exists as an MRS and could be

Automatically generating this would be good - I'm not sure whether we
have a (public) source available to generate from at the moment. I have
tried to methodically work through the spec when updating this file, but
as Gavin has already pointed out there was at least one mistake (in
currently unused definitions) this time.

Thanks,
Steve

---

## [83] Suzuki K Poulose — 2026-05-21
*Subject: Re: [PATCH v14 08/44] arm64: RMI: Ensure that the RMM has GPT entries
 for memory*

On 21/05/2026 14:47, Marc Zyngier wrote:
> On Wed, 13 May 2026 14:17:16 +0100,
> Steven Price <steven.price@arm.com> wrote:

True,

> 
>> +

This could be triggered if the RMM doesn't have static carveout
for tracking the DRAM granules. (state != RMI_TRACKING_FINE).
This not worth WARN_ONCE(), we could simply not enable KVM.
We plan to add support for donating memory to the RMM in
the future. (Primarily we don't yet have an RMM implementation
that does dynamic management via SRO. This can be added later
as a separate series)

> 
> If that's not expected, turn this into a WARN_ONCE().




> 
>> +		}

For now, there is no cleanup required. What we essentially do here is
making sure that the GPT tables have been created upto L1 (i.e.,
by checking ret == RMI_ERROR_GPT).

We do not donate any memory now, but only support RMMs with static 
memory carved out for L1 GPT. Support for dynamic RMMs could be added as
a separate series, at which point, we could defer the table creation to
the actual use case (e.g, RMI_GRANULE_DELEGATE).

Clean up would be required when we donate memory to the RMM.

>> +		}
>> +		start += l0gpt_sz;

Good point, we need a hook for hotpug to make sure this is taken care
of. As mentioned above, when we add support for RMM with support for
dynamic Tracking/GPT with SRO, this could be deferred to the actual
use (handling RMI return codes, RMI_ERROR_TRACKING/RMI_ERROR_GPT)

Suzuki


> 
>> +

---

## [84] Steven Price — 2026-05-21
*Subject: Re: [PATCH v14 05/44] arm64: RMI: Add wrappers for RMI calls*

On 19/05/2026 06:35, Aneesh Kumar K.V wrote:
> Steven Price <steven.price@arm.com> writes:
> 

Ah good spot - yes this was replaced with a proper static inline
rmi_smccc_invoke() function. I missed removing this macro.

Thanks,
Steve

---

## [85] Steven Price — 2026-05-21
*Subject: Re: [PATCH v14 05/44] arm64: RMI: Add wrappers for RMI calls*

On 21/05/2026 01:21, Gavin Shan wrote:
> Hi Steven,
> 

I have attempted to keep the descriptions consistent with the spec - I'm
not quite sure what you think the issue is here. The @rd parameter gains
a "for the target realm" - which isn't really very informative (clearly
rmi_rtt_destroy() is targetting the realm which is being passed into the
function). @level is less informative. @out_xxx are prefixed with
"Pointer to write the" because the C function does indeed take a pointer
for the output parameter to be written.

But fair enough I can align them more precisely. In some cases I've
written the code before the final spec wording has been available which
might explain some differences.

Thanks,
Steve

>> + * Destroys an RTT. The RTT must be non-live, i.e. none of the
>> entries in the

---

## [86] Steven Price — 2026-05-21
*Subject: Re: [PATCH v14 05/44] arm64: RMI: Add wrappers for RMI calls*

On 21/05/2026 13:49, Marc Zyngier wrote:
> On Wed, 13 May 2026 14:17:13 +0100,
> Steven Price <steven.price@arm.com> wrote:

Yes, RMI_INCOMPLETE is the return for SRO. Fixing all this up is on the
plan for my next posting which I expect to be after 7.2-rc1 (so July).
There were some changes in the beta 2 spec and the RMM doesn't implement
most of this yet so I didn't want to rush out completely untested code
which might change.

Thanks,
Steve

> Thanks,
>

---

## [87] Steven Price — 2026-05-21
*Subject: Re: [PATCH v14 06/44] arm64: RMI: Check for RMI support at init*

On 21/05/2026 01:39, Gavin Shan wrote:
> Hi Steven,
> 

Hmm, I guess now this is moved to arm64 code this indeed doesn't need
to. Within a module I believe an error return can fail the module loading.

I'm not sure it really makes much difference though - if this
initialisation fails then it's not really an error - it just means the
feature is unavailable.

Thanks,
Steve

>> +
>> +    if (WARN_ON(rmi_features(0, &rmm_feat_reg0)))

---

## [88] Suzuki K Poulose — 2026-05-21
*Subject: Re: [PATCH v14 09/44] arm64: RMI: Provide functions to
 delegate/undelegate ranges of memory*

On 21/05/2026 14:59, Marc Zyngier wrote:
> On Wed, 13 May 2026 14:17:17 +0100,
> Steven Price <steven.price@arm.com> wrote:

That is not true ? It triggers, top_bound error condition, for both.


pre: UInt(top) <= UInt(base)
post: result.status == RMI_ERROR_INPUT


Suzuki
> 
> Same questions for the delegation, obviously.

---

## [89] Suzuki K Poulose — 2026-05-21
*Subject: Re: [PATCH v14 07/44] arm64: RMI: Configure the RMM with the host's
 page size*

On 21/05/2026 01:51, Gavin Shan wrote:
> Hi Steven,
> 

You are right. The tf-RMM only supports 4KB. The policy at the KVM host
is to set the Linux PAGE_SIZE for the GRANULE_SIZE (at least for now).
If the RMM doesn't support the PAGE_SIZE, we don't support the RMM.


> Besides, there has checks in the handler of the RMI command to make sure 
> that

Thanks, this explicit initialisation is missing, though in effect the
value is 0'd. Also, we can't really say 1GB here, because the driver 
should work for an RMM capable of 64K. So, instead, may be we could :

	/* See the definition of RMM_GRANULE_TRACKING_SIZE */
	config.tracking_region_size = 0;

Suzuki


>      ret = rmi_rmm_config_set(virt_to_phys(config));
>

---

## [90] Marc Zyngier — 2026-05-22
*Subject: Re: [PATCH v14 04/44] arm64: RMI: Add SMC definitions for calling the RMM*

On Thu, 21 May 2026 16:33:09 +0100,
Steven Price <steven.price@arm.com> wrote:
> 
> On 21/05/2026 13:40, Marc Zyngier wrote:

I found that the PDF spec was less susceptible to creative nonsense,
and people can download it for future reference, whereas ARM has
happily *deleted* specs from the website over time (try to find PSCI
0.1, for example...).

[...]

> >> +struct realm_params {
> >> +	union { /* 0x0 */

Indeed, but it is (SZ_4K - SZ_256 * 3). And a lot of these structures
seem to be designed to form a 4kB blob. I'm sure we can make use of
that information (BUILD_BUG_ON?).

> 
> The RMM deals with this with macro magic:

I think this is just as horrible, but at least it seems to take the
boundaries of the structure into account.

>
> I'm happy to hear other suggestions on how to encode this neatly.

Honestly, I wouldn't mind having the structures described in a more
abstract way and then pre-processed to generate the include files. If
the architectural MRS wasn't so huge, I would have added it to the
kernel and used that directly for KVM.

>
> > I haven't checked the details of the encodings (life is too short),

I'm slightly baffled that even the RMM is written this way. Given the
formalism used in the RMM spec, I was expecting that you'd have a
bunch of JSON at hand and able to generate any output from that. Doing
this stuff by hand is both incredibly dull work *and* extremely error
prone.

Thanks,

	M.

---

## [91] Marc Zyngier — 2026-05-22
*Subject: Re: [PATCH v14 09/44] arm64: RMI: Provide functions to delegate/undelegate ranges of memory*

On Thu, 21 May 2026 17:01:37 +0100,
Suzuki K Poulose <suzuki.poulose@arm.com> wrote:
> 
> On 21/05/2026 14:59, Marc Zyngier wrote:

News flash, I can't read. Ignore me.

	M.

---

## [92] Gavin Shan — 2026-05-25
*Subject: Re: [PATCH v14 06/44] arm64: RMI: Check for RMI support at init*

Hi Steve,

On 5/22/26 1:49 AM, Steven Price wrote:
> On 21/05/2026 01:39, Gavin Shan wrote:
>> On 5/13/26 11:17 PM, Steven Price wrote:

I think the return value would be consistent to the value of 'arm64_rmi_is_available'.
'arm64_rmi_is_available' is true when zero is returned, otherwise, 'arm64_rmi_is_available'
is false.

With the consistency between the return value and 'arm64_rmi_is_available', users are
able to know the value of 'arm64_rmi_is_available' through kernel parameter 'initcall_debug'.
With the kernel parameter, the initcalls including arm64_init_rmi() are traced and its
return value is outputted in the traced messages, seeing do_trace_initcall_start().

> Thanks,
> Steve

Thanks,
Gavin

---

## [93] Wei-Lin Chang — 2026-05-26
*Subject: Re: [PATCH v14 13/44] arm64: RMI: Define the user ABI*

On Wed, May 13, 2026 at 02:17:21PM +0100, Steven Price wrote:
> There is one CAP which identified the presence of CCA, and one ioctl.
> The ioctl is used to populate memory during creation of the realm as

Nit:
I believe spelling out the CAP and ioctl names can improve the commit
message. Also "memory conversion" is a little vague, maybe

... CCA does not support shared <-> private memory conversion where ...

would make this clearer?

Thanks,
Wei-Lin Chang

> 
> Signed-off-by: Steven Price <steven.price@arm.com>

---

## [94] Wei-Lin Chang — 2026-05-26
*Subject: Re: [PATCH v14 17/44] arm64: RMI: RTT tear down*

Hi,

On Wed, May 13, 2026 at 02:17:25PM +0100, Steven Price wrote:
> The RMM owns the stage 2 page tables for a realm, and KVM must request
> that the RMM creates/destroys entries as necessary. The physical pages

Is this included by accident?

>  
>  	write_lock(&kvm->mmu_lock);

[...]

Thanks,
Wei-Lin Chang

---

## [95] Wei-Lin Chang — 2026-05-26
*Subject: Re: [PATCH v14 17/44] arm64: RMI: RTT tear down*

Hi,

On Wed, May 13, 2026 at 02:17:25PM +0100, Steven Price wrote:
> The RMM owns the stage 2 page tables for a realm, and KVM must request
> that the RMM creates/destroys entries as necessary. The physical pages

Looks like out_rtt can be simplified out.

[...]

Thanks,
Wei-Lin Chang

---

## [96] Wei-Lin Chang — 2026-05-26
*Subject: Re: [PATCH v14 19/44] arm64: RMI: Allocate/free RECs to match vCPUs*

Hi,

On Wed, May 13, 2026 at 02:17:27PM +0100, Steven Price wrote:
> The RMM maintains a data structure known as the Realm Execution Context
> (or REC). It is similar to struct kvm_vcpu and tracks the state of the

Should this be cast to (struct rec_run *) ?

> +	rec->sro = kmalloc_obj(*rec->sro);
> +	if (!params || !rec->rec_page || !rec->run || !rec->sro) {

[...]

Thanks,
Wei-Lin Chang

---

## [97] Wei-Lin Chang — 2026-05-26
*Subject: Re: [PATCH v14 28/44] arm64: RMI: Create the realm descriptor*

Hi,

On Wed, May 13, 2026 at 02:17:36PM +0100, Steven Price wrote:
> Creating a realm involves first creating a realm descriptor (RD). This
> involves passing the configuration information to the RMM. Do this as

I think ret can be simplified out.

Thanks,
Wei-Lin Chang

>  
>  static int set_ripas_of_protected_regions(struct kvm *kvm)

---

## [98] Wei-Lin Chang — 2026-05-27
*Subject: Re: [PATCH v14 23/44] arm64: RMI: Handle RMI_EXIT_RIPAS_CHANGE*

Hi,

On Wed, May 13, 2026 at 02:17:31PM +0100, Steven Price wrote:
> The guest can request that a region of it's protected address space is
> switched between RIPAS_RAM and RIPAS_EMPTY (and back) using

Do you think it's better if we use enum kvm_gfn_range_filter for this?
Pass KVM_FILTER_{PRIVATE, SHARED} to indicate what to unmap. This way we
don't have the think about booleans. kvm_realm_unmap_range() in patch 23
will have to change too though.

>   *
>   * Clear a range of stage-2 mappings, lowering the various ref-counts.  Must

[...]

Thanks,
Wei-Lin Chang

---

## [99] Marc Zyngier — 2026-05-27
*Subject: Re: [PATCH v14 13/44] arm64: RMI: Define the user ABI*

On Wed, 13 May 2026 14:17:21 +0100,
Steven Price <steven.price@arm.com> wrote:
> 
> There is one CAP which identified the presence of CCA, and one ioctl.

$SUBJECT looks wrong. This is a KVM change, not an RMI change.

>
> diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst

Where is that measurement stored? And retrieved? At least a pointer to
that would help.

> +
>  .. _kvm_run:

Thanks,

	M.

---

## [100] Gavin Shan — 2026-05-28
*Subject: Re: [PATCH v14 20/44] arm64: RMI: Support for the VGIC in realms*

Hi Steve,

On 5/13/26 11:17 PM, Steven Price wrote:
> The RMM provides emulation of a VGIC to the realm guest. With RMM v2.0
> the registers are passed in the system registers so this works similar

For a REC, kvm_vcpu_{load, put}_debug() becomes unbalanced in kvm_arch_vcpu_{load, put}().
kvm_vcpu_load_debug() is called in kvm_arch_vcpu_load(), but kvm_vcpu_put_debug() won't
be called in kvm_arch_vcpu_put() after this whole series is applied.

>   	kvm_vcpu_put_debug(vcpu);
>   	kvm_arch_vcpu_put_fp(vcpu);

Thanks,
Gavin

---

## [101] Gavin Shan — 2026-05-28
*Subject: Re: [PATCH v14 21/44] KVM: arm64: Support timers in realm RECs*

Hi Steve,

On 5/13/26 11:17 PM, Steven Price wrote:
> The RMM keeps track of the timer while the realm REC is running, but on
> exit to the normal world KVM is responsible for handling the timers.

s/!kvm_is_realm(vcpu->kvm)/!vcpu_is_rec(vcpu)

> @@ -1110,7 +1125,7 @@ void kvm_timer_vcpu_init(struct kvm_vcpu *vcpu)
>   		timer_context_init(vcpu, i);

Same as above.

> @@ -1611,6 +1626,13 @@ int kvm_timer_enable(struct kvm_vcpu *vcpu)
>   		return -EINVAL;

Thanks,
Gavin

---

## [102] Gavin Shan — 2026-05-28
*Subject: Re: [PATCH v14 22/44] arm64: RMI: Handle realm enter/exit*

Hi Steve,

On 5/13/26 11:17 PM, Steven Price wrote:
> Entering a realm is done using a SMC call to the RMM. On exit the
> exit-codes need to be handled slightly differently to the normal KVM

The condition could be posssibly imprecise because ARM_EXCEPTION_CODE(ret)
can be ARM_EXCEPTION_IRQ even for a REC. So the precise condition would be:

		if ((!vcpu_is_rec(vcpu) && ARM_EXCEPTION_CODE(ret) == ARM_EXCEPTION_IRQ) ||
		    (vcpu_is_rec(vcpu) && vcpu->arch.rec.run->exit.exit_reason == RMI_EXIT_IRQ)) {

> @@ -1436,8 +1444,13 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
>   

s/rec->run->exit.esr/kvm_vcpu_get_esr(vcpu), rec->run->exit.esr has been
copied to the storage space pointed by kvm_vcpu_get_esr() in its caller.

> +static int rec_exit_sync_dabt(struct kvm_vcpu *vcpu)
> +{

s/rec->run->exit.esr/kvm_vcpu_get_esr(vcpu)

> +static int rec_exit_sys_reg(struct kvm_vcpu *vcpu)
> +{

I doubt if the flag (REC_ENTER_FLAG_RIPAS_RESPONSE) will be handed over to RMM
since the negative return value forces we're exiting to VMM like QEMU where
how this problematic case can be handled is TBD.

> +
> +	/* Exit to VMM, the actual RIPAS change is done on next entry */

Thanks,
Gavin

---

## [103] Gavin Shan — 2026-05-28
*Subject: Re: [PATCH v14 24/44] KVM: arm64: Handle realm MMIO emulation*

Hi Steve,

On 5/13/26 11:17 PM, Steven Price wrote:
> MMIO emulation for a realm cannot be done directly with the VM's
> registers as they are protected from the host. However, for emulatable

{ } is needed here.

>   	return kvm_handle_guest_abort(vcpu);
>   }

Thanks,
Gavin

---

## [104] Gavin Shan — 2026-05-28
*Subject: Re: [PATCH v14 26/44] arm64: RMI: Allow populating initial contents*

Hi Steve,

On 5/13/26 11:17 PM, Steven Price wrote:
> The VMM needs to populate the realm with some data before starting (e.g.
> a kernel and initrd). This is measured by the RMM and used as part of

s/return ret/return 0; The variable 'ret' can be dropped.

>   	default:
>   		return -EINVAL;

		KVM_BUG_ON(level >= KVM_PGTABLE_LAST_LEVEL, kvm);> +
> +		ret = realm_create_rtt_levels(realm, ipa, level,
> +					      KVM_PGTABLE_LAST_LEVEL, NULL);

	if (ret && WARN_ON(rmi_undelegate_page(dst_phys)) {
		/* Leak the page that fails to be undelegated */
		get_page(pfn_to_page(dst_pfn));
	}

> +	return ret;
> +}

There are more conditions missed here:

	args->size == 0, return 0;
	args->base + args->size < args->base, return -EINVAL;  // wrapped range

> +	ret = realm_ensure_created(kvm);
> +	if (ret)

pages_populaged is 'unsigned long', this function returns a 'int' value.

> +
> +	args->size -= pages_populated << PAGE_SHIFT;

Thanks,
Gavin

---

## [105] Gavin Shan — 2026-05-28
*Subject: Re: [PATCH v14 28/44] arm64: RMI: Create the realm descriptor*

Hi Steve,

On 5/13/26 11:17 PM, Steven Price wrote:
> Creating a realm involves first creating a realm descriptor (RD). This
> involves passing the configuration information to the RMM. Do this as

In the latest RMM implementation (topics/rmm-v2.0-poc_2), rmi_delegate_range() works
with the granularity of granule (4KB) and it can fail on any granule. For example,
we have 16x granule as the root RTT and rmi_delegate_range() fails on the first
granule, we're going to undelegate all these 16x granules, which were never delegated
to RMM. It eventually leads to error and memory leakage.

For this, rmi_delegate_range() could be improved to return the number of granules that
have been delegated. The return value can be used by the caller to handle the erroneous
case by passing the correct range to rmi_undelegate_page().

> +	if (WARN_ON(rmi_undelegate_page(rd_phys))) {
> +		/* Leak the page if it isn't returned */

Thanks,
Gavin

---

## [106] Gavin Shan — 2026-05-28
*Subject: Re: [PATCH v14 32/44] KVM: arm64: Handle Realm PSCI requests*

Hi Steve,

On 5/13/26 11:17 PM, Steven Price wrote:
> The RMM needs to be informed of the target REC when a PSCI call is made
> with an MPIDR argument.

This change isn't supposed to be part of this patch :-)

>   	/*
>   	 * Make sure the reset request is observed if the RUNNABLE mp_state is

		return -ENXIO;

> +
> +	return 0;

Thanks,
Gavin

---

## [107] Marc Zyngier — 2026-05-28
*Subject: Re: [PATCH v14 14/44] arm64: RMI: Basic infrastructure for creating a realm.*

On Wed, 13 May 2026 14:17:22 +0100,
Steven Price <steven.price@arm.com> wrote:
> 
> Introduce the skeleton functions for creating and destroying a realm.

Again, $SUBJECT doesn't reflect that this is purely a KVM patch.

> 
> Signed-off-by: Steven Price <steven.price@arm.com>

What is the ABI status of this state? Is it purely internal to KVM? Or
is it something that the RMM actively tracks?

> +
>  /**

Why is this void? Doesn't it have a proper type?

> +	struct realm_params *params;
> +	unsigned int ia_bits;

Consider reordering this structure to avoid holes.

>  };
>  

The use of 'realm' is confusing. This is not a per-realm property, but
something global. I'd rather reserve the term 'realm' for CCA VMs (cue
the two prototypes below).

> +
> +int kvm_init_realm(struct kvm *kvm);

Why moving this init?

>  	err = KVM_PGT_FN(kvm_pgtable_stage2_init)(pgt, mmu, &kvm_s2_mm_ops);
>  	if (err)

Why can't you make kvm_stage2_destroy() do the right thing? Surely the
PTs have to be reclaimed one way or another.

>  		kfree(pgt);
>  	}

This really needs documentation: what happens at each stage? What
memory is reclaimed when?

But even more importantly, why is this built in a completely parallel
way, potentially deviating from the existing KVM S2 management?

Thanks,

	M.

---

## [108] Suzuki K Poulose — 2026-06-02
*Subject: Re: [PATCH v14 13/44] arm64: RMI: Define the user ABI*

Hi Marc

On 27/05/2026 16:21, Marc Zyngier wrote:
> On Wed, 13 May 2026 14:17:21 +0100,
> Steven Price <steven.price@arm.com> wrote:

The measurement is stored by the RMM and is made available to the Guests
via RSI interface (RSI_ATTEST_TOKEN_{INIT,CONTINUE}) as part of the 
attestation report along with the Platform attestation. On Linux Guest,
this could be fetched using TSM report infrastructure. This could be 
added to the doc.


Suzuki



> 
>> +

---

## [109] Suzuki K Poulose — 2026-06-02
*Subject: Re: [PATCH v14 14/44] arm64: RMI: Basic infrastructure for creating a
 realm.*

Hi Marc

On 28/05/2026 08:10, Marc Zyngier wrote:
> On Wed, 13 May 2026 14:17:22 +0100,
> Steven Price <steven.price@arm.com> wrote:

The states are in line with what the RMM maintains for the Realm state,
(Section A2.2.5 Realm Lifecycle)
except for :

1. REALM_STATE_DYING is really a KVM internal state to indicate, we
are in the process of destroying the Realm and no further requests
needs to be serviced

2. We don't track the REALM_SYSTEM_OFF, REALM_ZOMBIE states separately
as we :
  a) Always TERMINATE the Realm, just before the DESTROY
  b) SYSTEM_OFF is naturally triggering the tear down path, leading to 
DYING.




> 
>> +

Not really. This is an object that RMM manages (Realm Descriptor)
in the Realm world. We use it as a parameter to address the Realm.


> 
>> +	struct realm_params *params;

Agreed. Perhaps, kvm_rmm_ipa_limit() ?


> 
>> +

Because, we need to know the "kvm" instance for kvm_init_ipa_range to
detect the limit that applies to Realms.

> 
>>   	err = KVM_PGT_FN(kvm_pgtable_stage2_init)(pgt, mmu, &kvm_s2_mm_ops);

Actually yes, we could make it work. We need to skip walking the page
table for Realms. We may be able to do the checks via 
pgt->mmu->arch->kvm and skip the walking for Realms. ( The S2 is 
unmapped and torn
down before the RD is destroyed in kvm_destroy_realm(). We can't
rely on the contents of the PGDs to be zero - e.g., with MEC.)



> 
>>   		kfree(pgt);

Agreed.

> 
> But even more importantly, why is this built in a completely parallel


RMM requires a Realm is not live at the time of REALM_DESTROY.
(See section A2.2.4 Realm Liveness).
i.e., All RECs are destroyed, Root RTTs wiped clean (no live mappings)
before the RD is destroyed. So, we need to make sure all of this is
done at Realm Destroy. Hence we delay the kvm_free_stage2_pgd() until
we destroy the RD.

Does that help? May be we could improve the comments around it.


Suzuki



 > Thanks,>
> 	M.
>

---

## [110] Steven Price — 2026-06-03
*Subject: Re: [PATCH v14 04/44] arm64: RMI: Add SMC definitions for calling the
 RMM*

On 22/05/2026 10:58, Marc Zyngier wrote:
> On Thu, 21 May 2026 16:33:09 +0100,
> Steven Price <steven.price@arm.com> wrote:

Sadly the nearest I found to a link directly to the PDF is:

https://documentation-service.arm.com/static/69cb945ac1586b7c59b1c00c

But I have 0 confidence that that link will work for long (if indeed it
even works for others now!). If you know of any way of getting a better
link out of the Arm website that I'm all ears!

> [...]
> 

Do you really think

 		u8 padding3[SZ_4K - SZ_256 * 3];

is better? I certainly don't. I'll give you (SZ_4K - 0x300) is tempting.
Although it then makes the BUILD_BUG_ON idea below somewhat pointless.

> And a lot of these structures> seem to be designed to form a 4kB blob.
I'm sure we can make use of
> that information (BUILD_BUG_ON?).

BUILD_BUG_ON requires being in a function. But static_assert() can be
used in the header by the struct definitions - I'll add that, thanks for
the suggestion.

>>
>> The RMM deals with this with macro magic:

I'll look into the possibility of generating the headers. While dull and
error prone I have found it is sometimes useful for forcing a review of
the spec itself. There have been a number of bugs I've found (and have
been corrected) in the spec while writing the header files - it's very
easy to skim read those parts of the document otherwise.

Writing the structures out in a "more abstract way" might be a good
idea, but I'm just a little wary of writing another tool which is only
used in this one spot. The RMM structures are somewhat unusual in being
so sparse.

Thanks,
Steve

> Thanks,
>

---

## [111] Steven Price — 2026-06-03
*Subject: Re: [PATCH v14 06/44] arm64: RMI: Check for RMI support at init*

On 25/05/2026 07:58, Gavin Shan wrote:
> Hi Steve,
> 

Fair enough, and actually refactoring this function to pass error codes
up the call stack I think does improve the look.

Thanks,
Steve

>> Thanks,
>> Steve

---

## [112] Steven Price — 2026-06-03
*Subject: Re: [PATCH v14 06/44] arm64: RMI: Check for RMI support at init*

On 21/05/2026 14:02, Marc Zyngier wrote:
> On Wed, 13 May 2026 14:17:14 +0100,
> Steven Price <steven.price@arm.com> wrote:

Good point - there's no requirement. Also the name isn't quite right - 
these should be named rmi_ as there is a different set for RSI.

>> +
>> +static int rmi_check_version(void)

Yes I'm expecting this to be called before KVM's initialisation. 
kvm_init_rmi() alls rmi_is_available() to check if CCA is supported and 
only enables the KVM side of things if that check passes. So if the 
initialisation was the other way round then Realm guests would be 
unsupported. I'll add a comment

/*
 * Note arm64_init_rmi() must be called before kvm_init_rmi() otherwise KVM
 * will not support realm guests. subsys_initcall() is called before
 * module_init() (used for KVM) so this is OK.
 */

Thanks,
Steve

---

## [113] Steven Price — 2026-06-03
*Subject: Re: [PATCH v14 07/44] arm64: RMI: Configure the RMM with the host's
 page size*

On 21/05/2026 14:30, Marc Zyngier wrote:
> On Wed, 13 May 2026 14:17:15 +0100,
> Steven Price <steven.price@arm.com> wrote:

Good spot. I have to admit I'm still getting the hang of these cleanup
handlers.

>> +
>> +	switch (PAGE_SIZE) {

No, but falling through is clearly wrong (and likely to trigger AI
review comments if nothing else) - BUILD_BUG() sounds like a good solution.

>> +		return -EINVAL;
>> +	}

Yes, as Suzuki answered - it never leaves the NS PAS. The RMM just reads it.

Thanks,
Steve

>> +
>> +	ret = rmi_rmm_activate();

---

## [114] Steven Price — 2026-06-03
*Subject: Re: [PATCH v14 08/44] arm64: RMI: Ensure that the RMM has GPT entries
 for memory*

On 19/05/2026 06:55, Aneesh Kumar K.V wrote:
>> +
>> +bool rmi_is_available(void)

Sure, will do.

Thanks,
Steve

---

## [115] Steven Price — 2026-06-03
*Subject: Re: [PATCH v14 08/44] arm64: RMI: Ensure that the RMM has GPT entries
 for memory*

On 21/05/2026 01:58, Gavin Shan wrote:
> Hi Steven,
> 

Ah, good spot. In a previous version the tracking size was necessary 
when walking below. But the spec was updated to a range based API so 
this is no longer necessary.

>> +/*
>> + * Make sure the area is tracked by RMM at FINE granularity.

True - I think partly due to the long line I split this into a separate 
function. But I could do something like:

	unsigned long l0gpt_sz;

	l0gpt_sz = 1UL << (30 + FIELD_GET(RMI_FEATURE_REGISTER_1_L0GPTSZ,
					  rmi_feat_reg(1)));

which isn't too bad.

Thanks,
Steve

>> +static int rmi_create_gpts(phys_addr_t start, phys_addr_t end)
>> +{

---

## [116] Steven Price — 2026-06-03
*Subject: Re: [PATCH v14 08/44] arm64: RMI: Ensure that the RMM has GPT entries
 for memory*

On 21/05/2026 16:39, Suzuki K Poulose wrote:
> On 21/05/2026 14:47, Marc Zyngier wrote:
>> On Wed, 13 May 2026 14:17:16 +0100,

As Gavin pointed out we actually don't need this anymore because of the
move to a range based API.

It's also not quite that simple because for 4K PAGE_SIZED the RMM
doesn't support 2MB (which would be the level 2 size), instead jumping
to 1GB. And if we add a Kconfig option in the future then this could
change because of that.

For now I'll just delete this block since it's unused.

>>
>>> +

I'm not sure 1 message really counts as 'spam' - it provides the
information on why the RMI interface (and therefore realm guests) is
unavailable. The PA might help track down whether this physical region
was intended to be given to Linux.

> This could be triggered if the RMM doesn't have static carveout
> for tracking the DRAM granules. (state != RMI_TRACKING_FINE).

As Suzuki says - this case should be handled in the future - so it's a
limitation in the current implementation. So a WARN_ONCE is a bit strong
- it's not a "can never happen" situation - it's a "Linux doesn't
support this (yet)".

>>
>> If that's not expected, turn this into a WARN_ONCE().

The missing SRO support is why we're not donating memory - with that
missing the clean up is unnecessary as Suzuki says.

>>> +        }
>>> +        start += l0gpt_sz;

Yep, that was an oversight - we definitely will need to handle hotplug.

Thanks,
Steve

> Suzuki
>

---

## [117] Steven Price — 2026-06-04
*Subject: Re: [PATCH v14 09/44] arm64: RMI: Provide functions to
 delegate/undelegate ranges of memory*

On 21/05/2026 14:59, Marc Zyngier wrote:
> On Wed, 13 May 2026 14:17:17 +0100,
> Steven Price <steven.price@arm.com> wrote:

Ok, I'll admit that this is left over debugging - although this is a
condition that shouldn't happen.

Note that the while() condition prevents this from actually getting to
the RMM.

I'll drop the WARN_ON() since it's confusing.

Thanks,
Steve

> You also don't seem to be bothered with that on the delegation side...
>

---

## [118] Steven Price — 2026-06-04
*Subject: Re: [PATCH v14 10/44] arm64: RMI: Add support for SRO*

On 19/05/2026 07:02, Aneesh Kumar K.V wrote:
> Steven Price <steven.price@arm.com> writes:
> 

I'm split on this. The kernel makes use of "(unsigned) long" for a
register sized value in quite a few places. Not least in struct
arm_smccc_1_2_regs which is ultimately where most of the values are read
from or written to.

I'm not a great fan of the kernel's approach to using long like this -
there's a good argument that uintptr_t is more correct. Equally when
we're in arch code for a 64 bit architecture (i.e. "arm64") then we know
the size is u64.

The disadvantage here is that if I use u64 then there's a bunch of
implicit conversions going on between unsigned long and u64 - which
might come back to bite if anything changes. Hence my current view that
"unsigned long" is the best option here in the kernel.

Anyone else have any view on the best type here?

Thanks,
Steve

---

## [119] Steven Price — 2026-06-04
*Subject: Re: [PATCH v14 10/44] arm64: RMI: Add support for SRO*

On 21/05/2026 05:38, Gavin Shan wrote:
> Hi Steven,
> 

Generally it's best to let the compiler make the decision. A small
static function like this is highly likely to be inlined by the compiler
already.

The exception of course is when the function is in a header and then
it's necessary to use "static inline".

> {P4D, PUD, PMD}_SIZE can be equal if there> are
> no P4D and PUD, depending on CONFIG_PGTABLE_LEVELS. In this case, can the

Technically yes. I think I can actually rewrite this more simply as:

static unsigned long donate_req_to_size(unsigned long donatereq)
{
	unsigned long unit_size = RMI_DONATE_SIZE(donatereq);

	return BIT(ARM64_HW_PGTABLE_LEVEL_SHIFT(3 - unit_size));
}

which neatly sidesteps the CONFIG_PGTABLE_LEVELS problem too.

>> +static void rmi_smccc_invoke(struct arm_smccc_1_2_regs *regs_in,
>> +                 struct arm_smccc_1_2_regs *regs_out)

This is an area where to be honest I'm really not sure what to do.
Technically the RMM is allowed to ask for a contiguous range of 512GB
pages (on a 4K system - larger with larger page sizes) - but clearly no
real OS is going to be able to provide anything like that.

In practise we don't expect the RMM to do anything so crazy. It's not
really clear to be whether even 2MB (PMD_SIZE) is needed. But the spec
is written to be generic.

So my current approach is to calculate the required size and pass it
into alloc_pages_exact(). For "stupidly large" values this will fail and
Linux just doesn't support an RMM which attempts this. If there is ever
a usecase which needs this then we'd need to find a different method of
providing the memory (most likely some form of carveout to avoid
fragmentation). But my view is we should wait for that usecase to be
identified first.

>> +    if (state == RMI_OP_MEM_DELEGATED) {
>> +        if (rmi_delegate_range(phys, size)) {

Good spot - ret should be initialised to 0.

Thanks,
Steve

>> +        case RMI_OP_MEM_REQ_DONATE:
>> +            ret = rmi_sro_donate(sro, sro_handle, regs.a2, &regs,

---

## [120] Steven Price — 2026-06-04
*Subject: Re: [PATCH v14 10/44] arm64: RMI: Add support for SRO*

On 21/05/2026 15:35, Marc Zyngier wrote:
> On Wed, 13 May 2026 14:17:18 +0100,
> Steven Price <steven.price@arm.com> wrote:

It doesn't work (as Gavin also pointed out). There's an existing macro
to make this even cleaner:

return BIT(ARM64_HW_PGTABLE_LEVEL_SHIFT(3 - unit_size));

>> +	}
>> +	unreachable();

Happy to change to WARN_ON_ONCE(). I think we should keep a WARN of some
sort as this is causing Linux to leak pages - it's definitely something
the sysadmin would want to know about.

>> +		/* Undelegate failed: leak the page */
>> +		return -EBUSY;

I'm not sure quite what you are suggesting. I already have a
rmi_sro_ensure_capacity() helper. By this point we know there's space.

>> +out:
>> +	regs.a2 = virt_to_phys(&sro->addr_list[sro->addr_count]);

That's a good point. SRO is a bit tricky because I wanted the actual SMC
call to be done in one place so we can handle all the RMI_INCOMPLETE
cases together. But I could certainly add some helpers to setup the
registers rather than assigning directly to regs.a<n>.

Thanks,
Steve

> 	M.
>> +	rmi_smccc_invoke(&regs, out_regs);

---

## [121] Steven Price — 2026-06-04
*Subject: Re: [PATCH v14 13/44] arm64: RMI: Define the user ABI*

On 26/05/2026 23:17, Wei-Lin Chang wrote:
> On Wed, May 13, 2026 at 02:17:21PM +0100, Steven Price wrote:
>> There is one CAP which identified the presence of CCA, and one ioctl.

Thanks for the suggestions - yes I agree that would make it clearer.

Thanks,
Steve

> Thanks,
> Wei-Lin Chang

---

## [122] Steven Price — 2026-06-04
*Subject: Re: [PATCH v14 13/44] arm64: RMI: Define the user ABI*

On 27/05/2026 16:21, Marc Zyngier wrote:
> On Wed, 13 May 2026 14:17:21 +0100,
> Steven Price <steven.price@arm.com> wrote:

Ah, true I guess "KVM: arm64: Define the user ABI for CCA" is more accurate.

>>
>> diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst

It's stored within the RMM and retrieved by the guest (using the RSI
interface). I'll update to:

`flags` can be set to `KVM_ARM_RMI_POPULATE_FLAGS_MEASURE` to request
that the populated data is hashed and added to the guest's Realm Initial
Measurement (RIM) stored by the RMM. This can then be retrieved by the
guest (using the RSI interface) to present to an attestation server.

Thanks,

Steve

>> +
>>  .. _kvm_run:

---

## [123] Steven Price — 2026-06-04
*Subject: Re: [PATCH v14 14/44] arm64: RMI: Basic infrastructure for creating a
 realm.*

On 02/06/2026 15:49, Suzuki K Poulose wrote:
> Hi Marc
> 

Indeed - "KVM: arm64: CCA" is a better prefix.

>>>
>>> Signed-off-by: Steven Price <steven.price@arm.com>

I'll add a comment:

+ * Mirrors the RMM's Realm lifecycle states where they are meaningful to KVM,
+ * with REALM_STATE_DYING being a KVM-internal state used to prevent further
+ * requests while teardown is in progress. KVM does not track REALM_SYSTEM_OFF
+ * or REALM_ZOMBIE separately as they naturally lead to teardown.

> 
> 

Sure

>>>   };
>>>     void kvm_init_rmi(void);

Sounds good to me.

> 
>>

Yes I'll move the check into kvm_stage2_destroy() instead with a comment
explaining what's going on.

>>
>>>           kfree(pgt);

I'll add a comment in kvm_destroy_realm().

Thanks,
Steve

> 
> Suzuki

---

## [124] Gavin Shan — 2026-06-05
*Subject: Re: [PATCH v14 29/44] arm64: RMI: Runtime faulting of memory*

Hi Steve,

On 5/13/26 11:17 PM, Steven Price wrote:
> At runtime if the realm guest accesses memory which hasn't yet been
> mapped then KVM needs to either populate the region or fault the guest.

I'm a bit concerned with this. We don't have KVM_PGTABLE_PROT_W set in @prot
if the stage2 fault is raised due to memory read. With -EFAULT returned to VMM
(e.g. QEMU), the vCPU continuous execution is stopped and system won't be
working any more.

> +	ipa = ALIGN_DOWN(ipa, PAGE_SIZE);
> +	if (!kvm_realm_is_private_address(realm, ipa))

For the case kvm_is_realm(), need we adjust 's2fd->fault_ipa' for the sake of
huge pages. In kvm_s2_fault_map(), @gfn and @pfn may have been adjusted by
transparent_hugepage_adjust() to be aligned with huge page size. If the
adjustment happened in transparent_hugepage_adjust(), we need to align
s2fd->fault_ipa down to the huge page size either.


> @@ -2214,6 +2285,13 @@ int kvm_handle_guest_sea(struct kvm_vcpu *vcpu)
>   	return 0;

Thanks,
Gavin

---

## [125] Lorenzo Pieralisi — 2026-06-05
*Subject: Re: [PATCH v14 29/44] arm64: RMI: Runtime faulting of memory*

On Fri, Jun 05, 2026 at 04:23:15PM +1000, Gavin Shan wrote:

[...]

> > +static int realm_map_ipa(struct kvm *kvm, phys_addr_t ipa,
> > +			 kvm_pfn_t pfn, unsigned long map_size,

All of the above + some RMM changes are needed to get QEmu VMM going
with anon pages guest memory backing - currently testing various
configurations in the background.

Thanks,
Lorenzo

> > @@ -2214,6 +2285,13 @@ int kvm_handle_guest_sea(struct kvm_vcpu *vcpu)
> >   	return 0;

---

## [126] Gavin Shan — 2026-06-05
*Subject: Re: [PATCH v14 29/44] arm64: RMI: Runtime faulting of memory*

On 6/5/26 5:28 PM, Lorenzo Pieralisi wrote:
> On Fri, Jun 05, 2026 at 04:23:15PM +1000, Gavin Shan wrote:
> 

I tried to rebase Jean's latest QEMU series [1] to upstream QEMU, and found
that memory slots backed by THP are broken. With THP disabled on the host and
other fixes (mentioned in my prevous replies) applied on the top of this (v14)
series, I'm able to boot a realm guest with rebased QEMU series [2], plus more
fxies on the top.

[1] https://git.codelinaro.org/linaro/dcap/qemu.git  (branch: cca/latest)
[2] https://git.qemu.org/git/qemu.git                (branch: cca/gavin)

Lorenzo, You may be saying there is someone making QEMU to support ARM/CCA?
If so, I'm not sure if there is a QEMU repository for me to try?

Thanks,
Gavin

> Thanks,
> Lorenzo

---

## [127] Gavin Shan — 2026-06-05
*Subject: Re: [PATCH v14 29/44] arm64: RMI: Runtime faulting of memory*

Hi Steve,

On 5/13/26 11:17 PM, Steven Price wrote:
> At runtime if the realm guest accesses memory which hasn't yet been
> mapped then KVM needs to either populate the region or fault the guest.

[...]

> @@ -1604,27 +1641,52 @@ static int gmem_abort(const struct kvm_s2_fault_desc *s2fd)
>   	bool write_fault, exec_fault;

For a Realm, gmem_abort() is called by kvm_handle_guest_abort() only when
we're faulting in the private (protected) space.

     if (kvm_slot_has_gmem(memslot) && !shared_ipa_fault(vcpu->kvm, fault_ipa))
         ret = gmem_abort(&s2fd);
     else
         ret = user_mem_abort(&s2fd);

With the condition, this block of code can be simplied to handle conversion
(shared -> private) instead of both directions.

     /* Convert the shared address to the private adress for Realm */
     if (kvm_is_realm(vcpu->kvm) &&
         !kvm_mem_is_private(kvm, gpa >> PAGE_SHIFT)) {
         /*
          * KVM_EXIT_MEMORY_FAULT requires an return code of
          * -EFAULT, see the API documentation
          */
         kvm_prepare_memory_fault_exit(vcpu, gpa, PAGE_SIZE,
                                       kvm_is_write_fault(vcpu),
                                       false, true);
         return -EFAULT;
     }


[...]

> @@ -2396,7 +2475,7 @@ int kvm_handle_guest_abort(struct kvm_vcpu *vcpu)
>   				!write_fault &&
gmem_abort() is only called for faults in the protected (private) space.

Thanks,
Gavin

---

## [128] Lorenzo Pieralisi — 2026-06-05
*Subject: Re: [PATCH v14 29/44] arm64: RMI: Runtime faulting of memory*

On Fri, Jun 05, 2026 at 06:11:11PM +1000, Gavin Shan wrote:
> On 6/5/26 5:28 PM, Lorenzo Pieralisi wrote:
> > On Fri, Jun 05, 2026 at 04:23:15PM +1000, Gavin Shan wrote:

Mathieu and I are working on that yes and with Steven/Suzuki to fix the THP
issues you pointed out above.

> If so, I'm not sure if there is a QEMU repository for me to try?

We should be able to submit patches by end of June - we shall let you know
whether we can make something available earlier.

Thanks,
Lorenzo

> 
> Thanks,

---

## [129] Steven Price — 2026-06-05
*Subject: Re: [PATCH v14 17/44] arm64: RMI: RTT tear down*

On 26/05/2026 23:27, Wei-Lin Chang wrote:
> Hi,
> 

Thanks for spotting that. Yes that change shouldn't have sneaked in
here. The original code before this series had the redundant assignment
to NULL. But it's unrelated to this patch so I'll drop the change.

Thanks,
Steve

> 
>>

---

## [130] Steven Price — 2026-06-05
*Subject: Re: [PATCH v14 17/44] arm64: RMI: RTT tear down*

On 26/05/2026 23:32, Wei-Lin Chang wrote:
> Hi,
> 

The issue here is there's a type conversion going on. rmi_rtt_destroy()
takes an "unsigned long *" to match the general approach of using
"unsigned long" for the inputs/outputs of SMCCC calls. But rtt_granule
is a "phys_addr_t". While we know these are (currently) the same size,
they are not the same type according to the compiler - phys_addr_t is
"long long unsigned int".

Thanks,
Steve

> [...]
>

---

## [131] Steven Price — 2026-06-05
*Subject: Re: [PATCH v14 19/44] arm64: RMI: Allocate/free RECs to match vCPUs*

On 26/05/2026 23:39, Wei-Lin Chang wrote:
> Hi,
> 

Yes it probably should - I'll update. Although IMHO get_zeroed_page()
should really return void * - but I know that would be a contentious change.

Thanks,
Steve

>> +	rec->sro = kmalloc_obj(*rec->sro);
>> +	if (!params || !rec->rec_page || !rec->run || !rec->sro) {

---

## [132] Steven Price — 2026-06-05
*Subject: Re: [PATCH v14 20/44] arm64: RMI: Support for the VGIC in realms*

On 28/05/2026 05:07, Gavin Shan wrote:
> Hi Steve,
> 

Good catch. Yes that's not quite right.

Thanks,
Steve

>>       kvm_vcpu_put_debug(vcpu);
>>       kvm_arch_vcpu_put_fp(vcpu);

---

## [133] Steven Price — 2026-06-05
*Subject: Re: [PATCH v14 22/44] arm64: RMI: Handle realm enter/exit*

On 28/05/2026 05:38, Gavin Shan wrote:
> Hi Steve,
> 

Good point - I guess this wouldn't have shown up in testing because
there's no harm (other than performance) in the ISB.

>> @@ -1436,8 +1444,13 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
>>             trace_kvm_exit(ret, kvm_vcpu_trap_get_class(vcpu),

Ack

>> +static int rec_exit_sync_dabt(struct kvm_vcpu *vcpu)
>> +{

Ack

>> +static int rec_exit_sys_reg(struct kvm_vcpu *vcpu)
>> +{

It's perhaps a bit non-obvious but enter.flags is cleared on the exit.
So even if we return to the VMM the flags will be kept for the next entry.

I agree it is somewhat TBD exactly how this case should be handled -
there's a bunch of "VM did something stupid" cases like this that are a
bit problematic.

Thanks,
Steve

>> +
>> +    /* Exit to VMM, the actual RIPAS change is done on next entry */

---

## [134] Steven Price — 2026-06-05
*Subject: Re: [PATCH v14 23/44] arm64: RMI: Handle RMI_EXIT_RIPAS_CHANGE*

On 19/05/2026 10:40, Aneesh Kumar K.V wrote:
> Steven Price <steven.price@arm.com> writes:
> 

Because we treat the private and shared spaces are aliasing we don't
really support a "private-only" invalidation. So the shared space will
be invalidated as well. Something has gone wrong if we've ended up with
the 'same' IPA being used in both the private and shared spaces.

Private has to be treated slightly specially because removing a private
mapping is observable by the guest (the page can't be reinserted without
the guest agreeing and the contents being wiped). For shared mappings
the page can simply be refaulted.

That said, I'll look into Wei-Lin's suggestion to use
kvm_gfn_range_filter which would allow all three combinations of
private-only, shared-only and private+shared.

Thanks,
Steve

---

## [135] Steven Price — 2026-06-08
*Subject: Re: [PATCH v14 24/44] KVM: arm64: Handle realm MMIO emulation*

On 28/05/2026 06:03, Gavin Shan wrote:
> Hi Steve,
> 

Indeed - I'm surprised checkpatch didn't manage to flag that. I'll fix.

Thanks,
Steve

>>       return kvm_handle_guest_abort(vcpu);
>>   }

---

## [136] Suzuki K Poulose — 2026-06-08
*Subject: Re: [PATCH v14 29/44] arm64: RMI: Runtime faulting of memory*

On 05/06/2026 07:23, Gavin Shan wrote:
> Hi Steve,
> 

Could we give the RMM a chance to make use of the Block mappings by 
creating the Missing RTTs to the level that may work for the current
range_desc ? i.e., if the range_desc is a 2M block size, we could create
tables upto L2 in the first go and if the RMM still needs RTT, we could
go further down to the KVM_PGTABLE_LAST_LEVEL. I understand this is
kind of an optimisation, so may be we could defer it. (Same applies for
the non_secure map below).


>> +            if (ret)
>> +                goto err_undelegate;

^^ Same as above.

Suzuki


>> +                              memcache);
>> +            if (ret)

---

## [137] Steven Price — 2026-06-08
*Subject: Re: [PATCH v14 26/44] arm64: RMI: Allow populating initial contents*

On 28/05/2026 06:30, Gavin Shan wrote:
> Hi Steve,
> 

kvm_arm_rmi_populate() may return an error though. E.g. if the
"reserved" field is set then it's kvm_arm_rmi_populate() that detects
that and returns -EINVAL.

>>       default:
>>           return -EINVAL;

Ack.

>> +        ret = realm_create_rtt_levels(realm, ipa, level,
>> +                          KVM_PGTABLE_LAST_LEVEL, NULL);

Ack

>> +    return ret;
>> +}

Good catch. args->size == 0 can trigger a WARN_ON currently. I'll put
the "return 0" after the realm_ensure_created() call so the behaviour
matches.

I don't think the wrapped range is quite such a problem - but detecting
it and rejecting it early seems like a good idea.

>> +    ret = realm_ensure_created(kvm);
>> +    if (ret)

pages_populated is *signed* long. This is handling an error code - so if
it's negative we expect the error code to be between -1 and -MAX_ERRNO
which should easily fit within the 'int' return.

For positive values we continue below (encoding the potentially larger
number in the args outputs) and return 0.

Thanks,
Steve

>> +
>> +    args->size -= pages_populated << PAGE_SHIFT;

---

## [138] Suzuki K Poulose — 2026-06-08
*Subject: Re: [PATCH v14 26/44] arm64: RMI: Allow populating initial contents*

On 08/06/2026 10:36, Steven Price wrote:
> On 28/05/2026 06:30, Gavin Shan wrote:
>> Hi Steve,

...

>>> diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
>>> index a89873a5eb77..209087bcf399 100644

Thinking more about this, I guess a buggy VMM can trigger this
by populating twice ? (level == KVM_PGTABLE_LAST_LEVEL). So, we should
return the error back, than warning here and suppressing the error ?


Suzuki

---

## [139] Steven Price — 2026-06-08
*Subject: Re: [PATCH v14 28/44] arm64: RMI: Create the realm descriptor*

On 26/05/2026 23:47, Wei-Lin Chang wrote:
> Hi,
> 
Indeed.

Thanks,
Steve

> Thanks,
> Wei-Lin Chang

---

## [140] Steven Price — 2026-06-08
*Subject: Re: [PATCH v14 28/44] arm64: RMI: Create the realm descriptor*

On 28/05/2026 06:51, Gavin Shan wrote:
> Hi Steve,
> 

Well spotted - yes the current situation where the entire region is
leaked if the delegate only partially completes is less than ideal! I'll
add a third argument to rmi_delegate_range() to return the top of the
region that was successfully delegated. The caller can then attempt an
undelegate on just the range which was delegated.

Thanks,
Steve

>> +    if (WARN_ON(rmi_undelegate_page(rd_phys))) {
>> +        /* Leak the page if it isn't returned */

---

## [141] Steven Price — 2026-06-08
*Subject: Re: [PATCH v14 29/44] arm64: RMI: Runtime faulting of memory*

On 08/06/2026 10:30, Suzuki K Poulose wrote:
> On 05/06/2026 07:23, Gavin Shan wrote:
>> Hi Steve,

[...]

>>> diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
>>> index cae29fd3353c..761b38a4071c 100644

A simple change would be just to create one level at a time like this:

diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index b79b96f7dffb..3f3ade1d3895 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -767,15 +767,15 @@ static int realm_map_protected(struct kvm *kvm,
 			/* Create missing RTTs and retry */
 			int level = RMI_RETURN_INDEX(ret);
 
-			WARN_ON(level == KVM_PGTABLE_LAST_LEVEL);
+			if (WARN_ON(level >= KVM_PGTABLE_LAST_LEVEL))
+				goto err_undelegate;
 			ret = realm_create_rtt_levels(realm, ipa, level,
-						      KVM_PGTABLE_LAST_LEVEL,
+						      level + 1,
 						      memcache);
 			if (ret)
 				goto err_undelegate;
 
-			ret = rmi_rtt_data_map(rd, ipa, ipa_top, flags,
-					       range_desc, &out_top);
+			continue;
 		}
 
 		if (WARN_ON(ret))

Thanks,
Steve

---

## [142] Steven Price — 2026-06-08
*Subject: Re: [PATCH v14 29/44] arm64: RMI: Runtime faulting of memory*

On 05/06/2026 12:20, Gavin Shan wrote:
> Hi Steve,
> 

You're absolutely correct - that's a nice simplification!

Thanks,
Steve

---

## [143] Steven Price — 2026-06-08
*Subject: Re: [PATCH v14 32/44] KVM: arm64: Handle Realm PSCI requests*

On 28/05/2026 07:55, Gavin Shan wrote:
> Hi Steve,
> 

Whoops - indeed it isn't!

>>       /*
>>        * Make sure the reset request is observed if the RUNNABLE

Ack, although as the comment says this should be going away.

Thanks,
Steve

>> +
>> +    return 0;

---

## [144] Suzuki K Poulose — 2026-06-08
*Subject: Re: [PATCH v14 29/44] arm64: RMI: Runtime faulting of memory*

On 08/06/2026 11:56, Steven Price wrote:
> On 08/06/2026 10:30, Suzuki K Poulose wrote:
>> On 05/06/2026 07:23, Gavin Shan wrote:

That looks good to me.

Cheers
Suzuki


>   
>   		if (WARN_ON(ret))

---

## [145] Steven Price — 2026-06-08
*Subject: Re: [PATCH v14 26/44] arm64: RMI: Allow populating initial contents*

On 08/06/2026 10:41, Suzuki K Poulose wrote:
> On 08/06/2026 10:36, Steven Price wrote:
>> On 28/05/2026 06:30, Gavin Shan wrote:

Populating twice causes rmi_delegate_page() to be run twice on the same
page and the second one will then fail. So I don't think this is
possible (please correct me if I've missed something!)

Thanks,
Steve

---

## [146] Dan Williams (nvidia) — 2026-06-12
*Subject: Re: [PATCH v14 10/44] arm64: RMI: Add support for SRO*

Steven Price wrote:
[..]
> > alloc_pages_exact() will fail if the requested size exceeds the maximal
> > allowed

Just some comparison comments as I am also going through the TDX patches
which enable "Extension SEAMCALLs". These new SEAMCALLs are similar to
the SRO mechanism [1].

TDX asks for an upfront delegation of memory at init time using
alloc_contig_pages() that is never returned until entire module is
shutdown. alloc_contig_pages() is not subject to the MAX_ORDER limit,
but not sure that alloc_contig_pages() is suitable for small+dynamic
runtime memory add / release that SRO potentially wants to do?

Does SRO always balance the size of RMI_OP_MEM_REQ_DONATE with
RMI_OP_MEM_REQ_RECLAIM, or might some donate requests be a one way
donation like TDX? Just poking to see if there is a path to preallocate
a pool vs the fine grained per-operation alloc/free.

[1]: http://lore.kernel.org/20260522034128.3144354-3-yilun.xu@linux.intel.com

---

## [147] Steven Price — 2026-06-15
*Subject: Re: [PATCH v14 10/44] arm64: RMI: Add support for SRO*

Hi Dan,

On 13/06/2026 00:07, Dan Williams (nvidia) wrote:
> Steven Price wrote:
> [..]

Looks like at least at the moment it's much more one-way than the SRO
mechanism - there's no reclaim mechanism (yet).

> TDX asks for an upfront delegation of memory at init time using
> alloc_contig_pages() that is never returned until entire module is

Yeah I'm not sure quite what is best. I expect the RMM to only request
contiguous memory for very small allocations to use as hardware page
tables. It's an issue I'm trying to work through that the specification
doesn't provide any guidance for what sort of allocations the host
should expect to provide.

> Does SRO always balance the size of RMI_OP_MEM_REQ_DONATE with
> RMI_OP_MEM_REQ_RECLAIM, or might some donate requests be a one way

The spec is unfortunately not prescriptive on this point. For an
operation which eventually fails, the expectation is that the RMM will
return all the memory that was provided (and exactly that memory). But
the specification doesn't actually require that.

The problem is that there are situations where a racing operation on
another CPU could trigger this to not happen. For example, a new page
table needs to be allocated to complete a map operation, but then a
racing operation on another CPU makes use of this page table (e.g due to
a map at a different address), the memory for the page table cannot be
returned even if the operation doesn't complete because it's in use from
the racing operation.

I don't believe the current RMM design will actually do this - but it's
not something we actually want to prevent in the spec.

Equally the expectation is that all the donated memory for a guest will
be returned when the guest is destroyed. But we don't have anything in
the spec to enforce this.

I don't particularly expect a pool to be that useful for the expected
memory allocation patterns as I expect SRO donations to be long lived.
We don't (yet at least) have a concept of donating memory just for
"scratch" memory during an operation. Although the SRO mechanism doesn't
rule that out.

Thanks,
Steve

---

## [148] Gavin Shan — 2026-06-25
*Subject: Re: [PATCH v14 29/44] arm64: RMI: Runtime faulting of memory*

On 6/6/26 12:35 AM, Lorenzo Pieralisi wrote:
> On Fri, Jun 05, 2026 at 06:11:11PM +1000, Gavin Shan wrote:
>> On 6/5/26 5:28 PM, Lorenzo Pieralisi wrote:

Not sure if there are other known issues in this series. It seems the stage2
page fault handling on the shared space isn't working well. In my test, the
vring (struct vring_desc) of virtio-net-pci is updated by the guest, and the
data isn't seen by QEMU, I'm suspecting if the host-page-frame-number is properly
resolved in the s2 page fault handler for shared (unprotected) space.

- I rebased Jean's latest qemu branch to the upstream qemu;

- On the host, which is emulated by qemu/tcg, the THP (transparent huge page) is
   disabled.

- On the guest, I can see the virtio vring (struct vring_desc) is updated. The
   S1 page-table entry looks correct because the corresponding physical address
   0x10046880000 is a sane shared (unprotected) space address.

   [   52.094143] software IO TLB: Memory encryption is active and system is using DMA bounce buffers
   [   52.289746] virtqueue_add_desc_split: desc[0]@0xffff000006880000, [00000100b983f000  00000640  0002  0001]
   [   52.432150] PTE 0x00e8010046880707 at address 0xffff000006880000

- On the host, the s2 page-table-entry is unmapped due to attribute transition (private -> shared).
   A subsequent S2 page fault is raised against the adress and the s2 page-table-entry is built.

   [  109.259077] ====> realm_unmap_shared_range: tracked_unprot_addr=0x10046880000
   [  109.260249] realm_unmap_shared_range: unmapped shared range at 0x10046880000
   [  109.317786] realm_unmap_shared_range: unmapped shared range at 0x10046880000
   [  109.629939] ====> kvm_handle_guest_abort: fault_ipa=0x10046880000, esr=0x92000007
   [  109.630245] realm_map_non_secure: ipa=0x10046880000, pfn=0xb8b59, size=0x1000, prot=0xf
   [  109.630331] realm_map_non_secure: ipa=0x10046880000, ipa_top=0x10046881000, flags=0x1e0001, range_desc=0xb8b59004

- On QEMU, the updated vring (struct vring_desc) at GPA 0x46880000 isn't seen. All the
   data in that adress are zeros.

   ====> virtqueue_split_pop: vdev=<virtio-net>, sz=0x38, queue_index=0x0, vq->vring.num=0x100
   virtqueue_split_pop: last_avail_idx=0x0, head=0x0
   address_space_read_cached_slow: cache@0xffff1c036440, addr=0x0, buf=0xffffeee34880, len=0x10
   address_space_read_cached_slow: cache: ptr=0x0, xlat=0x10046880000, len=0x1000, mrs=<realm-dma-region>, is_write=no
   address_space_read_cached_slow: translated to mr=<mach-virt.ram>, mr_addr=0x6880000, l=0x10
   flatview_read_continue_step: mr=<mach-virt.ram>, host=0xffff23e00000, mr_addr=0x6880000, ram_ptr=0xffff2a680000
   virtqueue_split_pop: desc: 0000000000000000 - 00000000 - 00000000 - 00000000
   qemu-system-aarch64: virtio: zero sized buffers are not allowed


Thanks,
Gavin

---

## [149] Suzuki K Poulose — 2026-06-25
*Subject: Re: [PATCH v14 29/44] arm64: RMI: Runtime faulting of memory*

On 25/06/2026 14:53, Gavin Shan wrote:
> On 6/6/26 12:35 AM, Lorenzo Pieralisi wrote:
>> On Fri, Jun 05, 2026 at 06:11:11PM +1000, Gavin Shan wrote:

Are you able to correlate the order of the transitions and the Guest
access with RMM log ? We haven't seen this from our end. We are aware
of permission fault issues with Unprotected IPA when backing the memslot
with MAP_PRIVATE areas. But this looks different.

Lorenzo, have you run into this ?

Suzuki


> 
> - On QEMU, the updated vring (struct vring_desc) at GPA 0x46880000 isn't

---

## [150] Suzuki K Poulose — 2026-06-25
*Subject: Re: [PATCH v14 26/44] arm64: RMI: Allow populating initial contents*

On 08/06/2026 14:53, Steven Price wrote:
> On 08/06/2026 10:41, Suzuki K Poulose wrote:
>> On 08/06/2026 10:36, Steven Price wrote:

Good point, but I think this may not fail to allow the hugepages in the
future. The DELEGATE_RANGE would skip the granules in DELEGATED/DATA 
state. I am getting this clarified in the spec.


Suzuki

> 
> Thanks,

---

## [151] Gavin Shan — 2026-06-26
*Subject: Re: [PATCH v14 29/44] arm64: RMI: Runtime faulting of memory*

On 6/26/26 1:58 AM, Suzuki K Poulose wrote:
> On 25/06/2026 14:53, Gavin Shan wrote:
>> On 6/6/26 12:35 AM, Lorenzo Pieralisi wrote:

[...]

>>>>
>>>> I tried to rebase Jean's latest QEMU series [1] to upstream QEMU, and found

It's hard to correlate the order since the logs are collected from two separate
consoles. For the write permission, I add code to the host where the permission
is always added for all s2 page faults in the shared space. Otherwise, qemu can
be killed by -EFAULT or similar error.

There are more findings after more experiments: this virtio-net-pci device has 3
queues or vrings (Rx/Tx/Ctrl). The Rx/Tx/Ctrl queue are populated in order one after
one. In the guest kernel, I intentionally write fixed data (0x0123456789abcdef) to
the first 8 bytes of the queue when it gets populated, and stop the guest at random
points to see if the data is gone. I found that the data written to Rx/Tx queue are
lost after Ctrl queue is allocated.

The data written to Rx/Tx queue is lost if the guest stops (B). The data written to
Rx/Tx queue isn't lost if the guest stops at (A). I can see the pattern (0x0123...cdef)
by dumping the physcial memory through 'pmemsave' command in qemu.

DMA allocation
==============
dma_alloc_coherent
   dma_alloc_attrs
     dma_direct_alloc
       __dma_direct_alloc_pages
       dma_set_decrypted                    // (A) No data lost if being stopped here for the Ctrl queue
       memset(ret, 0, size)                 // (B) Data lost after being stopped after memset() for the Ctrl queue

The memset() on the Ctrl queue should trigger a stage2 page fault. It seems the page
fault enforces the shared pages for Rx/Tx queue to be dropped? I need to add more
debugging code and track it down.

> Suzuki
> 
Thanks,
Gavin

---

## [152] Suzuki K Poulose — 2026-06-26
*Subject: Re: [PATCH v14 29/44] arm64: RMI: Runtime faulting of memory*

On 26/06/2026 08:43, Gavin Shan wrote:
> On 6/26/26 1:58 AM, Suzuki K Poulose wrote:
>> On 25/06/2026 14:53, Gavin Shan wrote:

This is the problem. We can't add WRITE permission by default. I believe
you may have MAP_PRIVATE mapping and it has to be mapped as READ only
and on a permission fault, we replace it with a writable page. By
overriding the WRITE permission, you let the guest write to a page
that may not be seen by the VMM.

We identified this as a bug in the KVM driver in this series (reported
by Lorenzo) and there is a corresponding tf-RMM change that is required
to get this working. So, please could you wait until the next series
when this will be addressed ? Or you could switch to using MAP_SHARED
for the "shared" memory in the memslot.


Suzuki


> 
> There are more findings after more experiments: this virtio-net-pci

---

## [153] Suzuki K Poulose — 2026-06-26
*Subject: Re: [PATCH v14 29/44] arm64: RMI: Runtime faulting of memory*

On 26/06/2026 09:47, Suzuki K Poulose wrote:
> On 26/06/2026 08:43, Gavin Shan wrote:
>> On 6/26/26 1:58 AM, Suzuki K Poulose wrote:

For the record, you need something like this :

--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c

@@ -838,8 +838,17 @@ int realm_map_non_secure(struct realm *realm,
                 if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
                         /* Create missing RTTs and retry */
                         int level = RMI_RETURN_INDEX(ret);
+                       int req_level = find_map_level(realm, ipa, ipa_top);
+
+                       /*
+                        * There already exists a mapping at the level. 
May be
+                        * we are relaxing a permission for the given 
range ?
+                        */
+                       if (level >= req_level) {
+                               realm_unmap_shared_range(kvm, ipa, 
ipa_top, false);
+                               continue;
+                       }

-                       WARN_ON(level == KVM_PGTABLE_LAST_LEVEL);
                         ret = realm_create_rtt_levels(realm, ipa, level,
  
KVM_PGTABLE_LAST_LEVEL,
                                                       memcache);


Thanks
Suzuki


> 
>

---

## [154] Gavin Shan — 2026-06-26
*Subject: Re: [PATCH v14 29/44] arm64: RMI: Runtime faulting of memory*

On 6/26/26 6:47 PM, Suzuki K Poulose wrote:
> On 26/06/2026 08:43, Gavin Shan wrote:
>> On 6/26/26 1:58 AM, Suzuki K Poulose wrote:

Exactly. the syntax for MAP_PRIVATE is broken if the write permission is
enforced for a read fault in the shared space. In my case, the host page can
be the zero page and eventually multiple s2 page-table entries (for multiple
unprotected or shared pages) point to the zero page. It's why clearing the
3rd queue (Ctrl queue) also clears the first queue (Rx queue) in my case.

Yes, this issue can be avoid by using a shared memory backend in qemu, something
like below. With this, I'm able to see virtio-net-pci starts to work...

     -object memory-backend-ram,id=mem0,size=2G,share=yes

Thanks,
Gavin

> 
> Suzuki

---

## [155] Lorenzo Pieralisi — 2026-06-26
*Subject: Re: [PATCH v14 29/44] arm64: RMI: Runtime faulting of memory*

On Fri, Jun 26, 2026 at 09:43:03PM +1000, Gavin Shan wrote:
> On 6/26/26 6:47 PM, Suzuki K Poulose wrote:
> > On 26/06/2026 08:43, Gavin Shan wrote:

Yes, as Suzuki said that's what we have been fixing. QEmu patches
will be on the mailing lists very shortly - the KVM/tf-RMM fixes
to make MAP_PRIVATE work will be included in the next posting.

Feel free to drop your QEmu command line so that I can give it
a shot and check whether the fixes solve the problem you hit
(I think so because that's precisely the kind of issue I got
into when I started debugging THP/MAP_PRIVATE but it is better
to check).

Thanks,
Lorenzo

---

## [156] Gavin Shan — 2026-06-28
*Subject: Re: [PATCH v14 29/44] arm64: RMI: Runtime faulting of memory*

On 6/27/26 2:44 AM, Lorenzo Pieralisi wrote:
> On Fri, Jun 26, 2026 at 09:43:03PM +1000, Gavin Shan wrote:
>> On 6/26/26 6:47 PM, Suzuki K Poulose wrote:

The virtio-net-pci doesn't work with the following command lines. The guest
kernel image is built from upstream kernel (v7.1.rc7).

     qemu-system-aarch64 -enable-kvm -object rme-guest,id=rme0,             \
     -machine virt,gic-version=3,confidential-guest-support=rme0            \
     -cpu host,pmu=off                                                      \
     -smp maxcpus=2,cpus=2,sockets=1,clusters=1,cores=1,threads=2           \
     -m 2G -object memory-backend-ram,id=mem0,size=2G                       \
     -numa node,nodeid=0,cpus=0-1,memdev=mem0                               \
     -serial mon:stdio -monitor none -nographic -nodefaults                 \
     -kernel /mnt/linux/arch/arm64/boot/Image                               \
     -initrd /mnt/buildroot/output/images/rootfs.cpio.xz                    \
     -append earlycon=pl011,mmio,0x10009000000                              \
     -device pcie-root-port,bus=pcie.0,chassis=1,id=pcie.1                  \
     -device pcie-root-port,bus=pcie.0,chassis=2,id=pcie.2                  \
     -device pcie-root-port,bus=pcie.0,chassis=3,id=pcie.3                  \
     -device pcie-root-port,bus=pcie.0,chassis=4,id=pcie.4                  \
     -netdev tap,id=tap1,vhost=on,script=/etc/qemu-ifup,downscript=/etc/qemu-ifdown  \
     -device virtio-net-pci,bus=pcie.2,netdev=tap1,mac=b8:3f:d2:1d:3e:c0

The virtio-net-pci starts to work with the shareable memory-backend.

     -object memory-backend-ram,id=mem0,size=2G,share=yes

Note that THP is disabled on my host.

     root@host:~# cat /sys/kernel/mm/transparent_hugepage/enabled
     always madvise [never]

Thanks,
Gavin

> Thanks,
> Lorenzo

---
