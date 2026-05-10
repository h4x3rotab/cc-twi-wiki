---
title: 'Address Association Register setup for RP'
date: 2025-09-28
last_reply: 2025-10-06
message_count: 17
participants: ['Xu Yilun', 'Ilpo Järvinen', 'dan.j.williams@intel.com']
---

## [1] Xu Yilun — 2025-09-28

This patchset is for Address Association Register setup for RP. It is
based on devsec/tdx but the first 2 patches could be cleanly applied to
devsec/staging.

The last patch is not for apply. It takes TDX Connect as an example to
illustrate the usage of these newly introduced helpers.

ARM is expected to get benifit from this extra support in
pci_ide_stream_setup(). Intel TDX Connect should retrieve the address
range info from pci_ide.partner[PCI_IDE_RP].mem64 and use firmware call
for setup. AMD is expected to bypass the setup or does the setup but no
harm.


Xu Yilun (3):
  PCI/IDE: Add/export mini helpers for platform TSM drivers
  PCI/IDE: Add Address Association Register setup for RP
  coco/tdx-host: Illustrate IDE Address Association Register setup

 include/linux/pci-ide.h               | 17 +++++++
 drivers/pci/ide.c                     | 72 ++++++++++++++++++++++++---
 drivers/virt/coco/tdx-host/tdx-host.c | 33 ++----------
 3 files changed, 87 insertions(+), 35 deletions(-)

---

## [2] Xu Yilun — 2025-09-28
*Subject: [PATCH 1/3] PCI/IDE: Add/export mini helpers for platform TSM drivers*

These mini helpers are mainly for platform TSM drivers to setup root
port side configuration. Root port side IDE settings may require
platform specific firmware calls (e.g. TDX Connect [1]) so could not use
pci_ide_stream_setup(), but may still share these mini helpers cause
they also refer to definitions in IDE specification.

[1]: https://lore.kernel.org/linux-coco/20250919142237.418648-28-dan.j.williams@intel.com/

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 include/linux/pci-ide.h | 6 ++++++
 drivers/pci/ide.c       | 8 +++-----
 2 files changed, 9 insertions(+), 5 deletions(-)

diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
index a30f9460b04a..5adbd8b81f65 100644
--- a/include/linux/pci-ide.h
+++ b/include/linux/pci-ide.h
@@ -6,6 +6,11 @@
 #ifndef __PCI_IDE_H__
 #define __PCI_IDE_H__
 
+#define PREP_PCI_IDE_SEL_RID_2(base, domain)               \
+	(FIELD_PREP(PCI_IDE_SEL_RID_2_VALID, 1) |          \
+	 FIELD_PREP(PCI_IDE_SEL_RID_2_BASE, (base)) | \
+	 FIELD_PREP(PCI_IDE_SEL_RID_2_SEG, (domain)))
+
 enum pci_ide_partner_select {
 	PCI_IDE_EP,
 	PCI_IDE_RP,
@@ -61,6 +66,7 @@ struct pci_ide {
 	struct tsm_dev *tsm_dev;
 };
 
+int pci_ide_domain(struct pci_dev *pdev);
 struct pci_ide_partner *pci_ide_to_settings(struct pci_dev *pdev, struct pci_ide *ide);
 struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev);
 void pci_ide_stream_free(struct pci_ide *ide);
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index 10603f2d2319..7633b8e52399 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -345,12 +345,13 @@ void pci_ide_stream_unregister(struct pci_ide *ide)
 }
 EXPORT_SYMBOL_GPL(pci_ide_stream_unregister);
 
-static int pci_ide_domain(struct pci_dev *pdev)
+int pci_ide_domain(struct pci_dev *pdev)
 {
 	if (pdev->fm_enabled)
 		return pci_domain_nr(pdev->bus);
 	return 0;
 }
+EXPORT_SYMBOL_GPL(pci_ide_domain);
 
 struct pci_ide_partner *pci_ide_to_settings(struct pci_dev *pdev, struct pci_ide *ide)
 {
@@ -420,10 +421,7 @@ void pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide)
 	val = FIELD_PREP(PCI_IDE_SEL_RID_1_LIMIT, settings->rid_end);
 	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_1, val);
 
-	val = FIELD_PREP(PCI_IDE_SEL_RID_2_VALID, 1) |
-	      FIELD_PREP(PCI_IDE_SEL_RID_2_BASE, settings->rid_start) |
-	      FIELD_PREP(PCI_IDE_SEL_RID_2_SEG, pci_ide_domain(pdev));
-
+	val = PREP_PCI_IDE_SEL_RID_2(settings->rid_start, pci_ide_domain(pdev));
 	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_2, val);
 
 	/*

---

## [3] Xu Yilun — 2025-09-28
*Subject: [PATCH 2/3] PCI/IDE: Add Address Association Register setup for RP*

Add Address Association Register setup for Root Ports.

The address ranges for RP side Address Association Registers should
cover memory addresses for all PFs/VFs/downstream devices of the DSM
device. A simple solution is to get the aggregated 32-bit and 64-bit
address ranges from directly connected downstream port (either an RP or
a switch port) and set into 2 Address Association Register blocks.

There is a case the platform doesn't require Address Association
Registers setup and provides no register block for RP (AMD). Will skip
the setup in pci_ide_stream_setup().

Also imaging another case where there is only one block for RP.
Prioritize 64-bit address ranges setup for it. No strong reason for the
preference until a real use case comes.

The Address Association Register setup for Endpoint Side is still
uncertain so isn't supported in this patch.

Take the oppotunity to export some mini helpers for Address Association
Registers setup. TDX Connect needs the provided aggregated address
ranges but will use specific firmware calls for actual setup instead of
pci_ide_stream_setup().

Co-developed-by: Aneesh Kumar K.V <aneesh.kumar@kernel.org>
Signed-off-by: Aneesh Kumar K.V <aneesh.kumar@kernel.org>
Co-developed-by: Arto Merilainen <amerilainen@nvidia.com>
Signed-off-by: Arto Merilainen <amerilainen@nvidia.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 include/linux/pci-ide.h | 11 +++++++
 drivers/pci/ide.c       | 64 ++++++++++++++++++++++++++++++++++++++++-
 2 files changed, 74 insertions(+), 1 deletion(-)

diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
index 5adbd8b81f65..ac84fb611963 100644
--- a/include/linux/pci-ide.h
+++ b/include/linux/pci-ide.h
@@ -6,6 +6,15 @@
 #ifndef __PCI_IDE_H__
 #define __PCI_IDE_H__
 
+#define SEL_ADDR1_LOWER GENMASK(31, 20)
+#define SEL_ADDR_UPPER GENMASK_ULL(63, 32)
+#define PREP_PCI_IDE_SEL_ADDR1(base, limit)                    \
+	(FIELD_PREP(PCI_IDE_SEL_ADDR_1_VALID, 1) |             \
+	 FIELD_PREP(PCI_IDE_SEL_ADDR_1_BASE_LOW,          \
+		    FIELD_GET(SEL_ADDR1_LOWER, (base))) | \
+	 FIELD_PREP(PCI_IDE_SEL_ADDR_1_LIMIT_LOW,         \
+		    FIELD_GET(SEL_ADDR1_LOWER, (limit))))
+
 #define PREP_PCI_IDE_SEL_RID_2(base, domain)               \
 	(FIELD_PREP(PCI_IDE_SEL_RID_2_VALID, 1) |          \
 	 FIELD_PREP(PCI_IDE_SEL_RID_2_BASE, (base)) | \
@@ -42,6 +51,8 @@ struct pci_ide_partner {
 	unsigned int default_stream:1;
 	unsigned int setup:1;
 	unsigned int enable:1;
+	struct range mem32;
+	struct range mem64;
 };
 
 /**
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index 7633b8e52399..8db1163737e5 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -159,7 +159,11 @@ struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev)
 	struct stream_index __stream[PCI_IDE_HB + 1];
 	struct pci_host_bridge *hb;
 	struct pci_dev *rp;
+	struct pci_dev *br;
 	int num_vf, rid_end;
+	struct range mem32 = {}, mem64 = {};
+	struct pci_bus_region region;
+	struct resource *res;
 
 	if (!pci_is_pcie(pdev))
 		return NULL;
@@ -206,6 +210,24 @@ struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev)
 	else
 		rid_end = pci_dev_id(pdev);
 
+	br = pci_upstream_bridge(pdev);
+	if (!br)
+		return NULL;
+
+	res = &br->resource[PCI_BRIDGE_MEM_WINDOW];
+	if (res->flags & IORESOURCE_MEM) {
+		pcibios_resource_to_bus(br->bus, &region, res);
+		mem32.start = region.start;
+		mem32.end = region.end;
+	}
+
+	res = &br->resource[PCI_BRIDGE_PREF_MEM_WINDOW];
+	if (res->flags & IORESOURCE_PREFETCH) {
+		pcibios_resource_to_bus(br->bus, &region, res);
+		mem64.start = region.start;
+		mem64.end = region.end;
+	}
+
 	*ide = (struct pci_ide) {
 		.pdev = pdev,
 		.partner = {
@@ -218,6 +240,8 @@ struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev)
 				.rid_start = pci_dev_id(pdev),
 				.rid_end = rid_end,
 				.stream_index = no_free_ptr(rp_stream)->stream_index,
+				.mem32 = mem32,
+				.mem64 = mem64,
 			},
 		},
 		.host_bridge_stream = no_free_ptr(hb_stream)->stream_index,
@@ -397,6 +421,21 @@ static void set_ide_sel_ctl(struct pci_dev *pdev, struct pci_ide *ide,
 	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, val);
 }
 
+static void set_ide_sel_addr(struct pci_dev *pdev, int pos, int assoc_idx,
+			     struct range *mem)
+{
+	u32 val;
+
+	val = PREP_PCI_IDE_SEL_ADDR1(mem->start, mem->end);
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_1(assoc_idx), val);
+
+	val = FIELD_GET(SEL_ADDR_UPPER, mem->end);
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_2(assoc_idx), val);
+
+	val = FIELD_GET(SEL_ADDR_UPPER, mem->start);
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_3(assoc_idx), val);
+}
+
 /**
  * pci_ide_stream_setup() - program settings to Selective IDE Stream registers
  * @pdev: PCIe device object for either a Root Port or Endpoint Partner Port
@@ -410,6 +449,7 @@ static void set_ide_sel_ctl(struct pci_dev *pdev, struct pci_ide *ide,
 void pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide)
 {
 	struct pci_ide_partner *settings = pci_ide_to_settings(pdev, ide);
+	u8 assoc_idx = 0;
 	int pos;
 	u32 val;
 
@@ -424,6 +464,21 @@ void pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide)
 	val = PREP_PCI_IDE_SEL_RID_2(settings->rid_start, pci_ide_domain(pdev));
 	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_2, val);
 
+	/*
+	 * Feel free to change the default stratagy, Intel & AMD don't directly
+	 * setup RP registers.
+	 *
+	 * 64 bit memory first, assuming it's more popular.
+	 */
+	if (assoc_idx < pdev->nr_ide_mem && settings->mem64.end != 0) {
+		set_ide_sel_addr(pdev, pos, assoc_idx, &settings->mem64);
+		assoc_idx++;
+	}
+
+	/* 64 bit memory in lower block and 32 bit in higher block, any risk? */
+	if (assoc_idx < pdev->nr_ide_mem && settings->mem32.end != 0)
+		set_ide_sel_addr(pdev, pos, assoc_idx, &settings->mem32);
+
 	/*
 	 * Setup control register early for devices that expect
 	 * stream_id is set during key programming.
@@ -445,7 +500,7 @@ EXPORT_SYMBOL_GPL(pci_ide_stream_setup);
 void pci_ide_stream_teardown(struct pci_dev *pdev, struct pci_ide *ide)
 {
 	struct pci_ide_partner *settings = pci_ide_to_settings(pdev, ide);
-	int pos;
+	int pos, i;
 
 	if (!settings)
 		return;
@@ -453,6 +508,13 @@ void pci_ide_stream_teardown(struct pci_dev *pdev, struct pci_ide *ide)
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

## [4] Xu Yilun — 2025-09-28
*Subject: [PATCH 3/3] coco/tdx-host: Illustrate IDE Address Association Register setup*

Not for devsec-staging. Just illustrate, can't compile. Please wait for:

  [RFC PATCH v2 00/27] PCI/TSM: TDX Connect: SPDM Session and IDE Establishment

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/virt/coco/tdx-host/tdx-host.c | 33 ++++-----------------------
 1 file changed, 4 insertions(+), 29 deletions(-)

diff --git a/drivers/virt/coco/tdx-host/tdx-host.c b/drivers/virt/coco/tdx-host/tdx-host.c
index 5553c63b4083..58777225b51e 100644
--- a/drivers/virt/coco/tdx-host/tdx-host.c
+++ b/drivers/virt/coco/tdx-host/tdx-host.c
@@ -387,29 +387,6 @@ static void tdx_ide_stream_key_stop(struct tdx_link *tlink)
 
 DEFINE_FREE(tdx_ide_stream_key_stop, struct tdx_link *, if (!IS_ERR_OR_NULL(_T)) tdx_ide_stream_key_stop(_T))
 
-/* OPEN: Should we add general address range support in pci/ide.c ? */
-static void setup_addr_range(struct pci_dev *pdev,
-			     resource_size_t *start, resource_size_t *end)
-{
-	struct device *dev;
-	u32 devid;
-	int i;
-
-	add_pdev_to_addr_range(pdev, start, end);
-
-	for (i = 0; i < pci_num_vf(pdev); i++) {
-		devid = PCI_DEVID(pci_iov_virtfn_bus(pdev, i),
-				  pci_iov_virtfn_devfn(pdev, i));
-
-		dev = bus_find_device(&pci_bus_type, NULL, &devid,
-				      match_pci_dev_by_devid);
-		if (dev) {
-			add_pdev_to_addr_range(to_pci_dev(dev), start, end);
-			put_device(dev);
-		}
-	}
-}
-
 static void sel_stream_block_setup(struct pci_dev *pdev, struct pci_ide *ide,
 				   u64 *rid_assoc1, u64 *rid_assoc2,
 				   u64 *addr_assoc1, u64 *addr_assoc2,
@@ -422,12 +399,10 @@ static void sel_stream_block_setup(struct pci_dev *pdev, struct pci_ide *ide,
 	*rid_assoc1 = FIELD_PREP(PCI_IDE_SEL_RID_1_LIMIT, setting->rid_end);
 	*rid_assoc2 = PREP_PCI_IDE_SEL_RID_2(setting->rid_start, pci_ide_domain(pdev));
 
-	/* Only one address association register block */
-	setup_addr_range(pdev, &start, &end);
-
-	*addr_assoc1 = PREP_PCI_IDE_SEL_ADDR1(start, end);
-	*addr_assoc2 = FIELD_GET(SEL_ADDR_UPPER, end);
-	*addr_assoc3 = FIELD_GET(SEL_ADDR_UPPER, start);
+	/* TDX Module enforces only one address association register block */
+	*addr_assoc1 = PREP_PCI_IDE_SEL_ADDR1(setting->mem64.start, setting->mem64.end);
+	*addr_assoc2 = FIELD_GET(SEL_ADDR_UPPER, setting->mem64.end);
+	*addr_assoc3 = FIELD_GET(SEL_ADDR_UPPER, setting->mem64.start);
 }
 
 #define STREAM_INFO_RP_DEVFN		GENMASK_ULL(7, 0)

---

## [5] Ilpo Järvinen — 2025-09-30
*Subject: Re: [PATCH 2/3] PCI/IDE: Add Address Association Register setup for
 RP*

On Sun, 28 Sep 2025, Xu Yilun wrote:

> Add Address Association Register setup for Root Ports.
> 

Why not join with the previous line?

>  	int num_vf, rid_end;
> +	struct range mem32 = {}, mem64 = {};

pci_resource_n()

> +	if (res->flags & IORESOURCE_MEM) {
> +		pcibios_resource_to_bus(br->bus, &region, res);

Ditto.

> +	if (res->flags & IORESOURCE_PREFETCH) {

While I don't know much about what's going on here, is this assuming the 
bridge window is not disabled solely based on this flag check?

Previously inactive bridge window flags were reset but that's no longer 
the case after the commit 8278c6914306 ("PCI: Preserve bridge window 
resource type flags") (currently in pci/resource)?

---

## [6] dan.j.williams@intel.com — 2025-09-30
*Subject: Re: [PATCH 1/3] PCI/IDE: Add/export mini helpers for platform TSM
 drivers*

Xu Yilun wrote:
> These mini helpers are mainly for platform TSM drivers to setup root
> port side configuration. Root port side IDE settings may require

So I do not think we need to export these as much as let TSM drivers
reuse more of the common register setup logic.

I will flesh out more of the proposal on the next patch.

---

## [7] dan.j.williams@intel.com — 2025-09-30
*Subject: Re: [PATCH 2/3] PCI/IDE: Add Address Association Register setup for
 RP*

Ilpo Järvinen wrote:
> On Sun, 28 Sep 2025, Xu Yilun wrote:
> 

Indeed it does seem to be assumining that the flag is only set when the
resource is valid and active.

> Previously inactive bridge window flags were reset but that's no longer 
> the case after the commit 8278c6914306 ("PCI: Preserve bridge window 

Thanks for the heads up. It does seem odd that both IORESOURCE_UNSET and
IORESOURCE_DISABLED are both being set and the check allows for either.
Is that assuming that other call paths not touched in that set may only
set one of those flags?

Otherwise, the change to mark the resource as zero-sized feels a better
/ more explicit protocol than checking for flags. IDE setup only cares
that any downstream MMIO get included in the stream.

---

## [8] Ilpo Järvinen — 2025-10-01
*Subject: Re: [PATCH 2/3] PCI/IDE: Add Address Association Register setup for
 RP*

On Tue, 30 Sep 2025, dan.j.williams@intel.com wrote:
> Ilpo J�rvinen wrote:
> > On Sun, 28 Sep 2025, Xu Yilun wrote:

I'm a bit lost on what check you're referring to.

If you refer to the check in pci_bus_alloc_from_region() added by that 
commit, now that I relook at it, it would probably be better written as 
!r->parent (a TODO entry added to verify it).

> Is that assuming that other call paths not touched in that set may only
> set one of those flags?

Presence of either of those flags indicates the bridge window resource is 
not usable "normally". There's also res->parent which directly tells if 
the resource is assigned. Out of those three, res->parent is the preferred 
way to know if the resource is usable normally (aka. "assigned"), however, 
res->parent check can only be used if this code runs late enough.

To me IORESOURCE_UNSET looks unnecessary flag and would want to get rid of 
it entirely as res->parent mostly tells the same information. But I don't 
expect that to be an easy change, and there's also the init transient 
where res->parent is not yet set which complicates things.

But until IORESOURCE_UNSET is gone, it alone can indicate the resource is 
not in usable state. And so can IORESOURCE_DISABLED.

The resource fitting code clears DISABLED (while sizing bridge windows) 
before UNSET (on assignment), so they have different meaning even if 
there's overlap on the consumer side depending on use case. The resource 
fitting/assignment code cares for this distinction, see e.g. 
pdev_resource_assignable() which only checks for DISABLED because, well, 
we're about to attempt to turn UNSET into !UNSET.

> Otherwise, the change to mark the resource as zero-sized feels a better
> / more explicit protocol than checking for flags. IDE setup only cares

If this particular code here runs after resources have been assigned by 
the kernel, please check res->parent to know if the resource is assigned 
or not.

I'm considering adding resource_assigned() helper for this purpose as 
res->parent check looks too odd and may alienate developers from using it 
if they don't know about the internals of the resource management.

If the bridge window resource is assigned, it should have the expected 
flags and IMO it's useless to check for the flags (if flags are not right 
for the bridge window resources that is assigned, we've a bug elsewhere in 
the code).


As a sidenote, there are lots of !res->flags and !pci_resource_len(...), 
etc. checks which are often custom implementations resource_assigned(), 
they all are landmines that make my life harder as I'd want to make 
further improvements to resource behavior.

---

## [9] dan.j.williams@intel.com — 2025-10-01
*Subject: Re: [PATCH 2/3] PCI/IDE: Add Address Association Register setup for
 RP*

Ilpo Järvinen wrote:
> On Tue, 30 Sep 2025, dan.j.williams@intel.com wrote:
> > Ilpo Järvinen wrote:

Thanks for the details!

> > Otherwise, the change to mark the resource as zero-sized feels a better
> > / more explicit protocol than checking for flags. IDE setup only cares

A resource_assigned() helper sounds good to me. I will fold that into
this patch for now, but feel free to pull that out and merge separately
if you need it in other places.

---

## [10] dan.j.williams@intel.com — 2025-10-01
*Subject: Re: [PATCH 2/3] PCI/IDE: Add Address Association Register setup for
 RP*

[ Add Ilpo for resource_assigned() usage proposal below ]

Xu Yilun wrote:
> Add Address Association Register setup for Root Ports.

Perhaps it would be more accurate to call this "Address Association for
downstream MMIO" to clearly distinguish it from memory cycles targetting
the root port.

> The address ranges for RP side Address Association Registers should
> cover memory addresses for all PFs/VFs/downstream devices of the DSM

For the bridge the split is not 32-bit vs 64-bit. The split is
non-prefetchable vs prefetchable where the latter is potentially 64-bit,
but not always.

> There is a case the platform doesn't require Address Association
> Registers setup and provides no register block for RP (AMD). Will skip

Instead of calling out architecture specific details this can say

"Just like RID association, address associations will be set by default
if hardware sets 'Number of Address Association Register Blocks' in the
'Selective IDE Stream Capability Register' to a non-zero value.
Alternatively, TSM drivers can opt-out of the settings by zero'ing out
the probed region."

> Also imaging another case where there is only one block for RP.
> Prioritize 64-bit address ranges setup for it. No strong reason for the

Rather than invent a new a policy just follow the PCI bridge
specification precedent where memory is mandatory and
prefetchable-memory is optional. If a bridge maps both, check if the
device needs both. If the device needs both and the platform only
provides 1 address association block then setup the non-optional BAR
first. If that results in an incomplete solution that is a quirk that
the vendor needs to solve, not the core PCI implementation.

Specifically, if that happens, the solution might be either a quirk to
disable address associations, or a quirk to disable one of the ranges.
Which path to take is unknown until there is a practical problem to
solve.

> The Address Association Register setup for Endpoint Side is still
> uncertain so isn't supported in this patch.

Per-above these should be mem_assoc, and pref_assoc;

> +	struct pci_bus_region region;
> +	struct resource *res;

Per Ilpo this can now just be a size check.

> +		pcibios_resource_to_bus(br->bus, &region, res);
> +		mem32.start = region.start;

Per-above, just drop the 64-bit policy and assumption. It will naturally
fail if the required number of address associations is insufficient.
I.e. either we are in the AMD situation and no amount of address
association is required, or we are in the ARM / Intel situation where it
assigns memory then prefetch-memory (if both are present). If both of
those are required and the hardware only supports 1 address association
then that hardware vendor is responsible for figuring out a quirk.

Otherwise Linux expects that any hardware that requires address
association always produces at least 2 address association blocks at the
root port, or otherwise arranges for only one memory window type to be
active.

>  	/*
>  	 * Setup control register early for devices that expect

Hmm, if we are going to clear all on stop then probably should also
clear all unused on setup just to be consistent.

> +
>  	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_2, 0);

Here are the proposed incremental changes addressing the above. The new
pci_ide_stream_to_regs() helper can later be exported to TSM drivers
that need a formatted copy of the register settings. I prefer that to
exporting the internals (the PREP_() macros for register setup and the
pci_ide_domain()).

-- >8 --
diff --git a/include/linux/ioport.h b/include/linux/ioport.h
index b46e42bcafe3..e7c14ce1b1d0 100644
--- a/include/linux/ioport.h
+++ b/include/linux/ioport.h
@@ -336,6 +336,12 @@ static inline bool resource_union(const struct resource *r1, const struct resour
 	return true;
 }
 
+/* Check if this resource is added to a resource tree or detached. */
+static inline bool resource_assigned(struct resource *res)
+{
+	return res->parent != NULL;
+}
+
 int find_resource_space(struct resource *root, struct resource *new,
 			resource_size_t size, struct resource_constraint *constraint);
 
diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
index ad4fcde75a56..4e33fa6944a1 100644
--- a/include/linux/pci-ide.h
+++ b/include/linux/pci-ide.h
@@ -28,6 +28,9 @@ enum pci_ide_partner_select {
  * @rid_start: Partner Port Requester ID range start
  * @rid_end: Partner Port Requester ID range end
  * @stream_index: Selective IDE Stream Register Block selection
+ * @mem_assoc: PCI bus memory address association for targetting peer partner
+ * @pref_assoc: (optional) PCI bus prefetchable memory address association for
+ *		targetting peer partner
  * @default_stream: Endpoint uses this stream for all upstream TLPs regardless of
  *		    address and RID association registers
  * @setup: flag to track whether to run pci_ide_stream_teardown() for this
@@ -38,11 +41,33 @@ struct pci_ide_partner {
 	u16 rid_start;
 	u16 rid_end;
 	u8 stream_index;
+	struct pci_bus_region mem_assoc;
+	struct pci_bus_region pref_assoc;
 	unsigned int default_stream:1;
 	unsigned int setup:1;
 	unsigned int enable:1;
-	struct range mem32;
-	struct range mem64;
+};
+
+/**
+ * struct pci_ide_regs - Hardware register association settings for Selective
+ *			 IDE Streams
+ * @rid_1: IDE RID Association Register 1
+ * @rid_2: IDE RID Association Register 2
+ * @addr: Up to two address association blocks (IDE Address Association Register
+ *	  1 through 3) for MMIO and prefetchable MMIO
+ * @nr_addr: Number of address association blocks initialized
+ *
+ * See pci_ide_stream_to_regs()
+ */
+struct pci_ide_regs {
+	u32 rid_1;
+	u32 rid_2;
+	struct {
+		u32 assoc1;
+		u32 assoc2;
+		u32 assoc3;
+	} addr[2];
+	int nr_addr;
 };
 
 /**
diff --git a/include/linux/pci.h b/include/linux/pci.h
index 3a71f30211a5..ca97590de116 100644
--- a/include/linux/pci.h
+++ b/include/linux/pci.h
@@ -877,6 +877,11 @@ struct pci_bus_region {
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
index 7b2aa0b30376..8e30b75f1f4d 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -157,13 +157,13 @@ struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev)
 {
 	/* EP, RP, + HB Stream allocation */
 	struct stream_index __stream[PCI_IDE_HB + 1];
+	struct pci_bus_region pref_assoc = { 0, -1 };
+	struct pci_bus_region mem_assoc = { 0, -1 };
+	struct resource *res, *mem, *pref;
 	struct pci_host_bridge *hb;
+	int num_vf, rid_end;
 	struct pci_dev *rp;
 	struct pci_dev *br;
-	int num_vf, rid_end;
-	struct range mem32 = {}, mem64 = {};
-	struct pci_bus_region region;
-	struct resource *res;
 
 	if (!pci_is_pcie(pdev))
 		return NULL;
@@ -214,18 +214,20 @@ struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev)
 	if (!br)
 		return NULL;
 
-	res = &br->resource[PCI_BRIDGE_MEM_WINDOW];
-	if (res->flags & IORESOURCE_MEM) {
-		pcibios_resource_to_bus(br->bus, &region, res);
-		mem32.start = region.start;
-		mem32.end = region.end;
-	}
-
-	res = &br->resource[PCI_BRIDGE_PREF_MEM_WINDOW];
-	if (res->flags & IORESOURCE_PREFETCH) {
-		pcibios_resource_to_bus(br->bus, &region, res);
-		mem64.start = region.start;
-		mem64.end = region.end;
+	/*
+	 * Check if the device consumes memory and/or prefetch-memory. Setup
+	 * downstream address association ranges for each.
+	 */
+	mem = pci_resource_n(br, PCI_BRIDGE_MEM_WINDOW);
+	pref = pci_resource_n(br, PCI_BRIDGE_PREF_MEM_WINDOW);
+	pci_dev_for_each_resource(pdev, res) {
+		if (resource_assigned(mem) && resource_contains(mem, res) &&
+		    !pci_bus_region_size(&mem_assoc))
+			pcibios_resource_to_bus(br->bus, &mem_assoc, mem);
+
+		if (resource_assigned(pref) && resource_contains(pref, res) &&
+		    !pci_bus_region_size(&pref_assoc))
+			pcibios_resource_to_bus(br->bus, &pref_assoc, pref);
 	}
 
 	*ide = (struct pci_ide) {
@@ -235,13 +237,16 @@ struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev)
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
-				.mem32 = mem32,
-				.mem64 = mem64,
+				.mem_assoc = mem_assoc,
+				.pref_assoc = pref_assoc,
 			},
 		},
 		.host_bridge_stream = no_free_ptr(hb_stream)->stream_index,
@@ -420,19 +425,61 @@ static void set_ide_sel_ctl(struct pci_dev *pdev, struct pci_ide *ide,
 	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_CTL, val);
 }
 
-static void set_ide_sel_addr(struct pci_dev *pdev, int pos, int assoc_idx,
-			     struct range *mem)
+#define SEL_ADDR1_LOWER GENMASK(31, 20)
+#define SEL_ADDR_UPPER GENMASK_ULL(63, 32)
+#define PREP_PCI_IDE_SEL_ADDR1(base, limit)               \
+	(FIELD_PREP(PCI_IDE_SEL_ADDR_1_VALID, 1) |        \
+	 FIELD_PREP(PCI_IDE_SEL_ADDR_1_BASE_LOW,          \
+		    FIELD_GET(SEL_ADDR1_LOWER, (base))) | \
+	 FIELD_PREP(PCI_IDE_SEL_ADDR_1_LIMIT_LOW,         \
+		    FIELD_GET(SEL_ADDR1_LOWER, (limit))))
+
+static void mem_assoc_to_regs(struct pci_bus_region *region,
+			      struct pci_ide_regs *regs, int idx)
 {
-	u32 val;
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
+	int pos, assoc_idx = 0;
+
+	memset(regs, 0, sizeof(*regs));
+
+	if (!settings)
+		return;
 
-	val = PREP_PCI_IDE_SEL_ADDR1(mem->start, mem->end);
-	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_1(assoc_idx), val);
+	pos = sel_ide_offset(pdev, settings);
+
+	regs->rid_1 = FIELD_PREP(PCI_IDE_SEL_RID_1_LIMIT, settings->rid_end);
+
+	regs->rid_2 = FIELD_PREP(PCI_IDE_SEL_RID_2_VALID, 1) |
+		      FIELD_PREP(PCI_IDE_SEL_RID_2_BASE, settings->rid_start) |
+		      FIELD_PREP(PCI_IDE_SEL_RID_2_SEG, pci_ide_domain(pdev));
+
+	if (pdev->nr_ide_mem && pci_bus_region_size(&settings->mem_assoc)) {
+		mem_assoc_to_regs(&settings->mem_assoc, regs, assoc_idx);
+		assoc_idx++;
+	}
 
-	val = FIELD_GET(SEL_ADDR_UPPER, mem->end);
-	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_2(assoc_idx), val);
+	if (pdev->nr_ide_mem > assoc_idx &&
+	    pci_bus_region_size(&settings->pref_assoc)) {
+		mem_assoc_to_regs(&settings->pref_assoc, regs, assoc_idx);
+		assoc_idx++;
+	}
 
-	val = FIELD_GET(SEL_ADDR_UPPER, mem->start);
-	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_3(assoc_idx), val);
+	regs->nr_addr = assoc_idx;
 }
 
 /**
@@ -448,38 +495,34 @@ static void set_ide_sel_addr(struct pci_dev *pdev, int pos, int assoc_idx,
 void pci_ide_stream_setup(struct pci_dev *pdev, struct pci_ide *ide)
 {
 	struct pci_ide_partner *settings = pci_ide_to_settings(pdev, ide);
-	u8 assoc_idx = 0;
+	struct pci_ide_regs regs;
 	int pos;
-	u32 val;
 
 	if (!settings)
 		return;
 
-	pos = sel_ide_offset(pdev, settings);
+	pci_ide_stream_to_regs(pdev, ide, &regs);
 
-	val = FIELD_PREP(PCI_IDE_SEL_RID_1_LIMIT, settings->rid_end);
-	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_1, val);
-
-	val = FIELD_PREP(PCI_IDE_SEL_RID_2_VALID, 1) |
-	      FIELD_PREP(PCI_IDE_SEL_RID_2_BASE, settings->rid_start) |
-	      FIELD_PREP(PCI_IDE_SEL_RID_2_SEG, pci_ide_domain(pdev));
+	pos = sel_ide_offset(pdev, settings);
 
-	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_2, val);
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_1, regs.rid_1);
+	pci_write_config_dword(pdev, pos + PCI_IDE_SEL_RID_2, regs.rid_2);
 
-	/*
-	 * Feel free to change the default stratagy, Intel & AMD don't directly
-	 * setup RP registers.
-	 *
-	 * 64 bit memory first, assuming it's more popular.
-	 */
-	if (assoc_idx < pdev->nr_ide_mem && settings->mem64.end != 0) {
-		set_ide_sel_addr(pdev, pos, assoc_idx, &settings->mem64);
-		assoc_idx++;
+	for (int i = 0; i < regs.nr_addr; i++) {
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_1(i),
+				       regs.addr[i].assoc1);
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_2(i),
+				       regs.addr[i].assoc2);
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_3(i),
+				       regs.addr[i].assoc3);
 	}
 
-	/* 64 bit memory in lower block and 32 bit in higher block, any risk? */
-	if (assoc_idx < pdev->nr_ide_mem && settings->mem32.end != 0)
-		set_ide_sel_addr(pdev, pos, assoc_idx, &settings->mem32);
+	/* clear extra unused address association blocks */
+	for (int i = regs.nr_addr; i < pdev->nr_ide_mem; i++) {
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_1(i), 0);
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_2(i), 0);
+		pci_write_config_dword(pdev, pos + PCI_IDE_SEL_ADDR_3(i), 0);
+	}
 
 	/*
 	 * Setup control register early for devices that expect

---

## [11] Ilpo Järvinen — 2025-10-02
*Subject: Re: [PATCH 2/3] PCI/IDE: Add Address Association Register setup for
 RP*

On Wed, 1 Oct 2025, dan.j.williams@intel.com wrote:

> [ Add Ilpo for resource_assigned() usage proposal below ]
> 

I don't know why you said this about size as you implemented it below 
correctly using res->parent check (inside resource_assigned()).

> > +		pcibios_resource_to_bus(br->bus, &region, res);
> > +		mem32.start = region.start;

---

## [12] dan.j.williams@intel.com — 2025-10-02
*Subject: Re: [PATCH 2/3] PCI/IDE: Add Address Association Register setup for
 RP*

Ilpo Järvinen wrote:
[..]
> > > @@ -206,6 +210,24 @@ struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev)
> > >  	else

Oh, stale comment. I wrote this, then read your suggestion about
resource_assigned(), updated the proposed patch, but failed to come back
and adjust this stale comment.

Sorry for the confusion.

---

## [13] Xu Yilun — 2025-10-03
*Subject: Re: [PATCH 1/3] PCI/IDE: Add/export mini helpers for platform TSM
 drivers*

On Tue, Sep 30, 2025 at 05:24:06PM -0700, dan.j.williams@intel.com wrote:
> Xu Yilun wrote:
> > These mini helpers are mainly for platform TSM drivers to setup root

Do you mean PCI IDE should provide the collapsed raw RID/Address
Association Register values for platform TSM drivers? TDX needs these
raw values for SEAMCALLs.

> 
> I will flesh out more of the proposal on the next patch.

---

## [14] dan.j.williams@intel.com — 2025-10-02
*Subject: Re: [PATCH 1/3] PCI/IDE: Add/export mini helpers for platform TSM
 drivers*

Xu Yilun wrote:
[..]
> Do you mean PCI IDE should provide the collapsed raw RID/Address
> Association Register values for platform TSM drivers? TDX needs these

Right, see pci_ide_stream_to_regs() [1] as the proposal for TSM drivers that
want to share the same register value setup code as the PCI/TSM core.

[1]: http://lore.kernel.org/68dd8d20aafb4_1fa2100f0@dwillia2-mobl4.notmuch

---

## [15] Xu Yilun — 2025-10-03
*Subject: Re: [PATCH 2/3] PCI/IDE: Add Address Association Register setup for
 RP*

> Per-above, just drop the 64-bit policy and assumption. It will naturally
> fail if the required number of address associations is insufficient.

Intel can't assign both memory now.

In my patch, the new policy only applies to pci_ide_stream_setup(rp)
which TDX won't use. pci_ide_stream_alloc() just listed the 2 memory
ranges regardless the actuall number of address association blocks.
That's why I said TDX is not the user of the new policy.

> those are required and the hardware only supports 1 address association
> then that hardware vendor is responsible for figuring out a quirk.

But if we want the address association register setting all controlled by
PCI IDE core, TDX is the practical problem and needs a quirk. I see there
is only 1 address association block for RP in my test ENV, and the test
device requires perf memory to be IDE protected and later private
assigned.

> Otherwise Linux expects that any hardware that requires address
> association always produces at least 2 address association blocks at the

I get the answer to my question in Patch #1.

[...]

> @@ -157,13 +157,13 @@ struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev)
>  {

We still need to cover all sub-functions of the dsm device, only
check the need of the dsm device is not enough. But if we check all
functions, we don't have to check then.

[...]

> +/**
> + * pci_ide_stream_to_regs() - convert IDE settings to association register values

I image the quirk for TDX is, reset the RP side settings->mem_assoc back
to {0, -1} before calling this function.
 

> +		mem_assoc_to_regs(&settings->mem_assoc, regs, assoc_idx);
> +		assoc_idx++;

---

## [16] dan.j.williams@intel.com — 2025-10-03
*Subject: Re: [PATCH 2/3] PCI/IDE: Add Address Association Register setup for
 RP*

Xu Yilun wrote:
> > Per-above, just drop the 64-bit policy and assumption. It will naturally
> > fail if the required number of address associations is insufficient.

The address association setting is not *controlled* by the PCI IDE core,
it is simply *initialized* by the PCI IDE core. The PCI IDE core should
always be a library, not a mid-layer when it comes to policy. So, if TDX
knows that only prefetchable memory will ever be protected then it can
do the following:

        struct pci_ide *ide __free(pci_ide_stream_release) =
                pci_ide_stream_alloc(pdev);
        if (!ide)
                return -ENOMEM;
	...
        rp_settings = pci_ide_to_settings(rp, ide);
        /* only support address association for prefetchable memory */
        rp_settings->mem_assoc = { 0, -1 };

[..]
> > +	/*
> > +	 * Check if the device consumes memory and/or prefetch-memory. Setup

True, good point, no real need to limit the stream just based on the DSM
device just do:

        if (resource_assigned(mem))
                pcibios_resource_to_bus(br->bus, &mem_assoc, mem);
        if (resource_assigned(pref))
                pcibios_resource_to_bus(br->bus, &pref_assoc, pref);

I was hoping that limiting it to the bridge windows that are used might
naturally result in the non-prefetchable memory window dropping out.
However, better to associate all downstream memory by default and let
the TSM driver trim associations it does not want to support.

[..]
> > + * pci_ide_stream_to_regs() - convert IDE settings to association register values
> > + * @pdev: PCIe device object for either a Root Port or Endpoint Partner Port

Oh, yup, you predicted my response above.

Now, I worry that some device will need its memory window protected in
addition to its prefetch window, but that is an architecture limitation
that the TDX Module will need to solve when / if it happens.

---

## [17] Xu Yilun — 2025-10-06
*Subject: Re: [PATCH 2/3] PCI/IDE: Add Address Association Register setup for
 RP*

> The address association setting is not *controlled* by the PCI IDE core,
> it is simply *initialized* by the PCI IDE core. The PCI IDE core should

Yeah, good to me.

> 
> [..]

Delete the pos stuff, not used in this function.

> > > +
> > > +	regs->rid_1 = FIELD_PREP(PCI_IDE_SEL_RID_1_LIMIT, settings->rid_end);

Agree.

I've tested all your changes, work for me.

Thanks,
Yilun

---
