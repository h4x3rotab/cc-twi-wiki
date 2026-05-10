---
title: 'COCONUT-SVSM Development Release v2026.02-devel'
date: 2026-02-27
last_reply: 2026-02-27
message_count: 1
participants: ['Jörg Rödel']
---

## [1] Jörg Rödel — 2026-02-27

Hi,

The COCONUT-SVSM development release for February is tagged and ready for
testing and wider use. The release includes 65 non-merge commits which bring
several improvements to COCONUT-SVSM.

There are no new features this time, but a lot of improvements around CI and
the core infrastructure. Highlights are:

	- CI improvements. GitHub CI is now able to optionally run formal
	  verification on PRs.

	- Fix of unsound behavior in the per-cpu code.

	- Update to OpenSSL 3.5.5 for the TPM.

	- Switch to Rust 1.88 as the minimal version to build COCONUT-SVSM.

	- A lot of rework and improvements in the boot flow, an important step
	  towards a minimal stage2 loader.

Again a big THANKs to the COCONUT-SVSM community for all the contributions. The
first two releases of 2026 mark a strong start into the year for COCONUT-SVSM.
For all the nitty details of what changes the shortlog is attached.

Happy testing and hacking.

Regards,

	Joerg

Full shortlog:

Carlos L�pez (16):
      mm/guestmem: fix GuestPtr trait bounds
      mm/guestmem: introduce GuestPtr::try_read()
      mm/guestmem: introduce UserPtr::try_read()
      cpu/percpu: do not expose raw runqueue
      cpu/percpu: do not expose vranges directly
      cpu/percpu: fully harden against reentrancy
      mm/page_visibility: add Sync for SharedBox
      cpu/apic: require Sync as part of ApicAccess
      cpu/irq_state: make IrqState Sync
      cpu/percpu: ensure PerCpu is reentrancy-safe at compile time
      repo: update packit to latest commit
      insn_decode: make InsnMachineMem generic over T
      insn_decode: remove dynamic dispatch from InsnMachineCtx
      kernel/insn_decode: tests: fix Miri errors
      kernel/mm/guestmem: tests: ignore invalid bit pattern test under Miri
      fuzz: insn: provide valid pointer in TestCtx

Joerg Roedel (3):
      kernel/sev: Check physical address of VMSA for 2MiB alignemnt
      kernel/platform: Use PageSize conditionally
      COCONUT-SVSM Release 2026.02-devel

Jon Lange (22):
      stage2: allocate kernel page tables from kernel heap
      svsm: remove duplicate construction of kernel page tables
      kernel: simplify stage2 layout
      svsm: create transition page tables for AP startup
      kernel: limit low memory page tables to AP startup code
      Merge pull request #928 from msft-jlange/page_tables
      igvmbuilder: require tdx-stage1 for TDP
      Merge pull request #881 from MelodyHuibo/reinject_irq_clear_busy
      kernel: defer page validation out of stage2
      kernel: allocate CPUID/secrets pages on all platforms
      kernel_launch: remove platform type from launch struct
      kernel: reclaim VMSA heap space when unused
      kernel: remove `SvsmConfig`
      igvm_params: rename `igvm_params`
      boot: move boot definition crate
      bootimg: implement boot image loader library
      stage2: consume boot image library
      svsm: move kernel initialization arguments onto the stack
      Merge pull request #968 from stefano-garzarella/rust-1.88.0
      Cargo.toml: add `cpudefs` to `members`
      sev/ghcb: calculate page state chage page size directly
      global_asm: ensure code is marked as `.text`

J�rg R�del (14):
      Merge pull request #920 from 00xc/cpu/percpu/sync-v2
      Merge pull request #954 from joergroedel/boot-fix
      Merge pull request #922 from 00xc/mm/guestmem/bounds
      Merge pull request #952 from 00xc/repo/update-packit
      Merge pull request #955 from stefano-garzarella/update-cargo-lock-zerocopy
      Merge pull request #974 from 00xc/tests/miri
      Merge pull request #973 from msft-jlange/ghcb_psc
      Merge pull request #969 from luigix25/cleanup_launch_guest
      Merge pull request #972 from msft-jlange/cargo_members
      Merge pull request #959 from stefano-garzarella/cargo-hack
      Merge pull request #964 from stefano-garzarella/ci-fix-cargo-v-check
      Merge pull request #965 from stefano-garzarella/verification-label
      Merge pull request #977 from 00xc/tests/miri
      Merge pull request #978 from msft-jlange/gloabl_asm

Luigi Leonardi (2):
      block: remove unnecessary Box wrapper
      scripts/launch_guest: require QEMU 10.1 as minimum version

Melody Wang (1):
      cpu: Make sure interrupts do not disappear

Oliver Steffen (4):
      libtcgtpm/libcrt: Add stub for strpbrk()
      libtcgtpm: Update OpenSSL to 3.5.5
      libtcgtpm: Disable more unused algorithms for OpenSSL
      libtcgtpm: Remove deprecated OpenSSL build option

Peter Fang (2):
      Merge pull request #957 from msft-jlange/igvm_stage1
      Merge pull request #953 from msft-jlange/bootlib

Stefano Garzarella (26):
      Cargo.lock: refresh after packit zerocopy update
      Merge pull request #958 from 00xc/mm/guestmem/bounds
      verification: add NonNull<T> specification for Verus
      github/manual-verify: check cargo-v output for errors
      Add `test` crate in the workspace
      verification/verus_stub: fix unresolved import
      virtio-drivers: use std crates in FakeHal
      virtio-drivers: fix unused variable
      kernel/block: make BLOCK_DEVICE publicly visible
      Makefile: add CARGO_HACK env variable to run clippy with cargo-hack
      Documentation: add `Linting` section in CONTRIBUTING.md
      libtcgtpm: update TPM reference implementation to fix the license
      Merge pull request #960 from luigix25/cleanup_blk
      Merge pull request #961 from osteffenrh/openssl-3.5.5
      Merge pull request #962 from stefano-garzarella/fix-verification
      Merge pull request #966 from stefano-garzarella/update-tcg-tpm-license
      kernel/gdt: fix UB in GDT::drop()
      Fix `uninlined_format_args` lint for Rust 1.88.0
      kernel: fix `borrow_as_ptr` lint for Rust 1.88.0
      kernel/vtpm: fix `manual_dangling_ptr` lint for Rust 1.88.0
      Cargo.toml: remove deprecated `clippy::match_on_vec_items` lint
      Update Rust toolchain to 1.88.0
      Update bytes to 1.11.1
      Update time to 0.3.47
      Merge pull request #956 from stefano-garzarella/fix-cargo-audit-bytes
      github/manual-verify: trigger on verification label

---
