---
title: 'x86/cpufeatures: Add X86_FEATURE_RMPOPT feature flag'
date: 2026-06-15
last_reply: 2026-06-22
message_count: 33
participants: ['Ashish Kalra', 'K Prateek Nayak', 'Borislav Petkov', 'Tom Lendacky', 'Dave Hansen', 'Thomas Gleixner']
---

## [1] Ashish Kalra — 2026-06-15

From: Ashish Kalra <ashish.kalra@amd.com>

Add a flag indicating whether RMPOPT instruction is supported.

RMPOPT is a new instruction that reduces the performance overhead of
RMP checks for the hypervisor and non-SNP guests by allowing those
checks to be skipped when 1-GB memory regions are known to contain no
SEV-SNP guest memory.

For more information on the RMPOPT instruction, see the AMD64 RMPOPT
technical documentation.

Suggested-by: Borislav Petkov (AMD) <bp@alien8.de>
Reviewed-by: Dave Hansen <dave.hansen@linux.intel.com>
Reviewed-by: Ackerley Tng <ackerleytng@google.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/include/asm/cpufeatures.h       | 2 +-
 arch/x86/kernel/cpu/scattered.c          | 1 +
 tools/arch/x86/include/asm/cpufeatures.h | 2 +-
 3 files changed, 3 insertions(+), 2 deletions(-)

diff --git a/arch/x86/include/asm/cpufeatures.h b/arch/x86/include/asm/cpufeatures.h
index 1d506e5d6f46..794cc96b8493 100644
--- a/arch/x86/include/asm/cpufeatures.h
+++ b/arch/x86/include/asm/cpufeatures.h
@@ -76,7 +76,7 @@
 #define X86_FEATURE_K8			( 3*32+ 4) /* Opteron, Athlon64 */
 #define X86_FEATURE_ZEN5		( 3*32+ 5) /* CPU based on Zen5 microarchitecture */
 #define X86_FEATURE_ZEN6		( 3*32+ 6) /* CPU based on Zen6 microarchitecture */
-/* Free                                 ( 3*32+ 7) */
+#define X86_FEATURE_RMPOPT		( 3*32+ 7) /* Support for AMD RMPOPT instruction */
 #define X86_FEATURE_CONSTANT_TSC	( 3*32+ 8) /* "constant_tsc" TSC ticks at a constant rate */
 #define X86_FEATURE_UP			( 3*32+ 9) /* "up" SMP kernel running on UP */
 #define X86_FEATURE_ART			( 3*32+10) /* "art" Always running timer (ART) */
diff --git a/arch/x86/kernel/cpu/scattered.c b/arch/x86/kernel/cpu/scattered.c
index 937129ce6a96..021c0bf22de2 100644
--- a/arch/x86/kernel/cpu/scattered.c
+++ b/arch/x86/kernel/cpu/scattered.c
@@ -67,6 +67,7 @@ static const struct cpuid_bit cpuid_bits[] = {
 	{ X86_FEATURE_PERFMON_V2,		CPUID_EAX,  0, 0x80000022, 0 },
 	{ X86_FEATURE_AMD_LBR_V2,		CPUID_EAX,  1, 0x80000022, 0 },
 	{ X86_FEATURE_AMD_LBR_PMC_FREEZE,	CPUID_EAX,  2, 0x80000022, 0 },
+	{ X86_FEATURE_RMPOPT,			CPUID_EDX,  0, 0x80000025, 0 },
 	{ X86_FEATURE_AMD_HTR_CORES,		CPUID_EAX, 30, 0x80000026, 0 },
 	{ 0, 0, 0, 0, 0 }
 };
diff --git a/tools/arch/x86/include/asm/cpufeatures.h b/tools/arch/x86/include/asm/cpufeatures.h
index 86d17b195e79..7ce681af1dd7 100644
--- a/tools/arch/x86/include/asm/cpufeatures.h
+++ b/tools/arch/x86/include/asm/cpufeatures.h
@@ -76,7 +76,7 @@
 #define X86_FEATURE_K8			( 3*32+ 4) /* Opteron, Athlon64 */
 #define X86_FEATURE_ZEN5		( 3*32+ 5) /* CPU based on Zen5 microarchitecture */
 #define X86_FEATURE_ZEN6		( 3*32+ 6) /* CPU based on Zen6 microarchitecture */
-/* Free                                 ( 3*32+ 7) */
+#define X86_FEATURE_RMPOPT		( 3*32+ 7) /* Support for AMD RMPOPT instruction */
 #define X86_FEATURE_CONSTANT_TSC	( 3*32+ 8) /* "constant_tsc" TSC ticks at a constant rate */
 #define X86_FEATURE_UP			( 3*32+ 9) /* "up" SMP kernel running on UP */
 #define X86_FEATURE_ART			( 3*32+10) /* "art" Always running timer (ART) */

---

## [2] Ashish Kalra — 2026-06-15
*Subject: [PATCH v8 2/7] x86/sev: Initialize RMPOPT configuration MSRs*

From: Ashish Kalra <ashish.kalra@amd.com>

The new RMPOPT instruction helps manage per-CPU RMP optimization
structures inside the CPU. It takes a 1GB-aligned physical address
and either returns the status of the optimizations or tries to enable
the optimizations.

Per-CPU RMPOPT tables support at most 2 TB of addressable memory for
RMP optimizations.

Initialize the per-CPU RMPOPT table base to the starting physical
address. This enables RMP optimization for up to 2 TB of system RAM on
all CPUs.

Additionally, add support to setup and enable RMPOPT once SNP is
enabled and initialized.

Suggested-by: Thomas Lendacky <thomas.lendacky@amd.com>
Suggested-by: Dave Hansen <dave.hansen@linux.intel.com>
Reviewed-by: Dave Hansen <dave.hansen@linux.intel.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/coco/core.c             |  2 +
 arch/x86/include/asm/msr-index.h |  3 ++
 arch/x86/include/asm/sev.h       |  4 ++
 arch/x86/virt/svm/sev.c          | 70 ++++++++++++++++++++++++++++++++
 drivers/crypto/ccp/sev-dev.c     |  3 ++
 5 files changed, 82 insertions(+)

diff --git a/arch/x86/coco/core.c b/arch/x86/coco/core.c
index 989ca9f72ba3..8c1393ddc5df 100644
--- a/arch/x86/coco/core.c
+++ b/arch/x86/coco/core.c
@@ -16,6 +16,7 @@
 #include <asm/archrandom.h>
 #include <asm/coco.h>
 #include <asm/processor.h>
+#include <asm/sev.h>
 
 enum cc_vendor cc_vendor __ro_after_init = CC_VENDOR_NONE;
 SYM_PIC_ALIAS(cc_vendor);
@@ -172,6 +173,7 @@ static void amd_cc_platform_clear(enum cc_attr attr)
 	switch (attr) {
 	case CC_ATTR_HOST_SEV_SNP:
 		cc_flags.host_sev_snp = 0;
+		snp_clear_rmpopt_configured();
 		break;
 	default:
 		break;
diff --git a/arch/x86/include/asm/msr-index.h b/arch/x86/include/asm/msr-index.h
index 86554de9a3f5..28540744f1eb 100644
--- a/arch/x86/include/asm/msr-index.h
+++ b/arch/x86/include/asm/msr-index.h
@@ -761,6 +761,9 @@
 #define MSR_AMD64_SEG_RMP_ENABLED_BIT	0
 #define MSR_AMD64_SEG_RMP_ENABLED	BIT_ULL(MSR_AMD64_SEG_RMP_ENABLED_BIT)
 #define MSR_AMD64_RMP_SEGMENT_SHIFT(x)	(((x) & GENMASK_ULL(13, 8)) >> 8)
+#define MSR_AMD64_RMPOPT_BASE		0xc0010139
+#define MSR_AMD64_RMPOPT_ENABLE_BIT	0
+#define MSR_AMD64_RMPOPT_ENABLE		BIT_ULL(MSR_AMD64_RMPOPT_ENABLE_BIT)
 
 #define MSR_SVSM_CAA			0xc001f000
 
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 594cfa19cbd4..0d662221615a 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -662,6 +662,8 @@ static inline void snp_leak_pages(u64 pfn, unsigned int pages)
 	__snp_leak_pages(pfn, pages, true);
 }
 int snp_prepare(void);
+void snp_setup_rmpopt(void);
+void snp_clear_rmpopt_configured(void);
 void snp_shutdown(void);
 #else
 static inline bool snp_probe_rmptable_info(void) { return false; }
@@ -680,6 +682,8 @@ static inline void snp_leak_pages(u64 pfn, unsigned int npages) {}
 static inline void kdump_sev_callback(void) { }
 static inline void snp_fixup_e820_tables(void) {}
 static inline int snp_prepare(void) { return -ENODEV; }
+static inline void snp_setup_rmpopt(void) {}
+static inline void snp_clear_rmpopt_configured(void) {}
 static inline void snp_shutdown(void) {}
 #endif
 
diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index 8bcdce98f6dc..1b5c18408f0b 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -124,6 +124,10 @@ static void *rmp_bookkeeping __ro_after_init;
 
 static u64 probed_rmp_base, probed_rmp_size;
 
+static cpumask_t rmpopt_cpumask;
+static phys_addr_t rmpopt_pa_start;
+static bool rmpopt_configured;
+
 static LIST_HEAD(snp_leaked_pages_list);
 static DEFINE_SPINLOCK(snp_leaked_pages_list_lock);
 
@@ -490,7 +494,12 @@ static bool __init setup_rmptable(void)
 	if (rmp_cfg & MSR_AMD64_SEG_RMP_ENABLED) {
 		if (!setup_segmented_rmptable())
 			return false;
+		rmpopt_configured = true;
 	} else {
+		/*
+		 * RMPOPT requires a segmented RMP table, so leave
+		 * rmpopt_configured clear on contiguous RMP systems.
+		 */
 		if (!setup_contiguous_rmptable())
 			return false;
 	}
@@ -555,6 +564,21 @@ int snp_prepare(void)
 }
 EXPORT_SYMBOL_FOR_MODULES(snp_prepare, "ccp");
 
+static void rmpopt_cleanup(void)
+{
+	int cpu;
+
+	cpus_read_lock();
+
+	for_each_cpu(cpu, &rmpopt_cpumask)
+		WARN_ON_ONCE(wrmsrq_on_cpu(cpu, MSR_AMD64_RMPOPT_BASE, 0));
+
+	cpus_read_unlock();
+
+	cpumask_clear(&rmpopt_cpumask);
+	rmpopt_pa_start = 0;
+}
+
 void snp_shutdown(void)
 {
 	u64 syscfg;
@@ -563,11 +587,57 @@ void snp_shutdown(void)
 	if (syscfg & MSR_AMD64_SYSCFG_SNP_EN)
 		return;
 
+	rmpopt_cleanup();
+
 	clear_rmp();
 	on_each_cpu(mfd_reconfigure, NULL, 1);
 }
 EXPORT_SYMBOL_FOR_MODULES(snp_shutdown, "ccp");
 
+void snp_clear_rmpopt_configured(void)
+{
+	rmpopt_configured = false;
+}
+
+void snp_setup_rmpopt(void)
+{
+	u64 rmpopt_base;
+	int cpu;
+
+	if (!cpu_feature_enabled(X86_FEATURE_RMPOPT) || !rmpopt_configured)
+		return;
+
+	cpus_read_lock();
+
+	/*
+	 * The RMPOPT_BASE MSR is per-core, so only one thread per core needs
+	 * to set up the RMPOPT_BASE MSR.
+	 *
+	 * Note: only online primary threads are included.  If a core's
+	 * primary thread is offline, that core is not covered.  CPU hotplug
+	 * is not currently supported with SNP enabled.
+	 */
+
+	for_each_online_cpu(cpu)
+		if (topology_is_primary_thread(cpu))
+			cpumask_set_cpu(cpu, &rmpopt_cpumask);
+
+	rmpopt_pa_start = ALIGN_DOWN(PFN_PHYS(min_low_pfn), SZ_1G);
+	rmpopt_base = rmpopt_pa_start | MSR_AMD64_RMPOPT_ENABLE;
+
+	/*
+	 * Per-CPU RMPOPT tables support at most 2 TB of addressable memory
+	 * for RMP optimizations. Initialize the per-CPU RMPOPT table base
+	 * to the starting physical address to enable RMP optimizations for
+	 * up to 2 TB of system RAM on all CPUs.
+	 */
+	for_each_cpu(cpu, &rmpopt_cpumask)
+		WARN_ON_ONCE(wrmsrq_on_cpu(cpu, MSR_AMD64_RMPOPT_BASE, rmpopt_base));
+
+	cpus_read_unlock();
+}
+EXPORT_SYMBOL_FOR_MODULES(snp_setup_rmpopt, "ccp");
+
 /*
  * Do the necessary preparations which are verified by the firmware as
  * described in the SNP_INIT_EX firmware command description in the SNP
diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 78f98aee7a66..217b6b19802e 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1478,6 +1478,9 @@ static int __sev_snp_init_locked(int *error, unsigned int max_snp_asid)
 	}
 
 	snp_hv_fixed_pages_state_update(sev, HV_FIXED);
+
+	snp_setup_rmpopt();
+
 	sev->snp_initialized = true;
 	dev_dbg(sev->dev, "SEV-SNP firmware initialized, SEV-TIO is %s\n",
 		data.tio_en ? "enabled" : "disabled");

---

## [3] Ashish Kalra — 2026-06-15
*Subject: [PATCH v8 3/7] crypto/ccp: Disable CPU hotplug while SNP is active*

From: Ashish Kalra <ashish.kalra@amd.com>

The SEV firmware enumerates the CPUs at SNP initialization and is not
aware of the OS bringing CPUs online or offline afterwards, so OS CPU
hotplug can diverge from the firmware's expectations and break SNP.
Disable CPU hotplug while SNP is active.

SNP is fully torn down only on the SNP_SHUTDOWN_EX x86_snp_shutdown
path; the legacy path leaves SNP enabled in hardware while clearing
snp_initialized, so __sev_snp_init_locked() can run again.  Track the
disable with a flag so it is balanced by a matching enable rather than
stacked, and re-enable hotplug only on the x86_snp_shutdown path, after
snp_shutdown() has cleared the per-core RMPOPT_BASE MSRs with hotplug
still disabled.

This also keeps the CPU set stable for the asynchronous RMPOPT scan
added later in this series, and ensures cpus_read_lock() in the scan
is uncontended.

Suggested-by: Thomas Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 drivers/crypto/ccp/sev-dev.c | 29 ++++++++++++++++++++++++++++-
 1 file changed, 28 insertions(+), 1 deletion(-)

diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 217b6b19802e..c8c3c577463c 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -106,6 +106,9 @@ struct snp_hv_fixed_pages_entry {
 
 static LIST_HEAD(snp_hv_fixed_pages);
 
+/* Set while SNP has CPU hotplug disabled. */
+static bool snp_cpu_hotplug_disabled;
+
 /* Trusted Memory Region (TMR):
  *   The TMR is a 1MB area that must be 1MB aligned.  Use the page allocator
  *   to allocate the memory, which will return aligned memory for the specified
@@ -1479,6 +1482,17 @@ static int __sev_snp_init_locked(int *error, unsigned int max_snp_asid)
 
 	snp_hv_fixed_pages_state_update(sev, HV_FIXED);
 
+	/*
+	 * Disable CPU hotplug while SNP is active.  Guard against stacking
+	 * the disable count: the legacy SNP_SHUTDOWN_EX path clears
+	 * snp_initialized without re-enabling hotplug, so this can run
+	 * again while hotplug is already disabled.
+	 */
+	if (!snp_cpu_hotplug_disabled) {
+		cpu_hotplug_disable();
+		snp_cpu_hotplug_disabled = true;
+	}
+
 	snp_setup_rmpopt();
 
 	sev->snp_initialized = true;
@@ -2083,8 +2097,21 @@ static int __sev_snp_shutdown_locked(int *error, bool panic)
 	}
 
 	if (data.x86_snp_shutdown) {
-		if (!panic)
+		if (!panic) {
 			snp_shutdown();
+			/*
+			 * snp_shutdown() fully tears SNP down (clear_rmp()) and
+			 * has already cleared the per-core RMPOPT_BASE MSRs via
+			 * rmpopt_cleanup() with hotplug still disabled.  Re-enable
+			 * CPU hotplug now.  On the legacy path SNP stays
+			 * enabled in hardware, so hotplug is correctly left
+			 * disabled.
+			 */
+			if (snp_cpu_hotplug_disabled) {
+				cpu_hotplug_enable();
+				snp_cpu_hotplug_disabled = false;
+			}
+		}
 		snp_hv_fixed_pages_state_update(sev, ALLOCATED);
 	} else {
 		/*

---

## [4] Ashish Kalra — 2026-06-15
*Subject: [PATCH v8 4/7] x86/sev: Add support to perform RMP optimizations asynchronously*

From: Ashish Kalra <ashish.kalra@amd.com>

When SEV-SNP is enabled, all writes to memory are checked to ensure
integrity of SNP guest memory. This imposes performance overhead on the
whole system.

RMPOPT is a new instruction that minimizes the performance overhead of
RMP checks on the hypervisor and on non-SNP guests by allowing RMP
checks to be skipped for 1GB regions of memory that are known not to
contain any SEV-SNP guest memory.

Add support for performing RMP optimizations asynchronously using a
dedicated workqueue.

Enable RMPOPT optimizations for up to 2TB of system RAM starting from
the lowest physical memory address aligned down to a 1GB boundary at
RMP initialization time. RMP checks can initially be skipped for 1GB
memory ranges that do not contain SEV-SNP guest memory (excluding
preassigned pages such as the RMP table and firmware pages). As SNP
guests are launched, RMPUPDATE will disable the corresponding RMPOPT
optimizations.

Suggested-by: Thomas Lendacky <thomas.lendacky@amd.com>
Suggested-by: Dave Hansen <dave.hansen@linux.intel.com>
Reviewed-by: Ackerley Tng <ackerleytng@google.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/virt/svm/sev.c | 230 +++++++++++++++++++++++++++++++++++++++-
 1 file changed, 227 insertions(+), 3 deletions(-)

diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index 1b5c18408f0b..b63b639bfc30 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -19,6 +19,7 @@
 #include <linux/iommu.h>
 #include <linux/amd-iommu.h>
 #include <linux/nospec.h>
+#include <linux/workqueue.h>
 
 #include <asm/sev.h>
 #include <asm/processor.h>
@@ -125,9 +126,20 @@ static void *rmp_bookkeeping __ro_after_init;
 static u64 probed_rmp_base, probed_rmp_size;
 
 static cpumask_t rmpopt_cpumask;
-static phys_addr_t rmpopt_pa_start;
+static phys_addr_t rmpopt_pa_start, rmpopt_pa_end;
 static bool rmpopt_configured;
 
+enum rmpopt_function {
+	RMPOPT_FUNC_VERIFY_AND_REPORT_STATUS,
+	RMPOPT_FUNC_REPORT_STATUS
+};
+
+#define RMPOPT_WORK_TIMEOUT	10000
+
+static struct workqueue_struct *rmpopt_wq;
+static struct delayed_work rmpopt_delayed_work;
+static DEFINE_MUTEX(rmpopt_wq_mutex);
+
 static LIST_HEAD(snp_leaked_pages_list);
 static DEFINE_SPINLOCK(snp_leaked_pages_list_lock);
 
@@ -568,6 +580,14 @@ static void rmpopt_cleanup(void)
 {
 	int cpu;
 
+	guard(mutex)(&rmpopt_wq_mutex);
+
+	if (!rmpopt_wq)
+		return;
+
+	cancel_delayed_work_sync(&rmpopt_delayed_work);
+	destroy_workqueue(rmpopt_wq);
+
 	cpus_read_lock();
 
 	for_each_cpu(cpu, &rmpopt_cpumask)
@@ -576,7 +596,8 @@ static void rmpopt_cleanup(void)
 	cpus_read_unlock();
 
 	cpumask_clear(&rmpopt_cpumask);
-	rmpopt_pa_start = 0;
+	rmpopt_pa_start = rmpopt_pa_end = 0;
+	rmpopt_wq = NULL;
 }
 
 void snp_shutdown(void)
@@ -599,6 +620,168 @@ void snp_clear_rmpopt_configured(void)
 	rmpopt_configured = false;
 }
 
+/*
+ * RMPOPT: F2 0F 01 FC
+ *   Input:  RAX = system physical address (1GB aligned)
+ *           RCX = operation type
+ *   Output: CF set if the range was optimized
+ */
+static inline bool __rmpopt(u64 pa_start, u64 op_type)
+{
+	bool optimized;
+
+	asm volatile(".byte 0xf2, 0x0f, 0x01, 0xfc"
+		     : "=@ccc" (optimized)
+		     : "a" (pa_start), "c" (op_type)
+		     : "memory", "cc");
+
+	return optimized;
+}
+
+static void rmpopt(u64 pa)
+{
+	u64 pa_start = ALIGN_DOWN(pa, SZ_1G);
+	u64 op_type = RMPOPT_FUNC_VERIFY_AND_REPORT_STATUS;
+
+	__rmpopt(pa_start, op_type);
+}
+
+/*
+ * 'val' is a system physical address.
+ */
+static void rmpopt_smp(void *val)
+{
+	rmpopt((u64)val);
+}
+
+/*
+ * Leader function for work_on_cpu(): runs the full RMPOPT scan in
+ * process context on a CPU that has RMPOPT_BASE MSR programmed.
+ */
+static long rmpopt_leader_fn(void *arg)
+{
+	phys_addr_t pa;
+
+	for (pa = rmpopt_pa_start; pa < rmpopt_pa_end; pa += SZ_1G) {
+		rmpopt(pa);
+		cond_resched();
+	}
+	return 0;
+}
+
+/*
+ * RMPOPT optimizations skip RMP checks at 1GB granularity if this
+ * range of memory does not contain any SNP guest memory.
+ */
+static void rmpopt_work_handler(struct work_struct *work)
+{
+	cpumask_var_t follower_mask;
+	phys_addr_t pa;
+	int this_cpu;
+
+	pr_info("Attempt RMP optimizations on physical address range @1GB alignment [0x%016llx - 0x%016llx]\n",
+		rmpopt_pa_start, rmpopt_pa_end);
+
+	if (!alloc_cpumask_var(&follower_mask, GFP_KERNEL))
+		return;
+
+	/*
+	 * RMPOPT scans the RMP table, stores the result of the scan in the
+	 * reserved processor memory. The RMP scan is the most expensive
+	 * part. If a second RMPOPT occurs, it can skip the expensive scan
+	 * if they can see a cached result in the reserved processor memory.
+	 *
+	 * Do RMPOPT on one CPU alone. Then, follow that up with RMPOPT
+	 * on every other primary thread. Followers are "designed to"
+	 * skip the scan if they see the "cached" scan results.
+	 */
+	cpumask_copy(follower_mask, &rmpopt_cpumask);
+
+	/*
+	 * Pin the worker to the current CPU for the leader loop so that
+	 * this_cpu remains valid and the RMPOPT instruction executes on
+	 * the correct CPU.
+	 *
+	 * Use migrate_disable() rather than get_cpu() to prevent
+	 * migration while still allowing preemption.
+	 */
+	migrate_disable();
+	this_cpu = smp_processor_id();
+
+	if (cpumask_test_cpu(this_cpu, follower_mask)) {
+		/*
+		 * Current CPU is a primary thread in rmpopt_cpumask.
+		 * Run leader locally and remove from follower mask.
+		 */
+		cpumask_clear_cpu(this_cpu, follower_mask);
+
+		for (pa = rmpopt_pa_start; pa < rmpopt_pa_end; pa += SZ_1G) {
+			rmpopt(pa);
+			cond_resched();
+		}
+	} else if (cpumask_intersects(topology_sibling_cpumask(this_cpu),
+				      follower_mask)) {
+		/*
+		 * Current CPU is a sibling thread whose primary is in
+		 * rmpopt_cpumask.  RMPOPT_BASE MSR is per-core, so it
+		 * is safe to run the leader locally.  Remove the sibling's
+		 * primary from the follower mask as this core is already
+		 * covered by the leader.
+		 */
+		cpumask_andnot(follower_mask, follower_mask,
+			       topology_sibling_cpumask(this_cpu));
+
+		for (pa = rmpopt_pa_start; pa < rmpopt_pa_end; pa += SZ_1G) {
+			rmpopt(pa);
+			cond_resched();
+		}
+	} else {
+		/*
+		 * Current CPU does not have RMPOPT_BASE MSR programmed.
+		 * Pick an explicit leader from the cpumask to avoid #UD.
+		 * Use work_on_cpu() to run in process context on the leader,
+		 * avoiding IPI latency.
+		 */
+		int leader_cpu = cpumask_first(follower_mask);
+
+		if (WARN_ON_ONCE(leader_cpu >= nr_cpu_ids)) {
+			migrate_enable();
+			goto out;
+		}
+
+		cpumask_clear_cpu(leader_cpu, follower_mask);
+
+		/* Release migration pin before work_on_cpu(). */
+		migrate_enable();
+
+		work_on_cpu(leader_cpu, rmpopt_leader_fn, NULL);
+
+		goto followers;
+	}
+
+	migrate_enable();
+
+followers:
+	/*
+	 * Followers: run RMPOPT on remaining cores.
+	 * CPU hotplug is disabled while SNP is active
+	 * (cpu_hotplug_disable() in __sev_snp_init_locked()),
+	 * so cpus_read_lock() is uncontended.
+	 */
+	cpus_read_lock();
+	for (pa = rmpopt_pa_start; pa < rmpopt_pa_end; pa += SZ_1G) {
+		on_each_cpu_mask(follower_mask, rmpopt_smp,
+				 (void *)pa, true);
+
+		 /* Give a chance for other threads to run */
+		cond_resched();
+	}
+	cpus_read_unlock();
+
+out:
+	free_cpumask_var(follower_mask);
+}
+
 void snp_setup_rmpopt(void)
 {
 	u64 rmpopt_base;
@@ -607,11 +790,37 @@ void snp_setup_rmpopt(void)
 	if (!cpu_feature_enabled(X86_FEATURE_RMPOPT) || !rmpopt_configured)
 		return;
 
+	guard(mutex)(&rmpopt_wq_mutex);
+
+	/*
+	 * Guard against re-initialization.  When SNP_SHUTDOWN_EX is issued
+	 * with x86_snp_shutdown=0, snp_shutdown() is not called and
+	 * rmpopt_cleanup() is skipped, but snp_initialized is still cleared.
+	 * A subsequent __sev_snp_init_locked() would call snp_setup_rmpopt()
+	 * again, leaking the existing workqueue, delayed work, debugfs
+	 * entries, and cpumask state.
+	 */
+	if (rmpopt_wq)
+		return;
+
+	/*
+	 * Create an RMPOPT-specific workqueue to avoid scheduling
+	 * RMPOPT workitem on the global system workqueue.
+	 */
+	rmpopt_wq = alloc_workqueue("rmpopt_wq", WQ_UNBOUND, 1);
+	if (!rmpopt_wq) {
+		pr_err("Failed to allocate RMPOPT workqueue\n");
+		return;
+	}
+
+	INIT_DELAYED_WORK(&rmpopt_delayed_work, rmpopt_work_handler);
+
 	cpus_read_lock();
 
 	/*
 	 * The RMPOPT_BASE MSR is per-core, so only one thread per core needs
-	 * to set up the RMPOPT_BASE MSR.
+	 * to set up the RMPOPT_BASE MSR. Likewise, only one thread per core
+	 * needs to issue the RMPOPT instruction.
 	 *
 	 * Note: only online primary threads are included.  If a core's
 	 * primary thread is offline, that core is not covered.  CPU hotplug
@@ -635,6 +844,21 @@ void snp_setup_rmpopt(void)
 		WARN_ON_ONCE(wrmsrq_on_cpu(cpu, MSR_AMD64_RMPOPT_BASE, rmpopt_base));
 
 	cpus_read_unlock();
+
+	rmpopt_pa_end = ALIGN(PFN_PHYS(max_pfn), SZ_1G);
+
+	/* Limit memory scanning to 2TB of RAM */
+	if ((rmpopt_pa_end - rmpopt_pa_start) > SZ_2T) {
+		pr_info("RMPOPT coverage limited to 2TB; memory above 0x%llx not optimized\n",
+			rmpopt_pa_start + SZ_2T);
+		rmpopt_pa_end = rmpopt_pa_start + SZ_2T;
+	}
+
+	/*
+	 * Once all per-CPU RMPOPT tables have been configured, enable RMPOPT
+	 * optimizations on all physical memory.
+	 */
+	queue_delayed_work(rmpopt_wq, &rmpopt_delayed_work, 0);
 }
 EXPORT_SYMBOL_FOR_MODULES(snp_setup_rmpopt, "ccp");

---

## [5] Ashish Kalra — 2026-06-15
*Subject: [PATCH v8 5/7] x86/sev: Add interface to re-enable RMP optimizations.*

From: Ashish Kalra <ashish.kalra@amd.com>

RMPOPT table is a per-CPU table which indicates if 1GB regions of
physical memory are entirely hypervisor-owned or not.

When performing host memory accesses in hypervisor mode as well as
non-SNP guest mode, the processor may consult the RMPOPT table to
potentially skip an RMP access and improve performance.

Events such as RMPUPDATE can clear RMP optimizations. Add an interface
to re-enable those optimizations.

The interface uses mod_delayed_work() instead of queue_delayed_work()
so that the delay timer is reset on each call. This provides proper
batching semantics: re-optimization runs 10 seconds after the *last*
VM termination rather than after the first. mod_delayed_work() also
re-queues work that is already in-flight, so a re-scan request
during an active scan is not silently dropped.

Reviewed-by: Ackerley Tng <ackerleytng@google.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/include/asm/sev.h |  2 ++
 arch/x86/virt/svm/sev.c    | 15 +++++++++++++++
 2 files changed, 17 insertions(+)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 0d662221615a..a11306f25336 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -662,6 +662,7 @@ static inline void snp_leak_pages(u64 pfn, unsigned int pages)
 	__snp_leak_pages(pfn, pages, true);
 }
 int snp_prepare(void);
+void snp_rmpopt_all_physmem(void);
 void snp_setup_rmpopt(void);
 void snp_clear_rmpopt_configured(void);
 void snp_shutdown(void);
@@ -682,6 +683,7 @@ static inline void snp_leak_pages(u64 pfn, unsigned int npages) {}
 static inline void kdump_sev_callback(void) { }
 static inline void snp_fixup_e820_tables(void) {}
 static inline int snp_prepare(void) { return -ENODEV; }
+static inline void snp_rmpopt_all_physmem(void) {}
 static inline void snp_setup_rmpopt(void) {}
 static inline void snp_clear_rmpopt_configured(void) {}
 static inline void snp_shutdown(void) {}
diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index b63b639bfc30..253a534b9a0d 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -782,6 +782,21 @@ static void rmpopt_work_handler(struct work_struct *work)
 	free_cpumask_var(follower_mask);
 }
 
+void snp_rmpopt_all_physmem(void)
+{
+	if (!cpu_feature_enabled(X86_FEATURE_RMPOPT) || !rmpopt_configured)
+		return;
+
+	guard(mutex)(&rmpopt_wq_mutex);
+
+	if (!rmpopt_wq)
+		return;
+
+	mod_delayed_work(rmpopt_wq, &rmpopt_delayed_work,
+			 msecs_to_jiffies(RMPOPT_WORK_TIMEOUT));
+}
+EXPORT_SYMBOL_GPL(snp_rmpopt_all_physmem);
+
 void snp_setup_rmpopt(void)
 {
 	u64 rmpopt_base;

---

## [6] Ashish Kalra — 2026-06-15
*Subject: [PATCH v8 6/7] KVM: SEV: Perform RMP optimizations on SNP guest shutdown*

From: Ashish Kalra <ashish.kalra@amd.com>

Pages are converted from shared to private as SNP guests are launched.
This destroys exisiting RMPOPT optimizations in the regions where
pages are converted.

Conversely, guest pages are converted back to shared during SNP guest
termination and their region may become eligible for RMPOPT
optimization.

To take advantage of this, perform RMPOPT after guest termination.
Do it after a delay so that a single RMPOPT pass can be done if
multiple guests terminate in a short period of time.

Acked-by: Dave Hansen <dave.hansen@linux.intel.com>
Reviewed-by: Ackerley Tng <ackerleytng@google.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/kvm/svm/sev.c | 2 ++
 1 file changed, 2 insertions(+)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index e107f368ed2d..29af6f6e603c 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -3005,6 +3005,8 @@ void sev_vm_destroy(struct kvm *kvm)
 		 */
 		if (snp_decommission_context(kvm))
 			return;
+
+		snp_rmpopt_all_physmem();
 	} else {
 		sev_unbind_asid(kvm, sev->handle);
 	}

---

## [7] Ashish Kalra — 2026-06-15
*Subject: [PATCH v8 7/7] x86/sev: Add debugfs support for RMPOPT*

From: Ashish Kalra <ashish.kalra@amd.com>

Add a debugfs interface to report per-CPU RMPOPT status across all
system RAM.

To dump the per-CPU RMPOPT status for all system RAM:

/sys/kernel/debug/rmpopt# cat rmpopt-table

Memory @  0GB: CPU(s): none
Memory @  1GB: CPU(s): none
Memory @  2GB: CPU(s): 0-1023
Memory @  3GB: CPU(s): 0-1023
Memory @  4GB: CPU(s): none
Memory @  5GB: CPU(s): 0-1023
Memory @  6GB: CPU(s): 0-1023
Memory @  7GB: CPU(s): 0-1023
...
Memory @1025GB: CPU(s): 0-1023
Memory @1026GB: CPU(s): 0-1023
Memory @1027GB: CPU(s): 0-1023
Memory @1028GB: CPU(s): 0-1023
Memory @1029GB: CPU(s): 0-1023
Memory @1030GB: CPU(s): 0-1023
Memory @1031GB: CPU(s): 0-1023
Memory @1032GB: CPU(s): 0-1023
Memory @1033GB: CPU(s): 0-1023
Memory @1034GB: CPU(s): 0-1023
Memory @1035GB: CPU(s): 0-1023
Memory @1036GB: CPU(s): 0-1023
Memory @1037GB: CPU(s): 0-1023
Memory @1038GB: CPU(s): none

Suggested-by: Thomas Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/virt/svm/sev.c | 128 ++++++++++++++++++++++++++++++++++++++++
 1 file changed, 128 insertions(+)

diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index 253a534b9a0d..b8b00c50ce41 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -20,6 +20,8 @@
 #include <linux/amd-iommu.h>
 #include <linux/nospec.h>
 #include <linux/workqueue.h>
+#include <linux/debugfs.h>
+#include <linux/seq_file.h>
 
 #include <asm/sev.h>
 #include <asm/processor.h>
@@ -145,6 +147,15 @@ static DEFINE_SPINLOCK(snp_leaked_pages_list_lock);
 
 static unsigned long snp_nr_leaked_pages;
 
+/* All users of rmpopt_report_cpumask must hold rmpopt_show_mutex. */
+static cpumask_t rmpopt_report_cpumask;
+static struct dentry *rmpopt_debugfs;
+static DEFINE_MUTEX(rmpopt_show_mutex);
+
+struct seq_paddr {
+	phys_addr_t next_seq_paddr;
+};
+
 #undef pr_fmt
 #define pr_fmt(fmt)	"SEV-SNP: " fmt
 
@@ -587,6 +598,8 @@ static void rmpopt_cleanup(void)
 
 	cancel_delayed_work_sync(&rmpopt_delayed_work);
 	destroy_workqueue(rmpopt_wq);
+	debugfs_remove_recursive(rmpopt_debugfs);
+	rmpopt_debugfs = NULL;
 
 	cpus_read_lock();
 
@@ -635,6 +648,10 @@ static inline bool __rmpopt(u64 pa_start, u64 op_type)
 		     : "a" (pa_start), "c" (op_type)
 		     : "memory", "cc");
 
+	if (op_type == RMPOPT_FUNC_REPORT_STATUS)
+		assign_cpu(smp_processor_id(), &rmpopt_report_cpumask,
+			   optimized);
+
 	return optimized;
 }
 
@@ -669,6 +686,115 @@ static long rmpopt_leader_fn(void *arg)
 	return 0;
 }
 
+/*
+ * 'val' is a system physical address.
+ */
+static void rmpopt_report_status(void *val)
+{
+	u64 pa_start = ALIGN_DOWN((u64)val, SZ_1G);
+	u64 op_type = RMPOPT_FUNC_REPORT_STATUS;
+
+	__rmpopt(pa_start, op_type);
+}
+
+/*
+ * start() can be called multiple times if allocated buffer has overflowed
+ * and bigger buffer is allocated.
+ */
+static void *rmpopt_table_seq_start(struct seq_file *seq, loff_t *pos)
+{
+	phys_addr_t end_paddr = rmpopt_pa_end;
+	struct seq_paddr *p = seq->private;
+
+	if (*pos == 0) {
+		p->next_seq_paddr = rmpopt_pa_start;
+		if (p->next_seq_paddr >= end_paddr)
+			return NULL;
+		return &p->next_seq_paddr;
+	}
+
+	if (p->next_seq_paddr >= end_paddr)
+		return NULL;
+
+	return &p->next_seq_paddr;
+}
+
+static void *rmpopt_table_seq_next(struct seq_file *seq, void *v, loff_t *pos)
+{
+	phys_addr_t end_paddr = rmpopt_pa_end;
+	phys_addr_t *curr_paddr = v;
+
+	(*pos)++;
+	*curr_paddr += SZ_1G;
+	if (*curr_paddr >= end_paddr)
+		return NULL;
+
+	return curr_paddr;
+}
+
+static void rmpopt_table_seq_stop(struct seq_file *seq, void *v)
+{
+}
+
+static int rmpopt_table_seq_show(struct seq_file *seq, void *v)
+{
+	phys_addr_t *curr_paddr = v;
+
+	guard(mutex)(&rmpopt_show_mutex);
+
+	seq_printf(seq, "Memory @%3lluGB: ",
+		   *curr_paddr >> (get_order(SZ_1G) + PAGE_SHIFT));
+
+	/*
+	 * Query all online CPUs rather than just rmpopt_cpumask (primary
+	 * threads only). The RMPOPT instruction only needs to run on one
+	 * thread per core for the optimization to take effect, but debugfs
+	 * reporting requires the RMPOPT status across all CPUs.
+	 * Performance is not a concern for this diagnostic interface.
+	 *
+	 * This is safe because RMPOPT_BASE MSR is per-core and
+	 * snp_prepare() ensures all CPUs are online when the MSR is
+	 * programmed during snp_setup_rmpopt().
+	 */
+	cpumask_clear(&rmpopt_report_cpumask);
+	on_each_cpu_mask(cpu_online_mask, rmpopt_report_status,
+			 (void *)*curr_paddr, true);
+
+	if (cpumask_empty(&rmpopt_report_cpumask))
+		seq_puts(seq, "CPU(s): none\n");
+	else
+		seq_printf(seq, "CPU(s): %*pbl\n", cpumask_pr_args(&rmpopt_report_cpumask));
+
+	return 0;
+}
+
+static const struct seq_operations rmpopt_table_seq_ops = {
+	.start = rmpopt_table_seq_start,
+	.next = rmpopt_table_seq_next,
+	.stop = rmpopt_table_seq_stop,
+	.show = rmpopt_table_seq_show
+};
+
+static int rmpopt_table_open(struct inode *inode, struct file *file)
+{
+	return seq_open_private(file, &rmpopt_table_seq_ops, sizeof(struct seq_paddr));
+}
+
+static const struct file_operations rmpopt_table_fops = {
+	.open = rmpopt_table_open,
+	.read = seq_read,
+	.llseek = seq_lseek,
+	.release = seq_release_private,
+};
+
+static void rmpopt_debugfs_setup(void)
+{
+	rmpopt_debugfs = debugfs_create_dir("rmpopt", arch_debugfs_dir);
+
+	debugfs_create_file("rmpopt-table", 0400, rmpopt_debugfs,
+			    NULL, &rmpopt_table_fops);
+}
+
 /*
  * RMPOPT optimizations skip RMP checks at 1GB granularity if this
  * range of memory does not contain any SNP guest memory.
@@ -874,6 +1000,8 @@ void snp_setup_rmpopt(void)
 	 * optimizations on all physical memory.
 	 */
 	queue_delayed_work(rmpopt_wq, &rmpopt_delayed_work, 0);
+
+	rmpopt_debugfs_setup();
 }
 EXPORT_SYMBOL_FOR_MODULES(snp_setup_rmpopt, "ccp");

---

## [8] K Prateek Nayak — 2026-06-16
*Subject: Re: [PATCH v8 2/7] x86/sev: Initialize RMPOPT configuration MSRs*

Hello Ashish,

On 6/16/2026 1:18 AM, Ashish Kalra wrote:
> diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
> index 8bcdce98f6dc..1b5c18408f0b 100644

nit.

I believe you can use cpumask_var_t here and do a zalloc_cpumask_var()
during snp_setup_rmpopt(). That way !X86_FEATURE_RMPOPT configs don't
have to needlessly waste space to keep a redundant cpumask around.

Same comment for rmpopt_report_cpumask in Patch 7 which can be
allocated dynamically during rmpopt_debugfs_setup().

> +static phys_addr_t rmpopt_pa_start;
> +static bool rmpopt_configured;

nit.

You can use guard(cpus_read_lock)() unless there is a complicated
locking pattern where you need to drop and re-acquire the read lock.

> +
> +	for_each_cpu(cpu, &rmpopt_cpumask)

---

## [9] K Prateek Nayak — 2026-06-16
*Subject: Re: [PATCH v8 4/7] x86/sev: Add support to perform RMP optimizations
 asynchronously*

Hello Ashish,

On 6/16/2026 1:19 AM, Ashish Kalra wrote:
> +	/*
> +	 * RMPOPT scans the RMP table, stores the result of the scan in the

rmpopt_cpumask is constructed after hotplug is disabled but ...

> +
> +	/*

... this_cpu is neither in the "rmpopt_cpumask", nor is any of its
siblings on "rmpopt_cpumask".

How does that happen?

> +		int leader_cpu = cpumask_first(follower_mask);
> +

This creates a delayed work and also waits for it to finish execution
which will add more latency than a simple IPI if the comment about IPI
latency above is accurate.

I think there is some corner case in construction of the
"rmpopt_cpumask" that requires this not-so-pretty else block. Can you
elaborate why this is required?

Perhaps the "rmpopt_cpumask" construction needs:

    for_each_online_cpu(cpu) {
        /* Nominate the first CPU on the sibling mask for RMPOPT */
        if (cpu != cpumask_first(topology_sibling_cpumask(cpu)))
            continue;
        cpumask_set_cpu(cpu, &rmpopt_cpumask);
    }


and all you need here is:

    /* Do RMPOPt for local core */
    for (pa = rmpopt_pa_start; pa < rmpopt_pa_end; pa += SZ_1G)
        rmpopt(pa);

    /* Skip this core from concurrent RMPOPT */
    cpumask_and_not(follower_mask, &rmpopt_cpumask, topology_sibling_cpumask(cpu));

No?

> +
> +		goto followers;

---

## [10] Kalra, Ashish — 2026-06-16
*Subject: Re: [PATCH v8 4/7] x86/sev: Add support to perform RMP optimizations
 asynchronously*

Hello Prateek,

On 6/16/2026 2:27 AM, K Prateek Nayak wrote:
> Hello Ashish,
> 

Actually, this was the implementation before the CPU hotplug disable enforcement code was implemented and added in v8,
and i should have fixed this rmpopt_work_handler() accordingly for v8.

With the enforced cpu hotplug disable support, case #3 here (above) is now dead code, and removing it lets
cases #1 and #2 collapse too.

snp_prepare() requires cpu_online_mask == cpu_present_mask before SNP init — so when snp_setup_rmpopt() programs the MSRs, every
core's primary is online -> every core is in rmpopt_cpumask.
  
So now the work handler always runs on a CPU whose core is programmed. topology_sibling_cpumask(this_cpu) therefore always intersects
rmpopt_cpumask -> case #1 or #2 always matches.

So i should actually drop case #3 here - which is: "this_cpu is neither in the "rmpopt_cpumask", nor is any of its
siblings on rmpopt_cpumask"


> 
>> +		int leader_cpu = cpumask_first(follower_mask);

Yes, a simpler implementation will be like this: 
...

 	if (!alloc_cpumask_var(&follower_mask, GFP_KERNEL))
                return;

 	cpumask_copy(follower_mask, &rmpopt_cpumask);

        /*
         * The current CPU's core always has RMPOPT_BASE programmed
         * (snp_prepare() required all CPUs online at setup and CPU hotplug
         * is disabled while SNP is active), so it can always be the leader.
         * RMPOPT_BASE is per-core; exclude this core from the followers.
         */
        migrate_disable();
        cpumask_andnot(follower_mask, follower_mask,
                       topology_sibling_cpumask(smp_processor_id()));

        for (pa = rmpopt_pa_start; pa < rmpopt_pa_end; pa += SZ_1G) {
                rmpopt(pa);
                cond_resched();
        }
        migrate_enable();

        cpus_read_lock();
        for (pa = rmpopt_pa_start; pa < rmpopt_pa_end; pa += SZ_1G) {
                on_each_cpu_mask(follower_mask, rmpopt_smp, (void *)pa, true);
                cond_resched();
        }
        cpus_read_unlock();

        free_cpumask_var(follower_mask);


 Here, the leader exclusion must use the sibling mask, not clear_cpu(this_cpu). That's why my collapsed version uses:

        cpumask_andnot(follower_mask, follower_mask,
                       topology_sibling_cpumask(smp_processor_id()));

  - If this_cpu is a primary: its sibling mask contains itself (the primary) -> andnot removes this core's primary from the followers.
  
  - If this_cpu is a secondary: it isn't in follower_mask at all, but its sibling mask contains its primary, which is in
  follower_mask -> andnot still removes this core's primary. 

  So either way the current core is dropped from the followers. (The old code needed two branches because case #1 used
  clear_cpu(this_cpu) — only correct when this_cpu is the primary — while case #2 used the sibling andnot. The single andnot works for
  both cases).

Thanks,
Ashish

>> +		goto followers;
>> +	}

---

## [11] K Prateek Nayak — 2026-06-17
*Subject: Re: [PATCH v8 4/7] x86/sev: Add support to perform RMP optimizations
 asynchronously*

Hello Ashish,

On 6/17/2026 1:26 AM, Kalra, Ashish wrote:
> Hello Prateek,
> 

Ack.

Also the fact that cpu_mark_primary_thread() uses LSBs of APICID and if
you have some insanely weird configuration - like boot with maxcpus=1,
online all the secondary threads (CPUs 256-511 on a 256C/512T system),
launch an SNP guest - it can actually leave everything except CORE0 out
of the "rmpopt_cpumask".

> 
> 

If you move the migrate_disable() here, you can simply do an andnot
without needing to copy the rmpopt_cpumask beforehand and save on one
cpumask iteration.

>  	cpumask_copy(follower_mask, &rmpopt_cpumask);
> 

I think you can even skip the cpus_read_lock() since we know for a
fact that hotplug is disabled when we are here.

Perhaps we can have a lockdep_assert_cpu_hotplug_disabled() which
ensures we'll get a splat if that assumption ever changes when
running with LOCKDEP?

I'll let others comment if that is a good idea or not.

>         for (pa = rmpopt_pa_start; pa < rmpopt_pa_end; pa += SZ_1G) {
>                 on_each_cpu_mask(follower_mask, rmpopt_smp, (void *)pa, true);

Ack! And I think this looks much cleaner (to my eyes at least ;-)

---

## [12] K Prateek Nayak — 2026-06-17
*Subject: Re: [PATCH v8 3/7] crypto/ccp: Disable CPU hotplug while SNP is
 active*

Hello Ashish,

On 6/16/2026 1:19 AM, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Dumb question: Is this specific to RMPOPT? Otherwise ...

> 
> SNP is fully torn down only on the SNP_SHUTDOWN_EX x86_snp_shutdown

... should this be done before __sev_do_cmd_locked(SEV_CMD_SNP_INIT_EX)
is issued?

I'm assuming that is when the firmware enumerates the CPUs during SNP
initialization and any hotplug after that should be disallowed?

>  	snp_setup_rmpopt();
>

---

## [13] Kalra, Ashish — 2026-06-17
*Subject: Re: [PATCH v8 4/7] x86/sev: Add support to perform RMP optimizations
 asynchronously*

Hello Prateek,

On 6/16/2026 11:20 PM, K Prateek Nayak wrote:
> Hello Ashish,
> 

Yes, that's a nice optimization, we can read directly from rmpopt_cpumask and write follower_mask in one pass.

> 
>>  	cpumask_copy(follower_mask, &rmpopt_cpumask);

Yes, that is true when we have made sure that hotplug is disabled, but i think it is Ok
to keep cpus_read_lock() here as it keeps Sashiko happy.

> 
> I'll let others comment if that is a good idea or not.

Thanks,
Ashish

---

## [14] Kalra, Ashish — 2026-06-17
*Subject: Re: [PATCH v8 3/7] crypto/ccp: Disable CPU hotplug while SNP is
 active*

Hello Prateek,

On 6/16/2026 11:33 PM, K Prateek Nayak wrote:
> Hello Ashish,
> 

The actual reason is purely about the SEV firmware: it enumerates the BIOS-enabled CPUs at SNP_INIT_EX
and has no knowledge of OS hotplug afterward. That's true whether or not RMPOPT exists. 
RMPOPT only benefits from the side effect, which is a stable rmpopt_cpumask and an uncontended cpus_read_lock()
in the work handler.

So it is specific to SNP, but RMPOPT patches that come later in the series rely on it, therefore it
is a pre-patch here.

> 
>>

Yes, it makes sense to do it before SNP_INIT_EX is issued.

Thanks,
Ashish

> 
>>  	snp_setup_rmpopt();

---

## [15] Borislav Petkov — 2026-06-18
*Subject: Re: [PATCH v8 7/7] x86/sev: Add debugfs support for RMPOPT*

On Mon, Jun 15, 2026 at 07:50:56PM +0000, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

https://lwn.net/Articles/309298/

---

## [16] Kalra, Ashish — 2026-06-18
*Subject: Re: [PATCH v8 2/7] x86/sev: Initialize RMPOPT configuration MSRs*

Hello Prateek,

On 6/16/2026 1:03 AM, K Prateek Nayak wrote:
> Hello Ashish,
> 

Yes.

>> +static phys_addr_t rmpopt_pa_start;
>> +static bool rmpopt_configured;

But if i use guard(cpus_read_lock)(), cpus_read_lock stays held across as it is
function-scope, so it will be still held for code following the wrmsrq_on_cpu(),
which is harmless but still changes code behavior.

Probably, the other option is to use scoped_guard form ? 

Thanks,
Ashish

> 
>> +

---

## [17] Kalra, Ashish — 2026-06-18
*Subject: Re: [PATCH v8 7/7] x86/sev: Add debugfs support for RMPOPT*

On 6/18/2026 1:08 PM, Borislav Petkov wrote:
> On Mon, Jun 15, 2026 at 07:50:56PM +0000, Ashish Kalra wrote:
>> From: Ashish Kalra <ashish.kalra@amd.com>

Since the RMPOPT file is a diagnostic (verify the optimization took effect), debugfs is
arguably the right home for it and we are not claiming it to be an API (there is no
Documentation/ABI entry for it) and we are not presenting it as something tools should
depend on, it is a self-contained diagnostic/debug interface.

Maybe i can add a line to this patch's commit message stating it's a debug-only interface
with no stability guarantee.

We have to provide some method/interface for users to verify if RMP optimizations
are enabled for a GB range of memory.

Thanks,
Ashish

---

## [18] Borislav Petkov — 2026-06-18
*Subject: Re: [PATCH v8 7/7] x86/sev: Add debugfs support for RMPOPT*

On Thu, Jun 18, 2026 at 02:57:45PM -0500, Kalra, Ashish wrote:
> Maybe i can add a line to this patch's commit message stating it's a debug-only interface
> with no stability guarantee.

Sounds to me like you didn't really read that article.

> We have to provide some method/interface for users to verify if RMP optimizations
> are enabled for a GB range of memory.

Sounds to me like this wants to be a facility which is present in the kernel
and it is going to be an ABI.

I am unclear on the real use case but I'm open to being persuaded otherwise.

Thx.

---

## [19] Tom Lendacky — 2026-06-18
*Subject: Re: [PATCH v8 2/7] x86/sev: Initialize RMPOPT configuration MSRs*

On 6/15/26 14:48, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

The usage of this isn't doesn't imply what the name says. How about
changing it to rmpopt_capable ?

> +
>  static LIST_HEAD(snp_leaked_pages_list);

I think this comment should be above where rmpopt_configured is set,
slightly changed to

	RMPOPT requires a segmented RMP, so indicate that the system
	is capable of configuring and running RMPOPT.

Thanks,
Tom
>  		if (!setup_contiguous_rmptable())
>  			return false;

---

## [20] Dave Hansen — 2026-06-18
*Subject: Re: [PATCH v8 3/7] crypto/ccp: Disable CPU hotplug while SNP is
 active*

On 6/15/26 12:49, Ashish Kalra wrote:
> +	/*
> +	 * Disable CPU hotplug while SNP is active.  Guard against stacking

This seems like a hack, guys.

cpu_hotplug_disable() seems like more of a temporary lock than enforcing
basically permanent system state.

This seems like it would be better implemented by registering a CPU
hotplug callback and then refusing to offline if sev->snp_initialized is
set.

snp_setup_rmpopt() can be run any time, right? It doesn't need to be
after sev->snp_initialized=1.

---

## [21] Dave Hansen — 2026-06-18
*Subject: Re: [PATCH v8 5/7] x86/sev: Add interface to re-enable RMP
 optimizations.*

On 6/15/26 12:49, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

This doesn't really help me understand when or how this function might
be called.

	Normal guest evens like splitting and collapsing large pages can
	clear RMP optimizations. Without some intervention, all RMP
	optimizations would eventually be lost. Periodically re-optimize
	the system.

> The interface uses mod_delayed_work() instead of queue_delayed_work()
> so that the delay timer is reset on each call. This provides proper

This seems sane.

> +void snp_rmpopt_all_physmem(void)
> +{

Does this need to be globally exported? Or can it be exported to a
single module namespace?

I'm close to being able to ack this, but it's still got a few too many
nits to ack.

---

## [22] Dave Hansen — 2026-06-18
*Subject: Re: [PATCH v8 6/7] KVM: SEV: Perform RMP optimizations on SNP guest
 shutdown*

On 6/15/26 12:50, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Oh, actually that would be good text for the *previous* patch too. You
might want to move some of it there.

---

## [23] Dave Hansen — 2026-06-18
*Subject: Re: [PATCH v8 7/7] x86/sev: Add debugfs support for RMPOPT*

On 6/18/26 12:57, Kalra, Ashish wrote:
> Maybe i can add a line to this patch's commit message stating it's a
> debug-only interface with no stability guarantee.

I'd highly suggest reading the lwn article Boris referenced.

In the meantime, drop this patch from the series. Please. Let's revisit
debugging interfaces *after* this gets merged. That way, you can
concentrate on functionality and not debug interfaces that aren't
critically needed.

---

## [24] Tom Lendacky — 2026-06-18
*Subject: Re: [PATCH v8 3/7] crypto/ccp: Disable CPU hotplug while SNP is
 active*

On 6/16/26 23:33, K Prateek Nayak wrote:
> Hello Ashish,
> 

Any hotplug before would be bad, too. SEV firmware understands what CPUs
are physically available based on the installed processor and BIOS/UEFI
settings (e.g. disabling SMT from the BIOS), not what Linux has online
at the time of SNP_INIT_EX.

So maybe the commit message needs updating about that.

Thanks,
Tom

> 
>>  	snp_setup_rmpopt();

---

## [25] Kalra, Ashish — 2026-06-19
*Subject: Re: [PATCH v8 3/7] crypto/ccp: Disable CPU hotplug while SNP is
 active*

On 6/18/2026 4:35 PM, Dave Hansen wrote:
> On 6/15/26 12:49, Ashish Kalra wrote:
>> +	/*

Yes, snp_setup_rmpopt() doesn't depend on snp_initialized. Programming RMPOPT_BASE only needs
the CPU online and the system rmpopt_capable.

Based on Dave's feedback, i am going to drop this cpu_hotplug_disable()/cpu_hotplug_enable()
and instead implementing and registering the CPU hotplug callback and then refusing to go offline
if SNP is enabled, unless anyone else here has a different thought/suggestion.

Thanks,
Ashish

---

## [26] Kalra, Ashish — 2026-06-19
*Subject: Re: [PATCH v8 3/7] crypto/ccp: Disable CPU hotplug while SNP is
 active*

On 6/19/2026 3:51 PM, Kalra, Ashish wrote:
> 
> On 6/18/2026 4:35 PM, Dave Hansen wrote:

After feedback from Tom, adding here that RMPOPT_BASE (RMPOPT_EN) can only be set if 
SNP and SegmentedRMP are enabled. 

Therefore, we can only call snp_setup_rmpopt() after snp_prepare() has enabled SNP in
__sev_snp_init_locked() (CCP module).

Additionally, as SNP_INIT, clears the RMPOPT table contents to 0, therefore we call it
after SNP_INIT_EX.
 
Thanks,
Ashish
 
> 
> Based on Dave's feedback, i am going to drop this cpu_hotplug_disable()/cpu_hotplug_enable()

---

## [27] Kalra, Ashish — 2026-06-19
*Subject: Re: [PATCH v8 7/7] x86/sev: Add debugfs support for RMPOPT*

On 6/18/2026 4:42 PM, Dave Hansen wrote:
> On 6/18/26 12:57, Kalra, Ashish wrote:
>> Maybe i can add a line to this patch's commit message stating it's a

I will drop this patch from the series and then revisit the debugging/
observability interface after this series gets merged.

Thanks,
Ashish

---

## [28] Borislav Petkov — 2026-06-19
*Subject: Re: [PATCH v8 3/7] crypto/ccp: Disable CPU hotplug while SNP is
 active*

On Fri, Jun 19, 2026 at 03:51:20PM -0500, Kalra, Ashish wrote:
> Based on Dave's feedback, i am going to drop this
> cpu_hotplug_disable()/cpu_hotplug_enable() and instead implementing and

What happened to using cpu_hotplug_disable_offlining() as I've been saying
a bunch of times now?

---

## [29] Kalra, Ashish — 2026-06-19
*Subject: Re: [PATCH v8 3/7] crypto/ccp: Disable CPU hotplug while SNP is
 active*

Hello Boris,

On 6/19/2026 5:10 PM, Borislav Petkov wrote:
> On Fri, Jun 19, 2026 at 03:51:20PM -0500, Kalra, Ashish wrote:
>> Based on Dave's feedback, i am going to drop this

One thing about cpu_hotplug_disable_offlining() is that it is permanent and one-way (__ro_after_init). 

Once SNP host RMP/SNP is enabled at boot, offlining is disabled for the entire boot — no re-enable, even if
SNP is fully shut down later. In comparison, there is the possibility to re-enable CPU hotplugging during
SNP shutdown path by calling cpuhp_remove_state_nocalls().

It has to invoked at boot-time, so it's tied to "RMP/SNP host enabled at boot". So on a host with SNP/RMP enabled
but where SNP firmware is never initialized (KVM/SEV never used), it would still permanently disable CPU offlining — 
which is arguably wrong, since SNP isn't in use there. 

It is otherwise a clean interface, the offline path returns -EOPNOTSUPP, distinct from an -EBUSY return
via the cpuhp interface.

To summarize, using cpu_hotplug_disable_offlining() is simpler than the cpuhp interface, but the 
trade-offs are (a) coarser granularity (SNP enabled vs SNP initialized) and (b) no re-enable.

Thanks,
Ashish

---

## [30] Borislav Petkov — 2026-06-19
*Subject: Re: [PATCH v8 3/7] crypto/ccp: Disable CPU hotplug while SNP is
 active*

On Fri, Jun 19, 2026 at 05:34:37PM -0500, Kalra, Ashish wrote:
> Once SNP host RMP/SNP is enabled at boot, offlining is disabled for the
> entire boot — no re-enable, even if SNP is fully shut down later. In

I'd let tglx maybe give a better idea but this cpu_hotplug_disable static var
in kernel/cpu.c could get a getter function and be used instead of you
reinventing the wheel in here.

---

## [31] Kalra, Ashish — 2026-06-19
*Subject: Re: [PATCH v8 3/7] crypto/ccp: Disable CPU hotplug while SNP is
 active*

On 6/19/2026 6:20 PM, Borislav Petkov wrote:
> I'd let tglx maybe give a better idea but this cpu_hotplug_disable static var
> in kernel/cpu.c could get a getter function and be used instead of you

I don't follow — I'm not reinventing anything here. Patch 3 will use the existing CPU-hotplug callback interface: cpuhp_setup_state()
with a down callback that returns -EBUSY to refuse the offline while SNP is active. That's the standard mechanism for conditionally
preventing a CPU offline, and it keeps no private "hotplug disabled" state of its own — so there's nothing here for a getter on
cpu_hotplug_disabled to replace.

I chose the cpuhp callback specifically over cpu_hotplug_disable_offlining(): the callback can be torn down with
cpuhp_remove_state() when SNP is fully shut down, which re-enables CPU offlining. cpu_hotplug_disable_offlining() sets
cpu_hotplug_offline_disabled, which is __ro_after_init and one-way — there's no interface to clear it, and adding one would mean
dropping the __ro_after_init marking and a new core "re-enable offlining" API. So that route can't re-enable offlining on SNP
shutdown without new core plumbing, whereas the cpuhp callback gives me that for free.

Happy to go whichever way you/tglx prefers — if there's a specific variable/getter you had in mind, please point me at it.

Thanks,
Ashish

---

## [32] Thomas Gleixner — 2026-06-21
*Subject: Re: [PATCH v8 3/7] crypto/ccp: Disable CPU hotplug while SNP is active*

On Fri, Jun 19 2026 at 18:51, Ashish Kalra wrote:
> On 6/19/2026 6:20 PM, Borislav Petkov wrote:
>> I'd let tglx maybe give a better idea but this cpu_hotplug_disable static var

That's not a standard mechanism. That's a hack as you have to start the
offlining operation in order to prevent something you already know.

The return code which prevents offlining is there for situations where
the subsystem/driver is momentarily in a state which cannot be
resolved.

That's a very different story than knowing that state at the point of
installing the callback already.

> I chose the cpuhp callback specifically over
> cpu_hotplug_disable_offlining(): the callback can be torn down with

That's exactly the wrong attitude. Hack around a core limitation in a
random driver by abusing the provided mechanism instead of sitting down
and doing the extra five lines of code which makes it entirely clear
what's going on.

When Boris asked me how to disable hotplug, I had the impression that
this is about permanently preventing it. So I pointed him to
cpu_hotplug_disable_offlining().

If I had known that it's about temporary prevention during runtime of
something, then I'd pointed him to cpu_hotplug_disable()/enable() which
is five lines farther down in cpu.c. It's not rocket science to find
them. The first AI chatbot I asked pointed me to it immediately.

cpu_hotplug_disable()/enable() is _the_ standard mechanism to prevent
hotplug operations temporarily. They return -EBUSY without invoking any
callback or changing any related state.

So what's exactly the new core plumbing you need?

Thanks,

        tglx

---

## [33] Kalra, Ashish — 2026-06-22
*Subject: Re: [PATCH v8 3/7] crypto/ccp: Disable CPU hotplug while SNP is
 active*

On 6/21/2026 5:44 AM, Thomas Gleixner wrote:
> On Fri, Jun 19 2026 at 18:51, Ashish Kalra wrote:
>> On 6/19/2026 6:20 PM, Borislav Petkov wrote:

Sure.

>> I chose the cpuhp callback specifically over
>> cpu_hotplug_disable_offlining(): the callback can be torn down with

This is the interface i have been using, in fact this current patch (v8) is based
on cpu_hotplug_disable()/enable(), but then this thread started from review feedback
on the v8 patch using cpu_hotplug_disable()/enable() that it looks like a hack — 
the concern being that cpu_hotplug_disable() reads as a temporary lock rather than a
way to enforce a basically-permanent system state.

That's what led me to look at cpu_hotplug_disable_offlining() and a cpuhp down-callback
as alternatives.

Your point that cpu_hotplug_disable()/enable() is the standard mechanism to prevent hotplug
operations temporarily settles it, and the disable/enable pair being reversible is exactly
what's wanted here: it's undone when SNP is fully shut down, so it isn't actually permanent
(unlike cpu_hotplug_disable_offlining(), which is one-way). So I'll stay with 
cpu_hotplug_disable()/enable() and drop the alternatives.

Thanks,
Ashish

> So what's exactly the new core plumbing you need?
>

---
