---
title: 'COCONUT-SVSM Development Release v2026.04-devel'
date: 2026-04-29
last_reply: 2026-04-29
message_count: 1
participants: ['Jörg Rödel']
---

## [1] Jörg Rödel — 2026-04-29

Hi all,

It is my pleasure to announce the COCONUT-SVSM development release
v2026.04-devel. It features 75 non-merge commits since the last release, the
highlights are:

  - Added initial VirtIO-VSOCK support in SVSM.

  - Reworked task scheduling and execution control.

  - Refactored virtual memory and page fault handling.

  - Added support for partial TLB flushes, including range-based CPU TLB
    flushing.

  - Updated the IGVM/stage2 boot flow.

  - Expanded kernel test coverage, including compile-time layout assertions
    plus simple stacktrace and symbol-resolution tests.
  
  - Refreshed documentation, especially around attestation, installation
    requirements, and debugging guidance.

All the details are in the shortlog below. A big thanks again to the
COCONUT-SVSM community for all the effort in driving the project forward!

Best,

	Joerg

Shortlog:

Carlos L�pez (32):
      kernel: debug/symbols: fix symtab slice length
      kernel: debug/symbols: add a simple symbol resolution test
      kernel: debug/stacktrace: add a simple stacktrace test
      kernel: cpu/tlb: rename TlbFlushScope::flush_all() to flush_all_cpus()
      kernel: cpu/tlb: allow specifying address ranges in TlbFlushScope
      kernel: cpu/tlb: support partial TLB flushes
      kernel: sev/tlb: strongly type INVLPGB RAX
      kernel: sev/tlb: merge flush_tlb_global_sync and flush_tlb_sync()
      kernel: sev/tlb: hide helper TLB functions
      kernel: sev/tlb: support partial TLB flushes
      kernel: cpu/tlb: expose partial TLB flush functions
      kernel: protocols/core: flush individual PVALIDATE entries
      kernel: sev/tlb: add additional inline assembly flags
      kernel: tests: convert struct layout tests to compile-time assertions
      kernel: mm/address_space: const-compute temporary mapping area size
      kernel: cpu/percpu: initialize vrange allocators in initialize_vm_ranges()
      kernel: mm/vm: remove Mapping type
      kernel: mm/vm/range: remove mapping in one go
      kernel: mm/vm/mapping: remove incorrect documentation
      kernel: mm/vm/range: make VMR::virt_range() return a MemoryRegion
      kernel: task: remove unnecessary unwrap()
      kernel: task: remove unused Task::handle_pf()
      kernel: mm/vm/range: always populate page table as part of #PF handling
      kernel: mm/vm: make handle_page_fault() take &self
      kernel: mm/vm: rewire page faults
      kernel: task/mm: ensure VMR addresses are VMR_GRANULE-aligned
      kernel: mm/vm: check VMR invariants upfront
      libtcgtpm: do not link libcrt for userspace targets
      xbuild: use workspace dependencies
      packit: update to latest commit
      xbuild: use packit as a library
      cpuarch: add CPUID page accessors

Gerd Hoffmann (1):
      libtcgtpm: remove libtcgtpm.a

Joerg Roedel (1):
      COCONUT-SVSM Release 2026.04-devel

Jon Lange (12):
      bootimg: implement `Error` for boot image errors
      igvmbuilder: use `Error::Display` for error messages
      stage2: build boot image in igvmbuilder
      stage2: remove secrets page from stage2
      svsm: validate lowmem in kernel if not done in stage2
      igvmbuilder: define abstraction for IGVM parameter layout
      igvmbuilder: make stage2 optional
      task: remove lock around `TaskSchedState`
      task: enforce mutual exclusion of execution
      task: add task termination test
      task/schedule: modify task rescheduling
      task/schedule: permit scheduler callers to disable interrupts

Luigi Leonardi (14):
      kernel: introduce VsockTransport trait for driver abstraction
      Revert "virtio: remove vsock support"
      virtio-drivers/socket: apply clippy lints
      virtio-drivers/connectionmanager: track connection established state
      virtio-drivers/connectionmanager: reject operations after peer shutdown
      virtio-drivers/connectionmanager: add `is_local_port_used`
      kernel/vsock: introduce virtio-vsock support
      kernel/vsock: introduce VsockStream
      scripts/launch_guest: add vsock to launch_guest
      kernel/vsock: add in-svsm tests for VsockStream
      Makefile: fix clippy with CARGO_HACK
      kernel/vsock: fix SVSM crash in VsockStream when device is not available
      Documentation/ATTESTATION: fix wrong protocol and path in example description
      Documentation/ATTESTATION: correct wrong parameter name

Nicola Ramacciotti (8):
      docs: Move debugging information to developer section
      docs: Improve debugging guide
      docs: Clarify gdb usage
      gitignore: Avoid tracking gdb_history
      github/workflows: Update some actions to Node.js 24
      github/workflows: Fix cargo audit installation
      github/workflows: Unify and always run both compliance checks
      github/workflows: enable vhost support in QEMU build and install netcat

Nihal (1):
      github/workflows: cargo audit

Oliver Steffen (1):
      kernel: Verify ACPI table checksum

Stefano Garzarella (3):
      kernel/ghcb: add missing register offset assertions
      docs/INSTALL: update guest image requirement
      github/workflows: drop explicit checkout ref in PR workflows

Tanya Agarwal (1):
      Actions: add SPDX header check script

Vaishali Thakkar (1):
      igvmbuilder: remove obsolete debug_swap CLI options

---
