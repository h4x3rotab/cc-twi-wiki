---
title: 'x86,fs/resctrl: Support L3 Smart Data Cache Injection Allocation Enforcement (SDCIAE)'
date: 2025-09-02
last_reply: 2025-09-25
message_count: 33
participants: ['Babu Moger', 'Reinette Chatre', 'Moger, Babu']
---

## [1] Babu Moger — 2025-09-02

This series adds the support for L3 Smart Data Cache Injection Allocation
Enforcement (SDCIAE) to resctrl infrastructure. It is referred to as
"io_alloc" in resctrl subsystem.

Upcoming AMD hardware implements Smart Data Cache Injection (SDCI).
Smart Data Cache Injection (SDCI) is a mechanism that enables direct
insertion of data from I/O devices into the L3 cache. By directly caching
data from I/O devices rather than first storing the I/O data in DRAM, SDCI
reduces demands on DRAM bandwidth and reduces latency to the processor
consuming the I/O data.

The SDCIAE (SDCI Allocation Enforcement) PQE feature allows system software
to control the portion of the L3 cache used for SDCI devices.

When enabled, SDCIAE forces all SDCI lines to be placed into the L3 cache
partitions identified by the highest-supported L3_MASK_n register, where n
is the maximum supported CLOSID.

Since CLOSIDs are managed by resctrl fs it is least invasive to make
the "io_alloc is supported by maximum supported CLOSID" part of the
initial resctrl fs support for io_alloc. Take care not to expose this
use of CLOSID for io_alloc to user space so that this is not required from
other architectures that may support io_alloc differently in the future.

The SDCIAE feature details are documented in APM [1] available from [2].
[1] AMD64 Architecture Programmer's Manual Volume 2: System Programming
Publication # 24593 Revision 3.41 section 19.4.7 L3 Smart Data Cache
Injection Allocation Enforcement (SDCIAE)
Link: https://bugzilla.kernel.org/show_bug.cgi?id=206537 # [2]

The feature requires linux support of TPH (TLP Processing Hints).
The support is available in linux kernel after the commit
48d0fd2b903e3 ("PCI/TPH: Add TPH documentation")

The patches are based on top of commit (v6.17.0-rc4)
commit a1d91c792486 ("tip/master) Merge branch into tip/master: 'x86/tdx'").

Comments and suggestions are always welcome as usual.

# Linux Implementation

Feature adds following interface files when the resctrl "io_alloc" feature
is supported on the resource:

/sys/fs/resctrl/info/L3/io_alloc: Report the feature status. Enable/disable the
				  feature by writing to the interface.

/sys/fs/resctrl/info/L3/io_alloc_cbm:  List the Capacity Bit Masks (CBMs) available
				       for I/O devices when io_alloc feature is enabled.
				       Configure the CBM by writing to the interface.

When CDP is enabled, these files are created both in L3CODE and L3DATA.

# Examples:

a. Check if io_alloc feature is available.

	# mount -t resctrl resctrl /sys/fs/resctrl/

	# cat /sys/fs/resctrl/info/L3/io_alloc
	disabled

b. Enable the io_alloc feature. 

	# echo 1 > /sys/fs/resctrl/info/L3/io_alloc 
	# cat /sys/fs/resctrl/info/L3/io_alloc
	enabled

c. Check the CBM values for the io_alloc feature.

	# cat /sys/fs/resctrl/info/L3/io_alloc_cbm 
	0=ffff;1=ffff

d. Change the CBM value of domain 1.
	# echo 1=ff > /sys/fs/resctrl/info/L3/io_alloc_cbm

	# cat /sys/fs/resctrl/info/L3/io_alloc_cbm 
	0=ffff;1=00ff

e. Change the CBM value of domain 0 and 1.
	# echo 0=ff;1=f > /sys/fs/resctrl/info/L3/io_alloc_cbm

	# cat /sys/fs/resctrl/info/L3/io_alloc_cbm
	0=00ff;1=000f


f. Disable io_alloc feature and exit.

	# echo 0 > /sys/fs/resctrl/info/L3/io_alloc 
	# cat /sys/fs/resctrl/info/L3/io_alloc
	disabled

	# umount /sys/fs/resctrl/
---
v9:
  Major change is related to CDP.
  The processing and updating CBMs for CDP_CODE and CDP_DATA are done only once.
  The updated CBMs are copied to the peers using staged_config.
  
  Removed resctrl_get_schema(). Not required anymore.

  Updated the "bit_usage" section of resctrl.rst for io_alloc.

  Fixed the tabs in SMBA and BMEC lines in resctrl.rst.

  Improved the changelog for all the patches.
  
  Added the code comments about CDP_CODE and CDP_DATA where applicable.

  Added Reviewed-by: tag for couple of patches.
  
  Added comments in each patch about the changes.


v8:
  Added Acked-by, Reviewed-by tags to couple of patches.

  Updated Documentation/filesystems/resctrl.rst for each interface.
   
  Updated the changelog in most patches. 
  
  Moved the patch to update the rdt_bit_usage_show() for io_alloc changes to the end.
 
  Moved resctrl_arch_io_alloc_enable() and its dependancies to
  arch/x86/kernel/cpu/resctrl/ctrlmondata.c file.
  
  Moved resctrl_io_alloc_show() to fs/resctrl/ctrlmondata.c.
  Added prototype for rdt_kn_parent_priv() in fs/resctrl/internal.h
  so, it can be uses in other fs/resctrl/ files.
  
  Renamed resctrl_io_alloc_init_cat() to resctrl_io_alloc_init_cbm().
  Moved resctrl_io_alloc_write() and all its dependancies to fs/resctrl/ctrlmondata.c.
  Added prototypes for all the functions in fs/resctrl/internal.h.

  Moved resctrl_io_alloc_cbm_show() to fs/resctrl/ctrlmondata.c. show_doms remains
  static with this change.

  Moved resctrl_io_alloc_parse_line() and resctrl_io_alloc_cbm_write()
  to fs/resctrl/ctrlmondata.c.

  Added resctrl_arch_get_cdp_enabled() check inside resctrl_io_alloc_parse_line().
  parse_cbm() remains static as everything moved to ctrlmondata.c.

  Simplified the CDT check  in rdt_bit_usage_show() as CDP_DATA and CDP_CODE
  are in sync with io_alloc enabled.

v7:
  Fixed few conflicts in
  arch/x86/include/asm/cpufeatures.h
  arch/x86/kernel/cpu/scattered.c

  Updated the changelog in most patches. Removed the references of L3 in
  filesystem related changes.

  Removed the inline for resctrl_arch_get_io_alloc_enabled().
  Updated the code comment in resctrl.h.
  Changed the subject to x86,fs/resctrl where applicable.
 
  Split the patches based on the comment.
  https://lore.kernel.org/lkml/3bec3844-7fda-452b-988f-42b0de9d63ba@intel.com/
  Separated resctrl_io_alloc_show and bit_usage changes in two separate patches.

  Added new function resctrl_io_alloc_closid_supported() to verify io_alloc CLOSID.
 
  Added the code to initialize/update the schemata for both CDP_DATA and CDP_CODE when CDP is enabled.

  Rephrased the changelog and code comments in all the patches.

v6: 
   Sorry if you see this series duplicate. Messed up the
   emails linux-doc@vger.kernel.org and linux-kernel@vger.kernel.org.

   Sent v5 by mistake before completing all testing.
   Most of the changes are in resctrl.rst user doc.
   The resource name is no longer printed in io_alloc_cbms.
   Updated the related documentation accordingly.
   Resolved conflicts in cpufeatures.h
   Added lockdep_assert_cpus_held() in _resctrl_sdciae_enable() to protect
   r->ctrl_domains.

   Added more comments in include/linux/resctrl.h.

   Updated "io_alloc_cbm" details in user doc resctrl.rst. Resource name is
   not printed in CBM now.

   Updated subjects to fs/resctrl: where applicable.

v5: 
    Patches are created on top of recent resctrl FS/ARCH code restructure.
    The files monitor.c/rdtgroup.c have been split between FS and ARCH directories.
    Resolved the conflict due to the merge.

    Updated bit_usage to reflect the io_alloc CBM as discussed in the thread:
    https://lore.kernel.org/lkml/3ca0a5dc-ad9c-4767-9011-b79d986e1e8d@intel.com/
    Modified rdt_bit_usage_show() to read io_alloc_cbm in hw_shareable, ensuring
    that bit_usage accurately represents the CBMs.

    Moved prototypes of resctrl_arch_io_alloc_enable() and
    resctrl_arch_get_io_alloc_enabled() to include/linux/resctrl.h.

    Used rdt_kn_name to get the rdtgroup name instead of accesssing it directly
    while printing group name used by the io_alloc_closid.

    Updated show_doms() to print the resource if only it is valid. Pass NULL while
    printing io_alloc CBM.

    Changed the code to access io_alloc CBMs via either L3CODE or L3DATA resources.

v4: The "io_alloc" interface will report "enabled/disabled/not supported"
    instead of 0 or 1..

    Updated resctrl_io_alloc_closid_get() to verify the max closid availability
    using closids_supported().

    Updated the documentation for "shareable_bits" and "bit_usage".

    NOTE: io_alloc is about specific CLOS. rdt_bit_usage_show() is not designed
    handle bit_usage for specific CLOS. Its about overall system. So, we cannot
    really tell the user which CLOS is shared across both hardware and software.
    This is something we need to discuss.

    Introduced io_alloc_init() to initialize fflags.

    Printed the group name when io_alloc enablement fails to help user.
    
    Added rdtgroup_mutex before rdt_last_cmd_puts() in resctrl_io_alloc_cbm_show().
    Returned -ENODEV when resource type is CDP_DATA.

    Kept the resource name while printing the CBM (L3:0=ffff) that way we dont have
    to change show_doms() just for this feature and it is consistant across all the
    schemata display.

    Added new patch to call parse_cbm() directly to avoid code duplication.

    Checked all the series(v1-v3) again to verify if I missed any comment.

v3: Rewrote commit log for the last 3 patches. Changed the text to bit
    more generic than the AMD specific feature. Added AMD feature
    specifics in the end.

    Renamed the rdt_get_sdciae_alloc_cfg() to rdt_set_io_alloc_capable().
    Renamed the _resctrl_io_alloc_enable() to _resctrl_sdciae_enable()
    as it is arch specific.

    Changed the return to void in _resctrl_sdciae_enable() instead of int.
 
    The number of CLOSIDs is determined based on the minimum supported
    across all resources (in closid_init). It needs to match the max
    supported on the resource. Added the check to verify if MAX CLOSID
    availability on the system.

    Added CDP check to make sure io_alloc is configured in CDP_CODE.
    Highest CLOSID corresponds to CDP_CODE. 

    Added resctrl_io_alloc_closid_free() to free the io_alloc CLOSID.

    Added errors in few cases when CLOSID allocation fails.
    Fixes splat reported when info/L3/bit_usage is accesed when io_alloc is enabled.
    https://lore.kernel.org/lkml/SJ1PR11MB60837B532254E7B23BC27E84FC052@SJ1PR11MB6083.namprd11.prod.outlook.com/

v2: Added dependancy on X86_FEATURE_CAT_L3
    Removed the "" in CPU feature definition.

    Changed sdciae_capable to io_alloc_capable to make it as generic feature.
    Moved io_alloc_capable field in struct resctrl_cache.

    Changed the name of few arch functions similar to ABMC series.
    resctrl_arch_get_io_alloc_enabled()
    resctrl_arch_io_alloc_enable()

    Renamed the feature to "io_alloc".
    Added generic texts for the feature in commit log and resctrl.rst doc.
    Added resctrl_io_alloc_init_cat() to initialize io_alloc to default values
    when enabled.
    Fixed io_alloc interface to show only on L3 resource.
    Added the locks while processing io_alloc CBMs.

Previous versions:
v8: https://lore.kernel.org/lkml/cover.1754436586.git.babu.moger@amd.com/
v7: https://lore.kernel.org/lkml/cover.1752167718.git.babu.moger@amd.com/
v6: https://lore.kernel.org/lkml/cover.1749677012.git.babu.moger@amd.com/
v5: https://lore.kernel.org/lkml/cover.1747943499.git.babu.moger@amd.com/
v4: https://lore.kernel.org/lkml/cover.1745275431.git.babu.moger@amd.com/
v3: https://lore.kernel.org/lkml/cover.1738272037.git.babu.moger@amd.com/
v2: https://lore.kernel.org/lkml/cover.1734556832.git.babu.moger@amd.com/
v1: https://lore.kernel.org/lkml/cover.1723824984.git.babu.moger@amd.com/


Babu Moger (10):
  x86/cpufeatures: Add support for L3 Smart Data Cache Injection
    Allocation Enforcement
  x86/resctrl: Add SDCIAE feature in the command line options
  x86,fs/resctrl: Detect io_alloc feature
  x86,fs/resctrl: Implement "io_alloc" enable/disable handlers
  fs/resctrl: Introduce interface to display "io_alloc" support
  fs/resctrl: Add user interface to enable/disable io_alloc feature
  fs/resctrl: Introduce interface to display io_alloc CBMs
  fs/resctrl: Modify rdt_parse_data to pass mode and CLOSID
  fs/resctrl: Introduce interface to modify io_alloc Capacity Bit Masks
  fs/resctrl: Update bit_usage to reflect io_alloc

 .../admin-guide/kernel-parameters.txt         |   2 +-
 Documentation/filesystems/resctrl.rst         | 124 +++++--
 arch/x86/include/asm/cpufeatures.h            |   1 +
 arch/x86/include/asm/msr-index.h              |   1 +
 arch/x86/kernel/cpu/cpuid-deps.c              |   1 +
 arch/x86/kernel/cpu/resctrl/core.c            |   9 +
 arch/x86/kernel/cpu/resctrl/ctrlmondata.c     |  40 +++
 arch/x86/kernel/cpu/resctrl/internal.h        |   5 +
 arch/x86/kernel/cpu/scattered.c               |   1 +
 fs/resctrl/ctrlmondata.c                      | 305 +++++++++++++++++-
 fs/resctrl/internal.h                         |  24 ++
 fs/resctrl/rdtgroup.c                         |  77 ++++-
 include/linux/resctrl.h                       |  24 ++
 13 files changed, 570 insertions(+), 44 deletions(-)

---

## [2] Babu Moger — 2025-09-02
*Subject: [PATCH v9 01/10] x86/cpufeatures: Add support for L3 Smart Data Cache Injection Allocation Enforcement*

Smart Data Cache Injection (SDCI) is a mechanism that enables direct
insertion of data from I/O devices into the L3 cache. By directly caching
data from I/O devices rather than first storing the I/O data in DRAM,
SDCI reduces demands on DRAM bandwidth and reduces latency to the processor
consuming the I/O data.

The SDCIAE (SDCI Allocation Enforcement) PQE feature allows system software
to control the portion of the L3 cache used for SDCI.

When enabled, SDCIAE forces all SDCI lines to be placed into the L3 cache
partitions identified by the highest-supported L3_MASK_n register, where n
is the maximum supported CLOSID.

Add CPUID feature bit that can be used to configure SDCIAE.

The SDCIAE feature details are documented in APM [1] available from [2].
[1] AMD64 Architecture Programmer's Manual Volume 2: System Programming
Publication # 24593 Revision 3.41 section 19.4.7 L3 Smart Data Cache
Injection Allocation Enforcement (SDCIAE)

Link: https://bugzilla.kernel.org/show_bug.cgi?id=206537 # [2]
Signed-off-by: Babu Moger <babu.moger@amd.com>
Acked-by: Borislav Petkov (AMD) <bp@alien8.de>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v9: No changes.

v8: Added Acked-by, Reviewed-by tags.

v7: No changes. Fixed few conflicts in
   arch/x86/include/asm/cpufeatures.h
   arch/x86/kernel/cpu/scattered.c

v6: Resolved conflicts in cpufeatures.h.

v5: No changes.

v4: Resolved a minor conflict in cpufeatures.h.

v3: No changes.

v2: Added dependancy on X86_FEATURE_CAT_L3
    Removed the "" in CPU feature definition.
    Minor text changes.
---
 arch/x86/include/asm/cpufeatures.h | 1 +
 arch/x86/kernel/cpu/cpuid-deps.c   | 1 +
 arch/x86/kernel/cpu/scattered.c    | 1 +
 3 files changed, 3 insertions(+)

diff --git a/arch/x86/include/asm/cpufeatures.h b/arch/x86/include/asm/cpufeatures.h
index 06fc0479a23f..7a6afd605643 100644
--- a/arch/x86/include/asm/cpufeatures.h
+++ b/arch/x86/include/asm/cpufeatures.h
@@ -495,6 +495,7 @@
 #define X86_FEATURE_TSA_SQ_NO		(21*32+11) /* AMD CPU not vulnerable to TSA-SQ */
 #define X86_FEATURE_TSA_L1_NO		(21*32+12) /* AMD CPU not vulnerable to TSA-L1 */
 #define X86_FEATURE_CLEAR_CPU_BUF_VM	(21*32+13) /* Clear CPU buffers using VERW before VMRUN */
+#define X86_FEATURE_SDCIAE		(21*32+14) /* L3 Smart Data Cache Injection Allocation Enforcement */
 
 /*
  * BUG word(s)
diff --git a/arch/x86/kernel/cpu/cpuid-deps.c b/arch/x86/kernel/cpu/cpuid-deps.c
index 46efcbd6afa4..87e78586395b 100644
--- a/arch/x86/kernel/cpu/cpuid-deps.c
+++ b/arch/x86/kernel/cpu/cpuid-deps.c
@@ -72,6 +72,7 @@ static const struct cpuid_dep cpuid_deps[] = {
 	{ X86_FEATURE_CQM_MBM_LOCAL,		X86_FEATURE_CQM_LLC   },
 	{ X86_FEATURE_BMEC,			X86_FEATURE_CQM_MBM_TOTAL   },
 	{ X86_FEATURE_BMEC,			X86_FEATURE_CQM_MBM_LOCAL   },
+	{ X86_FEATURE_SDCIAE,			X86_FEATURE_CAT_L3    },
 	{ X86_FEATURE_AVX512_BF16,		X86_FEATURE_AVX512VL  },
 	{ X86_FEATURE_AVX512_FP16,		X86_FEATURE_AVX512BW  },
 	{ X86_FEATURE_ENQCMD,			X86_FEATURE_XSAVES    },
diff --git a/arch/x86/kernel/cpu/scattered.c b/arch/x86/kernel/cpu/scattered.c
index 6b868afb26c3..84fd8c04d328 100644
--- a/arch/x86/kernel/cpu/scattered.c
+++ b/arch/x86/kernel/cpu/scattered.c
@@ -51,6 +51,7 @@ static const struct cpuid_bit cpuid_bits[] = {
 	{ X86_FEATURE_COHERENCY_SFW_NO,		CPUID_EBX, 31, 0x8000001f, 0 },
 	{ X86_FEATURE_SMBA,			CPUID_EBX,  2, 0x80000020, 0 },
 	{ X86_FEATURE_BMEC,			CPUID_EBX,  3, 0x80000020, 0 },
+	{ X86_FEATURE_SDCIAE,			CPUID_EBX,  6, 0x80000020, 0 },
 	{ X86_FEATURE_TSA_SQ_NO,		CPUID_ECX,  1, 0x80000021, 0 },
 	{ X86_FEATURE_TSA_L1_NO,		CPUID_ECX,  2, 0x80000021, 0 },
 	{ X86_FEATURE_AMD_WORKLOAD_CLASS,	CPUID_EAX, 22, 0x80000021, 0 },

---

## [3] Babu Moger — 2025-09-02
*Subject: [PATCH v9 02/10] x86/resctrl: Add SDCIAE feature in the command line options*

Add the command line option to enable or disable the new resctrl feature
L3 Smart Data Cache Injection Allocation Enforcement (SDCIAE).

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v9: Minor changelog update.
    Fixed the tabs in SMBA and BMEC lines.

v8: Updated Documentation/filesystems/resctrl.rst.

v7: No changes.

v6: No changes.

v5: No changes.

v4: No changes.

v3: No changes.

v2: No changes.
---
 .../admin-guide/kernel-parameters.txt         |  2 +-
 Documentation/filesystems/resctrl.rst         | 21 ++++++++++---------
 arch/x86/kernel/cpu/resctrl/core.c            |  2 ++
 3 files changed, 14 insertions(+), 11 deletions(-)

diff --git a/Documentation/admin-guide/kernel-parameters.txt b/Documentation/admin-guide/kernel-parameters.txt
index 747a55abf494..398136902e23 100644
--- a/Documentation/admin-guide/kernel-parameters.txt
+++ b/Documentation/admin-guide/kernel-parameters.txt
@@ -6154,7 +6154,7 @@
 	rdt=		[HW,X86,RDT]
 			Turn on/off individual RDT features. List is:
 			cmt, mbmtotal, mbmlocal, l3cat, l3cdp, l2cat, l2cdp,
-			mba, smba, bmec.
+			mba, smba, bmec, sdciae.
 			E.g. to turn on cmt and turn off mba use:
 				rdt=cmt,!mba
 
diff --git a/Documentation/filesystems/resctrl.rst b/Documentation/filesystems/resctrl.rst
index c7949dd44f2f..4866a8a4189f 100644
--- a/Documentation/filesystems/resctrl.rst
+++ b/Documentation/filesystems/resctrl.rst
@@ -17,16 +17,17 @@ AMD refers to this feature as AMD Platform Quality of Service(AMD QoS).
 This feature is enabled by the CONFIG_X86_CPU_RESCTRL and the x86 /proc/cpuinfo
 flag bits:
 
-===============================================	================================
-RDT (Resource Director Technology) Allocation	"rdt_a"
-CAT (Cache Allocation Technology)		"cat_l3", "cat_l2"
-CDP (Code and Data Prioritization)		"cdp_l3", "cdp_l2"
-CQM (Cache QoS Monitoring)			"cqm_llc", "cqm_occup_llc"
-MBM (Memory Bandwidth Monitoring)		"cqm_mbm_total", "cqm_mbm_local"
-MBA (Memory Bandwidth Allocation)		"mba"
-SMBA (Slow Memory Bandwidth Allocation)         ""
-BMEC (Bandwidth Monitoring Event Configuration) ""
-===============================================	================================
+=============================================================== ================================
+RDT (Resource Director Technology) Allocation			"rdt_a"
+CAT (Cache Allocation Technology)				"cat_l3", "cat_l2"
+CDP (Code and Data Prioritization)				"cdp_l3", "cdp_l2"
+CQM (Cache QoS Monitoring)					"cqm_llc", "cqm_occup_llc"
+MBM (Memory Bandwidth Monitoring)				"cqm_mbm_total", "cqm_mbm_local"
+MBA (Memory Bandwidth Allocation)				"mba"
+SMBA (Slow Memory Bandwidth Allocation)				""
+BMEC (Bandwidth Monitoring Event Configuration)			""
+SDCIAE (Smart Data Cache Injection Allocation Enforcement)	""
+=============================================================== ================================
 
 Historically, new features were made visible by default in /proc/cpuinfo. This
 resulted in the feature flags becoming hard to parse by humans. Adding a new
diff --git a/arch/x86/kernel/cpu/resctrl/core.c b/arch/x86/kernel/cpu/resctrl/core.c
index 187d527ef73b..f6d84882cc4e 100644
--- a/arch/x86/kernel/cpu/resctrl/core.c
+++ b/arch/x86/kernel/cpu/resctrl/core.c
@@ -707,6 +707,7 @@ enum {
 	RDT_FLAG_MBA,
 	RDT_FLAG_SMBA,
 	RDT_FLAG_BMEC,
+	RDT_FLAG_SDCIAE,
 };
 
 #define RDT_OPT(idx, n, f)	\
@@ -732,6 +733,7 @@ static struct rdt_options rdt_options[]  __ro_after_init = {
 	RDT_OPT(RDT_FLAG_MBA,	    "mba",	X86_FEATURE_MBA),
 	RDT_OPT(RDT_FLAG_SMBA,	    "smba",	X86_FEATURE_SMBA),
 	RDT_OPT(RDT_FLAG_BMEC,	    "bmec",	X86_FEATURE_BMEC),
+	RDT_OPT(RDT_FLAG_SDCIAE,    "sdciae",	X86_FEATURE_SDCIAE),
 };
 #define NUM_RDT_OPTIONS ARRAY_SIZE(rdt_options)

---

## [4] Babu Moger — 2025-09-02
*Subject: [PATCH v9 03/10] x86,fs/resctrl: Detect io_alloc feature*

Smart Data Cache Injection (SDCI) is a mechanism that enables direct
insertion of data from I/O devices into the L3 cache. It can reduce the
demands on DRAM bandwidth and reduces latency to the processor consuming
the I/O data.

Introduce cache resource property "io_alloc_capable" that an architecture
can set if a portion of the cache can be allocated for I/O traffic.

Set this property on x86 systems that support SDCIAE (L3 Smart Data Cache
Injection Allocation Enforcement). This property is set only for the L3
cache resource on systems that support SDCIAE.

Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v9: No changes.

v8: Added Reviewed-by tag.

v7: Few text updates in changelog and resctrl.h.

v6: No changes.

v5: No changes.

v4: Updated the commit message and code comment based on feedback.

v3: Rewrote commit log. Changed the text to bit generic than the AMD specific.
    Renamed the rdt_get_sdciae_alloc_cfg() to rdt_set_io_alloc_capable().
    Removed leftover comment from v2.

v2: Changed sdciae_capable to io_alloc_capable to make it generic feature.
    Also moved the io_alloc_capable in struct resctrl_cache.
---
 arch/x86/kernel/cpu/resctrl/core.c | 7 +++++++
 include/linux/resctrl.h            | 3 +++
 2 files changed, 10 insertions(+)

diff --git a/arch/x86/kernel/cpu/resctrl/core.c b/arch/x86/kernel/cpu/resctrl/core.c
index f6d84882cc4e..1d1002526745 100644
--- a/arch/x86/kernel/cpu/resctrl/core.c
+++ b/arch/x86/kernel/cpu/resctrl/core.c
@@ -274,6 +274,11 @@ static void rdt_get_cdp_config(int level)
 	rdt_resources_all[level].r_resctrl.cdp_capable = true;
 }
 
+static void rdt_set_io_alloc_capable(struct rdt_resource *r)
+{
+	r->cache.io_alloc_capable = true;
+}
+
 static void rdt_get_cdp_l3_config(void)
 {
 	rdt_get_cdp_config(RDT_RESOURCE_L3);
@@ -842,6 +847,8 @@ static __init bool get_rdt_alloc_resources(void)
 		rdt_get_cache_alloc_cfg(1, r);
 		if (rdt_cpu_has(X86_FEATURE_CDP_L3))
 			rdt_get_cdp_l3_config();
+		if (rdt_cpu_has(X86_FEATURE_SDCIAE))
+			rdt_set_io_alloc_capable(r);
 		ret = true;
 	}
 	if (rdt_cpu_has(X86_FEATURE_CAT_L2)) {
diff --git a/include/linux/resctrl.h b/include/linux/resctrl.h
index 6fb4894b8cfd..010f238843b2 100644
--- a/include/linux/resctrl.h
+++ b/include/linux/resctrl.h
@@ -191,6 +191,8 @@ struct rdt_mon_domain {
  * @arch_has_sparse_bitmasks:	True if a bitmask like f00f is valid.
  * @arch_has_per_cpu_cfg:	True if QOS_CFG register for this cache
  *				level has CPU scope.
+ * @io_alloc_capable:	True if portion of the cache can be configured
+ *			for I/O traffic.
  */
 struct resctrl_cache {
 	unsigned int	cbm_len;
@@ -198,6 +200,7 @@ struct resctrl_cache {
 	unsigned int	shareable_bits;
 	bool		arch_has_sparse_bitmasks;
 	bool		arch_has_per_cpu_cfg;
+	bool		io_alloc_capable;
 };
 
 /**

---

## [5] Babu Moger — 2025-09-02
*Subject: [PATCH v9 04/10] x86,fs/resctrl: Implement "io_alloc" enable/disable handlers*

"io_alloc" enables direct insertion of data from I/O devices into the
cache.

On AMD systems, "io_alloc" feature is backed by L3 Smart Data Cache
Injection Allocation Enforcement (SDCIAE). Change SDCIAE state by setting
(to enable) or clearing (to disable) bit 1 of MSR L3_QOS_EXT_CFG on all
logical processors within the cache domain.

Introduce architecture-specific call to enable and disable the feature.

The SDCIAE feature details are documented in APM [1] available from [2].
[1] AMD64 Architecture Programmer's Manual Volume 2: System Programming
Publication # 24593 Revision 3.41 section 19.4.7 L3 Smart Data Cache
Injection Allocation Enforcement (SDCIAE)

Link: https://bugzilla.kernel.org/show_bug.cgi?id=206537 # [2]
Signed-off-by: Babu Moger <babu.moger@amd.com>
Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>
---
v9: Minor changelog update.
    Added Reviewed-by: tag.

v8: Moved resctrl_arch_io_alloc_enable() and its dependancies to
    arch/x86/kernel/cpu/resctrl/ctrlmondata.c file.

v7: Removed the inline for resctrl_arch_get_io_alloc_enabled().
    Update code comment in resctrl.h.
    Changed the subject to x86,fs/resctrl.

v6: Added lockdep_assert_cpus_held() in _resctrl_sdciae_enable() to protect
    r->ctrl_domains.
    Added more comments in include/linux/resctrl.h.

v5: Resolved conflicts due to recent resctrl FS/ARCH code restructure.
    The files monitor.c/rdtgroup.c have been split between FS and ARCH directories.
    Moved prototypes of resctrl_arch_io_alloc_enable() and
    resctrl_arch_get_io_alloc_enabled() to include/linux/resctrl.h.

v4: Updated the commit log to address the feedback.

v3: Passed the struct rdt_resource to resctrl_arch_get_io_alloc_enabled() instead of resource id.
    Renamed the _resctrl_io_alloc_enable() to _resctrl_sdciae_enable() as it is arch specific.
    Changed the return to void in _resctrl_sdciae_enable() instead of int.
    Added more context in commit log and fixed few typos.

v2: Renamed the functions to simplify the code.
    Renamed sdciae_capable to io_alloc_capable.

    Changed the name of few arch functions similar to ABMC series.
    resctrl_arch_get_io_alloc_enabled()
    resctrl_arch_io_alloc_enable()
---
 arch/x86/include/asm/msr-index.h          |  1 +
 arch/x86/kernel/cpu/resctrl/ctrlmondata.c | 40 +++++++++++++++++++++++
 arch/x86/kernel/cpu/resctrl/internal.h    |  5 +++
 include/linux/resctrl.h                   | 21 ++++++++++++
 4 files changed, 67 insertions(+)

diff --git a/arch/x86/include/asm/msr-index.h b/arch/x86/include/asm/msr-index.h
index f627196eb796..e20450fd6253 100644
--- a/arch/x86/include/asm/msr-index.h
+++ b/arch/x86/include/asm/msr-index.h
@@ -1225,6 +1225,7 @@
 /* - AMD: */
 #define MSR_IA32_MBA_BW_BASE		0xc0000200
 #define MSR_IA32_SMBA_BW_BASE		0xc0000280
+#define MSR_IA32_L3_QOS_EXT_CFG		0xc00003ff
 #define MSR_IA32_EVT_CFG_BASE		0xc0000400
 
 /* AMD-V MSRs */
diff --git a/arch/x86/kernel/cpu/resctrl/ctrlmondata.c b/arch/x86/kernel/cpu/resctrl/ctrlmondata.c
index 1189c0df4ad7..85b6bd6bfb81 100644
--- a/arch/x86/kernel/cpu/resctrl/ctrlmondata.c
+++ b/arch/x86/kernel/cpu/resctrl/ctrlmondata.c
@@ -91,3 +91,43 @@ u32 resctrl_arch_get_config(struct rdt_resource *r, struct rdt_ctrl_domain *d,
 
 	return hw_dom->ctrl_val[idx];
 }
+
+bool resctrl_arch_get_io_alloc_enabled(struct rdt_resource *r)
+{
+	return resctrl_to_arch_res(r)->sdciae_enabled;
+}
+
+static void resctrl_sdciae_set_one_amd(void *arg)
+{
+	bool *enable = arg;
+
+	if (*enable)
+		msr_set_bit(MSR_IA32_L3_QOS_EXT_CFG, SDCIAE_ENABLE_BIT);
+	else
+		msr_clear_bit(MSR_IA32_L3_QOS_EXT_CFG, SDCIAE_ENABLE_BIT);
+}
+
+static void _resctrl_sdciae_enable(struct rdt_resource *r, bool enable)
+{
+	struct rdt_ctrl_domain *d;
+
+	/* Walking r->ctrl_domains, ensure it can't race with cpuhp */
+	lockdep_assert_cpus_held();
+
+	/* Update L3_QOS_EXT_CFG MSR on all the CPUs in all domains */
+	list_for_each_entry(d, &r->ctrl_domains, hdr.list)
+		on_each_cpu_mask(&d->hdr.cpu_mask, resctrl_sdciae_set_one_amd, &enable, 1);
+}
+
+int resctrl_arch_io_alloc_enable(struct rdt_resource *r, bool enable)
+{
+	struct rdt_hw_resource *hw_res = resctrl_to_arch_res(r);
+
+	if (hw_res->r_resctrl.cache.io_alloc_capable &&
+	    hw_res->sdciae_enabled != enable) {
+		_resctrl_sdciae_enable(r, enable);
+		hw_res->sdciae_enabled = enable;
+	}
+
+	return 0;
+}
diff --git a/arch/x86/kernel/cpu/resctrl/internal.h b/arch/x86/kernel/cpu/resctrl/internal.h
index 5e3c41b36437..70f5317f1ce4 100644
--- a/arch/x86/kernel/cpu/resctrl/internal.h
+++ b/arch/x86/kernel/cpu/resctrl/internal.h
@@ -37,6 +37,9 @@ struct arch_mbm_state {
 	u64	prev_msr;
 };
 
+/* Setting bit 1 in L3_QOS_EXT_CFG enables the SDCIAE feature. */
+#define SDCIAE_ENABLE_BIT		1
+
 /**
  * struct rdt_hw_ctrl_domain - Arch private attributes of a set of CPUs that share
  *			       a resource for a control function
@@ -102,6 +105,7 @@ struct msr_param {
  * @mon_scale:		cqm counter * mon_scale = occupancy in bytes
  * @mbm_width:		Monitor width, to detect and correct for overflow.
  * @cdp_enabled:	CDP state of this resource
+ * @sdciae_enabled:	SDCIAE feature (backing "io_alloc") is enabled.
  *
  * Members of this structure are either private to the architecture
  * e.g. mbm_width, or accessed via helpers that provide abstraction. e.g.
@@ -115,6 +119,7 @@ struct rdt_hw_resource {
 	unsigned int		mon_scale;
 	unsigned int		mbm_width;
 	bool			cdp_enabled;
+	bool			sdciae_enabled;
 };
 
 static inline struct rdt_hw_resource *resctrl_to_arch_res(struct rdt_resource *r)
diff --git a/include/linux/resctrl.h b/include/linux/resctrl.h
index 010f238843b2..d98933ce77af 100644
--- a/include/linux/resctrl.h
+++ b/include/linux/resctrl.h
@@ -531,6 +531,27 @@ void resctrl_arch_reset_rmid_all(struct rdt_resource *r, struct rdt_mon_domain *
  */
 void resctrl_arch_reset_all_ctrls(struct rdt_resource *r);
 
+/**
+ * resctrl_arch_io_alloc_enable() - Enable/disable io_alloc feature.
+ * @r:		The resctrl resource.
+ * @enable:	Enable (true) or disable (false) io_alloc on resource @r.
+ *
+ * This can be called from any CPU.
+ *
+ * Return:
+ * 0 on success, <0 on error.
+ */
+int resctrl_arch_io_alloc_enable(struct rdt_resource *r, bool enable);
+
+/**
+ * resctrl_arch_get_io_alloc_enabled() - Get io_alloc feature state.
+ * @r:		The resctrl resource.
+ *
+ * Return:
+ * true if io_alloc is enabled or false if disabled.
+ */
+bool resctrl_arch_get_io_alloc_enabled(struct rdt_resource *r);
+
 extern unsigned int resctrl_rmid_realloc_threshold;
 extern unsigned int resctrl_rmid_realloc_limit;

---

## [6] Babu Moger — 2025-09-02
*Subject: [PATCH v9 05/10] fs/resctrl: Introduce interface to display "io_alloc" support*

"io_alloc" feature in resctrl allows direct insertion of data from I/O
devices into the cache.

Introduce the 'io_alloc' resctrl file to indicate the support for the
feature.

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v9: Minor user doc(resctrl.rst) update.

v8: Updated Documentation/filesystems/resctrl.rst.
    Moved resctrl_io_alloc_show() to fs/resctrl/ctrlmondata.c.
    Added prototype for rdt_kn_parent_priv() in fs/resctrl/internal.h
    so, it can be uses in other fs/resctrl/ files.
    Added comment for io_alloc_init().

v7: Updated the changelog.
    Updated user doc for io_alloc in resctrl.rst.
    Added mutex rdtgroup_mutex in resctrl_io_alloc_show();

v6: Added "io_alloc_cbm" details in user doc resctrl.rst.
    Resource name is not printed in CBM now. Corrected the texts about it
    in resctrl.rst.

v5: Resolved conflicts due to recent resctrl FS/ARCH code restructure.
    Updated show_doms() to print the resource if only it is valid. Pass NULL while
    printing io_alloc CBM.
    Changed the code to access the CBMs via either L3CODE or L3DATA resources.

v4: Updated the change log.
    Added rdtgroup_mutex before rdt_last_cmd_puts().
    Returned -ENODEV when resource type is CDP_DATA.
    Kept the resource name while printing the CBM (L3:0=fff) that way
    I dont have to change show_doms() just for this feature and it is
    consistant across all the schemata display.

v3: Minor changes due to changes in resctrl_arch_get_io_alloc_enabled()
    and resctrl_io_alloc_closid_get().
    Added the check to verify CDP resource type.
    Updated the commit log.

v2: Fixed to display only on L3 resources.
    Added the locks while processing.
    Rename the displat to io_alloc_cbm (from sdciae_cmd).
---
 Documentation/filesystems/resctrl.rst | 30 +++++++++++++++++++++++++++
 fs/resctrl/ctrlmondata.c              | 21 +++++++++++++++++++
 fs/resctrl/internal.h                 |  5 +++++
 fs/resctrl/rdtgroup.c                 | 24 ++++++++++++++++++++-
 4 files changed, 79 insertions(+), 1 deletion(-)

diff --git a/Documentation/filesystems/resctrl.rst b/Documentation/filesystems/resctrl.rst
index 4866a8a4189f..89aab17b00cb 100644
--- a/Documentation/filesystems/resctrl.rst
+++ b/Documentation/filesystems/resctrl.rst
@@ -136,6 +136,36 @@ related to allocation:
 			"1":
 			      Non-contiguous 1s value in CBM is supported.
 
+"io_alloc":
+		"io_alloc" enables system software to configure the portion of
+		the cache allocated for I/O traffic. File may only exist if the
+		system supports this feature on some of its cache resources.
+
+			"disabled":
+			      Resource supports "io_alloc" but the feature is disabled.
+			      Portions of cache used for allocation of I/O traffic cannot
+			      be configured.
+			"enabled":
+			      Portions of cache used for allocation of I/O traffic
+			      can be configured using "io_alloc_cbm".
+			"not supported":
+			      Support not available for this resource.
+
+		The underlying implementation may reduce resources available to
+		general (CPU) cache allocation. See architecture specific notes
+		below. Depending on usage requirements the feature can be enabled
+		or disabled.
+
+		On AMD systems, io_alloc feature is supported by the L3 Smart
+		Data Cache Injection Allocation Enforcement (SDCIAE). The CLOSID for
+		io_alloc is the highest CLOSID supported by the resource. When
+		io_alloc is enabled, the highest CLOSID is dedicated to io_alloc and
+		no longer available for general (CPU) cache allocation. When CDP is
+		enabled, io_alloc routes I/O traffic using the highest CLOSID allocated
+		for the instruction cache (L3CODE), making this CLOSID no longer
+		available for general (CPU) cache allocation for both the L3CODE and
+		L3DATA resources.
+
 Memory bandwidth(MB) subdirectory contains the following files
 with respect to allocation:
 
diff --git a/fs/resctrl/ctrlmondata.c b/fs/resctrl/ctrlmondata.c
index d98e0d2de09f..d495a5d5c9d5 100644
--- a/fs/resctrl/ctrlmondata.c
+++ b/fs/resctrl/ctrlmondata.c
@@ -664,3 +664,24 @@ int rdtgroup_mondata_show(struct seq_file *m, void *arg)
 	rdtgroup_kn_unlock(of->kn);
 	return ret;
 }
+
+int resctrl_io_alloc_show(struct kernfs_open_file *of, struct seq_file *seq, void *v)
+{
+	struct resctrl_schema *s = rdt_kn_parent_priv(of->kn);
+	struct rdt_resource *r = s->res;
+
+	mutex_lock(&rdtgroup_mutex);
+
+	if (r->cache.io_alloc_capable) {
+		if (resctrl_arch_get_io_alloc_enabled(r))
+			seq_puts(seq, "enabled\n");
+		else
+			seq_puts(seq, "disabled\n");
+	} else {
+		seq_puts(seq, "not supported\n");
+	}
+
+	mutex_unlock(&rdtgroup_mutex);
+
+	return 0;
+}
diff --git a/fs/resctrl/internal.h b/fs/resctrl/internal.h
index 0a1eedba2b03..1a4543c2b988 100644
--- a/fs/resctrl/internal.h
+++ b/fs/resctrl/internal.h
@@ -375,6 +375,11 @@ bool closid_allocated(unsigned int closid);
 
 int resctrl_find_cleanest_closid(void);
 
+int resctrl_io_alloc_show(struct kernfs_open_file *of, struct seq_file *seq,
+			  void *v);
+
+void *rdt_kn_parent_priv(struct kernfs_node *kn);
+
 #ifdef CONFIG_RESCTRL_FS_PSEUDO_LOCK
 int rdtgroup_locksetup_enter(struct rdtgroup *rdtgrp);
 
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index 5f0b7cfa1cc2..41ce2be4b2cb 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -981,7 +981,7 @@ static int rdt_last_cmd_status_show(struct kernfs_open_file *of,
 	return 0;
 }
 
-static void *rdt_kn_parent_priv(struct kernfs_node *kn)
+void *rdt_kn_parent_priv(struct kernfs_node *kn)
 {
 	/*
 	 * The parent pointer is only valid within RCU section since it can be
@@ -1893,6 +1893,12 @@ static struct rftype res_common_files[] = {
 		.kf_ops		= &rdtgroup_kf_single_ops,
 		.seq_show	= rdt_thread_throttle_mode_show,
 	},
+	{
+		.name		= "io_alloc",
+		.mode		= 0444,
+		.kf_ops		= &rdtgroup_kf_single_ops,
+		.seq_show	= resctrl_io_alloc_show,
+	},
 	{
 		.name		= "max_threshold_occupancy",
 		.mode		= 0644,
@@ -2062,6 +2068,20 @@ static void thread_throttle_mode_init(void)
 				 RFTYPE_CTRL_INFO | RFTYPE_RES_MB);
 }
 
+/*
+ * The resctrl file "io_alloc" is added using L3 resource. However, it results
+ * in this file being visible for *all* cache resources (eg. L2 cache),
+ * whether it supports "io_alloc" or not.
+ */
+static void io_alloc_init(void)
+{
+	struct rdt_resource *r = resctrl_arch_get_resource(RDT_RESOURCE_L3);
+
+	if (r->cache.io_alloc_capable)
+		resctrl_file_fflags_init("io_alloc", RFTYPE_CTRL_INFO |
+					 RFTYPE_RES_CACHE);
+}
+
 void resctrl_file_fflags_init(const char *config, unsigned long fflags)
 {
 	struct rftype *rft;
@@ -4246,6 +4266,8 @@ int resctrl_init(void)
 
 	thread_throttle_mode_init();
 
+	io_alloc_init();
+
 	ret = resctrl_mon_resource_init();
 	if (ret)
 		return ret;

---

## [7] Babu Moger — 2025-09-02
*Subject: [PATCH v9 06/10] fs/resctrl: Add user interface to enable/disable io_alloc feature*

"io_alloc" feature in resctrl enables direct insertion of data from I/O
devices into the cache.

On AMD systems, when io_alloc is enabled, the highest CLOSID is reserved
exclusively for I/O allocation traffic and is no longer available for
general CPU cache allocation. Users are encouraged to enable it only when
running workloads that can benefit from this functionality.

Since CLOSIDs are managed by resctrl fs, it is least invasive to make the
"io_alloc is supported by maximum supported CLOSID" part of the initial
resctrl fs support for io_alloc. Take care not to expose this use of CLOSID
for io_alloc to user space so that this is not required from other
architectures that may support io_alloc differently in the future.

Introduce user interface to enable/disable io_alloc feature. Check to
verify the availability of CLOSID reserved for io_alloc, and initialize
the CLOSID with a usable CBMs across all the domains.

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v9: Updated the changelog.
    Moved resctrl_arch_get_io_alloc_enabled() check earlier in the
    Removed resctrl_get_schema().
    Copied staged_config from peer when CDP is enabled.

v8: Updated the changelog.
    Renamed resctrl_io_alloc_init_cat() to resctrl_io_alloc_init_cbm().
    Moved resctrl_io_alloc_write() and all its dependancies to fs/resctrl/ctrlmondata.c.
    Added prototypes for all the functions in fs/resctrl/internal.h.

v7: Separated resctrl_io_alloc_show and bit_usage changes in two separate
    patches.
    Added resctrl_io_alloc_closid_supported() to verify io_alloc CLOSID.
    Initialized the schema for both CDP_DATA and CDP_CODE when CDP is enabled.

v6: Changed the subject to fs/resctrl:

v5: Resolved conflicts due to recent resctrl FS/ARCH code restructure.
    Used rdt_kn_name to get the rdtgroup name instead of accesssing it directly
    while printing group name used by the io_alloc_closid.

    Updated bit_usage to reflect the io_alloc CBM as discussed in the thread:
    https://lore.kernel.org/lkml/3ca0a5dc-ad9c-4767-9011-b79d986e1e8d@intel.com/
    Modified rdt_bit_usage_show() to read io_alloc_cbm in hw_shareable, ensuring
    that bit_usage accurately represents the CBMs.

    Updated the code to modify io_alloc either with L3CODE or L3DATA.
    https://lore.kernel.org/lkml/c00c00ea-a9ac-4c56-961c-dc5bf633476b@intel.com/

v4: Updated the change log.
    Updated the user doc.
    The "io_alloc" interface will report "enabled/disabled/not supported".
    Updated resctrl_io_alloc_closid_get() to verify the max closid availability.
    Updated the documentation for "shareable_bits" and "bit_usage".
    Introduced io_alloc_init() to initialize fflags.
    Printed the group name when io_alloc enablement fails.

    NOTE: io_alloc is about specific CLOS. rdt_bit_usage_show() is not designed
    handle bit_usage for specific CLOS. Its about overall system. So, we cannot
    really tell the user which CLOS is shared across both hardware and software.
    We need to discuss this.

v3: Rewrote the change to make it generic.
    Rewrote the documentation in resctrl.rst to be generic and added
    AMD feature details in the end.
    Added the check to verify if MAX CLOSID availability on the system.
    Added CDP check to make sure io_alloc is configured in CDP_CODE.
    Added resctrl_io_alloc_closid_free() to free the io_alloc CLOSID.
    Added errors in few cases when CLOSID allocation fails.
    Fixes splat reported when info/L3/bit_usage is accesed when io_alloc
    is enabled.
    https://lore.kernel.org/lkml/SJ1PR11MB60837B532254E7B23BC27E84FC052@SJ1PR11MB6083.namprd11.prod.outlook.com/

v2: Renamed the feature to "io_alloc".
    Added generic texts for the feature in commit log and resctrl.rst doc.
    Added resctrl_io_alloc_init_cat() to initialize io_alloc to default
    values when enabled.
    Fixed io_alloc show functinality to display only on L3 resource.
---
 Documentation/filesystems/resctrl.rst |   8 ++
 fs/resctrl/ctrlmondata.c              | 122 ++++++++++++++++++++++++++
 fs/resctrl/internal.h                 |  11 +++
 fs/resctrl/rdtgroup.c                 |  24 ++++-
 4 files changed, 162 insertions(+), 3 deletions(-)

diff --git a/Documentation/filesystems/resctrl.rst b/Documentation/filesystems/resctrl.rst
index 89aab17b00cb..55e35db0c6de 100644
--- a/Documentation/filesystems/resctrl.rst
+++ b/Documentation/filesystems/resctrl.rst
@@ -151,6 +151,14 @@ related to allocation:
 			"not supported":
 			      Support not available for this resource.
 
+		The feature can be modified by writing to the interface, for example:
+
+		To enable:
+			# echo 1 > /sys/fs/resctrl/info/L3/io_alloc
+
+		To disable:
+			# echo 0 > /sys/fs/resctrl/info/L3/io_alloc
+
 		The underlying implementation may reduce resources available to
 		general (CPU) cache allocation. See architecture specific notes
 		below. Depending on usage requirements the feature can be enabled
diff --git a/fs/resctrl/ctrlmondata.c b/fs/resctrl/ctrlmondata.c
index d495a5d5c9d5..1f714301f79f 100644
--- a/fs/resctrl/ctrlmondata.c
+++ b/fs/resctrl/ctrlmondata.c
@@ -685,3 +685,125 @@ int resctrl_io_alloc_show(struct kernfs_open_file *of, struct seq_file *seq, voi
 
 	return 0;
 }
+
+/*
+ * resctrl_io_alloc_closid_supported() - io_alloc feature utilizes the
+ * highest CLOSID value to direct I/O traffic. Ensure that io_alloc_closid
+ * is in the supported range.
+ */
+static bool resctrl_io_alloc_closid_supported(u32 io_alloc_closid)
+{
+	return io_alloc_closid < closids_supported();
+}
+
+/*
+ * Initialize io_alloc CLOSID cache resource CBM with all usable (shared
+ * and unused) cache portions.
+ */
+static int resctrl_io_alloc_init_cbm(struct resctrl_schema *s, u32 closid)
+{
+	enum resctrl_conf_type peer_type;
+	struct rdt_resource *r = s->res;
+	struct rdt_ctrl_domain *d;
+	int ret;
+
+	rdt_staged_configs_clear();
+
+	ret = rdtgroup_init_cat(s, closid);
+	if (ret < 0)
+		goto out;
+
+	/* Keep CDP_CODE and CDP_DATA of io_alloc CLOSID's CBM in sync. */
+	if (resctrl_arch_get_cdp_enabled(r->rid)) {
+		peer_type = resctrl_peer_type(s->conf_type);
+		list_for_each_entry(d, &s->res->ctrl_domains, hdr.list)
+			memcpy(&d->staged_config[peer_type],
+			       &d->staged_config[s->conf_type],
+			       sizeof(d->staged_config[0]));
+	}
+
+	ret = resctrl_arch_update_domains(r, closid);
+out:
+	rdt_staged_configs_clear();
+	return ret;
+}
+
+/*
+ * resctrl_io_alloc_closid() - io_alloc feature routes I/O traffic using
+ * the highest available CLOSID. Retrieve the maximum CLOSID supported by the
+ * resource. Note that if Code Data Prioritization (CDP) is enabled, the number
+ * of available CLOSIDs is reduced by half.
+ */
+static u32 resctrl_io_alloc_closid(struct rdt_resource *r)
+{
+	if (resctrl_arch_get_cdp_enabled(r->rid))
+		return resctrl_arch_get_num_closid(r) / 2  - 1;
+	else
+		return resctrl_arch_get_num_closid(r) - 1;
+}
+
+ssize_t resctrl_io_alloc_write(struct kernfs_open_file *of, char *buf,
+			       size_t nbytes, loff_t off)
+{
+	struct resctrl_schema *s = rdt_kn_parent_priv(of->kn);
+	struct rdt_resource *r = s->res;
+	char const *grp_name;
+	u32 io_alloc_closid;
+	bool enable;
+	int ret;
+
+	ret = kstrtobool(buf, &enable);
+	if (ret)
+		return ret;
+
+	cpus_read_lock();
+	mutex_lock(&rdtgroup_mutex);
+
+	rdt_last_cmd_clear();
+
+	if (!r->cache.io_alloc_capable) {
+		rdt_last_cmd_printf("io_alloc is not supported on %s\n", s->name);
+		ret = -ENODEV;
+		goto out_unlock;
+	}
+
+	/* If the feature is already up to date, no action is needed. */
+	if (resctrl_arch_get_io_alloc_enabled(r) == enable)
+		goto out_unlock;
+
+	io_alloc_closid = resctrl_io_alloc_closid(r);
+	if (!resctrl_io_alloc_closid_supported(io_alloc_closid)) {
+		rdt_last_cmd_printf("io_alloc CLOSID (ctrl_hw_id) %d is not available\n",
+				    io_alloc_closid);
+		ret = -EINVAL;
+		goto out_unlock;
+	}
+
+	if (enable) {
+		if (!closid_alloc_fixed(io_alloc_closid)) {
+			grp_name = rdtgroup_name_by_closid(io_alloc_closid);
+			WARN_ON_ONCE(!grp_name);
+			rdt_last_cmd_printf("CLOSID (ctrl_hw_id) %d for io_alloc is used by %s group\n",
+					    io_alloc_closid, grp_name ? grp_name : "another");
+			ret = -ENOSPC;
+			goto out_unlock;
+		}
+
+		ret = resctrl_io_alloc_init_cbm(s, io_alloc_closid);
+		if (ret) {
+			rdt_last_cmd_puts("Failed to initialize io_alloc allocations\n");
+			closid_free(io_alloc_closid);
+			goto out_unlock;
+		}
+	} else {
+		closid_free(io_alloc_closid);
+	}
+
+	ret = resctrl_arch_io_alloc_enable(r, enable);
+
+out_unlock:
+	mutex_unlock(&rdtgroup_mutex);
+	cpus_read_unlock();
+
+	return ret ?: nbytes;
+}
diff --git a/fs/resctrl/internal.h b/fs/resctrl/internal.h
index 1a4543c2b988..335def7af1f6 100644
--- a/fs/resctrl/internal.h
+++ b/fs/resctrl/internal.h
@@ -373,6 +373,8 @@ void rdt_staged_configs_clear(void);
 
 bool closid_allocated(unsigned int closid);
 
+bool closid_alloc_fixed(u32 closid);
+
 int resctrl_find_cleanest_closid(void);
 
 int resctrl_io_alloc_show(struct kernfs_open_file *of, struct seq_file *seq,
@@ -380,6 +382,15 @@ int resctrl_io_alloc_show(struct kernfs_open_file *of, struct seq_file *seq,
 
 void *rdt_kn_parent_priv(struct kernfs_node *kn);
 
+int rdtgroup_init_cat(struct resctrl_schema *s, u32 closid);
+
+enum resctrl_conf_type resctrl_peer_type(enum resctrl_conf_type my_type);
+
+ssize_t resctrl_io_alloc_write(struct kernfs_open_file *of, char *buf,
+			       size_t nbytes, loff_t off);
+
+const char *rdtgroup_name_by_closid(int closid);
+
 #ifdef CONFIG_RESCTRL_FS_PSEUDO_LOCK
 int rdtgroup_locksetup_enter(struct rdtgroup *rdtgrp);
 
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index 41ce2be4b2cb..ebf56782ed63 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -232,6 +232,11 @@ bool closid_allocated(unsigned int closid)
 	return !test_bit(closid, closid_free_map);
 }
 
+bool closid_alloc_fixed(u32 closid)
+{
+	return __test_and_clear_bit(closid, closid_free_map);
+}
+
 /**
  * rdtgroup_mode_by_closid - Return mode of resource group with closid
  * @closid: closid if the resource group
@@ -1250,7 +1255,7 @@ static int rdtgroup_mode_show(struct kernfs_open_file *of,
 	return 0;
 }
 
-static enum resctrl_conf_type resctrl_peer_type(enum resctrl_conf_type my_type)
+enum resctrl_conf_type resctrl_peer_type(enum resctrl_conf_type my_type)
 {
 	switch (my_type) {
 	case CDP_CODE:
@@ -1803,6 +1808,18 @@ static ssize_t mbm_local_bytes_config_write(struct kernfs_open_file *of,
 	return ret ?: nbytes;
 }
 
+const char *rdtgroup_name_by_closid(int closid)
+{
+	struct rdtgroup *rdtgrp;
+
+	list_for_each_entry(rdtgrp, &rdt_all_groups, rdtgroup_list) {
+		if (rdtgrp->closid == closid)
+			return rdt_kn_name(rdtgrp->kn);
+	}
+
+	return NULL;
+}
+
 /* rdtgroup information files for one cache resource. */
 static struct rftype res_common_files[] = {
 	{
@@ -1895,9 +1912,10 @@ static struct rftype res_common_files[] = {
 	},
 	{
 		.name		= "io_alloc",
-		.mode		= 0444,
+		.mode		= 0644,
 		.kf_ops		= &rdtgroup_kf_single_ops,
 		.seq_show	= resctrl_io_alloc_show,
+		.write          = resctrl_io_alloc_write,
 	},
 	{
 		.name		= "max_threshold_occupancy",
@@ -3362,7 +3380,7 @@ static int __init_one_rdt_domain(struct rdt_ctrl_domain *d, struct resctrl_schem
  * If there are no more shareable bits available on any domain then
  * the entire allocation will fail.
  */
-static int rdtgroup_init_cat(struct resctrl_schema *s, u32 closid)
+int rdtgroup_init_cat(struct resctrl_schema *s, u32 closid)
 {
 	struct rdt_ctrl_domain *d;
 	int ret;

---

## [8] Babu Moger — 2025-09-02
*Subject: [PATCH v9 07/10] fs/resctrl: Introduce interface to display io_alloc CBMs*

The io_alloc feature in resctrl enables system software to configure
the portion of the cache allocated for I/O traffic.

Add "io_alloc_cbm" resctrl file to display the Capacity Bit Masks (CBMs)
that represent the portion of each cache instance allocated for I/O
traffic.

The CBM interface file io_alloc_cbm resides in the info directory (e.g.,
/sys/fs/resctrl/info/L3/). Since the resource name is part of the path, it
is not necessary to display the resource name as done in the schemata file.
Pass the resource name to show_doms() and print it only if the name is
valid. For io_alloc, pass NULL pointer to suppress printing the resource
name.

When CDP is enabled, io_alloc routes traffic using the highest CLOSID
associated with the L3CODE resource. To ensure consistent cache allocation
behavior, the L3CODE and L3DATA resources are kept in sync. So, the
Capacity Bit Masks (CBMs) accessed through either L3CODE or L3DATA will
reflect identical values.

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v9: Updated the changelog with respect to CDP.
    Added code comment in resctrl_io_alloc_cbm_show().

v8: Updated the changelog.
    Moved resctrl_io_alloc_cbm_show() to fs/resctrl/ctrlmondata.c.
    show_doms is remains static with this change.

v7: Updated changelog.
    Updated use doc (resctrl.rst).
    Removed if (io_alloc_closid < 0) check. Not required anymore.

v6: Added "io_alloc_cbm" details in user doc resctrl.rst.
    Resource name is not printed in CBM now. Corrected the texts about it
    in resctrl.rst.

v5: Resolved conflicts due to recent resctrl FS/ARCH code restructure.
    Updated show_doms() to print the resource if only it is valid. Pass NULL while
    printing io_alloc CBM.
    Changed the code to access the CBMs via either L3CODE or L3DATA resources.

v4: Updated the change log.
    Added rdtgroup_mutex before rdt_last_cmd_puts().
    Returned -ENODEV when resource type is CDP_DATA.
    Kept the resource name while printing the CBM (L3:0=fff) that way
    I dont have to change show_doms() just for this feature and it is
    consistant across all the schemata display.

v3: Minor changes due to changes in resctrl_arch_get_io_alloc_enabled()
    and resctrl_io_alloc_closid_get().
    Added the check to verify CDP resource type.
    Updated the commit log.

v2: Fixed to display only on L3 resources.
    Added the locks while processing.
    Rename the displat to io_alloc_cbm (from sdciae_cmd).
---
 Documentation/filesystems/resctrl.rst | 19 +++++++++++
 fs/resctrl/ctrlmondata.c              | 45 +++++++++++++++++++++++++--
 fs/resctrl/internal.h                 |  3 ++
 fs/resctrl/rdtgroup.c                 | 11 ++++++-
 4 files changed, 74 insertions(+), 4 deletions(-)

diff --git a/Documentation/filesystems/resctrl.rst b/Documentation/filesystems/resctrl.rst
index 55e35db0c6de..15e3a4abf90e 100644
--- a/Documentation/filesystems/resctrl.rst
+++ b/Documentation/filesystems/resctrl.rst
@@ -174,6 +174,25 @@ related to allocation:
 		available for general (CPU) cache allocation for both the L3CODE and
 		L3DATA resources.
 
+"io_alloc_cbm":
+		CBMs(Capacity Bit Masks) that describe the portions of cache instances
+		to which I/O traffic from supported I/O devices are routed when "io_alloc"
+		is enabled.
+
+		CBMs are displayed in the following format:
+
+			<cache_id0>=<cbm>;<cache_id1>=<cbm>;...
+
+		Example::
+
+			# cat /sys/fs/resctrl/info/L3/io_alloc_cbm
+			0=ffff;1=ffff
+
+		When CDP is enabled "io_alloc_cbm" associated with the DATA and CODE
+		resources may reflect the same values. For example, values read from and
+		written to /sys/fs/resctrl/info/L3DATA/io_alloc_cbm may be reflected by
+		/sys/fs/resctrl/info/L3CODE/io_alloc_cbm and vice versa.
+
 Memory bandwidth(MB) subdirectory contains the following files
 with respect to allocation:
 
diff --git a/fs/resctrl/ctrlmondata.c b/fs/resctrl/ctrlmondata.c
index 1f714301f79f..d1a54f6c4876 100644
--- a/fs/resctrl/ctrlmondata.c
+++ b/fs/resctrl/ctrlmondata.c
@@ -381,7 +381,8 @@ ssize_t rdtgroup_schemata_write(struct kernfs_open_file *of,
 	return ret ?: nbytes;
 }
 
-static void show_doms(struct seq_file *s, struct resctrl_schema *schema, int closid)
+static void show_doms(struct seq_file *s, struct resctrl_schema *schema,
+		      char *resource_name, int closid)
 {
 	struct rdt_resource *r = schema->res;
 	struct rdt_ctrl_domain *dom;
@@ -391,7 +392,8 @@ static void show_doms(struct seq_file *s, struct resctrl_schema *schema, int clo
 	/* Walking r->domains, ensure it can't race with cpuhp */
 	lockdep_assert_cpus_held();
 
-	seq_printf(s, "%*s:", max_name_width, schema->name);
+	if (resource_name)
+		seq_printf(s, "%*s:", max_name_width, resource_name);
 	list_for_each_entry(dom, &r->ctrl_domains, hdr.list) {
 		if (sep)
 			seq_puts(s, ";");
@@ -437,7 +439,7 @@ int rdtgroup_schemata_show(struct kernfs_open_file *of,
 			closid = rdtgrp->closid;
 			list_for_each_entry(schema, &resctrl_schema_all, list) {
 				if (closid < schema->num_closid)
-					show_doms(s, schema, closid);
+					show_doms(s, schema, schema->name, closid);
 			}
 		}
 	} else {
@@ -807,3 +809,40 @@ ssize_t resctrl_io_alloc_write(struct kernfs_open_file *of, char *buf,
 
 	return ret ?: nbytes;
 }
+
+int resctrl_io_alloc_cbm_show(struct kernfs_open_file *of, struct seq_file *seq, void *v)
+{
+	struct resctrl_schema *s = rdt_kn_parent_priv(of->kn);
+	struct rdt_resource *r = s->res;
+	int ret = 0;
+
+	cpus_read_lock();
+	mutex_lock(&rdtgroup_mutex);
+
+	rdt_last_cmd_clear();
+
+	if (!r->cache.io_alloc_capable) {
+		rdt_last_cmd_printf("io_alloc is not supported on %s\n", s->name);
+		ret = -ENODEV;
+		goto out_unlock;
+	}
+
+	if (!resctrl_arch_get_io_alloc_enabled(r)) {
+		rdt_last_cmd_printf("io_alloc is not enabled on %s\n", s->name);
+		ret = -EINVAL;
+		goto out_unlock;
+	}
+
+	/*
+	 * When CDP is enabled, resctrl_io_alloc_init_cbm() sets the same CBM for
+	 * both L3CODE and L3DATA of the highest CLOSID. As a result, the io_alloc
+	 * CBMs shown for either CDP resource are identical and accurately represent
+	 * the CBMs used for I/O.
+	 */
+	show_doms(seq, s, NULL, resctrl_io_alloc_closid(r));
+
+out_unlock:
+	mutex_unlock(&rdtgroup_mutex);
+	cpus_read_unlock();
+	return ret;
+}
diff --git a/fs/resctrl/internal.h b/fs/resctrl/internal.h
index 335def7af1f6..49934cd3dc40 100644
--- a/fs/resctrl/internal.h
+++ b/fs/resctrl/internal.h
@@ -389,6 +389,9 @@ enum resctrl_conf_type resctrl_peer_type(enum resctrl_conf_type my_type);
 ssize_t resctrl_io_alloc_write(struct kernfs_open_file *of, char *buf,
 			       size_t nbytes, loff_t off);
 
+int resctrl_io_alloc_cbm_show(struct kernfs_open_file *of, struct seq_file *seq,
+			      void *v);
+
 const char *rdtgroup_name_by_closid(int closid);
 
 #ifdef CONFIG_RESCTRL_FS_PSEUDO_LOCK
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index ebf56782ed63..71003328fdda 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -1917,6 +1917,12 @@ static struct rftype res_common_files[] = {
 		.seq_show	= resctrl_io_alloc_show,
 		.write          = resctrl_io_alloc_write,
 	},
+	{
+		.name		= "io_alloc_cbm",
+		.mode		= 0444,
+		.kf_ops		= &rdtgroup_kf_single_ops,
+		.seq_show	= resctrl_io_alloc_cbm_show,
+	},
 	{
 		.name		= "max_threshold_occupancy",
 		.mode		= 0644,
@@ -2095,9 +2101,12 @@ static void io_alloc_init(void)
 {
 	struct rdt_resource *r = resctrl_arch_get_resource(RDT_RESOURCE_L3);
 
-	if (r->cache.io_alloc_capable)
+	if (r->cache.io_alloc_capable) {
 		resctrl_file_fflags_init("io_alloc", RFTYPE_CTRL_INFO |
 					 RFTYPE_RES_CACHE);
+		resctrl_file_fflags_init("io_alloc_cbm",
+					 RFTYPE_CTRL_INFO | RFTYPE_RES_CACHE);
+	}
 }
 
 void resctrl_file_fflags_init(const char *config, unsigned long fflags)

---

## [9] Babu Moger — 2025-09-02
*Subject: [PATCH v9 08/10] fs/resctrl: Modify rdt_parse_data to pass mode and CLOSID*

parse_cbm() require resource group mode and CLOSID to validate the Capacity
Bit Mask (CBM). It is passed via struct rdtgroup in struct rdt_parse_data.

The io_alloc feature also uses CBMs to indicate which portions of cache are
allocated for I/O traffic. The CBMs are provided by user space and need to
be validated the same as CBMs provided for general (CPU) cache allocation.
parse_cbm() cannot be used as-is since io_alloc does not have rdtgroup
context.

Pass the resource group mode and CLOSID directly to parse_cbm() via struct
rdt_parse_data, instead of through the rdtgroup struct, to facilitate
calling parse_cbm() to verify the CBM of the io_alloc feature.

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v9: Rephrase of changelog.
    Minor code syntax update.

v8: Rephrase of changelog.

v7: Rephrase of changelog.

v6: Changed the subject line to fs/resctrl.

v5: Resolved conflicts due to recent resctrl FS/ARCH code restructure.

v4: New patch to call parse_cbm() directly to avoid code duplication.
---
 fs/resctrl/ctrlmondata.c | 24 +++++++++++++-----------
 1 file changed, 13 insertions(+), 11 deletions(-)

diff --git a/fs/resctrl/ctrlmondata.c b/fs/resctrl/ctrlmondata.c
index d1a54f6c4876..a4e861733a95 100644
--- a/fs/resctrl/ctrlmondata.c
+++ b/fs/resctrl/ctrlmondata.c
@@ -24,7 +24,8 @@
 #include "internal.h"
 
 struct rdt_parse_data {
-	struct rdtgroup		*rdtgrp;
+	u32			closid;
+	enum rdtgrp_mode	mode;
 	char			*buf;
 };
 
@@ -77,8 +78,8 @@ static int parse_bw(struct rdt_parse_data *data, struct resctrl_schema *s,
 		    struct rdt_ctrl_domain *d)
 {
 	struct resctrl_staged_config *cfg;
-	u32 closid = data->rdtgrp->closid;
 	struct rdt_resource *r = s->res;
+	u32 closid = data->closid;
 	u32 bw_val;
 
 	cfg = &d->staged_config[s->conf_type];
@@ -156,9 +157,10 @@ static bool cbm_validate(char *buf, u32 *data, struct rdt_resource *r)
 static int parse_cbm(struct rdt_parse_data *data, struct resctrl_schema *s,
 		     struct rdt_ctrl_domain *d)
 {
-	struct rdtgroup *rdtgrp = data->rdtgrp;
+	enum rdtgrp_mode mode = data->mode;
 	struct resctrl_staged_config *cfg;
 	struct rdt_resource *r = s->res;
+	u32 closid = data->closid;
 	u32 cbm_val;
 
 	cfg = &d->staged_config[s->conf_type];
@@ -171,7 +173,7 @@ static int parse_cbm(struct rdt_parse_data *data, struct resctrl_schema *s,
 	 * Cannot set up more than one pseudo-locked region in a cache
 	 * hierarchy.
 	 */
-	if (rdtgrp->mode == RDT_MODE_PSEUDO_LOCKSETUP &&
+	if (mode == RDT_MODE_PSEUDO_LOCKSETUP &&
 	    rdtgroup_pseudo_locked_in_hierarchy(d)) {
 		rdt_last_cmd_puts("Pseudo-locked region in hierarchy\n");
 		return -EINVAL;
@@ -180,8 +182,7 @@ static int parse_cbm(struct rdt_parse_data *data, struct resctrl_schema *s,
 	if (!cbm_validate(data->buf, &cbm_val, r))
 		return -EINVAL;
 
-	if ((rdtgrp->mode == RDT_MODE_EXCLUSIVE ||
-	     rdtgrp->mode == RDT_MODE_SHAREABLE) &&
+	if ((mode == RDT_MODE_EXCLUSIVE || mode == RDT_MODE_SHAREABLE) &&
 	    rdtgroup_cbm_overlaps_pseudo_locked(d, cbm_val)) {
 		rdt_last_cmd_puts("CBM overlaps with pseudo-locked region\n");
 		return -EINVAL;
@@ -191,14 +192,14 @@ static int parse_cbm(struct rdt_parse_data *data, struct resctrl_schema *s,
 	 * The CBM may not overlap with the CBM of another closid if
 	 * either is exclusive.
 	 */
-	if (rdtgroup_cbm_overlaps(s, d, cbm_val, rdtgrp->closid, true)) {
+	if (rdtgroup_cbm_overlaps(s, d, cbm_val, closid, true)) {
 		rdt_last_cmd_puts("Overlaps with exclusive group\n");
 		return -EINVAL;
 	}
 
-	if (rdtgroup_cbm_overlaps(s, d, cbm_val, rdtgrp->closid, false)) {
-		if (rdtgrp->mode == RDT_MODE_EXCLUSIVE ||
-		    rdtgrp->mode == RDT_MODE_PSEUDO_LOCKSETUP) {
+	if (rdtgroup_cbm_overlaps(s, d, cbm_val, closid, false)) {
+		if (mode == RDT_MODE_EXCLUSIVE ||
+		    mode == RDT_MODE_PSEUDO_LOCKSETUP) {
 			rdt_last_cmd_puts("Overlaps with other group\n");
 			return -EINVAL;
 		}
@@ -262,7 +263,8 @@ static int parse_line(char *line, struct resctrl_schema *s,
 	list_for_each_entry(d, &r->ctrl_domains, hdr.list) {
 		if (d->hdr.id == dom_id) {
 			data.buf = dom;
-			data.rdtgrp = rdtgrp;
+			data.closid = rdtgrp->closid;
+			data.mode = rdtgrp->mode;
 			if (parse_ctrlval(&data, s, d))
 				return -EINVAL;
 			if (rdtgrp->mode ==  RDT_MODE_PSEUDO_LOCKSETUP) {

---

## [10] Babu Moger — 2025-09-02
*Subject: [PATCH v9 09/10] fs/resctrl: Introduce interface to modify io_alloc Capacity Bit Masks*

The io_alloc feature in resctrl enables system software to configure the
portion of the cache allocated for I/O traffic. When supported, the
io_alloc_cbm file in resctrl provides access to Capacity Bit Masks (CBMs)
reserved for I/O devices.

Enable users to modify io_alloc CBMs (Capacity Bit Masks) via the
io_alloc_cbm resctrl file when io_alloc is enabled.

To ensure consistent cache allocation when CDP is enabled, the CBMs
written to either L3CODE or L3DATA are mirrored to the other, keeping both
resource types synchronized.

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v9: Rewrote the changelog.
    Removed duplicated rdt_last_cmd_clear().
    Corrected rdt_staged_configs_clear() placement.
    Added one more example to update the schemata with multiple domains.
    Copied staged_config from peer when CDP is enabled.

v8: Updated changelog.
    Moved resctrl_io_alloc_parse_line() and resctrl_io_alloc_cbm_write() to
    fs/resctrl/ctrlmondata.c.
    Added resctrl_arch_get_cdp_enabled() check inside resctrl_io_alloc_parse_line().
    Made parse_cbm() static again as everything moved to ctrlmondata.c.

v7: Updated changelog.
    Updated CBMs for both CDP_DATA and CDP_CODE when CDP is enabled.

v6: Updated the user doc restctr.doc for minor texts.
    Changed the subject to fs/resctrl.

v5: Changes due to FS/ARCH code restructure. The files monitor.c/rdtgroup.c
    have been split between FS and ARCH directories.
    Changed the code to access the CBMs via either L3CODE or L3DATA resources.

v4: Removed resctrl_io_alloc_parse_cbm and called parse_cbm() directly.

v3: Minor changes due to changes in resctrl_arch_get_io_alloc_enabled()
    and resctrl_io_alloc_closid_get().
    Taken care of handling the CBM update when CDP is enabled.
    Updated the commit log to make it generic.

v2: Added more generic text in documentation.
---
 Documentation/filesystems/resctrl.rst | 11 ++++
 fs/resctrl/ctrlmondata.c              | 93 +++++++++++++++++++++++++++
 fs/resctrl/internal.h                 |  3 +
 fs/resctrl/rdtgroup.c                 |  3 +-
 4 files changed, 109 insertions(+), 1 deletion(-)

diff --git a/Documentation/filesystems/resctrl.rst b/Documentation/filesystems/resctrl.rst
index 15e3a4abf90e..7e3eda324de5 100644
--- a/Documentation/filesystems/resctrl.rst
+++ b/Documentation/filesystems/resctrl.rst
@@ -188,6 +188,17 @@ related to allocation:
 			# cat /sys/fs/resctrl/info/L3/io_alloc_cbm
 			0=ffff;1=ffff
 
+		CBMs can be configured by writing to the interface.
+
+		Example::
+
+			# echo 1=ff > /sys/fs/resctrl/info/L3/io_alloc_cbm
+			# cat /sys/fs/resctrl/info/L3/io_alloc_cbm
+			0=ffff;1=00ff
+			# echo 0=ff;1=f > /sys/fs/resctrl/info/L3/io_alloc_cbm
+			# cat /sys/fs/resctrl/info/L3/io_alloc_cbm
+			0=00ff;1=000f
+
 		When CDP is enabled "io_alloc_cbm" associated with the DATA and CODE
 		resources may reflect the same values. For example, values read from and
 		written to /sys/fs/resctrl/info/L3DATA/io_alloc_cbm may be reflected by
diff --git a/fs/resctrl/ctrlmondata.c b/fs/resctrl/ctrlmondata.c
index a4e861733a95..791ecb559b50 100644
--- a/fs/resctrl/ctrlmondata.c
+++ b/fs/resctrl/ctrlmondata.c
@@ -848,3 +848,96 @@ int resctrl_io_alloc_cbm_show(struct kernfs_open_file *of, struct seq_file *seq,
 	cpus_read_unlock();
 	return ret;
 }
+
+static int resctrl_io_alloc_parse_line(char *line,  struct rdt_resource *r,
+				       struct resctrl_schema *s, u32 closid)
+{
+	enum resctrl_conf_type peer_type;
+	struct rdt_parse_data data;
+	struct rdt_ctrl_domain *d;
+	char *dom = NULL, *id;
+	unsigned long dom_id;
+
+next:
+	if (!line || line[0] == '\0')
+		return 0;
+
+	dom = strsep(&line, ";");
+	id = strsep(&dom, "=");
+	if (!dom || kstrtoul(id, 10, &dom_id)) {
+		rdt_last_cmd_puts("Missing '=' or non-numeric domain\n");
+		return -EINVAL;
+	}
+
+	dom = strim(dom);
+	list_for_each_entry(d, &r->ctrl_domains, hdr.list) {
+		if (d->hdr.id == dom_id) {
+			data.buf = dom;
+			data.mode = RDT_MODE_SHAREABLE;
+			data.closid = closid;
+			if (parse_cbm(&data, s, d))
+				return -EINVAL;
+			/*
+			 * When CDP is enabled, update the schema for both CDP_DATA
+			 * and CDP_CODE.
+			 */
+			if (resctrl_arch_get_cdp_enabled(r->rid)) {
+				peer_type = resctrl_peer_type(s->conf_type);
+				memcpy(&d->staged_config[peer_type],
+				       &d->staged_config[s->conf_type],
+				       sizeof(d->staged_config[0]));
+			}
+			goto next;
+		}
+	}
+
+	return -EINVAL;
+}
+
+ssize_t resctrl_io_alloc_cbm_write(struct kernfs_open_file *of, char *buf,
+				   size_t nbytes, loff_t off)
+{
+	struct resctrl_schema *s = rdt_kn_parent_priv(of->kn);
+	struct rdt_resource *r = s->res;
+	u32 io_alloc_closid;
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
+	rdt_last_cmd_clear();
+
+	if (!r->cache.io_alloc_capable) {
+		rdt_last_cmd_printf("io_alloc is not supported on %s\n", s->name);
+		ret = -ENODEV;
+		goto out_unlock;
+	}
+
+	if (!resctrl_arch_get_io_alloc_enabled(r)) {
+		rdt_last_cmd_printf("io_alloc is not enabled on %s\n", s->name);
+		ret = -ENODEV;
+		goto out_unlock;
+	}
+
+	io_alloc_closid = resctrl_io_alloc_closid(r);
+
+	rdt_staged_configs_clear();
+	ret = resctrl_io_alloc_parse_line(buf, r, s, io_alloc_closid);
+	if (ret)
+		goto out_clear_configs;
+
+	ret = resctrl_arch_update_domains(r, io_alloc_closid);
+
+out_clear_configs:
+	rdt_staged_configs_clear();
+out_unlock:
+	mutex_unlock(&rdtgroup_mutex);
+	cpus_read_unlock();
+
+	return ret ?: nbytes;
+}
diff --git a/fs/resctrl/internal.h b/fs/resctrl/internal.h
index 49934cd3dc40..5467c3ad1b6d 100644
--- a/fs/resctrl/internal.h
+++ b/fs/resctrl/internal.h
@@ -392,6 +392,9 @@ ssize_t resctrl_io_alloc_write(struct kernfs_open_file *of, char *buf,
 int resctrl_io_alloc_cbm_show(struct kernfs_open_file *of, struct seq_file *seq,
 			      void *v);
 
+ssize_t resctrl_io_alloc_cbm_write(struct kernfs_open_file *of, char *buf,
+				   size_t nbytes, loff_t off);
+
 const char *rdtgroup_name_by_closid(int closid);
 
 #ifdef CONFIG_RESCTRL_FS_PSEUDO_LOCK
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index 71003328fdda..ddac021c02d8 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -1919,9 +1919,10 @@ static struct rftype res_common_files[] = {
 	},
 	{
 		.name		= "io_alloc_cbm",
-		.mode		= 0444,
+		.mode		= 0644,
 		.kf_ops		= &rdtgroup_kf_single_ops,
 		.seq_show	= resctrl_io_alloc_cbm_show,
+		.write		= resctrl_io_alloc_cbm_write,
 	},
 	{
 		.name		= "max_threshold_occupancy",

---

## [11] Babu Moger — 2025-09-02
*Subject: [PATCH v9 10/10] fs/resctrl: Update bit_usage to reflect io_alloc*

When the io_alloc feature is enabled, a portion of the cache can be
configured for shared use between hardware and software.

Update bit_usage representation to reflect the io_alloc configuration.
Revise the documentation for "shareable_bits" and "bit_usage" to reflect
the impact of io_alloc feature.

Signed-off-by: Babu Moger <babu.moger@amd.com>
---
v9: Changelog update.
    Added code comments about CDP.
    Updated the "bit_usage" section of resctrl.rst for io_alloc.

v8: Moved the patch to last after all the concepts are initialized.
    Updated user doc resctrl.rst.
    Simplified the CDT check  in rdt_bit_usage_show() as CDP_DATA and CDP_CODE
    are in sync with io_alloc enabled.

v7: New patch split from earlier patch #5.
    Added resctrl_io_alloc_closid() to return max COSID.
---
 Documentation/filesystems/resctrl.rst | 35 ++++++++++++++++-----------
 fs/resctrl/ctrlmondata.c              |  2 +-
 fs/resctrl/internal.h                 |  2 ++
 fs/resctrl/rdtgroup.c                 | 21 ++++++++++++++--
 4 files changed, 43 insertions(+), 17 deletions(-)

diff --git a/Documentation/filesystems/resctrl.rst b/Documentation/filesystems/resctrl.rst
index 7e3eda324de5..72ea6f3f36bc 100644
--- a/Documentation/filesystems/resctrl.rst
+++ b/Documentation/filesystems/resctrl.rst
@@ -90,12 +90,19 @@ related to allocation:
 		must be set when writing a mask.
 
 "shareable_bits":
-		Bitmask of shareable resource with other executing
-		entities (e.g. I/O). User can use this when
-		setting up exclusive cache partitions. Note that
-		some platforms support devices that have their
-		own settings for cache use which can over-ride
-		these bits.
+		Bitmask of shareable resource with other executing entities
+		(e.g. I/O). Applies to all instances of this resource. User
+		can use this when setting up exclusive cache partitions.
+		Note that some platforms support devices that have their
+		own settings for cache use which can over-ride these bits.
+
+		When "io_alloc" is enabled, a portion of each cache instance can
+		be configured for shared use between hardware and software.
+		"bit_usage" should be used to see which portions of each cache
+		instance is configured for hardware use via "io_alloc" feature
+		because every cache instance can have its "io_alloc" bitmask
+		configured independently via io_alloc_cbm.
+
 "bit_usage":
 		Annotated capacity bitmasks showing how all
 		instances of the resource are used. The legend is:
@@ -109,16 +116,16 @@ related to allocation:
 			"H":
 			      Corresponding region is used by hardware only
 			      but available for software use. If a resource
-			      has bits set in "shareable_bits" but not all
-			      of these bits appear in the resource groups'
-			      schematas then the bits appearing in
-			      "shareable_bits" but no resource group will
-			      be marked as "H".
+			      has bits set in "shareable_bits" or "io_alloc_cbm"
+			      but not all of these bits appear in the resource
+			      groups' schematas then the bits appearing in
+			      "shareable_bits" or "io_alloc_cbm" but no
+			      resource group will be marked as "H".
 			"X":
 			      Corresponding region is available for sharing and
-			      used by hardware and software. These are the
-			      bits that appear in "shareable_bits" as
-			      well as a resource group's allocation.
+			      used by hardware and software. These are the bits
+			      that appear in "shareable_bits" or "io_alloc_cbm"
+			      as well as a resource group's allocation.
 			"S":
 			      Corresponding region is used by software
 			      and available for sharing.
diff --git a/fs/resctrl/ctrlmondata.c b/fs/resctrl/ctrlmondata.c
index 791ecb559b50..1118054fdc2c 100644
--- a/fs/resctrl/ctrlmondata.c
+++ b/fs/resctrl/ctrlmondata.c
@@ -738,7 +738,7 @@ static int resctrl_io_alloc_init_cbm(struct resctrl_schema *s, u32 closid)
  * resource. Note that if Code Data Prioritization (CDP) is enabled, the number
  * of available CLOSIDs is reduced by half.
  */
-static u32 resctrl_io_alloc_closid(struct rdt_resource *r)
+u32 resctrl_io_alloc_closid(struct rdt_resource *r)
 {
 	if (resctrl_arch_get_cdp_enabled(r->rid))
 		return resctrl_arch_get_num_closid(r) / 2  - 1;
diff --git a/fs/resctrl/internal.h b/fs/resctrl/internal.h
index 5467c3ad1b6d..98b87725508b 100644
--- a/fs/resctrl/internal.h
+++ b/fs/resctrl/internal.h
@@ -395,6 +395,8 @@ int resctrl_io_alloc_cbm_show(struct kernfs_open_file *of, struct seq_file *seq,
 ssize_t resctrl_io_alloc_cbm_write(struct kernfs_open_file *of, char *buf,
 				   size_t nbytes, loff_t off);
 
+u32 resctrl_io_alloc_closid(struct rdt_resource *r);
+
 const char *rdtgroup_name_by_closid(int closid);
 
 #ifdef CONFIG_RESCTRL_FS_PSEUDO_LOCK
diff --git a/fs/resctrl/rdtgroup.c b/fs/resctrl/rdtgroup.c
index ddac021c02d8..951d44d6f488 100644
--- a/fs/resctrl/rdtgroup.c
+++ b/fs/resctrl/rdtgroup.c
@@ -1068,15 +1068,17 @@ static int rdt_bit_usage_show(struct kernfs_open_file *of,
 
 	cpus_read_lock();
 	mutex_lock(&rdtgroup_mutex);
-	hw_shareable = r->cache.shareable_bits;
 	list_for_each_entry(dom, &r->ctrl_domains, hdr.list) {
 		if (sep)
 			seq_putc(seq, ';');
+		hw_shareable = r->cache.shareable_bits;
 		sw_shareable = 0;
 		exclusive = 0;
 		seq_printf(seq, "%d=", dom->hdr.id);
 		for (i = 0; i < closids_supported(); i++) {
-			if (!closid_allocated(i))
+			if (!closid_allocated(i) ||
+			    (resctrl_arch_get_io_alloc_enabled(r) &&
+			     i == resctrl_io_alloc_closid(r)))
 				continue;
 			ctrl_val = resctrl_arch_get_config(r, dom, i,
 							   s->conf_type);
@@ -1104,6 +1106,21 @@ static int rdt_bit_usage_show(struct kernfs_open_file *of,
 				break;
 			}
 		}
+
+		/*
+		 * When the "io_alloc" feature is enabled, a portion of the cache
+		 * is configured for shared use between hardware and software.
+		 * Also, when CDP is enabled the CBMs of L3CODE and L3DATA are kept
+		 * in sync. So, the CBMs for "io_alloc" can be accessed through either
+		 * L3CODE or L3DATA.
+		 */
+		if (resctrl_arch_get_io_alloc_enabled(r)) {
+			ctrl_val = resctrl_arch_get_config(r, dom,
+							   resctrl_io_alloc_closid(r),
+							   s->conf_type);
+			hw_shareable |= ctrl_val;
+		}
+
 		for (i = r->cache.cbm_len - 1; i >= 0; i--) {
 			pseudo_locked = dom->plr ? dom->plr->cbm : 0;
 			hwb = test_bit(i, &hw_shareable);

---

## [12] Reinette Chatre — 2025-09-17
*Subject: Re: [PATCH v9 01/10] x86/cpufeatures: Add support for L3 Smart Data
 Cache Injection Allocation Enforcement*

Hi Babu,

(Just highlighting some changelog formatting that was needed for ABMC
changelogs.)

On 9/2/25 3:41 PM, Babu Moger wrote:
> Smart Data Cache Injection (SDCI) is a mechanism that enables direct
> insertion of data from I/O devices into the L3 cache. By directly caching

Compare with how indentation of ABMC "x86,fs/resctrl: Implement resctrl_arch_config_cntr()
to assign a counter with ABMC" was changed during merge. 

  [1] AMD64 Architecture Programmer's Manual Volume 2: System Programming
      Publication # 24593 Revision 3.41 section 19.4.7 L3 Smart Data Cache
      Injection Allocation Enforcement (SDCIAE)

(also applies to patch #4)

> 
> Link: https://bugzilla.kernel.org/show_bug.cgi?id=206537 # [2]

Please place "Link:" tag at end to reduce needed adjustments during
merge.

> Signed-off-by: Babu Moger <babu.moger@amd.com>
> Acked-by: Borislav Petkov (AMD) <bp@alien8.de>

Reinette

---

## [13] Reinette Chatre — 2025-09-17
*Subject: Re: [PATCH v9 02/10] x86/resctrl: Add SDCIAE feature in the command
 line options*

Hi Babu,

On 9/2/25 3:41 PM, Babu Moger wrote:
> Add the command line option to enable or disable the new resctrl feature
> L3 Smart Data Cache Injection Allocation Enforcement (SDCIAE).

Since SDCIAE is the architecture specific feature while the generic resctrl feature
is "io_alloc" I think it will be more accurate to say something similar to the
ABMC changelog:
	Add a kernel command-line parameter to enable or disable the exposure of
	the L3 Smart Data Cache Injection Allocation Enforcement (SDCIAE) hardware
	feature to resctrl.

> 
> Signed-off-by: Babu Moger <babu.moger@amd.com>

With changelog change:

| Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>

Reinette

---

## [14] Reinette Chatre — 2025-09-17
*Subject: Re: [PATCH v9 03/10] x86,fs/resctrl: Detect io_alloc feature*

Hi Babu,

On 9/2/25 3:41 PM, Babu Moger wrote:
> Smart Data Cache Injection (SDCI) is a mechanism that enables direct
> insertion of data from I/O devices into the L3 cache. It can reduce the

This copy&pasted text found in cover letter and patch 1 and now here seems to be the
type of annoying repetitive text that Boris referred to [1]. Looking at this changelog
again it may also be confusing to start with introduction of one feature (SDCI), but
end with another SDCIAE.

Here is a changelog that attempts to address issues, please feel free to improve:

	AMD's SDCIAE (SDCI Allocation Enforcement) PQE feature enables system software  
	to control the portions of L3 cache used for direct insertion of data from   
	I/O devices into the L3 cache.                                                  
                                                                                
	Introduce a generic resctrl cache resource property "io_alloc_capable" as the
	first part of the new "io_alloc" resctrl feature that will support AMD's
	SDCIAE.	Any architecture can set a cache resource as "io_alloc_capable" if a
	portion	of the cache can be allocated for I/O traffic.  
                                                                                
	Set the "io_alloc_capable" property for the L3 cache resource on x86       
	(AMD) systems that support SDCIAE.                          

 
> Introduce cache resource property "io_alloc_capable" that an architecture
> can set if a portion of the cache can be allocated for I/O traffic.

Reinette


[1] https://lore.kernel.org/lkml/20250911150850.GAaMLmAoi5fTIznQzY@fat_crate.local/

---

## [15] Reinette Chatre — 2025-09-17
*Subject: Re: [PATCH v9 04/10] x86,fs/resctrl: Implement "io_alloc"
 enable/disable handlers*

Hi Babu,

On 9/2/25 3:41 PM, Babu Moger wrote:
> "io_alloc" enables direct insertion of data from I/O devices into the
> cache.

(repetition)

> 
> On AMD systems, "io_alloc" feature is backed by L3 Smart Data Cache

Did you notice Boris's touchup on ABMC "x86/resctrl: Add data structures and
definitions for ABMC assignment"? This should be MSR_IA32_L3_QOS_EXT_CFG
(also needed in patch self, more below)

> logical processors within the cache domain.
> 

(same comment as patch #1)

Changelog that aims to address feeback received in ABMC series, please feel free
to improve:
	"io_alloc" is the generic name of the new resctrl feature that enables          
	system software to configure the portion of cache allocated for I/O             
	traffic. On AMD systems, "io_alloc" resctrl feature is backed by AMD's
	L3 Smart Data Cache Injection Allocation Enforcement (SDCIAE).                           
                                                                                
	Introduce the architecture-specific functions that resctrl fs should call
	to enable, disable, or check status of the "io_alloc" feature. Change
	SDCIAE state by setting (to enable) or clearing (to disable) bit 1 of
 	MSR_IA32_L3_QOS_EXT_CFG on all logical processors within the cache domain.                                                        
                                                                                
	The SDCIAE feature details are documented in APM [1] available from [2].        
	[1] AMD64 Architecture Programmer's Manual Volume 2: System Programming         
	    Publication # 24593 Revision 3.41 section 19.4.7 L3 Smart Data Cache        
	    Injection Allocation Enforcement (SDCIAE)                                   

> 
> Link: https://bugzilla.kernel.org/show_bug.cgi?id=206537 # [2]

(please move to end of tags)

> Signed-off-by: Babu Moger <babu.moger@amd.com>
> Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>

... 

> +static void _resctrl_sdciae_enable(struct rdt_resource *r, bool enable)
> +{

"L3_QOS_EXT_CFG MSR" -> MSR_IA32_L3_QOS_EXT_CFG

(to match touchups needed to ABMC series)

> +	list_for_each_entry(d, &r->ctrl_domains, hdr.list)
> +		on_each_cpu_mask(&d->hdr.cpu_mask, resctrl_sdciae_set_one_amd, &enable, 1);

"L3_QOS_EXT_CFG" -> MSR_IA32_L3_QOS_EXT_CFG

Reinette

---

## [16] Reinette Chatre — 2025-09-17
*Subject: Re: [PATCH v9 05/10] fs/resctrl: Introduce interface to display
 "io_alloc" support*

Hi Babu,

On 9/2/25 3:41 PM, Babu Moger wrote:
> "io_alloc" feature in resctrl allows direct insertion of data from I/O
> devices into the cache.

Changelog that aims to address feeback received in ABMC series (avoid repetition
and document any non-obvious things), please feel free to improve:

	Introduce the "io_alloc" resctrl file to the "info" area of a cache
	resource, for example /sys/fs/resctrl/info/L3/io_alloc. "io_alloc"
	indicates support for the "io_alloc" feature that allows direct
	insertion of data from I/O devices into the cache.                                                         
                                                                                
	Restrict exposing support for "io_alloc" to the L3 resource that is the        
	only resource where this feature can be backed by AMD's L3 Smart Data Cache
	Injection Allocation Enforcement (SDCIAE). With that, the "io_alloc" file is only
	visible to user space if the L3 resource supports "io_alloc". Doing     
	so makes the file visible for all cache resources though, for example also L2   
	cache (if it supports cache allocation). As a consequence, add capability for
	file to report expected "enabled" and "disabled", as well as "not supported".                  


> 
> Signed-off-by: Babu Moger <babu.moger@amd.com>

...

> ---
>  Documentation/filesystems/resctrl.rst | 30 +++++++++++++++++++++++++++

After trying to rework the changelogs I believe the portion of doc below is better suited for
the next patch that adds support for enable/disable where CLOSIDs are relevant.

> +		The underlying implementation may reduce resources available to
> +		general (CPU) cache allocation. See architecture specific notes

Reinette

---

## [17] Reinette Chatre — 2025-09-17
*Subject: Re: [PATCH v9 06/10] fs/resctrl: Add user interface to enable/disable
 io_alloc feature*

Hi Babu,

On 9/2/25 3:41 PM, Babu Moger wrote:
> "io_alloc" feature in resctrl enables direct insertion of data from I/O
> devices into the cache.

(repetition)

> 
> On AMD systems, when io_alloc is enabled, the highest CLOSID is reserved

I think the flow will improve if above two paragraphs are swapped. This is
also missing the non-obvious support for CDP. As mentioned in previous patch, if
the related doc change is moved from patch 5 to here it can be handled together.

Trying to put it all together, please feel free to improve:

	AMD's SDCIAE forces all SDCI lines to be placed into the L3 cache portions
	identified by the highest-supported L3_MASK_n register, where n is the maximum
	supported CLOSID.

	To support AMD's SDCIAE, when io_alloc resctrl feature is enabled, reserve the
	highest CLOSID exclusively for I/O allocation traffic making it no longer available for
	general CPU cache allocation. 

	Introduce user interface to enable/disable io_alloc feature and encourage users
	to enable io_alloc only when running workloads that can benefit from this
	functionality. On enable, initialize the io_alloc CLOSID with all usable CBMs
	across all the domains.

	Since CLOSIDs are managed by resctrl fs, it is least invasive to make 
	"io_alloc is supported by maximum supported CLOSID" part of the initial
	resctrl fs support for io_alloc. Take care to minimally (only in error messages)
	expose this use of CLOSID for io_alloc to user space so that this is
	not required from other	architectures that may support io_alloc differently in the future.

	When resctrl is mounted with "-o cdp" to enable code/data prioritization        
	there are two L3 resources that can support I/O allocation: L3CODE and L3DATA.  
	From resctrl fs perspective the two resources share a CLOSID and the            
	architecture's available CLOSID are halved to support this.                      
	The architecture's underlying CLOSID used by SDCIAE when CDP is enabled is      
	the CLOSID associated with the L3CODE resource, but from resctrl's perspective  
	there is only one CLOSID for both L3CODE and L3DATA. L3DATA is thus not usable  
	for general (CPU) cache allocation nor I/O allocation. Keep the L3CODE and      
	L3DATA I/O alloc status in sync to avoid any confusion to user space. That      
	is, enabling io_alloc on L3CODE does so on L3DATA and vice-versa, and        
	keep the I/O allocation CBMs of L3CODE and L3DATA in sync.       

> 
> Signed-off-by: Babu Moger <babu.moger@amd.com>

...

> +ssize_t resctrl_io_alloc_write(struct kernfs_open_file *of, char *buf,
> +			       size_t nbytes, loff_t off)

%d -> %u ?

> +				    io_alloc_closid);
> +		ret = -EINVAL;

%d -> %u ?

> +					    io_alloc_closid, grp_name ? grp_name : "another");
> +			ret = -ENOSPC;

Reinette

---

## [18] Reinette Chatre — 2025-09-17
*Subject: Re: [PATCH v9 07/10] fs/resctrl: Introduce interface to display
 io_alloc CBMs*

Hi Babu,

On 9/2/25 3:41 PM, Babu Moger wrote:
> The io_alloc feature in resctrl enables system software to configure
> the portion of the cache allocated for I/O traffic.

(repetitive)

> 
> Add "io_alloc_cbm" resctrl file to display the Capacity Bit Masks (CBMs)

Related to changelog feedback received during ABMC series I think the portion
that describes the code  (from "Pass the resource name ..." to "printing the
resource name"), is unnecessary since it can be seen by looking at the patch.

> 
> When CDP is enabled, io_alloc routes traffic using the highest CLOSID

I do not think the "To ensure consistent cache allocation behavior" is accurate.
This is just to avoid the possible user space confusion if supporting the feature
with L3CODE used for I/O allocation and L3DATA becomes unusable, no?

Also, this also needs to be in imperative tone.

> Capacity Bit Masks (CBMs) accessed through either L3CODE or L3DATA will
> reflect identical values.

Attempt to put it together, please feel free to improve:

	Introduce the "io_alloc_cbm" resctrl file to display the Capacity Bit
	Masks (CBMs) that represent the portions of each cache instance allocated
	for I/O traffic on a cache resource that supports the "io_alloc" feature.         

	io_alloc_cbm resides in the info directory of a cache resource, for example,
	/sys/fs/resctrl/info/L3/. Since the resource name is part of the path, it
	is not necessary to display the resource name as done in the schemata file.

	When CDP is enabled, io_alloc routes traffic using the highest CLOSID
	associated with the L3CODE resource and that CLOSID becomes unusable for
	the L3DATA resource. The highest CLOSID of L3CODE and L3DATA resources will
	be kept	in sync	to ensure consistent user interface. In preparation for this,
	access the CBMs for I/O traffic through highest CLOSID of either L3CODE or
	L3DATA resource.

> 
> Signed-off-by: Babu Moger <babu.moger@amd.com>

..

> @@ -807,3 +809,40 @@ ssize_t resctrl_io_alloc_write(struct kernfs_open_file *of, char *buf,
>  

The return code when io_alloc is not enabled is different between reading from (EINVAL) and
writing to (ENODEV) io_alloc_cbm. Please be consistent.

> +		goto out_unlock;
> +	}

Not just during initialization, they are kept in sync during runtime also (when
user writes to io_alloc_cbm). First sentence can perhaps just be
	"When CDP is enabled the CBMs of the highest CLOSID of L3CODE
	 and L3DATA are kept in sync. As a result, ..."

Reinette

---

## [19] Reinette Chatre — 2025-09-17
*Subject: Re: [PATCH v9 08/10] fs/resctrl: Modify rdt_parse_data to pass mode
 and CLOSID*

Hi Babu,

nit:
Subject: fs/resctrl: Modify struct rdt_parse_data to pass mode and CLOSID

On 9/2/25 3:41 PM, Babu Moger wrote:
> parse_cbm() require resource group mode and CLOSID to validate the Capacity
> Bit Mask (CBM). It is passed via struct rdtgroup in struct rdt_parse_data.

With Subject change:

| Reviewed-by: Reinette Chatre <reinette.chatre@intel.com>

Reinette

---

## [20] Reinette Chatre — 2025-09-17
*Subject: Re: [PATCH v9 09/10] fs/resctrl: Introduce interface to modify
 io_alloc Capacity Bit Masks*

Hi Babu,

On 9/2/25 3:41 PM, Babu Moger wrote:
> The io_alloc feature in resctrl enables system software to configure the
> portion of the cache allocated for I/O traffic. When supported, the

reserved -> allocated?

The cache portions represented by CBMs are not reserved for I/O devices - these
portions are available for sharing and can still be used by CPU cache allocation. 

> 
> Enable users to modify io_alloc CBMs (Capacity Bit Masks) via the

Can drop "(Capacity Bit Masks)" since acronym was spelled out in first paragraph.

> io_alloc_cbm resctrl file when io_alloc is enabled.
> 

This is not about "consistent cache allocation" but instead a consistent user
interface. How about "To present consistent I/O allocation information to user
space when CDP is enabled, the CBMs ..."

> written to either L3CODE or L3DATA are mirrored to the other, keeping both
> resource types synchronized.

(needs imperative)

> 
> Signed-off-by: Babu Moger <babu.moger@amd.com>

...

> ---
>  Documentation/filesystems/resctrl.rst | 11 ++++

To accommodate how a shell may interpret above this should perhaps be (see schemata examples):

			# echo "0=ff;1=f" > /sys/fs/resctrl/info/L3/io_alloc_cbm

> +			# cat /sys/fs/resctrl/info/L3/io_alloc_cbm
> +			0=00ff;1=000f

The comment just describes what can be seen from the code. How about something like
"Keep io_alloc CLOSID's CBM of CDP_CODE and CDP_DATA in sync."?

Of note is that these comments are generic while earlier comments related to CDP are L3
specific ("L3CODE" and "L3DATA"). Having resource specific names in generic code is not ideal,
even if first implementation is only for L3. I think this was done in many places though,
even in a couple of the changelogs I created and I now realize the impact after seeing
this comment. Could you please take a look to make the name generic when it is used in
generic changelog and comments?

> +			 */
> +			if (resctrl_arch_get_cdp_enabled(r->rid)) {

Compare to comment in patch #7 where the same error of io_alloc not being enabled results
in different error code (EINVAL). Please keep these consistent.

> +		goto out_unlock;
> +	}

Reinette

---

## [21] Reinette Chatre — 2025-09-17
*Subject: Re: [PATCH v9 10/10] fs/resctrl: Update bit_usage to reflect io_alloc*

Hi Babu,

On 9/2/25 3:41 PM, Babu Moger wrote:
> When the io_alloc feature is enabled, a portion of the cache can be
> configured for shared use between hardware and software.

(repetitive)

> 
> Update bit_usage representation to reflect the io_alloc configuration.

Attempt at new version, please feel free to improve:

	The "shareable_bits" and "bit_usage" resctrl files associated with cache
	resources give insight into how instances of a cache is used.                  
                                                                                
	Update the annotated capacity bitmasks displayed by "bit_usage" to include the  
	cache portions allocated for I/O via the "io_alloc" feature. "shareable_bits" is
	a global bitmask of shareable cache with I/O and can thus not present the
	per-domain I/O allocations possible with the "io_alloc" feature. Revise the
	"shareable_bits" documentation to direct users to "bit_usage" for accurate
	cache usage information.                                                                    

> 
> Signed-off-by: Babu Moger <babu.moger@amd.com>

...

> ---
>  Documentation/filesystems/resctrl.rst | 35 ++++++++++++++++-----------

io_alloc_cbm -> "io_alloc_cbm" (to consistently place names of resctrl files in quotes)

> +
>  "bit_usage":

I understand that you are just copying this but "schemata" is plural of "schema". Since you
are copying this text, could you please fix "schematas" to be "schemata" while doing so?


> +			      "shareable_bits" or "io_alloc_cbm" but no
> +			      resource group will be marked as "H".

Reinette

---

## [22] Moger, Babu — 2025-09-19
*Subject: Re: [PATCH v9 01/10] x86/cpufeatures: Add support for L3 Smart Data
 Cache Injection Allocation Enforcement*

Hi Reinette,

Thanks for the review of the series. Sorry for duplicate messages. 
Setting the email on my new machine.

On 9/18/2025 12:08 AM, Reinette Chatre wrote:
> Hi Babu,
> 

Sure.

> 
>>

Yes. Sure.

Kept the Acked-by and Reviewed-by tag as is.

Thanks

Babu

---

## [23] Moger, Babu — 2025-09-19
*Subject: Re: [PATCH v9 02/10] x86/resctrl: Add SDCIAE feature in the command
 line options*

Hi Reinette,

On 9/18/2025 12:09 AM, Reinette Chatre wrote:
> Hi Babu,
> 

Sure.

>>
>> Signed-off-by: Babu Moger <babu.moger@amd.com>

Thanks
Babu

---

## [24] Moger, Babu — 2025-09-19
*Subject: Re: [PATCH v9 03/10] x86,fs/resctrl: Detect io_alloc feature*

Hi Reinette,

On 9/18/2025 12:15 AM, Reinette Chatre wrote:
> Hi Babu,
> 

Looks good. thank you.

>> Introduce cache resource property "io_alloc_capable" that an architecture
>> can set if a portion of the cache can be allocated for I/O traffic.

---

## [25] Moger, Babu — 2025-09-19
*Subject: Re: [PATCH v9 04/10] x86,fs/resctrl: Implement "io_alloc"
 enable/disable handlers*

Hi Reinette,

On 9/18/2025 12:19 AM, Reinette Chatre wrote:
> Hi Babu,
> 

Yes.

>> logical processors within the cache domain.
>>

Looks good. Thanks
>>
>> Link: https://bugzilla.kernel.org/show_bug.cgi?id=206537 # [2]

Sure.

> 
>> Signed-off-by: Babu Moger <babu.moger@amd.com>

Yes.

> 
>> +	list_for_each_entry(d, &r->ctrl_domains, hdr.list)
Sure.
Thanks
Babu

---

## [26] Moger, Babu — 2025-09-19
*Subject: Re: [PATCH v9 05/10] fs/resctrl: Introduce interface to display
 "io_alloc" support*

Hi Reinette,

On 9/18/2025 12:28 AM, Reinette Chatre wrote:
> Hi Babu,
> 

Looks good. Thanks

>>
>> Signed-off-by: Babu Moger <babu.moger@amd.com>

Sure.

Thanks
Babu
> 
>> +		The underlying implementation may reduce resources available to

---

## [27] Moger, Babu — 2025-09-19
*Subject: Re: [PATCH v9 06/10] fs/resctrl: Add user interface to enable/disable
 io_alloc feature*

Hi Reinette,

On 9/18/2025 12:37 AM, Reinette Chatre wrote:
> Hi Babu,
> 

Looks good. Thanks

>>
>> Signed-off-by: Babu Moger <babu.moger@amd.com>

Sure.

> 
>> +				    io_alloc_closid);

sure.

Thank you.

> 
>> +					    io_alloc_closid, grp_name ? grp_name : "another");

---

## [28] Moger, Babu — 2025-09-19
*Subject: Re: [PATCH v9 07/10] fs/resctrl: Introduce interface to display
 io_alloc CBMs*

Hi Reinette,

On 9/18/2025 12:43 AM, Reinette Chatre wrote:
> Hi Babu,
> 

Sure.

> 
>>

Yes. that is correct.

> 
> Also, this also needs to be in imperative tone.

Looks good.

>>
>> Signed-off-by: Babu Moger <babu.moger@amd.com>


Will change the return code in patch 9 to -EINVAL to be consistent.

> 
>> +		goto out_unlock;

Sure. Thanks
Babu

---

## [29] Moger, Babu — 2025-09-19
*Subject: Re: [PATCH v9 08/10] fs/resctrl: Modify rdt_parse_data to pass mode
 and CLOSID*

Hi Reinette,

On 9/18/2025 12:44 AM, Reinette Chatre wrote:
> Hi Babu,
> 

sure.

> 
> On 9/2/25 3:41 PM, Babu Moger wrote:

Thanks
Babu

---

## [30] Moger, Babu — 2025-09-19
*Subject: Re: [PATCH v9 09/10] fs/resctrl: Introduce interface to modify
 io_alloc Capacity Bit Masks*

Hi Reinette,

On 9/18/2025 1:03 AM, Reinette Chatre wrote:
> Hi Babu,
> 

Sure.

> 
> The cache portions represented by CBMs are not reserved for I/O devices - these

sure.

> 
>> io_alloc_cbm resctrl file when io_alloc is enabled.

Here is the updated full changelog.

fs/resctrl: Introduce interface to modify io_alloc Capacity Bit Masks

The io_alloc feature in resctrl enables system software to configure the
portion of the cache allocated for I/O traffic. When supported, the
io_alloc_cbm file in resctrl provides access to Capacity Bit Masks 
(CBMs) allocated for I/O devices.

Enable users to modify io_alloc CBMs via io_alloc_cbm resctrl file when 
the feature is enabled.

Mirror the CBMs between CDP_CODE and CDP_DATA when CDP is enabled to 
present consistent I/O allocation information to user space and keep 
both resource types synchronized.

Signed-off-by: Babu Moger <babu.moger@amd.com>


> 
>>

Sure.

> 
> 			# echo "0=ff;1=f" > /sys/fs/resctrl/info/L3/io_alloc_cbm

Sure.

> 
> Of note is that these comments are generic while earlier comments related to CDP are L3

Sure.

> 
>> +			 */

Yes. Changed it to -EINVAL.

thanks
Babu


> 
>

---

## [31] Moger, Babu — 2025-09-19
*Subject: Re: [PATCH v9 10/10] fs/resctrl: Update bit_usage to reflect io_alloc*

Hi Reinette,

On 9/18/2025 1:08 AM, Reinette Chatre wrote:
> Hi Babu,
> 

Looks good. Thanks

>>
>> Signed-off-by: Babu Moger <babu.moger@amd.com>

Sure.

> 
>> +

Sure.

Thanks
Babu

---

## [32] Reinette Chatre — 2025-09-22
*Subject: Re: [PATCH v9 09/10] fs/resctrl: Introduce interface to modify
 io_alloc Capacity Bit Masks*

Hi Babu,

On 9/19/25 1:49 PM, Moger, Babu wrote:
 
> Here is the updated full changelog.
> 

I do not think it is necessary to use upper case if not following it
by the acronym. I also think "bitmask" is usually one word? So:
	fs/resctrl: Introduce interface to modify io_alloc capacity bitmasks

> 
> The io_alloc feature in resctrl enables system software to configure the

(nit) can be made more specific with:

	Enable users to modify io_alloc CBMs by writing to the io_alloc_cbm resctrl
	file when the io_alloc feature is enabled.

> 
> Mirror the CBMs between CDP_CODE and CDP_DATA when CDP is enabled to present consistent I/O allocation information to user space and keep both resource types synchronized.

I think "and keep both resource types synchronized" is redundant considering the sentence
starts with "Mirror the CBMs"?

Reinette

---

## [33] Moger, Babu — 2025-09-25
*Subject: Re: [PATCH v9 09/10] fs/resctrl: Introduce interface to modify
 io_alloc Capacity Bit Masks*

Hi Reinette,

On 9/22/25 17:48, Reinette Chatre wrote:
> Hi Babu,
> 

Sure.

>>
>> The io_alloc feature in resctrl enables system software to configure the

Sure.

>>
>> Mirror the CBMs between CDP_CODE and CDP_DATA when CDP is enabled to present consistent I/O allocation information to user space and keep both resource types synchronized.

Removed "and keep both resource types synchronized."

---
