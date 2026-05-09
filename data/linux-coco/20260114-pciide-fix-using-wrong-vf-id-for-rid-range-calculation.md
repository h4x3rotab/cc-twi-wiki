---
title: 'PCI/IDE: Fix using wrong VF ID for RID range calculation'
date: 2026-01-14
last_reply: 2026-01-22
message_count: 3
participants: ['Li Ming', 'Xu Yilun', 'dan.j.williams@intel.com']
---

## [1] Li Ming — 2026-01-14

When allocate a new IDE stream for a PCI device in SR-IOV case, the RID
range of the new IDE stream should cover all VFs of the device. VF ID
range of a PCI device is [0, num_VFs - 1], so should use (num_VFs - 1)
as the last VF's ID.

Fixes: 1e4d2ff3ae45 ("PCI/IDE: Add IDE establishment helpers")
Signed-off-by: Li Ming <ming.li@zohomail.com>
---
v2:
 * Make kernel-doc more detailed. (Yilun)
 * Fix typos in commit log. (Bjorn)
---
 drivers/pci/ide.c       | 4 ++--
 include/linux/pci-ide.h | 2 +-
 2 files changed, 3 insertions(+), 3 deletions(-)

diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index f0ef474e1a0d..799caa94ab94 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -283,8 +283,8 @@ struct pci_ide *pci_ide_stream_alloc(struct pci_dev *pdev)
 	/* for SR-IOV case, cover all VFs */
 	num_vf = pci_num_vf(pdev);
 	if (num_vf)
-		rid_end = PCI_DEVID(pci_iov_virtfn_bus(pdev, num_vf),
-				    pci_iov_virtfn_devfn(pdev, num_vf));
+		rid_end = PCI_DEVID(pci_iov_virtfn_bus(pdev, num_vf - 1),
+				    pci_iov_virtfn_devfn(pdev, num_vf - 1));
 	else
 		rid_end = pci_dev_id(pdev);
 
diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
index 37a1ad9501b0..381a1bf22a95 100644
--- a/include/linux/pci-ide.h
+++ b/include/linux/pci-ide.h
@@ -26,7 +26,7 @@ enum pci_ide_partner_select {
 /**
  * struct pci_ide_partner - Per port pair Selective IDE Stream settings
  * @rid_start: Partner Port Requester ID range start
- * @rid_end: Partner Port Requester ID range end
+ * @rid_end: Partner Port Requester ID range end (inclusive)
  * @stream_index: Selective IDE Stream Register Block selection
  * @mem_assoc: PCI bus memory address association for targeting peer partner
  * @pref_assoc: PCI bus prefetchable memory address association for

---

## [2] Xu Yilun — 2026-01-19
*Subject: Re: [PATCH v2 1/1] PCI/IDE: Fix using wrong VF ID for RID range
 calculation*

On Wed, Jan 14, 2026 at 07:14:55PM +0800, Li Ming wrote:
> When allocate a new IDE stream for a PCI device in SR-IOV case, the RID
> range of the new IDE stream should cover all VFs of the device. VF ID

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

---

## [3] dan.j.williams@intel.com — 2026-01-22
*Subject: Re: [PATCH v2 1/1] PCI/IDE: Fix using wrong VF ID for RID range
 calculation*

I will change this subject to "PCI/IDE: Fix off by one error calculating VF RID range"

Li Ming wrote:
> When allocate a new IDE stream for a PCI device in SR-IOV case, the RID
> range of the new IDE stream should cover all VFs of the device. VF ID

This can be even more succinct / to the point:

---
The VF ID range of an SR-IOV device is [0, num_VFs - 1].
pci_ide_stream_alloc() mistakenly uses num_VFs to represent the last ID.
Fix that off by one error to stay in bounds of the range.
---

...but otherwise this looks good to me. Thanks!

---
