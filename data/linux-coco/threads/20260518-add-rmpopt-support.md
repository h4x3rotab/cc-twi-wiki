---
title: 'Add RMPOPT support.'
date: 2026-05-18
last_reply: 2026-05-27
message_count: 15
participants: ['Ashish Kalra', 'Dave Hansen', 'Borislav Petkov']
---

## [1] Ashish Kalra — 2026-05-18

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

v5:
- Introduce rmpopt_cleanup() to tear down workqueue, debugfs, cpumask,
  and MSR state, called from snp_shutdown().
- Introduce rmpopt_wq_mutex to serialize snp_setup_rmpopt(),
  snp_rmpopt_all_physmem(), and rmpopt_cleanup().
- Introduce rmpopt_show_mutex to serialize debugfs reporting of
  rmpopt_report_cpumask.
- Move snp_rmpopt_all_physmem() call after SNP DECOMMISSION during
  guest shutdown.
- Use migrate_disable()/migrate_enable() for CPU pinning in the
  rmpopt_work_handler() leader loop to maintain CPU affinity without
  disabling preemption for the entire RMPOPT scan.
- Add cpus_read_lock()/cpus_read_unlock() around the follower
  on_each_cpu_mask() loop in rmpopt_work_handler().
- Guard snp_setup_rmpopt() against re-initialization when
  SNP_SHUTDOWN_EX with x86_snp_shutdown=0 skips rmpopt_cleanup()
  but clears snp_initialized, preventing workqueue and resource
  leaks on repeated init/shutdown cycles.
- Replace setup_clear_cpu_cap() with pr_err() on alloc_workqueue()
  failure in snp_setup_rmpopt(), as setup_clear_cpu_cap() cannot be
  used after alternatives are patched; callers check rmpopt_wq != NULL
  as the runtime guard instead.
- Add pr_info() when RMPOPT coverage is capped at 2TB.
- Add comments noting CPU hotplug is not supported with SNP enabled
  and only online primary threads are covered by rmpopt_cpumask.
- Add comment in setup_rmptable() noting Segmented RMP must be
  enabled to enable RMPOPT.
- Simplify cpumask setup loop to set if primary thread rather than
  skip if not primary.
- Improve grammar and clarity in snp_setup_rmpopt() comments.
- Added Reviewed-by's.

  Sashiko AI code review identified several of the above issues.

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
 arch/x86/lib/msr-smp.c             |  20 ++
 arch/x86/virt/svm/sev.c            | 356 ++++++++++++++++++++++++++++-
 drivers/crypto/ccp/sev-dev.c       |   3 +
 10 files changed, 395 insertions(+), 2 deletions(-)

---

## [2] Ashish Kalra — 2026-05-18
*Subject: [PATCH v5 1/7] x86/cpufeatures: Add X86_FEATURE_AMD_RMPOPT feature flag*

From: Ashish Kalra <ashish.kalra@amd.com>

Add a flag indicating whether RMPOPT instruction is supported.

RMPOPT is a new instruction designed to minimize the performance
overhead of RMP checks on the hypervisor and on non-SNP guests by
allowing RMP checks to be skipped when 1G regions of memory are known
not to contain any SEV-SNP guest memory.

For more information on the RMPOPT instruction, see the AMD64 RMPOPT
technical documentation.

Reviewed-by: Dave Hansen <dave.hansen@linux.intel.com>
Reviewed-by: Ackerley Tng <ackerleytng@google.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/include/asm/cpufeatures.h | 2 +-
 arch/x86/kernel/cpu/scattered.c    | 1 +
 2 files changed, 2 insertions(+), 1 deletion(-)

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

---

## [3] Ashish Kalra — 2026-05-18
*Subject: [PATCH v5 2/7] x86/msr: add wrmsrq_on_cpus helper*

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
Reviewed-by: Ackerley Tng <ackerleytng@google.com>
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

## [4] Ashish Kalra — 2026-05-18
*Subject: [PATCH v5 3/7] x86/sev: Initialize RMPOPT configuration MSRs*

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
 arch/x86/coco/core.c             |  1 +
 arch/x86/include/asm/msr-index.h |  3 ++
 arch/x86/include/asm/sev.h       |  2 ++
 arch/x86/virt/svm/sev.c          | 59 +++++++++++++++++++++++++++++++-
 drivers/crypto/ccp/sev-dev.c     |  3 ++
 5 files changed, 67 insertions(+), 1 deletion(-)

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
index 594cfa19cbd4..6fd72a44a51e 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -662,6 +662,7 @@ static inline void snp_leak_pages(u64 pfn, unsigned int pages)
 	__snp_leak_pages(pfn, pages, true);
 }
 int snp_prepare(void);
+void snp_setup_rmpopt(void);
 void snp_shutdown(void);
 #else
 static inline bool snp_probe_rmptable_info(void) { return false; }
@@ -680,6 +681,7 @@ static inline void snp_leak_pages(u64 pfn, unsigned int npages) {}
 static inline void kdump_sev_callback(void) { }
 static inline void snp_fixup_e820_tables(void) {}
 static inline int snp_prepare(void) { return -ENODEV; }
+static inline void snp_setup_rmpopt(void) {}
 static inline void snp_shutdown(void) {}
 #endif
 
diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index 8bcdce98f6dc..82f9dc7a57c3 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -124,6 +124,9 @@ static void *rmp_bookkeeping __ro_after_init;
 
 static u64 probed_rmp_base, probed_rmp_size;
 
+static cpumask_t rmpopt_cpumask;
+static phys_addr_t rmpopt_pa_start;
+
 static LIST_HEAD(snp_leaked_pages_list);
 static DEFINE_SPINLOCK(snp_leaked_pages_list_lock);
 
@@ -488,9 +491,13 @@ static bool __init setup_segmented_rmptable(void)
 static bool __init setup_rmptable(void)
 {
 	if (rmp_cfg & MSR_AMD64_SEG_RMP_ENABLED) {
-		if (!setup_segmented_rmptable())
+		if (!setup_segmented_rmptable()) {
+			setup_clear_cpu_cap(X86_FEATURE_RMPOPT);
 			return false;
+		}
 	} else {
+		/* Note that Segmented RMP must be enabled to enable RMPOPT. */
+		setup_clear_cpu_cap(X86_FEATURE_RMPOPT);
 		if (!setup_contiguous_rmptable())
 			return false;
 	}
@@ -555,6 +562,16 @@ int snp_prepare(void)
 }
 EXPORT_SYMBOL_FOR_MODULES(snp_prepare, "ccp");
 
+static void rmpopt_cleanup(void)
+{
+	cpus_read_lock();
+	wrmsrq_on_cpus(&rmpopt_cpumask, MSR_AMD64_RMPOPT_BASE, 0);
+	cpus_read_unlock();
+
+	cpumask_clear(&rmpopt_cpumask);
+	rmpopt_pa_start = 0;
+}
+
 void snp_shutdown(void)
 {
 	u64 syscfg;
@@ -563,11 +580,51 @@ void snp_shutdown(void)
 	if (syscfg & MSR_AMD64_SYSCFG_SNP_EN)
 		return;
 
+	rmpopt_cleanup();
+
 	clear_rmp();
 	on_each_cpu(mfd_reconfigure, NULL, 1);
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
+	wrmsrq_on_cpus(&rmpopt_cpumask, MSR_AMD64_RMPOPT_BASE, rmpopt_base);
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

## [5] Ashish Kalra — 2026-05-18
*Subject: [PATCH v5 4/7] x86/sev: Add support to perform RMP optimizations asynchronously*

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
Reviewed-by: Ackerley Tng <ackerleytng@google.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/virt/svm/sev.c | 167 +++++++++++++++++++++++++++++++++++++++-
 1 file changed, 164 insertions(+), 3 deletions(-)

diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index 82f9dc7a57c3..8876cac052d5 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -19,6 +19,7 @@
 #include <linux/iommu.h>
 #include <linux/amd-iommu.h>
 #include <linux/nospec.h>
+#include <linux/workqueue.h>
 
 #include <asm/sev.h>
 #include <asm/processor.h>
@@ -125,7 +126,18 @@ static void *rmp_bookkeeping __ro_after_init;
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
+static DEFINE_MUTEX(rmpopt_wq_mutex);
 
 static LIST_HEAD(snp_leaked_pages_list);
 static DEFINE_SPINLOCK(snp_leaked_pages_list_lock);
@@ -564,12 +576,21 @@ EXPORT_SYMBOL_FOR_MODULES(snp_prepare, "ccp");
 
 static void rmpopt_cleanup(void)
 {
+	guard(mutex)(&rmpopt_wq_mutex);
+
+	if (!rmpopt_wq)
+		return;
+
+	cancel_delayed_work_sync(&rmpopt_delayed_work);
+	destroy_workqueue(rmpopt_wq);
+
 	cpus_read_lock();
 	wrmsrq_on_cpus(&rmpopt_cpumask, MSR_AMD64_RMPOPT_BASE, 0);
 	cpus_read_unlock();
 
 	cpumask_clear(&rmpopt_cpumask);
-	rmpopt_pa_start = 0;
+	rmpopt_pa_start = rmpopt_pa_end = 0;
+	rmpopt_wq = NULL;
 }
 
 void snp_shutdown(void)
@@ -587,6 +608,105 @@ void snp_shutdown(void)
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
+static void rmpopt(u64 pa)
+{
+	u64 rax = ALIGN_DOWN(pa, SZ_1G);
+	u64 rcx = RMPOPT_FUNC_VERIFY_AND_REPORT_STATUS;
+
+	__rmpopt(rax, rcx);
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
+	bool current_cpu_cleared = false;
+	phys_addr_t pa;
+	int this_cpu;
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
+	/*
+	 * Pin the worker to the current CPU for the leader loop so that
+	 * this_cpu remains valid and the RMPOPT instruction executes on
+	 * the CPU that was cleared from the cpumask.  The workqueue is
+	 * WQ_UNBOUND, so without pinning, the scheduler could migrate
+	 * the worker between the cpumask manipulation and the leader
+	 * loop, causing the leader to run on a different CPU while
+	 * this_cpu's core is skipped entirely.
+	 *
+	 * Use migrate_disable() rather than get_cpu() to prevent
+	 * migration while still allowing preemption.
+	 *
+	 * Note: rmpopt_cpumask is modified here without holding
+	 * rmpopt_wq_mutex.  This is safe because the delayed_work
+	 * mechanism guarantees single-threaded execution of this
+	 * handler, and rmpopt_cleanup() calls cancel_delayed_work_sync()
+	 * to ensure handler completion before tearing down the cpumask.
+	 */
+	migrate_disable();
+	this_cpu = smp_processor_id();
+	if (cpumask_test_cpu(this_cpu, &rmpopt_cpumask)) {
+		cpumask_clear_cpu(this_cpu, &rmpopt_cpumask);
+		current_cpu_cleared = true;
+	}
+
+	/* Leader: prime the RMPOPT cache on this CPU */
+	for (pa = rmpopt_pa_start; pa < rmpopt_pa_end; pa += SZ_1G)
+		rmpopt(pa);
+
+	migrate_enable();
+
+	/* Followers: run RMPOPT on all other cores */
+	cpus_read_lock();
+	for (pa = rmpopt_pa_start; pa < rmpopt_pa_end; pa += SZ_1G) {
+		on_each_cpu_mask(&rmpopt_cpumask, rmpopt_smp,
+				 (void *)pa, true);
+
+		 /* Give a chance for other threads to run */
+		cond_resched();
+	}
+	cpus_read_unlock();
+
+	if (current_cpu_cleared)
+		cpumask_set_cpu(this_cpu, &rmpopt_cpumask);
+}
+
 void snp_setup_rmpopt(void)
 {
 	u64 rmpopt_base;
@@ -595,11 +715,35 @@ void snp_setup_rmpopt(void)
 	if (!cpu_feature_enabled(X86_FEATURE_RMPOPT))
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
 	cpus_read_lock();
 
 	/*
 	 * The RMPOPT_BASE MSR is per-core, so only one thread per core needs
-	 * to set up the RMPOPT_BASE MSR.
+	 * to set up the RMPOPT_BASE MSR. Likewise, only one thread per core
+	 * needs to issue the RMPOPT instruction.
 	 *
 	 * Note: only online primary threads are included.  If a core's
 	 * primary thread is offline, that core is not covered.  CPU hotplug
@@ -622,6 +766,23 @@ void snp_setup_rmpopt(void)
 	wrmsrq_on_cpus(&rmpopt_cpumask, MSR_AMD64_RMPOPT_BASE, rmpopt_base);
 
 	cpus_read_unlock();
+
+	INIT_DELAYED_WORK(&rmpopt_delayed_work, rmpopt_work_handler);
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

## [6] Ashish Kalra — 2026-05-18
*Subject: [PATCH v5 5/7] x86/sev: Add interface to re-enable RMP optimizations.*

From: Ashish Kalra <ashish.kalra@amd.com>

RMPOPT table is a per-CPU table which indicates if 1GB regions of
physical memory are entirely hypervisor-owned or not.

When performing host memory accesses in hypervisor mode as well as
non-SNP guest mode, the processor may consult the RMPOPT table to
potentially skip an RMP access and improve performance.

Events such as RMPUPDATE can clear RMP optimizations. Add an interface
to re-enable those optimizations.

Reviewed-by: Ackerley Tng <ackerleytng@google.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/include/asm/sev.h |  2 ++
 arch/x86/virt/svm/sev.c    | 15 +++++++++++++++
 2 files changed, 17 insertions(+)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 6fd72a44a51e..09b1c5d33790 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -662,6 +662,7 @@ static inline void snp_leak_pages(u64 pfn, unsigned int pages)
 	__snp_leak_pages(pfn, pages, true);
 }
 int snp_prepare(void);
+void snp_rmpopt_all_physmem(void);
 void snp_setup_rmpopt(void);
 void snp_shutdown(void);
 #else
@@ -681,6 +682,7 @@ static inline void snp_leak_pages(u64 pfn, unsigned int npages) {}
 static inline void kdump_sev_callback(void) { }
 static inline void snp_fixup_e820_tables(void) {}
 static inline int snp_prepare(void) { return -ENODEV; }
+static inline void snp_rmpopt_all_physmem(void) {}
 static inline void snp_setup_rmpopt(void) {}
 static inline void snp_shutdown(void) {}
 #endif
diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index 8876cac052d5..7f8bb09844c1 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -707,6 +707,21 @@ static void rmpopt_work_handler(struct work_struct *work)
 		cpumask_set_cpu(this_cpu, &rmpopt_cpumask);
 }
 
+void snp_rmpopt_all_physmem(void)
+{
+	if (!cpu_feature_enabled(X86_FEATURE_RMPOPT))
+		return;
+
+	guard(mutex)(&rmpopt_wq_mutex);
+
+	if (!rmpopt_wq)
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

## [7] Ashish Kalra — 2026-05-18
*Subject: [PATCH v5 6/7] KVM: SEV: Perform RMP optimizations on SNP guest shutdown*

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

## [8] Ashish Kalra — 2026-05-18
*Subject: [PATCH v5 7/7] x86/sev: Add debugfs support for RMPOPT*

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
 arch/x86/virt/svm/sev.c | 121 ++++++++++++++++++++++++++++++++++++++++
 1 file changed, 121 insertions(+)

diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index 7f8bb09844c1..ac414143feed 100644
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
@@ -144,6 +146,15 @@ static DEFINE_SPINLOCK(snp_leaked_pages_list_lock);
 
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
 
@@ -583,6 +594,8 @@ static void rmpopt_cleanup(void)
 
 	cancel_delayed_work_sync(&rmpopt_delayed_work);
 	destroy_workqueue(rmpopt_wq);
+	debugfs_remove_recursive(rmpopt_debugfs);
+	rmpopt_debugfs = NULL;
 
 	cpus_read_lock();
 	wrmsrq_on_cpus(&rmpopt_cpumask, MSR_AMD64_RMPOPT_BASE, 0);
@@ -617,6 +630,10 @@ static inline bool __rmpopt(u64 rax, u64 rcx)
 		     : "a" (rax), "c" (rcx)
 		     : "memory", "cc");
 
+	if (rcx == RMPOPT_FUNC_REPORT_STATUS)
+		assign_cpu(smp_processor_id(), &rmpopt_report_cpumask,
+			   optimized);
+
 	return optimized;
 }
 
@@ -636,6 +653,108 @@ static void rmpopt_smp(void *val)
 	rmpopt((u64)val);
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
+	phys_addr_t end_paddr = rmpopt_pa_end;
+	struct seq_paddr *p = seq->private;
+
+	if (*pos == 0) {
+		p->next_seq_paddr = rmpopt_pa_start;
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
@@ -798,6 +917,8 @@ void snp_setup_rmpopt(void)
 	 * optimizations on all physical memory.
 	 */
 	queue_delayed_work(rmpopt_wq, &rmpopt_delayed_work, 0);
+
+	rmpopt_debugfs_setup();
 }
 EXPORT_SYMBOL_FOR_MODULES(snp_setup_rmpopt, "ccp");

---

## [9] Dave Hansen — 2026-05-18
*Subject: Re: [PATCH v5 2/7] x86/msr: add wrmsrq_on_cpus helper*

On 5/18/26 14:42, Ashish Kalra wrote:
> Co-developed-by: Dave Hansen <dave.hansen@linux.intel.com>
> Signed-off-by: Dave Hansen <dave.hansen@linux.intel.com>

Hi Ashish,

Sorry if my memory fails me, but I don't remember signing off on this.
Could you point me to the place where I gave you my Signed-off-by?

---

## [10] Kalra, Ashish — 2026-05-18
*Subject: Re: [PATCH v5 2/7] x86/msr: add wrmsrq_on_cpus helper*

Hello Dave,

On 5/18/2026 5:04 PM, Dave Hansen wrote:
> On 5/18/26 14:42, Ashish Kalra wrote:
>> Co-developed-by: Dave Hansen <dave.hansen@linux.intel.com>

Sorry about this, added this accidentally. 

You had suggested the code change, i accidentally took it as a Signed-off.

Thanks,
Ashish

---

## [11] Dave Hansen — 2026-05-18
*Subject: Re: [PATCH v5 2/7] x86/msr: add wrmsrq_on_cpus helper*

On 5/18/26 15:09, Kalra, Ashish wrote:
> On 5/18/2026 5:04 PM, Dave Hansen wrote:
>> On 5/18/26 14:42, Ashish Kalra wrote:

Hi Ashish,

First, please do me a favor and go back and re-read:

	Documentation/process/submitting-patches.rst

I recommend that everyone do this every once in a while so they remember
what they are constantly signing off on. It's important.

My personal rule for SoB lines is that I don't add them unless I've
explicitly talked to the person. Even then, I vastly prefer that the
person provides it to me *explicitly* (so I just copy and paste
directly) and on a public mailing list. That way, the avenues for
accidents to occur are very narrow.

---

## [12] Borislav Petkov — 2026-05-27
*Subject: Re: [PATCH v5 1/7] x86/cpufeatures: Add X86_FEATURE_AMD_RMPOPT
 feature flag*

On Mon, May 18, 2026 at 09:41:53PM +0000, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Streamline:

"RMPOPT is a new instruction that reduces the performance overhead of RMP
checks for the hypervisor and non‑SNP guests by allowing those checks to be
skipped when 1‑GB memory regions are known to contain no SEV‑SNP guest
memory."

---

## [13] Borislav Petkov — 2026-05-27
*Subject: Re: [PATCH v5 2/7] x86/msr: add wrmsrq_on_cpus helper*

On Mon, May 18, 2026 at 09:42:15PM +0000, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

So let's add yet another function which name differs from the other one by
a single letter and have people go look at the implementation to know which is
which...?

Instead of unifying what's there and extending this one to do what you want it
to do?

And now you have a wrmsrQ_on_cpus() but no rdmsrQ_on_cpus()?

Because if you look at the code, you'll see how those are used: first you
rdmsr on CPUs, modify each value and then wrmsr on same CPUs.

So no, try again pls.

---

## [14] Dave Hansen — 2026-05-27
*Subject: Re: [PATCH v5 2/7] x86/msr: add wrmsrq_on_cpus helper*

On 5/27/26 14:06, Borislav Petkov wrote:
> On Mon, May 18, 2026 at 09:42:15PM +0000, Ashish Kalra wrote:
>> From: Ashish Kalra <ashish.kalra@amd.com>

This one is my doing.

wrmsr_on_cpus() is kinda a mess. I think it only has a single user. It's
also not very flexible because it needs a 'struct msr __percpu *msrs'
argument where each MSR has a value in memory.

The use case for RMPOPT is that all CPUs get the same value. It'd be a
little awkward to go create a percpu data structure to duplcate the same
value to call wrmsr_on_cpus(). The RMPOPT case is also arguably
performance sensitive since it's done during boot. It should do the IPIs
in parallel.

toggle_ecc_err_reporting(), on the other hand, is done at module init
time. It's not really performance sensitive. It's probably pretty easy
to zap wrmsr_on_cpus() and just have toggle_ecc_err_reporting() do
something slightly less efficient.

Yeah, the

	wrmsr_on_cpus()
	wrmsrq_on_cpus()

naming pain is real. There's little chance of bugs coming from it
because the function signatures are *SO* different. But, it certainly
could confuse humans for a minute.

But the real solution to this is axing wrmsr_on_cpus(). Which I think we
could do after killing its one user which the attached (completely
untested) patch does. The only downside of the patch is that it does
RDMSR via IPIs one CPU at a time. But, looking at the code, I'm not sure
anyone would care. If anyone did, I _think_ all those MSRs have the same
value and the code could be simplified further. But that would take more
than 3 minutes.

It's also possible that my grepping was bad or I'm completely
misunderstanding amd64_edac.c. Cluebat welcome if I'm being dense.

BTW, I also don't feel the need to make Ashish go do any of this edac
cleanup. I think it can just be done in parallel. But I wouldn't stop
him if he volunteered.

---

## [15] Borislav Petkov — 2026-05-27
*Subject: Re: [PATCH v5 2/7] x86/msr: add wrmsrq_on_cpus helper*

On Wed, May 27, 2026 at 02:38:05PM -0700, Dave Hansen wrote:
> This one is my doing.

I know.

But hey, maybe we should not disagree on the public ML because the submitter
might disappear like the last one. :-P

> wrmsr_on_cpus() is kinda a mess. I think it only has a single user. It's
> also not very flexible because it needs a 'struct msr __percpu *msrs'

Right, we did that a looong time ago.

The only reason I'd have for per-CPU MSR structs is reading different MSR
values on different cores, modifying only the bits you need and then *keeping*
the remaining values as they were. And that interface allows you to do that
while this new thing won't.

And I'm going to venture a guess here that adding a simpler interface which
simply forces a new value ontop of a whole MSR could cause a lot of subtle
bugs when people don't pay attention to keep the old values.

> The use case for RMPOPT is that all CPUs get the same value. It'd be a
> little awkward to go create a percpu data structure to duplcate the same

Oh sure, my meaning was to create something that serves both purposes.

> toggle_ecc_err_reporting(), on the other hand, is done at module init
> time. It's not really performance sensitive. It's probably pretty easy

Sure. That's fine.

> Yeah, the
> 

Yap.

> But the real solution to this is axing wrmsr_on_cpus(). 

Yap, for example. Basically reingeneering the whole
write-MSRs-on-multiple-CPUs functionality is what I meant.

> Which I think we could do after killing its one user which the attached
> (completely untested) patch does. The only downside of the patch is that it

Looks ok to me, we can surely do that. I even hw to test it. I think...

> BTW, I also don't feel the need to make Ashish go do any of this edac
> cleanup. I think it can just be done in parallel. But I wouldn't stop

Why not?

It has always been the case: cleanups and bug fixes first, new features ontop.

So yeah, modulo figuring out how to redefine the *msr_on_cpus() interface,
I think this all makes sense.

Thx.

---
