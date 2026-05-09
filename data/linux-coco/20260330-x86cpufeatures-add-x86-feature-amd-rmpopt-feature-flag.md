---
title: 'x86/cpufeatures: Add X86_FEATURE_AMD_RMPOPT feature flag'
date: 2026-03-30
last_reply: 2026-04-08
message_count: 16
participants: ['Ashish Kalra', 'Dave Hansen']
---

## [1] Ashish Kalra — 2026-03-30

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

## [2] Ashish Kalra — 2026-03-30
*Subject: [PATCH v3 2/6] x86/sev: Add support for enabling RMPOPT*

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

Suggested-by: Thomas Lendacky <thomas.lendacky@amd.com>
Suggested-by: Dave Hansen <dave.hansen@linux.intel.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/include/asm/msr-index.h |  3 +++
 arch/x86/virt/svm/sev.c          | 26 ++++++++++++++++++++++++++
 2 files changed, 29 insertions(+)

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
 
diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index e35fac0a8a3d..dc6a8e102cdc 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -477,6 +477,30 @@ static bool __init setup_rmptable(void)
 	return true;
 }
 
+static __init void configure_and_enable_rmpopt(void)
+{
+	phys_addr_t pa_start = ALIGN_DOWN(PFN_PHYS(min_low_pfn), SZ_1G);
+	u64 rmpopt_base = pa_start | MSR_AMD64_RMPOPT_ENABLE;
+	int cpu;
+
+	if (!cpu_feature_enabled(X86_FEATURE_RMPOPT))
+		return;
+
+	if (!(rmp_cfg & MSR_AMD64_SEG_RMP_ENABLED)) {
+		pr_notice("RMPOPT optimizations not enabled, segmented RMP required\n");
+		return;
+	}
+
+	/*
+	 * Per-CPU RMPOPT tables support at most 2 TB of addressable memory
+	 * for RMP optimizations. Initialize the per-CPU RMPOPT table base
+	 * to the starting physical address to enable RMP optimizations for
+	 * up to 2 TB of system RAM on all CPUs.
+	 */
+	for_each_online_cpu(cpu)
+		wrmsrq_on_cpu(cpu, MSR_AMD64_RMPOPT_BASE, rmpopt_base);
+}
+
 /*
  * Do the necessary preparations which are verified by the firmware as
  * described in the SNP_INIT_EX firmware command description in the SNP
@@ -530,6 +554,8 @@ int __init snp_rmptable_init(void)
 	 */
 	crash_kexec_post_notifiers = true;
 
+	configure_and_enable_rmpopt();
+
 	return 0;
 }

---

## [3] Ashish Kalra — 2026-03-30
*Subject: [PATCH v3 3/6] x86/sev: Add support to perform RMP optimizations asynchronously*

From: Ashish Kalra <ashish.kalra@amd.com>

As SEV-SNP is enabled by default on boot when an RMP table is
allocated by BIOS, the hypervisor and non-SNP guests are subject to
RMP write checks to provide integrity of SNP guest memory.

RMPOPT is a new instruction that minimizes the performance overhead of
RMP checks on the hypervisor and on non-SNP guests by allowing RMP
checks to be skipped for 1GB regions of memory that are known not to
contain any SEV-SNP guest memory.

Add support for performing RMP optimizations asynchronously using a
dedicated workqueue, scheduling delayed work to perform RMP
optimizations every 10 seconds.

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
 arch/x86/virt/svm/sev.c | 114 ++++++++++++++++++++++++++++++++++++++++
 1 file changed, 114 insertions(+)

diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index dc6a8e102cdc..1644f8a9b2a2 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -19,6 +19,7 @@
 #include <linux/iommu.h>
 #include <linux/amd-iommu.h>
 #include <linux/nospec.h>
+#include <linux/workqueue.h>
 
 #include <asm/sev.h>
 #include <asm/processor.h>
@@ -124,6 +125,19 @@ static void *rmp_bookkeeping __ro_after_init;
 
 static u64 probed_rmp_base, probed_rmp_size;
 
+enum rmpopt_function {
+	RMPOPT_FUNC_VERIFY_AND_REPORT_STATUS,
+	RMPOPT_FUNC_REPORT_STATUS
+};
+
+#define RMPOPT_WORK_TIMEOUT	10000
+
+static struct workqueue_struct *rmpopt_wq;
+static struct delayed_work rmpopt_delayed_work;
+
+static cpumask_t primary_threads_cpumask;
+static phys_addr_t rmpopt_pa_start, rmpopt_pa_end;
+
 static LIST_HEAD(snp_leaked_pages_list);
 static DEFINE_SPINLOCK(snp_leaked_pages_list_lock);
 
@@ -477,6 +491,75 @@ static bool __init setup_rmptable(void)
 	return true;
 }
 
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
+static void rmpopt(void *val)
+{
+	u64 rax = ALIGN_DOWN((u64)val, SZ_1G);
+	u64 rcx = RMPOPT_FUNC_VERIFY_AND_REPORT_STATUS;
+
+	__rmpopt(rax, rcx);
+}
+
+static void rmpopt_work_handler(struct work_struct *work)
+{
+	phys_addr_t pa;
+
+	pr_info("Attempt RMP optimizations on physical address range @1GB alignment [0x%016llx - 0x%016llx]\n",
+		rmpopt_pa_start, rmpopt_pa_end);
+
+	/*
+	 * RMPOPT optimizations skip RMP checks at 1GB granularity if this
+	 * range of memory does not contain any SNP guest memory. Optimize
+	 * each range on one CPU first, then let other CPUs execute RMPOPT
+	 * in parallel so they can skip most work as the range has already
+	 * been optimized.
+	 */
+
+	cpumask_clear_cpu(smp_processor_id(), &primary_threads_cpumask);
+
+	/* current CPU */
+	for (pa = rmpopt_pa_start; pa < rmpopt_pa_end; pa += SZ_1G)
+		rmpopt((void *)pa);
+
+	for (pa = rmpopt_pa_start; pa < rmpopt_pa_end; pa += SZ_1G) {
+		on_each_cpu_mask(&primary_threads_cpumask, rmpopt,
+				 (void *)pa, true);
+
+		 /* Give a chance for other threads to run */
+		cond_resched();
+
+	}
+
+	cpumask_set_cpu(smp_processor_id(), &primary_threads_cpumask);
+}
+
+static void rmpopt_all_physmem(bool early)
+{
+	if (!rmpopt_wq)
+		return;
+
+	if (early)
+		queue_delayed_work(rmpopt_wq, &rmpopt_delayed_work,
+				   msecs_to_jiffies(1));
+	else
+		queue_delayed_work(rmpopt_wq, &rmpopt_delayed_work,
+				   msecs_to_jiffies(RMPOPT_WORK_TIMEOUT));
+}
+
 static __init void configure_and_enable_rmpopt(void)
 {
 	phys_addr_t pa_start = ALIGN_DOWN(PFN_PHYS(min_low_pfn), SZ_1G);
@@ -499,6 +582,37 @@ static __init void configure_and_enable_rmpopt(void)
 	 */
 	for_each_online_cpu(cpu)
 		wrmsrq_on_cpu(cpu, MSR_AMD64_RMPOPT_BASE, rmpopt_base);
+
+	/*
+	 * Create an RMPOPT-specific workqueue to avoid scheduling
+	 * RMPOPT workitem on the global system workqueue.
+	 */
+	rmpopt_wq = alloc_workqueue("rmpopt_wq", WQ_UNBOUND, 1);
+	if (!rmpopt_wq)
+		return;
+
+	INIT_DELAYED_WORK(&rmpopt_delayed_work, rmpopt_work_handler);
+
+	rmpopt_pa_start = pa_start;
+	rmpopt_pa_end = ALIGN(PFN_PHYS(max_pfn), SZ_1G);
+
+	/* Limit memory scanning to the first 2 TB of RAM */
+	if ((rmpopt_pa_end - rmpopt_pa_start) > SZ_2T)
+		rmpopt_pa_end = rmpopt_pa_start + SZ_2T;
+
+	/* Only one thread per core needs to issue RMPOPT instruction */
+	for_each_online_cpu(cpu) {
+		if (!topology_is_primary_thread(cpu))
+			continue;
+
+		cpumask_set_cpu(cpu, &primary_threads_cpumask);
+	}
+
+	/*
+	 * Once all per-CPU RMPOPT tables have been configured, enable RMPOPT
+	 * optimizations on all physical memory.
+	 */
+	rmpopt_all_physmem(TRUE);
 }
 
 /*

---

## [4] Ashish Kalra — 2026-03-30
*Subject: [PATCH v3 4/6] x86/sev: Add interface to re-enable RMP optimizations.*

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
index 1644f8a9b2a2..784c0e79200e 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -1138,6 +1138,23 @@ int rmp_make_shared(u64 pfn, enum pg_level level)
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
+	rmpopt_all_physmem(FALSE);
+
+	return 0;
+}
+EXPORT_SYMBOL_GPL(snp_perform_rmp_optimization);
+
 void __snp_leak_pages(u64 pfn, unsigned int npages, bool dump_rmp)
 {
 	struct page *page = pfn_to_page(pfn);
diff --git a/drivers/crypto/ccp/sev-dev.c b/drivers/crypto/ccp/sev-dev.c
index aebf4dad545e..0cbe828d204c 100644
--- a/drivers/crypto/ccp/sev-dev.c
+++ b/drivers/crypto/ccp/sev-dev.c
@@ -1476,6 +1476,10 @@ static int __sev_snp_init_locked(int *error, unsigned int max_snp_asid)
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

## [5] Ashish Kalra — 2026-03-30
*Subject: [PATCH v3 5/6] KVM: SEV: Perform RMP optimizations on SNP guest shutdown*

From: Ashish Kalra <ashish.kalra@amd.com>

As SNP guests are launched, pages converted to private cause RMPUPDATE
to disable the corresponding RMPOPT optimizations.

Conversely, during SNP guest termination, when guest pages are
converted back to shared and are not assigned, RMPOPT will be used
to re-enable RMP optimizations.

RMP optimizations are performed asynchronously by queuing work on a
dedicated workqueue with a delay.

Delaying work allows batching of multiple SNP guest terminations.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/kvm/svm/sev.c | 2 ++
 1 file changed, 2 insertions(+)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 3f9c1aa39a0a..2ad4727c4177 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2942,6 +2942,8 @@ void sev_vm_destroy(struct kvm *kvm)
 	if (sev_snp_guest(kvm)) {
 		snp_guest_req_cleanup(kvm);
 
+		snp_perform_rmp_optimization();
+
 		/*
 		 * Decomission handles unbinding of the ASID. If it fails for
 		 * some unexpected reason, just leak the ASID.

---

## [6] Ashish Kalra — 2026-03-30
*Subject: [PATCH v3 6/6] x86/sev: Add debugfs support for RMPOPT*

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
index 784c0e79200e..04d905894408 100644
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
 
+static cpumask_t rmpopt_cpumask;
+static struct dentry *rmpopt_debugfs;
+
+struct seq_paddr {
+	phys_addr_t next_seq_paddr;
+};
+
 #undef pr_fmt
 #define pr_fmt(fmt)	"SEV-SNP: " fmt
 
@@ -500,6 +509,8 @@ static inline bool __rmpopt(u64 rax, u64 rcx)
 		     : "a" (rax), "c" (rcx)
 		     : "memory", "cc");
 
+	assign_cpu(smp_processor_id(), &rmpopt_cpumask, optimized);
+
 	return optimized;
 }
 
@@ -514,6 +525,17 @@ static void rmpopt(void *val)
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
 static void rmpopt_work_handler(struct work_struct *work)
 {
 	phys_addr_t pa;
@@ -560,6 +582,89 @@ static void rmpopt_all_physmem(bool early)
 				   msecs_to_jiffies(RMPOPT_WORK_TIMEOUT));
 }
 
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
+	cpumask_clear(&rmpopt_cpumask);
+	on_each_cpu_mask(cpu_online_mask, rmpopt_report_status,
+			 (void *)*curr_paddr, true);
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
+	rmpopt_debugfs = debugfs_create_dir("rmpopt", arch_debugfs_dir);
+
+	debugfs_create_file("rmpopt-table", 0444, rmpopt_debugfs,
+			    NULL, &rmpopt_table_fops);
+}
+
 static __init void configure_and_enable_rmpopt(void)
 {
 	phys_addr_t pa_start = ALIGN_DOWN(PFN_PHYS(min_low_pfn), SZ_1G);
@@ -613,6 +718,8 @@ static __init void configure_and_enable_rmpopt(void)
 	 * optimizations on all physical memory.
 	 */
 	rmpopt_all_physmem(TRUE);
+
+	rmpopt_debugfs_setup();
 }
 
 /*

---

## [7] Dave Hansen — 2026-03-30
*Subject: Re: [PATCH v3 2/6] x86/sev: Add support for enabling RMPOPT*

On 3/30/26 15:26, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Isn't the Subject: more appropriately something like:

	x86/sev: Initialize RMPOPT configuration MSRs
The subject is too generic as-is.

> diff --git a/arch/x86/include/asm/msr-index.h b/arch/x86/include/asm/msr-index.h
> index be3e3cc963b2..9c8a6dfd7891 100644

Nit: just "setup_rmpopt()" would be fine, IMNHO. We have plenty of
"setup_foo()" functions that configure and enable CPU features.

> +	phys_addr_t pa_start = ALIGN_DOWN(PFN_PHYS(min_low_pfn), SZ_1G);
> +	u64 rmpopt_base = pa_start | MSR_AMD64_RMPOPT_ENABLE;

With those nits fixed:

Reviewed-by: Dave Hansen <dave.hansen@linux.intel.com>

---

## [8] Dave Hansen — 2026-03-30
*Subject: Re: [PATCH v3 3/6] x86/sev: Add support to perform RMP optimizations
 asynchronously*

On 3/30/26 15:26, Ashish Kalra wrote:
...
> As SEV-SNP is enabled by default on boot when an RMP table is
> allocated by BIOS, the hypervisor and non-SNP guests are subject to

This is a long-winded way of saying:

	When SEV-SNP is enabled, all writes to memory are checked to
	ensure integrity of SNP guest memory. This imposes performance
	overhead on the whole system.

> RMPOPT is a new instruction that minimizes the performance overhead of
> RMP checks on the hypervisor and on non-SNP guests by allowing RMP

Gah, does it really do this _every_ 10 seconds? Whether or not any
guests are running or if the SEV-SNP state has changed at *all*? This
code doesn't implement that, right? If so, why mention it here?

> +static void rmpopt_work_handler(struct work_struct *work)
> +{

This comment could be much more clear.

First, the granularity has *zero* to do with this optimization.

Second, the optimization this code is doing only makes sense if the RMP
itself is caching the RMPOPT result in a global, single place. That's
not explained. It needs something like:

	RMPOPT does three things: It scans the RMP table, stores the
	result of the scan in the global RMP table and copies that
	result to a per-CPU table. The scan is the most expensive part.
	If a second RMPOPT occurs, it can skip the expensive scan if it
	sees the "cached" scan result in the RMP.

	Do RMPOPT on one CPU alone. Then, follow that up with RMPOPT
	on every other primary thread. This potentially allows the
	followers to use the "cached" scan results to avoid repeating
	full scans.

> +	cpumask_clear_cpu(smp_processor_id(), &primary_threads_cpumask);

How do you know that the current CPU is *in* 'primary_threads_cpumask'
in the first place? I guess it doesn't hurt to do RMPOPT in two places,
but why not just be careful about it?

Also, logically, 'primary_threads_cpumask' never changes (modulo CPU
hotplug). The thing you're tracking here is "primary CPUs that need to
have RMPOPT executed on them". That's a far different thing than the
name for the variable.

> +	/* current CPU */
> +	for (pa = rmpopt_pa_start; pa < rmpopt_pa_end; pa += SZ_1G)

This _looks_ rather wonky because it's casting a 'pa' to a virtual
address for no apparent reason.

Also, rmpopt() itself does 1G alignment. This code ^ also aligns the
start and end. Why?

> +	for (pa = rmpopt_pa_start; pa < rmpopt_pa_end; pa += SZ_1G) {
> +		on_each_cpu_mask(&primary_threads_cpumask, rmpopt,

Honestly, I _really_ wish this series would dispense with *all* the
optimizations in the first version. This looks really wonky because
'primary_threads_cpumask' is a global variable and is initialized before
the work function when it could probably be done within the work function.

It's also *really* generically and non-descriptively named for a
global-scope variable.

> +static void rmpopt_all_physmem(bool early)
> +{

This is rather unfortunate on several levels.

First, even if the 'bool early' thing was a good idea, this should be
written:

	unsigned long timeout = RMPOPT_WORK_TIMEOUT;

	if (early)
		timeout = 1;
	
	queue_delayed_work(rmpopt_wq,
			   &rmpopt_delayed_work,			
			   msecs_to_jiffies(timeout));

But, really, why does it even *need* a bool for early/late? Just do a
late_initcall() if you want this done near boot time.


>  static __init void configure_and_enable_rmpopt(void)
>  {

What is the scope of MSR_AMD64_RMPOPT_BASE? Can you have it enabled on
one thread and not the other? Could they be different values both for
enabling and the rmpopt_base value?

If it's not per-thread, then why is it being initialized for each thread?

> +	/*
> +	 * Create an RMPOPT-specific workqueue to avoid scheduling

I'd probably just put this first. Then if the allocation fails, you
don't even bother doing the WRMSRs. Heck if you did that, you could even
use the MSR bit for the indicator of if RMPOPT is supported.

> +	INIT_DELAYED_WORK(&rmpopt_delayed_work, rmpopt_work_handler);
> +

Why is there a 'rmpopt_pa_start' and 'pa_start'?

> +	rmpopt_pa_end = ALIGN(PFN_PHYS(max_pfn), SZ_1G);
> +

---

## [9] Dave Hansen — 2026-03-30
*Subject: Re: [PATCH v3 4/6] x86/sev: Add interface to re-enable RMP
 optimizations.*

The subject seems rather imprecise. This both adds a function to
"re-enable RMP optimizations" *AND* calls it.

> RMPOPT table is a per-processor table which indicates if 1GB regions of
> physical memory are entirely hypervisor-owned or not.

It's per-core, right? Why not just be precise about it?

> When performing host memory accesses in hypervisor mode as well as
> non-SNP guest mode, the processor may consult the RMPOPT table to


> +int snp_perform_rmp_optimization(void)
> +{

This seems wrong. How about we just make 'X86_FEATURE_RMPOPT' the one
true source of RMP support?

If you don't have CC_ATTR_HOST_SEV_SNP you:

	setup_clear_cpu_cap(X86_FEATURE_RMPOPT)

Ditto for MSR_AMD64_SEG_RMP_ENABLED.

It could also potentially replace the 'rmpopt_wq' checks.

> +	rmpopt_all_physmem(FALSE);
> +

Ahhh, so this isn't happening at boot, it happens when kvm_amd.ko gets
loaded? That escaped me until now. It would be nice to mention
somewhere, please.

There is basically no naming difference between
snp_perform_rmp_optimization() and rmpopt_all_physmem(). Can you just
get this all down to a single function, please?

If you really have a reason to have a scan now and scan later mode, just
do this:

	rmpopt_all_physmem(RMPOPT_SCAN_NOW);

and:

	rmpopt_all_physmem(RMPOPT_SCAN_LATER);

*That* function can do the X86_FEATURE_RMPOPT check.

---

## [10] Dave Hansen — 2026-03-30
*Subject: Re: [PATCH v3 5/6] KVM: SEV: Perform RMP optimizations on SNP guest
 shutdown*

On 3/30/26 15:27, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

This is all super passive. It makes it impossible to tell what is
background versus imperative voice on what the patch is doing.

	== Background / Problem ==

	Pages are converted from shared to private as SNP guests are
	launched. This destroys existing RMPOPT optimizations in the
	regions where pages are converted.

	Conversely, guest pages are converted back to shared during SNP
	guest termination and their region may become eligible for
	RMPOPT optimization.

	== Solution ==

	To take advantage of this, perform RMPOPT after guest
	termination. Do it after a delay so that a single RMPOPT pass
	can be done if multiple guests terminate in a short period of
	time.
	
With a fixed changelog:

Acked-by: Dave Hansen <dave.hansen@linux.intel.com>

I'm just saying "ack" on this one because it's a pretty KVM-specific
thing about when the guest is destroyed to the point of being good for
RMPOPT. This needs many more eyeballs from the KVM folks than me.

---

## [11] Kalra, Ashish — 2026-03-30
*Subject: Re: [PATCH v3 3/6] x86/sev: Add support to perform RMP optimizations
 asynchronously*

On 3/30/2026 6:22 PM, Dave Hansen wrote:
> On 3/30/26 15:26, Ashish Kalra wrote:
> ...

Ok, i will name it more appropriately.

> 
>> +	/* current CPU */

This is re-using the rmpopt() wrapper, which exists for using the
on_each_cpu_mask() call below, and that needs the "void *' parameter. 

The on_each_cpu_mask() is needed to execute RMPOPT instructions in
parallel, as that is part of the bare minimum optimizations needed
for the RMPOPT loop.

I will add another wrapper for calling rmpopt() with the 'pa'
parameter directly.

> 
> Also, rmpopt() itself does 1G alignment. This code ^ also aligns the

Yes, RMPOPT instruction does 1G alignment on the specified PA, this code
alignment is to ensure the PFNs - min_low_pfn and max_pfn are aligned
appropriately.

> 
>> +	for (pa = rmpopt_pa_start; pa < rmpopt_pa_end; pa += SZ_1G) {

It is static and will never change, so i was doing it here outside the work function, 
but i can move it inside the work function.

> It's also *really* generically and non-descriptively named for a
> global-scope variable.

I can name it appropriately. 

I definitely want to have the bare minimum set of optimizations for the RMPOPT loop
in place for the first series of patches, which is:  

1). Issuing RMPOPT on one only one CPU first, before doing it in parallel on
all other CPUs. 

2). Issuing RMPOPT on only one thread per core.

This is the bare minimum set of optimizations for RMPOPT loop, for which
i had the performance numbers computed before: 

Best runtime for the RMPOPT loop:
When RMPOPT exits early as it finds an assigned page on the first RMP entry it checks in the 1GB -> ~95ms.

Worst runtime for the RMPOPT loop:
When RMPOPT does not find any assigned page in the full 1GB range it is checking -> ~311ms.

The following series will have support for system RAM > 2TB and other optimizations, but 
these bare minimum set of optimizations for RMPOPT should definitely be part of initial 
patch series.

>> +static void rmpopt_all_physmem(bool early)
>> +{

Ok.

> 
>>  static __init void configure_and_enable_rmpopt(void)

Only one logical thread per core needs to set RMPOPT_BASE MSR as it is per-core,
so i will use the "primary_threads_cpumask" here to use it for programming this
MSR.

Just another reason, to set the "primary_threads_cpumask" here in this function 
and then re-use it for the RMPOPT worker.

>> +	/*
>> +	 * Create an RMPOPT-specific workqueue to avoid scheduling

Ok.

> 
>> +	INIT_DELAYED_WORK(&rmpopt_delayed_work, rmpopt_work_handler);

Again, just statically setting the 'rmpopt_pa_start' for the RMPOPT worker,
but i can just use 'rmpopt_pa_start' here. 

Thanks,
Ashish

> 
>> +	rmpopt_pa_end = ALIGN(PFN_PHYS(max_pfn), SZ_1G);

---

## [12] Kalra, Ashish — 2026-03-30
*Subject: Re: [PATCH v3 4/6] x86/sev: Add interface to re-enable RMP
 optimizations.*

On 3/30/2026 6:33 PM, Dave Hansen wrote:
> The subject seems rather imprecise. This both adds a function to
> "re-enable RMP optimizations" *AND* calls it.

Ok.
 
>> When performing host memory accesses in hypervisor mode as well as
>> non-SNP guest mode, the processor may consult the RMPOPT table to

 
Ok, i will work on that.

> If you don't have CC_ATTR_HOST_SEV_SNP you:
> 

Well, as of now, it is happening at both boot time and here after SNP_INIT_EX,
as SNP_INIT clears the RMPOPT table contents to 0, but eventually, when SNP enable
is moved completely out of snp_rmptable_init() and only done when kvm_amd.ko
gets loaded, then it will only happen here.

Eventually, call to "configure_and_enable_rmpopt()" (setup_rmpopt()) will move out
of snp_rmptable_init() and get called from here.

> 
> There is basically no naming difference between

The only thing is that this is an exported function out of the x86 platform
code, so will probably need to be renamed as snp_rmpopt_all_physmem().

Thanks,
Ashish

---

## [13] Kalra, Ashish — 2026-04-01
*Subject: Re: [PATCH v3 3/6] x86/sev: Add support to perform RMP optimizations
 asynchronously*

Hello Dave,

On 3/30/2026 7:46 PM, Kalra, Ashish wrote:
> 
> On 3/30/2026 6:22 PM, Dave Hansen wrote:

>>
>>>  static __init void configure_and_enable_rmpopt(void)

Coming back to this ...

For using the "primary_thread_cpumask" i will need to use something like
on_each_cpu_mask() similar to what i was doing in v2.

In v2, i was programming the RMPOPT_BASE MSR using on_each_cpu_mask(),
that required using a callback function to do the WRMSR: 

+static void __configure_rmpopt(void *val)
+{
+       u64 rmpopt_base = ((u64)val & PUD_MASK) | MSR_AMD64_RMPOPT_ENABLE;
+
+       wrmsrq(MSR_AMD64_RMPOPT_BASE, rmpopt_base);
+}
+

+       on_each_cpu_mask(cpu_online_mask, __configure_rmpopt, (void *)pa_start, true);


But, that required using the (void *) casting, which you objected to and you 
suggested the use of for_each_online_cpu() and wrmsrq_on_cpu(), and i has replied
that i need to do it (only) once on each thread per core, and that's why i may need
to use on_each_cpu_mask() and then you had suggested that if you *need* performance  
then i can implement/add something like wrmsrq_on_cpumask(). 

For programming the RMPOPT_BASE MSR performance is not really that important as 
it is for issuing the RMPOPT instruction on only thread per core, and as we are
programming the RMPOPT_BASE MSRs on all CPUs/threads to the same (starting) physical
address to support all RAM up-to 2TB for RMP optimizations, therefore, i don't
think it is that critical to implement wrmsrq_on_cpumask() and instead we can continue
to program the RMPOPT_BASE MSR on all CPUs (threads).

Thanks,
Ashish

---

## [14] Dave Hansen — 2026-04-01
*Subject: Re: [PATCH v3 3/6] x86/sev: Add support to perform RMP optimizations
 asynchronously*

On 4/1/26 08:47, Kalra, Ashish wrote:
> For programming the RMPOPT_BASE MSR performance is not really that
> important as it is for issuing the RMPOPT instruction on only thread
I don't mean to be a grammar pedant. But, man, that's hard to parse when
written as a single sentence.

I'm also not quite sure what the resistance is to going and adding the
precise function that is needed:

int wrmsrq_on_cpus(const struct cpumask *mask, u32 msr_no, u64 q)
{
        int err;
        struct msr_info rv;

        memset(&rv, 0, sizeof(rv));

        rv.msr_no = msr_no;
        rv.reg.q = q;

        err = smp_call_function_many(mask, __wrmsr_on_cpu, &rv, 1);

        return err;
}
EXPORT_SYMBOL(wrmsrq_on_cpus);

It's just wrmsrq_on_cpu(), replace the 'cpu' with a cpumask and
s/_single/_many/. I think. Unless I'm missing something.

---

## [15] Kalra, Ashish — 2026-04-08
*Subject: Re: [PATCH v3 4/6] x86/sev: Add interface to re-enable RMP
 optimizations.*

Hello Dave,

On 3/30/2026 6:33 PM, Dave Hansen wrote:

>> +int snp_perform_rmp_optimization(void)
>> +{

Following up on this ...

It is straightforward to clear X86_FEATURE_RMPOPT if the RMPOPT setup
function (that is, configure and enable RMPOPT function) gets called, but 
if CC_ATTR_HOST_SEV_SNP is not set, then __sev_snp_init_locked() (CCP module)
does not invoke the RMPOPT setup function. 

And then as this function snp_perform_rmp_optimization() is an external
API, it needs to check for both CC_ATTR_HOST_SEV_SNP and MSR_AMD64_SEG_RMP_ENABLED.

Otherwise, we will need to clear X86_FEATURE_RMPOPT, wherever CC_ATTR_HOST_SEV_SNP
is cleared all across call sites like the AMD IOMMU driver, 
AMD SVM-SEV command line parsing support code and AMD CPU detection and BSP init
code.

And for clearing X86_FEATURE_RMPOPT, if MSR_AMD64_SEG_RMP_ENABLED is not set, 
the support will need to be added in setup_rmptable().

It is much more straightforward to check for both CC_ATTR_HOST_SEV_SNP and
MSR_AMD64_SEG_RMP_ENABLED in this API function itself.

Thanks,
Ashish

---

## [16] Dave Hansen — 2026-04-08
*Subject: Re: [PATCH v3 4/6] x86/sev: Add interface to re-enable RMP
 optimizations.*

On 4/8/26 12:32, Kalra, Ashish wrote:
> It is much more straightforward to check for both
> CC_ATTR_HOST_SEV_SNP and MSR_AMD64_SEG_RMP_ENABLED in this API

I kinda think it's not straightforward. That's why I'd like to see the
checks consolidated.

It's may take a wee bit of refactoring, but I think it's totally doable.

---
