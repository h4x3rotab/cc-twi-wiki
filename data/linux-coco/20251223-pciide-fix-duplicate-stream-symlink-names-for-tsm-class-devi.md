---
title: 'PCI/IDE: Fix duplicate stream symlink names for TSM class devices'
date: 2025-12-23
last_reply: 2025-12-24
message_count: 3
participants: ['Xu Yilun', 'Bjorn Helgaas']
---

## [1] Xu Yilun — 2025-12-23

The symlink name streamH.R.E is unique within a specific host bridge but
not across the system. Error occurs e.g. when creating the first stream
on a second host bridge:

[ 1244.034755] sysfs: cannot create duplicate filename '/devices/faux/tdx_host/tsm/tsm0/stream0.0.0'

Fix this by adding host bridge name into symlink name for TSM class
devices. It should be OK to change the uAPI to
/sys/class/tsm/tsmN/pciDDDD:BB:streamH.R.E since it's new and has few
users.

Internally in the IDE library, store the full name in struct pci_ide
so TSM symlinks can use it directly, while PCI host bridge symlinks
can skip the host bridge name to keep concise.

Fixes: a4438f06b1db ("PCI/TSM: Report active IDE streams")
Reported-by: Yi Lai <yi1.lai@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 Documentation/ABI/testing/sysfs-class-tsm |  2 +-
 drivers/pci/ide.c                         | 12 +++++++++---
 2 files changed, 10 insertions(+), 4 deletions(-)

diff --git a/Documentation/ABI/testing/sysfs-class-tsm b/Documentation/ABI/testing/sysfs-class-tsm
index 6fc1a5ac6da1..eff71e42c60e 100644
--- a/Documentation/ABI/testing/sysfs-class-tsm
+++ b/Documentation/ABI/testing/sysfs-class-tsm
@@ -8,7 +8,7 @@ Description:
 		link encryption and other device-security features coordinated
 		through a platform tsm.
 
-What:		/sys/class/tsm/tsmN/streamH.R.E
+What:		/sys/class/tsm/tsmN/pciDDDD:BB:streamH.R.E
 Contact:	linux-pci@vger.kernel.org
 Description:
 		(RO) When a host bridge has established a secure connection via
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index f0ef474e1a0d..db1c7423bf39 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -425,6 +425,7 @@ int pci_ide_stream_register(struct pci_ide *ide)
 	struct pci_host_bridge *hb = pci_find_host_bridge(pdev->bus);
 	struct pci_ide_stream_id __sid;
 	u8 ep_stream, rp_stream;
+	const char *short_name;
 	int rc;
 
 	if (ide->stream_id < 0 || ide->stream_id > U8_MAX) {
@@ -441,13 +442,16 @@ int pci_ide_stream_register(struct pci_ide *ide)
 
 	ep_stream = ide->partner[PCI_IDE_EP].stream_index;
 	rp_stream = ide->partner[PCI_IDE_RP].stream_index;
-	const char *name __free(kfree) = kasprintf(GFP_KERNEL, "stream%d.%d.%d",
+	const char *name __free(kfree) = kasprintf(GFP_KERNEL, "%s:stream%d.%d.%d",
+						   dev_name(&hb->dev),
 						   ide->host_bridge_stream,
 						   rp_stream, ep_stream);
 	if (!name)
 		return -ENOMEM;
 
-	rc = sysfs_create_link(&hb->dev.kobj, &pdev->dev.kobj, name);
+	/* Skip host bridge name in the host bridge context */
+	short_name = name + strlen(dev_name(&hb->dev)) + 1;
+	rc = sysfs_create_link(&hb->dev.kobj, &pdev->dev.kobj, short_name);
 	if (rc)
 		return rc;
 
@@ -471,8 +475,10 @@ void pci_ide_stream_unregister(struct pci_ide *ide)
 {
 	struct pci_dev *pdev = ide->pdev;
 	struct pci_host_bridge *hb = pci_find_host_bridge(pdev->bus);
+	const char *short_name;
 
-	sysfs_remove_link(&hb->dev.kobj, ide->name);
+	short_name = ide->name + strlen(dev_name(&hb->dev)) + 1;
+	sysfs_remove_link(&hb->dev.kobj, short_name);
 	kfree(ide->name);
 	ida_free(&hb->ide_stream_ids_ida, ide->stream_id);
 	ide->name = NULL;

base-commit: 8f0b4cce4481fb22653697cced8d0d04027cb1e8

---

## [2] Bjorn Helgaas — 2025-12-23
*Subject: Re: [PATCH] PCI/IDE: Fix duplicate stream symlink names for TSM
 class devices*

On Tue, Dec 23, 2025 at 04:56:01PM +0800, Xu Yilun wrote:
> The symlink name streamH.R.E is unique within a specific host bridge but
> not across the system. Error occurs e.g. when creating the first stream

Drop timestamp because it's no relevant.  Indent quoted material two
spaces.

> Fix this by adding host bridge name into symlink name for TSM class
> devices. It should be OK to change the uAPI to

Looks like this adds "pciDDDD:BB:" to one name, which is described
here and in the Documentation/ABI change.

> Internally in the IDE library, store the full name in struct pci_ide
> so TSM symlinks can use it directly, while PCI host bridge symlinks

And shortens this name, but no example or doc update?  Or maybe the
shortening just strips the "pciDDDD:BB" to preserve the existing names
somewhere else?

I'm just confused about which symlinks are changing (adding
"pciDDDD:BB") and which are being kept concise (either by staying the
same or being shortened).

> Fixes: a4438f06b1db ("PCI/TSM: Report active IDE streams")
> Reported-by: Yi Lai <yi1.lai@intel.com>

---

## [3] Xu Yilun — 2025-12-24
*Subject: Re: [PATCH] PCI/IDE: Fix duplicate stream symlink names for TSM
 class devices*

On Tue, Dec 23, 2025 at 11:31:57AM -0600, Bjorn Helgaas wrote:
> On Tue, Dec 23, 2025 at 04:56:01PM +0800, Xu Yilun wrote:
> > The symlink name streamH.R.E is unique within a specific host bridge but

Yes.

> 
> > Fix this by adding host bridge name into symlink name for TSM class

The later. The shortening is the internal code change, aims to preserve
the existing name /sys/devices/pciDDDD:BB/streamH.R.E, which is
described in:

  Documentation/ABI/testing/sysfs-devices-pci-host-bridge

  What:		pciDDDD:BB/streamH.R.E

I don't want repeat the host bridge name in host bridge context.

> 
> I'm just confused about which symlinks are changing (adding

I should have clearly listed the changed & preserved symlinks. Will
improve in v2.

Thanks,
Yilun

> 
> > Fixes: a4438f06b1db ("PCI/TSM: Report active IDE streams")

---
