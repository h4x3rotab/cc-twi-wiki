---
title: 'PCI/TSM: TEE I/O infrastructure'
date: 2025-08-26
last_reply: 2025-10-10
message_count: 47
participants: ['Dan Williams', 'Greg KH', 'Jason Gunthorpe', 'Alexey Kardashevskiy', 'Aneesh Kumar K.V', 'Jonathan Cameron', 'Xu Yilun']
---

## [1] Dan Williams — 2025-08-26

The PCI/TSM core has two users. The first, the VMM, uses the core for
physical link security and secure session establishment. That session is a
transport for managing all the assignable interfaces of a device, "TDIs".
Once a TDI is assigned to a TVM, the second user of the PCI/TSM core makes
requests to transition a TDI from UNLOCKED to LOCKED, and LOCKED to RUN.
That setup needs to be coordinated with device driver attach and MMIO + DMA
setup.

Add the support to lock and accept a device into a TVM / Trusted Execution
Environment (TEE).

See "PCI/TSM: Add Device Security (TVM Guest) operations support" for the
bulk of the infrastructure. See "device core: Introduce confidential device
acceptance" for a modest proposal on new device-core machinery for
coordinating a device's transition into the TEE.

The incremental "link TSM" / VMM side infrastructure in this set, "PCI/TSM:
Add pci_tsm_{bind,unbind}() methods for instantiating TDIs" and "PCI/TSM:
Add pci_tsm_guest_req() for managing TDIs" is not exercised by
samples/devsec/, but Aneesh asked that I am include them anyway. All other
functionality has a samples/devsec/ consumer. The simple smoke test I used
to verify the mechanics is included in tools/testing/devsec/devsec.sh.

This set is available at tsm.git#staging (rebasing branch) or
tsm.git#devsec-20250826 (immutable tag). It passes a basic smoke test
that exercises load/unload of the samples/devsec/ modules and
lock/accept/unlock of the emulated device.

Dan Williams (7):
  PCI/TSM: Add pci_tsm_{bind,unbind}() methods for instantiating TDIs
  PCI/TSM: Add pci_tsm_guest_req() for managing TDIs
  device core: Introduce confidential device acceptance
  x86/ioremap, resource: Introduce IORES_DESC_ENCRYPTED for encrypted
    PCI MMIO
  PCI/TSM: Add Device Security (TVM Guest) operations support
  samples/devsec: Introduce a "Device Security TSM" sample driver
  tools/testing/devsec: Add a script to exercise samples/devsec/

 Documentation/ABI/testing/sysfs-bus-pci   |  46 +-
 Documentation/ABI/testing/sysfs-class-tsm |  19 +
 arch/x86/mm/ioremap.c                     |  32 +-
 drivers/base/Kconfig                      |   4 +
 drivers/base/Makefile                     |   1 +
 drivers/base/base.h                       |   5 +
 drivers/base/coco.c                       |  96 ++++
 drivers/pci/Kconfig                       |   2 +
 drivers/pci/tsm.c                         | 513 +++++++++++++++++++++-
 drivers/virt/coco/tsm-core.c              |  41 ++
 include/linux/device.h                    |  29 ++
 include/linux/ioport.h                    |   2 +
 include/linux/pci-tsm.h                   | 106 ++++-
 samples/devsec/Makefile                   |   6 +
 samples/devsec/pci.c                      |  43 ++
 samples/devsec/tsm.c                      |  99 +++++
 tools/testing/devsec/devsec.sh            | 138 ++++++
 17 files changed, 1161 insertions(+), 21 deletions(-)
 create mode 100644 drivers/base/coco.c
 create mode 100644 samples/devsec/pci.c
 create mode 100644 samples/devsec/tsm.c
 create mode 100755 tools/testing/devsec/devsec.sh


base-commit: 4de43c0eb5d83004edf891b974371572e3815126

---

## [2] Dan Williams — 2025-08-26
*Subject: [PATCH 1/7] PCI/TSM: Add pci_tsm_{bind,unbind}() methods for instantiating TDIs*

After a PCIe device has established a secure link and session between a TEE
Security Manager (TSM) and its local Device Security Manager (DSM), the
device or its subfunctions are candidates to be bound to a private memory
context, a TVM. A PCIe device function interface assigned to a TVM is a TEE
Device Interface (TDI).

The pci_tsm_bind() requests the low-level TSM driver to associate the
device with private MMIO and private IOMMU context resources of a given TVM
represented by a @kvm argument. A device in the bound state corresponds to
the TDISP protocol LOCKED state and awaits validation by the TVM. It is a
'struct pci_tsm_link_ops' operation because, similar to IDE establishment,
it involves host side resource establishment and context setup on behalf of
the guest. It is also expected to be performed lazily to allow for
operation of the device in non-confidential "shared" context for pre-lock
configuration.

Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/pci/tsm.c       | 95 +++++++++++++++++++++++++++++++++++++++++
 include/linux/pci-tsm.h | 30 +++++++++++++
 2 files changed, 125 insertions(+)

diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index 092e81c5208c..302a974f3632 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -251,6 +251,99 @@ static int remove_fn(struct pci_dev *pdev, void *data)
 	return 0;
 }
 
+/*
+ * Note, this helper only returns an error code and takes an argument for
+ * compatibility with the pci_walk_bus() callback prototype. pci_tsm_unbind()
+ * always succeeds.
+ */
+static int __pci_tsm_unbind(struct pci_dev *pdev, void *data)
+{
+	struct pci_tdi *tdi;
+	struct pci_tsm_pf0 *tsm_pf0;
+
+	lockdep_assert_held(&pci_tsm_rwsem);
+
+	if (!pdev->tsm)
+		return 0;
+
+	tsm_pf0 = to_pci_tsm_pf0(pdev->tsm);
+	guard(mutex)(&tsm_pf0->lock);
+
+	tdi = pdev->tsm->tdi;
+	if (!tdi)
+		return 0;
+
+	pdev->tsm->ops->unbind(tdi);
+	pdev->tsm->tdi = NULL;
+
+	return 0;
+}
+
+void pci_tsm_unbind(struct pci_dev *pdev)
+{
+	guard(rwsem_read)(&pci_tsm_rwsem);
+	__pci_tsm_unbind(pdev, NULL);
+}
+EXPORT_SYMBOL_GPL(pci_tsm_unbind);
+
+/**
+ * pci_tsm_bind() - Bind @pdev as a TDI for @kvm
+ * @pdev: PCI device function to bind
+ * @kvm: Private memory attach context
+ * @tdi_id: Identifier (virtual BDF) for the TDI as referenced by the TSM and DSM
+ *
+ * Returns 0 on success, or a negative error code on failure.
+ *
+ * Context: Caller is responsible for constraining the bind lifetime to the
+ * registered state of the device. For example, pci_tsm_bind() /
+ * pci_tsm_unbind() limited to the VFIO driver bound state of the device.
+ */
+int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u32 tdi_id)
+{
+	const struct pci_tsm_ops *ops;
+	struct pci_tsm_pf0 *tsm_pf0;
+	struct pci_tdi *tdi;
+
+	if (!kvm)
+		return -EINVAL;
+
+	guard(rwsem_read)(&pci_tsm_rwsem);
+
+	if (!pdev->tsm)
+		return -EINVAL;
+
+	ops = pdev->tsm->ops;
+
+	if (!is_link_tsm(ops->owner))
+		return -ENXIO;
+
+	tsm_pf0 = to_pci_tsm_pf0(pdev->tsm);
+	guard(mutex)(&tsm_pf0->lock);
+
+	/* Resolve races to bind a TDI */
+	if (pdev->tsm->tdi) {
+		if (pdev->tsm->tdi->kvm == kvm)
+			return 0;
+		else
+			return -EBUSY;
+	}
+
+	tdi = ops->bind(pdev, kvm, tdi_id);
+	if (IS_ERR(tdi))
+		return PTR_ERR(tdi);
+
+	pdev->tsm->tdi = tdi;
+
+	return 0;
+}
+EXPORT_SYMBOL_GPL(pci_tsm_bind);
+
+static void pci_tsm_unbind_all(struct pci_dev *pdev)
+{
+	pci_tsm_walk_fns_reverse(pdev, __pci_tsm_unbind, NULL);
+	__pci_tsm_unbind(pdev, NULL);
+}
+
 static void __pci_tsm_disconnect(struct pci_dev *pdev)
 {
 	struct pci_tsm_pf0 *tsm_pf0 = to_pci_tsm_pf0(pdev->tsm);
@@ -259,6 +352,8 @@ static void __pci_tsm_disconnect(struct pci_dev *pdev)
 	/* disconnect() mutually exclusive with subfunction pci_tsm_init() */
 	lockdep_assert_held_write(&pci_tsm_rwsem);
 
+	pci_tsm_unbind_all(pdev);
+
 	/*
 	 * disconnect() is uninterruptible as it may be called for device
 	 * teardown
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index e4f9ea4a54a9..337b566adfc5 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -5,6 +5,8 @@
 #include <linux/pci.h>
 
 struct pci_tsm;
+struct kvm;
+enum pci_tsm_req_scope;
 
 /*
  * struct pci_tsm_ops - manage confidential links and security state
@@ -29,18 +31,25 @@ struct pci_tsm_ops {
 	 * @connect: establish / validate a secure connection (e.g. IDE)
 	 *	     with the device
 	 * @disconnect: teardown the secure link
+	 * @bind: bind a TDI in preparation for it to be accepted by a TVM
+	 * @unbind: remove a TDI from secure operation with a TVM
 	 *
 	 * Context: @probe, @remove, @connect, and @disconnect run under
 	 * pci_tsm_rwsem held for write to sync with TSM unregistration and
 	 * mutual exclusion of @connect and @disconnect. @connect and
 	 * @disconnect additionally run under the DSM lock (struct
 	 * pci_tsm_pf0::lock) as well as @probe and @remove of the subfunctions.
+	 * @bind and @unbind run under pci_tsm_rwsem held for read and the DSM
+	 * lock.
 	 */
 	struct_group_tagged(pci_tsm_link_ops, link_ops,
 		struct pci_tsm *(*probe)(struct pci_dev *pdev);
 		void (*remove)(struct pci_tsm *tsm);
 		int (*connect)(struct pci_dev *pdev);
 		void (*disconnect)(struct pci_dev *pdev);
+		struct pci_tdi *(*bind)(struct pci_dev *pdev,
+					struct kvm *kvm, u32 tdi_id);
+		void (*unbind)(struct pci_tdi *tdi);
 	);
 
 	/*
@@ -58,10 +67,21 @@ struct pci_tsm_ops {
 	struct tsm_dev *owner;
 };
 
+/**
+ * struct pci_tdi - Core TEE I/O Device Interface (TDI) context
+ * @pdev: host side representation of guest-side TDI
+ * @kvm: TEE VM context of bound TDI
+ */
+struct pci_tdi {
+	struct pci_dev *pdev;
+	struct kvm *kvm;
+};
+
 /**
  * struct pci_tsm - Core TSM context for a given PCIe endpoint
  * @pdev: Back ref to device function, distinguishes type of pci_tsm context
  * @dsm: PCI Device Security Manager for link operations on @pdev
+ * @tdi: TDI context established by the @bind link operation
  * @ops: Link Confidentiality or Device Function Security operations
  *
  * This structure is wrapped by low level TSM driver data and returned by
@@ -77,6 +97,7 @@ struct pci_tsm_ops {
 struct pci_tsm {
 	struct pci_dev *pdev;
 	struct pci_dev *dsm;
+	struct pci_tdi *tdi;
 	const struct pci_tsm_ops *ops;
 };
 
@@ -131,6 +152,8 @@ int pci_tsm_link_constructor(struct pci_dev *pdev, struct pci_tsm *tsm,
 int pci_tsm_pf0_constructor(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm,
 			    const struct pci_tsm_ops *ops);
 void pci_tsm_pf0_destructor(struct pci_tsm_pf0 *tsm);
+int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u32 tdi_id);
+void pci_tsm_unbind(struct pci_dev *pdev);
 #else
 static inline int pci_tsm_register(struct tsm_dev *tsm_dev)
 {
@@ -139,5 +162,12 @@ static inline int pci_tsm_register(struct tsm_dev *tsm_dev)
 static inline void pci_tsm_unregister(struct tsm_dev *tsm_dev)
 {
 }
+static inline int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u64 tdi_id)
+{
+	return -ENXIO;
+}
+static inline void pci_tsm_unbind(struct pci_dev *pdev)
+{
+}
 #endif
 #endif /*__PCI_TSM_H */

base-commit: 4de43c0eb5d83004edf891b974371572e3815126

---

## [3] Dan Williams — 2025-08-26
*Subject: [PATCH 2/7] PCI/TSM: Add pci_tsm_guest_req() for managing TDIs*

A PCIe device function interface assigned to a TVM is a TEE Device
Interface (TDI). A TDI instantiated by pci_tsm_bind() needs additional
steps to be accepted by a TVM and transitioned to the RUN state.

pci_tsm_guest_req() is a channel for the guest to request TDISP collateral,
like Device Interface Reports, and effect TDISP state changes, like
LOCKED->RUN transititions. Similar to IDE establishment and pci_tsm_bind(),
these are long running operations involving SPDM message passing via the
DOE mailbox, i.e. another 'struct pci_tsm_link_ops' operation.

The path for a guest to invoke pci_tsm_guest_request() is either via a kvm
handle_exit() or an ioctl() when an exit reason is serviced by a userspace
VMM.

Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/pci/tsm.c       | 60 +++++++++++++++++++++++++++++++++++++++++
 include/linux/pci-tsm.h | 55 +++++++++++++++++++++++++++++++++++--
 2 files changed, 113 insertions(+), 2 deletions(-)

diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index 302a974f3632..3143558373e3 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -338,6 +338,66 @@ int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u32 tdi_id)
 }
 EXPORT_SYMBOL_GPL(pci_tsm_bind);
 
+/**
+ * pci_tsm_guest_req() - helper to marshal guest requests to the TSM driver
+ * @pdev: @pdev representing a bound tdi
+ * @scope: security model scope for the TVM request
+ * @req_in: Input payload forwarded from the guest
+ * @in_len: Length of @req_in
+ * @out_len: Output length of the returned response payload
+ *
+ * This is a common entry point for KVM service handlers in userspace responding
+ * to TDI information or state change requests. The scope parameter limits
+ * requests to TDISP state management, or limited debug.
+ *
+ * Returns a pointer to the response payload on success, @req_in if there is no
+ * response to a successful request, or an ERR_PTR() on failure.
+ *
+ * Caller is responsible for kvfree() on the result when @ret != @req_in and
+ * !IS_ERR_OR_NULL(@ret).
+ *
+ * Context: Caller is responsible for calling this within the pci_tsm_bind()
+ * state of the TDI.
+ */
+void *pci_tsm_guest_req(struct pci_dev *pdev, enum pci_tsm_req_scope scope,
+			void *req_in, size_t in_len, size_t *out_len)
+{
+	const struct pci_tsm_ops *ops;
+	struct pci_tsm_pf0 *tsm_pf0;
+	struct pci_tdi *tdi;
+	int rc;
+
+	/*
+	 * Forbid requests that are not directly related to TDISP
+	 * operations
+	 */
+	if (scope > PCI_TSM_REQ_STATE_CHANGE)
+		return ERR_PTR(-EINVAL);
+
+	ACQUIRE(rwsem_read_intr, lock)(&pci_tsm_rwsem);
+	if ((rc = ACQUIRE_ERR(rwsem_read_intr, &lock)))
+		return ERR_PTR(rc);
+
+	if (!pdev->tsm)
+		return ERR_PTR(-ENXIO);
+
+	ops = pdev->tsm->ops;
+
+	if (!is_link_tsm(ops->owner))
+		return ERR_PTR(-ENXIO);
+
+	tsm_pf0 = to_pci_tsm_pf0(pdev->tsm);
+	ACQUIRE(mutex_intr, ops_lock)(&tsm_pf0->lock);
+	if ((rc = ACQUIRE_ERR(mutex_intr, &ops_lock)))
+		return ERR_PTR(rc);
+
+	tdi = pdev->tsm->tdi;
+	if (!tdi)
+		return ERR_PTR(-ENXIO);
+	return ops->guest_req(pdev, scope, req_in, in_len, out_len);
+}
+EXPORT_SYMBOL_GPL(pci_tsm_guest_req);
+
 static void pci_tsm_unbind_all(struct pci_dev *pdev)
 {
 	pci_tsm_walk_fns_reverse(pdev, __pci_tsm_unbind, NULL);
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index 337b566adfc5..5b61aac2e9f7 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -33,14 +33,15 @@ struct pci_tsm_ops {
 	 * @disconnect: teardown the secure link
 	 * @bind: bind a TDI in preparation for it to be accepted by a TVM
 	 * @unbind: remove a TDI from secure operation with a TVM
+	 * @guest_req: marshal TVM information and state change requests
 	 *
 	 * Context: @probe, @remove, @connect, and @disconnect run under
 	 * pci_tsm_rwsem held for write to sync with TSM unregistration and
 	 * mutual exclusion of @connect and @disconnect. @connect and
 	 * @disconnect additionally run under the DSM lock (struct
 	 * pci_tsm_pf0::lock) as well as @probe and @remove of the subfunctions.
-	 * @bind and @unbind run under pci_tsm_rwsem held for read and the DSM
-	 * lock.
+	 * @bind, @unbind, and @guest_req run under pci_tsm_rwsem held for read
+	 * and the DSM lock.
 	 */
 	struct_group_tagged(pci_tsm_link_ops, link_ops,
 		struct pci_tsm *(*probe)(struct pci_dev *pdev);
@@ -50,6 +51,9 @@ struct pci_tsm_ops {
 		struct pci_tdi *(*bind)(struct pci_dev *pdev,
 					struct kvm *kvm, u32 tdi_id);
 		void (*unbind)(struct pci_tdi *tdi);
+		void *(*guest_req)(struct pci_dev *pdev,
+				   enum pci_tsm_req_scope scope, void *req_in,
+				   size_t in_len, size_t *out_len);
 	);
 
 	/*
@@ -143,6 +147,44 @@ static inline bool is_pci_tsm_pf0(struct pci_dev *pdev)
 	return PCI_FUNC(pdev->devfn) == 0;
 }
 
+/**
+ * enum pci_tsm_req_scope - Scope of guest requests to be validated by TSM
+ *
+ * Guest requests are a transport for a TVM to communicate with a TSM + DSM for
+ * a given TDI. A TSM driver is responsible for maintaining the kernel security
+ * model and limit commands that may affect the host, or are otherwise outside
+ * the typical TDISP operational model.
+ */
+enum pci_tsm_req_scope {
+	/**
+	 * @PCI_TSM_REQ_INFO: Read-only, without side effects, request for
+	 * typical TDISP collateral information like Device Interface Reports.
+	 * No device secrets are permitted, and no device state is changed.
+	 */
+	PCI_TSM_REQ_INFO = 0,
+	/**
+	 * @PCI_TSM_REQ_STATE_CHANGE: Request to change the TDISP state from
+	 * UNLOCKED->LOCKED, LOCKED->RUN. No any other device state,
+	 * configuration, or data change is permitted.
+	 */
+	PCI_TSM_REQ_STATE_CHANGE = 1,
+	/**
+	 * @PCI_TSM_REQ_DEBUG_READ: Read-only request for debug information
+	 *
+	 * A method to facilitate TVM information retrieval outside of typical
+	 * TDISP operational requirements. No device secrets are permitted.
+	 */
+	PCI_TSM_REQ_DEBUG_READ = 2,
+	/**
+	 * @PCI_TSM_REQ_DEBUG_WRITE: Device state changes for debug purposes
+	 *
+	 * The request may affect the operational state of the device outside of
+	 * the TDISP operational model. If allowed, requires CAP_SYS_RAW_IO, and
+	 * will taint the kernel.
+	 */
+	PCI_TSM_REQ_DEBUG_WRITE = 3,
+};
+
 #ifdef CONFIG_PCI_TSM
 struct tsm_dev;
 int pci_tsm_register(struct tsm_dev *tsm_dev);
@@ -154,6 +196,8 @@ int pci_tsm_pf0_constructor(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm,
 void pci_tsm_pf0_destructor(struct pci_tsm_pf0 *tsm);
 int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u32 tdi_id);
 void pci_tsm_unbind(struct pci_dev *pdev);
+void *pci_tsm_guest_req(struct pci_dev *pdev, enum pci_tsm_req_scope scope,
+			void *req_in, size_t in_len, size_t *out_len);
 #else
 static inline int pci_tsm_register(struct tsm_dev *tsm_dev)
 {
@@ -169,5 +213,12 @@ static inline int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u64 tdi_id
 static inline void pci_tsm_unbind(struct pci_dev *pdev)
 {
 }
+static inline void *pci_tsm_guest_req(struct pci_dev *pdev,
+				      enum pci_tsm_req_scope scope,
+				      void *req_in, size_t in_len,
+				      size_t *out_len)
+{
+	return ERR_PTR(-ENXIO);
+}
 #endif
 #endif /*__PCI_TSM_H */

---

## [4] Dan Williams — 2025-08-26
*Subject: [PATCH 3/7] device core: Introduce confidential device acceptance*

Of the many problems to solve with PCIe Trusted Execution Environment
Device Interface Security Protocol (TDISP) support, this is among the most
fraught. New device core infrastructure demands a high degree of scrutiny
especially when touching the long standing kernel policy that the kernel
trusts devices by default. Previous adjacent proposals in this space (e.g.
device filter, no bounce buffer flag...) have not moved forward.

So, what is this new 'struct device_private' mechanism, how is it different
from previous attempts, and why not a bus-device-type specific mechanism
(e.g.  pci_dev::untrusted, usb_device::authorized, tb_switch::authorized,
etc...)?

TEE acceptance is not a state that random modules should be allowed to
change in the common case. A device entering the accepted state is a
violent operation. Pre-existing MMIO and DMA mappings can not survive this
event. The device_cc_accept() and device_cc_reject() helpers (where "cc" ==
"confidential computing") coordinate with driver attachment and are only
meant for core-kernel bus drivers like the PCI core.

Driver interactions with the "accepted" state are similar to driver
interactions with the driver-core probe deferral mechanism (also managed in
'struct device_private'). TEE I/O aware drivers are responsible for
preparing the device for acceptance and then waiting for the accept event.
That maps cleanly to the probe deferral mechanism and device_cc_probe()
helps coordinates that handoff.

When the device enters the TEE, other subsystems need to behave
differently. For example, the IOMMU/DMA mapping subsystem needs to switch
DMA mapping requests from SWIOTLB bounce buffering to direct-DMA to private
memory. That device state is communicated via device_cc_accepted() in a
common way.

The observation is that PCI is not the only bus that has designs on
interacting with a TEE acceptance state. The "adjacent proposals" mentioned
before include platform firmware and embedded buses that want to accept
devices into the TEE. A bus-type-specific flag would be an ongoing
maintenance burden for each new bus that adds TEE acceptance support.

Cc: Christoph Hellwig <hch@lst.de>
Cc: Jason Gunthorpe <jgg@ziepe.ca>
Cc: Marek Szyprowski <m.szyprowski@samsung.com>
Cc: Robin Murphy <robin.murphy@arm.com>
Cc: Roman Kisel <romank@linux.microsoft.com>
Cc: Bjorn Helgaas <bhelgaas@google.com>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: "Aneesh Kumar K.V" <aneesh.kumar@kernel.org>
Cc: Greg Kroah-Hartman <gregkh@linuxfoundation.org>
Cc: "Rafael J. Wysocki" <rafael@kernel.org>
Cc: Danilo Krummrich <dakr@kernel.org>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/base/Kconfig   |  4 ++
 drivers/base/Makefile  |  1 +
 drivers/base/base.h    |  5 +++
 drivers/base/coco.c    | 96 ++++++++++++++++++++++++++++++++++++++++++
 include/linux/device.h | 28 ++++++++++++
 5 files changed, 134 insertions(+)
 create mode 100644 drivers/base/coco.c

diff --git a/drivers/base/Kconfig b/drivers/base/Kconfig
index 064eb52ff7e2..311e5377bd70 100644
--- a/drivers/base/Kconfig
+++ b/drivers/base/Kconfig
@@ -243,4 +243,8 @@ config FW_DEVLINK_SYNC_STATE_TIMEOUT
 	  command line option on every system/board your kernel is expected to
 	  work on.
 
+config CONFIDENTIAL_DEVICES
+	depends on ARCH_HAS_CC_PLATFORM
+	bool
+
 endmenu
diff --git a/drivers/base/Makefile b/drivers/base/Makefile
index 8074a10183dc..e11052cd5253 100644
--- a/drivers/base/Makefile
+++ b/drivers/base/Makefile
@@ -27,6 +27,7 @@ obj-$(CONFIG_GENERIC_MSI_IRQ) += platform-msi.o
 obj-$(CONFIG_GENERIC_ARCH_TOPOLOGY) += arch_topology.o
 obj-$(CONFIG_GENERIC_ARCH_NUMA) += arch_numa.o
 obj-$(CONFIG_ACPI) += physical_location.o
+obj-$(CONFIG_CONFIDENTIAL_DEVICES) += coco.o
 
 obj-y			+= test/
 
diff --git a/drivers/base/base.h b/drivers/base/base.h
index 123031a757d9..e4eec07675aa 100644
--- a/drivers/base/base.h
+++ b/drivers/base/base.h
@@ -98,6 +98,8 @@ struct driver_private {
  *	the device; typically because it depends on another driver getting
  *	probed first.
  * @async_driver - pointer to device driver awaiting probe via async_probe
+ * @cc_accepted - track the TEE acceptance state of the device for deferred
+ *	probing, MMIO mapping type, and SWIOTLB bypass for private memory DMA.
  * @device - pointer back to the struct device that this structure is
  * associated with.
  * @dead - This device is currently either in the process of or has been
@@ -115,6 +117,9 @@ struct device_private {
 	struct list_head deferred_probe;
 	const struct device_driver *async_driver;
 	char *deferred_probe_reason;
+#ifdef CONFIG_CONFIDENTIAL_DEVICES
+	bool cc_accepted;
+#endif
 	struct device *device;
 	u8 dead:1;
 };
diff --git a/drivers/base/coco.c b/drivers/base/coco.c
new file mode 100644
index 000000000000..97c22d0e9247
--- /dev/null
+++ b/drivers/base/coco.c
@@ -0,0 +1,96 @@
+// SPDX-License-Identifier: GPL-2.0
+#include <linux/device.h>
+#include <linux/dev_printk.h>
+#include <linux/lockdep.h>
+#include "base.h"
+
+/*
+ * Confidential devices implement encrypted + integrity protected MMIO and have
+ * the ability to issue DMA to encrypted + integrity protected System RAM. The
+ * device_cc_*() helpers aid buses in setting the acceptance state, drivers in
+ * preparing and probing the acceptance state, and other kernel subsystem in
+ * augmenting behavior in the presence of accepted devices (e.g.
+ * ioremap_encrypted()).
+ */
+
+/**
+ * device_cc_accept(): Mark a device as accepted for TEE operation
+ * @dev: device to accept
+ *
+ * Confidential bus drivers use this helper to accept devices at initial
+ * enumeration, or dynamically one attestation has been performed.
+ *
+ * Given that moving a device into confidential / private operation implicates
+ * any of MMIO mapping attributes, physical address, and IOMMU mappings this
+ * transition must be done while the device is idle (driver detached).
+ *
+ * This is an internal helper for buses not device drivers.
+ */
+int device_cc_accept(struct device *dev)
+{
+	lockdep_assert_held(&dev->mutex);
+
+	if (dev->driver)
+		return -EBUSY;
+	dev->p->cc_accepted = true;
+
+	return 0;
+}
+
+int device_cc_reject(struct device *dev)
+{
+	lockdep_assert_held(&dev->mutex);
+
+	if (dev->driver)
+		return -EBUSY;
+	dev->p->cc_accepted = false;
+
+	return 0;
+}
+
+/**
+ * device_cc_accepted(): Get the TEE operational state of a device
+ * @dev: device to check
+ *
+ * Various subsystems, mm/ioremap, drivers/iommu, drivers/vfio, kernel/dma...
+ * need to augment their behavior in the presence of confidential devices. This
+ * simple, deliberately not exported, helper is for those built-in consumers.
+ *
+ * This is an internal helper for subsystems not device drivers.
+ */
+bool device_cc_accepted(struct device *dev)
+{
+	return dev->p->cc_accepted;
+}
+
+/**
+ * device_cc_probe(): Coordinate dynamic acceptance with a device driver
+ * @dev: device to defer probing while acceptance pending
+ *
+ * Dynamically accepted devices may need a driver to perform initial
+ * configuration to get the device into a state where it can be accepted. Use
+ * this helper to exit driver probe at that partial device-init point and log
+ * this TEE acceptance specific deferral reason.
+ *
+ * This is an exported helper for device drivers that need to coordinate device
+ * configuration state and acceptance.
+ */
+int device_cc_probe(struct device *dev)
+{
+	/*
+	 * See work_on_cpu() in local_pci_probe() for one reason why
+	 * lockdep_assert_held() can not be used here.
+	 */
+	WARN_ON_ONCE(!mutex_is_locked(&dev->mutex));
+
+	if (!dev->driver)
+		return -EINVAL;
+
+	if (dev->p->cc_accepted)
+		return 0;
+
+	dev_err_probe(dev, -EPROBE_DEFER, "TEE acceptance pending\n");
+
+	return -EPROBE_DEFER;
+}
+EXPORT_SYMBOL_GPL(device_cc_probe);
diff --git a/include/linux/device.h b/include/linux/device.h
index 0470d19da7f2..43d072866949 100644
--- a/include/linux/device.h
+++ b/include/linux/device.h
@@ -1207,6 +1207,34 @@ static inline bool device_link_test(const struct device_link *link, u32 flags)
 	return !!(link->flags & flags);
 }
 
+/* Confidential Device state helpers */
+#ifdef CONFIG_CONFIDENTIAL_DEVICES
+int device_cc_accept(struct device *dev);
+int device_cc_reject(struct device *dev);
+int device_cc_probe(struct device *dev);
+bool device_cc_accepted(struct device *dev);
+#else
+static inline int device_cc_accept(struct device *dev)
+{
+	lockdep_assert_held(&dev->mutex);
+	return 0;
+}
+static inline int device_cc_reject(struct device *dev)
+{
+	lockdep_assert_held(&dev->mutex);
+	return 0;
+}
+static inline int device_cc_probe(struct device *dev)
+{
+	lockdep_assert_held(&dev->mutex);
+	return 0;
+}
+static inline bool device_cc_accepted(struct device *dev)
+{
+	return false;
+}
+#endif /* CONFIG_CONFIDENTIAL_DEVICES */
+
 /* Create alias, so I can be autoloaded. */
 #define MODULE_ALIAS_CHARDEV(major,minor) \
 	MODULE_ALIAS("char-major-" __stringify(major) "-" __stringify(minor))

---

## [5] Dan Williams — 2025-08-26
*Subject: [PATCH 4/7] x86/ioremap, resource: Introduce IORES_DESC_ENCRYPTED for encrypted PCI MMIO*

PCIe Trusted Execution Environment Device Interface Security Protocol
(TDISP) arranges for a PCI device to support encrypted MMIO. In support of
that capability, ioremap() needs a mechanism to detect when a PCI device
has been dynamically transitioned into this secure state and enforce
encrypted MMIO mappings.

Teach ioremap() about a new IORES_DESC_ENCRYPTED type that supplements the
existing PCI Memory Space (MMIO) BAR resources. The proposal is that a
resource, "PCI MMIO Encrypted", with this description type is injected by
the PCI/TSM core for each PCI device BAR that is to be protected.

Unlike the existing encryption determination which is "implied with a silent
fallback to an unencrypted mapping", this indication is "explicit with an
expectation that the request fails instead of fallback". IORES_MUST_ENCRYPT
is added to manage this expectation.

Given that "PCI MMIO Encrypted" is an additional resource in the tree, the
IORESOURCE_BUSY flag will only be set on a descendant/child of that
resource. Adjust the resource tree walk to use walk_iomem_res_desc() and
check all intersecting resources for the IORES_MUST_ENCRYPT determination.

Cc: Dave Hansen <dave.hansen@linux.intel.com>
Cc: Andy Lutomirski <luto@kernel.org>
Cc: Peter Zijlstra <peterz@infradead.org>
Cc: Thomas Gleixner <tglx@linutronix.de>
Cc: Ingo Molnar <mingo@redhat.com>
Cc: Borislav Petkov <bp@alien8.de>
Cc: x86@kernel.org
Cc: "H. Peter Anvin" <hpa@zytor.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/mm/ioremap.c  | 32 +++++++++++++++++++++-----------
 include/linux/ioport.h |  2 ++
 2 files changed, 23 insertions(+), 11 deletions(-)

diff --git a/arch/x86/mm/ioremap.c b/arch/x86/mm/ioremap.c
index 12c8180ca1ba..78b677dadfdc 100644
--- a/arch/x86/mm/ioremap.c
+++ b/arch/x86/mm/ioremap.c
@@ -93,18 +93,24 @@ static unsigned int __ioremap_check_ram(struct resource *res)
  */
 static unsigned int __ioremap_check_encrypted(struct resource *res)
 {
+	u32 flags = 0;
+
+	if (res->desc == IORES_DESC_ENCRYPTED)
+		flags |= IORES_MUST_ENCRYPT;
+
 	if (!cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT))
-		return 0;
+		return flags;
 
 	switch (res->desc) {
 	case IORES_DESC_NONE:
 	case IORES_DESC_RESERVED:
 		break;
+	case IORES_DESC_ENCRYPTED:
 	default:
-		return IORES_MAP_ENCRYPTED;
+		flags |= IORES_MAP_ENCRYPTED;
 	}
 
-	return 0;
+	return flags;
 }
 
 /*
@@ -134,14 +140,10 @@ static int __ioremap_collect_map_flags(struct resource *res, void *arg)
 {
 	struct ioremap_desc *desc = arg;
 
-	if (!(desc->flags & IORES_MAP_SYSTEM_RAM))
-		desc->flags |= __ioremap_check_ram(res);
-
-	if (!(desc->flags & IORES_MAP_ENCRYPTED))
-		desc->flags |= __ioremap_check_encrypted(res);
+	desc->flags |= __ioremap_check_ram(res);
+	desc->flags |= __ioremap_check_encrypted(res);
 
-	return ((desc->flags & (IORES_MAP_SYSTEM_RAM | IORES_MAP_ENCRYPTED)) ==
-			       (IORES_MAP_SYSTEM_RAM | IORES_MAP_ENCRYPTED));
+	return 0;
 }
 
 /*
@@ -161,7 +163,8 @@ static void __ioremap_check_mem(resource_size_t addr, unsigned long size,
 	end = start + size - 1;
 	memset(desc, 0, sizeof(struct ioremap_desc));
 
-	walk_mem_res(start, end, desc, __ioremap_collect_map_flags);
+	walk_iomem_res_desc(IORES_DESC_NONE, IORESOURCE_MEM, start, end, desc,
+			    __ioremap_collect_map_flags);
 
 	__ioremap_check_other(addr, desc);
 }
@@ -209,6 +212,13 @@ __ioremap_caller(resource_size_t phys_addr, unsigned long size,
 
 	__ioremap_check_mem(phys_addr, size, &io_desc);
 
+	if ((io_desc.flags & IORES_MUST_ENCRYPT) &&
+	    !(io_desc.flags & IORES_MAP_ENCRYPTED)) {
+		pr_err("ioremap: encrypted mapping unavailable for %pa - %pa\n",
+		       &phys_addr, &last_addr);
+		return NULL;
+	}
+
 	/*
 	 * Don't allow anybody to remap normal RAM that we're using..
 	 */
diff --git a/include/linux/ioport.h b/include/linux/ioport.h
index e8b2d6aa4013..b46e42bcafe3 100644
--- a/include/linux/ioport.h
+++ b/include/linux/ioport.h
@@ -143,6 +143,7 @@ enum {
 	IORES_DESC_RESERVED			= 7,
 	IORES_DESC_SOFT_RESERVED		= 8,
 	IORES_DESC_CXL				= 9,
+	IORES_DESC_ENCRYPTED			= 10,
 };
 
 /*
@@ -151,6 +152,7 @@ enum {
 enum {
 	IORES_MAP_SYSTEM_RAM		= BIT(0),
 	IORES_MAP_ENCRYPTED		= BIT(1),
+	IORES_MUST_ENCRYPT		= BIT(2), /* disable transparent fallback */
 };
 
 /* helpers to define resources */

---

## [6] Dan Williams — 2025-08-26
*Subject: [PATCH 5/7] PCI/TSM: Add Device Security (TVM Guest) operations support*

PCIe Trusted Execution Environment Device Interface Security Protocol
(TDISP) has two distinct sets of operations. The first, currently enabled
in driver/pci/tsm.c, enables the VMM to authenticate the physical function
(PCIe Component Measurement and Authentication (CMA)), establish a secure
message passing session (DMTF SPDM), and establish physical link security
(PCIe Integrity and Data Encryption (IDE)). The second set lets the TVM
manage the security state of assigned devices (TEE Device Interfaces
(TDIs)). Enable the latter with three new 'struct pci_tsm_ops' operations:

 - lock(): Transition the device to the TDISP state. In this mode
   the device is responsible for validating that it is in a secure
   configuration and will transition to the TDISP ERROR state if those
   settings are modified. Device Security Manager (DSM) and the TEE
   Security Manager (TSM) enforce that the device is not permitted to issue
   T=1 traffic in this mode.

 - accept(): After validating device measurements, the launch state of the
   TVM, or any other pertinent information about the state of the TVM or
   TDI a relying party authorizes a device to enter the TEE. Transition the
   device to the TDISP RUN state and mark its PCI MMIO ranges as "encrypted".

 - unlock(): From the RUN state the only other TDISP states that can be moved to
   are ERROR or UNLOCKED. Voluntarily move the device to the UNLOCKED
   state.

Only the mechanism for these operations is included, all of the policy and
infrastructure to support making the 'accept' decision are left to
follow-on work.

Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Co-developed-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 Documentation/ABI/testing/sysfs-bus-pci   |  46 ++-
 Documentation/ABI/testing/sysfs-class-tsm |  19 ++
 drivers/pci/Kconfig                       |   2 +
 drivers/pci/tsm.c                         | 358 +++++++++++++++++++++-
 drivers/virt/coco/tsm-core.c              |  41 +++
 include/linux/device.h                    |   1 +
 include/linux/pci-tsm.h                   |  25 +-
 7 files changed, 482 insertions(+), 10 deletions(-)

diff --git a/Documentation/ABI/testing/sysfs-bus-pci b/Documentation/ABI/testing/sysfs-bus-pci
index e0c8dad8d889..38b8ec34c4a3 100644
--- a/Documentation/ABI/testing/sysfs-bus-pci
+++ b/Documentation/ABI/testing/sysfs-bus-pci
@@ -638,13 +638,16 @@ Description:
 		Encryption) establishment. Reads from this attribute return the
 		name of the connected TSM or the empty string if not
 		connected. A TSM device signals its readiness to accept PCI
-		connection via a KOBJ_CHANGE event.
+		connection via a KOBJ_CHANGE event. This is a "link" TSM
+		attribute, see Documentation/ABI/testing/sysfs-class-tsm.
 
 What:		/sys/bus/pci/devices/.../tsm/disconnect
 Contact:	linux-coco@lists.linux.dev
 Description:
 		(WO) Write the name of the TSM device that was specified
-		to 'connect' to teardown the connection.
+		to 'connect' to teardown the connection. This is a
+		"link" TSM attribute, see
+		Documentation/ABI/testing/sysfs-class-tsm.
 
 What:		/sys/bus/pci/devices/.../authenticated
 Contact:	linux-pci@vger.kernel.org
@@ -663,3 +666,42 @@ Description:
 		When present and the tsm/ attribute directory is present, the
 		authenticated attribute is an alias for the device 'connect'
 		state. See the 'tsm/connect' attribute for more details.
+		This is a "link" TSM attribute, see
+		Documentation/ABI/testing/sysfs-class-tsm.
+
+What:		/sys/bus/pci/devices/.../tsm/lock
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(RW) Write the name of a TSM (TEE Security Manager) device from
+		/sys/class/tsm to this file to request that TSM lock th device
+		device. This puts the device in a state where it can not accept
+		or issue secure memory cycles (T=1 in the PCIe TLP), and
+		security sensitive configuration setting can not be changed
+		without transitioning the device the PCIe TDISP ERROR state.
+		Reads from this attribute return the name of the lock-holding
+		TSM or the empty string if not locked. A TSM device signals its
+		readiness for lock requests via a KOBJ_CHANGE event. Writes fail
+		with EBUSY if this device is bound to a driver. This is a
+		"devsec" TSM attribute, see
+		Documentation/ABI/testing/sysfs-class-tsm.
+
+What:		/sys/bus/pci/devices/.../tsm/unlock
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(WO) Write the name of the TSM device that was specified to
+		'lock' to teardown the connection. Writes fail with EBUSY if
+		this device is bound to a driver. This is a "devsec" TSM
+		attribute, see Documentation/ABI/testing/sysfs-class-tsm.
+
+What:		/sys/bus/pci/devices/.../tsm/accept
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(RW) Write "1" (or any boolean "true" string) to this file to
+		request that TSM transition the device from the TDISP LOCKED
+		state to the RUN state and arrange the for the secure IOMMU to
+		accept requests with T=1 in the PCIe packet header (TLP)
+		targeting private memory. Per TDISP the only exits from the RUN
+		state are via an explicit unlock request or an event that
+		transitions the device to the ERROR state. Writes fail with
+		EBUSY if this device is bound to a driver. This is a "devsec"
+		TSM attribute, see Documentation/ABI/testing/sysfs-class-tsm.
diff --git a/Documentation/ABI/testing/sysfs-class-tsm b/Documentation/ABI/testing/sysfs-class-tsm
index 6fc1a5ac6da1..d1bcc1a266ca 100644
--- a/Documentation/ABI/testing/sysfs-class-tsm
+++ b/Documentation/ABI/testing/sysfs-class-tsm
@@ -17,3 +17,22 @@ Description:
 		across host bridges. The link points to the endpoint PCI device
 		and matches the same link published by the host bridge. See
 		Documentation/ABI/testing/sysfs-devices-pci-host-bridge.
+
+What:		/sys/class/tsm/tsmN/pci_mode
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(RO) A TSM with PCIe TDISP capability can be in one of two
+		modes.
+
+		    "link": typically for a hypervisor (VMM) to authenticate,
+			    establish a secure session, and setup link
+			    encryption.
+
+		    "devsec": typically for a confidential guest (TVM) to
+			      transition assigned devices through the TDISP
+			      state machine UNLOCKED->LOCKED->RUN.
+
+		See the "tsm/" entries in
+		Documentation/ABI/testing/sysfs-bus-pci for the available PCI
+		device attributes when a TSM with the given "pci_mode" is
+		registered.
diff --git a/drivers/pci/Kconfig b/drivers/pci/Kconfig
index 0183ca6f6954..d595e8fd8c3d 100644
--- a/drivers/pci/Kconfig
+++ b/drivers/pci/Kconfig
@@ -138,6 +138,8 @@ config PCI_IDE_STREAM_MAX
 
 config PCI_TSM
 	bool "PCI TSM: Device security protocol support"
+	depends on ARCH_HAS_CC_PLATFORM
+	select CONFIDENTIAL_DEVICES
 	select PCI_IDE
 	select PCI_DOE
 	select TSM
diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index 3143558373e3..948300f0ce92 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -9,6 +9,7 @@
 #define dev_fmt(fmt) "PCI/TSM: " fmt
 
 #include <linux/bitfield.h>
+#include <linux/ioport.h>
 #include <linux/pci.h>
 #include <linux/pci-doe.h>
 #include <linux/pci-tsm.h>
@@ -35,6 +36,11 @@ static inline bool is_dsm(struct pci_dev *pdev)
 	return pdev->tsm && pdev->tsm->dsm == pdev;
 }
 
+static inline bool has_tee(struct pci_dev *pdev)
+{
+	return pdev->devcap & PCI_EXP_DEVCAP_TEE;
+}
+
 /* 'struct pci_tsm_pf0' wraps 'struct pci_tsm' when ->dsm == ->pdev (self) */
 static struct pci_tsm_pf0 *to_pci_tsm_pf0(struct pci_tsm *pci_tsm)
 {
@@ -48,6 +54,24 @@ static struct pci_tsm_pf0 *to_pci_tsm_pf0(struct pci_tsm *pci_tsm)
 	return container_of(pci_tsm, struct pci_tsm_pf0, base);
 }
 
+static inline bool is_devsec(struct pci_dev *pdev)
+{
+	return pdev->tsm && pdev->tsm->dsm == NULL && pdev->tsm->tdi == NULL;
+}
+
+/* 'struct pci_tsm_devsec' wraps 'struct pci_tsm' when ->tdi == ->dsm == NULL */
+static struct pci_tsm_devsec *to_pci_tsm_devsec(struct pci_tsm *pci_tsm)
+{
+	struct pci_dev *pdev = pci_tsm->pdev;
+
+	if (!is_devsec(pdev) || !has_tee(pdev)) {
+		dev_WARN_ONCE(&pdev->dev, 1, "invalid context object\n");
+		return NULL;
+	}
+
+	return container_of(pci_tsm, struct pci_tsm_devsec, base);
+}
+
 static void tsm_remove(struct pci_tsm *tsm)
 {
 	struct pci_dev *pdev;
@@ -453,6 +477,265 @@ static ssize_t disconnect_store(struct device *dev,
 }
 static DEVICE_ATTR_WO(disconnect);
 
+static struct resource **alloc_encrypted_resources(struct pci_dev *pdev,
+						   struct resource **__res)
+{
+	int i;
+
+	memset(__res, 0, sizeof(struct resource *) * PCI_NUM_RESOURCES);
+
+	for (i = 0; i < PCI_NUM_RESOURCES; i++) {
+		unsigned long flags = pci_resource_flags(pdev, i);
+		resource_size_t len = pci_resource_len(pdev, i);
+
+		if (!len || !(flags & IORESOURCE_MEM))
+			continue;
+
+
+		__res[i] = kzalloc(sizeof(struct resource), GFP_KERNEL);
+		if (!__res[i])
+			break;
+
+		*__res[i] = DEFINE_RES_NAMED_DESC(pci_resource_start(pdev, i),
+						  len, "PCI MMIO Encrypted",
+						  flags, IORES_DESC_ENCRYPTED);
+
+		if (insert_resource(&iomem_resource, __res[i]) != 0) {
+			kfree(__res[i]);
+			__res[i] = NULL;
+			break;
+		}
+	}
+
+	if (i >= PCI_NUM_RESOURCES)
+		return __res;
+
+	for (; i >= 0; i--) {
+		if (!__res[i])
+			continue;
+
+		remove_resource(__res[i]);
+		kfree(__res[i]);
+		__res[i] = NULL;
+	}
+
+	return NULL;
+}
+
+static void set_encrypted_resources(struct pci_tsm_devsec *tsm,
+				    struct resource **res)
+{
+	memcpy(tsm->resource, res, sizeof(tsm->resource));
+}
+
+static void free_encrypted_resources(struct resource **res)
+{
+	for (int i = PCI_NUM_RESOURCES - 1; i >= 0; i--) {
+		if (!res[i])
+			continue;
+		remove_resource(res[i]);
+		kfree(res[i]);
+		res[i] = NULL;
+	}
+}
+
+DEFINE_FREE(free_encrypted_resources, struct resource **,
+	    if (_T) free_encrypted_resources(_T))
+
+/**
+ * pci_tsm_accept() - accept a device for private MMIO+DMA operation
+ * @pdev: PCI device to accept
+ *
+ * "Accept" transitions a device to the run state, it is only suitable to make
+ * that transition from a known DMA-idle (no active mappings) state. The "driver
+ * detached" state is a coarse way to assert that requirement.
+ */
+static int pci_tsm_accept(struct pci_dev *pdev)
+{
+	struct resource *__res[PCI_NUM_RESOURCES];
+	int rc;
+
+	ACQUIRE(rwsem_read_intr, lock)(&pci_tsm_rwsem);
+	if ((rc = ACQUIRE_ERR(rwsem_read_intr, &lock)))
+		return rc;
+
+	if (!pdev->tsm)
+		return -EINVAL;
+
+	ACQUIRE(device_intr, dev_lock)(&pdev->dev);
+	if ((rc = ACQUIRE_ERR(device_intr, &dev_lock)))
+		return rc;
+
+	if (pdev->dev.driver)
+		return -EBUSY;
+
+	struct resource **res __free(free_encrypted_resources) =
+		alloc_encrypted_resources(pdev, __res);
+	if (!res)
+		return -ENOMEM;
+
+	rc = pdev->tsm->ops->accept(pdev);
+	if (rc)
+		return rc;
+	device_cc_accept(&pdev->dev);
+	set_encrypted_resources(to_pci_tsm_devsec(pdev->tsm), no_free_ptr(res));
+
+	return 0;
+}
+
+static ssize_t accept_store(struct device *dev, struct device_attribute *attr,
+			    const char *buf, size_t len)
+{
+	struct pci_dev *pdev = to_pci_dev(dev);
+	bool accept;
+	int rc;
+
+	rc = kstrtobool(buf, &accept);
+	if (rc)
+		return rc;
+
+	/*
+	 * TDISP can only go from RUN to UNLOCKED/ERROR, so there is no
+	 * 'unaccept' verb.
+	 */
+	if (!accept)
+		return -EINVAL;
+
+	rc = pci_tsm_accept(pdev);
+	if (rc)
+		return rc;
+
+	return len;
+}
+
+static ssize_t accept_show(struct device *dev, struct device_attribute *attr,
+			   char *buf)
+{
+	return sysfs_emit(buf, "%d\n", device_cc_accepted(dev));
+}
+static DEVICE_ATTR_RW(accept);
+
+/**
+ * pci_tsm_unlock() - Transition TDI from LOCKED/RUN to UNLOCKED
+ * @pdev: TDI device to unlock
+ *
+ * Returns void, requires all callers to have satisfied dependencies like making
+ * sure the device is locked and detached from its driver.
+ */
+static void pci_tsm_unlock(struct pci_dev *pdev)
+{
+	struct pci_tsm_devsec *tsm = to_pci_tsm_devsec(pdev->tsm);
+
+	lockdep_assert_held_write(&pci_tsm_rwsem);
+	lockdep_assert_held(&pdev->dev.mutex);
+
+	if (dev_WARN_ONCE(&pdev->dev, pdev->dev.driver,
+			  "unlock attempted on driver attached device\n"))
+		return;
+
+	free_encrypted_resources(tsm->resource);
+	device_cc_reject(&pdev->dev);
+	pdev->tsm->ops->unlock(pdev);
+	pdev->tsm = NULL;
+}
+
+static int pci_tsm_lock(struct pci_dev *pdev, struct tsm_dev *tsm_dev)
+{
+	const struct pci_tsm_ops *ops = tsm_pci_ops(tsm_dev);
+	struct pci_tsm *tsm;
+	int rc;
+
+	ACQUIRE(device_intr, lock)(&pdev->dev);
+	if ((rc = ACQUIRE_ERR(device_intr, &lock)))
+		return rc;
+
+	if (pdev->dev.driver)
+		return -EBUSY;
+
+	tsm = ops->lock(pdev);
+	if (IS_ERR(tsm))
+		return PTR_ERR(tsm);
+
+	pdev->tsm = tsm;
+	return 0;
+}
+
+static ssize_t lock_store(struct device *dev, struct device_attribute *attr,
+			  const char *buf, size_t len)
+{
+	struct pci_dev *pdev = to_pci_dev(dev);
+	struct tsm_dev *tsm_dev;
+	int rc, id;
+
+	rc = sscanf(buf, "tsm%d\n", &id);
+	if (rc != 1)
+		return -EINVAL;
+
+	ACQUIRE(rwsem_write_kill, lock)(&pci_tsm_rwsem);
+	if ((rc = ACQUIRE_ERR(rwsem_write_kill, &lock)))
+		return rc;
+
+	if (pdev->tsm)
+		return -EBUSY;
+
+	tsm_dev = find_tsm_dev(id);
+	if (!is_devsec_tsm(tsm_dev))
+		return -ENXIO;
+
+	rc = pci_tsm_lock(pdev, tsm_dev);
+	if (rc)
+		return rc;
+	return len;
+}
+
+static ssize_t lock_show(struct device *dev, struct device_attribute *attr,
+			 char *buf)
+{
+	struct pci_dev *pdev = to_pci_dev(dev);
+	int rc;
+
+	ACQUIRE(rwsem_read_intr, lock)(&pci_tsm_rwsem);
+	if ((rc = ACQUIRE_ERR(rwsem_read_intr, &lock)))
+		return rc;
+
+	if (!pdev->tsm)
+		return sysfs_emit(buf, "\n");
+
+	return sysfs_emit(buf, "%s\n", tsm_name(pdev->tsm->ops->owner));
+}
+static DEVICE_ATTR_RW(lock);
+
+static ssize_t unlock_store(struct device *dev, struct device_attribute *attr,
+			  const char *buf, size_t len)
+{
+	struct pci_dev *pdev = to_pci_dev(dev);
+	const struct pci_tsm_ops *ops;
+	int rc;
+
+	ACQUIRE(rwsem_write_kill, lock)(&pci_tsm_rwsem);
+	if ((rc = ACQUIRE_ERR(rwsem_write_kill, &lock)))
+		return rc;
+
+	if (!pdev->tsm)
+		return -EINVAL;
+
+	ops = pdev->tsm->ops;
+	if (!sysfs_streq(buf, tsm_name(ops->owner)))
+		return -EINVAL;
+
+	ACQUIRE(device_intr, dev_lock)(&pdev->dev);
+	if ((rc = ACQUIRE_ERR(device_intr, &dev_lock)))
+		return rc;
+
+	if (pdev->dev.driver)
+		return -EBUSY;
+
+	pci_tsm_unlock(pdev);
+
+	return len;
+}
+static DEVICE_ATTR_WO(unlock);
+
 /* The 'authenticated' attribute is exclusive to the presence of a 'link' TSM */
 static bool pci_tsm_link_group_visible(struct kobject *kobj)
 {
@@ -462,6 +745,13 @@ static bool pci_tsm_link_group_visible(struct kobject *kobj)
 }
 DEFINE_SIMPLE_SYSFS_GROUP_VISIBLE(pci_tsm_link);
 
+static bool pci_tsm_devsec_group_visible(struct kobject *kobj)
+{
+	struct pci_dev *pdev = to_pci_dev(kobj_to_dev(kobj));
+
+	return pci_tsm_devsec_count && has_tee(pdev);
+}
+
 /*
  * 'link' and 'devsec' TSMs share the same 'tsm/' sysfs group, so the TSM type
  * specific attributes need individual visibility checks.
@@ -475,18 +765,29 @@ static umode_t pci_tsm_attr_visible(struct kobject *kobj,
 			return attr->mode;
 	}
 
+	if (pci_tsm_devsec_group_visible(kobj)) {
+		if (attr == &dev_attr_accept.attr ||
+		    attr == &dev_attr_lock.attr ||
+		    attr == &dev_attr_unlock.attr)
+			return attr->mode;
+	}
+
 	return 0;
 }
 
 static bool pci_tsm_group_visible(struct kobject *kobj)
 {
-	return pci_tsm_link_group_visible(kobj);
+	return pci_tsm_link_group_visible(kobj) ||
+	       pci_tsm_devsec_group_visible(kobj);
 }
 DEFINE_SYSFS_GROUP_VISIBLE(pci_tsm);
 
 static struct attribute *pci_tsm_attrs[] = {
 	&dev_attr_connect.attr,
 	&dev_attr_disconnect.attr,
+	&dev_attr_accept.attr,
+	&dev_attr_lock.attr,
+	&dev_attr_unlock.attr,
 	NULL
 };
 
@@ -598,6 +899,29 @@ int pci_tsm_link_constructor(struct pci_dev *pdev, struct pci_tsm *tsm,
 }
 EXPORT_SYMBOL_GPL(pci_tsm_link_constructor);
 
+/**
+ * pci_tsm_devsec_constructor() - devsec TSM context initialization
+ * @pdev: The PCI device
+ * @tsm: context to initialize
+ * @ops: PCI devsec operations provided by the TSM
+ */
+int pci_tsm_devsec_constructor(struct pci_dev *pdev, struct pci_tsm_devsec *tsm,
+			       const struct pci_tsm_ops *ops)
+{
+	struct pci_tsm *pci_tsm = &tsm->base;
+
+	if (!is_devsec_tsm(ops->owner))
+		return -EINVAL;
+
+	pci_tsm->dsm = NULL;
+	pci_tsm->tdi = NULL;
+	pci_tsm->pdev = pdev;
+	pci_tsm->ops = ops;
+
+	return 0;
+}
+EXPORT_SYMBOL_GPL(pci_tsm_devsec_constructor);
+
 /**
  * pci_tsm_pf0_constructor() - common 'struct pci_tsm_pf0' (DSM) initialization
  * @pdev: Physical Function 0 PCI device (as indicated by is_pci_tsm_pf0())
@@ -637,6 +961,13 @@ static void pf0_sysfs_enable(struct pci_dev *pdev)
 	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_attr_group);
 }
 
+static void devsec_sysfs_enable(struct pci_dev *pdev)
+{
+	pci_dbg(pdev, "TEE I/O Device capability detected (TDISP)\n");
+
+	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_attr_group);
+}
+
 int pci_tsm_register(struct tsm_dev *tsm_dev)
 {
 	struct pci_dev *pdev = NULL;
@@ -664,8 +995,10 @@ int pci_tsm_register(struct tsm_dev *tsm_dev)
 		for_each_pci_dev(pdev)
 			if (is_pci_tsm_pf0(pdev))
 				pf0_sysfs_enable(pdev);
-	} else if (is_devsec_tsm(tsm_dev)) {
-		pci_tsm_devsec_count++;
+	} else if (is_devsec_tsm(tsm_dev) && pci_tsm_devsec_count++ == 0) {
+		for_each_pci_dev(pdev)
+			if (has_tee(pdev))
+				devsec_sysfs_enable(pdev);
 	}
 
 	return 0;
@@ -693,6 +1026,9 @@ static void __pci_tsm_destroy(struct pci_dev *pdev, struct tsm_dev *tsm_dev)
 		sysfs_update_group(&pdev->dev.kobj, &pci_tsm_attr_group);
 	}
 
+	if (is_devsec_tsm(tsm_dev) && !pci_tsm_devsec_count)
+		sysfs_update_group(&pdev->dev.kobj, &pci_tsm_attr_group);
+
 	if (!tsm)
 		return;
 
@@ -701,10 +1037,18 @@ static void __pci_tsm_destroy(struct pci_dev *pdev, struct tsm_dev *tsm_dev)
 	else if (tsm_dev != tsm->ops->owner)
 		return;
 
-	if (is_link_tsm(tsm_dev) && is_pci_tsm_pf0(pdev))
-		pci_tsm_disconnect(pdev);
-	else
-		tsm_remove(pdev->tsm);
+	/* Disconnect DSMs, unlock assigned TDIs, or cleanup DSM subfunctions */
+	if (is_link_tsm(tsm_dev)) {
+		if (is_pci_tsm_pf0(pdev))
+			pci_tsm_disconnect(pdev);
+		else
+			tsm_remove(pdev->tsm);
+	}
+
+	if (is_devsec_tsm(tsm_dev) && has_tee(pdev)) {
+		guard(device)(&pdev->dev);
+		pci_tsm_unlock(pdev);
+	}
 }
 
 void pci_tsm_destroy(struct pci_dev *pdev)
diff --git a/drivers/virt/coco/tsm-core.c b/drivers/virt/coco/tsm-core.c
index f5bab1a9c617..488df6d396a0 100644
--- a/drivers/virt/coco/tsm-core.c
+++ b/drivers/virt/coco/tsm-core.c
@@ -66,6 +66,45 @@ static struct tsm_dev *alloc_tsm_dev(struct device *parent)
 	return no_free_ptr(tsm_dev);
 }
 
+static ssize_t pci_mode_show(struct device *dev, struct device_attribute *attr,
+			     char *buf)
+{
+	struct tsm_dev *tsm_dev = container_of(dev, struct tsm_dev, dev);
+	const struct pci_tsm_ops *ops = tsm_dev->pci_ops;
+
+	if (ops->connect)
+		return sysfs_emit(buf, "link\n");
+	if (ops->lock)
+		return sysfs_emit(buf, "devsec\n");
+	return sysfs_emit(buf, "none\n");
+}
+static DEVICE_ATTR_RO(pci_mode);
+
+static umode_t tsm_pci_visible(struct kobject *kobj, struct attribute *attr, int n)
+{
+	struct device *dev = container_of(kobj, struct device, kobj);
+	struct tsm_dev *tsm_dev = container_of(dev, struct tsm_dev, dev);
+
+	if (tsm_dev->pci_ops)
+		return attr->mode;
+	return 0;
+}
+
+static struct attribute *tsm_pci_attrs[] = {
+	&dev_attr_pci_mode.attr,
+	NULL
+};
+
+static const struct attribute_group tsm_pci_group = {
+	.attrs = tsm_pci_attrs,
+	.is_visible = tsm_pci_visible,
+};
+
+static const struct attribute_group *tsm_pci_groups[] = {
+	&tsm_pci_group,
+	NULL
+};
+
 static struct tsm_dev *tsm_register_pci_or_reset(struct tsm_dev *tsm_dev,
 						 struct pci_tsm_ops *pci_ops)
 {
@@ -83,6 +122,7 @@ static struct tsm_dev *tsm_register_pci_or_reset(struct tsm_dev *tsm_dev,
 		device_unregister(&tsm_dev->dev);
 		return ERR_PTR(rc);
 	}
+	sysfs_update_group(&tsm_dev->dev.kobj, &tsm_pci_group);
 
 	/* Notify TSM userspace that PCI/TSM operations are now possible */
 	kobject_uevent(&tsm_dev->dev.kobj, KOBJ_CHANGE);
@@ -168,6 +208,7 @@ static int __init tsm_init(void)
 	if (IS_ERR(tsm_class))
 		return PTR_ERR(tsm_class);
 
+	tsm_class->dev_groups = tsm_pci_groups;
 	tsm_class->dev_release = tsm_release;
 	return 0;
 }
diff --git a/include/linux/device.h b/include/linux/device.h
index 43d072866949..764461e9effb 100644
--- a/include/linux/device.h
+++ b/include/linux/device.h
@@ -927,6 +927,7 @@ static inline void device_unlock(struct device *dev)
 }
 
 DEFINE_GUARD(device, struct device *, device_lock(_T), device_unlock(_T))
+DEFINE_GUARD_COND(device, _intr, device_lock_interruptible(_T), _RET == 0)
 
 static inline void device_lock_assert(struct device *dev)
 {
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index 5b61aac2e9f7..37fafbfce386 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -60,13 +60,17 @@ struct pci_tsm_ops {
 	 * struct pci_tsm_security_ops - Manage the security state of the function
 	 * @lock: probe and initialize the device in the LOCKED state
 	 * @unlock: destroy TSM context and return device to UNLOCKED state
+	 * @accept: accept a locked TDI for use, move it to RUN state
 	 *
 	 * Context: @lock and @unlock run under pci_tsm_rwsem held for write to
-	 * sync with TSM unregistration and each other
+	 * sync with TSM unregistration and each other. @accept runs under
+	 * pci_tsm_rwsem held for read. All operations run under the device lock
+	 * for mutual exclusion with driver attach and detach.
 	 */
 	struct_group_tagged(pci_tsm_security_ops, devsec_ops,
 		struct pci_tsm *(*lock)(struct pci_dev *pdev);
 		void (*unlock)(struct pci_dev *pdev);
+		int (*accept)(struct pci_dev *pdev);
 	);
 	struct tsm_dev *owner;
 };
@@ -97,6 +101,13 @@ struct pci_tdi {
  * sub-function (SR-IOV virtual function, or non-function0
  * multifunction-device), or a downstream endpoint (PCIe upstream switch-port as
  * DSM).
+ *
+ * For devsec operations it serves to indicate that the function / TDI has been
+ * locked to a given TSM.
+ *
+ * The common expectation is that there is only ever one TSM, but this is not
+ * enforced. The implementation only enforces that a device can be "connected"
+ * to a TSM instance or "locked" to a different TSM.
  */
 struct pci_tsm {
 	struct pci_dev *pdev;
@@ -117,6 +128,16 @@ struct pci_tsm_pf0 {
 	struct pci_doe_mb *doe_mb;
 };
 
+/**
+ * struct pci_tsm_devsec - context for tracking private/accepted PCI resources
+ * @base: generic core "tsm" context
+ * @resource: encrypted MMIO resources for this assigned device
+ */
+struct pci_tsm_devsec {
+	struct pci_tsm base;
+	struct resource *resource[PCI_NUM_RESOURCES];
+};
+
 /* physical function0 and capable of 'connect' */
 static inline bool is_pci_tsm_pf0(struct pci_dev *pdev)
 {
@@ -193,6 +214,8 @@ int pci_tsm_link_constructor(struct pci_dev *pdev, struct pci_tsm *tsm,
 			     const struct pci_tsm_ops *ops);
 int pci_tsm_pf0_constructor(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm,
 			    const struct pci_tsm_ops *ops);
+int pci_tsm_devsec_constructor(struct pci_dev *pdev, struct pci_tsm_devsec *tsm,
+			       const struct pci_tsm_ops *ops);
 void pci_tsm_pf0_destructor(struct pci_tsm_pf0 *tsm);
 int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u32 tdi_id);
 void pci_tsm_unbind(struct pci_dev *pdev);

---

## [7] Dan Williams — 2025-08-26
*Subject: [PATCH 6/7] samples/devsec: Introduce a "Device Security TSM" sample driver*

There are 2 sides to a TEE Security Manager (TSM), the 'link' TSM, and the
'devsec' TSM. The 'link' TSM, outside the TEE, establishes physical link
confidentiality and integerity, and a secure session for transporting
commands the manage the security state of devices. The 'devsec' TSM, within
the TEE, issues requests for confidential devices to lock their
configuration and transition to secure operation.

Implement a sample implementation of a 'devsec' TSM. This leverages the PCI
core's ability to register multiple TSMs at a time to load a sample
devsec_tsm module alongside the existing devsec_link_tsm module. When both
are loaded the TSM personality is selected by choosing to 'connect' vs
'lock' the device.

Drivers like tdx_guest, sev_guest, or arm-cca-guest are examples of "Device
Security TSM" drivers.

A devsec_pci driver is included to test the device_cc_probe() helper for
drivers that need to coordinate some configuration before 'lock' and
'accept'.

Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 samples/devsec/Makefile |  6 +++
 samples/devsec/pci.c    | 43 ++++++++++++++++++
 samples/devsec/tsm.c    | 99 +++++++++++++++++++++++++++++++++++++++++
 3 files changed, 148 insertions(+)
 create mode 100644 samples/devsec/pci.c
 create mode 100644 samples/devsec/tsm.c

diff --git a/samples/devsec/Makefile b/samples/devsec/Makefile
index da122eb8d23d..0c52448a629f 100644
--- a/samples/devsec/Makefile
+++ b/samples/devsec/Makefile
@@ -8,3 +8,9 @@ devsec_bus-y := bus.o
 
 obj-$(CONFIG_SAMPLE_DEVSEC) += devsec_link_tsm.o
 devsec_link_tsm-y := link_tsm.o
+
+obj-$(CONFIG_SAMPLE_DEVSEC) += devsec_tsm.o
+devsec_tsm-y := tsm.o
+
+obj-$(CONFIG_SAMPLE_DEVSEC) += devsec_pci.o
+devsec_pci-y := pci.o
diff --git a/samples/devsec/pci.c b/samples/devsec/pci.c
new file mode 100644
index 000000000000..4661529fe10c
--- /dev/null
+++ b/samples/devsec/pci.c
@@ -0,0 +1,43 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright(c) 2024 - 2025 Intel Corporation. All rights reserved. */
+#include <linux/device.h>
+#include <linux/module.h>
+#include <linux/pci.h>
+
+static int devsec_pci_probe(struct pci_dev *pdev,
+			    const struct pci_device_id *id)
+{
+	void __iomem *base;
+	int rc;
+
+	rc = pcim_enable_device(pdev);
+	if (rc)
+		return dev_err_probe(&pdev->dev, rc, "enable failed\n");
+
+	base = pcim_iomap_region(pdev, 0, KBUILD_MODNAME);
+	if (IS_ERR(base))
+		return dev_err_probe(&pdev->dev, PTR_ERR(base),
+				     "iomap failed\n");
+
+	rc = device_cc_probe(&pdev->dev);
+	if (rc)
+		return rc;
+
+	dev_dbg(&pdev->dev, "attach\n");
+	return 0;
+}
+
+static const struct pci_device_id devsec_pci_ids[] = {
+	{ PCI_DEVICE(0x8086, 0xffff), .override_only = 1, },
+	{ }
+};
+
+static struct pci_driver devsec_pci_driver = {
+	.name = "devsec_pci",
+	.probe = devsec_pci_probe,
+	.id_table = devsec_pci_ids,
+};
+
+module_pci_driver(devsec_pci_driver);
+MODULE_LICENSE("GPL");
+MODULE_DESCRIPTION("Device Security Sample Infrastructure: Secure PCI Driver");
diff --git a/samples/devsec/tsm.c b/samples/devsec/tsm.c
new file mode 100644
index 000000000000..4de2d45db4c3
--- /dev/null
+++ b/samples/devsec/tsm.c
@@ -0,0 +1,99 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright(c) 2024 - 2025 Intel Corporation. All rights reserved. */
+
+#define dev_fmt(fmt) "devsec: " fmt
+#include <linux/device/faux.h>
+#include <linux/pci-tsm.h>
+#include <linux/module.h>
+#include <linux/pci.h>
+#include <linux/tsm.h>
+#include "devsec.h"
+
+struct devsec_dev_data {
+	struct pci_tsm_devsec pci;
+};
+
+static struct devsec_dev_data *to_devsec_data(struct pci_tsm *tsm)
+{
+	return container_of(tsm, struct devsec_dev_data, pci.base);
+}
+
+static const struct pci_tsm_ops *__devsec_pci_ops;
+
+static struct pci_tsm *devsec_tsm_lock(struct pci_dev *pdev)
+{
+	int rc;
+
+	struct devsec_dev_data *devsec_data __free(kfree) =
+		kzalloc(sizeof(*devsec_data), GFP_KERNEL);
+	if (!devsec_data)
+		return ERR_PTR(-ENOMEM);
+
+	rc = pci_tsm_devsec_constructor(pdev, &devsec_data->pci,
+					__devsec_pci_ops);
+	if (rc)
+		return ERR_PTR(rc);
+
+	return &no_free_ptr(devsec_data)->pci.base;
+}
+
+static void devsec_tsm_unlock(struct pci_dev *pdev)
+{
+	struct devsec_dev_data *devsec_data = to_devsec_data(pdev->tsm);
+
+	kfree(devsec_data);
+}
+
+static int devsec_tsm_accept(struct pci_dev *pdev)
+{
+	/* LGTM */
+	return 0;
+}
+
+static struct pci_tsm_ops devsec_pci_ops = {
+	.lock = devsec_tsm_lock,
+	.unlock = devsec_tsm_unlock,
+	.accept = devsec_tsm_accept,
+};
+
+static void devsec_tsm_remove(void *tsm_dev)
+{
+	tsm_unregister(tsm_dev);
+}
+
+static int devsec_tsm_probe(struct faux_device *fdev)
+{
+	struct tsm_dev *tsm_dev;
+
+	tsm_dev = tsm_register(&fdev->dev, &devsec_pci_ops);
+	if (IS_ERR(tsm_dev))
+		return PTR_ERR(tsm_dev);
+
+	return devm_add_action_or_reset(&fdev->dev, devsec_tsm_remove,
+					tsm_dev);
+}
+
+static struct faux_device *devsec_tsm;
+
+static const struct faux_device_ops devsec_device_ops = {
+	.probe = devsec_tsm_probe,
+};
+
+static int __init devsec_tsm_init(void)
+{
+	__devsec_pci_ops = &devsec_pci_ops;
+	devsec_tsm = faux_device_create("devsec_tsm", NULL, &devsec_device_ops);
+	if (!devsec_tsm)
+		return -ENOMEM;
+	return 0;
+}
+module_init(devsec_tsm_init);
+
+static void __exit devsec_tsm_exit(void)
+{
+	faux_device_destroy(devsec_tsm);
+}
+module_exit(devsec_tsm_exit);
+
+MODULE_LICENSE("GPL");
+MODULE_DESCRIPTION("Device Security Sample Infrastructure: Device Security TSM Driver");

---

## [8] Dan Williams — 2025-08-26
*Subject: [PATCH 7/7] tools/testing/devsec: Add a script to exercise samples/devsec/*

Run the samples/devsec/ infrastructure through the PCIe TDISP connect,
lock, and accept flows.

Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 tools/testing/devsec/devsec.sh | 138 +++++++++++++++++++++++++++++++++
 1 file changed, 138 insertions(+)
 create mode 100755 tools/testing/devsec/devsec.sh

diff --git a/tools/testing/devsec/devsec.sh b/tools/testing/devsec/devsec.sh
new file mode 100755
index 000000000000..cbf4b43ec93a
--- /dev/null
+++ b/tools/testing/devsec/devsec.sh
@@ -0,0 +1,138 @@
+#!/bin/bash
+# SPDX-License-Identifier: GPL-2.0
+# Copyright(c) 2025 Intel Corporation. All rights reserved.
+
+# Checkout PCI/TSM sysfs and driver-core mechanics with the
+# devsec_link_tsm and devsec_tsm sample modules from samples/devsec/.
+
+set -ex
+
+trap 'err $LINENO' ERR
+err() {
+        echo $(basename $0): failed at line $1
+        [ -n "$2" ] && "$2"
+        exit 1
+}
+
+ORDER=""
+
+setup_modules() {
+	if [[ $ORDER == "bus" ]]; then
+		modprobe devsec_bus
+		modprobe devsec_link_tsm
+		modprobe devsec_tsm
+	else
+		modprobe devsec_tsm
+		modprobe devsec_link_tsm
+		modprobe devsec_bus
+	fi
+}
+
+teardown_modules() {
+	if [[ $ORDER == "bus" ]]; then
+		modprobe -r devsec_tsm
+		modprobe -r devsec_link_tsm
+		modprobe -r devsec_bus
+	else
+		modprobe -r devsec_bus
+		modprobe -r devsec_link_tsm
+		modprobe -r devsec_tsm
+	fi
+}
+
+pci_dev="/sys/bus/pci/devices/10000:01:00.0"
+tsm_devsec=""
+tsm_link=""
+devsec_pci="/sys/bus/pci/drivers/devsec_pci"
+
+tdisp_test() {
+	# with the device disconnected from the link TSM validate that
+	# the devsec_pci driver fails to claim the device, and that the
+	# device is registered in the deferred probe queue
+	echo "devsec_pci" > $pci_dev/driver_override
+	modprobe devsec_pci
+
+	cat /sys/kernel/debug/devices_deferred | grep -q $(basename $pci_dev) || err "$LINENO"
+
+	# grab the device's resource from /proc/iomem
+	resource=$(cat /proc/iomem | grep -m1 $(basename $pci_dev) | awk -F ' :' '{print $1}' | tr -d ' ')
+	[[ -n $resource ]] || err "$LINENO"
+
+	# lock and accept the device, validate that the resource is now
+	# marked encrypted
+	echo $(basename $tsm_devsec) > $pci_dev/tsm/lock
+	echo $(basename $tsm_devsec) > $pci_dev/tsm/accept
+
+	cat /proc/iomem | grep "$resource" | grep -q -m1 "PCI MMIO Encrypted" || err "$LINENO"
+
+	# validate that the driver now fails with -EINVAL when trying to
+	# bind
+	expect="echo: write error: Invalid argument"
+	echo $(basename $pci_dev) 2>&1 > $devsec_pci/bind | grep -q "$expect" || err "$LINENO"
+
+	# unlock and validate that the encrypted mmio is removed
+	echo $(basename $tsm_devsec) > $pci_dev/tsm/unlock
+	cat /proc/iomem | grep "$resource" | grep -q "PCI MMIO Encrypted" && err "$LINENO"
+
+	modprobe -r devsec_pci
+}
+
+ide_test() {
+	# validate that all of the secure streams are idle by default
+	host_bridge=$(dirname $(dirname $(readlink -f $pci_dev)))
+	nr=$(cat $host_bridge/available_secure_streams)
+	[[ $nr == 4 ]] || err "$LINENO"
+
+	# connect a stream and validate that the stream link shows up at
+	# the host bridge and the TSM
+	echo $(basename $tsm_link) > $pci_dev/tsm/connect
+	nr=$(cat $host_bridge/available_secure_streams)
+	[[ $nr == 3 ]] || err "$LINENO"
+
+	[[ $(cat $pci_dev/tsm/connect) == $(basename $tsm_link) ]] || err "$LINENO"
+	[[ -e $host_bridge/stream0.0.0 ]] || err "$LINENO"
+	[[ -e $tsm_link/stream0.0.0 ]] || err "$LINENO"
+
+	# check that the links disappear at disconnect and the stream
+	# pool is refilled
+	echo $(basename $tsm_link) > $pci_dev/tsm/disconnect
+	nr=$(cat $host_bridge/available_secure_streams)
+	[[ $nr == 4 ]] || err "$LINENO"
+
+	[[ $(cat $pci_dev/tsm/connect) == "" ]] || err "$LINENO"
+	[[ ! -e $host_bridge/stream0.0.0 ]] || err "$LINENO"
+	[[ ! -e $tsm_link/stream0.0.0 ]] || err "$LINENO"
+}
+
+devsec_test() {
+	setup_modules
+
+	# find the tsm devices by personality
+	for tsm in /sys/class/tsm/tsm*; do
+		mode=$(cat $tsm/pci_mode)
+		[[ $mode == "devsec" ]] && tsm_devsec=$tsm
+		[[ $mode == "link" ]] && tsm_link=$tsm
+	done
+	[[ -n $tsm_devsec ]] || err "$LINENO"
+	[[ -n $tsm_link ]] || err "$LINENO"
+
+	# check that devsec bus loads correctly and the TSM is detected
+	[[ -e $pci_dev ]] || err "$LINENO"
+	[[ -e $pci_dev/tsm ]] || err "$LINENO"
+
+	ide_test
+	tdisp_test
+
+	# reconnect and test surprise removal of the TSM or device
+	echo $(basename $tsm_link) > $pci_dev/tsm/connect
+	[[ $(cat $pci_dev/tsm/connect) == $(basename $tsm_link) ]] || err "$LINENO"
+	[[ -e $host_bridge/stream0.0.0 ]] || err "$LINENO"
+	[[ -e $tsm_link/stream0.0.0 ]] || err "$LINENO"
+
+	teardown_modules
+}
+
+ORDER="bus"
+devsec_test
+ORDER="tsm"
+devsec_test

---

## [9] Greg KH — 2025-08-27
*Subject: Re: [PATCH 3/7] device core: Introduce confidential device acceptance*

On Tue, Aug 26, 2025 at 08:52:55PM -0700, Dan Williams wrote:
> --- a/drivers/base/base.h
> +++ b/drivers/base/base.h

Why did you not just use another u8:1 at the end?  You kind of added a
big hole in the structure that is created for every device :(


>  };
> diff --git a/drivers/base/coco.c b/drivers/base/coco.c

No copyright at the top?  Bold :)

> +#include <linux/device.h>
> +#include <linux/dev_printk.h>

What does TEE mean here?  I feel you mix "confidential" and TEE a bunch.

> + * @dev: device to accept
> + *

If not locked you just keep going?  Why not return an error?

thanks,

greg k-h

---

## [10] Jason Gunthorpe — 2025-08-27
*Subject: Re: [PATCH 6/7] samples/devsec: Introduce a "Device Security TSM"
 sample driver*

On Tue, Aug 26, 2025 at 08:52:58PM -0700, Dan Williams wrote:
> +static int devsec_pci_probe(struct pci_dev *pdev,
> +			    const struct pci_device_id *id)

I really don't understand what the proposal is here?

device_cc_probe() doesn't save anything, doesn't this just get into an
endless loop of EPROBE_DEFER? Usually the kernel will retry these
things during booting?

How does userspace accept through the sysfs retrigger probing?

As we discussed in the prior chain we need to have a policy decision
before auto-binding drivers at all in a CC environment, I don't see
that in the code though the cover letter talked about it??

How does the kernel/userspace tell the difference between drivers that
want this early binding and those that don't?

Can you write out the whole flow from a userspace perspective in one
of the commit messages?

This also disables BME, we talked about that a lot, the commit
messages didn't seem to describe what solution was settled on here?

Jason

---

## [11] Alexey Kardashevskiy — 2025-08-28
*Subject: Re: [PATCH 6/7] samples/devsec: Introduce a "Device Security TSM"
 sample driver*

On 27/8/25 22:39, Jason Gunthorpe wrote:
> On Tue, Aug 26, 2025 at 08:52:58PM -0700, Dan Williams wrote:
>> +static int devsec_pci_probe(struct pci_dev *pdev,

My current flow is:
- blacklist the driver,
- let the userspace "lock", attest, then "accept" via sysfs,
- modprove the device driver as usual - at this point DMA is enabled (device::force_encrypted_dma=1) and MMIOs are "validated" (in AMD's SNP words);
- the device driver will enable BME, which is allowed to go from 0 to 1 in the RUN state (my test device did not allow it in early days, now fixed);
- the device driver will map MMIO as usual and iomap() will do the right thing as it knows by now if the region is encrypted.

Thanks,



> 
> Jason

---

## [12] Alexey Kardashevskiy — 2025-08-28
*Subject: Re: [PATCH 2/7] PCI/TSM: Add pci_tsm_guest_req() for managing TDIs*

On 27/8/25 13:52, Dan Williams wrote:
> A PCIe device function interface assigned to a TVM is a TEE Device
> Interface (TDI). A TDI instantiated by pci_tsm_bind() needs additional

s/transititions/transitions/

> these are long running operations involving SPDM message passing via the
> DOE mailbox, i.e. another 'struct pci_tsm_link_ops' operation.


KVM will have to know about the host's pci_dev which it does not. I'd postpone mentioning KVM here till it learns about pci_dev, if.


> + * to TDI information or state change requests. The scope parameter limits
> + * requests to TDISP state management, or limited debug.

Uff... So the caller (which is IOMMUFD vdevice) has to check and decide on whether to kvfree. ioctl() is likely to have 2 buffers anyway and preallocate the response buffer, why make IOMMUFD care about this?

> + *
> + * Context: Caller is responsible for calling this within the pci_tsm_bind()

Why double braces?

> +		return ERR_PTR(rc);
> +

We have pdev in pci_tdi, pci_tsm and pci_tsm_pf0 (via .base), using these in pci_tsm_ops will document better which call is allowed on what entity - DSM or TDI. Or may be ditch those back "pdev" references?


> +				   enum pci_tsm_req_scope scope, void *req_in,
> +				   size_t in_len, size_t *out_len);


Out of curiosity (probably could go to the commit log) - for what kind of request and on which platform we do not know the response size in advance? On AMD, the request and response sizes are fixed.

And the userspace (which makes such request) will allocate some memory before calling such ioctl(), can "void *req_in" be "void __user *reg_in"? The CCP driver is going to copy the request and response anyway as there are RMP rules about them.

And what is wrong with returning "int" as an error vs ERR_PTR(), is there a recommendation for this, or something?


>   	);
>   


What is going to enforce this and how? It is a guest request, ideally encrypted, and the host does not really have to know the nature of the request (if the guest wants something from the host to do in addition to what is it asking the TSM to do - then GHCB is for that). And 3 of 4 AMD TIO requests (STATE_CHANGE is a host request and no plan for DEBUG) do not fit in any category from the above anyway. imho we do not need it at least now. Thanks,



> +};
> +

---

## [13] Aneesh Kumar K.V — 2025-08-28
*Subject: Re: [PATCH 2/7] PCI/TSM: Add pci_tsm_guest_req() for managing TDIs*

Dan Williams <dan.j.williams@intel.com> writes:

> +/** 
> + * enum pci_tsm_req_scope - Scope of guest requests to be validated by TSM

Will all architectures need to support all the above pci_tsm_req_scope
values?

For example, on ARM, I’ve implemented a simpler approach [1] by using an
architecture-specific pci_tsm_req_scope / type. This simplifies
the implementation, as I can access `info->req` and `info->resp`
directly within the same callback, without needing an additional
structure to carry arch-specific request types like
`ARM_CCA_DA_OBJECT_SIZE` or `ARM_CCA_DA_OBJECT_READ`.

[1] https://git.gitlab.arm.com/linux-arm/linux-cca/-/commit/ae6e667a6426fdeff9cdf9f6807acb8a5d5d601f

-aneesh

---

## [14] dan.j.williams@intel.com — 2025-08-28
*Subject: Re: [PATCH 3/7] device core: Introduce confidential device acceptance*

Greg KH wrote:
> On Tue, Aug 26, 2025 at 08:52:55PM -0700, Dan Williams wrote:
> > --- a/drivers/base/base.h

It was the concern for colliding bitfield updates. I will go audit if
all ->dead and ->cc_accepted updates can be guaranteed to be ordered by
the device_lock(), or otherwise put this bool in a better place in the
struct to not cause a hole.

> >  };
> > diff --git a/drivers/base/coco.c b/drivers/base/coco.c

Will fix.

Hanlon's razor v2, "never attribute to boldness..."

> > +#include <linux/device.h>
> > +#include <linux/dev_printk.h>

The distinction in my mind of merely Confidential and TEE acceptance, is
that a Trusted Execution Environment implies a larger attestation
infrastructure beyond just "are the bits on the wire protected by AES
XTS". A TEE has a launch state attestation for the TVM a vTPM or other
Runtime Measurement Scheme to have a relying party validate that changes
to the TVM do not violate expectations of the TEE, and in this case
"PCIe Device Acceptance" is one more event for the TEE to validate with
a relying party. The confidential device mechanism is just a property
that allows the TEE to maintain its confidentiality and data integrity
assumptions.

I will include a form of that commentary in v2 because it is an
important distinction.

[..]
> > +/**
> > + * device_cc_probe(): Coordinate dynamic acceptance with a device driver

It is ok to keep going because this is a warning that should only fire
on a kernel developer workstation when they have somehow messed up a
bus's probe implementation. It is more for documentation purposes like
lockdep_assert_held(). Maybe a lockdep_assert_remote_held() for this
work_on_cpu() case where the thread holding the lock is also in charge
of flushing work_on_cpu()?

Either way, this race fails safely. If the driver proceeds with falsely
believing the device is accepted the hardware will throw errors on MMIO
cycles, and fail to issue DMA. Failure in the other direction just means
the driver fall into deferred probing unnecessarily.

---

## [15] dan.j.williams@intel.com — 2025-08-28
*Subject: Re: [PATCH 6/7] samples/devsec: Introduce a "Device Security TSM"
 sample driver*

Jason Gunthorpe wrote:
> On Tue, Aug 26, 2025 at 08:52:58PM -0700, Dan Williams wrote:
> > +static int devsec_pci_probe(struct pci_dev *pdev,

tl;dr I will include an end-to-end flow document in Documentation in the
next posting.

> 
> device_cc_probe() doesn't save anything, doesn't this just get into an

Hmm, no, deferred probing retriggers after a one-time boot timeout
(extended by driver registration events) and after any device
successfully completes probe.

1/ TVM policy decides it is committed to operate $device in confidential
   mode.

2/ Enlightened driver learns about that policy "somehow" (I am open to
   this policy being conveyed via driver-core standard mechanism, but for
   now assume the driver learns the policy by driver specific means).

3/ Enlightened driver uses device_cc_probe() to exit its probe routine
   at a known point where the device's configuration is ready to be
   locked, or otherwise falls back to shared operation if confidential
   operation is not requested. This is different than standard device
   teardown path which may "unconfigure" the device and scuttle
   acceptance.

4/ Whenever TVM is ready to measure and accept the device it triggers
   manual bind. Meanwhile deferred probing has probably gone into "wait
   for userspace to manually kick this device" mode by this point.

Unenlightened drivers skip all of this and just assume that the device
arrives in a "ready-to-lock" configuration.

> How does userspace accept through the sysfs retrigger probing?

Yes.

> As we discussed in the prior chain we need to have a policy decision
> before auto-binding drivers at all in a CC environment, I don't see

The aim was for the "'struct device' has an acceptance flag" discussion
to settle before starting a "device-core policy for unaccepted devices"
discussion. I am ok to put more logs on the fire if there is an appetite
for that.

> How does the kernel/userspace tell the difference between drivers that
> want this early binding and those that don't?

I was hoping to put the onus of that on the vendors that think they need
this Enlightened driver path. The path of least resistance for device
vendors is design the hardware so that it can be locked without needing
a driver to take any configuration action ahead of time. Otherwise,
explain to users that they need to adjust/replace the eventual udev
sysfs script that does:

   lock
   accept
   bind

...instead needs to do:

   bind (defer)
   lock
   accept
   bind

Now, there is a debugfs method to learn the probe deferral reason, but
there is no requirement for debugfs to be mounted, and it turns out that
probe deferral reason is only updated if the device is autoprobed. If
the first time a driver sees a device is via explicit bind debugfs does
not convey the deferral reason.

> Can you write out the whole flow from a userspace perspective in one
> of the commit messages?

I will do that in v2.

> This also disables BME, we talked about that a lot, the commit
> messages didn't seem to describe what solution was settled on here?

Your proposal to put 100% of the onus of not clobbering the RUN state of
the device via configuration writes to standard registers on the VMM has
grown on me. Make VMM responsible for trapping and declining requests to
clear BME and MSE while the device is in LOCKED or RUN state.

Enlightened drivers could skip clearing BME + MSE when locked, but
unenlightened drivers should assume either the VMM traps the
configuration request or the TVM must re-lock re-accept when the VMM
fails to meet that requirement.

---

## [16] dan.j.williams@intel.com — 2025-08-28
*Subject: Re: [PATCH 2/7] PCI/TSM: Add pci_tsm_guest_req() for managing TDIs*

Alexey Kardashevskiy wrote:
> 
> 

Thanks, not sure why checkpatch spell check sometimes misses words.

> 
> > these are long running operations involving SPDM message passing via the

Oh, this was a copy paste mistake that I meant to cleanup after Yilun's
clarification [1]

[1]: http://lore.kernel.org/aCbglieuHI1BJDkz@yilunxu-OptiPlex-7050

So, the plan is *not* for KVM to have PCI device awareness.

> > + * to TDI information or state change requests. The scope parameter limits
> > + * requests to TDISP state management, or limited debug.

No, iommufd does not need to preallocate the response buffer, the
response buffer is allocated by the responder.

This follows the example fwctl because this guest_req() transport is in
the same class of kernel bypass tunnels. No need to reinvent a common
device RPC transport mechanism.

> > + *
> > + * Context: Caller is responsible for calling this within the pci_tsm_bind()

Because of the assignment used as truth value. The evaluation of the
ACQUIRE_ERR() result in the assignment was a compactness choice that
PeterZ made in his original proposal [2] that made sense to me, so I
carried it forward.

[2]: http://lore.kernel.org/20250509104028.GL4439@noisy.programming.kicks-ass.net

[..]
> > @@ -50,6 +51,9 @@ struct pci_tsm_ops {
> >   		struct pci_tdi *(*bind)(struct pci_dev *pdev,

Not immediately understanding what change you want here. Do you want
iommufd to track the pci_tdi?

> > +				   enum pci_tsm_req_scope scope, void *req_in,
> > +				   size_t in_len, size_t *out_len);

I don't know. Given this is to support any possible combination of TSM
and ABI I took inspiration from fwctl which is trying to solve a similar
common transport problem.

> And the userspace (which makes such request) will allocate some memory
> before calling such ioctl(), can "void *req_in" be "void __user

Keep interface innovation to minimum and follow an existing pattern.

[..]
> > +/**
> > + * enum pci_tsm_req_scope - Scope of guest requests to be validated by TSM

While the TSM is in the trust boundary of the TVM, the TSM and the TVM
are not necessarily trusted by the VMM. It has a responsibility to
maintain its own security model especially when marshaling opaque blobs
on behalf of a guest. This scope parameter serves the same purpose as it
does in fwctl to maintain a security model and explicitly control for
requests that are out of scope.

The enforcement is market and regulatory forces to make solutions are
not bypass security model expectations of the operating system.

---

## [17] dan.j.williams@intel.com — 2025-08-28
*Subject: Re: [PATCH 2/7] PCI/TSM: Add pci_tsm_guest_req() for managing TDIs*

Aneesh Kumar K.V wrote:
> Dan Williams <dan.j.williams@intel.com> writes:
> 

Are you confusing this new "enum pci_tsm_req_scope" proposal with the
previous "struct pci_tsm_guest_req_info" proposal.

> 
> For example, on ARM, I’ve implemented a simpler approach [1] by using an

So both of those are both PCI_TSM_REQ_INFO scope.

The observation is that Linux already has an opaque blob passing
mechanism wrapped by a security model, fwctl. The proposal is just
reuse those mechanics, skip a wrapper struct for the arguments, and let
the low level handler be responsible for response buffer allocation.

---

## [18] Alexey Kardashevskiy — 2025-08-29
*Subject: Re: [PATCH 2/7] PCI/TSM: Add pci_tsm_guest_req() for managing TDIs*

On 29/8/25 08:07, dan.j.williams@intel.com wrote:
> Alexey Kardashevskiy wrote:
>>

ok, time to read about fwctl.

>>> + *
>>> + * Context: Caller is responsible for calling this within the pci_tsm_bind()

Ah -Werror=parentheses.

> ACQUIRE_ERR() result in the assignment was a compactness choice that
> PeterZ made in his original proposal [2] that made sense to me, so I

oookay :(

> 
> [2]: http://lore.kernel.org/20250509104028.GL4439@noisy.programming.kicks-ass.net

I'd like to either:

- get rid of pdev back refs in pci_tsm/pci_tdi since we pass pci_dev everywhere as if a pdev from pci_tsm/pci_tdi is used in, say, 1-2 places, then it is just cleaner to pass pdev to those places explicitly

oooor

- pass pci_tsm/pci_tdi to pci_tsm_ops hooks and use pdev in those when needed, this way it is clearer from the hook prototype what it operates on.



>>> +				   enum pci_tsm_req_scope scope, void *req_in,
>>> +				   size_t in_len, size_t *out_len);

If guest_req() returns NULL - what is it - error (no response) or success ("request successfully accepted, no response needed")? The PSP returns fw_err (which I pass in my guest_request hook), does this interface suggest that my TSM dev should allocate a sizeof(fw_err) buffer at least, and if there is more - then sizeof(fw_err)+sizeof(response)? I thought TDX does return an error code too, surprised to see it missing here.


>> And the userspace (which makes such request) will allocate some memory
>> before calling such ioctl(), can "void *req_in" be "void __user

I get the idea, it just sounds like it should be a mask - READ|WRITE|TDISP_STATE|DEBUG. Which category would MMIO_VALIDATE fall (set "validated" in RMP)? Thanks,

---

## [19] Jason Gunthorpe — 2025-08-29
*Subject: Re: [PATCH 6/7] samples/devsec: Introduce a "Device Security TSM"
 sample driver*

On Thu, Aug 28, 2025 at 02:38:14PM -0700, dan.j.williams@intel.com wrote:
> > device_cc_probe() doesn't save anything, doesn't this just get into an
> > endless loop of EPROBE_DEFER? Usually the kernel will retry these

So it is not "endless" but it is also not "single probe then wait till
accept". I'm not keen on using this mechanism, I think the things
people want to do in the T=0 mode are going to be time consuming and
repeatedly doing that time consuming step is not a good idea.

How about this instead:

1) Drivers compiled into the kernel are "safe" and can freely bind
   at will during early boot

2) The first thing the initrd does is set
   /sys/bus/*/drivers_autoprobe to false.
   This stops all kernel driver autobinding.

   Maybe we also need a small kernel change to allow userspace to make
   drivers_autoprobe false for all future busses too.

3) Userspace then evaluates what devices are present, checks its
   policy, loads modules and issues /sys/.../bind operations.

   We need to close the general security gap I gave earlier, userspace
   policy should be able to implement the statement:

     mlx5 is allowed to bind to a RUN device after measuring and
     verifying it, and never otherwise.

   a) For non-TDISP devices userspace checks if a driver is "trusted"
      before binding it, a fancier CC only deny list stored in the
      initrd.
   b) For TDISP devices userspace runs through the
      prepare/measure/lock/run sequence then binds the final
      driver.
   c) Something something RAS driver restart

   Basically userspace policy is entirely in control if a device is
   "accepted" by the ccVM or not. The kernel won't auto bind
   a driver to a physical device. It would be driven off of
   uevents, I guess through new CC focused features in udev.

   I think the needed kernel support is already here, the main gap I
   see is that the modules.alias does not include the driver names, it
   just has the module names. We ran into this with vfio (see below)
   so it would be nice to fix, though it can be worked around like
   VFIO did by making the driver name == module name.

4) Userspace sequences the special "prepare" pre-T=0 drivers, perhaps
   discovered through modinfo matching similar to VFIO:

   $ grep vfio /lib/modules/`uname -r`/modules.alias
   alias vfio_pci:v000015B3d0000101Esv*sd*bc*sc*i* mlx5_vfio_pci
         ^^^^^^
   PCI driver but special for VFIO usage. So I imagine a
   ccprepare_pci:... driver variation.

   Userspace can inspect the modules.alias, find if the device's
   modalias has a ccprepare_pci: match and if so it will bind/unbind
   that driver before going to locked/run. When it reaches run it will
   find the pci: match and bind that driver which is the operating
   driver.

   Policy if the ccprepare device should even be permitted is also
   controlled by userspace.

   Userspace sequences all of this based on its policy to accept a
   device and push it to RUN, not the kernel, again probably
   through some new CC features in udev.

   The kernel side of this is a commit like cc6711b0bf36 ("PCI / VFIO:
   Add 'override_only' support for VFIO PCI sub system")

This is much less kernel change and gives the big thing CC needs -
driver binding policy decisions in userspace.

> > As we discussed in the prior chain we need to have a policy decision
> > before auto-binding drivers at all in a CC environment, I don't see

Sure, I think you shold drop this patch from this series and have this
series focus only on creating an accepted struct device environment
that a driver can bind to and operate. This is a long journey already,
once this basic support is landed we still need to do all the arch
support to enable DMA/IOMMU/etc as many followup series.

The questions about when and what drivers are probed can be left to a
different series, at this point it will be usable for development but
not secure like it should be.

The device_cc_probe() type issue should be solved in yet another
series, IMHO, and that should come with a really strong justification
why the kernel needs to do anything at all, vs just rely on userspace
as I outline above.

> I was hoping to put the onus of that on the vendors that think they need
> this Enlightened driver path. The path of least resistance for device

So if we already imagine changing udev, lets imagine the above
instead?

> > This also disables BME, we talked about that a lot, the commit
> > messages didn't seem to describe what solution was settled on here?

OK, worth explaining :)

Jason

---

## [20] dan.j.williams@intel.com — 2025-08-29
*Subject: Re: [PATCH 6/7] samples/devsec: Introduce a "Device Security TSM"
 sample driver*

Jason Gunthorpe wrote:
> On Thu, Aug 28, 2025 at 02:38:14PM -0700, dan.j.williams@intel.com wrote:
> > > device_cc_probe() doesn't save anything, doesn't this just get into an

It would only ever run multiple times if the driver is built-in or
loaded early, which is also mitigated by disabling autoprobe like you
have below. So that problem is manageable.

Now, I do think it is worth exploring a convention for "cc_prepare"
drivers, but as long as userspace is prepared to rebind post accept it
does not really matter if it got to that point by cc_prepare driver,
probe deferral of enlightened driver, or plain probe error plus retry.

> How about this instead:
> 

Agree.

In the past this idea has been met with "but but typical distro kernels
have lots of built-in drivers that *may* be unsafe", and the answer is
"yes, a VM image with a CC aware / specific kernel config is a
requirement".

> 2) The first thing the initrd does is set
>    /sys/bus/*/drivers_autoprobe to false.

Makes sense for the buses userspace is prepared to manage.

>    Maybe we also need a small kernel change to allow userspace to make
>    drivers_autoprobe false for all future busses too.

I do think we need a mechanism to say, "no more dynamic device
enumeration", but a coarse and future promise "no autoprobe of any bus"
I fear is going to have a long tail of problems especially with design
patterns like "faux_device" and "auxiliary_device".

As far as I understand, these CC environments do not immediately have
secrets to protect at launch. Also, not sure how many are ready to
validate the launch state of the TVM that early. I think it is more a
case of allow everything by default to start (whatever is in ACPI, and
T=0 PCI devices). Later the relying party either says "no, you have
enumerated devices that should not be there", or "yes, launch state
looks good, lock device topology, proceed with the performance
enhancement of converting some PCI TDISP devices to T=1 operation, here
are your secrets".

That post validate model saves us from a long tail of fixes for
subsystems that may be surprised by a new userspace acceptance loop. It
is userspace responsibility to validate device topology relative to
relying party expectations, and likely for the device topology to be
static for the duration of secrets deployment.

> 3) Userspace then evaluates what devices are present, checks its
>    policy, loads modules and issues /sys/.../bind operations.

The gap is present when secrets are deployed and if secrets are deployed
pre-accept the TCB is already broken.

>      mlx5 is allowed to bind to a RUN device after measuring and
>      verifying it, and never otherwise.

...and if userspace binds mlx5 pre-RUN that is not the kernel's problem.
I state that explicitly not for you, but because of the rejection of the
"device filter" in-kernel mechanism previously.

>    a) For non-TDISP devices userspace checks if a driver is "trusted"
>       before binding it, a fancier CC only deny list stored in the

Yes, necessary.

>    b) For TDISP devices userspace runs through the
>       prepare/measure/lock/run sequence then binds the final

Yes, the only quibble is whether that "kernel won't bind" is more a
"userspace shall lock and validate device topology" at a certain point
in the boot flow. Userspace may need to be prepared for some unaccepted
devices to bind before that point.

>    I think the needed kernel support is already here, the main gap I
>    see is that the modules.alias does not include the driver names, it

Yes, I think that is reasonable. Multi-driver modules are not the norm.

The kernel problems to solve are "accepted" flag and maybe documenting
to driver writers / udev developers strategies to handle the "prepare"
problem.

> 4) Userspace sequences the special "prepare" pre-T=0 drivers, perhaps
>    discovered through modinfo matching similar to VFIO:

Novel!

>    Userspace can inspect the modules.alias, find if the device's
>    modalias has a ccprepare_pci: match and if so it will bind/unbind

Yeah, that looks like a viable option for these complicated drivers.

For RAS I do still like the property of a driver that will field errors
also having everything it needs to take a device from reset back to the
ready-to-accept state. That can be solved later, and maybe the outcome 
is "cc_prepare" is incompatible with "recovery".

> This is much less kernel change and gives the big thing CC needs -
> driver binding policy decisions in userspace.

You mean drop the device_cc_probe() piece. The rest of patch is starting
the work of a "accepted struct device environment" with a single flag
that MMIO and DMA infrastructure can reference.

> This is a long journey already, once this basic support is landed we
> still need to do all the arch support to enable DMA/IOMMU/etc as many

Agree. Especially because attestation interfaces are not part of this
series yet.

> The device_cc_probe() type issue should be solved in yet another
> series, IMHO, and that should come with a really strong justification

It is trivial for a driver to open code EPROBE_DEFER so
device_cc_probe() is not putting any burden on the kernel besides
documentation, but I will drop it for now.

> > I was hoping to put the onus of that on the vendors that think they need
> > this Enlightened driver path. The path of least resistance for device

That's the whole discussion, what are the udev requirements relative to
the secrets deployment event.

---

## [21] Jason Gunthorpe — 2025-08-29
*Subject: Re: [PATCH 6/7] samples/devsec: Introduce a "Device Security TSM"
 sample driver*

On Fri, Aug 29, 2025 at 01:00:09PM -0700, dan.j.williams@intel.com wrote:
> Jason Gunthorpe wrote:
> > On Thu, Aug 28, 2025 at 02:38:14PM -0700, dan.j.williams@intel.com wrote:

There can be many tdisp devices loading after boot so it could be many
times while all the booting happens. I'm imagining around 8-15 TDISP
devices as what we may see in some real systems.

> In the past this idea has been met with "but but typical distro kernels
> have lots of built-in drivers that *may* be unsafe", and the answer is

Yeah, possibly that is where this is going. Or at least someone on the
distro side is well teed up to propose some kind of pre-initrd
mechanism to mitigate this down the road and get back to single kernel
build.

> >    Maybe we also need a small kernel change to allow userspace to make
> >    drivers_autoprobe false for all future busses too.

For the moment I would probably just have userspace special case
those and automatically run the userspace probing sequence.

> As far as I understand, these CC environments do not immediately have
> secrets to protect at launch. Also, not sure how many are ready to

It is not about secrets, it is about protecting the integrity of the
kernel - the software you intend to load secrets into. mlx5 is a 300k
LOC driver. I fully believe that an attacker prentending to be the
device can attack the driver and insert hostile code into the kernel
using this driver.

As such an attack would escape measurement it is completely
invisible. The only prevntion is to control what parts of the kernel
the VMM side can reach to attack by denying driver binding.

If the kernel now running hostile code gets secrets released the
hostile kernel code can ex-filtrate them back to the VMM.

It is the same argument we see MS making about secure boot, you have
to take steps to ensure that unmeasured code is never injected into
the system before you complete the boot and release the secrets.

From this view point any compromise that allows unmeasured code into
the boot chain is a security issue.

The same argument is made for T=1 devices.. I imagine an attack where
the VM accepts a T=1 device, and it instantly DMAs all over the kernel
and effectively makes itself invisible to the verifier. Hopefully this
is prevented by measurements made by the TSM, but IDK, seems scary.

However, I know there are alternative views. For instance that CC VM
users should just trust the CSP, trust their boot flow, trust their
provided VM kernels, trust their verfiers, and if you are already
agreeing to that trust then defending against a hostile VMM is silly.

IMHO I don't know where the industry will end up, I see people on both
sides of this debate pushing for their perspective. I'd like the
kernel to be happy with a userspace that wants to trust the VMM and a
userspace that is untrusting and very paranoid.

> I think it is more a case of allow everything by default to start
> (whatever is in ACPI, and T=0 PCI devices). Later the relying party

This is really the above "we trust the VMM" sort of view point, and
from a kernel perspective I think it is fine so long as userspace is
the one making the decision to work like that. I don't want to see the
kernel force the weakest security option onto the userspace.

IMHO the minimal issue here is what should the kernel do with a T=0
device that has TDISP capability..

We don't really want the kernel to autobind a driver in T=0 mode, that
is wasteful if we are going to unbind it, lock/run and then bind it
again.

So, IMHO, the bare minimum would be for the kernel to disable auto
binding for TDISP capable devices only and shoot out a udev event
signaling that userspace has to bind the device instead.

Let udev take it from there, and udev can then do whatever dance we
define.

Then we can have everything from a minimal security posture to a very
tight drivers_autoprobe situation, based on what userspace wants to
do.

> >      mlx5 is allowed to bind to a RUN device after measuring and
> >      verifying it, and never otherwise.

Right. I am stating the system level goal, expecting that userspace is
in control and conforming to it. The kernel just has to not bypass the
policy choices userspace is making.

> >    Basically userspace policy is entirely in control if a device is
> >    "accepted" by the ccVM or not. The kernel won't auto bind

My argument is "lock and validate" is a fine option, but kernel should
be designed to allow the more secure option of "approve every single
driver bind". Userspace can pick, but kernel should be desigend to do
both.

> The kernel problems to solve are "accepted" flag and maybe documenting
> to driver writers / udev developers strategies to handle the "prepare"

Yes, and maybe some small less-critical kernel items:

 - modules.alias includes the driver name
 - A way to default off drivers_autoprobe
 - A way for userspace to tell which busses are discovered from
   HW vs internal to the kernel (aux, fuax)
 - ccprepare_ drivers
 - A way to restrict built in drivers at initrd creation time

But I think each of these topics can be its own independent thing, and
I would send them along side RFC patches for udev if that is how
things are going to go.

> For RAS I do still like the property of a driver that will field errors
> also having everything it needs to take a device from reset back to the

Yeah, probably.

> > Sure, I think you shold drop this patch from this series and have this
> > series focus only on creating an accepted struct device environment

Yes, sorry, I forgot which patch this was: :)
 
> It is trivial for a driver to open code EPROBE_DEFER so
> device_cc_probe() is not putting any burden on the kernel besides

Sort of, it also establishes a kind of uAPI that I think is best
avoided until things are a bit more mature..

Jason

---

## [22] dan.j.williams@intel.com — 2025-08-29
*Subject: Re: [PATCH 2/7] PCI/TSM: Add pci_tsm_guest_req() for managing TDIs*

Alexey Kardashevskiy wrote:
[..]
> >> We have pdev in pci_tdi, pci_tsm and pci_tsm_pf0 (via .base), using
> >> these in pci_tsm_ops will document better which call is allowed on

Maybe if we see that that are unused then they are easy to delete later.

> oooor
> 

I think all of the operations need the pdev + extra data so it is always
operating on the pdev to some extent. I think this is another, get
"Aneesh and Yilun onboard" case.

> >> Out of curiosity (probably could go to the commit log) - for what kind
> >> of request and on which platform we do not know the response size in

As we talked about on the CCC call it sounds like at least TDX also
wants to pass an explicit FW response code separate from the response
buffer, so I will fix this up to not follow fwctl.

[..]
> >> What is going to enforce this and how? It is a guest request, ideally
> >> encrypted, and the host does not really have to know the nature of the

Curious why is MMIO_VALIDATE separate from other Guest Physical Address
validation? I think if it needs to be separate from other GPA validation
then it would be in the PCI_TSM_REQ_STATE_CHANGE scope as it is just
another expected step in the LOCKED->RUN transition.

---

## [23] Alexey Kardashevskiy — 2025-09-02
*Subject: Re: [PATCH 2/7] PCI/TSM: Add pci_tsm_guest_req() for managing TDIs*

On 30/8/25 12:37, dan.j.williams@intel.com wrote:
> Alexey Kardashevskiy wrote:
> [..]

It is way easier to do now than later when it grows. I'll dig a bit.


>> oooor
>>

For normal memory there is a guest "pvalidate" instruction to set the valid bit in the RMP. For MMIO, there is another bit in RMP which says "pvalidate" will fail on such entry, instead the PSP needs to set it (which is pretty much memcpy for it) as the guest needs assurance from the PSP that the RMP still maps the right thing. Thanks,

---

## [24] Alexey Kardashevskiy — 2025-09-02
*Subject: Re: [PATCH 1/7] PCI/TSM: Add pci_tsm_{bind,unbind}() methods for
 instantiating TDIs*

On 27/8/25 13:52, Dan Williams wrote:


I suggest changing "pci_tsm_{bind,unbind}()" to "pci_tsm_bind/pci_tsm_unbind" or "pci_tsm_bind/_unbind" as otherwise cannot grep for pci_tsm_bind in git log.


> After a PCIe device has established a secure link and session between a TEE
> Security Manager (TSM) and its local Device Security Manager (DSM), the



> Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
> Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>

What is expected to be passed to __pci_tsm_unbind/pci_tsm_bind as pdev - PF0 or TEE-IO VF? I guess the latter.

But to_pci_tsm_pf0() casts the pdev's tsm to pci_tsm_pf0 which makes sense for PF0 but not for VFs.

What do I miss and how does this work for you? Thanks,


> +	guard(mutex)(&tsm_pf0->lock);
> +

---

## [25] Aneesh Kumar K.V — 2025-09-02
*Subject: Re: [PATCH 1/7] PCI/TSM: Add pci_tsm_{bind,unbind}() methods for
 instantiating TDIs*

Alexey Kardashevskiy <aik@amd.com> writes:

> On 27/8/25 13:52, Dan Williams wrote:
>

I guess this needs

modified   drivers/pci/tsm.c
@@ -44,7 +44,7 @@ static inline bool has_tee(struct pci_dev *pdev)
 /* 'struct pci_tsm_pf0' wraps 'struct pci_tsm' when ->dsm == ->pdev (self) */
 static struct pci_tsm_pf0 *to_pci_tsm_pf0(struct pci_tsm *pci_tsm)
 {
-	struct pci_dev *pdev = pci_tsm->pdev;
+	struct pci_dev *pdev = pci_tsm->dsm;
 
 	if (!is_pci_tsm_pf0(pdev) || !is_dsm(pdev)) {
 		dev_WARN_ONCE(&pdev->dev, 1, "invalid context object\n");

-aneesh

---

## [26] Aneesh Kumar K.V — 2025-09-02
*Subject: Re: [PATCH 1/7] PCI/TSM: Add pci_tsm_{bind,unbind}() methods for
 instantiating TDIs*

Dan Williams <dan.j.williams@intel.com> writes:

> After a PCIe device has established a secure link and session between a TEE
> Security Manager (TSM) and its local Device Security Manager (DSM), the

Can we add tsm_bind/unbind so that we can call tsm function from iommufd instead of
pci specific functions like pci_tsm_bind()?

modified   drivers/virt/coco/tsm-core.c
@@ -193,6 +193,24 @@ void tsm_ide_stream_unregister(struct pci_ide *ide)
 }
 EXPORT_SYMBOL_GPL(tsm_ide_stream_unregister);
 
+int tsm_bind(struct device *dev, struct kvm *kvm, u64 tdi_id)
+{
+	if (!dev_is_pci(dev))
+		return -EINVAL;
+
+	return pci_tsm_bind(to_pci_dev(dev), kvm, tdi_id);
+}
+EXPORT_SYMBOL_GPL(tsm_bind);
+
+int tsm_unbind(struct device *dev)
+{
+	if (!dev_is_pci(dev))
+		return -EINVAL;
+
+	return pci_tsm_unbind(to_pci_dev(dev));
+}
+EXPORT_SYMBOL_GPL(tsm_unbind);
+
 static void tsm_release(struct device *dev)
 {
 	struct tsm_dev *tsm_dev = container_of(dev, typeof(*tsm_dev), dev);
modified   include/linux/tsm.h
@@ -118,6 +118,9 @@ const char *tsm_name(const struct tsm_dev *tsm_dev);
 struct tsm_dev *find_tsm_dev(int id);
 const struct pci_tsm_ops *tsm_pci_ops(const struct tsm_dev *tsm_dev);
 struct pci_ide;
+struct kvm;
 int tsm_ide_stream_register(struct pci_ide *ide);
 void tsm_ide_stream_unregister(struct pci_ide *ide);
+int tsm_bind(struct device *dev, struct kvm *kvm, u64 tdi_id);
+int tsm_unbind(struct device *dev);
 #endif /* __TSM_H */

---

## [27] Aneesh Kumar K.V — 2025-09-03
*Subject: Re: [PATCH 1/7] PCI/TSM: Add pci_tsm_{bind,unbind}() methods for
 instantiating TDIs*

Dan Williams <dan.j.williams@intel.com> writes:
...

> +/**
> + * pci_tsm_bind() - Bind @pdev as a TDI for @kvm

Are we missing assigning pdev and kvm in the above function? 

modified   drivers/pci/tsm.c
@@ -356,6 +356,8 @@ int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u32 tdi_id)
 	if (IS_ERR(tdi))
 		return PTR_ERR(tdi);
 
+	tdi->pdev = pdev;
+	tdi->kvm = kvm;
 	pdev->tsm->tdi = tdi;
 
 	return 0;

-aneesh

---

## [28] Aneesh Kumar K.V — 2025-09-03
*Subject: Re: [PATCH 5/7] PCI/TSM: Add Device Security (TVM Guest) operations
 support*

Dan Williams <dan.j.williams@intel.com> writes:


....

> +
> +static int pci_tsm_lock(struct pci_dev *pdev, struct tsm_dev *tsm_dev)

This is slightly different from connect() callback in that we don't have
pdev->tsm initialized when calling ->lock() callback. Should we do
something like below? (I also included the arch changes to show how
destructor is being used.)

modified   drivers/pci/tsm.c
@@ -917,11 +917,19 @@ int pci_tsm_devsec_constructor(struct pci_dev *pdev, struct pci_tsm_devsec *tsm,
 	pci_tsm->tdi = NULL;
 	pci_tsm->pdev = pdev;
 	pci_tsm->ops = ops;
+	pdev->tsm = pci_tsm;
 
 	return 0;
 }
 EXPORT_SYMBOL_GPL(pci_tsm_devsec_constructor);
 
+int pci_tsm_devsec_destructor(struct pci_dev *pdev)
+{
+	pdev->tsm = NULL;
+	return 0;
+}
+EXPORT_SYMBOL_GPL(pci_tsm_devsec_destructor);
+
 /**
  * pci_tsm_pf0_constructor() - common 'struct pci_tsm_pf0' (DSM) initialization
  * @pdev: Physical Function 0 PCI device (as indicated by is_pci_tsm_pf0())
modified   drivers/virt/coco/arm-cca-guest/arm-cca.c
@@ -217,13 +217,17 @@ static struct pci_tsm *cca_tsm_lock(struct pci_dev *pdev)
 		return ERR_PTR(ret);
 
 	ret = rhi_da_vdev_set_tdi_state(vdev_id, RHI_DA_TDI_CONFIG_LOCKED);
-	if (ret)
+	if (ret) {
+		pci_tsm_devsec_destructor(pdev);
 		return ERR_PTR(-EIO);
+	}
 
 	/* This will be done by above rhi in later spec */
 	ret = rsi_device_lock(pdev);
-	if (ret)
+	if (ret) {
+		pci_tsm_devsec_destructor(pdev);
 		return ERR_PTR(-EIO);
+	}
 
 	return &no_free_ptr(cca_dsc)->pci.base;
 }
@@ -245,6 +249,7 @@ static void cca_tsm_unlock(struct pci_dev *pdev)
 		return;
 	}
 
+	pci_tsm_devsec_destructor(pdev);
 	kfree(cca_dsc);
 }
 
modified   include/linux/pci-tsm.h
@@ -220,6 +220,7 @@ int pci_tsm_pf0_constructor(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm,
 			    const struct pci_tsm_ops *ops);
 int pci_tsm_devsec_constructor(struct pci_dev *pdev, struct pci_tsm_devsec *tsm,
 			       const struct pci_tsm_ops *ops);
+int pci_tsm_devsec_destructor(struct pci_dev *pdev);
 void pci_tsm_pf0_destructor(struct pci_tsm_pf0 *tsm);
 int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u32 tdi_id);
 void pci_tsm_unbind(struct pci_dev *pdev);



-aneesh

---

## [29] Alexey Kardashevskiy — 2025-09-04
*Subject: Re: [PATCH 1/7] PCI/TSM: Add pci_tsm_{bind,unbind}() methods for
 instantiating TDIs*

On 4/9/25 01:17, Aneesh Kumar K.V wrote:
> Dan Williams <dan.j.williams@intel.com> writes:
> ...

This signals that this pdev backref is not exactly needed :)

> +	tdi->kvm = kvm;


iommufd_vdevice holds the reference and AMD TSM only needs kvm* during bind() so it can go unnoticed but it is needed, yeah. Thanks,


>   	pdev->tsm->tdi = tdi;
>

---

## [30] Aneesh Kumar K.V — 2025-09-04
*Subject: Re: [PATCH 1/7] PCI/TSM: Add pci_tsm_{bind,unbind}() methods for
 instantiating TDIs*

Alexey Kardashevskiy <aik@amd.com> writes:

> On 4/9/25 01:17, Aneesh Kumar K.V wrote:
>> Dan Williams <dan.j.williams@intel.com> writes:

I need that in cca_tsm_unbind

static void cca_tsm_unbind(struct pci_tdi *tdi)
{
	struct realm *realm = &tdi->kvm->arch.realm;

	rme_unbind_vdev(realm, tdi->pdev, tdi->pdev->tsm->dsm);
	module_put(THIS_MODULE);
}


-aneesh

---

## [31] Aneesh Kumar K.V — 2025-09-04
*Subject: Re: [PATCH 5/7] PCI/TSM: Add Device Security (TVM Guest) operations
 support*

Dan Williams <dan.j.williams@intel.com> writes:

> PCIe Trusted Execution Environment Device Interface Security Protocol
> (TDISP) has two distinct sets of operations. The first, currently enabled

Not all resources are secure/encrypted. For example, if secure
interrupts are not supported, then the MSI-X table and PBA BARs remain
shared resources between the guest and the hypervisor.

In ARM CCA, the interface report is used to determine the nature of each
region. When ioremap() is called, it relies on the Realm IPA state of
the guest physical address to decide whether the mapping should be
treated as shared or private [1], [2].

With this change we report the msix table and pba range as encrypted in
/proc/iomem

 50012000-50012fff : PCI MMIO Encrypted
    50012000-50012fff : 0000:00:01.0
      50012000-50012fff : ahci
  50013000-50013fff : PCI MMIO Encrypted
    50013000-50013fff : 0000:00:01.0
      50013000-50013fff : ahci


[1] https://lore.kernel.org/all/20240830130150.8568-6-will@kernel.org
[2] https://lore.kernel.org/all/20240819131924.372366-12-steven.price@arm.com

> +		if (insert_resource(&iomem_resource, __res[i]) != 0) {
> +			kfree(__res[i]);

---

## [32] Alexey Kardashevskiy — 2025-09-05
*Subject: Re: [PATCH 1/7] PCI/TSM: Add pci_tsm_{bind,unbind}() methods for
 instantiating TDIs*

On 4/9/25 22:56, Aneesh Kumar K.V wrote:
> Alexey Kardashevskiy <aik@amd.com> writes:
> 

This does not really explain anything.

My unbind() needs DBDFn of the rootport to unfence IOMMU - easy to cache in the TDI's platform data; and resources to RMPUPDATE those back to shared - but this new device_cc stuff does this already (I am not using it yet though). And SPDM buffers but these in the PF0 platform data so that backref I do need but pci_dev is just too wide. Not much really.

> 	module_put(THIS_MODULE);

Why is that needed btw? Thanks,

> }
>

---

## [33] Alexey Kardashevskiy — 2025-09-08
*Subject: Re: [PATCH 2/7] PCI/TSM: Add pci_tsm_guest_req() for managing TDIs*

On 2/9/25 09:49, Alexey Kardashevskiy wrote:
> 
> 

So far it appears so that the only use for these backrefs is pci_tsm_ops's hooks which take pci_tsm/pci_tdi instead of pci_dev. So the backrefs are only needed because unbind()/remove() do not take pci_dev.

My problem with these backrefs is that for a new reader of the code  it won't be immediately obvious whether we need pci_dev_get/pci_dev_put for those, are pci_tsm/pci_tdi ever detached from pci_dev, etc. Dunno, I won't be nak-ing of this though. Thanks,

---

## [34] dan.j.williams@intel.com — 2025-09-09
*Subject: Re: [PATCH 1/7] PCI/TSM: Add pci_tsm_{bind,unbind}() methods for
 instantiating TDIs*

Alexey Kardashevskiy wrote:
> 
> 

Easy enough, and will change, but FWIW:

$ git log --grep pci_tsm_bind
commit a8c148ed753d640b5e5f8d1043d9f9d6188436b4 (HEAD -> for-6.18/devsec)
Author: Dan Williams <dan.j.williams@intel.com>
Date:   Mon Aug 18 13:59:26 2025 -0700

    PCI/TSM: Add pci_tsm_{bind,unbind}() methods for instantiating TDIs

...due to pci_tsm_bind() in the changelog.

[..]
> > diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
> > index 092e81c5208c..302a974f3632 100644

Yes, the latter.

> But to_pci_tsm_pf0() casts the pdev's tsm to pci_tsm_pf0 which makes sense for PF0 but not for VFs.

Yes, that it is a bug. Incremental fixup I will push in v6 below.

> What do I miss and how does this work for you? Thanks,

It works if only testing direct-device assignment of PF0.

-- 8< --
diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index 4688ddbc0b33..59458e894251 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -36,16 +36,16 @@ static inline bool is_dsm(struct pci_dev *pdev)
 }
 
 /* 'struct pci_tsm_pf0' wraps 'struct pci_tsm' when ->dsm_dev == ->pdev (self) */
-static struct pci_tsm_pf0 *to_pci_tsm_pf0(struct pci_tsm *pci_tsm)
+static struct pci_tsm_pf0 *to_pci_tsm_pf0(struct pci_tsm *tsm)
 {
-	struct pci_dev *pdev = pci_tsm->pdev;
+	struct pci_dev *pdev = tsm->dsm_dev;
 
 	if (!is_pci_tsm_pf0(pdev) || !is_dsm(pdev)) {
-		dev_WARN_ONCE(&pdev->dev, 1, "invalid context object\n");
+		pci_WARN_ONCE(tsm->pdev, 1, "invalid context object\n");
 		return NULL;
 	}
 
-	return container_of(pci_tsm, struct pci_tsm_pf0, base_tsm);
+	return container_of(tsm, struct pci_tsm_pf0, base_tsm);
 }
 
 static void tsm_remove(struct pci_tsm *tsm)
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index 61c947ff8735..d26d6e128d83 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -121,6 +121,9 @@ struct pci_tsm_pf0 {
 /* physical function0 and capable of 'connect' */
 static inline bool is_pci_tsm_pf0(struct pci_dev *pdev)
 {
+	if (!pdev)
+		return false;
+
 	if (!pci_is_pcie(pdev))
 		return false;

---

## [35] dan.j.williams@intel.com — 2025-09-09
*Subject: Re: [PATCH 1/7] PCI/TSM: Add pci_tsm_{bind,unbind}() methods for
 instantiating TDIs*

Aneesh Kumar K.V wrote:
> Alexey Kardashevskiy <aik@amd.com> writes:
> 

Yup, guess I should have read one more message in the thread before
taking the time go off and finish off v6.

---

## [36] dan.j.williams@intel.com — 2025-09-09
*Subject: Re: [PATCH 1/7] PCI/TSM: Add pci_tsm_{bind,unbind}() methods for
 instantiating TDIs*

Aneesh Kumar K.V wrote:
[..]
> Can we add tsm_bind/unbind so that we can call tsm function from iommufd instead of
> pci specific functions like pci_tsm_bind()?

I do not immediately understand the value of this. dev_is_pci() and
to_pci_dev() are already EXPORT_SYMBOL functionality. Why do they need
to be wrapped in a new EXPORT_SYMBOL_GPL wrapper that validates the
device is PCI?

If this is really needed it can do in the follow-on patch that adds the
iommufd hookup.

---

## [37] dan.j.williams@intel.com — 2025-09-09
*Subject: Re: [PATCH 1/7] PCI/TSM: Add pci_tsm_{bind,unbind}() methods for
 instantiating TDIs*

Aneesh Kumar K.V wrote:
> Dan Williams <dan.j.williams@intel.com> writes:
> ...

Indeed, but I think I will keep this as the same "constructor" pattern
so it is the TSM driver's job to make sure 'struct pci_tdi' is fully
initialized when ->bind() returns.

This is one of the oversights of not having a ->bind() flow yet in
samples/devsec/.

-- 8< --
diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index 4688ddbc0b33..125c682d2e08 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -519,6 +519,20 @@ static struct pci_dev *find_dsm_dev(struct pci_dev *pdev)
 	return NULL;
 }
 
+/**
+ * pci_tsm_tdi_constructor() - base 'struct pci_tdi' initialization for link TSMs
+ * @pdev: The PCI device
+ * @tsm: context to initialize
+ * @ops: PCI link operations provided by the TSM
+ */
+void pci_tsm_tdi_constructor(struct pci_dev *pdev, struct pci_tdi *tdi,
+			     struct kvm *kvm)
+{
+	tdi->pdev = pdev;
+	tdi->kvm = kvm;
+}
+EXPORT_SYMBOL_GPL(pci_tsm_tdi_constructor);
+
 /**
  * pci_tsm_link_constructor() - base 'struct pci_tsm' initialization for link TSMs
  * @pdev: The PCI device
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index 61c947ff8735..7eae8a1a2853 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -161,6 +161,8 @@ int pci_tsm_doe_transfer(struct pci_dev *pdev, u8 type, const void *req,
 			 size_t req_sz, void *resp, size_t resp_sz);
 int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u32 tdi_id);
 void pci_tsm_unbind(struct pci_dev *pdev);
+void pci_tsm_tdi_constructor(struct pci_dev *pdev, struct pci_tdi *tdi,
+			     struct kvm *kvm);
 #else
 static inline int pci_tsm_register(struct tsm_dev *tsm_dev)
 {

---

## [38] dan.j.williams@intel.com — 2025-09-09
*Subject: Re: [PATCH 5/7] PCI/TSM: Add Device Security (TVM Guest) operations
 support*

Aneesh Kumar K.V wrote:
> Dan Williams <dan.j.williams@intel.com> writes:
> 

Do you need to walk pdev->tsm when you are creating the tsm context?

For example, pass @pdev and the lock context structure to
rsi_device_lock()?

---

## [39] dan.j.williams@intel.com — 2025-09-09
*Subject: Re: [PATCH 5/7] PCI/TSM: Add Device Security (TVM Guest) operations
 support*

Aneesh Kumar K.V wrote:
> Dan Williams <dan.j.williams@intel.com> writes:
> 
[..]
> > @@ -453,6 +477,265 @@ static ssize_t disconnect_store(struct device *dev,
> >  }

I failed to mention this in the changelog, but part of thinking here is
that the mixed security state of a device based on interface report I
was expecting to be follow-on work. I.e. that minimum viable base case
is all MMIO is private of a private PCI device.

However, we can still keep the PCI/TSM core implementation equally
simple by moving these iomem manipulation routines to library helpers
that a TSM driver can optionally call as part of ->accept().

> In ARM CCA, the interface report is used to determine the nature of each
> region. When ioremap() is called, it relies on the Realm IPA state of

Unless these interface reports from different archs are all coming back
in a common format that can be parsed I do think it is a good idea to
reflect private MMIO in /proc/iomem regardless of how the arch
communicates to ioremap() to apply the private mapping pgprot setting.

In the meantime I will move these to optional library calls.

---

## [40] dan.j.williams@intel.com — 2025-09-09
*Subject: Re: [PATCH 2/7] PCI/TSM: Add pci_tsm_guest_req() for managing TDIs*

Alexey Kardashevskiy wrote:
> 
> 

Why would the new reader audit that the core is taking references on the
back pointers it provides?

The to_pci_tsm_pf0() object casting path has safety checks based on type
which can be inferred by walking the backref.

---

## [41] Aneesh Kumar K.V — 2025-09-11
*Subject: Re: [PATCH 5/7] PCI/TSM: Add Device Security (TVM Guest) operations
 support*

<dan.j.williams@intel.com> writes:

> Aneesh Kumar K.V wrote:
>> Dan Williams <dan.j.williams@intel.com> writes:

Sure I can pass struct cca_guest_dsc *dsm as an agrument to
rsi_device_lock().

I was comparing this to connect() callback which when getting called
will already have pdev->tsm set.

static int pci_tsm_connect(struct pci_dev *pdev, struct tsm_dev *tsm_dev)
{
	int rc;
	struct pci_tsm_pf0 *tsm_pf0;
	const struct pci_tsm_ops *ops = tsm_pci_ops(tsm_dev);
	struct pci_tsm *pci_tsm __free(tsm_remove) = ops->probe(pdev);

.....

	pdev->tsm = pci_tsm;
	tsm_pf0 = to_pci_tsm_pf0(pdev->tsm);

...
	rc = ops->connect(pdev);
	if (rc)
		return rc;

	pdev->tsm = no_free_ptr(pci_tsm);

}


-aneesh

---

## [42] Jonathan Cameron — 2025-09-16
*Subject: Re: [PATCH 3/7] device core: Introduce confidential device
 acceptance*

> diff --git a/drivers/base/coco.c b/drivers/base/coco.c
> new file mode 100644

> +/**
> + * device_cc_accept(): Mark a device as accepted for TEE operation

once

> + *
> + * Given that moving a device into confidential / private operation implicates

I'm not sure what 'implicates' covers here.

> + * any of MMIO mapping attributes, physical address, and IOMMU mappings this
> + * transition must be done while the device is idle (driver detached).

---

## [43] Jonathan Cameron — 2025-09-16
*Subject: Re: [PATCH 5/7] PCI/TSM: Add Device Security (TVM Guest) operations
 support*

One trivial thing noticed on a first scan through.

>  Documentation/ABI/testing/sysfs-bus-pci   |  46 ++-
>  Documentation/ABI/testing/sysfs-class-tsm |  19 ++

> +
> +What:		/sys/bus/pci/devices/.../tsm/lock

th device device -> the device.?

> +		device. This puts the device in a state where it can not accept
> +		or issue secure memory cycles (T=1 in the PCIe TLP), and

---

## [44] Jason Gunthorpe — 2025-09-17
*Subject: Re: [PATCH 4/7] x86/ioremap, resource: Introduce
 IORES_DESC_ENCRYPTED for encrypted PCI MMIO*

On Tue, Aug 26, 2025 at 08:52:56PM -0700, Dan Williams wrote:
> PCIe Trusted Execution Environment Device Interface Security Protocol
> (TDISP) arranges for a PCI device to support encrypted MMIO. In support of

I was just looking at the ioremap stuff from the core mm side, and I
really don't understand this patch. I agree with the commit message
though..

What I expect to see in this series is not x86 code (that should be in
a series enabling x86 TSM!) but code to update the pgprot_decrypted()
calls in io_remap_pfn_range() so they are conditional.

And futher code to validate that the pfn range requested by
io_remap_pfn_range() on a TEE secured device is one that has been
checked and validated with the TSM as being actually authentic and
private.

Bascially when a driver on a T=1 struct device calls
io_remap_pfn_range() it must be private MMIO, enforced by core code.

That probably does involve a new IORES_DESC_ENCRYPTED flag..

Jason

---

## [45] Alexey Kardashevskiy — 2025-10-07
*Subject: Re: [PATCH 4/7] x86/ioremap, resource: Introduce IORES_DESC_ENCRYPTED
 for encrypted PCI MMIO*

On 27/8/25 13:52, Dan Williams wrote:
> PCIe Trusted Execution Environment Device Interface Security Protocol
> (TDISP) arranges for a PCI device to support encrypted MMIO. In support of

How is this expected to work exactly?

samples/devsec/tsm.c calls pci_tsm_alloc_encrypted_resources() which essentially does:

*__res[i] = DEFINE_RES_NAMED_DESC(pci_resource_start(pdev, i),
                                   len, "PCI MMIO Encrypted",
                                   flags, IORES_DESC_ENCRYPTED);
                                                                
if (insert_resource(&iomem_resource, __res[i]) != 0) {
...

By later on pci_iomap(pdev, N, PAGE_SIZE) on that BAR maps as unencrypted. The resource makes it to (hacked) iomem:

c000000000-c7ffffffff : PCI Bus 0000:00 fl=200201 desc=0
   c000000000-c01fffffff : PCI Bus 0000:01 fl=102201 desc=0
     c000000000-c003ffffff : 0000:01:00.0 fl=14220c desc=0
       c000000000-c003ffffff : mydrv fl=80000200 desc=0
     c004000000-c004000fff : PCI MMIO Encrypted fl=14220c desc=a
       c004000000-c004000fff : 0000:01:00.0 fl=14220c desc=0
     c004001000-c004001fff : 0000:01:00.0 fl=14220c desc=0


and btw does not pci_resource_n(pdev, i) make more sense as a parent in insert_resource().


> 
> Cc: Dave Hansen <dave.hansen@linux.intel.com>


Here the found "res" is actually "c000000000-c7ffffffff : PCI Bus 0000:00", not c004000000 (from the above example)...

>   
> -	return ((desc->flags & (IORES_MAP_SYSTEM_RAM | IORES_MAP_ENCRYPTED)) ==


... which seems to be the result of passing IORES_DESC_NONE. What do I miss? Thanks,


>   
>   	__ioremap_check_other(addr, desc);

---

## [46] Alexey Kardashevskiy — 2025-10-08
*Subject: Re: [PATCH 4/7] x86/ioremap, resource: Introduce IORES_DESC_ENCRYPTED
 for encrypted PCI MMIO*

On 7/10/25 19:23, Alexey Kardashevskiy wrote:
> 
> 

Adding this here:

+       walk_iomem_res_desc(IORES_DESC_ENCRYPTED, IORESOURCE_MEM, start, end, desc,
+                           __ioremap_collect_map_flags);


fixed the problem and the encryption bit is set. Thanks,


>> -    walk_mem_res(start, end, desc, __ioremap_collect_map_flags);
>> +    walk_iomem_res_desc(IORES_DESC_NONE, IORESOURCE_MEM, start, end, desc,

---

## [47] Xu Yilun — 2025-10-10
*Subject: Re: [PATCH 2/7] PCI/TSM: Add pci_tsm_guest_req() for managing TDIs*

> > >> Out of curiosity (probably could go to the commit log) - for what kind
> > >> of request and on which platform we do not know the response size in

For TDX, the maximum response size are decided by guest, that's because
GHCI says guest should allocate request/response pages big enough for the
GHCI call. But guest may not know the actual response data size generated
by host.

> > > 
> > > I don't know. Given this is to support any possible combination of TSM

Now the API looks like:

 int pci_tsm_guest_req(struct pci_dev *pdev, enum pci_tsm_req_scope scope,
                       void *req_in, size_t in_len, void *req_out,
                       size_t out_len, u64 *tsm_code)

I understand the out_len should be the maximum response size decided by
guest, then I need an extra parameter actual_out_len.


Another thing is, the req_in/out bufers are user buffers passed in from
QEMU, but IOMMUFD does't have to copy them. We could offload the work to
TSM driver. It is because only TSM driver knows/cares the actual valid
data size in these pages, it could do copy_from/to_user() in most
efficient way.

----8<----

 int pci_tsm_guest_req(struct pci_dev *pdev, enum pci_tsm_req_scope scope,
-                     void *req_in, size_t in_len, void *req_out,
-                     size_t out_len, u64 *tsm_code)
+                     void __user *req_in, size_t in_len, void __user *req_out,
+                     size_t out_len, size_t *actual_out_len, u64 *tsm_code)


>

---
