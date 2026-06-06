---
title: '[PATCH v4 18/47] x86/kvm: Get local APIC bus frequency from PV\n CPUID Timing Info'
date: 2026-06-01
last_reply: 2026-06-01
message_count: 1
participants: ['David Woodhouse']
---

## [1] David Woodhouse — 2026-06-01

On Fri, 29 May 2026 11:24:50 -0700, Sean Christopherson wrote:
> On Fri, May 29, 2026, sashiko-bot@kernel.org wrote:
> > > diff --git a/arch/x86/kernel/kvm.c b/arch/x86/kernel/kvm.c

Yep.

> But this problem pre-exits in almost every other path that sets lapic_timer_period.
> So while I tried to avoid doing yet more tangentially related cleanup, it seems

Yay, more patches!

Reviewed-by: David Woodhouse <dwmw@amazon.co.uk>

---
