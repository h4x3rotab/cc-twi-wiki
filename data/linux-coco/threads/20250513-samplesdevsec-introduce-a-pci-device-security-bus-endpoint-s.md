---
title: '[PATCH v2 06/11] samples/devsec: Introduce a PCI\n device-security bus + endpoint sample'
date: 2025-05-13
last_reply: 2025-05-13
message_count: 1
participants: ['Zhi Wang']
---

## [1] Zhi Wang — 2025-05-13

On Mon, 03 Mar 2025 23:14:50 -0800
Dan Williams <dan.j.williams@intel.com> wrote:

> Establish just enough emulated PCI infrastructure to register a sample
> TSM (platform security manager) driver and have it discover an IDE +
...
> +
> +static int devsec_tsm_connect(struct pci_dev *pdev)

It might be helpful to put some comments here to describe the expected
common vendor-agnostic sequences from the perspective of TSM driver in
generic style. Guess it would be helpful for vendors to evaluate how to
fit there TSM drivers into these paths.

E.g. create device context, loops of sending SPDM messages of device
connect... The same in devsec_tsm_disconnect().

> +	return -ENXIO;
> +}

It would be nice to have TDI bind/unbind verbs included.

> +static const struct pci_tsm_ops devsec_pci_ops = {
> +	.probe = devsec_tsm_pci_probe,

---
