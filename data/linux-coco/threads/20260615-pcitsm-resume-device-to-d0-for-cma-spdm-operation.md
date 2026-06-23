---
title: 'PCI/TSM: Resume device to D0 for CMA-SPDM operation'
date: 2026-06-15
last_reply: 2026-06-19
message_count: 5
participants: ['Lukas Wunner', 'Jonathan Cameron', 'Dan Williams (nvidia)', 'Alexey Kardashevskiy']
---

## [1] Lukas Wunner — 2026-06-15

Per PCIe r7.0 sec 6.31.3, CMA-SPDM operation in non-D0 states is optional.
The spec does not define a way to determine if it's supported, so resume
to D0 unconditionally for the duration of a CMA-SPDM exchange.  Vivaik has
talked to Windows engineers and they said that Windows does the same.

Note that for plain DOE operation, it is sufficient for the device to be
in D3hot and its parents in D0 because config space remains accessible in
D3hot.  So CMA-SPDM goes beyond the requirements of plain DOE and hence
resuming to D0 needs to (only) be done in code paths which use DOE
specifically for CMA-SPDM.

The pattern used herein for runtime resume is the best practice introduced
by commit ef8057b07c72 ("PM: runtime: Wrapper macros for ACQUIRE()/
ACQUIRE_ERR()").

Fixes: 3225f52cde56 ("PCI/TSM: Establish Secure Sessions and Link Encryption")
Signed-off-by: Lukas Wunner <lukas@wunner.de>
Cc: stable@vger.kernel.org # v6.19+
Cc: Vivaik Balasubrawmanian <vivaik.balasubrawmanian@intel.com>
---
We're in the merge window for v7.2 and this isn't super urgent,
so it's targeting v7.3 via tsm.git/next.

Technically I'd have permission to apply myself,
but I wouldn't want to without acks from Dan and AMD!
Thanks for taking a look!

 drivers/crypto/ccp/sev-dev-tsm.c | 6 ++++++
 drivers/pci/tsm.c                | 6 ++++++
 2 files changed, 12 insertions(+)

diff --git a/drivers/crypto/ccp/sev-dev-tsm.c b/drivers/crypto/ccp/sev-dev-tsm.c
index b07ae52..108204f7 100644
--- a/drivers/crypto/ccp/sev-dev-tsm.c
+++ b/drivers/crypto/ccp/sev-dev-tsm.c
@@ -7,6 +7,7 @@
 #include <linux/tsm.h>
 #include <linux/iommu.h>
 #include <linux/pci-doe.h>
+#include <linux/pm_runtime.h>
 #include <linux/bitfield.h>
 #include <linux/module.h>
 
@@ -30,6 +31,7 @@ static int sev_tio_spdm_cmd(struct tio_dsm *dsm, int ret)
 {
 	struct tsm_dsm_tio *dev_data = &dsm->data;
 	struct tsm_spdm *spdm = &dev_data->spdm;
+	int pm_ret;
 
 	/* Check the main command handler response before entering the loop */
 	if (ret == 0 && dev_data->psp_ret != SEV_RET_SUCCESS)
@@ -38,6 +40,10 @@ static int sev_tio_spdm_cmd(struct tio_dsm *dsm, int ret)
 	if (ret <= 0)
 		return ret;
 
+	PM_RUNTIME_ACQUIRE(&dsm->tsm.base_tsm.pdev->dev, pm);
+	if ((pm_ret = PM_RUNTIME_ACQUIRE_ERR(&pm)))
+		return pm_ret;
+
 	/* ret > 0 means "SPDM requested" */
 	while (ret == PCI_DOE_FEATURE_CMA || ret == PCI_DOE_FEATURE_SSESSION) {
 		ret = pci_doe(dsm->tsm.doe_mb, PCI_VENDOR_ID_PCI_SIG, ret,
diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index 5fdcd7f..af1817e 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -12,6 +12,7 @@
 #include <linux/pci.h>
 #include <linux/pci-doe.h>
 #include <linux/pci-tsm.h>
+#include <linux/pm_runtime.h>
 #include <linux/sysfs.h>
 #include <linux/tsm.h>
 #include <linux/xarray.h>
@@ -886,6 +887,7 @@ int pci_tsm_doe_transfer(struct pci_dev *pdev, u8 type, const void *req,
 			 size_t req_sz, void *resp, size_t resp_sz)
 {
 	struct pci_tsm_pf0 *tsm;
+	int rc;
 
 	if (!pdev->tsm || !is_pci_tsm_pf0(pdev))
 		return -ENXIO;
@@ -894,6 +896,10 @@ int pci_tsm_doe_transfer(struct pci_dev *pdev, u8 type, const void *req,
 	if (!tsm->doe_mb)
 		return -ENXIO;
 
+	PM_RUNTIME_ACQUIRE(&pdev->dev, pm);
+	if ((rc = PM_RUNTIME_ACQUIRE_ERR(&pm)))
+		return rc;
+
 	return pci_doe(tsm->doe_mb, PCI_VENDOR_ID_PCI_SIG, type, req, req_sz,
 		       resp, resp_sz);
 }

---

## [2] Lukas Wunner — 2026-06-15
*Subject: Re: [PATCH] PCI/TSM: Resume device to D0 for CMA-SPDM operation*

On Mon, Jun 15, 2026 at 01:42:52PM +0000, sashiko-bot@kernel.org wrote:
> > +++ b/drivers/crypto/ccp/sev-dev-tsm.c
> > @@ -38,6 +40,10 @@ static int sev_tio_spdm_cmd(struct tio_dsm *dsm, int ret)

Moving PM_RUNTIME_ACQUIRE() inside the while loop may lead to repeated
D0 -> D3hot -> D0 -> D3hot ... transitions (depending on autosuspend
settings of the device, which are user-configurable through sysfs).
It would also lead to overhead induced by runtime PM code (repeated
spinlock acquisition etc).

So I believe keeping PM_RUNTIME_ACQUIRE() outside the while loop is
the right thing to do, but I'll leave this to AMD engineers to decide.

> [Severity: High]
> Does using PM_RUNTIME_ACQUIRE() here risk leaving the hardware permanently

If the device is deleted anyway, we don't care about leaked references.
And we absolutely do not want to synchronously runtime suspend here.

> > +++ b/drivers/pci/tsm.c
> > @@ -894,6 +896,10 @@ int pci_tsm_doe_transfer(struct pci_dev *pdev, u8 type, const void *req,

Hallucination, this code does not perform "generic DOE" exchanges, only
CMA-SPDM ones.

> [Severity: High]
> Is this exported API also susceptible to the same asynchronous put regression

We have to leave de-enumerated devices in D0 to ensure that a subsequent
rescan successfully re-enumerates them.  E.g. leaving a Downstream Port
in D3hot upon de-enumeration would leave any children inaccessible.

We also leave unbound devices in D0 for similar reasons.

Thanks,

Lukas

---

## [3] Jonathan Cameron — 2026-06-16
*Subject: Re: [PATCH] PCI/TSM: Resume device to D0 for CMA-SPDM operation*

On Mon, 15 Jun 2026 15:19:30 +0200
Lukas Wunner <lukas@wunner.de> wrote:

> Per PCIe r7.0 sec 6.31.3, CMA-SPDM operation in non-D0 states is optional.
> The spec does not define a way to determine if it's supported, so resume
Seems reasonable to me and your replies to sashiko stuff seem to have that well
covered.  So FWIW

Reviewed-by: Jonathan Cameron <jic23@kernel.org>

---

## [4] Dan Williams (nvidia) — 2026-06-16
*Subject: Re: [PATCH] PCI/TSM: Resume device to D0 for CMA-SPDM operation*

Lukas Wunner wrote:
> Per PCIe r7.0 sec 6.31.3, CMA-SPDM operation in non-D0 states is optional.
> The spec does not define a way to determine if it's supported, so resume

Thanks, Lukas. A few questions:

This says Fixes, but I assume it is based on inspection and not a
report?

There are no upstream usages of pci_tsm_doe_transfer() yet, but the ones
in flight would suffer from the "D0 -> D3hot -> D0 -> D3hot" bounce that
you described to sashiko. I.e. the runtime acquire should be done at a
higher level.

I think the natural place to add PM_RUNTIME_ACQUIRE() that covers all
cases is withing pci_tsm_connect() and pci_tsm_disconnect().

I also think failure to power manage the device in the disconnect path
should not be fatal to performing the rest of the cleanup.

---

## [5] Alexey Kardashevskiy — 2026-06-19
*Subject: Re: [PATCH] PCI/TSM: Resume device to D0 for CMA-SPDM operation*

On 17/6/26 03:34, Dan Williams (nvidia) wrote:
> Lukas Wunner wrote:
>> Per PCIe r7.0 sec 6.31.3, CMA-SPDM operation in non-D0 states is optional.

I am not convinced this is a very useful helper but I'll post a patch to use that instead of calling pci_doe() directly :)

> in flight would suffer from the "D0 -> D3hot -> D0 -> D3hot" bounce that
> you described to sashiko. I.e. the runtime acquire should be done at a

Agree, although the AMD chunk of the patch would work too.


> I also think failure to power manage the device in the disconnect path
> should not be fatal to performing the rest of the cleanup.

+1.

---
