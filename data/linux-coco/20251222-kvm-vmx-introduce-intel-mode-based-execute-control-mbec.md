---
title: 'KVM: VMX: Introduce Intel Mode-Based Execute Control (MBEC)'
date: 2025-12-22
last_reply: 2025-12-22
message_count: 2
participants: ['Jon Kohler']
---

## [1] Jon Kohler — 2025-12-22

## Summary
This series introduces support for Intel Mode-Based Execute Control
(MBEC) to KVM and nested VMX virtualization. By exposing MBEC to L2
guests, it enables a dramatic reduction in VMexits (up to 24x) for
Windows guests running with Hypervisor-Protected Code Integrity (HVCI),
significantly improving virtualization performance.

## What?
Intel MBEC is a hardware feature, introduced in the Kabylake
generation, that allows for more granular control over execution
permissions. MBEC enables the separation and tracking of execution
permissions for supervisor (kernel) and user-mode code. It is used as
an accelerator for Microsoft's Memory Integrity [1] (also known as
hypervisor-protected code integrity or HVCI).

## Why?
The primary reason for this feature is performance.

Without hardware-level MBEC, enabling Windows HVCI runs a 'software
MBEC' known as Restricted User Mode, which imposes a runtime overhead
due to increased state transitions between the guest's L2 root
partition and the L2 secure partition for running kernel mode code
integrity operations.

In practice, this results in a significant number of exits. For
example, playing a YouTube video within the Edge Browser produces
roughly 1.2 million VMexits/second across an 8 vCPU Windows 11 guest.

Most of these exits are VMREAD/VMWRITE operations, which can be
emulated with Enlightened VMCS (eVMCS). However, even with eVMCS, this
configuration still produces around 200,000 VMexits/second.

With MBEC exposed to the L1 Windows Hypervisor, the same scenario
results in approximately 50,000 VMexits/second, a *24x* reduction from
the baseline.

Not a typo, 24x reduction in VMexits.

## How?
This series implements core KVM support for exposing the MBEC bit in
secondary execution controls (bit 22) to L2 nested guests, based on
configuration from user space. The inspiration for this series started
with Mickaël's series for Heki [3], where we've extracted, refactored,
and completely reworked the MBEC-specific use case to be general-purpose.

MBEC splits the EPT execute permission into two independent bits. When
secondary execution control bit 22 ("mode-based execute control for EPT")
is set for the L2 guest, EPT PTE bit 2 controls execute permission for
supervisor-mode linear addresses, while bit 10 controls execute permission
for user-mode linear addresses.

The semantics for EPT violation qualifications also change when MBEC
is enabled, with bit 5 reflecting supervisor/kernel mode execute
permissions and bit 6 reflecting user mode execute permissions.
This ultimately serves to expose this feature to the L1 hypervisor,
which consumes MBEC and informs the L2 partitions not to use the
software MBEC by removing bit 13 in 0x40000004 EAX [4].

## Where?
The implementation spans multiple components:
- KVM MMU code: Teach the shadow MMU about MBEC execution modes
- KVM VMX code: Handle EPT violations and VMX controls for MBEC
- User space VMM: Pass secondary execution control bit 22 to enable MBEC
  for L2 guests 

A trivial enablement patch for QEMU enablement is available [5].

A GitHub mirror of this series is also available [6].

## Performance Impact
Testing shows dramatic performance improvements for Windows HVCI workloads:
- 24x reduction in VMexits for typical browser usage
- From ~1.2M VMexits/second to ~50K VMexits/second
- Enables hardware acceleration of Windows Memory Integrity

The implementation adds minimal overhead when MBEC is not used, especially
when combined with EVMCS to elide nested VMREAD/VMWRITE vmexits.

## Testing
Initial testing has been on done on 6.18-based code with:
  Guests
    - Windows 11 24H2 26100.2894
    - Windows Server 2025 24H2 26100.2894
    - Windows Server 2022 W1H2 20348.825
  Processors:
    - Intel Skylake 6154
    - Intel Sapphire Rapids 6444Y
  Unit Tests
    - KVM Unit Tests [7]

## Changelog
RFC -> V1:
- Fix incorrect bit reference in cover letter (Adrian-Ken)
- Remove module parameters (Sean, Amit)
- Remove redundant arch-level tracking boolean (Sean)
- Update is_present_gpte to account for MBEC bit 10 (Chao)
- Move MBEC enablement tracking to MMU role (Sean)
- Restrict MBEC advertisement to nested virtualization only (Sean)
- Consolidate preparatory patches into main implementation (Sean)
- Add permission mask refactoring preparation (Sean)
- Implement TDP-aware executable permission checking (Sean)

[1] https://learn.microsoft.com/en-us/windows/security/hardware-security/enable-virtualization-based-protection-of-code-integrity
[2] https://learn.microsoft.com/en-us/virtualization/hyper-v-on-windows/tlfs/nested-virtualization#enlightened-vmcs-intel
[3] https://patchwork.kernel.org/project/kvm/patch/20231113022326.24388-6-mic@digikod.net/
[4] https://learn.microsoft.com/en-us/virtualization/hyper-v-on-windows/tlfs/feature-discovery#implementation-recommendations---0x40000004
[5] https://github.com/JonKohler/qemu/tree/mbec-v1
[6] https://github.com/JonKohler/linux/tree/mbec-v1-6.18
[7] https://github.com/JonKohler/kvm-unit-tests/tree/mbec-v1

Cc: "Adrian-Ken Rueegsegger" <ken@codelabs.ch>
Cc: "Alexander Grest" <Alexander.Grest@microsoft.com>
Cc: "Chao Gao" <chao.gao@intel.com>
Cc: "Madhavan T . Venkataraman" <madvenka@linux.microsoft.com>
Cc: "Mickaël Salaün" <mic@digikod.net>
Cc: "Nicolas Saenz Julienne" <nsaenz@amazon.es>
Cc: "Tao Su" <tao1.su@linux.intel.com>
Cc: "Xiaoyao Li" <xiaoyao.li@intel.com>
Cc: "Zhao Liu" <zhao1.liu@intel.com>

Jon Kohler (8):
  KVM: TDX/VMX: rework EPT_VIOLATION_EXEC_FOR_RING3_LIN into PROT_MASK
  KVM: x86/mmu: remove SPTE_PERM_MASK
  KVM: x86/mmu: adjust MMIO generation bit allocation and allowed mask
  KVM: x86/mmu: update access permissions from ACC_ALL to ACC_RWX
  KVM: x86/mmu: bootstrap support for Intel MBEC
  KVM: VMX: enhance EPT violation handler for MBEC
  KVM: VMX: allow MBEC with EVMCS
  KVM: nVMX: advertise MBEC and setup mmu has_mbec

 Documentation/virt/kvm/x86/mmu.rst |  9 +++-
 arch/x86/include/asm/kvm_host.h    | 19 +++++---
 arch/x86/include/asm/vmx.h         |  9 +++-
 arch/x86/kvm/mmu.h                 | 15 +++++-
 arch/x86/kvm/mmu/mmu.c             | 74 ++++++++++++++++++++++++++--
 arch/x86/kvm/mmu/mmutrace.h        | 23 ++++++---
 arch/x86/kvm/mmu/paging_tmpl.h     | 24 ++++++---
 arch/x86/kvm/mmu/spte.c            | 65 +++++++++++++++++++------
 arch/x86/kvm/mmu/spte.h            | 78 ++++++++++++++++++++++++------
 arch/x86/kvm/mmu/tdp_mmu.c         | 12 +++--
 arch/x86/kvm/vmx/capabilities.h    |  6 +++
 arch/x86/kvm/vmx/common.h          | 15 ++++--
 arch/x86/kvm/vmx/hyperv_evmcs.h    |  1 +
 arch/x86/kvm/vmx/nested.c          |  6 +++
 arch/x86/kvm/vmx/tdx.c             |  2 +-
 arch/x86/kvm/vmx/vmx.c             | 10 +++-
 arch/x86/kvm/vmx/vmx.h             |  1 +
 17 files changed, 301 insertions(+), 68 deletions(-)

---

## [2] Jon Kohler — 2025-12-22
*Subject: [PATCH 1/8] KVM: TDX/VMX: rework EPT_VIOLATION_EXEC_FOR_RING3_LIN into PROT_MASK*

EPT exit qualification bit 6 is used when mode-based execute control
is enabled, and reflects user executable addresses. Rework name to
reflect the intention and add to EPT_VIOLATION_PROT_MASK, which allows
simplifying the return evaluation in
tdx_is_sept_violation_unexpected_pending a pinch.

Rework handling in __vmx_handle_ept_violation to unconditionally clear
EPT_VIOLATION_PROT_USER_EXEC until MBEC is implemented, as suggested by
Sean [1].

Note: Intel SDM Table 29-7 defines bit 6 as:
  If the “mode-based execute control” VM-execution control is 0, the
  value of this bit is undefined. If that control is 1, this bit is the
  logical-AND of bit 10 in the EPT paging-structure entries used to
  translate the guest-physical address of the access causing the EPT
  violation. In this case, it indicates whether the guest-physical
  address was executable for user-mode linear addresses.

[1] https://lore.kernel.org/all/aCJDzU1p_SFNRIJd@google.com/

Suggested-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Jon Kohler <jon@nutanix.com>
---
 arch/x86/include/asm/vmx.h | 5 +++--
 arch/x86/kvm/vmx/common.h  | 9 +++++++--
 arch/x86/kvm/vmx/tdx.c     | 2 +-
 3 files changed, 11 insertions(+), 5 deletions(-)

diff --git a/arch/x86/include/asm/vmx.h b/arch/x86/include/asm/vmx.h
index c85c50019523..de3abec84fe5 100644
--- a/arch/x86/include/asm/vmx.h
+++ b/arch/x86/include/asm/vmx.h
@@ -596,10 +596,11 @@ enum vm_entry_failure_code {
 #define EPT_VIOLATION_PROT_READ		BIT(3)
 #define EPT_VIOLATION_PROT_WRITE	BIT(4)
 #define EPT_VIOLATION_PROT_EXEC		BIT(5)
-#define EPT_VIOLATION_EXEC_FOR_RING3_LIN BIT(6)
+#define EPT_VIOLATION_PROT_USER_EXEC	BIT(6)
 #define EPT_VIOLATION_PROT_MASK		(EPT_VIOLATION_PROT_READ  | \
 					 EPT_VIOLATION_PROT_WRITE | \
-					 EPT_VIOLATION_PROT_EXEC)
+					 EPT_VIOLATION_PROT_EXEC  | \
+					 EPT_VIOLATION_PROT_USER_EXEC)
 #define EPT_VIOLATION_GVA_IS_VALID	BIT(7)
 #define EPT_VIOLATION_GVA_TRANSLATED	BIT(8)
 
diff --git a/arch/x86/kvm/vmx/common.h b/arch/x86/kvm/vmx/common.h
index 412d0829d7a2..adf925500b9e 100644
--- a/arch/x86/kvm/vmx/common.h
+++ b/arch/x86/kvm/vmx/common.h
@@ -94,8 +94,13 @@ static inline int __vmx_handle_ept_violation(struct kvm_vcpu *vcpu, gpa_t gpa,
 	/* Is it a fetch fault? */
 	error_code |= (exit_qualification & EPT_VIOLATION_ACC_INSTR)
 		      ? PFERR_FETCH_MASK : 0;
-	/* ept page table entry is present? */
-	error_code |= (exit_qualification & EPT_VIOLATION_PROT_MASK)
+	/*
+	 * ept page table entry is present?
+	 * note: unconditionally clear USER_EXEC until mode-based
+	 * execute control is implemented
+	 */
+	error_code |= (exit_qualification &
+		       (EPT_VIOLATION_PROT_MASK & ~EPT_VIOLATION_PROT_USER_EXEC))
 		      ? PFERR_PRESENT_MASK : 0;
 
 	if (exit_qualification & EPT_VIOLATION_GVA_IS_VALID)
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 0a49c863c811..61185c30a40e 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1922,7 +1922,7 @@ static inline bool tdx_is_sept_violation_unexpected_pending(struct kvm_vcpu *vcp
 	if (eeq_type != TDX_EXT_EXIT_QUAL_TYPE_PENDING_EPT_VIOLATION)
 		return false;
 
-	return !(eq & EPT_VIOLATION_PROT_MASK) && !(eq & EPT_VIOLATION_EXEC_FOR_RING3_LIN);
+	return !(eq & EPT_VIOLATION_PROT_MASK);
 }
 
 static int tdx_handle_ept_violation(struct kvm_vcpu *vcpu)

---
