---
title: 'KVM: SEV: Disable SEV-SNP support on initialization failure'
date: 2025-05-12
last_reply: 2025-05-12
message_count: 2
participants: ['Ashish Kalra', 'Tom Lendacky']
---

## [1] Ashish Kalra — 2025-05-12

From: Ashish Kalra <ashish.kalra@amd.com>

During platform init, SNP initialization may fail for several reasons,
such as firmware command failures and incompatible versions. However,
the KVM capability may continue to advertise support for it.

The platform may have SNP enabled but if SNP_INIT fails then SNP is
not supported by KVM.

During KVM module initialization query the SNP platform status to obtain
the SNP initialization state and use it as an additional condition to
determine support for SEV-SNP.

Co-developed-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
Co-developed-by: Pratik R. Sampat <prsampat@amd.com>
Signed-off-by: Pratik R. Sampat <prsampat@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/kvm/svm/sev.c | 44 +++++++++++++++++++++++++++++++++---------
 1 file changed, 35 insertions(+), 9 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index dea9480b9ff6..f7d343ab9acd 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2935,6 +2935,33 @@ void __init sev_set_cpu_caps(void)
 	}
 }
 
+static bool is_sev_snp_initialized(void)
+{
+	struct sev_user_data_snp_status *status;
+	struct sev_data_snp_addr buf;
+	bool initialized = false;
+	int error, ret;
+
+	status = snp_alloc_firmware_page(GFP_KERNEL | __GFP_ZERO);
+	if (!status)
+		return false;
+
+	buf.address = __psp_pa(status);
+	ret = sev_do_cmd(SEV_CMD_SNP_PLATFORM_STATUS, &buf, &error);
+	if (ret) {
+		pr_err("SEV: SNP_PLATFORM_STATUS failed ret=%d, fw_error=%d (%#x)\n",
+		       ret, error, error);
+		goto out;
+	}
+
+	initialized = !!status->state;
+
+out:
+	snp_free_firmware_page(status);
+
+	return initialized;
+}
+
 void __init sev_hardware_setup(void)
 {
 	unsigned int eax, ebx, ecx, edx, sev_asid_count, sev_es_asid_count;
@@ -3039,6 +3066,14 @@ void __init sev_hardware_setup(void)
 	sev_snp_supported = sev_snp_enabled && cc_platform_has(CC_ATTR_HOST_SEV_SNP);
 
 out:
+	if (sev_enabled) {
+		init_args.probe = true;
+		if (sev_platform_init(&init_args))
+			sev_supported = sev_es_supported = sev_snp_supported = false;
+		else if (sev_snp_supported)
+			sev_snp_supported = is_sev_snp_initialized();
+	}
+
 	if (boot_cpu_has(X86_FEATURE_SEV))
 		pr_info("SEV %s (ASIDs %u - %u)\n",
 			sev_supported ? min_sev_asid <= max_sev_asid ? "enabled" :
@@ -3065,15 +3100,6 @@ void __init sev_hardware_setup(void)
 	sev_supported_vmsa_features = 0;
 	if (sev_es_debug_swap_enabled)
 		sev_supported_vmsa_features |= SVM_SEV_FEAT_DEBUG_SWAP;
-
-	if (!sev_enabled)
-		return;
-
-	/*
-	 * Do both SNP and SEV initialization at KVM module load.
-	 */
-	init_args.probe = true;
-	sev_platform_init(&init_args);
 }
 
 void sev_hardware_unsetup(void)

---

## [2] Tom Lendacky — 2025-05-12
*Subject: Re: [PATCH v2] KVM: SEV: Disable SEV-SNP support on initialization
 failure*

On 5/12/25 16:04, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

One comment below, otherwise:

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

> ---
>  arch/x86/kvm/svm/sev.c | 44 +++++++++++++++++++++++++++++++++---------

You'll want to initialize error to 0 or you'll get a possible use of
uninitialized variable.

Thanks,
Tom

> +	if (ret) {
> +		pr_err("SEV: SNP_PLATFORM_STATUS failed ret=%d, fw_error=%d (%#x)\n",

---
