---
title: Confidential Computing Wiki Hub
description: Browsable archives of two confidential computing mailing lists — the CCC TWI SIG (groups.io) and the linux-coco kernel list (lore.kernel.org).
date: 2026-05-09
tags: [confidential-computing, hub, index]
---

Two mailing list corpora, both covering confidential computing from different angles: the industry coordination side (TWI SIG) and the upstream kernel development side (linux-coco).

## Lists

| List | Coverage | Threads | Description |
|---|---|---|---|
| [TWI SIG](twi/wiki/overview.md) | 2024–2025 | ~200 | Confidential Computing Consortium TWI SIG on groups.io — use-case definitions, attestation workflows, cross-vendor interop |
| [linux-coco](linux-coco/wiki/overview.md) | May 2024 – May 2026 | 602 | `linux-coco@lists.linux.dev` — upstream kernel patches for TDX, SEV-SNP, ARM CCA, TDISP, guest_memfd |

## What Is Confidential Computing?

Confidential Computing (CoCo) uses hardware-isolated execution environments (TEEs) to run VMs whose memory is encrypted and inaccessible to the host. The three main hardware implementations in these archives:

- **Intel TDX** (Trust Domain Extensions) — encrypted VMs managed by the TDX Module in SEAM mode
- **AMD SEV-SNP** (Secure Encrypted Virtualization, Secure Nested Paging) — encrypted VMs with RMP-enforced memory integrity
- **ARM CCA** (Confidential Compute Architecture) — Realm VMs managed by the Realm Management Monitor (RMM)
