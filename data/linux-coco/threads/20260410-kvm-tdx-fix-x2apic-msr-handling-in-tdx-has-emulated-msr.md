---
title: 'KVM: TDX: Fix x2APIC MSR handling in tdx_has_emulated_msr()'
date: 2026-04-10
last_reply: 2026-05-18
message_count: 3
participants: ['Rick Edgecombe', 'Binbin Wu', 'Sean Christopherson']
---

## [1] Rick Edgecombe — 2026-04-10

Rework tdx_has_emulated_msr() to explicitly enumerate the x2APIC MSRs
that KVM can emulate, instead of trying to enumerate the MSRs that KVM
cannot emulate. Drop the inner switch and list the emulatable x2APIC
registers directly in the outer switch's "return true" block.

The old code had multiple bugs in the x2APIC range handling.
X2APIC_MSR(APIC_ISR + APIC_ISR_NR) was incorrect because APIC_ISR_NR is
0x8, not 0x80, so the X2APIC_MSR() shift lost the lower bits, collapsing
each range to a single MSR. IA32_X2APIC_SELF_IPI was also missing from
the non-emulatable list.

KVM has no visibility into whether or not a guest has enabled #VE 
reduction, which changes which MSRs the TDX-Module handles itself versus 
triggering a #VE for the guest to make a TDVMCALL. So maintaining a list 
of non-emulatable MSRs is fragile. Listing only the MSRs KVM can always 
emulate sidesteps the problem.

Suggested-by: Sean Christopherson <seanjc@google.com>
Reported-by: Dmytro Maluka <dmaluka@chromium.org>
Fixes: dd50294f3e3c ("KVM: TDX: Implement callbacks for MSR operations")
Assisted-by: Claude:claude-opus-4-6
[based on a diff from Sean, but added missed LVTCMCI case, log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---

Thanks to Dmytro for finding this. They said to feel free to take this 
over, so here is another version with Sean's suggestions. Tested in the 
TDX CI.

In Sean's suggestion LVTCMCI was missed, so it's added here.

 arch/x86/kvm/vmx/tdx.c | 36 ++++++++++++++++++++----------------
 1 file changed, 20 insertions(+), 16 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 1e47c194af53..76ab6805ab29 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2116,23 +2116,27 @@ bool tdx_has_emulated_msr(u32 index)
 	case MSR_IA32_MC0_CTL2 ... MSR_IA32_MCx_CTL2(KVM_MAX_MCE_BANKS) - 1:
 		/* MSR_IA32_MCx_{CTL, STATUS, ADDR, MISC, CTL2} */
 	case MSR_KVM_POLL_CONTROL:
+	/*
+	 * x2APIC registers that are virtualized by the CPU can't be
+	 * emulated, KVM doesn't have access to the virtual APIC page.
+	 */
+	case X2APIC_MSR(APIC_ID):
+	case X2APIC_MSR(APIC_LVR):
+	case X2APIC_MSR(APIC_LDR):
+	case X2APIC_MSR(APIC_SPIV):
+	case X2APIC_MSR(APIC_ESR):
+	case X2APIC_MSR(APIC_LVTCMCI):
+	case X2APIC_MSR(APIC_ICR):
+	case X2APIC_MSR(APIC_LVTT):
+	case X2APIC_MSR(APIC_LVTTHMR):
+	case X2APIC_MSR(APIC_LVTPC):
+	case X2APIC_MSR(APIC_LVT0):
+	case X2APIC_MSR(APIC_LVT1):
+	case X2APIC_MSR(APIC_LVTERR):
+	case X2APIC_MSR(APIC_TMICT):
+	case X2APIC_MSR(APIC_TMCCT):
+	case X2APIC_MSR(APIC_TDCR):
 		return true;
-	case APIC_BASE_MSR ... APIC_BASE_MSR + 0xff:
-		/*
-		 * x2APIC registers that are virtualized by the CPU can't be
-		 * emulated, KVM doesn't have access to the virtual APIC page.
-		 */
-		switch (index) {
-		case X2APIC_MSR(APIC_TASKPRI):
-		case X2APIC_MSR(APIC_PROCPRI):
-		case X2APIC_MSR(APIC_EOI):
-		case X2APIC_MSR(APIC_ISR) ... X2APIC_MSR(APIC_ISR + APIC_ISR_NR):
-		case X2APIC_MSR(APIC_TMR) ... X2APIC_MSR(APIC_TMR + APIC_ISR_NR):
-		case X2APIC_MSR(APIC_IRR) ... X2APIC_MSR(APIC_IRR + APIC_ISR_NR):
-			return false;
-		default:
-			return true;
-		}
 	default:
 		return false;
 	}

---

## [2] Binbin Wu — 2026-04-13
*Subject: Re: [PATCH v2] KVM: TDX: Fix x2APIC MSR handling in
 tdx_has_emulated_msr()*

On 4/11/2026 7:26 AM, Rick Edgecombe wrote:
> Rework tdx_has_emulated_msr() to explicitly enumerate the x2APIC MSRs
> that KVM can emulate, instead of trying to enumerate the MSRs that KVM

Is it better to describe that the bug is benign for a sane guest?

> 
> KVM has no visibility into whether or not a guest has enabled #VE 

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

One nit below.

> ---
> 

Nit:
The original comment explains why certain MSRs are not emulated due to
its implementation. After the change, it lists the allowed emulated MSRs,
a quick read might give the false impression that the listed MSRs are the
ones that cannot be emulated. Maybe slightly tweak the comment to clarify
that the cases listed below are the MSRs that KVM is responsible for
emulating.


> +	case X2APIC_MSR(APIC_ID):
> +	case X2APIC_MSR(APIC_LVR):

---

## [3] Sean Christopherson — 2026-05-18
*Subject: Re: [PATCH v2] KVM: TDX: Fix x2APIC MSR handling in tdx_has_emulated_msr()*

On Fri, 10 Apr 2026 16:26:54 -0700, Rick Edgecombe wrote:
> Rework tdx_has_emulated_msr() to explicitly enumerate the x2APIC MSRs
> that KVM can emulate, instead of trying to enumerate the MSRs that KVM

Applied to kvm-x86 vmx, with a massaged comment as suggested by Binbin.  Thanks!

[1/1] KVM: TDX: Fix x2APIC MSR handling in tdx_has_emulated_msr()
      https://github.com/kvm-x86/linux/commit/1f3e69af5f93

--
https://github.com/kvm-x86/linux/tree/next

---
