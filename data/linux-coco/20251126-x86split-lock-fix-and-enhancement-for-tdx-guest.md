---
title: 'x86/split_lock: Fix and enhancement for TDX guest'
date: 2025-11-26
last_reply: 2025-12-17
message_count: 12
participants: ['Xiaoyao Li', 'Kiryl Shutsemau', 'Andrew Cooper']
---

## [1] Xiaoyao Li — 2025-11-26

Running a split lock test[1] inside a TDX guest under KVM triggers the
warning below. The test hangs but can be terminated.

  x86/split lock detection: #AC: split_lock/1176 took a split_lock trap at address: 0x5630b30921f9
  unchecked MSR access error: WRMSR to 0x33 (tried to write 0x0000000000000000) at rIP: 0xffffffff812a061f (native_write_msr+0xf/0x30)
  Call Trace:
  handle_user_split_lock
  exc_alignment_check
  asm_exc_alignment_check

It turns out that split lock detection is enabled (by the host) when the
TDX vCPU is running, and #AC is not intercepted but delivered directly to
the TDX guest. The default "warning" mode of split lock #AC handler in
the guest tries to handle the split lock by temporarily disabling
detection. However, the MSR that disables detection is not accessible to
a guest.

Patch 1 forces the TDX guest to always treat the split lock #AC as the
"fatal" mode. This prevents the TDX guest from attempting invalid MSR
writes.

Patch 2 enhances the sld_state_show() to indicate that the TDX guest can
receive #AC on split locks depending on the host's split lock detection
configuration.

Note that all the split lock issues on TDX guests are due to the
non-architectural behavior of TDX: a TDX guest can receive #AC even
though the split lock detection feature is not available and the
relevant MSR is not accessible.

One option is to make the behavior architectural for TDX guests by not
delivering the (unexpected) #AC to the TDX guest and letting the host
handle it instead. This is exactly how KVM handles split lock #AC for
normal VMs. This option also has the advantage that the TDX guest can
survive from split locks when the host mode is not fatal.

However, this option cannot replace current patches because it changes
the behavior of current TDX and would need to be opted-in by the host VMM
for compatibility. More importantly, it would be a new feature available
only in newer TDX modules, which means all existing TDX modules
cannot benefit from it.

We list the option here as an open to solicit feedback and determine
whether to pursue adding such feature to TDX module.

[1] https://github.com/xiaoyaoli-intel/splitlock/blob/main/splitlock.c

Xiaoyao Li (2):
  x86/split_lock: Don't try to handle user split lock in TDX guest
  x86/split_lock: Describe #AC handling in TDX guest kernel log

 arch/x86/kernel/cpu/bus_lock.c | 20 +++++++++++++++++++-
 1 file changed, 19 insertions(+), 1 deletion(-)


base-commit: ac3fd01e4c1efce8f2c054cdeb2ddd2fc0fb150d

---

## [2] Xiaoyao Li — 2025-11-26
*Subject: [PATCH 1/2] x86/split_lock: Don't try to handle user split lock in TDX guest*

When the host enables split lock detection feature, the split lock from
guests (normal or TDX) triggers #AC. The #AC caused by split lock access
within a normal guest triggers a VM Exit and is handled in the host.
The #AC caused by split lock access within a TDX guest does not trigger
a VM Exit and instead it's delivered to the guest self.

The default "warning" mode of handling split lock depends on being able
to temporarily disable detection to recover from the split lock event.
But the MSR that disables detection is not accessible to a guest.

This means that TDX guests today can not disable the feature or use
the "warning" mode (which is the default). But, they can use the "fatal"
mode.

Force TDX guests to use the "fatal" mode.

Signed-off-by: Xiaoyao Li <xiaoyao.li@intel.com>
---
 arch/x86/kernel/cpu/bus_lock.c | 17 ++++++++++++++++-
 1 file changed, 16 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kernel/cpu/bus_lock.c b/arch/x86/kernel/cpu/bus_lock.c
index 981f8b1f0792..f278e4ea3dd4 100644
--- a/arch/x86/kernel/cpu/bus_lock.c
+++ b/arch/x86/kernel/cpu/bus_lock.c
@@ -315,9 +315,24 @@ void bus_lock_init(void)
 	wrmsrq(MSR_IA32_DEBUGCTLMSR, val);
 }
 
+static bool split_lock_fatal(void)
+{
+	if (sld_state == sld_fatal)
+		return true;
+
+	/*
+	 * TDX guests can not disable split lock detection.
+	 * Force them into the fatal behavior.
+	 */
+	if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST))
+		return true;
+
+	return false;
+}
+
 bool handle_user_split_lock(struct pt_regs *regs, long error_code)
 {
-	if ((regs->flags & X86_EFLAGS_AC) || sld_state == sld_fatal)
+	if ((regs->flags & X86_EFLAGS_AC) || split_lock_fatal())
 		return false;
 	split_lock_warn(regs->ip);
 	return true;

---

## [3] Xiaoyao Li — 2025-11-26
*Subject: [PATCH 2/2] x86/split_lock: Describe #AC handling in TDX guest kernel log*

X86_FEATURE_HYPERVISOR and X86_FEATURE_BUS_LOCK_DETECT are always
enumerated in a TDX guest because the corresponding CPUID values are
fixed to 1 by the TDX module. Similar to a normal guest, a TDX guest
never enumerates X86_FEATURE_SPLIT_LOCK_DETECT.

When "split_lock_detect=off", the TDX guest kernel log shows:

  x86/split lock detection: disabled

and with other settings, it shows:

  x86/split lock detection: #DB: ...

However, if the host enables split lock detection, a TDX guest receives
 #AC regardless of its own "split_lock_detect" configuration. The actual
behavior does not match what the kernel log claims.

Call out the possible #AC behavior on TDX and highlight that this behavior
depends on the host's enabling of split lock detection.

Signed-off-by: Xiaoyao Li <xiaoyao.li@intel.com>
---
 arch/x86/kernel/cpu/bus_lock.c | 3 +++
 1 file changed, 3 insertions(+)

diff --git a/arch/x86/kernel/cpu/bus_lock.c b/arch/x86/kernel/cpu/bus_lock.c
index f278e4ea3dd4..18695214d214 100644
--- a/arch/x86/kernel/cpu/bus_lock.c
+++ b/arch/x86/kernel/cpu/bus_lock.c
@@ -437,6 +437,9 @@ static void sld_state_show(void)
 			pr_info("#DB: setting system wide bus lock rate limit to %u/sec\n", bld_ratelimit.burst);
 		break;
 	}
+
+	if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST))
+		pr_info("tdx: #AC depends on host configuration: crashing the kernel on kernel split_locks and sending SIGBUS on user-space split_locks\n");
 }
 
 void __init sld_setup(struct cpuinfo_x86 *c)

---

## [4] Kiryl Shutsemau — 2025-11-26
*Subject: Re: [PATCH 1/2] x86/split_lock: Don't try to handle user split lock
 in TDX guest*

On Wed, Nov 26, 2025 at 06:02:03PM +0800, Xiaoyao Li wrote:
> When the host enables split lock detection feature, the split lock from
> guests (normal or TDX) triggers #AC. The #AC caused by split lock access

Maybe it would be cleaner to make it conditional on
cpu_model_supports_sld instead of special-casing TDX guest?

#AC on any platfrom when we didn't asked for it suppose to be fatal, no?

>  	split_lock_warn(regs->ip);
>  	return true;

---

## [5] Xiaoyao Li — 2025-11-26
*Subject: Re: [PATCH 1/2] x86/split_lock: Don't try to handle user split lock
 in TDX guest*

On 11/26/2025 7:25 PM, Kiryl Shutsemau wrote:
> On Wed, Nov 26, 2025 at 06:02:03PM +0800, Xiaoyao Li wrote:
>> When the host enables split lock detection feature, the split lock from

But TDX is the only one has such special non-architectural behavior.

For example, for normal VMs under KVM, the behavior is x86 
architectural. MSR_TEST_CTRL is not accessible to normal VMs, and no 
split lock #AC will be delivered to the normal VMs because it's handled 
by KVM.

>>   	split_lock_warn(regs->ip);
>>   	return true;

---

## [6] Kiryl Shutsemau — 2025-11-26
*Subject: Re: [PATCH 1/2] x86/split_lock: Don't try to handle user split lock
 in TDX guest*

On Wed, Nov 26, 2025 at 08:17:18PM +0800, Xiaoyao Li wrote:
> On 11/26/2025 7:25 PM, Kiryl Shutsemau wrote:
> > On Wed, Nov 26, 2025 at 06:02:03PM +0800, Xiaoyao Li wrote:

How does it contradict what I suggested?

For both normal VMs and TDX guest, cpu_model_supports_sld will not be
set to true. So check for cpu_model_supports_sld here is going to be
NOP, unless #AC actually delivered, like we have in TDX case. Handling
it as fatal is sane behaviour in such case regardless if it TDX.

And we don't need to make the check explicitly about TDX guest.

---

## [7] Xiaoyao Li — 2025-11-27
*Subject: Re: [PATCH 1/2] x86/split_lock: Don't try to handle user split lock
 in TDX guest*

On 11/26/2025 9:35 PM, Kiryl Shutsemau wrote:
> On Wed, Nov 26, 2025 at 08:17:18PM +0800, Xiaoyao Li wrote:
>> On 11/26/2025 7:25 PM, Kiryl Shutsemau wrote:

Well, it depends on how defensive we would like to be, and whether to 
specialize or commonize the issue.

Either can work. If the preference and agreement are to commonize the 
issue, I can do it in v2. And in this direction, what should we do with 
the patch 2? just drop it since it's specialized for TDX ?

---

## [8] Kiryl Shutsemau — 2025-11-27
*Subject: Re: [PATCH 1/2] x86/split_lock: Don't try to handle user split lock
 in TDX guest*

On Thu, Nov 27, 2025 at 10:00:58AM +0800, Xiaoyao Li wrote:
> On 11/26/2025 9:35 PM, Kiryl Shutsemau wrote:
> > On Wed, Nov 26, 2025 at 08:17:18PM +0800, Xiaoyao Li wrote:

I am not sure. Leaving it as produces produces false messages which is
not good, but not critical.

Maybe just clear X86_FEATURE_BUS_LOCK_DETECT and stop pretending we
control split-lock behaviour from the guest?

---

## [9] Andrew Cooper — 2025-11-27
*Subject: Re: [PATCH 1/2] x86/split_lock: Don't try to handle user split lock
 in TDX guest*

> I am not sure. Leaving it as produces produces false messages which is
> not good, but not critical.

(Having just played with this mess for another task) you're talking
about two different things.

Sapphire Rapids has an architectural BUS_LOCK_DETECT (trap semantics,
#DB or VMExit), and a model-specific BUS_LOCK_DISABLE.

It's BUS_LOCK_DISABLE which generates #AC, with fault semantics,
preventing forward progress.  It also means the Bus Lock didn't happen,
and there's nothing to trigger the BUS_LOCK_DETECT (trap) behaviour.

Given that TDX is enabling BUS_LOCK_DISABLE, it's probably also enabling
UC_LOCK_DISABLE (causes #GP) too.

Looking at the backtrace:

  x86/split lock detection: #AC: split_lock/1176 took a split_lock trap at address: 0x5630b30921f9
  unchecked MSR access error: WRMSR to 0x33 (tried to write 0x0000000000000000) at rIP: 0xffffffff812a061f (native_write_msr+0xf/0x30)


First, "took a split_lock trap" is wrong.  It's a fault, not a trap.

Second, because the attempt to disable BUS_LOCK_DISABLE was blocked,
simply retrying the instruction will generate a new #AC and livelock. 
Linux probably ought to raise SIGSEGV with userspace, for want of
anything better to do.

It looks like software in a TDX VM will simply have to accept that it
cannot cause a bus lock.

~Andrew

---

## [10] Xiaoyao Li — 2025-11-28
*Subject: Re: [PATCH 1/2] x86/split_lock: Don't try to handle user split lock
 in TDX guest*

On 11/28/2025 12:16 AM, Kiryl Shutsemau wrote:
> On Thu, Nov 27, 2025 at 10:00:58AM +0800, Xiaoyao Li wrote:
>> On 11/26/2025 9:35 PM, Kiryl Shutsemau wrote:

By clearing X86_FEATURE_BUS_LOCK_DETECT, the TDX guest log doens't print 
anything about split lock detection. But the TDX guest is still possible 
to get #AC on split locks, which seems no good as well.

More, it's overkill to clear X86_FEATURE_BUS_LOCK_DETECT. Clearing it 
means TDX guest cannot use X86_FEATURE_BUS_LOCK_DETECT to detect the bus 
lock happens from the guest userspace, even when the host doesn't enable 
split lock detection. For example, on cloud environment, if the 
customers want to run their legacy workload that can generate split 
locks, the CSP would have to disable slit lock detection in the host but 
use bus lock VM exit to catch the bus lock in the TDX guest. In this 
case, TDX guest is free to use X86_FEATURE_BUS_LOCK_DETECT and it works 
as expected.

---

## [11] Xiaoyao Li — 2025-11-28
*Subject: Re: [PATCH 1/2] x86/split_lock: Don't try to handle user split lock
 in TDX guest*

Hi Andrew,

On 11/28/2025 12:55 AM, Andrew Cooper wrote:
>> I am not sure. Leaving it as produces produces false messages which is
>> not good, but not critical.

Well, more accurate, it's SPLIT_LOCK_DISABLE, not BUS_LOCK_DISABLE.(bus 
lock have two types: split lock and uc lock)

No, it's not TDX who is enabling SPLIT_LOCK_DISABLE, but the host. The 
default mode of Linux is "warn", so that by default the host Linux 
enables SPLIT_LOCK_DISABLE. And TDX module doesn't context switch 
MSR_TEST_CTRL when entering into the TDX vCPU because MSR_TEST_CTRL is 
not virtualizable. Thus SPLIT_LOCK_DISABLE remains enabled when TDX vCPU 
is running.

Regarding UC_LOCK_DISABLE, Linux doesn't enable it. Not sure if BIOS 
enables it or not (as far as I know, I don't see any bios enables it)

> Looking at the backtrace:
> 

Hi x86 maintainers,

Should we fix it?

> Second, because the attempt to disable BUS_LOCK_DISABLE was blocked,
> simply retrying the instruction will generate a new #AC and livelock.

This patch is just achieving this, while it raises the SIGBUS to userspace.

> It looks like software in a TDX VM will simply have to accept that it
> cannot cause a bus lock.

If the host doesn't enable SPLIT_LOCK_DISABLE, then split lock might not 
be fatal to TDX guests.

> ~Andrew

---

## [12] Xiaoyao Li — 2025-12-17
*Subject: Re: [PATCH 1/2] x86/split_lock: Don't try to handle user split lock
 in TDX guest*

On 11/26/2025 7:25 PM, Kiryl Shutsemau wrote:
> On Wed, Nov 26, 2025 at 06:02:03PM +0800, Xiaoyao Li wrote:
>> When the host enables split lock detection feature, the split lock from

Hi Dave,

Do you like this suggestion from Kiryl? If you don't object it, I will 
do it in v2.

---
