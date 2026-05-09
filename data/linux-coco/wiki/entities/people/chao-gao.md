---
title: Chao Gao
description: Intel engineer and lead of the TDX Runtime Module Update series on linux-coco, driving it from RFC through v8 targeting kernel 7.2.
date: 2026-05-08
tags: [people, intel, tdx, module-update]
---

**Chao Gao** (Intel, `chao.gao@intel.com`). Primary author of the TDX Runtime Module Update series — the single most active patch series on linux-coco from May 2025 through May 2026.

## Contributions

- **TDX Runtime Module Update** — led from RFC ("TD-Preserving Updates", May 2025[^rfc]) through v8 (April 2026[^v8]), targeting merge in kernel 7.2. 7 revision threads totaling ~619 messages.
- **KVM: x86/tdx: VMXON during bringup** — co-authored fixes for TDX state initialization on secondary CPUs[^vmxon].
- **Runtime TDX module update sequence diagrams** — the cover letter for v8 includes detailed descriptions of the P-SEAMLDR update protocol and sysfs ABI changes.

[^rfc]: [20250523-rfc-patch-0020-td-preserving-updates.md](../../../20250523-rfc-patch-0020-td-preserving-updates.md)
[^v8]: [20260427-runtime-tdx-module-update-support.md](../../../20260427-runtime-tdx-module-update-support.md)
[^vmxon]: [20260123-runtime-tdx-module-update-support.md](../../../20260123-runtime-tdx-module-update-support.md)

## See Also

- [TDX Module Update (patch series)](../patches/tdx-module-update.md)
- [Intel TDX](../../concepts/tdx.md)
