---
title: 'PCI/IDE: Fix reading a wrong reg for unused sel stream initialization'
date: 2026-01-11
last_reply: 2026-01-22
message_count: 5
participants: ['Li Ming', 'Xu Yilun', 'Bjorn Helgaas', 'dan.j.williams@intel.com']
---

## [1] Li Ming — 2026-01-11

During pci_ide_init(), it will write PCI_ID_RESERVED_STREAM_ID into all
unused selective IDE stream blocks. In a selective IDE stream block, IDE
stream ID field is in selective IDE stream control register instead of
selective IDE stream capability register.

Fixes: 079115370d00 ("PCI/IDE: Initialize an ID for all IDE streams")
Signed-off-by: Li Ming <ming.li@zohomail.com>
---
 drivers/pci/ide.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/drivers/pci/ide.c b/drivers/pci/ide.c
index f0ef474e1a0d..26f7cc94ec31 100644
--- a/drivers/pci/ide.c
+++ b/drivers/pci/ide.c
@@ -168,7 +168,7 @@ void pci_ide_init(struct pci_dev *pdev)
 	for (u16 i = 0; i < nr_streams; i++) {
 		int pos = __sel_ide_offset(ide_cap, nr_link_ide, i, nr_ide_mem);
 
-		pci_read_config_dword(pdev, pos + PCI_IDE_SEL_CAP, &val);
+		pci_read_config_dword(pdev, pos + PCI_IDE_SEL_CTL, &val);
 		if (val & PCI_IDE_SEL_CTL_EN)
 			continue;
 		val &= ~PCI_IDE_SEL_CTL_ID;

---

## [2] Xu Yilun — 2026-01-12
*Subject: Re: [PATCH 1/1] PCI/IDE: Fix reading a wrong reg for unused sel
 stream initialization*

On Sun, Jan 11, 2026 at 03:38:23PM +0800, Li Ming wrote:
> During pci_ide_init(), it will write PCI_ID_RESERVED_STREAM_ID into all
> unused selective IDE stream blocks. In a selective IDE stream block, IDE

Reviewed-by: Xu Yilun <yilun.xu@linux.intel.com>

---

## [3] Bjorn Helgaas — 2026-01-13
*Subject: Re: [PATCH 1/1] PCI/IDE: Fix reading a wrong reg for unused sel
 stream initialization*

On Sun, Jan 11, 2026 at 03:38:23PM +0800, Li Ming wrote:
> During pci_ide_init(), it will write PCI_ID_RESERVED_STREAM_ID into all
> unused selective IDE stream blocks. In a selective IDE stream block, IDE

Acked-by: Bjorn Helgaas <bhelgaas@google.com>

Dan, I assume you'll take this?  It looks like you've merged
everything to do with ide.c.

> ---
>  drivers/pci/ide.c | 2 +-

---

## [4] dan.j.williams@intel.com — 2026-01-14
*Subject: Re: [PATCH 1/1] PCI/IDE: Fix reading a wrong reg for unused sel
 stream initialization*

Bjorn Helgaas wrote:
> On Sun, Jan 11, 2026 at 03:38:23PM +0800, Li Ming wrote:
> > During pci_ide_init(), it will write PCI_ID_RESERVED_STREAM_ID into all

Yes, I have cleared some CXL backlog from over the holidays and will get
this queued.

---

## [5] dan.j.williams@intel.com — 2026-01-22
*Subject: Re: [PATCH 1/1] PCI/IDE: Fix reading a wrong reg for unused sel
 stream initialization*

dan.j.williams@ wrote:
> Bjorn Helgaas wrote:
> > On Sun, Jan 11, 2026 at 03:38:23PM +0800, Li Ming wrote:

Now applied and will show up soon in tsm.git.

---
