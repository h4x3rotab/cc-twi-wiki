---
title: Sean Christopherson
description: Google engineer and KVM x86 maintainer — the most prolific reviewer on linux-coco across TDX, SEV, guest_memfd, and general KVM confidential computing patches.
date: 2026-05-08
tags: [people, google, kvm, tdx, sev-snp, maintainer]
---

**Sean Christopherson** (Google, `seanjc@google.com`). KVM x86 co-maintainer and the most consistently active reviewer on linux-coco across all Intel and AMD confidential computing series.

## Role

Sean reviews (and frequently requests significant changes to) virtually every TDX, SEV, and KVM guest_memfd series that touches core KVM x86 paths. His review comments frequently drive major architectural revisions:
- On **TDX Dynamic PAMT**: commented extensively on SEPT integration and VMXON ordering[^pamt].
- On **guest_memfd in-place conversion**: reviewed every revision, providing detailed comments on the preparation/population split and maple tree usage[^inplace].
- On **TDX VMXON bringup**: co-authored portions of the fix[^vmxon].
- On **KVM: x86: APX register prep work**: authored cleanup series that landed in v6.10[^apx].

[^pamt]: [20260128-rfc-patch-v5-0045-tdx-dynamic-pamt-s-ept-hugepage.md](../../../20260128-rfc-patch-v5-0045-tdx-dynamic-pamt-s-ept-hugepage.md)
[^inplace]: [20260507-guest-memfd-in-place-conversion-support.md](../../../20260507-guest-memfd-in-place-conversion-support.md)
[^vmxon]: [20260213-kvm-x86tdx-have-tdx-handle-vmxon-during-bringu.md](../../../20260213-kvm-x86tdx-have-tdx-handle-vmxon-during-bringu.md)
[^apx]: [20260409-kvm-x86-reg-cleanups-prep-work-for-apx.md](../../../20260409-kvm-x86-reg-cleanups-prep-work-for-apx.md)

## See Also

- [Intel TDX](../../concepts/tdx.md)
- [guest_memfd](../../concepts/guest-memfd.md)
