---
title: '[RFC PATCH v4 00/16] coco/TSM: Implement host-side support for Arm CCA TDISP setup'
date: 2026-04-27
last_reply: 2026-04-27
message_count: 17
participants: ['Aneesh Kumar K.V (Arm)']
---

## [1] Aneesh Kumar K.V (Arm) — 2026-04-27

This patch series implements the host-side changes needed for end-to-end
Arm CCA TDISP setup. It adds the RMI/RHI plumbing required to create and
manage Realm vdev objects, service device-attestation object requests, and
complete the KVM/RMM flows needed for device run-time transitions.

The series is based on the RMM 2.0bet1 specification [1] and the
RHI v1.0 BET1 specification [5].

At a high level, the series adds support for:
- host-side vdev communication and lifecycle management
- host handling of RHI DA object read/size requests
- host-side fetching and caching of interface reports and measurements
- KVM handling of vdev request/complete exits
- KVM handling of map/validation exits and teardown on granule destroy
- vdev transition to TDISP RUN state
- enabling DA in Realm create parameters

The series builds upon the TSM framework patches posted at [2] and depends on
the KVM CCA patchset [3]. A git repository containing all related changes is
available at [4]. kvmtool repo is at [6]

Previous posting:
Changes from v3:
https://lore.kernel.org/all/20260312080743.3487326-1-aneesh.kumar@kernel.org
* updated the patches to follow the RMM 2.0bet1 specification
* moved vdev request-exit handling to the last patch in the series. This is
  expected to be dropped once the corresponding spec update lands
* dropped the vdev and pdev arguments from rmi_rtt_dev_validate(). The spec
  update for that change is still pending. The validation call is now made
  from the REC enter path
* added a response field to KVM_EXIT_ARM64_TIO so the VMM can pass the ioctl
  return status back to the exit handler
* dropped vcpu_fd from arm64_vdev_device_memmap_guest_req. Once vdev request
  handling is removed from the series, the ioctl path will no longer need
  vcpu_fd
* reworked the host-side vdev lifecycle to better match the RMM 2.0bet1 flow,
* updated the vdev flows to match the revised interfaces: populate MMIO BAR
  ranges in rmi_vdev_create(), rename the interface-report and measurement
  update commands, and drop vcpu_fd from the guest MMIO map request path

Changes from v1:
* rebase to latest kernel and core TSM changes
* address review feedback

rfc-v1: https://lore.kernel.org/all/20250728135216.48084-1-aneesh.kumar@kernel.org
There is no rfc-v2 posting. This series is marked rfc-v3 to stay aligned
with the rest of the CCA patchsets that are being posted as v3.

[1] https://developer.arm.com/documentation/den0137/2-0bet1/
[2] https://lore.kernel.org/all/20260303000207.1836586-1-dan.j.williams@intel.com
[3] https://lore.kernel.org/all/20260318155413.793430-1-steven.price@arm.com
[4] https://gitlab.arm.com/linux-arm/linux-cca.git cca/topics/cca-tdisp-upstream-rfc-v4
[5] https://developer.arm.com/documentation/den0148/latest/
[6] https://gitlab.arm.com/linux-arm/kvmtool-cca.git cca/topics/cca-tdisp-upstream-rfc-v4

Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Joerg Roedel <joro@8bytes.org>
Cc: Jonathan Cameron <jic23@kernel.org>
Cc: Marc Zyngier <maz@kernel.org>
Cc: Nicolin Chen <nicolinc@nvidia.com>
Cc: Pranjal Shrivastava <praan@google.com>
Cc: Robin Murphy <robin.murphy@arm.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Steven Price <steven.price@arm.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Xu Yilun <yilun.xu@linux.intel.com>

Aneesh Kumar K.V (Arm) (16):
  iommu/arm-smmu-v3: Discover RME support and realm IRQ topology
  iommu/arm-smmu-v3: Save the programmed MSI message in msi_desc
  iommu/arm-smmu-v3: Add initial pSMMU realm viommu plumbing
  iommu/arm-smmu-v3: Track realm pSMMU users with refcount_t
  coco: host: arm64: Add support for virtual device communication
  coco: host: arm64: Add support for RMM vdev objects
  coco: host: arm64: Add pdev stream key refresh and purge helpers
  coco: host: arm64: Add helpers to unlock and destroy RMM vdev
  coco: host: arm64: Add support for da object read RHI handling
  coco: host: arm64: Add helper for cached object fetches
  coco: host: arm64: Fetch interface report via RMI
  coco: host: arm64: Fetch device measurements via RMI
  coco: host: KVM: arm64: Handle vdev validate-mapping exits
  KVM: arm64: Unmap device mappings when a private granule is destroyed
  coco: host: arm64: Transition vdevs to TDISP RUN state
  KVM: arm64: CCA: enable DA in realm create parameters

 Documentation/virt/kvm/api.rst                |  20 +
 arch/arm64/include/asm/kvm_rmi.h              |   4 +
 arch/arm64/include/asm/rmi_cmds.h             | 193 ++++++
 arch/arm64/include/asm/rmi_smc.h              |  98 ++-
 arch/arm64/include/uapi/asm/rmi-da.h          |  47 ++
 arch/arm64/kernel/rmi.c                       |  51 ++
 arch/arm64/kvm/rmi-exit.c                     |  37 ++
 arch/arm64/kvm/rmi.c                          | 279 ++++++++-
 drivers/iommu/arm/arm-smmu-v3/Makefile        |   2 +-
 .../arm/arm-smmu-v3/arm-smmu-v3-iommufd.c     |   7 +
 .../iommu/arm/arm-smmu-v3/arm-smmu-v3-realm.c | 297 +++++++++
 drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.c   |  86 ++-
 drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.h   |  16 +
 drivers/virt/coco/arm-cca-host/arm-cca.c      | 188 +++++-
 drivers/virt/coco/arm-cca-host/rmi-da.c       | 569 +++++++++++++++++-
 drivers/virt/coco/arm-cca-host/rmi-da.h       |  40 ++
 include/uapi/linux/iommufd.h                  |   1 +
 include/uapi/linux/kvm.h                      |  11 +
 18 files changed, 1929 insertions(+), 17 deletions(-)
 create mode 100644 arch/arm64/include/uapi/asm/rmi-da.h
 create mode 100644 drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-realm.c

---

## [2] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 01/16] iommu/arm-smmu-v3: Discover RME support and realm IRQ topology*

Detect RME-capable SMMUv3 instances from IDR0.RME_IMPL and record the
capability in arm_smmu_device.

When RMM is active, query RMI_PSMMU_INFO to discover how realm-side
notifications are delivered. For pSMMUs that expose realm interrupts, store
the reported evtq/gerror/priq IRQs, reserve extra MSI vectors when RMM uses
MSI delivery, and register threaded handlers that acknowledge notifications
through RMI_PSMMU_IRQ_NOTIFY / RMI_PSMMU_EVENT_CONSUME.

Also add the RMI command/structure definitions needed for PSMMU_INFO and
interrupt notification, along with arm_smmu_device state for the physical
base address and realm IRQs.

If RMM reports a CMDQ sync interrupt requirement, keep the IRQ plumbing
but leave ARM_SMMU_FEAT_RME disabled.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h             |  52 ++++++++
 arch/arm64/include/asm/rmi_smc.h              |  32 ++++-
 drivers/iommu/arm/arm-smmu-v3/Makefile        |   2 +-
 .../iommu/arm/arm-smmu-v3/arm-smmu-v3-realm.c | 124 ++++++++++++++++++
 drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.c   |  81 +++++++++++-
 drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.h   |  10 ++
 6 files changed, 297 insertions(+), 4 deletions(-)
 create mode 100644 drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-realm.c

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index c82d4d9cbc06..75eb59d4fa84 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -811,4 +811,56 @@ static inline unsigned long rmi_pdev_stream_disconnect(unsigned long pdev1_phys,
 	return res.a0;
 }
 
+static inline unsigned long rmi_psmmu_info(unsigned long psmmu_phys,
+		unsigned long psmmu_info_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PSMMU_INFO,
+			     psmmu_phys, psmmu_info_phys, &res);
+
+	return res.a0;
+}
+
+struct rmi_psmmu_event_details {
+	u64 flags;
+	u64 event_num;
+	u64 stream_id; /* valid only if we have VSMMU event */
+	u64 fetch_addr;
+	u64 input_addr;
+	u64 syndrome;
+};
+
+static inline unsigned long rmi_psmmu_irq_notify(unsigned long psmmu_phys,
+		unsigned long irqs, struct rmi_psmmu_event_details *event)
+{
+	struct arm_smccc_1_2_regs regs = {
+		.a0 = SMC_RMI_PSMMU_IRQ_NOTIFY,
+		.a1 = psmmu_phys,
+		.a2 = irqs,
+	};
+
+	arm_smccc_1_2_invoke(&regs, &regs);
+
+	event->flags      = regs.a1;
+	event->event_num  = regs.a2;
+	event->stream_id  = regs.a3;
+	event->fetch_addr = regs.a4;
+	event->input_addr = regs.a5;
+	event->syndrome   = regs.a6;
+
+	return regs.a0;
+}
+
+static inline unsigned long rmi_psmmu_event_consume(unsigned long psmmu_phys,
+		unsigned long irqs)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PSMMU_EVENT_CONSUME,
+			     psmmu_phys, irqs, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 7b16f1540a0e..be1b1e95a937 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -101,7 +101,7 @@
 #define SMC_RMI_PDEV_MEC_UPDATE			SMC_RMI_CALL(0x01ed)
 #define SMC_RMI_VSMMU_EVENT_COMPLETE		SMC_RMI_CALL(0x01ee)
 
-#define SMC_RMI_PSMMU_EVENT_DISCARD		SMC_RMI_CALL(0x01f0)
+#define SMC_RMI_PSMMU_EVENT_CONSUME		SMC_RMI_CALL(0x01f0)
 #define SMC_RMI_GRANULE_RANGE_DELEGATE		SMC_RMI_CALL(0x01f1)
 #define SMC_RMI_GRANULE_RANGE_UNDELEGATE	SMC_RMI_CALL(0x01f2)
 #define SMC_RMI_GPT_L1_CREATE			SMC_RMI_CALL(0x01f3)
@@ -129,6 +129,7 @@
 #define SMC_RMI_OP_MEM_RECLAIM			SMC_RMI_CALL(0x0209)
 #define SMC_RMI_OP_CANCEL			SMC_RMI_CALL(0x020a)
 #define SMC_RMI_PDEV_SET_PROT			SMC_RMI_CALL(0x020b)
+#define SMC_RMI_PSMMU_INFO			SMC_RMI_CALL(0x020e)
 
 #define RMI_ABI_MAJOR_VERSION	2
 #define RMI_ABI_MINOR_VERSION	0
@@ -595,4 +596,33 @@ struct rmi_pdev_stream_params {
 	};
 };
 
+#define RMI_PSMMU_IRQCFG_IRQ_DISABLED	0x0
+#define RMI_PSMMU_IRQCFG_IRQ_WIRED	0x1
+#define RMI_PSMMU_IRQCFG_IRQ_MSI	0x2
+#define RMI_PSMMU_IRQCFG_MASK		GENMASK(1, 0)
+struct rmi_psmmu_info {
+	union {
+		struct {
+			u64 flags;
+			union {
+				u32 gerror_intr_num;
+				u8 padding1[8];
+			};
+			union {
+				u32 eventq_intr_num;
+				u8 padding2[8];
+			};
+			union {
+				u32 priq_intr_num;
+				u8 padding3[8];
+			};
+			union {
+				u32 cmdq_sync_intr_num;
+				u8 padding4[8];
+			};
+		};
+		u8 padding5[0x1000];
+	};
+};
+
 #endif /* __ASM_RMI_SMC_H */
diff --git a/drivers/iommu/arm/arm-smmu-v3/Makefile b/drivers/iommu/arm/arm-smmu-v3/Makefile
index 493a659cc66b..23bd794ebeda 100644
--- a/drivers/iommu/arm/arm-smmu-v3/Makefile
+++ b/drivers/iommu/arm/arm-smmu-v3/Makefile
@@ -1,6 +1,6 @@
 # SPDX-License-Identifier: GPL-2.0
 obj-$(CONFIG_ARM_SMMU_V3) += arm_smmu_v3.o
-arm_smmu_v3-y := arm-smmu-v3.o
+arm_smmu_v3-y := arm-smmu-v3.o arm-smmu-v3-realm.o
 arm_smmu_v3-$(CONFIG_ARM_SMMU_V3_IOMMUFD) += arm-smmu-v3-iommufd.o
 arm_smmu_v3-$(CONFIG_ARM_SMMU_V3_SVA) += arm-smmu-v3-sva.o
 arm_smmu_v3-$(CONFIG_TEGRA241_CMDQV) += tegra241-cmdqv.o
diff --git a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-realm.c b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-realm.c
new file mode 100644
index 000000000000..fec1a32de53c
--- /dev/null
+++ b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-realm.c
@@ -0,0 +1,124 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2026 ARM Ltd.
+ */
+
+#include <linux/interrupt.h>
+#include <asm/rmi_smc.h>
+#include <asm/rmi_cmds.h>
+
+#include "arm-smmu-v3.h"
+
+#define	RMI_PSMMU_IRQ_GERROR	BIT(0)
+#define	RMI_PSMMU_IRQ_EVENTQ	BIT(1)
+#define	RMI_PSMMU_IRQ_PRIQ	BIT(2)
+#define	RMI_PSMMU_IRQ_CMDQ	BIT(3)
+
+#define	RMI_PSMMU_IRQ_EVENT_NONE	0
+#define	RMI_PSMMU_IRQ_EVENT_ERROR	1
+#define	RMI_PSMMU_IRQ_EVENT_PSMMU	2
+#define	RMI_PSMMU_IRQ_EVENT_VSMMU	3
+#define RMI_PSMMU_IRQ_EVENT_MASK	GENMASK(2, 1)
+#define RMI_PSMMU_IRQ_EVENT_SHIFT	1
+#define RMI_PSMMU_IRQ_EVENT_PENDING	0x1
+
+static irqreturn_t arm_smmu_realm_notify_thread(int irq, void *dev)
+{
+	int rmi_psmmu_event;
+	unsigned long notify_flags;
+	struct arm_smmu_device *smmu = dev;
+	struct rmi_psmmu_event_details event;
+
+	if (irq == smmu->realm_evtq_irq)
+		notify_flags =  RMI_PSMMU_IRQ_EVENTQ;
+	else if (irq == smmu->realm_gerr_irq)
+		notify_flags =  RMI_PSMMU_IRQ_GERROR;
+	else if (irq == smmu->realm_pri_irq)
+		notify_flags =  RMI_PSMMU_IRQ_PRIQ;
+	else
+		return IRQ_HANDLED;
+
+	do {
+		if (rmi_psmmu_irq_notify(smmu->base_phys,
+					 notify_flags, &event)) {
+			dev_warn(smmu->dev,
+				 "failed to notify RMM of a SMMU event\n");
+			/* there is nothing much we could do. Mark it handled. */
+			return IRQ_HANDLED;
+		}
+		rmi_psmmu_event = (event.flags & RMI_PSMMU_IRQ_EVENT_MASK) >>
+				  RMI_PSMMU_IRQ_EVENT_SHIFT;
+		switch (rmi_psmmu_event) {
+		case RMI_PSMMU_IRQ_EVENT_NONE:
+			break;
+		case RMI_PSMMU_IRQ_EVENT_ERROR:
+			dev_warn(smmu->dev, "SMMU Error reported\n");
+			rmi_psmmu_event_consume(smmu->base_phys, notify_flags);
+			break;
+		case RMI_PSMMU_IRQ_EVENT_PSMMU:
+			dev_warn(smmu->dev,
+				 "SMMU event (event num: 0x%llx syndrome 0x%llx "
+				 "fetch_addr 0x%llx input_addr 0x%llx) reported\n",
+				 event.event_num, event.syndrome,
+				 event.fetch_addr, event.input_addr);
+			rmi_psmmu_event_consume(smmu->base_phys, notify_flags);
+			break;
+		case RMI_PSMMU_IRQ_EVENT_VSMMU:
+			dev_warn(smmu->dev, "Wrong VSMMU event on stream 0x%llx, ignoring\n",
+				 event.stream_id);
+			rmi_psmmu_event_consume(smmu->base_phys, notify_flags);
+			break;
+		}
+
+	} while (event.flags & RMI_PSMMU_IRQ_EVENT_PENDING);
+
+	return IRQ_HANDLED;
+}
+
+void arm_smmu_setup_realm_irqs(struct arm_smmu_device *smmu)
+{
+	int irq, ret;
+
+	irq = smmu->realm_evtq_irq;
+	if (irq) {
+		ret = devm_request_threaded_irq(smmu->dev, irq, NULL,
+						arm_smmu_realm_notify_thread,
+						IRQF_ONESHOT,
+						"arm-smmu-v3-realm-evtq",
+						smmu);
+		if (ret < 0)
+			dev_warn(smmu->dev, "failed to enable realm evtq irq\n");
+	} else {
+		dev_warn(smmu->dev, "no realm evtq irq - events will not be reported!\n");
+	}
+
+	irq = smmu->realm_gerr_irq;
+	if (irq) {
+		ret = devm_request_threaded_irq(smmu->dev, irq, NULL,
+						arm_smmu_realm_notify_thread,
+						IRQF_ONESHOT,
+						"arm-smmu-v3-realm-gerror",
+						smmu);
+		if (ret < 0)
+			dev_warn(smmu->dev, "failed to enable realm gerror irq\n");
+	} else {
+		dev_warn(smmu->dev, "no realm gerr irq - errors will not be reported!\n");
+	}
+
+	if (smmu->features & ARM_SMMU_FEAT_PRI) {
+		irq = smmu->realm_pri_irq;
+		if (irq) {
+
+			ret = devm_request_threaded_irq(smmu->dev, irq, NULL,
+							arm_smmu_realm_notify_thread,
+							IRQF_ONESHOT,
+							"arm-smmu-v3-realm-priq",
+							smmu);
+			if (ret < 0)
+				dev_warn(smmu->dev,
+					 "failed to enable realm priq irq\n");
+		} else {
+			dev_warn(smmu->dev, "no realm priq irq - PRI will be broken\n");
+		}
+	}
+}
diff --git a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.c b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.c
index 4d00d796f078..d5b9ab95beea 100644
--- a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.c
+++ b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.c
@@ -29,6 +29,9 @@
 #include <linux/string_choices.h>
 #include <kunit/visibility.h>
 #include <uapi/linux/iommufd.h>
+#include <linux/irq.h>
+#include <linux/msi.h>
+#include <asm/rmi_cmds.h>
 
 #include "arm-smmu-v3.h"
 #include "../../dma-iommu.h"
@@ -4000,10 +4003,20 @@ static void arm_smmu_free_msis(void *data)
 
 static void arm_smmu_write_msi_msg(struct msi_desc *desc, struct msi_msg *msg)
 {
+	int max_config_index = GERROR_MSI_INDEX;
 	phys_addr_t doorbell;
 	struct device *dev = msi_desc_to_dev(desc);
 	struct arm_smmu_device *smmu = dev_get_drvdata(dev);
-	phys_addr_t *cfg = arm_smmu_msi_cfg[desc->msi_index];
+	phys_addr_t *cfg;
+
+	if (smmu->features & ARM_SMMU_FEAT_PRI)
+		max_config_index = PRIQ_MSI_INDEX;
+
+	/* Don't try to config for Realm interrupts. */
+	if (desc->msi_index > max_config_index)
+		return;
+
+	cfg = arm_smmu_msi_cfg[desc->msi_index];
 
 	doorbell = (((u64)msg->address_hi) << 32) | msg->address_lo;
 	doorbell &= MSI_CFG0_ADDR_MASK;
@@ -4015,6 +4028,7 @@ static void arm_smmu_write_msi_msg(struct msi_desc *desc, struct msi_msg *msg)
 
 static void arm_smmu_setup_msis(struct arm_smmu_device *smmu)
 {
+	int irq_index;
 	int ret, nvec = ARM_SMMU_MAX_MSIS;
 	struct device *dev = smmu->dev;
 
@@ -4035,6 +4049,13 @@ static void arm_smmu_setup_msis(struct arm_smmu_device *smmu)
 		return;
 	}
 
+	/*
+	 * Request for realm side non secure interrupts too. Should this be condition
+	 * on non-secure gic?
+	 */
+	if (smmu->features & ARM_SMMU_FEAT_RME_MSI)
+		nvec = nvec * 2;
+
 	/* Allocate MSIs for evtq, gerror and priq. Ignore cmdq */
 	ret = platform_device_msi_init_and_alloc_irqs(dev, nvec, arm_smmu_write_msi_msg);
 	if (ret) {
@@ -4044,7 +4065,19 @@ static void arm_smmu_setup_msis(struct arm_smmu_device *smmu)
 
 	smmu->evtq.q.irq = msi_get_virq(dev, EVTQ_MSI_INDEX);
 	smmu->gerr_irq = msi_get_virq(dev, GERROR_MSI_INDEX);
-	smmu->priq.q.irq = msi_get_virq(dev, PRIQ_MSI_INDEX);
+	irq_index = 2;
+	if (smmu->features & ARM_SMMU_FEAT_PRI) {
+		smmu->priq.q.irq = msi_get_virq(dev, PRIQ_MSI_INDEX);
+		irq_index++;
+	}
+
+	if (smmu->features & ARM_SMMU_FEAT_RME_MSI) {
+		smmu->realm_evtq_irq = msi_get_virq(dev, irq_index++);
+		smmu->realm_gerr_irq = msi_get_virq(dev, irq_index++);
+		// fixme, we should check for pri rmm capability
+		if (smmu->features & ARM_SMMU_FEAT_PRI)
+			smmu->realm_pri_irq = msi_get_virq(dev, irq_index++);
+	}
 
 	/* Add callback to free MSIs on teardown */
 	devm_add_action_or_reset(dev, arm_smmu_free_msis, dev);
@@ -4094,6 +4127,9 @@ static void arm_smmu_setup_unique_irqs(struct arm_smmu_device *smmu)
 			dev_warn(smmu->dev, "no priq irq - PRI will be broken\n");
 		}
 	}
+
+	if (smmu->features & ARM_SMMU_FEAT_RME_IRQ)
+		arm_smmu_setup_realm_irqs(smmu);
 }
 
 static int arm_smmu_setup_irqs(struct arm_smmu_device *smmu)
@@ -4464,6 +4500,9 @@ static int arm_smmu_device_hw_probe(struct arm_smmu_device *smmu)
 	smmu->asid_bits = reg & IDR0_ASID16 ? 16 : 8;
 	smmu->vmid_bits = reg & IDR0_VMID16 ? 16 : 8;
 
+	if (reg & IDR0_RME_IMPL)
+		smmu->features |= ARM_SMMU_FEAT_RME;
+
 	/* IDR1 */
 	reg = readl_relaxed(smmu->base + ARM_SMMU_IDR1);
 	if (reg & (IDR1_TABLES_PRESET | IDR1_QUEUES_PRESET | IDR1_REL)) {
@@ -4852,6 +4891,7 @@ static int arm_smmu_device_probe(struct platform_device *pdev)
 		return -EINVAL;
 	}
 	ioaddr = res->start;
+	smmu->base_phys = ioaddr;
 
 	/*
 	 * Don't map the IMPLEMENTATION DEFINED regions, since they may contain
@@ -4893,6 +4933,43 @@ static int arm_smmu_device_probe(struct platform_device *pdev)
 	if (ret)
 		return ret;
 
+	if (rmm_is_active()) {
+		struct rmi_psmmu_info *psmmu_info;
+
+		psmmu_info = (struct rmi_psmmu_info *)get_zeroed_page(GFP_KERNEL);
+		if (!psmmu_info)
+			goto skip_rmm_config;
+
+		if (rmi_psmmu_info(smmu->base_phys, virt_to_phys(psmmu_info)))
+			smmu->features &= ~ARM_SMMU_FEAT_RME;
+
+		if ((psmmu_info->flags & RMI_PSMMU_IRQCFG_MASK) ==
+		    RMI_PSMMU_IRQCFG_IRQ_DISABLED) {
+			free_page((unsigned long)psmmu_info);
+			goto skip_rmm_config;
+		}
+
+		smmu->features |= ARM_SMMU_FEAT_RME_IRQ;
+
+		if ((psmmu_info->flags & RMI_PSMMU_IRQCFG_MASK) ==
+		    RMI_PSMMU_IRQCFG_IRQ_WIRED) {
+			smmu->realm_gerr_irq = psmmu_info->gerror_intr_num;
+			smmu->realm_evtq_irq = psmmu_info->eventq_intr_num;
+			smmu->realm_pri_irq = psmmu_info->priq_intr_num;
+
+			/* Disable RME FEAT because RMM need cmdq sync interrupt*/
+			if (psmmu_info->cmdq_sync_intr_num)
+				smmu->features &= ~ARM_SMMU_FEAT_RME;
+
+		} else if ((psmmu_info->flags & RMI_PSMMU_IRQCFG_MASK) ==
+			   RMI_PSMMU_IRQCFG_IRQ_MSI) {
+			smmu->features |= ARM_SMMU_FEAT_RME_MSI;
+		}
+
+		free_page((unsigned long)psmmu_info);
+	}
+skip_rmm_config:
+
 	/* Initialise in-memory data structures */
 	ret = arm_smmu_init_structures(smmu);
 	if (ret)
diff --git a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.h b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.h
index 3c6d65d36164..6680516b571b 100644
--- a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.h
+++ b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.h
@@ -20,6 +20,7 @@ struct arm_vsmmu;
 
 /* MMIO registers */
 #define ARM_SMMU_IDR0			0x0
+#define IDR0_RME_IMPL			(1 << 30)
 #define IDR0_ST_LVL			GENMASK(28, 27)
 #define IDR0_ST_LVL_2LVL		1
 #define IDR0_STALL_MODEL		GENMASK(25, 24)
@@ -739,6 +740,7 @@ struct arm_smmu_device {
 	struct device			*impl_dev;
 	const struct arm_smmu_impl_ops	*impl_ops;
 
+	phys_addr_t			base_phys;
 	void __iomem			*base;
 	void __iomem			*page1;
 
@@ -767,6 +769,9 @@ struct arm_smmu_device {
 #define ARM_SMMU_FEAT_HD		(1 << 22)
 #define ARM_SMMU_FEAT_S2FWB		(1 << 23)
 #define ARM_SMMU_FEAT_BBML2		(1 << 24)
+#define ARM_SMMU_FEAT_RME		(1 << 25)
+#define ARM_SMMU_FEAT_RME_IRQ		(1 << 26)
+#define ARM_SMMU_FEAT_RME_MSI		(1 << 27)
 	u32				features;
 
 #define ARM_SMMU_OPT_SKIP_PREFETCH	(1 << 0)
@@ -782,6 +787,9 @@ struct arm_smmu_device {
 
 	int				gerr_irq;
 	int				combined_irq;
+	int				realm_gerr_irq;
+	int				realm_evtq_irq;
+	int				realm_pri_irq;
 
 	unsigned long			oas; /* PA */
 	unsigned long			pgsize_bitmap;
@@ -1096,4 +1104,6 @@ static inline int arm_vmaster_report_event(struct arm_smmu_vmaster *vmaster,
 }
 #endif /* CONFIG_ARM_SMMU_V3_IOMMUFD */
 
+void arm_smmu_setup_realm_irqs(struct arm_smmu_device *smmu);
+
 #endif /* _ARM_SMMU_V3_H */

---

## [3] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 02/16] iommu/arm-smmu-v3: Save the programmed MSI message in msi_desc*

Cache the MSI message in desc->msg from arm_smmu_write_msi_msg(). The
realm support code later reads the MSI address and data through
irq_get_msi_desc(), so it needs the descriptor to reflect the last
programmed message.

This matches the caching done by __pci_write_msi_msg().

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.c | 3 +++
 1 file changed, 3 insertions(+)

diff --git a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.c b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.c
index d5b9ab95beea..17fd99887aab 100644
--- a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.c
+++ b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.c
@@ -4012,6 +4012,9 @@ static void arm_smmu_write_msi_msg(struct msi_desc *desc, struct msi_msg *msg)
 	if (smmu->features & ARM_SMMU_FEAT_PRI)
 		max_config_index = PRIQ_MSI_INDEX;
 
+	/* save the programmed msi message details */
+	desc->msg = *msg;
+
 	/* Don't try to config for Realm interrupts. */
 	if (desc->msi_index > max_config_index)
 		return;

---

## [4] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 03/16] iommu/arm-smmu-v3: Add initial pSMMU realm viommu plumbing*

Add initial plumbing for Realm pSMMU integration in the arm-smmu-v3 iommufd
path.

Changes include:
- add RMI SMC IDs and helper wrappers for pSMMU activate and ST_L2 create/destroy
- add RMI pSMMU parameter structure definitions
- add IOMMU_VIOMMU_TYPE_ARM_REALM_SMMUV3 UAPI/internal type support
- add arm-smmu-v3 realm viommu init/vdevice hooks
- store SMMU MMIO physical base and realm initialization state in arm_smmu_device

This enables basic realm pSMMU setup and vdevice stream-table operations.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h             |   7 +
 arch/arm64/include/asm/rmi_smc.h              |  18 +++
 arch/arm64/kernel/rmi.c                       |  39 +++++
 .../arm/arm-smmu-v3/arm-smmu-v3-iommufd.c     |   7 +
 .../iommu/arm/arm-smmu-v3/arm-smmu-v3-realm.c | 148 ++++++++++++++++++
 drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.c   |   1 +
 drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.h   |   4 +
 include/uapi/linux/iommufd.h                  |   1 +
 8 files changed, 225 insertions(+)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 75eb59d4fa84..659d68ad5f1d 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -863,4 +863,11 @@ static inline unsigned long rmi_psmmu_event_consume(unsigned long psmmu_phys,
 	return res.a0;
 }
 
+int rmi_psmmu_activate(unsigned long psmmu_phys,
+	       unsigned long psmmu_params_phys, unsigned long *rmi_ret);
+int rmi_psmmu_st_l2_create(unsigned long psmmu_phys,
+		   unsigned long stream_id, unsigned long *rmi_ret);
+int rmi_psmmu_st_l2_destroy(unsigned long psmmu_phys,
+		    unsigned long stream_id, unsigned long *rmi_ret);
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index be1b1e95a937..5b540d25914e 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -625,4 +625,22 @@ struct rmi_psmmu_info {
 	};
 };
 
+#define RMI_PSMMU_FLAG_MSI	BIT(0)
+#define RMI_PSMMU_FLAG_ATS	BIT(1)
+#define RMI_PSMMU_FLAG_PRI	BIT(2)
+struct rmi_psmmu_params {
+	union {
+		struct {
+			u64 flags;
+			u64 grr_addr;
+			u64 grr_data;
+			u64 eventq_addr;
+			u64 eventq_data;
+			u64 priq_addr;
+			u64 priq_data;
+		};
+		u8 padding5[0x1000];
+	};
+};
+
 #endif /* __ASM_RMI_SMC_H */
diff --git a/arch/arm64/kernel/rmi.c b/arch/arm64/kernel/rmi.c
index da4707981548..cc4050db5a6a 100644
--- a/arch/arm64/kernel/rmi.c
+++ b/arch/arm64/kernel/rmi.c
@@ -423,6 +423,45 @@ unsigned long rmi_sro_execute(struct rmi_sro_state *sro)
 	return regs.a0;
 }
 
+int rmi_psmmu_activate(unsigned long psmmu_phys,
+	       unsigned long psmmu_params_phys, unsigned long *rmi_ret)
+{
+	struct rmi_sro_state *sro __free(sro) =
+		rmi_sro_init(SMC_RMI_PSMMU_ACTIVATE, psmmu_phys, psmmu_params_phys);
+	if (!sro)
+		return -ENOMEM;
+
+	*rmi_ret = rmi_sro_execute(sro);
+
+	return 0;
+}
+
+int rmi_psmmu_st_l2_create(unsigned long psmmu_phys,
+		   unsigned long stream_id, unsigned long *rmi_ret)
+{
+	struct rmi_sro_state *sro __free(sro) =
+		rmi_sro_init(SMC_RMI_PSMMU_ST_L2_CREATE, psmmu_phys, stream_id);
+	if (!sro)
+		return -ENOMEM;
+
+	*rmi_ret = rmi_sro_execute(sro);
+
+	return 0;
+}
+
+int rmi_psmmu_st_l2_destroy(unsigned long psmmu_phys,
+		    unsigned long stream_id, unsigned long *rmi_ret)
+{
+	struct rmi_sro_state *sro __free(sro) =
+		rmi_sro_init(SMC_RMI_PSMMU_ST_L2_DESTROY, psmmu_phys, stream_id);
+	if (!sro)
+		return -ENOMEM;
+
+	*rmi_ret = rmi_sro_execute(sro);
+
+	return 0;
+}
+
 static int rmi_configure(void)
 {
 	struct rmm_config *config __free(free_page) = NULL;
diff --git a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-iommufd.c b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-iommufd.c
index ddae0b07c76b..c98e91b3ca13 100644
--- a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-iommufd.c
+++ b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-iommufd.c
@@ -437,6 +437,9 @@ size_t arm_smmu_get_viommu_size(struct device *dev,
 	if (viommu_type == IOMMU_VIOMMU_TYPE_ARM_SMMUV3)
 		return VIOMMU_STRUCT_SIZE(struct arm_vsmmu, core);
 
+	if (viommu_type == IOMMU_VIOMMU_TYPE_ARM_REALM_SMMUV3)
+		return VIOMMU_STRUCT_SIZE(struct arm_vsmmu, core);
+
 	if (!smmu->impl_ops || !smmu->impl_ops->get_viommu_size)
 		return 0;
 	return smmu->impl_ops->get_viommu_size(viommu_type);
@@ -464,6 +467,10 @@ int arm_vsmmu_init(struct iommufd_viommu *viommu,
 		return 0;
 	}
 
+	if (viommu->type == IOMMU_VIOMMU_TYPE_ARM_REALM_SMMUV3)
+		return arm_realm_smmu_v3_init(viommu, user_data);
+
+
 	return smmu->impl_ops->vsmmu_init(vsmmu, user_data);
 }
 
diff --git a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-realm.c b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-realm.c
index fec1a32de53c..6f8de7cead9d 100644
--- a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-realm.c
+++ b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-realm.c
@@ -6,6 +6,7 @@
 #include <linux/interrupt.h>
 #include <asm/rmi_smc.h>
 #include <asm/rmi_cmds.h>
+#include <asm/kvm_emulate.h>
 
 #include "arm-smmu-v3.h"
 
@@ -122,3 +123,150 @@ void arm_smmu_setup_realm_irqs(struct arm_smmu_device *smmu)
 		}
 	}
 }
+
+static void arm_realm_smmu_v3_destroy(struct iommufd_viommu *viommu)
+{
+	/* When we add refcount psmmu deactivate here. */
+}
+
+static void arm_realm_smmu_v3_vdevice_destroy(struct iommufd_vdevice *vdev)
+{
+	struct device *dev = iommufd_vdevice_to_device(vdev);
+	struct arm_smmu_master *master = dev_iommu_priv_get(dev);
+	/* FIXME which stream to pick */
+	/* At this moment, iommufd only supports PCI device that has one SID */
+	struct arm_smmu_stream *stream = &master->streams[0];
+	struct arm_smmu_device *smmu = master->smmu;
+	unsigned long rmi_ret = 0;
+	int ret;
+
+	if (!smmu->realm_initialized)
+		return;
+
+	ret = rmi_psmmu_st_l2_destroy(smmu->base_phys,
+				    ALIGN_DOWN(stream->id, STRTAB_NUM_L2_STES),
+				      &rmi_ret);
+	if (ret || rmi_ret) {
+
+		/* Table in use */
+		if (RMI_RETURN_STATUS(rmi_ret) == RMI_ERROR_PSMMU_ST &&
+		    RMI_RETURN_INDEX(rmi_ret) == 2)
+			return;
+
+		dev_warn(dev, "failed to destroy realm stream mapping\n");
+	}
+}
+
+static int arm_realm_smmu_v3_vdevice_init(struct iommufd_vdevice *vdev)
+{
+	struct device *dev = iommufd_vdevice_to_device(vdev);
+	struct arm_smmu_master *master = dev_iommu_priv_get(dev);
+	// fixme which stream to pick
+	/* At this moment, iommufd only supports PCI device that has one SID */
+	struct arm_smmu_stream *stream = &master->streams[0];
+	struct arm_smmu_device *smmu = master->smmu;
+	unsigned long rmi_ret = 0;
+	int ret;
+
+	if (!smmu->realm_initialized)
+		return -EINVAL;
+
+	ret = rmi_psmmu_st_l2_create(smmu->base_phys,
+				     ALIGN_DOWN(stream->id, STRTAB_NUM_L2_STES),
+				     &rmi_ret);
+	if (ret || rmi_ret) {
+		if (!ret)
+			return -EIO;
+		if (RMI_RETURN_STATUS(rmi_ret) == RMI_ERROR_PSMMU_ST &&
+		    RMI_RETURN_INDEX(rmi_ret) == 2) {
+			/* table already exist */
+			vdev->destroy = arm_realm_smmu_v3_vdevice_destroy;
+			return 0;
+		}
+		dev_warn(dev, "failed to create realm stream mapping\n");
+		return -EIO;
+	}
+	vdev->destroy = arm_realm_smmu_v3_vdevice_destroy;
+	return 0;
+}
+
+static const struct iommufd_viommu_ops arm_realm_smmu_v3_ops = {
+	.destroy = arm_realm_smmu_v3_destroy,
+	.alloc_domain_nested = arm_vsmmu_alloc_domain_nested,
+	.cache_invalidate = arm_vsmmu_cache_invalidate,
+	.vdevice_init = arm_realm_smmu_v3_vdevice_init,
+};
+
+static int get_irq_data(int irq, u64 *msi_addr, u64 *msi_data)
+{
+	struct msi_desc *desc;
+
+	desc = irq_get_msi_desc(irq);
+	if (!desc)
+		return -EINVAL;
+
+	*msi_addr = (((u64)desc->msg.address_hi) << 32) | desc->msg.address_lo;
+	*msi_data = desc->msg.data;
+	return 0;
+}
+
+int arm_realm_smmu_v3_init(struct iommufd_viommu *viommu,
+			   const struct iommu_user_data *user_data)
+{
+	int ret = 0;
+	struct kvm *kvm = viommu->kvm;
+	struct rmi_psmmu_params *params;
+	struct arm_smmu_device *smmu =
+		container_of(viommu->iommu_dev, struct arm_smmu_device, iommu);
+	unsigned long rmi_ret;
+
+	if (!kvm)
+		return -EINVAL;
+
+	if (!kvm_is_realm(kvm))
+		return -EINVAL;
+
+	if (!(smmu->features & ARM_SMMU_FEAT_RME))
+		return -EOPNOTSUPP;
+
+	if (smmu->realm_initialized)
+		goto psmmu_already_active;
+
+	params = (struct rmi_psmmu_params *)get_zeroed_page(GFP_KERNEL);
+	if (!params)
+		return -ENOMEM;
+
+	/* No ATS and PRI support */
+	if (!(smmu->features & ARM_SMMU_FEAT_MSI))
+		goto psmmu_activate;
+
+	params->flags = RMI_PSMMU_FLAG_MSI;
+	if (get_irq_data(smmu->realm_gerr_irq,
+			 &params->grr_addr, &params->grr_data)) {
+		ret = -EINVAL;
+		goto out_free;
+	}
+	if (get_irq_data(smmu->realm_evtq_irq,
+			 &params->eventq_addr, &params->eventq_data)) {
+		ret = -EINVAL;
+		goto out_free;
+	}
+
+psmmu_activate:
+	ret = rmi_psmmu_activate(smmu->base_phys, virt_to_phys(params),
+				 &rmi_ret);
+	if (ret || rmi_ret) {
+		if (!ret)
+			ret = -EIO;
+		dev_warn(smmu->dev, "failed to activate realm pSMMU\n");
+		ret = -EIO;
+	} else {
+		smmu->realm_initialized = true;
+	}
+out_free:
+	free_page((unsigned long)params);
+psmmu_already_active:
+	if (!ret)
+		viommu->ops = &arm_realm_smmu_v3_ops;
+	return ret;
+}
diff --git a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.c b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.c
index 17fd99887aab..1e3d4d682e32 100644
--- a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.c
+++ b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.c
@@ -3956,6 +3956,7 @@ static int arm_smmu_init_structures(struct arm_smmu_device *smmu)
 	if (ret)
 		return ret;
 
+	smmu->realm_initialized = false;
 	if (smmu->impl_ops && smmu->impl_ops->init_structures)
 		return smmu->impl_ops->init_structures(smmu);
 
diff --git a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.h b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.h
index 6680516b571b..d528b3212d38 100644
--- a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.h
+++ b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.h
@@ -811,6 +811,8 @@ struct arm_smmu_device {
 
 	struct rb_root			streams;
 	struct mutex			streams_mutex;
+
+	bool realm_initialized;
 };
 
 struct arm_smmu_stream {
@@ -1073,6 +1075,8 @@ arm_vsmmu_alloc_domain_nested(struct iommufd_viommu *viommu, u32 flags,
 			      const struct iommu_user_data *user_data);
 int arm_vsmmu_cache_invalidate(struct iommufd_viommu *viommu,
 			       struct iommu_user_data_array *array);
+int arm_realm_smmu_v3_init(struct iommufd_viommu *viommu,
+			   const struct iommu_user_data *user_data);
 #else
 #define arm_smmu_get_viommu_size NULL
 #define arm_smmu_hw_info NULL
diff --git a/include/uapi/linux/iommufd.h b/include/uapi/linux/iommufd.h
index 47213663c0c1..74afc9967c3e 100644
--- a/include/uapi/linux/iommufd.h
+++ b/include/uapi/linux/iommufd.h
@@ -1055,6 +1055,7 @@ enum iommu_viommu_type {
 	IOMMU_VIOMMU_TYPE_DEFAULT = 0,
 	IOMMU_VIOMMU_TYPE_ARM_SMMUV3 = 1,
 	IOMMU_VIOMMU_TYPE_TEGRA241_CMDQV = 2,
+	IOMMU_VIOMMU_TYPE_ARM_REALM_SMMUV3 = 3,
 };
 
 /**

---

## [5] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 04/16] iommu/arm-smmu-v3: Track realm pSMMU users with refcount_t*

Replace the realm pSMMU active-state boolean with a refcount so
activation/deactivation is tied to actual Realm vIOMMU lifetime.

- add realm_mutex and realm_users (refcount_t) to struct arm_smmu_device
- on first Realm init, activate pSMMU and set realm_users to 1
- on subsequent Realm inits, increment realm_users
- on Realm viommu destroy, decrement realm_users and call
  rmi_psmmu_deactivate() when the last user drops the count to 0

This removes duplicated state tracking and ensures pSMMU is deactivated only
after the last Realm user is gone.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h             |  1 +
 arch/arm64/kernel/rmi.c                       | 12 ++++++
 .../iommu/arm/arm-smmu-v3/arm-smmu-v3-realm.c | 39 +++++++++++++++----
 drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.c   |  3 +-
 drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.h   |  4 +-
 5 files changed, 50 insertions(+), 9 deletions(-)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 659d68ad5f1d..205fc200d1db 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -865,6 +865,7 @@ static inline unsigned long rmi_psmmu_event_consume(unsigned long psmmu_phys,
 
 int rmi_psmmu_activate(unsigned long psmmu_phys,
 	       unsigned long psmmu_params_phys, unsigned long *rmi_ret);
+int rmi_psmmu_deactivate(unsigned long psmmu_phys, unsigned long *rmi_ret);
 int rmi_psmmu_st_l2_create(unsigned long psmmu_phys,
 		   unsigned long stream_id, unsigned long *rmi_ret);
 int rmi_psmmu_st_l2_destroy(unsigned long psmmu_phys,
diff --git a/arch/arm64/kernel/rmi.c b/arch/arm64/kernel/rmi.c
index cc4050db5a6a..884ab3f99f2f 100644
--- a/arch/arm64/kernel/rmi.c
+++ b/arch/arm64/kernel/rmi.c
@@ -436,6 +436,18 @@ int rmi_psmmu_activate(unsigned long psmmu_phys,
 	return 0;
 }
 
+int rmi_psmmu_deactivate(unsigned long psmmu_phys, unsigned long *rmi_ret)
+{
+	struct rmi_sro_state *sro __free(sro) =
+		rmi_sro_init(SMC_RMI_PSMMU_DEACTIVATE, psmmu_phys);
+	if (!sro)
+		return -ENOMEM;
+
+	*rmi_ret = rmi_sro_execute(sro);
+
+	return 0;
+}
+
 int rmi_psmmu_st_l2_create(unsigned long psmmu_phys,
 		   unsigned long stream_id, unsigned long *rmi_ret)
 {
diff --git a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-realm.c b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-realm.c
index 6f8de7cead9d..dfff493f96d0 100644
--- a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-realm.c
+++ b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3-realm.c
@@ -124,9 +124,25 @@ void arm_smmu_setup_realm_irqs(struct arm_smmu_device *smmu)
 	}
 }
 
+static bool arm_realm_smmu_active(struct arm_smmu_device *smmu)
+{
+	lockdep_assert_held(&smmu->realm_mutex);
+	return refcount_read(&smmu->realm_users) > 0;
+}
+
 static void arm_realm_smmu_v3_destroy(struct iommufd_viommu *viommu)
 {
-	/* When we add refcount psmmu deactivate here. */
+	unsigned long rmi_ret;
+	struct arm_smmu_device *smmu =
+		container_of(viommu->iommu_dev, struct arm_smmu_device, iommu);
+
+	guard(mutex)(&smmu->realm_mutex);
+	if (WARN_ON(!arm_realm_smmu_active(smmu)))
+		return;
+
+	if (refcount_dec_and_test(&smmu->realm_users) &&
+	    (rmi_psmmu_deactivate(smmu->base_phys, &rmi_ret) || rmi_ret))
+		dev_warn(smmu->dev, "failed to deactivate realm pSMMU\n");
 }
 
 static void arm_realm_smmu_v3_vdevice_destroy(struct iommufd_vdevice *vdev)
@@ -140,7 +156,8 @@ static void arm_realm_smmu_v3_vdevice_destroy(struct iommufd_vdevice *vdev)
 	unsigned long rmi_ret = 0;
 	int ret;
 
-	if (!smmu->realm_initialized)
+	guard(mutex)(&smmu->realm_mutex);
+	if (!arm_realm_smmu_active(smmu))
 		return;
 
 	ret = rmi_psmmu_st_l2_destroy(smmu->base_phys,
@@ -168,7 +185,8 @@ static int arm_realm_smmu_v3_vdevice_init(struct iommufd_vdevice *vdev)
 	unsigned long rmi_ret = 0;
 	int ret;
 
-	if (!smmu->realm_initialized)
+	guard(mutex)(&smmu->realm_mutex);
+	if (!arm_realm_smmu_active(smmu))
 		return -EINVAL;
 
 	ret = rmi_psmmu_st_l2_create(smmu->base_phys,
@@ -229,12 +247,17 @@ int arm_realm_smmu_v3_init(struct iommufd_viommu *viommu,
 	if (!(smmu->features & ARM_SMMU_FEAT_RME))
 		return -EOPNOTSUPP;
 
-	if (smmu->realm_initialized)
+	mutex_lock(&smmu->realm_mutex);
+	if (arm_realm_smmu_active(smmu)) {
+		refcount_inc(&smmu->realm_users);
 		goto psmmu_already_active;
+	}
 
 	params = (struct rmi_psmmu_params *)get_zeroed_page(GFP_KERNEL);
-	if (!params)
-		return -ENOMEM;
+	if (!params) {
+		ret = -ENOMEM;
+		goto out_unlock;
+	}
 
 	/* No ATS and PRI support */
 	if (!(smmu->features & ARM_SMMU_FEAT_MSI))
@@ -261,12 +284,14 @@ int arm_realm_smmu_v3_init(struct iommufd_viommu *viommu,
 		dev_warn(smmu->dev, "failed to activate realm pSMMU\n");
 		ret = -EIO;
 	} else {
-		smmu->realm_initialized = true;
+		refcount_set(&smmu->realm_users, 1);
 	}
 out_free:
 	free_page((unsigned long)params);
 psmmu_already_active:
 	if (!ret)
 		viommu->ops = &arm_realm_smmu_v3_ops;
+out_unlock:
+	mutex_unlock(&smmu->realm_mutex);
 	return ret;
 }
diff --git a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.c b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.c
index 1e3d4d682e32..e458c3818c34 100644
--- a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.c
+++ b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.c
@@ -3946,6 +3946,8 @@ static int arm_smmu_init_structures(struct arm_smmu_device *smmu)
 	int ret;
 
 	mutex_init(&smmu->streams_mutex);
+	mutex_init(&smmu->realm_mutex);
+	refcount_set(&smmu->realm_users, 0);
 	smmu->streams = RB_ROOT;
 
 	ret = arm_smmu_init_queues(smmu);
@@ -3956,7 +3958,6 @@ static int arm_smmu_init_structures(struct arm_smmu_device *smmu)
 	if (ret)
 		return ret;
 
-	smmu->realm_initialized = false;
 	if (smmu->impl_ops && smmu->impl_ops->init_structures)
 		return smmu->impl_ops->init_structures(smmu);
 
diff --git a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.h b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.h
index d528b3212d38..b5d0e1341236 100644
--- a/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.h
+++ b/drivers/iommu/arm/arm-smmu-v3/arm-smmu-v3.h
@@ -13,6 +13,7 @@
 #include <linux/iommufd.h>
 #include <linux/kernel.h>
 #include <linux/mmzone.h>
+#include <linux/refcount.h>
 #include <linux/sizes.h>
 
 struct arm_smmu_device;
@@ -812,7 +813,8 @@ struct arm_smmu_device {
 	struct rb_root			streams;
 	struct mutex			streams_mutex;
 
-	bool realm_initialized;
+	struct mutex			realm_mutex;
+	refcount_t			realm_users;
 };
 
 struct arm_smmu_stream {

---

## [6] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 05/16] coco: host: arm64: Add support for virtual device communication*

Add support for vdev_communicate with RMM.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h       | 32 ++++++++++
 arch/arm64/include/asm/rmi_smc.h        |  7 +++
 drivers/virt/coco/arm-cca-host/rmi-da.c | 83 ++++++++++++++++++++++---
 drivers/virt/coco/arm-cca-host/rmi-da.h | 20 ++++++
 4 files changed, 135 insertions(+), 7 deletions(-)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 205fc200d1db..2925abde3882 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -871,4 +871,36 @@ int rmi_psmmu_st_l2_create(unsigned long psmmu_phys,
 int rmi_psmmu_st_l2_destroy(unsigned long psmmu_phys,
 		    unsigned long stream_id, unsigned long *rmi_ret);
 
+static inline unsigned long rmi_vdev_communicate(unsigned long rd_phys,
+		unsigned long pdev_phys, unsigned long vdev_phys,
+		unsigned long vdev_comm_data_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_COMMUNICATE, rd_phys, pdev_phys,
+			     vdev_phys, vdev_comm_data_phys, &res);
+
+	return res.a0;
+}
+
+static inline unsigned long rmi_vdev_get_state(unsigned long vdev_phys,
+		enum rmi_vdev_state *state)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_GET_STATE, vdev_phys, &res);
+
+	*state = res.a1;
+	return res.a0;
+}
+
+static inline unsigned long rmi_vdev_abort(unsigned long vdev_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_ABORT, vdev_phys, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 5b540d25914e..72e4a53b74b0 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -643,4 +643,11 @@ struct rmi_psmmu_params {
 	};
 };
 
+enum rmi_vdev_state {
+	RMI_VDEV_NEW,
+	RMI_VDEV_UNLOCKED,
+	RMI_VDEV_LOCKED,
+	RMI_VDEV_STARTED,
+	RMI_VDEV_ERROR,
+};
 #endif /* __ASM_RMI_SMC_H */
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index 33a2551fd09f..d61c3191c038 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -11,6 +11,8 @@
 #include <crypto/internal/rsa.h>
 #include <keys/asymmetric-type.h>
 #include <keys/x509-parser.h>
+#include <linux/kvm_types.h>
+#include <asm/kvm_rmi.h>
 
 #include "rmi-da.h"
 
@@ -217,6 +219,7 @@ static int _do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm, int
 	gfp_t cache_alloc_flags;
 	int nbytes, cp_len;
 	struct cache_object **cache_objp, *cache_obj;
+	struct cca_host_tdi *host_tdi = to_cca_host_tdi(tsm->pdev);
 	struct cca_host_pdev_dsc *pdev_dsc = to_cca_pdev_dsc(tsm->dsm_dev);
 	struct cca_host_comm_data *comm_data = to_cca_comm_data(tsm->pdev);
 	struct rmi_dev_comm_enter *io_enter = &comm_data->io_params->enter;
@@ -228,7 +231,10 @@ static int _do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm, int
 		rmi_ret = rmi_pdev_communicate(virt_to_phys(pdev_dsc->rmm_pdev),
 					       virt_to_phys(comm_data->io_params));
 	else
-		rmi_ret = RMI_ERROR_INPUT;
+		rmi_ret = rmi_vdev_communicate(virt_to_phys(host_tdi->realm->rd),
+					       virt_to_phys(pdev_dsc->rmm_pdev),
+					       virt_to_phys(host_tdi->rmm_vdev),
+					       virt_to_phys(comm_data->io_params));
 	if (rmi_ret != RMI_SUCCESS) {
 		if (rmi_ret == RMI_BUSY)
 			return -EBUSY;
@@ -252,6 +258,12 @@ static int _do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm, int
 		case RMI_DEV_CERTIFICATE:
 			cache_objp = &pf0_ep_dsc->cert_chain.cache;
 			break;
+		case RMI_DEV_INTERFACE_REPORT:
+			cache_objp = &host_tdi->interface_report;
+			break;
+		case RMI_DEV_MEASUREMENTS:
+			cache_objp = &host_tdi->measurements;
+			break;
 		default:
 			return -EINVAL;
 		}
@@ -355,9 +367,11 @@ static int _do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm, int
 static int do_dev_communicate(enum dev_comm_type type,
 		struct pci_tsm *tsm, unsigned long error_state, int *stream_wait)
 {
-	int ret, state = error_state;
+	int ret, state;
+	unsigned long rmi_ret;
 	struct rmi_dev_comm_enter *io_enter;
 	struct cca_host_pdev_dsc *pdev_dsc = to_cca_pdev_dsc(tsm->dsm_dev);
+	struct cca_host_tdi *host_tdi = to_cca_host_tdi(tsm->pdev);
 
 	io_enter = &pdev_dsc->comm_data.io_params->enter;
 	io_enter->resp_len = 0;
@@ -369,16 +383,23 @@ static int do_dev_communicate(enum dev_comm_type type,
 	if (ret) {
 		if (type == PDEV_COMMUNICATE)
 			rmi_pdev_abort(virt_to_phys(pdev_dsc->rmm_pdev));
+		else
+			rmi_vdev_abort(virt_to_phys(host_tdi->rmm_vdev));
+
+		state = error_state;
 	} else {
 		/*
 		 * Some device communication error will transition the
 		 * device to error state. Report that.
 		 */
-		if (type == PDEV_COMMUNICATE) {
-			if (rmi_pdev_get_state(virt_to_phys(pdev_dsc->rmm_pdev),
-					       (enum rmi_pdev_state *)&state))
-				state = error_state;
-		}
+		if (type == PDEV_COMMUNICATE)
+			rmi_ret = rmi_pdev_get_state(virt_to_phys(pdev_dsc->rmm_pdev),
+						     (enum rmi_pdev_state *)&state);
+		else
+			rmi_ret = rmi_vdev_get_state(virt_to_phys(host_tdi->rmm_vdev),
+						     (enum rmi_vdev_state *)&state);
+		if (rmi_ret)
+			state = error_state;
 	}
 
 	if (state == error_state)
@@ -408,6 +429,11 @@ static int wait_for_pdev_state(struct pci_tsm *tsm, enum rmi_pdev_state target_s
 	return wait_for_dev_state(PDEV_COMMUNICATE, tsm, target_state, RMI_PDEV_ERROR);
 }
 
+static int wait_for_vdev_state(struct pci_tsm *tsm, enum rmi_vdev_state target_state)
+{
+	return wait_for_dev_state(VDEV_COMMUNICATE, tsm, target_state, RMI_VDEV_ERROR);
+}
+
 static int parse_certificate_chain(struct pci_tsm *tsm)
 {
 	struct cca_host_pf0_ep_dsc *pf0_ep_dsc;
@@ -603,6 +629,49 @@ static int submit_pdev_state_transition_work(struct pci_dev *pdev,
 	return 0;
 }
 
+static void vdev_state_transition_workfn(struct work_struct *work)
+{
+	unsigned long state;
+	struct pci_tsm *tsm;
+	struct dev_comm_work *setup_work;
+	struct cca_host_pdev_dsc *pdev_dsc;
+
+	setup_work = container_of(work, struct dev_comm_work, work);
+	tsm = setup_work->tsm;
+
+	pdev_dsc = to_cca_pdev_dsc(tsm->dsm_dev);
+	guard(mutex)(&pdev_dsc->object_lock);
+
+	state = wait_for_vdev_state(tsm, setup_work->target_state);
+	WARN_ON(state != setup_work->target_state);
+}
+
+static int __maybe_unused submit_vdev_state_transition_work(struct pci_dev *pdev, int target_state)
+{
+	enum rmi_vdev_state state;
+	struct dev_comm_work comm_work;
+	struct cca_host_comm_data *comm_data = to_cca_comm_data(pdev);
+	struct cca_host_tdi *host_tdi = to_cca_host_tdi(pdev);
+
+	INIT_WORK_ONSTACK(&comm_work.work, vdev_state_transition_workfn);
+	comm_work.tsm = pdev->tsm;
+	comm_work.target_state = target_state;
+
+	queue_work(comm_data->work_queue, &comm_work.work);
+
+	flush_work(&comm_work.work);
+	destroy_work_on_stack(&comm_work.work);
+
+	/* check if we reached target state */
+	if (rmi_vdev_get_state(virt_to_phys(host_tdi->rmm_vdev), &state))
+		return -ENXIO;
+
+	if (state != target_state)
+		/* Protocol didn't take it to expected target state */
+		return -EPROTO;
+	return 0;
+}
+
 static void pdev_collect_identity_workfn(struct work_struct *work)
 {
 	struct pci_tsm *tsm;
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index 798a8ed7505f..88fa428f788e 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -116,6 +116,16 @@ struct cca_host_fn_dsc {
 
 enum dev_comm_type {
 	PDEV_COMMUNICATE = 0x1,
+	VDEV_COMMUNICATE = 0x2,
+};
+
+struct cca_host_tdi {
+	struct pci_tdi tdi;
+	struct realm *realm;
+	void *rmm_vdev;
+	/* protected by cca_host_pdev_dsc.object_lock */
+	struct cache_object *interface_report;
+	struct cache_object *measurements;
 };
 
 static inline int insert_addr_range_sorted(struct rmi_addr_range *addr_range,
@@ -203,6 +213,16 @@ static inline struct cca_host_comm_data *to_cca_comm_data(struct pci_dev *pdev)
 	return NULL;
 }
 
+static inline struct cca_host_tdi *to_cca_host_tdi(struct pci_dev *pdev)
+{
+	struct pci_tsm *tsm = pdev->tsm;
+
+	if (!tsm || !tsm->tdi)
+		return NULL;
+
+	return container_of(tsm->tdi, struct cca_host_tdi, tdi);
+}
+
 int cca_pdev_create(struct pci_dev *pdev);
 int cca_pdev_collect_identity(struct pci_dev *pdev);
 bool cca_pdev_needs_key(struct pci_dev *pdev);

---

## [7] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 06/16] coco: host: arm64: Add support for RMM vdev objects*

An RMM vdev object represents the binding between a device function and
a Realm. For example, a vdev can represent a physical function of a PCIe
device or a virtual function of a multi-function PCIe device. Each vdev
is associated with one pdev.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h        |  22 +++++
 arch/arm64/include/asm/rmi_smc.h         |  22 +++++
 drivers/virt/coco/arm-cca-host/arm-cca.c |  27 +++++-
 drivers/virt/coco/arm-cca-host/rmi-da.c  | 104 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.h  |   2 +
 5 files changed, 176 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 2925abde3882..242ce2fac14e 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -903,4 +903,26 @@ static inline unsigned long rmi_vdev_abort(unsigned long vdev_phys)
 	return res.a0;
 }
 
+static inline unsigned long rmi_vdev_create(unsigned long rd,
+		unsigned long pdev_phys, unsigned long vdev_phys,
+		unsigned long vdev_params_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_CREATE, rd, pdev_phys,
+			     vdev_phys, vdev_params_phys, &res);
+
+	return res.a0;
+}
+
+static inline unsigned long rmi_vdev_lock(unsigned long rd,
+		unsigned long pdev_phys, unsigned long vdev_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_LOCK, rd, pdev_phys, vdev_phys, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 72e4a53b74b0..d14d13a9f169 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -650,4 +650,26 @@ enum rmi_vdev_state {
 	RMI_VDEV_STARTED,
 	RMI_VDEV_ERROR,
 };
+
+#define MAX_VDEV_ADDR_RANGE 8
+
+struct rmi_vdev_params {
+	union {
+		struct {
+			u64 flags;
+			u64 vdev_id;
+			u64 tdi_id;
+			u64 padding1;
+			u64 vsmmu_addr;
+			u64 vsid;
+			u64 num_addr_range;
+		};
+		u8 padding2[0x200];
+	};
+	union { /* 0x200 */
+		struct rmi_addr_range addr_range[MAX_VDEV_ADDR_RANGE];
+		u8 padding3[0x1000 - 0x200];
+	};
+};
+
 #endif /* __ASM_RMI_SMC_H */
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index 8b1182620872..5930a30dd16f 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -12,7 +12,8 @@
 #include <linux/vmalloc.h>
 #include <linux/cleanup.h>
 #include <linux/pci-doe.h>
-
+#include <linux/pci.h>
+#include <linux/kvm_host.h>
 
 #include "rmi-da.h"
 
@@ -449,11 +450,35 @@ static void cca_tsm_disconnect(struct pci_dev *pdev)
 	}
 }
 
+static struct pci_tdi *cca_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u32 tdi_id)
+{
+	void *rmm_vdev;
+	struct pci_dev *dsm_dev = pdev->tsm->dsm_dev;
+	struct realm *realm = &kvm->arch.realm;
+
+	struct cca_host_tdi *host_tdi __free(kfree) =
+		kzalloc(sizeof(struct cca_host_tdi), GFP_KERNEL);
+	if (!host_tdi)
+		return ERR_PTR(-ENOMEM);
+
+	pci_tsm_tdi_constructor(pdev, &host_tdi->tdi, kvm, tdi_id);
+	/* Assign the tdi such that vdev_create can use that to lookup */
+	pdev->tsm->tdi = &host_tdi->tdi;
+	rmm_vdev = cca_vdev_create(realm, pdev, dsm_dev, tdi_id);
+	if (IS_ERR_OR_NULL(rmm_vdev)) {
+		pdev->tsm->tdi = NULL;
+		return rmm_vdev;
+	}
+
+	return &no_free_ptr(host_tdi)->tdi;
+}
+
 static struct pci_tsm_ops cca_link_pci_ops = {
 	.probe = cca_tsm_pci_probe,
 	.remove = cca_tsm_pci_remove,
 	.connect = cca_tsm_connect,
 	.disconnect = cca_tsm_disconnect,
+	.bind = cca_tsm_bind,
 };
 
 static void cca_link_tsm_remove(void *tsm_dev)
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index d61c3191c038..84f0b2211cd1 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -934,3 +934,107 @@ int cca_pdev_disconnect_stream(struct pci_dev *pdev1,
 
 	return submit_stream_work(pdev1, pdev2, stream_handle);
 }
+
+static unsigned long pci_get_tdi_id(struct pci_dev *pdev)
+{
+	/* requester segment is marked reserved. */
+	return pci_dev_id(pdev);
+}
+
+static void init_vdev_params_mmio_range(struct pci_dev *pdev,
+		struct rmi_vdev_params *params)
+{
+	int index = 0;
+
+	for (int i = 0; i < PCI_STD_NUM_BARS; i++) {
+		struct resource *res = &pdev->resource[i];
+
+		if (!(res->flags & IORESOURCE_MEM))
+			continue;
+
+		if (resource_size(res) == 0)
+			continue;
+
+		index = insert_addr_range_sorted(params->addr_range, index,
+						 res->start, res->end + 1);
+	}
+
+	params->num_addr_range = index;
+}
+
+
+void *cca_vdev_create(struct realm *realm, struct pci_dev *pdev,
+		struct pci_dev *pf0_dev, u32 guest_rid)
+{
+	phys_addr_t rd_phys = virt_to_phys(realm->rd);
+	struct rmi_vdev_params *params = NULL;
+	struct cca_host_pdev_dsc *pdev_dsc;
+	struct cca_host_tdi *host_tdi;
+	phys_addr_t rmm_pdev_phys;
+	phys_addr_t rmm_vdev_phys;
+	bool should_free = true;
+	void *rmm_vdev;
+	int ret;
+
+	pdev_dsc = to_cca_pdev_dsc(pf0_dev);
+	if (!pdev_dsc->rmm_pdev) {
+		ret = -EINVAL;
+		goto err_out;
+	}
+
+	rmm_vdev = (void *)get_zeroed_page(GFP_KERNEL);
+	if (!rmm_vdev) {
+		ret =  -ENOMEM;
+		goto err_out;
+	}
+
+	rmm_vdev_phys = virt_to_phys(rmm_vdev);
+	if (rmi_delegate_page(rmm_vdev_phys)) {
+		ret = -ENXIO;
+		goto err_granule_delegate;
+	}
+
+	params = (struct rmi_vdev_params *)get_zeroed_page(GFP_KERNEL);
+	if (!params) {
+		ret = -ENOMEM;
+		goto err_params_alloc;
+	}
+
+	params->flags = 0;
+	params->vdev_id = guest_rid;
+	params->tdi_id = pci_get_tdi_id(pdev);
+
+	init_vdev_params_mmio_range(pdev, params);
+
+	rmm_pdev_phys = virt_to_phys(pdev_dsc->rmm_pdev);
+	if (rmi_vdev_create(rd_phys, rmm_pdev_phys,
+			    rmm_vdev_phys, virt_to_phys(params))) {
+		ret = -ENXIO;
+		goto err_vdev_create;
+	}
+
+	/* setup host_tdi before call to device communicate */
+	host_tdi = to_cca_host_tdi(pdev);
+	host_tdi->rmm_vdev = rmm_vdev;
+	host_tdi->realm = realm;
+
+	submit_vdev_state_transition_work(pdev, RMI_VDEV_UNLOCKED);
+
+	ret = rmi_vdev_lock(rd_phys, rmm_pdev_phys, rmm_vdev_phys);
+
+	submit_vdev_state_transition_work(pdev, RMI_VDEV_LOCKED);
+
+	free_page((unsigned long)params);
+	return rmm_vdev;
+
+err_vdev_create:
+	free_page((unsigned long)params);
+err_params_alloc:
+	if (rmi_undelegate_page(rmm_vdev_phys))
+		should_free = false;
+err_granule_delegate:
+	if (should_free)
+		free_page((unsigned long)rmm_vdev);
+err_out:
+	return ERR_PTR(ret);
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index 88fa428f788e..cd13cbf650d5 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -233,5 +233,7 @@ int cca_pdev_stream_connect(struct pci_dev *pdev1, struct pci_dev *pdev2,
 		unsigned long *stream_handle);
 int cca_pdev_disconnect_stream(struct pci_dev *pdev1,
 		struct pci_dev *pdev2, unsigned long stream_handle);
+void *cca_vdev_create(struct realm *realm, struct pci_dev *pdev,
+		struct pci_dev *pf0_dev, u32 guest_rid);
 
 #endif

---

## [8] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 07/16] coco: host: arm64: Add pdev stream key refresh and purge helpers*

Add RMI command wrappers for PDEV stream key refresh and key purge,
and plumb them into arm-cca host helper functions.

The new helpers follow the existing stream operation pattern: issue the
RMI command for the local and optional peer pdev, then run the shared
stream synchronization work before returning.

This prepares the arm-cca host code to refresh or purge stream keys
during later vdev and stream state transitions.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h       | 24 +++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.c | 35 +++++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.h |  4 +++
 3 files changed, 63 insertions(+)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 242ce2fac14e..03dffba763e1 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -925,4 +925,28 @@ static inline unsigned long rmi_vdev_lock(unsigned long rd,
 	return res.a0;
 }
 
+static inline unsigned long rmi_pdev_stream_key_refresh(unsigned long pdev1_phys,
+		unsigned long pdev2_phys, unsigned long stream_handle)
+{
+
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_STREAM_KEY_REFRESH, pdev1_phys,
+			     pdev2_phys, stream_handle, &res);
+
+	return res.a0;
+}
+
+static inline unsigned long rmi_pdev_stream_key_purge(unsigned long pdev1_phys,
+		unsigned long pdev2_phys, unsigned long stream_handle)
+{
+
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_STREAM_KEY_PURGE, pdev1_phys,
+			     pdev2_phys, stream_handle, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index 84f0b2211cd1..128079d5b993 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -1038,3 +1038,38 @@ void *cca_vdev_create(struct realm *realm, struct pci_dev *pdev,
 err_out:
 	return ERR_PTR(ret);
 }
+
+int cca_pdev_refresh_stream_key(struct pci_dev *pdev1,
+		struct pci_dev *pdev2, unsigned long stream_handle)
+{
+
+	phys_addr_t rmm_pdev2_phys = 0;
+	struct cca_host_pdev_dsc *pdev_dsc1 = to_cca_pdev_dsc(pdev1);
+
+	if (pdev2)
+		rmm_pdev2_phys = virt_to_phys(to_cca_pdev_dsc(pdev2)->rmm_pdev);
+
+	if (rmi_pdev_stream_key_refresh(virt_to_phys(pdev_dsc1->rmm_pdev),
+					rmm_pdev2_phys, stream_handle))
+		return -EIO;
+
+	return submit_stream_work(pdev1, pdev2, stream_handle);
+}
+
+
+int cca_pdev_purge_stream_key(struct pci_dev *pdev1,
+		struct pci_dev *pdev2, unsigned long stream_handle)
+{
+
+	phys_addr_t rmm_pdev2_phys = 0;
+	struct cca_host_pdev_dsc *pdev_dsc1 = to_cca_pdev_dsc(pdev1);
+
+	if (pdev2)
+		rmm_pdev2_phys = virt_to_phys(to_cca_pdev_dsc(pdev2)->rmm_pdev);
+
+	if (rmi_pdev_stream_key_purge(virt_to_phys(pdev_dsc1->rmm_pdev),
+				      rmm_pdev2_phys, stream_handle))
+		return -EIO;
+
+	return submit_stream_work(pdev1, pdev2, stream_handle);
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index cd13cbf650d5..d6cdbc638d6d 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -235,5 +235,9 @@ int cca_pdev_disconnect_stream(struct pci_dev *pdev1,
 		struct pci_dev *pdev2, unsigned long stream_handle);
 void *cca_vdev_create(struct realm *realm, struct pci_dev *pdev,
 		struct pci_dev *pf0_dev, u32 guest_rid);
+int cca_pdev_refresh_stream_key(struct pci_dev *pdev1,
+		struct pci_dev *pdev2, unsigned long stream_handle);
+int cca_pdev_purge_stream_key(struct pci_dev *pdev1,
+		struct pci_dev *pdev2, unsigned long stream_handle);
 
 #endif

---

## [9] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 08/16] coco: host: arm64: Add helpers to unlock and destroy RMM vdev*

- define the SMCCC IDs and inline wrappers for RMI_VDEV_UNLOCK and
  RMI_VDEV_DESTROY
- extend vdev_create() to treat communication failures as fatal and
  tear down the newly created vdev
- provide vdev_unlock_and_destroy() that drives the vdev back to the
  unlocked state, issues the destroy call, and frees the delegated granule
- hook the new helper into the TSM unbind path so host cleanup always
  unlock and destroy RMM vdev and releases cached buffers

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h        | 20 +++++++
 arch/arm64/include/asm/rmi_smc.h         |  2 +
 drivers/virt/coco/arm-cca-host/arm-cca.c | 25 +++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.c  | 69 ++++++++++++++++++++++--
 drivers/virt/coco/arm-cca-host/rmi-da.h  |  3 ++
 5 files changed, 116 insertions(+), 3 deletions(-)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 03dffba763e1..aa7ef9f07517 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -949,4 +949,24 @@ static inline unsigned long rmi_pdev_stream_key_purge(unsigned long pdev1_phys,
 	return res.a0;
 }
 
+static inline unsigned long rmi_vdev_unlock(unsigned long rd,
+		unsigned long pdev_phys, unsigned long vdev_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_UNLOCK, rd, pdev_phys, vdev_phys, &res);
+
+	return res.a0;
+}
+
+static inline unsigned long rmi_vdev_destroy(unsigned long rd,
+		unsigned long pdev_phys, unsigned long vdev_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_DESTROY, rd, pdev_phys, vdev_phys, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index d14d13a9f169..6cd5439f56ec 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -649,6 +649,8 @@ enum rmi_vdev_state {
 	RMI_VDEV_LOCKED,
 	RMI_VDEV_STARTED,
 	RMI_VDEV_ERROR,
+	RMI_VDEV_KEY_REFRESH,
+	RMI_VDEV_KEY_PURGE,
 };
 
 #define MAX_VDEV_ADDR_RANGE 8
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index 5930a30dd16f..b75fa20513a9 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -473,12 +473,37 @@ static struct pci_tdi *cca_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u32 t
 	return &no_free_ptr(host_tdi)->tdi;
 }
 
+/*
+ * All device memory should be unmapped by now.
+ * 1. A pci device destroy will cause a driver remove (vfio) which will have
+ *    done a dmabuf based unmap
+ * 2. A vdevice/idevice destroy from VMM should have done a unmap_private_range
+ *    vm ioctl before
+ * 3. A guest unlock request should have done a rsi_invalidiate_mem_mapping
+ *    before unlock rhi
+ * 4. vfio_pci_core_close_device() should trigger tsm unbind if vdevice is not
+ *    already distroyed and that path involves vfio_pci_dma_buf_cleanup() which
+ *    should get kvm to unmap the devmap
+ */
+static void cca_tsm_unbind(struct pci_tdi *tdi)
+{
+	struct cca_host_tdi *host_tdi;
+	struct realm *realm = &tdi->kvm->arch.realm;
+
+	host_tdi = container_of(tdi, struct cca_host_tdi, tdi);
+	cca_vdev_unlock_and_destroy(realm, tdi->pdev, tdi->pdev->tsm->dsm_dev);
+	kvfree(host_tdi->interface_report);
+	kvfree(host_tdi->measurements);
+	kfree(host_tdi);
+}
+
 static struct pci_tsm_ops cca_link_pci_ops = {
 	.probe = cca_tsm_pci_probe,
 	.remove = cca_tsm_pci_remove,
 	.connect = cca_tsm_connect,
 	.disconnect = cca_tsm_disconnect,
 	.bind = cca_tsm_bind,
+	.unbind = cca_tsm_unbind,
 };
 
 static void cca_link_tsm_remove(void *tsm_dev)
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index 128079d5b993..ef25392562e0 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -1018,15 +1018,25 @@ void *cca_vdev_create(struct realm *realm, struct pci_dev *pdev,
 	host_tdi->rmm_vdev = rmm_vdev;
 	host_tdi->realm = realm;
 
-	submit_vdev_state_transition_work(pdev, RMI_VDEV_UNLOCKED);
+	ret = submit_vdev_state_transition_work(pdev, RMI_VDEV_UNLOCKED);
+	/* failure is treated as rmi_vdev_create failure */
+	if (ret)
+		goto err_vdev_comm;
 
-	ret = rmi_vdev_lock(rd_phys, rmm_pdev_phys, rmm_vdev_phys);
+	if (rmi_vdev_lock(rd_phys, rmm_pdev_phys, rmm_vdev_phys)) {
+		ret = -ENXIO;
+		goto err_vdev_comm;
+	}
 
-	submit_vdev_state_transition_work(pdev, RMI_VDEV_LOCKED);
+	ret = submit_vdev_state_transition_work(pdev, RMI_VDEV_LOCKED);
+	if (ret)
+		goto err_vdev_comm;
 
 	free_page((unsigned long)params);
 	return rmm_vdev;
 
+err_vdev_comm:
+	rmi_vdev_destroy(rd_phys, rmm_pdev_phys, rmm_vdev_phys);
 err_vdev_create:
 	free_page((unsigned long)params);
 err_params_alloc:
@@ -1073,3 +1083,56 @@ int cca_pdev_purge_stream_key(struct pci_dev *pdev1,
 
 	return submit_stream_work(pdev1, pdev2, stream_handle);
 }
+
+void cca_vdev_unlock_and_destroy(struct realm *realm,
+		struct pci_dev *pdev, struct pci_dev *pf0_dev)
+{
+	int ret;
+	phys_addr_t rmm_pdev_phys;
+	phys_addr_t rmm_vdev_phys;
+	struct cca_host_pdev_dsc *pdev_dsc;
+	struct cca_host_tdi *host_tdi;
+	phys_addr_t rd_phys = virt_to_phys(realm->rd);
+
+	host_tdi = to_cca_host_tdi(pdev);
+	rmm_vdev_phys = virt_to_phys(host_tdi->rmm_vdev);
+
+	pdev_dsc = to_cca_pdev_dsc(pf0_dev);
+	rmm_pdev_phys = virt_to_phys(pdev_dsc->rmm_pdev);
+	if (rmi_vdev_unlock(rd_phys, rmm_pdev_phys, rmm_vdev_phys)) {
+		pci_err(pdev, "failed to unlock vdev\n");
+		goto unlock_err;
+	}
+
+	if (rmm_has_reg2_feature(RMI_FEATURE_REGISTER_2_VDEV_KROU)) {
+		struct pci_dev *rp = pcie_find_root_port(pf0_dev);
+		struct cca_host_pf0_ep_dsc *pf0_ep_dsc = to_cca_pf0_ep_dsc(pf0_dev);
+
+		ret = submit_vdev_state_transition_work(pdev, RMI_VDEV_KEY_REFRESH);
+		if (ret)
+			pci_err(pdev, "failed to transition vdev to KEY_REFRESH state (%d)\n", ret);
+
+		ret = cca_pdev_refresh_stream_key(pf0_dev, rp, pf0_ep_dsc->stream_handle);
+		if (ret)
+			pci_err(pf0_dev, "failed to refresh pdev stream key (%d)\n", ret);
+
+		ret = cca_pdev_purge_stream_key(pf0_dev, rp, pf0_ep_dsc->stream_handle);
+		if (ret)
+			pci_err(pf0_dev, "failed to purge pdev stream key (%d)\n", ret);
+	}
+
+	ret = submit_vdev_state_transition_work(pdev, RMI_VDEV_UNLOCKED);
+	if (ret)
+		pci_err(pdev, "failed to unlock vdev (%d)\n", ret);
+
+unlock_err:
+	/* Try to destroy even in case of error */
+	if (rmi_vdev_destroy(rd_phys, rmm_pdev_phys, rmm_vdev_phys))
+		pci_err(pdev, "failed to destroy vdev\n");
+
+	if (!rmi_undelegate_page(rmm_vdev_phys))
+		free_page((unsigned long)host_tdi->rmm_vdev);
+
+	host_tdi->rmm_vdev = NULL;
+	host_tdi->realm = NULL;
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index d6cdbc638d6d..97f7eaf1f779 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -15,6 +15,7 @@
 #include <linux/wait.h>
 #include <asm/rmi_cmds.h>
 #include <asm/rmi_smc.h>
+#include <asm/rhi.h>
 
 #define MAX_CACHE_OBJ_SIZE	SZ_16M
 #define CACHE_CHUNK_SIZE	SZ_4K
@@ -239,5 +240,7 @@ int cca_pdev_refresh_stream_key(struct pci_dev *pdev1,
 		struct pci_dev *pdev2, unsigned long stream_handle);
 int cca_pdev_purge_stream_key(struct pci_dev *pdev1,
 		struct pci_dev *pdev2, unsigned long stream_handle);
+void cca_vdev_unlock_and_destroy(struct realm *realm, struct pci_dev *pdev,
+		struct pci_dev *pf0_dev);
 
 #endif

---

## [10] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 09/16] coco: host: arm64: Add support for da object read RHI handling*

Device assignment-related RHI calls result in a REC exit, which is
handled by the tsm guest_request callback.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/uapi/asm/rmi-da.h     | 21 ++++++
 drivers/virt/coco/arm-cca-host/arm-cca.c | 74 ++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.c  | 95 ++++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.h  |  3 +
 4 files changed, 193 insertions(+)
 create mode 100644 arch/arm64/include/uapi/asm/rmi-da.h

diff --git a/arch/arm64/include/uapi/asm/rmi-da.h b/arch/arm64/include/uapi/asm/rmi-da.h
new file mode 100644
index 000000000000..5ec3413dce94
--- /dev/null
+++ b/arch/arm64/include/uapi/asm/rmi-da.h
@@ -0,0 +1,21 @@
+/* SPDX-License-Identifier: GPL-2.0 WITH Linux-syscall-note */
+
+#ifndef _UAPI__ASM_RMI_DA_H
+#define _UAPI__ASM_RMI_DA_H
+
+#include <linux/types.h>
+
+struct arm64_vdev_object_size_guest_req {
+	__u32 req_type;
+	__u32 object_type;
+};
+#define __RHI_DA_OBJECT_SIZE		0x1
+
+struct arm64_vdev_object_read_guest_req {
+	__u32 req_type;
+	__u32 object_type;
+	__aligned_u64 offset;
+};
+#define __RHI_DA_OBJECT_READ		0x2
+
+#endif
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index b75fa20513a9..4bf1f1b394af 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -14,6 +14,7 @@
 #include <linux/pci-doe.h>
 #include <linux/pci.h>
 #include <linux/kvm_host.h>
+#include <asm/rmi-da.h>
 
 #include "rmi-da.h"
 
@@ -497,6 +498,78 @@ static void cca_tsm_unbind(struct pci_tdi *tdi)
 	kfree(host_tdi);
 }
 
+static ssize_t cca_tsm_guest_req(struct pci_tdi *tdi, enum pci_tsm_req_scope scope,
+		sockptr_t req, size_t req_len, sockptr_t resp,
+		size_t resp_len, u64 *tsm_code)
+{
+	struct pci_dev *pdev = tdi->pdev;
+
+	if (req.is_kernel || resp.is_kernel)
+		return -EINVAL;
+
+	switch (scope) {
+	case PCI_TSM_REQ_INFO: {
+		u32 req_type;
+
+		if (get_user(req_type, (u32 __user *)req.user))
+			return -EFAULT;
+
+		switch (req_type) {
+		case __RHI_DA_OBJECT_SIZE: {
+			int object_size;
+			struct arm64_vdev_object_size_guest_req req_obj;
+
+			if (req_len != sizeof(req_obj))
+				return -EINVAL;
+
+			if (copy_from_user((void *)&req_obj, req.user, req_len))
+				return -EFAULT;
+			object_size = cca_vdev_get_object_size(pdev, req_obj.object_type);
+			if (object_size > 0) {
+				if (resp_len < sizeof(object_size))
+					return -EINVAL;
+				if (copy_to_user(resp.user, &object_size, sizeof(object_size)))
+					return -EFAULT;
+
+				if (resp_len != sizeof(object_size))
+					return resp_len - sizeof(object_size);
+				return 0;
+			}
+			/* error */
+			return object_size;
+		}
+		case __RHI_DA_OBJECT_READ:
+		{
+			int len;
+			struct arm64_vdev_object_read_guest_req req_obj;
+
+			if (req_len != sizeof(req_obj))
+				return -EINVAL;
+
+			if (copy_from_user((void *)&req_obj, req.user, req_len))
+				return -EFAULT;
+
+			len = cca_vdev_read_cached_object(pdev,
+							  req_obj.object_type,
+							  req_obj.offset,
+							  resp_len, resp.user);
+			if (len > 0) {
+				if (resp_len != len)
+					return resp_len - len;
+				return 0;
+			}
+			/* error */
+			return len;
+		}
+		default:
+			return -EINVAL;
+		}
+	}
+	default:
+		return -EINVAL;
+	}
+}
+
 static struct pci_tsm_ops cca_link_pci_ops = {
 	.probe = cca_tsm_pci_probe,
 	.remove = cca_tsm_pci_remove,
@@ -504,6 +577,7 @@ static struct pci_tsm_ops cca_link_pci_ops = {
 	.disconnect = cca_tsm_disconnect,
 	.bind = cca_tsm_bind,
 	.unbind = cca_tsm_unbind,
+	.guest_req = cca_tsm_guest_req,
 };
 
 static void cca_link_tsm_remove(void *tsm_dev)
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index ef25392562e0..3db42c21dab0 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -12,6 +12,7 @@
 #include <keys/asymmetric-type.h>
 #include <keys/x509-parser.h>
 #include <linux/kvm_types.h>
+#include <linux/kvm_host.h>
 #include <asm/kvm_rmi.h>
 
 #include "rmi-da.h"
@@ -1136,3 +1137,97 @@ void cca_vdev_unlock_and_destroy(struct realm *realm,
 	host_tdi->rmm_vdev = NULL;
 	host_tdi->realm = NULL;
 }
+
+int cca_vdev_get_object_size(struct pci_dev *pdev, int type)
+{
+	long len;
+	struct cca_host_tdi *host_tdi;
+	struct cca_host_pf0_ep_dsc *pf0_ep_dsc;
+	struct pci_tsm *tsm = pdev->tsm;
+	struct cca_host_pdev_dsc *pdev_dsc;
+
+	if (!tsm)
+		return -EINVAL;
+
+	pdev_dsc = to_cca_pdev_dsc(tsm->dsm_dev);
+	pf0_ep_dsc = to_cca_pf0_ep_dsc(tsm->dsm_dev);
+	host_tdi = to_cca_host_tdi(pdev);
+
+	guard(mutex)(&pdev_dsc->object_lock);
+	/* Determine the buffer that should be used */
+	if (type == RHI_DA_OBJECT_INTERFACE_REPORT) {
+		if (!host_tdi->interface_report)
+			return -EINVAL;
+		len = host_tdi->interface_report->offset;
+	} else if (type == RHI_DA_OBJECT_MEASUREMENT) {
+		if (!host_tdi->measurements)
+			return -EINVAL;
+		len = host_tdi->measurements->offset;
+	} else if (type == RHI_DA_OBJECT_CERTIFICATE) {
+		if (!pf0_ep_dsc->cert_chain.cache)
+			return -EINVAL;
+		len = pf0_ep_dsc->cert_chain.cache->offset;
+	} else if (type == RHI_DA_OBJECT_VCA) {
+		if (!pf0_ep_dsc->vca)
+			return -EINVAL;
+		len = pf0_ep_dsc->vca->offset;
+	} else {
+		return -EINVAL;
+	}
+
+	return len;
+}
+
+int cca_vdev_read_cached_object(struct pci_dev *pdev, int type,
+		unsigned long offset, unsigned long max_len,
+		void __user *user_buf)
+{
+	void *buf;
+	unsigned long len;
+	struct cca_host_tdi *host_tdi;
+	struct cca_host_pf0_ep_dsc *pf0_ep_dsc;
+	struct pci_tsm *tsm = pdev->tsm;
+	struct cca_host_pdev_dsc *pdev_dsc;
+
+	if (!tsm)
+		return -EINVAL;
+
+	pdev_dsc = to_cca_pdev_dsc(tsm->dsm_dev);
+	pf0_ep_dsc = to_cca_pf0_ep_dsc(tsm->dsm_dev);
+	host_tdi = to_cca_host_tdi(pdev);
+
+	guard(mutex)(&pdev_dsc->object_lock);
+	/* Determine the buffer that should be used */
+	if (type == RHI_DA_OBJECT_INTERFACE_REPORT) {
+		if (!host_tdi->interface_report)
+			return -EINVAL;
+		len = host_tdi->interface_report->offset;
+		buf = host_tdi->interface_report->buf;
+	} else if (type == RHI_DA_OBJECT_MEASUREMENT) {
+		if (!host_tdi->measurements)
+			return -EINVAL;
+		len = host_tdi->measurements->offset;
+		buf = host_tdi->measurements->buf;
+	} else if (type == RHI_DA_OBJECT_CERTIFICATE) {
+		if (!pf0_ep_dsc->cert_chain.cache)
+			return -EINVAL;
+		len = pf0_ep_dsc->cert_chain.cache->offset;
+		buf = pf0_ep_dsc->cert_chain.cache->buf;
+	} else if (type == RHI_DA_OBJECT_VCA) {
+		if (!pf0_ep_dsc->vca)
+			return -EINVAL;
+		len = pf0_ep_dsc->vca->offset;
+		buf = pf0_ep_dsc->vca->buf;
+	} else {
+		return -EINVAL;
+	}
+
+	/* Assume that the buffer is large enough for the whole report */
+	if (max_len < len)
+		return -E2BIG;
+
+	if (copy_to_user(user_buf, buf + offset, len))
+		return -EIO;
+
+	return len;
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index 97f7eaf1f779..4f1a61a5dcfa 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -242,5 +242,8 @@ int cca_pdev_purge_stream_key(struct pci_dev *pdev1,
 		struct pci_dev *pdev2, unsigned long stream_handle);
 void cca_vdev_unlock_and_destroy(struct realm *realm, struct pci_dev *pdev,
 		struct pci_dev *pf0_dev);
+int cca_vdev_get_object_size(struct pci_dev *pdev, int type);
+int cca_vdev_read_cached_object(struct pci_dev *pdev, int type, unsigned long offset,
+		unsigned long max_len, void __user *user_buf);
 
 #endif

---

## [11] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 10/16] coco: host: arm64: Add helper for cached object fetches*

Introduce vdev_fetch_object_work() so we have a single workqueue handler
that refreshes any cached Realm object (interface report, measurements,
certificates). The helper receives the cache buffer/offset/size via
dev_comm_work, clears the existing contents under dsm_dev.object_lock,
performs the VDEV_COMMUNICATE call, and uses the updated size to signal
failures back to the caller once the work completes.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/virt/coco/arm-cca-host/rmi-da.c | 26 +++++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.h |  3 +++
 2 files changed, 29 insertions(+)

diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index 3db42c21dab0..63b20c8aef54 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -1138,6 +1138,32 @@ void cca_vdev_unlock_and_destroy(struct realm *realm,
 	host_tdi->realm = NULL;
 }
 
+static void __maybe_unused vdev_fetch_object_workfn(struct work_struct *work)
+{
+	int state;
+	struct pci_tsm *tsm;
+	struct cca_host_pdev_dsc *pdev_dsc;
+	struct dev_comm_work *setup_work;
+
+	setup_work = container_of(work, struct dev_comm_work, work);
+	tsm = setup_work->tsm;
+	pdev_dsc = to_cca_pdev_dsc(tsm->dsm_dev);
+
+	guard(mutex)(&pdev_dsc->object_lock);
+
+	if (setup_work->cache_size) {
+		memset(setup_work->cache_buf, 0, setup_work->cache_size);
+		*setup_work->cache_offset = 0;
+	}
+	state = do_dev_communicate(VDEV_COMMUNICATE, tsm, RMI_VDEV_ERROR, NULL);
+	/* return status through dev_comm_work.cache_cache */
+	if (state == RMI_VDEV_ERROR)
+		setup_work->cache_size = 0;
+	else
+		/* indicate success. This value is not used. */
+		setup_work->cache_size = CACHE_CHUNK_SIZE;
+}
+
 int cca_vdev_get_object_size(struct pci_dev *pdev, int type)
 {
 	long len;
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index 4f1a61a5dcfa..c1fc7c01943e 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -28,6 +28,9 @@ struct cache_object {
 struct dev_comm_work {
 	struct pci_tsm *tsm;
 	int target_state;
+	u8 *cache_buf;
+	int *cache_offset;
+	int cache_size;
 	struct work_struct work;
 };

---

## [12] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 11/16] coco: host: arm64: Fetch interface report via RMI*

- define __RHI_DA_VDEV_GET_INTERFACE_REPORT for guest requests and
  expose the RMI SMC ID/wrapper for RMI_VDEV_GET_INTERFACE_REPORT
- teach the CCA host driver to handle the new guest request by fetching
  the report from RMM using rmi_vdev_get_interface_report() and
  refreshing the cached buffer
- add a helper that submits a DOE work to pull the latest report into
  the cache

This lets guests request up-to-date interface reports via RHI

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h        | 12 ++++++
 arch/arm64/include/uapi/asm/rmi-da.h     |  3 ++
 drivers/virt/coco/arm-cca-host/arm-cca.c |  4 ++
 drivers/virt/coco/arm-cca-host/rmi-da.c  | 54 +++++++++++++++++++++++-
 drivers/virt/coco/arm-cca-host/rmi-da.h  |  1 +
 5 files changed, 73 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index aa7ef9f07517..b3c04029bb47 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -969,4 +969,16 @@ static inline unsigned long rmi_vdev_destroy(unsigned long rd,
 	return res.a0;
 }
 
+static inline unsigned long rmi_vdev_get_interface_report(unsigned long rd,
+					     unsigned long pdev_phys,
+					     unsigned long vdev_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_GET_INTERFACE_REPORT,
+			     rd, pdev_phys, vdev_phys, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/uapi/asm/rmi-da.h b/arch/arm64/include/uapi/asm/rmi-da.h
index 5ec3413dce94..8d36a4c59849 100644
--- a/arch/arm64/include/uapi/asm/rmi-da.h
+++ b/arch/arm64/include/uapi/asm/rmi-da.h
@@ -18,4 +18,7 @@ struct arm64_vdev_object_read_guest_req {
 };
 #define __RHI_DA_OBJECT_READ		0x2
 
+/* No arguments to this guest request */
+#define __RHI_DA_VDEV_UPDATE_INTERFACE_REPORT 0x3
+
 #endif
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index 4bf1f1b394af..2955993d29ac 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -561,6 +561,10 @@ static ssize_t cca_tsm_guest_req(struct pci_tdi *tdi, enum pci_tsm_req_scope sco
 			/* error */
 			return len;
 		}
+		case __RHI_DA_VDEV_UPDATE_INTERFACE_REPORT:
+		{
+			return cca_vdev_update_interface_report(pdev);
+		}
 		default:
 			return -EINVAL;
 		}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index 63b20c8aef54..1862e4ff8cbb 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -1138,7 +1138,7 @@ void cca_vdev_unlock_and_destroy(struct realm *realm,
 	host_tdi->realm = NULL;
 }
 
-static void __maybe_unused vdev_fetch_object_workfn(struct work_struct *work)
+static void vdev_fetch_object_workfn(struct work_struct *work)
 {
 	int state;
 	struct pci_tsm *tsm;
@@ -1257,3 +1257,55 @@ int cca_vdev_read_cached_object(struct pci_dev *pdev, int type,
 
 	return len;
 }
+
+static int vdev_update_interface_report_cache(struct pci_dev *pdev)
+{
+	struct dev_comm_work comm_work;
+	struct cca_host_tdi *host_tdi = to_cca_host_tdi(pdev);
+	struct cca_host_comm_data *comm_data = to_cca_comm_data(pdev);
+
+	INIT_WORK_ONSTACK(&comm_work.work, vdev_fetch_object_workfn);
+	comm_work.tsm = pdev->tsm;
+	if (host_tdi->interface_report) {
+		comm_work.cache_buf = host_tdi->interface_report->buf;
+		comm_work.cache_offset = &host_tdi->interface_report->offset;
+		comm_work.cache_size = host_tdi->interface_report->size;
+	} else {
+		comm_work.cache_buf = NULL;
+		comm_work.cache_offset = NULL;
+		comm_work.cache_size = 0;
+	}
+
+	queue_work(comm_data->work_queue, &comm_work.work);
+	flush_work(&comm_work.work);
+	destroy_work_on_stack(&comm_work.work);
+
+	if (comm_work.cache_size == 0)
+		return -ENXIO;
+	return 0;
+}
+
+int cca_vdev_update_interface_report(struct pci_dev *pdev)
+{
+	phys_addr_t rmm_pdev_phys;
+	phys_addr_t rmm_vdev_phys;
+	struct cca_host_pdev_dsc *pdev_dsc;
+	struct cca_host_tdi *host_tdi;
+	struct realm *realm;
+	phys_addr_t rd_phys;
+
+	host_tdi = to_cca_host_tdi(pdev);
+	rmm_vdev_phys = virt_to_phys(host_tdi->rmm_vdev);
+	realm = &host_tdi->tdi.kvm->arch.realm;
+	rd_phys = virt_to_phys(realm->rd);
+
+	pdev_dsc = to_cca_pdev_dsc(pdev->tsm->dsm_dev);
+	rmm_pdev_phys = virt_to_phys(pdev_dsc->rmm_pdev);
+
+	if (rmi_vdev_get_interface_report(rd_phys,
+					  rmm_pdev_phys, rmm_vdev_phys))
+		return -ENXIO;
+
+	/* get and update the interface report cache. */
+	return vdev_update_interface_report_cache(pdev);
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index c1fc7c01943e..b114bf4d4202 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -248,5 +248,6 @@ void cca_vdev_unlock_and_destroy(struct realm *realm, struct pci_dev *pdev,
 int cca_vdev_get_object_size(struct pci_dev *pdev, int type);
 int cca_vdev_read_cached_object(struct pci_dev *pdev, int type, unsigned long offset,
 		unsigned long max_len, void __user *user_buf);
+int cca_vdev_update_interface_report(struct pci_dev *pdev);
 
 #endif

---

## [13] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 12/16] coco: host: arm64: Fetch device measurements via RMI*

- define __RHI_DA_VDEV_GET_MEASUREMENTS for guest requests and
  expose the RMI SMC ID/wrapper for RMI_VDEV_GET_DEV_MEASUREMENTS
- teach the CCA host driver to handle the new guest request by fetching
  the device measurements from RMM using rmi_vdev_get_device_measurements()
  and refreshing the cached buffer
- add a helper that submits a DOE work to pull the latest device
  measurements into the cache

This lets guests request up-to-date device measurements via RHI

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h        | 12 +++++
 arch/arm64/include/asm/rmi_smc.h         | 13 +++++
 arch/arm64/include/uapi/asm/rmi-da.h     |  8 +++
 drivers/virt/coco/arm-cca-host/arm-cca.c | 16 ++++++
 drivers/virt/coco/arm-cca-host/rmi-da.c  | 68 ++++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.h  |  1 +
 6 files changed, 118 insertions(+)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index b3c04029bb47..350fd9bc93a4 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -981,4 +981,16 @@ static inline unsigned long rmi_vdev_get_interface_report(unsigned long rd,
 	return res.a0;
 }
 
+static inline unsigned long
+rmi_vdev_get_device_measurements(unsigned long rd, unsigned long pdev_phys,
+				 unsigned long vdev_phys,
+				 unsigned long param_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_GET_MEASUREMENTS,
+			     rd, pdev_phys, vdev_phys, param_phys, &res);
+
+	return res.a0;
+}
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 6cd5439f56ec..29dbe4e0dfb0 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -674,4 +674,17 @@ struct rmi_vdev_params {
 	};
 };
 
+#define RMI_VDEV_MEASURE_HASH	0x0
+#define RMI_VDEV_MEASURE_RAW	0x1
+struct rmi_vdev_measurement_params {
+	union {
+		u64 flags;
+		u8 padding0[256];
+	};
+	union {
+		u8 nonce[32];
+		u8 padding1[256];
+	};
+};
+
 #endif /* __ASM_RMI_SMC_H */
diff --git a/arch/arm64/include/uapi/asm/rmi-da.h b/arch/arm64/include/uapi/asm/rmi-da.h
index 8d36a4c59849..97648928f763 100644
--- a/arch/arm64/include/uapi/asm/rmi-da.h
+++ b/arch/arm64/include/uapi/asm/rmi-da.h
@@ -21,4 +21,12 @@ struct arm64_vdev_object_read_guest_req {
 /* No arguments to this guest request */
 #define __RHI_DA_VDEV_UPDATE_INTERFACE_REPORT 0x3
 
+struct arm64_vdev_device_measurement_guest_req {
+	__u32 req_type;
+	__u32 reserved;
+	__aligned_u64 flags;
+	__aligned_u64 nonce;
+};
+#define __RHI_DA_VDEV_UPDATE_MEASUREMENTS	0x4
+
 #endif
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index 2955993d29ac..855427935f2d 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -565,6 +565,22 @@ static ssize_t cca_tsm_guest_req(struct pci_tdi *tdi, enum pci_tsm_req_scope sco
 		{
 			return cca_vdev_update_interface_report(pdev);
 		}
+		case __RHI_DA_VDEV_UPDATE_MEASUREMENTS:
+		{
+			int ret;
+			struct arm64_vdev_device_measurement_guest_req req_obj;
+
+			if (req_len != sizeof(req_obj))
+				return -EINVAL;
+
+			if (copy_from_user((void *)&req_obj, req.user, req_len))
+				return -EFAULT;
+
+			ret = cca_vdev_update_device_measurements(pdev,
+								  req_obj.flags,
+								  (u8 *)req_obj.nonce);
+			return ret;
+		}
 		default:
 			return -EINVAL;
 		}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index 1862e4ff8cbb..ec7701ff7e03 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -1309,3 +1309,71 @@ int cca_vdev_update_interface_report(struct pci_dev *pdev)
 	/* get and update the interface report cache. */
 	return vdev_update_interface_report_cache(pdev);
 }
+
+static int vdev_update_device_measurements_cache(struct pci_dev *pdev)
+{
+	struct dev_comm_work comm_work;
+	struct cca_host_tdi *host_tdi = to_cca_host_tdi(pdev);
+	struct cca_host_comm_data *comm_data = to_cca_comm_data(pdev);
+
+	INIT_WORK_ONSTACK(&comm_work.work, vdev_fetch_object_workfn);
+	comm_work.tsm = pdev->tsm;
+	if (host_tdi->measurements) {
+		comm_work.cache_buf = host_tdi->measurements->buf;
+		comm_work.cache_offset = &host_tdi->measurements->offset;
+		comm_work.cache_size = host_tdi->measurements->size;
+	} else {
+		comm_work.cache_buf = NULL;
+		comm_work.cache_offset = NULL;
+		comm_work.cache_size = 0;
+	}
+
+	queue_work(comm_data->work_queue, &comm_work.work);
+	flush_work(&comm_work.work);
+	destroy_work_on_stack(&comm_work.work);
+
+	if (comm_work.cache_size == 0)
+		return -ENXIO;
+	return 0;
+}
+
+static inline void vdev_measurement_param_free(struct rmi_vdev_measurement_params *param)
+{
+	return free_page((unsigned long)param);
+}
+DEFINE_FREE(measurement_param_free, struct rmi_vdev_measurement_params *, if (_T) vdev_measurement_param_free(_T))
+
+int cca_vdev_update_device_measurements(struct pci_dev *pdev, unsigned long flags, u8 *nonce)
+{
+	struct realm *realm;
+	phys_addr_t rd_phys;
+	phys_addr_t rmm_pdev_phys;
+	phys_addr_t rmm_vdev_phys;
+	struct cca_host_tdi *host_tdi;
+	struct cca_host_pdev_dsc *pdev_dsc;
+
+	host_tdi = to_cca_host_tdi(pdev);
+	rmm_vdev_phys = virt_to_phys(host_tdi->rmm_vdev);
+	realm = &host_tdi->tdi.kvm->arch.realm;
+	rd_phys = virt_to_phys(realm->rd);
+
+	pdev_dsc = to_cca_pdev_dsc(pdev->tsm->dsm_dev);
+	rmm_pdev_phys = virt_to_phys(pdev_dsc->rmm_pdev);
+
+	struct rmi_vdev_measurement_params *params __free(measurement_param_free) =
+		(struct rmi_vdev_measurement_params *)get_zeroed_page(GFP_KERNEL_ACCOUNT);
+	if (!params)
+		return -ENOMEM;
+
+	params->flags = flags;
+
+	if (copy_from_user(params->nonce, nonce, sizeof(params->nonce)))
+		return -EFAULT;
+
+	if (rmi_vdev_get_device_measurements(rd_phys, rmm_pdev_phys,
+					     rmm_vdev_phys, virt_to_phys(params)))
+		return -ENXIO;
+
+	/* get and update the interface report cache. */
+	return vdev_update_device_measurements_cache(pdev);
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index b114bf4d4202..621e0858f0c6 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -249,5 +249,6 @@ int cca_vdev_get_object_size(struct pci_dev *pdev, int type);
 int cca_vdev_read_cached_object(struct pci_dev *pdev, int type, unsigned long offset,
 		unsigned long max_len, void __user *user_buf);
 int cca_vdev_update_interface_report(struct pci_dev *pdev);
+int cca_vdev_update_device_measurements(struct pci_dev *pdev, unsigned long flags, u8 *nonce);
 
 #endif

---

## [14] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 13/16] coco: host: KVM: arm64: Handle vdev validate-mapping exits*

Add the RMM/RHI definitions needed for device-memory mapping exits and
plumb them through the arm64 Realm host stack.

Teach KVM to handle RMI_EXIT_VDEV_VALIDATE_MAPPING by exposing the request
to userspace as KVM_EXIT_ARM64_TIO, carrying the vdev id together with the
GPA range and host PA supplied by RMM. On re-entry, complete the request
with RMI_RTT_DEV_VALIDATE.

Also add realm_dev_mem_map() so the host CCA driver can install
device-memory mappings for a vdev, and wire the PCI TSM state-change
request path to call it.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 Documentation/virt/kvm/api.rst           |  20 +++
 arch/arm64/include/asm/kvm_rmi.h         |   4 +
 arch/arm64/include/asm/rmi_smc.h         |   2 +
 arch/arm64/include/uapi/asm/rmi-da.h     |   9 ++
 arch/arm64/kvm/rmi-exit.c                |  37 +++++
 arch/arm64/kvm/rmi.c                     | 189 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/arm-cca.c |  27 ++++
 drivers/virt/coco/arm-cca-host/rmi-da.c  |  21 +++
 drivers/virt/coco/arm-cca-host/rmi-da.h  |   2 +
 include/uapi/linux/kvm.h                 |  11 ++
 10 files changed, 322 insertions(+)

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index 5dfaafae14b6..4df99bb2857f 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -7454,6 +7454,26 @@ the ``KVM_EXIT_ARM_SEA_FLAG_GPA_VALID`` flag is set. Otherwise, the value of
 ``gpa`` is unknown.
 
 ::
+		/* KVM_EXIT_ARM64_TIO*/
+		struct {
+			__u64 flags;
+			__u64 nr;
+			__u64 vdev_id;
+			__u64 gpa_base;
+			__u64 gpa_top;
+			__u64 pa_base;
+			__u64 response;
+		} cca_exit;
+
+Used on arm64 systems. When the VM capability ``KVM_CAP_ARM_RMI`` is
+enabled, KVM generates a VM exit whenever the guest needs host assistance
+to validate a device-memory GPA-to-PA mapping. The ``nr`` field records
+the exit reason; currently the following values are defined:
+
+* ``RMI_EXIT_VDEV_VALIDATE_MAPPING``: the guest wants the host to validate or install a
+  device-memory mapping.
+
+The ``flags`` field must be zero.
 
 		/* Fix the size of the union. */
 		char padding[256];
diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index e1f5523c2dfa..f49988fe182e 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -126,4 +126,8 @@ static inline bool kvm_realm_is_private_address(struct realm *realm,
 	return !(addr & BIT(realm->ia_bits - 1));
 }
 
+int realm_dev_mem_map(struct kvm *kvm, unsigned long pdev_phys,
+		unsigned long vdev_phys, unsigned long start_ipa,
+		unsigned long end_ipa, unsigned long start_pa);
+
 #endif /* __ASM_KVM_RMI_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 29dbe4e0dfb0..6bbabcd853bd 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -328,6 +328,7 @@ struct rec_params {
 #define REC_ENTER_FLAG_TRAP_WFI		BIT(2)
 #define REC_ENTER_FLAG_TRAP_WFE		BIT(3)
 #define REC_ENTER_FLAG_RIPAS_RESPONSE	BIT(4)
+#define REC_ENTER_FLAG_DEV_MEM_RESPONSE BIT(6)
 
 #define REC_RUN_GPRS			31
 #define REC_MAX_GIC_NUM_LRS		16
@@ -360,6 +361,7 @@ struct rec_enter {
 #define RMI_EXIT_RIPAS_CHANGE		0x04
 #define RMI_EXIT_HOST_CALL		0x05
 #define RMI_EXIT_SERROR			0x06
+#define RMI_EXIT_VDEV_VALIDATE_MAPPING		0x09
 
 struct rec_exit {
 	union { /* 0x000 */
diff --git a/arch/arm64/include/uapi/asm/rmi-da.h b/arch/arm64/include/uapi/asm/rmi-da.h
index 97648928f763..572afb4095f2 100644
--- a/arch/arm64/include/uapi/asm/rmi-da.h
+++ b/arch/arm64/include/uapi/asm/rmi-da.h
@@ -29,4 +29,13 @@ struct arm64_vdev_device_measurement_guest_req {
 };
 #define __RHI_DA_VDEV_UPDATE_MEASUREMENTS	0x4
 
+struct arm64_vdev_device_memmap_guest_req {
+	__u32 req_type;
+	__u32 reserved;
+	__aligned_u64 gpa_base;
+	__aligned_u64 gpa_top;
+	__aligned_u64 pa_base;
+};
+#define __REC_DA_VDEV_MAP		0x5
+
 #endif
diff --git a/arch/arm64/kvm/rmi-exit.c b/arch/arm64/kvm/rmi-exit.c
index 7eff6967530c..8c7cf716ce3c 100644
--- a/arch/arm64/kvm/rmi-exit.c
+++ b/arch/arm64/kvm/rmi-exit.c
@@ -129,6 +129,41 @@ static int rec_exit_host_call(struct kvm_vcpu *vcpu)
 	return kvm_smccc_call_handler(vcpu);
 }
 
+static inline void kvm_prepare_vdev_validate_mapping_exit(struct kvm_vcpu *vcpu,
+		gpa_t gpa_base, gpa_t gpa_top,
+		hpa_t pa_base, unsigned long vdev_id)
+{
+	vcpu->run->exit_reason = KVM_EXIT_ARM64_TIO;
+	vcpu->run->cca_exit.nr = RMI_EXIT_VDEV_VALIDATE_MAPPING;
+	vcpu->run->cca_exit.vdev_id  = vdev_id;
+	vcpu->run->cca_exit.flags = 0;
+	vcpu->run->cca_exit.gpa_base = gpa_base;
+	vcpu->run->cca_exit.gpa_top  = gpa_top;
+	vcpu->run->cca_exit.pa_base  = pa_base;
+	vcpu->run->cca_exit.response = 0;
+}
+
+static int rec_exit_vdev_validate_mapping(struct kvm_vcpu *vcpu)
+{
+	struct kvm *kvm = vcpu->kvm;
+	struct realm *realm = &kvm->arch.realm;
+	struct realm_rec *rec = &vcpu->arch.rec;
+	unsigned long base = rec->run->exit.dev_mem_base;
+	unsigned long top = rec->run->exit.dev_mem_top;
+
+	if (!kvm_realm_is_private_address(realm, base) ||
+	    !kvm_realm_is_private_address(realm, top - 1)) {
+
+		vcpu->run->cca_exit.response = -EINVAL;
+		/* return to guest */
+		return 1;
+	}
+
+	kvm_prepare_vdev_validate_mapping_exit(vcpu, base, top, rec->run->exit.dev_mem_pa,
+					       rec->run->exit.vdev_id_1);
+	return 0;
+}
+
 static void update_arch_timer_irq_lines(struct kvm_vcpu *vcpu)
 {
 	struct realm_rec *rec = &vcpu->arch.rec;
@@ -198,6 +233,8 @@ int handle_rec_exit(struct kvm_vcpu *vcpu, int rec_run_ret)
 		return rec_exit_ripas_change(vcpu);
 	case RMI_EXIT_HOST_CALL:
 		return rec_exit_host_call(vcpu);
+	case RMI_EXIT_VDEV_VALIDATE_MAPPING:
+		return rec_exit_vdev_validate_mapping(vcpu);
 	}
 
 	kvm_pr_unimpl("Unsupported exit reason: %u\n",
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index f33d17ca855d..3a549dc87906 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -1283,6 +1283,192 @@ static void kvm_complete_ripas_change(struct kvm_vcpu *vcpu)
 	rec->run->exit.ripas_base = base;
 }
 
+static int rmi_rtt_dev_map(unsigned long rd_phys, unsigned long vdev_phys,
+		unsigned long base, unsigned long top, unsigned long flags,
+		unsigned long oaddr, unsigned long *out_top, unsigned long *rmi_ret)
+{
+	struct rmi_sro_state *sro __free(sro) =
+		rmi_sro_init(SMC_RMI_RTT_DEV_MAP, rd_phys, vdev_phys, base, top, flags, oaddr);
+	if (!sro)
+		return -ENOMEM;
+
+	*rmi_ret = rmi_sro_execute(sro);
+	if (*rmi_ret)
+		return 0;
+
+	*out_top = sro->regs.a1;
+
+	return 0;
+}
+
+static int rmi_rtt_dev_validate(unsigned long rd_phys, unsigned long rec_phys,
+		unsigned long base, unsigned long top, unsigned long *out_top,
+		unsigned long *rmi_ret)
+{
+	struct rmi_sro_state *sro __free(sro) =
+		rmi_sro_init(SMC_RMI_RTT_DEV_VALIDATE, rd_phys,
+			     rec_phys, base, top);
+	if (!sro)
+		return -ENOMEM;
+
+	*rmi_ret = rmi_sro_execute(sro);
+	if (*rmi_ret)
+		return 0;
+
+	*out_top = sro->regs.a1;
+
+	return 0;
+}
+
+/*
+ * Even though we can map larger block, since we need to delegate each granule.
+ * We map granule size and fold
+ */
+static int __realm_dev_mem_map(struct kvm *kvm, struct kvm_mmu_memory_cache *cache,
+		unsigned long pdev_phys, unsigned long vdev_phys,
+		unsigned long start_ipa, unsigned long end_ipa,
+		phys_addr_t phys, unsigned long *top_ipa)
+{
+	int ret = 0;
+	unsigned long rmi_ret;
+	unsigned long ipa = start_ipa, next_ipa;
+	struct realm *realm = &kvm->arch.realm;
+	phys_addr_t rd_phys = virt_to_phys(realm->rd);
+
+	if (rmi_delegate_range(phys, end_ipa - start_ipa))
+		return -EINVAL;
+
+	while (ipa < end_ipa) {
+		unsigned long flags = RMI_ADDR_TYPE_SINGLE;
+		unsigned long range_desc = addr_range_desc(phys, end_ipa - ipa);
+
+		ret = rmi_rtt_dev_map(rd_phys, vdev_phys, ipa, end_ipa, flags,
+				      range_desc, &next_ipa, &rmi_ret);
+		if (ret)
+			goto err_undelegate_tail;
+
+		if (RMI_RETURN_STATUS(rmi_ret) == RMI_ERROR_RTT) {
+			/* Create missing RTTs and retry */
+			int level = RMI_RETURN_INDEX(rmi_ret);
+
+			WARN_ON(level == RMM_RTT_MAX_LEVEL);
+
+			if (kvm_mmu_memory_cache_nr_free_objects(cache) <
+			    (RMM_RTT_MAX_LEVEL - level)) {
+				ret = -ENOMEM;
+				goto err_undelegate_tail;
+			}
+
+			ret = realm_create_rtt_levels(realm, ipa, level,
+						      RMM_RTT_MAX_LEVEL,
+						      cache);
+			if (ret)
+				goto err_undelegate_tail;
+
+			ret = rmi_rtt_dev_map(rd_phys, vdev_phys, ipa, end_ipa, flags,
+					      range_desc, &next_ipa, &rmi_ret);
+			if (ret)
+				goto err_undelegate_tail;
+		}
+
+		if (WARN_ON(rmi_ret != RMI_SUCCESS)) {
+			ret = -EIO;
+			goto err_undelegate_tail;
+		}
+
+		phys += next_ipa - ipa;
+		ipa = next_ipa;
+	}
+	/*
+	 * successfully mapped the provided range, return the top_ipa
+	 */
+	*top_ipa = end_ipa;
+	return 0;
+
+err_undelegate_tail:
+	*top_ipa = ipa;
+	/*
+	 * undelegate the tail range. Rest will be done by the caller.
+	 */
+	if (end_ipa > ipa)
+		WARN_ON(rmi_undelegate_range(phys, end_ipa - ipa));
+
+	return ret;
+}
+
+int realm_dev_mem_map(struct kvm *kvm, unsigned long pdev_phys,
+		unsigned long vdev_phys, unsigned long start_ipa,
+		unsigned long end_ipa, unsigned long start_pa)
+{
+	int ret;
+	unsigned long top_ipa;
+	unsigned long base_ipa = start_ipa;
+	struct kvm_s2_mmu *mmu = &kvm->arch.mmu;
+	struct kvm_mmu_memory_cache cache = { .gfp_zero = __GFP_ZERO };
+
+	do {
+		ret = kvm_mmu_topup_memory_cache(&cache,
+						 kvm_mmu_cache_min_pages(mmu));
+		if (ret)
+			break;
+
+		write_lock(&kvm->mmu_lock);
+		ret = __realm_dev_mem_map(kvm, &cache, pdev_phys, vdev_phys,
+					  start_ipa, end_ipa, start_pa, &top_ipa);
+		write_unlock(&kvm->mmu_lock);
+
+		/* update base before we break out of loop*/
+		start_pa += top_ipa - start_ipa;
+		start_ipa = top_ipa;
+		if (ret && ret != -ENOMEM)
+			break;
+	} while (start_ipa < end_ipa);
+
+	kvm_mmu_free_memory_cache(&cache);
+
+	if (!ret) {
+		/* fold rtts if we can */
+		for (start_ipa = ALIGN(base_ipa, RMM_L2_BLOCK_SIZE);
+		     ((start_ipa + RMM_L2_BLOCK_SIZE) < end_ipa); start_ipa += RMM_L2_BLOCK_SIZE)
+			fold_rtt(&kvm->arch.realm, start_ipa, RMM_RTT_BLOCK_LEVEL);
+	}
+
+	return ret;
+}
+EXPORT_SYMBOL_GPL(realm_dev_mem_map);
+
+static void kvm_complete_vdev_map_validate(struct kvm_vcpu *vcpu)
+{
+	struct kvm *kvm = vcpu->kvm;
+	struct realm_rec *rec = &vcpu->arch.rec;
+	struct kvm_run *run = vcpu->run;
+	struct realm *realm = &kvm->arch.realm;
+	phys_addr_t rd_phys = virt_to_phys(realm->rd);
+	phys_addr_t rec_phys = virt_to_phys(rec->rec_page);
+
+	/* reject the vdev_map validate request  */
+	if (run->cca_exit.response) {
+		rec->run->enter.flags = REC_ENTER_FLAG_DEV_MEM_RESPONSE;
+	} else {
+		unsigned long next_ipa;
+		unsigned long start_ipa = run->cca_exit.gpa_base;
+
+		while (start_ipa < run->cca_exit.gpa_top) {
+			int ret;
+			unsigned long rmi_ret;
+
+			ret = rmi_rtt_dev_validate(rd_phys, rec_phys, start_ipa,
+					   run->cca_exit.gpa_top, &next_ipa,
+					   &rmi_ret);
+			if (ret || rmi_ret) {
+				rec->run->enter.flags = REC_ENTER_FLAG_DEV_MEM_RESPONSE;
+				break;
+			}
+			start_ipa = next_ipa;
+		}
+	}
+}
+
 /*
  * kvm_rec_pre_enter - Complete operations before entering a REC
  *
@@ -1311,6 +1497,9 @@ int kvm_rec_pre_enter(struct kvm_vcpu *vcpu)
 	case RMI_EXIT_RIPAS_CHANGE:
 		kvm_complete_ripas_change(vcpu);
 		break;
+	case RMI_EXIT_VDEV_VALIDATE_MAPPING:
+		kvm_complete_vdev_map_validate(vcpu);
+		break;
 	}
 
 	return 1;
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index 855427935f2d..66e0acadf743 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -585,6 +585,33 @@ static ssize_t cca_tsm_guest_req(struct pci_tdi *tdi, enum pci_tsm_req_scope sco
 			return -EINVAL;
 		}
 	}
+	case PCI_TSM_REQ_STATE_CHANGE:
+	{
+		u32 req_type;
+
+		if (get_user(req_type, (u32 __user *)req.user))
+			return -EFAULT;
+
+		switch (req_type) {
+
+		case __REC_DA_VDEV_MAP:
+		{
+			struct arm64_vdev_device_memmap_guest_req req_obj;
+
+			if (req_len != sizeof(req_obj))
+				return -EINVAL;
+
+			if (copy_from_user((void *)&req_obj, req.user, req_len))
+				return -EFAULT;
+
+			return cca_vdev_device_map(pdev, req_obj.gpa_base,
+						   req_obj.gpa_top,
+						   req_obj.pa_base);
+		}
+		default:
+			return -EINVAL;
+		}
+	}
 	default:
 		return -EINVAL;
 	}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index ec7701ff7e03..543c40fb1160 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -1377,3 +1377,24 @@ int cca_vdev_update_device_measurements(struct pci_dev *pdev, unsigned long flag
 	/* get and update the interface report cache. */
 	return vdev_update_device_measurements_cache(pdev);
 }
+
+int cca_vdev_device_map(struct pci_dev *pdev, unsigned long gpa_base,
+		unsigned long gpa_top, unsigned long pa_base)
+{
+	struct kvm *kvm;
+	struct realm *realm;
+	phys_addr_t rmm_pdev_phys;
+	phys_addr_t rmm_vdev_phys;
+	struct cca_host_tdi *host_tdi;
+	struct cca_host_pdev_dsc *pdev_dsc;
+
+	host_tdi = to_cca_host_tdi(pdev);
+	pdev_dsc = to_cca_pdev_dsc(pdev->tsm->dsm_dev);
+	kvm = host_tdi->tdi.kvm;
+	realm = &kvm->arch.realm;
+	rmm_vdev_phys = virt_to_phys(host_tdi->rmm_vdev);
+	rmm_pdev_phys = virt_to_phys(pdev_dsc->rmm_pdev);
+
+	return realm_dev_mem_map(kvm, rmm_pdev_phys, rmm_vdev_phys,
+				 gpa_base, gpa_top, pa_base);
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index 621e0858f0c6..3dfb6b3cc2ef 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -250,5 +250,7 @@ int cca_vdev_read_cached_object(struct pci_dev *pdev, int type, unsigned long of
 		unsigned long max_len, void __user *user_buf);
 int cca_vdev_update_interface_report(struct pci_dev *pdev);
 int cca_vdev_update_device_measurements(struct pci_dev *pdev, unsigned long flags, u8 *nonce);
+int cca_vdev_device_map(struct pci_dev *pdev, unsigned long gpa_base,
+		unsigned long gpa_top, unsigned long pa_base);
 
 #endif
diff --git a/include/uapi/linux/kvm.h b/include/uapi/linux/kvm.h
index 309f058cf2f8..bac41f2b13e4 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -192,6 +192,7 @@ struct kvm_exit_snp_req_certs {
 #define KVM_EXIT_ARM_SEA          41
 #define KVM_EXIT_ARM_LDST64B      42
 #define KVM_EXIT_SNP_REQ_CERTS    43
+#define KVM_EXIT_ARM64_TIO	  44
 
 /* For KVM_EXIT_INTERNAL_ERROR */
 /* Emulate instruction failed. */
@@ -496,6 +497,16 @@ struct kvm_run {
 		} arm_sea;
 		/* KVM_EXIT_SNP_REQ_CERTS */
 		struct kvm_exit_snp_req_certs snp_req_certs;
+		/* KVM_EXIT_ARM64_TIO*/
+		struct {
+			__u64 flags;
+			__u64 nr;
+			__u64 vdev_id;
+			__u64 gpa_base;
+			__u64 gpa_top; /* input and output */
+			__u64 pa_base;
+			__u64 response;
+		} cca_exit;
 		/* Fix the size of the union. */
 		char padding[256];
 	};

---

## [15] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 14/16] KVM: arm64: Unmap device mappings when a private granule is destroyed*

Ensure tearing down a private granule also tears down any RMM device
mapping by reading the RTT entry, invoking the new RMI_VDEV_MEM_UNMAP,
and remembering the entry’s RIPAS so we only free RAM pages.

Drive the device-unmap path when RIPAS transitions to EMPTY. Also roll
back partially built device maps when errors occur.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_smc.h |  1 +
 arch/arm64/kvm/rmi.c             | 87 ++++++++++++++++++++++++++++++--
 2 files changed, 83 insertions(+), 5 deletions(-)

diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 6bbabcd853bd..f3ad545d68b7 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -199,6 +199,7 @@ enum rmi_ripas {
 	RMI_EMPTY = 0,
 	RMI_RAM = 1,
 	RMI_DESTROYED = 2,
+	RMI_DEV = 3,
 };
 
 #define RMI_NO_MEASURE_CONTENT	0
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 3a549dc87906..cc9e045dcae9 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -720,6 +720,11 @@ static int realm_create_rd(struct kvm *kvm)
 	return r;
 }
 
+static int rmi_rtt_dev_unmap(unsigned long rd_phys,
+		unsigned long base, unsigned long top,
+		unsigned long *out_ipa, unsigned long *out_desc,
+		unsigned long *rmi_ret);
+
 static void realm_unmap_private_range(struct kvm *kvm,
 				      unsigned long start,
 				      unsigned long end,
@@ -728,16 +733,33 @@ static void realm_unmap_private_range(struct kvm *kvm,
 	struct realm *realm = &kvm->arch.realm;
 	unsigned long rd = virt_to_phys(realm->rd);
 	unsigned long next_addr, addr;
+	struct rtt_entry rtt_entry;
 	int ret;
 
+	/* Called with mmu_lock held, so RTT entry can't change. */
+	lockdep_assert_held_write(&kvm->mmu_lock);
+
+	/* An unmap request won't mix different RIPAS ranges. */
+	if (rmi_rtt_read_entry(rd, start, RMM_RTT_MAX_LEVEL, &rtt_entry))
+		return;
+
 	for (addr = start; addr < end; addr = next_addr) {
+		unsigned long rmi_ret;
 		unsigned long out_range;
 		unsigned long flags = RMI_ADDR_TYPE_SINGLE;
 		/* TODO: Optimise using RMI_ADDR_TYPE_LIST */
 
 retry:
-		ret = rmi_rtt_data_unmap(rd, addr, end, flags, 0,
-					 &next_addr, &out_range, NULL);
+		if (rtt_entry.ripas == RMI_DEV)
+			ret = rmi_rtt_dev_unmap(rd, addr, end,
+						&next_addr, &out_range,
+						&rmi_ret);
+		else
+			ret = rmi_rtt_data_unmap(rd, addr, end, flags, 0,
+						 &next_addr, &out_range, NULL);
+
+		if (!ret && rtt_entry.ripas == RMI_DEV)
+			ret = rmi_ret;
 
 		if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
 			phys_addr_t rtt;
@@ -763,6 +785,7 @@ static void realm_unmap_private_range(struct kvm *kvm,
 		if (WARN_ON(ret))
 			break;
 
+		//FIXME!! where are we freeing the private page?
 		if (may_block)
 			cond_resched_rwlock_write(&kvm->mmu_lock);
 	}
@@ -1152,10 +1175,27 @@ static int realm_set_ipa_state(struct kvm_vcpu *vcpu,
 			       unsigned long *top_ipa)
 {
 	struct kvm *kvm = vcpu->kvm;
-	int ret = ripas_change(kvm, vcpu, start, end, RIPAS_SET, top_ipa);
+	int ret;
 
-	if (ripas == RMI_EMPTY && *top_ipa != start)
-		realm_unmap_private_range(kvm, start, *top_ipa, false);
+	/*
+	 * We use the RIPAS value to decide between a data_destroy or a
+	 * dev_mem_unmap. Hence call realm_unmap_private_range() before
+	 * ripas_change().
+	 *
+	 * Technically, for private RAM, we don't need to call
+	 * realm_unmap_private_range(), because any RIPAS change via RSI would
+	 * trigger a memory fault exit. That would, in turn, invalidate the
+	 * guest's memfd range, which then triggers realm_unmap_private_range()
+	 * automatically.
+	 *
+	 * However, this doesn’t apply to RIPAS_DEV, because we currently
+	 * lack a user-space API to call realm_dev_mem_unmap() in response to a
+	 * memory fault exit. Therefore, the unmap must happen explicitly before
+	 * the RIPAS change.
+	 */
+	if (ripas == RMI_EMPTY)
+		realm_unmap_private_range(kvm, start, end, false);
+	ret = ripas_change(kvm, vcpu, start, end, RIPAS_SET, top_ipa);
 
 	return ret;
 }
@@ -1301,6 +1341,27 @@ static int rmi_rtt_dev_map(unsigned long rd_phys, unsigned long vdev_phys,
 	return 0;
 }
 
+static int rmi_rtt_dev_unmap(unsigned long rd_phys,
+		unsigned long base, unsigned long top,
+		unsigned long *out_ipa, unsigned long *out_desc,
+		unsigned long *rmi_ret)
+{
+	unsigned long flags = RMI_ADDR_TYPE_SINGLE;
+	struct rmi_sro_state *sro __free(sro) =
+		rmi_sro_init(SMC_RMI_RTT_DEV_UNMAP, rd_phys, base, top, flags, NULL);
+	if (!sro)
+		return -ENOMEM;
+
+	*rmi_ret = rmi_sro_execute(sro);
+	if (*rmi_ret)
+		return 0;
+
+	*out_ipa = sro->regs.a1;
+	*out_desc = sro->regs.a2;
+
+	return 0;
+}
+
 static int rmi_rtt_dev_validate(unsigned long rd_phys, unsigned long rec_phys,
 		unsigned long base, unsigned long top, unsigned long *out_top,
 		unsigned long *rmi_ret)
@@ -1401,9 +1462,12 @@ int realm_dev_mem_map(struct kvm *kvm, unsigned long pdev_phys,
 		unsigned long end_ipa, unsigned long start_pa)
 {
 	int ret;
+	unsigned long rmi_ret;
 	unsigned long top_ipa;
 	unsigned long base_ipa = start_ipa;
+	struct realm *realm = &kvm->arch.realm;
 	struct kvm_s2_mmu *mmu = &kvm->arch.mmu;
+	phys_addr_t rd_phys = virt_to_phys(realm->rd);
 	struct kvm_mmu_memory_cache cache = { .gfp_zero = __GFP_ZERO };
 
 	do {
@@ -1431,6 +1495,19 @@ int realm_dev_mem_map(struct kvm *kvm, unsigned long pdev_phys,
 		for (start_ipa = ALIGN(base_ipa, RMM_L2_BLOCK_SIZE);
 		     ((start_ipa + RMM_L2_BLOCK_SIZE) < end_ipa); start_ipa += RMM_L2_BLOCK_SIZE)
 			fold_rtt(&kvm->arch.realm, start_ipa, RMM_RTT_BLOCK_LEVEL);
+	} else {
+		/* unmap the partial mapping. [base_ipa, start_ipa) */
+		while (start_ipa > base_ipa) {
+			unsigned long out_ipa;
+			unsigned long out_range;
+
+			ret = rmi_rtt_dev_unmap(rd_phys, base_ipa, start_ipa,
+					&out_ipa, &out_range, &rmi_ret);
+			if (ret || (rmi_ret != RMI_SUCCESS))
+				break;
+			WARN_ON(undelegate_range_desc(out_range));
+			base_ipa = out_ipa;
+		}
 	}
 
 	return ret;

---

## [16] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 15/16] coco: host: arm64: Transition vdevs to TDISP RUN state*

Add host-side support for guest requests that move a vdev into the TDISP
RUN state.

Introduce the RMI helper for VDEV_START and a matching guest request
payload for VDEV_SET_TDI_STATE. In the host CCA TSM request handler, accept
only RHI_DA_TDI_CONFIG_RUN on the state-change path and invoke a new
cca_vdev_device_start() helper.

The start helper issues RMI_VDEV_START for the bound pdev/vdev pair and
then waits until firmware reports the vdev in the RMI_VDEV_STARTED state
before returning to the caller.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h        | 11 +++++++++++
 arch/arm64/include/uapi/asm/rmi-da.h     |  6 ++++++
 drivers/virt/coco/arm-cca-host/arm-cca.c | 15 +++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.c  | 22 ++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.h  |  1 +
 5 files changed, 55 insertions(+)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 350fd9bc93a4..19eba97a6c7b 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -993,4 +993,15 @@ rmi_vdev_get_device_measurements(unsigned long rd, unsigned long pdev_phys,
 
 	return res.a0;
 }
+
+static inline unsigned long rmi_vdev_start(unsigned long rd, unsigned long pdev_phys,
+					   unsigned long vdev_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_START, rd, pdev_phys, vdev_phys, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/uapi/asm/rmi-da.h b/arch/arm64/include/uapi/asm/rmi-da.h
index 572afb4095f2..c0cfcadfae47 100644
--- a/arch/arm64/include/uapi/asm/rmi-da.h
+++ b/arch/arm64/include/uapi/asm/rmi-da.h
@@ -38,4 +38,10 @@ struct arm64_vdev_device_memmap_guest_req {
 };
 #define __REC_DA_VDEV_MAP		0x5
 
+struct arm64_vdev_set_tdi_state_guest_req {
+	__u32 req_type;
+	__u32 tdi_state;
+};
+#define __RHI_DA_VDEV_SET_TDI_STATE	0x6
+
 #endif
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index 66e0acadf743..3a682352fb68 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -608,6 +608,21 @@ static ssize_t cca_tsm_guest_req(struct pci_tdi *tdi, enum pci_tsm_req_scope sco
 						   req_obj.gpa_top,
 						   req_obj.pa_base);
 		}
+		case __RHI_DA_VDEV_SET_TDI_STATE:
+		{
+			struct arm64_vdev_set_tdi_state_guest_req req_obj;
+
+			if (req_len != sizeof(req_obj))
+				return -EINVAL;
+
+			if (copy_from_user((void *)&req_obj, req.user, req_len))
+				return -EFAULT;
+
+			if (req_obj.tdi_state != RHI_DA_TDI_CONFIG_RUN)
+				return -EINVAL;
+
+			return cca_vdev_device_start(pdev);
+		}
 		default:
 			return -EINVAL;
 		}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index 543c40fb1160..60b750c961ea 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -1398,3 +1398,25 @@ int cca_vdev_device_map(struct pci_dev *pdev, unsigned long gpa_base,
 	return realm_dev_mem_map(kvm, rmm_pdev_phys, rmm_vdev_phys,
 				 gpa_base, gpa_top, pa_base);
 }
+
+int cca_vdev_device_start(struct pci_dev *pdev)
+{
+	phys_addr_t rmm_pdev_phys;
+	phys_addr_t rmm_vdev_phys;
+	struct cca_host_pdev_dsc *pdev_dsc;
+	struct cca_host_tdi *host_tdi;
+	struct realm *realm;
+	phys_addr_t rd_phys;
+
+	host_tdi = to_cca_host_tdi(pdev);
+	rmm_vdev_phys = virt_to_phys(host_tdi->rmm_vdev);
+	realm = &host_tdi->tdi.kvm->arch.realm;
+	rd_phys = virt_to_phys(realm->rd);
+
+	pdev_dsc = to_cca_pdev_dsc(pdev->tsm->dsm_dev);
+	rmm_pdev_phys = virt_to_phys(pdev_dsc->rmm_pdev);
+
+	if (rmi_vdev_start(rd_phys, rmm_pdev_phys, rmm_vdev_phys))
+		return -ENXIO;
+	return submit_vdev_state_transition_work(pdev, RMI_VDEV_STARTED);
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index 3dfb6b3cc2ef..3082166038c3 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -252,5 +252,6 @@ int cca_vdev_update_interface_report(struct pci_dev *pdev);
 int cca_vdev_update_device_measurements(struct pci_dev *pdev, unsigned long flags, u8 *nonce);
 int cca_vdev_device_map(struct pci_dev *pdev, unsigned long gpa_base,
 		unsigned long gpa_top, unsigned long pa_base);
+int cca_vdev_device_start(struct pci_dev *pdev);
 
 #endif

---

## [17] Aneesh Kumar K.V (Arm) — 2026-04-27
*Subject: [RFC PATCH v4 16/16] KVM: arm64: CCA: enable DA in realm create parameters*

Now that we have all the required steps for DA in-place, enable
DA while creating realm.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_smc.h | 1 +
 arch/arm64/kvm/rmi.c             | 3 +++
 2 files changed, 4 insertions(+)

diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index f3ad545d68b7..c02e2f087b1c 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -268,6 +268,7 @@ struct rmm_config {
 #define RMI_REALM_PARAM_FLAG_LPA2		BIT(0)
 #define RMI_REALM_PARAM_FLAG_SVE		BIT(1)
 #define RMI_REALM_PARAM_FLAG_PMU		BIT(2)
+#define RMI_REALM_PARAM_FLAG_DA			BIT(3)
 
 struct realm_params {
 	union { /* 0x0 */
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index cc9e045dcae9..e041c4caee79 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -691,6 +691,9 @@ static int realm_create_rd(struct kvm *kvm)
 	if (r)
 		goto out_undelegate_tables;
 
+	/* For now default enable DA */
+	if (rmm_has_reg2_feature(RMI_FEATURE_REGISTER_2_DA))
+		params->flags |= RMI_REALM_PARAM_FLAG_DA;
 	params_phys = virt_to_phys(params);
 
 	if (rmi_realm_create(rd_phys, params_phys)) {

---
