---
title: 'PCI/TSM: Finalize "Link" TSM infrastructure'
date: 2025-11-04
last_reply: 2025-11-13
message_count: 23
participants: ['Dan Williams', 'Aneesh Kumar K.V', 'Jonathan Cameron']
---

## [1] Dan Williams — 2025-11-04

Now that the base series has settled [1], here is a collection of topics
to finish off the "Link" side of the PCI/TSM core. Recall that "Link"
refers to all the physical device security aspects of TEE Device
Interface Security Protocol (TDISP) managed by the host kernel / VMM.

[1]: http://lore.kernel.org/20251031212902.2256310-1-dan.j.williams@intel.com

Add support for Address Association registers that helps root port
hardware pick the Selective IDE Stream to use for a downstream memory
transaction.

Add support for devices that expect to have all Stream IDs on the device
configured to unique values even if the given stream is not in use.

Add an operation for requesting a device enter the LOCKED TDISP state
(pci_tsm_bind())). This has no user outside of test code in the staging
tree [2] for now, but examples exist in the SEV-TIO and ARM CCA RFC
branches.

Add an operation for marshaling TDISP collateral and TDISP state change
requests from confidential guests to the platform TSM
(pci_tsm_guest_req()). This too has no consumer in the staging branch
outside of the samples/devsec/ test module, but is used in the vendor
RFC branches that will soon be incorporated into the staging branch.

These patches have previously appeared in the tsm.git#staging branch [3]
for integration testing.

[2]: https://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git/tree/samples/devsec/link_tsm.c?h=staging#n306
[3]: https://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git/log/?h=staging

Dan Williams (5):
  resource: Introduce resource_assigned() for discerning active
    resources
  PCI/IDE: Initialize an ID for all IDE streams
  PCI/TSM: Add pci_tsm_bind() helper for instantiating TDIs
  PCI/TSM: Add pci_tsm_guest_req() for managing TDIs
  PCI/TSM: Add 'dsm' and 'bound' attributes for dependent functions

Xu Yilun (1):
  PCI/IDE: Add Address Association Register setup for downstream MMIO

 Documentation/ABI/testing/sysfs-bus-pci |  30 +++
 drivers/pci/pci.h                       |   2 +
 include/linux/ioport.h                  |   9 +
 include/linux/pci-ide.h                 |  33 +++
 include/linux/pci-tsm.h                 |  92 +++++++
 include/linux/pci.h                     |   6 +
 drivers/pci/ide.c                       | 248 ++++++++++++++++++-
 drivers/pci/remove.c                    |   1 +
 drivers/pci/tsm.c                       | 303 ++++++++++++++++++++++--
 9 files changed, 694 insertions(+), 30 deletions(-)


base-commit: 0fe2f67a913cedca2be48c5b7b0412cbbaf29108

---

## [2] Dan Williams — 2025-11-04
*Subject: [PATCH 1/6] resource: Introduce resource_assigned() for discerning active resources*

A PCI bridge resource lifecycle involves both a "request" and "assign"
phase. At any point in time that resource may not yet be assigned, or may
have failed to assign (because it does not fit).

There are multiple conventions to determine when assignment has not
completed: IORESOURCE_UNSET, IORESOURCE_DISABLED, and checking whether the
resource is parented.

In code paths that are known to not be racing assignment, e.g. post
subsys_initcall(), the most reliable method to judge that a bridge resource
is assigned is to check the resource is parented [1].

Introduce a resource_assigned() helper for this purpose.

Link: http://lore.kernel.org/2b9f7f7b-d6a4-be59-14d4-7b4ffccfe373@linux.intel.com [1]
Suggested-by: Ilpo Järvinen <ilpo.jarvinen@linux.intel.com>
Cc: Bjorn Helgaas <bhelgaas@google.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 include/linux/ioport.h | 9 +++++++++
 1 file changed, 9 insertions(+)

diff --git a/include/linux/ioport.h b/include/linux/ioport.h
index e8b2d6aa4013..9afa30f9346f 100644
--- a/include/linux/ioport.h
+++ b/include/linux/ioport.h
@@ -334,6 +334,15 @@ static inline bool resource_union(const struct resource *r1, const struct resour
 	return true;
 }
 
+/*
+ * Check if this resource is added to a resource tree or detached. Caller is
+ * responsible for not racing assignment.
+ */
+static inline bool resource_assigned(struct resource *res)
+{
+	return res->parent;
+}
+
 int find_resource_space(struct resource *root, struct resource *new,
 			resource_size_t size, struct resource_constraint *constraint);

---

## [3] Dan Williams — 2025-11-04
*Subject: [PATCH 2/6] PCI/IDE: Add Address Association Register setup for downstream MMIO*

From: Xu Yilun <yilun.xu@linux.intel.com>

The address ranges for downstream Address Association Registers need to
cover memory addresses for all functions (PFs/VFs/downstream devices)
managed by a Device Security Manager (DSM). The proposed solution is get
the memory (32-bit only) range and prefetchable-memory (64-bit capable)
range from the immediate ancestor downstream port (either the direct-attach
RP or deepest switch port when switch attached).

Similar to RID association, address associations will be set by default if
hardware sets 'Number of Address Association Register Blocks' in the
'Selective IDE Stream Capability Register' to a non-zero value. TSM drivers
can opt-out of the settings by zero'ing out unwanted / unsupported address
ranges. E.g. TDX Connect only supports prefetachable (64-bit capable)
memory ranges for the Address Association setting.

If the immediate downstream port provides both a memory range and
prefetchable-memory range, but the IDE partner port only provides 1 Address
Association Register block then the TSM driver can pick which range to
associate, or let the PCI core prioritize memory.

Note, the Address Association Register setup for upstream requests is still
uncertain so is not included.

Co-developed-by: Aneesh Kumar K.V <aneesh.kumar@kernel.org>
Signed-off-by: Aneesh Kumar K.V <aneesh.kumar@kernel.org>
Co-developed-by: Arto Merilainen <amerilainen@nvidia.com>
Signed-off-by: Arto Merilainen <amerilainen@nvidia.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Co-developed-by: Dan Williams <dan.j.williams@intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 include/linux/pci-ide.h |  27 ++++++++++
 include/linux/pci.h     |   5 ++
 drivers/pci/ide.c       | 115 ++++++++++++++++++++++++++++++++++++----
 3 files changed, 138 insertions(+), 9 deletions(-)

diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
index d0f10f3c89fc..55283c8490e4 100644
--- a/include/linux/pci-ide.h
+++ b/include/linux/pci-ide.h
@@ -28,6 +28,9 @@ enum pci_ide_partner_select {
  * @rid_start: Partner Port Requester ID range start
  * @rid_end: Partner Port Requester ID range end
  * @stream_index: Selective IDE Stream Register Block selection
+ * @mem_assoc: PCI bus memory address association for targeting peer partner
+ * @pref_assoc: (optional) PCI bus prefetchable memory address association for
+ *		targeting peer partner
  * @default_stream: Endpoint uses this stream for all upstream TLPs regardless of
  *		    address and RID association registers
  * @setup: flag to track whether to run pci_ide_stream_teardown() for this
@@ -38,11 +41,35 @@ struct pci_ide_partner {
 	u16 rid_start;
 	u16 rid_end;
 	u8 stream_index;
+	struct pci_bus_region mem_assoc;
+	struct pci_bus_region pref_assoc;
 	unsigned int default_stream:1;
 	unsigned int setup:1;
 	unsigned int enable:1;
 };
 
+/**
+ * struct pci_ide_regs - Hardware register association settings for Selective
+ *			 IDE Streams
+ * @rid1: IDE RID Association Register 1
+ * @rid2: IDE RID Association Register 2
+ * @addr: Up to two address association blocks (IDE Address Association Register
+ *	  1 through 3) for MMIO and prefetchable MMIO
+ * @nr_addr: Number of address association blocks initialized
+ *
+ * See pci_ide_stream_to_regs()
+ */
+struct pci_ide_regs {
+	u32 rid1;
+	u32 rid2;
+	struct {
+		u32 assoc1;
+		u32 assoc2;
+		u32 assoc3;
+	} addr[2];
+	int nr_addr;
+};
+
 /**
  * struct pci_ide - PCIe Selective IDE Stream descriptor
  * @pdev: PCIe Endpoint in the pci_ide_partner pair
diff --git a/include/linux/pci.h b/include/linux/pci.h
index 9e9a9f7977a2..0a66230e28cf 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -870,6 +870,11 @@ struct pci_bus_region {
 	pci_bus_addr_t	end;
 };
 
+static inline pci_bus_addr_t pci_bus_region_size(const struct pci_bus_region *region)
+{
+	return region->end - region->start + 1;
+}
+
 struct pci_dynids {
 	spinlock_t		lock;	/* Protects list, index */
 	struct list_head	list;	/* For IDs added at runtime */
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index da5b1acccbb4..d7fc741f3a26 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -155,8 +155,11 @@ struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev)
 {
 	/* EP, RP, + HB Stream allocation */
 	struct stream_index __stream[PCI_IDE_HB + 1];
+	struct pci_bus_region pref_assoc = { 0, -1 };
+	struct pci_bus_region mem_assoc = { 0, -1 };
+	struct resource *mem, *pref;
 	struct pci_host_bridge *hb;
-	struct pci_dev *rp;
+	struct pci_dev *rp, *br;
 	int num_vf, rid_end;
 
 	if (!pci_is_pcie(pdev))
@@ -197,6 +200,21 @@ struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev)
 	else
 		rid_end = pci_dev_id(pdev);
 
+	br = pci_upstream_bridge(pdev);
+	if (!br)
+		return NULL;
+
+	/*
+	 * Check if the device consumes memory and/or prefetch-memory. Setup
+	 * downstream address association ranges for each.
+	 */
+	mem = pci_resource_n(br, PCI_BRIDGE_MEM_WINDOW);
+	pref = pci_resource_n(br, PCI_BRIDGE_PREF_MEM_WINDOW);
+	if (resource_assigned(mem))
+		pcibios_resource_to_bus(br->bus, &mem_assoc, mem);
+	if (resource_assigned(pref))
+		pcibios_resource_to_bus(br->bus, &pref_assoc, pref);
+
 	*ide = (struct pci_ide) {
 		.pdev = pdev,
 		.partner = {
@@ -204,11 +222,16 @@ struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev)
 				.rid_start = pci_dev_id(rp),
 				.rid_end = pci_dev_id(rp),
 				.stream_index = no_free_ptr(ep_stream)->stream_index,
+				/* Disable upstream address association */
+				.mem_assoc = { 0, -1 },
+				.pref_assoc = { 0, -1 },
 			},
 			[PCI_IDE_RP] = {
 				.rid_start = pci_dev_id(pdev),
 				.rid_end = rid_end,
 				.stream_index = no_free_ptr(rp_stream)->stream_index,
+				.mem_assoc = mem_assoc,
+				.pref_assoc = pref_assoc,
 			},
 		},
 		.host_bridge_stream = no_free_ptr(hb_stream)->stream_index,
@@ -385,6 +408,61 @@ static void set_ide_sel_ctl(struct pci_dev *pdev, struct pci_ide *ide,
 	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, val);
 }
 
+#define SEL_ADDR1_LOWER GENMASK(31, 20)
+#define SEL_ADDR_UPPER GENMASK_ULL(63, 32)
+#define PREP_PCI_IDE_SEL_ADDR1(base, limit)			\
+	(FIELD_PREP(PCI_IDE_SEL_ADDR_1_VALID, 1) |		\
+	 FIELD_PREP(PCI_IDE_SEL_ADDR_1_BASE_LOW,		\
+		    FIELD_GET(SEL_ADDR1_LOWER, (base))) |	\
+	 FIELD_PREP(PCI_IDE_SEL_ADDR_1_LIMIT_LOW,		\
+		    FIELD_GET(SEL_ADDR1_LOWER, (limit))))
+
+static void mem_assoc_to_regs(struct pci_bus_region *region,
+			      struct pci_ide_regs *regs, int idx)
+{
+	regs->addr[idx].assoc1 =
+		PREP_PCI_IDE_SEL_ADDR1(region->start, region->end);
+	regs->addr[idx].assoc2 = FIELD_GET(SEL_ADDR_UPPER, region->end);
+	regs->addr[idx].assoc3 = FIELD_GET(SEL_ADDR_UPPER, region->start);
+}
+
+/**
+ * pci_ide_stream_to_regs() - convert IDE settings to association register values
+ * @pdev: PCIe device object for either a Root Port or Endpoint Partner Port
+ * @ide: registered IDE settings descriptor
+ * @regs: output register values
+ */
+static void pci_ide_stream_to_regs(struct pci_dev *pdev, struct pci_ide *ide,
+				   struct pci_ide_regs *regs)
+{
+	struct pci_ide_partner *settings = pci_ide_to_settings(pdev, ide);
+	int assoc_idx = 0;
+
+	memset(regs, 0, sizeof(*regs));
+
+	if (!settings)
+		return;
+
+	regs->rid1 = FIELD_PREP(PCI_IDE_SEL_RID_1_LIMIT, settings->rid_end);
+
+	regs->rid2 = FIELD_PREP(PCI_IDE_SEL_RID_2_VALID, 1) |
+		     FIELD_PREP(PCI_IDE_SEL_RID_2_BASE, settings->rid_start) |
+		     FIELD_PREP(PCI_IDE_SEL_RID_2_SEG, pci_ide_domain(pdev));
+
+	if (pdev->nr_ide_mem && pci_bus_region_size(&settings->mem_assoc)) {
+		mem_assoc_to_regs(&settings->mem_assoc, regs, assoc_idx);
+		assoc_idx++;
+	}
+
+	if (pdev->nr_ide_mem > assoc_idx &&
+	    pci_bus_region_size(&settings->pref_assoc)) {
+		mem_assoc_to_regs(&settings->pref_assoc, regs, assoc_idx);
+		assoc_idx++;
+	}
+
+	regs->nr_addr = assoc_idx;
+}
+
 /**
  * pci_ide_stream_setup() - program settings to Selective IDE Stream registers
  * @pdev: PCIe device object for either a Root Port or Endpoint Partner Port
@@ -398,22 +476,34 @@ static void set_ide_sel_ctl(struct pci_dev *pdev, struct pci_ide *ide,
 void pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide)
 {
 	struct pci_ide_partner *settings = pci_ide_to_settings(pdev, ide);
+	struct pci_ide_regs regs;
 	int pos;
-	u32 val;
 
 	if (!settings)
 		return;
 
+	pci_ide_stream_to_regs(pdev, ide, &regs);
+
 	pos = sel_ide_offset(pdev, settings);
 
-	val = FIELD_PREP(PCI_IDE_SEL_RID_1_LIMIT, settings->rid_end);
-	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_1, val);
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_1, regs.rid1);
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_2, regs.rid2);
 
-	val = FIELD_PREP(PCI_IDE_SEL_RID_2_VALID, 1) |
-	      FIELD_PREP(PCI_IDE_SEL_RID_2_BASE, settings->rid_start) |
-	      FIELD_PREP(PCI_IDE_SEL_RID_2_SEG, pci_ide_domain(pdev));
+	for (int i = 0; i < regs.nr_addr; i++) {
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_1(i),
+				       regs.addr[i].assoc1);
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_2(i),
+				       regs.addr[i].assoc2);
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_3(i),
+				       regs.addr[i].assoc3);
+	}
 
-	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_2, val);
+	/* clear extra unused address association blocks */
+	for (int i = regs.nr_addr; i < pdev->nr_ide_mem; i++) {
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_1(i), 0);
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_2(i), 0);
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_3(i), 0);
+	}
 
 	/*
 	 * Setup control register early for devices that expect
@@ -436,7 +526,7 @@ EXPORT_SYMBOL_GPL(pci_ide_stream_setup);
 void pci_ide_stream_teardown(struct pci_dev *pdev, struct pci_ide *ide)
 {
 	struct pci_ide_partner *settings = pci_ide_to_settings(pdev, ide);
-	int pos;
+	int pos, i;
 
 	if (!settings)
 		return;
@@ -444,6 +534,13 @@ void pci_ide_stream_teardown(struct pci_dev *pdev, struct pci_ide *ide)
 	pos = sel_ide_offset(pdev, settings);
 
 	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, 0);
+
+	for (i = 0; i < pdev->nr_ide_mem; i++) {
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_1(i), 0);
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_2(i), 0);
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_3(i), 0);
+	}
+
 	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_2, 0);
 	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_1, 0);
 	settings->setup = 0;

---

## [4] Dan Williams — 2025-11-04
*Subject: [PATCH 3/6] PCI/IDE: Initialize an ID for all IDE streams*

The PCIe spec defines two types of streams - selective and link.  Each
stream has an ID from the same bucket so a stream ID does not tell the
type.  The spec defines an "enable" bit for every stream and required
stream IDs to be unique among all enabled stream but there is no such
requirement for disabled streams.

However, when IDE_KM is programming keys, an IDE-capable device needs
to know the type of stream being programmed to write it directly to
the hardware as keys are relatively large, possibly many of them and
devices often struggle with keeping around rather big data not being
used.

Walk through all streams on a device and initialise the IDs to some
unique number, both link and selective.

The weakest part of this proposal is the host bridge ide_stream_ids_ida.
Technically, a Stream ID only needs to be unique within a given partner
pair. However, with "anonymous" / unassigned streams there is no convenient
place to track the available ids. Proceed with an ida in the host bridge
for now, but consider moving this tracking to be an ide_stream_ids_ida per
device.

Co-developed-by: Alexey Kardashevskiy <aik@amd.com>
Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/pci/pci.h       |   2 +
 include/linux/pci-ide.h |   6 ++
 include/linux/pci.h     |   1 +
 drivers/pci/ide.c       | 133 ++++++++++++++++++++++++++++++++++++++++
 drivers/pci/remove.c    |   1 +
 5 files changed, 143 insertions(+)

diff --git a/drivers/pci/pci.h b/drivers/pci/pci.h
index f6ffe5ee4717..641c0b53c4e3 100644
--- a/drivers/pci/pci.h
+++ b/drivers/pci/pci.h
@@ -616,10 +616,12 @@ static inline void pci_doe_sysfs_teardown(struct pci_dev *pdev) { }
 #ifdef CONFIG_PCI_IDE
 void pci_ide_init(struct pci_dev *dev);
 void pci_ide_init_host_bridge(struct pci_host_bridge *hb);
+void pci_ide_destroy(struct pci_dev *dev);
 extern const struct attribute_group pci_ide_attr_group;
 #else
 static inline void pci_ide_init(struct pci_dev *dev) { }
 static inline void pci_ide_init_host_bridge(struct pci_host_bridge *hb) { }
+static inline void pci_ide_destroy(struct pci_dev *dev) { }
 #endif
 
 #ifdef CONFIG_PCI_TSM
diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
index 55283c8490e4..40f0be185120 100644
--- a/include/linux/pci-ide.h
+++ b/include/linux/pci-ide.h
@@ -92,6 +92,12 @@ struct pci_ide {
 	struct tsm_dev *tsm_dev;
 };
 
+/*
+ * Some devices need help with aliased stream-ids even for idle streams. Use
+ * this id as the "never enabled" place holder.
+ */
+#define PCI_IDE_RESERVED_STREAM_ID 255
+
 void pci_ide_set_nr_streams(struct pci_host_bridge *hb, u16 nr);
 struct pci_ide_partner *pci_ide_to_settings(struct pci_dev *pdev,
 					    struct pci_ide *ide);
diff --git a/include/linux/pci.h b/include/linux/pci.h
index 0a66230e28cf..1a31353dc109 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -619,6 +619,7 @@ struct pci_host_bridge {
 #ifdef CONFIG_PCI_IDE
 	u16 nr_ide_streams; /* Max streams possibly active in @ide_stream_ida */
 	struct ida ide_stream_ida;
+	struct ida ide_stream_ids_ida; /* track unique ids per domain */
 #endif
 	u8 (*swizzle_irq)(struct pci_dev *, u8 *); /* Platform IRQ swizzler */
 	int (*map_irq)(const struct pci_dev *, u8, u8);
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index d7fc741f3a26..33b3c54c62a1 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -35,8 +35,54 @@ static int sel_ide_offset(struct pci_dev *pdev,
 				settings->stream_index, pdev->nr_ide_mem);
 }
 
+static bool reserve_stream_index(struct pci_dev *pdev, u8 idx)
+{
+	int ret;
+
+	ret = ida_alloc_range(&pdev->ide_stream_ida, idx, idx, GFP_KERNEL);
+	if (ret < 0)
+		return false;
+	return true;
+}
+
+static bool reserve_stream_id(struct pci_host_bridge *hb, u8 id)
+{
+	int ret;
+
+	ret = ida_alloc_range(&hb->ide_stream_ids_ida, id, id, GFP_KERNEL);
+	if (ret < 0)
+		return false;
+	return true;
+}
+
+static bool claim_stream(struct pci_host_bridge *hb, u8 stream_id,
+			 struct pci_dev *pdev, u8 stream_idx)
+{
+	dev_info(&hb->dev, "Stream ID %d active at init\n", stream_id);
+	if (!reserve_stream_id(hb, stream_id)) {
+		dev_info(&hb->dev, "Failed to claim %s Stream ID %d\n",
+			 stream_id == PCI_IDE_RESERVED_STREAM_ID ? "reserved" :
+								   "active",
+			 stream_id);
+		return false;
+	}
+
+	/* No stream index to reserve in the Link IDE case */
+	if (!pdev)
+		return true;
+
+	if (!reserve_stream_index(pdev, stream_idx)) {
+		pci_info(pdev, "Failed to claim active Selective Stream %d\n",
+			 stream_idx);
+		return false;
+	}
+
+	return true;
+}
+
 void pci_ide_init(struct pci_dev *pdev)
 {
+	struct pci_host_bridge *hb = pci_find_host_bridge(pdev->bus);
 	u16 nr_link_ide, nr_ide_mem, nr_streams;
 	u16 ide_cap;
 	u32 val;
@@ -83,6 +129,7 @@ void pci_ide_init(struct pci_dev *pdev)
 		int pos = __sel_ide_offset(ide_cap, nr_link_ide, i, nr_ide_mem);
 		int nr_assoc;
 		u32 val;
+		u8 id;
 
 		pci_read_config_dword(pdev, pos + PCI_IDE_SEL_CAP, &val);
 
@@ -98,6 +145,51 @@ void pci_ide_init(struct pci_dev *pdev)
 		}
 
 		nr_ide_mem = nr_assoc;
+
+		/*
+		 * Claim Stream IDs and Selective Stream blocks that are already
+		 * active on the device
+		 */
+		pci_read_config_dword(pdev, pos + PCI_IDE_SEL_CTL, &val);
+		id = FIELD_GET(PCI_IDE_SEL_CTL_ID, val);
+		if ((val & PCI_IDE_SEL_CTL_EN) &&
+		    !claim_stream(hb, id, pdev, i))
+			return;
+	}
+
+	/* Reserve link stream-ids that are already active on the device */
+	for (u16 i = 0; i < nr_link_ide; ++i) {
+		int pos = ide_cap + PCI_IDE_LINK_STREAM_0 + i * PCI_IDE_LINK_BLOCK_SIZE;
+		u8 id;
+
+		pci_read_config_dword(pdev, pos + PCI_IDE_LINK_CTL_0, &val);
+		id = FIELD_GET(PCI_IDE_LINK_CTL_ID, val);
+		if ((val & PCI_IDE_LINK_CTL_EN) &&
+		    !claim_stream(hb, id, NULL, -1))
+			return;
+	}
+
+	for (u16 i = 0; i < nr_streams; i++) {
+		int pos = __sel_ide_offset(ide_cap, nr_link_ide, i, nr_ide_mem);
+
+		pci_read_config_dword(pdev, pos + PCI_IDE_SEL_CAP, &val);
+		if (val & PCI_IDE_SEL_CTL_EN)
+			continue;
+		val &= ~PCI_IDE_SEL_CTL_ID;
+		val |= FIELD_PREP(PCI_IDE_SEL_CTL_ID, PCI_IDE_RESERVED_STREAM_ID);
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, val);
+	}
+
+	for (u16 i = 0; i < nr_link_ide; ++i) {
+		int pos = ide_cap + PCI_IDE_LINK_STREAM_0 +
+			  i * PCI_IDE_LINK_BLOCK_SIZE;
+
+		pci_read_config_dword(pdev, pos, &val);
+		if (val & PCI_IDE_LINK_CTL_EN)
+			continue;
+		val &= ~PCI_IDE_LINK_CTL_ID;
+		val |= FIELD_PREP(PCI_IDE_LINK_CTL_ID, PCI_IDE_RESERVED_STREAM_ID);
+		pci_write_config_dword(pdev, pos, val);
 	}
 
 	pdev->ide_cap = ide_cap;
@@ -301,6 +393,28 @@ void pci_ide_stream_release(struct pci_ide *ide)
 }
 EXPORT_SYMBOL_GPL(pci_ide_stream_release);
 
+struct pci_ide_stream_id {
+	struct pci_host_bridge *hb;
+	u8 stream_id;
+};
+
+static struct pci_ide_stream_id *alloc_stream_id(struct pci_host_bridge *hb,
+						 u8 stream_id,
+						 struct pci_ide_stream_id *sid)
+{
+	if (!reserve_stream_id(hb, stream_id))
+		return NULL;
+
+	*sid = (struct pci_ide_stream_id) {
+		.hb = hb,
+		.stream_id = stream_id,
+	};
+
+	return sid;
+}
+DEFINE_FREE(free_stream_id, struct pci_ide_stream_id *,
+	    if (_T) ida_free(&_T->hb->ide_stream_ids_ida, _T->stream_id))
+
 /**
  * pci_ide_stream_register() - Prepare to activate an IDE Stream
  * @ide: IDE settings descriptor
@@ -313,6 +427,7 @@ int pci_ide_stream_register(struct pci_ide *ide)
 {
 	struct pci_dev *pdev = ide->pdev;
 	struct pci_host_bridge *hb = pci_find_host_bridge(pdev->bus);
+	struct pci_ide_stream_id __sid;
 	u8 ep_stream, rp_stream;
 	int rc;
 
@@ -321,6 +436,13 @@ int pci_ide_stream_register(struct pci_ide *ide)
 		return -ENXIO;
 	}
 
+	struct pci_ide_stream_id *sid __free(free_stream_id) =
+		alloc_stream_id(hb, ide->stream_id, &__sid);
+	if (!sid) {
+		pci_err(pdev, "Setup fail: Stream ID %d in use\n", ide->stream_id);
+		return -EBUSY;
+	}
+
 	ep_stream = ide->partner[PCI_IDE_EP].stream_index;
 	rp_stream = ide->partner[PCI_IDE_RP].stream_index;
 	const char *name __free(kfree) = kasprintf(GFP_KERNEL, "stream%d.%d.%d",
@@ -335,6 +457,9 @@ int pci_ide_stream_register(struct pci_ide *ide)
 
 	ide->name = no_free_ptr(name);
 
+	/* Stream ID reservation recorded in @ide is now successfully registered */
+	retain_and_null_ptr(sid);
+
 	return 0;
 }
 EXPORT_SYMBOL_GPL(pci_ide_stream_register);
@@ -353,6 +478,7 @@ void pci_ide_stream_unregister(struct pci_ide *ide)
 
 	sysfs_remove_link(&hb->dev.kobj, ide->name);
 	kfree(ide->name);
+	ida_free(&hb->ide_stream_ids_ida, ide->stream_id);
 	ide->name = NULL;
 }
 EXPORT_SYMBOL_GPL(pci_ide_stream_unregister);
@@ -614,6 +740,8 @@ void pci_ide_init_host_bridge(struct pci_host_bridge *hb)
 {
 	hb->nr_ide_streams = 256;
 	ida_init(&hb->ide_stream_ida);
+	ida_init(&hb->ide_stream_ids_ida);
+	reserve_stream_id(hb, PCI_IDE_RESERVED_STREAM_ID);
 }
 
 static ssize_t available_secure_streams_show(struct device *dev,
@@ -682,3 +810,8 @@ void pci_ide_set_nr_streams(struct pci_host_bridge *hb, u16 nr)
 	sysfs_update_group(&hb->dev.kobj, &pci_ide_attr_group);
 }
 EXPORT_SYMBOL_NS_GPL(pci_ide_set_nr_streams, "PCI_IDE");
+
+void pci_ide_destroy(struct pci_dev *pdev)
+{
+	ida_destroy(&pdev->ide_stream_ida);
+}
diff --git a/drivers/pci/remove.c b/drivers/pci/remove.c
index 803391892c4a..417a9ea59117 100644
--- a/drivers/pci/remove.c
+++ b/drivers/pci/remove.c
@@ -70,6 +70,7 @@ static void pci_destroy_dev(struct pci_dev *dev)
 	up_write(&pci_bus_sem);
 
 	pci_doe_destroy(dev);
+	pci_ide_destroy(dev);
 	pcie_aspm_exit_link_state(dev);
 	pci_bridge_d3_update(dev);
 	pci_pwrctrl_unregister(&dev->dev);

---

## [5] Dan Williams — 2025-11-04
*Subject: [PATCH 4/6] PCI/TSM: Add pci_tsm_bind() helper for instantiating TDIs*

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
 include/linux/pci-tsm.h |  34 +++++++++++++
 drivers/pci/tsm.c       | 110 +++++++++++++++++++++++++++++++++++++++-
 2 files changed, 143 insertions(+), 1 deletion(-)

diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index e921d30f9b6c..95b6a46423bb 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -6,6 +6,8 @@
 
 struct pci_tsm;
 struct tsm_dev;
+struct kvm;
+enum pci_tsm_req_scope;
 
 /*
  * struct pci_tsm_ops - manage confidential links and security state
@@ -29,12 +31,16 @@ struct pci_tsm_ops {
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
 		struct pci_tsm *(*probe)(struct tsm_dev *tsm_dev,
@@ -42,6 +48,9 @@ struct pci_tsm_ops {
 		void (*remove)(struct pci_tsm *tsm);
 		int (*connect)(struct pci_dev *pdev);
 		void (*disconnect)(struct pci_dev *pdev);
+		struct pci_tdi *(*bind)(struct pci_dev *pdev,
+					struct kvm *kvm, u32 tdi_id);
+		void (*unbind)(struct pci_tdi *tdi);
 	);
 
 	/*
@@ -61,12 +70,25 @@ struct pci_tsm_ops {
 	);
 };
 
+/**
+ * struct pci_tdi - Core TEE I/O Device Interface (TDI) context
+ * @pdev: host side representation of guest-side TDI
+ * @kvm: TEE VM context of bound TDI
+ * @tdi_id: Identifier (virtual BDF) for the TDI as referenced by the TSM and DSM
+ */
+struct pci_tdi {
+	struct pci_dev *pdev;
+	struct kvm *kvm;
+	u32 tdi_id;
+};
+
 /**
  * struct pci_tsm - Core TSM context for a given PCIe endpoint
  * @pdev: Back ref to device function, distinguishes type of pci_tsm context
  * @dsm_dev: PCI Device Security Manager for link operations on @pdev
  * @tsm_dev: PCI TEE Security Manager device for Link Confidentiality or Device
  *	     Function Security operations
+ * @tdi: TDI context established by the @bind link operation
  *
  * This structure is wrapped by low level TSM driver data and returned by
  * probe()/lock(), it is freed by the corresponding remove()/unlock().
@@ -82,6 +104,7 @@ struct pci_tsm {
 	struct pci_dev *pdev;
 	struct pci_dev *dsm_dev;
 	struct tsm_dev *tsm_dev;
+	struct pci_tdi *tdi;
 };
 
 /**
@@ -139,6 +162,10 @@ int pci_tsm_pf0_constructor(struct pci_dev *pdev, struct pci_tsm_pf0 *tsm,
 void pci_tsm_pf0_destructor(struct pci_tsm_pf0 *tsm);
 int pci_tsm_doe_transfer(struct pci_dev *pdev, u8 type, const void *req,
 			 size_t req_sz, void *resp, size_t resp_sz);
+int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u32 tdi_id);
+void pci_tsm_unbind(struct pci_dev *pdev);
+void pci_tsm_tdi_constructor(struct pci_dev *pdev, struct pci_tdi *tdi,
+			     struct kvm *kvm, u32 tdi_id);
 #else
 static inline int pci_tsm_register(struct tsm_dev *tsm_dev)
 {
@@ -153,5 +180,12 @@ static inline int pci_tsm_doe_transfer(struct pci_dev *pdev, u8 type,
 {
 	return -ENXIO;
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
diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index 6a2849f77adc..f0e38d7fee38 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -270,6 +270,96 @@ static int remove_fn(struct pci_dev *pdev, void *data)
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
+	to_pci_tsm_ops(pdev->tsm)->unbind(tdi);
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
+	if (!is_link_tsm(pdev->tsm->tsm_dev))
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
+	tdi = to_pci_tsm_ops(pdev->tsm)->bind(pdev, kvm, tdi_id);
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
@@ -278,6 +368,8 @@ static void __pci_tsm_disconnect(struct pci_dev *pdev)
 	/* disconnect() mutually exclusive with subfunction pci_tsm_init() */
 	lockdep_assert_held_write(&pci_tsm_rwsem);
 
+	pci_tsm_unbind_all(pdev);
+
 	/*
 	 * disconnect() is uninterruptible as it may be called for device
 	 * teardown
@@ -439,6 +531,22 @@ static struct pci_dev *find_dsm_dev(struct pci_dev *pdev)
 	return NULL;
 }
 
+/**
+ * pci_tsm_tdi_constructor() - base 'struct pci_tdi' initialization for link TSMs
+ * @pdev: PCI device function representing the TDI
+ * @tdi: context to initialize
+ * @kvm: Private memory attach context
+ * @tdi_id: Identifier (virtual BDF) for the TDI as referenced by the TSM and DSM
+ */
+void pci_tsm_tdi_constructor(struct pci_dev *pdev, struct pci_tdi *tdi,
+			     struct kvm *kvm, u32 tdi_id)
+{
+	tdi->pdev = pdev;
+	tdi->kvm = kvm;
+	tdi->tdi_id = tdi_id;
+}
+EXPORT_SYMBOL_GPL(pci_tsm_tdi_constructor);
+
 /**
  * pci_tsm_link_constructor() - base 'struct pci_tsm' initialization for link TSMs
  * @pdev: The PCI device
@@ -532,7 +640,7 @@ int pci_tsm_register(struct tsm_dev *tsm_dev)
 
 static void pci_tsm_fn_exit(struct pci_dev *pdev)
 {
-	/* TODO: unbind the fn */
+	__pci_tsm_unbind(pdev, NULL);
 	tsm_remove(pdev->tsm);
 }

---

## [6] Dan Williams — 2025-11-04
*Subject: [PATCH 5/6] PCI/TSM: Add pci_tsm_guest_req() for managing TDIs*

A PCIe device function interface assigned to a TVM is a TEE Device
Interface (TDI). A TDI instantiated by pci_tsm_bind() needs additional
steps taken by the TVM to be accepted into the TVM's Trusted Compute
Boundary (TCB) and transitioned to the RUN state.

pci_tsm_guest_req() is a channel for the guest to request TDISP collateral,
like Device Interface Reports, and effect TDISP state changes, like
LOCKED->RUN transititions. Similar to IDE establishment and pci_tsm_bind(),
these are long running operations involving SPDM message passing via the
DOE mailbox.

The path for a TVM to invoke pci_tsm_guest_req() is:
* TSM triggers exit via guest-to-host-interface ABI (implementation specific)
* VMM invokes handler (KVM handle_exit() -> userspace io)
* handler issues request (userspace io handler -> ioctl() ->
  pci_tsm_guest_req())
* handler supplies response
* VMM posts response, notifies/re-enters TVM

This path is purely a transport for messages from TVM to platform TSM. By
design the host kernel does not and must not care about the content of
these messages. I.e. the host kernel is not in the TCB of the TVM.

As this is an opaque passthrough interface, similar to fwctl, the kernel
requires that implementations stay within the bounds defined by 'enum
pci_tsm_req_scope'. Violation of those expectations likely has market and
regulatory consequences. Out of scope requests are blocked by default.

Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 include/linux/pci-tsm.h | 62 ++++++++++++++++++++++++++++++++++++++--
 drivers/pci/tsm.c       | 63 +++++++++++++++++++++++++++++++++++++++++
 2 files changed, 123 insertions(+), 2 deletions(-)

diff --git a/include/linux/pci-tsm.h b/include/linux/pci-tsm.h
index 95b6a46423bb..8b000753b65b 100644
--- a/include/linux/pci-tsm.h
+++ b/include/linux/pci-tsm.h
@@ -3,6 +3,7 @@
 #define __PCI_TSM_H
 #include <linux/mutex.h>
 #include <linux/pci.h>
+#include <linux/sockptr.h>
 
 struct pci_tsm;
 struct tsm_dev;
@@ -33,14 +34,15 @@ struct pci_tsm_ops {
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
 		struct pci_tsm *(*probe)(struct tsm_dev *tsm_dev,
@@ -51,6 +53,11 @@ struct pci_tsm_ops {
 		struct pci_tdi *(*bind)(struct pci_dev *pdev,
 					struct kvm *kvm, u32 tdi_id);
 		void (*unbind)(struct pci_tdi *tdi);
+		ssize_t (*guest_req)(struct pci_tdi *tdi,
+				     enum pci_tsm_req_scope scope,
+				     sockptr_t req_in, size_t in_len,
+				     sockptr_t req_out, size_t out_len,
+				     u64 *tsm_code);
 	);
 
 	/*
@@ -152,6 +159,46 @@ static inline bool is_pci_tsm_pf0(struct pci_dev *pdev)
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
+	 * UNLOCKED->LOCKED, LOCKED->RUN, or other architecture specific state
+	 * changes to support those transitions for a TDI. No other (unrelated
+	 * to TDISP) device / host state, configuration, or data change is
+	 * permitted.
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
 int pci_tsm_register(struct tsm_dev *tsm_dev);
 void pci_tsm_unregister(struct tsm_dev *tsm_dev);
@@ -166,6 +213,9 @@ int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u32 tdi_id);
 void pci_tsm_unbind(struct pci_dev *pdev);
 void pci_tsm_tdi_constructor(struct pci_dev *pdev, struct pci_tdi *tdi,
 			     struct kvm *kvm, u32 tdi_id);
+ssize_t pci_tsm_guest_req(struct pci_dev *pdev, enum pci_tsm_req_scope scope,
+			  sockptr_t req_in, size_t in_len, sockptr_t req_out,
+			  size_t out_len, u64 *tsm_code);
 #else
 static inline int pci_tsm_register(struct tsm_dev *tsm_dev)
 {
@@ -187,5 +237,13 @@ static inline int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u64 tdi_id
 static inline void pci_tsm_unbind(struct pci_dev *pdev)
 {
 }
+static inline ssize_t pci_tsm_guest_req(struct pci_dev *pdev,
+					enum pci_tsm_req_scope scope,
+					sockptr_t req_in, size_t in_len,
+					sockptr_t req_out, size_t out_len,
+					u64 *tsm_code)
+{
+	return -ENXIO;
+}
 #endif
 #endif /*__PCI_TSM_H */
diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index f0e38d7fee38..4dd518b45eea 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -354,6 +354,69 @@ int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u32 tdi_id)
 }
 EXPORT_SYMBOL_GPL(pci_tsm_bind);
 
+/**
+ * pci_tsm_guest_req() - helper to marshal guest requests to the TSM driver
+ * @pdev: @pdev representing a bound tdi
+ * @scope: caller asserts this passthrough request is limited to TDISP operations
+ * @req_in: Input payload forwarded from the guest
+ * @in_len: Length of @req_in
+ * @req_out: Output payload buffer response to the guest
+ * @out_len: Length of @req_out on input, bytes filled in @req_out on output
+ * @tsm_code: Optional TSM arch specific result code for the guest TSM
+ *
+ * This is a common entry point for requests triggered by userspace KVM-exit
+ * service handlers responding to TDI information or state change requests. The
+ * scope parameter limits requests to TDISP state management, or limited debug.
+ * This path is only suitable for commands and results that are the host kernel
+ * has no use, the host is only facilitating guest to TSM communication.
+ *
+ * Returns 0 on success and -error on failure and positive "residue" on success
+ * but @req_out is filled with less then @out_len, or @req_out is NULL and a
+ * residue number of bytes were not consumed from @req_in.  On success or
+ * failure @tsm_code may be populated with a TSM implementation specific result
+ * code for the guest to consume.
+ *
+ * Context: Caller is responsible for calling this within the pci_tsm_bind()
+ * state of the TDI.
+ */
+ssize_t pci_tsm_guest_req(struct pci_dev *pdev, enum pci_tsm_req_scope scope,
+			  sockptr_t req_in, size_t in_len, sockptr_t req_out,
+			  size_t out_len, u64 *tsm_code)
+{
+	struct pci_tsm_pf0 *tsm_pf0;
+	struct pci_tdi *tdi;
+	int rc;
+
+	/*
+	 * Forbid requests that are not directly related to TDISP
+	 * operations
+	 */
+	if (scope > PCI_TSM_REQ_STATE_CHANGE)
+		return -EINVAL;
+
+	ACQUIRE(rwsem_read_intr, lock)(&pci_tsm_rwsem);
+	if ((rc = ACQUIRE_ERR(rwsem_read_intr, &lock)))
+		return rc;
+
+	if (!pdev->tsm)
+		return -ENXIO;
+
+	if (!is_link_tsm(pdev->tsm->tsm_dev))
+		return -ENXIO;
+
+	tsm_pf0 = to_pci_tsm_pf0(pdev->tsm);
+	ACQUIRE(mutex_intr, ops_lock)(&tsm_pf0->lock);
+	if ((rc = ACQUIRE_ERR(mutex_intr, &ops_lock)))
+		return rc;
+
+	tdi = pdev->tsm->tdi;
+	if (!tdi)
+		return -ENXIO;
+	return to_pci_tsm_ops(pdev->tsm)->guest_req(tdi, scope, req_in, in_len,
+						    req_out, out_len, tsm_code);
+}
+EXPORT_SYMBOL_GPL(pci_tsm_guest_req);
+
 static void pci_tsm_unbind_all(struct pci_dev *pdev)
 {
 	pci_tsm_walk_fns_reverse(pdev, __pci_tsm_unbind, NULL);

---

## [7] Dan Williams — 2025-11-04
*Subject: [PATCH 6/6] PCI/TSM: Add 'dsm' and 'bound' attributes for dependent functions*

PCI/TSM sysfs for physical function 0 devices, i.e. the "DSM" (Device
Security Manager), contains the 'connect' and 'disconnect' attributes.
After a successful 'connect' operation the DSM, its dependent functions
(SR-IOV virtual functions, non-zero multi-functions, or downstream
endpoints of a switch DSM) are candidates for being transitioned into a
TDISP (TEE Device Interface Security Protocol) operational state, via
pci_tsm_bind(). At present sysfs is blind to which devices are capable of
TDISP operation and it is ambiguous which functions are serviced by which
DSMs.

Add a 'dsm' attribute to identify a function's DSM device, and add a
'bound' attribute to identify when a function has entered a TDISP
operational state.

Cc: Bjorn Helgaas <bhelgaas@google.com>
Cc: Lukas Wunner <lukas@wunner.de>
Cc: Samuel Ortiz <sameo@rivosinc.com>
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Xu Yilun <yilun.xu@linux.intel.com>
Cc: Suzuki K Poulose <suzuki.poulose@arm.com>
Cc: "Aneesh Kumar K.V" <aneesh.kumar@kernel.org>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 Documentation/ABI/testing/sysfs-bus-pci |  30 ++++++
 drivers/pci/tsm.c                       | 130 ++++++++++++++++++++----
 2 files changed, 140 insertions(+), 20 deletions(-)

diff --git a/Documentation/ABI/testing/sysfs-bus-pci b/Documentation/ABI/testing/sysfs-bus-pci
index 6ffe02f854d6..b767db2c52cb 100644
--- a/Documentation/ABI/testing/sysfs-bus-pci
+++ b/Documentation/ABI/testing/sysfs-bus-pci
@@ -655,6 +655,36 @@ Description:
 		(WO) Write the name of the TSM device that was specified
 		to 'connect' to teardown the connection.
 
+What:		/sys/bus/pci/devices/.../tsm/dsm
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) Return PCI device name of this device's DSM (Device
+		Security Manager). When a device is in the connected state it
+		indicates that the platform TSM (TEE Security Manager) has made
+		a secure-session connection with a device's DSM. A DSM is always
+		physical function 0 and when the device supports TDISP (TEE
+		Device Interface Security Protocol) its managed functions also
+		populate this tsm/dsm attribute. The managed functions of a DSM
+		are SR-IOV (Single Root I/O Virtualization) virtual functions,
+		non-zero functions of a multi-function device, or downstream
+		endpoints depending on whether the DSM is an SR-IOV physical
+		function, function0 of a multi-function device, or an upstream
+		PCIe switch port. This is a "link" TSM attribute, see
+		Documentation/ABI/testing/sysfs-class-tsm.
+
+What:		/sys/bus/pci/devices/.../tsm/bound
+Contact:	linux-coco@lists.linux.dev
+Description:	(RO) Return the device name of the TSM when the device is in a
+		TDISP (TEE Device Interface Security Protocol) operational state
+		(LOCKED, RUN, or ERROR, not UNLOCKED). Bound devices consume
+		platform TSM resources and depend on the device's configuration
+		(e.g. BME (Bus Master Enable) and MSE (Memory Space Enable)
+		among other settings) to remain stable for the duration of the
+		bound state. This attribute is only visible for devices that
+		support TDISP operation, and it is only populated after
+		successful connect and TSM bind. The TSM bind operation is
+		initiated by VFIO/IOMMUFD. This is a "link" TSM attribute, see
+		Documentation/ABI/testing/sysfs-class-tsm.
+
 What:		/sys/bus/pci/devices/.../authenticated
 Contact:	linux-pci@vger.kernel.org
 Description:
diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index 4dd518b45eea..9abfdb2b2033 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -151,6 +151,25 @@ static void pci_tsm_walk_fns_reverse(struct pci_dev *pdev,
 	}
 }
 
+static void link_sysfs_disable(struct pci_dev *pdev)
+{
+	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_auth_attr_group);
+	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_attr_group);
+}
+
+static void link_sysfs_enable(struct pci_dev *pdev)
+{
+	bool tee = has_tee(pdev);
+
+	pci_dbg(pdev, "%s Security Manager detected (%s%s%s)\n",
+		pdev->tsm ? "Device" : "Platform TEE",
+		pdev->ide_cap ? "IDE" : "", pdev->ide_cap && tee ? " " : "",
+		tee ? "TEE" : "");
+
+	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_auth_attr_group);
+	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_attr_group);
+}
+
 static int probe_fn(struct pci_dev *pdev, void *dsm)
 {
 	struct pci_dev *dsm_dev = dsm;
@@ -159,6 +178,8 @@ static int probe_fn(struct pci_dev *pdev, void *dsm)
 	pdev->tsm = ops->probe(dsm_dev->tsm->tsm_dev, pdev);
 	pci_dbg(pdev, "setup TSM context: DSM: %s status: %s\n",
 		pci_name(dsm_dev), pdev->tsm ? "success" : "failed");
+	if (pdev->tsm)
+		link_sysfs_enable(pdev);
 	return 0;
 }
 
@@ -267,6 +288,7 @@ static DEVICE_ATTR_RW(connect);
 static int remove_fn(struct pci_dev *pdev, void *data)
 {
 	tsm_remove(pdev->tsm);
+	link_sysfs_disable(pdev);
 	return 0;
 }
 
@@ -472,12 +494,74 @@ static ssize_t disconnect_store(struct device *dev,
 }
 static DEVICE_ATTR_WO(disconnect);
 
+static ssize_t bound_show(struct device *dev,
+			  struct device_attribute *attr, char *buf)
+{
+	struct pci_dev *pdev = to_pci_dev(dev);
+	struct pci_tsm_pf0 *tsm_pf0;
+	struct pci_tsm *tsm;
+	int rc;
+
+	ACQUIRE(rwsem_read_intr, lock)(&pci_tsm_rwsem);
+	if ((rc = ACQUIRE_ERR(rwsem_read_intr, &lock)))
+		return rc;
+
+	tsm = pdev->tsm;
+	if (!tsm)
+		return sysfs_emit(buf, "\n");
+	tsm_pf0 = to_pci_tsm_pf0(tsm);
+
+	ACQUIRE(mutex_intr, ops_lock)(&tsm_pf0->lock);
+	if ((rc = ACQUIRE_ERR(mutex_intr, &ops_lock)))
+		return rc;
+
+	if (!tsm->tdi)
+		return sysfs_emit(buf, "\n");
+	return sysfs_emit(buf, "%s\n", dev_name(&tsm->tsm_dev->dev));
+}
+static DEVICE_ATTR_RO(bound);
+
+static ssize_t dsm_show(struct device *dev, struct device_attribute *attr,
+			char *buf)
+{
+	struct pci_dev *pdev = to_pci_dev(dev);
+	struct pci_tsm *tsm;
+	int rc;
+
+	ACQUIRE(rwsem_read_intr, lock)(&pci_tsm_rwsem);
+	if ((rc = ACQUIRE_ERR(rwsem_read_intr, &lock)))
+		return rc;
+
+	tsm = pdev->tsm;
+	if (!tsm)
+		return sysfs_emit(buf, "\n");
+
+	return sysfs_emit(buf, "%s\n", pci_name(tsm->dsm_dev));
+}
+static DEVICE_ATTR_RO(dsm);
+
 /* The 'authenticated' attribute is exclusive to the presence of a 'link' TSM */
 static bool pci_tsm_link_group_visible(struct kobject *kobj)
 {
 	struct pci_dev *pdev = to_pci_dev(kobj_to_dev(kobj));
 
-	return pci_tsm_link_count && is_pci_tsm_pf0(pdev);
+	if (!pci_tsm_link_count)
+		return false;
+
+	if (!pci_is_pcie(pdev))
+		return false;
+
+	if (is_pci_tsm_pf0(pdev))
+		return true;
+
+	/*
+	 * Show 'authenticated' and other attributes for the managed
+	 * sub-functions of a DSM.
+	 */
+	if (pdev->tsm)
+		return true;
+
+	return false;
 }
 DEFINE_SIMPLE_SYSFS_GROUP_VISIBLE(pci_tsm_link);
 
@@ -489,9 +573,27 @@ static umode_t pci_tsm_attr_visible(struct kobject *kobj,
 				    struct attribute *attr, int n)
 {
 	if (pci_tsm_link_group_visible(kobj)) {
+		struct pci_dev *pdev = to_pci_dev(kobj_to_dev(kobj));
+
+		if (attr == &dev_attr_bound.attr) {
+			if (is_pci_tsm_pf0(pdev) && has_tee(pdev))
+				return attr->mode;
+			if (pdev->tsm && has_tee(pdev->tsm->dsm_dev))
+				return attr->mode;
+		}
+
+		if (attr == &dev_attr_dsm.attr) {
+			if (is_pci_tsm_pf0(pdev))
+				return attr->mode;
+			if (pdev->tsm && has_tee(pdev->tsm->dsm_dev))
+				return attr->mode;
+		}
+
 		if (attr == &dev_attr_connect.attr ||
-		    attr == &dev_attr_disconnect.attr)
-			return attr->mode;
+		    attr == &dev_attr_disconnect.attr) {
+			if (is_pci_tsm_pf0(pdev))
+				return attr->mode;
+		}
 	}
 
 	return 0;
@@ -506,6 +608,8 @@ DEFINE_SYSFS_GROUP_VISIBLE(pci_tsm);
 static struct attribute *pci_tsm_attrs[] = {
 	&dev_attr_connect.attr,
 	&dev_attr_disconnect.attr,
+	&dev_attr_bound.attr,
+	&dev_attr_dsm.attr,
 	NULL
 };
 
@@ -661,18 +765,6 @@ void pci_tsm_pf0_destructor(struct pci_tsm_pf0 *pf0_tsm)
 }
 EXPORT_SYMBOL_GPL(pci_tsm_pf0_destructor);
 
-static void pf0_sysfs_enable(struct pci_dev *pdev)
-{
-	bool tee = has_tee(pdev);
-
-	pci_dbg(pdev, "Device Security Manager detected (%s%s%s)\n",
-		pdev->ide_cap ? "IDE" : "", pdev->ide_cap && tee ? " " : "",
-		tee ? "TEE" : "");
-
-	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_auth_attr_group);
-	sysfs_update_group(&pdev->dev.kobj, &pci_tsm_attr_group);
-}
-
 int pci_tsm_register(struct tsm_dev *tsm_dev)
 {
 	struct pci_dev *pdev = NULL;
@@ -693,7 +785,7 @@ int pci_tsm_register(struct tsm_dev *tsm_dev)
 	if (is_link_tsm(tsm_dev) && pci_tsm_link_count++ == 0) {
 		for_each_pci_dev(pdev)
 			if (is_pci_tsm_pf0(pdev))
-				pf0_sysfs_enable(pdev);
+				link_sysfs_enable(pdev);
 	} else if (is_devsec_tsm(tsm_dev)) {
 		pci_tsm_devsec_count++;
 	}
@@ -727,10 +819,8 @@ static void __pci_tsm_destroy(struct pci_dev *pdev, struct tsm_dev *tsm_dev)
 	 * skipped if the device itself is being removed since sysfs goes away
 	 * naturally at that point
 	 */
-	if (is_link_tsm(tsm_dev) && is_pci_tsm_pf0(pdev) && !pci_tsm_link_count) {
-		sysfs_update_group(&pdev->dev.kobj, &pci_tsm_auth_attr_group);
-		sysfs_update_group(&pdev->dev.kobj, &pci_tsm_attr_group);
-	}
+	if (is_link_tsm(tsm_dev) && is_pci_tsm_pf0(pdev) && !pci_tsm_link_count)
+		link_sysfs_disable(pdev);
 
 	/* Nothing else to do if this device never attached to the departing TSM */
 	if (!tsm)

---

## [8] Aneesh Kumar K.V — 2025-11-05
*Subject: Re: [PATCH 4/6] PCI/TSM: Add pci_tsm_bind() helper for
 instantiating TDIs*

Dan Williams <dan.j.williams@intel.com> writes:

...

> +/**
> + * pci_tsm_bind() - Bind @pdev as a TDI for @kvm

Can we set tdi in the constructor? I use it later as part of a bind()
callback. I’d prefer not to pass tdi as an argument to those functions,
since functions like do_dev_communicate() are reused in other contexts
where tdi isn't needed.

cca_tsm_bind -> cca_vdev_create -> vdev state transition to VDEV_UNLOCKED.

	/* setup host_tdi before call to device communicate */
	host_tdi = to_cca_host_tdi(pdev);
	host_tdi->rmm_vdev = rmm_vdev;

	ret = submit_vdev_state_transition_work(pdev, RMI_VDEV_UNLOCKED);
	/* failure is treated as rmi_vdev_create failure */
	if (ret)
		goto err_vdev_comm;


static inline struct cca_host_tdi *to_cca_host_tdi(struct pci_dev *pdev)
{
	struct pci_tsm *tsm = pdev->tsm;

	if (!tsm || !tsm->tdi)
		return NULL;

	return container_of(tsm->tdi, struct cca_host_tdi, tdi);
}


modified   drivers/pci/tsm.c
@@ -391,8 +391,6 @@ int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u32 tdi_id)
 	if (IS_ERR(tdi))
 		return PTR_ERR(tdi);
 
-	pdev->tsm->tdi = tdi;
-
 	return 0;
 }
 EXPORT_SYMBOL_GPL(pci_tsm_bind);
@@ -998,6 +996,7 @@ static struct pci_dev *find_dsm_dev(struct pci_dev *pdev)
 void pci_tsm_tdi_constructor(struct pci_dev *pdev, struct pci_tdi *tdi,
 			     struct kvm *kvm, u32 tdi_id)
 {
+	pdev->tsm->tdi = tdi;
 	tdi->pdev = pdev;
 	tdi->kvm = kvm;
 	tdi->tdi_id = tdi_id;

We could do a pci_tsm_tdi_destructor() to reset pdev->tsm->tdi = NULL?  

-aneesh

---

## [9] Jonathan Cameron — 2025-11-05
*Subject: Re: [PATCH 1/6] resource: Introduce resource_assigned() for
 discerning active resources*

On Tue,  4 Nov 2025 20:00:50 -0800
Dan Williams <dan.j.williams@intel.com> wrote:

> A PCI bridge resource lifecycle involves both a "request" and "assign"
> phase. At any point in time that resource may not yet be assigned, or may
One trivial thing on documentation style below.

> ---
>  include/linux/ioport.h | 9 +++++++++

Some stuff in this file now has kernel-doc style comments. To me it
seems like a better idea to use that style for new function descriptions
whilst perhaps not being worth the churn that would be inherent in switching
all docs to that style.

> +static inline bool resource_assigned(struct resource *res)
> +{

---

## [10] Jonathan Cameron — 2025-11-05
*Subject: Re: [PATCH 2/6] PCI/IDE: Add Address Association Register setup for
 downstream MMIO*

On Tue,  4 Nov 2025 20:00:51 -0800
Dan Williams <dan.j.williams@intel.com> wrote:

> From: Xu Yilun <yilun.xu@linux.intel.com>
> 

The text above about TDX only support prefetchable to me suggestions this
is optional so should be marked so like pref_assoc?

> + * @pref_assoc: (optional) PCI bus prefetchable memory address association for
> + *		targeting peer partner


> diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
> index da5b1acccbb4..d7fc741f3a26 100644


> @@ -385,6 +408,61 @@ static void set_ide_sel_ctl(struct pci_dev *pdev, struct pci_ide *ide,
>  	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, val);

Whilst complex, if it is only going to get one use, I'd just put the
complexity inline.  If it's getting lots of use in later patches then
fair enough having this macro.

> +
> +static void mem_assoc_to_regs(struct pci_bus_region *region,

>  /**
>   * pci_ide_stream_setup() - program settings to Selective IDE Stream registers

If I were being super fussy, I'd suggest doing the factor out to a structure
+ helper as a precursor patch then just add the new stuff here.
meh. I'm not that bothered but it would slightly simply review.

I'm not entirely convinced by the helper as a readability improvement
but don't hate it.


> +
>  	pos = sel_ide_offset(pdev, settings);

---

## [11] Jonathan Cameron — 2025-11-05
*Subject: Re: [PATCH 3/6] PCI/IDE: Initialize an ID for all IDE streams*

On Tue,  4 Nov 2025 20:00:52 -0800
Dan Williams <dan.j.williams@intel.com> wrote:

> The PCIe spec defines two types of streams - selective and link.  Each
> stream has an ID from the same bucket so a stream ID does not tell the

A small side discussion on whether a new type of cleanup helper makes
sense here for allocations that need to stash some data which is never
used except in __free. Bit of an odd corner case but could see something
similar for pool allocators (Which is kind of what we have here).

> ---
>  drivers/pci/pci.h       |   2 +

	return ret >= 0; perhaps


> +}
> +

	return ret >= 0;

> +}
> +

Good to have a comment on why we carry on anyway.

> +		return false;
> +	}
Likewise. Why is this not an error.
> +		return false;
> +	}
Related to above, I'm not sure why we just eat this problem with a print.

> +	}
> +


> @@ -301,6 +393,28 @@ void pci_ide_stream_release(struct pci_ide *ide)
>  }

Doesn't feel like an allocation function to me. Maybe a rename if
it doesn't gain some allocation abilities later?

> +{
> +	if (!reserve_stream_id(hb, stream_id))

Given the use of __sid as magic storage, I wonder if this can
be a CLASS with that storage wrapped up alongside a flag
we clear to make the destructor a no op. Similar to what happens for
spin_lock_irqsave where we stash flags etc via __DEFINE_UNLOCK_GUARD() 

Would need something a little more complex than current retain_and_null_ptr()
as it would need to set _T.ptr = NULL rather that _T = NULL.


> +	if (!sid) {
> +		pci_err(pdev, "Setup fail: Stream ID %d in use\n", ide->stream_id);

---

## [12] Jonathan Cameron — 2025-11-05
*Subject: Re: [PATCH 4/6] PCI/TSM: Add pci_tsm_bind() helper for
 instantiating TDIs*

On Tue,  4 Nov 2025 20:00:53 -0800
Dan Williams <dan.j.williams@intel.com> wrote:

> After a PCIe device has established a secure link and session between a TEE
> Security Manager (TSM) and its local Device Security Manager (DSM), the
Trivial comments only from me.

> diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
> index 6a2849f77adc..f0e38d7fee38 100644


> +/**
> + * pci_tsm_bind() - Bind @pdev as a TDI for @kvm
I'd flip so the error case is out of line. Then drop the else.


		if (pdev->tsm->tdi->kvm != kvm)
			return -EBUSY;

		return 0;

> +		else
> +			return -EBUSY;

---

## [13] Jonathan Cameron — 2025-11-05
*Subject: Re: [PATCH 5/6] PCI/TSM: Add pci_tsm_guest_req() for managing TDIs*

On Tue,  4 Nov 2025 20:00:54 -0800
Dan Williams <dan.j.williams@intel.com> wrote:

> A PCIe device function interface assigned to a TVM is a TEE Device
> Interface (TDI). A TDI instantiated by pci_tsm_bind() needs additional
More triviality inline.


> diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
> index f0e38d7fee38..4dd518b45eea 100644

> +ssize_t pci_tsm_guest_req(struct pci_dev *pdev, enum pci_tsm_req_scope scope,
> +			  sockptr_t req_in, size_t in_len, sockptr_t req_out,

	/* Forbid requests that are not directly related to TDISP operations */
Is just under 80 chars.


> +	 */

---

## [14] Jonathan Cameron — 2025-11-05
*Subject: Re: [PATCH 6/6] PCI/TSM: Add 'dsm' and 'bound' attributes for
 dependent functions*

On Tue,  4 Nov 2025 20:00:55 -0800
Dan Williams <dan.j.williams@intel.com> wrote:

> PCI/TSM sysfs for physical function 0 devices, i.e. the "DSM" (Device
> Security Manager), contains the 'connect' and 'disconnect' attributes.

Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

---

## [15] dan.j.williams@intel.com — 2025-11-05
*Subject: Re: [PATCH 4/6] PCI/TSM: Add pci_tsm_bind() helper for instantiating
 TDIs*

Aneesh Kumar K.V wrote:
[..]
> Can we set tdi in the constructor? I use it later as part of a bind()
> callback. I’d prefer not to pass tdi as an argument to those functions,

I think if you need this it would be ok to set tsm->tdi in your driver.
It is not the greatest fit for pci_tsm_tdi_constructor() because that
function really does not know if the tdi is fully formed and ready to
publish via tsm->tdi. It only knows that the common fields have been
initialized. See below...

[..]
> modified   drivers/pci/tsm.c
> @@ -391,8 +391,6 @@ int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u32 tdi_id)

I think it is ok to keep this even if the TSM driver already did it.

>  	return 0;
>  }

This ordering potentially causes something that walks tdi->pdev to fail,
and who knows if the TSM driver calls pci_tsm_tdi_constructor() before
or after TSM driver specific init. It all around feels like the TSM
driver is responsible for making the "early publish" decision, not this
constructor.

---

## [16] dan.j.williams@intel.com — 2025-11-05
*Subject: Re: [PATCH 1/6] resource: Introduce resource_assigned() for
 discerning active resources*

Jonathan Cameron wrote:
> On Tue,  4 Nov 2025 20:00:50 -0800
> Dan Williams <dan.j.williams@intel.com> wrote:

Hmm, ioport.h is not included in any "kernel-doc::" statements. I do not
think this tiny function that no drivers should be using needs that
formality. It is an internal implementation detail of resource
management, not really a kernel API.

---

## [17] dan.j.williams@intel.com — 2025-11-05
*Subject: Re: [PATCH 2/6] PCI/IDE: Add Address Association Register setup for
 downstream MMIO*

Jonathan Cameron wrote:
> On Tue,  4 Nov 2025 20:00:51 -0800
> Dan Williams <dan.j.williams@intel.com> wrote:

Maybe... I think I was more considering the fact that PCI compliant
devices always have a 32-bit MMIO range. Given both are optional it
might be better to detail that in the Description section:

diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
index 40f0be185120..37a1ad9501b0 100644
--- a/include/linux/pci-ide.h
+++ b/include/linux/pci-ide.h
@@ -29,13 +29,18 @@ enum pci_ide_partner_select {
  * @rid_end: Partner Port Requester ID range end
  * @stream_index: Selective IDE Stream Register Block selection
  * @mem_assoc: PCI bus memory address association for targeting peer partner
- * @pref_assoc: (optional) PCI bus prefetchable memory address association for
+ * @pref_assoc: PCI bus prefetchable memory address association for
  *		targeting peer partner
  * @default_stream: Endpoint uses this stream for all upstream TLPs regardless of
  *		    address and RID association registers
  * @setup: flag to track whether to run pci_ide_stream_teardown() for this
  *	   partner slot
  * @enable: flag whether to run pci_ide_stream_disable() for this partner slot
+ *
+ * By default, pci_ide_stream_alloc() initializes @mem_assoc and @pref_assoc
+ * with the immediate ancestor downstream port memory ranges (i.e. Type 1
+ * Configuration Space Header values). Caller may zero size ({0, -1}) the range
+ * to drop it from consideration at pci_ide_stream_setup() time.
  */
 struct pci_ide_partner {
 	u16 rid_start;

> 
> > + * @pref_assoc: (optional) PCI bus prefetchable memory address association for

Not sure if that buys much just to move this down a few lines into
mem_assoc_to_regs().

> > +static void mem_assoc_to_regs(struct pci_bus_region *region,
> > +			      struct pci_ide_regs *regs, int idx)

Note that the helper has an ulterior motive. TDX Connect wants to have a
copy of the desired register settings to pass to a TSM ABI for root port
setup. That will become clearer / documented later when this helper gets
an export.

---

## [18] dan.j.williams@intel.com — 2025-11-05
*Subject: Re: [PATCH 3/6] PCI/IDE: Initialize an ID for all IDE streams*

Jonathan Cameron wrote:
> On Tue,  4 Nov 2025 20:00:52 -0800
> Dan Williams <dan.j.williams@intel.com> wrote:

Sure.

> > +}
> > +

...but we do not carry on. When claim_stream() fails pci_ide_init()
fails. So this dev_info() is there to clue in an admin wondering why IDE
capabilities may not be available for some devices.

[..]
> > @@ -83,6 +129,7 @@ void pci_ide_init(struct pci_dev *pdev)
> >  		int pos = __sel_ide_offset(ide_cap, nr_link_ide, i, nr_ide_mem);

Explained above.

[..]
> > @@ -301,6 +393,28 @@ void pci_ide_stream_release(struct pci_ide *ide)
> >  }

No, it does not, rename sounds good.

diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index 33b3c54c62a1..60c22a6ee322 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -398,9 +394,9 @@ struct pci_ide_stream_id {
 	u8 stream_id;
 };
 
-static struct pci_ide_stream_id *alloc_stream_id(struct pci_host_bridge *hb,
-						 u8 stream_id,
-						 struct pci_ide_stream_id *sid)
+static struct pci_ide_stream_id *
+request_stream_id(struct pci_host_bridge *hb, u8 stream_id,
+		  struct pci_ide_stream_id *sid)
 {
 	if (!reserve_stream_id(hb, stream_id))
 		return NULL;
@@ -437,7 +433,7 @@ int pci_ide_stream_register(struct pci_ide *ide)
 	}
 
 	struct pci_ide_stream_id *sid __free(free_stream_id) =
-		alloc_stream_id(hb, ide->stream_id, &__sid);
+		request_stream_id(hb, ide->stream_id, &__sid);
 	if (!sid) {
 		pci_err(pdev, "Setup fail: Stream ID %d in use\n", ide->stream_id);
 		return -EBUSY;
> 
> > +{

Interesting. It is rare to have this kind of request model in core code.
Most of the "discover the platform published resource + request it"
happens in driver probe contexts and devm cleanup is available for that
(e.g.  devm_request_mem_region()). If we can find more users for such a
scope-based-cleanup model I would cheer on the person that wanted to
take that on.

Otherwise the "magic storage" approach is also taken with:

    struct stream_index __stream[PCI_IDE_HB + 1];
    ...
    alloc_stream_index(..., &__stream[...]);

---

## [19] dan.j.williams@intel.com — 2025-11-05
*Subject: Re: [PATCH 4/6] PCI/TSM: Add pci_tsm_bind() helper for instantiating
 TDIs*

Jonathan Cameron wrote:
> On Tue,  4 Nov 2025 20:00:53 -0800
> Dan Williams <dan.j.williams@intel.com> wrote:
[..]
> > +	/* Resolve races to bind a TDI */
> > +	if (pdev->tsm->tdi) {

Looks good.

diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index 7df2a681ed19..001afdf00de6 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -381,10 +381,9 @@ int pci_tsm_bind(struct pci_dev *pdev, struct kvm *kvm, u32 tdi_id)
 
 	/* Resolve races to bind a TDI */
 	if (pdev->tsm->tdi) {
-		if (pdev->tsm->tdi->kvm == kvm)
-			return 0;
-		else
+		if (pdev->tsm->tdi->kvm != kvm)
 			return -EBUSY;
+		return 0;
 	}
 
 	tdi = to_pci_tsm_ops(pdev->tsm)->bind(pdev, kvm, tdi_id);

---

## [20] dan.j.williams@intel.com — 2025-11-05
*Subject: Re: [PATCH 5/6] PCI/TSM: Add pci_tsm_guest_req() for managing TDIs*

Jonathan Cameron wrote:
> On Tue,  4 Nov 2025 20:00:54 -0800
> Dan Williams <dan.j.williams@intel.com> wrote:

Indeed it is. Probably a case of rewording but then not reflowing with
clang-format.

---

## [21] Jonathan Cameron — 2025-11-10
*Subject: Re: [PATCH 2/6] PCI/IDE: Add Address Association Register setup for
 downstream MMIO*

On Wed, 5 Nov 2025 15:04:05 -0800
dan.j.williams@intel.com wrote:

> Jonathan Cameron wrote:
> > On Tue,  4 Nov 2025 20:00:51 -0800
That does the job. Thanks,

>  struct pci_ide_partner {
>  	u16 rid_start;

---

## [22] Jonathan Cameron — 2025-11-10
*Subject: Re: [PATCH 3/6] PCI/IDE: Initialize an ID for all IDE streams*

> > > ---
> > >  drivers/pci/pci.h       |   2 +

> 
> > > +}

Ok. Failure isn't an error as such, but stuff just doesn't get set up.
Fair enough.


> > > +	if (!reserve_stream_id(hb, stream_id))
> > > +		return NULL;
Agreed. Potentially this is something for another day. 

Jonathan

---

## [23] Jonathan Cameron — 2025-11-13
*Subject: Re: [PATCH 6/6] PCI/TSM: Add 'dsm' and 'bound' attributes for
 dependent functions*

On Tue,  4 Nov 2025 20:00:55 -0800
Dan Williams <dan.j.williams@intel.com> wrote:

> PCI/TSM sysfs for physical function 0 devices, i.e. the "DSM" (Device
> Security Manager), contains the 'connect' and 'disconnect' attributes.
Repeat of tag from v1. It was only patch I tagged in that version
so no problem that you missed it, or forgot to say why you dropped
it intentionally.

Reviewed-by: Jonathan Cameron <jonathan.cameron@huawei.com>

---
