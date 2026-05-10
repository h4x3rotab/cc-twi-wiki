---
title: 'x86/cpufeatures: Add X86_FEATURE_AMD_RMPOPT feature flag'
date: 2026-02-17
last_reply: 2026-02-18
message_count: 29
participants: ['Ashish Kalra', 'Dave Hansen', 'Ahmed S. Darwish', 'K Prateek Nayak', 'Uros Bizjak']
---

## [1] Ashish Kalra — 2026-02-17

From: Ashish Kalra <ashish.kalra@amd.com>

Add a flag indicating whether RMPOPT instruction is supported.

RMPOPT is a new instruction designed to minimize the performance
overhead of RMP checks on the hypervisor and on non-SNP guests by
allowing RMP checks to be skipped when 1G regions of memory are known
not to contain any SEV-SNP guest memory.

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

## [2] Ashish Kalra — 2026-02-17
*Subject: [PATCH 0/6] Add RMPOPT support.*

From: Ashish Kalra <ashish.kalra@amd.com>

In the SEV-SNP architecture, hypervisor and non-SNP guests are subject
to RMP checks on writes to provide integrity of SEV-SNP guest memory.

The RMPOPT architecture enables optimizations whereby the RMP checks
can be skipped if 1GB regions of memory are known to not contain any
SNP guest memory.

RMPOPT is a new instruction designed to minimize the performance
overhead of RMP checks for the hypervisor and non-SNP guests. 

As SNP is enabled by default the hypervisor and non-SNP guests are
subject to RMP write checks to provide integrity of SNP guest memory.

This patch series add support to enable RMPOPT optimizations globally
for all system RAM, and allow RMPUPDATE to disable those optimizations
as SNP guests are launched.

Additionally add a configfs interface to re-enable RMP optimizations at
runtime and debugfs interface to report per-CPU RMPOPT status across
all system RAM.

Ashish Kalra (6):
  x86/cpufeatures: Add X86_FEATURE_AMD_RMPOPT feature flag
  x86/sev: add support for enabling RMPOPT
  x86/sev: add support for RMPOPT instruction
  x86/sev: Add interface to re-enable RMP optimizations.
  x86/sev: Use configfs to re-enable RMP optimizations.
  x86/sev: Add debugfs support for RMPOPT

 arch/x86/include/asm/cpufeatures.h |   2 +-
 arch/x86/include/asm/msr-index.h   |   3 +
 arch/x86/include/asm/sev.h         |   2 +
 arch/x86/kernel/cpu/scattered.c    |   1 +
 arch/x86/kvm/Kconfig               |   1 +
 arch/x86/virt/svm/sev.c            | 471 +++++++++++++++++++++++++++++
 drivers/crypto/ccp/sev-dev.c       |   4 +
 7 files changed, 483 insertions(+), 1 deletion(-)

---

## [3] Ashish Kalra — 2026-02-17
*Subject: [PATCH 2/6] x86/sev: add support for enabling RMPOPT*

From: Ashish Kalra <ashish.kalra@amd.com>

The new RMPOPT instruction sets bits in a per-CPU RMPOPT table, which
indicates whether specific 1GB physical memory regions contain SEV-SNP
guest memory.

Per-CPU RMPOPT tables support at most 2 TB of addressable memory for
RMP optimizations. To handle this limitation:

For systems with 2 TB of RAM or less, configure each per-CPU RMPOPT
table base to 0 so that all system RAM is RMP-optimized on every CPU.

For systems with more than 2 TB of RAM, configure per-CPU RMPOPT
tables to cover the memory local to each NUMA node so RMP
optimizations can take advantage of NUMA locality. This must also
accommodate virtualized NUMA software domains (for example, AMD NPS
configurations) and ensure that the 2 TB RAM range local to each
physical socket is RMP-optimized.

Suggested-by: Thomas Lendacky <thomas.lendacky@amd.com>
Suggested-by: K Prateek Nayak <kprateek.nayak@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/include/asm/msr-index.h |   3 +
 arch/x86/virt/svm/sev.c          | 192 +++++++++++++++++++++++++++++++
 2 files changed, 195 insertions(+)

diff --git a/arch/x86/include/asm/msr-index.h b/arch/x86/include/asm/msr-index.h
index da5275d8eda6..8e7da03abd5b 100644
--- a/arch/x86/include/asm/msr-index.h
+++ b/arch/x86/include/asm/msr-index.h
@@ -753,6 +753,9 @@
 #define MSR_AMD64_SEG_RMP_ENABLED_BIT	0
 #define MSR_AMD64_SEG_RMP_ENABLED	BIT_ULL(MSR_AMD64_SEG_RMP_ENABLED_BIT)
 #define MSR_AMD64_RMP_SEGMENT_SHIFT(x)	(((x) & GENMASK_ULL(13, 8)) >> 8)
+#define MSR_AMD64_RMPOPT_BASE		0xc0010139
+#define MSR_AMD64_RMPOPT_ENABLE_BIT	0
+#define MSR_AMD64_RMPOPT_ENABLE		BIT_ULL(MSR_AMD64_RMPOPT_ENABLE_BIT)
 
 #define MSR_SVSM_CAA			0xc001f000
 
diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index ee643a6cd691..e6b784d26c33 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -127,6 +127,17 @@ static DEFINE_SPINLOCK(snp_leaked_pages_list_lock);
 
 static unsigned long snp_nr_leaked_pages;
 
+#define RMPOPT_TABLE_MAX_LIMIT_IN_TB	2
+#define NUM_TB(pfn_min, pfn_max)	\
+	(((pfn_max) - (pfn_min)) / (1 << (40 - PAGE_SHIFT)))
+
+struct rmpopt_socket_config {
+	unsigned long start_pfn, end_pfn;
+	cpumask_var_t cpulist;
+	int *node_id;
+	int current_node_idx;
+};
+
 #undef pr_fmt
 #define pr_fmt(fmt)	"SEV-SNP: " fmt
 
@@ -500,6 +511,185 @@ static bool __init setup_rmptable(void)
 	}
 }
 
+/*
+ * Build a cpumask of online primary threads, accounting for primary threads
+ * that have been offlined while their secondary threads are still online.
+ */
+static void get_cpumask_of_primary_threads(cpumask_var_t cpulist)
+{
+	cpumask_t cpus;
+	int cpu;
+
+	cpumask_copy(&cpus, cpu_online_mask);
+	for_each_cpu(cpu, &cpus) {
+		cpumask_set_cpu(cpu, cpulist);
+		cpumask_andnot(&cpus, &cpus, cpu_smt_mask(cpu));
+	}
+}
+
+static void __configure_rmpopt(void *val)
+{
+	u64 rmpopt_base = ((u64)val & PUD_MASK) | MSR_AMD64_RMPOPT_ENABLE;
+
+	wrmsrq(MSR_AMD64_RMPOPT_BASE, rmpopt_base);
+}
+
+static void configure_rmpopt_non_numa(cpumask_var_t primary_threads_cpulist)
+{
+	on_each_cpu_mask(primary_threads_cpulist, __configure_rmpopt, (void *)0, true);
+}
+
+static void free_rmpopt_socket_config(struct rmpopt_socket_config *socket)
+{
+	int i;
+
+	if (!socket)
+		return;
+
+	for (i = 0; i < topology_max_packages(); i++) {
+		free_cpumask_var(socket[i].cpulist);
+		kfree(socket[i].node_id);
+	}
+
+	kfree(socket);
+}
+DEFINE_FREE(free_rmpopt_socket_config, struct rmpopt_socket_config *, free_rmpopt_socket_config(_T))
+
+static void configure_rmpopt_large_physmem(cpumask_var_t primary_threads_cpulist)
+{
+	struct rmpopt_socket_config *socket __free(free_rmpopt_socket_config) = NULL;
+	int max_packages = topology_max_packages();
+	struct rmpopt_socket_config *sc;
+	int cpu, i;
+
+	socket = kcalloc(max_packages, sizeof(struct rmpopt_socket_config), GFP_KERNEL);
+	if (!socket)
+		return;
+
+	for (i = 0; i < max_packages; i++) {
+		sc = &socket[i];
+		if (!zalloc_cpumask_var(&sc->cpulist, GFP_KERNEL))
+			return;
+		sc->node_id = kcalloc(nr_node_ids, sizeof(int), GFP_KERNEL);
+		if (!sc->node_id)
+			return;
+		sc->current_node_idx = -1;
+	}
+
+	/*
+	 * Handle case of virtualized NUMA software domains, such as AMD Nodes Per Socket(NPS)
+	 * configurations. The kernel does not have an abstraction for physical sockets,
+	 * therefore, enumerate the physical sockets and Nodes Per Socket(NPS) information by
+	 * walking the online CPU list.
+	 */
+	for_each_cpu(cpu, primary_threads_cpulist) {
+		int socket_id, nid;
+
+		socket_id = topology_logical_package_id(cpu);
+		nid = cpu_to_node(cpu);
+		sc = &socket[socket_id];
+
+		/*
+		 * For each socket, determine the corresponding nodes and the socket's start
+		 * and end PFNs.
+		 * Record the node and the start and end PFNs of the first node found on the
+		 * socket, then record each subsequent node and update the end PFN for that
+		 * socket as additional nodes are found.
+		 */
+		if (sc->current_node_idx == -1) {
+			sc->current_node_idx = 0;
+			sc->node_id[sc->current_node_idx] = nid;
+			sc->start_pfn = node_start_pfn(nid);
+			sc->end_pfn = node_end_pfn(nid);
+		} else if (sc->node_id[sc->current_node_idx] != nid) {
+			sc->current_node_idx++;
+			sc->node_id[sc->current_node_idx] = nid;
+			sc->end_pfn = node_end_pfn(nid);
+		}
+
+		cpumask_set_cpu(cpu, sc->cpulist);
+	}
+
+	/*
+	 * If the "physical" socket has up to 2TB of memory, the per-CPU RMPOPT tables are
+	 * configured to the starting physical address of the socket, otherwise the tables
+	 * are configured per-node.
+	 */
+	for (i = 0; i < max_packages; i++) {
+		int num_tb_socket;
+		phys_addr_t pa;
+		int j;
+
+		sc = &socket[i];
+		num_tb_socket = NUM_TB(sc->start_pfn, sc->end_pfn) + 1;
+
+		pr_debug("socket start_pfn 0x%lx, end_pfn 0x%lx, socket cpu mask %*pbl\n",
+			 sc->start_pfn, sc->end_pfn, cpumask_pr_args(sc->cpulist));
+
+		if (num_tb_socket <= RMPOPT_TABLE_MAX_LIMIT_IN_TB) {
+			pa = PFN_PHYS(sc->start_pfn);
+			on_each_cpu_mask(sc->cpulist, __configure_rmpopt, (void *)pa, true);
+			continue;
+		}
+
+		for (j = 0; j <= sc->current_node_idx; j++) {
+			int nid = sc->node_id[j];
+			struct cpumask node_mask;
+
+			cpumask_and(&node_mask, cpumask_of_node(nid), sc->cpulist);
+			pa = PFN_PHYS(node_start_pfn(nid));
+
+			pr_debug("RMPOPT_BASE MSR on nodeid %d cpu mask %*pbl set to 0x%llx\n",
+				 nid, cpumask_pr_args(&node_mask), pa);
+			on_each_cpu_mask(&node_mask, __configure_rmpopt, (void *)pa, true);
+		}
+	}
+}
+
+static __init void configure_and_enable_rmpopt(void)
+{
+	cpumask_var_t primary_threads_cpulist;
+	int num_tb;
+
+	if (!cpu_feature_enabled(X86_FEATURE_RMPOPT)) {
+		pr_debug("RMPOPT not supported on this platform\n");
+		return;
+	}
+
+	if (!cc_platform_has(CC_ATTR_HOST_SEV_SNP)) {
+		pr_debug("RMPOPT optimizations not enabled as SNP support is not enabled\n");
+		return;
+	}
+
+	if (!(rmp_cfg & MSR_AMD64_SEG_RMP_ENABLED)) {
+		pr_info("RMPOPT optimizations not enabled, segmented RMP required\n");
+		return;
+	}
+
+	if (!zalloc_cpumask_var(&primary_threads_cpulist, GFP_KERNEL))
+		return;
+
+	num_tb = NUM_TB(min_low_pfn, max_pfn) + 1;
+	pr_debug("NUM_TB pages in system %d\n", num_tb);
+
+	/* Only one thread per core needs to set RMPOPT_BASE MSR as it is per-core */
+	get_cpumask_of_primary_threads(primary_threads_cpulist);
+
+	/*
+	 * Per-CPU RMPOPT tables support at most 2 TB of addressable memory for RMP optimizations.
+	 *
+	 * Fastpath RMPOPT configuration and setup:
+	 * For systems with <= 2 TB of RAM, configure each per-core RMPOPT base to 0,
+	 * ensuring all system RAM is RMP-optimized on all CPUs.
+	 */
+	if (num_tb <= RMPOPT_TABLE_MAX_LIMIT_IN_TB)
+		configure_rmpopt_non_numa(primary_threads_cpulist);
+	else
+		configure_rmpopt_large_physmem(primary_threads_cpulist);
+
+	free_cpumask_var(primary_threads_cpulist);
+}
+
 /*
  * Do the necessary preparations which are verified by the firmware as
  * described in the SNP_INIT_EX firmware command description in the SNP
@@ -555,6 +745,8 @@ int __init snp_rmptable_init(void)
 skip_enable:
 	cpuhp_setup_state(CPUHP_AP_ONLINE_DYN, "x86/rmptable_init:online", __snp_enable, NULL);
 
+	configure_and_enable_rmpopt();
+
 	/*
 	 * Setting crash_kexec_post_notifiers to 'true' to ensure that SNP panic
 	 * notifier is invoked to do SNP IOMMU shutdown before kdump.

---

## [4] Ashish Kalra — 2026-02-17
*Subject: [PATCH 3/6] x86/sev: add support for RMPOPT instruction*

From: Ashish Kalra <ashish.kalra@amd.com>

As SEV-SNP is enabled by default on boot when an RMP table is
allocated by BIOS, the hypervisor and non-SNP guests are subject to
RMP write checks to provide integrity of SNP guest memory.

RMPOPT is a new instruction that minimizes the performance overhead of
RMP checks on the hypervisor and on non-SNP guests by allowing RMP
checks to be skipped for 1GB regions of memory that are known not to
contain any SEV-SNP guest memory.

Enable RMPOPT optimizations globally for all system RAM at RMP
initialization time. RMP checks can initially be skipped for 1GB memory
ranges that do not contain SEV-SNP guest memory (excluding preassigned
pages such as the RMP table and firmware pages). As SNP guests are
launched, RMPUPDATE will disable the corresponding RMPOPT optimizations.

Suggested-by: Thomas Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/virt/svm/sev.c | 84 +++++++++++++++++++++++++++++++++++++++++
 1 file changed, 84 insertions(+)

diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index e6b784d26c33..a0d38fc50698 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -19,6 +19,7 @@
 #include <linux/iommu.h>
 #include <linux/amd-iommu.h>
 #include <linux/nospec.h>
+#include <linux/kthread.h>
 
 #include <asm/sev.h>
 #include <asm/processor.h>
@@ -127,10 +128,17 @@ static DEFINE_SPINLOCK(snp_leaked_pages_list_lock);
 
 static unsigned long snp_nr_leaked_pages;
 
+enum rmpopt_function {
+	RMPOPT_FUNC_VERIFY_AND_REPORT_STATUS,
+	RMPOPT_FUNC_REPORT_STATUS
+};
+
 #define RMPOPT_TABLE_MAX_LIMIT_IN_TB	2
 #define NUM_TB(pfn_min, pfn_max)	\
 	(((pfn_max) - (pfn_min)) / (1 << (40 - PAGE_SHIFT)))
 
+static struct task_struct *rmpopt_task;
+
 struct rmpopt_socket_config {
 	unsigned long start_pfn, end_pfn;
 	cpumask_var_t cpulist;
@@ -527,6 +535,66 @@ static void get_cpumask_of_primary_threads(cpumask_var_t cpulist)
 	}
 }
 
+/*
+ * 'val' is a system physical address aligned to 1GB OR'ed with
+ * a function selection. Currently supported functions are 0
+ * (verify and report status) and 1 (report status).
+ */
+static void rmpopt(void *val)
+{
+	asm volatile(".byte 0xf2, 0x0f, 0x01, 0xfc\n\t"
+		     : : "a" ((u64)val & PUD_MASK), "c" ((u64)val & 0x1)
+		     : "memory", "cc");
+}
+
+static int rmpopt_kthread(void *__unused)
+{
+	phys_addr_t pa_start, pa_end;
+	cpumask_var_t cpus;
+
+	if (!zalloc_cpumask_var(&cpus, GFP_KERNEL))
+		return -ENOMEM;
+
+	pa_start = ALIGN_DOWN(PFN_PHYS(min_low_pfn), PUD_SIZE);
+	pa_end = ALIGN(PFN_PHYS(max_pfn), PUD_SIZE);
+
+	while (!kthread_should_stop()) {
+		phys_addr_t pa;
+
+		pr_info("RMP optimizations enabled on physical address range @1GB alignment [0x%016llx - 0x%016llx]\n",
+			pa_start, pa_end);
+
+		/* Only one thread per core needs to issue RMPOPT instruction */
+		get_cpumask_of_primary_threads(cpus);
+
+		/*
+		 * RMPOPT optimizations skip RMP checks at 1GB granularity if this range of
+		 * memory does not contain any SNP guest memory.
+		 */
+		for (pa = pa_start; pa < pa_end; pa += PUD_SIZE) {
+			/* Bit zero passes the function to the RMPOPT instruction. */
+			on_each_cpu_mask(cpus, rmpopt,
+					 (void *)(pa | RMPOPT_FUNC_VERIFY_AND_REPORT_STATUS),
+					 true);
+
+			 /* Give a chance for other threads to run */
+			cond_resched();
+		}
+
+		set_current_state(TASK_INTERRUPTIBLE);
+		schedule();
+	}
+
+	free_cpumask_var(cpus);
+	return 0;
+}
+
+static void rmpopt_all_physmem(void)
+{
+	if (rmpopt_task)
+		wake_up_process(rmpopt_task);
+}
+
 static void __configure_rmpopt(void *val)
 {
 	u64 rmpopt_base = ((u64)val & PUD_MASK) | MSR_AMD64_RMPOPT_ENABLE;
@@ -687,6 +755,22 @@ static __init void configure_and_enable_rmpopt(void)
 	else
 		configure_rmpopt_large_physmem(primary_threads_cpulist);
 
+	rmpopt_task = kthread_create(rmpopt_kthread, NULL, "rmpopt_kthread");
+	if (IS_ERR(rmpopt_task)) {
+		pr_warn("Unable to start RMPOPT kernel thread\n");
+		rmpopt_task = NULL;
+		goto free_cpumask;
+	}
+
+	pr_info("RMPOPT worker thread created with PID %d\n", task_pid_nr(rmpopt_task));
+
+	/*
+	 * Once all per-CPU RMPOPT tables have been configured, enable RMPOPT
+	 * optimizations on all physical memory.
+	 */
+	rmpopt_all_physmem();
+
+free_cpumask:
 	free_cpumask_var(primary_threads_cpulist);
 }

---

## [5] Ashish Kalra — 2026-02-17
*Subject: [PATCH 4/6] x86/sev: Add interface to re-enable RMP optimizations.*

From: Ashish Kalra <ashish.kalra@amd.com>

RMPOPT table is a per-processor table which indicates if 1GB regions of
physical memory are entirely hypervisor-owned or not.

When performing host memory accesses in hypervisor mode as well as
non-SNP guest mode, the processor may consult the RMPOPT table to
potentially skip an RMP access and improve performance.

Events such as RMPUPDATE or SNP_INIT can clear RMP optimizations. Add
an interface to re-enable those optimizations.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/include/asm/sev.h   |  2 ++
 arch/x86/virt/svm/sev.c      | 17 +++++++++++++++++
 drivers/crypto/ccp/sev-dev.c |  4 ++++
 3 files changed, 23 insertions(+)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 0e6c0940100f..451fb2b2a0f7 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -657,6 +657,7 @@ int rmp_make_shared(u64 pfn, enum pg_level level);
 void __snp_leak_pages(u64 pfn, unsigned int npages, bool dump_rmp);
 void kdump_sev_callback(void);
 void snp_fixup_e820_tables(void);
+int snp_perform_rmp_optimization(void);
 static inline void snp_leak_pages(u64 pfn, unsigned int pages)
 {
 	__snp_leak_pages(pfn, pages, true);
@@ -677,6 +678,7 @@ static inline void __snp_leak_pages(u64 pfn, unsigned int npages, bool dump_rmp)
 static inline void snp_leak_pages(u64 pfn, unsigned int npages) {}
 static inline void kdump_sev_callback(void) { }
 static inline void snp_fixup_e820_tables(void) {}
+static inline int snp_perform_rmp_optimization(void) { return 0; }
 #endif
 
 #endif
diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index a0d38fc50698..713afcc2fab3 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -1305,6 +1305,23 @@ int rmp_make_shared(u64 pfn, enum pg_level level)
 }
 EXPORT_SYMBOL_GPL(rmp_make_shared);
 
+int snp_perform_rmp_optimization(void)
+{
+	if (!cpu_feature_enabled(X86_FEATURE_RMPOPT))
+		return -EINVAL;
+
+	if (!cc_platform_has(CC_ATTR_HOST_SEV_SNP))
+		return -EINVAL;
+
+	if (!(rmp_cfg & MSR_AMD64_SEG_RMP_ENABLED))
+		return -EINVAL;
+
+	rmpopt_all_physmem();
+
+	return 0;
+}
+EXPORT_SYMBOL_GPL(snp_perform_rmp_optimization);
+
 void __snp_leak_pages(u64 pfn, unsigned int npages, bool dump_rmp)
 {
 	struct page *page = pfn_to_page(pfn);
diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index 1cdadddb744e..d3df29b0c6bf 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1478,6 +1478,10 @@ static int __sev_snp_init_locked(int *error, unsigned int max_snp_asid)
 	}
 
 	snp_hv_fixed_pages_state_update(sev, HV_FIXED);
+
+	/* SNP_INIT clears the RMPOPT table, re-enable RMP optimizations */
+	snp_perform_rmp_optimization();
+
 	sev->snp_initialized = true;
 	dev_dbg(sev->dev, "SEV-SNP firmware initialized, SEV-TIO is %s\n",
 		data.tio_en ? "enabled" : "disabled");

---

## [6] Ashish Kalra — 2026-02-17
*Subject: [PATCH 5/6] x86/sev: Use configfs to re-enable RMP optimizations.*

From: Ashish Kalra <ashish.kalra@amd.com>

Use configfs as an interface to re-enable RMP optimizations at runtime

When SNP guests are launched, RMPUPDATE disables the corresponding
RMPOPT optimizations. Therefore, an interface is required to manually
re-enable RMP optimizations, as no mechanism currently exists to do so
during SNP guest cleanup.

Also select CONFIG_CONFIGFS_FS when host SEV or SNP support is enabled.

Suggested-by: Thomas Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/kvm/Kconfig    |  1 +
 arch/x86/virt/svm/sev.c | 79 +++++++++++++++++++++++++++++++++++++++++
 2 files changed, 80 insertions(+)

diff --git a/arch/x86/kvm/Kconfig b/arch/x86/kvm/Kconfig
index d916bd766c94..8fb21893ec8c 100644
--- a/arch/x86/kvm/Kconfig
+++ b/arch/x86/kvm/Kconfig
@@ -164,6 +164,7 @@ config KVM_AMD_SEV
 	select HAVE_KVM_ARCH_GMEM_PREPARE
 	select HAVE_KVM_ARCH_GMEM_INVALIDATE
 	select HAVE_KVM_ARCH_GMEM_POPULATE
+	select CONFIGFS_FS
 	help
 	  Provides support for launching encrypted VMs which use Secure
 	  Encrypted Virtualization (SEV), Secure Encrypted Virtualization with
diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index 713afcc2fab3..0f71a045e4aa 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -20,6 +20,7 @@
 #include <linux/amd-iommu.h>
 #include <linux/nospec.h>
 #include <linux/kthread.h>
+#include <linux/configfs.h>
 
 #include <asm/sev.h>
 #include <asm/processor.h>
@@ -146,6 +147,10 @@ struct rmpopt_socket_config {
 	int current_node_idx;
 };
 
+#define RMPOPT_CONFIGFS_NAME	"rmpopt"
+
+static atomic_t rmpopt_in_progress = ATOMIC_INIT(0);
+
 #undef pr_fmt
 #define pr_fmt(fmt)	"SEV-SNP: " fmt
 
@@ -581,6 +586,9 @@ static int rmpopt_kthread(void *__unused)
 			cond_resched();
 		}
 
+		/* Clear in_progress flag before going to sleep */
+		atomic_set(&rmpopt_in_progress, 0);
+
 		set_current_state(TASK_INTERRUPTIBLE);
 		schedule();
 	}
@@ -595,6 +603,75 @@ static void rmpopt_all_physmem(void)
 		wake_up_process(rmpopt_task);
 }
 
+static ssize_t rmpopt_action_show(struct config_item *item, char *page)
+{
+	return sprintf(page, "RMP optimization in progress: %s\n",
+		       atomic_read(&rmpopt_in_progress) == 1 ? "Yes" : "No");
+}
+
+static ssize_t rmpopt_action_store(struct config_item *item,
+				   const char *page, size_t count)
+{
+	int in_progress_flag, ret;
+	unsigned int action;
+
+	ret = kstrtouint(page, 10, &action);
+	if (ret)
+		return ret;
+
+	if (action == 1) {
+		/* perform RMP re-optimizations */
+		in_progress_flag = atomic_cmpxchg(&rmpopt_in_progress, 0, 1);
+		if (!in_progress_flag)
+			rmpopt_all_physmem();
+	} else {
+		return -EINVAL;
+	}
+
+	return count;
+}
+
+static ssize_t rmpopt_description_show(struct config_item *item, char *page)
+{
+	return sprintf(page, "[RMPOPT]\n\necho 1 > action to perform RMP optimization.\n");
+}
+
+CONFIGFS_ATTR(rmpopt_, action);
+CONFIGFS_ATTR_RO(rmpopt_, description);
+
+static struct configfs_attribute *rmpopt_attrs[] = {
+	&rmpopt_attr_action,
+	&rmpopt_attr_description,
+	NULL,
+};
+
+static const struct config_item_type rmpopt_config_type = {
+	.ct_attrs       = rmpopt_attrs,
+	.ct_owner       = THIS_MODULE,
+};
+
+static struct configfs_subsystem rmpopt_configfs = {
+	.su_group = {
+		.cg_item = {
+		.ci_namebuf = RMPOPT_CONFIGFS_NAME,
+		.ci_type = &rmpopt_config_type,
+		},
+	},
+	.su_mutex = __MUTEX_INITIALIZER(rmpopt_configfs.su_mutex),
+};
+
+static int rmpopt_configfs_setup(void)
+{
+	int ret;
+
+	config_group_init(&rmpopt_configfs.su_group);
+	ret = configfs_register_subsystem(&rmpopt_configfs);
+	if (ret)
+		pr_err("Error %d while registering subsystem %s\n", ret, RMPOPT_CONFIGFS_NAME);
+
+	return ret;
+}
+
 static void __configure_rmpopt(void *val)
 {
 	u64 rmpopt_base = ((u64)val & PUD_MASK) | MSR_AMD64_RMPOPT_ENABLE;
@@ -770,6 +847,8 @@ static __init void configure_and_enable_rmpopt(void)
 	 */
 	rmpopt_all_physmem();
 
+	rmpopt_configfs_setup();
+
 free_cpumask:
 	free_cpumask_var(primary_threads_cpulist);
 }

---

## [7] Ashish Kalra — 2026-02-17
*Subject: [PATCH 6/6] x86/sev: Add debugfs support for RMPOPT*

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
 arch/x86/virt/svm/sev.c | 101 +++++++++++++++++++++++++++++++++++++++-
 1 file changed, 100 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index 0f71a045e4aa..c5a11f574e42 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -21,6 +21,8 @@
 #include <linux/nospec.h>
 #include <linux/kthread.h>
 #include <linux/configfs.h>
+#include <linux/debugfs.h>
+#include <linux/seq_file.h>
 
 #include <asm/sev.h>
 #include <asm/processor.h>
@@ -151,6 +153,13 @@ struct rmpopt_socket_config {
 
 static atomic_t rmpopt_in_progress = ATOMIC_INIT(0);
 
+static cpumask_t rmpopt_cpumask;
+static struct dentry *rmpopt_debugfs;
+
+struct seq_paddr {
+	phys_addr_t next_seq_paddr;
+};
+
 #undef pr_fmt
 #define pr_fmt(fmt)	"SEV-SNP: " fmt
 
@@ -547,9 +556,14 @@ static void get_cpumask_of_primary_threads(cpumask_var_t cpulist)
  */
 static void rmpopt(void *val)
 {
+	bool optimized;
+
 	asm volatile(".byte 0xf2, 0x0f, 0x01, 0xfc\n\t"
-		     : : "a" ((u64)val & PUD_MASK), "c" ((u64)val & 0x1)
+		     : "=@ccc" (optimized)
+		     : "a" ((u64)val & PUD_MASK), "c" ((u64)val & 0x1)
 		     : "memory", "cc");
+
+	assign_cpu(smp_processor_id(), &rmpopt_cpumask, optimized);
 }
 
 static int rmpopt_kthread(void *__unused)
@@ -672,6 +686,89 @@ static int rmpopt_configfs_setup(void)
 	return ret;
 }
 
+/*
+ * start() can be called multiple times if allocated buffer has overflowed
+ * and bigger buffer is allocated.
+ */
+static void *rmpopt_table_seq_start(struct seq_file *seq, loff_t *pos)
+{
+	phys_addr_t end_paddr = ALIGN(PFN_PHYS(max_pfn), PUD_SIZE);
+	struct seq_paddr *p = seq->private;
+
+	if (*pos == 0) {
+		p->next_seq_paddr = ALIGN_DOWN(PFN_PHYS(min_low_pfn), PUD_SIZE);
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
+	phys_addr_t end_paddr = ALIGN(PFN_PHYS(max_pfn), PUD_SIZE);
+	phys_addr_t *curr_paddr = v;
+
+	(*pos)++;
+	if (*curr_paddr == end_paddr)
+		return NULL;
+	*curr_paddr += PUD_SIZE;
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
+	seq_printf(seq, "Memory @%3lluGB: ", *curr_paddr >> PUD_SHIFT);
+
+	cpumask_clear(&rmpopt_cpumask);
+	on_each_cpu_mask(cpu_online_mask, rmpopt,
+			 (void *)(*curr_paddr | RMPOPT_FUNC_REPORT_STATUS),
+			 true);
+
+	if (cpumask_empty(&rmpopt_cpumask))
+		seq_puts(seq, "CPU(s): none\n");
+	else
+		seq_printf(seq, "CPU(s): %*pbl\n", cpumask_pr_args(&rmpopt_cpumask));
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
+	rmpopt_debugfs = debugfs_create_dir("rmpopt", NULL);
+
+	debugfs_create_file("rmpopt-table", 0444, rmpopt_debugfs,
+			    NULL, &rmpopt_table_fops);
+}
+
 static void __configure_rmpopt(void *val)
 {
 	u64 rmpopt_base = ((u64)val & PUD_MASK) | MSR_AMD64_RMPOPT_ENABLE;
@@ -849,6 +946,8 @@ static __init void configure_and_enable_rmpopt(void)
 
 	rmpopt_configfs_setup();
 
+	rmpopt_debugfs_setup();
+
 free_cpumask:
 	free_cpumask_var(primary_threads_cpulist);
 }

---

## [8] Dave Hansen — 2026-02-17
*Subject: Re: [PATCH 2/6] x86/sev: add support for enabling RMPOPT*

> +#define RMPOPT_TABLE_MAX_LIMIT_IN_TB	2
> +#define NUM_TB(pfn_min, pfn_max)	\

IMNHO, you should just keep these in bytes. No reason to keep them in TB.

> +struct rmpopt_socket_config {
> +	unsigned long start_pfn, end_pfn;

This looks like optimization complexity before the groundwork is in
place. Also, don't we *have* CPU lists for NUMA nodes? This seems rather
redundant.

> +/*
> + * Build a cpumask of online primary threads, accounting for primary threads

Don't we have a primary thread mask already? I thought we did.

> +static void __configure_rmpopt(void *val)
> +{

I'd honestly just make the callers align the address..

> +static void configure_rmpopt_non_numa(cpumask_var_t primary_threads_cpulist)
> +{

Looking at all this, I really think you need a more organized series.

Make something that's _functional_ and works for all <2TB configs. Then,
go add all this NUMA complexity in a follow-on patch or patches. There's
too much going on here.

> +static void configure_rmpopt_large_physmem(cpumask_var_t primary_threads_cpulist)
> +{

By this point, I've forgotten why sockets are important here.

Why are they important?

> +	for_each_cpu(cpu, primary_threads_cpulist) {
> +		int socket_id, nid;

Ahh, so you're not optimizing by NUMA itself: you're assuming that there
are groups of NUMA nodes in a socket and then optimizing for those groups.

It would have been nice to say that. It would make great material for
the changelog for your broken out patches.

I have the feeling that the structure here could be one of these in a patch:

 1. Support systems with <2TB of memory
 2. Support a RMPOPT range per NUMA node
 3. Group NUMA nodes at socket boundaries and have them share a common
    RMPOPT config.

Right?

> +static __init void configure_and_enable_rmpopt(void)
> +{

This looks wrong. Earlier, you program 0 as the base RMPOPT address into
the MSR. But this uses 'min_low_pfn'. Why not 0?

> +	/* Only one thread per core needs to set RMPOPT_BASE MSR as it is per-core */
> +	get_cpumask_of_primary_threads(primary_threads_cpulist);

this part:

> +	else
> +		configure_rmpopt_large_physmem(primary_threads_cpulist);

^^ needs to be broken out into a separate optimization patch.

---

## [9] Dave Hansen — 2026-02-17
*Subject: Re: [PATCH 0/6] Add RMPOPT support.*

On 2/17/26 12:09, Ashish Kalra wrote:
> RMPOPT is a new instruction designed to minimize the performance
> overhead of RMP checks for the hypervisor and non-SNP guests. 

This needs a little theory of operation for the new instruction. It
seems like it will enable optimizations all by itself. You just call it,
and it figures out when the CPU can optimize things. The CPU also
figures out when the optimization must be flipped off.

That's not awful.

To be honest, though, I think this is misdesigned. Shouldn't the CPU
*boot* in a state where it is optimized? Why should software have to
tell it that coming out of reset, there is no SEV-SNP memory?

---

## [10] Dave Hansen — 2026-02-17
*Subject: Re: [PATCH 5/6] x86/sev: Use configfs to re-enable RMP optimizations.*

On 2/17/26 12:11, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Is this like a proof-of-concept to poke the hardware and show it works?
Or, is this intended to be the way that folks actually interact with
SEV-SNP optimization in real production scenarios?

Shouldn't freeing SEV-SNP memory back to the system do this
automatically? Worst case, keep a 1-bit-per-GB bitmap of memory that's
been freed and schedule_work() to run in 1 or 10 or 100 seconds. That
should batch things up nicely enough. No?

I can't fathom that users don't want this to be done automatically for them.

Is the optimization scan really expensive or something? 1GB of memory
should have a small number of megabytes of metadata to scan.

---

## [11] Ahmed S. Darwish — 2026-02-17
*Subject: Re: [PATCH 6/6] x86/sev: Add debugfs support for RMPOPT*

On Tue, 17 Feb 2026, Ashish Kalra wrote:
>
> To dump the per-CPU RMPOPT status for all system RAM:
...
> +
> +static void rmpopt_debugfs_setup(void)

For mainline, this should be under /sys/kernel/debug/x86/ instead:

    dir = debugfs_create_dir("rmpopt", arch_debugfs_dir);

Thanks,
Ahmed

---

## [12] Ahmed S. Darwish — 2026-02-18
*Subject: Re: [PATCH 1/6] x86/cpufeatures: Add X86_FEATURE_AMD_RMPOPT feature
 flag*

On Tue, 17 Feb 2026, Ashish Kalra wrote:
>
> --- a/arch/x86/kernel/cpu/scattered.c

CPUID(0x80000025).EDX is documented as reserved in the latest public
version of the APM, volume 3 (2025-07-02.)

I'll add it to the upcoming x86-cpuid-db release:

    https://gitlab.com/x86-cpuid.org/x86-cpuid-db

Thanks,

--
Ahmed S. Darwish
Linutronix GmbH

---

## [13] K Prateek Nayak — 2026-02-18
*Subject: Re: [PATCH 2/6] x86/sev: add support for enabling RMPOPT*

Hello Dave,

On 2/18/2026 3:36 AM, Dave Hansen wrote:
>> +/*
>> + * Build a cpumask of online primary threads, accounting for primary threads

If you are referring to cpu_primary_thread_mask(), the CPUs are set on it
based on the LSB of APICID, specifically:

    !(apicid & (__max_threads_per_core - 1))

It can so happen, the primary thread ((apicid & 1) == 0) of the core is
offline while the secondary thread ((apicid & 1) == 1) is online but the
traversal of (cpu_primary_thread_mask() & cpu_online_mask()) will simply
skip these cores.

Is there an equivalent mask that sets the first online CPU of each core?

---

## [14] Kalra, Ashish — 2026-02-17
*Subject: Re: [PATCH 5/6] x86/sev: Use configfs to re-enable RMP optimizations.*

Hello Dave, 

On 2/17/2026 4:19 PM, Dave Hansen wrote:
> On 2/17/26 12:11, Ashish Kalra wrote:
>> From: Ashish Kalra <ashish.kalra@amd.com>

Actually, the RMPOPT implementation is going to be a multi-phased development.

In the first phase (which is this patch-series) we enable RMPOPT globally, and let RMPUPDATE(s)
slowly switch it off over time as SNP guest spin up, and then in phase#2 once 1GB hugetlb is in place,
we enable re-issuing of RMPOPT during 1GB page cleanup.

So automatic re-issuing of RMPOPT will be done when SNP guests are shutdown and as part of 
SNP guest cleanup once 1GB hugetlb support (for guest_memfd) has been merged. 

As currently, i.e, as part of this patch series, there is no mechanism to re-issue RMPOPT
automatically as part of SNP guest cleanup, therefore this support exists to doing it
manually at runtime via configfs.

I will describe this multi-phased RMPOPT implementation plan in the cover letter for 
next revision of this patch series.

Thanks,
Ashish

> 
> I can't fathom that users don't want this to be done automatically for them.

---

## [15] Kalra, Ashish — 2026-02-17
*Subject: Re: [PATCH 0/6] Add RMPOPT support.*

Hello Dave,

On 2/17/2026 4:11 PM, Dave Hansen wrote:
> On 2/17/26 12:09, Ashish Kalra wrote:
>> RMPOPT is a new instruction designed to minimize the performance

Yes, i will add more theory of operation for the new instruction. 

RMPOPT instruction with the verify and report status operation, in this operation
the CPU will read the RMP contents, verify the entire 1GB region starting
at the provided SPA is HV-owned. For the entire 1GB region it checks that all RMP
entries in this region are HV-owned (i.e, not in assigned state) and then 
accordingly update the RMPOPT table to indicate if optimization has been enabled 
and provide indication to software if the optimization was successful.

RMPUPDATE instruction that mark new pages as assigned will automatically clear the
optimizations and the appropriate bit in the RMPOPT table. 

The RMPOPT table is managed by a combination of software and hardware.  Software uses
the RMPOPT instruction to set bits in the table, indicating that regions of memory are
entirely HV-owned.  Hardware automatically clears bits in the RMPOPT table when RMP contents
are changed during RMPUPDATE instruction.

> 
> That's not awful.

When the CPU boots, the RMP checks are not done and therefore the CPU
is booting in a state where it is optimized.

The RMP checks are not enabled till SEV-SNP is enabled and SNP is enabled
during kernel boot (as part of iommu_snp_enable() -> snp_rmptable_init()).

Once SNP is enabled as part of kernel boot, hypervisor and non-SNP guests are
subject to RMP checks on writes to provide integrity of SEV-SNP guest memory.

Therefore, we need to enable these RMP optimizations after SNP has been 
enabled to indicate which 1GB regions of memory are known to not contain any
SEV-SNP guest memory.

I will add the above details to the cover letter for the next revision of this
patch series.

Thanks,
Ashish

---

## [16] Kalra, Ashish — 2026-02-17
*Subject: Re: [PATCH 5/6] x86/sev: Use configfs to re-enable RMP optimizations.*

On 2/17/2026 9:34 PM, Kalra, Ashish wrote:
> Hello Dave, 
> 

And there is a cost associated with re-enabling the optimizations for all 
system RAM (even though it runs as a background kernel thread executing RMPOPT
on different 1GB regions in parallel and with inline cond_resched()'s), 
we don't want to run this periodically. 

In case of running SNP guests, this scheduled/periodic run will conflict with
RMPUPDATE(s) being executed for assigning the guest pages and marking them as private.
Even though the hardware takes care of handling such race conditions where 
one CPU is doing RMPOPT on it while another is changing one of the pages in that
region to be assigned via RMPUPDATE.  In this case, the hardware ensures that after
the RMPUPDATE completes, the CPU that did RMPOPT will see the region as un-optimized.

Once 1GB hugetlb support (for guest_memfd) has been merged, however it will be
straightforward to plumb it into the 1GB hugetlb cleanup path.

Thanks,
Ashish

> 
> Actually, the RMPOPT implementation is going to be a multi-phased development.

---

## [17] Dave Hansen — 2026-02-18
*Subject: Re: [PATCH 2/6] x86/sev: add support for enabling RMPOPT*

On 2/17/26 19:08, K Prateek Nayak wrote:
> Hello Dave,
> 

No I don't think we have that sitting around.

But, stepping back, why is this even necessary? Is it just saving a few
IPIs in the super rare case that someone has offlined the primary thread
but not a secondary one?

Why bother?

---

## [18] Dave Hansen — 2026-02-18
*Subject: Re: [PATCH 0/6] Add RMPOPT support.*

On 2/17/26 20:12, Kalra, Ashish wrote:
>> That's not awful.
>>

They are known not to contain any SEV-SNP guest memory at the moment
snp_rmptable_init() finishes, no?

---

## [19] Dave Hansen — 2026-02-18
*Subject: Re: [PATCH 5/6] x86/sev: Use configfs to re-enable RMP optimizations.*

On 2/17/26 19:34, Kalra, Ashish wrote:
...
> As currently, i.e, as part of this patch series, there is no
> mechanism to re-issue RMPOPT automatically as part of SNP guest
I think you need a mechanism that re-enable RMP optimizations
automatically for this feature to go upstream. It's just dead code
otherwise, and we don't merge dead code.

A configfs hack doesn't really count.

---

## [20] Uros Bizjak — 2026-02-18
*Subject: Re: [PATCH 3/6] x86/sev: add support for RMPOPT instruction*

On 2/17/26 21:10, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

There is no need for \n\t instruction delimiter with single instruction 
in the asm template, it will just confuse compiler's insn count estimator.

Uros.

> +		     : : "a" ((u64)val & PUD_MASK), "c" ((u64)val & 0x1)
> +		     : "memory", "cc");

---

## [21] Kalra, Ashish — 2026-02-18
*Subject: Re: [PATCH 2/6] x86/sev: add support for enabling RMPOPT*

On 2/18/2026 8:59 AM, Dave Hansen wrote:
> On 2/17/26 19:08, K Prateek Nayak wrote:
>> Hello Dave,

Because, setting RMPOPT_BASE MSR (which is a per-core MSR) and RMPOPT instruction
need to be issued on only one thread per core. If the primary thread is offlined
and secondary thread is not considered, we will miss/skip setting either the
RMPOPT_BASE MSR or not issuing the RMPOPT instruction for that physical CPU, which means
no RMP optimizations enabled for that physical CPU.

Thanks,
Ashish

---

## [22] Dave Hansen — 2026-02-18
*Subject: Re: [PATCH 2/6] x86/sev: add support for enabling RMPOPT*

On 2/18/26 08:55, Kalra, Ashish wrote:
> Because, setting RMPOPT_BASE MSR (which is a per-core MSR) and
> RMPOPT instruction need to be issued on only one thread per core. If
What is the harm of issuing it twice per core?

---

## [23] Kalra, Ashish — 2026-02-18
*Subject: Re: [PATCH 0/6] Add RMPOPT support.*

On 2/18/2026 9:03 AM, Dave Hansen wrote:
> On 2/17/26 20:12, Kalra, Ashish wrote:
>>> That's not awful.

Yes, but RMP checks are still performed and they affect performance.

Testing a bit in the per‑CPU RMPOPT table to avoid RMP checks significantly improves performance.

Thanks,
Ashish

---

## [24] Kalra, Ashish — 2026-02-18
*Subject: Re: [PATCH 2/6] x86/sev: add support for enabling RMPOPT*

On 2/18/2026 11:01 AM, Dave Hansen wrote:
> On 2/18/26 08:55, Kalra, Ashish wrote:
>> Because, setting RMPOPT_BASE MSR (which is a per-core MSR) and

Why to issue it if we can avoid it.

It is not that complex to setup a cpumask containing the online primary
or secondary thread and then issue the RMPOPT instruction only once per
thread.

Thanks,
Ashish

---

## [25] Dave Hansen — 2026-02-18
*Subject: Re: [PATCH 0/6] Add RMPOPT support.*

On 2/18/26 09:03, Kalra, Ashish wrote:
>> They are known not to contain any SEV-SNP guest memory at the
>> moment snp_rmptable_init() finishes, no?

Sorry, Ashish, I don't think I'm explaining myself very well. Let me try
again, please.

First, my goal here is to ensure that the system has a whole has good
performance, with minimal kernel code, and in the most common
configurations.

I would wager that the most common SEV-SNP configuration in the whole
world is a system that has booted, enabled SEV-SNP, and has never run an
SEV-SNP guest. If it's not *the* most common, it's certainly going to be
common enough to care about deeply.

Do you agree?

If you agree, I hope we can also agree that a "SNP enabled but never ran
a guest" state is deserving of good performance with minimal kernel code.

My assumption (which is maybe a bad one) is that there is a natural
point when SEV-SNP is enabled on the system when the system as a whole
can easily assert that no SEV-SNP guest has ever run. I'm assuming that
there is *a* point where, for instance, the RMP table gets atomically
flipped from being unprotected to being protected. At that point, its
state *must* be known. It must also be naturally obvious that no guest
has had a chance to run at this point.

If that point can be leveraged, and the RMPOPT optimization can be
applied at SEV-SNP enabled time, then an important SEV-SNP configuration
would be optimized by default and with zero or little kernel code needed
to drive it.

To me, that seems like a valuable goal.

Do you agree?

---

## [26] Dave Hansen — 2026-02-18
*Subject: Re: [PATCH 2/6] x86/sev: add support for enabling RMPOPT*

On 2/18/26 09:07, Kalra, Ashish wrote:
> On 2/18/2026 11:01 AM, Dave Hansen wrote:
>> On 2/18/26 08:55, Kalra, Ashish wrote:

It's a non-zero amount of error-prone kernel code. It *is* complex. It
has to be reviewed and maintained.

Please remove this unnecessary optimization from the series. If you
would like to add it back, please do it in a patch at the end so it can
be evaluated on its own. Include performance numbers so the code
complexity can be balanced against the performance gain.

---

## [27] Kalra, Ashish — 2026-02-18
*Subject: Re: [PATCH 0/6] Add RMPOPT support.*

Hello Dave,

On 2/18/2026 11:15 AM, Dave Hansen wrote:
> On 2/18/26 09:03, Kalra, Ashish wrote:
>>> They are known not to contain any SEV-SNP guest memory at the

Yes.

> 
> If you agree, I hope we can also agree that a "SNP enabled but never ran

Now, RMP gets protected at the *same* point where SNP is enabled and then
RMP checking is started. And this is the same point at which RMPOPT
optimizations are enabled with this patch. 

I believe you are talking about the hardware doing it as part of SNP enablement, 
but that isn't how it is implemented and the reasons for that are it would take
a long time (in CPU terms) for a single WRMSR, and we don't support that.

And if RMP has been allocated means that you are going to be running SNP guests,
otherwise you wouldn't have allocated the RMP and enabled SNP in BIOS. 

The RMPOPT feature address the RMP checks associated with non-SNP guests and the 
hypervisor itself, theoretically, a cloud provider has good memory placement for
guests and can benefit even when launching/running SNP guests.

We can simplify this initial series to just using this RMPOPT feature and enabling
RMP optimizations for 0 to 2TB across the system and then do the optimizations
for/or supporting larger systems as a follow on series.

That will address your concerns of performing the RMPOPT optimizations at
SEV-SNP enabled time, and having the important SEV-SNP configuration
optimized by default and with little kernel code needed to drive it.

Thanks,
Ashish

---

## [28] Kalra, Ashish — 2026-02-18
*Subject: Re: [PATCH 2/6] x86/sev: add support for enabling RMPOPT*

Hello Dave,

On 2/17/2026 4:06 PM, Dave Hansen wrote:
>> +#define RMPOPT_TABLE_MAX_LIMIT_IN_TB	2
>> +#define NUM_TB(pfn_min, pfn_max)	\

Yes, we do have CPU lists for NUMA nodes, but we need a socket specific 
cpumask, let me explain more about that below. 

>> +/*
>> + * Build a cpumask of online primary threads, accounting for primary threads

Already discussed this. 

>> +static void __configure_rmpopt(void *val)
>> +{

Sure. 

> 
>> +static void configure_rmpopt_large_physmem(cpumask_var_t primary_threads_cpulist)
Because, Nodes per Socket (NPS) configuration is enabled by default, therefore, we have to
look at Sockets instead of simply NUMA nodes, and collect/aggregate all the Node data per Socket
and then accordingly setup the RMPOPT tables, so that the 2TB limit of RMPOPT tables is covered
appropriately and we try to map the maximum possible memory in RMPOPT tables per-Socket rather
than per-Node.

And as there is no per-Socket information available in kernel, we walk through the online
CPU list and collect all this per-Socket information (including socket's start, end addresses,
NUMA nodes in the socket, cpumask of the socket, etc.)

>  
>> +	for_each_cpu(cpu, primary_threads_cpulist) {
Yes, by default Venice platform has the NPS2 configuration enabled by default,
so we have 'X' nodes per socket and we have to consider this NPSx configuration
and optimize for those groups. 

> It would have been nice to say that. It would make great material for
> the changelog for your broken out patches.

Ok. 

> 
> I have the feeling that the structure here could be one of these in a patch:

Yes, sure.

> 
>> +static __init void configure_and_enable_rmpopt(void)

You are right, we should have used min_low_pfn earlier to program the 
base RMPOPT address into the MSR. 

> 
>> +	/* Only one thread per core needs to set RMPOPT_BASE MSR as it is per-core */

Ok.

Thanks,
Ashish

---

## [29] Dave Hansen — 2026-02-18
*Subject: Re: [PATCH 2/6] x86/sev: add support for enabling RMPOPT*

On 2/18/26 14:17, Kalra, Ashish wrote:
> Yes, by default Venice platform has the NPS2 configuration enabled by default,
> so we have 'X' nodes per socket and we have to consider this NPSx configuration

Why, though?

You keep saying: "We have NPS so we must configure sockets". But not *why*.

I suspect this is another premature optimization. Nodes are a bit too
small so if you configure via nodes, the later nodes will have RMPOPT
tables that cover empty address space off the end of system memory.

Honestly, I think this is all just done wrong. It doesn't need to even
consider sockets. Sockets might even be the wrong thing to look at.

Basically, RMPOPT gives you a 2TB window of potentially "fast" memory.
The rest of memory is "slow". If you're lucky, the memory that's fast
because of RMPOPT is also in a low-distance NUMA node.

Sockets are a good thing to use, for sure. But they're not even optimal!
Just imagine what's going to happen if you have more than 2TB in a
socket. You just turn off the per-socket optimization. If that happens,
the last node in the socket will end up with an RMPOPT table that has
itself at the beginning, but probably a nonzero amount of off-socket memory.

I'd probably just do something like this:

Given a NUMA node, go through each 1GB of memory in the system and see
what the average NUMA distance of that 2TB window of memory is. Find the
2TB window with the lowest average distance. That'll give you a more or
less optimal RMPOPT window. It'll work with NPS or regular NUMA or
whatever bonkers future fancy thing shows up.

But that's all optimization territory. Please squirrel that away to go
look at in 6 months once you get the rest of this merged.

---
