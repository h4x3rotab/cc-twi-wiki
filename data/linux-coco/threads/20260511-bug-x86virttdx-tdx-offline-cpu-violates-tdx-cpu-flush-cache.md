---
title: '[BUG] x86/virt/tdx: tdx_offline_cpu() violates tdx_cpu_flush_cache()\n preemption assert'
date: 2026-05-11
last_reply: 2026-05-12
message_count: 2
participants: ['David CARLIER', 'Huang, Kai']
---

## [1] David CARLIER — 2026-05-11

Hi,

  In commit 597bdf6e068e ("x86/virt/tdx: Pull kexec cache flush logic into
  arch/x86"), tdx_offline_cpu() gained a call to tdx_cpu_flush_cache(),
  which starts with lockdep_assert_preemption_disabled().

  tdx_offline_cpu() is registered at CPUHP_AP_ONLINE_DYN. ONLINE-section
  teardown callbacks run from the pinned per-CPU hotplug thread with
  preemption and interrupts enabled (Documentation/core-api/cpu_hotplug.rst,
  and cpuhp_thread_fun() only disables IRQs for atomic states).

  The other callers — tdx_shutdown_cpu() via on_each_cpu(), and the
  crash path — satisfy the assertion. Only the offline path doesn't, and
  the splat should fire on every offline once the TDX module is
  initialized and the done: path is taken.

  Wrapping the call with preempt_disable() / preempt_enable() at the
  offline site keeps the contract for the kexec/shutdown callers.

  Not yet reproduced on a debug kernel; reporting on inspection.

  Fixes: 597bdf6e068e ("x86/virt/tdx: Pull kexec cache flush logic
into arch/x86")

  Cheers,
  David

---

## [2] Huang, Kai — 2026-05-12
*Subject: Re: [BUG] x86/virt/tdx: tdx_offline_cpu() violates
 tdx_cpu_flush_cache() preemption assert*

On Mon, 2026-05-11 at 22:33 +0100, David CARLIER wrote:
> Hi,
> 


Right the lockdep_assert_preemption_disabled() is wrong when
tdx_cpu_flush_cache() is called from CPUHP context (there's no functionality
issue, though, it's just the lockdep assertion is wrong).

It was introduced when the TDX host kexec support was added, so the above commit
is not the right one to blame.  Previously the tdx_cpu_flush_cache() was called
from KVM's module unload path, also via the CPUHP context.  The commit above
only moved it to TDX core's CPU offline path.

The latest version to fix is:

https://lore.kernel.org/lkml/20260407233333.1608820-1-kai.huang@intel.com/

but it needs rebasing now.

---
