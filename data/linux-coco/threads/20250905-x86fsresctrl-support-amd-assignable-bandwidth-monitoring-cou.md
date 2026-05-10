---
title: 'x86,fs/resctrl: Support AMD Assignable Bandwidth Monitoring Counters (ABMC)'
date: 2025-09-05
last_reply: 2025-11-18
message_count: 63
participants: ['Babu Moger', 'Reinette Chatre', 'Borislav Petkov', 'Luck, Tony', 'Drew Fustini', 'Babu Moger']
---

## [1] Babu Moger — 2025-09-05

This series adds the support for Assignable Bandwidth Monitoring Counters
(ABMC). It is also called QoS RMID Pinning feature.

Series is written such that it is easier to support other assignable
features supported from different vendors.

The feature details are documented in APM [1] available from [2].
[1] AMD64 Architecture Programmer's Manual Volume 2: System Programming
Publication # 24593 Revision 3.41 section 19.3.3.3 Assignable Bandwidth
Monitoring (ABMC). The documentation is available at
Link: https://bugzilla.kernel.org/show_bug.cgi?id=206537 # [2]

The patches are based on top of commit (6.17.0-rc4)
commit 7005ad1c5fa6 ("Merge branch into tip/master: 'x86/tdx'")

Comments and suggestions are welcome, as ever.

# Introduction

Users can create as many monitor groups as RMIDs supported by the hardware.
However, the bandwidth monitoring feature on AMD systems only guarantees
that RMIDs currently assigned to a processor will be tracked by hardware.
The counters of any other RMIDs which are no longer being tracked will be
reset to zero. The MBM event counters return "Unavailable" for the RMIDs
that are not tracked by hardware. So, there can be only limited number of
groups that can give guaranteed monitoring numbers. With ever changing
configurations there is no way to definitely know which of these groups
are being tracked during a particular time. Users do not have the option
to monitor a group or set of groups for a certain period of time without
worrying about counters being reset in between.
    
The ABMC feature allows users to assign a hardware counter ID to an RMID,
event pair and monitor bandwidth usage as long as it is assigned. The
hardware continues to track the assigned counter until it is explicitly
unassigned by the user. Additionally, the user can specify the type of
memory transactions (e.g., reads, writes) to be tracked by the counter
for the assigned RMID.

Without ABMC enabled, monitoring will work in current 'default' mode without
assignment option.

# History

Earlier implementation of ABMC had dependancy on BMEC (Bandwidth Monitoring
Event Configuration). Peter had concerns with that implementation because
it may be not be compatible with ARM's MPAM.

Here are the threads discussing the concerns and new interface to address the concerns.
https://lore.kernel.org/lkml/CALPaoCg97cLVVAcacnarp+880xjsedEWGJPXhYpy4P7=ky4MZw@mail.gmail.com/
https://lore.kernel.org/lkml/CALPaoCiii0vXOF06mfV=kVLBzhfNo0SFqt4kQGwGSGVUqvr2Dg@mail.gmail.com/

Here are the finalized requirements based on the discussion:

*   BMEC and ABMC are incompatible with each other. They need to be mutually exclusive.

*   Eliminate global assignment listing. The interface
    /sys/fs/resctrl/info/L3_MON/mbm_assign_control is no longer required.

*   Create the configuration directories at /sys/fs/resctrl/info/L3_MON/event_configs/.
    The configuration file names should be free-form, allowing users to create them as needed.

*   Perform assignment listing at the group level by introducing mbm_L3_assignments
    in each monitoring group level. The listing should provide the following details:

    Event Configuration: Specifies the event configuration applied. This will be crucial
    when "mkdir" on event configuration is added in the future, leading to the creation
    of mon_data/mon_l3_*/<event configuration>.

    Domains: Identifies the domains where the configuration is applied, supporting multi-domain setups.

    Assignment Type: Indicates whether the assignment is Exclusive (e or d), Shared (s), or Unassigned (_).

    Exclusive assignment: Assign the counter ID the RMID, event pair exclusively.
    
    Shared assignment: A shared assignment applies to both soft-ABMC and ABMC. A user can designate a
                       "counter" (could be hardware counter or "active" RMID) as shared and that means
                       the counter within that domain is shared between different monitor groups and actual
                       assignment is scheduled by resctrl.  

    Unassigned: No longer assigned.

*   Provide option to enable or disable auto assignment when new group is created.

*   Keep the flexibility to support future assign options like Soft-ABMC etc.
    https://lore.kernel.org/lkml/7f10fa69-d1fe-4748-b10c-fa0c9b60bd66@intel.com/
    

This series addresses the requirements listed above and keeping the options open for future
enhancements.

# Implementation details

Create a generic interface to support user space assignment of scarce
counters used for monitoring. First usage of interface is by ABMC with option
to expand usage to "soft-ABMC" and MPAM counters in future.

Feature adds following interface files:

/sys/fs/resctrl/info/L3_MON/mbm_assign_mode: Reports the list of assignable
monitoring features supported. The enclosed brackets indicate which
feature is enabled.

/sys/fs/resctrl/info/L3_MON/num_mbm_cntrs: The maximum number of monitoring counters
(total of available and assigned counters) in each domain when the system supports
mbm_event mode.

/sys/fs/resctrl/info/L3_MON/available_mbm_cntrs: The number of monitoring counters
available for assignment in each domain when mbm_event mode is enabled on the system.

/sys/fs/resctrl/info/L3_MON/event_configs: Contains sub-directory for each MBM event
					   that can be assigned to a counter.

/sys/fs/resctrl/info/L3_MON/event_configs/mbm_total_bytes/event_filter: The type of
			memory transactions tracked by the event mbm_total_bytes.

/sys/fs/resctrl/info/L3_MON/event_configs/mbm_local_bytes/event_filter: The type of
			memory transactions tracked by the event mbm_local_bytes.

/sys/fs/resctrl/mbm_L3_assignments: Per monitor group interface to list or modify
				    counters assigned to the group.

/sys/fs/resctrl/info/L3_MON/mbm_assign_on_mkdir: Interface to enable automatic assignments
						 on resctrl group creation.
# Examples

a. Check if MBM assign support is available
	#mount -t resctrl resctrl /sys/fs/resctrl/

	# cat /sys/fs/resctrl/info/L3_MON/mbm_assign_mode
	[mbm_event]
	default

	mbm_event feature is detected and it is enabled.

b. Check how many assignable counters are supported. 

	# cat /sys/fs/resctrl/info/L3_MON/num_mbm_cntrs 
	0=32;1=32

c. Check how many assignable counters are available for assignment in each domain.

	# cat /sys/fs/resctrl/info/L3_MON/available_mbm_cntrs 
	0=30;1=30

d. Check the default event configuration.

	# cat /sys/fs/resctrl/info/L3_MON/event_configs/mbm_total_bytes/event_filter 
	local_reads,remote_reads,local_non_temporal_writes,remote_non_temporal_writes,
        local_reads_slow_memory,remote_reads_slow_memory,dirty_victim_writes_all

	# cat /sys/fs/resctrl/info/L3_MON/event_configs/mbm_local_bytes/event_filter 
	local_reads,local_non_temporal_writes,local_reads_slow_memory

e. Series adds a new interface file "mbm_L3_assignments" in each monitoring group
   to list and modify that group's monitoring states.

	The list is displayed in the following format:

	<Event>:<Domain id>=<Assignment state>;<Domain id>=<Assignment state>

        Event: A valid MBM event listed in the
        /sys/fs/resctrl/info/L3_MON/event_configs directory.

        Domain ID: A valid domain ID.

        Assignment types:

        _ : No counter assigned.

        e : Counter assigned exclusively.

	To list the default group states:
	# cat /sys/fs/resctrl/mbm_L3_assignments
	mbm_total_bytes:0=e;1=e
	mbm_local_bytes:0=e;1=e

	To unassign the counter associated with the mbm_total_bytes event on domain 0:
	# echo "mbm_total_bytes:0=_" > /sys/fs/resctrl/mbm_L3_assignments
	# cat /sys/fs/resctrl/mbm_L3_assignments
	mbm_total_bytes:0=_;1=e
	mbm_local_bytes:0=e;1=e

	To unassign the counter associated with the mbm_total_bytes event on all domains:
    	# echo "mbm_total_bytes:*=_" > /sys/fs/resctrl/mbm_L3_assignments
	# cat /sys/fs/resctrl/mbm_L3_assignment
	mbm_total_bytes:0=_;1=_
	mbm_local_bytes:0=e;1=e

	To assign a counter associated with the mbm_total_bytes event on all domains in exclusive mode:
    	# echo "mbm_total_bytes:*=e" > /sys/fs/resctrl/mbm_L3_assignments
	# cat /sys/fs/resctrl/mbm_L3_assignments
	mbm_total_bytes:0=e;1=e
	mbm_local_bytes:0=e;1=e

g. Read the events mbm_total_bytes and mbm_local_bytes of the default group.
   There is no change in reading the events with the assignment.  If the event is unassigned
   when reading, then the read will come back as "Unassigned".
	
	# cat /sys/fs/resctrl/mon_data/mon_L3_00/mbm_total_bytes
	779247936
	# cat /sys/fs/resctrl/mon_data/mon_L3_01/mbm_total_bytes
	10101346
	# cat /sys/fs/resctrl/mon_data/mon_L3_00/mbm_local_bytes 
	765207488
	# cat /sys/fs/resctrl/mon_data/mon_L3_01/mbm_local_bytes 
	12125777
	
h. Check the event configurations.

	# cat /sys/fs/resctrl/info/L3_MON/event_configs/mbm_total_bytes/event_filter
	local_reads,remote_reads,local_non_temporal_writes,remote_non_temporal_writes,
	local_reads_slow_memory,remote_reads_slow_memory,dirty_victim_writes_all

	# cat /sys/fs/resctrl/info/L3_MON/event_configs/mbm_local_bytes/event_filter
	local_reads,local_non_temporal_writes,local_reads_slow_memory

i. Change the event configuration for mbm_local_bytes.

	# echo "local_reads, local_non_temporal_writes, local_reads_slow_memory, remote_reads" >
	/sys/fs/resctrl/info/L3_MON/event_configs/mbm_local_bytes/event_filter

	# cat /sys/fs/resctrl/info/L3_MON/event_configs/mbm_local_bytes/event_filter
	local_reads,local_non_temporal_writes,local_reads_slow_memory,remote_reads
	
j. Now read the local event again. The first read may come back with "Unavailable"
   status. The subsequent read of mbm_local_bytes will display the current value.
	
	# cat /sys/fs/resctrl/mon_data/mon_L3_00/mbm_local_bytes
	Unavailable
	# cat /sys/fs/resctrl/mon_data/mon_L3_00/mbm_local_bytes
	314101
	# cat /sys/fs/resctrl/mon_data/mon_L3_01/mbm_local_bytes
        42322

k. Users have the option to go back to 'default' mbm_assign_mode if required.
   This can be done using the following command. Note that switching the
   mbm_assign_mode will reset all the MBM counters (and thus all MBM events) of all
   the resctrl groups.

	# echo "default" > /sys/fs/resctrl/info/L3_MON/mbm_assign_mode
	# cat /sys/fs/resctrl/info/L3_MON/mbm_assign_mode
	mbm_event
	[default]
	
l. Unmount the resctrl filesystem.
	 
	# umount /sys/fs/resctrl/
---
v18: Only couple of patches changed in this series.
     Patch 25: Updated the open coding in rdtgroup_update_cntr_event().
     Patch 28: Adjusted the user doc resctrl.rst for mbm_L3_assignments.

     Added Reviewed-by tag in most patches. Thanks to Reinette.

     Minor changelog updates(about documentation Link) in few patches. Nothing significant.
     Updated the coverletter to add mbm_assign_on_mkdir.

v17:
    Picked up first four patches from:
    https://lore.kernel.org/lkml/20250711235341.113933-1-tony.luck@intel.com/
    These patches have already been reviewed. Added Signed-off-by tag.

    Updated the Reviewed-by in few patches and Removed Reviewed-by in few patches when patch changed.

    Rephrased the changelogs in few patches.
   
    Added ABMC check in resctrl_cpu_detect() while detecting the feature details.

    Moved resctrl_mbm_assign_mode_show() to fs/resctrl/monitor.c.

    Moved resctrl_num_mbm_cntrs_show() to fs/resctrl/monitor.c.

    Moved resctrl_available_mbm_cntrs_show() to fs/resctrl/monitor.c.

    Updated evt_cfg to use r->mon.mbm_cfg_mask when initializing the events.

    Moved many functions from fs/resctrl/rdtgroup.c to fs/resctrl/monitor.c.

    Brought rdtgroup_assign_cntrs() in this patch from patch 28 to make compiler happy.
         
    Brought rdtgroup_unassign_cntrs() from patch 28 to monitor.c to make compiler happy.

    Squashed patch #24 abd #25 into one. Both are dependent on each other.

    Removed the check for kernfs_activate() in rdtgroup_mkdir_info_resdir().

    Added resctrl_arch_mbm_cntr_assign_enabled() in event_filter_show().

    Added the check resctrl_arch_mbm_cntr_assign_enabled() in
    resctrl_mbm_assign_on_mkdir_show() and resctrl_mbm_assign_on_mkdir_write() to
    make it accessible when mbm_event mode is enabled.

    Moved mbm_L3_assignments_show() to fs/resctrl/monitor.c.

    Moved mbm_L3_assignments_show() and all dependencies to fs/resctrl/monitor.c.

    Fixed the extra reference release in resctrl_bmec_files_show().

    Moved resctrl_mbm_assign_mode_write() to fs/resctrl/monitor.c

    Fixed the event configuration initialization while considering hw support.

    Always enabled auto assignment when switching to "mbm_event" mode.

v16:
    Picked up first four patches from (Tony):
    https://lore.kernel.org/lkml/20250711235341.113933-1-tony.luck@intel.com/
    These patches have already been reviewed.

    Updated Reviewed-by: tag for few patches.

    Fixed the conflicts with latest cpufeatures.h and scattered.c files.

    Added a new check in get_rdt_mon_resources().
    Added check in resctrl_is_mon_event_enabled() before enabling.

    Resetting the architectural state in resctrl_arch_config_cntr() in both
    assign and unassign cases now.

    Function renames:
    resctrl_config_cntr() -> rdtgroup_assign_cntr()
    rdtgroup_alloc_config_cntr() -> rdtgroup_alloc_assign_cntr()

    Passed struct mevt to rdtgroup_alloc_assign_cntr so it can print event name on failure.

    Function rename:
      rdtgroup_free_config_cntr() -> rdtgroup_free_unassign_cntr().

    Updated rdtgroup_free_unassign_cntr() to pass struct mon_evt to match
    rdtgroup_alloc_assign_cntr() prototype.

    Removed lots of copied and unnecessary text from resctrl.h.
    Also removed references to LLC occupancy.
    Removed arch_mon_ctx from resctrl_arch_cntr_read().

    Renamed get_corrected_val() -> get_corrected_val().
     
    Removed the call resctrl_arch_rmid_read_context_check();
    Added the text about RMID_VAL_UNAVAIL error.

    Squashed two patches into one.
     https://lore.kernel.org/lkml/df215f02db88cad714755cd5275f20cf0ee4ae26.1752013061.git.babu.moger@amd.com/
     https://lore.kernel.org/lkml/296c435e9bf63fc5031114cced00fbb4837ad327.1752013061.git.babu.moger@amd.com/

    Changed is_cntr field in struct rmid_read to is_mbm_cntr.
    Fixed the memory leak with arch_mon_ctx.
    Updated the resctrl.rst user doc.

    Report Unassigned only if none of the events in CTRL_MON and MON are assigned.
      
    Moved event_filter_show() to fs/resctrl/monitor.c

    Added rdtgroup_mutex in event_filter_show().
    Removed extern for mbm_transactions. Not required.
          
    Moved resctrl_process_configs() and event_filter_write() to fs/resctrl/monitor.c.

    Renamed resctrl_process_configs() -> resctrl_parse_mem_transactions().

    Fixed the return in resctrl_mbm_assign_on_mkdir_write().

    Moved r->mon.mbm_assign_on_mkdir initialization to resctrl_mon_resource_init().

    Updated resctrl.rst few corrections and consistancy.

    Fixed few references of counter_configs to -> event_configs.
    Renamed resctrl_process_assign() to resctrl_parse_mbm_assignment().
    Moved resctrl_parse_mbm_assignment() and rdtgroup_modify_assign_state() to monitor.c.

    Added new comment in resctrl_bmec_files_show() about kernfs_find_and_get failure.
    Added the parameter to resctrl_bmec_files_show() to pass the kernfs_node.
    Updated resctrl_bmec_files_show() to pass NULL for kn_fs_node.

    Added a patch to add me as a reviewer on Reinette's suggestion.

v15:
  1-4  Picked up Tony's tree. This will be base for both the series.
  rdt-aet-v5.5 branch of git://git.kernel.org/pub/scm/linux/kernel/git/aegl/linux.git
  After Reinette's comment on previous version.
  https://lore.kernel.org/lkml/e9eb906f-d463-4c1e-9e15-5ed795fe5366@intel.com/
  https://lore.kernel.org/lkml/b761e6ec-a874-4d06-8437-a3a717a91abb@intel.com/

  Improved changelog in most of the patches. Thanks to Reinette.
  Improved the code comment in few places.

  Fixed the enumeration code by adding check in resctrl_cpu_detect() during the init.
  Moved the fs related enumeration to resctrl_mon_resource_init().

  Removed evt_cfg from struct mbm_cntr_cfg based on the discussion.
  https://lore.kernel.org/lkml/887bad33-7f4a-4b6d-95a7-fdfe0451f42b@intel.com/

  Removed resctrl_set_mon_evt_cfg().
  Moved the event initialization to resctrl_mon_resource_init().

  Changed few goto labels for consistency.

  Added extra check !r->mon.mbm_cntr_assignable in mbm_cntr_get() to return error.

  Added two new arch calls resctrl_arch_cntr_read() and resctrl_arch_reset_cntr() implement
  mbm_event mode. This is kind of major change in this series.
  https://lore.kernel.org/lkml/b4b14670-9cb0-4f65-abd5-39db996e8da9@intel.com/

  Added is_cntr in rmid_read to implement resctrl_arch_cntr_read() and resctrl_arch_reset_cntr().

  Removed the error setting in rdtgroup_mondata_show(). It is already done in mon_event_read()
  based on the discussion.
  https://lore.kernel.org/lkml/b4b14670-9cb0-4f65-abd5-39db996e8da9@intel.com/

  Changed the function name resctrl_mkdir_counter_configs() to resctrl_mkdir_event_configs().
  Called resctrl_mkdir_event_configs from rdtgroup_mkdir_info_resdir().
  It avoids the call kernfs_find_and_get() to get the node for info directory.
  Used for_each_mon_event() where applicable.

  Fixed the partial initialization of val in resctrl_process_configs().
  Passed mon_evt where applicable. The struct rdt_resource can be obtained from mon_evt::rid.

  Fixed the static checker warning in resctrl_mbm_assign_on_mkdir_write() reported in
  https://lore.kernel.org/lkml/dd4a1021-b996-438e-941c-69dfcea5f22a@intel.com/

  Moved resctrl_bmec_files_show() inside rdtgroup_mkdir_info_resdir().

v14:
   Patch #1 is already been reviewed. Not need to review.

   Patches # 2-5:
   This is Tony's work. This is part of Tony's telemetry series.
   https://lore.kernel.org/lkml/20250521225049.132551-1-tony.luck@intel.com/

   Tony made special update for me to include in this series.
   https://lore.kernel.org/lkml/20250609162139.91651-1-tony.luck@intel.com/.
   We both are going to carry thesse mutliple events support patches.

   Patches #6-31 are changes related to mbm_assign_mode. 

   Took time to check all the text comments. Taken care most of comments.
   Anything missing is not intentional. ):

   Removed the dependancy on X86_FEATURE_CQM_MBM_TOTAL and X86_FEATURE_CQM_MBM_LOCAL
   as discussed in https://lore.kernel.org/lkml/5f8b21c6-5166-46a6-be14-0c7c9bfb7cde@intel.com/
   Reworked on ABMC enumeration during the init.

   Updated the code comment in resctrl.h on all the prototypes.

   Added lockdep_assert_cpus_held() in _resctrl_abmc_enable().
   Removed inline for resctrl_arch_mbm_cntr_assign_enabled().
   Added prototype descriptions for resctrl_arch_mbm_cntr_assign_enabled()
   and resctrl_arch_mbm_cntr_assign_set() in include/linux/resctrl.h.
   
   Changed the name of the monitor mode to mbm_event_assign based on the discussion.
   https://lore.kernel.org/lkml/7628cec8-5914-4895-8289-027e7821777e@amd.com/
   Updated resctrl.rst for mbm_event mode.
   Changed subject line to fs/resctrl in few patches.

   Removed BMEC reference internal.h. 

   Removed mbm_mode in mon_evt data structure as it is not required anymore.
   Added resctrl_get_mon_evt_cfg() and resctrl_set_mon_evt_cfg().

   Removed evt_cfg parameter in resctrl_arch_config_cntr(). Get evt_cfg only
   when assign is required.

   Updated the code documentation for mbm_cntr_alloc() and  mbm_cntr_get().
   Passed struct mon_evt to resctrl_assign_cntr_event() that way to avoid
   back and forth calls to get event details.

   Passing the struct mon_evt to resctrl_free_config_cntr() and removed
   the need for mbm_get_mon_event() call.
   Corrected the code documentation for mbm_cntr_free().

   Added WARN_ON_ONCE() when cntr_id < 0.
   Improved code documentation in include/linux/resctrl.h.
   Added the check in mbm_update() to skip overflow handler when counter is unassigned.

   Changed the term memory events to memory transactions to be consistant.

   Changed the name of directory to event_configs from counter_config.
   Updated user doc about the memory transactions supported by assignment.

   Renamed few functions resctrl_group_assign() -> rdtgroup_assign_cntr()
   resctrl_update_assign() -> resctrl_assign_cntr_allrdtgrp()

   Added rdtgroup_mutex in resctrl_mbm_assign_on_mkdir_show().

   Fixed the problem reported by Peter.
   https://lore.kernel.org/lkml/CALPaoCjvUSKLKOXzF85j8mHT=eZYM-7R0=gJ3PRgOk4yuF5ZhQ@mail.gmail.com/
   Updated the changelog.
   
   Added check in rdt_mon_features_show to hide bmec related feature.

   Added the call resctrl_bmec_files_show() to enable/disable files
   related to BMEC monitor mode is changed.

   Added resctrl_set_mon_evt_cfg() to reset event configuration values
   when mode is changes.

   Changed the name of the mbm_assign_mode's supported to mbm_event or default.
   https://lore.kernel.org/lkml/9b08ab86-22d2-40c1-be20-fcc73ee98b3d@amd.com/

   Added example section in user doc (resctrl.rst) on how to use mbm_assign_modes.

v13:
   Removed BMEC related 2 patches which were in the previous series.
   It was related to optimization which can be doen later.

   Patches are created on top of FS/ARCH restructure. So, major changes
   are due to FS/ARCH restructure. The files are split between
   arch/x86/kernel/cpu/resctrl/ and fs/resctrl/. So, functions
   are moved between these files accordingly.

   Added fflag RFTYPE_RES_CACHE for mbm_assign_mode, num_mbm_cntrs, available_mbm_cntrs.

   Removed the references to "mbm_assign_control".
  
   Moved resctrl_arch_config_cntr() prototype to include/linux/resctrl.h.
   Changed resctrl_arch_config_cntr() to retun void from int to simplify few call
   sequences.

   Added the event configuration details inside the evt_list in monitor domains.
   The avoids the need for new structure mbm_assign_config. 

   Passed evtid to functions resctrl_alloc_config_cntr() and resctrl_assign_cntr_event().
   Event configuration value can be easily obtained from mon_evt list.

   Added new patch to pass the entire struct rdtgroup to __mon_event_count(),
   mbm_update(), and related functions. We can easily get RMID,CLOSID etc from rdtgroup.

   Added new function __cntr_id_read_phys() to handle ABMC event reading.

   Added a new patch to hide BMEC related files when mbm_cntr_assign mode is enabled..
  
   Added the call resctrl_init_evt_configuration() to setup the event configuration during init.

   And few other commit message updates and user doc updates.

   Removed Reviewed-by from few patches as patches have changed due to FS/ARCH restructure.

   Let me know if I missed something.

v12:
   This version is kind of RFC series with a new interface.
   
   Removed Reviewed-by tag on few patches when the patch has changed.

   Moved BMEC related patches (1 and 2) to beginning of the series.
   Removed the dependancy on BMEC to ABMC feature.

   Removed the un-necessary initialization of mon_config_info structure.
   Changed wrmsrl instead of wrmsr to address the below comment.
   https://lore.kernel.org/lkml/0fc8dbd4-07d8-40bd-8eec-402b48762807@zytor.com/

   Fixed the conflicts due to recent changes in rdt_resource data structure.
   Added new mbm_cfg_mask field to resctrl_mon.
   
   Added the code to reset arch state inside _resctrl_abmc_enable().

   Added the check CONFIG_RESCTRL_ASSIGN_FIXED to take care of arm platforms.
   This will be defined only in arm and not in x86.

   Changed the code to display the max supported monitoring counters in each domain.
   
   Fixed the struct mbm_cntr_cfg code documentation.
   Moved the struct mbm_cntr_cfg definition to resctrl/internal.h as suggested by James.

   Replaced seq_puts(s, ";") with seq_putc(s, ';');
   Added missing rdt_last_cmd_clear() in resctrl_available_mbm_cntrs_show().

   Added the check to reset the architecture-specific state only when assign is requested.

   Added evt_cfg as the parameter to resctrl_arch_config_cntr() as the user will
   be passing the event configuration from /info/L3_MON/event_configs/.

   Changed the check in resctrl_alloc_config_cntr() to reduce the indentation.
   Fixed the handling error on first failure while assigning.
   Added new parameter event configuration (evt_cfg) to get the event configuration from user space.

   Added tte support for reading ABMC counters. This is bit involved change and affects lots of code.

   New patch to support event configurations via new counter_configs method.

   Removed mbm_cntr_reset() as it is not required while removing the group.

   Added new patch to handle auto assign on group creation ("mbm_assign_on_mkdir")

   Added couple of patches add interface for "mbm_L3_assignments" on each mon group.

   Introduced mbm_cntr_free_all() and resctrl_reset_rmid_all() to clear counters and
   non-architectural states when monitor mode is changed.
   https://lore.kernel.org/lkml/b60b4f72-6245-46db-a126-428fb13b6310@intel.com/

   Moved the resctrl_arch_mbm_cntr_assign_set_one to domain_add_cpu_mon().

   Patches 17, 18, 19, 20, 21, 23, 24 are completely new to address the new interface requirement.

v11:
   The commit 2937f9c361f7a ("x86/resctrl: Introduce resctrl_file_fflags_init() to initialize fflags")
   is already merged. Removed from the series.
   
   Resolved minor conflicts due to code displacement in latest code.
 
   Moved the monitoring related calls to monitor.c file when possible.
   Moved some of the changes from include/linux/resctrl.h to arch/x86/kernel/cpu/resctrl/internal.h
   as requested by Reinette. This changes will be moved back when arch and non code is separated.
   
   Renamed rdtgroup_mbm_assign_mode_show() to resctrl_mbm_assign_mode_show().
   Renamed rdtgroup_num_mbm_cntrs_show() to resctrl_num_mbm_cntrs_show().

   Moved the mon_config_info structure definition to internal.h.
   Moved resctrl_arch_mon_event_config_get() and resctrl_arch_mon_event_config_set()
   to monitor.c file.

   Moved resctrl_arch_assign_cntr() and resctrl_abmc_config_one_amd() to monitor.c.
   Added the code to reset the arch state in resctrl_arch_assign_cntr().
   Also removed resctrl_arch_reset_rmid() inside IPI as the counters are reset from the callers.

   Renamed rdtgroup_assign_cntr_event() to resctrl_assign_cntr_event().
   Refactored the resctrl_assign_cntr_event().
   Added functionality to exit on the first error during assignment.
   Simplified mbm_cntr_free().
   Removed the function mbm_cntr_assigned(). Will be using mbm_cntr_get() to
   figure out if the counter is assigned or not.
   
   Renamed rdtgroup_unassign_cntr_event() to resctrl_unassign_cntr_event().
   Refactored the resctrl_unassign_cntr_event().

   Moved mbm_cntr_reset() to monitor.c.
   Added code reset non-architectural state in mbm_cntr_reset().
   Added missing rdtgroup_unassign_cntrs() calls on failure path.

   Domain can be NULL with SNC support so moved the unassign check in rdtgroup_mondata_show().

   Renamed rdtgroup_mbm_assign_mode_write() to resctrl_mbm_assign_mode_write().
   Added more details in resctrl.rst about mbm_cntr_assign mode.
   Re-arranged the text in resctrl.rst file in section mbm_cntr_assign.

   Moved resctrl_arch_mbm_cntr_assign_set_one() to monitor.c

   Added non-arch RMID reset in mbm_config_write_domain().
   Removed resctrl_arch_reset_rmid() call in resctrl_abmc_config_one_amd(). Not required
   as reset of arch and non-arch rmid counters done from the callers. It simplies the IPI code.

   Fixed printing the separator after each domain while listing the group assignments.
   Renamed rdtgroup_mbm_assign_control_show to resctrl_mbm_assign_control_show().

   Fixed the static check warning with initializing dom_id in resctrl_process_flags()

   Added change log in each patch for specific changes.

v10:
   Major change is related to domain specific assignment.
   Added struct mbm_cntr_cfg inside mon domains. This will handle
   the domain specific assignments as discussed in below.
   https://lore.kernel.org/lkml/CALPaoCj+zWq1vkHVbXYP0znJbe6Ke3PXPWjtri5AFgD9cQDCUg@mail.gmail.com/
   I did not see the need to add cntr_id in mbm_state structure. Not used in the code.
   Following patches take care of these changes.
   Patch 12, 13, 15, 16, 17, 18.
   
   Added __init attribute to cache_alloc_hsw_probe(). Followed function
   prototype rules (preferred order is storage class before return type).
   
   Moved the mon_config_info structure definition to resctrl.h
   
   Added call resctrl_arch_reset_rmid() to reset the RMID in the domain inside IPI call
   resctrl_abmc_config_one_amd.
   
   SMP and non-SMP call support is not required in resctrl_arch_config_cntr with new
   domain specific assign approach/data structure.
   
   Assigned the counter before exposing the event files.
   Moved the call rdtgroup_assign_cntrs() inside mkdir_rdt_prepare_rmid_alloc().
   This is called both CNTR_MON and MON group creation.
   
   Call mbm_cntr_reset() when unmounted to clear all the assignments.
   
   Fixed the issue with finding the domain in multiple iterations in rdtgroup_process_flags().
   
   Printed full error message with domain information when assign fails.
   
   Taken care of other text comments in all the patches. Patch specific changes are in each patch.
   
   If I missed something please point me and it is not intentional.

v9:
   Patch 14 is a new addition. 
   Major change in patch 24.
   Moved the fix patch to address __init attribute to begining of the series.
   Fixed all the call sequences. Added additional Fixed tags.

   Added Reviewed-by where applicable.

   Took care of couple of minor merge conflicts with latest code.
   Re-ordered the MSR in couple of instances.
   Added available_mbm_cntrs (patch 14) to print the number of counter in a domain.

   Used MBM_EVENT_ARRAY_INDEX macro to get the event index.
   Introduced rdtgroup_cntr_id_init() to initialize the cntr_id

   Introduced new function resctrl_config_cntr to assign the counter, update
   the bitmap and reset the architectural state.
   Taken care of error handling(freeing the counter) when assignment fails.
  
   Changed rdtgroup_assign_cntrs() and rdtgroup_unassign_cntrs() to return void.
   Updated couple of rdtgroup_unassign_cntrs() calls properly.

   Fixed problem changing the mode to mbm_cntr_assign mode when it is
   not supported. Added extra checks to detect if systems supports it.
   
   https://lore.kernel.org/lkml/03b278b5-6c15-4d09-9ab7-3317e84a409e@intel.com/
   As discussed in the above comment, introduced resctrl_mon_event_config_set to
   handle IPI. But sending another IPI inside IPI causes problem. Kernel
   reports SMP warning. So, introduced resctrl_arch_update_cntr() to send the
   command directly.

   Fixed handling special case '//0=' and '//".
   Removed extra strstr() call in rdtgroup_mbm_assign_control_write().
   Added generic failure text when assignment operation fails.
   Corrected user documentation format texts.

v8:
  Patches are getting into final stages. 
  Couple of changes Patch 8, Patch 19 and Patch 23.
  Most of the other changes are related to rename and text message updates.

  Details are in each patch. Here is the summary.

  Added __init attribute to dom_data_init() in patch 8/25.
  Moved the mbm_cntrs_init() and mbm_cntrs_exit() functionality inside
  dom_data_init() and dom_data_exit() respectively.

  Renamed resctrl_mbm_evt_config_init() to arch_mbm_evt_config_init()
  Renamed resctrl_arch_event_config_get() to resctrl_arch_mon_event_config_get().
          resctrl_arch_event_config_set() to resctrl_arch_mon_event_config_set().

  Rename resctrl_arch_assign_cntr to resctrl_arch_config_cntr.
  Renamed rdtgroup_assign_cntr() to rdtgroup_assign_cntr_event().
  Added the code to return the error if rdtgroup_assign_cntr_event fails.
  Moved definition of MBM_EVENT_ARRAY_INDEX to resctrl/internal.h.
  Renamed rdtgroup_mbm_cntr_is_assigned to mbm_cntr_assigned_to_domain
  Added return error handling in resctrl_arch_config_cntr().
  Renamed rdtgroup_assign_grp to rdtgroup_assign_cntrs.
  Renamed rdtgroup_unassign_grp to rdtgroup_unassign_cntrs.
  Fixed the problem with unassigning the child MON groups of CTRL_MON group.
  Reset the internal counters after mbm_cntr_assign mode is changed.
  Renamed rdtgroup_mbm_cntr_reset() to mbm_cntr_reset()
  Renamed resctrl_arch_mbm_cntr_assign_configure to
            resctrl_arch_mbm_cntr_assign_set_one.

  Used the same IPI as event update to modify the assignment.
  Could not do the way we discussed in the thread.
  https://lore.kernel.org/lkml/f77737ac-d3f6-3e4b-3565-564f79c86ca8@amd.com/
  Needed to figure out event type to update the configuration.

  Moved unassign first and assign during the assign modification.
  Assign none "_" takes priority. Cannot be mixed with other flags.
  Updated the documentation and .rst file format. htmldoc looks ok.

v7:
   Major changes are related to FS and arch codes separation.
   Changed few interface names based on feedback.
   Here are the summary and each patch contains changes specific the patch.

   Removed WARN_ON for num_mbm_cntrs. Decided to dynamically allocate the bitmap.
   WARN_ON is not required anymore.
 
   Renamed the function resctrl_arch_get_abmc_enabled() to resctrl_arch_mbm_cntr_assign_enabled().

   Merged resctrl_arch_mbm_cntr_assign_disable, resctrl_arch_mbm_cntr_assign_disable
   and renamed to resctrl_arch_mbm_cntr_assign_set(). Passed the struct rdt_resource
   to these functions.

   Removed resctrl_arch_reset_rmid_all() from arch code. This will be done from FS the caller.

   Updated the descriptions/commit log in resctrl.rst to generic text. Removed ABMC references.
   Renamed mbm_mode to mbm_assign_mode.
   Renamed mbm_control to  mbm_assign_control.
   Introduced mutex lock in rdtgroup_mbm_mode_show().
 
   The 'legacy' mode is called 'default' mode. 

   Removed the static allocation and now allocating bitmap mbm_cntr_free_map dynamically.

   Merged rdtgroup_assign_cntr(), rdtgroup_alloc_cntr() into one.
   Merged rdtgroup_unassign_cntr(), rdtgroup_free_cntr() into one.
   
  Added struct rdt_resource to the interface functions resctrl_arch_assign_cntr ()
  and resctrl_arch_unassign_cntr().
  Rename rdtgroup_abmc_cfg() to resctrl_abmc_config_one_amd().
   
  Added a new patch to fix counter assignment on event config changes.

  Removed the references of ABMC from user interfaces.

  Simplified the parsing (strsep(&token, "//") in rdtgroup_mbm_assign_control_write().
  Added mutex lock in rdtgroup_mbm_assign_control_write() while processing.

  Thomas Gleixner asked us to update  https://gitlab.com/x86-cpuid.org/x86-cpuid-db. 
  It needs internal approval. We are working on it.

v6:
  We still need to finalize few interface details on mbm_assign_mode and mbm_assign_control
  in case of ABMC and Soft-ABMC. We can continue the discussion with this series.

  Added support for domain-id '*' to update all the domains at once.
  Fixed assign interface to allocate the counter if counter is
  not assigned.   
  Fixed unassign interface to free the counter if the counter is not
  assigned in any of the domains.

  Renamed abmc_capable to mbm_cntr_assignable.

  Renamed abmc_enabled to mbm_cntr_assign_enabled.
  Used msr_set_bit and msr_clear_bit for msr updates.
  Renamed resctrl_arch_abmc_enable() to resctrl_arch_mbm_cntr_assign_enable().
  Renamed resctrl_arch_abmc_disable() to resctrl_arch_mbm_cntr_assign_disable().

  Changed the display name from num_cntrs to num_mbm_cntrs.

  Removed the variable mbm_cntrs_free_map_len. This is not required.
  Removed the call mbm_cntrs_init() in arch code. This needs to be done at higher level.
  Used DECLARE_BITMAP to initialize mbm_cntrs_free_map.
  Removed unused config value definitions.

  Introduced mbm_cntr_map to track counters at domain level. With this
  we dont need to send MSR read to read the counter configuration.

  Separated all the counter id management to upper level in FS code.

  Added checks to detect "Unassigned" before reading the RMID.

  More details in each patch.

v5:
  Rebase changes (because of SNC support)

  Interface changes.
   /sys/fs/resctrl/mbm_assign to /sys/fs/resctrl/mbm_assign_mode.
   /sys/fs/resctrl/mbm_assign_control to /sys/fs/resctrl/mbm_assign_control.

  Added few arch specific routines.
  resctrl_arch_get_abmc_enabled.
  resctrl_arch_abmc_enable.
  resctrl_arch_abmc_disable.

  Few renames
   num_cntrs_free_map -> mbm_cntrs_free_map
   num_cntrs_init -> mbm_cntrs_init
   arch_domain_mbm_evt_config -> resctrl_arch_mbm_evt_config

  Introduced resctrl_arch_event_config_get and
    resctrl_arch_event_config_set() to update event configuration.

  Removed mon_state field mongroup. Added MON_CNTR_UNSET to initialize counters.

  Renamed ctr_id to cntr_id for the hardware counter.
 
  Report "Unassigned" in case the user attempts to read the events without assigning the counter.
  
  ABMC is enabled during the boot up. Can be enabled or disabled later.

  Fixed opcode and flags combination.
    '=_" is valid.
    "-_" amd "+_" is not valid.

 Added all the comments as far as I know. If I missed something, it is not intentional.

v4: 
  Main change is domain specific event assignment.
  Kept the ABMC feature as a default.
  Dynamcic switching between ABMC and mbm_legacy is still allowed.
  We are still not clear about mount option.
  Moved the monitoring related data in resctrl_mon structure from rdt_resource.
  Fixed the display of legacy and ABMC mode.
  Used bimap APIs when possible.
  Removed event configuration read from MSRs. We can use the
  internal saved data.(patch 12)
  Added more comments about L3_QOS_ABMC_CFG MSR.
  Added IPIs to read the assignment status for each domain (patch 18 and 19)
  More details in each patch.

v3:
   This series adds the support for global assignment mode discussed in
   the thread. https://lore.kernel.org/lkml/20231201005720.235639-1-babu.moger@amd.com/
   Removed the individual assignment mode and included the global assignment interface.
   Added following interface files.
   a. /sys/fs/resctrl/info/L3_MON/mbm_assign
      Used for displaying the current assignment mode and switch between
      ABMC and legacy mode.
   b. /sys/fs/resctrl/info/L3_MON/mbm_assign_control
      Used for lising the groups assignment mode and modify the assignment states.
   c. Most of the changes are related to the new interface.
   d. Addressed the comments from Reinette, James and Peter.
   e. Hope I have addressed most of the major feedbacks discussed. If I missed
      something then it is not intentional. Please feel free to comment.
   f. Sending this as an RFC as per Reinette's comment. So, this is still open
      for discussion.

v2:
   a. Major change is the way ABMC is enabled. Earlier, user needed to remount
      with -o abmc to enable ABMC feature. Removed that option now.
      Now users can enable ABMC by "$echo 1 to /sys/fs/resctrl/info/L3_MON/mbm_assign_enable".
     
   b. Added new word 21 to x86/cpufeatures.h.

   c. Display unsupported if user attempts to read the events when ABMC is enabled
      and event is not assigned.

   d. Display monitor_state as "Unsupported" when ABMC is disabled.
  
   e. Text updates and rebase to latest tip tree (as of Jan 18).
 
   f. This series is still work in progress. I am yet to hear from ARM developers. 

---------------------------------------------------------------------------------

Previous revisions:
v17: https://lore.kernel.org/lkml/cover.1755224735.git.babu.moger@amd.com/
v16: https://lore.kernel.org/lkml/cover.1753467772.git.babu.moger@amd.com/
v15: https://lore.kernel.org/lkml/cover.1752013061.git.babu.moger@amd.com/
v14: https://lore.kernel.org/lkml/cover.1749848714.git.babu.moger@amd.com/
v13: https://lore.kernel.org/lkml/cover.1747349530.git.babu.moger@amd.com/
v12: https://lore.kernel.org/lkml/cover.1743725907.git.babu.moger@amd.com/
v11: https://lore.kernel.org/lkml/cover.1737577229.git.babu.moger@amd.com/
v10: https://lore.kernel.org/lkml/cover.1734034524.git.babu.moger@amd.com/
v9: https://lore.kernel.org/lkml/cover.1730244116.git.babu.moger@amd.com/
v8: https://lore.kernel.org/lkml/cover.1728495588.git.babu.moger@amd.com/
v7: https://lore.kernel.org/lkml/cover.1725488488.git.babu.moger@amd.com/
v6: https://lore.kernel.org/lkml/cover.1722981659.git.babu.moger@amd.com/
v5: https://lore.kernel.org/lkml/cover.1720043311.git.babu.moger@amd.com/
v4: https://lore.kernel.org/lkml/cover.1716552602.git.babu.moger@amd.com/
v3: https://lore.kernel.org/lkml/cover.1711674410.git.babu.moger@amd.com/  
v2: https://lore.kernel.org/lkml/20231201005720.235639-1-babu.moger@amd.com/
v1: https://lore.kernel.org/lkml/20231201005720.235639-1-babu.moger@amd.com/

----------------------------------------------------------------------------

Babu Moger (29):
  x86/cpufeatures: Add support for Assignable Bandwidth Monitoring
    Counters (ABMC)
  x86/resctrl: Add ABMC feature in the command line options
  x86,fs/resctrl: Consolidate monitoring related data from rdt_resource
  x86,fs/resctrl: Detect Assignable Bandwidth Monitoring feature details
  x86/resctrl: Add support to enable/disable AMD ABMC feature
  fs/resctrl: Introduce the interface to display monitoring modes
  fs/resctrl: Add resctrl file to display number of assignable counters
  fs/resctrl: Introduce mbm_cntr_cfg to track assignable counters per
    domain
  fs/resctrl: Introduce interface to display number of free MBM counters
  x86/resctrl: Add data structures and definitions for ABMC assignment
  fs/resctrl: Introduce event configuration field in struct mon_evt
  x86,fs/resctrl: Implement resctrl_arch_config_cntr() to assign a
    counter with ABMC
  fs/resctrl: Add the functionality to assign MBM events
  fs/resctrl: Add the functionality to unassign MBM events
  fs/resctrl: Pass struct rdtgroup instead of individual members
  fs/resctrl: Introduce counter ID read, reset calls in mbm_event mode
  x86/resctrl: Refactor resctrl_arch_rmid_read()
  x86/resctrl: Implement resctrl_arch_reset_cntr() and
    resctrl_arch_cntr_read()
  fs/resctrl: Support counter read/reset with mbm_event assignment mode
  fs/resctrl: Add event configuration directory under info/L3_MON/
  fs/resctrl: Provide interface to update the event configurations
  fs/resctrl: Introduce mbm_assign_on_mkdir to enable assignments on
    mkdir
  fs/resctrl: Auto assign counters on mkdir and clean up on group
    removal
  fs/resctrl: Introduce mbm_L3_assignments to list assignments in a
    group
  fs/resctrl: Introduce the interface to modify assignments in a group
  fs/resctrl: Disable BMEC event configuration when mbm_event mode is
    enabled
  fs/resctrl: Introduce the interface to switch between monitor modes
  x86/resctrl: Configure mbm_event mode if supported
  MAINTAINERS: resctrl: add myself as reviewer

Tony Luck (4):
  x86,fs/resctrl: Consolidate monitor event descriptions
  x86,fs/resctrl: Replace architecture event enabled checks
  x86/resctrl: Remove 'rdt_mon_features' global variable
  x86,fs/resctrl: Prepare for more monitor events

 .../admin-guide/kernel-parameters.txt         |    2 +-
 Documentation/filesystems/resctrl.rst         |  325 ++++++
 MAINTAINERS                                   |    1 +
 arch/x86/include/asm/cpufeatures.h            |    1 +
 arch/x86/include/asm/msr-index.h              |    2 +
 arch/x86/include/asm/resctrl.h                |   16 -
 arch/x86/kernel/cpu/resctrl/core.c            |   81 +-
 arch/x86/kernel/cpu/resctrl/internal.h        |   56 +-
 arch/x86/kernel/cpu/resctrl/monitor.c         |  248 +++-
 arch/x86/kernel/cpu/scattered.c               |    1 +
 fs/resctrl/ctrlmondata.c                      |   26 +-
 fs/resctrl/internal.h                         |   58 +-
 fs/resctrl/monitor.c                          | 1008 ++++++++++++++++-
 fs/resctrl/rdtgroup.c                         |  252 ++++-
 include/linux/resctrl.h                       |  148 ++-
 include/linux/resctrl_types.h                 |   18 +-
 16 files changed, 2019 insertions(+), 224 deletions(-)

---

## [2] Babu Moger — 2025-09-05
*Subject: [PATCH v18 01/33] x86,fs/resctrl: Consolidate monitor event descriptions*

From: Tony Luck <tony.luck@intel.com>

There are currently only three monitor events, all associated with
the RDT_RESOURCE_L3 resource. Growing support for additional events
will be easier with some restructuring to have a single point in
file system code where all attributes of all events are defined.

Place all event descriptions into an array mon_event_all[]. Doing
this has the beneficial side effect of removing the need for
rdt_resource::evt_list.

Add resctrl_event_id::QOS_FIRST_EVENT for a lower bound on range
checks for event ids and as the starting index to scan mon_event_all[].

Drop the code that builds evt_list and change the two places where
the list is scanned to scan mon_event_all[] instead using a new
helper macro for_each_mon_event().

Architecture code now informs file system code which events are
available with resctrl_enable_mon_event().

Signed-off-by: Tony Luck <tony.luck@intel.com>
Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Fenghua Yu <fenghuay@nvidia.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: No changes.

v17: Added Signed-off-by tag.

Picked up first four patches from:
https://lore.kernel.org/lkml/20250711235341.113933-1-tony.luck@intel.com/
These patches have already been reviewed.
---
 arch/x86/kernel/cpu/resctrl/core.c | 12 ++++--
 fs/resctrl/internal.h              | 13 ++++--
 fs/resctrl/monitor.c               | 63 +++++++++++++++---------------
 fs/resctrl/rdtgroup.c              | 11 +++---
 include/linux/resctrl.h            |  4 +-
 include/linux/resctrl_types.h      | 12 ++++--
 6 files changed, 66 insertions(+), 49 deletions(-)

diff --git a/arch/x86/kernel/cpu/resctrl/core.c b/arch/x86/kernel/cpu/resctrl/core.c
index 187d527ef73b..7fcae25874fe 100644
--- a/arch/x86/kernel/cpu/resctrl/core.c
+++ b/arch/x86/kernel/cpu/resctrl/core.c
@@ -864,12 +864,18 @@ static __init bool get_rdt_mon_resources(void)
 {
 	struct rdt_resource *r = &rdt_resources_all[RDT_RESOURCE_L3].r_resctrl;
 
-	if (rdt_cpu_has(X86_FEATURE_CQM_OCCUP_LLC))
+	if (rdt_cpu_has(X86_FEATURE_CQM_OCCUP_LLC)) {
+		resctrl_enable_mon_event(QOS_L3_OCCUP_EVENT_ID);
 		rdt_mon_features |= (1 << QOS_L3_OCCUP_EVENT_ID);
-	if (rdt_cpu_has(X86_FEATURE_CQM_MBM_TOTAL))
+	}
+	if (rdt_cpu_has(X86_FEATURE_CQM_MBM_TOTAL)) {
+		resctrl_enable_mon_event(QOS_L3_MBM_TOTAL_EVENT_ID);
 		rdt_mon_features |= (1 << QOS_L3_MBM_TOTAL_EVENT_ID);
-	if (rdt_cpu_has(X86_FEATURE_CQM_MBM_LOCAL))
+	}
+	if (rdt_cpu_has(X86_FEATURE_CQM_MBM_LOCAL)) {
+		resctrl_enable_mon_event(QOS_L3_MBM_LOCAL_EVENT_ID);
 		rdt_mon_features |= (1 << QOS_L3_MBM_LOCAL_EVENT_ID);
+	}
 
 	if (!rdt_mon_features)
 		return false;
diff --git a/fs/resctrl/internal.h b/fs/resctrl/internal.h
index 0a1eedba2b03..4f315b7e9ec0 100644
--- a/fs/resctrl/internal.h
+++ b/fs/resctrl/internal.h
@@ -52,19 +52,26 @@ static inline struct rdt_fs_context *rdt_fc2context(struct fs_context *fc)
 }
 
 /**
- * struct mon_evt - Entry in the event list of a resource
+ * struct mon_evt - Properties of a monitor event
  * @evtid:		event id
+ * @rid:		resource id for this event
  * @name:		name of the event
  * @configurable:	true if the event is configurable
- * @list:		entry in &rdt_resource->evt_list
+ * @enabled:		true if the event is enabled
  */
 struct mon_evt {
 	enum resctrl_event_id	evtid;
+	enum resctrl_res_level	rid;
 	char			*name;
 	bool			configurable;
-	struct list_head	list;
+	bool			enabled;
 };
 
+extern struct mon_evt mon_event_all[QOS_NUM_EVENTS];
+
+#define for_each_mon_event(mevt) for (mevt = &mon_event_all[QOS_FIRST_EVENT];	\
+				      mevt < &mon_event_all[QOS_NUM_EVENTS]; mevt++)
+
 /**
  * struct mon_data - Monitoring details for each event file.
  * @list:            Member of the global @mon_data_kn_priv_list list.
diff --git a/fs/resctrl/monitor.c b/fs/resctrl/monitor.c
index f5637855c3ac..2313e48de55f 100644
--- a/fs/resctrl/monitor.c
+++ b/fs/resctrl/monitor.c
@@ -844,38 +844,39 @@ static void dom_data_exit(struct rdt_resource *r)
 	mutex_unlock(&rdtgroup_mutex);
 }
 
-static struct mon_evt llc_occupancy_event = {
-	.name		= "llc_occupancy",
-	.evtid		= QOS_L3_OCCUP_EVENT_ID,
-};
-
-static struct mon_evt mbm_total_event = {
-	.name		= "mbm_total_bytes",
-	.evtid		= QOS_L3_MBM_TOTAL_EVENT_ID,
-};
-
-static struct mon_evt mbm_local_event = {
-	.name		= "mbm_local_bytes",
-	.evtid		= QOS_L3_MBM_LOCAL_EVENT_ID,
-};
-
 /*
- * Initialize the event list for the resource.
- *
- * Note that MBM events are also part of RDT_RESOURCE_L3 resource
- * because as per the SDM the total and local memory bandwidth
- * are enumerated as part of L3 monitoring.
+ * All available events. Architecture code marks the ones that
+ * are supported by a system using resctrl_enable_mon_event()
+ * to set .enabled.
  */
-static void l3_mon_evt_init(struct rdt_resource *r)
+struct mon_evt mon_event_all[QOS_NUM_EVENTS] = {
+	[QOS_L3_OCCUP_EVENT_ID] = {
+		.name	= "llc_occupancy",
+		.evtid	= QOS_L3_OCCUP_EVENT_ID,
+		.rid	= RDT_RESOURCE_L3,
+	},
+	[QOS_L3_MBM_TOTAL_EVENT_ID] = {
+		.name	= "mbm_total_bytes",
+		.evtid	= QOS_L3_MBM_TOTAL_EVENT_ID,
+		.rid	= RDT_RESOURCE_L3,
+	},
+	[QOS_L3_MBM_LOCAL_EVENT_ID] = {
+		.name	= "mbm_local_bytes",
+		.evtid	= QOS_L3_MBM_LOCAL_EVENT_ID,
+		.rid	= RDT_RESOURCE_L3,
+	},
+};
+
+void resctrl_enable_mon_event(enum resctrl_event_id eventid)
 {
-	INIT_LIST_HEAD(&r->evt_list);
+	if (WARN_ON_ONCE(eventid < QOS_FIRST_EVENT || eventid >= QOS_NUM_EVENTS))
+		return;
+	if (mon_event_all[eventid].enabled) {
+		pr_warn("Duplicate enable for event %d\n", eventid);
+		return;
+	}
 
-	if (resctrl_arch_is_llc_occupancy_enabled())
-		list_add_tail(&llc_occupancy_event.list, &r->evt_list);
-	if (resctrl_arch_is_mbm_total_enabled())
-		list_add_tail(&mbm_total_event.list, &r->evt_list);
-	if (resctrl_arch_is_mbm_local_enabled())
-		list_add_tail(&mbm_local_event.list, &r->evt_list);
+	mon_event_all[eventid].enabled = true;
 }
 
 /**
@@ -902,15 +903,13 @@ int resctrl_mon_resource_init(void)
 	if (ret)
 		return ret;
 
-	l3_mon_evt_init(r);
-
 	if (resctrl_arch_is_evt_configurable(QOS_L3_MBM_TOTAL_EVENT_ID)) {
-		mbm_total_event.configurable = true;
+		mon_event_all[QOS_L3_MBM_TOTAL_EVENT_ID].configurable = true;
 		resctrl_file_fflags_init("mbm_total_bytes_config",
 					 RFTYPE_MON_INFO | RFTYPE_RES_CACHE);
 	}
 	if (resctrl_arch_is_evt_configurable(QOS_L3_MBM_LOCAL_EVENT_ID)) {
-		mbm_local_event.configurable = true;
+		mon_event_all[QOS_L3_MBM_LOCAL_EVENT_ID].configurable = true;
 		resctrl_file_fflags_init("mbm_local_bytes_config",
 					 RFTYPE_MON_INFO | RFTYPE_RES_CACHE);
 	}
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index 5f0b7cfa1cc2..ab943a5907c5 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -1152,7 +1152,9 @@ static int rdt_mon_features_show(struct kernfs_open_file *of,
 	struct rdt_resource *r = rdt_kn_parent_priv(of->kn);
 	struct mon_evt *mevt;
 
-	list_for_each_entry(mevt, &r->evt_list, list) {
+	for_each_mon_event(mevt) {
+		if (mevt->rid != r->rid || !mevt->enabled)
+			continue;
 		seq_printf(seq, "%s\n", mevt->name);
 		if (mevt->configurable)
 			seq_printf(seq, "%s_config\n", mevt->name);
@@ -3054,10 +3056,9 @@ static int mon_add_all_files(struct kernfs_node *kn, struct rdt_mon_domain *d,
 	struct mon_evt *mevt;
 	int ret, domid;
 
-	if (WARN_ON(list_empty(&r->evt_list)))
-		return -EPERM;
-
-	list_for_each_entry(mevt, &r->evt_list, list) {
+	for_each_mon_event(mevt) {
+		if (mevt->rid != r->rid || !mevt->enabled)
+			continue;
 		domid = do_sum ? d->ci_id : d->hdr.id;
 		priv = mon_get_kn_priv(r->rid, domid, mevt, do_sum);
 		if (WARN_ON_ONCE(!priv))
diff --git a/include/linux/resctrl.h b/include/linux/resctrl.h
index 6fb4894b8cfd..2944042bd84c 100644
--- a/include/linux/resctrl.h
+++ b/include/linux/resctrl.h
@@ -269,7 +269,6 @@ enum resctrl_schema_fmt {
  * @mon_domains:	RCU list of all monitor domains for this resource
  * @name:		Name to use in "schemata" file.
  * @schema_fmt:		Which format string and parser is used for this schema.
- * @evt_list:		List of monitoring events
  * @mbm_cfg_mask:	Bandwidth sources that can be tracked when bandwidth
  *			monitoring events can be configured.
  * @cdp_capable:	Is the CDP feature available on this resource
@@ -287,7 +286,6 @@ struct rdt_resource {
 	struct list_head	mon_domains;
 	char			*name;
 	enum resctrl_schema_fmt	schema_fmt;
-	struct list_head	evt_list;
 	unsigned int		mbm_cfg_mask;
 	bool			cdp_capable;
 };
@@ -372,6 +370,8 @@ u32 resctrl_arch_get_num_closid(struct rdt_resource *r);
 u32 resctrl_arch_system_num_rmid_idx(void);
 int resctrl_arch_update_domains(struct rdt_resource *r, u32 closid);
 
+void resctrl_enable_mon_event(enum resctrl_event_id eventid);
+
 bool resctrl_arch_is_evt_configurable(enum resctrl_event_id evt);
 
 /**
diff --git a/include/linux/resctrl_types.h b/include/linux/resctrl_types.h
index a25fb9c4070d..2dadbc54e4b3 100644
--- a/include/linux/resctrl_types.h
+++ b/include/linux/resctrl_types.h
@@ -34,11 +34,15 @@
 /* Max event bits supported */
 #define MAX_EVT_CONFIG_BITS		GENMASK(6, 0)
 
-/*
- * Event IDs, the values match those used to program IA32_QM_EVTSEL before
- * reading IA32_QM_CTR on RDT systems.
- */
+/* Event IDs */
 enum resctrl_event_id {
+	/* Must match value of first event below */
+	QOS_FIRST_EVENT			= 0x01,
+
+	/*
+	 * These values match those used to program IA32_QM_EVTSEL before
+	 * reading IA32_QM_CTR on RDT systems.
+	 */
 	QOS_L3_OCCUP_EVENT_ID		= 0x01,
 	QOS_L3_MBM_TOTAL_EVENT_ID	= 0x02,
 	QOS_L3_MBM_LOCAL_EVENT_ID	= 0x03,

---

## [3] Babu Moger — 2025-09-05
*Subject: [PATCH v18 02/33] x86,fs/resctrl: Replace architecture event enabled checks*

From: Tony Luck <tony.luck@intel.com>

The resctrl file system now has complete knowledge of the status
of every event. So there is no need for per-event function calls
to check.

Replace each of the resctrl_arch_is_{event}enabled() calls with
resctrl_is_mon_event_enabled(QOS_{EVENT}).

No functional change.

Signed-off-by: Tony Luck <tony.luck@intel.com>
Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Fenghua Yu <fenghuay@nvidia.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v17: Addred Signed-off-by tag.

Picked up first four patches from:
https://lore.kernel.org/lkml/20250711235341.113933-1-tony.luck@intel.com/
These patches have already been reviewed.
---
 arch/x86/include/asm/resctrl.h        | 15 ---------------
 arch/x86/kernel/cpu/resctrl/core.c    |  4 ++--
 arch/x86/kernel/cpu/resctrl/monitor.c |  4 ++--
 fs/resctrl/ctrlmondata.c              |  4 ++--
 fs/resctrl/monitor.c                  | 16 +++++++++++-----
 fs/resctrl/rdtgroup.c                 | 18 +++++++++---------
 include/linux/resctrl.h               |  2 ++
 7 files changed, 28 insertions(+), 35 deletions(-)

diff --git a/arch/x86/include/asm/resctrl.h b/arch/x86/include/asm/resctrl.h
index feb93b50e990..b1dd5d6b87db 100644
--- a/arch/x86/include/asm/resctrl.h
+++ b/arch/x86/include/asm/resctrl.h
@@ -84,21 +84,6 @@ static inline void resctrl_arch_disable_mon(void)
 	static_branch_dec_cpuslocked(&rdt_enable_key);
 }
 
-static inline bool resctrl_arch_is_llc_occupancy_enabled(void)
-{
-	return (rdt_mon_features & (1 << QOS_L3_OCCUP_EVENT_ID));
-}
-
-static inline bool resctrl_arch_is_mbm_total_enabled(void)
-{
-	return (rdt_mon_features & (1 << QOS_L3_MBM_TOTAL_EVENT_ID));
-}
-
-static inline bool resctrl_arch_is_mbm_local_enabled(void)
-{
-	return (rdt_mon_features & (1 << QOS_L3_MBM_LOCAL_EVENT_ID));
-}
-
 /*
  * __resctrl_sched_in() - Writes the task's CLOSid/RMID to IA32_PQR_MSR
  *
diff --git a/arch/x86/kernel/cpu/resctrl/core.c b/arch/x86/kernel/cpu/resctrl/core.c
index 7fcae25874fe..1a319ce9328c 100644
--- a/arch/x86/kernel/cpu/resctrl/core.c
+++ b/arch/x86/kernel/cpu/resctrl/core.c
@@ -402,13 +402,13 @@ static int arch_domain_mbm_alloc(u32 num_rmid, struct rdt_hw_mon_domain *hw_dom)
 {
 	size_t tsize;
 
-	if (resctrl_arch_is_mbm_total_enabled()) {
+	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID)) {
 		tsize = sizeof(*hw_dom->arch_mbm_total);
 		hw_dom->arch_mbm_total = kcalloc(num_rmid, tsize, GFP_KERNEL);
 		if (!hw_dom->arch_mbm_total)
 			return -ENOMEM;
 	}
-	if (resctrl_arch_is_mbm_local_enabled()) {
+	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_LOCAL_EVENT_ID)) {
 		tsize = sizeof(*hw_dom->arch_mbm_local);
 		hw_dom->arch_mbm_local = kcalloc(num_rmid, tsize, GFP_KERNEL);
 		if (!hw_dom->arch_mbm_local) {
diff --git a/arch/x86/kernel/cpu/resctrl/monitor.c b/arch/x86/kernel/cpu/resctrl/monitor.c
index c261558276cd..61d38517e2bf 100644
--- a/arch/x86/kernel/cpu/resctrl/monitor.c
+++ b/arch/x86/kernel/cpu/resctrl/monitor.c
@@ -207,11 +207,11 @@ void resctrl_arch_reset_rmid_all(struct rdt_resource *r, struct rdt_mon_domain *
 {
 	struct rdt_hw_mon_domain *hw_dom = resctrl_to_arch_mon_dom(d);
 
-	if (resctrl_arch_is_mbm_total_enabled())
+	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID))
 		memset(hw_dom->arch_mbm_total, 0,
 		       sizeof(*hw_dom->arch_mbm_total) * r->num_rmid);
 
-	if (resctrl_arch_is_mbm_local_enabled())
+	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_LOCAL_EVENT_ID))
 		memset(hw_dom->arch_mbm_local, 0,
 		       sizeof(*hw_dom->arch_mbm_local) * r->num_rmid);
 }
diff --git a/fs/resctrl/ctrlmondata.c b/fs/resctrl/ctrlmondata.c
index d98e0d2de09f..ad7ffc6acf13 100644
--- a/fs/resctrl/ctrlmondata.c
+++ b/fs/resctrl/ctrlmondata.c
@@ -473,12 +473,12 @@ ssize_t rdtgroup_mba_mbps_event_write(struct kernfs_open_file *of,
 	rdt_last_cmd_clear();
 
 	if (!strcmp(buf, "mbm_local_bytes")) {
-		if (resctrl_arch_is_mbm_local_enabled())
+		if (resctrl_is_mon_event_enabled(QOS_L3_MBM_LOCAL_EVENT_ID))
 			rdtgrp->mba_mbps_event = QOS_L3_MBM_LOCAL_EVENT_ID;
 		else
 			ret = -EINVAL;
 	} else if (!strcmp(buf, "mbm_total_bytes")) {
-		if (resctrl_arch_is_mbm_total_enabled())
+		if (resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID))
 			rdtgrp->mba_mbps_event = QOS_L3_MBM_TOTAL_EVENT_ID;
 		else
 			ret = -EINVAL;
diff --git a/fs/resctrl/monitor.c b/fs/resctrl/monitor.c
index 2313e48de55f..9e988b2c1a22 100644
--- a/fs/resctrl/monitor.c
+++ b/fs/resctrl/monitor.c
@@ -336,7 +336,7 @@ void free_rmid(u32 closid, u32 rmid)
 
 	entry = __rmid_entry(idx);
 
-	if (resctrl_arch_is_llc_occupancy_enabled())
+	if (resctrl_is_mon_event_enabled(QOS_L3_OCCUP_EVENT_ID))
 		add_rmid_to_limbo(entry);
 	else
 		list_add_tail(&entry->list, &rmid_free_lru);
@@ -637,10 +637,10 @@ static void mbm_update(struct rdt_resource *r, struct rdt_mon_domain *d,
 	 * This is protected from concurrent reads from user as both
 	 * the user and overflow handler hold the global mutex.
 	 */
-	if (resctrl_arch_is_mbm_total_enabled())
+	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID))
 		mbm_update_one_event(r, d, closid, rmid, QOS_L3_MBM_TOTAL_EVENT_ID);
 
-	if (resctrl_arch_is_mbm_local_enabled())
+	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_LOCAL_EVENT_ID))
 		mbm_update_one_event(r, d, closid, rmid, QOS_L3_MBM_LOCAL_EVENT_ID);
 }
 
@@ -879,6 +879,12 @@ void resctrl_enable_mon_event(enum resctrl_event_id eventid)
 	mon_event_all[eventid].enabled = true;
 }
 
+bool resctrl_is_mon_event_enabled(enum resctrl_event_id eventid)
+{
+	return eventid >= QOS_FIRST_EVENT && eventid < QOS_NUM_EVENTS &&
+	       mon_event_all[eventid].enabled;
+}
+
 /**
  * resctrl_mon_resource_init() - Initialise global monitoring structures.
  *
@@ -914,9 +920,9 @@ int resctrl_mon_resource_init(void)
 					 RFTYPE_MON_INFO | RFTYPE_RES_CACHE);
 	}
 
-	if (resctrl_arch_is_mbm_local_enabled())
+	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_LOCAL_EVENT_ID))
 		mba_mbps_default_event = QOS_L3_MBM_LOCAL_EVENT_ID;
-	else if (resctrl_arch_is_mbm_total_enabled())
+	else if (resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID))
 		mba_mbps_default_event = QOS_L3_MBM_TOTAL_EVENT_ID;
 
 	return 0;
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index ab943a5907c5..2ca8e66c0d20 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -123,8 +123,8 @@ void rdt_staged_configs_clear(void)
 
 static bool resctrl_is_mbm_enabled(void)
 {
-	return (resctrl_arch_is_mbm_total_enabled() ||
-		resctrl_arch_is_mbm_local_enabled());
+	return (resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID) ||
+		resctrl_is_mon_event_enabled(QOS_L3_MBM_LOCAL_EVENT_ID));
 }
 
 static bool resctrl_is_mbm_event(int e)
@@ -196,7 +196,7 @@ static int closid_alloc(void)
 	lockdep_assert_held(&rdtgroup_mutex);
 
 	if (IS_ENABLED(CONFIG_RESCTRL_RMID_DEPENDS_ON_CLOSID) &&
-	    resctrl_arch_is_llc_occupancy_enabled()) {
+	    resctrl_is_mon_event_enabled(QOS_L3_OCCUP_EVENT_ID)) {
 		cleanest_closid = resctrl_find_cleanest_closid();
 		if (cleanest_closid < 0)
 			return cleanest_closid;
@@ -4048,7 +4048,7 @@ void resctrl_offline_mon_domain(struct rdt_resource *r, struct rdt_mon_domain *d
 
 	if (resctrl_is_mbm_enabled())
 		cancel_delayed_work(&d->mbm_over);
-	if (resctrl_arch_is_llc_occupancy_enabled() && has_busy_rmid(d)) {
+	if (resctrl_is_mon_event_enabled(QOS_L3_OCCUP_EVENT_ID) && has_busy_rmid(d)) {
 		/*
 		 * When a package is going down, forcefully
 		 * decrement rmid->ebusy. There is no way to know
@@ -4084,12 +4084,12 @@ static int domain_setup_mon_state(struct rdt_resource *r, struct rdt_mon_domain
 	u32 idx_limit = resctrl_arch_system_num_rmid_idx();
 	size_t tsize;
 
-	if (resctrl_arch_is_llc_occupancy_enabled()) {
+	if (resctrl_is_mon_event_enabled(QOS_L3_OCCUP_EVENT_ID)) {
 		d->rmid_busy_llc = bitmap_zalloc(idx_limit, GFP_KERNEL);
 		if (!d->rmid_busy_llc)
 			return -ENOMEM;
 	}
-	if (resctrl_arch_is_mbm_total_enabled()) {
+	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID)) {
 		tsize = sizeof(*d->mbm_total);
 		d->mbm_total = kcalloc(idx_limit, tsize, GFP_KERNEL);
 		if (!d->mbm_total) {
@@ -4097,7 +4097,7 @@ static int domain_setup_mon_state(struct rdt_resource *r, struct rdt_mon_domain
 			return -ENOMEM;
 		}
 	}
-	if (resctrl_arch_is_mbm_local_enabled()) {
+	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_LOCAL_EVENT_ID)) {
 		tsize = sizeof(*d->mbm_local);
 		d->mbm_local = kcalloc(idx_limit, tsize, GFP_KERNEL);
 		if (!d->mbm_local) {
@@ -4142,7 +4142,7 @@ int resctrl_online_mon_domain(struct rdt_resource *r, struct rdt_mon_domain *d)
 					   RESCTRL_PICK_ANY_CPU);
 	}
 
-	if (resctrl_arch_is_llc_occupancy_enabled())
+	if (resctrl_is_mon_event_enabled(QOS_L3_OCCUP_EVENT_ID))
 		INIT_DELAYED_WORK(&d->cqm_limbo, cqm_handle_limbo);
 
 	/*
@@ -4217,7 +4217,7 @@ void resctrl_offline_cpu(unsigned int cpu)
 			cancel_delayed_work(&d->mbm_over);
 			mbm_setup_overflow_handler(d, 0, cpu);
 		}
-		if (resctrl_arch_is_llc_occupancy_enabled() &&
+		if (resctrl_is_mon_event_enabled(QOS_L3_OCCUP_EVENT_ID) &&
 		    cpu == d->cqm_work_cpu && has_busy_rmid(d)) {
 			cancel_delayed_work(&d->cqm_limbo);
 			cqm_setup_limbo_handler(d, 0, cpu);
diff --git a/include/linux/resctrl.h b/include/linux/resctrl.h
index 2944042bd84c..40aba6b5d4f0 100644
--- a/include/linux/resctrl.h
+++ b/include/linux/resctrl.h
@@ -372,6 +372,8 @@ int resctrl_arch_update_domains(struct rdt_resource *r, u32 closid);
 
 void resctrl_enable_mon_event(enum resctrl_event_id eventid);
 
+bool resctrl_is_mon_event_enabled(enum resctrl_event_id eventid);
+
 bool resctrl_arch_is_evt_configurable(enum resctrl_event_id evt);
 
 /**

---

## [4] Babu Moger — 2025-09-05
*Subject: [PATCH v18 03/33] x86/resctrl: Remove 'rdt_mon_features' global variable*

From: Tony Luck <tony.luck@intel.com>

rdt_mon_features is used as a bitmask of enabled monitor events. A monitor
event's status is now maintained in mon_evt::enabled with all monitor
events' mon_evt structures found in the filesystem's mon_event_all[] array.

Remove the remaining uses of rdt_mon_features.

Signed-off-by: Tony Luck <tony.luck@intel.com>
Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: No changes

v17: Added Signed-off-by tag;

Picked up first four patches from:
https://lore.kernel.org/lkml/20250711235341.113933-1-tony.luck@intel.com/
These patches have already been reviewed.
---
 arch/x86/include/asm/resctrl.h        | 1 -
 arch/x86/kernel/cpu/resctrl/core.c    | 9 +++++----
 arch/x86/kernel/cpu/resctrl/monitor.c | 5 -----
 3 files changed, 5 insertions(+), 10 deletions(-)

diff --git a/arch/x86/include/asm/resctrl.h b/arch/x86/include/asm/resctrl.h
index b1dd5d6b87db..575f8408a9e7 100644
--- a/arch/x86/include/asm/resctrl.h
+++ b/arch/x86/include/asm/resctrl.h
@@ -44,7 +44,6 @@ DECLARE_PER_CPU(struct resctrl_pqr_state, pqr_state);
 
 extern bool rdt_alloc_capable;
 extern bool rdt_mon_capable;
-extern unsigned int rdt_mon_features;
 
 DECLARE_STATIC_KEY_FALSE(rdt_enable_key);
 DECLARE_STATIC_KEY_FALSE(rdt_alloc_enable_key);
diff --git a/arch/x86/kernel/cpu/resctrl/core.c b/arch/x86/kernel/cpu/resctrl/core.c
index 1a319ce9328c..5d14f9a14eda 100644
--- a/arch/x86/kernel/cpu/resctrl/core.c
+++ b/arch/x86/kernel/cpu/resctrl/core.c
@@ -863,21 +863,22 @@ static __init bool get_rdt_alloc_resources(void)
 static __init bool get_rdt_mon_resources(void)
 {
 	struct rdt_resource *r = &rdt_resources_all[RDT_RESOURCE_L3].r_resctrl;
+	bool ret = false;
 
 	if (rdt_cpu_has(X86_FEATURE_CQM_OCCUP_LLC)) {
 		resctrl_enable_mon_event(QOS_L3_OCCUP_EVENT_ID);
-		rdt_mon_features |= (1 << QOS_L3_OCCUP_EVENT_ID);
+		ret = true;
 	}
 	if (rdt_cpu_has(X86_FEATURE_CQM_MBM_TOTAL)) {
 		resctrl_enable_mon_event(QOS_L3_MBM_TOTAL_EVENT_ID);
-		rdt_mon_features |= (1 << QOS_L3_MBM_TOTAL_EVENT_ID);
+		ret = true;
 	}
 	if (rdt_cpu_has(X86_FEATURE_CQM_MBM_LOCAL)) {
 		resctrl_enable_mon_event(QOS_L3_MBM_LOCAL_EVENT_ID);
-		rdt_mon_features |= (1 << QOS_L3_MBM_LOCAL_EVENT_ID);
+		ret = true;
 	}
 
-	if (!rdt_mon_features)
+	if (!ret)
 		return false;
 
 	return !rdt_get_mon_l3_config(r);
diff --git a/arch/x86/kernel/cpu/resctrl/monitor.c b/arch/x86/kernel/cpu/resctrl/monitor.c
index 61d38517e2bf..07f8ab097cbe 100644
--- a/arch/x86/kernel/cpu/resctrl/monitor.c
+++ b/arch/x86/kernel/cpu/resctrl/monitor.c
@@ -31,11 +31,6 @@
  */
 bool rdt_mon_capable;
 
-/*
- * Global to indicate which monitoring events are enabled.
- */
-unsigned int rdt_mon_features;
-
 #define CF(cf)	((unsigned long)(1048576 * (cf) + 0.5))
 
 static int snc_nodes_per_l3_cache = 1;

---

## [5] Babu Moger — 2025-09-05
*Subject: [PATCH v18 04/33] x86,fs/resctrl: Prepare for more monitor events*

From: Tony Luck <tony.luck@intel.com>

There's a rule in computer programming that objects appear zero,
once, or many times. So code accordingly.

There are two MBM events and resctrl is coded with a lot of

        if (local)
                do one thing
        if (total)
                do a different thing

Change the rdt_mon_domain and rdt_hw_mon_domain structures to hold arrays
of pointers to per event data instead of explicit fields for total and
local bandwidth.

Simplify by coding for many events using loops on which are enabled.

Move resctrl_is_mbm_event() to <linux/resctrl.h> so it can be used more
widely. Also provide a for_each_mbm_event_id() helper macro.

Cleanup variable names in functions touched to consistently use
"eventid" for those with type enum resctrl_event_id.

Signed-off-by: Tony Luck <tony.luck@intel.com>
Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: No changes

v17: Added Signed-off-by tag.

Picked up first four patches from:
https://lore.kernel.org/lkml/20250711235341.113933-1-tony.luck@intel.com/
These patches have already been reviewed.
---
 arch/x86/kernel/cpu/resctrl/core.c     | 40 +++++++++++----------
 arch/x86/kernel/cpu/resctrl/internal.h |  8 ++---
 arch/x86/kernel/cpu/resctrl/monitor.c  | 36 +++++++++----------
 fs/resctrl/monitor.c                   | 13 ++++---
 fs/resctrl/rdtgroup.c                  | 50 +++++++++++++-------------
 include/linux/resctrl.h                | 23 +++++++++---
 include/linux/resctrl_types.h          |  3 ++
 7 files changed, 96 insertions(+), 77 deletions(-)

diff --git a/arch/x86/kernel/cpu/resctrl/core.c b/arch/x86/kernel/cpu/resctrl/core.c
index 5d14f9a14eda..fbf019c1ff11 100644
--- a/arch/x86/kernel/cpu/resctrl/core.c
+++ b/arch/x86/kernel/cpu/resctrl/core.c
@@ -365,8 +365,10 @@ static void ctrl_domain_free(struct rdt_hw_ctrl_domain *hw_dom)
 
 static void mon_domain_free(struct rdt_hw_mon_domain *hw_dom)
 {
-	kfree(hw_dom->arch_mbm_total);
-	kfree(hw_dom->arch_mbm_local);
+	int idx;
+
+	for_each_mbm_idx(idx)
+		kfree(hw_dom->arch_mbm_states[idx]);
 	kfree(hw_dom);
 }
 
@@ -400,25 +402,27 @@ static int domain_setup_ctrlval(struct rdt_resource *r, struct rdt_ctrl_domain *
  */
 static int arch_domain_mbm_alloc(u32 num_rmid, struct rdt_hw_mon_domain *hw_dom)
 {
-	size_t tsize;
-
-	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID)) {
-		tsize = sizeof(*hw_dom->arch_mbm_total);
-		hw_dom->arch_mbm_total = kcalloc(num_rmid, tsize, GFP_KERNEL);
-		if (!hw_dom->arch_mbm_total)
-			return -ENOMEM;
-	}
-	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_LOCAL_EVENT_ID)) {
-		tsize = sizeof(*hw_dom->arch_mbm_local);
-		hw_dom->arch_mbm_local = kcalloc(num_rmid, tsize, GFP_KERNEL);
-		if (!hw_dom->arch_mbm_local) {
-			kfree(hw_dom->arch_mbm_total);
-			hw_dom->arch_mbm_total = NULL;
-			return -ENOMEM;
-		}
+	size_t tsize = sizeof(*hw_dom->arch_mbm_states[0]);
+	enum resctrl_event_id eventid;
+	int idx;
+
+	for_each_mbm_event_id(eventid) {
+		if (!resctrl_is_mon_event_enabled(eventid))
+			continue;
+		idx = MBM_STATE_IDX(eventid);
+		hw_dom->arch_mbm_states[idx] = kcalloc(num_rmid, tsize, GFP_KERNEL);
+		if (!hw_dom->arch_mbm_states[idx])
+			goto cleanup;
 	}
 
 	return 0;
+cleanup:
+	for_each_mbm_idx(idx) {
+		kfree(hw_dom->arch_mbm_states[idx]);
+		hw_dom->arch_mbm_states[idx] = NULL;
+	}
+
+	return -ENOMEM;
 }
 
 static int get_domain_id_from_scope(int cpu, enum resctrl_scope scope)
diff --git a/arch/x86/kernel/cpu/resctrl/internal.h b/arch/x86/kernel/cpu/resctrl/internal.h
index 5e3c41b36437..58dca892a5df 100644
--- a/arch/x86/kernel/cpu/resctrl/internal.h
+++ b/arch/x86/kernel/cpu/resctrl/internal.h
@@ -54,15 +54,15 @@ struct rdt_hw_ctrl_domain {
  * struct rdt_hw_mon_domain - Arch private attributes of a set of CPUs that share
  *			      a resource for a monitor function
  * @d_resctrl:	Properties exposed to the resctrl file system
- * @arch_mbm_total:	arch private state for MBM total bandwidth
- * @arch_mbm_local:	arch private state for MBM local bandwidth
+ * @arch_mbm_states:	Per-event pointer to the MBM event's saved state.
+ *			An MBM event's state is an array of struct arch_mbm_state
+ *			indexed by RMID on x86.
  *
  * Members of this structure are accessed via helpers that provide abstraction.
  */
 struct rdt_hw_mon_domain {
 	struct rdt_mon_domain		d_resctrl;
-	struct arch_mbm_state		*arch_mbm_total;
-	struct arch_mbm_state		*arch_mbm_local;
+	struct arch_mbm_state		*arch_mbm_states[QOS_NUM_L3_MBM_EVENTS];
 };
 
 static inline struct rdt_hw_ctrl_domain *resctrl_to_arch_ctrl_dom(struct rdt_ctrl_domain *r)
diff --git a/arch/x86/kernel/cpu/resctrl/monitor.c b/arch/x86/kernel/cpu/resctrl/monitor.c
index 07f8ab097cbe..f01db2034d08 100644
--- a/arch/x86/kernel/cpu/resctrl/monitor.c
+++ b/arch/x86/kernel/cpu/resctrl/monitor.c
@@ -161,18 +161,14 @@ static struct arch_mbm_state *get_arch_mbm_state(struct rdt_hw_mon_domain *hw_do
 						 u32 rmid,
 						 enum resctrl_event_id eventid)
 {
-	switch (eventid) {
-	case QOS_L3_OCCUP_EVENT_ID:
-		return NULL;
-	case QOS_L3_MBM_TOTAL_EVENT_ID:
-		return &hw_dom->arch_mbm_total[rmid];
-	case QOS_L3_MBM_LOCAL_EVENT_ID:
-		return &hw_dom->arch_mbm_local[rmid];
-	default:
-		/* Never expect to get here */
-		WARN_ON_ONCE(1);
+	struct arch_mbm_state *state;
+
+	if (!resctrl_is_mbm_event(eventid))
 		return NULL;
-	}
+
+	state = hw_dom->arch_mbm_states[MBM_STATE_IDX(eventid)];
+
+	return state ? &state[rmid] : NULL;
 }
 
 void resctrl_arch_reset_rmid(struct rdt_resource *r, struct rdt_mon_domain *d,
@@ -201,14 +197,16 @@ void resctrl_arch_reset_rmid(struct rdt_resource *r, struct rdt_mon_domain *d,
 void resctrl_arch_reset_rmid_all(struct rdt_resource *r, struct rdt_mon_domain *d)
 {
 	struct rdt_hw_mon_domain *hw_dom = resctrl_to_arch_mon_dom(d);
-
-	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID))
-		memset(hw_dom->arch_mbm_total, 0,
-		       sizeof(*hw_dom->arch_mbm_total) * r->num_rmid);
-
-	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_LOCAL_EVENT_ID))
-		memset(hw_dom->arch_mbm_local, 0,
-		       sizeof(*hw_dom->arch_mbm_local) * r->num_rmid);
+	enum resctrl_event_id eventid;
+	int idx;
+
+	for_each_mbm_event_id(eventid) {
+		if (!resctrl_is_mon_event_enabled(eventid))
+			continue;
+		idx = MBM_STATE_IDX(eventid);
+		memset(hw_dom->arch_mbm_states[idx], 0,
+		       sizeof(*hw_dom->arch_mbm_states[0]) * r->num_rmid);
+	}
 }
 
 static u64 mbm_overflow_count(u64 prev_msr, u64 cur_msr, unsigned int width)
diff --git a/fs/resctrl/monitor.c b/fs/resctrl/monitor.c
index 9e988b2c1a22..dcc6c00eb362 100644
--- a/fs/resctrl/monitor.c
+++ b/fs/resctrl/monitor.c
@@ -346,15 +346,14 @@ static struct mbm_state *get_mbm_state(struct rdt_mon_domain *d, u32 closid,
 				       u32 rmid, enum resctrl_event_id evtid)
 {
 	u32 idx = resctrl_arch_rmid_idx_encode(closid, rmid);
+	struct mbm_state *state;
 
-	switch (evtid) {
-	case QOS_L3_MBM_TOTAL_EVENT_ID:
-		return &d->mbm_total[idx];
-	case QOS_L3_MBM_LOCAL_EVENT_ID:
-		return &d->mbm_local[idx];
-	default:
+	if (!resctrl_is_mbm_event(evtid))
 		return NULL;
-	}
+
+	state = d->mbm_states[MBM_STATE_IDX(evtid)];
+
+	return state ? &state[idx] : NULL;
 }
 
 static int __mon_event_count(u32 closid, u32 rmid, struct rmid_read *rr)
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index 2ca8e66c0d20..a6047e9345cd 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -127,12 +127,6 @@ static bool resctrl_is_mbm_enabled(void)
 		resctrl_is_mon_event_enabled(QOS_L3_MBM_LOCAL_EVENT_ID));
 }
 
-static bool resctrl_is_mbm_event(int e)
-{
-	return (e >= QOS_L3_MBM_TOTAL_EVENT_ID &&
-		e <= QOS_L3_MBM_LOCAL_EVENT_ID);
-}
-
 /*
  * Trivial allocator for CLOSIDs. Use BITMAP APIs to manipulate a bitmap
  * of free CLOSIDs.
@@ -4020,9 +4014,13 @@ static void rdtgroup_setup_default(void)
 
 static void domain_destroy_mon_state(struct rdt_mon_domain *d)
 {
+	int idx;
+
 	bitmap_free(d->rmid_busy_llc);
-	kfree(d->mbm_total);
-	kfree(d->mbm_local);
+	for_each_mbm_idx(idx) {
+		kfree(d->mbm_states[idx]);
+		d->mbm_states[idx] = NULL;
+	}
 }
 
 void resctrl_offline_ctrl_domain(struct rdt_resource *r, struct rdt_ctrl_domain *d)
@@ -4082,32 +4080,34 @@ void resctrl_offline_mon_domain(struct rdt_resource *r, struct rdt_mon_domain *d
 static int domain_setup_mon_state(struct rdt_resource *r, struct rdt_mon_domain *d)
 {
 	u32 idx_limit = resctrl_arch_system_num_rmid_idx();
-	size_t tsize;
+	size_t tsize = sizeof(*d->mbm_states[0]);
+	enum resctrl_event_id eventid;
+	int idx;
 
 	if (resctrl_is_mon_event_enabled(QOS_L3_OCCUP_EVENT_ID)) {
 		d->rmid_busy_llc = bitmap_zalloc(idx_limit, GFP_KERNEL);
 		if (!d->rmid_busy_llc)
 			return -ENOMEM;
 	}
-	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID)) {
-		tsize = sizeof(*d->mbm_total);
-		d->mbm_total = kcalloc(idx_limit, tsize, GFP_KERNEL);
-		if (!d->mbm_total) {
-			bitmap_free(d->rmid_busy_llc);
-			return -ENOMEM;
-		}
-	}
-	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_LOCAL_EVENT_ID)) {
-		tsize = sizeof(*d->mbm_local);
-		d->mbm_local = kcalloc(idx_limit, tsize, GFP_KERNEL);
-		if (!d->mbm_local) {
-			bitmap_free(d->rmid_busy_llc);
-			kfree(d->mbm_total);
-			return -ENOMEM;
-		}
+
+	for_each_mbm_event_id(eventid) {
+		if (!resctrl_is_mon_event_enabled(eventid))
+			continue;
+		idx = MBM_STATE_IDX(eventid);
+		d->mbm_states[idx] = kcalloc(idx_limit, tsize, GFP_KERNEL);
+		if (!d->mbm_states[idx])
+			goto cleanup;
 	}
 
 	return 0;
+cleanup:
+	bitmap_free(d->rmid_busy_llc);
+	for_each_mbm_idx(idx) {
+		kfree(d->mbm_states[idx]);
+		d->mbm_states[idx] = NULL;
+	}
+
+	return -ENOMEM;
 }
 
 int resctrl_online_ctrl_domain(struct rdt_resource *r, struct rdt_ctrl_domain *d)
diff --git a/include/linux/resctrl.h b/include/linux/resctrl.h
index 40aba6b5d4f0..478d7a935ca3 100644
--- a/include/linux/resctrl.h
+++ b/include/linux/resctrl.h
@@ -161,8 +161,9 @@ struct rdt_ctrl_domain {
  * @hdr:		common header for different domain types
  * @ci_id:		cache info id for this domain
  * @rmid_busy_llc:	bitmap of which limbo RMIDs are above threshold
- * @mbm_total:		saved state for MBM total bandwidth
- * @mbm_local:		saved state for MBM local bandwidth
+ * @mbm_states:		Per-event pointer to the MBM event's saved state.
+ *			An MBM event's state is an array of struct mbm_state
+ *			indexed by RMID on x86 or combined CLOSID, RMID on Arm.
  * @mbm_over:		worker to periodically read MBM h/w counters
  * @cqm_limbo:		worker to periodically read CQM h/w counters
  * @mbm_work_cpu:	worker CPU for MBM h/w counters
@@ -172,8 +173,7 @@ struct rdt_mon_domain {
 	struct rdt_domain_hdr		hdr;
 	unsigned int			ci_id;
 	unsigned long			*rmid_busy_llc;
-	struct mbm_state		*mbm_total;
-	struct mbm_state		*mbm_local;
+	struct mbm_state		*mbm_states[QOS_NUM_L3_MBM_EVENTS];
 	struct delayed_work		mbm_over;
 	struct delayed_work		cqm_limbo;
 	int				mbm_work_cpu;
@@ -376,6 +376,21 @@ bool resctrl_is_mon_event_enabled(enum resctrl_event_id eventid);
 
 bool resctrl_arch_is_evt_configurable(enum resctrl_event_id evt);
 
+static inline bool resctrl_is_mbm_event(enum resctrl_event_id eventid)
+{
+	return (eventid >= QOS_L3_MBM_TOTAL_EVENT_ID &&
+		eventid <= QOS_L3_MBM_LOCAL_EVENT_ID);
+}
+
+/* Iterate over all memory bandwidth events */
+#define for_each_mbm_event_id(eventid)				\
+	for (eventid = QOS_L3_MBM_TOTAL_EVENT_ID;		\
+	     eventid <= QOS_L3_MBM_LOCAL_EVENT_ID; eventid++)
+
+/* Iterate over memory bandwidth arrays in domain structures */
+#define for_each_mbm_idx(idx)					\
+	for (idx = 0; idx < QOS_NUM_L3_MBM_EVENTS; idx++)
+
 /**
  * resctrl_arch_mon_event_config_write() - Write the config for an event.
  * @config_info: struct resctrl_mon_config_info describing the resource, domain
diff --git a/include/linux/resctrl_types.h b/include/linux/resctrl_types.h
index 2dadbc54e4b3..d98351663c2c 100644
--- a/include/linux/resctrl_types.h
+++ b/include/linux/resctrl_types.h
@@ -51,4 +51,7 @@ enum resctrl_event_id {
 	QOS_NUM_EVENTS,
 };
 
+#define QOS_NUM_L3_MBM_EVENTS	(QOS_L3_MBM_LOCAL_EVENT_ID - QOS_L3_MBM_TOTAL_EVENT_ID + 1)
+#define MBM_STATE_IDX(evt)	((evt) - QOS_L3_MBM_TOTAL_EVENT_ID)
+
 #endif /* __LINUX_RESCTRL_TYPES_H */

---

## [6] Babu Moger — 2025-09-05
*Subject: [PATCH v18 05/33] x86/cpufeatures: Add support for Assignable Bandwidth Monitoring Counters (ABMC)*

Users can create as many monitor groups as RMIDs supported by the hardware.
However, bandwidth monitoring feature on AMD system only guarantees that
RMIDs currently assigned to a processor will be tracked by hardware. The
counters of any other RMIDs which are no longer being tracked will be reset
to zero. The MBM event counters return "Unavailable" for the RMIDs that are
not tracked by hardware. So, there can be only limited number of groups
that can give guaranteed monitoring numbers. With ever changing
configurations there is no way to definitely know which of these groups are
being tracked during a particular time. Users do not have the option to
monitor a group or set of groups for a certain period of time without
worrying about RMID being reset in between.

The ABMC feature allows users to assign a hardware counter to an RMID,
event pair and monitor bandwidth usage as long as it is assigned. The
hardware continues to track the assigned counter until it is explicitly
unassigned by the user. There is no need to worry about counters being
reset during this period. Additionally, the user can specify the type of
memory transactions (e.g., reads, writes) for the counter to track.

Without ABMC enabled, monitoring will work in current mode without
assignment option.

The Linux resctrl subsystem provides an interface that allows monitoring of
up to two memory bandwidth events per group, selected from a combination of
available total and local events. When ABMC is enabled, two events will be
assigned to each group by default, in line with the current interface
design. Users will also have the option to configure which types of memory
transactions are counted by these events.

Due to the limited number of available counters (32), users may quickly
exhaust the available counters. If the system runs out of assignable ABMC
counters, the kernel will report an error. In such cases, users will need
to unassign one or more active counters to free up counters for new
assignments. resctrl will provide options to assign or unassign events
through the group-specific interface file.

The feature is detected via CPUID_Fn80000020_EBX_x00 bit 5.
Bits Description
5    ABMC (Assignable Bandwidth Monitoring Counters)

The ABMC feature details are documented in APM [1] available from [2].
[1] AMD64 Architecture Programmer's Manual Volume 2: System Programming
Publication # 24593 Revision 3.41 section 19.3.3.3 Assignable Bandwidth
Monitoring (ABMC).

Link: https://bugzilla.kernel.org/show_bug.cgi?id=206537 # [2]
Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
Note: Checkpatch checks/warnings are ignored to maintain coding style.

v18: No code changes. Updated text about Link.

v17: Added Reviewed-by tag.

v16: Fixed the conflicts with latest cpufeatures.h and scattered.c files.

v15: Minor changelog update.

v14: Removed the dependancy on X86_FEATURE_CQM_MBM_TOTAL and X86_FEATURE_CQM_MBM_LOCAL.
     as discussed in https://lore.kernel.org/lkml/5f8b21c6-5166-46a6-be14-0c7c9bfb7cde@intel.com/
     Need to re-work on ABMC enumeration during the init.
     Updated changelog with few text update.

v13: Updated the commit log with Linux interface details.

v12: Removed the dependancy on X86_FEATURE_BMEC.
     Removed the Reviewed-by tag as patch has changed.

v11: No changes.

v10: No changes.

v9: Took care of couple of minor merge conflicts. No other changes.

v8: No changes.

v7: Removed "" from feature flags. Not required anymore.
    https://lore.kernel.org/lkml/20240817145058.GCZsC40neU4wkPXeVR@fat_crate.local/

v6: Added Reinette's Reviewed-by. Moved the Checkpatch note below ---.

v5: Minor rebase change and subject line update.

v4: Changes because of rebase. Feature word 21 has few more additions now.
    Changed the text to "tracked by hardware" instead of active.

v3: Change because of rebase. Actual patch did not change.

v2: Added dependency on X86_FEATURE_BMEC.
---
 arch/x86/include/asm/cpufeatures.h | 1 +
 arch/x86/kernel/cpu/scattered.c    | 1 +
 2 files changed, 2 insertions(+)

diff --git a/arch/x86/include/asm/cpufeatures.h b/arch/x86/include/asm/cpufeatures.h
index 06fc0479a23f..9a3bbd61f885 100644
--- a/arch/x86/include/asm/cpufeatures.h
+++ b/arch/x86/include/asm/cpufeatures.h
@@ -495,6 +495,7 @@
 #define X86_FEATURE_TSA_SQ_NO		(21*32+11) /* AMD CPU not vulnerable to TSA-SQ */
 #define X86_FEATURE_TSA_L1_NO		(21*32+12) /* AMD CPU not vulnerable to TSA-L1 */
 #define X86_FEATURE_CLEAR_CPU_BUF_VM	(21*32+13) /* Clear CPU buffers using VERW before VMRUN */
+#define X86_FEATURE_ABMC		(21*32+14) /* Assignable Bandwidth Monitoring Counters */
 
 /*
  * BUG word(s)
diff --git a/arch/x86/kernel/cpu/scattered.c b/arch/x86/kernel/cpu/scattered.c
index 6b868afb26c3..4cee6213d667 100644
--- a/arch/x86/kernel/cpu/scattered.c
+++ b/arch/x86/kernel/cpu/scattered.c
@@ -51,6 +51,7 @@ static const struct cpuid_bit cpuid_bits[] = {
 	{ X86_FEATURE_COHERENCY_SFW_NO,		CPUID_EBX, 31, 0x8000001f, 0 },
 	{ X86_FEATURE_SMBA,			CPUID_EBX,  2, 0x80000020, 0 },
 	{ X86_FEATURE_BMEC,			CPUID_EBX,  3, 0x80000020, 0 },
+	{ X86_FEATURE_ABMC,			CPUID_EBX,  5, 0x80000020, 0 },
 	{ X86_FEATURE_TSA_SQ_NO,		CPUID_ECX,  1, 0x80000021, 0 },
 	{ X86_FEATURE_TSA_L1_NO,		CPUID_ECX,  2, 0x80000021, 0 },
 	{ X86_FEATURE_AMD_WORKLOAD_CLASS,	CPUID_EAX, 22, 0x80000021, 0 },

---

## [7] Babu Moger — 2025-09-05
*Subject: [PATCH v18 06/33] x86/resctrl: Add ABMC feature in the command line options*

Add a kernel command-line parameter to enable or disable the exposure of
the ABMC (Assignable Bandwidth Monitoring Counters) hardware feature to
resctrl.

Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: No changes.

v17: No changes.

v16: Added Reviewed-by tag.

v15: No changes.

v14: Slight changelog modification.

v13: Removed the Reviewed-by as the file resctrl.rst is moved to
     Documentation/filesystems/resctrl.rst. In that sense patch has changed.

v12: No changes.

v11: No changes.

v10: No changes.

v9: No code changes. Added Reviewed-by.

v8: Commit message update.

v7: No changes

v6: No changes

v5: No changes

v4: No changes

v3: No changes

v2: No changes
---
 Documentation/admin-guide/kernel-parameters.txt | 2 +-
 Documentation/filesystems/resctrl.rst           | 1 +
 arch/x86/kernel/cpu/resctrl/core.c              | 2 ++
 3 files changed, 4 insertions(+), 1 deletion(-)

diff --git a/Documentation/admin-guide/kernel-parameters.txt b/Documentation/admin-guide/kernel-parameters.txt
index 747a55abf494..5bab2eff81eb 100644
--- a/Documentation/admin-guide/kernel-parameters.txt
+++ b/Documentation/admin-guide/kernel-parameters.txt
@@ -6154,7 +6154,7 @@
 	rdt=		[HW,X86,RDT]
 			Turn on/off individual RDT features. List is:
 			cmt, mbmtotal, mbmlocal, l3cat, l3cdp, l2cat, l2cdp,
-			mba, smba, bmec.
+			mba, smba, bmec, abmc.
 			E.g. to turn on cmt and turn off mba use:
 				rdt=cmt,!mba
 
diff --git a/Documentation/filesystems/resctrl.rst b/Documentation/filesystems/resctrl.rst
index c7949dd44f2f..c97fd77a107d 100644
--- a/Documentation/filesystems/resctrl.rst
+++ b/Documentation/filesystems/resctrl.rst
@@ -26,6 +26,7 @@ MBM (Memory Bandwidth Monitoring)		"cqm_mbm_total", "cqm_mbm_local"
 MBA (Memory Bandwidth Allocation)		"mba"
 SMBA (Slow Memory Bandwidth Allocation)         ""
 BMEC (Bandwidth Monitoring Event Configuration) ""
+ABMC (Assignable Bandwidth Monitoring Counters) ""
 ===============================================	================================
 
 Historically, new features were made visible by default in /proc/cpuinfo. This
diff --git a/arch/x86/kernel/cpu/resctrl/core.c b/arch/x86/kernel/cpu/resctrl/core.c
index fbf019c1ff11..b07b12a05886 100644
--- a/arch/x86/kernel/cpu/resctrl/core.c
+++ b/arch/x86/kernel/cpu/resctrl/core.c
@@ -711,6 +711,7 @@ enum {
 	RDT_FLAG_MBA,
 	RDT_FLAG_SMBA,
 	RDT_FLAG_BMEC,
+	RDT_FLAG_ABMC,
 };
 
 #define RDT_OPT(idx, n, f)	\
@@ -736,6 +737,7 @@ static struct rdt_options rdt_options[]  __ro_after_init = {
 	RDT_OPT(RDT_FLAG_MBA,	    "mba",	X86_FEATURE_MBA),
 	RDT_OPT(RDT_FLAG_SMBA,	    "smba",	X86_FEATURE_SMBA),
 	RDT_OPT(RDT_FLAG_BMEC,	    "bmec",	X86_FEATURE_BMEC),
+	RDT_OPT(RDT_FLAG_ABMC,	    "abmc",	X86_FEATURE_ABMC),
 };
 #define NUM_RDT_OPTIONS ARRAY_SIZE(rdt_options)

---

## [8] Babu Moger — 2025-09-05
*Subject: [PATCH v18 07/33] x86,fs/resctrl: Consolidate monitoring related data from rdt_resource*

The cache allocation and memory bandwidth allocation feature properties
are consolidated into struct resctrl_cache and struct resctrl_membw
respectively.

In preparation for more monitoring properties that will clobber the
existing resource struct more, re-organize the monitoring specific
properties to also be in a separate structure.

Also switch "bandwidth sources" term to "memory transactions" to use
consistent term within resctrl for related monitoring features.

Suggested-by: Reinette Chatre <reinette.chatre@intel.com>
Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: No changes.

v17: No changes.

v16: Added the Reviewed-by tag.

v15: Updated changelog.
     Minor update in code comment in resctrl.h.

v14: Updated the code comment in resctrl.h.

v13: Changes due to FS/ARCH restructure.

v12: Fixed the conflicts due to recent changes in rdt_resource data structure.
     Added new mbm_cfg_mask field to resctrl_mon.
     Removed Reviewed-by tag as patch has changed.

v11: No changes.

v10: No changes.

v9: No changes.

v8: Added Reviewed-by from Reinette. No other changes.

v7: Added kernel doc for data structure. Minor text update.

v6: Update commit message and update kernel doc for rdt_resource.

v5: Commit message update.
    Also changes related to data structure updates does to SNC support.

v4: New patch.
---
 arch/x86/kernel/cpu/resctrl/core.c    |  4 ++--
 arch/x86/kernel/cpu/resctrl/monitor.c | 10 +++++-----
 fs/resctrl/rdtgroup.c                 |  6 +++---
 include/linux/resctrl.h               | 18 +++++++++++++-----
 4 files changed, 23 insertions(+), 15 deletions(-)

diff --git a/arch/x86/kernel/cpu/resctrl/core.c b/arch/x86/kernel/cpu/resctrl/core.c
index b07b12a05886..267e9206a999 100644
--- a/arch/x86/kernel/cpu/resctrl/core.c
+++ b/arch/x86/kernel/cpu/resctrl/core.c
@@ -107,7 +107,7 @@ u32 resctrl_arch_system_num_rmid_idx(void)
 	struct rdt_resource *r = &rdt_resources_all[RDT_RESOURCE_L3].r_resctrl;
 
 	/* RMID are independent numbers for x86. num_rmid_idx == num_rmid */
-	return r->num_rmid;
+	return r->mon.num_rmid;
 }
 
 struct rdt_resource *resctrl_arch_get_resource(enum resctrl_res_level l)
@@ -541,7 +541,7 @@ static void domain_add_cpu_mon(int cpu, struct rdt_resource *r)
 
 	arch_mon_domain_online(r, d);
 
-	if (arch_domain_mbm_alloc(r->num_rmid, hw_dom)) {
+	if (arch_domain_mbm_alloc(r->mon.num_rmid, hw_dom)) {
 		mon_domain_free(hw_dom);
 		return;
 	}
diff --git a/arch/x86/kernel/cpu/resctrl/monitor.c b/arch/x86/kernel/cpu/resctrl/monitor.c
index f01db2034d08..2558b1bdef8b 100644
--- a/arch/x86/kernel/cpu/resctrl/monitor.c
+++ b/arch/x86/kernel/cpu/resctrl/monitor.c
@@ -130,7 +130,7 @@ static int logical_rmid_to_physical_rmid(int cpu, int lrmid)
 	if (snc_nodes_per_l3_cache == 1)
 		return lrmid;
 
-	return lrmid + (cpu_to_node(cpu) % snc_nodes_per_l3_cache) * r->num_rmid;
+	return lrmid + (cpu_to_node(cpu) % snc_nodes_per_l3_cache) * r->mon.num_rmid;
 }
 
 static int __rmid_read_phys(u32 prmid, enum resctrl_event_id eventid, u64 *val)
@@ -205,7 +205,7 @@ void resctrl_arch_reset_rmid_all(struct rdt_resource *r, struct rdt_mon_domain *
 			continue;
 		idx = MBM_STATE_IDX(eventid);
 		memset(hw_dom->arch_mbm_states[idx], 0,
-		       sizeof(*hw_dom->arch_mbm_states[0]) * r->num_rmid);
+		       sizeof(*hw_dom->arch_mbm_states[0]) * r->mon.num_rmid);
 	}
 }
 
@@ -344,7 +344,7 @@ int __init rdt_get_mon_l3_config(struct rdt_resource *r)
 
 	resctrl_rmid_realloc_limit = boot_cpu_data.x86_cache_size * 1024;
 	hw_res->mon_scale = boot_cpu_data.x86_cache_occ_scale / snc_nodes_per_l3_cache;
-	r->num_rmid = (boot_cpu_data.x86_cache_max_rmid + 1) / snc_nodes_per_l3_cache;
+	r->mon.num_rmid = (boot_cpu_data.x86_cache_max_rmid + 1) / snc_nodes_per_l3_cache;
 	hw_res->mbm_width = MBM_CNTR_WIDTH_BASE;
 
 	if (mbm_offset > 0 && mbm_offset <= MBM_CNTR_WIDTH_OFFSET_MAX)
@@ -359,7 +359,7 @@ int __init rdt_get_mon_l3_config(struct rdt_resource *r)
 	 *
 	 * For a 35MB LLC and 56 RMIDs, this is ~1.8% of the LLC.
 	 */
-	threshold = resctrl_rmid_realloc_limit / r->num_rmid;
+	threshold = resctrl_rmid_realloc_limit / r->mon.num_rmid;
 
 	/*
 	 * Because num_rmid may not be a power of two, round the value
@@ -373,7 +373,7 @@ int __init rdt_get_mon_l3_config(struct rdt_resource *r)
 
 		/* Detect list of bandwidth sources that can be tracked */
 		cpuid_count(0x80000020, 3, &eax, &ebx, &ecx, &edx);
-		r->mbm_cfg_mask = ecx & MAX_EVT_CONFIG_BITS;
+		r->mon.mbm_cfg_mask = ecx & MAX_EVT_CONFIG_BITS;
 	}
 
 	r->mon_capable = true;
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index a6047e9345cd..b6ab10704993 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -1135,7 +1135,7 @@ static int rdt_num_rmids_show(struct kernfs_open_file *of,
 {
 	struct rdt_resource *r = rdt_kn_parent_priv(of->kn);
 
-	seq_printf(seq, "%d\n", r->num_rmid);
+	seq_printf(seq, "%d\n", r->mon.num_rmid);
 
 	return 0;
 }
@@ -1731,9 +1731,9 @@ static int mon_config_write(struct rdt_resource *r, char *tok, u32 evtid)
 	}
 
 	/* Value from user cannot be more than the supported set of events */
-	if ((val & r->mbm_cfg_mask) != val) {
+	if ((val & r->mon.mbm_cfg_mask) != val) {
 		rdt_last_cmd_printf("Invalid event configuration: max valid mask is 0x%02x\n",
-				    r->mbm_cfg_mask);
+				    r->mon.mbm_cfg_mask);
 		return -EINVAL;
 	}
 
diff --git a/include/linux/resctrl.h b/include/linux/resctrl.h
index 478d7a935ca3..fe2af6cb96d4 100644
--- a/include/linux/resctrl.h
+++ b/include/linux/resctrl.h
@@ -255,38 +255,46 @@ enum resctrl_schema_fmt {
 	RESCTRL_SCHEMA_RANGE,
 };
 
+/**
+ * struct resctrl_mon - Monitoring related data of a resctrl resource.
+ * @num_rmid:		Number of RMIDs available.
+ * @mbm_cfg_mask:	Memory transactions that can be tracked when bandwidth
+ *			monitoring events can be configured.
+ */
+struct resctrl_mon {
+	int			num_rmid;
+	unsigned int		mbm_cfg_mask;
+};
+
 /**
  * struct rdt_resource - attributes of a resctrl resource
  * @rid:		The index of the resource
  * @alloc_capable:	Is allocation available on this machine
  * @mon_capable:	Is monitor feature available on this machine
- * @num_rmid:		Number of RMIDs available
  * @ctrl_scope:		Scope of this resource for control functions
  * @mon_scope:		Scope of this resource for monitor functions
  * @cache:		Cache allocation related data
  * @membw:		If the component has bandwidth controls, their properties.
+ * @mon:		Monitoring related data.
  * @ctrl_domains:	RCU list of all control domains for this resource
  * @mon_domains:	RCU list of all monitor domains for this resource
  * @name:		Name to use in "schemata" file.
  * @schema_fmt:		Which format string and parser is used for this schema.
- * @mbm_cfg_mask:	Bandwidth sources that can be tracked when bandwidth
- *			monitoring events can be configured.
  * @cdp_capable:	Is the CDP feature available on this resource
  */
 struct rdt_resource {
 	int			rid;
 	bool			alloc_capable;
 	bool			mon_capable;
-	int			num_rmid;
 	enum resctrl_scope	ctrl_scope;
 	enum resctrl_scope	mon_scope;
 	struct resctrl_cache	cache;
 	struct resctrl_membw	membw;
+	struct resctrl_mon	mon;
 	struct list_head	ctrl_domains;
 	struct list_head	mon_domains;
 	char			*name;
 	enum resctrl_schema_fmt	schema_fmt;
-	unsigned int		mbm_cfg_mask;
 	bool			cdp_capable;
 };

---

## [9] Babu Moger — 2025-09-05
*Subject: [PATCH v18 08/33] x86,fs/resctrl: Detect Assignable Bandwidth Monitoring feature details*

ABMC feature details are reported via CPUID Fn8000_0020_EBX_x5.
Bits Description
15:0 MAX_ABMC Maximum Supported Assignable Bandwidth
     Monitoring Counter ID + 1

The ABMC feature details are documented in APM [1] available from [2].
[1] AMD64 Architecture Programmer's Manual Volume 2: System Programming
Publication # 24593 Revision 3.41 section 19.3.3.3 Assignable Bandwidth
Monitoring (ABMC).

Detect the feature and number of assignable counters supported. For
backward compatibility, upon detecting the assignable counter feature,
enable the mbm_total_bytes and mbm_local_bytes events that users are
familiar with as part of original L3 MBM support.

Link: https://bugzilla.kernel.org/show_bug.cgi?id=206537 # [2]
Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: Added Reviewed-by tag. Updated the text about the documentation Link.

v17: Added another ABMC check in resctrl_cpu_detect().

v15: Minor update to changelog.
     Added check in resctrl_cpu_detect().
     Moved the resctrl_enable_mon_event() to resctrl_mon_resource_init().

v14: Updated enumeration to support ABMC regardless of MBM total and local support.
     Updated the changelog accordingly.

v13: No changes.

v12: Resolved conflicts because of latest merge.
     Removed Reviewed-by as the patch has changed.

v11: No changes.

v10: No changes.

v9: Added Reviewed-by tag. No code changes

v8: Used GENMASK for the mask.

v7: Removed WARN_ON for num_mbm_cntrs. Decided to dynamically allocate the
    bitmap. WARN_ON is not required anymore.
    Removed redundant comments.

v6: Commit message update.
    Renamed abmc_capable to mbm_cntr_assignable.

v5: Name change num_cntrs to num_mbm_cntrs.
    Moved abmc_capable to resctrl_mon.

v4: Removed resctrl_arch_has_abmc(). Added all the code inline. We dont
    need to separate this as arch code.

v3: Removed changes related to mon_features.
    Moved rdt_cpu_has to core.c and added new function resctrl_arch_has_abmc.
    Also moved the fields mbm_assign_capable and mbm_assign_cntrs to
    rdt_resource. (James)

v2: Changed the field name to mbm_assign_capable from abmc_capable.
---
 arch/x86/kernel/cpu/resctrl/core.c    |  7 +++++--
 arch/x86/kernel/cpu/resctrl/monitor.c | 11 ++++++++---
 fs/resctrl/monitor.c                  |  7 +++++++
 include/linux/resctrl.h               |  4 ++++
 4 files changed, 24 insertions(+), 5 deletions(-)

diff --git a/arch/x86/kernel/cpu/resctrl/core.c b/arch/x86/kernel/cpu/resctrl/core.c
index 267e9206a999..2e68aa02ad3f 100644
--- a/arch/x86/kernel/cpu/resctrl/core.c
+++ b/arch/x86/kernel/cpu/resctrl/core.c
@@ -883,6 +883,8 @@ static __init bool get_rdt_mon_resources(void)
 		resctrl_enable_mon_event(QOS_L3_MBM_LOCAL_EVENT_ID);
 		ret = true;
 	}
+	if (rdt_cpu_has(X86_FEATURE_ABMC))
+		ret = true;
 
 	if (!ret)
 		return false;
@@ -978,7 +980,7 @@ static enum cpuhp_state rdt_online;
 /* Runs once on the BSP during boot. */
 void resctrl_cpu_detect(struct cpuinfo_x86 *c)
 {
-	if (!cpu_has(c, X86_FEATURE_CQM_LLC)) {
+	if (!cpu_has(c, X86_FEATURE_CQM_LLC) && !cpu_has(c, X86_FEATURE_ABMC)) {
 		c->x86_cache_max_rmid  = -1;
 		c->x86_cache_occ_scale = -1;
 		c->x86_cache_mbm_width_offset = -1;
@@ -990,7 +992,8 @@ void resctrl_cpu_detect(struct cpuinfo_x86 *c)
 
 	if (cpu_has(c, X86_FEATURE_CQM_OCCUP_LLC) ||
 	    cpu_has(c, X86_FEATURE_CQM_MBM_TOTAL) ||
-	    cpu_has(c, X86_FEATURE_CQM_MBM_LOCAL)) {
+	    cpu_has(c, X86_FEATURE_CQM_MBM_LOCAL) ||
+	    cpu_has(c, X86_FEATURE_ABMC)) {
 		u32 eax, ebx, ecx, edx;
 
 		/* QoS sub-leaf, EAX=0Fh, ECX=1 */
diff --git a/arch/x86/kernel/cpu/resctrl/monitor.c b/arch/x86/kernel/cpu/resctrl/monitor.c
index 2558b1bdef8b..0a695ce68f46 100644
--- a/arch/x86/kernel/cpu/resctrl/monitor.c
+++ b/arch/x86/kernel/cpu/resctrl/monitor.c
@@ -339,6 +339,7 @@ int __init rdt_get_mon_l3_config(struct rdt_resource *r)
 	unsigned int mbm_offset = boot_cpu_data.x86_cache_mbm_width_offset;
 	struct rdt_hw_resource *hw_res = resctrl_to_arch_res(r);
 	unsigned int threshold;
+	u32 eax, ebx, ecx, edx;
 
 	snc_nodes_per_l3_cache = snc_get_config();
 
@@ -368,14 +369,18 @@ int __init rdt_get_mon_l3_config(struct rdt_resource *r)
 	 */
 	resctrl_rmid_realloc_threshold = resctrl_arch_round_mon_val(threshold);
 
-	if (rdt_cpu_has(X86_FEATURE_BMEC)) {
-		u32 eax, ebx, ecx, edx;
-
+	if (rdt_cpu_has(X86_FEATURE_BMEC) || rdt_cpu_has(X86_FEATURE_ABMC)) {
 		/* Detect list of bandwidth sources that can be tracked */
 		cpuid_count(0x80000020, 3, &eax, &ebx, &ecx, &edx);
 		r->mon.mbm_cfg_mask = ecx & MAX_EVT_CONFIG_BITS;
 	}
 
+	if (rdt_cpu_has(X86_FEATURE_ABMC)) {
+		r->mon.mbm_cntr_assignable = true;
+		cpuid_count(0x80000020, 5, &eax, &ebx, &ecx, &edx);
+		r->mon.num_mbm_cntrs = (ebx & GENMASK(15, 0)) + 1;
+	}
+
 	r->mon_capable = true;
 
 	return 0;
diff --git a/fs/resctrl/monitor.c b/fs/resctrl/monitor.c
index dcc6c00eb362..66c8c635f4b3 100644
--- a/fs/resctrl/monitor.c
+++ b/fs/resctrl/monitor.c
@@ -924,6 +924,13 @@ int resctrl_mon_resource_init(void)
 	else if (resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID))
 		mba_mbps_default_event = QOS_L3_MBM_TOTAL_EVENT_ID;
 
+	if (r->mon.mbm_cntr_assignable) {
+		if (!resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID))
+			resctrl_enable_mon_event(QOS_L3_MBM_TOTAL_EVENT_ID);
+		if (!resctrl_is_mon_event_enabled(QOS_L3_MBM_LOCAL_EVENT_ID))
+			resctrl_enable_mon_event(QOS_L3_MBM_LOCAL_EVENT_ID);
+	}
+
 	return 0;
 }
 
diff --git a/include/linux/resctrl.h b/include/linux/resctrl.h
index fe2af6cb96d4..eb80cc233be4 100644
--- a/include/linux/resctrl.h
+++ b/include/linux/resctrl.h
@@ -260,10 +260,14 @@ enum resctrl_schema_fmt {
  * @num_rmid:		Number of RMIDs available.
  * @mbm_cfg_mask:	Memory transactions that can be tracked when bandwidth
  *			monitoring events can be configured.
+ * @num_mbm_cntrs:	Number of assignable counters.
+ * @mbm_cntr_assignable:Is system capable of supporting counter assignment?
  */
 struct resctrl_mon {
 	int			num_rmid;
 	unsigned int		mbm_cfg_mask;
+	int			num_mbm_cntrs;
+	bool			mbm_cntr_assignable;
 };
 
 /**

---

## [10] Babu Moger — 2025-09-05
*Subject: [PATCH v18 09/33] x86/resctrl: Add support to enable/disable AMD ABMC feature*

Add the functionality to enable/disable AMD ABMC feature.

AMD ABMC feature is enabled by setting enabled bit(0) in MSR
L3_QOS_EXT_CFG. When the state of ABMC is changed, the MSR needs
to be updated on all the logical processors in the QOS Domain.

Hardware counters will reset when ABMC state is changed.

The ABMC feature details are documented in APM [1] available from [2].
[1] AMD64 Architecture Programmer's Manual Volume 2: System Programming
Publication # 24593 Revision 3.41 section 19.3.3.3 Assignable Bandwidth
Monitoring (ABMC).

Link: https://bugzilla.kernel.org/show_bug.cgi?id=206537 # [2]
Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: No changes.

v17: No changes.

v16: Added Reviewed-by tag.

v15: Minor comment change in resctrl.h.

v14: Added lockdep_assert_cpus_held() in _resctrl_abmc_enable().
     Removed inline for resctrl_arch_mbm_cntr_assign_enabled().
     Added prototype descriptions for resctrl_arch_mbm_cntr_assign_enabled()
     and resctrl_arch_mbm_cntr_assign_set() in include/linux/resctrl.h.

v13: Resolved minor conflicts with recent FS/ARCH restructure.

v12: Clarified the comment on _resctrl_abmc_enable().
     Added the code to reset arch state in _resctrl_abmc_enable().
     Resolved the conflicts with latest merge.

v11: Moved the monitoring related calls to monitor.c file.
     Moved the changes from include/linux/resctrl.h to
     arch/x86/kernel/cpu/resctrl/internal.h.
     Removed the Reviewed-by tag as patch changed.
     Actual code did not change.

v10: No changes.

v9: Re-ordered the MSR and added Reviewed-by tag.

v8: Commit message update and moved around the comments about L3_QOS_EXT_CFG
    to _resctrl_abmc_enable.

v7: Renamed the function
    resctrl_arch_get_abmc_enabled() to resctrl_arch_mbm_cntr_assign_enabled().

    Merged resctrl_arch_mbm_cntr_assign_disable, resctrl_arch_mbm_cntr_assign_disable
    and renamed to resctrl_arch_mbm_cntr_assign_set().

    Moved the function definition to linux/resctrl.h.

    Passed the struct rdt_resource to these functions.
    Removed resctrl_arch_reset_rmid_all() from arch code. This will be done
    from the caller.

v6: Renamed abmc_enabled to mbm_cntr_assign_enabled.
    Used msr_set_bit and msr_clear_bit for msr updates.
    Renamed resctrl_arch_abmc_enable() to resctrl_arch_mbm_cntr_assign_enable().
    Renamed resctrl_arch_abmc_disable() to resctrl_arch_mbm_cntr_assign_disable().
    Made _resctrl_abmc_enable to return void.

v5: Renamed resctrl_abmc_enable to resctrl_arch_abmc_enable.
    Renamed resctrl_abmc_disable to resctrl_arch_abmc_disable.
    Introduced resctrl_arch_get_abmc_enabled to get abmc state from
    non-arch code.
    Renamed resctrl_abmc_set_all to _resctrl_abmc_enable().
    Modified commit log to make it clear about AMD ABMC feature.

v3: No changes.

v2: Few text changes in commit message.
---
 arch/x86/include/asm/msr-index.h       |  1 +
 arch/x86/kernel/cpu/resctrl/internal.h |  5 +++
 arch/x86/kernel/cpu/resctrl/monitor.c  | 45 ++++++++++++++++++++++++++
 include/linux/resctrl.h                | 20 ++++++++++++
 4 files changed, 71 insertions(+)

diff --git a/arch/x86/include/asm/msr-index.h b/arch/x86/include/asm/msr-index.h
index a0c1dbf5692b..18222527b0ee 100644
--- a/arch/x86/include/asm/msr-index.h
+++ b/arch/x86/include/asm/msr-index.h
@@ -1232,6 +1232,7 @@
 /* - AMD: */
 #define MSR_IA32_MBA_BW_BASE		0xc0000200
 #define MSR_IA32_SMBA_BW_BASE		0xc0000280
+#define MSR_IA32_L3_QOS_EXT_CFG		0xc00003ff
 #define MSR_IA32_EVT_CFG_BASE		0xc0000400
 
 /* AMD-V MSRs */
diff --git a/arch/x86/kernel/cpu/resctrl/internal.h b/arch/x86/kernel/cpu/resctrl/internal.h
index 58dca892a5df..a79a487e639c 100644
--- a/arch/x86/kernel/cpu/resctrl/internal.h
+++ b/arch/x86/kernel/cpu/resctrl/internal.h
@@ -37,6 +37,9 @@ struct arch_mbm_state {
 	u64	prev_msr;
 };
 
+/* Setting bit 0 in L3_QOS_EXT_CFG enables the ABMC feature. */
+#define ABMC_ENABLE_BIT			0
+
 /**
  * struct rdt_hw_ctrl_domain - Arch private attributes of a set of CPUs that share
  *			       a resource for a control function
@@ -102,6 +105,7 @@ struct msr_param {
  * @mon_scale:		cqm counter * mon_scale = occupancy in bytes
  * @mbm_width:		Monitor width, to detect and correct for overflow.
  * @cdp_enabled:	CDP state of this resource
+ * @mbm_cntr_assign_enabled:	ABMC feature is enabled
  *
  * Members of this structure are either private to the architecture
  * e.g. mbm_width, or accessed via helpers that provide abstraction. e.g.
@@ -115,6 +119,7 @@ struct rdt_hw_resource {
 	unsigned int		mon_scale;
 	unsigned int		mbm_width;
 	bool			cdp_enabled;
+	bool			mbm_cntr_assign_enabled;
 };
 
 static inline struct rdt_hw_resource *resctrl_to_arch_res(struct rdt_resource *r)
diff --git a/arch/x86/kernel/cpu/resctrl/monitor.c b/arch/x86/kernel/cpu/resctrl/monitor.c
index 0a695ce68f46..cce35a0ad455 100644
--- a/arch/x86/kernel/cpu/resctrl/monitor.c
+++ b/arch/x86/kernel/cpu/resctrl/monitor.c
@@ -399,3 +399,48 @@ void __init intel_rdt_mbm_apply_quirk(void)
 	mbm_cf_rmidthreshold = mbm_cf_table[cf_index].rmidthreshold;
 	mbm_cf = mbm_cf_table[cf_index].cf;
 }
+
+static void resctrl_abmc_set_one_amd(void *arg)
+{
+	bool *enable = arg;
+
+	if (*enable)
+		msr_set_bit(MSR_IA32_L3_QOS_EXT_CFG, ABMC_ENABLE_BIT);
+	else
+		msr_clear_bit(MSR_IA32_L3_QOS_EXT_CFG, ABMC_ENABLE_BIT);
+}
+
+/*
+ * ABMC enable/disable requires update of L3_QOS_EXT_CFG MSR on all the CPUs
+ * associated with all monitor domains.
+ */
+static void _resctrl_abmc_enable(struct rdt_resource *r, bool enable)
+{
+	struct rdt_mon_domain *d;
+
+	lockdep_assert_cpus_held();
+
+	list_for_each_entry(d, &r->mon_domains, hdr.list) {
+		on_each_cpu_mask(&d->hdr.cpu_mask, resctrl_abmc_set_one_amd,
+				 &enable, 1);
+		resctrl_arch_reset_rmid_all(r, d);
+	}
+}
+
+int resctrl_arch_mbm_cntr_assign_set(struct rdt_resource *r, bool enable)
+{
+	struct rdt_hw_resource *hw_res = resctrl_to_arch_res(r);
+
+	if (r->mon.mbm_cntr_assignable &&
+	    hw_res->mbm_cntr_assign_enabled != enable) {
+		_resctrl_abmc_enable(r, enable);
+		hw_res->mbm_cntr_assign_enabled = enable;
+	}
+
+	return 0;
+}
+
+bool resctrl_arch_mbm_cntr_assign_enabled(struct rdt_resource *r)
+{
+	return resctrl_to_arch_res(r)->mbm_cntr_assign_enabled;
+}
diff --git a/include/linux/resctrl.h b/include/linux/resctrl.h
index eb80cc233be4..919806122c50 100644
--- a/include/linux/resctrl.h
+++ b/include/linux/resctrl.h
@@ -445,6 +445,26 @@ static inline u32 resctrl_get_config_index(u32 closid,
 bool resctrl_arch_get_cdp_enabled(enum resctrl_res_level l);
 int resctrl_arch_set_cdp_enabled(enum resctrl_res_level l, bool enable);
 
+/**
+ * resctrl_arch_mbm_cntr_assign_enabled() - Check if MBM counter assignment
+ *					    mode is enabled.
+ * @r:		Pointer to the resource structure.
+ *
+ * Return:
+ * true if the assignment mode is enabled, false otherwise.
+ */
+bool resctrl_arch_mbm_cntr_assign_enabled(struct rdt_resource *r);
+
+/**
+ * resctrl_arch_mbm_cntr_assign_set() - Configure the MBM counter assignment mode.
+ * @r:		Pointer to the resource structure.
+ * @enable:	Set to true to enable, false to disable the assignment mode.
+ *
+ * Return:
+ * 0 on success, < 0 on error.
+ */
+int resctrl_arch_mbm_cntr_assign_set(struct rdt_resource *r, bool enable);
+
 /*
  * Update the ctrl_val and apply this config right now.
  * Must be called on one of the domain's CPUs.

---

## [11] Babu Moger — 2025-09-05
*Subject: [PATCH v18 10/33] fs/resctrl: Introduce the interface to display monitoring modes*

Introduce the resctrl file "mbm_assign_mode" to list the supported counter
assignment modes.

The "mbm_event" counter assignment mode allows users to assign a hardware
counter to an RMID, event pair and monitor bandwidth usage as long as it is
assigned. The hardware continues to track the assigned counter until it is
explicitly unassigned by the user. Each event within a resctrl group can be
assigned independently in this mode.

On AMD systems "mbm_event" mode is backed by the ABMC (Assignable
Bandwidth Monitoring Counters) hardware feature and is enabled by default.

The "default" mode is the existing mode that works without the explicit
counter assignment, instead relying on dynamic counter assignment by
hardware that may result in hardware not dedicating a counter resulting
in monitoring data reads returning "Unavailable".

Provide an interface to display the monitor modes on the system.

$ cat /sys/fs/resctrl/info/L3_MON/mbm_assign_mode
[mbm_event]
default

Add IS_ENABLED(CONFIG_RESCTRL_ASSIGN_FIXED) check to support Arm64.

On x86, CONFIG_RESCTRL_ASSIGN_FIXED is not defined. On Arm64, it will be
defined when the "mbm_event" mode is supported.

Add IS_ENABLED(CONFIG_RESCTRL_ASSIGN_FIXED) check early to ensure the user
interface remains compatible with upcoming Arm64 support. IS_ENABLED()
safely evaluates to 0 when the configuration is not defined.

As a result, for MPAM, the display would be either:
[default]
or
[mbm_event]

Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: Added Reviewed-by tag.

v17: Moved resctrl_mbm_assign_mode_show() to fs/resctrl/monitor.c.
     Removed Reviewed-by tag as patch has changed.

v16: Update with Reviewed-by tag.

v15: Minor text changes in changelog and resctrl.rst.

v14: Changed the name of the monitor mode to mbm_cntr_evt_assign based on the discussion.
     https://lore.kernel.org/lkml/7628cec8-5914-4895-8289-027e7821777e@amd.com/
     Changed the name of the mbm_assign_mode's.
     Updated resctrl.rst for mbm_event mode.
     Changed subject line to fs/resctrl.

v13: Updated the commit log with motivation for adding CONFIG_RESCTRL_ASSIGN_FIXED.
     Added fflag RFTYPE_RES_CACHE for mbm_assign_mode file.
     Updated user doc. Removed the references to "mbm_assign_control".
     Resolved the conflicts with latest FS/ARCH code restructure.

v12: Minor text update in change log and user documentation.
     Added the check CONFIG_RESCTRL_ASSIGN_FIXED to take care of arm platforms.
     This will be defined only in arm and not in x86.

v11: Renamed rdtgroup_mbm_assign_mode_show() to resctrl_mbm_assign_mode_show().
     Removed few texts in resctrl.rst about AMD specific information.
     Updated few texts.

v10: Added few more text to user documentation clarify on the default mode.

v9: Updated user documentation based on comments.

v8: Commit message update.

v7: Updated the descriptions/commit log in resctrl.rst to generic text.
    Thanks to James and Reinette.
    Rename mbm_mode to mbm_assign_mode.
    Introduced mutex lock in rdtgroup_mbm_mode_show().

v6: Added documentation for mbm_cntr_assign and legacy mode.
    Moved mbm_mode fflags initialization to static initialization.

v5: Changed interface name to mbm_mode.
    It will be always available even if ABMC feature is not supported.
    Added description in resctrl.rst about ABMC mode.
    Fixed display abmc and legacy consistantly.

v4: Fixed the checks for legacy and abmc mode. Default it ABMC.

v3: New patch to display ABMC capability.
---
 Documentation/filesystems/resctrl.rst | 31 +++++++++++++++++++++++++++
 fs/resctrl/internal.h                 |  4 ++++
 fs/resctrl/monitor.c                  | 30 ++++++++++++++++++++++++++
 fs/resctrl/rdtgroup.c                 |  9 +++++++-
 4 files changed, 73 insertions(+), 1 deletion(-)

diff --git a/Documentation/filesystems/resctrl.rst b/Documentation/filesystems/resctrl.rst
index c97fd77a107d..b692829fec5f 100644
--- a/Documentation/filesystems/resctrl.rst
+++ b/Documentation/filesystems/resctrl.rst
@@ -257,6 +257,37 @@ with the following files:
 	    # cat /sys/fs/resctrl/info/L3_MON/mbm_local_bytes_config
 	    0=0x30;1=0x30;3=0x15;4=0x15
 
+"mbm_assign_mode":
+	The supported counter assignment modes. The enclosed brackets indicate which mode
+	is enabled.
+	::
+
+	  # cat /sys/fs/resctrl/info/L3_MON/mbm_assign_mode
+	  [mbm_event]
+	  default
+
+	"mbm_event":
+
+	mbm_event mode allows users to assign a hardware counter to an RMID, event
+	pair and monitor the bandwidth usage as long as it is assigned. The hardware
+	continues to track the assigned counter until it is explicitly unassigned by
+	the user. Each event within a resctrl group can be assigned independently.
+
+	In this mode, a monitoring event can only accumulate data while it is backed
+	by a hardware counter. Use "mbm_L3_assignments" found in each CTRL_MON and MON
+	group to specify which of the events should have a counter assigned. The number
+	of counters available is described in the "num_mbm_cntrs" file. Changing the
+	mode may cause all counters on the resource to reset.
+
+	"default":
+
+	In default mode, resctrl assumes there is a hardware counter for each
+	event within every CTRL_MON and MON group. On AMD platforms, it is
+	recommended to use the mbm_event mode, if supported, to prevent reset of MBM
+	events between reads resulting from hardware re-allocating counters. This can
+	result in misleading values or display "Unavailable" if no counter is assigned
+	to the event.
+
 "max_threshold_occupancy":
 		Read/write file provides the largest value (in
 		bytes) at which a previously used LLC_occupancy
diff --git a/fs/resctrl/internal.h b/fs/resctrl/internal.h
index 4f315b7e9ec0..4fbc809b11a6 100644
--- a/fs/resctrl/internal.h
+++ b/fs/resctrl/internal.h
@@ -382,6 +382,10 @@ bool closid_allocated(unsigned int closid);
 
 int resctrl_find_cleanest_closid(void);
 
+void *rdt_kn_parent_priv(struct kernfs_node *kn);
+
+int resctrl_mbm_assign_mode_show(struct kernfs_open_file *of, struct seq_file *s, void *v);
+
 #ifdef CONFIG_RESCTRL_FS_PSEUDO_LOCK
 int rdtgroup_locksetup_enter(struct rdtgroup *rdtgrp);
 
diff --git a/fs/resctrl/monitor.c b/fs/resctrl/monitor.c
index 66c8c635f4b3..379166134f5a 100644
--- a/fs/resctrl/monitor.c
+++ b/fs/resctrl/monitor.c
@@ -884,6 +884,36 @@ bool resctrl_is_mon_event_enabled(enum resctrl_event_id eventid)
 	       mon_event_all[eventid].enabled;
 }
 
+int resctrl_mbm_assign_mode_show(struct kernfs_open_file *of,
+				 struct seq_file *s, void *v)
+{
+	struct rdt_resource *r = rdt_kn_parent_priv(of->kn);
+	bool enabled;
+
+	mutex_lock(&rdtgroup_mutex);
+	enabled = resctrl_arch_mbm_cntr_assign_enabled(r);
+
+	if (r->mon.mbm_cntr_assignable) {
+		if (enabled)
+			seq_puts(s, "[mbm_event]\n");
+		else
+			seq_puts(s, "[default]\n");
+
+		if (!IS_ENABLED(CONFIG_RESCTRL_ASSIGN_FIXED)) {
+			if (enabled)
+				seq_puts(s, "default\n");
+			else
+				seq_puts(s, "mbm_event\n");
+		}
+	} else {
+		seq_puts(s, "[default]\n");
+	}
+
+	mutex_unlock(&rdtgroup_mutex);
+
+	return 0;
+}
+
 /**
  * resctrl_mon_resource_init() - Initialise global monitoring structures.
  *
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index b6ab10704993..144585a85996 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -975,7 +975,7 @@ static int rdt_last_cmd_status_show(struct kernfs_open_file *of,
 	return 0;
 }
 
-static void *rdt_kn_parent_priv(struct kernfs_node *kn)
+void *rdt_kn_parent_priv(struct kernfs_node *kn)
 {
 	/*
 	 * The parent pointer is only valid within RCU section since it can be
@@ -1911,6 +1911,13 @@ static struct rftype res_common_files[] = {
 		.seq_show	= mbm_local_bytes_config_show,
 		.write		= mbm_local_bytes_config_write,
 	},
+	{
+		.name		= "mbm_assign_mode",
+		.mode		= 0444,
+		.kf_ops		= &rdtgroup_kf_single_ops,
+		.seq_show	= resctrl_mbm_assign_mode_show,
+		.fflags		= RFTYPE_MON_INFO | RFTYPE_RES_CACHE,
+	},
 	{
 		.name		= "cpus",
 		.mode		= 0644,

---

## [12] Babu Moger — 2025-09-05
*Subject: [PATCH v18 11/33] fs/resctrl: Add resctrl file to display number of assignable counters*

The "mbm_event" counter assignment mode allows users to assign a hardware
counter to an RMID, event pair and monitor bandwidth usage as long as it is
assigned.  The hardware continues to track the assigned counter until it is
explicitly unassigned by the user.

Create 'num_mbm_cntrs' resctrl file that displays the number of counters
supported in each domain. 'num_mbm_cntrs' is only visible to user space
when the system supports "mbm_event" mode.

Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: Added Reviewed-by tag.

v17: Moved resctrl_num_mbm_cntrs_show() to fs/resctrl/monitor.c.
     Removed Reviewed-by tag.

v16: Added Reviewed-by tag.

v15: Changed "assign a hardware counter ID" to "assign a hardware counter"
     in couple of places.

v14: Minor update to changelog and user doc (resctrl.rst).
     Changed subject line to fs/resctrl.

v13: Updated the changelog.
     Added fflags RFTYPE_RES_CACHE to the file num_mbm_cntrs.
     Replaced seq_puts from seq_putc where applicable.
     Resolved conflicts caused by the recent FS/ARCH code restructure.
     The files monitor.c/rdtgroup.c have been split between FS and ARCH directories.

v12: Changed the code to display the max supported monitoring counters in
     each domain. Also updated the documentation.
     Resolved the conflict with the latest code.

v11: Renamed rdtgroup_num_mbm_cntrs_show() to resctrl_num_mbm_cntrs_show().
     Few monor text updates.

v10: No changes.

v9: Updated user document based on the comments.
    Will add a new file available_mbm_cntrs later in the series.

v8: Commit message update and documentation update.

v7: Minor commit log text changes.

v6: No changes.

v5: Changed the display name from num_cntrs to num_mbm_cntrs.
    Updated the commit message.
    Moved the patch after mbm_mode is introduced.

v4: Changed the counter name to num_cntrs. And few text changes.

v3: Changed the field name to mbm_assign_cntrs.

v2: Changed the field name to mbm_assignable_counters from abmc_counter.
---
 Documentation/filesystems/resctrl.rst | 11 +++++++++++
 fs/resctrl/internal.h                 |  2 ++
 fs/resctrl/monitor.c                  | 26 ++++++++++++++++++++++++++
 fs/resctrl/rdtgroup.c                 |  6 ++++++
 4 files changed, 45 insertions(+)

diff --git a/Documentation/filesystems/resctrl.rst b/Documentation/filesystems/resctrl.rst
index b692829fec5f..4eb27530be6f 100644
--- a/Documentation/filesystems/resctrl.rst
+++ b/Documentation/filesystems/resctrl.rst
@@ -288,6 +288,17 @@ with the following files:
 	result in misleading values or display "Unavailable" if no counter is assigned
 	to the event.
 
+"num_mbm_cntrs":
+	The maximum number of counters (total of available and assigned counters) in
+	each domain when the system supports mbm_event mode.
+
+	For example, on a system with maximum of 32 memory bandwidth monitoring
+	counters in each of its L3 domains:
+	::
+
+	  # cat /sys/fs/resctrl/info/L3_MON/num_mbm_cntrs
+	  0=32;1=32
+
 "max_threshold_occupancy":
 		Read/write file provides the largest value (in
 		bytes) at which a previously used LLC_occupancy
diff --git a/fs/resctrl/internal.h b/fs/resctrl/internal.h
index 4fbc809b11a6..e4d7aa1a8fd1 100644
--- a/fs/resctrl/internal.h
+++ b/fs/resctrl/internal.h
@@ -386,6 +386,8 @@ void *rdt_kn_parent_priv(struct kernfs_node *kn);
 
 int resctrl_mbm_assign_mode_show(struct kernfs_open_file *of, struct seq_file *s, void *v);
 
+int resctrl_num_mbm_cntrs_show(struct kernfs_open_file *of, struct seq_file *s, void *v);
+
 #ifdef CONFIG_RESCTRL_FS_PSEUDO_LOCK
 int rdtgroup_locksetup_enter(struct rdtgroup *rdtgrp);
 
diff --git a/fs/resctrl/monitor.c b/fs/resctrl/monitor.c
index 379166134f5a..667770ecfd78 100644
--- a/fs/resctrl/monitor.c
+++ b/fs/resctrl/monitor.c
@@ -914,6 +914,30 @@ int resctrl_mbm_assign_mode_show(struct kernfs_open_file *of,
 	return 0;
 }
 
+int resctrl_num_mbm_cntrs_show(struct kernfs_open_file *of,
+			       struct seq_file *s, void *v)
+{
+	struct rdt_resource *r = rdt_kn_parent_priv(of->kn);
+	struct rdt_mon_domain *dom;
+	bool sep = false;
+
+	cpus_read_lock();
+	mutex_lock(&rdtgroup_mutex);
+
+	list_for_each_entry(dom, &r->mon_domains, hdr.list) {
+		if (sep)
+			seq_putc(s, ';');
+
+		seq_printf(s, "%d=%d", dom->hdr.id, r->mon.num_mbm_cntrs);
+		sep = true;
+	}
+	seq_putc(s, '\n');
+
+	mutex_unlock(&rdtgroup_mutex);
+	cpus_read_unlock();
+	return 0;
+}
+
 /**
  * resctrl_mon_resource_init() - Initialise global monitoring structures.
  *
@@ -959,6 +983,8 @@ int resctrl_mon_resource_init(void)
 			resctrl_enable_mon_event(QOS_L3_MBM_TOTAL_EVENT_ID);
 		if (!resctrl_is_mon_event_enabled(QOS_L3_MBM_LOCAL_EVENT_ID))
 			resctrl_enable_mon_event(QOS_L3_MBM_LOCAL_EVENT_ID);
+		resctrl_file_fflags_init("num_mbm_cntrs",
+					 RFTYPE_MON_INFO | RFTYPE_RES_CACHE);
 	}
 
 	return 0;
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index 144585a85996..9d95d01da3f9 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -1836,6 +1836,12 @@ static struct rftype res_common_files[] = {
 		.seq_show	= rdt_default_ctrl_show,
 		.fflags		= RFTYPE_CTRL_INFO | RFTYPE_RES_CACHE,
 	},
+	{
+		.name		= "num_mbm_cntrs",
+		.mode		= 0444,
+		.kf_ops		= &rdtgroup_kf_single_ops,
+		.seq_show	= resctrl_num_mbm_cntrs_show,
+	},
 	{
 		.name		= "min_cbm_bits",
 		.mode		= 0444,

---

## [13] Babu Moger — 2025-09-05
*Subject: [PATCH v18 12/33] fs/resctrl: Introduce mbm_cntr_cfg to track assignable counters per domain*

The "mbm_event" counter assignment mode allows users to assign a hardware
counter to an RMID, event pair and monitor bandwidth usage as long as it is
assigned.  The hardware continues to track the assigned counter until it is
explicitly unassigned by the user. Counters are assigned/unassigned at
monitoring domain level.

Manage a monitoring domain's hardware counters using a per monitoring
domain array of struct mbm_cntr_cfg that is indexed by the hardware
counter ID. A hardware counter's configuration contains the MBM event
ID and points to the monitoring group that it is assigned to, with a NULL
pointer meaning that the hardware counter is available for assignment.

There is no direct way to determine which hardware counters are assigned
to a particular monitoring group. Check every entry of every hardware
counter configuration array in every monitoring domain to query which
MBM events of a monitoring group is tracked by hardware. Such queries are
acceptable because of a very small number of assignable counters (32
to 64).

Suggested-by: Peter Newman <peternewman@google.com>
Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: No changes.

v17: No changes.

v16: Added Reviewed-by tag.

v15: Minor changelog update.
     Removed evt_cfg from struct mbm_cntr_cfg based on the discussion.
     https://lore.kernel.org/lkml/887bad33-7f4a-4b6d-95a7-fdfe0451f42b@intel.com/

v14: Updated code documentation and changelog.
     Fixed up the indentation in resctrl.h.
     Changed subject line to fs/resctrl.

v13: Resolved conflicts caused by the recent FS/ARCH code restructure.
     The files monitor.c/rdtgroup.c have been split between FS and ARCH directories.

v12: Fixed the struct mbm_cntr_cfg code documentation.
     Removed few strange charactors in changelog.
     Added the counter range for better understanding.
     Moved the struct mbm_cntr_cfg definition to resctrl/internal.h as
     suggested by James.

v11: Refined the change log based on Reinette's feedback.
     Fixed few style issues.

v10: Patch changed completely to handle the counters at domain level.
     https://lore.kernel.org/lkml/CALPaoCj+zWq1vkHVbXYP0znJbe6Ke3PXPWjtri5AFgD9cQDCUg@mail.gmail.com/
     Removed Reviewed-by tag.
     Did not see the need to add cntr_id in mbm_state structure. Not used in the code.

v9: Added Reviewed-by tag. No other changes.

v8: Minor commit message changes.

v7: Added check mbm_cntr_assignable for allocating bitmap mbm_cntr_map

v6: New patch to add domain level assignment.
---
 fs/resctrl/rdtgroup.c   |  8 ++++++++
 include/linux/resctrl.h | 15 +++++++++++++++
 2 files changed, 23 insertions(+)

diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index 9d95d01da3f9..61f7b68f2273 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -4029,6 +4029,7 @@ static void domain_destroy_mon_state(struct rdt_mon_domain *d)
 {
 	int idx;
 
+	kfree(d->cntr_cfg);
 	bitmap_free(d->rmid_busy_llc);
 	for_each_mbm_idx(idx) {
 		kfree(d->mbm_states[idx]);
@@ -4112,6 +4113,13 @@ static int domain_setup_mon_state(struct rdt_resource *r, struct rdt_mon_domain
 			goto cleanup;
 	}
 
+	if (resctrl_is_mbm_enabled() && r->mon.mbm_cntr_assignable) {
+		tsize = sizeof(*d->cntr_cfg);
+		d->cntr_cfg = kcalloc(r->mon.num_mbm_cntrs, tsize, GFP_KERNEL);
+		if (!d->cntr_cfg)
+			goto cleanup;
+	}
+
 	return 0;
 cleanup:
 	bitmap_free(d->rmid_busy_llc);
diff --git a/include/linux/resctrl.h b/include/linux/resctrl.h
index 919806122c50..e013caba6641 100644
--- a/include/linux/resctrl.h
+++ b/include/linux/resctrl.h
@@ -156,6 +156,18 @@ struct rdt_ctrl_domain {
 	u32				*mbps_val;
 };
 
+/**
+ * struct mbm_cntr_cfg - Assignable counter configuration.
+ * @evtid:		MBM event to which the counter is assigned. Only valid
+ *			if @rdtgroup is not NULL.
+ * @rdtgrp:		resctrl group assigned to the counter. NULL if the
+ *			counter is free.
+ */
+struct mbm_cntr_cfg {
+	enum resctrl_event_id	evtid;
+	struct rdtgroup		*rdtgrp;
+};
+
 /**
  * struct rdt_mon_domain - group of CPUs sharing a resctrl monitor resource
  * @hdr:		common header for different domain types
@@ -168,6 +180,8 @@ struct rdt_ctrl_domain {
  * @cqm_limbo:		worker to periodically read CQM h/w counters
  * @mbm_work_cpu:	worker CPU for MBM h/w counters
  * @cqm_work_cpu:	worker CPU for CQM h/w counters
+ * @cntr_cfg:		array of assignable counters' configuration (indexed
+ *			by counter ID)
  */
 struct rdt_mon_domain {
 	struct rdt_domain_hdr		hdr;
@@ -178,6 +192,7 @@ struct rdt_mon_domain {
 	struct delayed_work		cqm_limbo;
 	int				mbm_work_cpu;
 	int				cqm_work_cpu;
+	struct mbm_cntr_cfg		*cntr_cfg;
 };
 
 /**

---

## [14] Babu Moger — 2025-09-05
*Subject: [PATCH v18 13/33] fs/resctrl: Introduce interface to display number of free MBM counters*

Introduce the "available_mbm_cntrs" resctrl file to display the number of
counters available for assignment in each domain when "mbm_event" mode is
enabled.

Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: Added Reviewed-by tag.

v17: Moved resctrl_available_mbm_cntrs_show() to fs/resctrl/monitor.c.
     Removed the Reviewed-by tag.

v16: Added Reviewed-by tag.

v15: Minor changelog text update.
     Minor resctrl.rst text update and corrected the error text in
     resctrl_available_mbm_cntrs_show().
     Changed the goto label to out_unlock for consistency.

v14: Minor changelog update.
     Changed subject line to fs/resctrl.

v13: Resolved conflicts caused by the recent FS/ARCH code restructure.
     The files monitor.c and rdtgroup.c file has now been split between
     the FS and ARCH directories.

v12: Minor change to change log.
     Updated the documentation text with an example.
     Replaced seq_puts(s, ";") with seq_putc(s, ';');
     Added missing rdt_last_cmd_clear() in resctrl_available_mbm_cntrs_show().

v11: Rename rdtgroup_available_mbm_cntrs_show() to resctrl_available_mbm_cntrs_show().
     Few minor text changes.

v10: Patch changed to handle the counters at domain level.
     https://lore.kernel.org/lkml/CALPaoCj+zWq1vkHVbXYP0znJbe6Ke3PXPWjtri5AFgD9cQDCUg@mail.gmail.com/
     So, display logic also changed now.

v9: New patch
---
 Documentation/filesystems/resctrl.rst | 11 +++++++
 fs/resctrl/internal.h                 |  3 ++
 fs/resctrl/monitor.c                  | 44 +++++++++++++++++++++++++++
 fs/resctrl/rdtgroup.c                 |  6 ++++
 4 files changed, 64 insertions(+)

diff --git a/Documentation/filesystems/resctrl.rst b/Documentation/filesystems/resctrl.rst
index 4eb27530be6f..446736dbd97f 100644
--- a/Documentation/filesystems/resctrl.rst
+++ b/Documentation/filesystems/resctrl.rst
@@ -299,6 +299,17 @@ with the following files:
 	  # cat /sys/fs/resctrl/info/L3_MON/num_mbm_cntrs
 	  0=32;1=32
 
+"available_mbm_cntrs":
+	The number of counters available for assignment in each domain when mbm_event
+	mode is enabled on the system.
+
+	For example, on a system with 30 available [hardware] assignable counters
+	in each of its L3 domains:
+	::
+
+	  # cat /sys/fs/resctrl/info/L3_MON/available_mbm_cntrs
+	  0=30;1=30
+
 "max_threshold_occupancy":
 		Read/write file provides the largest value (in
 		bytes) at which a previously used LLC_occupancy
diff --git a/fs/resctrl/internal.h b/fs/resctrl/internal.h
index e4d7aa1a8fd1..35a8bad8ca75 100644
--- a/fs/resctrl/internal.h
+++ b/fs/resctrl/internal.h
@@ -388,6 +388,9 @@ int resctrl_mbm_assign_mode_show(struct kernfs_open_file *of, struct seq_file *s
 
 int resctrl_num_mbm_cntrs_show(struct kernfs_open_file *of, struct seq_file *s, void *v);
 
+int resctrl_available_mbm_cntrs_show(struct kernfs_open_file *of, struct seq_file *s,
+				     void *v);
+
 #ifdef CONFIG_RESCTRL_FS_PSEUDO_LOCK
 int rdtgroup_locksetup_enter(struct rdtgroup *rdtgrp);
 
diff --git a/fs/resctrl/monitor.c b/fs/resctrl/monitor.c
index 667770ecfd78..4185f2a4ba89 100644
--- a/fs/resctrl/monitor.c
+++ b/fs/resctrl/monitor.c
@@ -938,6 +938,48 @@ int resctrl_num_mbm_cntrs_show(struct kernfs_open_file *of,
 	return 0;
 }
 
+int resctrl_available_mbm_cntrs_show(struct kernfs_open_file *of,
+				     struct seq_file *s, void *v)
+{
+	struct rdt_resource *r = rdt_kn_parent_priv(of->kn);
+	struct rdt_mon_domain *dom;
+	bool sep = false;
+	u32 cntrs, i;
+	int ret = 0;
+
+	cpus_read_lock();
+	mutex_lock(&rdtgroup_mutex);
+
+	rdt_last_cmd_clear();
+
+	if (!resctrl_arch_mbm_cntr_assign_enabled(r)) {
+		rdt_last_cmd_puts("mbm_event counter assignment mode is not enabled\n");
+		ret = -EINVAL;
+		goto out_unlock;
+	}
+
+	list_for_each_entry(dom, &r->mon_domains, hdr.list) {
+		if (sep)
+			seq_putc(s, ';');
+
+		cntrs = 0;
+		for (i = 0; i < r->mon.num_mbm_cntrs; i++) {
+			if (!dom->cntr_cfg[i].rdtgrp)
+				cntrs++;
+		}
+
+		seq_printf(s, "%d=%u", dom->hdr.id, cntrs);
+		sep = true;
+	}
+	seq_putc(s, '\n');
+
+out_unlock:
+	mutex_unlock(&rdtgroup_mutex);
+	cpus_read_unlock();
+
+	return ret;
+}
+
 /**
  * resctrl_mon_resource_init() - Initialise global monitoring structures.
  *
@@ -985,6 +1027,8 @@ int resctrl_mon_resource_init(void)
 			resctrl_enable_mon_event(QOS_L3_MBM_LOCAL_EVENT_ID);
 		resctrl_file_fflags_init("num_mbm_cntrs",
 					 RFTYPE_MON_INFO | RFTYPE_RES_CACHE);
+		resctrl_file_fflags_init("available_mbm_cntrs",
+					 RFTYPE_MON_INFO | RFTYPE_RES_CACHE);
 	}
 
 	return 0;
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index 61f7b68f2273..2e1d0a2703da 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -1822,6 +1822,12 @@ static struct rftype res_common_files[] = {
 		.seq_show	= rdt_mon_features_show,
 		.fflags		= RFTYPE_MON_INFO,
 	},
+	{
+		.name		= "available_mbm_cntrs",
+		.mode		= 0444,
+		.kf_ops		= &rdtgroup_kf_single_ops,
+		.seq_show	= resctrl_available_mbm_cntrs_show,
+	},
 	{
 		.name		= "num_rmids",
 		.mode		= 0444,

---

## [15] Babu Moger — 2025-09-05
*Subject: [PATCH v18 14/33] x86/resctrl: Add data structures and definitions for ABMC assignment*

The ABMC feature allows users to assign a hardware counter to an RMID,
event pair and monitor bandwidth usage as long as it is assigned. The
hardware continues to track the assigned counter until it is explicitly
unassigned by the user.

The ABMC feature implements an MSR L3_QOS_ABMC_CFG (C000_03FDh).
ABMC counter assignment is done by setting the counter id, bandwidth
source (RMID) and bandwidth configuration.

Attempts to read or write the MSR when ABMC is not enabled will result
in a #GP(0) exception.

Introduce the data structures and definitions for MSR L3_QOS_ABMC_CFG
(0xC000_03FDh):
=========================================================================
Bits 	Mnemonic	Description			Access Reset
							Type   Value
=========================================================================
63 	CfgEn 		Configuration Enable 		R/W 	0

62 	CtrEn 		Enable/disable counting		R/W 	0

61:53 	– 		Reserved 			MBZ 	0

52:48 	CtrID 		Counter Identifier		R/W	0

47 	IsCOS		BwSrc field is a CLOSID		R/W	0
			(not an RMID)

46:44 	–		Reserved			MBZ	0

43:32	BwSrc		Bandwidth Source		R/W	0
			(RMID or CLOSID)

31:0	BwType		Bandwidth configuration		R/W	0
			tracked by the CtrID
==========================================================================

The ABMC feature details are documented in APM [1] available from [2].
[1] AMD64 Architecture Programmer's Manual Volume 2: System Programming
Publication # 24593 Revision 3.41 section 19.3.3.3 Assignable Bandwidth
Monitoring (ABMC).

Link: https://bugzilla.kernel.org/show_bug.cgi?id=206537 # [2]
Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: No code changes. Updated the text about the Link.

v17: No changes.

v16: Added Reviewed-by tag.

v15: Minor changelog update.

v14: Removed BMEC reference internal.h.
     Updated the changelog and code documentation.

v13: Removed the Reviewed-by tag as there is commit log change to remove
     BMEC reference.

v12: No changes.

v11: No changes.

v10: No changes.

v9: Removed the references of L3_QOS_ABMC_DSC.
    Text changes about configuration in kernel doc.

v8: Update the configuration notes in kernel_doc.
    Few commit message update.

v7: Removed the reference of L3_QOS_ABMC_DSC as it is not used anymore.
    Moved the configuration notes to kernel_doc.
    Adjusted the tabs for l3_qos_abmc_cfg and checkpatch seems happy.

v6: Removed all the fs related changes.
    Added note on CfgEn,CtrEn.
    Removed the definitions which are not used.
    Removed cntr_id initialization.

v5: Moved assignment flags here (path 10/19 of v4).
    Added MON_CNTR_UNSET definition to initialize cntr_id's.
    More details in commit log.
    Renamed few fields in l3_qos_abmc_cfg for readability.

v4: Added more descriptions.
    Changed the name abmc_ctr_id to ctr_id.
    Added L3_QOS_ABMC_DSC. Used for reading the configuration.

v3: No changes.

v2: No changes.
---
 arch/x86/include/asm/msr-index.h       |  1 +
 arch/x86/kernel/cpu/resctrl/internal.h | 36 ++++++++++++++++++++++++++
 2 files changed, 37 insertions(+)

diff --git a/arch/x86/include/asm/msr-index.h b/arch/x86/include/asm/msr-index.h
index 18222527b0ee..48230814098d 100644
--- a/arch/x86/include/asm/msr-index.h
+++ b/arch/x86/include/asm/msr-index.h
@@ -1232,6 +1232,7 @@
 /* - AMD: */
 #define MSR_IA32_MBA_BW_BASE		0xc0000200
 #define MSR_IA32_SMBA_BW_BASE		0xc0000280
+#define MSR_IA32_L3_QOS_ABMC_CFG	0xc00003fd
 #define MSR_IA32_L3_QOS_EXT_CFG		0xc00003ff
 #define MSR_IA32_EVT_CFG_BASE		0xc0000400
 
diff --git a/arch/x86/kernel/cpu/resctrl/internal.h b/arch/x86/kernel/cpu/resctrl/internal.h
index a79a487e639c..6bf6042f11b6 100644
--- a/arch/x86/kernel/cpu/resctrl/internal.h
+++ b/arch/x86/kernel/cpu/resctrl/internal.h
@@ -164,6 +164,42 @@ union cpuid_0x10_x_edx {
 	unsigned int full;
 };
 
+/*
+ * ABMC counters are configured by writing to L3_QOS_ABMC_CFG.
+ *
+ * @bw_type		: Event configuration that represent the memory
+ *			  transactions being tracked by the @cntr_id.
+ * @bw_src		: Bandwidth source (RMID or CLOSID).
+ * @reserved1		: Reserved.
+ * @is_clos		: @bw_src field is a CLOSID (not an RMID).
+ * @cntr_id		: Counter identifier.
+ * @reserved		: Reserved.
+ * @cntr_en		: Counting enable bit.
+ * @cfg_en		: Configuration enable bit.
+ *
+ * Configuration and counting:
+ * Counter can be configured across multiple writes to MSR. Configuration
+ * is applied only when @cfg_en = 1. Counter @cntr_id is reset when the
+ * configuration is applied.
+ * @cfg_en = 1, @cntr_en = 0 : Apply @cntr_id configuration but do not
+ *                             count events.
+ * @cfg_en = 1, @cntr_en = 1 : Apply @cntr_id configuration and start
+ *                             counting events.
+ */
+union l3_qos_abmc_cfg {
+	struct {
+		unsigned long bw_type  :32,
+			      bw_src   :12,
+			      reserved1: 3,
+			      is_clos  : 1,
+			      cntr_id  : 5,
+			      reserved : 9,
+			      cntr_en  : 1,
+			      cfg_en   : 1;
+	} split;
+	unsigned long full;
+};
+
 void rdt_ctrl_update(void *arg);
 
 int rdt_get_mon_l3_config(struct rdt_resource *r);

---

## [16] Babu Moger — 2025-09-05
*Subject: [PATCH v18 15/33] fs/resctrl: Introduce event configuration field in struct mon_evt*

When supported, mbm_event counter assignment mode allows the user to
configure events to track specific types of memory transactions.

Introduce the evt_cfg field in struct mon_evt to define the type of memory
transactions tracked by a monitoring event. Also add a helper function to
get the evt_cfg value.

Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: Added Reviewed-by tag.

v17: Updated evt_cfg to use r->mon.mbm_cfg_mask.
     Removed Reviewed-by tag since the patch was modified slightly.

v16: Added Reviewed-by tag.

v15: Updated the changelog.
     Removed resctrl_set_mon_evt_cfg().
     Moved the event initialization to resctrl_mon_resource_init().

v14: This is updated patch from previous patch.
     https://lore.kernel.org/lkml/95b7f4e9d72773e8fda327fc80b429646efc3a8a.1747349530.git.babu.moger@amd.com/
     Removed mbm_mode as it is not required anymore.
     Added resctrl_get_mon_evt_cfg() and resctrl_set_mon_evt_cfg().

v13: New patch to handle different event configuration types with
     mbm_cntr_assign mode.
---
 fs/resctrl/internal.h   |  5 +++++
 fs/resctrl/monitor.c    | 10 ++++++++++
 include/linux/resctrl.h |  2 ++
 3 files changed, 17 insertions(+)

diff --git a/fs/resctrl/internal.h b/fs/resctrl/internal.h
index 35a8bad8ca75..874b59f52d13 100644
--- a/fs/resctrl/internal.h
+++ b/fs/resctrl/internal.h
@@ -56,6 +56,10 @@ static inline struct rdt_fs_context *rdt_fc2context(struct fs_context *fc)
  * @evtid:		event id
  * @rid:		resource id for this event
  * @name:		name of the event
+ * @evt_cfg:		Event configuration value that represents the
+ *			memory transactions (e.g., READS_TO_LOCAL_MEM,
+ *			READS_TO_REMOTE_MEM) being tracked by @evtid.
+ *			Only valid if @evtid is an MBM event.
  * @configurable:	true if the event is configurable
  * @enabled:		true if the event is enabled
  */
@@ -63,6 +67,7 @@ struct mon_evt {
 	enum resctrl_event_id	evtid;
 	enum resctrl_res_level	rid;
 	char			*name;
+	u32			evt_cfg;
 	bool			configurable;
 	bool			enabled;
 };
diff --git a/fs/resctrl/monitor.c b/fs/resctrl/monitor.c
index 4185f2a4ba89..8c6e44e0e57c 100644
--- a/fs/resctrl/monitor.c
+++ b/fs/resctrl/monitor.c
@@ -884,6 +884,11 @@ bool resctrl_is_mon_event_enabled(enum resctrl_event_id eventid)
 	       mon_event_all[eventid].enabled;
 }
 
+u32 resctrl_get_mon_evt_cfg(enum resctrl_event_id evtid)
+{
+	return mon_event_all[evtid].evt_cfg;
+}
+
 int resctrl_mbm_assign_mode_show(struct kernfs_open_file *of,
 				 struct seq_file *s, void *v)
 {
@@ -1025,6 +1030,11 @@ int resctrl_mon_resource_init(void)
 			resctrl_enable_mon_event(QOS_L3_MBM_TOTAL_EVENT_ID);
 		if (!resctrl_is_mon_event_enabled(QOS_L3_MBM_LOCAL_EVENT_ID))
 			resctrl_enable_mon_event(QOS_L3_MBM_LOCAL_EVENT_ID);
+		mon_event_all[QOS_L3_MBM_TOTAL_EVENT_ID].evt_cfg = r->mon.mbm_cfg_mask;
+		mon_event_all[QOS_L3_MBM_LOCAL_EVENT_ID].evt_cfg = r->mon.mbm_cfg_mask &
+								   (READS_TO_LOCAL_MEM |
+								    READS_TO_LOCAL_S_MEM |
+								    NON_TEMP_WRITE_TO_LOCAL_MEM);
 		resctrl_file_fflags_init("num_mbm_cntrs",
 					 RFTYPE_MON_INFO | RFTYPE_RES_CACHE);
 		resctrl_file_fflags_init("available_mbm_cntrs",
diff --git a/include/linux/resctrl.h b/include/linux/resctrl.h
index e013caba6641..87daa4ca312d 100644
--- a/include/linux/resctrl.h
+++ b/include/linux/resctrl.h
@@ -409,6 +409,8 @@ static inline bool resctrl_is_mbm_event(enum resctrl_event_id eventid)
 		eventid <= QOS_L3_MBM_LOCAL_EVENT_ID);
 }
 
+u32 resctrl_get_mon_evt_cfg(enum resctrl_event_id eventid);
+
 /* Iterate over all memory bandwidth events */
 #define for_each_mbm_event_id(eventid)				\
 	for (eventid = QOS_L3_MBM_TOTAL_EVENT_ID;		\

---

## [17] Babu Moger — 2025-09-05
*Subject: [PATCH v18 16/33] x86,fs/resctrl: Implement resctrl_arch_config_cntr() to assign a counter with ABMC*

The ABMC feature allows users to assign a hardware counter to an RMID,
event pair and monitor bandwidth usage as long as it is assigned. The
hardware continues to track the assigned counter until it is explicitly
unassigned by the user.

Implement an x86 architecture-specific handler to configure a counter. This
architecture specific handler is called by resctrl fs when a counter is
assigned or unassigned as well as when an already assigned counter's
configuration should be updated. Configure counters by writing to the
L3_QOS_ABMC_CFG MSR, specifying the counter ID, bandwidth source (RMID),
and event configuration.

The ABMC feature details are documented in APM [1] available from [2].
[1] AMD64 Architecture Programmer's Manual Volume 2: System Programming
    Publication # 24593 Revision 3.41 section 19.3.3.3 Assignable Bandwidth
    Monitoring (ABMC).

Link: https://bugzilla.kernel.org/show_bug.cgi?id=206537 # [2]
Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: Added the text about the documentation link.

v17: Added Reviewed-by tag.

v16: Updated the changelog.
     Reset the architectural state in resctrl_arch_config_cntr() in both
     assign and unassign cases.

v15: Minor changelog update.
     Added few code comments in include/linux/resctrl.h.

v14: Removed evt_cfg parameter in resctrl_arch_config_cntr(). Get evt_cfg
     only when assign is required.
     Minor update to changelog.

v13: Moved resctrl_arch_config_cntr() prototype to include/linux/resctrl.h.
     Changed resctrl_arch_config_cntr() to retun void from int.
     Updated the kernal doc for the prototype.
     Updated the code comment.

12: Added the check to reset the architecture-specific state only when
     assign is requested.
     Added evt_cfg as the parameter as the user will be passing the event
     configuration from /info/L3_MON/event_configs/.

v11: Moved resctrl_arch_assign_cntr() and resctrl_abmc_config_one_amd() to
     monitor.c.
     Added the code to reset the arch state in resctrl_arch_assign_cntr().
     Also removed resctrl_arch_reset_rmid() inside IPI as the counters are
     reset from the callers.
     Re-wrote commit message.

v10: Added call resctrl_arch_reset_rmid() to reset the RMID in the domain
     inside IPI call.
     SMP and non-SMP call support is not required in resctrl_arch_config_cntr
     with new domain specific assign approach/data structure.
     Commit message update.

v9: Removed the code to reset the architectural state. It will done
    in another patch.

v8: Rename resctrl_arch_assign_cntr to resctrl_arch_config_cntr.

v7: Separated arch and fs functions. This patch only has arch implementation.
    Added struct rdt_resource to the interface resctrl_arch_assign_cntr.
    Rename rdtgroup_abmc_cfg() to resctrl_abmc_config_one_amd().

v6: Removed mbm_cntr_alloc() from this patch to keep fs and arch code
    separate.
    Added code to update the counter assignment at domain level.

v5: Few name changes to match cntr_id.
    Changed the function names to
      rdtgroup_assign_cntr
      resctr_arch_assign_cntr
      More comments on commit log.
      Added function summary.

v4: Commit message update.
      User bitmap APIs where applicable.
      Changed the interfaces considering MPAM(arm).
      Added domain specific assignment.

v3: Removed the static from the prototype of rdtgroup_assign_abmc.
      The function is not called directly from user anymore. These
      changes are related to global assignment interface.

v2: Minor text changes in commit message.
---
 arch/x86/kernel/cpu/resctrl/monitor.c | 36 +++++++++++++++++++++++++++
 include/linux/resctrl.h               | 19 ++++++++++++++
 2 files changed, 55 insertions(+)

diff --git a/arch/x86/kernel/cpu/resctrl/monitor.c b/arch/x86/kernel/cpu/resctrl/monitor.c
index cce35a0ad455..ed295a6c5e66 100644
--- a/arch/x86/kernel/cpu/resctrl/monitor.c
+++ b/arch/x86/kernel/cpu/resctrl/monitor.c
@@ -444,3 +444,39 @@ bool resctrl_arch_mbm_cntr_assign_enabled(struct rdt_resource *r)
 {
 	return resctrl_to_arch_res(r)->mbm_cntr_assign_enabled;
 }
+
+static void resctrl_abmc_config_one_amd(void *info)
+{
+	union l3_qos_abmc_cfg *abmc_cfg = info;
+
+	wrmsrl(MSR_IA32_L3_QOS_ABMC_CFG, abmc_cfg->full);
+}
+
+/*
+ * Send an IPI to the domain to assign the counter to RMID, event pair.
+ */
+void resctrl_arch_config_cntr(struct rdt_resource *r, struct rdt_mon_domain *d,
+			      enum resctrl_event_id evtid, u32 rmid, u32 closid,
+			      u32 cntr_id, bool assign)
+{
+	struct rdt_hw_mon_domain *hw_dom = resctrl_to_arch_mon_dom(d);
+	union l3_qos_abmc_cfg abmc_cfg = { 0 };
+	struct arch_mbm_state *am;
+
+	abmc_cfg.split.cfg_en = 1;
+	abmc_cfg.split.cntr_en = assign ? 1 : 0;
+	abmc_cfg.split.cntr_id = cntr_id;
+	abmc_cfg.split.bw_src = rmid;
+	if (assign)
+		abmc_cfg.split.bw_type = resctrl_get_mon_evt_cfg(evtid);
+
+	smp_call_function_any(&d->hdr.cpu_mask, resctrl_abmc_config_one_amd, &abmc_cfg, 1);
+
+	/*
+	 * The hardware counter is reset (because cfg_en == 1) so there is no
+	 * need to record initial non-zero counts.
+	 */
+	am = get_arch_mbm_state(hw_dom, rmid, evtid);
+	if (am)
+		memset(am, 0, sizeof(*am));
+}
diff --git a/include/linux/resctrl.h b/include/linux/resctrl.h
index 87daa4ca312d..50e38445183a 100644
--- a/include/linux/resctrl.h
+++ b/include/linux/resctrl.h
@@ -594,6 +594,25 @@ void resctrl_arch_reset_rmid_all(struct rdt_resource *r, struct rdt_mon_domain *
  */
 void resctrl_arch_reset_all_ctrls(struct rdt_resource *r);
 
+/**
+ * resctrl_arch_config_cntr() - Configure the counter with its new RMID
+ *				and event details.
+ * @r:			Resource structure.
+ * @d:			The domain in which counter with ID @cntr_id should be configured.
+ * @evtid:		Monitoring event type (e.g., QOS_L3_MBM_TOTAL_EVENT_ID
+ *			or QOS_L3_MBM_LOCAL_EVENT_ID).
+ * @rmid:		RMID.
+ * @closid:		CLOSID.
+ * @cntr_id:		Counter ID to configure.
+ * @assign:		True to assign the counter or update an existing assignment,
+ *			false to unassign the counter.
+ *
+ * This can be called from any CPU.
+ */
+void resctrl_arch_config_cntr(struct rdt_resource *r, struct rdt_mon_domain *d,
+			      enum resctrl_event_id evtid, u32 rmid, u32 closid,
+			      u32 cntr_id, bool assign);
+
 extern unsigned int resctrl_rmid_realloc_threshold;
 extern unsigned int resctrl_rmid_realloc_limit;

---

## [18] Babu Moger — 2025-09-05
*Subject: [PATCH v18 17/33] fs/resctrl: Add the functionality to assign MBM events*

When supported, "mbm_event" counter assignment mode offers "num_mbm_cntrs"
number of counters that can be assigned to RMID, event pairs and monitor
bandwidth usage as long as it is assigned.

Add the functionality to allocate and assign a counter to an RMID, event
pair in the domain. Also, add the helper rdtgroup_assign_cntrs() to assign
counters in the group.

Log the error message "Failed to allocate counter for <event> in domain
<id>" in /sys/fs/resctrl/info/last_cmd_status if all the counters are in
use. Exit on the first failure when assigning counters across all the
domains.

Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: Added Reviewed-by tag.

v17: Minor changelog update.
     Moved all the functions from fs/resctrl/rdtgroup.c to fs/resctrl/monitor.c.
     Brought rdtgroup_assign_cntrs() in this patch from patch 28 to make compiler happy.

v16: Function renames:
     resctrl_config_cntr() -> rdtgroup_assign_cntr()
     rdtgroup_alloc_config_cntr() -> rdtgroup_alloc_assign_cntr()
     Passed struct mevt to rdtgroup_alloc_assign_cntr so it can print event name on failure.
     Minor code comment update.

v15: Updated the changelog.
     Added the check !r->mon.mbm_cntr_assignable in mbm_cntr_get() to return error.
     Removed the check to verify evt_cfg in the domain as it is not required anymore.
     https://lore.kernel.org/lkml/887bad33-7f4a-4b6d-95a7-fdfe0451f42b@intel.com/
     Return success if the counter is already assigned.
     Rename resctrl_assign_cntr_event() -> rdtgroup_assign_cntr_event().
     Removed the parameter struct rdt_resource. It can be obtained from mevt->rid.

v14: Updated the changelog little bit.
     Updated the code documentation for mbm_cntr_alloc() and  mbm_cntr_get().
     Passed struct mon_evt to resctrl_assign_cntr_event() that way to avoid
     back and forth calls to get event details.
     Updated the code documentation about the failure when counters are exhasted.
     Changed subject line to fs/resctrl.

v13: Updated changelog.
     Changed resctrl_arch_config_cntr() to return void instead of int.
     Just passing evtid is to resctrl_alloc_config_cntr() and
     resctrl_assign_cntr_event(). Event configuration value can be easily
     obtained from mon_evt list.
     Introduced new function mbm_get_mon_event() to get event configuration value.
     Added prototype descriptions to mbm_cntr_get() and mbm_cntr_alloc().
     Resolved conflicts caused by the recent FS/ARCH code restructure.
     The files monitor.c/rdtgroup.c have been split between FS and ARCH directories.

v12: Fixed typo in the subjest line.
     Replaced several counters with "num_mbm_cntrs" counters.
     Changed the check in resctrl_alloc_config_cntr() to reduce the indentation.
     Fixed the handling error on first failure.
     Added domain id and event id on failure.
     Fixed the return error override.
     Added new parameter event configuration (evt_cfg) to get the event configuration
     from user space.

v11: Patch changed again quite a bit.
     Moved the functions to monitor.c.
     Renamed rdtgroup_assign_cntr_event() to resctrl_assign_cntr_event().
     Refactored the resctrl_assign_cntr_event().
     Added functionality to exit on the first error during assignment.
     Simplified mbm_cntr_free().
     Removed the function mbm_cntr_assigned(). Will be using mbm_cntr_get() to
     figure out if the counter is assigned or not.
     Updated commit message and code comments.

v10: Patch changed completely.
     Counters are managed at the domain based on the discussion.
     https://lore.kernel.org/lkml/CALPaoCj+zWq1vkHVbXYP0znJbe6Ke3PXPWjtri5AFgD9cQDCUg@mail.gmail.com/
     Reset non-architectural MBM state.
     Commit message update.

v9: Introduced new function resctrl_config_cntr to assign the counter, update
    the bitmap and reset the architectural state.
    Taken care of error handling(freeing the counter) when assignment fails.
    Moved mbm_cntr_assigned_to_domain here as it used in this patch.
    Minor text changes.

v8: Renamed rdtgroup_assign_cntr() to rdtgroup_assign_cntr_event().
    Added the code to return the error if rdtgroup_assign_cntr_event fails.
    Moved definition of MBM_EVENT_ARRAY_INDEX to resctrl/internal.h.
    Updated typo in the comments.

v7: New patch. Moved all the FS code here.
    Merged rdtgroup_assign_cntr and rdtgroup_alloc_cntr.
    Adde new #define MBM_EVENT_ARRAY_INDEX.
---
 fs/resctrl/internal.h |   2 +
 fs/resctrl/monitor.c  | 156 ++++++++++++++++++++++++++++++++++++++++++
 2 files changed, 158 insertions(+)

diff --git a/fs/resctrl/internal.h b/fs/resctrl/internal.h
index 874b59f52d13..73cad7c17a1f 100644
--- a/fs/resctrl/internal.h
+++ b/fs/resctrl/internal.h
@@ -396,6 +396,8 @@ int resctrl_num_mbm_cntrs_show(struct kernfs_open_file *of, struct seq_file *s,
 int resctrl_available_mbm_cntrs_show(struct kernfs_open_file *of, struct seq_file *s,
 				     void *v);
 
+void rdtgroup_assign_cntrs(struct rdtgroup *rdtgrp);
+
 #ifdef CONFIG_RESCTRL_FS_PSEUDO_LOCK
 int rdtgroup_locksetup_enter(struct rdtgroup *rdtgrp);
 
diff --git a/fs/resctrl/monitor.c b/fs/resctrl/monitor.c
index 8c6e44e0e57c..3eb5a30f44fb 100644
--- a/fs/resctrl/monitor.c
+++ b/fs/resctrl/monitor.c
@@ -356,6 +356,55 @@ static struct mbm_state *get_mbm_state(struct rdt_mon_domain *d, u32 closid,
 	return state ? &state[idx] : NULL;
 }
 
+/*
+ * mbm_cntr_get() - Return the counter ID for the matching @evtid and @rdtgrp.
+ *
+ * Return:
+ * Valid counter ID on success, or -ENOENT on failure.
+ */
+static int mbm_cntr_get(struct rdt_resource *r, struct rdt_mon_domain *d,
+			struct rdtgroup *rdtgrp, enum resctrl_event_id evtid)
+{
+	int cntr_id;
+
+	if (!r->mon.mbm_cntr_assignable)
+		return -ENOENT;
+
+	if (!resctrl_is_mbm_event(evtid))
+		return -ENOENT;
+
+	for (cntr_id = 0; cntr_id < r->mon.num_mbm_cntrs; cntr_id++) {
+		if (d->cntr_cfg[cntr_id].rdtgrp == rdtgrp &&
+		    d->cntr_cfg[cntr_id].evtid == evtid)
+			return cntr_id;
+	}
+
+	return -ENOENT;
+}
+
+/*
+ * mbm_cntr_alloc() - Initialize and return a new counter ID in the domain @d.
+ * Caller must ensure that the specified event is not assigned already.
+ *
+ * Return:
+ * Valid counter ID on success, or -ENOSPC on failure.
+ */
+static int mbm_cntr_alloc(struct rdt_resource *r, struct rdt_mon_domain *d,
+			  struct rdtgroup *rdtgrp, enum resctrl_event_id evtid)
+{
+	int cntr_id;
+
+	for (cntr_id = 0; cntr_id < r->mon.num_mbm_cntrs; cntr_id++) {
+		if (!d->cntr_cfg[cntr_id].rdtgrp) {
+			d->cntr_cfg[cntr_id].rdtgrp = rdtgrp;
+			d->cntr_cfg[cntr_id].evtid = evtid;
+			return cntr_id;
+		}
+	}
+
+	return -ENOSPC;
+}
+
 static int __mon_event_count(u32 closid, u32 rmid, struct rmid_read *rr)
 {
 	int cpu = smp_processor_id();
@@ -889,6 +938,113 @@ u32 resctrl_get_mon_evt_cfg(enum resctrl_event_id evtid)
 	return mon_event_all[evtid].evt_cfg;
 }
 
+/*
+ * rdtgroup_assign_cntr() - Assign/unassign the counter ID for the event, RMID
+ * pair in the domain.
+ *
+ * Assign the counter if @assign is true else unassign the counter. Reset the
+ * associated non-architectural state.
+ */
+static void rdtgroup_assign_cntr(struct rdt_resource *r, struct rdt_mon_domain *d,
+				 enum resctrl_event_id evtid, u32 rmid, u32 closid,
+				 u32 cntr_id, bool assign)
+{
+	struct mbm_state *m;
+
+	resctrl_arch_config_cntr(r, d, evtid, rmid, closid, cntr_id, assign);
+
+	m = get_mbm_state(d, closid, rmid, evtid);
+	if (m)
+		memset(m, 0, sizeof(*m));
+}
+
+/*
+ * rdtgroup_alloc_assign_cntr() - Allocate a counter ID and assign it to the event
+ * pointed to by @mevt and the resctrl group @rdtgrp within the domain @d.
+ *
+ * Return:
+ * 0 on success, < 0 on failure.
+ */
+static int rdtgroup_alloc_assign_cntr(struct rdt_resource *r, struct rdt_mon_domain *d,
+				      struct rdtgroup *rdtgrp, struct mon_evt *mevt)
+{
+	int cntr_id;
+
+	/* No action required if the counter is assigned already. */
+	cntr_id = mbm_cntr_get(r, d, rdtgrp, mevt->evtid);
+	if (cntr_id >= 0)
+		return 0;
+
+	cntr_id = mbm_cntr_alloc(r, d, rdtgrp, mevt->evtid);
+	if (cntr_id < 0) {
+		rdt_last_cmd_printf("Failed to allocate counter for %s in domain %d\n",
+				    mevt->name, d->hdr.id);
+		return cntr_id;
+	}
+
+	rdtgroup_assign_cntr(r, d, mevt->evtid, rdtgrp->mon.rmid, rdtgrp->closid, cntr_id, true);
+
+	return 0;
+}
+
+/*
+ * rdtgroup_assign_cntr_event() - Assign a hardware counter for the event in
+ * @mevt to the resctrl group @rdtgrp. Assign counters to all domains if @d is
+ * NULL; otherwise, assign the counter to the specified domain @d.
+ *
+ * If all counters in a domain are already in use, rdtgroup_alloc_assign_cntr()
+ * will fail. The assignment process will abort at the first failure encountered
+ * during domain traversal, which may result in the event being only partially
+ * assigned.
+ *
+ * Return:
+ * 0 on success, < 0 on failure.
+ */
+static int rdtgroup_assign_cntr_event(struct rdt_mon_domain *d, struct rdtgroup *rdtgrp,
+				      struct mon_evt *mevt)
+{
+	struct rdt_resource *r = resctrl_arch_get_resource(mevt->rid);
+	int ret = 0;
+
+	if (!d) {
+		list_for_each_entry(d, &r->mon_domains, hdr.list) {
+			ret = rdtgroup_alloc_assign_cntr(r, d, rdtgrp, mevt);
+			if (ret)
+				return ret;
+		}
+	} else {
+		ret = rdtgroup_alloc_assign_cntr(r, d, rdtgrp, mevt);
+	}
+
+	return ret;
+}
+
+/*
+ * rdtgroup_assign_cntrs() - Assign counters to MBM events. Called when
+ *			     a new group is created.
+ *
+ * Each group can accommodate two counters per domain: one for the total
+ * event and one for the local event. Assignments may fail due to the limited
+ * number of counters. However, it is not necessary to fail the group creation
+ * and thus no failure is returned. Users have the option to modify the
+ * counter assignments after the group has been created.
+ */
+void rdtgroup_assign_cntrs(struct rdtgroup *rdtgrp)
+{
+	struct rdt_resource *r = resctrl_arch_get_resource(RDT_RESOURCE_L3);
+
+	if (!r->mon_capable || !resctrl_arch_mbm_cntr_assign_enabled(r))
+		return;
+
+	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID))
+		rdtgroup_assign_cntr_event(NULL, rdtgrp,
+					   &mon_event_all[QOS_L3_MBM_TOTAL_EVENT_ID]);
+
+	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_LOCAL_EVENT_ID))
+		rdtgroup_assign_cntr_event(NULL, rdtgrp,
+					   &mon_event_all[QOS_L3_MBM_LOCAL_EVENT_ID]);
+}
+
 int resctrl_mbm_assign_mode_show(struct kernfs_open_file *of,
 				 struct seq_file *s, void *v)
 {

---

## [19] Babu Moger — 2025-09-05
*Subject: [PATCH v18 18/33] fs/resctrl: Add the functionality to unassign MBM events*

The "mbm_event" counter assignment mode offers "num_mbm_cntrs" number of
counters that can be assigned to RMID, event pairs and monitor bandwidth
usage as long as it is assigned. If all the counters are in use, the kernel
logs the error message "Failed to allocate counter for <event> in domain
<id>" in /sys/fs/resctrl/info/last_cmd_status when a new assignment is
requested.

To make space for a new assignment, users must unassign an already
assigned counter and retry the assignment again.

Add the functionality to unassign and free the counters in the domain.
Also, add the helper rdtgroup_unassign_cntrs() to unassign counters in the
group.

Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: Added Reviewed-by tag.

v17: Updated changelog.
     Moved all the functions to monitor.c.
     Brought rdtgroup_unassign_cntrs() from patch 28 to monitor.c to make compiler happy.

v16: Function rename rdtgroup_free_config_cntr() -> rdtgroup_free_unassign_cntr().
     Updated rdtgroup_free_unassign_cntr() to pass struct mon_evt to match
     rdtgroup_alloc_assign_cntr() prototype.

v15: Updated the changelog.
     Changed code in mbm_cntr_free to use the sizeof(*d->cntr_cfg)).
     Removed unnecessary return in resctrl_free_config_cntr().
     Rename resctrl_unassign_cntr_event() -> rdtgroup_unassign_cntr_event().
     Removed the parameter struct rdt_resource. It can be obtained from mevt->rid.

v14: Passing the struct mon_evt to resctrl_free_config_cntr() and removed
     the need for mbm_get_mon_event() call.
     Corrected the code documentation for mbm_cntr_free().
     Changed resctrl_free_config_cntr() and resctrl_unassign_cntr_event()
     to return void.
     Changed subject line to fs/resctrl.
     Updated the changelog.

v13: Moved mbm_cntr_free() to this patch as it is used in here first.
     Not required to pass evt_cfg to resctrl_unassign_cntr_event(). It is
     available via mbm_get_mon_event().
     Resolved conflicts caused by the recent FS/ARCH code restructure.
     The monitor.c file has now been split between the FS and ARCH directories.

v12: Updated the commit text to make bit more clear.
     Replaced several counters with "num_mbm_cntrs" counters.
     Fixed typo in the subjest line.
     Fixed the handling error on first failure.
     Added domain id and event id on failure.
     Added new parameter event configuration (evt_cfg) to provide the event from
     user space.

v11: Moved the functions to monitor.c.
     Renamed rdtgroup_unassign_cntr_event() to resctrl_unassign_cntr_event().
     Refactored the resctrl_unassign_cntr_event().
     Updated commit message and code comments.


v10: Patch changed again.
     Counters are managed at the domain based on the discussion.
     https://lore.kernel.org/lkml/CALPaoCj+zWq1vkHVbXYP0znJbe6Ke3PXPWjtri5AFgD9cQDCUg@mail.gmail.com/
     commit message update.

v9: Changes related to addition of new function resctrl_config_cntr().
    The removed rdtgroup_mbm_cntr_is_assigned() as it was introduced
    already.
    Text changes to take care comments.

v8: Renamed rdtgroup_mbm_cntr_is_assigned to mbm_cntr_assigned_to_domain
    Added return error handling in resctrl_arch_config_cntr().

v7: Merged rdtgroup_unassign_cntr and rdtgroup_free_cntr functions.
    Renamed rdtgroup_mbm_cntr_test() to rdtgroup_mbm_cntr_is_assigned().
    Reworded the commit log little bit.

v6: Removed mbm_cntr_free from this patch.
    Added counter test in all the domains and free if it is not assigned to
    any domains.

v5: Few name changes to match cntr_id.
    Changed the function names to rdtgroup_unassign_cntr
    More comments on commit log.

v4: Added domain specific unassign feature.
    Few name changes.

v3: Removed the static from the prototype of rdtgroup_unassign_abmc.
    The function is not called directly from user anymore. These
    changes are related to global assignment interface.

v2: No changes.
---
 fs/resctrl/internal.h |  2 ++
 fs/resctrl/monitor.c  | 66 +++++++++++++++++++++++++++++++++++++++++++
 2 files changed, 68 insertions(+)

diff --git a/fs/resctrl/internal.h b/fs/resctrl/internal.h
index 73cad7c17a1f..c11f2751acf5 100644
--- a/fs/resctrl/internal.h
+++ b/fs/resctrl/internal.h
@@ -398,6 +398,8 @@ int resctrl_available_mbm_cntrs_show(struct kernfs_open_file *of, struct seq_fil
 
 void rdtgroup_assign_cntrs(struct rdtgroup *rdtgrp);
 
+void rdtgroup_unassign_cntrs(struct rdtgroup *rdtgrp);
+
 #ifdef CONFIG_RESCTRL_FS_PSEUDO_LOCK
 int rdtgroup_locksetup_enter(struct rdtgroup *rdtgrp);
 
diff --git a/fs/resctrl/monitor.c b/fs/resctrl/monitor.c
index 3eb5a30f44fb..c03266e36cba 100644
--- a/fs/resctrl/monitor.c
+++ b/fs/resctrl/monitor.c
@@ -405,6 +405,14 @@ static int mbm_cntr_alloc(struct rdt_resource *r, struct rdt_mon_domain *d,
 	return -ENOSPC;
 }
 
+/*
+ * mbm_cntr_free() - Clear the counter ID configuration details in the domain @d.
+ */
+static void mbm_cntr_free(struct rdt_mon_domain *d, int cntr_id)
+{
+	memset(&d->cntr_cfg[cntr_id], 0, sizeof(*d->cntr_cfg));
+}
+
 static int __mon_event_count(u32 closid, u32 rmid, struct rmid_read *rr)
 {
 	int cpu = smp_processor_id();
@@ -1045,6 +1053,64 @@ void rdtgroup_assign_cntrs(struct rdtgroup *rdtgrp)
 					   &mon_event_all[QOS_L3_MBM_LOCAL_EVENT_ID]);
 }
 
+/*
+ * rdtgroup_free_unassign_cntr() - Unassign and reset the counter ID configuration
+ * for the event pointed to by @mevt within the domain @d and resctrl group @rdtgrp.
+ */
+static void rdtgroup_free_unassign_cntr(struct rdt_resource *r, struct rdt_mon_domain *d,
+					struct rdtgroup *rdtgrp, struct mon_evt *mevt)
+{
+	int cntr_id;
+
+	cntr_id = mbm_cntr_get(r, d, rdtgrp, mevt->evtid);
+
+	/* If there is no cntr_id assigned, nothing to do */
+	if (cntr_id < 0)
+		return;
+
+	rdtgroup_assign_cntr(r, d, mevt->evtid, rdtgrp->mon.rmid, rdtgrp->closid, cntr_id, false);
+
+	mbm_cntr_free(d, cntr_id);
+}
+
+/*
+ * rdtgroup_unassign_cntr_event() - Unassign a hardware counter associated with
+ * the event structure @mevt from the domain @d and the group @rdtgrp. Unassign
+ * the counters from all the domains if @d is NULL else unassign from @d.
+ */
+static void rdtgroup_unassign_cntr_event(struct rdt_mon_domain *d, struct rdtgroup *rdtgrp,
+					 struct mon_evt *mevt)
+{
+	struct rdt_resource *r = resctrl_arch_get_resource(mevt->rid);
+
+	if (!d) {
+		list_for_each_entry(d, &r->mon_domains, hdr.list)
+			rdtgroup_free_unassign_cntr(r, d, rdtgrp, mevt);
+	} else {
+		rdtgroup_free_unassign_cntr(r, d, rdtgrp, mevt);
+	}
+}
+
+/*
+ * rdtgroup_unassign_cntrs() - Unassign the counters associated with MBM events.
+ *			       Called when a group is deleted.
+ */
+void rdtgroup_unassign_cntrs(struct rdtgroup *rdtgrp)
+{
+	struct rdt_resource *r = resctrl_arch_get_resource(RDT_RESOURCE_L3);
+
+	if (!r->mon_capable || !resctrl_arch_mbm_cntr_assign_enabled(r))
+		return;
+
+	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID))
+		rdtgroup_unassign_cntr_event(NULL, rdtgrp,
+					     &mon_event_all[QOS_L3_MBM_TOTAL_EVENT_ID]);
+
+	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_LOCAL_EVENT_ID))
+		rdtgroup_unassign_cntr_event(NULL, rdtgrp,
+					     &mon_event_all[QOS_L3_MBM_LOCAL_EVENT_ID]);
+}
+
 int resctrl_mbm_assign_mode_show(struct kernfs_open_file *of,
 				 struct seq_file *s, void *v)
 {

---

## [20] Babu Moger — 2025-09-05
*Subject: [PATCH v18 19/33] fs/resctrl: Pass struct rdtgroup instead of individual members*

Reading monitoring data for a monitoring group requires both the RMID and
CLOSID. The RMID and CLOSID are members of struct rdtgroup but passed
separately to several functions involved in retrieving event data.

When "mbm_event" counter assignment mode is enabled, a counter ID is
required to read event data. The counter ID is obtained through
mbm_cntr_get(), which expects a struct rdtgroup pointer.

Provide a pointer to the struct rdtgroup as parameter to functions involved
in retrieving event data to simplify access to RMID, CLOSID, and counter
ID.

Suggested-by: Reinette Chatre <reinette.chatre@intel.com>
Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: No changes.

v17: Added Reviewed-by.

v16: Minor code comment update.

v15: Rephrased the changelog. Thanks to Reinette.

v14: Few text update to commit log.

v13: New patch to pass the entire struct rdtgroup to __mon_event_count(),
     mbm_update(), and related functions.
---
 fs/resctrl/monitor.c | 33 ++++++++++++++++++---------------
 1 file changed, 18 insertions(+), 15 deletions(-)

diff --git a/fs/resctrl/monitor.c b/fs/resctrl/monitor.c
index c03266e36cba..85187273d562 100644
--- a/fs/resctrl/monitor.c
+++ b/fs/resctrl/monitor.c
@@ -413,9 +413,11 @@ static void mbm_cntr_free(struct rdt_mon_domain *d, int cntr_id)
 	memset(&d->cntr_cfg[cntr_id], 0, sizeof(*d->cntr_cfg));
 }
 
-static int __mon_event_count(u32 closid, u32 rmid, struct rmid_read *rr)
+static int __mon_event_count(struct rdtgroup *rdtgrp, struct rmid_read *rr)
 {
 	int cpu = smp_processor_id();
+	u32 closid = rdtgrp->closid;
+	u32 rmid = rdtgrp->mon.rmid;
 	struct rdt_mon_domain *d;
 	struct cacheinfo *ci;
 	struct mbm_state *m;
@@ -477,8 +479,8 @@ static int __mon_event_count(u32 closid, u32 rmid, struct rmid_read *rr)
 /*
  * mbm_bw_count() - Update bw count from values previously read by
  *		    __mon_event_count().
- * @closid:	The closid used to identify the cached mbm_state.
- * @rmid:	The rmid used to identify the cached mbm_state.
+ * @rdtgrp:	resctrl group associated with the CLOSID and RMID to identify
+ *		the cached mbm_state.
  * @rr:		The struct rmid_read populated by __mon_event_count().
  *
  * Supporting function to calculate the memory bandwidth
@@ -486,9 +488,11 @@ static int __mon_event_count(u32 closid, u32 rmid, struct rmid_read *rr)
  * __mon_event_count() is compared with the chunks value from the previous
  * invocation. This must be called once per second to maintain values in MBps.
  */
-static void mbm_bw_count(u32 closid, u32 rmid, struct rmid_read *rr)
+static void mbm_bw_count(struct rdtgroup *rdtgrp, struct rmid_read *rr)
 {
 	u64 cur_bw, bytes, cur_bytes;
+	u32 closid = rdtgrp->closid;
+	u32 rmid = rdtgrp->mon.rmid;
 	struct mbm_state *m;
 
 	m = get_mbm_state(rr->d, closid, rmid, rr->evtid);
@@ -517,7 +521,7 @@ void mon_event_count(void *info)
 
 	rdtgrp = rr->rgrp;
 
-	ret = __mon_event_count(rdtgrp->closid, rdtgrp->mon.rmid, rr);
+	ret = __mon_event_count(rdtgrp, rr);
 
 	/*
 	 * For Ctrl groups read data from child monitor groups and
@@ -528,8 +532,7 @@ void mon_event_count(void *info)
 
 	if (rdtgrp->type == RDTCTRL_GROUP) {
 		list_for_each_entry(entry, head, mon.crdtgrp_list) {
-			if (__mon_event_count(entry->closid, entry->mon.rmid,
-					      rr) == 0)
+			if (__mon_event_count(entry, rr) == 0)
 				ret = 0;
 		}
 	}
@@ -660,7 +663,7 @@ static void update_mba_bw(struct rdtgroup *rgrp, struct rdt_mon_domain *dom_mbm)
 }
 
 static void mbm_update_one_event(struct rdt_resource *r, struct rdt_mon_domain *d,
-				 u32 closid, u32 rmid, enum resctrl_event_id evtid)
+				 struct rdtgroup *rdtgrp, enum resctrl_event_id evtid)
 {
 	struct rmid_read rr = {0};
 
@@ -674,30 +677,30 @@ static void mbm_update_one_event(struct rdt_resource *r, struct rdt_mon_domain *
 		return;
 	}
 
-	__mon_event_count(closid, rmid, &rr);
+	__mon_event_count(rdtgrp, &rr);
 
 	/*
 	 * If the software controller is enabled, compute the
 	 * bandwidth for this event id.
 	 */
 	if (is_mba_sc(NULL))
-		mbm_bw_count(closid, rmid, &rr);
+		mbm_bw_count(rdtgrp, &rr);
 
 	resctrl_arch_mon_ctx_free(rr.r, rr.evtid, rr.arch_mon_ctx);
 }
 
 static void mbm_update(struct rdt_resource *r, struct rdt_mon_domain *d,
-		       u32 closid, u32 rmid)
+		       struct rdtgroup *rdtgrp)
 {
 	/*
 	 * This is protected from concurrent reads from user as both
 	 * the user and overflow handler hold the global mutex.
 	 */
 	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID))
-		mbm_update_one_event(r, d, closid, rmid, QOS_L3_MBM_TOTAL_EVENT_ID);
+		mbm_update_one_event(r, d, rdtgrp, QOS_L3_MBM_TOTAL_EVENT_ID);
 
 	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_LOCAL_EVENT_ID))
-		mbm_update_one_event(r, d, closid, rmid, QOS_L3_MBM_LOCAL_EVENT_ID);
+		mbm_update_one_event(r, d, rdtgrp, QOS_L3_MBM_LOCAL_EVENT_ID);
 }
 
 /*
@@ -770,11 +773,11 @@ void mbm_handle_overflow(struct work_struct *work)
 	d = container_of(work, struct rdt_mon_domain, mbm_over.work);
 
 	list_for_each_entry(prgrp, &rdt_all_groups, rdtgroup_list) {
-		mbm_update(r, d, prgrp->closid, prgrp->mon.rmid);
+		mbm_update(r, d, prgrp);
 
 		head = &prgrp->mon.crdtgrp_list;
 		list_for_each_entry(crgrp, head, mon.crdtgrp_list)
-			mbm_update(r, d, crgrp->closid, crgrp->mon.rmid);
+			mbm_update(r, d, crgrp);
 
 		if (is_mba_sc(NULL))
 			update_mba_bw(prgrp, d);

---

## [21] Babu Moger — 2025-09-05
*Subject: [PATCH v18 20/33] fs/resctrl: Introduce counter ID read, reset calls in mbm_event mode*

When supported, "mbm_event" counter assignment mode allows users to assign
a hardware counter to an RMID, event pair and monitor the bandwidth usage
as long as it is assigned. The hardware continues to track the assigned
counter until it is explicitly unassigned by the user.

Introduce the architecture calls resctrl_arch_cntr_read() and
resctrl_arch_reset_cntr() to read and reset event counters when "mbm_event"
mode is supported. Function names match existing resctrl_arch_rmid_read()
and resctrl_arch_reset_rmid().

Suggested-by: Reinette Chatre <reinette.chatre@intel.com>
Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: Added Reviewed-by tag.

v17: Updated the changelog.
     Updated kernel API doc.

v16: Updated the changelog.
     Removed lots of copied and unnecessary text from resctrl.h.
     Also removed references to LLC occupancy.
     Removed arch_mon_ctx from resctrl_arch_cntr_read().

v15: New patch to add arch calls resctrl_arch_cntr_read() and resctrl_arch_reset_cntr()
     with mbm_event mode.
     https://lore.kernel.org/lkml/b4b14670-9cb0-4f65-abd5-39db996e8da9@intel.com/
---
 include/linux/resctrl.h | 38 ++++++++++++++++++++++++++++++++++++++
 1 file changed, 38 insertions(+)

diff --git a/include/linux/resctrl.h b/include/linux/resctrl.h
index 50e38445183a..04152654827d 100644
--- a/include/linux/resctrl.h
+++ b/include/linux/resctrl.h
@@ -613,6 +613,44 @@ void resctrl_arch_config_cntr(struct rdt_resource *r, struct rdt_mon_domain *d,
 			      enum resctrl_event_id evtid, u32 rmid, u32 closid,
 			      u32 cntr_id, bool assign);
 
+/**
+ * resctrl_arch_cntr_read() - Read the event data corresponding to the counter ID
+ *			      assigned to the RMID, event pair for this resource
+ *			      and domain.
+ * @r:		Resource that the counter should be read from.
+ * @d:		Domain that the counter should be read from.
+ * @closid:	CLOSID that matches the RMID.
+ * @rmid:	The RMID to which @cntr_id is assigned.
+ * @cntr_id:	The counter to read.
+ * @eventid:	The MBM event to which @cntr_id is assigned.
+ * @val:	Result of the counter read in bytes.
+ *
+ * Called on a CPU that belongs to domain @d when "mbm_event" mode is enabled.
+ * Called from a non-migrateable process context via smp_call_on_cpu() unless all
+ * CPUs are nohz_full, in which case it is called via IPI (smp_call_function_any()).
+ *
+ * Return:
+ * 0 on success, or -EIO, -EINVAL etc on error.
+ */
+int resctrl_arch_cntr_read(struct rdt_resource *r, struct rdt_mon_domain *d,
+			   u32 closid, u32 rmid, int cntr_id,
+			   enum resctrl_event_id eventid, u64 *val);
+
+/**
+ * resctrl_arch_reset_cntr() - Reset any private state associated with counter ID.
+ * @r:		The domain's resource.
+ * @d:		The counter ID's domain.
+ * @closid:	CLOSID that matches the RMID.
+ * @rmid:	The RMID to which @cntr_id is assigned.
+ * @cntr_id:	The counter to reset.
+ * @eventid:	The MBM event to which @cntr_id is assigned.
+ *
+ * This can be called from any CPU.
+ */
+void resctrl_arch_reset_cntr(struct rdt_resource *r, struct rdt_mon_domain *d,
+			     u32 closid, u32 rmid, int cntr_id,
+			     enum resctrl_event_id eventid);
+
 extern unsigned int resctrl_rmid_realloc_threshold;
 extern unsigned int resctrl_rmid_realloc_limit;

---

## [22] Babu Moger — 2025-09-05
*Subject: [PATCH v18 21/33] x86/resctrl: Refactor resctrl_arch_rmid_read()*

resctrl_arch_rmid_read() adjusts the value obtained from MSR_IA32_QM_CTR to
account for the overflow for MBM events and apply counter scaling for all
the events. This logic is common to both reading an RMID and reading a
hardware counter directly.

Refactor the hardware value adjustment logic into get_corrected_val() to
prepare for support of reading a hardware counter.

Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: No changes.

v17: Added Reviewed-by tag.

v16: Rephrased the changelog.
     Fixed allignment.
     Renamed mbm_corrected_val() -> get_corrected_val().

v15: New patch to add arch calls resctrl_arch_cntr_read() and resctrl_arch_reset_cntr()
     with mbm_event mode.
     https://lore.kernel.org/lkml/b4b14670-9cb0-4f65-abd5-39db996e8da9@intel.com/
---
 arch/x86/kernel/cpu/resctrl/monitor.c | 38 ++++++++++++++++-----------
 1 file changed, 23 insertions(+), 15 deletions(-)

diff --git a/arch/x86/kernel/cpu/resctrl/monitor.c b/arch/x86/kernel/cpu/resctrl/monitor.c
index ed295a6c5e66..1f77fd58e707 100644
--- a/arch/x86/kernel/cpu/resctrl/monitor.c
+++ b/arch/x86/kernel/cpu/resctrl/monitor.c
@@ -217,24 +217,13 @@ static u64 mbm_overflow_count(u64 prev_msr, u64 cur_msr, unsigned int width)
 	return chunks >> shift;
 }
 
-int resctrl_arch_rmid_read(struct rdt_resource *r, struct rdt_mon_domain *d,
-			   u32 unused, u32 rmid, enum resctrl_event_id eventid,
-			   u64 *val, void *ignored)
+static u64 get_corrected_val(struct rdt_resource *r, struct rdt_mon_domain *d,
+			     u32 rmid, enum resctrl_event_id eventid, u64 msr_val)
 {
 	struct rdt_hw_mon_domain *hw_dom = resctrl_to_arch_mon_dom(d);
 	struct rdt_hw_resource *hw_res = resctrl_to_arch_res(r);
-	int cpu = cpumask_any(&d->hdr.cpu_mask);
 	struct arch_mbm_state *am;
-	u64 msr_val, chunks;
-	u32 prmid;
-	int ret;
-
-	resctrl_arch_rmid_read_context_check();
-
-	prmid = logical_rmid_to_physical_rmid(cpu, rmid);
-	ret = __rmid_read_phys(prmid, eventid, &msr_val);
-	if (ret)
-		return ret;
+	u64 chunks;
 
 	am = get_arch_mbm_state(hw_dom, rmid, eventid);
 	if (am) {
@@ -246,7 +235,26 @@ int resctrl_arch_rmid_read(struct rdt_resource *r, struct rdt_mon_domain *d,
 		chunks = msr_val;
 	}
 
-	*val = chunks * hw_res->mon_scale;
+	return chunks * hw_res->mon_scale;
+}
+
+int resctrl_arch_rmid_read(struct rdt_resource *r, struct rdt_mon_domain *d,
+			   u32 unused, u32 rmid, enum resctrl_event_id eventid,
+			   u64 *val, void *ignored)
+{
+	int cpu = cpumask_any(&d->hdr.cpu_mask);
+	u64 msr_val;
+	u32 prmid;
+	int ret;
+
+	resctrl_arch_rmid_read_context_check();
+
+	prmid = logical_rmid_to_physical_rmid(cpu, rmid);
+	ret = __rmid_read_phys(prmid, eventid, &msr_val);
+	if (ret)
+		return ret;
+
+	*val = get_corrected_val(r, d, rmid, eventid, msr_val);
 
 	return 0;
 }

---

## [23] Babu Moger — 2025-09-05
*Subject: [PATCH v18 22/33] x86/resctrl: Implement resctrl_arch_reset_cntr() and resctrl_arch_cntr_read()*

System software reads resctrl event data for a particular resource by
writing the RMID and Event Identifier (EvtID) to the QM_EVTSEL register and
then reading the event data from the QM_CTR register.

In ABMC mode, the event data of a specific counter ID is read by setting
the following fields: QM_EVTSEL.ExtendedEvtID = 1, QM_EVTSEL.EvtID =
L3CacheABMC (=1) and setting QM_EVTSEL.RMID to the desired counter ID.
Reading the QM_CTR then returns the contents of the specified counter ID.
RMID_VAL_ERROR bit is set if the counter configuration is invalid, or
if an invalid counter ID is set in the QM_EVTSEL.RMID field.
RMID_VAL_UNAVAIL bit is set if the counter data is unavailable.

Introduce resctrl_arch_reset_cntr() and resctrl_arch_cntr_read() to reset
and read event data for a specific counter.

Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: Added Reviewed-by tag.

v17: Updated changelog.
     Updated code comment little bit.

v16: Updated the changelog.
     Removed the call resctrl_arch_rmid_read_context_check();
     Added the text about RMID_VAL_UNAVAIL error.

v15: Updated patch to add arch calls resctrl_arch_cntr_read() and resctrl_arch_reset_cntr()
     with mbm_event mode.
     https://lore.kernel.org/lkml/b4b14670-9cb0-4f65-abd5-39db996e8da9@intel.com/

v14: Updated the context in changelog. Added text in imperative tone.
     Added WARN_ON_ONCE() when cntr_id < 0.
     Improved code documentation in include/linux/resctrl.h.
     Added the check in mbm_update() to skip overflow handler when counter is unassigned.

v13: Split the patch into 2. First one to handle the passing of rdtgroup structure to few
     functions( __mon_event_count and mbm_update(). Second one to handle ABMC counter reading.
     Added new function __cntr_id_read_phys() to handle ABMC event reading.
     Updated kernel doc for resctrl_arch_reset_rmid() and resctrl_arch_rmid_read().
     Resolved conflicts caused by the recent FS/ARCH code restructure.
     The monitor.c file has now been split between the FS and ARCH directories.

v12: New patch to support extended event mode when ABMC is enabled.
---
 arch/x86/kernel/cpu/resctrl/internal.h |  6 +++
 arch/x86/kernel/cpu/resctrl/monitor.c  | 69 ++++++++++++++++++++++++++
 2 files changed, 75 insertions(+)

diff --git a/arch/x86/kernel/cpu/resctrl/internal.h b/arch/x86/kernel/cpu/resctrl/internal.h
index 6bf6042f11b6..ae4003d44df4 100644
--- a/arch/x86/kernel/cpu/resctrl/internal.h
+++ b/arch/x86/kernel/cpu/resctrl/internal.h
@@ -40,6 +40,12 @@ struct arch_mbm_state {
 /* Setting bit 0 in L3_QOS_EXT_CFG enables the ABMC feature. */
 #define ABMC_ENABLE_BIT			0
 
+/*
+ * Qos Event Identifiers.
+ */
+#define ABMC_EXTENDED_EVT_ID		BIT(31)
+#define ABMC_EVT_ID			BIT(0)
+
 /**
  * struct rdt_hw_ctrl_domain - Arch private attributes of a set of CPUs that share
  *			       a resource for a control function
diff --git a/arch/x86/kernel/cpu/resctrl/monitor.c b/arch/x86/kernel/cpu/resctrl/monitor.c
index 1f77fd58e707..0b3c199e9e01 100644
--- a/arch/x86/kernel/cpu/resctrl/monitor.c
+++ b/arch/x86/kernel/cpu/resctrl/monitor.c
@@ -259,6 +259,75 @@ int resctrl_arch_rmid_read(struct rdt_resource *r, struct rdt_mon_domain *d,
 	return 0;
 }
 
+static int __cntr_id_read(u32 cntr_id, u64 *val)
+{
+	u64 msr_val;
+
+	/*
+	 * QM_EVTSEL Register definition:
+	 * =======================================================
+	 * Bits    Mnemonic        Description
+	 * =======================================================
+	 * 63:44   --              Reserved
+	 * 43:32   RMID            RMID or counter ID in ABMC mode
+	 *                         when reading an MBM event
+	 * 31      ExtendedEvtID   Extended Event Identifier
+	 * 30:8    --              Reserved
+	 * 7:0     EvtID           Event Identifier
+	 * =======================================================
+	 * The contents of a specific counter can be read by setting the
+	 * following fields in QM_EVTSEL.ExtendedEvtID(=1) and
+	 * QM_EVTSEL.EvtID = L3CacheABMC (=1) and setting QM_EVTSEL.RMID
+	 * to the desired counter ID. Reading the QM_CTR then returns the
+	 * contents of the specified counter. The RMID_VAL_ERROR bit is set
+	 * if the counter configuration is invalid, or if an invalid counter
+	 * ID is set in the QM_EVTSEL.RMID field.  The RMID_VAL_UNAVAIL bit
+	 * is set if the counter data is unavailable.
+	 */
+	wrmsr(MSR_IA32_QM_EVTSEL, ABMC_EXTENDED_EVT_ID | ABMC_EVT_ID, cntr_id);
+	rdmsrl(MSR_IA32_QM_CTR, msr_val);
+
+	if (msr_val & RMID_VAL_ERROR)
+		return -EIO;
+	if (msr_val & RMID_VAL_UNAVAIL)
+		return -EINVAL;
+
+	*val = msr_val;
+	return 0;
+}
+
+void resctrl_arch_reset_cntr(struct rdt_resource *r, struct rdt_mon_domain *d,
+			     u32 unused, u32 rmid, int cntr_id,
+			     enum resctrl_event_id eventid)
+{
+	struct rdt_hw_mon_domain *hw_dom = resctrl_to_arch_mon_dom(d);
+	struct arch_mbm_state *am;
+
+	am = get_arch_mbm_state(hw_dom, rmid, eventid);
+	if (am) {
+		memset(am, 0, sizeof(*am));
+
+		/* Record any initial, non-zero count value. */
+		__cntr_id_read(cntr_id, &am->prev_msr);
+	}
+}
+
+int resctrl_arch_cntr_read(struct rdt_resource *r, struct rdt_mon_domain *d,
+			   u32 unused, u32 rmid, int cntr_id,
+			   enum resctrl_event_id eventid, u64 *val)
+{
+	u64 msr_val;
+	int ret;
+
+	ret = __cntr_id_read(cntr_id, &msr_val);
+	if (ret)
+		return ret;
+
+	*val = get_corrected_val(r, d, rmid, eventid, msr_val);
+
+	return 0;
+}
+
 /*
  * The power-on reset value of MSR_RMID_SNC_CONFIG is 0x1
  * which indicates that RMIDs are configured in legacy mode.

---

## [24] Babu Moger — 2025-09-05
*Subject: [PATCH v18 23/33] fs/resctrl: Support counter read/reset with mbm_event assignment mode*

When "mbm_event" counter assignment mode is enabled, the architecture
requires a counter ID to read the event data.

Introduce an is_mbm_cntr field in struct rmid_read to indicate whether
counter assignment mode is in use.

Update the logic to call resctrl_arch_cntr_read() and
resctrl_arch_reset_cntr() when the assignment mode is active. Report
'Unassigned' in case the user attempts to read an event without assigning
a hardware counter.

Suggested-by: Reinette Chatre <reinette.chatre@intel.com>
Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: Added Reviewed-by tag.

v17: Updated the changelog.
     Removed duplicate resctrl_arch_mbm_cntr_assign_enabled() check.
     mbm_cntr_get() need not be static anymore.

v16: Squashed two patches here.
     https://lore.kernel.org/lkml/df215f02db88cad714755cd5275f20cf0ee4ae26.1752013061.git.babu.moger@amd.com/
     https://lore.kernel.org/lkml/296c435e9bf63fc5031114cced00fbb4837ad327.1752013061.git.babu.moger@amd.com/
     Changed is_cntr field in struct rmid_read to is_mbm_cntr.
     Fixed the memory leak with arch_mon_ctx.
     Updated the resctrl.rst user doc.
     Updated the changelog.
     Report Unassigned only if none of the events in CTRL_MON and MON are assigned.

v15: New patch to add is_cntr in rmid_read as discussed in
     https://lore.kernel.org/lkml/b4b14670-9cb0-4f65-abd5-39db996e8da9@intel.com/
---
 Documentation/filesystems/resctrl.rst |  6 ++++
 fs/resctrl/ctrlmondata.c              | 22 ++++++++++---
 fs/resctrl/internal.h                 |  3 ++
 fs/resctrl/monitor.c                  | 47 ++++++++++++++++++++-------
 4 files changed, 62 insertions(+), 16 deletions(-)

diff --git a/Documentation/filesystems/resctrl.rst b/Documentation/filesystems/resctrl.rst
index 446736dbd97f..4c24c5f3f4c1 100644
--- a/Documentation/filesystems/resctrl.rst
+++ b/Documentation/filesystems/resctrl.rst
@@ -434,6 +434,12 @@ When monitoring is enabled all MON groups will also contain:
 	for the L3 cache they occupy). These are named "mon_sub_L3_YY"
 	where "YY" is the node number.
 
+	When the 'mbm_event' counter assignment mode is enabled, reading
+	an MBM event of a MON group returns 'Unassigned' if no hardware
+	counter is assigned to it. For CTRL_MON groups, 'Unassigned' is
+	returned if the MBM event does not have an assigned counter in the
+	CTRL_MON group nor in any of its associated MON groups.
+
 "mon_hw_id":
 	Available only with debug option. The identifier used by hardware
 	for the monitor group. On x86 this is the RMID.
diff --git a/fs/resctrl/ctrlmondata.c b/fs/resctrl/ctrlmondata.c
index ad7ffc6acf13..31787ce6ec91 100644
--- a/fs/resctrl/ctrlmondata.c
+++ b/fs/resctrl/ctrlmondata.c
@@ -563,10 +563,15 @@ void mon_event_read(struct rmid_read *rr, struct rdt_resource *r,
 	rr->r = r;
 	rr->d = d;
 	rr->first = first;
-	rr->arch_mon_ctx = resctrl_arch_mon_ctx_alloc(r, evtid);
-	if (IS_ERR(rr->arch_mon_ctx)) {
-		rr->err = -EINVAL;
-		return;
+	if (resctrl_arch_mbm_cntr_assign_enabled(r) &&
+	    resctrl_is_mbm_event(evtid)) {
+		rr->is_mbm_cntr = true;
+	} else {
+		rr->arch_mon_ctx = resctrl_arch_mon_ctx_alloc(r, evtid);
+		if (IS_ERR(rr->arch_mon_ctx)) {
+			rr->err = -EINVAL;
+			return;
+		}
 	}
 
 	cpu = cpumask_any_housekeeping(cpumask, RESCTRL_PICK_ANY_CPU);
@@ -582,7 +587,8 @@ void mon_event_read(struct rmid_read *rr, struct rdt_resource *r,
 	else
 		smp_call_on_cpu(cpu, smp_mon_event_count, rr, false);
 
-	resctrl_arch_mon_ctx_free(r, evtid, rr->arch_mon_ctx);
+	if (rr->arch_mon_ctx)
+		resctrl_arch_mon_ctx_free(r, evtid, rr->arch_mon_ctx);
 }
 
 int rdtgroup_mondata_show(struct seq_file *m, void *arg)
@@ -653,10 +659,16 @@ int rdtgroup_mondata_show(struct seq_file *m, void *arg)
 
 checkresult:
 
+	/*
+	 * -ENOENT is a special case, set only when "mbm_event" counter assignment
+	 * mode is enabled and no counter has been assigned.
+	 */
 	if (rr.err == -EIO)
 		seq_puts(m, "Error\n");
 	else if (rr.err == -EINVAL)
 		seq_puts(m, "Unavailable\n");
+	else if (rr.err == -ENOENT)
+		seq_puts(m, "Unassigned\n");
 	else
 		seq_printf(m, "%llu\n", rr.val);
 
diff --git a/fs/resctrl/internal.h b/fs/resctrl/internal.h
index c11f2751acf5..88e1a800417d 100644
--- a/fs/resctrl/internal.h
+++ b/fs/resctrl/internal.h
@@ -110,6 +110,8 @@ struct mon_data {
  *	   domains in @r sharing L3 @ci.id
  * @evtid: Which monitor event to read.
  * @first: Initialize MBM counter when true.
+ * @is_mbm_cntr: true if "mbm_event" counter assignment mode is enabled and it
+ *	   is an MBM event.
  * @ci_id: Cacheinfo id for L3. Only set when @d is NULL. Used when summing domains.
  * @err:   Error encountered when reading counter.
  * @val:   Returned value of event counter. If @rgrp is a parent resource group,
@@ -124,6 +126,7 @@ struct rmid_read {
 	struct rdt_mon_domain	*d;
 	enum resctrl_event_id	evtid;
 	bool			first;
+	bool			is_mbm_cntr;
 	unsigned int		ci_id;
 	int			err;
 	u64			val;
diff --git a/fs/resctrl/monitor.c b/fs/resctrl/monitor.c
index 85187273d562..0a9d257e27a2 100644
--- a/fs/resctrl/monitor.c
+++ b/fs/resctrl/monitor.c
@@ -419,13 +419,25 @@ static int __mon_event_count(struct rdtgroup *rdtgrp, struct rmid_read *rr)
 	u32 closid = rdtgrp->closid;
 	u32 rmid = rdtgrp->mon.rmid;
 	struct rdt_mon_domain *d;
+	int cntr_id = -ENOENT;
 	struct cacheinfo *ci;
 	struct mbm_state *m;
 	int err, ret;
 	u64 tval = 0;
 
+	if (rr->is_mbm_cntr) {
+		cntr_id = mbm_cntr_get(rr->r, rr->d, rdtgrp, rr->evtid);
+		if (cntr_id < 0) {
+			rr->err = -ENOENT;
+			return -EINVAL;
+		}
+	}
+
 	if (rr->first) {
-		resctrl_arch_reset_rmid(rr->r, rr->d, closid, rmid, rr->evtid);
+		if (rr->is_mbm_cntr)
+			resctrl_arch_reset_cntr(rr->r, rr->d, closid, rmid, cntr_id, rr->evtid);
+		else
+			resctrl_arch_reset_rmid(rr->r, rr->d, closid, rmid, rr->evtid);
 		m = get_mbm_state(rr->d, closid, rmid, rr->evtid);
 		if (m)
 			memset(m, 0, sizeof(struct mbm_state));
@@ -436,8 +448,12 @@ static int __mon_event_count(struct rdtgroup *rdtgrp, struct rmid_read *rr)
 		/* Reading a single domain, must be on a CPU in that domain. */
 		if (!cpumask_test_cpu(cpu, &rr->d->hdr.cpu_mask))
 			return -EINVAL;
-		rr->err = resctrl_arch_rmid_read(rr->r, rr->d, closid, rmid,
-						 rr->evtid, &tval, rr->arch_mon_ctx);
+		if (rr->is_mbm_cntr)
+			rr->err = resctrl_arch_cntr_read(rr->r, rr->d, closid, rmid, cntr_id,
+							 rr->evtid, &tval);
+		else
+			rr->err = resctrl_arch_rmid_read(rr->r, rr->d, closid, rmid,
+							 rr->evtid, &tval, rr->arch_mon_ctx);
 		if (rr->err)
 			return rr->err;
 
@@ -462,8 +478,12 @@ static int __mon_event_count(struct rdtgroup *rdtgrp, struct rmid_read *rr)
 	list_for_each_entry(d, &rr->r->mon_domains, hdr.list) {
 		if (d->ci_id != rr->ci_id)
 			continue;
-		err = resctrl_arch_rmid_read(rr->r, d, closid, rmid,
-					     rr->evtid, &tval, rr->arch_mon_ctx);
+		if (rr->is_mbm_cntr)
+			err = resctrl_arch_cntr_read(rr->r, d, closid, rmid, cntr_id,
+						     rr->evtid, &tval);
+		else
+			err = resctrl_arch_rmid_read(rr->r, d, closid, rmid,
+						     rr->evtid, &tval, rr->arch_mon_ctx);
 		if (!err) {
 			rr->val += tval;
 			ret = 0;
@@ -670,11 +690,15 @@ static void mbm_update_one_event(struct rdt_resource *r, struct rdt_mon_domain *
 	rr.r = r;
 	rr.d = d;
 	rr.evtid = evtid;
-	rr.arch_mon_ctx = resctrl_arch_mon_ctx_alloc(rr.r, rr.evtid);
-	if (IS_ERR(rr.arch_mon_ctx)) {
-		pr_warn_ratelimited("Failed to allocate monitor context: %ld",
-				    PTR_ERR(rr.arch_mon_ctx));
-		return;
+	if (resctrl_arch_mbm_cntr_assign_enabled(r)) {
+		rr.is_mbm_cntr = true;
+	} else {
+		rr.arch_mon_ctx = resctrl_arch_mon_ctx_alloc(rr.r, rr.evtid);
+		if (IS_ERR(rr.arch_mon_ctx)) {
+			pr_warn_ratelimited("Failed to allocate monitor context: %ld",
+					    PTR_ERR(rr.arch_mon_ctx));
+			return;
+		}
 	}
 
 	__mon_event_count(rdtgrp, &rr);
@@ -686,7 +710,8 @@ static void mbm_update_one_event(struct rdt_resource *r, struct rdt_mon_domain *
 	if (is_mba_sc(NULL))
 		mbm_bw_count(rdtgrp, &rr);
 
-	resctrl_arch_mon_ctx_free(rr.r, rr.evtid, rr.arch_mon_ctx);
+	if (rr.arch_mon_ctx)
+		resctrl_arch_mon_ctx_free(rr.r, rr.evtid, rr.arch_mon_ctx);
 }
 
 static void mbm_update(struct rdt_resource *r, struct rdt_mon_domain *d,

---

## [25] Babu Moger — 2025-09-05
*Subject: [PATCH v18 24/33] fs/resctrl: Add event configuration directory under info/L3_MON/*

The "mbm_event" counter assignment mode allows the user to assign a
hardware counter to an RMID, event pair and monitor the bandwidth as long
as it is assigned. The user can specify the memory transaction(s) for the
counter to track.

When this mode is supported, the /sys/fs/resctrl/info/L3_MON/event_configs
directory contains a sub-directory for each MBM event that can be assigned
to a counter.  The MBM event sub-directory contains a file named
"event_filter" that is used to view and modify which memory transactions
the MBM event is configured with.

Create /sys/fs/resctrl/info/L3_MON/event_configs directory on resctrl mount
and pre-populate it with directories for the two existing MBM events:
mbm_total_bytes and mbm_local_bytes. Create the "event_filter" file within
each MBM event directory with the needed *show() that displays the memory
transactions with which the MBM event is configured.

Example:
$ mount -t resctrl resctrl /sys/fs/resctrl
$ cd /sys/fs/resctrl/
$ cat info/L3_MON/event_configs/mbm_total_bytes/event_filter
  local_reads,remote_reads,local_non_temporal_writes,
  remote_non_temporal_writes,local_reads_slow_memory,
  remote_reads_slow_memory,dirty_victim_writes_all

$ cat info/L3_MON/event_configs/mbm_local_bytes/event_filter
  local_reads,local_non_temporal_writes,local_reads_slow_memory

Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: Added Reviewed-by tag.

v17: Squashed patch #24 abd #25 into one. Both are dependent on each other.
     Minor change in resctrl.rst.
     Remove check for kernfs_activate() in rdtgroup_mkdir_info_resdir().
     Added resctrl_arch_mbm_cntr_assign_enabled() in event_filter_show().
     Moved struct mbm_transaction declaration to monitor.c and made it static.

v16: Moved event_filter_show() to fs/resctrl/monitor.c
     Changed the goto label out_config to out.
     Added rdtgroup_mutex in event_filter_show().
     Removed extern for mbm_transactions. Not required.
     0025-fs-resctrl-Add-event-configuration-directory-under
     0025-fs-resctrl-Add-event-configuration-directory-under
     0025-fs-resctrl-Add-event-configuration-directory-under
     Added prototype rdt_kn_parent_priv() in so it can be called from monitor.c

v15: Fixed the event_filter display with proper spacing.
     Updated the changelog.
     Changed the function name resctrl_mkdir_counter_configs() to
     resctrl_mkdir_event_configs().
     Called resctrl_mkdir_event_configs from rdtgroup_mkdir_info_resdir().
     It avoids the call kernfs_find_and_get() to get the node for info directory.
     Used for_each_mon_event() where applicable.

v14: Updated the changelog with context. Thanks to Reinette.
     Changed the name of directory to event_configs from counter_config.
     Updated user doc about the memory transactions supported by assignment.
     Removed mbm_mode from struct mon_evt. Not required anymore.

v13: Updated user doc (resctrl.rst).
     Changed the name of the function resctrl_mkdir_info_configs to
     resctrl_mkdir_counter_configs().
     Replaced seq_puts() with seq_putc() where applicable.
     Removed RFTYPE_MON_CONFIG definition. Not required.
     Changed the name of the flag RFTYPE_CONFIG to RFTYPE_ASSIGN_CONFIG.
     Reinette suggested RFTYPE_MBM_EVENT_CONFIG but RFTYPE_ASSIGN_CONFIG
     seemed shorter and pricise.
     The configuration is created using evt_list.
     Resolved conflicts caused by the recent FS/ARCH code restructure.
     The monitor.c/rdtgroup.c files have been split between the FS and ARCH directories.

v12: New patch to hold the MBM event configurations for mbm_cntr_assign mode.
---
 Documentation/filesystems/resctrl.rst | 33 +++++++++++++++
 fs/resctrl/internal.h                 |  4 ++
 fs/resctrl/monitor.c                  | 56 +++++++++++++++++++++++++
 fs/resctrl/rdtgroup.c                 | 59 ++++++++++++++++++++++++++-
 include/linux/resctrl_types.h         |  3 ++
 5 files changed, 153 insertions(+), 2 deletions(-)

diff --git a/Documentation/filesystems/resctrl.rst b/Documentation/filesystems/resctrl.rst
index 4c24c5f3f4c1..ddd95f1472e6 100644
--- a/Documentation/filesystems/resctrl.rst
+++ b/Documentation/filesystems/resctrl.rst
@@ -310,6 +310,39 @@ with the following files:
 	  # cat /sys/fs/resctrl/info/L3_MON/available_mbm_cntrs
 	  0=30;1=30
 
+"event_configs":
+	Directory that exists when "mbm_event" counter assignment mode is supported.
+	Contains a sub-directory for each MBM event that can be assigned to a counter.
+
+	Two MBM events are supported by default: mbm_local_bytes and mbm_total_bytes.
+	Each MBM event's sub-directory contains a file named "event_filter" that is
+	used to view and modify which memory transactions the MBM event is configured
+	with. The file is accessible only when "mbm_event" counter assignment mode is
+	enabled.
+
+	List of memory transaction types supported:
+
+	==========================  ========================================================
+	Name			    Description
+	==========================  ========================================================
+	dirty_victim_writes_all     Dirty Victims from the QOS domain to all types of memory
+	remote_reads_slow_memory    Reads to slow memory in the non-local NUMA domain
+	local_reads_slow_memory     Reads to slow memory in the local NUMA domain
+	remote_non_temporal_writes  Non-temporal writes to non-local NUMA domain
+	local_non_temporal_writes   Non-temporal writes to local NUMA domain
+	remote_reads                Reads to memory in the non-local NUMA domain
+	local_reads                 Reads to memory in the local NUMA domain
+	==========================  ========================================================
+
+	For example::
+
+	  # cat /sys/fs/resctrl/info/L3_MON/event_configs/mbm_total_bytes/event_filter
+	  local_reads,remote_reads,local_non_temporal_writes,remote_non_temporal_writes,
+	  local_reads_slow_memory,remote_reads_slow_memory,dirty_victim_writes_all
+
+	  # cat /sys/fs/resctrl/info/L3_MON/event_configs/mbm_local_bytes/event_filter
+	  local_reads,local_non_temporal_writes,local_reads_slow_memory
+
 "max_threshold_occupancy":
 		Read/write file provides the largest value (in
 		bytes) at which a previously used LLC_occupancy
diff --git a/fs/resctrl/internal.h b/fs/resctrl/internal.h
index 88e1a800417d..7b1206fff116 100644
--- a/fs/resctrl/internal.h
+++ b/fs/resctrl/internal.h
@@ -241,6 +241,8 @@ struct rdtgroup {
 
 #define RFTYPE_DEBUG			BIT(10)
 
+#define RFTYPE_ASSIGN_CONFIG		BIT(11)
+
 #define RFTYPE_CTRL_INFO		(RFTYPE_INFO | RFTYPE_CTRL)
 
 #define RFTYPE_MON_INFO			(RFTYPE_INFO | RFTYPE_MON)
@@ -403,6 +405,8 @@ void rdtgroup_assign_cntrs(struct rdtgroup *rdtgrp);
 
 void rdtgroup_unassign_cntrs(struct rdtgroup *rdtgrp);
 
+int event_filter_show(struct kernfs_open_file *of, struct seq_file *seq, void *v);
+
 #ifdef CONFIG_RESCTRL_FS_PSEUDO_LOCK
 int rdtgroup_locksetup_enter(struct rdtgroup *rdtgrp);
 
diff --git a/fs/resctrl/monitor.c b/fs/resctrl/monitor.c
index 0a9d257e27a2..25fec9bf2d61 100644
--- a/fs/resctrl/monitor.c
+++ b/fs/resctrl/monitor.c
@@ -974,6 +974,61 @@ u32 resctrl_get_mon_evt_cfg(enum resctrl_event_id evtid)
 	return mon_event_all[evtid].evt_cfg;
 }
 
+/**
+ * struct mbm_transaction - Memory transaction an MBM event can be configured with.
+ * @name:	Name of memory transaction (read, write ...).
+ * @val:	The bit (eg. READS_TO_LOCAL_MEM or READS_TO_REMOTE_MEM) used to
+ *		represent the memory transaction within an event's configuration.
+ */
+struct mbm_transaction {
+	char	name[32];
+	u32	val;
+};
+
+/* Decoded values for each type of memory transaction. */
+static struct mbm_transaction mbm_transactions[NUM_MBM_TRANSACTIONS] = {
+	{"local_reads", READS_TO_LOCAL_MEM},
+	{"remote_reads", READS_TO_REMOTE_MEM},
+	{"local_non_temporal_writes", NON_TEMP_WRITE_TO_LOCAL_MEM},
+	{"remote_non_temporal_writes", NON_TEMP_WRITE_TO_REMOTE_MEM},
+	{"local_reads_slow_memory", READS_TO_LOCAL_S_MEM},
+	{"remote_reads_slow_memory", READS_TO_REMOTE_S_MEM},
+	{"dirty_victim_writes_all", DIRTY_VICTIMS_TO_ALL_MEM},
+};
+
+int event_filter_show(struct kernfs_open_file *of, struct seq_file *seq, void *v)
+{
+	struct mon_evt *mevt = rdt_kn_parent_priv(of->kn);
+	struct rdt_resource *r;
+	bool sep = false;
+	int ret = 0, i;
+
+	mutex_lock(&rdtgroup_mutex);
+	rdt_last_cmd_clear();
+
+	r = resctrl_arch_get_resource(mevt->rid);
+	if (!resctrl_arch_mbm_cntr_assign_enabled(r)) {
+		rdt_last_cmd_puts("mbm_event counter assignment mode is not enabled\n");
+		ret = -EINVAL;
+		goto out_unlock;
+	}
+
+	for (i = 0; i < NUM_MBM_TRANSACTIONS; i++) {
+		if (mevt->evt_cfg & mbm_transactions[i].val) {
+			if (sep)
+				seq_putc(seq, ',');
+			seq_printf(seq, "%s", mbm_transactions[i].name);
+			sep = true;
+		}
+	}
+	seq_putc(seq, '\n');
+
+out_unlock:
+	mutex_unlock(&rdtgroup_mutex);
+
+	return ret;
+}
+
 /*
  * rdtgroup_assign_cntr() - Assign/unassign the counter ID for the event, RMID
  * pair in the domain.
@@ -1289,6 +1344,7 @@ int resctrl_mon_resource_init(void)
 					 RFTYPE_MON_INFO | RFTYPE_RES_CACHE);
 		resctrl_file_fflags_init("available_mbm_cntrs",
 					 RFTYPE_MON_INFO | RFTYPE_RES_CACHE);
+		resctrl_file_fflags_init("event_filter", RFTYPE_ASSIGN_CONFIG);
 	}
 
 	return 0;
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index 2e1d0a2703da..8f0c403e3fb5 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -1923,6 +1923,12 @@ static struct rftype res_common_files[] = {
 		.seq_show	= mbm_local_bytes_config_show,
 		.write		= mbm_local_bytes_config_write,
 	},
+	{
+		.name		= "event_filter",
+		.mode		= 0444,
+		.kf_ops		= &rdtgroup_kf_single_ops,
+		.seq_show	= event_filter_show,
+	},
 	{
 		.name		= "mbm_assign_mode",
 		.mode		= 0444,
@@ -2183,10 +2189,48 @@ int rdtgroup_kn_mode_restore(struct rdtgroup *r, const char *name,
 	return ret;
 }
 
+static int resctrl_mkdir_event_configs(struct rdt_resource *r, struct kernfs_node *l3_mon_kn)
+{
+	struct kernfs_node *kn_subdir, *kn_subdir2;
+	struct mon_evt *mevt;
+	int ret;
+
+	kn_subdir = kernfs_create_dir(l3_mon_kn, "event_configs", l3_mon_kn->mode, NULL);
+	if (IS_ERR(kn_subdir))
+		return PTR_ERR(kn_subdir);
+
+	ret = rdtgroup_kn_set_ugid(kn_subdir);
+	if (ret)
+		return ret;
+
+	for_each_mon_event(mevt) {
+		if (mevt->rid != r->rid || !mevt->enabled || !resctrl_is_mbm_event(mevt->evtid))
+			continue;
+
+		kn_subdir2 = kernfs_create_dir(kn_subdir, mevt->name, kn_subdir->mode, mevt);
+		if (IS_ERR(kn_subdir2)) {
+			ret = PTR_ERR(kn_subdir2);
+			goto out;
+		}
+
+		ret = rdtgroup_kn_set_ugid(kn_subdir2);
+		if (ret)
+			goto out;
+
+		ret = rdtgroup_add_files(kn_subdir2, RFTYPE_ASSIGN_CONFIG);
+		if (ret)
+			break;
+	}
+
+out:
+	return ret;
+}
+
 static int rdtgroup_mkdir_info_resdir(void *priv, char *name,
 				      unsigned long fflags)
 {
 	struct kernfs_node *kn_subdir;
+	struct rdt_resource *r;
 	int ret;
 
 	kn_subdir = kernfs_create_dir(kn_info, name,
@@ -2199,8 +2243,19 @@ static int rdtgroup_mkdir_info_resdir(void *priv, char *name,
 		return ret;
 
 	ret = rdtgroup_add_files(kn_subdir, fflags);
-	if (!ret)
-		kernfs_activate(kn_subdir);
+	if (ret)
+		return ret;
+
+	if ((fflags & RFTYPE_MON_INFO) == RFTYPE_MON_INFO) {
+		r = priv;
+		if (r->mon.mbm_cntr_assignable) {
+			ret = resctrl_mkdir_event_configs(r, kn_subdir);
+			if (ret)
+				return ret;
+		}
+	}
+
+	kernfs_activate(kn_subdir);
 
 	return ret;
 }
diff --git a/include/linux/resctrl_types.h b/include/linux/resctrl_types.h
index d98351663c2c..acfe07860b34 100644
--- a/include/linux/resctrl_types.h
+++ b/include/linux/resctrl_types.h
@@ -34,6 +34,9 @@
 /* Max event bits supported */
 #define MAX_EVT_CONFIG_BITS		GENMASK(6, 0)
 
+/* Number of memory transactions that an MBM event can be configured with */
+#define NUM_MBM_TRANSACTIONS		7
+
 /* Event IDs */
 enum resctrl_event_id {
 	/* Must match value of first event below */

---

## [26] Babu Moger — 2025-09-05
*Subject: [PATCH v18 25/33] fs/resctrl: Provide interface to update the event configurations*

When "mbm_event" counter assignment mode is enabled, users can modify
the event configuration by writing to the 'event_filter' resctrl file.
The event configurations for mbm_event mode are located in
/sys/fs/resctrl/info/L3_MON/event_configs/.

Update the assignments of all CTRL_MON and MON resource groups when the
event configuration is modified.

Example:
$ mount -t resctrl resctrl /sys/fs/resctrl

$ cd /sys/fs/resctrl/

$ cat info/L3_MON/event_configs/mbm_local_bytes/event_filter
  local_reads,local_non_temporal_writes,local_reads_slow_memory

$ echo "local_reads,local_non_temporal_writes" >
  info/L3_MON/event_configs/mbm_total_bytes/event_filter

$ cat info/L3_MON/event_configs/mbm_total_bytes/event_filter
  local_reads,local_non_temporal_writes

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v18: Removed open code in rdtgroup_update_cntr_event(). Called
     rdtgroup_assign_cntr() directly.

v17: Minor changelog update.
     Cleared mbm_state on every assignment update.
     All the code moved monitor.c.

v16: Moved resctrl_process_configs() and event_filter_write()
     to fs/resctrl/monitor.c.
     Renamed resctrl_process_configs() -> resctrl_parse_mem_transactions().
     Few minor code commnet update.

v15: Updated changelog.
     Updated spacing in resctrl.rst.
     Corrected the name counter_configs -> event_configs.
     Changed the name rdtgroup_assign_cntr() > rdtgroup_update_cntr_event().
     Removed the code to check d->cntr_cfg[cntr_id].evt_cfg.
     Fixed the partial initialization of val in resctrl_process_configs().
     Passed mon_evt where applicable. The struct rdt_resource can be obtained from mon_evt::rid.

v14: Passed struct mon_evt where applicable instead of just the event type.
     Fixed few text corrections about memory trasaction type.
     Renamed few functions resctrl_group_assign() -> rdtgroup_assign_cntr()
     resctrl_update_assign() -> resctrl_assign_cntr_allrdtgrp()
     Removed few extra bases.

v13: Updated changelog for imperative mode.
     Added function description in the prototype.
     Updated the user doc resctrl.rst to address few feedback.
     Resolved conflicts caused by the recent FS/ARCH code restructure.
     The rdtgroup.c/monitor.c file has now been split between the FS and ARCH directories.

v12: New patch to modify event configurations.
---
 Documentation/filesystems/resctrl.rst |  12 +++
 fs/resctrl/internal.h                 |   3 +
 fs/resctrl/monitor.c                  | 114 ++++++++++++++++++++++++++
 fs/resctrl/rdtgroup.c                 |   3 +-
 4 files changed, 131 insertions(+), 1 deletion(-)

diff --git a/Documentation/filesystems/resctrl.rst b/Documentation/filesystems/resctrl.rst
index ddd95f1472e6..2e840ef26f68 100644
--- a/Documentation/filesystems/resctrl.rst
+++ b/Documentation/filesystems/resctrl.rst
@@ -343,6 +343,18 @@ with the following files:
 	  # cat /sys/fs/resctrl/info/L3_MON/event_configs/mbm_local_bytes/event_filter
 	  local_reads,local_non_temporal_writes,local_reads_slow_memory
 
+	Modify the event configuration by writing to the "event_filter" file within
+	the "event_configs" directory. The read/write "event_filter" file contains the
+	configuration of the event that reflects which memory transactions are counted by it.
+
+	For example::
+
+	  # echo "local_reads, local_non_temporal_writes" >
+	    /sys/fs/resctrl/info/L3_MON/event_configs/mbm_total_bytes/event_filter
+
+	  # cat /sys/fs/resctrl/info/L3_MON/event_configs/mbm_total_bytes/event_filter
+	   local_reads,local_non_temporal_writes
+
 "max_threshold_occupancy":
 		Read/write file provides the largest value (in
 		bytes) at which a previously used LLC_occupancy
diff --git a/fs/resctrl/internal.h b/fs/resctrl/internal.h
index 7b1206fff116..5956570d49fc 100644
--- a/fs/resctrl/internal.h
+++ b/fs/resctrl/internal.h
@@ -407,6 +407,9 @@ void rdtgroup_unassign_cntrs(struct rdtgroup *rdtgrp);
 
 int event_filter_show(struct kernfs_open_file *of, struct seq_file *seq, void *v);
 
+ssize_t event_filter_write(struct kernfs_open_file *of, char *buf, size_t nbytes,
+			   loff_t off);
+
 #ifdef CONFIG_RESCTRL_FS_PSEUDO_LOCK
 int rdtgroup_locksetup_enter(struct rdtgroup *rdtgrp);
 
diff --git a/fs/resctrl/monitor.c b/fs/resctrl/monitor.c
index 25fec9bf2d61..a4bbd45fc58a 100644
--- a/fs/resctrl/monitor.c
+++ b/fs/resctrl/monitor.c
@@ -1194,6 +1194,120 @@ void rdtgroup_unassign_cntrs(struct rdtgroup *rdtgrp)
 					     &mon_event_all[QOS_L3_MBM_LOCAL_EVENT_ID]);
 }
 
+static int resctrl_parse_mem_transactions(char *tok, u32 *val)
+{
+	u32 temp_val = 0;
+	char *evt_str;
+	bool found;
+	int i;
+
+next_config:
+	if (!tok || tok[0] == '\0') {
+		*val = temp_val;
+		return 0;
+	}
+
+	/* Start processing the strings for each memory transaction type */
+	evt_str = strim(strsep(&tok, ","));
+	found = false;
+	for (i = 0; i < NUM_MBM_TRANSACTIONS; i++) {
+		if (!strcmp(mbm_transactions[i].name, evt_str)) {
+			temp_val |= mbm_transactions[i].val;
+			found = true;
+			break;
+		}
+	}
+
+	if (!found) {
+		rdt_last_cmd_printf("Invalid memory transaction type %s\n", evt_str);
+		return -EINVAL;
+	}
+
+	goto next_config;
+}
+
+/*
+ * rdtgroup_update_cntr_event - Update the counter assignments for the event
+ *				in a group.
+ * @r:		Resource to which update needs to be done.
+ * @rdtgrp:	Resctrl group.
+ * @evtid:	MBM monitor event.
+ */
+static void rdtgroup_update_cntr_event(struct rdt_resource *r, struct rdtgroup *rdtgrp,
+				       enum resctrl_event_id evtid)
+{
+	struct rdt_mon_domain *d;
+	int cntr_id;
+
+	list_for_each_entry(d, &r->mon_domains, hdr.list) {
+		cntr_id = mbm_cntr_get(r, d, rdtgrp, evtid);
+		if (cntr_id >= 0)
+			rdtgroup_assign_cntr(r, d, evtid, rdtgrp->mon.rmid,
+					     rdtgrp->closid, cntr_id, true);
+	}
+}
+
+/*
+ * resctrl_update_cntr_allrdtgrp - Update the counter assignments for the event
+ *				   for all the groups.
+ * @mevt	MBM Monitor event.
+ */
+static void resctrl_update_cntr_allrdtgrp(struct mon_evt *mevt)
+{
+	struct rdt_resource *r = resctrl_arch_get_resource(mevt->rid);
+	struct rdtgroup *prgrp, *crgrp;
+
+	/*
+	 * Find all the groups where the event is assigned and update the
+	 * configuration of existing assignments.
+	 */
+	list_for_each_entry(prgrp, &rdt_all_groups, rdtgroup_list) {
+		rdtgroup_update_cntr_event(r, prgrp, mevt->evtid);
+
+		list_for_each_entry(crgrp, &prgrp->mon.crdtgrp_list, mon.crdtgrp_list)
+			rdtgroup_update_cntr_event(r, crgrp, mevt->evtid);
+	}
+}
+
+ssize_t event_filter_write(struct kernfs_open_file *of, char *buf, size_t nbytes,
+			   loff_t off)
+{
+	struct mon_evt *mevt = rdt_kn_parent_priv(of->kn);
+	struct rdt_resource *r;
+	u32 evt_cfg = 0;
+	int ret = 0;
+
+	/* Valid input requires a trailing newline */
+	if (nbytes == 0 || buf[nbytes - 1] != '\n')
+		return -EINVAL;
+
+	buf[nbytes - 1] = '\0';
+
+	cpus_read_lock();
+	mutex_lock(&rdtgroup_mutex);
+
+	rdt_last_cmd_clear();
+
+	r = resctrl_arch_get_resource(mevt->rid);
+	if (!resctrl_arch_mbm_cntr_assign_enabled(r)) {
+		rdt_last_cmd_puts("mbm_event counter assignment mode is not enabled\n");
+		ret = -EINVAL;
+		goto out_unlock;
+	}
+
+	ret = resctrl_parse_mem_transactions(buf, &evt_cfg);
+	if (!ret && mevt->evt_cfg != evt_cfg) {
+		mevt->evt_cfg = evt_cfg;
+		resctrl_update_cntr_allrdtgrp(mevt);
+	}
+
+out_unlock:
+	mutex_unlock(&rdtgroup_mutex);
+	cpus_read_unlock();
+
+	return ret ?: nbytes;
+}
+
 int resctrl_mbm_assign_mode_show(struct kernfs_open_file *of,
 				 struct seq_file *s, void *v)
 {
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index 8f0c403e3fb5..e90bc808fe53 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -1925,9 +1925,10 @@ static struct rftype res_common_files[] = {
 	},
 	{
 		.name		= "event_filter",
-		.mode		= 0444,
+		.mode		= 0644,
 		.kf_ops		= &rdtgroup_kf_single_ops,
 		.seq_show	= event_filter_show,
+		.write		= event_filter_write,
 	},
 	{
 		.name		= "mbm_assign_mode",

---

## [27] Babu Moger — 2025-09-05
*Subject: [PATCH v18 26/33] fs/resctrl: Introduce mbm_assign_on_mkdir to enable assignments on mkdir*

The "mbm_event" counter assignment mode allows users to assign a hardware
counter to an RMID, event pair and monitor the bandwidth as long as it is
assigned.

Introduce a user-configurable option that determines if a counter will
automatically be assigned to an RMID, event pair when its associated
monitor group is created via mkdir. Accessible when "mbm_event" counter
assignment mode is enabled.

Suggested-by: Peter Newman <peternewman@google.com>
Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: Mismatched quote fix in changelog.
     Added Reviewed-by tag.
     Updated the coverletter to add mbm_assign_on_mkdir.

v17: Added the check resctrl_arch_mbm_cntr_assign_enabled() in
     resctrl_mbm_assign_on_mkdir_show() and resctrl_mbm_assign_on_mkdir_write()
     to make it accessible when mbm_event mode is enabled.
     Added texts in resctrl.rst about the accessability.

v16: Fixed the return in resctrl_mbm_assign_on_mkdir_write().

v15: Fixed the static checker warning in resctrl_mbm_assign_on_mkdir_write() reported in
     https://lore.kernel.org/lkml/dd4a1021-b996-438e-941c-69dfcea5f22a@intel.com/

v14: Added rdtgroup_mutex in resctrl_mbm_assign_on_mkdir_show().
     Updated resctrl.rst for clarity.
     Fixed squashing of few previous changes.
     Added more code documentation.

v13: Added Suggested-by tag.
     Resolved conflicts caused by the recent FS/ARCH code restructure.
     The rdtgroup.c/monitor.c file has now been split between the FS and ARCH directories.

v12: New patch. Added after the discussion on the list.
     https://lore.kernel.org/lkml/CALPaoCh8siZKjL_3yvOYGL4cF_n_38KpUFgHVGbQ86nD+Q2_SA@mail.gmail.com/
---
 Documentation/filesystems/resctrl.rst | 20 ++++++++++
 fs/resctrl/internal.h                 |  6 +++
 fs/resctrl/monitor.c                  | 53 +++++++++++++++++++++++++++
 fs/resctrl/rdtgroup.c                 |  7 ++++
 include/linux/resctrl.h               |  3 ++
 5 files changed, 89 insertions(+)

diff --git a/Documentation/filesystems/resctrl.rst b/Documentation/filesystems/resctrl.rst
index 2e840ef26f68..1de815b3a07b 100644
--- a/Documentation/filesystems/resctrl.rst
+++ b/Documentation/filesystems/resctrl.rst
@@ -355,6 +355,26 @@ with the following files:
 	  # cat /sys/fs/resctrl/info/L3_MON/event_configs/mbm_total_bytes/event_filter
 	   local_reads,local_non_temporal_writes
 
+"mbm_assign_on_mkdir":
+	Exists when "mbm_event" counter assignment mode is supported. Accessible
+	only when "mbm_event" counter assignment mode is enabled.
+
+	Determines if a counter will automatically be assigned to an RMID, MBM event
+	pair when its associated monitor group is created via mkdir. Enabled by default
+	on boot, also when switched from "default" mode to "mbm_event" counter assignment
+	mode. Users can disable this capability by writing to the interface.
+
+	"0":
+		Auto assignment is disabled.
+	"1":
+		Auto assignment is enabled.
+
+	Example::
+
+	  # echo 0 > /sys/fs/resctrl/info/L3_MON/mbm_assign_on_mkdir
+	  # cat /sys/fs/resctrl/info/L3_MON/mbm_assign_on_mkdir
+	  0
+
 "max_threshold_occupancy":
 		Read/write file provides the largest value (in
 		bytes) at which a previously used LLC_occupancy
diff --git a/fs/resctrl/internal.h b/fs/resctrl/internal.h
index 5956570d49fc..9be1e53a73d3 100644
--- a/fs/resctrl/internal.h
+++ b/fs/resctrl/internal.h
@@ -410,6 +410,12 @@ int event_filter_show(struct kernfs_open_file *of, struct seq_file *seq, void *v
 ssize_t event_filter_write(struct kernfs_open_file *of, char *buf, size_t nbytes,
 			   loff_t off);
 
+int resctrl_mbm_assign_on_mkdir_show(struct kernfs_open_file *of,
+				     struct seq_file *s, void *v);
+
+ssize_t resctrl_mbm_assign_on_mkdir_write(struct kernfs_open_file *of, char *buf,
+					  size_t nbytes, loff_t off);
+
 #ifdef CONFIG_RESCTRL_FS_PSEUDO_LOCK
 int rdtgroup_locksetup_enter(struct rdtgroup *rdtgrp);
 
diff --git a/fs/resctrl/monitor.c b/fs/resctrl/monitor.c
index a4bbd45fc58a..b3d33b983c3c 100644
--- a/fs/resctrl/monitor.c
+++ b/fs/resctrl/monitor.c
@@ -1029,6 +1029,57 @@ int event_filter_show(struct kernfs_open_file *of, struct seq_file *seq, void *v
 	return ret;
 }
 
+int resctrl_mbm_assign_on_mkdir_show(struct kernfs_open_file *of, struct seq_file *s,
+				     void *v)
+{
+	struct rdt_resource *r = rdt_kn_parent_priv(of->kn);
+	int ret = 0;
+
+	mutex_lock(&rdtgroup_mutex);
+	rdt_last_cmd_clear();
+
+	if (!resctrl_arch_mbm_cntr_assign_enabled(r)) {
+		rdt_last_cmd_puts("mbm_event counter assignment mode is not enabled\n");
+		ret = -EINVAL;
+		goto out_unlock;
+	}
+
+	seq_printf(s, "%u\n", r->mon.mbm_assign_on_mkdir);
+
+out_unlock:
+	mutex_unlock(&rdtgroup_mutex);
+
+	return ret;
+}
+
+ssize_t resctrl_mbm_assign_on_mkdir_write(struct kernfs_open_file *of, char *buf,
+					  size_t nbytes, loff_t off)
+{
+	struct rdt_resource *r = rdt_kn_parent_priv(of->kn);
+	bool value;
+	int ret;
+
+	ret = kstrtobool(buf, &value);
+	if (ret)
+		return ret;
+
+	mutex_lock(&rdtgroup_mutex);
+	rdt_last_cmd_clear();
+
+	if (!resctrl_arch_mbm_cntr_assign_enabled(r)) {
+		rdt_last_cmd_puts("mbm_event counter assignment mode is not enabled\n");
+		ret = -EINVAL;
+		goto out_unlock;
+	}
+
+	r->mon.mbm_assign_on_mkdir = value;
+
+out_unlock:
+	mutex_unlock(&rdtgroup_mutex);
+
+	return ret ?: nbytes;
+}
+
 /*
  * rdtgroup_assign_cntr() - Assign/unassign the counter ID for the event, RMID
  * pair in the domain.
@@ -1459,6 +1510,8 @@ int resctrl_mon_resource_init(void)
 		resctrl_file_fflags_init("available_mbm_cntrs",
 					 RFTYPE_MON_INFO | RFTYPE_RES_CACHE);
 		resctrl_file_fflags_init("event_filter", RFTYPE_ASSIGN_CONFIG);
+		resctrl_file_fflags_init("mbm_assign_on_mkdir", RFTYPE_MON_INFO |
+					 RFTYPE_RES_CACHE);
 	}
 
 	return 0;
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index e90bc808fe53..c7ea42c2a3c2 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -1808,6 +1808,13 @@ static struct rftype res_common_files[] = {
 		.seq_show	= rdt_last_cmd_status_show,
 		.fflags		= RFTYPE_TOP_INFO,
 	},
+	{
+		.name		= "mbm_assign_on_mkdir",
+		.mode		= 0644,
+		.kf_ops		= &rdtgroup_kf_single_ops,
+		.seq_show	= resctrl_mbm_assign_on_mkdir_show,
+		.write		= resctrl_mbm_assign_on_mkdir_write,
+	},
 	{
 		.name		= "num_closids",
 		.mode		= 0444,
diff --git a/include/linux/resctrl.h b/include/linux/resctrl.h
index 04152654827d..a7d92718b653 100644
--- a/include/linux/resctrl.h
+++ b/include/linux/resctrl.h
@@ -277,12 +277,15 @@ enum resctrl_schema_fmt {
  *			monitoring events can be configured.
  * @num_mbm_cntrs:	Number of assignable counters.
  * @mbm_cntr_assignable:Is system capable of supporting counter assignment?
+ * @mbm_assign_on_mkdir:True if counters should automatically be assigned to MBM
+ *			events of monitor groups created via mkdir.
  */
 struct resctrl_mon {
 	int			num_rmid;
 	unsigned int		mbm_cfg_mask;
 	int			num_mbm_cntrs;
 	bool			mbm_cntr_assignable;
+	bool			mbm_assign_on_mkdir;
 };
 
 /**

---

## [28] Babu Moger — 2025-09-05
*Subject: [PATCH v18 27/33] fs/resctrl: Auto assign counters on mkdir and clean up on group removal*

Resctrl provides a user-configurable option mbm_assign_on_mkdir that
determines if a counter will automatically be assigned to an RMID, event
pair when its associated monitor group is created via mkdir.

Enable mbm_assign_on_mkdir by default to automatically assign counters to
the two default events (MBM total and MBM local) of a new monitoring group
created via mkdir. This maintains backward compatibility with original
resctrl support for these two events.

Unassign and free counters belonging to a monitoring group when the group
is deleted.

Monitor group creation does not fail if a counter cannot be assigned to one
or both events. There may be limited counters and users have the
flexibility to modify counter assignments at a later time. Log the error
message "Failed to allocate counter for <event> in domain <id>" in
/sys/fs/resctrl/info/last_cmd_status when a new monitoring group is created
but counter assignment failed.

Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: Added Reviewed-by tag.

v17: rdtgroup_assign_cntrs() and rdtgroup_unassign_cntrs() have been moved to
     patch 17 and 18 respectively.

v16: Updated the changelog. Thanks to Reinette.
     Moved r->mon.mbm_assign_on_mkdir initialization to resctrl_mon_resource_init().
     Minor code comment update.
     Updated  the Subject line to fs/resctrl:

v15: Updated the subject line.
     Updated changelog to add unassign part.
     Fixed the check in rdtgroup_assign_cntrs() to call assign correctly.
     Renamed resctrl_assign_cntr_event() -> rdtgroup_assign_cntr_event()
             resctrl_unassign_cntr_event() -> rdtgroup_unassign_cntr_event().

v14: Updated the changelog with changed name mbm_event.
     Update code comments with changed name mbm_event.
     Changed the code to reflect Tony's struct mon_evt changes.

v13: Changes due to calling of resctrl_assign_cntr_event() and resctrl_unassign_cntr_event().
     It only takes evtid. evt_cfg is not required anymore.
     Resolved conflicts caused by the recent FS/ARCH code restructure.
     The monitor.c/rdtgroup.c files have been split between the FS and ARCH directories.

v12: Removed mbm_cntr_reset() as it is not required while removing the group.
     Update the commit text.
     Added r->mon_capable  check in rdtgroup_assign_cntrs() and rdtgroup_unassign_cntrs.

v11: Moved mbm_cntr_reset() to monitor.c.
     Added code reset non-architectural state in mbm_cntr_reset().
     Added missing rdtgroup_unassign_cntrs() calls on failure path.

v10: Assigned the counter before exposing the event files.
    Moved the call rdtgroup_assign_cntrs() inside mkdir_rdt_prepare_rmid_alloc().
    This is called both CNTR_MON and MON group creation.
    Call mbm_cntr_reset() when unmounted to clear all the assignments.
    Taken care of few other feedback comments.

v9: Changed rdtgroup_assign_cntrs() and rdtgroup_unassign_cntrs() to return void.
    Updated couple of rdtgroup_unassign_cntrs() calls properly.
    Updated function comments.

v8: Renamed rdtgroup_assign_grp to rdtgroup_assign_cntrs.
    Renamed rdtgroup_unassign_grp to rdtgroup_unassign_cntrs.
    Fixed the problem with unassigning the child MON groups of CTRL_MON group.

v7: Reworded the commit message.
    Removed the reference of ABMC with mbm_cntr_assign.
    Renamed the function rdtgroup_assign_cntrs to rdtgroup_assign_grp.

v6: Removed the redundant comments on all the calls of
    rdtgroup_assign_cntrs. Updated the commit message.
    Dropped printing error message on every call of rdtgroup_assign_cntrs.

v5: Removed the code to enable/disable ABMC during the mount.
    That will be another patch.
    Added arch callers to get the arch specific data.
    Renamed fuctions to match the other abmc function.
    Added code comments for assignment failures.

v4: Few name changes based on the upstream discussion.
    Commit message update.

v3: This is a new patch. Patch addresses the upstream comment to enable
    ABMC feature by default if the feature is available.
---
 fs/resctrl/monitor.c  |  4 +++-
 fs/resctrl/rdtgroup.c | 22 ++++++++++++++++++++--
 2 files changed, 23 insertions(+), 3 deletions(-)

diff --git a/fs/resctrl/monitor.c b/fs/resctrl/monitor.c
index b3d33b983c3c..13af138d4b3b 100644
--- a/fs/resctrl/monitor.c
+++ b/fs/resctrl/monitor.c
@@ -1233,7 +1233,8 @@ void rdtgroup_unassign_cntrs(struct rdtgroup *rdtgrp)
 {
 	struct rdt_resource *r = resctrl_arch_get_resource(RDT_RESOURCE_L3);
 
-	if (!r->mon_capable || !resctrl_arch_mbm_cntr_assign_enabled(r))
+	if (!r->mon_capable || !resctrl_arch_mbm_cntr_assign_enabled(r) ||
+	    !r->mon.mbm_assign_on_mkdir)
 		return;
 
 	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID))
@@ -1505,6 +1506,7 @@ int resctrl_mon_resource_init(void)
 								   (READS_TO_LOCAL_MEM |
 								    READS_TO_LOCAL_S_MEM |
 								    NON_TEMP_WRITE_TO_LOCAL_MEM);
+		r->mon.mbm_assign_on_mkdir = true;
 		resctrl_file_fflags_init("num_mbm_cntrs",
 					 RFTYPE_MON_INFO | RFTYPE_RES_CACHE);
 		resctrl_file_fflags_init("available_mbm_cntrs",
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index c7ea42c2a3c2..48f98146c099 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -2713,6 +2713,8 @@ static int rdt_get_tree(struct fs_context *fc)
 		if (ret < 0)
 			goto out_info;
 
+		rdtgroup_assign_cntrs(&rdtgroup_default);
+
 		ret = mkdir_mondata_all(rdtgroup_default.kn,
 					&rdtgroup_default, &kn_mondata);
 		if (ret < 0)
@@ -2751,8 +2753,10 @@ static int rdt_get_tree(struct fs_context *fc)
 	if (resctrl_arch_mon_capable())
 		kernfs_remove(kn_mondata);
 out_mongrp:
-	if (resctrl_arch_mon_capable())
+	if (resctrl_arch_mon_capable()) {
+		rdtgroup_unassign_cntrs(&rdtgroup_default);
 		kernfs_remove(kn_mongrp);
+	}
 out_info:
 	kernfs_remove(kn_info);
 out_closid_exit:
@@ -2897,6 +2901,7 @@ static void free_all_child_rdtgrp(struct rdtgroup *rdtgrp)
 
 	head = &rdtgrp->mon.crdtgrp_list;
 	list_for_each_entry_safe(sentry, stmp, head, mon.crdtgrp_list) {
+		rdtgroup_unassign_cntrs(sentry);
 		free_rmid(sentry->closid, sentry->mon.rmid);
 		list_del(&sentry->mon.crdtgrp_list);
 
@@ -2937,6 +2942,8 @@ static void rmdir_all_sub(void)
 		cpumask_or(&rdtgroup_default.cpu_mask,
 			   &rdtgroup_default.cpu_mask, &rdtgrp->cpu_mask);
 
+		rdtgroup_unassign_cntrs(rdtgrp);
+
 		free_rmid(rdtgrp->closid, rdtgrp->mon.rmid);
 
 		kernfs_remove(rdtgrp->kn);
@@ -3021,6 +3028,7 @@ static void resctrl_fs_teardown(void)
 		return;
 
 	rmdir_all_sub();
+	rdtgroup_unassign_cntrs(&rdtgroup_default);
 	mon_put_kn_priv();
 	rdt_pseudo_lock_release();
 	rdtgroup_default.mode = RDT_MODE_SHAREABLE;
@@ -3501,9 +3509,12 @@ static int mkdir_rdt_prepare_rmid_alloc(struct rdtgroup *rdtgrp)
 	}
 	rdtgrp->mon.rmid = ret;
 
+	rdtgroup_assign_cntrs(rdtgrp);
+
 	ret = mkdir_mondata_all(rdtgrp->kn, rdtgrp, &rdtgrp->mon.mon_data_kn);
 	if (ret) {
 		rdt_last_cmd_puts("kernfs subdir error\n");
+		rdtgroup_unassign_cntrs(rdtgrp);
 		free_rmid(rdtgrp->closid, rdtgrp->mon.rmid);
 		return ret;
 	}
@@ -3513,8 +3524,10 @@ static int mkdir_rdt_prepare_rmid_alloc(struct rdtgroup *rdtgrp)
 
 static void mkdir_rdt_prepare_rmid_free(struct rdtgroup *rgrp)
 {
-	if (resctrl_arch_mon_capable())
+	if (resctrl_arch_mon_capable()) {
+		rdtgroup_unassign_cntrs(rgrp);
 		free_rmid(rgrp->closid, rgrp->mon.rmid);
+	}
 }
 
 /*
@@ -3790,6 +3803,9 @@ static int rdtgroup_rmdir_mon(struct rdtgroup *rdtgrp, cpumask_var_t tmpmask)
 	update_closid_rmid(tmpmask, NULL);
 
 	rdtgrp->flags = RDT_DELETED;
+
+	rdtgroup_unassign_cntrs(rdtgrp);
+
 	free_rmid(rdtgrp->closid, rdtgrp->mon.rmid);
 
 	/*
@@ -3837,6 +3853,8 @@ static int rdtgroup_rmdir_ctrl(struct rdtgroup *rdtgrp, cpumask_var_t tmpmask)
 	cpumask_or(tmpmask, tmpmask, &rdtgrp->cpu_mask);
 	update_closid_rmid(tmpmask, NULL);
 
+	rdtgroup_unassign_cntrs(rdtgrp);
+
 	free_rmid(rdtgrp->closid, rdtgrp->mon.rmid);
 	closid_free(rdtgrp->closid);

---

## [29] Babu Moger — 2025-09-05
*Subject: [PATCH v18 28/33] fs/resctrl: Introduce mbm_L3_assignments to list assignments in a group*

Introduce the mbm_L3_assignments resctrl file associated with CTRL_MON and
MON resource groups to display the counter assignment states of the
resource group when "mbm_event" counter assignment mode is enabled.

Display the list in the following format:
<Event>:<Domain id>=<Assignment state>;<Domain id>=<Assignment state>

Event: A valid MBM event listed in
       /sys/fs/resctrl/info/L3_MON/event_configs directory.

Domain ID: A valid domain ID.

The assignment state can be one of the following:

_ : No counter assigned.

e : Counter assigned exclusively.

Example:
To list the assignment states for the default group
$ cd /sys/fs/resctrl
$ cat /sys/fs/resctrl/mbm_L3_assignments
mbm_total_bytes:0=e;1=e
mbm_local_bytes:0=e;1=e

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v18: Moved documentation of "mbm_L3_assignments" just after mon_hw_id.

v17: Moved mbm_L3_assignments_show() to fs/resctrl/monitor.c.
     mbm_cntr_get() can stay static.
     Minor change in changelog for imperative mode.
     Fixed the return error for consistancy.

v16: Fixed minor merge conflicts with code displacement.
     Changed the check with mbm_cntr_get() to "< 0" from " >=".

v15: Updated the changelog with Reinette's text.
     Updated the event format list to list multiple domains.
     Changed the goto out_assing to out_unlock.
     Updated to use new loop for_each_mon_event() instead of hardcoding.

v14: Added missed rdtgroup_kn_lock_live on failure case.
     Updated the user doc resctrl.rst to clarify counter assignments.
     Updated the changelog.

v13: Changelog update.
     Few changes in mbm_L3_assignments_show() after moving the event config to evt_list.
     Resolved conflicts caused by the recent FS/ARCH code restructure.
     The rdtgroup.c/monitor.c files have been split between the FS and ARCH directories.

v12: New patch:
     Assignment interface moved inside the group based the discussion
     https://lore.kernel.org/lkml/CALPaoCiii0vXOF06mfV=kVLBzhfNo0SFqt4kQGwGSGVUqvr2Dg@mail.gmail.com/#t
---
 Documentation/filesystems/resctrl.rst | 31 +++++++++++++++++
 fs/resctrl/internal.h                 |  2 ++
 fs/resctrl/monitor.c                  | 49 +++++++++++++++++++++++++++
 fs/resctrl/rdtgroup.c                 |  6 ++++
 4 files changed, 88 insertions(+)

diff --git a/Documentation/filesystems/resctrl.rst b/Documentation/filesystems/resctrl.rst
index 1de815b3a07b..a2b7240b0818 100644
--- a/Documentation/filesystems/resctrl.rst
+++ b/Documentation/filesystems/resctrl.rst
@@ -509,6 +509,37 @@ When monitoring is enabled all MON groups will also contain:
 	Available only with debug option. The identifier used by hardware
 	for the monitor group. On x86 this is the RMID.
 
+When monitoring is enabled all MON groups may also contain:
+
+"mbm_L3_assignments":
+	Exists when "mbm_event" counter assignment mode is supported and lists the
+	counter assignment states of the group.
+
+	The assignment list is displayed in the following format:
+
+	<Event>:<Domain ID>=<Assignment state>;<Domain ID>=<Assignment state>
+
+	Event: A valid MBM event in the
+	       /sys/fs/resctrl/info/L3_MON/event_configs directory.
+
+	Domain ID: A valid domain ID.
+
+	Assignment states:
+
+	_ : No counter assigned.
+
+	e : Counter assigned exclusively.
+
+	Example:
+
+	To display the counter assignment states for the default group.
+	::
+
+	 # cd /sys/fs/resctrl
+	 # cat /sys/fs/resctrl/mbm_L3_assignments
+	   mbm_total_bytes:0=e;1=e
+	   mbm_local_bytes:0=e;1=e
+
 When the "mba_MBps" mount option is used all CTRL_MON groups will also contain:
 
 "mba_MBps_event":
diff --git a/fs/resctrl/internal.h b/fs/resctrl/internal.h
index 9be1e53a73d3..88079ca0d57a 100644
--- a/fs/resctrl/internal.h
+++ b/fs/resctrl/internal.h
@@ -416,6 +416,8 @@ int resctrl_mbm_assign_on_mkdir_show(struct kernfs_open_file *of,
 ssize_t resctrl_mbm_assign_on_mkdir_write(struct kernfs_open_file *of, char *buf,
 					  size_t nbytes, loff_t off);
 
+int mbm_L3_assignments_show(struct kernfs_open_file *of, struct seq_file *s, void *v);
+
 #ifdef CONFIG_RESCTRL_FS_PSEUDO_LOCK
 int rdtgroup_locksetup_enter(struct rdtgroup *rdtgrp);
 
diff --git a/fs/resctrl/monitor.c b/fs/resctrl/monitor.c
index 13af138d4b3b..e8c3b3a7987b 100644
--- a/fs/resctrl/monitor.c
+++ b/fs/resctrl/monitor.c
@@ -1456,6 +1456,54 @@ int resctrl_available_mbm_cntrs_show(struct kernfs_open_file *of,
 	return ret;
 }
 
+int mbm_L3_assignments_show(struct kernfs_open_file *of, struct seq_file *s, void *v)
+{
+	struct rdt_resource *r = resctrl_arch_get_resource(RDT_RESOURCE_L3);
+	struct rdt_mon_domain *d;
+	struct rdtgroup *rdtgrp;
+	struct mon_evt *mevt;
+	int ret = 0;
+	bool sep;
+
+	rdtgrp = rdtgroup_kn_lock_live(of->kn);
+	if (!rdtgrp) {
+		ret = -ENOENT;
+		goto out_unlock;
+	}
+
+	rdt_last_cmd_clear();
+	if (!resctrl_arch_mbm_cntr_assign_enabled(r)) {
+		rdt_last_cmd_puts("mbm_event counter assignment mode is not enabled\n");
+		ret = -EINVAL;
+		goto out_unlock;
+	}
+
+	for_each_mon_event(mevt) {
+		if (mevt->rid != r->rid || !mevt->enabled || !resctrl_is_mbm_event(mevt->evtid))
+			continue;
+
+		sep = false;
+		seq_printf(s, "%s:", mevt->name);
+		list_for_each_entry(d, &r->mon_domains, hdr.list) {
+			if (sep)
+				seq_putc(s, ';');
+
+			if (mbm_cntr_get(r, d, rdtgrp, mevt->evtid) < 0)
+				seq_printf(s, "%d=_", d->hdr.id);
+			else
+				seq_printf(s, "%d=e", d->hdr.id);
+
+			sep = true;
+		}
+		seq_putc(s, '\n');
+	}
+
+out_unlock:
+	rdtgroup_kn_unlock(of->kn);
+
+	return ret;
+}
+
 /**
  * resctrl_mon_resource_init() - Initialise global monitoring structures.
  *
@@ -1514,6 +1562,7 @@ int resctrl_mon_resource_init(void)
 		resctrl_file_fflags_init("event_filter", RFTYPE_ASSIGN_CONFIG);
 		resctrl_file_fflags_init("mbm_assign_on_mkdir", RFTYPE_MON_INFO |
 					 RFTYPE_RES_CACHE);
+		resctrl_file_fflags_init("mbm_L3_assignments", RFTYPE_MON_BASE);
 	}
 
 	return 0;
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index 48f98146c099..519aa6acef5b 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -1937,6 +1937,12 @@ static struct rftype res_common_files[] = {
 		.seq_show	= event_filter_show,
 		.write		= event_filter_write,
 	},
+	{
+		.name		= "mbm_L3_assignments",
+		.mode		= 0444,
+		.kf_ops		= &rdtgroup_kf_single_ops,
+		.seq_show	= mbm_L3_assignments_show,
+	},
 	{
 		.name		= "mbm_assign_mode",
 		.mode		= 0444,

---

## [30] Babu Moger — 2025-09-05
*Subject: [PATCH v18 29/33] fs/resctrl: Introduce the interface to modify assignments in a group*

Enable the mbm_l3_assignments resctrl file to be used to modify counter
assignments of CTRL_MON and MON groups when the "mbm_event" counter
assignment mode is enabled.

Process the assignment modifications in the following format:
<Event>:<Domain id>=<Assignment state>;<Domain id>=<Assignment state>

Event: A valid MBM event in the
       /sys/fs/resctrl/info/L3_MON/event_configs directory.

Domain ID: A valid domain ID. When writing, '*' applies the changes
	   to all domains.

Assignment states:

    _ : Unassign a counter.

    e : Assign a counter exclusively.

Examples:

$ cd /sys/fs/resctrl
$ cat /sys/fs/resctrl/mbm_L3_assignments
  mbm_total_bytes:0=e;1=e
  mbm_local_bytes:0=e;1=e

To unassign the counter associated with the mbm_total_bytes event on
domain 0:

$ echo "mbm_total_bytes:0=_" > mbm_L3_assignments
$ cat /sys/fs/resctrl/mbm_L3_assignments
  mbm_total_bytes:0=_;1=e
  mbm_local_bytes:0=e;1=e

To unassign the counter associated with the mbm_total_bytes event on
all the domains:

$ echo "mbm_total_bytes:*=_" > mbm_L3_assignments
$ cat /sys/fs/resctrl/mbm_L3_assignments
  mbm_total_bytes:0=_;1=_
  mbm_local_bytes:0=e;1=e

Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: Added Reviewed-by tag.

v17: Moved mbm_L3_assignments_write() and all dependencies to fs/resctrl/monitor.c.
     Fixed extra space.
     Re-organized the user doc.

v16: Updated the changelog for minor corrections.
     Updated resctrl.rst few corrections and consistancy.
     Fixed few references of counter_configs to > event_configs.
     Renamed resctrl_process_assign() to resctrl_parse_mbm_assignment().
     Moved resctrl_parse_mbm_assignment() and rdtgroup_modify_assign_state() to monitor.c.

v15: Updated the changelog little bit.
     Fixed the spacing in event_filter display.
     Removed the enum ASSIGN_NONE etc. Not required anymore.
     Moved mbm_get_mon_event_by_name() to fs/resctrl/monitor.c
     Used the new macro for_each_mon_event().
     Renamed resctrl_get_assign_state() -> rdtgroup_modify_assign_state().
     Quite a few changes in resctrl_process_assign().
     Removed the found and domain variables.
     Called rdtgroup_modify_assign_state() directly where applicable.
     Removed couple of goto statements.

v14: Fixed the problem reported by Peter.
     Updated the changelog.
     Updated the user doc resctrl.rst.
     Added example section on how to use resctrl with mbm_assign_mode.

v13: Few changes in mbm_L3_assignments_write() after moving the event config to evt_list.
     Resolved conflicts caused by the recent FS/ARCH code restructure.

v12: New patch:
     Assignment interface moved inside the group based the discussion
     https://lore.kernel.org/lkml/CALPaoCiii0vXOF06mfV=kVLBzhfNo0SFqt4kQGwGSGVUqvr2Dg@mail.gmail.com/#t
---
 Documentation/filesystems/resctrl.rst | 151 +++++++++++++++++++++++++-
 fs/resctrl/internal.h                 |   3 +
 fs/resctrl/monitor.c                  | 139 ++++++++++++++++++++++++
 fs/resctrl/rdtgroup.c                 |   3 +-
 4 files changed, 294 insertions(+), 2 deletions(-)

diff --git a/Documentation/filesystems/resctrl.rst b/Documentation/filesystems/resctrl.rst
index a2b7240b0818..f60f6a96cb6b 100644
--- a/Documentation/filesystems/resctrl.rst
+++ b/Documentation/filesystems/resctrl.rst
@@ -522,7 +522,8 @@ When monitoring is enabled all MON groups may also contain:
 	Event: A valid MBM event in the
 	       /sys/fs/resctrl/info/L3_MON/event_configs directory.
 
-	Domain ID: A valid domain ID.
+	Domain ID: A valid domain ID. When writing, '*' applies the changes
+		   to all the domains.
 
 	Assignment states:
 
@@ -540,6 +541,35 @@ When monitoring is enabled all MON groups may also contain:
 	   mbm_total_bytes:0=e;1=e
 	   mbm_local_bytes:0=e;1=e
 
+	Assignments can be modified by writing to the interface.
+
+	Examples:
+
+	To unassign the counter associated with the mbm_total_bytes event on domain 0:
+	::
+
+	 # echo "mbm_total_bytes:0=_" > /sys/fs/resctrl/mbm_L3_assignments
+	 # cat /sys/fs/resctrl/mbm_L3_assignments
+	   mbm_total_bytes:0=_;1=e
+	   mbm_local_bytes:0=e;1=e
+
+	To unassign the counter associated with the mbm_total_bytes event on all the domains:
+	::
+
+	 # echo "mbm_total_bytes:*=_" > /sys/fs/resctrl/mbm_L3_assignments
+	 # cat /sys/fs/resctrl/mbm_L3_assignments
+	   mbm_total_bytes:0=_;1=_
+	   mbm_local_bytes:0=e;1=e
+
+	To assign a counter associated with the mbm_total_bytes event on all domains in
+	exclusive mode:
+	::
+
+	 # echo "mbm_total_bytes:*=e" > /sys/fs/resctrl/mbm_L3_assignments
+	 # cat /sys/fs/resctrl/mbm_L3_assignments
+	   mbm_total_bytes:0=e;1=e
+	   mbm_local_bytes:0=e;1=e
+
 When the "mba_MBps" mount option is used all CTRL_MON groups will also contain:
 
 "mba_MBps_event":
@@ -1585,6 +1615,125 @@ View the llc occupancy snapshot::
   # cat /sys/fs/resctrl/p1/mon_data/mon_L3_00/llc_occupancy
   11234000
 
+
+Examples on working with mbm_assign_mode
+========================================
+
+a. Check if MBM counter assignment mode is supported.
+::
+
+  # mount -t resctrl resctrl /sys/fs/resctrl/
+
+  # cat /sys/fs/resctrl/info/L3_MON/mbm_assign_mode
+  [mbm_event]
+  default
+
+The "mbm_event" mode is detected and enabled.
+
+b. Check how many assignable counters are supported.
+::
+
+  # cat /sys/fs/resctrl/info/L3_MON/num_mbm_cntrs
+  0=32;1=32
+
+c. Check how many assignable counters are available for assignment in each domain.
+::
+
+  # cat /sys/fs/resctrl/info/L3_MON/available_mbm_cntrs
+  0=30;1=30
+
+d. To list the default group's assign states.
+::
+
+  # cat /sys/fs/resctrl/mbm_L3_assignments
+  mbm_total_bytes:0=e;1=e
+  mbm_local_bytes:0=e;1=e
+
+e.  To unassign the counter associated with the mbm_total_bytes event on domain 0.
+::
+
+  # echo "mbm_total_bytes:0=_" > /sys/fs/resctrl/mbm_L3_assignments
+  # cat /sys/fs/resctrl/mbm_L3_assignments
+  mbm_total_bytes:0=_;1=e
+  mbm_local_bytes:0=e;1=e
+
+f. To unassign the counter associated with the mbm_total_bytes event on all domains.
+::
+
+  # echo "mbm_total_bytes:*=_" > /sys/fs/resctrl/mbm_L3_assignments
+  # cat /sys/fs/resctrl/mbm_L3_assignment
+  mbm_total_bytes:0=_;1=_
+  mbm_local_bytes:0=e;1=e
+
+g. To assign a counter associated with the mbm_total_bytes event on all domains in
+exclusive mode.
+::
+
+  # echo "mbm_total_bytes:*=e" > /sys/fs/resctrl/mbm_L3_assignments
+  # cat /sys/fs/resctrl/mbm_L3_assignments
+  mbm_total_bytes:0=e;1=e
+  mbm_local_bytes:0=e;1=e
+
+h. Read the events mbm_total_bytes and mbm_local_bytes of the default group. There is
+no change in reading the events with the assignment.
+::
+
+  # cat /sys/fs/resctrl/mon_data/mon_L3_00/mbm_total_bytes
+  779247936
+  # cat /sys/fs/resctrl/mon_data/mon_L3_01/mbm_total_bytes
+  562324232
+  # cat /sys/fs/resctrl/mon_data/mon_L3_00/mbm_local_bytes
+  212122123
+  # cat /sys/fs/resctrl/mon_data/mon_L3_01/mbm_local_bytes
+  121212144
+
+i. Check the event configurations.
+::
+
+  # cat /sys/fs/resctrl/info/L3_MON/event_configs/mbm_total_bytes/event_filter
+  local_reads,remote_reads,local_non_temporal_writes,remote_non_temporal_writes,
+  local_reads_slow_memory,remote_reads_slow_memory,dirty_victim_writes_all
+
+  # cat /sys/fs/resctrl/info/L3_MON/event_configs/mbm_local_bytes/event_filter
+  local_reads,local_non_temporal_writes,local_reads_slow_memory
+
+j. Change the event configuration for mbm_local_bytes.
+::
+
+  # echo "local_reads, local_non_temporal_writes, local_reads_slow_memory, remote_reads" >
+  /sys/fs/resctrl/info/L3_MON/event_configs/mbm_local_bytes/event_filter
+
+  # cat /sys/fs/resctrl/info/L3_MON/event_configs/mbm_local_bytes/event_filter
+  local_reads,local_non_temporal_writes,local_reads_slow_memory,remote_reads
+
+k. Now read the local events again. The first read may come back with "Unavailable"
+status. The subsequent read of mbm_local_bytes will display the current value.
+::
+
+  # cat /sys/fs/resctrl/mon_data/mon_L3_00/mbm_local_bytes
+  Unavailable
+  # cat /sys/fs/resctrl/mon_data/mon_L3_00/mbm_local_bytes
+  2252323
+  # cat /sys/fs/resctrl/mon_data/mon_L3_01/mbm_local_bytes
+  Unavailable
+  # cat /sys/fs/resctrl/mon_data/mon_L3_01/mbm_local_bytes
+  1566565
+
+l. Users have the option to go back to 'default' mbm_assign_mode if required. This can be
+done using the following command. Note that switching the mbm_assign_mode may reset all
+the MBM counters (and thus all MBM events) of all the resctrl groups.
+::
+
+  # echo "default" > /sys/fs/resctrl/info/L3_MON/mbm_assign_mode
+  # cat /sys/fs/resctrl/info/L3_MON/mbm_assign_mode
+  mbm_event
+  [default]
+
+m. Unmount the resctrl filesystem.
+::
+
+  # umount /sys/fs/resctrl/
+
 Intel RDT Errata
 ================
 
diff --git a/fs/resctrl/internal.h b/fs/resctrl/internal.h
index 88079ca0d57a..264f04c7dfba 100644
--- a/fs/resctrl/internal.h
+++ b/fs/resctrl/internal.h
@@ -418,6 +418,9 @@ ssize_t resctrl_mbm_assign_on_mkdir_write(struct kernfs_open_file *of, char *buf
 
 int mbm_L3_assignments_show(struct kernfs_open_file *of, struct seq_file *s, void *v);
 
+ssize_t mbm_L3_assignments_write(struct kernfs_open_file *of, char *buf, size_t nbytes,
+				 loff_t off);
+
 #ifdef CONFIG_RESCTRL_FS_PSEUDO_LOCK
 int rdtgroup_locksetup_enter(struct rdtgroup *rdtgrp);
 
diff --git a/fs/resctrl/monitor.c b/fs/resctrl/monitor.c
index e8c3b3a7987b..d49170247b75 100644
--- a/fs/resctrl/monitor.c
+++ b/fs/resctrl/monitor.c
@@ -1504,6 +1504,145 @@ int mbm_L3_assignments_show(struct kernfs_open_file *of, struct seq_file *s, voi
 	return ret;
 }
 
+/*
+ * mbm_get_mon_event_by_name() - Return the mon_evt entry for the matching
+ * event name.
+ */
+static struct mon_evt *mbm_get_mon_event_by_name(struct rdt_resource *r, char *name)
+{
+	struct mon_evt *mevt;
+
+	for_each_mon_event(mevt) {
+		if (mevt->rid == r->rid && mevt->enabled &&
+		    resctrl_is_mbm_event(mevt->evtid) &&
+		    !strcmp(mevt->name, name))
+			return mevt;
+	}
+
+	return NULL;
+}
+
+static int rdtgroup_modify_assign_state(char *assign, struct rdt_mon_domain *d,
+					struct rdtgroup *rdtgrp, struct mon_evt *mevt)
+{
+	int ret = 0;
+
+	if (!assign || strlen(assign) != 1)
+		return -EINVAL;
+
+	switch (*assign) {
+	case 'e':
+		ret = rdtgroup_assign_cntr_event(d, rdtgrp, mevt);
+		break;
+	case '_':
+		rdtgroup_unassign_cntr_event(d, rdtgrp, mevt);
+		break;
+	default:
+		ret = -EINVAL;
+		break;
+	}
+
+	return ret;
+}
+
+static int resctrl_parse_mbm_assignment(struct rdt_resource *r, struct rdtgroup *rdtgrp,
+					char *event, char *tok)
+{
+	struct rdt_mon_domain *d;
+	unsigned long dom_id = 0;
+	char *dom_str, *id_str;
+	struct mon_evt *mevt;
+	int ret;
+
+	mevt = mbm_get_mon_event_by_name(r, event);
+	if (!mevt) {
+		rdt_last_cmd_printf("Invalid event %s\n", event);
+		return -ENOENT;
+	}
+
+next:
+	if (!tok || tok[0] == '\0')
+		return 0;
+
+	/* Start processing the strings for each domain */
+	dom_str = strim(strsep(&tok, ";"));
+
+	id_str = strsep(&dom_str, "=");
+
+	/* Check for domain id '*' which means all domains */
+	if (id_str && *id_str == '*') {
+		ret = rdtgroup_modify_assign_state(dom_str, NULL, rdtgrp, mevt);
+		if (ret)
+			rdt_last_cmd_printf("Assign operation '%s:*=%s' failed\n",
+					    event, dom_str);
+		return ret;
+	} else if (!id_str || kstrtoul(id_str, 10, &dom_id)) {
+		rdt_last_cmd_puts("Missing domain id\n");
+		return -EINVAL;
+	}
+
+	/* Verify if the dom_id is valid */
+	list_for_each_entry(d, &r->mon_domains, hdr.list) {
+		if (d->hdr.id == dom_id) {
+			ret = rdtgroup_modify_assign_state(dom_str, d, rdtgrp, mevt);
+			if (ret) {
+				rdt_last_cmd_printf("Assign operation '%s:%ld=%s' failed\n",
+						    event, dom_id, dom_str);
+				return ret;
+			}
+			goto next;
+		}
+	}
+
+	rdt_last_cmd_printf("Invalid domain id %ld\n", dom_id);
+	return -EINVAL;
+}
+
+ssize_t mbm_L3_assignments_write(struct kernfs_open_file *of, char *buf,
+				 size_t nbytes, loff_t off)
+{
+	struct rdt_resource *r = resctrl_arch_get_resource(RDT_RESOURCE_L3);
+	struct rdtgroup *rdtgrp;
+	char *token, *event;
+	int ret = 0;
+
+	/* Valid input requires a trailing newline */
+	if (nbytes == 0 || buf[nbytes - 1] != '\n')
+		return -EINVAL;
+
+	buf[nbytes - 1] = '\0';
+
+	rdtgrp = rdtgroup_kn_lock_live(of->kn);
+	if (!rdtgrp) {
+		rdtgroup_kn_unlock(of->kn);
+		return -ENOENT;
+	}
+	rdt_last_cmd_clear();
+
+	if (!resctrl_arch_mbm_cntr_assign_enabled(r)) {
+		rdt_last_cmd_puts("mbm_event mode is not enabled\n");
+		rdtgroup_kn_unlock(of->kn);
+		return -EINVAL;
+	}
+
+	while ((token = strsep(&buf, "\n")) != NULL) {
+		/*
+		 * The write command follows the following format:
+		 * “<Event>:<Domain ID>=<Assignment state>”
+		 * Extract the event name first.
+		 */
+		event = strsep(&token, ":");
+
+		ret = resctrl_parse_mbm_assignment(r, rdtgrp, event, token);
+		if (ret)
+			break;
+	}
+
+	rdtgroup_kn_unlock(of->kn);
+
+	return ret ?: nbytes;
+}
+
 /**
  * resctrl_mon_resource_init() - Initialise global monitoring structures.
  *
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index 519aa6acef5b..bd4a115ffea1 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -1939,9 +1939,10 @@ static struct rftype res_common_files[] = {
 	},
 	{
 		.name		= "mbm_L3_assignments",
-		.mode		= 0444,
+		.mode		= 0644,
 		.kf_ops		= &rdtgroup_kf_single_ops,
 		.seq_show	= mbm_L3_assignments_show,
+		.write		= mbm_L3_assignments_write,
 	},
 	{
 		.name		= "mbm_assign_mode",

---

## [31] Babu Moger — 2025-09-05
*Subject: [PATCH v18 30/33] fs/resctrl: Disable BMEC event configuration when mbm_event mode is enabled*

The BMEC (Bandwidth Monitoring Event Configuration) feature enables
per-domain event configuration. With BMEC the MBM events are configured
using the mbm_total_bytes_config or mbm_local_bytes_config files in
/sys/fs/resctrl/info/L3_MON/ and the per-domain event configuration affects
all monitor resource groups.

The mbm_event counter assignment mode enables counters to be assigned to
RMID (i.e a monitor resource group), event pairs, with potentially unique
event configurations associated with every counter.

There may be systems that support both BMEC and mbm_event counter
assignment mode, but resctrl supporting both concurrently will present a
conflicting interface to the user with both per-domain and per RMID, event
configurations active at the same time.

The mbm_event counter assignment provides most flexibility to user space
and aligns with Arm's counter support. On systems that support both,
disable BMEC event configuration when mbm_event mode is enabled by hiding
the mbm_total_bytes_config or mbm_local_bytes_config files when mbm_event
mode is enabled. Ensure mon_features always displays accurate information
about monitor features.

Suggested-by: Reinette Chatre <reinette.chatre@intel.com>
Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: Added Reviewed-by tag.

v17: Fixed the extra reference release in resctrl_bmec_files_show().

v16: Added new comment in resctrl_bmec_files_show() about kernfs_find_and_get failure.
     Added the parameter to resctrl_bmec_files_show() to pass the kernfs_node.

v15: Updated the changelog.
     Moved resctrl_bmec_files_show() inside rdtgroup_mkdir_info_resdir().
     Removed the unnecessary kernfs_get() call.

v14: Updated the changelog for change in mbm_assign_modes.
     Added check in rdt_mon_features_show to hide bmec related feature.

v13: New patch to hide BMEC related files.
---
 fs/resctrl/rdtgroup.c | 47 ++++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 46 insertions(+), 1 deletion(-)

diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index bd4a115ffea1..0c404a159d45 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -1150,7 +1150,8 @@ static int rdt_mon_features_show(struct kernfs_open_file *of,
 		if (mevt->rid != r->rid || !mevt->enabled)
 			continue;
 		seq_printf(seq, "%s\n", mevt->name);
-		if (mevt->configurable)
+		if (mevt->configurable &&
+		    !resctrl_arch_mbm_cntr_assign_enabled(r))
 			seq_printf(seq, "%s_config\n", mevt->name);
 	}
 
@@ -1799,6 +1800,44 @@ static ssize_t mbm_local_bytes_config_write(struct kernfs_open_file *of,
 	return ret ?: nbytes;
 }
 
+/*
+ * resctrl_bmec_files_show() — Controls the visibility of BMEC-related resctrl
+ * files. When @show is true, the files are displayed; when false, the files
+ * are hidden.
+ * Don't treat kernfs_find_and_get failure as an error, since this function may
+ * be called regardless of whether BMEC is supported or the event is enabled.
+ */
+static void resctrl_bmec_files_show(struct rdt_resource *r, struct kernfs_node *l3_mon_kn,
+				    bool show)
+{
+	struct kernfs_node *kn_config, *mon_kn = NULL;
+	char name[32];
+
+	if (!l3_mon_kn) {
+		sprintf(name, "%s_MON", r->name);
+		mon_kn = kernfs_find_and_get(kn_info, name);
+		if (!mon_kn)
+			return;
+		l3_mon_kn = mon_kn;
+	}
+
+	kn_config = kernfs_find_and_get(l3_mon_kn, "mbm_total_bytes_config");
+	if (kn_config) {
+		kernfs_show(kn_config, show);
+		kernfs_put(kn_config);
+	}
+
+	kn_config = kernfs_find_and_get(l3_mon_kn, "mbm_local_bytes_config");
+	if (kn_config) {
+		kernfs_show(kn_config, show);
+		kernfs_put(kn_config);
+	}
+
+	/* Release the reference only if it was acquired */
+	if (mon_kn)
+		kernfs_put(mon_kn);
+}
+
 /* rdtgroup information files for one cache resource. */
 static struct rftype res_common_files[] = {
 	{
@@ -2267,6 +2306,12 @@ static int rdtgroup_mkdir_info_resdir(void *priv, char *name,
 			ret = resctrl_mkdir_event_configs(r, kn_subdir);
 			if (ret)
 				return ret;
+			/*
+			 * Hide BMEC related files if mbm_event mode
+			 * is enabled.
+			 */
+			if (resctrl_arch_mbm_cntr_assign_enabled(r))
+				resctrl_bmec_files_show(r, kn_subdir, false);
 		}
 	}

---

## [32] Babu Moger — 2025-09-05
*Subject: [PATCH v18 31/33] fs/resctrl: Introduce the interface to switch between monitor modes*

Resctrl subsystem can support two monitoring modes, "mbm_event" or
"default". In mbm_event mode, monitoring event can only accumulate data
while it is backed by a hardware counter. In "default" mode, resctrl
assumes there is a hardware counter for each event within every CTRL_MON
and MON group.

Introduce mbm_assign_mode resctrl file to switch between mbm_event and
default modes.

Example:
To list the MBM monitor modes supported:
$ cat /sys/fs/resctrl/info/L3_MON/mbm_assign_mode
[mbm_event]
default

To enable the "mbm_event" counter assignment mode:
$ echo "mbm_event" > /sys/fs/resctrl/info/L3_MON/mbm_assign_mode

To enable the "default" monitoring mode:
$ echo "default" > /sys/fs/resctrl/info/L3_MON/mbm_assign_mode

Reset MBM event counters automatically as part of changing the mode.
Clear both architectural and non-architectural event states to prevent
overflow conditions during the next event read. Clear assignable counter
configuration on all the domains. Also, enable auto assignment when
switching to "mbm_event" mode.

Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: Changelog update for imperative mode.
     Added Reviewed-by tag.

v17: Moved resctrl_mbm_assign_mode_write() to fs/resctrl/monitor.c
     Fixed the event configuration initialization while considering hw support.
     Enable auto assignment when switching to "mbm_event" mode.

v16: Minor changelog update.
     Minor update in resctrl.rst.
     Updated resctrl_bmec_files_show() to pass NULL for kn_fs_node.

v15: Minor changelog update.
     Minir user do resctrl.rst update.
     Fixed stray hunks.

v14: Updated the changelog to reflect the change in monitor mode naming.
     Added the call resctrl_bmec_files_show() to enable/disable files
     related to BMEC.
     Added resctrl_set_mon_evt_cfg() to reset event configuration values
     when mode is changes.

v13: Resolved the conflicts due to FS/ARCH restructure.
     Introduced the new resctrl_init_evt_configuration() to initialize
     the event modes and configuration values.
     Added the call to resctrl_bmec_files_show() hide/show BMEC related
     files.

v12: Fixed the documentation for a consistency.
     Introduced mbm_cntr_free_all() and resctrl_reset_rmid_all() to clear
     counters and non-architectural states when monitor mode is changed.
     https://lore.kernel.org/lkml/b60b4f72-6245-46db-a126-428fb13b6310@intel.com/

v11: Changed the name of the function rdtgroup_mbm_assign_mode_write() to
     resctrl_mbm_assign_mode_write().
     Rewrote the commit message with context.
     Added few more details in resctrl.rst about mbm_cntr_assign mode.
     Re-arranged the text in resctrl.rst file.

v10: The call mbm_cntr_reset() has been moved to earlier patch.
     Minor documentation update.

v9: Fixed extra spaces in user documentation.
    Fixed problem changing the mode to mbm_cntr_assign mode when it is
    not supported. Added extra checks to detect if systems supports it.
    Used the rdtgroup_cntr_id_init to initialize cntr_id.

v8: Reset the internal counters after mbm_cntr_assign mode is changed.
    Renamed rdtgroup_mbm_cntr_reset() to mbm_cntr_reset()
    Updated the documentation to make text generic.

v7: Changed the interface name to mbm_assign_mode.
    Removed the references of ABMC.
    Added the changes to reset global and domain bitmaps.
    Added the changes to reset rmid.

v6: Changed the mode name to mbm_cntr_assign.
    Moved all the FS related code here.
    Added changes to reset mbm_cntr_map and resctrl group counters.

v5: Change log and mode description text correction.

v4: Minor commit text changes. Keep the default to ABMC when supported.
    Fixed comments to reflect changed interface "mbm_mode".

v3: New patch to address the review comments from upstream.
---
 Documentation/filesystems/resctrl.rst |  22 +++++-
 fs/resctrl/internal.h                 |   6 ++
 fs/resctrl/monitor.c                  | 100 ++++++++++++++++++++++++++
 fs/resctrl/rdtgroup.c                 |   7 +-
 4 files changed, 131 insertions(+), 4 deletions(-)

diff --git a/Documentation/filesystems/resctrl.rst b/Documentation/filesystems/resctrl.rst
index f60f6a96cb6b..006d23af66e1 100644
--- a/Documentation/filesystems/resctrl.rst
+++ b/Documentation/filesystems/resctrl.rst
@@ -259,7 +259,8 @@ with the following files:
 
 "mbm_assign_mode":
 	The supported counter assignment modes. The enclosed brackets indicate which mode
-	is enabled.
+	is enabled. The MBM events associated with counters may reset when "mbm_assign_mode"
+	is changed.
 	::
 
 	  # cat /sys/fs/resctrl/info/L3_MON/mbm_assign_mode
@@ -279,6 +280,15 @@ with the following files:
 	of counters available is described in the "num_mbm_cntrs" file. Changing the
 	mode may cause all counters on the resource to reset.
 
+	Moving to mbm_event counter assignment mode requires users to assign the counters
+	to the events. Otherwise, the MBM event counters will return 'Unassigned' when read.
+
+	The mode is beneficial for AMD platforms that support more CTRL_MON
+	and MON groups than available hardware counters. By default, this
+	feature is enabled on AMD platforms with the ABMC (Assignable Bandwidth
+	Monitoring Counters) capability, ensuring counters remain assigned even
+	when the corresponding RMID is not actively used by any processor.
+
 	"default":
 
 	In default mode, resctrl assumes there is a hardware counter for each
@@ -288,6 +298,16 @@ with the following files:
 	result in misleading values or display "Unavailable" if no counter is assigned
 	to the event.
 
+	* To enable "mbm_event" counter assignment mode:
+	  ::
+
+	    # echo "mbm_event" > /sys/fs/resctrl/info/L3_MON/mbm_assign_mode
+
+	* To enable "default" monitoring mode:
+	  ::
+
+	    # echo "default" > /sys/fs/resctrl/info/L3_MON/mbm_assign_mode
+
 "num_mbm_cntrs":
 	The maximum number of counters (total of available and assigned counters) in
 	each domain when the system supports mbm_event mode.
diff --git a/fs/resctrl/internal.h b/fs/resctrl/internal.h
index 264f04c7dfba..6938734b14a4 100644
--- a/fs/resctrl/internal.h
+++ b/fs/resctrl/internal.h
@@ -396,6 +396,12 @@ void *rdt_kn_parent_priv(struct kernfs_node *kn);
 
 int resctrl_mbm_assign_mode_show(struct kernfs_open_file *of, struct seq_file *s, void *v);
 
+ssize_t resctrl_mbm_assign_mode_write(struct kernfs_open_file *of, char *buf,
+				      size_t nbytes, loff_t off);
+
+void resctrl_bmec_files_show(struct rdt_resource *r, struct kernfs_node *l3_mon_kn,
+			     bool show);
+
 int resctrl_num_mbm_cntrs_show(struct kernfs_open_file *of, struct seq_file *s, void *v);
 
 int resctrl_available_mbm_cntrs_show(struct kernfs_open_file *of, struct seq_file *s,
diff --git a/fs/resctrl/monitor.c b/fs/resctrl/monitor.c
index d49170247b75..4cf78a9a8807 100644
--- a/fs/resctrl/monitor.c
+++ b/fs/resctrl/monitor.c
@@ -1080,6 +1080,33 @@ ssize_t resctrl_mbm_assign_on_mkdir_write(struct kernfs_open_file *of, char *buf
 	return ret ?: nbytes;
 }
 
+/*
+ * mbm_cntr_free_all() - Clear all the counter ID configuration details in the
+ *			 domain @d. Called when mbm_assign_mode is changed.
+ */
+static void mbm_cntr_free_all(struct rdt_resource *r, struct rdt_mon_domain *d)
+{
+	memset(d->cntr_cfg, 0, sizeof(*d->cntr_cfg) * r->mon.num_mbm_cntrs);
+}
+
+/*
+ * resctrl_reset_rmid_all() - Reset all non-architecture states for all the
+ *			      supported RMIDs.
+ */
+static void resctrl_reset_rmid_all(struct rdt_resource *r, struct rdt_mon_domain *d)
+{
+	u32 idx_limit = resctrl_arch_system_num_rmid_idx();
+	enum resctrl_event_id evt;
+	int idx;
+
+	for_each_mbm_event_id(evt) {
+		if (!resctrl_is_mon_event_enabled(evt))
+			continue;
+		idx = MBM_STATE_IDX(evt);
+		memset(d->mbm_states[idx], 0, sizeof(*d->mbm_states[0]) * idx_limit);
+	}
+}
+
 /*
  * rdtgroup_assign_cntr() - Assign/unassign the counter ID for the event, RMID
  * pair in the domain.
@@ -1390,6 +1417,79 @@ int resctrl_mbm_assign_mode_show(struct kernfs_open_file *of,
 	return 0;
 }
 
+ssize_t resctrl_mbm_assign_mode_write(struct kernfs_open_file *of, char *buf,
+				      size_t nbytes, loff_t off)
+{
+	struct rdt_resource *r = rdt_kn_parent_priv(of->kn);
+	struct rdt_mon_domain *d;
+	int ret = 0;
+	bool enable;
+
+	/* Valid input requires a trailing newline */
+	if (nbytes == 0 || buf[nbytes - 1] != '\n')
+		return -EINVAL;
+
+	buf[nbytes - 1] = '\0';
+
+	cpus_read_lock();
+	mutex_lock(&rdtgroup_mutex);
+
+	rdt_last_cmd_clear();
+
+	if (!strcmp(buf, "default")) {
+		enable = 0;
+	} else if (!strcmp(buf, "mbm_event")) {
+		if (r->mon.mbm_cntr_assignable) {
+			enable = 1;
+		} else {
+			ret = -EINVAL;
+			rdt_last_cmd_puts("mbm_event mode is not supported\n");
+			goto out_unlock;
+		}
+	} else {
+		ret = -EINVAL;
+		rdt_last_cmd_puts("Unsupported assign mode\n");
+		goto out_unlock;
+	}
+
+	if (enable != resctrl_arch_mbm_cntr_assign_enabled(r)) {
+		ret = resctrl_arch_mbm_cntr_assign_set(r, enable);
+		if (ret)
+			goto out_unlock;
+
+		/* Update the visibility of BMEC related files */
+		resctrl_bmec_files_show(r, NULL, !enable);
+
+		/*
+		 * Initialize the default memory transaction values for
+		 * total and local events.
+		 */
+		if (resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID))
+			mon_event_all[QOS_L3_MBM_TOTAL_EVENT_ID].evt_cfg = r->mon.mbm_cfg_mask;
+		if (resctrl_is_mon_event_enabled(QOS_L3_MBM_LOCAL_EVENT_ID))
+			mon_event_all[QOS_L3_MBM_LOCAL_EVENT_ID].evt_cfg = r->mon.mbm_cfg_mask &
+									   (READS_TO_LOCAL_MEM |
+									    READS_TO_LOCAL_S_MEM |
+									    NON_TEMP_WRITE_TO_LOCAL_MEM);
+		/* Enable auto assignment when switching to "mbm_event" mode */
+		if (enable)
+			r->mon.mbm_assign_on_mkdir = true;
+		/*
+		 * Reset all the non-achitectural RMID state and assignable counters.
+		 */
+		list_for_each_entry(d, &r->mon_domains, hdr.list) {
+			mbm_cntr_free_all(r, d);
+			resctrl_reset_rmid_all(r, d);
+		}
+	}
+
+out_unlock:
+	mutex_unlock(&rdtgroup_mutex);
+	cpus_read_unlock();
+
+	return ret ?: nbytes;
+}
+
 int resctrl_num_mbm_cntrs_show(struct kernfs_open_file *of,
 			       struct seq_file *s, void *v)
 {
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index 0c404a159d45..0320360cd7a6 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -1807,8 +1807,8 @@ static ssize_t mbm_local_bytes_config_write(struct kernfs_open_file *of,
  * Don't treat kernfs_find_and_get failure as an error, since this function may
  * be called regardless of whether BMEC is supported or the event is enabled.
  */
-static void resctrl_bmec_files_show(struct rdt_resource *r, struct kernfs_node *l3_mon_kn,
-				    bool show)
+void resctrl_bmec_files_show(struct rdt_resource *r, struct kernfs_node *l3_mon_kn,
+			     bool show)
 {
 	struct kernfs_node *kn_config, *mon_kn = NULL;
 	char name[32];
@@ -1985,9 +1985,10 @@ static struct rftype res_common_files[] = {
 	},
 	{
 		.name		= "mbm_assign_mode",
-		.mode		= 0444,
+		.mode		= 0644,
 		.kf_ops		= &rdtgroup_kf_single_ops,
 		.seq_show	= resctrl_mbm_assign_mode_show,
+		.write		= resctrl_mbm_assign_mode_write,
 		.fflags		= RFTYPE_MON_INFO | RFTYPE_RES_CACHE,
 	},
 	{

---

## [33] Babu Moger — 2025-09-05
*Subject: [PATCH v18 32/33] x86/resctrl: Configure mbm_event mode if supported*

Configure mbm_event mode on AMD platforms. On AMD platforms, it is
recommended to use the mbm_event mode, if supported, to prevent the
hardware from resetting counters between reads. This can result in
misleading values or display "Unavailable" if no counter is assigned
to the event.

Enable mbm_event mode, known as ABMC (Assignable Bandwidth Monitoring
Counters) on AMD, by default if the system supports it.

Update ABMC across all logical processors within the resctrl domain to
ensure proper functionality.

Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: Added Reviewed-by tag.

v17: Updated the changelog to imperative mode.

v16: Fixed a minor conflict in arch/x86/kernel/cpu/resctrl/monitor.c.

v15: Minor comment update.

v14: Updated the changelog to reflect the change in name of the monitor mode
     to mbm_event.

v13 : Added the call resctrl_init_evt_configuration() to setup the event
      configuration during init.
      Resolved conflicts caused by the recent FS/ARCH code restructure.

v12: Moved the resctrl_arch_mbm_cntr_assign_set_one to domain_add_cpu_mon().
     Updated the commit log.

v11: Commit text in imperative tone. Added few more details.
     Moved resctrl_arch_mbm_cntr_assign_set_one() to monitor.c.

v10: Commit text in imperative tone.

v9: Minor code change due to merge. Actual code did not change.

v8: Renamed resctrl_arch_mbm_cntr_assign_configure to
        resctrl_arch_mbm_cntr_assign_set_one.
    Adde r->mon_capable check.
    Commit message update.

v7: Introduced resctrl_arch_mbm_cntr_assign_configure() to configure.
    Moved the default settings to rdt_get_mon_l3_config(). It should be
    done before the hotplug handler is called. It cannot be done at
    rdtgroup_init().

v6: Keeping the default enablement in arch init code for now.
     This may need some discussion.
     Renamed resctrl_arch_configure_abmc to resctrl_arch_mbm_cntr_assign_configure.

v5: New patch to enable ABMC by default.
---
 arch/x86/kernel/cpu/resctrl/core.c     | 7 +++++++
 arch/x86/kernel/cpu/resctrl/internal.h | 1 +
 arch/x86/kernel/cpu/resctrl/monitor.c  | 8 ++++++++
 3 files changed, 16 insertions(+)

diff --git a/arch/x86/kernel/cpu/resctrl/core.c b/arch/x86/kernel/cpu/resctrl/core.c
index 2e68aa02ad3f..06ca5a30140c 100644
--- a/arch/x86/kernel/cpu/resctrl/core.c
+++ b/arch/x86/kernel/cpu/resctrl/core.c
@@ -520,6 +520,9 @@ static void domain_add_cpu_mon(int cpu, struct rdt_resource *r)
 		d = container_of(hdr, struct rdt_mon_domain, hdr);
 
 		cpumask_set_cpu(cpu, &d->hdr.cpu_mask);
+		/* Update the mbm_assign_mode state for the CPU if supported */
+		if (r->mon.mbm_cntr_assignable)
+			resctrl_arch_mbm_cntr_assign_set_one(r);
 		return;
 	}
 
@@ -539,6 +542,10 @@ static void domain_add_cpu_mon(int cpu, struct rdt_resource *r)
 	d->ci_id = ci->id;
 	cpumask_set_cpu(cpu, &d->hdr.cpu_mask);
 
+	/* Update the mbm_assign_mode state for the CPU if supported */
+	if (r->mon.mbm_cntr_assignable)
+		resctrl_arch_mbm_cntr_assign_set_one(r);
+
 	arch_mon_domain_online(r, d);
 
 	if (arch_domain_mbm_alloc(r->mon.num_rmid, hw_dom)) {
diff --git a/arch/x86/kernel/cpu/resctrl/internal.h b/arch/x86/kernel/cpu/resctrl/internal.h
index ae4003d44df4..ee81c2d3f058 100644
--- a/arch/x86/kernel/cpu/resctrl/internal.h
+++ b/arch/x86/kernel/cpu/resctrl/internal.h
@@ -215,5 +215,6 @@ bool rdt_cpu_has(int flag);
 void __init intel_rdt_mbm_apply_quirk(void);
 
 void rdt_domain_reconfigure_cdp(struct rdt_resource *r);
+void resctrl_arch_mbm_cntr_assign_set_one(struct rdt_resource *r);
 
 #endif /* _ASM_X86_RESCTRL_INTERNAL_H */
diff --git a/arch/x86/kernel/cpu/resctrl/monitor.c b/arch/x86/kernel/cpu/resctrl/monitor.c
index 0b3c199e9e01..c8945610d455 100644
--- a/arch/x86/kernel/cpu/resctrl/monitor.c
+++ b/arch/x86/kernel/cpu/resctrl/monitor.c
@@ -456,6 +456,7 @@ int __init rdt_get_mon_l3_config(struct rdt_resource *r)
 		r->mon.mbm_cntr_assignable = true;
 		cpuid_count(0x80000020, 5, &eax, &ebx, &ecx, &edx);
 		r->mon.num_mbm_cntrs = (ebx & GENMASK(15, 0)) + 1;
+		hw_res->mbm_cntr_assign_enabled = true;
 	}
 
 	r->mon_capable = true;
@@ -557,3 +558,10 @@ void resctrl_arch_config_cntr(struct rdt_resource *r, struct rdt_mon_domain *d,
 	if (am)
 		memset(am, 0, sizeof(*am));
 }
+
+void resctrl_arch_mbm_cntr_assign_set_one(struct rdt_resource *r)
+{
+	struct rdt_hw_resource *hw_res = resctrl_to_arch_res(r);
+
+	resctrl_abmc_set_one_amd(&hw_res->mbm_cntr_assign_enabled);
+}

---

## [34] Babu Moger — 2025-09-05
*Subject: [PATCH v18 33/33] MAINTAINERS: resctrl: add myself as reviewer*

I have been contributing to resctrl for sometime now and I would like to
help with code reviews as well.

Signed-off-by: Babu Moger <babu.moger@amd.com>
Acked-by: Reinette Chatre <reinette.chatre@intel.com>
---
v18: No changes.

v17: Added Acked-by tag.

v16: Reinette suggested to add me as a reviewer. I am glad to help as a reviewer.
---
 MAINTAINERS | 1 +
 1 file changed, 1 insertion(+)

diff --git a/MAINTAINERS b/MAINTAINERS
index ec2586487c9f..d27b0fce1146 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -21171,6 +21171,7 @@ M:	Tony Luck <tony.luck@intel.com>
 M:	Reinette Chatre <reinette.chatre@intel.com>
 R:	Dave Martin <Dave.Martin@arm.com>
 R:	James Morse <james.morse@arm.com>
+R:	Babu Moger <babu.moger@amd.com>
 L:	linux-kernel@vger.kernel.org
 S:	Supported
 F:	Documentation/filesystems/resctrl.rst

---

## [35] Reinette Chatre — 2025-09-05
*Subject: Re: [PATCH v18 05/33] x86/cpufeatures: Add support for Assignable
 Bandwidth Monitoring Counters (ABMC)*

Hi Babu,

On 9/5/25 2:34 PM, Babu Moger wrote:
> 
> The ABMC feature details are documented in APM [1] available from [2].

Apologies for not catching this earlier. I double checked to make sure
we get this right and I interpret Documentation/process/maintainer-tip.rst
to say that "Link:" should be the final tag.

Reinette

---

## [36] Reinette Chatre — 2025-09-05
*Subject: Re: [PATCH v18 25/33] fs/resctrl: Provide interface to update the
 event configurations*

Hi Babu,

On 9/5/25 2:34 PM, Babu Moger wrote:
> When "mbm_event" counter assignment mode is enabled, users can modify
> the event configuration by writing to the 'event_filter' resctrl file.

Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>

Reinette

---

## [37] Reinette Chatre — 2025-09-05
*Subject: Re: [PATCH v18 28/33] fs/resctrl: Introduce mbm_L3_assignments to
 list assignments in a group*

Hi Babu,

On 9/5/25 2:34 PM, Babu Moger wrote:
> Introduce the mbm_L3_assignments resctrl file associated with CTRL_MON and
> MON resource groups to display the counter assignment states of the

Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>

Reinette

---

## [38] Reinette Chatre — 2025-09-05
*Subject: Re: [PATCH v18 29/33] fs/resctrl: Introduce the interface to modify
 assignments in a group*

Hi Babu,

Thanks for catching and removing that stray hunk.

Reinette

---

## [39] Moger, Babu — 2025-09-08
*Subject: Re: [PATCH v18 05/33] x86/cpufeatures: Add support for Assignable
 Bandwidth Monitoring Counters (ABMC)*

Hi Reinette,

On 9/5/25 23:49, Reinette Chatre wrote:
> Hi Babu,
> 

That’s fine. It wasn’t very clear to me in maintainer-tip.rst.

I checked a few older commits, and the placement seems mixed—some have it
at the end, but it’s not very consistent. I can update my patches
accordingly and apply the same change across all of them.


 The ABMC feature details are documented in APM [1] available from [2].
 [1] AMD64 Architecture Programmer's Manual Volume 2: System Programming
 Publication # 24593 Revision 3.41 section 19.3.3.3 Assignable Bandwidth
 Monitoring (ABMC).

 Signed-off-by: Babu Moger <babu.moger@amd.com>
 Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
 Link: https://bugzilla.kernel.org/show_bug.cgi?id=206537 # [2]


I’ve been basing the patches on top of:
git.kernel.org/pub/scm/linux/kernel/git/tip/tip.git
with `origin/HEAD -> origin/master`.

Please let me know if this is the correct branch to use to make the merge
process easier.

---

## [40] Borislav Petkov — 2025-09-08
*Subject: Re: [PATCH v18 05/33] x86/cpufeatures: Add support for Assignable
 Bandwidth Monitoring Counters (ABMC)*

On Mon, Sep 08, 2025 at 09:41:22AM -0500, Moger, Babu wrote:
> > Apologies for not catching this earlier. I double checked to make sure
> > we get this right and I interpret Documentation/process/maintainer-tip.rst

You don't need to worry about minor things like that - our scripts fix them up
while applying.

As to Link tags, see this here:

https://lore.kernel.org/r/CAHk-=wh5AyuvEhNY9a57v-vwyr7EkPVRUKMPwj92yF_K0dJHVg@mail.gmail.com

---

## [41] Moger, Babu — 2025-09-08
*Subject: Re: [PATCH v18 05/33] x86/cpufeatures: Add support for Assignable
 Bandwidth Monitoring Counters (ABMC)*

Hi Boris,

On 9/8/25 10:03, Borislav Petkov wrote:
> On Mon, Sep 08, 2025 at 09:41:22AM -0500, Moger, Babu wrote:
>>> Apologies for not catching this earlier. I double checked to make sure

Ok, sure. I don’t need to re-spin unless there are other comments.

> 
> As to Link tags, see this here:

---

## [42] Moger, Babu — 2025-09-08
*Subject: Re: [PATCH v18 29/33] fs/resctrl: Introduce the interface to modify
 assignments in a group*

Hi Reinette,

On 9/5/25 23:50, Reinette Chatre wrote:
> Hi Babu,
> 

Welcome! Thanks for noticing it — funny how it managed to slip past you
earlier. ):

---

## [43] Reinette Chatre — 2025-09-09
*Subject: Re: [PATCH v18 00/33] x86,fs/resctrl: Support AMD Assignable
 Bandwidth Monitoring Counters (ABMC)*

Hi Babu,

On 9/5/25 2:33 PM, Babu Moger wrote:
> 
> This series adds the support for Assignable Bandwidth Monitoring Counters

Heads up that [1] was merged to x86/urgent and conflicts with this series.
[1] is a small patch and fixups to this series should be clear.

When I checked tip/master did not include x86/urgent yet but when it does (and
tip/master thus includes x86/cache and x86/urgent), could you please
merge your series on top of tip/master to ensure all conflicts can be resolved
cleanly and ready to provide conflict resolutions to Boris if needed?

Thank you very much.

Reinette

[1] https://lore.kernel.org/lkml/0819ce534d0cb919f728e940d9412c3bab1a27c7.1757369564.git.reinette.chatre@intel.com/

---

## [44] Borislav Petkov — 2025-09-09
*Subject: Re: [PATCH v18 00/33] x86,fs/resctrl: Support AMD Assignable
 Bandwidth Monitoring Counters (ABMC)*

On Tue, Sep 09, 2025 at 09:03:13AM -0700, Reinette Chatre wrote:
> When I checked tip/master did not include x86/urgent yet but when it does (and
> tip/master thus includes x86/cache and x86/urgent), could you please

Thanks, just give it a test but no rebasing anymore - I'm going through the
set. If there are conflicts, we do enough patch tetris in tip to catch them
and handle them upfront - you guys don't have to worry about it.

Thx.

---

## [45] Reinette Chatre — 2025-09-09
*Subject: Re: [PATCH v18 00/33] x86,fs/resctrl: Support AMD Assignable
 Bandwidth Monitoring Counters (ABMC)*

On 9/9/25 9:19 AM, Borislav Petkov wrote:
> On Tue, Sep 09, 2025 at 09:03:13AM -0700, Reinette Chatre wrote:
>> When I checked tip/master did not include x86/urgent yet but when it does (and

Thank you very much Boris.

Reinette

---

## [46] Luck, Tony — 2025-09-09
*Subject: Re: [PATCH v18 00/33] x86,fs/resctrl: Support AMD Assignable
 Bandwidth Monitoring Counters (ABMC)*

On Tue, Sep 09, 2025 at 09:24:39AM -0700, Reinette Chatre wrote:
> 
> 

Conflicts in Babu's series were trivial. Fractionally more complex in
my AET series (because some of the code touched by Reinette's patch
moved to a whole new function. But still not hard.

Whole set (upstream + Reinette + Babu + Me) pushed here:

git://git.kernel.org/pub/scm/linux/kernel/git/aegl/linux.git reinette-abmc-aet-wip

-Tony

---

## [47] Borislav Petkov — 2025-09-09
*Subject: Re: [PATCH v18 00/33] x86,fs/resctrl: Support AMD Assignable
 Bandwidth Monitoring Counters (ABMC)*

On Tue, Sep 09, 2025 at 10:33:52AM -0700, Luck, Tony wrote:
> Conflicts in Babu's series were trivial.

Right, and considering how tip:x86/cache has only one patch, I might even
fast-forward it to -rc6 which will have Reinette's fix so we should be good.

At least that's the plan - we'll see.

> Fractionally more complex in my AET series (because some of the code touched
> by Reinette's patch moved to a whole new function. But still not hard.

It doesn't hurt to test the different piles.

Thx.

---

## [48] Borislav Petkov — 2025-09-10
*Subject: Re: [PATCH v18 14/33] x86/resctrl: Add data structures and
 definitions for ABMC assignment*

On Fri, Sep 05, 2025 at 04:34:13PM -0500, Babu Moger wrote:
> diff --git a/arch/x86/include/asm/msr-index.h b/arch/x86/include/asm/msr-index.h
> index 18222527b0ee..48230814098d 100644

Some of those MSRs are AMD-specific: why do they have "IA32" in the name and
not "AMD64"?

---

## [49] Moger, Babu — 2025-09-10
*Subject: Re: [PATCH v18 14/33] x86/resctrl: Add data structures and
 definitions for ABMC assignment*

Hi Boris,

On 9/10/25 12:26, Borislav Petkov wrote:
> On Fri, Sep 05, 2025 at 04:34:13PM -0500, Babu Moger wrote:
>> diff --git a/arch/x86/include/asm/msr-index.h b/arch/x86/include/asm/msr-index.h

No particular reason — it was just carried over from older MSRs by copy-paste.

In fact, all five of them are AMD-specific in this case. Let me know the
best way to handle this.

---

## [50] Borislav Petkov — 2025-09-10
*Subject: Re: [PATCH v18 14/33] x86/resctrl: Add data structures and
 definitions for ABMC assignment*

On Wed, Sep 10, 2025 at 02:49:23PM -0500, Moger, Babu wrote:
> No particular reason — it was just carried over from older MSRs by copy-paste.
> 

You could s/IA32/AMD/ them later, when the dust settles.

"AMD64" would mean they're architectural which doesn't look like it ... yet.

---

## [51] Moger, Babu — 2025-09-10
*Subject: Re: [PATCH v18 14/33] x86/resctrl: Add data structures and
 definitions for ABMC assignment*

On 9/10/25 14:59, Borislav Petkov wrote:
> On Wed, Sep 10, 2025 at 02:49:23PM -0500, Moger, Babu wrote:
>> No particular reason — it was just carried over from older MSRs by copy-paste.

ok. sounds good.

> 
> "AMD64" would mean they're architectural which doesn't look like it ... yet.

Yea. That's correct.

---

## [52] Borislav Petkov — 2025-09-11
*Subject: Re: [PATCH v18 26/33] fs/resctrl: Introduce mbm_assign_on_mkdir to
 enable assignments on mkdir*

On Fri, Sep 05, 2025 at 04:34:25PM -0500, Babu Moger wrote:
> The "mbm_event" counter assignment mode allows users to assign a hardware
> counter to an RMID, event pair and monitor the bandwidth as long as it is

This is just a note for the future - you don't have to go change things now:
reading those commit messages back-to-back, there's a lot of boilerplate code
which repeats with each commit message and there's a lot of text talking what
the patch does.

Please tone this down in the future - it is really annoying and doesn't bring
a whole lot by repeating things or explaining the obvious. Just concentrate on
explaining why the patch exists and mention any non-obvious things.

Everything else people can find by searching the net.

Thx.

---

## [53] Reinette Chatre — 2025-09-11
*Subject: Re: [PATCH v18 26/33] fs/resctrl: Introduce mbm_assign_on_mkdir to
 enable assignments on mkdir*

Hi Boris,

On 9/11/25 8:08 AM, Borislav Petkov wrote:
> 
> Please tone this down in the future - it is really annoying and doesn't bring

Thank you very much for this guidance. You raise two issues: repeating things and too
much text that explains the obvious.

About repeating things: As I see it the annoying repeating results from desire to
follow the "context-problem-solution" changelog script while also ensuring each
patch stands on its own. With these new features many patches share the same context
and then copy&paste results. I see how this can be annoying when going through
the series and I can also see how this is a lazy approach since the context is
not tailored to each patch. Will work on this.

About too much text that explains the obvious: I hear you and will add these criteria
to how changelogs are measured. I do find the criteria a bit subjective though and expect
that I will not get this right immediately and appreciate and welcome your feedback until
I do.

Thank you very much.

Reinette

---

## [54] Moger, Babu — 2025-09-11
*Subject: Re: [PATCH v18 26/33] fs/resctrl: Introduce mbm_assign_on_mkdir to
 enable assignments on mkdir*

Hi Boris,

On 9/11/25 10:08, Borislav Petkov wrote:
> On Fri, Sep 05, 2025 at 04:34:25PM -0500, Babu Moger wrote:
>> The "mbm_event" counter assignment mode allows users to assign a hardware

Agreed. Thanks for the note.

---

## [55] Borislav Petkov — 2025-09-11
*Subject: Re: [PATCH v18 26/33] fs/resctrl: Introduce mbm_assign_on_mkdir to
 enable assignments on mkdir*

On Thu, Sep 11, 2025 at 09:24:01AM -0700, Reinette Chatre wrote:
> About repeating things: As I see it the annoying repeating results from desire to
> follow the "context-problem-solution" changelog script while also ensuring each

Thanks. And I know it makes sense to repeat things to introduce the context
but let's try to keep that at minimum and only when absolutely necessary.

> About too much text that explains the obvious: I hear you and will add these criteria
> to how changelogs are measured. I do find the criteria a bit subjective though and expect

Yeah, that's fine, don't worry. But it is actually very simple: if it is
visible from the diff itself, then there's no need to state it again in text.
That would be waste of text.

Lemme paste my old git archeology example here in the hope it makes things
more clear. :-)

Do not talk about *what* the patch is doing in the commit message - that
should be obvious from the diff itself. Rather, concentrate on the *why*
it needs to be done.

Imagine one fine day you're doing git archeology, you find the place in
the code about which you want to find out why it was changed the way it 
is now.

You do git annotate <filename> ... find the line, see the commit id and
you do:

git show <commit id>

You read the commit message and there's just gibberish and nothing's
explaining *why* that change was done. And you start scratching your head,
trying to figure out why. Because the damn commit message is not worth the
electrons used to display it with.

This happens to us maintainers at least once a week.

---

## [56] Reinette Chatre — 2025-09-11
*Subject: Re: [PATCH v18 26/33] fs/resctrl: Introduce mbm_assign_on_mkdir to
 enable assignments on mkdir*

Hi Boris,

On 9/11/25 9:54 AM, Borislav Petkov wrote:
> On Thu, Sep 11, 2025 at 09:24:01AM -0700, Reinette Chatre wrote:
>> About repeating things: As I see it the annoying repeating results from desire to

Will do.
 
>> About too much text that explains the obvious: I hear you and will add these criteria
>> to how changelogs are measured. I do find the criteria a bit subjective though and expect

Thank you very much. Will use this as changelog benchmark.

 
> This happens to us maintainers at least once a week.
:(

Reinette

---

## [57] Borislav Petkov — 2025-09-15
*Subject: Re: [PATCH v18 00/33] x86,fs/resctrl: Support AMD Assignable
 Bandwidth Monitoring Counters (ABMC)*

On Fri, Sep 05, 2025 at 04:33:59PM -0500, Babu Moger wrote:
>  .../admin-guide/kernel-parameters.txt         |    2 +-
>  Documentation/filesystems/resctrl.rst         |  325 ++++++

Ok, I've rebased and pushed out the pile into tip:x86/cache.

Please run it one more time to make sure all is good.

Thx.

---

## [58] Reinette Chatre — 2025-09-15
*Subject: Re: [PATCH v18 00/33] x86,fs/resctrl: Support AMD Assignable
 Bandwidth Monitoring Counters (ABMC)*

Hi Boris,

On 9/15/25 4:25 AM, Borislav Petkov wrote:
> On Fri, Sep 05, 2025 at 04:33:59PM -0500, Babu Moger wrote:
>>  .../admin-guide/kernel-parameters.txt         |    2 +-

Thank you very much.

I successfully completed as much testing as I can do without the hardware that has
the feature. Will leave the actual feature sanity check to Babu.

As far as the patches goes ...

I noticed that you modified most changelogs to use closer to 80 characters per line,
max of 81 characters. Considering this I plan to ignore the checkpatch.pl "Prefer a maximum
75 chars per line ..." warning from now on when it comes to changelogs and replace it with
a check for 80 characters with same guidance to resctrl contributors.

Thank you very much for catching and fixing the non-ASCII characters in patch #29. I 
added a new patch check step that checks for non-ASCII characters.

Reinette

---

## [59] Borislav Petkov — 2025-09-16
*Subject: Re: [PATCH v18 00/33] x86,fs/resctrl: Support AMD Assignable
 Bandwidth Monitoring Counters (ABMC)*

On Mon, Sep 15, 2025 at 02:07:26PM -0700, Reinette Chatre wrote:
> I successfully completed as much testing as I can do

Thanks a lot - much appreciated!

> I noticed that you modified most changelogs to use closer to 80 characters
> per line, max of 81 characters. Considering this I plan to ignore the

Yeah, at least. Simply employ sane human judgement instead of blindly relying
on a tool. Sometimes the paragraph needs to have longer lines in order to fit
function names etc. And we don't use 80x25 terminals anymore so the 80 cols
rule is not even strict but a preferred one, as the coding-style.rst says.

> Thank you very much for catching and fixing the non-ASCII characters in
> patch #29. I added a new patch check step that checks for non-ASCII

Sure, np.

Thx.

---

## [60] Moger, Babu — 2025-09-16
*Subject: Re: [PATCH v18 00/33] x86,fs/resctrl: Support AMD Assignable
 Bandwidth Monitoring Counters (ABMC)*

Hi Boris/Reinette,

On 9/15/25 16:07, Reinette Chatre wrote:
> Hi Boris,
> 

I’ve completed the overnight test runs, and everything is working as expected.

However, I discovered an issue with automatic counter assignment that I
introduced during the v17 → v18 rebase. This is my bad. The automatic
merge mistakenly placed the code snippet in rdtgroup_unassign_cntrs()
instead of under mbm_assign_on_mkdir.

Here is the patch snippet. Will send the fix patch separately.

 diff --git a/fs/resctrl/monitor.c b/fs/resctrl/monitor.c
index 50c24460d992..4076336fbba6 100644
--- a/fs/resctrl/monitor.c
+++ b/fs/resctrl/monitor.c
@@ -1200,7 +1200,8 @@ void rdtgroup_assign_cntrs(struct rdtgroup *rdtgrp)
 {
 	struct rdt_resource *r = resctrl_arch_get_resource(RDT_RESOURCE_L3);

-	if (!r->mon_capable || !resctrl_arch_mbm_cntr_assign_enabled(r))
+	if (!r->mon_capable || !resctrl_arch_mbm_cntr_assign_enabled(r) ||
+	    !r->mon.mbm_assign_on_mkdir)
 		return;

 	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID))
@@ -1258,8 +1259,7 @@ void rdtgroup_unassign_cntrs(struct rdtgroup *rdtgrp)
 {
 	struct rdt_resource *r = resctrl_arch_get_resource(RDT_RESOURCE_L3);

-	if (!r->mon_capable || !resctrl_arch_mbm_cntr_assign_enabled(r) ||
-	    !r->mon.mbm_assign_on_mkdir)
+	if (!r->mon_capable || !resctrl_arch_mbm_cntr_assign_enabled(r))
 		return;

 	if (resctrl_is_mon_event_enabled(QOS_L3_MBM_TOTAL_EVENT_ID))

---

## [61] Drew Fustini — 2025-11-16
*Subject: Re: [PATCH v18 00/33] x86,fs/resctrl: Support AMD Assignable
 Bandwidth Monitoring Counters (ABMC)*

On Fri, Sep 05, 2025 at 04:33:59PM -0500, Babu Moger wrote:
> 
> This series adds the support for Assignable Bandwidth Monitoring Counters

Is there a way to find out which EPYC parts support ABMC?

I'm rebasing the RISC-V resctrl support on 6.18 and I noticed there are
a lot of changes to how events work. I've been reading the ABMC code
but I would like to get a better feel for how it works.

I found an EPYC 9124P on Cherry Servers which I was able to experiment
with using resctrl on x86. It has the following in cpuinfo:

cat_l3 cdp_l3 cqm cqm_llc cqm_mbm_local cqm_mbm_total cqm_occup_llc mba

It also has SMBA and BMEC based on the contents of /sys/fs/resctrl.

Ideally, I'd like to find a bare metal EPYC server that has ABMC, too.

Thanks,
Drew

---

## [62] Babu Moger — 2025-11-17
*Subject: Re: [PATCH v18 00/33] x86,fs/resctrl: Support AMD Assignable
 Bandwidth Monitoring Counters (ABMC)*

Hi Drew,

On 11/16/25 11:25, Drew Fustini wrote:
> On Fri, Sep 05, 2025 at 04:33:59PM -0500, Babu Moger wrote:
>> This series adds the support for Assignable Bandwidth Monitoring Counters

Looks like you are on Zen 4 system. ABMC is available on Zen 5 or later 
servers.

#lscpu
Vendor ID:                AuthenticAMD
Model name:            AMD EPYC 9655 96-Core Processor
CPU family:              26

Thanks for trying.

-Babu Moger

---

## [63] Drew Fustini — 2025-11-18
*Subject: Re: [PATCH v18 00/33] x86,fs/resctrl: Support AMD Assignable
 Bandwidth Monitoring Counters (ABMC)*

On Mon, Nov 17, 2025 at 09:07:20AM -0600, Babu Moger wrote:
> Hi Drew,
[snip]
> Looks like you are on Zen 4 system. ABMC is available on Zen 5 or later
> servers.

Thank for letting me know. I didn't realize until now that the last
digit is the Zen generation. Cherry Servers offer an EPYC 9255 so I'll
give that a try.

Drew

---
