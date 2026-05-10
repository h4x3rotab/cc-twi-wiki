---
title: 'x86/msr: let paravirt inline rdmsr/wrmsr instructions'
date: 2025-05-06
last_reply: 2025-05-06
message_count: 3
participants: ['Juergen Gross', 'Kirill A. Shutemov']
---

## [1] Juergen Gross — 2025-05-06

When building a kernel with CONFIG_PARAVIRT_XXL the paravirt
infrastructure will always use functions for reading or writing MSRs,
even when running on bare metal.

Switch to inline RDMSR/WRMSR instructions in this case, reducing the
paravirt overhead.

In order to make this less intrusive, some further reorganization of
the MSR access helpers is done in the first 4 patches.

This series has been tested to work with Xen PV and on bare metal.

There has been another approach by Xin Li, which used dedicated #ifdef
and removing the MSR related paravirt hooks instead of just modifying
the paravirt code generation.

Please note that I haven't included the use of WRMSRNS or the
immediate forms of WRMSR and RDMSR, because I wanted to get some
feedback on my approach first. Enhancing paravirt for those cases
is not very complicated, as the main base is already prepared for
that enhancement.

This series is based on the x86/msr branch of the tip tree.

Juergen Gross (6):
  coco/tdx: Rename MSR access helpers
  x86/kvm: Rename the KVM private read_msr() function
  x86/msr: minimize usage of native_*() msr access functions
  x86/msr: Move MSR trace calls one function level up
  x86/paravirt: Switch MSR access pv_ops functions to instruction
    interfaces
  x86/msr: reduce number of low level MSR access helpers

 arch/x86/coco/tdx/tdx.c                   |   8 +-
 arch/x86/hyperv/ivm.c                     |   2 +-
 arch/x86/include/asm/kvm_host.h           |   2 +-
 arch/x86/include/asm/msr.h                | 116 ++++++++++-------
 arch/x86/include/asm/paravirt.h           | 152 ++++++++++++++--------
 arch/x86/include/asm/paravirt_types.h     |  13 +-
 arch/x86/include/asm/qspinlock_paravirt.h |   5 +-
 arch/x86/kernel/kvmclock.c                |   2 +-
 arch/x86/kernel/paravirt.c                |  26 +++-
 arch/x86/kvm/svm/svm.c                    |  16 +--
 arch/x86/kvm/vmx/vmx.c                    |   4 +-
 arch/x86/xen/enlighten_pv.c               |  60 ++++++---
 arch/x86/xen/pmu.c                        |   4 +-
 13 files changed, 262 insertions(+), 148 deletions(-)

---

## [2] Juergen Gross — 2025-05-06
*Subject: [PATCH 1/6] coco/tdx: Rename MSR access helpers*

In order to avoid a name clash with some general MSR access helpers
after a future MSR infrastructure rework, rename the TDX specific
helpers.

Signed-off-by: Juergen Gross <jgross@suse.com>
---
 arch/x86/coco/tdx/tdx.c | 8 ++++----
 1 file changed, 4 insertions(+), 4 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index edab6d6049be..49d79668f85f 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -428,7 +428,7 @@ static void __cpuidle tdx_safe_halt(void)
 	raw_local_irq_enable();
 }
 
-static int read_msr(struct pt_regs *regs, struct ve_info *ve)
+static int tdx_read_msr(struct pt_regs *regs, struct ve_info *ve)
 {
 	struct tdx_module_args args = {
 		.r10 = TDX_HYPERCALL_STANDARD,
@@ -449,7 +449,7 @@ static int read_msr(struct pt_regs *regs, struct ve_info *ve)
 	return ve_instr_len(ve);
 }
 
-static int write_msr(struct pt_regs *regs, struct ve_info *ve)
+static int tdx_write_msr(struct pt_regs *regs, struct ve_info *ve)
 {
 	struct tdx_module_args args = {
 		.r10 = TDX_HYPERCALL_STANDARD,
@@ -802,9 +802,9 @@ static int virt_exception_kernel(struct pt_regs *regs, struct ve_info *ve)
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

## [3] Kirill A. Shutemov — 2025-05-06
*Subject: Re: [PATCH 1/6] coco/tdx: Rename MSR access helpers*

On Tue, May 06, 2025 at 11:20:10AM +0200, Juergen Gross wrote:
> In order to avoid a name clash with some general MSR access helpers
> after a future MSR infrastructure rework, rename the TDX specific

Acked-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

---
