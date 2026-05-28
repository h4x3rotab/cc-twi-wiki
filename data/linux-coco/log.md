---
title: Wiki Log
description: Append-only record of wiki ingests and edits for the linux-coco mailing list archive.
date: 2026-05-08
tags: [log, meta]
---

## 2026-05-11 — Incremental update (May 11–27, 2026)

- Fetched new mail: `git fetch origin` in `linux-coco/git/0.git`.
- Updated `~/.public-inbox/config` inboxdir to new consolidated repo path.
- Re-ran scraper: 360 threads since 2025-05-08 → 631 total files; 29 new threads, 29 updated.
- Noise filtered (6 skipped): guest-memfd bi-weekly call invites, SVSM dev call notices, Linux Security Summit CFP.
- Signal incorporated (23 threads):
  - `concepts/tdx.md` — TDX Module Update v9/v10, TDX Module Extensions + DICE quoting RFC, Dynamic PAMT v6, TDX KVM selftests, TDX offline CPU bug, Rick Edgecombe maintainer promotion
  - `concepts/arm-coca.md` — ARM CCA KVM v14 (RMM v2.0-bet1), CCA auxiliary device
  - `concepts/sev-snp.md` — RMPOPT v1 (first upstream posting)
  - `concepts/guest-memfd.md` — in-place conversion v7 (guest_memfd-native ioctl), bind/populate fixes
  - `concepts/pci-tdisp.md` — IOMMUFD TSM ioctls v5, crypto/ccp root port ordering fix
  - `concepts/tsm-framework.md` — DMA_ATTR_CC_SHARED propagation v1+v2
  - `entities/patches/arm-cca-kvm.md` — v14 row added to revision table
  - `overview.md` — corpus count updated (631 threads, ~9,800 messages through 2026-05-27)
  - `timeline.md` — May 2026 section added

## 2026-05-09 — Extended to 24 months (May 2024 – May 2025 added)

- Ran scraper with `SINCE=2024-05-08, UNTIL=2025-05-08` to extract the prior year.
- Extracted 3,753 messages / 271 threads (May 2024 – May 2025); rendered 271 markdown files.
- Total corpus now: 9,235 messages / 602 threads across 24 months.
- Updated `overview.md` — date range, corpus counts, source inventory.
- Rewrote `timeline.md` — extended Mermaid timeline with "Year 1 — Foundations" and "Year 1 — Early 2025" sections; new narrative for May–Dec 2024 and Jan–Apr 2025.
- Added 2024 "Foundational Work" sections to all 7 concept pages:
  - `concepts/tdx.md` — TDX kexec, MMIO from userspace, TDCALL rewrite, memory hotplug, userspace hypercalls
  - `concepts/sev-snp.md` — KVM SNP attestation / KVM_EXIT_COCO, SEV-ES kexec, SVSM calling areas, SEV firmware hotloading, move SNP init to KVM, SNP cert fetching
  - `concepts/arm-cca.md` — 2024 KVM CCA revisions (v3–v5), ARM CCA guest support (running Linux inside a Realm), pKVM protected guest
  - `concepts/svsm.md` — SVSM calling areas, KVM vCPU per VMPL RFC, enlightened vTPM, COCONUT-SVSM for Intel TD partitioning
  - `concepts/tsm-framework.md` — TSM Unified MR ABI (Sep 2024 – Feb 2025), TCB stability, May 2024 configfs RFC, PCI/TSM May 2024 genesis
  - `concepts/guest-memfd.md` — guest_memfd library refactoring, 2MB THP support, bi-weekly calls origin (Oct 2024), NUMA mempolicy early RFC
  - `concepts/pci-tdisp.md` — 2024 genesis section: May 2024 TSM RFC, Jun 2024 VFIO dma-buf, Jun 2024 PCI devauth, Aug 2024 Secure VFIO RFC (128 msgs), Dec 2024 core RFC, Feb 2025 Secure VFIO v2, Mar 2025 core revision
- Updated `entities/patches/arm-cca-kvm.md` — added 2024 revision history (v3 Jun, v4 Aug, v5 Oct, v6 Dec 2024, v7 Feb 2025).
- Updated `entities/patches/pci-tsm-tdisp.md` — added 2024 predecessor rows to revision table.

## 2026-05-08 — Initial ingest

- Cloned public-inbox git archive from `https://lore.kernel.org/linux-coco/git/0.git` (87 MB).
- Initialized public-inbox 1.9.0 mirror via `public-inbox-init -V2` + `public-inbox-index` (488 MB Xapian index).
- Extracted 5,482 messages / 331 threads (May 2025 – May 2026) using over.sqlite3 + git blob reads.
- Rendered 331 thread markdown files under `data/threads/`.
- Authored 22 wiki pages:
  - `overview.md` — hub page
  - `timeline.md` — 12-month chronological narrative
  - `concepts/`: tdx, sev-snp, arm-cca, svsm, tsm-framework, guest-memfd, pci-tdisp
  - `entities/patches/`: tdx-module-update, tdx-dynamic-pamt, arm-cca-kvm, pci-tsm-tdisp, guest-memfd-inplace
  - `entities/people/`: dan-williams, chao-gao, steven-price, sean-christopherson, ackerley-tng
  - `log.md`
