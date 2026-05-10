---
title: 'KVM: SEV: Fix unused variable in guest request handling'
date: 2024-05-13
last_reply: 2024-05-20
message_count: 5
participants: ['Michael Roth', 'Carlos Bilbao', 'Markus Elfring']
---

## [1] Michael Roth — 2024-05-13

The variable 'sev' is assigned, but never used. Remove it.

Fixes: 449ead2d1edb ("KVM: SEV: Provide support for SNP_GUEST_REQUEST NAE event")
Signed-off-by: Michael Roth <michael.roth@amd.com>
---
 arch/x86/kvm/svm/sev.c | 3 ---
 1 file changed, 3 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 59c0d89a4d52..6cf665c410b2 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -3965,14 +3965,11 @@ static int __snp_handle_guest_req(struct kvm *kvm, gpa_t req_gpa, gpa_t resp_gpa
 				  sev_ret_code *fw_err)
 {
 	struct sev_data_snp_guest_request data = {0};
-	struct kvm_sev_info *sev;
 	int ret;
 
 	if (!sev_snp_guest(kvm))
 		return -EINVAL;
 
-	sev = &to_kvm_svm(kvm)->sev_info;
-
 	ret = snp_setup_guest_buf(kvm, &data, req_gpa, resp_gpa);
 	if (ret)
 		return ret;

---

## [2] Carlos Bilbao — 2024-05-18
*Subject: Re: [PATCH] KVM: SEV: Fix unused variable in guest request handling*

On 5/13/24 13:19, Michael Roth wrote:

> The variable 'sev' is assigned, but never used. Remove it.
>


Reviewed-by: Carlos Bilbao <carlos.bilbao.osdev@gmail.com>


> ---
>  arch/x86/kvm/svm/sev.c | 3 ---

---

## [3] Markus Elfring — 2024-05-19
*Subject: Re: [PATCH] KVM: SEV: Fix unused variable in guest request handling*

> The variable 'sev' is assigned, but never used. Remove it.

Would it be a bit nicer to use the word “Omit” instead of “Fix”
in the summary phrase?

Regards,
Markus

---

## [4] Carlos Bilbao — 2024-05-20
*Subject: Re: [PATCH] KVM: SEV: Fix unused variable in guest request handling*

Hey Markus,

On 5/19/24 12:50 AM, Markus Elfring wrote:
>> The variable 'sev' is assigned, but never used. Remove it.
> Would it be a bit nicer to use the word “Omit” instead of “Fix”


I can find many instances of "Fix unused variable" in the history of the
kernel:

ubsan: fix unused variable warning in test module
x86/resctrl: Fix unused variable warning in cache_alloc_hsw_probe()
octeontx2-pf: Fix unused variable build error
etc...

but not a single "Omit unused variable" commit.


>
> Regards,


Thanks,
Carlos

---

## [5] Markus Elfring — 2024-05-20
*Subject: Re: KVM: SEV: Fix unused variable in guest request handling*

>>> The variable 'sev' is assigned, but never used. Remove it.
>> Would it be a bit nicer to use the word “Omit” instead of “Fix”
…
> but not a single "Omit unused variable" commit.

Some implementation details were fixed somehow because of a warning or error message.
You would probably like to point the desire out in your summary phrase
to get rid of another bit of redundant source code.

Were any analysis tools involved in the discovery of corresponding change possibilities?

Regards,
Markus

---
