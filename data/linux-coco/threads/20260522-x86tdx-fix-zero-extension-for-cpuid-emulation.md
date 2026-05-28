---
title: '[PATCH] x86/tdx: Fix zero-extension for CPUID emulation'
date: 2026-05-22
last_reply: 2026-05-22
message_count: 1
participants: ['Christian Ludloff']
---

## [1] Christian Ludloff — 2026-05-22

On Tue, May 12, 2026 at 03:14:54PM -0700, Dave Hansen wrote:
> CPUID (the instruction) is defined to fill in eax/ebx/ecx/edx.

In the original x64 spec CPUID inherited 32-bit op size from
the pre-x64 days, and although established leaves might all
have followed that definition, the ISA per se doesn't prohibit
an implementation that allows, or defaults to, 64-bit op size.

Having made that statement... the same does go for MSRs.

> Those are 32-bit registers so the normal register rules apply:
> "32-bit operands generate a 32-bit result, zero-extended to a

...in PM64 ...while outside PM64 and across mode switches
the upper 32 bits are explicitly undefined. Needless to say...
SMM and then VMX and SVM had to violate that to function.

> So a properly-behaving CPUID implementation will always end
> up with the top 32 bits empty on the four CPUID registers after

True for a "32-bit op size" implementation. Maybe insert that.

--
C.

---
