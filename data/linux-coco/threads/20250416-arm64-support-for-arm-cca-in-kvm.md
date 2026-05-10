---
title: 'arm64: Support for Arm CCA in KVM'
date: 2025-04-16
last_reply: 2025-05-07
message_count: 90
participants: ['Steven Price', 'Suzuki K Poulose', 'Gavin Shan']
---

## [1] Steven Price — 2025-04-16

This series adds support for running protected VMs using KVM under the
Arm Confidential Compute Architecture (CCA).

The related guest support was merged for v6.14-rc1 so you no longer need
that separately.

There are a few changes since v7, many thanks for the review
comments. The highlights are below, and individual patches have a changelog.

 * More documentation - the new ioctls and capabilties are now all
   documented.

 * Initial patch adding "only_private"/"only_shared" to struct
   kvm_gfn_range replaced with already upstream "attr_filter".

 * Improvement in variable naming and error codes, and some improved/new
   comments. All following valuable review feedback (thanks!).

 * Drop the final WIP patch for enabling large PAGE_SIZE support. It's
   not ready for merging and I want to focus on landing the 4k support.

 * Rebased onto v6.15-rc1.

Things to note:

 * The magic numbers for capabilities and ioctls have been updated. So
   you'll need to update your VMM. See below for update kvmtool branch.

 * Patch 42 increases KVM_VCPU_MAX_FEATURES to expose the new feature.
   This also exposes the NV features (as they are currently numbered
   lower). This will resolve when Marc's NV series has landed, see [2].

 * There are some conflicts with v6.15-rc2, mostly documentation, but
   also commit 26fbdf369227 ("KVM: arm64: Don't translate FAR if
   invalid/unsafe") 'hijacks' HPFAR_EL2_NS as a valid bit. This will
   require corresponding changes to the CCA code.

The ABI to the RMM (the RMI) is based on RMM v1.0-rel0 specification[1].

This series is based on v6.15-rc1. It is also available as a git
repository:

https://gitlab.arm.com/linux-arm/linux-cca cca-host/v8

Work in progress changes for kvmtool are available from the git
repository below:

https://gitlab.arm.com/linux-arm/kvmtool-cca cca/v6

[1] https://developer.arm.com/documentation/den0137/1-0rel0/
[2] https://lore.kernel.org/r/20250408105225.4002637-17-maz%40kernel.org

Jean-Philippe Brucker (7):
  arm64: RME: Propagate number of breakpoints and watchpoints to
    userspace
  arm64: RME: Set breakpoint parameters through SET_ONE_REG
  arm64: RME: Initialize PMCR.N with number counter supported by RMM
  arm64: RME: Propagate max SVE vector length from RMM
  arm64: RME: Configure max SVE vector length for a Realm
  arm64: RME: Provide register list for unfinalized RME RECs
  arm64: RME: Provide accurate register list

Joey Gouly (2):
  arm64: RME: allow userspace to inject aborts
  arm64: RME: support RSI_HOST_CALL

Steven Price (31):
  arm64: RME: Handle Granule Protection Faults (GPFs)
  arm64: RME: Add SMC definitions for calling the RMM
  arm64: RME: Add wrappers for RMI calls
  arm64: RME: Check for RME support at KVM init
  arm64: RME: Define the user ABI
  arm64: RME: ioctls to create and configure realms
  KVM: arm64: Allow passing machine type in KVM creation
  arm64: RME: RTT tear down
  arm64: RME: Allocate/free RECs to match vCPUs
  KVM: arm64: vgic: Provide helper for number of list registers
  arm64: RME: Support for the VGIC in realms
  KVM: arm64: Support timers in realm RECs
  arm64: RME: Allow VMM to set RIPAS
  arm64: RME: Handle realm enter/exit
  arm64: RME: Handle RMI_EXIT_RIPAS_CHANGE
  KVM: arm64: Handle realm MMIO emulation
  arm64: RME: Allow populating initial contents
  arm64: RME: Runtime faulting of memory
  KVM: arm64: Handle realm VCPU load
  KVM: arm64: Validate register access for a Realm VM
  KVM: arm64: Handle Realm PSCI requests
  KVM: arm64: WARN on injected undef exceptions
  arm64: Don't expose stolen time for realm guests
  arm64: RME: Always use 4k pages for realms
  arm64: RME: Prevent Device mappings for Realms
  arm_pmu: Provide a mechanism for disabling the physical IRQ
  arm64: RME: Enable PMU support with a realm guest
  arm64: RME: Hide KVM_CAP_READONLY_MEM for realm guests
  KVM: arm64: Expose support for private memory
  KVM: arm64: Expose KVM_ARM_VCPU_REC to user space
  KVM: arm64: Allow activating realms

Suzuki K Poulose (3):
  kvm: arm64: Include kvm_emulate.h in kvm/arm_psci.h
  kvm: arm64: Don't expose debug capabilities for realm guests
  arm64: RME: Allow checking SVE on VM instance

 Documentation/virt/kvm/api.rst       |   91 +-
 arch/arm64/include/asm/kvm_emulate.h |   40 +
 arch/arm64/include/asm/kvm_host.h    |   17 +-
 arch/arm64/include/asm/kvm_rme.h     |  137 +++
 arch/arm64/include/asm/rmi_cmds.h    |  508 ++++++++
 arch/arm64/include/asm/rmi_smc.h     |  259 ++++
 arch/arm64/include/asm/virt.h        |    1 +
 arch/arm64/include/uapi/asm/kvm.h    |   49 +
 arch/arm64/kvm/Kconfig               |    1 +
 arch/arm64/kvm/Makefile              |    3 +-
 arch/arm64/kvm/arch_timer.c          |   48 +-
 arch/arm64/kvm/arm.c                 |  160 ++-
 arch/arm64/kvm/guest.c               |  104 +-
 arch/arm64/kvm/hypercalls.c          |    4 +-
 arch/arm64/kvm/inject_fault.c        |    5 +-
 arch/arm64/kvm/mmio.c                |   16 +-
 arch/arm64/kvm/mmu.c                 |  201 ++-
 arch/arm64/kvm/pmu-emul.c            |    6 +
 arch/arm64/kvm/psci.c                |   30 +
 arch/arm64/kvm/reset.c               |   23 +-
 arch/arm64/kvm/rme-exit.c            |  199 +++
 arch/arm64/kvm/rme.c                 | 1708 ++++++++++++++++++++++++++
 arch/arm64/kvm/sys_regs.c            |   49 +-
 arch/arm64/kvm/vgic/vgic-init.c      |    2 +-
 arch/arm64/kvm/vgic/vgic-v3.c        |    6 +-
 arch/arm64/kvm/vgic/vgic.c           |   54 +-
 arch/arm64/mm/fault.c                |   31 +-
 drivers/perf/arm_pmu.c               |   15 +
 include/kvm/arm_arch_timer.h         |    2 +
 include/kvm/arm_pmu.h                |    4 +
 include/kvm/arm_psci.h               |    2 +
 include/linux/perf/arm_pmu.h         |    5 +
 include/uapi/linux/kvm.h             |   29 +-
 33 files changed, 3709 insertions(+), 100 deletions(-)
 create mode 100644 arch/arm64/include/asm/kvm_rme.h
 create mode 100644 arch/arm64/include/asm/rmi_cmds.h
 create mode 100644 arch/arm64/include/asm/rmi_smc.h
 create mode 100644 arch/arm64/kvm/rme-exit.c
 create mode 100644 arch/arm64/kvm/rme.c

---

## [2] Steven Price — 2025-04-16
*Subject: [PATCH v8 01/43] kvm: arm64: Include kvm_emulate.h in kvm/arm_psci.h*

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

## [3] Steven Price — 2025-04-16
*Subject: [PATCH v8 02/43] arm64: RME: Handle Granule Protection Faults (GPFs)*

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
Changes since v2:
 * Include missing "Granule Protection Fault at level -1"
---
 arch/arm64/mm/fault.c | 31 +++++++++++++++++++++++++------
 1 file changed, 25 insertions(+), 6 deletions(-)

diff --git a/arch/arm64/mm/fault.c b/arch/arm64/mm/fault.c
index ec0a337891dd..59a89a8fb226 100644
--- a/arch/arm64/mm/fault.c
+++ b/arch/arm64/mm/fault.c
@@ -844,6 +844,25 @@ static int do_tag_check_fault(unsigned long far, unsigned long esr,
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
+	const struct fault_info *inf = esr_to_fault_info(esr);
+
+	if (!is_el1_instruction_abort(esr) && fixup_exception(regs, esr))
+		return 0;
+
+	arm64_notify_die(inf->name, regs, inf->sig, inf->code, far, esr);
+	return 0;
+}
+
 static const struct fault_info fault_info[] = {
 	{ do_bad,		SIGKILL, SI_KERNEL,	"ttbr address size fault"	},
 	{ do_bad,		SIGKILL, SI_KERNEL,	"level 1 address size fault"	},
@@ -880,12 +899,12 @@ static const struct fault_info fault_info[] = {
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

## [4] Steven Price — 2025-04-16
*Subject: [PATCH v8 03/43] arm64: RME: Add SMC definitions for calling the RMM*

The RMM (Realm Management Monitor) provides functionality that can be
accessed by SMC calls from the host.

The SMC definitions are based on DEN0137[1] version 1.0-rel0

[1] https://developer.arm.com/documentation/den0137/1-0rel0/

Reviewed-by: Gavin Shan <gshan@redhat.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/include/asm/rmi_smc.h | 259 +++++++++++++++++++++++++++++++
 1 file changed, 259 insertions(+)
 create mode 100644 arch/arm64/include/asm/rmi_smc.h

diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
new file mode 100644
index 000000000000..7a93a3e0ac6e
--- /dev/null
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -0,0 +1,259 @@
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
+			u64 ripas_value;
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

## [5] Steven Price — 2025-04-16
*Subject: [PATCH v8 04/43] arm64: RME: Add wrappers for RMI calls*

The wrappers make the call sites easier to read and deal with the
boiler plate of handling the error codes from the RMM.

Reviewed-by: Gavin Shan <gshan@redhat.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
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
index 000000000000..27cd2751f3bf
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
+	arm_smccc_1_2_smc(&regs, &regs);
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

## [6] Steven Price — 2025-04-16
*Subject: [PATCH v8 05/43] arm64: RME: Check for RME support at KVM init*

Query the RMI version number and check if it is a compatible version. A
static key is also provided to signal that a supported RMM is available.

Functions are provided to query if a VM or VCPU is a realm (or rec)
which currently will always return false.

Later patches make use of struct realm and the states as the ioctls
interfaces are added to support realm and REC creation and destruction.

Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
---
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
 arch/arm64/include/asm/kvm_emulate.h | 18 +++++++++
 arch/arm64/include/asm/kvm_host.h    |  4 ++
 arch/arm64/include/asm/kvm_rme.h     | 56 ++++++++++++++++++++++++++++
 arch/arm64/include/asm/virt.h        |  1 +
 arch/arm64/kvm/Makefile              |  3 +-
 arch/arm64/kvm/arm.c                 |  6 +++
 arch/arm64/kvm/rme.c                 | 56 ++++++++++++++++++++++++++++
 7 files changed, 143 insertions(+), 1 deletion(-)
 create mode 100644 arch/arm64/include/asm/kvm_rme.h
 create mode 100644 arch/arm64/kvm/rme.c

diff --git a/arch/arm64/include/asm/kvm_emulate.h b/arch/arm64/include/asm/kvm_emulate.h
index d7cf66573aca..1c43a4fc25dd 100644
--- a/arch/arm64/include/asm/kvm_emulate.h
+++ b/arch/arm64/include/asm/kvm_emulate.h
@@ -686,4 +686,22 @@ static inline void vcpu_set_hcrx(struct kvm_vcpu *vcpu)
 			vcpu->arch.hcrx_el2 |= HCRX_EL2_EnFPM;
 	}
 }
+
+static inline bool kvm_is_realm(struct kvm *kvm)
+{
+	if (static_branch_unlikely(&kvm_rme_is_available) && kvm)
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
index e98cfe7855a6..7bd81b86eab0 100644
--- a/arch/arm64/include/asm/kvm_host.h
+++ b/arch/arm64/include/asm/kvm_host.h
@@ -27,6 +27,7 @@
 #include <asm/fpsimd.h>
 #include <asm/kvm.h>
 #include <asm/kvm_asm.h>
+#include <asm/kvm_rme.h>
 #include <asm/vncr_mapping.h>
 
 #define __KVM_HAVE_ARCH_INTC_INITIALIZED
@@ -394,6 +395,9 @@ struct kvm_arch {
 	 * the associated pKVM instance in the hypervisor.
 	 */
 	struct kvm_protected_vm pkvm;
+
+	bool is_realm;
+	struct realm realm;
 };
 
 struct kvm_vcpu_fault_info {
diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
new file mode 100644
index 000000000000..9c8a0b23e0e4
--- /dev/null
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -0,0 +1,56 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+/*
+ * Copyright (C) 2023 ARM Ltd.
+ */
+
+#ifndef __ASM_KVM_RME_H
+#define __ASM_KVM_RME_H
+
+/**
+ * enum realm_state - State of a Realm
+ */
+enum realm_state {
+	/**
+	 * @REALM_STATE_NONE:
+	 *      Realm has not yet been created. rmi_realm_create() may be
+	 *      called to create the realm.
+	 */
+	REALM_STATE_NONE,
+	/**
+	 * @REALM_STATE_NEW:
+	 *      Realm is under construction, not eligible for execution. Pages
+	 *      may be populated with rmi_data_create().
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
+void kvm_init_rme(void);
+
+#endif /* __ASM_KVM_RME_H */
diff --git a/arch/arm64/include/asm/virt.h b/arch/arm64/include/asm/virt.h
index ebf4a9f943ed..e45d47156dcf 100644
--- a/arch/arm64/include/asm/virt.h
+++ b/arch/arm64/include/asm/virt.h
@@ -81,6 +81,7 @@ void __hyp_reset_vectors(void);
 bool is_kvm_arm_initialised(void);
 
 DECLARE_STATIC_KEY_FALSE(kvm_protected_mode_initialized);
+DECLARE_STATIC_KEY_FALSE(kvm_rme_is_available);
 
 static inline bool is_pkvm_initialized(void)
 {
diff --git a/arch/arm64/kvm/Makefile b/arch/arm64/kvm/Makefile
index 209bc76263f1..2ebc66812d49 100644
--- a/arch/arm64/kvm/Makefile
+++ b/arch/arm64/kvm/Makefile
@@ -23,7 +23,8 @@ kvm-y += arm.o mmu.o mmio.o psci.o hypercalls.o pvtime.o \
 	 vgic/vgic-v3.o vgic/vgic-v4.o \
 	 vgic/vgic-mmio.o vgic/vgic-mmio-v2.o \
 	 vgic/vgic-mmio-v3.o vgic/vgic-kvm-device.o \
-	 vgic/vgic-its.o vgic/vgic-debug.o vgic/vgic-v3-nested.o
+	 vgic/vgic-its.o vgic/vgic-debug.o vgic/vgic-v3-nested.o \
+	 rme.o
 
 kvm-$(CONFIG_HW_PERF_EVENTS)  += pmu-emul.o pmu.o
 kvm-$(CONFIG_ARM64_PTR_AUTH)  += pauth.o
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 68fec8c95fee..856a721d41ac 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -40,6 +40,7 @@
 #include <asm/kvm_nested.h>
 #include <asm/kvm_pkvm.h>
 #include <asm/kvm_ptrauth.h>
+#include <asm/kvm_rme.h>
 #include <asm/sections.h>
 
 #include <kvm/arm_hypercalls.h>
@@ -59,6 +60,8 @@ enum kvm_wfx_trap_policy {
 static enum kvm_wfx_trap_policy kvm_wfi_trap_policy __read_mostly = KVM_WFX_NOTRAP_SINGLE_TASK;
 static enum kvm_wfx_trap_policy kvm_wfe_trap_policy __read_mostly = KVM_WFX_NOTRAP_SINGLE_TASK;
 
+DEFINE_STATIC_KEY_FALSE(kvm_rme_is_available);
+
 DECLARE_KVM_HYP_PER_CPU(unsigned long, kvm_hyp_vector);
 
 DEFINE_PER_CPU(unsigned long, kvm_arm_hyp_stack_base);
@@ -2819,6 +2822,9 @@ static __init int kvm_arm_init(void)
 
 	in_hyp_mode = is_kernel_in_hyp_mode();
 
+	if (in_hyp_mode)
+		kvm_init_rme();
+
 	if (cpus_have_final_cap(ARM64_WORKAROUND_DEVICE_LOAD_ACQUIRE) ||
 	    cpus_have_final_cap(ARM64_WORKAROUND_1508412))
 		kvm_info("Guests without required CPU erratum workarounds can deadlock system!\n" \
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
new file mode 100644
index 000000000000..67cf2d94cb2d
--- /dev/null
+++ b/arch/arm64/kvm/rme.c
@@ -0,0 +1,56 @@
+// SPDX-License-Identifier: GPL-2.0
+/*
+ * Copyright (C) 2023 ARM Ltd.
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
+void kvm_init_rme(void)
+{
+	if (PAGE_SIZE != SZ_4K)
+		/* Only 4k page size on the host is supported */
+		return;
+
+	if (rmi_check_version())
+		/* Continue without realm support */
+		return;
+
+	/* Future patch will enable static branch kvm_rme_is_available */
+}

---

## [7] Steven Price — 2025-04-16
*Subject: [PATCH v8 06/43] arm64: RME: Define the user ABI*

There is one (multiplexed) CAP which can be used to create, populate and
then activate the realm.

Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 Documentation/virt/kvm/api.rst    | 70 +++++++++++++++++++++++++++++++
 arch/arm64/include/uapi/asm/kvm.h | 49 ++++++++++++++++++++++
 include/uapi/linux/kvm.h          | 10 +++++
 3 files changed, 129 insertions(+)

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index 1f8625b7646a..99ba6c82cf37 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -3527,6 +3527,11 @@ Possible features:
 	      - the KVM_REG_ARM64_SVE_VLS pseudo-register is immutable, and can
 	        no longer be written using KVM_SET_ONE_REG.
 
+	- KVM_ARM_VCPU_REC: Allocate a REC (Realm Execution Context) for this
+	  VCPU. This must be specified on all VCPUs created in a Realm VM.
+	  Depends on KVM_CAP_ARM_RME.
+	  Requires KVM_ARM_VCPU_FINALIZE(KVM_ARM_VCPU_REC).
+
 4.83 KVM_ARM_PREFERRED_TARGET
 -----------------------------
 
@@ -5098,6 +5103,7 @@ Recognised values for feature:
 
   =====      ===========================================
   arm64      KVM_ARM_VCPU_SVE (requires KVM_CAP_ARM_SVE)
+  arm64      KVM_ARM_VCPU_REC (requires KVM_CAP_ARM_RME)
   =====      ===========================================
 
 Finalizes the configuration of the specified vcpu feature.
@@ -6452,6 +6458,30 @@ the capability to be present.
 
 `flags` must currently be zero.
 
+4.144 KVM_ARM_VCPU_RMM_PSCI_COMPLETE
+------------------------------------
+
+:Capability: KVM_CAP_ARM_RME
+:Architectures: arm64
+:Type: vcpu ioctl
+:Parameters: struct kvm_arm_rmm_psci_complete (in)
+:Returns: 0 if successful, < 0 on error
+
+::
+
+  struct kvm_arm_rmm_psci_complete {
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
 
 .. _kvm_run:
 
@@ -8280,6 +8310,46 @@ aforementioned registers before the first KVM_RUN. These registers are VM
 scoped, meaning that the same set of values are presented on all vCPUs in a
 given VM.
 
+7.38 KVM_CAP_ARM_RME
+--------------------
+
+:Architectures: arm64
+:Target: VM
+:Parameters: args[0] provides an action, args[1] points to a structure in
+	     memory for some actions.
+:Returns: 0 on success, negative value on error
+
+Used to configure and set up the memory for a Realm. The available actions are:
+
+================================= =============================================
+ KVM_CAP_ARM_RME_CONFIG_REALM     Takes struct arm_rme_config as args[1] and
+                                  configures realm parameters prior to it being
+                                  created.
+
+                                  Options are ARM_RME_CONFIG_RPV to set the
+                                  "Realm Personalization Value" and
+                                  ARM_RME_CONFIG_HASH_ALGO to set the hash
+                                  algorithm.
+
+ KVM_CAP_ARM_RME_CREATE_REALM     Request the RMM create the realm. The realm's
+                                  configuration parameters must be set first.
+
+ KVM_CAP_ARM_RME_INIT_RIPAS_REALM Takes struct arm_rme_init_ripas as args[1]
+                                  and sets the RIPAS (Realm IPA State) to
+                                  RIPAS_RAM of a specified area of the realm's
+                                  IPA.
+
+ KVM_CAP_ARM_RME_POPULATE_REALM   Takes struct arm_rme_init_ripas as args[1]
+                                  and populates a region of protected address
+                                  space by copying the data from the shared
+                                  alias.
+
+ KVM_CAP_ARM_RME_ACTIVATE_REALM   Request the RMM activate the realm. No
+                                  further changes can be made to the realm's
+                                  configuration, and VCPUs are not permitted to
+                                  enter the realm until it has been activated.
+================================= =============================================
+
 8. Other capabilities.
 ======================
 
diff --git a/arch/arm64/include/uapi/asm/kvm.h b/arch/arm64/include/uapi/asm/kvm.h
index af9d9acaf997..b57712880605 100644
--- a/arch/arm64/include/uapi/asm/kvm.h
+++ b/arch/arm64/include/uapi/asm/kvm.h
@@ -106,6 +106,7 @@ struct kvm_regs {
 #define KVM_ARM_VCPU_PTRAUTH_GENERIC	6 /* VCPU uses generic authentication */
 #define KVM_ARM_VCPU_HAS_EL2		7 /* Support nested virtualization */
 #define KVM_ARM_VCPU_HAS_EL2_E2H0	8 /* Limit NV support to E2H RES0 */
+#define KVM_ARM_VCPU_REC		9 /* VCPU REC state as part of Realm */
 
 struct kvm_vcpu_init {
 	__u32 target;
@@ -429,6 +430,54 @@ enum {
 #define   KVM_DEV_ARM_VGIC_SAVE_PENDING_TABLES	3
 #define   KVM_DEV_ARM_ITS_CTRL_RESET		4
 
+/* KVM_CAP_ARM_RME on VM fd */
+#define KVM_CAP_ARM_RME_CONFIG_REALM		0
+#define KVM_CAP_ARM_RME_CREATE_REALM		1
+#define KVM_CAP_ARM_RME_INIT_RIPAS_REALM	2
+#define KVM_CAP_ARM_RME_POPULATE_REALM		3
+#define KVM_CAP_ARM_RME_ACTIVATE_REALM		4
+
+/* List of configuration items accepted for KVM_CAP_ARM_RME_CONFIG_REALM */
+#define ARM_RME_CONFIG_RPV			0
+#define ARM_RME_CONFIG_HASH_ALGO		1
+
+#define ARM_RME_CONFIG_MEASUREMENT_ALGO_SHA256		0
+#define ARM_RME_CONFIG_MEASUREMENT_ALGO_SHA512		1
+
+#define ARM_RME_CONFIG_RPV_SIZE 64
+
+struct arm_rme_config {
+	__u32 cfg;
+	union {
+		/* cfg == ARM_RME_CONFIG_RPV */
+		struct {
+			__u8	rpv[ARM_RME_CONFIG_RPV_SIZE];
+		};
+
+		/* cfg == ARM_RME_CONFIG_HASH_ALGO */
+		struct {
+			__u32	hash_algo;
+		};
+
+		/* Fix the size of the union */
+		__u8	reserved[256];
+	};
+};
+
+#define KVM_ARM_RME_POPULATE_FLAGS_MEASURE	(1 << 0)
+struct arm_rme_populate_realm {
+	__u64 base;
+	__u64 size;
+	__u32 flags;
+	__u32 reserved[3];
+};
+
+struct arm_rme_init_ripas {
+	__u64 base;
+	__u64 size;
+	__u64 reserved[2];
+};
+
 /* Device Control API on vcpu fd */
 #define KVM_ARM_VCPU_PMU_V3_CTRL	0
 #define   KVM_ARM_VCPU_PMU_V3_IRQ	0
diff --git a/include/uapi/linux/kvm.h b/include/uapi/linux/kvm.h
index b6ae8ad8934b..0b8479985581 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -930,6 +930,7 @@ struct kvm_enable_cap {
 #define KVM_CAP_X86_APIC_BUS_CYCLES_NS 237
 #define KVM_CAP_X86_GUEST_MODE 238
 #define KVM_CAP_ARM_WRITABLE_IMP_ID_REGS 239
+#define KVM_CAP_ARM_RME 240
 
 struct kvm_irq_routing_irqchip {
 	__u32 irqchip;
@@ -1582,4 +1583,13 @@ struct kvm_pre_fault_memory {
 	__u64 padding[5];
 };
 
+/* Available with KVM_CAP_ARM_RME, only for VMs with KVM_VM_TYPE_ARM_REALM  */
+struct kvm_arm_rmm_psci_complete {
+	__u64 target_mpidr;
+	__u32 psci_status;
+	__u32 padding[3];
+};
+
+#define KVM_ARM_VCPU_RMM_PSCI_COMPLETE	_IOW(KVMIO, 0xd6, struct kvm_arm_rmm_psci_complete)
+
 #endif /* __LINUX_KVM_H */

---

## [8] Steven Price — 2025-04-16
*Subject: [PATCH v8 07/43] arm64: RME: ioctls to create and configure realms*

Add the KVM_CAP_ARM_RME_CREATE_RD ioctl to create a realm. This involves
delegating pages to the RMM to hold the Realm Descriptor (RD) and for
the base level of the Realm Translation Tables (RTT). A VMID also need
to be picked, since the RMM has a separate VMID address space a
dedicated allocator is added for this purpose.

KVM_CAP_ARM_RME_CONFIG_REALM is provided to allow configuring the realm
before it is created. Configuration options can be classified as:

 1. Parameters specific to the Realm stage2 (e.g. IPA Size, vmid, stage2
    entry level, entry level RTTs, number of RTTs in start level, LPA2)
    Most of these are not measured by RMM and comes from KVM book
    keeping.

 2. Parameters controlling "Arm Architecture features for the VM". (e.g.
    SVE VL, PMU counters, number of HW BRPs/WPs), configured by the VMM
    using the "user ID register write" mechanism. These will be
    supported in the later patches.

 3. Parameters are not part of the core Arm architecture but defined
    by the RMM spec (e.g. Hash algorithm for measurement,
    Personalisation value). These are programmed via
    KVM_CAP_ARM_RME_CONFIG_REALM.

For the IPA size there is the possibility that the RMM supports a
different size to the IPA size supported by KVM for normal guests. At
the moment the 'normal limit' is exposed by KVM_CAP_ARM_VM_IPA_SIZE and
the IPA size is configured by the bottom bits of vm_type in
KVM_CREATE_VM. This means that it isn't easy for the VMM to discover
what IPA sizes are supported for Realm guests. Since the IPA is part of
the measurement of the realm guest the current expectation is that the
VMM will be required to pick the IPA size demanded by attestation and
therefore simply failing if this isn't available is fine. An option
would be to expose a new capability ioctl to obtain the RMM's maximum
IPA size if this is needed in the future.

Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
---
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
 arch/arm64/include/asm/kvm_emulate.h |   5 +
 arch/arm64/include/asm/kvm_rme.h     |  19 ++
 arch/arm64/kvm/arm.c                 |  16 ++
 arch/arm64/kvm/mmu.c                 |  22 +-
 arch/arm64/kvm/rme.c                 | 319 +++++++++++++++++++++++++++
 5 files changed, 379 insertions(+), 2 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_emulate.h b/arch/arm64/include/asm/kvm_emulate.h
index 1c43a4fc25dd..4ee6c215da82 100644
--- a/arch/arm64/include/asm/kvm_emulate.h
+++ b/arch/arm64/include/asm/kvm_emulate.h
@@ -699,6 +699,11 @@ static inline enum realm_state kvm_realm_state(struct kvm *kvm)
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
diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index 9c8a0b23e0e4..5dc1915de891 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -6,6 +6,8 @@
 #ifndef __ASM_KVM_RME_H
 #define __ASM_KVM_RME_H
 
+#include <uapi/linux/kvm.h>
+
 /**
  * enum realm_state - State of a Realm
  */
@@ -46,11 +48,28 @@ enum realm_state {
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
 
 void kvm_init_rme(void);
+u32 kvm_realm_ipa_limit(void);
+
+int kvm_realm_enable_cap(struct kvm *kvm, struct kvm_enable_cap *cap);
+int kvm_init_realm_vm(struct kvm *kvm);
+void kvm_destroy_realm(struct kvm *kvm);
 
 #endif /* __ASM_KVM_RME_H */
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 856a721d41ac..0e8482fdc4d3 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -136,6 +136,11 @@ int kvm_vm_ioctl_enable_cap(struct kvm *kvm,
 		}
 		mutex_unlock(&kvm->lock);
 		break;
+	case KVM_CAP_ARM_RME:
+		mutex_lock(&kvm->lock);
+		r = kvm_realm_enable_cap(kvm, cap);
+		mutex_unlock(&kvm->lock);
+		break;
 	default:
 		break;
 	}
@@ -198,6 +203,13 @@ int kvm_arch_init_vm(struct kvm *kvm, unsigned long type)
 
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
@@ -257,6 +269,7 @@ void kvm_arch_destroy_vm(struct kvm *kvm)
 	kvm_unshare_hyp(kvm, kvm + 1);
 
 	kvm_arm_teardown_hypercalls(kvm);
+	kvm_destroy_realm(kvm);
 }
 
 static bool kvm_has_full_ptr_auth(void)
@@ -405,6 +418,9 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 	case KVM_CAP_ARM_SUPPORTED_REG_MASK_RANGES:
 		r = BIT(0);
 		break;
+	case KVM_CAP_ARM_RME:
+		r = static_key_enabled(&kvm_rme_is_available);
+		break;
 	default:
 		r = 0;
 	}
diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index 2feb6c6b63af..5957a07de86d 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -876,12 +876,16 @@ static struct kvm_pgtable_mm_ops kvm_s2_mm_ops = {
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
 
@@ -946,7 +950,7 @@ int kvm_init_stage2_mmu(struct kvm *kvm, struct kvm_s2_mmu *mmu, unsigned long t
 		return -EINVAL;
 	}
 
-	err = kvm_init_ipa_range(mmu, type);
+	err = kvm_init_ipa_range(kvm, mmu, type);
 	if (err)
 		return err;
 
@@ -1072,6 +1076,20 @@ void kvm_free_stage2_pgd(struct kvm_s2_mmu *mmu)
 	struct kvm_pgtable *pgt = NULL;
 
 	write_lock(&kvm->mmu_lock);
+	if (kvm_is_realm(kvm) &&
+	    (kvm_realm_state(kvm) != REALM_STATE_DEAD &&
+	     kvm_realm_state(kvm) != REALM_STATE_NONE)) {
+		/* Tearing down RTTs will be added in a later patch */
+		write_unlock(&kvm->mmu_lock);
+
+		/*
+		 * The physical PGD pages are delegated to the RMM, so cannot
+		 * be freed at this point. This function will be called again
+		 * from kvm_destroy_realm() after the physical pages have been
+		 * returned at which point the memory can be freed.
+		 */
+		return;
+	}
 	pgt = mmu->pgt;
 	if (pgt) {
 		mmu->pgd_phys = 0;
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 67cf2d94cb2d..dbb6521fe380 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -5,9 +5,23 @@
 
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
+static bool rme_has_feature(unsigned long feature)
+{
+	return !!u64_get_bits(rmm_feat_reg0, feature);
+}
+
 static int rmi_check_version(void)
 {
 	struct arm_smccc_res res;
@@ -42,6 +56,305 @@ static int rmi_check_version(void)
 	return 0;
 }
 
+u32 kvm_realm_ipa_limit(void)
+{
+	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_S2SZ);
+}
+
+static int get_start_level(struct realm *realm)
+{
+	return 4 - ((realm->ia_bits - 8) / (RMM_PAGE_SHIFT - 3));
+}
+
+static void free_delegated_granule(phys_addr_t phys)
+{
+	if (WARN_ON(rmi_granule_undelegate(phys))) {
+		/* Undelegate failed: leak the page */
+		return;
+	}
+
+	kvm_account_pgtable_pages(phys_to_virt(phys), -1);
+
+	free_page((unsigned long)phys_to_virt(phys));
+}
+
+/* Calculate the number of s2 root rtts needed */
+static int realm_num_root_rtts(struct realm *realm)
+{
+	unsigned int ipa_bits = realm->ia_bits;
+	unsigned int levels = 3 - get_start_level(realm);
+	unsigned int sl_ipa_bits = (levels + 1) * (RMM_PAGE_SHIFT - 3) +
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
+		goto out_undelegate_tables;
+	}
+
+	realm->rd = rd;
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
+/* Protects access to rme_vmid_bitmap */
+static DEFINE_SPINLOCK(rme_vmid_lock);
+static unsigned long *rme_vmid_bitmap;
+
+static int rme_vmid_init(void)
+{
+	unsigned int vmid_count = 1 << kvm_get_vmid_bits();
+
+	rme_vmid_bitmap = bitmap_zalloc(vmid_count, GFP_KERNEL);
+	if (!rme_vmid_bitmap) {
+		kvm_err("%s: Couldn't allocate rme vmid bitmap\n", __func__);
+		return -ENOMEM;
+	}
+
+	return 0;
+}
+
+static int rme_vmid_reserve(void)
+{
+	int ret;
+	unsigned int vmid_count = 1 << kvm_get_vmid_bits();
+
+	spin_lock(&rme_vmid_lock);
+	ret = bitmap_find_free_region(rme_vmid_bitmap, vmid_count, 0);
+	spin_unlock(&rme_vmid_lock);
+
+	return ret;
+}
+
+static void rme_vmid_release(unsigned int vmid)
+{
+	spin_lock(&rme_vmid_lock);
+	bitmap_release_region(rme_vmid_bitmap, vmid, 0);
+	spin_unlock(&rme_vmid_lock);
+}
+
+static int kvm_create_realm(struct kvm *kvm)
+{
+	struct realm *realm = &kvm->arch.realm;
+	int ret;
+
+	if (!kvm_is_realm(kvm))
+		return -EINVAL;
+	if (kvm_realm_is_created(kvm))
+		return -EEXIST;
+
+	ret = rme_vmid_reserve();
+	if (ret < 0)
+		return ret;
+	realm->vmid = ret;
+
+	ret = realm_create_rd(kvm);
+	if (ret) {
+		rme_vmid_release(realm->vmid);
+		return ret;
+	}
+
+	WRITE_ONCE(realm->state, REALM_STATE_NEW);
+
+	/* The realm is up, free the parameters.  */
+	free_page((unsigned long)realm->params);
+	realm->params = NULL;
+
+	return 0;
+}
+
+static int config_realm_hash_algo(struct realm *realm,
+				  struct arm_rme_config *cfg)
+{
+	switch (cfg->hash_algo) {
+	case ARM_RME_CONFIG_MEASUREMENT_ALGO_SHA256:
+		if (!rme_has_feature(RMI_FEATURE_REGISTER_0_HASH_SHA_256))
+			return -EINVAL;
+		break;
+	case ARM_RME_CONFIG_MEASUREMENT_ALGO_SHA512:
+		if (!rme_has_feature(RMI_FEATURE_REGISTER_0_HASH_SHA_512))
+			return -EINVAL;
+		break;
+	default:
+		return -EINVAL;
+	}
+	realm->params->hash_algo = cfg->hash_algo;
+	return 0;
+}
+
+static int kvm_rme_config_realm(struct kvm *kvm, struct kvm_enable_cap *cap)
+{
+	struct arm_rme_config cfg;
+	struct realm *realm = &kvm->arch.realm;
+	int r = 0;
+
+	if (kvm_realm_is_created(kvm))
+		return -EBUSY;
+
+	if (copy_from_user(&cfg, (void __user *)cap->args[1], sizeof(cfg)))
+		return -EFAULT;
+
+	switch (cfg.cfg) {
+	case ARM_RME_CONFIG_RPV:
+		memcpy(&realm->params->rpv, &cfg.rpv, sizeof(cfg.rpv));
+		break;
+	case ARM_RME_CONFIG_HASH_ALGO:
+		r = config_realm_hash_algo(realm, &cfg);
+		break;
+	default:
+		r = -EINVAL;
+	}
+
+	return r;
+}
+
+int kvm_realm_enable_cap(struct kvm *kvm, struct kvm_enable_cap *cap)
+{
+	int r = 0;
+
+	if (!kvm_is_realm(kvm))
+		return -EINVAL;
+
+	switch (cap->args[0]) {
+	case KVM_CAP_ARM_RME_CONFIG_REALM:
+		r = kvm_rme_config_realm(kvm, cap);
+		break;
+	case KVM_CAP_ARM_RME_CREATE_REALM:
+		r = kvm_create_realm(kvm);
+		break;
+	default:
+		r = -EINVAL;
+		break;
+	}
+
+	return r;
+}
+
+void kvm_destroy_realm(struct kvm *kvm)
+{
+	struct realm *realm = &kvm->arch.realm;
+	size_t pgd_size = kvm_pgtable_stage2_pgd_size(kvm->arch.mmu.vtcr);
+	int i;
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
+	rme_vmid_release(realm->vmid);
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
 void kvm_init_rme(void)
 {
 	if (PAGE_SIZE != SZ_4K)
@@ -52,5 +365,11 @@ void kvm_init_rme(void)
 		/* Continue without realm support */
 		return;
 
+	if (WARN_ON(rmi_features(0, &rmm_feat_reg0)))
+		return;
+
+	if (rme_vmid_init())
+		return;
+
 	/* Future patch will enable static branch kvm_rme_is_available */
 }

---

## [9] Steven Price — 2025-04-16
*Subject: [PATCH v8 08/43] kvm: arm64: Don't expose debug capabilities for realm guests*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

RMM v1.0 provides no mechanism for the host to perform debug operations
on the guest. So don't expose KVM_CAP_SET_GUEST_DEBUG and report 0
breakpoints and 0 watch points.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v7:
 * Remove the helper functions and inline the kvm_is_realm() check with
   a ternary operator.
 * Rewrite the commit message to explain this patch.
---
 arch/arm64/kvm/arm.c | 8 +++++---
 1 file changed, 5 insertions(+), 3 deletions(-)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 0e8482fdc4d3..c24448966529 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -331,7 +331,6 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 	case KVM_CAP_ARM_IRQ_LINE_LAYOUT_2:
 	case KVM_CAP_ARM_NISV_TO_USER:
 	case KVM_CAP_ARM_INJECT_EXT_DABT:
-	case KVM_CAP_SET_GUEST_DEBUG:
 	case KVM_CAP_VCPU_ATTRIBUTES:
 	case KVM_CAP_PTP_KVM:
 	case KVM_CAP_ARM_SYSTEM_SUSPEND:
@@ -340,6 +339,9 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 	case KVM_CAP_ARM_WRITABLE_IMP_ID_REGS:
 		r = 1;
 		break;
+	case KVM_CAP_SET_GUEST_DEBUG:
+		r = !kvm_is_realm(kvm);
+		break;
 	case KVM_CAP_SET_GUEST_DEBUG2:
 		return KVM_GUESTDBG_VALID_MASK;
 	case KVM_CAP_ARM_SET_DEVICE_ADDR:
@@ -385,10 +387,10 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 		r = cpus_have_final_cap(ARM64_HAS_32BIT_EL1);
 		break;
 	case KVM_CAP_GUEST_DEBUG_HW_BPS:
-		r = get_num_brps();
+		r = kvm_is_realm(kvm) ? 0 : get_num_brps();
 		break;
 	case KVM_CAP_GUEST_DEBUG_HW_WPS:
-		r = get_num_wrps();
+		r = kvm_is_realm(kvm) ? 0 : get_num_wrps();
 		break;
 	case KVM_CAP_ARM_PMU_V3:
 		r = kvm_supports_guest_pmuv3();

---

## [10] Steven Price — 2025-04-16
*Subject: [PATCH v8 09/43] KVM: arm64: Allow passing machine type in KVM creation*

Previously machine type was used purely for specifying the physical
address size of the guest. Reserve the higher bits to specify an ARM
specific machine type and declare a new type 'KVM_VM_TYPE_ARM_REALM'
used to create a realm guest.

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v7:
 * Add some documentation explaining the new machine type.
Changes since v6:
 * Make the check for kvm_rme_is_available more visible and report an
   error code of -EPERM (instead of -EINVAL) to make it explicit that
   the kernel supports RME, but the platform doesn't.
---
 Documentation/virt/kvm/api.rst | 16 ++++++++++++++--
 arch/arm64/kvm/arm.c           | 15 +++++++++++++++
 arch/arm64/kvm/mmu.c           |  3 ---
 include/uapi/linux/kvm.h       | 19 +++++++++++++++----
 4 files changed, 44 insertions(+), 9 deletions(-)

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index 99ba6c82cf37..54ae0b98030e 100644
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
index c24448966529..ba55950e6a6e 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -172,6 +172,21 @@ int kvm_arch_init_vm(struct kvm *kvm, unsigned long type)
 	mutex_unlock(&kvm->lock);
 #endif
 
+	if (type & ~(KVM_VM_TYPE_ARM_MASK | KVM_VM_TYPE_ARM_IPA_SIZE_MASK))
+		return -EINVAL;
+
+	switch (type & KVM_VM_TYPE_ARM_MASK) {
+	case KVM_VM_TYPE_ARM_NORMAL:
+		break;
+	case KVM_VM_TYPE_ARM_REALM:
+		if (!static_branch_unlikely(&kvm_rme_is_available))
+			return -EPERM;
+		kvm->arch.is_realm = true;
+		break;
+	default:
+		return -EINVAL;
+	}
+
 	kvm_init_nested(kvm);
 
 	ret = kvm_share_hyp(kvm, kvm + 1);
diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index 5957a07de86d..7531211f7e25 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -886,9 +886,6 @@ static int kvm_init_ipa_range(struct kvm *kvm,
 	if (kvm_is_realm(kvm))
 		kvm_ipa_limit = kvm_realm_ipa_limit();
 
-	if (type & ~KVM_VM_TYPE_ARM_IPA_SIZE_MASK)
-		return -EINVAL;
-
 	phys_shift = KVM_VM_TYPE_ARM_IPA_SIZE(type);
 	if (is_protected_kvm_enabled()) {
 		phys_shift = kvm_ipa_limit;
diff --git a/include/uapi/linux/kvm.h b/include/uapi/linux/kvm.h
index 0b8479985581..957e4646ec99 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -644,14 +644,25 @@ struct kvm_enable_cap {
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

## [11] Steven Price — 2025-04-16
*Subject: [PATCH v8 10/43] arm64: RME: RTT tear down*

The RMM owns the stage 2 page tables for a realm, and KVM must request
that the RMM creates/destroys entries as necessary. The physical pages
to store the page tables are delegated to the realm as required, and can
be undelegated when no longer used.

Creating new RTTs is the easy part, tearing down is a little more
tricky. The result of realm_rtt_destroy() can be used to effectively
walk the tree and destroy the entries (undelegating pages that were
given to the realm).

Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
---
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
 arch/arm64/include/asm/kvm_rme.h |   7 ++
 arch/arm64/kvm/mmu.c             |   6 +-
 arch/arm64/kvm/rme.c             | 128 +++++++++++++++++++++++++++++++
 3 files changed, 138 insertions(+), 3 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index 5dc1915de891..5f0de9a6d339 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -71,5 +71,12 @@ u32 kvm_realm_ipa_limit(void);
 int kvm_realm_enable_cap(struct kvm *kvm, struct kvm_enable_cap *cap);
 int kvm_init_realm_vm(struct kvm *kvm);
 void kvm_destroy_realm(struct kvm *kvm);
+void kvm_realm_destroy_rtts(struct kvm *kvm, u32 ia_bits);
+
+static inline bool kvm_realm_is_private_address(struct realm *realm,
+						unsigned long addr)
+{
+	return !(addr & BIT(realm->ia_bits - 1));
+}
 
 #endif /* __ASM_KVM_RME_H */
diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index 7531211f7e25..d80a9d408f71 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -1070,14 +1070,15 @@ void stage2_unmap_vm(struct kvm *kvm)
 void kvm_free_stage2_pgd(struct kvm_s2_mmu *mmu)
 {
 	struct kvm *kvm = kvm_s2_mmu_to_kvm(mmu);
-	struct kvm_pgtable *pgt = NULL;
+	struct kvm_pgtable *pgt;
 
 	write_lock(&kvm->mmu_lock);
+	pgt = mmu->pgt;
 	if (kvm_is_realm(kvm) &&
 	    (kvm_realm_state(kvm) != REALM_STATE_DEAD &&
 	     kvm_realm_state(kvm) != REALM_STATE_NONE)) {
-		/* Tearing down RTTs will be added in a later patch */
 		write_unlock(&kvm->mmu_lock);
+		kvm_realm_destroy_rtts(kvm, pgt->ia_bits);
 
 		/*
 		 * The physical PGD pages are delegated to the RMM, so cannot
@@ -1087,7 +1088,6 @@ void kvm_free_stage2_pgd(struct kvm_s2_mmu *mmu)
 		 */
 		return;
 	}
-	pgt = mmu->pgt;
 	if (pgt) {
 		mmu->pgd_phys = 0;
 		mmu->pgt = NULL;
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index dbb6521fe380..3053261c3b52 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
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
+static inline unsigned long rme_rtt_level_mapsize(int level)
+{
+	if (WARN_ON(level > RMM_RTT_MAX_LEVEL))
+		return RMM_PAGE_SIZE;
+
+	return (1UL << RMM_RTT_LEVEL_SHIFT(level));
+}
+
 static bool rme_has_feature(unsigned long feature)
 {
 	return !!u64_get_bits(rmm_feat_reg0, feature);
@@ -173,6 +189,118 @@ static int realm_create_rd(struct kvm *kvm)
 	return r;
 }
 
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
+	map_size = rme_rtt_level_mapsize(level - 1);
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
+			free_delegated_granule(rtt_granule);
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
+	return realm_tear_down_rtt_level(realm, get_start_level(realm) + 1,
+					 start, end);
+}
+
+void kvm_realm_destroy_rtts(struct kvm *kvm, u32 ia_bits)
+{
+	struct realm *realm = &kvm->arch.realm;
+
+	WARN_ON(realm_tear_down_rtt_range(realm, 0, (1UL << ia_bits)));
+}
+
 /* Protects access to rme_vmid_bitmap */
 static DEFINE_SPINLOCK(rme_vmid_lock);
 static unsigned long *rme_vmid_bitmap;

---

## [12] Steven Price — 2025-04-16
*Subject: [PATCH v8 11/43] arm64: RME: Allocate/free RECs to match vCPUs*

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
explicitly requests this e.g. by performing a PSCI call). The RMM also
requires that the VMM creates RECs in ascending order of the MPIDR.

See Realm Management Monitor specification (DEN0137) for more information:
https://developer.arm.com/documentation/den0137/

Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
---
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
 arch/arm64/include/asm/kvm_emulate.h |   7 ++
 arch/arm64/include/asm/kvm_host.h    |   3 +
 arch/arm64/include/asm/kvm_rme.h     |  27 ++++
 arch/arm64/kvm/arm.c                 |  13 +-
 arch/arm64/kvm/reset.c               |  11 ++
 arch/arm64/kvm/rme.c                 | 180 +++++++++++++++++++++++++++
 6 files changed, 239 insertions(+), 2 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_emulate.h b/arch/arm64/include/asm/kvm_emulate.h
index 4ee6c215da82..c803c8188d9c 100644
--- a/arch/arm64/include/asm/kvm_emulate.h
+++ b/arch/arm64/include/asm/kvm_emulate.h
@@ -706,7 +706,14 @@ static inline bool kvm_realm_is_created(struct kvm *kvm)
 
 static inline bool vcpu_is_rec(struct kvm_vcpu *vcpu)
 {
+	if (static_branch_unlikely(&kvm_rme_is_available))
+		return vcpu_has_feature(vcpu, KVM_ARM_VCPU_REC);
 	return false;
 }
 
+static inline bool kvm_arm_rec_finalized(struct kvm_vcpu *vcpu)
+{
+	return vcpu->arch.rec.mpidr != INVALID_HWID;
+}
+
 #endif /* __ARM64_KVM_EMULATE_H__ */
diff --git a/arch/arm64/include/asm/kvm_host.h b/arch/arm64/include/asm/kvm_host.h
index 7bd81b86eab0..ceb5e60ae5ae 100644
--- a/arch/arm64/include/asm/kvm_host.h
+++ b/arch/arm64/include/asm/kvm_host.h
@@ -828,6 +828,9 @@ struct kvm_vcpu_arch {
 
 	/* Per-vcpu CCSIDR override or NULL */
 	u32 *ccsidr;
+
+	/* Realm meta data */
+	struct realm_rec rec;
 };
 
 /*
diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index 5f0de9a6d339..f716b890e484 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -6,6 +6,7 @@
 #ifndef __ASM_KVM_RME_H
 #define __ASM_KVM_RME_H
 
+#include <asm/rmi_smc.h>
 #include <uapi/linux/kvm.h>
 
 /**
@@ -65,6 +66,30 @@ struct realm {
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
+	 * REC_PARAMS_AUX_GRANULES is the maximum number of granules that the
+	 * RMM can require. By using that to size the array we know that it
+	 * will be big enough as the page size is always at least as large as
+	 * the granule size. In the case of a larger page size than 4k (or an
+	 * RMM which requires fewer auxiliary granules), the array will be
+	 * bigger than needed however the extra memory required is small and
+	 * this keeps the code cleaner.
+	 */
+	struct page *aux_pages[REC_PARAMS_AUX_GRANULES];
+	struct rec_run *run;
+};
+
 void kvm_init_rme(void);
 u32 kvm_realm_ipa_limit(void);
 
@@ -72,6 +97,8 @@ int kvm_realm_enable_cap(struct kvm *kvm, struct kvm_enable_cap *cap);
 int kvm_init_realm_vm(struct kvm *kvm);
 void kvm_destroy_realm(struct kvm *kvm);
 void kvm_realm_destroy_rtts(struct kvm *kvm, u32 ia_bits);
+int kvm_create_rec(struct kvm_vcpu *vcpu);
+void kvm_destroy_rec(struct kvm_vcpu *vcpu);
 
 static inline bool kvm_realm_is_private_address(struct realm *realm,
 						unsigned long addr)
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index ba55950e6a6e..fd83efb667cc 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -489,6 +489,8 @@ int kvm_arch_vcpu_create(struct kvm_vcpu *vcpu)
 	/* Force users to call KVM_ARM_VCPU_INIT */
 	vcpu_clear_flag(vcpu, VCPU_INITIALIZED);
 
+	vcpu->arch.rec.mpidr = INVALID_HWID;
+
 	vcpu->arch.mmu_page_cache.gfp_zero = __GFP_ZERO;
 
 	/* Set up the timer */
@@ -1447,7 +1449,7 @@ int kvm_vm_ioctl_irq_line(struct kvm *kvm, struct kvm_irq_level *irq_level,
 	return -EINVAL;
 }
 
-static unsigned long system_supported_vcpu_features(void)
+static unsigned long system_supported_vcpu_features(struct kvm *kvm)
 {
 	unsigned long features = KVM_VCPU_VALID_FEATURES;
 
@@ -1468,6 +1470,9 @@ static unsigned long system_supported_vcpu_features(void)
 	if (!cpus_have_final_cap(ARM64_HAS_NESTED_VIRT))
 		clear_bit(KVM_ARM_VCPU_HAS_EL2, &features);
 
+	if (!kvm_is_realm(kvm))
+		clear_bit(KVM_ARM_VCPU_REC, &features);
+
 	return features;
 }
 
@@ -1485,7 +1490,7 @@ static int kvm_vcpu_init_check_features(struct kvm_vcpu *vcpu,
 			return -ENOENT;
 	}
 
-	if (features & ~system_supported_vcpu_features())
+	if (features & ~system_supported_vcpu_features(vcpu->kvm))
 		return -EINVAL;
 
 	/*
@@ -1507,6 +1512,10 @@ static int kvm_vcpu_init_check_features(struct kvm_vcpu *vcpu,
 	if (test_bit(KVM_ARM_VCPU_HAS_EL2, &features))
 		return -EINVAL;
 
+	/* RME is incompatible with AArch32 */
+	if (test_bit(KVM_ARM_VCPU_REC, &features))
+		return -EINVAL;
+
 	return 0;
 }
 
diff --git a/arch/arm64/kvm/reset.c b/arch/arm64/kvm/reset.c
index f82fcc614e13..7ba3c7918a0b 100644
--- a/arch/arm64/kvm/reset.c
+++ b/arch/arm64/kvm/reset.c
@@ -137,6 +137,11 @@ int kvm_arm_vcpu_finalize(struct kvm_vcpu *vcpu, int feature)
 			return -EPERM;
 
 		return kvm_vcpu_finalize_sve(vcpu);
+	case KVM_ARM_VCPU_REC:
+		if (!kvm_is_realm(vcpu->kvm) || !vcpu_is_rec(vcpu))
+			return -EINVAL;
+
+		return kvm_create_rec(vcpu);
 	}
 
 	return -EINVAL;
@@ -147,6 +152,11 @@ bool kvm_arm_vcpu_is_finalized(struct kvm_vcpu *vcpu)
 	if (vcpu_has_sve(vcpu) && !kvm_arm_vcpu_sve_finalized(vcpu))
 		return false;
 
+	if (kvm_is_realm(vcpu->kvm) &&
+	    !(vcpu_is_rec(vcpu) && kvm_arm_rec_finalized(vcpu) &&
+	      READ_ONCE(vcpu->kvm->arch.realm.state) == REALM_STATE_ACTIVE))
+		return false;
+
 	return true;
 }
 
@@ -159,6 +169,7 @@ void kvm_arm_vcpu_destroy(struct kvm_vcpu *vcpu)
 		kvm_unshare_hyp(sve_state, sve_state + vcpu_sve_state_size(vcpu));
 	kfree(sve_state);
 	kfree(vcpu->arch.ccsidr);
+	kvm_destroy_rec(vcpu);
 }
 
 static void kvm_vcpu_reset_sve(struct kvm_vcpu *vcpu)
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 3053261c3b52..f4923fc3b34e 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -474,6 +474,186 @@ void kvm_destroy_realm(struct kvm *kvm)
 	kvm_free_stage2_pgd(&kvm->arch.mmu);
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
+int kvm_create_rec(struct kvm_vcpu *vcpu)
+{
+	struct user_pt_regs *vcpu_regs = vcpu_gp_regs(vcpu);
+	unsigned long mpidr = kvm_vcpu_get_mpidr_aff(vcpu);
+	struct realm *realm = &vcpu->kvm->arch.realm;
+	struct realm_rec *rec = &vcpu->arch.rec;
+	unsigned long rec_page_phys;
+	struct rec_params *params;
+	int r, i;
+
+	if (kvm_realm_state(vcpu->kvm) != REALM_STATE_NEW)
+		return -ENOENT;
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
 int kvm_init_realm_vm(struct kvm *kvm)
 {
 	kvm->arch.realm.params = (void *)get_zeroed_page(GFP_KERNEL);

---

## [13] Steven Price — 2025-04-16
*Subject: [PATCH v8 12/43] KVM: arm64: vgic: Provide helper for number of list registers*

Currently the number of list registers available is stored in a global
(kvm_vgic_global_state.nr_lr). With Arm CCA the RMM is permitted to
reserve list registers for its own use and so the number of available
list registers can be fewer for a realm VM. Provide a wrapper function
to fetch the global in preparation for restricting nr_lr when dealing
with a realm VM.

Signed-off-by: Steven Price <steven.price@arm.com>
---
New patch for v6
---
 arch/arm64/kvm/vgic/vgic.c | 11 ++++++++---
 1 file changed, 8 insertions(+), 3 deletions(-)

diff --git a/arch/arm64/kvm/vgic/vgic.c b/arch/arm64/kvm/vgic/vgic.c
index 8f8096d48925..8d189ce18ea0 100644
--- a/arch/arm64/kvm/vgic/vgic.c
+++ b/arch/arm64/kvm/vgic/vgic.c
@@ -21,6 +21,11 @@ struct vgic_global kvm_vgic_global_state __ro_after_init = {
 	.gicv3_cpuif = STATIC_KEY_FALSE_INIT,
 };
 
+static inline int kvm_vcpu_vgic_nr_lr(struct kvm_vcpu *vcpu)
+{
+	return kvm_vgic_global_state.nr_lr;
+}
+
 /*
  * Locking order is always:
  * kvm->lock (mutex)
@@ -802,7 +807,7 @@ static void vgic_flush_lr_state(struct kvm_vcpu *vcpu)
 	lockdep_assert_held(&vgic_cpu->ap_list_lock);
 
 	count = compute_ap_list_depth(vcpu, &multi_sgi);
-	if (count > kvm_vgic_global_state.nr_lr || multi_sgi)
+	if (count > kvm_vcpu_vgic_nr_lr(vcpu) || multi_sgi)
 		vgic_sort_ap_list(vcpu);
 
 	count = 0;
@@ -831,7 +836,7 @@ static void vgic_flush_lr_state(struct kvm_vcpu *vcpu)
 
 		raw_spin_unlock(&irq->irq_lock);
 
-		if (count == kvm_vgic_global_state.nr_lr) {
+		if (count == kvm_vcpu_vgic_nr_lr(vcpu)) {
 			if (!list_is_last(&irq->ap_list,
 					  &vgic_cpu->ap_list_head))
 				vgic_set_underflow(vcpu);
@@ -840,7 +845,7 @@ static void vgic_flush_lr_state(struct kvm_vcpu *vcpu)
 	}
 
 	/* Nuke remaining LRs */
-	for (i = count ; i < kvm_vgic_global_state.nr_lr; i++)
+	for (i = count ; i < kvm_vcpu_vgic_nr_lr(vcpu); i++)
 		vgic_clear_lr(vcpu, i);
 
 	if (!static_branch_unlikely(&kvm_vgic_global_state.gicv3_cpuif))

---

## [14] Steven Price — 2025-04-16
*Subject: [PATCH v8 13/43] arm64: RME: Support for the VGIC in realms*

The RMM provides emulation of a VGIC to the realm guest but delegates
much of the handling to the host. Implement support in KVM for
saving/restoring state to/from the REC structure.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes from v5:
 * Handle RMM providing fewer GIC LRs than the hardware supports.
---
 arch/arm64/include/asm/kvm_rme.h |  1 +
 arch/arm64/kvm/arm.c             | 16 +++++++++---
 arch/arm64/kvm/rme.c             |  5 ++++
 arch/arm64/kvm/vgic/vgic-init.c  |  2 +-
 arch/arm64/kvm/vgic/vgic-v3.c    |  6 ++++-
 arch/arm64/kvm/vgic/vgic.c       | 43 ++++++++++++++++++++++++++++++--
 6 files changed, 66 insertions(+), 7 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index f716b890e484..9bcad6ec5dbb 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -92,6 +92,7 @@ struct realm_rec {
 
 void kvm_init_rme(void);
 u32 kvm_realm_ipa_limit(void);
+u32 kvm_realm_vgic_nr_lr(void);
 
 int kvm_realm_enable_cap(struct kvm *kvm, struct kvm_enable_cap *cap);
 int kvm_init_realm_vm(struct kvm *kvm);
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index fd83efb667cc..808d7e479571 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -683,19 +683,24 @@ void kvm_arch_vcpu_put(struct kvm_vcpu *vcpu)
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
@@ -912,6 +917,11 @@ int kvm_arch_vcpu_run_pid_change(struct kvm_vcpu *vcpu)
 			return ret;
 	}
 
+	if (!irqchip_in_kernel(kvm) && kvm_is_realm(vcpu->kvm)) {
+		/* Userspace irqchip not yet supported with Realms */
+		return -EOPNOTSUPP;
+	}
+
 	mutex_lock(&kvm->arch.config_lock);
 	set_bit(KVM_ARCH_FLAG_HAS_RAN_ONCE, &kvm->arch.flags);
 	mutex_unlock(&kvm->arch.config_lock);
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index f4923fc3b34e..1239eb07aca6 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
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
 	return 4 - ((realm->ia_bits - 8) / (RMM_PAGE_SHIFT - 3));
diff --git a/arch/arm64/kvm/vgic/vgic-init.c b/arch/arm64/kvm/vgic/vgic-init.c
index 1f33e71c2a73..a81c7f3d1d42 100644
--- a/arch/arm64/kvm/vgic/vgic-init.c
+++ b/arch/arm64/kvm/vgic/vgic-init.c
@@ -81,7 +81,7 @@ int kvm_vgic_create(struct kvm *kvm, u32 type)
 	 * the proper checks already.
 	 */
 	if (type == KVM_DEV_TYPE_ARM_VGIC_V2 &&
-		!kvm_vgic_global_state.can_emulate_gicv2)
+	    (!kvm_vgic_global_state.can_emulate_gicv2 || kvm_is_realm(kvm)))
 		return -ENODEV;
 
 	/* Must be held to avoid race with vCPU creation */
diff --git a/arch/arm64/kvm/vgic/vgic-v3.c b/arch/arm64/kvm/vgic/vgic-v3.c
index b9ad7c42c5b0..c10ad817030d 100644
--- a/arch/arm64/kvm/vgic/vgic-v3.c
+++ b/arch/arm64/kvm/vgic/vgic-v3.c
@@ -8,9 +8,11 @@
 #include <linux/kvm_host.h>
 #include <linux/string_choices.h>
 #include <kvm/arm_vgic.h>
+#include <asm/kvm_emulate.h>
 #include <asm/kvm_hyp.h>
 #include <asm/kvm_mmu.h>
 #include <asm/kvm_asm.h>
+#include <asm/rmi_smc.h>
 
 #include "vgic.h"
 
@@ -758,7 +760,9 @@ void vgic_v3_put(struct kvm_vcpu *vcpu)
 		return;
 	}
 
-	if (likely(!is_protected_kvm_enabled()))
+	if (vcpu_is_rec(vcpu))
+		cpu_if->vgic_vmcr = vcpu->arch.rec.run->exit.gicv3_vmcr;
+	else if (likely(!is_protected_kvm_enabled()))
 		kvm_call_hyp(__vgic_v3_save_vmcr_aprs, cpu_if);
 	WARN_ON(vgic_v4_put(vcpu));
 
diff --git a/arch/arm64/kvm/vgic/vgic.c b/arch/arm64/kvm/vgic/vgic.c
index 8d189ce18ea0..c68a41a29917 100644
--- a/arch/arm64/kvm/vgic/vgic.c
+++ b/arch/arm64/kvm/vgic/vgic.c
@@ -10,7 +10,9 @@
 #include <linux/list_sort.h>
 #include <linux/nospec.h>
 
+#include <asm/kvm_emulate.h>
 #include <asm/kvm_hyp.h>
+#include <asm/kvm_rme.h>
 
 #include "vgic.h"
 
@@ -23,6 +25,8 @@ struct vgic_global kvm_vgic_global_state __ro_after_init = {
 
 static inline int kvm_vcpu_vgic_nr_lr(struct kvm_vcpu *vcpu)
 {
+	if (unlikely(vcpu_is_rec(vcpu)))
+		return kvm_realm_vgic_nr_lr();
 	return kvm_vgic_global_state.nr_lr;
 }
 
@@ -864,10 +868,23 @@ static inline bool can_access_vgic_from_kernel(void)
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
@@ -903,10 +920,28 @@ void kvm_vgic_sync_hwstate(struct kvm_vcpu *vcpu)
 	vgic_prune_ap_list(vcpu);
 }
 
+static inline void vgic_rmm_restore_state(struct kvm_vcpu *vcpu)
+{
+	struct vgic_v3_cpu_if *cpu_if = &vcpu->arch.vgic_cpu.vgic_v3;
+	int i;
+
+	for (i = 0; i < kvm_vcpu_vgic_nr_lr(vcpu); i++) {
+		vcpu->arch.rec.run->enter.gicv3_lrs[i] = cpu_if->vgic_lr[i];
+		/*
+		 * Also populate the rec.run->exit copies so that a late
+		 * decision to back out from entering the realm doesn't cause
+		 * the state to be lost
+		 */
+		vcpu->arch.rec.run->exit.gicv3_lrs[i] = cpu_if->vgic_lr[i];
+	}
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
@@ -976,7 +1011,9 @@ void kvm_vgic_flush_hwstate(struct kvm_vcpu *vcpu)
 
 void kvm_vgic_load(struct kvm_vcpu *vcpu)
 {
-	if (unlikely(!irqchip_in_kernel(vcpu->kvm) || !vgic_initialized(vcpu->kvm))) {
+	if (unlikely(!irqchip_in_kernel(vcpu->kvm) ||
+		     !vgic_initialized(vcpu->kvm) ||
+		     vcpu_is_rec(vcpu))) {
 		if (has_vhe() && static_branch_unlikely(&kvm_vgic_global_state.gicv3_cpuif))
 			__vgic_v3_activate_traps(&vcpu->arch.vgic_cpu.vgic_v3);
 		return;
@@ -990,7 +1027,9 @@ void kvm_vgic_load(struct kvm_vcpu *vcpu)
 
 void kvm_vgic_put(struct kvm_vcpu *vcpu)
 {
-	if (unlikely(!irqchip_in_kernel(vcpu->kvm) || !vgic_initialized(vcpu->kvm))) {
+	if (unlikely(!irqchip_in_kernel(vcpu->kvm) ||
+		     !vgic_initialized(vcpu->kvm) ||
+		     vcpu_is_rec(vcpu))) {
 		if (has_vhe() && static_branch_unlikely(&kvm_vgic_global_state.gicv3_cpuif))
 			__vgic_v3_deactivate_traps(&vcpu->arch.vgic_cpu.vgic_v3);
 		return;

---

## [15] Steven Price — 2025-04-16
*Subject: [PATCH v8 14/43] KVM: arm64: Support timers in realm RECs*

The RMM keeps track of the timer while the realm REC is running, but on
exit to the normal world KVM is responsible for handling the timers.

The RMM doesn't provide a mechanism to set the counter offset, so don't
expose KVM_CAP_COUNTER_OFFSET for a realm VM.

A later patch adds the support for propagating the timer values from the
exit data structure and calling kvm_realm_timers_update().

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v7:
 * Hide KVM_CAP_COUNTER_OFFSET for realm guests.
---
 arch/arm64/kvm/arch_timer.c  | 48 +++++++++++++++++++++++++++++++++---
 arch/arm64/kvm/arm.c         |  2 +-
 include/kvm/arm_arch_timer.h |  2 ++
 3 files changed, 47 insertions(+), 5 deletions(-)

diff --git a/arch/arm64/kvm/arch_timer.c b/arch/arm64/kvm/arch_timer.c
index 5133dcbfe9f7..3dfc25873be2 100644
--- a/arch/arm64/kvm/arch_timer.c
+++ b/arch/arm64/kvm/arch_timer.c
@@ -148,6 +148,13 @@ static void timer_set_cval(struct arch_timer_context *ctxt, u64 cval)
 
 static void timer_set_offset(struct arch_timer_context *ctxt, u64 offset)
 {
+	struct kvm_vcpu *vcpu = ctxt->vcpu;
+
+	if (kvm_is_realm(vcpu->kvm)) {
+		WARN_ON(offset);
+		return;
+	}
+
 	if (!ctxt->offset.vm_offset) {
 		WARN(offset, "timer %ld\n", arch_timer_ctx_index(ctxt));
 		return;
@@ -462,6 +469,21 @@ static void kvm_timer_update_irq(struct kvm_vcpu *vcpu, bool new_level,
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
@@ -870,6 +892,8 @@ void kvm_timer_vcpu_load(struct kvm_vcpu *vcpu)
 	if (unlikely(!timer->enabled))
 		return;
 
+	kvm_timer_unblocking(vcpu);
+
 	get_timer_map(vcpu, &map);
 
 	if (static_branch_likely(&has_gic_active_state)) {
@@ -883,8 +907,6 @@ void kvm_timer_vcpu_load(struct kvm_vcpu *vcpu)
 		kvm_timer_vcpu_load_nogic(vcpu);
 	}
 
-	kvm_timer_unblocking(vcpu);
-
 	timer_restore_state(map.direct_vtimer);
 	if (map.direct_ptimer)
 		timer_restore_state(map.direct_ptimer);
@@ -1065,7 +1087,9 @@ static void timer_context_init(struct kvm_vcpu *vcpu, int timerid)
 
 	ctxt->vcpu = vcpu;
 
-	if (timerid == TIMER_VTIMER)
+	if (kvm_is_realm(vcpu->kvm))
+		ctxt->offset.vm_offset = NULL;
+	else if (timerid == TIMER_VTIMER)
 		ctxt->offset.vm_offset = &kvm->arch.timer_data.voffset;
 	else
 		ctxt->offset.vm_offset = &kvm->arch.timer_data.poffset;
@@ -1087,13 +1111,19 @@ static void timer_context_init(struct kvm_vcpu *vcpu, int timerid)
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
 
@@ -1633,6 +1663,13 @@ int kvm_timer_enable(struct kvm_vcpu *vcpu)
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
@@ -1764,6 +1801,9 @@ int kvm_vm_ioctl_set_counter_offset(struct kvm *kvm,
 	if (offset->reserved)
 		return -EINVAL;
 
+	if (kvm_is_realm(kvm))
+		return -EINVAL;
+
 	mutex_lock(&kvm->lock);
 
 	if (lock_all_vcpus(kvm)) {
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 808d7e479571..7c0bb1b05f4c 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -350,10 +350,10 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 	case KVM_CAP_PTP_KVM:
 	case KVM_CAP_ARM_SYSTEM_SUSPEND:
 	case KVM_CAP_IRQFD_RESAMPLE:
-	case KVM_CAP_COUNTER_OFFSET:
 	case KVM_CAP_ARM_WRITABLE_IMP_ID_REGS:
 		r = 1;
 		break;
+	case KVM_CAP_COUNTER_OFFSET:
 	case KVM_CAP_SET_GUEST_DEBUG:
 		r = !kvm_is_realm(kvm);
 		break;
diff --git a/include/kvm/arm_arch_timer.h b/include/kvm/arm_arch_timer.h
index 681cf0c8b9df..f64e317c091b 100644
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

## [16] Steven Price — 2025-04-16
*Subject: [PATCH v8 15/43] arm64: RME: Allow VMM to set RIPAS*

Each page within the protected region of the realm guest can be marked
as either RAM or EMPTY. Allow the VMM to control this before the guest
has started and provide the equivalent functions to change this (with
the guest's approval) at runtime.

When transitioning from RIPAS RAM (1) to RIPAS EMPTY (0) the memory is
unmapped from the guest and undelegated allowing the memory to be reused
by the host. When transitioning to RIPAS RAM the actual population of
the leaf RTTs is done later on stage 2 fault, however it may be
necessary to allocate additional RTTs to allow the RMM track the RIPAS
for the requested range.

When freeing a block mapping it is necessary to temporarily unfold the
RTT which requires delegating an extra page to the RMM, this page can
then be recovered once the contents of the block mapping have been
freed.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes from v7:
 * Replace use of "only_shared" with the upstream "attr_filter" field
   of struct kvm_gfn_range.
 * Clean up the logic in alloc_delegated_granule() for when to call
   kvm_account_pgtable_pages().
 * Rename realm_destroy_protected_granule() to
   realm_destroy_private_granule() to match the naming elsewhere. Also
   fix the return codes in the function to be descriptive.
 * Several other minor changes to names/return codes.
Changes from v6:
 * Split the code dealing with the guest triggering a RIPAS change into
   a separate patch, so this patch is purely for the VMM setting up the
   RIPAS before the guest first runs.
 * Drop the useless flags argument from alloc_delegated_granule().
 * Account RTTs allocated for a guest using kvm_account_pgtable_pages().
 * Deal with the RMM granule size potentially being smaller than the
   host's PAGE_SIZE. Although note alloc_delegated_granule() currently
   still allocates an entire host page for every RMM granule (so wasting
   memory when PAGE_SIZE>4k).
Changes from v5:
 * Adapt to rebasing.
 * Introduce find_map_level()
 * Rename some functions to be clearer.
 * Drop the "spare page" functionality.
Changes from v2:
 * {alloc,free}_delegated_page() moved from previous patch to this one.
 * alloc_delegated_page() now takes a gfp_t flags parameter.
 * Fix the reference counting of guestmem pages to avoid leaking memory.
 * Several misc code improvements and extra comments.
---
 arch/arm64/include/asm/kvm_rme.h |   5 +
 arch/arm64/kvm/mmu.c             |   8 +-
 arch/arm64/kvm/rme.c             | 384 +++++++++++++++++++++++++++++++
 3 files changed, 394 insertions(+), 3 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index 9bcad6ec5dbb..b916db8565a2 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -101,6 +101,11 @@ void kvm_realm_destroy_rtts(struct kvm *kvm, u32 ia_bits);
 int kvm_create_rec(struct kvm_vcpu *vcpu);
 void kvm_destroy_rec(struct kvm_vcpu *vcpu);
 
+void kvm_realm_unmap_range(struct kvm *kvm,
+			   unsigned long ipa,
+			   unsigned long size,
+			   bool unmap_private);
+
 static inline bool kvm_realm_is_private_address(struct realm *realm,
 						unsigned long addr)
 {
diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index d80a9d408f71..71c04259e39f 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -323,6 +323,7 @@ static void invalidate_icache_guest_page(void *va, size_t size)
  * @start: The intermediate physical base address of the range to unmap
  * @size:  The size of the area to unmap
  * @may_block: Whether or not we are permitted to block
+ * @only_shared: If true then protected mappings should not be unmapped
  *
  * Clear a range of stage-2 mappings, lowering the various ref-counts.  Must
  * be called while holding mmu_lock (unless for freeing the stage2 pgd before
@@ -330,7 +331,7 @@ static void invalidate_icache_guest_page(void *va, size_t size)
  * with things behind our backs.
  */
 static void __unmap_stage2_range(struct kvm_s2_mmu *mmu, phys_addr_t start, u64 size,
-				 bool may_block)
+				 bool may_block, bool only_shared)
 {
 	struct kvm *kvm = kvm_s2_mmu_to_kvm(mmu);
 	phys_addr_t end = start + size;
@@ -344,7 +345,7 @@ static void __unmap_stage2_range(struct kvm_s2_mmu *mmu, phys_addr_t start, u64
 void kvm_stage2_unmap_range(struct kvm_s2_mmu *mmu, phys_addr_t start,
 			    u64 size, bool may_block)
 {
-	__unmap_stage2_range(mmu, start, size, may_block);
+	__unmap_stage2_range(mmu, start, size, may_block, false);
 }
 
 void kvm_stage2_flush_range(struct kvm_s2_mmu *mmu, phys_addr_t addr, phys_addr_t end)
@@ -1975,7 +1976,8 @@ bool kvm_unmap_gfn_range(struct kvm *kvm, struct kvm_gfn_range *range)
 
 	__unmap_stage2_range(&kvm->arch.mmu, range->start << PAGE_SHIFT,
 			     (range->end - range->start) << PAGE_SHIFT,
-			     range->may_block);
+			     range->may_block,
+			     !(range->attr_filter & KVM_FILTER_PRIVATE));
 
 	kvm_nested_s2_unmap(kvm, range->may_block);
 	return false;
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 1239eb07aca6..33eb793d8bdb 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -87,6 +87,51 @@ static int get_start_level(struct realm *realm)
 	return 4 - ((realm->ia_bits - 8) / (RMM_PAGE_SHIFT - 3));
 }
 
+static int find_map_level(struct realm *realm,
+			  unsigned long start,
+			  unsigned long end)
+{
+	int level = RMM_RTT_MAX_LEVEL;
+
+	while (level > get_start_level(realm)) {
+		unsigned long map_size = rme_rtt_level_mapsize(level - 1);
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
+	if (mc)
+		virt = kvm_mmu_memory_cache_alloc(mc);
+	else
+		virt = (void *)__get_free_page(GFP_KERNEL_ACCOUNT);
+
+	if (!virt)
+		return PHYS_ADDR_MAX;
+
+	phys = virt_to_phys(virt);
+
+	if (rmi_granule_delegate(phys)) {
+		free_page((unsigned long)virt);
+
+		return PHYS_ADDR_MAX;
+	}
+
+	kvm_account_pgtable_pages(virt, 1);
+
+	return phys;
+}
+
 static void free_delegated_granule(phys_addr_t phys)
 {
 	if (WARN_ON(rmi_granule_undelegate(phys))) {
@@ -99,6 +144,154 @@ static void free_delegated_granule(phys_addr_t phys)
 	free_page((unsigned long)phys_to_virt(phys));
 }
 
+static int realm_rtt_create(struct realm *realm,
+			    unsigned long addr,
+			    int level,
+			    phys_addr_t phys)
+{
+	addr = ALIGN_DOWN(addr, rme_rtt_level_mapsize(level - 1));
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
+	ret = rmi_rtt_fold(virt_to_phys(realm->rd), addr, level, &out_rtt);
+
+	if (RMI_RETURN_STATUS(ret) == RMI_SUCCESS && rtt_granule)
+		*rtt_granule = out_rtt;
+
+	return ret;
+}
+
+static int realm_destroy_private_granule(struct realm *realm,
+					 unsigned long ipa,
+					 unsigned long *next_addr,
+					 phys_addr_t *out_rtt)
+{
+	unsigned long rd = virt_to_phys(realm->rd);
+	unsigned long rtt_addr;
+	phys_addr_t rtt;
+	int ret;
+
+retry:
+	ret = rmi_data_destroy(rd, ipa, &rtt_addr, next_addr);
+	if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
+		if (*next_addr > ipa)
+			return 0; /* UNASSIGNED */
+		rtt = alloc_delegated_granule(NULL);
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
+			free_delegated_granule(rtt);
+			return -ENXIO;
+		}
+		goto retry;
+	} else if (WARN_ON(ret)) {
+		return -ENXIO;
+	}
+
+	ret = rmi_granule_undelegate(rtt_addr);
+	if (WARN_ON(ret))
+		return -ENXIO;
+
+	*out_rtt = rtt_addr;
+
+	return 0;
+}
+
+static int realm_unmap_private_page(struct realm *realm,
+				    unsigned long ipa,
+				    unsigned long *next_addr)
+{
+	unsigned long end = ALIGN(ipa + 1, PAGE_SIZE);
+	unsigned long addr;
+	phys_addr_t out_rtt = PHYS_ADDR_MAX;
+	int ret;
+
+	for (addr = ipa; addr < end; addr = *next_addr) {
+		ret = realm_destroy_private_granule(realm, addr, next_addr,
+						    &out_rtt);
+		if (ret)
+			return ret;
+	}
+
+	if (out_rtt != PHYS_ADDR_MAX)
+		free_page((unsigned long)phys_to_virt(out_rtt));
+
+	return 0;
+}
+
+static void realm_unmap_shared_range(struct kvm *kvm,
+				     int level,
+				     unsigned long start,
+				     unsigned long end)
+{
+	struct realm *realm = &kvm->arch.realm;
+	unsigned long rd = virt_to_phys(realm->rd);
+	ssize_t map_size = rme_rtt_level_mapsize(level);
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
+						 min(next_addr, end));
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
+							 next_addr);
+			}
+			break;
+		default:
+			WARN_ON(1);
+			return;
+		}
+
+		cond_resched_rwlock_write(&kvm->mmu_lock);
+	}
+}
+
 /* Calculate the number of s2 root rtts needed */
 static int realm_num_root_rtts(struct realm *realm)
 {
@@ -209,6 +402,40 @@ static int realm_rtt_destroy(struct realm *realm, unsigned long addr,
 	return ret;
 }
 
+static int realm_create_rtt_levels(struct realm *realm,
+				   unsigned long ipa,
+				   int level,
+				   int max_level,
+				   struct kvm_mmu_memory_cache *mc)
+{
+	if (level == max_level)
+		return 0;
+
+	while (level++ < max_level) {
+		phys_addr_t rtt = alloc_delegated_granule(mc);
+		int ret;
+
+		if (rtt == PHYS_ADDR_MAX)
+			return -ENOMEM;
+
+		ret = realm_rtt_create(realm, ipa, level, rtt);
+
+		if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT &&
+		    RMI_RETURN_INDEX(ret) == level) {
+			/* The RTT already exists, continue */
+			continue;
+		}
+		if (ret) {
+			WARN(1, "Failed to create RTT at level %d: %d\n",
+			     level, ret);
+			free_delegated_granule(rtt);
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
@@ -299,6 +526,61 @@ static int realm_tear_down_rtt_range(struct realm *realm,
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
+	map_size = rme_rtt_level_mapsize(level - 1);
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
+			free_delegated_granule(rtt_granule);
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
+			if (ret < 0)
+				return ret;
+			else if (ret == 0)
+				/* Try again at this level */
+				next_addr = addr;
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
 void kvm_realm_destroy_rtts(struct kvm *kvm, u32 ia_bits)
 {
 	struct realm *realm = &kvm->arch.realm;
@@ -306,6 +588,96 @@ void kvm_realm_destroy_rtts(struct kvm *kvm, u32 ia_bits)
 	WARN_ON(realm_tear_down_rtt_range(realm, 0, (1UL << ia_bits)));
 }
 
+static void realm_unmap_private_range(struct kvm *kvm,
+				      unsigned long start,
+				      unsigned long end)
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
+	}
+
+	realm_fold_rtt_level(realm, get_start_level(realm) + 1,
+			     start, end);
+}
+
+void kvm_realm_unmap_range(struct kvm *kvm, unsigned long start,
+			   unsigned long size, bool unmap_private)
+{
+	unsigned long end = start + size;
+	struct realm *realm = &kvm->arch.realm;
+
+	end = min(BIT(realm->ia_bits - 1), end);
+
+	if (realm->state == REALM_STATE_NONE)
+		return;
+
+	realm_unmap_shared_range(kvm, find_map_level(realm, start, end),
+				 start, end);
+	if (unmap_private)
+		realm_unmap_private_range(kvm, start, end);
+}
+
+static int realm_init_ipa_state(struct realm *realm,
+				unsigned long ipa,
+				unsigned long end)
+{
+	phys_addr_t rd_phys = virt_to_phys(realm->rd);
+	int ret;
+
+	while (ipa < end) {
+		unsigned long next;
+
+		ret = rmi_rtt_init_ripas(rd_phys, ipa, end, &next);
+
+		if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
+			int err_level = RMI_RETURN_INDEX(ret);
+			int level = find_map_level(realm, ipa, end);
+
+			if (WARN_ON(err_level >= level))
+				return -ENXIO;
+
+			ret = realm_create_rtt_levels(realm, ipa,
+						      err_level,
+						      level, NULL);
+			if (ret)
+				return ret;
+			/* Retry with the RTT levels in place */
+			continue;
+		} else if (WARN_ON(ret)) {
+			return -ENXIO;
+		}
+
+		ipa = next;
+	}
+
+	return 0;
+}
+
+static int kvm_init_ipa_range_realm(struct kvm *kvm,
+				    struct arm_rme_init_ripas *args)
+{
+	gpa_t addr, end;
+	struct realm *realm = &kvm->arch.realm;
+
+	addr = args->base;
+	end = addr + args->size;
+
+	if (end < addr)
+		return -EINVAL;
+
+	if (kvm_realm_state(kvm) != REALM_STATE_NEW)
+		return -EPERM;
+
+	return realm_init_ipa_state(realm, addr, end);
+}
+
 /* Protects access to rme_vmid_bitmap */
 static DEFINE_SPINLOCK(rme_vmid_lock);
 static unsigned long *rme_vmid_bitmap;
@@ -431,6 +803,18 @@ int kvm_realm_enable_cap(struct kvm *kvm, struct kvm_enable_cap *cap)
 	case KVM_CAP_ARM_RME_CREATE_REALM:
 		r = kvm_create_realm(kvm);
 		break;
+	case KVM_CAP_ARM_RME_INIT_RIPAS_REALM: {
+		struct arm_rme_init_ripas args;
+		void __user *argp = u64_to_user_ptr(cap->args[1]);
+
+		if (copy_from_user(&args, argp, sizeof(args))) {
+			r = -EFAULT;
+			break;
+		}
+
+		r = kvm_init_ipa_range_realm(kvm, &args);
+		break;
+	}
 	default:
 		r = -EINVAL;
 		break;

---

## [17] Steven Price — 2025-04-16
*Subject: [PATCH v8 16/43] arm64: RME: Handle realm enter/exit*

Entering a realm is done using a SMC call to the RMM. On exit the
exit-codes need to be handled slightly differently to the normal KVM
path so define our own functions for realm enter/exit and hook them
in if the guest is a realm guest.

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/include/asm/kvm_rme.h |   3 +
 arch/arm64/kvm/Makefile          |   2 +-
 arch/arm64/kvm/arm.c             |  19 +++-
 arch/arm64/kvm/rme-exit.c        | 170 +++++++++++++++++++++++++++++++
 arch/arm64/kvm/rme.c             |  19 ++++
 5 files changed, 207 insertions(+), 6 deletions(-)
 create mode 100644 arch/arm64/kvm/rme-exit.c

diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index b916db8565a2..d86051ef0c5c 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -101,6 +101,9 @@ void kvm_realm_destroy_rtts(struct kvm *kvm, u32 ia_bits);
 int kvm_create_rec(struct kvm_vcpu *vcpu);
 void kvm_destroy_rec(struct kvm_vcpu *vcpu);
 
+int kvm_rec_enter(struct kvm_vcpu *vcpu);
+int handle_rec_exit(struct kvm_vcpu *vcpu, int rec_run_status);
+
 void kvm_realm_unmap_range(struct kvm *kvm,
 			   unsigned long ipa,
 			   unsigned long size,
diff --git a/arch/arm64/kvm/Makefile b/arch/arm64/kvm/Makefile
index 2ebc66812d49..c4b10012faa3 100644
--- a/arch/arm64/kvm/Makefile
+++ b/arch/arm64/kvm/Makefile
@@ -24,7 +24,7 @@ kvm-y += arm.o mmu.o mmio.o psci.o hypercalls.o pvtime.o \
 	 vgic/vgic-mmio.o vgic/vgic-mmio-v2.o \
 	 vgic/vgic-mmio-v3.o vgic/vgic-kvm-device.o \
 	 vgic/vgic-its.o vgic/vgic-debug.o vgic/vgic-v3-nested.o \
-	 rme.o
+	 rme.o rme-exit.o
 
 kvm-$(CONFIG_HW_PERF_EVENTS)  += pmu-emul.o pmu.o
 kvm-$(CONFIG_ARM64_PTR_AUTH)  += pauth.o
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 7c0bb1b05f4c..cf707130ef66 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -1263,7 +1263,10 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 		trace_kvm_entry(*vcpu_pc(vcpu));
 		guest_timing_enter_irqoff();
 
-		ret = kvm_arm_vcpu_enter_exit(vcpu);
+		if (vcpu_is_rec(vcpu))
+			ret = kvm_rec_enter(vcpu);
+		else
+			ret = kvm_arm_vcpu_enter_exit(vcpu);
 
 		vcpu->mode = OUTSIDE_GUEST_MODE;
 		vcpu->stat.exits++;
@@ -1319,10 +1322,13 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 
 		local_irq_enable();
 
-		trace_kvm_exit(ret, kvm_vcpu_trap_get_class(vcpu), *vcpu_pc(vcpu));
-
 		/* Exit types that need handling before we can be preempted */
-		handle_exit_early(vcpu, ret);
+		if (!vcpu_is_rec(vcpu)) {
+			trace_kvm_exit(ret, kvm_vcpu_trap_get_class(vcpu),
+				       *vcpu_pc(vcpu));
+
+			handle_exit_early(vcpu, ret);
+		}
 
 		preempt_enable();
 
@@ -1345,7 +1351,10 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 			ret = ARM_EXCEPTION_IL;
 		}
 
-		ret = handle_exit(vcpu, ret);
+		if (vcpu_is_rec(vcpu))
+			ret = handle_rec_exit(vcpu, ret);
+		else
+			ret = handle_exit(vcpu, ret);
 	}
 
 	/* Tell userspace about in-kernel device output levels */
diff --git a/arch/arm64/kvm/rme-exit.c b/arch/arm64/kvm/rme-exit.c
new file mode 100644
index 000000000000..a1adf5610455
--- /dev/null
+++ b/arch/arm64/kvm/rme-exit.c
@@ -0,0 +1,170 @@
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
+#include <asm/kvm_rme.h>
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
+	if (ret > 0 && !is_write)
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
+	__vcpu_sys_reg(vcpu, CNTV_CTL_EL0) = rec->run->exit.cntv_ctl;
+	__vcpu_sys_reg(vcpu, CNTV_CVAL_EL0) = rec->run->exit.cntv_cval;
+	__vcpu_sys_reg(vcpu, CNTP_CTL_EL0) = rec->run->exit.cntp_ctl;
+	__vcpu_sys_reg(vcpu, CNTP_CVAL_EL0) = rec->run->exit.cntp_cval;
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
+		vcpu->run->exit_reason = KVM_EXIT_UNKNOWN;
+		return 0;
+	}
+
+	if (rec_run_ret)
+		return -ENXIO;
+
+	vcpu->arch.fault.esr_el2 = rec->run->exit.esr;
+	vcpu->arch.fault.far_el2 = rec->run->exit.far;
+	vcpu->arch.fault.hpfar_el2 = rec->run->exit.hpfar;
+
+	update_arch_timer_irq_lines(vcpu);
+
+	/* Reset the emulation flags for the next run of the REC */
+	rec->run->enter.flags = 0;
+
+	switch (rec->run->exit.exit_reason) {
+	case RMI_EXIT_SYNC:
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
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 33eb793d8bdb..bee9dfe12e03 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -863,6 +863,25 @@ void kvm_destroy_realm(struct kvm *kvm)
 	kvm_free_stage2_pgd(&kvm->arch.mmu);
 }
 
+int kvm_rec_enter(struct kvm_vcpu *vcpu)
+{
+	struct realm_rec *rec = &vcpu->arch.rec;
+
+	switch (rec->run->exit.exit_reason) {
+	case RMI_EXIT_HOST_CALL:
+	case RMI_EXIT_PSCI:
+		for (int i = 0; i < REC_RUN_GPRS; i++)
+			rec->run->enter.gprs[i] = vcpu_get_reg(vcpu, i);
+		break;
+	}
+
+	if (kvm_realm_state(vcpu->kvm) != REALM_STATE_ACTIVE)
+		return -EINVAL;
+
+	return rmi_rec_enter(virt_to_phys(rec->rec_page),
+			     virt_to_phys(rec->run));
+}
+
 static void free_rec_aux(struct page **aux_pages,
 			 unsigned int num_aux)
 {

---

## [18] Steven Price — 2025-04-16
*Subject: [PATCH v8 17/43] arm64: RME: Handle RMI_EXIT_RIPAS_CHANGE*

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

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v7:
 * Rework the loop in realm_set_ipa_state() to make it clear when the
   'next' output value of rmi_rtt_set_ripas() is used.
New patch for v7: The code was previously split awkwardly between two
other patches.
---
 arch/arm64/kvm/rme.c | 88 ++++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 88 insertions(+)

diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index bee9dfe12e03..fe0d5b8703d2 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -624,6 +624,65 @@ void kvm_realm_unmap_range(struct kvm *kvm, unsigned long start,
 		realm_unmap_private_range(kvm, start, end);
 }
 
+static int realm_set_ipa_state(struct kvm_vcpu *vcpu,
+			       unsigned long start,
+			       unsigned long end,
+			       unsigned long ripas,
+			       unsigned long *top_ipa)
+{
+	struct kvm *kvm = vcpu->kvm;
+	struct realm *realm = &kvm->arch.realm;
+	struct realm_rec *rec = &vcpu->arch.rec;
+	phys_addr_t rd_phys = virt_to_phys(realm->rd);
+	phys_addr_t rec_phys = virt_to_phys(rec->rec_page);
+	struct kvm_mmu_memory_cache *memcache = &vcpu->arch.mmu_page_cache;
+	unsigned long ipa = start;
+	int ret = 0;
+
+	while (ipa < end) {
+		unsigned long next;
+
+		ret = rmi_rtt_set_ripas(rd_phys, rec_phys, ipa, end, &next);
+
+		if (RMI_RETURN_STATUS(ret) == RMI_SUCCESS) {
+			ipa = next;
+		} else if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
+			int walk_level = RMI_RETURN_INDEX(ret);
+			int level = find_map_level(realm, ipa, end);
+
+			/*
+			 * If the RMM walk ended early then more tables are
+			 * needed to reach the required depth to set the RIPAS.
+			 */
+			if (walk_level < level) {
+				ret = realm_create_rtt_levels(realm, ipa,
+							      walk_level,
+							      level,
+							      memcache);
+				/* Retry with RTTs created */
+				if (!ret)
+					continue;
+			} else {
+				ret = -EINVAL;
+			}
+
+			break;
+		} else {
+			WARN(1, "Unexpected error in %s: %#x\n", __func__,
+			     ret);
+			ret = -ENXIO;
+			break;
+		}
+	}
+
+	*top_ipa = ipa;
+
+	if (ripas == RMI_EMPTY && ipa != start)
+		realm_unmap_private_range(kvm, start, ipa);
+
+	return ret;
+}
+
 static int realm_init_ipa_state(struct realm *realm,
 				unsigned long ipa,
 				unsigned long end)
@@ -863,6 +922,32 @@ void kvm_destroy_realm(struct kvm *kvm)
 	kvm_free_stage2_pgd(&kvm->arch.mmu);
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
+	} while (top_ipa < top);
+}
+
 int kvm_rec_enter(struct kvm_vcpu *vcpu)
 {
 	struct realm_rec *rec = &vcpu->arch.rec;
@@ -873,6 +958,9 @@ int kvm_rec_enter(struct kvm_vcpu *vcpu)
 		for (int i = 0; i < REC_RUN_GPRS; i++)
 			rec->run->enter.gprs[i] = vcpu_get_reg(vcpu, i);
 		break;
+	case RMI_EXIT_RIPAS_CHANGE:
+		kvm_complete_ripas_change(vcpu);
+		break;
 	}
 
 	if (kvm_realm_state(vcpu->kvm) != REALM_STATE_ACTIVE)

---

## [19] Steven Price — 2025-04-16
*Subject: [PATCH v8 18/43] KVM: arm64: Handle realm MMIO emulation*

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
 arch/arm64/kvm/rme-exit.c     | 14 ++++++++++++++
 3 files changed, 29 insertions(+), 5 deletions(-)

diff --git a/arch/arm64/kvm/inject_fault.c b/arch/arm64/kvm/inject_fault.c
index a640e839848e..2a9682b9834f 100644
--- a/arch/arm64/kvm/inject_fault.c
+++ b/arch/arm64/kvm/inject_fault.c
@@ -165,7 +165,9 @@ static void inject_abt32(struct kvm_vcpu *vcpu, bool is_pabt, u32 addr)
  */
 void kvm_inject_dabt(struct kvm_vcpu *vcpu, unsigned long addr)
 {
-	if (vcpu_el1_is_32bit(vcpu))
+	if (unlikely(vcpu_is_rec(vcpu)))
+		vcpu->arch.rec.run->enter.flags |= REC_ENTER_FLAG_INJECT_SEA;
+	else if (vcpu_el1_is_32bit(vcpu))
 		inject_abt32(vcpu, false, addr);
 	else
 		inject_abt64(vcpu, false, addr);
diff --git a/arch/arm64/kvm/mmio.c b/arch/arm64/kvm/mmio.c
index ab365e839874..bff89d47a4d5 100644
--- a/arch/arm64/kvm/mmio.c
+++ b/arch/arm64/kvm/mmio.c
@@ -6,6 +6,7 @@
 
 #include <linux/kvm_host.h>
 #include <asm/kvm_emulate.h>
+#include <asm/rmi_smc.h>
 #include <trace/events/kvm.h>
 
 #include "trace.h"
@@ -136,14 +137,21 @@ int kvm_handle_mmio_return(struct kvm_vcpu *vcpu)
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
@@ -162,14 +170,14 @@ int io_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa)
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
 
-		if (vcpu_is_protected(vcpu)) {
+		if (vcpu_is_protected(vcpu) || vcpu_is_rec(vcpu)) {
 			kvm_inject_dabt(vcpu, kvm_vcpu_get_hfar(vcpu));
 			return 1;
 		}
diff --git a/arch/arm64/kvm/rme-exit.c b/arch/arm64/kvm/rme-exit.c
index a1adf5610455..6830dc080610 100644
--- a/arch/arm64/kvm/rme-exit.c
+++ b/arch/arm64/kvm/rme-exit.c
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

## [20] Steven Price — 2025-04-16
*Subject: [PATCH v8 19/43] arm64: RME: Allow populating initial contents*

The VMM needs to populate the realm with some data before starting (e.g.
a kernel and initrd). This is measured by the RMM and used as part of
the attestation later on.

Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
---
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
 arch/arm64/kvm/rme.c | 227 +++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 227 insertions(+)

diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index fe0d5b8703d2..f6af3ea6ea8a 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -624,6 +624,221 @@ void kvm_realm_unmap_range(struct kvm *kvm, unsigned long start,
 		realm_unmap_private_range(kvm, start, end);
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
+static int populate_region(struct kvm *kvm,
+			   phys_addr_t ipa_base,
+			   phys_addr_t ipa_end,
+			   unsigned long data_flags)
+{
+	struct realm *realm = &kvm->arch.realm;
+	struct kvm_memory_slot *memslot;
+	gfn_t base_gfn, end_gfn;
+	int idx;
+	phys_addr_t ipa = ipa_base;
+	int ret = 0;
+
+	base_gfn = gpa_to_gfn(ipa_base);
+	end_gfn = gpa_to_gfn(ipa_end);
+
+	idx = srcu_read_lock(&kvm->srcu);
+	memslot = gfn_to_memslot(kvm, base_gfn);
+	if (!memslot) {
+		ret = -EFAULT;
+		goto out;
+	}
+
+	/* We require the region to be contained within a single memslot */
+	if (memslot->base_gfn + memslot->npages < end_gfn) {
+		ret = -EINVAL;
+		goto out;
+	}
+
+	if (!kvm_slot_can_be_private(memslot)) {
+		ret = -EPERM;
+		goto out;
+	}
+
+	while (ipa < ipa_end) {
+		struct vm_area_struct *vma;
+		unsigned long hva;
+		struct page *page;
+		bool writeable;
+		kvm_pfn_t pfn;
+		kvm_pfn_t priv_pfn;
+		struct page *gmem_page;
+
+		hva = gfn_to_hva_memslot(memslot, gpa_to_gfn(ipa));
+		vma = vma_lookup(current->mm, hva);
+		if (!vma) {
+			ret = -EFAULT;
+			break;
+		}
+
+		pfn = __kvm_faultin_pfn(memslot, gpa_to_gfn(ipa), FOLL_WRITE,
+					&writeable, &page);
+
+		if (is_error_pfn(pfn)) {
+			ret = -EFAULT;
+			break;
+		}
+
+		ret = kvm_gmem_get_pfn(kvm, memslot,
+				       ipa >> PAGE_SHIFT,
+				       &priv_pfn, &gmem_page, NULL);
+		if (ret)
+			break;
+
+		ret = realm_create_protected_data_page(realm, ipa,
+						       priv_pfn,
+						       pfn,
+						       data_flags);
+
+		kvm_release_page_clean(page);
+
+		if (ret)
+			break;
+
+		ipa += PAGE_SIZE;
+	}
+
+out:
+	srcu_read_unlock(&kvm->srcu, idx);
+	return ret;
+}
+
+static int kvm_populate_realm(struct kvm *kvm,
+			      struct arm_rme_populate_realm *args)
+{
+	phys_addr_t ipa_base, ipa_end;
+	unsigned long data_flags = 0;
+
+	if (kvm_realm_state(kvm) != REALM_STATE_NEW)
+		return -EPERM;
+
+	if (!IS_ALIGNED(args->base, PAGE_SIZE) ||
+	    !IS_ALIGNED(args->size, PAGE_SIZE) ||
+	    (args->flags & ~RMI_MEASURE_CONTENT))
+		return -EINVAL;
+
+	ipa_base = args->base;
+	ipa_end = ipa_base + args->size;
+
+	if (ipa_end < ipa_base)
+		return -EINVAL;
+
+	if (args->flags & RMI_MEASURE_CONTENT)
+		data_flags |= RMI_MEASURE_CONTENT;
+
+	/*
+	 * Perform the population in parts to ensure locks are not held for too
+	 * long
+	 */
+	while (ipa_base < ipa_end) {
+		phys_addr_t end = min(ipa_end, ipa_base + SZ_2M);
+
+		int ret = populate_region(kvm, ipa_base, end,
+					  args->flags);
+
+		if (ret)
+			return ret;
+
+		ipa_base = end;
+
+		cond_resched();
+	}
+
+	return 0;
+}
+
 static int realm_set_ipa_state(struct kvm_vcpu *vcpu,
 			       unsigned long start,
 			       unsigned long end,
@@ -874,6 +1089,18 @@ int kvm_realm_enable_cap(struct kvm *kvm, struct kvm_enable_cap *cap)
 		r = kvm_init_ipa_range_realm(kvm, &args);
 		break;
 	}
+	case KVM_CAP_ARM_RME_POPULATE_REALM: {
+		struct arm_rme_populate_realm args;
+		void __user *argp = u64_to_user_ptr(cap->args[1]);
+
+		if (copy_from_user(&args, argp, sizeof(args))) {
+			r = -EFAULT;
+			break;
+		}
+
+		r = kvm_populate_realm(kvm, &args);
+		break;
+	}
 	default:
 		r = -EINVAL;
 		break;

---

## [21] Steven Price — 2025-04-16
*Subject: [PATCH v8 20/43] arm64: RME: Runtime faulting of memory*

At runtime if the realm guest accesses memory which hasn't yet been
mapped then KVM needs to either populate the region or fault the guest.

For memory in the lower (protected) region of IPA a fresh page is
provided to the RMM which will zero the contents. For memory in the
upper (shared) region of IPA, the memory from the memslot is mapped
into the realm VM non secure.

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/include/asm/kvm_emulate.h |  10 ++
 arch/arm64/include/asm/kvm_rme.h     |  10 ++
 arch/arm64/kvm/mmu.c                 | 127 ++++++++++++++++++-
 arch/arm64/kvm/rme.c                 | 180 +++++++++++++++++++++++++++
 4 files changed, 321 insertions(+), 6 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_emulate.h b/arch/arm64/include/asm/kvm_emulate.h
index c803c8188d9c..def439d6d732 100644
--- a/arch/arm64/include/asm/kvm_emulate.h
+++ b/arch/arm64/include/asm/kvm_emulate.h
@@ -704,6 +704,16 @@ static inline bool kvm_realm_is_created(struct kvm *kvm)
 	return kvm_is_realm(kvm) && kvm_realm_state(kvm) != REALM_STATE_NONE;
 }
 
+static inline gpa_t kvm_gpa_from_fault(struct kvm *kvm, phys_addr_t ipa)
+{
+	if (kvm_is_realm(kvm)) {
+		struct realm *realm = &kvm->arch.realm;
+
+		return ipa & ~BIT(realm->ia_bits - 1);
+	}
+	return ipa;
+}
+
 static inline bool vcpu_is_rec(struct kvm_vcpu *vcpu)
 {
 	if (static_branch_unlikely(&kvm_rme_is_available))
diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index d86051ef0c5c..47aa6362c6c9 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -108,6 +108,16 @@ void kvm_realm_unmap_range(struct kvm *kvm,
 			   unsigned long ipa,
 			   unsigned long size,
 			   bool unmap_private);
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
index 71c04259e39f..02b66ee35426 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -338,8 +338,13 @@ static void __unmap_stage2_range(struct kvm_s2_mmu *mmu, phys_addr_t start, u64
 
 	lockdep_assert_held_write(&kvm->mmu_lock);
 	WARN_ON(size & ~PAGE_MASK);
-	WARN_ON(stage2_apply_range(mmu, start, end, KVM_PGT_FN(kvm_pgtable_stage2_unmap),
-				   may_block));
+
+	if (kvm_is_realm(kvm))
+		kvm_realm_unmap_range(kvm, start, size, !only_shared);
+	else
+		WARN_ON(stage2_apply_range(mmu, start, end,
+					   KVM_PGT_FN(kvm_pgtable_stage2_unmap),
+					   may_block));
 }
 
 void kvm_stage2_unmap_range(struct kvm_s2_mmu *mmu, phys_addr_t start,
@@ -359,7 +364,10 @@ static void stage2_flush_memslot(struct kvm *kvm,
 	phys_addr_t addr = memslot->base_gfn << PAGE_SHIFT;
 	phys_addr_t end = addr + PAGE_SIZE * memslot->npages;
 
-	kvm_stage2_flush_range(&kvm->arch.mmu, addr, end);
+	if (kvm_is_realm(kvm))
+		kvm_realm_unmap_range(kvm, addr, end - addr, false);
+	else
+		kvm_stage2_flush_range(&kvm->arch.mmu, addr, end);
 }
 
 /**
@@ -1053,6 +1061,10 @@ void stage2_unmap_vm(struct kvm *kvm)
 	struct kvm_memory_slot *memslot;
 	int idx, bkt;
 
+	/* For realms this is handled by the RMM so nothing to do here */
+	if (kvm_is_realm(kvm))
+		return;
+
 	idx = srcu_read_lock(&kvm->srcu);
 	mmap_read_lock(current->mm);
 	write_lock(&kvm->mmu_lock);
@@ -1078,6 +1090,7 @@ void kvm_free_stage2_pgd(struct kvm_s2_mmu *mmu)
 	if (kvm_is_realm(kvm) &&
 	    (kvm_realm_state(kvm) != REALM_STATE_DEAD &&
 	     kvm_realm_state(kvm) != REALM_STATE_NONE)) {
+		kvm_stage2_unmap_range(mmu, 0, (~0ULL) & PAGE_MASK, false);
 		write_unlock(&kvm->mmu_lock);
 		kvm_realm_destroy_rtts(kvm, pgt->ia_bits);
 
@@ -1482,6 +1495,82 @@ static bool kvm_vma_mte_allowed(struct vm_area_struct *vma)
 	return vma->vm_flags & VM_MTE_ALLOWED;
 }
 
+static int realm_map_ipa(struct kvm *kvm, phys_addr_t ipa,
+			 kvm_pfn_t pfn, unsigned long map_size,
+			 enum kvm_pgtable_prot prot,
+			 struct kvm_mmu_memory_cache *memcache)
+{
+	struct realm *realm = &kvm->arch.realm;
+
+	if (WARN_ON(!(prot & KVM_PGTABLE_PROT_W)))
+		return -EFAULT;
+
+	ipa = ALIGN_DOWN(ipa, PAGE_SIZE);
+
+	if (!kvm_realm_is_private_address(realm, ipa))
+		return realm_map_non_secure(realm, ipa, pfn, map_size,
+					    memcache);
+
+	return realm_map_protected(realm, ipa, pfn, map_size, memcache);
+}
+
+static int private_memslot_fault(struct kvm_vcpu *vcpu,
+				 phys_addr_t fault_ipa,
+				 struct kvm_memory_slot *memslot)
+{
+	struct kvm *kvm = vcpu->kvm;
+	gpa_t gpa = kvm_gpa_from_fault(kvm, fault_ipa);
+	gfn_t gfn = gpa >> PAGE_SHIFT;
+	bool is_priv_gfn = kvm_mem_is_private(kvm, gfn);
+	struct kvm_mmu_memory_cache *memcache = &vcpu->arch.mmu_page_cache;
+	struct page *page;
+	kvm_pfn_t pfn;
+	int ret;
+	/*
+	 * For Realms, the shared address is an alias of the private GPA with
+	 * the top bit set. Thus is the fault address matches the GPA then it
+	 * is the private alias.
+	 */
+	bool is_priv_fault = (gpa == fault_ipa);
+
+	if (is_priv_gfn != is_priv_fault) {
+		kvm_prepare_memory_fault_exit(vcpu,
+					      gpa,
+					      PAGE_SIZE,
+					      kvm_is_write_fault(vcpu),
+					      false, is_priv_fault);
+
+		/*
+		 * KVM_EXIT_MEMORY_FAULT requires an return code of -EFAULT,
+		 * see the API documentation
+		 */
+		return -EFAULT;
+	}
+
+	if (!is_priv_fault) {
+		/* Not a private mapping, handling normally */
+		return -EINVAL;
+	}
+
+	ret = kvm_mmu_topup_memory_cache(memcache,
+					 kvm_mmu_cache_min_pages(vcpu->arch.hw_mmu));
+	if (ret)
+		return ret;
+
+	ret = kvm_gmem_get_pfn(kvm, memslot, gfn, &pfn, &page, NULL);
+	if (ret)
+		return ret;
+
+	/* FIXME: Should be able to use bigger than PAGE_SIZE mappings */
+	ret = realm_map_ipa(kvm, fault_ipa, pfn, PAGE_SIZE, KVM_PGTABLE_PROT_W,
+			    memcache);
+	if (!ret)
+		return 1; /* Handled */
+
+	put_page(page);
+	return ret;
+}
+
 static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 			  struct kvm_s2_trans *nested,
 			  struct kvm_memory_slot *memslot, unsigned long hva,
@@ -1509,6 +1598,14 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
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
 	VM_BUG_ON(write_fault && exec_fault);
 
@@ -1623,7 +1720,7 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 		ipa &= ~(vma_pagesize - 1);
 	}
 
-	gfn = ipa >> PAGE_SHIFT;
+	gfn = kvm_gpa_from_fault(kvm, ipa) >> PAGE_SHIFT;
 	mte_allowed = kvm_vma_mte_allowed(vma);
 
 	vfio_allow_any_uc = vma->vm_flags & VM_ALLOW_ANY_UNCACHED;
@@ -1756,6 +1853,9 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 		 */
 		prot &= ~KVM_NV_GUEST_MAP_SZ;
 		ret = KVM_PGT_FN(kvm_pgtable_stage2_relax_perms)(pgt, fault_ipa, prot, flags);
+	} else if (kvm_is_realm(kvm)) {
+		ret = realm_map_ipa(kvm, fault_ipa, pfn, vma_pagesize,
+				    prot, memcache);
 	} else {
 		ret = KVM_PGT_FN(kvm_pgtable_stage2_map)(pgt, fault_ipa, vma_pagesize,
 					     __pfn_to_phys(pfn), prot,
@@ -1897,8 +1997,15 @@ int kvm_handle_guest_abort(struct kvm_vcpu *vcpu)
 		nested = &nested_trans;
 	}
 
-	gfn = ipa >> PAGE_SHIFT;
+	gfn = kvm_gpa_from_fault(vcpu->kvm, ipa) >> PAGE_SHIFT;
 	memslot = gfn_to_memslot(vcpu->kvm, gfn);
+
+	if (kvm_slot_can_be_private(memslot)) {
+		ret = private_memslot_fault(vcpu, ipa, memslot);
+		if (ret != -EINVAL)
+			goto out;
+	}
+
 	hva = gfn_to_hva_memslot_prot(memslot, gfn, &writable);
 	write_fault = kvm_is_write_fault(vcpu);
 	if (kvm_is_error_hva(hva) || (write_fault && !writable)) {
@@ -1942,7 +2049,7 @@ int kvm_handle_guest_abort(struct kvm_vcpu *vcpu)
 		 * of the page size.
 		 */
 		ipa |= kvm_vcpu_get_hfar(vcpu) & GENMASK(11, 0);
-		ret = io_mem_abort(vcpu, ipa);
+		ret = io_mem_abort(vcpu, kvm_gpa_from_fault(vcpu->kvm, ipa));
 		goto out_unlock;
 	}
 
@@ -1990,6 +2097,10 @@ bool kvm_age_gfn(struct kvm *kvm, struct kvm_gfn_range *range)
 	if (!kvm->arch.mmu.pgt)
 		return false;
 
+	/* We don't support aging for Realms */
+	if (kvm_is_realm(kvm))
+		return true;
+
 	return KVM_PGT_FN(kvm_pgtable_stage2_test_clear_young)(kvm->arch.mmu.pgt,
 						   range->start << PAGE_SHIFT,
 						   size, true);
@@ -2006,6 +2117,10 @@ bool kvm_test_age_gfn(struct kvm *kvm, struct kvm_gfn_range *range)
 	if (!kvm->arch.mmu.pgt)
 		return false;
 
+	/* We don't support aging for Realms */
+	if (kvm_is_realm(kvm))
+		return true;
+
 	return KVM_PGT_FN(kvm_pgtable_stage2_test_clear_young)(kvm->arch.mmu.pgt,
 						   range->start << PAGE_SHIFT,
 						   size, false);
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index f6af3ea6ea8a..b6959cd17a6c 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -714,6 +714,186 @@ static int realm_create_protected_data_page(struct realm *realm,
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
+	free_delegated_granule(rtt_addr);
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
+	int map_level;
+	int ret = 0;
+
+	if (WARN_ON(!IS_ALIGNED(map_size, RMM_PAGE_SIZE)))
+		return -EINVAL;
+
+	if (WARN_ON(!IS_ALIGNED(ipa, map_size)))
+		return -EINVAL;
+
+	if (IS_ALIGNED(map_size, RMM_L2_BLOCK_SIZE))
+		map_level = 2;
+	else
+		map_level = 3;
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
+
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
+	int map_size, map_level;
+	int ret = 0;
+
+	if (WARN_ON(!IS_ALIGNED(size, RMM_PAGE_SIZE)))
+		return -EINVAL;
+
+	if (WARN_ON(!IS_ALIGNED(ipa, size)))
+		return -EINVAL;
+
+	if (IS_ALIGNED(size, RMM_L2_BLOCK_SIZE)) {
+		map_level = 2;
+		map_size = RMM_L2_BLOCK_SIZE;
+	} else {
+		map_level = 3;
+		map_size = RMM_PAGE_SIZE;
+	}
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
+		 * present for the address.  The call to
+		 * realm_create_rtt_levels() above handles the first case, and
+		 * in the second case this indicates that another thread has
+		 * already populated the RTTE for us, so we can ignore the
+		 * error and continue.
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
 static int populate_region(struct kvm *kvm,
 			   phys_addr_t ipa_base,
 			   phys_addr_t ipa_end,

---

## [22] Steven Price — 2025-04-16
*Subject: [PATCH v8 21/43] KVM: arm64: Handle realm VCPU load*

When loading a realm VCPU much of the work is handled by the RMM so only
some of the actions are required. Rearrange kvm_arch_vcpu_load()
slightly so we can bail out early for a realm guest.

Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
---
 arch/arm64/kvm/arm.c | 13 +++++++++----
 1 file changed, 9 insertions(+), 4 deletions(-)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index cf707130ef66..08d5e0d76749 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -644,10 +644,6 @@ void kvm_arch_vcpu_load(struct kvm_vcpu *vcpu, int cpu)
 	kvm_timer_vcpu_load(vcpu);
 	kvm_vgic_load(vcpu);
 	kvm_vcpu_load_debug(vcpu);
-	if (has_vhe())
-		kvm_vcpu_load_vhe(vcpu);
-	kvm_arch_vcpu_load_fp(vcpu);
-	kvm_vcpu_pmu_restore_guest(vcpu);
 	if (kvm_arm_is_pvtime_enabled(&vcpu->arch))
 		kvm_make_request(KVM_REQ_RECORD_STEAL, vcpu);
 
@@ -671,6 +667,15 @@ void kvm_arch_vcpu_load(struct kvm_vcpu *vcpu, int cpu)
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
+
 	if (!cpumask_test_cpu(cpu, vcpu->kvm->arch.supported_cpus))
 		vcpu_set_on_unsupported_cpu(vcpu);
 }

---

## [23] Steven Price — 2025-04-16
*Subject: [PATCH v8 22/43] KVM: arm64: Validate register access for a Realm VM*

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

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v5:
 * Upper GPRS can be set as part of a HOST_CALL return, so fix up the
   test to allow them.
---
 arch/arm64/kvm/guest.c | 40 ++++++++++++++++++++++++++++++++++++++++
 1 file changed, 40 insertions(+)

diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index 2196979a24a3..ff0306650b39 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -73,6 +73,24 @@ static u64 core_reg_offset_from_id(u64 id)
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
@@ -783,12 +801,34 @@ int kvm_arm_get_reg(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg)
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

## [24] Steven Price — 2025-04-16
*Subject: [PATCH v8 23/43] KVM: arm64: Handle Realm PSCI requests*

The RMM needs to be informed of the target REC when a PSCI call is made
with an MPIDR argument. Expose an ioctl to the userspace in case the PSCI
is handled by it.

Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
---
Changes since v6:
 * Use vcpu_is_rec() rather than kvm_is_realm(vcpu->kvm).
 * Minor renaming/formatting fixes.
---
 arch/arm64/include/asm/kvm_rme.h |  3 +++
 arch/arm64/kvm/arm.c             | 25 +++++++++++++++++++++++++
 arch/arm64/kvm/psci.c            | 30 ++++++++++++++++++++++++++++++
 arch/arm64/kvm/rme.c             | 14 ++++++++++++++
 4 files changed, 72 insertions(+)

diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index 47aa6362c6c9..7000fa1227d0 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
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
index 08d5e0d76749..cacdc10d2a6b 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -1745,6 +1745,22 @@ static int kvm_arm_vcpu_set_events(struct kvm_vcpu *vcpu,
 	return __kvm_arm_vcpu_set_events(vcpu, events);
 }
 
+static int kvm_arm_vcpu_rmm_psci_complete(struct kvm_vcpu *vcpu,
+					  struct kvm_arm_rmm_psci_complete *arg)
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
@@ -1867,6 +1883,15 @@ long kvm_arch_vcpu_ioctl(struct file *filp,
 
 		return kvm_arm_vcpu_finalize(vcpu, what);
 	}
+	case KVM_ARM_VCPU_RMM_PSCI_COMPLETE: {
+		struct kvm_arm_rmm_psci_complete req;
+
+		if (!vcpu_is_rec(vcpu))
+			return -EPERM;
+		if (copy_from_user(&req, argp, sizeof(req)))
+			return -EFAULT;
+		return kvm_arm_vcpu_rmm_psci_complete(vcpu, &req);
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
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index b6959cd17a6c..70244e01c161 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -144,6 +144,20 @@ static void free_delegated_granule(phys_addr_t phys)
 	free_page((unsigned long)phys_to_virt(phys));
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

## [25] Steven Price — 2025-04-16
*Subject: [PATCH v8 24/43] KVM: arm64: WARN on injected undef exceptions*

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
index 2a9682b9834f..7dba6fc8c41d 100644
--- a/arch/arm64/kvm/inject_fault.c
+++ b/arch/arm64/kvm/inject_fault.c
@@ -226,6 +226,7 @@ void kvm_inject_size_fault(struct kvm_vcpu *vcpu)
  */
 void kvm_inject_undefined(struct kvm_vcpu *vcpu)
 {
+	WARN(vcpu_is_rec(vcpu), "Unexpected undefined exception injection to REC");
 	if (vcpu_el1_is_32bit(vcpu))
 		inject_undef32(vcpu);
 	else

---

## [26] Steven Price — 2025-04-16
*Subject: [PATCH v8 25/43] arm64: Don't expose stolen time for realm guests*

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
index 54ae0b98030e..f91b35128748 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -8684,6 +8684,9 @@ is supported, than the other should as well and vice versa.  For arm64
 see Documentation/virt/kvm/devices/vcpu.rst "KVM_ARM_VCPU_PVTIME_CTRL".
 For x86 see Documentation/virt/kvm/x86/msr.rst "MSR_KVM_STEAL_TIME".
 
+Note that steal time accounting is not available when a guest is running
+within a Arm CCA realm (machine type KVM_VM_TYPE_ARM_REALM).
+
 8.25 KVM_CAP_S390_DIAG318
 -------------------------
 
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index cacdc10d2a6b..97c5efbe47a6 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -396,7 +396,10 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
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

## [27] Steven Price — 2025-04-16
*Subject: [PATCH v8 26/43] arm64: RME: allow userspace to inject aborts*

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
index f91b35128748..4d0721827314 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -1307,6 +1307,8 @@ User space may need to inject several types of events to the guest.
 Set the pending SError exception state for this VCPU. It is not possible to
 'cancel' an Serror that has been made pending.
 
+User space cannot inject SErrors into Realms.
+
 If the guest performed an access to I/O memory which could not be handled by
 userspace, for example because of missing instruction syndrome decode
 information or because there is no device mapped at the accessed IPA, then
diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index ff0306650b39..d56ac89ca37a 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -880,6 +880,30 @@ int __kvm_arm_vcpu_set_events(struct kvm_vcpu *vcpu,
 	bool has_esr = events->exception.serror_has_esr;
 	bool ext_dabt_pending = events->exception.ext_dabt_pending;
 
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
 	if (serror_pending && has_esr) {
 		if (!cpus_have_final_cap(ARM64_HAS_RAS_EXTN))
 			return -EINVAL;

---

## [28] Steven Price — 2025-04-16
*Subject: [PATCH v8 27/43] arm64: RME: support RSI_HOST_CALL*

From: Joey Gouly <joey.gouly@arm.com>

Forward RSI_HOST_CALLS to KVM's HVC handler.

Signed-off-by: Joey Gouly <joey.gouly@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
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
 arch/arm64/kvm/rme-exit.c | 15 +++++++++++++++
 1 file changed, 15 insertions(+)

diff --git a/arch/arm64/kvm/rme-exit.c b/arch/arm64/kvm/rme-exit.c
index 6830dc080610..f1443b58c1c4 100644
--- a/arch/arm64/kvm/rme-exit.c
+++ b/arch/arm64/kvm/rme-exit.c
@@ -114,6 +114,19 @@ static int rec_exit_ripas_change(struct kvm_vcpu *vcpu)
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
@@ -175,6 +188,8 @@ int handle_rec_exit(struct kvm_vcpu *vcpu, int rec_run_ret)
 		return rec_exit_psci(vcpu);
 	case RMI_EXIT_RIPAS_CHANGE:
 		return rec_exit_ripas_change(vcpu);
+	case RMI_EXIT_HOST_CALL:
+		return rec_exit_host_call(vcpu);
 	}
 
 	kvm_pr_unimpl("Unsupported exit reason: %u\n",

---

## [29] Steven Price — 2025-04-16
*Subject: [PATCH v8 28/43] arm64: RME: Allow checking SVE on VM instance*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

Given we have different types of VMs supported, check the
support for SVE for the given instance of the VM to accurately
report the status.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
---
 arch/arm64/include/asm/kvm_rme.h | 2 ++
 arch/arm64/kvm/arm.c             | 5 ++++-
 arch/arm64/kvm/rme.c             | 5 +++++
 3 files changed, 11 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index 7000fa1227d0..f786fd978cf6 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -94,6 +94,8 @@ void kvm_init_rme(void);
 u32 kvm_realm_ipa_limit(void);
 u32 kvm_realm_vgic_nr_lr(void);
 
+bool kvm_rme_supports_sve(void);
+
 int kvm_realm_enable_cap(struct kvm *kvm, struct kvm_enable_cap *cap);
 int kvm_init_realm_vm(struct kvm *kvm);
 void kvm_destroy_realm(struct kvm *kvm);
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 97c5efbe47a6..850708db660e 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -420,7 +420,10 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 		r = get_kvm_ipa_limit();
 		break;
 	case KVM_CAP_ARM_SVE:
-		r = system_supports_sve();
+		if (kvm_is_realm(kvm))
+			r = kvm_rme_supports_sve();
+		else
+			r = system_supports_sve();
 		break;
 	case KVM_CAP_ARM_PTRAUTH_ADDRESS:
 	case KVM_CAP_ARM_PTRAUTH_GENERIC:
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 70244e01c161..a89bd1c29e99 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -38,6 +38,11 @@ static bool rme_has_feature(unsigned long feature)
 	return !!u64_get_bits(rmm_feat_reg0, feature);
 }
 
+bool kvm_rme_supports_sve(void)
+{
+	return rme_has_feature(RMI_FEATURE_REGISTER_0_SVE_EN);
+}
+
 static int rmi_check_version(void)
 {
 	struct arm_smccc_res res;

---

## [30] Steven Price — 2025-04-16
*Subject: [PATCH v8 29/43] arm64: RME: Always use 4k pages for realms*

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
---
Changes since v7:
 * Rewritten commit message
---
 arch/arm64/kvm/mmu.c | 4 ++++
 1 file changed, 4 insertions(+)

diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index 02b66ee35426..29bab7a46033 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -1653,6 +1653,10 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 	if (logging_active || is_protected_kvm_enabled()) {
 		force_pte = true;
 		vma_shift = PAGE_SHIFT;
+	} else if (vcpu_is_rec(vcpu)) {
+		// Force PTE level mappings for realms
+		force_pte = true;
+		vma_shift = PAGE_SHIFT;
 	} else {
 		vma_shift = get_vma_page_shift(vma, hva);
 	}

---

## [31] Steven Price — 2025-04-16
*Subject: [PATCH v8 30/43] arm64: RME: Prevent Device mappings for Realms*

Physical device assignment is not yet supported by the RMM, so it
doesn't make much sense to allow device mappings within the realm.
Prevent them when the guest is a realm.

Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
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
index 29bab7a46033..b861747ea1b3 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -1185,6 +1185,10 @@ int kvm_phys_addr_ioremap(struct kvm *kvm, phys_addr_t guest_ipa,
 	if (is_protected_kvm_enabled())
 		return -EPERM;
 
+	/* We don't support mapping special pages into a Realm */
+	if (kvm_is_realm(kvm))
+		return -EPERM;
+
 	size += offset_in_page(guest_ipa);
 	guest_ipa &= PAGE_MASK;
 
@@ -1775,6 +1779,15 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 	if (exec_fault && device)
 		return -ENOEXEC;
 
+	/*
+	 * For now we shouldn't be hitting protected addresses because they are
+	 * handled in private_memslot_fault(). In the future this check may be
+	 * relaxed to support e.g. protected devices.
+	 */
+	if (vcpu_is_rec(vcpu) &&
+	    kvm_gpa_from_fault(kvm, fault_ipa) == fault_ipa)
+		return -EINVAL;
+
 	/*
 	 * Potentially reduce shadow S2 permissions to match the guest's own
 	 * S2. For exec faults, we'd only reach this point if the guest

---

## [32] Steven Price — 2025-04-16
*Subject: [PATCH v8 31/43] arm_pmu: Provide a mechanism for disabling the physical IRQ*

Arm CCA assigns the physical PMU device to the guest running in realm
world, however the IRQs are routed via the host. To enter a realm guest
while a PMU IRQ is pending it is necessary to block the physical IRQ to
prevent an immediate exit. Provide a mechanism in the PMU driver for KVM
to control the physical IRQ.

Signed-off-by: Steven Price <steven.price@arm.com>
---
v3: Add a dummy function for the !CONFIG_ARM_PMU case.
---
 drivers/perf/arm_pmu.c       | 15 +++++++++++++++
 include/linux/perf/arm_pmu.h |  5 +++++
 2 files changed, 20 insertions(+)

diff --git a/drivers/perf/arm_pmu.c b/drivers/perf/arm_pmu.c
index 2f33e69a8caf..ae1234001f79 100644
--- a/drivers/perf/arm_pmu.c
+++ b/drivers/perf/arm_pmu.c
@@ -733,6 +733,21 @@ static int arm_perf_teardown_cpu(unsigned int cpu, struct hlist_node *node)
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
index 6dc5e0cd76ca..a209de38a01c 100644
--- a/include/linux/perf/arm_pmu.h
+++ b/include/linux/perf/arm_pmu.h
@@ -177,6 +177,7 @@ void kvm_host_pmu_init(struct arm_pmu *pmu);
 #endif
 
 bool arm_pmu_irq_is_nmi(void);
+void arm_pmu_set_phys_irq(bool enable);
 
 /* Internal functions only for core arm_pmu code */
 struct arm_pmu *armpmu_alloc(void);
@@ -187,6 +188,10 @@ void armpmu_free_irq(int irq, int cpu);
 
 #define ARMV8_PMU_PDEV_NAME "armv8-pmu"
 
+#else /* CONFIG_ARM_PMU */
+
+static inline void arm_pmu_set_phys_irq(bool enable) {}
+
 #endif /* CONFIG_ARM_PMU */
 
 #define ARMV8_SPE_PDEV_NAME "arm,spe-v1"

---

## [33] Steven Price — 2025-04-16
*Subject: [PATCH v8 32/43] arm64: RME: Enable PMU support with a realm guest*

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

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v2:
 * Add a macro kvm_pmu_get_irq_level() to avoid compile issues when PMU
   support is disabled.
---
 arch/arm64/kvm/arm.c      | 11 +++++++++++
 arch/arm64/kvm/guest.c    |  7 +++++++
 arch/arm64/kvm/pmu-emul.c |  3 +++
 arch/arm64/kvm/rme.c      |  8 ++++++++
 arch/arm64/kvm/sys_regs.c |  2 +-
 include/kvm/arm_pmu.h     |  4 ++++
 6 files changed, 34 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 850708db660e..8060e25afbd0 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -15,6 +15,7 @@
 #include <linux/vmalloc.h>
 #include <linux/fs.h>
 #include <linux/mman.h>
+#include <linux/perf/arm_pmu.h>
 #include <linux/sched.h>
 #include <linux/kvm.h>
 #include <linux/kvm_irqfd.h>
@@ -1219,6 +1220,8 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 	run->exit_reason = KVM_EXIT_UNKNOWN;
 	run->flags = 0;
 	while (ret > 0) {
+		bool pmu_stopped = false;
+
 		/*
 		 * Check conditions before entering the guest
 		 */
@@ -1239,6 +1242,11 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 		if (kvm_vcpu_has_pmu(vcpu))
 			kvm_pmu_flush_hwstate(vcpu);
 
+		if (vcpu_is_rec(vcpu) && kvm_pmu_get_irq_level(vcpu)) {
+			pmu_stopped = true;
+			arm_pmu_set_phys_irq(false);
+		}
+
 		local_irq_disable();
 
 		kvm_vgic_flush_hwstate(vcpu);
@@ -1343,6 +1351,9 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 
 		preempt_enable();
 
+		if (pmu_stopped)
+			arm_pmu_set_phys_irq(true);
+
 		/*
 		 * The ARMv8 architecture doesn't give the hypervisor
 		 * a mechanism to prevent a guest from dropping to AArch32 EL0
diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index d56ac89ca37a..da8961a5d01a 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -801,6 +801,8 @@ int kvm_arm_get_reg(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg)
 	return kvm_arm_sys_reg_get_reg(vcpu, reg);
 }
 
+#define KVM_REG_ARM_PMCR_EL0		ARM64_SYS_REG(3, 3, 9, 12, 0)
+
 /*
  * The RMI ABI only enables setting some GPRs and PC. The selection of GPRs
  * that are available depends on the Realm state and the reason for the last
@@ -815,6 +817,11 @@ static bool validate_realm_set_reg(struct kvm_vcpu *vcpu,
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
index a1bc10d7116a..52b6e0eda894 100644
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
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index a89bd1c29e99..297b13ef1729 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -369,6 +369,11 @@ static int realm_create_rd(struct kvm *kvm)
 	params->rtt_base = kvm->arch.mmu.pgd_phys;
 	params->vmid = realm->vmid;
 
+	if (kvm->arch.arm_pmu) {
+		params->pmu_num_ctrs = kvm->arch.pmcr_n;
+		params->flags |= RMI_REALM_PARAM_FLAG_PMU;
+	}
+
 	params_phys = virt_to_phys(params);
 
 	if (rmi_realm_create(rd_phys, params_phys)) {
@@ -1488,6 +1493,9 @@ int kvm_create_rec(struct kvm_vcpu *vcpu)
 	if (!vcpu_has_feature(vcpu, KVM_ARM_VCPU_PSCI_0_2))
 		return -EINVAL;
 
+	if (vcpu->kvm->arch.arm_pmu && !kvm_vcpu_has_pmu(vcpu))
+		return -EINVAL;
+
 	BUILD_BUG_ON(sizeof(*params) > PAGE_SIZE);
 	BUILD_BUG_ON(sizeof(*rec->run) > PAGE_SIZE);
 
diff --git a/arch/arm64/kvm/sys_regs.c b/arch/arm64/kvm/sys_regs.c
index 005ad28f7306..de7fe024dbff 100644
--- a/arch/arm64/kvm/sys_regs.c
+++ b/arch/arm64/kvm/sys_regs.c
@@ -1215,7 +1215,7 @@ static int set_pmcr(struct kvm_vcpu *vcpu, const struct sys_reg_desc *r,
 	 * implements. Ignore this error to maintain compatibility
 	 * with the existing KVM behavior.
 	 */
-	if (!kvm_vm_has_ran_once(kvm) &&
+	if (!kvm_vm_has_ran_once(kvm) && !kvm_realm_is_created(kvm) &&
 	    new_n <= kvm_arm_pmu_get_max_counters(kvm))
 		kvm->arch.pmcr_n = new_n;
 
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

## [34] Steven Price — 2025-04-16
*Subject: [PATCH v8 33/43] arm64: RME: Hide KVM_CAP_READONLY_MEM for realm guests*

For protected memory read only isn't supported by the RMM. While it may
be possible to support read only for unprotected memory, this isn't
supported at the present time.

Note that this does mean that ROM (or flash) data cannot be emulated
correctly by the VMM as the stage 2 mappings are either always
read/write or are trapped as MMIO (so don't support operations where the
syndrome information doesn't allow emulation, e.g. load/store pair).

This restriction can be lifted in the future by allowing the stage 2
mappings to be made read only.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v7:
 * Updated commit message to spell out the impact on ROM/flash
   emulation.
---
 arch/arm64/kvm/arm.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 8060e25afbd0..4780e3af1bb9 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -340,7 +340,6 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 	case KVM_CAP_ONE_REG:
 	case KVM_CAP_ARM_PSCI:
 	case KVM_CAP_ARM_PSCI_0_2:
-	case KVM_CAP_READONLY_MEM:
 	case KVM_CAP_MP_STATE:
 	case KVM_CAP_IMMEDIATE_EXIT:
 	case KVM_CAP_VCPU_EVENTS:
@@ -355,6 +354,7 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 		r = 1;
 		break;
 	case KVM_CAP_COUNTER_OFFSET:
+	case KVM_CAP_READONLY_MEM:
 	case KVM_CAP_SET_GUEST_DEBUG:
 		r = !kvm_is_realm(kvm);
 		break;

---

## [35] Steven Price — 2025-04-16
*Subject: [PATCH v8 34/43] arm64: RME: Propagate number of breakpoints and watchpoints to userspace*

From: Jean-Philippe Brucker <jean-philippe@linaro.org>

The RMM describes the maximum number of BPs/WPs available to the guest
in the Feature Register 0. Propagate those numbers into ID_AA64DFR0_EL1,
which is visible to userspace. A VMM needs this information in order to
set up realm parameters.

Signed-off-by: Jean-Philippe Brucker <jean-philippe@linaro.org>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/include/asm/kvm_rme.h |  2 ++
 arch/arm64/kvm/rme.c             | 22 ++++++++++++++++++++++
 arch/arm64/kvm/sys_regs.c        |  2 +-
 3 files changed, 25 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index f786fd978cf6..09cbb61816f3 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -94,6 +94,8 @@ void kvm_init_rme(void);
 u32 kvm_realm_ipa_limit(void);
 u32 kvm_realm_vgic_nr_lr(void);
 
+u64 kvm_realm_reset_id_aa64dfr0_el1(const struct kvm_vcpu *vcpu, u64 val);
+
 bool kvm_rme_supports_sve(void);
 
 int kvm_realm_enable_cap(struct kvm *kvm, struct kvm_enable_cap *cap);
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 297b13ef1729..0c358ce0a7a1 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -87,6 +87,28 @@ u32 kvm_realm_vgic_nr_lr(void)
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
 	return 4 - ((realm->ia_bits - 8) / (RMM_PAGE_SHIFT - 3));
diff --git a/arch/arm64/kvm/sys_regs.c b/arch/arm64/kvm/sys_regs.c
index de7fe024dbff..36e22ed84e7e 100644
--- a/arch/arm64/kvm/sys_regs.c
+++ b/arch/arm64/kvm/sys_regs.c
@@ -1844,7 +1844,7 @@ static u64 sanitise_id_aa64dfr0_el1(const struct kvm_vcpu *vcpu, u64 val)
 	/* Hide BRBE from guests */
 	val &= ~ID_AA64DFR0_EL1_BRBE_MASK;
 
-	return val;
+	return kvm_realm_reset_id_aa64dfr0_el1(vcpu, val);
 }
 
 static int set_id_aa64dfr0_el1(struct kvm_vcpu *vcpu,

---

## [36] Steven Price — 2025-04-16
*Subject: [PATCH v8 35/43] arm64: RME: Set breakpoint parameters through SET_ONE_REG*

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
---
 arch/arm64/kvm/guest.c    |  2 ++
 arch/arm64/kvm/rme.c      |  3 +++
 arch/arm64/kvm/sys_regs.c | 17 +++++++++++------
 3 files changed, 16 insertions(+), 6 deletions(-)

diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index da8961a5d01a..dbd45d0a0d54 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -802,6 +802,7 @@ int kvm_arm_get_reg(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg)
 }
 
 #define KVM_REG_ARM_PMCR_EL0		ARM64_SYS_REG(3, 3, 9, 12, 0)
+#define KVM_REG_ARM_ID_AA64DFR0_EL1	ARM64_SYS_REG(3, 0, 0, 5, 0)
 
 /*
  * The RMI ABI only enables setting some GPRs and PC. The selection of GPRs
@@ -820,6 +821,7 @@ static bool validate_realm_set_reg(struct kvm_vcpu *vcpu,
 	} else {
 		switch (reg->id) {
 		case KVM_REG_ARM_PMCR_EL0:
+		case KVM_REG_ARM_ID_AA64DFR0_EL1:
 			return true;
 		}
 	}
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 0c358ce0a7a1..7e5469ae8a95 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -354,6 +354,7 @@ static int realm_create_rd(struct kvm *kvm)
 	void *rd = NULL;
 	phys_addr_t rd_phys, params_phys;
 	size_t pgd_size = kvm_pgtable_stage2_pgd_size(kvm->arch.mmu.vtcr);
+	u64 dfr0 = kvm_read_vm_id_reg(kvm, SYS_ID_AA64DFR0_EL1);
 	int i, r;
 	int rtt_num_start;
 
@@ -390,6 +391,8 @@ static int realm_create_rd(struct kvm *kvm)
 	params->rtt_num_start = rtt_num_start;
 	params->rtt_base = kvm->arch.mmu.pgd_phys;
 	params->vmid = realm->vmid;
+	params->num_bps = SYS_FIELD_GET(ID_AA64DFR0_EL1, BRPs, dfr0);
+	params->num_wps = SYS_FIELD_GET(ID_AA64DFR0_EL1, WRPs, dfr0);
 
 	if (kvm->arch.arm_pmu) {
 		params->pmu_num_ctrs = kvm->arch.pmcr_n;
diff --git a/arch/arm64/kvm/sys_regs.c b/arch/arm64/kvm/sys_regs.c
index 36e22ed84e7e..a53a06700867 100644
--- a/arch/arm64/kvm/sys_regs.c
+++ b/arch/arm64/kvm/sys_regs.c
@@ -1853,6 +1853,9 @@ static int set_id_aa64dfr0_el1(struct kvm_vcpu *vcpu,
 {
 	u8 debugver = SYS_FIELD_GET(ID_AA64DFR0_EL1, DebugVer, val);
 	u8 pmuver = SYS_FIELD_GET(ID_AA64DFR0_EL1, PMUVer, val);
+	u8 bps = SYS_FIELD_GET(ID_AA64DFR0_EL1, BRPs, val);
+	u8 wps = SYS_FIELD_GET(ID_AA64DFR0_EL1, WRPs, val);
+	u8 ctx_cmps = SYS_FIELD_GET(ID_AA64DFR0_EL1, CTX_CMPs, val);
 
 	/*
 	 * Prior to commit 3d0dba5764b9 ("KVM: arm64: PMU: Move the
@@ -1872,10 +1875,11 @@ static int set_id_aa64dfr0_el1(struct kvm_vcpu *vcpu,
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
 
 	return set_id_reg(vcpu, rd, val);
@@ -2055,10 +2059,11 @@ static int set_id_reg(struct kvm_vcpu *vcpu, const struct sys_reg_desc *rd,
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

## [37] Steven Price — 2025-04-16
*Subject: [PATCH v8 36/43] arm64: RME: Initialize PMCR.N with number counter supported by RMM*

From: Jean-Philippe Brucker <jean-philippe@linaro.org>

Provide an accurate number of available PMU counters to userspace when
setting up a Realm.

Signed-off-by: Jean-Philippe Brucker <jean-philippe@linaro.org>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/include/asm/kvm_rme.h | 1 +
 arch/arm64/kvm/pmu-emul.c        | 3 +++
 arch/arm64/kvm/rme.c             | 5 +++++
 3 files changed, 9 insertions(+)

diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index 09cbb61816f3..773e730da364 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -93,6 +93,7 @@ struct realm_rec {
 void kvm_init_rme(void);
 u32 kvm_realm_ipa_limit(void);
 u32 kvm_realm_vgic_nr_lr(void);
+u8 kvm_realm_max_pmu_counters(void);
 
 u64 kvm_realm_reset_id_aa64dfr0_el1(const struct kvm_vcpu *vcpu, u64 val);
 
diff --git a/arch/arm64/kvm/pmu-emul.c b/arch/arm64/kvm/pmu-emul.c
index 52b6e0eda894..5ca2eac730b3 100644
--- a/arch/arm64/kvm/pmu-emul.c
+++ b/arch/arm64/kvm/pmu-emul.c
@@ -1016,6 +1016,9 @@ u8 kvm_arm_pmu_get_max_counters(struct kvm *kvm)
 {
 	struct arm_pmu *arm_pmu = kvm->arch.arm_pmu;
 
+	if (kvm_is_realm(kvm))
+		return kvm_realm_max_pmu_counters();
+
 	/*
 	 * PMUv3 requires that all event counters are capable of counting any
 	 * event, though the same may not be true of non-PMUv3 hardware.
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 7e5469ae8a95..b09faca304fe 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -87,6 +87,11 @@ u32 kvm_realm_vgic_nr_lr(void)
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

## [38] Steven Price — 2025-04-16
*Subject: [PATCH v8 37/43] arm64: RME: Propagate max SVE vector length from RMM*

From: Jean-Philippe Brucker <jean-philippe@linaro.org>

RMM provides the maximum vector length it supports for a guest in its
feature register. Make it visible to the rest of KVM and to userspace
via KVM_REG_ARM64_SVE_VLS.

Signed-off-by: Jean-Philippe Brucker <jean-philippe@linaro.org>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/include/asm/kvm_host.h |  2 +-
 arch/arm64/include/asm/kvm_rme.h  |  1 +
 arch/arm64/kvm/guest.c            |  2 +-
 arch/arm64/kvm/reset.c            | 12 ++++++++++--
 arch/arm64/kvm/rme.c              |  6 ++++++
 5 files changed, 19 insertions(+), 4 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_host.h b/arch/arm64/include/asm/kvm_host.h
index ceb5e60ae5ae..1d2e871b8b63 100644
--- a/arch/arm64/include/asm/kvm_host.h
+++ b/arch/arm64/include/asm/kvm_host.h
@@ -76,9 +76,9 @@ enum kvm_mode kvm_get_mode(void);
 static inline enum kvm_mode kvm_get_mode(void) { return KVM_MODE_NONE; };
 #endif
 
-extern unsigned int __ro_after_init kvm_sve_max_vl;
 extern unsigned int __ro_after_init kvm_host_sve_max_vl;
 int __init kvm_arm_init_sve(void);
+unsigned int kvm_sve_get_max_vl(struct kvm *kvm);
 
 u32 __attribute_const__ kvm_target_cpu(void);
 void kvm_reset_vcpu(struct kvm_vcpu *vcpu);
diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index 773e730da364..98a83b1ed4f4 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -94,6 +94,7 @@ void kvm_init_rme(void);
 u32 kvm_realm_ipa_limit(void);
 u32 kvm_realm_vgic_nr_lr(void);
 u8 kvm_realm_max_pmu_counters(void);
+unsigned int kvm_realm_sve_max_vl(void);
 
 u64 kvm_realm_reset_id_aa64dfr0_el1(const struct kvm_vcpu *vcpu, u64 val);
 
diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index dbd45d0a0d54..17d988289100 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -374,7 +374,7 @@ static int set_sve_vls(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg)
 		if (vq_present(vqs, vq))
 			max_vq = vq;
 
-	if (max_vq > sve_vq_from_vl(kvm_sve_max_vl))
+	if (max_vq > sve_vq_from_vl(kvm_sve_get_max_vl(vcpu->kvm)))
 		return -EINVAL;
 
 	/*
diff --git a/arch/arm64/kvm/reset.c b/arch/arm64/kvm/reset.c
index 7ba3c7918a0b..f11f1f8036d5 100644
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
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index b09faca304fe..596838abdf85 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -92,6 +92,12 @@ u8 kvm_realm_max_pmu_counters(void)
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

## [39] Steven Price — 2025-04-16
*Subject: [PATCH v8 38/43] arm64: RME: Configure max SVE vector length for a Realm*

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
 arch/arm64/kvm/rme.c   | 42 ++++++++++++++++++++++++++++++++++++++++++
 2 files changed, 44 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index 17d988289100..dd379aba31bb 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -360,7 +360,7 @@ static int set_sve_vls(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg)
 	if (!vcpu_has_sve(vcpu))
 		return -ENOENT;
 
-	if (kvm_arm_vcpu_sve_finalized(vcpu))
+	if (kvm_arm_vcpu_sve_finalized(vcpu) || kvm_realm_is_created(vcpu->kvm))
 		return -EPERM; /* too late! */
 
 	if (WARN_ON(vcpu->arch.sve_state))
@@ -822,6 +822,7 @@ static bool validate_realm_set_reg(struct kvm_vcpu *vcpu,
 		switch (reg->id) {
 		case KVM_REG_ARM_PMCR_EL0:
 		case KVM_REG_ARM_ID_AA64DFR0_EL1:
+		case KVM_REG_ARM64_SVE_VLS:
 			return true;
 		}
 	}
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 596838abdf85..978906ff86fa 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -344,6 +344,44 @@ static void realm_unmap_shared_range(struct kvm *kvm,
 	}
 }
 
+static int realm_init_sve_param(struct kvm *kvm, struct realm_params *params)
+{
+	int ret = 0;
+	unsigned long i;
+	struct kvm_vcpu *vcpu;
+	int vl, last_vl = -1;
+
+	/*
+	 * Get the preferred SVE configuration, set by userspace with the
+	 * KVM_ARM_VCPU_SVE feature and KVM_REG_ARM64_SVE_VLS pseudo-register.
+	 */
+	kvm_for_each_vcpu(i, vcpu, kvm) {
+		mutex_lock(&vcpu->mutex);
+		if (vcpu_has_sve(vcpu)) {
+			if (!kvm_arm_vcpu_sve_finalized(vcpu))
+				ret = -EINVAL;
+			vl = vcpu->arch.sve_max_vl;
+		} else {
+			vl = 0;
+		}
+		mutex_unlock(&vcpu->mutex);
+		if (ret)
+			return ret;
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
@@ -410,6 +448,10 @@ static int realm_create_rd(struct kvm *kvm)
 		params->flags |= RMI_REALM_PARAM_FLAG_PMU;
 	}
 
+	r = realm_init_sve_param(kvm, params);
+	if (r)
+		goto out_undelegate_tables;
+
 	params_phys = virt_to_phys(params);
 
 	if (rmi_realm_create(rd_phys, params_phys)) {

---

## [40] Steven Price — 2025-04-16
*Subject: [PATCH v8 39/43] arm64: RME: Provide register list for unfinalized RME RECs*

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
---
 arch/arm64/kvm/arm.c   | 4 ----
 arch/arm64/kvm/guest.c | 9 +++------
 2 files changed, 3 insertions(+), 10 deletions(-)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 4780e3af1bb9..eaa60ba6d97b 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -1832,10 +1832,6 @@ long kvm_arch_vcpu_ioctl(struct file *filp,
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
index dd379aba31bb..1288920fc73d 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -671,12 +671,9 @@ static unsigned long num_sve_regs(const struct kvm_vcpu *vcpu)
 {
 	const unsigned int slices = vcpu_sve_slices(vcpu);
 
-	if (!vcpu_has_sve(vcpu))
+	if (!vcpu_has_sve(vcpu) || !kvm_arm_vcpu_sve_finalized(vcpu))
 		return 0;
 
-	/* Policed by KVM_GET_REG_LIST: */
-	WARN_ON(!kvm_arm_vcpu_sve_finalized(vcpu));
-
 	return slices * (SVE_NUM_PREGS + SVE_NUM_ZREGS + 1 /* FFR */)
 		+ 1; /* KVM_REG_ARM64_SVE_VLS */
 }
@@ -692,8 +689,8 @@ static int copy_sve_reg_indices(const struct kvm_vcpu *vcpu,
 	if (!vcpu_has_sve(vcpu))
 		return 0;
 
-	/* Policed by KVM_GET_REG_LIST: */
-	WARN_ON(!kvm_arm_vcpu_sve_finalized(vcpu));
+	if (!kvm_arm_vcpu_sve_finalized(vcpu))
+		return -EPERM;
 
 	/*
 	 * Enumerate this first, so that userspace can save/restore in

---

## [41] Steven Price — 2025-04-16
*Subject: [PATCH v8 40/43] arm64: RME: Provide accurate register list*

From: Jean-Philippe Brucker <jean-philippe@linaro.org>

Userspace can set a few registers with KVM_SET_ONE_REG (9 GP registers
at runtime, and 3 system registers during initialization). Update the
register list returned by KVM_GET_REG_LIST.

Signed-off-by: Jean-Philippe Brucker <jean-philippe@linaro.org>
Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v7:
 * Reworked on upstream changes.
---
 arch/arm64/kvm/guest.c      | 19 ++++++++++++++-----
 arch/arm64/kvm/hypercalls.c |  4 ++--
 arch/arm64/kvm/sys_regs.c   | 28 ++++++++++++++++++++++------
 3 files changed, 38 insertions(+), 13 deletions(-)

diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index 1288920fc73d..e9bb7647aa65 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -618,8 +618,6 @@ static const u64 timer_reg_list[] = {
 	KVM_REG_ARM_PTIMER_CVAL,
 };
 
-#define NUM_TIMER_REGS ARRAY_SIZE(timer_reg_list)
-
 static bool is_timer_reg(u64 index)
 {
 	switch (index) {
@@ -634,9 +632,14 @@ static bool is_timer_reg(u64 index)
 	return false;
 }
 
+static unsigned long num_timer_regs(struct kvm_vcpu *vcpu)
+{
+	return kvm_is_realm(vcpu->kvm) ? 0 : ARRAY_SIZE(timer_reg_list);
+}
+
 static int copy_timer_indices(struct kvm_vcpu *vcpu, u64 __user *uindices)
 {
-	for (int i = 0; i < NUM_TIMER_REGS; i++) {
+	for (int i = 0; i < num_timer_regs(vcpu); i++) {
 		if (put_user(timer_reg_list[i], uindices))
 			return -EFAULT;
 		uindices++;
@@ -674,6 +677,9 @@ static unsigned long num_sve_regs(const struct kvm_vcpu *vcpu)
 	if (!vcpu_has_sve(vcpu) || !kvm_arm_vcpu_sve_finalized(vcpu))
 		return 0;
 
+	if (kvm_is_realm(vcpu->kvm))
+		return 1; /* KVM_REG_ARM64_SVE_VLS */
+
 	return slices * (SVE_NUM_PREGS + SVE_NUM_ZREGS + 1 /* FFR */)
 		+ 1; /* KVM_REG_ARM64_SVE_VLS */
 }
@@ -701,6 +707,9 @@ static int copy_sve_reg_indices(const struct kvm_vcpu *vcpu,
 		return -EFAULT;
 	++num_regs;
 
+	if (kvm_is_realm(vcpu->kvm))
+		return num_regs;
+
 	for (i = 0; i < slices; i++) {
 		for (n = 0; n < SVE_NUM_ZREGS; n++) {
 			reg = KVM_REG_ARM64_SVE_ZREG(n, i);
@@ -739,7 +748,7 @@ unsigned long kvm_arm_num_regs(struct kvm_vcpu *vcpu)
 	res += num_sve_regs(vcpu);
 	res += kvm_arm_num_sys_reg_descs(vcpu);
 	res += kvm_arm_get_fw_num_regs(vcpu);
-	res += NUM_TIMER_REGS;
+	res += num_timer_regs(vcpu);
 
 	return res;
 }
@@ -773,7 +782,7 @@ int kvm_arm_copy_reg_indices(struct kvm_vcpu *vcpu, u64 __user *uindices)
 	ret = copy_timer_indices(vcpu, uindices);
 	if (ret < 0)
 		return ret;
-	uindices += NUM_TIMER_REGS;
+	uindices += num_timer_regs(vcpu);
 
 	return kvm_arm_copy_sys_reg_indices(vcpu, uindices);
 }
diff --git a/arch/arm64/kvm/hypercalls.c b/arch/arm64/kvm/hypercalls.c
index 569941eeb3fe..fb2bba0c7e86 100644
--- a/arch/arm64/kvm/hypercalls.c
+++ b/arch/arm64/kvm/hypercalls.c
@@ -412,14 +412,14 @@ void kvm_arm_teardown_hypercalls(struct kvm *kvm)
 
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
index a53a06700867..7d384016d1ba 100644
--- a/arch/arm64/kvm/sys_regs.c
+++ b/arch/arm64/kvm/sys_regs.c
@@ -4960,18 +4960,18 @@ int kvm_arm_sys_reg_set_reg(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg
 				    sys_reg_descs, ARRAY_SIZE(sys_reg_descs));
 }
 
-static unsigned int num_demux_regs(void)
+static unsigned int num_demux_regs(struct kvm_vcpu *vcpu)
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
@@ -5002,11 +5002,27 @@ static bool copy_reg_to_user(const struct sys_reg_desc *reg, u64 __user **uind)
 	return true;
 }
 
+static bool kvm_realm_sys_reg_hidden_user(const struct kvm_vcpu *vcpu, u64 reg)
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
@@ -5044,7 +5060,7 @@ static int walk_sys_regs(struct kvm_vcpu *vcpu, u64 __user *uind)
 
 unsigned long kvm_arm_num_sys_reg_descs(struct kvm_vcpu *vcpu)
 {
-	return num_demux_regs()
+	return num_demux_regs(vcpu)
 		+ walk_sys_regs(vcpu, (u64 __user *)NULL);
 }
 
@@ -5057,7 +5073,7 @@ int kvm_arm_copy_sys_reg_indices(struct kvm_vcpu *vcpu, u64 __user *uindices)
 		return err;
 	uindices += err;
 
-	return write_demux_regids(uindices);
+	return write_demux_regids(vcpu, uindices);
 }
 
 #define KVM_ARM_FEATURE_ID_RANGE_INDEX(r)			\

---

## [42] Steven Price — 2025-04-16
*Subject: [PATCH v8 41/43] KVM: arm64: Expose support for private memory*

Select KVM_GENERIC_PRIVATE_MEM and provide the necessary support
functions.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v2:
 * Switch kvm_arch_has_private_mem() to a macro to avoid overhead of a
   function call.
 * Guard definitions of kvm_arch_{pre,post}_set_memory_attributes() with
   #ifdef CONFIG_KVM_GENERIC_MEMORY_ATTRIBUTES.
 * Early out in kvm_arch_post_set_memory_attributes() if the WARN_ON
   should trigger.
---
 arch/arm64/include/asm/kvm_host.h |  6 ++++++
 arch/arm64/kvm/Kconfig            |  1 +
 arch/arm64/kvm/mmu.c              | 24 ++++++++++++++++++++++++
 3 files changed, 31 insertions(+)

diff --git a/arch/arm64/include/asm/kvm_host.h b/arch/arm64/include/asm/kvm_host.h
index 1d2e871b8b63..3c61b84e5c4e 100644
--- a/arch/arm64/include/asm/kvm_host.h
+++ b/arch/arm64/include/asm/kvm_host.h
@@ -1460,6 +1460,12 @@ struct kvm *kvm_arch_alloc_vm(void);
 
 #define vcpu_is_protected(vcpu)		kvm_vm_is_protected((vcpu)->kvm)
 
+#ifdef CONFIG_KVM_PRIVATE_MEM
+#define kvm_arch_has_private_mem(kvm) ((kvm)->arch.is_realm)
+#else
+#define kvm_arch_has_private_mem(kvm) false
+#endif
+
 int kvm_arm_vcpu_finalize(struct kvm_vcpu *vcpu, int feature);
 bool kvm_arm_vcpu_is_finalized(struct kvm_vcpu *vcpu);
 
diff --git a/arch/arm64/kvm/Kconfig b/arch/arm64/kvm/Kconfig
index 096e45acadb2..a5fbf51d57b5 100644
--- a/arch/arm64/kvm/Kconfig
+++ b/arch/arm64/kvm/Kconfig
@@ -38,6 +38,7 @@ menuconfig KVM
 	select HAVE_KVM_VCPU_RUN_PID_CHANGE
 	select SCHED_INFO
 	select GUEST_PERF_EVENTS if PERF_EVENTS
+	select KVM_GENERIC_PRIVATE_MEM
 	help
 	  Support hosting virtualized guest machines.
 
diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index b861747ea1b3..55664ddeae42 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -2364,6 +2364,30 @@ int kvm_arch_prepare_memory_region(struct kvm *kvm,
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

## [43] Steven Price — 2025-04-16
*Subject: [PATCH v8 42/43] KVM: arm64: Expose KVM_ARM_VCPU_REC to user space*

Increment KVM_VCPU_MAX_FEATURES to expose the new capability to user
space.

Signed-off-by: Steven Price <steven.price@arm.com>
---
*NOTE*: This also exposes KVM_ARM_VCPU_HAS_EL2/KVM_ARM_VCPU_HAS_EL2_E2H0
(as they are both less than KVM_ARM_VCPU_REC) - so this currently
depends on nested virt being 'finished' before merging.

So this should be merged after: "KVM: arm64: Allow userspace to request
KVM_ARM_VCPU_EL2*":
https://lore.kernel.org/r/20250408105225.4002637-17-maz%40kernel.org
---
 arch/arm64/include/asm/kvm_host.h | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/kvm_host.h b/arch/arm64/include/asm/kvm_host.h
index 3c61b84e5c4e..6d0b1772540d 100644
--- a/arch/arm64/include/asm/kvm_host.h
+++ b/arch/arm64/include/asm/kvm_host.h
@@ -40,7 +40,7 @@
 
 #define KVM_MAX_VCPUS VGIC_V3_MAX_CPUS
 
-#define KVM_VCPU_MAX_FEATURES 7
+#define KVM_VCPU_MAX_FEATURES 10
 #define KVM_VCPU_VALID_FEATURES	(BIT(KVM_VCPU_MAX_FEATURES) - 1)
 
 #define KVM_REQ_SLEEP \

---

## [44] Steven Price — 2025-04-16
*Subject: [PATCH v8 43/43] KVM: arm64: Allow activating realms*

Add the ioctl to activate a realm and set the static branch to enable
access to the realm functionality if the RMM is detected.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/kvm/rme.c | 19 ++++++++++++++++++-
 1 file changed, 18 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 978906ff86fa..3f8441bdf293 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -1234,6 +1234,20 @@ static int kvm_init_ipa_range_realm(struct kvm *kvm,
 	return realm_init_ipa_state(realm, addr, end);
 }
 
+static int kvm_activate_realm(struct kvm *kvm)
+{
+	struct realm *realm = &kvm->arch.realm;
+
+	if (kvm_realm_state(kvm) != REALM_STATE_NEW)
+		return -EINVAL;
+
+	if (rmi_realm_activate(virt_to_phys(realm->rd)))
+		return -ENXIO;
+
+	WRITE_ONCE(realm->state, REALM_STATE_ACTIVE);
+	return 0;
+}
+
 /* Protects access to rme_vmid_bitmap */
 static DEFINE_SPINLOCK(rme_vmid_lock);
 static unsigned long *rme_vmid_bitmap;
@@ -1383,6 +1397,9 @@ int kvm_realm_enable_cap(struct kvm *kvm, struct kvm_enable_cap *cap)
 		r = kvm_populate_realm(kvm, &args);
 		break;
 	}
+	case KVM_CAP_ARM_RME_ACTIVATE_REALM:
+		r = kvm_activate_realm(kvm);
+		break;
 	default:
 		r = -EINVAL;
 		break;
@@ -1687,5 +1704,5 @@ void kvm_init_rme(void)
 	if (rme_vmid_init())
 		return;
 
-	/* Future patch will enable static branch kvm_rme_is_available */
+	static_branch_enable(&kvm_rme_is_available);
 }

---

## [45] Suzuki K Poulose — 2025-04-25
*Subject: Re: [PATCH v8 03/43] arm64: RME: Add SMC definitions for calling the
 RMM*

On 16/04/2025 14:41, Steven Price wrote:
> The RMM (Realm Management Monitor) provides functionality that can be
> accessed by SMC calls from the host.

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>

---

## [46] Suzuki K Poulose — 2025-04-25
*Subject: Re: [PATCH v8 04/43] arm64: RME: Add wrappers for RMI calls*

Hi Steven

On 16/04/2025 14:41, Steven Price wrote:
> The wrappers make the call sites easier to read and deal with the
> boiler plate of handling the error codes from the RMM.

...

> +
> +/**

minor nit: It may be worth emphasising that you mean HIPAS here and not
RMI_ASSIGNED (as returned by RTT_READ_ENTRY). The key is, an unprotected
live leaf mapping  (i.e., HIPAS=ASSIGNED_NS) is considered non-live.

Either ways:

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>

---

## [47] Suzuki K Poulose — 2025-04-25
*Subject: Re: [PATCH v8 04/43] arm64: RME: Add wrappers for RMI calls*

On 25/04/2025 11:48, Suzuki K Poulose wrote:
> Hi Steven
> 

Ah, I went back to the spec and TABLE is not a HIPAS ( :facepalm ).
They are indeed RmmRttEntryState type. So, the comment is fine as it is.
Please ignore ^

> 
> Either ways:


> Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>

Suzuki

---

## [48] Suzuki K Poulose — 2025-04-25
*Subject: Re: [PATCH v8 05/43] arm64: RME: Check for RME support at KVM init*

On 16/04/2025 14:41, Steven Price wrote:
> Query the RMI version number and check if it is a compatible version. A
> static key is also provided to signal that a supported RMM is available.

minor nit:

I wondering if this check is necessary. If the host is running under a
a hypervisor, it could relay the calls to the RMM. Nothing urgent, but
it is a possibility. It doesn't matter to the host as such. The
Realm Guest will do its own verification and the host can ignore
what lies beneath ?


Either ways,

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>

---

## [49] Suzuki K Poulose — 2025-04-28
*Subject: Re: [PATCH v8 06/43] arm64: RME: Define the user ABI*

Hi Steven

On 16/04/2025 14:41, Steven Price wrote:
> There is one (multiplexed) CAP which can be used to create, populate and
> then activate the realm.

minor nit: s/RMM create/RMM to create/

Or may be rephrase it:

Request the RMM to create the Realm with the configured parameters.


> +                                  configuration parameters must be set first.
> +

nit: struct arm_rme_populate_realm

> +                                  and populates a region of protected address
> +                                  space by copying the data from the shared

s/the RMM/the RMM to/

> +                                  further changes can be made to the realm's
> +                                  configuration, and VCPUs are not permitted to

minor nit: this sounds as if "configurations" (of parameters)  are
possible after the CREATE_REALM and before ACTIVATE_REALM ? Could we
also make it clear that the VCPUs must have been created before ACTIVATE ?


May be rephrase it to:

No changes can be made to Realm's memory (including the IPA state). No 
new VCPUs can be created after this step.


> +================================= =============================================
> +

minor nit:
May be we could rename this to CONFIG_HASH_ALGO_* to align with the
RMM spec (btw which also moved from measurement to hash) and the
parameter.


Suzuki


> +
> +#define ARM_RME_CONFIG_RPV_SIZE 64

---

## [50] Suzuki K Poulose — 2025-04-29
*Subject: Re: [PATCH v8 07/43] arm64: RME: ioctls to create and configure
 realms*

On 16/04/2025 14:41, Steven Price wrote:
> Add the KVM_CAP_ARM_RME_CREATE_RD ioctl to create a realm. This involves
> delegating pages to the RMM to hold the Realm Descriptor (RD) and for

minor nit: It may be worth adding a comment here, how we got this magic
number 8. We could say:

Open coded version of ARM64_HW_PGTABLE_LEVELS(ia_bits - 4) (accounting 
for the concatenation of upto 16 tables in entry level) for RMM Stage2.


> +}
> +

nit: Why is this 3 - start_level and not 4 ? Though that is compensated 
by the "levels + 1" below, hence the calculation is correct.

> +	unsigned int sl_ipa_bits = (levels + 1) * (RMM_PAGE_SHIFT - 3) +
> +				   RMM_PAGE_SHIFT;

minor nit: Do we need to try undelegating the other pages ? We could 
make that WARN_ON_ONCE() too.

Suzuki

---

## [51] Gavin Shan — 2025-04-30
*Subject: Re: [PATCH v8 06/43] arm64: RME: Define the user ABI*

On 4/16/25 11:41 PM, Steven Price wrote:
> There is one (multiplexed) CAP which can be used to create, populate and
> then activate the realm.

With below comment addressed:

Reviewed-by: Gavin Shan <gshan@redhat.com>

> diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
> index 1f8625b7646a..99ba6c82cf37 100644
                                                               ^^^^^^^^^^^^^^^^^^
s/has been activated/is deactivated

I don't see where the guard is applied to prevent vCPU is added after realm
has been activated. I may missed that. Otherwise, it's something to be improved
n the subsequent patch where a vCPU is created and added to the realm.


> +================================= =============================================
> +

Thanks,
Gavin

---

## [52] Gavin Shan — 2025-04-30
*Subject: Re: [PATCH v8 07/43] arm64: RME: ioctls to create and configure
 realms*

On 4/16/25 11:41 PM, Steven Price wrote:
> Add the KVM_CAP_ARM_RME_CREATE_RD ioctl to create a realm. This involves
> delegating pages to the RMM to hold the Realm Descriptor (RD) and for

This check is duplicate because the only caller kvm_realm_enable_cap() already
has the check. So it can be dropped.

> +	if (kvm_realm_is_created(kvm))
> +		return -EEXIST;

Thanks,
Gavin

---

## [53] Gavin Shan — 2025-04-30
*Subject: Re: [PATCH v8 08/43] kvm: arm64: Don't expose debug capabilities for
 realm guests*

On 4/16/25 11:41 PM, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

Reviewed-by: Gavin Shan <gshan@redhat.com>

---

## [54] Gavin Shan — 2025-04-30
*Subject: Re: [PATCH v8 09/43] KVM: arm64: Allow passing machine type in KVM
 creation*

On 4/16/25 11:41 PM, Steven Price wrote:
> Previously machine type was used purely for specifying the physical
> address size of the guest. Reserve the higher bits to specify an ARM

Reviewed-by: Gavin Shan <gshan@redhat.com>

---

## [55] Gavin Shan — 2025-04-30
*Subject: Re: [PATCH v8 12/43] KVM: arm64: vgic: Provide helper for number of
 list registers*

On 4/16/25 11:41 PM, Steven Price wrote:
> Currently the number of list registers available is stored in a global
> (kvm_vgic_global_state.nr_lr). With Arm CCA the RMM is permitted to

With below nitpick addressed:

Reviewed-by: Gavin Shan <gshan@redhat.com>

> diff --git a/arch/arm64/kvm/vgic/vgic.c b/arch/arm64/kvm/vgic/vgic.c
> index 8f8096d48925..8d189ce18ea0 100644

The unnecessary space before the semicolon can be dropped.

	for (i = count; i < kvm_vcpu_vgic_nr_lr(vcpu); i++)

>   	if (!static_branch_unlikely(&kvm_vgic_global_state.gicv3_cpuif))

Thanks,
Gavin

---

## [56] Gavin Shan — 2025-04-30
*Subject: Re: [PATCH v8 15/43] arm64: RME: Allow VMM to set RIPAS*

On 4/16/25 11:41 PM, Steven Price wrote:
> Each page within the protected region of the realm guest can be marked
> as either RAM or EMPTY. Allow the VMM to control this before the guest


It would be more safe to use (GFP_ATOMIC | __GFP_ZERO | __GFP_ACCOUNT), consistent
to the flags used by kvm_mmu_memory_cache_alloc().

> +
> +	if (!virt)

This function can be called by the MMU notifier to invalidate the mapping for
the specified IPA range. However, we're missing one parameter to indicate if
the request from the MMU notifier is blockable or not. We're having the imprecise
assumption that all requests are blockable, which isn't always true. With this
assumption, cond_resched_rwlock_write(&kvm->mmu_lock) is always called in
realm_unmap_shared_range().

Another issue is that cond_resched_rwlock_write(&kvm->mmu_lock) is missed if
the request is blockable in realm_unmap_private_page().

> +	unsigned long end = start + size;
> +	struct realm *realm = &kvm->arch.realm;

	if (!kvm_realm_is_created(kvm)))
		return;

> +
> +	realm_unmap_shared_range(kvm, find_map_level(realm, start, end),

The readability would be better if the explicit 'continue' can be avoid, something
like below:

	switch (RMI_RETURN_STATUS(ret)) {
	case RMI_SUCCESS:
		ipa = next;
		break;
	case RMI_ERROR_RTT:
		:
		ret = realm_create_rtt_levels(realm, ipa, error_level, level, NULL);
		if (ret)
			return ret;
		break;
	default:
		WARN_ON(1);
		return -ENXIO;
	}

> +static int kvm_init_ipa_range_realm(struct kvm *kvm,
> +				    struct arm_rme_init_ripas *args)

The check needs to cover 'end <= addr'. RMI_ERROR_INPUT is returned from RMM::smc_rtt_init_ripas()
if 'end' is equal to 'addr', but we're returning 0, inconsistent to that.

	if (end <= addr)
		return -EINVAL;

> +
> +	if (kvm_realm_state(kvm) != REALM_STATE_NEW)

To keep the consistency, kvm_realm_is_created() can be used here.

	if (kvm_realm_is_created(kvm))
		return -EPERM;

> +
> +	return realm_init_ipa_state(realm, addr, end);

Thanks,
Gavin

---

## [57] Gavin Shan — 2025-04-30
*Subject: Re: [PATCH v8 16/43] arm64: RME: Handle realm enter/exit*

On 4/16/25 11:41 PM, Steven Price wrote:
> Entering a realm is done using a SMC call to the RMM. On exit the
> exit-codes need to be handled slightly differently to the normal KVM

One nitpick below.

Reviewed-by: Gavin Shan <gshan@redhat.com>

> diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
> index b916db8565a2..d86051ef0c5c 100644

kvm_handle_sys_reg() always returns positive value, so it can be:

	if (!is_write)
		rc->run->enter.gprs[0] = vcpu_get_reg(vcpu, rt);

> +
> +	return ret;

Thanks,
Gavin

---

## [58] Gavin Shan — 2025-04-30
*Subject: Re: [PATCH v8 17/43] arm64: RME: Handle RMI_EXIT_RIPAS_CHANGE*

On 4/16/25 11:41 PM, Steven Price wrote:
> The guest can request that a region of it's protected address space is
> switched between RIPAS_RAM and RIPAS_EMPTY (and back) using

One nitpick below, either way:

Reviewed-by: Gavin Shan <gshan@redhat.com>

> diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
> index bee9dfe12e03..fe0d5b8703d2 100644

--->

> +			int walk_level = RMI_RETURN_INDEX(ret);
> +			int level = find_map_level(realm, ipa, end);

<--- This block of code have been existing in multiple functions. I guess
it would be worthy to introduce a helper for it if you agree. Alternatively,
it's definitely something to do in the future, after this series is merged :)

> +			break;
> +		} else {

Thanks,
Gavin

---

## [59] Gavin Shan — 2025-05-01
*Subject: Re: [PATCH v8 20/43] arm64: RME: Runtime faulting of memory*

On 4/16/25 11:41 PM, Steven Price wrote:
> At runtime if the realm guest accesses memory which hasn't yet been
> mapped then KVM needs to either populate the region or fault the guest.

As spotted previsouly, the parameter @may_block isn't handled by kvm_realm_unmap_range().

>   void kvm_stage2_unmap_range(struct kvm_s2_mmu *mmu, phys_addr_t start,
> @@ -359,7 +364,10 @@ static void stage2_flush_memslot(struct kvm *kvm,

(~0ULL & PAGE_MASK) wouldn't be a problem since the range will be limited to
[0, BIT(realm->ia_bits) - 1] in kvm_realm_unmap_range(). I think it's reasonable
to pass the maximal size here, something like:

		kvm_stage2_unmap_range(mmu, 0, BIT(realm->ia_bits - 1), false);

>   
> @@ -1482,6 +1495,82 @@ static bool kvm_vma_mte_allowed(struct vm_area_struct *vma)

A comment to explain why KVM_PGTABLE_PROT_W is required would be nice, something like:

	/*
	 * Write permission is required for now even though it's possible to
	 * map unprotected pages (granules) as read-only. It's impossible to
	 * map protected pages (granules) as read-only.
	 */

> +
> +	ipa = ALIGN_DOWN(ipa, PAGE_SIZE);

nit:

		kvm_prepare_memory_fault_exit(vcpu, gpa, PAGE_SIZE,
				kvm_is_write_fault(vcpu), false, is_priv_fault);

> +
> +		/*

This block of code can be compacted a bit:

	int map_level = IS_ALIGNED(map_size, RMM_L2_BLOCK_SIZE) ? 2 : 3;

	if (WARN_ON(!IS_ALIGNED(map_size, RMM_PAGE_SIZE) || !IS_ALIGNED(ipa, map_size))
		return -EINVAL;

> +	if (map_level < RMM_RTT_MAX_LEVEL) {
> +		/*

Similiarly, it can be compacted a bit:

	int map_size = IS_ALIGNED(size, RMM_L2_BLOCK_SIZE) ? RMM_L2_BLOCK_SIZE : RMM_PAGE_SIZE;
	int map_level = IS_ALIGNED(map_size, RMM_L2_BLOCK_SIZE) ? 2 : 3;

	if (WARN_ON(!IS_ALIGNED(size, RMM_PAGE_SIZE) || !IS_ALIGNED(ipa, size))
		return -EINVAL;

> +	for (offset = 0; offset < size; offset += map_size) {
> +		/*

The comments needs to be aligned in format :)

If RMM returns RMI_ERROR_RTT for third case in the future, the assumption here
is broken. I think it's worthy to double confirm by checking the RTT entry
through RTT_READ_ENTRY interface. If the mapping doesn't exist, we probably
still need to retry.

> +
> +		ipa += map_size;

Thanks,
Gavin

---

## [60] Gavin Shan — 2025-05-01
*Subject: Re: [PATCH v8 22/43] KVM: arm64: Validate register access for a Realm
 VM*

On 4/16/25 11:41 PM, Steven Price wrote:
> The RMM only allows setting the GPRS (x0-x30) and PC for a realm
> guest. Check this in kvm_arm_set_reg() so that the VMM can receive a

Reviewed-by: Gavin Shan <gshan@redhat.com>

---

## [61] Gavin Shan — 2025-05-01
*Subject: Re: [PATCH v8 27/43] arm64: RME: support RSI_HOST_CALL*

On 4/16/25 11:41 PM, Steven Price wrote:
> From: Joey Gouly <joey.gouly@arm.com>
> 

Reviewed-by: Gavin Shan <gshan@redhat.com>

---

## [62] Gavin Shan — 2025-05-01
*Subject: Re: [PATCH v8 29/43] arm64: RME: Always use 4k pages for realms*

On 4/16/25 11:41 PM, Steven Price wrote:
> Guest_memfd doesn't yet natively support huge pages, and there are
> currently difficulties for a VMM to manage huge pages efficiently so for

One nitpick below.

Reviewed-by: Gavin Shan <gshan@redhat.com>

> diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
> index 02b66ee35426..29bab7a46033 100644

		/* Force PTE level mappings for realms */

>   	} else {
>   		vma_shift = get_vma_page_shift(vma, hva);

Thanks,
Gavin

---

## [63] Gavin Shan — 2025-05-01
*Subject: Re: [PATCH v8 33/43] arm64: RME: Hide KVM_CAP_READONLY_MEM for realm
 guests*

On 4/16/25 11:41 PM, Steven Price wrote:
> For protected memory read only isn't supported by the RMM. While it may
> be possible to support read only for unprotected memory, this isn't

Reviewed-by: Gavin Shan <gshan@redhat.com>

---

## [64] Gavin Shan — 2025-05-01
*Subject: Re: [PATCH v8 41/43] KVM: arm64: Expose support for private memory*

On 4/16/25 11:42 PM, Steven Price wrote:
> Select KVM_GENERIC_PRIVATE_MEM and provide the necessary support
> functions.

Reviewed-by: Gavin Shan <gshan@redhat.com>

---

## [65] Gavin Shan — 2025-05-01
*Subject: Re: [PATCH v8 42/43] KVM: arm64: Expose KVM_ARM_VCPU_REC to user
 space*

On 4/16/25 11:42 PM, Steven Price wrote:
> Increment KVM_VCPU_MAX_FEATURES to expose the new capability to user
> space.

Reviewed-by: Gavin Shan <gshan@redhat.com>

---

## [66] Gavin Shan — 2025-05-01
*Subject: Re: [PATCH v8 43/43] KVM: arm64: Allow activating realms*

On 4/16/25 11:42 PM, Steven Price wrote:
> Add the ioctl to activate a realm and set the static branch to enable
> access to the realm functionality if the RMM is detected.

Reviewed-by: Gavin Shan <gshan@redhat.com>

---

## [67] Gavin Shan — 2025-05-01
*Subject: Re: [PATCH v8 34/43] arm64: RME: Propagate number of breakpoints and
 watchpoints to userspace*

On 4/16/25 11:41 PM, Steven Price wrote:
> From: Jean-Philippe Brucker <jean-philippe@linaro.org>
> 

If I don't miss anything, it's not enough to apply the filter on reading and
resetting path where sanitise_id_aa64dfr0_el1() is called. id_aa64dfr0_el1
is writable and it's possible that QEMU modifies its value. Afterwards, the
register is read from guest kernel, which will be trapped to host and the
modified value is returned, without this filter applied. So I think the same
filter need to be applied to the write path originated from QEMU.

Thanks,
Gavin

> diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
> index f786fd978cf6..09cbb61816f3 100644

---

## [68] Gavin Shan — 2025-05-01
*Subject: Re: [PATCH v8 34/43] arm64: RME: Propagate number of breakpoints and
 watchpoints to userspace*

On 5/1/25 1:36 PM, Gavin Shan wrote:
> On 4/16/25 11:41 PM, Steven Price wrote:
>> From: Jean-Philippe Brucker <jean-philippe@linaro.org>

Please ignore this and it has been done in next patch :)

Thanks,
Gavin

>> diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
>> index f786fd978cf6..09cbb61816f3 100644

---

## [69] Gavin Shan — 2025-05-01
*Subject: Re: [PATCH v8 34/43] arm64: RME: Propagate number of breakpoints and
 watchpoints to userspace*

On 4/16/25 11:41 PM, Steven Price wrote:
> From: Jean-Philippe Brucker <jean-philippe@linaro.org>
> 

Reviewed-by: Gavin Shan <gshan@redhat.com>

---

## [70] Gavin Shan — 2025-05-01
*Subject: Re: [PATCH v8 36/43] arm64: RME: Initialize PMCR.N with number
 counter supported by RMM*

On 4/16/25 11:41 PM, Steven Price wrote:
> From: Jean-Philippe Brucker <jean-philippe@linaro.org>
> 

Reviewed-by: Gavin Shan <gshan@redhat.com>

---

## [71] Gavin Shan — 2025-05-01
*Subject: Re: [PATCH v8 37/43] arm64: RME: Propagate max SVE vector length from
 RMM*

On 4/16/25 11:41 PM, Steven Price wrote:
> From: Jean-Philippe Brucker <jean-philippe@linaro.org>
> 

Reviewed-by: Gavin Shan <gshan@redhat.com>

---

## [72] Gavin Shan — 2025-05-01
*Subject: Re: [PATCH v8 38/43] arm64: RME: Configure max SVE vector length for
 a Realm*

On 4/16/25 11:42 PM, Steven Price wrote:
> From: Jean-Philippe Brucker <jean-philippe@linaro.org>
> 

Reviewed-by: Gavin Shan <gshan@redhat.com>

---

## [73] Steven Price — 2025-05-01
*Subject: Re: [PATCH v8 05/43] arm64: RME: Check for RME support at KVM init*

On 25/04/2025 12:08, Suzuki K Poulose wrote:
> On 16/04/2025 14:41, Steven Price wrote:
>> Query the RMI version number and check if it is a compatible version. A

Reasonable point - I don't think we have anything yet that can do that
sort of relaying. But I guess anything which handles the RMI API we
should be compatible with, so there's no need specifically to require
in_hyp_mode.

Thanks,
Steve

> 
> Either ways,

---

## [74] Steven Price — 2025-05-01
*Subject: Re: [PATCH v8 06/43] arm64: RME: Define the user ABI*

On 28/04/2025 09:58, Suzuki K Poulose wrote:
> Hi Steven
> 

Ack

> Or may be rephrase it:
> 

Copy/paste error - thanks for spotting.

>> +                                  and populates a region of protected
>> address

Ack

>> +                                  further changes can be made to the
>> realm's

I was attmepting to include that CONFIG_REALM cannot be called. How about:

	Request the RMM to activate the realm. No
	changes can be made to the Realm's memory,
	IPA state or configuration parameters.  No
	new VCPUs can be created after this step.

>> +=================================
>> =============================================

Ah, I must have missed that rename in the spec - yes that makes sense,
I've generally tried to stick closely to the naming in the spec.

Thanks,
Steve

> Suzuki
>

---

## [75] Steven Price — 2025-05-01
*Subject: Re: [PATCH v8 06/43] arm64: RME: Define the user ABI*

Hi Gavin,

On 30/04/2025 05:25, Gavin Shan wrote:
> On 4/16/25 11:41 PM, Steven Price wrote:
>> There is one (multiplexed) CAP which can be used to create, populate and

I think I worded it badly before (as Susuki has already pointed out) and
you haven't understood what I intended.

VCPUs can be added to a Realm guest up until the ACTIVATE_REALM call.
There is no "deactivate" - you would need to destroy the guest and start
again.

What I intended was to say that a VCPU must not be executed (KVM_RUN)
until the ACTIVE_REALM call.

> I don't see where the guard is applied to prevent vCPU is added after realm
> has been activated. I may missed that. Otherwise, it's something to be

This is handled in kvm_create_rec() where there's a check that
kvm_realm_state() != REALM_STATE_NEW. This prevents finalization of a
VCPU unless the realm is still in "new" state.

Admittedly this doesn't technically stop the user creating a VCPU. I
could add a check in kvm_arch_vcpu_create(), however this wouldn't stop
a VMM creating a VCPU and not finalising it before activating the realm.
So we'd end up with the same situation. I'm not sure whether it's worth
trying to stop the VMM or if I should just reword to say that the VMM
shouldn't do this.

I don't believe anything bad will happen to the host in these situations
- you will just end up with a useless VCPU which cannot be run.

Thanks,
Steve

>> +=================================
>> =============================================

---

## [76] Suzuki K Poulose — 2025-05-01
*Subject: Re: [PATCH v8 06/43] arm64: RME: Define the user ABI*

On 01/05/2025 14:31, Steven Price wrote:
> On 28/04/2025 09:58, Suzuki K Poulose wrote:
>> Hi Steven

>>
>> May be rephrase it to:

Looks good to me, cheers

Suzuki

---

## [77] Steven Price — 2025-05-01
*Subject: Re: [PATCH v8 07/43] arm64: RME: ioctls to create and configure
 realms*

On 29/04/2025 10:45, Suzuki K Poulose wrote:
> On 16/04/2025 14:41, Steven Price wrote:
>> Add the KVM_CAP_ARM_RME_CREATE_RD ioctl to create a realm. This involves

Agreed a comment makes sense. This is actually an open coded version of
"4 - stage2_pgtable_levels()" but using the RMM's page size (indeed
previous versions of the series did exactly that). There's already a
comment for stage2_pgtable_levels() explaining the concatenation.

>> +}
>> +

I honestly can't remember - will change ;)

>> +    unsigned int sl_ipa_bits = (levels + 1) * (RMM_PAGE_SHIFT - 3) +
>> +                   RMM_PAGE_SHIFT;

We could do, but there's no real point unless we also deal with leaking
only the pages which cannot be undelegated. Considering this is a
"should never happen" case I felt it was better to keep the code simple
and leak more than necessary. To me this feels like a "save everything
and reboot as soon as possible" sort of error condition - the kernel (or
RMM) has lost track of which pages are delegated and so a GPT fault
could be coming at any point. So it's better to play safe and be
pessimistic.

Thanks,
Steve

---

## [78] Steven Price — 2025-05-01
*Subject: Re: [PATCH v8 07/43] arm64: RME: ioctls to create and configure
 realms*

On 30/04/2025 06:39, Gavin Shan wrote:
> On 4/16/25 11:41 PM, Steven Price wrote:
[...]
>> diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
>> index 67cf2d94cb2d..dbb6521fe380 100644
[...]
>> +
>> +static int kvm_create_realm(struct kvm *kvm)

Ah, good spot - thanks!

Steve

---

## [79] Steven Price — 2025-05-01
*Subject: Re: [PATCH v8 15/43] arm64: RME: Allow VMM to set RIPAS*

On 30/04/2025 12:38, Gavin Shan wrote:
> On 4/16/25 11:41 PM, Steven Price wrote:
>> Each page within the protected region of the realm guest can be marked

Ack

>> +
>> +    if (!virt)

Thanks, that makes a lot of sense. I'd got myself rather confused about
whether this function could block or not. Somehow I'd completely missed
the may_block flag in __unmap_stage2_range().

>> +    unsigned long end = start + size;
>> +    struct realm *realm = &kvm->arch.realm;

Ack

>> +
>> +    realm_unmap_shared_range(kvm, find_map_level(realm, start, end),

I have to admit to quite liking 'continue' for retry loops, but in this
case your switch statement seems just as readable so I'll switch this.

>> +static int kvm_init_ipa_range_realm(struct kvm *kvm,
>> +                    struct arm_rme_init_ripas *args)

I agree we're different to smc_rtt_init_ripas(), but I don't really see
why we should prevent args->size==0. Calling the low level SMC in that
case would clearly be wrong (the kernel should be validating and that
would show a lack of validation), but we handle that with the while loop
in realm_init_ipa_state().

Do you think it's important to define this uAPI to disallow size==0?

>     if (end <= addr)
>         return -EINVAL;

This isn't the same - kvm_realm_is_create() is checking for
REALM_STATE_NONE, but we want to check for REALM_STATE_NEW.

Thanks,
Steve

>> +
>> +    return realm_init_ipa_state(realm, addr, end);

---

## [80] Suzuki K Poulose — 2025-05-01
*Subject: Re: [PATCH v8 11/43] arm64: RME: Allocate/free RECs to match vCPUs*

On 16/04/2025 14:41, Steven Price wrote:
> The RMM maintains a data structure known as the Realm Execution Context
> (or REC). It is similar to struct kvm_vcpu and tracks the state of the

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>


> ---
> Changes since v7:

[ Coming back to the top after a full review, feel free to ignore
the comments on the naming with non-4K support code. ]

minor nit: aux_phys_granule ? or even aux_granule ? "page" is confusing.

> +		bool should_free = true;
> +

minor nit: aux_[phys_]?granules ? as we are storing the granules here.

> +			 unsigned int num_aux)
> +{

same here, aux_granule

> +
> +		aux_page = alloc_page(GFP_KERNEL);

This is problematic. Realm->num_aux is number of AUX granules, not
num_aux_pages and can easily trigger overflow with non-4K. The 
alloc_rec_aux() is only allocating as many Pages required to cover
the num_aux granules.

I would say, simply drop the non-4K page support change, we can come
back to fixing the non-4K properly later, when we enable it.


Suzuki


> +out_undelegate_rmm_rec:
> +	if (WARN_ON(rmi_granule_undelegate(rec_page_phys)))

---

## [81] Suzuki K Poulose — 2025-05-01
*Subject: Re: [PATCH v8 12/43] KVM: arm64: vgic: Provide helper for number of
 list registers*

On 16/04/2025 14:41, Steven Price wrote:
> Currently the number of list registers available is stored in a global
> (kvm_vgic_global_state.nr_lr). With Arm CCA the RMM is permitted to

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>

---

## [82] Gavin Shan — 2025-05-02
*Subject: Re: [PATCH v8 39/43] arm64: RME: Provide register list for
 unfinalized RME RECs*

On 4/16/25 11:42 PM, Steven Price wrote:
> From: Jean-Philippe Brucker <jean-philippe@linaro.org>
> 

With below comment addressed.

Reviewed-by: Gavin Shan <gshan@redhat.com>

> diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
> index 4780e3af1bb9..eaa60ba6d97b 100644

KVM_REG_ARM64_SVE_VLS is exposed even SVE isn't finalized. See set_sve_vls() where
it's required that SVE isn't finalized, or -EPERM is returned. So this would be
something like below:

	if (!vcpu_has_sve(vcpu))
		return 0;

	if (!kvm_arm_vcpu_sve_finalized(vcpu))
		return 1;	/* KVM_REG_ARM64_SVE_VLS */

	return slices * (SVE_NUM_PREGS + SVE_NUM_ZREGS + 1 /* FFR */)
		+ 1; /* KVM_REG_ARM64_SVE_VLS */

> @@ -692,8 +689,8 @@ static int copy_sve_reg_indices(const struct kvm_vcpu *vcpu,
>   	if (!vcpu_has_sve(vcpu))

Since KVM_REG_ARM64_SVE_VLS can be exposed before the vCPU is finalized, it'd better to
move the check after the followup block where KVM_REG_ARM64_SVE_VLS index is copied
to user space.

	/*
          * Enumerate this first, so that userspace can save/restore in
          * the order reported by KVM_GET_REG_LIST:
          */
         reg = KVM_REG_ARM64_SVE_VLS;
         if (put_user(reg, uindices++))
                 return -EFAULT;
         ++num_regs;

	if (!kvm_arm_vcpu_sve_finalized(vcpu))
		return num_regs;

Thanks,
Gavin

---

## [83] Gavin Shan — 2025-05-02
*Subject: Re: [PATCH v8 40/43] arm64: RME: Provide accurate register list*

On 4/16/25 11:42 PM, Steven Price wrote:
> From: Jean-Philippe Brucker <jean-philippe@linaro.org>
> 

With below nitpicks addressed:

Reviewed-by: Gavin Shan <gshan@redhat.com>

> diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
> index 1288920fc73d..e9bb7647aa65 100644

static inline unsigned long num_timer_regs(struct kvm_vcpu *vcpu)

>   static int copy_timer_indices(struct kvm_vcpu *vcpu, u64 __user *uindices)
>   {

	for (unsigned long i = 0; ...)

> @@ -674,6 +677,9 @@ static unsigned long num_sve_regs(const struct kvm_vcpu *vcpu)
>   	if (!vcpu_has_sve(vcpu) || !kvm_arm_vcpu_sve_finalized(vcpu))

static inline unsigned int num_demux_regs(struct kvm_vcpu *vcpu)

> -static int write_demux_regids(u64 __user *uindices)
> +static int write_demux_regids(struct kvm_vcpu *vcpu, u64 __user *uindices)

static inline bool kvm_realm_sys_reg_hidden_user(const struct kvm_vcpu *vcpu, u64 reg)

>   static int walk_one_sys_reg(const struct kvm_vcpu *vcpu,
>   			    const struct sys_reg_desc *rd,

Thanks,
Gavin

---

## [84] Gavin Shan — 2025-05-02
*Subject: Re: [PATCH v8 15/43] arm64: RME: Allow VMM to set RIPAS*

On 5/2/25 2:00 AM, Steven Price wrote:
> On 30/04/2025 12:38, Gavin Shan wrote:
>> On 4/16/25 11:41 PM, Steven Price wrote:

.../...

>>> +static int kvm_init_ipa_range_realm(struct kvm *kvm,
>>> +                    struct arm_rme_init_ripas *args)

No, it's not a big deal since it's just a nitpick. The current implementation
isn't wrong because 0 will be returned when size is 0, meaning it succeeds
but no work to do there. Please leave the code as of being :)

>>      if (end <= addr)
>>          return -EINVAL;

Hmm, sorry for the noise. The current code is good enough then :)

Thanks,
Gavin

---

## [85] Gavin Shan — 2025-05-02
*Subject: Re: [PATCH v8 00/43] arm64: Support for Arm CCA in KVM*

On 4/16/25 11:41 PM, Steven Price wrote:

[...]

> 
> The ABI to the RMM (the RMI) is based on RMM v1.0-rel0 specification[1].

I got a chance to try the following combination, the guest can boot using
qemu/kvmtool except a RCU stall is observed (more details provided below)

host.tf-rmm      https://git.codelinaro.org/linaro/dcap/rmm.git                      (cca/v8)
host.edk2        git@github.com:tianocore/edk2.git                                   (edk2-stable202411)
host.tf-a        https://git.codelinaro.org/linaro/dcap/tf-a/trusted-firmware-a.git  (cca/v4)
host.qemu        https://git.qemu.org/git/qemu.git                                   (stable-9.2)
host.linux       https://git.gitlab.arm.com/linux-arm/linux-cca.git                  (cca-host/v8)
host.buildroot   https://github.com/buildroot/buildroot                              (master)
guest.qemu       https://git.codelinaro.org/linaro/dcap/qemu.git                     (cca/latest)
guest.kvmtool    https://gitlab.arm.com/linux-arm/kvmtool-cca                        (cca/latest)
guest.buildroot  https://github.com/buildroot/buildroot                              (master)

RCU stall report
----------------

[ 7816.381336] rcu: INFO: rcu_preempt self-detected stall on CPU
[ 7816.382816] rcu:     6-....: (5249 ticks this GP) idle=3a4c/1/0x4000000000000000 softirq=6001/6003 fqs=2624
[ 7816.384399] rcu:     (t=5250 jiffies g=29821 q=47 ncpus=8)
[ 7816.386059] CPU: 6 UID: 0 PID: 203 Comm: qemu-system-aar Not tainted 6.15.0-rc1-gavin-g78b23c56de79 #34 PREEMPT
[ 7816.387133] Hardware name: QEMU QEMU Virtual Machine, BIOS unknown 02/02/2022
[ 7816.387926] pstate: 61402009 (nZCv daif +PAN -UAO -TCO +DIT -SSBS BTYPE=--)
[ 7816.388678] pc : realm_unmap_private_range+0x19c/0x2c0
[ 7816.389878] lr : realm_unmap_private_range+0x94/0x2c0
[ 7816.390388] sp : ffff80008095bb60
[ 7816.390765] x29: ffff80008095bb60 x28: 000000007caef000 x27: ffffba3322764000
[ 7816.392321] x26: 00007fffffffffff x25: 000000007caf0000 x24: 0001000000000000
[ 7816.393168] x23: 00000000c4000155 x22: ffff8000801b5e98 x21: 0000000106481000
[ 7816.393999] x20: 000000007caef000 x19: 0000000000000000 x18: 0000000000000000
[ 7816.394833] x17: 0000000000000000 x16: 0000000000000000 x15: 0000ffff8e997058
[ 7816.395668] x14: 0000000000000000 x13: 0000000000000000 x12: 0000000000000000
[ 7816.396548] x11: 0000000038e38e39 x10: 0000000000000004 x9 : ffffba33218a2564
[ 7816.397419] x8 : ffff8000801b5e98 x7 : 000000003fffffff x6 : 0000000000000001
[ 7816.398243] x5 : 000000011e795000 x4 : 0000000000000002 x3 : 0000000000000000
[ 7816.399062] x2 : 000000007caf0000 x1 : 000000011e796000 x0 : 0000000000000000
[ 7816.400021] Call trace:
[ 7816.400604]  realm_unmap_private_range+0x19c/0x2c0 (P)
[ 7816.401347]  kvm_realm_unmap_range+0x94/0xb0
[ 7816.401894]  __unmap_stage2_range+0x70/0xa0
[ 7816.402421]  kvm_arch_post_set_memory_attributes+0x68/0xa8
[ 7816.403011]  kvm_vm_ioctl+0x6bc/0x1b58
[ 7816.403509]  __arm64_sys_ioctl+0xa4/0xe8
[ 7816.404020]  invoke_syscall+0x50/0x120
[ 7816.404562]  el0_svc_common.constprop.0+0x48/0xf0
[ 7816.405113]  do_el0_svc+0x24/0x38
[ 7816.405584]  el0_svc+0x34/0xf0
[ 7816.406045]  el0t_64_sync_handler+0x10c/0x138
[ 7816.406571]  el0t_64_sync+0x1ac/0x1b0

Thanks,
Gavin

---

## [86] Suzuki K Poulose — 2025-05-02
*Subject: Re: [PATCH v8 13/43] arm64: RME: Support for the VGIC in realms*

On 16/04/2025 14:41, Steven Price wrote:
> The RMM provides emulation of a VGIC to the realm guest but delegates
> much of the handling to the host. Implement support in KVM for

We also need to save/restore gicv3_hcr/cpuif->vgic_hcr.

> +
>   static inline void vgic_save_state(struct kvm_vcpu *vcpu)


>   		if (has_vhe() && static_branch_unlikely(&kvm_vgic_global_state.gicv3_cpuif))
>   			__vgic_v3_activate_traps(&vcpu->arch.vgic_cpu.vgic_v3);

We could return early here for rec, and skip the unnecessary trap steps. 
Similar for the vgic_load case.

Rest looks good to me.

Suzuki


>   		return;

---

## [87] Suzuki K Poulose — 2025-05-02
*Subject: Re: [PATCH v8 14/43] KVM: arm64: Support timers in realm RECs*

On 16/04/2025 14:41, Steven Price wrote:
> The RMM keeps track of the timer while the realm REC is running, but on
> exit to the normal world KVM is responsible for handling the timers.

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>

---

## [88] Suzuki K Poulose — 2025-05-06
*Subject: Re: [PATCH v8 15/43] arm64: RME: Allow VMM to set RIPAS*

Hi Steven

On 16/04/2025 14:41, Steven Price wrote:
> Each page within the protected region of the realm guest can be marked
> as either RAM or EMPTY. Allow the VMM to control this before the guest

> +
> +static phys_addr_t alloc_delegated_granule(struct kvm_mmu_memory_cache *mc)


> +	kvm_account_pgtable_pages(virt, 1);

Could we delay this to the place where we actually use it ? Otherwise
we may get the accounting wrong, if e.g, free it using
free_delegated_granule() ? Also, the name doesn't suggest that
we are allocating an rtt (though it accepts a memory_cache for rtts).


> +
> +	return phys;

minor nit: Should we align "addr" to level - 1, similar to what we do
for rtt_create, just to be consistent and safer ?

> +
> +	if (RMI_RETURN_STATUS(ret) == RMI_SUCCESS && rtt_granule)

Can we race with another thread ? If so, we may need to do an rtt read
to confirm if we are safe to retry and ignore the failure.

> +			free_delegated_granule(rtt);
> +			return -ENXIO;

minor nit: I am wondering, if we should add a new wrapper for warn_on, 
which also dumps the RTT entry and the operation that caused the WARNING 
? Might be useful to debug and pin point issues. We have several cases
where this might be used.

> +		return -ENXIO;
> +	}

nit: If this non-4K host, then, we may want to ALIGN_DOWN(out_rtt, 
PAGE_SIZE) ?

> +
> +	return 0;

For the record, as Aneesh pointed out offline, this must be level - 1,
as rtt_create only walks to level - 1.

> +			/* The RTT already exists, continue */
> +			continue;

Do we need yielding CPU here, similar to the shared case ? It may be 
difficult (not impossible) to define a check point to do that.


> +	}
> +

We don't seem to be reclaiing the RTTs from shared mapping case ?

> +}
> +

I am wondering if WARN_ON() is required here. A buggy VMM could trigger
the WARN_ON(). (e.g, INIT_IPA after POPULATE, where L3 table is
created.). The only case where it may be worth WARNING is if the level == 3.

Suzuki



> +				return -ENXIO;
> +

---

## [89] Suzuki K Poulose — 2025-05-07
*Subject: Re: [PATCH v8 16/43] arm64: RME: Handle realm enter/exit*

On 16/04/2025 14:41, Steven Price wrote:
> Entering a realm is done using a SMC call to the RMM. On exit the
> exit-codes need to be handled slightly differently to the normal KVM

minor nit: Looks like we loose the kvm_exit trace. Could we add
something in handle_rec_exit ?
>   
>   		preempt_enable();

Do we need to set the RMI_REJECT for run->enter.flags 
REC_ENTER_FLAG_RIPAS_RESPONSE ?

Rest looks fine to me.

Suzuki

---

## [90] Suzuki K Poulose — 2025-05-07
*Subject: Re: [PATCH v8 17/43] arm64: RME: Handle RMI_EXIT_RIPAS_CHANGE*

On 16/04/2025 14:41, Steven Price wrote:
> The guest can request that a region of it's protected address space is
> switched between RIPAS_RAM and RIPAS_EMPTY (and back) using

minor nit: Do we need to add a comment here, saying, we stop processing
the request if we run out of RTT pages in this go and Realm could retry
it.

> +				if (!ret)
> +					continue;

minor nit: Following from Gavin's comment on another patch, could
switch() make the above code more readable and remove the continue; ?

		switch (RMI_RETURN_STATUS(ret)) {
		case RMI_SUCCESS:
			ipa = next;
			break;
		case RMI_ERROR_RTT: {

		
		}
			break;
		default:
			WARN(..);
			ret = -ENXIO;
			goto out;
		}

I am fine either way.

> +	}
> +

out:

> +	*top_ipa = ipa;
> +

Rest looks good to me.

Suzuki

---
