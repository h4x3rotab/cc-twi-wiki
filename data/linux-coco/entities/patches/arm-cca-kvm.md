---
title: ARM CCA in KVM — Patch Series
description: The multi-revision RFC series adding KVM host-side support for ARM CCA Realm VMs, targeting RMM v2.0-beta. Largest single topic by message count in the archive. Revision history spans Jun 2024 – Mar 2026.
date: 2026-05-08
tags: [arm, cca, rme, kvm, realm, patch-series]
---

The **ARM CCA in KVM** series adds Linux KVM host-side support for creating and managing ARM Realm VMs — the ARM equivalent of Intel TDX's Trust Domains or AMD SEV-SNP guests. The series ran from June 2024 through March 2026 (7 major revisions) and is the largest topic by total message count in the 24-month archive.

## Revision History

| Version | Date | Messages | RMM Target |
|---|---|---|---|
| v3 | Jun 2024 | ~60 | RMM v1.0[^cca-jun24] |
| v4 | Aug 2024 | ~55 | RMM v1.0[^cca-aug24] |
| v5 | Oct 2024 | — | RMM v1.x[^cca-oct24] |
| v6 | Dec 2024 | ~80 | RMM v1.x[^cca-dec24] |
| v7 (RFC) | Feb 2025 | ~70 | RMM v1.x[^cca-feb25] |
| Early RFC | Jun 2025 | 89 | RMM v1.0 |
| Rev 2 | Jul 2025 | 74 | RMM v1.0 |
| Rev 3 | Aug 2025 | 74 | RMM v1.0 |
| Rev 4 | Dec 2025 | 82 | RMM v1.x |
| Rev 5 | Mar 2026 | 133 | RMM v2.0-beta |
| **v14** | **May 2026** | **107** | **RMM v2.0-bet1**[^cca-v14] |

[^cca-jun24]: [20240610-arm64-support-for-arm-cca-in-kvm.md](../../threads/20240610-arm64-support-for-arm-cca-in-kvm.md)
[^cca-aug24]: [20240821-arm64-support-for-arm-cca-in-kvm.md](../../threads/20240821-arm64-support-for-arm-cca-in-kvm.md)
[^cca-oct24]: [20241004-arm64-support-for-arm-cca-in-kvm.md](../../threads/20241004-arm64-support-for-arm-cca-in-kvm.md)
[^cca-dec24]: [20241212-arm64-support-for-arm-cca-in-kvm.md](../../threads/20241212-arm64-support-for-arm-cca-in-kvm.md)
[^cca-feb25]: [20250213-arm64-support-for-arm-cca-in-kvm.md](../../threads/20250213-arm64-support-for-arm-cca-in-kvm.md)

## Technical Design (March 2026 RFC)

The March 2026 RFC[^cca-mar26] represents a significant architectural update driven by the RMM v2.0 specification changes.

### Stateful RMI Operations (SROs)

RMM v2.0 introduces **SROs** — Stateful RMI Operations — where a single logical operation spans multiple SMC calls. Each call does a bounded amount of work (e.g., allocates a few pages), then returns `INCOMPLETE` until the operation finishes. This allows the RMM to dynamically allocate memory during complex operations like Realm creation rather than requiring the host to pre-commit all needed pages.

Currently only `RMI_REC_CREATE` and `RMI_REC_DESTROY` use SROs; other operations may follow in future spec revisions.

KVM's handling: a new `vcpu_precreate` flow loops on `RMI_REC_CREATE` until it completes, contributing memory on each iteration.

### Range-Based APIs

RMM v2.0 adds range-based variants of memory operations (e.g., map/unmap pages in a single SMC call rather than one SMC per page). This significantly reduces the overhead of Realm creation and teardown, which previously required thousands of individual SMC calls for a large VM.

### RMM v1.0 Compatibility

The series provides an **SMC shim layer** that translates v2.0 API calls to v1.0 equivalents for platforms running older RMM firmware. This allows the same KVM code to run on existing hardware with RMM v1.0.

### Key Design Decisions

**Memory management**: Realm memory comes from guest_memfd private pages. The host never has direct access to Realm pages once they are mapped into the Realm's IPA (Intermediate Physical Address) space.

**VGIC support**: ARM RME support for the VGIC (Virtual GIC Interrupt Controller) was added separately[^vgic] — Realms have a separate interrupt virtualization path through the RMM.

**pKVM interaction**: The series must be compatible with pKVM (protected KVM), where the host kernel itself runs at EL1 with restricted privileges.

## Key Participants

- **Steven Price** (Arm) — overall lead and primary author
- **Marc Zyngier** — KVM ARM maintainer, key reviewer
- **Suzuki K Poulose** (Arm) — VGIC and CPU topology
- **Joey Gouly** — SMC shim and compatibility
- **Oliver Upton** — KVM ARM core

## Related Series

- **ARM CCA Device Assignment** (RFC v1/v4): device TDISP for Realms. See [ARM CCA](../../concepts/arm-cca.md).
- **ARM LFA**: live firmware update for RMM. See [ARM CCA](../../concepts/arm-cca.md).
- **coc/tsm callbacks**: TSM lock/accept for CCA device assignment[^tsm-lock].
- **ARM CCA Planes** (RFC): in-VM isolation layers[^planes].

[^cca-v14]: [20260513-arm64-support-for-arm-cca-in-kvm.md](../../threads/20260513-arm64-support-for-arm-cca-in-kvm.md)
[^cca-mar26]: [20260318-arm64-support-for-arm-cca-in-kvm.md](../../threads/20260318-arm64-support-for-arm-cca-in-kvm.md)
[^vgic]: [20250512-arm64-rme-support-for-the-vgic-in-realms.md](../../threads/20250512-arm64-rme-support-for-the-vgic-in-realms.md)
[^tsm-lock]: [20251117-tsm-implement-lock-accept-callbacks-for-arm-cca-tdisp-setup.md](../../threads/20251117-tsm-implement-lock-accept-callbacks-for-arm-cca-tdisp-setup.md)
[^planes]: [20250926-rfc-patch-05-arm-cca-planes-support.md](../../threads/20250926-rfc-patch-05-arm-cca-planes-support.md)

## See Also

- [ARM CCA](../../concepts/arm-cca.md)
- [PCI/TDISP](pci-tsm-tdisp.md)
- [guest_memfd](../../concepts/guest-memfd.md)
