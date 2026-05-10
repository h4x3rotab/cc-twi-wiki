---
title: '[RFC PATCH] x86/sev: Cleanup vc_handle_msr()'
date: 2024-11-06
last_reply: 2024-11-07
message_count: 4
participants: ['Borislav Petkov (AMD)', 'Tom Lendacky', 'Gupta, Pankaj']
---

## [1] Borislav Petkov (AMD) — 2024-11-06

Hi,

I think we should clean this one up before in-flight patchsets make it more
unreadable and in need for an even more cleanup.

---
Carve out the MSR_SVSM_CAA into a helper with the suggestion that
upcoming future users should do the same. Rename that silly exit_info_1
into what it actually means in this function - whether the MSR access is
a read or a write.

No functional changes.

Signed-off-by: Borislav Petkov (AMD) <bp@alien8.de>
---
 arch/x86/coco/sev/core.c | 34 +++++++++++++++++++---------------
 1 file changed, 19 insertions(+), 15 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 97f445f3366a..1efb4a5c5ab3 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -1406,35 +1406,39 @@ int __init sev_es_efi_map_ghcbs(pgd_t *pgd)
 	return 0;
 }
 
+/* Writes to the SVSM CAA MSR are ignored */
+static enum es_result __vc_handle_msr_caa(struct pt_regs *regs, bool write)
+{
+	if (write)
+		return ES_OK;
+
+	regs->ax = lower_32_bits(this_cpu_read(svsm_caa_pa));
+	regs->dx = upper_32_bits(this_cpu_read(svsm_caa_pa));
+
+	return ES_OK;
+}
+
 static enum es_result vc_handle_msr(struct ghcb *ghcb, struct es_em_ctxt *ctxt)
 {
 	struct pt_regs *regs = ctxt->regs;
 	enum es_result ret;
-	u64 exit_info_1;
+	bool write;
 
 	/* Is it a WRMSR? */
-	exit_info_1 = (ctxt->insn.opcode.bytes[1] == 0x30) ? 1 : 0;
-
-	if (regs->cx == MSR_SVSM_CAA) {
-		/* Writes to the SVSM CAA msr are ignored */
-		if (exit_info_1)
-			return ES_OK;
-
-		regs->ax = lower_32_bits(this_cpu_read(svsm_caa_pa));
-		regs->dx = upper_32_bits(this_cpu_read(svsm_caa_pa));
+	write = ctxt->insn.opcode.bytes[1] == 0x30;
 
-		return ES_OK;
-	}
+	if (regs->cx == MSR_SVSM_CAA)
+		return __vc_handle_msr_caa(regs, write);
 
 	ghcb_set_rcx(ghcb, regs->cx);
-	if (exit_info_1) {
+	if (write) {
 		ghcb_set_rax(ghcb, regs->ax);
 		ghcb_set_rdx(ghcb, regs->dx);
 	}
 
-	ret = sev_es_ghcb_hv_call(ghcb, ctxt, SVM_EXIT_MSR, exit_info_1, 0);
+	ret = sev_es_ghcb_hv_call(ghcb, ctxt, SVM_EXIT_MSR, !!write, 0);
 
-	if ((ret == ES_OK) && (!exit_info_1)) {
+	if ((ret == ES_OK) && (!write)) {
 		regs->ax = ghcb->save.rax;
 		regs->dx = ghcb->save.rdx;
 	}

---

## [2] Tom Lendacky — 2024-11-06
*Subject: Re: [RFC PATCH] x86/sev: Cleanup vc_handle_msr()*

On 11/6/24 11:26, Borislav Petkov (AMD) wrote:
> Hi,
> 

Is the !! necessary? It should have either 0 or 1 because of the boolean
operation used to set it, right?

>  
> -	if ((ret == ES_OK) && (!exit_info_1)) {

I guess the parentheses around "!write" can be removed while your at it.

Other than those two little things...

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

>  		regs->ax = ghcb->save.rax;
>  		regs->dx = ghcb->save.rdx;

---

## [3] Borislav Petkov — 2024-11-06
*Subject: Re: [RFC PATCH] x86/sev: Cleanup vc_handle_msr()*

On Wed, Nov 06, 2024 at 01:40:47PM -0600, Tom Lendacky wrote:
> Is the !! necessary? It should have either 0 or 1 because of the boolean
> operation used to set it, right?

I was going to be overly cautious but integer promotion will make sure there
really is a 0 or a 1. So yeah, I can drop the !!.

> 
> >  

Ack.

> Other than those two little things...
> 

Thanks!

---

## [4] Gupta, Pankaj — 2024-11-07
*Subject: Re: [RFC PATCH] x86/sev: Cleanup vc_handle_msr()*

On 11/6/2024 6:26 PM, Borislav Petkov (AMD) wrote:
> Hi,
> 

LGTM

With minor comments from Tom,

Reviewed-by: Pankaj Gupta <pankaj.gupta@amd.com>

> ---
>   arch/x86/coco/sev/core.c | 34 +++++++++++++++++++---------------

---
