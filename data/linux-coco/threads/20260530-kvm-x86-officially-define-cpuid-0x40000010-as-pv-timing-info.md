---
title: '[PATCH v4 15/47] KVM: x86: Officially define CPUID 0x40000010 as\n PV Timing Info (TSC and Bus)'
date: 2026-05-30
last_reply: 2026-05-30
message_count: 1
participants: ['Christian Ludloff']
---

## [1] Christian Ludloff — 2026-05-30

> + *  # EAX: (Virtual) TSC frequency in kHz.
> + *  # EBX: (Virtual) Bus (local APIC timer) frequency in kHz.

Can someone from Broadcom please speak up as to
what a non-ECX value signifies for their HV? (Asking
because I see a value of 2, not a must-be-zero.)

--
C.

---
