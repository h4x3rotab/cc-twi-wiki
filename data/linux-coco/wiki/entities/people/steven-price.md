---
title: Steven Price
description: Arm engineer and lead of the ARM CCA in KVM series on linux-coco, driving it through multiple RFCs toward RMM v2.0 compliance.
date: 2026-05-08
tags: [people, arm, cca, kvm]
---

**Steven Price** (Arm, `steven.price@arm.com`). Primary author and lead of the ARM CCA in KVM series — the largest topic by total message count in the 12-month archive.

## Contributions

- **ARM CCA in KVM** — led all five major revisions (Jun 2025 through Mar 2026[^cca-mar26]), adding KVM host-side support for Realm VM creation, memory management, and vCPU lifecycle against the RMM v1.0 → v2.0 spec evolution.
- **RMM v2.0 adoption** — the March 2026 RFC is the first version targeting RMM v2.0-beta, adding Stateful RMI Operations (SROs) and range-based APIs.
- **TSM connect/disconnect callbacks** — co-authored the TSM host-side callbacks for CCA device assignment[^tsm-connect].

[^cca-mar26]: [20260318-arm64-support-for-arm-cca-in-kvm.md](../../../20260318-arm64-support-for-arm-cca-in-kvm.md)
[^tsm-connect]: [20251027-coc-tsm-implement-connect-disconnect-callbacks-for-arm-cca-i.md](../../../20251027-coc-tsm-implement-connect-disconnect-callbacks-for-arm-cca-i.md)

## See Also

- [ARM CCA in KVM (patch series)](../patches/arm-cca-kvm.md)
- [ARM CCA concept](../../concepts/arm-cca.md)
