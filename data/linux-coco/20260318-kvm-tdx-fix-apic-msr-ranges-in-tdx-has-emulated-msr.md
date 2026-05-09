---
title: 'KVM: TDX: Fix APIC MSR ranges in tdx_has_emulated_msr()'
date: 2026-03-18
last_reply: 2026-04-06
message_count: 14
participants: ['Dmytro Maluka', 'Dave Hansen', 'Binbin Wu', 'Edgecombe, Rick P', 'Sean Christopherson']
---

## [1] Dmytro Maluka — 2026-03-18

Note: compile-tested only. Bug found by code inspection.

X2APIC_MSR(APIC_xxx + APIC_ISR_NR) is incorrect, since APIC_ISR_NR is
0x8, not 0x80, so shifting it in X2APIC_MSR() results in losing those
lower bits, making it simply equal to X2APIC_MSR(APIC_xxx), i.e. making
the entire range consist of APIC_xxx only. So adding APIC_ISR_NR needs
to be outside X2APIC_MSR().

Additionally, since "..." ranges are inclusive, need to subtract 1.

Fixes: dd50294f3e3c ("KVM: TDX: Implement callbacks for MSR operations")
Signed-off-by: Dmytro Maluka <dmaluka@chromium.org>
---
 arch/x86/kvm/vmx/tdx.c | 6 +++---
 1 file changed, 3 insertions(+), 3 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index c5065f84b78b..466a7de660c2 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2136,9 +2136,9 @@ bool tdx_has_emulated_msr(u32 index)
 		case X2APIC_MSR(APIC_TASKPRI):
 		case X2APIC_MSR(APIC_PROCPRI):
 		case X2APIC_MSR(APIC_EOI):
-		case X2APIC_MSR(APIC_ISR) ... X2APIC_MSR(APIC_ISR + APIC_ISR_NR):
-		case X2APIC_MSR(APIC_TMR) ... X2APIC_MSR(APIC_TMR + APIC_ISR_NR):
-		case X2APIC_MSR(APIC_IRR) ... X2APIC_MSR(APIC_IRR + APIC_ISR_NR):
+		case X2APIC_MSR(APIC_ISR) ... X2APIC_MSR(APIC_ISR) + APIC_ISR_NR - 1:
+		case X2APIC_MSR(APIC_TMR) ... X2APIC_MSR(APIC_TMR) + APIC_ISR_NR - 1:
+		case X2APIC_MSR(APIC_IRR) ... X2APIC_MSR(APIC_IRR) + APIC_ISR_NR - 1:
 			return false;
 		default:
 			return true;

---

## [2] Dave Hansen — 2026-03-18
*Subject: Re: [PATCH] KVM: TDX: Fix APIC MSR ranges in tdx_has_emulated_msr()*

On 3/18/26 12:01, Dmytro Maluka wrote:
> +		case X2APIC_MSR(APIC_ISR) ... X2APIC_MSR(APIC_ISR) + APIC_ISR_NR - 1:
> +		case X2APIC_MSR(APIC_TMR) ... X2APIC_MSR(APIC_TMR) + APIC_ISR_NR - 1:

Thanks for the patch, Dmytro.

<sigh>

So this code never worked (at least for a big chunk of the ranges.
Isaku, could you please go try to figure out if there are tests for this
somewhere, and why this never bit us?

It might also be handy to have a:

#define X2APIC_LAST_MSR(r)	(X2APIC_MSR(x)+APIC_ISR_NR-1)

so that the resulting code is a bit more readable:

	case X2APIC_MSR(APIC_IRR) ... X2APIC_LAST_MSR(APIC_IRR):

Dmytro, if you feel a burning need to respin this, don't let me stop
you. I can probably just fix this up when it gets applied, or Isaku can
make those changes and resend it too.

---

## [3] Dmytro Maluka — 2026-03-18
*Subject: Re: [PATCH] KVM: TDX: Fix APIC MSR ranges in tdx_has_emulated_msr()*

On Wed, Mar 18, 2026 at 12:42:59PM -0700, Dave Hansen wrote:
> It might also be handy to have a:
> 

Sure, please feel free to take over this. I even have no way to test it
anyway. :)

I'm hesitating whether X2APIC_LAST_MSR would be the best name for it,
given that it is for ISR/IRR/TMR only and is using APIC_ISR_NR (so
maybe, don't know, X2APIC_LAST_ISR_MSR?).

---

## [4] Binbin Wu — 2026-03-19
*Subject: Re: [PATCH] KVM: TDX: Fix APIC MSR ranges in tdx_has_emulated_msr()*

On 3/19/2026 3:42 AM, Dave Hansen wrote:
> On 3/18/26 12:01, Dmytro Maluka wrote:
>> +		case X2APIC_MSR(APIC_ISR) ... X2APIC_MSR(APIC_ISR) + APIC_ISR_NR - 1:

The bug doesn't cause problems for TDs because:
- These x2apic MSRs (TASKPRI, PROCPRI, EOI, ISRx, TMRx, IRRx) are virtualized by CPU,
  when a TD accesses these MSRs, it doesn't cause #VE, thus no TDVMCALL from the TD to
  request the emulation of these MSRs.
- The bug make the "false" range of APIC MSRs smaller, so it doesn't impact the result
  for the rest of the APIC MSRs.

The bug could be triggered if a TD issues a TDVMCALL directly to request the
read/write operations for these x2apic MSRs, but a sane TD will not do it. 

Currently, we don't have dedicated KVM selftests code to call TDVMCALL directly to request
the emulation for these x2apic MSRs.

> 
> It might also be handy to have a:

---

## [5] Dave Hansen — 2026-03-18
*Subject: Re: [PATCH] KVM: TDX: Fix APIC MSR ranges in tdx_has_emulated_msr()*

On 3/18/26 18:14, Binbin Wu wrote:
> The bug doesn't cause problems for TDs because:
> - These x2apic MSRs (TASKPRI, PROCPRI, EOI, ISRx, TMRx, IRRx) are virtualized by CPU,

Could we fix this up so that the code that's there is actually usable
and testable, please?

---

## [6] Binbin Wu — 2026-03-19
*Subject: Re: [PATCH] KVM: TDX: Fix APIC MSR ranges in tdx_has_emulated_msr()*

On 3/19/2026 9:48 AM, Dave Hansen wrote:
> On 3/18/26 18:14, Binbin Wu wrote:
>> The bug doesn't cause problems for TDs because:

tdx_has_emulated_msr() is used by KVM to decide whether to emulate a MSR access from the
TDVMCALL or just return the error code.

During an off-list discussion, Rick noted that #VE reduction could change the behavior of
accessing an MSR (e.g., from #VE to #GP or to be virtualized by the TDX module) without
KVM knowing.Because KVM lacks the full context to perfectly decide if an MSR should be
emulated, the question was raised: Can we just delete tdx_has_emulated_msr() entirely?

However, these native type x2apic MSRs are a special case. Since the TDX module owns the
APICv page, KVM cannot emulate these MSRs. If we remove tdx_has_emulated_msr(), a guest
directly issuing TDVMCALLs for these native type x2apic MSRs will trigger a silent failure,
even though this is the guest's fault.

It comes down to a tradeoff. Should we prioritize code simplicity by dropping the function,
or keep it to explicitly catch this misbehaving guest corner case?


BTW, besides the bug described by this patch, according to the latest published TDX module
ABI table, MSR IA32_X2APIC_SELF_IPI is native type, but not included in the list.
There are some MSRs, which are reserved for xAPIC MSR, not included in the list, but they
can be covered by the KVM common code.

---

## [7] Edgecombe, Rick P — 2026-03-19
*Subject: Re: [PATCH] KVM: TDX: Fix APIC MSR ranges in tdx_has_emulated_msr()*

On Thu, 2026-03-19 at 15:40 +0800, Binbin Wu wrote:
> tdx_has_emulated_msr() is used by KVM to decide whether to emulate a MSR access from the
> TDVMCALL or just return the error code.

I think from KVM's perspective it doesn't want to help the guest behave
correctly. So we can ignore that I think. But it does really care to not define
any specific guest ABI that it has to maintain. So tdx_has_emulated_msr() has
some value there. And even more, it wants to not allow the guest to hurt the
host.

On the latter point, another problem with deleting tdx_has_emulated_msr() is the
current code path skips the checks done in the other MSR paths. So we would need
to call some appropriate higher up MSR helper to protect the host? And that
wades into the CPUID bit consistency issues.

So maybe... could we do a more limited version of the deletion where we allow
all the APIC MSRs through? We'd have to check that it won't cause problems.

Failing that, we should maybe just explicitly list the ones TDX supports rather
than the current way we define the APIC ones. As you mention below, it's not
correct in other ways too so it could be more robust.

> 
>

---

## [8] Sean Christopherson — 2026-04-03
*Subject: Re: [PATCH] KVM: TDX: Fix APIC MSR ranges in tdx_has_emulated_msr()*

On Thu, Mar 19, 2026, Rick P Edgecombe wrote:
> On Thu, 2026-03-19 at 15:40 +0800, Binbin Wu wrote:
> > tdx_has_emulated_msr() is used by KVM to decide whether to emulate a MSR access from the

Uh, yes KVM does does.  KVM is responsible for emulating the APIC timer, isn't it?

> So we can ignore that I think. But it does really care to not define
> any specific guest ABI that it has to maintain. So tdx_has_emulated_msr() has

What?  No.  KVM can't get actually read/write most (all?) MSRs, allowing access
is far worse than returning an error, as for all intents and purposes KVM will
silently drop writes, and return garbage on reads.

> Failing that, we should maybe just explicitly list the ones TDX supports rather
> than the current way we define the APIC ones. As you mention below, it's not

No?  Don't we just want to allow access to MSRs that aren't accelerated?  What
the TDX-Module supports is largely irrelevant, I think.

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 1e47c194af53..28e87630870b 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2116,23 +2116,26 @@ bool tdx_has_emulated_msr(u32 index)
        case MSR_IA32_MC0_CTL2 ... MSR_IA32_MCx_CTL2(KVM_MAX_MCE_BANKS) - 1:
                /* MSR_IA32_MCx_{CTL, STATUS, ADDR, MISC, CTL2} */
        case MSR_KVM_POLL_CONTROL:
+       /*
+        * x2APIC registers that are virtualized by the CPU can't be
+        * emulated, KVM doesn't have access to the virtual APIC page.
+        */
+       case X2APIC_MSR(APIC_ID):
+       case X2APIC_MSR(APIC_LVR):
+       case X2APIC_MSR(APIC_LDR):
+       case X2APIC_MSR(APIC_SPIV):
+       case X2APIC_MSR(APIC_ESR):
+       case X2APIC_MSR(APIC_ICR):
+       case X2APIC_MSR(APIC_LVTT):
+       case X2APIC_MSR(APIC_LVTTHMR):
+       case X2APIC_MSR(APIC_LVTPC):
+       case X2APIC_MSR(APIC_LVT0):
+       case X2APIC_MSR(APIC_LVT1):
+       case X2APIC_MSR(APIC_LVTERR):
+       case X2APIC_MSR(APIC_TMICT):
+       case X2APIC_MSR(APIC_TMCCT):
+       case X2APIC_MSR(APIC_TDCR):
                return true;
-       case APIC_BASE_MSR ... APIC_BASE_MSR + 0xff:
-               /*
-                * x2APIC registers that are virtualized by the CPU can't be
-                * emulated, KVM doesn't have access to the virtual APIC page.
-                */
-               switch (index) {
-               case X2APIC_MSR(APIC_TASKPRI):
-               case X2APIC_MSR(APIC_PROCPRI):
-               case X2APIC_MSR(APIC_EOI):
-               case X2APIC_MSR(APIC_ISR) ... X2APIC_MSR(APIC_ISR + APIC_ISR_NR):
-               case X2APIC_MSR(APIC_TMR) ... X2APIC_MSR(APIC_TMR + APIC_ISR_NR):
-               case X2APIC_MSR(APIC_IRR) ... X2APIC_MSR(APIC_IRR + APIC_ISR_NR):
-                       return false;
-               default:
-                       return true;
-               }
        default:
                return false;
        }

---

## [9] Edgecombe, Rick P — 2026-04-03
*Subject: Re: [PATCH] KVM: TDX: Fix APIC MSR ranges in tdx_has_emulated_msr()*

On Fri, 2026-04-03 at 09:30 -0700, Sean Christopherson wrote:
> On Thu, Mar 19, 2026, Rick P Edgecombe wrote:
> > On Thu, 2026-03-19 at 15:40 +0800, Binbin Wu wrote:

Yea totally. We need to emulate the interface accurately. But we are kind of
making up the contract after the fact. If the guest performs the wrong type of
MSR write, should we make the contract that the VMM should help it catch it's
mistake?

> 
> > So we can ignore that I think. But it does really care to not define

Not sure if I might be missing the point here. As above, we don't have enough
info to know which MSRs are accelerated. If the guest enabled #VE reduction, it
changes which ones are accelerated and the VMM is not notified. I think the
below is a sane limitation, but doesn't lets KVM perfectly notify the guest when
it screws up.

So the line would be to block MSRs that can never be emulated.

BTW, I've been treating this secret contract change as an arch mistake to at
least not build on. It's a whole subject though... Let me know if you are
interested in the details.

> 
> diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c

---

## [10] Sean Christopherson — 2026-04-03
*Subject: Re: [PATCH] KVM: TDX: Fix APIC MSR ranges in tdx_has_emulated_msr()*

On Fri, Apr 03, 2026, Rick P Edgecombe wrote:
> On Fri, 2026-04-03 at 09:30 -0700, Sean Christopherson wrote:
> > > > It comes down to a tradeoff. Should we prioritize code simplicity by dropping the function,

What does the "accleration" in that case?  Or does it reduce which ones are
accelerated?

> I think the below is a sane limitation, but doesn't lets KVM perfectly notify
> the guest when it screws up.

---

## [11] Edgecombe, Rick P — 2026-04-03
*Subject: Re: [PATCH] KVM: TDX: Fix APIC MSR ranges in tdx_has_emulated_msr()*

On Fri, 2026-04-03 at 12:07 -0700, Sean Christopherson wrote:
> > > No?  Don't we just want to allow access to MSRs that aren't accelerated? 
> > > What the TDX-Module supports is largely irrelevant, I think.

I mean ones where wrmsr is handled by the TDX module instead of generating a #VE
that gets morphed into TDVMCALL by the guest. Actually usually called "native",
but I just reused your "accelerated" term from the mail.

So... "Reduced #VE" (also called "VE reduction") reduces which things cause a
#VE. The guest opts into it and the TDX module starts behaving differently. It's
kind of grab bag of changes including changing CPUID behavior, which is another
wrinkle. It was intended to fixup guest side TDX arch issues.

---

## [12] Sean Christopherson — 2026-04-03
*Subject: Re: [PATCH] KVM: TDX: Fix APIC MSR ranges in tdx_has_emulated_msr()*

On Fri, Apr 03, 2026, Rick P Edgecombe wrote:
> On Fri, 2026-04-03 at 12:07 -0700, Sean Christopherson wrote:
> > > > No?  Don't we just want to allow access to MSRs that aren't accelerated? 

It's neither.  Precision matters here, otherwise I can't follow along.  Accelerated
means the CPU virtualizes it without software involvement.  Native would mean the
guest has direct access to bare metal hardware.  IIUC, what's happening here is
that the TDX-Module is emulating x2APIC stuff.

> So... "Reduced #VE" (also called "VE reduction") reduces which things cause a
> #VE. The guest opts into it and the TDX module starts behaving differently. It's

And KVM has no visilibity into which mode the guest has selected?  That's awful.

If KVM has no visiblity, then I don't see an option other than for KVM to advertise
and emulate what it can at all times, and it becomes the guest's responsibility
to not screw up.  I guess it's not really any different from not trying to use
MMIO accesses after switching to x2APIC mode.

---

## [13] Edgecombe, Rick P — 2026-04-04
*Subject: Re: [PATCH] KVM: TDX: Fix APIC MSR ranges in tdx_has_emulated_msr()*

On Fri, 2026-04-03 at 16:07 -0700, Sean Christopherson wrote:
> > I mean ones where wrmsr is handled by the TDX module instead of generating a
> > #VE that gets morphed into TDVMCALL by the guest. Actually usually called

Oh, sorry. 

> IIUC, what's happening here is that the TDX-Module is emulating x2APIC stuff.

I'll stick to this language. The tdx docs call them differently of course.
"native" there is about #VE or not. So I can talk about it with respect to VE or
!VE.

> 
> > So... "Reduced #VE" (also called "VE reduction") reduces which things cause

Yea, on both accounts. So where we are at with this is, starting to reject
changes that build on the pattern. We haven't gone so far as to ask for a
feature to notify the host of the guest opt-ins. But I wouldn't say we have a
grand design in mind either. If you have any clarity, please feel free to drop a
quotable.

> 
> If KVM has no visiblity, then I don't see an option other than for KVM to

Like your diff? Expose any MSRs that might be emulated in the TDX paradigm. But
don't expose all MSRs that KVM supports.

---

## [14] Sean Christopherson — 2026-04-06
*Subject: Re: [PATCH] KVM: TDX: Fix APIC MSR ranges in tdx_has_emulated_msr()*

On Sat, Apr 04, 2026, Rick P Edgecombe wrote:
> On Fri, 2026-04-03 at 16:07 -0700, Sean Christopherson wrote:
> > > So... "Reduced #VE" (also called "VE reduction") reduces which things cause

I got nothing, probably best to just deal with things on a case-by-case basis
unless we end up with a recurring theme.

> > If KVM has no visiblity, then I don't see an option other than for KVM to
> > advertise and emulate what it can at all times, and it becomes the guest's

Yep.

---
