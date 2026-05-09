---
title: 'PCI/MSI: Fix x86 VMs crash due to dereferencing NULL'
date: 2025-03-27
last_reply: 2025-03-27
message_count: 3
participants: ['Ashish Kalra', 'Roger Pau Monné', 'Dan Williams']
---

## [1] Ashish Kalra — 2025-03-27

From: Ashish Kalra <ashish.kalra@amd.com>

Moving pci_msi_ignore_mask to per MSI domain flag is causing a panic
with SEV-SNP VMs under KVM while booting and initializing virtio-scsi
driver as below :

...
[    9.854554] virtio_scsi virtio1: 4/0/0 default/read/poll queues
[    9.855670] BUG: kernel NULL pointer dereference, address: 0000000000000000
[    9.856840] #PF: supervisor read access in kernel mode
[    9.857695] #PF: error_code(0x0000) - not-present page
[    9.858501] PGD 0 P4D 0
[    9.858501] Oops: Oops: 0000 [#1] SMP NOPTI
[    9.858501] CPU: 0 UID: 0 PID: 1 Comm: swapper/0 Not tainted 6.14.0-next-20250326-snp-host-f2a41ff576cc #379 VOLUNTARY
[    9.858501] Hardware name: QEMU Standard PC (Q35 + ICH9, 2009), BIOS unknown 02/02/2022
[    9.858501] RIP: 0010:msix_prepare_msi_desc+0x3c/0x90
[    9.858501] Code: 89 f0 48 8b 52 20 66 81 4e 4c 01 01 c7 46 04 01 00 00 00 8b 8f b4 03 00 00 48 89 e5 89 4e 50 48 8b b7 b0 09 00 00 48 89 70 58 <8b> 0a 81 e1 00 00 40 00 75 25 0f b6 50 4d d0 ea 83 f2 01 83 e2 01
[    9.858501] RSP: 0018:ffffa37f4002b898 EFLAGS: 00010202
[    9.858501] RAX: ffffa37f4002b8c8 RBX: ffffa37f4002b8c8 RCX: 0000000000000017
[    9.858501] RDX: 0000000000000000 RSI: ffffa37f400b5000 RDI: ffff984802524000
[    9.858501] RBP: ffffa37f4002b898 R08: 0000000000000002 R09: ffffa37f4002b854
[    9.858501] R10: 0000000000000004 R11: 0000000000000018 R12: ffff984802924000
[    9.858501] R13: ffff984802524000 R14: ffff9848025240c8 R15: 0000000000000000
[    9.858501] FS:  0000000000000000(0000) GS:ffff984bae657000(0000) knlGS:0000000000000000
[    9.858501] CS:  0010 DS: 0000 ES: 0000 CR0: 0000000080050033
[    9.858501] CR2: 0000000000000000 CR3: 000800003c260000 CR4: 00000000003506f0
[    9.858501] Call Trace:
[    9.858501]  <TASK>
[    9.858501]  msix_setup_interrupts+0x10e/0x290
[    9.858501]  __pci_enable_msix_range+0x2ce/0x470
[    9.858501]  pci_alloc_irq_vectors_affinity+0xb2/0x110
[    9.858501]  vp_find_vqs_msix+0x228/0x530
[    9.858501]  vp_find_vqs+0x41/0x290
[    9.858501]  ? srso_return_thunk+0x5/0x5f
[    9.858501]  ? __dev_printk+0x39/0x80
[    9.858501]  ? srso_return_thunk+0x5/0x5f
[    9.858501]  ? _dev_info+0x6f/0x90
[    9.858501]  vp_modern_find_vqs+0x1c/0x70
[    9.858501]  virtscsi_init+0x2d2/0x340
[    9.858501]  ? __pfx_default_calc_sets+0x10/0x10
[    9.858501]  virtscsi_probe+0x135/0x3c0
[    9.858501]  virtio_dev_probe+0x1b6/0x2a0
...
...
[    9.934826] Kernel panic - not syncing: Attempted to kill init! exitcode=0x00000009

This is happening as x86 VMs only have x86_vector_domain (irq_domain)
created by native_create_pci_msi_domain() and that does not have an
associated msi_domain_info. Thus accessing msi_domain_info causes a
kernel NULL pointer dereference during msix_setup_interrupts() and
breaks x86 VMs.

In comparison, for native x86, there is irq domain hierarchy created
by interrupt remapping logic either by AMD IOMMU (AMD-IR) or Intel
DMAR (DMAR-MSI) and they have an associated msi_domain_info, so
moving pci_msi_ignore_mask to a per MSI domain flag works for
native x86.

Also, Hyper-V and Xen x86 VMs create "virtual" irq domains
(XEN-MSI) or (HV-PCI-MSI) with their associated msi_domain_info,
and they can also access pci_msi_ignore_mask as per MSI domain flag.

Fixes: c3164d2e0d18 ("PCI/MSI: Convert pci_msi_ignore_mask to per MSI domain flag")
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/pci/msi/msi.c | 7 ++++---
 1 file changed, 4 insertions(+), 3 deletions(-)

diff --git a/drivers/pci/msi/msi.c b/drivers/pci/msi/msi.c
index d74162880d83..05c651be93cc 100644
--- a/drivers/pci/msi/msi.c
+++ b/drivers/pci/msi/msi.c
@@ -297,7 +297,7 @@ static int msi_setup_msi_desc(struct pci_dev *dev, int nvec,
 	/* Lies, damned lies, and MSIs */
 	if (dev->dev_flags & PCI_DEV_FLAGS_HAS_MSI_MASKING)
 		control |= PCI_MSI_FLAGS_MASKBIT;
-	if (info->flags & MSI_FLAG_NO_MASK)
+	if (info && info->flags & MSI_FLAG_NO_MASK)
 		control &= ~PCI_MSI_FLAGS_MASKBIT;
 
 	desc.nvec_used			= nvec;
@@ -612,7 +612,8 @@ void msix_prepare_msi_desc(struct pci_dev *dev, struct msi_desc *desc)
 	desc->pci.msi_attrib.is_64		= 1;
 	desc->pci.msi_attrib.default_irq	= dev->irq;
 	desc->pci.mask_base			= dev->msix_base;
-	desc->pci.msi_attrib.can_mask		= !(info->flags & MSI_FLAG_NO_MASK) &&
+	desc->pci.msi_attrib.can_mask		= info ? !(info->flags & MSI_FLAG_NO_MASK) &&
+						  !desc->pci.msi_attrib.is_virtual :
 						  !desc->pci.msi_attrib.is_virtual;
 
 	if (desc->pci.msi_attrib.can_mask) {
@@ -747,7 +748,7 @@ static int msix_capability_init(struct pci_dev *dev, struct msix_entry *entries,
 	/* Disable INTX */
 	pci_intx_for_msi(dev, 0);
 
-	if (!(info->flags & MSI_FLAG_NO_MASK)) {
+	if (!info || !(info->flags & MSI_FLAG_NO_MASK)) {
 		/*
 		 * Ensure that all table entries are masked to prevent
 		 * stale entries from firing in a crash kernel.

---

## [2] Roger Pau Monné — 2025-03-27
*Subject: Re: [PATCH] PCI/MSI: Fix x86 VMs crash due to dereferencing NULL*

On Thu, Mar 27, 2025 at 04:21:55PM +0000, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Sorry for the breakage.  Already fixed upstream by commit:

3ece3e8e5976 ("PCI/MSI: Handle the NOMASK flag correctly for all PCI/MSI backends")

From Thomas.

Regards, Roger.

---

## [3] Dan Williams — 2025-03-27
*Subject: Re: [PATCH] PCI/MSI: Fix x86 VMs crash due to dereferencing NULL*

Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

I think this would look better, and more like the original code, with an
pci_msi_ignore_mask() helper that takes an @info arg and returns bool.
Otherwise, this looks good to me.

Reviewed-by: Dan Williams <dan.j.williams@intel.com>

---
