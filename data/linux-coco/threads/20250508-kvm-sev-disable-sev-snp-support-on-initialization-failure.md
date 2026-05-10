---
title: 'KVM: SEV: Disable SEV-SNP support on initialization failure'
date: 2025-05-08
last_reply: 2025-05-09
message_count: 5
participants: ['Ashish Kalra', 'Tom Lendacky', 'Paluri, PavanKumar']
---

## [1] Ashish Kalra — 2025-05-08

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
 arch/x86/kvm/svm/sev.c | 43 +++++++++++++++++++++++++++++++++---------
 1 file changed, 34 insertions(+), 9 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index ada53f04158c..a6abdb26f877 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2934,6 +2934,32 @@ void __init sev_set_cpu_caps(void)
 	}
 }
 
+static bool sev_is_snp_initialized(void)
+{
+	struct sev_user_data_snp_status *status;
+	struct sev_data_snp_addr buf;
+	bool initialized = false;
+	void *data;
+	int error;
+
+	data = snp_alloc_firmware_page(GFP_KERNEL_ACCOUNT | __GFP_ZERO);
+	if (!data)
+		return initialized;
+
+	buf.address = __psp_pa(data);
+	if (sev_do_cmd(SEV_CMD_SNP_PLATFORM_STATUS, &buf, &error))
+		goto out;
+
+	status = (struct sev_user_data_snp_status *)data;
+	if (status->state)
+		initialized = true;
+
+out:
+	snp_free_firmware_page(data);
+
+	return initialized;
+}
+
 void __init sev_hardware_setup(void)
 {
 	unsigned int eax, ebx, ecx, edx, sev_asid_count, sev_es_asid_count;
@@ -3038,6 +3064,14 @@ void __init sev_hardware_setup(void)
 	sev_snp_supported = sev_snp_enabled && cc_platform_has(CC_ATTR_HOST_SEV_SNP);
 
 out:
+	if (sev_enabled) {
+		init_args.probe = true;
+		if (sev_platform_init(&init_args))
+			sev_supported = sev_es_supported = sev_snp_supported = false;
+		else
+			sev_snp_supported &= sev_is_snp_initialized();
+	}
+
 	if (boot_cpu_has(X86_FEATURE_SEV))
 		pr_info("SEV %s (ASIDs %u - %u)\n",
 			sev_supported ? min_sev_asid <= max_sev_asid ? "enabled" :
@@ -3064,15 +3098,6 @@ void __init sev_hardware_setup(void)
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

## [2] Tom Lendacky — 2025-05-09
*Subject: Re: [PATCH] KVM: SEV: Disable SEV-SNP support on initialization
 failure*

On 5/8/25 17:52, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

No need for 'data', just allocate directly to 'status', no?

> +	int error;
> +

	if (!sev_snp_supported)
		return false;

No need to issue the command if it doesn't matter.

> +	data = snp_alloc_firmware_page(GFP_KERNEL_ACCOUNT | __GFP_ZERO);

GFP_KERNEL instead of GFP_KERNEL_ACCOUNT ?

> +	if (!data)
> +		return initialized;

		return false;

I like explicit values in these conditions, but that's just me.

> +
> +	buf.address = __psp_pa(data);

You should issue an error message here or not pass in error (I would
prefer the former).

> +		goto out;
> +

	initialized = !!status->state; ?

> +
> +out:

With changes above, then you can just do:

	sev_snp_supported = sev_is_snp_initialized()

Thanks,
Tom

> +	}
> +

---

## [3] Paluri, PavanKumar — 2025-05-09
*Subject: Re: [PATCH] KVM: SEV: Disable SEV-SNP support on initialization
 failure*

On 5/8/2025 5:52 PM, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

s/sev_is_snp_initialized/is_sev_snp_initalized looks better.

> +{
> +	struct sev_user_data_snp_status *status;

On what kernel version is this patch based on? I do not see the below
diff in 6.15-rc5.

Thanks,
Pavan
> -
> -	if (!sev_enabled)

---

## [4] Kalra, Ashish — 2025-05-09
*Subject: Re: [PATCH] KVM: SEV: Disable SEV-SNP support on initialization
 failure*

On 5/9/2025 12:01 PM, Paluri, PavanKumar wrote:
> 
> 

Actually the convention is sev_is_xx(). 
 
>> +{
>> +	struct sev_user_data_snp_status *status;

This is based on linux-next.

Thanks,
Ashish
 
> Thanks,
> Pavan

---

## [5] Tom Lendacky — 2025-05-09
*Subject: Re: [PATCH] KVM: SEV: Disable SEV-SNP support on initialization
 failure*

On 5/9/25 12:52, Kalra, Ashish wrote:
> 
> On 5/9/2025 12:01 PM, Paluri, PavanKumar wrote:

Except that it is a static, so doesn't need to start with sev_. See
is_pfn_range_shared(), max_level_for_order(), etc. in the same file.

Thanks,
Tom

>  
>>> +{

---
