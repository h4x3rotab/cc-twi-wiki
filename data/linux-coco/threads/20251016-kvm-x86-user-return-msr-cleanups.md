---
title: 'KVM: x86: User-return MSR cleanups'
date: 2025-10-16
last_reply: 2025-10-23
message_count: 17
participants: ['Sean Christopherson', 'Chao Gao', 'Edgecombe, Rick P', 'Adrian Hunter', 'Xiaoyao Li']
---

## [1] Sean Christopherson — 2025-10-16

This is a combo of Hou's series to clean up the "IRQs disabled" mess(es), and
my one-off patch to drop "cache" from a few names that escalated.  I tagged it
v4 since Hou's last posting was v3, and this is much closer to Hou's series
than anything else.

v4:
 - Tweak changelog regarding the "cache" rename to try and better capture
   the details of how .curr is used. [Yan]
 - Synchronize the cache immediately after TD-Exit to minimize the window
   where the cache is stale (even with the reboot change, it's still nice to
   minimize the window). [Yan]
 - Leave the user-return notifier registered on reboot/shutdown so that the
   common code doesn't have to be paranoid about being interrupted.

v3: https://lore.kernel.org/all/15fa59ba7f6f849082fb36735e784071539d5ad2.1758002303.git.houwenlong.hwl@antgroup.com

v1 (cache): https://lore.kernel.org/all/20250919214259.1584273-1-seanjc@google.com

Hou Wenlong (1):
  KVM: x86: Don't disable IRQs when unregistering user-return notifier

Sean Christopherson (3):
  KVM: TDX: Synchronize user-return MSRs immediately after VP.ENTER
  KVM: x86: Leave user-return notifier registered on reboot/shutdown
  KVM: x86: Drop "cache" from user return MSR setter that skips WRMSR

 arch/x86/include/asm/kvm_host.h |  4 +--
 arch/x86/kvm/vmx/tdx.c          | 28 ++++++++++-------
 arch/x86/kvm/vmx/tdx.h          |  2 +-
 arch/x86/kvm/x86.c              | 56 +++++++++++++++++++--------------
 4 files changed, 53 insertions(+), 37 deletions(-)


base-commit: f222788458c8a7753d43befef2769cd282dc008e

---

## [2] Sean Christopherson — 2025-10-16
*Subject: [PATCH v4 1/4] KVM: TDX: Synchronize user-return MSRs immediately
 after VP.ENTER*

Immediately synchronize the user-return MSR values after a successful
VP.ENTER to minimize the window where KVM is tracking stale values in the
"curr" field, and so that the tracked value is synchronized before IRQs
are enabled.

This is *very* technically a bug fix, as a forced shutdown/reboot will
invoke kvm_shutdown() without waiting for tasks to be frozen, and so the
on_each_cpu() calls to kvm_disable_virtualization_cpu() will call
kvm_on_user_return() from IRQ context and thus could consume a stale
values->curr if the IRQ hits while KVM is active.  That said, the real
motivation is to minimize the window where "curr" is stale, as the same
forced shutdown/reboot flaw has effectively existed for all of non-TDX
for years, as kvm_set_user_return_msr() runs with IRQs enabled.  Not to
mention that a stale MSR is the least of the kernel's concerns if a reboot
is forced while KVM is active.

Fixes: e0b4f31a3c65 ("KVM: TDX: restore user ret MSRs")
Cc: Yan Zhao <yan.y.zhao@intel.com>
Cc: Xiaoyao Li <xiaoyao.li@intel.com>
Cc: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 20 +++++++++++++-------
 arch/x86/kvm/vmx/tdx.h |  2 +-
 2 files changed, 14 insertions(+), 8 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 326db9b9c567..2f3dfe9804b5 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -780,6 +780,14 @@ void tdx_prepare_switch_to_guest(struct kvm_vcpu *vcpu)
 		vt->msr_host_kernel_gs_base = read_msr(MSR_KERNEL_GS_BASE);
 
 	vt->guest_state_loaded = true;
+
+	/*
+	 * Several of KVM's user-return MSRs are clobbered by the TDX-Module if
+	 * VP.ENTER succeeds, i.e. on TD-Exit.  Mark those MSRs as needing an
+	 * update to synchronize the "current" value in KVM's cache with the
+	 * value in hardware (loaded by the TDX-Module).
+	 */
+	to_tdx(vcpu)->need_user_return_msr_sync = true;
 }
 
 struct tdx_uret_msr {
@@ -807,7 +815,6 @@ static void tdx_user_return_msr_update_cache(void)
 static void tdx_prepare_switch_to_host(struct kvm_vcpu *vcpu)
 {
 	struct vcpu_vt *vt = to_vt(vcpu);
-	struct vcpu_tdx *tdx = to_tdx(vcpu);
 
 	if (!vt->guest_state_loaded)
 		return;
@@ -815,11 +822,6 @@ static void tdx_prepare_switch_to_host(struct kvm_vcpu *vcpu)
 	++vcpu->stat.host_state_reload;
 	wrmsrl(MSR_KERNEL_GS_BASE, vt->msr_host_kernel_gs_base);
 
-	if (tdx->guest_entered) {
-		tdx_user_return_msr_update_cache();
-		tdx->guest_entered = false;
-	}
-
 	vt->guest_state_loaded = false;
 }
 
@@ -1059,7 +1061,11 @@ fastpath_t tdx_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 		update_debugctlmsr(vcpu->arch.host_debugctl);
 
 	tdx_load_host_xsave_state(vcpu);
-	tdx->guest_entered = true;
+
+	if (tdx->need_user_return_msr_sync) {
+		tdx_user_return_msr_update_cache();
+		tdx->need_user_return_msr_sync = false;
+	}
 
 	vcpu->arch.regs_avail &= TDX_REGS_AVAIL_SET;
 
diff --git a/arch/x86/kvm/vmx/tdx.h b/arch/x86/kvm/vmx/tdx.h
index ca39a9391db1..9434a6371d67 100644
--- a/arch/x86/kvm/vmx/tdx.h
+++ b/arch/x86/kvm/vmx/tdx.h
@@ -67,7 +67,7 @@ struct vcpu_tdx {
 	u64 vp_enter_ret;
 
 	enum vcpu_tdx_state state;
-	bool guest_entered;
+	bool need_user_return_msr_sync;
 
 	u64 map_gpa_next;
 	u64 map_gpa_end;

---

## [3] Sean Christopherson — 2025-10-16
*Subject: [PATCH v4 2/4] KVM: x86: Leave user-return notifier registered on reboot/shutdown*

Leave KVM's user-return notifier registered in the unlikely case that the
notifier is registered when disabling virtualization via IPI callback in
response to reboot/shutdown.  On reboot/shutdown, keeping the notifier
registered is ok as far as MSR state is concerned (arguably better then
restoring MSRs at an unknown point in time), as the callback will run
cleanly and restore host MSRs if the CPU manages to return to userspace
before the system goes down.

The only wrinkle is that if kvm.ko module unload manages to race with
reboot/shutdown, then leaving the notifier registered could lead to
use-after-free due to calling into unloaded kvm.ko module code.  But such
a race is only possible on --forced reboot/shutdown, because otherwise
userspace tasks would be frozen before kvm_shutdown() is called, i.e. on a
"normal" reboot/shutdown, it should be impossible for the CPU to return to
userspace after kvm_shutdown().

Furthermore, on a --forced reboot/shutdown, unregistering the user-return
hook from IRQ context doesn't fully guard against use-after-free, because
KVM could immediately re-register the hook, e.g. if the IRQ arrives before
kvm_user_return_register_notifier() is called.

Rather than trying to guard against the IPI in the "normal" user-return
code, which is difficult and noisy, simply leave the user-return notifier
registered on a reboot, and bump the kvm.ko module refcount to defend
against a use-after-free due to kvm.ko unload racing against reboot.

Alternatively, KVM could allow kvm.ko and try to drop the notifiers during
kvm_x86_exit(), but that's also a can of worms as registration is per-CPU,
and so KVM would need to blast an IPI, and doing so while a reboot/shutdown
is in-progress is far risky than preventing userspace from unloading KVM.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/x86.c | 21 ++++++++++++++++++++-
 1 file changed, 20 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index b4b5d2d09634..386dc2401f58 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -13078,7 +13078,21 @@ int kvm_arch_enable_virtualization_cpu(void)
 void kvm_arch_disable_virtualization_cpu(void)
 {
 	kvm_x86_call(disable_virtualization_cpu)();
-	drop_user_return_notifiers();
+
+	/*
+	 * Leave the user-return notifiers as-is when disabling virtualization
+	 * for reboot, i.e. when disabling via IPI function call, and instead
+	 * pin kvm.ko (if it's a module) to defend against use-after-free (in
+	 * the *very* unlikely scenario module unload is racing with reboot).
+	 * On a forced reboot, tasks aren't frozen before shutdown, and so KVM
+	 * could be actively modifying user-return MSR state when the IPI to
+	 * disable virtualization arrives.  Handle the extreme edge case here
+	 * instead of trying to account for it in the normal flows.
+	 */
+	if (in_task() || WARN_ON_ONCE(!kvm_rebooting))
+		drop_user_return_notifiers();
+	else
+		__module_get(THIS_MODULE);
 }
 
 bool kvm_vcpu_is_reset_bsp(struct kvm_vcpu *vcpu)
@@ -14363,6 +14377,11 @@ module_init(kvm_x86_init);
 
 static void __exit kvm_x86_exit(void)
 {
+	int cpu;
+
+	for_each_possible_cpu(cpu)
+		WARN_ON_ONCE(per_cpu_ptr(user_return_msrs, cpu)->registered);
+
 	WARN_ON_ONCE(static_branch_unlikely(&kvm_has_noapic_vcpu));
 }
 module_exit(kvm_x86_exit);

---

## [4] Sean Christopherson — 2025-10-16
*Subject: [PATCH v4 3/4] KVM: x86: Don't disable IRQs when unregistering
 user-return notifier*

From: Hou Wenlong <houwenlong.hwl@antgroup.com>

Remove the code to disable IRQs when unregistering KVM's user-return
notifier now that KVM doesn't invoke kvm_on_user_return() when disabling
virtualization via IPI function call, i.e. now that there's no need to
guard against re-entrancy via IPI callback.

Note, disabling IRQs has largely been unnecessary since commit
a377ac1cd9d7b ("x86/entry: Move user return notifier out of loop") moved
fire_user_return_notifiers() into the section with IRQs disabled.  In doing
so, the commit somewhat inadvertently fixed the underlying issue that
was papered over by commit 1650b4ebc99d ("KVM: Disable irq while
unregistering user notifier").  I.e. in practice, the code and comment
has been stale since commit a377ac1cd9d7b.

Signed-off-by: Hou Wenlong <houwenlong.hwl@antgroup.com>
[sean: rewrite changelog after rebasing, drop lockdep assert]
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/x86.c | 14 +++-----------
 1 file changed, 3 insertions(+), 11 deletions(-)

diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 386dc2401f58..394a30bb33da 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -581,18 +581,10 @@ static void kvm_on_user_return(struct user_return_notifier *urn)
 	struct kvm_user_return_msrs *msrs
 		= container_of(urn, struct kvm_user_return_msrs, urn);
 	struct kvm_user_return_msr_values *values;
-	unsigned long flags;
 
-	/*
-	 * Disabling irqs at this point since the following code could be
-	 * interrupted and executed through kvm_arch_disable_virtualization_cpu()
-	 */
-	local_irq_save(flags);
-	if (msrs->registered) {
-		msrs->registered = false;
-		user_return_notifier_unregister(urn);
-	}
-	local_irq_restore(flags);
+	msrs->registered = false;
+	user_return_notifier_unregister(urn);
+
 	for (slot = 0; slot < kvm_nr_uret_msrs; ++slot) {
 		values = &msrs->values[slot];
 		if (values->host != values->curr) {

---

## [5] Sean Christopherson — 2025-10-16
*Subject: [PATCH v4 4/4] KVM: x86: Drop "cache" from user return MSR setter
 that skips WRMSR*

Rename kvm_user_return_msr_update_cache() to __kvm_set_user_return_msr()
and use the helper in kvm_set_user_return_msr() to make it obvious that
the double-underscores version is doing a subset of the work of the "full"
setter.

While the function does indeed update a cache, the nomenclature is
slightly misleading now that there is a "get" helper (see commit
9bc366350734 ("KVM: x86: Add helper to retrieve current value of user
return MSR"), as the current value isn't _just_ the cached value, it's
also the value that's currently loaded in hardware (modulo the fact that
writing .curr and the actual MSR isn't atomic and may have significant
"delays" in certain setups).

Opportunistically rename "index" to "slot" in the prototypes.  The user-
return APIs deliberately use "slot" to try and make it more obvious that
they take the slot within the array, not the index of the MSR.

Opportunistically tweak the local TDX helper to drop "cache" from its
name and to use "sync" instead of "update", so that it's more obvious the
goal is to sync (with hardware), versus doing some arbitrary update.

No functional change intended.

Cc: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>
Reviewed-by: Yan Zhao <yan.y.zhao@intel.com>
Link: https://lore.kernel.org/all/aM2EvzLLmBi5-iQ5@google.com [1]
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm_host.h |  4 ++--
 arch/x86/kvm/vmx/tdx.c          | 10 +++++-----
 arch/x86/kvm/x86.c              | 21 ++++++++++-----------
 3 files changed, 17 insertions(+), 18 deletions(-)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 48598d017d6f..dc2476f25c75 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -2377,8 +2377,8 @@ int kvm_pv_send_ipi(struct kvm *kvm, unsigned long ipi_bitmap_low,
 
 int kvm_add_user_return_msr(u32 msr);
 int kvm_find_user_return_msr(u32 msr);
-int kvm_set_user_return_msr(unsigned index, u64 val, u64 mask);
-void kvm_user_return_msr_update_cache(unsigned int index, u64 val);
+int kvm_set_user_return_msr(unsigned int slot, u64 val, u64 mask);
+void __kvm_set_user_return_msr(unsigned int slot, u64 val);
 u64 kvm_get_user_return_msr(unsigned int slot);
 
 static inline bool kvm_is_supported_user_return_msr(u32 msr)
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 2f3dfe9804b5..b7e2957d53d9 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -803,13 +803,13 @@ static struct tdx_uret_msr tdx_uret_msrs[] = {
 	{.msr = MSR_TSC_AUX,},
 };
 
-static void tdx_user_return_msr_update_cache(void)
+static void tdx_sync_user_return_msrs(void)
 {
 	int i;
 
 	for (i = 0; i < ARRAY_SIZE(tdx_uret_msrs); i++)
-		kvm_user_return_msr_update_cache(tdx_uret_msrs[i].slot,
-						 tdx_uret_msrs[i].defval);
+		__kvm_set_user_return_msr(tdx_uret_msrs[i].slot,
+					  tdx_uret_msrs[i].defval);
 }
 
 static void tdx_prepare_switch_to_host(struct kvm_vcpu *vcpu)
@@ -1063,7 +1063,7 @@ fastpath_t tdx_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 	tdx_load_host_xsave_state(vcpu);
 
 	if (tdx->need_user_return_msr_sync) {
-		tdx_user_return_msr_update_cache();
+		tdx_sync_user_return_msrs();
 		tdx->need_user_return_msr_sync = false;
 	}
 
@@ -3446,7 +3446,7 @@ static int __init __tdx_bringup(void)
 		 *
 		 * this_cpu_ptr(user_return_msrs)->registered isn't checked
 		 * because the registration is done at vcpu runtime by
-		 * tdx_user_return_msr_update_cache().
+		 * tdx_sync_user_return_msrs().
 		 */
 		tdx_uret_msrs[i].slot = kvm_find_user_return_msr(tdx_uret_msrs[i].msr);
 		if (tdx_uret_msrs[i].slot == -1) {
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 394a30bb33da..68daf94e0deb 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -655,6 +655,15 @@ static void kvm_user_return_register_notifier(struct kvm_user_return_msrs *msrs)
 	}
 }
 
+void __kvm_set_user_return_msr(unsigned int slot, u64 value)
+{
+	struct kvm_user_return_msrs *msrs = this_cpu_ptr(user_return_msrs);
+
+	msrs->values[slot].curr = value;
+	kvm_user_return_register_notifier(msrs);
+}
+EXPORT_SYMBOL_GPL(__kvm_set_user_return_msr);
+
 int kvm_set_user_return_msr(unsigned slot, u64 value, u64 mask)
 {
 	struct kvm_user_return_msrs *msrs = this_cpu_ptr(user_return_msrs);
@@ -667,21 +676,11 @@ int kvm_set_user_return_msr(unsigned slot, u64 value, u64 mask)
 	if (err)
 		return 1;
 
-	msrs->values[slot].curr = value;
-	kvm_user_return_register_notifier(msrs);
+	__kvm_set_user_return_msr(slot, value);
 	return 0;
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_set_user_return_msr);
 
-void kvm_user_return_msr_update_cache(unsigned int slot, u64 value)
-{
-	struct kvm_user_return_msrs *msrs = this_cpu_ptr(user_return_msrs);
-
-	msrs->values[slot].curr = value;
-	kvm_user_return_register_notifier(msrs);
-}
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_user_return_msr_update_cache);
-
 u64 kvm_get_user_return_msr(unsigned int slot)
 {
 	return this_cpu_ptr(user_return_msrs)->values[slot].curr;

---

## [6] Chao Gao — 2025-10-17
*Subject: Re: [PATCH v4 4/4] KVM: x86: Drop "cache" from user return MSR
 setter that skips WRMSR*

>+void __kvm_set_user_return_msr(unsigned int slot, u64 value)
>+{

nit: s/EXPORT_SYMBOL_GPL/EXPORT_SYMBOL_FOR_KVM_INTERNAL

>+
> int kvm_set_user_return_msr(unsigned slot, u64 value, u64 mask)

---

## [7] Chao Gao — 2025-10-17
*Subject: Re: [PATCH v4 2/4] KVM: x86: Leave user-return notifier registered
 on reboot/shutdown*

> bool kvm_vcpu_is_reset_bsp(struct kvm_vcpu *vcpu)
>@@ -14363,6 +14377,11 @@ module_init(kvm_x86_init);

Is it OK to reference user_return_msrs during kvm.ko unloading? IIUC,
user_return_msrs has already been freed during kvm-{intel,amd}.ko unloading.
See:

vmx_exit/svm_exit()
  -> kvm_x86_vendor_exit()
       -> free_percpu(user_return_msrs);

>+
>t 	WARN_ON_ONCE(static_branch_unlikely(&kvm_has_noapic_vcpu));

---

## [8] Sean Christopherson — 2025-10-17
*Subject: Re: [PATCH v4 2/4] KVM: x86: Leave user-return notifier registered on reboot/shutdown*

On Fri, Oct 17, 2025, Chao Gao wrote:
> > bool kvm_vcpu_is_reset_bsp(struct kvm_vcpu *vcpu)
> >@@ -14363,6 +14377,11 @@ module_init(kvm_x86_init);

Ouch.  Guess who didn't run with KASAN...

And rather than squeezing the WARN into this patch, I'm strongly leaning toward
adding it in a prep patch, as the WARN is valuable irrespective of how KVM handles
reboot.

Not yet tested...

--
From: Sean Christopherson <seanjc@google.com>
Date: Fri, 17 Oct 2025 06:10:30 -0700
Subject: [PATCH 2/5] KVM: x86: WARN if user-return MSR notifier is registered
 on exit

When freeing the per-CPU user-return MSRs structures, WARN if any CPU has
a registered notifier to help detect and/or debug potential use-after-free
issues.  The lifecycle of the notifiers is rather convoluted, and has
several non-obvious paths where notifiers are unregistered, i.e. isn't
exactly the most robust code possible.

The notifiers they are registered on-demand in KVM, on the first WRMSR to
a tracked register.  _Usually_ the notifier is unregistered whenever the
CPU returns to userspace.  But because any given CPU isn't guaranteed to
return to userspace, e.g. the CPU could be offlined before doing so, KVM
also "drops", a.k.a. unregisters, the notifiers when virtualization is
disabled on the CPU.

Further complicating the unregister path is the fact that the calls to
disable virtualization come from common KVM, and the per-CPU calls are
guarded by a per-CPU flag (to harden _that_ code against bugs, e.g. due to
mishandling reboot).  Reboot/shutdown in particular is problematic, as KVM
disables virtualization via IPI function call, i.e. from IRQ context,
instead of using the cpuhp framework, which runs in task context.  I.e. on
reboot/shutdown, drop_user_return_notifiers() is called asynchronously.

Forced reboot/shutdown is the most problematic scenario, as userspace tasks
are not frozen before kvm_shutdown() is invoked, i.e. KVM could be actively
manipulating the user-return MSR lists and/or notifiers when the IPI
arrives.  To a certain extent, all bets are off when userspace forces a
reboot/shutdown, but KVM should at least avoid a use-after-free, e.g. to
avoid crashing the kernel when trying to reboot.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/x86.c | 33 +++++++++++++++++++++++++--------
 1 file changed, 25 insertions(+), 8 deletions(-)

diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index b4b5d2d09634..334a911b36c5 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -575,6 +575,27 @@ static inline void kvm_async_pf_hash_reset(struct kvm_vcpu *vcpu)
 		vcpu->arch.apf.gfns[i] = ~0;
 }
 
+static int kvm_init_user_return_msrs(void)
+{
+	user_return_msrs = alloc_percpu(struct kvm_user_return_msrs);
+	if (!user_return_msrs) {
+		pr_err("failed to allocate percpu user_return_msrs\n");
+		return -ENOMEM;
+	}
+	kvm_nr_uret_msrs = 0;
+	return 0;
+}
+
+static void kvm_free_user_return_msrs(void)
+{
+	int cpu;
+
+	for_each_possible_cpu(cpu)
+		WARN_ON_ONCE(per_cpu_ptr(user_return_msrs, cpu)->registered);
+
+	free_percpu(user_return_msrs);
+}
+
 static void kvm_on_user_return(struct user_return_notifier *urn)
 {
 	unsigned slot;
@@ -10032,13 +10053,9 @@ int kvm_x86_vendor_init(struct kvm_x86_init_ops *ops)
 		return -ENOMEM;
 	}
 
-	user_return_msrs = alloc_percpu(struct kvm_user_return_msrs);
-	if (!user_return_msrs) {
-		pr_err("failed to allocate percpu kvm_user_return_msrs\n");
-		r = -ENOMEM;
+	r = kvm_init_user_return_msrs();
+	if (r)
 		goto out_free_x86_emulator_cache;
-	}
-	kvm_nr_uret_msrs = 0;
 
 	r = kvm_mmu_vendor_module_init();
 	if (r)
@@ -10141,7 +10158,7 @@ int kvm_x86_vendor_init(struct kvm_x86_init_ops *ops)
 out_mmu_exit:
 	kvm_mmu_vendor_module_exit();
 out_free_percpu:
-	free_percpu(user_return_msrs);
+	kvm_free_user_return_msrs();
 out_free_x86_emulator_cache:
 	kmem_cache_destroy(x86_emulator_cache);
 	return r;
@@ -10170,7 +10187,7 @@ void kvm_x86_vendor_exit(void)
 #endif
 	kvm_x86_call(hardware_unsetup)();
 	kvm_mmu_vendor_module_exit();
-	free_percpu(user_return_msrs);
+	kvm_free_user_return_msrs();
 	kmem_cache_destroy(x86_emulator_cache);
 #ifdef CONFIG_KVM_XEN
 	static_key_deferred_flush(&kvm_xen_enabled);
--

---

## [9] Edgecombe, Rick P — 2025-10-20
*Subject: Re: [PATCH v4 1/4] KVM: TDX: Synchronize user-return MSRs immediately
 after VP.ENTER*

+Adrian for TDX arch MSR clobbering details

On Thu, 2025-10-16 at 15:28 -0700, Sean Christopherson wrote:
> diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
> index 326db9b9c567..2f3dfe9804b5 100644

I think we should be synchronizing only after a successful VP.ENTER with a real
TD exit, but today instead we synchronize after any attempt to VP.ENTER. Or more
accurately, we plan to synchronize when returning to userspace in that case.

It looks to me that if we get some VP.ENTER errors, the registers should not get
clobbered (although I'd love a second assessment on this from other TDX devs).
Then we actually desync the registers with tdx_user_return_msr_update_cache().

I mention because I think this change widens the issue. For the
TDX_OPERAND_BUSY, etc cases the issue is mostly accidentally avoided, by re-
entering the TD before returning to userspace and doing the sync.

> +	to_tdx(vcpu)->need_user_return_msr_sync = true;
>  }

Not sure what the purpose of need_user_return_msr_sync is now that this is moved
here. Before I guess guest_entered was trying to determine if VP.ENTER got
called, but now we know that is the case. So what condition is it avoiding?

But otherwise, as above, we might want to do it depending on the VP.ENTER error
code. Maybe:
if (!(vp_enter_ret & TDX_ERROR))?

> +		tdx_user_return_msr_update_cache();
> +		tdx->need_user_return_msr_sync = false;

---

## [10] Adrian Hunter — 2025-10-21
*Subject: Re: [PATCH v4 1/4] KVM: TDX: Synchronize user-return MSRs immediately
 after VP.ENTER*

On 21/10/2025 01:55, Edgecombe, Rick P wrote:
>> +	 * Several of KVM's user-return MSRs are clobbered by the TDX-Module if
>> +	 * VP.ENTER succeeds, i.e. on TD-Exit.  Mark those MSRs as needing an

If the MSR's do not get clobbered, does it matter whether or not they get
restored.

---

## [11] Sean Christopherson — 2025-10-21
*Subject: Re: [PATCH v4 1/4] KVM: TDX: Synchronize user-return MSRs immediately
 after VP.ENTER*

On Tue, Oct 21, 2025, Adrian Hunter wrote:
> On 21/10/2025 01:55, Edgecombe, Rick P wrote:
> >> +	 * Several of KVM's user-return MSRs are clobbered by the TDX-Module if

Well this is all completely @#($*#.  Looking at the TDX-Module source, if the
TDX-Module synthesizes an exit, e.g. because it suspects a zero-step attack, it
will signal a "normal" exit but not "restore" VMM state.

> If the MSR's do not get clobbered, does it matter whether or not they get
> restored.

It matters because KVM needs to know the actual value in hardware.  If KVM thinks
an MSR is 'X', but it's actually 'Y', then KVM could fail to write the correct
value into hardware when returning to userspace and/or when running a different
vCPU.

Taking a step back, the entire approach of updating the "cache" after the fact is
ridiculous.  TDX entry/exit is anything but fast; avoiding _at most_ 4x WRMSRs at
the start of the run loop is a very, very premature optimization.  Preemptively
load hardware with the value that the TDX-Module _might_ set and call it good.

I'll replace patches 1 and 4 with this, tagged for stable@.

---
 arch/x86/include/asm/kvm_host.h |  1 -
 arch/x86/kvm/vmx/tdx.c          | 52 +++++++++++++++------------------
 arch/x86/kvm/vmx/tdx.h          |  1 -
 arch/x86/kvm/x86.c              |  9 ------
 4 files changed, 23 insertions(+), 40 deletions(-)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 48598d017d6f..d158dfd1842e 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -2378,7 +2378,6 @@ int kvm_pv_send_ipi(struct kvm *kvm, unsigned long ipi_bitmap_low,
 int kvm_add_user_return_msr(u32 msr);
 int kvm_find_user_return_msr(u32 msr);
 int kvm_set_user_return_msr(unsigned index, u64 val, u64 mask);
-void kvm_user_return_msr_update_cache(unsigned int index, u64 val);
 u64 kvm_get_user_return_msr(unsigned int slot);
 
 static inline bool kvm_is_supported_user_return_msr(u32 msr)
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 326db9b9c567..63abfa251243 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -763,25 +763,6 @@ static bool tdx_protected_apic_has_interrupt(struct kvm_vcpu *vcpu)
 	return tdx_vcpu_state_details_intr_pending(vcpu_state_details);
 }
 
-/*
- * Compared to vmx_prepare_switch_to_guest(), there is not much to do
- * as SEAMCALL/SEAMRET calls take care of most of save and restore.
- */
-void tdx_prepare_switch_to_guest(struct kvm_vcpu *vcpu)
-{
-	struct vcpu_vt *vt = to_vt(vcpu);
-
-	if (vt->guest_state_loaded)
-		return;
-
-	if (likely(is_64bit_mm(current->mm)))
-		vt->msr_host_kernel_gs_base = current->thread.gsbase;
-	else
-		vt->msr_host_kernel_gs_base = read_msr(MSR_KERNEL_GS_BASE);
-
-	vt->guest_state_loaded = true;
-}
-
 struct tdx_uret_msr {
 	u32 msr;
 	unsigned int slot;
@@ -795,19 +776,38 @@ static struct tdx_uret_msr tdx_uret_msrs[] = {
 	{.msr = MSR_TSC_AUX,},
 };
 
-static void tdx_user_return_msr_update_cache(void)
+void tdx_prepare_switch_to_guest(struct kvm_vcpu *vcpu)
 {
+	struct vcpu_vt *vt = to_vt(vcpu);
 	int i;
 
+	if (vt->guest_state_loaded)
+		return;
+
+	if (likely(is_64bit_mm(current->mm)))
+		vt->msr_host_kernel_gs_base = current->thread.gsbase;
+	else
+		vt->msr_host_kernel_gs_base = read_msr(MSR_KERNEL_GS_BASE);
+
+	vt->guest_state_loaded = true;
+
+	/*
+	 * Explicitly set user-return MSRs that are clobbered by the TDX-Module
+	 * if VP.ENTER succeeds, i.e. on TD-Exit, with the values that would be
+	 * written by the TDX-Module.  Don't rely on the TDX-Module to actually
+	 * clobber the MSRs, as the contract is poorly defined and not upheld.
+	 * E.g. the TDX-Module will synthesize an EPT Violation without doing
+	 * VM-Enter if it suspects a zero-step attack, and never "restore" VMM
+	 * state.
+	 */
 	for (i = 0; i < ARRAY_SIZE(tdx_uret_msrs); i++)
-		kvm_user_return_msr_update_cache(tdx_uret_msrs[i].slot,
-						 tdx_uret_msrs[i].defval);
+		kvm_set_user_return_msr(i, tdx_uret_msrs[i].slot,
+					tdx_uret_msrs[i].defval);
 }
 
 static void tdx_prepare_switch_to_host(struct kvm_vcpu *vcpu)
 {
 	struct vcpu_vt *vt = to_vt(vcpu);
-	struct vcpu_tdx *tdx = to_tdx(vcpu);
 
 	if (!vt->guest_state_loaded)
 		return;
@@ -815,11 +815,6 @@ static void tdx_prepare_switch_to_host(struct kvm_vcpu *vcpu)
 	++vcpu->stat.host_state_reload;
 	wrmsrl(MSR_KERNEL_GS_BASE, vt->msr_host_kernel_gs_base);
 
-	if (tdx->guest_entered) {
-		tdx_user_return_msr_update_cache();
-		tdx->guest_entered = false;
-	}
-
 	vt->guest_state_loaded = false;
 }
 
@@ -1059,7 +1054,6 @@ fastpath_t tdx_vcpu_run(struct kvm_vcpu *vcpu, u64 run_flags)
 		update_debugctlmsr(vcpu->arch.host_debugctl);
 
 	tdx_load_host_xsave_state(vcpu);
-	tdx->guest_entered = true;
 
 	vcpu->arch.regs_avail &= TDX_REGS_AVAIL_SET;
 
diff --git a/arch/x86/kvm/vmx/tdx.h b/arch/x86/kvm/vmx/tdx.h
index ca39a9391db1..7f258870dc41 100644
--- a/arch/x86/kvm/vmx/tdx.h
+++ b/arch/x86/kvm/vmx/tdx.h
@@ -67,7 +67,6 @@ struct vcpu_tdx {
 	u64 vp_enter_ret;
 
 	enum vcpu_tdx_state state;
-	bool guest_entered;
 
 	u64 map_gpa_next;
 	u64 map_gpa_end;
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index b4b5d2d09634..639589af7cbe 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -681,15 +681,6 @@ int kvm_set_user_return_msr(unsigned slot, u64 value, u64 mask)
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_set_user_return_msr);
 
-void kvm_user_return_msr_update_cache(unsigned int slot, u64 value)
-{
-	struct kvm_user_return_msrs *msrs = this_cpu_ptr(user_return_msrs);
-
-	msrs->values[slot].curr = value;
-	kvm_user_return_register_notifier(msrs);
-}
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_user_return_msr_update_cache);
-
 u64 kvm_get_user_return_msr(unsigned int slot)
 {
 	return this_cpu_ptr(user_return_msrs)->values[slot].curr;

base-commit: f222788458c8a7753d43befef2769cd282dc008e
--

---

## [12] Adrian Hunter — 2025-10-21
*Subject: Re: [PATCH v4 1/4] KVM: TDX: Synchronize user-return MSRs immediately
 after VP.ENTER*

On 21/10/2025 18:06, Sean Christopherson wrote:
> On Tue, Oct 21, 2025, Adrian Hunter wrote:
>> On 21/10/2025 01:55, Edgecombe, Rick P wrote:

I don't quite follow:  if an MSR does not get clobbered, where does the
incorrect value come from?

---

## [13] Sean Christopherson — 2025-10-21
*Subject: Re: [PATCH v4 1/4] KVM: TDX: Synchronize user-return MSRs immediately
 after VP.ENTER*

On Tue, Oct 21, 2025, Adrian Hunter wrote:
> On 21/10/2025 18:06, Sean Christopherson wrote:
> > On Tue, Oct 21, 2025, Adrian Hunter wrote:

kvm_set_user_return_msr() elides the WRMSR if the current value in hardware matches
the new, desired value.  If KVM thinks the MSR is 'X', and KVM wants to set the MSR
to 'X', then KVM will skip the WRMSR and continue on with the wrong value.

Using MSR_TSC_AUX as an example, let's say the vCPU task is running on CPU1, and
that there's a non-TDX vCPU (with guest-side CPU=0) also scheduled on CPU1.  Before
VP.ENTER, MSR_TSC_AUX=user_return_msrs[slot].curr=1 (the host's CPU1 value).  After
a *failed* VP.ENTER, MSR_TSC_AUX will still be '1', but it's "curr" value in
user_return_msrs will be '0' due to kvm_user_return_msr_update_cache() incorrectly
thinking the TDX-Module clobbered the MSR to '0'

When KVM runs the non-TDX vCPU, which wants to run with MSR_TSC_AUX=0, then
kvm_set_user_return_msr() will see msrs->values[slot].curr==value==0 and not do
the WRMSR.  KVM will then run the non-TDX vCPU with MSR_TSC_AUX=1 and corrupt the
guest.

---

## [14] Edgecombe, Rick P — 2025-10-21
*Subject: Re: [PATCH v4 1/4] KVM: TDX: Synchronize user-return MSRs immediately
 after VP.ENTER*

On Tue, 2025-10-21 at 08:06 -0700, Sean Christopherson wrote:
>  I think we should be synchronizing only after a successful VP.ENTER with a real
> > > TD exit, but today instead we synchronize after any attempt to VP.ENTER.

Oh yea, good point. So there is no way to tell from the return code if the
clobbering happened.

> 
> > If the MSR's do not get clobbered, does it matter whether or not they get

Seems reasonable to me in concept, but there is a bug. It looks like some
important MSR isn't getting restored right and the host gets into a bad state.
The first signs start with triggering this:

asmlinkage __visible noinstr struct pt_regs *fixup_bad_iret(struct pt_regs
*bad_regs)
{
	struct pt_regs tmp, *new_stack;

	/*
	 * This is called from entry_64.S early in handling a fault
	 * caused by a bad iret to user mode.  To handle the fault
	 * correctly, we want to move our stack frame to where it would
	 * be had we entered directly on the entry stack (rather than
	 * just below the IRET frame) and we want to pretend that the
	 * exception came from the IRET target.
	 */
	new_stack = (struct pt_regs *)__this_cpu_read(cpu_tss_rw.x86_tss.sp0) -
1;

	/* Copy the IRET target to the temporary storage. */
	__memcpy(&tmp.ip, (void *)bad_regs->sp, 5*8);

	/* Copy the remainder of the stack from the current stack. */
	__memcpy(&tmp, bad_regs, offsetof(struct pt_regs, ip));

	/* Update the entry stack */
	__memcpy(new_stack, &tmp, sizeof(tmp));

	BUG_ON(!user_mode(new_stack)); <---------------HERE

Need to debug.

---

## [15] Sean Christopherson — 2025-10-21
*Subject: Re: [PATCH v4 1/4] KVM: TDX: Synchronize user-return MSRs immediately
 after VP.ENTER*

On Tue, Oct 21, 2025, Rick P Edgecombe wrote:
> On Tue, 2025-10-21 at 08:06 -0700, Sean Christopherson wrote:
> >  I think we should be synchronizing only after a successful VP.ENTER with a real

/facepalm

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 63abfa251243..cde91a995076 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -801,8 +801,8 @@ void tdx_prepare_switch_to_guest(struct kvm_vcpu *vcpu)
         * state.
         */
        for (i = 0; i < ARRAY_SIZE(tdx_uret_msrs); i++)
-               kvm_set_user_return_msr(i, tdx_uret_msrs[i].slot,
-                                       tdx_uret_msrs[i].defval);
+               kvm_set_user_return_msr(tdx_uret_msrs[i].slot,
+                                       tdx_uret_msrs[i].defval, -1ull);
 }
 
 static void tdx_prepare_switch_to_host(struct kvm_vcpu *vcpu)

---

## [16] Edgecombe, Rick P — 2025-10-21
*Subject: Re: [PATCH v4 1/4] KVM: TDX: Synchronize user-return MSRs immediately
 after VP.ENTER*

On Tue, 2025-10-21 at 12:33 -0700, Sean Christopherson wrote:
> /facepalm
> 

Ah ok, I'll give it another spin after I finish debugging step 0, which is
figure out what has gone wrong with my TDX dev machine.

---

## [17] Xiaoyao Li — 2025-10-23
*Subject: Re: [PATCH v4 1/4] KVM: TDX: Synchronize user-return MSRs immediately
 after VP.ENTER*

On 10/22/2025 3:33 AM, Sean Christopherson wrote:
> On Tue, Oct 21, 2025, Rick P Edgecombe wrote:
>> On Tue, 2025-10-21 at 08:06 -0700, Sean Christopherson wrote:

with the above fix, the whole diff/implementation works. It passes our 
internal TDX CI.

---
