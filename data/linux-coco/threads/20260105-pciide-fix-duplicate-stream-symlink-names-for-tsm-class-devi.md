---
title: 'PCI/IDE: Fix duplicate stream symlink names for TSM class devices'
date: 2026-01-05
last_reply: 2026-01-23
message_count: 8
participants: ['Xu Yilun', 'Jonathan Cameron', 'dan.j.williams@intel.com']
---

## [1] Xu Yilun — 2026-01-05

The name streamH.R.E is used for 2 symlinks:

  1. TSM class devices: /sys/class/tsm/tsmN/streamH.R.E
  2. host bridge devices: /sys/devices/pciDDDD:BB/streamH.R.E

The first usage is broken cause streamH.R.E is only unique within a
specific host bridge but not across the system. Error occurs e.g. when
creating the first stream on a second host bridge:

  sysfs: cannot create duplicate filename '/devices/faux/tdx_host/tsm/tsm0/stream0.0.0'

Fix this by adding host bridge name into symlink name for TSM class
devices so they show up as:

  /sys/class/tsm/tsmN/pciDDDD:BB:streamH.R.E

It should be OK to change the uAPI since it's new and has few users.

The symlink name for host bridge devices keeps unchanged. Keep concise
as it is already in host bridge context.

Internally in the IDE library, store the full name in struct pci_ide
so TSM symlinks can use it directly as before, while host bridge
symlinks use only the streamH.R.E portion to preserve the existing name.

Fixes: a4438f06b1db ("PCI/TSM: Report active IDE streams")
Reported-by: Yi Lai <yi1.lai@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
v2: Changelog improvements

v1: https://lore.kernel.org/linux-coco/20251223085601.2607455-1-yilun.xu@linux.intel.com/
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
index f0ef474e1a0d..58fbe9cfd68c 100644
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
+	/* Strip host bridge name in the host bridge context */
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

## [2] Jonathan Cameron — 2026-01-05
*Subject: Re: [PATCH v2] PCI/IDE: Fix duplicate stream symlink names for TSM
 class devices*

On Mon,  5 Jan 2026 17:35:16 +0800
Xu Yilun <yilun.xu@linux.intel.com> wrote:

> The name streamH.R.E is used for 2 symlinks:
> 

For those who have managed to completely forget, it would be useful
to just mention what H R and E are. Given the docs
say H is the host bridge number I'm a little confused why it
isn't unique. At least at first glance I'd expect to see
stream0.0.0 and stream 1.0.0 your example.
Maybe H isn't unique across segments / PCI Domains? (DDDD in the above)
Maybe it should be?

Jonathan.

> 
> The first usage is broken cause streamH.R.E is only unique within a

---

## [3] Xu Yilun — 2026-01-06
*Subject: Re: [PATCH v2] PCI/IDE: Fix duplicate stream symlink names for TSM
 class devices*

On Mon, Jan 05, 2026 at 10:13:17AM +0000, Jonathan Cameron wrote:
> On Mon,  5 Jan 2026 17:35:16 +0800
> Xu Yilun <yilun.xu@linux.intel.com> wrote:

No, the Documentation/ABI/testing/sysfs-devices-pci-host-bridge says
H represents a Stream ID slot (or a Stream index) within the host
bridge's context, not the host bridge index itself. So do R/E.

> stream0.0.0 and stream 1.0.0 your example.
> Maybe H isn't unique across segments / PCI Domains? (DDDD in the above)

No. The counter of H along with the pciDDDD:BB/available_secure_streams,
indicate the platform hardware limitation on the maximum number of
Streams a host bridge can support. It should not be a global counter
across System.

Thanks,
Yilun

---

## [4] dan.j.williams@intel.com — 2026-01-22
*Subject: Re: [PATCH v2] PCI/IDE: Fix duplicate stream symlink names for TSM
 class devices*

Xu Yilun wrote:
> The name streamH.R.E is used for 2 symlinks:
> 

First thanks for fixing this, a significant oversight on my part. I will
add this to the devsec-sample tests as penance.

> Fix this by adding host bridge name into symlink name for TSM class
> devices so they show up as:

I do not like that we have this large combo name and the confusion it
causes in the code as Bjorn tripped over it.

> It should be OK to change the uAPI since it's new and has few users.

A better reason is that this ABI has never seen a released kernel.

> The symlink name for host bridge devices keeps unchanged. Keep concise
> as it is already in host bridge context.

I think what I would rather do is just back out this ABI for v6.19,
since it is late in the cycle, and fix this properly.

My initial thought of a better way to achieve the same is to create a
kobject named for the host-bridge to namespace the streams. For example:

    /sys/class/tsm/tsmN/pciDDDD:BB/streamH.R.E

However, after seeing Jonathan's feedback and noticing that he missed
that 'H' 'R' and 'E' are documented in the host bridge ABI I think it
would be better to simplify this to just a link back to the host bridge.

    /sys/class/tsm/tsmN/pciDDDD:BB => /sys/devices/pciDDDD:BB

That achieves the same result and is easier to document as "When a TSM
has a established any IDE stream it links to the host bridge. When the
last stream is removed the link is removed." It achieves the goal of
letting an admin do "ls /sys/class/tsm/tsmN/*/stream*" to get a survey
of all consumed stream resources in the system.

That is all a bit too much to do at this late date, so I think for
v6.19-final just delete this ABI, and try again for v7.0.

-- 8< --
From 2d236b203ea155d16d3251bd0e3bf4eeab2fcf6b Mon Sep 17 00:00:00 2001
From: Dan Williams <dan.j.williams@intel.com>
Date: Thu, 22 Jan 2026 16:35:56 -0800
Subject: [PATCH] Revert "PCI/TSM: Report active IDE streams"

The proposed ABI failed to account for multiple host bridges with the same
stream name. The fix needs to namespace streams or otherwise link back to
the host bridge, but a change like that is too big for a fix. Given this
ABI never saw a released kernel, delete it for now and bring it back later
with this issue addressed.

Reported-by: Xu Yilun <yilun.xu@linux.intel.com>
Reported-by: Yi Lai <yi1.lai@intel.com>
Closes: http://lore.kernel.org/20251223085601.2607455-1-yilun.xu@linux.intel.com
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 Documentation/ABI/testing/sysfs-class-tsm | 10 --------
 include/linux/pci-ide.h                   |  2 --
 include/linux/tsm.h                       |  3 ---
 drivers/pci/ide.c                         |  4 ----
 drivers/virt/coco/tsm-core.c              | 28 -----------------------
 5 files changed, 47 deletions(-)

diff --git a/Documentation/ABI/testing/sysfs-class-tsm b/Documentation/ABI/testing/sysfs-class-tsm
index 6fc1a5ac6da1..2949468deaf7 100644
--- a/Documentation/ABI/testing/sysfs-class-tsm
+++ b/Documentation/ABI/testing/sysfs-class-tsm
@@ -7,13 +7,3 @@ Description:
 		signals when the PCI layer is able to support establishment of
 		link encryption and other device-security features coordinated
 		through a platform tsm.
-
-What:		/sys/class/tsm/tsmN/streamH.R.E
-Contact:	linux-pci@vger.kernel.org
-Description:
-		(RO) When a host bridge has established a secure connection via
-		the platform TSM, symlink appears. The primary function of this
-		is have a system global review of TSM resource consumption
-		across host bridges. The link points to the endpoint PCI device
-		and matches the same link published by the host bridge. See
-		Documentation/ABI/testing/sysfs-devices-pci-host-bridge.
diff --git a/include/linux/pci-ide.h b/include/linux/pci-ide.h
index 37a1ad9501b0..5d4d56ed088d 100644
--- a/include/linux/pci-ide.h
+++ b/include/linux/pci-ide.h
@@ -82,7 +82,6 @@ struct pci_ide_regs {
  * @host_bridge_stream: allocated from host bridge @ide_stream_ida pool
  * @stream_id: unique Stream ID (within Partner Port pairing)
  * @name: name of the established Selective IDE Stream in sysfs
- * @tsm_dev: For TSM established IDE, the TSM device context
  *
  * Negative @stream_id values indicate "uninitialized" on the
  * expectation that with TSM established IDE the TSM owns the stream_id
@@ -94,7 +93,6 @@ struct pci_ide {
 	u8 host_bridge_stream;
 	int stream_id;
 	const char *name;
-	struct tsm_dev *tsm_dev;
 };
 
 /*
diff --git a/include/linux/tsm.h b/include/linux/tsm.h
index a3b7ab668eff..22e05b2aac69 100644
--- a/include/linux/tsm.h
+++ b/include/linux/tsm.h
@@ -123,7 +123,4 @@ int tsm_report_unregister(const struct tsm_report_ops *ops);
 struct tsm_dev *tsm_register(struct device *parent, struct pci_tsm_ops *ops);
 void tsm_unregister(struct tsm_dev *tsm_dev);
 struct tsm_dev *find_tsm_dev(int id);
-struct pci_ide;
-int tsm_ide_stream_register(struct pci_ide *ide);
-void tsm_ide_stream_unregister(struct pci_ide *ide);
 #endif /* __TSM_H */
diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index f0ef474e1a0d..280941b05969 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -11,7 +11,6 @@
 #include <linux/pci_regs.h>
 #include <linux/slab.h>
 #include <linux/sysfs.h>
-#include <linux/tsm.h>
 
 #include "pci.h"
 
@@ -373,9 +372,6 @@ void pci_ide_stream_release(struct pci_ide *ide)
 	if (ide->partner[PCI_IDE_EP].enable)
 		pci_ide_stream_disable(pdev, ide);
 
-	if (ide->tsm_dev)
-		tsm_ide_stream_unregister(ide);
-
 	if (ide->partner[PCI_IDE_RP].setup)
 		pci_ide_stream_teardown(rp, ide);
 
diff --git a/drivers/virt/coco/tsm-core.c b/drivers/virt/coco/tsm-core.c
index f027876a2f19..0e705f3067a1 100644
--- a/drivers/virt/coco/tsm-core.c
+++ b/drivers/virt/coco/tsm-core.c
@@ -4,13 +4,11 @@
 #define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
 
 #include <linux/tsm.h>
-#include <linux/pci.h>
 #include <linux/rwsem.h>
 #include <linux/device.h>
 #include <linux/module.h>
 #include <linux/cleanup.h>
 #include <linux/pci-tsm.h>
-#include <linux/pci-ide.h>
 
 static struct class *tsm_class;
 static DECLARE_RWSEM(tsm_rwsem);
@@ -108,32 +106,6 @@ void tsm_unregister(struct tsm_dev *tsm_dev)
 }
 EXPORT_SYMBOL_GPL(tsm_unregister);
 
-/* must be invoked between tsm_register / tsm_unregister */
-int tsm_ide_stream_register(struct pci_ide *ide)
-{
-	struct pci_dev *pdev = ide->pdev;
-	struct pci_tsm *tsm = pdev->tsm;
-	struct tsm_dev *tsm_dev = tsm->tsm_dev;
-	int rc;
-
-	rc = sysfs_create_link(&tsm_dev->dev.kobj, &pdev->dev.kobj, ide->name);
-	if (rc)
-		return rc;
-
-	ide->tsm_dev = tsm_dev;
-	return 0;
-}
-EXPORT_SYMBOL_GPL(tsm_ide_stream_register);
-
-void tsm_ide_stream_unregister(struct pci_ide *ide)
-{
-	struct tsm_dev *tsm_dev = ide->tsm_dev;
-
-	ide->tsm_dev = NULL;
-	sysfs_remove_link(&tsm_dev->dev.kobj, ide->name);
-}
-EXPORT_SYMBOL_GPL(tsm_ide_stream_unregister);
-
 static void tsm_release(struct device *dev)
 {
 	struct tsm_dev *tsm_dev = container_of(dev, typeof(*tsm_dev), dev);

---

## [5] dan.j.williams@intel.com — 2026-01-22
*Subject: Re: [PATCH v2] PCI/IDE: Fix duplicate stream symlink names for TSM
 class devices*

dan.j.williams@ wrote:
[..]
> However, after seeing Jonathan's feedback and noticing that he missed
> that 'H' 'R' and 'E' are documented in the host bridge ABI I think it

In fact it does not even need to be dynamic. At tsm_register() time when
@pci_ops is provided, link all host bridges. Unlink them at unregister
time. The only driving need for it to be dynamic is if there is ever a
platform that supports multiple TSMs each supporting a different set of
host bridges. Can cross that bridge later.

---

## [6] Xu Yilun — 2026-01-23
*Subject: Re: [PATCH v2] PCI/IDE: Fix duplicate stream symlink names for TSM
 class devices*

On Thu, Jan 22, 2026 at 05:07:01PM -0800, dan.j.williams@intel.com wrote:
> dan.j.williams@ wrote:
> [..]

I'm sort of supporting dynamic. My DUT has 40 host bridges registered,
most of them has nothing to do with TSM/IDE, so I'm afraid if it is
overkill to list them all, and bury the real TSM capable bridge in the
noise.

And if TSM always list all bridges then why we need these symlinks, we
can just:

  ls -d /sys/devices/pci*\:*/stream*


I assume the annoying part of dynamic is we need to refcount, which IMHO
unnecessarily complex and you are trying to avoid, is it?

> time. The only driving need for it to be dynamic is if there is ever a
> platform that supports multiple TSMs each supporting a different set of

---

## [7] dan.j.williams@intel.com — 2026-01-22
*Subject: Re: [PATCH v2] PCI/IDE: Fix duplicate stream symlink names for TSM
 class devices*

Xu Yilun wrote:
> On Thu, Jan 22, 2026 at 05:07:01PM -0800, dan.j.williams@intel.com wrote:
> > dan.j.williams@ wrote:

I am ok with a simple xarray of registered host bridges that gets
cleaned up when the last stream leaves.

The end goal is "ls /sys/class/tsm/tsmN/*/stream*" gives valuable signal to
the user, and yes 40 host bridges of noise should be avoided.

---

## [8] Xu Yilun — 2026-01-23
*Subject: Re: [PATCH v2] PCI/IDE: Fix duplicate stream symlink names for TSM
 class devices*

> That is all a bit too much to do at this late date, so I think for
> v6.19-final just delete this ABI, and try again for v7.0.

I agree.

> 
> -- 8< --

Tested, no problem.

---
