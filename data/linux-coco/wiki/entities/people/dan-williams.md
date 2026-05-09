---
title: Dan Williams
description: Intel engineer and lead of the PCI/TSM TDISP framework on linux-coco. Maintains tsm.git and authors the cross-vendor PCIe device attestation infrastructure.
date: 2026-05-08
tags: [people, intel, pci-tsm, tdisp, tee-io]
---

**Dan Williams** (Intel, `dan.j.williams@intel.com`). The primary architect and maintainer of the PCI/TSM (TDISP) framework for confidential computing device assignment in the Linux kernel.

## Contributions

- **PCI/TSM Core Infrastructure** — leads the multi-revision series establishing the vendor-neutral TDISP framework. v3 landed in `tsm.git#next`; GIT PULL for 7.1 issued April 2026[^pci-tsm].
- **PCI/TSM: TEE I/O Infrastructure** — authored the guest-side netlink ABI for device attestation evidence and the `IORES_DESC_ENCRYPTED` MMIO classification[^tee-io].
- **tsm.git maintainer** — maintains the `tsm.git#staging` and `tsm.git#next` trees as the coordination point for all CoCo device assignment series across vendors.
- **GIT PULL requests** — submits TSM pull requests to Linus; issued for 6.16 and 7.1[^gitpull].

[^pci-tsm]: [20250515-pcitsm-core-infrastructure-for-pci-device-security-tdisp.md](../../../20250515-pcitsm-core-infrastructure-for-pci-device-security-tdisp.md)
[^tee-io]: [20260302-pcitsm-tee-io-infrastructure.md](../../../20260302-pcitsm-tee-io-infrastructure.md)
[^gitpull]: [20260426-git-pull-trusted-security-manager-pcie-tsm-update-for-71.md](../../../20260426-git-pull-trusted-security-manager-pcie-tsm-update-for-71.md)

## See Also

- [PCI/TSM TDISP (patch series)](../patches/pci-tsm-tdisp.md)
- [PCI/TDISP concept](../../concepts/pci-tdisp.md)
