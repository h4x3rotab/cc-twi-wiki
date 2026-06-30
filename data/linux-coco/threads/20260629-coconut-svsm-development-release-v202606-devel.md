---
title: 'COCONUT-SVSM Development Release v2026.06-devel'
date: 2026-06-29
last_reply: 2026-06-29
message_count: 1
participants: ['Jörg Rödel']
---

## [1] Jörg Rödel — 2026-06-29

Hi all,

The end of the month is approaching quickly and it is time for another exciting
development release of COCONUT-SVSM. Exciting because this release brings some
new features, e.g. support for the UEFI variable store protocol. But there is
more, list below:

  - Added UEFI variable-store protocol.

  - Replaced the in-tree VirtIO driver fork with upstream virtio-drivers;
    integrated safe-mmio and fixed unaligned MMIO and resource-drop handling.

  - Major scheduler/task rework: fixed cross-CPU races, simplified affinity and
    context switching, added task termination waiting and a PENDING state, and
    corrected register/reference handling.

  - Expanded xbuild to build test kernels and support recipe-specific
    environment, toolchain, and feature settings.

  - Moved SVSM to 128 MiB on QEMU and Hyper-V platforms.
  - Improved APIC emulation correctness, including ICR/EOI validation, LDR
    reads, NMI self-IPIs, PPR calculation, and protocol error reporting.

  - Added libtcgtpm cross-build support and switched to Rust’s default linker
    behavior. COCONUT-SVSM can now be cross-compiled on Apple Silicon with MacOS.

  - Hardened CPUID/XSAVE handling.

  - Improved per-CPU TLB flushing.

These changes include the work of 9 contributors with a total of 99 non-merge
commits in 42 merges. The full shortlog is included below.

Happy testing!

-Joerg

Carlos López (30):
      kernel: cpu/tlb: add TlbFlushScope constructor methods
      kernel: cpu/tlb: homogenize per-CPU TLB flushes
      kernel: mm/vm/range: perform partial TLB flush for per-CPU mappings
      igvmbuilder: add CPUID leaf for YMM XSAVE size
      cpuarch: remove packed qualifier from CPUID structures
      kernel: cpu/cpuid: filter FPU/SSE features if size subleaf is not present
      kernel: cpu/sse: retrieve XSAVE area size from 0xD CPUID subleaves
      kernel: platform/snp: ignore XCR0/XSS for CPUID lookups
      Merge pull request #1111 from kraxel/edk2-docs
      xbuild: build TDX stage1 directly
      xbuild: introduce no_default_features recipe field
      xbuild: introduce toolchain recipe field
      xbuild: introduce env recipe field
      xbuild: introduce test kernel build infrastructure
      Makefile: move test kernel builds into xbuild recipes
      Makefile: respect RELEASE for test kernels
      kernel: mm/alloc: convert linear bitscan to trailing bit count
      kernel: cpu/apic: truly ignore host EOI errors
      kernel: cpu/apic: verify value written to EOI register
      kernel: cpu/apic: verify MBZ fields for ICR writes
      kernel: cpu/apic: fix get_ppr_with_tpr() ISR indexing
      kernel: cpu/apic: fix NMI delivery for physical-mode self-IPI
      kernel: cpu/apic: handle LDR register reads
      kernel: protocols/apic: correct error on invalid register access
      Merge pull request #1125 from joergroedel/gpa-map
      kernel: cpu/apic: reject more fields on ICR writes
      Merge pull request #1135 from n-ramacciotti/protocols/core_query_add_vtpm
      Documentation: add release process to doc website
      Documentation: add object handle documentation to doc website
      packit: update to latest version

Gerd Hoffmann (20):
      stage1: tag code sections as 'ax'
      stage1: rework linker script
      kernel: add .got to linker script
      bldr: add .got to linker script
      cargo: switch to rust default linker
      libtcgtpm: cross compiler setup
      libtcgtpm: libcrt cross build
      libtcgtpm: openssl cross build
      libtcgtpm: tcgtpm cross build
      Documentation: update build instructions
      Documentation: remove PcdUninstallMemAttrProtocol=TRUE
      Documentation: recommend the upstream edk2 repo
      uefivars: write up uefi mm protocol spec draft
      uefivars: add uefi mm protocol
      uefivars: announce via query protocol
      uefivars: add secure boot support
      uefivars: add uefi_mm_get_manifest
      uefivars: wire up attestation manifest
      uefivars: ensure test build coverage.
      Documentation: document edk2 build options

Joerg Roedel (6):
      CODEOWNERS: Add Carlos López
      igvmbuilder: Move COCONUT-SVSM to 128MB physical address
      Documentation: Update installation documentation for KVM planes
      launch_guest.sh: Update for KVM planes support
      Update Cargo.lock for release
      COCONUT-SVSM Release 2026.06-devel

Jon Lange (25):
      task: always start the scheduler in the idle task
      task: change context switch to a true function
      gdbstub: use common exception context structure
      task: streamline register preservation during context switch
      cpu/percpu: store certain address fields as atomics
      task: update task per-CPU state when task is locked active
      cpu/vc: remove CAA MSR handling
      platform: rename `validate_fw`
      svsm: create transition page tables only when required
      svsm: accept low memory in the kernel
      bldr: relocate from 8 MB down to 64 KB
      igvmbuilder: specify a single VTL for native IGVM platforms
      bldr: move SIPI stub into bldr
      cpu/idt: define scheduler interrupt vector
      cpu: move per-CPU run queue into `PerCpuShared`
      task: simplify `set_affinity
      Merge pull request #1061 from msft-jlange/bldr_cleanup
      tasks/exec_user: return `TaskPointer` instead of task ID
      igvmbuilder: use correct VTL for VBS VP context
      Merge pull request #1099 from msft-jlange/igvm_vtl
      task: implement `wait_for_termination`
      task: streamline reference count management during task termination
      SVSM: require SNP restricted injection
      task: introduce `PENDING` state
      Merge pull request #1134 from 00xc/apic/misc-fixes-v2

Jörg Rödel (28):
      Merge pull request #1060 from msft-jlange/task_work
      Merge pull request #1086 from msft-jlange/caa_msr
      Merge pull request #1083 from luigix25/tcg_doc
      Merge pull request #1096 from msft-jlange/igvm_vtl
      Merge pull request #1063 from 00xc/sse/xsave-size
      Merge pull request #1098 from n-ramacciotti/scripts/fix_signed_off
      Merge pull request #1084 from stefano-garzarella/script-qemu-avoid-sig-remap
      Merge pull request #1044 from msft-jlange/wait_for_task
      Merge branch 'main' into affinity
      Merge pull request #1045 from msft-jlange/affinity
      Merge pull request #1028 from 00xc/cpu/tlb/percpu
      Merge pull request #1106 from kraxel/vtpm-cross-build
      Merge pull request #1109 from joergroedel/codeowners
      Merge pull request #981 from kraxel/rust-linker
      Merge pull request #1107 from kraxel/cross-build-docs
      Merge pull request #1103 from msft-jlange/task_terminate
      Merge pull request #694 from kraxel/uefivars
      Merge pull request #1119 from luigix25/fix_fpu
      Merge pull request #1112 from stefano-garzarella/contributing-capital-letter
      Merge pull request #1131 from 00xc/mm/alloc/bitscan
      Merge pull request #1117 from joergroedel/planes-update
      Merge pull request #1126 from 00xc/apic/misc-fixes
      Merge pull request #1129 from msft-jlange/task_pending
      Merge pull request #1127 from 00xc/xbuild/test-kernels
      Merge pull request #259 from msft-jlange/restr_inj
      Merge pull request #1141 from n-ramacciotti/xbuild/fix_path
      Merge pull request #1140 from 00xc/docs/fix-missing
      Merge pull request #1145 from 00xc/packit/deps

Luigi Leonardi (7):
      Documentation/INSTALL: document all missing launch script options
      Documentation/INSTALL: remove trailing whitespace
      scripts/launch_guest: use `memory-backend-ram` for nocc mode
      scripts/launch_guest: replace grep -P with portable sed
      virtio/mmio: handle non-page-aligned MMIO device addresses
      virtio/mmio: fix drop order in MmioSlot
      kernel/task: preserve r12-r15 across context switch

Nicola Ramacciotti (6):
      scripts/signed-off: Fix check for empty body
      scripts/signed-off: Avoid exiting on the first failure
      kernel/tests: Improve accuracy of fpu test utilities
      kernel/tests: Make sure that fpu test tasks terminate
      kernel/protocols: Add vtpm to core query protocol
      xbuild/fs: Handle multi-level path

Oliver Steffen (5):
      virtio-drivers: Use forked repo
      virtio-drivers: Remove in-repo copy
      virtio: Add safe-mmio crate dependency
      virtio: Use upstream virtio-drivers
      virtio: Fix typo in safety comment

Stefano Garzarella (13):
      scripts/launch_guest: avoid signal remapping
      Merge pull request #1101 from luigix25/macos_support
      Merge pull request #1092 from osteffenrh/virtio-from-forked-repo
      Merge pull request #1102 from luigix25/virtio_alignment
      Documentation: remove capital letter requirement from commit subject
      Merge pull request #1110 from luigix25/fix_drop
      Merge pull request #1115 from n-ramacciotti/tests/wait_for_termination
      docs/attestation: fix attestation test steps ordering
      docs/attestation: document kbs-test --secret argument
      Merge pull request #1097 from tanish111/secretbox-zeroize
      Merge pull request #1108 from osteffenrh/virtio_safe-mmio_custom_backend
      docs/attestation: link to INSTALL.md in the build step
      Merge pull request #1132 from stefano-garzarella/doc-attestation-fix

tanish111 (1):
      kernel/attest: add SecretSlice for zeroed attestation secrets

---
