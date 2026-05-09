---
title: guest_memfd — Private Memory for Confidential VMs
description: The Linux kernel's file-descriptor-backed private memory system for CoCo VMs — architecture, library refactoring, huge-page support, bi-weekly calls, in-place conversion, and NUMA mempolicy, May 2024 – May 2026.
date: 2026-05-08
tags: [guest-memfd, kvm, memory, confidential-computing, tee]
---

**guest_memfd** is a Linux kernel mechanism for managing **guest-private memory** — physical memory that is mapped into a CoCo VM but not directly accessible to the host kernel or hypervisor. It is backed by a file descriptor (the "memfd") owned by the KVM guest, which tracks page ownership and protects pages from host mapping.

## Why It Exists

In a normal KVM VM, the host can `mmap()` the guest's physical memory through the `kvm_userspace_mem` interface. In a CoCo VM (TDX, SNP, CCA Realm), the TEE hardware prevents the host from reading those pages — but the kernel still needs a way to track which pages are private (TEE-protected) vs. shared (host-accessible DMA buffers).

guest_memfd is the kernel's answer: a memfd-like object that only grants the host access to **shared** pages, and refuses host-accessible mappings of private pages.

## Architecture

```mermaid
graph TD
    APP[QEMU / VMM userspace]
    KVM[KVM kernel module]
    GMEMFD[guest_memfd fd]
    PRIV[Private pages\nTEE-encrypted]
    SHARED[Shared pages\nhost can mmap]

    APP -->|KVM_SET_USER_MEMORY_REGION2\nwith guest_memfd| KVM
    KVM --> GMEMFD
    GMEMFD --> PRIV
    GMEMFD --> SHARED
    APP -->|mmap guest_memfd\nshared only| SHARED
```

## Foundational Work (May 2024 – May 2025)

### guest_memfd Library Refactoring

A recurring theme in the first year: guest_memfd's internals needed to be restructured as a reusable library so that ARM CCA, SEV-SNP, and TDX could share common memory management code rather than duplicating it.

- `mm: Introduce guest_memfd library` (Aug 2024, initial RFC) — first proposal to extract the core guest_memfd logic into a separate library module[^gmemfd-lib-aug].
- Second revision (Aug 2024) refined the API[^gmemfd-lib-aug2].
- `mm: Refactor KVM guest_memfd to introduce guestmem library` (Nov 2024, Elliot Berman, Qualcomm) — a substantially reworked approach: rather than extracting into a library module, this version reorganizes the code into a proper `mm/guestmem.c` unit with a clean API boundary. Three posting rounds in November 2024[^gmemfd-refactor-nov].

The Qualcomm involvement reflects ARM CCA's need for guest_memfd: Realms use guest_memfd for private memory management, so Qualcomm (building CCA-capable hardware) has strong interest in making the library arch-agnostic.

### 2MB THP (Huge Page) Support

`KVM: gmem: 2MB THP support and preparedness tracking changes` (Dec 2024) — a prerequisite series for huge-page support in guest_memfd: adds 2MB transparent huge page (THP) backing for guest_memfd folios. Without this, every private page in a CoCo VM is 4KB, causing significant TLB pressure for large VMs[^gmemfd-thp].

This is the precursor to the in-place conversion work (which is needed to fully enable huge pages: you can't have a 2MB page spanning private and shared halves).

### Bi-Weekly Upstream Calls (Origin)

The guest_memfd community proposed regular upstream calls in October 2024[^gmemfd-biweekly-prop], and the first invitation went out for October 17, 2024[^gmemfd-biweekly-inv]. These bi-weekly calls became the coordination mechanism for the in-place conversion, NUMA mempolicy, and THP series.

### NUMA Mempolicy (Early RFC)

`[RFC PATCH v4] Add fbind and NUMA mempolicy support for KVM guest_memfd` (Nov 2024) — an early version of the NUMA mempolicy series (later reaching v8 in year 2)[^gmemfd-numa-2024].

[^gmemfd-lib-aug]: [20240805-mm-introduce-guest-memfd-library.md](../../20240805-mm-introduce-guest-memfd-library.md)
[^gmemfd-lib-aug2]: [20240829-mm-introduce-guest-memfd-library.md](../../20240829-mm-introduce-guest-memfd-library.md)
[^gmemfd-refactor-nov]: [20241113-mm-refactor-kvm-guest-memfd-to-introduce-guestmem-library.md](../../20241113-mm-refactor-kvm-guest-memfd-to-introduce-guestmem-library.md)
[^gmemfd-thp]: [20241212-kvm-gmem-2mb-thp-support-and-preparedness-tracking-changes.md](../../20241212-kvm-gmem-2mb-thp-support-and-preparedness-tracking-changes.md)
[^gmemfd-biweekly-prop]: [20241010-proposal-bi-weekly-guest-memfd-upstream-call.md](../../20241010-proposal-bi-weekly-guest-memfd-upstream-call.md)
[^gmemfd-biweekly-inv]: [20241015-invitation-bi-weekly-guest-memfd-upstream-call-on-2024-10-17.md](../../20241015-invitation-bi-weekly-guest-memfd-upstream-call-on-2024-10-17.md)
[^gmemfd-numa-2024]: [20241107-rfc-patch-04-add-fbind-and-numa-mempolicy-support-for-kvm-gu.md](../../20241107-rfc-patch-04-add-fbind-and-numa-mempolicy-support-for-kvm-gu.md)

## Active Patch Series (May 2025 – May 2026)

### In-Place Conversion (the flagship effort)

The most active guest_memfd patch series: **41 threads / 390 messages** over 12 months, reaching **v6** in May 2026[^inplace-v5][^inplace-v6].

**Problem**: The original guest_memfd design requires two physical memory pools — one for private pages, one for shared pages. Sharing a page means copying it. This blocks huge-page support (huge pages can't span the two pools) and wastes memory.

**Solution**: In-place conversion. A single physical page can transition between private and shared states without copying. The guest_memfd tracks the state per-page.

Key design decisions:
- New ioctl on the guest_memfd fd (not on `/dev/kvm`) for per-page shared/private attribute control.
- Guest-private pages remain unmappable to host userspace even after conversion to "shared" state until explicitly accepted.
- `PRESERVE` semantics (keep page content across state transition) restricted to pre-finalization for TDX/SNP; CCA can use it more freely.
- Foundation for huge-page support in guest_memfd (pending, not yet in this series).
- Extensive selftests: six test suites covering TDX, SNP, and generic paths.

Lead: Ackerley Tng. Reviewers: Sean Christopherson, Michael Roth, Liam Howlett.

→ Details: [guest_memfd In-Place Conversion](../entities/patches/guest-memfd-inplace.md)

### NUMA Mempolicy Support

`Add NUMA mempolicy support for KVM guest-memfd` (RFC v8, 7 patches, 39 messages)[^numa].

guest_memfd pages are allocated without NUMA awareness by default — all pages land on whatever NUMA node has free memory. For NUMA-sensitive workloads (e.g., a VM pinned to a specific NUMA node's CPUs), this can cause significant remote memory latency.

This series adds `mbind()`-style NUMA policy for guest_memfd regions, so that pages are allocated from the preferred NUMA node. The implementation reuses the kernel's existing mempolicy infrastructure.

### Preparation / Population Rework

`KVM: guest_memfd: Rework preparation/population flows in prep for in-place conversion`[^prepflow] — a prerequisite refactor series that cleanly separates the "prepare" (allocate physical pages into guest_memfd) and "populate" (map pages into the guest's second-level page table) phases.

This separation is necessary for in-place conversion: when a page converts from private to shared, only the "populate" step needs to re-run — the physical page stays in the memfd.

### Inline Helper Cleanups

`KVM: guest_memfd: Inline kvm_gmem_get_index()` series[^inline] — small maintenance patches improving the internal structure of the guest_memfd code, reducing indirection and making the folio-based path more consistent.

### Allow Host to Map guest_memfd Pages

`KVM: guest_memfd: Allow host to map guest_memfd pages`[^hostmap] — a separate proposal to allow the host to read guest_memfd shared pages directly via mmap, for debugging purposes. Received mixed feedback about security implications; still under discussion.

### IOMMUFD Integration

`[RFC PATCH] arm64/kernel: iommufd: Allow mapping from KVM's guest_memfd`[^iommufd] — explores using IOMMUFD (the kernel's IOMMU management interface) to map guest_memfd pages through the IOMMU for device DMA, enabling secure DMA for confidential VMs without copying.

### Bi-Weekly Calls

The guest_memfd community holds bi-weekly upstream calls (tracked via meeting invite threads on linux-coco)[^biweekly], coordinating patch ordering, review priorities, and integration with other CoCo subsystems.

[^inplace-v5]: [20260428-guest-memfd-in-place-conversion-support.md](../../20260428-guest-memfd-in-place-conversion-support.md)
[^inplace-v6]: [20260507-guest-memfd-in-place-conversion-support.md](../../20260507-guest-memfd-in-place-conversion-support.md)
[^numa]: [20250827-add-numa-mempolicy-support-for-kvm-guest-memfd.md](../../20250827-add-numa-mempolicy-support-for-kvm-guest-memfd.md)
[^prepflow]: [20251113-kvm-guest-memfd-rework-preparationpopulation-flows-in-prep-f.md](../../20251113-kvm-guest-memfd-rework-preparationpopulation-flows-in-prep-f.md)
[^inline]: [20250901-kvm-guest-memfd-inline-kvm-gmem-get-index-and-misc-cleanups.md](../../20250901-kvm-guest-memfd-inline-kvm-gmem-get-index-and-misc-cleanups.md)
[^hostmap]: [20250602-kvm-guest-memfd-allow-host-to-map-guest-memfd-pages.md](../../20250602-kvm-guest-memfd-allow-host-to-map-guest-memfd-pages.md)
[^iommufd]: [20260225-rfc-patch-kernel-iommufd-allow-mapping-from-kvms-guest-memfd.md](../../20260225-rfc-patch-kernel-iommufd-allow-mapping-from-kvms-guest-memfd.md)
[^biweekly]: [20250514-invitation-bi-weekly-guest-memfd-upstream-call-on-2025-05-15.md](../../20250514-invitation-bi-weekly-guest-memfd-upstream-call-on-2025-05-15.md)

## See Also

- [guest_memfd In-Place Conversion (patch series)](../entities/patches/guest-memfd-inplace.md)
- [PCI/TDISP](pci-tdisp.md)
- [Intel TDX](tdx.md)
