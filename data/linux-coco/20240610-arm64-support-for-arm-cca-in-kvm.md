---
title: 'arm64: Support for Arm CCA in KVM'
date: 2024-06-10
last_reply: 2024-06-10
message_count: 44
participants: ['Steven Price']
---

## [1] Steven Price — 2024-06-10

This series adds support for running protected VMs using KVM under the
Arm Confidential Compute Architecture (CCA).

The related guest support was posted[1] last week but the two series are
separate (i.e. you can mix-and-match v2/v3 between the two series).
Unlike the guest series this one is a bit more "work in progress" and
there are some rough edges (see below). The aim is to focus on merging
the guest support first before moving onto the host side patches for
KVM. Review comments are very welcome though!

Individual patches have their own changelog, but the bulk of the changes
(from v2) are updating to match more closely with the spec and making
the code more readable. There's also the 'minor' fix to prevent leaking
all the guest's pages which v2 suffered from! ;) Thanks for all the
review comments on v2 - I've attempted to address everything that was
raised.

Major limitations:
 * Only supports 4k host PAGE_SIZE (if PAGE_SIZE != 4k then the realm
   extensions are disabled).
 * No support for huge pages when mapping the guest's pages. There is
   some 'dead' code left over from before guest_mem was supported. This
   is partly a current limitation of guest_memfd.

The ABI to the RMM (the RMI) is based on the final RMM v1.0 (EAC 5)
specification[2].

This series is based on v6.10-rc1. It is also available as a git
repository:

https://gitlab.arm.com/linux-arm/linux-cca cca-host/v3

Work in progress changes for kvmtool are available from the git
repository below, these changes are based on Fuad Tabba's repository for
pKVM to provide some alignment with the ongoing pKVM work:

https://gitlab.arm.com/linux-arm/kvmtool-cca cca/v2

Introduction (unchanged from v2)
============
A more general introduction to Arm CCA is available on the Arm
website[3], and links to the other components involved are available in
the overall cover letter.

Arm Confidential Compute Architecture adds two new 'worlds' to the
architecture: Root and Realm. A new software component known as the RMM
(Realm Management Monitor) runs in Realm EL2 and is trusted by both the
Normal World and VMs running within Realms. This enables mutual
distrust between the Realm VMs and the Normal World.

Virtual machines running within a Realm can decide on a (4k)
page-by-page granularity whether to share a page with the (Normal World)
host or to keep it private (protected). This protection is provided by
the hardware and attempts to access a page which isn't shared by the
Normal World will trigger a Granule Protection Fault. The series starts
by adding handling for these; faults within user space can be handled by
killing the process, faults within kernel space are considered fatal.

The Normal World host can communicate with the RMM via an SMC interface
known as RMI (Realm Management Interface), and Realm VMs can communicate
with the RMM via another SMC interface known as RSI (Realm Services
Interface). This series adds wrappers for the full set of RMI commands
and uses them to manage the realm guests.

The Normal World can use RMI commands to delegate pages to the Realm
world and to create, manage and run Realm VMs. Once delegated the pages
are inaccessible to the Normal World (unless explicitly shared by the
guest). However the Normal World may destroy the Realm VM at any time to
be able to reclaim (undelegate) the pages.

Realm VMs are identified by the KVM_CREATE_VM command, where the 'type'
argument has a new field to describe whether the guest is 'normal' or a
'realm'.

Entry/exit of a Realm VM attempts to reuse the KVM infrastructure, but
ultimately the final mechanism is different. So this series has a bunch
of commits handling the differences. As much as possible is placed in a
two new files: rme.c and rme-exit.c.

KVM also handles some of the PSCI requests for a realm and helps the RMM
complete the PSCI service requests.

Interrupts are managed by KVM, and are injected into the Realm with the
help of the RMM.

The RMM specification provides a new mechanism for a guest to
communicate with host which goes by the name "Host Call". This is simply
hooked up to the existing support for HVC calls from a normal
guest.

[1] https://lore.kernel.org/r/20240605093006.145492-1-steven.price%40arm.com
[2] https://developer.arm.com/documentation/den0137/1-0eac5/
[3] https://www.arm.com/architecture/security-features/arm-confidential-compute-architecture

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
  arm64: rme: allow userspace to inject aborts
  arm64: rme: support RSI_HOST_CALL

Sean Christopherson (1):
  KVM: Prepare for handling only shared mappings in mmu_notifier events

Steven Price (29):
  arm64: RME: Handle Granule Protection Faults (GPFs)
  arm64: RME: Add SMC definitions for calling the RMM
  arm64: RME: Add wrappers for RMI calls
  arm64: RME: Check for RME support at KVM init
  arm64: RME: Define the user ABI
  arm64: RME: ioctls to create and configure realms
  arm64: kvm: Allow passing machine type in KVM creation
  arm64: RME: Keep a spare page delegated to the RMM
  arm64: RME: RTT tear down
  arm64: RME: Allocate/free RECs to match vCPUs
  arm64: RME: Support for the VGIC in realms
  KVM: arm64: Support timers in realm RECs
  arm64: RME: Allow VMM to set RIPAS
  arm64: RME: Handle realm enter/exit
  KVM: arm64: Handle realm MMIO emulation
  arm64: RME: Allow populating initial contents
  arm64: RME: Runtime faulting of memory
  KVM: arm64: Handle realm VCPU load
  KVM: arm64: Validate register access for a Realm VM
  KVM: arm64: Handle Realm PSCI requests
  KVM: arm64: WARN on injected undef exceptions
  arm64: Don't expose stolen time for realm guests
  arm64: RME: Always use 4k pages for realms
  arm64: rme: Prevent Device mappings for Realms
  arm_pmu: Provide a mechanism for disabling the physical IRQ
  arm64: rme: Enable PMU support with a realm guest
  kvm: rme: Hide KVM_CAP_READONLY_MEM for realm guests
  arm64: kvm: Expose support for private memory
  KVM: arm64: Allow activating realms

Suzuki K Poulose (4):
  kvm: arm64: pgtable: Track the number of pages in the entry level
  kvm: arm64: Include kvm_emulate.h in kvm/arm_psci.h
  kvm: arm64: Expose debug HW register numbers for Realm
  arm64: rme: Allow checking SVE on VM instance

 Documentation/virt/kvm/api.rst       |    3 +
 arch/arm64/include/asm/kvm_emulate.h |   35 +
 arch/arm64/include/asm/kvm_host.h    |   15 +-
 arch/arm64/include/asm/kvm_pgtable.h |    2 +
 arch/arm64/include/asm/kvm_rme.h     |  155 +++
 arch/arm64/include/asm/rmi_cmds.h    |  508 ++++++++
 arch/arm64/include/asm/rmi_smc.h     |  251 ++++
 arch/arm64/include/asm/virt.h        |    1 +
 arch/arm64/include/uapi/asm/kvm.h    |   49 +
 arch/arm64/kvm/Kconfig               |    1 +
 arch/arm64/kvm/Makefile              |    3 +-
 arch/arm64/kvm/arch_timer.c          |   45 +-
 arch/arm64/kvm/arm.c                 |  166 ++-
 arch/arm64/kvm/guest.c               |   99 +-
 arch/arm64/kvm/hyp/pgtable.c         |    5 +-
 arch/arm64/kvm/hypercalls.c          |    4 +-
 arch/arm64/kvm/inject_fault.c        |    2 +
 arch/arm64/kvm/mmio.c                |   10 +-
 arch/arm64/kvm/mmu.c                 |  177 ++-
 arch/arm64/kvm/pmu-emul.c            |    7 +-
 arch/arm64/kvm/psci.c                |   29 +
 arch/arm64/kvm/reset.c               |   23 +-
 arch/arm64/kvm/rme-exit.c            |  212 ++++
 arch/arm64/kvm/rme.c                 | 1620 ++++++++++++++++++++++++++
 arch/arm64/kvm/sys_regs.c            |   83 +-
 arch/arm64/kvm/vgic/vgic-v3.c        |    8 +-
 arch/arm64/kvm/vgic/vgic.c           |   37 +-
 arch/arm64/mm/fault.c                |   31 +-
 drivers/perf/arm_pmu.c               |   15 +
 include/kvm/arm_arch_timer.h         |    2 +
 include/kvm/arm_pmu.h                |    4 +
 include/kvm/arm_psci.h               |    2 +
 include/linux/kvm_host.h             |    2 +
 include/linux/perf/arm_pmu.h         |    5 +
 include/uapi/linux/kvm.h             |   30 +-
 virt/kvm/kvm_main.c                  |    7 +
 36 files changed, 3550 insertions(+), 98 deletions(-)
 create mode 100644 arch/arm64/include/asm/kvm_rme.h
 create mode 100644 arch/arm64/include/asm/rmi_cmds.h
 create mode 100644 arch/arm64/include/asm/rmi_smc.h
 create mode 100644 arch/arm64/kvm/rme-exit.c
 create mode 100644 arch/arm64/kvm/rme.c

---

## [2] Steven Price — 2024-06-10
*Subject: [PATCH v3 01/43] KVM: Prepare for handling only shared mappings in mmu_notifier events*

From: Sean Christopherson <seanjc@google.com>

Add flags to "struct kvm_gfn_range" to let notifier events target only
shared and only private mappings, and write up the existing mmu_notifier
events to be shared-only (private memory is never associated with a
userspace virtual address, i.e. can't be reached via mmu_notifiers).

Add two flags so that KVM can handle the three possibilities (shared,
private, and shared+private) without needing something like a tri-state
enum.

Link: https://lore.kernel.org/all/ZJX0hk+KpQP0KUyB@google.com
Signed-off-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 include/linux/kvm_host.h | 2 ++
 virt/kvm/kvm_main.c      | 7 +++++++
 2 files changed, 9 insertions(+)

diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index 692c01e41a18..c5394c948db5 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -265,6 +265,8 @@ struct kvm_gfn_range {
 	gfn_t start;
 	gfn_t end;
 	union kvm_mmu_notifier_arg arg;
+	bool only_private;
+	bool only_shared;
 	bool may_block;
 };
 bool kvm_unmap_gfn_range(struct kvm *kvm, struct kvm_gfn_range *range);
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index 14841acb8b95..ff486d7d29b4 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -634,6 +634,13 @@ static __always_inline kvm_mn_ret_t __kvm_handle_hva_range(struct kvm *kvm,
 			 * the second or later invocation of the handler).
 			 */
 			gfn_range.arg = range->arg;
+
+			/*
+			 * HVA-based notifications aren't relevant to private
+			 * mappings as they don't have a userspace mapping.
+			 */
+			gfn_range.only_private = false;
+			gfn_range.only_shared = true;
 			gfn_range.may_block = range->may_block;
 
 			/*

---

## [3] Steven Price — 2024-06-10
*Subject: [PATCH v3 02/43] kvm: arm64: pgtable: Track the number of pages in the entry level*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

Keep track of the number of pages allocated for the top level PGD,
rather than computing it everytime (though we need it only twice now).
This will be used later by Arm CCA KVM changes.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/include/asm/kvm_pgtable.h | 2 ++
 arch/arm64/kvm/hyp/pgtable.c         | 5 +++--
 2 files changed, 5 insertions(+), 2 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_pgtable.h b/arch/arm64/include/asm/kvm_pgtable.h
index 19278dfe7978..0350c08ada7a 100644
--- a/arch/arm64/include/asm/kvm_pgtable.h
+++ b/arch/arm64/include/asm/kvm_pgtable.h
@@ -362,6 +362,7 @@ static inline bool kvm_pgtable_walk_lock_held(void)
  * struct kvm_pgtable - KVM page-table.
  * @ia_bits:		Maximum input address size, in bits.
  * @start_level:	Level at which the page-table walk starts.
+ * @pgd_pages:		Number of pages in the entry level of the page-table.
  * @pgd:		Pointer to the first top-level entry of the page-table.
  * @mm_ops:		Memory management callbacks.
  * @mmu:		Stage-2 KVM MMU struct. Unused for stage-1 page-tables.
@@ -372,6 +373,7 @@ static inline bool kvm_pgtable_walk_lock_held(void)
 struct kvm_pgtable {
 	u32					ia_bits;
 	s8					start_level;
+	u8					pgd_pages;
 	kvm_pteref_t				pgd;
 	struct kvm_pgtable_mm_ops		*mm_ops;
 
diff --git a/arch/arm64/kvm/hyp/pgtable.c b/arch/arm64/kvm/hyp/pgtable.c
index 9e2bbee77491..fb6675838b65 100644
--- a/arch/arm64/kvm/hyp/pgtable.c
+++ b/arch/arm64/kvm/hyp/pgtable.c
@@ -1574,7 +1574,8 @@ int __kvm_pgtable_stage2_init(struct kvm_pgtable *pgt, struct kvm_s2_mmu *mmu,
 	u32 sl0 = FIELD_GET(VTCR_EL2_SL0_MASK, vtcr);
 	s8 start_level = VTCR_EL2_TGRAN_SL0_BASE - sl0;
 
-	pgd_sz = kvm_pgd_pages(ia_bits, start_level) * PAGE_SIZE;
+	pgt->pgd_pages = kvm_pgd_pages(ia_bits, start_level);
+	pgd_sz = pgt->pgd_pages * PAGE_SIZE;
 	pgt->pgd = (kvm_pteref_t)mm_ops->zalloc_pages_exact(pgd_sz);
 	if (!pgt->pgd)
 		return -ENOMEM;
@@ -1626,7 +1627,7 @@ void kvm_pgtable_stage2_destroy(struct kvm_pgtable *pgt)
 	};
 
 	WARN_ON(kvm_pgtable_walk(pgt, 0, BIT(pgt->ia_bits), &walker));
-	pgd_sz = kvm_pgd_pages(pgt->ia_bits, pgt->start_level) * PAGE_SIZE;
+	pgd_sz = pgt->pgd_pages * PAGE_SIZE;
 	pgt->mm_ops->free_pages_exact(kvm_dereference_pteref(&walker, pgt->pgd), pgd_sz);
 	pgt->pgd = NULL;
 }

---

## [4] Steven Price — 2024-06-10
*Subject: [PATCH v3 03/43] kvm: arm64: Include kvm_emulate.h in kvm/arm_psci.h*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

Fix a potential build error (like below, when asm/kvm_emulate.h gets included after
the kvm/arm_psci.h) by including the missing header file in kvm/arm_psci.h:

./include/kvm/arm_psci.h: In function ‘kvm_psci_version’:
./include/kvm/arm_psci.h:29:13: error: implicit declaration of function
   ‘vcpu_has_feature’; did you mean ‘cpu_have_feature’? [-Werror=implicit-function-declaration]
   29 |         if (vcpu_has_feature(vcpu, KVM_ARM_VCPU_PSCI_0_2)) {
	         |             ^~~~~~~~~~~~~~~~
			       |             cpu_have_feature

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 include/kvm/arm_psci.h | 2 ++
 1 file changed, 2 insertions(+)

diff --git a/include/kvm/arm_psci.h b/include/kvm/arm_psci.h
index e8fb624013d1..1801c6fd3f10 100644
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

## [5] Steven Price — 2024-06-10
*Subject: [PATCH v3 04/43] arm64: RME: Handle Granule Protection Faults (GPFs)*

If the host attempts to access granules that have been delegated for use
in a realm these accesses will be caught and will trigger a Granule
Protection Fault (GPF).

A fault during a page walk signals a bug in the kernel and is handled by
oopsing the kernel. A non-page walk fault could be caused by user space
having access to a page which has been delegated to the kernel and will
trigger a SIGBUS to allow debugging why user space is trying to access a
delegated page.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v2:
 * Include missing "Granule Protection Fault at level -1"
---
 arch/arm64/mm/fault.c | 31 +++++++++++++++++++++++++------
 1 file changed, 25 insertions(+), 6 deletions(-)

diff --git a/arch/arm64/mm/fault.c b/arch/arm64/mm/fault.c
index 451ba7cbd5ad..8adc0d0b41a2 100644
--- a/arch/arm64/mm/fault.c
+++ b/arch/arm64/mm/fault.c
@@ -751,6 +751,25 @@ static int do_tag_check_fault(unsigned long far, unsigned long esr,
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
+	if (!is_el1_instruction_abort(esr) && fixup_exception(regs))
+		return 0;
+
+	arm64_notify_die(inf->name, regs, inf->sig, inf->code, far, esr);
+	return 0;
+}
+
 static const struct fault_info fault_info[] = {
 	{ do_bad,		SIGKILL, SI_KERNEL,	"ttbr address size fault"	},
 	{ do_bad,		SIGKILL, SI_KERNEL,	"level 1 address size fault"	},
@@ -787,12 +806,12 @@ static const struct fault_info fault_info[] = {
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

## [6] Steven Price — 2024-06-10
*Subject: [PATCH v3 05/43] arm64: RME: Add SMC definitions for calling the RMM*

The RMM (Realm Management Monitor) provides functionality that can be
accessed by SMC calls from the host.

The SMC definitions are based on DEN0137[1] version 1.0-eac5

[1] https://developer.arm.com/documentation/den0137/1-0eac5/

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v2:
 * Fix specification link.
 * Rename rec_entry->rec_enter to match spec.
 * Fix size of pmu_ovf_status to match spec.
---
 arch/arm64/include/asm/rmi_smc.h | 251 +++++++++++++++++++++++++++++++
 1 file changed, 251 insertions(+)
 create mode 100644 arch/arm64/include/asm/rmi_smc.h

diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
new file mode 100644
index 000000000000..fb8d9025c6e9
--- /dev/null
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -0,0 +1,251 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+/*
+ * Copyright (C) 2023-2024 ARM Ltd.
+ *
+ * The values and structures in this file are from the Realm Management Monitor
+ * specification (DEN0137) version 1.0 EAC5:
+ * https://developer.arm.com/documentation/den0137/1-0eac5/
+ */
+
+#ifndef __ASM_RME_SMC_H
+#define __ASM_RME_SMC_H
+
+#include <linux/arm-smccc.h>
+
+#define SMC_RxI_CALL(func)				\
+	ARM_SMCCC_CALL_VAL(ARM_SMCCC_FAST_CALL,		\
+			   ARM_SMCCC_SMC_64,		\
+			   ARM_SMCCC_OWNER_STANDARD,	\
+			   (func))
+
+#define SMC_RMI_DATA_CREATE		SMC_RxI_CALL(0x0153)
+#define SMC_RMI_DATA_CREATE_UNKNOWN	SMC_RxI_CALL(0x0154)
+#define SMC_RMI_DATA_DESTROY		SMC_RxI_CALL(0x0155)
+#define SMC_RMI_FEATURES		SMC_RxI_CALL(0x0165)
+#define SMC_RMI_GRANULE_DELEGATE	SMC_RxI_CALL(0x0151)
+#define SMC_RMI_GRANULE_UNDELEGATE	SMC_RxI_CALL(0x0152)
+#define SMC_RMI_PSCI_COMPLETE		SMC_RxI_CALL(0x0164)
+#define SMC_RMI_REALM_ACTIVATE		SMC_RxI_CALL(0x0157)
+#define SMC_RMI_REALM_CREATE		SMC_RxI_CALL(0x0158)
+#define SMC_RMI_REALM_DESTROY		SMC_RxI_CALL(0x0159)
+#define SMC_RMI_REC_AUX_COUNT		SMC_RxI_CALL(0x0167)
+#define SMC_RMI_REC_CREATE		SMC_RxI_CALL(0x015a)
+#define SMC_RMI_REC_DESTROY		SMC_RxI_CALL(0x015b)
+#define SMC_RMI_REC_ENTER		SMC_RxI_CALL(0x015c)
+#define SMC_RMI_RTT_CREATE		SMC_RxI_CALL(0x015d)
+#define SMC_RMI_RTT_DESTROY		SMC_RxI_CALL(0x015e)
+#define SMC_RMI_RTT_FOLD		SMC_RxI_CALL(0x0166)
+#define SMC_RMI_RTT_INIT_RIPAS		SMC_RxI_CALL(0x0168)
+#define SMC_RMI_RTT_MAP_UNPROTECTED	SMC_RxI_CALL(0x015f)
+#define SMC_RMI_RTT_READ_ENTRY		SMC_RxI_CALL(0x0161)
+#define SMC_RMI_RTT_SET_RIPAS		SMC_RxI_CALL(0x0169)
+#define SMC_RMI_RTT_UNMAP_UNPROTECTED	SMC_RxI_CALL(0x0162)
+#define SMC_RMI_VERSION			SMC_RxI_CALL(0x0150)
+
+#define RMI_ABI_MAJOR_VERSION	1
+#define RMI_ABI_MINOR_VERSION	0
+
+#define RMI_UNASSIGNED			0
+#define RMI_ASSIGNED			1
+#define RMI_TABLE			2
+
+#define RMI_ABI_VERSION_GET_MAJOR(version) ((version) >> 16)
+#define RMI_ABI_VERSION_GET_MINOR(version) ((version) & 0xFFFF)
+#define RMI_ABI_VERSION(major, minor)      (((major) << 16) | (minor))
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
+#define RMI_EMPTY		0
+#define RMI_RAM			1
+#define RMI_DESTROYED		2
+
+#define RMI_NO_MEASURE_CONTENT	0
+#define RMI_MEASURE_CONTENT	1
+
+#define RMI_FEATURE_REGISTER_0_S2SZ		GENMASK(7, 0)
+#define RMI_FEATURE_REGISTER_0_LPA2		BIT(8)
+#define RMI_FEATURE_REGISTER_0_SVE_EN		BIT(9)
+#define RMI_FEATURE_REGISTER_0_SVE_VL		GENMASK(13, 10)
+#define RMI_FEATURE_REGISTER_0_NUM_BPS		GENMASK(17, 14)
+#define RMI_FEATURE_REGISTER_0_NUM_WPS		GENMASK(21, 18)
+#define RMI_FEATURE_REGISTER_0_PMU_EN		BIT(22)
+#define RMI_FEATURE_REGISTER_0_PMU_NUM_CTRS	GENMASK(27, 23)
+#define RMI_FEATURE_REGISTER_0_HASH_SHA_256	BIT(28)
+#define RMI_FEATURE_REGISTER_0_HASH_SHA_512	BIT(29)
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
+		u8 padding_1[0x400];
+	};
+	union { /* 0x400 */
+		u8 rpv[64];
+		u8 padding_2[0x400];
+	};
+	union { /* 0x800 */
+		struct {
+			u64 vmid;
+			u64 rtt_base;
+			s64 rtt_level_start;
+			u64 rtt_num_start;
+		};
+		u8 padding_3[0x800];
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
+		u8 padding1[0x100];
+	};
+	union { /* 0x100 */
+		u64 mpidr;
+		u8 padding2[0x100];
+	};
+	union { /* 0x200 */
+		u64 pc;
+		u8 padding3[0x100];
+	};
+	union { /* 0x300 */
+		u64 gprs[REC_CREATE_NR_GPRS];
+		u8 padding4[0x500];
+	};
+	union { /* 0x800 */
+		struct {
+			u64 num_rec_aux;
+			u64 aux[REC_PARAMS_AUX_GRANULES];
+		};
+		u8 padding5[0x800];
+	};
+};
+
+#define RMI_EMULATED_MMIO		BIT(0)
+#define RMI_INJECT_SEA			BIT(1)
+#define RMI_TRAP_WFI			BIT(2)
+#define RMI_TRAP_WFE			BIT(3)
+#define RMI_RIPAS_RESPONSE		BIT(4)
+
+#define REC_RUN_GPRS			31
+#define REC_GIC_NUM_LRS			16
+
+struct rec_enter {
+	union { /* 0x000 */
+		u64 flags;
+		u8 padding0[0x200];
+	};
+	union { /* 0x200 */
+		u64 gprs[REC_RUN_GPRS];
+		u8 padding2[0x100];
+	};
+	union { /* 0x300 */
+		struct {
+			u64 gicv3_hcr;
+			u64 gicv3_lrs[REC_GIC_NUM_LRS];
+		};
+		u8 padding3[0x100];
+	};
+	u8 padding4[0x400];
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
+			u64 gicv3_lrs[REC_GIC_NUM_LRS];
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
+#endif

---

## [7] Steven Price — 2024-06-10
*Subject: [PATCH v3 06/43] arm64: RME: Add wrappers for RMI calls*

The wrappers make the call sites easier to read and deal with the
boiler plate of handling the error codes from the RMM.

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
index 000000000000..5288fed4c11a
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
+ * rmi_data_create() - Create a Data Granule
+ * @rd: PA of the RD
+ * @data: PA of the target granule
+ * @ipa: IPA at which the granule will be mapped in the guest
+ * @src: PA of the source granule
+ * @flags: RMI_MEASURE_CONTENT if the contents should be measured
+ *
+ * Create a new Data Granule, copying contents from a Non-secure Granule.
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
+ * rmi_data_create_unknown() - Create a Data Granule with unknown contents
+ * @rd: PA of the RD
+ * @data: PA of the target granule
+ * @ipa: IPA at which the granule will be mapped in the guest
+ *
+ * Create a new Data Granule with unknown contents
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
+ * rmi_data_destroy() - Destroy a Data Granule
+ * @rd: PA of the RD
+ * @ipa: IPA at which the granule is mapped in the guest
+ * @data_out: PA of the granule which was destroyed
+ * @top_out: Top IPA of non-live RTT entries
+ *
+ * Transitions the granule to DESTROYED state, the address cannot be used by
+ * the guest for the lifetime of the Realm.
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
+ * rmi_granule_delegate() - Delegate a Granule
+ * @phys: PA of the Granule
+ *
+ * Delegate a Granule for use by the Realm World.
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
+ * rmi_granule_undelegate() - Undelegate a Granule
+ * @phys: PA of the Granule
+ *
+ * Undelegate a Granule to allow use by the Normal World. Will fail if the
+ * Granule is in use.
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
+ * rmi_realm_activate() - Active a Realm
+ * @rd: PA of the RD
+ *
+ * Mark a Realm as Active signalling that creation is complete and allowing
+ * execution of the Realm.
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
+ * rmi_realm_create() - Create a Realm
+ * @rd: PA of the RD
+ * @params_ptr: PA of Realm parameters
+ *
+ * Create a new Realm using the given parameters.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_realm_create(unsigned long rd, unsigned long params_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_REALM_CREATE, rd, params_ptr, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_realm_destroy() - Destroy a Realm
+ * @rd: PA of the RD
+ *
+ * Destroys a Realm, all objects belonging to the Realm must be destroyed first.
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
+ * rmi_rec_aux_count() - Get number of auxiliary Granules required
+ * @rd: PA of the RD
+ * @aux_count: Number of pages written to this pointer
+ *
+ * A REC may require extra auxiliary pages to be delegated for the RMM to
+ * store metadata (not visible to the normal world) in. This function provides
+ * the number of pages that are required.
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
+ * @params_ptr: PA of REC parameters
+ *
+ * Create a REC using the parameters specified in the struct rec_params pointed
+ * to by @params_ptr.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rec_create(unsigned long rd, unsigned long rec,
+				 unsigned long params_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_REC_CREATE, rd, rec, params_ptr, &res);
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
+ * Creates an RTT (Realm Translation Table) at the specified address and level
+ * within the realm.
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
+ * Destroys an RTT. The RTT must be empty.
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
+ * rmi_rtt_init_ripas() - Set RIPAS for new Realm
+ * @rd: PA of the RD
+ * @base: Base of target IPA region
+ * @top: Top of target IPA region
+ * @out_top: Top IPA of range whose RIPAS was modified
+ *
+ * Sets the RIPAS of a target IPA range to RAM, for a Realm in the NEW state.
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
+ * rmi_rtt_map_unprotected() - Map NS pages into a Realm
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
+ * Completes a request made by the Realm to change the RIPAS of a target IPA
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
+#endif

---

## [8] Steven Price — 2024-06-10
*Subject: [PATCH v3 07/43] arm64: RME: Check for RME support at KVM init*

Query the RMI version number and check if it is a compatible version. A
static key is also provided to signal that a supported RMM is available.

Functions are provided to query if a VM or VCPU is a realm (or rec)
which currently will always return false.

Signed-off-by: Steven Price <steven.price@arm.com>
---
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
 arch/arm64/kvm/rme.c                 | 50 +++++++++++++++++++++++++
 7 files changed, 137 insertions(+), 1 deletion(-)
 create mode 100644 arch/arm64/include/asm/kvm_rme.h
 create mode 100644 arch/arm64/kvm/rme.c

diff --git a/arch/arm64/include/asm/kvm_emulate.h b/arch/arm64/include/asm/kvm_emulate.h
index 501e3e019c93..bedc8344e082 100644
--- a/arch/arm64/include/asm/kvm_emulate.h
+++ b/arch/arm64/include/asm/kvm_emulate.h
@@ -599,4 +599,22 @@ static __always_inline void kvm_reset_cptr_el2(struct kvm_vcpu *vcpu)
 
 	kvm_write_cptr_el2(val);
 }
+
+static inline bool kvm_is_realm(struct kvm *kvm)
+{
+	if (static_branch_unlikely(&kvm_rme_is_available))
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
index 8170c04fde91..47c5235bf4f2 100644
--- a/arch/arm64/include/asm/kvm_host.h
+++ b/arch/arm64/include/asm/kvm_host.h
@@ -27,6 +27,7 @@
 #include <asm/fpsimd.h>
 #include <asm/kvm.h>
 #include <asm/kvm_asm.h>
+#include <asm/kvm_rme.h>
 #include <asm/vncr_mapping.h>
 
 #define __KVM_HAVE_ARCH_INTC_INITIALIZED
@@ -339,6 +340,9 @@ struct kvm_arch {
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
index 000000000000..69af5c3a1e44
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
+#endif
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
index a6497228c5a8..5e79e5eee88d 100644
--- a/arch/arm64/kvm/Makefile
+++ b/arch/arm64/kvm/Makefile
@@ -20,7 +20,8 @@ kvm-y += arm.o mmu.o mmio.o psci.o hypercalls.o pvtime.o \
 	 vgic/vgic-v3.o vgic/vgic-v4.o \
 	 vgic/vgic-mmio.o vgic/vgic-mmio-v2.o \
 	 vgic/vgic-mmio-v3.o vgic/vgic-kvm-device.o \
-	 vgic/vgic-its.o vgic/vgic-debug.o
+	 vgic/vgic-its.o vgic/vgic-debug.o \
+	 rme.o
 
 kvm-$(CONFIG_HW_PERF_EVENTS)  += pmu-emul.o pmu.o
 kvm-$(CONFIG_ARM64_PTR_AUTH)  += pauth.o
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 9996a989b52e..cf136316afd5 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -40,6 +40,7 @@
 #include <asm/kvm_nested.h>
 #include <asm/kvm_pkvm.h>
 #include <asm/kvm_ptrauth.h>
+#include <asm/kvm_rme.h>
 #include <asm/sections.h>
 
 #include <kvm/arm_hypercalls.h>
@@ -48,6 +49,8 @@
 
 static enum kvm_mode kvm_mode = KVM_MODE_DEFAULT;
 
+DEFINE_STATIC_KEY_FALSE(kvm_rme_is_available);
+
 DECLARE_KVM_HYP_PER_CPU(unsigned long, kvm_hyp_vector);
 
 DEFINE_PER_CPU(unsigned long, kvm_arm_hyp_stack_page);
@@ -2681,6 +2684,9 @@ static __init int kvm_arm_init(void)
 
 	in_hyp_mode = is_kernel_in_hyp_mode();
 
+	if (in_hyp_mode)
+		kvm_init_rme();
+
 	if (cpus_have_final_cap(ARM64_WORKAROUND_DEVICE_LOAD_ACQUIRE) ||
 	    cpus_have_final_cap(ARM64_WORKAROUND_1508412))
 		kvm_info("Guests without required CPU erratum workarounds can deadlock system!\n" \
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
new file mode 100644
index 000000000000..418685fbf6ed
--- /dev/null
+++ b/arch/arm64/kvm/rme.c
@@ -0,0 +1,50 @@
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
+	int version_major, version_minor;
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
+		kvm_err("Unsupported RMI ABI (v%d.%d) host supports v%d.%d\n",
+			version_major, version_minor,
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

## [9] Steven Price — 2024-06-10
*Subject: [PATCH v3 08/43] arm64: RME: Define the user ABI*

There is one (multiplexed) CAP which can be used to create, populate and
then activate the realm.

Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 Documentation/virt/kvm/api.rst    |  1 +
 arch/arm64/include/uapi/asm/kvm.h | 49 +++++++++++++++++++++++++++++++
 include/uapi/linux/kvm.h          | 11 +++++++
 3 files changed, 61 insertions(+)

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index a71d91978d9e..dd53beb8fe14 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -5064,6 +5064,7 @@ Recognised values for feature:
 
   =====      ===========================================
   arm64      KVM_ARM_VCPU_SVE (requires KVM_CAP_ARM_SVE)
+  arm64      KVM_ARM_VCPU_REC (requires KVM_CAP_ARM_RME)
   =====      ===========================================
 
 Finalizes the configuration of the specified vcpu feature.
diff --git a/arch/arm64/include/uapi/asm/kvm.h b/arch/arm64/include/uapi/asm/kvm.h
index 964df31da975..080331008b79 100644
--- a/arch/arm64/include/uapi/asm/kvm.h
+++ b/arch/arm64/include/uapi/asm/kvm.h
@@ -108,6 +108,7 @@ struct kvm_regs {
 #define KVM_ARM_VCPU_PTRAUTH_ADDRESS	5 /* VCPU uses address authentication */
 #define KVM_ARM_VCPU_PTRAUTH_GENERIC	6 /* VCPU uses generic authentication */
 #define KVM_ARM_VCPU_HAS_EL2		7 /* Support nested virtualization */
+#define KVM_ARM_VCPU_REC		8 /* VCPU REC state as part of Realm */
 
 struct kvm_vcpu_init {
 	__u32 target;
@@ -418,6 +419,54 @@ enum {
 #define   KVM_DEV_ARM_VGIC_SAVE_PENDING_TABLES	3
 #define   KVM_DEV_ARM_ITS_CTRL_RESET		4
 
+/* KVM_CAP_ARM_RME on VM fd */
+#define KVM_CAP_ARM_RME_CONFIG_REALM		0
+#define KVM_CAP_ARM_RME_CREATE_RD		1
+#define KVM_CAP_ARM_RME_INIT_IPA_REALM		2
+#define KVM_CAP_ARM_RME_POPULATE_REALM		3
+#define KVM_CAP_ARM_RME_ACTIVATE_REALM		4
+
+#define KVM_CAP_ARM_RME_MEASUREMENT_ALGO_SHA256		0
+#define KVM_CAP_ARM_RME_MEASUREMENT_ALGO_SHA512		1
+
+#define KVM_CAP_ARM_RME_RPV_SIZE 64
+
+/* List of configuration items accepted for KVM_CAP_ARM_RME_CONFIG_REALM */
+#define KVM_CAP_ARM_RME_CFG_RPV			0
+#define KVM_CAP_ARM_RME_CFG_HASH_ALGO		1
+
+struct kvm_cap_arm_rme_config_item {
+	__u32 cfg;
+	union {
+		/* cfg == KVM_CAP_ARM_RME_CFG_RPV */
+		struct {
+			__u8	rpv[KVM_CAP_ARM_RME_RPV_SIZE];
+		};
+
+		/* cfg == KVM_CAP_ARM_RME_CFG_HASH_ALGO */
+		struct {
+			__u32	hash_algo;
+		};
+
+		/* Fix the size of the union */
+		__u8	reserved[256];
+	};
+};
+
+#define KVM_ARM_RME_POPULATE_FLAGS_MEASURE	BIT(0)
+struct kvm_cap_arm_rme_populate_realm_args {
+	__u64 populate_ipa_base;
+	__u64 populate_ipa_size;
+	__u32 flags;
+	__u32 reserved[3];
+};
+
+struct kvm_cap_arm_rme_init_ipa_args {
+	__u64 init_ipa_base;
+	__u64 init_ipa_size;
+	__u32 reserved[4];
+};
+
 /* Device Control API on vcpu fd */
 #define KVM_ARM_VCPU_PMU_V3_CTRL	0
 #define   KVM_ARM_VCPU_PMU_V3_IRQ	0
diff --git a/include/uapi/linux/kvm.h b/include/uapi/linux/kvm.h
index d03842abae57..44c68e36f230 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -918,6 +918,8 @@ struct kvm_enable_cap {
 #define KVM_CAP_GUEST_MEMFD 234
 #define KVM_CAP_VM_TYPES 235
 
+#define KVM_CAP_ARM_RME 300 /* FIXME: Large number to prevent conflicts */
+
 struct kvm_irq_routing_irqchip {
 	__u32 irqchip;
 	__u32 pin;
@@ -1548,4 +1550,13 @@ struct kvm_create_guest_memfd {
 	__u64 reserved[6];
 };
 
+/* Available with KVM_CAP_ARM_RME, only for VMs with KVM_VM_TYPE_ARM_REALM  */
+struct kvm_arm_rmm_psci_complete {
+	__u64 target_mpidr;
+	__u32 psci_status;
+	__u32 padding[3];
+};
+
+#define KVM_ARM_VCPU_RMM_PSCI_COMPLETE	_IOW(KVMIO, 0xd2, struct kvm_arm_rmm_psci_complete)
+
 #endif /* __LINUX_KVM_H */

---

## [10] Steven Price — 2024-06-10
*Subject: [PATCH v3 09/43] arm64: RME: ioctls to create and configure realms*

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
---
Changes since v2:
 * Improved commit description.
 * Improved return failures for rmi_check_version().
 * Clear contents of PGD after it has been undelegated in case the RMM
   left stale data.
 * Minor changes to reflect changes in previous patches.
---
 arch/arm64/include/asm/kvm_emulate.h |   5 +
 arch/arm64/include/asm/kvm_rme.h     |  19 ++
 arch/arm64/kvm/arm.c                 |  18 ++
 arch/arm64/kvm/mmu.c                 |  15 +-
 arch/arm64/kvm/rme.c                 | 283 +++++++++++++++++++++++++++
 5 files changed, 338 insertions(+), 2 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_emulate.h b/arch/arm64/include/asm/kvm_emulate.h
index bedc8344e082..56526594e3b5 100644
--- a/arch/arm64/include/asm/kvm_emulate.h
+++ b/arch/arm64/include/asm/kvm_emulate.h
@@ -612,6 +612,11 @@ static inline enum realm_state kvm_realm_state(struct kvm *kvm)
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
index 69af5c3a1e44..209cd99f03dd 100644
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
 
 #endif
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index cf136316afd5..d3cdc775d001 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -143,6 +143,13 @@ int kvm_vm_ioctl_enable_cap(struct kvm *kvm,
 		}
 		mutex_unlock(&kvm->slots_lock);
 		break;
+	case KVM_CAP_ARM_RME:
+		if (!kvm_is_realm(kvm))
+			return -EINVAL;
+		mutex_lock(&kvm->lock);
+		r = kvm_realm_enable_cap(kvm, cap);
+		mutex_unlock(&kvm->lock);
+		break;
 	default:
 		break;
 	}
@@ -202,6 +209,13 @@ int kvm_arch_init_vm(struct kvm *kvm, unsigned long type)
 
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
@@ -260,6 +274,7 @@ void kvm_arch_destroy_vm(struct kvm *kvm)
 	kvm_unshare_hyp(kvm, kvm + 1);
 
 	kvm_arm_teardown_hypercalls(kvm);
+	kvm_destroy_realm(kvm);
 }
 
 static bool kvm_has_full_ptr_auth(void)
@@ -407,6 +422,9 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
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
index 8bcab0cc3fe9..19df60fee8c8 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -872,6 +872,10 @@ int kvm_init_stage2_mmu(struct kvm *kvm, struct kvm_s2_mmu *mmu, unsigned long t
 	struct kvm_pgtable *pgt;
 	u64 mmfr0, mmfr1;
 	u32 phys_shift;
+	u32 ipa_limit = kvm_ipa_limit;
+
+	if (kvm_is_realm(kvm))
+		ipa_limit = kvm_realm_ipa_limit();
 
 	if (type & ~KVM_VM_TYPE_ARM_IPA_SIZE_MASK)
 		return -EINVAL;
@@ -880,12 +884,12 @@ int kvm_init_stage2_mmu(struct kvm *kvm, struct kvm_s2_mmu *mmu, unsigned long t
 	if (is_protected_kvm_enabled()) {
 		phys_shift = kvm_ipa_limit;
 	} else if (phys_shift) {
-		if (phys_shift > kvm_ipa_limit ||
+		if (phys_shift > ipa_limit ||
 		    phys_shift < ARM64_MIN_PARANGE_BITS)
 			return -EINVAL;
 	} else {
 		phys_shift = KVM_PHYS_SHIFT;
-		if (phys_shift > kvm_ipa_limit) {
+		if (phys_shift > ipa_limit) {
 			pr_warn_once("%s using unsupported default IPA limit, upgrade your VMM\n",
 				     current->comm);
 			return -EINVAL;
@@ -1014,6 +1018,13 @@ void kvm_free_stage2_pgd(struct kvm_s2_mmu *mmu)
 	struct kvm_pgtable *pgt = NULL;
 
 	write_lock(&kvm->mmu_lock);
+	if (kvm_is_realm(kvm) &&
+	    (kvm_realm_state(kvm) != REALM_STATE_DEAD &&
+	     kvm_realm_state(kvm) != REALM_STATE_NONE)) {
+		/* Tearing down RTTs will be added in a later patch */
+		write_unlock(&kvm->mmu_lock);
+		return;
+	}
 	pgt = mmu->pgt;
 	if (pgt) {
 		mmu->pgd_phys = 0;
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 418685fbf6ed..4d21ec5f2910 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -5,9 +5,20 @@
 
 #include <linux/kvm_host.h>
 
+#include <asm/kvm_emulate.h>
+#include <asm/kvm_mmu.h>
 #include <asm/rmi_cmds.h>
 #include <asm/virt.h>
 
+#include <asm/kvm_pgtable.h>
+
+static unsigned long rmm_feat_reg0;
+
+static bool rme_supports(unsigned long feature)
+{
+	return !!u64_get_bits(rmm_feat_reg0, feature);
+}
+
 static int rmi_check_version(void)
 {
 	struct arm_smccc_res res;
@@ -36,6 +47,272 @@ static int rmi_check_version(void)
 	return 0;
 }
 
+u32 kvm_realm_ipa_limit(void)
+{
+	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_S2SZ);
+}
+
+static int get_start_level(struct realm *realm)
+{
+	return 4 - stage2_pgtable_levels(realm->ia_bits);
+}
+
+static int realm_create_rd(struct kvm *kvm)
+{
+	struct realm *realm = &kvm->arch.realm;
+	struct realm_params *params = realm->params;
+	void *rd = NULL;
+	phys_addr_t rd_phys, params_phys;
+	struct kvm_pgtable *pgt = kvm->arch.mmu.pgt;
+	int i, r;
+
+	if (WARN_ON(realm->rd) || WARN_ON(!realm->params))
+		return -EEXIST;
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
+	for (i = 0; i < pgt->pgd_pages; i++) {
+		phys_addr_t pgd_phys = kvm->arch.mmu.pgd_phys + i * PAGE_SIZE;
+
+		if (rmi_granule_delegate(pgd_phys)) {
+			r = -ENXIO;
+			goto out_undelegate_tables;
+		}
+	}
+
+	realm->ia_bits = VTCR_EL2_IPA(kvm->arch.mmu.vtcr);
+
+	params->s2sz = VTCR_EL2_IPA(kvm->arch.mmu.vtcr);
+	params->rtt_level_start = get_start_level(realm);
+	params->rtt_num_start = pgt->pgd_pages;
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
+	realm->rd = rd;
+
+	if (WARN_ON(rmi_rec_aux_count(rd_phys, &realm->num_aux))) {
+		WARN_ON(rmi_realm_destroy(rd_phys));
+		goto out_undelegate_tables;
+	}
+
+	return 0;
+
+out_undelegate_tables:
+	while (--i >= 0) {
+		phys_addr_t pgd_phys = kvm->arch.mmu.pgd_phys + i * PAGE_SIZE;
+
+		WARN_ON(rmi_granule_undelegate(pgd_phys));
+	}
+	WARN_ON(rmi_granule_undelegate(rd_phys));
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
+				  struct kvm_cap_arm_rme_config_item *cfg)
+{
+	switch (cfg->hash_algo) {
+	case KVM_CAP_ARM_RME_MEASUREMENT_ALGO_SHA256:
+		if (!rme_supports(RMI_FEATURE_REGISTER_0_HASH_SHA_256))
+			return -EINVAL;
+		break;
+	case KVM_CAP_ARM_RME_MEASUREMENT_ALGO_SHA512:
+		if (!rme_supports(RMI_FEATURE_REGISTER_0_HASH_SHA_512))
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
+	struct kvm_cap_arm_rme_config_item cfg;
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
+	case KVM_CAP_ARM_RME_CFG_RPV:
+		memcpy(&realm->params->rpv, &cfg.rpv, sizeof(cfg.rpv));
+		break;
+	case KVM_CAP_ARM_RME_CFG_HASH_ALGO:
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
+	case KVM_CAP_ARM_RME_CREATE_RD:
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
+	struct kvm_pgtable *pgt = kvm->arch.mmu.pgt;
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
+		if (WARN_ON(rmi_granule_undelegate(rd_phys)))
+			return;
+		free_page((unsigned long)realm->rd);
+		realm->rd = NULL;
+	}
+
+	rme_vmid_release(realm->vmid);
+
+	for (i = 0; i < pgt->pgd_pages; i++) {
+		phys_addr_t pgd_phys = kvm->arch.mmu.pgd_phys + i * PAGE_SIZE;
+
+		if (WARN_ON(rmi_granule_undelegate(pgd_phys)))
+			return;
+
+		clear_page(phys_to_virt(pgd_phys));
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
+	struct realm_params *params;
+
+	params = (struct realm_params *)get_zeroed_page(GFP_KERNEL);
+	if (!params)
+		return -ENOMEM;
+
+	kvm->arch.realm.params = params;
+	return 0;
+}
+
 void kvm_init_rme(void)
 {
 	if (PAGE_SIZE != SZ_4K)
@@ -46,5 +323,11 @@ void kvm_init_rme(void)
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

## [11] Steven Price — 2024-06-10
*Subject: [PATCH v3 10/43] kvm: arm64: Expose debug HW register numbers for Realm*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

Expose VM specific Debug HW register numbers.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/kvm/arm.c | 24 +++++++++++++++++++++---
 1 file changed, 21 insertions(+), 3 deletions(-)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index d3cdc775d001..c37b563d1d66 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -68,6 +68,22 @@ bool is_kvm_arm_initialised(void)
 	return kvm_arm_initialised;
 }
 
+static u32 kvm_arm_get_num_brps(struct kvm *kvm)
+{
+	if (!kvm || !kvm_is_realm(kvm))
+		return get_num_brps();
+	/* Realm guest is not debuggable. */
+	return 0;
+}
+
+static u32 kvm_arm_get_num_wrps(struct kvm *kvm)
+{
+	if (!kvm || !kvm_is_realm(kvm))
+		return get_num_wrps();
+	/* Realm guest is not debuggable. */
+	return 0;
+}
+
 int kvm_arch_vcpu_should_kick(struct kvm_vcpu *vcpu)
 {
 	return kvm_vcpu_exiting_guest_mode(vcpu) == IN_GUEST_MODE;
@@ -336,7 +352,6 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 	case KVM_CAP_ARM_IRQ_LINE_LAYOUT_2:
 	case KVM_CAP_ARM_NISV_TO_USER:
 	case KVM_CAP_ARM_INJECT_EXT_DABT:
-	case KVM_CAP_SET_GUEST_DEBUG:
 	case KVM_CAP_VCPU_ATTRIBUTES:
 	case KVM_CAP_PTP_KVM:
 	case KVM_CAP_ARM_SYSTEM_SUSPEND:
@@ -344,6 +359,9 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 	case KVM_CAP_COUNTER_OFFSET:
 		r = 1;
 		break;
+	case KVM_CAP_SET_GUEST_DEBUG:
+		r = !kvm_is_realm(kvm);
+		break;
 	case KVM_CAP_SET_GUEST_DEBUG2:
 		return KVM_GUESTDBG_VALID_MASK;
 	case KVM_CAP_ARM_SET_DEVICE_ADDR:
@@ -389,10 +407,10 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 		r = cpus_have_final_cap(ARM64_HAS_32BIT_EL1);
 		break;
 	case KVM_CAP_GUEST_DEBUG_HW_BPS:
-		r = get_num_brps();
+		r = kvm_arm_get_num_brps(kvm);
 		break;
 	case KVM_CAP_GUEST_DEBUG_HW_WPS:
-		r = get_num_wrps();
+		r = kvm_arm_get_num_wrps(kvm);
 		break;
 	case KVM_CAP_ARM_PMU_V3:
 		r = kvm_arm_support_pmu_v3();

---

## [12] Steven Price — 2024-06-10
*Subject: [PATCH v3 11/43] arm64: kvm: Allow passing machine type in KVM creation*

Previously machine type was used purely for specifying the physical
address size of the guest. Reserve the higher bits to specify an ARM
specific machine type and declare a new type 'KVM_VM_TYPE_ARM_REALM'
used to create a realm guest.

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/kvm/arm.c     | 17 +++++++++++++++++
 arch/arm64/kvm/mmu.c     |  3 ---
 include/uapi/linux/kvm.h | 19 +++++++++++++++----
 3 files changed, 32 insertions(+), 7 deletions(-)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index c37b563d1d66..b1df789e9013 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -196,6 +196,23 @@ int kvm_arch_init_vm(struct kvm *kvm, unsigned long type)
 	mutex_unlock(&kvm->lock);
 #endif
 
+	if (type & ~(KVM_VM_TYPE_ARM_MASK | KVM_VM_TYPE_ARM_IPA_SIZE_MASK))
+		return -EINVAL;
+
+	switch (type & KVM_VM_TYPE_ARM_MASK) {
+	case KVM_VM_TYPE_ARM_NORMAL:
+		break;
+	case KVM_VM_TYPE_ARM_REALM:
+		kvm->arch.is_realm = true;
+		if (!kvm_is_realm(kvm)) {
+			/* Realm support unavailable */
+			return -EINVAL;
+		}
+		break;
+	default:
+		return -EINVAL;
+	}
+
 	ret = kvm_share_hyp(kvm, kvm + 1);
 	if (ret)
 		return ret;
diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index 19df60fee8c8..93300491b31b 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -877,9 +877,6 @@ int kvm_init_stage2_mmu(struct kvm *kvm, struct kvm_s2_mmu *mmu, unsigned long t
 	if (kvm_is_realm(kvm))
 		ipa_limit = kvm_realm_ipa_limit();
 
-	if (type & ~KVM_VM_TYPE_ARM_IPA_SIZE_MASK)
-		return -EINVAL;
-
 	phys_shift = KVM_VM_TYPE_ARM_IPA_SIZE(type);
 	if (is_protected_kvm_enabled()) {
 		phys_shift = kvm_ipa_limit;
diff --git a/include/uapi/linux/kvm.h b/include/uapi/linux/kvm.h
index 44c68e36f230..32cff22f0e4d 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -635,14 +635,25 @@ struct kvm_enable_cap {
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

## [13] Steven Price — 2024-06-10
*Subject: [PATCH v3 12/43] arm64: RME: Keep a spare page delegated to the RMM*

Pages can only be populated/destroyed on the RMM at the 4KB granule,
this requires creating the full depth of RTTs. However if the pages are
going to be combined into a 2MB huge page the last RTT is only
temporarily needed. Similarly when freeing memory the huge page must be
temporarily split requiring temporary usage of the full depth oF RTTs.

To avoid needing to perform a temporary allocation and delegation of a
page for this purpose we keep a spare delegated page around. In
particular this avoids the need for memory allocation while destroying
the realm guest.

Reviewed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/include/asm/kvm_rme.h | 5 +++++
 arch/arm64/kvm/rme.c             | 8 ++++++++
 2 files changed, 13 insertions(+)

diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index 209cd99f03dd..bd306bd7b64b 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -50,6 +50,9 @@ enum realm_state {
  * @state: The lifetime state machine for the realm
  * @rd: Kernel mapping of the Realm Descriptor (RD)
  * @params: Parameters for the RMI_REALM_CREATE command
+ * @spare_page: A physical page that has been delegated to the Realm world but
+ *              is otherwise free. Used to avoid temporary allocation during
+ *              RTT operations.
  * @num_aux: The number of auxiliary pages required by the RMM
  * @vmid: VMID to be used by the RMM for the realm
  * @ia_bits: Number of valid Input Address bits in the IPA
@@ -60,6 +63,8 @@ struct realm {
 	void *rd;
 	struct realm_params *params;
 
+	phys_addr_t spare_page;
+
 	unsigned long num_aux;
 	unsigned int vmid;
 	unsigned int ia_bits;
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 4d21ec5f2910..f6430d460519 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -104,6 +104,7 @@ static int realm_create_rd(struct kvm *kvm)
 	}
 
 	realm->rd = rd;
+	realm->spare_page = PHYS_ADDR_MAX;
 
 	if (WARN_ON(rmi_rec_aux_count(rd_phys, &realm->num_aux))) {
 		WARN_ON(rmi_realm_destroy(rd_phys));
@@ -286,6 +287,13 @@ void kvm_destroy_realm(struct kvm *kvm)
 
 	rme_vmid_release(realm->vmid);
 
+	if (realm->spare_page != PHYS_ADDR_MAX) {
+		/* Leak the page if the undelegate fails */
+		if (!WARN_ON(rmi_granule_undelegate(realm->spare_page)))
+			free_page((unsigned long)phys_to_virt(realm->spare_page));
+		realm->spare_page = PHYS_ADDR_MAX;
+	}
+
 	for (i = 0; i < pgt->pgd_pages; i++) {
 		phys_addr_t pgd_phys = kvm->arch.mmu.pgd_phys + i * PAGE_SIZE;

---

## [14] Steven Price — 2024-06-10
*Subject: [PATCH v3 13/43] arm64: RME: RTT tear down*

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
Changes since v2:
 * Moved {alloc,free}_delegated_page() and ensure_spare_page() to a
   later patch when they are actually used.
 * Some simplifications now rmi_xxx() functions allow NULL as an output
   parameter.
 * Improved comments and code layout.
---
 arch/arm64/include/asm/kvm_rme.h |  19 ++++++
 arch/arm64/kvm/mmu.c             |   6 +-
 arch/arm64/kvm/rme.c             | 113 +++++++++++++++++++++++++++++++
 3 files changed, 135 insertions(+), 3 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index bd306bd7b64b..e5704859a6e5 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -76,5 +76,24 @@ u32 kvm_realm_ipa_limit(void);
 int kvm_realm_enable_cap(struct kvm *kvm, struct kvm_enable_cap *cap);
 int kvm_init_realm_vm(struct kvm *kvm);
 void kvm_destroy_realm(struct kvm *kvm);
+void kvm_realm_destroy_rtts(struct kvm *kvm, u32 ia_bits);
+
+#define RME_RTT_BLOCK_LEVEL	2
+#define RME_RTT_MAX_LEVEL	3
+
+#define RME_PAGE_SHIFT		12
+#define RME_PAGE_SIZE		BIT(RME_PAGE_SHIFT)
+/* See ARM64_HW_PGTABLE_LEVEL_SHIFT() */
+#define RME_RTT_LEVEL_SHIFT(l)	\
+	((RME_PAGE_SHIFT - 3) * (4 - (l)) + 3)
+#define RME_L2_BLOCK_SIZE	BIT(RME_RTT_LEVEL_SHIFT(2))
+
+static inline unsigned long rme_rtt_level_mapsize(int level)
+{
+	if (WARN_ON(level > RME_RTT_MAX_LEVEL))
+		return RME_PAGE_SIZE;
+
+	return (1UL << RME_RTT_LEVEL_SHIFT(level));
+}
 
 #endif
diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index 93300491b31b..83bd10845efb 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -1012,17 +1012,17 @@ void stage2_unmap_vm(struct kvm *kvm)
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
 		return;
 	}
-	pgt = mmu->pgt;
 	if (pgt) {
 		mmu->pgd_phys = 0;
 		mmu->pgt = NULL;
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index f6430d460519..7db405d2b2b2 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -125,6 +125,119 @@ static int realm_create_rd(struct kvm *kvm)
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
+	if (WARN_ON(level > RME_RTT_MAX_LEVEL))
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
+			if (!WARN_ON(rmi_granule_undelegate(rtt_granule)))
+				free_page((unsigned long)phys_to_virt(rtt_granule));
+			break;
+		case RMI_ERROR_RTT:
+			if (next_addr > addr) {
+				/* Missing RTT, skip */
+				break;
+			}
+			if (WARN_ON(RMI_RETURN_INDEX(ret) != level))
+				return -EBUSY;
+			/*
+			 * We tear down the RTT range for the full IPA
+			 * space, after everything is unmapped. Also we
+			 * descend down only if we cannot tear down a
+			 * top level RTT. Thus RMM must be able to walk
+			 * to the requested level. e.g., a block mapping
+			 * exists at L1 or L2.
+			 */
+			if (WARN_ON(level == RME_RTT_MAX_LEVEL))
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

## [15] Steven Price — 2024-06-10
*Subject: [PATCH v3 14/43] arm64: RME: Allocate/free RECs to match vCPUs*

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

See Realm Management Monitor specification (DEN0137) for more information:
https://developer.arm.com/documentation/den0137/

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v2:
 * Free rec->run earlier in kvm_destroy_realm() and adapt to previous patches.
---
 arch/arm64/include/asm/kvm_emulate.h |   2 +
 arch/arm64/include/asm/kvm_host.h    |   3 +
 arch/arm64/include/asm/kvm_rme.h     |  18 ++++
 arch/arm64/kvm/arm.c                 |   2 +
 arch/arm64/kvm/reset.c               |  11 ++
 arch/arm64/kvm/rme.c                 | 155 +++++++++++++++++++++++++++
 6 files changed, 191 insertions(+)

diff --git a/arch/arm64/include/asm/kvm_emulate.h b/arch/arm64/include/asm/kvm_emulate.h
index 56526594e3b5..590a6bad9bd4 100644
--- a/arch/arm64/include/asm/kvm_emulate.h
+++ b/arch/arm64/include/asm/kvm_emulate.h
@@ -619,6 +619,8 @@ static inline bool kvm_realm_is_created(struct kvm *kvm)
 
 static inline bool vcpu_is_rec(struct kvm_vcpu *vcpu)
 {
+	if (static_branch_unlikely(&kvm_rme_is_available))
+		return vcpu->arch.rec.mpidr != INVALID_HWID;
 	return false;
 }
 
diff --git a/arch/arm64/include/asm/kvm_host.h b/arch/arm64/include/asm/kvm_host.h
index 47c5235bf4f2..bacd2bf1f084 100644
--- a/arch/arm64/include/asm/kvm_host.h
+++ b/arch/arm64/include/asm/kvm_host.h
@@ -696,6 +696,9 @@ struct kvm_vcpu_arch {
 
 	/* Per-vcpu CCSIDR override or NULL */
 	u32 *ccsidr;
+
+	/* Realm meta data */
+	struct realm_rec rec;
 };
 
 /*
diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index e5704859a6e5..3a3aaf5d591c 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -6,6 +6,7 @@
 #ifndef __ASM_KVM_RME_H
 #define __ASM_KVM_RME_H
 
+#include <asm/rmi_smc.h>
 #include <uapi/linux/kvm.h>
 
 /**
@@ -70,6 +71,21 @@ struct realm {
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
+	struct page *aux_pages[REC_PARAMS_AUX_GRANULES];
+	struct rec_run *run;
+};
+
 void kvm_init_rme(void);
 u32 kvm_realm_ipa_limit(void);
 
@@ -77,6 +93,8 @@ int kvm_realm_enable_cap(struct kvm *kvm, struct kvm_enable_cap *cap);
 int kvm_init_realm_vm(struct kvm *kvm);
 void kvm_destroy_realm(struct kvm *kvm);
 void kvm_realm_destroy_rtts(struct kvm *kvm, u32 ia_bits);
+int kvm_create_rec(struct kvm_vcpu *vcpu);
+void kvm_destroy_rec(struct kvm_vcpu *vcpu);
 
 #define RME_RTT_BLOCK_LEVEL	2
 #define RME_RTT_MAX_LEVEL	3
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index b1df789e9013..d7c62796c9c0 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -511,6 +511,8 @@ int kvm_arch_vcpu_create(struct kvm_vcpu *vcpu)
 	/* Force users to call KVM_ARM_VCPU_INIT */
 	vcpu_clear_flag(vcpu, VCPU_INITIALIZED);
 
+	vcpu->arch.rec.mpidr = INVALID_HWID;
+
 	vcpu->arch.mmu_page_cache.gfp_zero = __GFP_ZERO;
 
 	/* Set up the timer */
diff --git a/arch/arm64/kvm/reset.c b/arch/arm64/kvm/reset.c
index 1b7b58cb121f..073c9b6b9285 100644
--- a/arch/arm64/kvm/reset.c
+++ b/arch/arm64/kvm/reset.c
@@ -134,6 +134,11 @@ int kvm_arm_vcpu_finalize(struct kvm_vcpu *vcpu, int feature)
 			return -EPERM;
 
 		return kvm_vcpu_finalize_sve(vcpu);
+	case KVM_ARM_VCPU_REC:
+		if (!kvm_is_realm(vcpu->kvm))
+			return -EINVAL;
+
+		return kvm_create_rec(vcpu);
 	}
 
 	return -EINVAL;
@@ -144,6 +149,11 @@ bool kvm_arm_vcpu_is_finalized(struct kvm_vcpu *vcpu)
 	if (vcpu_has_sve(vcpu) && !kvm_arm_vcpu_sve_finalized(vcpu))
 		return false;
 
+	if (kvm_is_realm(vcpu->kvm) &&
+	    !(vcpu_is_rec(vcpu) &&
+	      READ_ONCE(vcpu->kvm->arch.realm.state) == REALM_STATE_ACTIVE))
+		return false;
+
 	return true;
 }
 
@@ -156,6 +166,7 @@ void kvm_arm_vcpu_destroy(struct kvm_vcpu *vcpu)
 		kvm_unshare_hyp(sve_state, sve_state + vcpu_sve_state_size(vcpu));
 	kfree(sve_state);
 	kfree(vcpu->arch.ccsidr);
+	kvm_destroy_rec(vcpu);
 }
 
 static void kvm_vcpu_reset_sve(struct kvm_vcpu *vcpu)
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 7db405d2b2b2..6f0ced6e0cc1 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -422,6 +422,161 @@ void kvm_destroy_realm(struct kvm *kvm)
 	kvm_free_stage2_pgd(&kvm->arch.mmu);
 }
 
+static void free_rec_aux(struct page **aux_pages,
+			 unsigned int num_aux)
+{
+	unsigned int i;
+
+	for (i = 0; i < num_aux; i++) {
+		phys_addr_t aux_page_phys = page_to_phys(aux_pages[i]);
+
+		/* If the undelegate fails then leak the page */
+		if (WARN_ON(rmi_granule_undelegate(aux_page_phys)))
+			continue;
+
+		__free_page(aux_pages[i]);
+	}
+}
+
+static int alloc_rec_aux(struct page **aux_pages,
+			 u64 *aux_phys_pages,
+			 unsigned int num_aux)
+{
+	int ret;
+	unsigned int i;
+
+	for (i = 0; i < num_aux; i++) {
+		struct page *aux_page;
+		phys_addr_t aux_page_phys;
+
+		aux_page = alloc_page(GFP_KERNEL);
+		if (!aux_page) {
+			ret = -ENOMEM;
+			goto out_err;
+		}
+		aux_page_phys = page_to_phys(aux_page);
+		if (rmi_granule_delegate(aux_page_phys)) {
+			__free_page(aux_page);
+			ret = -ENXIO;
+			goto out_err;
+		}
+		aux_pages[i] = aux_page;
+		aux_phys_pages[i] = aux_page_phys;
+	}
+
+	return 0;
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
+	/* If the undelegate fails then leak the REC page */
+	if (WARN_ON(rmi_granule_undelegate(rec_page_phys)))
+		return;
+
+	free_page((unsigned long)rec->rec_page);
+}
+
 int kvm_init_realm_vm(struct kvm *kvm)
 {
 	struct realm_params *params;

---

## [16] Steven Price — 2024-06-10
*Subject: [PATCH v3 15/43] arm64: RME: Support for the VGIC in realms*

The RMM provides emulation of a VGIC to the realm guest but delegates
much of the handling to the host. Implement support in KVM for
saving/restoring state to/from the REC structure.

Signed-off-by: Steven Price <steven.price@arm.com>
---
v3: Changes to adapt to rebasing only.
---
 arch/arm64/kvm/arm.c          | 15 +++++++++++---
 arch/arm64/kvm/vgic/vgic-v3.c |  8 +++++++-
 arch/arm64/kvm/vgic/vgic.c    | 37 +++++++++++++++++++++++++++++++++--
 3 files changed, 54 insertions(+), 6 deletions(-)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index d7c62796c9c0..84c3dc1d89b8 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -652,17 +652,22 @@ void kvm_arch_vcpu_load(struct kvm_vcpu *vcpu, int cpu)
 
 void kvm_arch_vcpu_put(struct kvm_vcpu *vcpu)
 {
+	kvm_timer_vcpu_put(vcpu);
+	kvm_vgic_put(vcpu);
+
+	vcpu->cpu = -1;
+
+	if (vcpu_is_rec(vcpu))
+		return;
+
 	kvm_arch_vcpu_put_debug_state_flags(vcpu);
 	kvm_arch_vcpu_put_fp(vcpu);
 	if (has_vhe())
 		kvm_vcpu_put_vhe(vcpu);
-	kvm_timer_vcpu_put(vcpu);
-	kvm_vgic_put(vcpu);
 	kvm_vcpu_pmu_restore_host(vcpu);
 	kvm_arm_vmid_clear_active();
 
 	vcpu_clear_on_unsupported_cpu(vcpu);
-	vcpu->cpu = -1;
 }
 
 static void __kvm_arm_vcpu_power_off(struct kvm_vcpu *vcpu)
@@ -872,6 +877,10 @@ int kvm_arch_vcpu_run_pid_change(struct kvm_vcpu *vcpu)
 	}
 
 	if (!irqchip_in_kernel(kvm)) {
+		/* Userspace irqchip not yet supported with Realms */
+		if (kvm_is_realm(vcpu->kvm))
+			return -EOPNOTSUPP;
+
 		/*
 		 * Tell the rest of the code that there are userspace irqchip
 		 * VMs in the wild.
diff --git a/arch/arm64/kvm/vgic/vgic-v3.c b/arch/arm64/kvm/vgic/vgic-v3.c
index ed6e412cd74b..ffb42966fe63 100644
--- a/arch/arm64/kvm/vgic/vgic-v3.c
+++ b/arch/arm64/kvm/vgic/vgic-v3.c
@@ -7,9 +7,11 @@
 #include <linux/kvm.h>
 #include <linux/kvm_host.h>
 #include <kvm/arm_vgic.h>
+#include <asm/kvm_emulate.h>
 #include <asm/kvm_hyp.h>
 #include <asm/kvm_mmu.h>
 #include <asm/kvm_asm.h>
+#include <asm/rmi_smc.h>
 
 #include "vgic.h"
 
@@ -667,7 +669,8 @@ int vgic_v3_probe(const struct gic_kvm_info *info)
 			(unsigned long long)info->vcpu.start);
 	} else if (kvm_get_mode() != KVM_MODE_PROTECTED) {
 		kvm_vgic_global_state.vcpu_base = info->vcpu.start;
-		kvm_vgic_global_state.can_emulate_gicv2 = true;
+		if (!static_branch_unlikely(&kvm_rme_is_available))
+			kvm_vgic_global_state.can_emulate_gicv2 = true;
 		ret = kvm_register_vgic_device(KVM_DEV_TYPE_ARM_VGIC_V2);
 		if (ret) {
 			kvm_err("Cannot register GICv2 KVM device.\n");
@@ -734,6 +737,9 @@ void vgic_v3_put(struct kvm_vcpu *vcpu)
 {
 	struct vgic_v3_cpu_if *cpu_if = &vcpu->arch.vgic_cpu.vgic_v3;
 
+	if (vcpu_is_rec(vcpu))
+		cpu_if->vgic_vmcr = vcpu->arch.rec.run->exit.gicv3_vmcr;
+
 	kvm_call_hyp(__vgic_v3_save_vmcr_aprs, cpu_if);
 	WARN_ON(vgic_v4_put(vcpu));
 
diff --git a/arch/arm64/kvm/vgic/vgic.c b/arch/arm64/kvm/vgic/vgic.c
index f07b3ddff7d4..46f7065e993c 100644
--- a/arch/arm64/kvm/vgic/vgic.c
+++ b/arch/arm64/kvm/vgic/vgic.c
@@ -10,7 +10,9 @@
 #include <linux/list_sort.h>
 #include <linux/nospec.h>
 
+#include <asm/kvm_emulate.h>
 #include <asm/kvm_hyp.h>
+#include <asm/rmi_smc.h>
 
 #include "vgic.h"
 
@@ -843,10 +845,23 @@ static inline bool can_access_vgic_from_kernel(void)
 	return !static_branch_unlikely(&kvm_vgic_global_state.gicv3_cpuif) || has_vhe();
 }
 
+static inline void vgic_rmm_save_state(struct kvm_vcpu *vcpu)
+{
+	struct vgic_v3_cpu_if *cpu_if = &vcpu->arch.vgic_cpu.vgic_v3;
+	int i;
+
+	for (i = 0; i < kvm_vgic_global_state.nr_lr; i++) {
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
@@ -873,10 +888,28 @@ void kvm_vgic_sync_hwstate(struct kvm_vcpu *vcpu)
 	vgic_prune_ap_list(vcpu);
 }
 
+static inline void vgic_rmm_restore_state(struct kvm_vcpu *vcpu)
+{
+	struct vgic_v3_cpu_if *cpu_if = &vcpu->arch.vgic_cpu.vgic_v3;
+	int i;
+
+	for (i = 0; i < kvm_vgic_global_state.nr_lr; i++) {
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
@@ -917,7 +950,7 @@ void kvm_vgic_flush_hwstate(struct kvm_vcpu *vcpu)
 
 void kvm_vgic_load(struct kvm_vcpu *vcpu)
 {
-	if (unlikely(!vgic_initialized(vcpu->kvm)))
+	if (unlikely(!vgic_initialized(vcpu->kvm)) || vcpu_is_rec(vcpu))
 		return;
 
 	if (kvm_vgic_global_state.type == VGIC_V2)
@@ -928,7 +961,7 @@ void kvm_vgic_load(struct kvm_vcpu *vcpu)
 
 void kvm_vgic_put(struct kvm_vcpu *vcpu)
 {
-	if (unlikely(!vgic_initialized(vcpu->kvm)))
+	if (unlikely(!vgic_initialized(vcpu->kvm)) || vcpu_is_rec(vcpu))
 		return;
 
 	if (kvm_vgic_global_state.type == VGIC_V2)

---

## [17] Steven Price — 2024-06-10
*Subject: [PATCH v3 16/43] KVM: arm64: Support timers in realm RECs*

The RMM keeps track of the timer while the realm REC is running, but on
exit to the normal world KVM is responsible for handling the timers.

A later patch adds the support for propagating the timer values from the
exit data structure and calling kvm_realm_timers_update().

Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/kvm/arch_timer.c  | 45 ++++++++++++++++++++++++++++++++----
 include/kvm/arm_arch_timer.h |  2 ++
 2 files changed, 43 insertions(+), 4 deletions(-)

diff --git a/arch/arm64/kvm/arch_timer.c b/arch/arm64/kvm/arch_timer.c
index 879982b1cc73..0b2be34a9ba3 100644
--- a/arch/arm64/kvm/arch_timer.c
+++ b/arch/arm64/kvm/arch_timer.c
@@ -162,6 +162,13 @@ static void timer_set_cval(struct arch_timer_context *ctxt, u64 cval)
 
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
@@ -460,6 +467,21 @@ static void kvm_timer_update_irq(struct kvm_vcpu *vcpu, bool new_level,
 	}
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
@@ -831,6 +853,8 @@ void kvm_timer_vcpu_load(struct kvm_vcpu *vcpu)
 	if (unlikely(!timer->enabled))
 		return;
 
+	kvm_timer_unblocking(vcpu);
+
 	get_timer_map(vcpu, &map);
 
 	if (static_branch_likely(&has_gic_active_state)) {
@@ -844,8 +868,6 @@ void kvm_timer_vcpu_load(struct kvm_vcpu *vcpu)
 		kvm_timer_vcpu_load_nogic(vcpu);
 	}
 
-	kvm_timer_unblocking(vcpu);
-
 	timer_restore_state(map.direct_vtimer);
 	if (map.direct_ptimer)
 		timer_restore_state(map.direct_ptimer);
@@ -988,7 +1010,9 @@ static void timer_context_init(struct kvm_vcpu *vcpu, int timerid)
 
 	ctxt->vcpu = vcpu;
 
-	if (timerid == TIMER_VTIMER)
+	if (kvm_is_realm(vcpu->kvm))
+		ctxt->offset.vm_offset = NULL;
+	else if (timerid == TIMER_VTIMER)
 		ctxt->offset.vm_offset = &kvm->arch.timer_data.voffset;
 	else
 		ctxt->offset.vm_offset = &kvm->arch.timer_data.poffset;
@@ -1011,13 +1035,19 @@ static void timer_context_init(struct kvm_vcpu *vcpu, int timerid)
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
 
@@ -1525,6 +1555,13 @@ int kvm_timer_enable(struct kvm_vcpu *vcpu)
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
diff --git a/include/kvm/arm_arch_timer.h b/include/kvm/arm_arch_timer.h
index c819c5d16613..d8ab297560d0 100644
--- a/include/kvm/arm_arch_timer.h
+++ b/include/kvm/arm_arch_timer.h
@@ -112,6 +112,8 @@ int kvm_arm_timer_set_attr(struct kvm_vcpu *vcpu, struct kvm_device_attr *attr);
 int kvm_arm_timer_get_attr(struct kvm_vcpu *vcpu, struct kvm_device_attr *attr);
 int kvm_arm_timer_has_attr(struct kvm_vcpu *vcpu, struct kvm_device_attr *attr);
 
+void kvm_realm_timers_update(struct kvm_vcpu *vcpu);
+
 u64 kvm_phys_timer_read(void);
 
 void kvm_timer_vcpu_load(struct kvm_vcpu *vcpu);

---

## [18] Steven Price — 2024-06-10
*Subject: [PATCH v3 17/43] arm64: RME: Allow VMM to set RIPAS*

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
freed. A spare, delegated page (spare_page) is used for this purpose.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes from v2:
 * {alloc,free}_delegated_page() moved from previous patch to this one.
 * alloc_delegated_page() now takes a gfp_t flags parameter.
 * Fix the reference counting of guestmem pages to avoid leaking memory.
 * Several misc code improvements and extra comments.
---
 arch/arm64/include/asm/kvm_rme.h |  17 ++
 arch/arm64/kvm/mmu.c             |   8 +-
 arch/arm64/kvm/rme.c             | 481 ++++++++++++++++++++++++++++++-
 3 files changed, 501 insertions(+), 5 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index 3a3aaf5d591c..c064bfb080ad 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -96,6 +96,15 @@ void kvm_realm_destroy_rtts(struct kvm *kvm, u32 ia_bits);
 int kvm_create_rec(struct kvm_vcpu *vcpu);
 void kvm_destroy_rec(struct kvm_vcpu *vcpu);
 
+void kvm_realm_unmap_range(struct kvm *kvm,
+			   unsigned long ipa,
+			   u64 size,
+			   bool unmap_private);
+int realm_set_ipa_state(struct kvm_vcpu *vcpu,
+			unsigned long addr, unsigned long end,
+			unsigned long ripas,
+			unsigned long *top_ipa);
+
 #define RME_RTT_BLOCK_LEVEL	2
 #define RME_RTT_MAX_LEVEL	3
 
@@ -114,4 +123,12 @@ static inline unsigned long rme_rtt_level_mapsize(int level)
 	return (1UL << RME_RTT_LEVEL_SHIFT(level));
 }
 
+static inline bool realm_is_addr_protected(struct realm *realm,
+					   unsigned long addr)
+{
+	unsigned int ia_bits = realm->ia_bits;
+
+	return !(addr & ~(BIT(ia_bits - 1) - 1));
+}
+
 #endif
diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index 83bd10845efb..2e4e883d671e 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -310,6 +310,7 @@ static void invalidate_icache_guest_page(void *va, size_t size)
  * @start: The intermediate physical base address of the range to unmap
  * @size:  The size of the area to unmap
  * @may_block: Whether or not we are permitted to block
+ * @only_shared: If true then protected mappings should not be unmapped
  *
  * Clear a range of stage-2 mappings, lowering the various ref-counts.  Must
  * be called while holding mmu_lock (unless for freeing the stage2 pgd before
@@ -317,7 +318,7 @@ static void invalidate_icache_guest_page(void *va, size_t size)
  * with things behind our backs.
  */
 static void __unmap_stage2_range(struct kvm_s2_mmu *mmu, phys_addr_t start, u64 size,
-				 bool may_block)
+				 bool may_block, bool only_shared)
 {
 	struct kvm *kvm = kvm_s2_mmu_to_kvm(mmu);
 	phys_addr_t end = start + size;
@@ -330,7 +331,7 @@ static void __unmap_stage2_range(struct kvm_s2_mmu *mmu, phys_addr_t start, u64
 
 static void unmap_stage2_range(struct kvm_s2_mmu *mmu, phys_addr_t start, u64 size)
 {
-	__unmap_stage2_range(mmu, start, size, true);
+	__unmap_stage2_range(mmu, start, size, true, false);
 }
 
 static void stage2_flush_memslot(struct kvm *kvm,
@@ -1773,7 +1774,8 @@ bool kvm_unmap_gfn_range(struct kvm *kvm, struct kvm_gfn_range *range)
 
 	__unmap_stage2_range(&kvm->arch.mmu, range->start << PAGE_SHIFT,
 			     (range->end - range->start) << PAGE_SHIFT,
-			     range->may_block);
+			     range->may_block,
+			     range->only_shared);
 
 	return false;
 }
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 6f0ced6e0cc1..1fa9991d708b 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -47,9 +47,197 @@ static int rmi_check_version(void)
 	return 0;
 }
 
-u32 kvm_realm_ipa_limit(void)
+static phys_addr_t alloc_delegated_page(struct realm *realm,
+					struct kvm_mmu_memory_cache *mc,
+					gfp_t flags)
 {
-	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_S2SZ);
+	phys_addr_t phys = PHYS_ADDR_MAX;
+	void *virt;
+
+	if (realm->spare_page != PHYS_ADDR_MAX) {
+		swap(realm->spare_page, phys);
+		goto out;
+	}
+
+	if (mc)
+		virt = kvm_mmu_memory_cache_alloc(mc);
+	else
+		virt = (void *)__get_free_page(flags);
+
+	if (!virt)
+		goto out;
+
+	phys = virt_to_phys(virt);
+
+	if (rmi_granule_delegate(phys)) {
+		free_page((unsigned long)virt);
+
+		phys = PHYS_ADDR_MAX;
+	}
+
+out:
+	return phys;
+}
+
+static void free_delegated_page(struct realm *realm, phys_addr_t phys)
+{
+	if (realm->spare_page == PHYS_ADDR_MAX) {
+		realm->spare_page = phys;
+		return;
+	}
+
+	if (WARN_ON(rmi_granule_undelegate(phys))) {
+		/* Undelegate failed: leak the page */
+		return;
+	}
+
+	free_page((unsigned long)phys_to_virt(phys));
+}
+
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
+static int realm_destroy_protected(struct realm *realm,
+				   unsigned long ipa,
+				   unsigned long *next_addr)
+{
+	unsigned long rd = virt_to_phys(realm->rd);
+	unsigned long addr;
+	phys_addr_t rtt;
+	int ret;
+
+loop:
+	ret = rmi_data_destroy(rd, ipa, &addr, next_addr);
+	if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
+		if (*next_addr > ipa)
+			return 0; /* UNASSIGNED */
+		rtt = alloc_delegated_page(realm, NULL, GFP_KERNEL);
+		if (WARN_ON(rtt == PHYS_ADDR_MAX))
+			return -1;
+		/*
+		 * ASSIGNED - ipa is mapped as a block, so split. The index
+		 * from the return code should be 2 otherwise it appears
+		 * there's a huge page bigger than allowed
+		 */
+		WARN_ON(RMI_RETURN_INDEX(ret) != 2);
+		ret = realm_rtt_create(realm, ipa, 3, rtt);
+		if (WARN_ON(ret)) {
+			free_delegated_page(realm, rtt);
+			return -1;
+		}
+		/* retry */
+		goto loop;
+	} else if (WARN_ON(ret)) {
+		return -1;
+	}
+	ret = rmi_granule_undelegate(addr);
+
+	/*
+	 * If the undelegate fails then something has gone seriously
+	 * wrong: take an extra reference to just leak the page
+	 */
+	if (!WARN_ON(ret))
+		put_page(phys_to_page(addr));
+
+	return 0;
+}
+
+static void realm_unmap_range_shared(struct kvm *kvm,
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
+	if (WARN_ON(level > RME_RTT_MAX_LEVEL))
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
+			realm_unmap_range_shared(kvm, level + 1, addr,
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
+				realm_unmap_range_shared(kvm, level + 1, addr,
+							 next_addr);
+			}
+			break;
+		default:
+			WARN_ON(1);
+			return;
+		}
+	}
+}
+
+static void realm_unmap_range_private(struct kvm *kvm,
+				      unsigned long start,
+				      unsigned long end)
+{
+	struct realm *realm = &kvm->arch.realm;
+	ssize_t map_size = RME_PAGE_SIZE;
+	unsigned long next_addr, addr;
+
+	for (addr = start; addr < end; addr = next_addr) {
+		int ret;
+
+		next_addr = ALIGN(addr + 1, map_size);
+
+		ret = realm_destroy_protected(realm, addr, &next_addr);
+
+		if (WARN_ON(ret))
+			break;
+	}
 }
 
 static int get_start_level(struct realm *realm)
@@ -57,6 +245,26 @@ static int get_start_level(struct realm *realm)
 	return 4 - stage2_pgtable_levels(realm->ia_bits);
 }
 
+static void realm_unmap_range(struct kvm *kvm,
+			      unsigned long start,
+			      unsigned long end,
+			      bool unmap_private)
+{
+	struct realm *realm = &kvm->arch.realm;
+
+	if (realm->state == REALM_STATE_NONE)
+		return;
+
+	realm_unmap_range_shared(kvm, get_start_level(realm), start, end);
+	if (unmap_private)
+		realm_unmap_range_private(kvm, start, end);
+}
+
+u32 kvm_realm_ipa_limit(void)
+{
+	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_S2SZ);
+}
+
 static int realm_create_rd(struct kvm *kvm)
 {
 	struct realm *realm = &kvm->arch.realm;
@@ -140,6 +348,30 @@ static int realm_rtt_destroy(struct realm *realm, unsigned long addr,
 	return ret;
 }
 
+static int realm_create_rtt_levels(struct realm *realm,
+				   unsigned long ipa,
+				   int level,
+				   int max_level,
+				   struct kvm_mmu_memory_cache *mc)
+{
+	if (WARN_ON(level == max_level))
+		return 0;
+
+	while (level++ < max_level) {
+		phys_addr_t rtt = alloc_delegated_page(realm, mc, GFP_KERNEL);
+
+		if (rtt == PHYS_ADDR_MAX)
+			return -ENOMEM;
+
+		if (realm_rtt_create(realm, ipa, level, rtt)) {
+			free_delegated_page(realm, rtt);
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
@@ -231,6 +463,90 @@ static int realm_tear_down_rtt_range(struct realm *realm,
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
+	if (WARN_ON(level > RME_RTT_MAX_LEVEL))
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
+			if (!WARN_ON(rmi_granule_undelegate(rtt_granule)))
+				free_page((unsigned long)phys_to_virt(rtt_granule));
+			break;
+		case RMI_ERROR_RTT:
+			if (level == RME_RTT_MAX_LEVEL ||
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
+static int realm_fold_rtt_range(struct realm *realm,
+				unsigned long start, unsigned long end)
+{
+	return realm_fold_rtt_level(realm, get_start_level(realm) + 1,
+				    start, end);
+}
+
+static void ensure_spare_page(struct realm *realm)
+{
+	phys_addr_t tmp_rtt;
+
+	/*
+	 * Make sure we have a spare delegated page for tearing down the
+	 * block mappings. We do this by allocating then freeing a page.
+	 * We must use Atomic allocations as we are called with kvm->mmu_lock
+	 * held.
+	 */
+	tmp_rtt = alloc_delegated_page(realm, NULL, GFP_ATOMIC);
+
+	/*
+	 * If the allocation failed, continue as we may not have a block level
+	 * mapping so it may not be fatal, otherwise free it to assign it
+	 * to the spare page.
+	 */
+	if (tmp_rtt != PHYS_ADDR_MAX)
+		free_delegated_page(realm, tmp_rtt);
+}
+
 void kvm_realm_destroy_rtts(struct kvm *kvm, u32 ia_bits)
 {
 	struct realm *realm = &kvm->arch.realm;
@@ -238,6 +554,155 @@ void kvm_realm_destroy_rtts(struct kvm *kvm, u32 ia_bits)
 	WARN_ON(realm_tear_down_rtt_range(realm, 0, (1UL << ia_bits)));
 }
 
+void kvm_realm_unmap_range(struct kvm *kvm, unsigned long ipa, u64 size,
+			   bool unmap_private)
+{
+	unsigned long end = ipa + size;
+	struct realm *realm = &kvm->arch.realm;
+
+	end = min(BIT(realm->ia_bits - 1), end);
+
+	ensure_spare_page(realm);
+
+	realm_unmap_range(kvm, ipa, end, unmap_private);
+
+	if (unmap_private)
+		realm_fold_rtt_range(realm, ipa, end);
+}
+
+static int find_map_level(struct realm *realm,
+			  unsigned long start,
+			  unsigned long end)
+{
+	int level = RME_RTT_MAX_LEVEL;
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
+int realm_set_ipa_state(struct kvm_vcpu *vcpu,
+			unsigned long start,
+			unsigned long end,
+			unsigned long ripas,
+			unsigned long *top_ipa)
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
+		if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
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
+		} else if (RMI_RETURN_STATUS(ret) != RMI_SUCCESS) {
+			WARN(1, "Unexpected error in %s: %#x\n", __func__,
+			     ret);
+			ret = -EINVAL;
+			break;
+		}
+		ipa = next;
+	}
+
+	*top_ipa = ipa;
+
+	if (ripas == RMI_EMPTY && ipa != start) {
+		realm_unmap_range_private(kvm, start, ipa);
+		realm_fold_rtt_range(realm, start, ipa);
+	}
+
+	return ret;
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
+				    struct kvm_cap_arm_rme_init_ipa_args *args)
+{
+	gpa_t addr, end;
+	struct realm *realm = &kvm->arch.realm;
+
+	addr = args->init_ipa_base;
+	end = addr + args->init_ipa_size;
+
+	if (end < addr)
+		return -EINVAL;
+
+	if (kvm_realm_state(kvm) != REALM_STATE_NEW)
+		return -EINVAL;
+
+	return realm_init_ipa_state(realm, addr, end);
+}
+
 /* Protects access to rme_vmid_bitmap */
 static DEFINE_SPINLOCK(rme_vmid_lock);
 static unsigned long *rme_vmid_bitmap;
@@ -363,6 +828,18 @@ int kvm_realm_enable_cap(struct kvm *kvm, struct kvm_enable_cap *cap)
 	case KVM_CAP_ARM_RME_CREATE_RD:
 		r = kvm_create_realm(kvm);
 		break;
+	case KVM_CAP_ARM_RME_INIT_IPA_REALM: {
+		struct kvm_cap_arm_rme_init_ipa_args args;
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

## [19] Steven Price — 2024-06-10
*Subject: [PATCH v3 18/43] arm64: RME: Handle realm enter/exit*

Entering a realm is done using a SMC call to the RMM. On exit the
exit-codes need to be handled slightly differently to the normal KVM
path so define our own functions for realm enter/exit and hook them
in if the guest is a realm guest.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v2:
 * realm_set_ipa_state() now provides an output parameter for the
   top_iap that was changed. Use this to signal the VMM with the correct
   range that has been transitioned.
 * Adapt to previous patch changes.
---
 arch/arm64/include/asm/kvm_rme.h |   3 +
 arch/arm64/kvm/Makefile          |   2 +-
 arch/arm64/kvm/arm.c             |  19 +++-
 arch/arm64/kvm/rme-exit.c        | 181 +++++++++++++++++++++++++++++++
 arch/arm64/kvm/rme.c             |  11 ++
 5 files changed, 210 insertions(+), 6 deletions(-)
 create mode 100644 arch/arm64/kvm/rme-exit.c

diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index c064bfb080ad..0e44b20cfa48 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -96,6 +96,9 @@ void kvm_realm_destroy_rtts(struct kvm *kvm, u32 ia_bits);
 int kvm_create_rec(struct kvm_vcpu *vcpu);
 void kvm_destroy_rec(struct kvm_vcpu *vcpu);
 
+int kvm_rec_enter(struct kvm_vcpu *vcpu);
+int handle_rme_exit(struct kvm_vcpu *vcpu, int rec_run_status);
+
 void kvm_realm_unmap_range(struct kvm *kvm,
 			   unsigned long ipa,
 			   u64 size,
diff --git a/arch/arm64/kvm/Makefile b/arch/arm64/kvm/Makefile
index 5e79e5eee88d..9f893e86cac9 100644
--- a/arch/arm64/kvm/Makefile
+++ b/arch/arm64/kvm/Makefile
@@ -21,7 +21,7 @@ kvm-y += arm.o mmu.o mmio.o psci.o hypercalls.o pvtime.o \
 	 vgic/vgic-mmio.o vgic/vgic-mmio-v2.o \
 	 vgic/vgic-mmio-v3.o vgic/vgic-kvm-device.o \
 	 vgic/vgic-its.o vgic/vgic-debug.o \
-	 rme.o
+	 rme.o rme-exit.o
 
 kvm-$(CONFIG_HW_PERF_EVENTS)  += pmu-emul.o pmu.o
 kvm-$(CONFIG_ARM64_PTR_AUTH)  += pauth.o
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 84c3dc1d89b8..0b51ea30d679 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -1243,7 +1243,10 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 		trace_kvm_entry(*vcpu_pc(vcpu));
 		guest_timing_enter_irqoff();
 
-		ret = kvm_arm_vcpu_enter_exit(vcpu);
+		if (vcpu_is_rec(vcpu))
+			ret = kvm_rec_enter(vcpu);
+		else
+			ret = kvm_arm_vcpu_enter_exit(vcpu);
 
 		vcpu->mode = OUTSIDE_GUEST_MODE;
 		vcpu->stat.exits++;
@@ -1297,10 +1300,13 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 
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
 
@@ -1323,7 +1329,10 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 			ret = ARM_EXCEPTION_IL;
 		}
 
-		ret = handle_exit(vcpu, ret);
+		if (vcpu_is_rec(vcpu))
+			ret = handle_rme_exit(vcpu, ret);
+		else
+			ret = handle_exit(vcpu, ret);
 	}
 
 	/* Tell userspace about in-kernel device output levels */
diff --git a/arch/arm64/kvm/rme-exit.c b/arch/arm64/kvm/rme-exit.c
new file mode 100644
index 000000000000..f4e45d475798
--- /dev/null
+++ b/arch/arm64/kvm/rme-exit.c
@@ -0,0 +1,181 @@
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
+	pr_err("[vcpu %d] Unhandled exit reason from realm (ESR: %#llx)\n",
+	       vcpu->vcpu_id, rec->run->exit.esr);
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
+	pr_err("[vcpu %d] Unhandled instruction abort (ESR: %#llx).\n",
+	       vcpu->vcpu_id, rec->run->exit.esr);
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
+
+	if (ret >= 0 && !is_write)
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
+	int ret;
+
+	for (i = 0; i < REC_RUN_GPRS; i++)
+		vcpu_set_reg(vcpu, i, rec->run->exit.gprs[i]);
+
+	ret = kvm_smccc_call_handler(vcpu);
+
+	for (i = 0; i < REC_RUN_GPRS; i++)
+		rec->run->enter.gprs[i] = vcpu_get_reg(vcpu, i);
+
+	return ret;
+}
+
+static int rec_exit_ripas_change(struct kvm_vcpu *vcpu)
+{
+	struct kvm *kvm = vcpu->kvm;
+	struct realm *realm = &kvm->arch.realm;
+	struct realm_rec *rec = &vcpu->arch.rec;
+	unsigned long base = rec->run->exit.ripas_base;
+	unsigned long top = rec->run->exit.ripas_top;
+	unsigned long ripas = rec->run->exit.ripas_value & 1;
+	unsigned long top_ipa;
+	int ret = -EINVAL;
+
+	if (realm_is_addr_protected(realm, base) &&
+	    realm_is_addr_protected(realm, top - 1)) {
+		kvm_mmu_topup_memory_cache(&vcpu->arch.mmu_page_cache,
+					   kvm_mmu_cache_min_pages(vcpu->arch.hw_mmu));
+		write_lock(&kvm->mmu_lock);
+		ret = realm_set_ipa_state(vcpu, base, top, ripas, &top_ipa);
+		write_unlock(&kvm->mmu_lock);
+	}
+
+	WARN(ret && ret != -ENOMEM,
+	     "Unable to satisfy SET_IPAS for %#lx - %#lx, ripas: %#lx\n",
+	     base, top, ripas);
+
+	/* Exit to VMM to complete the change */
+	kvm_prepare_memory_fault_exit(vcpu, base, top_ipa - base, false, false,
+				      ripas == 1);
+
+	return 0;
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
+int handle_rme_exit(struct kvm_vcpu *vcpu, int rec_run_ret)
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
index 1fa9991d708b..fd4162af551d 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -899,6 +899,17 @@ void kvm_destroy_realm(struct kvm *kvm)
 	kvm_free_stage2_pgd(&kvm->arch.mmu);
 }
 
+int kvm_rec_enter(struct kvm_vcpu *vcpu)
+{
+	struct realm_rec *rec = &vcpu->arch.rec;
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

## [20] Steven Price — 2024-06-10
*Subject: [PATCH v3 19/43] KVM: arm64: Handle realm MMIO emulation*

MMIO emulation for a realm cannot be done directly with the VM's
registers as they are protected from the host. However, for emulatable
data aborts, the RMM uses GPRS[0] to provide the read/written value.
We can transfer this from/to the equivalent VCPU's register entry and
then depend on the generic MMIO handling code in KVM.

For a MMIO read, the value is placed in the shared RecExit structure
during kvm_handle_mmio_return() rather than in the VCPU's register
entry.

Signed-off-by: Steven Price <steven.price@arm.com>
---
v3: Adapt to previous patch changes
---
 arch/arm64/kvm/mmio.c     | 10 +++++++++-
 arch/arm64/kvm/rme-exit.c |  6 ++++++
 2 files changed, 15 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/kvm/mmio.c b/arch/arm64/kvm/mmio.c
index cd6b7b83e2c3..dbd06ca368e8 100644
--- a/arch/arm64/kvm/mmio.c
+++ b/arch/arm64/kvm/mmio.c
@@ -6,6 +6,7 @@
 
 #include <linux/kvm_host.h>
 #include <asm/kvm_emulate.h>
+#include <asm/rmi_smc.h>
 #include <trace/events/kvm.h>
 
 #include "trace.h"
@@ -90,6 +91,9 @@ int kvm_handle_mmio_return(struct kvm_vcpu *vcpu)
 
 	vcpu->mmio_needed = 0;
 
+	if (vcpu_is_rec(vcpu))
+		vcpu->arch.rec.run->enter.flags |= RMI_EMULATED_MMIO;
+
 	if (!kvm_vcpu_dabt_iswrite(vcpu)) {
 		struct kvm_run *run = vcpu->run;
 
@@ -108,7 +112,11 @@ int kvm_handle_mmio_return(struct kvm_vcpu *vcpu)
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
diff --git a/arch/arm64/kvm/rme-exit.c b/arch/arm64/kvm/rme-exit.c
index f4e45d475798..03ed147f7926 100644
--- a/arch/arm64/kvm/rme-exit.c
+++ b/arch/arm64/kvm/rme-exit.c
@@ -25,6 +25,12 @@ static int rec_exit_reason_notimpl(struct kvm_vcpu *vcpu)
 
 static int rec_exit_sync_dabt(struct kvm_vcpu *vcpu)
 {
+	struct realm_rec *rec = &vcpu->arch.rec;
+
+	if (kvm_vcpu_dabt_iswrite(vcpu) && kvm_vcpu_dabt_isvalid(vcpu))
+		vcpu_set_reg(vcpu, kvm_vcpu_dabt_get_rd(vcpu),
+			     rec->run->exit.gprs[0]);
+
 	return kvm_handle_guest_abort(vcpu);
 }

---

## [21] Steven Price — 2024-06-10
*Subject: [PATCH v3 20/43] arm64: RME: Allow populating initial contents*

The VMM needs to populate the realm with some data before starting (e.g.
a kernel and initrd). This is measured by the RMM and used as part of
the attestation later on.

For now only 4k mappings are supported, future work may add support for
larger mappings.

Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
v3: Minor changes to simplify the code. Make the 4k only RMM mapping
support more obvious with a 'FIXME' in the code.
---
 arch/arm64/kvm/rme.c | 223 +++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 223 insertions(+)

diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index fd4162af551d..2c4e28b457be 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -4,6 +4,7 @@
  */
 
 #include <linux/kvm_host.h>
+#include <linux/hugetlb.h>
 
 #include <asm/kvm_emulate.h>
 #include <asm/kvm_mmu.h>
@@ -570,6 +571,216 @@ void kvm_realm_unmap_range(struct kvm *kvm, unsigned long ipa, u64 size,
 		realm_fold_rtt_range(realm, ipa, end);
 }
 
+static int realm_create_protected_data_page(struct realm *realm,
+					    unsigned long ipa,
+					    struct page *dst_page,
+					    struct page *src_page,
+					    unsigned long flags)
+{
+	phys_addr_t dst_phys, src_phys;
+	int ret;
+
+	dst_phys = page_to_phys(dst_page);
+	src_phys = page_to_phys(src_page);
+
+	if (rmi_granule_delegate(dst_phys))
+		return -ENXIO;
+
+	ret = rmi_data_create(virt_to_phys(realm->rd), dst_phys, ipa, src_phys,
+			      flags);
+
+	if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
+		/* Create missing RTTs and retry */
+		int level = RMI_RETURN_INDEX(ret);
+
+		ret = realm_create_rtt_levels(realm, ipa, level,
+					      RME_RTT_MAX_LEVEL, NULL);
+		if (ret)
+			goto err;
+
+		ret = rmi_data_create(virt_to_phys(realm->rd), dst_phys, ipa,
+				      src_phys, flags);
+	}
+
+	if (!ret)
+		return 0;
+
+err:
+	if (WARN_ON(rmi_granule_undelegate(dst_phys))) {
+		/* Page can't be returned to NS world so is lost */
+		get_page(dst_page);
+	}
+	return -ENXIO;
+}
+
+static int fold_rtt(struct realm *realm, unsigned long addr, int level)
+{
+	phys_addr_t rtt_addr;
+	int ret;
+
+	ret = realm_rtt_fold(realm, addr, level + 1, &rtt_addr);
+	if (ret)
+		return ret;
+
+	free_delegated_page(realm, rtt_addr);
+
+	return 0;
+}
+
+static int populate_par_region(struct kvm *kvm,
+			       phys_addr_t ipa_base,
+			       phys_addr_t ipa_end,
+			       u32 flags)
+{
+	struct realm *realm = &kvm->arch.realm;
+	struct kvm_memory_slot *memslot;
+	gfn_t base_gfn, end_gfn;
+	int idx;
+	phys_addr_t ipa;
+	int ret = 0;
+	struct page *tmp_page;
+	unsigned long data_flags = 0;
+
+	base_gfn = gpa_to_gfn(ipa_base);
+	end_gfn = gpa_to_gfn(ipa_end);
+
+	if (flags & KVM_ARM_RME_POPULATE_FLAGS_MEASURE)
+		data_flags = RMI_MEASURE_CONTENT;
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
+	tmp_page = alloc_page(GFP_KERNEL);
+	if (!tmp_page) {
+		ret = -ENOMEM;
+		goto out;
+	}
+
+	mmap_read_lock(current->mm);
+
+	ipa = ipa_base;
+	while (ipa < ipa_end) {
+		struct vm_area_struct *vma;
+		unsigned long map_size;
+		unsigned int vma_shift;
+		unsigned long offset;
+		unsigned long hva;
+		struct page *page;
+		kvm_pfn_t pfn;
+		int level;
+
+		hva = gfn_to_hva_memslot(memslot, gpa_to_gfn(ipa));
+		vma = vma_lookup(current->mm, hva);
+		if (!vma) {
+			ret = -EFAULT;
+			break;
+		}
+
+		/* FIXME: Currently we only support 4k sized mappings */
+		vma_shift = PAGE_SHIFT;
+
+		map_size = 1 << vma_shift;
+
+		ipa = ALIGN_DOWN(ipa, map_size);
+
+		switch (map_size) {
+		case RME_L2_BLOCK_SIZE:
+			level = 2;
+			break;
+		case PAGE_SIZE:
+			level = 3;
+			break;
+		default:
+			WARN_ONCE(1, "Unsupport vma_shift %d", vma_shift);
+			ret = -EFAULT;
+			break;
+		}
+
+		pfn = gfn_to_pfn_memslot(memslot, gpa_to_gfn(ipa));
+
+		if (is_error_pfn(pfn)) {
+			ret = -EFAULT;
+			break;
+		}
+
+		if (level < RME_RTT_MAX_LEVEL) {
+			/*
+			 * A temporary RTT is needed during the map, precreate
+			 * it, however if there is an error (e.g. missing
+			 * parent tables) this will be handled in the
+			 * realm_create_protected_data_page() call.
+			 */
+			realm_create_rtt_levels(realm, ipa, level,
+						RME_RTT_MAX_LEVEL, NULL);
+		}
+
+		page = pfn_to_page(pfn);
+
+		for (offset = 0; offset < map_size && !ret;
+		     offset += PAGE_SIZE, page++) {
+			phys_addr_t page_ipa = ipa + offset;
+
+			ret = realm_create_protected_data_page(realm, page_ipa,
+							       page, tmp_page,
+							       data_flags);
+		}
+		if (ret)
+			goto err_release_pfn;
+
+		if (level == 2)
+			fold_rtt(realm, ipa, level);
+
+		ipa += map_size;
+		kvm_release_pfn_dirty(pfn);
+err_release_pfn:
+		if (ret) {
+			kvm_release_pfn_clean(pfn);
+			break;
+		}
+	}
+
+	mmap_read_unlock(current->mm);
+	__free_page(tmp_page);
+
+out:
+	srcu_read_unlock(&kvm->srcu, idx);
+	return ret;
+}
+
+static int kvm_populate_realm(struct kvm *kvm,
+			      struct kvm_cap_arm_rme_populate_realm_args *args)
+{
+	phys_addr_t ipa_base, ipa_end;
+
+	if (kvm_realm_state(kvm) != REALM_STATE_NEW)
+		return -EINVAL;
+
+	if (!IS_ALIGNED(args->populate_ipa_base, PAGE_SIZE) ||
+	    !IS_ALIGNED(args->populate_ipa_size, PAGE_SIZE))
+		return -EINVAL;
+
+	if (args->flags & ~RMI_MEASURE_CONTENT)
+		return -EINVAL;
+
+	ipa_base = args->populate_ipa_base;
+	ipa_end = ipa_base + args->populate_ipa_size;
+
+	if (ipa_end < ipa_base)
+		return -EINVAL;
+
+	return populate_par_region(kvm, ipa_base, ipa_end, args->flags);
+}
+
 static int find_map_level(struct realm *realm,
 			  unsigned long start,
 			  unsigned long end)
@@ -840,6 +1051,18 @@ int kvm_realm_enable_cap(struct kvm *kvm, struct kvm_enable_cap *cap)
 		r = kvm_init_ipa_range_realm(kvm, &args);
 		break;
 	}
+	case KVM_CAP_ARM_RME_POPULATE_REALM: {
+		struct kvm_cap_arm_rme_populate_realm_args args;
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

## [22] Steven Price — 2024-06-10
*Subject: [PATCH v3 21/43] arm64: RME: Runtime faulting of memory*

At runtime if the realm guest accesses memory which hasn't yet been
mapped then KVM needs to either populate the region or fault the guest.

For memory in the lower (protected) region of IPA a fresh page is
provided to the RMM which will zero the contents. For memory in the
upper (shared) region of IPA, the memory from the memslot is mapped
into the realm VM non secure.

Signed-off-by: Steven Price <steven.price@arm.com>
---
Changes since v2:
 * Avoid leaking memory if failing to map it in the realm.
 * Correctly mask RTT based on LPA2 flag (see rtt_get_phys()).
 * Adapt to changes in previous patches.
---
 arch/arm64/include/asm/kvm_emulate.h |  10 ++
 arch/arm64/include/asm/kvm_rme.h     |  10 ++
 arch/arm64/kvm/mmu.c                 | 121 +++++++++++++++-
 arch/arm64/kvm/rme.c                 | 205 +++++++++++++++++++++++++--
 4 files changed, 326 insertions(+), 20 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_emulate.h b/arch/arm64/include/asm/kvm_emulate.h
index 590a6bad9bd4..27c58bbdf50b 100644
--- a/arch/arm64/include/asm/kvm_emulate.h
+++ b/arch/arm64/include/asm/kvm_emulate.h
@@ -617,6 +617,16 @@ static inline bool kvm_realm_is_created(struct kvm *kvm)
 	return kvm_is_realm(kvm) && kvm_realm_state(kvm) != REALM_STATE_NONE;
 }
 
+static inline gpa_t kvm_gpa_stolen_bits(struct kvm *kvm)
+{
+	if (kvm_is_realm(kvm)) {
+		struct realm *realm = &kvm->arch.realm;
+
+		return BIT(realm->ia_bits - 1);
+	}
+	return 0;
+}
+
 static inline bool vcpu_is_rec(struct kvm_vcpu *vcpu)
 {
 	if (static_branch_unlikely(&kvm_rme_is_available))
diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index 0e44b20cfa48..c50854f44674 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -103,6 +103,16 @@ void kvm_realm_unmap_range(struct kvm *kvm,
 			   unsigned long ipa,
 			   u64 size,
 			   bool unmap_private);
+int realm_map_protected(struct realm *realm,
+			unsigned long base_ipa,
+			struct page *dst_page,
+			unsigned long map_size,
+			struct kvm_mmu_memory_cache *memcache);
+int realm_map_non_secure(struct realm *realm,
+			 unsigned long ipa,
+			 struct page *page,
+			 unsigned long map_size,
+			 struct kvm_mmu_memory_cache *memcache);
 int realm_set_ipa_state(struct kvm_vcpu *vcpu,
 			unsigned long addr, unsigned long end,
 			unsigned long ripas,
diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index 2e4e883d671e..5eb5af0ff5d7 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -325,8 +325,13 @@ static void __unmap_stage2_range(struct kvm_s2_mmu *mmu, phys_addr_t start, u64
 
 	lockdep_assert_held_write(&kvm->mmu_lock);
 	WARN_ON(size & ~PAGE_MASK);
-	WARN_ON(stage2_apply_range(mmu, start, end, kvm_pgtable_stage2_unmap,
-				   may_block));
+
+	if (kvm_is_realm(kvm))
+		kvm_realm_unmap_range(kvm, start, size, !only_shared);
+	else
+		WARN_ON(stage2_apply_range(mmu, start, end,
+					   kvm_pgtable_stage2_unmap,
+					   may_block));
 }
 
 static void unmap_stage2_range(struct kvm_s2_mmu *mmu, phys_addr_t start, u64 size)
@@ -340,7 +345,11 @@ static void stage2_flush_memslot(struct kvm *kvm,
 	phys_addr_t addr = memslot->base_gfn << PAGE_SHIFT;
 	phys_addr_t end = addr + PAGE_SIZE * memslot->npages;
 
-	stage2_apply_range_resched(&kvm->arch.mmu, addr, end, kvm_pgtable_stage2_flush);
+	if (kvm_is_realm(kvm))
+		kvm_realm_unmap_range(kvm, addr, end - addr, false);
+	else
+		stage2_apply_range_resched(&kvm->arch.mmu, addr, end,
+					   kvm_pgtable_stage2_flush);
 }
 
 /**
@@ -997,6 +1006,10 @@ void stage2_unmap_vm(struct kvm *kvm)
 	struct kvm_memory_slot *memslot;
 	int idx, bkt;
 
+	/* For realms this is handled by the RMM so nothing to do here */
+	if (kvm_is_realm(kvm))
+		return;
+
 	idx = srcu_read_lock(&kvm->srcu);
 	mmap_read_lock(current->mm);
 	write_lock(&kvm->mmu_lock);
@@ -1020,6 +1033,7 @@ void kvm_free_stage2_pgd(struct kvm_s2_mmu *mmu)
 	if (kvm_is_realm(kvm) &&
 	    (kvm_realm_state(kvm) != REALM_STATE_DEAD &&
 	     kvm_realm_state(kvm) != REALM_STATE_NONE)) {
+		unmap_stage2_range(mmu, 0, (~0ULL) & PAGE_MASK);
 		write_unlock(&kvm->mmu_lock);
 		kvm_realm_destroy_rtts(kvm, pgt->ia_bits);
 		return;
@@ -1383,6 +1397,71 @@ static bool kvm_vma_mte_allowed(struct vm_area_struct *vma)
 	return vma->vm_flags & VM_MTE_ALLOWED;
 }
 
+static int realm_map_ipa(struct kvm *kvm, phys_addr_t ipa,
+			 kvm_pfn_t pfn, unsigned long map_size,
+			 enum kvm_pgtable_prot prot,
+			 struct kvm_mmu_memory_cache *memcache)
+{
+	struct realm *realm = &kvm->arch.realm;
+	struct page *page = pfn_to_page(pfn);
+
+	if (WARN_ON(!(prot & KVM_PGTABLE_PROT_W)))
+		return -EFAULT;
+
+	if (!realm_is_addr_protected(realm, ipa))
+		return realm_map_non_secure(realm, ipa, page, map_size,
+					    memcache);
+
+	return realm_map_protected(realm, ipa, page, map_size, memcache);
+}
+
+static int private_memslot_fault(struct kvm_vcpu *vcpu,
+				 phys_addr_t fault_ipa,
+				 struct kvm_memory_slot *memslot)
+{
+	struct kvm *kvm = vcpu->kvm;
+	gpa_t gpa_stolen_mask = kvm_gpa_stolen_bits(kvm);
+	gfn_t gfn = (fault_ipa & ~gpa_stolen_mask) >> PAGE_SHIFT;
+	bool is_priv_gfn = !((fault_ipa & gpa_stolen_mask) == gpa_stolen_mask);
+	bool priv_exists = kvm_mem_is_private(kvm, gfn);
+	struct kvm_mmu_memory_cache *memcache = &vcpu->arch.mmu_page_cache;
+	kvm_pfn_t pfn;
+	int ret;
+
+	if (priv_exists != is_priv_gfn) {
+		kvm_prepare_memory_fault_exit(vcpu,
+					      fault_ipa & ~gpa_stolen_mask,
+					      PAGE_SIZE,
+					      kvm_is_write_fault(vcpu),
+					      false, is_priv_gfn);
+
+		return 0;
+	}
+
+	if (!is_priv_gfn) {
+		/* Not a private mapping, handling normally */
+		return -EAGAIN;
+	}
+
+	ret = kvm_mmu_topup_memory_cache(memcache,
+					 kvm_mmu_cache_min_pages(vcpu->arch.hw_mmu));
+	if (ret)
+		return ret;
+
+	ret = kvm_gmem_get_pfn(kvm, memslot, gfn, &pfn, NULL);
+	if (ret)
+		return ret;
+
+	/* FIXME: Should be able to use bigger than PAGE_SIZE mappings */
+	ret = realm_map_ipa(kvm, fault_ipa, pfn, PAGE_SIZE, KVM_PGTABLE_PROT_W,
+			    memcache);
+	if (!ret)
+		return 1; /* Handled */
+
+	put_page(pfn_to_page(pfn));
+	return ret;
+}
+
 static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 			  struct kvm_memory_slot *memslot, unsigned long hva,
 			  bool fault_is_perm)
@@ -1402,10 +1481,19 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 	long vma_pagesize, fault_granule;
 	enum kvm_pgtable_prot prot = KVM_PGTABLE_PROT_R;
 	struct kvm_pgtable *pgt;
+	gpa_t gpa_stolen_mask = kvm_gpa_stolen_bits(vcpu->kvm);
 
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
 
@@ -1478,7 +1566,7 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 	if (vma_pagesize == PMD_SIZE || vma_pagesize == PUD_SIZE)
 		fault_ipa &= ~(vma_pagesize - 1);
 
-	gfn = fault_ipa >> PAGE_SHIFT;
+	gfn = (fault_ipa & ~gpa_stolen_mask) >> PAGE_SHIFT;
 	mte_allowed = kvm_vma_mte_allowed(vma);
 
 	vfio_allow_any_uc = vma->vm_flags & VM_ALLOW_ANY_UNCACHED;
@@ -1540,7 +1628,8 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 	 * If we are not forced to use page mapping, check if we are
 	 * backed by a THP and thus use block mapping if possible.
 	 */
-	if (vma_pagesize == PAGE_SIZE && !(force_pte || device)) {
+	/* FIXME: We shouldn't need to disable this for realms */
+	if (vma_pagesize == PAGE_SIZE && !(force_pte || device || kvm_is_realm(kvm))) {
 		if (fault_is_perm && fault_granule > PAGE_SIZE)
 			vma_pagesize = fault_granule;
 		else
@@ -1586,6 +1675,9 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 	 */
 	if (fault_is_perm && vma_pagesize == fault_granule)
 		ret = kvm_pgtable_stage2_relax_perms(pgt, fault_ipa, prot);
+	else if (kvm_is_realm(kvm))
+		ret = realm_map_ipa(kvm, fault_ipa, pfn, vma_pagesize,
+				    prot, memcache);
 	else
 		ret = kvm_pgtable_stage2_map(pgt, fault_ipa, vma_pagesize,
 					     __pfn_to_phys(pfn), prot,
@@ -1640,6 +1732,7 @@ int kvm_handle_guest_abort(struct kvm_vcpu *vcpu)
 	struct kvm_memory_slot *memslot;
 	unsigned long hva;
 	bool is_iabt, write_fault, writable;
+	gpa_t gpa_stolen_mask = kvm_gpa_stolen_bits(vcpu->kvm);
 	gfn_t gfn;
 	int ret, idx;
 
@@ -1695,8 +1788,15 @@ int kvm_handle_guest_abort(struct kvm_vcpu *vcpu)
 
 	idx = srcu_read_lock(&vcpu->kvm->srcu);
 
-	gfn = fault_ipa >> PAGE_SHIFT;
+	gfn = (fault_ipa & ~gpa_stolen_mask) >> PAGE_SHIFT;
 	memslot = gfn_to_memslot(vcpu->kvm, gfn);
+
+	if (kvm_slot_can_be_private(memslot)) {
+		ret = private_memslot_fault(vcpu, fault_ipa, memslot);
+		if (ret != -EAGAIN)
+			goto out;
+	}
+
 	hva = gfn_to_hva_memslot_prot(memslot, gfn, &writable);
 	write_fault = kvm_is_write_fault(vcpu);
 	if (kvm_is_error_hva(hva) || (write_fault && !writable)) {
@@ -1740,6 +1840,7 @@ int kvm_handle_guest_abort(struct kvm_vcpu *vcpu)
 		 * of the page size.
 		 */
 		fault_ipa |= kvm_vcpu_get_hfar(vcpu) & ((1 << 12) - 1);
+		fault_ipa &= ~gpa_stolen_mask;
 		ret = io_mem_abort(vcpu, fault_ipa);
 		goto out_unlock;
 	}
@@ -1787,6 +1888,10 @@ bool kvm_age_gfn(struct kvm *kvm, struct kvm_gfn_range *range)
 	if (!kvm->arch.mmu.pgt)
 		return false;
 
+	/* We don't support aging for Realms */
+	if (kvm_is_realm(kvm))
+		return true;
+
 	return kvm_pgtable_stage2_test_clear_young(kvm->arch.mmu.pgt,
 						   range->start << PAGE_SHIFT,
 						   size, true);
@@ -1799,6 +1904,10 @@ bool kvm_test_age_gfn(struct kvm *kvm, struct kvm_gfn_range *range)
 	if (!kvm->arch.mmu.pgt)
 		return false;
 
+	/* We don't support aging for Realms */
+	if (kvm_is_realm(kvm))
+		return true;
+
 	return kvm_pgtable_stage2_test_clear_young(kvm->arch.mmu.pgt,
 						   range->start << PAGE_SHIFT,
 						   size, false);
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 2c4e28b457be..337b3dd1e00c 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -627,6 +627,181 @@ static int fold_rtt(struct realm *realm, unsigned long addr, int level)
 	return 0;
 }
 
+static phys_addr_t rtt_get_phys(struct realm *realm, struct rtt_entry *rtt)
+{
+	bool lpa2 = realm->params->flags & RMI_REALM_PARAM_FLAG_LPA2;
+
+	if (lpa2)
+		return rtt->desc & GENMASK(49, 12);
+	return rtt->desc & GENMASK(47, 12);
+}
+
+int realm_map_protected(struct realm *realm,
+			unsigned long base_ipa,
+			struct page *dst_page,
+			unsigned long map_size,
+			struct kvm_mmu_memory_cache *memcache)
+{
+	phys_addr_t dst_phys = page_to_phys(dst_page);
+	phys_addr_t rd = virt_to_phys(realm->rd);
+	unsigned long phys = dst_phys;
+	unsigned long ipa = base_ipa;
+	unsigned long size;
+	int map_level;
+	int ret = 0;
+
+	if (WARN_ON(!IS_ALIGNED(ipa, map_size)))
+		return -EINVAL;
+
+	switch (map_size) {
+	case PAGE_SIZE:
+		map_level = 3;
+		break;
+	case RME_L2_BLOCK_SIZE:
+		map_level = 2;
+		break;
+	default:
+		return -EINVAL;
+	}
+
+	if (map_level < RME_RTT_MAX_LEVEL) {
+		/*
+		 * A temporary RTT is needed during the map, precreate it,
+		 * however if there is an error (e.g. missing parent tables)
+		 * this will be handled below.
+		 */
+		realm_create_rtt_levels(realm, ipa, map_level,
+					RME_RTT_MAX_LEVEL, memcache);
+	}
+
+	for (size = 0; size < map_size; size += PAGE_SIZE) {
+		if (rmi_granule_delegate(phys)) {
+			struct rtt_entry rtt;
+
+			/*
+			 * It's possible we raced with another VCPU on the same
+			 * fault. If the entry exists and matches then exit
+			 * early and assume the other VCPU will handle the
+			 * mapping.
+			 */
+			if (rmi_rtt_read_entry(rd, ipa, RME_RTT_MAX_LEVEL, &rtt))
+				goto err;
+
+			/*
+			 * FIXME: For a block mapping this could race at level
+			 * 2 or 3... currently we don't support block mappings
+			 */
+			if (WARN_ON((rtt.walk_level != RME_RTT_MAX_LEVEL ||
+				     rtt.state != RMI_ASSIGNED ||
+				     rtt_get_phys(realm, &rtt) != phys))) {
+				goto err;
+			}
+
+			return 0;
+		}
+
+		ret = rmi_data_create_unknown(rd, phys, ipa);
+
+		if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
+			/* Create missing RTTs and retry */
+			int level = RMI_RETURN_INDEX(ret);
+
+			ret = realm_create_rtt_levels(realm, ipa, level,
+						      RME_RTT_MAX_LEVEL,
+						      memcache);
+			WARN_ON(ret);
+			if (ret)
+				goto err_undelegate;
+
+			ret = rmi_data_create_unknown(rd, phys, ipa);
+		}
+		WARN_ON(ret);
+
+		if (ret)
+			goto err_undelegate;
+
+		phys += PAGE_SIZE;
+		ipa += PAGE_SIZE;
+	}
+
+	if (map_size == RME_L2_BLOCK_SIZE)
+		ret = fold_rtt(realm, base_ipa, map_level);
+	if (WARN_ON(ret))
+		goto err;
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
+		phys -= PAGE_SIZE;
+		size -= PAGE_SIZE;
+		ipa -= PAGE_SIZE;
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
+			 struct page *page,
+			 unsigned long map_size,
+			 struct kvm_mmu_memory_cache *memcache)
+{
+	phys_addr_t rd = virt_to_phys(realm->rd);
+	int map_level;
+	int ret = 0;
+	unsigned long desc = page_to_phys(page) |
+			     PTE_S2_MEMATTR(MT_S2_FWB_NORMAL) |
+			     /* FIXME: Read+Write permissions for now */
+			     (3 << 6) |
+			     PTE_SHARED;
+
+	if (WARN_ON(!IS_ALIGNED(ipa, map_size)))
+		return -EINVAL;
+
+	switch (map_size) {
+	case PAGE_SIZE:
+		map_level = 3;
+		break;
+	case RME_L2_BLOCK_SIZE:
+		map_level = 2;
+		break;
+	default:
+		return -EINVAL;
+	}
+
+	ret = rmi_rtt_map_unprotected(rd, ipa, map_level, desc);
+
+	if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
+		/* Create missing RTTs and retry */
+		int level = RMI_RETURN_INDEX(ret);
+
+		ret = realm_create_rtt_levels(realm, ipa, level, map_level,
+					      memcache);
+		if (WARN_ON(ret))
+			return -ENXIO;
+
+		ret = rmi_rtt_map_unprotected(rd, ipa, map_level, desc);
+	}
+	if (WARN_ON(ret))
+		return -ENXIO;
+
+	return 0;
+}
+
 static int populate_par_region(struct kvm *kvm,
 			       phys_addr_t ipa_base,
 			       phys_addr_t ipa_end,
@@ -638,7 +813,6 @@ static int populate_par_region(struct kvm *kvm,
 	int idx;
 	phys_addr_t ipa;
 	int ret = 0;
-	struct page *tmp_page;
 	unsigned long data_flags = 0;
 
 	base_gfn = gpa_to_gfn(ipa_base);
@@ -660,9 +834,8 @@ static int populate_par_region(struct kvm *kvm,
 		goto out;
 	}
 
-	tmp_page = alloc_page(GFP_KERNEL);
-	if (!tmp_page) {
-		ret = -ENOMEM;
+	if (!kvm_slot_can_be_private(memslot)) {
+		ret = -EINVAL;
 		goto out;
 	}
 
@@ -729,28 +902,32 @@ static int populate_par_region(struct kvm *kvm,
 		for (offset = 0; offset < map_size && !ret;
 		     offset += PAGE_SIZE, page++) {
 			phys_addr_t page_ipa = ipa + offset;
+			kvm_pfn_t priv_pfn;
+			int order;
+
+			ret = kvm_gmem_get_pfn(kvm, memslot,
+					       page_ipa >> PAGE_SHIFT,
+					       &priv_pfn, &order);
+			if (ret)
+				break;
 
 			ret = realm_create_protected_data_page(realm, page_ipa,
-							       page, tmp_page,
-							       data_flags);
+							       pfn_to_page(priv_pfn),
+							       page, data_flags);
 		}
+
+		kvm_release_pfn_clean(pfn);
+
 		if (ret)
-			goto err_release_pfn;
+			break;
 
 		if (level == 2)
 			fold_rtt(realm, ipa, level);
 
 		ipa += map_size;
-		kvm_release_pfn_dirty(pfn);
-err_release_pfn:
-		if (ret) {
-			kvm_release_pfn_clean(pfn);
-			break;
-		}
 	}
 
 	mmap_read_unlock(current->mm);
-	__free_page(tmp_page);
 
 out:
 	srcu_read_unlock(&kvm->srcu, idx);

---

## [23] Steven Price — 2024-06-10
*Subject: [PATCH v3 22/43] KVM: arm64: Handle realm VCPU load*

When loading a realm VCPU much of the work is handled by the RMM so only
some of the actions are required. Rearrange kvm_arch_vcpu_load()
slightly so we can bail out early for a realm guest.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/kvm/arm.c | 13 +++++++++----
 1 file changed, 9 insertions(+), 4 deletions(-)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 0b51ea30d679..aa57aa8cab4e 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -630,10 +630,6 @@ void kvm_arch_vcpu_load(struct kvm_vcpu *vcpu, int cpu)
 
 	kvm_vgic_load(vcpu);
 	kvm_timer_vcpu_load(vcpu);
-	if (has_vhe())
-		kvm_vcpu_load_vhe(vcpu);
-	kvm_arch_vcpu_load_fp(vcpu);
-	kvm_vcpu_pmu_restore_guest(vcpu);
 	if (kvm_arm_is_pvtime_enabled(&vcpu->arch))
 		kvm_make_request(KVM_REQ_RECORD_STEAL, vcpu);
 
@@ -644,6 +640,15 @@ void kvm_arch_vcpu_load(struct kvm_vcpu *vcpu, int cpu)
 
 	vcpu_set_pauth_traps(vcpu);
 
+	/* No additional state needs to be loaded on Realmed VMs */
+	if (vcpu_is_rec(vcpu))
+		return;
+
+	if (has_vhe())
+		kvm_vcpu_load_vhe(vcpu);
+	kvm_arch_vcpu_load_fp(vcpu);
+	kvm_vcpu_pmu_restore_guest(vcpu);
+
 	kvm_arch_vcpu_load_debug_state_flags(vcpu);
 
 	if (!cpumask_test_cpu(cpu, vcpu->kvm->arch.supported_cpus))

---

## [24] Steven Price — 2024-06-10
*Subject: [PATCH v3 23/43] KVM: arm64: Validate register access for a Realm VM*

The RMM only allows setting the lower GPRS (x0-x7) and PC for a realm
guest. Check this in kvm_arm_set_reg() so that the VMM can receive a
suitable error return if other registers are accessed.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/kvm/guest.c | 26 ++++++++++++++++++++++++++
 1 file changed, 26 insertions(+)

diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index e2f762d959bb..a035689dc39b 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -782,12 +782,38 @@ int kvm_arm_get_reg(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg)
 	return kvm_arm_sys_reg_get_reg(vcpu, reg);
 }
 
+/*
+ * The RMI ABI only enables setting the lower GPRs (x0-x7) and PC.
+ * All other registers are reset to architectural or otherwise defined reset
+ * values by the RMM, except for a few configuration fields that correspond to
+ * Realm parameters.
+ */
+static bool validate_realm_set_reg(struct kvm_vcpu *vcpu,
+				   const struct kvm_one_reg *reg)
+{
+	if ((reg->id & KVM_REG_ARM_COPROC_MASK) == KVM_REG_ARM_CORE) {
+		u64 off = core_reg_offset_from_id(reg->id);
+
+		switch (off) {
+		case KVM_REG_ARM_CORE_REG(regs.regs[0]) ...
+		     KVM_REG_ARM_CORE_REG(regs.regs[7]):
+		case KVM_REG_ARM_CORE_REG(regs.pc):
+			return true;
+		}
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

## [25] Steven Price — 2024-06-10
*Subject: [PATCH v3 24/43] KVM: arm64: Handle Realm PSCI requests*

The RMM needs to be informed of the target REC when a PSCI call is made
with an MPIDR argument. Expose an ioctl to the userspace in case the PSCI
is handled by it.

Co-developed-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/include/asm/kvm_rme.h |  3 +++
 arch/arm64/kvm/arm.c             | 25 +++++++++++++++++++++++++
 arch/arm64/kvm/psci.c            | 29 +++++++++++++++++++++++++++++
 arch/arm64/kvm/rme.c             | 15 +++++++++++++++
 4 files changed, 72 insertions(+)

diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index c50854f44674..5492e60aa8de 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -117,6 +117,9 @@ int realm_set_ipa_state(struct kvm_vcpu *vcpu,
 			unsigned long addr, unsigned long end,
 			unsigned long ripas,
 			unsigned long *top_ipa);
+int realm_psci_complete(struct kvm_vcpu *calling,
+			struct kvm_vcpu *target,
+			unsigned long status);
 
 #define RME_RTT_BLOCK_LEVEL	2
 #define RME_RTT_MAX_LEVEL	3
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index aa57aa8cab4e..77ea231cfb04 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -1718,6 +1718,22 @@ static int kvm_arm_vcpu_set_events(struct kvm_vcpu *vcpu,
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
@@ -1840,6 +1856,15 @@ long kvm_arch_vcpu_ioctl(struct file *filp,
 
 		return kvm_arm_vcpu_finalize(vcpu, what);
 	}
+	case KVM_ARM_VCPU_RMM_PSCI_COMPLETE: {
+		struct kvm_arm_rmm_psci_complete req;
+
+		if (!kvm_is_realm(vcpu->kvm))
+			return -EINVAL;
+		if (copy_from_user(&req, argp, sizeof(req)))
+			return -EFAULT;
+		return kvm_arm_vcpu_rmm_psci_complete(vcpu, &req);
+	}
 	default:
 		r = -EINVAL;
 	}
diff --git a/arch/arm64/kvm/psci.c b/arch/arm64/kvm/psci.c
index 1f69b667332b..f9abab5d50d7 100644
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
@@ -115,6 +121,10 @@ static unsigned long kvm_psci_vcpu_on(struct kvm_vcpu *source_vcpu)
 
 out_unlock:
 	spin_unlock(&vcpu->arch.mp_state_lock);
+	if (vcpu_is_rec(vcpu) && ret != PSCI_RET_SUCCESS)
+		realm_psci_complete(source_vcpu, vcpu,
+				    ret == PSCI_RET_ALREADY_ON ?
+				    PSCI_RET_SUCCESS : PSCI_RET_DENIED);
 	return ret;
 }
 
@@ -142,6 +152,25 @@ static unsigned long kvm_psci_vcpu_affinity_info(struct kvm_vcpu *vcpu)
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
+		 * Provide the references of running and target RECs to the RMM
+		 * so that the RMM can complete the PSCI request.
+		 */
+		realm_psci_complete(vcpu, target_vcpu, PSCI_RET_SUCCESS);
+		return PSCI_RET_SUCCESS;
+	}
+
 	/*
 	 * If one or more VCPU matching target affinity are running
 	 * then ON else OFF
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 337b3dd1e00c..45d49d12a34c 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -95,6 +95,21 @@ static void free_delegated_page(struct realm *realm, phys_addr_t phys)
 	free_page((unsigned long)phys_to_virt(phys));
 }
 
+int realm_psci_complete(struct kvm_vcpu *calling, struct kvm_vcpu *target,
+			unsigned long status)
+{
+	int ret;
+
+	ret = rmi_psci_complete(virt_to_phys(calling->arch.rec.rec_page),
+				virt_to_phys(target->arch.rec.rec_page),
+				status);
+
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

## [26] Steven Price — 2024-06-10
*Subject: [PATCH v3 25/43] KVM: arm64: WARN on injected undef exceptions*

The RMM doesn't allow injection of a undefined exception into a realm
guest. Add a WARN to catch if this ever happens.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/kvm/inject_fault.c | 2 ++
 1 file changed, 2 insertions(+)

diff --git a/arch/arm64/kvm/inject_fault.c b/arch/arm64/kvm/inject_fault.c
index a640e839848e..44ce1c9bdc2e 100644
--- a/arch/arm64/kvm/inject_fault.c
+++ b/arch/arm64/kvm/inject_fault.c
@@ -224,6 +224,8 @@ void kvm_inject_size_fault(struct kvm_vcpu *vcpu)
  */
 void kvm_inject_undefined(struct kvm_vcpu *vcpu)
 {
+	if (vcpu_is_rec(vcpu))
+		WARN(1, "Cannot inject undefined exception into REC. Continuing with unknown behaviour");
 	if (vcpu_el1_is_32bit(vcpu))
 		inject_undef32(vcpu);
 	else

---

## [27] Steven Price — 2024-06-10
*Subject: [PATCH v3 26/43] arm64: Don't expose stolen time for realm guests*

It doesn't make much sense and with the ABI as it is it's a footgun for
the VMM which makes fatal granule protection faults easy to trigger.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/kvm/arm.c | 5 ++++-
 1 file changed, 4 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index 77ea231cfb04..f78e92dfaa72 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -418,7 +418,10 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 		r = system_supports_mte();
 		break;
 	case KVM_CAP_STEAL_TIME:
-		r = kvm_arm_pvtime_supported();
+		if (kvm && kvm_is_realm(kvm))
+			r = 0;
+		else
+			r = kvm_arm_pvtime_supported();
 		break;
 	case KVM_CAP_ARM_EL1_32BIT:
 		r = cpus_have_final_cap(ARM64_HAS_32BIT_EL1);

---

## [28] Steven Price — 2024-06-10
*Subject: [PATCH v3 27/43] arm64: rme: allow userspace to inject aborts*

From: Joey Gouly <joey.gouly@arm.com>

Extend KVM_SET_VCPU_EVENTS to support realms, where KVM cannot set the
system registers, and the RMM must perform it on next REC entry.

Signed-off-by: Joey Gouly <joey.gouly@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 Documentation/virt/kvm/api.rst |  2 ++
 arch/arm64/kvm/guest.c         | 24 ++++++++++++++++++++++++
 2 files changed, 26 insertions(+)

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index dd53beb8fe14..310e151a2382 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -1278,6 +1278,8 @@ User space may need to inject several types of events to the guest.
 Set the pending SError exception state for this VCPU. It is not possible to
 'cancel' an Serror that has been made pending.
 
+User space cannot inject SErrors into Realms.
+
 If the guest performed an access to I/O memory which could not be handled by
 userspace, for example because of missing instruction syndrome decode
 information or because there is no device mapped at the accessed IPA, then
diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index a035689dc39b..b01d900c89ff 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -865,6 +865,30 @@ int __kvm_arm_vcpu_set_events(struct kvm_vcpu *vcpu,
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
+			if (!(vcpu->arch.rec.run->enter.flags & RMI_EMULATED_MMIO))
+				return -EINVAL;
+
+			vcpu->arch.rec.run->enter.flags &= ~RMI_EMULATED_MMIO;
+			vcpu->arch.rec.run->enter.flags |= RMI_INJECT_SEA;
+		}
+
+		return 0;
+	}
+
 	if (serror_pending && has_esr) {
 		if (!cpus_have_final_cap(ARM64_HAS_RAS_EXTN))
 			return -EINVAL;

---

## [29] Steven Price — 2024-06-10
*Subject: [PATCH v3 28/43] arm64: rme: support RSI_HOST_CALL*

From: Joey Gouly <joey.gouly@arm.com>

Forward RSI_HOST_CALLS to KVM's HVC handler.

Signed-off-by: Joey Gouly <joey.gouly@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/kvm/rme-exit.c | 25 +++++++++++++++++++++++++
 1 file changed, 25 insertions(+)

diff --git a/arch/arm64/kvm/rme-exit.c b/arch/arm64/kvm/rme-exit.c
index 03ed147f7926..0940575b0a14 100644
--- a/arch/arm64/kvm/rme-exit.c
+++ b/arch/arm64/kvm/rme-exit.c
@@ -117,6 +117,29 @@ static int rec_exit_ripas_change(struct kvm_vcpu *vcpu)
 	return 0;
 }
 
+static int rec_exit_host_call(struct kvm_vcpu *vcpu)
+{
+	int ret, i;
+	struct realm_rec *rec = &vcpu->arch.rec;
+
+	vcpu->stat.hvc_exit_stat++;
+
+	for (i = 0; i < REC_RUN_GPRS; i++)
+		vcpu_set_reg(vcpu, i, rec->run->exit.gprs[i]);
+
+	ret = kvm_smccc_call_handler(vcpu);
+
+	if (ret < 0) {
+		vcpu_set_reg(vcpu, 0, ~0UL);
+		ret = 1;
+	}
+
+	for (i = 0; i < REC_RUN_GPRS; i++)
+		rec->run->enter.gprs[i] = vcpu_get_reg(vcpu, i);
+
+	return ret;
+}
+
 static void update_arch_timer_irq_lines(struct kvm_vcpu *vcpu)
 {
 	struct realm_rec *rec = &vcpu->arch.rec;
@@ -178,6 +201,8 @@ int handle_rme_exit(struct kvm_vcpu *vcpu, int rec_run_ret)
 		return rec_exit_psci(vcpu);
 	case RMI_EXIT_RIPAS_CHANGE:
 		return rec_exit_ripas_change(vcpu);
+	case RMI_EXIT_HOST_CALL:
+		return rec_exit_host_call(vcpu);
 	}
 
 	kvm_pr_unimpl("Unsupported exit reason: %u\n",

---

## [30] Steven Price — 2024-06-10
*Subject: [PATCH v3 29/43] arm64: rme: Allow checking SVE on VM instance*

From: Suzuki K Poulose <suzuki.poulose@arm.com>

Given we have different types of VMs supported, check the
support for SVE for the given instance of the VM to accurately
report the status.

Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/include/asm/kvm_rme.h | 2 ++
 arch/arm64/kvm/arm.c             | 5 ++++-
 arch/arm64/kvm/rme.c             | 5 +++++
 3 files changed, 11 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index 5492e60aa8de..80c7db964079 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -89,6 +89,8 @@ struct realm_rec {
 void kvm_init_rme(void);
 u32 kvm_realm_ipa_limit(void);
 
+bool kvm_rme_supports_sve(void);
+
 int kvm_realm_enable_cap(struct kvm *kvm, struct kvm_enable_cap *cap);
 int kvm_init_realm_vm(struct kvm *kvm);
 void kvm_destroy_realm(struct kvm *kvm);
diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index f78e92dfaa72..f3743ba8b006 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -442,7 +442,10 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 		r = get_kvm_ipa_limit();
 		break;
 	case KVM_CAP_ARM_SVE:
-		r = system_supports_sve();
+		if (kvm && kvm_is_realm(kvm))
+			r = kvm_rme_supports_sve();
+		else
+			r = system_supports_sve();
 		break;
 	case KVM_CAP_ARM_PTRAUTH_ADDRESS:
 	case KVM_CAP_ARM_PTRAUTH_GENERIC:
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 45d49d12a34c..999bd4bf2d73 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -20,6 +20,11 @@ static bool rme_supports(unsigned long feature)
 	return !!u64_get_bits(rmm_feat_reg0, feature);
 }
 
+bool kvm_rme_supports_sve(void)
+{
+	return rme_supports(RMI_FEATURE_REGISTER_0_SVE_EN);
+}
+
 static int rmi_check_version(void)
 {
 	struct arm_smccc_res res;

---

## [31] Steven Price — 2024-06-10
*Subject: [PATCH v3 30/43] arm64: RME: Always use 4k pages for realms*

Always split up huge pages to avoid problems managing huge pages. There
are two issues currently:

1. The uABI for the VMM allows populating memory on 4k boundaries even
   if the underlying allocator (e.g. hugetlbfs) is using a larger page
   size. Using a memfd for private allocations will push this issue onto
   the VMM as it will need to respect the granularity of the allocator.

2. The guest is able to request arbitrary ranges to be remapped as
   shared. Again with a memfd approach it will be up to the VMM to deal
   with the complexity and either overmap (need the huge mapping and add
   an additional 'overlapping' shared mapping) or reject the request as
   invalid due to the use of a huge page allocator.

For now just break everything down to 4k pages in the RMM controlled
stage 2.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/kvm/mmu.c | 4 ++++
 1 file changed, 4 insertions(+)

diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index 5eb5af0ff5d7..cdbd5a29539a 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -1534,6 +1534,10 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 	if (logging_active) {
 		force_pte = true;
 		vma_shift = PAGE_SHIFT;
+	} else if (kvm_is_realm(kvm)) {
+		// Force PTE level mappings for realms
+		force_pte = true;
+		vma_shift = PAGE_SHIFT;
 	} else {
 		vma_shift = get_vma_page_shift(vma, hva);
 	}

---

## [32] Steven Price — 2024-06-10
*Subject: [PATCH v3 31/43] arm64: rme: Prevent Device mappings for Realms*

Physical device assignment is not yet supported by the RMM, so it
doesn't make much sense to allow device mappings within the realm.
Prevent them when the guest is a realm.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/kvm/mmu.c | 4 ++++
 1 file changed, 4 insertions(+)

diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index cdbd5a29539a..b3793c2b8499 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -1101,6 +1101,10 @@ int kvm_phys_addr_ioremap(struct kvm *kvm, phys_addr_t guest_ipa,
 	if (is_protected_kvm_enabled())
 		return -EPERM;
 
+	/* We don't support mapping special pages into a Realm */
+	if (kvm_is_realm(kvm))
+		return -EINVAL;
+
 	size += offset_in_page(guest_ipa);
 	guest_ipa &= PAGE_MASK;

---

## [33] Steven Price — 2024-06-10
*Subject: [PATCH v3 32/43] arm_pmu: Provide a mechanism for disabling the physical IRQ*

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
index 8458fe2cebb4..1e024acc98bb 100644
--- a/drivers/perf/arm_pmu.c
+++ b/drivers/perf/arm_pmu.c
@@ -735,6 +735,21 @@ static int arm_perf_teardown_cpu(unsigned int cpu, struct hlist_node *node)
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
index b3b34f6670cf..f9fa628ae2ae 100644
--- a/include/linux/perf/arm_pmu.h
+++ b/include/linux/perf/arm_pmu.h
@@ -168,6 +168,7 @@ void kvm_host_pmu_init(struct arm_pmu *pmu);
 #endif
 
 bool arm_pmu_irq_is_nmi(void);
+void arm_pmu_set_phys_irq(bool enable);
 
 /* Internal functions only for core arm_pmu code */
 struct arm_pmu *armpmu_alloc(void);
@@ -178,6 +179,10 @@ void armpmu_free_irq(int irq, int cpu);
 
 #define ARMV8_PMU_PDEV_NAME "armv8-pmu"
 
+#else /* CONFIG_ARM_PMU */
+
+static inline void arm_pmu_set_phys_irq(bool enable) {}
+
 #endif /* CONFIG_ARM_PMU */
 
 #define ARMV8_SPE_PDEV_NAME "arm,spe-v1"

---

## [34] Steven Price — 2024-06-10
*Subject: [PATCH v3 33/43] arm64: rme: Enable PMU support with a realm guest*

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
 arch/arm64/kvm/pmu-emul.c |  4 +++-
 arch/arm64/kvm/rme.c      |  8 ++++++++
 arch/arm64/kvm/sys_regs.c |  2 +-
 include/kvm/arm_pmu.h     |  4 ++++
 6 files changed, 34 insertions(+), 2 deletions(-)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index f3743ba8b006..e642484e3611 100644
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
@@ -1188,6 +1189,8 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 	run->exit_reason = KVM_EXIT_UNKNOWN;
 	run->flags = 0;
 	while (ret > 0) {
+		bool pmu_stopped = false;
+
 		/*
 		 * Check conditions before entering the guest
 		 */
@@ -1219,6 +1222,11 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 
 		kvm_pmu_flush_hwstate(vcpu);
 
+		if (vcpu_is_rec(vcpu) && kvm_pmu_get_irq_level(vcpu)) {
+			pmu_stopped = true;
+			arm_pmu_set_phys_irq(false);
+		}
+
 		local_irq_disable();
 
 		kvm_vgic_flush_hwstate(vcpu);
@@ -1321,6 +1329,9 @@ int kvm_arch_vcpu_ioctl_run(struct kvm_vcpu *vcpu)
 
 		preempt_enable();
 
+		if (pmu_stopped)
+			arm_pmu_set_phys_irq(true);
+
 		/*
 		 * The ARMv8 architecture doesn't give the hypervisor
 		 * a mechanism to prevent a guest from dropping to AArch32 EL0
diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index b01d900c89ff..e17679c347ae 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -782,6 +782,8 @@ int kvm_arm_get_reg(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg)
 	return kvm_arm_sys_reg_get_reg(vcpu, reg);
 }
 
+#define KVM_REG_ARM_PMCR_EL0		ARM64_SYS_REG(3, 3, 9, 12, 0)
+
 /*
  * The RMI ABI only enables setting the lower GPRs (x0-x7) and PC.
  * All other registers are reset to architectural or otherwise defined reset
@@ -800,6 +802,11 @@ static bool validate_realm_set_reg(struct kvm_vcpu *vcpu,
 		case KVM_REG_ARM_CORE_REG(regs.pc):
 			return true;
 		}
+	} else {
+		switch (reg->id) {
+		case KVM_REG_ARM_PMCR_EL0:
+			return true;
+		}
 	}
 
 	return false;
diff --git a/arch/arm64/kvm/pmu-emul.c b/arch/arm64/kvm/pmu-emul.c
index a35ce10e0a9f..ce7c8e55d904 100644
--- a/arch/arm64/kvm/pmu-emul.c
+++ b/arch/arm64/kvm/pmu-emul.c
@@ -341,7 +341,9 @@ static u64 kvm_pmu_overflow_status(struct kvm_vcpu *vcpu)
 {
 	u64 reg = 0;
 
-	if ((kvm_vcpu_read_pmcr(vcpu) & ARMV8_PMU_PMCR_E)) {
+	if (vcpu_is_rec(vcpu)) {
+		reg = vcpu->arch.rec.run->exit.pmu_ovf_status;
+	} else if ((kvm_vcpu_read_pmcr(vcpu) & ARMV8_PMU_PMCR_E)) {
 		reg = __vcpu_sys_reg(vcpu, PMOVSSET_EL0);
 		reg &= __vcpu_sys_reg(vcpu, PMCNTENSET_EL0);
 		reg &= __vcpu_sys_reg(vcpu, PMINTENSET_EL1);
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 999bd4bf2d73..93757c550394 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -325,6 +325,11 @@ static int realm_create_rd(struct kvm *kvm)
 	params->rtt_base = kvm->arch.mmu.pgd_phys;
 	params->vmid = realm->vmid;
 
+	if (kvm->arch.arm_pmu) {
+		params->pmu_num_ctrs = kvm->arch.pmcr_n;
+		params->flags |= RMI_REALM_PARAM_FLAG_PMU;
+	}
+
 	params_phys = virt_to_phys(params);
 
 	if (rmi_realm_create(rd_phys, params_phys)) {
@@ -1398,6 +1403,9 @@ int kvm_create_rec(struct kvm_vcpu *vcpu)
 	if (!vcpu_has_feature(vcpu, KVM_ARM_VCPU_PSCI_0_2))
 		return -EINVAL;
 
+	if (vcpu->kvm->arch.arm_pmu && !kvm_vcpu_has_pmu(vcpu))
+		return -EINVAL;
+
 	BUILD_BUG_ON(sizeof(*params) > PAGE_SIZE);
 	BUILD_BUG_ON(sizeof(*rec->run) > PAGE_SIZE);
 
diff --git a/arch/arm64/kvm/sys_regs.c b/arch/arm64/kvm/sys_regs.c
index 22b45a15d068..435bcd02ddfd 100644
--- a/arch/arm64/kvm/sys_regs.c
+++ b/arch/arm64/kvm/sys_regs.c
@@ -1279,7 +1279,7 @@ static int set_pmcr(struct kvm_vcpu *vcpu, const struct sys_reg_desc *r,
 	 * implements. Ignore this error to maintain compatibility
 	 * with the existing KVM behavior.
 	 */
-	if (!kvm_vm_has_ran_once(kvm) &&
+	if (!kvm_vm_has_ran_once(kvm) && !kvm_realm_is_created(kvm) &&
 	    new_n <= kvm_arm_pmu_get_max_counters(kvm))
 		kvm->arch.pmcr_n = new_n;
 
diff --git a/include/kvm/arm_pmu.h b/include/kvm/arm_pmu.h
index 35d4ca4f6122..e2d31640e2e7 100644
--- a/include/kvm/arm_pmu.h
+++ b/include/kvm/arm_pmu.h
@@ -76,6 +76,8 @@ void kvm_vcpu_pmu_restore_guest(struct kvm_vcpu *vcpu);
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

## [35] Steven Price — 2024-06-10
*Subject: [PATCH v3 34/43] kvm: rme: Hide KVM_CAP_READONLY_MEM for realm guests*

For protected memory read only isn't supported. While it may be possible
to support read only for unprotected memory, this isn't supported at the
present time.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/kvm/arm.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/arch/arm64/kvm/arm.c b/arch/arm64/kvm/arm.c
index e642484e3611..b04f08e242a6 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -363,7 +363,6 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 	case KVM_CAP_ONE_REG:
 	case KVM_CAP_ARM_PSCI:
 	case KVM_CAP_ARM_PSCI_0_2:
-	case KVM_CAP_READONLY_MEM:
 	case KVM_CAP_MP_STATE:
 	case KVM_CAP_IMMEDIATE_EXIT:
 	case KVM_CAP_VCPU_EVENTS:
@@ -377,6 +376,7 @@ int kvm_vm_ioctl_check_extension(struct kvm *kvm, long ext)
 	case KVM_CAP_COUNTER_OFFSET:
 		r = 1;
 		break;
+	case KVM_CAP_READONLY_MEM:
 	case KVM_CAP_SET_GUEST_DEBUG:
 		r = !kvm_is_realm(kvm);
 		break;

---

## [36] Steven Price — 2024-06-10
*Subject: [PATCH v3 35/43] arm64: RME: Propagate number of breakpoints and watchpoints to userspace*

From: Jean-Philippe Brucker <jean-philippe@linaro.org>

The RMM describes the maximum number of BPs/WPs available to the guest
in the Feature Register 0. Propagate those numbers into ID_AA64DFR0_EL1,
which is visible to userspace. A VMM needs this information in order to
set up realm parameters.

Signed-off-by: Jean-Philippe Brucker <jean-philippe@linaro.org>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/include/asm/kvm_rme.h |  1 +
 arch/arm64/kvm/rme.c             | 22 ++++++++++++++++++++++
 arch/arm64/kvm/sys_regs.c        |  2 +-
 3 files changed, 24 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index 80c7db964079..8aa02134c461 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -88,6 +88,7 @@ struct realm_rec {
 
 void kvm_init_rme(void);
 u32 kvm_realm_ipa_limit(void);
+u64 kvm_realm_reset_id_aa64dfr0_el1(struct kvm_vcpu *vcpu, u64 val);
 
 bool kvm_rme_supports_sve(void);
 
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 93757c550394..66e124b4d25a 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -286,6 +286,28 @@ u32 kvm_realm_ipa_limit(void)
 	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_S2SZ);
 }
 
+u64 kvm_realm_reset_id_aa64dfr0_el1(struct kvm_vcpu *vcpu, u64 val)
+{
+	u32 bps = u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_NUM_BPS);
+	u32 wps = u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_NUM_WPS);
+	u32 ctx_cmps;
+
+	if (!kvm_is_realm(vcpu->kvm))
+		return val;
+
+	/* Ensure CTX_CMPs is still valid */
+	ctx_cmps = FIELD_GET(ID_AA64DFR0_EL1_CTX_CMPs, val) + 1;
+	ctx_cmps = min(bps, ctx_cmps);
+
+	val &= ~(ID_AA64DFR0_EL1_BRPs_MASK | ID_AA64DFR0_EL1_WRPs_MASK |
+		 ID_AA64DFR0_EL1_CTX_CMPs);
+	val |= FIELD_PREP(ID_AA64DFR0_EL1_BRPs_MASK, bps - 1) |
+	       FIELD_PREP(ID_AA64DFR0_EL1_WRPs_MASK, wps - 1) |
+	       FIELD_PREP(ID_AA64DFR0_EL1_CTX_CMPs, ctx_cmps - 1);
+
+	return val;
+}
+
 static int realm_create_rd(struct kvm *kvm)
 {
 	struct realm *realm = &kvm->arch.realm;
diff --git a/arch/arm64/kvm/sys_regs.c b/arch/arm64/kvm/sys_regs.c
index 435bcd02ddfd..96d73b1867ad 100644
--- a/arch/arm64/kvm/sys_regs.c
+++ b/arch/arm64/kvm/sys_regs.c
@@ -1722,7 +1722,7 @@ static u64 read_sanitised_id_aa64dfr0_el1(struct kvm_vcpu *vcpu,
 	/* Hide SPE from guests */
 	val &= ~ID_AA64DFR0_EL1_PMSVer_MASK;
 
-	return val;
+	return kvm_realm_reset_id_aa64dfr0_el1(vcpu, val);
 }
 
 static int set_id_aa64dfr0_el1(struct kvm_vcpu *vcpu,

---

## [37] Steven Price — 2024-06-10
*Subject: [PATCH v3 36/43] arm64: RME: Set breakpoint parameters through SET_ONE_REG*

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
---
 arch/arm64/kvm/guest.c    |  2 ++
 arch/arm64/kvm/rme.c      |  3 +++
 arch/arm64/kvm/sys_regs.c | 21 ++++++++++++++-------
 3 files changed, 19 insertions(+), 7 deletions(-)

diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index e17679c347ae..ad77e1343269 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -783,6 +783,7 @@ int kvm_arm_get_reg(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg)
 }
 
 #define KVM_REG_ARM_PMCR_EL0		ARM64_SYS_REG(3, 3, 9, 12, 0)
+#define KVM_REG_ARM_ID_AA64DFR0_EL1	ARM64_SYS_REG(3, 0, 0, 5, 0)
 
 /*
  * The RMI ABI only enables setting the lower GPRs (x0-x7) and PC.
@@ -805,6 +806,7 @@ static bool validate_realm_set_reg(struct kvm_vcpu *vcpu,
 	} else {
 		switch (reg->id) {
 		case KVM_REG_ARM_PMCR_EL0:
+		case KVM_REG_ARM_ID_AA64DFR0_EL1:
 			return true;
 		}
 	}
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 66e124b4d25a..31e00c52551d 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -315,6 +315,7 @@ static int realm_create_rd(struct kvm *kvm)
 	void *rd = NULL;
 	phys_addr_t rd_phys, params_phys;
 	struct kvm_pgtable *pgt = kvm->arch.mmu.pgt;
+	u64 dfr0 = IDREG(kvm, SYS_ID_AA64DFR0_EL1);
 	int i, r;
 
 	if (WARN_ON(realm->rd) || WARN_ON(!realm->params))
@@ -346,6 +347,8 @@ static int realm_create_rd(struct kvm *kvm)
 	params->rtt_num_start = pgt->pgd_pages;
 	params->rtt_base = kvm->arch.mmu.pgd_phys;
 	params->vmid = realm->vmid;
+	params->num_bps = SYS_FIELD_GET(ID_AA64DFR0_EL1, BRPs, dfr0) + 1;
+	params->num_wps = SYS_FIELD_GET(ID_AA64DFR0_EL1, WRPs, dfr0) + 1;
 
 	if (kvm->arch.arm_pmu) {
 		params->pmu_num_ctrs = kvm->arch.pmcr_n;
diff --git a/arch/arm64/kvm/sys_regs.c b/arch/arm64/kvm/sys_regs.c
index 96d73b1867ad..7b05ecc369e0 100644
--- a/arch/arm64/kvm/sys_regs.c
+++ b/arch/arm64/kvm/sys_regs.c
@@ -1731,6 +1731,9 @@ static int set_id_aa64dfr0_el1(struct kvm_vcpu *vcpu,
 {
 	u8 debugver = SYS_FIELD_GET(ID_AA64DFR0_EL1, DebugVer, val);
 	u8 pmuver = SYS_FIELD_GET(ID_AA64DFR0_EL1, PMUVer, val);
+	u8 bps = SYS_FIELD_GET(ID_AA64DFR0_EL1, BRPs, val);
+	u8 wps = SYS_FIELD_GET(ID_AA64DFR0_EL1, WRPs, val);
+	u8 ctx_cmps = SYS_FIELD_GET(ID_AA64DFR0_EL1, CTX_CMPs, val);
 
 	/*
 	 * Prior to commit 3d0dba5764b9 ("KVM: arm64: PMU: Move the
@@ -1750,10 +1753,11 @@ static int set_id_aa64dfr0_el1(struct kvm_vcpu *vcpu,
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
@@ -1836,10 +1840,11 @@ static int set_id_reg(struct kvm_vcpu *vcpu, const struct sys_reg_desc *rd,
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
@@ -2321,7 +2326,9 @@ static const struct sys_reg_desc sys_reg_descs[] = {
 	  .set_user = set_id_aa64dfr0_el1,
 	  .reset = read_sanitised_id_aa64dfr0_el1,
 	  .val = ID_AA64DFR0_EL1_PMUVer_MASK |
-		 ID_AA64DFR0_EL1_DebugVer_MASK, },
+		 ID_AA64DFR0_EL1_DebugVer_MASK |
+		 ID_AA64DFR0_EL1_BRPs_MASK |
+		 ID_AA64DFR0_EL1_WRPs_MASK, },
 	ID_SANITISED(ID_AA64DFR1_EL1),
 	ID_UNALLOCATED(5,2),
 	ID_UNALLOCATED(5,3),

---

## [38] Steven Price — 2024-06-10
*Subject: [PATCH v3 37/43] arm64: RME: Initialize PMCR.N with number counter supported by RMM*

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
index 8aa02134c461..c30d7899f58b 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -88,6 +88,7 @@ struct realm_rec {
 
 void kvm_init_rme(void);
 u32 kvm_realm_ipa_limit(void);
+u8 kvm_realm_max_pmu_counters(void);
 u64 kvm_realm_reset_id_aa64dfr0_el1(struct kvm_vcpu *vcpu, u64 val);
 
 bool kvm_rme_supports_sve(void);
diff --git a/arch/arm64/kvm/pmu-emul.c b/arch/arm64/kvm/pmu-emul.c
index ce7c8e55d904..39790736f1e2 100644
--- a/arch/arm64/kvm/pmu-emul.c
+++ b/arch/arm64/kvm/pmu-emul.c
@@ -912,6 +912,9 @@ u8 kvm_arm_pmu_get_max_counters(struct kvm *kvm)
 {
 	struct arm_pmu *arm_pmu = kvm->arch.arm_pmu;
 
+	if (kvm_is_realm(kvm))
+		return kvm_realm_max_pmu_counters();
+
 	/*
 	 * The arm_pmu->num_events considers the cycle counter as well.
 	 * Ignore that and return only the general-purpose counters.
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 31e00c52551d..1d355f0bb0eb 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -286,6 +286,11 @@ u32 kvm_realm_ipa_limit(void)
 	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_S2SZ);
 }
 
+u8 kvm_realm_max_pmu_counters(void)
+{
+	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_PMU_NUM_CTRS);
+}
+
 u64 kvm_realm_reset_id_aa64dfr0_el1(struct kvm_vcpu *vcpu, u64 val)
 {
 	u32 bps = u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_NUM_BPS);

---

## [39] Steven Price — 2024-06-10
*Subject: [PATCH v3 38/43] arm64: RME: Propagate max SVE vector length from RMM*

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
index bacd2bf1f084..804da7337439 100644
--- a/arch/arm64/include/asm/kvm_host.h
+++ b/arch/arm64/include/asm/kvm_host.h
@@ -76,8 +76,8 @@ static inline enum kvm_mode kvm_get_mode(void) { return KVM_MODE_NONE; };
 
 DECLARE_STATIC_KEY_FALSE(userspace_irqchip_in_use);
 
-extern unsigned int __ro_after_init kvm_sve_max_vl;
 int __init kvm_arm_init_sve(void);
+unsigned int kvm_sve_get_max_vl(struct kvm *kvm);
 
 u32 __attribute_const__ kvm_target_cpu(void);
 void kvm_reset_vcpu(struct kvm_vcpu *vcpu);
diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index c30d7899f58b..a72e06cf4ea6 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -89,6 +89,7 @@ struct realm_rec {
 void kvm_init_rme(void);
 u32 kvm_realm_ipa_limit(void);
 u8 kvm_realm_max_pmu_counters(void);
+unsigned int kvm_realm_sve_max_vl(void);
 u64 kvm_realm_reset_id_aa64dfr0_el1(struct kvm_vcpu *vcpu, u64 val);
 
 bool kvm_rme_supports_sve(void);
diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index ad77e1343269..c06098bc5392 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -355,7 +355,7 @@ static int set_sve_vls(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg)
 		if (vq_present(vqs, vq))
 			max_vq = vq;
 
-	if (max_vq > sve_vq_from_vl(kvm_sve_max_vl))
+	if (max_vq > sve_vq_from_vl(kvm_sve_get_max_vl(vcpu->kvm)))
 		return -EINVAL;
 
 	/*
diff --git a/arch/arm64/kvm/reset.c b/arch/arm64/kvm/reset.c
index 073c9b6b9285..f8b56f6b6dc5 100644
--- a/arch/arm64/kvm/reset.c
+++ b/arch/arm64/kvm/reset.c
@@ -45,7 +45,7 @@ static u32 __ro_after_init kvm_ipa_limit;
 #define VCPU_RESET_PSTATE_SVC	(PSR_AA32_MODE_SVC | PSR_AA32_A_BIT | \
 				 PSR_AA32_I_BIT | PSR_AA32_F_BIT)
 
-unsigned int __ro_after_init kvm_sve_max_vl;
+static unsigned int __ro_after_init kvm_sve_max_vl;
 
 int __init kvm_arm_init_sve(void)
 {
@@ -73,9 +73,17 @@ int __init kvm_arm_init_sve(void)
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
index 1d355f0bb0eb..81964d87daa6 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -291,6 +291,12 @@ u8 kvm_realm_max_pmu_counters(void)
 	return u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_PMU_NUM_CTRS);
 }
 
+unsigned int kvm_realm_sve_max_vl(void)
+{
+	return sve_vl_from_vq(u64_get_bits(rmm_feat_reg0,
+					   RMI_FEATURE_REGISTER_0_SVE_VL) + 1);
+}
+
 u64 kvm_realm_reset_id_aa64dfr0_el1(struct kvm_vcpu *vcpu, u64 val)
 {
 	u32 bps = u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_NUM_BPS);

---

## [40] Steven Price — 2024-06-10
*Subject: [PATCH v3 39/43] arm64: RME: Configure max SVE vector length for a Realm*

From: Jean-Philippe Brucker <jean-philippe@linaro.org>

Obtain the max vector length configured by userspace on the vCPUs, and
write it into the Realm parameters. By default the vCPU is configured
with the max vector length reported by RMM, and userspace can reduce it
with a write to KVM_REG_ARM64_SVE_VLS.

Signed-off-by: Jean-Philippe Brucker <jean-philippe@linaro.org>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/kvm/guest.c |  3 ++-
 arch/arm64/kvm/rme.c   | 42 ++++++++++++++++++++++++++++++++++++++++++
 2 files changed, 44 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index c06098bc5392..e3366c9bdd9d 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -341,7 +341,7 @@ static int set_sve_vls(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg)
 	if (!vcpu_has_sve(vcpu))
 		return -ENOENT;
 
-	if (kvm_arm_vcpu_sve_finalized(vcpu))
+	if (kvm_arm_vcpu_sve_finalized(vcpu) || kvm_realm_is_created(vcpu->kvm))
 		return -EPERM; /* too late! */
 
 	if (WARN_ON(vcpu->arch.sve_state))
@@ -807,6 +807,7 @@ static bool validate_realm_set_reg(struct kvm_vcpu *vcpu,
 		switch (reg->id) {
 		case KVM_REG_ARM_PMCR_EL0:
 		case KVM_REG_ARM_ID_AA64DFR0_EL1:
+		case KVM_REG_ARM64_SVE_VLS:
 			return true;
 		}
 	}
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 81964d87daa6..3f2e2aa4ceac 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -319,6 +319,44 @@ u64 kvm_realm_reset_id_aa64dfr0_el1(struct kvm_vcpu *vcpu, u64 val)
 	return val;
 }
 
+static int realm_init_sve_param(struct kvm *kvm, struct realm_params *params)
+{
+	int ret = 0;
+	unsigned long i;
+	struct kvm_vcpu *vcpu;
+	int max_vl, realm_max_vl = -1;
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
+			max_vl = vcpu->arch.sve_max_vl;
+		} else {
+			max_vl = 0;
+		}
+		mutex_unlock(&vcpu->mutex);
+		if (ret)
+			return ret;
+
+		/* We need all vCPUs to have the same SVE config */
+		if (realm_max_vl >= 0 && realm_max_vl != max_vl)
+			return -EINVAL;
+
+		realm_max_vl = max_vl;
+	}
+
+	if (realm_max_vl > 0) {
+		params->sve_vl = sve_vq_from_vl(realm_max_vl) - 1;
+		params->flags |= RMI_REALM_PARAM_FLAG_SVE;
+	}
+	return 0;
+}
+
 static int realm_create_rd(struct kvm *kvm)
 {
 	struct realm *realm = &kvm->arch.realm;
@@ -366,6 +404,10 @@ static int realm_create_rd(struct kvm *kvm)
 		params->flags |= RMI_REALM_PARAM_FLAG_PMU;
 	}
 
+	r = realm_init_sve_param(kvm, params);
+	if (r)
+		goto out_undelegate_tables;
+
 	params_phys = virt_to_phys(params);
 
 	if (rmi_realm_create(rd_phys, params_phys)) {

---

## [41] Steven Price — 2024-06-10
*Subject: [PATCH v3 40/43] arm64: RME: Provide register list for unfinalized RME RECs*

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
index b04f08e242a6..19b04299d1b2 100644
--- a/arch/arm64/kvm/arm.c
+++ b/arch/arm64/kvm/arm.c
@@ -1805,10 +1805,6 @@ long kvm_arch_vcpu_ioctl(struct file *filp,
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
index e3366c9bdd9d..6299561da46d 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -652,12 +652,9 @@ static unsigned long num_sve_regs(const struct kvm_vcpu *vcpu)
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
@@ -673,8 +670,8 @@ static int copy_sve_reg_indices(const struct kvm_vcpu *vcpu,
 	if (!vcpu_has_sve(vcpu))
 		return 0;
 
-	/* Policed by KVM_GET_REG_LIST: */
-	WARN_ON(!kvm_arm_vcpu_sve_finalized(vcpu));
+	if (!kvm_arm_vcpu_sve_finalized(vcpu))
+		return -EPERM;
 
 	/*
 	 * Enumerate this first, so that userspace can save/restore in

---

## [42] Steven Price — 2024-06-10
*Subject: [PATCH v3 41/43] arm64: RME: Provide accurate register list*

From: Jean-Philippe Brucker <jean-philippe@linaro.org>

Userspace can set a few registers with KVM_SET_ONE_REG (9 GP registers
at runtime, and 3 system registers during initialization). Update the
register list returned by KVM_GET_REG_LIST.

Signed-off-by: Jean-Philippe Brucker <jean-philippe@linaro.org>
Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/kvm/guest.c      | 40 ++++++++++++++++++-------
 arch/arm64/kvm/hypercalls.c |  4 +--
 arch/arm64/kvm/sys_regs.c   | 58 ++++++++++++++++++++++++++++---------
 3 files changed, 75 insertions(+), 27 deletions(-)

diff --git a/arch/arm64/kvm/guest.c b/arch/arm64/kvm/guest.c
index 6299561da46d..1f26452dc4d3 100644
--- a/arch/arm64/kvm/guest.c
+++ b/arch/arm64/kvm/guest.c
@@ -73,6 +73,17 @@ static u64 core_reg_offset_from_id(u64 id)
 	return id & ~(KVM_REG_ARCH_MASK | KVM_REG_SIZE_MASK | KVM_REG_ARM_CORE);
 }
 
+static bool kvm_realm_validate_core_reg(u64 off)
+{
+	switch (off) {
+	case KVM_REG_ARM_CORE_REG(regs.regs[0]) ...
+	     KVM_REG_ARM_CORE_REG(regs.regs[7]):
+	case KVM_REG_ARM_CORE_REG(regs.pc):
+		return true;
+	}
+	return false;
+}
+
 static int core_reg_size_from_offset(const struct kvm_vcpu *vcpu, u64 off)
 {
 	int size;
@@ -115,6 +126,9 @@ static int core_reg_size_from_offset(const struct kvm_vcpu *vcpu, u64 off)
 	if (vcpu_has_sve(vcpu) && core_reg_offset_is_vreg(off))
 		return -EINVAL;
 
+	if (kvm_is_realm(vcpu->kvm) && !kvm_realm_validate_core_reg(off))
+		return -EPERM;
+
 	return size;
 }
 
@@ -599,8 +613,6 @@ static const u64 timer_reg_list[] = {
 	KVM_REG_ARM_PTIMER_CVAL,
 };
 
-#define NUM_TIMER_REGS ARRAY_SIZE(timer_reg_list)
-
 static bool is_timer_reg(u64 index)
 {
 	switch (index) {
@@ -615,9 +627,14 @@ static bool is_timer_reg(u64 index)
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
@@ -655,6 +672,9 @@ static unsigned long num_sve_regs(const struct kvm_vcpu *vcpu)
 	if (!vcpu_has_sve(vcpu) || !kvm_arm_vcpu_sve_finalized(vcpu))
 		return 0;
 
+	if (kvm_is_realm(vcpu->kvm))
+		return 1; /* KVM_REG_ARM64_SVE_VLS */
+
 	return slices * (SVE_NUM_PREGS + SVE_NUM_ZREGS + 1 /* FFR */)
 		+ 1; /* KVM_REG_ARM64_SVE_VLS */
 }
@@ -682,6 +702,9 @@ static int copy_sve_reg_indices(const struct kvm_vcpu *vcpu,
 		return -EFAULT;
 	++num_regs;
 
+	if (kvm_is_realm(vcpu->kvm))
+		return num_regs;
+
 	for (i = 0; i < slices; i++) {
 		for (n = 0; n < SVE_NUM_ZREGS; n++) {
 			reg = KVM_REG_ARM64_SVE_ZREG(n, i);
@@ -720,7 +743,7 @@ unsigned long kvm_arm_num_regs(struct kvm_vcpu *vcpu)
 	res += num_sve_regs(vcpu);
 	res += kvm_arm_num_sys_reg_descs(vcpu);
 	res += kvm_arm_get_fw_num_regs(vcpu);
-	res += NUM_TIMER_REGS;
+	res += num_timer_regs(vcpu);
 
 	return res;
 }
@@ -754,7 +777,7 @@ int kvm_arm_copy_reg_indices(struct kvm_vcpu *vcpu, u64 __user *uindices)
 	ret = copy_timer_indices(vcpu, uindices);
 	if (ret < 0)
 		return ret;
-	uindices += NUM_TIMER_REGS;
+	uindices += num_timer_regs(vcpu);
 
 	return kvm_arm_copy_sys_reg_indices(vcpu, uindices);
 }
@@ -794,12 +817,7 @@ static bool validate_realm_set_reg(struct kvm_vcpu *vcpu,
 	if ((reg->id & KVM_REG_ARM_COPROC_MASK) == KVM_REG_ARM_CORE) {
 		u64 off = core_reg_offset_from_id(reg->id);
 
-		switch (off) {
-		case KVM_REG_ARM_CORE_REG(regs.regs[0]) ...
-		     KVM_REG_ARM_CORE_REG(regs.regs[7]):
-		case KVM_REG_ARM_CORE_REG(regs.pc):
-			return true;
-		}
+		return kvm_realm_validate_core_reg(off);
 	} else {
 		switch (reg->id) {
 		case KVM_REG_ARM_PMCR_EL0:
diff --git a/arch/arm64/kvm/hypercalls.c b/arch/arm64/kvm/hypercalls.c
index 5763d979d8ca..28b4166cf234 100644
--- a/arch/arm64/kvm/hypercalls.c
+++ b/arch/arm64/kvm/hypercalls.c
@@ -407,14 +407,14 @@ void kvm_arm_teardown_hypercalls(struct kvm *kvm)
 
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
index 7b05ecc369e0..7e4fc7915db5 100644
--- a/arch/arm64/kvm/sys_regs.c
+++ b/arch/arm64/kvm/sys_regs.c
@@ -3888,18 +3888,18 @@ int kvm_arm_sys_reg_set_reg(struct kvm_vcpu *vcpu, const struct kvm_one_reg *reg
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
@@ -3907,6 +3907,23 @@ static int write_demux_regids(u64 __user *uindices)
 	return 0;
 }
 
+static unsigned int num_invariant_regs(struct kvm_vcpu *vcpu)
+{
+	return kvm_is_realm(vcpu->kvm) ? 0 : ARRAY_SIZE(invariant_sys_regs);
+}
+
+static int write_invariant_regids(struct kvm_vcpu *vcpu, u64 __user *uindices)
+{
+	unsigned int i;
+
+	for (i = 0; i < num_invariant_regs(vcpu); i++) {
+		if (put_user(sys_reg_to_index(&invariant_sys_regs[i]), uindices))
+			return -EFAULT;
+		uindices++;
+	}
+	return 0;
+}
+
 static u64 sys_reg_to_index(const struct sys_reg_desc *reg)
 {
 	return (KVM_REG_ARM64 | KVM_REG_SIZE_U64 |
@@ -3930,11 +3947,27 @@ static bool copy_reg_to_user(const struct sys_reg_desc *reg, u64 __user **uind)
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
@@ -3972,29 +4005,26 @@ static int walk_sys_regs(struct kvm_vcpu *vcpu, u64 __user *uind)
 
 unsigned long kvm_arm_num_sys_reg_descs(struct kvm_vcpu *vcpu)
 {
-	return ARRAY_SIZE(invariant_sys_regs)
-		+ num_demux_regs()
+	return num_invariant_regs(vcpu)
+		+ num_demux_regs(vcpu)
 		+ walk_sys_regs(vcpu, (u64 __user *)NULL);
 }
 
 int kvm_arm_copy_sys_reg_indices(struct kvm_vcpu *vcpu, u64 __user *uindices)
 {
-	unsigned int i;
 	int err;
 
-	/* Then give them all the invariant registers' indices. */
-	for (i = 0; i < ARRAY_SIZE(invariant_sys_regs); i++) {
-		if (put_user(sys_reg_to_index(&invariant_sys_regs[i]), uindices))
-			return -EFAULT;
-		uindices++;
-	}
+	err = write_invariant_regids(vcpu, uindices);
+	if (err)
+		return err;
+	uindices += num_invariant_regs(vcpu);
 
 	err = walk_sys_regs(vcpu, uindices);
 	if (err < 0)
 		return err;
 	uindices += err;
 
-	return write_demux_regids(uindices);
+	return write_demux_regids(vcpu, uindices);
 }
 
 #define KVM_ARM_FEATURE_ID_RANGE_INDEX(r)			\

---

## [43] Steven Price — 2024-06-10
*Subject: [PATCH v3 42/43] arm64: kvm: Expose support for private memory*

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
 arch/arm64/kvm/mmu.c              | 22 ++++++++++++++++++++++
 3 files changed, 29 insertions(+)

diff --git a/arch/arm64/include/asm/kvm_host.h b/arch/arm64/include/asm/kvm_host.h
index 804da7337439..b7ad94149c61 100644
--- a/arch/arm64/include/asm/kvm_host.h
+++ b/arch/arm64/include/asm/kvm_host.h
@@ -1302,6 +1302,12 @@ struct kvm *kvm_arch_alloc_vm(void);
 
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
index 58f09370d17e..8da57e74c86a 100644
--- a/arch/arm64/kvm/Kconfig
+++ b/arch/arm64/kvm/Kconfig
@@ -37,6 +37,7 @@ menuconfig KVM
 	select HAVE_KVM_VCPU_RUN_PID_CHANGE
 	select SCHED_INFO
 	select GUEST_PERF_EVENTS if PERF_EVENTS
+	select KVM_GENERIC_PRIVATE_MEM
 	help
 	  Support hosting virtualized guest machines.
 
diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index b3793c2b8499..e693887af424 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -2141,6 +2141,28 @@ int kvm_arch_prepare_memory_region(struct kvm *kvm,
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
+		range->only_shared = true;
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

## [44] Steven Price — 2024-06-10
*Subject: [PATCH v3 43/43] KVM: arm64: Allow activating realms*

Add the ioctl to activate a realm and set the static branch to enable
access to the realm functionality if the RMM is detected.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/kvm/rme.c | 19 ++++++++++++++++++-
 1 file changed, 18 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 3f2e2aa4ceac..60b41b79db1b 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -1194,6 +1194,20 @@ static int kvm_init_ipa_range_realm(struct kvm *kvm,
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
@@ -1343,6 +1357,9 @@ int kvm_realm_enable_cap(struct kvm *kvm, struct kvm_enable_cap *cap)
 		r = kvm_populate_realm(kvm, &args);
 		break;
 	}
+	case KVM_CAP_ARM_RME_ACTIVATE_REALM:
+		r = kvm_activate_realm(kvm);
+		break;
 	default:
 		r = -EINVAL;
 		break;
@@ -1599,5 +1616,5 @@ void kvm_init_rme(void)
 	if (rme_vmid_init())
 		return;
 
-	/* Future patch will enable static branch kvm_rme_is_available */
+	static_branch_enable(&kvm_rme_is_available);
 }

---
