---
title: 'x86/cpufeatures: Add X86_FEATURE_RMPOPT feature flag'
date: 2026-06-24
last_reply: 2026-06-28
message_count: 19
participants: ['Ashish Kalra', 'K Prateek Nayak', 'Borislav Petkov']
---

## [1] Ashish Kalra — 2026-06-24

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

## [2] Ashish Kalra — 2026-06-24
*Subject: [PATCH v9 2/6] x86/sev: Initialize RMPOPT configuration MSRs*

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
index 989ca9f72ba3..f0ed6c62d86c 100644
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
+		snp_clear_rmpopt_capable();
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
index 594cfa19cbd4..0243989f229b 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -662,6 +662,8 @@ static inline void snp_leak_pages(u64 pfn, unsigned int pages)
 	__snp_leak_pages(pfn, pages, true);
 }
 int snp_prepare(void);
+void snp_setup_rmpopt(void);
+void snp_clear_rmpopt_capable(void);
 void snp_shutdown(void);
 #else
 static inline bool snp_probe_rmptable_info(void) { return false; }
@@ -680,6 +682,8 @@ static inline void snp_leak_pages(u64 pfn, unsigned int npages) {}
 static inline void kdump_sev_callback(void) { }
 static inline void snp_fixup_e820_tables(void) {}
 static inline int snp_prepare(void) { return -ENODEV; }
+static inline void snp_setup_rmpopt(void) {}
+static inline void snp_clear_rmpopt_capable(void) {}
 static inline void snp_shutdown(void) {}
 #endif
 
diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index 8bcdce98f6dc..dab6e1c290bc 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -124,6 +124,10 @@ static void *rmp_bookkeeping __ro_after_init;
 
 static u64 probed_rmp_base, probed_rmp_size;
 
+static cpumask_var_t rmpopt_cpumask;
+static phys_addr_t rmpopt_pa_start;
+static bool rmpopt_capable;
+
 static LIST_HEAD(snp_leaked_pages_list);
 static DEFINE_SPINLOCK(snp_leaked_pages_list_lock);
 
@@ -490,6 +494,11 @@ static bool __init setup_rmptable(void)
 	if (rmp_cfg & MSR_AMD64_SEG_RMP_ENABLED) {
 		if (!setup_segmented_rmptable())
 			return false;
+		/*
+		 * RMPOPT requires a segmented RMP, so indicate that the
+		 * system is capable of configuring and running RMPOPT.
+		 */
+		rmpopt_capable = true;
 	} else {
 		if (!setup_contiguous_rmptable())
 			return false;
@@ -555,6 +564,19 @@ int snp_prepare(void)
 }
 EXPORT_SYMBOL_FOR_MODULES(snp_prepare, "ccp");
 
+static void rmpopt_cleanup(void)
+{
+	int cpu;
+
+	scoped_guard(cpus_read_lock) {
+		for_each_cpu(cpu, rmpopt_cpumask)
+			wrmsrq_on_cpu(cpu, MSR_AMD64_RMPOPT_BASE, 0);
+	}
+
+	free_cpumask_var(rmpopt_cpumask);
+	rmpopt_pa_start = 0;
+}
+
 void snp_shutdown(void)
 {
 	u64 syscfg;
@@ -563,11 +585,59 @@ void snp_shutdown(void)
 	if (syscfg & MSR_AMD64_SYSCFG_SNP_EN)
 		return;
 
+	rmpopt_cleanup();
+
 	clear_rmp();
 	on_each_cpu(mfd_reconfigure, NULL, 1);
 }
 EXPORT_SYMBOL_FOR_MODULES(snp_shutdown, "ccp");
 
+void snp_clear_rmpopt_capable(void)
+{
+	rmpopt_capable = false;
+}
+
+void snp_setup_rmpopt(void)
+{
+	u64 rmpopt_base;
+	int cpu;
+
+	if (!cpu_feature_enabled(X86_FEATURE_RMPOPT) || !rmpopt_capable)
+		return;
+
+	if (!zalloc_cpumask_var(&rmpopt_cpumask, GFP_KERNEL)) {
+		pr_err("Failed to allocate RMPOPT cpumask\n");
+		return;
+	}
+
+	/*
+	 * The RMPOPT_BASE MSR is per-core, so only one thread per core needs
+	 * to set up the RMPOPT_BASE MSR.
+	 *
+	 * Note: only online primary threads are included.  If a core's
+	 * primary thread is offline, that core is not covered.  CPU hotplug
+	 * is not currently supported with SNP enabled.
+	 */
+	scoped_guard(cpus_read_lock) {
+		for_each_online_cpu(cpu)
+			if (topology_is_primary_thread(cpu))
+				cpumask_set_cpu(cpu, rmpopt_cpumask);
+
+		rmpopt_pa_start = ALIGN_DOWN(PFN_PHYS(min_low_pfn), SZ_1G);
+		rmpopt_base = rmpopt_pa_start | MSR_AMD64_RMPOPT_ENABLE;
+
+		/*
+		 * Per-CPU RMPOPT tables support at most 2 TB of addressable memory
+		 * for RMP optimizations. Initialize the per-CPU RMPOPT table base
+		 * to the starting physical address to enable RMP optimizations for
+		 * up to 2 TB of system RAM on all CPUs.
+		 */
+		for_each_cpu(cpu, rmpopt_cpumask)
+			wrmsrq_on_cpu(cpu, MSR_AMD64_RMPOPT_BASE, rmpopt_base);
+	}
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

## [3] Ashish Kalra — 2026-06-24
*Subject: [PATCH v9 3/6] x86/sev: Disable CPU hotplug while SNP is active*

From: Ashish Kalra <ashish.kalra@amd.com>

While SNP is active, every memory write is checked against the RMP to
protect the integrity of SEV-SNP guest memory.  By the SNP architecture
these checks cannot be disabled on a subset of CPUs: they are gated
per-core by SYSCFG[SNP_EN], which the SEV firmware requires to be set on
every present CPU before SNP initialization.  A CPU that does not have
SNP_EN set and was not initialized via SNP_INIT performs no RMP checks at
all, so there is no valid configuration with SNP active and any CPU exempt
from RMP checks.

The firmware determines which CPUs are present from the processor and the
BIOS/UEFI configuration (e.g. SMT disabled in the BIOS) and enumerates
them at SNP init; it is not aware of the OS bringing CPUs online or
offline afterwards.  A CPU brought online after SNP init was not
enumerated at SNP_INIT and does not have SNP_EN set, so writes from it are
not RMP-checked and could corrupt SEV-SNP guest memory, and there is no
way to keep work off such a CPU once it is online.  OS CPU hotplug can thus
diverge from the firmware's expectations and break SNP.  Disable CPU
hotplug while SNP is active.

Use cpu_hotplug_disable() at SNP init and cpu_hotplug_enable() only on the
full x86_snp_shutdown path; the legacy SNP_SHUTDOWN_EX path leaves SNP
active and must keep hotplug disabled.  A flag in built-in SNP code keeps
the disable balanced across the teardown paths, re-init and kexec, and
survives a ccp module reload.

This also keeps the CPU set stable for the asynchronous RMPOPT scan added
later in this series, and ensures cpus_read_lock() in the scan is
uncontended.

Suggested-by: Thomas Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/include/asm/sev.h   |  2 ++
 arch/x86/virt/svm/sev.c      | 30 ++++++++++++++++++++++++++++++
 drivers/crypto/ccp/sev-dev.c |  3 +++
 3 files changed, 35 insertions(+)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 0243989f229b..440c813fedde 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -664,6 +664,7 @@ static inline void snp_leak_pages(u64 pfn, unsigned int pages)
 int snp_prepare(void);
 void snp_setup_rmpopt(void);
 void snp_clear_rmpopt_capable(void);
+void snp_disable_cpu_hotplug(void);
 void snp_shutdown(void);
 #else
 static inline bool snp_probe_rmptable_info(void) { return false; }
@@ -684,6 +685,7 @@ static inline void snp_fixup_e820_tables(void) {}
 static inline int snp_prepare(void) { return -ENODEV; }
 static inline void snp_setup_rmpopt(void) {}
 static inline void snp_clear_rmpopt_capable(void) {}
+static inline void snp_disable_cpu_hotplug(void) {}
 static inline void snp_shutdown(void) {}
 #endif
 
diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index dab6e1c290bc..60984f76b4e9 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -133,6 +133,9 @@ static DEFINE_SPINLOCK(snp_leaked_pages_list_lock);
 
 static unsigned long snp_nr_leaked_pages;
 
+/* Set while SNP has CPU hotplug disabled (kernel-lifetime; survives ccp reload). */
+static bool snp_cpu_hotplug_disabled;
+
 #undef pr_fmt
 #define pr_fmt(fmt)	"SEV-SNP: " fmt
 
@@ -577,6 +580,22 @@ static void rmpopt_cleanup(void)
 	rmpopt_pa_start = 0;
 }
 
+/*
+ * Disable CPU hotplug while SNP is active. Applied once per SNP-active
+ * window and balanced by cpu_hotplug_enable() in snp_shutdown().
+ * The legacy SNP_SHUTDOWN_EX path leaves SNP enabled without re-enabling
+ * hotplug, so a re-init while SNP is still active must not stack the
+ * disable count.
+ */
+void snp_disable_cpu_hotplug(void)
+{
+	if (!snp_cpu_hotplug_disabled) {
+		cpu_hotplug_disable();
+		snp_cpu_hotplug_disabled = true;
+	}
+}
+EXPORT_SYMBOL_FOR_MODULES(snp_disable_cpu_hotplug, "ccp");
+
 void snp_shutdown(void)
 {
 	u64 syscfg;
@@ -587,6 +606,17 @@ void snp_shutdown(void)
 
 	rmpopt_cleanup();
 
+	/*
+	 * Re-enable CPU hotplug now that SNP is fully shut down.  Done here
+	 * (x86_snp_shutdown path) only -- the legacy path leaves SNP active
+	 * and must keep hotplug disabled.  After rmpopt_cleanup() so the
+	 * per-core RMPOPT_BASE MSRs are cleared with hotplug still disabled.
+	 */
+	if (snp_cpu_hotplug_disabled) {
+		cpu_hotplug_enable();
+		snp_cpu_hotplug_disabled = false;
+	}
+
 	clear_rmp();
 	on_each_cpu(mfd_reconfigure, NULL, 1);
 }
diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 217b6b19802e..66475145b3fa 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1479,6 +1479,9 @@ static int __sev_snp_init_locked(int *error, unsigned int max_snp_asid)
 
 	snp_hv_fixed_pages_state_update(sev, HV_FIXED);
 
+	/* Disable CPU hotplug while SNP is active (see snp_disable_cpu_hotplug). */
+	snp_disable_cpu_hotplug();
+
 	snp_setup_rmpopt();
 
 	sev->snp_initialized = true;

---

## [4] Ashish Kalra — 2026-06-24
*Subject: [PATCH v9 4/6] x86/sev: Add support to perform RMP optimizations asynchronously*

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
 arch/x86/virt/svm/sev.c | 165 +++++++++++++++++++++++++++++++++++++++-
 1 file changed, 162 insertions(+), 3 deletions(-)

diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index 60984f76b4e9..5f99cbbc6cbd 100644
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
 
 static cpumask_var_t rmpopt_cpumask;
-static phys_addr_t rmpopt_pa_start;
+static phys_addr_t rmpopt_pa_start, rmpopt_pa_end;
 static bool rmpopt_capable;
 
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
 
@@ -571,13 +583,22 @@ static void rmpopt_cleanup(void)
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
 	scoped_guard(cpus_read_lock) {
 		for_each_cpu(cpu, rmpopt_cpumask)
 			wrmsrq_on_cpu(cpu, MSR_AMD64_RMPOPT_BASE, 0);
 	}
 
 	free_cpumask_var(rmpopt_cpumask);
-	rmpopt_pa_start = 0;
+	rmpopt_pa_start = rmpopt_pa_end = 0;
+	rmpopt_wq = NULL;
 }
 
 /*
@@ -627,6 +648,101 @@ void snp_clear_rmpopt_capable(void)
 	rmpopt_capable = false;
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
+	 *
+	 * Pin the worker to the current CPU for the leader loop so that
+	 * this_cpu remains valid and the RMPOPT instruction executes on
+	 * the correct CPU.  Use migrate_disable() rather than get_cpu() to
+	 * prevent migration while still allowing preemption.
+	 */
+	migrate_disable();
+	this_cpu = smp_processor_id();
+
+	cpumask_andnot(follower_mask, rmpopt_cpumask,
+		       topology_sibling_cpumask(this_cpu));
+
+	for (pa = rmpopt_pa_start; pa < rmpopt_pa_end; pa += SZ_1G) {
+		rmpopt(pa);
+		cond_resched();
+	}
+	migrate_enable();
+
+	/*
+	 * Followers: run RMPOPT on remaining cores.  CPUs cannot go offline
+	 * while SNP is active, so the follower set stays valid across the
+	 * scan and cpus_read_lock() is uncontended.
+	 */
+	scoped_guard(cpus_read_lock) {
+		for (pa = rmpopt_pa_start; pa < rmpopt_pa_end; pa += SZ_1G) {
+			on_each_cpu_mask(follower_mask, rmpopt_smp,
+					 (void *)pa, true);
+
+			/* Give a chance for other threads to run */
+			cond_resched();
+		}
+	}
+
+	free_cpumask_var(follower_mask);
+}
+
 void snp_setup_rmpopt(void)
 {
 	u64 rmpopt_base;
@@ -635,14 +751,42 @@ void snp_setup_rmpopt(void)
 	if (!cpu_feature_enabled(X86_FEATURE_RMPOPT) || !rmpopt_capable)
 		return;
 
+	guard(mutex)(&rmpopt_wq_mutex);
+
+	/*
+	 * Guard against re-initialization.  When SNP_SHUTDOWN_EX is issued
+	 * with x86_snp_shutdown=0, snp_shutdown() is not called and
+	 * rmpopt_cleanup() is skipped, but snp_initialized is still cleared.
+	 * A subsequent __sev_snp_init_locked() would call snp_setup_rmpopt()
+	 * again, leaking the existing workqueue, delayed work, and cpumask
+	 * state.
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
 	if (!zalloc_cpumask_var(&rmpopt_cpumask, GFP_KERNEL)) {
 		pr_err("Failed to allocate RMPOPT cpumask\n");
+		destroy_workqueue(rmpopt_wq);
+		rmpopt_wq = NULL;
 		return;
 	}
 
 	/*
 	 * The RMPOPT_BASE MSR is per-core, so only one thread per core needs
-	 * to set up the RMPOPT_BASE MSR.
+	 * to set up the RMPOPT_BASE MSR. Likewise, only one thread per core
+	 * needs to issue the RMPOPT instruction.
 	 *
 	 * Note: only online primary threads are included.  If a core's
 	 * primary thread is offline, that core is not covered.  CPU hotplug
@@ -665,6 +809,21 @@ void snp_setup_rmpopt(void)
 		for_each_cpu(cpu, rmpopt_cpumask)
 			wrmsrq_on_cpu(cpu, MSR_AMD64_RMPOPT_BASE, rmpopt_base);
 	}
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

## [5] Ashish Kalra — 2026-06-24
*Subject: [PATCH v9 5/6] x86/sev: Add interface to re-enable RMP optimizations.*

From: Ashish Kalra <ashish.kalra@amd.com>

RMPOPT table is a per-CPU table which indicates if 1GB regions of
physical memory are entirely hypervisor-owned or not.

When performing host memory accesses in hypervisor mode as well as
non-SNP guest mode, the processor may consult the RMPOPT table to
potentially skip an RMP access and improve performance.

Normal guest events clear RMP optimizations: pages are converted from
shared to private as SNP guests are launched, and large pages are split
and collapsed during guest operation -- both clear the RMPOPT
optimizations for the affected 1GB regions.  Conversely, guest pages are
converted back to shared during SNP guest termination, so those regions
may become eligible for RMPOPT optimization again.

Without some intervention, all RMP optimizations would eventually be
lost.  Add an interface to re-optimize all of physical memory.

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
index 440c813fedde..d40beafbebb6 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -662,6 +662,7 @@ static inline void snp_leak_pages(u64 pfn, unsigned int pages)
 	__snp_leak_pages(pfn, pages, true);
 }
 int snp_prepare(void);
+void snp_rmpopt_all_physmem(void);
 void snp_setup_rmpopt(void);
 void snp_clear_rmpopt_capable(void);
 void snp_disable_cpu_hotplug(void);
@@ -683,6 +684,7 @@ static inline void snp_leak_pages(u64 pfn, unsigned int npages) {}
 static inline void kdump_sev_callback(void) { }
 static inline void snp_fixup_e820_tables(void) {}
 static inline int snp_prepare(void) { return -ENODEV; }
+static inline void snp_rmpopt_all_physmem(void) {}
 static inline void snp_setup_rmpopt(void) {}
 static inline void snp_clear_rmpopt_capable(void) {}
 static inline void snp_disable_cpu_hotplug(void) {}
diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index 5f99cbbc6cbd..4661e5271a2d 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -743,6 +743,21 @@ static void rmpopt_work_handler(struct work_struct *work)
 	free_cpumask_var(follower_mask);
 }
 
+void snp_rmpopt_all_physmem(void)
+{
+	if (!cpu_feature_enabled(X86_FEATURE_RMPOPT) || !rmpopt_capable)
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
+EXPORT_SYMBOL_FOR_MODULES(snp_rmpopt_all_physmem, "kvm-amd");
+
 void snp_setup_rmpopt(void)
 {
 	u64 rmpopt_base;

---

## [6] Ashish Kalra — 2026-06-24
*Subject: [PATCH v9 6/6] KVM: SEV: Perform RMP optimizations on SNP guest shutdown*

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
 arch/x86/kvm/svm/sev.c | 10 ++++++++++
 1 file changed, 10 insertions(+)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index e107f368ed2d..23e236b13ccd 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -3005,6 +3005,16 @@ void sev_vm_destroy(struct kvm *kvm)
 		 */
 		if (snp_decommission_context(kvm))
 			return;
+
+		/*
+		 * Perform RMP optimizations on memory freed by terminating
+		 * guests.  The scan is deferred, so it normally runs after
+		 * sev_gmem_invalidate() has converted this guest's pages back to
+		 * shared, and picks them up then.  A very large guest whose
+		 * conversion has not finished by then is picked up by a later
+		 * teardown's scan.
+		 */
+		snp_rmpopt_all_physmem();
 	} else {
 		sev_unbind_asid(kvm, sev->handle);
 	}

---

## [7] K Prateek Nayak — 2026-06-25
*Subject: Re: [PATCH v9 3/6] x86/sev: Disable CPU hotplug while SNP is active*

Hello Ashish,

On 6/25/2026 3:26 AM, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

If this is true ...

[..snip..]

> diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
> index 217b6b19802e..66475145b3fa 100644

... then this should be done at snp_prepare() before
on_each_cpu(snp_enable) right?

If not, then any CPU hotplug between the cpus_read_unlock() there and
the snp_disable_cpu_hotplug() here will not have the SNP_EN set.

Isn't that a concern?

Also, this patch can probably go first since the FW assumptions on
hotplug exists independent of RMPOPT bits.

> +
>  	snp_setup_rmpopt();

---

## [8] Kalra, Ashish — 2026-06-25
*Subject: Re: [PATCH v9 3/6] x86/sev: Disable CPU hotplug while SNP is active*

Hello Prateek,

On 6/24/2026 10:45 PM, K Prateek Nayak wrote:
> Hello Ashish,
> 

yes — it's a concern, and i agree the disable belongs in snp_prepare() before SNP_EN is programmed.

snp_enable runs via on_each_cpu() over the set that is online at snp_prepare() time, and SNP_INIT_EX runs
right after. With the disable where it is now (after SNP_INIT_EX/DF_FLUSH), there's a window starting at
snp_prepare()'s cpus_read_unlock() in which a CPU can come online that never had snp_enable run on it, i.e.
with SNP_EN clear. .

So hotplug needs to be frozen before SNP_EN is programmed, so the online set that gets SNP_EN cannot change underneath us.

I'll move the disable into snp_prepare(), before cpus_read_lock() rather than just before on_each_cpu(snp_enable):
cpu_hotplug_disable() takes cpu_add_remove_lock, which nests above cpu_hotplug_lock, so calling it under
cpus_read_lock() would invert the order, causing deadlock.

On the failure paths where SNP does not end up active, i.e., SNP_INIT_EX/DF_FLUSH error, then I'll
re-enable hotplug so a failed init doesn't leave it permanently disabled; the success path continues to re-enable
only on the full shutdown path.

Will fix in v10.

Thanks,
Ashish

> 
> Also, this patch can probably go first since the FW assumptions on

---

## [9] Borislav Petkov — 2026-06-25
*Subject: Re: [PATCH v9 3/6] x86/sev: Disable CPU hotplug while SNP is active*

On Wed, Jun 24, 2026 at 09:56:49PM +0000, Ashish Kalra wrote:
> +/* Set while SNP has CPU hotplug disabled (kernel-lifetime; survives ccp reload). */
> +static bool snp_cpu_hotplug_disabled;

Do you really need this?

---

## [10] Kalra, Ashish — 2026-06-25
*Subject: Re: [PATCH v9 3/6] x86/sev: Disable CPU hotplug while SNP is active*

Hello Boris,

On 6/25/2026 10:02 AM, Borislav Petkov wrote:
> On Wed, Jun 24, 2026 at 09:56:49PM +0000, Ashish Kalra wrote:
>> +/* Set while SNP has CPU hotplug disabled (kernel-lifetime; survives ccp reload). */

Yes.

cpu_hotplug_disable()/cpu_hotplug_enable() are refcounted (cpu_hotplug_disabled++/--,
with a WARN on underflow), so they have to be balanced. This flag collapses them to
exactly one outstanding disable per SNP-active window, because the disable and enable
sites are not reached a symmetric number of times:

  - On firmware without SNP_X86_SHUTDOWN_SUPPORTED, __sev_snp_shutdown_locked() does not
  call snp_shutdown() (it's gated on data.x86_snp_shutdown), so SNP stays enabled in
  hardware — SNP_EN stays set and hotplug stays disabled — while sev->snp_initialized is
  cleared. Re-init after that is routine, the SNP ioctls self-bracket init and shutdown
  (e.g. SNP_COMMIT, SNP_SET_CONFIG, SNP_VLEK_LOAD):

  if (!sev->snp_initialized)
          snp_move_to_init_state(...);   /* -> __sev_snp_init_locked -> snp_prepare() */
  ... SNP_CMD ...
  if (shutdown_required)
          __sev_snp_shutdown_locked(...);
  - So whenever SNP isn't already initialized (psp_init_on_probe off, or after a prior
  legacy shutdown), every such ioctl does init -> command -> legacy shutdown. Each init
  reaches snp_prepare() with SNP_EN already set, and the disable now sits at the top of
  snp_prepare(), so it fires on every cycle. Without this flag that keeps bumping
  cpu_hotplug_disabled while the legacy shutdown never re-enables — hotplug ends up stuck
  disabled. This flag makes all but the first disable a no-op.
 
  - Also, importantly, kvm-amd module reload on legacy firmware is the same pattern: 
  unload leaves SNP_EN set, reload re-inits.)

  - On the enable side it avoids an unbalanced cpu_hotplug_enable() when the teardown/failure
  paths run without an outstanding disable (e.g. shutdown of a never-fully-initialized SNP).

So it's not redundant with cpu_hotplug_disabled — it tracks whether the outstanding disable
belongs to this SNP-active window in this kernel, which keeps the single disable/enable
balanced across the asymmetric legacy-vs-full SNP teardown paths and re-init.

Thanks,
Ashish

---

## [11] K Prateek Nayak — 2026-06-26
*Subject: Re: [PATCH v9 3/6] x86/sev: Disable CPU hotplug while SNP is active*

Hello Ashish,

On 6/26/2026 1:12 AM, Kalra, Ashish wrote:
> Hello Boris,
> 

Looking at snp_prepare(), we have an early-bailout for

    rdmsrq(MSR_AMD64_SYSCFG, val);
    if (val & MSR_AMD64_SYSCFG_SNP_EN)
         return;

Does executing SHUTDOWN command lead to the firmware clearing SNP_EN in
SYSCFG on all CPUS?

If SNP_EN remains set (and Linux can't clear it since it is
"Write-1-only" bit), then a subsequent snp_prepare() will skip setting
SYSCFG if it sees SNP_EN on local CPU.

It can so happen that we enable hotlpug at shutdown, CPUs come online
without setting SNP_EN in SYSCFG, subsequent snp_prepare() runs on a CPU
where SNP_EN is still set and skips configuring it for the CPUs that
don't have it set, and we'll be in a pickle still.

The comment above that bailout saying "this can happen in case of kexec
boot" makes me believe that SNP_EN remains set until a full system
reset.

The only safe way to do this is to ensure all possible CPUs are online
during snp_prepare() and do snp_enable() regardless of whether local CPU
has SNP_EN or not.

Am I missing something?

> 
>   - On the enable side it avoids an unbalanced cpu_hotplug_enable() when the teardown/failure

---

## [12] Kalra, Ashish — 2026-06-25
*Subject: Re: [PATCH v9 3/6] x86/sev: Disable CPU hotplug while SNP is active*

On 6/25/2026 5:16 PM, K Prateek Nayak wrote:
> Hello Ashish,
> 

Yes, in case of X86_SNP_SHUTDOWN (available if firmware supports X86SnpShutdown feature)
SNP is disabled on all cores by clearing SYSCFG[SNPEn] bit.

If X86_SNP_SHUTDOWN is set to 1, the firmware clears the SYSCFG[SNPEn] bit in each core. 

But, in case of legacy SNP shutdown, SNP_EN bit is not cleared and so SNP remains enabled.

> 
> If SNP_EN remains set (and Linux can't clear it since it is

The piece that makes the early bailout safe is the disable this patch adds:
hotplug is disabled while SNP is active, so the online set can't change under an
active SNP. snp_prepare() already requires online == present, so at a successful
init every present CPU gets SNP_EN, and because hotplug is then disabled none
can leave or rejoin without it. So whenever the bailout is hit with SNP active,
every online CPU already has SNP_EN:

  - kexec: SNP_EN is already set on all CPUs by the previous kernel.
  - re-init while SNP is still active (e.g. after a legacy SNP_SHUTDOWN that
  leaves SNP_EN set): hotplug was disabled the whole time, so the online set is
  unchanged and all of them still have SNP_EN.

The only way a CPU can be online without SNP_EN is when SNP is not active --
i.e. after an SNP_INIT failure, where this patch re-enables hotplug. That is
deliberately the same as the behavior before this support existed (hotplug was
never disabled then), and it is benign: SNP_EN only gates RMP checks, the RMP
itself is initialized by SNP_INIT, so on a failed init the RMP is all-zeroes --
every entry is in the default HV-owned state, no page is assigned, no check ever blocks
and snp_initialized stays false, so no SNP guest can be created.
Nothing is enforced and nothing is protected.

So I've kept snp_prepare()'s existing bailout / snp_enable() behavior unchanged;
what this patch adds is disabling hotplug while SNP is active, which is what
actually closes the window (a CPU coming online without SNP_EN while SNP is
live). That window -- and the SNP_EN-stays-set-on-failure situation -- already
exist in today's code, this patch constrains the dangerous (active) case and
otherwise matches current behavior.

(On the v9 placement specifically: I'm moving the disable into snp_prepare()
ahead of SNP_EN in the next version; in v9 it sits after SNP_INIT, which leaves
the window you originally pointed out.)

Thanks,
Ashish

>>
>>   - On the enable side it avoids an unbalanced cpu_hotplug_enable() when the teardown/failure

---

## [13] K Prateek Nayak — 2026-06-26
*Subject: Re: [PATCH v9 3/6] x86/sev: Disable CPU hotplug while SNP is active*

Hello Ashish,

On 6/26/2026 8:08 AM, Kalra, Ashish wrote:
>> Looking at snp_prepare(), we have an early-bailout for
>>

Ah! That was the bit I was missing. Thanks a ton for clarifying.

> 
>>

How is this enforced? AFAICT, on_each_cpu(snp_enable) will only covers
the online CPUs and there could be CPUs that have been offlined before
that right?

> and because hotplug is then disabled none
> can leave or rejoin without it. So whenever the bailout is hit with SNP active,

There is a catch here: you can have offline CPUs during the previous boot
(say you have maxcpus=8 in your cmdline), and then you kexec with a different
kernel / cmdline that brings online a bunch more CPUs.

SNP_EN will only be set for a subset of then with the legacy SNP_INIT and
if snp_prepare() runs on those legacy CPUs, you still skip setting it for
the ones that don't have SNP_EN set.

Is that case covered somehow or is it a non-issue?

>   - re-init while SNP is still active (e.g. after a legacy SNP_SHUTDOWN that
>   leaves SNP_EN set): hotplug was disabled the whole time, so the online set is

Ack! Just that one small bit up above bothers me but other than that,
doing it in snp_prepare() should be good.

This is all new to me so thanks a ton for answering my queries.

> 
> (On the v9 placement specifically: I'm moving the disable into snp_prepare()

---

## [14] Borislav Petkov — 2026-06-26
*Subject: Re: [PATCH v9 3/6] x86/sev: Disable CPU hotplug while SNP is active*

On Thu, Jun 25, 2026 at 02:42:23PM -0500, Kalra, Ashish wrote:
> Hello Boris,

Hello Ashish,

lemme try to make sense of your AI reply...

> cpu_hotplug_disable()/cpu_hotplug_enable() are refcounted (cpu_hotplug_disabled++/--,
> with a WARN on underflow), so they have to be balanced. This flag collapses them to

Well, why aren't they?

Why isn't a simple design where on SNP init hotplug is disabled - *exactly*
one call to cpu_hotplug_disable() and on SNP shutdown hotplug is reenabled
again - also exactly one call.

I know why...

>   - On firmware without SNP_X86_SHUTDOWN_SUPPORTED, __sev_snp_shutdown_locked() does not

This function is one convoluted mess which does gazillion things. If I were
maintaining that code, I would impose a mandatory cleanup phase before new
features are added. But I probably said that already before...

And because a lot of code from your set goes into areas I maintain, I would
suggest you take the time and do that cleanup. Before that code goes
completely off the rails. And I'm willing to offer you review bandwidth and
other help I can with doing this right.

>   call snp_shutdown() (it's gated on data.x86_snp_shutdown), so SNP stays enabled in
>   hardware — SNP_EN stays set and hotplug stays disabled — while sev->snp_initialized is

That init and teardown flow should be simplified:

You have multiple things which you need to do at different times

- per-CPU init 
- global init 

- per-CPU teardown
- global teardown

CPU hotplug toggling belongs to the global category. Instead of piling more
stuff onto that __sev_snp_shutdown_locked() function, you should take some
time to clean it up, analyze what goes where and then simplify that flow.

So let's clean stuff up first, please, analyze the flow and determine what
goes where and then do it. Not bolt more stuff on what is already wobbly.

Thx.

---

## [15] Kalra, Ashish — 2026-06-26
*Subject: Re: [PATCH v9 3/6] x86/sev: Disable CPU hotplug while SNP is active*

Hello Prateek,

On 6/25/2026 11:01 PM, K Prateek Nayak wrote:
> Hello Ashish,
> 
Right that on_each_cpu() only covers online CPUs -- but snp_prepare() refuses to
proceed unless online == present. 

  if (!cpumask_equal(cpu_online_mask, cpu_present_mask)) {
          ret = -EOPNOTSUPP;
          pr_warn("SNP init failed: not all CPUs online. ...");
          goto unlock;
  }
  
The check right before on_each_cpu(snp_enable) returns -EOPNOTSUPP if any present CPU
is offline, so SNP init simply fails in that case -- there is no successful init
that leaves a CPU without SNP_EN. The check and on_each_cpu(snp_enable) both run
under cpus_read_lock(), so the online set can't change between the two, at a
successful snp_prepare(), online == present and every present CPU has SNP_EN.
After that this patch disables hotplug, so the set stays == present.

(That online == present requirement is existing snp_prepare() behavior, not
something this patch adds.)

And cpu_hotplug_disable() comes right before cpus_read_lock() as it must not be called
while holding cpus_read_lock(), something like this: 


        rdmsrq(MSR_AMD64_SYSCFG, val);
        if (val & MSR_AMD64_SYSCFG_SNP_EN)
                return 0;                 /* bailout: re-init/kexec, SNP_EN already set */

        clear_rmp();

        cpu_hotplug_disable();            /* <-- here: after bailout, before cpus_read_lock */

        cpus_read_lock();
        if (!cpumask_equal(cpu_online_mask, cpu_present_mask)) {
                ret = -EOPNOTSUPP;
                ...
                goto unlock;             /* will re-enable below */
        }
        on_each_cpu(mfd_reconfigure, ...);
        on_each_cpu(snp_enable, ...);
        ...
  unlock:
        cpus_read_unlock();
        if (ret)
                cpu_hotplug_enable();    /* undo: failed before SNP_EN was set */
        return ret;

> 
>> and because hotplug is then disabled none

It's a non-issue, for two independent reasons.

First, kexec with SNP active currently requires a full SNP shutdown before the
kexec. SNP_SHUTDOWN_EX (and the IOMMU SNP shutdown it performs) fail if there
are any active SNP guests or assigned ASIDs, so a working kexec has to terminate
all SNP guests and run a full shutdown first (via systemctl kexec). On
firmware that supports X86_SNP_SHUTDOWN, that full shutdown clears SNP_EN on all
CPUs, so the kexec target boots with SNP_EN clear and runs a complete, fresh
snp_prepare() -- where online == present is enforced, so every present CPU gets
SNP_EN. There is no inherited partial-SNP_EN state.

Second, even independent of kexec, this kernel's snp_prepare() never sets SNP_EN
on a subset: on_each_cpu(snp_enable) runs only after the
cpumask_equal(cpu_online_mask, cpu_present_mask) check passes, so it's all (every
present CPU) or nothing (snp_prepare() returns -EOPNOTSUPP and SNP_EN is never
set). With maxcpus=8 on a larger system, online != present, so SNP simply does
not initialize -- it cannot leave SNP_EN set on only those 8 cores. A successful
init therefore implies every present CPU has SNP_EN, and the present mask is the
same physical hardware across kexec.

So producing a partial SNP_EN set would require a source kernel that both sets
SNP_EN partially (i.e. doesn't enforce online == present) and skips the
full shutdown before kexec -- neither of which applies here. I think it's a
non-issue in practice.

>>   - re-init while SNP is still active (e.g. after a legacy SNP_SHUTDOWN that
>>   leaves SNP_EN set): hotplug was disabled the whole time, so the online set is

Thanks,
Ashish

>>
>> (On the v9 placement specifically: I'm moving the disable into snp_prepare()

---

## [16] Kalra, Ashish — 2026-06-26
*Subject: Re: [PATCH v9 3/6] x86/sev: Disable CPU hotplug while SNP is active*

Hello Boris,

On 6/26/2026 11:40 AM, Borislav Petkov wrote:
> On Thu, Jun 25, 2026 at 02:42:23PM -0500, Kalra, Ashish wrote:
>> Hello Boris,

It can be that simple, and flag-free, by following the SNP_EN state:

  - cpu_hotplug_disable() when SNP_EN is programmed: in snp_prepare(), before snp_enable().
  - cpu_hotplug_enable() when SNP_EN is cleared: in snp_shutdown(), after the firmware clears
  it on X86_SNP_SHUTDOWN.

SNP_EN is set only by snp_enable() in snp_prepare() (gated by online == present),
and only the firmware clears it. So:

  - snp_prepare() programs SNP_EN and disables hotplug on the same path; if it's
  called again while SNP_EN is already set (re-init), it bails before the
  disable.
  - snp_shutdown() runs only on the X86_SNP_SHUTDOWN path, after SNP_EN has been
  cleared, and enables hotplug. A legacy shutdown leaves SNP_EN set and does
  not call snp_shutdown(), so hotplug correctly stays disabled.

We also have to re-enable cpu hotplug on the init failure paths 
(snp_prepare()'s online != present check, and the SNP_INIT_EX / DF_FLUSH failures in 
__sev_snp_init_locked()), so a failed init leaves hotplug enabled, as it was before
this support.

The only extra case is a kexec target that boots with SNP_EN already set (legacy
firmware -- on X86_SNP_SHUTDOWN firmware the full shutdown required before kexec
clears SNP_EN, so the target re-inits normally). There snp_prepare() bails, so I
do the disable once at boot in snp_rmptable_init() when SNP_EN is already set.
That and the snp_prepare() disable can't both run -- SNP_EN is either already set
at boot, or it gets programmed by snp_prepare().

No (extra) flag needed.

Thanks,
Ashish

---

## [17] Borislav Petkov — 2026-06-26
*Subject: Re: [PATCH v9 3/6] x86/sev: Disable CPU hotplug while SNP is active*

On Fri, Jun 26, 2026 at 03:59:34PM -0500, Kalra, Ashish wrote:
> It can be that simple, and flag-free, by following the SNP_EN state:

Maybe. But that doesn't mean that you should not clean things up first where
needed. But I'll do a proper review once the dust from patchsets flying around
settles.

> We also have to re-enable cpu hotplug on the init failure paths 
> (snp_prepare()'s online != present check, and the SNP_INIT_EX / DF_FLUSH failures in 

You could also block hotplug for the time being by grabbing cpus_read_lock().
And only when you know you are all clear to disable hotplug, then you can do
that in the end and drop the hotplug lock.

> The only extra case is a kexec target that boots with SNP_EN already set (legacy
> firmware -- on X86_SNP_SHUTDOWN firmware the full shutdown required before kexec

Ok.

Thx.

---

## [18] K Prateek Nayak — 2026-06-29
*Subject: Re: [PATCH v9 3/6] x86/sev: Disable CPU hotplug while SNP is active*

Hello Boris,

On 6/27/2026 10:11 AM, Borislav Petkov wrote:
> You could also block hotplug for the time being by grabbing cpus_read_lock().
> And only when you know you are all clear to disable hotplug, then you can do

This is bad idea because it'll stall the tasks trying to do a hotplug
until the last SNP VM exits. Instead of simply getting an -EBUSY, the
users will start seeing a hung task splats in dmesg.

Also, since the last VM has to re-enable hotplug, you'll need a
up_read_non_owner() variant for cpus_read_unlock() to unlock the rwsem
from a different thread compared to the one that locks.

I think cpu_hotplug_disable() is the correct way to go forward but if
you are not a fan of the global "snp_cpu_hotplug_disabled" flag, maybe
it can be turned into an indicator like "snp_initialized" in
"struct sev_device". Thoughts?

---

## [19] Kalra, Ashish — 2026-06-28
*Subject: Re: [PATCH v9 3/6] x86/sev: Disable CPU hotplug while SNP is active*

On 6/28/2026 10:05 PM, K Prateek Nayak wrote:
> Hello Boris,
> 

As i mentioned in my previous reply, i have already removed the global
"snp_cpu_hotplug_disabled", the new implementation is flag-free, and
does hotplug disable/enable by following the SNP_EN state.

Thanks,
Ashish

---
