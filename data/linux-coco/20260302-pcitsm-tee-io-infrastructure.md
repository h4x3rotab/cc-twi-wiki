---
title: 'PCI/TSM: TEE I/O infrastructure'
date: 2026-03-02
last_reply: 2026-04-24
message_count: 99
participants: ['Dan Williams', 'kernel test robot', 'Baolu Lu', 'Alexey Kardashevskiy', 'Aneesh Kumar K.V', 'Jonathan Cameron', 'Greg KH', 'Xu Yilun', 'Jason Gunthorpe', 'Jakub Kicinski', 'Lukas Wunner', 'Borislav Petkov', 'Lai, Yi']
---

## [1] Dan Williams — 2026-03-02

Changes since v1 [1]:
- Add a netlink ABI for conveying device attestation evidence and
  interface reports
- Add a module autoprobe policy proposal
- Add simulated device evidence support to samples/devsec/
- Add MMIO resource evaluation from a TDISP device interface report
- Include device_cc_accepted() proposals for DMA setup
- Restore a lookup mechanism from tsm class device to all established
  streams
- Clarify TEE vs Confidential vs Private in drivers/base/coco.c (Greg)
- Move 'cc_accepted' to an additional bitfield next to 'dead' (Greg)
- Drop device_cc_probe() proposal (Jason)

[1]: http://lore.kernel.org/20250827035259.1356758-1-dan.j.williams@intel.com

---

Overview
========

TEE I/O starts with the premise that devices are adversarial. That
threat model needs a series of new ABIs and mechanisms. The x86 changes
and the samples/devsec/ implementation in this set serve to have a
consumer for all of these proposed mechanisms.

1/ Userspace needs to be able to intercept driver attach. If a relying
   party does not endorse the system talking to a given device then
   userspace needs a control point to decline device operation. Module
   policy is suitable for that policy mechanism. See "device core:
   Autoprobe considered harmful?"

2/ Userspace needs to be able to gather evidence that validates the
   device's identity, configuration, and active mappings of MMIO and DMA.
   See "PCI/TSM: Add 'evidence' support"

3/ To gather and act on device evidence a device needs a "lock"
   mechanism to hold a stable configuration, and an "accept" mechanism to
   bring the device into operation after relying party validation. See
   "PCI/TSM: Add Device Security (TVM Guest) LOCK operation support" and
   "PCI/TSM: Add Device Security (TVM Guest) ACCEPT operation support".

4/ Drivers must be unmodified (1): ioremap() requests must automatically
   determine whether a resource range is mapped as encrypted or not. See
   "x86, ioremap, resource: Support IORES_DESC_ENCRYPTED for encrypted PCI
   MMIO". TODO: test unencrypted ranges in the middle of a PCI device BAR
   that is otherwise encrypted (MSI-X table case).

5/ Drivers must be unmodified (2): dma_alloc_coherent() and dma_map()
   need to bypass swiotlb and potentially modify DMA handles when a device
   is accepted to DMA direct to private memory. See "x86, swiotlb: Teach
   swiotlb to skip 'accepted' devices" and "x86, dma: Allow accepted
   devices to map private memory".

Note an example SEV-TIO implementation of the lock+accept operations is
out for review here [2] (based on older baseline of tsm.git#staging).

[2]: http://lore.kernel.org/20260225053806.3311234-1-aik@amd.com

On PCI/TSM Netlink and Rust SPDM
================================

The PCI/TSM netlink proposal is a result of the discussion from the Rust
SPDM proposal [3]. That thread discussed the merits of an SPDM netlink
ABI that multicasts signature events and a ".cma" keyring to
authenticate PCI devices. The PCI/TSM netlink proposal diverges
significantly based on the following assumptions:

1/ Device acceptance decisions are based on evidence material beyond
   whether the device publishes a valid root certificate (kernel SPDM
   library proposal).

2/ Automatic device identity revalidation after reset is secondary to
   initial device acceptance. It is follow-on work that can be achieved
   without a ".cma" ring. For example, cache a hash of the device
   certificate chain and / or measurements. Otherwise, mere identity
   revalidation is insufficient for PCI TDISP.

3/ Device evidence mutates based on userspace taking action on the
   device state. For example, the device interface report is not available
   until post "lock". The result, the netlink interface must be on demand,
   not implicit multicast. PCI/TSM evidence conveyance is a netlink
   "dump" request.

The proposal for how the native kernel SPDM support would interact with
the PCI/TSM implementation is via an "spdm-tsm" driver. An "spdm-tsm"
driver allows for userspace policy to select between a kernel native
"spdm-tsm" and "$platform-tsm" as only one TSM can have a session
established at a time.

[3]: http://lore.kernel.org/20260211032935.2705841-1-alistair.francis@wdc.com

On PCI/TSM Netlink and guest request
====================================

One of the open questions is whether pci_tsm_guest_req() should be used
to convey device evidence to guests.  In other words, if the core kernel
understands 'struct pci_tsm_evidence' in a common way across
architectures, why not implement a common transport and save
pci_tsm_guest_req() for other ancillary messages that are indeed
implementation specific?


This all passes a tools/testing/devsec/devsec.sh run. It wants a rebase
on v7.0-rc2. It is pushed out as new tag, devsec-20260302, in the
tsm.git#staging tree. The Maturity Map [4] has been updated accordingly.

[4]: https://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git/tree/Documentation/driver-api/pci/tsm.rst?h=staging

Dan Williams (19):
  PCI/TSM: Report active IDE streams per host bridge
  device core: Fix kernel-doc warnings in base.h
  device core: Introduce confidential device acceptance
  modules: Document the global async_probe parameter
  device core: Autoprobe considered harmful?
  PCI/TSM: Add Device Security (TVM Guest) LOCK operation support
  PCI/TSM: Add Device Security (TVM Guest) ACCEPT operation support
  PCI/TSM: Add "evidence" support
  PCI/TSM: Support creating encrypted MMIO descriptors via TDISP Report
  x86, swiotlb: Teach swiotlb to skip "accepted" devices
  x86, dma: Allow accepted devices to map private memory
  x86, ioremap, resource: Support IORES_DESC_ENCRYPTED for encrypted PCI
    MMIO
  samples/devsec: Introduce a PCI device-security bus + endpoint sample
  samples/devsec: Add sample IDE establishment
  samples/devsec: Add sample TSM bind and guest_request flows
  samples/devsec: Introduce a "Device Security TSM" sample driver
  tools/testing/devsec: Add a script to exercise samples/devsec/
  samples/devsec: Add evidence support
  tools/testing/devsec: Add basic evidence retrieval validation

 drivers/base/Kconfig                        |  28 +
 drivers/pci/Kconfig                         |   2 +
 samples/Kconfig                             |  19 +
 drivers/base/Makefile                       |   1 +
 drivers/pci/Makefile                        |   2 +-
 drivers/pci/tsm/Makefile                    |   9 +
 samples/Makefile                            |   1 +
 samples/devsec/Makefile                     |  16 +
 Documentation/ABI/stable/sysfs-module       |  20 +
 Documentation/ABI/testing/sysfs-bus-pci     |  47 +-
 Documentation/ABI/testing/sysfs-class-tsm   |  32 +
 Documentation/ABI/testing/sysfs-faux-devsec |  15 +
 Documentation/driver-api/pci/tsm.rst        |  44 ++
 Documentation/netlink/specs/pci-tsm.yaml    | 151 ++++
 drivers/base/base.h                         |  89 ++-
 drivers/pci/tsm/netlink.h                   |  23 +
 include/linux/device.h                      |  23 +
 include/linux/ioport.h                      |   2 +
 include/linux/module.h                      |  14 +
 include/linux/pci-ide.h                     |   2 +
 include/linux/pci-tsm.h                     | 121 ++-
 include/linux/swiotlb.h                     |  15 +-
 include/linux/tsm.h                         |   3 +
 include/uapi/linux/pci-tsm-netlink.h        | 101 +++
 samples/devsec/devsec.h                     |  48 ++
 arch/x86/kernel/pci-dma.c                   |   2 +-
 arch/x86/mm/ioremap.c                       |  49 +-
 arch/x86/mm/mem_encrypt.c                   |   5 +-
 drivers/base/bus.c                          |   7 +-
 drivers/base/coco.c                         |  58 ++
 drivers/base/dd.c                           |  26 +-
 drivers/pci/ide.c                           |   4 +
 drivers/pci/{tsm.c => tsm/core.c}           | 532 ++++++++++++-
 drivers/pci/tsm/evidence.c                  | 274 +++++++
 drivers/pci/tsm/netlink.c                   |  43 ++
 drivers/virt/coco/tsm-core.c                | 138 ++++
 kernel/dma/swiotlb.c                        |   1 +
 kernel/module/main.c                        |  13 +
 samples/devsec/bus.c                        | 784 ++++++++++++++++++++
 samples/devsec/common.c                     | 160 ++++
 samples/devsec/link_tsm.c                   | 432 +++++++++++
 samples/devsec/pci.c                        |  39 +
 samples/devsec/tsm.c                        | 131 ++++
 tools/testing/devsec/devsec.sh              | 280 +++++++
 MAINTAINERS                                 |   6 +-
 45 files changed, 3736 insertions(+), 76 deletions(-)
 create mode 100644 drivers/pci/tsm/Makefile
 create mode 100644 samples/devsec/Makefile
 create mode 100644 Documentation/ABI/testing/sysfs-faux-devsec
 create mode 100644 Documentation/netlink/specs/pci-tsm.yaml
 create mode 100644 drivers/pci/tsm/netlink.h
 create mode 100644 include/uapi/linux/pci-tsm-netlink.h
 create mode 100644 samples/devsec/devsec.h
 create mode 100644 drivers/base/coco.c
 rename drivers/pci/{tsm.c => tsm/core.c} (63%)
 create mode 100644 drivers/pci/tsm/evidence.c
 create mode 100644 drivers/pci/tsm/netlink.c
 create mode 100644 samples/devsec/bus.c
 create mode 100644 samples/devsec/common.c
 create mode 100644 samples/devsec/link_tsm.c
 create mode 100644 samples/devsec/pci.c
 create mode 100644 samples/devsec/tsm.c
 create mode 100755 tools/testing/devsec/devsec.sh


base-commit: c2012263047689e495e81c96d7d5b0586299578d

---

## [2] Dan Williams — 2026-03-02
*Subject: [PATCH v2 01/19] PCI/TSM: Report active IDE streams per host bridge*

The first attempt at an ABI for this failed to account for naming
collisions across host bridges:

Commit a4438f06b1db ("PCI/TSM: Report active IDE streams")

Revive this ABI with a per host bridge link that appears at first stream
creation for a given host bridge and disappears after the last stream is
removed.

For systems with many host bridge objects it allows:

    ls /sys/class/tsm/tsmN/pci*/stream*

...to find all the host bridges with active streams without first iterating
over all host bridges. Yilun notes that is handy to have this short cut [1]
and from an administrator perspective it helps with inventory for
constrained stream resources.

Link: http://lore.kernel.org/aXLtILY85oMU5qlb@yilunxu-OptiPlex-7050 [1]
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 Documentation/ABI/testing/sysfs-class-tsm | 13 +++
 include/linux/pci-ide.h                   |  2 +
 include/linux/tsm.h                       |  3 +
 drivers/pci/ide.c                         |  4 +
 drivers/virt/coco/tsm-core.c              | 97 +++++++++++++++++++++++
 5 files changed, 119 insertions(+)

diff --git a/Documentation/ABI/testing/sysfs-class-tsm b/Documentation/ABI/testing/sysfs-class-tsm
index 2949468deaf7..1ddb8f357961 100644
--- a/Documentation/ABI/testing/sysfs-class-tsm
+++ b/Documentation/ABI/testing/sysfs-class-tsm
@@ -7,3 +7,16 @@ Description:
 		signals when the PCI layer is able to support establishment of
 		link encryption and other device-security features coordinated
 		through a platform tsm.
+
+What:		/sys/class/tsm/tsmN/pciDDDD:BB
+Contact:	linux-pci@vger.kernel.org
+Description:
+		(RO) When a PCIe host bridge has established a secure connection
+		via a TSM to an endpoint, this symlink appears. It facilitates a
+		TSM instance scoped view of PCIe Link Encryption and Secure
+		Session resource consumption across host bridges. The symlink
+		appears when a host bridge has 1 or more IDE streams established
+		with this TSM, and disappears when that number returns to 0. See
+		Documentation/ABI/testing/sysfs-devices-pci-host-bridge for the
+		description of the pciDDDD:BB/streamH.R.E symlink and the
+		pciDDDD:BB/available_secure_streams attribute.
diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
index ae07d9f699c0..381a1bf22a95 100644
--- a/include/linux/pci-ide.h
+++ b/include/linux/pci-ide.h
@@ -82,6 +82,7 @@ struct pci_ide_regs {
  * @host_bridge_stream: allocated from host bridge @ide_stream_ida pool
  * @stream_id: unique Stream ID (within Partner Port pairing)
  * @name: name of the established Selective IDE Stream in sysfs
+ * @tsm_dev: For TSM established IDE, the TSM device context
  *
  * Negative @stream_id values indicate "uninitialized" on the
  * expectation that with TSM established IDE the TSM owns the stream_id
@@ -93,6 +94,7 @@ struct pci_ide {
 	u8 host_bridge_stream;
 	int stream_id;
 	const char *name;
+	struct tsm_dev *tsm_dev;
 };
 
 /*
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index 22e05b2aac69..a3b7ab668eff 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -123,4 +123,7 @@ int tsm_report_unregister(const struct tsm_report_ops *ops);
 struct tsm_dev *tsm_register(struct device *parent, struct pci_tsm_ops *ops);
 void tsm_unregister(struct tsm_dev *tsm_dev);
 struct tsm_dev *find_tsm_dev(int id);
+struct pci_ide;
+int tsm_ide_stream_register(struct pci_ide *ide);
+void tsm_ide_stream_unregister(struct pci_ide *ide);
 #endif /* __TSM_H */
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index 23f554490539..9629f3ceb213 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -11,6 +11,7 @@
 #include <linux/pci_regs.h>
 #include <linux/slab.h>
 #include <linux/sysfs.h>
+#include <linux/tsm.h>
 
 #include "pci.h"
 
@@ -372,6 +373,9 @@ void pci_ide_stream_release(struct pci_ide *ide)
 	if (ide->partner[PCI_IDE_EP].enable)
 		pci_ide_stream_disable(pdev, ide);
 
+	if (ide->tsm_dev)
+		tsm_ide_stream_unregister(ide);
+
 	if (ide->partner[PCI_IDE_RP].setup)
 		pci_ide_stream_teardown(rp, ide);
 
diff --git a/drivers/virt/coco/tsm-core.c b/drivers/virt/coco/tsm-core.c
index 8712df8596a1..3c99c38cfaa5 100644
--- a/drivers/virt/coco/tsm-core.c
+++ b/drivers/virt/coco/tsm-core.c
@@ -4,10 +4,12 @@
 #define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
 
 #include <linux/tsm.h>
+#include <linux/pci.h>
 #include <linux/device.h>
 #include <linux/module.h>
 #include <linux/cleanup.h>
 #include <linux/pci-tsm.h>
+#include <linux/pci-ide.h>
 
 static struct class *tsm_class;
 static DEFINE_IDA(tsm_ida);
@@ -104,6 +106,100 @@ void tsm_unregister(struct tsm_dev *tsm_dev)
 }
 EXPORT_SYMBOL_GPL(tsm_unregister);
 
+static DEFINE_XARRAY(tsm_ide_streams);
+static DEFINE_MUTEX(tsm_ide_streams_lock);
+
+/* tracker for the bridge symlink when the bridge has any streams */
+struct tsm_ide_stream {
+	struct tsm_dev *tsm_dev;
+	struct pci_host_bridge *bridge;
+	struct kref kref;
+};
+
+static struct tsm_ide_stream *create_streams(struct tsm_dev *tsm_dev,
+					    struct pci_host_bridge *bridge)
+{
+	int rc;
+
+	struct tsm_ide_stream *streams __free(kfree) =
+		kzalloc(sizeof(*streams), GFP_KERNEL);
+	if (!streams)
+		return NULL;
+
+	streams->tsm_dev = tsm_dev;
+	streams->bridge = bridge;
+	kref_init(&streams->kref);
+	rc = xa_insert(&tsm_ide_streams, (unsigned long)bridge, streams,
+		       GFP_KERNEL);
+	if (rc)
+		return NULL;
+
+	rc = sysfs_create_link(&tsm_dev->dev.kobj, &bridge->dev.kobj,
+			       dev_name(&bridge->dev));
+	if (rc) {
+		xa_erase(&tsm_ide_streams, (unsigned long)bridge);
+		return NULL;
+	}
+
+	return no_free_ptr(streams);
+}
+
+int tsm_ide_stream_register(struct pci_ide *ide)
+{
+	struct tsm_ide_stream *streams;
+	struct pci_dev *pdev = ide->pdev;
+	struct pci_tsm *tsm = pdev->tsm;
+	struct tsm_dev *tsm_dev = tsm->tsm_dev;
+	struct pci_host_bridge *bridge = pci_find_host_bridge(pdev->bus);
+
+	guard(mutex)(&tsm_ide_streams_lock);
+	streams = xa_load(&tsm_ide_streams, (unsigned long)bridge);
+	if (streams)
+		kref_get(&streams->kref);
+	else
+		streams = create_streams(tsm_dev, bridge);
+
+	if (!streams)
+		return -ENOMEM;
+	ide->tsm_dev = tsm_dev;
+
+	return 0;
+}
+EXPORT_SYMBOL_GPL(tsm_ide_stream_register);
+
+static void destroy_streams(struct kref *kref)
+{
+	struct tsm_ide_stream *streams =
+		container_of(kref, struct tsm_ide_stream, kref);
+	struct tsm_dev *tsm_dev = streams->tsm_dev;
+	struct pci_host_bridge *bridge = streams->bridge;
+
+	lockdep_assert_held(&tsm_ide_streams_lock);
+	sysfs_remove_link(&tsm_dev->dev.kobj, dev_name(&bridge->dev));
+	xa_erase(&tsm_ide_streams, (unsigned long)bridge);
+	kfree(streams);
+}
+
+void tsm_ide_stream_unregister(struct pci_ide *ide)
+{
+	struct tsm_ide_stream *streams;
+	struct tsm_dev *tsm_dev = ide->tsm_dev;
+	struct pci_dev *pdev = ide->pdev;
+	struct pci_host_bridge *bridge = pci_find_host_bridge(pdev->bus);
+
+	guard(mutex)(&tsm_ide_streams_lock);
+	streams = xa_load(&tsm_ide_streams, (unsigned long)bridge);
+	/* catch API abuse */
+	if (dev_WARN_ONCE(&tsm_dev->dev,
+			  !streams || streams->tsm_dev != tsm_dev,
+			  "no IDE streams associated with %s\n",
+			  dev_name(&bridge->dev)))
+		return;
+	kref_put(&streams->kref, destroy_streams);
+	ide->tsm_dev = NULL;
+}
+EXPORT_SYMBOL_GPL(tsm_ide_stream_unregister);
+
 static void tsm_release(struct device *dev)
 {
 	struct tsm_dev *tsm_dev = container_of(dev, typeof(*tsm_dev), dev);
@@ -126,6 +222,7 @@ module_init(tsm_init)
 static void __exit tsm_exit(void)
 {
 	class_destroy(tsm_class);
+	xa_destroy(&tsm_ide_streams);
 }
 module_exit(tsm_exit)

---

## [3] Dan Williams — 2026-03-02
*Subject: [PATCH v2 02/19] device core: Fix kernel-doc warnings in base.h*

In preparation for adding new fields to 'struct device_private' fix up
existing kernel-doc warnings in this header file of the form:

Warning: drivers/base/base.h:59 struct member 'subsys' not described in
'subsys_private'
Warning: drivers/base/base.h:59 struct member 'devices_kset' not described
in 'subsys_private'
Warning: drivers/base/base.h:59 struct member 'interfaces' not described in
'subsys_private'
Warning: drivers/base/base.h:59 struct member 'mutex' not described in
'subsys_private'

...which are simple replacements of " - " with ": ".

Add new descriptions for these previously undescribed fields:

Warning: drivers/base/base.h:58 struct member 'drivers_autoprobe' not
described in 'subsys_private'
Warning: drivers/base/base.h:117 struct member 'deferred_probe_reason' not
described in 'device_private'

Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/base/base.h | 79 +++++++++++++++++++++++----------------------
 1 file changed, 41 insertions(+), 38 deletions(-)

diff --git a/drivers/base/base.h b/drivers/base/base.h
index 430cbefbc97f..b68355f5d6e3 100644
--- a/drivers/base/base.h
+++ b/drivers/base/base.h
@@ -13,27 +13,28 @@
 #include <linux/notifier.h>
 
 /**
- * struct subsys_private - structure to hold the private to the driver core portions of the bus_type/class structure.
- *
- * @subsys - the struct kset that defines this subsystem
- * @devices_kset - the subsystem's 'devices' directory
- * @interfaces - list of subsystem interfaces associated
- * @mutex - protect the devices, and interfaces lists.
- *
- * @drivers_kset - the list of drivers associated
- * @klist_devices - the klist to iterate over the @devices_kset
- * @klist_drivers - the klist to iterate over the @drivers_kset
- * @bus_notifier - the bus notifier list for anything that cares about things
- *                 on this bus.
- * @bus - pointer back to the struct bus_type that this structure is associated
- *        with.
+ * struct subsys_private - structure to hold the private to the driver core
+ *			   portions of the bus_type/class structure.
+ * @subsys: the struct kset that defines this subsystem
+ * @devices_kset: the subsystem's 'devices' directory
+ * @interfaces: list of subsystem interfaces associated
+ * @mutex: protect the devices, and interfaces lists.
+ * @drivers_kset: the list of drivers associated
+ * @klist_devices: the klist to iterate over the @devices_kset
+ * @klist_drivers: the klist to iterate over the @drivers_kset
+ * @bus_notifier: the bus notifier list for anything that cares about things
+ *		  on this bus.
+ * @drivers_autoprobe: gate whether new devices are automatically attached to
+ *		       registered drivers, or new drivers automatically attach
+ *		       to existing devices.
+ * @bus: pointer back to the struct bus_type that this structure is associated
+ *	 with.
  * @dev_root: Default device to use as the parent.
- *
- * @glue_dirs - "glue" directory to put in-between the parent device to
- *              avoid namespace conflicts
- * @class - pointer back to the struct class that this structure is associated
- *          with.
- * @lock_key:	Lock class key for use by the lock validator
+ * @glue_dirs: "glue" directory to put in-between the parent device to
+ *	       avoid namespace conflicts
+ * @class: pointer back to the struct class that this structure is associated
+ *	   with.
+ * @lock_key: Lock class key for use by the lock validator
  *
  * This structure is the one that is the actual kobject allowing struct
  * bus_type/class to be statically allocated safely.  Nothing outside of the
@@ -98,24 +99,26 @@ struct driver_type {
 #endif
 
 /**
- * struct device_private - structure to hold the private to the driver core portions of the device structure.
- *
- * @klist_children - klist containing all children of this device
- * @knode_parent - node in sibling list
- * @knode_driver - node in driver list
- * @knode_bus - node in bus list
- * @knode_class - node in class list
- * @deferred_probe - entry in deferred_probe_list which is used to retry the
- *	binding of drivers which were unable to get all the resources needed by
- *	the device; typically because it depends on another driver getting
- *	probed first.
- * @async_driver - pointer to device driver awaiting probe via async_probe
- * @device - pointer back to the struct device that this structure is
- * associated with.
- * @driver_type - The type of the bound Rust driver.
- * @dead - This device is currently either in the process of or has been
- *	removed from the system. Any asynchronous events scheduled for this
- *	device should exit without taking any action.
+ * struct device_private - structure to hold the private to the driver core
+ *			   portions of the device structure.
+ * @klist_children: klist containing all children of this device
+ * @knode_parent: node in sibling list
+ * @knode_driver: node in driver list
+ * @knode_bus: node in bus list
+ * @knode_class: node in class list
+ * @deferred_probe: entry in deferred_probe_list which is used to retry the
+ *		    binding of drivers which were unable to get all the
+ *		    resources needed by the device; typically because it depends
+ *		    on another driver getting probed first.
+ * @async_driver: pointer to device driver awaiting probe via async_probe
+ * @deferred_probe_reason: capture the -EPROBE_DEFER message emitted with
+ *			   dev_err_probe() for later retrieval via debugfs
+ * @device: pointer back to the struct device that this structure is
+ *	    associated with.
+ * @driver_type: The type of the bound Rust driver.
+ * @dead: This device is currently either in the process of or has been
+ *	  removed from the system. Any asynchronous events scheduled for this
+ *	  device should exit without taking any action.
  *
  * Nothing outside of the driver core should ever touch these fields.
  */

---

## [4] Dan Williams — 2026-03-02
*Subject: [PATCH v2 03/19] device core: Introduce confidential device acceptance*

An "accepted" device is one that is allowed to access private memory within
a Trusted Computing Boundary (TCB). The concept of "acceptance" is distinct
from other device properties like usb_device::authorized, or
tb_switch::authorized. The entry to the accepted state is a violent
operation in which the device will reject MMIO requests that are not
encrypted, and the device enters a new IOMMU protection domain to allow it
to access addresses that were previously off-limits.

Subsystems like the DMA mapping layer, that need to modify their behavior
based on the accept state, may only have access to the base 'struct
device'. It is also likely that the concept of TCB acceptance grows beyond
PCI devices over time. For these reasons, introduce the concept of
acceptance in 'struct device_private' which is device common, but only
suitable for buses and built-in infrastructure to consume.

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
 drivers/base/Kconfig   |  4 +++
 drivers/base/Makefile  |  1 +
 drivers/base/base.h    |  9 +++++++
 include/linux/device.h | 22 ++++++++++++++++
 drivers/base/coco.c    | 58 ++++++++++++++++++++++++++++++++++++++++++
 5 files changed, 94 insertions(+)
 create mode 100644 drivers/base/coco.c

diff --git a/drivers/base/Kconfig b/drivers/base/Kconfig
index 1786d87b29e2..d4743bf978ec 100644
--- a/drivers/base/Kconfig
+++ b/drivers/base/Kconfig
@@ -249,4 +249,8 @@ config FW_DEVLINK_SYNC_STATE_TIMEOUT
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
index b68355f5d6e3..1ae9a1679504 100644
--- a/drivers/base/base.h
+++ b/drivers/base/base.h
@@ -119,8 +119,13 @@ struct driver_type {
  * @dead: This device is currently either in the process of or has been
  *	  removed from the system. Any asynchronous events scheduled for this
  *	  device should exit without taking any action.
+ * @cc_accepted: track the TEE acceptance state of the device for deferred
+ *		 probing, MMIO mapping type, and SWIOTLB bypass for private memory DMA.
  *
  * Nothing outside of the driver core should ever touch these fields.
+ *
+ * All bitfield flags are manipulated under device_lock() to avoid
+ * read-modify-write collisions.
  */
 struct device_private {
 	struct klist klist_children;
@@ -136,6 +141,10 @@ struct device_private {
 	struct driver_type driver_type;
 #endif
 	u8 dead:1;
+#ifdef CONFIG_CONFIDENTIAL_DEVICES
+	u8 cc_accepted:1;
+#endif
+
 };
 #define to_device_private_parent(obj)	\
 	container_of(obj, struct device_private, knode_parent)
diff --git a/include/linux/device.h b/include/linux/device.h
index 0be95294b6e6..4470365d772b 100644
--- a/include/linux/device.h
+++ b/include/linux/device.h
@@ -1191,6 +1191,28 @@ static inline bool device_link_test(const struct device_link *link, u32 flags)
 	return !!(link->flags & flags);
 }
 
+/* Confidential Device state helpers */
+#ifdef CONFIG_CONFIDENTIAL_DEVICES
+int device_cc_accept(struct device *dev);
+int device_cc_reject(struct device *dev);
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
+static inline bool device_cc_accepted(struct device *dev)
+{
+	return false;
+}
+#endif /* CONFIG_CONFIDENTIAL_DEVICES */
+
 /* Create alias, so I can be autoloaded. */
 #define MODULE_ALIAS_CHARDEV(major,minor) \
 	MODULE_ALIAS("char-major-" __stringify(major) "-" __stringify(minor))
diff --git a/drivers/base/coco.c b/drivers/base/coco.c
new file mode 100644
index 000000000000..2589745530e3
--- /dev/null
+++ b/drivers/base/coco.c
@@ -0,0 +1,58 @@
+// SPDX-License-Identifier: GPL-2.0
+/* Copyright (C) 2026 Intel Corporation */
+#include <linux/device.h>
+#include <linux/lockdep.h>
+#include "base.h"
+
+/*
+ * Confidential devices implement encrypted + integrity protected MMIO and have
+ * the ability to issue DMA to encrypted + integrity protected System RAM
+ * (private memory). The device_cc_*() helpers aid buses in setting the
+ * acceptance state and the DMA mapping subsystem augmenting behavior in the
+ * presence of accepted devices.
+ */
+
+/**
+ * device_cc_accept(): Mark a device as able to access private memory
+ * @dev: device to accept
+ *
+ * Confidential bus drivers use this helper to accept devices. For example, PCI
+ * has a sysfs ABI to accept devices after relying party attestation.
+ *
+ * Given that moving a device into confidential / private operation implicates
+ * changes to MMIO mapping attributes and DMA mappings, the transition must be
+ * done while the device is idle (driver detached).
+ */
+int device_cc_accept(struct device *dev)
+{
+	lockdep_assert_held(&dev->mutex);
+
+	if (dev->driver)
+		return -EBUSY;
+	dev->p->cc_accepted = 1;
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
+	dev->p->cc_accepted = 0;
+
+	return 0;
+}
+
+/**
+ * device_cc_accepted(): Fetch the device's ability to access private memory
+ * @dev: device to check
+ *
+ * Mechanisms like swiotlb and dma_alloc() need to augment their behavior in the
+ * presence of accepted devices.
+ */
+bool device_cc_accepted(struct device *dev)
+{
+	return dev->p->cc_accepted;
+}

---

## [5] Dan Williams — 2026-03-02
*Subject: [PATCH v2 04/19] modules: Document the global async_probe parameter*

In preparation for adding another /sys/module/module/parameters entry,
document the existing async_probe parameter.

Cc: Saravana Kannan <saravanak@google.com>
Cc: Luis Chamberlain <mcgrof@kernel.org>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 Documentation/ABI/stable/sysfs-module | 10 ++++++++++
 1 file changed, 10 insertions(+)

diff --git a/Documentation/ABI/stable/sysfs-module b/Documentation/ABI/stable/sysfs-module
index 41b1f16e8795..397c5c850894 100644
--- a/Documentation/ABI/stable/sysfs-module
+++ b/Documentation/ABI/stable/sysfs-module
@@ -45,3 +45,13 @@ Date:		Jun 2005
 Description:
 		If the module source has MODULE_VERSION, this file will contain
 		the version of the source code.
+
+What:		/sys/module/module/parameters/async_probe
+Description:
+		(RW) Emits "1" if drivers from loadable modules attempt async
+		probing by default. Emits "0" if drivers from loadable modules
+		attempt synchronous probing by default. This value is overridden
+		(in priority order) by: the module's built-in "PROBE_FORCE_*"
+		requests, the "driver_async_probe=..." kernel command line, the
+		"async_probe" module option, then this default. Write a valid
+		boolean value to toggle this policy.

---

## [6] Dan Williams — 2026-03-02
*Subject: [PATCH v2 05/19] device core: Autoprobe considered harmful?*

The threat model of PCI Trusted Execution Environment Device Interface
Security Protocol (TDISP), is that an adversary may be impersonating the
device's identity, redirecting the device's MMIO interface, and/or
snooping/manipulating the physical link. Outside of PCI TDISP, PCI ATS
(that allows IOMMU bypass) comes to mind as another threat vector that
warrants additional device verification beyond whether ACPI enumerates the
device as "internal" [1].

The process of verifying a device ranges from the traditional default
"accept everything" to gathering signed evidence from a locked device,
shipping it to a relying party and acting on that disposition. That policy
belongs in userspace. A natural way for userspace to get a control point
for verifying a device before use is when the driver for the device comes
from a module.

For deployments that are concerned about adversarial devices, introduce a
mechanism to disable autoprobe. When a driver originates from a module,
consult that driver's autoprobe policy at initial device or driver attach.

Note that with TDISP, unaccepted devices do not have access to private
memory (so called "T=0" mode). However, a deployment may still not want to
operate more than a handful of boot devices until confirming the system
device topology with a verifier.

Yes, this is a security vs convenience tradeoff. Yes, devices with
non-modular drivers are out of scope. Yes, there are known regression cases
for subsystems where device objects are expected to auto-attach outside of
fatal probe failure. For navigating regressions, a per-module "autoprobe"
option is included to allow fine grained policy.

Cc: Christoph Hellwig <hch@lst.de>
Cc: Jason Gunthorpe <jgg@nvidia.com>
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
Link: http://lore.kernel.org/6971b9406d069_1d33100df@dwillia2-mobl4.notmuch [1]
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/base/Kconfig                  | 24 ++++++++++++++++++++++++
 Documentation/ABI/stable/sysfs-module | 10 ++++++++++
 drivers/base/base.h                   |  1 +
 include/linux/module.h                | 14 ++++++++++++++
 drivers/base/bus.c                    |  7 ++++++-
 drivers/base/dd.c                     | 26 +++++++++++++++++++++++---
 kernel/module/main.c                  | 13 +++++++++++++
 7 files changed, 91 insertions(+), 4 deletions(-)

diff --git a/drivers/base/Kconfig b/drivers/base/Kconfig
index d4743bf978ec..7c1da5df9745 100644
--- a/drivers/base/Kconfig
+++ b/drivers/base/Kconfig
@@ -253,4 +253,28 @@ config CONFIDENTIAL_DEVICES
 	depends on ARCH_HAS_CC_PLATFORM
 	bool
 
+config MODULES_AUTOPROBE
+	bool "Automatic probe of drivers from modules"
+	default y
+	help
+	  Say Y for the typical and traditional Linux behavior of automatically
+	  attaching devices to drivers when a module is loaded.
+
+	  Say N to opt into a threat model where userspace verification of a
+	  device is required before driver attach. This includes Confidential
+	  Computing use cases where the device needs to have its configuration
+	  locked and verified by a relying party. It also includes use cases
+	  like leaving devices with Address Translation (IOMMU protection
+	  bypass) capability disabled until userspace attests the device and
+	  binds a driver.
+
+	  This default value can be overridden by the "autoprobe" module option.
+	  Note that some subsystems may not be prepared for autoprobe to be
+	  disabled, take care to test your selected drivers.  Built-in drivers are
+	  unaffected by this policy and will autoprobe unless the bus itself has
+	  disabled autoprobe.
+
+	  If in doubt, say Y. The N case is only for expert configurations, and
+	  selective "autoprobe=0" in modprobe policy is the common expectation.
+
 endmenu
diff --git a/Documentation/ABI/stable/sysfs-module b/Documentation/ABI/stable/sysfs-module
index 397c5c850894..1085d0942b17 100644
--- a/Documentation/ABI/stable/sysfs-module
+++ b/Documentation/ABI/stable/sysfs-module
@@ -55,3 +55,13 @@ Description:
 		requests, the "driver_async_probe=..." kernel command line, the
 		"async_probe" module option, then this default. Write a valid
 		boolean value to toggle this policy.
+
+What:		/sys/module/module/parameters/modules_autoprobe
+Description:
+		(RW) Emits "1" if drivers from loadable modules automatically
+		attach to their devices. Emits "0" if userspace is responsible
+		to attach devices to drivers post module load, or device
+		arrival. This value defaults to CONFIG_MODULES_AUTOPROBE compile
+		to configuration and is overridden by either a bus's autoprobe
+		policy or the per-module "autoprobe" option. Write a valid
+		boolean value to toggle this policy.
diff --git a/drivers/base/base.h b/drivers/base/base.h
index 1ae9a1679504..908ba366b8d2 100644
--- a/drivers/base/base.h
+++ b/drivers/base/base.h
@@ -230,6 +230,7 @@ void device_block_probing(void);
 void device_unblock_probing(void);
 void deferred_probe_extend_timeout(void);
 void driver_deferred_probe_trigger(void);
+bool driver_autoprobe(struct device_driver *drv);
 const char *device_get_devnode(const struct device *dev, umode_t *mode,
 			       kuid_t *uid, kgid_t *gid, const char **tmp);
 
diff --git a/include/linux/module.h b/include/linux/module.h
index d80c3ea57472..7db34ef0400c 100644
--- a/include/linux/module.h
+++ b/include/linux/module.h
@@ -450,6 +450,7 @@ struct module {
 #endif
 
 	bool async_probe_requested;
+	bool autoprobe;
 
 	/* Exception table */
 	unsigned int num_exentries;
@@ -761,6 +762,14 @@ static inline bool module_requested_async_probing(struct module *module)
 	return module && module->async_probe_requested;
 }
 
+static inline bool module_requested_autoprobe(struct module *module)
+{
+	/* Built-in modules autoprobe by default. */
+	if (!module)
+		return true;
+	return module->autoprobe;
+}
+
 static inline bool is_livepatch_module(struct module *mod)
 {
 #ifdef CONFIG_LIVEPATCH
@@ -865,6 +874,11 @@ static inline bool module_requested_async_probing(struct module *module)
 	return false;
 }
 
+static inline bool module_requested_autoprobe(struct module *module)
+{
+	/* Built-in modules autoprobe by default. */
+	return true;
+}
 
 static inline void set_module_sig_enforced(void)
 {
diff --git a/drivers/base/bus.c b/drivers/base/bus.c
index 9eb7771706f0..26ca98cd2a74 100644
--- a/drivers/base/bus.c
+++ b/drivers/base/bus.c
@@ -677,6 +677,11 @@ static ssize_t uevent_store(struct device_driver *drv, const char *buf,
 }
 static DRIVER_ATTR_WO(uevent);
 
+bool driver_autoprobe(struct device_driver *drv)
+{
+	return module_requested_autoprobe(drv->owner);
+}
+
 /**
  * bus_add_driver - Add a driver to the bus.
  * @drv: driver.
@@ -711,7 +716,7 @@ int bus_add_driver(struct device_driver *drv)
 		goto out_unregister;
 
 	klist_add_tail(&priv->knode_bus, &sp->klist_drivers);
-	if (sp->drivers_autoprobe) {
+	if (sp->drivers_autoprobe && driver_autoprobe(drv)) {
 		error = driver_attach(drv);
 		if (error)
 			goto out_del_list;
diff --git a/drivers/base/dd.c b/drivers/base/dd.c
index 349f31bedfa1..926e120b3cc4 100644
--- a/drivers/base/dd.c
+++ b/drivers/base/dd.c
@@ -917,6 +917,12 @@ struct device_attach_data {
 	 * driver, we'll encounter one that requests asynchronous probing.
 	 */
 	bool have_async;
+
+	/*
+	 * On initial device arrival driver attach is subject to
+	 * driver_autoprobe() policy.
+	 */
+	bool initial_probe;
 };
 
 static int __device_attach_driver(struct device_driver *drv, void *_data)
@@ -926,6 +932,13 @@ static int __device_attach_driver(struct device_driver *drv, void *_data)
 	bool async_allowed;
 	int ret;
 
+	/*
+	 * At initial probe of a newly arrived device, honor the policy to defer
+	 * attachment to explicit userspace bind request.
+	 */
+	if (data->initial_probe && !driver_autoprobe(drv))
+		return 0;
+
 	ret = driver_match_device(drv, dev);
 	if (ret == 0) {
 		/* no match */
@@ -998,8 +1011,13 @@ static void __device_attach_async_helper(void *_dev, async_cookie_t cookie)
 	put_device(dev);
 }
 
-static int __device_attach(struct device *dev, bool allow_async)
+#define DEVICE_ATTACH_F_ASYNC BIT(0)
+#define DEVICE_ATTACH_F_INITIAL BIT(1)
+
+static int __device_attach(struct device *dev, unsigned long flags)
 {
+	bool allow_async = flags & DEVICE_ATTACH_F_ASYNC;
+	bool initial_probe = flags & DEVICE_ATTACH_F_INITIAL;
 	int ret = 0;
 	bool async = false;
 
@@ -1023,6 +1041,7 @@ static int __device_attach(struct device *dev, bool allow_async)
 			.dev = dev,
 			.check_async = allow_async,
 			.want_async = false,
+			.initial_probe = initial_probe,
 		};
 
 		if (dev->parent)
@@ -1071,7 +1090,7 @@ static int __device_attach(struct device *dev, bool allow_async)
  */
 int device_attach(struct device *dev)
 {
-	return __device_attach(dev, false);
+	return __device_attach(dev, 0);
 }
 EXPORT_SYMBOL_GPL(device_attach);
 
@@ -1083,7 +1102,8 @@ void device_initial_probe(struct device *dev)
 		return;
 
 	if (sp->drivers_autoprobe)
-		__device_attach(dev, true);
+		__device_attach(dev, DEVICE_ATTACH_F_INITIAL |
+					     DEVICE_ATTACH_F_ASYNC);
 
 	subsys_put(sp);
 }
diff --git a/kernel/module/main.c b/kernel/module/main.c
index 710ee30b3bea..3fca2bc3217d 100644
--- a/kernel/module/main.c
+++ b/kernel/module/main.c
@@ -3001,6 +3001,10 @@ void flush_module_init_free_work(void)
 static bool async_probe;
 module_param(async_probe, bool, 0644);
 
+/* Default value for module->autoprobe */
+bool modules_autoprobe = IS_ENABLED(CONFIG_MODULES_AUTOPROBE);
+module_param(modules_autoprobe, bool, 0644);
+
 /*
  * This is where the real work happens.
  *
@@ -3304,6 +3308,14 @@ static int unknown_module_param_cb(char *param, char *val, const char *modname,
 		return 0;
 	}
 
+	if (strcmp(param, "autoprobe") == 0) {
+		bool autoprobe;
+
+		if (kstrtobool(val, &autoprobe) >= 0)
+			mod->autoprobe = autoprobe;
+		return 0;
+	}
+
 	/* Check for magic 'dyndbg' arg */
 	ret = ddebug_dyndbg_module_param_cb(param, val, modname);
 	if (ret != 0)
@@ -3473,6 +3485,7 @@ static int load_module(struct load_info *info, const char __user *uargs,
 		goto bug_cleanup;
 
 	mod->async_probe_requested = async_probe;
+	mod->autoprobe = modules_autoprobe;
 
 	/* Module is ready to execute: parsing args may do that. */
 	after_dashes = parse_args(mod->name, mod->args, mod->kp, mod->num_kp,

---

## [7] Dan Williams — 2026-03-02
*Subject: [PATCH v2 06/19] PCI/TSM: Add Device Security (TVM Guest) LOCK operation support*

PCIe Trusted Execution Environment Device Interface Security Protocol
(TDISP) has two distinct sets of operations. The first, already enabled in
driver/pci/tsm.c, enables the VMM to authenticate the physical function
(PCIe Component Measurement and Authentication (CMA)), establish a secure
message passing session (DMTF SPDM), and establish physical link security
(PCIe Integrity and Data Encryption (IDE)). The second set of operations
lets a VM manage the security state of assigned devices (TEE Device
Interfaces (TDIs)). Implement the LOCK/UNLOCK operations in pci_tsm_ops, to
be followed with an ACCEPT operation.

 - lock(): Transition the device to the TDISP state. In this mode
   the device is responsible for validating that it is in a secure
   configuration and will transition to the TDISP ERROR state if those
   settings are modified. Device Security Manager (DSM) and the TEE
   Security Manager (TSM) enforce that the device is not permitted to issue
   T=1 traffic in this mode.

 - unlock(): From the RUN state the only other TDISP states that can be
   moved to are ERROR or UNLOCKED. Voluntarily move the device to the
   UNLOCKED state.

Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Co-developed-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 Documentation/ABI/testing/sysfs-bus-pci   |  34 +++-
 Documentation/ABI/testing/sysfs-class-tsm |  19 ++
 Documentation/driver-api/pci/tsm.rst      |  44 +++++
 include/linux/device.h                    |   1 +
 include/linux/pci-tsm.h                   |  21 ++-
 drivers/pci/tsm.c                         | 213 +++++++++++++++++++++-
 drivers/virt/coco/tsm-core.c              |  41 +++++
 7 files changed, 363 insertions(+), 10 deletions(-)

diff --git a/Documentation/ABI/testing/sysfs-bus-pci b/Documentation/ABI/testing/sysfs-bus-pci
index b767db2c52cb..1ed77b9402a6 100644
--- a/Documentation/ABI/testing/sysfs-bus-pci
+++ b/Documentation/ABI/testing/sysfs-bus-pci
@@ -647,13 +647,16 @@ Description:
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
 
 What:		/sys/bus/pci/devices/.../tsm/dsm
 Contact:	linux-coco@lists.linux.dev
@@ -702,3 +705,30 @@ Description:
 		When present and the tsm/ attribute directory is present, the
 		authenticated attribute is an alias for the device 'connect'
 		state. See the 'tsm/connect' attribute for more details.
+		This is a "link" TSM attribute, see
+		Documentation/ABI/testing/sysfs-class-tsm.
+
+What:		/sys/bus/pci/devices/.../tsm/lock
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(RW) Write the name of a TSM (TEE Security Manager) device
+		instance to this file to request that the platform transition
+		the PCIe device configuration to the TDISP LOCKED state. This
+		puts the device in a state where security sensitive
+		configuration setting can not be changed without transitioning
+		the device the PCIe TDISP ERROR state. Reads from this attribute
+		return the name of the TSM device instance that has arranged for
+		the device to be locked, or the empty string if not locked. A
+		TSM class device signals its readiness for lock requests via a
+		KOBJ_CHANGE event. Writes fail with EBUSY if this device is
+		bound to a driver. This is a "devsec" TSM attribute, see
+		Documentation/ABI/testing/sysfs-class-tsm. See
+		Documentation/driver-api/pci/tsm.rst for more details.
+
+What:		/sys/bus/pci/devices/.../tsm/unlock
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(WO) Write the name of the TSM device that was specified to
+		'lock' to teardown the connection. Writes fail with EBUSY if
+		this device is bound to a driver. This is a "devsec" TSM
+		attribute, see Documentation/ABI/testing/sysfs-class-tsm.
diff --git a/Documentation/ABI/testing/sysfs-class-tsm b/Documentation/ABI/testing/sysfs-class-tsm
index 1ddb8f357961..76704501f082 100644
--- a/Documentation/ABI/testing/sysfs-class-tsm
+++ b/Documentation/ABI/testing/sysfs-class-tsm
@@ -20,3 +20,22 @@ Description:
 		Documentation/ABI/testing/sysfs-devices-pci-host-bridge for the
 		description of the pciDDDD:BB/streamH.R.E symlink and the
 		pciDDDD:BB/available_secure_streams attribute.
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
diff --git a/Documentation/driver-api/pci/tsm.rst b/Documentation/driver-api/pci/tsm.rst
index 232b92bec93f..e9b7ac70b404 100644
--- a/Documentation/driver-api/pci/tsm.rst
+++ b/Documentation/driver-api/pci/tsm.rst
@@ -5,6 +5,50 @@
 PCI Trusted Execution Environment Security Manager (TSM)
 ========================================================
 
+Overview
+========
+
+A "TSM", as detailed by PCIe r7.0 section 11 "TEE Device Interface
+Security Protocol (TDISP)", is an entity within the platform's Trusted
+Computing Base (TCB) that enforces security policies on the host. It
+serves to mitigate a threat model where devices may be under the control
+of an adversary. The adversarial threats are:
+
+- Identity: Device may be mimicking a legitimate device identity / firmware
+- Physical: link may be under observation, or control (reorder / drop data)
+- Virtual: Device MMIO presented to a guest may not actually map the
+  device, device DMA may be redirected.
+
+In Linux a "tsm" is a broader concept. It is a class device interface to
+mitigate one or more of the above threats. A "tsm driver" registers a
+tsm device that publishes either the 'tsm/connect' or
+'tsm/{lock,accept}' set of attributes for the PCIe device. The typical
+expectation is that 'tsm/{lock,accept}' is published by a guest "tsm
+driver" to mitigate "Virtual" threats. The 'tsm/connect' interface is
+published by a host "tsm driver" to mitigate "Identity" and/or
+"Physical" threats.
+
+Device Interface LOCK
+=====================
+The lock operation facilitated by tsm/lock (see
+Documentation/ABI/testing/sysfs-bus-pci) places the device in a mode
+where any security sensitive changes to the device configuration results
+in the device transitioning to the ERROR state. The device presents
+signed evidence of its LOCK state to the kernel through the tsm driver.
+The relying party is responsible for verifying not only the evidence but
+that the device is trusted to maintain those attested values while
+locked. Accepting the locked configuration also asserts that device is
+trusted to cease TCB interactions (send T=1 DMA / accept T=1 MMIO TLPs)
+when it is next unlocked by STOP. The TSM is responsible for enforcing
+that the device is not unlocked within the interval between evidence
+collection and acceptance, by correlating the evidence from LOCK to the
+subsequent RUN request.
+
+While the PCIe specification allows for the device to operate outside
+the TCB when locked, depending on the TSM architecture implementation,
+T=0 DMA from the device may be blocked until the device is next
+unlocked.
+
 Subsystem Interfaces
 ====================
 
diff --git a/include/linux/device.h b/include/linux/device.h
index 4470365d772b..f131623f39d9 100644
--- a/include/linux/device.h
+++ b/include/linux/device.h
@@ -911,6 +911,7 @@ static inline void device_unlock(struct device *dev)
 }
 
 DEFINE_GUARD(device, struct device *, device_lock(_T), device_unlock(_T))
+DEFINE_GUARD_COND(device, _intr, device_lock_interruptible(_T), _RET == 0)
 
 static inline void device_lock_assert(struct device *dev)
 {
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index a6435aba03f9..2a896b83bff9 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -68,7 +68,8 @@ struct pci_tsm_ops {
 	 * @unlock: destroy TSM context and return device to UNLOCKED state
 	 *
 	 * Context: @lock and @unlock run under pci_tsm_rwsem held for write to
-	 * sync with TSM unregistration and each other
+	 * sync with TSM unregistration and each other. All operations run under
+	 * the device lock for mutual exclusion with driver attach and detach.
 	 */
 	struct_group_tagged(pci_tsm_devsec_ops, devsec_ops,
 		struct pci_tsm *(*lock)(struct tsm_dev *tsm_dev,
@@ -106,6 +107,13 @@ struct pci_tdi {
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
@@ -126,6 +134,14 @@ struct pci_tsm_pf0 {
 	struct pci_doe_mb *doe_mb;
 };
 
+/**
+ * struct pci_tsm_devsec - context for tracking private/accepted PCI resources
+ * @base_tsm: generic core "tsm" context
+ */
+struct pci_tsm_devsec {
+	struct pci_tsm base_tsm;
+};
+
 /* physical function0 and capable of 'connect' */
 static inline bool is_pci_tsm_pf0(struct pci_dev *pdev)
 {
@@ -206,6 +222,8 @@ int pci_tsm_link_constructor(struct pci_dev *pdev, struct pci_tsm *tsm,
 			     struct tsm_dev *tsm_dev);
 int pci_tsm_pf0_constructor(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm,
 			    struct tsm_dev *tsm_dev);
+int pci_tsm_devsec_constructor(struct pci_dev *pdev, struct pci_tsm_devsec *tsm,
+			       struct tsm_dev *tsm_dev);
 void pci_tsm_pf0_destructor(struct pci_tsm_pf0 *tsm);
 int pci_tsm_doe_transfer(struct pci_dev *pdev, u8 type, const void *req,
 			 size_t req_sz, void *resp, size_t resp_sz);
@@ -216,6 +234,7 @@ void pci_tsm_tdi_constructor(struct pci_dev *pdev, struct pci_tdi *tdi,
 ssize_t pci_tsm_guest_req(struct pci_dev *pdev, enum pci_tsm_req_scope scope,
 			  sockptr_t req_in, size_t in_len, sockptr_t req_out,
 			  size_t out_len, u64 *tsm_code);
+struct pci_tsm_devsec *to_pci_tsm_devsec(struct pci_tsm *tsm);
 #else
 static inline int pci_tsm_register(struct tsm_dev *tsm_dev)
 {
diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index 5fdcd7f2e820..259e75092618 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -9,6 +9,7 @@
 #define dev_fmt(fmt) "PCI/TSM: " fmt
 
 #include <linux/bitfield.h>
+#include <linux/ioport.h>
 #include <linux/pci.h>
 #include <linux/pci-doe.h>
 #include <linux/pci-tsm.h>
@@ -63,6 +64,26 @@ static struct pci_tsm_pf0 *to_pci_tsm_pf0(struct pci_tsm *tsm)
 	return container_of(pf0->tsm, struct pci_tsm_pf0, base_tsm);
 }
 
+static inline bool is_devsec(struct pci_dev *pdev)
+{
+	return pdev->tsm && pdev->tsm->dsm_dev == NULL &&
+	       pdev->tsm->tdi == NULL;
+}
+
+/* 'struct pci_tsm_devsec' wraps 'struct pci_tsm' when ->tdi == ->dsm == NULL */
+struct pci_tsm_devsec *to_pci_tsm_devsec(struct pci_tsm *tsm)
+{
+	struct pci_dev *pdev = tsm->pdev;
+
+	if (!is_devsec(pdev) || !has_tee(pdev)) {
+		pci_WARN_ONCE(pdev, 1, "invalid context object\n");
+		return NULL;
+	}
+
+	return container_of(tsm, struct pci_tsm_devsec, base_tsm);
+}
+EXPORT_SYMBOL_GPL(to_pci_tsm_devsec);
+
 static void tsm_remove(struct pci_tsm *tsm)
 {
 	struct pci_dev *pdev;
@@ -536,6 +557,125 @@ static ssize_t dsm_show(struct device *dev, struct device_attribute *attr,
 }
 static DEVICE_ATTR_RO(dsm);
 
+/**
+ * pci_tsm_unlock() - Transition TDI from LOCKED/RUN to UNLOCKED
+ * @pdev: TDI device to unlock
+ *
+ * Returns void, requires all callers to have satisfied dependencies like making
+ * sure the device is locked and detached from its driver.
+ */
+static void pci_tsm_unlock(struct pci_dev *pdev)
+{
+	lockdep_assert_held_write(&pci_tsm_rwsem);
+	device_lock_assert(&pdev->dev);
+
+	if (dev_WARN_ONCE(&pdev->dev, pdev->dev.driver,
+			  "unlock attempted on driver attached device\n"))
+		return;
+
+	device_cc_reject(&pdev->dev);
+	to_pci_tsm_ops(pdev->tsm)->unlock(pdev->tsm);
+	pdev->tsm = NULL;
+}
+
+static int pci_tsm_lock(struct pci_dev *pdev, struct tsm_dev *tsm_dev)
+{
+	const struct pci_tsm_ops *ops = tsm_dev->pci_ops;
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
+	tsm = ops->lock(tsm_dev, pdev);
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
+	struct tsm_dev *tsm_dev __free(put_tsm_dev) = find_tsm_dev(id);
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
+	struct tsm_dev *tsm_dev;
+	int rc;
+
+	ACQUIRE(rwsem_read_intr, lock)(&pci_tsm_rwsem);
+	if ((rc = ACQUIRE_ERR(rwsem_read_intr, &lock)))
+		return rc;
+
+	if (!pdev->tsm)
+		return sysfs_emit(buf, "\n");
+
+	tsm_dev = pdev->tsm->tsm_dev;
+	return sysfs_emit(buf, "%s\n", dev_name(&tsm_dev->dev));
+}
+static DEVICE_ATTR_RW(lock);
+
+static ssize_t unlock_store(struct device *dev, struct device_attribute *attr,
+			  const char *buf, size_t len)
+{
+	struct pci_dev *pdev = to_pci_dev(dev);
+	struct tsm_dev *tsm_dev;
+	int rc;
+
+	ACQUIRE(rwsem_write_kill, lock)(&pci_tsm_rwsem);
+	if ((rc = ACQUIRE_ERR(rwsem_write_kill, &lock)))
+		return rc;
+
+	if (!pdev->tsm)
+		return -EINVAL;
+
+	tsm_dev = pdev->tsm->tsm_dev;
+	if (!sysfs_streq(buf, dev_name(&tsm_dev->dev)))
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
@@ -561,6 +701,13 @@ static bool pci_tsm_link_group_visible(struct kobject *kobj)
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
@@ -592,12 +739,19 @@ static umode_t pci_tsm_attr_visible(struct kobject *kobj,
 		}
 	}
 
+	if (pci_tsm_devsec_group_visible(kobj)) {
+		if (attr == &dev_attr_lock.attr ||
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
 
@@ -606,6 +760,8 @@ static struct attribute *pci_tsm_attrs[] = {
 	&dev_attr_disconnect.attr,
 	&dev_attr_bound.attr,
 	&dev_attr_dsm.attr,
+	&dev_attr_lock.attr,
+	&dev_attr_unlock.attr,
 	NULL
 };
 
@@ -734,6 +890,29 @@ int pci_tsm_link_constructor(struct pci_dev *pdev, struct pci_tsm *tsm,
 }
 EXPORT_SYMBOL_GPL(pci_tsm_link_constructor);
 
+/**
+ * pci_tsm_devsec_constructor() - devsec TSM context initialization
+ * @pdev: The PCI device
+ * @tsm: context to initialize
+ * @tsm_dev: Platform TEE Security Manager, initiator of security operations
+ */
+int pci_tsm_devsec_constructor(struct pci_dev *pdev, struct pci_tsm_devsec *tsm,
+			       struct tsm_dev *tsm_dev)
+{
+	struct pci_tsm *pci_tsm = &tsm->base_tsm;
+
+	if (!is_devsec_tsm(tsm_dev))
+		return -EINVAL;
+
+	pci_tsm->dsm_dev = NULL;
+	pci_tsm->tdi = NULL;
+	pci_tsm->pdev = pdev;
+	pci_tsm->tsm_dev = tsm_dev;
+
+	return 0;
+}
+EXPORT_SYMBOL_GPL(pci_tsm_devsec_constructor);
+
 /**
  * pci_tsm_pf0_constructor() - common 'struct pci_tsm_pf0' (DSM) initialization
  * @pdev: Physical Function 0 PCI device (as indicated by is_pci_tsm_pf0())
@@ -761,6 +940,13 @@ void pci_tsm_pf0_destructor(struct pci_tsm_pf0 *pf0_tsm)
 }
 EXPORT_SYMBOL_GPL(pci_tsm_pf0_destructor);
 
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
@@ -782,8 +968,10 @@ int pci_tsm_register(struct tsm_dev *tsm_dev)
 		for_each_pci_dev(pdev)
 			if (is_pci_tsm_pf0(pdev))
 				link_sysfs_enable(pdev);
-	} else if (is_devsec_tsm(tsm_dev)) {
-		pci_tsm_devsec_count++;
+	} else if (is_devsec_tsm(tsm_dev) && pci_tsm_devsec_count++ == 0) {
+		for_each_pci_dev(pdev)
+			if (has_tee(pdev))
+				devsec_sysfs_enable(pdev);
 	}
 
 	return 0;
@@ -818,6 +1006,9 @@ static void __pci_tsm_destroy(struct pci_dev *pdev, struct tsm_dev *tsm_dev)
 	if (is_link_tsm(tsm_dev) && is_pci_tsm_pf0(pdev) && !pci_tsm_link_count)
 		link_sysfs_disable(pdev);
 
+	if (is_devsec_tsm(tsm_dev) && !pci_tsm_devsec_count)
+		sysfs_update_group(&pdev->dev.kobj, &pci_tsm_attr_group);
+
 	/* Nothing else to do if this device never attached to the departing TSM */
 	if (!tsm)
 		return;
@@ -828,10 +1019,18 @@ static void __pci_tsm_destroy(struct pci_dev *pdev, struct tsm_dev *tsm_dev)
 	else if (tsm_dev != tsm->tsm_dev)
 		return;
 
-	if (is_link_tsm(tsm_dev) && is_pci_tsm_pf0(pdev))
-		pci_tsm_disconnect(pdev);
-	else
-		pci_tsm_fn_exit(pdev);
+	/* Disconnect DSMs, unlock assigned TDIs, or cleanup DSM subfunctions */
+	if (is_link_tsm(tsm_dev)) {
+		if (is_pci_tsm_pf0(pdev))
+			pci_tsm_disconnect(pdev);
+		else
+			pci_tsm_fn_exit(pdev);
+	}
+
+	if (is_devsec_tsm(tsm_dev) && has_tee(pdev)) {
+		guard(device)(&pdev->dev);
+		pci_tsm_unlock(pdev);
+	}
 }
 
 void pci_tsm_destroy(struct pci_dev *pdev)
diff --git a/drivers/virt/coco/tsm-core.c b/drivers/virt/coco/tsm-core.c
index 3c99c38cfaa5..231462d60379 100644
--- a/drivers/virt/coco/tsm-core.c
+++ b/drivers/virt/coco/tsm-core.c
@@ -54,6 +54,45 @@ static struct tsm_dev *alloc_tsm_dev(struct device *parent)
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
@@ -70,6 +109,7 @@ static struct tsm_dev *tsm_register_pci_or_reset(struct tsm_dev *tsm_dev,
 		device_unregister(&tsm_dev->dev);
 		return ERR_PTR(rc);
 	}
+	sysfs_update_group(&tsm_dev->dev.kobj, &tsm_pci_group);
 
 	/* Notify TSM userspace that PCI/TSM operations are now possible */
 	kobject_uevent(&tsm_dev->dev.kobj, KOBJ_CHANGE);
@@ -214,6 +254,7 @@ static int __init tsm_init(void)
 	if (IS_ERR(tsm_class))
 		return PTR_ERR(tsm_class);
 
+	tsm_class->dev_groups = tsm_pci_groups;
 	tsm_class->dev_release = tsm_release;
 	return 0;
 }

---

## [8] Dan Williams — 2026-03-02
*Subject: [PATCH v2 07/19] PCI/TSM: Add Device Security (TVM Guest) ACCEPT operation support*

The final operation of the PCIe Trusted Execution Environment (TEE) Device
Interface Security Protocol (TDISP) is asking the TEE Security Manager
(TEE) to enable private DMA and MMIO.

The story so far in the security lifecycle of the device is that the VMM
setup an SPDM session and link encryption with the device's physical
function0. The VMM then assigned either that physical function or other
virtual function of that device to a VM. The VM asked the TSM to transition
the device from TDISP UNLOCKED->LOCKED. With the device LOCKED the VM
validated signed fresh device evidence and expected MMIO mappings.

The VM now accepts the device to transition it from LOCKED to RUN and tell
the TSM to unblock DMA to VM private memory.

Implement a sysfs trigger to flip the device to private operation and plumb
that to a 'struct pci_tsm_ops::accept()' operation.

Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Co-developed-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/pci/Kconfig                     |  2 +
 Documentation/ABI/testing/sysfs-bus-pci | 13 +++++
 include/linux/pci-tsm.h                 |  7 ++-
 drivers/pci/tsm.c                       | 69 ++++++++++++++++++++++++-
 4 files changed, 88 insertions(+), 3 deletions(-)

diff --git a/drivers/pci/Kconfig b/drivers/pci/Kconfig
index e3f848ffb52a..c45c6b978e1d 100644
--- a/drivers/pci/Kconfig
+++ b/drivers/pci/Kconfig
@@ -127,6 +127,8 @@ config PCI_IDE
 
 config PCI_TSM
 	bool "PCI TSM: Device security protocol support"
+	depends on ARCH_HAS_CC_PLATFORM
+	select CONFIDENTIAL_DEVICES
 	select PCI_IDE
 	select PCI_DOE
 	select TSM
diff --git a/Documentation/ABI/testing/sysfs-bus-pci b/Documentation/ABI/testing/sysfs-bus-pci
index 1ed77b9402a6..c2a5c4fe9373 100644
--- a/Documentation/ABI/testing/sysfs-bus-pci
+++ b/Documentation/ABI/testing/sysfs-bus-pci
@@ -732,3 +732,16 @@ Description:
 		'lock' to teardown the connection. Writes fail with EBUSY if
 		this device is bound to a driver. This is a "devsec" TSM
 		attribute, see Documentation/ABI/testing/sysfs-class-tsm.
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
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index 2a896b83bff9..176d214cd0da 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -66,15 +66,18 @@ struct pci_tsm_ops {
 	 *	  pci_tsm') for follow-on security state transitions from the
 	 *	  LOCKED state
 	 * @unlock: destroy TSM context and return device to UNLOCKED state
+	 * @accept: accept a locked TDI for use, move it to RUN state
 	 *
 	 * Context: @lock and @unlock run under pci_tsm_rwsem held for write to
-	 * sync with TSM unregistration and each other. All operations run under
-	 * the device lock for mutual exclusion with driver attach and detach.
+	 * sync with TSM unregistration and each other. @accept runs under
+	 * pci_tsm_rwsem held for read. All operations run under the device lock
+	 * for mutual exclusion with driver attach and detach.
 	 */
 	struct_group_tagged(pci_tsm_devsec_ops, devsec_ops,
 		struct pci_tsm *(*lock)(struct tsm_dev *tsm_dev,
 					struct pci_dev *pdev);
 		void (*unlock)(struct pci_tsm *tsm);
+		int (*accept)(struct pci_dev *pdev);
 	);
 };
 
diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index 259e75092618..aa93a59d2720 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -557,6 +557,71 @@ static ssize_t dsm_show(struct device *dev, struct device_attribute *attr,
 }
 static DEVICE_ATTR_RO(dsm);
 
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
+	rc = to_pci_tsm_ops(pdev->tsm)->accept(pdev);
+	if (rc)
+		return rc;
+
+	return device_cc_accept(&pdev->dev);
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
 /**
  * pci_tsm_unlock() - Transition TDI from LOCKED/RUN to UNLOCKED
  * @pdev: TDI device to unlock
@@ -740,7 +805,8 @@ static umode_t pci_tsm_attr_visible(struct kobject *kobj,
 	}
 
 	if (pci_tsm_devsec_group_visible(kobj)) {
-		if (attr == &dev_attr_lock.attr ||
+		if (attr == &dev_attr_accept.attr ||
+		    attr == &dev_attr_lock.attr ||
 		    attr == &dev_attr_unlock.attr)
 			return attr->mode;
 	}
@@ -760,6 +826,7 @@ static struct attribute *pci_tsm_attrs[] = {
 	&dev_attr_disconnect.attr,
 	&dev_attr_bound.attr,
 	&dev_attr_dsm.attr,
+	&dev_attr_accept.attr,
 	&dev_attr_lock.attr,
 	&dev_attr_unlock.attr,
 	NULL

---

## [9] Dan Williams — 2026-03-02
*Subject: [PATCH v2 08/19] PCI/TSM: Add "evidence" support*

Once one accepts the threat model that devices may be adversarial the
process of establishing trust in the device identity, the integrity +
confidentiality of its link, and the integrity + confidentiality of its
MMIO interface requires multiple evidence objects from the device. The
device's certificate chain, measurements and interface report need to be
retrieved by the host, validated by the TSM and transmitted to the guest
all while mitigating TOCTOU races.

All TSM implementations share the same fundamental objects, but vary in how
the TSM conveys its trust in the objects. Some TSM implementations expect
the full documents to be conveyed over untrustworthy channels while the TSM
securely conveys a digest. Others transmit full objects with signed SPDM
transcripts of requester provided nonces. Some offer a single transcript
to convey the version, capabilities, and algorithms (VCA) data and
measurements in one blob while others split VCA as a separate signed blob.

Introduce a netlink interface to dump all these objects in a common way
across TSM implementations and across host and guest environments.
Userspace is responsible for handling the variance of "TSM provides combo
measurements + VCA + nonce + signature, vs TSM provides a digest over a
secure channel of the same".

The implementation adheres to the guideline from:
Documentation/userspace-api/netlink/genetlink-legacy.rst

    New Netlink families should never respond to a DO operation with
    multiple replies, with ``NLM_F_MULTI`` set. Use a filtered dump
    instead.

Per SPDM, transcripts may grow to be 16MB in size. Large PCI/TSM netlink
blobs are handled via a sequence of dump messages that userspace must
concatenate.

Cc: Donald Hunter <donald.hunter@gmail.com>
Cc: Jakub Kicinski <kuba@kernel.org>
Cc: Bjorn Helgaas <bhelgaas@google.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: "Aneesh Kumar K.V (Arm)" <aneesh.kumar@kernel.org>
Cc: Alexey Kardashevskiy <aik@amd.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/pci/Makefile                     |   2 +-
 drivers/pci/tsm/Makefile                 |   9 +
 Documentation/netlink/specs/pci-tsm.yaml | 151 +++++++++++++
 drivers/pci/tsm/netlink.h                |  23 ++
 include/linux/pci-tsm.h                  |  63 ++++++
 include/uapi/linux/pci-tsm-netlink.h     | 101 +++++++++
 drivers/pci/{tsm.c => tsm/core.c}        |  17 +-
 drivers/pci/tsm/evidence.c               | 274 +++++++++++++++++++++++
 drivers/pci/tsm/netlink.c                |  43 ++++
 MAINTAINERS                              |   4 +-
 10 files changed, 682 insertions(+), 5 deletions(-)
 create mode 100644 drivers/pci/tsm/Makefile
 create mode 100644 Documentation/netlink/specs/pci-tsm.yaml
 create mode 100644 drivers/pci/tsm/netlink.h
 create mode 100644 include/uapi/linux/pci-tsm-netlink.h
 rename drivers/pci/{tsm.c => tsm/core.c} (98%)
 create mode 100644 drivers/pci/tsm/evidence.c
 create mode 100644 drivers/pci/tsm/netlink.c

diff --git a/drivers/pci/Makefile b/drivers/pci/Makefile
index e10cfe5a280b..31f5095360af 100644
--- a/drivers/pci/Makefile
+++ b/drivers/pci/Makefile
@@ -35,7 +35,7 @@ obj-$(CONFIG_XEN_PCIDEV_FRONTEND) += xen-pcifront.o
 obj-$(CONFIG_VGA_ARB)		+= vgaarb.o
 obj-$(CONFIG_PCI_DOE)		+= doe.o
 obj-$(CONFIG_PCI_IDE)		+= ide.o
-obj-$(CONFIG_PCI_TSM)		+= tsm.o
+obj-$(CONFIG_PCI_TSM)		+= tsm/
 obj-$(CONFIG_PCI_DYNAMIC_OF_NODES) += of_property.o
 obj-$(CONFIG_PCI_NPEM)		+= npem.o
 obj-$(CONFIG_PCIE_TPH)		+= tph.o
diff --git a/drivers/pci/tsm/Makefile b/drivers/pci/tsm/Makefile
new file mode 100644
index 000000000000..afa775224b8d
--- /dev/null
+++ b/drivers/pci/tsm/Makefile
@@ -0,0 +1,9 @@
+# SPDX-License-Identifier: GPL-2.0
+#
+# Makefile for the PCI/TSM infrastructure
+
+obj-$(CONFIG_PCI_TSM) += tsm.o
+
+tsm-y := core.o
+tsm-$(CONFIG_NET) += netlink.o
+tsm-$(CONFIG_NET) += evidence.o
diff --git a/Documentation/netlink/specs/pci-tsm.yaml b/Documentation/netlink/specs/pci-tsm.yaml
new file mode 100644
index 000000000000..eb7fc03bd705
--- /dev/null
+++ b/Documentation/netlink/specs/pci-tsm.yaml
@@ -0,0 +1,151 @@
+# SPDX-License-Identifier: ((GPL-2.0 WITH Linux-syscall-note) OR BSD-3-Clause)
+#
+---
+name: pci-tsm
+protocol: genetlink
+uapi-header: linux/pci-tsm-netlink.h
+doc: PCI TSM Evidence retrieval over generic netlink
+
+definitions:
+  -
+    type: const
+    name: max-object-size
+    value: 0x01000000
+  -
+    type: const
+    name: max-nonce-size
+    value: 256
+  -
+    type: const
+    name: max-obj-type
+    value: 4
+  -
+    name: evidence-type
+    type: enum
+    doc: PCI device security evidence objects
+    entries:
+      -
+        name: cert0
+        doc: SPDM certificate chain from device slot0
+      -
+        name: cert1
+        doc: SPDM certificate chain from device slot1
+      -
+        name: cert2
+        doc: SPDM certificate chain from device slot2
+      -
+        name: cert3
+        doc: SPDM certificate chain from device slot3
+      -
+        name: cert4
+        doc: SPDM certificate chain from device slot4
+      -
+        name: cert5
+        doc: SPDM certificate chain from device slot5
+      -
+        name: cert6
+        doc: SPDM certificate chain from device slot6
+      -
+        name: cert7
+        doc: SPDM certificate chain from device slot7
+      -
+        name: vca
+        doc: SPDM transcript of version, capabilities, and algorithms negotiation
+      -
+        name: measurements
+        doc: SPDM GET_MEASUREMENTS response
+      -
+        name: report
+        doc: TDISP GET_DEVICE_INTERFACE_REPORT response
+
+    render-max: true
+  -
+    name: evidence-type-flag
+    type: flags
+    doc: PCI device security evidence request flags
+    render-max: true
+    # NOTE! these values must match the name and order of evidence-type
+    entries:
+      -
+        name: cert0
+      -
+        name: cert1
+      -
+        name: cert2
+      -
+        name: cert3
+      -
+        name: cert4
+      -
+        name: cert5
+      -
+        name: cert6
+      -
+        name: cert7
+      -
+        name: vca
+      -
+        name: measurements
+      -
+        name: report
+  -
+    name: evidence-flag
+    type: flags
+    render-max: true
+    doc: Flags to control evidence retrieval
+    entries:
+      -
+        name: digest
+        doc: Request the TSM's private digest of an evidence object
+
+attribute-sets:
+  -
+    name: evidence-object
+    attributes:
+      -
+        name: type
+        type: u32
+        doc: evidence type-id
+      -
+        name: type-mask
+        type: u32
+        doc: evidence types as a flag mask
+      -
+        name: flags
+        type: u32
+        doc: evidence modifier flags like 'request TSM digest'
+      -
+        name: dev-name
+        type: string
+        doc: PCI device name
+      -
+        name: nonce
+        type: binary
+        checks:
+          max-len: max-nonce-size
+      -
+        name: val
+        type: binary
+        checks:
+          max-len: max-obj-size
+
+operations:
+  list:
+    -
+      name: evidence-read
+      doc: Read the PCI TSM objects of a given type mask
+      attribute-set: evidence-object
+      flags: [admin-perm]
+      dump:
+        pre: pci-tsm-nl-evidence-read-pre
+        post: pci-tsm-nl-evidence-read-post
+        request:
+          attributes:
+            - type-mask
+            - flags
+            - dev-name
+            - nonce
+        reply:
+          attributes:
+            - type
+            - val
diff --git a/drivers/pci/tsm/netlink.h b/drivers/pci/tsm/netlink.h
new file mode 100644
index 000000000000..34f3fb6ba2b7
--- /dev/null
+++ b/drivers/pci/tsm/netlink.h
@@ -0,0 +1,23 @@
+/* SPDX-License-Identifier: ((GPL-2.0 WITH Linux-syscall-note) OR BSD-3-Clause) */
+/* Do not edit directly, auto-generated from: */
+/*	Documentation/netlink/specs/pci-tsm.yaml */
+/* YNL-GEN kernel header */
+/* To regenerate run: tools/net/ynl/ynl-regen.sh */
+
+#ifndef _LINUX_PCI_TSM_GEN_H
+#define _LINUX_PCI_TSM_GEN_H
+
+#include <net/netlink.h>
+#include <net/genetlink.h>
+
+#include <uapi/linux/pci-tsm-netlink.h>
+
+int pci_tsm_nl_evidence_read_pre(struct netlink_callback *cb);
+int pci_tsm_nl_evidence_read_post(struct netlink_callback *cb);
+
+int pci_tsm_nl_evidence_read_dumpit(struct sk_buff *skb,
+				    struct netlink_callback *cb);
+
+extern struct genl_family pci_tsm_nl_family;
+
+#endif /* _LINUX_PCI_TSM_GEN_H */
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index 176d214cd0da..b70b4c0457c4 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -3,7 +3,10 @@
 #define __PCI_TSM_H
 #include <linux/mutex.h>
 #include <linux/pci.h>
+#include <linux/rwsem.h>
 #include <linux/sockptr.h>
+#include <uapi/linux/hash_info.h>
+#include <uapi/linux/pci-tsm-netlink.h>
 
 struct pci_tsm;
 struct tsm_dev;
@@ -79,6 +82,11 @@ struct pci_tsm_ops {
 		void (*unlock)(struct pci_tsm *tsm);
 		int (*accept)(struct pci_dev *pdev);
 	);
+
+	int (*refresh_evidence)(struct pci_tsm *tsm,
+				enum pci_tsm_evidence_type type,
+				unsigned long flags, void *nonce,
+				size_t nonce_len);
 };
 
 /**
@@ -93,6 +101,52 @@ struct pci_tdi {
 	u32 tdi_id;
 };
 
+/**
+ * struct pci_tsm_evidence_object - General PCI/TSM blob descriptor
+ * @data: pointer to the evidence data blob
+ * @len: length of the evidence data blob
+ * @digest: TSM expected digest of the data blob
+ *
+ * There are multiple population and verification models for these blobs
+ * depending on TSM policy. Some examples:
+ * 1/ Host (link) TSM: populates certs and provides a device signed measurement
+ *    transcript PCI_TSM_EVIDENCE_TYPE_MEASUREMENTS
+ * 2/ Guest (devsec) TSM: receives untrusted blobs via guest-to-host shared
+ *    memory protocol and then requests digests of the same via guest-to-host
+ *    encrypted protocol.
+ * The expectation is that all of these blobs are received in an SPDM session
+ * with a signed transcript, however not all TSMs provide the full transcript of
+ * these objects' retrieval and instead require asking the TSM for cached
+ * digests of the blobs over trusted TSM channels.
+ */
+struct pci_tsm_evidence_object {
+	void *data;
+	size_t len;
+	void *digest;
+};
+
+/**
+ * struct pci_tsm_evidence - Retrieved evidence for SPDM session GET commands
+ * @slot: certificate slot used by a link TSM for connect.
+ * @generation: refresh_evidence() invocation detection
+ * @digest_algo: payload size of PCI_TSM_EVIDENCE_FLAG_DIGEST requests
+ * @lock: synchronize dumps vs refresh_evidence()
+ * @obj: array of evidence objects a TSM might populate
+ *
+ * Note @slot selection not applicable for devsec TSMs. By the time the guest is
+ * retrieving the device's certificates the choice of slot was long since
+ * decided by the corresponding link TSM.
+ *
+ * An increment of @generation causes in flight dumps to fail with -EAGAIN.
+ */
+struct pci_tsm_evidence {
+	int slot;
+	int generation;
+	enum hash_algo digest_algo;
+	struct rw_semaphore lock;
+	struct pci_tsm_evidence_object obj[PCI_TSM_EVIDENCE_TYPE_MAX + 1];
+};
+
 /**
  * struct pci_tsm - Core TSM context for a given PCIe endpoint
  * @pdev: Back ref to device function, distinguishes type of pci_tsm context
@@ -100,6 +154,8 @@ struct pci_tdi {
  * @tsm_dev: PCI TEE Security Manager device for Link Confidentiality or Device
  *	     Function Security operations
  * @tdi: TDI context established by the @bind link operation
+ * @evidence: cached evidence from SPDM session establishment (connect), or
+ *	      TDISP bind (lock)
  *
  * This structure is wrapped by low level TSM driver data and returned by
  * probe()/lock(), it is freed by the corresponding remove()/unlock().
@@ -123,6 +179,7 @@ struct pci_tsm {
 	struct pci_dev *dsm_dev;
 	struct tsm_dev *tsm_dev;
 	struct pci_tdi *tdi;
+	struct pci_tsm_evidence evidence;
 };
 
 /**
@@ -238,6 +295,8 @@ ssize_t pci_tsm_guest_req(struct pci_dev *pdev, enum pci_tsm_req_scope scope,
 			  sockptr_t req_in, size_t in_len, sockptr_t req_out,
 			  size_t out_len, u64 *tsm_code);
 struct pci_tsm_devsec *to_pci_tsm_devsec(struct pci_tsm *tsm);
+void pci_tsm_init_evidence(struct pci_tsm_evidence *evidence, int slot,
+			   enum hash_algo digest_algo);
 #else
 static inline int pci_tsm_register(struct tsm_dev *tsm_dev)
 {
@@ -262,4 +321,8 @@ static inline ssize_t pci_tsm_guest_req(struct pci_dev *pdev,
 	return -ENXIO;
 }
 #endif
+
+/* private: */
+extern struct rw_semaphore pci_tsm_rwsem;
+
 #endif /*__PCI_TSM_H */
diff --git a/include/uapi/linux/pci-tsm-netlink.h b/include/uapi/linux/pci-tsm-netlink.h
new file mode 100644
index 000000000000..a0e8b044e1b8
--- /dev/null
+++ b/include/uapi/linux/pci-tsm-netlink.h
@@ -0,0 +1,101 @@
+/* SPDX-License-Identifier: ((GPL-2.0 WITH Linux-syscall-note) OR BSD-3-Clause) */
+/* Do not edit directly, auto-generated from: */
+/*	Documentation/netlink/specs/pci-tsm.yaml */
+/* YNL-GEN uapi header */
+/* To regenerate run: tools/net/ynl/ynl-regen.sh */
+
+#ifndef _UAPI_LINUX_PCI_TSM_NETLINK_H
+#define _UAPI_LINUX_PCI_TSM_NETLINK_H
+
+#define PCI_TSM_FAMILY_NAME	"pci-tsm"
+#define PCI_TSM_FAMILY_VERSION	1
+
+#define PCI_TSM_MAX_OBJECT_SIZE	16777216
+#define PCI_TSM_MAX_NONCE_SIZE	256
+#define PCI_TSM_MAX_OBJ_TYPE	4
+
+/**
+ * enum pci_tsm_evidence_type - PCI device security evidence objects
+ * @PCI_TSM_EVIDENCE_TYPE_CERT0: SPDM certificate chain from device slot0
+ * @PCI_TSM_EVIDENCE_TYPE_CERT1: SPDM certificate chain from device slot1
+ * @PCI_TSM_EVIDENCE_TYPE_CERT2: SPDM certificate chain from device slot2
+ * @PCI_TSM_EVIDENCE_TYPE_CERT3: SPDM certificate chain from device slot3
+ * @PCI_TSM_EVIDENCE_TYPE_CERT4: SPDM certificate chain from device slot4
+ * @PCI_TSM_EVIDENCE_TYPE_CERT5: SPDM certificate chain from device slot5
+ * @PCI_TSM_EVIDENCE_TYPE_CERT6: SPDM certificate chain from device slot6
+ * @PCI_TSM_EVIDENCE_TYPE_CERT7: SPDM certificate chain from device slot7
+ * @PCI_TSM_EVIDENCE_TYPE_VCA: SPDM transcript of version, capabilities, and
+ *   algorithms negotiation
+ * @PCI_TSM_EVIDENCE_TYPE_MEASUREMENTS: SPDM GET_MEASUREMENTS response
+ * @PCI_TSM_EVIDENCE_TYPE_REPORT: TDISP GET_DEVICE_INTERFACE_REPORT response
+ */
+enum pci_tsm_evidence_type {
+	PCI_TSM_EVIDENCE_TYPE_CERT0,
+	PCI_TSM_EVIDENCE_TYPE_CERT1,
+	PCI_TSM_EVIDENCE_TYPE_CERT2,
+	PCI_TSM_EVIDENCE_TYPE_CERT3,
+	PCI_TSM_EVIDENCE_TYPE_CERT4,
+	PCI_TSM_EVIDENCE_TYPE_CERT5,
+	PCI_TSM_EVIDENCE_TYPE_CERT6,
+	PCI_TSM_EVIDENCE_TYPE_CERT7,
+	PCI_TSM_EVIDENCE_TYPE_VCA,
+	PCI_TSM_EVIDENCE_TYPE_MEASUREMENTS,
+	PCI_TSM_EVIDENCE_TYPE_REPORT,
+
+	/* private: */
+	__PCI_TSM_EVIDENCE_TYPE_MAX,
+	PCI_TSM_EVIDENCE_TYPE_MAX = (__PCI_TSM_EVIDENCE_TYPE_MAX - 1)
+};
+
+/*
+ * PCI device security evidence request flags
+ */
+enum pci_tsm_evidence_type_flag {
+	PCI_TSM_EVIDENCE_TYPE_FLAG_CERT0 = 1,
+	PCI_TSM_EVIDENCE_TYPE_FLAG_CERT1 = 2,
+	PCI_TSM_EVIDENCE_TYPE_FLAG_CERT2 = 4,
+	PCI_TSM_EVIDENCE_TYPE_FLAG_CERT3 = 8,
+	PCI_TSM_EVIDENCE_TYPE_FLAG_CERT4 = 16,
+	PCI_TSM_EVIDENCE_TYPE_FLAG_CERT5 = 32,
+	PCI_TSM_EVIDENCE_TYPE_FLAG_CERT6 = 64,
+	PCI_TSM_EVIDENCE_TYPE_FLAG_CERT7 = 128,
+	PCI_TSM_EVIDENCE_TYPE_FLAG_VCA = 256,
+	PCI_TSM_EVIDENCE_TYPE_FLAG_MEASUREMENTS = 512,
+	PCI_TSM_EVIDENCE_TYPE_FLAG_REPORT = 1024,
+
+	/* private: */
+	PCI_TSM_EVIDENCE_TYPE_FLAG_MASK = 2047,
+};
+
+/**
+ * enum pci_tsm_evidence_flag - Flags to control evidence retrieval
+ * @PCI_TSM_EVIDENCE_FLAG_DIGEST: Request the TSM's private digest of an
+ *   evidence object
+ */
+enum pci_tsm_evidence_flag {
+	PCI_TSM_EVIDENCE_FLAG_DIGEST = 1,
+
+	/* private: */
+	PCI_TSM_EVIDENCE_FLAG_MASK = 1,
+};
+
+enum {
+	PCI_TSM_A_EVIDENCE_OBJECT_TYPE = 1,
+	PCI_TSM_A_EVIDENCE_OBJECT_TYPE_MASK,
+	PCI_TSM_A_EVIDENCE_OBJECT_FLAGS,
+	PCI_TSM_A_EVIDENCE_OBJECT_DEV_NAME,
+	PCI_TSM_A_EVIDENCE_OBJECT_NONCE,
+	PCI_TSM_A_EVIDENCE_OBJECT_VAL,
+
+	__PCI_TSM_A_EVIDENCE_OBJECT_MAX,
+	PCI_TSM_A_EVIDENCE_OBJECT_MAX = (__PCI_TSM_A_EVIDENCE_OBJECT_MAX - 1)
+};
+
+enum {
+	PCI_TSM_CMD_EVIDENCE_READ = 1,
+
+	__PCI_TSM_CMD_MAX,
+	PCI_TSM_CMD_MAX = (__PCI_TSM_CMD_MAX - 1)
+};
+
+#endif /* _UAPI_LINUX_PCI_TSM_NETLINK_H */
diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm/core.c
similarity index 98%
rename from drivers/pci/tsm.c
rename to drivers/pci/tsm/core.c
index aa93a59d2720..039733fd19b1 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm/core.c
@@ -3,7 +3,7 @@
  * Interface with platform TEE Security Manager (TSM) objects as defined by
  * PCIe r7.0 section 11 TEE Device Interface Security Protocol (TDISP)
  *
- * Copyright(c) 2024-2025 Intel Corporation. All rights reserved.
+ * Copyright (C) 2024-2026 Intel Corporation
  */
 
 #define dev_fmt(fmt) "PCI/TSM: " fmt
@@ -16,13 +16,13 @@
 #include <linux/sysfs.h>
 #include <linux/tsm.h>
 #include <linux/xarray.h>
-#include "pci.h"
+#include "../pci.h"
 
 /*
  * Provide a read/write lock against the init / exit of pdev tsm
  * capabilities and arrival/departure of a TSM instance
  */
-static DECLARE_RWSEM(pci_tsm_rwsem);
+DECLARE_RWSEM(pci_tsm_rwsem);
 
 /*
  * Count of TSMs registered that support physical link operations vs device
@@ -302,6 +302,7 @@ static ssize_t connect_store(struct device *dev, struct device_attribute *attr,
 	rc = pci_tsm_connect(pdev, tsm_dev);
 	if (rc)
 		return rc;
+
 	return len;
 }
 static DEVICE_ATTR_RW(connect);
@@ -933,6 +934,16 @@ void pci_tsm_tdi_constructor(struct pci_dev *pdev, struct pci_tdi *tdi,
 }
 EXPORT_SYMBOL_GPL(pci_tsm_tdi_constructor);
 
+void pci_tsm_init_evidence(struct pci_tsm_evidence *evidence, int slot,
+			   enum hash_algo digest_algo)
+{
+	evidence->slot = slot;
+	evidence->generation = 1;
+	evidence->digest_algo = digest_algo;
+	init_rwsem(&evidence->lock);
+}
+EXPORT_SYMBOL_GPL(pci_tsm_init_evidence);
+
 /**
  * pci_tsm_link_constructor() - base 'struct pci_tsm' initialization for link TSMs
  * @pdev: The PCI device
diff --git a/drivers/pci/tsm/evidence.c b/drivers/pci/tsm/evidence.c
new file mode 100644
index 000000000000..4d475b3dd6f6
--- /dev/null
+++ b/drivers/pci/tsm/evidence.c
@@ -0,0 +1,274 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright (C) 2026 Intel Corporation */
+
+#include <crypto/hash_info.h>
+#include <linux/bitfield.h>
+#include <linux/init.h>
+#include <linux/kernel.h>
+#include <linux/module.h>
+#include <linux/netlink.h>
+#include <linux/pci.h>
+#include <linux/pci-tsm.h>
+#include <linux/slab.h>
+#include <net/genetlink.h>
+#include <net/netlink.h>
+
+#include "netlink.h"
+
+struct pci_tsm_evidence_ctx {
+	struct pci_dev *pdev;
+	unsigned long type_mask;
+	unsigned long flags;
+	void *nonce;
+	int generation;
+	int type;
+	u32 offset;
+	u16 nonce_len;
+};
+
+#define PCI_TSM_EVIDENCE_START U32_MAX
+#define PCI_TSM_EVIDENCE_OBJECT_START (U32_MAX - 1)
+int pci_tsm_nl_evidence_read_pre(struct netlink_callback *cb)
+{
+	struct pci_tsm_evidence_ctx *ctx = (struct pci_tsm_evidence_ctx *)cb->ctx;
+	const struct genl_info *info = genl_info_dump(cb);
+	unsigned long type_mask_unknown;
+	struct nlattr *attr;
+	struct device *dev;
+	char name[32];
+
+	NL_ASSERT_CTX_FITS(struct pci_tsm_evidence_ctx);
+
+	if (GENL_REQ_ATTR_CHECK(info, PCI_TSM_A_EVIDENCE_OBJECT_TYPE_MASK)) {
+		NL_SET_ERR_MSG(info->extack, "missing object request mask");
+		return -EINVAL;
+	}
+
+	attr = info->attrs[PCI_TSM_A_EVIDENCE_OBJECT_TYPE_MASK];
+	ctx->type_mask = nla_get_u32(attr);
+	type_mask_unknown = ctx->type_mask & ~PCI_TSM_EVIDENCE_TYPE_FLAG_MASK;
+	if (type_mask_unknown) {
+		NL_SET_ERR_MSG_FMT(info->extack,
+				   "unsupported object request %#lx",
+				   type_mask_unknown);
+		return -EINVAL;
+	}
+
+	attr = info->attrs[PCI_TSM_A_EVIDENCE_OBJECT_FLAGS];
+	if (attr) {
+		ctx->flags = nla_get_u32(attr);
+		if (ctx->flags & ~PCI_TSM_EVIDENCE_FLAG_MASK) {
+			NL_SET_BAD_ATTR(info->extack, attr);
+			return -EINVAL;
+		}
+	}
+
+	if (GENL_REQ_ATTR_CHECK(info, PCI_TSM_A_EVIDENCE_OBJECT_DEV_NAME)) {
+		NL_SET_ERR_MSG(info->extack, "missing device name");
+		return -EINVAL;
+	}
+
+	attr = info->attrs[PCI_TSM_A_EVIDENCE_OBJECT_DEV_NAME];
+	if (nla_strscpy(name, attr, sizeof(name)) < 0) {
+		NL_SET_BAD_ATTR(info->extack, attr);
+		return -EINVAL;
+	}
+
+	dev = bus_find_device_by_name(&pci_bus_type, NULL, name);
+	if (!dev) {
+		NL_SET_ERR_MSG_FMT(info->extack, "device '%s' not found", name);
+		return -ENODEV;
+	}
+	ctx->pdev = to_pci_dev(dev);
+
+	ctx->type =
+		find_first_bit(&ctx->type_mask, PCI_TSM_EVIDENCE_TYPE_MAX + 1);
+	if (ctx->type > PCI_TSM_EVIDENCE_TYPE_MAX) {
+		NL_SET_ERR_MSG(info->extack, "no evidence type requested");
+		return -EINVAL;
+	}
+	ctx->offset = PCI_TSM_EVIDENCE_START;
+
+	return 0;
+}
+
+int pci_tsm_nl_evidence_read_post(struct netlink_callback *cb)
+{
+	struct pci_tsm_evidence_ctx *ctx =
+		(struct pci_tsm_evidence_ctx *)cb->ctx;
+
+	pci_dev_put(ctx->pdev);
+	return 0;
+}
+
+static size_t evidence_len(struct pci_tsm_evidence *evidence,
+			   struct pci_tsm_evidence_object *obj,
+			   unsigned long flags)
+{
+	if (flags & PCI_TSM_EVIDENCE_FLAG_DIGEST) {
+		if (obj->digest)
+			return hash_digest_size[evidence->digest_algo];
+		return 0;
+	}
+	return obj->len;
+}
+
+static void *evidence_data(struct pci_tsm_evidence_object *obj,
+			   unsigned long flags)
+{
+	if (flags & PCI_TSM_EVIDENCE_FLAG_DIGEST)
+		return obj->digest;
+	return obj->data;
+}
+
+static int __pci_tsm_evidence_read(struct sk_buff *skb,
+				   struct netlink_callback *cb)
+{
+	struct pci_tsm_evidence_ctx *ctx =
+		(struct pci_tsm_evidence_ctx *)cb->ctx;
+	struct pci_dev *pdev = ctx->pdev;
+	struct pci_tsm_evidence *evidence = &pdev->tsm->evidence;
+	struct pci_tsm_evidence_object *obj = &evidence->obj[ctx->type];
+	size_t object_len = evidence_len(evidence, obj, ctx->flags);
+	void *object_data = evidence_data(obj, ctx->flags);
+	size_t available, overhead, len;
+	void *hdr;
+	int rc;
+
+	hdr = genlmsg_put(skb, NETLINK_CB(cb->skb).portid, cb->nlh->nlmsg_seq,
+			  &pci_tsm_nl_family, NLM_F_MULTI,
+			  PCI_TSM_CMD_EVIDENCE_READ);
+	if (!hdr)
+		return -EMSGSIZE;
+
+	if (ctx->offset == PCI_TSM_EVIDENCE_OBJECT_START) {
+		rc = nla_put_u32(skb, PCI_TSM_A_EVIDENCE_OBJECT_TYPE,
+				 ctx->type);
+		if (rc)
+			goto out_cancel;
+		ctx->offset = 0;
+	}
+
+	available = skb_tailroom(skb);
+	overhead = nla_total_size(0) + NLA_ALIGNTO;
+	if (available <= overhead) {
+		rc = -EMSGSIZE;
+		goto out_cancel;
+	}
+
+	if (object_len)
+		len = min(available - overhead, object_len - ctx->offset);
+	else
+		len = 0;
+
+	rc = nla_put(skb, PCI_TSM_A_EVIDENCE_OBJECT_VAL, len,
+		     object_data + ctx->offset);
+	if (rc)
+		goto out_end;
+
+	ctx->offset += len;
+	if (ctx->offset < object_len) {
+		rc = 1;
+		goto out_end;
+	}
+
+	ctx->type = find_next_bit(&ctx->type_mask,
+				  PCI_TSM_EVIDENCE_TYPE_MAX + 1, ctx->type + 1);
+	/* no more evidence types requested */
+	if (ctx->type > PCI_TSM_EVIDENCE_TYPE_MAX) {
+		rc = 0;
+		goto out_end;
+	}
+	ctx->offset = PCI_TSM_EVIDENCE_OBJECT_START;
+	rc = 1;
+
+out_end:
+	genlmsg_end(skb, hdr);
+	if (rc > 0)
+		return skb->len;
+	return rc;
+
+out_cancel:
+	genlmsg_cancel(skb, hdr);
+	return rc;
+}
+
+static int pci_tsm_evidence_read(struct sk_buff *skb,
+				 struct netlink_callback *cb)
+{
+	struct pci_tsm_evidence_ctx *ctx =
+		(struct pci_tsm_evidence_ctx *)cb->ctx;
+	const struct genl_info *info = genl_info_dump(cb);
+	struct pci_tsm_evidence *evidence;
+	struct pci_dev *pdev = ctx->pdev;
+	int rc;
+
+	ACQUIRE(rwsem_read_intr, tsm_lock)(&pci_tsm_rwsem);
+	if ((rc = ACQUIRE_ERR(rwsem_read_intr, &tsm_lock))) {
+		NL_SET_ERR_MSG(info->extack,
+			       "interrupted acquiring TSM context");
+		return rc;
+	}
+
+	if (!pdev->tsm) {
+		NL_SET_ERR_MSG(info->extack, "no TSM context");
+		return -ENXIO;
+	}
+
+	evidence = &pdev->tsm->evidence;
+	ACQUIRE(rwsem_read_intr, evidence_lock)(&evidence->lock);
+	if ((rc = ACQUIRE_ERR(rwsem_read_intr, &evidence_lock))) {
+		NL_SET_ERR_MSG(info->extack, "interrupted acquiring evidence");
+		return rc;
+	}
+
+	/* generation is only valid when non-zero */
+	if (ctx->offset == PCI_TSM_EVIDENCE_START) {
+		if (!evidence->generation) {
+			NL_SET_ERR_MSG(info->extack, "no evidence available");
+			return -ENXIO;
+		}
+		ctx->generation = evidence->generation;
+		ctx->offset = PCI_TSM_EVIDENCE_OBJECT_START;
+	}
+
+	if (ctx->generation != evidence->generation) {
+		NL_SET_ERR_MSG(info->extack, "evidence updated during read");
+		return -EAGAIN;
+	}
+
+	return __pci_tsm_evidence_read(skb, cb);
+}
+
+static int pci_tsm_evidence_refresh(struct pci_tsm_evidence_ctx *ctx)
+{
+	return -EOPNOTSUPP;
+}
+
+int pci_tsm_nl_evidence_read_dumpit(struct sk_buff *skb,
+				    struct netlink_callback *cb)
+{
+	struct pci_tsm_evidence_ctx *ctx =
+		(struct pci_tsm_evidence_ctx *)cb->ctx;
+	const struct genl_info *info = genl_info_dump(cb);
+
+	/* Attempt one refresh per dump request before reading */
+	if (ctx->offset == PCI_TSM_EVIDENCE_START && ctx->nonce) {
+		int rc = pci_tsm_evidence_refresh(ctx);
+
+		if (rc) {
+			NL_SET_ERR_MSG_FMT(info->extack,
+					   "evidence refresh failed: %d", rc);
+			return rc;
+		}
+		ctx->nonce = NULL;
+	}
+	return pci_tsm_evidence_read(skb, cb);
+}
+
+static int __init pci_tsm_nl_init(void)
+{
+	return genl_register_family(&pci_tsm_nl_family);
+}
+
+subsys_initcall(pci_tsm_nl_init);
diff --git a/drivers/pci/tsm/netlink.c b/drivers/pci/tsm/netlink.c
new file mode 100644
index 000000000000..26fadb727666
--- /dev/null
+++ b/drivers/pci/tsm/netlink.c
@@ -0,0 +1,43 @@
+// SPDX-License-Identifier: ((GPL-2.0 WITH Linux-syscall-note) OR BSD-3-Clause)
+/* Do not edit directly, auto-generated from: */
+/*	Documentation/netlink/specs/pci-tsm.yaml */
+/* YNL-GEN kernel source */
+/* To regenerate run: tools/net/ynl/ynl-regen.sh */
+
+#include <net/netlink.h>
+#include <net/genetlink.h>
+
+#include "netlink.h"
+
+#include <uapi/linux/pci-tsm-netlink.h>
+
+/* PCI_TSM_CMD_EVIDENCE_READ - dump */
+static const struct nla_policy pci_tsm_evidence_read_nl_policy[PCI_TSM_A_EVIDENCE_OBJECT_NONCE + 1] = {
+	[PCI_TSM_A_EVIDENCE_OBJECT_TYPE_MASK] = { .type = NLA_U32, },
+	[PCI_TSM_A_EVIDENCE_OBJECT_FLAGS] = { .type = NLA_U32, },
+	[PCI_TSM_A_EVIDENCE_OBJECT_DEV_NAME] = { .type = NLA_NUL_STRING, },
+	[PCI_TSM_A_EVIDENCE_OBJECT_NONCE] = NLA_POLICY_MAX_LEN(PCI_TSM_MAX_NONCE_SIZE),
+};
+
+/* Ops table for pci_tsm */
+static const struct genl_split_ops pci_tsm_nl_ops[] = {
+	{
+		.cmd		= PCI_TSM_CMD_EVIDENCE_READ,
+		.start		= pci_tsm_nl_evidence_read_pre,
+		.dumpit		= pci_tsm_nl_evidence_read_dumpit,
+		.done		= pci_tsm_nl_evidence_read_post,
+		.policy		= pci_tsm_evidence_read_nl_policy,
+		.maxattr	= PCI_TSM_A_EVIDENCE_OBJECT_NONCE,
+		.flags		= GENL_ADMIN_PERM | GENL_CMD_CAP_DUMP,
+	},
+};
+
+struct genl_family pci_tsm_nl_family __ro_after_init = {
+	.name		= PCI_TSM_FAMILY_NAME,
+	.version	= PCI_TSM_FAMILY_VERSION,
+	.netnsok	= true,
+	.parallel_ops	= true,
+	.module		= THIS_MODULE,
+	.split_ops	= pci_tsm_nl_ops,
+	.n_split_ops	= ARRAY_SIZE(pci_tsm_nl_ops),
+};
diff --git a/MAINTAINERS b/MAINTAINERS
index da9dbc1a4019..3d5e2cbef71e 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -26534,9 +26534,11 @@ S:	Maintained
 F:	Documentation/ABI/testing/configfs-tsm-report
 F:	Documentation/driver-api/coco/
 F:	Documentation/driver-api/pci/tsm.rst
-F:	drivers/pci/tsm.c
+F:	Documentation/netlink/specs/pci-tsm.yaml
+F:	drivers/pci/tsm/
 F:	drivers/virt/coco/guest/
 F:	include/linux/*tsm*.h
+F:	include/uapi/linux/pci-tsm-netlink.h
 F:	samples/tsm-mr/
 
 TRUSTED SERVICES TEE DRIVER

---

## [10] Dan Williams — 2026-03-02
*Subject: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO descriptors via TDISP Report*

After pci_tsm_bind() and pci_tsm_lock() the low level TSM driver is
expected to populate PCI_TSM_EVIDENCE_TYPE_REPORT in its evidence store.
This report is defined by the TDISP GET_DEVICE_INTERFACE_REPORT response
payload.

Add a helper to create encrypted MMIO descriptors from that report
data. With those descriptors the TSM driver can use pci_tsm_mmio_setup() to
inform ioremap() how to map the device per the device's expectations. The
VM is expected to validate the interface with the relying party before
accepting the device for operation.

The helper also provides the obfuscated starting address for each
encrypted MMIO range as the VM is never disclosed on the hpa that
correlates to the gpa of the device's mmio. The obfuscated address is BAR
relative.

Based on an original patch by Aneesh [1]

Cc: Arnd Bergmann <arnd@arndb.de>
Link: https://lore.kernel.org/linux-coco/20251117140007.122062-8-aneesh.kumar@kernel.org/
Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 include/linux/ioport.h  |   1 +
 include/linux/pci-tsm.h |  34 ++++++
 drivers/pci/tsm/core.c  | 235 ++++++++++++++++++++++++++++++++++++++++
 3 files changed, 270 insertions(+)

diff --git a/include/linux/ioport.h b/include/linux/ioport.h
index 9afa30f9346f..1c106608c514 100644
--- a/include/linux/ioport.h
+++ b/include/linux/ioport.h
@@ -143,6 +143,7 @@ enum {
 	IORES_DESC_RESERVED			= 7,
 	IORES_DESC_SOFT_RESERVED		= 8,
 	IORES_DESC_CXL				= 9,
+	IORES_DESC_ENCRYPTED			= 10,
 };
 
 /*
diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index b70b4c0457c4..8869585230a3 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -194,12 +194,42 @@ struct pci_tsm_pf0 {
 	struct pci_doe_mb *doe_mb;
 };
 
+/**
+ * struct pci_tsm_mmio_entry - an encrypted MMIO range
+ * @res: MMIO address range (typically Guest Physical Address, GPA)
+ * @tsm_offset: Host Physical Address, HPA obfuscation offset added by the TSM.
+ *		Translates report addresses to GPA.
+ */
+struct pci_tsm_mmio_entry {
+	struct resource res;
+	u64 tsm_offset;
+};
+
+struct pci_tsm_mmio {
+	int nr;
+	struct pci_tsm_mmio_entry mmio[] __counted_by(nr);
+};
+
+static inline struct pci_tsm_mmio_entry *
+pci_tsm_mmio_entry(struct pci_tsm_mmio *mmio, int idx)
+{
+	return &mmio->mmio[idx];
+}
+
+static inline struct resource *pci_tsm_mmio_resource(struct pci_tsm_mmio *mmio,
+						     int idx)
+{
+	return &mmio->mmio[idx].res;
+}
+
 /**
  * struct pci_tsm_devsec - context for tracking private/accepted PCI resources
  * @base_tsm: generic core "tsm" context
+ * @mmio: encrypted MMIO resources for this assigned device
  */
 struct pci_tsm_devsec {
 	struct pci_tsm base_tsm;
+	struct pci_tsm_mmio *mmio;
 };
 
 /* physical function0 and capable of 'connect' */
@@ -297,6 +327,10 @@ ssize_t pci_tsm_guest_req(struct pci_dev *pdev, enum pci_tsm_req_scope scope,
 struct pci_tsm_devsec *to_pci_tsm_devsec(struct pci_tsm *tsm);
 void pci_tsm_init_evidence(struct pci_tsm_evidence *evidence, int slot,
 			   enum hash_algo digest_algo);
+int pci_tsm_mmio_setup(struct pci_dev *pdev, struct pci_tsm_mmio *mmio);
+void pci_tsm_mmio_teardown(struct pci_tsm_mmio *mmio);
+struct pci_tsm_mmio *pci_tsm_mmio_alloc(struct pci_dev *pdev);
+int pci_tsm_mmio_free(struct pci_dev *pdev, struct pci_tsm_mmio *mmio);
 #else
 static inline int pci_tsm_register(struct tsm_dev *tsm_dev)
 {
diff --git a/drivers/pci/tsm/core.c b/drivers/pci/tsm/core.c
index 039733fd19b1..e4f830b16d18 100644
--- a/drivers/pci/tsm/core.c
+++ b/drivers/pci/tsm/core.c
@@ -15,6 +15,7 @@
 #include <linux/pci-tsm.h>
 #include <linux/sysfs.h>
 #include <linux/tsm.h>
+#include <linux/unaligned.h>
 #include <linux/xarray.h>
 #include "../pci.h"
 
@@ -558,6 +559,240 @@ static ssize_t dsm_show(struct device *dev, struct device_attribute *attr,
 }
 static DEVICE_ATTR_RO(dsm);
 
+static void mmio_teardown(struct pci_tsm_mmio *mmio, int nr)
+{
+	while (nr--)
+		remove_resource(pci_tsm_mmio_resource(mmio, nr));
+}
+
+/**
+ * pci_tsm_mmio_setup() - mark device MMIO as encrypted in iomem
+ * @pdev: device owner of MMIO resources
+ * @mmio: container of an array of resources to mark encrypted
+ */
+int pci_tsm_mmio_setup(struct pci_dev *pdev, struct pci_tsm_mmio *mmio)
+{
+	int i;
+
+	device_lock_assert(&pdev->dev);
+	if (pdev->dev.driver)
+		return -EBUSY;
+
+	for (i = 0; i < mmio->nr; i++) {
+		struct resource *res = pci_tsm_mmio_resource(mmio, i);
+		int j;
+
+		if (resource_size(res) == 0 || !res->end)
+			break;
+
+		/* Only require the caller to set the range, init remainder */
+		*res = DEFINE_RES_NAMED_DESC(res->start, resource_size(res),
+					     "PCI MMIO Encrypted",
+					     IORESOURCE_MEM,
+					     IORES_DESC_ENCRYPTED);
+
+		for (j = 0; j < PCI_NUM_RESOURCES; j++)
+			if (resource_contains(pci_resource_n(pdev, j), res))
+				break;
+
+		/* Request is outside of device MMIO */
+		if (j >= PCI_NUM_RESOURCES)
+			break;
+
+		if (insert_resource(&iomem_resource, res) != 0)
+			break;
+	}
+
+	if (i >= mmio->nr)
+		return 0;
+
+	mmio_teardown(mmio, i);
+
+	return -EINVAL;
+}
+EXPORT_SYMBOL_GPL(pci_tsm_mmio_setup);
+
+void pci_tsm_mmio_teardown(struct pci_tsm_mmio *mmio)
+{
+	mmio_teardown(mmio, mmio->nr);
+}
+EXPORT_SYMBOL_GPL(pci_tsm_mmio_teardown);
+
+/*
+ * PCIe ECN TEE Device Interface Security Protocol (TDISP)
+ *
+ * Device Interface Report data object layout as defined by PCIe r7.0 section
+ * 11.3.11
+ */
+#define PCI_TSM_DEVIF_REPORT_MMIO_ATTR_MSIX_TABLE BIT(0)
+#define PCI_TSM_DEVIF_REPORT_MMIO_ATTR_MSIX_PBA BIT(1)
+#define PCI_TSM_DEVIF_REPORT_MMIO_ATTR_IS_NON_TEE BIT(2)
+#define PCI_TSM_DEVIF_REPORT_MMIO_ATTR_IS_UPDATABLE BIT(3)
+#define PCI_TSM_DEVIF_REPORT_MMIO_ATTR_RANGE_ID GENMASK(31, 16)
+
+/* An interface report 'pfn' is 4K in size */
+struct pci_tsm_devif_mmio {
+	__le64 pfn;
+	__le32 nr_pfns;
+	__le32 attributes;
+};
+
+struct pci_tsm_devif_report {
+	__le16 interface_info;
+	__le16 reserved;
+	__le16 msi_x_message_control;
+	__le16 lnr_control;
+	__le32 tph_control;
+	__le32 mmio_range_count;
+	struct pci_tsm_devif_mmio mmio[];
+};
+
+/**
+ * pci_tsm_mmio_alloc() - allocate encrypted MMIO range descriptor
+ * @pdev: device owner of MMIO ranges
+ * @report_data: TDISP Device Interface (DevIf) Report blob
+ * @report_sz: DevIf Report size
+ *
+ * Return: the encrypted MMIO range descriptor on success, NULL on failure
+ *
+ * Assumes that this is called within the live lifetime of a PCI device's
+ * association with a low level TSM.
+ */
+struct pci_tsm_mmio *pci_tsm_mmio_alloc(struct pci_dev *pdev)
+{
+	struct pci_tsm *tsm = pdev->tsm;
+	struct pci_tsm_evidence *evidence = &tsm->evidence;
+	struct pci_tsm_evidence_object *report_obj = &evidence->obj[PCI_TSM_EVIDENCE_TYPE_REPORT];
+	struct tsm_dev *tsm_dev = tsm->tsm_dev;
+	u64 reporting_bar_base, last_reporting_end;
+	const struct pci_tsm_devif_report *report;
+	u32 mmio_range_count;
+	int last_bar = -1;
+	int i;
+
+	guard(rwsem_read)(&evidence->lock);
+	if (report_obj->len < sizeof(struct pci_tsm_devif_report))
+		return NULL;
+
+	if (dev_WARN_ONCE(&tsm_dev->dev, !IS_ALIGNED((unsigned long) report_obj->data, 8),
+			  "misaligned report data\n"))
+		return NULL;
+
+	report = report_obj->data;
+	mmio_range_count = __le32_to_cpu(report->mmio_range_count);
+
+	/* check that the report object is self-consistent on mmio entries */
+	if (report_obj->len < struct_size(report, mmio, mmio_range_count))
+		return NULL;
+
+	/* create pci_tsm_mmio descriptors from the report data */
+	struct pci_tsm_mmio *mmio __free(kfree) =
+		kzalloc(struct_size(mmio, mmio, mmio_range_count), GFP_KERNEL);
+	if (!mmio)
+		return NULL;
+
+	for (i = 0; i < mmio_range_count; i++) {
+		u64 range_off;
+		struct range range;
+		const struct pci_tsm_devif_mmio *mmio_data = &report->mmio[i];
+		struct pci_tsm_mmio_entry *entry =
+			pci_tsm_mmio_entry(mmio, mmio->nr);
+		/* report values in are in terms of 4K pages */
+		u64 tsm_offset = __le64_to_cpu(mmio_data->pfn) * SZ_4K;
+		u64 size = __le32_to_cpu(mmio_data->nr_pfns) * SZ_4K;
+		u32 attr = __le32_to_cpu(mmio_data->attributes);
+		int bar = FIELD_GET(PCI_TSM_DEVIF_REPORT_MMIO_ATTR_RANGE_ID,
+				    attr);
+
+		tsm_offset *= SZ_4K;
+		size *= SZ_4K;
+
+		if (bar >= PCI_STD_NUM_BARS ||
+		    !(pci_resource_flags(pdev, bar) & IORESOURCE_MEM)) {
+			pci_dbg(pdev, "Invalid reporting bar ID %d\n", bar);
+			return NULL;
+		}
+
+		if (last_bar > bar) {
+			pci_dbg(pdev, "Reporting bar ID not in ascending order\n");
+			return NULL;
+		}
+
+		if (last_bar < bar) {
+			/* transition to a new bar */
+			last_bar = bar;
+			/*
+			 * The tsm_offset for the first range of the BAR
+			 * corresponds to the BAR base.
+			 */
+			reporting_bar_base = tsm_offset;
+		} else if (tsm_offset < last_reporting_end) {
+			pci_dbg(pdev, "Reporting ranges within BAR not in ascending order\n");
+			return NULL;
+		}
+
+		last_reporting_end = tsm_offset + size;
+		if (last_reporting_end < tsm_offset) {
+			pci_dbg(pdev, "Reporting range overflow\n");
+			return NULL;
+		}
+
+		range_off = tsm_offset - reporting_bar_base;
+		if (pci_resource_len(pdev, bar) < range_off + size) {
+			pci_dbg(pdev, "Reporting range larger than BAR size\n");
+			return NULL;
+		}
+
+		range.start = pci_resource_start(pdev, bar) + range_off;
+		range.end = range.start + size - 1;
+
+		if (FIELD_GET(PCI_TSM_DEVIF_REPORT_MMIO_ATTR_IS_NON_TEE,
+			      attr)) {
+			pci_dbg(pdev, "Skipping non-TEE range, BAR%d %pra\n",
+				 bar, &range);
+			continue;
+		}
+
+		/* Currently not supported */
+		if (FIELD_GET(PCI_TSM_DEVIF_REPORT_MMIO_ATTR_MSIX_TABLE,
+			      attr) ||
+		    FIELD_GET(PCI_TSM_DEVIF_REPORT_MMIO_ATTR_MSIX_PBA, attr)) {
+			pci_dbg(pdev, "Skipping MSIX range BAR%d %pra\n", bar,
+				 &range);
+			continue;
+		}
+
+		entry->res.start = range.start;
+		entry->res.end = range.end;
+		entry->tsm_offset = tsm_offset;
+		mmio->nr++;
+	}
+
+	return_ptr(mmio);
+}
+EXPORT_SYMBOL_GPL(pci_tsm_mmio_alloc);
+
+/**
+ * pci_tsm_mmio_free() - free a pci_tsm_mmio instance
+ * @pdev: device owner of MMIO ranges
+ * @mmio: instance to free
+ *
+ * Returns 0 if @mmio was idle on entry, -EBUSY otherwise
+ */
+int pci_tsm_mmio_free(struct pci_dev *pdev, struct pci_tsm_mmio *mmio)
+{
+	for (int i = 0; i < mmio->nr; i++) {
+		struct resource *res = pci_tsm_mmio_resource(mmio, i);
+
+		if (dev_WARN_ONCE(&pdev->dev, resource_assigned(res),
+				  "MMIO resource still assigned %pr\n", res))
+			return -EBUSY;
+	}
+	kfree(mmio);
+	return 0;
+}
+EXPORT_SYMBOL_GPL(pci_tsm_mmio_free);
+
 /**
  * pci_tsm_accept() - accept a device for private MMIO+DMA operation
  * @pdev: PCI device to accept

---

## [11] Dan Williams — 2026-03-02
*Subject: [PATCH v2 10/19] x86, swiotlb: Teach swiotlb to skip "accepted" devices*

There are two mechanisms to force SWIOTLB operation, the kernel command
line option and the internal SWIOTLB_FORCE flag. With the arrival of
"accepted" devices, devices that have been enabled to DMA to private
encrypted memory, the SWIOTLB_FORCE flag is an awkward fit. It may be the
case that SWIOTLB operation wants to be forced regardless of the device
acceptance state.

Introduce a new SWIOTLB_UNACCPTED flag that allows for both augmenting the
result of is_swiotlb_force_bounce() dynamically and allowing for an "always
SWIOTLB" override.

Cc: Thomas Gleixner <tglx@kernel.org>
Cc: Ingo Molnar <mingo@redhat.com>
Cc: Borislav Petkov <bp@alien8.de>
Cc: Dave Hansen <dave.hansen@linux.intel.com>
Cc: x86@kernel.org
Cc: "H. Peter Anvin" <hpa@zytor.com>
Cc: Marek Szyprowski <m.szyprowski@samsung.com>
Cc: Robin Murphy <robin.murphy@arm.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 include/linux/swiotlb.h   | 15 ++++++++++++---
 arch/x86/kernel/pci-dma.c |  2 +-
 kernel/dma/swiotlb.c      |  1 +
 3 files changed, 14 insertions(+), 4 deletions(-)

diff --git a/include/linux/swiotlb.h b/include/linux/swiotlb.h
index 3dae0f592063..0efb9b8e5dd0 100644
--- a/include/linux/swiotlb.h
+++ b/include/linux/swiotlb.h
@@ -17,6 +17,7 @@ struct scatterlist;
 #define SWIOTLB_VERBOSE	(1 << 0) /* verbose initialization */
 #define SWIOTLB_FORCE	(1 << 1) /* force bounce buffering */
 #define SWIOTLB_ANY	(1 << 2) /* allow any memory for the buffer */
+#define SWIOTLB_UNACCEPTED (1 << 3) /* swiotlb for unaccepted devices */
 
 /*
  * Maximum allowable number of contiguous slabs to map,
@@ -91,6 +92,7 @@ struct io_tlb_pool {
  * @nslabs:	Total number of IO TLB slabs in all pools.
  * @debugfs:	The dentry to debugfs.
  * @force_bounce: %true if swiotlb bouncing is forced
+ * @bounce_unaccepted: %true if unaccepted devices must bounce
  * @for_alloc:  %true if the pool is used for memory allocation
  * @can_grow:	%true if more pools can be allocated dynamically.
  * @phys_limit:	Maximum allowed physical address.
@@ -109,8 +111,9 @@ struct io_tlb_mem {
 	struct io_tlb_pool defpool;
 	unsigned long nslabs;
 	struct dentry *debugfs;
-	bool force_bounce;
-	bool for_alloc;
+	u8 force_bounce:1;
+	u8 bounce_unaccepted:1;
+	u8 for_alloc:1;
 #ifdef CONFIG_SWIOTLB_DYNAMIC
 	bool can_grow;
 	u64 phys_limit;
@@ -173,7 +176,13 @@ static inline bool is_swiotlb_force_bounce(struct device *dev)
 {
 	struct io_tlb_mem *mem = dev->dma_io_tlb_mem;
 
-	return mem && mem->force_bounce;
+	if (!mem)
+		return false;
+	if (mem->force_bounce)
+		return true;
+	if (mem->bounce_unaccepted && !device_cc_accepted(dev))
+		return true;
+	return false;
 }
 
 void swiotlb_init(bool addressing_limited, unsigned int flags);
diff --git a/arch/x86/kernel/pci-dma.c b/arch/x86/kernel/pci-dma.c
index 6267363e0189..8a737f501ae5 100644
--- a/arch/x86/kernel/pci-dma.c
+++ b/arch/x86/kernel/pci-dma.c
@@ -61,7 +61,7 @@ static void __init pci_swiotlb_detect(void)
 	 */
 	if (cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT)) {
 		x86_swiotlb_enable = true;
-		x86_swiotlb_flags |= SWIOTLB_FORCE;
+		x86_swiotlb_flags |= SWIOTLB_UNACCEPTED;
 	}
 }
 #else
diff --git a/kernel/dma/swiotlb.c b/kernel/dma/swiotlb.c
index a547c7693135..57e9647939fe 100644
--- a/kernel/dma/swiotlb.c
+++ b/kernel/dma/swiotlb.c
@@ -365,6 +365,7 @@ void __init swiotlb_init_remap(bool addressing_limit, unsigned int flags,
 
 	io_tlb_default_mem.force_bounce =
 		swiotlb_force_bounce || (flags & SWIOTLB_FORCE);
+	io_tlb_default_mem.bounce_unaccepted = flags & SWIOTLB_UNACCEPTED;
 
 #ifdef CONFIG_SWIOTLB_DYNAMIC
 	if (!remap)

---

## [12] Dan Williams — 2026-03-02
*Subject: [PATCH v2 11/19] x86, dma: Allow accepted devices to map private memory*

With the arrival of "accepted" devices, devices that have been enabled to
DMA to private encrypted memory, coherent DMA allocation no longer requires
page conversion. Update force_dma_unencrypted() to skip accepted devices.

Cc: Dave Hansen <dave.hansen@linux.intel.com>
Cc: Andy Lutomirski <luto@kernel.org>
Cc: Peter Zijlstra <peterz@infradead.org>
Cc: Thomas Gleixner <tglx@kernel.org>
Cc: Ingo Molnar <mingo@redhat.com>
Cc: Borislav Petkov <bp@alien8.de>
Cc: x86@kernel.org
Cc: "H. Peter Anvin" <hpa@zytor.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/mm/mem_encrypt.c | 5 +++--
 1 file changed, 3 insertions(+), 2 deletions(-)

diff --git a/arch/x86/mm/mem_encrypt.c b/arch/x86/mm/mem_encrypt.c
index 95bae74fdab2..6d2972ff6ed8 100644
--- a/arch/x86/mm/mem_encrypt.c
+++ b/arch/x86/mm/mem_encrypt.c
@@ -20,10 +20,11 @@
 bool force_dma_unencrypted(struct device *dev)
 {
 	/*
-	 * For SEV, all DMA must be to unencrypted addresses.
+	 * Require unencrypted DMA unless the device has been "accepted",
+	 * enabled by a TSM driver to DMA to private encrypted memory.
 	 */
 	if (cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT))
-		return true;
+		return !device_cc_accepted(dev);
 
 	/*
 	 * For SME, all DMA must be to unencrypted addresses if the

---

## [13] Dan Williams — 2026-03-02
*Subject: [PATCH v2 12/19] x86, ioremap, resource: Support IORES_DESC_ENCRYPTED for encrypted PCI MMIO*

PCIe Trusted Execution Environment Device Interface Security Protocol
(TDISP) arranges for a PCI device to support encrypted MMIO. In support of
that capability, ioremap() needs a mechanism to detect when a PCI device
has been dynamically transitioned into this secure state and enforce
encrypted MMIO mappings.

Teach ioremap() about a new IORES_DESC_ENCRYPTED type that supplements the
existing PCI Memory Space (MMIO) BAR resources. The proposal is that a
resource, "PCI MMIO Encrypted", with this description type is injected by
the PCI/TSM core for each PCI device BAR that is to be protected.

Unlike the existing encryption determination which is "implied with a
silent fallback to an unencrypted mapping", this indication is "explicit
with an expectation that the request fails instead of fallback".
IORES_MUST_ENCRYPT is added to manage this expectation.

Given that "PCI MMIO Encrypted" is an additional resource in the tree, the
IORESOURCE_BUSY flag will only be set on a descendant/child of that
resource. That means it cannot share the same walk as the check for "System
RAM". Add walk_iomem_res_desc() to check if any IORES_DESC_ENCRYPTED
intersects the ioremap() range and set IORES_MUST_ENCRYPT accordingly. When
IORES_MUST_ENCRYPT is set, the entire ioremap() range must be covered by
IORES_DESC_ENCRYPTED.

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
 include/linux/ioport.h |  1 +
 arch/x86/mm/ioremap.c  | 49 +++++++++++++++++++++++++++++++-----------
 2 files changed, 37 insertions(+), 13 deletions(-)

diff --git a/include/linux/ioport.h b/include/linux/ioport.h
index 1c106608c514..3efd07443c47 100644
--- a/include/linux/ioport.h
+++ b/include/linux/ioport.h
@@ -152,6 +152,7 @@ enum {
 enum {
 	IORES_MAP_SYSTEM_RAM		= BIT(0),
 	IORES_MAP_ENCRYPTED		= BIT(1),
+	IORES_MUST_ENCRYPT		= BIT(2), /* disable transparent fallback */
 };
 
 /* helpers to define resources */
diff --git a/arch/x86/mm/ioremap.c b/arch/x86/mm/ioremap.c
index 12c8180ca1ba..0f300e226a9f 100644
--- a/arch/x86/mm/ioremap.c
+++ b/arch/x86/mm/ioremap.c
@@ -36,6 +36,7 @@
  */
 struct ioremap_desc {
 	unsigned int flags;
+	u64 encrypt_size;
 };
 
 /*
@@ -88,23 +89,35 @@ static unsigned int __ioremap_check_ram(struct resource *res)
 }
 
 /*
- * In a SEV guest, NONE and RESERVED should not be mapped encrypted because
- * there the whole memory is already encrypted.
+ * In a encrypted guest, NONE and RESERVED should not be mapped encrypted
+ * because there the whole memory is already encrypted.
+ *
+ * For the encrypted case the entire range must agree with being mapped
+ * encrypted.
  */
-static unsigned int __ioremap_check_encrypted(struct resource *res)
+static unsigned int __ioremap_check_encrypted(struct ioremap_desc *desc,
+					      struct resource *res)
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
+		desc->encrypt_size += resource_size(res);
+		fallthrough;
 	default:
-		return IORES_MAP_ENCRYPTED;
+		flags |= IORES_MAP_ENCRYPTED;
 	}
 
-	return 0;
+	return flags;
 }
 
 /*
@@ -134,14 +147,10 @@ static int __ioremap_collect_map_flags(struct resource *res, void *arg)
 {
 	struct ioremap_desc *desc = arg;
 
-	if (!(desc->flags & IORES_MAP_SYSTEM_RAM))
-		desc->flags |= __ioremap_check_ram(res);
-
-	if (!(desc->flags & IORES_MAP_ENCRYPTED))
-		desc->flags |= __ioremap_check_encrypted(res);
+	desc->flags |= __ioremap_check_ram(res);
+	desc->flags |= __ioremap_check_encrypted(desc, res);
 
-	return ((desc->flags & (IORES_MAP_SYSTEM_RAM | IORES_MAP_ENCRYPTED)) ==
-			       (IORES_MAP_SYSTEM_RAM | IORES_MAP_ENCRYPTED));
+	return 0;
 }
 
 /*
@@ -162,6 +171,13 @@ static void __ioremap_check_mem(resource_size_t addr, unsigned long size,
 	memset(desc, 0, sizeof(struct ioremap_desc));
 
 	walk_mem_res(start, end, desc, __ioremap_collect_map_flags);
+	/*
+	 * Encrypted MMIO may parent a driver's requested region, so it needs a
+	 * separate search
+	 */
+	desc->encrypt_size = 0;
+	walk_iomem_res_desc(IORES_DESC_ENCRYPTED, IORESOURCE_MEM, start, end,
+			    desc, __ioremap_collect_map_flags);
 
 	__ioremap_check_other(addr, desc);
 }
@@ -209,6 +225,13 @@ __ioremap_caller(resource_size_t phys_addr, unsigned long size,
 
 	__ioremap_check_mem(phys_addr, size, &io_desc);
 
+	if ((io_desc.flags & IORES_MUST_ENCRYPT) &&
+	    io_desc.encrypt_size < size) {
+		pr_err("ioremap: encrypted mapping unavailable for %pa - %pa\n",
+		       &phys_addr, &last_addr);
+		return NULL;
+	}
+
 	/*
 	 * Don't allow anybody to remap normal RAM that we're using..
 	 */

---

## [14] Dan Williams — 2026-03-02
*Subject: [PATCH v2 13/19] samples/devsec: Introduce a PCI device-security bus + endpoint sample*

Establish just enough emulated PCI infrastructure to register a sample
TSM (platform security manager) driver and have it discover an IDE + TEE
(link encryption + device-interface security protocol (TDISP)) capable
device.

Use the existing CONFIG_PCI_BRIDGE_EMUL to emulate an IDE capable root
port, and open code the emulation of an endpoint device via simulated
configuration cycle responses.

The devsec_link_tsm driver responds to the PCI core TSM operations as if it
successfully exercised the given interface security protocol messages.

The devsec_bus and devsec_link_tsm drivers can be loaded in either order to
reflect cases like SEV-TIO where the TSM is PCI-device firmware, and cases
like TDX Connect where the TSM is a software agent running on the host CPU.

Follow-on patches exercise the IDE establishment core and the TDISP
operations that guests execute. For now, just successfully complete setup
and teardown of the DSM (device security manager) context as a building
block for management of TDI (trusted device interface) instances.

Note that 2 host bridges are emulated to regression test a bug report
[1] against the initial TSM based IDE establishment.

Trimmed kernel logs from loading the devsec sample modules and connecting a
device.

 # modprobe devsec_bus
    faux_driver devsec_bus: PCI host bridge to bus 10000:00
    pci_bus 10000:00: root bus resource [bus 00-01]
    pci_bus 10000:00: root bus resource [mem 0xf0000000-0xf03fffff]
    pci 10000:00:00.0: [8086:ffff] type 01 class 0x060400 PCIe Root Port
    pci 10000:00:00.0: PCI bridge to [bus 01]
    pci 10000:00:00.0:   bridge window [mem 0xf0000000-0xf03fffff]
    pci 10000:01:00.0: [8086:ffff] type 00 class 0x120000 PCIe Endpoint
    pci 10000:01:00.1: [8086:ffff] type 00 class 0x120000 PCIe Endpoint
    pci 10000:01:00.0: BAR 0 [mem 0xf0000000-0xf01fffff]: assigned
    pci 10000:01:00.1: BAR 0 [mem 0xf0200000-0xf03fffff]: assigned
    pcieport 10000:00:00.0: enabling device (0000 -> 0002)
    faux_driver devsec_bus: PCI host bridge to bus 10001:02
    pci_bus 10001:02: root bus resource [bus 02-03]
    pci_bus 10001:02: root bus resource [mem 0xf0400000-0xf07fffff]
    pci 10001:02:00.0: [8086:ffff] type 01 class 0x060400 PCIe Root Port
    pci 10001:02:00.0: PCI bridge to [bus 03]
    pci 10001:02:00.0:   bridge window [mem 0xf0400000-0xf07fffff]
    pci 10001:03:00.0: [8086:ffff] type 00 class 0x120000 PCIe Endpoint
    pci 10001:03:00.1: [8086:ffff] type 00 class 0x120000 PCIe Endpoint
    pci 10001:03:00.0: BAR 0 [mem 0xf0400000-0xf05fffff]: assigned
    pci 10001:03:00.1: BAR 0 [mem 0xf0600000-0xf07fffff]: assigned
    pcieport 10001:02:00.0: enabling device (0000 -> 0002)

 # modprobe devsec_link_tsm
    link_sysfs_enable: pci 10000:01:00.0: PCI/TSM: Platform TEE Security Manager detected (IDE TEE)
    link_sysfs_enable: pci 10001:03:00.0: PCI/TSM: Platform TEE Security Manager detected (IDE TEE)

 # echo tsm0 > /sys/bus/pci/devices/10000:01:00.0/tsm/connect
    devsec_tsm_pf0_probe: pci 10000:01:00.0: devsec: TSM enabled
    link_sysfs_enable: pci 10000:01:00.1: PCI/TSM: Device Security Manager detected (TEE)

Cc: Bjorn Helgaas <bhelgaas@google.com>
Cc: Lukas Wunner <lukas@wunner.de>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Link: http://lore.kernel.org/20260105093516.2645397-1-yilun.xu@linux.intel.com [1]
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 samples/Kconfig           |  19 +
 samples/Makefile          |   1 +
 samples/devsec/Makefile   |  10 +
 samples/devsec/devsec.h   |  43 +++
 samples/devsec/bus.c      | 780 ++++++++++++++++++++++++++++++++++++++
 samples/devsec/common.c   |  28 ++
 samples/devsec/link_tsm.c | 192 ++++++++++
 MAINTAINERS               |   1 +
 8 files changed, 1074 insertions(+)
 create mode 100644 samples/devsec/Makefile
 create mode 100644 samples/devsec/devsec.h
 create mode 100644 samples/devsec/bus.c
 create mode 100644 samples/devsec/common.c
 create mode 100644 samples/devsec/link_tsm.c

diff --git a/samples/Kconfig b/samples/Kconfig
index 5bc7c9e5a59e..679c332abd10 100644
--- a/samples/Kconfig
+++ b/samples/Kconfig
@@ -324,6 +324,25 @@ source "samples/rust/Kconfig"
 
 source "samples/damon/Kconfig"
 
+config SAMPLE_DEVSEC
+	tristate "Build a sample TEE Security Manager with an emulated PCI endpoint"
+	depends on m
+	depends on PCI
+	depends on VIRT_DRIVERS
+	depends on PCI_DOMAINS
+	select PCI_BRIDGE_EMUL
+	select PCI_TSM
+	select TSM
+	help
+	  Build a sample platform TEE Security Manager (TSM) driver with a
+	  corresponding emulated PCIe topology. The resulting sample modules,
+	  devsec_bus and devsec_tsm, exercise device-security enumeration, PCI
+	  subsystem use ABIs, device security flows. For example, exercise IDE
+	  (link encryption) establishment and TDISP state transitions via a
+	  Device Security Manager (DSM).
+
+	  If unsure, say N
+
 endif # SAMPLES
 
 config HAVE_SAMPLE_FTRACE_DIRECT
diff --git a/samples/Makefile b/samples/Makefile
index 07641e177bd8..59b510ace9b2 100644
--- a/samples/Makefile
+++ b/samples/Makefile
@@ -45,3 +45,4 @@ obj-$(CONFIG_SAMPLE_DAMON_PRCL)		+= damon/
 obj-$(CONFIG_SAMPLE_DAMON_MTIER)	+= damon/
 obj-$(CONFIG_SAMPLE_HUNG_TASK)		+= hung_task/
 obj-$(CONFIG_SAMPLE_TSM_MR)		+= tsm-mr/
+obj-y					+= devsec/
diff --git a/samples/devsec/Makefile b/samples/devsec/Makefile
new file mode 100644
index 000000000000..da122eb8d23d
--- /dev/null
+++ b/samples/devsec/Makefile
@@ -0,0 +1,10 @@
+# SPDX-License-Identifier: GPL-2.0
+
+obj-$(CONFIG_SAMPLE_DEVSEC) += devsec_common.o
+devsec_common-y := common.o
+
+obj-$(CONFIG_SAMPLE_DEVSEC) += devsec_bus.o
+devsec_bus-y := bus.o
+
+obj-$(CONFIG_SAMPLE_DEVSEC) += devsec_link_tsm.o
+devsec_link_tsm-y := link_tsm.o
diff --git a/samples/devsec/devsec.h b/samples/devsec/devsec.h
new file mode 100644
index 000000000000..e0ea9c6bb5e9
--- /dev/null
+++ b/samples/devsec/devsec.h
@@ -0,0 +1,43 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/* Copyright (C) 2024 - 2026 Intel Corporation */
+
+#ifndef __DEVSEC_H__
+#define __DEVSEC_H__
+
+#define NR_DEVSEC_HOST_BRIDGES 2
+
+struct devsec_sysdata {
+#ifdef CONFIG_X86
+	/*
+	 * Must be first member to that x86::pci_domain_nr() can type
+	 * pun devsec_sysdata and pci_sysdata.
+	 */
+	struct pci_sysdata sd;
+#else
+	int domain_nr;
+#endif
+};
+
+#ifdef CONFIG_X86
+static inline void devsec_set_domain_nr(struct devsec_sysdata *sd,
+					int domain_nr)
+{
+	sd->sd.domain = domain_nr;
+}
+static inline int devsec_get_domain_nr(struct devsec_sysdata *sd)
+{
+	return sd->sd.domain;
+}
+#else
+static inline void devsec_set_domain_nr(struct devsec_sysdata *sd,
+					int domain_nr)
+{
+	sd->domain_nr = domain_nr;
+}
+static inline int devsec_get_domain_nr(struct devsec_sysdata *sd)
+{
+	return sd->domain_nr;
+}
+#endif
+extern struct devsec_sysdata *devsec_sysdata[NR_DEVSEC_HOST_BRIDGES];
+#endif /* __DEVSEC_H__ */
diff --git a/samples/devsec/bus.c b/samples/devsec/bus.c
new file mode 100644
index 000000000000..a55e9573c8bf
--- /dev/null
+++ b/samples/devsec/bus.c
@@ -0,0 +1,780 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright (C) 2024 - 2026 Intel Corporation */
+
+#include <linux/bitfield.h>
+#include <linux/cleanup.h>
+#include <linux/device/faux.h>
+#include <linux/module.h>
+#include <linux/pci.h>
+#include <linux/range.h>
+#include <uapi/linux/pci_regs.h>
+
+#include "../../drivers/pci/pci-bridge-emul.h"
+#include "devsec.h"
+
+#define NR_DEVSEC_BUSES 1 /* root ports per host-bridge */
+#define NR_DEVICES_PER_BUS 1
+#define NR_FUNCTIONS 2
+#define NR_DEVICES (NR_DEVICES_PER_BUS * NR_FUNCTIONS * NR_DEVSEC_BUSES)
+#define NR_PORT_STREAMS 1
+#define NR_PORT_LINK_STREAMS 4
+#define NR_ADDR_ASSOC 1
+
+struct devsec {
+	struct pci_host_bridge hb;
+	struct devsec_sysdata sysdata;
+	struct resource busnr_res;
+	struct resource mmio_res;
+	struct resource prefetch_res;
+	struct pci_bus *bus;
+	struct device *dev;
+	struct devsec_port {
+		union {
+			struct devsec_ide {
+				u32 cap;
+				u32 ctl;
+				struct devsec_link_stream {
+					u32 ctl;
+					u32 status;
+				} link_stream[NR_PORT_LINK_STREAMS];
+				struct devsec_stream {
+					u32 cap;
+					u32 ctl;
+					u32 status;
+					u32 rid1;
+					u32 rid2;
+					struct devsec_addr_assoc {
+						u32 assoc1;
+						u32 assoc2;
+						u32 assoc3;
+					} assoc[NR_ADDR_ASSOC];
+				} stream[NR_PORT_STREAMS];
+			} ide __packed;
+			char ide_regs[sizeof(struct devsec_ide)];
+		};
+		struct pci_bridge_emul bridge;
+	} *devsec_ports[NR_DEVSEC_BUSES];
+	struct devsec_dev {
+		struct devsec *devsec;
+		struct range mmio_range;
+		u8 __cfg[SZ_4K];
+		struct devsec_dev_doe {
+			int cap;
+			u32 req[SZ_4K / sizeof(u32)];
+			u32 rsp[SZ_4K / sizeof(u32)];
+			int write, read, read_ttl;
+		} doe;
+		u16 ide_pos;
+		union {
+			struct devsec_ide ide __packed;
+			char ide_regs[sizeof(struct devsec_ide)];
+		};
+	} *devsec_devs[NR_DEVICES];
+};
+
+#define devsec_base(x) ((void __force __iomem *) &(x)->__cfg[0])
+
+static struct devsec *bus_to_devsec(struct pci_bus *bus)
+{
+	return container_of(bus->sysdata, struct devsec, sysdata);
+}
+
+static int devsec_dev_config_read(struct devsec *devsec, struct pci_bus *bus,
+				  unsigned int devfn, int pos, int size,
+				  u32 *val)
+{
+	int fn = PCI_SLOT(devfn) * NR_FUNCTIONS + PCI_FUNC(devfn);
+	struct devsec_dev *devsec_dev;
+	struct devsec_dev_doe *doe;
+	void __iomem *base;
+
+	if (PCI_FUNC(devfn) > NR_FUNCTIONS ||
+	    PCI_SLOT(devfn) > NR_DEVICES_PER_BUS ||
+	    fn >= ARRAY_SIZE(devsec->devsec_devs))
+		return PCIBIOS_DEVICE_NOT_FOUND;
+
+	devsec_dev = devsec->devsec_devs[fn];
+	base = devsec_base(devsec_dev);
+	doe = &devsec_dev->doe;
+
+	if (doe->cap && pos == doe->cap + PCI_DOE_READ) {
+		if (doe->read_ttl > 0) {
+			*val = doe->rsp[doe->read];
+			dev_dbg(&bus->dev, "devfn: %#x doe read[%d]\n", devfn,
+				doe->read);
+		} else {
+			*val = 0;
+			dev_dbg(&bus->dev, "devfn: %#x doe no data\n", devfn);
+		}
+		return PCIBIOS_SUCCESSFUL;
+	} else if (doe->cap && pos == doe->cap + PCI_DOE_STATUS) {
+		if (doe->read_ttl > 0) {
+			*val = PCI_DOE_STATUS_DATA_OBJECT_READY;
+			dev_dbg(&bus->dev, "devfn: %#x object ready\n", devfn);
+		} else if (doe->read_ttl < 0) {
+			*val = PCI_DOE_STATUS_ERROR;
+			dev_dbg(&bus->dev, "devfn: %#x error\n", devfn);
+		} else {
+			*val = 0;
+			dev_dbg(&bus->dev, "devfn: %#x idle\n", devfn);
+		}
+		return PCIBIOS_SUCCESSFUL;
+	} else if (devsec_dev->ide_pos && pos >= devsec_dev->ide_pos &&
+		   pos < devsec_dev->ide_pos + sizeof(struct devsec_ide)) {
+		*val = *(u32 *) &devsec_dev->ide_regs[pos - devsec_dev->ide_pos];
+		return PCIBIOS_SUCCESSFUL;
+	}
+
+	switch (size) {
+	case 1:
+		*val = readb(base + pos);
+		break;
+	case 2:
+		*val = readw(base + pos);
+		break;
+	case 4:
+		*val = readl(base + pos);
+		break;
+	default:
+		PCI_SET_ERROR_RESPONSE(val);
+		return PCIBIOS_BAD_REGISTER_NUMBER;
+	}
+	return PCIBIOS_SUCCESSFUL;
+}
+
+static int devsec_port_config_read(struct devsec *devsec, unsigned int devfn,
+				   int pos, int size, u32 *val)
+{
+	struct devsec_port *devsec_port;
+
+	if (PCI_FUNC(devfn) != 0 ||
+	    PCI_SLOT(devfn) >= ARRAY_SIZE(devsec->devsec_ports))
+		return PCIBIOS_DEVICE_NOT_FOUND;
+
+	devsec_port = devsec->devsec_ports[PCI_SLOT(devfn)];
+	return pci_bridge_emul_conf_read(&devsec_port->bridge, pos, size, val);
+}
+
+static int devsec_pci_read(struct pci_bus *bus, unsigned int devfn, int pos,
+			   int size, u32 *val)
+{
+	struct devsec *devsec = bus_to_devsec(bus);
+
+	dev_vdbg(&bus->dev, "devfn: %#x pos: %#x size: %d\n", devfn, pos, size);
+
+	if (bus == devsec->hb.bus)
+		return devsec_port_config_read(devsec, devfn, pos, size, val);
+	else if (bus->parent == devsec->hb.bus)
+		return devsec_dev_config_read(devsec, bus, devfn, pos, size,
+					      val);
+
+	return PCIBIOS_DEVICE_NOT_FOUND;
+}
+
+#ifndef PCI_DOE_PROTOCOL_DISCOVERY
+#define PCI_DOE_PROTOCOL_DISCOVERY 0
+#define PCI_DOE_FEATURE_CMA 1
+#endif
+
+/* just indicate support for CMA */
+static void doe_process(struct devsec_dev_doe *doe)
+{
+	u8 type;
+	u16 vid;
+
+	vid = FIELD_GET(PCI_DOE_DATA_OBJECT_HEADER_1_VID, doe->req[0]);
+	type = FIELD_GET(PCI_DOE_DATA_OBJECT_HEADER_1_TYPE, doe->req[0]);
+
+	if (vid != PCI_VENDOR_ID_PCI_SIG) {
+		doe->read_ttl = -1;
+		return;
+	}
+
+	if (type != PCI_DOE_PROTOCOL_DISCOVERY) {
+		doe->read_ttl = -1;
+		return;
+	}
+
+	doe->rsp[0] = doe->req[0];
+	doe->rsp[1] = FIELD_PREP(PCI_DOE_DATA_OBJECT_HEADER_2_LENGTH, 3);
+	doe->read_ttl = 3;
+	doe->rsp[2] = FIELD_PREP(PCI_DOE_DATA_OBJECT_DISC_RSP_3_VID,
+				 PCI_VENDOR_ID_PCI_SIG) |
+		      FIELD_PREP(PCI_DOE_DATA_OBJECT_DISC_RSP_3_PROTOCOL,
+				 PCI_DOE_FEATURE_CMA) |
+		      FIELD_PREP(PCI_DOE_DATA_OBJECT_DISC_RSP_3_NEXT_INDEX, 0);
+}
+
+static int devsec_dev_config_write(struct devsec *devsec, struct pci_bus *bus,
+				   unsigned int devfn, int pos, int size,
+				   u32 val)
+{
+	int fn = PCI_SLOT(devfn) * NR_FUNCTIONS + PCI_FUNC(devfn);
+	struct devsec_dev *devsec_dev;
+	struct devsec_dev_doe *doe;
+	struct devsec_ide *ide;
+	void __iomem *base;
+
+	dev_vdbg(&bus->dev, "devfn: %#x pos: %#x size: %d\n", devfn, pos, size);
+
+	if (PCI_FUNC(devfn) > NR_FUNCTIONS ||
+	    PCI_SLOT(devfn) > NR_DEVICES_PER_BUS ||
+	    fn >= ARRAY_SIZE(devsec->devsec_devs))
+		return PCIBIOS_DEVICE_NOT_FOUND;
+
+	devsec_dev = devsec->devsec_devs[fn];
+	base = devsec_base(devsec_dev);
+	doe = &devsec_dev->doe;
+	ide = &devsec_dev->ide;
+
+	if (pos >= PCI_BASE_ADDRESS_0 && pos <= PCI_BASE_ADDRESS_5) {
+		if (size != 4)
+			return PCIBIOS_BAD_REGISTER_NUMBER;
+		/* only one 64-bit mmio bar emulated for now */
+		if (pos == PCI_BASE_ADDRESS_0)
+			val &= ~lower_32_bits(range_len(&devsec_dev->mmio_range) - 1);
+		else if (pos == PCI_BASE_ADDRESS_1)
+			val &= ~upper_32_bits(range_len(&devsec_dev->mmio_range) - 1);
+		else
+			val = 0;
+	} else if (pos == PCI_ROM_ADDRESS) {
+		val = 0;
+	} else if (doe->cap && pos == doe->cap + PCI_DOE_CTRL) {
+		if (val & PCI_DOE_CTRL_GO) {
+			dev_dbg(&bus->dev, "devfn: %#x doe go\n", devfn);
+			doe_process(doe);
+		}
+		if (val & PCI_DOE_CTRL_ABORT) {
+			dev_dbg(&bus->dev, "devfn: %#x doe abort\n", devfn);
+			doe->write = 0;
+			doe->read = 0;
+			doe->read_ttl = 0;
+		}
+		return PCIBIOS_SUCCESSFUL;
+	} else if (doe->cap && pos == doe->cap + PCI_DOE_WRITE) {
+		if (doe->write < ARRAY_SIZE(doe->req))
+			doe->req[doe->write++] = val;
+		dev_dbg(&bus->dev, "devfn: %#x doe write[%d]\n", devfn,
+			doe->write - 1);
+		return PCIBIOS_SUCCESSFUL;
+	} else if (doe->cap && pos == doe->cap + PCI_DOE_READ) {
+		if (doe->read_ttl > 0) {
+			doe->read_ttl--;
+			doe->read++;
+			dev_dbg(&bus->dev, "devfn: %#x doe ack[%d]\n", devfn,
+				doe->read - 1);
+		}
+		return PCIBIOS_SUCCESSFUL;
+	} else if (devsec_dev->ide_pos && pos >= devsec_dev->ide_pos &&
+		   pos < devsec_dev->ide_pos + sizeof(struct devsec_ide)) {
+
+		*(u32 *) &devsec_dev->ide_regs[pos - devsec_dev->ide_pos] = val;
+
+		/*
+		 * Check if the control register is written and update the
+		 * status register accordingly
+		 */
+		for (int i = 0; i < NR_PORT_STREAMS; i++) {
+			struct devsec_stream *stream = &ide->stream[i];
+			u16 ide_off = pos - devsec_dev->ide_pos;
+
+			if (ide_off != offsetof(typeof(*ide), stream[i].ctl))
+				continue;
+
+			stream->status &= ~PCI_IDE_SEL_STS_STATE;
+			if (val & PCI_IDE_SEL_CTL_EN)
+				stream->status |= FIELD_PREP(
+					PCI_IDE_SEL_STS_STATE,
+					PCI_IDE_SEL_STS_STATE_SECURE);
+			else
+				stream->status |= FIELD_PREP(
+					PCI_IDE_SEL_STS_STATE,
+					PCI_IDE_SEL_STS_STATE_INSECURE);
+			break;
+		}
+		return PCIBIOS_SUCCESSFUL;
+	}
+
+	switch (size) {
+	case 1:
+		writeb(val, base + pos);
+		break;
+	case 2:
+		writew(val, base + pos);
+		break;
+	case 4:
+		writel(val, base + pos);
+		break;
+	default:
+		return PCIBIOS_BAD_REGISTER_NUMBER;
+	}
+	return PCIBIOS_SUCCESSFUL;
+}
+
+static int devsec_port_config_write(struct devsec *devsec, struct pci_bus *bus,
+				    unsigned int devfn, int pos, int size,
+				    u32 val)
+{
+	struct devsec_port *devsec_port;
+
+	dev_vdbg(&bus->dev, "devfn: %#x pos: %#x size: %d\n", devfn, pos, size);
+
+	if (PCI_FUNC(devfn) != 0 ||
+	    PCI_SLOT(devfn) >= ARRAY_SIZE(devsec->devsec_ports))
+		return PCIBIOS_DEVICE_NOT_FOUND;
+
+	devsec_port = devsec->devsec_ports[PCI_SLOT(devfn)];
+	return pci_bridge_emul_conf_write(&devsec_port->bridge, pos, size, val);
+}
+
+static int devsec_pci_write(struct pci_bus *bus, unsigned int devfn, int pos,
+			    int size, u32 val)
+{
+	struct devsec *devsec = bus_to_devsec(bus);
+
+	dev_vdbg(&bus->dev, "devfn: %#x pos: %#x size: %d\n", devfn, pos, size);
+
+	if (bus == devsec->hb.bus)
+		return devsec_port_config_write(devsec, bus, devfn, pos, size,
+						val);
+	else if (bus->parent == devsec->hb.bus)
+		return devsec_dev_config_write(devsec, bus, devfn, pos, size,
+					       val);
+	return PCIBIOS_DEVICE_NOT_FOUND;
+}
+
+static struct pci_ops devsec_ops = {
+	.read = devsec_pci_read,
+	.write = devsec_pci_write,
+};
+
+static void destroy_bus(void *data)
+{
+	struct pci_host_bridge *hb = data;
+
+	pci_stop_root_bus(hb->bus);
+	pci_remove_root_bus(hb->bus);
+}
+
+static u32 build_ext_cap_header(u32 id, u32 ver, u32 next)
+{
+	return FIELD_PREP(GENMASK(15, 0), id) |
+	       FIELD_PREP(GENMASK(19, 16), ver) |
+	       FIELD_PREP(GENMASK(31, 20), next);
+}
+
+static void init_ide(struct devsec_ide *ide)
+{
+	ide->cap =
+		PCI_IDE_CAP_LINK | PCI_IDE_CAP_SELECTIVE | PCI_IDE_CAP_IDE_KM |
+		PCI_IDE_CAP_TEE_LIMITED |
+		FIELD_PREP(PCI_IDE_CAP_LINK_TC_NUM, NR_PORT_LINK_STREAMS - 1) |
+		FIELD_PREP(PCI_IDE_CAP_SEL_NUM, NR_PORT_STREAMS - 1);
+
+	for (int i = 0; i < NR_PORT_STREAMS; i++)
+		ide->stream[i].cap =
+			FIELD_PREP(PCI_IDE_SEL_CAP_ASSOC_NUM, NR_ADDR_ASSOC);
+}
+
+static void init_dev_cfg(struct devsec_dev *devsec_dev, int fn)
+{
+	void __iomem *base = devsec_base(devsec_dev), *cap_base;
+	int pos, next;
+
+	/* BAR space */
+	writew(0x8086, base + PCI_VENDOR_ID);
+	writew(0xffff, base + PCI_DEVICE_ID);
+	writew(PCI_CLASS_ACCELERATOR_PROCESSING, base + PCI_CLASS_DEVICE);
+	writel(lower_32_bits(devsec_dev->mmio_range.start) |
+		       PCI_BASE_ADDRESS_MEM_TYPE_64 |
+		       PCI_BASE_ADDRESS_MEM_PREFETCH,
+	       base + PCI_BASE_ADDRESS_0);
+	writel(upper_32_bits(devsec_dev->mmio_range.start),
+	       base + PCI_BASE_ADDRESS_1);
+
+	/* PF0 is a DSM for this multifunction device */
+	writeb(PCI_HEADER_TYPE_MFD, base + PCI_HEADER_TYPE);
+
+	/* Capability init */
+	writew(PCI_STATUS_CAP_LIST, base + PCI_STATUS);
+	pos = 0x40;
+	writew(pos, base + PCI_CAPABILITY_LIST);
+
+	/* PCI-E Capability */
+	cap_base = base + pos;
+	writeb(PCI_CAP_ID_EXP, cap_base);
+	writew(PCI_EXP_TYPE_ENDPOINT, cap_base + PCI_EXP_FLAGS);
+	writew(PCI_EXP_LNKSTA_CLS_2_5GB | PCI_EXP_LNKSTA_NLW_X1, cap_base + PCI_EXP_LNKSTA);
+	writel(PCI_EXP_DEVCAP_FLR | PCI_EXP_DEVCAP_TEE, cap_base + PCI_EXP_DEVCAP);
+
+	/* PF0 has DOE and IDE, the rest of the functions are assignable TDIs */
+	if (fn > 0)
+		return;
+
+	/* DOE Extended Capability */
+	pos = PCI_CFG_SPACE_SIZE;
+	next = pos + PCI_DOE_CAP_SIZEOF;
+	cap_base = base + pos;
+	devsec_dev->doe.cap = pos;
+	writel(build_ext_cap_header(PCI_EXT_CAP_ID_DOE, 2, next), cap_base);
+
+	/* IDE Extended Capability */
+	pos = next;
+	cap_base = base + pos;
+	writel(build_ext_cap_header(PCI_EXT_CAP_ID_IDE, 1, 0), cap_base);
+	devsec_dev->ide_pos = pos + 4;
+	init_ide(&devsec_dev->ide);
+}
+
+#define MMIO_SIZE SZ_2M
+#define PREFETCH_SIZE SZ_2M
+
+static void destroy_devsec_dev(void *devsec_dev)
+{
+	kfree(devsec_dev);
+}
+
+static struct devsec_dev *devsec_dev_alloc(struct devsec *devsec, int rp, int fn)
+{
+	struct devsec_dev *devsec_dev __free(kfree) =
+		kzalloc(sizeof(*devsec_dev), GFP_KERNEL);
+	u64 start = devsec->prefetch_res.start +
+		    (rp * NR_FUNCTIONS + fn) * PREFETCH_SIZE;
+
+	if (!devsec_dev)
+		return ERR_PTR(-ENOMEM);
+
+	*devsec_dev = (struct devsec_dev) {
+		.mmio_range = {
+			.start = start,
+			.end = start + PREFETCH_SIZE - 1,
+		},
+		.devsec = devsec,
+	};
+	init_dev_cfg(devsec_dev, fn);
+
+	return_ptr(devsec_dev);
+}
+
+static int alloc_dev(struct devsec *devsec, int hb, int rp, int fn)
+{
+	struct devsec_dev *devsec_dev = devsec_dev_alloc(devsec, rp, fn);
+	int rc;
+
+	if (IS_ERR(devsec_dev))
+		return PTR_ERR(devsec_dev);
+	rc = devm_add_action_or_reset(devsec->dev, destroy_devsec_dev,
+				      devsec_dev);
+	if (rc)
+		return rc;
+	devsec->devsec_devs[rp * NR_FUNCTIONS + fn] = devsec_dev;
+
+	dev_dbg(devsec->dev, "added: hb: %d rp: %d fn: %d mmio: %pra\n",
+		hb, rp, fn, &devsec_dev->mmio_range);
+	return 0;
+}
+
+static pci_bridge_emul_read_status_t
+devsec_bridge_read_base(struct pci_bridge_emul *bridge, int pos, u32 *val)
+{
+	return PCI_BRIDGE_EMUL_NOT_HANDLED;
+}
+
+static pci_bridge_emul_read_status_t
+devsec_bridge_read_pcie(struct pci_bridge_emul *bridge, int pos, u32 *val)
+{
+	return PCI_BRIDGE_EMUL_NOT_HANDLED;
+}
+
+static pci_bridge_emul_read_status_t
+devsec_bridge_read_ext(struct pci_bridge_emul *bridge, int pos, u32 *val)
+{
+	struct devsec_port *devsec_port = bridge->data;
+
+	/* only one extended capability, IDE... */
+	if (pos == 0) {
+		*val = build_ext_cap_header(PCI_EXT_CAP_ID_IDE, 1, 0);
+		return PCI_BRIDGE_EMUL_HANDLED;
+	}
+
+	if (pos < 4)
+		return PCI_BRIDGE_EMUL_NOT_HANDLED;
+
+	pos -= 4;
+	if (pos < sizeof(struct devsec_ide)) {
+		*val = *(u32 *)(&devsec_port->ide_regs[pos]);
+		return PCI_BRIDGE_EMUL_HANDLED;
+	}
+
+	return PCI_BRIDGE_EMUL_NOT_HANDLED;
+}
+
+static void devsec_bridge_write_base(struct pci_bridge_emul *bridge, int pos,
+				     u32 old, u32 new, u32 mask)
+{
+}
+
+static void devsec_bridge_write_pcie(struct pci_bridge_emul *bridge, int pos,
+				     u32 old, u32 new, u32 mask)
+{
+}
+
+static void devsec_bridge_write_ext(struct pci_bridge_emul *bridge, int pos,
+				    u32 old, u32 new, u32 mask)
+{
+	struct devsec_port *devsec_port = bridge->data;
+
+	if (pos < sizeof(struct devsec_ide))
+		*(u32 *)(&devsec_port->ide_regs[pos]) = new;
+}
+
+static const struct pci_bridge_emul_ops devsec_bridge_ops = {
+	.read_base = devsec_bridge_read_base,
+	.write_base = devsec_bridge_write_base,
+	.read_pcie = devsec_bridge_read_pcie,
+	.write_pcie = devsec_bridge_write_pcie,
+	.read_ext = devsec_bridge_read_ext,
+	.write_ext = devsec_bridge_write_ext,
+};
+
+static int init_port(struct devsec *devsec, struct devsec_port *devsec_port,
+		     int hb, int rp)
+{
+	const struct resource *mres = &devsec->mmio_res;
+	const struct resource *pres = &devsec->prefetch_res;
+	struct pci_bridge_emul *bridge = &devsec_port->bridge;
+	u16 membase = cpu_to_le16(upper_16_bits(mres->start + MMIO_SIZE * rp) &
+				  0xfff0);
+	u16 memlimit =
+		cpu_to_le16(upper_16_bits(mres->end + MMIO_SIZE * rp) & 0xfff0);
+	u16 pref_mem_base =
+		cpu_to_le16((upper_16_bits(lower_32_bits(pres->start +
+							 PREFETCH_SIZE * rp)) &
+			     0xfff0) |
+			    PCI_PREF_RANGE_TYPE_64);
+	u16 pref_mem_limit = cpu_to_le16(
+		(upper_16_bits(lower_32_bits(pres->end + PREFETCH_SIZE * rp)) &
+		 0xfff0) |
+		PCI_PREF_RANGE_TYPE_64);
+	u32 prefbaseupper =
+		cpu_to_le32(upper_32_bits(pres->start + PREFETCH_SIZE * rp));
+	u32 preflimitupper =
+		cpu_to_le32(upper_32_bits(pres->end + PREFETCH_SIZE * rp));
+	int primary_bus = hb * (NR_DEVSEC_BUSES + 1);
+
+	*bridge = (struct pci_bridge_emul) {
+		.conf = {
+			.vendor = cpu_to_le16(0x8086),
+			.device = cpu_to_le16(0xffff),
+			.class_revision = cpu_to_le32(0x1),
+			.primary_bus = primary_bus,
+			.secondary_bus = primary_bus + rp + 1,
+			.subordinate_bus = primary_bus + rp + 1,
+			.membase = membase,
+			.memlimit = memlimit,
+			.pref_mem_base = pref_mem_base,
+			.pref_mem_limit = pref_mem_limit,
+			.prefbaseupper = prefbaseupper,
+			.preflimitupper = preflimitupper,
+		},
+		.pcie_conf = {
+			.devcap = cpu_to_le16(PCI_EXP_DEVCAP_FLR),
+			.lnksta = cpu_to_le16(PCI_EXP_LNKSTA_CLS_2_5GB),
+		},
+		.subsystem_vendor_id = cpu_to_le16(0x8086),
+		.has_pcie = true,
+		.data = devsec_port,
+		.ops = &devsec_bridge_ops,
+	};
+
+	init_ide(&devsec_port->ide);
+
+	return pci_bridge_emul_init(bridge, PCI_BRIDGE_EMUL_NO_IO_FORWARD);
+}
+
+static void destroy_port(void *data)
+{
+	struct devsec_port *devsec_port = data;
+
+	pci_bridge_emul_cleanup(&devsec_port->bridge);
+	kfree(devsec_port);
+}
+
+static struct devsec_port *devsec_port_alloc(struct devsec *devsec, int hb, int rp)
+{
+	int rc;
+
+	struct devsec_port *devsec_port __free(kfree) =
+		kzalloc(sizeof(*devsec_port), GFP_KERNEL);
+
+	if (!devsec_port)
+		return ERR_PTR(-ENOMEM);
+
+	rc = init_port(devsec, devsec_port, hb, rp);
+	if (rc)
+		return ERR_PTR(rc);
+
+	return_ptr(devsec_port);
+}
+
+static int alloc_port(struct devsec *devsec, int hb, int rp)
+{
+	struct devsec_port *devsec_port = devsec_port_alloc(devsec, hb, rp);
+	int rc;
+
+	if (IS_ERR(devsec_port))
+		return PTR_ERR(devsec_port);
+	rc = devm_add_action_or_reset(devsec->dev, destroy_port, devsec_port);
+	if (rc)
+		return rc;
+	devsec->devsec_ports[rp] = devsec_port;
+
+	return 0;
+}
+
+static void release_mmio_region(void *res)
+{
+	remove_resource(res);
+}
+
+static void release_prefetch_region(void *res)
+{
+	remove_resource(res);
+}
+
+static int devsec_add_host_bridge(struct faux_device *fdev, int hb_idx)
+{
+	struct pci_bus *bus;
+	struct devsec *devsec;
+	struct devsec_sysdata *sd;
+	struct pci_host_bridge *hb;
+	int busnr_start, busnr_end, rc;
+	struct device *dev = &fdev->dev;
+
+	hb = devm_pci_alloc_host_bridge(
+		dev, sizeof(*devsec) - sizeof(struct pci_host_bridge));
+	if (!hb)
+		return -ENOMEM;
+
+	devsec = container_of(hb, struct devsec, hb);
+	devsec->dev = dev;
+
+	devsec->mmio_res.name = "DEVSEC MMIO";
+	devsec->mmio_res.flags = IORESOURCE_MEM;
+	rc = allocate_resource(&iomem_resource, &devsec->mmio_res,
+			       MMIO_SIZE * NR_DEVICES, 0, SZ_4G, MMIO_SIZE,
+			       NULL, NULL);
+	if (rc)
+		return rc;
+
+	rc = devm_add_action_or_reset(dev, release_mmio_region,
+				      &devsec->mmio_res);
+	if (rc)
+		return rc;
+
+	devsec->prefetch_res.name = "DEVSEC PREFETCH";
+	devsec->prefetch_res.flags = IORESOURCE_MEM | IORESOURCE_MEM_64 |
+				     IORESOURCE_PREFETCH;
+	rc = allocate_resource(&iomem_resource, &devsec->prefetch_res,
+			       PREFETCH_SIZE * NR_DEVICES, SZ_4G, U64_MAX,
+			       PREFETCH_SIZE, NULL, NULL);
+	if (rc)
+		return rc;
+
+	rc = devm_add_action_or_reset(dev, release_prefetch_region,
+				      &devsec->prefetch_res);
+	if (rc)
+		return rc;
+
+	for (int i = 0; i < NR_DEVSEC_BUSES; i++) {
+		rc = alloc_port(devsec, hb_idx, i);
+		if (rc)
+			return rc;
+
+		for (int j = 0; j < NR_FUNCTIONS; j++) {
+			rc = alloc_dev(devsec, hb_idx, i, j);
+			if (rc)
+				return rc;
+		}
+	}
+
+	busnr_start = hb_idx * (NR_DEVSEC_BUSES + 1);
+	busnr_end = busnr_start + NR_DEVSEC_BUSES;
+
+	devsec->busnr_res = (struct resource) {
+		.name = "DEVSEC BUSES",
+		.start = busnr_start,
+		.end = busnr_end,
+		.flags = IORESOURCE_BUS | IORESOURCE_PCI_FIXED,
+	};
+	pci_add_resource(&hb->windows, &devsec->busnr_res);
+	pci_add_resource(&hb->windows, &devsec->mmio_res);
+	pci_add_resource(&hb->windows, &devsec->prefetch_res);
+
+	sd = &devsec->sysdata;
+	devsec_sysdata[hb_idx] = sd;
+
+	/* Start devsec_bus emulation above the last ACPI segment */
+	hb->domain_nr = pci_bus_find_emul_domain_nr(0, 0x10000, INT_MAX);
+	if (hb->domain_nr < 0)
+		return hb->domain_nr;
+
+	/*
+	 * Note, domain_nr is set in devsec_sysdata for
+	 * !CONFIG_PCI_DOMAINS_GENERIC platforms
+	 */
+	devsec_set_domain_nr(sd, hb->domain_nr);
+
+	hb->dev.parent = dev;
+	hb->sysdata = sd;
+	hb->ops = &devsec_ops;
+
+	rc = pci_scan_root_bus_bridge(hb);
+	if (rc)
+		return rc;
+
+	bus = hb->bus;
+	rc = devm_add_action_or_reset(dev, destroy_bus, no_free_ptr(hb));
+	if (rc)
+		return rc;
+
+	pci_assign_unassigned_bus_resources(bus);
+	pci_bus_add_devices(bus);
+
+	return 0;
+}
+
+static int __init devsec_bus_probe(struct faux_device *fdev)
+{
+	for (int i = 0; i < NR_DEVSEC_HOST_BRIDGES; i++) {
+		int rc = devsec_add_host_bridge(fdev, i);
+
+		if (rc)
+			return rc;
+	}
+	return 0;
+}
+
+static struct faux_device *devsec_bus;
+
+static struct faux_device_ops devsec_bus_ops = {
+	.probe = devsec_bus_probe,
+};
+
+static int __init devsec_bus_init(void)
+{
+	devsec_bus = faux_device_create("devsec_bus", NULL, &devsec_bus_ops);
+	if (!devsec_bus)
+		return -ENODEV;
+	return 0;
+}
+module_init(devsec_bus_init);
+
+static void __exit devsec_bus_exit(void)
+{
+	faux_device_destroy(devsec_bus);
+}
+module_exit(devsec_bus_exit);
+
+MODULE_LICENSE("GPL");
+MODULE_DESCRIPTION("Device Security Sample Infrastructure: TDISP Device Emulation");
diff --git a/samples/devsec/common.c b/samples/devsec/common.c
new file mode 100644
index 000000000000..d0e8648dfe98
--- /dev/null
+++ b/samples/devsec/common.c
@@ -0,0 +1,28 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright (C) 2024 - 2026 Intel Corporation */
+
+#include <linux/pci.h>
+#include <linux/export.h>
+
+#include "devsec.h"
+
+/*
+ * devsec_bus and devsec_tsm need a common location for this data to
+ * avoid depending on each other. Enables load order testing
+ */
+struct devsec_sysdata *devsec_sysdata[NR_DEVSEC_HOST_BRIDGES];
+EXPORT_SYMBOL_FOR_MODULES(devsec_sysdata, "devsec*");
+
+static int __init common_init(void)
+{
+	return 0;
+}
+module_init(common_init);
+
+static void __exit common_exit(void)
+{
+}
+module_exit(common_exit);
+
+MODULE_LICENSE("GPL");
+MODULE_DESCRIPTION("Device Security Sample Infrastructure: Shared data");
diff --git a/samples/devsec/link_tsm.c b/samples/devsec/link_tsm.c
new file mode 100644
index 000000000000..e5d66b877bca
--- /dev/null
+++ b/samples/devsec/link_tsm.c
@@ -0,0 +1,192 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright (C) 2024 - 2026 Intel Corporation */
+
+#define dev_fmt(fmt) "devsec: " fmt
+#include <linux/device/faux.h>
+#include <linux/pci-tsm.h>
+#include <linux/module.h>
+#include <linux/pci.h>
+#include <linux/tsm.h>
+#include "devsec.h"
+
+struct devsec_tsm_pf0 {
+	struct pci_tsm_pf0 pci;
+#define NR_TSM_STREAMS 4
+};
+
+struct devsec_tsm_fn {
+	struct pci_tsm pci;
+};
+
+static struct devsec_tsm_pf0 *to_devsec_tsm_pf0(struct pci_tsm *tsm)
+{
+	return container_of(tsm, struct devsec_tsm_pf0, pci.base_tsm);
+}
+
+static struct devsec_tsm_fn *to_devsec_tsm_fn(struct pci_tsm *tsm)
+{
+	return container_of(tsm, struct devsec_tsm_fn, pci);
+}
+
+static struct device *pci_tsm_host(struct pci_dev *pdev)
+{
+	struct pci_tsm *tsm = READ_ONCE(pdev->tsm);
+
+	if (!tsm)
+		return NULL;
+	return tsm->tsm_dev->dev.parent;
+}
+
+static struct pci_tsm *devsec_tsm_pf0_probe(struct tsm_dev *tsm_dev,
+					    struct pci_dev *pdev)
+{
+	int rc;
+
+	dev_dbg(tsm_dev->dev.parent, "%s\n", pci_name(pdev));
+
+	struct devsec_tsm_pf0 *devsec_tsm __free(kfree) =
+		kzalloc(sizeof(*devsec_tsm), GFP_KERNEL);
+	if (!devsec_tsm)
+		return NULL;
+
+	rc = pci_tsm_pf0_constructor(pdev, &devsec_tsm->pci, tsm_dev);
+	if (rc)
+		return NULL;
+
+	pci_dbg(pdev, "TSM enabled\n");
+	return &no_free_ptr(devsec_tsm)->pci.base_tsm;
+}
+
+static struct pci_tsm *devsec_link_tsm_fn_probe(struct tsm_dev *tsm_dev,
+						struct pci_dev *pdev)
+{
+	int rc;
+
+	dev_dbg(tsm_dev->dev.parent, "%s\n", pci_name(pdev));
+
+	struct devsec_tsm_fn *devsec_tsm __free(kfree) =
+		kzalloc(sizeof(*devsec_tsm), GFP_KERNEL);
+	if (!devsec_tsm)
+		return NULL;
+
+	rc = pci_tsm_link_constructor(pdev, &devsec_tsm->pci, tsm_dev);
+	if (rc)
+		return NULL;
+
+	pci_dbg(pdev, "TSM (sub-function) enabled\n");
+	return &no_free_ptr(devsec_tsm)->pci;
+}
+
+static struct pci_tsm *devsec_link_tsm_pci_probe(struct tsm_dev *tsm_dev,
+						 struct pci_dev *pdev)
+{
+	int i;
+
+	for (i = 0; i < NR_DEVSEC_HOST_BRIDGES; i++)
+		if (pdev->sysdata == devsec_sysdata[i])
+			break;
+	if (i >= NR_DEVSEC_HOST_BRIDGES)
+		return NULL;
+
+	if (is_pci_tsm_pf0(pdev))
+		return devsec_tsm_pf0_probe(tsm_dev, pdev);
+	return devsec_link_tsm_fn_probe(tsm_dev, pdev);
+}
+
+static void devsec_link_tsm_pci_remove(struct pci_tsm *tsm)
+{
+	struct pci_dev *pdev = tsm->pdev;
+
+	dev_dbg(pci_tsm_host(pdev), "%s\n", pci_name(pdev));
+
+	if (is_pci_tsm_pf0(pdev)) {
+		struct devsec_tsm_pf0 *devsec_tsm = to_devsec_tsm_pf0(tsm);
+
+		pci_tsm_pf0_destructor(&devsec_tsm->pci);
+		kfree(devsec_tsm);
+	} else {
+		struct devsec_tsm_fn *devsec_tsm = to_devsec_tsm_fn(tsm);
+
+		kfree(devsec_tsm);
+	}
+}
+
+/*
+ * Reference consumer for a TSM driver "connect" operation callback. The
+ * low-level TSM driver understands details about the platform the PCI
+ * core does not, like number of available streams that can be
+ * established per host bridge. The expected flow is:
+ *
+ * 1/ Allocate platform specific Stream resource (TSM specific)
+ * 2/ Allocate Stream Ids in the endpoint and Root Port (PCI TSM helper)
+ * 3/ Register Stream Ids for the consumed resources from the last 2
+ *    steps to be accountable (via sysfs) to the admin (PCI TSM helper)
+ * 4/ Register the Stream with the TSM core so that either PCI sysfs or
+ *    TSM core sysfs can list the in-use resources (TSM core helper)
+ * 5/ Configure IDE settings in the endpoint and Root Port (PCI TSM helper)
+ * 6/ RPC call to TSM to perform IDE_KM and optionally enable the stream
+ * (TSM Specific)
+ * 7/ Enable the stream in the endpoint, and root port if TSM call did
+ *    not already handle that (PCI TSM helper)
+ *
+ * The expectation is the helpers referenceed are convenience "library"
+ * APIs for common operations, not a "midlayer" that enforces a specific
+ * or use model sequencing.
+ */
+static int devsec_link_tsm_connect(struct pci_dev *pdev)
+{
+	return -ENXIO;
+}
+
+static void devsec_link_tsm_disconnect(struct pci_dev *pdev)
+{
+}
+
+static struct pci_tsm_ops devsec_link_pci_ops = {
+	.probe = devsec_link_tsm_pci_probe,
+	.remove = devsec_link_tsm_pci_remove,
+	.connect = devsec_link_tsm_connect,
+	.disconnect = devsec_link_tsm_disconnect,
+};
+
+static void devsec_link_tsm_remove(void *tsm_dev)
+{
+	tsm_unregister(tsm_dev);
+}
+
+static int devsec_link_tsm_probe(struct faux_device *fdev)
+{
+	struct tsm_dev *tsm_dev;
+
+	tsm_dev = tsm_register(&fdev->dev, &devsec_link_pci_ops);
+	if (IS_ERR(tsm_dev))
+		return PTR_ERR(tsm_dev);
+
+	return devm_add_action_or_reset(&fdev->dev, devsec_link_tsm_remove,
+					tsm_dev);
+}
+
+static struct faux_device *devsec_link_tsm;
+
+static const struct faux_device_ops devsec_link_device_ops = {
+	.probe = devsec_link_tsm_probe,
+};
+
+static int __init devsec_link_tsm_init(void)
+{
+	devsec_link_tsm = faux_device_create("devsec_link_tsm", NULL,
+					     &devsec_link_device_ops);
+	if (!devsec_link_tsm)
+		return -ENOMEM;
+	return 0;
+}
+module_init(devsec_link_tsm_init);
+
+static void __exit devsec_link_tsm_exit(void)
+{
+	faux_device_destroy(devsec_link_tsm);
+}
+module_exit(devsec_link_tsm_exit);
+
+MODULE_LICENSE("GPL");
+MODULE_DESCRIPTION("Device Security Sample Infrastructure: Platform Link-TSM Driver");
diff --git a/MAINTAINERS b/MAINTAINERS
index 3d5e2cbef71e..889546f66f2f 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -26539,6 +26539,7 @@ F:	drivers/pci/tsm/
 F:	drivers/virt/coco/guest/
 F:	include/linux/*tsm*.h
 F:	include/uapi/linux/pci-tsm-netlink.h
+F:	samples/devsec/
 F:	samples/tsm-mr/
 
 TRUSTED SERVICES TEE DRIVER

---

## [15] Dan Williams — 2026-03-02
*Subject: [PATCH v2 14/19] samples/devsec: Add sample IDE establishment*

Exercise common setup and teardown flows for a sample platform TSM
driver that implements the TSM 'connect' and 'disconnect' flows.

This is both a template for platform specific implementations and a
simple integration test for the PCI core infrastructure + ABI.

Cc: Bjorn Helgaas <bhelgaas@google.com>
Cc: Lukas Wunner <lukas@wunner.de>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <suzuki.poulose@arm.com>
Cc: "Aneesh Kumar K.V" <aneesh.kumar@kernel.org>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 samples/devsec/bus.c      |  4 +++
 samples/devsec/link_tsm.c | 70 ++++++++++++++++++++++++++++++++++++++-
 2 files changed, 73 insertions(+), 1 deletion(-)

diff --git a/samples/devsec/bus.c b/samples/devsec/bus.c
index a55e9573c8bf..fe32b5c8e033 100644
--- a/samples/devsec/bus.c
+++ b/samples/devsec/bus.c
@@ -6,6 +6,7 @@
 #include <linux/device/faux.h>
 #include <linux/module.h>
 #include <linux/pci.h>
+#include <linux/pci-ide.h>
 #include <linux/range.h>
 #include <uapi/linux/pci_regs.h>
 
@@ -16,6 +17,7 @@
 #define NR_DEVICES_PER_BUS 1
 #define NR_FUNCTIONS 2
 #define NR_DEVICES (NR_DEVICES_PER_BUS * NR_FUNCTIONS * NR_DEVSEC_BUSES)
+#define NR_HOST_BRIDGE_STREAMS 4
 #define NR_PORT_STREAMS 1
 #define NR_PORT_LINK_STREAMS 4
 #define NR_ADDR_ASSOC 1
@@ -728,6 +730,7 @@ static int devsec_add_host_bridge(struct faux_device *fdev, int hb_idx)
 	hb->dev.parent = dev;
 	hb->sysdata = sd;
 	hb->ops = &devsec_ops;
+	pci_ide_set_nr_streams(hb, NR_HOST_BRIDGE_STREAMS);
 
 	rc = pci_scan_root_bus_bridge(hb);
 	if (rc)
@@ -776,5 +779,6 @@ static void __exit devsec_bus_exit(void)
 }
 module_exit(devsec_bus_exit);
 
+MODULE_IMPORT_NS("PCI_IDE");
 MODULE_LICENSE("GPL");
 MODULE_DESCRIPTION("Device Security Sample Infrastructure: TDISP Device Emulation");
diff --git a/samples/devsec/link_tsm.c b/samples/devsec/link_tsm.c
index e5d66b877bca..dea5215ff97b 100644
--- a/samples/devsec/link_tsm.c
+++ b/samples/devsec/link_tsm.c
@@ -4,6 +4,7 @@
 #define dev_fmt(fmt) "devsec: " fmt
 #include <linux/device/faux.h>
 #include <linux/pci-tsm.h>
+#include <linux/pci-ide.h>
 #include <linux/module.h>
 #include <linux/pci.h>
 #include <linux/tsm.h>
@@ -111,6 +112,23 @@ static void devsec_link_tsm_pci_remove(struct pci_tsm *tsm)
 	}
 }
 
+/* protected by tsm_ops lock */
+static DECLARE_BITMAP(devsec_stream_ids, NR_TSM_STREAMS);
+static struct pci_ide *devsec_streams[NR_TSM_STREAMS];
+
+static unsigned long *alloc_devsec_stream_id(unsigned long *stream_id)
+{
+	unsigned long id;
+
+	id = find_first_zero_bit(devsec_stream_ids, NR_TSM_STREAMS);
+	if (id == NR_TSM_STREAMS)
+		return NULL;
+	set_bit(id, devsec_stream_ids);
+	*stream_id = id;
+	return stream_id;
+}
+DEFINE_FREE(free_devsec_stream, unsigned long *, if (_T) clear_bit(*_T, devsec_stream_ids))
+
 /*
  * Reference consumer for a TSM driver "connect" operation callback. The
  * low-level TSM driver understands details about the platform the PCI
@@ -135,11 +153,61 @@ static void devsec_link_tsm_pci_remove(struct pci_tsm *tsm)
  */
 static int devsec_link_tsm_connect(struct pci_dev *pdev)
 {
-	return -ENXIO;
+	struct pci_dev *rp = pcie_find_root_port(pdev);
+	unsigned long __stream_id;
+	int rc;
+
+	unsigned long *stream_id __free(free_devsec_stream) =
+		alloc_devsec_stream_id(&__stream_id);
+	if (!stream_id)
+		return -EBUSY;
+
+	struct pci_ide *ide __free(pci_ide_stream_release) =
+		pci_ide_stream_alloc(pdev);
+	if (!ide)
+		return -ENOMEM;
+
+	ide->stream_id = *stream_id;
+	rc = pci_ide_stream_register(ide);
+	if (rc)
+		return rc;
+
+	pci_ide_stream_setup(pdev, ide);
+	pci_ide_stream_setup(rp, ide);
+
+	rc = tsm_ide_stream_register(ide);
+	if (rc)
+		return rc;
+
+	/*
+	 * Model a TSM that handled enabling the stream at
+	 * tsm_ide_stream_register() time
+	 */
+	rc = pci_ide_stream_enable(pdev, ide);
+	if (rc)
+		return rc;
+
+	devsec_streams[*no_free_ptr(stream_id)] = no_free_ptr(ide);
+
+	return 0;
 }
 
 static void devsec_link_tsm_disconnect(struct pci_dev *pdev)
 {
+	struct pci_ide *ide;
+	unsigned long i;
+
+	for_each_set_bit(i, devsec_stream_ids, NR_TSM_STREAMS)
+		if (devsec_streams[i]->pdev == pdev)
+			break;
+
+	if (i >= NR_TSM_STREAMS)
+		return;
+
+	ide = devsec_streams[i];
+	devsec_streams[i] = NULL;
+	pci_ide_stream_release(ide);
+	clear_bit(i, devsec_stream_ids);
 }
 
 static struct pci_tsm_ops devsec_link_pci_ops = {

---

## [16] Dan Williams — 2026-03-02
*Subject: [PATCH v2 15/19] samples/devsec: Add sample TSM bind and guest_request flows*

Provide a method to test the basic object lifetime mechanics of 'struct
pci_tdi', and passthrough sysfs message to simulate pci_tsm_guest_req().
Arrange for pci_tsm_bind() and pci_tsm_guest_req() to be invoked via
devsec_link_tsm faux-device sysfs attributes.

Cc: Bjorn Helgaas <bhelgaas@google.com>
Cc: Lukas Wunner <lukas@wunner.de>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <suzuki.poulose@arm.com>
Cc: "Aneesh Kumar K.V" <aneesh.kumar@kernel.org>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 Documentation/ABI/testing/sysfs-faux-devsec |  15 ++
 samples/devsec/link_tsm.c                   | 157 +++++++++++++++++++-
 2 files changed, 170 insertions(+), 2 deletions(-)
 create mode 100644 Documentation/ABI/testing/sysfs-faux-devsec

diff --git a/Documentation/ABI/testing/sysfs-faux-devsec b/Documentation/ABI/testing/sysfs-faux-devsec
new file mode 100644
index 000000000000..29da17bfa720
--- /dev/null
+++ b/Documentation/ABI/testing/sysfs-faux-devsec
@@ -0,0 +1,15 @@
+What:		/sys/bus/faux/devices/{devsec_link_tsm,devsec_tsm}
+Contact:	linux-coco@lists.linux.dev
+Description:
+		(DIR) The devsec_link_tsm and devsec_tsm faux devices test the
+		kernel's ABIs and flows that support PCIe Trusted Device
+		Interface Security Protocol (TDISP). The devsec_link_tsm device
+		simulates a "host" TSM that establishes an SPDM session and link
+		security (PCIe IDE). The devsec_tsm device simulates a "guest"
+		TSM that implements the lock+accept flows.
+
+What:
+/sys/bus/faux/devices/devsec_link_tsm/{bind,unbind}
+Contact:	linux-coco@lists.linux.dev
+Description:
+
diff --git a/samples/devsec/link_tsm.c b/samples/devsec/link_tsm.c
index dea5215ff97b..2e4c1234bdee 100644
--- a/samples/devsec/link_tsm.c
+++ b/samples/devsec/link_tsm.c
@@ -19,6 +19,10 @@ struct devsec_tsm_fn {
 	struct pci_tsm pci;
 };
 
+struct devsec_tsm_tdi {
+	struct pci_tdi pci;
+};
+
 static struct devsec_tsm_pf0 *to_devsec_tsm_pf0(struct pci_tsm *tsm)
 {
 	return container_of(tsm, struct devsec_tsm_pf0, pci.base_tsm);
@@ -29,6 +33,12 @@ static struct devsec_tsm_fn *to_devsec_tsm_fn(struct pci_tsm *tsm)
 	return container_of(tsm, struct devsec_tsm_fn, pci);
 }
 
+/*
+ * Note that outside of pci_tsm_ops callbacks, this lookup is racy. I.e. does
+ * not account for racing disconnect / unlock after reading ->tsm. The
+ * @devsec_link_groups usage of this is only for best-effort protection against
+ * using this sample / test module to interfere with other TSM drivers.
+ */
 static struct device *pci_tsm_host(struct pci_dev *pdev)
 {
 	struct pci_tsm *tsm = READ_ONCE(pdev->tsm);
@@ -157,6 +167,8 @@ static int devsec_link_tsm_connect(struct pci_dev *pdev)
 	unsigned long __stream_id;
 	int rc;
 
+	dev_dbg(pci_tsm_host(pdev), "%s\n", pci_name(pdev));
+
 	unsigned long *stream_id __free(free_devsec_stream) =
 		alloc_devsec_stream_id(&__stream_id);
 	if (!stream_id)
@@ -197,6 +209,8 @@ static void devsec_link_tsm_disconnect(struct pci_dev *pdev)
 	struct pci_ide *ide;
 	unsigned long i;
 
+	dev_dbg(pci_tsm_host(pdev), "%s\n", pci_name(pdev));
+
 	for_each_set_bit(i, devsec_stream_ids, NR_TSM_STREAMS)
 		if (devsec_streams[i]->pdev == pdev)
 			break;
@@ -210,11 +224,56 @@ static void devsec_link_tsm_disconnect(struct pci_dev *pdev)
 	clear_bit(i, devsec_stream_ids);
 }
 
+static struct pci_tdi *devsec_link_tsm_bind(struct pci_dev *pdev,
+					    struct kvm *kvm, u32 tdi_id)
+{
+	struct devsec_tsm_tdi *devsec_tdi =
+		kzalloc(sizeof(struct devsec_tsm_tdi), GFP_KERNEL);
+
+	dev_dbg(pci_tsm_host(pdev), "%s\n", pci_name(pdev));
+
+	if (!devsec_tdi)
+		return ERR_PTR(-ENOMEM);
+
+	pci_tsm_tdi_constructor(pdev, &devsec_tdi->pci, kvm, tdi_id);
+
+	return &devsec_tdi->pci;
+}
+
+static void devsec_link_tsm_unbind(struct pci_tdi *tdi)
+{
+	struct devsec_tsm_tdi *devsec_tdi =
+		container_of(tdi, struct devsec_tsm_tdi, pci);
+
+	dev_dbg(pci_tsm_host(tdi->pdev), "%s\n", pci_name(tdi->pdev));
+
+	kfree(devsec_tdi);
+}
+
+static ssize_t devsec_link_tsm_guest_req(struct pci_tdi *tdi,
+					 enum pci_tsm_req_scope scope,
+					 sockptr_t req_in, size_t in_len,
+					 sockptr_t req_out, size_t out_len,
+					 u64 *tsm_code)
+{
+	if (!sockptr_is_kernel(req_in))
+		return -ENXIO;
+
+	dev_dbg(pci_tsm_host(tdi->pdev), "%s\n", pci_name(tdi->pdev));
+	print_hex_dump_debug("devsec req_in  ", DUMP_PREFIX_OFFSET, 16, 4,
+			     req_in.kernel, min(in_len, 256u), true);
+
+	return 0;
+}
+
 static struct pci_tsm_ops devsec_link_pci_ops = {
 	.probe = devsec_link_tsm_pci_probe,
 	.remove = devsec_link_tsm_pci_remove,
 	.connect = devsec_link_tsm_connect,
 	.disconnect = devsec_link_tsm_disconnect,
+	.bind = devsec_link_tsm_bind,
+	.unbind = devsec_link_tsm_unbind,
+	.guest_req = devsec_link_tsm_guest_req,
 };
 
 static void devsec_link_tsm_remove(void *tsm_dev)
@@ -240,10 +299,104 @@ static const struct faux_device_ops devsec_link_device_ops = {
 	.probe = devsec_link_tsm_probe,
 };
 
+static struct pci_dev *pci_find_device(const char *name)
+{
+	struct device *dev = bus_find_device_by_name(&pci_bus_type, NULL, name);
+
+	if (dev)
+		return to_pci_dev(dev);
+	return NULL;
+}
+
+static ssize_t tsm_bind_store(struct device *dev, struct device_attribute *attr,
+			      const char *buf, size_t count)
+{
+	struct device *host;
+	int rc;
+
+	struct pci_dev *pdev __free(pci_dev_put) = pci_find_device(buf);
+	if (!pdev)
+		return -ENODEV;
+
+	host = pci_tsm_host(pdev);
+	if (!host || host != &devsec_link_tsm->dev)
+		return -ENXIO;
+
+	rc = pci_tsm_bind(pdev, (struct kvm *)1, pci_dev_id(pdev));
+	if (rc)
+		return rc;
+	return count;
+}
+static DEVICE_ATTR_WO(tsm_bind);
+
+static ssize_t tsm_unbind_store(struct device *dev,
+				struct device_attribute *attr,
+				const char *buf, size_t count)
+{
+	struct device *host;
+
+	struct pci_dev *pdev __free(pci_dev_put) = pci_find_device(buf);
+	if (!pdev)
+		return -ENODEV;
+
+	host = pci_tsm_host(pdev);
+	if (!host || host != &devsec_link_tsm->dev)
+		return -ENXIO;
+
+	pci_tsm_unbind(pdev);
+	return count;
+}
+static DEVICE_ATTR_WO(tsm_unbind);
+
+static ssize_t tsm_request_store(struct device *dev,
+				 struct device_attribute *attr,
+				 const char *__buf, size_t count)
+{
+	ssize_t rc;
+	u64 tsm_code = 0;
+	struct device *host;
+	char req_out[16] = {0};
+	size_t out_len = sizeof(req_out);
+
+	struct pci_dev *pdev __free(pci_dev_put) = pci_find_device(__buf);
+	if (!pdev)
+		return -ENODEV;
+
+	char *buf __free(kvfree) = kvmemdup(__buf, count, GFP_KERNEL);
+	if (!buf)
+		return -ENOMEM;
+
+	host = pci_tsm_host(pdev);
+	if (!host || host != &devsec_link_tsm->dev)
+		return -ENXIO;
+
+	rc = pci_tsm_guest_req(pdev, PCI_TSM_REQ_INFO, KERNEL_SOCKPTR(buf),
+			       count, KERNEL_SOCKPTR(req_out), out_len,
+			       &tsm_code);
+	if (rc)
+		return rc;
+
+	return count;
+}
+static DEVICE_ATTR_WO(tsm_request);
+
+/*
+ * Facilitate testing of the bind and request flows in lieu of VFIO/IOMMUFD
+ * support to exercise these paths.
+ */
+static struct attribute *devsec_link_attrs[] = {
+	&dev_attr_tsm_bind.attr,
+	&dev_attr_tsm_unbind.attr,
+	&dev_attr_tsm_request.attr,
+	NULL,
+};
+ATTRIBUTE_GROUPS(devsec_link);
+
 static int __init devsec_link_tsm_init(void)
 {
-	devsec_link_tsm = faux_device_create("devsec_link_tsm", NULL,
-					     &devsec_link_device_ops);
+	devsec_link_tsm = faux_device_create_with_groups(
+		"devsec_link_tsm", NULL, &devsec_link_device_ops,
+		devsec_link_groups);
 	if (!devsec_link_tsm)
 		return -ENOMEM;
 	return 0;

---

## [17] Dan Williams — 2026-03-02
*Subject: [PATCH v2 16/19] samples/devsec: Introduce a "Device Security TSM" sample driver*

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
 samples/devsec/Makefile |   6 ++
 samples/devsec/pci.c    |  39 +++++++++++++
 samples/devsec/tsm.c    | 124 ++++++++++++++++++++++++++++++++++++++++
 3 files changed, 169 insertions(+)
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
index 000000000000..50519be412ed
--- /dev/null
+++ b/samples/devsec/pci.c
@@ -0,0 +1,39 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright (C) 2024 - 2026 Intel Corporation */
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
index 000000000000..46dbe668945a
--- /dev/null
+++ b/samples/devsec/tsm.c
@@ -0,0 +1,124 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright (C) 2024 - 2026 Intel Corporation */
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
+	return container_of(tsm, struct devsec_dev_data, pci.base_tsm);
+}
+
+static struct pci_tsm *devsec_tsm_lock(struct tsm_dev *tsm_dev, struct pci_dev *pdev)
+{
+	int rc;
+
+	struct devsec_dev_data *devsec_data __free(kfree) =
+		kzalloc(sizeof(*devsec_data), GFP_KERNEL);
+	if (!devsec_data)
+		return ERR_PTR(-ENOMEM);
+
+	rc = pci_tsm_devsec_constructor(pdev, &devsec_data->pci, tsm_dev);
+	if (rc)
+		return ERR_PTR(rc);
+
+	return &no_free_ptr(devsec_data)->pci.base_tsm;
+}
+
+static void devsec_tsm_unlock(struct pci_tsm *tsm)
+{
+	struct devsec_dev_data *devsec_data = to_devsec_data(tsm);
+	struct pci_tsm_devsec *devsec_tsm = to_pci_tsm_devsec(tsm);
+
+	pci_tsm_mmio_teardown(devsec_tsm->mmio);
+	kfree(devsec_tsm->mmio);
+	kfree(devsec_data);
+}
+
+static int devsec_tsm_accept(struct pci_dev *pdev)
+{
+	struct pci_tsm_devsec *devsec_tsm = to_pci_tsm_devsec(pdev->tsm);
+	int rc;
+
+	struct pci_tsm_mmio *mmio __free(kfree) =
+		kzalloc(struct_size(mmio, mmio, PCI_NUM_RESOURCES), GFP_KERNEL);
+	if (!mmio)
+		return -ENOMEM;
+
+	/*
+	 * Typically this range request would come from the TDISP Interface
+	 * Report. For this sample, just request all BARs be marked encrypted
+	 */
+	for (int i = 0; i < PCI_NUM_RESOURCES; i++) {
+		struct resource *res = pci_tsm_mmio_resource(mmio, mmio->nr);
+
+		if (pci_resource_len(pdev, i) == 0 ||
+		    !(pci_resource_flags(pdev, i) & IORESOURCE_MEM))
+			continue;
+		res->start = pci_resource_start(pdev, i);
+		res->end = pci_resource_end(pdev, i);
+		mmio->nr++;
+	}
+
+	rc = pci_tsm_mmio_setup(pdev, mmio);
+	if (rc)
+		return rc;
+	devsec_tsm->mmio = no_free_ptr(mmio);
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

## [18] Dan Williams — 2026-03-02
*Subject: [PATCH v2 17/19] tools/testing/devsec: Add a script to exercise samples/devsec/*

Run the samples/devsec/ infrastructure through the PCIe TDISP connect,
bind, lock, and accept flows. Include tests for module "autoprobe" policy.

Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 tools/testing/devsec/devsec.sh | 234 +++++++++++++++++++++++++++++++++
 MAINTAINERS                    |   1 +
 2 files changed, 235 insertions(+)
 create mode 100755 tools/testing/devsec/devsec.sh

diff --git a/tools/testing/devsec/devsec.sh b/tools/testing/devsec/devsec.sh
new file mode 100755
index 000000000000..ce4a986b74dd
--- /dev/null
+++ b/tools/testing/devsec/devsec.sh
@@ -0,0 +1,234 @@
+#!/bin/bash
+# SPDX-License-Identifier: GPL-2.0
+# Copyright (C) 2025-2026 Intel Corporation
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
+PCI_DEVS=(
+"/sys/bus/pci/devices/10000:01:00.0"
+"/sys/bus/pci/devices/10001:03:00.0"
+)
+FN_DEVS=(
+"/sys/bus/pci/devices/10000:01:00.1"
+"/sys/bus/pci/devices/10001:03:00.1"
+)
+tsm_devsec=""
+tsm_link=""
+devsec_pci="/sys/bus/pci/drivers/devsec_pci"
+
+tdisp_test() {
+	pci_dev=${PCI_DEVS[$1]}
+	fn_dev=${FN_DEVS[$1]}
+	host_bridge=$(dirname $(dirname $(readlink -f $pci_dev)))
+
+	# with the device disconnected from the devsec TSM validate that
+	# the devsec_pci driver loads and honors the autoprobe policy
+	echo "devsec_pci" > $pci_dev/driver_override
+	modprobe devsec_pci "autoprobe=0"
+
+	[[ -e $pci_dev/driver ]] && err "$LINENO"
+	echo $(basename $pci_dev) > $devsec_pci/bind
+	echo $(basename $pci_dev) > $devsec_pci/unbind
+
+	# grab the device's resource from /proc/iomem
+	resource=$(cat /proc/iomem | grep -m1 $(basename $pci_dev) | awk -F ' :' '{print $1}' | tr -d ' ')
+	[[ -n $resource ]] || err "$LINENO"
+
+	# lock and accept the device, validate that the resource is now
+	# marked encrypted
+	echo $(basename $tsm_devsec) > $pci_dev/tsm/lock
+	echo 1 > $pci_dev/tsm/accept
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
+validate_disconnected() {
+	pci_dev=${PCI_DEVS[$1]}
+	fn_dev=${FN_DEVS[$1]}
+	host_bridge=$(dirname $(dirname $(readlink -f $pci_dev)))
+
+	# validate that the dsm is not yet detected and that the sub-function
+	# is aware of any TSM capabilities
+	dsm=$(cat $pci_dev/tsm/dsm) || err "$LINENO from $2"
+	bound=$(cat $pci_dev/tsm/bound) || err "$LINENO from $2"
+	[[ -z $dsm ]] || err "$LINENO from $2"
+	[[ -z $bound ]] || err "$LINENO from $2"
+	[[ ! -e $fn_dev/tsm/dsm ]] || err "$LINENO from $2"
+	[[ ! -e $fn_dev/tsm/bound ]] || err "$LINENO from $2"
+	[[ ! -e $fn_dev/tsm/connect ]] || err "$LINENO from $2"
+	[[ ! -e $fn_dev/tsm/disconnect ]] || err "$LINENO from $2"
+}
+
+# check that all devices can be connected simultaneously
+ide_multi_test() {
+	for pci_dev in ${PCI_DEVS[@]}; do
+		echo $(basename $tsm_link) > $pci_dev/tsm/connect
+	done
+
+	#check stream links show up and point back to the pci_dev
+	for pci_dev in ${PCI_DEVS[@]}; do
+		host_bridge=$(dirname $(dirname $(readlink -f $pci_dev)))
+		hb=$(basename $host_bridge)
+		[[ -e $host_bridge/stream0.0.0 ]] || err "$LINENO"
+		[[ -e $tsm_link/$hb/stream0.0.0 ]] || err "$LINENO"
+		[[ $(readlink -f "$tsm_link/$hb/stream0.0.0") == $(readlink -f $pci_dev) ]] || err "$LINENO"
+	done
+
+	for pci_dev in ${PCI_DEVS[@]}; do
+		echo $(basename $tsm_link) > $pci_dev/tsm/disconnect
+	done
+}
+
+ide_test() {
+	pci_dev=${PCI_DEVS[$1]}
+	fn_dev=${FN_DEVS[$1]}
+	host_bridge=$(dirname $(dirname $(readlink -f $pci_dev)))
+
+	# validate that all of the secure streams are idle by default
+	hb=$(basename $host_bridge)
+	nr=$(cat $host_bridge/available_secure_streams)
+	[[ $nr == 4 ]] || err "$LINENO"
+
+	validate_disconnected $1 $LINENO
+
+	# connect a stream and validate that the stream link shows up at
+	# the host bridge and the TSM
+	echo $(basename $tsm_link) > $pci_dev/tsm/connect
+	nr=$(cat $host_bridge/available_secure_streams)
+	[[ $nr == 3 ]] || err "$LINENO"
+
+	[[ $(cat $pci_dev/tsm/connect) == $(basename $tsm_link) ]] || err "$LINENO"
+	[[ -e $host_bridge/stream0.0.0 ]] || err "$LINENO"
+	[[ -e $tsm_link/$hb/stream0.0.0 ]] || err "$LINENO"
+
+	# with the DSM connected (PF0), validate both it and its
+	# sub-function (PF1) populate tsm/dsm with the PF0 device.
+	dsm=$(cat $pci_dev/tsm/dsm)
+	[[ $dsm == $(basename $pci_dev) ]] || err "$LINENO"
+	dsm=$(cat $fn_dev/tsm/dsm)
+	[[ $dsm == $(basename $pci_dev) ]] || err "$LINENO"
+
+	# bind both functions and validate that they display bound to
+	# the TSM device
+	echo $(basename $pci_dev) > $tsm_link/device/tsm_bind
+	bound=$(cat $pci_dev/tsm/bound)
+	[[ $bound == $(basename $tsm_link) ]] || err "$LINENO"
+	echo $(basename $fn_dev) > $tsm_link/device/tsm_bind
+	bound=$(cat $fn_dev/tsm/bound)
+	[[ $bound == $(basename $tsm_link) ]] || err "$LINENO"
+
+	# test manual unbind
+	echo $(basename $pci_dev) > $tsm_link/device/tsm_unbind
+	bound=$(cat $pci_dev/tsm/bound)
+	[[ -z $bound ]] || err "$LINENO"
+	echo $(basename $fn_dev) > $tsm_link/device/tsm_unbind
+	bound=$(cat $fn_dev/tsm/bound)
+	[[ -z $bound ]] || err "$LINENO"
+
+	# rebind to test automatic unbind at disconnect
+	echo $(basename $pci_dev) > $tsm_link/device/tsm_bind
+	echo $(basename $fn_dev) > $tsm_link/device/tsm_bind
+
+	# check that the links disappear at disconnect and the stream
+	# pool is refilled
+	echo $(basename $tsm_link) > $pci_dev/tsm/disconnect
+	nr=$(cat $host_bridge/available_secure_streams)
+	[[ $nr == 4 ]] || err "$LINENO"
+
+	validate_disconnected $1 $LINENO
+
+	[[ $(cat $pci_dev/tsm/connect) == "" ]] || err "$LINENO"
+	[[ ! -e $host_bridge/stream0.0.0 ]] || err "$LINENO"
+	[[ ! -e $tsm_link/$hb/stream0.0.0 ]] || err "$LINENO"
+}
+
+reconnect() {
+	pci_dev=${PCI_DEVS[$1]}
+	fn_dev=${FN_DEVS[$1]}
+	host_bridge=$(dirname $(dirname $(readlink -f $pci_dev)))
+
+	# reconnect to prepare for surprise removal of the TSM or device
+	echo $(basename $tsm_link) > $pci_dev/tsm/connect
+	[[ $(cat $pci_dev/tsm/connect) == $(basename $tsm_link) ]] || err "$LINENO"
+	[[ -e $host_bridge/stream0.0.0 ]] || err "$LINENO"
+	[[ -e $tsm_link/$hb/stream0.0.0 ]] || err "$LINENO"
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
+	for i in ${!PCI_DEVS[@]}; do
+		pci_dev=${PCI_DEVS[$i]}
+		[[ -e $pci_dev ]] || err "$LINENO"
+		[[ -e $pci_dev/tsm ]] || err "$LINENO"
+	done
+
+	ide_multi_test
+	ide_test 0
+	tdisp_test 0
+
+	reconnect 0
+	teardown_modules
+}
+
+ORDER="bus"
+devsec_test
+ORDER="tsm"
+devsec_test
diff --git a/MAINTAINERS b/MAINTAINERS
index 889546f66f2f..a62b32481094 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -26541,6 +26541,7 @@ F:	include/linux/*tsm*.h
 F:	include/uapi/linux/pci-tsm-netlink.h
 F:	samples/devsec/
 F:	samples/tsm-mr/
+F:	tools/testing/devsec/
 
 TRUSTED SERVICES TEE DRIVER
 M:	Balint Dobszay <balint.dobszay@arm.com>

---

## [19] Dan Williams — 2026-03-02
*Subject: [PATCH v2 18/19] samples/devsec: Add evidence support*

For testing purposes add "certs" and "transcript" attributes to the devsec
faux devices. Both the link_tsm and devsec_tsm reference the same shared
data. The flow is:

- generate cert chain
- sign simulated evidence
- write blobs to "certs" and "transcript"
- trigger tsm/connect or tsm/lock to consume that evidence

Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 samples/devsec/devsec.h   |   5 ++
 samples/devsec/common.c   | 134 +++++++++++++++++++++++++++++++++++++-
 samples/devsec/link_tsm.c |  21 +++++-
 samples/devsec/tsm.c      |   9 ++-
 4 files changed, 166 insertions(+), 3 deletions(-)

diff --git a/samples/devsec/devsec.h b/samples/devsec/devsec.h
index e0ea9c6bb5e9..a89ce587cb3b 100644
--- a/samples/devsec/devsec.h
+++ b/samples/devsec/devsec.h
@@ -40,4 +40,9 @@ static inline int devsec_get_domain_nr(struct devsec_sysdata *sd)
 }
 #endif
 extern struct devsec_sysdata *devsec_sysdata[NR_DEVSEC_HOST_BRIDGES];
+extern const struct attribute_group devsec_evidence_group;
+void devsec_evidence_busy(void);
+void devsec_evidence_idle(void);
+struct pci_tsm_evidence;
+void devsec_init_evidence(struct pci_tsm_evidence *evidence);
 #endif /* __DEVSEC_H__ */
diff --git a/samples/devsec/common.c b/samples/devsec/common.c
index d0e8648dfe98..5dc4152e8b99 100644
--- a/samples/devsec/common.c
+++ b/samples/devsec/common.c
@@ -1,8 +1,11 @@
 // SPDX-License-Identifier: GPL-2.0-only
 /* Copyright (C) 2024 - 2026 Intel Corporation */
 
-#include <linux/pci.h>
 #include <linux/export.h>
+#include <linux/pci.h>
+#include <linux/pci-tsm.h>
+#include <linux/vmalloc.h>
+#include <uapi/linux/pci-tsm-netlink.h>
 
 #include "devsec.h"
 
@@ -13,14 +16,143 @@
 struct devsec_sysdata *devsec_sysdata[NR_DEVSEC_HOST_BRIDGES];
 EXPORT_SYMBOL_FOR_MODULES(devsec_sysdata, "devsec*");
 
+static struct {
+	void *certs;
+	size_t certs_size;
+	void *transcript;
+	size_t transcript_size;
+	int busy;
+	struct mutex lock;
+} devsec_evidence;
+
+void devsec_init_evidence(struct pci_tsm_evidence *evidence)
+{
+	struct pci_tsm_evidence_object *obj;
+
+	obj = &evidence->obj[PCI_TSM_EVIDENCE_TYPE_CERT0];
+	obj->data = devsec_evidence.certs;
+	obj->len = devsec_evidence.certs_size;
+
+	obj = &evidence->obj[PCI_TSM_EVIDENCE_TYPE_MEASUREMENTS];
+	obj->data = devsec_evidence.transcript;
+	obj->len = devsec_evidence.transcript_size;
+}
+EXPORT_SYMBOL_FOR_MODULES(devsec_init_evidence, "devsec*");
+
+static ssize_t certs_read(struct file *file, struct kobject *kobj,
+			  const struct bin_attribute *bin_attr, char *buf,
+			  loff_t off, size_t count)
+{
+	guard(mutex)(&devsec_evidence.lock);
+	return memory_read_from_buffer(buf, count, &off, devsec_evidence.certs,
+				       devsec_evidence.certs_size);
+}
+
+#define EVIDENCE_MAX_SIZE SZ_16M
+
+static ssize_t evidence_write(char *buf, loff_t off, size_t count, void **data,
+			      size_t *data_size)
+{
+	loff_t in_off = 0;
+
+	if (off + count > EVIDENCE_MAX_SIZE)
+		return -EFBIG;
+
+	guard(mutex)(&devsec_evidence.lock);
+	if (devsec_evidence.busy)
+		return -EBUSY;
+	if (off + count > *data_size) {
+		void *new_data = kvrealloc(*data, off + count, GFP_KERNEL);
+
+		if (!new_data)
+			return -ENOMEM;
+		*data = new_data;
+		*data_size = off + count;
+	}
+
+	/* reset the buffer on a single byte write */
+	if (off + count == 1) {
+		kvfree(*data);
+		*data = NULL;
+		*data_size = 0;
+		return 1;
+	}
+
+	return memory_read_from_buffer(*data + off, count, &in_off, buf, count);
+}
+
+static ssize_t certs_write(struct file *file, struct kobject *kobj,
+			   const struct bin_attribute *bin_attr, char *buf,
+			   loff_t off, size_t count)
+{
+	return evidence_write(buf, off, count, &devsec_evidence.certs,
+			      &devsec_evidence.certs_size);
+}
+
+static ssize_t transcript_read(struct file *file, struct kobject *kobj,
+			       const struct bin_attribute *bin_attr, char *buf,
+			       loff_t off, size_t count)
+{
+	guard(mutex)(&devsec_evidence.lock);
+	return memory_read_from_buffer(buf, count, &off,
+				       devsec_evidence.transcript,
+				       devsec_evidence.transcript_size);
+}
+
+static ssize_t transcript_write(struct file *file, struct kobject *kobj,
+				const struct bin_attribute *bin_attr, char *buf,
+				loff_t off, size_t count)
+{
+	return evidence_write(buf, off, count, &devsec_evidence.transcript,
+			      &devsec_evidence.transcript_size);
+}
+
+static const BIN_ATTR_RW(certs, 0);
+static const BIN_ATTR_RW(transcript, 0);
+
+static const struct bin_attribute *devsec_evidence_attrs[] = {
+	&bin_attr_certs,
+	&bin_attr_transcript,
+	NULL,
+};
+
+/*
+ * Prevent evidence from changing while any sample device is connected or locked
+ */
+void devsec_evidence_busy(void)
+{
+	guard(mutex)(&devsec_evidence.lock);
+	devsec_evidence.busy++;
+}
+EXPORT_SYMBOL_FOR_MODULES(devsec_evidence_busy, "devsec*");
+
+void devsec_evidence_idle(void)
+{
+	guard(mutex)(&devsec_evidence.lock);
+	if (devsec_evidence.busy-- <= 0) {
+		WARN_ON_ONCE(1);
+		devsec_evidence.busy = 0;
+	}
+}
+EXPORT_SYMBOL_FOR_MODULES(devsec_evidence_idle, "devsec*");
+
+const struct attribute_group devsec_evidence_group = {
+	.bin_attrs = devsec_evidence_attrs,
+};
+EXPORT_SYMBOL_FOR_MODULES(devsec_evidence_group, "devsec*");
+
 static int __init common_init(void)
 {
+	mutex_init(&devsec_evidence.lock);
 	return 0;
 }
 module_init(common_init);
 
 static void __exit common_exit(void)
 {
+	kvfree(devsec_evidence.certs);
+	kvfree(devsec_evidence.transcript);
+	mutex_destroy(&devsec_evidence.lock);
 }
 module_exit(common_exit);
 
diff --git a/samples/devsec/link_tsm.c b/samples/devsec/link_tsm.c
index 2e4c1234bdee..21b6c3c7ea52 100644
--- a/samples/devsec/link_tsm.c
+++ b/samples/devsec/link_tsm.c
@@ -3,6 +3,7 @@
 
 #define dev_fmt(fmt) "devsec: " fmt
 #include <linux/device/faux.h>
+#include <crypto/hash_info.h>
 #include <linux/pci-tsm.h>
 #include <linux/pci-ide.h>
 #include <linux/module.h>
@@ -51,6 +52,8 @@ static struct device *pci_tsm_host(struct pci_dev *pdev)
 static struct pci_tsm *devsec_tsm_pf0_probe(struct tsm_dev *tsm_dev,
 					    struct pci_dev *pdev)
 {
+	struct pci_tsm_evidence *evidence;
+	struct pci_tsm *tsm;
 	int rc;
 
 	dev_dbg(tsm_dev->dev.parent, "%s\n", pci_name(pdev));
@@ -60,10 +63,16 @@ static struct pci_tsm *devsec_tsm_pf0_probe(struct tsm_dev *tsm_dev,
 	if (!devsec_tsm)
 		return NULL;
 
+	tsm = &devsec_tsm->pci.base_tsm;
 	rc = pci_tsm_pf0_constructor(pdev, &devsec_tsm->pci, tsm_dev);
 	if (rc)
 		return NULL;
 
+	devsec_evidence_busy();
+	evidence = &tsm->evidence;
+	pci_tsm_init_evidence(evidence, 0, HASH_ALGO_SHA384);
+	devsec_init_evidence(evidence);
+
 	pci_dbg(pdev, "TSM enabled\n");
 	return &no_free_ptr(devsec_tsm)->pci.base_tsm;
 }
@@ -113,6 +122,7 @@ static void devsec_link_tsm_pci_remove(struct pci_tsm *tsm)
 	if (is_pci_tsm_pf0(pdev)) {
 		struct devsec_tsm_pf0 *devsec_tsm = to_devsec_tsm_pf0(tsm);
 
+		devsec_evidence_idle();
 		pci_tsm_pf0_destructor(&devsec_tsm->pci);
 		kfree(devsec_tsm);
 	} else {
@@ -390,7 +400,16 @@ static struct attribute *devsec_link_attrs[] = {
 	&dev_attr_tsm_request.attr,
 	NULL,
 };
-ATTRIBUTE_GROUPS(devsec_link);
+
+static const struct attribute_group devsec_link_group = {
+	.attrs = devsec_link_attrs,
+};
+
+static const struct attribute_group *devsec_link_groups[] = {
+	&devsec_link_group,
+	&devsec_evidence_group,
+	NULL,
+};
 
 static int __init devsec_link_tsm_init(void)
 {
diff --git a/samples/devsec/tsm.c b/samples/devsec/tsm.c
index 46dbe668945a..4a62e05ecf35 100644
--- a/samples/devsec/tsm.c
+++ b/samples/devsec/tsm.c
@@ -6,6 +6,7 @@
 #include <linux/pci-tsm.h>
 #include <linux/module.h>
 #include <linux/pci.h>
+#include <linux/sysfs.h>
 #include <linux/tsm.h>
 #include "devsec.h"
 
@@ -105,9 +106,15 @@ static const struct faux_device_ops devsec_device_ops = {
 	.probe = devsec_tsm_probe,
 };
 
+static const struct attribute_group *devsec_evidence_groups[] = {
+	&devsec_evidence_group,
+	NULL,
+};
+
 static int __init devsec_tsm_init(void)
 {
-	devsec_tsm = faux_device_create("devsec_tsm", NULL, &devsec_device_ops);
+	devsec_tsm = faux_device_create_with_groups(
+		"devsec_tsm", NULL, &devsec_device_ops, devsec_evidence_groups);
 	if (!devsec_tsm)
 		return -ENOMEM;
 	return 0;

---

## [20] Dan Williams — 2026-03-02
*Subject: [PATCH v2 19/19] tools/testing/devsec: Add basic evidence retrieval validation*

Checkout basic operation of the pci-tsm-netlink ABI. The main complexity is
reassembly of single evidence payloads that span multiple messages.

Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 tools/testing/devsec/devsec.sh | 46 ++++++++++++++++++++++++++++++++++
 1 file changed, 46 insertions(+)

diff --git a/tools/testing/devsec/devsec.sh b/tools/testing/devsec/devsec.sh
index ce4a986b74dd..6a9313e7104f 100755
--- a/tools/testing/devsec/devsec.sh
+++ b/tools/testing/devsec/devsec.sh
@@ -126,6 +126,46 @@ ide_multi_test() {
 	done
 }
 
+check_evidence() {
+	pci_dev=$1
+
+	set +x
+
+	python3 tools/net/ynl/pyynl/cli.py --family pci-tsm --dump evidence-read \
+	--json "{\"type-mask\": 2047, \"dev-name\": \"$(basename $pci_dev)\", \"flags\": 0}" \
+	--output-json > json
+
+	# Coalesce multi-message payloads where the protocol is a tuple
+	# of (type, val) followed by one more (val) only messages.
+	objects=()
+	for obj in $(jq -c '.[]' json); do
+		if [[ $(echo $obj | jq -r 'has("type")') == "true" ]]; then
+			t=$(echo $obj | jq -r '.type')
+			val_len=$(echo $obj | jq -r '.val | length')
+			objects[$t]=$val_len
+		else
+			val_len=$(echo $obj | jq -r '.val | length')
+			objects[$t]=$((objects[$t] + val_len))
+		fi
+	done
+
+	# Check that all 11 objects (PCI_TSM_EVIDENCE_TYPE_MAX) were
+	# returned and only objects 0 and 9
+	# (PCI_TSM_EVIDENCE_TYPE_CERT0,
+	# PCI_TSM_EVIDENCE_TYPE_MEASUREMENTS) have a length of 8192 and
+	# the rest are empty.
+	[[ ${#objects[@]} -eq 11 ]] || err "$LINENO"
+	for i in ${!objects[@]}; do
+		if [[ $i == 0 || $i == 9 ]]; then
+			[[ ${objects[$i]} == 8192 ]] || err "$LINENO"
+		else
+			[[ ${objects[$i]} == 0 ]] || err "$LINENO"
+		fi
+	done
+
+	set -x
+}
+
 ide_test() {
 	pci_dev=${PCI_DEVS[$1]}
 	fn_dev=${FN_DEVS[$1]}
@@ -155,6 +195,8 @@ ide_test() {
 	dsm=$(cat $fn_dev/tsm/dsm)
 	[[ $dsm == $(basename $pci_dev) ]] || err "$LINENO"
 
+	check_evidence $pci_dev
+
 	# bind both functions and validate that they display bound to
 	# the TSM device
 	echo $(basename $pci_dev) > $tsm_link/device/tsm_bind
@@ -213,6 +255,10 @@ devsec_test() {
 	[[ -n $tsm_devsec ]] || err "$LINENO"
 	[[ -n $tsm_link ]] || err "$LINENO"
 
+	# initialize evidence payloads
+	dd if=/dev/zero of=/sys/bus/faux/devices/devsec_link_tsm/certs bs=4K count=1
+	dd if=/dev/zero of=/sys/bus/faux/devices/devsec_link_tsm/transcript bs=4K count=1
+
 	# check that devsec bus loads correctly and the TSM is detected
 	for i in ${!PCI_DEVS[@]}; do
 		pci_dev=${PCI_DEVS[$i]}

---

## [21] kernel test robot — 2026-03-03
*Subject: Re: [PATCH v2 08/19] PCI/TSM: Add "evidence" support*

Hi Dan,

kernel test robot noticed the following build warnings:

[auto build test WARNING on c2012263047689e495e81c96d7d5b0586299578d]

url:    https://github.com/intel-lab-lkp/linux/commits/Dan-Williams/PCI-TSM-Report-active-IDE-streams-per-host-bridge/20260303-080409
base:   c2012263047689e495e81c96d7d5b0586299578d
patch link:    https://lore.kernel.org/r/20260303000207.1836586-9-dan.j.williams%40intel.com
patch subject: [PATCH v2 08/19] PCI/TSM: Add "evidence" support
compiler: clang version 20.1.8 (https://github.com/llvm/llvm-project 87f0227cb60147a26a1eeb4fb06e3b505e9c7261)
docutils: docutils (Docutils 0.21.2, Python 3.13.5, on linux)
reproduce: (https://download.01.org/0day-ci/archive/20260303/202603030451.0ZpbO6ex-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202603030451.0ZpbO6ex-lkp@intel.com/

All warnings (new ones prefixed by >>):

   Warning: tools/docs/documentation-file-ref-check references a file that doesn't exist: m,^Documentation/scheduler/sched-pelt
   Warning: tools/docs/documentation-file-ref-check references a file that doesn't exist: m,(Documentation/translations/[
   Using alabaster theme
   WARNING: ./include/crypto/skcipher.h:166 struct member 'SKCIPHER_ALG_COMMON' not described in 'skcipher_alg'
   Documentation/driver-api/pci/tsm:147: ./include/linux/pci-tsm.h:112: ERROR: Unexpected indentation. [docutils]
>> Documentation/driver-api/pci/tsm:147: ./include/linux/pci-tsm.h:113: WARNING: Block quote ends without a blank line; unexpected unindent. [docutils]
>> Documentation/driver-api/pci/tsm:147: ./include/linux/pci-tsm.h:116: WARNING: Definition list ends without a blank line; unexpected unindent. [docutils]
   ERROR: Cannot find file ./drivers/pci/tsm.c
   ERROR: Cannot find file ./drivers/pci/tsm.c
   WARNING: No kernel-doc for file ./drivers/pci/tsm.c
   WARNING: ./include/linux/virtio.h:183 struct member 'map' not described in 'virtio_device'
   WARNING: ./include/linux/virtio.h:183 struct member 'VIRTIO_DECLARE_FEATURES(features' not described in 'virtio_device'

---

## [22] Baolu Lu — 2026-03-03
*Subject: Re: [PATCH v2 07/19] PCI/TSM: Add Device Security (TVM Guest) ACCEPT
 operation support*

On 3/3/26 08:01, Dan Williams wrote:
> The final operation of the PCIe Trusted Execution Environment (TEE) Device
> Interface Security Protocol (TDISP) is asking the TEE Security Manager

Nit: remove the typo extra 'the'

"...and arrange for the secure IOMMU to..."

> +		accept requests with T=1 in the PCIe packet header (TLP)
> +		targeting private memory. Per TDISP the only exits from the RUN

Thanks,
baolu

---

## [23] Alexey Kardashevskiy — 2026-03-03
*Subject: Re: [PATCH v2 11/19] x86, dma: Allow accepted devices to map private
 memory*

On 3/3/26 11:01, Dan Williams wrote:
> With the arrival of "accepted" devices, devices that have been enabled to
> DMA to private encrypted memory, coherent DMA allocation no longer requires

Reviewed-by: Alexey Kardashevskiy <aik@amd.com>

> ---
>   arch/x86/mm/mem_encrypt.c | 5 +++--

---

## [24] Aneesh Kumar K.V — 2026-03-03
*Subject: Re: [PATCH v2 10/19] x86, swiotlb: Teach swiotlb to skip "accepted"
 devices*

Dan Williams <dan.j.williams@intel.com> writes:

> There are two mechanisms to force SWIOTLB operation, the kernel command
> line option and the internal SWIOTLB_FORCE flag. With the arrival of

This should be.

@@ -373,7 +373,7 @@ void __init swiotlb_init_remap(bool addressing_limit, unsigned int flags,
 
 	io_tlb_default_mem.force_bounce =
 		swiotlb_force_bounce || (flags & SWIOTLB_FORCE);
-	io_tlb_default_mem.bounce_unaccepted = flags & SWIOTLB_UNACCEPTED;
+	io_tlb_default_mem.bounce_unaccepted = !!(flags & SWIOTLB_UNACCEPTED);
 
>  
>  #ifdef CONFIG_SWIOTLB_DYNAMIC

---

## [25] Aneesh Kumar K.V — 2026-03-03
*Subject: Re: [PATCH v2 00/19] PCI/TSM: TEE I/O infrastructure*

Dan Williams <dan.j.williams@intel.com> writes:

....

To support devices without  IDE/DOE support we need something similar. 

modified   drivers/pci/tsm/core.c
@@ -1236,12 +1236,14 @@ int pci_tsm_pf0_constructor(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm,
 			    struct tsm_dev *tsm_dev)
 {
 	mutex_init(&tsm->lock);
-	tsm->doe_mb = pci_find_doe_mailbox(pdev, PCI_VENDOR_ID_PCI_SIG,
-					   PCI_DOE_FEATURE_CMA);
-	if (!tsm->doe_mb) {
-		pci_warn(pdev, "TSM init failure, no CMA mailbox\n");
-		return -ENODEV;
-	}
+
+       /*
+        * Note, low-level TSM driver responsible for determining if it wants to
+        * proceed with a device that has no DOE mailbox. TSM may have an
+        * alternate method for coordinating TDISP.
+        */
+       if (!tsm->doe_mb)
+               pci_dbg(pdev, "no CMA mailbox\n");
 
 	return pci_tsm_link_constructor(pdev, &tsm->base_tsm, tsm_dev);
 }

---

## [26] Aneesh Kumar K.V — 2026-03-03
*Subject: Re: [PATCH v2 08/19] PCI/TSM: Add "evidence" support*

Dan Williams <dan.j.williams@intel.com> writes:

> Once one accepts the threat model that devices may be adversarial the
> process of establishing trust in the device identity, the integrity +

In the case of CCA, the slot number is determined early, when we create
the pdev object that maps to PF0. This is done as part of the connect
callback. Currently, the slot number is hardcoded to 0. I believe we
need to extend connect to include slot information.

Even with that change, we would only have one certificate type.
These would correspond to whichever slot number was selected during
connect.


-aneesh

---

## [27] Aneesh Kumar K.V — 2026-03-03
*Subject: Re: [PATCH v2 08/19] PCI/TSM: Add "evidence" support*

Dan Williams <dan.j.williams@intel.com> writes:

> Once one accepts the threat model that devices may be adversarial the
> process of establishing trust in the device identity, the integrity +

Should we also expose evidence->generation to userspace so it can be
used during accept()? This would allow us to ensure that the device is
accepted using the same evidence generation observed by userspace.

-aneesh

---

## [28] dan.j.williams@intel.com — 2026-03-03
*Subject: Re: [PATCH v2 00/19] PCI/TSM: TEE I/O infrastructure*

Aneesh Kumar K.V wrote:
> Dan Williams <dan.j.williams@intel.com> writes:
> 

A patch like patch can go upstream now. Care to send?

---

## [29] dan.j.williams@intel.com — 2026-03-04
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

Dan Williams wrote:
> After pci_tsm_bind() and pci_tsm_lock() the low level TSM driver is
> expected to populate PCI_TSM_EVIDENCE_TYPE_REPORT in its evidence store.
[..]
> +/**
> + * pci_tsm_mmio_alloc() - allocate encrypted MMIO range descriptor

Is this going to cause any implementation to need to copy the buffer
received from the low-level TSM? If so I would just mark 'struct
pci_tsm_devif_report' and 'struct pci_tsm_mmio_entry' as __packed and
drop this check.

> +
> +	report = report_obj->data;

Whoops, these pfn to absolute address conversions were already performed above, will fix.

---

## [30] Aneesh Kumar K.V — 2026-03-05
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

Dan Williams <dan.j.williams@intel.com> writes:

> After pci_tsm_bind() and pci_tsm_lock() the low level TSM driver is
> expected to populate PCI_TSM_EVIDENCE_TYPE_REPORT in its evidence store.
....
> +		range_off = tsm_offset - reporting_bar_base;
> 
range_off will always be zero? Should we do

 		range_off = tsm_offset & (pci_resource_len(pdev, bar) - 1);


So that we correctly handle if the interface report is reporting a range
within a bar. The only requirement here is bar address should be aligned
to its size and mmio_reporting_offset should not add offsets in that range.

> +
> +		last_reporting_end = tsm_offset + size;

---

## [31] Jonathan Cameron — 2026-03-09
*Subject: Re: [PATCH v2 01/19] PCI/TSM: Report active IDE streams per host
 bridge*

On Mon,  2 Mar 2026 16:01:49 -0800
Dan Williams <dan.j.williams@intel.com> wrote:

> The first attempt at an ABI for this failed to account for naming
> collisions across host bridges:

> diff --git a/drivers/virt/coco/tsm-core.c b/drivers/virt/coco/tsm-core.c
> index 8712df8596a1..3c99c38cfaa5 100644

> +
> +static struct tsm_ide_stream *create_streams(struct tsm_dev *tsm_dev,

Crossed with kzalloc_obj() etc being introduced which seems appropriate here.
 
> +	if (!streams)
> +		return NULL;

---

## [32] Jonathan Cameron — 2026-03-09
*Subject: Re: [PATCH v2 02/19] device core: Fix kernel-doc warnings in base.h*

On Mon,  2 Mar 2026 16:01:50 -0800
Dan Williams <dan.j.williams@intel.com> wrote:

> In preparation for adding new fields to 'struct device_private' fix up
> existing kernel-doc warnings in this header file of the form:

Maybe if the rest looks 'slow' can send this one ahead?

Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>


Jonathan

---

## [33] Jonathan Cameron — 2026-03-09
*Subject: Re: [PATCH v2 03/19] device core: Introduce confidential device
 acceptance*

On Mon,  2 Mar 2026 16:01:51 -0800
Dan Williams <dan.j.williams@intel.com> wrote:

> An "accepted" device is one that is allowed to access private memory within
> a Trusted Computing Boundary (TCB). The concept of "acceptance" is distinct
Seems reasonable to me.
Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

---

## [34] Jonathan Cameron — 2026-03-09
*Subject: Re: [PATCH v2 05/19] device core: Autoprobe considered harmful?*

On Mon,  2 Mar 2026 16:01:53 -0800
Dan Williams <dan.j.williams@intel.com> wrote:

> The threat model of PCI Trusted Execution Environment Device Interface
> Security Protocol (TDISP), is that an adversary may be impersonating the
Approach seems reasonable to me.
A few trivial things inline.

Jonathan

> ---
>  drivers/base/Kconfig                  | 24 ++++++++++++++++++++++++

Stray extra space.

> +	  unaffected by this policy and will autoprobe unless the bus itself has
> +	  disabled autoprobe.


> diff --git a/drivers/base/dd.c b/drivers/base/dd.c
> index 349f31bedfa1..926e120b3cc4 100644

I'm not sure 'initial' naming works.  How does that work with drivers that
have not autobound anyway?  E.g. VFIO.
Seems they'll be fine even if it is their initial probe.  Also the
deferred cases remain 'initial' for repeated probing.

Why not stick to the auto probing terminology here?

There is clearly history of this naming though in device_initial_probe()
So maybe that name is fine...


>  };
>

---

## [35] Greg KH — 2026-03-12
*Subject: Re: [PATCH v2 03/19] device core: Introduce confidential device
 acceptance*

On Mon, Mar 02, 2026 at 04:01:51PM -0800, Dan Williams wrote:
> An "accepted" device is one that is allowed to access private memory within
> a Trusted Computing Boundary (TCB). The concept of "acceptance" is distinct

Trying to mix/match "acceptance" with "authorized" is going to be a
nightmare, what's the combination that can happen here over time?

We need to either "trust" or "not trust" the device, and the bus can
decide what to do with that value (if anything).  The DMA layer can then
use that value to do:

> Subsystems like the DMA mapping layer, that need to modify their behavior
> based on the accept state, may only have access to the base 'struct

^this.

> It is also likely that the concept of TCB acceptance grows beyond
> PCI devices over time. For these reasons, introduce the concept of

Busses are what can control this, but please, let's not make this a
cc-only type thing.  We have the idea of trust starting to propagate
through a number of different busses, let's get it right here, so we
don't have to have all of these different bus-specific hacks like we do
today.

> Cc: Christoph Hellwig <hch@lst.de>
> Cc: Jason Gunthorpe <jgg@ziepe.ca>

Just make this:
	u8 trusted:1;

no need for an #ifdef.


> +
>  };

No __must_hold() usage?  That's best to check this at build time, not
just relying on:

> +{
> +	lockdep_assert_held(&dev->mutex);

runtime checks.

Same for all the calls here.

> +/**
> + * device_cc_accept(): Mark a device as able to access private memory

So you are saying that once a driver is bound, it is "trusted"?  That's
fine, but maybe you don't want to do that in the core, shouldn't that be
a bus-specific thing?

this could then be:
int device_trust(struct device *dev);
int device_untrust(struct device *dev);  /* ugh, bad name, pick something else? */
bool device_trusted(struct device *dev);

but note, do you ever want to move a device from trusted to untrusted?
What would cause that?

thanks,

greg k-h

---

## [36] Greg KH — 2026-03-12
*Subject: Re: [PATCH v2 02/19] device core: Fix kernel-doc warnings in base.h*

On Mon, Mar 09, 2026 at 04:39:32PM +0000, Jonathan Cameron wrote:
> On Mon,  2 Mar 2026 16:01:50 -0800
> Dan Williams <dan.j.williams@intel.com> wrote:
 
I can takt this now, thanks.

greg k-h

---

## [37] Dan Williams — 2026-03-12
*Subject: Re: [PATCH v2 03/19] device core: Introduce confidential device
 acceptance*

Greg KH wrote:
> On Mon, Mar 02, 2026 at 04:01:51PM -0800, Dan Williams wrote:
> > An "accepted" device is one that is allowed to access private memory within

I do think Linux needs to mix/match these concepts. "Authorization" is a
kernel policy to operate a device at all. "Acceptance" is a mechanism
to operate a device within a hardware TCB boundary.

So, the truth table of combinations would be:

accepted	authorized	result
0		0		logically and physically disconnected device

0		1		connected device, DMA is bounce buffered
				and loses confidentiality, integrity,
				and performance

1		0		logically disconnected device, but a
				relying party trusts that the device is
				not spoofing authorization.

1		1		connected device, DMA is direct and gains
				confidentiality, integrity and performance

To say it another way, when the above distinguishes "logically" vs
"physically" disconnected it is whether the device interface can be
verified to not be under adversarial control. An unaccepted device can
do limited damage, but still can bounce buffer secrets out of the TCB if
so directed.

> We need to either "trust" or "not trust" the device, and the bus can
> decide what to do with that value (if anything).  The DMA layer can then

Trust is separate. For example, there are deployed use cases today where
the device is trusted, but unaccepted. Acceptance support for those
cases is mostly a performance optimization to be able to stop performing
software encryption on top of DMA bounce buffering.

> > Subsystems like the DMA mapping layer, that need to modify their behavior
> > based on the accept state, may only have access to the base 'struct

The DMA layer is not operating on a trust concept it is effectively
being told to select an IOMMU.

> > It is also likely that the concept of TCB acceptance grows beyond
> > PCI devices over time. For these reasons, introduce the concept of

The conflation of "trust" and "acceptance" has been the main stumbling
block of past proposals. As you have said before "kernel drivers trust
their devices". That precedent is not being touched in this proposal.
Instead, give userspace all the tools it needs to deploy policy about
when to operate a device. When it does decide to operate the device give
it the mechanism to add confidentiality, integrity and performance to
that operation.

This is a "CC-only type thing" because only CC partitions the system
into two device domains. One where "trusted unaccepted" devices can
operate without CC protections and "trusted accepted" devices can
operate with CC protections and direct DMA.

> 
> > Cc: Christoph Hellwig <hch@lst.de>

Ok.

> 
> 

Ok, will take a look and convert.

> > +/**
> > + * device_cc_accept(): Mark a device as able to access private memory

No, per above this not about trust. This is about the fact that the
device can not switch between DMA/IOMMU and encrypted MMIO operational
models while it may have active DMA or MMIO mappings. So the check here
is to observe that the mechanism of toggling inside / outside TCB
operation is so violent as to not be something that can change while the
device is being operated by a driver.

> 
> this could then be:

Moving to unaccepted operation is when any detail that the relying party
used to make "accept" decision changed. For example, the device moves
to the ERROR security state from severe events like PCIe link encryption
loss, to modest events like the host VMM toggled the bus-master-enable
bit in the physical function's command register.

So error recovery takes the device from RUN to ERROR before it can be
transitioned back to LOCK then RUN (accepted). But also a coordinated
firmware update would need to take the device from RUN to UNLOCKED to
LOCKED (revalidate device evidence) back to RUN.

---

## [38] Xu Yilun — 2026-03-13
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

> > +	if (dev_WARN_ONCE(&tsm_dev->dev, !IS_ALIGNED((unsigned long) report_obj->data, 8),
> > +			  "misaligned report data\n"))

TDX Connect needs the copy, the GHCI header is 20 byte size, not
naturally aligned...

> pci_tsm_devif_report' and 'struct pci_tsm_mmio_entry' as __packed and
> drop this check.

..But since this series will persist the report blob long term in
tsm.evidence.obj[PCI_TSM_EVIDENCE_TYPE_REPORT], we anyway need to copy
the blob out from temporary shared GHCI communication buffer. So it is
actually good to me.

---

## [39] Xu Yilun — 2026-03-13
*Subject: Re: [PATCH v2 08/19] PCI/TSM: Add "evidence" support*

> +void pci_tsm_init_evidence(struct pci_tsm_evidence *evidence, int slot,
> +			   enum hash_algo digest_algo)

IIUC, this function is for link tsm driver, is it? But in the following
patch, devsec tsm would consume pci_tsm_mmio_alloc() which uses
evidence->lock. So my solution is to initialize the lock on tsm
construction.

--------8<--------
diff --git a/drivers/pci/tsm/core.c b/drivers/pci/tsm/core.c
index 9f062218c312..c55deeafe32b 100644
--- a/drivers/pci/tsm/core.c
+++ b/drivers/pci/tsm/core.c
@@ -1175,7 +1175,6 @@ void pci_tsm_init_evidence(struct pci_tsm_evidence *evidence, int slot,
        evidence->slot = slot;
        evidence->generation = 1;
        evidence->digest_algo = digest_algo;
-       init_rwsem(&evidence->lock);
 }
 EXPORT_SYMBOL_GPL(pci_tsm_init_evidence);

@@ -1198,6 +1197,7 @@ int pci_tsm_link_constructor(struct pci_dev *pdev, struct pci_tsm *tsm,
        }
        tsm->pdev = pdev;
        tsm->tsm_dev = tsm_dev;
+       init_rwsem(&tsm->evidence.lock);

        return 0;
 }
@@ -1221,6 +1221,7 @@ int pci_tsm_devsec_constructor(struct pci_dev *pdev, struct pci_tsm_devsec *tsm,
        pci_tsm->tdi = NULL;
        pci_tsm->pdev = pdev;
        pci_tsm->tsm_dev = tsm_dev;
+       init_rwsem(&pci_tsm->evidence.lock);

        return 0;
 }

---

## [40] Xu Yilun — 2026-03-13
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

> > +		if (last_bar < bar) {
> > +			/* transition to a new bar */

tsm_offset comes from Device Interface Report, MMIO RANGE, First 4k
Page. How do you interpret the exact meaning of this field?

My understanding is, it is the obfuscated host start pfn of this range,
if this range has offset to the BAR start, this field should also be
offsetted.

But if the first range in the BAR should be aligned to BAR, otherwise
there is no way for guest to position the range in the BAR.

So the logic here is:

  reporting_bar_base:	the first obfuscated pfn for the BAR, the BAR pfn
  tsm_offset:		the current obfucated pfn for the BAR.
  tsm_offset - reporting_bar_base: the offset to the BAR.

> 
>  		range_off = tsm_offset & (pci_resource_len(pdev, bar) - 1);

---

## [41] Xu Yilun — 2026-03-13
*Subject: Re: [PATCH v2 10/19] x86, swiotlb: Teach swiotlb to skip "accepted"
 devices*

> > @@ -365,6 +365,7 @@ void __init swiotlb_init_remap(bool addressing_limit, unsigned int flags,
> >  

Ah yes, I just realized assigning to a 1-bit field would truncate the
assigned value to its LSB...

---

## [42] Greg KH — 2026-03-13
*Subject: Re: [PATCH v2 03/19] device core: Introduce confidential device
 acceptance*

On Thu, Mar 12, 2026 at 09:11:32PM -0700, Dan Williams wrote:
> Greg KH wrote:
> > On Mon, Mar 02, 2026 at 04:01:51PM -0800, Dan Williams wrote:

I really don't agree with this, but I can't think of why at the moment.
I feel like you are looking at this purely in the TCB point of view,
while I don't feel that is something that should be considered "special"
at all here.  Linux has, for the most part, always trusted the hardware,
and now you are wanting to not trust the hardware for some things and
parts of the kernel.  Which is great, it's something that I have wanted
to change for a very long time now, but let's do it right if at all
possible.

Give me a few days to come up with a better reply, let me think about
this some more...

> > We need to either "trust" or "not trust" the device, and the bus can
> > decide what to do with that value (if anything).  The DMA layer can then

If "acceptance" is just a performance issue, I think you all need to go
back to the marketing people as that's probably not what they intended
to have happen here.  For some reason I thought they were selling this
as "security", not "speed" :)

> > > Subsystems like the DMA mapping layer, that need to modify their behavior
> > > based on the accept state, may only have access to the base 'struct

Ok, then that's independent of "acceptance", that is "use this IOMMU vs.
that one" type of thing which is just a "basic configuration for speed"
type of thing as you mention above :)

Let's not confuse that with anything else like "acceptance" please.

> > > It is also likely that the concept of TCB acceptance grows beyond
> > > PCI devices over time. For these reasons, introduce the concept of

Ah, but I WANT to touch that.  Let's FINALLY solve that!  Or at the very
least, provide the infrastructure in the driver core to allow busses
that want to do that, to be able to do so.

> Instead, give userspace all the tools it needs to deploy policy about
> when to operate a device. When it does decide to operate the device give

Yes, this is a policy decision, and if you are only saying this is about
"which IOMMU should we select", then that's a dma layer configuration
option.  Let's not call that "acceptance" please.

> This is a "CC-only type thing" because only CC partitions the system
> into two device domains. One where "trusted unaccepted" devices can

In other words, it's an IOMMU switch, so why not use the switch
infrastructure?  </me runs away...>

anyway, let me think about this some more...

thanks,

greg k-h

---

## [43] Jason Gunthorpe — 2026-03-13
*Subject: Re: [PATCH v2 03/19] device core: Introduce confidential device
 acceptance*

On Thu, Mar 12, 2026 at 09:11:32PM -0700, Dan Williams wrote:
> Greg KH wrote:
> > On Mon, Mar 02, 2026 at 04:01:51PM -0800, Dan Williams wrote:

I'm not sure about these words either, I would revise your table to be
more OS centric, the device can be in one of four security levels:

0 Blocked and disabled
  The device cannot attack the system, enforced by the OS not loading a
  driver or mapping the MMIO and IOMMU fully blocking everything from it.

1 In use, attacks from a hostile device are possible
  A driver can operate the device and is expected to defend against
  attacks from the device itself. The IOMMU restricts the device to only
  access driver approved data (no ATS, DMA strict only, CC shared
  only, interrupt remapping security, bounce partial DMA mappings, etc)

2 In use, no attacks from the device
  The device does what the driver says and is not hostile. The driver
  does not have to defend itself, the IOMMU can run in faster & lower
  security modes (ATS on, DMA-FQ, Identity, still CC shared only)
   * Basically our default security level today

3 In use, no attacks, and access to CC private memory
  Like #2 and now the IOMMU allows access to CC private memory too.

[*] I'm inclunding all attacks with "hostile device", including MIM on
the PCIe link, compromised/fake device, attacks from a VMM through a
virtual device, etc.

From a CC VM perspective 0 is at boot, 1 is an out of TCB device, 2
doesn't exist (without TDISP there is no way to keep the
hypervisor from attacking?), and 3 is a full accepted TDSIP device.

#2 can happen in bare metal where a OS may activate link encryption
and attest the device, but doesn't have CC private/shared memory.

From a uAPI perspective I'm not sold on having two bools, I think a
level string would be more flexible. TSM and CC properties are
orthogonal, except you can't select #3 without the TSM saying it is in
RUN.

Internally we'd probably turn that dev->trusted thing into an
enum and teach the iommu layer to treat it more dynamically.

Jason

---

## [44] Jason Gunthorpe — 2026-03-13
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

On Fri, Mar 13, 2026 at 06:23:51PM +0800, Xu Yilun wrote:

> My understanding is, it is the obfuscated host start pfn of this range,
> if this range has offset to the BAR start, this field should also be

The OS must get an idea of the bar layout out of the report, so there
have to be restrictions on how it is formed otherwise it is
unparsible. IMHO the PCI spec created this very general mechanism but
the CPU CC specs need to constrain it to be usable by an OS.

> >  		range_off = tsm_offset & (pci_resource_len(pdev, bar) - 1);
> > 

Right.

Jason

---

## [45] Dan Williams — 2026-03-13
*Subject: Re: [PATCH v2 08/19] PCI/TSM: Add "evidence" support*

Xu Yilun wrote:
> > +void pci_tsm_init_evidence(struct pci_tsm_evidence *evidence, int slot,
> > +			   enum hash_algo digest_algo)

It is meant to be generic for both, and an "optional" support
library for the low-level TSM drivers.

- Host PCI/TSM evidence interface collects the blobs
- Guest PCI/TSM evidence interface retrieves the digests via private TSM
  GHCI
- Some infrastructure (either arch specific GHCI or new common GHCI)
  pushes the blobs from Host to Guest so that guest PCI/TSM evidence
gathering can also get the blobs.

> But in the following patch, devsec tsm would consume
> pci_tsm_mmio_alloc() which uses evidence->lock. So my solution is to

So I did flub the "->evidence == 0" check, and yes initializing the lock
by default looks like the right answer to that problem.

---

## [46] Dan Williams — 2026-03-13
*Subject: Re: [PATCH v2 03/19] device core: Introduce confidential device
 acceptance*

Greg KH wrote:
> On Thu, Mar 12, 2026 at 09:11:32PM -0700, Dan Williams wrote:
> > Greg KH wrote:

I think framing "trust" as an enum rather than a boolean better
addresses this problem.

> for some things and parts of the kernel.  Which is great, it's
> something that I have wanted to change for a very long time now, but

Sure, but I also think we might already be converging, more below...

> > > We need to either "trust" or "not trust" the device, and the bus can
> > > decide what to do with that value (if anything).  The DMA layer can then

Do not get me wrong there are several threat models mitigated by having
hardware assurance that all communications with the device are
confidentiality and integrity protected. Hardware assurances that
attempts to subvert those protections result in hardware error states is
part of the value. However, you can approximate a subset of those
protections with high overhead workarounds.

> > > > Subsystems like the DMA mapping layer, that need to modify their behavior
> > > > based on the accept state, may only have access to the base 'struct

That is fine, and I think you and Jason may be hitting on the same
concern.

> 
> > > > It is also likely that the concept of TCB acceptance grows beyond

Jason's framing of an enum rather than a boolean for "trust" seems
workable to me and melds "authorization" and "CC acceptance" into one
concept.

> > Instead, give userspace all the tools it needs to deploy policy about
> > when to operate a device. When it does decide to operate the device give

Done.

...and there is precedent for a "trust" enum, lockdown levels. In that
case as well there are a menu of priveleges that can be incrementally
enabled by a policy.

> > This is a "CC-only type thing" because only CC partitions the system
> > into two device domains. One where "trusted unaccepted" devices can

Will do, however in the meantime I am going to speculate that this "trust
as enum" idea is workable and start drafting some patches towards that.

---

## [47] Jason Gunthorpe — 2026-03-13
*Subject: Re: [PATCH v2 03/19] device core: Introduce confidential device
 acceptance*

On Fri, Mar 13, 2026 at 11:53:11AM -0700, Dan Williams wrote:

> Jason's framing of an enum rather than a boolean for "trust" seems
> workable to me and melds "authorization" and "CC acceptance" into one

I think you can also fold the auto-probe into this as well.

The kernel would have some default policy for what enum value to set
upon discovery and instead of 'disable auto probe' you'd arrange to
set trust level 0 which would block driver binding and probing
inherently.

Policy in userspace then has to increase the trust level which could
trigger an auto-bind.

> > > Instead, give userspace all the tools it needs to deploy policy about
> > > when to operate a device. When it does decide to operate the device give

AFAICT "which IOMMU should we select" should entirely be driven by the
TDISP state being in RUN

Jason

---

## [48] Dan Williams — 2026-03-13
*Subject: Re: [PATCH v2 03/19] device core: Introduce confidential device
 acceptance*

Jason Gunthorpe wrote:
> On Thu, Mar 12, 2026 at 09:11:32PM -0700, Dan Williams wrote:
> > Greg KH wrote:

I like this framing.

> 0 Blocked and disabled
>   The device cannot attack the system, enforced by the OS not loading a

In terms of details I am trying to think through whether the device
actually changes its ->trust level in reaction to a driver attaching, or
whether the block and disabled state is implicit in not being driver
bound.

It does strike me that this value could be used to convey whether a
given arch's IOMMU driver indeed arranges for devices to be IOMMU
blocked while driver detached. In that case you could see, "oh, devices
are not DMA blocked by default" as we talked about in the ATS-always-on
thread [1].

[1]: http://lore.kernel.org/20260128130520.GV1134360@nvidia.com

> 1 In use, attacks from a hostile device are possible
>   A driver can operate the device and is expected to defend against

This is a better way to convey the current "force_swiotlb" settings that
TVMs deploy in their arch code.

> 2 In use, no attacks from the device
>   The device does what the driver says and is not hostile. The driver

I am assuming that each bus implementation may have a different way to
get the device to the various trust levels.

For example, the uAPI for PCI TDISP requires associating a device with a
TSM and asking the TSM to push the device to trust level 3. Another bus
like thunderbolt may want to imply that "authorized" that uses challenge
response (tb_domain_challenge_switch_key) enables trust level 2, but
otherwise only enables trust level 1.

> [*] I'm inclunding all attacks with "hostile device", including MIM on
> the PCIe link, compromised/fake device, attacks from a VMM through a

Yes, no mitigations against spoofing the device interface without TDISP.
However, I would also assume that level 2 is the ATS-on trust level
outside of TDISP cases.

> and 3 is a full accepted TDSIP device.
> 

Bare metal would still need to figure out how to send T=1 MMIO cycles
and check with some boot attestation that it can trust its MMIO mappings
are indeed targeting the device. So let's say trust level 2 is
everything but private MMIO and private DMA.

> From a uAPI perspective I'm not sold on having two bools, I think a
> level string would be more flexible. TSM and CC properties are

Perhaps the concern is less 2 bools in the uAPI and more the concern
that 'struct pci_dev::untrusted', 'struct tb_switch::authorized',
'struct usb_dev::authorized' and this new 'struct
device_private::cc_accepted' are getting convoluted.

> Internally we'd probably turn that dev->trusted thing into an
> enum and teach the iommu layer to treat it more dynamically.

I will take a stab at some patches in this direction and at least
demonstrate how 'struct pci_dev::untrusted' can be merged with what CC
wants to add on top.

---

## [49] Jason Gunthorpe — 2026-03-13
*Subject: Re: [PATCH v2 03/19] device core: Introduce confidential device
 acceptance*

On Fri, Mar 13, 2026 at 12:56:07PM -0700, Dan Williams wrote:
> > 0 Blocked and disabled
> >   The device cannot attack the system, enforced by the OS not loading a

I am thinking of it as an independent property. When the device is
first discovered it gets a level by default, userspace can change the
level but only when not bound. The level restricts what the kernel
will do with the device, 0 would mean "do not allow a driver to bind"

> > 1 In use, attacks from a hostile device are possible
> >   A driver can operate the device and is expected to defend against

SWIOTLB that is needed to make the DMA API work because the device
cannot reach CC private memory is orthogonal - the TDISP state (or
lack of) should directly drive that in the DMA API.

The DMA API just wants a flag in the struct device that says if the
device can access encrypted memory or only decrypted.

> I am assuming that each bus implementation may have a different way to
> get the device to the various trust levels.

I was actually thinking no, it is just a generic orthogonal driver
core property.

> For example, the uAPI for PCI TDISP requires associating a device with a
> TSM and asking the TSM to push the device to trust level 3. 

The other way, you can't get to level 3 unless the TSM subsystem ACK's
it. So TSM independently does its bit then userspace can set the level
to 3.

If it sets RUN and 2 that should work and have some kind of meaning,
just not be super useful.

> Another bus like thunderbolt may want to imply that "authorized"
> that uses challenge response (tb_domain_challenge_switch_key)

For thunderbolt/hot plug I imagine the kernel would default all
devices to level 0. Userspace would do its thing, using whatever other
uAPIs, and then set the level to 1 or 2. Then the driver starts.

This way nothing is coupled and the kernel can offer all kinds of
different uAPI for device verification. Userspaces picks the
appropriate one and acks it with the level change.

> Yes, no mitigations against spoofing the device interface without TDISP.
> However, I would also assume that level 2 is the ATS-on trust level

Yes, level 2 would be the break where the device is required to not do
wild PCIe packets to maintain kernel integrity.

> > #2 can happen in bare metal where a OS may activate link encryption
> > and attest the device, but doesn't have CC private/shared memory.

bare metal has no T=1 and no "private" at all. It just sets up link
encryption, excludes a MIM, attests the peer, then opens the iommu.

Jason

---

## [50] Dan Williams — 2026-03-13
*Subject: Re: [PATCH v2 03/19] device core: Introduce confidential device
 acceptance*

Jason Gunthorpe wrote:
> On Fri, Mar 13, 2026 at 12:56:07PM -0700, Dan Williams wrote:
> > > 0 Blocked and disabled

The problem is that for all the buses that do not currently have a
"device authorization" concept only userspace can decide that a device
should skip bind by default. For that, I propose module autoprobe policy
[1]. Not yet convinced the kernel needs its own per-device "no bind"
policy.

However, I do think userspace would like to know if the IOMMU subsystem
has blocked device DMA while unbound.

[1]: http://lore.kernel.org/20260303000207.1836586-6-dan.j.williams@intel.com

> > > 1 In use, attacks from a hostile device are possible
> > >   A driver can operate the device and is expected to defend against

You mean separate "trusted to access private" and "currently enabled to
access private" properties? I am trying to think of a situation where
"dev->trust >= 3" and a flag saying "disable bouncing for encrypted
memory" would ever disagree.

> > I am assuming that each bus implementation may have a different way to
> > get the device to the various trust levels.

Property? Agreed. uAPI? Not so sure...

> > For example, the uAPI for PCI TDISP requires associating a device with a
> > TSM and asking the TSM to push the device to trust level 3. 

That bit though has lock-to-run consistency expectations. So if the
kernel does not yet fully trust the device by time the relying party is
satisfied, and the uAPI to transition the device into the TCB (level 3)
is driver-core generic it raises TOCTOU issues in my mind. The
driver-core would need to ask the bus "user now trusts this device, do
you?".

Aneesh and I are currently debating on Discord whether the kernel needs
to protect against guest userspace confusing itself. Part of me says no,
especially with sysfs, if multiple threads are racing "unlock,
update/re-measure, lock, accept", then userspace gets to keep the
pieces.

However, to Aneesh's point we could protect against that with a
transactional uAPI like netlink that can express "trust if and only if
the device has not been relocked before final accept" by passing a
cookie obtained at lock to accept. That would be awkward to coordinate
with driver-core generic uAPI for trust.

> If it sets RUN and 2 that should work and have some kind of meaning,
> just not be super useful.

Thunderbolt already has authorized uAPI. I expect adding dev->trust
support to thunderbolt is more related to ATS privilege and private
memory privilege.

> > Yes, no mitigations against spoofing the device interface without TDISP.
> > However, I would also assume that level 2 is the ATS-on trust level

Ok, we are on the same page as to what a theoretical level 2 would mean.

---

## [51] Jakub Kicinski — 2026-03-14
*Subject: Re: [PATCH v2 08/19] PCI/TSM: Add "evidence" support*

On Mon,  2 Mar 2026 16:01:56 -0800 Dan Williams wrote:
> The implementation adheres to the guideline from:
> Documentation/userspace-api/netlink/genetlink-legacy.rst

My understanding of F_MULTI is that deserializer is supposed to
continue deserializing into current object. IOW if we have:

struct does_this {
	int really;
	int have_to;
	int be_netlink;
};

You can send "really" and "be_netlink" in one message and "have_to" 
in the next, and receiver should reconstruct them into a single struct.

If F_MULTI is not set - receiver assumes that the next message is a new
struct. And the whole dump returns a list of structs.

So IOW I think what you're doing is a bit too.. inventive.
Do you have plans to add more commands? 
The read-only stuff feels like it could be a sysfs API?
The main strength of Netlink is "do" commands with multiple optional
attrs.

---

## [52] Lukas Wunner — 2026-03-14
*Subject: Re: [PATCH v2 08/19] PCI/TSM: Add "evidence" support*

On Mon, Mar 02, 2026 at 04:01:56PM -0800, Dan Williams wrote:
> +definitions:
> +  -
[...]
> +      -
> +        name: val

The length of a netlink attribute is a 16-bit value, so a 16 MByte value
(0x01000000) won't fit.

Moreover you're referencing max-obj-size but are defining max-object-size.

This doesn't look like it's ever been tested, so at the very least
it should be marked RFC in the subject to convey that it's not yet
in a cut-and-dried state.

The two top-most commits on my development branch have solved the
size problem and may serve as a template:

https://github.com/l1k/linux/commits/doe

Thanks,

Lukas

---

## [53] Alexey Kardashevskiy — 2026-03-16
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

On 13/03/2026 21:23, Xu Yilun wrote:
>>> +		if (last_bar < bar) {
>>> +			/* transition to a new bar */

It is not the first 4K though if the actual first 4K (or whatever) of that BAR is MSIX which the device is mandated to skip in the report if MSIX is not "locked".

> How do you interpret the exact meaning of this field?
> 

and btw this only works if the entity generating the MMIO reporting offset (==TSM) knows about BARs sizes, which is not the case for AMD - the FW has no access to the config space (so the HV needs to feed this to the FW? may be). Thanks,

---

## [54] Dan Williams — 2026-03-16
*Subject: Re: [PATCH v2 08/19] PCI/TSM: Add "evidence" support*

Lukas Wunner wrote:
> On Mon, Mar 02, 2026 at 04:01:56PM -0800, Dan Williams wrote:
> > +definitions:

Good catch, not sure why the tooling did not complain.

> This doesn't look like it's ever been tested, so at the very least
> it should be marked RFC in the subject to convey that it's not yet

The 16MB limit has indeed not been tested, the test script in this set
was using smaller than 64K payloads to check out the interface.

The RFC comment for this piece is fair. The whole became a v2 based on
the maturity of other proposals that were in v1. This "evidence"
proposal deserves its own conversation.

> The two top-most commits on my development branch have solved the
> size problem and may serve as a template:

I was concerned that gets the same "too inventive" feedback from netdev
folks, but I ended up triggering the same with a broken alternate
proposal.

---

## [55] Dan Williams — 2026-03-16
*Subject: Re: [PATCH v2 08/19] PCI/TSM: Add "evidence" support*

Dan Williams wrote:
> Lukas Wunner wrote:
> > On Mon, Mar 02, 2026 at 04:01:56PM -0800, Dan Williams wrote:

This ends up not being a problem because 'val' is not referenced by a
request, only a reply. The automatic code generation does not generate
an nla_policy for replies. It should just be deleted because, see
below...

> > This doesn't look like it's ever been tested, so at the very least
> > it should be marked RFC in the subject to convey that it's not yet

So 16MB works ok, slow, but works. A given attribute in this
implementation never exceeds the limit because the protocol is for
assembly of a bulk attribute over multiple messages.

> The RFC comment for this piece is fair. The whole became a v2 based on
> the maturity of other proposals that were in v1. This "evidence"

I think your patches address the performance problem if userspace passes
large recieve buffers, but I do not think we need to make that a
userspace requirement.

---

## [56] Dan Williams — 2026-03-16
*Subject: Re: [PATCH v2 08/19] PCI/TSM: Add "evidence" support*

Jakub Kicinski wrote:
> On Mon,  2 Mar 2026 16:01:56 -0800 Dan Williams wrote:
> > The implementation adheres to the guideline from:

Heh, sensing a subtle message here...

> You can send "really" and "be_netlink" in one message and "have_to" 
> in the next, and receiver should reconstruct them into a single struct.

Fair, but see below, satisfying the requirements here are stuck in the
liminal space between sysfs and netlink... 

> Do you have plans to add more commands? 

Yes, future work like teaching the kernel how to cache device evidence
and re-challenge a device after error or power-loss recovery [1]. It may
even supplant some sysfs interfaces that would be better with
transactional semantics.

For example, a LOCK operation that returns a session cookie and a
RUN/ACCEPT operation that only succeeds if the session has not been
invalidated in the interim. sysfs would require userspace locking for
such a semantic.

[1]: http://lore.kernel.org/69a9de4791667_6423c1006c@dwillia2-mobl4.notmuch

> The read-only stuff feels like it could be a sysfs API?

In fact, the original genesis of a proposal in this space was sysfs back
at Plumbers 2024 [2].

As the number of attributes, modifiers, and transactions grew the
feedback in the BoF was to move to a more suitable uAPI, netlink.

Yes, a subset of the objects here could move to sysfs [3], but that does
relieve the main need here which is an interface that can dump a fresh
copy of the device measurements (settings and device data up to 16MB in
size), signed by the device, with a nonce provided by relying party
(userspace).

[2]: https://lpc.events/event/18/contributions/1955/
[3]: http://lore.kernel.org/20260219124119.GD723117@nvidia.com

> The main strength of Netlink is "do" commands with multiple optional
> attrs.

Yes, that is attractive and saves a pile of bug prone ioctl handling.

The gap I need to fill first though is a uAPI that allows for large
blobs to be fetched after being regenerated / reformatted besed on some
input attributes.

"Multi message netlink attributes" while inventive, feels less awkward
and more future proof than a sysfs binary attribute scheme to do the
same.

---

## [57] Xu Yilun — 2026-03-17
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

On Fri, Mar 13, 2026 at 10:36:58AM -0300, Jason Gunthorpe wrote:
> On Fri, Mar 13, 2026 at 06:23:51PM +0800, Xu Yilun wrote:
> 

Yeah, now I think I've fully understood the problem. The essential thing
is some of the MMIO ranges could be hidden from the report, at least the
MSIX/PBA ranges must be hidden if not locked/private. This makes guest
hard to find the bar layout out of the report.

> the CPU CC specs need to constrain it to be usable by an OS.
> 

This is the solution on CPU CC side, which requires the TSM to choose a
mmio_reporting_offset aligned to the MAX BAR size so that the
obfuscation won't blur the bar offset info. This is a trade off, the
larger the bar_size, the weaker the obfuscation. Is there a worst case,
that a device has a large bar in high address and a small bar in low
address, the small bar address has no intersection with the
mmio_reporting_offset. Then the obfuscated address ends up being amusing
0xabcd012345000, which clearly leaks the mmio_reporting_offset and the
physical BAR address...


And I've no idea why unlocked MSIX/PBA must be hidden? How about other
non-TEE ranges, must be hidden or mustn't? Is there a possibility we
enforce DSM to present all ranges, then the layout is clear to OS?

> 
> Right.

---

## [58] Lukas Wunner — 2026-03-17
*Subject: Re: [PATCH v2 08/19] PCI/TSM: Add "evidence" support*

On Mon, Mar 16, 2026 at 04:02:22PM -0700, Dan Williams wrote:
> Dan Williams wrote:
> > Lukas Wunner wrote:

Famous last words.

If you look at netlink_dump(), it sizes the skb based on
nlk->max_recvmsg_len.  If that's larger than 64k, you'll
try to fill as much as possible of that space with a single
netlink attribute.  The computation of "available" in your
patch doesn't take the 65531 bytes limit for a netlink attribute
into account so it looks like you'll end up overflowing the length
of the netlink attribute.

Unfortunately nla_put() doesn't prevent such overflows, it does
all the size calculations with an int, not a u16.

Thanks,

Lukas

---

## [59] Lukas Wunner — 2026-03-17
*Subject: Re: [PATCH v2 08/19] PCI/TSM: Add "evidence" support*

On Sat, Mar 14, 2026 at 11:12:45AM -0700, Jakub Kicinski wrote:
> On Mon,  2 Mar 2026 16:01:56 -0800 Dan Williams wrote:
> > The implementation adheres to the guideline from:

So is the "should" above meant to be understood in the RFC 2119 way,
i.e. as a mere recommendation?

The problem we're facing is that nlattr::nla_len is u16, so the maximum
size is 65531 bytes (65535 minus header).  That's insufficient for
transmitting blobs that are several megabytes in size.

The obvious solution is to split the blobs into smaller chunks and
transmit each chunk in an attribute of the same type.  The application
then concatenates them together to reconstruct the blob.  For particularly
large blobs, it may even be necessary to split across multiple messages
by way of NLM_F_MULTI.

Apart from the attribute size limitation, there's the problem that copying
large blobs in memory is inefficient.  Ideally we'd want zero-copy.
The solution I came up with is to attach the blob's pages as fragments
to the skb.  Conceptually the fragments succeed the linear buffer of the
skb, so by putting the nlattr header into the linear buffer and attaching
the blob as fragments, the receiver consumes the netlink message in a
natural way.  This patch introduces an nla_put_blob() helper which was
pretty straightforward:

https://github.com/l1k/linux/commit/af9b939fc30b

This patch is taking advantage of the helper:

https://github.com/l1k/linux/commit/009663bd172e

The only change I had to make is amending nlmsg_end() to take the
fragments into account when calculating the nlmsg_len.

The patch does achieve zero-copy on the sender's end.  It may also
achieve zero-copy on the receiver's end if the receiver is in the
kernel.  However it does *not* achieve zero-copy if the receiver is
in user space.  That's because:

simple_copy_to_iter()
  copy_to_iter()
    _copy_to_iter()
      copy_to_user_iter()
        raw_copy_to_user()

... will just stupidly copy the data into the user space buffer.
It might be possible to achieve zero-copy in user space via io_uring.

At this point perhaps your conclusion is that netlink isn't the right
protocol for this job.  It's great for transmitting sets of small items,
some of which may be optional, but it's obviously not well-suited for
large items.

Jason Gunthorpe was quite insistent that we use netlink and you know
how consensus-oriented kernel development is.  Indeed sysfs has turned
out not to be ideal because the protocol that we're dealing with
(SPDM - DMTF DSP0274) allows many degrees of freedom and making
them available through sysfs quickly becomes unwieldy.

E.g. when installing a certificate onto a device, the protocol allows
specifying additional parameters (a keypair ID and a certificate model)
together with the certificate chain that shall be installed.  That doesn't
square well with the "one value per file" sysfs model.  User space would
have to write the keypair ID and certificate model to separate attributes,
then write the certificate chain to a third attribute.  So the kernel would
need some kind of state machine to keep track of which sysfs attributes
have been written.  It gets quite ugly.

As another example, the SPDM protocol allows retrieving measurements
from the device.  The measurements are indexed by an 8-bit number.
To expose them via sysfs, the kernel would have to retrieve all of them
on device enumeration so that it knows which indices are populated
and need to be exposed in sysfs.  That would incur a delay on device
enumeration and thus lead to slower boot times.

If netlink is at all the right protocol for the job, I'm wondering if an
extension for larger attributes would be entertained.  Basically a
variation of struct nlattr, but with a 24-bit or 32-bit size and
maybe a list of fragment numbers.  The latter would be useful to have
*multiple* zero-copy attributes because the patches linked above only
allow for a single zero-copy attribute per nlmsg.

Thanks,

Lukas

---

## [60] Lukas Wunner — 2026-03-17
*Subject: Re: [PATCH v2 08/19] PCI/TSM: Add "evidence" support*

On Mon, Mar 02, 2026 at 04:01:56PM -0800, Dan Williams wrote:
> +    type: const
> +    name: max-nonce-size
[...]
> +#define PCI_TSM_MAX_OBJECT_SIZE	16777216
> +#define PCI_TSM_MAX_NONCE_SIZE	256

Where is the maximum nonce size of 256 bytes coming from?

Such definitions should always be accompanied by a spec reference,
not pulled out of thin air.

SPDM nonces are 32 bytes, I assume that's what we're dealing with here?

This patch:
https://github.com/l1k/linux/commit/bca645e08ee9

... contains the following definition:
#define SPDM_NONCE_SZ 32 /* SPDM 1.0.0 table 20 */

Though it's defined in a private header in lib/spdm/spdm.h.  If there's
a need outside of the SPDM library, its visibility can be broadened
of course.

Thanks,

Lukas

---

## [61] Dan Williams — 2026-03-18
*Subject: Re: [PATCH v2 08/19] PCI/TSM: Add "evidence" support*

Lukas Wunner wrote:
> On Mon, Mar 16, 2026 at 04:02:22PM -0700, Dan Williams wrote:
> > Dan Williams wrote:

I am not convinced you have found the "gotcha" you think you have...

> If you look at netlink_dump(), it sizes the skb based on
> nlk->max_recvmsg_len.  If that's larger than 64k, you'll

The @len to nla_put() should not overflow because it is based on the
available tailroom in the skb minus netlink overhead. The "inventive"
hack that Jakub is reacting to is that this scheme requires a receiver
that assumes repeating the attribute in the receive stream must be
handled as concatenation.

> Unfortunately nla_put() doesn't prevent such overflows, it does
> all the size calculations with an int, not a u16.

Are we looking at the same capacity calculation?

    len = min(available - overhead, object_len - ctx->offset);

---

## [62] Dan Williams — 2026-03-18
*Subject: Re: [PATCH v2 08/19] PCI/TSM: Add "evidence" support*

Lukas Wunner wrote:
> On Mon, Mar 02, 2026 at 04:01:56PM -0800, Dan Williams wrote:
> > +    type: const

I took it from Aneesh's off-list RFC, and meant to circle back with him.
Yes, it should come with a spec reference.

I am having trouble finding a clear reference for ARM CCA that clarifies
that measurement recollection takes the SPDM standard nonce as an input.
Perhaps the document I have "DEN0137 1.1-alp8" is out of date? TDX and
SEV-TIO do reference SPDM for the nonce size.

> Such definitions should always be accompanied by a spec reference,
> not pulled out of thin air.

Yes.

> SPDM nonces are 32 bytes, I assume that's what we're dealing with here?
> 

Of course. Again this points to a need to pull this proposal out
separate from the rest.

The ARM CCA spec does reference the EAT nonce which is 64-bytes. So it
may be the case that PCI_TSM_MAX_NONCE_SIZE != SPDM_NONCE_SZ depending
on what evidence can be collected over this interface, but I am not
finding any spec references for 256, Aneesh?

---

## [63] Dan Williams — 2026-03-18
*Subject: Re: [PATCH v2 08/19] PCI/TSM: Add "evidence" support*

Lukas Wunner wrote:
[..] 
> At this point perhaps your conclusion is that netlink isn't the right
> protocol for this job. It's great for transmitting sets of small items,

Right, and sysfs is not well suited for transaction in/out semantics.

> Jason Gunthorpe was quite insistent that we use netlink and you know

Jason can of course correct me, but the insistence was less that netlink
was the right tool for the job, and more that sysfs was the wrong tool
for the job.

Netlink appears to be the least worst option.

> how consensus-oriented kernel development is.  Indeed sysfs has turned
> out not to be ideal because the protocol that we're dealing with
[..]
> If netlink is at all the right protocol for the job, I'm wondering if an
> extension for larger attributes would be entertained.

It is still not clear to me that allowing larger attributes are part of
the solution space. They seem to be a premature performance optimization
once userspace is prepared to reassemble a large blob over multiple
messages.

---

## [64] Jakub Kicinski — 2026-03-18
*Subject: Re: [PATCH v2 08/19] PCI/TSM: Add "evidence" support*

On Mon, 16 Mar 2026 18:45:24 -0700 Dan Williams wrote:
> Jakub Kicinski wrote:
> > On Mon,  2 Mar 2026 16:01:56 -0800 Dan Williams wrote:  

One learns to optimize for conserving one's own attention wherever
possible :>

> > The main strength of Netlink is "do" commands with multiple optional
> > attrs.  

Alright, so to make this more Netlink-y you can either:
 - delete the F_MULTI and replicate other attrs in each message and 
   add an offset attr; this will make each message in the dump more
   standalone. 
 - keep the F_MULTI but object_val has to be a multi-attr, and then 
   we have to teach YNL to correctly append the attrs.

Former is definitely less work. Latter could end up being cleaner
but there are some unknowns so hard to tell for sure; more plumbing.

---

## [65] Borislav Petkov — 2026-03-19
*Subject: Re: [PATCH v2 12/19] x86, ioremap, resource: Support
 IORES_DESC_ENCRYPTED for encrypted PCI MMIO*

On Mon, Mar 02, 2026 at 04:02:00PM -0800, Dan Williams wrote:
> PCIe Trusted Execution Environment Device Interface Security Protocol
> (TDISP) arranges for a PCI device to support encrypted MMIO. In support of

"Add IORES_MUST_ENCRYPT to manage... "

Pls read section "2) Describe your changes" in
Documentation/process/submitting-patches.rst for more details. Especially the
part about ordering the code to do stuff.

> Given that "PCI MMIO Encrypted" is an additional resource in the tree, the
> IORESOURCE_BUSY flag will only be set on a descendant/child of that

"In an encrypted... "

> + * because there the whole memory is already encrypted.
> + *

This looks too convoluted. I'm sure we can state the rules for encrypted
ranges first and then can simplify it into something more understandable.

>  
>  /*

This change I don't grok. Perhaps it needs to be a separate patch.

>  /*
> @@ -162,6 +171,13 @@ static void __ioremap_check_mem(resource_size_t addr, unsigned long size,

<---- newline here.

> +	/*
> +	 * Encrypted MMIO may parent a driver's requested region, so it needs a

Why is this here and executed unconditionally regardless of coco guest or not?

---

## [66] Dan Williams — 2026-03-19
*Subject: Re: [PATCH v2 08/19] PCI/TSM: Add "evidence" support*

Jakub Kicinski wrote:
[..] 
> > > The main strength of Netlink is "do" commands with multiple optional
> > > attrs.  

Makes sense, and not yet sure which one is lower maintenance burden
long term. I will play with it a bit.

I am leaning to the first option more for the fact that it puts the
burden of being strange squarely on the implementation that wants it. If
this discussion attracts more large blob dumpers then the second option.

Thanks for spending some attention here.

---

## [67] Jason Gunthorpe — 2026-03-23
*Subject: Re: [PATCH v2 03/19] device core: Introduce confidential device
 acceptance*

On Fri, Mar 13, 2026 at 06:32:27PM -0700, Dan Williams wrote:

> The problem is that for all the buses that do not currently have a
> "device authorization" concept only userspace can decide that a device

I think it is just part of the broader definition of the level that
extends into the iommu and so on. It makes sense to have this kind of
no-binding security level, IMHO.

> > The DMA API just wants a flag in the struct device that says if the
> > device can access encrypted memory or only decrypted.

I'm steering the trust level toward more of an acceptance criteria.
If the trust level is you have access to private memory but the device
can't actually do that then fail the trust level change.

Same for the reverse, if the trust level says no private memory and the
device is T=1 then fail the trust level change.

> That bit though has lock-to-run consistency expectations. So if the
> kernel does not yet fully trust the device by time the relying party is

Huh? No, there is no concept of trust in the kernel. The userspace
setting level 3 is "I now ack that this device is trusted", there is
no further trust cross check. If TSM side says it is in RUN/T=1 then
we are done.

If we fall out of RUN then the level auto-resets back to 0 and
userspace has to go around and fix it again. (ignoring driver RAS)

> Aneesh and I are currently debating on Discord whether the kernel needs
> to protect against guest userspace confusing itself. 

Userspace that controls acceptance must be part of the TCB or the
whole model is fully broken. If your guest userspace is so security
broken it can accept devices it doesn't mean to then just forget it.

> However, to Aneesh's point we could protect against that with a
> transactional uAPI like netlink that can express "trust if and only if

You could, but why make it so complicated? The whole LOCKED/RUN thing
is already supposed to deal with TOCTOU, doesn't it? The CSP cannot
trick a device to fall out of LOCKED an the re-enter LOCKED without
the VM knowing.

The VM attacking itself on something as security critical as device
accepance can't be in scope :\

> > This way nothing is coupled and the kernel can offer all kinds of
> > different uAPI for device verification. Userspaces picks the

It brings it into the whole 'measure the device and then decide what
to do with it' framework. The trust level is still the generic ack
that the device is allowed the participate in the system with whatever
level of security.

Jason

---

## [68] Jason Gunthorpe — 2026-03-23
*Subject: Re: [PATCH v2 08/19] PCI/TSM: Add "evidence" support*

On Wed, Mar 18, 2026 at 12:56:42AM -0700, Dan Williams wrote:
> Lukas Wunner wrote:
> [..] 

+1

netlink is a good starting point, but if it isn't fitting well then
the next stop would be an ioctl char dev..

Jason

---

## [69] Jason Gunthorpe — 2026-03-23
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

On Mon, Mar 16, 2026 at 04:19:30PM +1100, Alexey Kardashevskiy wrote:

> and btw this only works if the entity generating the MMIO reporting
> offset (==TSM) knows about BARs sizes, which is not the case for AMD

Then your platform just shouldn't use the mmio offset feature. Set it
to 0 always.

Jason

---

## [70] Dan Williams — 2026-03-23
*Subject: Re: [PATCH v2 03/19] device core: Introduce confidential device
 acceptance*

Jason Gunthorpe wrote:
> On Fri, Mar 13, 2026 at 06:32:27PM -0700, Dan Williams wrote:
> 

Easy to include for completeness.

In a CC VM userspace can set "$module autoprobe=0" to get a control
point to set @trust to zero, but @trust otherwise defaults to 1. This
allows for userspace policy to generically distrust devices, but without
needing to build a new mechanism to specify which devices start life at
trust == 0 (i.e.  "device filter" proposal previously NAK'd).

> > > The DMA API just wants a flag in the struct device that says if the
> > > device can access encrypted memory or only decrypted.

Ok, so the uapi for PCI/TDISP would be:

echo $tsm > $pdev/tsm/lock
<gather evidence, validate with relying party>
echo 3 > $pdev/trust

...where that @trust attribute is a generic device semantic, but in the
case of PCI device connected to a given TSM it invokes the TSM hypercall
to transition the device to the RUN state and the TSM local call to
unblock DMA to private memory.

So, userspace can generically understand what privileges come with which
trust levels, but the mechanism to get those privileges remains bus
specific.

> > That bit though has lock-to-run consistency expectations. So if the
> > kernel does not yet fully trust the device by time the relying party is

Ok, so maybe I misunderstood your point. Per the above, if the trust
setting is what kicks the bus to finalize T=1 then it makes sense. If
that kick fails, the user's trust setting request fails.

What I expect is unwanted / surprising is device has already been
transitioned to T=1 state ahead of the trust setting, it is a
synchronous mechanism.

> If we fall out of RUN then the level auto-resets back to 0 and
> userspace has to go around and fix it again. (ignoring driver RAS)

Yes, at the moment that the bus detects that an event like SPDM session
loss, IDE link loss, TDISP ERROR state entry has occurred it can
downgrade trust and notify. That notification fits well with netlink
because all of those events are downstream of evidence validation.

> > Aneesh and I are currently debating on Discord whether the kernel needs
> > to protect against guest userspace confusing itself. 

Agree, it is a non-problem. If guest userspace confuses itself by racing
sysfs operations then the relying party should not trust that userspace.

> > However, to Aneesh's point we could protect against that with a
> > transactional uAPI like netlink that can express "trust if and only if

Right, the threat vector is the guest accepting something it has had no
chance to validate. Guest userspace confusion is not that. Guest
userspace asking the device to be re-locked in a way that confuses an
ongoing evidence validation sequence in another thread is a "you get to
keep the pieces" event.

> The CSP cannot trick a device to fall out of LOCKED an the re-enter
> LOCKED without the VM knowing.

The complication vs benefit tradeoff is indeed not mathing, but wanted
to do justice to Aneesh's proposal and the suitability of the sysfs
uapi.

> > > This way nothing is coupled and the kernel can offer all kinds of
> > > different uAPI for device verification. Userspaces picks the

Some thought experiments to confirm alignment...

'Generic ack' is a synchronous mechanism for the bus to evaluate. So if
@trust appears for any device, and by consequence alongside @authorized
for a thunderbolt device, it should be the case that these operations
are equivalent:

# echo 1 > $dev/trust
# echo 1 > $dev/authorized

...and the result is cross-reflected for comptability:

# echo 1 > $dev/trust
# cat $dev/authorized
1

Consequently this:

# echo 2 > $dev/trust

...would be equivalent to authorizing the device and unblocking ATS (if
such a thing existed).

For bare metal PCI device security the TSM 'connection' needs to be
established in order to enable device evidence collection.

echo $tsm > $pdev/tsm/connect
<validate device evidence>
echo 2 > $pdev/trust

Now, I question whether 5 trust levels instead of 4. This would be to
explicitly only trust devices where the TSM has established physical
link encryption, or the TSM has asserted that the link is protected by
other means. So the trust levels are:

0 disconnected: bus does not attach drivers
1 limited: core code deploys hostile device mitigations like disable
           ATS, CC force shared memory bouncing.
2 DMA: full DMA access, driver responsible for protecting against
       adverarial devices.
3 Link: mitigations against physical integrity and snooping attacks
        deployed
4 TCB: full device interface validation via a protocol like TDISP,
       CC private memory access granted.

Where the native Rust library based SPDM driver only offers trust level
2, bare metal TSMs can support trust level 3, and the TSM interfaces in
CC VMs can support trust level 4. I could see squashing 2 and 3 and
making it a documentation problem to understand the capabilities of the
various TSM drivers.

---

## [71] Dan Williams — 2026-03-23
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

Xu Yilun wrote:
[..] 
> And I've no idea why unlocked MSIX/PBA must be hidden? How about other
> non-TEE ranges, must be hidden or mustn't? Is there a possibility we

Just to close this question, this was discussed at the last device
security call. Indeed the expectation is that Linux will assume that all
ranges besides MSIX/PBA must be present in the report, and that offset
is always aligned. If / when an implementation violates that expectation
they can help write the Linux quirk for that case or otherwise fix their
implementation.

---

## [72] Jason Gunthorpe — 2026-03-24
*Subject: Re: [PATCH v2 03/19] device core: Introduce confidential device
 acceptance*

On Mon, Mar 23, 2026 at 07:18:17PM -0700, Dan Williams wrote:
> Jason Gunthorpe wrote:
> > On Fri, Mar 13, 2026 at 06:32:27PM -0700, Dan Williams wrote:

I feel like starting with trust=0 is much cleaner than using
autoprobe. Especially since it would be nice that when you do
ultimately set trust!=0 then you do want the kernel to do the normal
autoprobe flow.

Double so because I would like the iommu drivers to respond to trust 0
by fully blocking the device 100% of the time without holes, so to
make that work I would like to see the struct device report trust 0
the moment the iommu framework attaches the iommu.

How you decide the starting trust value for device during system boot
is definately something we need to discuss properly..

I liked your idea of using built in driver match, so if there is a
simple command line paramater that says 'only built in is trusted'
then we'd default all devices to untrusted and during device probe
check if any built in driver is matching and auto-set trust to X based
on the commandline parameter.

With the idea that only devices required to get to the initrd are
built in. Then the initrd userspace has the policy to bring more
devices into trusted!=0 to get to the root file system, then the
rootfs has more policy for further devices, and so on.

Probably this would ultimately escalate into annotations in the
modinfo about default policies for various drivers.

A kernel default policy of trusting everything without a "trust ops"
(see below) may also be quite reasonable, however boot ordering the
trust ops might be really tricky...

> > > > The DMA API just wants a flag in the struct device that says if the
> > > > device can access encrypted memory or only decrypted.

Maybe, but I was thinking the transition through run/locked would be
done through TSM uAPIs too. trust setting in the kernel just confirms
the device is in the right state.

But I haven't thought of a reason why the final switch to RUN couldn't
happen like this either.

> So, userspace can generically understand what privileges come with which
> trust levels, but the mechanism to get those privileges remains bus

Yes

> > If we fall out of RUN then the level auto-resets back to 0 and
> > userspace has to go around and fix it again. (ignoring driver RAS)

Which is also why it would be nice to be consistent and rely on
trust=0 to isolate the device in all cases, not a mixture of
autoprobe.

> The complication vs benefit tradeoff is indeed not mathing, but wanted
> to do justice to Aneesh's proposal and the suitability of the sysfs

I think if you want something like this then it is better to target
the root - remove the ability for concurrent userspace to wrongly
operate the TSM entirely. Ie use a cdev, make it so going to LOCKED
isolates access to only this cdev fd and require only this cdev fd to
go to RUN. Then these kinds of bugs don't exist.

> > It brings it into the whole 'measure the device and then decide what
> > to do with it' framework. The trust level is still the generic ack

Yes, I don't know anything about thunderbolt, but this seems
reasonable. You could also do as you suggested for TDISP that trust!=0
auto-authorizes.

Basically the 'trust' generic framework sits on top of some "trust
ops" that will be provided by the security module that is affiliated
with the struct device (ie thunderbolt, TSM TDISP, TSM Link IDE, etc,
etc)

Then it becomes a general synchronization point where on one side the
"tust ops" can ack that the level is acceptable and consistent with
the system when on the other side generic compoments like IOMMU,
driver binding, etc can respond to it and change their behavior.

> For bare metal PCI device security the TSM 'connection' needs to be
> established in order to enable device evidence collection.

I probably wouldn't use an int for the uAPI, but yes picking the
initial levels is important. As above since this is a clearing point
between two different worlds it needs to be defined in some way both
sides can understand what it means for them.

> 0 disconnected: bus does not attach drivers
> 1 limited: core code deploys hostile device mitigations like disable

This seems reasonable to me, the 3/4 distinction is not meaningful for
the iommu&dev side, but it does provide a good check point for the
"trust ops". If userspace ack's that it expects physical security and
the kernel says it isn't physically secure (or becomes insecure later)
then it should fail.

> Where the native Rust library based SPDM driver only offers trust level
> 2, bare metal TSMs can support trust level 3, and the TSM interfaces in

I'm not sure that the SPDM driver even provides a "trust ops" right? I
would guess that 0/1/2 are simply built in always available if trust ops are
NULL and 3/4 require positive reply from the ops to accept it.

So #3 needs a "trust ops" linked to enabling link IDE.. If this is
done in-kernel the link IDE module is providing the trust ops and just
using SPDM as a library to establish the link IDE keys?

Jason

---

## [73] Jason Gunthorpe — 2026-03-24
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

On Mon, Mar 23, 2026 at 08:26:26PM -0700, Dan Williams wrote:
> Xu Yilun wrote:
> [..] 

I don't think you can quirk it.

Implementations can always follow this requirement by setting the
offset to 0. If they cannot compute a proper aligned offset then this
is what they must do.

Jason

---

## [74] Dan Williams — 2026-03-24
*Subject: Re: [PATCH v2 03/19] device core: Introduce confidential device
 acceptance*

Jason Gunthorpe wrote:
[..] 
> I feel like starting with trust=0 is much cleaner than using
> autoprobe. Especially since it would be nice that when you do

I do agree that forcing trust=0 at the beginning of time is attractive
and theoretically clean. I am concerned about subsystems that are not
prepared for driver attach failures. For example, I would not expect to
need to set trust for auxiliary bus devices if the host device is
trusted.

However, the work to set module autoprobe policy is on the same order as
adding a module scoped trust policy.

So something like "modprobe $module trust=X" automatically tries to set
the device trust level on attach to any drivers in that module. That
could allow a semantic of "attach iff device is able to go to level 4".

> With the idea that only devices required to get to the initrd are
> built in. Then the initrd userspace has the policy to bring more

Yes, escalate over time for subsystems to say "devices I create are
trusted, the responsibility to manage trust lies with clients of my
APIs".

> A kernel default policy of trusting everything without a "trust ops"
> (see below) may also be quite reasonable, however boot ordering the

Given the optionality in selecting a trust ops provider I think it gets
extra messy quickly. Let me see how far I can get with built-in auto
trust + module trust policy.

> > > > > The DMA API just wants a flag in the struct device that says if the
> > > > > device can access encrypted memory or only decrypted.

Right, the potential to see in-between states concerns me because TSM
uAPIs would have fully enabled the device to wreak havoc, meanwhile
dev->trust is still showing the device at some lower level of trust. So
I think trust modification needs to be synchronous with privileges
granted/revoked.

[..]
> > The complication vs benefit tradeoff is indeed not mathing, but wanted
> > to do justice to Aneesh's proposal and the suitability of the sysfs

The netlink evidence proposal can handle this, it just needs a
'validate' command. 'Validate' records a device evidence generation
number. Require a stable generation number between entering LOCK and the
trust=4 event transitioning the device to RUN.

Yes, not as safe as fd-private LOCK-to-RUN, but I like semantic of
"modprobe $module trust=4" to say "transition to RUN and attach to all
validated devices".

[..]
> Basically the 'trust' generic framework sits on top of some "trust
> ops" that will be provided by the security module that is affiliated

Something like this, yes.

> > For bare metal PCI device security the TSM 'connection' needs to be
> > established in order to enable device evidence collection.

Yes, but an int for now saves the bikeshed of the level names till a bit
later.

> ...but yes picking the initial levels is important. As above since
> this is a clearing point between two different worlds it needs to be

Right. Even though the SPDM driver allows device evidence to be
collected there is no event like LOCK-to-RUN that expects validated
evidence as a precondition.

> So #3 needs a "trust ops" linked to enabling link IDE.. If this is
> done in-kernel the link IDE module is providing the trust ops and just

Yes, but note to date only Intel platforms allow for IDE establishment
without talking to the platform TSM.

---

## [75] Jason Gunthorpe — 2026-03-25
*Subject: Re: [PATCH v2 03/19] device core: Introduce confidential device
 acceptance*

On Tue, Mar 24, 2026 at 09:13:06PM -0700, Dan Williams wrote:
> Jason Gunthorpe wrote:
> [..] 

Yeah, IDK here either. Maybe it is some per-bus opt int.

I think the most important thing is we get a clean story for devices
to be isolated by the iommu until user space ack's them.

> Right, the potential to see in-between states concerns me because TSM
> uAPIs would have fully enabled the device to wreak havoc, meanwhile

If an iommu is present then the device will still be blocked even
though it is in RUN, I'm not sure this synchronicity is so important.

Jason

---

## [76] Dan Williams — 2026-03-25
*Subject: Re: [PATCH v2 03/19] device core: Introduce confidential device
 acceptance*

Jason Gunthorpe wrote:
[..]
> > Right, the potential to see in-between states concerns me because TSM
> > uAPIs would have fully enabled the device to wreak havoc, meanwhile

Oh, maybe we are just quibbling about where the mechanism lives. The
"unblock DMA" step in current preliminary patches is currently behind
the "struct pci_tsm_ops::accept()" op which also handles transitioning
the device to RUN / T=1. It is a bus callback.

However, if the IOMMU layer is enlightened to block/unblock DMA on trust
setting then the TDISP "unblock DMA" step can be factored out of this bus
callback and into the IOMMU trust responder.

So device could enter T=1 way in advance of the "unblock DMA" event.

I assume this would also expect that encrypted MMIO mappings are also
not established while trust is less than "TCB"? That would require some
additional enabling to catch attempts to establish an encrypted mapping
that the hardware is prepared for, but dev->trust is not, all without
needing to modify the driver to worry about this difference. Drivers
would just see ioremap() failure in this case.

A bit more work, but yes, that is a cleaner separation of concerns.

---

## [77] Jason Gunthorpe — 2026-03-26
*Subject: Re: [PATCH v2 03/19] device core: Introduce confidential device
 acceptance*

On Wed, Mar 25, 2026 at 06:27:04PM -0700, Dan Williams wrote:
> Jason Gunthorpe wrote:
> [..]

Yes, I would prefer this because it makes the whole IOMMU mechanism
entirely general and not tied to TDISP - which I think is sort of what
Greg is pushing on too.

> I assume this would also expect that encrypted MMIO mappings are also
> not established while trust is less than "TCB"? That would require some

Hmm.. I don't know if this matters. Once we decide to use the device
the MMIO should be mapped in the correct way, whatever that is.

If we decide to eventually allow a lower trust while T=1 then that
should be taken to mean the user wants all the features protecting the
communication channel but also all the IOMMU features restricting what
memory the device can access.

Remember there are two parallel things here, one is T=1 which is
designed to protect against hypervisor and physical attacks, the other
is the trust level and iommu which would be able to protect against
attacks from an attested device itself.

Even if you are in a T=1 environment you may still decide you don't
really trust the device firmware that much and would prefer to have it
more restricted.

For example, if you have a system with a NVMe drive then all the data
on the drive is probably still encrypted and has be CPU-decrypted
before it can be used. It would be reasonable to run in T=1 and attest
the drive to limit attack surface but also use the IOMMU to limit NVMe
access to only the memory used to bounce to the CPU decryption as an
additional fortification.

This is why I am tending to prefer that the kernel's view of trust
level and the physical HW capability are somewhat orthogonal
things. Even if the HW has high security the user may still prefer
that the kernel distrust.

Jason

---

## [78] Greg KH — 2026-03-26
*Subject: Re: [PATCH v2 03/19] device core: Introduce confidential device
 acceptance*

On Thu, Mar 26, 2026 at 09:00:46AM -0300, Jason Gunthorpe wrote:
> On Wed, Mar 25, 2026 at 06:27:04PM -0700, Dan Williams wrote:
> > Jason Gunthorpe wrote:

That is what I am going to _require_ here :)

> > I assume this would also expect that encrypted MMIO mappings are also
> > not established while trust is less than "TCB"? That would require some

I agree, that's a good way of putting this.

greg k-h

---

## [79] Dan Williams — 2026-03-26
*Subject: Re: [PATCH v2 03/19] device core: Introduce confidential device
 acceptance*

Jason Gunthorpe wrote:
[..]
> > I assume this would also expect that encrypted MMIO mappings are also
> > not established while trust is less than "TCB"? That would require some

The question is whether any part of the kernel would ever track that
secrets in MMIO writes should not be written to TCB-external devices...
but that is probably a "trust=0" situation. "trust=1" means "be careful
what you send to this device whether the transport is protected or not".

> Remember there are two parallel things here, one is T=1 which is
> designed to protect against hypervisor and physical attacks, the other

Sounds workable to me.

---

## [80] Jason Gunthorpe — 2026-03-26
*Subject: Re: [PATCH v2 03/19] device core: Introduce confidential device
 acceptance*

On Thu, Mar 26, 2026 at 11:31:16AM -0700, Dan Williams wrote:
> Jason Gunthorpe wrote:
> [..]

Right, the kernel has no idea what is secret or not, it is up to
userspace not to give the device secrets if it doesn't fully trust it.

Jason

---

## [81] Alexey Kardashevskiy — 2026-03-27
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

On 24/3/26 05:20, Jason Gunthorpe wrote:
> On Mon, Mar 16, 2026 at 04:19:30PM +1100, Alexey Kardashevskiy wrote:
> 

pcie r7, Table 11-16 TDI Report Structure, MMIO_RANGE:

"Each MMIO Range of the TDI is reported with the MMIO reporting offset added."

My english struggles here - can the above be interpreted as "Each reported MMIO Range ..."?

as if it is each (except msix), then I know where msix is and can amend the report inside the VM if msix is not locked. Thanks,

---

## [82] Lai, Yi — 2026-03-27
*Subject: Re: [PATCH v2 16/19] samples/devsec: Introduce a "Device Security
 TSM" sample driver*

On Mon, Mar 02, 2026 at 04:02:04PM -0800, Dan Williams wrote:
> There are 2 sides to a TEE Security Manager (TSM), the 'link' TSM, and the
> 'devsec' TSM. The 'link' TSM, outside the TEE, establishes physical link

Hi Dan,

While validating devsec mode transitions, I hit a reproducible crash in the
sample devsec driver.

Reproducer:
1. lock with devsec tsm
2. unlock

Observed: NULL pointer dereference in the MMIO teardown path

Expected: unlock from LOCKED should return to UNLOCKED safely.

My understanding is that this is a sample driver implementation bug - missing
NULL guard before MMIO teardown.

A follow-up question: do you prefer current design and each device
security TSM driver is responsible for MMIO check, or should tsm/core
adds a NULL guard to avoid potential crash?

Regards,
Yi Lai

> +static int devsec_tsm_accept(struct pci_dev *pdev)
> +{

---

## [83] Jason Gunthorpe — 2026-03-27
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

On Fri, Mar 27, 2026 at 10:38:15AM +1100, Alexey Kardashevskiy wrote:
> 
> 

To do this you must be convert between the offset'd and phys_addr_t
versions otherwise you have no idea where the translated ones fall
within the BAR, so you can't figure out if msix is covered or not.

Jason

---

## [84] Alexey Kardashevskiy — 2026-03-30
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

On 27/3/26 22:49, Jason Gunthorpe wrote:
> On Fri, Mar 27, 2026 at 10:38:15AM +1100, Alexey Kardashevskiy wrote:
>>

I know if MSIX is covered because I know (from the PSP) if it is locked so it must be reported, with specific MSIX/PBA flags. If it is not locked, then skipped in the report but I still know where it is. For other ranges, if the device is not skipping them randomly, then, with a preserved order (as PCIe mandates), it can be reconstructed.

PCIe:
===
MMIO ranges assigned via BAR(s) must be reported in ascending order starting with the lowest numbered BAR such that
the first range corresponds to the first BAR and so on. The range ID reports the BAR equivalent Indicator (BEI). Values 0-7
of the Range ID are reserved to indicate the BEI. The device must report the BAR equivalent Indicator (BEI) for ranges
associated with a PCIe BAR.
When reporting the MMIO range for a TDI, the MMIO ranges must be reported in the logical order in which the TDI MMIO
range is configured such that the first range reported corresponds to first range of pages in the TDI and so on.
===

What do I miss? Thanks,

---

## [85] Jason Gunthorpe — 2026-03-30
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

On Mon, Mar 30, 2026 at 04:47:44PM +1100, Alexey Kardashevskiy wrote:

> What do I miss? Thanks,

You can't tell where things start so there is no way to relate the
offsets to something the kernel can understand.

Jason

---

## [86] Alexey Kardashevskiy — 2026-04-03
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

On 30/3/26 22:49, Jason Gunthorpe wrote:
> On Mon, Mar 30, 2026 at 04:47:44PM +1100, Alexey Kardashevskiy wrote:
> 

Reported ranges have BAR indexes and start addresses (with the reported MMIO offset added), and the first reported range starts at the first 4K of that BAR. And these ranges are in sorted order. Enough to calculate an offset of a 2nd/3rd/... range of that BAR, and this is what I am after.

---

## [87] Jason Gunthorpe — 2026-04-03
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

On Fri, Apr 03, 2026 at 11:41:25PM +1100, Alexey Kardashevskiy wrote:
> 
> 

I was told this is not the case, the first reported range can start
anywhere in the BAR?

Jason

---

## [88] Alexey Kardashevskiy — 2026-04-07
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

On 4/4/26 01:08, Jason Gunthorpe wrote:
> On Fri, Apr 03, 2026 at 11:41:25PM +1100, Alexey Kardashevskiy wrote:
>>

This is what I am trying to clarify - if all ranges must be reported (as some think this is what the PCIe spec says), then no, not anywhere.

pcie r7, Table 11-16 TDI Report Structure, MMIO_RANGE:

"Each MMIO Range of the TDI is reported with the MMIO reporting offset added."

---

## [89] Jason Gunthorpe — 2026-04-06
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

On Tue, Apr 07, 2026 at 08:08:51AM +1000, Alexey Kardashevskiy wrote:
> 
> 

I think the argument was something like it didn't have to report
non-secure ranges? But I don't know, it was hashed out in some thread
for ARM and then I know our folks looked at it and nobody pushed back
to insist that every single byte of the BAR had to be covered by a
reported range.

I wouldn't take the sentance you quoted as confirmation, you need a
sentance that says every single byte of the BAR is covered by a single
reported range.

Jason

---

## [90] Xu Yilun — 2026-04-08
*Subject: Re: [PATCH v2 01/19] PCI/TSM: Report active IDE streams per host
 bridge*

On Mon, Mar 02, 2026 at 04:01:49PM -0800, Dan Williams wrote:
> The first attempt at an ABI for this failed to account for naming
> collisions across host bridges:

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

---

## [91] Alexey Kardashevskiy — 2026-04-08
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

On 7/4/26 08:21, Jason Gunthorpe wrote:
> On Tue, Apr 07, 2026 at 08:08:51AM +1000, Alexey Kardashevskiy wrote:
>>

That's (my ignorant guess) because of the ARM FW TSM guy which sees the BARs and can easily make sure that MMIO_OFFSET is such that BAR alignment is preserved (and there is a clause in PCIe about how such offset is "permitted" to be calculated) => does not make much difference on ARM but it does in my case :-/
> I wouldn't take the sentance you quoted as confirmation, you need a
> sentance that says every single byte of the BAR is covered by a single

Why "by a single range"? Every byte of a BAR needs to be covered (which is what my quote suggests) and the spec allows multiple ranges but also requires strict ascending order of the ranges, 3 paragraphs of text about it. Thanks,


> 
> Jason

---

## [92] Jason Gunthorpe — 2026-04-08
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

On Wed, Apr 08, 2026 at 05:03:16PM +1000, Alexey Kardashevskiy wrote:
> > > This is what I am trying to clarify - if all ranges muI thinkst be reported
> > > (as some think this is what the PCIe spec says), then no, not

No, your quote doesn't suggest that at all, it just says if a range is
present it has to be offset.

In fact the spec specifically says not to report ranges sometimes:

 Bit 0 -  MSI-X Table - if the range maps MSI-X table. This
 must be reported **only if locked** by the
 LOCK_INTERFACE_REQUEST.

So if the MSI-X table is not locked then what is reported? Seems not
covered by a range at all is the consensus answer.

Thus you get this case where the non-reported MSI-X table could be at
byte 0, not get a range and then there is no range covering byte 0 of
the bar at all.

> and the spec allows multiple ranges but also requires strict
> ascending order of the ranges, 3 paragraphs of text about

single range per byte means there are not overlapping ranges.

This was the old thread with my suggestion.

https://lore.kernel.org/all/20250911134107.GG882933@ziepe.ca/

If this is important to AMD they need to get an ECN with PCI-SIG to
clarify. I think as of right now Linux can't assume the ranges start
at bar physical offset 0.

Jason

---

## [93] Alexey Kardashevskiy — 2026-04-09
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

On 9/4/26 02:54, Jason Gunthorpe wrote:
> On Wed, Apr 08, 2026 at 05:03:16PM +1000, Alexey Kardashevskiy wrote:
>>>> This is what I am trying to clarify - if all ranges muI thinkst be reported

At all? My hw architect says it does.

PCIe says "Each MMIO Range of the TDI is reported with the MMIO reporting offset added."
Not "Each reported MMIO Range of the TDI is reported with the MMIO reporting offset added."


> In fact the spec specifically says not to report ranges sometimes:
> 

This is the only case when dropping a range in the report is allowed and even required. When this happens, the OS knows MSIX is not locked (part of the FW ABI) and the OS knows where MSIX BAR is and can easily amend the report.


>> and the spec allows multiple ranges but also requires strict
>> ascending order of the ranges, 3 paragraphs of text about

ah, misread, sorry.

> This was the old thread with my suggestion.
> 

uff may be...

> 
> Jason

---

## [94] Jason Gunthorpe — 2026-04-08
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

On Thu, Apr 09, 2026 at 08:22:57AM +1000, Alexey Kardashevskiy wrote:
> 
> 

I don't see how you can possibly read that phrase that way. Go ask
your PCI SIG rep.

> PCIe says "Each MMIO Range of the TDI is reported with the MMIO
> reporting offset added."

"MMIO Range" does not refer to an entire bar, it refers to an entry in
the rage table.

> > In fact the spec specifically says not to report ranges sometimes:
> > 

Which firmly disproves the assertion about the first phrase.

> When this happens, the OS knows MSIX is not
> locked (part of the FW ABI) and the OS knows where MSIX BAR is and

Typically OS has no idea how big MSIX things actually are, there is no
way to fix things if the hole is at the start of the BAR, and that's a
legal design.

Jason

---

## [95] Aneesh Kumar K.V — 2026-04-09
*Subject: Re: [PATCH v2 10/19] x86, swiotlb: Teach swiotlb to skip "accepted"
 devices*

Dan Williams <dan.j.williams@intel.com> writes:

> There are two mechanisms to force SWIOTLB operation, the kernel command
> line option and the internal SWIOTLB_FORCE flag. With the arrival of

I guess we can also include arm64 change here
modified   arch/arm64/mm/init.c
@@ -335,7 +335,7 @@ void __init arch_mm_preinit(void)
 
 	if (is_realm_world()) {
 		swiotlb = true;
-		flags |= SWIOTLB_FORCE;
+		flags |= SWIOTLB_UNACCEPTED;
 	}
 
 	if (IS_ENABLED(CONFIG_DMA_BOUNCE_UNALIGNED_KMALLOC) && !swiotlb) {

-aneesh

---

## [96] Aneesh Kumar K.V — 2026-04-09
*Subject: Re: [PATCH v2 09/19] PCI/TSM: Support creating encrypted MMIO
 descriptors via TDISP Report*

Jason Gunthorpe <jgg@nvidia.com> writes:

> On Fri, Mar 13, 2026 at 06:23:51PM +0800, Xu Yilun wrote:
>

ARM CCA spec mention these restrictions in section

A9.6.2 Realm validation of device memory mappings

-aneesh

---

## [97] Lai, Yi — 2026-04-10
*Subject: Re: [PATCH v2 07/19] PCI/TSM: Add Device Security (TVM Guest) ACCEPT
 operation support*

On Mon, Mar 02, 2026 at 04:01:55PM -0800, Dan Williams wrote:
> The final operation of the PCIe Trusted Execution Environment (TEE) Device
> Interface Security Protocol (TDISP) is asking the TEE Security Manager

Hi Dan,

Repeated accept on a device that is already in RUN state is not rejected
by the PCI TSM core, and multiple encrypted MMIO resources for the same
BAR range can be created. Furthermore, a later request to move the
device to UNLOCKED state only removes the most recently tracked
encrypted range.

Reproduce steps:
1. echo tsmX > /sys/bus/pci/devices/<bdf>/tsm/lock
2. echo 1 > /sys/bus/pci/devices/<bdf>/tsm/accept
3. echo 1 > /sys/bus/pci/devices/<bdf>/tsm/accept
4. cat /proc/iomem | grep "PCI MMIO Encrypted"
5. echo tsmX > /sys/bus/pci/devices/<bdf>/tsm/unlock
6. cat /proc/iomem | grep "PCI MMIO Encrypted"

Observed results after step4 (duplicate BAR range):
380002000000-3800021fffff : PCI MMIO Encrypted
  380002000000-3800021fffff : PCI MMIO Encrypted

Observed results after step 6 (leaked resource):
380002000000-3800021fffff : PCI MMIO Encrypted

Regards,
Yi Lai

> +static int pci_tsm_accept(struct pci_dev *pdev)
> +{

---

## [98] Lai, Yi — 2026-04-10
*Subject: Re: [PATCH v2 07/19] PCI/TSM: Add Device Security (TVM Guest) ACCEPT
 operation support*

On Mon, Mar 02, 2026 at 04:01:55PM -0800, Dan Williams wrote:
> The final operation of the PCIe Trusted Execution Environment (TEE) Device
> Interface Security Protocol (TDISP) is asking the TEE Security Manager
# Re-send to Dan's kernel.org address. Sorry if you receive the same
# email twice.

Repeated accept on a device that is already in RUN state is not rejected
by the PCI TSM core, and multiple encrypted MMIO resources for the same
BAR range can be created. Furthermore, a later request to move the
device to UNLOCKED state only removes the most recently tracked
encrypted range.

Reproduce steps:
1. echo tsmX > /sys/bus/pci/devices/<bdf>/tsm/lock
2. echo 1 > /sys/bus/pci/devices/<bdf>/tsm/accept
3. echo 1 > /sys/bus/pci/devices/<bdf>/tsm/accept
4. cat /proc/iomem | grep "PCI MMIO Encrypted"
5. echo tsmX > /sys/bus/pci/devices/<bdf>/tsm/unlock
6. cat /proc/iomem | grep "PCI MMIO Encrypted"

Observed results after step4 (duplicate BAR range):
380002000000-3800021fffff : PCI MMIO Encrypted
  380002000000-3800021fffff : PCI MMIO Encrypted

Observed results after step 6 (leaked resource):
380002000000-3800021fffff : PCI MMIO Encrypted

Regards,
Yi Lai

> +static ssize_t accept_store(struct device *dev, struct device_attribute *attr,
> +			    const char *buf, size_t len)

---

## [99] Aneesh Kumar K.V — 2026-04-24
*Subject: Re: [PATCH v2 08/19] PCI/TSM: Add "evidence" support*

Dan Williams <dan.j.williams@intel.com> writes:

> The ARM CCA spec does reference the EAT nonce which is 64-bytes. So it
> may be the case that PCI_TSM_MAX_NONCE_SIZE != SPDM_NONCE_SZ depending

That was probably me getting confused about 256 bits in an earlier
version of the code. Also, the RmiVdevMeasureParams structure layout
adds 256 bytes of padding between the different fields.

-aneesh

---
