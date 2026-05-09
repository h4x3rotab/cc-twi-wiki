---
title: 'kvm: sev: Add SNP guest request throttling'
date: 2025-05-14
last_reply: 2025-05-16
message_count: 7
participants: ['Dionna Glaze', 'kernel test robot']
---

## [1] Dionna Glaze — 2025-05-14

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

 .../virt/kvm/x86/amd-memory-encryption.rst    | 23 ++++++++++++
 arch/x86/include/uapi/asm/kvm.h               |  7 ++++
 arch/x86/kvm/svm/sev.c                        | 36 +++++++++++++++++++
 arch/x86/kvm/svm/svm.h                        |  2 ++
 4 files changed, 68 insertions(+)

---

## [2] Dionna Glaze — 2025-05-14
*Subject: [PATCH v4 1/2] kvm: sev: Add SEV-SNP guest request throttling*

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
 .../virt/kvm/x86/amd-memory-encryption.rst    | 23 ++++++++++++++
 arch/x86/include/uapi/asm/kvm.h               |  7 +++++
 arch/x86/kvm/svm/sev.c                        | 31 +++++++++++++++++++
 arch/x86/kvm/svm/svm.h                        |  2 ++
 4 files changed, 63 insertions(+)

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
index a7a7dc507336..febf4b45fddf 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2535,6 +2535,29 @@ static int snp_launch_finish(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	return ret;
 }
 
+static int snp_set_request_throttle_ms(struct kvm *kvm, struct kvm_sev_cmd *argp)
+{
+	struct kvm_sev_info *sev = to_kvm_sev_info(kvm);
+	struct kvm_sev_snp_set_request_throttle_rate params;
+	int ret;
+	u64 jiffies;
+
+	if (!sev_snp_guest(kvm))
+		return -ENOTTY;
+
+	if (copy_from_user(&params, u64_to_user_ptr(argp->data), sizeof(params)))
+		return -EFAULT;
+
+	jiffies = (params.interval_ms * HZ) / 1000;
+
+	if (!jiffies || !params.burst)
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
@@ -2640,6 +2663,9 @@ int sev_mem_enc_ioctl(struct kvm *kvm, void __user *argp)
 	case KVM_SEV_SNP_LAUNCH_FINISH:
 		r = snp_launch_finish(kvm, &sev_cmd);
 		break;
+	case KVM_SEV_SNP_SET_REQUEST_THROTTLE_RATE_MS:
+		r = snp_set_request_throttle_ms(kvm, &sev_cmd);
+		break;
 	default:
 		r = -EINVAL;
 		goto out;
@@ -4015,6 +4041,11 @@ static int snp_handle_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_
 
 	mutex_lock(&sev->guest_req_mutex);
 
+	if (!__ratelimit(&sev->snp_guest_msg_rs)) {
+		rc = SNP_GUEST_VMM_ERR_BUSY;
+		goto out_unlock;
+	}
+
 	if (kvm_read_guest(kvm, req_gpa, sev->guest_req_buf, PAGE_SIZE)) {
 		ret = -EIO;
 		goto out_unlock;
diff --git a/arch/x86/kvm/svm/svm.h b/arch/x86/kvm/svm/svm.h
index f16b068c4228..0a7c8d3a7560 100644
--- a/arch/x86/kvm/svm/svm.h
+++ b/arch/x86/kvm/svm/svm.h
@@ -112,6 +112,8 @@ struct kvm_sev_info {
 	void *guest_req_buf;    /* Bounce buffer for SNP Guest Request input */
 	void *guest_resp_buf;   /* Bounce buffer for SNP Guest Request output */
 	struct mutex guest_req_mutex; /* Must acquire before using bounce buffers */
+
+	struct ratelimit_state snp_guest_msg_rs; /* Limit guest requests */
 };
 
 struct kvm_svm {

---

## [3] Dionna Glaze — 2025-05-14
*Subject: [PATCH v4 2/2] kvm: sev: If ccp is busy, report busy to guest*

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
index febf4b45fddf..c1bd82c26a11 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -4061,6 +4061,11 @@ static int snp_handle_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_
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

## [4] Dionna Glaze — 2025-05-14
*Subject: [PATCH v4 2/2] The ccp driver can be overloaded even with guest
 request rate limits. The return value of -EBUSY means that there is no
 firmware error to report back to user space, so the guest VM would see this
 as exitinfo2 = 0. The false success can trick the guest to update its message
 sequence number when it shouldn't have.*

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
index ddbfdce9dc18..5901a7f59f88 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -4065,6 +4065,11 @@ static int snp_handle_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_
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

## [5] Dionna Amalie Glaze — 2025-05-14
*Subject: Re: [PATCH v4 2/2] The ccp driver can be overloaded even with guest
 request rate limits. The return value of -EBUSY means that there is no
 firmware error to report back to user space, so the guest VM would see this
 as exitinfo2 = 0. The false success can trick the guest to update its message
 sequence number when it shouldn't have.*

On Wed, May 14, 2025 at 11:42 AM Dionna Glaze <dionnaglaze@google.com> wrote:
>
> Instead, when ccp returns -EBUSY, that is reported to userspace as the

Ah, disregard this email. Globbed one too many patch files.

---

## [6] Dionna Amalie Glaze — 2025-05-14
*Subject: Re: [PATCH v4 1/2] kvm: sev: Add SEV-SNP guest request throttling*

On Wed, May 14, 2025 at 11:41 AM Dionna Glaze <dionnaglaze@google.com> wrote:
>
> The AMD-SP is a precious resource that doesn't have a scheduler other

embarrassing. My build totally skipped this error. Disregard as well.

> +               goto out_unlock;
> +       }

---

## [7] kernel test robot — 2025-05-16
*Subject: Re: [PATCH v4 1/2] kvm: sev: Add SEV-SNP guest request throttling*

Hi Dionna,

kernel test robot noticed the following build errors:

[auto build test ERROR on kvm/queue]
[also build test ERROR on kvm/next mst-vhost/linux-next linus/master v6.15-rc6 next-20250515]
[cannot apply to kvm/linux-next]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Dionna-Glaze/kvm-sev-Add-SEV-SNP-guest-request-throttling/20250515-064452
base:   https://git.kernel.org/pub/scm/virt/kvm/kvm.git queue
patch link:    https://lore.kernel.org/r/20250514184136.238446-2-dionnaglaze%40google.com
patch subject: [PATCH v4 1/2] kvm: sev: Add SEV-SNP guest request throttling
config: x86_64-rhel-9.4 (https://download.01.org/0day-ci/archive/20250516/202505160203.9PdDhrOM-lkp@intel.com/config)
compiler: gcc-12 (Debian 12.2.0-14) 12.2.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20250516/202505160203.9PdDhrOM-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202505160203.9PdDhrOM-lkp@intel.com/

All errors (new ones prefixed by >>):

   arch/x86/kvm/svm/sev.c: In function 'snp_set_request_throttle_ms':
   arch/x86/kvm/svm/sev.c:2542:13: warning: unused variable 'ret' [-Wunused-variable]
    2542 |         int ret;
         |             ^~~
   arch/x86/kvm/svm/sev.c: In function 'sev_mem_enc_ioctl':
>> arch/x86/kvm/svm/sev.c:2666:14: error: 'KVM_SEV_SNP_SET_REQUEST_THROTTLE_RATE_MS' undeclared (first use in this function); did you mean 'KVM_SEV_SNP_SET_REQUEST_THROTTLE_RATE'?
    2666 |         case KVM_SEV_SNP_SET_REQUEST_THROTTLE_RATE_MS:
         |              ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
         |              KVM_SEV_SNP_SET_REQUEST_THROTTLE_RATE
   arch/x86/kvm/svm/sev.c:2666:14: note: each undeclared identifier is reported only once for each function it appears in
   arch/x86/kvm/svm/sev.c: In function 'snp_handle_guest_req':
>> arch/x86/kvm/svm/sev.c:4039:17: error: 'rc' undeclared (first use in this function); did you mean 'rq'?
    4039 |                 rc = SNP_GUEST_VMM_ERR_BUSY;
         |                 ^~
         |                 rq


vim +2666 arch/x86/kvm/svm/sev.c

  2537	
  2538	static int snp_set_request_throttle_ms(struct kvm *kvm, struct kvm_sev_cmd *argp)
  2539	{
  2540		struct kvm_sev_info *sev = to_kvm_sev_info(kvm);
  2541		struct kvm_sev_snp_set_request_throttle_rate params;
> 2542		int ret;
  2543		u64 jiffies;
  2544	
  2545		if (!sev_snp_guest(kvm))
  2546			return -ENOTTY;
  2547	
  2548		if (copy_from_user(&params, u64_to_user_ptr(argp->data), sizeof(params)))
  2549			return -EFAULT;
  2550	
  2551		jiffies = (params.interval_ms * HZ) / 1000;
  2552	
  2553		if (!jiffies || !params.burst)
  2554			return -EINVAL;
  2555	
  2556		ratelimit_state_init(&sev->snp_guest_msg_rs, jiffies, params.burst);
  2557	
  2558		return 0;
  2559	}
  2560	
  2561	int sev_mem_enc_ioctl(struct kvm *kvm, void __user *argp)
  2562	{
  2563		struct kvm_sev_cmd sev_cmd;
  2564		int r;
  2565	
  2566		if (!sev_enabled)
  2567			return -ENOTTY;
  2568	
  2569		if (!argp)
  2570			return 0;
  2571	
  2572		if (copy_from_user(&sev_cmd, argp, sizeof(struct kvm_sev_cmd)))
  2573			return -EFAULT;
  2574	
  2575		mutex_lock(&kvm->lock);
  2576	
  2577		/* Only the enc_context_owner handles some memory enc operations. */
  2578		if (is_mirroring_enc_context(kvm) &&
  2579		    !is_cmd_allowed_from_mirror(sev_cmd.id)) {
  2580			r = -EINVAL;
  2581			goto out;
  2582		}
  2583	
  2584		/*
  2585		 * Once KVM_SEV_INIT2 initializes a KVM instance as an SNP guest, only
  2586		 * allow the use of SNP-specific commands.
  2587		 */
  2588		if (sev_snp_guest(kvm) && sev_cmd.id < KVM_SEV_SNP_LAUNCH_START) {
  2589			r = -EPERM;
  2590			goto out;
  2591		}
  2592	
  2593		switch (sev_cmd.id) {
  2594		case KVM_SEV_ES_INIT:
  2595			if (!sev_es_enabled) {
  2596				r = -ENOTTY;
  2597				goto out;
  2598			}
  2599			fallthrough;
  2600		case KVM_SEV_INIT:
  2601			r = sev_guest_init(kvm, &sev_cmd);
  2602			break;
  2603		case KVM_SEV_INIT2:
  2604			r = sev_guest_init2(kvm, &sev_cmd);
  2605			break;
  2606		case KVM_SEV_LAUNCH_START:
  2607			r = sev_launch_start(kvm, &sev_cmd);
  2608			break;
  2609		case KVM_SEV_LAUNCH_UPDATE_DATA:
  2610			r = sev_launch_update_data(kvm, &sev_cmd);
  2611			break;
  2612		case KVM_SEV_LAUNCH_UPDATE_VMSA:
  2613			r = sev_launch_update_vmsa(kvm, &sev_cmd);
  2614			break;
  2615		case KVM_SEV_LAUNCH_MEASURE:
  2616			r = sev_launch_measure(kvm, &sev_cmd);
  2617			break;
  2618		case KVM_SEV_LAUNCH_FINISH:
  2619			r = sev_launch_finish(kvm, &sev_cmd);
  2620			break;
  2621		case KVM_SEV_GUEST_STATUS:
  2622			r = sev_guest_status(kvm, &sev_cmd);
  2623			break;
  2624		case KVM_SEV_DBG_DECRYPT:
  2625			r = sev_dbg_crypt(kvm, &sev_cmd, true);
  2626			break;
  2627		case KVM_SEV_DBG_ENCRYPT:
  2628			r = sev_dbg_crypt(kvm, &sev_cmd, false);
  2629			break;
  2630		case KVM_SEV_LAUNCH_SECRET:
  2631			r = sev_launch_secret(kvm, &sev_cmd);
  2632			break;
  2633		case KVM_SEV_GET_ATTESTATION_REPORT:
  2634			r = sev_get_attestation_report(kvm, &sev_cmd);
  2635			break;
  2636		case KVM_SEV_SEND_START:
  2637			r = sev_send_start(kvm, &sev_cmd);
  2638			break;
  2639		case KVM_SEV_SEND_UPDATE_DATA:
  2640			r = sev_send_update_data(kvm, &sev_cmd);
  2641			break;
  2642		case KVM_SEV_SEND_FINISH:
  2643			r = sev_send_finish(kvm, &sev_cmd);
  2644			break;
  2645		case KVM_SEV_SEND_CANCEL:
  2646			r = sev_send_cancel(kvm, &sev_cmd);
  2647			break;
  2648		case KVM_SEV_RECEIVE_START:
  2649			r = sev_receive_start(kvm, &sev_cmd);
  2650			break;
  2651		case KVM_SEV_RECEIVE_UPDATE_DATA:
  2652			r = sev_receive_update_data(kvm, &sev_cmd);
  2653			break;
  2654		case KVM_SEV_RECEIVE_FINISH:
  2655			r = sev_receive_finish(kvm, &sev_cmd);
  2656			break;
  2657		case KVM_SEV_SNP_LAUNCH_START:
  2658			r = snp_launch_start(kvm, &sev_cmd);
  2659			break;
  2660		case KVM_SEV_SNP_LAUNCH_UPDATE:
  2661			r = snp_launch_update(kvm, &sev_cmd);
  2662			break;
  2663		case KVM_SEV_SNP_LAUNCH_FINISH:
  2664			r = snp_launch_finish(kvm, &sev_cmd);
  2665			break;
> 2666		case KVM_SEV_SNP_SET_REQUEST_THROTTLE_RATE_MS:
  2667			r = snp_set_request_throttle_ms(kvm, &sev_cmd);
  2668			break;
  2669		default:
  2670			r = -EINVAL;
  2671			goto out;
  2672		}
  2673	
  2674		if (copy_to_user(argp, &sev_cmd, sizeof(struct kvm_sev_cmd)))
  2675			r = -EFAULT;
  2676	
  2677	out:
  2678		mutex_unlock(&kvm->lock);
  2679		return r;
  2680	}
  2681

---
