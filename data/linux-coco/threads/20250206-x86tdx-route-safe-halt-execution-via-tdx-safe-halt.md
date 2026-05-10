---
title: 'x86/tdx: Route safe halt execution via tdx_safe_halt()'
date: 2025-02-06
last_reply: 2025-02-11
message_count: 8
participants: ['Vishal Annapurve', 'Sean Christopherson', 'Kirill A. Shutemov', 'Dave Hansen']
---

## [1] Vishal Annapurve — 2025-02-06

Direct HLT instruction execution causes #VEs for TDX VMs which is routed
to hypervisor via TDCALL. safe_halt() routines execute HLT in STI-shadow
so IRQs need to remain disabled until the TDCALL to ensure that pending
IRQs are correctly treated as wake events. So "sti;hlt" sequence needs to
be replaced with "TDCALL; raw_local_irq_enable()" for TDX VMs.

Commit bfe6ed0c6727 ("x86/tdx: Add HLT support for TDX guests")
prevented the idle routines from using "sti;hlt". But it missed the
paravirt routine which can be reached like this as an example:
        acpi_safe_halt() =>
        raw_safe_halt()  =>
        arch_safe_halt() =>
        irq.safe_halt()  =>
        pv_native_safe_halt()

Modify tdx_safe_halt() to implement the sequence "TDCALL;
raw_local_irq_enable()" and invoke tdx_halt() from idle routine which just
executes TDCALL without changing state of interrupts.

If CONFIG_PARAVIRT_XXL is disabled, "sti;hlt" sequences can still get
executed from TDX VMs via paths like:
        acpi_safe_halt() =>
        raw_safe_halt()  =>
        arch_safe_halt() =>
	native_safe_halt()
There is a long term plan to fix these paths by carving out
irq.safe_halt() outside paravirt framework.

Cc: stable@vger.kernel.org
Fixes: bfe6ed0c6727 ("x86/tdx: Add HLT support for TDX guests")
Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>@linux.intel.com>
Signed-off-by: Vishal Annapurve <vannapurve@google.com>
---
Changes since V2:
1) Addressed comments from Dave H and Kirill S.

V2: https://lore.kernel.org/lkml/20250129232525.3519586-1-vannapurve@google.com/

 arch/x86/coco/tdx/tdx.c    | 18 +++++++++++++++++-
 arch/x86/include/asm/tdx.h |  2 +-
 arch/x86/kernel/process.c  |  2 +-
 3 files changed, 19 insertions(+), 3 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 32809a06dab4..5e68758666a4 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -14,6 +14,7 @@
 #include <asm/ia32.h>
 #include <asm/insn.h>
 #include <asm/insn-eval.h>
+#include <asm/paravirt_types.h>
 #include <asm/pgtable.h>
 #include <asm/set_memory.h>
 #include <asm/traps.h>
@@ -398,7 +399,7 @@ static int handle_halt(struct ve_info *ve)
 	return ve_instr_len(ve);
 }
 
-void __cpuidle tdx_safe_halt(void)
+void __cpuidle tdx_halt(void)
 {
 	const bool irq_disabled = false;
 
@@ -409,6 +410,12 @@ void __cpuidle tdx_safe_halt(void)
 		WARN_ONCE(1, "HLT instruction emulation failed\n");
 }
 
+static void __cpuidle tdx_safe_halt(void)
+{
+	tdx_halt();
+	raw_local_irq_enable();
+}
+
 static int read_msr(struct pt_regs *regs, struct ve_info *ve)
 {
 	struct tdx_module_args args = {
@@ -1109,6 +1116,15 @@ void __init tdx_early_init(void)
 	x86_platform.guest.enc_kexec_begin	     = tdx_kexec_begin;
 	x86_platform.guest.enc_kexec_finish	     = tdx_kexec_finish;
 
+#ifdef CONFIG_PARAVIRT_XXL
+	/*
+	 * Avoid the literal hlt instruction in TDX guests. hlt will
+	 * induce a #VE in the STI-shadow which will enable interrupts
+	 * in a place where they are not wanted.
+	 */
+	pv_ops.irq.safe_halt = tdx_safe_halt;
+#endif
+
 	/*
 	 * TDX intercepts the RDMSR to read the X2APIC ID in the parallel
 	 * bringup low level code. That raises #VE which cannot be handled
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index b4b16dafd55e..393ee2dfaab1 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -58,7 +58,7 @@ void tdx_get_ve_info(struct ve_info *ve);
 
 bool tdx_handle_virt_exception(struct pt_regs *regs, struct ve_info *ve);
 
-void tdx_safe_halt(void);
+void tdx_halt(void);
 
 bool tdx_early_handle_ve(struct pt_regs *regs);
 
diff --git a/arch/x86/kernel/process.c b/arch/x86/kernel/process.c
index 6da6769d7254..d11956a178df 100644
--- a/arch/x86/kernel/process.c
+++ b/arch/x86/kernel/process.c
@@ -934,7 +934,7 @@ void __init select_idle_routine(void)
 		static_call_update(x86_idle, mwait_idle);
 	} else if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST)) {
 		pr_info("using TDX aware idle routine\n");
-		static_call_update(x86_idle, tdx_safe_halt);
+		static_call_update(x86_idle, tdx_halt);
 	} else {
 		static_call_update(x86_idle, default_idle);
 	}

---

## [2] Vishal Annapurve — 2025-02-06
*Subject: [PATCH V3 2/2] x86/tdx: Emit warning if IRQs are enabled during HLT
 #VE handling*

Direct HLT instruction execution causes #VEs for TDX VMs which is routed
to hypervisor via TDCALL. safe_halt() routines execute HLT in STI-shadow
so IRQs need to remain disabled until the TDCALL to ensure that pending
IRQs are correctly treated as wake events.

Emit warning and fail emulation if IRQs are enabled during HLT #VE handling
to avoid running into scenarios where IRQ wake events are lost resulting in
indefinite HLT execution times.

Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>@linux.intel.com>
Signed-off-by: Vishal Annapurve <vannapurve@google.com>
---
 arch/x86/coco/tdx/tdx.c | 5 +++++
 1 file changed, 5 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 5e68758666a4..ed6738ea225c 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -393,6 +393,11 @@ static int handle_halt(struct ve_info *ve)
 {
 	const bool irq_disabled = irqs_disabled();
 
+	if (!irq_disabled) {
+		WARN_ONCE(1, "HLT instruction emulation unsafe with irqs enabled\n");
+		return -EIO;
+	}
+
 	if (__halt(irq_disabled))
 		return -EIO;

---

## [3] Sean Christopherson — 2025-02-07
*Subject: Re: [PATCH V3 2/2] x86/tdx: Emit warning if IRQs are enabled during
 HLT #VE handling*

On Thu, Feb 06, 2025, Vishal Annapurve wrote:
> Direct HLT instruction execution causes #VEs for TDX VMs which is routed
> to hypervisor via TDCALL. safe_halt() routines execute HLT in STI-shadow

Wrap the check with WARN_ONCE(), doing so adds an unlikely to the <drum roll>
unlikely scenario.

> +		WARN_ONCE(1, "HLT instruction emulation unsafe with irqs enabled\n");

Newline is redundant, the WARN does that for you.  IMO, it's also worth adding
a comment, because this is like the fifth time "safe halt" has come up in the
context of TDX.

E.g.

	/*
	 * HLT with IRQs enabled is unsafe, as an IRQ that is intended to be a
	 * wake event may be consumed before requesting HLT emulation, leaving
	 * the vCPU blocking indefinitely.
	 */
	if (WARN_ONCE(!irq_disabled, "HLT emulation with IRQs enabled"))
		return -EIO;

---

## [4] Vishal Annapurve — 2025-02-10
*Subject: Re: [PATCH V3 2/2] x86/tdx: Emit warning if IRQs are enabled during
 HLT #VE handling*

On Fri, Feb 7, 2025 at 7:22 AM Sean Christopherson <seanjc@google.com> wrote:
>
> On Thu, Feb 06, 2025, Vishal Annapurve wrote:

Ack, will integrate this feedback in v4.

Thanks,
Vishal

---

## [5] Kirill A. Shutemov — 2025-02-11
*Subject: Re: [PATCH V3 1/2] x86/tdx: Route safe halt execution via
 tdx_safe_halt()*

On Thu, Feb 06, 2025 at 10:27:12PM +0000, Vishal Annapurve wrote:
> Direct HLT instruction execution causes #VEs for TDX VMs which is routed
> to hypervisor via TDCALL. safe_halt() routines execute HLT in STI-shadow

I don't think it is acceptable to keep !PARAVIRT_XXL (read no-Xen) config
broken.

We need either move irq.safe_halt() out of PARAVIRT_XXL now or make
non-paravirt arch_safe_halt() to use TDCALL. Or if we don't care about
performance of !PARAVIRT_XXL config, special-case HLT in
exc_virtualization_exception().

---

## [6] Vishal Annapurve — 2025-02-11
*Subject: Re: [PATCH V3 1/2] x86/tdx: Route safe halt execution via tdx_safe_halt()*

On Tue, Feb 11, 2025 at 12:32 AM Kirill A. Shutemov
<kirill.shutemov@linux.intel.com> wrote:
>
> On Thu, Feb 06, 2025 at 10:27:12PM +0000, Vishal Annapurve wrote:

I will post v4 with the patch [1] move safe_halt/halt out of
PARAVIRT_XXL included as the next step.

[1] https://lore.kernel.org/lkml/20210517235008.257241-1-sathyanarayanan.kuppuswamy@linux.intel.com/

>
> --

---

## [7] Dave Hansen — 2025-02-11
*Subject: Re: [PATCH V3 1/2] x86/tdx: Route safe halt execution via
 tdx_safe_halt()*

On 2/11/25 00:32, Kirill A. Shutemov wrote:
>> If CONFIG_PARAVIRT_XXL is disabled, "sti;hlt" sequences can still get
>> executed from TDX VMs via paths like:

Oh, I thought it took PARAVIRT_XXL=y to even trigger this issue. Was I
just confused?

---

## [8] Vishal Annapurve — 2025-02-11
*Subject: Re: [PATCH V3 1/2] x86/tdx: Route safe halt execution via tdx_safe_halt()*

On Tue, Feb 11, 2025 at 3:46 PM Dave Hansen <dave.hansen@intel.com> wrote:
>
> On 2/11/25 00:32, Kirill A. Shutemov wrote:

Original issue with unsafe "sti;hlt" execution for TDX VMs doesn't
need PARAVIRT_XXL to be enabled in theory. Any caller just needs to
reach native*halt() to trigger the issue.

---
