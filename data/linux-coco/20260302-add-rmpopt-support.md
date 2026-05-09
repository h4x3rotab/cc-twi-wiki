---
title: 'Add RMPOPT support.'
date: 2026-03-02
last_reply: 2026-03-30
message_count: 42
participants: ['Ashish Kalra', 'Dave Hansen', 'Sean Christopherson', 'Andrew Cooper', 'Borislav Petkov', 'Tom Lendacky', 'Ackerley Tng']
---

## [1] Ashish Kalra — 2026-03-02

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
technical documentation. [1]

As SNP is enabled by default the hypervisor and non-SNP guests are
subject to RMP write checks to provide integrity of SNP guest memory.

This patch-series adds support to enable RMP optimizations for up to
2TB of system RAM across the system and allow RMPUPDATE to disable
those optimizations as SNP guests are launched.

Support for RAM larger than 2 TB will be added in follow-on series.

This series also introduces a new guest_memfd cleanup interface for
guest teardown, in case of SEV-SNP this interface is used to re-enable
RMP optimizations during guest shutdown and/or termination.

Once 1GB hugetlb guest_memfd support is merged, support for 
re-enabling RMPOPT optimizations during 1GB page cleanup will be added
in follow-on series.

Additionally add debugfs interface to report per-CPU RMPOPT status
across all system RAM.


[1] https://docs.amd.com/v/u/en-US/69201_1.00_AMD64_RMPOPT_PUB 

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
  x86/sev: add support for enabling RMPOPT
  x86/sev: add support for RMPOPT instruction
  x86/sev: Add interface to re-enable RMP optimizations.
  KVM: guest_memfd: Add cleanup interface for guest teardown
  KVM: SEV: Implement SEV-SNP specific guest cleanup
  x86/sev: Add debugfs support for RMPOPT

 arch/x86/include/asm/cpufeatures.h |   2 +-
 arch/x86/include/asm/kvm-x86-ops.h |   1 +
 arch/x86/include/asm/kvm_host.h    |   1 +
 arch/x86/include/asm/msr-index.h   |   3 +
 arch/x86/include/asm/sev.h         |   2 +
 arch/x86/kernel/cpu/scattered.c    |   1 +
 arch/x86/kvm/Kconfig               |   1 +
 arch/x86/kvm/svm/sev.c             |   9 ++
 arch/x86/kvm/svm/svm.c             |   1 +
 arch/x86/kvm/svm/svm.h             |   2 +
 arch/x86/kvm/x86.c                 |   7 +
 arch/x86/virt/svm/sev.c            | 231 +++++++++++++++++++++++++++++
 drivers/crypto/ccp/sev-dev.c       |   4 +
 include/linux/kvm_host.h           |   4 +
 virt/kvm/Kconfig                   |   4 +
 virt/kvm/guest_memfd.c             |   8 +
 16 files changed, 280 insertions(+), 1 deletion(-)

---

## [2] Ashish Kalra — 2026-03-02
*Subject: [PATCH v2 1/7] x86/cpufeatures: Add X86_FEATURE_AMD_RMPOPT feature flag*

From: Ashish Kalra <ashish.kalra@amd.com>

Add a flag indicating whether RMPOPT instruction is supported.

RMPOPT is a new instruction designed to minimize the performance
overhead of RMP checks on the hypervisor and on non-SNP guests by
allowing RMP checks to be skipped when 1G regions of memory are known
not to contain any SEV-SNP guest memory.

For more information on the RMPOPT instruction, see the AMD64 RMPOPT
technical documentation. [1]

Link: https://docs.amd.com/v/u/en-US/69201_1.00_AMD64_RMPOPT_PUB [1]
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

## [3] Ashish Kalra — 2026-03-02
*Subject: [PATCH v2 2/7] x86/sev: add support for enabling RMPOPT*

From: Ashish Kalra <ashish.kalra@amd.com>

The new RMPOPT instruction sets bits in a per-CPU RMPOPT table, which
indicates whether specific 1GB physical memory regions contain SEV-SNP
guest memory.

Per-CPU RMPOPT tables support at most 2 TB of addressable memory for
RMP optimizations.

Initialize the per-CPU RMPOPT table base to the starting physical
address. This enables RMP optimization for up to 2 TB of system RAM on
all CPUs.

Suggested-by: Thomas Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/include/asm/msr-index.h |  3 +++
 arch/x86/virt/svm/sev.c          | 37 ++++++++++++++++++++++++++++++++
 2 files changed, 40 insertions(+)

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
index a4f3a364fb65..405199c2f563 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -500,6 +500,41 @@ static bool __init setup_rmptable(void)
 	}
 }
 
+static void __configure_rmpopt(void *val)
+{
+	u64 rmpopt_base = ((u64)val & PUD_MASK) | MSR_AMD64_RMPOPT_ENABLE;
+
+	wrmsrq(MSR_AMD64_RMPOPT_BASE, rmpopt_base);
+}
+
+static __init void configure_and_enable_rmpopt(void)
+{
+	phys_addr_t pa_start = ALIGN_DOWN(PFN_PHYS(min_low_pfn), PUD_SIZE);
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
+	/*
+	 * Per-CPU RMPOPT tables support at most 2 TB of addressable memory for RMP optimizations.
+	 *
+	 * Set per-core RMPOPT base to min_low_pfn to enable RMP optimization for
+	 * up to 2TB of system RAM on all CPUs.
+	 */
+	on_each_cpu_mask(cpu_online_mask, __configure_rmpopt, (void *)pa_start, true);
+}
+
 /*
  * Do the necessary preparations which are verified by the firmware as
  * described in the SNP_INIT_EX firmware command description in the SNP
@@ -555,6 +590,8 @@ int __init snp_rmptable_init(void)
 skip_enable:
 	cpuhp_setup_state(CPUHP_AP_ONLINE_DYN, "x86/rmptable_init:online", __snp_enable, NULL);
 
+	configure_and_enable_rmpopt();
+
 	/*
 	 * Setting crash_kexec_post_notifiers to 'true' to ensure that SNP panic
 	 * notifier is invoked to do SNP IOMMU shutdown before kdump.

---

## [4] Ashish Kalra — 2026-03-02
*Subject: [PATCH v2 3/7] x86/sev: add support for RMPOPT instruction*

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
 arch/x86/virt/svm/sev.c | 78 +++++++++++++++++++++++++++++++++++++++++
 1 file changed, 78 insertions(+)

diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
index 405199c2f563..c99270dfe3b3 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -19,6 +19,7 @@
 #include <linux/iommu.h>
 #include <linux/amd-iommu.h>
 #include <linux/nospec.h>
+#include <linux/kthread.h>
 
 #include <asm/sev.h>
 #include <asm/processor.h>
@@ -122,6 +123,13 @@ static u64 rmp_cfg;
 
 static u64 probed_rmp_base, probed_rmp_size;
 
+enum rmpopt_function {
+	RMPOPT_FUNC_VERIFY_AND_REPORT_STATUS,
+	RMPOPT_FUNC_REPORT_STATUS
+};
+
+static struct task_struct *rmpopt_task;
+
 static LIST_HEAD(snp_leaked_pages_list);
 static DEFINE_SPINLOCK(snp_leaked_pages_list_lock);
 
@@ -500,6 +508,61 @@ static bool __init setup_rmptable(void)
 	}
 }
 
+/*
+ * 'val' is a system physical address aligned to 1GB OR'ed with
+ * a function selection. Currently supported functions are 0
+ * (verify and report status) and 1 (report status).
+ */
+static void rmpopt(void *val)
+{
+	asm volatile(".byte 0xf2, 0x0f, 0x01, 0xfc"
+		     : : "a" ((u64)val & PUD_MASK), "c" ((u64)val & 0x1)
+		     : "memory", "cc");
+}
+
+static int rmpopt_kthread(void *__unused)
+{
+	phys_addr_t pa_start, pa_end;
+
+	pa_start = ALIGN_DOWN(PFN_PHYS(min_low_pfn), PUD_SIZE);
+	pa_end = ALIGN(PFN_PHYS(max_pfn), PUD_SIZE);
+
+	/* Limit memory scanning to the first 2 TB of RAM */
+	pa_end = (pa_end - pa_start) <= SZ_2T ? pa_end : pa_start + SZ_2T;
+
+	while (!kthread_should_stop()) {
+		phys_addr_t pa;
+
+		pr_info("RMP optimizations enabled on physical address range @1GB alignment [0x%016llx - 0x%016llx]\n",
+			pa_start, pa_end);
+
+		/*
+		 * RMPOPT optimizations skip RMP checks at 1GB granularity if this range of
+		 * memory does not contain any SNP guest memory.
+		 */
+		for (pa = pa_start; pa < pa_end; pa += PUD_SIZE) {
+			/* Bit zero passes the function to the RMPOPT instruction. */
+			on_each_cpu_mask(cpu_online_mask, rmpopt,
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
@@ -533,6 +596,21 @@ static __init void configure_and_enable_rmpopt(void)
 	 * up to 2TB of system RAM on all CPUs.
 	 */
 	on_each_cpu_mask(cpu_online_mask, __configure_rmpopt, (void *)pa_start, true);
+
+	rmpopt_task = kthread_create(rmpopt_kthread, NULL, "rmpopt_kthread");
+	if (IS_ERR(rmpopt_task)) {
+		pr_warn("Unable to start RMPOPT kernel thread\n");
+		rmpopt_task = NULL;
+		return;
+	}
+
+	pr_info("RMPOPT worker thread created with PID %d\n", task_pid_nr(rmpopt_task));
+
+	/*
+	 * Once all per-CPU RMPOPT tables have been configured, enable RMPOPT
+	 * optimizations on all physical memory.
+	 */
+	rmpopt_all_physmem();
 }
 
 /*

---

## [5] Ashish Kalra — 2026-03-02
*Subject: [PATCH v2 4/7] x86/sev: Add interface to re-enable RMP optimizations.*

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
index c99270dfe3b3..4dd5a525ad32 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -1144,6 +1144,23 @@ int rmp_make_shared(u64 pfn, enum pg_level level)
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
index 096f993974d1..d84178a232e0 100644
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

## [6] Ashish Kalra — 2026-03-02
*Subject: [PATCH v2 5/7] KVM: guest_memfd: Add cleanup interface for guest teardown*

From: Ashish Kalra <ashish.kalra@amd.com>

Introduce kvm_arch_gmem_cleanup() to perform architecture-specific
cleanups when the last file descriptor for the guest_memfd inode is
closed. This typically occurs during guest shutdown and termination
and allows for final resource release.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/include/asm/kvm-x86-ops.h | 1 +
 arch/x86/include/asm/kvm_host.h    | 1 +
 arch/x86/kvm/x86.c                 | 7 +++++++
 include/linux/kvm_host.h           | 4 ++++
 virt/kvm/Kconfig                   | 4 ++++
 virt/kvm/guest_memfd.c             | 8 ++++++++
 6 files changed, 25 insertions(+)

diff --git a/arch/x86/include/asm/kvm-x86-ops.h b/arch/x86/include/asm/kvm-x86-ops.h
index de709fb5bd76..ebbecd0c9e4f 100644
--- a/arch/x86/include/asm/kvm-x86-ops.h
+++ b/arch/x86/include/asm/kvm-x86-ops.h
@@ -148,6 +148,7 @@ KVM_X86_OP_OPTIONAL(alloc_apic_backing_page)
 KVM_X86_OP_OPTIONAL_RET0(gmem_prepare)
 KVM_X86_OP_OPTIONAL_RET0(gmem_max_mapping_level)
 KVM_X86_OP_OPTIONAL(gmem_invalidate)
+KVM_X86_OP_OPTIONAL(gmem_cleanup)
 
 #undef KVM_X86_OP
 #undef KVM_X86_OP_OPTIONAL
diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index ff07c45e3c73..7894cf791fef 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -1962,6 +1962,7 @@ struct kvm_x86_ops {
 	int (*gmem_prepare)(struct kvm *kvm, kvm_pfn_t pfn, gfn_t gfn, int max_order);
 	void (*gmem_invalidate)(kvm_pfn_t start, kvm_pfn_t end);
 	int (*gmem_max_mapping_level)(struct kvm *kvm, kvm_pfn_t pfn, bool is_private);
+	void (*gmem_cleanup)(void);
 };
 
 struct kvm_x86_nested_ops {
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 3fb64905d190..d992848942c3 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -14080,6 +14080,13 @@ void kvm_arch_gmem_invalidate(kvm_pfn_t start, kvm_pfn_t end)
 	kvm_x86_call(gmem_invalidate)(start, end);
 }
 #endif
+
+#ifdef CONFIG_HAVE_KVM_ARCH_GMEM_CLEANUP
+void kvm_arch_gmem_cleanup(void)
+{
+	kvm_x86_call(gmem_cleanup)();
+}
+#endif
 #endif
 
 int kvm_spec_ctrl_test_value(u64 value)
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index dde605cb894e..b14143c427eb 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -2607,6 +2607,10 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t gfn, void __user *src, long npages
 void kvm_arch_gmem_invalidate(kvm_pfn_t start, kvm_pfn_t end);
 #endif
 
+#ifdef CONFIG_HAVE_KVM_ARCH_GMEM_CLEANUP
+void kvm_arch_gmem_cleanup(void);
+#endif
+
 #ifdef CONFIG_KVM_GENERIC_PRE_FAULT_MEMORY
 long kvm_arch_vcpu_pre_fault_memory(struct kvm_vcpu *vcpu,
 				    struct kvm_pre_fault_memory *range);
diff --git a/virt/kvm/Kconfig b/virt/kvm/Kconfig
index 267c7369c765..9072ec12d5e7 100644
--- a/virt/kvm/Kconfig
+++ b/virt/kvm/Kconfig
@@ -125,3 +125,7 @@ config HAVE_KVM_ARCH_GMEM_INVALIDATE
 config HAVE_KVM_ARCH_GMEM_POPULATE
        bool
        depends on KVM_GUEST_MEMFD
+
+config HAVE_KVM_ARCH_GMEM_CLEANUP
+       bool
+       depends on KVM_GUEST_MEMFD
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 017d84a7adf3..2724dd1099f2 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -955,6 +955,14 @@ static void kvm_gmem_destroy_inode(struct inode *inode)
 
 static void kvm_gmem_free_inode(struct inode *inode)
 {
+#ifdef CONFIG_HAVE_KVM_ARCH_GMEM_CLEANUP
+	/*
+	 * Finalize cleanup for the inode once the last guest_memfd
+	 * reference is released. This usually occurs after guest
+	 * termination.
+	 */
+	kvm_arch_gmem_cleanup();
+#endif
 	kmem_cache_free(kvm_gmem_inode_cachep, GMEM_I(inode));
 }

---

## [7] Ashish Kalra — 2026-03-02
*Subject: [PATCH v2 6/7] KVM: SEV: Implement SEV-SNP specific guest cleanup*

From: Ashish Kalra <ashish.kalra@amd.com>

Implement the arch-specific cleanup for SEV-SNP via the
kvm_gmem_cleanup() hook. Use this interface to re-enable RMP
optimizations during guest shutdown.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/kvm/Kconfig   | 1 +
 arch/x86/kvm/svm/sev.c | 9 +++++++++
 arch/x86/kvm/svm/svm.c | 1 +
 arch/x86/kvm/svm/svm.h | 2 ++
 4 files changed, 13 insertions(+)

diff --git a/arch/x86/kvm/Kconfig b/arch/x86/kvm/Kconfig
index d916bd766c94..fdfdb7ac6a45 100644
--- a/arch/x86/kvm/Kconfig
+++ b/arch/x86/kvm/Kconfig
@@ -164,6 +164,7 @@ config KVM_AMD_SEV
 	select HAVE_KVM_ARCH_GMEM_PREPARE
 	select HAVE_KVM_ARCH_GMEM_INVALIDATE
 	select HAVE_KVM_ARCH_GMEM_POPULATE
+	select HAVE_KVM_ARCH_GMEM_CLEANUP
 	help
 	  Provides support for launching encrypted VMs which use Secure
 	  Encrypted Virtualization (SEV), Secure Encrypted Virtualization with
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 3f9c1aa39a0a..4c206e9f70cd 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -5109,6 +5109,15 @@ int sev_gmem_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn, bool is_private)
 	return level;
 }
 
+void sev_gmem_cleanup(void)
+{
+	/*
+	 * Re-enable RMP optimizations once all guest pages are
+	 * converted back to shared following guest shutdown.
+	 */
+	snp_perform_rmp_optimization();
+}
+
 struct vmcb_save_area *sev_decrypt_vmsa(struct kvm_vcpu *vcpu)
 {
 	struct vcpu_svm *svm = to_svm(vcpu);
diff --git a/arch/x86/kvm/svm/svm.c b/arch/x86/kvm/svm/svm.c
index 8f8bc863e214..46526ab9ab92 100644
--- a/arch/x86/kvm/svm/svm.c
+++ b/arch/x86/kvm/svm/svm.c
@@ -5260,6 +5260,7 @@ struct kvm_x86_ops svm_x86_ops __initdata = {
 	.gmem_prepare = sev_gmem_prepare,
 	.gmem_invalidate = sev_gmem_invalidate,
 	.gmem_max_mapping_level = sev_gmem_max_mapping_level,
+	.gmem_cleanup = sev_gmem_cleanup,
 };
 
 /*
diff --git a/arch/x86/kvm/svm/svm.h b/arch/x86/kvm/svm/svm.h
index ebd7b36b1ceb..443c29c23a6a 100644
--- a/arch/x86/kvm/svm/svm.h
+++ b/arch/x86/kvm/svm/svm.h
@@ -896,6 +896,7 @@ void sev_handle_rmp_fault(struct kvm_vcpu *vcpu, gpa_t gpa, u64 error_code);
 int sev_gmem_prepare(struct kvm *kvm, kvm_pfn_t pfn, gfn_t gfn, int max_order);
 void sev_gmem_invalidate(kvm_pfn_t start, kvm_pfn_t end);
 int sev_gmem_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn, bool is_private);
+void sev_gmem_cleanup(void);
 struct vmcb_save_area *sev_decrypt_vmsa(struct kvm_vcpu *vcpu);
 void sev_free_decrypted_vmsa(struct kvm_vcpu *vcpu, struct vmcb_save_area *vmsa);
 #else
@@ -928,6 +929,7 @@ static inline int sev_gmem_max_mapping_level(struct kvm *kvm, kvm_pfn_t pfn, boo
 {
 	return 0;
 }
+static inline void sev_gmem_cleanup(void) {}
 
 static inline struct vmcb_save_area *sev_decrypt_vmsa(struct kvm_vcpu *vcpu)
 {

---

## [8] Ashish Kalra — 2026-03-02
*Subject: [PATCH v2 7/7] x86/sev: Add debugfs support for RMPOPT*

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
index 4dd5a525ad32..49bd7ba76169 100644
--- a/arch/x86/virt/svm/sev.c
+++ b/arch/x86/virt/svm/sev.c
@@ -20,6 +20,8 @@
 #include <linux/amd-iommu.h>
 #include <linux/nospec.h>
 #include <linux/kthread.h>
+#include <linux/debugfs.h>
+#include <linux/seq_file.h>
 
 #include <asm/sev.h>
 #include <asm/processor.h>
@@ -135,6 +137,13 @@ static DEFINE_SPINLOCK(snp_leaked_pages_list_lock);
 
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
 
@@ -515,9 +524,14 @@ static bool __init setup_rmptable(void)
  */
 static void rmpopt(void *val)
 {
+	bool optimized;
+
 	asm volatile(".byte 0xf2, 0x0f, 0x01, 0xfc"
-		     : : "a" ((u64)val & PUD_MASK), "c" ((u64)val & 0x1)
+		     : "=@ccc" (optimized)
+		     : "a" ((u64)val & PUD_MASK), "c" ((u64)val & 0x1)
 		     : "memory", "cc");
+
+	assign_cpu(smp_processor_id(), &rmpopt_cpumask, optimized);
 }
 
 static int rmpopt_kthread(void *__unused)
@@ -563,6 +577,89 @@ static void rmpopt_all_physmem(void)
 		wake_up_process(rmpopt_task);
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
+	rmpopt_debugfs = debugfs_create_dir("rmpopt", arch_debugfs_dir);
+
+	debugfs_create_file("rmpopt-table", 0444, rmpopt_debugfs,
+			    NULL, &rmpopt_table_fops);
+}
+
 static void __configure_rmpopt(void *val)
 {
 	u64 rmpopt_base = ((u64)val & PUD_MASK) | MSR_AMD64_RMPOPT_ENABLE;
@@ -611,6 +708,8 @@ static __init void configure_and_enable_rmpopt(void)
 	 * optimizations on all physical memory.
 	 */
 	rmpopt_all_physmem();
+
+	rmpopt_debugfs_setup();
 }
 
 /*

---

## [9] Dave Hansen — 2026-03-02
*Subject: Re: [PATCH v2 2/7] x86/sev: add support for enabling RMPOPT*

On 3/2/26 13:35, Ashish Kalra wrote:
> The new RMPOPT instruction sets bits in a per-CPU RMPOPT table, which
> indicates whether specific 1GB physical memory regions contain SEV-SNP

Honestly, this is an implementation detail that we don't need to know
about in the kernel. It's also not even factually correct. The
instruction _might_ not set any bits, either because there is SEV-SNP
memory or because it's being run in query mode.

	The new RMPOPT instruction helps manage per-CPU RMP optimization
	structures inside the CPU. It takes a 1GB-aligned physical
	address and either returns the status of the optimizations or
	tries to enable the optimizations.

> Per-CPU RMPOPT tables support at most 2 TB of addressable memory for
> RMP optimizations.

The reset looks good.

> diff --git a/arch/x86/include/asm/msr-index.h b/arch/x86/include/asm/msr-index.h
> index da5275d8eda6..8e7da03abd5b 100644

To be honest, I think those two are just plain noise ^^.

> +	if (!(rmp_cfg & MSR_AMD64_SEG_RMP_ENABLED)) {
> +		pr_info("RMPOPT optimizations not enabled, segmented RMP required\n");

Please at least be consistent with your comments. This is both over 80
columns *and* not even consistent in the two sentences.

> +	on_each_cpu_mask(cpu_online_mask, __configure_rmpopt, (void *)pa_start, true);
> +}

What's wrong with:

	u64 rmpopt_base = pa_start | MSR_AMD64_RMPOPT_ENABLE;
	...
	for_each_online_cpu(cpu)
		wrmsrq_on_cpu(cpu, MSR_AMD64_RMPOPT_BASE, rmpopt_base);

Then there's at least no ugly casting.

---

## [10] Dave Hansen — 2026-03-02
*Subject: Re: [PATCH v2 2/7] x86/sev: add support for enabling RMPOPT*

Oh, and:

[PATCH v2 2/7] x86/sev: add support for enabling RMPOPT

		        ^ Capitalize this, please

---

## [11] Kalra, Ashish — 2026-03-02
*Subject: Re: [PATCH v2 2/7] x86/sev: add support for enabling RMPOPT*

Hello Dave,

On 3/2/2026 4:32 PM, Dave Hansen wrote:

>> +static __init void configure_and_enable_rmpopt(void)
>> +{

They are basically pr_debug's, so won't really cause noise generally.

> 
>> +	if (!(rmp_cfg & MSR_AMD64_SEG_RMP_ENABLED)) {

Sure.

> 
>> +	on_each_cpu_mask(cpu_online_mask, __configure_rmpopt, (void *)pa_start, true);

RMOPT_BASE MSRs don't need to be set serially, therefore, by
using the cpu_online_mask and on_each_cpu_mask(), we can setup the MSRs
concurrently and in parallel. Using for_each_online_cpu() will be slower than
doing on_each_cpu_mask() as it doesn't send IPIs in parallel, right.

Thanks,
Ashish

---

## [12] Dave Hansen — 2026-03-02
*Subject: Re: [PATCH v2 3/7] x86/sev: add support for RMPOPT instruction*

That subject could use a wee bit of work.

I'd probably talk about this adding a new kernel thread that does the
optimizations asynchronously.


On 3/2/26 13:36, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

This is heavy on the "what" and light on the "why" and "how".

> diff --git a/arch/x86/virt/svm/sev.c b/arch/x86/virt/svm/sev.c
> index 405199c2f563..c99270dfe3b3 100644

Shouldn't these go by the instruction definition?

You could even call it rmpopt_rcx or something.

> +static struct task_struct *rmpopt_task;
> +

Doesn't this belong in:

arch/x86/include/asm/special_insns.h

Also, it's not reporting *any* status here, right? So why even talk
about it if the kernel isn't doing any status checks? It just makes it
more confusing.

> +static int rmpopt_kthread(void *__unused)
> +{

Needs vertical alignment:

	pa_start = ALIGN_DOWN(PFN_PHYS(min_low_pfn), PUD_SIZE);
	pa_end   = ALIGN(     PFN_PHYS(max_pfn),     PUD_SIZE);

Nit: the architecture says "1GB" regions, not PUD_SIZE. If we ever got
fancy and changed the page tables, this code would break. Why make it
harder on ourselves than it has to be?

> +	/* Limit memory scanning to the first 2 TB of RAM */
> +	pa_end = (pa_end - pa_start) <= SZ_2T ? pa_end : pa_start + SZ_2T;

That's a rather unfortunate use of ternary form. Isn't this a billion
times more clear?

	if (pa_end - pa_start > SZ_2T)
		pa_end = pa_start + SZ_2T;

> +	while (!kthread_should_stop()) {
> +		phys_addr_t pa;

This isn't really enabling optimizations. It's trying to enable them,
right? It might fall on its face and fail every time, right?

> +		/*
> +		 * RMPOPT optimizations skip RMP checks at 1GB granularity if this range of

Could you also put together some proper helpers, please? The
lowest-level helper should look a lot like the instruction reference:

void __rmpopt(u64 rax, u64 rcx)
{
	asm volatile(".byte 0xf2, 0x0f, 0x01, 0xfc"
		     : : "a" (rax), "c" (rcx)
		     : "memory", "cc");
}

Then you can have a higher-level instruction that shows how you convert
the logical things "physical address" and "rmpopt_function" into the
register arguments:

void rmpopt(unsigned long pa)
{
	u64 rax = ALIGN_DOWN(pa & SZ_1GB);
	u64 rcx = RMPOPT_FUNC_VERIFY_AND_REPORT_STATUS;

	__rmpopt(rax, rcx);
}

There's no need right now to pack and unpack rax/rcx from a pointer. Why
even bother when rcx is a fixed value?

> +		set_current_state(TASK_INTERRUPTIBLE);
> +		schedule();

Wait a sec, doesn't this just run all the time? It'll be doing an RMPOPT
on some forever.

---

## [13] Dave Hansen — 2026-03-02
*Subject: Re: [PATCH v2 2/7] x86/sev: add support for enabling RMPOPT*

On 3/2/26 14:55, Kalra, Ashish wrote:
>> What's wrong with:
>>

If that's the case and you *need* performance, then please go add a
wrmsrq_on_cpumask() function to do things in parallel.

---

## [14] Dave Hansen — 2026-03-02
*Subject: Re: [PATCH v2 1/7] x86/cpufeatures: Add X86_FEATURE_AMD_RMPOPT
 feature flag*

On 3/2/26 13:35, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Reviewed-by: Dave Hansen <dave.hansen@linux.intel.com>

---

## [15] Kalra, Ashish — 2026-03-02
*Subject: Re: [PATCH v2 3/7] x86/sev: add support for RMPOPT instruction*

Hello Dave,

On 3/2/2026 4:57 PM, Dave Hansen wrote:

>> +		set_current_state(TASK_INTERRUPTIBLE);
>> +		schedule();

The rmpopt_kthread will be sleeping, till it is woken explicitly by wake_up_process() here.

When the schedule() function is called with the state as TASK_INTERRUPTIBLE or TASK_UNINTERRUPTIBLE,
an additional step is performed: the currently executing process is moved off the run queue before
another process is scheduled. The effect of this is the executing process goes to sleep,
as it no longer is on the run queue. Hence, it never is scheduled by the scheduler.

The thread would then be woken up by calling wake_up_process().

I believe, this is probably the simplest way of sleeping and waking in the kernel.

Thanks,
Ashish

---

## [16] Kalra, Ashish — 2026-03-02
*Subject: Re: [PATCH v2 2/7] x86/sev: add support for enabling RMPOPT*

On 3/2/2026 5:00 PM, Dave Hansen wrote:
> On 3/2/26 14:55, Kalra, Ashish wrote:
>>> What's wrong with:

Sure.

Thanks,
Ashish

---

## [17] Dave Hansen — 2026-03-02
*Subject: Re: [PATCH v2 3/7] x86/sev: add support for RMPOPT instruction*

On 3/2/26 15:09, Kalra, Ashish wrote:
>>> +static void rmpopt_all_physmem(void)
>>> +{

Sorry for the noise, I totally parsed that bit wrong.

---

## [18] Sean Christopherson — 2026-03-04
*Subject: Re: [PATCH v2 3/7] x86/sev: add support for RMPOPT instruction*

On Mon, Mar 02, 2026, Ashish Kalra wrote:
> @@ -500,6 +508,61 @@ static bool __init setup_rmptable(void)
> +/*

I'm not terribly concerned with other threads, but I am most definitely concerned
about other CPUs.  IIUC, *every* time a guest_memfd file is destroyed, the kernel
will process *every* 2MiB chunk of memory, interrupting *every* CPU in the process.

Given that the whole point of RMPOPT is to allow running non-SNP and SNP VMs
side-by-side, inducing potentially significant jitter when stopping SNP VMs seems
like a dealbreaker.

Even using a kthread seems flawed, e.g. if all CPUs in the system are being used
to run VMs, then the kernel could be stealing cycles from an arbitrary VM/vCPU to
process RMPOPT.  Contrast that with KVM's NX hugepage recovery thread, which is
spawned in the context of a specific VM so that recovering steady state performance
at the cost of periodically consuming CPU cycles is bound entirely to that VM.

I don't see any performance data in either posted version.  Bluntly, this series
isn't going anywhere without data to guide us.  E.g. comments like this from v1

 : And there is a cost associated with re-enabling the optimizations for all
 : system RAM (even though it runs as a background kernel thread executing RMPOPT
 : on different 1GB regions in parallel and with inline cond_resched()'s),
 : we don't want to run this periodically.

suggest there is meaningful cost associated with the scan.

---

## [19] Dave Hansen — 2026-03-04
*Subject: Re: [PATCH v2 3/7] x86/sev: add support for RMPOPT instruction*

On 3/4/26 07:01, Sean Christopherson wrote:
> I don't see any performance data in either posted version.  Bluntly, this series
> isn't going anywhere without data to guide us.  E.g. comments like this from v1

Well the RMP is 0.4% of the size of system memory, and I assume that you
need to scan the whole table. There are surely shortcuts for 2M pages,
but with 4k, that's ~8.5GB of RMP table for 2TB of memory. That's an
awful lot of memory traffic for each CPU.

It'll be annoying to keep a refcount per 1GB of paddr space.

One other way to do it would be to loosely mirror the RMPOPT bitmap and
keep our own bitmap of 1GB regions that _need_ RMPOPT run on them. Any
private=>shared conversion sets a bit in the bitmap and schedules some
work out in the future.

It could also be less granular than that. Instead of any private=>shared
conversion, the RMPOPT scan could be triggered on VM destruction which
is much more likely to result in RMPOPT doing anything useful.

BTW, I assume that the RMPOPT disable machinery is driven from the
INVLPGB-like TLB invalidations that are a part of the SNP
shared=>private conversions. It's a darn shame that RMPOPT wasn't
broadcast in the same way. It would save the poor OS a lot of work. The
RMPOPT table is per-cpu of course, but I'm not sure what keeps *a* CPU
from broadcasting its success finding an SNP-free physical region to
other CPUs.

tl;dr: I agree with you. The cost of these scans is going to be
annoying, and it's going to need OS help to optimize it.

---

## [20] Dave Hansen — 2026-03-04
*Subject: Re: [PATCH v2 3/7] x86/sev: add support for RMPOPT instruction*

On 3/4/26 07:25, Dave Hansen wrote:
> BTW, I assume that the RMPOPT disable machinery is driven from the
> INVLPGB-like TLB invalidations that are a part of the SNP

I guess the other dirt simple optimization would be to have one CPU to
the RMPOPT scan and then only IPI more CPUs if that first one succeeds.
That wouldn't be awful.

---

## [21] Andrew Cooper — 2026-03-04
*Subject: Re: [PATCH v2 3/7] x86/sev: add support for RMPOPT instruction*

>> +/* + * 'val' is a system physical address aligned to 1GB OR'ed with
>> + * a function selection. Currently supported functions are 0 + *

The "c" (val & 0x1) constraint encodes whether this is a query or a
mutation, but both forms produce an answer via the carry flag.

Because it's void, it's a useless helper, and the overloading via one
parameter makes specifically poor code generation.

It should be:

static inline bool __rmpopt(unsigned long addr, unsigned int fn)
{
    bool res;

    asm volatile (".byte 0xf2, 0x0f, 0x01, 0xfc"
                 : "=ccc" (res)
                 : "a" (addr), "c" (fn));

    return res;
}

with:

    static inline bool rmpopt_query(unsigned long addr)
    static inline bool rmpopt_set(unsigned long addr)

built on top.

Logic asking hardware to optimise a 1G region because of no guest memory
should at least WARN() if hardware comes back and says "well hang on now..."

The memory barrier isn't necessary and hinders the optimiser.

~Andrew

---

## [22] Dave Hansen — 2026-03-04
*Subject: Re: [PATCH v2 3/7] x86/sev: add support for RMPOPT instruction*

On 3/4/26 07:56, Andrew Cooper wrote:
> Logic asking hardware to optimise a 1G region because of no guest memory
> should at least WARN() if hardware comes back and says "well hang on now..."

It would be _nice_ to have a system where we can do a WARN(). But for
something that's just a lowly optimization, I'd rather that RMPOPT lose
the occasional race with a shared=>private conversion than have it take
a lock and _block_ those conversions.

---

## [23] Kalra, Ashish — 2026-03-04
*Subject: Re: [PATCH v2 3/7] x86/sev: add support for RMPOPT instruction*

Hello Dave and Sean,

On 3/4/2026 9:25 AM, Dave Hansen wrote:
> On 3/4/26 07:01, Sean Christopherson wrote:
>> I don't see any performance data in either posted version.  Bluntly, this series

The RMPOPT instruction is optimized for 2M pages, so it checks that
all 512 2MB entries in that 1GB region are not assigned, i.e., for each
2MB RMP in the 1GB region containing the specified address it checks if
they are not assigned.
  
> 
> It'll be annoying to keep a refcount per 1GB of paddr space.

Yes, it will need to be more granular than scheduling RMPOPT work for any
private->shared conversion. 

And that's what we are doing in v2 patch series, RMPOPT scan getting 
triggered on VM destruction.

> 
> BTW, I assume that the RMPOPT disable machinery is driven from the

The hardware does this broadcast for the RMPUPDATE instruction, 
a broadcast will be sent in the RMPUPDATE instruction to clear matching entries
in other RMPOPT tables.  This broadcast will be sent to all CPUs.

For the RMPOPT instruction itself, there is no such broadcast, but RMPOPT 
instruction needs to be executed on only one thread per core, the 
per-CPU RMPOPT table of the other sibling thread will be programmed while
executing the same instruction.

That's the reason, why we had this optimization to executing RMPOPT instruction
on only the primary thread as part of the v1 patch series and i believe we should
include this optimization as part of future series.

> 
> tl;dr: I agree with you. The cost of these scans is going to be

Here is some performance data:

Raw CPU cycles for a single RMPOPT instruction, func=0 :

RMPOPT during snp_rmptable_init() while booting: 

....
[   12.098580] SEV-SNP: RMPOPT max. CPU cycles 501460
[   12.103839] SEV-SNP: RMPOPT min. CPU cycles 60
[   12.108799] SEV-SNP: RMPOPT average cycles 139790


RMPOPT during SNP_INIT_EX, at CCP module load at boot: 

[   40.206619] SEV-SNP: RMPOPT max. CPU cycles 248083620
[   40.206629] SEV-SNP: RMPOPT min. CPU cycles 60
[   40.206629] SEV-SNP: RMPOPT average cycles 249820

RMPOPT after SNP guest shutdown:
...
[  298.746893] SEV-SNP: RMPOPT max. CPU cycles 248083620
[  298.746898] SEV-SNP: RMPOPT min. CPU cycles 60
[  298.746900] SEV-SNP: RMPOPT average cycles 127859


I believe the min. CPU cycles is the case where RMPOPT fails early. 


Raw CPU cycles for one complete iteration of executing RMPOPT (func=0) on all CPUs for the whole RAM: 

This is for this complete loop with cond_resched() removed.

      while (!kthread_should_stop()) {
                phys_addr_t pa;

                pr_info("RMP optimizations enabled on physical address range @1GB alignment [0x%016llx - 0x%016llx]\n",
                        pa_start, pa_end);

                start = rdtsc_ordered();
                /*
                 * RMPOPT optimizations skip RMP checks at 1GB granularity if this range of
                 * memory does not contain any SNP guest memory.
                 */
                for (pa = pa_start; pa < pa_end; pa += PUD_SIZE) {
                        /* Bit zero passes the function to the RMPOPT instruction. */
                        on_each_cpu_mask(cpu_online_mask, rmpopt,
                                         (void *)(pa | RMPOPT_FUNC_VERIFY_AND_REPORT_STATUS),
                                         true);

                        
                }
                end = rdtsc_ordered();

                pr_info("RMPOPT cycles taken for physical address range 0x%016llx - 0x%016llx on all cpus %llu cycles\n",
                                pa_start, pa_end, end - start);

                set_current_state(TASK_INTERRUPTIBLE);
                schedule();
        }


RMPOPT during snp_rmptable_init() while booting: 

...
[   12.114047] SEV-SNP: RMPOPT cycles taken for physical address range 0x0000000000000000 - 0x0000010380000000 on all cpus 1499496600 cycles

RMPOPT during SNP_INIT_EX:
...
[   40.206630] SEV-SNP: RMPOPT cycles taken for physical address range 0x0000000000000000 - 0x0000010380000000 on all cpus 686519180 cycles

RMPOPT after SNP guest shutdown:
...
[  298.746900] SEV-SNP: RMPOPT cycles taken for physical address range 0x0000000000000000 - 0x0000010380000000 on all cpus 369059160 cycles

Thanks,
Ashish

---

## [24] Borislav Petkov — 2026-03-05
*Subject: Re: [PATCH v2 1/7] x86/cpufeatures: Add X86_FEATURE_AMD_RMPOPT
 feature flag*

On Mon, Mar 02, 2026 at 09:35:19PM +0000, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Please do not add URLs to documents on corporate sites because latter change
notoriously fast, resulting in dead links. Instead, quote the document title
so that anyone looking for it, can find it after a web search engine has
indexed it.

> Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
> ---

Btw, looking further in the set, the first several patches are for tip and
then KVM ones come.

I'm thinking, when the time comes, I'll give you, Sean, an immutable branch
which you can merge.

Right?

---

## [25] Kalra, Ashish — 2026-03-05
*Subject: Re: [PATCH v2 3/7] x86/sev: add support for RMPOPT instruction*

An update on performance data: 

> 
> RMPOPT after SNP guest shutdown:

A single RMPOPT instruction should not be taking 248M cycles, so i looked at
my performance measurement code : 

I was not disabling interrupts around my measurement code, so probably this 
measurement code was getting interrupted/preempted and causing this discrepancy: 

I am now measuring with interrupts disabled around this code: 

static void rmpopt(void *val)
{
        bool optimized;
        u64 start, end;

        local_irq_disable();
        start = rdtsc_ordered();

        asm volatile(".byte 0xf2, 0x0f, 0x01, 0xfc"
                     : "=@ccc" (optimized)
                     : "a" ((u64)val & PUD_MASK), "c" ((u64)val & 0x1)
                     : "memory", "cc");

        end = rdtsc_ordered();
        local_irq_enable();

	total_cycles += (end - start);
        ++iteration;

        if ((end - start) > largest_cycle_rmpopt) {
                pr_info("RMPOPT max cycle on cpu %d, addr 0x%llx, cycles %llu, prev largest %llu\n",
                                smp_processor_id(), ((u64)val & PUD_MASK), end - start, largest_cycle_rmpopt);
                largest_cycle_rmpopt = end - start;
        }
...
...

But, the following is interesting, if I invoke rmpopt() using smp_call_on_cpu() which issues
RMPOPT on each CPU serially compared to using on_each_cpu_mask() above which will execute rmpopt()
function and RMPOPT instruction in parallel on multiple CPUs (by sending IPIs in parallel),
I observe a significant difference and improvement in "individual" RMPOPT instruction performance: 

rmpopt() executing serially using smp_call_on_cpu(): 

[  244.518677] SEV-SNP: RMPOPT instruction cycles 3300
[  244.518716] SEV-SNP: RMPOPT instruction cycles 2840
[  244.518758] SEV-SNP: RMPOPT instruction cycles 3260
[  244.518800] SEV-SNP: RMPOPT instruction cycles 3640
[  244.518838] SEV-SNP: RMPOPT instruction cycles 1980
[  244.518878] SEV-SNP: RMPOPT instruction cycles 3420
[  244.518919] SEV-SNP: RMPOPT instruction cycles 3620
[  244.518958] SEV-SNP: RMPOPT instruction cycles 3120
[  244.518997] SEV-SNP: RMPOPT instruction cycles 2160
[  244.519038] SEV-SNP: RMPOPT instruction cycles 3040
[  244.519078] SEV-SNP: RMPOPT instruction cycles 3700
[  244.519119] SEV-SNP: RMPOPT instruction cycles 3960
[  244.519158] SEV-SNP: RMPOPT instruction cycles 3420
[  244.519211] SEV-SNP: RMPOPT instruction cycles 5080
[  244.519254] SEV-SNP: RMPOPT instruction cycles 3000
[  244.519295] SEV-SNP: RMPOPT instruction cycles 3420
[  244.527150] SEV-SNP: RMPOPT max cycle on cpu 256, addr 0x40000000, cycles 34680, prev largest 22100
[  244.529622] SEV-SNP: RMPOPT max cycle on cpu 320, addr 0x40000000, cycles 36800, prev largest 34680
[  244.559314] SEV-SNP: RMPOPT max cycle on cpu 256, addr 0x80000000, cycles 39740, prev largest 36800
[  244.561718] SEV-SNP: RMPOPT max cycle on cpu 320, addr 0x80000000, cycles 41840, prev largest 39740
[  244.562837] SEV-SNP: RMPOPT max cycle on cpu 352, addr 0x80000000, cycles 42160, prev largest 41840
[  244.886705] SEV-SNP: RMPOPT max cycle on cpu 384, addr 0x300000000, cycles 42300, prev largest 42160
[  247.701377] SEV-SNP: RMPOPT max cycle on cpu 384, addr 0x1980000000, cycles 42400, prev largest 42300
[  250.322355] SEV-SNP: RMPOPT max cycle on cpu 384, addr 0x2ec0000000, cycles 42420, prev largest 42400
[  250.755457] SEV-SNP: RMPOPT max cycle on cpu 384, addr 0x3240000000, cycles 42540, prev largest 42420
[  264.271293] SEV-SNP: RMPOPT max cycle on cpu 32, addr 0xa040000000, cycles 50400, prev largest 42540
[  264.333739] SEV-SNP: RMPOPT max cycle on cpu 32, addr 0xa0c0000000, cycles 50940, prev largest 50400
[  264.395521] SEV-SNP: RMPOPT max cycle on cpu 32, addr 0xa140000000, cycles 51240, prev largest 50940
[  264.733133] SEV-SNP: RMPOPT max cycle on cpu 32, addr 0xa400000000, cycles 51480, prev largest 51240
[  269.500891] SEV-SNP: RMPOPT max cycle on cpu 0, addr 0xcac0000000, cycles 66080, prev largest 51480
[  273.507009] SEV-SNP: RMPOPT max cycle on cpu 320, addr 0xeb40000000, cycles 83680, prev largest 66080
[  276.435091] SEV-SNP: RMPOPT largest cycles 83680
[  276.435096] SEV-SNP: RMPOPT smallest cycles 60
[  276.435097] SEV-SNP: RMPOPT average cycles 5658
[  276.435098] SEV-SNP: RMPOPT cycles taken for physical address range 0x0000000000000000 - 0x0000010380000000 on all cpus 63815935380 cycles

Compare this to executing rmpopt() in parallel:

[ 1238.809183] SEV-SNP: RMPOPT average cycles 114372


So, looks like executing RMPOPT in parallel is causing performance degradation, which we will investigate. 

But, these are the performance numbers you should be considering : 

RMPOPT during boot: 

[   49.913402] SEV-SNP: RMPOPT largest cycles 1143020
[   49.913407] SEV-SNP: RMPOPT smallest cycles 60
[   49.913408] SEV-SNP: RMPOPT average cycles 5226


RMPOPT after SNP guest shutdown: 

[  276.435091] SEV-SNP: RMPOPT largest cycles 83680
[  276.435096] SEV-SNP: RMPOPT smallest cycles 60
[  276.435097] SEV-SNP: RMPOPT average cycles 5658


Thanks,
Ashish

---

## [26] Dave Hansen — 2026-03-05
*Subject: Re: [PATCH v2 3/7] x86/sev: add support for RMPOPT instruction*

On 3/5/26 11:22, Kalra, Ashish wrote:
> But, these are the performance numbers you should be considering : 
> 

First of all, I'd really appreciate wall clock measurements on these.
It's just less math and guesswork. Cycles are easy to measure but hard
to read. Please make these easier to read. Also, the per-RMPOPT numbers
don't mean much. You have to scale it by the number of CPUs and memory
(or 2TB) to get to a real, useful number.

The thing that matters is how long this loop takes:

	for (pa = pa_start; pa < pa_end; pa += PUD_SIZE)

and *especially* how long it takes per-cpu and when the system has a
full 2TB load of memory.

That will tell us how many resources this RMPOPT thing is going to take,
which is the _real_ thing we need to know.

Also, to some degree, the thing we care about here the *most* is the
worst case scenario. I think the worst possible case is that there's one
4k private page in each 1GB of memory, and that it's the last 4k page.
I'd like to see numbers for something close to *that*, not when there
are no private pages.

The two things you measured above are interesting, but they're only part
of the story.

---

## [27] Borislav Petkov — 2026-03-06
*Subject: Re: [PATCH v2 2/7] x86/sev: add support for enabling RMPOPT*

On Mon, Mar 02, 2026 at 09:35:55PM +0000, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

"... which indicate... "

> guest memory.
> 

...

> +static void __configure_rmpopt(void *val)
> +{

If the sub-helper is called __configure_rmpopt() then this should be called
"configure_rmpopt", without the prepended underscores.

> +	phys_addr_t pa_start = ALIGN_DOWN(PFN_PHYS(min_low_pfn), PUD_SIZE);
> +

Zap this one - snp_rmptable_init() already checked it.

Also, zap those pr_debugs - you have that information elsewhere already.

> +
> +	if (!(rmp_cfg & MSR_AMD64_SEG_RMP_ENABLED)) {

You can't test this one - you need to test the result of
setup_segmented_rmptable() and whether it did set up the segmented RMP
properly. Only then you can continue here.

> +		pr_info("RMPOPT optimizations not enabled, segmented RMP required\n");

This looks like pr_notice() to me.

> +		return;
> +	}

---

## [28] Tom Lendacky — 2026-03-06
*Subject: Re: [PATCH v2 2/7] x86/sev: add support for enabling RMPOPT*

On 3/6/26 09:18, Borislav Petkov wrote:
> On Mon, Mar 02, 2026 at 09:35:55PM +0000, Ashish Kalra wrote:
>> From: Ashish Kalra <ashish.kalra@amd.com>

If the segmented RMP setup fails, then CC_ATTR_HOST_SEV_SNP gets cleared,
so it looks like the above check needs to remain then.

Thanks,
Tom

> 
>> +		pr_info("RMPOPT optimizations not enabled, segmented RMP required\n");

---

## [29] Ackerley Tng — 2026-03-09
*Subject: Re: [PATCH v2 5/7] KVM: guest_memfd: Add cleanup interface for guest teardown*

Ashish Kalra <Ashish.Kalra@amd.com> writes:

> From: Ashish Kalra <ashish.kalra@amd.com>
>

Folks have already talked about the performance implications of doing
the scan and rmpopt, I just want to call out that one VM could have more
than one associated guest_memfd too.

I think the cleanup function should be thought of as cleanup for the
inode (even if it doesn't take an inode pointer since it's not (yet)
required).

So, the gmem cleanup function should not handle deduplicating cleanup
requests, but the arch function should, if the cleanup needs
deduplicating.

Also, .free_inode() is called through RCU, so it could be called after
some delay. Could it be possible that .free_inode() ends up being called
way after the associated VM gets torn down, or after KVM the module gets
unloaded?  Does rmpopt still work fine if KVM the module got unloaded?

IIUC the current kmem_cache_free(kvm_gmem_inode_cachep, GMEM_I(inode));
is fine because in kvm_gmem_exit(), there is a rcu_barrier() before
kmem_cache_destroy(kvm_gmem_inode_cachep);.

>  	kmem_cache_free(kvm_gmem_inode_cachep, GMEM_I(inode));
>  }

---

## [30] Kalra, Ashish — 2026-03-10
*Subject: Re: [PATCH v2 5/7] KVM: guest_memfd: Add cleanup interface for guest
 teardown*

Hello Ackerley,

On 3/9/2026 4:01 AM, Ackerley Tng wrote:
> Ashish Kalra <Ashish.Kalra@amd.com> writes:
> 

Yes, i have observed that kvm_gmem_free_inode() gets invoked multiple times
at SNP guest shutdown.

And the same is true for kvm_gmem_destroy_inode() too.

> 
> I think the cleanup function should be thought of as cleanup for the

I agree, the arch function will have to handle deduplicating,  and for that
the arch function will probably need to be passed the inode pointer,
to have a parameter to assist with deduplicating.

> 
> Also, .free_inode() is called through RCU, so it could be called after

Yes, .free_inode() can probably get called after the associated VM has
been torn down and which should be fine for issuing RMPOPT to do
RMP re-optimizations.

As far as about KVM module getting unloaded, then as part of the forthcoming patch-series,
during KVM module unload, X86_SNP_SHUTDOWN would be issued which means SNP would get
disabled and therefore, RMP checks are also disabled.

And as CC_ATTR_HOST_SEV_SNP would then be cleared, therefore, snp_perform_rmp_optimization()
will simply return.

Another option is to add a new guest_memfd superblock operation, and then do the
final guest_memfd cleanup using the .evict_inode() callback. This will then ensure
that the cleanup is not called through RCU and avoids any kind of delays, as following: 

+static void kvm_gmem_evict_inode(struct inode *inode)
+{
+#ifdef CONFIG_HAVE_KVM_ARCH_GMEM_CLEANUP
+        kvm_arch_gmem_cleanup();
+#endif
+       truncate_inode_pages_final(&inode->i_data);
+       clear_inode(inode);
+}
+

@@ -971,6 +979,7 @@ static const struct super_operations kvm_gmem_super_operations = {
        .alloc_inode    = kvm_gmem_alloc_inode,
        .destroy_inode  = kvm_gmem_destroy_inode,
        .free_inode     = kvm_gmem_free_inode,
+       .evict_inode    = kvm_gmem_evict_inode,
 };


Thanks,
Ashish

> 
> IIUC the current kmem_cache_free(kvm_gmem_inode_cachep, GMEM_I(inode));

---

## [31] Ackerley Tng — 2026-03-10
*Subject: Re: [PATCH v2 5/7] KVM: guest_memfd: Add cleanup interface for guest teardown*

"Kalra, Ashish" <ashish.kalra@amd.com> writes:

> Hello Ackerley,
>

By the time .free_folio() is called, folio->mapping may no longer exist,
so if we definitely want to deduplicate using something in the inode,
.free_folio() won't be the right callback to use.

I was thinking that deduplicating using something in the folio would be
better. Can rmpopt take a PFN range? Then there's really no
deduplication, the cleanup would be nicely narrowed to whatever was just
freed. Perhaps the PFNs could be aligned up to the nearest PMD or PUD
size for rmpopt to do the right thing.

Or perhaps some more tracking is required to check that the entire
aligned range is freed before doing the rmpopt.

I need to implement some of this tracking for guest_memfd HugeTLB
support, so if the tracking is useful for you, we should discuss!

>>
>> Also, .free_inode() is called through RCU, so it could be called after

I think relying on CC_ATTR_HOST_SEV_SNP to skip optimization should be
best as long as there are no races (like the .free_inode() will
definitely not try to optimize when SNP is half shut down or something
like that.

> Another option is to add a new guest_memfd superblock operation, and then do the
> final guest_memfd cleanup using the .evict_inode() callback. This will then ensure

At the point of .evict_inode(), CoCo-shared guest_memfd pages could
still be pinned (for DMA or whatever, accidentally or maliciously), can
rmpopt work on shared pages that might still be used for DMA?

.invalidate_folio() and .free_folio() both actually happen on removal
from guest_memfd ownership, though both are not exactly when the folio
is completely not in use.

Is the best time to optimize when the pages are truly freed?

> @@ -971,6 +979,7 @@ static const struct super_operations kvm_gmem_super_operations = {
>         .alloc_inode    = kvm_gmem_alloc_inode,

---

## [32] Kalra, Ashish — 2026-03-11
*Subject: Re: [PATCH v2 3/7] x86/sev: add support for RMPOPT instruction*

Hello Dave and Sean,

On 3/5/2026 1:40 PM, Dave Hansen wrote:
> On 3/5/26 11:22, Kalra, Ashish wrote:
>> But, these are the performance numbers you should be considering : 

Here is the concerned performance data:

All these measurements are done with 2TB RAM installed on the server:

$ free -h
               total        used        free      shared  buff/cache   available
Mem:           2.0Ti        13Gi       1.9Ti       8.8Mi       1.6Gi       1.9Ti
Swap:          2.0Gi          0B       2.0Gi


For the loop executing RMPOPT on up-to 2TB of RAM on all CPUs: 

                ..
                start = ktime_get();
               
                for (pa = pa_start; pa < pa_end; pa += PUD_SIZE) {
                        /* Bit zero passes the function to the RMPOPT instruction. */
                        on_each_cpu_mask(cpu_online_mask, rmpopt,
                                         (void *)(pa | RMPOPT_FUNC_VERIFY_AND_REPORT_STATUS),
                                         true);
                }
                end = ktime_get();

                elapsed_ns = ktime_to_ns(ktime_sub(end, start));
		...

There are 2 active SNP VMs here, with one SNP VM being terminated, the other SNP VM is still running, both VMs are configured with 100GB guest RAM: 

When this loop is executed when the SNP guest terminates:

[  232.789187] SEV-SNP: RMPOPT execution time 391609638 ns for physical address range 0x0000000000000000 - 0x0000020000000000 on all cpus -> ~391 ms

[  234.647462] SEV-SNP: RMPOPT execution time 457933019 ns for physical address range 0x0000000000000000 - 0x0000020000000000 on all cpus -> ~457 ms


Now, there are a couple of additional RMPOPT optimizations which can be applied to this loop : 

1). RMPOPT can skip the bulk of its work if another CPU has already optimized that region.
The optimal thing may be to optimize all memory on one CPU first, and then let all the others
run RMPOPT in parallel.

2). The other optimization being applied here is only executing RMPOPT on only thread per
core.

The code sequence being used here:

	...
        /* Only one thread per core needs to issue RMPOPT instruction */
        for_each_online_cpu(cpu) {
                if (!topology_is_primary_thread(cpu))
                        continue;

                cpumask_set_cpu(cpu, cpus);
        }

         while (!kthread_should_stop()) {
         	...
                start = ktime_get();
               
                /*
                 * RMPOPT is optimized to skip the bulk of its work if another CPU has already
                 * optimized that region. Optimize all memory on one CPU first, and then let all
                 * the others run RMPOPT in parallel.
                 */
                cpumask_clear_cpu(smp_processor_id(), cpus);

                /* current CPU */
                for (pa = pa_start; pa < pa_end; pa += PUD_SIZE)
                        rmpopt((void *)(pa | RMPOPT_FUNC_VERIFY_AND_REPORT_STATUS));

                for (pa = pa_start; pa < pa_end; pa += PUD_SIZE) {
                        /* Bit zero passes the function to the RMPOPT instruction. */
                        on_each_cpu_mask(cpus, rmpopt,
                                         (void *)(pa | RMPOPT_FUNC_VERIFY_AND_REPORT_STATUS),
                                         true);                       
                }
                end = ktime_get();

                elapsed_ns = ktime_to_ns(ktime_sub(end, start));
		...

With these optimizations applied:

When this loop is executed when an SNP guest terminates, again with 2 active SNP VMs with 100GB guest RAM:

[  363.926595] SEV-SNP: RMPOPT execution time 317016656 ns for physical address range 0x0000000000000000 - 0x0000020000000000 on all cpus -> ~317 ms

[  365.415243] SEV-SNP: RMPOPT execution time 369659769 ns for physical address range 0x0000000000000000 - 0x0000020000000000 on all cpus -> ~369 ms.

So, with these two optimizations applied, there is like a ~16-20% performance improvement (when SNP guest terminates) in the execution of this loop
which is executing RMPOPT on upto 2TB of RAM on all CPUs.

Any thoughts, feedback on the performance numbers ? 

Ideally we should be issuing RMPOPTs to only optimize the 1G regions that contained memory associated with that guest and that should be 
significantly less than the whole 2TB RAM range. 

But that is something we planned for 1GB hugetlb guest_memfd support getting merged and which i believe has dependency on:
1). in-place conversion for guest_memfd, 
2). 2M hugepage support for guest_memfd and finally 
3). 1GB hugeTLB support for guest_memfd.

The other alternative probably will be to use Dave's suggestions to loosely mirror the RMPOPT bitmap and
keep our own bitmap of 1GB regions that _need_ RMPOPT run on them and probably this bitmap lives in
guest_memfd and we track when they are being freed and then issue RMPOPT on those 1GB regions
(and this will be independent of the 1GB hugeTLB support for guest_memfd).

Thanks,
Ashish

---

## [33] Kalra, Ashish — 2026-03-11
*Subject: Re: [PATCH v2 5/7] KVM: guest_memfd: Add cleanup interface for guest
 teardown*

Hello Ackerley,

On 3/11/2026 1:00 AM, Ackerley Tng wrote:
> "Kalra, Ashish" <ashish.kalra@amd.com> writes:
> 

Ok.

> 
> I was thinking that deduplicating using something in the folio would be

It will really be ideal if the cleanup can be narrowed down to whatever was just freed.

RMPOPT takes a SPA which is GB aligned, so if the PFNs are aligned to the nearest
PUD, then RMPOPT will be perfectly aligned to optimize the 1G regions that contained
memory associated with that guest being freed.

This will also be the most optimal way to use RMPOPT, as we only optimize the 1G regions
that contains memory associated with that guest, which should be much smaller than
optimizing the whole 2TB RAM. 

And that's what the actual plans for RMPOPT are.

We had planned for a phased RMPOPT implementation. 

In the first phase, we were planning to do RMP re-optimizations for entire 2TB
RAM. 

Once 1GB hugetlb guest_memfd support is merged, we planned to support re-enabling
RMPOPT optimizations during 1GB page cleanup as a follow-on series.

But i believe this support is dependent on:
1). in-place conversion for guest_memfd, 
2). 2M hugepage support for guest_memfd.

Another alternative we are considering is implementing a bitmap of 1GB regions in guest_memfd
that tracks when they are being freed and then issue RMPOPT on those 1GB regions.
(and this will be independent of the 1GB hugeTLB support for guest_memfd).

> Or perhaps some more tracking is required to check that the entire
> aligned range is freed before doing the rmpopt.

Yes, this tracking is going to be useful for RMPOPT. 

Is this going to be implemented as part of the 1GB hugeTLB support for guest_memfd ?

> 
>>>

Yeah, i will have to take a look at such races.

> 
>> Another option is to add a new guest_memfd superblock operation, and then do the

Yes, RMPOPT should be safe to work here, as it checks the RMP table for assigned
or private pages in the 1GB range specified. For a 1GB range full of shared pages,
it will mark that range to be RMP optimized.

If all RMPUPDATE's for all private->shared pages conversion have been completed at
the point of .evict_inode(), then RMPOPT re-optimizations will work nicely.

> .invalidate_folio() and .free_folio() both actually happen on removal
> from guest_memfd ownership, though both are not exactly when the folio

Yes.

Thanks,
Ashish

>> @@ -971,6 +979,7 @@ static const struct super_operations kvm_gmem_super_operations = {
>>         .alloc_inode    = kvm_gmem_alloc_inode,

---

## [34] Dave Hansen — 2026-03-11
*Subject: Re: [PATCH v2 3/7] x86/sev: add support for RMPOPT instruction*

On 3/11/26 14:24, Kalra, Ashish wrote:
...
> There are 2 active SNP VMs here, with one SNP VM being terminated, the other SNP VM is still running, both VMs are configured with 100GB guest RAM: 
> 

That's better, but it's not quite what am looking for.

The most important case (IMNHO) is when RMPOPT falls flat on its face:
it tries to optimize the full 2TB of memory and manages to optimize nothing.

I doubt that two 100GB VMs will get close to that case. It's
theoretically possible, but unlikely.

You also didn't mention 4k vs. 2M vs. 1G mappings.

> Now, there are a couple of additional RMPOPT optimizations which can be applied to this loop : 
> 

Ahh, so the RMP table itself caches the result of the RMPOPT in its 1G
metadata, then the CPUs can just copy it into their core-local
optimization table at RMPOPT time?

That's handy.

*But*, for the purposes of finding pathological behavior, it's actually
contrary to what I think I was asking for which was having all 1G pages
filled with some private memory. If the system was in the state I want
to see tested, that optimization won't function.

> [  363.926595] SEV-SNP: RMPOPT execution time 317016656 ns for physical address range 0x0000000000000000 - 0x0000020000000000 on all cpus -> ~317 ms
> 

16-20% isn't horrible, but it isn't really a fundamental change.

It would also be nice to see elapsed time for each CPU. Having one
pegged CPU for 400ms and 99 mostly idle ones is way different than
having 100 pegged CPUs for 400ms.

That's why I was interested in "how long it takes per-cpu".

But you could get some pretty good info with your new optimized loop:

                start = ktime_get();

                for (pa = pa_start; pa < pa_end; pa += PUD_SIZE)
                        rmpopt() // current CPU

                middle = ktime_get();

                for (pa = pa_start; pa < pa_end; pa += PUD_SIZE)
                        on_each_cpu_mask(...) // remote CPUs

                end = ktime_get();

If you do that ^ with a system:

	1. full of private memory
	2. empty of private memory
	3. empty again

You'll hopefully see:

	1. RMPOPT fall on its face. Worst case scenario (what I want to
	   see most)
	2. RMPOPT sees great success, but has to scan the RMP at least
	   once. Remote CPUs get a free ride on the first CPU's scan.
	   Largest (middle-start) vs. (end-middle)/nr_cpus delta.
	3. RMPOPT best case. Everything is already optimized.

> Ideally we should be issuing RMPOPTs to only optimize the 1G regions that contained memory associated with that guest and that should be 
> significantly less than the whole 2TB RAM range. 

It's a no-brainer to do RMPOPT when you have 1GB pages around. You'll
see zero argument from me.

Doing things per-guest and for smaller pages gets a little bit harder to
reason about. In the end, this is all about trying to optimize against
the RMP table which is a global resource. It's going to get wonky if
RMPOPT is driven purely by guest-local data. There are lots of potential
pitfalls.

For now, let's just do it as simply as possible. Get maximum bang for
our buck with minimal data structures and see how that works out. It
might end up being a:

	queue_delayed_work()

to do some cleanup a few seconds out after each SNP guest terminates. If
a bunch of guests terminate all at once it'll at least only do a single
set of IPIs.

---

## [35] Kalra, Ashish — 2026-03-16
*Subject: Re: [PATCH v2 3/7] x86/sev: add support for RMPOPT instruction*

Hello Dave,

On 3/11/2026 5:20 PM, Dave Hansen wrote:
> On 3/11/26 14:24, Kalra, Ashish wrote:
> ...

True that in this case RMPOPT will not do any optimizations and the system performance will be worst, but actually 
if you see in this case, for this loop which we are considering, the loop will actually have the smallest runtime.
More on this below.

> 
>> [  363.926595] SEV-SNP: RMPOPT execution time 317016656 ns for physical address range 0x0000000000000000 - 0x0000020000000000 on all cpus -> ~317 ms

Again, for this case RMPOPT fails to do any optimizations, but for this loop which we are considering, this case will have the smallest runtime.


> 	2. empty of private memory
> 	3. empty again

In both these cases, RMPOPT does the best optimizations for system performance, but for the loop which we are considering, these cases will have
the longest runtime, as in this case RMPOPT has to check *all* the RMP entries in each 1GB region (and for every 1G region it is executed for) and
so each RMPOPT instruction and this loop itself will take the maximum time.

Here are the actual numbers: 

These measurements are done with the *new* optimized loop: 

		...
		/* Only one thread per core needs to issue RMPOPT instruction */
        	for_each_online_cpu(cpu) {
                	if (!topology_is_primary_thread(cpu))
                        	continue;

                	cpumask_set_cpu(cpu, cpus);
        	}

		...
		start = ktime_get();
                
                /*
                 * RMPOPT is optimized to skip the bulk of its work if another CPU has already
                 * optimized that region. Optimize all memory on one CPU first, and then let all
                 * the others run RMPOPT in parallel.
                 */
                cpumask_clear_cpu(smp_processor_id(), cpus);

                /* current CPU */
                for (pa = pa_start; pa < pa_end; pa += PUD_SIZE)
                        rmpopt((void *)(pa | RMPOPT_FUNC_VERIFY_AND_REPORT_STATUS));

                for (pa = pa_start; pa < pa_end; pa += PUD_SIZE) {
                        /* Bit zero passes the function to the RMPOPT instruction. */
                        on_each_cpu_mask(cpus, rmpopt,
                                         (void *)(pa | RMPOPT_FUNC_VERIFY_AND_REPORT_STATUS),
                                         true); 
                }
                end = ktime_get();

                elapsed_ns = ktime_to_ns(ktime_sub(end, start));
                pr_info("RMPOPT execution time %llu ns for physical address range 0x%016llx - 0x%016llx on all cpus\n",
                                elapsed_ns, pa_start, pa_end);
		...

Case 2 and 3: 

When the following loop is executed, after SNP is enabled at snp_rmptable_init(), the RMP table does not have any assigned pages, which is 
essentially case 2.

So the loop has the worst runtime, as can be seen below: 

[   12.961935] SEV-SNP: RMP optimizations enabled on physical address range @1GB alignment [0x0000000000000000 - 0x0000020000000000]
[   13.286659] SEV-SNP: RMPOPT execution time 311135734 ns for physical address range 0x0000000000000000 - 0x0000020000000000 on all cpus -> ~311 ms.

At this point, i simulate the case you are looking for, where the RAM is full of private memory/assigned pages, essentially case 1.

In other words, i simulated a case, where the first 4K page at every 1GB boundary is an assigned page.
This means that RMPOPT will exit immediately and early as it finds an assigned page on the first page it checks in every 1GB range, as below: 

	...
      	for (pfn = 0; pfn < max_pfn; pfn += (1 << (PUD_SHIFT - PAGE_SHIFT)))
                  rmp_make_private(pfn, 0, PG_LEVEL_4K, 0, true);
	...
              
And so RMPOPT instruction itself and executing this loop after programming the RMP table as above has the smallest runtime: 

[   13.430801] SEV-SNP: RMP optimizations enabled on physical address range @1GB alignment [0x0000000000000000 - 0x0000020000000000]
[   13.539667] SEV-SNP: RMPOPT execution time 95275588 ns for physical address range 0x0000000000000000 - 0x0000020000000000 on all cpus -> ~95 ms.

To summarize, these two are the worst and best performance numbers for this loop which we are considering.

Best runtime for the loop:
When RMPOPT exits early as it finds an assigned page on the first RMP entry it checks in the 1GB -> ~95ms.

Worst runtime for the loop:
When RMPOPT does not find any assigned page in the full 1GB range it is checking -> ~311ms. 

So looking at this range [95ms - 311ms], we need to decide if we want to use the kthread approach ?

> 
> You'll hopefully see:

Yes.

> Doing things per-guest and for smaller pages gets a little bit harder to
> reason about. In the end, this is all about trying to optimize against

Again, looking at the numbers above, what are your suggestions for 

1). using the kthread approach OR 
2). probably scheduling it for later execution after SNP guest termination via a workqueue OR
3). use some additional data structure like a bitmap to track 1G pages in guest_memfd 
to do the RMP re-optimizations.

Thanks,
Ashish

---

## [36] Dave Hansen — 2026-03-18
*Subject: Re: [PATCH v2 3/7] x86/sev: add support for RMPOPT instruction*

Thanks for the additional performance numbers!

On 3/16/26 12:03, Kalra, Ashish wrote:
> Again, looking at the numbers above, what are your suggestions for 
> 

I don't like the kthread approach. The kernel has a billion features. If
each one gets a kthread or kthread-per-$SOMETHING, we'll spend all of
our RAM on kthread task_structs and stacks.

> 2). probably scheduling it for later execution after SNP guest termination via a workqueue OR

I think there are two different issues:

1. What asynchronous kernel mechanism is used to execute the RMPOPT?
2. How does that mechanism get triggered?

For #1, I think schedule_work() is the place to start. You need more
justification on why it needs a dedicated kthread.

For #2, I say just schedule some delayed work on every SEV-SNP
private=>shared conversion to do RMPOPT. Schedule it out 1 second or 10
seconds or _something_. If work is scheduled and you convert another
page, cancel it and push it out another 1 or 10 seconds.

> 3). use some additional data structure like a bitmap to track 1G pages in guest_memfd 
> to do the RMP re-optimizations.

That's an optimization that can be added later.

Whatever you do, it's going to need trigger points and asynchronous
work. There will always be ways to get the work amount down, but the
worst case will always be there.

---

## [37] Kalra, Ashish — 2026-03-25
*Subject: Re: [PATCH v2 3/7] x86/sev: add support for RMPOPT instruction*

On 3/4/2026 9:56 AM, Andrew Cooper wrote:
>>> +/* + * 'val' is a system physical address aligned to 1GB OR'ed with
>>> + * a function selection. Currently supported functions are 0 + *

RMPOPT instructions for a given 1 GB page can be executed concurrently across CPUs,
reducing the overall penalty of enabling the optimization, hence we use 
on_each_cpu_mask() to execute RMPOPT instructions in parallel.

Now, the issue with that is the callback function to run on_each_cpu_mask() is of the type: 
(typedef void (*smp_call_func_t)(void *info)).

Hence, the rmpopt() function here has return "void" type and additionally takes "void *"
as parameter.

> 
> It should be:

The above constraints to use on_each_cpu_mask() is forcing the use of:

void rmpopt(void *val)

Thanks,
Ashish
 
> with:
>

---

## [38] Andrew Cooper — 2026-03-26
*Subject: Re: [PATCH v2 3/7] x86/sev: add support for RMPOPT instruction*

On 25/03/2026 9:53 pm, Kalra, Ashish wrote:
> On 3/4/2026 9:56 AM, Andrew Cooper wrote:
>> It should be:

No.  You don't break your thin wrapper in order to force it into a
wrong-shaped hole.

You need something like this:

void do_rmpopt_optimise(void *val)
{
    unsigned long addr = *(unsigned long *)val;

    WARN_ON_ONCE(__rmpopt(addr, OPTIMISE));
}

to invoke the wrapper safely from the IPI.  That will at obvious when
something wrong occurs.

~Andrew

---

## [39] Kalra, Ashish — 2026-03-25
*Subject: Re: [PATCH v2 3/7] x86/sev: add support for RMPOPT instruction*

On 3/25/2026 7:40 PM, Andrew Cooper wrote:
> On 25/03/2026 9:53 pm, Kalra, Ashish wrote:
>> On 3/4/2026 9:56 AM, Andrew Cooper wrote:

This wrapper i can/will use, but doing a WARN_ON_ONCE() is probably avoidable as 
there will be ranges where RMPOPT will always fail, such as while checking 
the RMP table entries itself, so there is a good chance that we will always trigger
the WARN_ON_ONCE() on the memory range containing the RMP table.

Thanks,
Ashish

> 
> ~Andrew

---

## [40] Kalra, Ashish — 2026-03-25
*Subject: Re: [PATCH v2 3/7] x86/sev: add support for RMPOPT instruction*

On 3/25/2026 9:02 PM, Kalra, Ashish wrote:
> 
> On 3/25/2026 7:40 PM, Andrew Cooper wrote:

To add, the above is in context of the current implementation, where we scan all 
memory up-to 2TB for applying RMP optimizations when SNP is enabled (and/or SNP_INIT).

We will *always* get this stack trace during booting, so i think it makes sense
to avoid this WARN_ON_ONCE().

Thanks,
Ashish

---

## [41] Ackerley Tng — 2026-03-27
*Subject: Re: [PATCH v2 5/7] KVM: guest_memfd: Add cleanup interface for guest teardown*

"Kalra, Ashish" <ashish.kalra@amd.com> writes:

> Hello Ackerley,
>

You're right about this dependency. Do you meant guest_memfd THP support
for "2M hugepage"?

> Another alternative we are considering is implementing a bitmap of 1GB regions in guest_memfd
> that tracks when they are being freed and then issue RMPOPT on those 1GB regions.

Yes, this is going to be implemented as part of the HugeTLB support
for guest_memfd. HugeTLB support for guest_memfd extends to any HugeTLB
page size the host supports, so not just 1G, 2M as well. :)

>>
>>>>

Ah okay. The kvm_arch_gmem_invalidate() call in .free_folio is the part
that updates the RMP table to make anything private become shared.

So the RMPOPT probably needs to happen after the invalidate in .free_folio

The RMPOPT stuff is still useful even if the host never uses huge pages
for guest_memfd, right? If so, I think we still need a solution
regardless of when huge page support for guest_memfd lands.

What if we do it this way: in .free_folio, after doing the invalidate,
take the pfn of the folio being freed, align that to the GB containing
that pfn, then RMPOPT that? This way there is no dependency on the inode
being around.

RMPOPT looks up the shared/private-ness of the page in the RMP table
anyway so as long as the RMP table is updated, we should be good?

The awkward part is if RMPOPT is run twice when the RMP table state
hasn't changed. Is my understanding right that there will be no
correctness issues, just performance?

We can perhaps optimize (away or otherwise) unnecessary RMPOPTs later?

With this aligning-up-to-the-GB, at least we're not iterating the entire
host memory.

>> .invalidate_folio() and .free_folio() both actually happen on removal
>> from guest_memfd ownership, though both are not exactly when the folio

Thank you!

>>> @@ -971,6 +979,7 @@ static const struct super_operations kvm_gmem_super_operations = {
>>>         .alloc_inode    = kvm_gmem_alloc_inode,

---

## [42] Kalra, Ashish — 2026-03-30
*Subject: Re: [PATCH v2 5/7] KVM: guest_memfd: Add cleanup interface for guest
 teardown*

Hello Ackerley,

On 3/27/2026 12:16 PM, Ackerley Tng wrote:
> "Kalra, Ashish" <ashish.kalra@amd.com> writes:
> 

Yes.

>> Another alternative we are considering is implementing a bitmap of 1GB regions in guest_memfd
>> that tracks when they are being freed and then issue RMPOPT on those 1GB regions.

Ok. 

>>>
>>>>>

Yes.

> What if we do it this way: in .free_folio, after doing the invalidate,
> take the pfn of the folio being freed, align that to the GB containing

The issue with doing it in .free_folio after doing the invalidate OR after P->S translation,
and aligning it to the GB containing that pfn, the chances of that being the only
private page in the range is small and there is a high probability of multiple pages
still existing in this range which are still assigned. 

So doing RMPOPT for such page(s) (aligned to 1GB) will most likely fail, as there are
still private/assigned pages in this 1GB range.

RMPOPT will succeed or work optimally when we issue it when RMPOPT-able ranges or
full 1GB regions are actually becoming available/freed from guest_memfd. 

> 
> RMPOPT looks up the shared/private-ness of the page in the RMP table

Yes.

> The awkward part is if RMPOPT is run twice when the RMP table state
> hasn't changed. Is my understanding right that there will be no

Yes. 

 
> We can perhaps optimize (away or otherwise) unnecessary RMPOPTs later?
> 

Until we have full 1GB regions available on which we can issue RMPOPT it does
not make sense to issue RMPOPT as most likely it will fail. 

That's why until hugeTLB support for guest_memfd is available, for the initial
series, iterating all system RAM for RMPOPT after SNP VM teardown is an option. 
As this is being scheduled like 10 seconds later, then if other VMs terminate
there is already work scheduled and we skip scheduling another RMPOPT work.

Thanks,
Ashish
 
>>> .invalidate_folio() and .free_folio() both actually happen on removal
>>> from guest_memfd ownership, though both are not exactly when the folio

---
