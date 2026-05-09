---
title: 'x86/tdx: Fix HLT logic execution for TDX VMs'
date: 2025-02-25
last_reply: 2025-02-27
message_count: 9
participants: ['Vishal Annapurve', 'Juergen Gross', 'Kirill A. Shutemov', 'kernel test robot']
---

## [1] Vishal Annapurve — 2025-02-25

Direct HLT instruction execution causes #VEs for TDX VMs which is routed
to hypervisor via TDCALL. safe_halt() routines execute HLT in STI-shadow
so IRQs need to remain disabled until the TDCALL to ensure that pending
IRQs are correctly treated as wake events. As per current TDX spec, HLT
#VE handler doesn't have access to interruptibility state to selectively
enable interrupts, it ends up enabling interrupts during #VE handling
before the TDCALL is executed.
 
Commit bfe6ed0c6727 ("x86/tdx: Add HLT support for TDX guests")
effectively solved this issue for idle routines by defining TDX specific
idle routine which directly invokes TDCALL while keeping interrupts
disabled, but missed handling arch_safe_halt(). This series intends to fix
arch_safe_halt() execution for TDX VMs.

Changes introduced by the series include:
- Move *halt() variants outside CONFIG_PARAVIRT_XXL and under
  CONFIG_PARAVIRT [1].
- Add explicit dependency on CONFIG_PARAVIRT for TDX VMs.
- Route "sti; hlt" sequences via tdx_safe_halt() for reliability.
- Route "hlt" sequences via tdx_halt() to avoid unnecessary #VEs.
- Warn and fail emulation if HLT #VE emulation executes with interrupts
  enabled.

Changes since v5:
1) Addressed Dave's comments.
2) Dropped the cleanup patch for now, it can be discussed separately.

v5: https://lore.kernel.org/lkml/20250220211628.1832258-1-vannapurve@google.com/

Kirill A. Shutemov (1):
  x86/paravirt: Move halt paravirt calls under CONFIG_PARAVIRT

Vishal Annapurve (2):
  x86/tdx: Fix arch_safe_halt() execution for TDX VMs
  x86/tdx: Emit warning if IRQs are enabled during HLT #VE handling

 arch/x86/Kconfig                      |  1 +
 arch/x86/coco/tdx/tdx.c               | 34 ++++++++++++++++++++++-
 arch/x86/include/asm/irqflags.h       | 40 +++++++++++++++------------
 arch/x86/include/asm/paravirt.h       | 20 +++++++-------
 arch/x86/include/asm/paravirt_types.h |  3 +-
 arch/x86/include/asm/tdx.h            |  2 +-
 arch/x86/kernel/paravirt.c            | 14 ++++++----
 arch/x86/kernel/process.c             |  2 +-
 8 files changed, 77 insertions(+), 39 deletions(-)

---

## [2] Vishal Annapurve — 2025-02-25
*Subject: [PATCH v6 1/3] x86/paravirt: Move halt paravirt calls under CONFIG_PARAVIRT*

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

## [3] Vishal Annapurve — 2025-02-25
*Subject: [PATCH v6 2/3] x86/tdx: Fix arch_safe_halt() execution for TDX VMs*

Direct HLT instruction execution causes #VEs for TDX VMs which is routed
to hypervisor via TDCALL. If HLT is executed in STI-shadow, resulting #VE
handler will enable interrupts before TDCALL is routed to hypervisor
leading to missed wakeup events.

Current TDX spec doesn't expose interruptibility state information to
allow #VE handler to selectively enable interrupts. To bypass this
issue, TDX VMs need to replace "sti;hlt" execution with direct TDCALL
followed by explicit interrupt flag update.

Commit bfe6ed0c6727 ("x86/tdx: Add HLT support for TDX guests")
prevented the idle routines from executing HLT instruction in STI-shadow.
But it missed the paravirt routine which can be reached like this as an
example:
        acpi_safe_halt() =>
        raw_safe_halt()  =>
        arch_safe_halt() =>
        irq.safe_halt()  =>
        pv_native_safe_halt()

To reliably handle arch_safe_halt() for TDX VMs, introduce explicit
dependency on CONFIG_PARAVIRT and override paravirt halt()/safe_halt()
routines with TDX-safe versions that execute direct TDCALL and needed
interrupt flag updates. Executing direct TDCALL brings in additional
benefit of avoiding HLT related #VEs altogether.

Cc: stable@vger.kernel.org
Fixes: bfe6ed0c6727 ("x86/tdx: Add HLT support for TDX guests")
Signed-off-by: Vishal Annapurve <vannapurve@google.com>
---
 arch/x86/Kconfig           |  1 +
 arch/x86/coco/tdx/tdx.c    | 26 +++++++++++++++++++++++++-
 arch/x86/include/asm/tdx.h |  2 +-
 arch/x86/kernel/process.c  |  2 +-
 4 files changed, 28 insertions(+), 3 deletions(-)

diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
index be2c311f5118..933c046e8966 100644
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
index 32809a06dab4..6aad910d119d 100644
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
@@ -1109,6 +1120,19 @@ void __init tdx_early_init(void)
 	x86_platform.guest.enc_kexec_begin	     = tdx_kexec_begin;
 	x86_platform.guest.enc_kexec_finish	     = tdx_kexec_finish;
 
+	/*
+	 * Avoid "sti;hlt" execution in TDX guests as HLT induces a #VE that
+	 * will enable interrupts before HLT TDCALL invocation if executed
+	 * in STI-shadow, possibly resulting in missed wakeup events.
+	 *
+	 * Modify all possible HLT execution paths to use TDX specific routines
+	 * that directly execute TDCALL and toggle the interrupt state as
+	 * needed after TDCALL completion. This also reduces HLT related #VEs
+	 * in addition to having a reliable halt logic execution.
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

## [4] Vishal Annapurve — 2025-02-25
*Subject: [PATCH v6 3/3] x86/tdx: Emit warning if IRQs are enabled during HLT
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
index 6aad910d119d..a97ddc6a52c3 100644
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

## [5] Juergen Gross — 2025-02-25
*Subject: Re: [PATCH v6 1/3] x86/paravirt: Move halt paravirt calls under
 CONFIG_PARAVIRT*

On 25.02.25 01:47, Vishal Annapurve wrote:
> From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
> 

Reviewed-by: Juergen Gross <jgross@suse.com>


Juergen

---

## [6] Kirill A. Shutemov — 2025-02-26
*Subject: Re: [PATCH v6 2/3] x86/tdx: Fix arch_safe_halt() execution for TDX
 VMs*

On Tue, Feb 25, 2025 at 12:47:03AM +0000, Vishal Annapurve wrote:
> Direct HLT instruction execution causes #VEs for TDX VMs which is routed
> to hypervisor via TDCALL. If HLT is executed in STI-shadow, resulting #VE

I would rather use paravirt spinlock example. It is less controversial.
I still see no point in ACPI cpuidle be a thing in TDX guests.

> 
> To reliably handle arch_safe_halt() for TDX VMs, introduce explicit

Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

---

## [7] kernel test robot — 2025-02-28
*Subject: Re: [PATCH v6 2/3] x86/tdx: Fix arch_safe_halt() execution for TDX
 VMs*

Hi Vishal,

kernel test robot noticed the following build errors:

[auto build test ERROR on tip/x86/core]
[also build test ERROR on tip/master linus/master v6.14-rc4 next-20250227]
[cannot apply to tip/x86/tdx tip/auto-latest]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Vishal-Annapurve/x86-paravirt-Move-halt-paravirt-calls-under-CONFIG_PARAVIRT/20250225-085043
base:   tip/x86/core
patch link:    https://lore.kernel.org/r/20250225004704.603652-3-vannapurve%40google.com
patch subject: [PATCH v6 2/3] x86/tdx: Fix arch_safe_halt() execution for TDX VMs
config: i386-buildonly-randconfig-003-20250227 (https://download.01.org/0day-ci/archive/20250227/202502272346.iiQ6Dptt-lkp@intel.com/config)
compiler: clang version 19.1.7 (https://github.com/llvm/llvm-project cd708029e0b2869e80abe31ddb175f7c35361f90)
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20250227/202502272346.iiQ6Dptt-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202502272346.iiQ6Dptt-lkp@intel.com/

All errors (new ones prefixed by >>):

   In file included from arch/x86/kernel/process.c:6:
   In file included from include/linux/mm.h:2224:
   include/linux/vmstat.h:504:43: warning: arithmetic between different enumeration types ('enum zone_stat_item' and 'enum numa_stat_item') [-Wenum-enum-conversion]
     504 |         return vmstat_text[NR_VM_ZONE_STAT_ITEMS +
         |                            ~~~~~~~~~~~~~~~~~~~~~ ^
     505 |                            item];
         |                            ~~~~
   include/linux/vmstat.h:511:43: warning: arithmetic between different enumeration types ('enum zone_stat_item' and 'enum numa_stat_item') [-Wenum-enum-conversion]
     511 |         return vmstat_text[NR_VM_ZONE_STAT_ITEMS +
         |                            ~~~~~~~~~~~~~~~~~~~~~ ^
     512 |                            NR_VM_NUMA_EVENT_ITEMS +
         |                            ~~~~~~~~~~~~~~~~~~~~~~
>> arch/x86/kernel/process.c:937:32: error: use of undeclared identifier 'tdx_halt'; did you mean 'tdx_init'?
     937 |                 static_call_update(x86_idle, tdx_halt);
         |                                              ^~~~~~~~
         |                                              tdx_init
   include/linux/static_call.h:154:42: note: expanded from macro 'static_call_update'
     154 |         typeof(&STATIC_CALL_TRAMP(name)) __F = (func);                  \
         |                                                 ^
   arch/x86/include/asm/tdx.h:123:20: note: 'tdx_init' declared here
     123 | static inline void tdx_init(void) { }
         |                    ^
   2 warnings and 1 error generated.


vim +937 arch/x86/kernel/process.c

   919	
   920	void __init select_idle_routine(void)
   921	{
   922		if (boot_option_idle_override == IDLE_POLL) {
   923			if (IS_ENABLED(CONFIG_SMP) && __max_threads_per_core > 1)
   924				pr_warn_once("WARNING: polling idle and HT enabled, performance may degrade\n");
   925			return;
   926		}
   927	
   928		/* Required to guard against xen_set_default_idle() */
   929		if (x86_idle_set())
   930			return;
   931	
   932		if (prefer_mwait_c1_over_halt()) {
   933			pr_info("using mwait in idle threads\n");
   934			static_call_update(x86_idle, mwait_idle);
   935		} else if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST)) {
   936			pr_info("using TDX aware idle routine\n");
 > 937			static_call_update(x86_idle, tdx_halt);
   938		} else {
   939			static_call_update(x86_idle, default_idle);
   940		}
   941	}
   942

---

## [8] Vishal Annapurve — 2025-02-27
*Subject: Re: [PATCH v6 2/3] x86/tdx: Fix arch_safe_halt() execution for TDX VMs*

On Wed, Feb 26, 2025 at 3:49 AM Kirill A. Shutemov <kirill@shutemov.name> wrote:
>
> On Tue, Feb 25, 2025 at 12:47:03AM +0000, Vishal Annapurve wrote:

I will modify the description to include a paravirt spinlock example.

> >
> > To reliably handle arch_safe_halt() for TDX VMs, introduce explicit

---

## [9] Vishal Annapurve — 2025-02-27
*Subject: Re: [PATCH v6 2/3] x86/tdx: Fix arch_safe_halt() execution for TDX VMs*

On Thu, Feb 27, 2025 at 8:25 AM kernel test robot <lkp@intel.com> wrote:
>
> Hi Vishal,

Will fix this in the next version.

---
