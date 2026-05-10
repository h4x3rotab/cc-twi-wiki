---
title: TDX Dynamic PAMT + S-EPT Hugepage — Patch Series
description: RFC combining two TDX memory-management optimizations — Dynamic PAMT (sparse metadata) and S-EPT Hugepage — into a 45-patch series that has been in RFC since 2025 due to dependency ordering.
date: 2026-05-08
tags: [tdx, intel, pamt, ept, hugepage, memory, patch-series]
---

This RFC combines two independent TDX memory-management optimizations that share enough infrastructure to benefit from co-development:

1. **Dynamic PAMT** (Rick Edgecombe) — reduces the memory overhead of the Physical Address Metadata Table by using sparse allocation.
2. **S-EPT Hugepage** (Yan Zhao) — enables 2MB/1GB huge-page mappings in TDX's Secure EPT, improving TD VM performance.

## Background

### PAMT Overhead

The Physical Address Metadata Table tracks ownership and type of every 4KB physical page used by TDX. In the current implementation, PAMT is allocated statically at TDX initialization time as a contiguous array covering all physical memory — roughly **1/256th of RAM**. On a 2TB server, that's ~8GB of permanently reserved metadata.

Dynamic PAMT replaces the flat array with a sparse structure: PAMT chunks are only allocated when the corresponding physical memory is actually used by TDs, dramatically reducing the static footprint[^pamt-v5].

### S-EPT Huge Pages

TDX's Secure EPT (Second-Level Page Table) currently operates at 4KB granularity — even when the host EPT uses 2MB or 1GB pages. This forces the TDX Module to walk deeper page table trees and reduces TLB efficiency for TD workloads with large working sets. S-EPT Hugepage adds support for 2MB pages in the SEPT[^pamt-v5].

## Revision History

| Version | Date | Patches | Messages |
|---|---|---|---|
| Early separate RFCs | Mid-2025 | — | 97+97+106 |
| Combined RFC v5 | Jan 2026 | 45 | 151 |

The three earlier threads (all titled `TDX: Enable Dynamic PAMT`, May/Sep/Nov 2025) represent the standalone Dynamic PAMT progression. The January 2026 RFC v5 merged S-EPT Hugepage into the same series.

## v5 Design

The 45-patch RFC v5[^pamt-v5] has a two-part structure:

**Part 1: Dynamic PAMT** (patches 1–25)
- New `tdx_pamt` object with reference counting.
- Lazy PAMT allocation keyed to `struct page` ranges.
- TDMR rebuild triggers for partial PAMT coverage.
- Integration with TDX Module's `TDH.SYS.TDMR.CONFIG` interface.

**Part 2: S-EPT Hugepage** (patches 26–45)
- New `TDH.MEM.SEPT.ADD.HUGE` and related SEAMCALL wrappers.
- KVM EPT page fault handler updated to promote/demote SEPT pages.
- IOMMU integration for huge-page DMA (coordinated with IOMMUFD changes).

## Dependencies and Blockers

The series has been in RFC because it depends on:
1. **VMXON series** landing upstream first (restructuring CPU bringup; needed by both Dynamic PAMT and S-EPT).
2. **TDX Module v1.6+** supporting the new SEAMCALLs for SEPT huge pages.

The VMXON series itself went through multiple revisions on linux-coco[^vmxon]. As of May 2026, Dynamic PAMT is still in RFC.

[^pamt-v5]: [20260128-rfc-patch-v5-0045-tdx-dynamic-pamt-s-ept-hugepage.md](../../threads/20260128-rfc-patch-v5-0045-tdx-dynamic-pamt-s-ept-hugepage.md)
[^pamt-v3]: [20251120-tdx-enable-dynamic-pamt.md](../../threads/20251120-tdx-enable-dynamic-pamt.md)
[^vmxon]: [20251205-kvm-x86tdx-have-tdx-handle-vmxon-during-bringu.md](../../threads/20251205-kvm-x86tdx-have-tdx-handle-vmxon-during-bringu.md)

## See Also

- [Intel TDX](../../concepts/tdx.md)
- [TDX Module Update](tdx-module-update.md)
