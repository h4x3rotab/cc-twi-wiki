---
title: 'KVM: x86: User-return MSR fix+cleanups'
date: 2025-10-30
last_reply: 2025-11-10
message_count: 18
participants: ['Sean Christopherson', 'Yan Zhao', 'Xiaoyao Li', 'Huang, Kai', 'Chao Gao']
---

## [1] Sean Christopherson — 2025-10-30

Fix a bug in TDX where KVM will incorrectly update the current user-return
MSR values when the TDX-Module doesn't actually clobber the relevant MSRs,
and then cleanup and harden the user-return MSR code, e.g. against forced
reboots.

v5:
 - Set TDX MSRs to their expected post-run value during
   tdx_prepare_switch_to_guest() instead of trying to predict what value
   is in hardware after the SEAMCALL. [Yan]
 - Free user_return_msrs at kvm_x86_vendor_exit(), not kvm_x86_exit(). [Chao]

v4:
 - https://lore.kernel.org/all/20251016222816.141523-1-seanjc@google.com
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
  KVM: TDX: Explicitly set user-return MSRs that *may* be clobbered by
    the TDX-Module
  KVM: x86: WARN if user-return MSR notifier is registered on exit
  KVM: x86: Leave user-return notifier registered on reboot/shutdown

 arch/x86/include/asm/kvm_host.h |  1 -
 arch/x86/kvm/vmx/tdx.c          | 52 +++++++++++-------------
 arch/x86/kvm/vmx/tdx.h          |  1 -
 arch/x86/kvm/x86.c              | 72 ++++++++++++++++++++-------------
 4 files changed, 66 insertions(+), 60 deletions(-)


base-commit: 4cc167c50eb19d44ac7e204938724e685e3d8057

---

## [2] Sean Christopherson — 2025-10-30
*Subject: [PATCH v5 1/4] KVM: TDX: Explicitly set user-return MSRs that *may*
 be clobbered by the TDX-Module*

Set all user-return MSRs to their post-TD-exit value when preparing to run
a TDX vCPU to ensure the value that KVM expects to be loaded after running
the vCPU is indeed the value that's loaded in hardware.  If the TDX-Module
doesn't actually enter the guest, i.e. doesn't do VM-Enter, then it won't
"restore" VMM state, i.e. won't clobber user-return MSRs to their expected
post-run values, in which case simply updating KVM's "cached" value will
effectively corrupt the cache due to hardware still holding the original
value.

In theory, KVM could conditionally update the current user-return value if
and only if tdh_vp_enter() succeeds, but in practice "success" doesn't
guarantee the TDX-Module actually entered the guest, e.g. if the TDX-Module
synthesizes an EPT Violation because it suspects a zero-step attack.

Force-load the expected values instead of trying to decipher whether or
not the TDX-Module restored/clobbered MSRs, as the risk doesn't justify
the benefits.  Effectively avoiding four WRMSRs once per run loop (even if
the vCPU is scheduled out, user-return MSRs only need to be reloaded if
the CPU exits to userspace or runs a non-TDX vCPU) is likely in the noise
when amortized over all entries, given the cost of running a TDX vCPU.
E.g. the cost of the WRMSRs is somewhere between ~300 and ~500 cycles,
whereas the cost of a _single_ roundtrip to/from a TDX guest is thousands
of cycles.

Fixes: e0b4f31a3c65 ("KVM: TDX: restore user ret MSRs")
Cc: stable@vger.kernel.org
Cc: Yan Zhao <yan.y.zhao@intel.com>
Cc: Xiaoyao Li <xiaoyao.li@intel.com>
Cc: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
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
index 326db9b9c567..cde91a995076 100644
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
+		kvm_set_user_return_msr(tdx_uret_msrs[i].slot,
+					tdx_uret_msrs[i].defval, -1ull);
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

---

## [3] Sean Christopherson — 2025-10-30
*Subject: [PATCH v5 2/4] KVM: x86: WARN if user-return MSR notifier is
 registered on exit*

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
index 639589af7cbe..bb7a7515f280 100644
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
@@ -10023,13 +10044,9 @@ int kvm_x86_vendor_init(struct kvm_x86_init_ops *ops)
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
@@ -10132,7 +10149,7 @@ int kvm_x86_vendor_init(struct kvm_x86_init_ops *ops)
 out_mmu_exit:
 	kvm_mmu_vendor_module_exit();
 out_free_percpu:
-	free_percpu(user_return_msrs);
+	kvm_free_user_return_msrs();
 out_free_x86_emulator_cache:
 	kmem_cache_destroy(x86_emulator_cache);
 	return r;
@@ -10161,7 +10178,7 @@ void kvm_x86_vendor_exit(void)
 #endif
 	kvm_x86_call(hardware_unsetup)();
 	kvm_mmu_vendor_module_exit();
-	free_percpu(user_return_msrs);
+	kvm_free_user_return_msrs();
 	kmem_cache_destroy(x86_emulator_cache);
 #ifdef CONFIG_KVM_XEN
 	static_key_deferred_flush(&kvm_xen_enabled);

---

## [4] Sean Christopherson — 2025-10-30
*Subject: [PATCH v5 3/4] KVM: x86: Leave user-return notifier registered on reboot/shutdown*

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
 arch/x86/kvm/x86.c | 16 +++++++++++++++-
 1 file changed, 15 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index bb7a7515f280..c927326344b1 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -13086,7 +13086,21 @@ int kvm_arch_enable_virtualization_cpu(void)
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

---

## [5] Sean Christopherson — 2025-10-30
*Subject: [PATCH v5 4/4] KVM: x86: Don't disable IRQs when unregistering
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
index c927326344b1..719a5fa45eb1 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -602,18 +602,10 @@ static void kvm_on_user_return(struct user_return_notifier *urn)
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

## [6] Yan Zhao — 2025-11-03
*Subject: Re: [PATCH v5 1/4] KVM: TDX: Explicitly set user-return MSRs that
 *may* be clobbered by the TDX-Module*

On Thu, Oct 30, 2025 at 12:15:25PM -0700, Sean Christopherson wrote:
> Set all user-return MSRs to their post-TD-exit value when preparing to run
> a TDX vCPU to ensure the value that KVM expects to be loaded after running
This paragraph is confusing.

The flow for the TDX module for the user-return MSRs is:

1. Before entering guest, i.e., inside tdh_vp_enter(), 
   a) if VM-Enter is guaranteed to succeed, load MSRs with saved guest value;
   b) otherwise, do nothing and return to VMM.

2. After VMExit, before returning to VMM,
   save guest value and restore MSRs to default values.


Failure of tdh_vp_enter() (i.e., in case of 1.b), the hardware values of the
MSRs should be either host value or default value, while with
msrs->values[slot].curr being default value.

As a result, the reasoning of "hardware still holding the original value" is not
convincing, since the original value is exactly the host value.

> In theory, KVM could conditionally update the current user-return value if
> and only if tdh_vp_enter() succeeds, but in practice "success" doesn't

---

## [7] Xiaoyao Li — 2025-11-03
*Subject: Re: [PATCH v5 1/4] KVM: TDX: Explicitly set user-return MSRs that
 *may* be clobbered by the TDX-Module*

On 10/31/2025 3:15 AM, Sean Christopherson wrote:
> Set all user-return MSRs to their post-TD-exit value when preparing to run
> a TDX vCPU to ensure the value that KVM expects to be loaded after running

Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>

> ---
>   arch/x86/include/asm/kvm_host.h |  1 -

---

## [8] Yan Zhao — 2025-11-04
*Subject: Re: [PATCH v5 1/4] KVM: TDX: Explicitly set user-return MSRs that
 *may* be clobbered by the TDX-Module*

Another nit:
Remove the tdx_user_return_msr_update_cache() in the comment of __tdx_bringup().

Or could we just invoke tdx_user_return_msr_update_cache() in
tdx_prepare_switch_to_guest()?

On Mon, Nov 03, 2025 at 02:20:18PM +0800, Yan Zhao wrote:
> On Thu, Oct 30, 2025 at 12:15:25PM -0700, Sean Christopherson wrote:
> > Set all user-return MSRs to their post-TD-exit value when preparing to run

---

## [9] Xiaoyao Li — 2025-11-04
*Subject: Re: [PATCH v5 1/4] KVM: TDX: Explicitly set user-return MSRs that
 *may* be clobbered by the TDX-Module*

On 11/4/2025 3:06 PM, Yan Zhao wrote:
> Another nit:
> Remove the tdx_user_return_msr_update_cache() in the comment of __tdx_bringup().

No. It lacks the WRMSR operation to update the hardware value, which is 
the key of this patch.

> On Mon, Nov 03, 2025 at 02:20:18PM +0800, Yan Zhao wrote:
>> On Thu, Oct 30, 2025 at 12:15:25PM -0700, Sean Christopherson wrote:

---

## [10] Yan Zhao — 2025-11-04
*Subject: Re: [PATCH v5 1/4] KVM: TDX: Explicitly set user-return MSRs that
 *may* be clobbered by the TDX-Module*

On Tue, Nov 04, 2025 at 04:40:44PM +0800, Xiaoyao Li wrote:
> On 11/4/2025 3:06 PM, Yan Zhao wrote:
> > Another nit:
As [1], I don't think the WRMSR operation to update the hardware value is
necessary. The value will be updated to guest value soon any way if
tdh_vp_enter() succeeds, or the hardware value remains to be the host value or
the default value.

But I think invoking tdx_user_return_msr_update_cache() in
tdx_prepare_switch_to_guest() is better than in
tdx_prepare_switch_to_host().

[1] https://lore.kernel.org/kvm/aQhJol0CvT6bNCJQ@yzhao56-desk.sh.intel.com/

---

## [11] Huang, Kai — 2025-11-04
*Subject: Re: [PATCH v5 4/4] KVM: x86: Don't disable IRQs when unregistering
 user-return notifier*

On Thu, 2025-10-30 at 12:15 -0700, Sean Christopherson wrote:
> From: Hou Wenlong <houwenlong.hwl@antgroup.com>
> 

Reviewed-by: Kai Huang <kai.huang@intel.com>

> ---
>  arch/x86/kvm/x86.c | 14 +++-----------

---

## [12] Sean Christopherson — 2025-11-04
*Subject: Re: [PATCH v5 1/4] KVM: TDX: Explicitly set user-return MSRs that
 *may* be clobbered by the TDX-Module*

On Tue, Nov 04, 2025, Yan Zhao wrote:
> On Tue, Nov 04, 2025 at 04:40:44PM +0800, Xiaoyao Li wrote:
> > On 11/4/2025 3:06 PM, Yan Zhao wrote:

As explained in the original thread:  

 : > If the MSR's do not get clobbered, does it matter whether or not they get
 : > restored.
 : 
 : It matters because KVM needs to know the actual value in hardware.  If KVM thinks
 : an MSR is 'X', but it's actually 'Y', then KVM could fail to write the correct
 : value into hardware when returning to userspace and/or when running a different
 : vCPU.

I.e. updating the cache effectively corrupts state if the TDX-Module doesn't
clobber MSRs as expected, i.e. if the current value is preserved in hardware.

> But I think invoking tdx_user_return_msr_update_cache() in
> tdx_prepare_switch_to_guest() is better than in

---

## [13] Yan Zhao — 2025-11-05
*Subject: Re: [PATCH v5 1/4] KVM: TDX: Explicitly set user-return MSRs that
 *may* be clobbered by the TDX-Module*

On Tue, Nov 04, 2025 at 09:55:54AM -0800, Sean Christopherson wrote:
> On Tue, Nov 04, 2025, Yan Zhao wrote:
> > On Tue, Nov 04, 2025 at 04:40:44PM +0800, Xiaoyao Li wrote:
I'm not against this patch. But I think the above explanation is not that
convincing, (or somewhat confusing).


By "if the TDX-Module doesn't clobber MSRs as expected",
- if it occurs due to tdh_vp_enter() failure, I think it's fine.
  Though KVM thinks the MSR is 'X', the actual value in hardware should be
  either 'Y' (the host value) or 'X' (the expected clobbered value).
  It's benign to preserving value 'Y', no?

- if it occurs due to TDX module bugs, e.g., if after a successful
  tdh_vp_enter() and VM exits, the TDX module clobbers the MSR to 'Z', while
  the host value for the MSR is 'Y' and KVM thinks the actual value is 'X'.
  Then the hardware state will be incorrect after returning to userspace if
  'X' == 'Y'. But this patch can't guard against this condition as well, right?


> > But I think invoking tdx_user_return_msr_update_cache() in
> > tdx_prepare_switch_to_guest() is better than in

---

## [14] Xiaoyao Li — 2025-11-05
*Subject: Re: [PATCH v5 1/4] KVM: TDX: Explicitly set user-return MSRs that
 *may* be clobbered by the TDX-Module*

On 11/5/2025 9:52 AM, Yan Zhao wrote:
> On Tue, Nov 04, 2025 at 09:55:54AM -0800, Sean Christopherson wrote:
>> On Tue, Nov 04, 2025, Yan Zhao wrote:

For example, after tdh_vp_enter() failure, the state becomes

     .curr == 'X'
     hardware == 'Y'

and the TD vcpu thread is preempted and the pcpu is scheduled to run 
another VM's vcpu, which is a normal VMX vcpu and it happens to have the 
MSR value of 'X'. So in

   vmx_prepare_switch_to_guest()
     -> kvm_set_user_return_msr()

it will skip the WRMSR because written_value == .curr == 'X', but the 
hardware value is 'Y'. Then KVM fails to load the expected value 'X' for 
the VMX vcpu.

> - if it occurs due to TDX module bugs, e.g., if after a successful
>    tdh_vp_enter() and VM exits, the TDX module clobbers the MSR to 'Z', while

---

## [15] Yan Zhao — 2025-11-06
*Subject: Re: [PATCH v5 1/4] KVM: TDX: Explicitly set user-return MSRs that
 *may* be clobbered by the TDX-Module*

On Wed, Nov 05, 2025 at 05:16:56PM +0800, Xiaoyao Li wrote:
> On 11/5/2025 9:52 AM, Yan Zhao wrote:
> > On Tue, Nov 04, 2025 at 09:55:54AM -0800, Sean Christopherson wrote:
Oh. Thanks! I overlooked that there's another checking of .curr in
kvm_set_user_return_msr(). It explains why .curr must be equal to the hardware
value when outside guest mode.

> > - if it occurs due to TDX module bugs, e.g., if after a successful
> >    tdh_vp_enter() and VM exits, the TDX module clobbers the MSR to 'Z', while

---

## [16] Chao Gao — 2025-11-07
*Subject: Re: [PATCH v5 3/4] KVM: x86: Leave user-return notifier registered
 on reboot/shutdown*

On Thu, Oct 30, 2025 at 12:15:27PM -0700, Sean Christopherson wrote:
>Leave KVM's user-return notifier registered in the unlikely case that the
>notifier is registered when disabling virtualization via IPI callback in

This doesn't pin kvm-{intel,amd}.ko, right? if so, there is still a potential
user-after-free if the CPU returns to userspace after the per-CPU
user_return_msrs is freed on kvm-{intel,amd}.ko unloading.

I think we need to either move __module_get() into
kvm_x86_call(disable_virtualization_cpu)() or allocate/free the per-CPU
user_return_msrs when loading/unloading kvm.ko. e.g.,

From 0269f0ee839528e8a9616738d615a096901d6185 Mon Sep 17 00:00:00 2001
From: Chao Gao <chao.gao@intel.com>
Date: Fri, 7 Nov 2025 00:10:28 -0800
Subject: [PATCH] KVM: x86: Allocate/free user_return_msrs at kvm.ko
 (un)loading time

Move user_return_msrs allocation/free from vendor modules (kvm-intel.ko and
kvm-amd.ko) (un)loading time to kvm.ko's to make it less risky to access
user_return_msrs in kvm.ko. Tying the lifetime of user_return_msrs to
vendor modules makes every access to user_return_msrs prone to
use-after-free issues as vendor modules may be unloaded at any time.

kvm_nr_uret_msrs is still reset to 0 when vendor modules are loaded to
clear out the user return MSR list configured by the previous vendor
module.

Signed-off-by: Chao Gao <chao.gao@intel.com>
---
 arch/x86/kvm/x86.c | 21 +++++++++++----------
 1 file changed, 11 insertions(+), 10 deletions(-)

diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index bb7a7515f280..ab411bd09567 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -575,18 +575,17 @@ static inline void kvm_async_pf_hash_reset(struct
kvm_vcpu *vcpu)
		vcpu->arch.apf.gfns[i] = ~0;
 }
 
-static int kvm_init_user_return_msrs(void)
+static int __init kvm_init_user_return_msrs(void)
 {
	user_return_msrs = alloc_percpu(struct kvm_user_return_msrs);
	if (!user_return_msrs) {
		pr_err("failed to allocate percpu user_return_msrs\n");
		return -ENOMEM;
	}
-	kvm_nr_uret_msrs = 0;
	return 0;
 }
 
-static void kvm_free_user_return_msrs(void)
+static void __exit kvm_free_user_return_msrs(void)
 {
	int cpu;
 
@@ -10044,13 +10043,11 @@ int kvm_x86_vendor_init(struct kvm_x86_init_ops
*ops)
		return -ENOMEM;
	}
 
-	r = kvm_init_user_return_msrs();
-	if (r)
-		goto out_free_x86_emulator_cache;
+	kvm_nr_uret_msrs = 0;
 
	r = kvm_mmu_vendor_module_init();
	if (r)
-		goto out_free_percpu;
+		goto out_free_x86_emulator_cache;
 
	kvm_caps.supported_vm_types = BIT(KVM_X86_DEFAULT_VM);
	kvm_caps.supported_mce_cap = MCG_CTL_P | MCG_SER_P;
@@ -10148,8 +10145,6 @@ int kvm_x86_vendor_init(struct kvm_x86_init_ops
*ops)
	kvm_x86_call(hardware_unsetup)();
 out_mmu_exit:
	kvm_mmu_vendor_module_exit();
-out_free_percpu:
-	kvm_free_user_return_msrs();
 out_free_x86_emulator_cache:
	kmem_cache_destroy(x86_emulator_cache);
	return r;
@@ -10178,7 +10173,6 @@ void kvm_x86_vendor_exit(void)
 #endif
	kvm_x86_call(hardware_unsetup)();
	kvm_mmu_vendor_module_exit();
-	kvm_free_user_return_msrs();
	kmem_cache_destroy(x86_emulator_cache);
 #ifdef CONFIG_KVM_XEN
	static_key_deferred_flush(&kvm_xen_enabled);
@@ -14361,8 +14355,14 @@ EXPORT_TRACEPOINT_SYMBOL_GPL(kvm_rmp_fault);
 
 static int __init kvm_x86_init(void)
 {
+	int r;
+
	kvm_init_xstate_sizes();
 
+	r = kvm_init_user_return_msrs();
+	if (r)
+		return r;
+
	kvm_mmu_x86_module_init();
	mitigate_smt_rsb &= boot_cpu_has_bug(X86_BUG_SMT_RSB) &&
cpu_smt_possible();
	return 0;
@@ -14371,6 +14371,7 @@ module_init(kvm_x86_init);
 
 static void __exit kvm_x86_exit(void)
 {
+	kvm_free_user_return_msrs();
	WARN_ON_ONCE(static_branch_unlikely(&kvm_has_noapic_vcpu));
 }
 module_exit(kvm_x86_exit);

---

## [17] Sean Christopherson — 2025-11-07
*Subject: Re: [PATCH v5 3/4] KVM: x86: Leave user-return notifier registered on reboot/shutdown*

On Fri, Nov 07, 2025, Chao Gao wrote:
> On Thu, Oct 30, 2025 at 12:15:27PM -0700, Sean Christopherson wrote:
> >diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c

Gah, you're right.  I considered the complications with vendor modules, but missed
the kvm_x86_vendor_exit() angle.

> >From 0269f0ee839528e8a9616738d615a096901d6185 Mon Sep 17 00:00:00 2001
> From: Chao Gao <chao.gao@intel.com>

Hmm, the other idea would to stash the owner in kvm_x86_ops, and then do:

		__module_get(kvm_x86_ops.owner);

LOL, but that's even more flawed from a certain perspective, because
kvm_x86_ops.owner could be completely stale, especially if this races with
kvm_x86_vendor_exit().

> +static void __exit kvm_free_user_return_msrs(void)
>  {

For maximum paranoia, we should zero at exit() and WARN at init().

> 	r = kvm_mmu_vendor_module_init();
> 	if (r)

Rather than dynamically allocate the array of structures, we can "statically"
allocate it when the module is loaded.

I'll post this as a proper patch (with my massages) once I've tested.

Thanks much!

(and I forgot to hit "send", so this is going to show up after the patch, sorry)

---

## [18] Sean Christopherson — 2025-11-10
*Subject: Re: [PATCH v5 0/4] KVM: x86: User-return MSR fix+cleanups*

On Thu, 30 Oct 2025 12:15:24 -0700, Sean Christopherson wrote:
> Fix a bug in TDX where KVM will incorrectly update the current user-return
> MSR values when the TDX-Module doesn't actually clobber the relevant MSRs,

Applied to kvm-x86 misc, thanks!

[1/4] KVM: TDX: Explicitly set user-return MSRs that *may* be clobbered by the TDX-Module
      https://github.com/kvm-x86/linux/commit/c0711f8c610e
[2/4] KVM: x86: WARN if user-return MSR notifier is registered on exit
      https://github.com/kvm-x86/linux/commit/b371174d2fa6
[3/4] KVM: x86: Leave user-return notifier registered on reboot/shutdown
      https://github.com/kvm-x86/linux/commit/2baa33a8ddd6
[4/4] KVM: x86: Don't disable IRQs when unregistering user-return notifier
      https://github.com/kvm-x86/linux/commit/995d504100cf

--
https://github.com/kvm-x86/linux/tree/next

---
