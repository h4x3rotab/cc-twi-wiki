---
title: 'x86/tdx: Route safe halt execution via tdx_safe_halt()'
date: 2025-01-29
last_reply: 2025-02-04
message_count: 16
participants: ['Vishal Annapurve', 'Kirill A. Shutemov', 'Dave Hansen']
---

## [1] Vishal Annapurve — 2025-01-29

Direct HLT instruction execution causes #VEs for TDX VMs which is routed
to hypervisor via tdvmcall. This process renders HLT instruction
execution inatomic, so any preceding instructions like STI/MOV SS will
end up enabling interrupts before the HLT instruction is routed to the
hypervisor. This creates scenarios where interrupts could land during
HLT instruction emulation without aborting halt operation leading to
idefinite halt wait times.

Commit bfe6ed0c6727 ("x86/tdx: Add HLT support for TDX guests") already
upgraded x86_idle() to invoke tdvmcall to avoid such scenarios, but
it didn't cover pv_native_safe_halt() which can be invoked using
raw_safe_halt() from call sites like acpi_safe_halt().

raw_safe_halt() also returns with interrupts enabled so upgrade
tdx_safe_halt() to enable interrupts by default and ensure that paravirt
safe_halt() executions invoke tdx_safe_halt(). Earlier x86_idle() is now
handled via tdx_idle() which simply invokes tdvmcall while preserving
irq state.

To avoid future call sites which cause HLT instruction emulation with
irqs enabled, add a warn and fail the HLT instruction emulation.

Cc: stable@vger.kernel.org
Fixes: bfe6ed0c6727 ("x86/tdx: Add HLT support for TDX guests")
Signed-off-by: Vishal Annapurve <vannapurve@google.com>
---
Changes since V1:
1) Addressed comments from Dave H
   - Comment regarding adding a check for TDX VMs in halt path is not
     resolved in v2, would like feedback around better place to do so,
     maybe in pv_native_safe_halt (?).
2) Added a new version of tdx_safe_halt() that will enable interrupts.
3) Previous tdx_safe_halt() implementation is moved to newly introduced
tdx_idle().

V1: https://lore.kernel.org/lkml/Z5l6L3Hen9_Y3SGC@google.com/T/

 arch/x86/coco/tdx/tdx.c    | 23 ++++++++++++++++++++++-
 arch/x86/include/asm/tdx.h |  2 +-
 arch/x86/kernel/process.c  |  2 +-
 3 files changed, 24 insertions(+), 3 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 0d9b090b4880..cc2a637dca15 100644
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
@@ -380,13 +381,18 @@ static int handle_halt(struct ve_info *ve)
 {
 	const bool irq_disabled = irqs_disabled();
 
+	if (!irq_disabled) {
+		WARN_ONCE(1, "HLT instruction emulation unsafe with irqs enabled\n");
+		return -EIO;
+	}
+
 	if (__halt(irq_disabled))
 		return -EIO;
 
 	return ve_instr_len(ve);
 }
 
-void __cpuidle tdx_safe_halt(void)
+void __cpuidle tdx_idle(void)
 {
 	const bool irq_disabled = false;
 
@@ -397,6 +403,12 @@ void __cpuidle tdx_safe_halt(void)
 		WARN_ONCE(1, "HLT instruction emulation failed\n");
 }
 
+static void __cpuidle tdx_safe_halt(void)
+{
+	tdx_idle();
+	raw_local_irq_enable();
+}
+
 static int read_msr(struct pt_regs *regs, struct ve_info *ve)
 {
 	struct tdx_module_args args = {
@@ -1083,6 +1095,15 @@ void __init tdx_early_init(void)
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
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index eba178996d84..dd386500ab1c 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -58,7 +58,7 @@ void tdx_get_ve_info(struct ve_info *ve);
 
 bool tdx_handle_virt_exception(struct pt_regs *regs, struct ve_info *ve);
 
-void tdx_safe_halt(void);
+void tdx_idle(void);
 
 bool tdx_early_handle_ve(struct pt_regs *regs);
 
diff --git a/arch/x86/kernel/process.c b/arch/x86/kernel/process.c
index f63f8fd00a91..4083838fe4a0 100644
--- a/arch/x86/kernel/process.c
+++ b/arch/x86/kernel/process.c
@@ -933,7 +933,7 @@ void __init select_idle_routine(void)
 		static_call_update(x86_idle, mwait_idle);
 	} else if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST)) {
 		pr_info("using TDX aware idle routine\n");
-		static_call_update(x86_idle, tdx_safe_halt);
+		static_call_update(x86_idle, tdx_idle);
 	} else {
 		static_call_update(x86_idle, default_idle);
 	}

---

## [2] Kirill A. Shutemov — 2025-01-30
*Subject: Re: [PATCH V2 1/1] x86/tdx: Route safe halt execution via
 tdx_safe_halt()*

On Wed, Jan 29, 2025 at 11:25:25PM +0000, Vishal Annapurve wrote:
> Direct HLT instruction execution causes #VEs for TDX VMs which is routed
> to hypervisor via tdvmcall. This process renders HLT instruction

I think it is worth to putting this into a separate patch and not
backport. The rest of the patch is bugfix and this doesn't belong.

Otherwise, looks good to me:

Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>@linux.intel.com>

---

## [3] Vishal Annapurve — 2025-01-30
*Subject: Re: [PATCH V2 1/1] x86/tdx: Route safe halt execution via tdx_safe_halt()*

On Thu, Jan 30, 2025 at 1:28 AM Kirill A. Shutemov <kirill@shutemov.name> wrote:
>
> On Wed, Jan 29, 2025 at 11:25:25PM +0000, Vishal Annapurve wrote:

Thanks Kirill for the review.

Thinking more about this fix, now I am wondering why the efforts [1]
to move halt/safe_halt under CONFIG_PARAVIRT were abandoned. Currently
proposed fix is incomplete as it would not handle scenarios where
CONFIG_PARAVIRT_XXL is disabled. I am tilting towards reviving [1] and
requiring CONFIG_PARAVIRT for TDX VMs. WDYT?

[1] https://lore.kernel.org/lkml/20210517235008.257241-1-sathyanarayanan.kuppuswamy@linux.intel.com/

---

## [4] Kirill A. Shutemov — 2025-01-30
*Subject: Re: [PATCH V2 1/1] x86/tdx: Route safe halt execution via
 tdx_safe_halt()*

On Thu, Jan 30, 2025 at 09:24:37AM -0800, Vishal Annapurve wrote:
> On Thu, Jan 30, 2025 at 1:28 AM Kirill A. Shutemov <kirill@shutemov.name> wrote:
> >

Many people dislike paravirt callbacks. We tried to avoid relying on them
for core TDX enabling.

Can you explain the issue you see with CONFIG_PARAVIRT_XXL being disabled?
I don't think I follow.

---

## [5] Vishal Annapurve — 2025-01-30
*Subject: Re: [PATCH V2 1/1] x86/tdx: Route safe halt execution via tdx_safe_halt()*

On Thu, Jan 30, 2025 at 10:48 AM Kirill A. Shutemov
<kirill@shutemov.name> wrote:
> ...
> > >

Relevant callers of *_safe_halt() are:
1) kvm_wait() -> safe_halt() -> raw_safe_halt() -> arch_safe_halt()
2) acpi_safe_halt() -> safe_halt() -> raw_safe_halt() -> arch_safe_halt()

arch_safe_halt() can get routed to native_safe_halt if
CONFIG_PARAVIRT_XXL is disabled and will use "sti; hlt" combination
which is unsafe for TDX VMs as of now.

Either patch suggested by Sean [1] earlier or the implementation [2]
to implement safe_halt always for TDX VMs seem functionally more
correct to me. [2] being better where it avoids #VEs altogether. I
haven't come across configurations where CONFIG_PARAVIRT_XXL is
disabled but I don't see any guarantees around keeping it enabled for
TDX VMs.

[1] https://lore.kernel.org/lkml/Z5l6L3Hen9_Y3SGC@google.com/
[2] https://lore.kernel.org/lkml/20210517235008.257241-1-sathyanarayanan.kuppuswamy@linux.intel.com/

>
> --

---

## [6] Kirill A. Shutemov — 2025-01-31
*Subject: Re: [PATCH V2 1/1] x86/tdx: Route safe halt execution via
 tdx_safe_halt()*

On Thu, Jan 30, 2025 at 11:45:01AM -0800, Vishal Annapurve wrote:
> On Thu, Jan 30, 2025 at 10:48 AM Kirill A. Shutemov
> <kirill@shutemov.name> wrote:

Okay, I didn't realized that CONFIG_PARAVIRT_SPINLOCKS doesn't depend on
CONFIG_PARAVIRT_XXL.

It would be interesting to check if paravirtualized spinlocks make sense
for TDX given the cost of TD exit.

Maybe we should avoid advertising KVM_FEATURE_PV_UNHALT to the TDX guests?

> 2) acpi_safe_halt() -> safe_halt() -> raw_safe_halt() -> arch_safe_halt()

Have you checked why you get there? I don't see a reason for TDX guest to
get into ACPI idle stuff. We don't have C-states to manage.

---

## [7] Vishal Annapurve — 2025-01-31
*Subject: Re: [PATCH V2 1/1] x86/tdx: Route safe halt execution via tdx_safe_halt()*

On Fri, Jan 31, 2025 at 12:13 AM Kirill A. Shutemov
<kirill@shutemov.name> wrote:
>
> On Thu, Jan 30, 2025 at 11:45:01AM -0800, Vishal Annapurve wrote:

Are you hinting towards a model where TDX guest prohibits such call
sites from being configured? I am not sure if it's a sustainable model
if we just rely on the host not advertising these features as the
guest kernel can still add new paths that are not controlled by the
host that lead to *_safe_halt().

> > 2) acpi_safe_halt() -> safe_halt() -> raw_safe_halt() -> arch_safe_halt()
>

Apparently userspace VMM is advertising pblock_address through SSDT
tables in my configuration which causes guests to enable ACPI cpuidle
drivers. Do you know if future generations of TDX hardware will not
support different c-states for TDX VMs?

>
> --

---

## [8] Kirill A. Shutemov — 2025-02-03
*Subject: Re: [PATCH V2 1/1] x86/tdx: Route safe halt execution via
 tdx_safe_halt()*

On Fri, Jan 31, 2025 at 06:32:04PM -0800, Vishal Annapurve wrote:
> On Fri, Jan 31, 2025 at 12:13 AM Kirill A. Shutemov
> <kirill@shutemov.name> wrote:

I've asked TDX module folks to provide additional information in ve_info
to help handle STI shadow correctly. They will implement it, but it will
take some time.

So we need some kind of stopgap until we have it.

I am reluctant to commit to paravirt calls for this workaround. They will
likely stick forever. It is possible, I would like to avoid them. If not,
oh well.

> > > 2) acpi_safe_halt() -> safe_halt() -> raw_safe_halt() -> arch_safe_halt()
> >

I have very limited understanding of power management, but I don't see how
C-states can be meaningfully supported by any virtualized environment.
To me, C-states only make sense for baremetal.

---

## [9] Vishal Annapurve — 2025-02-03
*Subject: Re: [PATCH V2 1/1] x86/tdx: Route safe halt execution via tdx_safe_halt()*

On Mon, Feb 3, 2025 at 8:00 AM Kirill A. Shutemov <kirill@shutemov.name> wrote:
>
> ...

What will the final solution look like?

>
> So we need some kind of stopgap until we have it.

Does it make sense to carry the patch suggested by Sean [1] as a
stopgap for now?

[1] https://lore.kernel.org/lkml/Z5l6L3Hen9_Y3SGC@google.com/

>
> I am reluctant to commit to paravirt calls for this workaround. They will

One possibility is that host can convey guests about using "mwait" as
cstate entry mechanism as an alternative to halt if supported.

>
> --

---

## [10] Dave Hansen — 2025-02-03
*Subject: Re: [PATCH V2 1/1] x86/tdx: Route safe halt execution via
 tdx_safe_halt()*

On 1/31/25 18:32, Vishal Annapurve wrote:
...
> Are you hinting towards a model where TDX guest prohibits such call
> sites from being configured? I am not sure if it's a sustainable model

Let's say we required PARAVIRT_XXL for TDX guests and had TDX setup do:

static const typeof(pv_ops) tdx_irq_ops __initconst = {
        .irq = {
		.safe_halt = tdx_safe_halt,
	},
};

We could get rid of a _bit_ of what TDX is doing now, like:

        } else if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST)) {
                pr_info("using TDX aware idle routine\n");
                static_call_update(x86_idle, tdx_safe_halt);

and it would also fix this issue. Right?

This commit:

	bfe6ed0c6727 ("x86/tdx: Add HLT support for TDX guests")

Makes it seem totally possible:

>     Alternative choices like PV ops have been considered for adding
>     safe_halt() support. But it was rejected because HLT paravirt calls

and honestly it's seeming more "worth the cost" now since that partial
approach has a bug and might have more bugs in the future.

---

## [11] Kirill A. Shutemov — 2025-02-03
*Subject: Re: [PATCH V2 1/1] x86/tdx: Route safe halt execution via
 tdx_safe_halt()*

On Mon, Feb 03, 2025 at 09:01:41AM -0800, Vishal Annapurve wrote:
> On Mon, Feb 3, 2025 at 8:00 AM Kirill A. Shutemov <kirill@shutemov.name> wrote:
> >

VMX has GUEST_INTERRUPTIBILITY_INFO. This info is going to passed via
ve_info. Details are TBD.

With the info at hands, we can check if we are in STI shadow (regardless
of instruction) and skip interrupt enabling in that case.
 
> >
> > So we need some kind of stopgap until we have it.

I like it more than paravirt calls. And in the future, HLT check can be
replaced with STI shadow check if the info is available.

> >
> > I am reluctant to commit to paravirt calls for this workaround. They will

You don't need cpuidle for that. If MWAIT is supported, just enumerate
MWAIT to the guest and select_idle_routine() will pick it over
TDX-specific one.

---

## [12] Kirill A. Shutemov — 2025-02-03
*Subject: Re: [PATCH V2 1/1] x86/tdx: Route safe halt execution via
 tdx_safe_halt()*

On Mon, Feb 03, 2025 at 10:06:28AM -0800, Dave Hansen wrote:
> On 1/31/25 18:32, Vishal Annapurve wrote:
> ...

If we want to go this path, I would rather move safe_halt out of
PARAVIRT_XXL. PARAVIRT_XXL is kitchen sink, no new code should touch it.

But Sean's proposal with HLT check before enabling interrupts looks better
to me.

---

## [13] Dave Hansen — 2025-02-03
*Subject: Re: [PATCH V2 1/1] x86/tdx: Route safe halt execution via
 tdx_safe_halt()*

On 2/3/25 12:09, Kirill A. Shutemov wrote:
...
> But Sean's proposal with HLT check before enabling interrupts looks better
> to me.

"Sean's proposal" being this:

	https://lore.kernel.org/all/Z5l6L3Hen9_Y3SGC@google.com/

?

Is that just intended to quietly fix up a hlt-induced #VE? I'm not sure
that's a good idea. The TDVMCALL is slow, but the #VE is also presumably
quite slow. This is (presumably) getting called in an idle path which is
actually one of the most performance-sensitive things we have in the kernel.

Or am I missing the point of Sean's proposal?

I don't mind having the #VE handler warn about the situation if we end
up there accidentally.

I'd much rather have a kernel configured in a way that we are pretty
sure there's no path to even call hlt.

---

## [14] Vishal Annapurve — 2025-02-03
*Subject: Re: [PATCH V2 1/1] x86/tdx: Route safe halt execution via tdx_safe_halt()*

On Mon, Feb 3, 2025 at 1:19 PM Dave Hansen <dave.hansen@intel.com> wrote:
>
> On 2/3/25 12:09, Kirill A. Shutemov wrote:
Yes.

>
> Is that just intended to quietly fix up a hlt-induced #VE? I'm not sure

I think you have captured the intent correctly.

>
> I don't mind having the #VE handler warn about the situation if we end

+1.

---

## [15] Dave Hansen — 2025-02-04
*Subject: Re: [PATCH V2 1/1] x86/tdx: Route safe halt execution via
 tdx_safe_halt()*

I think this is the right fix for _now_. In practice, Vishal's problem
only occurs on CONFIG_PARAVIRT_XXL systems. His proposed fix here does
not make TDX depend on CONFIG_PARAVIRT_XXL, it just provides an extra
override when TDX and CONFIG_PARAVIRT_XXL collide.

This seems like a reasonable compromise that avoids entangling
PARAVIRT_XXL and TDX _too_ much and also avoids reinventing a hunk of
PARAVIRT_XXL just to fix this bug.

Long-term, I think it would be nice to move pv_ops.irq.safe_halt() away
from being a paravirt thing and move it over to a plain static_call().

Then, TDX can get rid of this hunk:

                pr_info("using TDX aware idle routine\n");
                static_call_update(x86_idle, tdx_safe_halt);

and move back to default_idle() which could look like this:

 void __cpuidle default_idle(void)
 {
-        raw_safe_halt();
+	 static_call(x86_safe_halt)();
         raw_local_irq_disable();
 }

If 'x86_safe_halt' was the only route in the kernel to call 'sti;hlt'
then we can know with pretty high confidence if TDX or Xen code sets
their own 'x86_safe_halt' that they won't run into more bugs like this one.

On to the patch itself...

On 1/29/25 15:25, Vishal Annapurve wrote:
> Direct HLT instruction execution causes #VEs for TDX VMs which is routed
> to hypervisor via tdvmcall. This process renders HLT instruction

Vishal! I'm noticing spelling issues right up front and center here,
just like in v1. I think I asked nicely last time if you could start
spell checking your changelogs before posting v2. Any chance you could
actually put some spell checking in place before v3?

So, the x86 STI-shadow mechanism has left a trail of tears. We don't
want to explain the whole sordid tale here, but I don't feel like
talking about the "what" (atomic vs. inatomic execution) without
explaining "why" is really sufficient to explain the problem at hand.

Sean had a pretty concise description in here that I liked:

	https://lore.kernel.org/all/Z5l6L3Hen9_Y3SGC@google.com/

But the net result is that it is currently unsafe for TDX guests to use
the "sti;hlt" sequence. It's really important to say *that* somewhere.

> Commit bfe6ed0c6727 ("x86/tdx: Add HLT support for TDX guests") already
> upgraded x86_idle() to invoke tdvmcall to avoid such scenarios, but

Does this convey the same thing?

Commit bfe6ed0c6727 ("x86/tdx: Add HLT support for TDX guests")
prevented the idle routines from using "sti;hlt". But it missed the
paravirt routine. That can be reached like this, for example:

	acpi_safe_halt() =>
	raw_safe_halt()  =>
	arch_safe_halt() =>
	irq.safe_halt()  =>
	pv_native_safe_halt()

I also dislike the "upgrade" nomenclature. It's not really an "upgrade".

...
> @@ -380,13 +381,18 @@ static int handle_halt(struct ve_info *ve)
>  {

The warning is fine, but I do think it should be separated from the bug fix.

>  
> -void __cpuidle tdx_safe_halt(void)

The naming here is a bit wonky. Think of how the call chain will look:

	irq.safe_halt() =>
	tdx_safe_halt() =>
	tdx_idle()	=>
	__halt()

See how it's doing a more and more TDX-specific halt operation? Isn't
the "idle" call right in the middle confusing?

>  static int read_msr(struct pt_regs *regs, struct ve_info *ve)
>  {

Just like the changelog, it's hard to write a good comment without going
into the horrors of the STI-shadow. But I think this is a bit more to
the point:

	/*
	 * Avoid the literal hlt instruction in TDX guests. hlt will
	 * induce a #VE in the STI-shadow which will enable interrupts
	 * in a place where they are not wanted.
	 */

---

## [16] Vishal Annapurve — 2025-02-04
*Subject: Re: [PATCH V2 1/1] x86/tdx: Route safe halt execution via tdx_safe_halt()*

On Tue, Feb 4, 2025 at 9:32 AM Dave Hansen <dave.hansen@intel.com> wrote:
>
> I think this is the right fix for _now_. In practice, Vishal's problem
To ensure that we spend a bit more time here, would folks be ok with
making TDX depend on CONFIG_PARAVIRT_XXL as a stopgap until we have
the long term proposal Dave mentioned below to cleanly separate
"pv_ops.irq.safe_halt()" from paravirt infra?

>
> Long-term, I think it would be nice to move pv_ops.irq.safe_halt() away

Yeah, will do. I incorrectly thought that codespell runs by default
with checkpatch.pl.

>
> So, the x86 STI-shadow mechanism has left a trail of tears. We don't
Ack.

> > Commit bfe6ed0c6727 ("x86/tdx: Add HLT support for TDX guests") already
> > upgraded x86_idle() to invoke tdvmcall to avoid such scenarios, but
Ack.
>
> ...
Makes sense.

>
> >  static int read_msr(struct pt_regs *regs, struct ve_info *ve)

Ack, will take care of these comments in v3.

---
