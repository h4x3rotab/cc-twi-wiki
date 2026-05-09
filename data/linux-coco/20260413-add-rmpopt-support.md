---
title: 'Add RMPOPT support.'
date: 2026-04-13
last_reply: 2026-05-05
message_count: 18
participants: ['Ashish Kalra', 'Ackerley Tng']
---

## [1] Ashish Kalra — 2026-04-13

From: Ashish Kalra <ashish.kalra@amd.com>

In the SEV-SNP architecture, hypervisor and non-SNP guests are subject
to RMP checks on writes to provide integrity of SEV-SNP guest memory.

The RMPOPT architecture enables optimizations whereby the RMP checks
can be skipped if 1GB regions of memory are known to not contain any
SNP guest memory.

RMPOPT is a new instruction designed to minimize the performance
overhead of RMP checks for the hypervisor and non-SNP guests.

RMPOPT instruction currently supports two functions. In case of the
verify and report status function the CPU will read the RMP contents,
verify the entire 1GB region starting at the provided SPA is HV-owned.
For the entire 1GB region it checks that all RMP entries in this region
are HV-owned (i.e, not in assigned state) and then accordingly updates
the RMPOPT table to indicate if optimization has been enabled and
provide indication to software if the optimization was successful.

In case of report status function, the CPU returns the optimization
status for the 1GB region.

The RMPOPT table is managed by a combination of software and hardware.
Software uses the RMPOPT instruction to set bits in the table,
indicating that regions of memory are entirely HV-owned.  Hardware
automatically clears bits in the RMPOPT table when RMP contents are
changed during RMPUPDATE instruction.

For more information on the RMPOPT instruction, see the AMD64 RMPOPT
technical documentation.

As SNP is enabled by default the hypervisor and non-SNP guests are
subject to RMP write checks to provide integrity of SNP guest memory.

This patch-series adds support to enable RMP optimizations for up to
2TB of system RAM across the system and allow RMPUPDATE to disable
those optimizations as SNP guests are launched.

Support for RAM larger than 2 TB will be added in follow-on series.

This series also introduces support to re-enable RMP optimizations
during SNP guest termination, after guest pages have been converted
back to shared.

RMP optimizations are performed asynchronously by queuing work on a
dedicated workqueue after a 10 second delay.

Delaying work allows batching of multiple SNP guest terminations.

Once 1GB hugetlb guest_memfd support is merged, support for
re-enabling RMPOPT optimizations during 1GB page cleanup will be added
in follow-on series.

Additionally add debugfs interface to report per-CPU RMPOPT status
across all system RAM.

v4:
- Add new wrmsrq_on_cpus() helper to write same u64 value to a
  per-CPU MSR across a cpumask without per-cpu struct allocation
  overhead. 
- Rename configure_and_enable_rmpopt() to snp_setup_rmpopt().
- Use wrmsrq_on_cpus() instead of wrmsrq_on_cpu() loop for
  programming RMPOPT_BASE MSRs.
- Add setup_clear_cpu_cap(X86_FEATURE_RMPOPT) if segmented RMP
  setup fails or workqueue allocation fails.
- Add X86_FEATURE_RMPOPT feature clear logic in amd_cc_platform_clear()
  for CC_ATTR_HOST_SEV_SNP.
- All of the above allow checking for only X86_FEATURE_RMPOPT for both
  RMPOPT setup/enable and RMP re-optimizations.
- Rename snp_perform_rmp_optimization() to snp_rmpopt_all_physmem().
- Split rmpopt() into rmpopt() and rmpopt_smp() for SMP callback use.
- Introduce separate rmpopt_report_cpumask for debugfs reporting,
  distinct from rmpopt_cpumask used for primary thread tracking.
- Remove snp_perform_rmp_optimization() call from __sev_snp_init_locked() 
  and instead setup and enable RMPOPT after SNP is enabled and 
  initialized.

v3:
- Drop all RMPOPT kthread support and introduce adding custom and
  dedicated workqueue to schedule delayed and asynchronous RMPOPT work.
- Drop the guest_memfd inode cleanup interface and add support to
  re-enable RMP optimizations during guest shutdown using the
  asynchronous and delayed workqueue interface.
- Introduce new __rmpopt() helper and rmpopt() and
  rmpopt_report_status() wrappers on top which use rax and rcx
  parameters to closely match RMPOPT specs.
- Use new optimized RMPOPT loop to issue RMPOPT instructions on all
  system RAM upto 2TB and all CPUs, by optimizing each range on one CPU
  first, then let other CPUs execute RMPOPT in parallel so they can skip
  most work as the range has already been optimized.
- Also add support for running the optimized RMPOPT loop only on
  one thread per core.
- Replace all PUD_SIZE references with SZ_1G to conform to 1GB regions
  as specified by RMPOPT specifications and not be dependent on PUD_SIZE
  which makes the RMPOPT patch-set independent of x86 page table sizes.
- Use wrmsrq_on_cpu() to program the RMPOPT_BASE MSR registers on
  all CPUs that removes all ugly casting to use on_each_cpu_mask().
- Fix inline commits and patch commit messages


v2:
- Drop all NUMA and Socket configuration and enablement support and
  enable RMPOPT support for up to 2TB of system RAM.
- Drop get_cpumask_of_primary_threads() and enable per-core RMPOPT
  base MSRs and issue RMPOPT instruction on all CPUs.
- Drop the configfs interface to manually re-enable RMP optimizations.
- Add new guest_memfd cleanup interface to automatically re-enable
  RMP optimizations during guest shutdown.
- Include references to the public RMPOPT documentation.
- Move debugfs directory for RMPOPT under architecuture specific
  parent directory.

Ashish Kalra (7):
  x86/cpufeatures: Add X86_FEATURE_AMD_RMPOPT feature flag
  x86/msr: add wrmsrq_on_cpus helper
  x86/sev: Initialize RMPOPT configuration MSRs
  x86/sev: Add support to perform RMP optimizations asynchronously
  x86/sev: Add interface to re-enable RMP optimizations.
  KVM: SEV: Perform RMP optimizations on SNP guest shutdown
  x86/sev: Add debugfs support for RMPOPT

 arch/x86/coco/core.c               |   1 +
 arch/x86/include/asm/cpufeatures.h |   2 +-
 arch/x86/include/asm/msr-index.h   |   3 +
 arch/x86/include/asm/msr.h         |   5 +
 arch/x86/include/asm/sev.h         |   4 +
 arch/x86/kernel/cpu/scattered.c    |   1 +
 arch/x86/kvm/svm/sev.c             |   2 +
 arch/x86/lib/msr-smp.c             |  20 +++
 arch/x86/virt/svm/sev.c            | 271 ++++++++++++++++++++++++++++-
 drivers/crypto/ccp/sev-dev.c       |   3 +
 10 files changed, 310 insertions(+), 2 deletions(-)

--
2.43.0

---

## [2] Ashish Kalra — 2026-04-13
*Subject: [PATCH v4 1/7] x86/cpufeatures: Add X86_FEATURE_AMD_RMPOPT feature flag*

From: Ashish Kalra <ashish.kalra@amd.com>

Add a flag indicating whether RMPOPT instruction is supported.

RMPOPT is a new instruction designed to minimize the performance
overhead of RMP checks on the hypervisor and on non-SNP guests by
allowing RMP checks to be skipped when 1G regions of memory are known
not to contain any SEV-SNP guest memory.

For more information on the RMPOPT instruction, see the AMD64 RMPOPT
technical documentation.

Reviewed-by: Dave Hansen <dave.hansen@linux.intel.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/include/asm/cpufeatures.h | 2 +-
 arch/x86/kernel/cpu/scattered.c    | 1 +
 2 files changed, 2 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/cpufeatures.h b/arch/x86/include/asm/cpufeatures.h
index dbe104df339b..bce1b2e2a35c 100644
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
index 42c7eac0c387..7ac3818c4502 100644
--- a/arch/x86/kernel/cpu/scattered.c
+++ b/arch/x86/kernel/cpu/scattered.c
@@ -65,6 +65,7 @@ static const struct cpuid_bit cpuid_bits[] = {
 	{ X86_FEATURE_PERFMON_V2,		CPUID_EAX,  0, 0x80000022, 0 },
 	{ X86_FEATURE_AMD_LBR_V2,		CPUID_EAX,  1, 0x80000022, 0 },
 	{ X86_FEATURE_AMD_LBR_PMC_FREEZE,	CPUID_EAX,  2, 0x80000022, 0 },
+	{ X86_FEATURE_RMPOPT,			CPUID_EDX,  0, 0x80000025, 0 },
 	{ X86_FEATURE_AMD_HTR_CORES,		CPUID_EAX, 30, 0x80000026, 0 },
 	{ 0, 0, 0, 0, 0 }
 };

---

## [3] Ashish Kalra — 2026-04-13
*Subject: [PATCH v4 2/7] x86/msr: add wrmsrq_on_cpus helper*

From: Ashish Kalra <ashish.kalra@amd.com>

The existing wrmsr_on_cpus() takes a per-cpu struct msr array, requiring
callers to allocate and populate per-cpu storage even when every CPU
receives the same value. This is unnecessary overhead for the common
case of writing a single uniform u64 to a per-CPU MSR across multiple
CPUs.

Add wrmsrq_on_cpus() which writes the same u64 value to the specified
MSR on all CPUs in the given cpumask.

Co-developed-by: Dave Hansen <dave.hansen@linux.intel.com>
Signed-off-by: Dave Hansen <dave.hansen@linux.intel.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/include/asm/msr.h |  5 +++++
 arch/x86/lib/msr-smp.c     | 20 ++++++++++++++++++++
 2 files changed, 25 insertions(+)

diff --git a/arch/x86/include/asm/msr.h b/arch/x86/include/asm/msr.h
index 9c2ea29e12a9..f5f63b4115c8 100644
--- a/arch/x86/include/asm/msr.h
+++ b/arch/x86/include/asm/msr.h
@@ -260,6 +260,7 @@ int rdmsr_on_cpu(unsigned int cpu, u32 msr_no, u32 *l, u32 *h);
 int wrmsr_on_cpu(unsigned int cpu, u32 msr_no, u32 l, u32 h);
 int rdmsrq_on_cpu(unsigned int cpu, u32 msr_no, u64 *q);
 int wrmsrq_on_cpu(unsigned int cpu, u32 msr_no, u64 q);
+void wrmsrq_on_cpus(const struct cpumask *mask, u32 msr_no, u64 q);
 void rdmsr_on_cpus(const struct cpumask *mask, u32 msr_no, struct msr __percpu *msrs);
 void wrmsr_on_cpus(const struct cpumask *mask, u32 msr_no, struct msr __percpu *msrs);
 int rdmsr_safe_on_cpu(unsigned int cpu, u32 msr_no, u32 *l, u32 *h);
@@ -289,6 +290,10 @@ static inline int wrmsrq_on_cpu(unsigned int cpu, u32 msr_no, u64 q)
 	wrmsrq(msr_no, q);
 	return 0;
 }
+static inline void wrmsrq_on_cpus(const struct cpumask *mask, u32 msr_no, u64 q)
+{
+	wrmsrq_on_cpu(0, msr_no, q);
+}
 static inline void rdmsr_on_cpus(const struct cpumask *m, u32 msr_no,
 				struct msr __percpu *msrs)
 {
diff --git a/arch/x86/lib/msr-smp.c b/arch/x86/lib/msr-smp.c
index b8f63419e6ae..d2c91c9bb47b 100644
--- a/arch/x86/lib/msr-smp.c
+++ b/arch/x86/lib/msr-smp.c
@@ -94,6 +94,26 @@ int wrmsrq_on_cpu(unsigned int cpu, u32 msr_no, u64 q)
 }
 EXPORT_SYMBOL(wrmsrq_on_cpu);
 
+void wrmsrq_on_cpus(const struct cpumask *mask, u32 msr_no, u64 q)
+{
+	struct msr_info rv;
+	int this_cpu;
+
+	memset(&rv, 0, sizeof(rv));
+
+	rv.msr_no = msr_no;
+	rv.reg.q = q;
+
+	this_cpu = get_cpu();
+
+	if (cpumask_test_cpu(this_cpu, mask))
+		__wrmsr_on_cpu(&rv);
+
+	smp_call_function_many(mask, __wrmsr_on_cpu, &rv, 1);
+	put_cpu();
+}
+EXPORT_SYMBOL(wrmsrq_on_cpus);
+
 static void __rwmsr_on_cpus(const struct cpumask *mask, u32 msr_no,
 			    struct msr __percpu *msrs,
 			    void (*msr_func) (void *info))

---

## [4] Ashish Kalra — 2026-04-13
*Subject: [PATCH v4 3/7] x86/sev: Initialize RMPOPT configuration MSRs*

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
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/coco/core.c             |  1 +
 arch/x86/include/asm/msr-index.h |  3 +++
 arch/x86/include/asm/sev.h       |  2 ++
 arch/x86/virt/svm/sev.c          | 41 +++++++++++++++++++++++++++++++-
 drivers/crypto/ccp/sev-dev.c     |  3 +++
 5 files changed, 49 insertions(+), 1 deletion(-)

diff --git a/arch/x86/coco/core.c b/arch/x86/coco/core.c
index 989ca9f72ba3..7fdef00ca8f2 100644
--- a/arch/x86/coco/core.c
+++ b/arch/x86/coco/core.c
@@ -172,6 +172,7 @@ static void amd_cc_platform_clear(enum cc_attr attr)
 	switch (attr) {
 	case CC_ATTR_HOST_SEV_SNP:
 		cc_flags.host_sev_snp = 0;
+		setup_clear_cpu_cap(X86_FEATURE_RMPOPT);
 		break;
 	default:
 		break;
diff --git a/arch/x86/include/asm/msr-index.h b/arch/x86/include/asm/msr-index.h
index be3e3cc963b2..9c8a6dfd7891 100644
--- a/arch/x86/include/asm/msr-index.h
+++ b/arch/x86/include/asm/msr-index.h
@@ -758,6 +758,9 @@
 #define MSR_AMD64_SEG_RMP_ENABLED_BIT	0
 #define MSR_AMD64_SEG_RMP_ENABLED	BIT_ULL(MSR_AMD64_SEG_RMP_ENABLED_BIT)
 #define MSR_AMD64_RMP_SEGMENT_SHIFT(x)	(((x) & GENMASK_ULL(13, 8)) >> 8)
+#define MSR_AMD64_RMPOPT_BASE		0xc0010139
+#define MSR_AMD64_RMPOPT_ENABLE_BIT	0
+#define MSR_AMD64_RMPOPT_ENABLE		BIT_ULL(MSR_AMD64_RMPOPT_ENABLE_BIT)
 
 #define MSR_SVSM_CAA			0xc001f000
 
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 09e605c85de4..409ab3372f7c 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -662,6 +662,7 @@ static inline void snp_leak_pages(u64 pfn, unsigned int pages)
 	__snp_leak_pages(pfn, pages, true);
 }
 void snp_prepare(void);
+void snp_setup_rmpopt(void);
 void snp_shutdown(void);
 #else
 static inline bool snp_probe_rmptable_info(void) { return false; }
@@ -680,6 +681,7 @@ static inline void snp_leak_pages(u64 pfn, unsigned int npages) {}
 static inline void kdump_sev_callback(void) { }
 static inline void snp_fixup_e820_tables(void) {}
 static inline void snp_prepare(void) {}
+static inline void snp_setup_rmpopt(void) {}
 static inline void snp_shutdown(void) {}
 #endif
 
diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index 41f76f15caa1..4f942abaf86e 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -124,6 +124,9 @@ static void *rmp_bookkeeping __ro_after_init;
 
 static u64 probed_rmp_base, probed_rmp_size;
 
+static cpumask_t rmpopt_cpumask;
+static phys_addr_t rmpopt_pa_start;
+
 static LIST_HEAD(snp_leaked_pages_list);
 static DEFINE_SPINLOCK(snp_leaked_pages_list_lock);
 
@@ -488,9 +491,12 @@ static bool __init setup_segmented_rmptable(void)
 static bool __init setup_rmptable(void)
 {
 	if (rmp_cfg & MSR_AMD64_SEG_RMP_ENABLED) {
-		if (!setup_segmented_rmptable())
+		if (!setup_segmented_rmptable()) {
+			setup_clear_cpu_cap(X86_FEATURE_RMPOPT);
 			return false;
+		}
 	} else {
+		setup_clear_cpu_cap(X86_FEATURE_RMPOPT);
 		if (!setup_contiguous_rmptable())
 			return false;
 	}
@@ -554,6 +560,39 @@ void snp_shutdown(void)
 }
 EXPORT_SYMBOL_FOR_MODULES(snp_shutdown, "ccp");
 
+void snp_setup_rmpopt(void)
+{
+	u64 rmpopt_base;
+	int cpu;
+
+	if (!cpu_feature_enabled(X86_FEATURE_RMPOPT))
+		return;
+
+	/*
+	 * RMPOPT_BASE MSR is per-core, so only one thread per core needs to
+	 * setup RMPOPT_BASE MSR.
+	 */
+
+	for_each_online_cpu(cpu) {
+		if (!topology_is_primary_thread(cpu))
+			continue;
+
+		cpumask_set_cpu(cpu, &rmpopt_cpumask);
+	}
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
+	wrmsrq_on_cpus(&rmpopt_cpumask, MSR_AMD64_RMPOPT_BASE, rmpopt_base);
+}
+EXPORT_SYMBOL_FOR_MODULES(snp_setup_rmpopt, "ccp");
+
 /*
  * Do the necessary preparations which are verified by the firmware as
  * described in the SNP_INIT_EX firmware command description in the SNP
diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 939fa8aa155c..901395ad7d51 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1476,6 +1476,9 @@ static int __sev_snp_init_locked(int *error, unsigned int max_snp_asid)
 	}
 
 	snp_hv_fixed_pages_state_update(sev, HV_FIXED);
+
+	snp_setup_rmpopt();
+
 	sev->snp_initialized = true;
 	dev_dbg(sev->dev, "SEV-SNP firmware initialized, SEV-TIO is %s\n",
 		data.tio_en ? "enabled" : "disabled");

---

## [5] Ashish Kalra — 2026-04-13
*Subject: [PATCH v4 4/7] x86/sev: Add support to perform RMP optimizations asynchronously*

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

Enable RMPOPT optimizations globally for all system RAM up to 2TB at
RMP initialization time. RMP checks can initially be skipped for 1GB
memory ranges that do not contain SEV-SNP guest memory (excluding
preassigned pages such as the RMP table and firmware pages). As SNP
guests are launched, RMPUPDATE will disable the corresponding RMPOPT
optimizations.

Suggested-by: Thomas Lendacky <thomas.lendacky@amd.com>
Suggested-by: Dave Hansen <dave.hansen@linux.intel.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/virt/svm/sev.c | 117 +++++++++++++++++++++++++++++++++++++++-
 1 file changed, 115 insertions(+), 2 deletions(-)

diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index 4f942abaf86e..56c9fc3fe53a 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -19,6 +19,7 @@
 #include <linux/iommu.h>
 #include <linux/amd-iommu.h>
 #include <linux/nospec.h>
+#include <linux/workqueue.h>
 
 #include <asm/sev.h>
 #include <asm/processor.h>
@@ -125,7 +126,17 @@ static void *rmp_bookkeeping __ro_after_init;
 static u64 probed_rmp_base, probed_rmp_size;
 
 static cpumask_t rmpopt_cpumask;
-static phys_addr_t rmpopt_pa_start;
+static phys_addr_t rmpopt_pa_start, rmpopt_pa_end;
+
+enum rmpopt_function {
+	RMPOPT_FUNC_VERIFY_AND_REPORT_STATUS,
+	RMPOPT_FUNC_REPORT_STATUS
+};
+
+#define RMPOPT_WORK_TIMEOUT	10000
+
+static struct workqueue_struct *rmpopt_wq;
+static struct delayed_work rmpopt_delayed_work;
 
 static LIST_HEAD(snp_leaked_pages_list);
 static DEFINE_SPINLOCK(snp_leaked_pages_list_lock);
@@ -560,6 +571,83 @@ void snp_shutdown(void)
 }
 EXPORT_SYMBOL_FOR_MODULES(snp_shutdown, "ccp");
 
+static inline bool __rmpopt(u64 rax, u64 rcx)
+{
+	bool optimized;
+
+	asm volatile(".byte 0xf2, 0x0f, 0x01, 0xfc"
+		     : "=@ccc" (optimized)
+		     : "a" (rax), "c" (rcx)
+		     : "memory", "cc");
+
+	return optimized;
+}
+
+/*
+ * 'val' is a system physical address.
+ */
+static void rmpopt_smp(void *val)
+{
+	u64 rax = ALIGN_DOWN((u64)val, SZ_1G);
+	u64 rcx = RMPOPT_FUNC_VERIFY_AND_REPORT_STATUS;
+
+	__rmpopt(rax, rcx);
+}
+
+static void rmpopt(u64 pa)
+{
+	u64 rax = ALIGN_DOWN(pa, SZ_1G);
+	u64 rcx = RMPOPT_FUNC_VERIFY_AND_REPORT_STATUS;
+
+	__rmpopt(rax, rcx);
+}
+
+/*
+ * RMPOPT optimizations skip RMP checks at 1GB granularity if this
+ * range of memory does not contain any SNP guest memory.
+ */
+static void rmpopt_work_handler(struct work_struct *work)
+{
+	bool current_cpu_cleared = false;
+	phys_addr_t pa;
+
+	pr_info("Attempt RMP optimizations on physical address range @1GB alignment [0x%016llx - 0x%016llx]\n",
+		rmpopt_pa_start, rmpopt_pa_end);
+
+	/*
+	 * RMPOPT scans the RMP table, stores the result of the scan in the
+	 * reserved processor memory. The RMP scan is the most expensive
+	 * part. If a second RMPOPT occurs, it can skip the expensive scan
+	 * if they can see a cached result in the reserved processor memory.
+	 *
+	 * Do RMPOPT on one CPU alone. Then, follow that up with RMPOPT
+	 * on every other primary thread. This potentially allows the
+	 * followers to use the "cached" scan results to avoid repeating
+	 * full scans.
+	 */
+
+	if (cpumask_test_cpu(smp_processor_id(), &rmpopt_cpumask)) {
+		cpumask_clear_cpu(smp_processor_id(), &rmpopt_cpumask);
+		current_cpu_cleared = true;
+	}
+
+	/* current CPU */
+	for (pa = rmpopt_pa_start; pa < rmpopt_pa_end; pa += SZ_1G)
+		rmpopt(pa);
+
+	for (pa = rmpopt_pa_start; pa < rmpopt_pa_end; pa += SZ_1G) {
+		on_each_cpu_mask(&rmpopt_cpumask, rmpopt_smp,
+				 (void *)pa, true);
+
+		 /* Give a chance for other threads to run */
+		cond_resched();
+
+	}
+
+	if (current_cpu_cleared)
+		cpumask_set_cpu(smp_processor_id(), &rmpopt_cpumask);
+}
+
 void snp_setup_rmpopt(void)
 {
 	u64 rmpopt_base;
@@ -568,9 +656,20 @@ void snp_setup_rmpopt(void)
 	if (!cpu_feature_enabled(X86_FEATURE_RMPOPT))
 		return;
 
+	/*
+	 * Create an RMPOPT-specific workqueue to avoid scheduling
+	 * RMPOPT workitem on the global system workqueue.
+	 */
+	rmpopt_wq = alloc_workqueue("rmpopt_wq", WQ_UNBOUND, 1);
+	if (!rmpopt_wq) {
+		setup_clear_cpu_cap(X86_FEATURE_RMPOPT);
+		return;
+	}
+
 	/*
 	 * RMPOPT_BASE MSR is per-core, so only one thread per core needs to
-	 * setup RMPOPT_BASE MSR.
+	 * setup RMPOPT_BASE MSR. Additionally only one thread per core needs
+	 * to issue the RMPOPT instruction.
 	 */
 
 	for_each_online_cpu(cpu) {
@@ -590,6 +689,20 @@ void snp_setup_rmpopt(void)
 	 * up to 2 TB of system RAM on all CPUs.
 	 */
 	wrmsrq_on_cpus(&rmpopt_cpumask, MSR_AMD64_RMPOPT_BASE, rmpopt_base);
+
+	INIT_DELAYED_WORK(&rmpopt_delayed_work, rmpopt_work_handler);
+
+	rmpopt_pa_end = ALIGN(PFN_PHYS(max_pfn), SZ_1G);
+
+	/* Limit memory scanning to the first 2 TB of RAM */
+	if ((rmpopt_pa_end - rmpopt_pa_start) > SZ_2T)
+		rmpopt_pa_end = rmpopt_pa_start + SZ_2T;
+
+	/*
+	 * Once all per-CPU RMPOPT tables have been configured, enable RMPOPT
+	 * optimizations on all physical memory.
+	 */
+	queue_delayed_work(rmpopt_wq, &rmpopt_delayed_work, 0);
 }
 EXPORT_SYMBOL_FOR_MODULES(snp_setup_rmpopt, "ccp");

---

## [6] Ashish Kalra — 2026-04-13
*Subject: [PATCH v4 5/7] x86/sev: Add interface to re-enable RMP optimizations.*

From: Ashish Kalra <ashish.kalra@amd.com>

RMPOPT table is a per-CPU table which indicates if 1GB regions of
physical memory are entirely hypervisor-owned or not.

When performing host memory accesses in hypervisor mode as well as
non-SNP guest mode, the processor may consult the RMPOPT table to
potentially skip an RMP access and improve performance.

Events such as RMPUPDATE can clear RMP optimizations. Add an interface
to re-enable those optimizations.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/include/asm/sev.h |  2 ++
 arch/x86/virt/svm/sev.c    | 10 ++++++++++
 2 files changed, 12 insertions(+)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 409ab3372f7c..dc9086057060 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -662,6 +662,7 @@ static inline void snp_leak_pages(u64 pfn, unsigned int pages)
 	__snp_leak_pages(pfn, pages, true);
 }
 void snp_prepare(void);
+void snp_rmpopt_all_physmem(void);
 void snp_setup_rmpopt(void);
 void snp_shutdown(void);
 #else
@@ -681,6 +682,7 @@ static inline void snp_leak_pages(u64 pfn, unsigned int npages) {}
 static inline void kdump_sev_callback(void) { }
 static inline void snp_fixup_e820_tables(void) {}
 static inline void snp_prepare(void) {}
+static inline void snp_rmpopt_all_physmem(void) {}
 static inline void snp_setup_rmpopt(void) {}
 static inline void snp_shutdown(void) {}
 #endif
diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index 56c9fc3fe53a..74ba8ec9de35 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -648,6 +648,16 @@ static void rmpopt_work_handler(struct work_struct *work)
 		cpumask_set_cpu(smp_processor_id(), &rmpopt_cpumask);
 }
 
+void snp_rmpopt_all_physmem(void)
+{
+	if (!cpu_feature_enabled(X86_FEATURE_RMPOPT))
+		return;
+
+	queue_delayed_work(rmpopt_wq, &rmpopt_delayed_work,
+			   msecs_to_jiffies(RMPOPT_WORK_TIMEOUT));
+}
+EXPORT_SYMBOL_GPL(snp_rmpopt_all_physmem);
+
 void snp_setup_rmpopt(void)
 {
 	u64 rmpopt_base;

---

## [7] Ashish Kalra — 2026-04-13
*Subject: [PATCH v4 6/7] KVM: SEV: Perform RMP optimizations on SNP guest shutdown*

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
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/kvm/svm/sev.c | 2 ++
 1 file changed, 2 insertions(+)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 3f9c1aa39a0a..e0f4f8ebef68 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2942,6 +2942,8 @@ void sev_vm_destroy(struct kvm *kvm)
 	if (sev_snp_guest(kvm)) {
 		snp_guest_req_cleanup(kvm);
 
+		snp_rmpopt_all_physmem();
+
 		/*
 		 * Decomission handles unbinding of the ASID. If it fails for
 		 * some unexpected reason, just leak the ASID.

---

## [8] Ashish Kalra — 2026-04-13
*Subject: [PATCH v4 7/7] x86/sev: Add debugfs support for RMPOPT*

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
 arch/x86/virt/svm/sev.c | 107 ++++++++++++++++++++++++++++++++++++++++
 1 file changed, 107 insertions(+)

diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index 74ba8ec9de35..dee2e853b4ad 100644
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
@@ -143,6 +145,13 @@ static DEFINE_SPINLOCK(snp_leaked_pages_list_lock);
 
 static unsigned long snp_nr_leaked_pages;
 
+static cpumask_t rmpopt_report_cpumask;
+static struct dentry *rmpopt_debugfs;
+
+struct seq_paddr {
+	phys_addr_t next_seq_paddr;
+};
+
 #undef pr_fmt
 #define pr_fmt(fmt)	"SEV-SNP: " fmt
 
@@ -580,6 +589,8 @@ static inline bool __rmpopt(u64 rax, u64 rcx)
 		     : "a" (rax), "c" (rcx)
 		     : "memory", "cc");
 
+	assign_cpu(smp_processor_id(), &rmpopt_report_cpumask, optimized);
+
 	return optimized;
 }
 
@@ -602,6 +613,100 @@ static void rmpopt(u64 pa)
 	__rmpopt(rax, rcx);
 }
 
+/*
+ * 'val' is a system physical address.
+ */
+static void rmpopt_report_status(void *val)
+{
+	u64 rax = ALIGN_DOWN((u64)val, SZ_1G);
+	u64 rcx = RMPOPT_FUNC_REPORT_STATUS;
+
+	__rmpopt(rax, rcx);
+}
+
+/*
+ * start() can be called multiple times if allocated buffer has overflowed
+ * and bigger buffer is allocated.
+ */
+static void *rmpopt_table_seq_start(struct seq_file *seq, loff_t *pos)
+{
+	phys_addr_t end_paddr = ALIGN(PFN_PHYS(max_pfn), SZ_1G);
+	struct seq_paddr *p = seq->private;
+
+	if (*pos == 0) {
+		p->next_seq_paddr = ALIGN_DOWN(PFN_PHYS(min_low_pfn), SZ_1G);
+		return &p->next_seq_paddr;
+	}
+
+	if (p->next_seq_paddr == end_paddr)
+		return NULL;
+
+	return &p->next_seq_paddr;
+}
+
+static void *rmpopt_table_seq_next(struct seq_file *seq, void *v, loff_t *pos)
+{
+	phys_addr_t end_paddr = ALIGN(PFN_PHYS(max_pfn), SZ_1G);
+	phys_addr_t *curr_paddr = v;
+
+	(*pos)++;
+	if (*curr_paddr == end_paddr)
+		return NULL;
+	*curr_paddr += SZ_1G;
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
+	seq_printf(seq, "Memory @%3lluGB: ",
+		   *curr_paddr >> (get_order(SZ_1G) + PAGE_SHIFT));
+
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
+	debugfs_create_file("rmpopt-table", 0444, rmpopt_debugfs,
+			    NULL, &rmpopt_table_fops);
+}
+
 /*
  * RMPOPT optimizations skip RMP checks at 1GB granularity if this
  * range of memory does not contain any SNP guest memory.
@@ -713,6 +818,8 @@ void snp_setup_rmpopt(void)
 	 * optimizations on all physical memory.
 	 */
 	queue_delayed_work(rmpopt_wq, &rmpopt_delayed_work, 0);
+
+	rmpopt_debugfs_setup();
 }
 EXPORT_SYMBOL_FOR_MODULES(snp_setup_rmpopt, "ccp");

---

## [9] Kalra, Ashish — 2026-04-29
*Subject: Re: [PATCH v4 0/7] Add RMPOPT support.*

Hello Dave, Sean,

Looking forward to your feedback, comments, thoughts on RMPOPT v4 patch series.

Thanks,
Ashish

On 4/13/2026 2:42 PM, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
>

---

## [10] Ackerley Tng — 2026-05-01
*Subject: Re: [PATCH v4 1/7] x86/cpufeatures: Add X86_FEATURE_AMD_RMPOPT
 feature flag*

Ashish Kalra <Ashish.Kalra@amd.com> writes:

>
> [...snip...]

Reviewed-by: Ackerley Tng <ackerleytng@google.com>

---

## [11] Ackerley Tng — 2026-05-01
*Subject: Re: [PATCH v4 3/7] x86/sev: Initialize RMPOPT configuration MSRs*

Ashish Kalra <Ashish.Kalra@amd.com> writes:

>
> [...snip...]

Dave mentioned hotplug in v3 [1], which led me to check. From this
series, it looks like RMPOPT won't ever be performed for newly-plugged
cpus, is that okay?

> +		if (!topology_is_primary_thread(cpu))
> +			continue;

nit: perhaps flipping the condition is easier to read:

    if (topology_is_primary_thread(cpu))
    	cpumask_set_cpu()

> +	}
> +

[1] https://lore.kernel.org/all/ab41b1d8-e464-4ad6-ac07-7318686db10e@intel.com/

>
> [...snip...]

---

## [12] Ackerley Tng — 2026-05-01
*Subject: Re: [PATCH v4 2/7] x86/msr: add wrmsrq_on_cpus helper*

Ashish Kalra <Ashish.Kalra@amd.com> writes:

>
> [...snip...]

I think

  on_each_cpu_mask(mask, __wrmsr_on_cpu, (void *)&rv, true);

is more readable than get and put cpu.

I understand Dave wanted to remove the ugly casting earlier, but perhaps
it's okay now that the cast is wrapped in a function like this?

Just my 2c, feel free to go ahead either way.

Reviewed-by: Ackerley Tng <ackerleytng@google.com>

>
> [...snip...]

---

## [13] Ackerley Tng — 2026-05-01
*Subject: Re: [PATCH v4 4/7] x86/sev: Add support to perform RMP optimizations asynchronously*

Ashish Kalra <Ashish.Kalra@amd.com> writes:

>
> [...snip...]

Could rmpopt_smp() call rmpopt() to remove duplicate code?

> +/*
> + * RMPOPT optimizations skip RMP checks at 1GB granularity if this

Out of curiosity, how does this caching work? Is it possible to do it
once and then synchronize the cache to the other CPUs?

> +	 */
> +

Sashiko [1] pointed this out: after cond_resched(), this code might be
on a different cpu so smp_processor_id() would return a different cpu,
that would mess up the global cpumask.

Perhaps it's better to store the id on a stack? Or actually, what if we
give on_each_cpu_mask a copy of rmpopt_cpumask with the current cpu
unset?

[1] https://sashiko.dev/#/patchset/cover.1775874970.git.ashish.kalra%40amd.com

> +}
> +

I think this is better phrased as "limit memory scanning to 2TB",

> +	if ((rmpopt_pa_end - rmpopt_pa_start) > SZ_2T)
> +		rmpopt_pa_end = rmpopt_pa_start + SZ_2T;

and then this could be

    rmpopt_pa_end = min(rmpopt_pa_end, rmpopt_pa_start + SZ_2T);

> +
> +	/*

Reviewed-by: Ackerley Tng <ackerleytng@google.com>

---

## [14] Ackerley Tng — 2026-05-01
*Subject: Re: [PATCH v4 5/7] x86/sev: Add interface to re-enable RMP optimizations.*

Ashish Kalra <Ashish.Kalra@amd.com> writes:

>
> [...snip...]

Reviewed-by: Ackerley Tng <ackerleytng@google.com>

---

## [15] Ackerley Tng — 2026-05-01
*Subject: Re: [PATCH v4 6/7] KVM: SEV: Perform RMP optimizations on SNP guest shutdown*

Ashish Kalra <Ashish.Kalra@amd.com> writes:

>
> [...snip...]

I see this is what you suggested in [1]. The time-based batching you
suggeested works because adding to the workqueue when there's already a
job just does nothing. Thanks!

I think optimizing when the VM is destroyed makes sense, in most cases
for SNP VMs, we don't expect large 1G blocks of memory to be shared
anyway, so even if we try to RMPOPT on every conversion to private, most
of those tries would be optimizing nothing.

I guess the remaining optimization would be to update based on only the
range of pfns where guest_memfd has private memory, but that could be
done in another patch series.

Reviewed-by: Ackerley Tng <ackerleytng@google.com>

[1] https://lore.kernel.org/all/31040bb7-653a-40f9-8899-40bc852f7e1f@amd.com/

>  		/*
>  		 * Decomission handles unbinding of the ASID. If it fails for

---

## [16] Kalra, Ashish — 2026-05-05
*Subject: Re: [PATCH v4 3/7] x86/sev: Initialize RMPOPT configuration MSRs*

Hello Ackerley,

On 5/1/2026 1:12 PM, Ackerley Tng wrote:
> Ashish Kalra <Ashish.Kalra@amd.com> writes:
> 

Yes, with this current series, RMPOPT won't be performed on newly-plugged
CPUs, i was computing and storing the cpumask for threads to fire RMPOPT on,
statically during the setup code to save computing it again on the
worker thread, but i believe the simple fix for handling hotplugged CPUs
would be to compute the cpumask every time the worker thread executes.

> 
>> +		if (!topology_is_primary_thread(cpu))

Yes.

> 
>     if (topology_is_primary_thread(cpu))

---

## [17] Kalra, Ashish — 2026-05-05
*Subject: Re: [PATCH v4 4/7] x86/sev: Add support to perform RMP optimizations
 asynchronously*

Hello Ackerley,

On 5/1/2026 1:57 PM, Ackerley Tng wrote:
> Ashish Kalra <Ashish.Kalra@amd.com> writes:
> 

Yes. 

> 
>> +/*

The first CPU does the full RMP scan and stores the result of the scan in reserved processor memory.
And other CPUs can skip the scan if they can see a cached result in the reserved processor memory.
So i believe the other CPUs would *still* have to issue the RMPOPT instruction, but then they will 
avoid the full RMP scan and use the cached results.

> 
>> +	 */

Yes, i think it makes sense to store the id on the stack.

Additionally, i will be moving the computing of the cpumask within this workitem,
so cpumask won't be global.
 
>> +}
>> +

Ok.

>> +	if ((rmpopt_pa_end - rmpopt_pa_start) > SZ_2T)
>> +		rmpopt_pa_end = rmpopt_pa_start + SZ_2T;

Yes.

Thanks,
Ashish

>> +
>> +	/*

---

## [18] Kalra, Ashish — 2026-05-05
*Subject: Re: [PATCH v4 6/7] KVM: SEV: Perform RMP optimizations on SNP guest
 shutdown*

Hello Ackerley,

On 5/1/2026 2:12 PM, Ackerley Tng wrote:
> Ashish Kalra <Ashish.Kalra@amd.com> writes:
> 

Yes.

Thanks,
Ashish

> I guess the remaining optimization would be to update based on only the
> range of pfns where guest_memfd has private memory, but that could be

---
