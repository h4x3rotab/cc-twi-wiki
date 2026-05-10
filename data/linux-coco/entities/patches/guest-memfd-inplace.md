---
title: guest_memfd In-Place Conversion — Patch Series
description: The v1–v6 series enabling shared/private memory state transitions within a single guest_memfd physical page, eliminating the need for two physical memory pools.
date: 2026-05-08
tags: [guest-memfd, kvm, memory, patch-series, confidential-computing]
---

The **guest_memfd In-Place Conversion** series eliminates the two-pool limitation of the original guest_memfd design, allowing a single physical page to transition between private (TEE-encrypted) and shared (host-accessible) states without copying. Reached v6 in May 2026 with six test suites and is close to upstream merge.

## Revision History

| Version | Date | Messages | Key Change |
|---|---|---|---|
| RFC v1 | Jun 2025 | 18 | Initial RFC |
| v2–v3 | Jul–Oct 2025 | — | API refinement |
| v4 | Nov 2025 | 37 | Preparation/population rework integrated |
| v5 | Apr 2026 | 70 | Full PRESERVE semantics, 6 test suites |
| **v6** | **May 2026** | **50** | Maple tree fixes, out of RFC |

## Core Design

### The Two-Pool Problem

Original guest_memfd tracked pages in two separate physical pools:
- **Private pool**: pages under TEE control (not host-accessible)
- **Shared pool**: pages the host can mmap for DMA

Switching a page from private to shared required removing it from the private pool, copying it to the shared pool, and re-mapping it. This made huge-page support impossible (huge pages can't span pool boundaries) and doubled memory requirements for mixed workloads.

### In-Place Solution

Each physical page in the guest_memfd has an associated state bit. State transitions happen without copying:

```
Private ──┐           ┌── Private
          │ in-place  │
          └───────────┘
          Shared
```

The host cannot mmap a page flagged as "private" — this is enforced by the guest_memfd fault handler. After converting to "shared", the host can mmap it.

### New ioctl

A new ioctl on the guest_memfd fd (not on `/dev/kvm`) sets per-page shared/private attributes:
```c
ioctl(gmemfd, KVM_GMEM_SET_PRIVATE, &range);
ioctl(gmemfd, KVM_GMEM_SET_SHARED, &range);
```

This ioctl — not a KVM ioctl — makes guest_memfd a first-class kernel object rather than a KVM implementation detail.

### PRESERVE Semantics

The series adds a `KVM_GMEM_ATTR_PRESERVE` flag: when converting from private to shared, keep the page contents (don't zero). This is safe only if the TEE hardware guarantees the contents were not modified while private (TDX and SNP do not guarantee this post-finalization; CCA does). Accordingly:
- TDX and SNP: PRESERVE only allowed pre-finalization.
- ARM CCA: PRESERVE allowed at any time.

### Testing

Six test suites added in v5[^v5]:
1. Basic conversion (private → shared → private)
2. TDX-specific acceptance flow
3. SNP-specific pvalidate/invalidate
4. PRESERVE semantics (CCA path)
5. Huge-page boundary behavior
6. Concurrent conversion stress test

### Dependency: Preparation/Population Rework

The `KVM: guest_memfd: Rework preparation/population flows` series[^prepflow] was integrated as a prerequisite, separating the "allocate physical pages" step from the "map into guest page table" step. This separation makes in-place conversion implementable without rebuilding the whole memfd structure.

## v6 Changes

v6 (May 2026)[^v6] moved out of RFC status. Changes from v5:
- Fixed maple tree usage (improper range iteration in the conversion ioctl).
- Removed stale RFC notices from commit messages.
- Minor documentation improvements.

[^v5]: [20260428-guest-memfd-in-place-conversion-support.md](../../threads/20260428-guest-memfd-in-place-conversion-support.md)
[^v6]: [20260507-guest-memfd-in-place-conversion-support.md](../../threads/20260507-guest-memfd-in-place-conversion-support.md)
[^prepflow]: [20251113-kvm-guest-memfd-rework-preparationpopulation-flows-in-prep-f.md](../../threads/20251113-kvm-guest-memfd-rework-preparationpopulation-flows-in-prep-f.md)
[^v1]: [20250612-kvm-guest-memfd-support-in-place-conversion-for-coco-vms.md](../../threads/20250612-kvm-guest-memfd-support-in-place-conversion-for-coco-vms.md)

## See Also

- [guest_memfd concept](../../concepts/guest-memfd.md)
- [Ackerley Tng](../people/ackerley-tng.md)
