---
title: 'kvm: sev: Add SNP guest request throttling'
date: 2025-05-15
last_reply: 2025-05-28
message_count: 8
participants: ['Dionna Glaze', 'Sean Christopherson']
---

## [1] Dionna Glaze — 2025-05-15

The GHCB specification recommends that SNP guest requests should be
rate limited. Add a command to permit the VMM to set the rate limit
on a per-VM scale.

The AMD-SP is a global resource that must be shared across VMs, so
its time should be multiplexed across VMs fairly. It is the
responsibility of the VMM to ensure all SEV-SNP VMs have a rate limit
set such that the collective set of VMs on the machine have a rate of
access that does not exceed the device's capacity.

The sev-guest device already respects the SNP_GUEST_VMM_ERR_BUSY
result code, so utilize that result to cause the guest to retry after
waiting momentarily.

Changes since v4:
  * Fixed build failure caused by rebase.
  * Added ratelimit.h include.
  * Added rate bounds checking to stay within ratelimit types.
Changes since v3:
  * Rebased on master, changed module parameter to mem_enc_ioctl
    command. Changed commit descriptions. Much time has passed.
Changes since v2:
  * Rebased on v7, changed "we" wording to passive voice.
Changes since v1:
  * Added missing Ccs to patches.

Dionna Glaze (2):
  kvm: sev: Add SEV-SNP guest request throttling
  kvm: sev: If ccp is busy, report busy to guest

 .../virt/kvm/x86/amd-memory-encryption.rst    | 23 +++++++++++
 arch/x86/include/uapi/asm/kvm.h               |  7 ++++
 arch/x86/kvm/svm/sev.c                        | 38 +++++++++++++++++++
 arch/x86/kvm/svm/svm.h                        |  3 ++
 4 files changed, 71 insertions(+)

---

## [2] Dionna Glaze — 2025-05-15
*Subject: [PATCH v5 1/2] kvm: sev: Add SEV-SNP guest request throttling*

The AMD-SP is a precious resource that doesn't have a scheduler other
than a mutex lock queue. To avoid customers from causing a DoS, a
mem_enc_ioctl command for rate limiting guest requests is added.

Recommended values are {.interval_ms = 1000, .burst = 1} or
{.interval_ms = 2000, .burst = 2} to average 1 request every second.
You may need to allow 2 requests back to back to allow for the guest
to query the certificate length in an extended guest request without
a pause. The 1 second average is our target for quality of service
since empirical tests show that 64 VMs can concurrently request an
attestation report with a maximum latency of 1 second. We don't
anticipate more concurrency than that for a seldom used request for
a majority well-behaved set of VMs. The majority point is decided as
>64 VMs given the assumed 128 VM count for "extreme load".

Cc: Thomas Lendacky <Thomas.Lendacky@amd.com>
Cc: Paolo Bonzini <pbonzini@redhat.com>
Cc: Joerg Roedel <jroedel@suse.de>
Cc: Peter Gonda <pgonda@google.com>
Cc: Borislav Petkov <bp@alien8.de>
Cc: Sean Christopherson <seanjc@google.com>

Signed-off-by: Dionna Glaze <dionnaglaze@google.com>
---
 .../virt/kvm/x86/amd-memory-encryption.rst    | 23 +++++++++++++
 arch/x86/include/uapi/asm/kvm.h               |  7 ++++
 arch/x86/kvm/svm/sev.c                        | 33 +++++++++++++++++++
 arch/x86/kvm/svm/svm.h                        |  3 ++
 4 files changed, 66 insertions(+)

diff --git a/Documentation/virt/kvm/x86/amd-memory-encryption.rst b/Documentation/virt/kvm/x86/amd-memory-encryption.rst
index 1ddb6a86ce7f..1b5b4fc35aac 100644
--- a/Documentation/virt/kvm/x86/amd-memory-encryption.rst
+++ b/Documentation/virt/kvm/x86/amd-memory-encryption.rst
@@ -572,6 +572,29 @@ Returns: 0 on success, -negative on error
 See SNP_LAUNCH_FINISH in the SEV-SNP specification [snp-fw-abi]_ for further
 details on the input parameters in ``struct kvm_sev_snp_launch_finish``.
 
+21. KVM_SEV_SNP_SET_REQUEST_THROTTLE_RATE
+-----------------------------------------
+
+The KVM_SEV_SNP_SET_REQUEST_THROTTLE_RATE command is used to set a per-VM rate
+limit on responding to requests for AMD-SP to process a guest request.
+The AMD-SP is a global resource with limited capacity, so to avoid noisy
+neighbor effects, the host may set a request rate for guests.
+
+Parameters (in): struct kvm_sev_snp_set_request_throttle_rate
+
+Returns: 0 on success, -negative on error
+
+::
+
+	struct kvm_sev_snp_set_request_throttle_rate {
+		__u32 interval_ms;
+		__u32 burst;
+	};
+
+The interval will be translated into jiffies, so if it after transformation
+the interval is 0, the command will return ``-EINVAL``. The ``burst`` value
+must be greater than 0.
+
 Device attribute API
 ====================
 
diff --git a/arch/x86/include/uapi/asm/kvm.h b/arch/x86/include/uapi/asm/kvm.h
index 460306b35a4b..d92242d9b9af 100644
--- a/arch/x86/include/uapi/asm/kvm.h
+++ b/arch/x86/include/uapi/asm/kvm.h
@@ -708,6 +708,8 @@ enum sev_cmd_id {
 	KVM_SEV_SNP_LAUNCH_UPDATE,
 	KVM_SEV_SNP_LAUNCH_FINISH,
 
+	KVM_SEV_SNP_SET_REQUEST_THROTTLE_RATE,
+
 	KVM_SEV_NR_MAX,
 };
 
@@ -877,6 +879,11 @@ struct kvm_sev_snp_launch_finish {
 	__u64 pad1[4];
 };
 
+struct kvm_sev_snp_set_request_throttle_rate {
+	__u32 interval_ms;
+	__u32 burst;
+};
+
 #define KVM_X2APIC_API_USE_32BIT_IDS            (1ULL << 0)
 #define KVM_X2APIC_API_DISABLE_BROADCAST_QUIRK  (1ULL << 1)
 
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index a7a7dc507336..35b04a10ed73 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -12,12 +12,14 @@
 #include <linux/kvm_host.h>
 #include <linux/kernel.h>
 #include <linux/highmem.h>
+#include <linux/limits.h>
 #include <linux/psp.h>
 #include <linux/psp-sev.h>
 #include <linux/pagemap.h>
 #include <linux/swap.h>
 #include <linux/misc_cgroup.h>
 #include <linux/processor.h>
+#include <linux/ratelimit.h>
 #include <linux/trace_events.h>
 #include <uapi/linux/sev-guest.h>
 
@@ -2535,6 +2537,28 @@ static int snp_launch_finish(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	return ret;
 }
 
+static int snp_set_request_throttle_ms(struct kvm *kvm, struct kvm_sev_cmd *argp)
+{
+	struct kvm_sev_info *sev = to_kvm_sev_info(kvm);
+	struct kvm_sev_snp_set_request_throttle_rate params;
+	u64 jiffies;
+
+	if (!sev_snp_guest(kvm))
+		return -ENOTTY;
+
+	if (copy_from_user(&params, u64_to_user_ptr(argp->data), sizeof(params)))
+		return -EFAULT;
+
+	jiffies = ((u64)params.interval_ms * HZ) / 1000;
+
+	if (!jiffies || !params.burst || params.burst > S32_MAX || jiffies > S32_MAX)
+		return -EINVAL;
+
+	ratelimit_state_init(&sev->snp_guest_msg_rs, jiffies, params.burst);
+
+	return 0;
+}
+
 int sev_mem_enc_ioctl(struct kvm *kvm, void __user *argp)
 {
 	struct kvm_sev_cmd sev_cmd;
@@ -2640,6 +2664,9 @@ int sev_mem_enc_ioctl(struct kvm *kvm, void __user *argp)
 	case KVM_SEV_SNP_LAUNCH_FINISH:
 		r = snp_launch_finish(kvm, &sev_cmd);
 		break;
+	case KVM_SEV_SNP_SET_REQUEST_THROTTLE_RATE_MS:
+		r = snp_set_request_throttle_ms(kvm, &sev_cmd);
+		break;
 	default:
 		r = -EINVAL;
 		goto out;
@@ -4015,6 +4042,12 @@ static int snp_handle_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_
 
 	mutex_lock(&sev->guest_req_mutex);
 
+	if (!__ratelimit(&sev->snp_guest_msg_rs)) {
+		svm_vmgexit_no_action(svm, SNP_GUEST_ERR(SNP_GUEST_VMM_ERR_BUSY, 0));
+		ret = 1;
+		goto out_unlock;
+	}
+
 	if (kvm_read_guest(kvm, req_gpa, sev->guest_req_buf, PAGE_SIZE)) {
 		ret = -EIO;
 		goto out_unlock;
diff --git a/arch/x86/kvm/svm/svm.h b/arch/x86/kvm/svm/svm.h
index f16b068c4228..2643c940d054 100644
--- a/arch/x86/kvm/svm/svm.h
+++ b/arch/x86/kvm/svm/svm.h
@@ -18,6 +18,7 @@
 #include <linux/kvm_types.h>
 #include <linux/kvm_host.h>
 #include <linux/bits.h>
+#include <linux/ratelimit.h>
 
 #include <asm/svm.h>
 #include <asm/sev-common.h>
@@ -112,6 +113,8 @@ struct kvm_sev_info {
 	void *guest_req_buf;    /* Bounce buffer for SNP Guest Request input */
 	void *guest_resp_buf;   /* Bounce buffer for SNP Guest Request output */
 	struct mutex guest_req_mutex; /* Must acquire before using bounce buffers */
+
+	struct ratelimit_state snp_guest_msg_rs; /* Limit guest requests */
 };
 
 struct kvm_svm {

---

## [3] Dionna Glaze — 2025-05-15
*Subject: [PATCH v5 2/2] kvm: sev: If ccp is busy, report busy to guest*

The ccp driver can be overloaded even with guest request rate limits.
The return value of -EBUSY means that there is no firmware error to
report back to user space, so the guest VM would see this as
exitinfo2 = 0. The false success can trick the guest to update its
message sequence number when it shouldn't have.

Instead, when ccp returns -EBUSY, that is reported to userspace as the
throttling return value.

Cc: Thomas Lendacky <Thomas.Lendacky@amd.com>
Cc: Paolo Bonzini <pbonzini@redhat.com>
Cc: Joerg Roedel <jroedel@suse.de>
Cc: Peter Gonda <pgonda@google.com>
Cc: Borislav Petkov <bp@alien8.de>
Cc: Sean Christopherson <seanjc@google.com>

Signed-off-by: Dionna Glaze <dionnaglaze@google.com>
---
 arch/x86/kvm/svm/sev.c | 5 +++++
 1 file changed, 5 insertions(+)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 35b04a10ed73..884ab3f54fca 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -4063,6 +4063,11 @@ static int snp_handle_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_
 	 * the PSP is dead and commands are timing out.
 	 */
 	ret = sev_issue_cmd(kvm, SEV_CMD_SNP_GUEST_REQUEST, &data, &fw_err);
+	if (ret == -EBUSY) {
+		svm_vmgexit_no_action(svm, SNP_GUEST_ERR(SNP_GUEST_VMM_ERR_BUSY, fw_err));
+		ret = 1;
+		goto out_unlock;
+	}
 	if (ret && !fw_err)
 		goto out_unlock;

---

## [4] Sean Christopherson — 2025-05-15
*Subject: Re: [PATCH v5 1/2] kvm: sev: Add SEV-SNP guest request throttling*

On Thu, May 15, 2025, Dionna Glaze wrote:
> The AMD-SP is a precious resource that doesn't have a scheduler other
> than a mutex lock queue. To avoid customers from causing a DoS, a

Who is we?

> anticipate more concurrency than that for a seldom used request for
> a majority well-behaved set of VMs. The majority point is decided as

I assume this is a limitation of the __ratelimit() interface?

> +the interval is 0, the command will return ``-EINVAL``. The ``burst`` value
> +must be greater than 0.

Ugh, whose terribly idea was a per-VM capability?  Oh, mine[*].  *sigh*

Looking at this again, a per-VM capability doesn't change anything.  In fact,
it's far, far worse.  At least with a module param there's guaranteed to be some
amount of ratelimiting.  Relying on the VMM to opt-in to ratelimiting its VM if
userspace is compromised is completely nonsensical.

Unless someone has a better idea, let's just go with a module param.  

[*] https://lore.kernel.org/all/Y8rEFpbMV58yJIKy@google.com

> @@ -4015,6 +4042,12 @@ static int snp_handle_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_
>  

Can you (or anyone) explain what a well-behaved guest will do in in response to
BUSY?  And/or explain why KVM injecting an error into the guest is better than
exiting to userspace.

---

## [5] Dionna Amalie Glaze — 2025-05-15
*Subject: Re: [PATCH v5 1/2] kvm: sev: Add SEV-SNP guest request throttling*

On Thu, May 15, 2025 at 3:40 PM Sean Christopherson <seanjc@google.com> wrote:
>
> On Thu, May 15, 2025, Dionna Glaze wrote:

It is.
>
> > +the interval is 0, the command will return ``-EINVAL``. The ``burst`` value

Thanks for that. Do you want the module param to be in units of KHZ (1
interval / x milliseconds),
and treat 0 as unlimited?

The original burst value of 2 is due to an oddity of an older version
of the kernel that would ratelimit
before handling the certificate buffer length negotiation, so we could
simply have a single module
parameter and set the burst rate to 1 unconditionally.

I'd generally prefer this to go in after Michael Roth's patch that
adds the extended guest request support.

>
> [*] https://lore.kernel.org/all/Y8rEFpbMV58yJIKy@google.com

---

## [6] Dionna Amalie Glaze — 2025-05-16
*Subject: Re: [PATCH v5 1/2] kvm: sev: Add SEV-SNP guest request throttling*

> > @@ -4015,6 +4042,12 @@ static int snp_handle_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_
> >

Ah, I missed this question. The guest is meant to back off and try
again after waiting a bit.
This is the behavior added in
https://lore.kernel.org/all/20230214164638.1189804-2-dionnaglaze@google.com/

If KVM returns to userspace with an exit type that the guest request
was throttled, then
what is user space supposed to do with that? It could wait a bit
before trying KVM_RUN
again, but with the enlightened method, the guest could at least work
on other kernel
tasks while it waits for its turn to get an attestation report.

Perhaps this is me not understanding the preferred KVM way of doing things.

---

## [7] Sean Christopherson — 2025-05-21
*Subject: Re: [PATCH v5 1/2] kvm: sev: Add SEV-SNP guest request throttling*

On Fri, May 16, 2025, Dionna Amalie Glaze wrote:
> > > @@ -4015,6 +4042,12 @@ static int snp_handle_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_
> > >

Nice, it's already landed and considered legal VMM behavior.

> If KVM returns to userspace with an exit type that the guest request was
> throttled, then what is user space supposed to do with that?

The userspace exit doesn't have to notify userspace that the guest was throttled,
e.g. KVM could exit on _every_ request and let userspace do its own throttling.

I have no idea whether or not that's sane/useful, which is why I'm asking.  The
cover letter, changelog, and documentation are all painfully sparse with respect
to explaining why *this* uAPI is the right uAPI.

> It could wait a bit before trying KVM_RUN again, but with the enlightened
> method, the guest could at least work on other kernel tasks while it waits

Nothing prevents KVM from providing userspace a way to communicate VMM_ERR_BUSY,
e.g. as done for KVM_EXIT_SNP_REQ_CERTS:

https://lore.kernel.org/all/20250428195113.392303-2-michael.roth@amd.com

> Perhaps this is me not understanding the preferred KVM way of doing things.

The only real preference at play is to not end up with uAPI and ABI that doesn't
fit "everyone's" needs.  It's impossible to fully future-proof KVM's ABI, but we
can at least perform due diligence to ensure we didn't simply pick the the path
of least resistance.

The bar gets lowered a tiny bit if we go with a module param (which I think we
should do), but I'd still like an explanation of why a fairly simple ratelimiting
mechanism is the best overall approach.

---

## [8] Dionna Amalie Glaze — 2025-05-28
*Subject: Re: [PATCH v5 1/2] kvm: sev: Add SEV-SNP guest request throttling*

On Wed, May 21, 2025 at 11:19 AM Sean Christopherson <seanjc@google.com> wrote:
>
> On Fri, May 16, 2025, Dionna Amalie Glaze wrote:

Before I send out a revised patchset with changed commit text, what do
you think about the following

    The AMD-SP is a precious resource that doesn't have a scheduler other
    than a mutex lock queue. To avoid customers from causing a DoS, a
    kernel module parameter for rate limiting guest requests is added.
[Addition:]
    The kernel module parameter is a lower bound kernel-imposed rate limit
    for any SEV-SNP VM-initiated guest request. This does not preclude the
    addition of a new KVM exit type for SEV-SNP guest requests for
    userspace to impose any additional throttling logic. The default value of
    0 maintains the previous behavior that there is no imposed rate limit on
    guest requests.


We could still ask Michael to change KVM_EXIT_SNP_REQ_CERTS  to
KVM_EXIT_SNP_GUEST_REQ
and for the exit structure to include msg_type as well as the
gfn+npages when the kind is an extended request for an attestation
report so that we don't need to have two exit types.

Regardless of that change for additional throttling opportunities, I
think the system-wide imposed lower bound is important for quelling
noisy neighbors to some degree.

---
