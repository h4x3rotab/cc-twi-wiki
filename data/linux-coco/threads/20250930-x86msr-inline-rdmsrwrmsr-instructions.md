---
title: 'x86/msr: Inline rdmsr/wrmsr instructions'
date: 2025-09-30
last_reply: 2025-09-30
message_count: 4
participants: ['Juergen Gross', 'Kiryl Shutsemau', 'H. Peter Anvin']
---

## [1] Juergen Gross — 2025-09-30

When building a kernel with CONFIG_PARAVIRT_XXL the paravirt
infrastructure will always use functions for reading or writing MSRs,
even when running on bare metal.

Switch to inline RDMSR/WRMSR instructions in this case, reducing the
paravirt overhead.

In order to make this less intrusive, some further reorganization of
the MSR access helpers is done in the first 5 patches.

The next 5 patches are converting the non-paravirt case to use direct
inlining of the MSR access instructions, including the WRMSRNS
instruction and the immediate variants of RDMSR and WRMSR if possible.

Patch 11 removes the PV hooks for MSR accesses and implements the
Xen PV cases via calls depending on X86_FEATURE_XENPV, which results
in runtime patching those calls away for the non-XenPV case.

Patch 12 is a final little cleanup patch.

This series has been tested to work with Xen PV and on bare metal.

This series is inspired by Xin Li, who used a similar approach, but
(in my opinion) with some flaws. Originally I thought it should be
possible to use the paravirt infrastructure, but this turned out to be
rather complicated, especially for the Xen PV case in the *_safe()
variants of the MSR access functions.

Changes since V1:
- Use Xin Li's approach for inlining
- Several new patches

Juergen Gross (9):
  coco/tdx: Rename MSR access helpers
  x86/sev: replace call of native_wrmsr() with native_wrmsrq()
  x86/kvm: Remove the KVM private read_msr() function
  x86/msr: minimize usage of native_*() msr access functions
  x86/msr: Move MSR trace calls one function level up
  x86/msr: Use the alternatives mechanism for WRMSR
  x86/msr: Use the alternatives mechanism for RDMSR
  x86/paravirt: Don't use pv_ops vector for MSR access functions
  x86/msr: Reduce number of low level MSR access helpers

Xin Li (Intel) (3):
  x86/cpufeatures: Add a CPU feature bit for MSR immediate form
    instructions
  x86/opcode: Add immediate form MSR instructions
  x86/extable: Add support for immediate form MSR instructions

 arch/x86/coco/tdx/tdx.c               |   8 +-
 arch/x86/hyperv/ivm.c                 |   2 +-
 arch/x86/include/asm/cpufeatures.h    |   1 +
 arch/x86/include/asm/fred.h           |   2 +-
 arch/x86/include/asm/kvm_host.h       |  10 -
 arch/x86/include/asm/msr.h            | 409 +++++++++++++++++++-------
 arch/x86/include/asm/paravirt.h       |  67 -----
 arch/x86/include/asm/paravirt_types.h |  13 -
 arch/x86/include/asm/sev-internal.h   |   7 +-
 arch/x86/kernel/cpu/scattered.c       |   1 +
 arch/x86/kernel/kvmclock.c            |   2 +-
 arch/x86/kernel/paravirt.c            |   5 -
 arch/x86/kvm/svm/svm.c                |  16 +-
 arch/x86/kvm/vmx/vmx.c                |   4 +-
 arch/x86/lib/x86-opcode-map.txt       |   5 +-
 arch/x86/mm/extable.c                 |  39 ++-
 arch/x86/xen/enlighten_pv.c           |  24 +-
 arch/x86/xen/pmu.c                    |   5 +-
 tools/arch/x86/lib/x86-opcode-map.txt |   5 +-
 19 files changed, 383 insertions(+), 242 deletions(-)

---

## [2] Juergen Gross — 2025-09-30
*Subject: [PATCH v2 01/12] coco/tdx: Rename MSR access helpers*

In order to avoid a name clash with some general MSR access helpers
after a future MSR infrastructure rework, rename the TDX specific
helpers.

Signed-off-by: Juergen Gross <jgross@suse.com>
---
 arch/x86/coco/tdx/tdx.c | 8 ++++----
 1 file changed, 4 insertions(+), 4 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 7b2833705d47..500166c1a161 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -468,7 +468,7 @@ static void __cpuidle tdx_safe_halt(void)
 	raw_local_irq_enable();
 }
 
-static int read_msr(struct pt_regs *regs, struct ve_info *ve)
+static int tdx_read_msr(struct pt_regs *regs, struct ve_info *ve)
 {
 	struct tdx_module_args args = {
 		.r10 = TDX_HYPERCALL_STANDARD,
@@ -489,7 +489,7 @@ static int read_msr(struct pt_regs *regs, struct ve_info *ve)
 	return ve_instr_len(ve);
 }
 
-static int write_msr(struct pt_regs *regs, struct ve_info *ve)
+static int tdx_write_msr(struct pt_regs *regs, struct ve_info *ve)
 {
 	struct tdx_module_args args = {
 		.r10 = TDX_HYPERCALL_STANDARD,
@@ -842,9 +842,9 @@ static int virt_exception_kernel(struct pt_regs *regs, struct ve_info *ve)
 	case EXIT_REASON_HLT:
 		return handle_halt(ve);
 	case EXIT_REASON_MSR_READ:
-		return read_msr(regs, ve);
+		return tdx_read_msr(regs, ve);
 	case EXIT_REASON_MSR_WRITE:
-		return write_msr(regs, ve);
+		return tdx_write_msr(regs, ve);
 	case EXIT_REASON_CPUID:
 		return handle_cpuid(regs, ve);
 	case EXIT_REASON_EPT_VIOLATION:

---

## [3] Kiryl Shutsemau — 2025-09-30
*Subject: Re: [PATCH v2 01/12] coco/tdx: Rename MSR access helpers*

On Tue, Sep 30, 2025 at 09:03:45AM +0200, Juergen Gross wrote:
> In order to avoid a name clash with some general MSR access helpers
> after a future MSR infrastructure rework, rename the TDX specific

Reviewed-by: Kiryl Shutsemau <kas@kernel.org>

---

## [4] H. Peter Anvin — 2025-09-30
*Subject: Re: [PATCH v2 00/12] x86/msr: Inline rdmsr/wrmsr instructions*

On 2025-09-30 00:03, Juergen Gross wrote:
> When building a kernel with CONFIG_PARAVIRT_XXL the paravirt
> infrastructure will always use functions for reading or writing MSRs,

Looks good to me.

(I'm not at all surprised that paravirt_ops didn't do the job. Both I and Xin
had come to the same conclusion.)


Reviewed-by: H. Peter Anvin (Intel) <hpa@zytor.com>

---
