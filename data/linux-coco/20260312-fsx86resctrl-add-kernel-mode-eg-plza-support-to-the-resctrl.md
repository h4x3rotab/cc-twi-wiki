---
title: 'fs,x86/resctrl: Add kernel-mode (e.g., PLZA) support to the resctrl subsystem'
date: 2026-03-12
last_reply: 2026-04-22
message_count: 63
participants: ['Babu Moger', 'Askar Safin', 'Reinette Chatre', 'Moger, Babu', 'Luck, Tony']
---

## [1] Babu Moger — 2026-03-12

This series adds support for Privilege-Level Zero Association (PLZA) to the
resctrl subsystem. PLZA is an AMD feature that allows specifying a CLOSID
and/or RMID for execution in kernel mode (privilege level zero), so that
kernel work is not subject to the same resource constrains as the current
user-space task. This avoids kernel operations being aggressively throttled
when a task's memory bandwidth is heavily limited.

The feature documentation is not yet publicly available, but it is expected
to be released in the next few weeks. In the meantime, a brief description
of the features is provided below. 

Privilege Level Zero Association (PLZA) 

Privilege Level Zero Association (PLZA) allows the hardware to
automatically associate execution in Privilege Level Zero (CPL=0) with a
specific COS (Class of Service) and/or RMID (Resource Monitoring
Identifier). The QoS feature set already has a mechanism to associate
execution on each logical processor with an RMID or COS. PLZA allows the
system to override this per-thread association for a thread that is
executing with CPL=0. 
------------------------------------------------------------------------

The series introduces the feature in a way that supports the interface in
a generic manner to accomodate MPAM or other vendor specific implimentation.

Below is the detailed requirements provided by Reinette:
https://lore.kernel.org/lkml/2ab556af-095b-422b-9396-f845c6fd0342@intel.com/

Summary:
1. Kernel-mode/PLZA controls and status should be exposed under the resctrl
   info directory:/sys/fs/resctrl/info/, not as a separate or arch-specific path.

2. Add two info files

 a. kernel_mode
    Purpose: Control how resource allocation and monitoring apply in kernel mode
    (e.g. inherit from task vs global assign).

    Read: List supported modes and show current one (e.g. with [brackets]).
    Write: Set current mode by name (e.g. inherit_ctrl_and_mon, global_assign_ctrl_assign_mon).

b. kernel_mode_assignment

   Purpose: When a “global assign” kernel mode is active, specify which resctrl group
   (CLOSID/RMID) is used for kernel work.

   Read: Show the assigned group in a path-like form (e.g. //, ctrl1//, ctrl1/mon1/).
   Write: Assign or clear the group used for kernel mode (and optionally clear with an empty write).

The patches are based on top of commit (v7.0.0-rc3)
839e91ce3f41b (tip/master) Merge branch into tip/master: 'x86/tdx'
------------------------------------------------------------------------

Examples: kernel_mode and kernel_mode_assignment

All paths below are under /sys/fs/resctrl/ (e.g. info/kernel_mode means
/sys/fs/resctrl/info/kernel_mode). Resctrl must be mounted and the platform
must support the relevant modes (e.g. AMD with PLZA).

1) kernel_mode — show and set the current kernel mode

   Read supported modes and which one is active (current in brackets):

     $ cat info/kernel_mode
     [inherit_ctrl_and_mon]
     global_assign_ctrl_inherit_mon
     global_assign_ctrl_assign_mon

   Set the active mode (e.g. use one CLOSID+RMID for all kernel work):

     $ echo "global_assign_ctrl_assign_mon" > info/kernel_mode
     $ cat info/kernel_mode
     inherit_ctrl_and_mon
     global_assign_ctrl_inherit_mon
     [global_assign_ctrl_assign_mon]

   Mode meanings:
   - inherit_ctrl_and_mon: kernel uses same CLOSID/RMID as the current task (default).
   - global_assign_ctrl_inherit_mon: one CLOSID for all kernel work; RMID inherited from user.
   - global_assign_ctrl_assign_mon: one resource group (CLOSID+RMID) for all kernel work.

2) kernel_mode_assignment — show and set which group is used for kernel work

   Only relevant when kernel_mode is not "inherit_ctrl_and_mon". Read the
   currently assigned group (path format is "CTRL_MON/MON/"):

     $ cat info/kernel_mode_assignment
     //

   "//" means the default CTRL_MON group is assigned. Assign a specific
   group instead (e.g. a CTRL_MON group "ctrl1", or a MON group "mon1" under it):

     $ echo "ctrl1//" > info/kernel_mode_assignment
     $ cat info/kernel_mode_assignment
     ctrl1//

     $ echo "ctrl1/mon1/" > info/kernel_mode_assignment
     $ cat info/kernel_mode_assignment
     ctrl1/mon1/

   Clear the assignment (no dedicated group for kernel work):

     $ echo >> info/kernel_mode_assignment
     $ cat info/kernel_mode_assignment
     Kmode is not configured

   Errors (e.g. invalid group name or unsupported mode) are reported in
   info/last_cmd_status.

---

v2: 
     This is similar to RFC with new proposal. Names of the some interfaces
     are not final. Lets fix that later as we move forward.

     Separated the two features: Global Bandwidth Enforcement (GLBE) and
     Privilege Level Zero Association (PLZA).
 
     This series only adds support for PLZA.

     Used the name of the feature as kmode instead of PLZA. That can be changed as well.

     Tony suggested using global variables to store the kernel mode
     CLOSID and RMID. However, the kernel mode CLOSID and RMID are
     coming from rdtgroup structure with the new interface. Accessing
     them requires holding the associated lock, which would make the
     context switch path unnecessarily expensive. So, dropped the idea.
     https://lore.kernel.org/lkml/aXuxVSbk1GR2ttzF@agluck-desk3/
     Let me know if there are other ways to optimize this.

Patch 1: Data structures and arch hook: Add resctrl_kmode,
	resctrl_kmode_cfg, kernel-mode bits, and resctrl_arch_get_kmode_cfg()
	for generic resctrl kernel mode (e.g. PLZA).

Patch 2: Implement resctrl_arch_get_kmode_cfg() on x86, add global resctrl_kcfg
	and resctrl_kmode_init() to set default kmode.

Patch 3: Add info/kernel_mode and resctrl_kernel_mode_show() to list supported
	kernel modes and show the current one in brackets.

Patch 4: Add x86 PLZA support and boot option rdt=plza.

Patch 5: Add supported modes from CPUID.

Patch 6: Add rdt_kmode_enable_key and arch enable/disable helpers so PLZA only
	touches fast paths when enabled.

Patch 7: Add MSR_IA32_PQR_PLZA_ASSOC, bit defines, and union qos_pqr_plza_assoc
	for programming PLZA.

Patch 8: Add Per-CPU and per-task state.

Patch 9: Add resctrl_arch_configure_kmode() and resctrl_arch_set_kmode()
	to program PLZA per domain and set/clear it on a CPU.

Patch 10: In the sched-in path, program MSR_IA32_PQR_PLZA_ASSOC from task or
	per-CPU kmode; only write when kmode changes; guard with rdt_kmode_enable_key.

Patch 11: Add write handler so the current kernel mode can be set by name.

Patch 12: Add info/kernel_mode_assignment and show which rdtgroup is assigned
	for kernel mode in CTRL_MON/MON/ form.

Patch 13: Add write handler to assign/clear the group used for kernel mode;
	enforce single assignment and clear on rmdir.

Patch 14: Update per-CPU PLZA state when its cpu_mask changes (add/remove CPUs)
	via cpus_write_kmode() and helpers.

Patch 15: Refactor so task list respects t->kmode when the group has kmode (PLZA),
	so tasks are shown correctly.

Patch 16: Add arch helper to set task kmode.
--------------------------------------------------------------------------------

v1 : https://lore.kernel.org/lkml/cover.1769029977.git.babu.moger@amd.com/


Babu Moger (16):
  fs/resctrl: Add kernel mode (kmode) data structures and arch hook
  fs, x86/resctrl: Add architecture routines for kernel mode
    initialization
  fs/resctrl: Add info/kernel_mode file to show kernel mode options
  x86/resctrl: Support Privilege-Level Zero Association (PLZA)
  x86/resctrl: Initialize supported kernel modes when CPUID reports PLZA
  resctrl: Introduce kmode static key enable/disable helpers
  x86/resctrl: Add data structures and definitions for PLZA
    configuration
  x86/resctrl: Add per-CPU and per-task kernel mode state
  x86,fs/resctrl: Add the functionality to configure PLZA
  x86/resctrl: Add PLZA state tracking and context switch handling
  fs/resctrl: Add write handler for info/kernel_mode
  fs/resctrl: Add info/kernel_mode_assignment to show kernel-mode
    rdtgroup
  fs/resctrl: Add write interface for kernel_mode_assignment
  fs/resctrl: Update kmode configuration when cpu_mask changes
  x86/resctrl: Refactor show_rdt_tasks() to support PLZA tasks
  fs/resctrl: Add per-task kmode enable support via rdtgroup

 .../admin-guide/kernel-parameters.txt         |   2 +-
 Documentation/filesystems/resctrl.rst         |  69 ++
 arch/x86/include/asm/cpufeatures.h            |   1 +
 arch/x86/include/asm/msr-index.h              |   7 +
 arch/x86/include/asm/resctrl.h                |  92 ++-
 arch/x86/kernel/cpu/resctrl/core.c            |  12 +
 arch/x86/kernel/cpu/resctrl/ctrlmondata.c     |  77 +++
 arch/x86/kernel/cpu/resctrl/internal.h        |  26 +
 arch/x86/kernel/cpu/resctrl/rdtgroup.c        |   2 +
 arch/x86/kernel/cpu/scattered.c               |   1 +
 fs/resctrl/internal.h                         |   2 +
 fs/resctrl/rdtgroup.c                         | 635 +++++++++++++++++-
 include/linux/resctrl.h                       |  40 ++
 include/linux/resctrl_types.h                 |  30 +
 include/linux/sched.h                         |   2 +
 15 files changed, 989 insertions(+), 9 deletions(-)

---

## [2] Babu Moger — 2026-03-12
*Subject: [PATCH v2 01/16] fs/resctrl: Add kernel mode (kmode) data structures and arch hook*

Add resctrl_kmode, resctrl_kmode_cfg, kernel mode bit defines, and
resctrl_arch_get_kmode_cfg() for resctrl kernel mode (e.g. PLZA) support.

INHERIT_CTRL_AND_MON: kernel and user space use the same CLOSID/RMID.

GLOBAL_ASSIGN_CTRL_INHERIT_MON: When active, CLOSID/control group can be
assigned for all kernel work while all kernel work uses same RMID as user
space.

GLOBAL_ASSIGN_CTRL_ASSIGN_MON: When active the same resource group (CLOSID
and RMID) can be assigned to all the kernel work. This could be any group,
including the default group.

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v2: New patch to handle PLZA interfaces with /sys/fs/resctrl/info/ directory.
    https://lore.kernel.org/lkml/2ab556af-095b-422b-9396-f845c6fd0342@intel.com/
---
 include/linux/resctrl.h       | 10 ++++++++++
 include/linux/resctrl_types.h | 30 ++++++++++++++++++++++++++++++
 2 files changed, 40 insertions(+)

diff --git a/include/linux/resctrl.h b/include/linux/resctrl.h
index 006e57fd7ca5..2c36d1ac392f 100644
--- a/include/linux/resctrl.h
+++ b/include/linux/resctrl.h
@@ -699,6 +699,16 @@ int resctrl_arch_io_alloc_enable(struct rdt_resource *r, bool enable);
  */
 bool resctrl_arch_get_io_alloc_enabled(struct rdt_resource *r);
 
+/**
+ * resctrl_arch_get_kmode_cfg() - Get resctrl kernel mode configuration
+ * @kcfg:	Filled with current kernel mode config (kmode, kmode_cur, k_rdtgrp).
+ *
+ * Used by the arch (e.g. x86) to report which kernel mode is active and,
+ * when a global assign mode is in use, which rdtgroup is assigned to
+ * kernel work.
+ */
+void resctrl_arch_get_kmode_cfg(struct resctrl_kmode_cfg *kcfg);
+
 extern unsigned int resctrl_rmid_realloc_threshold;
 extern unsigned int resctrl_rmid_realloc_limit;
 
diff --git a/include/linux/resctrl_types.h b/include/linux/resctrl_types.h
index a5f56faa18d2..6b78b08eab29 100644
--- a/include/linux/resctrl_types.h
+++ b/include/linux/resctrl_types.h
@@ -65,7 +65,37 @@ enum resctrl_event_id {
 	QOS_NUM_EVENTS,
 };
 
+/**
+ * struct resctrl_kmode - Resctrl kernel mode descriptor
+ * @name:	Human-readable name of the kernel mode.
+ * @val:	Bitmask value for the kernel mode (e.g. INHERIT_CTRL_AND_MON).
+ */
+struct resctrl_kmode {
+	char    name[32];
+	u32     val;
+};
+
+/**
+ * struct resctrl_kmode_cfg - Resctrl kernel mode configuration
+ * @kmode:	Requested kernel mode.
+ * @kmode_cur:	Currently active kernel mode.
+ * @k_rdtgrp:	Resource control structure in use, or NULL otherwise.
+ */
+struct resctrl_kmode_cfg {
+	u32 kmode;
+	u32 kmode_cur;
+	struct rdtgroup *k_rdtgrp;
+};
+
 #define QOS_NUM_L3_MBM_EVENTS	(QOS_L3_MBM_LOCAL_EVENT_ID - QOS_L3_MBM_TOTAL_EVENT_ID + 1)
 #define MBM_STATE_IDX(evt)	((evt) - QOS_L3_MBM_TOTAL_EVENT_ID)
 
+/* Resctrl kernel mode bits (e.g. for PLZA). */
+#define INHERIT_CTRL_AND_MON		BIT(0)	/* Kernel uses same CLOSID/RMID as user. */
+/* One CLOSID for all kernel work; RMID inherited from user. */
+#define GLOBAL_ASSIGN_CTRL_INHERIT_MON	BIT(1)
+/* One resource group (CLOSID+RMID) for all kernel work. */
+#define GLOBAL_ASSIGN_CTRL_ASSIGN_MON	BIT(2)
+#define RESCTRL_KERNEL_MODES_NUM	3
+
 #endif /* __LINUX_RESCTRL_TYPES_H */

---

## [3] Babu Moger — 2026-03-12
*Subject: [PATCH v2 02/16] fs, x86/resctrl: Add architecture routines for kernel mode initialization*

Implement the resctrl kernel mode (kmode) arch initialization.

- Add resctrl_arch_get_kmode_cfg() to fill the default kernel mode
  (INHERIT_CTRL_AND_MON). This can be extended later (e.g. for PLZA) to set
  additional modes.

- Add global resctrl_kcfg and resctrl_kmode_init() to initialize default
  values.

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v2: New patch to handle PLZA interfaces with /sys/fs/resctrl/info/ directory.
    https://lore.kernel.org/lkml/2ab556af-095b-422b-9396-f845c6fd0342@intel.com/
---
 arch/x86/kernel/cpu/resctrl/core.c |  7 +++++++
 fs/resctrl/rdtgroup.c              | 10 ++++++++++
 2 files changed, 17 insertions(+)

diff --git a/arch/x86/kernel/cpu/resctrl/core.c b/arch/x86/kernel/cpu/resctrl/core.c
index 7667cf7c4e94..4c3ab2d93909 100644
--- a/arch/x86/kernel/cpu/resctrl/core.c
+++ b/arch/x86/kernel/cpu/resctrl/core.c
@@ -892,6 +892,13 @@ bool resctrl_arch_is_evt_configurable(enum resctrl_event_id evt)
 	}
 }
 
+void resctrl_arch_get_kmode_cfg(struct resctrl_kmode_cfg *kcfg)
+{
+	kcfg->kmode = INHERIT_CTRL_AND_MON;
+	kcfg->kmode_cur = INHERIT_CTRL_AND_MON;
+	kcfg->k_rdtgrp = NULL;
+}
+
 static __init bool get_mem_config(void)
 {
 	struct rdt_hw_resource *hw_res = &rdt_resources_all[RDT_RESOURCE_MBA];
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index 5da305bd36c9..9d6d74af4874 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -76,6 +76,9 @@ static void rdtgroup_destroy_root(void);
 
 struct dentry *debugfs_resctrl;
 
+/* Current resctrl kernel mode config (kmode, kmode_cur, k_rdtgrp). */
+struct resctrl_kmode_cfg resctrl_kcfg;
+
 /*
  * Memory bandwidth monitoring event to use for the default CTRL_MON group
  * and each new CTRL_MON group created by the user.  Only relevant when
@@ -2204,6 +2207,11 @@ static void io_alloc_init(void)
 	}
 }
 
+static void resctrl_kmode_init(void)
+{
+	resctrl_arch_get_kmode_cfg(&resctrl_kcfg);
+}
+
 void resctrl_file_fflags_init(const char *config, unsigned long fflags)
 {
 	struct rftype *rft;
@@ -4554,6 +4562,8 @@ int resctrl_init(void)
 
 	io_alloc_init();
 
+	resctrl_kmode_init();
+
 	ret = resctrl_l3_mon_resource_init();
 	if (ret)
 		return ret;

---

## [4] Babu Moger — 2026-03-12
*Subject: [PATCH v2 03/16] fs/resctrl: Add info/kernel_mode file to show kernel mode options*

Add resctrl_kernel_mode_show() and the "kernel_mode" info file to
display supported kernel modes and the current one (e.g. for PLZA).

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v2: New patch to handle PLZA interfaces with /sys/fs/resctrl/info/ directory.
    https://lore.kernel.org/lkml/2ab556af-095b-422b-9396-f845c6fd0342@intel.com/
---
 fs/resctrl/rdtgroup.c | 42 ++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 42 insertions(+)

diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index 9d6d74af4874..081da61bfe84 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -984,6 +984,41 @@ static int rdt_last_cmd_status_show(struct kernfs_open_file *of,
 	return 0;
 }
 
+/*
+ * Supported resctrl kernel modes for info/kernel_mode. Names match
+ * user-visible strings.
+ */
+static struct resctrl_kmode kmodes[RESCTRL_KERNEL_MODES_NUM] = {
+	{"inherit_ctrl_and_mon", INHERIT_CTRL_AND_MON},
+	{"global_assign_ctrl_inherit_mon", GLOBAL_ASSIGN_CTRL_INHERIT_MON},
+	{"global_assign_ctrl_assign_mon", GLOBAL_ASSIGN_CTRL_ASSIGN_MON},
+};
+
+/**
+ * resctrl_kernel_mode_show() - Show supported and current resctrl kernel modes
+ * @of:	kernfs file handle.
+ * @s:	seq_file to write to.
+ * @v:	unused.
+ *
+ * Writes one line per supported mode. The currently active mode is shown as
+ * [name]; other supported modes are shown as name.
+ */
+static int resctrl_kernel_mode_show(struct kernfs_open_file *of,
+				    struct seq_file *s, void *v)
+{
+	int i;
+
+	mutex_lock(&rdtgroup_mutex);
+	for (i = 0; i < RESCTRL_KERNEL_MODES_NUM; i++) {
+		if (resctrl_kcfg.kmode_cur & kmodes[i].val)
+			seq_printf(s, "[%s]\n", kmodes[i].name);
+		else if (resctrl_kcfg.kmode & kmodes[i].val)
+			seq_printf(s, "%s\n", kmodes[i].name);
+	}
+	mutex_unlock(&rdtgroup_mutex);
+	return 0;
+}
+
 void *rdt_kn_parent_priv(struct kernfs_node *kn)
 {
 	/*
@@ -1885,6 +1920,13 @@ static struct rftype res_common_files[] = {
 		.seq_show	= rdt_last_cmd_status_show,
 		.fflags		= RFTYPE_TOP_INFO,
 	},
+	{
+		.name		= "kernel_mode",
+		.mode		= 0444,
+		.kf_ops		= &rdtgroup_kf_single_ops,
+		.seq_show	= resctrl_kernel_mode_show,
+		.fflags		= RFTYPE_TOP_INFO,
+	},
 	{
 		.name		= "mbm_assign_on_mkdir",
 		.mode		= 0644,

---

## [5] Babu Moger — 2026-03-12
*Subject: [PATCH v2 04/16] x86/resctrl: Support Privilege-Level Zero Association (PLZA)*

Customers have identified an issue while using the QoS resource Control
feature. If a memory bandwidth associated with a CLOSID is aggressively
throttled, and it moves into Kernel mode, the Kernel operations are also
aggressively throttled. This can stall forward progress and eventually
degrade overall system performance. AMD hardware supports a feature
Privilege-Level Zero Association (PLZA) to change the association of the
thread as soon as it begins executing.

Privilege-Level Zero Association (PLZA) allows the user to specify a CLOSID
and/or RMID associated with execution in Privilege-Level Zero. When enabled
on a HW thread, when the thread enters Privilege-Level Zero, transactions
associated with that thread will be associated with the PLZA CLOSID and/or
RMID. Otherwise, the HW thread will be associated with the CLOSID and RMID
identified by PQR_ASSOC.

Add PLZA support to resctrl and introduce a kernel parameter that allows
enabling or disabling the feature at boot time.

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v2: - Rebased on top of the latest tip.
---
 Documentation/admin-guide/kernel-parameters.txt | 2 +-
 arch/x86/include/asm/cpufeatures.h              | 1 +
 arch/x86/kernel/cpu/resctrl/core.c              | 2 ++
 arch/x86/kernel/cpu/scattered.c                 | 1 +
 4 files changed, 5 insertions(+), 1 deletion(-)

diff --git a/Documentation/admin-guide/kernel-parameters.txt b/Documentation/admin-guide/kernel-parameters.txt
index cb850e5290c2..b1ea28505835 100644
--- a/Documentation/admin-guide/kernel-parameters.txt
+++ b/Documentation/admin-guide/kernel-parameters.txt
@@ -6439,7 +6439,7 @@ Kernel parameters
 	rdt=		[HW,X86,RDT]
 			Turn on/off individual RDT features. List is:
 			cmt, mbmtotal, mbmlocal, l3cat, l3cdp, l2cat, l2cdp,
-			mba, smba, bmec, abmc, sdciae, energy[:guid],
+			mba, smba, bmec, abmc, sdciae, plza, energy[:guid],
 			perf[:guid].
 			E.g. to turn on cmt and turn off mba use:
 				rdt=cmt,!mba
diff --git a/arch/x86/include/asm/cpufeatures.h b/arch/x86/include/asm/cpufeatures.h
index dbe104df339b..b7932ffc185b 100644
--- a/arch/x86/include/asm/cpufeatures.h
+++ b/arch/x86/include/asm/cpufeatures.h
@@ -515,6 +515,7 @@
 						      * and purposes if CLEAR_CPU_BUF_VM is set).
 						      */
 #define X86_FEATURE_X2AVIC_EXT		(21*32+20) /* AMD SVM x2AVIC support for 4k vCPUs */
+#define X86_FEATURE_PLZA		(21*32+21) /* Privilege-Level Zero Association */
 
 /*
  * BUG word(s)
diff --git a/arch/x86/kernel/cpu/resctrl/core.c b/arch/x86/kernel/cpu/resctrl/core.c
index 4c3ab2d93909..8fb9029fe547 100644
--- a/arch/x86/kernel/cpu/resctrl/core.c
+++ b/arch/x86/kernel/cpu/resctrl/core.c
@@ -799,6 +799,7 @@ enum {
 	RDT_FLAG_BMEC,
 	RDT_FLAG_ABMC,
 	RDT_FLAG_SDCIAE,
+	RDT_FLAG_PLZA,
 };
 
 #define RDT_OPT(idx, n, f)	\
@@ -826,6 +827,7 @@ static struct rdt_options rdt_options[]  __ro_after_init = {
 	RDT_OPT(RDT_FLAG_BMEC,	    "bmec",	X86_FEATURE_BMEC),
 	RDT_OPT(RDT_FLAG_ABMC,	    "abmc",	X86_FEATURE_ABMC),
 	RDT_OPT(RDT_FLAG_SDCIAE,    "sdciae",	X86_FEATURE_SDCIAE),
+	RDT_OPT(RDT_FLAG_PLZA,	    "plza",	X86_FEATURE_PLZA),
 };
 #define NUM_RDT_OPTIONS ARRAY_SIZE(rdt_options)
 
diff --git a/arch/x86/kernel/cpu/scattered.c b/arch/x86/kernel/cpu/scattered.c
index 42c7eac0c387..acc137d327b5 100644
--- a/arch/x86/kernel/cpu/scattered.c
+++ b/arch/x86/kernel/cpu/scattered.c
@@ -59,6 +59,7 @@ static const struct cpuid_bit cpuid_bits[] = {
 	{ X86_FEATURE_BMEC,			CPUID_EBX,  3, 0x80000020, 0 },
 	{ X86_FEATURE_ABMC,			CPUID_EBX,  5, 0x80000020, 0 },
 	{ X86_FEATURE_SDCIAE,			CPUID_EBX,  6, 0x80000020, 0 },
+	{ X86_FEATURE_PLZA,			CPUID_EBX,  9, 0x80000020, 0 },
 	{ X86_FEATURE_TSA_SQ_NO,		CPUID_ECX,  1, 0x80000021, 0 },
 	{ X86_FEATURE_TSA_L1_NO,		CPUID_ECX,  2, 0x80000021, 0 },
 	{ X86_FEATURE_AMD_WORKLOAD_CLASS,	CPUID_EAX, 22, 0x80000021, 0 },

---

## [6] Babu Moger — 2026-03-12
*Subject: [PATCH v2 05/16] x86/resctrl: Initialize supported kernel modes when CPUID reports PLZA*

If X86_FEATURE_PLZA is set, add GLOBAL_ASSIGN_CTRL_INHERIT_MON and
GLOBAL_ASSIGN_CTRL_ASSIGN_MON to the supported kmode bits in
resctrl_arch_get_kmode_cfg().

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v2: New patch to handle PLZA interfaces with /sys/fs/resctrl/info/ directory.
    https://lore.kernel.org/lkml/2ab556af-095b-422b-9396-f845c6fd0342@intel.com/
---
 arch/x86/kernel/cpu/resctrl/core.c | 3 +++
 1 file changed, 3 insertions(+)

diff --git a/arch/x86/kernel/cpu/resctrl/core.c b/arch/x86/kernel/cpu/resctrl/core.c
index 8fb9029fe547..739190ac96d3 100644
--- a/arch/x86/kernel/cpu/resctrl/core.c
+++ b/arch/x86/kernel/cpu/resctrl/core.c
@@ -898,6 +898,9 @@ void resctrl_arch_get_kmode_cfg(struct resctrl_kmode_cfg *kcfg)
 {
 	kcfg->kmode = INHERIT_CTRL_AND_MON;
 	kcfg->kmode_cur = INHERIT_CTRL_AND_MON;
+	if (rdt_cpu_has(X86_FEATURE_PLZA))
+		kcfg->kmode |= GLOBAL_ASSIGN_CTRL_INHERIT_MON |
+				GLOBAL_ASSIGN_CTRL_ASSIGN_MON;
 	kcfg->k_rdtgrp = NULL;
 }

---

## [7] Babu Moger — 2026-03-12
*Subject: [PATCH v2 06/16] resctrl: Introduce kmode static key enable/disable helpers*

The resctrl subsystem uses static keys to efficiently toggle allocation and
monitoring features at runtime (e.g., rdt_alloc_enable_key,
rdt_mon_enable_key). Privilege-Level Zero Association (PLZA) is a new,
optional capability that should only impact fast paths when enabled.

Introduce a new static key, rdt_kmode_enable_key, and wire it up with arch
helpers that mirror the existing alloc/mon pattern. This provides a
lightweight, unified mechanism to guard PLZA-specific paths and to keep the
global resctrl usage count accurate.

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v2: Changed the name from PLZA to kmode to better reflect the purpose of the static key.
---
 arch/x86/include/asm/resctrl.h         | 13 +++++++++++++
 arch/x86/kernel/cpu/resctrl/rdtgroup.c |  2 ++
 fs/resctrl/rdtgroup.c                  |  6 ++++++
 3 files changed, 21 insertions(+)

diff --git a/arch/x86/include/asm/resctrl.h b/arch/x86/include/asm/resctrl.h
index 575f8408a9e7..4b4291006e78 100644
--- a/arch/x86/include/asm/resctrl.h
+++ b/arch/x86/include/asm/resctrl.h
@@ -48,6 +48,7 @@ extern bool rdt_mon_capable;
 DECLARE_STATIC_KEY_FALSE(rdt_enable_key);
 DECLARE_STATIC_KEY_FALSE(rdt_alloc_enable_key);
 DECLARE_STATIC_KEY_FALSE(rdt_mon_enable_key);
+DECLARE_STATIC_KEY_FALSE(rdt_kmode_enable_key);
 
 static inline bool resctrl_arch_alloc_capable(void)
 {
@@ -83,6 +84,18 @@ static inline void resctrl_arch_disable_mon(void)
 	static_branch_dec_cpuslocked(&rdt_enable_key);
 }
 
+static inline void resctrl_arch_enable_kmode(void)
+{
+	static_branch_enable_cpuslocked(&rdt_kmode_enable_key);
+	static_branch_inc_cpuslocked(&rdt_enable_key);
+}
+
+static inline void resctrl_arch_disable_kmode(void)
+{
+	static_branch_disable_cpuslocked(&rdt_kmode_enable_key);
+	static_branch_dec_cpuslocked(&rdt_enable_key);
+}
+
 /*
  * __resctrl_sched_in() - Writes the task's CLOSid/RMID to IA32_PQR_MSR
  *
diff --git a/arch/x86/kernel/cpu/resctrl/rdtgroup.c b/arch/x86/kernel/cpu/resctrl/rdtgroup.c
index 885026468440..05299117d871 100644
--- a/arch/x86/kernel/cpu/resctrl/rdtgroup.c
+++ b/arch/x86/kernel/cpu/resctrl/rdtgroup.c
@@ -38,6 +38,8 @@ DEFINE_STATIC_KEY_FALSE(rdt_mon_enable_key);
 
 DEFINE_STATIC_KEY_FALSE(rdt_alloc_enable_key);
 
+DEFINE_STATIC_KEY_FALSE(rdt_kmode_enable_key);
+
 /*
  * This is safe against resctrl_arch_sched_in() called from __switch_to()
  * because __switch_to() is executed with interrupts disabled. A local call
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index 081da61bfe84..bb775afc78f5 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -2911,6 +2911,9 @@ static int rdt_get_tree(struct fs_context *fc)
 		resctrl_arch_enable_alloc();
 	if (resctrl_arch_mon_capable())
 		resctrl_arch_enable_mon();
+	if (resctrl_kcfg.kmode & (GLOBAL_ASSIGN_CTRL_INHERIT_MON |
+				  GLOBAL_ASSIGN_CTRL_ASSIGN_MON))
+		resctrl_arch_enable_kmode();
 
 	if (resctrl_arch_alloc_capable() || resctrl_arch_mon_capable())
 		resctrl_mounted = true;
@@ -3233,6 +3236,9 @@ static void rdt_kill_sb(struct super_block *sb)
 		resctrl_arch_disable_alloc();
 	if (resctrl_arch_mon_capable())
 		resctrl_arch_disable_mon();
+	if (resctrl_kcfg.kmode & (GLOBAL_ASSIGN_CTRL_INHERIT_MON |
+				  GLOBAL_ASSIGN_CTRL_ASSIGN_MON))
+		resctrl_arch_disable_kmode();
 	resctrl_mounted = false;
 	kernfs_kill_sb(sb);
 	mutex_unlock(&rdtgroup_mutex);

---

## [8] Babu Moger — 2026-03-12
*Subject: [PATCH v2 07/16] x86/resctrl: Add data structures and definitions for PLZA configuration*

Privilege Level Zero Association (PLZA) is configured with a Per Logical
Processor MSR: MSR_IA32_PQR_PLZA_ASSOC (0xc00003fc).

Add the necessary data structures and definitions to support PLZA
configuration.

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v2: No changes. Just rebasing on top of the latest tip branch.
---
 arch/x86/include/asm/msr-index.h       |  7 +++++++
 arch/x86/kernel/cpu/resctrl/internal.h | 26 ++++++++++++++++++++++++++
 2 files changed, 33 insertions(+)

diff --git a/arch/x86/include/asm/msr-index.h b/arch/x86/include/asm/msr-index.h
index be3e3cc963b2..c96fb7db3ca9 100644
--- a/arch/x86/include/asm/msr-index.h
+++ b/arch/x86/include/asm/msr-index.h
@@ -1282,10 +1282,17 @@
 /* - AMD: */
 #define MSR_IA32_MBA_BW_BASE		0xc0000200
 #define MSR_IA32_SMBA_BW_BASE		0xc0000280
+#define MSR_IA32_PQR_PLZA_ASSOC		0xc00003fc
 #define MSR_IA32_L3_QOS_ABMC_CFG	0xc00003fd
 #define MSR_IA32_L3_QOS_EXT_CFG		0xc00003ff
 #define MSR_IA32_EVT_CFG_BASE		0xc0000400
 
+/* Lower 32 bits of MSR_IA32_PQR_PLZA_ASSOC */
+#define RMID_EN				BIT(31)
+/* Upper 32 bits of MSR_IA32_PQR_PLZA_ASSOC */
+#define CLOSID_EN			BIT(15)
+#define PLZA_EN				BIT(31)
+
 /* AMD-V MSRs */
 #define MSR_VM_CR                       0xc0010114
 #define MSR_VM_IGNNE                    0xc0010115
diff --git a/arch/x86/kernel/cpu/resctrl/internal.h b/arch/x86/kernel/cpu/resctrl/internal.h
index e3cfa0c10e92..403849a22e91 100644
--- a/arch/x86/kernel/cpu/resctrl/internal.h
+++ b/arch/x86/kernel/cpu/resctrl/internal.h
@@ -222,6 +222,32 @@ union l3_qos_abmc_cfg {
 	unsigned long full;
 };
 
+/*
+ * PLZA can be configured on a CPU by writing to MSR_IA32_PQR_PLZA_ASSOC.
+ *
+ * @rmid		: The RMID to be configured for PLZA.
+ * @reserved1		: Reserved.
+ * @rmid_en		: Associate RMID or not.
+ * @closid		: The CLOSID to be configured for PLZA.
+ * @reserved2		: Reserved.
+ * @closid_en		: Associate CLOSID or not.
+ * @reserved3		: Reserved.
+ * @plza_en		: Configure PLZA or not.
+ */
+union qos_pqr_plza_assoc {
+	struct {
+		unsigned long rmid	:12,
+			      reserved1	:19,
+			      rmid_en	: 1,
+			      closid	: 4,
+			      reserved2	:11,
+			      closid_en	: 1,
+			      reserved3	:15,
+			      plza_en	: 1;
+	} split;
+	unsigned long full;
+};
+
 void rdt_ctrl_update(void *arg);
 
 int rdt_get_l3_mon_config(struct rdt_resource *r);

---

## [9] Babu Moger — 2026-03-12
*Subject: [PATCH v2 08/16] x86/resctrl: Add per-CPU and per-task kernel mode state*

Add per-CPU state and per-task state for resctrl kernel mode.

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v2: Minor name change from plza to kmode.
    Tony suggested using global variables to store the kernel mode
    CLOSID and RMID. However, the kernel mode CLOSID and RMID are
    coming from rdtgroup structure with the new interface. Accessing
    them requires holding the associated lock, which would make the
    context switch path unnecessarily expensive.
    https://lore.kernel.org/lkml/aXuxVSbk1GR2ttzF@agluck-desk3/
---
 arch/x86/include/asm/resctrl.h | 14 +++++++++++++-
 include/linux/sched.h          |  2 ++
 2 files changed, 15 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/resctrl.h b/arch/x86/include/asm/resctrl.h
index 4b4291006e78..e0a992abaeb4 100644
--- a/arch/x86/include/asm/resctrl.h
+++ b/arch/x86/include/asm/resctrl.h
@@ -21,9 +21,13 @@
 /**
  * struct resctrl_pqr_state - State cache for the PQR MSR
  * @cur_rmid:		The cached Resource Monitoring ID
- * @cur_closid:	The cached Class Of Service ID
+ * @cur_closid:		The cached Class Of Service ID
  * @default_rmid:	The user assigned Resource Monitoring ID
  * @default_closid:	The user assigned cached Class Of Service ID
+ * @cur_kmode:		Currently active kernel mode (PLZA) bits for this CPU
+ * @default_kmode:	Default kernel mode bits for this CPU (e.g. from resctrl mount)
+ * @kmode_rmid:		RMID used when executing in kernel mode (PLZA)
+ * @kmode_closid:	CLOSID used when executing in kernel mode (PLZA)
  *
  * The upper 32 bits of MSR_IA32_PQR_ASSOC contain closid and the
  * lower 10 bits rmid. The update to MSR_IA32_PQR_ASSOC always
@@ -32,12 +36,20 @@
  *
  * The cache also helps to avoid pointless updates if the value does
  * not change.
+ *
+ * Kernel mode (e.g. PLZA) state: cur_kmode/default_kmode hold the active
+ * and default mode bits; kmode_rmid and kmode_closid are the association
+ * used when the thread is in privilege level zero.
  */
 struct resctrl_pqr_state {
 	u32			cur_rmid;
 	u32			cur_closid;
 	u32			default_rmid;
 	u32			default_closid;
+	u32			cur_kmode;
+	u32			default_kmode;
+	u32			kmode_rmid;
+	u32			kmode_closid;
 };
 
 DECLARE_PER_CPU(struct resctrl_pqr_state, pqr_state);
diff --git a/include/linux/sched.h b/include/linux/sched.h
index a7b4a980eb2f..2ec0530399be 100644
--- a/include/linux/sched.h
+++ b/include/linux/sched.h
@@ -1328,6 +1328,8 @@ struct task_struct {
 #ifdef CONFIG_X86_CPU_RESCTRL
 	u32				closid;
 	u32				rmid;
+	/* Resctrl kernel mode (e.g. PLZA) bits for this task */
+	u32				kmode;
 #endif
 #ifdef CONFIG_FUTEX
 	struct robust_list_head __user	*robust_list;

---

## [10] Babu Moger — 2026-03-12
*Subject: [PATCH v2 09/16] x86,fs/resctrl: Add the functionality to configure PLZA*

Privilege Level Zero Association (PLZA) is configured by writing to
MSR_IA32_PQR_PLZA_ASSOC. PLZA is disabled by default on all logical
processors in the QOS Domain. System software must follow the following
sequence.

1. Set the closid, closid_en, rmid and rmid_en fields of
MSR_IA32_PQR_PLZA_ASSOC to the desired configuration on all logical
processors in the QOS Domain.

2. Set MSR_IA32_PQR_PLZA_ASSOC[PLZA_EN]=1 for
all logical processors in the QOS domain where PLZA should be enabled.

MSR_IA32_PQR_PLZA_ASSOC[PLZA_EN] may have a different value on every
logical processor in the QOS domain. The system software should perform
this as a read-modify-write to avoid changing the value of closid_en,
closid, rmid_en, and rmid fields of MSR_IA32_PQR_PLZA_ASSOC.

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v2: - Updated the commit message to include the sequence of steps to enable PLZA.
      Added mode code comments for clarity.
      Added kmode to functin names to be generic.
---
 arch/x86/include/asm/resctrl.h            | 19 ++++++
 arch/x86/kernel/cpu/resctrl/ctrlmondata.c | 77 +++++++++++++++++++++++
 include/linux/resctrl.h                   | 30 +++++++++
 3 files changed, 126 insertions(+)

diff --git a/arch/x86/include/asm/resctrl.h b/arch/x86/include/asm/resctrl.h
index e0a992abaeb4..167be18983c1 100644
--- a/arch/x86/include/asm/resctrl.h
+++ b/arch/x86/include/asm/resctrl.h
@@ -186,6 +186,25 @@ static inline bool resctrl_arch_match_rmid(struct task_struct *tsk, u32 ignored,
 	return READ_ONCE(tsk->rmid) == rmid;
 }
 
+/**
+ * resctrl_arch_set_cpu_kmode() - Set per-CPU kernel mode state for PLZA programming
+ * @cpu:	Logical CPU to update.
+ * @closid:	CLOSID to use for kernel work on this CPU when kmode is enabled.
+ * @rmid:	RMID to use for kernel work on this CPU when kmode is enabled.
+ * @enable:	1 to enable PLZA on this CPU; 0 to leave disabled. Stored in default_kmode.
+ *
+ * Stores the given CLOSID, RMID, and enable value in per-CPU state (kmode_closid,
+ * kmode_rmid, default_kmode). The actual MSR_IA32_PQR_PLZA_ASSOC write is done
+ * separately (e.g. via on_each_cpu_mask) so that closid/rmid are set on all CPUs
+ * in the domain before PLZA_EN is set, per the PLZA programming sequence.
+ */
+static inline void resctrl_arch_set_cpu_kmode(int cpu, u32 closid, u32 rmid, u32 enable)
+{
+	WRITE_ONCE(per_cpu(pqr_state.default_kmode, cpu), enable);
+	WRITE_ONCE(per_cpu(pqr_state.kmode_closid, cpu), closid);
+	WRITE_ONCE(per_cpu(pqr_state.kmode_rmid, cpu), rmid);
+}
+
 static inline void resctrl_arch_sched_in(struct task_struct *tsk)
 {
 	if (static_branch_likely(&rdt_enable_key))
diff --git a/arch/x86/kernel/cpu/resctrl/ctrlmondata.c b/arch/x86/kernel/cpu/resctrl/ctrlmondata.c
index b20e705606b8..b5dfe30aca26 100644
--- a/arch/x86/kernel/cpu/resctrl/ctrlmondata.c
+++ b/arch/x86/kernel/cpu/resctrl/ctrlmondata.c
@@ -131,3 +131,80 @@ int resctrl_arch_io_alloc_enable(struct rdt_resource *r, bool enable)
 
 	return 0;
 }
+
+/*
+ * IPI callback: write MSR_IA32_PQR_PLZA_ASSOC on this CPU (AMD PLZA).
+ */
+static void resctrl_kmode_set_one_amd(void *arg)
+{
+	union qos_pqr_plza_assoc *plza = arg;
+
+	wrmsrl(MSR_IA32_PQR_PLZA_ASSOC, plza->full);
+}
+
+/**
+ * resctrl_arch_configure_kmode() - x86/AMD: program PLZA per control domain
+ *
+ * For each control domain, first sets per-CPU state (closid, rmid, enable=0)
+ * on all CPUs in the domain, then writes MSR_IA32_PQR_PLZA_ASSOC on each CPU
+ * so that closid/closid_en (and optionally rmid/rmid_en) are programmed
+ * before PLZA_EN is set, per the PLZA programming sequence.
+ */
+void resctrl_arch_configure_kmode(struct rdt_resource *r, struct resctrl_kmode_cfg *kcfg,
+				  u32 closid, u32 rmid)
+{
+	union qos_pqr_plza_assoc plza = { 0 };
+	struct rdt_ctrl_domain *d;
+	int cpu;
+
+	if (kcfg->kmode_cur & INHERIT_CTRL_AND_MON)
+		return;
+
+	if (kcfg->kmode_cur & GLOBAL_ASSIGN_CTRL_ASSIGN_MON) {
+		plza.split.rmid = rmid;
+		plza.split.rmid_en = 1;
+	}
+	plza.split.closid = closid;
+	plza.split.closid_en = 1;
+
+	list_for_each_entry(d, &r->ctrl_domains, hdr.list) {
+		for_each_cpu(cpu, &d->hdr.cpu_mask)
+			resctrl_arch_set_cpu_kmode(cpu, closid, rmid, 0);
+		on_each_cpu_mask(&d->hdr.cpu_mask, resctrl_kmode_set_one_amd, &plza, 1);
+	}
+}
+
+/**
+ * resctrl_arch_set_kmode() - x86/AMD: set PLZA enable/disable on a set of CPUs
+ * @cpu_mask:	CPUs to update (e.g. a control domain's cpu_mask).
+ * @kcfg:	Current kernel mode configuration.
+ * @closid:	CLOSID to use for kernel work when a global assign mode is active.
+ * @rmid:	RMID to use for kernel work when GLOBAL_ASSIGN_CTRL_ASSIGN_MON is active.
+ * @enable:	True to set MSR_IA32_PQR_PLZA_ASSOC.PLZA_EN; false to clear it.
+ *
+ * Writes MSR_IA32_PQR_PLZA_ASSOC on each CPU in @cpu_mask (via IPI) and updates
+ * per-CPU state. No-op when kmode_cur is INHERIT_CTRL_AND_MON. Call after
+ * resctrl_arch_configure_kmode() so that closid/rmid are programmed before
+ * PLZA_EN is set.
+ */
+void resctrl_arch_set_kmode(cpumask_var_t cpu_mask, struct resctrl_kmode_cfg *kcfg,
+			    u32 closid, u32 rmid, bool enable)
+{
+	int cpu;
+	union qos_pqr_plza_assoc plza = { 0 };
+
+	if (kcfg->kmode_cur & INHERIT_CTRL_AND_MON)
+		return;
+
+	if (kcfg->kmode_cur & GLOBAL_ASSIGN_CTRL_ASSIGN_MON) {
+		plza.split.rmid = rmid;
+		plza.split.rmid_en = 1;
+	}
+	plza.split.closid = closid;
+	plza.split.closid_en = 1;
+	plza.split.plza_en = enable;
+
+	on_each_cpu_mask(cpu_mask, resctrl_kmode_set_one_amd, &plza, 1);
+	for_each_cpu(cpu, cpu_mask)
+		resctrl_arch_set_cpu_kmode(cpu, closid, rmid, enable);
+}
diff --git a/include/linux/resctrl.h b/include/linux/resctrl.h
index 2c36d1ac392f..3f3e8c1e549b 100644
--- a/include/linux/resctrl.h
+++ b/include/linux/resctrl.h
@@ -709,6 +709,36 @@ bool resctrl_arch_get_io_alloc_enabled(struct rdt_resource *r);
  */
 void resctrl_arch_get_kmode_cfg(struct resctrl_kmode_cfg *kcfg);
 
+/**
+ * resctrl_arch_configure_kmode() - Program kernel mode (e.g. PLZA) for all domains
+ * @r:          The resctrl resource (scope for control domains).
+ * @kcfg:       Current kernel mode configuration.
+ * @closid:     CLOSID to use for kernel work when a global assign mode is active.
+ * @rmid:       RMID to use for kernel work when GLOBAL_ASSIGN_CTRL_ASSIGN_MON is active.
+ *
+ * Programs each control domain so that kernel work uses the given CLOSID/RMID
+ * per the active kernel mode (e.g. MSR_IA32_PQR_PLZA_ASSOC on x86). No-op when
+ * kmode_cur is INHERIT_CTRL_AND_MON. May be called from any CPU.
+ */
+void resctrl_arch_configure_kmode(struct rdt_resource *r, struct resctrl_kmode_cfg *kcfg,
+				  u32 closid, u32 rmid);
+
+/**
+ * resctrl_arch_set_kmode() - Set kernel mode (e.g. PLZA) on a set of CPUs
+ * @cpu_mask:	CPUs to update (e.g. a control domain's cpu_mask).
+ * @kcfg:	Current kernel mode configuration.
+ * @closid:	CLOSID to use for kernel work when a global assign mode is active.
+ * @rmid:	RMID to use for kernel work when GLOBAL_ASSIGN_CTRL_ASSIGN_MON is active.
+ * @enable:	True to set MSR_IA32_PQR_PLZA_ASSOC.PLZA_EN on the CPUs; false to clear it.
+ *
+ * Writes MSR_IA32_PQR_PLZA_ASSOC on each CPU in @cpu_mask and updates per-CPU
+ * state. No-op when kmode_cur is INHERIT_CTRL_AND_MON. Call after
+ * resctrl_arch_configure_kmode() so that closid/rmid are programmed before
+ * PLZA_EN is set. May be called from any CPU.
+ */
+void resctrl_arch_set_kmode(cpumask_var_t cpu_mask, struct resctrl_kmode_cfg *kcfg,
+			    u32 closid, u32 rmid, bool enable);
+
 extern unsigned int resctrl_rmid_realloc_threshold;
 extern unsigned int resctrl_rmid_realloc_limit;

---

## [11] Babu Moger — 2026-03-12
*Subject: [PATCH v2 10/16] x86/resctrl: Add PLZA state tracking and context switch handling*

When kernel mode (e.g., PLZA) is enabled, the resctrl sched-in path must
program MSR_IA32_PQR_PLZA_ASSOC in addition to IA32_PQR_ASSOC.

Add resctrl_kmode_mon_en() to indicate whether kernel mode monitoring needs
to be enabled (GLOBAL_ASSIGN_CTRL_ASSIGN_MON). Task's kmode takes
precedence when kmode is enabled for that task; otherwise, fall back to the
per-CPU default_kmode. Write MSR_IA32_PQR_PLZA_ASSOC only when kmode is
changed.

Protect the PLZA path with rdt_kmode_enable_key to avoid overhead when
kmode is disabled.

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v2: Updated code comments.
    Added new function resctrl_kmode_mon_en() to check if kernel mode
    monitoring needs to be enabled.
---
 arch/x86/include/asm/resctrl.h | 33 +++++++++++++++++++++++++++++++++
 1 file changed, 33 insertions(+)

diff --git a/arch/x86/include/asm/resctrl.h b/arch/x86/include/asm/resctrl.h
index 167be18983c1..ccfd95b98bac 100644
--- a/arch/x86/include/asm/resctrl.h
+++ b/arch/x86/include/asm/resctrl.h
@@ -57,6 +57,9 @@ DECLARE_PER_CPU(struct resctrl_pqr_state, pqr_state);
 extern bool rdt_alloc_capable;
 extern bool rdt_mon_capable;
 
+/* Global kernel mode config; used by resctrl_kmode_mon_en(). */
+extern struct resctrl_kmode_cfg resctrl_kcfg;
+
 DECLARE_STATIC_KEY_FALSE(rdt_enable_key);
 DECLARE_STATIC_KEY_FALSE(rdt_alloc_enable_key);
 DECLARE_STATIC_KEY_FALSE(rdt_mon_enable_key);
@@ -108,6 +111,17 @@ static inline void resctrl_arch_disable_kmode(void)
 	static_branch_dec_cpuslocked(&rdt_enable_key);
 }
 
+/**
+ * resctrl_kmode_mon_en() - True when kernel mode requires RMID in PLZA MSR
+ *
+ * When GLOBAL_ASSIGN_CTRL_ASSIGN_MON is active, MSR_IA32_PQR_PLZA_ASSOC must
+ * program both CLOSID and RMID for kernel work; otherwise only CLOSID is used.
+ */
+static bool resctrl_kmode_mon_en(void)
+{
+	return resctrl_kcfg.kmode_cur & GLOBAL_ASSIGN_CTRL_ASSIGN_MON;
+}
+
 /*
  * __resctrl_sched_in() - Writes the task's CLOSid/RMID to IA32_PQR_MSR
  *
@@ -127,6 +141,7 @@ static inline void __resctrl_sched_in(struct task_struct *tsk)
 	struct resctrl_pqr_state *state = this_cpu_ptr(&pqr_state);
 	u32 closid = READ_ONCE(state->default_closid);
 	u32 rmid = READ_ONCE(state->default_rmid);
+	u32 kmode = READ_ONCE(state->default_kmode);
 	u32 tmp;
 
 	/*
@@ -150,6 +165,24 @@ static inline void __resctrl_sched_in(struct task_struct *tsk)
 		state->cur_rmid = rmid;
 		wrmsr(MSR_IA32_PQR_ASSOC, rmid, closid);
 	}
+
+	/*
+	 * When kernel mode (e.g. PLZA) is enabled, program MSR_IA32_PQR_PLZA_ASSOC.
+	 * Task's kmode overrides per-CPU default_kmode. Only write the MSR when
+	 * kmode has changed to avoid unnecessary writes on the scheduler hot path.
+	 */
+	if (static_branch_likely(&rdt_kmode_enable_key)) {
+		tmp = READ_ONCE(tsk->kmode);
+		if (tmp)
+			kmode = tmp;
+
+		if (kmode != state->cur_kmode) {
+			state->cur_kmode = kmode;
+			wrmsr(MSR_IA32_PQR_PLZA_ASSOC,
+			      resctrl_kmode_mon_en() ? (RMID_EN | state->kmode_rmid) : 0,
+			      (kmode ? PLZA_EN : 0) | (CLOSID_EN | state->kmode_closid));
+		}
+	}
 }
 
 static inline unsigned int resctrl_arch_round_mon_val(unsigned int val)

---

## [12] Babu Moger — 2026-03-12
*Subject: [PATCH v2 11/16] fs/resctrl: Add write handler for info/kernel_mode*

Add resctrl_kernel_mode_write() so users can set the current kernel
mode by writing a mode name to info/kernel_mode. Unsupported or invalid
names are rejected; errors are reported in info/last_cmd_status.

Add rdtgroup_config_kmode() to assign or clear a group for kernel mode
(e.g. PLZA), and extend struct rdtgroup with a kmode flag. Update
Documentation/filesystems/resctrl.rst to describe the kernel_mode file.

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v2: New patch to handle PLZA interfaces with /sys/fs/resctrl/info/ directory.
    https://lore.kernel.org/lkml/2ab556af-095b-422b-9396-f845c6fd0342@intel.com/
---
 Documentation/filesystems/resctrl.rst |  34 +++++++++
 fs/resctrl/internal.h                 |   2 +
 fs/resctrl/rdtgroup.c                 | 101 +++++++++++++++++++++++++-
 3 files changed, 136 insertions(+), 1 deletion(-)

diff --git a/Documentation/filesystems/resctrl.rst b/Documentation/filesystems/resctrl.rst
index ba609f8d4de5..2107dd4b3649 100644
--- a/Documentation/filesystems/resctrl.rst
+++ b/Documentation/filesystems/resctrl.rst
@@ -514,6 +514,40 @@ conveyed in the error returns from file operations. E.g.
 	# cat info/last_cmd_status
 	mask f7 has non-consecutive 1-bits
 
+"kernel_mode":
+	In the top level of the "info" directory, "kernel_mode" controls how
+	resource allocation and monitoring work in kernel mode. This is used on
+	some platforms to assign a dedicated CLOSID and/or RMID to kernel threads.
+
+	Reading the file lists supported kernel modes, one per line. The
+	currently active mode is shown in square brackets; other modes supported
+	by the platform are shown without brackets. Example::
+
+	  # cat info/kernel_mode
+	  [inherit_ctrl_and_mon]
+	  global_assign_ctrl_inherit_mon
+	  global_assign_ctrl_assign_mon
+
+	Writing a mode name (followed by a newline) sets the current kernel mode.
+	The name must match one of the supported mode names exactly. Modes not
+	supported by the platform (e.g. not advertised when reading the file)
+	cannot be set. Errors are reported in "info/last_cmd_status". Example::
+
+	  # echo "global_assign_ctrl_assign_mon" > info/kernel_mode
+	  # cat info/kernel_mode
+	  inherit_ctrl_and_mon
+	  global_assign_ctrl_inherit_mon
+	  [global_assign_ctrl_assign_mon]
+
+	Modes:
+
+	- "inherit_ctrl_and_mon": Kernel uses the same CLOSID and RMID as the
+	  current user-space task (default).
+	- "global_assign_ctrl_inherit_mon": One CLOSID is assigned for all
+	  kernel work; RMID is still inherited from user space.
+	- "global_assign_ctrl_assign_mon": One resource group (CLOSID and RMID)
+	  is assigned for all kernel work.
+
 Resource alloc and monitor groups
 =================================
 
diff --git a/fs/resctrl/internal.h b/fs/resctrl/internal.h
index 1a9b29119f88..b5999d8079d6 100644
--- a/fs/resctrl/internal.h
+++ b/fs/resctrl/internal.h
@@ -216,6 +216,7 @@ struct mongroup {
  * @mon:			mongroup related data
  * @mode:			mode of resource group
  * @mba_mbps_event:		input monitoring event id when mba_sc is enabled
+ * @kmode:			true if this group is assigned for kernel mode (e.g. PLZA)
  * @plr:			pseudo-locked region
  */
 struct rdtgroup {
@@ -229,6 +230,7 @@ struct rdtgroup {
 	struct mongroup			mon;
 	enum rdtgrp_mode		mode;
 	enum resctrl_event_id		mba_mbps_event;
+	bool				kmode;
 	struct pseudo_lock_region	*plr;
 };
 
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index bb775afc78f5..6cd928fabaa2 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -1019,6 +1019,104 @@ static int resctrl_kernel_mode_show(struct kernfs_open_file *of,
 	return 0;
 }
 
+/**
+ * rdtgroup_config_kmode() - Enable or disable kernel mode (e.g. PLZA) for a group
+ * @rdtgrp:	The rdtgroup to assign or unassign for kernel work.
+ * @enable:	True to assign this group for kernel mode; false to clear.
+ *
+ * Programs arch state via resctrl_arch_configure_kmode() and
+ * resctrl_arch_set_kmode(), and updates resctrl_kcfg.k_rdtgrp. Only one group
+ * may have kmode at a time. Pseudo-locked groups cannot be used for kernel mode.
+ *
+ * Return: 0 on success, or -EINVAL if the group is pseudo-locked.
+ */
+static int rdtgroup_config_kmode(struct rdtgroup *rdtgrp, bool enable)
+{
+	struct rdt_resource *r = resctrl_arch_get_resource(RDT_RESOURCE_L3);
+	u32 closid;
+
+	if (rdtgrp->mode == RDT_MODE_PSEUDO_LOCKED) {
+		rdt_last_cmd_puts("Resource group is pseudo-locked\n");
+		return -EINVAL;
+	}
+
+	if (rdtgrp->type == RDTMON_GROUP)
+		closid = rdtgrp->mon.parent->closid;
+	else
+		closid = rdtgrp->closid;
+
+	resctrl_arch_configure_kmode(r, &resctrl_kcfg, closid, rdtgrp->mon.rmid);
+
+	resctrl_arch_set_kmode(&rdtgrp->cpu_mask, &resctrl_kcfg, closid,
+			       rdtgrp->mon.rmid, enable);
+	rdtgrp->kmode = enable;
+	if (enable)
+		resctrl_kcfg.k_rdtgrp = rdtgrp;
+	else
+		resctrl_kcfg.k_rdtgrp = NULL;
+
+	return 0;
+}
+
+/**
+ * resctrl_kernel_mode_write() - Set current kernel mode via info/kernel_mode
+ * @of:	kernfs file handle.
+ * @buf:	Mode name string (e.g. "inherit_ctrl_and_mon"); must end with newline.
+ * @nbytes:	Length of buf.
+ * @off:	File offset (unused).
+ *
+ * Accepts one of the names in kmodes[]. The mode must be supported by the
+ * platform (resctrl_kcfg.kmode). On success updates resctrl_kcfg.kmode_cur.
+ * Errors are reported in last_cmd_status.
+ *
+ * Return: nbytes on success, or -EINVAL with last_cmd_status set on error.
+ */
+static ssize_t resctrl_kernel_mode_write(struct kernfs_open_file *of,
+					 char *buf, size_t nbytes, loff_t off)
+{
+	int ret = 0;
+	u32 kmode;
+	int i;
+
+	if (nbytes == 0 || buf[nbytes - 1] != '\n')
+		return -EINVAL;
+	buf[nbytes - 1] = '\0';
+
+	mutex_lock(&rdtgroup_mutex);
+	rdt_last_cmd_clear();
+
+	for (i = 0; i < RESCTRL_KERNEL_MODES_NUM; i++) {
+		if (strcmp(buf, kmodes[i].name) != 0)
+			continue;
+		/* Mode name matched; reject if not supported by this platform. */
+		if (!(resctrl_kcfg.kmode & kmodes[i].val)) {
+			rdt_last_cmd_puts("Kernel mode not available\n");
+			ret = -EINVAL;
+			goto out_unlock;
+		}
+		if (resctrl_kcfg.kmode_cur != kmodes[i].val) {
+			kmode = resctrl_kcfg.kmode_cur;
+			resctrl_kcfg.kmode_cur = kmodes[i].val;
+			if (resctrl_kcfg.k_rdtgrp) {
+				ret = rdtgroup_config_kmode(resctrl_kcfg.k_rdtgrp, true);
+				if (ret) {
+					/* Revert to the previous mode. */
+					resctrl_kcfg.kmode_cur = kmode;
+					rdt_last_cmd_puts("Kernel mode change failed\n");
+				}
+			}
+			goto out_unlock;
+		}
+	}
+
+	rdt_last_cmd_puts("Unknown or unsupported kernel mode\n");
+	ret = -EINVAL;
+
+out_unlock:
+	mutex_unlock(&rdtgroup_mutex);
+	return ret ?: nbytes;
+}
+
 void *rdt_kn_parent_priv(struct kernfs_node *kn)
 {
 	/*
@@ -1922,9 +2020,10 @@ static struct rftype res_common_files[] = {
 	},
 	{
 		.name		= "kernel_mode",
-		.mode		= 0444,
+		.mode		= 0644,
 		.kf_ops		= &rdtgroup_kf_single_ops,
 		.seq_show	= resctrl_kernel_mode_show,
+		.write		= resctrl_kernel_mode_write,
 		.fflags		= RFTYPE_TOP_INFO,
 	},
 	{

---

## [13] Babu Moger — 2026-03-12
*Subject: [PATCH v2 12/16] fs/resctrl: Add info/kernel_mode_assignment to show kernel-mode rdtgroup*

Add the interface info/kernel_mode_assignment file to show the rdtgroup
enabled for kernel mode (e.g. PLZA).

The assigned rdtgroup list is printed in following format:

       "<CTRL_MON group>/<MON group>/"

       Format for specific type of groups:

       * Default CTRL_MON group:
	 "//"

       * Non-default CTRL_MON group:
         "<CTRL_MON group>//"

       * Child MON group of default CTRL_MON group:
         "/<MON group>/"

       * Child MON group of non-default CTRL_MON group:
               "<CTRL_MON group>/<MON group>/"

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v2: New patch to handle PLZA interfaces with /sys/fs/resctrl/info/ directory.
    https://lore.kernel.org/lkml/2ab556af-095b-422b-9396-f845c6fd0342@intel.com/
---
 fs/resctrl/rdtgroup.c | 46 +++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 46 insertions(+)

diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index 6cd928fabaa2..c2d6d1995dff 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -1117,6 +1117,45 @@ static ssize_t resctrl_kernel_mode_write(struct kernfs_open_file *of,
 	return ret ?: nbytes;
 }
 
+/**
+ * resctrl_kernel_mode_assignment_show() - Show rdtgroup assigned to kernel mode
+ * @of:	kernfs file handle.
+ * @s:	seq_file to write to.
+ * @v:	unused.
+ *
+ * Prints the rdtgroup (resctrl_kcfg.k_rdtgrp) used for kernel work when a
+ * kernel mode is active (e.g. PLZA).
+ * Format: "CTRL_MON/MON/\n"
+ * "//" for default CTRL_MON,
+ * "ctrl_name//" for a CTRL_MON group,
+ * "/mon_name/" for a MON group under default,
+ * "ctrl_name/mon_name/" otherwise.
+ *
+ * Prints "Kmode is not configured" if no rdtgroup is assigned.
+ */
+static int resctrl_kernel_mode_assignment_show(struct kernfs_open_file *of,
+					       struct seq_file *s, void *v)
+{
+	mutex_lock(&rdtgroup_mutex);
+	if (!resctrl_kcfg.k_rdtgrp) {
+		seq_puts(s, "Kmode is not configured");
+	} else if (resctrl_kcfg.k_rdtgrp == &rdtgroup_default) {
+		seq_puts(s, "//");
+	} else if (resctrl_kcfg.k_rdtgrp->type == RDTCTRL_GROUP) {
+		seq_printf(s, "%s//", rdt_kn_name(resctrl_kcfg.k_rdtgrp->kn));
+	} else if (resctrl_kcfg.k_rdtgrp->type == RDTMON_GROUP) {
+		if (resctrl_kcfg.k_rdtgrp->mon.parent == &rdtgroup_default)
+			seq_printf(s, "/%s/", rdt_kn_name(resctrl_kcfg.k_rdtgrp->kn));
+		else
+			seq_printf(s, "%s/%s/",
+				   rdt_kn_name(resctrl_kcfg.k_rdtgrp->mon.parent->kn),
+				   rdt_kn_name(resctrl_kcfg.k_rdtgrp->kn));
+	}
+	seq_puts(s, "\n");
+	mutex_unlock(&rdtgroup_mutex);
+	return 0;
+}
+
 void *rdt_kn_parent_priv(struct kernfs_node *kn)
 {
 	/*
@@ -2026,6 +2065,13 @@ static struct rftype res_common_files[] = {
 		.write		= resctrl_kernel_mode_write,
 		.fflags		= RFTYPE_TOP_INFO,
 	},
+	{
+		.name		= "kernel_mode_assignment",
+		.mode		= 0444,
+		.kf_ops		= &rdtgroup_kf_single_ops,
+		.seq_show	= resctrl_kernel_mode_assignment_show,
+		.fflags		= RFTYPE_TOP_INFO,
+	},
 	{
 		.name		= "mbm_assign_on_mkdir",
 		.mode		= 0644,

---

## [14] Babu Moger — 2026-03-12
*Subject: [PATCH v2 13/16] fs/resctrl: Add write interface for kernel_mode_assignment*

Allow enabling kernel mode assignment (PLZA) for resctrl groups via the
kernel_mode_assignment sysfs file. Add a kmode flag to struct rdtgroup to
track the state, enforce that only one group has PLZA at a time, and clear
kmode when groups are removed or during rmdir_all_sub teardown.

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v2: New patch to handle PLZA interfaces with /sys/fs/resctrl/info/ directory.
    https://lore.kernel.org/lkml/2ab556af-095b-422b-9396-f845c6fd0342@intel.com/
---
 Documentation/filesystems/resctrl.rst |  35 ++++++
 fs/resctrl/rdtgroup.c                 | 148 +++++++++++++++++++++++++-
 2 files changed, 182 insertions(+), 1 deletion(-)

diff --git a/Documentation/filesystems/resctrl.rst b/Documentation/filesystems/resctrl.rst
index 2107dd4b3649..2b4beedd7207 100644
--- a/Documentation/filesystems/resctrl.rst
+++ b/Documentation/filesystems/resctrl.rst
@@ -548,6 +548,41 @@ conveyed in the error returns from file operations. E.g.
 	- "global_assign_ctrl_assign_mon": One resource group (CLOSID and RMID)
 	  is assigned for all kernel work.
 
+"kernel_mode_assignment":
+	In the top level of the "info" directory, "kernel_mode_assignment" shows
+	and (when a global-assign kernel mode is active) sets which resctrl group
+	is used for kernel mode. It is only relevant when "kernel_mode" is not
+        "inherit_ctrl_and_mon".
+
+	Reading the file shows the currently assigned group in the form
+	"CTRL_MON/MON/" with a newline::
+
+	  # cat info/kernel_mode_assignment
+	  //
+
+	Possible read formats:
+
+	- "//": Default CTRL_MON group is assigned.
+	- "ctrl_name//": A CTRL_MON group named "ctrl_name" is assigned.
+	- "/mon_name/": A MON group named "mon_name" under the default CTRL_MON
+	  group is assigned.
+	- "ctrl_name/mon_name/": A MON group named "mon_name" under the CTRL_MON
+	  group "ctrl_name" is assigned.
+	- "Kmode is not configured": No group is assigned for kernel mode.
+
+	Writing assigns a group for kernel mode. The write is only allowed when
+	the current kernel mode is not "inherit_ctrl_and_mon". Input format is
+	one or more lines, each of the form "CTRL_MON/MON/" (same as the read
+	format). Examples::
+
+	  # echo "//" > info/kernel_mode_assignment
+	  # echo "mydir//" > info/kernel_mode_assignment
+	  # echo "mydir/mon1/" > info/kernel_mode_assignment
+
+	An empty write (e.g. ``echo >> info/kernel_mode_assignment``) clears the
+	assignment. Only one group can be assigned at a time. Pseudo-locked
+	groups cannot be assigned. Errors are reported in "info/last_cmd_status".
+
 Resource alloc and monitor groups
 =================================
 
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index c2d6d1995dff..23e610d59111 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -1156,6 +1156,137 @@ static int resctrl_kernel_mode_assignment_show(struct kernfs_open_file *of,
 	return 0;
 }
 
+/**
+ * rdtgroup_find_grp_by_name() - Find an rdtgroup by type and parent/child names
+ * @rtype:	RDTCTRL_GROUP or RDTMON_GROUP.
+ * @p_grp:	Parent CTRL_MON group name, or "" for the default group.
+ * @c_grp:	Child MON group name (only used when rtype is RDTMON_GROUP).
+ *
+ * Return: The rdtgroup, or NULL if not found.
+ */
+static struct rdtgroup *rdtgroup_find_grp_by_name(enum rdt_group_type rtype,
+						  char *p_grp, char *c_grp)
+{
+	struct rdtgroup *rdtg, *crg;
+
+	if (rtype == RDTCTRL_GROUP && *p_grp == '\0') {
+		return &rdtgroup_default;
+	} else if (rtype == RDTCTRL_GROUP) {
+		list_for_each_entry(rdtg, &rdt_all_groups, rdtgroup_list)
+			if (rdtg->type == RDTCTRL_GROUP && !strcmp(p_grp, rdtg->kn->name))
+				return rdtg;
+	} else if (rtype == RDTMON_GROUP) {
+		list_for_each_entry(rdtg, &rdt_all_groups, rdtgroup_list) {
+			if (rdtg->type == RDTCTRL_GROUP && !strcmp(p_grp, rdtg->kn->name)) {
+				list_for_each_entry(crg, &rdtg->mon.crdtgrp_list,
+						    mon.crdtgrp_list) {
+					if (!strcmp(c_grp, crg->kn->name))
+						return crg;
+				}
+			}
+		}
+	}
+
+	return NULL;
+}
+
+/**
+ * resctrl_kernel_mode_assignment_write() - Set rdtgroup for kernel mode via info file
+ * @of:	kernfs file handle.
+ * @buf:	Input: "CTRL_MON/MON/" per line (e.g. "//" for default,
+ *		"ctrl1//" or "ctrl1/mon1/"); empty string clears the assignment.
+ * @nbytes:	Length of buf.
+ * @off:	File offset (unused).
+ *
+ * Only valid when kernel mode is not inherit_ctrl_and_mon. Empty write clears
+ * the current assignment. Parses lines as "parent/child/"; empty child means
+ * CTRL_MON group. Errors are reported in last_cmd_status.
+ *
+ * Return: nbytes on success, or -EINVAL with last_cmd_status set on error.
+ */
+static ssize_t resctrl_kernel_mode_assignment_write(struct kernfs_open_file *of,
+						    char *buf, size_t nbytes, loff_t off)
+{
+	struct rdtgroup *rdtgrp;
+	char *token, *cmon_grp, *mon_grp;
+	enum rdt_group_type rtype;
+	int ret = 0;
+
+	if (nbytes == 0 || buf[nbytes - 1] != '\n')
+		return -EINVAL;
+	buf[nbytes - 1] = '\0';
+	buf = strim(buf);
+
+	mutex_lock(&rdtgroup_mutex);
+	rdt_last_cmd_clear();
+
+	if (resctrl_kcfg.kmode_cur & INHERIT_CTRL_AND_MON) {
+		rdt_last_cmd_puts("Cannot change kmode in inherit_ctrl_and_mon\n");
+		ret = -EINVAL;
+		goto out_unlock;
+	}
+
+	/*
+	 * Group can be deleted from Kmode by empty write: e.g.
+	 * "echo >> /sys/fs/resctrl/info/kernel_mode_assignment"
+	 */
+	if (*buf == '\0') {
+		if (resctrl_kcfg.k_rdtgrp) {
+			ret = rdtgroup_config_kmode(resctrl_kcfg.k_rdtgrp, false);
+			if (ret)
+				rdt_last_cmd_printf("Kernel mode disable failed on group %s\n",
+						    rdt_kn_name(resctrl_kcfg.k_rdtgrp->kn));
+		}
+		goto out_unlock;
+	}
+
+	/* Only one group can be assigned for kernel mode at a time. */
+	if (resctrl_kcfg.k_rdtgrp) {
+		rdt_last_cmd_printf("Kernel mode already configured on group %s\n",
+				    rdt_kn_name(resctrl_kcfg.k_rdtgrp->kn));
+		ret = -EINVAL;
+		goto out_unlock;
+	}
+
+	while ((token = strsep(&buf, "\n")) != NULL) {
+		/*
+		 * Each line has the format "<CTRL_MON group>/<MON group>/".
+		 * Extract the CTRL_MON group name.
+		 */
+		cmon_grp = strsep(&token, "/");
+
+		/*
+		 * Extract the MON_GROUP.
+		 * strsep returns empty string for contiguous delimiters.
+		 * Empty mon_grp here means it is a RDTCTRL_GROUP.
+		 */
+		mon_grp = strsep(&token, "/");
+
+		if (*mon_grp == '\0')
+			rtype = RDTCTRL_GROUP;
+		else
+			rtype = RDTMON_GROUP;
+
+		rdtgrp = rdtgroup_find_grp_by_name(rtype, cmon_grp, mon_grp);
+
+		if (!rdtgrp) {
+			rdt_last_cmd_puts("Not a valid resctrl group\n");
+			ret = -EINVAL;
+			goto out_unlock;
+		}
+
+		if (!rdtgrp->kmode) {
+			ret = rdtgroup_config_kmode(rdtgrp, true);
+			if (ret)
+				break;
+		}
+	}
+
+out_unlock:
+	mutex_unlock(&rdtgroup_mutex);
+	return ret ?: nbytes;
+}
+
 void *rdt_kn_parent_priv(struct kernfs_node *kn)
 {
 	/*
@@ -2067,9 +2198,10 @@ static struct rftype res_common_files[] = {
 	},
 	{
 		.name		= "kernel_mode_assignment",
-		.mode		= 0444,
+		.mode		= 0644,
 		.kf_ops		= &rdtgroup_kf_single_ops,
 		.seq_show	= resctrl_kernel_mode_assignment_show,
+		.write		= resctrl_kernel_mode_assignment_write,
 		.fflags		= RFTYPE_TOP_INFO,
 	},
 	{
@@ -3248,6 +3380,10 @@ static void rmdir_all_sub(void)
 	rdt_move_group_tasks(NULL, &rdtgroup_default, NULL);
 
 	list_for_each_entry_safe(rdtgrp, tmp, &rdt_all_groups, rdtgroup_list) {
+		/* Disable Kmode if configured */
+		if (rdtgrp->kmode)
+			rdtgroup_config_kmode(rdtgrp, false);
+
 		/* Free any child rmids */
 		free_all_child_rdtgrp(rdtgrp);
 
@@ -3358,6 +3494,8 @@ static void resctrl_fs_teardown(void)
 	mon_put_kn_priv();
 	rdt_pseudo_lock_release();
 	rdtgroup_default.mode = RDT_MODE_SHAREABLE;
+	resctrl_kcfg.k_rdtgrp = NULL;
+	resctrl_kcfg.kmode_cur = INHERIT_CTRL_AND_MON;
 	closid_exit();
 	schemata_list_destroy();
 	rdtgroup_destroy_root();
@@ -4156,6 +4294,10 @@ static int rdtgroup_rmdir_mon(struct rdtgroup *rdtgrp, cpumask_var_t tmpmask)
 	u32 closid, rmid;
 	int cpu;
 
+	/* Disable Kmode if configured */
+	if (rdtgrp->kmode)
+		rdtgroup_config_kmode(rdtgrp, false);
+
 	/* Give any tasks back to the parent group */
 	rdt_move_group_tasks(rdtgrp, prdtgrp, tmpmask);
 
@@ -4206,6 +4348,10 @@ static int rdtgroup_rmdir_ctrl(struct rdtgroup *rdtgrp, cpumask_var_t tmpmask)
 	u32 closid, rmid;
 	int cpu;
 
+	/* Disable Kmode if configured */
+	if (rdtgrp->kmode)
+		rdtgroup_config_kmode(rdtgrp, false);
+
 	/* Give any tasks back to the default group */
 	rdt_move_group_tasks(rdtgrp, &rdtgroup_default, tmpmask);

---

## [15] Babu Moger — 2026-03-12
*Subject: [PATCH v2 14/16] fs/resctrl: Update kmode configuration when cpu_mask changes*

When kernel mode (e.g. PLZA) is active for a resctrl group, per-CPU
state must stay in sync with the group's cpu_mask. If the user
changes the cpus file, we must enable kmode on newly added CPUs and
disable it on CPUs that left the group.

Add cpus_write_kmode(), which calls cpus_ctrl_write_kmode() for
CTRL_MON groups and cpus_mon_write_kmode() for MON groups.

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v2: Fixed few typos in commit message.
    Added separate functions to handle kmode configuration for CTRL_MON and MON groups.
---
 fs/resctrl/rdtgroup.c | 149 +++++++++++++++++++++++++++++++++++++++++-
 1 file changed, 148 insertions(+), 1 deletion(-)

diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index 23e610d59111..31479893633a 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -456,6 +456,150 @@ static void cpumask_rdtgrp_clear(struct rdtgroup *r, struct cpumask *m)
 		cpumask_and(&crgrp->cpu_mask, &r->cpu_mask, &crgrp->cpu_mask);
 }
 
+/**
+ * cpus_mon_write_kmode() - Update per-CPU kmode when a MON group's cpu_mask changes
+ * @rdtgrp:	The MON group whose cpu_mask is being updated.
+ * @newmask:	The new CPU mask requested by the user.
+ * @tmpmask:	Temporary mask for computing CPU set differences.
+ *
+ * When CPUs are dropped from the group, disables kmode on those CPUs and
+ * returns them to the parent. When CPUs are added, removes them from sibling
+ * MON groups and enables kmode on them. Caller must hold rdtgroup_mutex.
+ *
+ * Return: 0 on success, or -EINVAL if newmask contains CPUs outside the parent.
+ */
+static int cpus_mon_write_kmode(struct rdtgroup *rdtgrp, cpumask_var_t newmask,
+				cpumask_var_t tmpmask)
+{
+	struct rdtgroup *prgrp = rdtgrp->mon.parent, *crgrp;
+	struct list_head *head;
+
+	/* Check whether cpus belong to parent ctrl group */
+	cpumask_andnot(tmpmask, newmask, &prgrp->cpu_mask);
+	if (!cpumask_empty(tmpmask)) {
+		rdt_last_cmd_puts("Can only add CPUs to mongroup that belong to parent\n");
+		return -EINVAL;
+	}
+
+	/* Check whether cpus are dropped from this group */
+	cpumask_andnot(tmpmask, &rdtgrp->cpu_mask, newmask);
+	if (!cpumask_empty(tmpmask)) {
+		/* Give any dropped cpus to parent rdtgroup */
+		cpumask_or(&prgrp->cpu_mask, &prgrp->cpu_mask, tmpmask);
+
+		/* Disable kmode on the dropped CPUs */
+		resctrl_arch_set_kmode(tmpmask, &resctrl_kcfg, prgrp->closid,
+				       rdtgrp->mon.rmid, false);
+	}
+
+	/*
+	 * If we added cpus, remove them from previous group that owned them
+	 * and enable kmode on added CPUs.
+	 */
+	cpumask_andnot(tmpmask, newmask, &rdtgrp->cpu_mask);
+	if (!cpumask_empty(tmpmask)) {
+		head = &prgrp->mon.crdtgrp_list;
+		list_for_each_entry(crgrp, head, mon.crdtgrp_list) {
+			if (crgrp == rdtgrp)
+				continue;
+			cpumask_andnot(&crgrp->cpu_mask, &crgrp->cpu_mask, tmpmask);
+		}
+		resctrl_arch_set_kmode(tmpmask, &resctrl_kcfg, prgrp->closid,
+				       rdtgrp->mon.rmid, true);
+	}
+
+	/* Done pushing/pulling - update this group with new mask */
+	cpumask_copy(&rdtgrp->cpu_mask, newmask);
+
+	return 0;
+}
+
+/**
+ * cpus_ctrl_write_kmode() - Update per-CPU kmode when a CTRL group's cpu_mask changes
+ * @rdtgrp:	The CTRL_MON group whose cpu_mask is being updated.
+ * @newmask:	The new CPU mask requested by the user.
+ * @tmpmask:	Temporary mask for computing CPU set differences.
+ * @tmpmask1:	Second temporary mask (e.g. for cpumask_rdtgrp_clear).
+ *
+ * When CPUs are dropped from the group, disables kmode on those CPUs (cannot
+ * drop from default group). When CPUs are added, clears them from child groups
+ * that owned them and enables kmode on them. Updates this group's cpu_mask and
+ * intersects child MON group masks with the new parent mask. Caller must hold
+ * rdtgroup_mutex.
+ *
+ * Return: 0 on success, or -EINVAL if dropping CPUs from the default group.
+ */
+static int cpus_ctrl_write_kmode(struct rdtgroup *rdtgrp, cpumask_var_t newmask,
+				 cpumask_var_t tmpmask, cpumask_var_t tmpmask1)
+{
+	struct rdtgroup *crgrp;
+	struct list_head *head;
+
+	/* Check whether cpus are dropped from this group */
+	cpumask_andnot(tmpmask, &rdtgrp->cpu_mask, newmask);
+	if (!cpumask_empty(tmpmask)) {
+		/* Can't drop from default group */
+		if (rdtgrp == &rdtgroup_default) {
+			rdt_last_cmd_puts("Can't drop CPUs from default group\n");
+			return -EINVAL;
+		}
+		/* Disable kmode on the dropped CPUs */
+		resctrl_arch_set_kmode(tmpmask, &resctrl_kcfg, rdtgrp->closid,
+				       rdtgrp->mon.rmid, false);
+	}
+
+	/*
+	 * If we added cpus, remove them from child groups that owned them
+	 * previously.
+	 */
+	cpumask_andnot(tmpmask, newmask, &rdtgrp->cpu_mask);
+	if (!cpumask_empty(tmpmask)) {
+		cpumask_rdtgrp_clear(rdtgrp, tmpmask1);
+		/* Enable kmode on the added CPUs */
+		resctrl_arch_set_kmode(tmpmask, &resctrl_kcfg, rdtgrp->closid,
+				       rdtgrp->mon.rmid, true);
+	}
+
+	/* Done pushing/pulling - update this group with new mask */
+	cpumask_copy(&rdtgrp->cpu_mask, newmask);
+
+	/* Clear child mon group masks since there is a new parent mask now */
+	head = &rdtgrp->mon.crdtgrp_list;
+	list_for_each_entry(crgrp, head, mon.crdtgrp_list) {
+		cpumask_and(tmpmask, &rdtgrp->cpu_mask, &crgrp->cpu_mask);
+	}
+
+	return 0;
+}
+
+/**
+ * cpus_write_kmode() - Update per-CPU kmode for a group's new cpu_mask
+ * @rdtgrp:	The group (CTRL_MON or MON) whose cpu_mask is being updated.
+ * @newmask:	The new CPU mask requested by the user.
+ * @tmpmask:	Temporary mask for computing CPU set differences.
+ * @tmpmask1:	Second temporary mask (only used for CTRL_MON groups).
+ *
+ * Dispatches to cpus_ctrl_write_kmode() or cpus_mon_write_kmode() based on
+ * group type. Used when the group has kmode enabled and the user writes to
+ * the cpus file.
+ *
+ * Return: 0 on success, or -EINVAL on error.
+ */
+static int cpus_write_kmode(struct rdtgroup *rdtgrp, cpumask_var_t newmask,
+			    cpumask_var_t tmpmask, cpumask_var_t tmpmask1)
+{
+	int ret;
+
+	if (rdtgrp->type == RDTCTRL_GROUP)
+		ret = cpus_ctrl_write_kmode(rdtgrp, newmask, tmpmask, tmpmask1);
+	else if (rdtgrp->type == RDTMON_GROUP)
+		ret = cpus_mon_write_kmode(rdtgrp, newmask, tmpmask);
+	else
+		ret = -EINVAL;
+
+	return ret;
+}
+
 static int cpus_ctrl_write(struct rdtgroup *rdtgrp, cpumask_var_t newmask,
 			   cpumask_var_t tmpmask, cpumask_var_t tmpmask1)
 {
@@ -566,7 +710,10 @@ static ssize_t rdtgroup_cpus_write(struct kernfs_open_file *of,
 		goto unlock;
 	}
 
-	if (rdtgrp->type == RDTCTRL_GROUP)
+	/* Group has kernel mode: update per-CPU kmode state for new mask. */
+	if (rdtgrp->kmode)
+		ret = cpus_write_kmode(rdtgrp, newmask, tmpmask, tmpmask1);
+	else if (rdtgrp->type == RDTCTRL_GROUP)
 		ret = cpus_ctrl_write(rdtgrp, newmask, tmpmask, tmpmask1);
 	else if (rdtgrp->type == RDTMON_GROUP)
 		ret = cpus_mon_write(rdtgrp, newmask, tmpmask);

---

## [16] Babu Moger — 2026-03-12
*Subject: [PATCH v2 15/16] x86/resctrl: Refactor show_rdt_tasks() to support PLZA tasks*

Refactor show_rdt_tasks() to use a new rdt_task_match() helper that checks
t->kmode when kmode (e.g. PLZA) is enabled for a group, falling back to
CLOSID/RMID matching otherwise. This ensures correct task display for
PLZA-enabled groups.

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v2: Added more code comments for clarity.
---
 fs/resctrl/rdtgroup.c | 39 ++++++++++++++++++++++++++++++++++-----
 1 file changed, 34 insertions(+), 5 deletions(-)

diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index 31479893633a..b41e681f6922 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -966,6 +966,34 @@ static ssize_t rdtgroup_tasks_write(struct kernfs_open_file *of,
 	return ret ?: nbytes;
 }
 
+/**
+ * rdt_task_match() - Decide if a task belongs to an rdtgroup for display
+ * @t:		Task to check.
+ * @r:		Rdtgroup (for CLOSID/RMID matching when not kmode).
+ * @kmode:	True if @r has kernel mode (e.g. PLZA) enabled.
+ *
+ * When @kmode is true, matches tasks that have kernel mode set (they are
+ * associated with this group via PLZA). Otherwise matches by CLOSID or RMID.
+ *
+ * Return: true if @t should be shown as belonging to @r.
+ */
+static inline bool rdt_task_match(struct task_struct *t,
+				  struct rdtgroup *r, bool kmode)
+{
+	if (kmode)
+		return t->kmode;
+
+	return is_closid_match(t, r) || is_rmid_match(t, r);
+}
+
+/**
+ * show_rdt_tasks() - List task PIDs that belong to the rdtgroup
+ * @r:		Rdtgroup whose tasks to list.
+ * @s:		seq_file to write PIDs to.
+ *
+ * Uses rdt_task_match() so that when the group has kernel mode (e.g. PLZA)
+ * enabled, tasks are matched by t->kmode; otherwise by CLOSID/RMID.
+ */
 static void show_rdt_tasks(struct rdtgroup *r, struct seq_file *s)
 {
 	struct task_struct *p, *t;
@@ -973,11 +1001,12 @@ static void show_rdt_tasks(struct rdtgroup *r, struct seq_file *s)
 
 	rcu_read_lock();
 	for_each_process_thread(p, t) {
-		if (is_closid_match(t, r) || is_rmid_match(t, r)) {
-			pid = task_pid_vnr(t);
-			if (pid)
-				seq_printf(s, "%d\n", pid);
-		}
+		if (!rdt_task_match(t, r, r->kmode))
+			continue;
+
+		pid = task_pid_vnr(t);
+		if (pid)
+			seq_printf(s, "%d\n", pid);
 	}
 	rcu_read_unlock();
 }

---

## [17] Babu Moger — 2026-03-12
*Subject: [PATCH v2 16/16] fs/resctrl: Add per-task kmode enable support via rdtgroup*

Introduce support for enabling kmode on a per-task basis through the
resctrl control-group interface.

Add an architecture helper to set the kmode state in the task structure and
extend the rdtgroup task handling path to apply kmode (e.g. PLZA) when
associating a task with a CTRL_MON or MON group.

Proper memory ordering is enforced to ensure that task closid and rmid
updates are visible before determining whether the task is currently
running. If the task is active on a CPU, the relevant MSRs are updated
immediately; otherwise, PLZA state is programmed on the next context
switch.

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v2: Few name changes to refer PLZA as kmode.
---
 arch/x86/include/asm/resctrl.h | 13 +++++
 fs/resctrl/rdtgroup.c          | 98 +++++++++++++++++++++++++++++++++-
 2 files changed, 110 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/resctrl.h b/arch/x86/include/asm/resctrl.h
index ccfd95b98bac..f48d1279e33d 100644
--- a/arch/x86/include/asm/resctrl.h
+++ b/arch/x86/include/asm/resctrl.h
@@ -238,6 +238,19 @@ static inline void resctrl_arch_set_cpu_kmode(int cpu, u32 closid, u32 rmid, u32
 	WRITE_ONCE(per_cpu(pqr_state.kmode_rmid, cpu), rmid);
 }
 
+/**
+ * resctrl_arch_set_task_kmode() - Set per-task kernel mode (e.g. PLZA) flag
+ * @tsk:	Task to update.
+ * @enable:	1 to enable kmode for this task; 0 to disable.
+ *
+ * When enabled, the task will use the group's CLOSID/RMID for kernel mode
+ * on context switch (see __resctrl_sched_in()).
+ */
+static inline void resctrl_arch_set_task_kmode(struct task_struct *tsk, u32 enable)
+{
+	WRITE_ONCE(tsk->kmode, enable);
+}
+
 static inline void resctrl_arch_sched_in(struct task_struct *tsk)
 {
 	if (static_branch_likely(&rdt_enable_key))
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index b41e681f6922..74fc942e6a4e 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -827,6 +827,31 @@ static int __rdtgroup_move_task(struct task_struct *tsk,
 	return 0;
 }
 
+/**
+ * __rdtgroup_task_kmode() - Enable kernel mode (e.g. PLZA) for a single task
+ * @tsk:	Task to enable kmode for.
+ * @rdtgrp:	Rdtgroup with kmode enabled (used for context; CLOSID/RMID applied on sched-in).
+ *
+ * Sets t->kmode so that the task uses the group's CLOSID/RMID on context
+ * switch. Memory ordering ensures the store is visible before we check if
+ * the task is current (and thus before any sched-in that may observe it).
+ *
+ * Return: 0.
+ */
+static int __rdtgroup_task_kmode(struct task_struct *tsk, struct rdtgroup *rdtgrp)
+{
+	resctrl_arch_set_task_kmode(tsk, true);
+
+	/*
+	 * Order the task's kmode state stores above before the loads in
+	 * task_curr(). This pairs with the full barrier between the
+	 * rq->curr update and resctrl_arch_sched_in() during context switch.
+	 */
+	smp_mb();
+
+	return 0;
+}
+
 static bool is_closid_match(struct task_struct *t, struct rdtgroup *r)
 {
 	return (resctrl_arch_alloc_capable() && (r->type == RDTCTRL_GROUP) &&
@@ -916,6 +941,48 @@ static int rdtgroup_move_task(pid_t pid, struct rdtgroup *rdtgrp,
 	return ret;
 }
 
+/**
+ * rdtgroup_task_kmode() - Enable kernel mode for a task added to a kmode group
+ * @pid:	PID of the task (0 for current).
+ * @rdtgrp:	Rdtgroup with kmode enabled.
+ * @of:		kernfs file (for permission check).
+ *
+ * Called when a task is written to the "tasks" file of a group that has
+ * kernel mode enabled. Enables kmode for that task so it uses the group's
+ * CLOSID/RMID on context switch. If the task is currently running, MSRs are
+ * updated on next sched-in.
+ *
+ * Return: 0 on success, or -ESRCH/-EPERM on error.
+ */
+static int rdtgroup_task_kmode(pid_t pid, struct rdtgroup *rdtgrp,
+			       struct kernfs_open_file *of)
+{
+	struct task_struct *tsk;
+	int ret;
+
+	rcu_read_lock();
+	if (pid) {
+		tsk = find_task_by_vpid(pid);
+		if (!tsk) {
+			rcu_read_unlock();
+			rdt_last_cmd_printf("No task %d\n", pid);
+			return -ESRCH;
+		}
+	} else {
+		tsk = current;
+	}
+
+	get_task_struct(tsk);
+	rcu_read_unlock();
+
+	ret = rdtgroup_task_write_permission(tsk, of);
+	if (!ret)
+		ret = __rdtgroup_task_kmode(tsk, rdtgrp);
+
+	put_task_struct(tsk);
+	return ret;
+}
+
 static ssize_t rdtgroup_tasks_write(struct kernfs_open_file *of,
 				    char *buf, size_t nbytes, loff_t off)
 {
@@ -953,7 +1020,11 @@ static ssize_t rdtgroup_tasks_write(struct kernfs_open_file *of,
 			break;
 		}
 
-		ret = rdtgroup_move_task(pid, rdtgrp, of);
+		/* Group has kmode: set task kmode; else move task CLOSID/RMID. */
+		if (rdtgrp->kmode)
+			ret = rdtgroup_task_kmode(pid, rdtgrp, of);
+		else
+			ret = rdtgroup_move_task(pid, rdtgrp, of);
 		if (ret) {
 			rdt_last_cmd_printf("Error while processing task %d\n", pid);
 			break;
@@ -1011,6 +1082,28 @@ static void show_rdt_tasks(struct rdtgroup *r, struct seq_file *s)
 	rcu_read_unlock();
 }
 
+/**
+ * rdt_task_set_kmode() - Set or clear kmode for all tasks in the rdtgroup
+ * @r:		Rdtgroup (must have r->kmode set for matching).
+ * @kmode:	True to set t->kmode for each matching task; false to clear.
+ *
+ * Walks all tasks that belong to @r (via rdt_task_match) and updates their
+ * per-task kmode flag. Used when enabling or disabling kernel mode for the
+ * group so existing members get the new state.
+ */
+static void rdt_task_set_kmode(struct rdtgroup *r, bool kmode)
+{
+	struct task_struct *p, *t;
+
+	rcu_read_lock();
+	for_each_process_thread(p, t) {
+		if (!rdt_task_match(t, r, r->kmode))
+			continue;
+		resctrl_arch_set_task_kmode(t, kmode);
+	}
+	rcu_read_unlock();
+}
+
 static int rdtgroup_tasks_show(struct kernfs_open_file *of,
 			       struct seq_file *s, void *v)
 {
@@ -1225,6 +1318,9 @@ static int rdtgroup_config_kmode(struct rdtgroup *rdtgrp, bool enable)
 
 	resctrl_arch_set_kmode(&rdtgrp->cpu_mask, &resctrl_kcfg, closid,
 			       rdtgrp->mon.rmid, enable);
+
+	rdt_task_set_kmode(rdtgrp, enable);
+
 	rdtgrp->kmode = enable;
 	if (enable)
 		resctrl_kcfg.k_rdtgrp = rdtgrp;

---

## [18] Askar Safin — 2026-03-24
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA) support to the resctrl subsystem*

Please, remove me from CC list in future versions of this patchset

---

## [19] Reinette Chatre — 2026-03-24
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Babu,

On 3/12/26 1:36 PM, Babu Moger wrote:
> 
> This series adds support for Privilege-Level Zero Association (PLZA) to the

Our discussion considered how resctrl could support PLZA in a generic way while
also preparing to support MPAM's variants and how PLZA may evolve to have similar
capabilities when considering the capabilities of its registers. 

This does not mean that your work needs to implement everything that was discussed.
Instead, this work is expected to just support what PLZA is capable of today but
do so in a way that the future enhancements could be added to.

This series is quite difficult to follow since it appears to implement a full
featured generic interface while PLZA cannot take advantage of it.

Could you please simplify this work to focus on just enabling PLZA and only
add interfaces needed to do so?

> 
> Summary:

To help with future usages please connect visibility of this file with the mode in
info/kernel_mode. This helps us to support future modes with other resctrl files, possible
within each resource group.
Specifically, kernel_mode_assignment is not visible to user space if mode is "inherit_ctrl_and_mon",
while it is visible when mode is global_assign_ctrl_inherit_mon or global_assign_ctrl_assign_mon.

>    currently assigned group (path format is "CTRL_MON/MON/"):

The format depends on the mode, right? If the mode is "global_assign_ctrl_inherit_mon"
then it should only contain a control group, alternatively, if the mode is
"global_assign_ctrl_assign_mon" then it contains control and mon group. This gives
resctrl future flexibility to change format for future modes.

We should also consider the scenario when it is a "monitoring only" system, which can
happen independent from what hardware actually supports, for example, if user boots
with "rdt=!l3cat,!l2cat,!mba,!smba". In this case I assume CLOS should just always be
zero and thus only "default control group" is accepted?

> 
>      $ cat info/kernel_mode_assignment

This does not look right. Would this not create a conflict between info/kernel_mode
and info/kernel_mode_assignment about what the current mode is? The way I see it
info/kernel_mode_assignment must always contain a valid group.

> 
>    Errors (e.g. invalid group name or unsupported mode) are reported in

I do not see why the context switch path needs to be touched at all with this
implementation. Since PLZA only supports global assignment does it not mean that resctrl
only needs to update PQR_PLZA_ASSOC when user writes to info/kernel_mode and
info/kernel_mode_assignment?

Consider some of the scenarios:

resctrl mount with default state:

	# cat info/kernel_mode
	[inherit_ctrl_and_mon]
	global_assign_ctrl_inherit_mon
	global_assign_ctrl_assign_mon
	# ls info/kernel_mode_assignment
	ls: cannot access 'info/kernel_mode_assignment': No such file or directory

enable global_assign_ctrl_assign_mon mode:
	# echo "global_assign_ctrl_assign_mon" > info/kernel_mode

Expectation here is that when user space sets this mode as above then resctrl would
in turn program MSR_IA32_PQR_PLZA_ASSOC on all CPUs to be:
	MSR_IA32_PQR_PLZA_ASSOC.rmid=0
	MSR_IA32_PQR_PLZA_ASSOC.rmid_en=1
	MSR_IA32_PQR_PLZA_ASSOC.closid=0
	MSR_IA32_PQR_PLZA_ASSOC.closid_en=1
	MSR_IA32_PQR_PLZA_ASSOC.plza_en=1

I do not see why it is necessary to maintain any per-CPU or per-task state or needing
to touch the context switch code. Since PLZA only supports global could it not
just set MSR_IA32_PQR_PLZA_ASSOC on all online CPUs and be done with it?
Only caveat is that if a CPU is offline then this setting needs to be stashed
so that MSR_IA32_PQR_PLZA_ASSOC can be set when new CPU comes online.

The way that rdtgroup_config_kmode() introduced in patch #11 assumes it is dealing
with RDT_RESOURCE_L3 and traverses the resource domain list and resource group
CPU mask seems unnecessary to me as well as error prone since the system may only
have, for example, RDT_RESOURCE_MBA enabled or even just monitoring. Why not just set
MSR_IA32_PQR_PLZA_ASSOC on all CPUs and be done?

To continue the scenarios ...

After user's setting above related files read:
	# cat info/kernel_mode
	inherit_ctrl_and_mon
	global_assign_ctrl_inherit_mon
	[global_assign_ctrl_assign_mon]
	# cat info/kernel_mode_assignment
	//

Modify group used by global_assign_ctrl_assign_mon mode:
	# echo 'ctrl1/mon1/' > info/kernel_mode_assignment

Expectation here is that when user space sets this then resctrl would
program MSR_IA32_PQR_PLZA_ASSOC on all CPUs to be:
	MSR_IA32_PQR_PLZA_ASSOC.rmid=<rmid of mon1>
	MSR_IA32_PQR_PLZA_ASSOC.rmid_en=1
	MSR_IA32_PQR_PLZA_ASSOC.closid=<closid of ctrl1>
	MSR_IA32_PQR_PLZA_ASSOC.closid_en=1
	MSR_IA32_PQR_PLZA_ASSOC.plza_en=1

Enable global_assign_ctrl_inherit_mon mode:
	# echo "global_assign_ctrl_inherit_mon" > info/kernel_mode

Expectation here is that when user space sets this mode then resctrl would
program MSR_IA32_PQR_PLZA_ASSOC on all CPUs to be:
	MSR_IA32_PQR_PLZA_ASSOC.rmid=0
	MSR_IA32_PQR_PLZA_ASSOC.rmid_en=0
	MSR_IA32_PQR_PLZA_ASSOC.closid=0
	MSR_IA32_PQR_PLZA_ASSOC.closid_en=1
	MSR_IA32_PQR_PLZA_ASSOC.plza_en=1

	# cat info/kernel_mode
	inherit_ctrl_and_mon
	[global_assign_ctrl_inherit_mon]
	global_assign_ctrl_assign_mon
	# cat info/kernel_mode_assignment <==== returns just a ctrl group
	/

Modify group used by global_assign_ctrl_inherit_mon mode:
	# echo ctrl1 > info/kernel_mode_assignment

Expectation here is that when user space sets this then resctrl would
program MSR_IA32_PQR_PLZA_ASSOC on all CPUs to be:
	MSR_IA32_PQR_PLZA_ASSOC.rmid=0
	MSR_IA32_PQR_PLZA_ASSOC.rmid_en=0
	MSR_IA32_PQR_PLZA_ASSOC.closid=<closid of ctrl1>
	MSR_IA32_PQR_PLZA_ASSOC.closid_en=1
	MSR_IA32_PQR_PLZA_ASSOC.plza_en=1

	# cat info/kernel_mode_assignment <==== returns just a ctrl group
	ctrl/

Enable inherit_ctrl_and_mon mode:
	# echo "inherit_ctrl_and_mon" > info/kernel_mode

Expectation here is that when user space sets this mode then resctrl would
program MSR_IA32_PQR_PLZA_ASSOC on all CPUs to be:
	MSR_IA32_PQR_PLZA_ASSOC.rmid=0
	MSR_IA32_PQR_PLZA_ASSOC.rmid_en=0
	MSR_IA32_PQR_PLZA_ASSOC.closid=0
	MSR_IA32_PQR_PLZA_ASSOC.closid_en=0
	MSR_IA32_PQR_PLZA_ASSOC.plza_en=0

At this point info/kernel_mode_assignment is not visible anymore:

	# ls info/kernel_mode_assignment
	ls: cannot access 'info/kernel_mode_assignment': No such file or directory

From what I understand above exposes and enables full capability of PLZA. All the other
per-task and per-cpu handling in this series is not something that PLZA can benefit from. 
If this is not the case, what am I missing? Could this series be simplified to just support
PLZA today? When next hardware with more capability needs to be supported resctrl could be
enhanced to support it by using the more accurate information about what the hardware is
capable of.

We also do not really know what use cases users prefer. This may even be sufficient.

Reinette

---

## [20] Reinette Chatre — 2026-03-24
*Subject: Re: [PATCH v2 01/16] fs/resctrl: Add kernel mode (kmode) data
 structures and arch hook*

Hi Babu,

On 3/12/26 1:36 PM, Babu Moger wrote:
> Add resctrl_kmode, resctrl_kmode_cfg, kernel mode bit defines, and
> resctrl_arch_get_kmode_cfg() for resctrl kernel mode (e.g. PLZA) support.

We should not have to start every series from scratch.
Documentation/process/maintainer-tip.rst. Always.

> ---
>  include/linux/resctrl.h       | 10 ++++++++++

This interface does not look right. Would it not be resctrl fs that determines
which resource group is assigned? This cannot be set by arch. Why does arch decide
which mode is active? Is this not also resctrl fs? Should arch not just tell
resctrl fs what it supports?

> +
>  extern unsigned int resctrl_rmid_realloc_threshold;

There is no reason why this needs to be in a central header exposed to archs. Could
this not be a static within the only function that uses it? Something like
rdt_mode_str[]?

> +
> +/**

I think it will make the code much easier to understand if the different modes are described by an
enum. For example, 

	enum resctrl_kernel_modes {
		INHERIT_CTRL_AND_MON,
		GLOBAL_ASSIGN_CTRL_INHERIT_MON,
		GLOBAL_ASSIGN_CTRL_ASSIGN_MON,
		RESCTRL_KMODE_LAST = GLOBAL_ASSIGN_CTRL_ASSIGN_MON
	};
	#define RESCTRL_NUM_KERNEL_MODES (RESCTRL_KMODE_LAST + 1)

The supported kernel modes can still be managed as a bitmap with intuitive API using the
enum that will make the code easier to read. For example, __set_bit(INHERIT_CTRL_AND_MON, ...)
or BIT(INHERIT_CTRL_AND_MON). The naming is awkward at the moment though, we should improve here.
		
Reinette

---

## [21] Reinette Chatre — 2026-03-24
*Subject: Re: [PATCH v2 02/16] fs, x86/resctrl: Add architecture routines for
 kernel mode initialization*

Hi Babu,

On 3/12/26 1:36 PM, Babu Moger wrote:
> Implement the resctrl kernel mode (kmode) arch initialization.
> 

I do not think this is something that the architecture should set, at least
at this time. Every mode has different requirements and this just lets the arch set
it without any support for what configurations it implies. For example, if
arch sets a different default mode than INHERIT_CTRL_AND_MON then PQR_PLZA_ASSOC
needs to be programmed as the CPUs come online and this does not seem to
accommodate this. This implementation appears to have significant assumptions on
what architecture will end up setting since it is only considering PLZA.

> 
> - Add global resctrl_kcfg and resctrl_kmode_init() to initialize default

I already commented on the arch vs filesystem settings.

When using an arch helper this forces all architectures to support this helper. Is a
helper required? Is it perhaps possible for arch to set a property instead? For example,
how enumeration is handled? 
I think the assumption here is that INHERIT_CTRL_AND_MON is the default and expected to
be supported by all architectures. I do not see why arch should set this as default but
instead this should be from resctrl fs. At the same time it is expected that the
architecture supports this mode so there needs to be a failure if an architecture does
not support this mode?

I'm going to stop here. I think the comments so far may result in major changes already
making further detailed review of patches unnecessary.

Reinette

---

## [22] Babu Moger — 2026-03-26
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Reinette,

Thanks for the review comments. Will address one by one.

On 3/24/26 17:51, Reinette Chatre wrote:
> Hi Babu,
>
Sure. Will try. Lets continue the discussion.
>
>> Summary:

Sure. Will do.

>
>>     currently assigned group (path format is "CTRL_MON/MON/"):

This can be done both ways.  Whole purpose of these groups is to get 
CLOSID and RMID to enable PLZA. User can echo CTRL_MON or MON group to 
kernel_mode_assignment in any of the modes.  We can decide what needs to 
be updated in MSR (PQR_PLZA_ASSOC) based on what kernel mode is selected.


>
> We should also consider the scenario when it is a "monitoring only" system, which can

Yes.  It depends on how we want to implement like we mentioned above.


>
>>       $ cat info/kernel_mode_assignment
Yes.  We can do that.
>
>>     Errors (e.g. invalid group name or unsupported mode) are reported in

Each thread has an MSR to configure whether to associate privilege level 
zero execution with a separate COS and/or RMID, and the value of the COS 
and/or RMID.  PLZA may be enabled or disabled on a per-thread 
basis. However, the COS and RMID association and configuration must be 
the same for all threads in the QOS Domain.

So, PQR_PLZA_ASSOC is a per thread MSR just like PQR_ASSOC.

Privilege-Level Zero Association (PLZA) allows the user to specify a COS 
and/or RMID associated with execution in Privilege-Level Zero. When 
enabled on a HW thread, when that thread enters Privilige-Level Zero, 
transactions associated with that thread will be associated with the 
PLZA COS and/or RMID. Otherwise, the HW thread will be associated with 
the COS and RMID identified by  PQR_ASSOC.

More below.

>
> Consider some of the scenarios:


This works correctly when PLZA associations are defined by per CPU. For 
example, lets assume that *ctrl1* is assigned *CLOSID 1*.

In this scenario, every task in the system running on a any CPU will use 
the limits associated with *CLOSID 1* whenever it enters Privilege-Level 
Zero, because the CPU's *PQR_PLZA_ASSOC* register has PLZA enabled and 
CLOSID is 1.

Now consider task-based association:

We have two resctrl groups:

  * *ctrl1 -> CLOSID 1 -> task1.plza = 1   : *User wants PLZA be enabled
    for this task.
  * *ctrl2 -> CLOSID 2 -> task2.plza = 0   : *User wants PLZA
    disabled for this task.

Suppose *task1* is first scheduled on *CPU 0*. This behaves as expected: 
since CPU 0 's *PQR_PLZA_ASSOC* contains *CLOSID 1, plza_en =1*, task1 
will use the limits from CLOSID 1 when it enters Privilege-Level Zero.

However, if *task2* later runs on *CPU 0*, we expect it to use *CLOSID 
2* in both user mode and kernel mode, because user has PLZA disabled for 
this task. But CPU 0 still has *CLOSID 1, **plza_en =1* in its 
PQR_PLZA_ASSOC register.

As a result, task2 will incorrectly run with *CLOSID 1* when entering 
Privilege-Level Zero something we explicitly want to avoid.

At that point, PLZA must be disabled on CPU 0 to prevent the unintended 
association. Hope this explanation makes the issue clear.

Thanks

Babu

>
> Enable global_assign_ctrl_inherit_mon mode:

---

## [23] Babu Moger — 2026-03-26
*Subject: Re: [PATCH v2 01/16] fs/resctrl: Add kernel mode (kmode) data
 structures and arch hook*

Hi Reinette,

On 3/24/26 17:51, Reinette Chatre wrote:
> Hi Babu,
>

Sure. Yea. I did not focus on that aspect of patch submission in this 
series. Will do next revision.


>
>> ---
Yes. Sure. Let the arch tell what is supported.  Let fs decide what is 
default.
>
>> +
Yes. I think so.
>
>> +
Yes. Sure.
>
> 	enum resctrl_kernel_modes {

Sure.  Yes. We need to think about naming.. Let me think about it.

Thanks

Babu

---

## [24] Babu Moger — 2026-03-26
*Subject: Re: [PATCH v2 02/16] fs, x86/resctrl: Add architecture routines for
 kernel mode initialization*

Hi Reinette,

On 3/24/26 17:53, Reinette Chatre wrote:
> Hi Babu,
>

Sure.  Let the arch report what is supported. Will change it to set the 
default in fs code.

Users can change change modes from FS code.


>
>> - Add global resctrl_kcfg and resctrl_kmode_init() to initialize default

I will change. Arch sets the supported modes.  FS sets the default. 
Users can change it to required mode later.


>
> I'm going to stop here. I think the comments so far may result in major changes already


Based on my comments below you may need to re-look at the some of the 
patches.

https://lore.kernel.org/lkml/47c0db32-d0e0-4c53-90bd-b74863d233dc@amd.com/

I am fine otherwise also. Let continue that discussion.

Thanks

Babu


>
> Reinette

---

## [25] Reinette Chatre — 2026-03-27
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Babu,

On 3/26/26 10:12 AM, Babu Moger wrote:
> Hi Reinette,
> 

The "both ways" are specific to one of the two active modes though.
PLZA only needs the RMID when the mode is "global_assign_ctrl_assign_mon".

Displaying and parsing monitor group when the mode is
"global_assign_ctrl_inherit_mon" creates an inconsistent interface since the mode
only uses a control group. The interface to user space should match the mode otherwise
it becomes confusing.

...


>>>
>>>       Tony suggested using global variables to store the kernel mode

Based on previous comment in https://lore.kernel.org/lkml/abb049fa-3a3d-4601-9ae3-61eeb7fd8fcf@amd.com/ 
and this implementation all fields of PQR_PLZA_ASSOC except PQR_PLZA_ASSOC.plza_en must be the
same for all CPUs on the system, not just per QoS domain. Could you please confirm?

> 
> So, PQR_PLZA_ASSOC is a per thread MSR just like PQR_ASSOC.

A couple of points:
- Looks like we still need to come to agreement what is meant by "global" when it
  comes to kernel mode.

  In your description there is a "global" configuration, but the assignment is "per-task".
  To me this sounds like a new and distinct kernel_mode from the "global" modes
  considered so far. This seems to move to the "per_task" mode mentioned in but
  the implementation does not take into account any of the earlier discussions
  surrounding it:
  https://lore.kernel.org/lkml/2ab556af-095b-422b-9396-f845c6fd0342@intel.com/

  We only learned about one use case in https://lore.kernel.org/lkml/CABPqkBSq=cgn-am4qorA_VN0vsbpbfDePSi7gubicpROB1=djw@mail.gmail.com/
  As I understand this use case requires PLZA globally enabled for all tasks. Thus
  I consider task assignment to be "global" when in the "global_*" kernel modes.
  If this is indeed a common use case then supporting only global configuration
  but then requiring user space to manually assign all tasks afterwards sounds
  cumbersome for user space and also detrimental to system performance with all
  the churn to modify all the task_structs involved. The accompanying documentation
  does not mention all this additional user space interactions required by user
  space to use this implementation. 

  I find this implementation difficult and inefficient to use in the one use case
  we know of. I would suggest that resctrl optimizes for the one known use case.

- This implementation ignores discussion on how existing resctrl files should
  not be repurposed.

  This implementation allows user space to set a resource group in
  kernel_mode_assignment with the consequence that this resource group's
  "tasks" file changes behavior. I consider this a break of resctrl interface.
  We did briefly consider per-task configuration/assignment in previous discussion
  and the proposal was for it to use a new file (only when and if needed!).

- Now a user is required to write the task id of every task that participates
  in PLZA. Apart from the churn already mentioned this also breaks existing
  usage since it is no longer possible for new tasks to be added to this
  resource group. This creates an awkward interface where all tasks belonging
  to a resource group inherits the allocations/monitoring for their user space
  work and will get PLZA enabled whether user requested it or not while
  tasks from other resource groups need to be explicitly enabled. This creates
  an inconsistency when it comes to task assignment. The only way to "remove"
  PLZA from such a task would be to assign it to another resource group which
  may not have the user space allocations ... and once this is done the task
  cannot be moved back.
  There is no requirement that CLOSID/RMID should be dedicated to kernel work
  but this implementation does so in an inconsistent way.

- Apart from the same issues as with repurposing of tasks file, why should same
  CPU allocation be used for kernel and user space? 

Reinette

---

## [26] Babu Moger — 2026-03-30
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Reinette,

On 3/27/26 17:11, Reinette Chatre wrote:
> Hi Babu,
>
Ok. That is fine. We can do that.
> ...
>

Sorry for the confusion. It is "per QoS domain".

All the fields of PQR_PLZA_ASSOC except PQR_PLZA_ASSOC.plza_enmust be set to the same value for all HW threads in the QOS domain for 
consistent operation (Per-QosDomain).

>
>> So, PQR_PLZA_ASSOC is a per thread MSR just like PQR_ASSOC.
Yes, I agree with your concerns. The goal here is to make the interface 
less disruptive while still addressing the different use cases.


      Background: Customers have identified an issue with the QoS
      Bandwidth Control feature: when a CLOS is aggressively throttled
      and execution transitions into kernel mode, kernel operations are
      also subject to the same aggressive throttling.

Privilege-Level Zero Association (PLZA) allows a user to specify a COS 
and/or RMID to be used during execution at Privilege Level Zero. When 
PLZA is enabled on a hardware thread, any execution that enters 
Privilege Level Zero will have its transactions associated with the PLZA 
COS and/or RMID. Otherwise, the thread continues to use the COS and RMID 
specified by |PQR_ASSOC|. In other words, the hardware provides a 
dedicated COS and/or RMID specifically for kernel-mode execution.

There are multiple ways this feature can be applied. For simplicity, the 
discussion below focuses only on CLOSID.


      1. Global PLZA enablement

PLZA can be configured as a global feature by setting 
|PQR_PLZA_ASSOC.closid = CLOSID| and |PQR_PLZA_ASSOC.plza_en = 1| on all 
threads in the system. A dedicated CLOSID is reserved for this purpose, 
and all CPU threads use its allocations whenever they enter Privilege 
Level Zero. This CLOSID does not need to be associated with any resctrl 
group. The user can explicitly enable or disable this feature. There is 
no context switch overhead but there is no flexibility with this approach.


      2. Group based PLZA allocation :  PLZA is managed via dedicated
      restctrl group. A separate resctrl group can be created
      specifically for PLZA, with a dedicated CLOSID used exclusively
      for kernel mode execution. This approach can be further divided
      into two association models:

i) CPU based association
CPUs are assigned to the PLZA group, and PLZA is enabled only on those 
CPUs. This effectively creates a dedicated PLZA group. MSRs 
(|PQR_PLZA_ASSOC)| are programmed only when the user changes CPU 
assignments. This approach requires no changes to the context switch 
code and introduces no additional context switch overhead.

ii) Task based association
Tasks are explicitly assigned by the user to the PLZA group. Tasks need 
to be updated when user adds a new task. Also, this requires updates 
during task scheduling so that the MSRs (|PQR_PLZA_ASSOC)| are 
programmed on each context switch, which introduces additional context 
switch overhead.

I tried to fit these requirements into  the interface files in 
/sys/fs/resctrl/info/.  I may have missed few things while trying to 
achieve it.  As usual, I am open for the discussion and recommendations.

Thanks,
Babu

---

## [27] Reinette Chatre — 2026-03-31
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Babu,

On 3/30/26 11:46 AM, Babu Moger wrote:
> On 3/27/26 17:11, Reinette Chatre wrote:
>> On 3/26/26 10:12 AM, Babu Moger wrote:

>>>>>        Tony suggested using global variables to store the kernel mode
>>>>>        CLOSID and RMID. However, the kernel mode CLOSID and RMID are

Thank you for clarifying. To build on this, what would be best way for resctrl to interpret this?
As I see it all values in PQR_PLZA_ASSOC apply to *all* resources yet (theoretically?) every resource
can have domains that span different CPUs. There thus seem to be a built in assumption of what a "domain"
means for PQR_PLZA_ASSOC so it sounds to me as though, instead of saying that "PQR_PLZA_ASSOC needs
to be the same in QoS domain" it may be more accurate to, for example, say that "PQR_PLZA_ASSOC has L3 scope"?

This seems to be what this implementation does since it hardcodes PQR_PLZA_ASSOC scope to the L3
resource but that creates dependency to the L3 resource that would make PLZA unusable if, for example,
the user boots with "rdt=!l3cat" while wanting to use PLZA to manage MBA allocations when in kernel?

...

> Yes, I agree with your concerns. The goal here is to make the interface less disruptive while still addressing the different use cases.

I consider changing resctrl behavior when values are written to existing resctrl files
to be disruptive. This is something we explicitly discussed during v1 as something to
be avoided so this implementation that overloads the tasks file again is unexpected.

>      Background: Customers have identified an issue with the QoS
>      Bandwidth Control feature: when a CLOS is aggressively throttled
ack.

> 
> There are multiple ways this feature can be applied. For simplicity, the discussion below focuses only on CLOSID.

Also discussed during v1 is that there is no need to dedicate a CLOSID for this purpose.
There could be an "unthrottled" CLOSID to which all high priority user space tasks as
well as all kernel work of all tasks are assigned.
If user space chooses to dedicate a CLOSID for kernel work then that should supported and
interface can allow that, but there is no need for resctrl to enforce this.

> and all CPU threads use its allocations whenever they enter Privilege Level Zero. This CLOSID does not need to be associated with any resctrl group.

The CLOSID has to be associated with a resource group to be able to manage its
resource allocations, no?

> The user can explicitly enable or disable this feature.
ack.

> There is no context switch overhead but there is no flexibility with this approach.

Flexibility is subjective. As I understand this supports the only use case we learned about so far:
https://lore.kernel.org/lkml/CABPqkBSq=cgn-am4qorA_VN0vsbpbfDePSi7gubicpROB1=djw@mail.gmail.com/

>      2. Group based PLZA allocation :  PLZA is managed via dedicated
>      restctrl group. A separate resctrl group can be created

So far this sounds like global allocation since both need a dedicated resource group.
Whether this group is dedicated to kernel work or shared between kernel and user space work
is up to the user. There is no motivation why CLOSID should ever be enforced to be
exclusive for kernel mode execution.

> 
> i) CPU based association

As discussed during v1 any changes needed to support per task assignment would
need to be done with new files dedicated to this purpose. Do not overload the
existing resctrl tasks/cpus/cpus_list files.
 
> I tried to fit these requirements into  the interface files in /sys/
> fs/resctrl/info/.  I may have missed few things while trying to

Many of these items were already discussed as part of v1 so I think we may be
talking past each other here. I tried to highlight the relevant points raised
during v1 discussion that I thought there already was agreement on. 

The one new aspect is that I assumed this implementation will only be for
global configuration and assignment. It looks like you want to support both
global configuration and per-task assignment. In the original I did not consider
configuration and assignment to occur at different scope so we may need to come up
with new modes to distinguish. Consider the addition of two modes as below:

	# cat info/kernel_mode
	[inherit_ctrl_and_mon]
	global_assign_ctrl_inherit_mon_set_all
	global_assign_ctrl_assign_mon_set_all
	global_assign_ctrl_inherit_mon_set_individual
	global_assign_ctrl_assign_mon_set_individual

Above introduces a "set_all" and "set_individual" suffix to the original two
modes.

global_assign_ctrl_inherit_mon_set_all
global_assign_ctrl_assign_mon_set_all:

	Above are the original two modes but makes it clear that when this mode is
	activated _all_ tasks run with the assignment.

global_assign_ctrl_inherit_mon_set_individual
global_assign_ctrl_assign_mon_set_individual:

	Above are two new modes. In this mode user space also assigns a resource
	group globally but then needs to follow that up by activating every task
	separately to run with this assignment.
	One way in which this can be accomplished could be to have "kernel_mode_tasks",
	"kernel_mode_cpus", and "kernel_mode_cpus_list"	files become visible (or be
	created) in the resource group found in	info/kernel_mode_assignment. User
	space interacts with the new files to set which tasks and/or CPUs run with
	PLZA enabled.
	
Even so, as I understand global_assign_ctrl_inherit_mon_set_all and 
global_assign_ctrl_assign_mon_set_all addresses the only known use case. Do you know 
if there are use cases for global_assign_ctrl_inherit_mon_set_individual and
global_assign_ctrl_assign_mon_set_individual? The latter two adds significant
complexity to resctrl while I have not heard about any use case for it.

Reinette

---

## [28] Babu Moger — 2026-04-06
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Reinette,

Sorry for the late response. I was trying to get confirmation about the 
use case.

On 3/31/26 17:24, Reinette Chatre wrote:
> Hi Babu,
> 

Yes.  That is correct. PLZA applies to all the resources.

> can have domains that span different CPUs. There thus seem to be a built in assumption of what a "domain"
> means for PQR_PLZA_ASSOC so it sounds to me as though, instead of saying that "PQR_PLZA_ASSOC needs

Yes.

> 
> This seems to be what this implementation does since it hardcodes PQR_PLZA_ASSOC scope to the L3

Yes. that is correct. It should not be attached to one resource. We need 
to change it to global scope.

> 
> ...

Yes. Agree. If required we need to introduce new files (kmode_cpus, 
kmode_cpu_list or kmode_tasks) to handle these cases.

> 
>>       Background: Customers have identified an issue with the QoS

I misspoke here.

> 
> The CLOSID has to be associated with a resource group to be able to manage its

Yes. We need to have resource group schemata to enforce the limits.

> 
>> The user can explicitly enable or disable this feature.

Yes. That is fine.
> 
>>

Yes. Sure.

>   
>> I tried to fit these requirements into  the interface files in /sys/

Yes. I agree. The changes in context switch code is a concern.

You covered some of the cases I was thinking(xx_set_individual).

How about this idea?

I suggest splitting the PLZA into two distinct aspects:

1. How PLZA is applied within a resource group

2. How PLZA is monitored


Introduce a new file, "info/kmode_type", to describe how kmode applies 
in the system.

# cat info/kmode_type
[global] <- Kernel mode applies to the entire system (all CPUs/tasks)
   cpus   <- Kernel mode applies only to the CPUs in the group
   tasks  <- Kernel mode applies only to the tasks in the group

The "global" option is the default right now and it is current common 
use-case.

The "info/kmode_type -> cpus" option introduces new files "kmode_cpus" 
and "kmode_cpus_list" for users to apply kmode to specific set of CPUs. 
This lets users change the CPU set for PLZA. The PLZA MSR is updated 
when user changes the association to the file. No context switch code 
changes are needed. This will be dedicated group. The current resctrl 
group files, "cpus, cpus_list and tasks" will not be accessible in this 
mode. This option give some flexibility for the user without the context 
switch overhead.

The "info/kmode_type -> tasks" option introduces a new file, 
"kmode_tasks", for users to apply kmode to specific set of tasks. This 
requires context switch changes. This will be dedicated group. The 
current resctrl group files, "cpus, cpus_list and tasks" will not be 
accessible in this mode. We currently have no use case for this, so it 
will not be supported now.


Add a file, "info/kmode_monitor", to describe how kmode is monitored.

# cat info/kmode_monitor
[inherit_ctrl_and_mon] <- Kernel uses the same CLOSID/RMID as user. 
Default option for the "global"
assign_ctrl_inherit_mon <- One CLOSID for all kernel work; RMID 
inherited from user.
assign_ctrl_assign_mon <- One resource group (CLOSID+RMID) for all 
kernel work. Default option for "cpu" type.


Rename “kernel_mode_assignment” to “kmode_group” to assign the specific 
group to kmode. This file usage is same as before.

#cat info/kmode_groups (Renamed "kernel_mode_assignment")
//


Thoughts?

thanks
Babu

---

## [29] Reinette Chatre — 2026-04-07
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Babu,

On 4/6/26 3:45 PM, Babu Moger wrote:
> Hi Reinette,
> 

No problem. I appreciate that you did this so that we can make sure resctrl supports
needed use cases.

> 
> On 3/31/26 17:24, Reinette Chatre wrote:

>> can have domains that span different CPUs. There thus seem to be a built in assumption of what a "domain"
>> means for PQR_PLZA_ASSOC so it sounds to me as though, instead of saying that "PQR_PLZA_ASSOC needs

Above is about L3 scope ...
 
>>
>> This seems to be what this implementation does since it hardcodes PQR_PLZA_ASSOC scope to the L3

Can I interpret "global scope" as "all online CPUs"? Doing so will simplify
supporting this feature. It does not sound practical for a user wanting to assign
different resource groups to kernel work done in different domains ... the guidance should
instead be to just set the allocations of one resource group to what is needed in the different
domains? There may be more flexibility when supporting per-domain RMIDs though but so far
it sounds as though the focus is global. We can consider what needs to be done to support
some type of "per-domain" assignment as exercise whether current interface could support it
in the future.

...

>>> There are multiple ways this feature can be applied. For simplicity, the discussion below focuses only on CLOSID.
>>>

(above is comment about dedicated group - please see below)

 
> Yes. I agree. The changes in context switch code is a concern.
> 

I think I see where you are going here. While the "How PLZA is monitored" naming 
refers to "monitoring" I *think* what you are separating here is (a) how PLZA is configured
(CLOSID and RMID settings) and (b) how that PLZA configuration is assigned to tasks/CPUs,
not just within a resource group but across the system. Please see below.


> Introduce a new file, "info/kmode_type", to describe how kmode applies in the system.

ack. "in the system" as you have above, not "within a resource group" as mentioned
before that.

> 
> # cat info/kmode_type
Where were you thinking about placing these files in the hierarchy?

> The PLZA MSR is updated when user changes the association to the
> file. No context switch code changes are needed. This will be

Why does this have to be a dedicated group? One of the conclusions from v1
discussion was that the "PLZA group" need *not* be a dedicated group. I repeated that
in my earlier response that I left quoted above. You did not respond to these
conclusions and statements in this regard while you keep coming back to this
needing to be a dedicated group without providing a motivation to do so.
Could you please elaborate why a dedicated group is required?


> and tasks" will not be accessible in this mode. This option give

These files can continue to be accessible. 

> some flexibility for the user without the context switch overhead.

Dedicating a resource group to PLZA removes flexibility though, no?

> 
> The "info/kmode_type -> tasks" option introduces a new file,

Thank you for confirming. This is a relief.

> 
> 

My first thought is that the naming is confusing. resctrl has a very strong relationship between
"RMID" and "monitoring" so naming a file "monitor" that deals with allocation/ctrl/CLOSID is
potentially confusion.

Apart from that, while I think I understand where you are going by separating the mode into
two files I am concerned about future complications needing to accommodate all different
combinations of the (now) essentially two modes. My preference is thus to keep this simple by
keeping the mode within one file.

Even so, when stepping back, it does not really look like we need to separate the "global"
and "per CPU" modes. We could just have a single "per CPU" mode and the "global" is just
its default of "all CPUs", no?

Consider, for example, the implementation just consisting of:

	# cat info/kernel_mode
	[inherit_ctrl_and_mon]
	global_assign_ctrl_inherit_mon_per_cpu
	global_assign_ctrl_assign_mon_per_cpu
 
> 
> Rename “kernel_mode_assignment” to “kmode_group” to assign the specific group to kmode. This file usage is same as before.

Please consider the intent of this file when thinking about names. The idea is that "info/kernel_mode"
specifies the "mode" of how kernel work is handled and it determines the configuration files used in that
mode as well as the syntax when interacting with those files. By renaming "kernel_mode_assignment" to
"kmode_groups" it implicitly requires all future kernel mode enhancements to need some data related to "groups".

In summary, I think this can be simplified by introducing just two new files in info/ that enables the
user to (a) select and (b) configure the "kernel mode". To start there can be just two modes,
global_assign_ctrl_inherit_mon_per_cpu and global_assign_ctrl_assign_mon_per_cpu. 
global_assign_ctrl_inherit_mon_per_cpu mode requires a control group in kernel_mode_assignment while
global_assign_ctrl_assign_mon_per_cpu requires a control and monitoring group.

The resource group in info/kernel_mode_assignment gets two additional files "kernel_mode_cpus" and
"kernel_mode_cpus_list" that contains the CPUs enabled with the kernel mode configuration, by default
it will be all online CPUs. The resource group can continue to be used to manage allocations of and
monitor user space tasks. Specifically, the "cpus", "cpus_list", and "tasks" files remain.

A user wanting just "global" settings will get just that when writing the group to
info/kernel_mode_assignment. A user wanting "per CPU" settings can follow the
info/kernel_mode_assignment setting with changes to that resource group's kernel_mode_cpus/kernel_mode_cpus_list
files. Any task running on a CPU that is *not* in kernel_mode_cpus/kernel_mode_cpus_list can be
expected to inherit both CLOSID and RMID from user space for all kernel work.

Reinette

---

## [30] Babu Moger — 2026-04-07
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Reinette,

On 4/7/26 12:48, Reinette Chatre wrote:
> Hi Babu,
> 

Yes. The scope for PQR_PLZA_ASSOC is L3.

Is that what you are asking here?

>   
>>>

Yes. That is correct.


> supporting this feature. It does not sound practical for a user wanting to assign
> different resource groups to kernel work done in different domains ... the guidance should

Yes. Makes sense.

> 
> ...

It needs to be inside the resctrl group (in struct rdtgroup).


> 
>> The PLZA MSR is updated when user changes the association to the

If the same group applies identical limits to both user and kernel 
space, it essentially behaves like a current resctrl group. In that 
sense, it’s not really a PLZA group. PLZA’s key value is the ability to 
separate allocations between user space and kernel space. A single CPU 
can belong to two groups: one group manages the user-space allocation 
for that CPU, while another manages the kernel-mode allocation.
This approach also simplifies file handling, which is another reason I 
prefer it.

That said, I’m open to not having a dedicated group if we can still 
support all the features that PLZA provides without it.


> 
> 

ok.

> 
>> some flexibility for the user without the context switch overhead.

Yes. But makes it easy to handle the files as I mentioned above.

> 
>>

Yes. That correct.

> 
> Consider, for example, the implementation just consisting of:

After further consideration, I don’t think the info/kernel_mode file is 
necessary. There’s no need to enforce a specific mode for all the PLZA 
groups. Avoiding this constraint makes the design more flexible, 
particularly as we move toward supporting multiple PLZA groups in the 
future. MPAM already appears capable of handling more than one group—for 
example, one group could use inherit_ctrl_and_mon, while another could 
use global_assign_ctrl_inherit_mon_per_cpu.

The mode can simply be determined on a per-group basis. We can introduce 
two new files—kernel_mode_cpus and kernel_mode_cpus_list—within each 
resctrl group when kmode (or PLZA) is supported.

The info/kernel_mode_assignment file would indicate which resctrl 
group(or groups) is used for PLZA. The files—kernel_mode_cpus and 
kernel_mode_cpus_list would indicate how the plza is applied which each 
group.

Files and behavior:
- cpus / cpus_list:

CPUs listed here use the same allocation for both user and kernel space.
There is no change to the current semantics of these files.
If these files are empty, the group effectively becomes a PLZA-dedicated 
group.

- kernel_mode_cpus / kernel_mode_cpus_list:

These files determine whether a separate kernel allocation is applied.
If empty, user and kernel share the same allocation.
If non-empty, the kernel uses a separate allocation.

The group can be CTL_MON or MON group. Based on type the group the 
CLOSID and RMID will be used to enable PLZA. If it is MON, then rmid_en 
= 1 when writing PLZA MSR.


Here’s the proposed flow:

# mount -t resctrl resctrl /sys/fs/resctrl/
# cd /sys/fs/resctrl/
# cat info/kernel_mode_assignment
//

By default, the root (default) group is PLZA-enabled when resctrl is 
mounted. All CPUs use CLOSID 0 for both user and kernel-mode allocation.

# cat cpus_list
1-64
# cat kmode_cpus_list
1-64

Next, create a new group for PLZA:

# mkdir plza_group

# echo "plza_group//" > info/kernel_mode_assignment

At this point, plza_group becomes the new PLZA-enabled group, and the 
PLZA-related MSRs are updated accordingly.

# cat plza_group/cpus_list
<empty>

# cat plza_group/kmode_cpus_list
1-64

The user can then update kmode_cpus_list to apply PLZA only to a 
specific subset of CPUs, if desired.


What do you think of this approach?


Thanks
Babu

---

## [31] Reinette Chatre — 2026-04-07
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Babu,

On 4/7/26 6:01 PM, Babu Moger wrote:
> Hi Reinette,
> 

I was trying to point out that there appears to be a mismatch between the actual scope and
the planned implementation. As highlighted below during the discussion about "global" this is
fine with me and I just wanted to confirm that this matches your intentions.

> 
>>  

...

>>> The PLZA MSR is updated when user changes the association to the
>>> file. No context switch code changes are needed. This will be

The plan has never been to force identical allocations for user and kernel
space since that would go against this feature entirely. Even so, just as
user and kernel space cannot be forced to have identical allocations they
also cannot be forced to have different allocations. Specifically,
a task *can* use the same CLOSID for user and kernel space work just as easily
as it can use *different* CLOSID for user and kernel space work. There
should not be any CLOSID reserved just for kernel work. Or am I missing something?

> single CPU can belong to two groups: one group manages the user-
> space allocation for that CPU, while another manages the kernel-mode

Exactly. This is why it is important to have two files for this CPU association
within a resource group. The cpus/cpus_list file continues to be used as today
while the new kernel_mode_cpus/kernel_mode_cpus_list is used for kernel work.
With this a task can be associated with any resource group for its user space
allocations but when it runs on one of the CPUs within kernel_mode_cpus then
its kernel work will be done with allocations of the resource group the
kernel_mode_cpus file belongs to, which may or may not be the same
resource group that the user space task belongs to.

> This approach also simplifies file handling, which is another reason
> I prefer it.

I *think* we have different interpretations of "dedicated group":
It sounds as though you interpret "dedicated group" as a way that enforces
the same allocations to user space and kernel work.
I interpret "dedicated group" essentially as a CLOSID reserved for kernel
work. Since I do not see that resctrl should dedicate a CLOSID/resource group
for kernel work I have been pushing against such "dedicated group". 

> That said, I’m open to not having a dedicated group if we can still support all the features that PLZA provides without it.

I find that enabling user space to share CLOSID/RMID between user space
and kernel space to indeed support what PLZA provides. I think I am missing
something here since below proposal again attempts to isolate a resource group
(CLOSID) for kernel work.

>>> Add a file, "info/kmode_monitor", to describe how kmode is monitored.
>>>

You are looking ahead at future capabilities for which we do not know all requirements
at this time. I think it is very good to consider how things may progress and your example
of MPAM is of course on point. I believe the current design does consider this progression.
Please see https://lore.kernel.org/lkml/2ab556af-095b-422b-9396-f845c6fd0342@intel.com/ 
(search for "per_group_assign_ctrl_assign_mon"). In that exploration per-group assignment
is actually accomplished with global files. I thus think we should not make such a big
architectural decision that does not benefit the immediate feature using partial information.
As it is, a "info/kernel_mode" gives the flexibility to expand to, if needed, configuration
files within a resource group. That is why the intention is to associate the mode within
info/kernel_mode with the presence/absence of info/kernel_mode_assignment (search for
"Visibility depends on active mode in info/kernel_mode" in linked email) since in the
future resctrl may need to enable a mode that needs configuration files within each
resource group and when enabling such mode the per-resource group files will appear
instead of the global info/kernel_mode_assignment.

> 
> The mode can simply be determined on a per-group basis. We can introduce two new files—kernel_mode_cpus and kernel_mode_cpus_list—within each resctrl group when kmode (or PLZA) is supported.

I think having these files in every resource group is confusing since user can only interact
with these files in one resource group for current PLZA. Why not *just* have the files in the
resource group that matches the group in info/kernel_mode_assignment?
 
> 
> The info/kernel_mode_assignment file would indicate which resctrl

The "how PLZA is applied" should be learned from info/kernel_mode where user
space learns whether RMID is inherited or not. While I find kernel_mode_cpus
and kernel_mode_cpus_list to be just for configuration and just found in the
resource group listed in info/kernel_mode_assignment.

> 
> Files and behavior:

Both user and kernel space?
Monitoring would depend on info/kernel_mode_assignment ("inherit_mon")
and kernel space allocation would depend on whether the CPU on which the task runs
can be found in kernel_mode_cpus, no?


> There is no change to the current semantics of these files.
> If these files are empty, the group effectively becomes a PLZA-dedicated group.

I do not see it this way. If the cpu/cpus_list files are empty then it means that the
tasks in the group will use their own CLOSID/RMID for user space allocation and
monitoring. What allocations/monitoring is used by tasks when in kernel mode depends
on whether the CPU the task is running on can be found in a kernel_mode_cpus/kernel_mode_cpuslist
file. If the CPU the task is running on can be found in a kernel_mode_cpus/kernel_mode_cpuslist
file then it will inherit whatever the PQR_PLZA setting of that CPU which is the allocation
associated with the resource group to which that kernel_mode_cpus/kernel_mode_cpuslist belongs.
If the CPU the task is running on cannot be found in kernel_mode_cpus/kernel_mode_cpuslist
then its kernel work will inherit its user space allocations and monitoring.

> 
> - kernel_mode_cpus / kernel_mode_cpus_list:

This will be difficult to get right since CTRL_MON groups also have RMID assigned.

> Here’s the proposed flow:
> 

It really looks like you are getting back to trying to dedicate a resource group to
kernel work and that is not something that resctrl should enforce.

> 
> # cat plza_group/cpus_list

It is difficult to predict how the "next" PLZA will actually end up looking like and I find resctrl creating a complicated
interface to support this to be risky. Instead I would prefer to focus on efficiently supporting what PLZA can do today
and make it extensible. Apart from that I find the implicit interface, "If it is MON, then rmid_en = 1" to be too
architecture specific for a generic interface while also not able to accurately capture user's intent (i.e. user may
indeed, for example, want "a CTRL_MON group to have rmid_en = 1"). Finally, I am just so confused about why the implementations
keep needing to dedicate a resource group/CLOSID to kernel work.

Reinette

---

## [32] Babu Moger — 2026-04-08
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Reinette,

On 4/7/26 23:45, Reinette Chatre wrote:
> Hi Babu,
> 

Ack.

> 
>>

No. You are not missing anything.


> 
>> single CPU can belong to two groups: one group manages the user-

Yes. Exactly.

> 
>> This approach also simplifies file handling, which is another reason

Actually, our understanding is same. Probably, I am not explaining it 
right. Hope we get there soon.


> 
>> That said, I’m open to not having a dedicated group if we can still support all the features that PLZA provides without it.

No. I dont want to isolate a group just for PLZA. All I am saying is, we 
should provide option to create a dedicated group if the user wants to 
do it.

> 
>>>> Add a file, "info/kmode_monitor", to describe how kmode is monitored.

The default group can also serve as the PLZA group.

#cat info/kernel_mode_assignment
//

At this point, the (kmode_cpus / kmode_cpus_list) files will exist in 
the default group:

Then user changes the PLZA group to "test".

#echo "test//" > info/kernel_mode_assignment

At this point, we expect the files "(kmode_cpus/kmode_cpus_list)" to be 
visible in "test//" group.

One open question is whether we should remove the visibility of these 
files from the default group. It’s unclear if we can safely do this 
dynamically.

An alternative approach would be to always keep the files present, but 
allow access to them only for groups that are listed in 
"info/kernel_mode_assignment".


>>
>> The info/kernel_mode_assignment file would indicate which resctrl

ok.

> 
>>

As it stands today, the CPU list is written to MSR_PQR_ASSOC, resulting 
in the same allocation for both user and kernel within a given CLOS.

Kernel-mode allocation changes only if specific CPUs are included in the 
kmode_cpus list.


> Monitoring would depend on info/kernel_mode_assignment ("inherit_mon")
> and kernel space allocation would depend on whether the CPU on which the task runs

Yes. that is correct.

> 
> 

Yes. that is correct. I think our understanding is correct, but our 
implementation ideas are different it seems.

>>
>> - kernel_mode_cpus / kernel_mode_cpus_list:

Let me make sure I understand what you mentioned earlier. Copied the 
text below from the thread for the context:

https://lore.kernel.org/lkml/3305c18e-9e50-4df0-b9f1-c61028628967@intel.com/
=====================================================================

Please consider the intent of this file when thinking about names. The 
idea is that "info/kernel_mode"
specifies the "mode" of how kernel work is handled and it determines the 
configuration files used in that
mode as well as the syntax when interacting with those files. By 
renaming "kernel_mode_assignment" to
"kmode_groups" it implicitly requires all future kernel mode 
enhancements to need some data related to "groups".

In summary, I think this can be simplified by introducing just two new 
files in info/ that enables the
user to (a) select and (b) configure the "kernel mode". To start there 
can be just two modes,
global_assign_ctrl_inherit_mon_per_cpu and 
global_assign_ctrl_assign_mon_per_cpu.
global_assign_ctrl_inherit_mon_per_cpu mode requires a control group in 
kernel_mode_assignment while
global_assign_ctrl_assign_mon_per_cpu requires a control and monitoring 
group.

The resource group in info/kernel_mode_assignment gets two additional 
files "kernel_mode_cpus" and
"kernel_mode_cpus_list" that contains the CPUs enabled with the kernel 
mode configuration, by default
it will be all online CPUs. The resource group can continue to be used 
to manage allocations of and
monitor user space tasks. Specifically, the "cpus", "cpus_list", and 
"tasks" files remain.

A user wanting just "global" settings will get just that when writing 
the group to
info/kernel_mode_assignment. A user wanting "per CPU" settings can 
follow the
info/kernel_mode_assignment setting with changes to that resource 
group's kernel_mode_cpus/kernel_mode_cpus_list
files. Any task running on a CPU that is *not* in 
kernel_mode_cpus/kernel_mode_cpus_list can be
expected to inherit both CLOSID and RMID from user space for all kernel 
work.

======================================================================

Let me try to get few clarification on things here.

# cat info/kernel_mode
   [inherit_ctrl_and_mon]
   global_assign_ctrl_inherit_mon_per_cpu
   global_assign_ctrl_assign_mon_per_cpu

My understanding of "inherit_ctrl_and_mon" is that the kernel inherits 
both the CLOS and the RMID from user space. Basically both user and 
kernel uses same CLOSID and RMID. This reflects the current behavior 
(without PLZA) correct? This would correspond to the default group when 
resctrl is mounted.

The modes "global_assign_ctrl_inherit_mon_per_cpu" and 
"global_assign_ctrl_assign_mon_per_cpu" represent the actual PLZA modes.

Both of these modes introduce new files kernel_mode_cpus/ and 
kernel_mode_cpus_list in the resctrl group.

When the user echoes a group name into info/kernel_mode_assignment, PLZA 
is applied globally across all CPUs. This is default behavior.

If the user wants PLZA to apply only to a specific subset of CPUs, then 
the kernel_mode_cpus or kernel_mode_cpus_list files need to be updated 
accordingly.

global_assign_ctrl_inherit_mon_per_cpu : The group needs to be CTLR_MON 
group. This mode uses rmid_en=0 when writing PLZA MSR.

global_assign_ctrl_assign_mon_per_cpu: The group needs to be 
CTLR_MON/MON group. This mode uses rmid_en=1 when writing PLZA MSR.

Did I get it right?

Thanks
Babu

---

## [33] Reinette Chatre — 2026-04-08
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Babu,

On 4/8/26 1:45 PM, Babu Moger wrote:
> On 4/7/26 23:45, Reinette Chatre wrote:
>> On 4/7/26 6:01 PM, Babu Moger wrote:

>>> That said, I’m open to not having a dedicated group if we can still support all the features that PLZA provides without it.
>>
I agree. I do not see resctrl needing to do anything to accomplish this though. If
the user wants a group dedicated to kernel mode/PLZA then all that is needed is for the
user not to assign any tasks to this group, either via changes to the group's tasks file
or via the group's cpus/cpus_list files.

>>>
>>> The mode can simply be determined on a per-group basis. We can

The files appearing/disappearing is just how the user experiences the resctrl fs interface.
Within resctrl the files could indeed always exist but resctrl can use the kernfs_show()
API to show/hide them as needed. Similar to resctrl_bmec_files_show() that you created.
Allowing/removing access becomes complicated because user space can always do a chmod
to change permissions that resctrl would need to handle.

I do not know if there are sharp corners here when thinking about strange scenarios where
user opens a file before resctrl changes visibility or permissions and then user space
interacts with the file. This may be worthwhile to test to matter which mechanism is used.

>>> Files and behavior:
>>> - cpus / cpus_list:

ack.

>>> There is no change to the current semantics of these files.
>>> If these files are empty, the group effectively becomes a PLZA-dedicated group.

While we have been sharing different ideas I have tried to be clear on *why* I made
certain choices and attempted to provide specific feedback to your ideas. If you find
your plan to be better then please respond to my feedback about it to help me understand
why that may be the better solution. If you find your solution is better then could you please
describe it with detail? At this time I do not have a clear understanding of what you propose.

...
> 
> Let me make sure I understand what you mentioned earlier. Copied the text below from the thread for the context:

Correct.

> default group when resctrl is mounted.

> 
> The modes "global_assign_ctrl_inherit_mon_per_cpu" and "global_assign_ctrl_assign_mon_per_cpu" represent the actual PLZA modes.

Right. To be specific when the user changes the mode to either "global_assign_ctrl_inherit_mon_per_cpu" or
"global_assign_ctrl_assign_mon_per_cpu" the new files will be created in the default resource group with
associated setting applied globally at that time.

> 
> When the user echoes a group name into info/kernel_mode_assignment, PLZA is applied globally across all CPUs. This is default behavior.

This is my understanding also, yes.

Reinette

---

## [34] Moger, Babu — 2026-04-08
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Reinette,

On 4/8/2026 4:24 PM, Reinette Chatre wrote:
> Hi Babu,
> 

If, at that point, "info/kernel_mode_assignment" points to // (the 
default group), is that correct?

And if "info/kernel_mode_assignment" points to a different group (for 
example, test//), then the kernel_mode_cpus/ and kernel_mode_cpus_list 
files will be created only under the test// group. Is that correct?

Thanks
Babu

---

## [35] Reinette Chatre — 2026-04-08
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Babu,

On 4/8/26 4:07 PM, Moger, Babu wrote:
> On 4/8/2026 4:24 PM, Reinette Chatre wrote:
>> On 4/8/26 1:45 PM, Babu Moger wrote:
...

>>> The modes "global_assign_ctrl_inherit_mon_per_cpu" and "global_assign_ctrl_assign_mon_per_cpu" represent the actual PLZA modes.
>>>

I see "info/kernel_mode_assignment" pointing to default group as the only
option right after a mode switch away from "inherit_ctrl_and_mon".

To elaborate, the current idea is that the mode within info/kernel_mode determines
which, if any, control files are presented to user space.
Assuming that the system boots up with:
	# cat info/kernel_mode
	[inherit_ctrl_and_mon]
	global_assign_ctrl_inherit_mon_per_cpu
	global_assign_ctrl_assign_mon_per_cpu

In above scenario "info/kernel_mode_assignment" does not exist (is not visible to
user space).

When the user switches to either "global_assign_ctrl_inherit_mon_per_cpu" or
'global_assign_ctrl_assign_mon_per_cpu" then "info/kernel_mode_assignment" is created
(or made visible to user space) and is expected to point to default group.
User can change the group using "info/kernel_mode_assignment" at this point.

If the current scenario is below ...
	# cat info/kernel_mode
	[global_assign_ctrl_inherit_mon_per_cpu]
	inherit_ctrl_and_mon
	global_assign_ctrl_assign_mon_per_cpu

... then "info/kernel_mode_assignment" will exist but what it should contain if
user switches mode at this point may be up for discussion.

option 1)
When user switches mode to "global_assign_ctrl_assign_mon_per_cpu" then
the resource group in "info/kernel_mode_assignment" is reset to the
default group and all CPUs PLZA state reset to match. The kernel_mode_cpus
and kernel_mode_cpuslist files become visible in default resource group
and they contain "all online CPUs".

option 2)
When user switches mode to "global_assign_ctrl_assign_mon_per_cpu" then
the resource group in "info/kernel_mode_assignment" is kept and all
CPUs PLZA state set to match it while also keeping the current 
values of that resource group's kernel_mode_cpus and kernel_mode_cpuslist
files.

I am leaning towards "option 1" to keep it consistent with a switch from
"inherit_ctrl_and_mon" and being deterministic about how a mode is started with
a clean slate. What are your thoughts? What would be use case where a user would
want to switch between "global_assign_ctrl_inherit_mon_per_cpu" and
"global_assign_ctrl_assign_mon_per_cpu" to just switch rmid_en on and off?


> And if "info/kernel_mode_assignment" points to a different group
> (for example, test//), then the kernel_mode_cpus/ and

I expect that if "info/kernel_mode_assignment" exists then the group
listed within contains kernel_mode_cpus and kernel_mode_cpuslist.
How the group ends up in "info/kernel_mode_assignment" could result
from mode change or from write by user space.

Reinette

---

## [36] Moger, Babu — 2026-04-09
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Reinette,

On 4/8/2026 6:41 PM, Reinette Chatre wrote:
> Hi Babu,
> 

Yes. The "option 1" seems appropriate.

> a clean slate. What are your thoughts? What would be use case where a user would
> want to switch between "global_assign_ctrl_inherit_mon_per_cpu" and


This is a bit tricky.

Currently, our requirement is to have a CTRL_MON group for 
global_assign_ctrl_inherit_mon_per_cpu. In this scenario, we use the 
group’s CLOSID for PLZA configuration, and RMID is not used (rmid_en = 
0) when setting up PLZA.

Our requirement is also to have a CTRL_MON/MON group for 
global_assign_ctrl_assign_mon_per_cpu. In this case as well, the group’s 
CLOSID and RMID (rmid_en = 1)  both are used configure PLZA.

Actually, we should not allow these changes from 
global_assign_ctrl_inherit_mon_per_cpu  to 
global_assign_ctrl_assign_mon_per_cpu or visa versa.

This seems restrictive.

> 
> 
Ack.

Thanks
Babu>

---

## [37] Reinette Chatre — 2026-04-09
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Babu,

On 4/9/26 10:19 AM, Moger, Babu wrote:
> On 4/8/2026 6:41 PM, Reinette Chatre wrote:

>> When the user switches to either "global_assign_ctrl_inherit_mon_per_cpu" or
>> 'global_assign_ctrl_assign_mon_per_cpu" then "info/kernel_mode_assignment" is created

ah, right. Good catch.

> 
> Actually, we should not allow these changes from

resctrl could allow it but as part of the switch it resets the "kernel mode group" to
be the default group every time? This would be the "option 1" above.

Reinette

---

## [38] Moger, Babu — 2026-04-09
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Reinette,

On 4/9/2026 12:26 PM, Reinette Chatre wrote:
> 
> Hi Babu,

Other options.

Allow global_assign_ctrl_inherit_mon_per_cpu -> 
global_assign_ctrl_assign_mon_per_cpu. As part of the switch, reset the 
"kernel mode group" to the default group.

Allow global_assign_ctrl_assign_mon_per_cpu -> 
global_assign_ctrl_inherit_mon_per_cpu. In this case switch
to CTRL_MON/MON -> CTRL_MON.

Thanks
Babu



> 
> Reinette

---

## [39] Reinette Chatre — 2026-04-09
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Babu,

On 4/9/26 11:05 AM, Moger, Babu wrote:
> On 4/9/2026 12:26 PM, Reinette Chatre wrote:
>> On 4/9/26 10:19 AM, Moger, Babu wrote:

ok. Could you please return the courtesy of providing feedback on the
suggestion you are responding to and also include the motivation why your
suggestion is the better option? 

Reinette

---

## [40] Moger, Babu — 2026-04-09
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Reinette,

On 4/9/2026 3:50 PM, Reinette Chatre wrote:
> Hi Babu,
> 

Yea. Sure.

We need to allow the switch between the modes. Otherwise only way to 
reset is to remount the resctrl filesystem. That is not a good option.

Allow global_assign_ctrl_inherit_mon_per_cpu -> 
global_assign_ctrl_assign_mon_per_cpu. As part of the switch, reset the 
"kernel mode group" to the default group.

This option is same as you suggested.

Allow global_assign_ctrl_assign_mon_per_cpu -> 
global_assign_ctrl_inherit_mon_per_cpu. In this case switch
to CTRL_MON/MON -> CTRL_MON. This option basically disables monitor 
(rmid_en=0). It is less disruptive. Move is between child group to 
parent group.

Thanks
Babu

---

## [41] Reinette Chatre — 2026-04-09
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Babu,

On 4/9/26 4:42 PM, Moger, Babu wrote:
> Hi Reinette,
> 

ok. I am concerned that this creates an inconsistent interface. Specifically, sometimes
when switching the mode the kernel group will reset and sometimes it won't. This inconsistency
may be more apparent when writing the user documentation as part of this work. If you are
able to clearly explain how this resctrl fs interface behaves (this cannot be about PLZA
internals as above) then this could work.

Reinette

---

## [42] Moger, Babu — 2026-04-10
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Reinette,

On 4/9/2026 10:41 PM, Reinette Chatre wrote:
> Hi Babu,
> 

Yes, certainly. I’ll begin work on v3, and we can continue refining it 
as we move forward.

Thanks
Babu

---

## [43] Babu Moger — 2026-04-20
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Reinette,

On 4/9/26 22:41, Reinette Chatre wrote:
> Hi Babu,
> 
Started working on these changes. May be it is better to discuss this 
before to avoid one more revision.


The current mode change behavior is very restrictive.

For example:

# cat info/kernel_mode
       inherit_ctrl_and_mon
       [global_assign_ctrl_assign_mon_per_cpu]
        global_assign_ctrl_inherit_mon_per_cpu


# cat info/kernel_mode_assignment
      ctrl1/mon1/

In this state, we cannot change kernel_mode to inherit_ctrl_and_mon. The 
expectation, however, is that inherit_ctrl_and_mon should always map to 
the RDTCTRL_GROUP.


A similar issue exists when switching between
global_assign_ctrl_inherit_mon_per_cpu and
global_assign_ctrl_assign_mon_per_cpu (in either direction).

The same problem also occurs when modifying the kernel_mode_assignment 
group. If the current group is an RDTMON_GROUP, we can't assign another
RDTCTRL_GROUP without changing both mode and group together.


To address this, I propose changing the mode and the group together.

System boots up with following defaults:

# cat info/kernel_mode
       [inherit_ctrl_and_mon]
       global_assign_ctrl_assign_mon_per_cpu
       global_assign_ctrl_inherit_mon_per_cpu

# cat info/kernel_mode_assignment
      inherit_ctrl_and_mon://


# echo "global_assign_ctrl_assign_mon_per_cpu:ctrl1/mon1/" > 
info/kernel_mode_assignment

# cat info/kernel_mode_assignment
      global_assign_ctrl_assign_mon_per_cpu:ctrl1/mon1/

# cat info/kernel_mode
       inherit_ctrl_and_mon
       [global_assign_ctrl_assign_mon_per_cpu]
       global_assign_ctrl_inherit_mon_per_cpu


# echo "inherit_ctrl_and_mon://" > info/kernel_mode_assignment

# cat info/kernel_mode_assignment
    inherit_ctrl_and_mon://


# cat info/kernel_mode
       [inherit_ctrl_and_mon]
       global_assign_ctrl_assign_mon_per_cpu
        global_assign_ctrl_inherit_mon_per_cpu


# echo "global_assign_ctrl_inherit_mon_per_cpu:ctrl1//"

# cat info/kernel_mode_assignment
    global_assign_ctrl_inherit_mon_per_cpu:ctrl1//

# cat info/kernel_mode
       inherit_ctrl_and_mon
       global_assign_ctrl_assign_mon_per_cpu
       [global_assign_ctrl_inherit_mon_per_cpu]


The interface "info/kernel_mode" becomes read-only,

The mode change and group change will be done with 
"info/kernel_mode_assignment"


I’m also planning to rename the kernel modes as follows:

inherit_ctrl_and_mon → shared_alloc_mon
global_assign_ctrl_inherit_mon_per_cpu → global_alloc_per_cpu
global_assign_ctrl_assign_mon_per_cpu → global_alloc_mon_per_cpu

What do you think?

Thanks
Babu

---

## [44] Reinette Chatre — 2026-04-20
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Babu,

On 4/20/26 12:38 PM, Babu Moger wrote:
> On 4/9/26 22:41, Reinette Chatre wrote:
>> On 4/9/26 4:42 PM, Moger, Babu wrote:

Could you please provide details behind the "we cannot change kernel_mode to
inherit_ctrl_and_mon" statement? Why is this not possible?

I do not see "inherit_ctrl_and_mon" to map to *any* group though. Expectation is
that when user changes mode to "inherit_ctrl_and_mon" then 
info/kernel_mode_assignment would become invisible to user space.

> 
> 

What similar issue? Could you please provide some detail to help me understand what the
issue is? Isn't this what we just discussed in thread you are replying to? That is, you were
looking at developing that interface that I viewed as "inconsistent"?

> 
> The same problem also occurs when modifying the kernel_mode_assignment group. If the current group is an RDTMON_GROUP, we can't assign another

Same problem? Still unclear what the problem is. So far three problems are mentioned but I am
not able to decipher what the problems are. Could you please elaborate?
When modifying the kernel_mode_assignment group I expect that the interface
will only accept a MON group when in "assign_mon" mode and a CTRL group when
in "inherit_mon" mode. 
I do not understand what you mean with *another* RDTCTRL_GROUP. Only one group
can be assigned at any time, no?

Reinette

---

## [45] Moger, Babu — 2026-04-20
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Reinette,

On 4/20/2026 5:03 PM, Reinette Chatre wrote:
> Hi Babu,
> 

Ok. That is fine.


Sorry for not making it clear. Let’s consider the following scenario.

The system boots with these default settings:

# cat info/kernel_mode
[inherit_ctrl_and_mon]
global_assign_ctrl_assign_mon_per_cpu
global_assign_ctrl_inherit_mon_per_cpu


At this point, the interface info/kernel_mode_assignment is not visible.

Next, lets create a new control group:

# mkdir ctrl1

We want to designate this group as the new kernel-mode group.

First operation: Change the mode:

# echo "global_assign_ctrl_inherit_mon_per_cpu" > info/kernel_mode

At this stage, only the kernel mode is being changed. However, there is 
no way to know which control group the user intends to assign to kernel 
mode. All we know here is the selected mode.

After this operation, the info/kernel_mode_assignment interface should 
become visible. But the question is: what should it contain or point to 
at this moment?

# cat info/kernel_mode_assignment
??

Next operation: Assign the group

# echo "ctrl1//" > info/kernel_mode_assignment


Now the intended control group (ctrl1) is explicitly specified for 
kernel mode. In summary, changing the kernel mode requires two distinct 
inputs:

- Selecting the kernel mode.
- Specifying the control group to be used for that mode.


Hope this makes sense.

Thanks
Babu

> 
>>

---

## [46] Reinette Chatre — 2026-04-20
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Babu,

On 4/20/26 3:59 PM, Moger, Babu wrote:
> On 4/20/2026 5:03 PM, Reinette Chatre wrote:
>> On 4/20/26 12:38 PM, Babu Moger wrote:

>>> The current mode change behavior is very restrictive.
>>>

This was considered as part of original proposal per
https://lore.kernel.org/lkml/2ab556af-095b-422b-9396-f845c6fd0342@intel.com/ 
(search for "default value") where the idea was that the group
should be initialized to the default group.

> 
> # cat info/kernel_mode_assignment

After
# echo "global_assign_ctrl_inherit_mon_per_cpu" > info/kernel_mode
# cat info/kernel_mode_assignment
/

After
# echo "global_assign_ctrl_assign_mon_per_cpu" > info/kernel_mode
# cat info/kernel_mode_assignment
//

(although this is where previous discussion comes in on how interface
can become inconsistent depending on what the previous kernel mode was)

> 
> Next operation: Assign the group
Understood. Could you please elaborate what the problem is with making it so?
Are you trying to eliminate one per-CPU register write? Is this something that
ends up being very expensive? I assumed that a register designed to support
modification during context switch should be fast. Or is it the IPI you are
concerned about? Please help me to understand what the actual problem is that
you are trying to solve.
I think it is reasonable to start with defaults when changing the mode which
I do not expect users to change often.

Reinette

---

## [47] Luck, Tony — 2026-04-20
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

> The system boots with these default settings:
> 

This allocates a CLOSID and an RMID for this group.

> We want to designate this group as the new kernel-mode group.
> 

This mode needs a CLOSID for PLZA, but doesn't need an RMID.

> At this stage, only the kernel mode is being changed. However, there is no
> way to know which control group the user intends to assign to kernel mode.

Now ring0 code is using the CLOSID from the ctrl1 group.

But the RMID for this group isn't used.

Are we OK with "wasting" an RMID in this way?

Maybe it doesn't matter too much for AMD as you would just
avoid assigning any counters to this group. But should Intel
get around to doing PLZA-like functionality, that's a real
loss of an RMID that might be useful elsewhere.

-Tony

---

## [48] Reinette Chatre — 2026-04-20
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Tony,

On 4/20/26 5:03 PM, Luck, Tony wrote:
>> The system boots with these default settings:
>>

... and user space tasks also continue to use the CLOSID from the
ctrl1 group.
It is up to user space to decide if a group is dedicated to kernel
mode or not. resctrl does not enforce it.

> 
> But the RMID for this group isn't used.

RMID is still used by user mode that maintains existing behavior concerning
this group when considering its tasks/cpus/cpus_list files. RMID assigned to this
group is just not used for kernel mode.

> 
> Are we OK with "wasting" an RMID in this way?

How do you see this RMID as "wasted"?

> 
> Maybe it doesn't matter too much for AMD as you would just

Reinette

---

## [49] Moger, Babu — 2026-04-20
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Reinette,

On 4/20/2026 6:34 PM, Reinette Chatre wrote:
> Hi Babu,
> 

This operation effectively promotes the default group (CLOSID 0) to the 
kernel-mode group. Consequently, MSRs will be programmed on all threads, 
which is not the user’s intent.

> 
>>

Once again, this causes MSRs to be programmed with a new CLOSID(ctrl1) 
which is actual intended result.

>>
>> Now the intended control group (ctrl1) is explicitly specified for kernel mode. In summary, changing the kernel mode requires two distinct inputs:

Note that these MSR writes are not occurring in the context-switch path.

However, every time the kernel mode is changed, we end up performing an 
additional set of MSR writes, which is unnecessary overhead.

There is also another issue, as previously discussed: switching between
global_assign_ctrl_assign_mon_per_cpu and
global_assign_ctrl_inherit_mon_per_cpu, and vice versa.

One mode requires a CTRL_MON group, while the other requires a MON 
group. Because of this mismatch in required group types, switching 
between these modes is not possible.

We already discussed moving back to the default group on every mode 
switch. Doing so here would once again cause extra MSR writes on each 
mode transition, which is undesirable.

Thanks
Babu

---

## [50] Reinette Chatre — 2026-04-20
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Babu,

On 4/20/26 5:40 PM, Moger, Babu wrote:
> 
> We already discussed moving back to the default group on every mode

Needing to avoid extra MSR writes in resctrl is not so absolute. Consider, for
example, how resctrl initializes default allocations when a new resource group is
created. resctrl aims to initialize with sane defaults and the user is expected to
follow with desired allocations.

I am not against optimizing, I just want to be careful with such general statements.

Considering your proposal in https://lore.kernel.org/lkml/39e0c786-cc35-4555-bfb9-ff7cd758c423@amd.com/:

I do not think we should make info/kernel_mode read-only. If I understand correctly
doing so would accommodate AMD PLZA but it ignores the discussions on how resctrl could
support MPAM ... or do you perhaps have proposal on how MPAM can be supported when considering
your proposal? Even if you do not want to consider MPAM - what if the PLZA_PQR register's
scope becomes per-CPU in the next version of AMD PLZA?

The idea behind info/kernel_mode is that the active mode it identifies indicates which
configuration files exist to configure the active mode. Since the mode may not always
depend on global configuration, for which info/kernel_mode_assignment was created, but instead
rely on per-resource group files, I do not see how resctrl can build on a read-only
info/kernel_mode backed by a mode and group change via info/kernel_mode_assignment.
Specifically, MPAM support may not use info/kernel_mode_assignment at all.
Instead, MPAM may use something like described in https://lore.kernel.org/lkml/aYyxAPdTFejzsE42@e134344.arm.com/

Could we perhaps consider dropping info/kernel_mode_assignment entirely for
AMD PLZA's global allocations? Similar to what you suggest, the mode and
group assignment could be done via the info/kernel_mode file instead?

Thinking about this more since the CPUs allocation is global, these could *theoretically*
be included also (but see later).
This could mean that "kernel_mode_cpus" and "kernel_mode_cpus_list" could be dropped?
Although, this may complicate the interface since user space may want a convenient way
to modify just CPUs independently from needing to repeat the mode and group every time.

Consider, for example:

# echo "global_assign_ctrl_assign_mon_per_cpu:group=ctrl1/mon1/;cpus_list=5-8" > info/kernel_mode

Having named fields (a) makes this extensible, (b) output does not need to be split among files,
and (c) "inherit_ctrl_and_mon" can continue to be supported.

The named fields could be made optional, if group is omitted then it will become the
default resource group, and if cpus/cpus_list is omitted then it will default to all CPUs.
This may not be intuitive since a user may expect that not mentioning a field means
that the field is left untouched. Have you considered this scenario in your proposal?

As an alternative the group could be made a required field and "kernel_mode_cpus"/"kernel_mode_cpuslist"
can stay? This may be the simplest approach.

Output could still use [] to indicate the active mode that includes its properties.
I find to be more intuitive interface where output more closely matches input.

Reinette

---

## [51] Babu Moger — 2026-04-21
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Reinette,

On 4/20/26 22:17, Reinette Chatre wrote:
> Hi Babu,
> 

This looks reasonable.

> 
> Having named fields (a) makes this extensible, (b) output does not need to be split among files,

How about keeping a single option to update the CPUs using 
kernel_mode_cpus / kernel_mode_cpuslist within the group?

Should we consider removing the per‑CPU extension altogether? By 
default, the mode already applies to all online CPUs, and any per‑CPU 
requirements can be handled within the group using kernel_mode_cpus / 
kernel_mode_cpuslist.


# echo "global_assign_ctrl_assign_mon_per_cpu:group=ctrl1/mon1/

Why do we still need to keep the "inherit_ctrl_and_mon"?  By default all 
the groups in the system falls in this category it is not plza enabled 
group.


System boots up with following options if PLZA is supported.

# cat info/kernel_mode
       global_assign_ctrl_assign_mon_per_cpu
       global_assign_ctrl_inherit_mon_per_cpu

No groups are associated with kernel mode at this point.

# echo "global_assign_ctrl_assign_mon_per_cpu:group=ctrl1/mon1/" > 
info/kernel_mode

# cat info/kernel_mode
   global_assign_ctrl_assign_mon_per_cpu:group=ctrl1/mon1/
   global_assign_ctrl_inherit_mon_per_cpu


# echo "global_assign_ctrl_inherit_mon_per_cpu:group=//" > info/kernel_mode


# cat info/kernel_mode
   global_assign_ctrl_assign_mon_per_cpu
   global_assign_ctrl_inherit_mon_per_cpu:group=//


How does this look?

Thanks
Babu

---

## [52] Luck, Tony — 2026-04-21
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

On Mon, Apr 20, 2026 at 05:21:50PM -0700, Reinette Chatre wrote:
> Hi Tony,
> 

True, that the RMID is used if the user makes assignments using tasks/cpus/cpus_list
for the ctrl1 group. But they might not do that.

> 
> > 

Suppose the user doesn't assign tasks to the ctrl1 group?

Perhaps the resources they want to make available to the kernel do
not exactly match with resources that they want to provide to any
tasks. In this case the RMID is wasted.

> > 
> > Maybe it doesn't matter too much for AMD as you would just

-Tony

---

## [53] Reinette Chatre — 2026-04-21
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Tony,

On 4/21/26 8:11 AM, Luck, Tony wrote:
> On Mon, Apr 20, 2026 at 05:21:50PM -0700, Reinette Chatre wrote:
>> On 4/20/26 5:03 PM, Luck, Tony wrote:
...

>>>> # echo "global_assign_ctrl_inherit_mon_per_cpu" > info/kernel_mode
>>>

Under these circumstances, yes, the RMID will not be used. 

A related scenario (when considering  what may happen if user does not assign tasks to
the ctrl1 group) is when user space disables PLZA on all CPUs in a domain then the CLOSID
(as well as RMID since this is irrespective of rmid_en mode) associated with kernel_mode
will be unused in that domain.

Reinette

---

## [54] Reinette Chatre — 2026-04-21
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Babu,

On 4/21/26 8:08 AM, Babu Moger wrote:
> Hi Reinette,
> 

It sounds like we are saying the same thing? 
When considering all the sharp corners I agree that keeping kernel_mode_cpus/kernel_mode_cpuslist
seems most user friendly. When doing so there is no need to include CPU assignment in the global
files.
 
> 
> # echo "global_assign_ctrl_assign_mon_per_cpu:group=ctrl1/mon1/

To me it seems useful to be clear to user space on what the current mode is. If I understand correctly
above default scenario essentially means "inherit_ctrl_and_mon" but instead of adding it to this file
we will need to add documentation that describes to user space how this file should be interpreted.
It seems easier to me to just be clear via info/kernel_mode itself on what the current active mode is?

I think something like below will be more intuitive and not need much additional 
documentation to understand (I am just adding the "uninitialized" as an example to match text
printed in schemata file during pseudo-locking ... even if there is a group named "uninitialized"
the lack of "/" could be used to make it clear what this means?):

	# cat info/kernel_mode
	[inherit_ctrl_and_mon]
	global_assign_ctrl_assign_mon_per_cpu:group=uninitialized
	global_assign_ctrl_inherit_mon_per_cpu:group=uninitialized

I also think an interface like this would be simpler for user space to use as it (user space) switches
between PLZA capable and non-PLZA capable systems since user space need not associate existence of
the file with some kernel mode state in addition to actual content of the file when it does exist.

I assumed that info/kernel_mode can just always be made visible and not depend on PLZA
capable hardware. This means that on Intel and Arm this file can show:

	# cat info/kernel_mode
	[inherit_ctrl_and_mon]

For Intel this is accurate and also for Arm if I interpret the Arm implementation correctly
(see mpam_thread_switch()) in  https://lore.kernel.org/lkml/20260313144617.3420416-7-ben.horgan@arm.com/

> 
> # echo "global_assign_ctrl_assign_mon_per_cpu:group=ctrl1/mon1/" > info/kernel_mode

In addition to above I think it will be helpful to add a clear indication to user
space on what the current active mode is, for example, via the [] characters.

Reinette

---

## [55] Babu Moger — 2026-04-21
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Reinette,

On 4/21/26 11:15, Reinette Chatre wrote:
> Hi Babu,
> 

Actually, I was talking about removing _per_cpu extension also as the 
per-CPU requirement is handled inside the group using 
kernel_mode_cpus/kernel_mode_cpuslist. It can be documented.

global_assign_ctrl_assign_mon_per_cpu -> global_assign_ctrl_assign_mon
global_assign_ctrl_inherit_mon_per_cpu -> global_assign_ctrl_inherit_mon


>>
>> # echo "global_assign_ctrl_assign_mon_per_cpu:group=ctrl1/mon1/

Sounds ok to me.


> I also think an interface like this would be simpler for user space to use as it (user space) switches
> between PLZA capable and non-PLZA capable systems since user space need not associate existence of

Yes. Sure.


> For Intel this is accurate and also for Arm if I interpret the Arm implementation correctly
> (see mpam_thread_switch()) in  https://lore.kernel.org/lkml/20260313144617.3420416-7-ben.horgan@arm.com/

# echo "global_assign_ctrl_assign_mon_per_cpu:group=ctrl1/mon1/" > 
info/kernel_mode

# cat info/kernel_mode
    inherit_ctrl_and_mon
    global_assign_ctrl_assign_mon_per_cpu:group=uninitialized
    [global_assign_ctrl_assign_mon_per_cpu]:group=ctrl1/mon1/

Something like this?

There is one problem here. The mode "inherit_ctrl_and_mon" listing not 
consistent with others.

Thanks
Babu

---

## [56] Reinette Chatre — 2026-04-21
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Babu,

On 4/21/26 9:46 AM, Babu Moger wrote:
> On 4/21/26 11:15, Reinette Chatre wrote:
>> On 4/21/26 8:08 AM, Babu Moger wrote:

>> It sounds like we are saying the same thing?
>> When considering all the sharp corners I agree that keeping kernel_mode_cpus/kernel_mode_cpuslist

I see. The goal with this name choice was to distinguish a global mode that 
additionally supports per-CPU assignment from a "true/pure" global mode that
does not support per-CPU assignment.

If resctrl ever needs to support such "true/pure" global mode that does
not support per-CPU assignment then resctrl will need to either come up with
a new mode that does not expose kernel_mode_cpus/kernel_mode_cpuslist or
make kernel_mode_cpus/kernel_mode_cpuslist read-only. The latter adds the
complication that user space can always change the mode of a file so resctrl
would need to add corner cases for that.

To me the "per_cpu" distinction is useful since it make it clear to user space
that even though this is a "global" configuration it additionally supports
per-CPU assignment for which user space can expect kernel_mode_cpus/kernel_mode_cpuslist
to exist and be writable. To me this makes the interface clear and intuitive.

>>>
>>> # echo "global_assign_ctrl_assign_mon_per_cpu:group=ctrl1/mon1/

How about making it clear that the whole line/configuration is active, like below:

	# cat info/kernel_mode
	inherit_ctrl_and_mon
	global_assign_ctrl_assign_mon_per_cpu:group=uninitialized
	[global_assign_ctrl_assign_mon_per_cpu:group=ctrl1/mon1/]


> 
> There is one problem here. The mode "inherit_ctrl_and_mon" listing not consistent with others.

It is difficult to predict what resctrl will be asked to support next. One possibility here is
to make it part of the original design that the first field is the "mode" and the following field
contains that mode's global properties of which there could be more than one. Above shows that
the two "global" modes have a single global property but we could just try to be safe with some
documentation that states there could be more.

Consider for example some hypothetical future where the file looks like:

	# cat info/kernel_mode
	inherit_ctrl_and_mon:some_unique_capability=true
	global_assign_ctrl_assign_mon_per_cpu:group=uninitialized;other_property=val
	[global_assign_ctrl_assign_mon_per_cpu:group=ctrl1/mon1/]

To leave room for growth the file could start out by, for example, appending ":"
to "inherit_ctrl_and_mon" to indicate that there are no known properties yet?  Something like
below. Would this be more consistent with the others?

	# cat info/kernel_mode
	inherit_ctrl_and_mon:
	global_assign_ctrl_assign_mon_per_cpu:group=uninitialized
	[global_assign_ctrl_assign_mon_per_cpu:group=ctrl1/mon1/]

Reinette

---

## [57] Babu Moger — 2026-04-21
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Reinette,

On 4/21/26 12:35, Reinette Chatre wrote:
> Hi Babu,
> 

ok. Sure.

> 
>>>>

ok. Sure.

>>
>> There is one problem here. The mode "inherit_ctrl_and_mon" listing not consistent with others.

To me, it might be clearer to simply document what the default mode is 
when kernel mode is not enabled, and omit "inherit_ctrl_and_mon" from 
the display.

That said, I’m fine with either approach.

Thanks
Babu

---

## [58] Reinette Chatre — 2026-04-21
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Babu,

On 4/21/26 11:19 AM, Babu Moger wrote:
> On 4/21/26 12:35, Reinette Chatre wrote:
>> On 4/21/26 9:46 AM, Babu Moger wrote:


>>>>>
>>>>> # echo "global_assign_ctrl_assign_mon_per_cpu:group=ctrl1/mon1/

Here you question why "inherit_ctrl_and_mon" is needed ...

>>>>>
>>>>>

Above I share considerations when thinking whether to keep "inherit_ctrl_and_mon" or not ...

>>>
>>> Sounds ok to me.

... to which you seem to agree ...

>>>
>>>


... more considerations from me when thinking whether to keep "inherit_ctrl_and_mon" or not ...

>>>>
>>>> I assumed that info/kernel_mode can just always be made visible and not depend on PLZA

... to which you seem to agree ...

>>>
>>>

... and even more considerations from me when thinking whether to keep "inherit_ctrl_and_mon" or not.

...

>>> There is one problem here. The mode "inherit_ctrl_and_mon" listing not consistent with others.
>>

... and now you question again why "inherit_ctrl_and_mon" should be included in display without
a motivation why and without addressing any of the previous considerations motivating its
inclusion. How can I respond when you clearly ignore my response to the previous time you asked
this question?

My previous comments are still valid. You mention that "it might be clearer to simply document what
the default mode is when kernel mode is not enabled". To me there is not really a "disabled" kernel mode
since kernel work done on behalf of a task needs to be done with *some* allocation - kernel mode is not
"disabled". Why should resctrl not make it clear what this behavior is? Adding another consideration to
the list ... what if resctrl needs to support some other "default" mode in the future? How can a user
know that not having an active mode means one or the other "default" mode?

If you feel that "inherit_ctrl_and_mon" should be omitted then please motivate why and also address why
the considerations I mentioned are not valid.

Reinette

---

## [59] Moger, Babu — 2026-04-21
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Reinette,

On 4/21/2026 3:57 PM, Reinette Chatre wrote:
> Hi Babu,
> 


My bad. My only motivation was to keep the mode listing display consistent.

That said, I agree we need to support this. Without it, we won’t be able 
to move the group from PLZA to non-PLZA.

# cat info/kernel_mode
     inherit_ctrl_and_mon:
     global_assign_ctrl_assign_mon_per_cpu:group=uninitialized
     [global_assign_ctrl_assign_mon_per_cpu]:group=ctrl1/mon1/

# echo "inherit_ctrl_and_mon:group=ctrl1/mon1/" > info/kernel_mode

# cat info/kernel_mode
     inherit_ctrl_and_mon:
     global_assign_ctrl_assign_mon_per_cpu:group=uninitialized
     [global_assign_ctrl_assign_mon_per_cpu]:group=uninitialized

Thanks
Babu

---

## [60] Reinette Chatre — 2026-04-21
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Babu,

On 4/21/26 3:04 PM, Moger, Babu wrote:
> My bad. My only motivation was to keep the mode listing display consistent.

The listing display is already inconsistent since the different modes have different
global properties, no? 

> 
> That said, I agree we need to support this. Without it, we won’t be able to move the group from PLZA to non-PLZA.

Like above where the listing is inconsistent. Is this what you mean?

sidenote: Should the last line be "[global_assign_ctrl_assign_mon_per_cpu:group=ctrl1/mon1/]"?

> 
> # echo "inherit_ctrl_and_mon:group=ctrl1/mon1/" > info/kernel_mode

This does not look right. Why is a "group" property needed here? Can the mode not just
be set by itself? Specifically, why not just:

	# echo "inherit_ctrl_and_mon" > info/kernel_mode

This reminds me that there is still an open remaining from
https://lore.kernel.org/lkml/71099958-1ddf-40dc-8a3c-aa13d0c56fee@intel.com/ 
Specifically this from that message:
	The named fields could be made optional, if group is omitted then it will become the
	default resource group, and if cpus/cpus_list is omitted then it will default to all CPUs.
	This may not be intuitive since a user may expect that not mentioning a field means
	that the field is left untouched. Have you considered this scenario in your proposal?

I think this needs some clear description of behavior wrt properties, for example:
- Is it required to provide all properties on each write? More specifically, can user expect there
  to be "default" values when a property is not provided or is user required to provide a value
  for each property? We need to be careful here because we do not want user scripts to fail when a new
  property is added in the future. What if resctrl specifies that if user space does not provide
  a property then resctrl will pick a default. For example, if user runs:
	# echo "global_assign_ctrl_assign_mon_per_cpu" > info/kernel_mode
  then resctrl will switch to "global_assign_ctrl_assign_mon_per_cpu" mode initialized to
  the default group.
  I am not sure if resctrl needs to support re-configuration of modes in the future where the
  mode stays the same but a property changes? Consider, for example,

	# cat info/kernel_mode
	[inherit_ctrl_and_mon:]
	global_assign_ctrl_assign_mon_per_cpu:group=uninitialized

	# echo "global_assign_ctrl_assign_mon_per_cpu" > info/kernel_mode
	/*
	 * resctrl switches to "global_assign_ctrl_assign_mon_per_cpu" mode and sets
	 * PLZA group to default group
	 */
	# cat info/kernel_mode
	inherit_ctrl_and_mon:
	[global_assign_ctrl_assign_mon_per_cpu:group=//]
	# echo "global_assign_ctrl_assign_mon_per_cpu:group=ctrl1/mon1/" > info/kernel_mode
	/*
	 * resctrl stays in "global_assign_ctrl_assign_mon_per_cpu" mode and sets
	 * PLZA group to default group
	 */
	# cat info/kernel_mode
	inherit_ctrl_and_mon:
	[global_assign_ctrl_assign_mon_per_cpu:group=ctrl1/mon1/]
	# echo "global_assign_ctrl_assign_mon_per_cpu" > info/kernel_mode
	/*
	 * TBD: should resctrl switch back to default group or just keep
	 * group as ctrl1/mon1/ ?
	 */

  resctrl could thus specify different behavior for switching to a mode where all properties
  not specified obtains default values and re-configuring a mode where only specified
  properties are changed. That means, the "TBD" above would be that the group stays
  as ctrl1/mon1/. So,
	# cat info/kernel_mode
	inherit_ctrl_and_mon:
	[global_assign_ctrl_assign_mon_per_cpu:group=ctrl1/mon1/]

  What do you think?

> # cat info/kernel_mode
>     inherit_ctrl_and_mon:
This does not look right. After switching the kernel_mode to inherit_ctrl_and_mon
I expect inherit_ctrl_and_mon to be the active mode?

Reinette

---

## [61] Moger, Babu — 2026-04-21
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Reinette,

On 4/21/2026 5:44 PM, Reinette Chatre wrote:
> Hi Babu,
> 

Yes. That is true.

>>
>> That said, I agree we need to support this. Without it, we won’t be able to move the group from PLZA to non-PLZA.

I meant the listing of "inherit_ctrl_and_mon" does not have groups while 
other modes have it.

> 
> sidenote: Should the last line be "[global_assign_ctrl_assign_mon_per_cpu:group=ctrl1/mon1/]"?

Yes.

> 
>>

We can go with this based on your another comment below. While changing 
the mode use the defaults if properties are not provided.


> 
> This reminds me that there is still an open remaining from

I think you meant "PLZA group to ctrl1/mon1/" here.

> 	# cat info/kernel_mode
> 	inherit_ctrl_and_mon:

Yes. Sure. We can do that. We only have 2 properties now (mode and 
group). We should be able to handle that.


> 
>> # cat info/kernel_mode

Yes. inherit_ctrl_and_mon should be active here.

Thanks
Babu

---

## [62] Reinette Chatre — 2026-04-21
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Babu,

On 4/21/26 5:17 PM, Moger, Babu wrote:
> On 4/21/2026 5:44 PM, Reinette Chatre wrote:
>> On 4/21/26 3:04 PM, Moger, Babu wrote:

>>> That said, I agree we need to support this. Without it, we won’t be able to move the group from PLZA to non-PLZA.
>>>

I think this is ok since it does not need a group or any other (for now?) property.
What issues do you foresee here?

>>
>> sidenote: Should the last line be "[global_assign_ctrl_assign_mon_per_cpu:group=ctrl1/mon1/]"?

Indeed, yes. Thank you.

> 
>>     # cat info/kernel_mode

Thank you for considering.

Reinette

---

## [63] Moger, Babu — 2026-04-22
*Subject: Re: [PATCH v2 00/16] fs,x86/resctrl: Add kernel-mode (e.g., PLZA)
 support to the resctrl subsystem*

Hi Reinette,

On 4/21/2026 9:56 PM, Reinette Chatre wrote:
> Hi Babu,
> 

Nothing at this point.  Will let you know if something comes up when 
started working on it.

Thanks,
Babu

---
