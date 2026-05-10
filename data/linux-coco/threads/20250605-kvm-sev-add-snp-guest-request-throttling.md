---
title: 'kvm: sev: Add SNP guest request throttling'
date: 2025-06-05
last_reply: 2025-06-06
message_count: 6
participants: ['Dionna Glaze', 'Tom Lendacky', 'kernel test robot']
---

## [1] Dionna Glaze — 2025-06-05

The GHCB specification recommends that SNP guest requests should be
rate limited. Add a kernel module parameter to ensure a system-wide
lower bound rate limit on a per-VM scale for all new VMs. Note that
this does not preclude the addition of a new KVM exit type for SEV-SNP
guest requests for userspace to impose any additional throttling logic.

The AMD-SP is a global resource that must be shared across VMs, so
its time should be multiplexed across VMs fairly. It is the
responsibility of the VMM to ensure all SEV-SNP VMs have a rate limit
set such that the collective set of VMs on the machine have a rate of
access that does not exceed the device's capacity.

The sev-guest device already respects the SNP_GUEST_VMM_ERR_BUSY
result code, so utilize that result to cause the guest to retry after
waiting momentarily.

Changes since v5:
  * Reverted the KVM command for setting the rate limit in favor of
    the module parameter solution. The default is no rate-limiting
    to maintain existing behavior.
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

 arch/x86/kvm/svm/sev.c | 22 ++++++++++++++++++++++
 arch/x86/kvm/svm/svm.h |  3 +++
 2 files changed, 25 insertions(+)

---

## [2] Dionna Glaze — 2025-06-05
*Subject: [PATCH v6 1/2] kvm: sev: Add SEV-SNP guest request throttling*

The AMD-SP is a precious resource that doesn't have a scheduler other
than a mutex lock queue. To avoid customers from causing a DoS, a
kernel module parameter for rate limiting guest requests is added.

The default value does not impose any rate limiting.

Throttling vs scheduling:
Even though Linux kernel mutexes have fair scheduling, the SEV command
mutex is not enough to balance the AMD-SP load in a manner that favors
the host to run VM launches for low boot latency over traffic from the
guest in the form of guests requests that it can't predict.
Boot sequence commands and guest request commands all contend on
the same mutex, so boot latency is affected by increased guest request
contention.

A VM launch may see dozens of SNP_LAUNCH_UPDATE commands before
SNP_LAUNCH_FINISH, and boot times are a heavily protected metric in
hyperscalars.
To favor lower latency of VM launches over each VM's ability to request
attestations at a high rate, the guest requests need a secondary
scheduling mechanism.
It's not good practice to hold a lock and return to user space, so using
a secondary lock for VM launch sequences is not an appropriate solution.
For simplicity, merely set a rate limit for every VM's guest requests
and allow a system administrator to tune that rate limit to platform
needs.

Design decisions:
The throttle rate for a VM cannot be changed once it has been started.
The rate the VM gets is its level of service, so it should not be
degradable by a mem_enc_ioctl for example.

Empirical investigation:
With a test methodology of turning up N-1 "antagonist" VMs with 2 vCPUs
and 4GiB RAM that all request a SEV-SNP attestation a tight loop before
measuring the boot latency of the Nth VM, an effective quality of service
should keep the average boot latency at levels without any guest request
contention.

On a dedicated 256 core AMD Zen3 with 1TiB of RAM, continuous performance
testing shows that a boot latency of 220ms +- 50ms is typical with N in
{4, 16, 32, 64} when the request rate is set to 1/s.

After N=64, the rate limit of 1 HZ is insufficient to hold back enough
time for the final VM launch to succeed consistently in the contention.

Cc: Thomas Lendacky <Thomas.Lendacky@amd.com>
Cc: Paolo Bonzini <pbonzini@redhat.com>
Cc: Joerg Roedel <jroedel@suse.de>
Cc: Peter Gonda <pgonda@google.com>
Cc: Borislav Petkov <bp@alien8.de>
Cc: Sean Christopherson <seanjc@google.com>

Signed-off-by: Dionna Glaze <dionnaglaze@google.com>
---
 arch/x86/kvm/svm/sev.c | 17 +++++++++++++++++
 arch/x86/kvm/svm/svm.h |  3 +++
 2 files changed, 20 insertions(+)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 1aa0f07d3a63..e45f0cfae2bd 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -12,13 +12,16 @@
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
+#include <linux/units.h>
 #include <uapi/linux/sev-guest.h>
 
 #include <asm/pkru.h>
@@ -59,6 +62,10 @@ static bool sev_es_debug_swap_enabled = true;
 module_param_named(debug_swap, sev_es_debug_swap_enabled, bool, 0444);
 static u64 sev_supported_vmsa_features;
 
+/* set a per-VM rate limit for SEV-SNP guest requests on VM creation. 0 is unlimited. */
+static int sev_snp_request_ratelimit_khz = 0;
+module_param(sev_snp_request_ratelimit_khz, int, 0444);
+
 #define AP_RESET_HOLD_NONE		0
 #define AP_RESET_HOLD_NAE_EVENT		1
 #define AP_RESET_HOLD_MSR_PROTO		2
@@ -367,6 +374,7 @@ static int snp_guest_req_init(struct kvm *kvm)
 {
 	struct kvm_sev_info *sev = to_kvm_sev_info(kvm);
 	struct page *req_page;
+	u64 throttle_interval;
 
 	req_page = alloc_page(GFP_KERNEL_ACCOUNT | __GFP_ZERO);
 	if (!req_page)
@@ -381,6 +389,9 @@ static int snp_guest_req_init(struct kvm *kvm)
 	sev->guest_req_buf = page_address(req_page);
 	mutex_init(&sev->guest_req_mutex);
 
+	throttle_interval = ((u64)sev_snp_request_ratelimit_khz * HZ) / HZ_PER_KHZ;
+	ratelimit_state_init(&sev->snp_guest_msg_rs, sev_snp_request_ratelimit_khz, 1);
+
 	return 0;
 }
 
@@ -4028,6 +4039,12 @@ static int snp_handle_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_
 
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

## [3] Dionna Glaze — 2025-06-05
*Subject: [PATCH v6 2/2] kvm: sev: If ccp is busy, report busy to guest*

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
index e45f0cfae2bd..0ceb7e83a98d 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -4060,6 +4060,11 @@ static int snp_handle_guest_req(struct vcpu_svm *svm, gpa_t req_gpa, gpa_t resp_
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

## [4] Tom Lendacky — 2025-06-05
*Subject: Re: [PATCH v6 2/2] kvm: sev: If ccp is busy, report busy to guest*

On 6/5/25 10:02, Dionna Glaze wrote:
> The ccp driver can be overloaded even with guest request rate limits.
> The return value of -EBUSY means that there is no firmware error to

-EBUSY from the CCP driver is an error, not a throttling condition. Either
the driver has marked the ASP/PSP as dead or there are no command buffers
available, which is an error situation. There is no throttling support in
the CCP driver. A mutex is used to serialize requests, but all requests
proceed at some point. So there should not be a special check for -EBUSY.

Thanks,
Tom

> 
> Instead, when ccp returns -EBUSY, that is reported to userspace as the

---

## [5] Dionna Amalie Glaze — 2025-06-05
*Subject: Re: [PATCH v6 2/2] kvm: sev: If ccp is busy, report busy to guest*

On Thu, Jun 5, 2025 at 12:15 PM Tom Lendacky <thomas.lendacky@amd.com> wrote:
>
> On 6/5/25 10:02, Dionna Glaze wrote:

Ah, okay thanks Tom. I'll drop it for v6. I'll see how the first patch
is received before cutting a new email.

---

## [6] kernel test robot — 2025-06-06
*Subject: Re: [PATCH v6 1/2] kvm: sev: Add SEV-SNP guest request throttling*

Hi Dionna,

kernel test robot noticed the following build warnings:

[auto build test WARNING on mst-vhost/linux-next]
[also build test WARNING on linus/master v6.15 next-20250606]
[cannot apply to kvm/queue kvm/next kvm/linux-next]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Dionna-Glaze/kvm-sev-Add-SEV-SNP-guest-request-throttling/20250605-230536
base:   https://git.kernel.org/pub/scm/linux/kernel/git/mst/vhost.git linux-next
patch link:    https://lore.kernel.org/r/20250605150236.3775954-2-dionnaglaze%40google.com
patch subject: [PATCH v6 1/2] kvm: sev: Add SEV-SNP guest request throttling
config: x86_64-rhel-9.4-rust (https://download.01.org/0day-ci/archive/20250606/202506061922.q7OljdiN-lkp@intel.com/config)
compiler: clang version 18.1.8 (https://github.com/llvm/llvm-project 3b5b5c1ec4a3095ab096dd780e84d7ab81f3d7ff)
rustc: rustc 1.78.0 (9b00956e5 2024-04-29)
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20250606/202506061922.q7OljdiN-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202506061922.q7OljdiN-lkp@intel.com/

All warnings (new ones prefixed by >>):

>> arch/x86/kvm/svm/sev.c:376:6: warning: variable 'throttle_interval' set but not used [-Wunused-but-set-variable]
     376 |         u64 throttle_interval;
         |             ^
   1 warning generated.


vim +/throttle_interval +376 arch/x86/kvm/svm/sev.c

   334	
   335	/*
   336	 * This sets up bounce buffers/firmware pages to handle SNP Guest Request
   337	 * messages (e.g. attestation requests). See "SNP Guest Request" in the GHCB
   338	 * 2.0 specification for more details.
   339	 *
   340	 * Technically, when an SNP Guest Request is issued, the guest will provide its
   341	 * own request/response pages, which could in theory be passed along directly
   342	 * to firmware rather than using bounce pages. However, these pages would need
   343	 * special care:
   344	 *
   345	 *   - Both pages are from shared guest memory, so they need to be protected
   346	 *     from migration/etc. occurring while firmware reads/writes to them. At a
   347	 *     minimum, this requires elevating the ref counts and potentially needing
   348	 *     an explicit pinning of the memory. This places additional restrictions
   349	 *     on what type of memory backends userspace can use for shared guest
   350	 *     memory since there is some reliance on using refcounted pages.
   351	 *
   352	 *   - The response page needs to be switched to Firmware-owned[1] state
   353	 *     before the firmware can write to it, which can lead to potential
   354	 *     host RMP #PFs if the guest is misbehaved and hands the host a
   355	 *     guest page that KVM might write to for other reasons (e.g. virtio
   356	 *     buffers/etc.).
   357	 *
   358	 * Both of these issues can be avoided completely by using separately-allocated
   359	 * bounce pages for both the request/response pages and passing those to
   360	 * firmware instead. So that's what is being set up here.
   361	 *
   362	 * Guest requests rely on message sequence numbers to ensure requests are
   363	 * issued to firmware in the order the guest issues them, so concurrent guest
   364	 * requests generally shouldn't happen. But a misbehaved guest could issue
   365	 * concurrent guest requests in theory, so a mutex is used to serialize
   366	 * access to the bounce buffers.
   367	 *
   368	 * [1] See the "Page States" section of the SEV-SNP Firmware ABI for more
   369	 *     details on Firmware-owned pages, along with "RMP and VMPL Access Checks"
   370	 *     in the APM for details on the related RMP restrictions.
   371	 */
   372	static int snp_guest_req_init(struct kvm *kvm)
   373	{
   374		struct kvm_sev_info *sev = to_kvm_sev_info(kvm);
   375		struct page *req_page;
 > 376		u64 throttle_interval;
   377	
   378		req_page = alloc_page(GFP_KERNEL_ACCOUNT | __GFP_ZERO);
   379		if (!req_page)
   380			return -ENOMEM;
   381	
   382		sev->guest_resp_buf = snp_alloc_firmware_page(GFP_KERNEL_ACCOUNT | __GFP_ZERO);
   383		if (!sev->guest_resp_buf) {
   384			__free_page(req_page);
   385			return -EIO;
   386		}
   387	
   388		sev->guest_req_buf = page_address(req_page);
   389		mutex_init(&sev->guest_req_mutex);
   390	
   391		throttle_interval = ((u64)sev_snp_request_ratelimit_khz * HZ) / HZ_PER_KHZ;
   392		ratelimit_state_init(&sev->snp_guest_msg_rs, sev_snp_request_ratelimit_khz, 1);
   393	
   394		return 0;
   395	}
   396

---
