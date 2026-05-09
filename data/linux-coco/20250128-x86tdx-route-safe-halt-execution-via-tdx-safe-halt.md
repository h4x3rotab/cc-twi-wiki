---
title: 'x86/tdx: Route safe halt execution via tdx_safe_halt'
date: 2025-01-28
last_reply: 2025-01-29
message_count: 9
participants: ['Vishal Annapurve', 'Dave Hansen', 'Sean Christopherson', 'Kirill A. Shutemov']
---

## [1] Vishal Annapurve — 2025-01-28

Direct HLT instruction execution causes #VEs for TDX VMs which is routed
to hypervisor via tdvmcall. This process renders HLT instruction
execution inatomic, so any preceeding instructions like STI/MOV SS will
end up enabling interrupts before the HLT instruction is routed to the
hypervisor. This creates scenarios where interrupts could land during
HLT instruction emulation without aborting halt operation leading to
idefinite halt wait times.

x86_idle is already upgraded to invoke tdx_safe_halt to avoid such
scenarios, but it didn't cover pvnative_safe_halt which can be invoked
using raw_safe_halt from call sites like acpi_safe_halt (acpi_pm
subsystem). This patch upgrades the safe_halt executions to use
tdx_safe_halt.

To avoid future call sites which cause HLT instruction emulation with
irqs enabled, add a warn and fail the HLT instruction emulation.

Signed-off-by: Vishal Annapurve <vannapurve@google.com>
---
 arch/x86/coco/tdx/tdx.c | 15 +++++++++++++++
 1 file changed, 15 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 0d9b090b4880..98b5f317596d 100644
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
@@ -380,6 +381,11 @@ static int handle_halt(struct ve_info *ve)
 {
 	const bool irq_disabled = irqs_disabled();
 
+	if (!irq_disabled) {
+		WARN(1, "HLT instruction emulation unsafe with irqs enabled\n");
+		return -EIO;
+	}
+
 	if (__halt(irq_disabled))
 		return -EIO;
 
@@ -1083,6 +1089,15 @@ void __init tdx_early_init(void)
 	x86_platform.guest.enc_kexec_begin	     = tdx_kexec_begin;
 	x86_platform.guest.enc_kexec_finish	     = tdx_kexec_finish;
 
+#ifdef CONFIG_PARAVIRT_XXL
+	/*
+	 * halt instruction execution is not atomic for TDX VMs as it generates
+	 * #VEs, so otherwise "safe" halt invocations which cause interrupts to
+	 * get enabled right after halt instruction don't work for TDX VMs.
+	 */
+	pv_ops.irq.safe_halt = tdx_safe_halt;
+#endif
+
 	/*
 	 * TDX intercepts the RDMSR to read the X2APIC ID in the parallel
 	 * bringup low level code. That raises #VE which cannot be handled

---

## [2] Dave Hansen — 2025-01-28
*Subject: Re: [PATCH 1/1] x86/tdx: Route safe halt execution via tdx_safe_halt*

On 1/28/25 13:36, Vishal Annapurve wrote:
> Direct HLT instruction execution causes #VEs for TDX VMs which is routed
> to hypervisor via tdvmcall. This process renders HLT instruction

Could you please break out the spell checker before posting v2? There
are a couple problems in that paragraph.

> x86_idle is already upgraded to invoke tdx_safe_halt to avoid such

Please add parenthesis to functions() to make it more clear what you are
referring to.

> scenarios, but it didn't cover pvnative_safe_halt which can be invoked
> using raw_safe_halt from call sites like acpi_safe_halt (acpi_pm

No "this patch", please.

> To avoid future call sites which cause HLT instruction emulation with
> irqs enabled, add a warn and fail the HLT instruction emulation.

This seems like a bug fix. Shouldn't it have a cc:stable@ and a Fixes: tag?

Do you have any thoughts on why nobody has hit this up to now? Are TDX
users not enabling PARAVIRT_XXL? Not using ACPI?

> diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
> index 0d9b090b4880..98b5f317596d 100644

Yeah, this warning is a good idea. But probably best left as a
WARN_ONCE() so it doesn't spew too badly.

> @@ -1083,6 +1089,15 @@ void __init tdx_early_init(void)
>  	x86_platform.guest.enc_kexec_begin	     = tdx_kexec_begin;
The basic bug here was that there was a path to a hlt instruction that
folks didn't realize. This patch fixes the basic bug and gives us a nice
warning if there are additional paths that weren't imagined.

But it doesn't really help us audit the code to make it clear that TDX
guest kernel's _can't_ screw up hlt again the same way.  This, for
instance would make it pretty clear:

static __always_inline void native_safe_halt(void)
{
	if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST))
		tdx_safe_halt();
        mds_idle_clear_cpu_buffers();
        asm volatile("sti; hlt": : :"memory");
}

There are reasons we wouldn't want to do that exactly, but I'd much
prefer something that is harder to screw up than the proposal above.
Anybody have any better ideas?

---

## [3] Vishal Annapurve — 2025-01-28
*Subject: Re: [PATCH 1/1] x86/tdx: Route safe halt execution via tdx_safe_halt*

On Tue, Jan 28, 2025 at 2:08 PM Dave Hansen <dave.hansen@intel.com> wrote:
>
> On 1/28/25 13:36, Vishal Annapurve wrote:

Makes sense to add "fixes: bfe6ed0c6727 (x86/tdx: Add HLT support for
TDX guests)" tag.

> Do you have any thoughts on why nobody has hit this up to now? Are TDX
> users not enabling PARAVIRT_XXL? Not using ACPI?

This has been a long-standing issue which would show up visibly with
certain workloads where vcpus hit idle loop quite often during the
runtime. I was only able to recently spend some time towards
understanding the cause properly.

>
> > diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c

All other suggestions look good to me and will incorporate them for V2.

---

## [4] Sean Christopherson — 2025-01-28
*Subject: Re: [PATCH 1/1] x86/tdx: Route safe halt execution via tdx_safe_halt*

On Tue, Jan 28, 2025, Vishal Annapurve wrote:
> On Tue, Jan 28, 2025 at 2:08 PM Dave Hansen <dave.hansen@intel.com> wrote:
> > Do you have any thoughts on why nobody has hit this up to now? Are TDX

...

> > > @@ -1083,6 +1089,15 @@ void __init tdx_early_init(void)
> > >       x86_platform.guest.enc_kexec_begin           = tdx_kexec_begin;

This incorrectly assumes the hypervisor is intercepting HLT.  If the VM is given
a slice of hardware, HLT-exiting may be disabled, in which case it's desirable
for the guest to natively execute HLT, as the latencies to get in and out of "HLT"
are lower, especially for TDX guests.  Such a VM would hopefully have MONITOR/MWAIT
available as well, but even if that were the case, the admin could select HLT for
idling.

Ugh, and I see that bfe6ed0c6727 ("x86/tdx: Add HLT support for TDX guests")
overrides default_idle().  The kernel really shouldn't do that, because odds are
decent that any TDX guest will have direct access to HLT.  The best approach I
can think of would be to patch x86_idle() to tdx_safe_halt() if and only if a HLT
#VE is taken.  The tricky part would be delaying the update until it's safe to do
so.

As for taking a #VE, the exception itself is fine (assuming the kernel isn't off
the rails and using a trap gate :-D).  The issue is likely that RFLAGS.IF=1 on
the stack, and so the call to cond_local_irq_enable() enables IRQs before making
the hypercall.  E.g. no one has complained about #VC, because exc_vmm_communication()
doesn't enable IRQs.

Off the top of my head, I can't think of any flows that would do HLT with IRQs
fully enabled.  Even PV spinlocks use safe_halt(), e.g. in kvm_wait(), so I don't
think there's any value in trying to precisely identify that it's a safe HLT?

E.g. this should fix the immediate problem, and then ideally someone would make
TDX guests play nice with native HLT.

diff --git a/arch/x86/kernel/traps.c b/arch/x86/kernel/traps.c
index 2dbadf347b5f..c60659468894 100644
--- a/arch/x86/kernel/traps.c
+++ b/arch/x86/kernel/traps.c
@@ -78,6 +78,8 @@
 
 #include <asm/proto.h>
 
+#include <uapi/asm/vmx.h>
+
 DECLARE_BITMAP(system_vectors, NR_VECTORS);
 
 __always_inline int is_valid_bugaddr(unsigned long addr)
@@ -1424,7 +1426,14 @@ DEFINE_IDTENTRY(exc_virtualization_exception)
         */
        tdx_get_ve_info(&ve);
 
-       cond_local_irq_enable(regs);
+       /*
+        * Don't enable IRQs on #VE due to HLT, as the HLT was likely executed
+        * in an STI-shadow, e.g. by safe_halt().  For safe HLT, IRQs need to
+        * remain disabled until the TDCALL to request HLT emulation, so that
+        * pending IRQs are correctly treated as wake events.
+        */
+       if (ve.exit_reason != EXIT_REASON_HLT)
+               cond_local_irq_enable(regs);
 
        /*
         * If tdx_handle_virt_exception() could not process
@@ -1433,7 +1442,8 @@ DEFINE_IDTENTRY(exc_virtualization_exception)
        if (!tdx_handle_virt_exception(regs, &ve))
                ve_raise_fault(regs, 0, ve.gla);
 
-       cond_local_irq_disable(regs);
+       if (ve.exit_reason != EXIT_REASON_HLT)
+               cond_local_irq_disable(regs);
 }
 
 #endif

---

## [5] Kirill A. Shutemov — 2025-01-29
*Subject: Re: [PATCH 1/1] x86/tdx: Route safe halt execution via tdx_safe_halt*

On Tue, Jan 28, 2025 at 09:36:52PM +0000, Vishal Annapurve wrote:
> Direct HLT instruction execution causes #VEs for TDX VMs which is routed
> to hypervisor via tdvmcall. This process renders HLT instruction

The question is why acpi_safe_halt() is ever called.

It only supposed to be called if the CPU supports C-states. See
pr->flags.power check in acpi_processor_power_init().

pr->flags.power is zero for me.

Maybe your BIOS is broken and enumerates C-states. I don't see how
C-states make sense for VMs.

---

## [6] Kirill A. Shutemov — 2025-01-29
*Subject: Re: [PATCH 1/1] x86/tdx: Route safe halt execution via tdx_safe_halt*

On Tue, Jan 28, 2025 at 04:45:35PM -0800, Sean Christopherson wrote:
> On Tue, Jan 28, 2025, Vishal Annapurve wrote:
> > On Tue, Jan 28, 2025 at 2:08 PM Dave Hansen <dave.hansen@intel.com> wrote:

I am confused. HLT triggers #VE unconditionally in TDX guests. How would
TDX guest have direct access to HLT?

Even if it would in the future, it is going to explicit opt-in from the
guest and we can avoid setting x86_idle() for such cases.

> As for taking a #VE, the exception itself is fine (assuming the kernel isn't off
> the rails and using a trap gate :-D).  The issue is likely that RFLAGS.IF=1 on

I can only think of "CPU is dead" use-case of HLT where interrupts are
enabled. But I hate special-casing HLT in exc_virtualization_exception() :/

> E.g. this should fix the immediate problem, and then ideally someone would make
> TDX guests play nice with native HLT.

I've asked (some time ago) TDX module folks to provide interruptibility
state as part of the guest so we can handle STI shadow properly, not as a
hack around HLT.

The immediate problem can be addressed by fixing the BIOS to not advertise
C-states (if I read the situation right).

---

## [7] Sean Christopherson — 2025-01-29
*Subject: Re: [PATCH 1/1] x86/tdx: Route safe halt execution via tdx_safe_halt*

On Wed, Jan 29, 2025, Kirill A. Shutemov wrote:
> On Tue, Jan 28, 2025 at 04:45:35PM -0800, Sean Christopherson wrote:
> > This incorrectly assumes the hypervisor is intercepting HLT.  If the VM is given

Gah, you're not confused, I am.  I was thinking of the SEV-ES model where intercepts
are morphed to #VC.  

> Even if it would in the future, it is going to explicit opt-in from the
> guest and we can avoid setting x86_idle() for such cases.

Or explicitly enumeration from the TDX module.

> > As for taking a #VE, the exception itself is fine (assuming the kernel isn't off
> > the rails and using a trap gate :-D).  The issue is likely that RFLAGS.IF=1 on

Ignore me, overriding at boot time is the way to go. 

> > E.g. this should fix the immediate problem, and then ideally someone would make
> > TDX guests play nice with native HLT.

No, something like Vishal proposed is a better fix.  It's still desirable for the
vCPU to call out to the hypervisor when going idle, otherwise a vCPU that is idle
for an extended duration will never let the pCPU go idle.

---

## [8] Sean Christopherson — 2025-01-29
*Subject: Re: [PATCH 1/1] x86/tdx: Route safe halt execution via tdx_safe_halt*

On Wed, Jan 29, 2025, Kirill A. Shutemov wrote:
> On Tue, Jan 28, 2025 at 04:45:35PM -0800, Sean Christopherson wrote:
> > This incorrectly assumes the hypervisor is intercepting HLT.  If the VM is given

Gah, you're not confused, I am.  I was thinking of the SEV-ES model where intercepts
are morphed to #VC.  

> Even if it would in the future, it is going to explicit opt-in from the
> guest and we can avoid setting x86_idle() for such cases.

Or explicit enumeration from the TDX module.

> > As for taking a #VE, the exception itself is fine (assuming the kernel isn't off
> > the rails and using a trap gate :-D).  The issue is likely that RFLAGS.IF=1 on

Ignore me, overriding at boot time is the way to go. 

> > E.g. this should fix the immediate problem, and then ideally someone would make
> > TDX guests play nice with native HLT.

No, something like Vishal proposed is a better fix.  It's still desirable for the
vCPU to call out to the hypervisor when going idle, otherwise a vCPU that is idle
for an extended duration will never let the pCPU go idle.

---

## [9] Vishal Annapurve — 2025-01-29
*Subject: Re: [PATCH 1/1] x86/tdx: Route safe halt execution via tdx_safe_halt*

On Wed, Jan 29, 2025 at 6:00 AM Sean Christopherson <seanjc@google.com> wrote:
>
> ...

I think Kirill's suggestion will ensure that cpuidle_idle_call() will
invoke default_idle_call() [1] which is correctly patched to call
tdx_safe_halt(), instead of using cpuidle driver subsystem. I am yet
to vet the ACPI cstate configuration for TDX VMs, but unless there is
something critically wrong with exposing cstates to the VM I think
it's better to handle acpi_safe_halt for TDX VMs.

Until there is a better solution to emulate the "sti; hlt;" behavior
for TDX VMs, it's important to deploy warnings as these scenarios are
easy to miss and hard to debug otherwise.

[1] https://elixir.bootlin.com/linux/v6.13/source//kernel/sched/idle.c#L182

---
