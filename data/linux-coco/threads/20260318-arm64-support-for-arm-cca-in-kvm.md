---
title: 'arm64: Support for Arm CCA in KVM'
date: 2026-03-18
last_reply: 2026-04-22
message_count: 133
participants: ['Steven Price', 'Joey Gouly', 'Suzuki K Poulose', 'Wei-Lin Chang', 'Mathieu Poirier', 'Marc Zyngier', 'Gavin Shan', 'Alper Gun', 'Jiahao zheng']
---

## [1] Steven Price — 2026-03-18

This series adds support for running protected VMs using KVM under the
Arm Confidential Compute Architecture (CCA).

New major version number! This now targets RMM v2.0-bet0[1]. And unlike
for Linux this represents a significant change.

RMM v2.0 brings with it the ability to configure the RMM to have the
same page size as the host (so no more RMM_PAGE_SIZE and dealing with
granules being different from host pages). It also introduces range
based APIs for many operations which should be more efficient and
simplifies the code in places.

The handling of the GIC has changed, so the system registers are used to
pass the GIC state rather than memory. This means fewer changes to the
KVM code as it looks much like a normal VM in this respect.

And of course the new uAPI introduced in the previous v12 posting is
retained so that also remains simplified compared to earlier postings.

The RMM support for v2.0 is still early and so this series includes a
few hacks to ease the integration. Of note are that there are some RMM
v1.0 SMCs added to paper over areas where the RMM implementation isn't
quite ready for v2.0, and "SROs" (see below) are deferred to the final
patch in the series.

The PMU in RMM v2.0 requires more handling on the RMM-side (and
therefore simplifies the implementation on Linux), but this isn't quite
ready yet. The Linux side is implemented (but untested).

PSCI still requires the VMM to provide the "target" REC for operations
that affect another vCPU. This is likely to change in a future version
of the specification. There's also a desire to force PSCI to be handled
in the VMM for realm guests - this isn't implemented yet as I'm waiting
for the dust to settle on the RMM interface first.

Stateful RMI Operations
-----------------------

The RMM v2.0 spec brings a new concept of Stateful RMI Operations (SROs)
which allow the RMM to complete an operation over several SMC calls and
requesting/returning memory to the host. This has the benefit of
allowing interrupts to be handled in the middle of an operation (by
returning to the host to handle the interrupt without completing the
operation) and enables the RMM to dynamically allocate memory for
internal tracking purposes. One example of this is RMI_REC_CREATE no
longer needs "auxiliary granules" provided upfront but can request the
memory needed during the RMI_REC_CREATE operation.

There are a fairly large number of operations that are defined as SROs
in the specification, but current both Linux and RMM only have support
for RMI_REC_CREATE and RMI_REC_DESTROY. There a number of TODOs/FIXMEs
in the code where support is missing.

Given the early stage support for this, the SRO handling is all confined
to the final patch. This patch can be dropped to return to a pre-SRO
state (albeit a mixture of RMM v1.0 and v2.0 APIs) for testing purposes.

A future posting will reorder the series to move the generic SRO support
to an early patch and will implement the proper support for this in all
RMI SMCs.

One aspect of SROs which is not yet well captured is that in some
circumstances the Linux kernel will need to call an SRO call in a
context where memory allocation is restricted (e.g. because a spinlock
is held). In this case the intention is that the SRO will be cancelled,
the spinlock dropped so the memory allocation can be completed, and then
the SRO restarted (obviously after rechecking the state that the
spinlock was protecting). For this reason the code stores the memory
allocations within a struct rmi_sro_state object - see the final patch
for more details.

This series is based on v7.0-rc1. It is also available as a git
repository:

https://gitlab.arm.com/linux-arm/linux-cca cca-host/v13

Work in progress changes for kvmtool are available from the git
repository below:

https://gitlab.arm.com/linux-arm/kvmtool-cca cca/v11

Note that the kvmtool code has been tidied up (thanks to Suzuki) and
this involves a minor change in flags. The "--restricted_mem" flag is no
longer recognised (or necessary).

The TF-RMM has not yet merged the RMMv2.0 support, so you will need to
use the following branch:

https://git.trustedfirmware.org/TF-RMM/tf-rmm.git topics/rmm-v2.0-poc

[1] https://developer.arm.com/documentation/den0137/2-0bet0/

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

Steven Price (36):
  kvm: arm64: Avoid including linux/kvm_host.h in kvm_pgtable.h
  arm64: RME: Handle Granule Protection Faults (GPFs)
  arm64: RMI: Add SMC definitions for calling the RMM
  arm64: RMI: Temporarily add SMCs from RMM v1.0 spec
  arm64: RMI: Add wrappers for RMI calls
  arm64: RMI: Check for RMI support at KVM init
  arm64: RMI: Configure the RMM with the host's page size
  arm64: RMI: Check for LPA2 support
  arm64: RMI: Ensure that the RMM has GPT entries for memory
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
  arm64: Don't expose stolen time for realm guests
  arm64: RMI: Always use 4k pages for realms
  arm64: RMI: Prevent Device mappings for Realms
  arm64: RMI: Enable PMU support with a realm guest
  KVM: arm64: Expose KVM_ARM_VCPU_REC to user space
  arm64: RMI: Enable realms to be created
  [WIP] arm64: RMI: Add support for SRO

Suzuki K Poulose (3):
  kvm: arm64: Include kvm_emulate.h in kvm/arm_psci.h
  kvm: arm64: Don't expose unsupported capabilities for realm guests
  arm64: RMI: Allow checking SVE on VM instance

 Documentation/virt/kvm/api.rst       |   86 +-
 arch/arm64/include/asm/kvm_emulate.h |   31 +
 arch/arm64/include/asm/kvm_host.h    |   15 +-
 arch/arm64/include/asm/kvm_pgtable.h |    5 +-
 arch/arm64/include/asm/kvm_pkvm.h    |    2 +-
 arch/arm64/include/asm/kvm_rmi.h     |  129 ++
 arch/arm64/include/asm/rmi_cmds.h    |  692 +++++++++
 arch/arm64/include/asm/rmi_smc.h     |  430 ++++++
 arch/arm64/include/asm/virt.h        |    1 +
 arch/arm64/kernel/cpufeature.c       |    1 +
 arch/arm64/kvm/Kconfig               |    2 +
 arch/arm64/kvm/Makefile              |    2 +-
 arch/arm64/kvm/arch_timer.c          |   28 +-
 arch/arm64/kvm/arm.c                 |  178 ++-
 arch/arm64/kvm/guest.c               |   95 +-
 arch/arm64/kvm/hyp/pgtable.c         |    1 +
 arch/arm64/kvm/hypercalls.c          |    4 +-
 arch/arm64/kvm/inject_fault.c        |    5 +-
 arch/arm64/kvm/mmio.c                |   16 +-
 arch/arm64/kvm/mmu.c                 |  214 ++-
 arch/arm64/kvm/pmu-emul.c            |    6 +
 arch/arm64/kvm/psci.c                |   30 +
 arch/arm64/kvm/reset.c               |   13 +-
 arch/arm64/kvm/rmi-exit.c            |  207 +++
 arch/arm64/kvm/rmi.c                 | 1948 ++++++++++++++++++++++++++
 arch/arm64/kvm/sys_regs.c            |   53 +-
 arch/arm64/kvm/vgic/vgic-init.c      |    2 +-
 arch/arm64/mm/fault.c                |   28 +-
 include/kvm/arm_arch_timer.h         |    2 +
 include/kvm/arm_pmu.h                |    4 +
 include/kvm/arm_psci.h               |    2 +
 include/uapi/linux/kvm.h             |   41 +-
 32 files changed, 4176 insertions(+), 97 deletions(-)
 create mode 100644 arch/arm64/include/asm/kvm_rmi.h
 create mode 100644 arch/arm64/include/asm/rmi_cmds.h
 create mode 100644 arch/arm64/include/asm/rmi_smc.h
 create mode 100644 arch/arm64/kvm/rmi-exit.c
 create mode 100644 arch/arm64/kvm/rmi.c

---

## [2] Steven Price — 2026-03-18
*Subject: [PATCH v13 01/48] kvm: arm64: Include kvm_emulate.h in kvm/arm_psci.h*

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

## [3] Steven Price — 2026-03-18
*Subject: [PATCH v13 02/48] kvm: arm64: Avoid including linux/kvm_host.h in kvm_pgtable.h*

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
index c201168f2857..f3fe85cebdf1 100644
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
index 757076ad4ec9..3a2480e269e6 100644
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
index 0e4ddd28ef5d..e2a3a52b163e 100644
--- a/arch/arm64/kvm/hyp/pgtable.c
+++ b/arch/arm64/kvm/hyp/pgtable.c
@@ -8,6 +8,7 @@
  */
 
 #include <linux/bitfield.h>
+#include <linux/kvm_host.h>
 #include <asm/kvm_pgtable.h>
 #include <asm/stage2_pgtable.h>

---

## [4] Steven Price — 2026-03-18
*Subject: [PATCH v13 03/48] arm64: RME: Handle Granule Protection Faults (GPFs)*

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

## [5] Steven Price — 2026-03-18
*Subject: [PATCH v13 04/48] arm64: RMI: Add SMC definitions for calling the RMM*

The RMM (Realm Management Monitor) provides functionality that can be
accessed by SMC calls from the host.

The SMC definitions are based on DEN0137[1] version 2.0-bet0

[1] https://developer.arm.com/documentation/den0137/2-0bet0/

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/include/asm/rmi_smc.h | 432 +++++++++++++++++++++++++++++++
 1 file changed, 432 insertions(+)
 create mode 100644 arch/arm64/include/asm/rmi_smc.h

diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
new file mode 100644
index 000000000000..8a42b83218f8
--- /dev/null
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -0,0 +1,432 @@
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
+#define SMC_RMI_ATTEST_PLAT_TOKEN_REFRESH	SMC_RMI_CALL(0x0170)
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
+#define SMC_RMI_VDEV_P2P_BIND			SMC_RMI_CALL(0x01d4)
+#define SMC_RMI_VDEV_P2P_UNBIND			SMC_RMI_CALL(0x01d5)
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
+#define SMC_RMI_CMEM_ADD_PDEV			SMC_RMI_CALL(0x01e4)
+#define SMC_RMI_CMEM_CREATE			SMC_RMI_CALL(0x01e5)
+#define SMC_RMI_CMEM_DESTROY			SMC_RMI_CALL(0x01e6)
+#define SMC_RMI_CMEM_POPULATE			SMC_RMI_CALL(0x01e7)
+#define SMC_RMI_CMEM_REMOTE_PDEV		SMC_RMI_CALL(0x01e8)
+#define SMC_RMI_CMEM_START			SMC_RMI_CALL(0x01e9)
+#define SMC_RMI_CMEM_STOP			SMC_RMI_CALL(0x01ea)
+#define SMC_RMI_CMEM_UNPOPULATE			SMC_RMI_CALL(0x01eb)
+#define SMC_RMI_RMM_CONFIG_GET			SMC_RMI_CALL(0x01ec)
+#define SMC_RMI_PDEV_MEC_UPDATE			SMC_RMI_CALL(0x01ed)
+#define SMC_RMI_VSMMU_EVENT_COMPLETE		SMC_RMI_CALL(0x01ee)
+
+#define SMC_RMI_PSMMU_EVENT_DISCARD		SMC_RMI_CALL(0x01f0)
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
+#define SMC_RMI_RTT_AUX_UNMAP_UNMAP		SMC_RMI_CALL(0x0200)
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
+#define SMC_RMI_PDEV_SET_PROT			SMC_RMI_CALL(0x020b)
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
+#define RMI_RETURN_CANCANCEL(ret)	(((ret) >> 10) & 0x1)
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
+#define RMI_ADDR_RANGE_SIZE(ar)		(FIELD_GET(GENMASK(1, 0), (ar)))
+#define RMI_ADDR_RANGE_COUNT(ar)	(FIELD_GET(GENMASK(PAGE_SHIFT - 1, 2), \
+						   (ar)))
+#define RMI_ADDR_RANGE_ADDR(ar)		((ar) & PAGE_MASK & GENMASK(51, 0))
+#define RMI_ADDR_RANGE_STATE(ar)	(FIELD_GET(BIT(63), (ar)))
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
+#define RMI_FEATURE_REGISTER_2_MAX_VDEVS_ORDER	GEN_MASK(7, 4)
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
+		};
+		u8 padding0[0x400];
+	};
+	union { /* 0x400 */
+		u8 rpv[64];
+		u8 padding1[0x400];
+	};
+	union { /* 0x800 */
+		struct {
+			u64 padding;
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
+#endif /* __ASM_RMI_SMC_H */

---

## [6] Steven Price — 2026-03-18
*Subject: [PATCH v13 05/48] arm64: RMI: Temporarily add SMCs from RMM v1.0 spec*

Not all the functionality has been migrated to the v2.0 specification,
so for now we still rely on some v1.0 SMCs. This mixture is not
spec-compliant, but is necessary until an updated RMM is available.

Signed-off-by: Steven Price <steven.price@arm.com>
---
New patch in v13
---
 arch/arm64/include/asm/rmi_smc.h | 5 +++--
 1 file changed, 3 insertions(+), 2 deletions(-)

diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 8a42b83218f8..049d71470486 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -30,14 +30,15 @@
 #define SMC_RMI_REC_ENTER			SMC_RMI_CALL(0x015c)
 #define SMC_RMI_RTT_CREATE			SMC_RMI_CALL(0x015d)
 #define SMC_RMI_RTT_DESTROY			SMC_RMI_CALL(0x015e)
+#define SMC_RMI_RTT_MAP_UNPROTECTED		SMC_RMI_CALL(0x015f) //
 
 #define SMC_RMI_RTT_READ_ENTRY			SMC_RMI_CALL(0x0161)
-
+#define SMC_RMI_RTT_UNMAP_UNPROTECTED		SMC_RMI_CALL(0x0162) //
 #define SMC_RMI_RTT_DEV_VALIDATE		SMC_RMI_CALL(0x0163)
 #define SMC_RMI_PSCI_COMPLETE			SMC_RMI_CALL(0x0164)
 #define SMC_RMI_FEATURES			SMC_RMI_CALL(0x0165)
 #define SMC_RMI_RTT_FOLD			SMC_RMI_CALL(0x0166)
-
+#define SMC_RMI_REC_AUX_COUNT			SMC_RMI_CALL(0x0167) //
 #define SMC_RMI_RTT_INIT_RIPAS			SMC_RMI_CALL(0x0168)
 #define SMC_RMI_RTT_SET_RIPAS			SMC_RMI_CALL(0x0169)
 #define SMC_RMI_VSMMU_CREATE			SMC_RMI_CALL(0x016a)

---

## [7] Steven Price — 2026-03-18
*Subject: [PATCH v13 06/48] arm64: RMI: Add wrappers for RMI calls*

The wrappers make the call sites easier to read and deal with the
boiler plate of handling the error codes from the RMM.

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/include/asm/rmi_cmds.h | 699 ++++++++++++++++++++++++++++++
 1 file changed, 699 insertions(+)
 create mode 100644 arch/arm64/include/asm/rmi_cmds.h

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
new file mode 100644
index 000000000000..9c4f83644a61
--- /dev/null
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -0,0 +1,699 @@
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
+ * rmi_rmm_config_get() - Get the system configuration
+ * @cfg_ptr: PA of a struct rmm_config
+ *
+ * Gets the system configuration
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rmm_config_get(unsigned long cfg_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RMM_CONFIG_GET, cfg_ptr, &res);
+
+	return res.a0;
+}
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
+ * @addr: PA of the tracking region
+ * @out_category: Memory category
+ * @out_state: Tracking region state
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_granule_tracking_get(unsigned long addr,
+					   unsigned long *out_category,
+					   unsigned long *out_state)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_GRANULE_TRACKING_GET, addr, &res);
+
+	if (out_category)
+		*out_category = res.a1;
+	if (out_state)
+		*out_state = res.a2;
+
+	return res.a0;
+}
+
+/**
+ * rmi_granule_tracking_set() - Set configuration of a Granule tracking region
+ * @addr: PA of the tracking region
+ * @category: Memory category
+ * @state: Tracking region state
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_granule_tracking_set(unsigned long addr,
+					   unsigned long category,
+					   unsigned long state)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_GRANULE_TRACKING_SET, addr, category,
+			     state, &res);
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
+ * rmi_gpt_l1_destroy() - Destroy a Level 1 GPT
+ * @addr: Base of physical address region descripted by the L1GPT
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_gpt_l1_destroy(unsigned long addr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_GPT_L1_DESTROY, addr, &res);
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

## [8] Steven Price — 2026-03-18
*Subject: [PATCH v13 07/48] arm64: RMI: Check for RMI support at KVM init*

Query the RMI version number and check if it is a compatible version. A
static key is also provided to signal that a supported RMM is available.

Functions are provided to query if a VM or VCPU is a realm (or rec)
which currently will always return false.

Later patches make use of struct realm and the states as the ioctls
interfaces are added to support realm and REC creation and destruction.

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/include/asm/kvm_emulate.h | 18 +++++++++
 arch/arm64/include/asm/kvm_host.h    |  4 ++
 arch/arm64/include/asm/kvm_rmi.h     | 56 +++++++++++++++++++++++++++
 arch/arm64/include/asm/virt.h        |  1 +
 arch/arm64/kernel/cpufeature.c       |  1 +
 arch/arm64/kvm/Makefile              |  2 +-
 arch/arm64/kvm/arm.c                 |  5 +++
 arch/arm64/kvm/rmi.c                 | 57 ++++++++++++++++++++++++++++
 8 files changed, 143 insertions(+), 1 deletion(-)
 create mode 100644 arch/arm64/include/asm/kvm_rmi.h
 create mode 100644 arch/arm64/kvm/rmi.c

diff --git a/arch/arm64/include/asm/kvm_emulate.h b/arch/arm64/include/asm/kvm_emulate.h
index 5bf3d7e1d92c..f38b50151ce8 100644
--- a/arch/arm64/include/asm/kvm_emulate.h
+++ b/arch/arm64/include/asm/kvm_emulate.h
@@ -688,4 +688,22 @@ static inline void vcpu_set_hcrx(struct kvm_vcpu *vcpu)
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
+static inline bool vcpu_is_rec(struct kvm_vcpu *vcpu)
+{
+	return false;
+}
+
 #endif /* __ARM64_KVM_EMULATE_H__ */
diff --git a/arch/arm64/include/asm/kvm_host.h b/arch/arm64/include/asm/kvm_host.h
index 5d5a3bbdb95e..9267a2f2d65b 100644
--- a/arch/arm64/include/asm/kvm_host.h
+++ b/arch/arm64/include/asm/kvm_host.h
@@ -27,6 +27,7 @@
 #include <asm/fpsimd.h>
 #include <asm/kvm.h>
 #include <asm/kvm_asm.h>
+#include <asm/kvm_rmi.h>
 #include <asm/vncr_mapping.h>
 
 #define __KVM_HAVE_ARCH_INTC_INITIALIZED
@@ -405,6 +406,9 @@ struct kvm_arch {
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
index c31f8e17732a..ddf7e57f23e8 100644
--- a/arch/arm64/kernel/cpufeature.c
+++ b/arch/arm64/kernel/cpufeature.c
@@ -289,6 +289,7 @@ static const struct arm64_ftr_bits ftr_id_aa64isar3[] = {
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
index 29f0326f7e00..274d7866efdc 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -39,6 +39,7 @@
 #include <asm/kvm_nested.h>
 #include <asm/kvm_pkvm.h>
 #include <asm/kvm_ptrauth.h>
+#include <asm/kvm_rmi.h>
 #include <asm/sections.h>
 #include <asm/stacktrace/nvhe.h>
 
@@ -104,6 +105,8 @@ long kvm_get_cap_for_kvm_ioctl(unsigned int ioctl, long *ext)
 	return -EINVAL;
 }
 
+DEFINE_STATIC_KEY_FALSE(kvm_rmi_is_available);
+
 DECLARE_KVM_HYP_PER_CPU(unsigned long, kvm_hyp_vector);
 
 DEFINE_PER_CPU(unsigned long, kvm_arm_hyp_stack_base);
@@ -2921,6 +2924,8 @@ static __init int kvm_arm_init(void)
 
 	in_hyp_mode = is_kernel_in_hyp_mode();
 
+	kvm_init_rmi();
+
 	if (cpus_have_final_cap(ARM64_WORKAROUND_DEVICE_LOAD_ACQUIRE) ||
 	    cpus_have_final_cap(ARM64_WORKAROUND_1508412))
 		kvm_info("Guests without required CPU erratum workarounds can deadlock system!\n" \
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
new file mode 100644
index 000000000000..fac151580c01
--- /dev/null
+++ b/arch/arm64/kvm/rmi.c
@@ -0,0 +1,57 @@
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
+	/* Continue without realm support if we can't agree on a version */
+	if (rmi_check_version())
+		return;
+
+	/* Future patch will enable static branch kvm_rmi_is_available */
+}

---

## [9] Steven Price — 2026-03-18
*Subject: [PATCH v13 08/48] arm64: RMI: Configure the RMM with the host's page size*

RMM v2.0 brings the ability to set the RMM's granule size. Read the
feature registers and configure the RMM so that it matches the host's
page size. This means that operations can be done with a granulatity
equal to PAGE_SIZE.

Signed-off-by: Steven Price <steven.price@arm.com>
---
New patch for v13
---
 arch/arm64/kvm/rmi.c | 50 ++++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 50 insertions(+)

diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index fac151580c01..482dc542451a 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -8,6 +8,9 @@
 #include <asm/rmi_cmds.h>
 #include <asm/virt.h>
 
+static unsigned long rmm_feat_reg0;
+static unsigned long rmm_feat_reg1;
+
 static int rmi_check_version(void)
 {
 	struct arm_smccc_res res;
@@ -47,11 +50,58 @@ static int rmi_check_version(void)
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
+		kvm_err("Unsupported PAGE_SIZE for RMM\n");
+		return -EINVAL;
+	}
+
+	ret = rmi_rmm_config_set(virt_to_phys(config));
+	if (ret) {
+		kvm_err("RMM config set failed\n");
+		return -EINVAL;
+	}
+
+	ret = rmi_rmm_activate();
+	if (ret) {
+		kvm_err("RMM activate failed\n");
+		return -ENXIO;
+	}
+
+	return 0;
+}
+
 void kvm_init_rmi(void)
 {
 	/* Continue without realm support if we can't agree on a version */
 	if (rmi_check_version())
 		return;
 
+	if (WARN_ON(rmi_features(0, &rmm_feat_reg0)))
+		return;
+	if (WARN_ON(rmi_features(1, &rmm_feat_reg1)))
+		return;
+
+	if (rmi_configure())
+		return;
+
 	/* Future patch will enable static branch kvm_rmi_is_available */
 }

---

## [10] Steven Price — 2026-03-18
*Subject: [PATCH v13 09/48] arm64: RMI: Check for LPA2 support*

If KVM has enabled LPA2 support then check that the RMM also supports
it. If there is a mismatch then disable support for realm guests as the
VMM may attempt to create a guest which is incompatible with the RMM.

Signed-off-by: Steven Price <steven.price@arm.com>
---
New patch for v13
---
 arch/arm64/kvm/rmi.c | 18 ++++++++++++++++++
 1 file changed, 18 insertions(+)

diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 482dc542451a..9590dff9a2c1 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -5,12 +5,18 @@
 
 #include <linux/kvm_host.h>
 
+#include <asm/kvm_pgtable.h>
 #include <asm/rmi_cmds.h>
 #include <asm/virt.h>
 
 static unsigned long rmm_feat_reg0;
 static unsigned long rmm_feat_reg1;
 
+static bool rmi_has_feature(unsigned long feature)
+{
+	return !!u64_get_bits(rmm_feat_reg0, feature);
+}
+
 static int rmi_check_version(void)
 {
 	struct arm_smccc_res res;
@@ -89,6 +95,16 @@ static int rmi_configure(void)
 	return 0;
 }
 
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
 	/* Continue without realm support if we can't agree on a version */
@@ -100,6 +116,8 @@ void kvm_init_rmi(void)
 	if (WARN_ON(rmi_features(1, &rmm_feat_reg1)))
 		return;
 
+	if (rmm_check_features())
+		return;
 	if (rmi_configure())
 		return;

---

## [11] Steven Price — 2026-03-18
*Subject: [PATCH v13 10/48] arm64: RMI: Ensure that the RMM has GPT entries for memory*

The RMM may not be tracking all the memory of the system at boot. Create
the necessary tracking state and GPTs within the RMM so that all boot
memory can be delegated to the RMM as needed during runtime.

Note: support is currently missing for SROs which means that if the RMM
needs memory donating this will fail (and render CCA unusable in Linux).

Signed-off-by: Steven Price <steven.price@arm.com>
---
New patch for v13
---
 arch/arm64/kvm/rmi.c | 89 ++++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 89 insertions(+)

diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 9590dff9a2c1..80aedc85e94a 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -4,6 +4,7 @@
  */
 
 #include <linux/kvm_host.h>
+#include <linux/memblock.h>
 
 #include <asm/kvm_pgtable.h>
 #include <asm/rmi_cmds.h>
@@ -56,6 +57,18 @@ static int rmi_check_version(void)
 	return 0;
 }
 
+/*
+ * These are the 'default' sizes when passing 0 as the tracking_region_size.
+ * TODO: Support other granule sizes
+ */
+#ifdef CONFIG_PAGE_SIZE_4KB
+#define RMM_GRANULE_TRACKING_SIZE	SZ_1G
+#elif defined(CONFIG_PAGE_SIZE_16KB)
+#define RMM_GRANULE_TRACKING_SIZE	SZ_32M
+#elif defined(CONFIG_PAGE_SIZE_64KB)
+#define RMM_GRANULE_TRACKING_SIZE	SZ_512M
+#endif
+
 static int rmi_configure(void)
 {
 	struct rmm_config *config __free(free_page) = NULL;
@@ -95,6 +108,80 @@ static int rmi_configure(void)
 	return 0;
 }
 
+static int rmi_verify_memory_tracking(phys_addr_t start, phys_addr_t end)
+{
+	start = ALIGN_DOWN(start, RMM_GRANULE_TRACKING_SIZE);
+	end = ALIGN(end, RMM_GRANULE_TRACKING_SIZE);
+
+	while (start < end) {
+		unsigned long ret, category, state;
+
+		ret = rmi_granule_tracking_get(start, &category, &state);
+		if (ret != RMI_SUCCESS ||
+		    state != RMI_TRACKING_FINE ||
+		    category != RMI_MEM_CATEGORY_CONVENTIONAL) {
+			/* TODO: Set granule tracking in this case */
+			kvm_err("Granule tracking for region isn't fine/conventional: %llx",
+				start);
+			return -ENODEV;
+		}
+		start += RMM_GRANULE_TRACKING_SIZE;
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
+		if (ret && ret != RMI_ERROR_GPT) {
+			/*
+			 * FIXME: Handle SRO so that memory can be donated for
+			 * the tables.
+			 */
+			kvm_err("GPT Level1 table missing for %llx\n", start);
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
 static int rmm_check_features(void)
 {
 	if (kvm_lpa2_is_enabled() && !rmi_has_feature(RMI_FEATURE_REGISTER_0_LPA2)) {
@@ -120,6 +207,8 @@ void kvm_init_rmi(void)
 		return;
 	if (rmi_configure())
 		return;
+	if (rmi_init_metadata())
+		return;
 
 	/* Future patch will enable static branch kvm_rmi_is_available */
 }

---

## [12] Steven Price — 2026-03-18
*Subject: [PATCH v13 11/48] arm64: RMI: Define the user ABI*

There is one CAP which identified the presence of CCA, and two ioctls.
One ioctl is used to populate memory and the other is used when user
space is providing the PSCI implementation to identify the target of the
operation.

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 Documentation/virt/kvm/api.rst | 65 ++++++++++++++++++++++++++++++++++
 include/uapi/linux/kvm.h       | 22 ++++++++++++
 2 files changed, 87 insertions(+)

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index fc5736839edd..72a2ce96d1ba 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -6553,6 +6553,62 @@ KVM_S390_KEYOP_SSKE
   Sets the storage key for the guest address ``guest_addr`` to the key
   specified in ``key``, returning the previous value in ``key``.
 
+4.145 KVM_ARM_VCPU_RMI_PSCI_COMPLETE
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
+4.146 KVM_ARM_RMI_POPULATE
+--------------------------
+
+:Capability: KVM_CAP_ARM_RMI
+:Architectures: arm64
+:Type: vm ioctl
+:Parameters: struct kvm_arm_rmi_populate (in)
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
+entire region and updates the fields `base`, `size` and `source_uaddr`. User
+space may have to repeatedly call it until `size` is 0 to populate the entire
+region.
+
+`flags` can be set to `KVM_ARM_RMI_POPULATE_FLAGS_MEASURE` to request that the
+populated data is hashed and added to the guest's Realm Initial Measurement
+(RIM).
+
 .. _kvm_run:
 
 5. The kvm_run structure
@@ -8896,6 +8952,15 @@ helpful if user space wants to emulate instructions which are not
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
index 65500f5db379..6ec140ab0ed1 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -985,6 +985,7 @@ struct kvm_enable_cap {
 #define KVM_CAP_ARM_SEA_TO_USER 245
 #define KVM_CAP_S390_USER_OPEREXEC 246
 #define KVM_CAP_S390_KEYOP 247
+#define KVM_CAP_ARM_RMI 248
 
 struct kvm_irq_routing_irqchip {
 	__u32 irqchip;
@@ -1650,4 +1651,25 @@ struct kvm_pre_fault_memory {
 	__u64 padding[5];
 };
 
+/* Available with KVM_CAP_ARM_RMI, only for VMs with KVM_VM_TYPE_ARM_REALM  */
+#define KVM_ARM_VCPU_RMI_PSCI_COMPLETE	_IOW(KVMIO, 0xd6, struct kvm_arm_rmi_psci_complete)
+
+struct kvm_arm_rmi_psci_complete {
+	__u64 target_mpidr;
+	__u32 psci_status;
+	__u32 padding[3];
+};
+
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

## [13] Steven Price — 2026-03-18
*Subject: [PATCH v13 12/48] arm64: RMI: Basic infrastructure for creating a realm.*

Introduce the skeleton functions for creating and destroying a realm.
The IPA size requested is checked against what the RMM supports.

The actual work of constructing the realm will be added in future
patches.

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/include/asm/kvm_emulate.h |  5 ++
 arch/arm64/include/asm/kvm_rmi.h     | 16 +++++
 arch/arm64/kvm/arm.c                 | 12 ++++
 arch/arm64/kvm/mmu.c                 | 11 +++-
 arch/arm64/kvm/rmi.c                 | 88 ++++++++++++++++++++++++++++
 5 files changed, 129 insertions(+), 3 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_emulate.h b/arch/arm64/include/asm/kvm_emulate.h
index f38b50151ce8..39310d9b4e16 100644
--- a/arch/arm64/include/asm/kvm_emulate.h
+++ b/arch/arm64/include/asm/kvm_emulate.h
@@ -701,6 +701,11 @@ static inline enum realm_state kvm_realm_state(struct kvm *kvm)
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
index 3506f50b05cd..0ada525af18f 100644
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
@@ -46,11 +48,25 @@ enum realm_state {
  * struct realm - Additional per VM data for a Realm
  *
  * @state: The lifetime state machine for the realm
+ * @rd: Kernel mapping of the Realm Descriptor (RD)
+ * @params: Parameters for the RMI_REALM_CREATE command
+ * @num_aux: The number of auxiliary pages required by the RMM
+ * @ia_bits: Number of valid Input Address bits in the IPA
  */
 struct realm {
 	enum realm_state state;
+
+	void *rd;
+	struct realm_params *params;
+
+	unsigned long num_aux;
+	unsigned int ia_bits;
 };
 
 void kvm_init_rmi(void);
+u32 kvm_realm_ipa_limit(void);
+
+int kvm_init_realm_vm(struct kvm *kvm);
+void kvm_destroy_realm(struct kvm *kvm);
 
 #endif /* __ASM_KVM_RMI_H */
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 274d7866efdc..9b17bdfaf0c2 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -253,6 +253,13 @@ int kvm_arch_init_vm(struct kvm *kvm, unsigned long type)
 
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
@@ -312,6 +319,8 @@ void kvm_arch_destroy_vm(struct kvm *kvm)
 	kvm_unshare_hyp(kvm, kvm + 1);
 
 	kvm_arm_teardown_hypercalls(kvm);
+	if (kvm_is_realm(kvm))
+		kvm_destroy_realm(kvm);
 }
 
 static bool kvm_has_full_ptr_auth(void)
@@ -473,6 +482,9 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 		else
 			r = kvm_supports_cacheable_pfnmap();
 		break;
+	case KVM_CAP_ARM_RMI:
+		r = static_key_enabled(&kvm_rmi_is_available);
+		break;
 
 	default:
 		r = 0;
diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index 070a01e53fcb..d6094b60c4ce 100644
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
index 80aedc85e94a..700b8c935d29 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -6,6 +6,8 @@
 #include <linux/kvm_host.h>
 #include <linux/memblock.h>
 
+#include <asm/kvm_emulate.h>
+#include <asm/kvm_mmu.h>
 #include <asm/kvm_pgtable.h>
 #include <asm/rmi_cmds.h>
 #include <asm/virt.h>
@@ -182,6 +184,92 @@ static int rmi_init_metadata(void)
 	return 0;
 }
 
+u32 kvm_realm_ipa_limit(void)
+{
+	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_S2SZ);
+}
+
+static int undelegate_range(phys_addr_t phys, unsigned long size)
+{
+	unsigned long ret;
+	unsigned long top = phys + size;
+	unsigned long out_top;
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
+static int undelegate_page(phys_addr_t phys)
+{
+	return undelegate_range(phys, PAGE_SIZE);
+}
+
+static int free_delegated_page(phys_addr_t phys)
+{
+	if (WARN_ON(undelegate_page(phys))) {
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
+		free_delegated_page(rd_phys);
+		realm->rd = NULL;
+	}
+
+	if (WARN_ON(undelegate_range(kvm->arch.mmu.pgd_phys, pgd_size)))
+		return;
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
 static int rmm_check_features(void)
 {
 	if (kvm_lpa2_is_enabled() && !rmi_has_feature(RMI_FEATURE_REGISTER_0_LPA2)) {

---

## [14] Steven Price — 2026-03-18
*Subject: [PATCH v13 13/48] kvm: arm64: Don't expose unsupported capabilities for realm guests*

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
 arch/arm64/kvm/arm.c | 22 ++++++++++++++++++++++
 1 file changed, 22 insertions(+)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 9b17bdfaf0c2..ddbf080e4f55 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -357,6 +357,25 @@ static bool kvm_has_full_ptr_auth(void)
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
@@ -364,6 +383,9 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 	if (is_protected_kvm_enabled() && !kvm_pkvm_ext_allowed(kvm, ext))
 		return 0;
 
+	if (kvm && kvm_is_realm(kvm) && !kvm_realm_ext_allowed(ext))
+		return 0;
+
 	switch (ext) {
 	case KVM_CAP_IRQCHIP:
 		r = vgic_present;

---

## [15] Steven Price — 2026-03-18
*Subject: [PATCH v13 14/48] KVM: arm64: Allow passing machine type in KVM creation*

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
index 72a2ce96d1ba..bc180c853faf 100644
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
index ddbf080e4f55..b79b58802b33 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -216,6 +216,22 @@ int kvm_arch_init_vm(struct kvm *kvm, unsigned long type)
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
index d6094b60c4ce..9dc242c3b9c8 100644
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
index 6ec140ab0ed1..efd054cfbd07 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -691,14 +691,25 @@ struct kvm_enable_cap {
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

## [16] Steven Price — 2026-03-18
*Subject: [PATCH v13 15/48] arm64: RMI: RTT tear down*

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
 arch/arm64/kvm/mmu.c             |  15 +++-
 arch/arm64/kvm/rmi.c             | 145 +++++++++++++++++++++++++++++++
 3 files changed, 166 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index 0ada525af18f..16a297f3091a 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -68,5 +68,12 @@ u32 kvm_realm_ipa_limit(void);
 
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
index 9dc242c3b9c8..41152abf55b2 100644
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
index 700b8c935d29..1fd2c18f7381 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -15,6 +15,19 @@
 static unsigned long rmm_feat_reg0;
 static unsigned long rmm_feat_reg1;
 
+#define RMM_RTT_BLOCK_LEVEL	2
+#define RMM_RTT_MAX_LEVEL	3
+
+#define RMM_L2_BLOCK_SIZE	PMD_SIZE
+
+static inline unsigned long rmi_rtt_level_mapsize(int level)
+{
+	if (WARN_ON(level > RMM_RTT_MAX_LEVEL))
+		return PAGE_SIZE;
+
+	return (1UL << ARM64_HW_PGTABLE_LEVEL_SHIFT(level));
+}
+
 static bool rmi_has_feature(unsigned long feature)
 {
 	return !!u64_get_bits(rmm_feat_reg0, feature);
@@ -189,6 +202,11 @@ u32 kvm_realm_ipa_limit(void)
 	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_S2SZ);
 }
 
+static int get_start_level(struct realm *realm)
+{
+	return 4 - stage2_pgtable_levels(realm->ia_bits);
+}
+
 static int undelegate_range(phys_addr_t phys, unsigned long size)
 {
 	unsigned long ret;
@@ -223,6 +241,131 @@ static int free_delegated_page(phys_addr_t phys)
 	return 0;
 }
 
+static void free_rtt(phys_addr_t phys)
+{
+	if (free_delegated_page(phys))
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
@@ -246,6 +389,8 @@ void kvm_destroy_realm(struct kvm *kvm)
 	if (realm->rd) {
 		phys_addr_t rd_phys = virt_to_phys(realm->rd);
 
+		kvm_realm_destroy_rtts(kvm);
+
 		if (WARN_ON(rmi_realm_destroy(rd_phys)))
 			return;
 		free_delegated_page(rd_phys);

---

## [17] Steven Price — 2026-03-18
*Subject: [PATCH v13 16/48] arm64: RMI: Activate realm on first VCPU run*

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
index 16a297f3091a..6c13847480f7 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -67,6 +67,7 @@ void kvm_init_rmi(void);
 u32 kvm_realm_ipa_limit(void);
 
 int kvm_init_realm_vm(struct kvm *kvm);
+int kvm_activate_realm(struct kvm *kvm);
 void kvm_destroy_realm(struct kvm *kvm);
 void kvm_realm_destroy_rtts(struct kvm *kvm);
 
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index b79b58802b33..c8e51ed009c0 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -998,6 +998,12 @@ int kvm_arch_vcpu_run_pid_change(struct kvm_vcpu *vcpu)
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
index 1fd2c18f7381..937fababf960 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -366,6 +366,45 @@ void kvm_realm_destroy_rtts(struct kvm *kvm)
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
+	WRITE_ONCE(realm->state, REALM_STATE_DEAD);
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

## [18] Steven Price — 2026-03-18
*Subject: [PATCH v13 17/48] arm64: RMI: Allocate/free RECs to match vCPUs*

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
 arch/arm64/include/asm/kvm_rmi.h     |  21 +++
 arch/arm64/kvm/arm.c                 |  10 +-
 arch/arm64/kvm/reset.c               |   1 +
 arch/arm64/kvm/rmi.c                 | 196 +++++++++++++++++++++++++++
 6 files changed, 230 insertions(+), 3 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_emulate.h b/arch/arm64/include/asm/kvm_emulate.h
index 39310d9b4e16..d194d91fbc2a 100644
--- a/arch/arm64/include/asm/kvm_emulate.h
+++ b/arch/arm64/include/asm/kvm_emulate.h
@@ -708,7 +708,7 @@ static inline bool kvm_realm_is_created(struct kvm *kvm)
 
 static inline bool vcpu_is_rec(struct kvm_vcpu *vcpu)
 {
-	return false;
+	return kvm_is_realm(vcpu->kvm);
 }
 
 #endif /* __ARM64_KVM_EMULATE_H__ */
diff --git a/arch/arm64/include/asm/kvm_host.h b/arch/arm64/include/asm/kvm_host.h
index 9267a2f2d65b..64304848aad4 100644
--- a/arch/arm64/include/asm/kvm_host.h
+++ b/arch/arm64/include/asm/kvm_host.h
@@ -924,6 +924,9 @@ struct kvm_vcpu_arch {
 
 	/* Per-vcpu TLB for VNCR_EL2 -- NULL when !NV */
 	struct vncr_tlb	*vncr_tlb;
+
+	/* Realm meta data */
+	struct realm_rec rec;
 };
 
 /*
diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index 6c13847480f7..4e2c61e71a38 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -63,6 +63,26 @@ struct realm {
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
 
@@ -70,6 +90,7 @@ int kvm_init_realm_vm(struct kvm *kvm);
 int kvm_activate_realm(struct kvm *kvm);
 void kvm_destroy_realm(struct kvm *kvm);
 void kvm_realm_destroy_rtts(struct kvm *kvm);
+void kvm_destroy_rec(struct kvm_vcpu *vcpu);
 
 static inline bool kvm_realm_is_private_address(struct realm *realm,
 						unsigned long addr)
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index c8e51ed009c0..8c50ebd9fba0 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -575,6 +575,8 @@ int kvm_arch_vcpu_create(struct kvm_vcpu *vcpu)
 	/* Force users to call KVM_ARM_VCPU_INIT */
 	vcpu_clear_flag(vcpu, VCPU_INITIALIZED);
 
+	vcpu->arch.rec.mpidr = INVALID_HWID;
+
 	vcpu->arch.mmu_page_cache.gfp_zero = __GFP_ZERO;
 
 	/* Set up the timer */
@@ -1549,7 +1551,7 @@ int kvm_vm_ioctl_irq_line(struct kvm *kvm, struct kvm_irq_level *irq_level,
 	return -EINVAL;
 }
 
-static unsigned long system_supported_vcpu_features(void)
+static unsigned long system_supported_vcpu_features(struct kvm *kvm)
 {
 	unsigned long features = KVM_VCPU_VALID_FEATURES;
 
@@ -1587,7 +1589,7 @@ static int kvm_vcpu_init_check_features(struct kvm_vcpu *vcpu,
 			return -ENOENT;
 	}
 
-	if (features & ~system_supported_vcpu_features())
+	if (features & ~system_supported_vcpu_features(vcpu->kvm))
 		return -EINVAL;
 
 	/*
@@ -1609,6 +1611,10 @@ static int kvm_vcpu_init_check_features(struct kvm_vcpu *vcpu,
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
index 937fababf960..6daf14c4b413 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -207,6 +207,28 @@ static int get_start_level(struct realm *realm)
 	return 4 - stage2_pgtable_levels(realm->ia_bits);
 }
 
+static int delegate_range(phys_addr_t phys, unsigned long size)
+{
+	unsigned long ret;
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
+static int delegate_page(phys_addr_t phys)
+{
+	return delegate_range(phys, PAGE_SIZE);
+}
+
 static int undelegate_range(phys_addr_t phys, unsigned long size)
 {
 	unsigned long ret;
@@ -372,9 +394,177 @@ static int realm_ensure_created(struct kvm *kvm)
 	return -ENXIO;
 }
 
+static void free_rec_aux(struct page **aux_pages,
+			 unsigned int num_aux)
+{
+	unsigned int i;
+	unsigned int page_count = 0;
+
+	for (i = 0; i < num_aux; i++) {
+		struct page *aux_page = aux_pages[page_count++];
+		phys_addr_t aux_page_phys = page_to_phys(aux_page);
+
+		if (!WARN_ON(undelegate_page(aux_page_phys)))
+			__free_page(aux_page);
+		aux_page_phys += PAGE_SIZE;
+	}
+}
+
+static int alloc_rec_aux(struct page **aux_pages,
+			 u64 *aux_phys_pages,
+			 unsigned int num_aux)
+{
+	struct page *aux_page;
+	unsigned int i;
+	int ret;
+
+	for (i = 0; i < num_aux; i++) {
+		phys_addr_t aux_page_phys;
+
+		aux_page = alloc_page(GFP_KERNEL);
+		if (!aux_page) {
+			ret = -ENOMEM;
+			goto out_err;
+		}
+
+		aux_page_phys = page_to_phys(aux_page);
+		if (delegate_page(aux_page_phys)) {
+			ret = -ENXIO;
+			goto err_undelegate;
+		}
+		aux_phys_pages[i] = aux_page_phys;
+		aux_pages[i] = aux_page;
+	}
+
+	return 0;
+err_undelegate:
+	while (i > 0) {
+		i--;
+		if (WARN_ON(undelegate_page(aux_phys_pages[i]))) {
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
+	if (delegate_page(rec_page_phys)) {
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
+	if (WARN_ON(undelegate_page(rec_page_phys)))
+		rec->rec_page = NULL;
+out_free_pages:
+	free_page((unsigned long)rec->run);
+	free_page((unsigned long)rec->rec_page);
+	free_page((unsigned long)params);
+	rec->run = NULL;
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
@@ -397,6 +587,12 @@ int kvm_activate_realm(struct kvm *kvm)
 	/* Mark state as dead in case we fail */
 	WRITE_ONCE(realm->state, REALM_STATE_DEAD);
 
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

## [19] Steven Price — 2026-03-18
*Subject: [PATCH v13 18/48] arm64: RMI: Support for the VGIC in realms*

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
index 8c50ebd9fba0..45eff4c41cde 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -770,19 +770,24 @@ void kvm_arch_vcpu_put(struct kvm_vcpu *vcpu)
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
index 9b3091ad868c..9050e556d11f 100644
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

---

## [20] Steven Price — 2026-03-18
*Subject: [PATCH v13 19/48] KVM: arm64: Support timers in realm RECs*

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
index 600f250753b4..2f2b4befb448 100644
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
@@ -1056,7 +1071,7 @@ static void timer_context_init(struct kvm_vcpu *vcpu, int timerid)
 
 	ctxt->timer_id = timerid;
 
-	if (!kvm_vm_is_protected(vcpu->kvm)) {
+	if (!kvm_vm_is_protected(vcpu->kvm) && !kvm_is_realm(vcpu->kvm)) {
 		if (timerid == TIMER_VTIMER)
 			ctxt->offset.vm_offset = &kvm->arch.timer_data.voffset;
 		else
@@ -1087,7 +1102,7 @@ void kvm_timer_vcpu_init(struct kvm_vcpu *vcpu)
 		timer_context_init(vcpu, i);
 
 	/* Synchronize offsets across timers of a VM if not already provided */
-	if (!vcpu_is_protected(vcpu) &&
+	if (!vcpu_is_protected(vcpu) && !kvm_is_realm(vcpu->kvm) &&
 	    !test_bit(KVM_ARCH_FLAG_VM_COUNTER_OFFSET, &vcpu->kvm->arch.flags)) {
 		timer_set_offset(vcpu_vtimer(vcpu), kvm_phys_timer_read());
 		timer_set_offset(vcpu_ptimer(vcpu), 0);
@@ -1561,6 +1576,13 @@ int kvm_timer_enable(struct kvm_vcpu *vcpu)
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
@@ -1692,7 +1714,7 @@ int kvm_vm_ioctl_set_counter_offset(struct kvm *kvm,
 	if (offset->reserved)
 		return -EINVAL;
 
-	if (kvm_vm_is_protected(kvm))
+	if (kvm_vm_is_protected(kvm) || kvm_is_realm(kvm))
 		return -EINVAL;
 
 	mutex_lock(&kvm->lock);
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

## [21] Steven Price — 2026-03-18
*Subject: [PATCH v13 20/48] arm64: RMI: Handle realm enter/exit*

Entering a realm is done using a SMC call to the RMM. On exit the
exit-codes need to be handled slightly differently to the normal KVM
path so define our own functions for realm enter/exit and hook them
in if the guest is a realm guest.

Signed-off-by: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
---
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
 arch/arm64/kvm/rmi-exit.c        | 178 +++++++++++++++++++++++++++++++
 arch/arm64/kvm/rmi.c             |  43 ++++++++
 5 files changed, 247 insertions(+), 6 deletions(-)
 create mode 100644 arch/arm64/kvm/rmi-exit.c

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index 4e2c61e71a38..7bec3a3976e7 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -92,6 +92,10 @@ void kvm_destroy_realm(struct kvm *kvm);
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
index 45eff4c41cde..badb94b398bc 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -1311,6 +1311,9 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 		if (ret > 0)
 			ret = check_vcpu_requests(vcpu);
 
+		if (ret > 0 && vcpu_is_rec(vcpu))
+			ret = kvm_rec_pre_enter(vcpu);
+
 		/*
 		 * Preparing the interrupts to be injected also
 		 * involves poking the GIC, which must be done in a
@@ -1358,7 +1361,10 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 		trace_kvm_entry(*vcpu_pc(vcpu));
 		guest_timing_enter_irqoff();
 
-		ret = kvm_arm_vcpu_enter_exit(vcpu);
+		if (vcpu_is_rec(vcpu))
+			ret = kvm_rec_enter(vcpu);
+		else
+			ret = kvm_arm_vcpu_enter_exit(vcpu);
 
 		vcpu->mode = OUTSIDE_GUEST_MODE;
 		vcpu->stat.exits++;
@@ -1404,7 +1410,9 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
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
@@ -1416,8 +1424,13 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 
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
 
@@ -1442,7 +1455,10 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
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
index 6daf14c4b413..ee8aab098117 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -394,6 +394,49 @@ static int realm_ensure_created(struct kvm *kvm)
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
 static void free_rec_aux(struct page **aux_pages,
 			 unsigned int num_aux)
 {

---

## [22] Steven Price — 2026-03-18
*Subject: [PATCH v13 21/48] arm64: RMI: Handle RMI_EXIT_RIPAS_CHANGE*

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

There's a FIXME for the case where the RMM rejects a RIPAS change when
(a portion of) the region. The current RMM implementation isn't spec
compliant in this case, this should be fixed in a later release.

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/kvm/rmi.c             | 459 +++++++++++++++++++++++++++++++
 3 files changed, 470 insertions(+), 3 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index 7bec3a3976e7..46b0cbe6c202 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -96,6 +96,12 @@ int kvm_rec_enter(struct kvm_vcpu *vcpu);
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
index 41152abf55b2..b705ad6c6c8b 100644
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
@@ -2241,7 +2242,8 @@ bool kvm_unmap_gfn_range(struct kvm *kvm, struct kvm_gfn_range *range)
 
 	__unmap_stage2_range(&kvm->arch.mmu, range->start << PAGE_SHIFT,
 			     (range->end - range->start) << PAGE_SHIFT,
-			     range->may_block);
+			     range->may_block,
+			     !(range->attr_filter & KVM_FILTER_PRIVATE));
 
 	kvm_nested_s2_unmap(kvm, range->may_block);
 	return false;
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index ee8aab098117..13eed6f0b9eb 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -251,6 +251,88 @@ static int undelegate_page(phys_addr_t phys)
 	return undelegate_range(phys, PAGE_SIZE);
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
+	return undelegate_range(addr, size * count);
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
+	if (delegate_page(phys)) {
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
 static int free_delegated_page(phys_addr_t phys)
 {
 	if (WARN_ON(undelegate_page(phys))) {
@@ -271,6 +353,32 @@ static void free_rtt(phys_addr_t phys)
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
@@ -286,6 +394,38 @@ static int realm_rtt_destroy(struct realm *realm, unsigned long addr,
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
@@ -380,6 +520,62 @@ static int realm_tear_down_rtt_range(struct realm *realm,
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
@@ -388,12 +584,272 @@ void kvm_realm_destroy_rtts(struct kvm *kvm)
 	WARN_ON(realm_tear_down_rtt_range(realm, 0, (1UL << ia_bits)));
 }
 
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
@@ -419,6 +875,9 @@ int kvm_rec_pre_enter(struct kvm_vcpu *vcpu)
 		for (int i = 0; i < REC_RUN_GPRS; i++)
 			rec->run->enter.gprs[i] = vcpu_get_reg(vcpu, i);
 		break;
+	case RMI_EXIT_RIPAS_CHANGE:
+		kvm_complete_ripas_change(vcpu);
+		break;
 	}
 
 	return 1;

---

## [23] Steven Price — 2026-03-18
*Subject: [PATCH v13 22/48] KVM: arm64: Handle realm MMIO emulation*

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

## [24] Steven Price — 2026-03-18
*Subject: [PATCH v13 23/48] KVM: arm64: Expose support for private memory*

Select KVM_GENERIC_MEMORY_ATTRIBUTES and provide the necessary support
functions.

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/include/asm/kvm_host.h |  4 ++++
 arch/arm64/kvm/Kconfig            |  1 +
 arch/arm64/kvm/mmu.c              | 24 ++++++++++++++++++++++++
 3 files changed, 29 insertions(+)

diff --git a/arch/arm64/include/asm/kvm_host.h b/arch/arm64/include/asm/kvm_host.h
index 64304848aad4..1efea996f474 100644
--- a/arch/arm64/include/asm/kvm_host.h
+++ b/arch/arm64/include/asm/kvm_host.h
@@ -1486,6 +1486,10 @@ struct kvm *kvm_arch_alloc_vm(void);
 
 #define vcpu_is_protected(vcpu)		kvm_vm_is_protected((vcpu)->kvm)
 
+#ifdef CONFIG_KVM_GENERIC_MEMORY_ATTRIBUTES
+#define kvm_arch_has_private_mem(kvm) ((kvm)->arch.is_realm)
+#endif
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
index b705ad6c6c8b..bad93938acdb 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -2494,6 +2494,30 @@ int kvm_arch_prepare_memory_region(struct kvm *kvm,
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

## [25] Steven Price — 2026-03-18
*Subject: [PATCH v13 24/48] arm64: RMI: Allow populating initial contents*

The VMM needs to populate the realm with some data before starting (e.g.
a kernel and initrd). This is measured by the RMM and used as part of
the attestation later on.

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/kvm/rmi.c             | 111 +++++++++++++++++++++++++++++++
 4 files changed, 129 insertions(+)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index 46b0cbe6c202..bf663bb240c4 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -96,6 +96,10 @@ int kvm_rec_enter(struct kvm_vcpu *vcpu);
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
index badb94b398bc..43d05da7e694 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -2089,6 +2089,19 @@ int kvm_arch_vm_ioctl(struct file *filp, unsigned int ioctl, unsigned long arg)
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
index 13eed6f0b9eb..b48f4e12e4e0 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -718,6 +718,80 @@ void kvm_realm_unmap_range(struct kvm *kvm, unsigned long start,
 		realm_unmap_private_range(kvm, start, end, may_block);
 }
 
+static int realm_create_protected_data_page(struct kvm *kvm,
+					    unsigned long ipa,
+					    kvm_pfn_t dst_pfn,
+					    kvm_pfn_t src_pfn,
+					    unsigned long flags)
+{
+	struct realm *realm = &kvm->arch.realm;
+	phys_addr_t rd = virt_to_phys(realm->rd);
+	phys_addr_t dst_phys, src_phys;
+	int ret;
+
+	dst_phys = __pfn_to_phys(dst_pfn);
+	src_phys = __pfn_to_phys(src_pfn);
+
+	if (delegate_page(dst_phys))
+		return -ENXIO;
+
+	ret = rmi_rtt_data_map_init(rd, dst_phys, ipa, src_phys, flags);
+	if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
+		/* Create missing RTTs and retry */
+		int level = RMI_RETURN_INDEX(ret);
+
+		KVM_BUG_ON(level == RMM_RTT_MAX_LEVEL, kvm);
+
+		ret = realm_create_rtt_levels(realm, ipa, level,
+					      RMM_RTT_MAX_LEVEL, NULL);
+		if (!ret) {
+			ret = rmi_rtt_data_map_init(rd, dst_phys, ipa, src_phys,
+						    flags);
+		}
+	}
+
+	if (ret) {
+		if (WARN_ON(undelegate_page(dst_phys))) {
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
+	return realm_create_protected_data_page(kvm, ipa, pfn,
+						page_to_pfn(src_page),
+						data_flags);
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
@@ -815,6 +889,43 @@ static int realm_ensure_created(struct kvm *kvm)
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

## [26] Steven Price — 2026-03-18
*Subject: [PATCH v13 25/48] arm64: RMI: Set RIPAS of initial memslots*

The memory which the realm guest accesses must be set to RIPAS_RAM.
Iterate over the memslots and set all gmem memslots to RIPAS_RAM.

Signed-off-by: Steven Price <steven.price@arm.com>
---
New patch for v12.
---
 arch/arm64/kvm/rmi.c | 36 ++++++++++++++++++++++++++++++++++++
 1 file changed, 36 insertions(+)

diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index b48f4e12e4e0..38349c7b34f4 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -883,12 +883,44 @@ static int realm_set_ipa_state(struct kvm_vcpu *vcpu,
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
@@ -1206,6 +1238,10 @@ int kvm_activate_realm(struct kvm *kvm)
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

## [27] Steven Price — 2026-03-18
*Subject: [PATCH v13 26/48] arm64: RMI: Create the realm descriptor*

Creating a realm involves first creating a realm descriptor (RD). This
involves passing the configuration information to the RMM. Do this as
part of realm_ensure_created() so that the realm is created when it is
first needed.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v12:
 * Since RMM page size is now equal to the host's page size various
   calculations are simplified.
 * Switch to using range based APIs to delegate/undelegate.
 * VMID handling is now handled entirely by the RMM.
---
 arch/arm64/kvm/rmi.c | 94 +++++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 92 insertions(+), 2 deletions(-)

diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 38349c7b34f4..d5fee203824b 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -649,6 +649,83 @@ static void realm_unmap_shared_range(struct kvm *kvm,
 			     start, end);
 }
 
+static int realm_create_rd(struct kvm *kvm)
+{
+	struct realm *realm = &kvm->arch.realm;
+	struct realm_params *params = realm->params;
+	void *rd = NULL;
+	phys_addr_t rd_phys, params_phys;
+	size_t pgd_size = kvm_pgtable_stage2_pgd_size(kvm->arch.mmu.vtcr);
+	int i, r;
+
+	realm->ia_bits = VTCR_EL2_IPA(kvm->arch.mmu.vtcr);
+
+	if (WARN_ON(realm->rd || !realm->params))
+		return -EEXIST;
+
+	rd = (void *)__get_free_page(GFP_KERNEL);
+	if (!rd)
+		return -ENOMEM;
+
+	rd_phys = virt_to_phys(rd);
+	if (delegate_page(rd_phys)) {
+		r = -ENXIO;
+		goto free_rd;
+	}
+
+	if (delegate_range(kvm->arch.mmu.pgd_phys, pgd_size)) {
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
+	if (WARN_ON(undelegate_range(kvm->arch.mmu.pgd_phys, i))) {
+		/* Leak the pages if they cannot be returned */
+		kvm->arch.mmu.pgt = NULL;
+	}
+	if (WARN_ON(undelegate_page(rd_phys))) {
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
@@ -893,8 +970,21 @@ static int realm_init_ipa_state(struct kvm *kvm,
 
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

## [28] Steven Price — 2026-03-18
*Subject: [PATCH v13 27/48] arm64: RMI: Runtime faulting of memory*

At runtime if the realm guest accesses memory which hasn't yet been
mapped then KVM needs to either populate the region or fault the guest.

For memory in the lower (protected) region of IPA a fresh page is
provided to the RMM which will zero the contents. For memory in the
upper (shared) region of IPA, the memory from the memslot is mapped
into the realm VM non secure.

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/kvm/mmu.c                 | 139 ++++++++++++++++--
 arch/arm64/kvm/rmi.c                 | 206 +++++++++++++++++++++++++++
 4 files changed, 351 insertions(+), 14 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_emulate.h b/arch/arm64/include/asm/kvm_emulate.h
index d194d91fbc2a..0734c4a65174 100644
--- a/arch/arm64/include/asm/kvm_emulate.h
+++ b/arch/arm64/include/asm/kvm_emulate.h
@@ -706,6 +706,14 @@ static inline bool kvm_realm_is_created(struct kvm *kvm)
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
index bf663bb240c4..38208be3c602 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -6,6 +6,7 @@
 #ifndef __ASM_KVM_RMI_H
 #define __ASM_KVM_RMI_H
 
+#include <asm/kvm_pgtable.h>
 #include <asm/rmi_smc.h>
 
 /**
@@ -105,6 +106,17 @@ void kvm_realm_unmap_range(struct kvm *kvm,
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
index bad93938acdb..73c18c2861a2 100644
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
 
@@ -1516,6 +1533,29 @@ static bool kvm_vma_mte_allowed(struct vm_area_struct *vma)
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
@@ -1588,6 +1628,7 @@ static int gmem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 	enum kvm_pgtable_walk_flags flags = KVM_PGTABLE_WALK_SHARED;
 	enum kvm_pgtable_prot prot = KVM_PGTABLE_PROT_R;
 	struct kvm_pgtable *pgt = vcpu->arch.hw_mmu->pgt;
+	gpa_t gpa = kvm_gpa_from_fault(vcpu->kvm, fault_ipa);
 	unsigned long mmu_seq;
 	struct page *page;
 	struct kvm *kvm = vcpu->kvm;
@@ -1596,6 +1637,29 @@ static int gmem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
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
@@ -1603,7 +1667,7 @@ static int gmem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 	if (nested)
 		gfn = kvm_s2_trans_output(nested) >> PAGE_SHIFT;
 	else
-		gfn = fault_ipa >> PAGE_SHIFT;
+		gfn = gpa >> PAGE_SHIFT;
 
 	write_fault = kvm_is_write_fault(vcpu);
 	exec_fault = kvm_vcpu_trap_is_exec_fault(vcpu);
@@ -1616,7 +1680,7 @@ static int gmem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 
 	ret = kvm_gmem_get_pfn(kvm, memslot, gfn, &pfn, &page, NULL);
 	if (ret) {
-		kvm_prepare_memory_fault_exit(vcpu, fault_ipa, PAGE_SIZE,
+		kvm_prepare_memory_fault_exit(vcpu, gpa, PAGE_SIZE,
 					      write_fault, exec_fault, false);
 		return ret;
 	}
@@ -1638,15 +1702,25 @@ static int gmem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
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
@@ -1685,6 +1759,14 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
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
 
@@ -1779,7 +1861,7 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 		ipa &= ~(vma_pagesize - 1);
 	}
 
-	gfn = ipa >> PAGE_SHIFT;
+	gfn = kvm_gpa_from_fault(kvm, ipa) >> PAGE_SHIFT;
 	mte_allowed = kvm_vma_mte_allowed(vma);
 
 	vfio_allow_any_uc = vma->vm_flags & VM_ALLOW_ANY_UNCACHED;
@@ -1855,6 +1937,15 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
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
@@ -1939,6 +2030,9 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 		 */
 		prot &= ~KVM_NV_GUEST_MAP_SZ;
 		ret = KVM_PGT_FN(kvm_pgtable_stage2_relax_perms)(pgt, fault_ipa, prot, flags);
+	} else if (kvm_is_realm(kvm)) {
+		ret = realm_map_ipa(kvm, fault_ipa, pfn, vma_pagesize,
+				    prot, memcache);
 	} else {
 		ret = KVM_PGT_FN(kvm_pgtable_stage2_map)(pgt, fault_ipa, vma_pagesize,
 					     __pfn_to_phys(pfn), prot,
@@ -2049,6 +2143,13 @@ int kvm_handle_guest_sea(struct kvm_vcpu *vcpu)
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
@@ -2159,8 +2260,9 @@ int kvm_handle_guest_abort(struct kvm_vcpu *vcpu)
 		nested = &nested_trans;
 	}
 
-	gfn = ipa >> PAGE_SHIFT;
+	gfn = kvm_gpa_from_fault(vcpu->kvm, ipa) >> PAGE_SHIFT;
 	memslot = gfn_to_memslot(vcpu->kvm, gfn);
+
 	hva = gfn_to_hva_memslot_prot(memslot, gfn, &writable);
 	write_fault = kvm_is_write_fault(vcpu);
 	if (kvm_is_error_hva(hva) || (write_fault && !writable)) {
@@ -2203,7 +2305,7 @@ int kvm_handle_guest_abort(struct kvm_vcpu *vcpu)
 		 * of the page size.
 		 */
 		ipa |= FAR_TO_FIPA_OFFSET(kvm_vcpu_get_hfar(vcpu));
-		ret = io_mem_abort(vcpu, ipa);
+		ret = io_mem_abort(vcpu, kvm_gpa_from_fault(vcpu->kvm, ipa));
 		goto out_unlock;
 	}
 
@@ -2219,7 +2321,7 @@ int kvm_handle_guest_abort(struct kvm_vcpu *vcpu)
 	VM_WARN_ON_ONCE(kvm_vcpu_trap_is_permission_fault(vcpu) &&
 			!write_fault && !kvm_vcpu_trap_is_exec_fault(vcpu));
 
-	if (kvm_slot_has_gmem(memslot))
+	if (kvm_slot_has_gmem(memslot) && !shared_ipa_fault(vcpu->kvm, fault_ipa))
 		ret = gmem_abort(vcpu, fault_ipa, nested, memslot,
 				 esr_fsc_is_permission_fault(esr));
 	else
@@ -2256,6 +2358,10 @@ bool kvm_age_gfn(struct kvm *kvm, struct kvm_gfn_range *range)
 	if (!kvm->arch.mmu.pgt)
 		return false;
 
+	/* We don't support aging for Realms */
+	if (kvm_is_realm(kvm))
+		return true;
+
 	return KVM_PGT_FN(kvm_pgtable_stage2_test_clear_young)(kvm->arch.mmu.pgt,
 						   range->start << PAGE_SHIFT,
 						   size, true);
@@ -2272,6 +2378,10 @@ bool kvm_test_age_gfn(struct kvm *kvm, struct kvm_gfn_range *range)
 	if (!kvm->arch.mmu.pgt)
 		return false;
 
+	/* We don't support aging for Realms */
+	if (kvm_is_realm(kvm))
+		return true;
+
 	return KVM_PGT_FN(kvm_pgtable_stage2_test_clear_young)(kvm->arch.mmu.pgt,
 						   range->start << PAGE_SHIFT,
 						   size, false);
@@ -2438,10 +2548,11 @@ int kvm_arch_prepare_memory_region(struct kvm *kvm,
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
index d5fee203824b..30292814b1ec 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -837,6 +837,212 @@ static int realm_create_protected_data_page(struct kvm *kvm,
 	return ret;
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
+static unsigned long addr_range_desc(unsigned long phys, unsigned long size)
+{
+	unsigned long out = 0;
+
+	switch (size) {
+	case P4D_SIZE:
+		out = 0 | (1 << 2);
+		break;
+	case PUD_SIZE:
+		out = 1 | (1 << 2);
+		break;
+	case PMD_SIZE:
+		out = 2 | (1 << 2);
+		break;
+	case PAGE_SIZE:
+		out = 3 | (1 << 2);
+		break;
+	default:
+		/*
+		 * Only support mapping at the page level granulatity when
+		 * it's an unusual length. This should get us back onto a larger
+		 * block size for the subsequent mappings.
+		 */
+		out = 3 | ((MIN(size >> PAGE_SHIFT, PTRS_PER_PTE - 1)) << 2);
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
+	phys_addr_t rd = virt_to_phys(realm->rd);
+	unsigned long base_ipa = ipa;
+	unsigned long ipa_top = ipa + map_size;
+	int map_level = IS_ALIGNED(map_size, RMM_L2_BLOCK_SIZE) ?
+			RMM_RTT_BLOCK_LEVEL : RMM_RTT_MAX_LEVEL;
+	int ret = 0;
+
+	if (WARN_ON(!IS_ALIGNED(map_size, PAGE_SIZE) ||
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
+	if (delegate_range(phys, map_size)) {
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
+			WARN_ON(level == RMM_RTT_MAX_LEVEL);
+			ret = realm_create_rtt_levels(realm, ipa, level,
+						      RMM_RTT_MAX_LEVEL,
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
+	if (map_size == RMM_L2_BLOCK_SIZE) {
+		ret = fold_rtt(realm, base_ipa, map_level + 1);
+		if (WARN_ON(ret))
+			goto err;
+	}
+
+	return 0;
+
+err_undelegate:
+	if (WARN_ON(undelegate_range(phys, map_size))) {
+		/* Page can't be returned to NS world so is lost */
+		get_page(phys_to_page(phys));
+	}
+err:
+	realm_unmap_private_range(kvm, base_ipa, ipa, true);
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
+	unsigned long attr;
+	phys_addr_t rd = virt_to_phys(realm->rd);
+	phys_addr_t phys = __pfn_to_phys(pfn);
+	unsigned long offset;
+	/* TODO: Support block mappings */
+	int map_level = RMM_RTT_MAX_LEVEL;
+	int map_size = rmi_rtt_level_mapsize(map_level);
+	int ret = 0;
+
+	if (WARN_ON(!IS_ALIGNED(size, PAGE_SIZE) ||
+		    !IS_ALIGNED(ipa, size)))
+		return -EINVAL;
+
+	switch (prot & (KVM_PGTABLE_PROT_DEVICE | KVM_PGTABLE_PROT_NORMAL_NC)) {
+	case KVM_PGTABLE_PROT_DEVICE | KVM_PGTABLE_PROT_NORMAL_NC:
+		return -EINVAL;
+	case KVM_PGTABLE_PROT_DEVICE:
+		attr = PTE_S2_MEMATTR(MT_S2_FWB_DEVICE_nGnRE);
+		break;
+	case KVM_PGTABLE_PROT_NORMAL_NC:
+		attr = PTE_S2_MEMATTR(MT_S2_FWB_NORMAL_NC);
+		break;
+	default:
+		attr = PTE_S2_MEMATTR(MT_S2_FWB_NORMAL);
+	}
+
+	for (offset = 0; offset < size; offset += map_size) {
+		/*
+		 * realm_map_ipa() enforces that the memory is writable,
+		 * so for now we permit both read and write.
+		 */
+		unsigned long desc = kvm_phys_to_pte(phys) | attr |
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
 			      struct page *src_page, void *opaque)
 {

---

## [29] Steven Price — 2026-03-18
*Subject: [PATCH v13 28/48] KVM: arm64: Handle realm VCPU load*

When loading a realm VCPU much of the work is handled by the RMM so only
some of the actions are required. Rearrange kvm_arch_vcpu_load()
slightly so we can bail out early for a realm guest.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/kvm/arm.c | 19 ++++++++++++-------
 1 file changed, 12 insertions(+), 7 deletions(-)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 43d05da7e694..304fb1f2b3ff 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -688,7 +688,7 @@ void kvm_arch_vcpu_load(struct kvm_vcpu *vcpu, int cpu)
 	struct kvm_s2_mmu *mmu;
 	int *last_ran;
 
-	if (is_protected_kvm_enabled())
+	if (is_protected_kvm_enabled() || kvm_is_realm(vcpu->kvm))
 		goto nommu;
 
 	if (vcpu_has_nv(vcpu))
@@ -732,12 +732,6 @@ void kvm_arch_vcpu_load(struct kvm_vcpu *vcpu, int cpu)
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
@@ -759,6 +753,17 @@ void kvm_arch_vcpu_load(struct kvm_vcpu *vcpu, int cpu)
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

## [30] Steven Price — 2026-03-18
*Subject: [PATCH v13 29/48] KVM: arm64: Validate register access for a Realm VM*

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

## [31] Steven Price — 2026-03-18
*Subject: [PATCH v13 30/48] KVM: arm64: Handle Realm PSCI requests*

The RMM needs to be informed of the target REC when a PSCI call is made
with an MPIDR argument. Expose an ioctl to the userspace in case the PSCI
is handled by it.

[NOTE: A future version of the RMM specification is likely to remove the
need for this ioctl.]

Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/include/asm/kvm_rmi.h |  3 +++
 arch/arm64/kvm/arm.c             | 25 +++++++++++++++++++++++++
 arch/arm64/kvm/psci.c            | 30 ++++++++++++++++++++++++++++++
 arch/arm64/kvm/rmi.c             | 14 ++++++++++++++
 4 files changed, 72 insertions(+)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index 38208be3c602..1ee5ed0f5ab2 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -117,6 +117,9 @@ int realm_map_non_secure(struct realm *realm,
 			 unsigned long size,
 			 enum kvm_pgtable_prot prot,
 			 struct kvm_mmu_memory_cache *memcache);
+int realm_psci_complete(struct kvm_vcpu *source,
+			struct kvm_vcpu *target,
+			unsigned long status);
 
 static inline bool kvm_realm_is_private_address(struct realm *realm,
 						unsigned long addr)
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 304fb1f2b3ff..61182eb0cf70 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -1846,6 +1846,22 @@ static int kvm_arm_vcpu_set_events(struct kvm_vcpu *vcpu,
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
@@ -1974,6 +1990,15 @@ long kvm_arch_vcpu_ioctl(struct file *filp,
 
 		return kvm_arm_vcpu_finalize(vcpu, what);
 	}
+	case KVM_ARM_VCPU_RMI_PSCI_COMPLETE: {
+		struct kvm_arm_rmi_psci_complete req;
+
+		if (!vcpu_is_rec(vcpu))
+			return -ENXIO;
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
index 30292814b1ec..e56c8af2ad61 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -353,6 +353,20 @@ static void free_rtt(phys_addr_t phys)
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

## [32] Steven Price — 2026-03-18
*Subject: [PATCH v13 31/48] KVM: arm64: WARN on injected undef exceptions*

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

## [33] Steven Price — 2026-03-18
*Subject: [PATCH v13 32/48] arm64: Don't expose stolen time for realm guests*

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
index bc180c853faf..70911fe6d435 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -9240,6 +9240,9 @@ is supported, than the other should as well and vice versa.  For arm64
 see Documentation/virt/kvm/devices/vcpu.rst "KVM_ARM_VCPU_PVTIME_CTRL".
 For x86 see Documentation/virt/kvm/x86/msr.rst "MSR_KVM_STEAL_TIME".
 
+Note that steal time accounting is not available when a guest is running
+within a Arm CCA realm (machine type KVM_VM_TYPE_ARM_REALM).
+
 8.25 KVM_CAP_S390_DIAG318
 -------------------------
 
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 61182eb0cf70..7d92ddb06460 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -469,7 +469,10 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
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

## [34] Steven Price — 2026-03-18
*Subject: [PATCH v13 33/48] arm64: RMI: allow userspace to inject aborts*

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
index 70911fe6d435..eabe20d3ae76 100644
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

## [35] Steven Price — 2026-03-18
*Subject: [PATCH v13 34/48] arm64: RMI: support RSI_HOST_CALL*

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

## [36] Steven Price — 2026-03-18
*Subject: [PATCH v13 35/48] arm64: RMI: Allow checking SVE on VM instance*

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
index 1ee5ed0f5ab2..d6cf87de099b 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -87,6 +87,8 @@ struct realm_rec {
 void kvm_init_rmi(void);
 u32 kvm_realm_ipa_limit(void);
 
+bool kvm_rmi_supports_sve(void);
+
 int kvm_init_realm_vm(struct kvm *kvm);
 int kvm_activate_realm(struct kvm *kvm);
 void kvm_destroy_realm(struct kvm *kvm);
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 7d92ddb06460..3e6f1e810921 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -388,6 +388,8 @@ static bool kvm_realm_ext_allowed(long ext)
 	case KVM_CAP_ARM_PTRAUTH_GENERIC:
 	case KVM_CAP_ARM_RMI:
 		return true;
+	case KVM_CAP_ARM_SVE:
+		return kvm_rmi_supports_sve();
 	}
 	return false;
 }
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index e56c8af2ad61..7cc6dc14d325 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -33,6 +33,11 @@ static bool rmi_has_feature(unsigned long feature)
 	return !!u64_get_bits(rmm_feat_reg0, feature);
 }
 
+bool kvm_rmi_supports_sve(void)
+{
+	return rmi_has_feature(RMI_FEATURE_REGISTER_0_SVE);
+}
+
 static int rmi_check_version(void)
 {
 	struct arm_smccc_res res;

---

## [37] Steven Price — 2026-03-18
*Subject: [PATCH v13 36/48] arm64: RMI: Always use 4k pages for realms*

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
index 73c18c2861a2..ad1300f366df 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -1761,11 +1761,14 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
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

## [38] Steven Price — 2026-03-18
*Subject: [PATCH v13 37/48] arm64: RMI: Prevent Device mappings for Realms*

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
index ad1300f366df..7d7caab8f573 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -1222,6 +1222,10 @@ int kvm_phys_addr_ioremap(struct kvm *kvm, phys_addr_t guest_ipa,
 	if (is_protected_kvm_enabled())
 		return -EPERM;
 
+	/* We don't support mapping special pages into a Realm */
+	if (kvm_is_realm(kvm))
+		return -EPERM;
+
 	size += offset_in_page(guest_ipa);
 	guest_ipa &= PAGE_MASK;
 
@@ -1965,6 +1969,15 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 		return 1;
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

## [39] Steven Price — 2026-03-18
*Subject: [PATCH v13 38/48] arm64: RMI: Enable PMU support with a realm guest*

Use the PMU registers from the RmiRecExit structure to identify when an
overflow interrupt is due and inject it into the guest. Also hook up the
configuration option for enabling the PMU within the guest.

The number of PMU counters is configured by the VMM by writing to PMCR.N.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v12:
 * RMMv2.0 no longer requires disaling the physical interrupt when
   entering the guest with a PMU overflow interrupt active.
Changes since v2:
 * Add a macro kvm_pmu_get_irq_level() to avoid compile issues when PMU
   support is disabled.
---
 arch/arm64/include/asm/kvm_rmi.h | 1 +
 arch/arm64/kvm/arm.c             | 2 ++
 arch/arm64/kvm/guest.c           | 7 +++++++
 arch/arm64/kvm/pmu-emul.c        | 3 +++
 arch/arm64/kvm/rmi.c             | 8 ++++++++
 arch/arm64/kvm/sys_regs.c        | 5 +++--
 include/kvm/arm_pmu.h            | 4 ++++
 7 files changed, 28 insertions(+), 2 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index d6cf87de099b..17bb7e2a2aa0 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -88,6 +88,7 @@ void kvm_init_rmi(void);
 u32 kvm_realm_ipa_limit(void);
 
 bool kvm_rmi_supports_sve(void);
+bool kvm_rmi_supports_pmu(void);
 
 int kvm_init_realm_vm(struct kvm *kvm);
 int kvm_activate_realm(struct kvm *kvm);
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 3e6f1e810921..cd2cb5e54f21 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -388,6 +388,8 @@ static bool kvm_realm_ext_allowed(long ext)
 	case KVM_CAP_ARM_PTRAUTH_GENERIC:
 	case KVM_CAP_ARM_RMI:
 		return true;
+	case KVM_CAP_ARM_PMU_V3:
+		return kvm_rmi_supports_pmu();
 	case KVM_CAP_ARM_SVE:
 		return kvm_rmi_supports_sve();
 	}
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
index 93cc9bbb5cec..450b0eac20f8 100644
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
index 7cc6dc14d325..8dc090da6e5f 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -38,6 +38,11 @@ bool kvm_rmi_supports_sve(void)
 	return rmi_has_feature(RMI_FEATURE_REGISTER_0_SVE);
 }
 
+bool kvm_rmi_supports_pmu(void)
+{
+	return rmi_has_feature(RMI_FEATURE_REGISTER_0_PMU);
+}
+
 static int rmi_check_version(void)
 {
 	struct arm_smccc_res res;
@@ -1431,6 +1436,9 @@ static int kvm_create_rec(struct kvm_vcpu *vcpu)
 	if (!vcpu_has_feature(vcpu, KVM_ARM_VCPU_PSCI_0_2))
 		return -EINVAL;
 
+	if (vcpu->kvm->arch.arm_pmu && !kvm_vcpu_has_pmu(vcpu))
+		return -EINVAL;
+
 	BUILD_BUG_ON(sizeof(*params) > PAGE_SIZE);
 	BUILD_BUG_ON(sizeof(*rec->run) > PAGE_SIZE);
 
diff --git a/arch/arm64/kvm/sys_regs.c b/arch/arm64/kvm/sys_regs.c
index a7cd0badc20c..46f5e2ab3e2c 100644
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

## [40] Steven Price — 2026-03-18
*Subject: [PATCH v13 39/48] arm64: RMI: Propagate number of breakpoints and watchpoints to userspace*

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
index 17bb7e2a2aa0..8fb526764c30 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -87,6 +87,8 @@ struct realm_rec {
 void kvm_init_rmi(void);
 u32 kvm_realm_ipa_limit(void);
 
+u64 kvm_realm_reset_id_aa64dfr0_el1(const struct kvm_vcpu *vcpu, u64 val);
+
 bool kvm_rmi_supports_sve(void);
 bool kvm_rmi_supports_pmu(void);
 
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 8dc090da6e5f..01519d934d3a 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -212,6 +212,28 @@ u32 kvm_realm_ipa_limit(void)
 	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_S2SZ);
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
 	return 4 - stage2_pgtable_levels(realm->ia_bits);
diff --git a/arch/arm64/kvm/sys_regs.c b/arch/arm64/kvm/sys_regs.c
index 46f5e2ab3e2c..83b5c36f43bf 100644
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

## [41] Steven Price — 2026-03-18
*Subject: [PATCH v13 40/48] arm64: RMI: Set breakpoint parameters through SET_ONE_REG*

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
index 01519d934d3a..76ff00488883 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -702,6 +702,7 @@ static int realm_create_rd(struct kvm *kvm)
 	void *rd = NULL;
 	phys_addr_t rd_phys, params_phys;
 	size_t pgd_size = kvm_pgtable_stage2_pgd_size(kvm->arch.mmu.vtcr);
+	u64 dfr0 = kvm_read_vm_id_reg(kvm, SYS_ID_AA64DFR0_EL1);
 	int i, r;
 
 	realm->ia_bits = VTCR_EL2_IPA(kvm->arch.mmu.vtcr);
@@ -728,6 +729,8 @@ static int realm_create_rd(struct kvm *kvm)
 	params->rtt_level_start = get_start_level(realm);
 	params->rtt_num_start = pgd_size / PAGE_SIZE;
 	params->rtt_base = kvm->arch.mmu.pgd_phys;
+	params->num_bps = SYS_FIELD_GET(ID_AA64DFR0_EL1, BRPs, dfr0);
+	params->num_wps = SYS_FIELD_GET(ID_AA64DFR0_EL1, WRPs, dfr0);
 
 	if (kvm->arch.arm_pmu) {
 		params->pmu_num_ctrs = kvm->arch.nr_pmu_counters;
diff --git a/arch/arm64/kvm/sys_regs.c b/arch/arm64/kvm/sys_regs.c
index 83b5c36f43bf..ebb428b861f5 100644
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

## [42] Steven Price — 2026-03-18
*Subject: [PATCH v13 41/48] arm64: RMI: Initialize PMCR.N with number counter supported by RMM*

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
index 8fb526764c30..8f871daf6540 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -86,6 +86,7 @@ struct realm_rec {
 
 void kvm_init_rmi(void);
 u32 kvm_realm_ipa_limit(void);
+u8 kvm_realm_max_pmu_counters(void);
 
 u64 kvm_realm_reset_id_aa64dfr0_el1(const struct kvm_vcpu *vcpu, u64 val);
 
diff --git a/arch/arm64/kvm/pmu-emul.c b/arch/arm64/kvm/pmu-emul.c
index 450b0eac20f8..9d8bc26c5c69 100644
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
index 76ff00488883..f29c04d2318a 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -212,6 +212,11 @@ u32 kvm_realm_ipa_limit(void)
 	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_S2SZ);
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

## [43] Steven Price — 2026-03-18
*Subject: [PATCH v13 42/48] arm64: RMI: Propagate max SVE vector length from RMM*

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
index 1efea996f474..1d5fb001408c 100644
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
index 8f871daf6540..b914b9a84bd8 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -87,6 +87,7 @@ struct realm_rec {
 void kvm_init_rmi(void);
 u32 kvm_realm_ipa_limit(void);
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
index f29c04d2318a..f2aeda7f5e6e 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -217,6 +217,12 @@ u8 kvm_realm_max_pmu_counters(void)
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

## [44] Steven Price — 2026-03-18
*Subject: [PATCH v13 43/48] arm64: RMI: Configure max SVE vector length for a Realm*

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
index f2aeda7f5e6e..f69151d4235a 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -706,6 +706,39 @@ static void realm_unmap_shared_range(struct kvm *kvm,
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
@@ -751,6 +784,10 @@ static int realm_create_rd(struct kvm *kvm)
 	if (kvm_lpa2_is_enabled())
 		params->flags |= RMI_REALM_PARAM_FLAG_LPA2;
 
+	r = realm_init_sve_param(kvm, params);
+	if (r)
+		goto out_undelegate_tables;
+
 	params_phys = virt_to_phys(params);
 
 	if (rmi_realm_create(rd_phys, params_phys)) {

---

## [45] Steven Price — 2026-03-18
*Subject: [PATCH v13 44/48] arm64: RMI: Provide register list for unfinalized RMI RECs*

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
index cd2cb5e54f21..11a816fe981c 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -1923,10 +1923,6 @@ long kvm_arch_vcpu_ioctl(struct file *filp,
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

## [46] Steven Price — 2026-03-18
*Subject: [PATCH v13 45/48] arm64: RMI: Provide accurate register list*

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
index ebb428b861f5..088d900b9c3a 100644
--- a/arch/arm64/kvm/sys_regs.c
+++ b/arch/arm64/kvm/sys_regs.c
@@ -5436,18 +5436,18 @@ int kvm_arm_sys_reg_set_reg(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg
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
@@ -5491,11 +5491,28 @@ static bool copy_reg_to_user(const struct sys_reg_desc *reg, u64 __user **uind)
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
@@ -5533,7 +5550,7 @@ static int walk_sys_regs(struct kvm_vcpu *vcpu, u64 __user *uind)
 
 unsigned long kvm_arm_num_sys_reg_descs(struct kvm_vcpu *vcpu)
 {
-	return num_demux_regs()
+	return num_demux_regs(vcpu)
 		+ walk_sys_regs(vcpu, (u64 __user *)NULL);
 }
 
@@ -5546,7 +5563,7 @@ int kvm_arm_copy_sys_reg_indices(struct kvm_vcpu *vcpu, u64 __user *uindices)
 		return err;
 	uindices += err;
 
-	return write_demux_regids(uindices);
+	return write_demux_regids(vcpu, uindices);
 }
 
 #define KVM_ARM_FEATURE_ID_RANGE_INDEX(r)			\

---

## [47] Steven Price — 2026-03-18
*Subject: [PATCH v13 46/48] KVM: arm64: Expose KVM_ARM_VCPU_REC to user space*

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
index 1d5fb001408c..b02f97de4436 100644
--- a/arch/arm64/include/asm/kvm_host.h
+++ b/arch/arm64/include/asm/kvm_host.h
@@ -40,7 +40,7 @@
 
 #define KVM_MAX_VCPUS VGIC_V3_MAX_CPUS
 
-#define KVM_VCPU_MAX_FEATURES 9
+#define KVM_VCPU_MAX_FEATURES 10
 #define KVM_VCPU_VALID_FEATURES	(BIT(KVM_VCPU_MAX_FEATURES) - 1)
 
 #define KVM_REQ_SLEEP \

---

## [48] Steven Price — 2026-03-18
*Subject: [PATCH v13 47/48] arm64: RMI: Enable realms to be created*

All the pieces are now in place, so enable kvm_rmi_is_available when the
RMM is detected.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/kvm/rmi.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index f69151d4235a..e76e58762f55 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -1723,5 +1723,5 @@ void kvm_init_rmi(void)
 	if (rmi_init_metadata())
 		return;
 
-	/* Future patch will enable static branch kvm_rmi_is_available */
+	static_branch_enable(&kvm_rmi_is_available);
 }

---

## [49] Steven Price — 2026-03-18
*Subject: [PATCH v13 48/48] [WIP] arm64: RMI: Add support for SRO*

RMM v2.0 introduces the concept of "Stateful RMI Operations" (SRO).
This means that an SMC can return with an operation still in progress.
The host is expected to continue the operation until it reaches a
conclusion (either success or failure). During this process the RMM can
request addition memory ('donate') or hand memory back to the host
('reclaim'). The host can request an operation is cancelled, but must
still continue the operation until it has completed (otherwise the
incomplete operation may cause future RMM operations to fail).

SROs may request memory and these operations sometimes have to be
performed in places where memory allocation may not be possible. To deal
with this a SRO may be started, but then cancelled when the memory
allocation cannot be completed. The reclaimed memory will then be stored
in a struct rmi_sro_state object with the intention that once Linux has
returned to a state where memory allocation is possible, the failed
allocation can be reattempted (with GFP flags enabling sleeping and/or
direct reclaim) and the SRO operation reattempted (after acquiring the
necessary locks). In the worst case this may require several attempts
(if the RMM makes several memory requests) but should always make
forward progress.

This patch is currently a work-in-progress showing the general structure
of how this should work and implementing SROs for two operations
(RMI_REC_CREATE and RMI_REC_DESTROY). I'm aware there is missing
error-checking and there are some details in the specification that need
clarifying. These operations are also 'easy' in that we don't have
restrictions on memory allocation in these contexts.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/include/asm/kvm_rmi.h  |   8 -
 arch/arm64/include/asm/rmi_cmds.h |  71 +++---
 arch/arm64/include/asm/rmi_smc.h  |  27 +--
 arch/arm64/kvm/rmi.c              | 385 +++++++++++++++++++++++-------
 4 files changed, 347 insertions(+), 144 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index b914b9a84bd8..e1f5523c2dfa 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -51,7 +51,6 @@ enum realm_state {
  * @state: The lifetime state machine for the realm
  * @rd: Kernel mapping of the Realm Descriptor (RD)
  * @params: Parameters for the RMI_REALM_CREATE command
- * @num_aux: The number of auxiliary pages required by the RMM
  * @ia_bits: Number of valid Input Address bits in the IPA
  */
 struct realm {
@@ -60,7 +59,6 @@ struct realm {
 	void *rd;
 	struct realm_params *params;
 
-	unsigned long num_aux;
 	unsigned int ia_bits;
 };
 
@@ -75,12 +73,6 @@ struct realm {
 struct realm_rec {
 	unsigned long mpidr;
 	void *rec_page;
-	/*
-	 * REC_PARAMS_AUX_GRANULES is the maximum number of 4K granules that
-	 * the RMM can require. The array is sized to be large enough for the
-	 * maximum number of host sized pages that could be required.
-	 */
-	struct page *aux_pages[(REC_PARAMS_AUX_GRANULES * SZ_4K) >> PAGE_SHIFT];
 	struct rec_run *run;
 };
 
diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 9c4f83644a61..b761d74e1273 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -17,6 +17,27 @@ struct rtt_entry {
 	int ripas;
 };
 
+#define RMI_MAX_ADDR_LIST 256
+
+struct rmi_sro_state {
+	struct arm_smccc_1_2_regs regs;
+
+	unsigned long addr_count;
+	unsigned long addr_list[RMI_MAX_ADDR_LIST];
+};
+
+#define rmi_init_sro(...) ({						\
+	struct rmi_sro_state *sro = kmalloc_obj(*sro);			\
+	if (sro)							\
+		*sro = (struct rmi_sro_state){.regs = {__VA_ARGS__}};	\
+	sro;								\
+})
+
+#define rmi_smccc(...) do { \
+	arm_smccc_1_1_invoke(__VA_ARGS__); \
+} while (RMI_RETURN_STATUS(res.a0) == RMI_BUSY || \
+	 RMI_RETURN_STATUS(res.a0) == RMI_BLOCKED)
+
 /**
  * rmi_rmm_config_get() - Get the system configuration
  * @cfg_ptr: PA of a struct rmm_config
@@ -410,29 +431,7 @@ static inline int rmi_realm_destroy(unsigned long rd)
 }
 
 /**
- * rmi_rec_aux_count() - Get number of auxiliary granules required
- * @rd: PA of the RD
- * @aux_count: Number of granules written to this pointer
- *
- * A REC may require extra auxiliary granules to be delegated for the RMM to
- * store metadata (not visible to the normal world) in. This function provides
- * the number of granules that are required.
- *
- * Return: RMI return code
- */
-static inline int rmi_rec_aux_count(unsigned long rd, unsigned long *aux_count)
-{
-	struct arm_smccc_res res;
-
-	arm_smccc_1_1_invoke(SMC_RMI_REC_AUX_COUNT, rd, &res);
-
-	if (aux_count)
-		*aux_count = res.a1;
-	return res.a0;
-}
-
-/**
- * rmi_rec_create() - Create a REC
+ * rmi_rec_create_sro_init() - Init an SRO to create a REC
  * @rd: PA of the RD
  * @rec: PA of the target REC
  * @params: PA of REC parameters
@@ -440,33 +439,27 @@ static inline int rmi_rec_aux_count(unsigned long rd, unsigned long *aux_count)
  * Create a REC using the parameters specified in the struct rec_params pointed
  * to by @params.
  *
- * Return: RMI return code
+ * Returns: Allocated SRO object
  */
-static inline int rmi_rec_create(unsigned long rd, unsigned long rec,
-				 unsigned long params)
+static inline struct rmi_sro_state *
+rmi_rec_create_sro_init(unsigned long rd,
+			unsigned long rec,
+			unsigned long params)
 {
-	struct arm_smccc_res res;
-
-	arm_smccc_1_1_invoke(SMC_RMI_REC_CREATE, rd, rec, params, &res);
-
-	return res.a0;
+	return rmi_init_sro(SMC_RMI_REC_CREATE, rd, rec, params);
 }
 
 /**
- * rmi_rec_destroy() - Destroy a REC
+ * rmi_rec_destroy_sro_init() - Init an SRO to destroy a REC
  * @rec: PA of the target REC
  *
  * Destroys a REC. The REC must not be running.
  *
- * Return: RMI return code
+ * Return: Allocated SRO object
  */
-static inline int rmi_rec_destroy(unsigned long rec)
+static inline struct rmi_sro_state *rmi_rec_destroy_sro_init(unsigned long rec)
 {
-	struct arm_smccc_res res;
-
-	arm_smccc_1_1_invoke(SMC_RMI_REC_DESTROY, rec, &res);
-
-	return res.a0;
+	return rmi_init_sro(SMC_RMI_REC_DESTROY, rec);
 }
 
 /**
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 049d71470486..fa23818e1b4c 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -38,7 +38,6 @@
 #define SMC_RMI_PSCI_COMPLETE			SMC_RMI_CALL(0x0164)
 #define SMC_RMI_FEATURES			SMC_RMI_CALL(0x0165)
 #define SMC_RMI_RTT_FOLD			SMC_RMI_CALL(0x0166)
-#define SMC_RMI_REC_AUX_COUNT			SMC_RMI_CALL(0x0167) //
 #define SMC_RMI_RTT_INIT_RIPAS			SMC_RMI_CALL(0x0168)
 #define SMC_RMI_RTT_SET_RIPAS			SMC_RMI_CALL(0x0169)
 #define SMC_RMI_VSMMU_CREATE			SMC_RMI_CALL(0x016a)
@@ -180,11 +179,18 @@
 #define RMI_ADDR_TYPE_SINGLE		1
 #define RMI_ADDR_TYPE_LIST		2
 
-#define RMI_ADDR_RANGE_SIZE(ar)		(FIELD_GET(GENMASK(1, 0), (ar)))
-#define RMI_ADDR_RANGE_COUNT(ar)	(FIELD_GET(GENMASK(PAGE_SHIFT - 1, 2), \
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
 						   (ar)))
-#define RMI_ADDR_RANGE_ADDR(ar)		((ar) & PAGE_MASK & GENMASK(51, 0))
-#define RMI_ADDR_RANGE_STATE(ar)	(FIELD_GET(BIT(63), (ar)))
 
 enum rmi_ripas {
 	RMI_EMPTY = 0,
@@ -295,8 +301,6 @@ struct realm_params {
 
 #define REC_PARAMS_FLAG_RUNNABLE	BIT_ULL(0)
 
-#define REC_PARAMS_AUX_GRANULES		16
-
 struct rec_params {
 	union { /* 0x0 */
 		u64 flags;
@@ -312,14 +316,7 @@ struct rec_params {
 	};
 	union { /* 0x300 */
 		u64 gprs[REC_CREATE_NR_GPRS];
-		u8 padding3[0x500];
-	};
-	union { /* 0x800 */
-		struct {
-			u64 num_rec_aux;
-			u64 aux[REC_PARAMS_AUX_GRANULES];
-		};
-		u8 padding4[0x800];
+		u8 padding3[0xd00];
 	};
 };
 
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index e76e58762f55..10ff1c3bddaf 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -20,6 +20,295 @@ static unsigned long rmm_feat_reg1;
 
 #define RMM_L2_BLOCK_SIZE	PMD_SIZE
 
+static int delegate_range(phys_addr_t phys, unsigned long size);
+static int undelegate_range(phys_addr_t phys, unsigned long size);
+
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
+static int rmi_sro_donate_contig(struct rmi_sro_state *sro,
+				 unsigned long sro_handle,
+				 unsigned long donatereq,
+				 struct arm_smccc_1_2_regs *out_regs,
+				 gfp_t gfp)
+{
+	unsigned long unit_size = RMI_DONATE_SIZE(donatereq);
+	unsigned long count = RMI_DONATE_COUNT(donatereq);
+	unsigned long state = RMI_DONATE_STATE(donatereq);
+	unsigned long size;
+	unsigned long addr_range;
+	struct page *pages;
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
+	size = donate_req_to_size(donatereq) * count;
+
+	pages = alloc_pages(gfp, get_order(size));
+	if (!pages)
+		return -ENOMEM;
+	phys = page_to_phys(pages);
+
+	if (state == RMI_OP_MEM_DELEGATED) {
+		if (delegate_range(phys, size)) {
+			__free_pages(pages, get_order(size));
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
+
+	WARN_ON(donated_granules > 1);
+	if (WARN_ON(donated_granules == 0)) {
+		sro->addr_count++;
+		return 0;
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
+	unsigned long count = RMI_DONATE_COUNT(donatereq);
+	unsigned long state = RMI_DONATE_STATE(donatereq);
+	unsigned long found = 0;
+	unsigned long addr_list_start = sro->addr_count;
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
+	while (found < count) {
+		unsigned long addr_range;
+		unsigned long size = donate_req_to_size(donatereq);
+
+		struct page *pages = alloc_pages(gfp, get_order(size));
+		phys_addr_t phys;
+
+		if (!pages)
+			return -ENOMEM;
+
+		phys = page_to_phys(pages);
+
+		if (state == RMI_OP_MEM_DELEGATED) {
+			if (delegate_range(phys, size)) {
+				__free_pages(pages, get_order(size));
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
+	while (donated_granules < found) {
+		swap(sro->addr_list[addr_list_start++],
+		     sro->addr_list[--sro->addr_count]);
+		found--;
+	}
+	sro->addr_count -= donated_granules;
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
+	struct arm_smccc_1_2_regs regs = {
+		SMC_RMI_OP_MEM_RECLAIM,
+		sro_handle,
+		virt_to_phys(&sro->addr_list[sro->addr_count]),
+		RMI_MAX_ADDR_LIST - sro->addr_count
+	};
+	rmi_smccc_invoke(&regs, out_regs);
+	sro->addr_count += out_regs->a1;
+
+	return 0;
+}
+
+static void rmi_sro_free(struct rmi_sro_state *sro)
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
+			if (WARN_ON(undelegate_range(addr, size))) {
+				/* Leak the pages */
+				continue;
+			}
+		}
+		__free_pages(phys_to_page(addr), get_order(size));
+	}
+
+	sro->addr_count = 0;
+}
+
+DEFINE_FREE(sro, struct rmi_sro_state *, if (_T) rmi_sro_free(_T))
+
+static unsigned long rmi_sro_execute(struct rmi_sro_state *sro)
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
+		bool can_cancel = RMI_RETURN_CANCANCEL(regs.a0);
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
+					     GFP_KERNEL);
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
 static inline unsigned long rmi_rtt_level_mapsize(int level)
 {
 	if (WARN_ON(level > RMM_RTT_MAX_LEVEL))
@@ -795,12 +1084,6 @@ static int realm_create_rd(struct kvm *kvm)
 		goto out_undelegate_tables;
 	}
 
-	if (WARN_ON(rmi_rec_aux_count(rd_phys, &realm->num_aux))) {
-		WARN_ON(rmi_realm_destroy(rd_phys));
-		r = -ENXIO;
-		goto out_undelegate_tables;
-	}
-
 	realm->rd = rd;
 	WRITE_ONCE(realm->state, REALM_STATE_NEW);
 	/* The realm is up, free the parameters.  */
@@ -1432,65 +1715,9 @@ int noinstr kvm_rec_enter(struct kvm_vcpu *vcpu)
 	return ret;
 }
 
-static void free_rec_aux(struct page **aux_pages,
-			 unsigned int num_aux)
-{
-	unsigned int i;
-	unsigned int page_count = 0;
-
-	for (i = 0; i < num_aux; i++) {
-		struct page *aux_page = aux_pages[page_count++];
-		phys_addr_t aux_page_phys = page_to_phys(aux_page);
-
-		if (!WARN_ON(undelegate_page(aux_page_phys)))
-			__free_page(aux_page);
-		aux_page_phys += PAGE_SIZE;
-	}
-}
-
-static int alloc_rec_aux(struct page **aux_pages,
-			 u64 *aux_phys_pages,
-			 unsigned int num_aux)
-{
-	struct page *aux_page;
-	unsigned int i;
-	int ret;
-
-	for (i = 0; i < num_aux; i++) {
-		phys_addr_t aux_page_phys;
-
-		aux_page = alloc_page(GFP_KERNEL);
-		if (!aux_page) {
-			ret = -ENOMEM;
-			goto out_err;
-		}
-
-		aux_page_phys = page_to_phys(aux_page);
-		if (delegate_page(aux_page_phys)) {
-			ret = -ENXIO;
-			goto err_undelegate;
-		}
-		aux_phys_pages[i] = aux_page_phys;
-		aux_pages[i] = aux_page;
-	}
-
-	return 0;
-err_undelegate:
-	while (i > 0) {
-		i--;
-		if (WARN_ON(undelegate_page(aux_phys_pages[i]))) {
-			/* Leak the page if the undelegate fails */
-			goto out_err;
-		}
-	}
-	__free_page(aux_page);
-out_err:
-	free_rec_aux(aux_pages, i);
-	return ret;
-}
-
 static int kvm_create_rec(struct kvm_vcpu *vcpu)
 {
+	struct rmi_sro_state *sro __free(sro) = NULL;
 	struct user_pt_regs *vcpu_regs = vcpu_gp_regs(vcpu);
 	unsigned long mpidr = kvm_vcpu_get_mpidr_aff(vcpu);
 	struct realm *realm = &vcpu->kvm->arch.realm;
@@ -1538,18 +1765,17 @@ static int kvm_create_rec(struct kvm_vcpu *vcpu)
 		goto out_free_pages;
 	}
 
-	r = alloc_rec_aux(rec->aux_pages, params->aux, realm->num_aux);
-	if (r)
-		goto out_undelegate_rmm_rec;
-
-	params->num_rec_aux = realm->num_aux;
 	params->mpidr = mpidr;
 
-	if (rmi_rec_create(virt_to_phys(realm->rd),
-			   rec_page_phys,
-			   virt_to_phys(params))) {
+	sro = rmi_rec_create_sro_init(virt_to_phys(realm->rd),
+				      rec_page_phys, virt_to_phys(params));
+	if (!sro) {
+		r = -ENOMEM;
+		goto out_undelegate_rmm_rec;
+	}
+	if (rmi_sro_execute(sro)) {
 		r = -ENXIO;
-		goto out_free_rec_aux;
+		goto out_undelegate_rmm_rec;
 	}
 
 	rec->mpidr = mpidr;
@@ -1557,8 +1783,6 @@ static int kvm_create_rec(struct kvm_vcpu *vcpu)
 	free_page((unsigned long)params);
 	return 0;
 
-out_free_rec_aux:
-	free_rec_aux(rec->aux_pages, realm->num_aux);
 out_undelegate_rmm_rec:
 	if (WARN_ON(undelegate_page(rec_page_phys)))
 		rec->rec_page = NULL;
@@ -1572,7 +1796,7 @@ static int kvm_create_rec(struct kvm_vcpu *vcpu)
 
 void kvm_destroy_rec(struct kvm_vcpu *vcpu)
 {
-	struct realm *realm = &vcpu->kvm->arch.realm;
+	struct rmi_sro_state *sro __free(sro) = NULL;
 	struct realm_rec *rec = &vcpu->arch.rec;
 	unsigned long rec_page_phys;
 
@@ -1588,15 +1812,12 @@ void kvm_destroy_rec(struct kvm_vcpu *vcpu)
 
 	rec_page_phys = virt_to_phys(rec->rec_page);
 
-	/*
-	 * The REC and any AUX pages cannot be reclaimed until the REC is
-	 * destroyed. So if the REC destroy fails then the REC page and any AUX
-	 * pages will be leaked.
-	 */
-	if (WARN_ON(rmi_rec_destroy(rec_page_phys)))
+	sro = rmi_rec_destroy_sro_init(rec_page_phys);
+	if (WARN_ON(!sro))
 		return;
 
-	free_rec_aux(rec->aux_pages, realm->num_aux);
+	if (WARN_ON(rmi_sro_execute(sro)))
+		return;
 
 	free_delegated_page(rec_page_phys);
 }

---

## [50] Joey Gouly — 2026-03-18
*Subject: Re: [PATCH v13 04/48] arm64: RMI: Add SMC definitions for calling
 the RMM*

On Wed, Mar 18, 2026 at 03:53:28PM +0000, Steven Price wrote:
> The RMM (Realm Management Monitor) provides functionality that can be
> accessed by SMC calls from the host.

Both copyright and version (2.0 now) need updating.

Thanks,
Joey

> +
> +#ifndef __ASM_RMI_SMC_H

---

## [51] Steven Price — 2026-03-18
*Subject: Re: [PATCH v13 00/48] arm64: Support for Arm CCA in KVM*

And for those who like to use shrinkwrap the following YAML config
should work on top of the 2025.12.0 tag to pull the various repos. Save
the below as e.g. cca-v13.yaml and follow the usual instructions in
cca-3world.yaml but refer to cca-v13.yaml instead.

---8<---
%YAML 1.2
---
concrete: true

layers:
  - cca-3world.yaml

build:
  linux:
    repo:
      revision: cca-host/v13

  kvmtool:
    repo:
      kvmtool:
        revision: cca/v11

  tfa:
    params:
      RMM_V1_COMPAT: 0
    repo:
      revision: master

  rmm:
    repo:
      revision: topics/rmm-v2.0-poc

---

## [52] Steven Price — 2026-03-18
*Subject: Re: [PATCH v13 04/48] arm64: RMI: Add SMC definitions for calling the
 RMM*

On 18/03/2026 16:07, Joey Gouly wrote:
> On Wed, Mar 18, 2026 at 03:53:28PM +0000, Steven Price wrote:
>> The RMM (Realm Management Monitor) provides functionality that can be

Indeed they do! I didn't think anyone read these comments, but
apparently some people do (I obviously don't otherwise I might have
spotted this!) ;)

Thanks,
Steve

> Thanks,
> Joey

---

## [53] Joey Gouly — 2026-03-19
*Subject: Re: [PATCH v13 36/48] arm64: RMI: Always use 4k pages for realms*

Hi,

On Wed, Mar 18, 2026 at 03:54:00PM +0000, Steven Price wrote:
> Guest_memfd doesn't yet natively support huge pages, and there are
> currently difficulties for a VMM to manage huge pages efficiently so for

The commit title/message mention 4K, but should probably say PAGE_SIZE or
something now that RMM isn't fixed to 4K.

Thanks,
Joey

> 
> Signed-off-by: Steven Price <steven.price@arm.com>

---

## [54] Joey Gouly — 2026-03-19
*Subject: Re: [PATCH v13 37/48] arm64: RMI: Prevent Device mappings for Realms*

On Wed, Mar 18, 2026 at 03:54:01PM +0000, Steven Price wrote:
> Physical device assignment is not supported by RMM v1.0, so it

But we're targetting 2.0 now!

I guess just change it to something about device support being a later feature.

Thanks,
Joey

> doesn't make much sense to allow device mappings within the realm.
> Prevent them when the guest is a realm.

---

## [55] Suzuki K Poulose — 2026-03-19
*Subject: Re: [PATCH v13 10/48] arm64: RMI: Ensure that the RMM has GPT entries
 for memory*

Hi Steven

On 18/03/2026 15:53, Steven Price wrote:
> The RMM may not be tracking all the memory of the system at boot. Create

Looks good to me. Please find some suggestions below.


May be add a bit more context here :

RMM maintains the state of all the granules in the System to make sure
that the host is abiding by the rules. This state can be maintained at
different granularity - per PAGE (TRACKING_FINE) or per region (COARSE),
where the "region size" depends on the underlying "RMI_GRANULE_SIZE".
The state of the "tracked area" must be the same. This implies, we may
need to have "FINE" tracking for DRAM, so that we can start delegating
PAGEs. For now, we only support RMM with statically carved out memory
for tracking FINE granularity for the tracking regions. We will extend
the support for modifying the TRACKING region in the future.

Similarly, the firmware may create L0 GPT entries describing the total
address space (think of this as Block mappings in the page tables). But
if we change the "PAS" of a granule in the block mapping, we may need
to create L1 tables to track the PAS at the finer granularity. For now
we only support a system where the L1 GPTs are created at boot time
and dynamic GPT support will be added later.



> the necessary tracking state and GPTs within the RMM so that all boot
> memory can be delegated to the RMM as needed during runtime.

Probably this should be made a Kconfig option, like the VA_BITS we have 
today for each page size.

>   static int rmi_configure(void)
>   {

Could we add a comment what we are trying to do here ?

/*
  * Make sure the area is tracked by RMM at FINE granularity.
  * We do not support changing the TRACKING yet. This will
  * be added in the future.
  */


> +{
> +	start = ALIGN_DOWN(start, RMM_GRANULE_TRACKING_SIZE);

How about adding a comment here explaining why we look for RMI_ERROR_GPT ?


>
		/*
		 * Make sure the L1 GPT tables are created for the region.
		 * RMI_ERROR_GPT indicates the L1 table exists.
		 */
  +
> +		if (ret && ret != RMI_ERROR_GPT) {


> +			/*
> +			 * FIXME: Handle SRO so that memory can be donated for

---

## [56] Suzuki K Poulose — 2026-03-19
*Subject: Re: [PATCH v13 07/48] arm64: RMI: Check for RMI support at KVM init*

On 18/03/2026 15:53, Steven Price wrote:
> Query the RMI version number and check if it is a compatible version. A
> static key is also provided to signal that a supported RMM is available.


--8>---

> +
> +static inline bool kvm_is_realm(struct kvm *kvm)


--8<---

Minor nit: The above looks out of place in this patch. Could we
move it to where this may be actually used ?

Rest looks good to me.


> +void kvm_init_rmi(void);
> +

---

## [57] Suzuki K Poulose — 2026-03-19
*Subject: Re: [PATCH v13 10/48] arm64: RMI: Ensure that the RMM has GPT entries
 for memory*

On 18/03/2026 15:53, Steven Price wrote:
> The RMM may not be tracking all the memory of the system at boot. Create
> the necessary tracking state and GPTs within the RMM so that all boot

This is a little bit vague. Should we explicitly mention :

"For now we set the tracking_region_size to 0 for RMI_RMM_CONFIG_SET()"


> + * TODO: Support other granule sizes

nit: s/granule/Tracking/

Suzuki


> + */
> +#ifdef CONFIG_PAGE_SIZE_4KB

---

## [58] Steven Price — 2026-03-19
*Subject: Re: [PATCH v13 07/48] arm64: RMI: Check for RMI support at KVM init*

On 19/03/2026 10:38, Suzuki K Poulose wrote:
> On 18/03/2026 15:53, Steven Price wrote:
>> Query the RMI version number and check if it is a compatible version. A

Yes, good point. This can be moved to patch 12 quite easily. I think
originally I'd needed this earlier on, but the code's moved on.

Thanks,
Steve

> Rest looks good to me.
>

---

## [59] Suzuki K Poulose — 2026-03-19
*Subject: Re: [PATCH v13 13/48] kvm: arm64: Don't expose unsupported
 capabilities for realm guests*

On 18/03/2026 15:53, Steven Price wrote:
> From: Suzuki K Poulose <suzuki.poulose@arm.com>
> 

We need a similar check in in kvm_vm_ioctl_enable_cap() to prevent 
enabling the filtered caps ? Otherwise looks good to me.

Suzuki

>   	switch (ext) {
>   	case KVM_CAP_IRQCHIP:

---

## [60] Steven Price — 2026-03-19
*Subject: Re: [PATCH v13 10/48] arm64: RMI: Ensure that the RMM has GPT entries
 for memory*

On 19/03/2026 10:31, Suzuki K Poulose wrote:
> Hi Steven
> 

Thanks for the wording - that does indeed make things clearer. SRO
support will effectively enable the "future" items.

>> the necessary tracking state and GPTs within the RMM so that all boot
>> memory can be delegated to the RMM as needed during runtime.

Yes that's probably a good option - note that for 4k page size there is
only the one option in the spec. So this is only relevant for 16K/64K.

Thanks for the other comment suggestions below (and in the other email)
- all good points.

Thanks,
Steve

>>   static int rmi_configure(void)
>>   {

---

## [61] Steven Price — 2026-03-19
*Subject: Re: [PATCH v13 13/48] kvm: arm64: Don't expose unsupported
 capabilities for realm guests*

On 19/03/2026 14:09, Suzuki K Poulose wrote:
> On 18/03/2026 15:53, Steven Price wrote:
>> From: Suzuki K Poulose <suzuki.poulose@arm.com>

Indeed - thanks for spotting.

Thanks,
Steve

> Suzuki
>

---

## [62] Steven Price — 2026-03-19
*Subject: Re: [PATCH v13 36/48] arm64: RMI: Always use 4k pages for realms*

On 19/03/2026 10:24, Joey Gouly wrote:
> Hi,
> 

Indeed - this is all PAGE_SIZE not 4k any more. Also hopefully the
reasons for this patch are also going to disappear soon. (2) above isn't
really very true any more (we do support mmap() from guest_memfd).

Thanks,
Steve

> Thanks,
> Joey

---

## [63] Wei-Lin Chang — 2026-03-19
*Subject: Re: [PATCH v13 12/48] arm64: RMI: Basic infrastructure for creating
 a realm.*

On Wed, Mar 18, 2026 at 03:53:36PM +0000, Steven Price wrote:
> Introduce the skeleton functions for creating and destroying a realm.
> The IPA size requested is checked against what the RMM supports.

Hi,

I believe we can do:

struct kvm *kvm = kvm_s2_mmu_to_kvm(mmu);

to avoid introducing the extra argument.
But in order for that to work we'll have to initialize mmu->arch
earlier:

diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index 8c5d259810b2..e98da7bde9a0 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -974,6 +974,7 @@ int kvm_init_stage2_mmu(struct kvm *kvm, struct kvm_s2_mmu *mmu, unsigned long t
 		return -EINVAL;
 	}
 
+	mmu->arch = &kvm->arch;
 	err = kvm_init_ipa_range(mmu, type);
 	if (err)
 		return err;
@@ -982,7 +983,6 @@ int kvm_init_stage2_mmu(struct kvm *kvm, struct kvm_s2_mmu *mmu, unsigned long t
 	if (!pgt)
 		return -ENOMEM;
 
-	mmu->arch = &kvm->arch;
 	err = KVM_PGT_FN(kvm_pgtable_stage2_init)(pgt, mmu, &kvm_s2_mm_ops);
 	if (err)
 		goto out_free_pgtable;

Thanks,
Wei-Lin Chang

>  	if (type & ~KVM_VM_TYPE_ARM_IPA_SIZE_MASK)
>  		return -EINVAL;

---

## [64] Wei-Lin Chang — 2026-03-19
*Subject: Re: [PATCH v13 07/48] arm64: RMI: Check for RMI support at KVM init*

On Wed, Mar 18, 2026 at 03:53:31PM +0000, Steven Price wrote:
> Query the RMI version number and check if it is a compatible version. A
> static key is also provided to signal that a supported RMM is available.

Hi,

Both kvm_vm_is_protected() and vcpu_is_protected() are in kvm_host.h, do
you think that's a better place? Or is there a reason for this being in
kvm_emulate.h?

Thanks,
Wei-Lin Chang

>  #endif /* __ARM64_KVM_EMULATE_H__ */
> diff --git a/arch/arm64/include/asm/kvm_host.h b/arch/arm64/include/asm/kvm_host.h

---

## [65] Steven Price — 2026-03-19
*Subject: Re: [PATCH v13 12/48] arm64: RMI: Basic infrastructure for creating a
 realm.*

On 19/03/2026 16:11, Wei-Lin Chang wrote:
> On Wed, Mar 18, 2026 at 03:53:36PM +0000, Steven Price wrote:
>> Introduce the skeleton functions for creating and destroying a realm.

Nice - I hadn't noticed that I could just pull the mmu->arch assignment
up and avoid that extra argument.

Thanks,
Steve

> 
> Thanks,

---

## [66] Steven Price — 2026-03-19
*Subject: Re: [PATCH v13 07/48] arm64: RMI: Check for RMI support at KVM init*

On 19/03/2026 16:17, Wei-Lin Chang wrote:
> On Wed, Mar 18, 2026 at 03:53:31PM +0000, Steven Price wrote:
>> Query the RMI version number and check if it is a compatible version. A

I've no strong opinions, but as usual there are complications with the
header include order.

kvm_vm_is_protected/vcpu_is_protected are defined in asm/kvm_host.h, but
struct kvm is defined in linux/kvm_host.h (which includes
asm/kvm_host.h). The same is true for struct kvm_vcpu. This means that
we can't have a static inline function using the kvm pointer (because
the struct definition hasn't been reached). The 'solution' in the case
of kvm_vm_is_protected/vcpu_is_protected is to use a macro - which works
but has drawbacks (e.g. lack of type checking).

I'll move them if there's a strong feeling they are in the wrong place,
but to me it feels more like the macros in asm/kvm_host.h are just a
hack to get around them being in the wrong place.

Thanks,
Steve

> Thanks,
> Wei-Lin Chang

---

## [67] Wei-Lin Chang — 2026-03-19
*Subject: Re: [PATCH v13 12/48] arm64: RMI: Basic infrastructure for creating
 a realm.*

On Wed, Mar 18, 2026 at 03:53:36PM +0000, Steven Price wrote:
> Introduce the skeleton functions for creating and destroying a realm.
> The IPA size requested is checked against what the RMM supports.

Hi,

Sorry I missed one nit: perhaps call this kvm_init_realm()? So these two
look like a pair. There are also no realm_vm in other function names.

Thanks,
Wei-Lin Chang

>  
>  #endif /* __ASM_KVM_RMI_H */

---

## [68] Wei-Lin Chang — 2026-03-19
*Subject: Re: [PATCH v13 15/48] arm64: RMI: RTT tear down*

On Wed, Mar 18, 2026 at 03:53:39PM +0000, Steven Price wrote:
> The RMM owns the stage 2 page tables for a realm, and KVM must request
> that the RMM creates/destroys entries as necessary. The physical pages

Hi,

I see that kvm_free_stage2_pgd() will be called twice:

kvm_destroy_vm()
  mmu_notifier_unregister()
    kvm_mmu_notifier_release()
      kvm_flush_shadow_all()
        kvm_arch_flush_shadow_all()
          kvm_uninit_stage2_mmu()
            kvm_free_stage2_pgd()
  kvm_arch_destroy_vm()
    kvm_destroy_realm()
      kvm_free_stage2_pgd()

At the first call the realm state is REALM_STATE_ACTIVE, at the second
it is REALM_STATE_DEAD. Reading the comment added to
kvm_free_stage2_pgd() here, does it mean this function is called twice
on purpose? If so do you think it's better to extract this and create
another function instead, then use kvm_is_realm() to choose which to
run? I think it is confusing to have this function run twice for a
realm.

Thanks,
Wei-Lin Chang

>  	if (pgt) {
>  		mmu->pgd_phys = 0;

---

## [69] Suzuki K Poulose — 2026-03-19
*Subject: Re: [PATCH v13 46/48] KVM: arm64: Expose KVM_ARM_VCPU_REC to user
 space*

On 18/03/2026 15:54, Steven Price wrote:
> Increment KVM_VCPU_MAX_FEATURES to expose the new capability to user
> space.

Not needed any more as we don't need the VCPU feature.

Cheers
Suzuki



> ---
> Changes since v8:

---

## [70] Wei-Lin Chang — 2026-03-19
*Subject: Re: [PATCH v13 07/48] arm64: RMI: Check for RMI support at KVM init*

On Wed, Mar 18, 2026 at 03:53:31PM +0000, Steven Price wrote:
> Query the RMI version number and check if it is a compatible version. A
> static key is also provided to signal that a supported RMM is available.

Hi,

Do you think it would be helpful to have a write version of this?
That way we can search for the write version to see all the locations of
realm state changes, instead of having to search through all the
WRITE_ONCE()'s.

Thanks,
Wei-Lin Chang

> +
> +static inline bool vcpu_is_rec(struct kvm_vcpu *vcpu)

---

## [71] Wei-Lin Chang — 2026-03-19
*Subject: Re: [PATCH v13 17/48] arm64: RMI: Allocate/free RECs to match vCPUs*

On Wed, Mar 18, 2026 at 03:53:41PM +0000, Steven Price wrote:
> The RMM maintains a data structure known as the Realm Execution Context
> (or REC). It is similar to struct kvm_vcpu and tracks the state of the

Hi,

Are these two hunks superfluous?

Thanks,
Wei-Lin Chang

>  		return -EINVAL;
>

---

## [72] Wei-Lin Chang — 2026-03-19
*Subject: Re: [PATCH v13 26/48] arm64: RMI: Create the realm descriptor*

On Wed, Mar 18, 2026 at 03:53:50PM +0000, Steven Price wrote:
> Creating a realm involves first creating a realm descriptor (RD). This
> involves passing the configuration information to the RMM. Do this as

Hi,

Should this be GFP_KERNEL_ACCOUNT?

> +	if (!rd)
> +		return -ENOMEM;

Did you mean kvm->arch.mmu.pgd_phys = NULL; ?

Thanks,
Wei-Lin Chang

> +	}
> +	if (WARN_ON(undelegate_page(rd_phys))) {

---

## [73] Wei-Lin Chang — 2026-03-19
*Subject: Re: [PATCH v13 27/48] arm64: RMI: Runtime faulting of memory*

On Wed, Mar 18, 2026 at 03:53:51PM +0000, Steven Price wrote:
> At runtime if the realm guest accesses memory which hasn't yet been
> mapped then KVM needs to either populate the region or fault the guest.

I think we should use gpa_t as the type for ipa.

> +{
> +	if (!kvm_is_realm(kvm))

Hi,

Thus is -> Thus if.

> +		 * the GPA then it is the private alias.
> +		 */

Maybe use !shared_ipa_fault() here?

Thanks,
Wei-Lin Chang

> +		ret = -EINVAL;
> +

---

## [74] Wei-Lin Chang — 2026-03-19
*Subject: Re: [PATCH v13 37/48] arm64: RMI: Prevent Device mappings for Realms*

On Wed, Mar 18, 2026 at 03:54:01PM +0000, Steven Price wrote:
> Physical device assignment is not supported by RMM v1.0, so it
> doesn't make much sense to allow device mappings within the realm.

Hi,

What is private_memslot_fault()? I don't see it anywhere in the series &
upstream.

> +	 * relaxed to support e.g. protected devices.
> +	 */

Additionally, there is a hunk almost identical to this one here in added
in patch 27.

Thanks,
Wei-Lin Chang

>  	if (nested)
>  		adjust_nested_fault_perms(nested, &prot, &writable);

---

## [75] Wei-Lin Chang — 2026-03-19
*Subject: Re: [PATCH v13 39/48] arm64: RMI: Propagate number of breakpoints
 and watchpoints to userspace*

On Wed, Mar 18, 2026 at 03:54:03PM +0000, Steven Price wrote:
> From: Jean-Philippe Brucker <jean-philippe@linaro.org>
> 

Hi,

Nit:
In other places we condition on kvm_is_realm() to separate
realm/non-realm paths but here everyone goes into kvm_realm_*, do you
think it's more consistent to move the kvm_is_realm() check out of this
function?

Thanks,
Wei-Lin Chang

>  }
>

---

## [76] Wei-Lin Chang — 2026-03-19
*Subject: Re: [PATCH v13 45/48] arm64: RMI: Provide accurate register list*

On Wed, Mar 18, 2026 at 03:54:09PM +0000, Steven Price wrote:
> From: Jean-Philippe Brucker <jean-philippe@linaro.org>
> 

Hi,

Same as my comment for patch 39, I would suggest moving the
kvm_is_realm() check out of this function.

Thanks,
Wei-Lin Chang

> +		return 0;
> +

---

## [77] Wei-Lin Chang — 2026-03-19
*Subject: Re: [PATCH v13 23/48] KVM: arm64: Expose support for private memory*

On Wed, Mar 18, 2026 at 03:53:47PM +0000, Steven Price wrote:
> Select KVM_GENERIC_MEMORY_ATTRIBUTES and provide the necessary support
> functions.

Hi,

I believe we should also add this:

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index bfa0ab343081..13722f876dcd 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -6365,7 +6365,7 @@ Returns -EINVAL if called on a protected VM.
 -------------------------------
 
 :Capability: KVM_CAP_MEMORY_ATTRIBUTES
-:Architectures: x86
+:Architectures: x86, arm64
 :Type: vm ioctl
 :Parameters: struct kvm_memory_attributes (in)
 :Returns: 0 on success, <0 on error

Thanks,
Wei-Lin Chang

>  	help
>  	  Support hosting virtualized guest machines.

---

## [78] Mathieu Poirier — 2026-03-19
*Subject: Re: [PATCH v13 00/48] arm64: Support for Arm CCA in KVM*

Good day,

On Wed, Mar 18, 2026 at 03:53:24PM +0000, Steven Price wrote:
> This series adds support for running protected VMs using KVM under the
> Arm Confidential Compute Architecture (CCA).

This RMM version is expecting a RMM EL3 interface version of at least 2.0.  Do
you have a TF-A to use with it?

Thanks,
Mathieu

> 
> [1] https://developer.arm.com/documentation/den0137/2-0bet0/

---

## [79] Suzuki K Poulose — 2026-03-20
*Subject: Re: [PATCH v13 15/48] arm64: RMI: RTT tear down*

On 18/03/2026 15:53, Steven Price wrote:
> The RMM owns the stage 2 page tables for a realm, and KVM must request
> that the RMM creates/destroys entries as necessary. The physical pages

-->

> +#define RMM_RTT_BLOCK_LEVEL	2
...
> +
> +#define RMM_L2_BLOCK_SIZE	PMD_SIZE

<--

Unused ? Even better we could use PMD_SIZE directly if at all we need
it, as we are using PAGE_SIZE


minor nit: Also, may be we can have a generic name for the 
RMM_RTT_MAX_LEVEL ? This applies to all page tables ?

I see we have KVM_PGTALBE_LAST_LEVEL, may be we could use that ?


> +
> +static inline unsigned long rmi_rtt_level_mapsize(int level)


How about a comment here for the function below ?

Something like :

/*
  * realm_rtt_destroy: Destroy an RTT at @level for @addr.
  *
  * Returns - Result of the RMI_RTT_DESTROY call, additionally :
  *  @out_rtt  : RTT granule, if the RTT was destroyed.
  *  @next_addr: IPA corresponding to the next possible valid Table entry
  *		we can target.
  */
> +
> +static int realm_rtt_destroy(struct realm *realm, unsigned long addr,

AFAICS, we already WARN_ON() in all the cases where the
realm_tear_down_rtt_range() fails, so may be we can skip this
WARN_ON here ?

Suzuki

> +}
> +

---

## [80] Suzuki K Poulose — 2026-03-20
*Subject: Re: [PATCH v13 21/48] arm64: RMI: Handle RMI_EXIT_RIPAS_CHANGE*

Hi Steven

On 18/03/2026 15:53, Steven Price wrote:
> The guest can request that a region of it's protected address space is
> switched between RIPAS_RAM and RIPAS_EMPTY (and back) using

I have been thinking about this. Today we do a KVM_MEMORY_FAULT_EXIT
to the VMM to handle the request. The other option is to make this
a KVM_EXIT_HYPERCALL with SMC_RSI_SET_RIPAS. But this would leak RSI
implementation to the VMM. The advantage is that the VMM can provide
a clear response RSI_ACCEPT vs RSI_REJECT (including accepting a partial
range) and KVM can satisfy the RMI_RTT_SET_RIPAS.

We may end up doing something similar for Device assignment too, where
the VMM gets a chance to reject any inconsistent device mappings.

Like you mentioned, the VMM can stop the Realm today as an alternate
approach.

Suzuki

> 
> There's a FIXME for the case where the RMM rejects a RIPAS change when

---

## [81] Suzuki K Poulose — 2026-03-20
*Subject: Re: [PATCH v13 20/48] arm64: RMI: Handle realm enter/exit*

On 18/03/2026 15:53, Steven Price wrote:
> Entering a realm is done using a SMC call to the RMM. On exit the
> exit-codes need to be handled slightly differently to the normal KVM

The RMM has been fixed to indicate the correct value in ESR_ELx_SRT. So
this could be :
		vcpu_set_reg(vcpu, rt, rec->run->ext.gprs[rt]); ?

> +
> +	ret = kvm_handle_sys_reg(vcpu);

Same here ^

> +
> +	return ret;

Even ESR_EL2 is only valid when the exit reason is RMI_EXIT_SYNC or 
RMI_EXIT_SERROR.
Doing this unconditional copying is fine, as long as we don't consume
the esr_el2 in exit handling without consulting the exit reason, which
may not be available to the rest of the KVM. It may be safer to set it
to 0 ?


> +	vcpu->arch.fault.far_el2 = rec->run->exit.far;
> +	/* HPFAR_EL2 is only valid for RMI_EXIT_SYNC */

RMI_EXIT_SERROR is missing in the list above.

> +	}
> +



> +	vcpu->run->exit_reason = KVM_EXIT_INTERNAL_ERROR;
> +	return 0;

In the normal VM case, we try to fixup some of the exits (e.g., GIC 
CPUIF register accesses) which may be applicable to Realms. Do we
need such fixups here ? Given the cost of world switch, it is
debatable whether it matters or not.

Suzuki
> +	guest_state_exit_irqoff();
> +

---

## [82] Steven Price — 2026-03-20
*Subject: Re: [PATCH v13 07/48] arm64: RMI: Check for RMI support at KVM init*

On 19/03/2026 18:05, Wei-Lin Chang wrote:
> On Wed, Mar 18, 2026 at 03:53:31PM +0000, Steven Price wrote:
>> Query the RMI version number and check if it is a compatible version. A

Hi,

> Do you think it would be helpful to have a write version of this?
> That way we can search for the write version to see all the locations of

Yes that's a reasonable request. Like you say it would make it much
easier to search for the places that update the state.

Thanks,
Steve

> Thanks,
> Wei-Lin Chang

---

## [83] Steven Price — 2026-03-20
*Subject: Re: [PATCH v13 12/48] arm64: RMI: Basic infrastructure for creating a
 realm.*

On 19/03/2026 17:17, Wei-Lin Chang wrote:
> On Wed, Mar 18, 2026 at 03:53:36PM +0000, Steven Price wrote:
>> Introduce the skeleton functions for creating and destroying a realm.

Makes sense, thanks for the suggestion.

Thanks,
Steve

> Thanks,
> Wei-Lin Chang

---

## [84] Steven Price — 2026-03-20
*Subject: Re: [PATCH v13 15/48] arm64: RMI: RTT tear down*

On 19/03/2026 17:35, Wei-Lin Chang wrote:
> On Wed, Mar 18, 2026 at 03:53:39PM +0000, Steven Price wrote:
>> The RMM owns the stage 2 page tables for a realm, and KVM must request

So the issue here is that the RMM requires we do things in a different
order to a normal VM. For a realm the PGD cannot be destroyed until the
realm itself is destroyed - the RMM revent the host undelegating them.

So the first call cannot actually do the free - this is the
REALM_STATE_ACTIVE case.

In kvm_destroy_realm() we tear down the actual realm and undelegate the
granules. We then need to actually free the PGD - the "obvious" way of
doing that is calling kvm_free_stage2_pgd() as that handles the KVM
intricacies - e.g. updating the mmu object.

I'm not sure how to structure the code better without causing
duplication - I don't want another copy of the cleanup from
kvm_free_stage2_pgd() in a CCA specific file because it will most likely
get out of sync with the normal VM case. There is a comment added
explaining "we call this again" which I hoped would make it less confusing.

Thanks,
Steve

> Thanks,
> Wei-Lin Chang

---

## [85] Steven Price — 2026-03-20
*Subject: Re: [PATCH v13 15/48] arm64: RMI: RTT tear down*

On 20/03/2026 10:37, Suzuki K Poulose wrote:
> On 18/03/2026 15:53, Steven Price wrote:
>> The RMM owns the stage 2 page tables for a realm, and KVM must request

They are used in realm_map_protected() to calculate 'map_level'. But
actually I should be able to drop that use. With the range-based APIs
there's no longer a need to create a temporary RTT when populating a
huge-page.

> 
> minor nit: Also, may be we can have a generic name for the

Yes that would work - thanks for the suggestion.

> 
>> +

Sure

>> +
>> +static int realm_rtt_destroy(struct realm *realm, unsigned long addr,

So we do - yes this WARN_ON is unnecessary.

Thanks,
Steve

> Suzuki
>

---

## [86] Steven Price — 2026-03-20
*Subject: Re: [PATCH v13 17/48] arm64: RMI: Allocate/free RECs to match vCPUs*

On 19/03/2026 18:10, Wei-Lin Chang wrote:
> On Wed, Mar 18, 2026 at 03:53:41PM +0000, Steven Price wrote:
>> The RMM maintains a data structure known as the Realm Execution Context

Ah, yes that's left over from a previous version - thanks for spotting.

Thanks,
Steve

> Thanks,
> Wei-Lin Chang

---

## [87] Steven Price — 2026-03-20
*Subject: Re: [PATCH v13 20/48] arm64: RMI: Handle realm enter/exit*

On 20/03/2026 14:08, Suzuki K Poulose wrote:
> On 18/03/2026 15:53, Steven Price wrote:
>> Entering a realm is done using a SMC call to the RMM. On exit the

True, although no functional change because it's always going to be 0.

>> +
>> +    return ret;

For HPFAR_EL2 there is code in the kernel which hijacks the EL2_NS bit a
'valid' bit, hence we have to handle that one specially to record
whether the value is valid or not.

esr_el2/far_el2 may or may not be valid depending on the exit, but
there's no 'valid' flag for the generic kernel code to look for - so
that generic code either depends on the value (in which case 0 is just
as invalid) or doesn't use it.

My preference is to avoid trying to keep track of the exit reasons where
such flags are valid and just provide the generic code with whatever the
RMM provides. In any case the values are generally 'sanitised' by the
RMM so they don't represent the real CPU registers.

>> +    vcpu->arch.fault.far_el2 = rec->run->exit.far;
>> +    /* HPFAR_EL2 is only valid for RMI_EXIT_SYNC */

Indeed, I think I need to read up on how that's meant to be handled.

>> +    }
>> +

I'm not really sure what you are referring to here. Can you point me at
the normal VM case? This function is the equivalent of
kvm_arm_vcpu_enter_exit().

Thanks,
Steve

> Suzuki
>> +    guest_state_exit_irqoff();

---

## [88] Steven Price — 2026-03-20
*Subject: Re: [PATCH v13 23/48] KVM: arm64: Expose support for private memory*

On 19/03/2026 19:01, Wei-Lin Chang wrote:
> On Wed, Mar 18, 2026 at 03:53:47PM +0000, Steven Price wrote:
>> Select KVM_GENERIC_MEMORY_ATTRIBUTES and provide the necessary support

Good spot.

Thanks,
Steve

> 
> Thanks,

---

## [89] Steven Price — 2026-03-20
*Subject: Re: [PATCH v13 26/48] arm64: RMI: Create the realm descriptor*

On 19/03/2026 18:25, Wei-Lin Chang wrote:
> On Wed, Mar 18, 2026 at 03:53:50PM +0000, Steven Price wrote:
>> Creating a realm involves first creating a realm descriptor (RD). This

Yes that would be better.

>> +	if (!rd)
>> +		return -ENOMEM;

No, although I agree this isn't exactly ideal. kvm_free_stage2_pgd()
uses mmu->pgt to decide whether to free the memory - pgd_phys isn't used
in that path. Technically here we end up leaking more than just the PGD
pages in this case, but as it's a "should never happen" case I didn't
see the need to worry about the leak being a bit larger than necessary.

Thanks,
Steve

> Thanks,
> Wei-Lin Chang

---

## [90] Steven Price — 2026-03-20
*Subject: Re: [PATCH v13 27/48] arm64: RMI: Runtime faulting of memory*

On 19/03/2026 18:41, Wei-Lin Chang wrote:
> On Wed, Mar 18, 2026 at 03:53:51PM +0000, Steven Price wrote:
>> At runtime if the realm guest accesses memory which hasn't yet been

This is just matching the usage in mmu.c, e.g. user_mem_abort() has
fault_ipa as a phys_addr_t.

>> +{
>> +	if (!kvm_is_realm(kvm))

Ack

>> +		 * the GPA then it is the private alias.
>> +		 */

Ack.

Thanks,
Steve

> 
> Thanks,

---

## [91] Steven Price — 2026-03-20
*Subject: Re: [PATCH v13 37/48] arm64: RMI: Prevent Device mappings for Realms*

On 19/03/2026 18:46, Wei-Lin Chang wrote:
> On Wed, Mar 18, 2026 at 03:54:01PM +0000, Steven Price wrote:
>> Physical device assignment is not supported by RMM v1.0, so it

Oh dear, that comment is out of date ;) It's now become gmem_abort()...

>> +	 * relaxed to support e.g. protected devices.
>> +	 */

Which is what this chunk says. It appears I screwed up a rebase at some
point! This whole patch can really be dropped and the
kvm_phys_addr_ioremap() change moved into another patch.

Thanks,
Steve

> Thanks,
> Wei-Lin Chang

---

## [92] Steven Price — 2026-03-20
*Subject: Re: [PATCH v13 39/48] arm64: RMI: Propagate number of breakpoints and
 watchpoints to userspace*

On 19/03/2026 18:50, Wei-Lin Chang wrote:
> On Wed, Mar 18, 2026 at 03:54:03PM +0000, Steven Price wrote:
>> From: Jean-Philippe Brucker <jean-philippe@linaro.org>

Yes I agree that would be more consistent.

Thanks,
Steve

> Thanks,
> Wei-Lin Chang

---

## [93] Steven Price — 2026-03-20
*Subject: Re: [PATCH v13 45/48] arm64: RMI: Provide accurate register list*

On 19/03/2026 18:53, Wei-Lin Chang wrote:
> On Wed, Mar 18, 2026 at 03:54:09PM +0000, Steven Price wrote:
>> From: Jean-Philippe Brucker <jean-philippe@linaro.org>

Sure, although at least this time the functions were right next to each
other ;)

Thanks,
Steve

> Thanks,
> Wei-Lin Chang

---

## [94] Steven Price — 2026-03-20
*Subject: Re: [PATCH v13 00/48] arm64: Support for Arm CCA in KVM*

On 19/03/2026 23:02, Mathieu Poirier wrote:
> Good day,
> 

You should be able to use the 'master' branch of the TF-A repository.
For now you need to set RMM_V1_COMPAT=0 to enable 2.0 support.

Thanks,
Steve

> Thanks,
> Mathieu

---

## [95] Mathieu Poirier — 2026-03-20
*Subject: Re: [PATCH v13 00/48] arm64: Support for Arm CCA in KVM*

On Fri, Mar 20, 2026 at 04:45:49PM +0000, Steven Price wrote:
> On 19/03/2026 23:02, Mathieu Poirier wrote:
> > Good day,

That worked - thanks for the clarification.
 
> Thanks,
> Steve

---

## [96] Wei-Lin Chang — 2026-03-21
*Subject: Re: [PATCH v13 15/48] arm64: RMI: RTT tear down*

On Fri, Mar 20, 2026 at 04:12:48PM +0000, Steven Price wrote:
> On 19/03/2026 17:35, Wei-Lin Chang wrote:
> > On Wed, Mar 18, 2026 at 03:53:39PM +0000, Steven Price wrote:

Oh, I see, thanks for letting me know!

During this I found in the first call of kvm_free_stage2_pgd() it's doing
kvm_stage2_unmap_range() and kvm_realm_destroy_rtts(), but they are also
called in kvm_destroy_realm(), is that intentional?
If they can be called at kvm_destroy_realm() time, could we just not do
kvm_free_stage2_pgd() in kvm_uninit_stage2_mmu() for realms?
And if they should be called in kvm_free_stage2_pgd(), could we refactor
it to something like:
(just showing the idea, didn't try compiling or anything)

diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index 7d7caab8f573..280d2bef8492 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -1030,9 +1030,25 @@ int kvm_init_stage2_mmu(struct kvm *kvm, struct kvm_s2_mmu *mmu, unsigned long t
 	return err;
 }
 
+static void kvm_realm_uninit_stage2(struct kvm_s2_mmu *mmu)
+{
+	struct kvm *kvm = kvm_s2_mmu_to_kvm(mmu);
+	struct realm *realm = &kvm->arch.realm;
+
+	WARN_ON(kvm_realm_state(kvm) != REALM_STATE_ACTIVE);
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
+
 	kvm_mmu_free_memory_cache(&kvm->arch.mmu.split_page_cache);
 }
 
@@ -1117,22 +1133,7 @@ void kvm_free_stage2_pgd(struct kvm_s2_mmu *mmu)
 
 	write_lock(&kvm->mmu_lock);
 	pgt = mmu->pgt;
-	if (kvm_is_realm(kvm) &&
-	    (kvm_realm_state(kvm) != REALM_STATE_DEAD &&
-	     kvm_realm_state(kvm) != REALM_STATE_NONE)) {
-		struct realm *realm = &kvm->arch.realm;
-
-		kvm_stage2_unmap_range(mmu, 0, BIT(realm->ia_bits - 1), true);
-		write_unlock(&kvm->mmu_lock);
-		kvm_realm_destroy_rtts(kvm);
 
-		/*
-		 * The PGD pages can be reclaimed only after the realm (RD) is
-		 * destroyed. We call this again from kvm_destroy_realm() after
-		 * the RD is destroyed.
-		 */
-		return;
-	}
 	if (pgt) {
 		mmu->pgd_phys = 0;
 		mmu->pgt = NULL;

Sorry if I missed anything!

Thanks,
Wei-Lin Chang

> Thanks,
> Steve

---

## [97] Marc Zyngier — 2026-03-21
*Subject: Re: [PATCH v13 05/48] arm64: RMI: Temporarily add SMCs from RMM v1.0 spec*

On Wed, 18 Mar 2026 15:53:29 +0000,
Steven Price <steven.price@arm.com> wrote:
> 
> Not all the functionality has been migrated to the v2.0 specification,

This sort of things really makes it awkward to review the series.

Do you really expect the reviewers to mentally triage what is current
and what is only throwaway code? I want to see patches that are merge
candidates, not patches that are only there to cope with the broken
state of the RMM.

If extra hacks are required to work with the current Franken-RMM, keep
them as a separate series that doesn't pollute what is targeted at
upstream.

It also means that any testing you have done will be invalidated when
the one true RMM shows up...

"This is great."

	M.

---

## [98] Wei-Lin Chang — 2026-03-21
*Subject: Re: [PATCH v13 26/48] arm64: RMI: Create the realm descriptor*

On Fri, Mar 20, 2026 at 04:41:12PM +0000, Steven Price wrote:
> On 19/03/2026 18:25, Wei-Lin Chang wrote:
> > On Wed, Mar 18, 2026 at 03:53:50PM +0000, Steven Price wrote:

Thank you for the clarification.

Thanks,
Wei-Lin Chang

> 
> Thanks,

---

## [99] Wei-Lin Chang — 2026-03-21
*Subject: Re: [PATCH v13 37/48] arm64: RMI: Prevent Device mappings for Realms*

On Fri, Mar 20, 2026 at 04:45:07PM +0000, Steven Price wrote:
> On 19/03/2026 18:46, Wei-Lin Chang wrote:
> > On Wed, Mar 18, 2026 at 03:54:01PM +0000, Steven Price wrote:

Ah no wonder!

Thanks,
Wei-Lin Chang

> 
> >> +	 * relaxed to support e.g. protected devices.

---

## [100] Wei-Lin Chang — 2026-03-21
*Subject: Re: [PATCH v13 12/48] arm64: RMI: Basic infrastructure for creating
 a realm.*

On Wed, Mar 18, 2026 at 03:53:36PM +0000, Steven Price wrote:
> Introduce the skeleton functions for creating and destroying a realm.
> The IPA size requested is checked against what the RMM supports.

Hi,

Question:
Since kvm_stage2_destroy() is only called for non-realm VMs, then where
does the root level RTT pages get freed?
After searching for a while I feel like it is missed, but I am not
certain.

Thanks,
Wei-Lin Chang

>  		kfree(pgt);
>  	}

---

## [101] Suzuki K Poulose — 2026-03-23
*Subject: Re: [PATCH v13 20/48] arm64: RMI: Handle realm enter/exit*

On 20/03/2026 16:32, Steven Price wrote:
> On 20/03/2026 14:08, Suzuki K Poulose wrote:
>> On 18/03/2026 15:53, Steven Price wrote:

This happens via fixup_guest_exit() in either vhe/nvhe cases. The VGIC
registers are emulated in the fast path for normal VMs (when trapping is
enabled)


Cheers
Suzuki

> 
> Thanks,

---

## [102] Suzuki K Poulose — 2026-03-23
*Subject: Re: [PATCH v13 05/48] arm64: RMI: Temporarily add SMCs from RMM v1.0
 spec*

Hi Marc,

On 21/03/2026 13:21, Marc Zyngier wrote:
> On Wed, 18 Mar 2026 15:53:29 +0000,
> Steven Price <steven.price@arm.com> wrote:

I agree, that this makes it painful to review as it doesn't get you a
clear picture of what will stay or what will change and is not the best
use of the precious time of the Maintainers. We will make sure to flag
the appropriate portions in the next iteration. Apologies!

> 
> Do you really expect the reviewers to mentally triage what is current

Agree, we could clearly mark the "areas" of code that we anticipate to
change and by the next posting this will be clearly marked.


> If extra hacks are required to work with the current Franken-RMM, keep
> them as a separate series that doesn't pollute what is targeted at

In fact there are only a few areas that would change with a true RMM-
v2.0 spec compliant firmware. But yes, I acknowledge that feedback from
the maintainers would be fedback to the RMM spec and this might trigger
minor changes to align with them.

> 
> It also means that any testing you have done will be invalidated when

Agreed,  True, but not very much of the functionality/
spec are changing until we land in fully compliant 2.0 RMM.
See more on this below.

> 
> "This is great."


> diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
> index 8a42b83218f8..049d71470486 100644


> +#define SMC_RMI_RTT_MAP_UNPROTECTED		SMC_RMI_CALL(0x015f) //
>  


The above two RMI commands help with mapping/unmapping Unprotected
memory and will be replaced with two renamed commands with "Range based"
ABI => SMC_RMI_RTT_UNPROT_{MAP,UNMAP}. So, as far as the KVM code is
concerned, we do the mapping a granule at a time (without hugetlb
support) and this is simply a change in the command in the true 2.0 RMM.



>  #define SMC_RMI_RTT_DEV_VALIDATE		SMC_RMI_CALL(0x0163)
>  #define SMC_RMI_PSCI_COMPLETE			SMC_RMI_CALL(0x0164)

This is part of the REC creation, where we donate AUXilliary granules 
for the VCPU to save state. This is replaced by the SRO method, which we 
have a WIP path at the top of the series and it will be cleaned up in
the next version.

We wanted to send this version out which is the first one with RMM-v2.0
spec, which has addressed the concerns and feedback around the RMM-v1.0
spec. But we have clearly felt short of marking "what is volatile" and 
what is stable, to help the review. We will address this in the next 
iteration.

Thanks for taking the time to respond.

Kind regards
Suzuki

---

## [103] Suzuki K Poulose — 2026-03-23
*Subject: Re: [PATCH v13 24/48] arm64: RMI: Allow populating initial contents*

On 18/03/2026 15:53, Steven Price wrote:
> The VMM needs to populate the realm with some data before starting (e.g.
> a kernel and initrd). This is measured by the RMM and used as part of

minor nit: To align with the RMM ABI, could we rename this to :

	realm_data_map_init() ?

> +					    unsigned long ipa,
> +					    kvm_pfn_t dst_pfn,

A buggy VMM can trigger this by calling RMI_POPULATE twice ? Should we
return -ENXIO here rather ? The delegate_page() above could prevent
normal cases, but is the VMM allowed to somehow trigger a "pfn" change
backing the KVM ? Either way, this need not be Fatal ?

Otherwise looks good to me.

Suzuki


> +
> +		ret = realm_create_rtt_levels(realm, ipa, level,

---

## [104] Suzuki K Poulose — 2026-03-23
*Subject: Re: [PATCH v13 17/48] arm64: RMI: Allocate/free RECs to match vCPUs*

Hi,

This is a NOTE for the fellow reviewers. This patch will undergo some
changes to handle how the AUX granules (metadata storage for RMM) for
the REC (aka vCPU) will be donated/reclaimed with RMM-v2.0.


Please see PATCH 48/48 for the changes with the new Stateful RMI
Operations (SRO), for REC create and destory.

I have tried to mark the areas affected below.


On 18/03/2026 15:53, Steven Price wrote:
> The RMM maintains a data structure known as the Realm Execution Context
> (or REC). It is similar to struct kvm_vcpu and tracks the state of the

--->8--- Cut here

> +static void free_rec_aux(struct page **aux_pages,
> +			 unsigned int num_aux)

---8<---




> +static int kvm_create_rec(struct kvm_vcpu *vcpu)
> +{

...

---8>--- CUT here

> +	r = alloc_rec_aux(rec->aux_pages, params->aux, realm->num_aux);
> +	if (r)

---8<---

> +	params->mpidr = mpidr;
> +


> +
> +	rec->mpidr = mpidr;

--8>-- Cut here

> +	/*
> +	 * The REC and any AUX pages cannot be reclaimed until the REC is

---8<---


Suzuki



> +
> +	free_delegated_page(rec_page_phys);

---

## [105] Gavin Shan — 2026-03-25
*Subject: Re: [PATCH v13 00/48] arm64: Support for Arm CCA in KVM*

Hi Steven,

On 3/19/26 1:53 AM, Steven Price wrote:
> 
> This series is based on v7.0-rc1. It is also available as a git

Could you please share if we have a working qemu repository on top of this
(v13) series? The previous qemu repository [1] seems out of dated for long
time. I heard Jean won't be able to continue his efforts on QEMU part, who
is going to pick it up in this case.

[1] https://git.codelinaro.org/linaro/dcap/qemu.git    (branch: cca/latest)

> Note that the kvmtool code has been tidied up (thanks to Suzuki) and
> this involves a minor change in flags. The "--restricted_mem" flag is no

I'm seeing error to initialize RMM with the suggested RMM branch (topics/rmm-v2.0-poc)
and the upstream TF-A [1]. It seems the problem is compatible issue in the
RMM-EL3 interface. RMM requires verion 2.0 while TF-A only supports 0.8. So
I guess I must be using a wrong TF-A repository. Could you please share which
TF-A repository you use for testing?

[1] git@github.com:ARM-software/arm-trusted-firmware.git    (branch: master)

Booting logs
=============
NOTICE:  Booting Trusted Firmware
NOTICE:  BL1: v2.14.0(debug):67edb4f8e
NOTICE:  BL1: Built : 00:01:39, Mar 25 2026
INFO:    BL1: RAM 0xe0ee000 - 0xe0f7000
INFO:    BL1: Loading BL2
INFO:    Loading image id=1 at address 0xe05b000
INFO:    Image id=1 loaded: 0xe05b000 - 0xe0642bc
NOTICE:  BL1: Booting BL2
INFO:    Entry point address = 0xe05b000
INFO:    SPSR = 0x3cd
NOTICE:  BL2: v2.14.0(debug):67edb4f8e
NOTICE:  BL2: Built : 00:01:39, Mar 25 2026
INFO:    BL2: Doing platform setup
INFO:    Reserved RMM memory [0x40100000, 0x418fffff] in Device tree
INFO:    BL2: Loading image id 3
INFO:    Loading image id=3 at address 0xe090000
INFO:    Image id=3 loaded: 0xe090000 - 0xe0a292b
INFO:    BL2: Loading image id 35
INFO:    Loading image id=35 at address 0x40100000
INFO:    Image id=35 loaded: 0x40100000 - 0x401a11e0
INFO:    BL2: Loading image id 5
INFO:    Loading image id=5 at address 0x60000000
INFO:    Image id=5 loaded: 0x60000000 - 0x60200000
NOTICE:  BL2: Booting BL31
INFO:    Entry point address = 0xe090000
INFO:    SPSR = 0x3cd
INFO:    GPT: Boot Configuration
INFO:      PPS/T:     0x2/40
INFO:      PGS/P:     0x0/12
INFO:      L0GPTSZ/S: 0x0/30
INFO:      PAS count: 6
INFO:      L0 base:   0xedfe000
INFO:    Enabling Granule Protection Checks
NOTICE:  BL31: v2.14.0(debug):67edb4f8e
NOTICE:  BL31: Built : 00:01:39, Mar 25 2026
INFO:    GICv3 without legacy support detected.
INFO:    ARM GICv3 driver initialized in EL3
INFO:    Maximum SPI INTID supported: 287
INFO:    BL31: Initializing runtime services
INFO:    RMM setup done.
INFO:    BL31: Initializing RMM
INFO:    RMM init start.
ERROR:   RMM init failed: -2                           <<<< Error raised by RMM here
WARNING: BL31: RMM initialization failed
INFO:    BL31: Preparing for EL3 exit to normal world
INFO:    Entry point address = 0x60000000
INFO:    SPSR = 0x3c9
UEFI firmware (version  built at 19:33:51 on Mar  3 2026)


Thanks,
Gavin

---

## [106] Gavin Shan — 2026-03-25
*Subject: Re: [PATCH v13 00/48] arm64: Support for Arm CCA in KVM*

Hi Steven,

On 3/21/26 2:45 AM, Steven Price wrote:
> On 19/03/2026 23:02, Mathieu Poirier wrote:

[...]

>>>
>>> The TF-RMM has not yet merged the RMMv2.0 support, so you will need to

In upstream TF-A repository [1], I don't see the config option 'RMM_V1_COMPAT'.
would it be something else?

[1] git@github.com:ARM-software/arm-trusted-firmware.git    (branch: master)

I use the following command to build TF-A image. The RMM-EL3 compatible issue is
still seen.

     TFA_PATH=$PWD
     EDK2_IMAGE=${TFA_PATH}/../edk2/Build/ArmVirtQemuKernel-AARCH64/RELEASE_GCC5/FV/QEMU_EFI.fd
     RMM_IMAGE=${TFA_PATH}/../tf-rmm/build-qemu/Debug/rmm.img
     
     make CROSS_COMPILE=aarch64-none-elf-                               \
          PLAT=qemu ENABLE_RME=1 RMM_V1_COMPAT=0 DEBUG=1 LOG_LEVEL=40   \
          QEMU_USE_GIC_DRIVER=QEMU_GICV3                                \
          BL33=${EDK2_IMAGE} RMM=${RMM_IMAGE}                           \
          -j 8 all fip

Booting messages
================
INFO:    BL31: Initializing runtime services
INFO:    RMM setup done.
INFO:    BL31: Initializing RMM
INFO:    RMM init start.
ERROR:   RMM init failed: -2
WARNING: BL31: RMM initialization failed

Thanks,
Gavin

---

## [107] Suzuki K Poulose — 2026-03-25
*Subject: Re: [PATCH v13 00/48] arm64: Support for Arm CCA in KVM*

Hi Gavin

Steven is on holidays, so I am jumping in here.

On 25/03/2026 06:37, Gavin Shan wrote:
> Hi Steven,
> 

suzuki@ewhatever:trusted-firmware-a$ git grep RMM_V1_COMPAT
Makefile:       RMM_V1_COMPAT \
Makefile:       RMM_V1_COMPAT \
docs/getting_started/build-options.rst:-  ``RMM_V1_COMPAT``: Boolean 
flag to enable support for RMM v1.x compatibility
include/services/rmmd_svc.h:#if RMM_V1_COMPAT
include/services/rmmd_svc.h:#endif /* RMM_V1_COMPAT */
make_helpers/defaults.mk:RMM_V1_COMPAT                  := 1
services/std_svc/rmmd/rmmd_main.c:#if RMM_V1_COMPAT
services/std_svc/rmmd/rmmd_main.c:#if RMM_V1_COMPAT
services/std_svc/rmmd/rmmd_main.c:#if !RMM_V1_COMPAT
services/std_svc/rmmd/rmmd_main.c:#if RMM_V1_COMPAT
services/std_svc/rmmd/rmmd_main.c:#if RMM_V1_COMPAT
services/std_svc/rmmd/rmmd_main.c:#if RMM_V1_COMPAT
services/std_svc/rmmd/rmmd_rmm_lfa.c:#if RMM_V1_COMPAT
services/std_svc/rmmd/rmmd_rmm_lfa.c:#if RMM_V1_COMPAT
services/std_svc/rmmd/rmmd_rmm_lfa.c:#if RMM_V1_COMPAT
services/std_svc/rmmd/rmmd_rmm_lfa.c:#if RMM_V1_COMPAT
suzuki@ewhatever:trusted-firmware-a$ git log --oneline -1
8dae0862c (HEAD, origin/master, origin/integration, origin/HEAD) Merge 
changes from topic "qti_lemans_evk" into integration
suzuki@ewhatever:trusted-firmware-a$ git remote get-url origin
https://git.trustedfirmware.org/TF-A/trusted-firmware-a.git



> I use the following command to build TF-A image. The RMM-EL3 compatible 
> issue is




> Booting messages
> ================

This is definitely the TF-A RMM incompatibility.

Btw, the shrinkwrap overlay configs in tf-RMM repository should work.
But unfortunately the Linux/kvmtool repositories are pointing to
internal repositories. The following patch should fix it and get
it all working. I am working with the tf-rmm team to fix this.



--8>--

diff --git a/tools/shrinkwrap/configs/cca.yaml 
b/tools/shrinkwrap/configs/cca.yaml
index 1c0455ba..0d70a582 100644
--- a/tools/shrinkwrap/configs/cca.yaml
+++ b/tools/shrinkwrap/configs/cca.yaml
@@ -25,8 +25,8 @@ build:

    linux:
      repo:
-      remote: https://gitlab.geo.arm.com/software/linux-arm/fkvm.git
-      revision: stepri01/cca/v13-wip+sro
+      remote: https://gitlab.arm.com/linux-arm/linux-cca
+      revision: cca-host/v13
      prebuild:
        - ./scripts/config --file ${param:builddir}/.config --enable 
CONFIG_PCI_TSM
        - ./scripts/config --file ${param:builddir}/.config --enable 
CONFIG_PCI_DOE
@@ -50,5 +50,5 @@ build:
          remote: https://git.kernel.org/pub/scm/utils/dtc/dtc.git
          revision: v1.7.2
        kvmtool:
-        remote: https://gitlab.geo.arm.com/software/linux-arm/fkvmtool.git
-        revision: stepri01/cca/v13-wip
+        remote: https://gitlab.arm.com/linux-arm/kvmtool-cca
+        revision: cca/v11



Kind regards
Suzuki


> 
> Thanks,

---

## [108] Suzuki K Poulose — 2026-03-25
*Subject: Re: [PATCH v13 00/48] arm64: Support for Arm CCA in KVM*

Hi Gavin

On 25/03/2026 04:07, Gavin Shan wrote:
> Hi Steven,
> 

Unfortunately not at the moment. We have moved on to a simpler UABI,
which drops most of the previous configuration steps.

> 
>> Note that the kvmtool code has been tidied up (thanks to Suzuki) and

See the other thread with Mathieu.

Kind regards
Suzuki

---

## [109] Suzuki K Poulose — 2026-03-25
*Subject: Re: [PATCH v13 00/48] arm64: Support for Arm CCA in KVM*

On 25/03/2026 10:16, Suzuki K Poulose wrote:
> Hi Gavin
> 

This is now fixed in the branch :

https://git.trustedfirmware.org/plugins/gitiles/TF-RMM/tf-rmm/+/refs/heads/topics/rmm-v2.0-poc/tools/shrinkwrap/configs/cca.yaml

Cheers
Suzuki

---

## [110] Gavin Shan — 2026-03-26
*Subject: Re: [PATCH v13 00/48] arm64: Support for Arm CCA in KVM*

Hi Suzuki,

On 3/25/26 8:16 PM, Suzuki K Poulose wrote:
> On 25/03/2026 06:37, Gavin Shan wrote:
>> On 3/21/26 2:45 AM, Steven Price wrote:

[...]

>>
>> In upstream TF-A repository [1], I don't see the config option 'RMM_V1_COMPAT'.

Thanks for the details. It turned out that I used the wrong TF-A repository. In
the proposed repository, I'm able to see the option 'RMM_V1_COMPAT' and the EL3-RMM
interface compatible issue disappears. However, there are more issues popped up.

I build everything manually where the host is emulated by QEMU instead of shrinkwrap
and FVP model. It's used to work well before. Maybe it's time to switch to shinkwrap
and FVP model since device assignment (DA) isn't supported by an emulated host
by QEMU and shrinkwrap and FVP model seems the only option. I need to learn how
to do that later.

There are two issues I can see with the following combinations. Details are provided
like below.

     QEMU:      https://git.qemu.org/git/qemu.git                            (branch: stable-9.2)
     TF-RMM:    https://git.trustedfirmware.org/TF-RMM/tf-rmm.git            (branch: topics/rmm-v2.0-poc)
     EDK2:      git@github.com:tianocore/edk2.git                            (tag:    edk2-stable202411)
     TF-A:      https://git.trustedfirmware.org/TF-A/trusted-firmware-a.git  (branch: master)
     HOST:      https://git.gitlab.arm.com/linux-arm/linux-cca.git           (branch: cca-host/v13)
     BUILDROOT: https://github.com/buildroot/buildroot                       (branch: master)
     KVMTOOL:   https://gitlab.arm.com/linux-arm/kvmtool-cca                 (branch: cca/v11)
     GUEST:     https://github.com/torvalds/linux.git                        (branch: master)

(1) The emulated host is started by the following command lines.

     sudo /home/gshan/sandbox/cca/host/qemu/build/qemu-system-aarch64                  \
     -M virt,virtualization=on,secure=on,gic-version=3,acpi=off                        \
     -cpu max,x-rme=on -m 8G -smp 8                                                    \
     -serial mon:stdio -monitor none -nographic -nodefaults                            \
     -bios /home/gshan/sandbox/cca/host/tf-a/flash.bin                                 \
     -kernel /home/gshan/sandbox/cca/host/linux/arch/arm64/boot/Image                  \
     -initrd /home/gshan/sandbox/cca/host/buildroot/output/images/rootfs.cpio.xz       \
     -device pcie-root-port,bus=pcie.0,chassis=1,id=pcie.1                             \
     -device pcie-root-port,bus=pcie.0,chassis=2,id=pcie.2                             \
     -device pcie-root-port,bus=pcie.0,chassis=3,id=pcie.3                             \
     -device pcie-root-port,bus=pcie.0,chassis=4,id=pcie.4                             \
     -device virtio-9p-device,fsdev=shr0,mount_tag=shr0                                \
     -fsdev local,security_model=none,path=/home/gshan/sandbox/cca/guest,id=shr0       \
     -netdev tap,id=tap1,script=/etc/qemu-ifup-gshan,downscript=/etc/qemu-ifdown-gshan \
     -device virtio-net-pci,bus=pcie.2,netdev=tap1,mac=b8:3f:d2:1d:3e:f1

(2) Issue-1: TF-RMM complains about the root complex list is invalid. This error is
     raised in TF-RMM::setup_root_complex_list() where the error code is still set to
     0 (SUCCESS) in this failing case. The TF-RMM initialization is terminated early,
     but TF-A still thinks the initialization has been completely done.

     INFO:    BL31: Initializing RMM
     INFO:    RMM init start.
     RMM EL3 compat memory reservation enabled.
     Dynamic VA pool base address: 0xc0000000
     Reserved 20 pages. Remaining: 3615 pages
     Reserve mem: 20 pages at PA: 0x401f2000 (alignment 0x1000)
     Static Low VA initialized. xlat tables allocated: 20 used: 7
     Reserved 514 pages. Remaining: 3101 pages
     Reserve mem: 514 pages at PA: 0x40206000 (alignment 0x1000)
     Dynamic Low VA initialized. xlat tables allocated: 514 used: 514
     Invalid: Root Complex list                                         <<<<< ERROR
     INFO:    RMM init end.

(3) Issue-2: The host kernel gets stuck in rmi_check_version() where SMC_RMI_VERSION
     is issued to TF-A, but it can't be forwarded to TF-RMM because its initialization
     isn't completely done (issue-1).

     [   37.438253] Unpacking initramfs...
     [   37.563460] kvm [1]: nv: 570 coarse grained trap handlers
     [   37.581139] kvm [1]: nv: 664 fine grained trap handlers
     <... system becomes stuck here ...>

So my workaround is to skip fetching root complex list from the EL3-RMM manifest data
in TF-RMM::setup_root_complex_list() since it's not provided for the qemu platform by
TF-A. With this workaround, the host can boot up into shell prompt and the guest can
be started by kvmtool.

     host$ uname -r
     7.0.0-rc1-gavin-gd62aa44b2590
     host$ lkvm run --realm -c 2 -m 256                   \
           -k /mnt/linux/arch/arm64/boot/Image            \
           -i /mnt/buildroot/output/images/rootfs.cpio.xz
           -p earlycon=uart,mmio,0x101000000
     Info: # lkvm run -k /mnt/linux/arch/arm64/boot/Image -m 256 -c 2 --name guest-163
     Info: Enabling Guest memfd for confidential guest
     Warning: The maximum recommended amount of VCPUs is 1
     [    0.000000] Booting Linux on physical CPU 0x0000000000 [0x000f0510]
     [    0.000000] Linux version 7.0.0-rc2-gavin-g0031c06807cf (gshan@nvidia-grace-hopper-01.khw.eng.bos2.dc.redhat.com) (gcc (GCC) 14.3.1 20251022 (Red Hat 14.3.1-4), GNU ld version 2.41-64.el10) #2 SMP PREEMPT Wed Mar 25 20:28:05 EDT 2026
     [    0.000000] KASLR enabled
          :
     [  267.578060] Freeing initrd memory: 4728K
     [  267.921865] Warning: unable to open an initial console.
     [  270.327960] Freeing unused kernel memory: 1792K
     [  270.669368] Run /init as init process

Thanks,
Gavin

---

## [111] Suzuki K Poulose — 2026-03-26
*Subject: Re: [PATCH v13 00/48] arm64: Support for Arm CCA in KVM*

Hi Gavin,

On 26/03/2026 00:48, Gavin Shan wrote:
> Hi Suzuki,
> 

Thanks for the update. Yes, QEMU TF-RMM support is in progress, @Mathieu 
Poirier is looking into it

> 
> There are two issues I can see with the following combinations. Details 

^^ This may have to do with the RMM<->TF-A Manifest changes


> TF-A. With this workaround, the host can boot up into shell prompt and 
> the guest can

Cool, thanks!

Suzuki

> Thanks,
> Gavin

---

## [112] Suzuki K Poulose — 2026-03-30
*Subject: Re: [PATCH v13 30/48] KVM: arm64: Handle Realm PSCI requests*

On 18/03/2026 15:53, Steven Price wrote:
> The RMM needs to be informed of the target REC when a PSCI call is made
> with an MPIDR argument. Expose an ioctl to the userspace in case the PSCI

This will need to stay for the PSCI_CPU_ON case, where the host has to
acknowledge the onlining of a vCPU.

> 
> Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>

For the record, we can drop the UAPI following our discussions and 
implicitly do the PSCI complete before REC_ENTER, similar to what
we do for the SET_RIPAS request. The VMM/KVM can treat the case
as a normal PSCI_CPU_ON request and return the result as in normal
VMs.

The target REC may ENTER before we complete the reporting, but we can
handle this error case (RMI_ERROR_REC) and return -EAGAIN to the
userspace.

Suzuki


> ---
> Changes since v12:

---

## [113] Suzuki K Poulose — 2026-03-30
*Subject: Re: [PATCH v13 31/48] KVM: arm64: WARN on injected undef exceptions*

On 18/03/2026 15:53, Steven Price wrote:
> The RMM doesn't allow injection of a undefined exception into a realm
> guest. Add a WARN to catch if this ever happens.

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>


> ---
> Changes since v6:

---

## [114] Suzuki K Poulose — 2026-03-30
*Subject: Re: [PATCH v13 32/48] arm64: Don't expose stolen time for realm
 guests*

On 18/03/2026 15:53, Steven Price wrote:
> It doesn't make much sense as a realm guest wouldn't want to trust the
> host. It will also need some extra work to ensure that KVM will only

Could this be handled in kvm_realm_ext_allowed() ?

Suzuki


>   		break;
>   	case KVM_CAP_ARM_EL1_32BIT:

---

## [115] Suzuki K Poulose — 2026-03-30
*Subject: Re: [PATCH v13 34/48] arm64: RMI: support RSI_HOST_CALL*

On 18/03/2026 15:53, Steven Price wrote:
> From: Joey Gouly <joey.gouly@arm.com>
> 

Minor nit: Please could we add a line or two, explaining what 
RSI_HOST_CALL is ? e.g.:

Realm's can talk to the hypervisor using the RSI_HOST_CALL, which
the RMM forwards to the KVM. Handle them as regular hypercalls.

Suzuki

> 
> Signed-off-by: Joey Gouly <joey.gouly@arm.com>

Probably we should move the RMI_EXIT_HOST_CALL case addition in 
kvm_rec_pre_enter() to this hunk to keep all in one place ?

Otherwise, looks good to me.

Suzuki


>   
>   	kvm_pr_unimpl("Unsupported exit reason: %u\n",

---

## [116] Mathieu Poirier — 2026-03-30
*Subject: Re: [PATCH v13 10/48] arm64: RMI: Ensure that the RMM has GPT
 entries for memory*

Hi,

On Wed, Mar 18, 2026 at 03:53:34PM +0000, Steven Price wrote:
> The RMM may not be tracking all the memory of the system at boot. Create
> the necessary tracking state and GPTs within the RMM so that all boot

This will produce an error on systems where the start of system memory is not
aligned to RMM_GRANULE_TRACKING_SIZE.  For instance, on QEMU-SBSA the system
memory starts at 0x100_4300_0000.  With the above and RMM_GRANULE_TRACKING_SIZE
set to SZ_1G, @start becomes 0x100_4000_0000, which falls outside the memory map
known to the TF-A.  I fixed it with these modifications:

LINUX:

diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 10ff1c3bddaf..21bfbbe2f047 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -424,7 +424,9 @@ static int rmi_configure(void)
 
 static int rmi_verify_memory_tracking(phys_addr_t start, phys_addr_t end)
 {
-       start = ALIGN_DOWN(start, RMM_GRANULE_TRACKING_SIZE);
+       phys_addr_t offset;
+
+       offset = start - ALIGN_DOWN(start, RMM_GRANULE_TRACKING_SIZE);
        end = ALIGN(end, RMM_GRANULE_TRACKING_SIZE);
 
        while (start < end) {
@@ -439,7 +441,13 @@ static int rmi_verify_memory_tracking(phys_addr_t start, phys_addr_t end)
                                start);
                        return -ENODEV;
                }
-               start += RMM_GRANULE_TRACKING_SIZE;
+
+               if (offset) {
+                       start += (RMM_GRANULE_TRACKING_SIZE - offset);
+                       offset = 0;
+               } else {
+                       start += RMM_GRANULE_TRACKING_SIZE;
+               }
        }
 
        return 0;

RMM:

diff --git a/runtime/rmi/granule.c b/runtime/rmi/granule.c
index cef521fc0869..60358d9ee81e 100644
--- a/runtime/rmi/granule.c
+++ b/runtime/rmi/granule.c
@@ -209,9 +209,11 @@ void smc_granule_tracking_get(unsigned long addr,
                return;
        }
 
+#if 0
        if (!ALIGNED(addr, RMM_INTERNAL_TRACKING_REGION_SIZE)) {
                return;
        }
+#endif
 
        g = find_granule(addr);
        if (g != NULL) {

This is likely not the right fix but hopefully provides some guidance.  Send me
your patches when you have an idea and I'll test them.

Thanks,
Mathieu


> +	end = ALIGN(end, RMM_GRANULE_TRACKING_SIZE);
> +

---

## [117] Suzuki K Poulose — 2026-03-31
*Subject: Re: [PATCH v13 10/48] arm64: RMI: Ensure that the RMM has GPT entries
 for memory*

Hi Mathieu,

On 30/03/2026 21:58, Mathieu Poirier wrote:
> Hi,
> 

Thanks for raising this. This would need to be addressed in the RMM
spec, I have raised it with the team and will be addressed soon.

> 
> LINUX:

We will send you the update once it is fixed in the RMM spec. The rough 
idea is to remove the ALIGNMENT restrictions and return a Range that
the host can iterate over to find "regions" with the same type of
memory.


Cheers
Suzuki


> 
> Thanks,

---

## [118] Mathieu Poirier — 2026-03-31
*Subject: Re: [PATCH v13 10/48] arm64: RMI: Ensure that the RMM has GPT
 entries for memory*

On Tue, Mar 31, 2026 at 12:05:47PM +0100, Suzuki K Poulose wrote:
> Hi Mathieu,
> 

Ok, thanks for looking into this.
 
> 
> Cheers

---

## [119] Steven Price — 2026-04-01
*Subject: Re: [PATCH v13 12/48] arm64: RMI: Basic infrastructure for creating a
 realm.*

On 21/03/2026 16:34, Wei-Lin Chang wrote:
> On Wed, Mar 18, 2026 at 03:53:36PM +0000, Steven Price wrote:
>> Introduce the skeleton functions for creating and destroying a realm.

You're absolutely right. I do have a bug fix locally for this:

diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index 9cfb8c434aa5..3e55c1ff046c 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -1148,6 +1148,8 @@ void kvm_free_stage2_pgd(struct kvm_s2_mmu *mmu)
        if (pgt) {
                if (!kvm_is_realm(kvm))
                        kvm_stage2_destroy(pgt);
+               else
+                       kvm_pgtable_stage2_destroy_pgd(pgt);
                kfree(pgt);
        }
 }

The issue here is that we don't want to talk the tables (because they
will have been scrubbed by the RMM), but I apparently forgot to add the
call to free the actual memory.

Thanks,
Steve

> Thanks,
> Wei-Lin Chang

---

## [120] Steven Price — 2026-04-10
*Subject: Re: [PATCH v13 15/48] arm64: RMI: RTT tear down*

On 21/03/2026 13:04, Wei-Lin Chang wrote:
> On Fri, Mar 20, 2026 at 04:12:48PM +0000, Steven Price wrote:
>> On 19/03/2026 17:35, Wei-Lin Chang wrote:

No I don't think you've missed anything, that actually does look nicer.
Thanks for the suggestion.

Thanks,
Steve

---

## [121] Steven Price — 2026-04-10
*Subject: Re: [PATCH v13 20/48] arm64: RMI: Handle realm enter/exit*

On 23/03/2026 10:03, Suzuki K Poulose wrote:
> On 20/03/2026 16:32, Steven Price wrote:
>> On 20/03/2026 14:08, Suzuki K Poulose wrote:

[...]

>>>> +int noinstr kvm_rec_enter(struct kvm_vcpu *vcpu)
>>>> +{

Ah, I see what you mean. Yes the VGIC emulation in theory could be
shortcut and speeded up slightly. I'd prefer to leave this sort of pure
optimisation until the basic support is merged to keep the size of the
series (vaguely) under control.

I think it would also be worth doing some benchmarking on a real
platform to see whether it really makes a meaningful difference (or
whether we need to push for an architectural change moving more
processing into the RMM).

Thanks,
Steve

---

## [122] Steven Price — 2026-04-10
*Subject: Re: [PATCH v13 21/48] arm64: RMI: Handle RMI_EXIT_RIPAS_CHANGE*

On 20/03/2026 11:15, Suzuki K Poulose wrote:
> Hi Steven
> 

Faking up hypercalls based on a very narrow interface seems like a bad
API design. The guest is of course perfectly allowed to have another
interface directly to the VMM to communicate intent.

> We may end up doing something similar for Device assignment too, where
> the VMM gets a chance to reject any inconsistent device mappings.
The intention here is that we start with a very basic interface and can
then extend it when we work out how to handle rejection. The ordering in
the kernel is explicitly to allow that extension. I get the impression
that device assignment has a much better justification for handling the
reject flow so it's probably best to leave that until device assignment
is implemented.

Thanks,
Steve

---

## [123] Steven Price — 2026-04-10
*Subject: Re: [PATCH v13 24/48] arm64: RMI: Allow populating initial contents*

On 23/03/2026 11:32, Suzuki K Poulose wrote:
> On 18/03/2026 15:53, Steven Price wrote:
>> The VMM needs to populate the realm with some data before starting (e.g.

Makes sense - I have to admit there is a bit of cruft in some of the
names because the spec keeps changing ;)

>> +                        unsigned long ipa,
>> +                        kvm_pfn_t dst_pfn,

I believe KVM_BUG_ON is only fatal to the VM - it won't take down the
host (KVM_BUG_ON_DATA_CORRUPTION() is for that). AFAICT the
delegate_page() check should catch this case, but in the event that it
doesn't then this will kill the VM but otherwise recover.

Of course if it turns out there is a way of a VMM hitting this we might
need to tone down the error handling to something a bit quieter. But I
think it would also be good to get an understanding of how this can happen.

Thanks,
Steve

> Otherwise looks good to me.
>

---

## [124] Steven Price — 2026-04-10
*Subject: Re: [PATCH v13 32/48] arm64: Don't expose stolen time for realm
 guests*

On 30/03/2026 11:52, Suzuki K Poulose wrote:
> On 18/03/2026 15:53, Steven Price wrote:
>> It doesn't make much sense as a realm guest wouldn't want to trust the

Indeed it is already handled there. I'm not sure how I missed that, but
this patch is completely unnecessary now. Stolen time was an extension
that I knew about (having added it in the first place) and needed
disabling because it's implemented with the assumption that the host can
write into the guest.

In theory with some extra work it could be supported in a realm guest,
but it requires some extra plumbing to ensure the structures end up in
shared memory. My intention is that this can be revisited once the basic
CCA support is in.

Thanks,
Steve

> Suzuki
>

---

## [125] Steven Price — 2026-04-10
*Subject: Re: [PATCH v13 37/48] arm64: RMI: Prevent Device mappings for Realms*

On 19/03/2026 10:27, Joey Gouly wrote:
> On Wed, Mar 18, 2026 at 03:54:01PM +0000, Steven Price wrote:
>> Physical device assignment is not supported by RMM v1.0, so it

Whoops ;) In my head it's still "in the future" but I guess the "future" 
is now!

I'll update this to say:

    Physical device assignment is not yet supported. RMM v2.0 does add the
    relevant APIs, but device assignment is a big topic so will be handled
    in a future patch series. For now prevent device mappings when the guest
    is a realm.

Thanks,
Steve

> I guess just change it to something about device support being a later feature.
>

---

## [126] Steven Price — 2026-04-10
*Subject: Re: [PATCH v13 46/48] KVM: arm64: Expose KVM_ARM_VCPU_REC to user
 space*

On 19/03/2026 17:36, Suzuki K Poulose wrote:
> On 18/03/2026 15:54, Steven Price wrote:
>> Increment KVM_VCPU_MAX_FEATURES to expose the new capability to user

This patch caused so much bother with rebasing in the past, I'd
completely forgotten it isn't actually needed! Thanks for spotting!

Thanks,
Steve

> Cheers
> Suzuki

---

## [127] Alper Gun — 2026-04-14
*Subject: Re: [PATCH v13 00/48] arm64: Support for Arm CCA in KVM*

On Wed, Mar 18, 2026 at 8:54 AM Steven Price <steven.price@arm.com> wrote:
>
> This series adds support for running protected VMs using KVM under the

Hi Steven,

I have a question regarding host kexec and kdump scenarios, and
whether there is any plan to make them work in this initial series.

Intel TDX and AMD SEV-SNP both have a firmware shutdown command that
is invoked during the kexec or panic code paths to safely bypass
hardware memory protections and boot into the new kernel. As far as
I know, there is no similar global teardown command available for
the RMM.

What is the roadmap for supporting both general kexec and
more specifically kdump (panic) scenarios with CCA?

Thanks,
Alper

---

## [128] Steven Price — 2026-04-15
*Subject: Re: [PATCH v13 00/48] arm64: Support for Arm CCA in KVM*

On 14/04/2026 22:40, Alper Gun wrote:
> On Wed, Mar 18, 2026 at 8:54 AM Steven Price <steven.price@arm.com> wrote:
>>

Correct, the RMM specification as it stands doesn't provide a mechanism
for the host to do this. The host would have to identify all the realm
guests in the system: specifically the address of the RDs (Realm
Descriptors) and RECs (Realm Execution Contexts). It needs this to tear
down the guests and be able to undelegate the memory.

It's an interesting point and I'll raise the idea of a "firmware
shutdown command" to make this more possible.

> What is the roadmap for supporting both general kexec and
> more specifically kdump (panic) scenarios with CCA?

I don't have a roadmap I'm afraid for these. kexec in theory would be
possible with KVM gracefully terminating all realms. For kdump/panic
that sort of graceful shutdown isn't really appropriate (or likely to
succeed).

There is also some RMM configuration which cannot be repeated (see
RMI_RMM_CONFIG_SET) - which implies that the kexec kernel must be
similar to the first kernel (i.e. same page size).

Thanks,
Steve

---

## [129] Alper Gun — 2026-04-15
*Subject: Re: [PATCH v13 00/48] arm64: Support for Arm CCA in KVM*

On Wed, Apr 15, 2026 at 4:01 AM Steven Price <steven.price@arm.com> wrote:
>
> On 14/04/2026 22:40, Alper Gun wrote:

Thanks Steven for the clarification.

For us, kdump is highly critical as it is our primary diagnostic tool
for host crashes. Without it, monitoring and debugging at fleet scale
would become unmanageable.

To confirm my understanding of the current architecture: if a host
panics while no Realms are actively running (and therefore no pages
are currently in the delegated state), the standard kdump extraction
should work perfectly fine without any modifications, correct?

Regarding the KVM tracking structures (RDs, RECs, RTTs, etc.) when VMs
are running, perhaps we could use `vmcoreinfo` to export the physical
addresses of these delegated pages. This would allow tools like
`makedumpfile` to explicitly filter them out. I assume these pages must
remain hardware-locked while the VMs are active.

Long-term, having an architectural shutdown command - similar to the
TDH.SYS.DISABLE command in Intel TDX - would be incredibly useful. It
would allow the kdump kernel to safely bypass these hardware security
checks, especially when extracting host-side KVM state.

As for the protected realm memory, I assume that is an easier problem.
We naturally want to exclude guest pages from a host dump regardless
of whether they are Realm pages or not. However, accidental touches
are still fatal.

> There is also some RMM configuration which cannot be repeated (see
> RMI_RMM_CONFIG_SET) - which implies that the kexec kernel must be

---

## [130] Suzuki K Poulose — 2026-04-16
*Subject: Re: [PATCH v13 00/48] arm64: Support for Arm CCA in KVM*

On 16/04/2026 00:27, Alper Gun wrote:
> On Wed, Apr 15, 2026 at 4:01 AM Steven Price <steven.price@arm.com> wrote:
>>

This may not be true. We could have pages donated to RMM for GPT,
Tracking etc. So, unless Linux keeps track of them, it may be
unsafe for a crash kernel to access them.

> 
> Regarding the KVM tracking structures (RDs, RECs, RTTs, etc.) when VMs

Thinking of this, do we really need to ? We could access the pages from
"vmcore" read and handle the GPFs for such accesses and give out 0s
for the Granules. Anyways, we can't get access to the data on those
pages that are still in Realm PAS.

> `makedumpfile` to explicitly filter them out. I assume these pages must
> remain hardware-locked while the VMs are active.



> 
> Long-term, having an architectural shutdown command - similar to the

For kexec, may be we could do this. Alternatively we could try to
reclaim everything back, (GPTs, Tracking) before kexec-reboot.

> 
> As for the protected realm memory, I assume that is an easier problem.

That is true, the page sizes must match. RMM spec is updated to probe 
the state of the RMM and detect if it can do the CONFIG_SET

Suzuki

>>
>> Thanks,

---

## [131] Alper Gun — 2026-04-16
*Subject: Re: [PATCH v13 00/48] arm64: Support for Arm CCA in KVM*

On Thu, Apr 16, 2026 at 4:05 AM Suzuki K Poulose <suzuki.poulose@arm.com> wrote:
>
> On 16/04/2026 00:27, Alper Gun wrote:

I like the idea of handling the GPFs directly during vmcore reads for
kdump case. That's much simpler\cleaner solution.

> > `makedumpfile` to explicitly filter them out. I assume these pages must
> > remain hardware-locked while the VMs are active.

> For kexec, may be we could do this. Alternatively we could try to
> reclaim everything back, (GPTs, Tracking) before kexec-reboot.

Agreed. Reclaiming all delegated memory prior to the kexec reboot
makes perfect sense.

> >
> > As for the protected realm memory, I assume that is an easier problem.

---

## [132] Jiahao zheng — 2026-04-21

Hi Steven,

I've been testing CCA patch series and noticed Realm VM cannot boot successfully when the host is forced to run in nVHE mode (e.g., via `kvm-arm.mode=nvhe`). The kvmtool debug information will be truncated in set_guest_bank_private_gpa. 

Currently, in `kvm_ioctl_vcpu_run()`, running a Realm VM (REC) bypasses the standard nVHE EL2 stub. `kvm_rec_enter()` directly executes the SMC instruction to transition to the RMM. Upon returning to the EL1 host, the code falls back to `kvm_vgic_sync_hwstate()`, where the VGIC save operation is explicitly skipped for nVHE. Since the EL2 stub was bypassed, `__vgic_v3_save_state()` is never executed, and `ICH_*_EL2` states are lost.

To resolve this, I have a couple of thoughts:
1. If Host nVHE mode is not intended to be supported for Realms:
Since RME implies ARMv9 which mandates VHE, running a Realm with an nVHE host might just be an unsupported edge case. If so, we should explicitly reject RME initialization or REC creation when `!is_kernel_in_hyp_mode()`. This would cleanly prevent the undefined behavior.
2. If Host nVHE mode is intended to be supported:
Since RMM should remain agnostic to the Non-Secure VGIC states, the burden of saving these states falls strictly on KVM. However, the EL1 host cannot access `ICH_*_EL2`. Therefore, KVM needs to add specific logic for this scenario. We would likely need to route the REC exit through a dedicated nVHE EL2 stub to invoke `__vgic_v3_save_state()` before dropping back to EL1, rather than jumping straight back to `kvm_ioctl_vcpu_run()`.

I might have missed some documentation or comments regarding nVHE restrictions for CCA. If this is an oversight, it would be great to see a check added in the next iteration of the series.


Thanks,
Zheng

---

## [133] Steven Price — 2026-04-22
*Subject: Re: [PATCH v13 00/48] arm64: Support for Arm CCA in KVM*

On 21/04/2026 14:51, Jiahao zheng wrote:
> Hi Steven,
> 

Thanks for the testing. Yes indeed this is an oversight. For now option
1 is what I'm going to go for. There's nothing stopping nVHE mode being
supported but as you note any platform with RME will have VHE so it's
not an immediate priority to support.

One interesting case of nVHE is of course pKVM and for that there needs
to be some significant work to ensure that the EL2 hypervisor
understands the RMM communication and prevent any confused-deputy style
attacks. E.g. the host must not be able to map a pVM's private memory
into a realm guest.

I don't have any immediate plans to work on nVHE - my focus is getting
the basic support merged. But I know there was some interest to ensure
that pKVM and CCA would be able to co-exist on a platform so I expect it
will come in some form or another.

Thanks,
Steve

---
