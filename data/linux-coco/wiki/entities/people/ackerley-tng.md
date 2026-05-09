---
title: Ackerley Tng
description: Author of the guest_memfd in-place conversion series, driving it from RFC through v6 over 12 months with six test suites.
date: 2026-05-08
tags: [people, guest-memfd, kvm, memory]
---

**Ackerley Tng** (`ackerleytng@google.com`, Google). Primary author of the guest_memfd in-place conversion series — the most iterated guest_memfd work in the 12-month archive, with 41 thread files and ~390 messages.

## Contributions

- **guest_memfd in-place conversion** — led from RFC v1 (June 2025[^v1]) through v6 (May 2026[^v6]), adding shared/private page-state transitions within a single physical page and eliminating the two-pool limitation.
- **Six selftests** in v5/v6 covering TDX, SNP, CCA, and generic paths.
- **PRESERVE semantics** — designed and implemented the `KVM_GMEM_ATTR_PRESERVE` flag with appropriate restrictions per TEE type.

[^v1]: [20250612-kvm-guest-memfd-support-in-place-conversion-for-coco-vms.md](../../../20250612-kvm-guest-memfd-support-in-place-conversion-for-coco-vms.md)
[^v6]: [20260507-guest-memfd-in-place-conversion-support.md](../../../20260507-guest-memfd-in-place-conversion-support.md)

## See Also

- [guest_memfd In-Place Conversion (patch series)](../patches/guest-memfd-inplace.md)
- [guest_memfd concept](../../concepts/guest-memfd.md)
