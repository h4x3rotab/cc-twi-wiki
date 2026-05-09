---
title: 'PCI/IDE: Fix using wrong VF ID for RID range calculation'
date: 2026-01-11
last_reply: 2026-01-13
message_count: 4
participants: ['Li Ming', 'Xu Yilun', 'Bjorn Helgaas']
---

## [1] Li Ming — 2026-01-11

When allocate a new IDE stream for a pci device in SR-IOV case, the RID
range of the new IDE stream should cover all VFs of the device. VF id
range of a pci device is [0 - (num_VFs - 1)], so should use (num_VFs - )
as the last VF's ID.

Fixes: 1e4d2ff3ae45 ("PCI/IDE: Add IDE establishment helpers")
Signed-off-by: Li Ming <ming.li@zohomail.com>
---
 drivers/pci/ide.c | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)

diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index 26f7cc94ec31..9629f3ceb213 100644
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

---

## [2] Xu Yilun — 2026-01-12
*Subject: Re: [PATCH 1/1] PCI/IDE: Fix using wrong VF ID for RID range
 calculation*

On Sun, Jan 11, 2026 at 04:06:31PM +0800, Li Ming wrote:
> When allocate a new IDE stream for a pci device in SR-IOV case, the RID
> range of the new IDE stream should cover all VFs of the device. VF id

I don't have VF for test but I believe the change is correct.

The calculated rid_end will be passed to IDE RID association register values,
which is inclusive according to IDE SPEC.

  void pci_ide_stream_to_regs(...)
  {
	...
	regs->rid1 = FIELD_PREP(PCI_IDE_SEL_RID_1_LIMIT, settings->rid_end);
	...
  }

Is it better we clarify the kernel-doc a little bit:

--------8<--------

diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
index 2521a2914294..f0c6975fd429 100644
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

## [3] Li Ming — 2026-01-13
*Subject: Re: [PATCH 1/1] PCI/IDE: Fix using wrong VF ID for RID range
 calculation*

在 2026/1/12 10:30, Xu Yilun 写道:
> On Sun, Jan 11, 2026 at 04:06:31PM +0800, Li Ming wrote:
>> When allocate a new IDE stream for a pci device in SR-IOV case, the RID

Sure, will do that in V2, thanks for review.


Ming

---

## [4] Bjorn Helgaas — 2026-01-13
*Subject: Re: [PATCH 1/1] PCI/IDE: Fix using wrong VF ID for RID range
 calculation*

On Sun, Jan 11, 2026 at 04:06:31PM +0800, Li Ming wrote:
> When allocate a new IDE stream for a pci device in SR-IOV case, the RID
> range of the new IDE stream should cover all VFs of the device. VF id

s/(num_VFs - )/(num_VFs - 1)/  (I think?)

s/pci/PCI/  (or could just omit, it's obvious these are PCI devices)
s/id/ID/

> Fixes: 1e4d2ff3ae45 ("PCI/IDE: Add IDE establishment helpers")
> Signed-off-by: Li Ming <ming.li@zohomail.com>

---
