---
title: 'x86/sev: Do not touch VMSA pages during kdump of SNP guest memory'
date: 2025-04-28
last_reply: 2025-04-30
message_count: 4
participants: ['Ashish Kalra', 'Tom Lendacky', 'Gupta, Pankaj', 'Borislav Petkov']
---

## [1] Ashish Kalra — 2025-04-28

From: Ashish Kalra <ashish.kalra@amd.com>

When kdump is running makedumpfile to generate vmcore and dumping SNP
guest memory it touches the VMSA page of the vCPU executing kdump which
then results in unrecoverable #NPF/RMP faults as the VMSA page is
marked busy/in-use when the vCPU is running and subsequently causes
guest softlockup/hang.

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
 arch/x86/coco/sev/core.c | 241 +++++++++++++++++++++++++--------------
 1 file changed, 155 insertions(+), 86 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index dcfaa698d6cf..f4eb5b645239 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -877,6 +877,99 @@ void snp_accept_memory(phys_addr_t start, phys_addr_t end)
 	set_pages_state(vaddr, npages, SNP_PAGE_STATE_PRIVATE);
 }
 
+static int vmgexit_ap_control(u64 event, struct sev_es_save_area *vmsa, u32 apic_id)
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
+	if (event == SVM_VMGEXIT_AP_CREATE)
+		ghcb_set_rax(ghcb, vmsa->sev_features);
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
+static int snp_set_vmsa(void *va, void *caa, int apic_id, bool make_vmsa)
+{
+	int ret;
+
+	if (snp_vmpl) {
+		struct svsm_call call = {};
+		unsigned long flags;
+
+		local_irq_save(flags);
+
+		call.caa = this_cpu_read(svsm_caa);
+		call.rcx = __pa(va);
+
+		if (make_vmsa) {
+			/* Protocol 0, Call ID 2 */
+			call.rax = SVSM_CORE_CALL(SVSM_CORE_CREATE_VCPU);
+			call.rdx = __pa(caa);
+			call.r8  = apic_id;
+		} else {
+			/* Protocol 0, Call ID 3 */
+			call.rax = SVSM_CORE_CALL(SVSM_CORE_DELETE_VCPU);
+		}
+
+		ret = svsm_perform_call_protocol(&call);
+
+		local_irq_restore(flags);
+	} else {
+		/*
+		 * If the kernel runs at VMPL0, it can change the VMSA
+		 * bit for a page using the RMPADJUST instruction.
+		 * However, for the instruction to succeed it must
+		 * target the permissions of a lesser privileged (higher
+		 * numbered) VMPL level, so use VMPL1.
+		 */
+		u64 attrs = 1;
+
+		if (make_vmsa)
+			attrs |= RMPADJUST_VMSA_PAGE_BIT;
+
+		ret = rmpadjust((unsigned long)va, RMP_PG_SIZE_4K, attrs);
+	}
+
+	return ret;
+}
+
+static void snp_cleanup_vmsa(struct sev_es_save_area *vmsa, int apic_id)
+{
+	int err;
+
+	err = snp_set_vmsa(vmsa, NULL, apic_id, false);
+	if (err)
+		pr_err("clear VMSA page failed (%u), leaking page\n", err);
+	else
+		free_page((unsigned long)vmsa);
+}
+
 static void set_pte_enc(pte_t *kpte, int level, void *va)
 {
 	struct pte_enc_desc d = {
@@ -973,6 +1066,65 @@ void snp_kexec_begin(void)
 		pr_warn("Failed to stop shared<->private conversions\n");
 }
 
+/*
+ * Shutdown all APs except the one handling kexec/kdump and clearing
+ * the VMSA tag on AP's VMSA pages as they are not being used as
+ * VMSA page anymore.
+ */
+static void shutdown_all_aps(void)
+{
+	struct sev_es_save_area *vmsa;
+	int apic_id, this_cpu, cpu;
+
+	this_cpu = get_cpu();
+
+	/*
+	 * APs are already in HLT loop when enc_kexec_finish() callback
+	 * is invoked.
+	 */
+	for_each_present_cpu(cpu) {
+		vmsa = per_cpu(sev_vmsa, cpu);
+
+		/*
+		 * BSP does not have guest allocated VMSA and there is no need
+		 * to clear the VMSA tag for this page.
+		 */
+		if (!vmsa)
+			continue;
+
+		/*
+		 * Cannot clear the VMSA tag for the currently running vCPU.
+		 */
+		if (this_cpu == cpu) {
+			unsigned long pa;
+			struct page *p;
+
+			pa = __pa(vmsa);
+			/*
+			 * Mark the VMSA page of the running vCPU as offline
+			 * so that is excluded and not touched by makedumpfile
+			 * while generating vmcore during kdump.
+			 */
+			p = pfn_to_online_page(pa >> PAGE_SHIFT);
+			if (p)
+				__SetPageOffline(p);
+			continue;
+		}
+
+		apic_id = cpuid_to_apicid[cpu];
+
+		/*
+		 * Issue AP destroy to ensure AP gets kicked out of guest mode
+		 * to allow using RMPADJUST to remove the VMSA tag on it's
+		 * VMSA page.
+		 */
+		vmgexit_ap_control(SVM_VMGEXIT_AP_DESTROY, vmsa, apic_id);
+		snp_cleanup_vmsa(vmsa, apic_id);
+	}
+
+	put_cpu();
+}
+
 void snp_kexec_finish(void)
 {
 	struct sev_es_runtime_data *data;
@@ -987,6 +1139,8 @@ void snp_kexec_finish(void)
 	if (!IS_ENABLED(CONFIG_KEXEC_CORE))
 		return;
 
+	shutdown_all_aps();
+
 	unshare_all_memory();
 
 	/*
@@ -1008,51 +1162,6 @@ void snp_kexec_finish(void)
 	}
 }
 
-static int snp_set_vmsa(void *va, void *caa, int apic_id, bool make_vmsa)
-{
-	int ret;
-
-	if (snp_vmpl) {
-		struct svsm_call call = {};
-		unsigned long flags;
-
-		local_irq_save(flags);
-
-		call.caa = this_cpu_read(svsm_caa);
-		call.rcx = __pa(va);
-
-		if (make_vmsa) {
-			/* Protocol 0, Call ID 2 */
-			call.rax = SVSM_CORE_CALL(SVSM_CORE_CREATE_VCPU);
-			call.rdx = __pa(caa);
-			call.r8  = apic_id;
-		} else {
-			/* Protocol 0, Call ID 3 */
-			call.rax = SVSM_CORE_CALL(SVSM_CORE_DELETE_VCPU);
-		}
-
-		ret = svsm_perform_call_protocol(&call);
-
-		local_irq_restore(flags);
-	} else {
-		/*
-		 * If the kernel runs at VMPL0, it can change the VMSA
-		 * bit for a page using the RMPADJUST instruction.
-		 * However, for the instruction to succeed it must
-		 * target the permissions of a lesser privileged (higher
-		 * numbered) VMPL level, so use VMPL1.
-		 */
-		u64 attrs = 1;
-
-		if (make_vmsa)
-			attrs |= RMPADJUST_VMSA_PAGE_BIT;
-
-		ret = rmpadjust((unsigned long)va, RMP_PG_SIZE_4K, attrs);
-	}
-
-	return ret;
-}
-
 #define __ATTR_BASE		(SVM_SELECTOR_P_MASK | SVM_SELECTOR_S_MASK)
 #define INIT_CS_ATTRIBS		(__ATTR_BASE | SVM_SELECTOR_READ_MASK | SVM_SELECTOR_CODE_MASK)
 #define INIT_DS_ATTRIBS		(__ATTR_BASE | SVM_SELECTOR_WRITE_MASK)
@@ -1084,24 +1193,10 @@ static void *snp_alloc_vmsa_page(int cpu)
 	return page_address(p + 1);
 }
 
-static void snp_cleanup_vmsa(struct sev_es_save_area *vmsa, int apic_id)
-{
-	int err;
-
-	err = snp_set_vmsa(vmsa, NULL, apic_id, false);
-	if (err)
-		pr_err("clear VMSA page failed (%u), leaking page\n", err);
-	else
-		free_page((unsigned long)vmsa);
-}
-
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
@@ -1215,33 +1310,7 @@ static int wakeup_cpu_via_vmgexit(u32 apic_id, unsigned long start_ip)
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
-
-	/* Perform cleanup if there was an error */
+	ret = vmgexit_ap_control(SVM_VMGEXIT_AP_CREATE, vmsa, apic_id);
 	if (ret) {
 		snp_cleanup_vmsa(vmsa, apic_id);
 		vmsa = NULL;

---

## [2] Tom Lendacky — 2025-04-29
*Subject: Re: [PATCH v3] x86/sev: Do not touch VMSA pages during kdump of SNP
 guest memory*

On 4/28/25 16:41, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

> ---
>  arch/x86/coco/sev/core.c | 241 +++++++++++++++++++++++++--------------

---

## [3] Gupta, Pankaj — 2025-04-30
*Subject: Re: [PATCH v3] x86/sev: Do not touch VMSA pages during kdump of SNP
 guest memory*

> When kdump is running makedumpfile to generate vmcore and dumping SNP
> guest memory it touches the VMSA page of the vCPU executing kdump which

Reviewed-by: Pankaj Gupta <pankaj.gupta@amd.com>

> ---
>   arch/x86/coco/sev/core.c | 241 +++++++++++++++++++++++++--------------

---

## [4] Borislav Petkov — 2025-04-30
*Subject: Re: [PATCH v3] x86/sev: Do not touch VMSA pages during kdump of SNP
 guest memory*

On Mon, Apr 28, 2025 at 09:41:51PM +0000, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Some minor cleanups ontop:

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index b031cabb2ccf..9ac902d022bf 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -961,6 +961,7 @@ void snp_accept_memory(phys_addr_t start, phys_addr_t end)
 
 static int vmgexit_ap_control(u64 event, struct sev_es_save_area *vmsa, u32 apic_id)
 {
+	bool create = event == SVM_VMGEXIT_AP_CREATE;
 	struct ghcb_state state;
 	unsigned long flags;
 	struct ghcb *ghcb;
@@ -971,8 +972,10 @@ static int vmgexit_ap_control(u64 event, struct sev_es_save_area *vmsa, u32 apic
 	ghcb = __sev_get_ghcb(&state);
 
 	vc_ghcb_invalidate(ghcb);
-	if (event == SVM_VMGEXIT_AP_CREATE)
+
+	if (create)
 		ghcb_set_rax(ghcb, vmsa->sev_features);
+
 	ghcb_set_sw_exit_code(ghcb, SVM_VMGEXIT_AP_CREATION);
 	ghcb_set_sw_exit_info_1(ghcb,
 				((u64)apic_id << 32)	|
@@ -985,7 +988,7 @@ static int vmgexit_ap_control(u64 event, struct sev_es_save_area *vmsa, u32 apic
 
 	if (!ghcb_sw_exit_info_1_is_valid(ghcb) ||
 	    lower_32_bits(ghcb->save.sw_exit_info_1)) {
-		pr_err("SNP AP %s error\n", (event == SVM_VMGEXIT_AP_CREATE ? "CREATE" : "DESTROY"));
+		pr_err("SNP AP %s error\n", (create ? "CREATE" : "DESTROY"));
 		ret = -EINVAL;
 	}
 
@@ -1168,8 +1171,8 @@ static void shutdown_all_aps(void)
 		vmsa = per_cpu(sev_vmsa, cpu);
 
 		/*
-		 * BSP does not have guest allocated VMSA and there is no need
-		 * to clear the VMSA tag for this page.
+		 * The BSP or offlined APs do not have guest allocated VMSA
+		 * and there is no need  to clear the VMSA tag for this page.
 		 */
 		if (!vmsa)
 			continue;

---
