---
title: 'COCONUT-SVSM Development Release v2026.05-devel'
date: 2026-05-28
last_reply: 2026-05-28
message_count: 1
participants: ['Jörg Rödel']
---

## [1] Jörg Rödel — 2026-05-28

Hi all,

The month is almost over and it is time for a new COCONUT-SVSM development
release. This one turned out bigger than usual with 33 merges that brought in
91 non-merge commits from 9 contributors.

The changes include:

  - Boot flow: stage2 was removed and replaced by the new simpler boot/bldr
    loader. Build, xbuild, IGVM builder, configs, and launch paths now
    prefer/consume bldr.

  - Platform/CPU feature model: CPUID handling was routed through the platform
    abstraction, with a feature lookup table added for x2APIC, physical address
    size, Hyper-V discovery, CET, FPU/SSE, INVLPGB, C-bit, and related SNP
    features.

  - Attestation: Added vsock transport support with serial fallback, refactored
    aproxy transport handling, added read_exact / write_all helpers, and
    documented the vsock transport option.

  - Protocol hardening: Core and attestation protocol handlers gained stricter
    region validation, reserved-bit checks, request validation, mutually
    exclusive core calls, safer CAA/VMSA handling, and better guest fault
    forwarding.
  
  - Memory and guest handling: Shared pages are made private on SharedBox drop,
    guest memory reads now require FromBytes, VMSA registration checks
    overlaps, and CAA/VMSA tracking was tightened.

  - Virtio/vTPM fixes: Virtio owning queue validation now checks tokens and
    lengths before indexing/slicing. vTPM failure mode no longer returns
    uninitialized heap bytes.

  - ACPI/fw_cfg cleanup: Removed leftover fw_cfg-based ACPI/MADT logic and
    dropped the ACPI fuzz target.

  - Common architecture code: MSR, CR0/CR4, SEV status, x86, and APIC
    definitions moved into cpuarch.

  - Scripts and CI: QEMU launch no longer invokes sudo, gained --tcg, dropped
    the QEMU >= 11 nocc object path, improved test timeout/error reporting,
    fixed workflow triggers, added Verus caching, updated dependency review to
    Node 24, and dumps host dmesg on QEMU/test failures.

  - Verification: Documentation and workflows now reflect cargo-verus usage and
    Verus installation changes.

  - Misc fixes: ELF symbol/buffer bounds fixes, IPI race fixes, CPU vendor
    display, kernel version display during guest launch, and IGVM target VTL
    selection based on firmware presence.

As usual, the full shortlog since the last release is attached.

Have fun!

Regards,

	Joerg

Carlos L�pez (18):
      kernel: platform: add platform_method!() macro
      kernel: platform: do not take &self to query CPUID
      kernel: cpu/vc: simplify snp_cpuid()
      kernel: platform/snp: properly handle CPUID leaf 0xd
      kernel: platform: add default CPUID implementation
      kernel: always route CPUID through the platform abstraction
      kernel: cpu/features: create feature lookup table
      kernel: cet: make CET discovery into a feature
      kernel: cpu/sse: make FPU feature detection into a feature
      kernel: hyperv: make Hyper-V discovery into a feature
      kernel: sev/tlb: make INVLPGB max entry detection into a feature
      kernel: platform: make phys address sizes into a feature
      kernel: platform: make x2apic into a feature
      kernel: platform: make platform statics read-only after init
      kernel: platform: remove trivial FIXME for SvsmPlatformCell
      kernel: platform/snp: make C-bit into a feature
      kernel: platform/snp: get physical address size through CPU features
      kernel: platform: remove setup_guest_host_comm()

Joerg Roedel (23):
      kernel/guestmem: Require FromBytes for read_from_guest()
      kernel/mm: Make all pages private when SharedBox is dropped
      kernel/protocols: Forward GuestPtr faults to the guest
      kernel/protocols: Make sure memory regions are valid for attestation protocol
      kernel/greq: Round extended guest request size up to page-size
      kernel/percpu: Always page_align CAA address before mapping
      kernel/percpu: Track CAA address in PERCPU_VMSAS
      kernel/percpu: Check for region overlap in VMSA registration
      kernel/percpu: Return SvsmError from PERCPU_VMSAS.unregister()
      kernel/snp: Register initial guest VMSA
      kernel/protocols: Check for valid regions in core_pvalidate
      kernel/protocols: Update PERCPU_VMSAS in core_remap_caa()
      kernel/protocols: Do not deregister VMSA before updating RMP state
      kernel/protocols: Check for reserved bits in core_pvalidate_one()
      kernel/protocols: Check for region validity in core_pvalidate_one()
      kernel/protocols: Check whether attestation requests are valid
      kernel/protocols: Remove try_from_as_ref() from attestation structures
      kernel/protocols: Use valid_phys_region() where needed
      kernel/protocols: Make some core protocol calls mutually exclusive
      kernel/protocols: Use MemoryRegion::checked_new() in core protocol handlers
      Elf: Make sure buffer length is multiple of 16
      Elf: Do not read symbols beyond symbol table
      COCONUT-SVSM Release 2026.05-devel

Jon Lange (22):
      cpuarch: move MSR and CR0/CR4 definitions to common crate
      igvmbuilder: reshape the initial low-mem page tables
      bldr: implement a simpler boot loader
      igvmbuild: support bldr
      xbuild: support bldr
      build: consume bldr instead of stage2
      Merge pull request #1029 from msft-jlange/bldr
      svsm: prefer bldr to stage2
      xbuild: remove stage2 support
      igvmbuilder: remove support for stage2
      stage2: remove stage2
      bldr: clear temporary mapping PTEs after use
      Merge pull request #1064 from MelodyHuibo/init_vgif
      Merge pull request #1068 from 00xc/platform/fixme
      error: avoid `SvsmReqError` outside of SVSM-specific paths
      svsm: detect and display CPU vendor
      scripts: display kernel version when launching guest
      cpu/ipi: fix race conditions
      Merge pull request #1076 from msft-jlange/cpu_vendor
      Merge pull request #1077 from msft-jlange/kernel_info
      igvmbuilder: configure target VTL based on the presence of firmware
      cpuarch: move APIC constants to a common location

J�rg R�del (24):
      Merge pull request #1048 from luigix25/fix_ci
      Merge pull request #1052 from n-ramacciotti/ci/remove_unmaintained_action
      Merge pull request #1054 from msft-jlange/bldr_ptes
      Merge pull request #1043 from mvanhorn/feat/1042-tools-check
      Merge pull request #1050 from n-ramacciotti/ci/simplify-test-in-svsm
      Merge pull request #1053 from msft-jlange/remove_stage2
      Merge pull request #1055 from n-ramacciotti/ci/update_dep_review_node_24
      Merge pull request #1030 from 00xc/platform/cpuid-v2
      Merge pull request #1059 from ziqiaozhou/fix-broken-alloc-proof
      Merge pull request #1067 from 00xc/ro-after-init
      Merge pull request #1070 from MelodyHuibo/enable_alternate_injection
      Merge pull request #1071 from 00xc/platform/remove-host-comm
      Merge pull request #1072 from stefano-garzarella/virtio-fix-owning-pop
      Merge pull request #1074 from stefano-garzarella/fix-tpm-allocation
      Merge pull request #1078 from msft-jlange/ipi_fix
      Merge pull request #1038 from ziqiaozhou/cargo-verus
      Merge pull request #1079 from stefano-garzarella/verus-cache
      Merge pull request #1080 from stefano-garzarella/ci-fix-verification-label-trigger
      Merge pull request #1082 from stefano-garzarella/ci-dmesg
      Merge pull request #1066 from luigix25/remove_sudo
      Merge pull request #1090 from luigix25/fw_cfg_cleanup
      Merge pull request #1085 from msft-jlange/igvm_vtl
      Merge pull request #1087 from msft-jlange/cpu_apic
      Merge pull request #1069 from 00xc/platform/missing-features

Luigi Leonardi (14):
      github/workflows: add apt update before apt install in publish-docs
      io: add `read_exact` and `write_all` to Read and Write trait
      aproxy: use read/write traits
      aproxy: factor out accept loop to a separate function
      aproxy: enable vsock for attestation
      kernel/attest: abstract transport implementation
      kernel/attest: switch to write_all/read_exact
      kernel/attest: add vsock transport with serial fallback
      Documentation/ATTESTATION: document vsock transport option
      scripts/launch_guest: drop nocc object for QEMU >= 11.0
      scripts/launch_guest: add --tcg option to use TCG acceleration
      github/workflows: set up /dev/kvm permissions
      scripts/launch_guest: remove sudo from QEMU invocation
      acpi: remove fw_cfg-based ACPI/MADT leftover

Matt Van Horn (1):
      testing/scripts: Check required host tools before launching guest

Melody Wang (2):
      cpu: Make sure guest's GIF is set
      boot: Allow Alternate Injection to be configured via boot params

Nicola Ramacciotti (5):
      github/workflows: Remove unmaintained action
      scripts/test-in-svsm: Print exit code when failing
      scripts/test-in-svsm: Add optional timeout handling
      github/workflows: Use the test-in-svsm script directly
      github/workflows: update dependency review to node 24

Stefano Garzarella (10):
      Merge pull request #879 from luigix25/add_attestation_to_vsock
      Merge pull request #1058 from luigix25/qemu_11_launch
      Merge pull request #1065 from msft-jlange/svsm_req_error
      virtio-drivers: queue/owning: validate the token before indexing buffer table
      virtio-drivers: queue/owning: validate len before slicing buffer
      kernel/vtpm: fix uninitialized heap bytes returned in TPM failure mode
      github/manual-verify: fix triggering on 'verification' label
      github/manual-verify: cache verus toolchain
      Merge pull request #1073 from joergroedel/fixes
      github/qemu: dump host kernel messages on QEMU or test failure

Ziqiao Zhou (5):
      mm/alloc.verus: update phys_to_virt proof after stage2 removal
      verification: Support Verus's verita test via cargo-verus.
      scripts: Update vsinstall.sh to directly install verus.
      workflow: Revert "github/manual-verify: check cargo-v output for errors"
      doc: Update verification.md to reflect the use of cargo-verus

---
