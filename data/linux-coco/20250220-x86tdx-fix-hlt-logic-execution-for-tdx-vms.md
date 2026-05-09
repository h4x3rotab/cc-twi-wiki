---
title: 'x86/tdx: Fix HLT logic execution for TDX VMs'
date: 2025-02-20
last_reply: 2025-03-03
message_count: 11
participants: ['Vishal Annapurve', 'Dave Hansen', 'Konrad Rzeszutek Wilk', 'Jürgen Groß']
---

## [1] Vishal Annapurve — 2025-02-20

Direct HLT instruction execution causes #VEs for TDX VMs which is routed
to hypervisor via TDCALL. safe_halt() routines execute HLT in STI-shadow
so IRQs need to remain disabled until the TDCALL to ensure that pending
IRQs are correctly treated as wake events. So "sti;hlt" sequence needs to
be replaced for TDX VMs with TDCALL execution followed by enabling of
interrupts.

Changes introduced by the series include:
- Move *halt() variants outside CONFIG_PARAVIRT_XXL and under
  CONFIG_PARAVIRT [1].
- Route "sti; hlt" sequences via tdx_safe_halt() for reliability.
- Route "hlt" sequences via tdx_halt() to avoid unnecessary #VEs.
- Add explicit dependency on CONFIG_PARAVIRT for TDX VMs.
- Warn and fail emulation if HLT #VE emulation executes with interrupts
  enabled.
- Clean up TDX specific idle routine override.

Changes since v4:
1) Addressed Kirill's comments.

v4: https://lore.kernel.org/lkml/20250212000747.3403836-1-vannapurve@google.com/

Changes since v3:
1) Addressed comments from Sean.
2) Included [1] in the series to fix the scenarios where
CONFIG_PARAVIRT_XXL could be disabled.
v3: https://lore.kernel.org/all/20250206222714.1079059-1-vannapurve@google.com/

[1] https://lore.kernel.org/lkml/20210517235008.257241-1-sathyanarayanan.kuppuswamy@linux.intel.com/

Kirill A. Shutemov (1):
  x86/paravirt: Move halt paravirt calls under CONFIG_PARAVIRT

Vishal Annapurve (3):
  x86/tdx: Route safe halt execution via tdx_safe_halt()
  x86/tdx: Emit warning if IRQs are enabled during HLT #VE handling
  x86/tdx: Remove TDX specific idle routine

 arch/x86/Kconfig                      |  1 +
 arch/x86/coco/tdx/tdx.c               | 30 +++++++++++++++++++-
 arch/x86/include/asm/irqflags.h       | 40 +++++++++++++++------------
 arch/x86/include/asm/paravirt.h       | 20 +++++++-------
 arch/x86/include/asm/paravirt_types.h |  3 +-
 arch/x86/include/asm/tdx.h            |  2 --
 arch/x86/kernel/paravirt.c            | 14 ++++++----
 arch/x86/kernel/process.c             |  3 --
 8 files changed, 71 insertions(+), 42 deletions(-)

---

## [2] Vishal Annapurve — 2025-02-20
*Subject: [PATCH V5 1/4] x86/paravirt: Move halt paravirt calls under CONFIG_PARAVIRT*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

CONFIG_PARAVIRT_XXL is mainly defined/used by XEN PV guests. For
other VM guest types, features supported under CONFIG_PARAVIRT
are self sufficient. CONFIG_PARAVIRT mainly provides support for
TLB flush operations and time related operations.

For TDX guest as well, paravirt calls under CONFIG_PARVIRT meets
most of its requirement except the need of HLT and SAFE_HLT
paravirt calls, which is currently defined under
CONFIG_PARAVIRT_XXL.

Since enabling CONFIG_PARAVIRT_XXL is too bloated for TDX guest
like platforms, move HLT and SAFE_HLT paravirt calls under
CONFIG_PARAVIRT.

Moving HLT and SAFE_HLT paravirt calls are not fatal and should not
break any functionality for current users of CONFIG_PARAVIRT.

Cc: stable@vger.kernel.org
Fixes: bfe6ed0c6727 ("x86/tdx: Add HLT support for TDX guests")
Co-developed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Signed-off-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Andi Kleen <ak@linux.intel.com>
Reviewed-by: Tony Luck <tony.luck@intel.com>
Signed-off-by: Vishal Annapurve <vannapurve@google.com>
---
 arch/x86/include/asm/irqflags.h       | 40 +++++++++++++++------------
 arch/x86/include/asm/paravirt.h       | 20 +++++++-------
 arch/x86/include/asm/paravirt_types.h |  3 +-
 arch/x86/kernel/paravirt.c            | 14 ++++++----
 4 files changed, 41 insertions(+), 36 deletions(-)

diff --git a/arch/x86/include/asm/irqflags.h b/arch/x86/include/asm/irqflags.h
index cf7fc2b8e3ce..1c2db11a2c3c 100644
--- a/arch/x86/include/asm/irqflags.h
+++ b/arch/x86/include/asm/irqflags.h
@@ -76,6 +76,28 @@ static __always_inline void native_local_irq_restore(unsigned long flags)
 
 #endif
 
+#ifndef CONFIG_PARAVIRT
+#ifndef __ASSEMBLY__
+/*
+ * Used in the idle loop; sti takes one instruction cycle
+ * to complete:
+ */
+static __always_inline void arch_safe_halt(void)
+{
+	native_safe_halt();
+}
+
+/*
+ * Used when interrupts are already enabled or to
+ * shutdown the processor:
+ */
+static __always_inline void halt(void)
+{
+	native_halt();
+}
+#endif /* __ASSEMBLY__ */
+#endif /* CONFIG_PARAVIRT */
+
 #ifdef CONFIG_PARAVIRT_XXL
 #include <asm/paravirt.h>
 #else
@@ -97,24 +119,6 @@ static __always_inline void arch_local_irq_enable(void)
 	native_irq_enable();
 }
 
-/*
- * Used in the idle loop; sti takes one instruction cycle
- * to complete:
- */
-static __always_inline void arch_safe_halt(void)
-{
-	native_safe_halt();
-}
-
-/*
- * Used when interrupts are already enabled or to
- * shutdown the processor:
- */
-static __always_inline void halt(void)
-{
-	native_halt();
-}
-
 /*
  * For spinlocks, etc:
  */
diff --git a/arch/x86/include/asm/paravirt.h b/arch/x86/include/asm/paravirt.h
index 041aff51eb50..29e7331a0c98 100644
--- a/arch/x86/include/asm/paravirt.h
+++ b/arch/x86/include/asm/paravirt.h
@@ -107,6 +107,16 @@ static inline void notify_page_enc_status_changed(unsigned long pfn,
 	PVOP_VCALL3(mmu.notify_page_enc_status_changed, pfn, npages, enc);
 }
 
+static __always_inline void arch_safe_halt(void)
+{
+	PVOP_VCALL0(irq.safe_halt);
+}
+
+static inline void halt(void)
+{
+	PVOP_VCALL0(irq.halt);
+}
+
 #ifdef CONFIG_PARAVIRT_XXL
 static inline void load_sp0(unsigned long sp0)
 {
@@ -170,16 +180,6 @@ static inline void __write_cr4(unsigned long x)
 	PVOP_VCALL1(cpu.write_cr4, x);
 }
 
-static __always_inline void arch_safe_halt(void)
-{
-	PVOP_VCALL0(irq.safe_halt);
-}
-
-static inline void halt(void)
-{
-	PVOP_VCALL0(irq.halt);
-}
-
 static inline u64 paravirt_read_msr(unsigned msr)
 {
 	return PVOP_CALL1(u64, cpu.read_msr, msr);
diff --git a/arch/x86/include/asm/paravirt_types.h b/arch/x86/include/asm/paravirt_types.h
index fea56b04f436..abccfccc2e3f 100644
--- a/arch/x86/include/asm/paravirt_types.h
+++ b/arch/x86/include/asm/paravirt_types.h
@@ -120,10 +120,9 @@ struct pv_irq_ops {
 	struct paravirt_callee_save save_fl;
 	struct paravirt_callee_save irq_disable;
 	struct paravirt_callee_save irq_enable;
-
+#endif
 	void (*safe_halt)(void);
 	void (*halt)(void);
-#endif
 } __no_randomize_layout;
 
 struct pv_mmu_ops {
diff --git a/arch/x86/kernel/paravirt.c b/arch/x86/kernel/paravirt.c
index 1ccaa3397a67..c5bb980b8a67 100644
--- a/arch/x86/kernel/paravirt.c
+++ b/arch/x86/kernel/paravirt.c
@@ -110,6 +110,11 @@ int paravirt_disable_iospace(void)
 	return request_resource(&ioport_resource, &reserve_ioports);
 }
 
+static noinstr void pv_native_safe_halt(void)
+{
+	native_safe_halt();
+}
+
 #ifdef CONFIG_PARAVIRT_XXL
 static noinstr void pv_native_write_cr2(unsigned long val)
 {
@@ -125,11 +130,6 @@ static noinstr void pv_native_set_debugreg(int regno, unsigned long val)
 {
 	native_set_debugreg(regno, val);
 }
-
-static noinstr void pv_native_safe_halt(void)
-{
-	native_safe_halt();
-}
 #endif
 
 struct pv_info pv_info = {
@@ -186,9 +186,11 @@ struct paravirt_patch_template pv_ops = {
 	.irq.save_fl		= __PV_IS_CALLEE_SAVE(pv_native_save_fl),
 	.irq.irq_disable	= __PV_IS_CALLEE_SAVE(pv_native_irq_disable),
 	.irq.irq_enable		= __PV_IS_CALLEE_SAVE(pv_native_irq_enable),
+#endif /* CONFIG_PARAVIRT_XXL */
+
+	/* Irq HLT ops. */
 	.irq.safe_halt		= pv_native_safe_halt,
 	.irq.halt		= native_halt,
-#endif /* CONFIG_PARAVIRT_XXL */
 
 	/* Mmu ops. */
 	.mmu.flush_tlb_user	= native_flush_tlb_local,

---

## [3] Vishal Annapurve — 2025-02-20
*Subject: [PATCH V5 2/4] x86/tdx: Route safe halt execution via tdx_safe_halt()*

Direct HLT instruction execution causes #VEs for TDX VMs which is routed
to hypervisor via TDCALL. safe_halt() routines execute HLT in STI-shadow
so IRQs need to remain disabled until the TDCALL to ensure that pending
IRQs are correctly treated as wake events. So "sti;hlt" sequence needs to
be replaced for TDX VMs with "TDCALL; *_irq_enable()" to keep interrupts
disabled during TDCALL execution.

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
executes TDCALL without toggling interrupt state. Introduce dependency
on CONFIG_PARAVIRT and override paravirt halt()/safe_halt() routines for
TDX VMs.

Cc: stable@vger.kernel.org
Fixes: bfe6ed0c6727 ("x86/tdx: Add HLT support for TDX guests")
Signed-off-by: Vishal Annapurve <vannapurve@google.com>
---
 arch/x86/Kconfig           |  1 +
 arch/x86/coco/tdx/tdx.c    | 22 +++++++++++++++++++++-
 arch/x86/include/asm/tdx.h |  2 +-
 arch/x86/kernel/process.c  |  2 +-
 4 files changed, 24 insertions(+), 3 deletions(-)

diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
index 87198d957e2f..afcdbc9693dc 100644
--- a/arch/x86/Kconfig
+++ b/arch/x86/Kconfig
@@ -902,6 +902,7 @@ config INTEL_TDX_GUEST
 	depends on X86_64 && CPU_SUP_INTEL
 	depends on X86_X2APIC
 	depends on EFI_STUB
+	depends on PARAVIRT
 	select ARCH_HAS_CC_PLATFORM
 	select X86_MEM_ENCRYPT
 	select X86_MCE
diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 32809a06dab4..7ab427e85bd3 100644
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
 
@@ -409,6 +410,16 @@ void __cpuidle tdx_safe_halt(void)
 		WARN_ONCE(1, "HLT instruction emulation failed\n");
 }
 
+static void __cpuidle tdx_safe_halt(void)
+{
+	tdx_halt();
+	/*
+	 * "__cpuidle" section doesn't support instrumentation, so stick
+	 * with raw_* variant that avoids tracing hooks.
+	 */
+	raw_local_irq_enable();
+}
+
 static int read_msr(struct pt_regs *regs, struct ve_info *ve)
 {
 	struct tdx_module_args args = {
@@ -1109,6 +1120,15 @@ void __init tdx_early_init(void)
 	x86_platform.guest.enc_kexec_begin	     = tdx_kexec_begin;
 	x86_platform.guest.enc_kexec_finish	     = tdx_kexec_finish;
 
+	/*
+	 * "sti;hlt" execution in TDX guests will induce a #VE in the STI-shadow
+	 * which will enable interrupts before HLT TDCALL inocation possibly
+	 * resulting in missed wakeup events. Modify all possible HLT
+	 * execution paths to use TDCALL for performance/reliability reasons.
+	 */
+	pv_ops.irq.safe_halt = tdx_safe_halt;
+	pv_ops.irq.halt = tdx_halt;
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

## [4] Vishal Annapurve — 2025-02-20
*Subject: [PATCH V5 3/4] x86/tdx: Emit warning if IRQs are enabled during HLT
 #VE handling*

Direct HLT instruction execution causes #VEs for TDX VMs which is routed
to hypervisor via TDCALL. safe_halt() routines execute HLT in STI-shadow
so IRQs need to remain disabled until the TDCALL to ensure that pending
IRQs are correctly treated as wake events.

Emit warning and fail emulation if IRQs are enabled during HLT #VE handling
to avoid running into scenarios where IRQ wake events are lost resulting in
indefinite HLT execution times.

Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Vishal Annapurve <vannapurve@google.com>
---
 arch/x86/coco/tdx/tdx.c | 8 ++++++++
 1 file changed, 8 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 7ab427e85bd3..16ac337df9fa 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -393,6 +393,14 @@ static int handle_halt(struct ve_info *ve)
 {
 	const bool irq_disabled = irqs_disabled();
 
+	/*
+	 * HLT with IRQs enabled is unsafe, as an IRQ that is intended to be a
+	 * wake event may be consumed before requesting HLT emulation, leaving
+	 * the vCPU blocking indefinitely.
+	 */
+	if (WARN_ONCE(!irq_disabled, "HLT emulation with IRQs enabled"))
+		return -EIO;
+
 	if (__halt(irq_disabled))
 		return -EIO;

---

## [5] Vishal Annapurve — 2025-02-20
*Subject: [PATCH V5 4/4] x86/tdx: Remove TDX specific idle routine*

With explicit dependency on CONFIG_PARAVIRT and TDX specific
halt()/safe_halt() routines in place, default_idle() is safe to execute for
TDX VMs. Remove TDX specific idle routine override which is now
redundant.

Signed-off-by: Vishal Annapurve <vannapurve@google.com>
---
 arch/x86/coco/tdx/tdx.c    | 2 +-
 arch/x86/include/asm/tdx.h | 2 --
 arch/x86/kernel/process.c  | 3 ---
 3 files changed, 1 insertion(+), 6 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 16ac337df9fa..46f7bb82c8b7 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -407,7 +407,7 @@ static int handle_halt(struct ve_info *ve)
 	return ve_instr_len(ve);
 }
 
-void __cpuidle tdx_halt(void)
+static void __cpuidle tdx_halt(void)
 {
 	const bool irq_disabled = false;
 
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 393ee2dfaab1..6769d1da4c80 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -58,8 +58,6 @@ void tdx_get_ve_info(struct ve_info *ve);
 
 bool tdx_handle_virt_exception(struct pt_regs *regs, struct ve_info *ve);
 
-void tdx_halt(void);
-
 bool tdx_early_handle_ve(struct pt_regs *regs);
 
 int tdx_mcall_get_report0(u8 *reportdata, u8 *tdreport);
diff --git a/arch/x86/kernel/process.c b/arch/x86/kernel/process.c
index d11956a178df..9b21989c283b 100644
--- a/arch/x86/kernel/process.c
+++ b/arch/x86/kernel/process.c
@@ -932,9 +932,6 @@ void __init select_idle_routine(void)
 	if (prefer_mwait_c1_over_halt()) {
 		pr_info("using mwait in idle threads\n");
 		static_call_update(x86_idle, mwait_idle);
-	} else if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST)) {
-		pr_info("using TDX aware idle routine\n");
-		static_call_update(x86_idle, tdx_halt);
 	} else {
 		static_call_update(x86_idle, default_idle);
 	}

---

## [6] Dave Hansen — 2025-02-20
*Subject: Re: [PATCH V5 1/4] x86/paravirt: Move halt paravirt calls under
 CONFIG_PARAVIRT*

On 2/20/25 13:16, Vishal Annapurve wrote:
> Since enabling CONFIG_PARAVIRT_XXL is too bloated for TDX guest
> like platforms, move HLT and SAFE_HLT paravirt calls under

I guess it's just one patch, but doesn't this expose CONFIG_PARAVIRT=y
users to what _was_ specific to CONFIG_PARAVIRT_XXL=y? According to the
changelog, TDX users shouldn't have to use use PARAVIRT_XXL, so
PARAVIRT=y and PARAVIRT_XXL=n must be an *IMPORTANT* configuration for
TDX users.

Before this patch, those users would have no way to hit the
unsafe-for-TDX pv_native_safe_halt(). After this patch, they will hit it.

So, there are two possibilities:

 1. This patch breaks bisection for an important TDX configuration
 2. This patch's conjecture that PARAVIRT_XXL=n is important for TDX
    is wrong and it is not necessary in the first place.

What am I missing?

---

## [7] Dave Hansen — 2025-02-20
*Subject: Re: [PATCH V5 2/4] x86/tdx: Route safe halt execution via
 tdx_safe_halt()*

On 2/20/25 13:16, Vishal Annapurve wrote:
> Direct HLT instruction execution causes #VEs for TDX VMs which is routed
> to hypervisor via TDCALL. safe_halt() routines execute HLT in STI-shadow

This isn't quite true. There's only one paravirt safe_halt() and it
doesn't do HLT or STI.

I think it's more true to say that "safe" halts are entered with IRQs
disabled. They logically do the halt operation and then enable
interrupts before returning.

> So "sti;hlt" sequence needs to be replaced for TDX VMs with "TDCALL;
> *_irq_enable()" to keep interrupts disabled during TDCALL execution.
But this isn't new. TDX already tried to avoid "sti;hlt". It just
screwed up the implementation.

> Commit bfe6ed0c6727 ("x86/tdx: Add HLT support for TDX guests")
> prevented the idle routines from using "sti;hlt". But it missed the

This, on the other hand, *is* important.

> Modify tdx_safe_halt() to implement the sequence "TDCALL;
> raw_local_irq_enable()" and invoke tdx_halt() from idle routine which just

This changelog glosses over one of the key points: Why *MUST* TDX use
paravirt? It further confuses the reasoning by alluding to the idea that
"Direct HLT instruction execution ... is routed to hypervisor via TDCALL".

It gives background and a solution, but it's not obvious what the
problem is or how the solution _fixes_ the problem.

What must TDX now depend on PARAVIRT?

Why not just route the HLT to a TDXCALL via the #VE code?

---

## [8] Vishal Annapurve — 2025-02-20
*Subject: Re: [PATCH V5 1/4] x86/paravirt: Move halt paravirt calls under CONFIG_PARAVIRT*

On Thu, Feb 20, 2025 at 1:47 PM Dave Hansen <dave.hansen@intel.com> wrote:
>
> On 2/20/25 13:16, Vishal Annapurve wrote:

Before this patch, those users had access to arch_safe_halt() ->
native_safe_halt() path. With this patch, such users can execute
arch_safe_halt -> pv_native_safe_halt() -> native_safe_halt(), so this
patch doesn't cause any additional regression.

>
> So, there are two possibilities:

---

## [9] Vishal Annapurve — 2025-02-20
*Subject: Re: [PATCH V5 2/4] x86/tdx: Route safe halt execution via tdx_safe_halt()*

On Thu, Feb 20, 2025 at 3:00 PM Dave Hansen <dave.hansen@intel.com> wrote:
>
> On 2/20/25 13:16, Vishal Annapurve wrote:

pv_native_safe_halt() -> native_safe_halt() -> "sti; hlt".

>
> I think it's more true to say that "safe" halts are entered with IRQs

Makes sense, I will update the commit message in the next version to
clearly answer these questions and address the above comments.

---

## [10] Konrad Rzeszutek Wilk — 2025-02-28
*Subject: Re: [PATCH V5 1/4] x86/paravirt: Move halt paravirt calls under
 CONFIG_PARAVIRT*

On Thu, Feb 20, 2025 at 09:16:25PM +0000, Vishal Annapurve wrote:
> From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
> 

Could you use the bloat-o-meter to give an idea of the savings?

Also .. aren't most distros building with Xen support so they will
always have the full paravirt support?

> 
> Moving HLT and SAFE_HLT paravirt calls are not fatal and should not

---

## [11] Jürgen Groß — 2025-03-03
*Subject: Re: [PATCH V5 1/4] x86/paravirt: Move halt paravirt calls under
 CONFIG_PARAVIRT*

On 28.02.25 22:47, Konrad Rzeszutek Wilk wrote:
> On Thu, Feb 20, 2025 at 09:16:25PM +0000, Vishal Annapurve wrote:
>> From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

Adding PARAVIRT_XXL users should be avoided if possible.

Main reason is that the work to make PVH dom0 fully functional compared
to PV dom0 will make it possible to deprecate PV mode in the long run.


Juergen

---
