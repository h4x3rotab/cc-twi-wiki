---
title: 'PCI/TSM: fix use-after-free in find_dsm_dev()'
date: 2026-06-16
last_reply: 2026-06-16
message_count: 2
participants: ['Wentao Liang', 'Lukas Wunner']
---

## [1] Wentao Liang — 2026-06-16

In find_dsm_dev(), pf0 is obtained via pf0_dev_get() which returns a
reference-counted pointer.  It is declared with __free(pci_dev_put),
so pci_dev_put() will be called when the variable goes out of scope.
Returning 'pf0' directly while it still has __free cleanup causes the
reference to be dropped before the caller can use the pointer, leading
to a use-after-free.

Fix by using return no_free_ptr(pf0) to suppress the automatic
cleanup and properly transfer ownership to the caller.

Fixes: 3225f52cde56 ("PCI/TSM: Establish Secure Sessions and Link Encryption")
Cc: stable@vger.kernel.org
Signed-off-by: Wentao Liang <vulab@iscas.ac.cn>
---
 drivers/pci/tsm.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index 5fdcd7f2e820..dd4e0cb0c6aa 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -670,7 +670,7 @@ static struct pci_dev *find_dsm_dev(struct pci_dev *pdev)
 		return NULL;
 
 	if (is_dsm(pf0))
-		return pf0;
+		return no_free_ptr(pf0);
 
 	/*
 	 * For cases where a switch may be hosting TDISP services on behalf of

---

## [2] Lukas Wunner — 2026-06-16
*Subject: Re: [PATCH] PCI/TSM: fix use-after-free in find_dsm_dev()*

On Tue, Jun 16, 2026 at 03:02:43AM +0000, Wentao Liang wrote:
> In find_dsm_dev(), pf0 is obtained via pf0_dev_get() which returns a
> reference-counted pointer.  It is declared with __free(pci_dev_put),

No, the code comment preceding find_dsm_dev() explicitly states:

   "Note that no additional reference is held for the resulting device
    because that resulting object always has a registered lifetime
    greater-than-or-equal to that of the @pdev argument."

Your patch looks like it may be an LLM-generated hallucination.
Did you use an LLM to come up with the patch?  If so, please use
an Assisted-by tag per Documentation/process/coding-assistants.rst
so that we know to expect hallucinations.

Thanks,

Lukas

---
