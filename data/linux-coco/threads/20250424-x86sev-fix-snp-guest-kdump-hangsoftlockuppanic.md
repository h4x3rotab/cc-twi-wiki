---
title: 'x86/sev: Fix SNP guest kdump hang/softlockup/panic'
date: 2025-04-24
last_reply: 2025-04-24
message_count: 5
participants: ['Ashish Kalra', 'Borislav Petkov', 'Tom Lendacky']
---

## [1] Ashish Kalra — 2025-04-24

From: Ashish Kalra <ashish.kalra@amd.com>

When kdump is running makedumpfile to generate vmcore and dumping SNP
guest memory it touches the VMSA page of the vCPU executing kdump which
then results in unrecoverable #NPF/RMP faults as the VMSA page is
marked busy/in-use when the vCPU is running.

This leads to guest softlockup/hang:

[  117.111097] watchdog: BUG: soft lockup - CPU#0 stuck for 27s! [cp:318]
[  117.111165] CPU: 0 UID: 0 PID: 318 Comm: cp Not tainted 6.14.0-next-20250328-snp-host-f2a41ff576cc-dirty #414 VOLUNTARY
[  117.111171] Hardware name: QEMU Standard PC (Q35 + ICH9, 2009), BIOS unknown 02/02/2022
[  117.111176] RIP: 0010:rep_movs_alternative+0x5b/0x70
[  117.111200] Call Trace:
[  117.111204]  <TASK>
[  117.111206]  ? _copy_to_iter+0xc1/0x720
[  117.111216]  ? srso_return_thunk+0x5/0x5f
[  117.111220]  ? _raw_spin_unlock+0x27/0x40
[  117.111234]  ? srso_return_thunk+0x5/0x5f
[  117.111236]  ? find_vmap_area+0xd6/0xf0
[  117.111251]  ? srso_return_thunk+0x5/0x5f
[  117.111253]  ? __check_object_size+0x18d/0x2e0
[  117.111268]  __copy_oldmem_page.part.0+0x64/0xa0
[  117.111281]  copy_oldmem_page_encrypted+0x1d/0x30
[  117.111285]  read_from_oldmem.part.0+0xf4/0x200
[  117.111306]  read_vmcore+0x206/0x3c0
[  117.111309]  ? srso_return_thunk+0x5/0x5f
[  117.111325]  proc_reg_read_iter+0x59/0x90
[  117.111334]  vfs_read+0x26e/0x350

Additionally other APs may be halted in guest mode and their VMSA pages
are marked busy and touching these VMSA pages during guest memory dump
will also cause #NPF.

Issue AP_DESTROY GHCB calls on other APs to ensure they are kicked out
of guest mode and then clear the VMSA bit on their VMSA pages.

If the vCPU running kdump is an AP, mark it's VMSA page as offline to
ensure that makedumpfile excludes that page while dumping guest memory.

Cc: stable@vger.kernel.org
Fixes: 3074152e56c9 ("x86/sev: Convert shared memory back to private on kexec")
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/coco/sev/core.c | 129 ++++++++++++++++++++++++++++++---------
 1 file changed, 101 insertions(+), 28 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index dcfaa698d6cf..870f4994a13d 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -113,6 +113,8 @@ DEFINE_PER_CPU(struct sev_es_save_area *, sev_vmsa);
 DEFINE_PER_CPU(struct svsm_ca *, svsm_caa);
 DEFINE_PER_CPU(u64, svsm_caa_pa);
 
+static void snp_cleanup_vmsa(struct sev_es_save_area *vmsa, int apic_id);
+
 static __always_inline bool on_vc_stack(struct pt_regs *regs)
 {
 	unsigned long sp = regs->sp;
@@ -877,6 +879,42 @@ void snp_accept_memory(phys_addr_t start, phys_addr_t end)
 	set_pages_state(vaddr, npages, SNP_PAGE_STATE_PRIVATE);
 }
 
+static int issue_vmgexit_ap_create_destroy(u64 event, struct sev_es_save_area *vmsa, u32 apic_id)
+{
+	struct ghcb_state state;
+	unsigned long flags;
+	struct ghcb *ghcb;
+	int ret = 0;
+
+	local_irq_save(flags);
+
+	ghcb = __sev_get_ghcb(&state);
+
+	vc_ghcb_invalidate(ghcb);
+	ghcb_set_rax(ghcb, vmsa->sev_features);
+	ghcb_set_sw_exit_code(ghcb, SVM_VMGEXIT_AP_CREATION);
+	ghcb_set_sw_exit_info_1(ghcb,
+				((u64)apic_id << 32)	|
+				((u64)snp_vmpl << 16)	|
+				event);
+	ghcb_set_sw_exit_info_2(ghcb, __pa(vmsa));
+
+	sev_es_wr_ghcb_msr(__pa(ghcb));
+	VMGEXIT();
+
+	if (!ghcb_sw_exit_info_1_is_valid(ghcb) ||
+	    lower_32_bits(ghcb->save.sw_exit_info_1)) {
+		pr_err("SNP AP %s error\n", (event == SVM_VMGEXIT_AP_CREATE ? "CREATE" : "DESTROY"));
+		ret = -EINVAL;
+	}
+
+	__sev_put_ghcb(&state);
+
+	local_irq_restore(flags);
+
+	return ret;
+}
+
 static void set_pte_enc(pte_t *kpte, int level, void *va)
 {
 	struct pte_enc_desc d = {
@@ -973,6 +1011,66 @@ void snp_kexec_begin(void)
 		pr_warn("Failed to stop shared<->private conversions\n");
 }
 
+/*
+ * Shutdown all APs except the one handling kexec/kdump and clearing
+ * the VMSA tag on AP's VMSA pages as they are not being used as
+ * VMSA page anymore.
+ */
+static void snp_shutdown_all_aps(void)
+{
+	struct sev_es_save_area *vmsa;
+	int apic_id, cpu;
+
+	/*
+	 * APs are already in HLT loop when kexec_finish() is invoked.
+	 */
+	for_each_present_cpu(cpu) {
+		vmsa = per_cpu(sev_vmsa, cpu);
+
+		/*
+		 * BSP does not have guest allocated VMSA, so it's in-use/busy
+		 * VMSA cannot touch a guest page and there is no need to clear
+		 * the VMSA tag for this page.
+		 */
+		if (!vmsa)
+			continue;
+
+		/*
+		 * Cannot clear the VMSA tag for the currently running vCPU.
+		 */
+		if (get_cpu() == cpu) {
+			unsigned long pa;
+			struct page *p;
+
+			pa = __pa(vmsa);
+			p = pfn_to_online_page(pa >> PAGE_SHIFT);
+			/*
+			 * Mark the VMSA page of the running vCPU as Offline
+			 * so that is excluded and not touched by makedumpfile
+			 * while generating vmcore during kdump boot.
+			 */
+			if (p)
+				__SetPageOffline(p);
+			put_cpu();
+			continue;
+		}
+		put_cpu();
+
+		apic_id = cpuid_to_apicid[cpu];
+
+		/*
+		 * Issue AP destroy on all APs (to ensure they are kicked out
+		 * of guest mode) to allow using RMPADJUST to remove the VMSA
+		 * tag on VMSA pages especially for guests that allow HLT to
+		 * not be intercepted.
+		 */
+
+		issue_vmgexit_ap_create_destroy(SVM_VMGEXIT_AP_DESTROY, vmsa, apic_id);
+
+		snp_cleanup_vmsa(vmsa, apic_id);
+	}
+}
+
 void snp_kexec_finish(void)
 {
 	struct sev_es_runtime_data *data;
@@ -987,6 +1085,8 @@ void snp_kexec_finish(void)
 	if (!IS_ENABLED(CONFIG_KEXEC_CORE))
 		return;
 
+	snp_shutdown_all_aps();
+
 	unshare_all_memory();
 
 	/*
@@ -1098,10 +1198,7 @@ static void snp_cleanup_vmsa(struct sev_es_save_area *vmsa, int apic_id)
 static int wakeup_cpu_via_vmgexit(u32 apic_id, unsigned long start_ip)
 {
 	struct sev_es_save_area *cur_vmsa, *vmsa;
-	struct ghcb_state state;
 	struct svsm_ca *caa;
-	unsigned long flags;
-	struct ghcb *ghcb;
 	u8 sipi_vector;
 	int cpu, ret;
 	u64 cr4;
@@ -1215,31 +1312,7 @@ static int wakeup_cpu_via_vmgexit(u32 apic_id, unsigned long start_ip)
 	}
 
 	/* Issue VMGEXIT AP Creation NAE event */
-	local_irq_save(flags);
-
-	ghcb = __sev_get_ghcb(&state);
-
-	vc_ghcb_invalidate(ghcb);
-	ghcb_set_rax(ghcb, vmsa->sev_features);
-	ghcb_set_sw_exit_code(ghcb, SVM_VMGEXIT_AP_CREATION);
-	ghcb_set_sw_exit_info_1(ghcb,
-				((u64)apic_id << 32)	|
-				((u64)snp_vmpl << 16)	|
-				SVM_VMGEXIT_AP_CREATE);
-	ghcb_set_sw_exit_info_2(ghcb, __pa(vmsa));
-
-	sev_es_wr_ghcb_msr(__pa(ghcb));
-	VMGEXIT();
-
-	if (!ghcb_sw_exit_info_1_is_valid(ghcb) ||
-	    lower_32_bits(ghcb->save.sw_exit_info_1)) {
-		pr_err("SNP AP Creation error\n");
-		ret = -EINVAL;
-	}
-
-	__sev_put_ghcb(&state);
-
-	local_irq_restore(flags);
+	ret = issue_vmgexit_ap_create_destroy(SVM_VMGEXIT_AP_CREATE, vmsa, apic_id);
 
 	/* Perform cleanup if there was an error */
 	if (ret) {

---

## [2] Borislav Petkov — 2025-04-24
*Subject: Re: [PATCH v2] x86/sev: Fix SNP guest kdump hang/softlockup/panic*

Rn Thu, Apr 24, 2025 at 02:15:36PM +0000, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Definitely better. Thanks.

> This leads to guest softlockup/hang:
> 

I ask you again: why is that untrimmed splat needed here?

> Additionally other APs may be halted in guest mode and their VMSA pages
> are marked busy and touching these VMSA pages during guest memory dump

So, the title of this patch should be something like "Do not touch VMSA
pages during kdump of SNP guest memory" ?

Because what you have now cannot be any more indeterminate...

> Issue AP_DESTROY GHCB calls on other APs to ensure they are kicked out
> of guest mode and then clear the VMSA bit on their VMSA pages.

This one and the next one you sent are fixing both one and the same
patch - yours.

So, how much has this one and your other one:

https://lore.kernel.org/all/20250424142739.673666-1-Ashish.Kalra@amd.com

have been tested?

I'd like for those two to be extensively tested before I send them to
Linus in this cycle still so that they don't break anything.

> Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
> ---

No lazy forward declarations. Restructure your code pls so that you
don't need them.

> +
>  static __always_inline bool on_vc_stack(struct pt_regs *regs)

vmgexit_ap_control() or so.

> +{
> +	struct ghcb_state state;

Static function - no need for "snp_" prefix.

> +{
> +	struct sev_es_save_area *vmsa;

Which kexec_finish?

$ git grep -w kexec_finish
$

> +	 */

Btw, comment fits on one line.

> +	for_each_present_cpu(cpu) {

What if some CPUs are offlined? Or in this part of kexec that's not
a problem?

> +		vmsa = per_cpu(sev_vmsa, cpu);
> +

This comment's text needs sanitizing.

> +		 */
> +		if (!vmsa)

offline

> +			 * so that is excluded and not touched by makedumpfile
> +			 * while generating vmcore during kdump boot.

during kdump. No boot.

> +			 */

Put that comment above the previous line: p = pfn_...

> +			if (p)
> +				__SetPageOffline(p);

Restructure your code so that you don't need those two put_cpu()s there.

> +
> +		apic_id = cpuid_to_apicid[cpu];

This is not "on all" - it is only on this apic_id.

Also, your comment needs splitting into simple sentences as it tries to
say *everything* which is not really necessary.

> +

Superfluous newline.

Thx.

---

## [3] Tom Lendacky — 2025-04-24
*Subject: Re: [PATCH v2] x86/sev: Fix SNP guest kdump hang/softlockup/panic*

On 4/24/25 09:15, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

RAX should only be set on a SVM_VMGEXIT_AP_CREATE event.

> +	ghcb_set_sw_exit_code(ghcb, SVM_VMGEXIT_AP_CREATION);
> +	ghcb_set_sw_exit_info_1(ghcb,

Remove this blank line.

> +		issue_vmgexit_ap_create_destroy(SVM_VMGEXIT_AP_DESTROY, vmsa, apic_id);
> +

And this one.

> +		snp_cleanup_vmsa(vmsa, apic_id);
> +	}

You can remove the two lines above (the blank line and the comment) now
that the setting of ret is not a few lines before. That way you have

	/* Issue VMGEXIT AP Creation NAE event */
	ret = issue_vmgexit_ap_create_destroy(SVM_VMGEXIT_AP_CREATE, vmsa, apic_id);
	if (ret) {

and it's nicely grouped.

Thanks,
Tom

>  	if (ret) {

---

## [4] Kalra, Ashish — 2025-04-24
*Subject: Re: [PATCH v2] x86/sev: Fix SNP guest kdump hang/softlockup/panic*

Hello Boris,

On 4/24/2025 1:06 PM, Borislav Petkov wrote:
> Rn Thu, Apr 24, 2025 at 02:15:36PM +0000, Ashish Kalra wrote:
>> From: Ashish Kalra <ashish.kalra@amd.com>

I will remove this.

>> Additionally other APs may be halted in guest mode and their VMSA pages
>> are marked busy and touching these VMSA pages during guest memory dump

Ok, that makes sense.
 
> Because what you have now cannot be any more indeterminate...
> 

Both patches have been tested by me and additionally both have been tested
by Tencent in their development environment, so i would say they have been
tested fairly well. 

>> Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
>> ---

Ok.

>> +
>>  static __always_inline bool on_vc_stack(struct pt_regs *regs)

Ok.
 
>> +{
>> +	struct ghcb_state state;

Ok.
 
>> +{
>> +	struct sev_es_save_area *vmsa;

I meant the x86_platform.guest.enc_kexec_finish() callback, which in this case is snp_kexec_finish().

>> +	 */
> 

Yes, offlined CPUs won't have VMSA pages marked busy or in-use. 

>> +		vmsa = per_cpu(sev_vmsa, cpu);
>> +
Ok.

>> +		 */
>> +		if (!vmsa)
Ok.

>> +			if (p)
>> +				__SetPageOffline(p);
Ok.
 
>> +
>> +		apic_id = cpuid_to_apicid[cpu];
Yes.

> Also, your comment needs splitting into simple sentences as it tries to
> say *everything* which is not really necessary.

Ok.

Thanks,
Ashish
 
>> +
>

---

## [5] Borislav Petkov — 2025-04-24
*Subject: Re: [PATCH v2] x86/sev: Fix SNP guest kdump hang/softlockup/panic*

On Thu, Apr 24, 2025 at 02:45:28PM -0500, Kalra, Ashish wrote:
> Both patches have been tested by me and additionally both have been tested
> by Tencent in their development environment, so i would say they have been

Ok, once I queue them after all review feedback has been incorporated,
I'll give you a branch and I'd need you and Tencent folks to run the
final result one more time, please, before I send them upwards.

Thx.

---
