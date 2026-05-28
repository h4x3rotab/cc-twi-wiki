---
title: 'x86/tdx: Fix zero-extension for CPUID emulation'
date: 2026-05-12
last_reply: 2026-05-22
message_count: 9
participants: ['Carlos López', 'Edgecombe, Rick P', 'Dave Hansen', 'Kiryl Shutsemau']
---

## [1] Carlos López — 2026-05-12

In the x86 architecture, 32-bit operations zero-extend the result in the
destination register to 64 bits. This includes the CPUID instruction,
which writes 32-bit values EAX/EBX/ECX/EDX.

When handling the CPUID instruction via #VE, copy only the lower 32-bits
provided by the hypervisor for the output registers, and zero out the
upper half.

Fixes: c141fa2c2bba ("x86/tdx: Handle CPUID via #VE")
Cc: stable@vger.kernel.org
Signed-off-by: Carlos López <clopez@suse.de>
---
 arch/x86/coco/tdx/tdx.c | 8 ++++----
 1 file changed, 4 insertions(+), 4 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index c8b9e86d0488..a2fe1ae019bd 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -543,10 +543,10 @@ static int handle_cpuid(struct pt_regs *regs, struct ve_info *ve)
 	 * EAX, EBX, ECX, EDX registers after the CPUID instruction execution.
 	 * So copy the register contents back to pt_regs.
 	 */
-	regs->ax = args.r12;
-	regs->bx = args.r13;
-	regs->cx = args.r14;
-	regs->dx = args.r15;
+	regs->ax = lower_32_bits(args.r12);
+	regs->bx = lower_32_bits(args.r13);
+	regs->cx = lower_32_bits(args.r14);
+	regs->dx = lower_32_bits(args.r15);
 
 	return ve_instr_len(ve);
 }

---

## [2] Edgecombe, Rick P — 2026-05-12
*Subject: Re: [PATCH] x86/tdx: Fix zero-extension for CPUID emulation*

On Tue, 2026-05-12 at 23:37 +0200, Carlos López wrote:
> In the x86 architecture, 32-bit operations zero-extend the result in the
> destination register to 64 bits. This includes the CPUID instruction,

Can you explain the impact here? Why should the guest fixup what the VMM
emulates?

---

## [3] Dave Hansen — 2026-05-12
*Subject: Re: [PATCH] x86/tdx: Fix zero-extension for CPUID emulation*

On 5/12/26 14:48, Edgecombe, Rick P wrote:
>> -	regs->ax = args.r12;
>> -	regs->bx = args.r13;

Oh boy.

args.r12-15 come from the VMM, right? So the VMM Can put whatever it
wants in there.

CPUID (the instruction) is defined to fill in eax/ebx/ecx/edx. Those are
32-bit registers so the normal register rules apply: "32-bit operands
generate a 32-bit result, zero-extended to a 64-bit result in the
destination general-purpose register."

So a properly-behaving CPUID implementation will always end up with the
top 32 bits empty on the four CPUID registers after a CPUID is executed.

The VMM here obviously might be naughty and might put gunk in
args.r12/r13/r14/r15 that gets copied to ptregs->ax/bx/cx/dx which are
'unsigned long' on 64-bit.

The end result is that a TDX guest can use CPUID and end up having bits
set in rax/rbx/rcx/rdx that are architecturally impossible. This patch
is effectively fixing up the VMM naughtiness before the guest CPUID
instance can see it.

Does anybody disagree with any of that?

Do we *want* to fix this up silently? If we catch a malicious VMM trying
to stuff garbage into the guest, shouldn't we be a bit more upset than
silently papering over it?

---

## [4] Carlos López — 2026-05-13
*Subject: Re: [PATCH] x86/tdx: Fix zero-extension for CPUID emulation*

On 5/12/26 11:48 PM, Edgecombe, Rick P wrote:
> On Tue, 2026-05-12 at 23:37 +0200, Carlos López wrote:
>> In the x86 architecture, 32-bit operations zero-extend the result in the

It's a correctness issue. The CPUID instruction has 32-bit operands,
which should be zero extended as per the SDM. Other code like read_msr()
in that same file does the same zero-extension. There was also a patch
sent for a similar issue in handle_in() not that long ago.

In terms of how this could materialize, if you have code like this:

	asm volatile("cpuid"
	    : "=a" (eax),
	      "=b" (ebx),
	      "=c" (ecx),
	      "=d" (edx)
	    : "0" (eax), "2" (ecx)
	    : "memory");

The compiler would be allowed to assume that e.g. RAX can be used as an
already-zero-extended register.

Best,
Carlos

---

## [5] Edgecombe, Rick P — 2026-05-12
*Subject: Re: [PATCH] x86/tdx: Fix zero-extension for CPUID emulation*

On Tue, 2026-05-12 at 15:14 -0700, Dave Hansen wrote:
> The end result is that a TDX guest can use CPUID and end up having bits
> set in rax/rbx/rcx/rdx that are architecturally impossible. This patch

A naughty VMM could mess with the guest in a number of ways though. For example
setting impossible bits in specific leafs in the lower 32 bits. This patch is a
relatively simple sanity check compared to a complete check of CPUID arch
matching (or MSR, etc) of course.

> 
> Does anybody disagree with any of that?

I agree a warning would be appropriate. This should probably trigger a bug fix
in the VMM. For example, BIOS might hit it too. So I kind of wonder, how
valuable is catching this specific bug in the guest? Do we need to worry about
the specific issue for some reason?

On the other hand, the #VE handler is supposed to do the emulation of the
instruction, with the help of the TDVMCALL, so maybe the correctness should be
in the guest... Hmm...

---

## [6] Carlos López — 2026-05-13
*Subject: Re: [PATCH] x86/tdx: Fix zero-extension for CPUID emulation*

On 5/13/26 12:14 AM, Dave Hansen wrote:
> On 5/12/26 14:48, Edgecombe, Rick P wrote:
>>> -	regs->ax = args.r12;

Yes, exactly.

> CPUID (the instruction) is defined to fill in eax/ebx/ecx/edx. Those are
> 32-bit registers so the normal register rules apply: "32-bit operands

Okay, how about this (on top of the changes I already sent)?

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 831475cf4313..cd33781c8d61 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -538,6 +538,13 @@ static int handle_cpuid(struct pt_regs *regs, struct ve_info *ve)
        if (__tdx_hypercall(&args))
                return -EIO;
 
+       /* Emit a warning if the hypervisor tries to inject architecturally
+        * invalid (non-zero-extended) output values for CPUID */
+       if (upper_32_bits(args.r12) || upper_32_bits(args.r13)
+           || upper_32_bits(args.r14) || upper_32_bits(args.r15))
+               pr_warn("detected invalid CPUID result from VMM: eax=%lld ebx=%lld ecx=%lld edx=%lld",
+                                       args.r12, args.r13, args.r14, args.r15);
+
        /*
         * As per TDX GHCI CPUID ABI, r12-r15 registers contain contents of
         * EAX, EBX, ECX, EDX registers after the CPUID instruction execution.

---

## [7] Dave Hansen — 2026-05-12
*Subject: Re: [PATCH] x86/tdx: Fix zero-extension for CPUID emulation*

On 5/12/26 15:24, Edgecombe, Rick P wrote:
> On the other hand, the #VE handler is supposed to do the emulation of the
> instruction, with the help of the TDVMCALL, so maybe the correctness should be

Maybe we should just change the GHCI spec.

What if we said:

 | Operand 	       | ... |
 | R12 (lower 32 bits) | EAX |
 | R13 (lower 32 bits) | EBX |
 | R14 (lower 32 bits) | ECX |
 | R15 (lower 32 bits) | EDX |

Then said the upper 32 bits are undefined. Then the kernel *must* mask
them to be correct. Then we don't have to do any checking at all and
there's no ambiguity about what the VMM is allowed to do or what chaos
it might cause.

---

## [8] Edgecombe, Rick P — 2026-05-12
*Subject: Re: [PATCH] x86/tdx: Fix zero-extension for CPUID emulation*

On Tue, 2026-05-12 at 15:37 -0700, Dave Hansen wrote:
> On 5/12/26 15:24, Edgecombe, Rick P wrote:
> > On the other hand, the #VE handler is supposed to do the emulation of the

Hmm, let me check. It intersects with the other guests/hosts, but hard to see
how the other ones could be out of spec and not be buggy.

---

## [9] Kiryl Shutsemau — 2026-05-22
*Subject: Re: [PATCH] x86/tdx: Fix zero-extension for CPUID emulation*

On Tue, May 12, 2026 at 03:14:54PM -0700, Dave Hansen wrote:
> On 5/12/26 14:48, Edgecombe, Rick P wrote:
> >> -	regs->ax = args.r12;

Not really.

But note that the exposure is minimal as we do not issue hypercalls to
VMM for anything outside of hypervisor range. I am not sure stable@ is
justified, but worth fixing.

---
