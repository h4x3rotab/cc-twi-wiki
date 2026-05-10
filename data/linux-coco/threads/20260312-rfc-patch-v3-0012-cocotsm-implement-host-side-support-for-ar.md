---
title: '[RFC PATCH v3 00/12] coco/TSM: Implement host-side support for Arm CCA TDISP setup'
date: 2026-03-12
last_reply: 2026-03-12
message_count: 13
participants: ['Aneesh Kumar K.V (Arm)']
---

## [1] Aneesh Kumar K.V (Arm) — 2026-03-12

This patch series implements the host-side changes needed for end-to-end
Arm CCA TDISP setup. It adds the RMI/RHI plumbing required to create and
manage Realm vdev objects, service device-attestation object requests, and
complete the KVM/RMM flows needed for device run-time transitions.

The series is based on the RMM ALP17 specification [1] and the
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
available at [4].

Previous posting:
rfc-v1: https://lore.kernel.org/all/20250728135216.48084-1-aneesh.kumar@kernel.org
There is no rfc-v2 posting. This series is marked rfc-v3 to stay aligned
with the rest of the CCA patchsets that are being posted as v3.

Changes from v1:
- rebase to latest kernel and core TSM changes
- address review feedback

[1] https://developer.arm.com/-/cdn-downloads/permalink/Architectures/Armv9/DEN0137_1.1-alp17.zip
[2] https://lore.kernel.org/all/20260303000207.1836586-1-dan.j.williams@intel.com
[3] https://lore.kernel.org/all/461fa23f-9add-40e5-a0d0-759030e7c70b@arm.com
[4] https://gitlab.arm.com/linux-arm/linux-cca.git cca/topics/cca-tdisp-upstream-rfc-v3
[5] https://developer.arm.com/documentation/den0148/latest/ RHI

Aneesh Kumar K.V (Arm) (12):
  coco: host: arm64: Add support for virtual device communication
  coco: host: arm64: Add support for RMM vdev objects
  coco: host: arm64: Add helpers to unlock and destroy RMM vdev
  coco: host: arm64: Add support for da object read RHI handling
  coco: host: arm64: Add helper for cached object fetches
  coco: host: arm64: Fetch interface report via RMI
  coco: host: arm64: Fetch device measurements via RMI
  coco: host: KVM: arm64: Handle vdev request exits and completion
  coco: host: KVM: arm64: Handle vdev map/validation exits
  KVM: arm64: Unmap device mappings when a private granule is destroyed
  coco: host: arm64: Transition vdevs to TDISP RUN state
  KVM: arm64: CCA: enable DA in realm create parameters

 Documentation/virt/kvm/api.rst           |  22 +
 arch/arm64/include/asm/kvm_rmi.h         |   4 +
 arch/arm64/include/asm/rhi.h             |   9 +
 arch/arm64/include/asm/rmi_cmds.h        | 163 +++++++
 arch/arm64/include/asm/rmi_smc.h         |  75 +++-
 arch/arm64/include/uapi/asm/rmi-da.h     |  43 ++
 arch/arm64/kvm/rmi-exit.c                |  55 +++
 arch/arm64/kvm/rmi.c                     | 183 +++++++-
 drivers/virt/coco/arm-cca-host/arm-cca.c | 200 +++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.c  | 544 ++++++++++++++++++++++-
 drivers/virt/coco/arm-cca-host/rmi-da.h  |  39 ++
 include/linux/kvm_host.h                 |   1 +
 include/uapi/linux/kvm.h                 |  10 +
 virt/kvm/kvm_main.c                      |   6 +
 14 files changed, 1337 insertions(+), 17 deletions(-)
 create mode 100644 arch/arm64/include/uapi/asm/rmi-da.h

---

## [2] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 01/12] coco: host: arm64: Add support for virtual device communication*

Add support for vdev_communicate with RMM.

Cc: Marc Zyngier <maz@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h       | 31 +++++++++++++
 arch/arm64/include/asm/rmi_smc.h        | 10 +++++
 drivers/virt/coco/arm-cca-host/rmi-da.c | 60 ++++++++++++++++++++++---
 drivers/virt/coco/arm-cca-host/rmi-da.h | 20 +++++++++
 4 files changed, 114 insertions(+), 7 deletions(-)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 339bea517760..0754d420faad 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -583,4 +583,35 @@ static inline unsigned long rmi_pdev_set_pubkey(unsigned long pdev_phys, unsigne
 	return res.a0;
 }
 
+static inline unsigned long rmi_vdev_communicate(unsigned long rd_phys,
+						 unsigned long pdev_phys,
+						 unsigned long vdev_phys,
+						 unsigned long vdev_comm_data_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_COMMUNICATE, rd_phys,
+			     pdev_phys, vdev_phys, vdev_comm_data_phys, &res);
+
+	return res.a0;
+}
+
+static inline unsigned long rmi_vdev_get_state(unsigned long vdev_phys, enum rmi_vdev_state *state)
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
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 907e00f4855a..14a2090cbac8 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -54,6 +54,9 @@
 #define SMC_RMI_PDEV_GET_STATE		SMC_RMI_CALL(0x0178)
 #define SMC_RMI_PDEV_SET_PUBKEY		SMC_RMI_CALL(0x017b)
 #define SMC_RMI_PDEV_STOP		SMC_RMI_CALL(0x017c)
+#define SMC_RMI_VDEV_ABORT		SMC_RMI_CALL(0x0185)
+#define SMC_RMI_VDEV_COMMUNICATE	SMC_RMI_CALL(0x0186)
+#define SMC_RMI_VDEV_GET_STATE		SMC_RMI_CALL(0x0189)
 
 #define RMI_ABI_MAJOR_VERSION	1
 #define RMI_ABI_MINOR_VERSION	0
@@ -445,4 +448,11 @@ struct rmi_public_key_params {
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
index 029758ada136..af0632544911 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -11,6 +11,8 @@
 #include <crypto/internal/rsa.h>
 #include <keys/asymmetric-type.h>
 #include <keys/x509-parser.h>
+#include <linux/kvm_types.h>
+#include <asm/kvm_rmi.h>
 
 #include "rmi-da.h"
 
@@ -209,6 +211,7 @@ static int _do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm)
 	int nbytes, cp_len;
 	struct cache_object **cache_objp, *cache_obj;
 	struct cca_host_pf0_dsc *pf0_dsc = to_cca_pf0_dsc(tsm->dsm_dev);
+	struct cca_host_tdi *host_tdi = to_cca_host_tdi(tsm->pdev);
 	struct cca_host_comm_data *comm_data = to_cca_comm_data(tsm->pdev);
 	struct rmi_dev_comm_enter *io_enter = &comm_data->io_params->enter;
 	struct rmi_dev_comm_exit *io_exit = &comm_data->io_params->exit;
@@ -219,7 +222,11 @@ static int _do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm)
 		rmi_ret = rmi_pdev_communicate(virt_to_phys(pf0_dsc->rmm_pdev),
 					       virt_to_phys(comm_data->io_params));
 	else
-		rmi_ret = RMI_ERROR_INPUT;
+		rmi_ret = rmi_vdev_communicate(virt_to_phys(host_tdi->realm->rd),
+					       virt_to_phys(pf0_dsc->rmm_pdev),
+					       virt_to_phys(host_tdi->rmm_vdev),
+					       virt_to_phys(comm_data->io_params));
+
 	if (rmi_ret != RMI_SUCCESS) {
 		if (rmi_ret == RMI_BUSY)
 			return -EBUSY;
@@ -236,6 +243,12 @@ static int _do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm)
 		case RMI_DEV_CERTIFICATE:
 			cache_objp = &pf0_dsc->cert_chain.cache;
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
@@ -337,9 +350,11 @@ static int _do_dev_communicate(enum dev_comm_type type, struct pci_tsm *tsm)
 static int do_dev_communicate(enum dev_comm_type type,
 				struct pci_tsm *tsm, unsigned long error_state)
 {
-	int ret, state = error_state;
+	int ret, state;
+	unsigned long rmi_ret;
 	struct rmi_dev_comm_enter *io_enter;
 	struct cca_host_pf0_dsc *pf0_dsc = to_cca_pf0_dsc(tsm->dsm_dev);
+	struct cca_host_tdi *host_tdi = to_cca_host_tdi(tsm->pdev);
 
 	io_enter = &pf0_dsc->comm_data.io_params->enter;
 	io_enter->resp_len = 0;
@@ -349,16 +364,23 @@ static int do_dev_communicate(enum dev_comm_type type,
 	if (ret) {
 		if (type == PDEV_COMMUNICATE)
 			rmi_pdev_abort(virt_to_phys(pf0_dsc->rmm_pdev));
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
-			if (rmi_pdev_get_state(virt_to_phys(pf0_dsc->rmm_pdev),
-					       (enum rmi_pdev_state *)&state))
-				state = error_state;
-		}
+		if (type == PDEV_COMMUNICATE)
+			rmi_ret = rmi_pdev_get_state(virt_to_phys(pf0_dsc->rmm_pdev),
+						     (enum rmi_pdev_state *)&state);
+		else
+			rmi_ret = rmi_vdev_get_state(virt_to_phys(host_tdi->rmm_vdev),
+						     (enum rmi_vdev_state *)&state);
+		if (rmi_ret)
+			state = error_state;
 	}
 
 	if (state == error_state)
@@ -637,3 +659,27 @@ void cca_pdev_stop_and_destroy(struct pci_dev *pdev)
 		free_page((unsigned long)pf0_dsc->rmm_pdev);
 	pf0_dsc->rmm_pdev = NULL;
 }
+
+static int wait_for_vdev_state(struct pci_tsm *tsm, enum rmi_vdev_state target_state)
+{
+	return wait_for_dev_state(VDEV_COMMUNICATE, tsm, target_state, RMI_VDEV_ERROR);
+}
+
+static __maybe_unused void vdev_state_transition_workfn(struct work_struct *work)
+{
+	unsigned long state;
+	struct pci_tsm *tsm;
+	struct dev_comm_work *setup_work;
+	struct cca_host_pf0_dsc *pf0_dsc;
+
+	setup_work = container_of(work, struct dev_comm_work, work);
+	tsm = setup_work->tsm;
+
+	pf0_dsc = to_cca_pf0_dsc(tsm->dsm_dev);
+	guard(mutex)(&pf0_dsc->object_lock);
+
+	state = wait_for_vdev_state(tsm, setup_work->target_state);
+	WARN_ON(state != setup_work->target_state);
+
+	complete(&setup_work->complete);
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index 38550103c2a5..914a3c297c24 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -82,6 +82,16 @@ struct cca_host_fn_dsc {
 
 enum dev_comm_type {
 	PDEV_COMMUNICATE = 0x1,
+	VDEV_COMMUNICATE = 0x2,
+};
+
+struct cca_host_tdi {
+	struct pci_tdi tdi;
+	struct realm *realm;
+	void *rmm_vdev;
+	/* protected by cca_host_pf0_dsc.object_lock */
+	struct cache_object *interface_report;
+	struct cache_object *measurements;
 };
 
 static inline struct cca_host_pf0_dsc *to_cca_pf0_dsc(struct pci_dev *pdev)
@@ -116,6 +126,16 @@ static inline struct cca_host_comm_data *to_cca_comm_data(struct pci_dev *pdev)
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
 int cca_pdev_ide_setup(struct pci_dev *pdev);
 void cca_pdev_stop_and_destroy(struct pci_dev *pdev);

---

## [3] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 02/12] coco: host: arm64: Add support for RMM vdev objects*

An RMM vdev object represents the binding between a device function and
a Realm. For example, a vdev can represent a physical function of a PCIe
device or a virtual function of a multi-function PCIe device. Each vdev
is associated with one pdev.

Cc: Marc Zyngier <maz@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h        |  25 ++++++
 arch/arm64/include/asm/rmi_smc.h         |  24 +++++
 drivers/virt/coco/arm-cca-host/arm-cca.c |  25 ++++++
 drivers/virt/coco/arm-cca-host/rmi-da.c  | 110 ++++++++++++++++++++++-
 drivers/virt/coco/arm-cca-host/rmi-da.h  |   2 +
 5 files changed, 185 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 0754d420faad..2a86de5eb160 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -614,4 +614,29 @@ static inline unsigned long rmi_vdev_abort(unsigned long vdev_phys)
 
 	return res.a0;
 }
+
+static inline unsigned long rmi_vdev_create(unsigned long rd,
+					    unsigned long pdev_phys,
+					    unsigned long vdev_phys,
+					    unsigned long vdev_params_phys)
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
+					  unsigned long pdev_phys,
+					  unsigned long vdev_phys)
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
index 14a2090cbac8..20c36a01df94 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -56,8 +56,11 @@
 #define SMC_RMI_PDEV_STOP		SMC_RMI_CALL(0x017c)
 #define SMC_RMI_VDEV_ABORT		SMC_RMI_CALL(0x0185)
 #define SMC_RMI_VDEV_COMMUNICATE	SMC_RMI_CALL(0x0186)
+#define SMC_RMI_VDEV_CREATE		SMC_RMI_CALL(0x0187)
 #define SMC_RMI_VDEV_GET_STATE		SMC_RMI_CALL(0x0189)
 
+#define SMC_RMI_VDEV_LOCK		SMC_RMI_CALL(0x01D2)
+
 #define RMI_ABI_MAJOR_VERSION	1
 #define RMI_ABI_MINOR_VERSION	0
 
@@ -455,4 +458,25 @@ enum rmi_vdev_state {
 	RMI_VDEV_STARTED,
 	RMI_VDEV_ERROR,
 };
+
+#define MAX_VDEV_AUX_GRANULES	32
+
+struct rmi_vdev_params {
+	union {
+		struct {
+			u64 flags;
+			u64 vdev_id;
+			u64 tdi_id;
+			u64 num_aux;
+		};
+		u8 padding1[0x100];
+	};
+	union {	/* 0x100 */
+		struct {
+			unsigned long aux[MAX_VDEV_AUX_GRANULES];
+		};
+		u8 padding2[0x900];
+	};
+};
+
 #endif /* __ASM_RMI_SMC_H */
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index 987c1be566ba..ae62749f36e8 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -12,6 +12,7 @@
 #include <linux/vmalloc.h>
 #include <linux/cleanup.h>
 #include <linux/kvm_host.h>
+#include <linux/pci.h>
 
 #include "rmi-da.h"
 
@@ -229,11 +230,35 @@ static void cca_tsm_disconnect(struct pci_dev *pdev)
 	clear_bit(stream_id, cca_stream_ids);
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
index af0632544911..336a4f5a832d 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -665,7 +665,7 @@ static int wait_for_vdev_state(struct pci_tsm *tsm, enum rmi_vdev_state target_s
 	return wait_for_dev_state(VDEV_COMMUNICATE, tsm, target_state, RMI_VDEV_ERROR);
 }
 
-static __maybe_unused void vdev_state_transition_workfn(struct work_struct *work)
+static void vdev_state_transition_workfn(struct work_struct *work)
 {
 	unsigned long state;
 	struct pci_tsm *tsm;
@@ -683,3 +683,111 @@ static __maybe_unused void vdev_state_transition_workfn(struct work_struct *work
 
 	complete(&setup_work->complete);
 }
+
+static int submit_vdev_state_transition_work(struct pci_dev *pdev, int target_state)
+{
+	enum rmi_vdev_state state;
+	struct dev_comm_work comm_work;
+	struct cca_host_comm_data *comm_data = to_cca_comm_data(pdev);
+	struct cca_host_tdi *host_tdi = to_cca_host_tdi(pdev);
+
+	INIT_WORK_ONSTACK(&comm_work.work, vdev_state_transition_workfn);
+	init_completion(&comm_work.complete);
+	comm_work.tsm = pdev->tsm;
+	comm_work.target_state = target_state;
+
+	queue_work(comm_data->work_queue, &comm_work.work);
+
+	wait_for_completion(&comm_work.complete);
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
+static unsigned long pci_get_tdi_id(struct pci_dev *pdev)
+{
+	/* requester segment is marked reserved. */
+	return pci_dev_id(pdev);
+}
+
+void *cca_vdev_create(struct realm *realm, struct pci_dev *pdev,
+		      struct pci_dev *pf0_dev, u32 guest_rid)
+{
+	phys_addr_t rd_phys = virt_to_phys(realm->rd);
+	struct rmi_vdev_params *params = NULL;
+	struct cca_host_pf0_dsc *pf0_dsc;
+	struct cca_host_tdi *host_tdi;
+	phys_addr_t rmm_pdev_phys;
+	phys_addr_t rmm_vdev_phys;
+	bool should_free = true;
+	void *rmm_vdev;
+	int ret;
+
+	pf0_dsc = to_cca_pf0_dsc(pf0_dev);
+	if (!pf0_dsc->rmm_pdev) {
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
+	if (rmi_granule_delegate(rmm_vdev_phys)) {
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
+	params->num_aux = 0;
+
+	rmm_pdev_phys = virt_to_phys(pf0_dsc->rmm_pdev);
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
+	if (rmi_granule_undelegate(rmm_vdev_phys))
+		should_free = false;
+err_granule_delegate:
+	if (should_free)
+		free_page((unsigned long)rmm_vdev);
+err_out:
+	return ERR_PTR(ret);
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index 914a3c297c24..e92078ae9a90 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -139,4 +139,6 @@ static inline struct cca_host_tdi *to_cca_host_tdi(struct pci_dev *pdev)
 int cca_pdev_create(struct pci_dev *pdev);
 int cca_pdev_ide_setup(struct pci_dev *pdev);
 void cca_pdev_stop_and_destroy(struct pci_dev *pdev);
+void *cca_vdev_create(struct realm *realm, struct pci_dev *pdev,
+		      struct pci_dev *pf0_dev, u32 guest_rid);
 #endif

---

## [4] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 03/12] coco: host: arm64: Add helpers to unlock and destroy RMM vdev*

- define the SMCCC IDs and inline wrappers for `RMI_VDEV_UNLOCK` and
  RMI_VDEV_DESTROY
- extend `vdev_create()` to treat communication failures as fatal and
  tear down the newly created vdev
- provide `vdev_unlock_and_destroy()` that drives the vdev back to the
  unlocked state, issues the destroy call, and frees the delegated granule
- hook the new helper into the TSM unbind path so host cleanup always
  unlock and destroy RMM vdev and releases cached buffers

Cc: Marc Zyngier <maz@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h        | 22 ++++++++++
 arch/arm64/include/asm/rmi_smc.h         |  2 +
 drivers/virt/coco/arm-cca-host/arm-cca.c | 25 ++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.c  | 52 ++++++++++++++++++++++--
 drivers/virt/coco/arm-cca-host/rmi-da.h  |  2 +
 5 files changed, 100 insertions(+), 3 deletions(-)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 2a86de5eb160..5964549aca23 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -639,4 +639,26 @@ static inline unsigned long rmi_vdev_lock(unsigned long rd,
 	return res.a0;
 }
 
+static inline unsigned long rmi_vdev_unlock(unsigned long rd,
+					    unsigned long pdev_phys,
+					    unsigned long vdev_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_UNLOCK, rd, pdev_phys, vdev_phys, &res);
+
+	return res.a0;
+}
+
+static inline unsigned long rmi_vdev_destroy(unsigned long rd,
+					     unsigned long pdev_phys,
+					     unsigned long vdev_phys)
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
index 20c36a01df94..95ddbc6dd1e0 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -57,7 +57,9 @@
 #define SMC_RMI_VDEV_ABORT		SMC_RMI_CALL(0x0185)
 #define SMC_RMI_VDEV_COMMUNICATE	SMC_RMI_CALL(0x0186)
 #define SMC_RMI_VDEV_CREATE		SMC_RMI_CALL(0x0187)
+#define SMC_RMI_VDEV_DESTROY		SMC_RMI_CALL(0x0188)
 #define SMC_RMI_VDEV_GET_STATE		SMC_RMI_CALL(0x0189)
+#define SMC_RMI_VDEV_UNLOCK		SMC_RMI_CALL(0x018A)
 
 #define SMC_RMI_VDEV_LOCK		SMC_RMI_CALL(0x01D2)
 
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index ae62749f36e8..1c17269809a1 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -253,12 +253,37 @@ static struct pci_tdi *cca_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u32 t
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
index 336a4f5a832d..2181430c47b5 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -771,15 +771,25 @@ void *cca_vdev_create(struct realm *realm, struct pci_dev *pdev,
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
@@ -791,3 +801,39 @@ void *cca_vdev_create(struct realm *realm, struct pci_dev *pdev,
 err_out:
 	return ERR_PTR(ret);
 }
+
+void cca_vdev_unlock_and_destroy(struct realm *realm,
+				 struct pci_dev *pdev, struct pci_dev *pf0_dev)
+{
+	int ret;
+	phys_addr_t rmm_pdev_phys;
+	phys_addr_t rmm_vdev_phys;
+	struct cca_host_pf0_dsc *pf0_dsc;
+	struct cca_host_tdi *host_tdi;
+	phys_addr_t rd_phys = virt_to_phys(realm->rd);
+
+	host_tdi = to_cca_host_tdi(pdev);
+	rmm_vdev_phys = virt_to_phys(host_tdi->rmm_vdev);
+
+	pf0_dsc = to_cca_pf0_dsc(pf0_dev);
+	rmm_pdev_phys = virt_to_phys(pf0_dsc->rmm_pdev);
+	if (rmi_vdev_unlock(rd_phys, rmm_pdev_phys, rmm_vdev_phys)) {
+		pci_err(pdev, "failed to unlock vdev\n");
+		goto unlock_err;
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
+	if (!rmi_granule_undelegate(rmm_vdev_phys))
+		free_page((unsigned long)host_tdi->rmm_vdev);
+
+	host_tdi->rmm_vdev = NULL;
+	host_tdi->realm = NULL;
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index e92078ae9a90..9b0af1ac208f 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -141,4 +141,6 @@ int cca_pdev_ide_setup(struct pci_dev *pdev);
 void cca_pdev_stop_and_destroy(struct pci_dev *pdev);
 void *cca_vdev_create(struct realm *realm, struct pci_dev *pdev,
 		      struct pci_dev *pf0_dev, u32 guest_rid);
+void cca_vdev_unlock_and_destroy(struct realm *realm, struct pci_dev *pdev,
+				 struct pci_dev *pf0_dev);
 #endif

---

## [5] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 04/12] coco: host: arm64: Add support for da object read RHI handling*

Device assignment-related RHI calls result in a REC exit, which is
handled by the tsm guest_request callback.

Cc: Marc Zyngier <maz@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rhi.h             |  4 ++
 arch/arm64/include/uapi/asm/rmi-da.h     | 19 +++++
 drivers/virt/coco/arm-cca-host/arm-cca.c | 75 +++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.c  | 91 ++++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.h  |  4 ++
 5 files changed, 193 insertions(+)
 create mode 100644 arch/arm64/include/uapi/asm/rmi-da.h

diff --git a/arch/arm64/include/asm/rhi.h b/arch/arm64/include/asm/rhi.h
index 8f9ea4a4bb7c..3c84fedba4ab 100644
--- a/arch/arm64/include/asm/rhi.h
+++ b/arch/arm64/include/asm/rhi.h
@@ -79,4 +79,8 @@ enum rhi_tdi_state {
 #define RHI_DA_VDEV_SET_TDI_STATE	SMC_RHI_CALL(0x0054)
 #define RHI_DA_VDEV_ABORT		SMC_RHI_CALL(0x0056)
 
+/* guest request operation nr */
+#define __RHI_DA_OBJECT_SIZE		0x1
+#define __RHI_DA_OBJECT_READ		0x2
+
 #endif
diff --git a/arch/arm64/include/uapi/asm/rmi-da.h b/arch/arm64/include/uapi/asm/rmi-da.h
new file mode 100644
index 000000000000..8743d9a2e5f7
--- /dev/null
+++ b/arch/arm64/include/uapi/asm/rmi-da.h
@@ -0,0 +1,19 @@
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
+
+struct arm64_vdev_object_read_guest_req {
+	__u32 req_type;
+	__u32 object_type;
+	__aligned_u64 offset;
+};
+
+#endif
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index 1c17269809a1..8678acd84d7d 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -13,6 +13,7 @@
 #include <linux/cleanup.h>
 #include <linux/kvm_host.h>
 #include <linux/pci.h>
+#include <asm/rmi-da.h>
 
 #include "rmi-da.h"
 
@@ -277,6 +278,79 @@ static void cca_tsm_unbind(struct pci_tdi *tdi)
 	kfree(host_tdi);
 }
 
+static ssize_t cca_tsm_guest_req(struct pci_tdi *tdi, enum pci_tsm_req_scope scope,
+				 sockptr_t req, size_t req_len,
+				 sockptr_t resp, size_t resp_len,
+				 u64 *tsm_code)
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
@@ -284,6 +358,7 @@ static struct pci_tsm_ops cca_link_pci_ops = {
 	.disconnect = cca_tsm_disconnect,
 	.bind = cca_tsm_bind,
 	.unbind = cca_tsm_unbind,
+	.guest_req = cca_tsm_guest_req,
 };
 
 static void cca_link_tsm_remove(void *tsm_dev)
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index 2181430c47b5..fb623e5e5b62 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -12,6 +12,7 @@
 #include <keys/asymmetric-type.h>
 #include <keys/x509-parser.h>
 #include <linux/kvm_types.h>
+#include <linux/kvm_host.h>
 #include <asm/kvm_rmi.h>
 
 #include "rmi-da.h"
@@ -837,3 +838,93 @@ void cca_vdev_unlock_and_destroy(struct realm *realm,
 	host_tdi->rmm_vdev = NULL;
 	host_tdi->realm = NULL;
 }
+
+int cca_vdev_get_object_size(struct pci_dev *pdev, int type)
+{
+	long len;
+	struct pci_tsm *tsm = pdev->tsm;
+	struct cca_host_pf0_dsc *pf0_dsc;
+	struct cca_host_tdi *host_tdi;
+
+	if (!tsm)
+		return -EINVAL;
+
+	pf0_dsc = to_cca_pf0_dsc(tsm->dsm_dev);
+	host_tdi = to_cca_host_tdi(pdev);
+
+	guard(mutex)(&pf0_dsc->object_lock);
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
+		if (!pf0_dsc->cert_chain.cache)
+			return -EINVAL;
+		len = pf0_dsc->cert_chain.cache->offset;
+	} else if (type == RHI_DA_OBJECT_VCA) {
+		if (!pf0_dsc->vca)
+			return -EINVAL;
+		len = pf0_dsc->vca->offset;
+	} else {
+		return -EINVAL;
+	}
+
+	return len;
+}
+
+int cca_vdev_read_cached_object(struct pci_dev *pdev, int type,
+				unsigned long offset,
+				unsigned long max_len, void __user *user_buf)
+{
+	void *buf;
+	unsigned long len;
+	struct cca_host_pf0_dsc *pf0_dsc;
+	struct cca_host_tdi *host_tdi;
+	struct pci_tsm *tsm = pdev->tsm;
+
+	if (!tsm)
+		return -EINVAL;
+
+	pf0_dsc = to_cca_pf0_dsc(tsm->dsm_dev);
+	host_tdi = to_cca_host_tdi(pdev);
+
+	guard(mutex)(&pf0_dsc->object_lock);
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
+		if (!pf0_dsc->cert_chain.cache)
+			return -EINVAL;
+		len = pf0_dsc->cert_chain.cache->offset;
+		buf = pf0_dsc->cert_chain.cache->buf;
+	} else if (type == RHI_DA_OBJECT_VCA) {
+		if (!pf0_dsc->vca)
+			return -EINVAL;
+		len = pf0_dsc->vca->offset;
+		buf = pf0_dsc->vca->buf;
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
index 9b0af1ac208f..9cc587393d02 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -11,6 +11,7 @@
 #include <linux/pci-tsm.h>
 #include <linux/sizes.h>
 #include <asm/rmi_smc.h>
+#include <asm/rhi.h>
 
 #define MAX_CACHE_OBJ_SIZE	SZ_16M
 #define CACHE_CHUNK_SIZE	SZ_4K
@@ -143,4 +144,7 @@ void *cca_vdev_create(struct realm *realm, struct pci_dev *pdev,
 		      struct pci_dev *pf0_dev, u32 guest_rid);
 void cca_vdev_unlock_and_destroy(struct realm *realm, struct pci_dev *pdev,
 				 struct pci_dev *pf0_dev);
+int cca_vdev_get_object_size(struct pci_dev *pdev, int type);
+int cca_vdev_read_cached_object(struct pci_dev *pdev, int type, unsigned long offset,
+				unsigned long max_len, void __user *user_buf);
 #endif

---

## [6] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 05/12] coco: host: arm64: Add helper for cached object fetches*

Introduce vdev_fetch_object_work() so we have a single workqueue handler
that refreshes any cached Realm object (interface report, measurements,
certificates). The helper receives the cache buffer/offset/size via
dev_comm_work, clears the existing contents under dsm_dev.object_lock,
performs the VDEV_COMMUNICATE call, and uses the updated size to signal
failures back to the caller once the work completes.

Cc: Marc Zyngier <maz@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 drivers/virt/coco/arm-cca-host/rmi-da.c | 28 +++++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.h |  3 +++
 2 files changed, 31 insertions(+)

diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index fb623e5e5b62..123cda44535c 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -839,6 +839,34 @@ void cca_vdev_unlock_and_destroy(struct realm *realm,
 	host_tdi->realm = NULL;
 }
 
+static void __maybe_unused vdev_fetch_object_workfn(struct work_struct *work)
+{
+	int state;
+	struct pci_tsm *tsm;
+	struct cca_host_pf0_dsc *pf0_dsc;
+	struct dev_comm_work *setup_work;
+
+	setup_work = container_of(work, struct dev_comm_work, work);
+	tsm = setup_work->tsm;
+	pf0_dsc = to_cca_pf0_dsc(tsm->dsm_dev);
+
+	guard(mutex)(&pf0_dsc->object_lock);
+
+	if (setup_work->cache_size) {
+		memset(setup_work->cache_buf, 0, setup_work->cache_size);
+		*setup_work->cache_offset = 0;
+	}
+	state = do_dev_communicate(VDEV_COMMUNICATE, tsm, RMI_VDEV_ERROR);
+	/* return status through dev_comm_work.cache_cache */
+	if (state == RMI_VDEV_ERROR)
+		setup_work->cache_size = 0;
+	else
+		/* indicate success. This value is not used. */
+		setup_work->cache_size = CACHE_CHUNK_SIZE;
+
+	complete(&setup_work->complete);
+}
+
 int cca_vdev_get_object_size(struct pci_dev *pdev, int type)
 {
 	long len;
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index 9cc587393d02..c4f31986389c 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -24,6 +24,9 @@ struct cache_object {
 struct dev_comm_work {
 	struct pci_tsm *tsm;
 	int target_state;
+	u8 *cache_buf;
+	int *cache_offset;
+	int cache_size;
 	struct work_struct work;
 	struct completion complete;
 };

---

## [7] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 06/12] coco: host: arm64: Fetch interface report via RMI*

- define `__RHI_DA_VDEV_GET_INTERFACE_REPORT` for guest requests and
  expose the RMI SMC ID/wrapper for `RMI_VDEV_GET_INTERFACE_REPORT`
- teach the CCA host driver to handle the new guest request by fetching
  the report from RMM using `rmi_vdev_get_interface_report()` and
  refreshing the cached buffer
- add a helper that submits a DOE work to pull the latest report into
  the cache

This lets guests request up-to-date interface reports via RHI

Cc: Marc Zyngier <maz@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rhi.h             |  1 +
 arch/arm64/include/asm/rmi_cmds.h        | 12 ++++++
 arch/arm64/include/asm/rmi_smc.h         |  1 +
 drivers/virt/coco/arm-cca-host/arm-cca.c |  4 ++
 drivers/virt/coco/arm-cca-host/rmi-da.c  | 55 +++++++++++++++++++++++-
 drivers/virt/coco/arm-cca-host/rmi-da.h  |  1 +
 6 files changed, 73 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/rhi.h b/arch/arm64/include/asm/rhi.h
index 3c84fedba4ab..edb23614cdeb 100644
--- a/arch/arm64/include/asm/rhi.h
+++ b/arch/arm64/include/asm/rhi.h
@@ -82,5 +82,6 @@ enum rhi_tdi_state {
 /* guest request operation nr */
 #define __RHI_DA_OBJECT_SIZE		0x1
 #define __RHI_DA_OBJECT_READ		0x2
+#define __RHI_DA_VDEV_GET_INTERFACE_REPORT 0x3
 
 #endif
diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 5964549aca23..ea9d4ec21e0e 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -661,4 +661,16 @@ static inline unsigned long rmi_vdev_destroy(unsigned long rd,
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
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 95ddbc6dd1e0..b3239f51de22 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -60,6 +60,7 @@
 #define SMC_RMI_VDEV_DESTROY		SMC_RMI_CALL(0x0188)
 #define SMC_RMI_VDEV_GET_STATE		SMC_RMI_CALL(0x0189)
 #define SMC_RMI_VDEV_UNLOCK		SMC_RMI_CALL(0x018A)
+#define SMC_RMI_VDEV_GET_INTERFACE_REPORT SMC_RMI_CALL(0x01D0)
 
 #define SMC_RMI_VDEV_LOCK		SMC_RMI_CALL(0x01D2)
 
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index 8678acd84d7d..de3c239345a8 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -342,6 +342,10 @@ static ssize_t cca_tsm_guest_req(struct pci_tdi *tdi, enum pci_tsm_req_scope sco
 			/* error */
 			return len;
 		}
+		case __RHI_DA_VDEV_GET_INTERFACE_REPORT:
+		{
+			return cca_vdev_get_interface_report(pdev);
+		}
 		default:
 			return -EINVAL;
 		}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index 123cda44535c..48a18905bb55 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -839,7 +839,7 @@ void cca_vdev_unlock_and_destroy(struct realm *realm,
 	host_tdi->realm = NULL;
 }
 
-static void __maybe_unused vdev_fetch_object_workfn(struct work_struct *work)
+static void vdev_fetch_object_workfn(struct work_struct *work)
 {
 	int state;
 	struct pci_tsm *tsm;
@@ -956,3 +956,56 @@ int cca_vdev_read_cached_object(struct pci_dev *pdev, int type,
 
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
+	init_completion(&comm_work.complete);
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
+	wait_for_completion(&comm_work.complete);
+	destroy_work_on_stack(&comm_work.work);
+
+	if (comm_work.cache_size == 0)
+		return -ENXIO;
+	return 0;
+}
+
+int cca_vdev_get_interface_report(struct pci_dev *pdev)
+{
+	phys_addr_t rmm_pdev_phys;
+	phys_addr_t rmm_vdev_phys;
+	struct cca_host_pf0_dsc *pf0_dsc;
+	struct cca_host_tdi *host_tdi;
+	struct realm *realm;
+	phys_addr_t rd_phys;
+
+	host_tdi = to_cca_host_tdi(pdev);
+	rmm_vdev_phys = virt_to_phys(host_tdi->rmm_vdev);
+	realm = &host_tdi->tdi.kvm->arch.realm;
+	rd_phys = virt_to_phys(realm->rd);
+
+	pf0_dsc = to_cca_pf0_dsc(pdev->tsm->dsm_dev);
+	rmm_pdev_phys = virt_to_phys(pf0_dsc->rmm_pdev);
+
+	if (rmi_vdev_get_interface_report(rd_phys,
+					  rmm_pdev_phys, rmm_vdev_phys))
+		return -ENXIO;
+
+	/* get and update the interface report cache. */
+	return vdev_update_interface_report_cache(pdev);
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index c4f31986389c..662cedd23c42 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -150,4 +150,5 @@ void cca_vdev_unlock_and_destroy(struct realm *realm, struct pci_dev *pdev,
 int cca_vdev_get_object_size(struct pci_dev *pdev, int type);
 int cca_vdev_read_cached_object(struct pci_dev *pdev, int type, unsigned long offset,
 				unsigned long max_len, void __user *user_buf);
+int cca_vdev_get_interface_report(struct pci_dev *pdev);
 #endif

---

## [8] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 07/12] coco: host: arm64: Fetch device measurements via RMI*

- define __RHI_DA_VDEV_GET_MEASUREMENTS for guest requests and
  expose the RMI SMC ID/wrapper for RMI_VDEV_GET_DEV_MEASUREMENTS
- teach the CCA host driver to handle the new guest request by fetching
  the device measurements from RMM using rmi_vdev_get_device_measurements()
  and refreshing the cached buffer
- add a helper that submits a DOE work to pull the latest device
  measurements into the cache

This lets guests request up-to-date device measurements via RHI

Cc: Marc Zyngier <maz@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rhi.h             |  1 +
 arch/arm64/include/asm/rmi_cmds.h        | 12 +++++
 arch/arm64/include/asm/rmi_smc.h         | 15 +++++-
 arch/arm64/include/uapi/asm/rmi-da.h     |  6 +++
 drivers/virt/coco/arm-cca-host/arm-cca.c | 16 ++++++
 drivers/virt/coco/arm-cca-host/rmi-da.c  | 69 ++++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.h  |  1 +
 7 files changed, 119 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/rhi.h b/arch/arm64/include/asm/rhi.h
index edb23614cdeb..a18ad7bbc028 100644
--- a/arch/arm64/include/asm/rhi.h
+++ b/arch/arm64/include/asm/rhi.h
@@ -83,5 +83,6 @@ enum rhi_tdi_state {
 #define __RHI_DA_OBJECT_SIZE		0x1
 #define __RHI_DA_OBJECT_READ		0x2
 #define __RHI_DA_VDEV_GET_INTERFACE_REPORT 0x3
+#define __RHI_DA_VDEV_GET_MEASUREMENTS	0x4
 
 #endif
diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index ea9d4ec21e0e..aad245675c7d 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -673,4 +673,16 @@ static inline unsigned long rmi_vdev_get_interface_report(unsigned long rd,
 	return res.a0;
 }
 
+static inline unsigned long
+rmi_vdev_get_device_measurements(unsigned long rd, unsigned long pdev_phys,
+				 unsigned long vdev_phys,
+				 unsigned long param_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_GET_DEV_MEASUREMENTS,
+			     rd, pdev_phys, vdev_phys, param_phys, &res);
+
+	return res.a0;
+}
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index b3239f51de22..36c3db8b821d 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -61,7 +61,7 @@
 #define SMC_RMI_VDEV_GET_STATE		SMC_RMI_CALL(0x0189)
 #define SMC_RMI_VDEV_UNLOCK		SMC_RMI_CALL(0x018A)
 #define SMC_RMI_VDEV_GET_INTERFACE_REPORT SMC_RMI_CALL(0x01D0)
-
+#define SMC_RMI_VDEV_GET_DEV_MEASUREMENTS	SMC_RMI_CALL(0x01D1)
 #define SMC_RMI_VDEV_LOCK		SMC_RMI_CALL(0x01D2)
 
 #define RMI_ABI_MAJOR_VERSION	1
@@ -482,4 +482,17 @@ struct rmi_vdev_params {
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
index 8743d9a2e5f7..1c21a5e78eb5 100644
--- a/arch/arm64/include/uapi/asm/rmi-da.h
+++ b/arch/arm64/include/uapi/asm/rmi-da.h
@@ -16,4 +16,10 @@ struct arm64_vdev_object_read_guest_req {
 	__aligned_u64 offset;
 };
 
+struct arm64_vdev_device_measurement_guest_req {
+	__u32 req_type;
+	__aligned_u64 flags;
+	__aligned_u64 nonce;
+};
+
 #endif
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index de3c239345a8..ba2751eb06f7 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -346,6 +346,22 @@ static ssize_t cca_tsm_guest_req(struct pci_tdi *tdi, enum pci_tsm_req_scope sco
 		{
 			return cca_vdev_get_interface_report(pdev);
 		}
+		case __RHI_DA_VDEV_GET_MEASUREMENTS:
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
+			ret = cca_vdev_get_device_measurements(pdev,
+							       req_obj.flags,
+							       (u8 *)req_obj.nonce);
+			return ret;
+		}
 		default:
 			return -EINVAL;
 		}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index 48a18905bb55..58a20877c6b6 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -1009,3 +1009,72 @@ int cca_vdev_get_interface_report(struct pci_dev *pdev)
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
+	init_completion(&comm_work.complete);
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
+	wait_for_completion(&comm_work.complete);
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
+int cca_vdev_get_device_measurements(struct pci_dev *pdev, unsigned long flags, u8 *nonce)
+{
+	struct realm *realm;
+	phys_addr_t rd_phys;
+	phys_addr_t rmm_pdev_phys;
+	phys_addr_t rmm_vdev_phys;
+	struct cca_host_tdi *host_tdi;
+	struct cca_host_pf0_dsc *pf0_dsc;
+
+	host_tdi = to_cca_host_tdi(pdev);
+	rmm_vdev_phys = virt_to_phys(host_tdi->rmm_vdev);
+	realm = &host_tdi->tdi.kvm->arch.realm;
+	rd_phys = virt_to_phys(realm->rd);
+
+	pf0_dsc = to_cca_pf0_dsc(pdev->tsm->dsm_dev);
+	rmm_pdev_phys = virt_to_phys(pf0_dsc->rmm_pdev);
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
index 662cedd23c42..6304cee85874 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -151,4 +151,5 @@ int cca_vdev_get_object_size(struct pci_dev *pdev, int type);
 int cca_vdev_read_cached_object(struct pci_dev *pdev, int type, unsigned long offset,
 				unsigned long max_len, void __user *user_buf);
 int cca_vdev_get_interface_report(struct pci_dev *pdev);
+int cca_vdev_get_device_measurements(struct pci_dev *pdev, unsigned long flags, u8 *nonce);
 #endif

---

## [9] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 08/12] coco: host: KVM: arm64: Handle vdev request exits and completion*

- add the RMI/RHI definitions for RMI_VDEV_COMPLETE, the new exit
  reason, and the extended REC exit payload
- update KVM to recognize RMI_EXIT_VDEV_REQUEST and surface it to
  userspace via KVM_EXIT_ARM64_TIO
- Add CCA TSM guest request handler for __REC_EXIT_DA_VDEV_REQUEST which
  takes a vCPU fd and verify it belongs to the same VM before calling
  rmi_vdev_complete()

This lets Realm firmware hand control back to the VMM when it needs host
assistance for vdev operations, and gives userspace a way to finish the
request.

Cc: Marc Zyngier <maz@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 Documentation/virt/kvm/api.rst           | 22 +++++++++++++++++
 arch/arm64/include/asm/rhi.h             |  1 +
 arch/arm64/include/asm/rmi_cmds.h        | 10 ++++++++
 arch/arm64/include/asm/rmi_smc.h         | 17 ++++++++++++--
 arch/arm64/include/uapi/asm/rmi-da.h     |  5 ++++
 arch/arm64/kvm/rmi-exit.c                | 17 ++++++++++++++
 drivers/virt/coco/arm-cca-host/arm-cca.c | 12 ++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.c  | 30 ++++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.h  |  2 ++
 include/linux/kvm_host.h                 |  1 +
 include/uapi/linux/kvm.h                 | 10 ++++++++
 virt/kvm/kvm_main.c                      |  6 +++++
 12 files changed, 131 insertions(+), 2 deletions(-)

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index bd2f0dd0aeda..041009307ee8 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -7429,6 +7429,28 @@ the ``KVM_EXIT_ARM_SEA_FLAG_GPA_VALID`` flag is set. Otherwise, the value of
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
+		} cca_exit;
+
+Used on arm64 systems. When the VM capability ``KVM_CAP_ARM_RMI`` is enabled,
+KVM generates a VM exit whenever the guest needs host assistance to map a vdev
+ID to a vdev object, or to validate a device-memory GPA-to-PA mapping. The
+``nr`` field records the exit reason; currently the following values are
+defined:
+
+* ``RMI_EXIT_VDEV_REQUEST``: the RMM is requiring host to provide the vdev
+  object details matching a specific virtual device id.
+* ``RMI_EXIT_VDEV_MAP``: the guest wants the host to validate or install a
+  device-memory mapping.
+
+The ``flags`` field must be zero.
 
 		/* Fix the size of the union. */
 		char padding[256];
diff --git a/arch/arm64/include/asm/rhi.h b/arch/arm64/include/asm/rhi.h
index a18ad7bbc028..888b3a1c3953 100644
--- a/arch/arm64/include/asm/rhi.h
+++ b/arch/arm64/include/asm/rhi.h
@@ -84,5 +84,6 @@ enum rhi_tdi_state {
 #define __RHI_DA_OBJECT_READ		0x2
 #define __RHI_DA_VDEV_GET_INTERFACE_REPORT 0x3
 #define __RHI_DA_VDEV_GET_MEASUREMENTS	0x4
+#define __REC_EXIT_DA_VDEV_REQUEST	0x5
 
 #endif
diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index aad245675c7d..f29c2de5d3b9 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -685,4 +685,14 @@ rmi_vdev_get_device_measurements(unsigned long rd, unsigned long pdev_phys,
 
 	return res.a0;
 }
+
+static inline unsigned long rmi_vdev_complete(unsigned long rec_phys, unsigned long vdev_phys)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_COMPLETE, rec_phys, vdev_phys, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 36c3db8b821d..6b685585e750 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -60,6 +60,7 @@
 #define SMC_RMI_VDEV_DESTROY		SMC_RMI_CALL(0x0188)
 #define SMC_RMI_VDEV_GET_STATE		SMC_RMI_CALL(0x0189)
 #define SMC_RMI_VDEV_UNLOCK		SMC_RMI_CALL(0x018A)
+#define SMC_RMI_VDEV_COMPLETE		SMC_RMI_CALL(0x018e)
 #define SMC_RMI_VDEV_GET_INTERFACE_REPORT SMC_RMI_CALL(0x01D0)
 #define SMC_RMI_VDEV_GET_DEV_MEASUREMENTS	SMC_RMI_CALL(0x01D1)
 #define SMC_RMI_VDEV_LOCK		SMC_RMI_CALL(0x01D2)
@@ -225,6 +226,7 @@ struct rec_enter {
 #define RMI_EXIT_RIPAS_CHANGE		0x04
 #define RMI_EXIT_HOST_CALL		0x05
 #define RMI_EXIT_SERROR			0x06
+#define RMI_EXIT_VDEV_REQUEST		0x08
 
 struct rec_exit {
 	union { /* 0x000 */
@@ -266,12 +268,23 @@ struct rec_exit {
 			u64 ripas_base;
 			u64 ripas_top;
 			u8 ripas_value;
-			u8 padding8[7];
+			u8 padding8[15];
+			u64 s2ap_base;
+			u64 s2ap_top;
+			u64 vdev_id_1;
+			u64 vdev_id_2;
+			u64 dev_mem_base;
+			u64 dev_mem_top;
+			u64 dev_mem_pa;
 		};
 		u8 padding5[0x100];
 	};
 	union { /* 0x600 */
-		u16 imm;
+		struct {
+			u16 imm;
+			u8 padding[6];
+			u64 plane;
+		};
 		u8 padding6[0x100];
 	};
 	union { /* 0x700 */
diff --git a/arch/arm64/include/uapi/asm/rmi-da.h b/arch/arm64/include/uapi/asm/rmi-da.h
index 1c21a5e78eb5..ac6e2fd2807d 100644
--- a/arch/arm64/include/uapi/asm/rmi-da.h
+++ b/arch/arm64/include/uapi/asm/rmi-da.h
@@ -22,4 +22,9 @@ struct arm64_vdev_device_measurement_guest_req {
 	__aligned_u64 nonce;
 };
 
+struct arm64_vdev_device_idmap_guest_req {
+	__u32 req_type;
+	__s32 vcpu_fd;
+};
+
 #endif
diff --git a/arch/arm64/kvm/rmi-exit.c b/arch/arm64/kvm/rmi-exit.c
index 7eff6967530c..3bba5e6afe88 100644
--- a/arch/arm64/kvm/rmi-exit.c
+++ b/arch/arm64/kvm/rmi-exit.c
@@ -129,6 +129,21 @@ static int rec_exit_host_call(struct kvm_vcpu *vcpu)
 	return kvm_smccc_call_handler(vcpu);
 }
 
+static inline void kvm_prepare_vdev_request_exit(struct kvm_vcpu *vcpu, unsigned long vdev_id)
+{
+	vcpu->run->exit_reason = KVM_EXIT_ARM64_TIO;
+	vcpu->run->cca_exit.nr = RMI_EXIT_VDEV_REQUEST;
+	vcpu->run->cca_exit.vdev_id  = vdev_id;
+	vcpu->run->cca_exit.flags = 0;
+}
+
+static int rec_exit_vdev_request(struct kvm_vcpu *vcpu)
+{
+	struct realm_rec *rec = &vcpu->arch.rec;
+
+	kvm_prepare_vdev_request_exit(vcpu, rec->run->exit.vdev_id_1);
+	return 0;
+}
 static void update_arch_timer_irq_lines(struct kvm_vcpu *vcpu)
 {
 	struct realm_rec *rec = &vcpu->arch.rec;
@@ -198,6 +213,8 @@ int handle_rec_exit(struct kvm_vcpu *vcpu, int rec_run_ret)
 		return rec_exit_ripas_change(vcpu);
 	case RMI_EXIT_HOST_CALL:
 		return rec_exit_host_call(vcpu);
+	case RMI_EXIT_VDEV_REQUEST:
+		return rec_exit_vdev_request(vcpu);
 	}
 
 	kvm_pr_unimpl("Unsupported exit reason: %u\n",
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index ba2751eb06f7..8aa362f44090 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -362,6 +362,18 @@ static ssize_t cca_tsm_guest_req(struct pci_tdi *tdi, enum pci_tsm_req_scope sco
 							       (u8 *)req_obj.nonce);
 			return ret;
 		}
+		case __REC_EXIT_DA_VDEV_REQUEST:
+		{
+			struct arm64_vdev_device_idmap_guest_req req_obj;
+
+			if (req_len != sizeof(req_obj))
+				return -EINVAL;
+
+			if (copy_from_user((void *)&req_obj, req.user, req_len))
+				return -EFAULT;
+
+			return cca_vdev_device_request(pdev, req_obj.vcpu_fd);
+		}
 		default:
 			return -EINVAL;
 		}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index 58a20877c6b6..3c19dfe89c0a 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -1078,3 +1078,33 @@ int cca_vdev_get_device_measurements(struct pci_dev *pdev, unsigned long flags,
 	/* get and update the interface report cache. */
 	return vdev_update_device_measurements_cache(pdev);
 }
+
+int cca_vdev_device_request(struct pci_dev *pdev, unsigned long vcpu_fd)
+{
+	struct kvm *kvm;
+	struct kvm_vcpu *vcpu;
+	unsigned long rec_phys;
+	struct cca_host_tdi *host_tdi = NULL;
+	struct file *vcpu_filp __free(fput) = fget(vcpu_fd);
+
+	if (!file_is_vcpu(vcpu_filp))
+		return -EINVAL;
+
+	vcpu = vcpu_filp->private_data;
+	if (!vcpu)
+		return -EINVAL;
+
+	rec_phys = virt_to_phys(vcpu->arch.rec.rec_page);
+	host_tdi = to_cca_host_tdi(pdev);
+	if (!host_tdi)
+		return -EINVAL;
+
+	kvm = host_tdi->tdi.kvm;
+	/* make sure this is the same vm */
+	if (vcpu->kvm != kvm)
+		return -EINVAL;
+
+	if (rmi_vdev_complete(rec_phys, virt_to_phys(host_tdi->rmm_vdev)))
+		return -ENXIO;
+	return 0;
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index 6304cee85874..2547afa1256f 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -93,6 +93,7 @@ struct cca_host_tdi {
 	struct pci_tdi tdi;
 	struct realm *realm;
 	void *rmm_vdev;
+	unsigned long vdev_id;
 	/* protected by cca_host_pf0_dsc.object_lock */
 	struct cache_object *interface_report;
 	struct cache_object *measurements;
@@ -152,4 +153,5 @@ int cca_vdev_read_cached_object(struct pci_dev *pdev, int type, unsigned long of
 				unsigned long max_len, void __user *user_buf);
 int cca_vdev_get_interface_report(struct pci_dev *pdev);
 int cca_vdev_get_device_measurements(struct pci_dev *pdev, unsigned long flags, u8 *nonce);
+int cca_vdev_device_request(struct pci_dev *pdev, unsigned long rec_id);
 #endif
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index 34759a262b28..26a9619c364c 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -1066,6 +1066,7 @@ void kvm_get_kvm(struct kvm *kvm);
 bool kvm_get_kvm_safe(struct kvm *kvm);
 void kvm_put_kvm(struct kvm *kvm);
 bool file_is_kvm(struct file *file);
+bool file_is_vcpu(struct file *file);
 void kvm_put_kvm_no_destroy(struct kvm *kvm);
 
 static inline struct kvm_memslots *__kvm_memslots(struct kvm *kvm, int as_id)
diff --git a/include/uapi/linux/kvm.h b/include/uapi/linux/kvm.h
index 49d5ce0b7a26..c2e12a1bb23b 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -188,6 +188,7 @@ struct kvm_exit_snp_req_certs {
 #define KVM_EXIT_ARM_SEA          41
 #define KVM_EXIT_ARM_LDST64B      42
 #define KVM_EXIT_SNP_REQ_CERTS    43
+#define KVM_EXIT_ARM64_TIO	  44
 
 /* For KVM_EXIT_INTERNAL_ERROR */
 /* Emulate instruction failed. */
@@ -492,6 +493,15 @@ struct kvm_run {
 		} arm_sea;
 		/* KVM_EXIT_SNP_REQ_CERTS */
 		struct kvm_exit_snp_req_certs snp_req_certs;
+		/* KVM_EXIT_ARM64_TIO*/
+		struct {
+			__u64 flags;
+			__u64 nr;
+			__u64 vdev_id;
+			__u64 gpa_base;
+			__u64 gpa_top;
+			__u64 pa_base;
+		} cca_exit;
 		/* Fix the size of the union. */
 		char padding[256];
 	};
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index f076c5a7a290..229c2b14bc83 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -4110,6 +4110,12 @@ static struct file_operations kvm_vcpu_fops = {
 	KVM_COMPAT(kvm_vcpu_compat_ioctl),
 };
 
+bool file_is_vcpu(struct file *file)
+{
+	return file && file->f_op == &kvm_vcpu_fops;
+}
+EXPORT_SYMBOL_GPL(file_is_vcpu);
+
 /*
  * Allocates an inode for the vcpu.
  */

---

## [10] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 09/12] coco: host: KVM: arm64: Handle vdev map/validation exits*

- define the RMM SMCCC IDs (and wrappers) for VDEV_VALIDATE_MAPPING
  and VDEV_MEM_MAP, add the matching RHI request IDs, and extend the REC
  exit payload to carry GPA/HPA details for mapping exits
- update KVM to recognize RMI_EXIT_VDEV_MAP and surface it to
  userspace via KVM_EXIT_ARM64_TIO
- use the new realm_dev_mem_map() to map device memory.

Cc: Marc Zyngier <maz@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/kvm_rmi.h         |   4 +
 arch/arm64/include/asm/rhi.h             |   1 +
 arch/arm64/include/asm/rmi_cmds.h        |  26 +++++
 arch/arm64/include/asm/rmi_smc.h         |   4 +
 arch/arm64/include/uapi/asm/rmi-da.h     |   8 ++
 arch/arm64/kvm/rmi-exit.c                |  38 ++++++++
 arch/arm64/kvm/rmi.c                     | 115 +++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/arm-cca.c |  28 ++++++
 drivers/virt/coco/arm-cca-host/rmi-da.c  |  37 ++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.h  |   3 +
 10 files changed, 264 insertions(+)

diff --git a/arch/arm64/include/asm/kvm_rmi.h b/arch/arm64/include/asm/kvm_rmi.h
index a967061af6ed..0a38a489fd53 100644
--- a/arch/arm64/include/asm/kvm_rmi.h
+++ b/arch/arm64/include/asm/kvm_rmi.h
@@ -134,4 +134,8 @@ static inline bool kvm_realm_is_private_address(struct realm *realm,
 	return !(addr & BIT(realm->ia_bits - 1));
 }
 
+int realm_dev_mem_map(struct kvm *kvm, unsigned long rec_phys,
+		      unsigned long pdev_phys, unsigned long vdev_phys,
+		      unsigned long start_ipa, unsigned long end_ipa,
+		      unsigned long start_pa);
 #endif /* __ASM_KVM_RMI_H */
diff --git a/arch/arm64/include/asm/rhi.h b/arch/arm64/include/asm/rhi.h
index 888b3a1c3953..ba9e11152c1b 100644
--- a/arch/arm64/include/asm/rhi.h
+++ b/arch/arm64/include/asm/rhi.h
@@ -85,5 +85,6 @@ enum rhi_tdi_state {
 #define __RHI_DA_VDEV_GET_INTERFACE_REPORT 0x3
 #define __RHI_DA_VDEV_GET_MEASUREMENTS	0x4
 #define __REC_EXIT_DA_VDEV_REQUEST	0x5
+#define __REC_EXIT_DA_VDEV_MAP		0x6
 
 #endif
diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index f29c2de5d3b9..53bffaace64c 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -695,4 +695,30 @@ static inline unsigned long rmi_vdev_complete(unsigned long rec_phys, unsigned l
 	return res.a0;
 }
 
+static inline int rmi_vdev_validate_mapping(unsigned long rd, unsigned long rec_phys,
+					    unsigned long pdev_phys, unsigned long vdev_phys,
+					    unsigned long base, unsigned long top,
+					    unsigned long *out_top)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_VALIDATE_MAPPING, rd,
+			     rec_phys, pdev_phys, vdev_phys, base, top, &res);
+
+	if (out_top)
+		*out_top = res.a1;
+
+	return res.a0;
+}
+
+static inline int rmi_vdev_mem_map(unsigned long rd, unsigned long vdev_phys,
+				   unsigned long ipa, unsigned long level, unsigned long pa)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_MEM_MAP, rd, vdev_phys, ipa, level, pa, &res);
+
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 6b685585e750..41ee49c341c0 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -39,6 +39,7 @@
 
 #define SMC_RMI_RTT_READ_ENTRY		SMC_RMI_CALL(0x0161)
 #define SMC_RMI_RTT_UNMAP_UNPROTECTED	SMC_RMI_CALL(0x0162)
+#define SMC_RMI_VDEV_VALIDATE_MAPPING	SMC_RMI_CALL(0x0163)
 
 #define SMC_RMI_PSCI_COMPLETE		SMC_RMI_CALL(0x0164)
 #define SMC_RMI_FEATURES		SMC_RMI_CALL(0x0165)
@@ -47,6 +48,7 @@
 #define SMC_RMI_RTT_INIT_RIPAS		SMC_RMI_CALL(0x0168)
 #define SMC_RMI_RTT_SET_RIPAS		SMC_RMI_CALL(0x0169)
 
+#define SMC_RMI_VDEV_MEM_MAP		SMC_RMI_CALL(0x0172)
 #define SMC_RMI_PDEV_ABORT		SMC_RMI_CALL(0x0174)
 #define SMC_RMI_PDEV_COMMUNICATE        SMC_RMI_CALL(0x0175)
 #define SMC_RMI_PDEV_CREATE             SMC_RMI_CALL(0x0176)
@@ -187,6 +189,7 @@ struct rec_params {
 #define REC_ENTER_FLAG_TRAP_WFI		BIT(2)
 #define REC_ENTER_FLAG_TRAP_WFE		BIT(3)
 #define REC_ENTER_FLAG_RIPAS_RESPONSE	BIT(4)
+#define REC_ENTER_FLAG_DEV_MEM_RESPONSE BIT(6)
 
 #define REC_RUN_GPRS			31
 #define REC_MAX_GIC_NUM_LRS		16
@@ -227,6 +230,7 @@ struct rec_enter {
 #define RMI_EXIT_HOST_CALL		0x05
 #define RMI_EXIT_SERROR			0x06
 #define RMI_EXIT_VDEV_REQUEST		0x08
+#define RMI_EXIT_VDEV_MAP		0x09
 
 struct rec_exit {
 	union { /* 0x000 */
diff --git a/arch/arm64/include/uapi/asm/rmi-da.h b/arch/arm64/include/uapi/asm/rmi-da.h
index ac6e2fd2807d..20d3eab8ce64 100644
--- a/arch/arm64/include/uapi/asm/rmi-da.h
+++ b/arch/arm64/include/uapi/asm/rmi-da.h
@@ -27,4 +27,12 @@ struct arm64_vdev_device_idmap_guest_req {
 	__s32 vcpu_fd;
 };
 
+struct arm64_vdev_device_memmap_guest_req {
+	__u32 req_type;
+	__s32 vcpu_fd;
+	__aligned_u64 gpa_base;
+	__aligned_u64 gpa_top;
+	__aligned_u64 pa_base;
+};
+
 #endif
diff --git a/arch/arm64/kvm/rmi-exit.c b/arch/arm64/kvm/rmi-exit.c
index 3bba5e6afe88..c1605b03a32d 100644
--- a/arch/arm64/kvm/rmi-exit.c
+++ b/arch/arm64/kvm/rmi-exit.c
@@ -144,6 +144,42 @@ static int rec_exit_vdev_request(struct kvm_vcpu *vcpu)
 	kvm_prepare_vdev_request_exit(vcpu, rec->run->exit.vdev_id_1);
 	return 0;
 }
+
+static inline void kvm_prepare_vdev_validate_mapping_exit(struct kvm_vcpu *vcpu,
+							  gpa_t gpa_base, gpa_t gpa_top,
+							  hpa_t pa_base, unsigned long vdev_id)
+{
+	vcpu->run->exit_reason = KVM_EXIT_ARM64_TIO;
+	vcpu->run->cca_exit.nr = RMI_EXIT_VDEV_MAP;
+	vcpu->run->cca_exit.vdev_id  = vdev_id;
+	vcpu->run->cca_exit.flags = 0;
+	vcpu->run->cca_exit.gpa_base = gpa_base;
+	vcpu->run->cca_exit.gpa_top  = gpa_top;
+	vcpu->run->cca_exit.pa_base  = pa_base;
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
+		/* Set RMI_REJECT bit */
+		rec->run->enter.flags = REC_ENTER_FLAG_DEV_MEM_RESPONSE;
+		vcpu_err(vcpu, "Invalid DEV_MEM_VALIDATE for %#lx - %#lx\n", base, top);
+		return -EINVAL;
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
@@ -215,6 +251,8 @@ int handle_rec_exit(struct kvm_vcpu *vcpu, int rec_run_ret)
 		return rec_exit_host_call(vcpu);
 	case RMI_EXIT_VDEV_REQUEST:
 		return rec_exit_vdev_request(vcpu);
+	case RMI_EXIT_VDEV_MAP:
+		return rec_exit_vdev_validate_mapping(vcpu);
 	}
 
 	kvm_pr_unimpl("Unsupported exit reason: %u\n",
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 08f3d2362dfd..bb338712ef34 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -1505,6 +1505,121 @@ static void kvm_complete_ripas_change(struct kvm_vcpu *vcpu)
 	rec->run->exit.ripas_base = base;
 }
 
+/*
+ * Even though we can map larger block, since we need to delegate each granule.
+ * We map granule size and fold
+ */
+static int __realm_dev_mem_map(struct kvm *kvm,
+			       struct kvm_mmu_memory_cache *cache, unsigned long rec_phys,
+			       unsigned long pdev_phys, unsigned long vdev_phys,
+			       unsigned long start_ipa, unsigned long end_ipa,
+			       phys_addr_t phys, unsigned long *top_ipa)
+{
+	int ret = 0;
+	unsigned long rmi_ret;
+	unsigned long ipa, next_ipa;
+	struct realm *realm = &kvm->arch.realm;
+	phys_addr_t rd_phys = virt_to_phys(realm->rd);
+
+	for (ipa = start_ipa ; ipa < end_ipa; ipa += RMM_PAGE_SIZE) {
+
+		if (rmi_granule_delegate(phys)) {
+			ret = -EINVAL;
+			goto err_delegate;
+		}
+
+		rmi_ret = rmi_vdev_mem_map(rd_phys, vdev_phys,
+					   ipa, RMM_RTT_MAX_LEVEL, phys);
+		if (RMI_RETURN_STATUS(rmi_ret) == RMI_ERROR_RTT) {
+			/* Create missing RTTs and retry */
+			int level = RMI_RETURN_INDEX(rmi_ret);
+
+			ret = realm_create_rtt_levels(realm, ipa, level,
+						      RMM_RTT_MAX_LEVEL,
+						      cache);
+			if (ret)
+				goto err_vdev_mem_map;
+
+			if (rmi_vdev_mem_map(rd_phys, vdev_phys,
+					     ipa, RMM_RTT_MAX_LEVEL, phys))
+				ret = -ENXIO;
+		}
+		if (ret)
+			goto err_vdev_mem_map;
+
+		phys += RMM_PAGE_SIZE;
+	}
+
+	/*
+	 * Return the highest mapped IPA within the range
+	 * (processed by vdev_mem_map)
+	 */
+	*top_ipa = end_ipa;
+
+	while (start_ipa < end_ipa) {
+		/* now validate the device memory mapping */
+		if (rmi_vdev_validate_mapping(rd_phys, rec_phys, pdev_phys,
+				vdev_phys, start_ipa, end_ipa, &next_ipa)) {
+			/*
+			 * We can't find the RTT error here, because
+			 * things are already setup by dev_mem_map before
+			 * Caller will do the unmap and undelegate
+			 */
+			return -ENXIO;
+		}
+		start_ipa = next_ipa;
+	}
+
+	return 0;
+
+ err_vdev_mem_map:
+	WARN_ON(rmi_granule_undelegate(phys));
+ err_delegate:
+	*top_ipa = ipa - RMM_PAGE_SIZE;
+	return ret;
+}
+
+int realm_dev_mem_map(struct kvm *kvm, unsigned long rec_phys,
+		      unsigned long pdev_phys, unsigned long vdev_phys,
+		      unsigned long start_ipa, unsigned long end_ipa,
+		      unsigned long start_pa)
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
+		ret = __realm_dev_mem_map(kvm, &cache, rec_phys, pdev_phys,
+				vdev_phys, start_ipa, end_ipa, start_pa, &top_ipa);
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
 /*
  * kvm_rec_pre_enter - Complete operations before entering a REC
  *
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index 8aa362f44090..405542ffd9d1 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -378,6 +378,34 @@ static ssize_t cca_tsm_guest_req(struct pci_tdi *tdi, enum pci_tsm_req_scope sco
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
+		case __REC_EXIT_DA_VDEV_MAP:
+		{
+			struct arm64_vdev_device_memmap_guest_req req_obj;
+
+			if (req_len != sizeof(req_obj))
+				return -EINVAL;
+
+			if (copy_from_user((void *)&req_obj, req.user, req_len))
+				return -EFAULT;
+
+			return cca_vdev_device_map_validate(pdev, req_obj.vcpu_fd,
+							    req_obj.gpa_base,
+							    req_obj.gpa_top,
+							    req_obj.pa_base);
+		}
+		default:
+			return -EINVAL;
+		}
+	}
 	default:
 		return -EINVAL;
 	}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.c b/drivers/virt/coco/arm-cca-host/rmi-da.c
index 3c19dfe89c0a..d76095a3e6c3 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -1108,3 +1108,40 @@ int cca_vdev_device_request(struct pci_dev *pdev, unsigned long vcpu_fd)
 		return -ENXIO;
 	return 0;
 }
+
+int cca_vdev_device_map_validate(struct pci_dev *pdev, unsigned long vcpu_fd,
+				 unsigned long gpa_base, unsigned long gpa_top,
+				 unsigned long pa_base)
+{
+	struct kvm *kvm;
+	struct realm *realm;
+	phys_addr_t rec_phys;
+	struct kvm_vcpu *vcpu;
+	phys_addr_t rmm_pdev_phys;
+	phys_addr_t rmm_vdev_phys;
+	struct cca_host_tdi *host_tdi;
+	struct cca_host_pf0_dsc *pf0_dsc;
+	struct file *vcpu_filp __free(fput) = fget(vcpu_fd);
+
+	if (!file_is_vcpu(vcpu_filp))
+		return -EINVAL;
+
+	vcpu = vcpu_filp->private_data;
+	if (!vcpu)
+		return -EINVAL;
+
+	host_tdi = to_cca_host_tdi(pdev);
+	pf0_dsc = to_cca_pf0_dsc(pdev->tsm->dsm_dev);
+	kvm = host_tdi->tdi.kvm;
+	realm = &kvm->arch.realm;
+	rec_phys = virt_to_phys(vcpu->arch.rec.rec_page);
+	rmm_vdev_phys = virt_to_phys(host_tdi->rmm_vdev);
+	rmm_pdev_phys = virt_to_phys(pf0_dsc->rmm_pdev);
+
+	/* make sure this is the same vm */
+	if (vcpu->kvm != kvm)
+		return -EINVAL;
+
+	return realm_dev_mem_map(kvm, rec_phys, rmm_pdev_phys,
+				 rmm_vdev_phys, gpa_base, gpa_top, pa_base);
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index 2547afa1256f..60b10bce3140 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -154,4 +154,7 @@ int cca_vdev_read_cached_object(struct pci_dev *pdev, int type, unsigned long of
 int cca_vdev_get_interface_report(struct pci_dev *pdev);
 int cca_vdev_get_device_measurements(struct pci_dev *pdev, unsigned long flags, u8 *nonce);
 int cca_vdev_device_request(struct pci_dev *pdev, unsigned long rec_id);
+int cca_vdev_device_map_validate(struct pci_dev *pdev, unsigned long vcpu_fd,
+				 unsigned long gpa_base, unsigned long gpa_top,
+				 unsigned long pa_base);
 #endif

---

## [11] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 10/12] KVM: arm64: Unmap device mappings when a private granule is destroyed*

Ensure tearing down a private granule also tears down any RMM device
mapping by reading the RTT entry, invoking the new RMI_VDEV_MEM_UNMAP,
and remembering the entry’s RIPAS so we only free RAM pages.

Drive the device-unmap path when RIPAS transitions to EMPTY. Also roll
back partially built device maps when errors occur.

Cc: Marc Zyngier <maz@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_cmds.h | 15 +++++++
 arch/arm64/include/asm/rmi_smc.h  |  2 +
 arch/arm64/kvm/rmi.c              | 65 +++++++++++++++++++++++++++----
 3 files changed, 74 insertions(+), 8 deletions(-)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 53bffaace64c..0c06a4f45346 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -721,4 +721,19 @@ static inline int rmi_vdev_mem_map(unsigned long rd, unsigned long vdev_phys,
 	return res.a0;
 }
 
+static inline int rmi_vdev_mem_unmap(unsigned long rd, unsigned long ipa, unsigned long level,
+				     unsigned long *out_pa, unsigned long *out_ipa)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_MEM_UNMAP, rd, ipa, level, &res);
+
+	if (out_pa)
+		*out_pa = res.a1;
+	if (out_ipa)
+		*out_ipa = res.a2;
+
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 41ee49c341c0..f4b8f1c9ba0b 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -49,6 +49,7 @@
 #define SMC_RMI_RTT_SET_RIPAS		SMC_RMI_CALL(0x0169)
 
 #define SMC_RMI_VDEV_MEM_MAP		SMC_RMI_CALL(0x0172)
+#define SMC_RMI_VDEV_MEM_UNMAP		SMC_RMI_CALL(0x0173)
 #define SMC_RMI_PDEV_ABORT		SMC_RMI_CALL(0x0174)
 #define SMC_RMI_PDEV_COMMUNICATE        SMC_RMI_CALL(0x0175)
 #define SMC_RMI_PDEV_CREATE             SMC_RMI_CALL(0x0176)
@@ -92,6 +93,7 @@ enum rmi_ripas {
 	RMI_EMPTY = 0,
 	RMI_RAM = 1,
 	RMI_DESTROYED = 2,
+	RMI_DEV = 3,
 };
 
 #define RMI_NO_MEASURE_CONTENT	0
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index bb338712ef34..5de49a47d782 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -454,15 +454,26 @@ void kvm_realm_destroy_rtts(struct kvm *kvm, u32 ia_bits)
 static int realm_destroy_private_granule(struct realm *realm,
 					 unsigned long ipa,
 					 unsigned long *next_addr,
-					 phys_addr_t *out_rtt)
+					 phys_addr_t *out_rtt,
+					 int *ripas)
 {
 	unsigned long rd = virt_to_phys(realm->rd);
 	unsigned long rtt_addr;
+	struct rtt_entry rtt_entry;
 	phys_addr_t rtt;
 	int ret;
 
+	// mmu_lock avoids parallel rte modification?
+	ret = rmi_rtt_read_entry(rd, ipa, RMM_RTT_MAX_LEVEL, &rtt_entry);
+	if (ret != RMI_SUCCESS)
+		return -ENXIO;
+
 retry:
-	ret = rmi_data_destroy(rd, ipa, &rtt_addr, next_addr);
+	if (rtt_entry.ripas == RMI_DEV)
+		ret = rmi_vdev_mem_unmap(rd, ipa, RMM_RTT_MAX_LEVEL, &rtt_addr, next_addr);
+	else
+		ret = rmi_data_destroy(rd, ipa, &rtt_addr, next_addr);
+
 	if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
 		if (*next_addr > ipa)
 			return 0; /* UNASSIGNED */
@@ -490,6 +501,7 @@ static int realm_destroy_private_granule(struct realm *realm,
 		return -ENXIO;
 
 	*out_rtt = rtt_addr;
+	*ripas = rtt_entry.ripas;
 
 	return 0;
 }
@@ -501,16 +513,16 @@ static int realm_unmap_private_page(struct realm *realm,
 	unsigned long end = ALIGN(ipa + 1, PAGE_SIZE);
 	unsigned long addr;
 	phys_addr_t out_rtt = PHYS_ADDR_MAX;
-	int ret;
+	int ret, ripas;
 
 	for (addr = ipa; addr < end; addr = *next_addr) {
 		ret = realm_destroy_private_granule(realm, addr, next_addr,
-						    &out_rtt);
+						    &out_rtt, &ripas);
 		if (ret)
 			return ret;
 	}
 
-	if (out_rtt != PHYS_ADDR_MAX) {
+	if (out_rtt != PHYS_ADDR_MAX && ripas != RMI_DEV) {
 		out_rtt = ALIGN_DOWN(out_rtt, PAGE_SIZE);
 		free_page((unsigned long)phys_to_virt(out_rtt));
 	}
@@ -1226,10 +1238,27 @@ static int realm_set_ipa_state(struct kvm_vcpu *vcpu,
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
@@ -1587,7 +1616,9 @@ int realm_dev_mem_map(struct kvm *kvm, unsigned long rec_phys,
 	int ret;
 	unsigned long top_ipa;
 	unsigned long base_ipa = start_ipa;
+	struct realm *realm = &kvm->arch.realm;
 	struct kvm_s2_mmu *mmu = &kvm->arch.mmu;
+	phys_addr_t rd_phys = virt_to_phys(realm->rd);
 	struct kvm_mmu_memory_cache cache = { .gfp_zero = __GFP_ZERO };
 
 	do {
@@ -1614,6 +1645,24 @@ int realm_dev_mem_map(struct kvm *kvm, unsigned long rec_phys,
 		for (start_ipa = ALIGN(base_ipa, RMM_L2_BLOCK_SIZE);
 		     ((start_ipa + RMM_L2_BLOCK_SIZE) < end_ipa); start_ipa += RMM_L2_BLOCK_SIZE)
 			fold_rtt(&kvm->arch.realm, start_ipa, RMM_RTT_BLOCK_LEVEL);
+	} else {
+		/* unmap the partial mapping. */
+		while (start_ipa > base_ipa) {
+			unsigned long out_pa;
+			unsigned long out_ipa;
+
+			/* start_ipa is highest mapped ipa */
+			start_pa -= RMM_PAGE_SIZE;
+			start_ipa -= RMM_PAGE_SIZE;
+
+			WARN_ON(rmi_vdev_mem_unmap(rd_phys, start_ipa,
+					RMM_RTT_MAX_LEVEL, &out_pa, &out_ipa));
+
+			WARN_ON(start_pa != out_pa);
+			WARN_ON(start_ipa + RMM_PAGE_SIZE != out_ipa);
+			WARN_ON(rmi_granule_undelegate(out_pa));
+
+		}
 	}
 
 	return ret;

---

## [12] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 11/12] coco: host: arm64: Transition vdevs to TDISP RUN state*

- define SMC_RMI_VDEV_START and the __RHI_DA_VDEV_SET_TDI_STATE
- let the host guest TSM request handler (__RHI_DA_SET_TDI_STATE) accept
  RHI_DA_TDI_CONFIG_RUN and call into rmi_vdev_start()
- The RHI_DA_TDI_CONFIG_UNLOCKED and RHI_DA_TDI_CONFIG_LOCKED transition
  will be handled by the VMM
- wait for the firmware to report vdev state as RMI_VDEV_STARTED before
  returning

With this in place, a guest can move a vdev from LOCKED into the TDISP
RUN state once attestation completes.

Cc: Marc Zyngier <maz@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rhi.h             |  1 +
 arch/arm64/include/asm/rmi_cmds.h        | 10 ++++++++++
 arch/arm64/include/asm/rmi_smc.h         |  1 +
 arch/arm64/include/uapi/asm/rmi-da.h     |  5 +++++
 drivers/virt/coco/arm-cca-host/arm-cca.c | 15 +++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.c  | 22 ++++++++++++++++++++++
 drivers/virt/coco/arm-cca-host/rmi-da.h  |  1 +
 7 files changed, 55 insertions(+)

diff --git a/arch/arm64/include/asm/rhi.h b/arch/arm64/include/asm/rhi.h
index ba9e11152c1b..68780918e28b 100644
--- a/arch/arm64/include/asm/rhi.h
+++ b/arch/arm64/include/asm/rhi.h
@@ -86,5 +86,6 @@ enum rhi_tdi_state {
 #define __RHI_DA_VDEV_GET_MEASUREMENTS	0x4
 #define __REC_EXIT_DA_VDEV_REQUEST	0x5
 #define __REC_EXIT_DA_VDEV_MAP		0x6
+#define __RHI_DA_VDEV_SET_TDI_STATE	0x7
 
 #endif
diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index 0c06a4f45346..688414f695f7 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -686,6 +686,16 @@ rmi_vdev_get_device_measurements(unsigned long rd, unsigned long pdev_phys,
 	return res.a0;
 }
 
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
 static inline unsigned long rmi_vdev_complete(unsigned long rec_phys, unsigned long vdev_phys)
 {
 	struct arm_smccc_res res;
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index f4b8f1c9ba0b..384bde2d423e 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -67,6 +67,7 @@
 #define SMC_RMI_VDEV_GET_INTERFACE_REPORT SMC_RMI_CALL(0x01D0)
 #define SMC_RMI_VDEV_GET_DEV_MEASUREMENTS	SMC_RMI_CALL(0x01D1)
 #define SMC_RMI_VDEV_LOCK		SMC_RMI_CALL(0x01D2)
+#define SMC_RMI_VDEV_START		SMC_RMI_CALL(0x01D3)
 
 #define RMI_ABI_MAJOR_VERSION	1
 #define RMI_ABI_MINOR_VERSION	0
diff --git a/arch/arm64/include/uapi/asm/rmi-da.h b/arch/arm64/include/uapi/asm/rmi-da.h
index 20d3eab8ce64..dc2855cb05a8 100644
--- a/arch/arm64/include/uapi/asm/rmi-da.h
+++ b/arch/arm64/include/uapi/asm/rmi-da.h
@@ -35,4 +35,9 @@ struct arm64_vdev_device_memmap_guest_req {
 	__aligned_u64 pa_base;
 };
 
+struct arm64_vdev_set_tdi_state_guest_req {
+	__u32 req_type;
+	__u32 tdi_state;
+};
+
 #endif
diff --git a/drivers/virt/coco/arm-cca-host/arm-cca.c b/drivers/virt/coco/arm-cca-host/arm-cca.c
index 405542ffd9d1..9883bf9e0470 100644
--- a/drivers/virt/coco/arm-cca-host/arm-cca.c
+++ b/drivers/virt/coco/arm-cca-host/arm-cca.c
@@ -402,6 +402,21 @@ static ssize_t cca_tsm_guest_req(struct pci_tdi *tdi, enum pci_tsm_req_scope sco
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
index d76095a3e6c3..877a649dea13 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.c
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.c
@@ -1145,3 +1145,25 @@ int cca_vdev_device_map_validate(struct pci_dev *pdev, unsigned long vcpu_fd,
 	return realm_dev_mem_map(kvm, rec_phys, rmm_pdev_phys,
 				 rmm_vdev_phys, gpa_base, gpa_top, pa_base);
 }
+
+int cca_vdev_device_start(struct pci_dev *pdev)
+{
+	phys_addr_t rmm_pdev_phys;
+	phys_addr_t rmm_vdev_phys;
+	struct cca_host_pf0_dsc *pf0_dsc;
+	struct cca_host_tdi *host_tdi;
+	struct realm *realm;
+	phys_addr_t rd_phys;
+
+	host_tdi = to_cca_host_tdi(pdev);
+	rmm_vdev_phys = virt_to_phys(host_tdi->rmm_vdev);
+	realm = &host_tdi->tdi.kvm->arch.realm;
+	rd_phys = virt_to_phys(realm->rd);
+
+	pf0_dsc = to_cca_pf0_dsc(pdev->tsm->dsm_dev);
+	rmm_pdev_phys = virt_to_phys(pf0_dsc->rmm_pdev);
+
+	if (rmi_vdev_start(rd_phys, rmm_pdev_phys, rmm_vdev_phys))
+		return -ENXIO;
+	return submit_vdev_state_transition_work(pdev, RMI_VDEV_STARTED);
+}
diff --git a/drivers/virt/coco/arm-cca-host/rmi-da.h b/drivers/virt/coco/arm-cca-host/rmi-da.h
index 60b10bce3140..51ef49cb482b 100644
--- a/drivers/virt/coco/arm-cca-host/rmi-da.h
+++ b/drivers/virt/coco/arm-cca-host/rmi-da.h
@@ -157,4 +157,5 @@ int cca_vdev_device_request(struct pci_dev *pdev, unsigned long rec_id);
 int cca_vdev_device_map_validate(struct pci_dev *pdev, unsigned long vcpu_fd,
 				 unsigned long gpa_base, unsigned long gpa_top,
 				 unsigned long pa_base);
+int cca_vdev_device_start(struct pci_dev *pdev);
 #endif

---

## [13] Aneesh Kumar K.V (Arm) — 2026-03-12
*Subject: [RFC PATCH v3 12/12] KVM: arm64: CCA: enable DA in realm create parameters*

Now that we have all the required steps for DA in-place, enable
DA while creating realm.

Cc: Marc Zyngier <maz@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Jonathan Cameron <Jonathan.Cameron@huawei.com>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Dan Williams <dan.j.williams@intel.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <Suzuki.Poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/rmi_smc.h | 1 +
 arch/arm64/kvm/rmi.c             | 3 +++
 2 files changed, 4 insertions(+)

diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 384bde2d423e..5598b19ffc1d 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -118,6 +118,7 @@ enum rmi_ripas {
 #define RMI_REALM_PARAM_FLAG_LPA2		BIT(0)
 #define RMI_REALM_PARAM_FLAG_SVE		BIT(1)
 #define RMI_REALM_PARAM_FLAG_PMU		BIT(2)
+#define RMI_REALM_PARAM_FLAG_DA			BIT(3)
 
 /*
  * Note many of these fields are smaller than u64 but all fields have u64
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 5de49a47d782..328eef406419 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -703,6 +703,9 @@ static int realm_create_rd(struct kvm *kvm)
 	if (r)
 		goto out_undelegate_tables;
 
+	/* For now default enable DA */
+	if (rmi_has_feature(RMI_FEATURE_REGISTER_0_DA))
+		params->flags |= RMI_REALM_PARAM_FLAG_DA;
 	params_phys = virt_to_phys(params);
 
 	if (rmi_realm_create(rd_phys, params_phys)) {

---
