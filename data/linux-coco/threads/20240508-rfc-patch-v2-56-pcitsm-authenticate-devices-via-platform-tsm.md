---
title: '[RFC PATCH v2 5/6] PCI/TSM: Authenticate devices via platform TSM'
date: 2024-05-08
last_reply: 2024-05-14
message_count: 2
participants: ['Xu Yilun', 'Zhi Wang']
---

## [1] Xu Yilun — 2024-05-08

On Tue, May 07, 2024 at 11:21:37AM -0700, Dan Williams wrote:
> Xu Yilun wrote:
> > > > If (!ide_cap && tee_cap), we get here but doing the below does not make 

Agreed. I drafted some simple changes for the idea, that we keep
pci_dev::tsm for every TEE capable device (PF & VF) to execute tsm_ops,
but only adds PFs to pci_tsm_devs for "connect".


diff --git a/drivers/pci/tsm.c b/drivers/pci/tsm.c
index 9c5fb2c46662..31707f0351c6 100644
--- a/drivers/pci/tsm.c
+++ b/drivers/pci/tsm.c
@@ -241,9 +241,14 @@ void pci_tsm_init(struct pci_dev *pdev)
        if (!pci_tsm)
                return;

-       pci_tsm->ide_cap = ide_cap;
        mutex_init(&pci_tsm->exec_lock);

+       if (pdev->is_virtfn) {
+               pdev->tsm = no_free_ptr(pci_tsm);
+               return;
+       }
+
+       pci_tsm->ide_cap = ide_cap;
        pci_tsm->doe_mb = pci_find_doe_mailbox(pdev, PCI_VENDOR_ID_PCI_SIG,
                                               PCI_DOE_PROTO_CMA);
        if (!pci_tsm->doe_mb)
@@ -262,9 +267,14 @@ void pci_tsm_init(struct pci_dev *pdev)

 void pci_tsm_destroy(struct pci_dev *pdev)
 {
+       if (!pdev->tsm)
+               return;
+
        guard(rwsem_write)(&pci_tsm_rwsem);
-       pci_tsm_del(pdev);
-       xa_erase(&pci_tsm_devs, pci_tsm_devid(pdev));
+       if (!pdev->is_virtfn) {
+               pci_tsm_del(pdev);
+               xa_erase(&pci_tsm_devs, pci_tsm_devid(pdev));
+       }
        kfree(pdev->tsm);
        pdev->tsm = NULL;
 }

Thanks,
Yilun

> 
> I still think the PF needs to go through an ->add() callback because I

---

## [2] Zhi Wang — 2024-05-14
*Subject: Re: [RFC PATCH v2 5/6] PCI/TSM: Authenticate devices via platform
 TSM*

On Tue, 7 May 2024 16:46:29 +0800
Xu Yilun <yilun.xu@linux.intel.com> wrote:

> > > > +
> > > > +/* collect TSM capable devices to rendezvous with the tsm

What is the plan for the TSM capable devices in the guest?

My current understanding is there would be host TSM driver and guest
TSM driver, or a vendor TSM driver will have a host mode and a guest
mode due to its nature to understand if it is running in host or a
guest. They will be plugged into the same framework here. 

If that is the case, the TSM driver should step in and decide if a
PF/VF can be managed(added) according to its mode. Maybe TSM driver
should also indicate what tdi_verbs it supports. E.g. in the guest
mode, it tells CONNECT is not available but the device can be managed
by the TSM driver.

Thanks,
Zhi.

> 
> Thanks,

---
