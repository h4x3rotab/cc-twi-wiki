---
title: 'arm64: Support for Arm CCA in KVM'
date: 2025-12-17
last_reply: 2026-03-12
message_count: 82
participants: ['Steven Price', 'Suzuki K Poulose', 'Marc Zyngier', 'kernel test robot', 'Alper Gun', 'Mathieu Poirier']
---

## [1] Steven Price — 2025-12-17

This series adds support for running protected VMs using KVM under the
Arm Confidential Compute Architecture (CCA). I've changed the uAPI
following feedback from Marc.

The main change is that rather than providing a multiplex CAP and
expecting the VMM to drive the different stages of realm construction,
there's now just a minimal interface and KVM performs the necessary
operations when needed.

This series is lightly tested and is meant as a demonstration of the new
uAPI. There are a number of (known) rough corners in the implementation
that I haven't dealt with properly.

In particular please note that this series is still targetting RMM v1.0.
There is an alpha quality version of RMM v2.0 available[1]. Feedback was
that there are a number of blockers for merging with RMM v1.0 and so I
expect to rework this series to support RMM v2.0 before it is merged.
That will necessarily involve reworking the implementation.

Specifically I'm expecting improvements in:

 * GIC handling - passing state in registers, and allowing the host to
   fully emulate the GIC by allowing trap bits to be set.

 * PMU handling - again providing flexibility to the host's emulation.

 * Page size/granule size mismatch. RMM v1.0 defines the granule as 4k,
   RMM v2.0 provide the option for the host to change the granule size.
   The intention is that Linux would simply set the granule size equal
   to its page size which will significantly simplify the management of
   granules.

 * Some performance improvement from the use of range-based map/unmap
   RMI calls.

This series is based on v6.19-rc1. It is also available as a git
repository:

https://gitlab.arm.com/linux-arm/linux-cca cca-host/v12

Work in progress changes for kvmtool are available from the git
repository below:

https://gitlab.arm.com/linux-arm/kvmtool-cca cca/v10

[1] https://developer.arm.com/documentation/den0137/latest/

Jean-Philippe Brucker (7):
  arm64: RMI: Propagate number of breakpoints and watchpoints to
    userspace
  arm64: RMI: Set breakpoint parameters through SET_ONE_REG
  arm64: RMI: Initialize PMCR.N with number counter supported by RMM
  arm64: RMI: Propagate max SVE vector length from RMM
  arm64: RMI: Configure max SVE vector length for a Realm
  arm64: RMI: Provide register list for unfinalized RMI RECs
  arm64: RMI: Provide accurate register list

Joey Gouly (2):
  arm64: RMI: allow userspace to inject aborts
  arm64: RMI: support RSI_HOST_CALL

Steven Price (34):
  arm64: RME: Handle Granule Protection Faults (GPFs)
  arm64: RMI: Add SMC definitions for calling the RMM
  arm64: RMI: Add wrappers for RMI calls
  arm64: RMI: Check for RMI support at KVM init
  arm64: RMI: Define the user ABI
  arm64: RMI: Basic infrastructure for creating a realm.
  KVM: arm64: Allow passing machine type in KVM creation
  arm64: RMI: RTT tear down
  arm64: RMI: Activate realm on first VCPU run
  arm64: RMI: Allocate/free RECs to match vCPUs
  KVM: arm64: vgic: Provide helper for number of list registers
  arm64: RMI: Support for the VGIC in realms
  KVM: arm64: Support timers in realm RECs
  arm64: RMI: Handle realm enter/exit
  arm64: RMI: Handle RMI_EXIT_RIPAS_CHANGE
  KVM: arm64: Handle realm MMIO emulation
  KVM: arm64: Expose support for private memory
  arm64: RMI: Allow populating initial contents
  arm64: RMI: Set RIPAS of initial memslots
  arm64: RMI: Create the realm descriptor
  arm64: RMI: Add a VMID allocator for realms
  arm64: RMI: Runtime faulting of memory
  KVM: arm64: Handle realm VCPU load
  KVM: arm64: Validate register access for a Realm VM
  KVM: arm64: Handle Realm PSCI requests
  KVM: arm64: WARN on injected undef exceptions
  arm64: Don't expose stolen time for realm guests
  arm64: RMI: Always use 4k pages for realms
  arm64: RMI: Prevent Device mappings for Realms
  HACK: Restore per-CPU cpu_armpmu pointer
  arm_pmu: Provide a mechanism for disabling the physical IRQ
  arm64: RMI: Enable PMU support with a realm guest
  KVM: arm64: Expose KVM_ARM_VCPU_REC to user space
  arm64: RMI: Enable realms to be created

Suzuki K Poulose (3):
  kvm: arm64: Include kvm_emulate.h in kvm/arm_psci.h
  kvm: arm64: Don't expose unsupported capabilities for realm guests
  arm64: RMI: Allow checking SVE on VM instance

 Documentation/virt/kvm/api.rst       |   78 +-
 arch/arm64/include/asm/kvm_emulate.h |   31 +
 arch/arm64/include/asm/kvm_host.h    |   13 +-
 arch/arm64/include/asm/kvm_rmi.h     |  137 +++
 arch/arm64/include/asm/rmi_cmds.h    |  508 ++++++++
 arch/arm64/include/asm/rmi_smc.h     |  269 +++++
 arch/arm64/include/asm/virt.h        |    1 +
 arch/arm64/kernel/cpufeature.c       |    1 +
 arch/arm64/kvm/Kconfig               |    2 +
 arch/arm64/kvm/Makefile              |    2 +-
 arch/arm64/kvm/arch_timer.c          |   37 +-
 arch/arm64/kvm/arm.c                 |  179 ++-
 arch/arm64/kvm/guest.c               |   95 +-
 arch/arm64/kvm/hypercalls.c          |    4 +-
 arch/arm64/kvm/inject_fault.c        |    5 +-
 arch/arm64/kvm/mmio.c                |   16 +-
 arch/arm64/kvm/mmu.c                 |  214 +++-
 arch/arm64/kvm/pmu-emul.c            |    6 +
 arch/arm64/kvm/psci.c                |   30 +
 arch/arm64/kvm/reset.c               |   13 +-
 arch/arm64/kvm/rmi-exit.c            |  207 ++++
 arch/arm64/kvm/rmi.c                 | 1663 ++++++++++++++++++++++++++
 arch/arm64/kvm/sys_regs.c            |   53 +-
 arch/arm64/kvm/vgic/vgic-init.c      |    2 +-
 arch/arm64/kvm/vgic/vgic-v2.c        |    6 +-
 arch/arm64/kvm/vgic/vgic-v3.c        |   14 +-
 arch/arm64/kvm/vgic/vgic.c           |   55 +-
 arch/arm64/kvm/vgic/vgic.h           |   20 +-
 arch/arm64/mm/fault.c                |   28 +-
 drivers/perf/arm_pmu.c               |   20 +
 include/kvm/arm_arch_timer.h         |    2 +
 include/kvm/arm_pmu.h                |    4 +
 include/kvm/arm_psci.h               |    2 +
 include/linux/perf/arm_pmu.h         |    7 +
 include/uapi/linux/kvm.h             |   42 +-
 35 files changed, 3650 insertions(+), 116 deletions(-)
 create mode 100644 arch/arm64/include/asm/kvm_rmi.h
 create mode 100644 arch/arm64/include/asm/rmi_cmds.h
 create mode 100644 arch/arm64/include/asm/rmi_smc.h
 create mode 100644 arch/arm64/kvm/rmi-exit.c
 create mode 100644 arch/arm64/kvm/rmi.c

---

## [2] Steven Price — 2025-12-17
*Subject: [PATCH v12 01/46] kvm: arm64: Include kvm_emulate.h in kvm/arm_psci.h*

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

## [3] Steven Price — 2025-12-17
*Subject: [PATCH v12 02/46] arm64: RME: Handle Granule Protection Faults (GPFs)*

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
index be9dab2c7d6a..13b1d5de6d77 100644
--- a/arch/arm64/mm/fault.c
+++ b/arch/arm64/mm/fault.c
@@ -858,6 +858,22 @@ static int do_tag_check_fault(unsigned long far, unsigned long esr,
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
@@ -894,12 +910,12 @@ static const struct fault_info fault_info[] = {
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

## [4] Steven Price — 2025-12-17
*Subject: [PATCH v12 03/46] arm64: RMI: Add SMC definitions for calling the RMM*

The RMM (Realm Management Monitor) provides functionality that can be
accessed by SMC calls from the host.

The SMC definitions are based on DEN0137[1] version 1.0-rel0

[1] https://developer.arm.com/documentation/den0137/1-0rel0/

Reviewed-by: Gavin Shan <gshan@redhat.com>
Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/include/asm/rmi_smc.h | 269 +++++++++++++++++++++++++++++++
 1 file changed, 269 insertions(+)
 create mode 100644 arch/arm64/include/asm/rmi_smc.h

diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
new file mode 100644
index 000000000000..1000368f1bca
--- /dev/null
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -0,0 +1,269 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+/*
+ * Copyright (C) 2023-2024 ARM Ltd.
+ *
+ * The values and structures in this file are from the Realm Management Monitor
+ * specification (DEN0137) version 1.0-rel0:
+ * https://developer.arm.com/documentation/den0137/1-0rel0/
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
+#define SMC_RMI_VERSION			SMC_RMI_CALL(0x0150)
+#define SMC_RMI_GRANULE_DELEGATE	SMC_RMI_CALL(0x0151)
+#define SMC_RMI_GRANULE_UNDELEGATE	SMC_RMI_CALL(0x0152)
+#define SMC_RMI_DATA_CREATE		SMC_RMI_CALL(0x0153)
+#define SMC_RMI_DATA_CREATE_UNKNOWN	SMC_RMI_CALL(0x0154)
+#define SMC_RMI_DATA_DESTROY		SMC_RMI_CALL(0x0155)
+
+#define SMC_RMI_REALM_ACTIVATE		SMC_RMI_CALL(0x0157)
+#define SMC_RMI_REALM_CREATE		SMC_RMI_CALL(0x0158)
+#define SMC_RMI_REALM_DESTROY		SMC_RMI_CALL(0x0159)
+#define SMC_RMI_REC_CREATE		SMC_RMI_CALL(0x015a)
+#define SMC_RMI_REC_DESTROY		SMC_RMI_CALL(0x015b)
+#define SMC_RMI_REC_ENTER		SMC_RMI_CALL(0x015c)
+#define SMC_RMI_RTT_CREATE		SMC_RMI_CALL(0x015d)
+#define SMC_RMI_RTT_DESTROY		SMC_RMI_CALL(0x015e)
+#define SMC_RMI_RTT_MAP_UNPROTECTED	SMC_RMI_CALL(0x015f)
+
+#define SMC_RMI_RTT_READ_ENTRY		SMC_RMI_CALL(0x0161)
+#define SMC_RMI_RTT_UNMAP_UNPROTECTED	SMC_RMI_CALL(0x0162)
+
+#define SMC_RMI_PSCI_COMPLETE		SMC_RMI_CALL(0x0164)
+#define SMC_RMI_FEATURES		SMC_RMI_CALL(0x0165)
+#define SMC_RMI_RTT_FOLD		SMC_RMI_CALL(0x0166)
+#define SMC_RMI_REC_AUX_COUNT		SMC_RMI_CALL(0x0167)
+#define SMC_RMI_RTT_INIT_RIPAS		SMC_RMI_CALL(0x0168)
+#define SMC_RMI_RTT_SET_RIPAS		SMC_RMI_CALL(0x0169)
+
+#define RMI_ABI_MAJOR_VERSION	1
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
+
+#define RMI_SUCCESS		0
+#define RMI_ERROR_INPUT		1
+#define RMI_ERROR_REALM		2
+#define RMI_ERROR_REC		3
+#define RMI_ERROR_RTT		4
+
+enum rmi_ripas {
+	RMI_EMPTY = 0,
+	RMI_RAM = 1,
+	RMI_DESTROYED = 2,
+};
+
+#define RMI_NO_MEASURE_CONTENT	0
+#define RMI_MEASURE_CONTENT	1
+
+#define RMI_FEATURE_REGISTER_0_S2SZ		GENMASK(7, 0)
+#define RMI_FEATURE_REGISTER_0_LPA2		BIT(8)
+#define RMI_FEATURE_REGISTER_0_SVE_EN		BIT(9)
+#define RMI_FEATURE_REGISTER_0_SVE_VL		GENMASK(13, 10)
+#define RMI_FEATURE_REGISTER_0_NUM_BPS		GENMASK(19, 14)
+#define RMI_FEATURE_REGISTER_0_NUM_WPS		GENMASK(25, 20)
+#define RMI_FEATURE_REGISTER_0_PMU_EN		BIT(26)
+#define RMI_FEATURE_REGISTER_0_PMU_NUM_CTRS	GENMASK(31, 27)
+#define RMI_FEATURE_REGISTER_0_HASH_SHA_256	BIT(32)
+#define RMI_FEATURE_REGISTER_0_HASH_SHA_512	BIT(33)
+#define RMI_FEATURE_REGISTER_0_GICV3_NUM_LRS	GENMASK(37, 34)
+#define RMI_FEATURE_REGISTER_0_MAX_RECS_ORDER	GENMASK(41, 38)
+#define RMI_FEATURE_REGISTER_0_Reserved		GENMASK(63, 42)
+
+#define RMI_REALM_PARAM_FLAG_LPA2		BIT(0)
+#define RMI_REALM_PARAM_FLAG_SVE		BIT(1)
+#define RMI_REALM_PARAM_FLAG_PMU		BIT(2)
+
+/*
+ * Note many of these fields are smaller than u64 but all fields have u64
+ * alignment, so use u64 to ensure correct alignment.
+ */
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
+		};
+		u8 padding0[0x400];
+	};
+	union { /* 0x400 */
+		u8 rpv[64];
+		u8 padding1[0x400];
+	};
+	union { /* 0x800 */
+		struct {
+			u64 vmid;
+			u64 rtt_base;
+			s64 rtt_level_start;
+			u64 rtt_num_start;
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
+#define REC_PARAMS_AUX_GRANULES		16
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
+		u8 padding3[0x500];
+	};
+	union { /* 0x800 */
+		struct {
+			u64 num_rec_aux;
+			u64 aux[REC_PARAMS_AUX_GRANULES];
+		};
+		u8 padding4[0x800];
+	};
+};
+
+#define REC_ENTER_FLAG_EMULATED_MMIO	BIT(0)
+#define REC_ENTER_FLAG_INJECT_SEA	BIT(1)
+#define REC_ENTER_FLAG_TRAP_WFI		BIT(2)
+#define REC_ENTER_FLAG_TRAP_WFE		BIT(3)
+#define REC_ENTER_FLAG_RIPAS_RESPONSE	BIT(4)
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
+	union { /* 0x300 */
+		struct {
+			u64 gicv3_hcr;
+			u64 gicv3_lrs[REC_MAX_GIC_NUM_LRS];
+		};
+		u8 padding2[0x100];
+	};
+	u8 padding3[0x400];
+};
+
+#define RMI_EXIT_SYNC			0x00
+#define RMI_EXIT_IRQ			0x01
+#define RMI_EXIT_FIQ			0x02
+#define RMI_EXIT_PSCI			0x03
+#define RMI_EXIT_RIPAS_CHANGE		0x04
+#define RMI_EXIT_HOST_CALL		0x05
+#define RMI_EXIT_SERROR			0x06
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
+		};
+		u8 padding1[0x100];
+	};
+	union { /* 0x200 */
+		u64 gprs[REC_RUN_GPRS];
+		u8 padding2[0x100];
+	};
+	union { /* 0x300 */
+		struct {
+			u64 gicv3_hcr;
+			u64 gicv3_lrs[REC_MAX_GIC_NUM_LRS];
+			u64 gicv3_misr;
+			u64 gicv3_vmcr;
+		};
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
+			u8 padding8[7];
+		};
+		u8 padding5[0x100];
+	};
+	union { /* 0x600 */
+		u16 imm;
+		u8 padding6[0x100];
+	};
+	union { /* 0x700 */
+		struct {
+			u8 pmu_ovf_status;
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
+#endif /* __ASM_RMI_SMC_H */

---

## [5] Steven Price — 2025-12-17
*Subject: [PATCH v12 04/46] arm64: RMI: Add wrappers for RMI calls*

The wrappers make the call sites easier to read and deal with the
boiler plate of handling the error codes from the RMM.

Reviewed-by: Gavin Shan <gshan@redhat.com>
Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/include/asm/rmi_cmds.h | 508 ++++++++++++++++++++++++++++++
 1 file changed, 508 insertions(+)
 create mode 100644 arch/arm64/include/asm/rmi_cmds.h

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
new file mode 100644
index 000000000000..ef53147c1984
--- /dev/null
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -0,0 +1,508 @@
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
+/**
+ * rmi_data_create() - Create a data granule
+ * @rd: PA of the RD
+ * @data: PA of the target granule
+ * @ipa: IPA at which the granule will be mapped in the guest
+ * @src: PA of the source granule
+ * @flags: RMI_MEASURE_CONTENT if the contents should be measured
+ *
+ * Create a new data granule, copying contents from a non-secure granule.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_data_create(unsigned long rd, unsigned long data,
+				  unsigned long ipa, unsigned long src,
+				  unsigned long flags)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_DATA_CREATE, rd, data, ipa, src,
+			     flags, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_data_create_unknown() - Create a data granule with unknown contents
+ * @rd: PA of the RD
+ * @data: PA of the target granule
+ * @ipa: IPA at which the granule will be mapped in the guest
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_data_create_unknown(unsigned long rd,
+					  unsigned long data,
+					  unsigned long ipa)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_DATA_CREATE_UNKNOWN, rd, data, ipa, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_data_destroy() - Destroy a data granule
+ * @rd: PA of the RD
+ * @ipa: IPA at which the granule is mapped in the guest
+ * @data_out: PA of the granule which was destroyed
+ * @top_out: Top IPA of non-live RTT entries
+ *
+ * Unmap a protected IPA from stage 2, transitioning it to DESTROYED.
+ * The IPA cannot be used by the guest unless it is transitioned to RAM again
+ * by the realm guest.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_data_destroy(unsigned long rd, unsigned long ipa,
+				   unsigned long *data_out,
+				   unsigned long *top_out)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_DATA_DESTROY, rd, ipa, &res);
+
+	if (data_out)
+		*data_out = res.a1;
+	if (top_out)
+		*top_out = res.a2;
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
+ * rmi_granule_delegate() - Delegate a granule
+ * @phys: PA of the granule
+ *
+ * Delegate a granule for use by the realm world.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_granule_delegate(unsigned long phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_GRANULE_DELEGATE, phys, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_granule_undelegate() - Undelegate a granule
+ * @phys: PA of the granule
+ *
+ * Undelegate a granule to allow use by the normal world. Will fail if the
+ * granule is in use.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_granule_undelegate(unsigned long phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_GRANULE_UNDELEGATE, phys, &res);
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
+ * rmi_rec_aux_count() - Get number of auxiliary granules required
+ * @rd: PA of the RD
+ * @aux_count: Number of granules written to this pointer
+ *
+ * A REC may require extra auxiliary granules to be delegated for the RMM to
+ * store metadata (not visible to the normal world) in. This function provides
+ * the number of granules that are required.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rec_aux_count(unsigned long rd, unsigned long *aux_count)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_REC_AUX_COUNT, rd, &res);
+
+	if (aux_count)
+		*aux_count = res.a1;
+	return res.a0;
+}
+
+/**
+ * rmi_rec_create() - Create a REC
+ * @rd: PA of the RD
+ * @rec: PA of the target REC
+ * @params: PA of REC parameters
+ *
+ * Create a REC using the parameters specified in the struct rec_params pointed
+ * to by @params.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rec_create(unsigned long rd, unsigned long rec,
+				 unsigned long params)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_REC_CREATE, rd, rec, params, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_rec_destroy() - Destroy a REC
+ * @rec: PA of the target REC
+ *
+ * Destroys a REC. The REC must not be running.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rec_destroy(unsigned long rec)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_REC_DESTROY, rec, &res);
+
+	return res.a0;
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
+ * rmi_rtt_map_unprotected() - Map NS granules into a realm
+ * @rd: PA of the RD
+ * @ipa: Base IPA of the mapping
+ * @level: Depth within the RTT tree
+ * @desc: RTTE descriptor
+ *
+ * Create a mapping from an Unprotected IPA to a Non-secure PA.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rtt_map_unprotected(unsigned long rd,
+					  unsigned long ipa,
+					  long level,
+					  unsigned long desc)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_MAP_UNPROTECTED, rd, ipa, level,
+			     desc, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_rtt_read_entry() - Read an RTTE
+ * @rd: PA of the RD
+ * @ipa: IPA for which to read the RTTE
+ * @level: RTT level at which to read the RTTE
+ * @rtt: Output structure describing the RTTE
+ *
+ * Reads a RTTE (Realm Translation Table Entry).
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rtt_read_entry(unsigned long rd, unsigned long ipa,
+				     long level, struct rtt_entry *rtt)
+{
+	struct arm_smccc_1_2_regs regs = {
+		SMC_RMI_RTT_READ_ENTRY,
+		rd, ipa, level
+	};
+
+	arm_smccc_1_2_invoke(&regs, &regs);
+
+	rtt->walk_level = regs.a1;
+	rtt->state = regs.a2 & 0xFF;
+	rtt->desc = regs.a3;
+	rtt->ripas = regs.a4 & 0xFF;
+
+	return regs.a0;
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
+ * rmi_rtt_unmap_unprotected() - Remove a NS mapping
+ * @rd: PA of the RD
+ * @ipa: Base IPA of the mapping
+ * @level: Depth within the RTT tree
+ * @out_top: Pointer to write top IPA of non-live RTT entries
+ *
+ * Removes a mapping at an Unprotected IPA.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rtt_unmap_unprotected(unsigned long rd,
+					    unsigned long ipa,
+					    long level,
+					    unsigned long *out_top)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_UNMAP_UNPROTECTED, rd, ipa,
+			     level, &res);
+
+	if (out_top)
+		*out_top = res.a1;
+
+	return res.a0;
+}
+
+#endif /* __ASM_RMI_CMDS_H */

---

## [6] Steven Price — 2025-12-17
*Subject: [PATCH v12 05/46] arm64: RMI: Check for RMI support at KVM init*

Query the RMI version number and check if it is a compatible version. A
static key is also provided to signal that a supported RMM is available.

Functions are provided to query if a VM or VCPU is a realm (or rec)
which currently will always return false.

Later patches make use of struct realm and the states as the ioctls
interfaces are added to support realm and REC creation and destruction.

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/include/asm/kvm_emulate.h | 18 ++++++++
 arch/arm64/include/asm/kvm_host.h    |  4 ++
 arch/arm64/include/asm/kvm_rmi.h     | 56 +++++++++++++++++++++++++
 arch/arm64/include/asm/virt.h        |  1 +
 arch/arm64/kernel/cpufeature.c       |  1 +
 arch/arm64/kvm/Makefile              |  2 +-
 arch/arm64/kvm/arm.c                 |  5 +++
 arch/arm64/kvm/rmi.c                 | 61 ++++++++++++++++++++++++++++
 8 files changed, 147 insertions(+), 1 deletion(-)
 create mode 100644 arch/arm64/include/asm/kvm_rmi.h
 create mode 100644 arch/arm64/kvm/rmi.c

diff --git a/arch/arm64/include/asm/kvm_emulate.h b/arch/arm64/include/asm/kvm_emulate.h
index c9eab316398e..67f75678e489 100644
--- a/arch/arm64/include/asm/kvm_emulate.h
+++ b/arch/arm64/include/asm/kvm_emulate.h
@@ -696,4 +696,22 @@ static inline void vcpu_set_hcrx(struct kvm_vcpu *vcpu)
 			vcpu->arch.hcrx_el2 |= HCRX_EL2_SCTLR2En;
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
+static inline bool vcpu_is_rec(struct kvm_vcpu *vcpu)
+{
+	return false;
+}
+
 #endif /* __ARM64_KVM_EMULATE_H__ */
diff --git a/arch/arm64/include/asm/kvm_host.h b/arch/arm64/include/asm/kvm_host.h
index ac7f970c7883..da913fee70b6 100644
--- a/arch/arm64/include/asm/kvm_host.h
+++ b/arch/arm64/include/asm/kvm_host.h
@@ -27,6 +27,7 @@
 #include <asm/fpsimd.h>
 #include <asm/kvm.h>
 #include <asm/kvm_asm.h>
+#include <asm/kvm_rmi.h>
 #include <asm/vncr_mapping.h>
 
 #define __KVM_HAVE_ARCH_INTC_INITIALIZED
@@ -408,6 +409,9 @@ struct kvm_arch {
 	 * the associated pKVM instance in the hypervisor.
 	 */
 	struct kvm_protected_vm pkvm;
+
+	bool is_realm;
+	struct realm realm;
 };
 
 struct kvm_vcpu_fault_info {
diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
new file mode 100644
index 000000000000..3506f50b05cd
--- /dev/null
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -0,0 +1,56 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+/*
+ * Copyright (C) 2023-2025 ARM Ltd.
+ */
+
+#ifndef __ASM_KVM_RMI_H
+#define __ASM_KVM_RMI_H
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
+/**
+ * struct realm - Additional per VM data for a Realm
+ *
+ * @state: The lifetime state machine for the realm
+ */
+struct realm {
+	enum realm_state state;
+};
+
+void kvm_init_rmi(void);
+
+#endif /* __ASM_KVM_RMI_H */
diff --git a/arch/arm64/include/asm/virt.h b/arch/arm64/include/asm/virt.h
index b51ab6840f9c..dc9b2899e0b2 100644
--- a/arch/arm64/include/asm/virt.h
+++ b/arch/arm64/include/asm/virt.h
@@ -87,6 +87,7 @@ void __hyp_reset_vectors(void);
 bool is_kvm_arm_initialised(void);
 
 DECLARE_STATIC_KEY_FALSE(kvm_protected_mode_initialized);
+DECLARE_STATIC_KEY_FALSE(kvm_rmi_is_available);
 
 static inline bool is_pkvm_initialized(void)
 {
diff --git a/arch/arm64/kernel/cpufeature.c b/arch/arm64/kernel/cpufeature.c
index c840a93b9ef9..fa5ef83af7de 100644
--- a/arch/arm64/kernel/cpufeature.c
+++ b/arch/arm64/kernel/cpufeature.c
@@ -288,6 +288,7 @@ static const struct arm64_ftr_bits ftr_id_aa64isar3[] = {
 static const struct arm64_ftr_bits ftr_id_aa64pfr0[] = {
 	ARM64_FTR_BITS(FTR_HIDDEN, FTR_NONSTRICT, FTR_LOWER_SAFE, ID_AA64PFR0_EL1_CSV3_SHIFT, 4, 0),
 	ARM64_FTR_BITS(FTR_HIDDEN, FTR_NONSTRICT, FTR_LOWER_SAFE, ID_AA64PFR0_EL1_CSV2_SHIFT, 4, 0),
+	ARM64_FTR_BITS(FTR_HIDDEN, FTR_NONSTRICT, FTR_LOWER_SAFE, ID_AA64PFR0_EL1_RME_SHIFT, 4, 0),
 	ARM64_FTR_BITS(FTR_VISIBLE, FTR_STRICT, FTR_LOWER_SAFE, ID_AA64PFR0_EL1_DIT_SHIFT, 4, 0),
 	ARM64_FTR_BITS(FTR_HIDDEN, FTR_NONSTRICT, FTR_LOWER_SAFE, ID_AA64PFR0_EL1_AMU_SHIFT, 4, 0),
 	ARM64_FTR_BITS(FTR_HIDDEN, FTR_STRICT, FTR_LOWER_SAFE, ID_AA64PFR0_EL1_MPAM_SHIFT, 4, 0),
diff --git a/arch/arm64/kvm/Makefile b/arch/arm64/kvm/Makefile
index 3ebc0570345c..e17c4077d8e7 100644
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
index 4f80da0c0d1d..a537f56f97db 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -39,6 +39,7 @@
 #include <asm/kvm_nested.h>
 #include <asm/kvm_pkvm.h>
 #include <asm/kvm_ptrauth.h>
+#include <asm/kvm_rmi.h>
 #include <asm/sections.h>
 
 #include <kvm/arm_hypercalls.h>
@@ -58,6 +59,8 @@ enum kvm_wfx_trap_policy {
 static enum kvm_wfx_trap_policy kvm_wfi_trap_policy __read_mostly = KVM_WFX_NOTRAP_SINGLE_TASK;
 static enum kvm_wfx_trap_policy kvm_wfe_trap_policy __read_mostly = KVM_WFX_NOTRAP_SINGLE_TASK;
 
+DEFINE_STATIC_KEY_FALSE(kvm_rmi_is_available);
+
 DECLARE_KVM_HYP_PER_CPU(unsigned long, kvm_hyp_vector);
 
 DEFINE_PER_CPU(unsigned long, kvm_arm_hyp_stack_base);
@@ -2865,6 +2868,8 @@ static __init int kvm_arm_init(void)
 
 	in_hyp_mode = is_kernel_in_hyp_mode();
 
+	kvm_init_rmi();
+
 	if (cpus_have_final_cap(ARM64_WORKAROUND_DEVICE_LOAD_ACQUIRE) ||
 	    cpus_have_final_cap(ARM64_WORKAROUND_1508412))
 		kvm_info("Guests without required CPU erratum workarounds can deadlock system!\n" \
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
new file mode 100644
index 000000000000..629ace10cacc
--- /dev/null
+++ b/arch/arm64/kvm/rmi.c
@@ -0,0 +1,61 @@
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
+		kvm_err("Unsupported RMI ABI (v%d.%d - v%d.%d) we want v%d.%d\n",
+			version_major, version_minor,
+			high_version_major, high_version_minor,
+			RMI_ABI_MAJOR_VERSION,
+			RMI_ABI_MINOR_VERSION);
+		return -ENXIO;
+	}
+
+	kvm_info("RMI ABI version %d.%d\n", version_major, version_minor);
+
+	return 0;
+}
+
+void kvm_init_rmi(void)
+{
+	/* Only 4k page size on the host is supported */
+	if (PAGE_SIZE != SZ_4K)
+		return;
+
+	/* Continue without realm support if we can't agree on a version */
+	if (rmi_check_version())
+		return;
+
+	/* Future patch will enable static branch kvm_rmi_is_available */
+}

---

## [7] Steven Price — 2025-12-17
*Subject: [PATCH v12 06/46] arm64: RMI: Define the user ABI*

There is one CAP which identified the presence of CCA, and two ioctls.
One ioctl is used to populate memory and the other is used when user
space is providing the PSCI implementation to identify the target of the
operation.

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 Documentation/virt/kvm/api.rst | 57 ++++++++++++++++++++++++++++++++++
 include/uapi/linux/kvm.h       | 23 ++++++++++++++
 2 files changed, 80 insertions(+)

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index 01a3abef8abb..2d5dc7e48954 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -6517,6 +6517,54 @@ the capability to be present.
 
 `flags` must currently be zero.
 
+4.144 KVM_ARM_VCPU_RMI_PSCI_COMPLETE
+------------------------------------
+
+:Capability: KVM_CAP_ARM_RMI
+:Architectures: arm64
+:Type: vcpu ioctl
+:Parameters: struct kvm_arm_rmi_psci_complete (in)
+:Returns: 0 if successful, < 0 on error
+
+::
+
+  struct kvm_arm_rmi_psci_complete {
+	__u64 target_mpidr;
+	__u32 psci_status;
+	__u32 padding[3];
+  };
+
+Where PSCI functions are handled by user space, the RMM needs to be informed of
+the target of the operation using `target_mpidr`, along with the status
+(`psci_status`). The RMM v1.0 specification defines two functions that require
+this call: PSCI_CPU_ON and PSCI_AFFINITY_INFO.
+
+If the kernel is handling PSCI then this is done automatically and the VMM
+doesn't need to call this ioctl.
+
+4.145 KVM_ARM_RMI_POPULATE
+--------------------------
+
+:Capability: KVM_CAP_ARM_RMI
+:Architectures: arm64
+:Type: vm ioctl
+:Parameters: struct kvm_arm_rmi_populate (in)
+:Returns: number of bytes populated, < 0 on error
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
+Populate a region of protected address space by copying the data from the user
+space pointer provided. This is only valid before any VCPUs have been run.
+The ioctl might not populate the entire region and user space may have to
+repeatedly call it (with updated pointers) to populate the entire region.
 
 .. _kvm_run:
 
@@ -8765,6 +8813,15 @@ helpful if user space wants to emulate instructions which are not
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
index dddb781b0507..8e66ba9c81db 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -974,6 +974,7 @@ struct kvm_enable_cap {
 #define KVM_CAP_GUEST_MEMFD_FLAGS 244
 #define KVM_CAP_ARM_SEA_TO_USER 245
 #define KVM_CAP_S390_USER_OPEREXEC 246
+#define KVM_CAP_ARM_RMI 247
 
 struct kvm_irq_routing_irqchip {
 	__u32 irqchip;
@@ -1628,4 +1629,26 @@ struct kvm_pre_fault_memory {
 	__u64 padding[5];
 };
 
+/* Available with KVM_CAP_ARM_RMI, only for VMs with KVM_VM_TYPE_ARM_REALM  */
+struct kvm_arm_rmi_psci_complete {
+	__u64 target_mpidr;
+	__u32 psci_status;
+	__u32 padding[3];
+};
+
+#define KVM_ARM_VCPU_RMI_PSCI_COMPLETE	_IOW(KVMIO, 0xd6, struct kvm_arm_rmi_psci_complete)
+
+/* Available with KVM_CAP_ARM_RMI, only for VMs with KVM_VM_TYPE_ARM_REALM */
+struct kvm_arm_rmi_populate {
+	__u64 base;
+	__u64 size;
+	__u64 source_uaddr;
+	__u32 flags;
+	__u32 reserved;
+};
+
+#define KVM_ARM_RMI_POPULATE_FLAGS_MEASURE	(1 << 0)
+
+#define KVM_ARM_RMI_POPULATE	_IOW(KVMIO, 0xd7, struct kvm_arm_rmi_populate)
+
 #endif /* __LINUX_KVM_H */

---

## [8] Steven Price — 2025-12-17
*Subject: [PATCH v12 07/46] arm64: RMI: Basic infrastructure for creating a realm.*

Introduce the skeleton functions for creating and destroying a realm.
The IPA size requested is checked against what the RMM supports.

The actual work of constructing the realm will be added in future
patches.

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/include/asm/kvm_emulate.h |  5 ++
 arch/arm64/include/asm/kvm_rmi.h     | 18 +++++++
 arch/arm64/kvm/arm.c                 | 11 ++++
 arch/arm64/kvm/mmu.c                 | 11 ++--
 arch/arm64/kvm/rmi.c                 | 81 ++++++++++++++++++++++++++++
 5 files changed, 123 insertions(+), 3 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_emulate.h b/arch/arm64/include/asm/kvm_emulate.h
index 67f75678e489..e7e9364ae118 100644
--- a/arch/arm64/include/asm/kvm_emulate.h
+++ b/arch/arm64/include/asm/kvm_emulate.h
@@ -709,6 +709,11 @@ static inline enum realm_state kvm_realm_state(struct kvm *kvm)
 	return READ_ONCE(kvm->arch.realm.state);
 }
 
+static inline bool kvm_realm_is_created(struct kvm *kvm)
+{
+	return kvm_is_realm(kvm) && kvm_realm_state(kvm) != REALM_STATE_NONE;
+}
+
 static inline bool vcpu_is_rec(struct kvm_vcpu *vcpu)
 {
 	return false;
diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index 3506f50b05cd..7f06aa5b0550 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -6,6 +6,8 @@
 #ifndef __ASM_KVM_RMI_H
 #define __ASM_KVM_RMI_H
 
+#include <asm/rmi_smc.h>
+
 /**
  * enum realm_state - State of a Realm
  */
@@ -46,11 +48,27 @@ enum realm_state {
  * struct realm - Additional per VM data for a Realm
  *
  * @state: The lifetime state machine for the realm
+ * @rd: Kernel mapping of the Realm Descriptor (RD)
+ * @params: Parameters for the RMI_REALM_CREATE command
+ * @num_aux: The number of auxiliary pages required by the RMM
+ * @vmid: VMID to be used by the RMM for the realm
+ * @ia_bits: Number of valid Input Address bits in the IPA
  */
 struct realm {
 	enum realm_state state;
+
+	void *rd;
+	struct realm_params *params;
+
+	unsigned long num_aux;
+	unsigned int vmid;
+	unsigned int ia_bits;
 };
 
 void kvm_init_rmi(void);
+u32 kvm_realm_ipa_limit(void);
+
+int kvm_init_realm_vm(struct kvm *kvm);
+void kvm_destroy_realm(struct kvm *kvm);
 
 #endif /* __ASM_KVM_RMI_H */
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index a537f56f97db..4ce3ad1d69b0 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -207,6 +207,13 @@ int kvm_arch_init_vm(struct kvm *kvm, unsigned long type)
 
 	bitmap_zero(kvm->arch.vcpu_features, KVM_VCPU_MAX_FEATURES);
 
+	/* Initialise the realm bits after the generic bits are enabled */
+	if (kvm_is_realm(kvm)) {
+		ret = kvm_init_realm_vm(kvm);
+		if (ret)
+			goto err_free_cpumask;
+	}
+
 	return 0;
 
 err_free_cpumask:
@@ -266,6 +273,7 @@ void kvm_arch_destroy_vm(struct kvm *kvm)
 	kvm_unshare_hyp(kvm, kvm + 1);
 
 	kvm_arm_teardown_hypercalls(kvm);
+	kvm_destroy_realm(kvm);
 }
 
 static bool kvm_has_full_ptr_auth(void)
@@ -427,6 +435,9 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 		else
 			r = kvm_supports_cacheable_pfnmap();
 		break;
+	case KVM_CAP_ARM_RMI:
+		r = static_key_enabled(&kvm_rmi_is_available);
+		break;
 
 	default:
 		r = 0;
diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index 48d7c372a4cd..d91e7eb2c8d3 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -872,12 +872,16 @@ static struct kvm_pgtable_mm_ops kvm_s2_mm_ops = {
 	.icache_inval_pou	= invalidate_icache_guest_page,
 };
 
-static int kvm_init_ipa_range(struct kvm_s2_mmu *mmu, unsigned long type)
+static int kvm_init_ipa_range(struct kvm *kvm,
+			      struct kvm_s2_mmu *mmu, unsigned long type)
 {
 	u32 kvm_ipa_limit = get_kvm_ipa_limit();
 	u64 mmfr0, mmfr1;
 	u32 phys_shift;
 
+	if (kvm_is_realm(kvm))
+		kvm_ipa_limit = kvm_realm_ipa_limit();
+
 	if (type & ~KVM_VM_TYPE_ARM_IPA_SIZE_MASK)
 		return -EINVAL;
 
@@ -974,7 +978,7 @@ int kvm_init_stage2_mmu(struct kvm *kvm, struct kvm_s2_mmu *mmu, unsigned long t
 		return -EINVAL;
 	}
 
-	err = kvm_init_ipa_range(mmu, type);
+	err = kvm_init_ipa_range(kvm, mmu, type);
 	if (err)
 		return err;
 
@@ -1113,7 +1117,8 @@ void kvm_free_stage2_pgd(struct kvm_s2_mmu *mmu)
 	write_unlock(&kvm->mmu_lock);
 
 	if (pgt) {
-		kvm_stage2_destroy(pgt);
+		if (!kvm_is_realm(kvm))
+			kvm_stage2_destroy(pgt);
 		kfree(pgt);
 	}
 }
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 629ace10cacc..c2b13fecfd11 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -5,9 +5,18 @@
 
 #include <linux/kvm_host.h>
 
+#include <asm/kvm_emulate.h>
+#include <asm/kvm_mmu.h>
 #include <asm/rmi_cmds.h>
 #include <asm/virt.h>
 
+#include <asm/kvm_pgtable.h>
+
+static unsigned long rmm_feat_reg0;
+
+#define RMM_PAGE_SHIFT		12
+#define RMM_PAGE_SIZE		BIT(RMM_PAGE_SHIFT)
+
 static int rmi_check_version(void)
 {
 	struct arm_smccc_res res;
@@ -47,6 +56,75 @@ static int rmi_check_version(void)
 	return 0;
 }
 
+u32 kvm_realm_ipa_limit(void)
+{
+	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_S2SZ);
+}
+
+static int free_delegated_granule(phys_addr_t phys)
+{
+	if (WARN_ON(rmi_granule_undelegate(phys))) {
+		/* Undelegate failed: leak the page */
+		return -EBUSY;
+	}
+
+	free_page((unsigned long)phys_to_virt(phys));
+
+	return 0;
+}
+
+void kvm_destroy_realm(struct kvm *kvm)
+{
+	struct realm *realm = &kvm->arch.realm;
+	size_t pgd_size = kvm_pgtable_stage2_pgd_size(kvm->arch.mmu.vtcr);
+	int i;
+
+	write_lock(&kvm->mmu_lock);
+	kvm_stage2_unmap_range(&kvm->arch.mmu, 0,
+			       BIT(realm->ia_bits - 1), true);
+	write_unlock(&kvm->mmu_lock);
+
+	if (realm->params) {
+		free_page((unsigned long)realm->params);
+		realm->params = NULL;
+	}
+
+	if (!kvm_realm_is_created(kvm))
+		return;
+
+	WRITE_ONCE(realm->state, REALM_STATE_DYING);
+
+	if (realm->rd) {
+		phys_addr_t rd_phys = virt_to_phys(realm->rd);
+
+		if (WARN_ON(rmi_realm_destroy(rd_phys)))
+			return;
+		free_delegated_granule(rd_phys);
+		realm->rd = NULL;
+	}
+
+	for (i = 0; i < pgd_size; i += RMM_PAGE_SIZE) {
+		phys_addr_t pgd_phys = kvm->arch.mmu.pgd_phys + i;
+
+		if (WARN_ON(rmi_granule_undelegate(pgd_phys)))
+			return;
+	}
+
+	WRITE_ONCE(realm->state, REALM_STATE_DEAD);
+
+	/* Now that the Realm is destroyed, free the entry level RTTs */
+	kvm_free_stage2_pgd(&kvm->arch.mmu);
+}
+
+int kvm_init_realm_vm(struct kvm *kvm)
+{
+	kvm->arch.realm.params = (void *)get_zeroed_page(GFP_KERNEL);
+
+	if (!kvm->arch.realm.params)
+		return -ENOMEM;
+	return 0;
+}
+
 void kvm_init_rmi(void)
 {
 	/* Only 4k page size on the host is supported */
@@ -57,5 +135,8 @@ void kvm_init_rmi(void)
 	if (rmi_check_version())
 		return;
 
+	if (WARN_ON(rmi_features(0, &rmm_feat_reg0)))
+		return;
+
 	/* Future patch will enable static branch kvm_rmi_is_available */
 }

---

## [9] Steven Price — 2025-12-17
*Subject: [PATCH v12 08/46] kvm: arm64: Don't expose unsupported capabilities for realm guests*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

RMM v1.0 provides no mechanism for the host to perform debug operations
on the guest. So limit the extensions that are visible to an allowlist
so that only those capabilities we can support are advertised.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v10:
 * Add a kvm_realm_ext_allowed() function which limits which extensions
   are exposed to an allowlist. This removes the need for special casing
   various extensions.
Changes since v7:
 * Remove the helper functions and inline the kvm_is_realm() check with
   a ternary operator.
 * Rewrite the commit message to explain this patch.
---
 arch/arm64/kvm/arm.c | 23 +++++++++++++++++++++++
 1 file changed, 23 insertions(+)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 4ce3ad1d69b0..345d9f56e98e 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -310,6 +310,26 @@ static bool kvm_has_full_ptr_auth(void)
 		(apa + api + apa3) == 1);
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
+	case KVM_CAP_ARM_PMU_V3:
+	case KVM_CAP_ARM_PTRAUTH_ADDRESS:
+	case KVM_CAP_ARM_PTRAUTH_GENERIC:
+	case KVM_CAP_ARM_RMI:
+		return true;
+	}
+	return false;
+}
+
 int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 {
 	int r;
@@ -317,6 +337,9 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 	if (kvm && kvm_vm_is_protected(kvm) && !kvm_pvm_ext_allowed(ext))
 		return 0;
 
+	if (kvm && kvm_is_realm(kvm) && !kvm_realm_ext_allowed(ext))
+		return 0;
+
 	switch (ext) {
 	case KVM_CAP_IRQCHIP:
 		r = vgic_present;

---

## [10] Steven Price — 2025-12-17
*Subject: [PATCH v12 09/46] KVM: arm64: Allow passing machine type in KVM creation*

Previously machine type was used purely for specifying the physical
address size of the guest. Reserve the higher bits to specify an ARM
specific machine type and declare a new type 'KVM_VM_TYPE_ARM_REALM'
used to create a realm guest.

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 Documentation/virt/kvm/api.rst | 16 ++++++++++++++--
 arch/arm64/kvm/arm.c           | 16 ++++++++++++++++
 arch/arm64/kvm/mmu.c           |  3 ---
 include/uapi/linux/kvm.h       | 19 +++++++++++++++----
 4 files changed, 45 insertions(+), 9 deletions(-)

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index 2d5dc7e48954..d7ebf42933e8 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -181,8 +181,20 @@ flag KVM_VM_MIPS_VZ.
 ARM64:
 ^^^^^^
 
-On arm64, the physical address size for a VM (IPA Size limit) is limited
-to 40bits by default. The limit can be configured if the host supports the
+On arm64, the machine type identifier is used to encode a type and the
+physical address size for the VM. The lower byte (bits[7-0]) encode the
+address size and the upper bits[11-8] encode a machine type. The machine
+types that might be available are:
+
+ ======================   ============================================
+ KVM_VM_TYPE_ARM_NORMAL   A standard VM
+ KVM_VM_TYPE_ARM_REALM    A "Realm" VM using the Arm Confidential
+                          Compute extensions, the VM's memory is
+                          protected from the host.
+ ======================   ============================================
+
+The physical address size for a VM (IPA Size limit) is limited to 40bits
+by default. The limit can be configured if the host supports the
 extension KVM_CAP_ARM_VM_IPA_SIZE. When supported, use
 KVM_VM_TYPE_ARM_IPA_SIZE(IPA_Bits) to set the size in the machine type
 identifier, where IPA_Bits is the maximum width of any physical
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 345d9f56e98e..941d1bec8e77 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -170,6 +170,22 @@ int kvm_arch_init_vm(struct kvm *kvm, unsigned long type)
 	mutex_unlock(&kvm->lock);
 #endif
 
+	if (type & ~(KVM_VM_TYPE_ARM_MASK | KVM_VM_TYPE_ARM_IPA_SIZE_MASK))
+		return -EINVAL;
+
+	switch (type & KVM_VM_TYPE_ARM_MASK) {
+	case KVM_VM_TYPE_ARM_NORMAL:
+		break;
+	case KVM_VM_TYPE_ARM_REALM:
+		if (!static_branch_unlikely(&kvm_rmi_is_available))
+			return -EINVAL;
+		WRITE_ONCE(kvm->arch.realm.state, REALM_STATE_NONE);
+		kvm->arch.is_realm = true;
+		break;
+	default:
+		return -EINVAL;
+	}
+
 	kvm_init_nested(kvm);
 
 	ret = kvm_share_hyp(kvm, kvm + 1);
diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index d91e7eb2c8d3..ed86a10f08e0 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -882,9 +882,6 @@ static int kvm_init_ipa_range(struct kvm *kvm,
 	if (kvm_is_realm(kvm))
 		kvm_ipa_limit = kvm_realm_ipa_limit();
 
-	if (type & ~KVM_VM_TYPE_ARM_IPA_SIZE_MASK)
-		return -EINVAL;
-
 	phys_shift = KVM_VM_TYPE_ARM_IPA_SIZE(type);
 	if (is_protected_kvm_enabled()) {
 		phys_shift = kvm_ipa_limit;
diff --git a/include/uapi/linux/kvm.h b/include/uapi/linux/kvm.h
index 8e66ba9c81db..c51fd88feedf 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -681,14 +681,25 @@ struct kvm_enable_cap {
 #define KVM_S390_SIE_PAGE_OFFSET 1
 
 /*
- * On arm64, machine type can be used to request the physical
- * address size for the VM. Bits[7-0] are reserved for the guest
- * PA size shift (i.e, log2(PA_Size)). For backward compatibility,
- * value 0 implies the default IPA size, 40bits.
+ * On arm64, machine type can be used to request both the machine type and
+ * the physical address size for the VM.
+ *
+ * Bits[11-8] are reserved for the ARM specific machine type.
+ *
+ * Bits[7-0] are reserved for the guest PA size shift (i.e, log2(PA_Size)).
+ * For backward compatibility, value 0 implies the default IPA size, 40bits.
  */
+#define KVM_VM_TYPE_ARM_SHIFT		8
+#define KVM_VM_TYPE_ARM_MASK		(0xfULL << KVM_VM_TYPE_ARM_SHIFT)
+#define KVM_VM_TYPE_ARM(_type)		\
+	(((_type) << KVM_VM_TYPE_ARM_SHIFT) & KVM_VM_TYPE_ARM_MASK)
+#define KVM_VM_TYPE_ARM_NORMAL		KVM_VM_TYPE_ARM(0)
+#define KVM_VM_TYPE_ARM_REALM		KVM_VM_TYPE_ARM(1)
+
 #define KVM_VM_TYPE_ARM_IPA_SIZE_MASK	0xffULL
 #define KVM_VM_TYPE_ARM_IPA_SIZE(x)		\
 	((x) & KVM_VM_TYPE_ARM_IPA_SIZE_MASK)
+
 /*
  * ioctls for /dev/kvm fds:
  */

---

## [11] Steven Price — 2025-12-17
*Subject: [PATCH v12 10/46] arm64: RMI: RTT tear down*

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
 arch/arm64/kvm/mmu.c             |  15 ++-
 arch/arm64/kvm/rmi.c             | 151 +++++++++++++++++++++++++++++++
 3 files changed, 172 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index 7f06aa5b0550..cb7350f8a01a 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -70,5 +70,12 @@ u32 kvm_realm_ipa_limit(void);
 
 int kvm_init_realm_vm(struct kvm *kvm);
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
index ed86a10f08e0..68e6cefe1135 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -1098,10 +1098,23 @@ void stage2_unmap_vm(struct kvm *kvm)
 void kvm_free_stage2_pgd(struct kvm_s2_mmu *mmu)
 {
 	struct kvm *kvm = kvm_s2_mmu_to_kvm(mmu);
-	struct kvm_pgtable *pgt = NULL;
+	struct kvm_pgtable *pgt;
 
 	write_lock(&kvm->mmu_lock);
 	pgt = mmu->pgt;
+	if (kvm_is_realm(kvm) &&
+	    (kvm_realm_state(kvm) != REALM_STATE_DEAD &&
+	     kvm_realm_state(kvm) != REALM_STATE_NONE)) {
+		write_unlock(&kvm->mmu_lock);
+		kvm_realm_destroy_rtts(kvm);
+
+		/*
+		 * The PGD pages can be reclaimed only after the realm (RD) is
+		 * destroyed. We call this again from kvm_destroy_realm() after
+		 * the RD is destroyed.
+		 */
+		return;
+	}
 	if (pgt) {
 		mmu->pgd_phys = 0;
 		mmu->pgt = NULL;
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index c2b13fecfd11..e57e8b7eafa9 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -17,6 +17,22 @@ static unsigned long rmm_feat_reg0;
 #define RMM_PAGE_SHIFT		12
 #define RMM_PAGE_SIZE		BIT(RMM_PAGE_SHIFT)
 
+#define RMM_RTT_BLOCK_LEVEL	2
+#define RMM_RTT_MAX_LEVEL	3
+
+/* See ARM64_HW_PGTABLE_LEVEL_SHIFT() */
+#define RMM_RTT_LEVEL_SHIFT(l)	\
+	((RMM_PAGE_SHIFT - 3) * (4 - (l)) + 3)
+#define RMM_L2_BLOCK_SIZE	BIT(RMM_RTT_LEVEL_SHIFT(2))
+
+static inline unsigned long rmi_rtt_level_mapsize(int level)
+{
+	if (WARN_ON(level > RMM_RTT_MAX_LEVEL))
+		return RMM_PAGE_SIZE;
+
+	return (1UL << RMM_RTT_LEVEL_SHIFT(level));
+}
+
 static int rmi_check_version(void)
 {
 	struct arm_smccc_res res;
@@ -61,6 +77,15 @@ u32 kvm_realm_ipa_limit(void)
 	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_S2SZ);
 }
 
+static int get_start_level(struct realm *realm)
+{
+	/*
+	 * Open coded version of 4 - stage2_pgtable_levels(ia_bits) but using
+	 * the RMM's page size rather than the host's.
+	 */
+	return 4 - ((realm->ia_bits - 8) / (RMM_PAGE_SHIFT - 3));
+}
+
 static int free_delegated_granule(phys_addr_t phys)
 {
 	if (WARN_ON(rmi_granule_undelegate(phys))) {
@@ -73,6 +98,131 @@ static int free_delegated_granule(phys_addr_t phys)
 	return 0;
 }
 
+static void free_rtt(phys_addr_t phys)
+{
+	if (free_delegated_granule(phys))
+		return;
+
+	kvm_account_pgtable_pages(phys_to_virt(phys), -1);
+}
+
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
+	if (WARN_ON(level > RMM_RTT_MAX_LEVEL))
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
+			if (WARN_ON(level == RMM_RTT_MAX_LEVEL))
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
+	WARN_ON(realm_tear_down_rtt_range(realm, 0, (1UL << ia_bits)));
+}
+
 void kvm_destroy_realm(struct kvm *kvm)
 {
 	struct realm *realm = &kvm->arch.realm;
@@ -83,6 +233,7 @@ void kvm_destroy_realm(struct kvm *kvm)
 	kvm_stage2_unmap_range(&kvm->arch.mmu, 0,
 			       BIT(realm->ia_bits - 1), true);
 	write_unlock(&kvm->mmu_lock);
+	kvm_realm_destroy_rtts(kvm);
 
 	if (realm->params) {
 		free_page((unsigned long)realm->params);

---

## [12] Steven Price — 2025-12-17
*Subject: [PATCH v12 11/46] arm64: RMI: Activate realm on first VCPU run*

When a VCPU migrates to another physical CPU check if this is the first
time the guest has run, and if so activate the realm.

Before the realm can be activated it must first be created, this is a
stub in this patch and will be filled in by a later patch.

Signed-off-by: Steven Price <steven.price@arm.com>
---
New patch for v12
---
 arch/arm64/include/asm/kvm_rmi.h |  1 +
 arch/arm64/kvm/arm.c             |  6 +++++
 arch/arm64/kvm/rmi.c             | 42 ++++++++++++++++++++++++++++++++
 3 files changed, 49 insertions(+)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index cb7350f8a01a..e4534af06d96 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -69,6 +69,7 @@ void kvm_init_rmi(void);
 u32 kvm_realm_ipa_limit(void);
 
 int kvm_init_realm_vm(struct kvm *kvm);
+int kvm_activate_realm(struct kvm *kvm);
 void kvm_destroy_realm(struct kvm *kvm);
 void kvm_realm_destroy_rtts(struct kvm *kvm);
 
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 941d1bec8e77..542df37b9e82 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -951,6 +951,12 @@ int kvm_arch_vcpu_run_pid_change(struct kvm_vcpu *vcpu)
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
index e57e8b7eafa9..98929382c365 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -223,6 +223,48 @@ void kvm_realm_destroy_rtts(struct kvm *kvm)
 	WARN_ON(realm_tear_down_rtt_range(realm, 0, (1UL << ia_bits)));
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
+	if (!kvm_is_realm(kvm))
+		return -ENXIO;
+
+	if (kvm_realm_state(kvm) == REALM_STATE_ACTIVE)
+		return 0;
+
+	guard(mutex)(&kvm->arch.config_lock);
+	/* Check again with the lock held */
+	if (kvm_realm_state(kvm) == REALM_STATE_ACTIVE)
+		return 0;
+
+	ret = realm_ensure_created(kvm);
+	if (ret)
+		return ret;
+
+	/* Mark state as dead in case we fail */
+	WRITE_ONCE(realm->state, REALM_STATE_DEAD);
+
+	if (!irqchip_in_kernel(kvm)) {
+		/* Userspace irqchip not yet supported with realms */
+		return -EOPNOTSUPP;
+	}
+
+	ret = rmi_realm_activate(virt_to_phys(realm->rd));
+	if (ret)
+		return -ENXIO;
+
+	WRITE_ONCE(realm->state, REALM_STATE_ACTIVE);
+	return 0;
+}
+
 void kvm_destroy_realm(struct kvm *kvm)
 {
 	struct realm *realm = &kvm->arch.realm;

---

## [13] Steven Price — 2025-12-17
*Subject: [PATCH v12 12/46] arm64: RMI: Allocate/free RECs to match vCPUs*

The RMM maintains a data structure known as the Realm Execution Context
(or REC). It is similar to struct kvm_vcpu and tracks the state of the
virtual CPUs. KVM must delegate memory and request the structures are
created when vCPUs are created, and suitably tear down on destruction.

RECs must also be supplied with addition pages - auxiliary (or AUX)
granules - for storing the larger registers state (e.g. for SVE). The
number of AUX granules for a REC depends on the parameters with which
the Realm was created - the RMM makes this information available via the
RMI_REC_AUX_COUNT call performed after creating the Realm Descriptor (RD).

Note that only some of register state for the REC can be set by KVM, the
rest is defined by the RMM (zeroed). The register state then cannot be
changed by KVM after the REC is created (except when the guest
explicitly requests this e.g. by performing a PSCI call).

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/include/asm/kvm_rmi.h     |  21 +++
 arch/arm64/kvm/arm.c                 |  10 +-
 arch/arm64/kvm/reset.c               |   1 +
 arch/arm64/kvm/rmi.c                 | 185 +++++++++++++++++++++++++++
 6 files changed, 219 insertions(+), 3 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_emulate.h b/arch/arm64/include/asm/kvm_emulate.h
index e7e9364ae118..f884bac43c06 100644
--- a/arch/arm64/include/asm/kvm_emulate.h
+++ b/arch/arm64/include/asm/kvm_emulate.h
@@ -716,7 +716,7 @@ static inline bool kvm_realm_is_created(struct kvm *kvm)
 
 static inline bool vcpu_is_rec(struct kvm_vcpu *vcpu)
 {
-	return false;
+	return kvm_is_realm(vcpu->kvm);
 }
 
 #endif /* __ARM64_KVM_EMULATE_H__ */
diff --git a/arch/arm64/include/asm/kvm_host.h b/arch/arm64/include/asm/kvm_host.h
index da913fee70b6..5a24227088c1 100644
--- a/arch/arm64/include/asm/kvm_host.h
+++ b/arch/arm64/include/asm/kvm_host.h
@@ -900,6 +900,9 @@ struct kvm_vcpu_arch {
 
 	/* Per-vcpu TLB for VNCR_EL2 -- NULL when !NV */
 	struct vncr_tlb	*vncr_tlb;
+
+	/* Realm meta data */
+	struct realm_rec rec;
 };
 
 /*
diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index e4534af06d96..dbb4b97d5d42 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -65,6 +65,26 @@ struct realm {
 	unsigned int ia_bits;
 };
 
+/**
+ * struct realm_rec - Additional per VCPU data for a Realm
+ *
+ * @mpidr: MPIDR (Multiprocessor Affinity Register) value to identify this VCPU
+ * @rec_page: Kernel VA of the RMM's private page for this REC
+ * @aux_pages: Additional pages private to the RMM for this REC
+ * @run: Kernel VA of the RmiRecRun structure shared with the RMM
+ */
+struct realm_rec {
+	unsigned long mpidr;
+	void *rec_page;
+	/*
+	 * REC_PARAMS_AUX_GRANULES is the maximum number of 4K granules that
+	 * the RMM can require. The array is sized to be large enough for the
+	 * maximum number of host sized pages that could be required.
+	 */
+	struct page *aux_pages[(REC_PARAMS_AUX_GRANULES * SZ_4K) >> PAGE_SHIFT];
+	struct rec_run *run;
+};
+
 void kvm_init_rmi(void);
 u32 kvm_realm_ipa_limit(void);
 
@@ -72,6 +92,7 @@ int kvm_init_realm_vm(struct kvm *kvm);
 int kvm_activate_realm(struct kvm *kvm);
 void kvm_destroy_realm(struct kvm *kvm);
 void kvm_realm_destroy_rtts(struct kvm *kvm);
+void kvm_destroy_rec(struct kvm_vcpu *vcpu);
 
 static inline bool kvm_realm_is_private_address(struct realm *realm,
 						unsigned long addr)
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 542df37b9e82..512d0ec9de60 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -529,6 +529,8 @@ int kvm_arch_vcpu_create(struct kvm_vcpu *vcpu)
 	/* Force users to call KVM_ARM_VCPU_INIT */
 	vcpu_clear_flag(vcpu, VCPU_INITIALIZED);
 
+	vcpu->arch.rec.mpidr = INVALID_HWID;
+
 	vcpu->arch.mmu_page_cache.gfp_zero = __GFP_ZERO;
 
 	/* Set up the timer */
@@ -1502,7 +1504,7 @@ int kvm_vm_ioctl_irq_line(struct kvm *kvm, struct kvm_irq_level *irq_level,
 	return -EINVAL;
 }
 
-static unsigned long system_supported_vcpu_features(void)
+static unsigned long system_supported_vcpu_features(struct kvm *kvm)
 {
 	unsigned long features = KVM_VCPU_VALID_FEATURES;
 
@@ -1540,7 +1542,7 @@ static int kvm_vcpu_init_check_features(struct kvm_vcpu *vcpu,
 			return -ENOENT;
 	}
 
-	if (features & ~system_supported_vcpu_features())
+	if (features & ~system_supported_vcpu_features(vcpu->kvm))
 		return -EINVAL;
 
 	/*
@@ -1562,6 +1564,10 @@ static int kvm_vcpu_init_check_features(struct kvm_vcpu *vcpu,
 	if (test_bit(KVM_ARM_VCPU_HAS_EL2, &features))
 		return -EINVAL;
 
+	/* Realms are incompatible with AArch32 */
+	if (vcpu_is_rec(vcpu))
+		return -EINVAL;
+
 	return 0;
 }
 
diff --git a/arch/arm64/kvm/reset.c b/arch/arm64/kvm/reset.c
index 959532422d3a..4bbf58892928 100644
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
index 98929382c365..27ecd7d9f757 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -229,9 +229,188 @@ static int realm_ensure_created(struct kvm *kvm)
 	return -ENXIO;
 }
 
+static void free_rec_aux(struct page **aux_pages,
+			 unsigned int num_aux)
+{
+	unsigned int i, j;
+	unsigned int page_count = 0;
+
+	for (i = 0; i < num_aux;) {
+		struct page *aux_page = aux_pages[page_count++];
+		phys_addr_t aux_page_phys = page_to_phys(aux_page);
+		bool should_free = true;
+
+		for (j = 0; j < PAGE_SIZE && i < num_aux; j += RMM_PAGE_SIZE) {
+			if (WARN_ON(rmi_granule_undelegate(aux_page_phys)))
+				should_free = false;
+			aux_page_phys += RMM_PAGE_SIZE;
+			i++;
+		}
+		/* Only free if all the undelegate calls were successful */
+		if (should_free)
+			__free_page(aux_page);
+	}
+}
+
+static int alloc_rec_aux(struct page **aux_pages,
+			 u64 *aux_phys_pages,
+			 unsigned int num_aux)
+{
+	struct page *aux_page;
+	int page_count = 0;
+	unsigned int i, j;
+	int ret;
+
+	for (i = 0; i < num_aux;) {
+		phys_addr_t aux_page_phys;
+
+		aux_page = alloc_page(GFP_KERNEL);
+		if (!aux_page) {
+			ret = -ENOMEM;
+			goto out_err;
+		}
+
+		aux_page_phys = page_to_phys(aux_page);
+		for (j = 0; j < PAGE_SIZE && i < num_aux; j += RMM_PAGE_SIZE) {
+			if (rmi_granule_delegate(aux_page_phys)) {
+				ret = -ENXIO;
+				goto err_undelegate;
+			}
+			aux_phys_pages[i++] = aux_page_phys;
+			aux_page_phys += RMM_PAGE_SIZE;
+		}
+		aux_pages[page_count++] = aux_page;
+	}
+
+	return 0;
+err_undelegate:
+	while (j > 0) {
+		j -= RMM_PAGE_SIZE;
+		i--;
+		if (WARN_ON(rmi_granule_undelegate(aux_phys_pages[i]))) {
+			/* Leak the page if the undelegate fails */
+			goto out_err;
+		}
+	}
+	__free_page(aux_page);
+out_err:
+	free_rec_aux(aux_pages, i);
+	return ret;
+}
+
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
+	if (!params || !rec->rec_page || !rec->run) {
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
+	if (rmi_granule_delegate(rec_page_phys)) {
+		r = -ENXIO;
+		goto out_free_pages;
+	}
+
+	r = alloc_rec_aux(rec->aux_pages, params->aux, realm->num_aux);
+	if (r)
+		goto out_undelegate_rmm_rec;
+
+	params->num_rec_aux = realm->num_aux;
+	params->mpidr = mpidr;
+
+	if (rmi_rec_create(virt_to_phys(realm->rd),
+			   rec_page_phys,
+			   virt_to_phys(params))) {
+		r = -ENXIO;
+		goto out_free_rec_aux;
+	}
+
+	rec->mpidr = mpidr;
+
+	free_page((unsigned long)params);
+	return 0;
+
+out_free_rec_aux:
+	free_rec_aux(rec->aux_pages, realm->num_aux);
+out_undelegate_rmm_rec:
+	if (WARN_ON(rmi_granule_undelegate(rec_page_phys)))
+		rec->rec_page = NULL;
+out_free_pages:
+	free_page((unsigned long)rec->run);
+	free_page((unsigned long)rec->rec_page);
+	free_page((unsigned long)params);
+	return r;
+}
+
+void kvm_destroy_rec(struct kvm_vcpu *vcpu)
+{
+	struct realm *realm = &vcpu->kvm->arch.realm;
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
+	/*
+	 * The REC and any AUX pages cannot be reclaimed until the REC is
+	 * destroyed. So if the REC destroy fails then the REC page and any AUX
+	 * pages will be leaked.
+	 */
+	if (WARN_ON(rmi_rec_destroy(rec_page_phys)))
+		return;
+
+	free_rec_aux(rec->aux_pages, realm->num_aux);
+
+	free_delegated_granule(rec_page_phys);
+}
+
 int kvm_activate_realm(struct kvm *kvm)
 {
 	struct realm *realm = &kvm->arch.realm;
+	struct kvm_vcpu *vcpu;
+	unsigned long i;
 	int ret;
 
 	if (!kvm_is_realm(kvm))
@@ -257,6 +436,12 @@ int kvm_activate_realm(struct kvm *kvm)
 		return -EOPNOTSUPP;
 	}
 
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

## [14] Steven Price — 2025-12-17
*Subject: [PATCH v12 13/46] KVM: arm64: vgic: Provide helper for number of list registers*

Currently the number of list registers available is stored in a global
(kvm_vgic_global_state.nr_lr). With Arm CCA the RMM is permitted to
reserve list registers for its own use and so the number of available
list registers can be fewer for a realm VM. Provide wrapper functions
to fetch the global in preparation for restricting nr_lr when dealing
with a realm VM.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes in v12:
 * Upstream changes mean that vcpu isn't available everywhere we need
   it, so update helpers to take vcpu.
 * Note that the VGIC handling will be reworked for the RMM 2.0 spec.
New patch for v6
---
 arch/arm64/kvm/vgic/vgic-v2.c |  6 +++---
 arch/arm64/kvm/vgic/vgic-v3.c |  8 ++++----
 arch/arm64/kvm/vgic/vgic.c    |  6 +++---
 arch/arm64/kvm/vgic/vgic.h    | 18 ++++++++++++------
 4 files changed, 22 insertions(+), 16 deletions(-)

diff --git a/arch/arm64/kvm/vgic/vgic-v2.c b/arch/arm64/kvm/vgic/vgic-v2.c
index 585491fbda80..990bf693f65d 100644
--- a/arch/arm64/kvm/vgic/vgic-v2.c
+++ b/arch/arm64/kvm/vgic/vgic-v2.c
@@ -34,11 +34,11 @@ void vgic_v2_configure_hcr(struct kvm_vcpu *vcpu,
 
 	cpuif->vgic_hcr = GICH_HCR_EN;
 
-	if (irqs_pending_outside_lrs(als))
+	if (irqs_pending_outside_lrs(als, vcpu))
 		cpuif->vgic_hcr |= GICH_HCR_NPIE;
-	if (irqs_active_outside_lrs(als))
+	if (irqs_active_outside_lrs(als, vcpu))
 		cpuif->vgic_hcr |= GICH_HCR_LRENPIE;
-	if (irqs_outside_lrs(als))
+	if (irqs_outside_lrs(als, vcpu))
 		cpuif->vgic_hcr |= GICH_HCR_UIE;
 
 	cpuif->vgic_hcr |= (cpuif->vgic_vmcr & GICH_VMCR_ENABLE_GRP0_MASK) ?
diff --git a/arch/arm64/kvm/vgic/vgic-v3.c b/arch/arm64/kvm/vgic/vgic-v3.c
index 1d6dd1b545bd..c9ff4f90c975 100644
--- a/arch/arm64/kvm/vgic/vgic-v3.c
+++ b/arch/arm64/kvm/vgic/vgic-v3.c
@@ -31,11 +31,11 @@ void vgic_v3_configure_hcr(struct kvm_vcpu *vcpu,
 
 	cpuif->vgic_hcr = ICH_HCR_EL2_En;
 
-	if (irqs_pending_outside_lrs(als))
+	if (irqs_pending_outside_lrs(als, vcpu))
 		cpuif->vgic_hcr |= ICH_HCR_EL2_NPIE;
-	if (irqs_active_outside_lrs(als))
+	if (irqs_active_outside_lrs(als, vcpu))
 		cpuif->vgic_hcr |= ICH_HCR_EL2_LRENPIE;
-	if (irqs_outside_lrs(als))
+	if (irqs_outside_lrs(als, vcpu))
 		cpuif->vgic_hcr |= ICH_HCR_EL2_UIE;
 
 	if (!als->nr_sgi)
@@ -60,7 +60,7 @@ void vgic_v3_configure_hcr(struct kvm_vcpu *vcpu,
 	 * can change behind our back without any warning...
 	 */
 	if (!cpus_have_final_cap(ARM64_HAS_ICH_HCR_EL2_TDIR) ||
-	    irqs_active_outside_lrs(als)		     ||
+	    irqs_active_outside_lrs(als, vcpu)		     ||
 	    atomic_read(&vcpu->kvm->arch.vgic.active_spis))
 		cpuif->vgic_hcr |= ICH_HCR_EL2_TDIR;
 }
diff --git a/arch/arm64/kvm/vgic/vgic.c b/arch/arm64/kvm/vgic/vgic.c
index 430aa98888fd..2fdcef3d28d1 100644
--- a/arch/arm64/kvm/vgic/vgic.c
+++ b/arch/arm64/kvm/vgic/vgic.c
@@ -957,7 +957,7 @@ static void vgic_flush_lr_state(struct kvm_vcpu *vcpu)
 
 	summarize_ap_list(vcpu, &als);
 
-	if (irqs_outside_lrs(&als))
+	if (irqs_outside_lrs(&als, vcpu))
 		vgic_sort_ap_list(vcpu);
 
 	list_for_each_entry(irq, &vgic_cpu->ap_list_head, ap_list) {
@@ -967,12 +967,12 @@ static void vgic_flush_lr_state(struct kvm_vcpu *vcpu)
 			}
 		}
 
-		if (count == kvm_vgic_global_state.nr_lr)
+		if (count == kvm_vcpu_vgic_nr_lr(vcpu))
 			break;
 	}
 
 	/* Nuke remaining LRs */
-	for (int i = count ; i < kvm_vgic_global_state.nr_lr; i++)
+	for (int i = count ; i < kvm_vcpu_vgic_nr_lr(vcpu); i++)
 		vgic_clear_lr(vcpu, i);
 
 	if (!static_branch_unlikely(&kvm_vgic_global_state.gicv3_cpuif)) {
diff --git a/arch/arm64/kvm/vgic/vgic.h b/arch/arm64/kvm/vgic/vgic.h
index 5f0fc96b4dc2..55a1142efc6f 100644
--- a/arch/arm64/kvm/vgic/vgic.h
+++ b/arch/arm64/kvm/vgic/vgic.h
@@ -7,6 +7,7 @@
 
 #include <linux/irqchip/arm-gic-common.h>
 #include <asm/kvm_mmu.h>
+#include <asm/kvm_rmi.h>
 
 #define PRODUCT_ID_KVM		0x4b	/* ASCII code K */
 #define IMPLEMENTER_ARM		0x43b
@@ -242,14 +243,19 @@ struct ap_list_summary {
 	unsigned int	nr_sgi;		/* any SGI */
 };
 
-#define irqs_outside_lrs(s)						\
-	 (((s)->nr_pend + (s)->nr_act) > kvm_vgic_global_state.nr_lr)
+static inline int kvm_vcpu_vgic_nr_lr(struct kvm_vcpu *vcpu)
+{
+	return kvm_vgic_global_state.nr_lr;
+}
+
+#define irqs_outside_lrs(s, vcpu)					\
+	 (((s)->nr_pend + (s)->nr_act) > kvm_vcpu_vgic_nr_lr(vcpu))
 
-#define irqs_pending_outside_lrs(s)			\
-	((s)->nr_pend > kvm_vgic_global_state.nr_lr)
+#define irqs_pending_outside_lrs(s, vcpu)			\
+	((s)->nr_pend > kvm_vcpu_vgic_nr_lr(vcpu))
 
-#define irqs_active_outside_lrs(s)		\
-	((s)->nr_act &&	irqs_outside_lrs(s))
+#define irqs_active_outside_lrs(s, vcpu)		\
+	((s)->nr_act &&	irqs_outside_lrs(s, vcpu))
 
 int vgic_v3_parse_attr(struct kvm_device *dev, struct kvm_device_attr *attr,
 		       struct vgic_reg_attr *reg_attr);

---

## [15] Steven Price — 2025-12-17
*Subject: [PATCH v12 14/46] arm64: RMI: Support for the VGIC in realms*

The RMM provides emulation of a VGIC to the realm guest but delegates
much of the handling to the host. Implement support in KVM for
saving/restoring state to/from the REC structure.

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/include/asm/kvm_rmi.h |  1 +
 arch/arm64/kvm/arm.c             | 11 +++++--
 arch/arm64/kvm/rmi.c             |  5 ++++
 arch/arm64/kvm/vgic/vgic-init.c  |  2 +-
 arch/arm64/kvm/vgic/vgic-v3.c    |  6 ++--
 arch/arm64/kvm/vgic/vgic.c       | 49 +++++++++++++++++++++++++++++---
 arch/arm64/kvm/vgic/vgic.h       |  2 ++
 7 files changed, 65 insertions(+), 11 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index dbb4b97d5d42..6190d75cc615 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -87,6 +87,7 @@ struct realm_rec {
 
 void kvm_init_rmi(void);
 u32 kvm_realm_ipa_limit(void);
+u32 kvm_realm_vgic_nr_lr(void);
 
 int kvm_init_realm_vm(struct kvm *kvm);
 int kvm_activate_realm(struct kvm *kvm);
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 512d0ec9de60..66f23b8b3144 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -723,19 +723,24 @@ void kvm_arch_vcpu_put(struct kvm_vcpu *vcpu)
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
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 27ecd7d9f757..275b266c6614 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -77,6 +77,11 @@ u32 kvm_realm_ipa_limit(void)
 	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_S2SZ);
 }
 
+u32 kvm_realm_vgic_nr_lr(void)
+{
+	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_GICV3_NUM_LRS);
+}
+
 static int get_start_level(struct realm *realm)
 {
 	/*
diff --git a/arch/arm64/kvm/vgic/vgic-init.c b/arch/arm64/kvm/vgic/vgic-init.c
index dc9f9db31026..bb1a876bf298 100644
--- a/arch/arm64/kvm/vgic/vgic-init.c
+++ b/arch/arm64/kvm/vgic/vgic-init.c
@@ -82,7 +82,7 @@ int kvm_vgic_create(struct kvm *kvm, u32 type)
 	 * the proper checks already.
 	 */
 	if (type == KVM_DEV_TYPE_ARM_VGIC_V2 &&
-		!kvm_vgic_global_state.can_emulate_gicv2)
+	    (!kvm_vgic_global_state.can_emulate_gicv2 || kvm_is_realm(kvm)))
 		return -ENODEV;
 
 	/*
diff --git a/arch/arm64/kvm/vgic/vgic-v3.c b/arch/arm64/kvm/vgic/vgic-v3.c
index c9ff4f90c975..f01dd30330e3 100644
--- a/arch/arm64/kvm/vgic/vgic-v3.c
+++ b/arch/arm64/kvm/vgic/vgic-v3.c
@@ -982,10 +982,10 @@ void vgic_v3_load(struct kvm_vcpu *vcpu)
 		return;
 	}
 
-	if (likely(!is_protected_kvm_enabled()))
+	if (likely(!is_protected_kvm_enabled()) && !vcpu_is_rec(vcpu))
 		kvm_call_hyp(__vgic_v3_restore_vmcr_aprs, cpu_if);
 
-	if (has_vhe())
+	if (has_vhe() && !vcpu_is_rec(vcpu))
 		__vgic_v3_activate_traps(cpu_if);
 
 	WARN_ON(vgic_v4_load(vcpu));
@@ -1004,6 +1004,6 @@ void vgic_v3_put(struct kvm_vcpu *vcpu)
 		kvm_call_hyp(__vgic_v3_save_aprs, cpu_if);
 	WARN_ON(vgic_v4_put(vcpu));
 
-	if (has_vhe())
+	if (has_vhe() && !vcpu_is_rec(vcpu))
 		__vgic_v3_deactivate_traps(cpu_if);
 }
diff --git a/arch/arm64/kvm/vgic/vgic.c b/arch/arm64/kvm/vgic/vgic.c
index 2fdcef3d28d1..b317b2a9815f 100644
--- a/arch/arm64/kvm/vgic/vgic.c
+++ b/arch/arm64/kvm/vgic/vgic.c
@@ -10,6 +10,7 @@
 #include <linux/list_sort.h>
 #include <linux/nospec.h>
 
+#include <asm/kvm_emulate.h>
 #include <asm/kvm_hyp.h>
 
 #include "vgic.h"
@@ -994,10 +995,26 @@ static inline bool can_access_vgic_from_kernel(void)
 	return !static_branch_unlikely(&kvm_vgic_global_state.gicv3_cpuif) || has_vhe();
 }
 
+static inline void vgic_rmm_save_state(struct kvm_vcpu *vcpu)
+{
+	struct vgic_v3_cpu_if *cpu_if = &vcpu->arch.vgic_cpu.vgic_v3;
+	int i;
+
+	for (i = 0; i < kvm_vcpu_vgic_nr_lr(vcpu); i++) {
+		cpu_if->vgic_lr[i] = vcpu->arch.rec.run->exit.gicv3_lrs[i];
+		vcpu->arch.rec.run->enter.gicv3_lrs[i] = 0;
+	}
+
+	cpu_if->vgic_hcr = vcpu->arch.rec.run->exit.gicv3_hcr;
+	cpu_if->vgic_vmcr = vcpu->arch.rec.run->exit.gicv3_vmcr;
+}
+
 static inline void vgic_save_state(struct kvm_vcpu *vcpu)
 {
 	if (!static_branch_unlikely(&kvm_vgic_global_state.gicv3_cpuif))
 		vgic_v2_save_state(vcpu);
+	else if (vcpu_is_rec(vcpu))
+		vgic_rmm_save_state(vcpu);
 	else
 		__vgic_v3_save_state(&vcpu->arch.vgic_cpu.vgic_v3);
 }
@@ -1032,10 +1049,30 @@ void kvm_vgic_process_async_update(struct kvm_vcpu *vcpu)
 	local_irq_restore(flags);
 }
 
+static inline void vgic_rmm_restore_state(struct kvm_vcpu *vcpu)
+{
+	struct vgic_v3_cpu_if *cpu_if = &vcpu->arch.vgic_cpu.vgic_v3;
+	int i;
+
+	for (i = 0; i < cpu_if->used_lrs; i++) {
+		vcpu->arch.rec.run->enter.gicv3_lrs[i] = cpu_if->vgic_lr[i];
+		/*
+		 * Also populate the rec.run->exit copies so that a late
+		 * decision to back out from entering the realm doesn't cause
+		 * the state to be lost
+		 */
+		vcpu->arch.rec.run->exit.gicv3_lrs[i] = cpu_if->vgic_lr[i];
+	}
+
+	vcpu->arch.rec.run->enter.gicv3_hcr = cpu_if->vgic_hcr & RMI_PERMITTED_GICV3_HCR_BITS;
+}
+
 static inline void vgic_restore_state(struct kvm_vcpu *vcpu)
 {
 	if (!static_branch_unlikely(&kvm_vgic_global_state.gicv3_cpuif))
 		vgic_v2_restore_state(vcpu);
+	else if (vcpu_is_rec(vcpu))
+		vgic_rmm_restore_state(vcpu);
 	else
 		__vgic_v3_restore_state(&vcpu->arch.vgic_cpu.vgic_v3);
 }
@@ -1088,8 +1125,10 @@ void kvm_vgic_flush_hwstate(struct kvm_vcpu *vcpu)
 
 void kvm_vgic_load(struct kvm_vcpu *vcpu)
 {
-	if (unlikely(!irqchip_in_kernel(vcpu->kvm) || !vgic_initialized(vcpu->kvm))) {
-		if (has_vhe() && static_branch_unlikely(&kvm_vgic_global_state.gicv3_cpuif))
+	if (unlikely(!irqchip_in_kernel(vcpu->kvm) ||
+		     !vgic_initialized(vcpu->kvm))) {
+		if (has_vhe() && !vcpu_is_rec(vcpu) &&
+		    static_branch_unlikely(&kvm_vgic_global_state.gicv3_cpuif))
 			__vgic_v3_activate_traps(&vcpu->arch.vgic_cpu.vgic_v3);
 		return;
 	}
@@ -1102,8 +1141,10 @@ void kvm_vgic_load(struct kvm_vcpu *vcpu)
 
 void kvm_vgic_put(struct kvm_vcpu *vcpu)
 {
-	if (unlikely(!irqchip_in_kernel(vcpu->kvm) || !vgic_initialized(vcpu->kvm))) {
-		if (has_vhe() && static_branch_unlikely(&kvm_vgic_global_state.gicv3_cpuif))
+	if (unlikely(!irqchip_in_kernel(vcpu->kvm) ||
+		     !vgic_initialized(vcpu->kvm))) {
+		if (has_vhe() && !vcpu_is_rec(vcpu) &&
+		    static_branch_unlikely(&kvm_vgic_global_state.gicv3_cpuif))
 			__vgic_v3_deactivate_traps(&vcpu->arch.vgic_cpu.vgic_v3);
 		return;
 	}
diff --git a/arch/arm64/kvm/vgic/vgic.h b/arch/arm64/kvm/vgic/vgic.h
index 55a1142efc6f..282a9701dea6 100644
--- a/arch/arm64/kvm/vgic/vgic.h
+++ b/arch/arm64/kvm/vgic/vgic.h
@@ -245,6 +245,8 @@ struct ap_list_summary {
 
 static inline int kvm_vcpu_vgic_nr_lr(struct kvm_vcpu *vcpu)
 {
+	if (unlikely(vcpu_is_rec(vcpu)))
+		return kvm_realm_vgic_nr_lr();
 	return kvm_vgic_global_state.nr_lr;
 }

---

## [16] Steven Price — 2025-12-17
*Subject: [PATCH v12 15/46] KVM: arm64: Support timers in realm RECs*

The RMM keeps track of the timer while the realm REC is running, but on
exit to the normal world KVM is responsible for handling the timers.

A later patch adds the support for propagating the timer values from the
exit data structure and calling kvm_realm_timers_update().

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/kvm/arch_timer.c  | 37 ++++++++++++++++++++++++++++++++++--
 include/kvm/arm_arch_timer.h |  2 ++
 2 files changed, 37 insertions(+), 2 deletions(-)

diff --git a/arch/arm64/kvm/arch_timer.c b/arch/arm64/kvm/arch_timer.c
index 99a07972068d..99308bde2a05 100644
--- a/arch/arm64/kvm/arch_timer.c
+++ b/arch/arm64/kvm/arch_timer.c
@@ -453,6 +453,21 @@ static void kvm_timer_update_irq(struct kvm_vcpu *vcpu, bool new_level,
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
@@ -1056,7 +1071,9 @@ static void timer_context_init(struct kvm_vcpu *vcpu, int timerid)
 
 	ctxt->timer_id = timerid;
 
-	if (timerid == TIMER_VTIMER)
+	if (kvm_is_realm(vcpu->kvm))
+		ctxt->offset.vm_offset = NULL;
+	else if (timerid == TIMER_VTIMER)
 		ctxt->offset.vm_offset = &kvm->arch.timer_data.voffset;
 	else
 		ctxt->offset.vm_offset = &kvm->arch.timer_data.poffset;
@@ -1078,13 +1095,19 @@ static void timer_context_init(struct kvm_vcpu *vcpu, int timerid)
 void kvm_timer_vcpu_init(struct kvm_vcpu *vcpu)
 {
 	struct arch_timer_cpu *timer = vcpu_timer(vcpu);
+	u64 cntvoff;
 
 	for (int i = 0; i < NR_KVM_TIMERS; i++)
 		timer_context_init(vcpu, i);
 
+	if (kvm_is_realm(vcpu->kvm))
+		cntvoff = 0;
+	else
+		cntvoff = kvm_phys_timer_read();
+
 	/* Synchronize offsets across timers of a VM if not already provided */
 	if (!test_bit(KVM_ARCH_FLAG_VM_COUNTER_OFFSET, &vcpu->kvm->arch.flags)) {
-		timer_set_offset(vcpu_vtimer(vcpu), kvm_phys_timer_read());
+		timer_set_offset(vcpu_vtimer(vcpu), cntvoff);
 		timer_set_offset(vcpu_ptimer(vcpu), 0);
 	}
 
@@ -1556,6 +1579,13 @@ int kvm_timer_enable(struct kvm_vcpu *vcpu)
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
 
 	ret = kvm_vgic_map_phys_irq(vcpu,
@@ -1687,6 +1717,9 @@ int kvm_vm_ioctl_set_counter_offset(struct kvm *kvm,
 	if (offset->reserved)
 		return -EINVAL;
 
+	if (kvm_is_realm(kvm))
+		return -EINVAL;
+
 	mutex_lock(&kvm->lock);
 
 	if (!kvm_trylock_all_vcpus(kvm)) {
diff --git a/include/kvm/arm_arch_timer.h b/include/kvm/arm_arch_timer.h
index 7310841f4512..bab0daafc6b1 100644
--- a/include/kvm/arm_arch_timer.h
+++ b/include/kvm/arm_arch_timer.h
@@ -111,6 +111,8 @@ int kvm_arm_timer_set_attr(struct kvm_vcpu *vcpu, struct kvm_device_attr *attr);
 int kvm_arm_timer_get_attr(struct kvm_vcpu *vcpu, struct kvm_device_attr *attr);
 int kvm_arm_timer_has_attr(struct kvm_vcpu *vcpu, struct kvm_device_attr *attr);
 
+void kvm_realm_timers_update(struct kvm_vcpu *vcpu);
+
 u64 kvm_phys_timer_read(void);
 
 void kvm_timer_vcpu_load(struct kvm_vcpu *vcpu);

---

## [17] Steven Price — 2025-12-17
*Subject: [PATCH v12 16/46] arm64: RMI: Handle realm enter/exit*

Entering a realm is done using a SMC call to the RMM. On exit the
exit-codes need to be handled slightly differently to the normal KVM
path so define our own functions for realm enter/exit and hook them
in if the guest is a realm guest.

Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
---
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
 arch/arm64/kvm/arm.c             |  22 +++-
 arch/arm64/kvm/rmi-exit.c        | 178 +++++++++++++++++++++++++++++++
 arch/arm64/kvm/rmi.c             |  38 +++++++
 5 files changed, 239 insertions(+), 5 deletions(-)
 create mode 100644 arch/arm64/kvm/rmi-exit.c

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index 6190d75cc615..faf0af563210 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -95,6 +95,10 @@ void kvm_destroy_realm(struct kvm *kvm);
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
index e17c4077d8e7..4b103bcbe760 100644
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
index 66f23b8b3144..7927181887cf 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -1264,6 +1264,9 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 		if (ret > 0)
 			ret = check_vcpu_requests(vcpu);
 
+		if (ret > 0 && vcpu_is_rec(vcpu))
+			ret = kvm_rec_pre_enter(vcpu);
+
 		/*
 		 * Preparing the interrupts to be injected also
 		 * involves poking the GIC, which must be done in a
@@ -1311,7 +1314,10 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 		trace_kvm_entry(*vcpu_pc(vcpu));
 		guest_timing_enter_irqoff();
 
-		ret = kvm_arm_vcpu_enter_exit(vcpu);
+		if (vcpu_is_rec(vcpu))
+			ret = kvm_rec_enter(vcpu);
+		else
+			ret = kvm_arm_vcpu_enter_exit(vcpu);
 
 		vcpu->mode = OUTSIDE_GUEST_MODE;
 		vcpu->stat.exits++;
@@ -1369,8 +1375,13 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 
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
 
@@ -1395,7 +1406,10 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
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
index 000000000000..f5701153dec0
--- /dev/null
+++ b/arch/arm64/kvm/rmi-exit.c
@@ -0,0 +1,178 @@
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
+	bool is_write = !(esr & 1);
+	int ret;
+
+	if (is_write)
+		vcpu_set_reg(vcpu, rt, rec->run->exit.gprs[0]);
+
+	ret = kvm_handle_sys_reg(vcpu);
+	if (!is_write)
+		rec->run->enter.gprs[0] = vcpu_get_reg(vcpu, rt);
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
+	if (status == RMI_ERROR_REALM && index == 1) {
+		vcpu->run->exit_reason = KVM_EXIT_SHUTDOWN;
+		return 0;
+	}
+
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
index 275b266c6614..215eb4f4fc47 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -234,6 +234,44 @@ static int realm_ensure_created(struct kvm *kvm)
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
+	case RMI_EXIT_PSCI:
+		for (int i = 0; i < REC_RUN_GPRS; i++)
+			rec->run->enter.gprs[i] = vcpu_get_reg(vcpu, i);
+		break;
+	}
+
+	return 1;
+}
+
+int kvm_rec_enter(struct kvm_vcpu *vcpu)
+{
+	struct realm_rec *rec = &vcpu->arch.rec;
+
+	return rmi_rec_enter(virt_to_phys(rec->rec_page),
+			     virt_to_phys(rec->run));
+}
+
 static void free_rec_aux(struct page **aux_pages,
 			 unsigned int num_aux)
 {

---

## [18] Steven Price — 2025-12-17
*Subject: [PATCH v12 17/46] arm64: RMI: Handle RMI_EXIT_RIPAS_CHANGE*

The guest can request that a region of it's protected address space is
switched between RIPAS_RAM and RIPAS_EMPTY (and back) using
RSI_IPA_STATE_SET. This causes a guest exit with the
RMI_EXIT_RIPAS_CHANGE code. We treat this as a request to convert a
protected region to unprotected (or back), exiting to the VMM to make
the necessary changes to the guest_memfd and memslot mappings. On the
next entry the RIPAS changes are committed by making RMI_RTT_SET_RIPAS
calls.

The VMM may wish to reject the RIPAS change requested by the guest. For
now it can only do with by no longer scheduling the VCPU as we don't
currently have a usecase for returning that rejection to the guest, but
by postponing the RMI_RTT_SET_RIPAS changes to entry we leave the door
open for adding a new ioctl in the future for this purpose.

There's a FIXME for the case where the RMM rejects a RIPAS change when
(a portion of) the region. The current RMM API makes this difficult to
handle efficiently, but it should be fixed in a later version of the
spec.

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/kvm/rmi.c             | 459 +++++++++++++++++++++++++++++++
 3 files changed, 470 insertions(+), 3 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index faf0af563210..8a862fc1a99d 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -99,6 +99,12 @@ int kvm_rec_enter(struct kvm_vcpu *vcpu);
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
index 68e6cefe1135..cac3d7b73b3d 100644
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
@@ -340,7 +341,7 @@ static void __unmap_stage2_range(struct kvm_s2_mmu *mmu, phys_addr_t start, u64
 void kvm_stage2_unmap_range(struct kvm_s2_mmu *mmu, phys_addr_t start,
 			    u64 size, bool may_block)
 {
-	__unmap_stage2_range(mmu, start, size, may_block);
+	__unmap_stage2_range(mmu, start, size, may_block, false);
 }
 
 void kvm_stage2_flush_range(struct kvm_s2_mmu *mmu, phys_addr_t addr, phys_addr_t end)
@@ -2230,7 +2231,8 @@ bool kvm_unmap_gfn_range(struct kvm *kvm, struct kvm_gfn_range *range)
 
 	__unmap_stage2_range(&kvm->arch.mmu, range->start << PAGE_SHIFT,
 			     (range->end - range->start) << PAGE_SHIFT,
-			     range->may_block);
+			     range->may_block,
+			     !(range->attr_filter & KVM_FILTER_PRIVATE));
 
 	kvm_nested_s2_unmap(kvm, range->may_block);
 	return false;
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 215eb4f4fc47..fe15b400091c 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -91,6 +91,59 @@ static int get_start_level(struct realm *realm)
 	return 4 - ((realm->ia_bits - 8) / (RMM_PAGE_SHIFT - 3));
 }
 
+static int find_map_level(struct realm *realm,
+			  unsigned long start,
+			  unsigned long end)
+{
+	int level = RMM_RTT_MAX_LEVEL;
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
+	if (rmi_granule_delegate(phys)) {
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
 static int free_delegated_granule(phys_addr_t phys)
 {
 	if (WARN_ON(rmi_granule_undelegate(phys))) {
@@ -111,6 +164,32 @@ static void free_rtt(phys_addr_t phys)
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
 static int realm_rtt_destroy(struct realm *realm, unsigned long addr,
 			     int level, phys_addr_t *rtt_granule,
 			     unsigned long *next_addr)
@@ -126,6 +205,38 @@ static int realm_rtt_destroy(struct realm *realm, unsigned long addr,
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
@@ -220,6 +331,62 @@ static int realm_tear_down_rtt_range(struct realm *realm,
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
+	if (WARN_ON(level > RMM_RTT_MAX_LEVEL))
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
+			if (level == RMM_RTT_MAX_LEVEL ||
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
@@ -228,12 +395,301 @@ void kvm_realm_destroy_rtts(struct kvm *kvm)
 	WARN_ON(realm_tear_down_rtt_range(realm, 0, (1UL << ia_bits)));
 }
 
+static int realm_destroy_private_granule(struct realm *realm,
+					 unsigned long ipa,
+					 unsigned long *next_addr)
+{
+	unsigned long rd = virt_to_phys(realm->rd);
+	unsigned long phy_addr;
+	phys_addr_t rtt;
+	int ret;
+
+retry:
+	ret = rmi_data_destroy(rd, ipa, &phy_addr, next_addr);
+	if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
+		if (*next_addr > ipa)
+			return 0; /* UNASSIGNED */
+		rtt = alloc_rtt(NULL);
+		if (WARN_ON(rtt == PHYS_ADDR_MAX))
+			return -ENOMEM;
+		/*
+		 * ASSIGNED - ipa is mapped as a block, so split. The index
+		 * from the return code should be 2 otherwise it appears
+		 * there's a huge page bigger than KVM currently supports
+		 */
+		WARN_ON(RMI_RETURN_INDEX(ret) != 2);
+		ret = realm_rtt_create(realm, ipa, 3, rtt);
+		if (WARN_ON(ret)) {
+			free_rtt(rtt);
+			return -ENXIO;
+		}
+		goto retry;
+	} else if (WARN_ON(ret)) {
+		return -ENXIO;
+	}
+
+	ret = rmi_granule_undelegate(phy_addr);
+	if (WARN_ON(ret))
+		return -ENXIO;
+
+	return 0;
+}
+
+static void realm_unmap_shared_range(struct kvm *kvm,
+				     int level,
+				     unsigned long start,
+				     unsigned long end,
+				     bool may_block)
+{
+	struct realm *realm = &kvm->arch.realm;
+	unsigned long rd = virt_to_phys(realm->rd);
+	ssize_t map_size = rmi_rtt_level_mapsize(level);
+	unsigned long next_addr, addr;
+	unsigned long shared_bit = BIT(realm->ia_bits - 1);
+
+	if (WARN_ON(level > RMM_RTT_MAX_LEVEL))
+		return;
+
+	start |= shared_bit;
+	end |= shared_bit;
+
+	for (addr = start; addr < end; addr = next_addr) {
+		unsigned long align_addr = ALIGN(addr, map_size);
+		int ret;
+
+		next_addr = ALIGN(addr + 1, map_size);
+
+		if (align_addr != addr || next_addr > end) {
+			/* Need to recurse deeper */
+			if (addr < align_addr)
+				next_addr = align_addr;
+			realm_unmap_shared_range(kvm, level + 1, addr,
+						 min(next_addr, end),
+						 may_block);
+			continue;
+		}
+
+		ret = rmi_rtt_unmap_unprotected(rd, addr, level, &next_addr);
+		switch (RMI_RETURN_STATUS(ret)) {
+		case RMI_SUCCESS:
+			break;
+		case RMI_ERROR_RTT:
+			if (next_addr == addr) {
+				/*
+				 * There's a mapping here, but it's not a block
+				 * mapping, so reset next_addr to the next block
+				 * boundary and recurse to clear out the pages
+				 * one level deeper.
+				 */
+				next_addr = ALIGN(addr + 1, map_size);
+				realm_unmap_shared_range(kvm, level + 1, addr,
+							 next_addr,
+							 may_block);
+			}
+			break;
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
+static int realm_unmap_private_page(struct realm *realm,
+				    unsigned long ipa,
+				    unsigned long *next_addr)
+{
+	unsigned long end = ALIGN(ipa + 1, PAGE_SIZE);
+	unsigned long addr;
+	int ret;
+
+	for (addr = ipa; addr < end; addr = *next_addr) {
+		ret = realm_destroy_private_granule(realm, addr, next_addr);
+		if (ret)
+			return ret;
+	}
+
+	return 0;
+}
+
+static void realm_unmap_private_range(struct kvm *kvm,
+				      unsigned long start,
+				      unsigned long end,
+				      bool may_block)
+{
+	struct realm *realm = &kvm->arch.realm;
+	unsigned long next_addr, addr;
+	int ret;
+
+	for (addr = start; addr < end; addr = next_addr) {
+		ret = realm_unmap_private_page(realm, addr, &next_addr);
+
+		if (ret)
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
+	end = min(BIT(realm->ia_bits - 1), end);
+
+	if (!kvm_realm_is_created(kvm))
+		return;
+
+	realm_unmap_shared_range(kvm, find_map_level(realm, start, end),
+				 start, end, may_block);
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
+			if (err_level >= level) {
+				/* FIXME: Ugly hack to skip regions which are
+				 * already RIPAS_RAM
+				 */
+				ipa += PAGE_SIZE;
+				break;
+				return -EINVAL;
+			}
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
@@ -259,6 +715,9 @@ int kvm_rec_pre_enter(struct kvm_vcpu *vcpu)
 		for (int i = 0; i < REC_RUN_GPRS; i++)
 			rec->run->enter.gprs[i] = vcpu_get_reg(vcpu, i);
 		break;
+	case RMI_EXIT_RIPAS_CHANGE:
+		kvm_complete_ripas_change(vcpu);
+		break;
 	}
 
 	return 1;

---

## [19] Steven Price — 2025-12-17
*Subject: [PATCH v12 18/46] KVM: arm64: Handle realm MMIO emulation*

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
index dfcd66c65517..5e00f7a69bcc 100644
--- a/arch/arm64/kvm/inject_fault.c
+++ b/arch/arm64/kvm/inject_fault.c
@@ -224,7 +224,9 @@ static void inject_abt32(struct kvm_vcpu *vcpu, bool is_pabt, u32 addr)
 
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
index 54f9358c9e0e..d7ad291b5357 100644
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
@@ -164,14 +172,14 @@ int io_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa)
 	 * No valid syndrome? Ask userspace for help if it has
 	 * volunteered to do so, and bail out otherwise.
 	 *
-	 * In the protected VM case, there isn't much userspace can do
+	 * In the protected/realm VM case, there isn't much userspace can do
 	 * though, so directly deliver an exception to the guest.
 	 */
 	if (!kvm_vcpu_dabt_isvalid(vcpu)) {
 		trace_kvm_mmio_nisv(*vcpu_pc(vcpu), kvm_vcpu_get_esr(vcpu),
 				    kvm_vcpu_get_hfar(vcpu), fault_ipa);
 
-		if (vcpu_is_protected(vcpu))
+		if (vcpu_is_protected(vcpu) || vcpu_is_rec(vcpu))
 			return kvm_inject_sea_dabt(vcpu, kvm_vcpu_get_hfar(vcpu));
 
 		if (test_bit(KVM_ARCH_FLAG_RETURN_NISV_IO_ABORT_TO_USER,
diff --git a/arch/arm64/kvm/rmi-exit.c b/arch/arm64/kvm/rmi-exit.c
index f5701153dec0..b4843f094615 100644
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

## [20] Steven Price — 2025-12-17
*Subject: [PATCH v12 19/46] KVM: arm64: Expose support for private memory*

Select KVM_GENERIC_MEMORY_ATTRIBUTES and provide the necessary support
functions.

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/include/asm/kvm_host.h |  2 ++
 arch/arm64/kvm/Kconfig            |  1 +
 arch/arm64/kvm/mmu.c              | 24 ++++++++++++++++++++++++
 3 files changed, 27 insertions(+)

diff --git a/arch/arm64/include/asm/kvm_host.h b/arch/arm64/include/asm/kvm_host.h
index 5a24227088c1..7590d86c78a5 100644
--- a/arch/arm64/include/asm/kvm_host.h
+++ b/arch/arm64/include/asm/kvm_host.h
@@ -1462,6 +1462,8 @@ struct kvm *kvm_arch_alloc_vm(void);
 
 #define vcpu_is_protected(vcpu)		kvm_vm_is_protected((vcpu)->kvm)
 
+#define kvm_arch_has_private_mem(kvm) ((kvm)->arch.is_realm)
+
 int kvm_arm_vcpu_finalize(struct kvm_vcpu *vcpu, int feature);
 bool kvm_arm_vcpu_is_finalized(struct kvm_vcpu *vcpu);
 
diff --git a/arch/arm64/kvm/Kconfig b/arch/arm64/kvm/Kconfig
index 4f803fd1c99a..1cac6dfc0972 100644
--- a/arch/arm64/kvm/Kconfig
+++ b/arch/arm64/kvm/Kconfig
@@ -38,6 +38,7 @@ menuconfig KVM
 	select SCHED_INFO
 	select GUEST_PERF_EVENTS if PERF_EVENTS
 	select KVM_GUEST_MEMFD
+	select KVM_GENERIC_MEMORY_ATTRIBUTES
 	help
 	  Support hosting virtualized guest machines.
 
diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index cac3d7b73b3d..f2ac01c1de04 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -2503,6 +2503,30 @@ int kvm_arch_prepare_memory_region(struct kvm *kvm,
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

## [21] Steven Price — 2025-12-17
*Subject: [PATCH v12 20/46] arm64: RMI: Allow populating initial contents*

The VMM needs to populate the realm with some data before starting (e.g.
a kernel and initrd). This is measured by the RMM and used as part of
the attestation later on.

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/include/asm/kvm_rmi.h |   4 +
 arch/arm64/kvm/Kconfig           |   1 +
 arch/arm64/kvm/arm.c             |   9 ++
 arch/arm64/kvm/rmi.c             | 175 +++++++++++++++++++++++++++++++
 4 files changed, 189 insertions(+)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index 8a862fc1a99d..b5e36344975c 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -99,6 +99,10 @@ int kvm_rec_enter(struct kvm_vcpu *vcpu);
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
index 1cac6dfc0972..b495dfd3a8b4 100644
--- a/arch/arm64/kvm/Kconfig
+++ b/arch/arm64/kvm/Kconfig
@@ -39,6 +39,7 @@ menuconfig KVM
 	select GUEST_PERF_EVENTS if PERF_EVENTS
 	select KVM_GUEST_MEMFD
 	select KVM_GENERIC_MEMORY_ATTRIBUTES
+	select HAVE_KVM_ARCH_GMEM_POPULATE
 	help
 	  Support hosting virtualized guest machines.
 
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 7927181887cf..0a06ed9d1a64 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -2037,6 +2037,15 @@ int kvm_arch_vm_ioctl(struct file *filp, unsigned int ioctl, unsigned long arg)
 			return -EFAULT;
 		return kvm_vm_ioctl_get_reg_writable_masks(kvm, &range);
 	}
+	case KVM_ARM_RMI_POPULATE: {
+		struct kvm_arm_rmi_populate req;
+
+		if (!kvm_is_realm(kvm))
+			return -EPERM;
+		if (copy_from_user(&req, argp, sizeof(req)))
+			return -EFAULT;
+		return kvm_arm_rmi_populate(kvm, &req);
+	}
 	default:
 		return -EINVAL;
 	}
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index fe15b400091c..39577e956a59 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -558,6 +558,150 @@ void kvm_realm_unmap_range(struct kvm *kvm, unsigned long start,
 		realm_unmap_private_range(kvm, start, end, may_block);
 }
 
+static int realm_create_protected_data_granule(struct realm *realm,
+					       unsigned long ipa,
+					       phys_addr_t dst_phys,
+					       phys_addr_t src_phys,
+					       unsigned long flags)
+{
+	phys_addr_t rd = virt_to_phys(realm->rd);
+	int ret;
+
+	if (rmi_granule_delegate(dst_phys))
+		return -ENXIO;
+
+	ret = rmi_data_create(rd, dst_phys, ipa, src_phys, flags);
+	if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
+		/* Create missing RTTs and retry */
+		int level = RMI_RETURN_INDEX(ret);
+
+		WARN_ON(level == RMM_RTT_MAX_LEVEL);
+
+		ret = realm_create_rtt_levels(realm, ipa, level,
+					      RMM_RTT_MAX_LEVEL, NULL);
+		if (ret)
+			return -EIO;
+
+		ret = rmi_data_create(rd, dst_phys, ipa, src_phys, flags);
+	}
+	if (ret)
+		return -EIO;
+
+	return 0;
+}
+
+static int realm_create_protected_data_page(struct realm *realm,
+					    unsigned long ipa,
+					    kvm_pfn_t dst_pfn,
+					    kvm_pfn_t src_pfn,
+					    unsigned long flags)
+{
+	unsigned long rd = virt_to_phys(realm->rd);
+	phys_addr_t dst_phys, src_phys;
+	bool undelegate_failed = false;
+	int ret, offset;
+
+	dst_phys = __pfn_to_phys(dst_pfn);
+	src_phys = __pfn_to_phys(src_pfn);
+
+	for (offset = 0; offset < PAGE_SIZE; offset += RMM_PAGE_SIZE) {
+		ret = realm_create_protected_data_granule(realm,
+							  ipa,
+							  dst_phys,
+							  src_phys,
+							  flags);
+		if (ret)
+			goto err;
+
+		ipa += RMM_PAGE_SIZE;
+		dst_phys += RMM_PAGE_SIZE;
+		src_phys += RMM_PAGE_SIZE;
+	}
+
+	return 0;
+
+err:
+	if (ret == -EIO) {
+		/* current offset needs undelegating */
+		if (WARN_ON(rmi_granule_undelegate(dst_phys)))
+			undelegate_failed = true;
+	}
+	while (offset > 0) {
+		ipa -= RMM_PAGE_SIZE;
+		offset -= RMM_PAGE_SIZE;
+		dst_phys -= RMM_PAGE_SIZE;
+
+		rmi_data_destroy(rd, ipa, NULL, NULL);
+
+		if (WARN_ON(rmi_granule_undelegate(dst_phys)))
+			undelegate_failed = true;
+	}
+
+	if (undelegate_failed) {
+		/*
+		 * A granule could not be undelegated,
+		 * so the page has to be leaked
+		 */
+		get_page(pfn_to_page(dst_pfn));
+	}
+
+	return -ENXIO;
+}
+
+static int populate_region_cb(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
+			      void __user *src, int order, void *opaque)
+{
+	struct realm *realm = &kvm->arch.realm;
+	unsigned long data_flags = *(unsigned long *)opaque;
+	phys_addr_t ipa = gfn_to_gpa(gfn);
+	int npages = (1 << order);
+	int i;
+
+	for (i = 0; i < npages; i++) {
+		struct page *src_page;
+		int ret;
+
+		ret = get_user_pages((unsigned long)src, 1, 0, &src_page);
+		if (ret < 0)
+			return ret;
+		if (ret != 1)
+			return -ENOMEM;
+
+		ret = realm_create_protected_data_page(realm, ipa, pfn,
+						       page_to_pfn(src_page),
+						       data_flags);
+
+		put_page(src_page);
+
+		if (ret)
+			return ret;
+
+		ipa += PAGE_SIZE;
+		pfn++;
+		src += PAGE_SIZE;
+	}
+
+	return 0;
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
+	mmap_read_lock(current->mm);
+	ret = kvm_gmem_populate(kvm, base_gfn, u64_to_user_ptr(uaddr), pages,
+				populate_region_cb, &data_flags);
+	mmap_read_unlock(current->mm);
+	mutex_unlock(&kvm->slots_lock);
+
+	return ret;
+}
+
 enum ripas_action {
 	RIPAS_INIT,
 	RIPAS_SET,
@@ -655,6 +799,37 @@ static int realm_ensure_created(struct kvm *kvm)
 	return -ENXIO;
 }
 
+int kvm_arm_rmi_populate(struct kvm *kvm,
+			 struct kvm_arm_rmi_populate *args)
+{
+	unsigned long data_flags = 0;
+	unsigned long ipa_start = args->base;
+	unsigned long ipa_end = ipa_start + args->size;
+	int ret;
+
+	if (args->reserved ||
+	    (args->flags & ~KVM_ARM_RMI_POPULATE_FLAGS_MEASURE) ||
+	    !IS_ALIGNED(ipa_start, PAGE_SIZE) ||
+	    !IS_ALIGNED(ipa_end, PAGE_SIZE))
+		return -EINVAL;
+
+	ret = realm_ensure_created(kvm);
+	if (ret)
+		return ret;
+
+	if (args->flags & KVM_ARM_RMI_POPULATE_FLAGS_MEASURE)
+		data_flags |= RMI_MEASURE_CONTENT;
+
+	ret = populate_region(kvm, gpa_to_gfn(ipa_start),
+			      args->size >> PAGE_SHIFT,
+			      args->source_uaddr, args->flags);
+
+	if (ret < 0)
+		return ret;
+
+	return ret * PAGE_SIZE;
+}
+
 static void kvm_complete_ripas_change(struct kvm_vcpu *vcpu)
 {
 	struct kvm *kvm = vcpu->kvm;

---

## [22] Steven Price — 2025-12-17
*Subject: [PATCH v12 21/46] arm64: RMI: Set RIPAS of initial memslots*

The memory which the realm guest accesses must be set to RIPAS_RAM.
Iterate over the memslots and set all gmem memslots to RIPAS_RAM.

Signed-off-by: Steven Price <steven.price@arm.com>
---
New patch for v12.
---
 arch/arm64/kvm/rmi.c | 36 ++++++++++++++++++++++++++++++++++++
 1 file changed, 36 insertions(+)

diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 39577e956a59..b51e68e56d56 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -793,12 +793,44 @@ static int realm_set_ipa_state(struct kvm_vcpu *vcpu,
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
@@ -1119,6 +1151,10 @@ int kvm_activate_realm(struct kvm *kvm)
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

## [23] Steven Price — 2025-12-17
*Subject: [PATCH v12 22/46] arm64: RMI: Create the realm descriptor*

Creating a realm involves first creating a realm descriptor (RD). This
involves passing the configuration information to the RMM. Do this as
part of realm_ensure_created() so that the realm is created when it is
first needed.

Signed-off-by: Steven Price <steven.price@arm.com>
---
New patch for v12
---
 arch/arm64/kvm/rmi.c | 117 ++++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 115 insertions(+), 2 deletions(-)

diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index b51e68e56d56..18edc7eeb5fa 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -500,6 +500,106 @@ static void realm_unmap_shared_range(struct kvm *kvm,
 			     start, end);
 }
 
+/* Calculate the number of s2 root rtts needed */
+static int realm_num_root_rtts(struct realm *realm)
+{
+	unsigned int ipa_bits = realm->ia_bits;
+	unsigned int levels = 4 - get_start_level(realm);
+	unsigned int sl_ipa_bits = levels * (RMM_PAGE_SHIFT - 3) +
+				   RMM_PAGE_SHIFT;
+
+	if (sl_ipa_bits >= ipa_bits)
+		return 1;
+
+	return 1 << (ipa_bits - sl_ipa_bits);
+}
+
+static int realm_create_rd(struct kvm *kvm)
+{
+	struct realm *realm = &kvm->arch.realm;
+	struct realm_params *params = realm->params;
+	void *rd = NULL;
+	phys_addr_t rd_phys, params_phys;
+	size_t pgd_size = kvm_pgtable_stage2_pgd_size(kvm->arch.mmu.vtcr);
+	int i, r;
+	int rtt_num_start;
+
+	realm->ia_bits = VTCR_EL2_IPA(kvm->arch.mmu.vtcr);
+	rtt_num_start = realm_num_root_rtts(realm);
+
+	if (WARN_ON(realm->rd || !realm->params))
+		return -EEXIST;
+
+	if (pgd_size / RMM_PAGE_SIZE < rtt_num_start)
+		return -EINVAL;
+
+	rd = (void *)__get_free_page(GFP_KERNEL);
+	if (!rd)
+		return -ENOMEM;
+
+	rd_phys = virt_to_phys(rd);
+	if (rmi_granule_delegate(rd_phys)) {
+		r = -ENXIO;
+		goto free_rd;
+	}
+
+	for (i = 0; i < pgd_size; i += RMM_PAGE_SIZE) {
+		phys_addr_t pgd_phys = kvm->arch.mmu.pgd_phys + i;
+
+		if (rmi_granule_delegate(pgd_phys)) {
+			r = -ENXIO;
+			goto out_undelegate_tables;
+		}
+	}
+
+	params->s2sz = VTCR_EL2_IPA(kvm->arch.mmu.vtcr);
+	params->rtt_level_start = get_start_level(realm);
+	params->rtt_num_start = rtt_num_start;
+	params->rtt_base = kvm->arch.mmu.pgd_phys;
+	params->vmid = realm->vmid;
+
+	params_phys = virt_to_phys(params);
+
+	if (rmi_realm_create(rd_phys, params_phys)) {
+		r = -ENXIO;
+		goto out_undelegate_tables;
+	}
+
+	if (WARN_ON(rmi_rec_aux_count(rd_phys, &realm->num_aux))) {
+		WARN_ON(rmi_realm_destroy(rd_phys));
+		r = -ENXIO;
+		goto out_undelegate_tables;
+	}
+
+	realm->rd = rd;
+	WRITE_ONCE(realm->state, REALM_STATE_NEW);
+	/* The realm is up, free the parameters.  */
+	free_page((unsigned long)realm->params);
+	realm->params = NULL;
+
+	return 0;
+
+out_undelegate_tables:
+	while (i > 0) {
+		i -= RMM_PAGE_SIZE;
+
+		phys_addr_t pgd_phys = kvm->arch.mmu.pgd_phys + i;
+
+		if (WARN_ON(rmi_granule_undelegate(pgd_phys))) {
+			/* Leak the pages if they cannot be returned */
+			kvm->arch.mmu.pgt = NULL;
+			break;
+		}
+	}
+	if (WARN_ON(rmi_granule_undelegate(rd_phys))) {
+		/* Leak the page if it isn't returned */
+		return r;
+	}
+free_rd:
+	free_page((unsigned long)rd);
+	return r;
+}
+
 static int realm_unmap_private_page(struct realm *realm,
 				    unsigned long ipa,
 				    unsigned long *next_addr)
@@ -803,8 +903,21 @@ static int realm_init_ipa_state(struct kvm *kvm,
 
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

## [24] Steven Price — 2025-12-17
*Subject: [PATCH v12 23/46] arm64: RMI: Add a VMID allocator for realms*

The RMM v1.0 spec requires that the host manage the VMIDs of realm
guests. Add a basic allocator and assign a unique VMID to the guest when
creating the realm descriptor.

Signed-off-by: Steven Price <steven.price@arm.com>
---
New patch for v12.
NOTE: RMM v2.0 will remove the requirement for the host to manage VMIDs
---
 arch/arm64/kvm/rmi.c | 48 ++++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 48 insertions(+)

diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 18edc7eeb5fa..ede6c250bcfb 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -600,6 +600,42 @@ static int realm_create_rd(struct kvm *kvm)
 	return r;
 }
 
+/* Protects access to rmi_vmid_bitmap */
+static DEFINE_SPINLOCK(rmi_vmid_lock);
+static unsigned long *rmi_vmid_bitmap;
+
+static int rmi_vmid_init(void)
+{
+	unsigned int vmid_count = 1 << kvm_get_vmid_bits();
+
+	rmi_vmid_bitmap = bitmap_zalloc(vmid_count, GFP_KERNEL);
+	if (!rmi_vmid_bitmap) {
+		kvm_err("%s: Couldn't allocate rmi vmid bitmap\n", __func__);
+		return -ENOMEM;
+	}
+
+	return 0;
+}
+
+static int rmi_vmid_reserve(void)
+{
+	int ret;
+	unsigned int vmid_count = 1 << kvm_get_vmid_bits();
+
+	spin_lock(&rmi_vmid_lock);
+	ret = bitmap_find_free_region(rmi_vmid_bitmap, vmid_count, 0);
+	spin_unlock(&rmi_vmid_lock);
+
+	return ret;
+}
+
+static void rmi_vmid_release(unsigned int vmid)
+{
+	spin_lock(&rmi_vmid_lock);
+	bitmap_release_region(rmi_vmid_bitmap, vmid, 0);
+	spin_unlock(&rmi_vmid_lock);
+}
+
 static int realm_unmap_private_page(struct realm *realm,
 				    unsigned long ipa,
 				    unsigned long *next_addr)
@@ -903,6 +939,7 @@ static int realm_init_ipa_state(struct kvm *kvm,
 
 static int realm_ensure_created(struct kvm *kvm)
 {
+	struct realm *realm = &kvm->arch.realm;
 	int ret;
 
 	switch (kvm_realm_state(kvm)) {
@@ -916,7 +953,13 @@ static int realm_ensure_created(struct kvm *kvm)
 		return -EBUSY;
 	}
 
+	ret = rmi_vmid_reserve();
+	if (ret < 0)
+		return ret;
+	realm->vmid = ret;
 	ret = realm_create_rd(kvm);
+	if (ret)
+		rmi_vmid_release(realm->vmid);
 	return ret;
 }
 
@@ -1307,6 +1350,8 @@ void kvm_destroy_realm(struct kvm *kvm)
 		realm->rd = NULL;
 	}
 
+	rmi_vmid_release(realm->vmid);
+
 	for (i = 0; i < pgd_size; i += RMM_PAGE_SIZE) {
 		phys_addr_t pgd_phys = kvm->arch.mmu.pgd_phys + i;
 
@@ -1342,5 +1387,8 @@ void kvm_init_rmi(void)
 	if (WARN_ON(rmi_features(0, &rmm_feat_reg0)))
 		return;
 
+	if (rmi_vmid_init())
+		return;
+
 	/* Future patch will enable static branch kvm_rmi_is_available */
 }

---

## [25] Steven Price — 2025-12-17
*Subject: [PATCH v12 24/46] arm64: RMI: Runtime faulting of memory*

At runtime if the realm guest accesses memory which hasn't yet been
mapped then KVM needs to either populate the region or fault the guest.

For memory in the lower (protected) region of IPA a fresh page is
provided to the RMM which will zero the contents. For memory in the
upper (shared) region of IPA, the memory from the memslot is mapped
into the realm VM non secure.

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/include/asm/kvm_rmi.h     |  10 ++
 arch/arm64/kvm/mmu.c                 | 139 ++++++++++++++++++++---
 arch/arm64/kvm/rmi.c                 | 164 +++++++++++++++++++++++++++
 4 files changed, 307 insertions(+), 14 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_emulate.h b/arch/arm64/include/asm/kvm_emulate.h
index f884bac43c06..7d8380fede14 100644
--- a/arch/arm64/include/asm/kvm_emulate.h
+++ b/arch/arm64/include/asm/kvm_emulate.h
@@ -714,6 +714,14 @@ static inline bool kvm_realm_is_created(struct kvm *kvm)
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
 static inline bool vcpu_is_rec(struct kvm_vcpu *vcpu)
 {
 	return kvm_is_realm(vcpu->kvm);
diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index b5e36344975c..bfe6428eaf16 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -108,6 +108,16 @@ void kvm_realm_unmap_range(struct kvm *kvm,
 			   unsigned long size,
 			   bool unmap_private,
 			   bool may_block);
+int realm_map_protected(struct realm *realm,
+			unsigned long base_ipa,
+			kvm_pfn_t pfn,
+			unsigned long size,
+			struct kvm_mmu_memory_cache *memcache);
+int realm_map_non_secure(struct realm *realm,
+			 unsigned long ipa,
+			 kvm_pfn_t pfn,
+			 unsigned long size,
+			 struct kvm_mmu_memory_cache *memcache);
 
 static inline bool kvm_realm_is_private_address(struct realm *realm,
 						unsigned long addr)
diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index f2ac01c1de04..860c42aabcf0 100644
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
@@ -355,7 +362,10 @@ static void stage2_flush_memslot(struct kvm *kvm,
 	phys_addr_t addr = memslot->base_gfn << PAGE_SHIFT;
 	phys_addr_t end = addr + PAGE_SIZE * memslot->npages;
 
-	kvm_stage2_flush_range(&kvm->arch.mmu, addr, end);
+	if (kvm_is_realm(kvm))
+		kvm_realm_unmap_range(kvm, addr, end - addr, false, true);
+	else
+		kvm_stage2_flush_range(&kvm->arch.mmu, addr, end);
 }
 
 /**
@@ -1081,6 +1091,10 @@ void stage2_unmap_vm(struct kvm *kvm)
 	struct kvm_memory_slot *memslot;
 	int idx, bkt;
 
+	/* For realms this is handled by the RMM so nothing to do here */
+	if (kvm_is_realm(kvm))
+		return;
+
 	idx = srcu_read_lock(&kvm->srcu);
 	mmap_read_lock(current->mm);
 	write_lock(&kvm->mmu_lock);
@@ -1106,6 +1120,9 @@ void kvm_free_stage2_pgd(struct kvm_s2_mmu *mmu)
 	if (kvm_is_realm(kvm) &&
 	    (kvm_realm_state(kvm) != REALM_STATE_DEAD &&
 	     kvm_realm_state(kvm) != REALM_STATE_NONE)) {
+		struct realm *realm = &kvm->arch.realm;
+
+		kvm_stage2_unmap_range(mmu, 0, BIT(realm->ia_bits - 1), true);
 		write_unlock(&kvm->mmu_lock);
 		kvm_realm_destroy_rtts(kvm);
 
@@ -1515,6 +1532,29 @@ static bool kvm_vma_mte_allowed(struct vm_area_struct *vma)
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
+		return realm_map_non_secure(realm, ipa, pfn, map_size,
+					    memcache);
+
+	return realm_map_protected(realm, ipa, pfn, map_size, memcache);
+}
+
 static bool kvm_vma_is_cacheable(struct vm_area_struct *vma)
 {
 	switch (FIELD_GET(PTE_ATTRINDX_MASK, pgprot_val(vma->vm_page_prot))) {
@@ -1589,6 +1629,7 @@ static int gmem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 	enum kvm_pgtable_walk_flags flags = KVM_PGTABLE_WALK_MEMABORT_FLAGS;
 	enum kvm_pgtable_prot prot = KVM_PGTABLE_PROT_R;
 	struct kvm_pgtable *pgt = vcpu->arch.hw_mmu->pgt;
+	gpa_t gpa = kvm_gpa_from_fault(vcpu->kvm, fault_ipa);
 	unsigned long mmu_seq;
 	struct page *page;
 	struct kvm *kvm = vcpu->kvm;
@@ -1597,6 +1638,29 @@ static int gmem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 	gfn_t gfn;
 	int ret;
 
+	if (kvm_is_realm(vcpu->kvm)) {
+		/* check for memory attribute mismatch */
+		bool is_priv_gfn = kvm_mem_is_private(kvm, gpa >> PAGE_SHIFT);
+		/*
+		 * For Realms, the shared address is an alias of the private
+		 * PA with the top bit set. Thus is the fault address matches
+		 * the GPA then it is the private alias.
+		 */
+		bool is_priv_fault = (gpa == fault_ipa);
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
 	ret = prepare_mmu_memcache(vcpu, true, &memcache);
 	if (ret)
 		return ret;
@@ -1604,7 +1668,7 @@ static int gmem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 	if (nested)
 		gfn = kvm_s2_trans_output(nested) >> PAGE_SHIFT;
 	else
-		gfn = fault_ipa >> PAGE_SHIFT;
+		gfn = gpa >> PAGE_SHIFT;
 
 	write_fault = kvm_is_write_fault(vcpu);
 	exec_fault = kvm_vcpu_trap_is_exec_fault(vcpu);
@@ -1617,7 +1681,7 @@ static int gmem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 
 	ret = kvm_gmem_get_pfn(kvm, memslot, gfn, &pfn, &page, NULL);
 	if (ret) {
-		kvm_prepare_memory_fault_exit(vcpu, fault_ipa, PAGE_SIZE,
+		kvm_prepare_memory_fault_exit(vcpu, gpa, PAGE_SIZE,
 					      write_fault, exec_fault, false);
 		return ret;
 	}
@@ -1639,15 +1703,25 @@ static int gmem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 	kvm_fault_lock(kvm);
 	if (mmu_invalidate_retry(kvm, mmu_seq)) {
 		ret = -EAGAIN;
-		goto out_unlock;
+		goto out_release_page;
+	}
+
+	if (kvm_is_realm(kvm)) {
+		ret = realm_map_ipa(kvm, fault_ipa, pfn,
+				    PAGE_SIZE, KVM_PGTABLE_PROT_W, memcache);
+		/* if successful don't release the page */
+		if (!ret)
+			goto out_unlock;
+		goto out_release_page;
 	}
 
 	ret = KVM_PGT_FN(kvm_pgtable_stage2_map)(pgt, fault_ipa, PAGE_SIZE,
 						 __pfn_to_phys(pfn), prot,
 						 memcache, flags);
 
-out_unlock:
+out_release_page:
 	kvm_release_faultin_page(kvm, page, !!ret, writable);
+out_unlock:
 	kvm_fault_unlock(kvm);
 
 	if (writable && !ret)
@@ -1686,6 +1760,14 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 	if (fault_is_perm)
 		fault_granule = kvm_vcpu_trap_get_perm_fault_granule(vcpu);
 	write_fault = kvm_is_write_fault(vcpu);
+
+	/*
+	 * Realms cannot map protected pages read-only
+	 * FIXME: It should be possible to map unprotected pages read-only
+	 */
+	if (vcpu_is_rec(vcpu))
+		write_fault = true;
+
 	exec_fault = kvm_vcpu_trap_is_exec_fault(vcpu);
 	VM_WARN_ON_ONCE(write_fault && exec_fault);
 
@@ -1780,7 +1862,7 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 		ipa &= ~(vma_pagesize - 1);
 	}
 
-	gfn = ipa >> PAGE_SHIFT;
+	gfn = kvm_gpa_from_fault(kvm, ipa) >> PAGE_SHIFT;
 	mte_allowed = kvm_vma_mte_allowed(vma);
 
 	vfio_allow_any_uc = vma->vm_flags & VM_ALLOW_ANY_UNCACHED;
@@ -1856,6 +1938,15 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 	if (exec_fault && s2_force_noncacheable)
 		ret = -ENOEXEC;
 
+	/*
+	 * For now we shouldn't be hitting protected addresses because they are
+	 * handled in gmem_abort(). In the future this check may be relaxed to
+	 * support e.g. protected devices.
+	 */
+	if (!ret && vcpu_is_rec(vcpu) &&
+	    kvm_gpa_from_fault(kvm, fault_ipa) == fault_ipa)
+		ret = -EINVAL;
+
 	if (ret) {
 		kvm_release_page_unused(page);
 		return ret;
@@ -1929,6 +2020,9 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 		 */
 		prot &= ~KVM_NV_GUEST_MAP_SZ;
 		ret = KVM_PGT_FN(kvm_pgtable_stage2_relax_perms)(pgt, fault_ipa, prot, flags);
+	} else if (kvm_is_realm(kvm)) {
+		ret = realm_map_ipa(kvm, fault_ipa, pfn, vma_pagesize,
+				    prot, memcache);
 	} else {
 		ret = KVM_PGT_FN(kvm_pgtable_stage2_map)(pgt, fault_ipa, vma_pagesize,
 					     __pfn_to_phys(pfn), prot,
@@ -2039,6 +2133,13 @@ int kvm_handle_guest_sea(struct kvm_vcpu *vcpu)
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
@@ -2148,8 +2249,9 @@ int kvm_handle_guest_abort(struct kvm_vcpu *vcpu)
 		nested = &nested_trans;
 	}
 
-	gfn = ipa >> PAGE_SHIFT;
+	gfn = kvm_gpa_from_fault(vcpu->kvm, ipa) >> PAGE_SHIFT;
 	memslot = gfn_to_memslot(vcpu->kvm, gfn);
+
 	hva = gfn_to_hva_memslot_prot(memslot, gfn, &writable);
 	write_fault = kvm_is_write_fault(vcpu);
 	if (kvm_is_error_hva(hva) || (write_fault && !writable)) {
@@ -2192,7 +2294,7 @@ int kvm_handle_guest_abort(struct kvm_vcpu *vcpu)
 		 * of the page size.
 		 */
 		ipa |= kvm_vcpu_get_hfar(vcpu) & GENMASK(11, 0);
-		ret = io_mem_abort(vcpu, ipa);
+		ret = io_mem_abort(vcpu, kvm_gpa_from_fault(vcpu->kvm, ipa));
 		goto out_unlock;
 	}
 
@@ -2208,7 +2310,7 @@ int kvm_handle_guest_abort(struct kvm_vcpu *vcpu)
 	VM_WARN_ON_ONCE(kvm_vcpu_trap_is_permission_fault(vcpu) &&
 			!write_fault && !kvm_vcpu_trap_is_exec_fault(vcpu));
 
-	if (kvm_slot_has_gmem(memslot))
+	if (kvm_slot_has_gmem(memslot) && !shared_ipa_fault(vcpu->kvm, fault_ipa))
 		ret = gmem_abort(vcpu, fault_ipa, nested, memslot,
 				 esr_fsc_is_permission_fault(esr));
 	else
@@ -2245,6 +2347,10 @@ bool kvm_age_gfn(struct kvm *kvm, struct kvm_gfn_range *range)
 	if (!kvm->arch.mmu.pgt)
 		return false;
 
+	/* We don't support aging for Realms */
+	if (kvm_is_realm(kvm))
+		return true;
+
 	return KVM_PGT_FN(kvm_pgtable_stage2_test_clear_young)(kvm->arch.mmu.pgt,
 						   range->start << PAGE_SHIFT,
 						   size, true);
@@ -2261,6 +2367,10 @@ bool kvm_test_age_gfn(struct kvm *kvm, struct kvm_gfn_range *range)
 	if (!kvm->arch.mmu.pgt)
 		return false;
 
+	/* We don't support aging for Realms */
+	if (kvm_is_realm(kvm))
+		return true;
+
 	return KVM_PGT_FN(kvm_pgtable_stage2_test_clear_young)(kvm->arch.mmu.pgt,
 						   range->start << PAGE_SHIFT,
 						   size, false);
@@ -2447,10 +2557,11 @@ int kvm_arch_prepare_memory_region(struct kvm *kvm,
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
index ede6c250bcfb..de1a66df7a5e 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -784,6 +784,170 @@ static int realm_create_protected_data_page(struct realm *realm,
 	return -ENXIO;
 }
 
+static int fold_rtt(struct realm *realm, unsigned long addr, int level)
+{
+	phys_addr_t rtt_addr;
+	int ret;
+
+	ret = realm_rtt_fold(realm, addr, level, &rtt_addr);
+	if (ret)
+		return ret;
+
+	free_rtt(rtt_addr);
+
+	return 0;
+}
+
+int realm_map_protected(struct realm *realm,
+			unsigned long ipa,
+			kvm_pfn_t pfn,
+			unsigned long map_size,
+			struct kvm_mmu_memory_cache *memcache)
+{
+	phys_addr_t phys = __pfn_to_phys(pfn);
+	phys_addr_t rd = virt_to_phys(realm->rd);
+	unsigned long base_ipa = ipa;
+	unsigned long size;
+	int map_level = IS_ALIGNED(map_size, RMM_L2_BLOCK_SIZE) ?
+			RMM_RTT_BLOCK_LEVEL : RMM_RTT_MAX_LEVEL;
+	int ret = 0;
+
+	if (WARN_ON(!IS_ALIGNED(map_size, RMM_PAGE_SIZE) ||
+		    !IS_ALIGNED(ipa, map_size)))
+		return -EINVAL;
+
+	if (map_level < RMM_RTT_MAX_LEVEL) {
+		/*
+		 * A temporary RTT is needed during the map, precreate it,
+		 * however if there is an error (e.g. missing parent tables)
+		 * this will be handled below.
+		 */
+		realm_create_rtt_levels(realm, ipa, map_level,
+					RMM_RTT_MAX_LEVEL, memcache);
+	}
+
+	for (size = 0; size < map_size; size += RMM_PAGE_SIZE) {
+		if (rmi_granule_delegate(phys)) {
+			/*
+			 * It's likely we raced with another VCPU on the same
+			 * fault. Assume the other VCPU has handled the fault
+			 * and return to the guest.
+			 */
+			return 0;
+		}
+
+		ret = rmi_data_create_unknown(rd, phys, ipa);
+
+		if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
+			/* Create missing RTTs and retry */
+			int level = RMI_RETURN_INDEX(ret);
+
+			WARN_ON(level == RMM_RTT_MAX_LEVEL);
+			ret = realm_create_rtt_levels(realm, ipa, level,
+						      RMM_RTT_MAX_LEVEL,
+						      memcache);
+			if (ret)
+				goto err_undelegate;
+
+			ret = rmi_data_create_unknown(rd, phys, ipa);
+		}
+
+		if (WARN_ON(ret))
+			goto err_undelegate;
+
+		phys += RMM_PAGE_SIZE;
+		ipa += RMM_PAGE_SIZE;
+	}
+
+	if (map_size == RMM_L2_BLOCK_SIZE) {
+		ret = fold_rtt(realm, base_ipa, map_level + 1);
+		if (WARN_ON(ret))
+			goto err;
+	}
+
+	return 0;
+
+err_undelegate:
+	if (WARN_ON(rmi_granule_undelegate(phys))) {
+		/* Page can't be returned to NS world so is lost */
+		get_page(phys_to_page(phys));
+	}
+err:
+	while (size > 0) {
+		unsigned long data, top;
+
+		phys -= RMM_PAGE_SIZE;
+		size -= RMM_PAGE_SIZE;
+		ipa -= RMM_PAGE_SIZE;
+
+		WARN_ON(rmi_data_destroy(rd, ipa, &data, &top));
+
+		if (WARN_ON(rmi_granule_undelegate(phys))) {
+			/* Page can't be returned to NS world so is lost */
+			get_page(phys_to_page(phys));
+		}
+	}
+	return -ENXIO;
+}
+
+int realm_map_non_secure(struct realm *realm,
+			 unsigned long ipa,
+			 kvm_pfn_t pfn,
+			 unsigned long size,
+			 struct kvm_mmu_memory_cache *memcache)
+{
+	phys_addr_t rd = virt_to_phys(realm->rd);
+	phys_addr_t phys = __pfn_to_phys(pfn);
+	unsigned long offset;
+	/* TODO: Support block mappings */
+	int map_level = RMM_RTT_MAX_LEVEL;
+	int map_size = rmi_rtt_level_mapsize(map_level);
+	int ret = 0;
+
+	if (WARN_ON(!IS_ALIGNED(size, RMM_PAGE_SIZE) ||
+		    !IS_ALIGNED(ipa, size)))
+		return -EINVAL;
+
+	for (offset = 0; offset < size; offset += map_size) {
+		/*
+		 * realm_map_ipa() enforces that the memory is writable,
+		 * so for now we permit both read and write.
+		 */
+		unsigned long desc = phys |
+				     PTE_S2_MEMATTR(MT_S2_FWB_NORMAL) |
+				     KVM_PTE_LEAF_ATTR_LO_S2_S2AP_R |
+				     KVM_PTE_LEAF_ATTR_LO_S2_S2AP_W;
+		ret = rmi_rtt_map_unprotected(rd, ipa, map_level, desc);
+
+		if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
+			/* Create missing RTTs and retry */
+			int level = RMI_RETURN_INDEX(ret);
+
+			ret = realm_create_rtt_levels(realm, ipa, level,
+						      map_level, memcache);
+			if (ret)
+				return -ENXIO;
+
+			ret = rmi_rtt_map_unprotected(rd, ipa, map_level, desc);
+		}
+		/*
+		 * RMI_ERROR_RTT can be reported for two reasons: either the
+		 * RTT tables are not there, or there is an RTTE already
+		 * present for the address.  The above call to create RTTs
+		 * handles the first case, and in the second case this
+		 * indicates that another thread has already populated the RTTE
+		 * for us, so we can ignore the error and continue.
+		 */
+		if (ret && RMI_RETURN_STATUS(ret) != RMI_ERROR_RTT)
+			return -ENXIO;
+
+		ipa += map_size;
+		phys += map_size;
+	}
+
+	return 0;
+}
+
 static int populate_region_cb(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 			      void __user *src, int order, void *opaque)
 {

---

## [26] Steven Price — 2025-12-17
*Subject: [PATCH v12 25/46] KVM: arm64: Handle realm VCPU load*

When loading a realm VCPU much of the work is handled by the RMM so only
some of the actions are required. Rearrange kvm_arch_vcpu_load()
slightly so we can bail out early for a realm guest.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/kvm/arm.c | 19 ++++++++++++-------
 1 file changed, 12 insertions(+), 7 deletions(-)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 0a06ed9d1a64..06070bc47ee3 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -641,7 +641,7 @@ void kvm_arch_vcpu_load(struct kvm_vcpu *vcpu, int cpu)
 	struct kvm_s2_mmu *mmu;
 	int *last_ran;
 
-	if (is_protected_kvm_enabled())
+	if (is_protected_kvm_enabled() || kvm_is_realm(vcpu->kvm))
 		goto nommu;
 
 	if (vcpu_has_nv(vcpu))
@@ -685,12 +685,6 @@ void kvm_arch_vcpu_load(struct kvm_vcpu *vcpu, int cpu)
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
@@ -712,6 +706,17 @@ void kvm_arch_vcpu_load(struct kvm_vcpu *vcpu, int cpu)
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
 }

---

## [27] Steven Price — 2025-12-17
*Subject: [PATCH v12 26/46] KVM: arm64: Validate register access for a Realm VM*

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
index 1c87699fd886..e62a4feddff3 100644
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

## [28] Steven Price — 2025-12-17
*Subject: [PATCH v12 27/46] KVM: arm64: Handle Realm PSCI requests*

The RMM needs to be informed of the target REC when a PSCI call is made
with an MPIDR argument. Expose an ioctl to the userspace in case the PSCI
is handled by it.

Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
---
Changes since v11:
 * RMM->RMI renaming.
Changes since v6:
 * Use vcpu_is_rec() rather than kvm_is_realm(vcpu->kvm).
 * Minor renaming/formatting fixes.
---
 arch/arm64/include/asm/kvm_rmi.h |  3 +++
 arch/arm64/kvm/arm.c             | 25 +++++++++++++++++++++++++
 arch/arm64/kvm/psci.c            | 30 ++++++++++++++++++++++++++++++
 arch/arm64/kvm/rmi.c             | 14 ++++++++++++++
 4 files changed, 72 insertions(+)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index bfe6428eaf16..77da297ca09d 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -118,6 +118,9 @@ int realm_map_non_secure(struct realm *realm,
 			 kvm_pfn_t pfn,
 			 unsigned long size,
 			 struct kvm_mmu_memory_cache *memcache);
+int realm_psci_complete(struct kvm_vcpu *source,
+			struct kvm_vcpu *target,
+			unsigned long status);
 
 static inline bool kvm_realm_is_private_address(struct realm *realm,
 						unsigned long addr)
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 06070bc47ee3..fb04d032504e 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -1797,6 +1797,22 @@ static int kvm_arm_vcpu_set_events(struct kvm_vcpu *vcpu,
 	return __kvm_arm_vcpu_set_events(vcpu, events);
 }
 
+static int kvm_arm_vcpu_rmi_psci_complete(struct kvm_vcpu *vcpu,
+					  struct kvm_arm_rmi_psci_complete *arg)
+{
+	struct kvm_vcpu *target = kvm_mpidr_to_vcpu(vcpu->kvm, arg->target_mpidr);
+
+	if (!target)
+		return -EINVAL;
+
+	/*
+	 * RMM v1.0 only supports PSCI_RET_SUCCESS or PSCI_RET_DENIED
+	 * for the status. But, let us leave it to the RMM to filter
+	 * for making this future proof.
+	 */
+	return realm_psci_complete(vcpu, target, arg->psci_status);
+}
+
 long kvm_arch_vcpu_ioctl(struct file *filp,
 			 unsigned int ioctl, unsigned long arg)
 {
@@ -1925,6 +1941,15 @@ long kvm_arch_vcpu_ioctl(struct file *filp,
 
 		return kvm_arm_vcpu_finalize(vcpu, what);
 	}
+	case KVM_ARM_VCPU_RMI_PSCI_COMPLETE: {
+		struct kvm_arm_rmi_psci_complete req;
+
+		if (!vcpu_is_rec(vcpu))
+			return -EPERM;
+		if (copy_from_user(&req, argp, sizeof(req)))
+			return -EFAULT;
+		return kvm_arm_vcpu_rmi_psci_complete(vcpu, &req);
+	}
 	default:
 		r = -EINVAL;
 	}
diff --git a/arch/arm64/kvm/psci.c b/arch/arm64/kvm/psci.c
index 3b5dbe9a0a0e..a68f3c1878a5 100644
--- a/arch/arm64/kvm/psci.c
+++ b/arch/arm64/kvm/psci.c
@@ -103,6 +103,12 @@ static unsigned long kvm_psci_vcpu_on(struct kvm_vcpu *source_vcpu)
 
 	reset_state->reset = true;
 	kvm_make_request(KVM_REQ_VCPU_RESET, vcpu);
+	/*
+	 * Make sure we issue PSCI_COMPLETE before the VCPU can be
+	 * scheduled.
+	 */
+	if (vcpu_is_rec(vcpu))
+		realm_psci_complete(source_vcpu, vcpu, PSCI_RET_SUCCESS);
 
 	/*
 	 * Make sure the reset request is observed if the RUNNABLE mp_state is
@@ -115,6 +121,11 @@ static unsigned long kvm_psci_vcpu_on(struct kvm_vcpu *source_vcpu)
 
 out_unlock:
 	spin_unlock(&vcpu->arch.mp_state_lock);
+	if (vcpu_is_rec(vcpu) && ret != PSCI_RET_SUCCESS) {
+		realm_psci_complete(source_vcpu, vcpu,
+				    ret == PSCI_RET_ALREADY_ON ?
+				    PSCI_RET_SUCCESS : PSCI_RET_DENIED);
+	}
 	return ret;
 }
 
@@ -142,6 +153,25 @@ static unsigned long kvm_psci_vcpu_affinity_info(struct kvm_vcpu *vcpu)
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
+		/*
+		 * Provide the references of the source and target RECs to the
+		 * RMM so that the RMM can complete the PSCI request.
+		 */
+		realm_psci_complete(vcpu, target_vcpu, PSCI_RET_SUCCESS);
+		return PSCI_RET_SUCCESS;
+	}
+
 	/*
 	 * If one or more VCPU matching target affinity are running
 	 * then ON else OFF
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index de1a66df7a5e..5f50566c701d 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -164,6 +164,20 @@ static void free_rtt(phys_addr_t phys)
 	kvm_account_pgtable_pages(phys_to_virt(phys), -1);
 }
 
+int realm_psci_complete(struct kvm_vcpu *source, struct kvm_vcpu *target,
+			unsigned long status)
+{
+	int ret;
+
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

---

## [29] Steven Price — 2025-12-17
*Subject: [PATCH v12 28/46] KVM: arm64: WARN on injected undef exceptions*

The RMM doesn't allow injection of a undefined exception into a realm
guest. Add a WARN to catch if this ever happens.

Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
---
Changes since v6:
 * if (x) WARN(1, ...) makes no sense, just WARN(x, ...)!
---
 arch/arm64/kvm/inject_fault.c | 1 +
 1 file changed, 1 insertion(+)

diff --git a/arch/arm64/kvm/inject_fault.c b/arch/arm64/kvm/inject_fault.c
index 5e00f7a69bcc..22bd9258665b 100644
--- a/arch/arm64/kvm/inject_fault.c
+++ b/arch/arm64/kvm/inject_fault.c
@@ -289,6 +289,7 @@ void kvm_inject_size_fault(struct kvm_vcpu *vcpu)
  */
 void kvm_inject_undefined(struct kvm_vcpu *vcpu)
 {
+	WARN(vcpu_is_rec(vcpu), "Unexpected undefined exception injection to REC");
 	if (vcpu_el1_is_32bit(vcpu))
 		inject_undef32(vcpu);
 	else

---

## [30] Steven Price — 2025-12-17
*Subject: [PATCH v12 29/46] arm64: Don't expose stolen time for realm guests*

It doesn't make much sense as a realm guest wouldn't want to trust the
host. It will also need some extra work to ensure that KVM will only
attempt to write into a shared memory region. So for now just disable
it.

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v7:
 * Update the documentation to add a note about stolen time being
   unavailable in a realm.
---
 Documentation/virt/kvm/api.rst | 3 +++
 arch/arm64/kvm/arm.c           | 5 ++++-
 2 files changed, 7 insertions(+), 1 deletion(-)

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index d7ebf42933e8..6788a8242fc7 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -9101,6 +9101,9 @@ is supported, than the other should as well and vice versa.  For arm64
 see Documentation/virt/kvm/devices/vcpu.rst "KVM_ARM_VCPU_PVTIME_CTRL".
 For x86 see Documentation/virt/kvm/x86/msr.rst "MSR_KVM_STEAL_TIME".
 
+Note that steal time accounting is not available when a guest is running
+within a Arm CCA realm (machine type KVM_VM_TYPE_ARM_REALM).
+
 8.25 KVM_CAP_S390_DIAG318
 -------------------------
 
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index fb04d032504e..403f9119543e 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -423,7 +423,10 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 		r = system_supports_mte();
 		break;
 	case KVM_CAP_STEAL_TIME:
-		r = kvm_arm_pvtime_supported();
+		if (kvm_is_realm(kvm))
+			r = 0;
+		else
+			r = kvm_arm_pvtime_supported();
 		break;
 	case KVM_CAP_ARM_EL1_32BIT:
 		r = cpus_have_final_cap(ARM64_HAS_32BIT_EL1);

---

## [31] Steven Price — 2025-12-17
*Subject: [PATCH v12 30/46] arm64: RMI: allow userspace to inject aborts*

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
index 6788a8242fc7..609bf0981f6e 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -1310,6 +1310,8 @@ User space may need to inject several types of events to the guest.
 Set the pending SError exception state for this VCPU. It is not possible to
 'cancel' an Serror that has been made pending.
 
+User space cannot inject SErrors into Realms.
+
 If the guest performed an access to I/O memory which could not be handled by
 userspace, for example because of missing instruction syndrome decode
 information or because there is no device mapped at the accessed IPA, then
diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index e62a4feddff3..d9f392cb2759 100644
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

## [32] Steven Price — 2025-12-17
*Subject: [PATCH v12 31/46] arm64: RMI: support RSI_HOST_CALL*

From: Joey Gouly <joey.gouly@arm.com>

Forward RSI_HOST_CALLS to KVM's HVC handler.

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
index b4843f094615..7eff6967530c 100644
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
@@ -183,6 +196,8 @@ int handle_rec_exit(struct kvm_vcpu *vcpu, int rec_run_ret)
 		return rec_exit_psci(vcpu);
 	case RMI_EXIT_RIPAS_CHANGE:
 		return rec_exit_ripas_change(vcpu);
+	case RMI_EXIT_HOST_CALL:
+		return rec_exit_host_call(vcpu);
 	}
 
 	kvm_pr_unimpl("Unsupported exit reason: %u\n",

---

## [33] Steven Price — 2025-12-17
*Subject: [PATCH v12 32/46] arm64: RMI: Allow checking SVE on VM instance*

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
 arch/arm64/include/asm/kvm_rmi.h |  2 ++
 arch/arm64/kvm/arm.c             |  2 ++
 arch/arm64/kvm/rmi.c             | 10 ++++++++++
 3 files changed, 14 insertions(+)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index 77da297ca09d..82280c138935 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -89,6 +89,8 @@ void kvm_init_rmi(void);
 u32 kvm_realm_ipa_limit(void);
 u32 kvm_realm_vgic_nr_lr(void);
 
+bool kvm_rmi_supports_sve(void);
+
 int kvm_init_realm_vm(struct kvm *kvm);
 int kvm_activate_realm(struct kvm *kvm);
 void kvm_destroy_realm(struct kvm *kvm);
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 403f9119543e..f8255de92902 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -342,6 +342,8 @@ static bool kvm_realm_ext_allowed(long ext)
 	case KVM_CAP_ARM_PTRAUTH_GENERIC:
 	case KVM_CAP_ARM_RMI:
 		return true;
+	case KVM_CAP_ARM_SVE:
+		return kvm_rmi_supports_sve();
 	}
 	return false;
 }
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 5f50566c701d..7ef5d7f48d0b 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -33,6 +33,16 @@ static inline unsigned long rmi_rtt_level_mapsize(int level)
 	return (1UL << RMM_RTT_LEVEL_SHIFT(level));
 }
 
+static bool rmi_has_feature(unsigned long feature)
+{
+	return !!u64_get_bits(rmm_feat_reg0, feature);
+}
+
+bool kvm_rmi_supports_sve(void)
+{
+	return rmi_has_feature(RMI_FEATURE_REGISTER_0_SVE_EN);
+}
+
 static int rmi_check_version(void)
 {
 	struct arm_smccc_res res;

---

## [34] Steven Price — 2025-12-17
*Subject: [PATCH v12 33/46] arm64: RMI: Always use 4k pages for realms*

Guest_memfd doesn't yet natively support huge pages, and there are
currently difficulties for a VMM to manage huge pages efficiently so for
now always split up mappings to PTE (4k).

The two issues that need progressing before supporting huge pages for
realms are:

 1. guest_memfd needs to be able to allocate from an appropriate
    allocator which can provide huge pages.

 2. The VMM needs to be able to repurpose private memory for a shared
    mapping when the guest VM requests memory is transitioned. Because
    this can happen at a 4k granularity it isn't possible to
    free/reallocate while huge pages are in use. Allowing the VMM to
    mmap() the shared portion of a huge page would allow the huge page
    to be recreated when the memory is unshared and made protected again.

These two issues are not specific to realms and don't affect the realm
API, so for now just break everything down to 4k pages in the RMM
controlled stage 2. Future work can add huge page support without
changing the uAPI.

Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
---
Changes since v7:
 * Rewritten commit message
---
 arch/arm64/kvm/mmu.c | 7 +++++--
 1 file changed, 5 insertions(+), 2 deletions(-)

diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index 860c42aabcf0..c30d7be27361 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -1762,11 +1762,14 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 	write_fault = kvm_is_write_fault(vcpu);
 
 	/*
-	 * Realms cannot map protected pages read-only
+	 * Realms cannot map protected pages read-only, also force PTE mappings
+	 * for Realms.
 	 * FIXME: It should be possible to map unprotected pages read-only
 	 */
-	if (vcpu_is_rec(vcpu))
+	if (vcpu_is_rec(vcpu)) {
 		write_fault = true;
+		force_pte = true;
+	}
 
 	exec_fault = kvm_vcpu_trap_is_exec_fault(vcpu);
 	VM_WARN_ON_ONCE(write_fault && exec_fault);

---

## [35] Steven Price — 2025-12-17
*Subject: [PATCH v12 34/46] arm64: RMI: Prevent Device mappings for Realms*

Physical device assignment is not supported by RMM v1.0, so it
doesn't make much sense to allow device mappings within the realm.
Prevent them when the guest is a realm.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes from v6:
 * Fix the check in user_mem_abort() to prevent all pages that are not
   guest_memfd() from being mapped into the protected half of the IPA.
Changes from v5:
 * Also prevent accesses in user_mem_abort()
---
 arch/arm64/kvm/mmu.c | 13 +++++++++++++
 1 file changed, 13 insertions(+)

diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index c30d7be27361..e71ef41fb6b1 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -1221,6 +1221,10 @@ int kvm_phys_addr_ioremap(struct kvm *kvm, phys_addr_t guest_ipa,
 	if (is_protected_kvm_enabled())
 		return -EPERM;
 
+	/* We don't support mapping special pages into a Realm */
+	if (kvm_is_realm(kvm))
+		return -EPERM;
+
 	size += offset_in_page(guest_ipa);
 	guest_ipa &= PAGE_MASK;
 
@@ -1955,6 +1959,15 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 		return ret;
 	}
 
+	/*
+	 * For now we shouldn't be hitting protected addresses because they are
+	 * handled in private_memslot_fault(). In the future this check may be
+	 * relaxed to support e.g. protected devices.
+	 */
+	if (vcpu_is_rec(vcpu) &&
+	    kvm_gpa_from_fault(kvm, fault_ipa) == fault_ipa)
+		return -EINVAL;
+
 	if (nested)
 		adjust_nested_fault_perms(nested, &prot, &writable);

---

## [36] Steven Price — 2025-12-17
*Subject: [PATCH v12 35/46] HACK: Restore per-CPU cpu_armpmu pointer*

Commit fa9d27773873 ("perf: arm_pmu: Kill last use of per-CPU cpu_armpmu
pointer") removed the per-CPU cpu_armpmu. Rather than refactoring the
code to deal with this just reintroduce it. The CCA PMU code will be
changing when switching to the RMM v2.0 ABI and will need completely
reworking.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 drivers/perf/arm_pmu.c       | 5 +++++
 include/linux/perf/arm_pmu.h | 2 ++
 2 files changed, 7 insertions(+)

diff --git a/drivers/perf/arm_pmu.c b/drivers/perf/arm_pmu.c
index 973a027d9063..c94494db06f5 100644
--- a/drivers/perf/arm_pmu.c
+++ b/drivers/perf/arm_pmu.c
@@ -104,6 +104,7 @@ static const struct pmu_irq_ops percpu_pmunmi_ops = {
 	.free_pmuirq = armpmu_free_percpu_pmunmi
 };
 
+DEFINE_PER_CPU(struct arm_pmu *, cpu_armpmu);
 static DEFINE_PER_CPU(int, cpu_irq);
 static DEFINE_PER_CPU(const struct pmu_irq_ops *, cpu_irq_ops);
 
@@ -724,6 +725,8 @@ static int arm_perf_starting_cpu(unsigned int cpu, struct hlist_node *node)
 	if (pmu->reset)
 		pmu->reset(pmu);
 
+	per_cpu(cpu_armpmu, cpu) = pmu;
+
 	irq = armpmu_get_cpu_irq(pmu, cpu);
 	if (irq)
 		per_cpu(cpu_irq_ops, cpu)->enable_pmuirq(irq);
@@ -743,6 +746,8 @@ static int arm_perf_teardown_cpu(unsigned int cpu, struct hlist_node *node)
 	if (irq)
 		per_cpu(cpu_irq_ops, cpu)->disable_pmuirq(irq);
 
+	per_cpu(cpu_armpmu, cpu) = NULL;
+
 	return 0;
 }
 
diff --git a/include/linux/perf/arm_pmu.h b/include/linux/perf/arm_pmu.h
index 52b37f7bdbf9..e1be4a6c8b43 100644
--- a/include/linux/perf/arm_pmu.h
+++ b/include/linux/perf/arm_pmu.h
@@ -133,6 +133,8 @@ struct arm_pmu {
 
 #define to_arm_pmu(p) (container_of(p, struct arm_pmu, pmu))
 
+DECLARE_PER_CPU(struct arm_pmu *, cpu_armpmu);
+
 u64 armpmu_event_update(struct perf_event *event);
 
 int armpmu_event_set_period(struct perf_event *event);

---

## [37] Steven Price — 2025-12-17
*Subject: [PATCH v12 36/46] arm_pmu: Provide a mechanism for disabling the physical IRQ*

Arm CCA assigns the physical PMU device to the guest running in realm
world, however the IRQs are routed via the host. To enter a realm guest
while a PMU IRQ is pending it is necessary to block the physical IRQ to
prevent an immediate exit. Provide a mechanism in the PMU driver for KVM
to control the physical IRQ.

Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
---
v3: Add a dummy function for the !CONFIG_ARM_PMU case.
---
 drivers/perf/arm_pmu.c       | 15 +++++++++++++++
 include/linux/perf/arm_pmu.h |  5 +++++
 2 files changed, 20 insertions(+)

diff --git a/drivers/perf/arm_pmu.c b/drivers/perf/arm_pmu.c
index c94494db06f5..6705c61c73c2 100644
--- a/drivers/perf/arm_pmu.c
+++ b/drivers/perf/arm_pmu.c
@@ -751,6 +751,21 @@ static int arm_perf_teardown_cpu(unsigned int cpu, struct hlist_node *node)
 	return 0;
 }
 
+void arm_pmu_set_phys_irq(bool enable)
+{
+	int cpu = get_cpu();
+	struct arm_pmu *pmu = per_cpu(cpu_armpmu, cpu);
+	int irq;
+
+	irq = armpmu_get_cpu_irq(pmu, cpu);
+	if (irq && !enable)
+		per_cpu(cpu_irq_ops, cpu)->disable_pmuirq(irq);
+	else if (irq && enable)
+		per_cpu(cpu_irq_ops, cpu)->enable_pmuirq(irq);
+
+	put_cpu();
+}
+
 #ifdef CONFIG_CPU_PM
 static void cpu_pm_pmu_setup(struct arm_pmu *armpmu, unsigned long cmd)
 {
diff --git a/include/linux/perf/arm_pmu.h b/include/linux/perf/arm_pmu.h
index e1be4a6c8b43..de49f92f6ebf 100644
--- a/include/linux/perf/arm_pmu.h
+++ b/include/linux/perf/arm_pmu.h
@@ -186,6 +186,7 @@ void kvm_host_pmu_init(struct arm_pmu *pmu);
 #endif
 
 bool arm_pmu_irq_is_nmi(void);
+void arm_pmu_set_phys_irq(bool enable);
 
 /* Internal functions only for core arm_pmu code */
 struct arm_pmu *armpmu_alloc(void);
@@ -196,6 +197,10 @@ void armpmu_free_irq(struct arm_pmu * __percpu *armpmu, int irq, int cpu);
 
 #define ARMV8_PMU_PDEV_NAME "armv8-pmu"
 
+#else /* CONFIG_ARM_PMU */
+
+static inline void arm_pmu_set_phys_irq(bool enable) {}
+
 #endif /* CONFIG_ARM_PMU */
 
 #define ARMV8_SPE_PDEV_NAME "arm,spe-v1"

---

## [38] Steven Price — 2025-12-17
*Subject: [PATCH v12 37/46] arm64: RMI: Enable PMU support with a realm guest*

Use the PMU registers from the RmiRecExit structure to identify when an
overflow interrupt is due and inject it into the guest. Also hook up the
configuration option for enabling the PMU within the guest.

When entering a realm guest with a PMU interrupt pending, it is
necessary to disable the physical interrupt. Otherwise when the RMM
restores the PMU state the physical interrupt will trigger causing an
immediate exit back to the host. The guest is expected to acknowledge
the interrupt causing a host exit (to update the GIC state) which gives
the opportunity to re-enable the physical interrupt before the next PMU
event.

Number of PMU counters is configured by the VMM by writing to PMCR.N.

Reviewed-by: Gavin Shan <gshan@redhat.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v2:
 * Add a macro kvm_pmu_get_irq_level() to avoid compile issues when PMU
   support is disabled.
---
 arch/arm64/kvm/arm.c      | 11 +++++++++++
 arch/arm64/kvm/guest.c    |  7 +++++++
 arch/arm64/kvm/pmu-emul.c |  3 +++
 arch/arm64/kvm/rmi.c      |  8 ++++++++
 arch/arm64/kvm/sys_regs.c |  5 +++--
 include/kvm/arm_pmu.h     |  4 ++++
 6 files changed, 36 insertions(+), 2 deletions(-)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index f8255de92902..b2e1401cc223 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -14,6 +14,7 @@
 #include <linux/vmalloc.h>
 #include <linux/fs.h>
 #include <linux/mman.h>
+#include <linux/perf/arm_pmu.h>
 #include <linux/sched.h>
 #include <linux/kvm.h>
 #include <linux/kvm_irqfd.h>
@@ -1264,6 +1265,8 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 	run->exit_reason = KVM_EXIT_UNKNOWN;
 	run->flags = 0;
 	while (ret > 0) {
+		bool pmu_stopped = false;
+
 		/*
 		 * Check conditions before entering the guest
 		 */
@@ -1289,6 +1292,11 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 		if (kvm_vcpu_has_pmu(vcpu))
 			kvm_pmu_flush_hwstate(vcpu);
 
+		if (vcpu_is_rec(vcpu) && kvm_pmu_get_irq_level(vcpu)) {
+			pmu_stopped = true;
+			arm_pmu_set_phys_irq(false);
+		}
+
 		local_irq_disable();
 
 		kvm_vgic_flush_hwstate(vcpu);
@@ -1397,6 +1405,9 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 
 		preempt_enable();
 
+		if (pmu_stopped)
+			arm_pmu_set_phys_irq(true);
+
 		/*
 		 * The ARMv8 architecture doesn't give the hypervisor
 		 * a mechanism to prevent a guest from dropping to AArch32 EL0
diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index d9f392cb2759..14302130d341 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -735,6 +735,8 @@ int kvm_arm_get_reg(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg)
 	return kvm_arm_sys_reg_get_reg(vcpu, reg);
 }
 
+#define KVM_REG_ARM_PMCR_EL0		ARM64_SYS_REG(3, 3, 9, 12, 0)
+
 /*
  * The RMI ABI only enables setting some GPRs and PC. The selection of GPRs
  * that are available depends on the Realm state and the reason for the last
@@ -749,6 +751,11 @@ static bool validate_realm_set_reg(struct kvm_vcpu *vcpu,
 		u64 off = core_reg_offset_from_id(reg->id);
 
 		return kvm_realm_validate_core_reg(off);
+	} else {
+		switch (reg->id) {
+		case KVM_REG_ARM_PMCR_EL0:
+			return true;
+		}
 	}
 
 	return false;
diff --git a/arch/arm64/kvm/pmu-emul.c b/arch/arm64/kvm/pmu-emul.c
index b03dbda7f1ab..41331f883780 100644
--- a/arch/arm64/kvm/pmu-emul.c
+++ b/arch/arm64/kvm/pmu-emul.c
@@ -374,6 +374,9 @@ static bool kvm_pmu_overflow_status(struct kvm_vcpu *vcpu)
 {
 	u64 reg = __vcpu_sys_reg(vcpu, PMOVSSET_EL0);
 
+	if (vcpu_is_rec(vcpu))
+		return vcpu->arch.rec.run->exit.pmu_ovf_status;
+
 	reg &= __vcpu_sys_reg(vcpu, PMINTENSET_EL1);
 
 	/*
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 7ef5d7f48d0b..1d26fd893caf 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -582,6 +582,11 @@ static int realm_create_rd(struct kvm *kvm)
 	params->rtt_base = kvm->arch.mmu.pgd_phys;
 	params->vmid = realm->vmid;
 
+	if (kvm->arch.arm_pmu) {
+		params->pmu_num_ctrs = kvm->arch.nr_pmu_counters;
+		params->flags |= RMI_REALM_PARAM_FLAG_PMU;
+	}
+
 	params_phys = virt_to_phys(params);
 
 	if (rmi_realm_create(rd_phys, params_phys)) {
@@ -1371,6 +1376,9 @@ static int kvm_create_rec(struct kvm_vcpu *vcpu)
 	if (!vcpu_has_feature(vcpu, KVM_ARM_VCPU_PSCI_0_2))
 		return -EINVAL;
 
+	if (vcpu->kvm->arch.arm_pmu && !kvm_vcpu_has_pmu(vcpu))
+		return -EINVAL;
+
 	BUILD_BUG_ON(sizeof(*params) > PAGE_SIZE);
 	BUILD_BUG_ON(sizeof(*rec->run) > PAGE_SIZE);
 
diff --git a/arch/arm64/kvm/sys_regs.c b/arch/arm64/kvm/sys_regs.c
index c8fd7c6a12a1..af641939a033 100644
--- a/arch/arm64/kvm/sys_regs.c
+++ b/arch/arm64/kvm/sys_regs.c
@@ -1360,8 +1360,9 @@ static int set_pmcr(struct kvm_vcpu *vcpu, const struct sys_reg_desc *r,
 	 * implements. Ignore this error to maintain compatibility
 	 * with the existing KVM behavior.
 	 */
-	if (!kvm_vm_has_ran_once(kvm) &&
-	    !vcpu_has_nv(vcpu)	      &&
+	if (!kvm_vm_has_ran_once(kvm)  &&
+	    !kvm_realm_is_created(kvm) &&
+	    !vcpu_has_nv(vcpu)	       &&
 	    new_n <= kvm_arm_pmu_get_max_counters(kvm))
 		kvm->arch.nr_pmu_counters = new_n;
 
diff --git a/include/kvm/arm_pmu.h b/include/kvm/arm_pmu.h
index 96754b51b411..da32f1bd9f8c 100644
--- a/include/kvm/arm_pmu.h
+++ b/include/kvm/arm_pmu.h
@@ -70,6 +70,8 @@ void kvm_vcpu_pmu_restore_guest(struct kvm_vcpu *vcpu);
 void kvm_vcpu_pmu_restore_host(struct kvm_vcpu *vcpu);
 void kvm_vcpu_pmu_resync_el0(void);
 
+#define kvm_pmu_get_irq_level(vcpu) ((vcpu)->arch.pmu.irq_level)
+
 #define kvm_vcpu_has_pmu(vcpu)					\
 	(vcpu_has_feature(vcpu, KVM_ARM_VCPU_PMU_V3))
 
@@ -157,6 +159,8 @@ static inline u64 kvm_pmu_get_pmceid(struct kvm_vcpu *vcpu, bool pmceid1)
 	return 0;
 }
 
+#define kvm_pmu_get_irq_level(vcpu) (false)
+
 #define kvm_vcpu_has_pmu(vcpu)		({ false; })
 static inline void kvm_pmu_update_vcpu_events(struct kvm_vcpu *vcpu) {}
 static inline void kvm_vcpu_pmu_restore_guest(struct kvm_vcpu *vcpu) {}

---

## [39] Steven Price — 2025-12-17
*Subject: [PATCH v12 38/46] arm64: RMI: Propagate number of breakpoints and watchpoints to userspace*

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
 arch/arm64/kvm/rmi.c             | 22 ++++++++++++++++++++++
 arch/arm64/kvm/sys_regs.c        |  2 +-
 3 files changed, 25 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index 82280c138935..f36d3c845836 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -89,6 +89,8 @@ void kvm_init_rmi(void);
 u32 kvm_realm_ipa_limit(void);
 u32 kvm_realm_vgic_nr_lr(void);
 
+u64 kvm_realm_reset_id_aa64dfr0_el1(const struct kvm_vcpu *vcpu, u64 val);
+
 bool kvm_rmi_supports_sve(void);
 
 int kvm_init_realm_vm(struct kvm *kvm);
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 1d26fd893caf..1c5257636ef1 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -92,6 +92,28 @@ u32 kvm_realm_vgic_nr_lr(void)
 	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_GICV3_NUM_LRS);
 }
 
+u64 kvm_realm_reset_id_aa64dfr0_el1(const struct kvm_vcpu *vcpu, u64 val)
+{
+	u32 bps = u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_NUM_BPS);
+	u32 wps = u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_NUM_WPS);
+	u32 ctx_cmps;
+
+	if (!kvm_is_realm(vcpu->kvm))
+		return val;
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
 	/*
diff --git a/arch/arm64/kvm/sys_regs.c b/arch/arm64/kvm/sys_regs.c
index af641939a033..70b51b5cdea8 100644
--- a/arch/arm64/kvm/sys_regs.c
+++ b/arch/arm64/kvm/sys_regs.c
@@ -2043,7 +2043,7 @@ static u64 sanitise_id_aa64dfr0_el1(const struct kvm_vcpu *vcpu, u64 val)
 	/* Hide BRBE from guests */
 	val &= ~ID_AA64DFR0_EL1_BRBE_MASK;
 
-	return val;
+	return kvm_realm_reset_id_aa64dfr0_el1(vcpu, val);
 }
 
 /*

---

## [40] Steven Price — 2025-12-17
*Subject: [PATCH v12 39/46] arm64: RMI: Set breakpoint parameters through SET_ONE_REG*

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
 arch/arm64/kvm/guest.c    |  2 ++
 arch/arm64/kvm/rmi.c      |  3 +++
 arch/arm64/kvm/sys_regs.c | 17 +++++++++++------
 3 files changed, 16 insertions(+), 6 deletions(-)

diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index 14302130d341..7cf919db1adc 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -736,6 +736,7 @@ int kvm_arm_get_reg(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg)
 }
 
 #define KVM_REG_ARM_PMCR_EL0		ARM64_SYS_REG(3, 3, 9, 12, 0)
+#define KVM_REG_ARM_ID_AA64DFR0_EL1	ARM64_SYS_REG(3, 0, 0, 5, 0)
 
 /*
  * The RMI ABI only enables setting some GPRs and PC. The selection of GPRs
@@ -754,6 +755,7 @@ static bool validate_realm_set_reg(struct kvm_vcpu *vcpu,
 	} else {
 		switch (reg->id) {
 		case KVM_REG_ARM_PMCR_EL0:
+		case KVM_REG_ARM_ID_AA64DFR0_EL1:
 			return true;
 		}
 	}
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 1c5257636ef1..5f3164539bfe 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -567,6 +567,7 @@ static int realm_create_rd(struct kvm *kvm)
 	void *rd = NULL;
 	phys_addr_t rd_phys, params_phys;
 	size_t pgd_size = kvm_pgtable_stage2_pgd_size(kvm->arch.mmu.vtcr);
+	u64 dfr0 = kvm_read_vm_id_reg(kvm, SYS_ID_AA64DFR0_EL1);
 	int i, r;
 	int rtt_num_start;
 
@@ -603,6 +604,8 @@ static int realm_create_rd(struct kvm *kvm)
 	params->rtt_num_start = rtt_num_start;
 	params->rtt_base = kvm->arch.mmu.pgd_phys;
 	params->vmid = realm->vmid;
+	params->num_bps = SYS_FIELD_GET(ID_AA64DFR0_EL1, BRPs, dfr0);
+	params->num_wps = SYS_FIELD_GET(ID_AA64DFR0_EL1, WRPs, dfr0);
 
 	if (kvm->arch.arm_pmu) {
 		params->pmu_num_ctrs = kvm->arch.nr_pmu_counters;
diff --git a/arch/arm64/kvm/sys_regs.c b/arch/arm64/kvm/sys_regs.c
index 70b51b5cdea8..f93e37bc77aa 100644
--- a/arch/arm64/kvm/sys_regs.c
+++ b/arch/arm64/kvm/sys_regs.c
@@ -2072,6 +2072,9 @@ static int set_id_aa64dfr0_el1(struct kvm_vcpu *vcpu,
 {
 	u8 debugver = SYS_FIELD_GET(ID_AA64DFR0_EL1, DebugVer, val);
 	u8 pmuver = SYS_FIELD_GET(ID_AA64DFR0_EL1, PMUVer, val);
+	u8 bps = SYS_FIELD_GET(ID_AA64DFR0_EL1, BRPs, val);
+	u8 wps = SYS_FIELD_GET(ID_AA64DFR0_EL1, WRPs, val);
+	u8 ctx_cmps = SYS_FIELD_GET(ID_AA64DFR0_EL1, CTX_CMPs, val);
 
 	/*
 	 * Prior to commit 3d0dba5764b9 ("KVM: arm64: PMU: Move the
@@ -2091,10 +2094,11 @@ static int set_id_aa64dfr0_el1(struct kvm_vcpu *vcpu,
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
@@ -2329,10 +2333,11 @@ static int set_id_reg(struct kvm_vcpu *vcpu, const struct sys_reg_desc *rd,
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

## [41] Steven Price — 2025-12-17
*Subject: [PATCH v12 40/46] arm64: RMI: Initialize PMCR.N with number counter supported by RMM*

From: Jean-Philippe Brucker <jean-philippe@linaro.org>

Provide an accurate number of available PMU counters to userspace when
setting up a Realm.

Signed-off-by: Jean-Philippe Brucker <jean-philippe@linaro.org>
Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Reviewed-by: Joey Gouly <joey.gouly@arm.com>
---
 arch/arm64/include/asm/kvm_rmi.h | 1 +
 arch/arm64/kvm/pmu-emul.c        | 3 +++
 arch/arm64/kvm/rmi.c             | 5 +++++
 3 files changed, 9 insertions(+)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index f36d3c845836..39770d9e9fcb 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -88,6 +88,7 @@ struct realm_rec {
 void kvm_init_rmi(void);
 u32 kvm_realm_ipa_limit(void);
 u32 kvm_realm_vgic_nr_lr(void);
+u8 kvm_realm_max_pmu_counters(void);
 
 u64 kvm_realm_reset_id_aa64dfr0_el1(const struct kvm_vcpu *vcpu, u64 val);
 
diff --git a/arch/arm64/kvm/pmu-emul.c b/arch/arm64/kvm/pmu-emul.c
index 41331f883780..6604aa982d02 100644
--- a/arch/arm64/kvm/pmu-emul.c
+++ b/arch/arm64/kvm/pmu-emul.c
@@ -1014,6 +1014,9 @@ u8 kvm_arm_pmu_get_max_counters(struct kvm *kvm)
 {
 	struct arm_pmu *arm_pmu = kvm->arch.arm_pmu;
 
+	if (kvm_is_realm(kvm))
+		return kvm_realm_max_pmu_counters();
+
 	/*
 	 * PMUv3 requires that all event counters are capable of counting any
 	 * event, though the same may not be true of non-PMUv3 hardware.
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 5f3164539bfe..4e1c7bc2f52a 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -92,6 +92,11 @@ u32 kvm_realm_vgic_nr_lr(void)
 	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_GICV3_NUM_LRS);
 }
 
+u8 kvm_realm_max_pmu_counters(void)
+{
+	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_PMU_NUM_CTRS);
+}
+
 u64 kvm_realm_reset_id_aa64dfr0_el1(const struct kvm_vcpu *vcpu, u64 val)
 {
 	u32 bps = u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_NUM_BPS);

---

## [42] Steven Price — 2025-12-17
*Subject: [PATCH v12 41/46] arm64: RMI: Propagate max SVE vector length from RMM*

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
index 7590d86c78a5..97c747cfb5be 100644
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
index 39770d9e9fcb..073b999bcd96 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -89,6 +89,7 @@ void kvm_init_rmi(void);
 u32 kvm_realm_ipa_limit(void);
 u32 kvm_realm_vgic_nr_lr(void);
 u8 kvm_realm_max_pmu_counters(void);
+unsigned int kvm_realm_sve_max_vl(void);
 
 u64 kvm_realm_reset_id_aa64dfr0_el1(const struct kvm_vcpu *vcpu, u64 val);
 
diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index 7cf919db1adc..705c2ccc335d 100644
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
index 4bbf58892928..08883c9e848f 100644
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
index 4e1c7bc2f52a..b719c39329c8 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -97,6 +97,12 @@ u8 kvm_realm_max_pmu_counters(void)
 	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_PMU_NUM_CTRS);
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

## [43] Steven Price — 2025-12-17
*Subject: [PATCH v12 42/46] arm64: RMI: Configure max SVE vector length for a Realm*

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
index 705c2ccc335d..999edf0b5219 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -361,7 +361,7 @@ static int set_sve_vls(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg)
 	if (!vcpu_has_sve(vcpu))
 		return -ENOENT;
 
-	if (kvm_arm_vcpu_sve_finalized(vcpu))
+	if (kvm_arm_vcpu_sve_finalized(vcpu) || kvm_realm_is_created(vcpu->kvm))
 		return -EPERM; /* too late! */
 
 	if (WARN_ON(vcpu->arch.sve_state))
@@ -756,6 +756,7 @@ static bool validate_realm_set_reg(struct kvm_vcpu *vcpu,
 		switch (reg->id) {
 		case KVM_REG_ARM_PMCR_EL0:
 		case KVM_REG_ARM_ID_AA64DFR0_EL1:
+		case KVM_REG_ARM64_SVE_VLS:
 			return true;
 		}
 	}
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index b719c39329c8..657d70eab0ab 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -557,6 +557,39 @@ static void realm_unmap_shared_range(struct kvm *kvm,
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
 /* Calculate the number of s2 root rtts needed */
 static int realm_num_root_rtts(struct realm *realm)
 {
@@ -623,6 +656,10 @@ static int realm_create_rd(struct kvm *kvm)
 		params->flags |= RMI_REALM_PARAM_FLAG_PMU;
 	}
 
+	r = realm_init_sve_param(kvm, params);
+	if (r)
+		goto out_undelegate_tables;
+
 	params_phys = virt_to_phys(params);
 
 	if (rmi_realm_create(rd_phys, params_phys)) {

---

## [44] Steven Price — 2025-12-17
*Subject: [PATCH v12 43/46] arm64: RMI: Provide register list for unfinalized RMI RECs*

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
index b2e1401cc223..88a807a78c04 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -1883,10 +1883,6 @@ long kvm_arch_vcpu_ioctl(struct file *filp,
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
index 999edf0b5219..2c4db2d1a6ca 100644
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

## [45] Steven Price — 2025-12-17
*Subject: [PATCH v12 44/46] arm64: RMI: Provide accurate register list*

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
 arch/arm64/kvm/sys_regs.c   | 29 +++++++++++++++++++++++------
 3 files changed, 31 insertions(+), 8 deletions(-)

diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index 2c4db2d1a6ca..23fdb2ee8a61 100644
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
index f93e37bc77aa..32b7be718e54 100644
--- a/arch/arm64/kvm/sys_regs.c
+++ b/arch/arm64/kvm/sys_regs.c
@@ -5401,18 +5401,18 @@ int kvm_arm_sys_reg_set_reg(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg
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
@@ -5456,11 +5456,28 @@ static bool copy_reg_to_user(const struct sys_reg_desc *reg, u64 __user **uind)
 	return true;
 }
 
+static inline bool kvm_realm_sys_reg_hidden_user(const struct kvm_vcpu *vcpu,
+						 u64 reg)
+{
+	if (!kvm_is_realm(vcpu->kvm))
+		return false;
+
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
+	if (kvm_realm_sys_reg_hidden_user(vcpu, reg_to_encoding(rd)))
+		return 0;
+
 	/*
 	 * Ignore registers we trap but don't save,
 	 * and for which no custom user accessor is provided.
@@ -5498,7 +5515,7 @@ static int walk_sys_regs(struct kvm_vcpu *vcpu, u64 __user *uind)
 
 unsigned long kvm_arm_num_sys_reg_descs(struct kvm_vcpu *vcpu)
 {
-	return num_demux_regs()
+	return num_demux_regs(vcpu)
 		+ walk_sys_regs(vcpu, (u64 __user *)NULL);
 }
 
@@ -5511,7 +5528,7 @@ int kvm_arm_copy_sys_reg_indices(struct kvm_vcpu *vcpu, u64 __user *uindices)
 		return err;
 	uindices += err;
 
-	return write_demux_regids(uindices);
+	return write_demux_regids(vcpu, uindices);
 }
 
 #define KVM_ARM_FEATURE_ID_RANGE_INDEX(r)			\

---

## [46] Steven Price — 2025-12-17
*Subject: [PATCH v12 45/46] KVM: arm64: Expose KVM_ARM_VCPU_REC to user space*

Increment KVM_VCPU_MAX_FEATURES to expose the new capability to user
space.

Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
---
Changes since v8:
 * Since NV is now merged and enabled, this no longer conflicts with it.
---
 arch/arm64/include/asm/kvm_host.h | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/kvm_host.h b/arch/arm64/include/asm/kvm_host.h
index 97c747cfb5be..7e3221d102a9 100644
--- a/arch/arm64/include/asm/kvm_host.h
+++ b/arch/arm64/include/asm/kvm_host.h
@@ -40,7 +40,7 @@
 
 #define KVM_MAX_VCPUS VGIC_V3_MAX_CPUS
 
-#define KVM_VCPU_MAX_FEATURES 9
+#define KVM_VCPU_MAX_FEATURES 10
 #define KVM_VCPU_VALID_FEATURES	(BIT(KVM_VCPU_MAX_FEATURES) - 1)
 
 #define KVM_REQ_SLEEP \

---

## [47] Steven Price — 2025-12-17
*Subject: [PATCH v12 46/46] arm64: RMI: Enable realms to be created*

All the pieces are now in place, so enable kvm_rmi_is_available when the
RMM is detected.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/kvm/rmi.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 657d70eab0ab..0e470f31d46a 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -1659,5 +1659,5 @@ void kvm_init_rmi(void)
 	if (rmi_vmid_init())
 		return;
 
-	/* Future patch will enable static branch kvm_rmi_is_available */
+	static_branch_enable(&kvm_rmi_is_available);
 }

---

## [48] Suzuki K Poulose — 2025-12-17
*Subject: Re: [PATCH v12 11/46] arm64: RMI: Activate realm on first VCPU run*

On 17/12/2025 10:10, Steven Price wrote:
> When a VCPU migrates to another physical CPU check if this is the first
> time the guest has run, and if so activate the realm.

super minor nit: We could do this check before create the realm, within
the config_lock'ed region.

Suzuki

---

## [49] Marc Zyngier — 2025-12-17
*Subject: Re: [PATCH v12 00/46] arm64: Support for Arm CCA in KVM*

On Wed, 17 Dec 2025 10:10:37 +0000,
Steven Price <steven.price@arm.com> wrote:
> 
> This series adds support for running protected VMs using KVM under the

What are the relevant patches? I'd rather not look at the non-2.0
patches at all, given that they are pretty meaningless for KVM.

	M.

---

## [50] Steven Price — 2025-12-17
*Subject: Re: [PATCH v12 00/46] arm64: Support for Arm CCA in KVM*

On 17/12/2025 14:55, Marc Zyngier wrote:
> On Wed, 17 Dec 2025 10:10:37 +0000,
> Steven Price <steven.price@arm.com> wrote:

Sorry, I really should have included that in the cover letter.

Patch 6 defines the uAPI - so I'd welcome feedback on whether that is
now the right shape.

Patch 11 shows how the "first VCPU run" is handled with a hook in
kvm_arch_vcpu_run_pid_change() (similar to pKVM).

Patch 20 is implementation of the new populate ioctl.

Patch 21 handles the INIT_RIPAS by assuming that any memslot with gmem
is private and should be RIPAS_RAM.

Patch 27 handles the PSCI requests which is the other ioctl. No real
change from the previous posting, but it would be good to know if there
are any issues with the uAPI here.

I think other than those there's either very little change from the
previous series, or it's likely to change with RMM v2.0.

Thanks,
Steve

---

## [51] kernel test robot — 2025-12-20
*Subject: Re: [PATCH v12 19/46] KVM: arm64: Expose support for private memory*

Hi Steven,

kernel test robot noticed the following build errors:

[auto build test ERROR on linus/master]
[also build test ERROR on v6.19-rc1 next-20251219]
[cannot apply to kvmarm/next kvm/queue kvm/next arm64/for-next/core kvm/linux-next]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Steven-Price/kvm-arm64-Include-kvm_emulate-h-in-kvm-arm_psci-h/20251218-030351
base:   linus/master
patch link:    https://lore.kernel.org/r/20251217101125.91098-20-steven.price%40arm.com
patch subject: [PATCH v12 19/46] KVM: arm64: Expose support for private memory
config: arm64-allnoconfig (https://download.01.org/0day-ci/archive/20251220/202512202102.XFW5Jfym-lkp@intel.com/config)
compiler: aarch64-linux-gcc (GCC) 15.1.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20251220/202512202102.XFW5Jfym-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202512202102.XFW5Jfym-lkp@intel.com/

All errors (new ones prefixed by >>):

   In file included from include/linux/kvm_host.h:45,
                    from arch/arm64/kernel/asm-offsets.c:16:
>> include/linux/kvm_host.h:725:45: error: expected identifier or '(' before 'struct'
     725 | static inline bool kvm_arch_has_private_mem(struct kvm *kvm)
         |                                             ^~~~~~
   arch/arm64/include/asm/kvm_host.h:1465:41: note: in definition of macro 'kvm_arch_has_private_mem'
    1465 | #define kvm_arch_has_private_mem(kvm) ((kvm)->arch.is_realm)
         |                                         ^~~
>> arch/arm64/include/asm/kvm_host.h:1465:45: error: expected ')' before '->' token
    1465 | #define kvm_arch_has_private_mem(kvm) ((kvm)->arch.is_realm)
         |                                             ^~
   include/linux/kvm_host.h:725:20: note: in expansion of macro 'kvm_arch_has_private_mem'
     725 | static inline bool kvm_arch_has_private_mem(struct kvm *kvm)
         |                    ^~~~~~~~~~~~~~~~~~~~~~~~
   make[3]: *** [scripts/Makefile.build:182: arch/arm64/kernel/asm-offsets.s] Error 1
   make[3]: Target 'prepare' not remade because of errors.
   make[2]: *** [Makefile:1314: prepare0] Error 2
   make[2]: Target 'prepare' not remade because of errors.
   make[1]: *** [Makefile:248: __sub-make] Error 2
   make[1]: Target 'prepare' not remade because of errors.
   make: *** [Makefile:248: __sub-make] Error 2
   make: Target 'prepare' not remade because of errors.


vim +725 include/linux/kvm_host.h

f481b069e67437 Paolo Bonzini       2015-05-17  723  
d1e54dd08f163a Fuad Tabba          2025-07-29  724  #ifndef CONFIG_KVM_GENERIC_MEMORY_ATTRIBUTES
a7800aa80ea4d5 Sean Christopherson 2023-11-13 @725  static inline bool kvm_arch_has_private_mem(struct kvm *kvm)
a7800aa80ea4d5 Sean Christopherson 2023-11-13  726  {
a7800aa80ea4d5 Sean Christopherson 2023-11-13  727  	return false;
a7800aa80ea4d5 Sean Christopherson 2023-11-13  728  }
a7800aa80ea4d5 Sean Christopherson 2023-11-13  729  #endif
a7800aa80ea4d5 Sean Christopherson 2023-11-13  730

---

## [52] kernel test robot — 2025-12-20
*Subject: Re: [PATCH v12 19/46] KVM: arm64: Expose support for private memory*

Hi Steven,

kernel test robot noticed the following build errors:

[auto build test ERROR on linus/master]
[also build test ERROR on v6.19-rc1 next-20251219]
[cannot apply to kvmarm/next kvm/queue kvm/next arm64/for-next/core kvm/linux-next]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Steven-Price/kvm-arm64-Include-kvm_emulate-h-in-kvm-arm_psci-h/20251218-030351
base:   linus/master
patch link:    https://lore.kernel.org/r/20251217101125.91098-20-steven.price%40arm.com
patch subject: [PATCH v12 19/46] KVM: arm64: Expose support for private memory
config: arm64-randconfig-001-20251219 (https://download.01.org/0day-ci/archive/20251220/202512202152.gapj1OD5-lkp@intel.com/config)
compiler: clang version 22.0.0git (https://github.com/llvm/llvm-project b324c9f4fa112d61a553bf489b5f4f7ceea05ea8)
rustc: rustc 1.88.0 (6b00bc388 2025-06-23)
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20251220/202512202152.gapj1OD5-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202512202152.gapj1OD5-lkp@intel.com/

All errors (new ones prefixed by >>):

   In file included from arch/arm64/kernel/asm-offsets.c:16:
>> include/linux/kvm_host.h:725:45: error: expected identifier or '('
     725 | static inline bool kvm_arch_has_private_mem(struct kvm *kvm)
         |                                             ^
>> include/linux/kvm_host.h:725:45: error: expected ')'
   include/linux/kvm_host.h:725:20: note: to match this '('
     725 | static inline bool kvm_arch_has_private_mem(struct kvm *kvm)
         |                    ^
   arch/arm64/include/asm/kvm_host.h:1465:40: note: expanded from macro 'kvm_arch_has_private_mem'
    1465 | #define kvm_arch_has_private_mem(kvm) ((kvm)->arch.is_realm)
         |                                        ^
   In file included from arch/arm64/kernel/asm-offsets.c:16:
   include/linux/kvm_host.h:725:20: error: expected ')'
     725 | static inline bool kvm_arch_has_private_mem(struct kvm *kvm)
         |                    ^
   arch/arm64/include/asm/kvm_host.h:1465:45: note: expanded from macro 'kvm_arch_has_private_mem'
    1465 | #define kvm_arch_has_private_mem(kvm) ((kvm)->arch.is_realm)
         |                                             ^
   include/linux/kvm_host.h:725:20: note: to match this '('
   arch/arm64/include/asm/kvm_host.h:1465:39: note: expanded from macro 'kvm_arch_has_private_mem'
    1465 | #define kvm_arch_has_private_mem(kvm) ((kvm)->arch.is_realm)
         |                                       ^
   3 errors generated.
   make[3]: *** [scripts/Makefile.build:182: arch/arm64/kernel/asm-offsets.s] Error 1 shuffle=1976660145
   make[3]: Target 'prepare' not remade because of errors.
   make[2]: *** [Makefile:1314: prepare0] Error 2 shuffle=1976660145
   make[2]: Target 'prepare' not remade because of errors.
   make[1]: *** [Makefile:248: __sub-make] Error 2 shuffle=1976660145
   make[1]: Target 'prepare' not remade because of errors.
   make: *** [Makefile:248: __sub-make] Error 2 shuffle=1976660145
   make: Target 'prepare' not remade because of errors.


vim +725 include/linux/kvm_host.h

f481b069e67437 Paolo Bonzini       2015-05-17  723  
d1e54dd08f163a Fuad Tabba          2025-07-29  724  #ifndef CONFIG_KVM_GENERIC_MEMORY_ATTRIBUTES
a7800aa80ea4d5 Sean Christopherson 2023-11-13 @725  static inline bool kvm_arch_has_private_mem(struct kvm *kvm)
a7800aa80ea4d5 Sean Christopherson 2023-11-13  726  {
a7800aa80ea4d5 Sean Christopherson 2023-11-13  727  	return false;
a7800aa80ea4d5 Sean Christopherson 2023-11-13  728  }
a7800aa80ea4d5 Sean Christopherson 2023-11-13  729  #endif
a7800aa80ea4d5 Sean Christopherson 2023-11-13  730

---

## [53] kernel test robot — 2025-12-20
*Subject: Re: [PATCH v12 19/46] KVM: arm64: Expose support for private memory*

Hi Steven,

kernel test robot noticed the following build errors:

[auto build test ERROR on linus/master]
[also build test ERROR on next-20251219]
[cannot apply to kvmarm/next kvm/queue kvm/next arm64/for-next/core kvm/linux-next v6.16-rc1]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Steven-Price/kvm-arm64-Include-kvm_emulate-h-in-kvm-arm_psci-h/20251217-224409
base:   linus/master
patch link:    https://lore.kernel.org/r/20251217101125.91098-20-steven.price%40arm.com
patch subject: [PATCH v12 19/46] KVM: arm64: Expose support for private memory
config: arm64-allnoconfig-bpf (https://download.01.org/0day-ci/archive/20251220/202512201539.ZhAox5t9-lkp@intel.com/config)
compiler: clang version 22.0.0git (https://github.com/llvm/llvm-project ecaf673850beb241957352bd61e95ed34256635f)
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20251220/202512201539.ZhAox5t9-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202512201539.ZhAox5t9-lkp@intel.com/

All errors (new ones prefixed by >>):

   In file included from arch/arm64/kernel/asm-offsets.c:16:
>> ./include/linux/kvm_host.h:725:45: error: expected identifier or '('
     725 | static inline bool kvm_arch_has_private_mem(struct kvm *kvm)
         |                                             ^
>> ./include/linux/kvm_host.h:725:45: error: expected ')'
   ./include/linux/kvm_host.h:725:20: note: to match this '('
     725 | static inline bool kvm_arch_has_private_mem(struct kvm *kvm)
         |                    ^
   ./arch/arm64/include/asm/kvm_host.h:1465:40: note: expanded from macro 'kvm_arch_has_private_mem'
    1465 | #define kvm_arch_has_private_mem(kvm) ((kvm)->arch.is_realm)
         |                                        ^
   In file included from arch/arm64/kernel/asm-offsets.c:16:
   ./include/linux/kvm_host.h:725:20: error: expected ')'
     725 | static inline bool kvm_arch_has_private_mem(struct kvm *kvm)
         |                    ^
   ./arch/arm64/include/asm/kvm_host.h:1465:45: note: expanded from macro 'kvm_arch_has_private_mem'
    1465 | #define kvm_arch_has_private_mem(kvm) ((kvm)->arch.is_realm)
         |                                             ^
   ./include/linux/kvm_host.h:725:20: note: to match this '('
   ./arch/arm64/include/asm/kvm_host.h:1465:39: note: expanded from macro 'kvm_arch_has_private_mem'
    1465 | #define kvm_arch_has_private_mem(kvm) ((kvm)->arch.is_realm)
         |                                       ^
   3 errors generated.


vim +725 ./include/linux/kvm_host.h

f481b069e67437 Paolo Bonzini       2015-05-17  723  
d1e54dd08f163a Fuad Tabba          2025-07-29  724  #ifndef CONFIG_KVM_GENERIC_MEMORY_ATTRIBUTES
a7800aa80ea4d5 Sean Christopherson 2023-11-13 @725  static inline bool kvm_arch_has_private_mem(struct kvm *kvm)
a7800aa80ea4d5 Sean Christopherson 2023-11-13  726  {
a7800aa80ea4d5 Sean Christopherson 2023-11-13  727  	return false;
a7800aa80ea4d5 Sean Christopherson 2023-11-13  728  }
a7800aa80ea4d5 Sean Christopherson 2023-11-13  729  #endif
a7800aa80ea4d5 Sean Christopherson 2023-11-13  730

---

## [54] kernel test robot — 2025-12-20
*Subject: Re: [PATCH v12 20/46] arm64: RMI: Allow populating initial contents*

Hi Steven,

kernel test robot noticed the following build warnings:

[auto build test WARNING on linus/master]
[also build test WARNING on v6.19-rc1 next-20251219]
[cannot apply to kvmarm/next kvm/queue kvm/next arm64/for-next/core kvm/linux-next]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Steven-Price/kvm-arm64-Include-kvm_emulate-h-in-kvm-arm_psci-h/20251218-030351
base:   linus/master
patch link:    https://lore.kernel.org/r/20251217101125.91098-21-steven.price%40arm.com
patch subject: [PATCH v12 20/46] arm64: RMI: Allow populating initial contents
config: arm64-allmodconfig (https://download.01.org/0day-ci/archive/20251220/202512202203.1g4jywFB-lkp@intel.com/config)
compiler: clang version 19.1.7 (https://github.com/llvm/llvm-project cd708029e0b2869e80abe31ddb175f7c35361f90)
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20251220/202512202203.1g4jywFB-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202512202203.1g4jywFB-lkp@intel.com/

All warnings (new ones prefixed by >>):

>> arch/arm64/kvm/rmi.c:805:16: warning: variable 'data_flags' set but not used [-Wunused-but-set-variable]
     805 |         unsigned long data_flags = 0;
         |                       ^
   1 warning generated.


vim +/data_flags +805 arch/arm64/kvm/rmi.c

   801	
   802	int kvm_arm_rmi_populate(struct kvm *kvm,
   803				 struct kvm_arm_rmi_populate *args)
   804	{
 > 805		unsigned long data_flags = 0;
   806		unsigned long ipa_start = args->base;
   807		unsigned long ipa_end = ipa_start + args->size;
   808		int ret;
   809	
   810		if (args->reserved ||
   811		    (args->flags & ~KVM_ARM_RMI_POPULATE_FLAGS_MEASURE) ||
   812		    !IS_ALIGNED(ipa_start, PAGE_SIZE) ||
   813		    !IS_ALIGNED(ipa_end, PAGE_SIZE))
   814			return -EINVAL;
   815	
   816		ret = realm_ensure_created(kvm);
   817		if (ret)
   818			return ret;
   819	
   820		if (args->flags & KVM_ARM_RMI_POPULATE_FLAGS_MEASURE)
   821			data_flags |= RMI_MEASURE_CONTENT;
   822	
   823		ret = populate_region(kvm, gpa_to_gfn(ipa_start),
   824				      args->size >> PAGE_SHIFT,
   825				      args->source_uaddr, args->flags);
   826	
   827		if (ret < 0)
   828			return ret;
   829	
   830		return ret * PAGE_SIZE;
   831	}
   832

---

## [55] Suzuki K Poulose — 2026-01-23
*Subject: Re: [PATCH v12 06/46] arm64: RMI: Define the user ABI*

Hi Steven

On 17/12/2025 10:10, Steven Price wrote:
> There is one CAP which identified the presence of CCA, and two ioctls.
> One ioctl is used to populate memory and the other is used when user

Could we split these changes to the corresponding implementation patches
? That might give us a full picture of how these UAPIs fit in the bigger
picture.

> Signed-off-by: Steven Price <steven.price@arm.com>
> ---

It may be a good idea to spill out the restrictions on calling this,
right ? We expect that the source_uaddr is a separate memory area
from the "DRAM" (in shared mode) ?

Can this be called before/after converting the entire memory of the
Guest to Private ? I believe, it must be done after the "initial
change all of DRAM to private" ?

Suzuki

>   
>   .. _kvm_run:

---

## [56] Alper Gun — 2026-01-23
*Subject: Re: [PATCH v12 22/46] arm64: RMI: Create the realm descriptor*

On Wed, Dec 17, 2025 at 2:13 AM Steven Price <steven.price@arm.com> wrote:
>
> Creating a realm involves first creating a realm descriptor (RD). This

I don't see a way to configure rpv and hash_algo anymore. I assume they
are gone for a minimal userspace interface. Will there be a way to set
them going forward?

> +
> +       params_phys = virt_to_phys(params);

---

## [57] Steven Price — 2026-01-26
*Subject: Re: [PATCH v12 06/46] arm64: RMI: Define the user ABI*

On 23/01/2026 16:47, Suzuki K Poulose wrote:
> Hi Steven
> 

I could do that, but I was deliberately keeping this as a patch which
contains the uABI interface so that the whole uABI is visible in one
place. I was trying to reduce the amount to review for those who aren't
so interested in the implementation details (especially for this series
where we know it's going to change somewhat with the move to RMM v2.0).

>> Signed-off-by: Steven Price <steven.price@arm.com>
>> ---

Yes - I'd tried to say that by mentioning it's a "user space pointer",
but I could make that more explicit.

> Can this be called before/after converting the entire memory of the
> Guest to Private ? I believe, it must be done after the "initial

It can be called before or after setting RIPAS and it implicitly sets
RIPAS to RAM (I'll add something to make that explicit).

With RMM v1.0 there's an ugly problem that INIT_RIPAS fails on a region
which is already RIPAS RAM. This should be fixed with RMM v2.0. There's
a workaround in patch 17 currently:

		/* FIXME: Ugly hack to skip regions which are
		 * already RIPAS_RAM
		 */

But that should go away.

Note that with this proposed uAPI there is no mechanism for user space
to directly set the RIPAS - it's assumed that all guestmem_fd regions
should be set to RIPAS RAM at the time of the first VCPU run - which
means the VMM doesn't need to do anything special.

In the future we could consider a guestmem_fd flag or extra ioctl to
allow the VMM to control RIPAS at a finer granularity. But so far we
don't seem to have any compelling reason to expose that.

Thanks,
Steve

> Suzuki
>

---

## [58] Steven Price — 2026-01-26
*Subject: Re: [PATCH v12 22/46] arm64: RMI: Create the realm descriptor*

On 23/01/2026 18:57, Alper Gun wrote:
> On Wed, Dec 17, 2025 at 2:13 AM Steven Price <steven.price@arm.com> wrote:
>>

Yes the intention is that the uAPI will be extended in the future to
allow these to be configured. This would be by exposing new capability
flags and allowing the VMM to set the capability. This ensures that a
basic VMM doesn't need to worry about them, but a more featured VMM can
provide support for configuration.

This series is already rather long so I've attempted to drop optional
parts to keep the complexity down while still providing something
"useful" (i.e. can launch a realm guest and there's some meaningful
extra security/attestation over a normal VM). There's loads of extra
features in the spec which will come later.

Thanks,
Steve

>> +
>> +       params_phys = virt_to_phys(params);

---

## [59] Mathieu Poirier — 2026-02-12
*Subject: Re: [PATCH v12 00/46] arm64: Support for Arm CCA in KVM*

Hi Steven,

On Wed, Dec 17, 2025 at 10:10:37AM +0000, Steven Price wrote:
> This series adds support for running protected VMs using KVM under the
> Arm Confidential Compute Architecture (CCA). I've changed the uAPI

The first thing to note is that branch cca/v10 does not compile due to function
realm_configure_parameters() not being called anywhere.  Marking the function as
[[maybe_unused]] solved the problem on my side.

Using the FVP emulator, booting a Realm that includes EDK2 in its boot stack
worked.  If EDK2 is not part of the boot stack and a kernel is booted directly
from lkvm, mounting the initrd fails.  Looking into this issue further, I see
that from a Realm kernel's perspective, the content of the initrd is either
encrypted or has been trampled on.  

I'd be happy to provide more details on the above, just let me know.

Thanks,
Mathieu

> 
> [1] https://developer.arm.com/documentation/den0137/latest/

---

## [60] Steven Price — 2026-02-16
*Subject: Re: [PATCH v12 00/46] arm64: Support for Arm CCA in KVM*

On 12/02/2026 17:48, Mathieu Poirier wrote:
> Hi Steven,
> 

This is in the kvmtool code - and yes I agree "work in progress" is a
bit generous for the current state of that code, "horrid ugly hacks to
get things working" is probably more accurate ;)

The issue here is that the two things that realm_configure_parameters()
set up (hash algorithm and RPV) are currently unsupported with the Linux
changes, but will need to be reintroduced in the future. So the contents
of the functions which set this up (using the old uAPI) are just #if 0'd
out.

Depending on the compile flags the code will compile with a warning, but
using __attribute__((unused)) would at least make this clear. I'd want
to avoid the "[[maybe_unused]]" as it's not used elsewhere in the code
base and limits compatibility.

> Using the FVP emulator, booting a Realm that includes EDK2 in its boot stack
> worked.  If EDK2 is not part of the boot stack and a kernel is booted directly

I can reproduce that, a quick fix is to change INITRD_ALIGN:

#define INITRD_ALIGN	SZ_64K

But the code was meant to be able to deal with an unaligned initrd -
I'll see if I can figure out what's going wrong.

Thanks,
Steve

> I'd be happy to provide more details on the above, just let me know.
>

---

## [61] Steven Price — 2026-02-16
*Subject: Re: [PATCH v12 00/46] arm64: Support for Arm CCA in KVM*

On 16/02/2026 12:33, Steven Price wrote:
> On 12/02/2026 17:48, Mathieu Poirier wrote:
>> Hi Steven,

Looks like a simple bug in kvm_arm_realm_populate_ram() - it wasn't
updating the source address when it had to align the start of the
region. Simple fix below:

---8<---
diff --git a/arm/aarch64/realm.c b/arm/aarch64/realm.c
--- a/arm/aarch64/realm.c
+++ b/arm/aarch64/realm.c
@@ -104,7 +104,7 @@ void kvm_arm_realm_populate_ram(struct kvm *kvm,
unsigned long start,

        new_region->start = ALIGN_DOWN(start, SZ_64K);
        new_region->file_end = ALIGN(start + size, SZ_64K);
-       new_region->source = source;
+       new_region->source = source - (start - new_region->start);

        list_add_tail(&new_region->list, &realm_ram_regions);
 }
---8<---

Thanks for the pointer, and I'll try to remember to include initrd
testing in future.

Steve

---

## [62] Mathieu Poirier — 2026-02-17
*Subject: Re: [PATCH v12 00/46] arm64: Support for Arm CCA in KVM*

On Mon, Feb 16, 2026 at 02:27:02PM +0000, Steven Price wrote:
> On 16/02/2026 12:33, Steven Price wrote:
> > On 12/02/2026 17:48, Mathieu Poirier wrote:

That also worked on my side.

> 
>         list_add_tail(&new_region->list, &realm_ram_regions);

Very well.

Thanks for looking into this.

> Steve
>

---

## [63] Marc Zyngier — 2026-03-02
*Subject: Re: [PATCH v12 06/46] arm64: RMI: Define the user ABI*

On Wed, 17 Dec 2025 10:10:43 +0000,
Steven Price <steven.price@arm.com> wrote:
> 
> There is one CAP which identified the presence of CCA, and two ioctls.

Shouldn't we make handling of PSCI mandatory for VMMs that deal with
CCA? I suspect it would simplify the implementation significantly.

What vcpu fd does this apply to? The vcpu calling the PSCI function?
Or the target? This is pretty important for PSCI_ON. My guess is that
this is setting the return value for the caller?

Assuming this is indeed for the caller, why do we have a different
flow from anything else that returns a result from a hypercall?

> +
> +4.145 KVM_ARM_RMI_POPULATE

size as a __u64 is odd, as the return value from the ioctl is a signed
int. This implies that you can't really report how many bytes you have
copied.  Some form of consistency wouldn't hurt.

Thanks,

	M.

---

## [64] Marc Zyngier — 2026-03-02
*Subject: Re: [PATCH v12 11/46] arm64: RMI: Activate realm on first VCPU run*

On Wed, 17 Dec 2025 10:10:48 +0000,
Steven Price <steven.price@arm.com> wrote:
> 
> When a VCPU migrates to another physical CPU check

To another physical CPU?

That's not what kvm_arch_vcpu_run_pid_change() tracks. It really is
limited to a new PID being associated to the vpcu thread. Which is
indeed the case when the vpcu runs for the first time, but that's
about it.

If you need to track the physical CPU, we have some tracking for it in
vcpu_load(), but that'd need some rework.

> if this is the first
> time the guest has run, and if so activate the realm.

nit: you already checked for this in caller.

> +
> +	if (kvm_realm_state(kvm) == REALM_STATE_ACTIVE)

You probably also want to return early once the realm has been marked
as dead -- it shouldn't be able to be a zombie and die twice.

> +
> +	guard(mutex)(&kvm->arch.config_lock);

Thanks,

	M.

---

## [65] Marc Zyngier — 2026-03-02
*Subject: Re: [PATCH v12 20/46] arm64: RMI: Allow populating initial contents*

On Wed, 17 Dec 2025 10:10:57 +0000,
Steven Price <steven.price@arm.com> wrote:
> 
> The VMM needs to populate the realm with some data before starting (e.g.

EPERM is odd. It isn't that the VMM doesn't have the right to do it,
it is that it shouldn't have called that, because the ioctl doesn't
exist for a normal VM. -ENOSYS?

> +		if (copy_from_user(&req, argp, sizeof(req)))
> +			return -EFAULT;

If this is unexpected, why do we still try to handle it? We should
abort hard on anything that doesn't seem 100% correct, and mark the
realm dead.

> +
> +		ret = realm_create_rtt_levels(realm, ipa, level,

This flag isn't documented.

> +		data_flags |= RMI_MEASURE_CONTENT;
> +

Bits of the code works on PAGE_SIZE, other bits on RMM_PAGE_SIZE. It
is pretty confusing. Are you in the middle of reworking this?

Thanks,

	M.

---

## [66] Steven Price — 2026-03-02
*Subject: Re: [PATCH v12 06/46] arm64: RMI: Define the user ABI*

Hi Marc,

On 02/03/2026 14:25, Marc Zyngier wrote:
> On Wed, 17 Dec 2025 10:10:43 +0000,
> Steven Price <steven.price@arm.com> wrote:

What do you mean by making it "mandatory for VMMs"? If you mean PSCI is
always forwarded to user space then I don't think it's going to make
much difference. Patch 27 handles the PSCI changes (72 lines added), and
some of that is adding this uAPI for the VMM to handle it.

Removing the functionality to allow the VMM to handle it would obviously
simplify things a bit (we can drop this uAPI), but I think the desire is
to push this onto user space.

> What vcpu fd does this apply to? The vcpu calling the PSCI function?
> Or the target? This is pretty important for PSCI_ON. My guess is that

Yes the fd is the vcpu calling PSCI. As you say, this is for the return
value to be set correctly.

> Assuming this is indeed for the caller, why do we have a different
> flow from anything else that returns a result from a hypercall?

I'm not entirely sure what you are suggesting. Do you mean why are we
not just writing to the GPRS that would contain the result? The issue
here is that the RMM needs to know the PA of the target REC structure -
this isn't a return to the guest, but information for the RMM itself to
complete the PSCI call.

Ultimately even in the case where the VMM is handling PSCI, it's
actually a combination of the VMM and the RMM - with the RMM validating
the responses.

>> +
>> +4.145 KVM_ARM_RMI_POPULATE

Good spot. In practice this works because >2GB in one operation is
highly unlikely to be processed in one go. But I guess I'll change this
to have an output size argument. I guess I could make the kernel update
all of base,size,source_uaddr which would simplify user space.

Thanks,
Steve

---

## [67] Steven Price — 2026-03-02
*Subject: Re: [PATCH v12 11/46] arm64: RMI: Activate realm on first VCPU run*

On 02/03/2026 14:40, Marc Zyngier wrote:
> On Wed, 17 Dec 2025 10:10:48 +0000,
> Steven Price <steven.price@arm.com> wrote:

Sorry that was just a complete brainfart when I wrote that commit
message. We don't care about physical CPUs - this is just catching the
first VCPU run. Thanks for catching that.

>> if this is the first
>> time the guest has run, and if so activate the realm.

Ack

>> +
>> +	if (kvm_realm_state(kvm) == REALM_STATE_ACTIVE)

Indeed, >= would be a better check.

Thanks,
Steve

>> +
>> +	guard(mutex)(&kvm->arch.config_lock);

---

## [68] Marc Zyngier — 2026-03-02
*Subject: Re: [PATCH v12 27/46] KVM: arm64: Handle Realm PSCI requests*

On Wed, 17 Dec 2025 10:11:04 +0000,
Steven Price <steven.price@arm.com> wrote:
> 
> The RMM needs to be informed of the target REC when a PSCI call is made

Same remark as for the other ioctl: EPERM is not quite describing the
problem.

> +		if (copy_from_user(&req, argp, sizeof(req)))
> +			return -EFAULT;

I really think in-kernel PSCI should be for NS VMs only. The whole
reason for moving to userspace support was to stop adding features to
an already complex infrastructure, and CCA is exactly the sort of
things we want userspace to deal with.

Thanks,

	M.

---

## [69] Steven Price — 2026-03-02
*Subject: Re: [PATCH v12 20/46] arm64: RMI: Allow populating initial contents*

On 02/03/2026 14:56, Marc Zyngier wrote:
> On Wed, 17 Dec 2025 10:10:57 +0000,
> Steven Price <steven.price@arm.com> wrote:

Ack

>> +		if (copy_from_user(&req, argp, sizeof(req)))
>> +			return -EFAULT;

Well this is a "should never happen - the RMM (or Linux kerne) is buggy" 
situation - so it's not specifically the realm's fault. The "do nothing" 
error handling deals with things quite reasonably - the following 
realm_create_rtt_levels() call is a no-op, so we'll retry the 
rmi_data_create() call and bubble the error up.

I'll change this to KVM_BUG_ON so that the guest is killed just in case 
it turns out the guest can somehow trigger this maliciously.

>> +
>> +		ret = realm_create_rtt_levels(realm, ipa, level,

Indeed - that's an oversight! I'll add the following to the docs:

`flags` can be set to `KVM_ARM_RMI_POPULATE_FLAGS_MEASURE` to request that the
populated data is hashed and added to the guest's Realm Initial Measurement
(RIM).

>> +		data_flags |= RMI_MEASURE_CONTENT;
>> +

Yes, sorry about that - RMM_PAGE_SIZE will be completely gone when
this is updated to RMM v2.0.

Thanks,
Steve

---

## [70] Suzuki K Poulose — 2026-03-02
*Subject: Re: [PATCH v12 06/46] arm64: RMI: Define the user ABI*

On 02/03/2026 15:23, Steven Price wrote:
> Hi Marc,
> 

More importantly, we have to make sure that the "RMI_PSCI_COMPLETE" is
invoked before both of the following:
   1. The "source" vCPU is run again
   2. More importantly the "target" vCPU is run.

The latter part makes it difficult to issue this RMI_PSCI_COMPLETE on
the way back from servicing the SMCCC call.

Suzuki


>>> +
>>> +4.145 KVM_ARM_RMI_POPULATE

---

## [71] Suzuki K Poulose — 2026-03-03
*Subject: Re: [PATCH v12 27/46] KVM: arm64: Handle Realm PSCI requests*

On 02/03/2026 16:39, Marc Zyngier wrote:
> On Wed, 17 Dec 2025 10:11:04 +0000,
> Steven Price <steven.price@arm.com> wrote:

Agreed. How would you like us to enforce this ? Should we always exit
to the VMM, even if it hasn't requested the handling ? (I guess it is
fine and in the worst case VMM could exit, it being buggy)

Cheers
Suzuki


> 
> Thanks,

---

## [72] Marc Zyngier — 2026-03-03
*Subject: Re: [PATCH v12 27/46] KVM: arm64: Handle Realm PSCI requests*

On Tue, 03 Mar 2026 09:26:31 +0000,
Suzuki K Poulose <suzuki.poulose@arm.com> wrote:
> 
> On 02/03/2026 16:39, Marc Zyngier wrote:

My current train of though is that a CCA VM always routes PSCI to
userspace, no configuration needed. That's part of the contract.

Now, I'm pretty sure we should *also* get rid of the ioctl that
establishes the relationship between MPIDR and REC. I can't see why
this can't be done at the point where the vcpu runs for the first
time, just like this is done for the first CPU.

Thanks,

	M.

---

## [73] Marc Zyngier — 2026-03-03
*Subject: Re: [PATCH v12 06/46] arm64: RMI: Define the user ABI*

On Mon, 02 Mar 2026 15:23:44 +0000,
Steven Price <steven.price@arm.com> wrote:
> 
> Hi Marc,

And that's what I'm asking for. I do not want this to be optional. CCA
should implies PSCI in userspace, and that's it.

> 
> > What vcpu fd does this apply to? The vcpu calling the PSCI function?

Another question is why do we need the ioctl at all? Why can't it be
done on the first run of the target vcpu? If no PSCI call was issued
to run it, then the run fails.

> 
> > Assuming this is indeed for the caller, why do we have a different

PSCI is a SMC call. SMC calls are routed to userspace as such. For odd
reasons, the RMM treats PSCI differently from any other SMC call.

That seems a very bizarre behaviour to me.

> 
> Ultimately even in the case where the VMM is handling PSCI, it's

I don't see why PSCI is singled out here, irrespective of the tracking
that the RMM wants to do.

	M.

---

## [74] Marc Zyngier — 2026-03-03
*Subject: Re: [PATCH v12 06/46] arm64: RMI: Define the user ABI*

On Mon, 02 Mar 2026 17:13:41 +0000,
Suzuki K Poulose <suzuki.poulose@arm.com> wrote:
> 
> On 02/03/2026 15:23, Steven Price wrote:

I don't understand why (1) is required. Once the VMM gets the request,
the target vcpu can run, and can itself do the completion, without any
additional userspace involvement.

	M.

---

## [75] Suzuki K Poulose — 2026-03-03
*Subject: Re: [PATCH v12 06/46] arm64: RMI: Define the user ABI*

On 03/03/2026 13:13, Marc Zyngier wrote:
> On Mon, 02 Mar 2026 17:13:41 +0000,
> Suzuki K Poulose <suzuki.poulose@arm.com> wrote:

The underlying issue is, the RMM doesn't have the VCPU object for the
"target" VCPU, to make the book keeping. Also, please note that for  a
Realm, PSCI is emulated by the "RMM". Host is obviously notified of the
"PSCI" changes via EXIT_PSCI (note, it is not SMCCC exit)
  so that it can be in sync with the real state. And does have a say in
  CPU_ON. So, before we return to running the "source" CPU,
Host must provide the target VCPU object and its consent (via
psci_status) to the RMM. This allows the RMM to emulate the PSCI
request correctly and also at the same time keep its book keeping
in tact (i.e., marking the Target VCPU as runnable or not).

When a "source" VCPU exits to the host with a PSCI_EXIT, the RMM
marks the source VCPU has a pending PSCI operation, and
RMI_PSCI_COMPLETE request ticks that off, making it runnable again.


Suzuki

> the target vcpu can run, and can itself do the completion, without any
> additional userspace involvement.

---

## [76] Marc Zyngier — 2026-03-03
*Subject: Re: [PATCH v12 06/46] arm64: RMI: Define the user ABI*

On Tue, 03 Mar 2026 14:23:08 +0000,
Suzuki K Poulose <suzuki.poulose@arm.com> wrote:
> 
> On 03/03/2026 13:13, Marc Zyngier wrote:

Sure. What I don't get is what this has to happen on the source vcpu
thread. The RMM has absolutely no clue about that, and there should be
no impediment to letting the target vcpu do it as it starts.

Even better, you should be able to do that on the first thread that
reenters the guest, completely removing any RMM knowledge from the
PSCI handling in userspace.

If you can't do that, then please consider fixing the RMM to allow it.

Thanks,

	M.

---

## [77] Suzuki K Poulose — 2026-03-03
*Subject: Re: [PATCH v12 06/46] arm64: RMI: Define the user ABI*

On 03/03/2026 14:37, Marc Zyngier wrote:
> On Tue, 03 Mar 2026 14:23:08 +0000,
> Suzuki K Poulose <suzuki.poulose@arm.com> wrote:

Because, the RMM wants to make that the state is consistent. i.e,
Host cannot lie to the "source" VCPU and RMM (e.g., CPU_ON denied) and
then run the "target" VCPU.

In other words, the response to the CPU_ON must be recorded by the RMM
in the target VCPU state, to make sure the target VCPU state is
consistent with the response.

The only way to fix this would be RMM keeping track of "mpidr" to REC
object mapping (VCPU object), which impacts the scalability. With that
in place, RMM can update the target VCPU state from the return of the
REC_ENTER after a PSCI_EXIT.

That said, will explore the options to address this

Thanks
Suzuki

> 
> Even better, you should be able to do that on the first thread that

---

## [78] Steven Price — 2026-03-04
*Subject: Re: [PATCH v12 06/46] arm64: RMI: Define the user ABI*

On 03/03/2026 13:11, Marc Zyngier wrote:
> On Mon, 02 Mar 2026 15:23:44 +0000,
> Steven Price <steven.price@arm.com> wrote:

So my concern is the ordering of operations for PSCI_CPU_ON. As things
stand the RMM needs to know the MPIDR mapping to look up the REC object
before either VCPU runs again.

If we do this on the first run of the target VCPU, then how is the VMM
to tell that the target VCPU has executed "long enough" that it is safe
to do the return on the initial VCPU? Since the VCPUs are different
threads this becomes tricky. Options I can see are:

a) The VMM has to wait for the target VCPU to exit - we'd probably want
to trigger an artificial early exit in this case to unblock things.

b) The kernel blocks the initial VCPU from running until the target VCPU
has completed this "first run" logic. I think waiting in the kernel is
probably problematic, so this implies return some sort of "retry later"
response to the VMM.

c) The kernel handles the "PSCI_COMPLETE" dance on whichever VCPU runs
first, blocking the other until the dance is complete. A disadvantage
here is that behaviour can differ (in error conditions) depending on
which VCPU thread wins the race.

All these options also involve the kernel keeping track of the PSCI
sequence, in particular:

1. Tracking that the exit was due to a PSCI_CPU_ON.

2. Treating attempting to run the target VCPU as an implicit success
return from the PSCI call.

3. Recognising the next run on the initial VCPU as containing the PSCI
result - if 2, above, has happened then the kernel will need to handle
this (by killing the guest).

TLDR; Yes this is possible but I don't think it's pretty, and I'm not
convinced it's an improved uAPI.

Of course the above all assumes that the RMM can't just track things
internally. My preference is to kill RMI_PSCI_COMPLETE altogether, but
I'm not sure how possible that is within the context of the RMM.

>>
>>> Assuming this is indeed for the caller, why do we have a different

The RMM generally treats SMC specially. We have the RSI_HOST_CALL as a
proxy for "general SMC-like" behaviour which is forwarded to the VMM. I
believe the intention here is to ensure that SMCs (from the realm guest)
are handled by a trusted agent (i.e. the RMM). PSCI is a corner case
because it requires some coordination and buy-in from the VMM.

I'm not sure I fully understand the security pros and cons of the design
here and what impact it would have if PSCI was well trusted.

Thanks,
Steve

>>
>> Ultimately even in the case where the VMM is handling PSCI, it's

---

## [79] Marc Zyngier — 2026-03-11
*Subject: Re: [PATCH v12 06/46] arm64: RMI: Define the user ABI*

On Mon, 02 Mar 2026 15:23:44 +0000,
Steven Price <steven.price@arm.com> wrote:
> 
> >> +  struct kvm_arm_rmi_populate {

In a conversation with Suzuki, I suggested that splice(2) could be a
nicer way to express this, and allow asynchronous use with io-uring.

After all, having a guestmem backend for CCA is not exactly
outlandish, and having a splice implementation realistic enough.

Thoughts?

	M.

---

## [80] Suzuki K Poulose — 2026-03-12
*Subject: Re: [PATCH v12 06/46] arm64: RMI: Define the user ABI*

On 11/03/2026 19:10, Marc Zyngier wrote:
> On Mon, 02 Mar 2026 15:23:44 +0000,
> Steven Price <steven.price@arm.com> wrote:

One issue that I realised, is about the "flags" for the populate.
Data can be loaded as measured vs unmeasured in CCA (and in TDX
and SNP). I don't see a way to convey this with splice.

Suzuki

> 
> 	M.

---

## [81] Marc Zyngier — 2026-03-12
*Subject: Re: [PATCH v12 06/46] arm64: RMI: Define the user ABI*

On Thu, 12 Mar 2026 09:28:16 +0000,
Suzuki K Poulose <suzuki.poulose@arm.com> wrote:
> 
> On 11/03/2026 19:10, Marc Zyngier wrote:

Surely that should me a property of the memory region, and not the way
it is copied, right?

	M.

---

## [82] Steven Price — 2026-03-12
*Subject: Re: [PATCH v12 06/46] arm64: RMI: Define the user ABI*

On 12/03/2026 09:39, Marc Zyngier wrote:
> On Thu, 12 Mar 2026 09:28:16 +0000,
> Suzuki K Poulose <suzuki.poulose@arm.com> wrote:

I'm not sure what the current thoughts on the matter are, but there was
an intention in the past that some data could be measured and some not
within a region which is logically the same. E.g. the DT might be
deliberately unmeasured so that the same measurement would cover a
selection of different configurations (with the guest obviously
validating that it was sane before continuing). Forcing the memory to be
split into multiple memslots just so a measurement flag can be set
correctly seems like a poor uAPI.

While splice(2) certainly looks similar to what we want, it does
(according to the man page at least) have the requirement that "one of
the file descriptors must refer to a pipe" which seems less than ideal
for the DT case where it's likely to be generated in memory by the VMM.
Or is my man page out of date and the pipe restriction isn't there in
the kernel?

Thanks,
Steve

---
