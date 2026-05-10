---
title: 'COCONUT-SVSM Development Release v2026.01-devel'
date: 2026-01-29
last_reply: 2026-01-29
message_count: 1
participants: ['Jörg Rödel']
---

## [1] Jörg Rödel — 2026-01-29

Hi,

The first development release of COCONUT-SVSM in 2026 it tagged and ready for
wider testing and use. This release includes 96 non-merge commits which bring
really nice improvements to the project.

The highlights include:

	- Move to the Rust 2024 edition. This includes updates to adapt the
	  code-base to changes in Rust language semantics and quite a number of
	  updates for cargo-fmt compliance.

	- Symbolized stack traces for easier debugging. When COCONUT-SVSM
	  prints a kernel stack trace it will now include the symbols in debug
	  builds.

	- Boot flow improvements. The stage2 loader can now allocate directly
	  from the kernel heap and build the initial page-tables for
	  COCONUT-SVSM. Once the kernel boots it does not need to re-build its
	  page-tables.

	- A critical bug has been fixed which caused boot failures using
	  upstream EDK2 firmware.

Besides these highlights there have been numerous other changes to improve the
code-base and fix smaller issues. A big THANKS again to the COCONUT-SVSM
community for all the efforts and contributions. The attached shortlog has all
the details.

Quite a few members of our community will attend FOSDEM in Brussels this
weekend. If you are interested come by and say Hi, we will coordinate us in our
project Matrix chat:

	https://matrix.to/#/#coconut-svsm:matrix.org

I will hang out mostly in the Virtualization, Confidential Computing, and
Kernel Devrooms. Hope to see many of you there.

Regards,

	Joerg

Shortlog:

Carlos L�pez (52):
      xbuild: add shorthand method to get component features
      xbuild/features: simply return feature list to caller
      xbuild: use features in make-based build
      mm/alloc: constify allocate_slab_page()
      mm/alloc: check slab size at compile time
      mm/alloc: convert slab const generics to usize
      address: implement NonNull to VirtAddr conversion
      mm/alloc: type slab allocations as NonNull
      mm/alloc: type SlabPage::next_page as NonNull
      mm/alloc: ensure that SlabPage data pages are freed once
      mm/alloc: introduce SlabCommon::allocate_page_slot()
      mm/alloc: consolidate SlabPage initialization/destruction
      mm/guestmem: implement NonNull to GuestPtr conversion
      cpu/percpu: represent CAA as NonNull instead of VirtAddr
      Makefile: build test kernels via xbuild
      github/workflows: call xbuild on JSON recipes only
      repo: move verification crates into verification/
      platform: mark all page validation operations as unsafe
      debug/stacktrace: cleanup argument usage
      debug/stacktrace: do not allocate when printing a stacktrace
      sev/secrets_page: remove SecretsPageRef
      virtio-drivers: remove unused Cargo.toml file
      cpuarch: update to Rust 2024 edition (no changes)
      libtcgtpm: update to Rust 2024 edition (no changes)
      release: update to Rust 2024 edition (no changes)
      stage1: update to Rust 2024 edition (no changes)
      test: update to Rust 2024 edition (no changes)
      bootlib: update to Rust 2024 edition (format changes)
      elf: update to Rust 2024 edition (format changes)
      fuzz: update to Rust 2024 edition (format changes)
      libaproxy: update to Rust 2024 edition (format changes)
      syscall: update to Rust 2024 edition (format changes)
      tools/aproxy: update to Rust 2024 edition (format changes)
      tools/igvmmeasure: update to Rust 2024 edition (format changes)
      verification: update to Rust 2024 edition (format changes)
      virtio-drivers: update to Rust 2024 edition (format changes)
      xbuild: update to Rust 2024 edition (format changes)
      user: update to Rust 2024 edition (misc. changes)
      tools/igvmbuilder: update to Rust 2024 edition (several changes)
      kernel: update to Rust 2024 edition (several changes)
      repo: use single workspace edition
      scripts/pre-commit: pick up Rust edition from rustfmt.toml
      elf/file: introduce ElfFile::read_verified_phdr()
      elf/file: introduce ElfFile::read_verified_shdr()
      build: keep ELF symbol information in debug builds
      elf/file: parse .symtab section
      elf/file: parse .strtab section
      bootlib: add kernel symbol definitions
      stage2: decouple ELF reading and loading
      stage2: parse ELF symbol information
      SVSM: introduce symbol resolution infrastructure
      debug/stacktrace: resolve symbol addresses

Jon Lange (17):
      igvmmeasure: remove SEV features check
      sev: require the debug register virtualization feature
      vc: remove DR7 ghcb test
      stage2: allocate kernel launch info from kernel heap
      svsm: eliminate static `LAUNCH_INFO`
      kernel: remove valid page bitmap from stage2
      stage2: remove heap alignment requirement
      kernel: allocate initial kernel stack from kernel heap
      kernel: free BSP init stack when it is no longer needed
      kernel: alllocate CPUID page from kernel heap
      kernel: alllocate secrets page from kernel heap
      cpu/idt: don't panic on unhandled user-mode exceptions
      cpu/idt: remove unused handlers
      vpu/vc: panic on a page not validated #VC
      tools/igvmbuilder: fix highest VTL for native builds
      tdp: start APs without going through stage2
      virtio: suppress virtio detection when no fw_cfg is present

Nicola Ramacciotti (7):
      kernel/mm/alloc: Remove unnecessary any()
      kernel/mm/alloc: Remove dead code allowance
      kernel,stage1: Remove the explicit rust-version number
      kernel: Apply clippy suggestion
      repo: Update rust version to 1.87.0
      kernel/mm/address_space: Fix conditional compilation in test module
      kernel/lib: Use compact cfg_attr syntax for test inside svsm

Luigi Leonardi (5):
      virtio: put block code behind the new `block` feature
      verification: add missing SPDX header
      virtio: introduce MMIOSlots structure
      block: introduce BLOCK_DEVICE variable
      virtio: integrate MmioSlot infrastructure with block device subsystem

Peter Fang (5):
      kernel/igvm_params: Allow unaligned guest memory map
      igvmbuilder/ovmf: Use (start, size) for regions instead of (start, end)
      igvmbuilder/ovmf: Sanity check pre-validated regions
      igvmbuilder: Sanity check firmware regions
      kernel/config: Remove check_ovmf_regions()

Joerg Roedel (3):
      kernel: Fix nightly warnings
      kernel/vc: Fix nightly warnings
      COCONUT-SVSM Release 2026.01-devel

Stefano Garzarella (2):
      kernel: fix unused `slots` variable
      virtio/mmio: move fw_cfg check into probe_mmio_slots()

Vaishali Thakkar (2):
      sev/utils: Use iterator combinators for pvalidate and RMP revoke paths
      sev/utils: Improve error handling for pvalidate callers

Ziqiao Zhou (2):
      Upgrade verus lib to 2025-12-07-0054
      verify_external: Remove spec for From, Into, and Integer in verify_external

Geoffrey Ndu (1):
      kernel/protocol/attest: Add extended attestation support

---
