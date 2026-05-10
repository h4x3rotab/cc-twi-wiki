---
title: 'fs/resctrl: Fix MBM events being unconditionally enabled in mbm_event mode'
date: 2025-09-30
last_reply: 2025-10-15
message_count: 15
participants: ['Babu Moger', 'Reinette Chatre', 'Babu Moger']
---

## [1] Babu Moger — 2025-09-30

resctrl features can be enabled or disabled using boot-time kernel
parameters. To turn off the memory bandwidth events (mbmtotal and
mbmlocal), users need to pass the following parameter to the kernel:
"rdt=!mbmtotal,!mbmlocal".

Found that memory bandwidth events (mbmtotal and mbmlocal) cannot be
disabled when mbm_event mode is enabled. resctrl_mon_resource_init()
unconditionally enables these events without checking if the underlying
hardware supports them.

Remove the unconditional enablement of MBM features in
resctrl_mon_resource_init() to fix the problem. The hardware support
verification is already done in get_rdt_mon_resources().

Fixes: 13390861b426 ("x86,fs/resctrl: Detect Assignable Bandwidth Monitoring feature details")
Signed-off-by: Babu Moger <babu.moger@amd.com>
---
Patch is created on top of latest tip/master(6.17.0-rc7):
707007037fc6 (tip/master) Merge branch into tip/master: 'x86/tdx'
---
 fs/resctrl/monitor.c | 16 +++++++---------
 1 file changed, 7 insertions(+), 9 deletions(-)

diff --git a/fs/resctrl/monitor.c b/fs/resctrl/monitor.c
index 4076336fbba6..572a9925bd6c 100644
--- a/fs/resctrl/monitor.c
+++ b/fs/resctrl/monitor.c
@@ -1782,15 +1782,13 @@ int resctrl_mon_resource_init(void)
 		mba_mbps_default_event = QOS_L3_MBM_TOTAL_EVENT_ID;
 
 	if (r->mon.mbm_cntr_assignable) {
-		if (!resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID))
-			resctrl_enable_mon_event(QOS_L3_MBM_TOTAL_EVENT_ID);
-		if (!resctrl_is_mon_event_enabled(QOS_L3_MBM_LOCAL_EVENT_ID))
-			resctrl_enable_mon_event(QOS_L3_MBM_LOCAL_EVENT_ID);
-		mon_event_all[QOS_L3_MBM_TOTAL_EVENT_ID].evt_cfg = r->mon.mbm_cfg_mask;
-		mon_event_all[QOS_L3_MBM_LOCAL_EVENT_ID].evt_cfg = r->mon.mbm_cfg_mask &
-								   (READS_TO_LOCAL_MEM |
-								    READS_TO_LOCAL_S_MEM |
-								    NON_TEMP_WRITE_TO_LOCAL_MEM);
+		if (resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID))
+			mon_event_all[QOS_L3_MBM_TOTAL_EVENT_ID].evt_cfg = r->mon.mbm_cfg_mask;
+		if (resctrl_is_mon_event_enabled(QOS_L3_MBM_LOCAL_EVENT_ID))
+			mon_event_all[QOS_L3_MBM_LOCAL_EVENT_ID].evt_cfg = r->mon.mbm_cfg_mask &
+									   (READS_TO_LOCAL_MEM |
+									    READS_TO_LOCAL_S_MEM |
+									    NON_TEMP_WRITE_TO_LOCAL_MEM);
 		r->mon.mbm_assign_on_mkdir = true;
 		resctrl_file_fflags_init("num_mbm_cntrs",
 					 RFTYPE_MON_INFO | RFTYPE_RES_CACHE);

---

## [2] Reinette Chatre — 2025-10-06
*Subject: Re: [PATCH] fs/resctrl: Fix MBM events being unconditionally enabled
 in mbm_event mode*

Hi Babu,

On 9/30/25 1:26 PM, Babu Moger wrote:
> resctrl features can be enabled or disabled using boot-time kernel
> parameters. To turn off the memory bandwidth events (mbmtotal and

ah, indeed ... although, the intention behind the mbmtotal and mbmlocal kernel
parameters was to connect them to the actual hardware features identified
by X86_FEATURE_CQM_MBM_TOTAL and X86_FEATURE_CQM_MBM_LOCAL respectively.


> Found that memory bandwidth events (mbmtotal and mbmlocal) cannot be
> disabled when mbm_event mode is enabled. resctrl_mon_resource_init()

Technically this is correct since if hardware supports ABMC then the
hardware is no longer required to support X86_FEATURE_CQM_MBM_TOTAL and
X86_FEATURE_CQM_MBM_LOCAL in order to provide mbm_total_bytes
and mbm_local_bytes. 

I can see how this may be confusing to user space though ...

> 
> Remove the unconditional enablement of MBM features in

I believe by "hardware support" you mean hardware support for 
X86_FEATURE_CQM_MBM_TOTAL and X86_FEATURE_CQM_MBM_LOCAL. Wouldn't a fix like
this then require any system that supports ABMC to also support
X86_FEATURE_CQM_MBM_TOTAL and X86_FEATURE_CQM_MBM_LOCAL to be able to 
support mbm_total_bytes and mbm_local_bytes?

This problem seems to be similar to the one solved by [1] since
by supporting ABMC there is no "hardware does not support mbmtotal/mbmlocal"
but instead there only needs to be a check if the feature has been disabled
by command line. That is, add a rdt_is_feature_enabled() check to the
existing "!resctrl_is_mon_event_enabled()" check?

But wait ... I think there may be a bigger problem when considering systems
that support ABMC but not X86_FEATURE_CQM_MBM_TOTAL and X86_FEATURE_CQM_MBM_LOCAL.
Shouldn't resctrl prevent such a system from switching to "default" 
mbm_assign_mode? Otherwise resctrl will happily let such a system switch
to default mode and when user attempts to read an event file resctrl will
attempt to read it via MSRs that are not supported.
Looks like ABMC may need something similar to CONFIG_RESCTRL_ASSIGN_FIXED
to handle this case in show() while preventing user space from switching to
"default" mode on write()?

Reinette

[1] https://lore.kernel.org/lkml/20250925200328.64155-23-tony.luck@intel.com/

---

## [3] Moger, Babu — 2025-10-06
*Subject: Re: [PATCH] fs/resctrl: Fix MBM events being unconditionally enabled
 in mbm_event mode*

Hi Reinette,

On 10/6/25 12:56, Reinette Chatre wrote:
> Hi Babu,
> 

Yes. That is correct. Right now, ABMC and X86_FEATURE_CQM_MBM_TOTAL/
X86_FEATURE_CQM_MBM_LOCAL are kind of tightly coupled. We have not clearly
separated the that.

> 
> This problem seems to be similar to the one solved by [1] since

Enable or disable needs to be done at get_rdt_mon_resources(). It needs to
be done early in  the initialization before calling domain_add_cpu() where
event data structures (mbm_states aarch_mbm_states) are allocated.

> 
> But wait ... I think there may be a bigger problem when considering systems

This may not be an issue right now. When X86_FEATURE_CQM_MBM_TOTAL and
X86_FEATURE_CQM_MBM_LOCAL are not supported then mon_data files of these
events are not created.

> 
> Reinette

---

## [4] Reinette Chatre — 2025-10-06
*Subject: Re: [PATCH] fs/resctrl: Fix MBM events being unconditionally enabled
 in mbm_event mode*

Hi Babu,

On 10/6/25 1:38 PM, Moger, Babu wrote:
> Hi Reinette,
> 

Are you speaking from resctrl side since from what I understand these are
independent features from the hardware side?

>> This problem seems to be similar to the one solved by [1] since
>> by supporting ABMC there is no "hardware does not support mbmtotal/mbmlocal"

Good point. My mistake to suggest the event should be enabled by
resctrl fs.

> 
>>

By "right now" I assume you mean the current implementation? I think your statement
assumes that no CPUs come or go after resctrl_mon_resource_init() enables the MBM events?
Current implementation will enable MBM events if ABMC is supported. When the
first CPU of a domain comes online after that then resctrl will create the mon_data
files. These files will remain if a user then switches to default mode and if
the user then attempts to read one of these counters then I expect problems.

Reinette

---

## [5] Babu Moger — 2025-10-07
*Subject: Re: [PATCH] fs/resctrl: Fix MBM events being unconditionally enabled
 in mbm_event mode*

Hi Reinette,

On 10/6/25 20:23, Reinette Chatre wrote:
> Hi Babu,
> 

It is independent from hardware side. I meant we still use legacy events 
from "default" mode.

> 
>>> This problem seems to be similar to the one solved by [1] since


How about adding another check in get_rdt_mon_resources()?

if (rdt_cpu_has(X86_FEATURE_CQM_MBM_TOTAL)
     || rdt_is_feature_enabled(mbmtotal)) {
                 resctrl_enable_mon_event(QOS_L3_MBM_TOTAL_EVENT_ID);
                 ret = true;
         }

I need to take Tony's patch for this.

> 
>>

Yes. It will be a problem in the that case.

I am not clear on using config option you mentioned above.

What about using the check resctrl_is_mon_event_enabled() in

resctrl_mbm_assign_mode_show() and resctrl_mbm_assign_mode_write() ?

Thanks
Babu

---

## [6] Reinette Chatre — 2025-10-07
*Subject: Re: [PATCH] fs/resctrl: Fix MBM events being unconditionally enabled
 in mbm_event mode*

Hi Babu,

On 10/7/25 10:36 AM, Babu Moger wrote:
> Hi Reinette,
> 

Thank you for confirming. I was wondering if we need to fix it via cpuid_deps[]
and resctrl_cpu_detect() to address a hardware dependency. If hardware self
does not have the dependency then we need to fix it another way.

> 
>>

Something like this yes. I think it should be in rdt_get_mon_l3_config() though, within
the ABMC feature settings. If not then there may be an issue if the user boots with
rdt=!abmc? I cannot see why the rdt_cpu_has(X86_FEATURE_CQM_MBM_TOTAL) check is needed,
which flow are you addressing?

Before we exchange code I would like to step back a bit just to be clear that we agree
on the current issues and what user space may expect. After this it should be easier to
exchange code. (more below)

> 
> I need to take Tony's patch for this.

Thinking about this more the issue is not about the mon_data files being created since
they are only created if resctrl is mounted and resctrl_mon_resource_init() is run
before creating the mountpoint. From what I can tell current MBM events supported by
ABMC will be enabled at the time resctrl can be mounted so if X86_FEATURE_CQM_MBM_TOTAL
and X86_FEATURE_CQM_MBM_LOCAL are not supported but ABMC is then I believe the
mon_data files will be created.

There is a problem with the actual domain creation during resctrl initialization
where the MBM state data structures are created and depend on the events being
enabled then.
resctrl assumes that if an event is enabled then that event's associated
rdt_mon_domain::mbm_states and rdt_hw_mon_domain::arch_mbm_states exist and if
those data structures are created (or not created) during CPU online and MBM
event comes online later then there will be invalid memory accesses.

The conclusion is the same though ... the events need to be initialized during
resctrl initialization as you note above.

> 
> I am not clear on using config option you mentioned above.

This is more about what is accomplished by the config option than whether it is
a config option that controls the flow. More below but I believe there may be
scenarios where only mbm_event is supported and in that case I expect, even on AMD,
it may be possible that there is no supported "default" mode and thus:
 # cat /sys/fs/resctrl/info/L3_MON/mbm_assign_mode                             
  [mbm_event]

> 
> What about using the check resctrl_is_mon_event_enabled() in

Trying to think through how to support a system that can switch between default
and mbm_event mode I see a couple of things to consider. This is as I am thinking
through the flows without able to experiment. I think it may help if you could sanity
check this with perhaps a few experiments to considering the flows yourself to see where
I am missing things.

When we are clear on the flows to support and how to interact with user space it will
be easier to start exchanging code.

a) MBM state data structures
   As mentioned above, rdt_mon_domain::mbm_states and rdt_hw_mon_domain::arch_mbm_states
   are created during CPU online based on MBM event enabled state. During runtime
   an enabled MBM event is assumed to have state.
   To me this implies that any possible MBM event should be enabled during early
   initialization.
   A consequence is that any possible MBM event will have its associated event file
   created even if the active mode of the time cannot support it. (I do not think
   we want to have event files come and go).
b) Switching between modes.
   From what I can tell switching mode is always allowed as long as system supports
   assignable counters and that may not be correct. Consider a system that supports
   ABMC but does not support X86_FEATURE_CQM_MBM_TOTAL and/or X86_FEATURE_CQM_MBM_LOCAL ...
   should it be allowed to switch to "default" mode? At this time I believe this is allowed
   yet this is an unusable state (as far as MBM goes) and I expect any attempt at reading
   an event file will result in invalid MSR access?
   Complexity increases if there is a mismatch in supported events, for example if mbm_event
   mode supports total and local but default mode only supports one. Should it be allowed
   to switch modes? If so, user can then still read from both files, the check whether assignable
   counters is enabled will fail and resctrl will attempt to read both via the counter MSRs,
   even an unsupported event (continued below).
c) Read of event file
   A user can read from event file any time even if active mode (default or mbm_event) does
   not support it. If mbm_event mode is enabled then resctrl will attempt to use counters,
   if default mode is enabled then resctrl will attempt to use MSRs.
   This currently entirely depends on whether mbm_event mode is enabled or not.
   Perhaps we should add checks here to prevent user from reading an event if the
   active mode does not support it? Alternatively prevent user from switching to a mode
   that cannot be supported.

Look forward to how you view things and thoughts on how user may expect to interact with these
features.

Reinette

---

## [7] Reinette Chatre — 2025-10-14
*Subject: Re: [PATCH] fs/resctrl: Fix MBM events being unconditionally enabled
 in mbm_event mode*

Hi Babu,

On 10/7/25 7:38 PM, Reinette Chatre wrote:
> On 10/7/25 10:36 AM, Babu Moger wrote:
>> On 10/6/25 20:23, Reinette Chatre wrote:

I am concerned about this issue. The original changelog only mentions that events are enabled when
they should not be but it looks to me that there is a more serious issue if the user then attempts
to read from such an event. Have you tried the scenario when a user boots with the parameters
mentioned in changelog (rdt=!mbmtotal,!mbmlocal) and then attempts to read one of these events?
Reading from the event will attempt to access its architectural state but from what I can tell
that will not be allocated since the events are not enabled at the time of the allocation.

This needs to be fixed during this cycle. A week has passed since my previous message so I do not
think that it will be possible to create a full featured solution that keeps X86_FEATURE_ABMC
and X86_FEATURE_CQM_MBM_TOTAL/X86_FEATURE_CQM_MBM_LOCAL independent.

What do you think of something like below that builds on your original change and additionally
enforces dependency between these features to support the resctrl assumptions? From what I understand
this is ok for current AMD hardware? A not-as-urgent follow-up can make these features independent
again?


diff --git a/arch/x86/kernel/cpu/resctrl/monitor.c b/arch/x86/kernel/cpu/resctrl/monitor.c
index c8945610d455..fd42fe7b2fdc 100644
--- a/arch/x86/kernel/cpu/resctrl/monitor.c
+++ b/arch/x86/kernel/cpu/resctrl/monitor.c
@@ -452,7 +452,16 @@ int __init rdt_get_mon_l3_config(struct rdt_resource *r)
 		r->mon.mbm_cfg_mask = ecx & MAX_EVT_CONFIG_BITS;
 	}
 
-	if (rdt_cpu_has(X86_FEATURE_ABMC)) {
+	/*
+	 * resctrl assumes a system that supports assignable counters can
+	 * switch to "default" mode. Ensure that there is a "default" mode
+	 * to switch to. This enforces a dependency between the independent
+	 * X86_FEATURE_ABMC and X86_FEATURE_CQM_MBM_TOTAL/X86_FEATURE_CQM_MBM_LOCAL
+	 * hardware features.
+	 */
+	if (rdt_cpu_has(X86_FEATURE_ABMC) &&
+	    (rdt_cpu_has(X86_FEATURE_CQM_MBM_TOTAL) ||
+	     rdt_cpu_has(X86_FEATURE_CQM_MBM_LOCAL))) {
 		r->mon.mbm_cntr_assignable = true;
 		cpuid_count(0x80000020, 5, &eax, &ebx, &ecx, &edx);
 		r->mon.num_mbm_cntrs = (ebx & GENMASK(15, 0)) + 1;
diff --git a/fs/resctrl/monitor.c b/fs/resctrl/monitor.c
index 4076336fbba6..572a9925bd6c 100644
--- a/fs/resctrl/monitor.c
+++ b/fs/resctrl/monitor.c
@@ -1782,15 +1782,13 @@ int resctrl_mon_resource_init(void)
 		mba_mbps_default_event = QOS_L3_MBM_TOTAL_EVENT_ID;
 
 	if (r->mon.mbm_cntr_assignable) {
-		if (!resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID))
-			resctrl_enable_mon_event(QOS_L3_MBM_TOTAL_EVENT_ID);
-		if (!resctrl_is_mon_event_enabled(QOS_L3_MBM_LOCAL_EVENT_ID))
-			resctrl_enable_mon_event(QOS_L3_MBM_LOCAL_EVENT_ID);
-		mon_event_all[QOS_L3_MBM_TOTAL_EVENT_ID].evt_cfg = r->mon.mbm_cfg_mask;
-		mon_event_all[QOS_L3_MBM_LOCAL_EVENT_ID].evt_cfg = r->mon.mbm_cfg_mask &
-								   (READS_TO_LOCAL_MEM |
-								    READS_TO_LOCAL_S_MEM |
-								    NON_TEMP_WRITE_TO_LOCAL_MEM);
+		if (resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID))
+			mon_event_all[QOS_L3_MBM_TOTAL_EVENT_ID].evt_cfg = r->mon.mbm_cfg_mask;
+		if (resctrl_is_mon_event_enabled(QOS_L3_MBM_LOCAL_EVENT_ID))
+			mon_event_all[QOS_L3_MBM_LOCAL_EVENT_ID].evt_cfg = r->mon.mbm_cfg_mask &
+									   (READS_TO_LOCAL_MEM |
+									    READS_TO_LOCAL_S_MEM |
+									    NON_TEMP_WRITE_TO_LOCAL_MEM);
 		r->mon.mbm_assign_on_mkdir = true;
 		resctrl_file_fflags_init("num_mbm_cntrs",
 					 RFTYPE_MON_INFO | RFTYPE_RES_CACHE);

---

## [8] Babu Moger — 2025-10-14
*Subject: Re: [PATCH] fs/resctrl: Fix MBM events being unconditionally enabled
 in mbm_event mode*

Hi Reinette,

On 10/14/25 11:24, Reinette Chatre wrote:
> Hi Babu,
>


Yea.  Taken note of all your points. Sorry for the Iate response.  I was 
investigating on how to fix in a proper way.


> I am concerned about this issue. The original changelog only mentions that events are enabled when
> they should not be but it looks to me that there is a more serious issue if the user then attempts


Yes. I saw the issues. It fails to mount in my case with panic trace.


>
> This needs to be fixed during this cycle. A week has passed since my previous message so I do not


Yes. I understand your concern.


> think that it will be possible to create a full featured solution that keeps X86_FEATURE_ABMC
> and X86_FEATURE_CQM_MBM_TOTAL/X86_FEATURE_CQM_MBM_LOCAL independent.


Agree.


>
> What do you think of something like below that builds on your original change and additionally


Yes. I tested it. Works fine.  It defaults to "default" mode if both the 
events(local and total) are disabled in kernel parameter. That is expected.


>
>
Thanks for the quick patch.

- Babu

>

---

## [9] Babu Moger — 2025-10-14
*Subject: Re: [PATCH] fs/resctrl: Fix MBM events being unconditionally enabled
 in mbm_event mode*

Hi Reinette,

On 10/14/25 12:38, Babu Moger wrote:
> Hi Reinette,
>

I can send the official patch if you are ok to go ahead with the patch.

Let me know if I can add Signoff from you or you can respond after it is 
reviewed.



>>
>>

---

## [10] Reinette Chatre — 2025-10-14
*Subject: Re: [PATCH] fs/resctrl: Fix MBM events being unconditionally enabled
 in mbm_event mode*

Hi Babu,

On 10/14/25 10:43 AM, Babu Moger wrote:
> On 10/14/25 12:38, Babu Moger wrote:
>> On 10/14/25 11:24, Reinette Chatre wrote:

...

>>>>>>>> But wait ... I think there may be a bigger problem when considering systems
>>>>>>>> that support ABMC but not X86_FEATURE_CQM_MBM_TOTAL and X86_FEATURE_CQM_MBM_LOCAL.

(Just to ensure that there is not anything else going on) Could you please confirm if the panic is from
mon_add_all_files()->mon_event_read()->mon_event_count()->__mon_event_count()->resctrl_arch_reset_rmid()
that creates the MBM event files during mount and then does the initial read of RMID to determine the
starting count? 


>>
>>

Thank you very much for considering it and trying it out. Could you please also check if it
behaves sanely when just one of the MBM events is enabled? For example by just booting with
"rdt=!mbmtotal" or "rdt=!mbmlocal". Only one event's file should be created while it should
still be possible to switch between default and mbm_event mode, event reads from the event
file working as expected in both modes.


>>> diff --git a/arch/x86/kernel/cpu/resctrl/monitor.c b/arch/x86/kernel/cpu/resctrl/monitor.c
>>> index c8945610d455..fd42fe7b2fdc 100644

I am ok to go ahead with this patch. Please do rewrite the subject and changelog to highlight the
severity. I'd recommend that the changelog be something like:


	The following BUG/PANIC/splat(?) is encountered on mount of resctrl fs after booting
	a system that has X86_FEATURE_ABMC with the "rdt=!mbmtotal,!mbmlocal" kernel parameters:

	<trimmed backtrace>

	<problem description>

	<description of fix that also mentions it adds dependency where there is none and why this
	 is ok (for now?)>

> 
> Let me know if I can add Signoff from you or you can respond after it is reviewed.

You could add below tags or we can just do the usual review. Either works for me. Let me know if
you would like more collaboration on the changelog.

Co-developed-by: Reinette Chatre <reinette.chatre@intel.com>
Signed-off-by: Reinette Chatre <reinette.chatre@intel.com>

Reinette

---

## [11] Moger, Babu — 2025-10-14
*Subject: Re: [PATCH] fs/resctrl: Fix MBM events being unconditionally enabled
 in mbm_event mode*

Hi Reinette,

On 10/14/2025 3:57 PM, Reinette Chatre wrote:
> Hi Babu,
> 

It happens just before that (at mbm_cntr_get). We have not allocated 
d->cntr_cfg for the counters.
===================Panic trace =================================

349.330416] BUG: kernel NULL pointer dereference, address: 0000000000000008
[  349.338187] #PF: supervisor read access in kernel mode
[  349.343914] #PF: error_code(0x0000) - not-present page
[  349.349644] PGD 10419f067 P4D 0
[  349.353241] Oops: Oops: 0000 [#1] SMP NOPTI
[  349.357905] CPU: 45 UID: 0 PID: 3449 Comm: mount Not tainted 
6.18.0-rc1+ #120 PREEMPT(voluntary)
[  349.367803] Hardware name: AMD Corporation PURICO/PURICO, BIOS 
RPUT1003E 12/11/2024
[  349.376334] RIP: 0010:mbm_cntr_get+0x56/0x90
[  349.381096] Code: 45 8d 41 fe 83 f8 01 77 3d 8b 7b 50 85 ff 7e 36 49 
8b 84 24 f0 04 00 00 45 31 c0 eb 0d 41 83 c0 01 48 83 c0 10 44 39 c7 74 
1c <48> 3b 50 08 75 ed 3b 08 75 e9 48 83 c4 10 44 89 c0 5b 41 5c 41 5d
[  349.402037] RSP: 0018:ff56bba58655f958 EFLAGS: 00010246
[  349.407861] RAX: 0000000000000000 RBX: ffffffff9525b900 RCX: 
0000000000000002
[  349.415818] RDX: ffffffff95d526a0 RSI: ff1f5d52517c1800 RDI: 
0000000000000020
[  349.423774] RBP: ff56bba58655f980 R08: 0000000000000000 R09: 
0000000000000001
[  349.431730] R10: ff1f5d52c616a6f0 R11: fffc6a2f046c3980 R12: 
ff1f5d52517c1800
[  349.439687] R13: 0000000000000001 R14: ffffffff95d526a0 R15: 
ffffffff9525b968
[  349.447635] FS:  00007f17926b7800(0000) GS:ff1f5d59d45ff000(0000) 
knlGS:0000000000000000
[  349.456659] CS:  0010 DS: 0000 ES: 0000 CR0: 0000000080050033
[  349.463064] CR2: 0000000000000008 CR3: 0000000147afe002 CR4: 
0000000000771ef0
[  349.471022] PKRU: 55555554
[  349.474033] Call Trace:
[  349.476755]  <TASK>
[  349.479091]  ? kernfs_add_one+0x114/0x170
[  349.483560]  rdtgroup_assign_cntr_event+0x9b/0xd0
[  349.488795]  rdtgroup_assign_cntrs+0xab/0xb0
[  349.493553]  rdt_get_tree+0x4be/0x770
[  349.497623]  vfs_get_tree+0x2e/0xf0
[  349.501508]  fc_mount+0x18/0x90
[  349.505007]  path_mount+0x360/0xc50
[  349.508884]  ? putname+0x68/0x80
[  349.512479]  __x64_sys_mount+0x124/0x150
[  349.516848]  x64_sys_call+0x2133/0x2190
[  349.521123]  do_syscall_64+0x74/0x970

==================================================================

> 
> 

Yes. Checked already. Going to check again running few more tests.

> 
> 

Yes. Sure.


>>
>> Let me know if I can add Signoff from you or you can respond after it is reviewed.

Sure. Will send you the full change log first.

> 
> Co-developed-by: Reinette Chatre <reinette.chatre@intel.com>

thanks
Babu

---

## [12] Reinette Chatre — 2025-10-14
*Subject: Re: [PATCH] fs/resctrl: Fix MBM events being unconditionally enabled
 in mbm_event mode*

Hi Babu,

On 10/14/25 3:45 PM, Moger, Babu wrote:
> On 10/14/2025 3:57 PM, Reinette Chatre wrote:
>> On 10/14/25 10:43 AM, Babu Moger wrote:


>>>> Yes. I saw the issues. It fails to mount in my case with panic trace.
>>

Thank you for capturing this. This is a different trace but it confirms that it is the
same root cause. Specifically, event is enabled after the state it depends on is (not) allocated
during domain online.

Reinette

---

## [13] Moger, Babu — 2025-10-15
*Subject: Re: [PATCH] fs/resctrl: Fix MBM events being unconditionally enabled
 in mbm_event mode*

Hi Reinette,

On 10/14/2025 6:09 PM, Reinette Chatre wrote:
> Hi Babu,
> 

Yes. Thanks

Here is the changelog.

x86,fs/resctrl: Fix BUG with mbm_event mode when MBM events are disabled

The following BUG is encountered when mounting the resctrl filesystem 
after booting a system with X86_FEATURE_ABMC support and the kernel 
parameter 'rdt=!mbmtotal,!mbmlocal'.
  
===========================================================================
[  349.330416] BUG: kernel NULL pointer dereference, address: 
0000000000000008
[  349.338187] #PF: supervisor read access in kernel mode
[  349.343914] #PF: error_code(0x0000) - not-present page
[  349.349644] PGD 10419f067 P4D 0
[  349.353241] Oops: Oops: 0000 [#1] SMP NOPTI
[  349.357905] CPU: 45 UID: 0 PID: 3449 Comm: mount Not tainted
                    6.18.0-rc1+ #120 PREEMPT(voluntary)
[  349.367803] Hardware name: AMD Corporation
[  349.376334] RIP: 0010:mbm_cntr_get+0x56/0x90
[  349.381096] Code: 45 8d 41 fe 83 f8 01 77 3d 8b 7b 50 85 ff 7e 36 49 
8b 84 24 f0 04 00 00 45 31 c0 eb 0d 41 83 c0 01 48 83 c0 10 44 39 c7 74 
1c <48> 3b 50 08 75 ed 3b 08 75 e9 48 83 c4 10 44 89 c0 5b 41 5c 41 5d
[  349.402037] RSP: 0018:ff56bba58655f958 EFLAGS: 00010246
[  349.407861] RAX: 0000000000000000 RBX: ffffffff9525b900 RCX: 
0000000000000002
[  349.415818] RDX: ffffffff95d526a0 RSI: ff1f5d52517c1800 RDI: 
0000000000000020
[  349.423774] RBP: ff56bba58655f980 R08: 0000000000000000 R09: 
0000000000000001
[  349.431730] R10: ff1f5d52c616a6f0 R11: fffc6a2f046c3980 R12: 
ff1f5d52517c1800
[  349.439687] R13: 0000000000000001 R14: ffffffff95d526a0 R15: 
ffffffff9525b968
[  349.447635] FS:  00007f17926b7800(0000) GS:ff1f5d59d45ff000(0000)
                     knlGS:0000000000000000
[  349.456659] CS:  0010 DS: 0000 ES: 0000 CR0: 0000000080050033
[  349.463064] CR2: 0000000000000008 CR3: 0000000147afe002 CR4: 
0000000000771ef0
[  349.471022] PKRU: 55555554
[  349.474033] Call Trace:
[  349.476755]  <TASK>
[  349.479091]  ? kernfs_add_one+0x114/0x170
[  349.483560]  rdtgroup_assign_cntr_event+0x9b/0xd0
[  349.488795]  rdtgroup_assign_cntrs+0xab/0xb0
[  349.493553]  rdt_get_tree+0x4be/0x770
[  349.497623]  vfs_get_tree+0x2e/0xf0
[  349.501508]  fc_mount+0x18/0x90
[  349.505007]  path_mount+0x360/0xc50
[  349.508884]  ? putname+0x68/0x80
[  349.512479]  __x64_sys_mount+0x124/0x150

When mbm_event mode is enabled, it implicitly enables both MBM total and
local events. However, specifying the kernel parameter
"rdt=!mbmtotal,!mbmlocal" disables these events during resctrl 
initialization. As a result, related data structures, such as 
rdt_mon_domain::mbm_states, cntr_cfg, and 
rdt_hw_mon_domain::arch_mbm_states are not allocated. This
leads to a BUG when the user attempts to mount the resctrl filesystem,
which tries to access these un-allocated structures.


Fix the issue by adding a dependency on X86_FEATURE_CQM_MBM_TOTAL and
X86_FEATURE_CQM_MBM_LOCAL for X86_FEATURE_ABMC to be enabled. This is
acceptable for now, as X86_FEATURE_ABMC currently implies support for 
MBM total and local events. However, this dependency should be revisited 
and removed in the future to decouple feature handling more cleanly.

Fixes: 13390861b426e ("x86,fs/resctrl: Detect Assignable Bandwidth 
Monitoring feature details")
Co-developed-by: Reinette Chatre <reinette.chatre@intel.com>
Signed-off-by: Reinette Chatre <reinette.chatre@intel.com>
Signed-off-by: Babu Moger <babu.moger@amd.com>

====================================================

thanks
Babu

---

## [14] Reinette Chatre — 2025-10-15
*Subject: Re: [PATCH] fs/resctrl: Fix MBM events being unconditionally enabled
 in mbm_event mode*

Hi Babu,

On 10/15/25 7:55 AM, Moger, Babu wrote:
> Hi Reinette,
> 

"booting a system with X86_FEATURE_ABMC" sounds like this is a feature enabled
during boot?

>  
> ===========================================================================

This backtrace needs to be trimmed. See "Backtraces in commit messages" in
Documentation/process/submitting-patches.rst

> [  349.376334] RIP: 0010:mbm_cntr_get+0x56/0x90
> [  349.381096] Code: 45 8d 41 fe 83 f8 01 77 3d 8b 7b 50 85 ff 7e 36 49 8b 84 24 f0 04 00 00 45 31 c0 eb 0d 41 83 c0 01 48 83 c0 10 44 39 c7 74 1c <48> 3b 50 08 75 ed 3b 08 75 e9 48 83 c4 10 44 89 c0 5b 41 5c 41 5d

This may be a bit confusing with the jumps from "enabled" to "disabled" without noting the
contexts (arch vs fs, early init vs late init).

> leads to a BUG when the user attempts to mount the resctrl filesystem,
> which tries to access these un-allocated structures.

If I understand correctly the fix for the NULL pointer access is to remove
the late event enabling from resctrl fs. The new dependency fixes a related but different
issue that limits the scenarios in which mbm_event mode is enabled and when it may be possible
to switch between modes.

I think the changelog can be made more specific with some adjustments. Here is an attempt
at doing so but I think it can still be improved for flow.

	x86,fs/resctrl: Fix NULL pointer dereference when events force disabled while in mbm_event mode

	The following NULL pointer dereference is encountered on mount of resctrl fs after booting
	a system that support assignable counters with the "rdt=!mbmtotal,!mbmlocal" kernel parameters:

	BUG: kernel NULL pointer dereference, address: 0000000000000008
	#PF: supervisor read access in kernel mode
	#PF: error_code(0x0000) - not-present page
	RIP: 0010:mbm_cntr_get
	Call Trace:
	rdtgroup_assign_cntr_event
	rdtgroup_assign_cntrs
	rdt_get_tree

	Specifying the kernel parameter "rdt=!mbmtotal,!mbmlocal" effectively disables the legacy
	X86_FEATURE_CQM_MBM_TOTAL and X86_FEATURE_CQM_MBM_LOCAL features and thus the MBM events
	they represent. This results in the per-domain MBM event related data structures to not
	be allocated during resctrl early initialization.

	resctrl fs initialization follows by implicitly enabling both MBM total and local
	events on a system that	supports assignable counters (mbm_event mode), but this enabling
	occurs after the per-domain data structures have been created.

	During runtime resctrl fs assumes that an enabled event can access all its state.
	This results in NULL pointer dereference when resctrl attempts to access the
	un-allocated structures of an enabled event.

	Remove the late MBM event enabling from resctrl fs.

	This leaves a problem where the X86_FEATURE_CQM_MBM_TOTAL and X86_FEATURE_CQM_MBM_LOCAL
	features may be	disabled while assignable counter (mbm_event) mode is enabled without
	any events to support. Switching between the "default" and "mbm_event" mode without
	any events is not practical.

	Create a dependency between the X86_FEATURE_CQM_MBM_TOTAL/X86_FEATURE_CQM_MBM_LOCAL
	and X86_FEATURE_ABMC (assignable counter) hardware features. An x86 system that supports
	assignable counters now requires support of X86_FEATURE_CQM_MBM_TOTAL or X86_FEATURE_CQM_MBM_LOCAL.
	This ensures all needed MBM related data structures are created before use and that it is
	only possible to switch	between "default" and "mbm_event" mode when the same events are
	available in both modes. This dependency does not exist in the hardware but this usage of
	these feature settings work for known systems.
	

> 
> Fixes: 13390861b426e ("x86,fs/resctrl: Detect Assignable Bandwidth Monitoring feature details")
Reinette

---

## [15] Moger, Babu — 2025-10-15
*Subject: Re: [PATCH] fs/resctrl: Fix MBM events being unconditionally enabled
 in mbm_event mode*

Hi Reinette,

On 10/15/2025 2:56 PM, Reinette Chatre wrote:
> Hi Babu,
> 

Yea.

> 
>>   

Yes. Sure.

> 
>> [  349.376334] RIP: 0010:mbm_cntr_get+0x56/0x90

Looks good to me.

thanks
Babu

---
