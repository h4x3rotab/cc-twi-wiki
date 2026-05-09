---
title: 'x86/kexec: Disable kexec/kdump on platforms with TDX partial write erratum'
date: 2025-10-25
last_reply: 2025-11-04
message_count: 9
participants: ['Sasha Levin', 'Huang, Kai']
---

## [1] Sasha Levin — 2025-10-25

From: Kai Huang <kai.huang@intel.com>

[ Upstream commit b18651f70ce0e45d52b9e66d9065b831b3f30784 ]

Some early TDX-capable platforms have an erratum: A kernel partial
write (a write transaction of less than cacheline lands at memory
controller) to TDX private memory poisons that memory, and a subsequent
read triggers a machine check.

On those platforms, the old kernel must reset TDX private memory before
jumping to the new kernel, otherwise the new kernel may see unexpected
machine check.  Currently the kernel doesn't track which page is a TDX
private page.  For simplicity just fail kexec/kdump for those platforms.

Leverage the existing machine_kexec_prepare() to fail kexec/kdump by
adding the check of the presence of the TDX erratum (which is only
checked for if the kernel is built with TDX host support).  This rejects
kexec/kdump when the kernel is loading the kexec/kdump kernel image.

The alternative is to reject kexec/kdump when the kernel is jumping to
the new kernel.  But for kexec this requires adding a new check (e.g.,
arch_kexec_allowed()) in the common code to fail kernel_kexec() at early
stage.  Kdump (crash_kexec()) needs similar check, but it's hard to
justify because crash_kexec() is not supposed to abort.

It's feasible to further relax this limitation, i.e., only fail kexec
when TDX is actually enabled by the kernel.  But this is still a half
measure compared to resetting TDX private memory so just do the simplest
thing for now.

The impact to userspace is the users will get an error when loading the
kexec/kdump kernel image:

  kexec_load failed: Operation not supported

This might be confusing to the users, thus also print the reason in the
dmesg:

  [..] kexec: Not allowed on platform with tdx_pw_mce bug.

Signed-off-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Paolo Bonzini <pbonzini@redhat.com>
Signed-off-by: Dave Hansen <dave.hansen@linux.intel.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
Link: https://lore.kernel.org/all/20250901160930.1785244-5-pbonzini%40redhat.com
Signed-off-by: Sasha Levin <sashal@kernel.org>
---

LLM Generated explanations, may be completely bogus:

YES

**Why This Fix Matters**
- Prevents machine checks during kexec/kdump on early TDX-capable
  platforms with the “partial write to TDX private memory” erratum.
  Without this, the new kernel may hit an MCE after the old kernel
  jumps, which is a hard failure affecting users.

**What Changed**
- Adds an early guard in the kexec image load path to reject kexec/kdump
  if the CPU bug is present:
  - `arch/x86/kernel/machine_kexec_64.c:361`: `if
    (boot_cpu_has_bug(X86_BUG_TDX_PW_MCE)) { ... return -EOPNOTSUPP; }`
  - `arch/x86/kernel/machine_kexec_64.c:362`: Prints a one-time reason:
    “Not allowed on platform with tdx_pw_mce bug”
  - The check runs before page table setup and other preparation,
    minimizing side effects.

**Where the Bug Flag Comes From**
- Bug flag definition: `arch/x86/include/asm/cpufeatures.h:543` defines
  `X86_BUG_TDX_PW_MCE`.
- Detection/enablement on TDX host platforms:
  - `arch/x86/kernel/cpu/common.c:2124`: Calls `tdx_init()` during boot
    CPU identification.
  - `arch/x86/virt/vmx/tdx/tdx.c:1465`: `tdx_init()` calls
    `check_tdx_erratum()`.
  - `arch/x86/virt/vmx/tdx/tdx.c:1396`: `check_tdx_erratum()` sets the
    bug via `setup_force_cpu_bug(X86_BUG_TDX_PW_MCE)` for affected
    models (`:1407`).
- If TDX host support is not built, `tdx_init()` is a stub and the bug
  bit is never set (guard becomes a no-op). This scopes the behavior to
  kernels configured with TDX host support as intended.

**Effect on Callers**
- kexec fast-fails when loading the image:
  - `kernel/kexec.c:142`: `ret = machine_kexec_prepare(image);`
  - `kernel/kexec_file.c:416`: `ret = machine_kexec_prepare(image);`
- Userspace sees `EOPNOTSUPP` and dmesg logs the rationale, avoiding a
  crash later at handoff.

**Scope and Risk**
- Small, localized change; no architectural refactor.
- Only affects x86-64 kexec/kdump on systems where the bug flag is set;
  no behavioral change for others.
- Conservative by design: disallows kexec/kdump to prevent hard machine
  checks.
- Reuse of existing CPU-bug infrastructure ensures correctness and
  stability.

**Dependencies/Backport Notes**
- Requires `X86_BUG_TDX_PW_MCE` to exist and be set on affected hardware
  (see cpufeatures and TDX init paths). If a target stable branch lacks
  this bug flag or `tdx_init()` path, the guard must be adapted or
  prerequisite patches included.

**Stable Criteria**
- Fixes a real user-visible reliability issue (hard MCE on reboot-to-
  crash kernel).
- Minimal and contained change with low regression risk.
- No new features or architectural changes; limited to x86 kexec path.
- Behavior matches stable policy: prefer preventing fatal errors over
  risky runtime mitigation.

Given the above, this is a good candidate for backporting to stable
trees that include TDX host infrastructure and the corresponding bug
flag.

 arch/x86/kernel/machine_kexec_64.c | 16 ++++++++++++++++
 1 file changed, 16 insertions(+)

diff --git a/arch/x86/kernel/machine_kexec_64.c b/arch/x86/kernel/machine_kexec_64.c
index 697fb99406e6b..754e95285b910 100644
--- a/arch/x86/kernel/machine_kexec_64.c
+++ b/arch/x86/kernel/machine_kexec_64.c
@@ -346,6 +346,22 @@ int machine_kexec_prepare(struct kimage *image)
 	unsigned long reloc_end = (unsigned long)__relocate_kernel_end;
 	int result;
 
+	/*
+	 * Some early TDX-capable platforms have an erratum.  A kernel
+	 * partial write (a write transaction of less than cacheline
+	 * lands at memory controller) to TDX private memory poisons that
+	 * memory, and a subsequent read triggers a machine check.
+	 *
+	 * On those platforms the old kernel must reset TDX private
+	 * memory before jumping to the new kernel otherwise the new
+	 * kernel may see unexpected machine check.  For simplicity
+	 * just fail kexec/kdump on those platforms.
+	 */
+	if (boot_cpu_has_bug(X86_BUG_TDX_PW_MCE)) {
+		pr_info_once("Not allowed on platform with tdx_pw_mce bug\n");
+		return -EOPNOTSUPP;
+	}
+
 	/* Setup the identity mapped 64bit page table */
 	result = init_pgtable(image, __pa(control_page));
 	if (result)

---

## [2] Sasha Levin — 2025-10-25
*Subject: [PATCH AUTOSEL 6.17] x86/virt/tdx: Mark memory cache state incoherent when making SEAMCALL*

From: Kai Huang <kai.huang@intel.com>

[ Upstream commit 10df8607bf1a22249d21859f56eeb61e9a033313 ]

On TDX platforms, dirty cacheline aliases with and without encryption
bits can coexist, and the cpu can flush them back to memory in random
order.  During kexec, the caches must be flushed before jumping to the
new kernel otherwise the dirty cachelines could silently corrupt the
memory used by the new kernel due to different encryption property.

A percpu boolean is used to mark whether the cache of a given CPU may be
in an incoherent state, and the kexec performs WBINVD on the CPUs with
that boolean turned on.

For TDX, only the TDX module or the TDX guests can generate dirty
cachelines of TDX private memory, i.e., they are only generated when the
kernel does a SEAMCALL.

Set that boolean when the kernel does SEAMCALL so that kexec can flush
the cache correctly.

The kernel provides both the __seamcall*() assembly functions and the
seamcall*() wrapper ones which additionally handle running out of
entropy error in a loop.  Most of the SEAMCALLs are called using the
seamcall*(), except TDH.VP.ENTER and TDH.PHYMEM.PAGE.RDMD which are
called using __seamcall*() variant directly.

To cover the two special cases, add a new __seamcall_dirty_cache()
helper which only sets the percpu boolean and calls the __seamcall*(),
and change the special cases to use the new helper.  To cover all other
SEAMCALLs, change seamcall*() to call the new helper.

For the SEAMCALLs invoked via seamcall*(), they can be made from both
task context and IRQ disabled context.  Given SEAMCALL is just a lengthy
instruction (e.g., thousands of cycles) from kernel's point of view and
preempt_{disable|enable}() is cheap compared to it, just unconditionally
disable preemption during setting the boolean and making SEAMCALL.

Signed-off-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Paolo Bonzini <pbonzini@redhat.com>
Signed-off-by: Dave Hansen <dave.hansen@linux.intel.com>
Reviewed-by: Chao Gao <chao.gao@intel.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Tested-by: Farrah Chen <farrah.chen@intel.com>
Link: https://lore.kernel.org/all/20250901160930.1785244-4-pbonzini%40redhat.com
Signed-off-by: Sasha Levin <sashal@kernel.org>
---

LLM Generated explanations, may be completely bogus:

YES

Why this fixes a real bug
- TDX can leave dirty cachelines for private memory with different
  encryption attributes (C-bit aliases). If kexec interrupts a CPU
  during a SEAMCALL, its dirty private cachelines can later be flushed
  in the wrong order and silently corrupt the new kernel’s memory.
  Marking the CPU’s cache state as “incoherent” before executing
  SEAMCALL ensures kexec will WBINVD on that CPU and avoid corruption.

What changed (key points with code references)
- New helper marks per-CPU cache incoherent before any SEAMCALL:
  - arch/x86/include/asm/tdx.h:111 sets
    `this_cpu_write(cache_state_incoherent, true)` in
    `__seamcall_dirty_cache()` and asserts preemption is disabled (lines
    111–128).
- Wrap all `seamcall*()` paths with preemption-disabled critical
  section:
  - arch/x86/include/asm/tdx.h:130–147 uses
    `preempt_disable()/preempt_enable()` in `sc_retry()` so the same CPU
    that sets the flag executes the SEAMCALL, avoiding migration races.
- Convert special direct callers to use the new helper:
  - arch/x86/virt/vmx/tdx/tdx.c:1271 changes `paddr_is_tdx_private()` to
    call `__seamcall_dirty_cache(__seamcall_ret, TDH_PHYMEM_PAGE_RDMD,
    ...)`.
  - arch/x86/virt/vmx/tdx/tdx.c:1522 changes `tdh_vp_enter()` to call
    `__seamcall_dirty_cache(__seamcall_saved_ret, TDH_VP_ENTER, ...)`.
- Consumers of the per-CPU flag during kexec/CPU stop:
  - arch/x86/kernel/process.c:99 defines `cache_state_incoherent` and
    uses it in `stop_this_cpu()` to WBINVD if set
    (arch/x86/kernel/process.c:840).
  - arch/x86/kernel/machine_kexec_64.c:449 sets
    `RELOC_KERNEL_CACHE_INCOHERENT` when the per-CPU flag is set so
    `relocate_kernel_64.S` executes WBINVD (relocate path).
  - The TDX-specific flush routine will WBINVD and clear the flag if
    needed (arch/x86/virt/vmx/tdx/tdx.c:1872–1887).

Why it’s safe to backport
- Scope-limited: touches only TDX host paths and the seamcall wrappers;
  no ABI or architectural changes.
- Minimal risk: setting a per-CPU boolean and wrapping SEAMCALLs with
  preempt disable. SEAMCALLs are long; added preemption control is
  negligible overhead and avoids CPU migration races.
- Correctness across contexts: SEAMCALLs can happen with IRQs disabled;
  the helper asserts preemption is off, and the wrappers explicitly
  ensure it. The two special direct-call sites run in contexts where
  IRQs are off or preemption is already disabled.
- Aligns with existing kexec logic: Stable trees already check
  `cache_state_incoherent` during CPU stop and relocation
  (arch/x86/kernel/process.c:840,
  arch/x86/kernel/machine_kexec_64.c:449).

Dependencies/assumptions for stable trees
- Requires the per-CPU `cache_state_incoherent` infrastructure and kexec
  consumers:
  - Declaration: arch/x86/include/asm/processor.h:734
  - Definition/usage: arch/x86/kernel/process.c:99,
    arch/x86/kernel/process.c:840
  - Kexec integration: arch/x86/kernel/machine_kexec_64.c:449 and
    arch/x86/kernel/relocate_kernel_64.S (WBINVD when
    `RELOC_KERNEL_CACHE_INCOHERENT` set)

Summary
- This is a focused, low-risk bugfix preventing silent memory corruption
  on TDX hosts during kexec by correctly marking and subsequently
  flushing CPUs that might have generated dirty private cachelines
  during SEAMCALLs. It satisfies stable backport criteria (user-visible
  correctness fix, minimal change, localized impact).

 arch/x86/include/asm/tdx.h  | 25 ++++++++++++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx.c |  4 ++--
 2 files changed, 26 insertions(+), 3 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 7ddef3a698668..0922265c6bdcb 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -102,10 +102,31 @@ u64 __seamcall_ret(u64 fn, struct tdx_module_args *args);
 u64 __seamcall_saved_ret(u64 fn, struct tdx_module_args *args);
 void tdx_init(void);
 
+#include <linux/preempt.h>
 #include <asm/archrandom.h>
+#include <asm/processor.h>
 
 typedef u64 (*sc_func_t)(u64 fn, struct tdx_module_args *args);
 
+static __always_inline u64 __seamcall_dirty_cache(sc_func_t func, u64 fn,
+						  struct tdx_module_args *args)
+{
+	lockdep_assert_preemption_disabled();
+
+	/*
+	 * SEAMCALLs are made to the TDX module and can generate dirty
+	 * cachelines of TDX private memory.  Mark cache state incoherent
+	 * so that the cache can be flushed during kexec.
+	 *
+	 * This needs to be done before actually making the SEAMCALL,
+	 * because kexec-ing CPU could send NMI to stop remote CPUs,
+	 * in which case even disabling IRQ won't help here.
+	 */
+	this_cpu_write(cache_state_incoherent, true);
+
+	return func(fn, args);
+}
+
 static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
 			   struct tdx_module_args *args)
 {
@@ -113,7 +134,9 @@ static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
 	u64 ret;
 
 	do {
-		ret = func(fn, args);
+		preempt_disable();
+		ret = __seamcall_dirty_cache(func, fn, args);
+		preempt_enable();
 	} while (ret == TDX_RND_NO_ENTROPY && --retry);
 
 	return ret;
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index c7a9a087ccaf5..3ea6f587c81a3 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1266,7 +1266,7 @@ static bool paddr_is_tdx_private(unsigned long phys)
 		return false;
 
 	/* Get page type from the TDX module */
-	sret = __seamcall_ret(TDH_PHYMEM_PAGE_RDMD, &args);
+	sret = __seamcall_dirty_cache(__seamcall_ret, TDH_PHYMEM_PAGE_RDMD, &args);
 
 	/*
 	 * The SEAMCALL will not return success unless there is a
@@ -1522,7 +1522,7 @@ noinstr __flatten u64 tdh_vp_enter(struct tdx_vp *td, struct tdx_module_args *ar
 {
 	args->rcx = tdx_tdvpr_pa(td);
 
-	return __seamcall_saved_ret(TDH_VP_ENTER, args);
+	return __seamcall_dirty_cache(__seamcall_saved_ret, TDH_VP_ENTER, args);
 }
 EXPORT_SYMBOL_GPL(tdh_vp_enter);

---

## [3] Sasha Levin — 2025-10-25
*Subject: [PATCH AUTOSEL 6.17] x86/virt/tdx: Use precalculated TDVPR page physical address*

From: Kai Huang <kai.huang@intel.com>

[ Upstream commit e414b1005891d74bb0c3d27684c58dfbfbd1754b ]

All of the x86 KVM guest types (VMX, SEV and TDX) do some special context
tracking when entering guests. This means that the actual guest entry
sequence must be noinstr.

Part of entering a TDX guest is passing a physical address to the TDX
module. Right now, that physical address is stored as a 'struct page'
and converted to a physical address at guest entry. That page=>phys
conversion can be complicated, can vary greatly based on kernel
config, and it is definitely _not_ a noinstr path today.

There have been a number of tinkering approaches to try and fix this
up, but they all fall down due to some part of the page=>phys
conversion infrastructure not being noinstr friendly.

Precalculate the page=>phys conversion and store it in the existing
'tdx_vp' structure.  Use the new field at every site that needs a
tdvpr physical address. Remove the now redundant tdx_tdvpr_pa().
Remove the __flatten remnant from the tinkering.

Note that only one user of the new field is actually noinstr. All
others can use page_to_phys(). But, they might as well save the effort
since there is a pre-calculated value sitting there for them.

[ dhansen: rewrite all the text ]

Signed-off-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Dave Hansen <dave.hansen@linux.intel.com>
Reviewed-by: Kiryl Shutsemau <kas@kernel.org>
Tested-by: Farrah Chen <farrah.chen@intel.com>
Signed-off-by: Sasha Levin <sashal@kernel.org>
---

LLM Generated explanations, may be completely bogus:

YES

Rationale
- Fixes a real correctness bug in a critical noinstr path. Entering a
  TDX guest must be noinstr; previously, `tdh_vp_enter()` converted a
  `struct page` to a physical address at runtime, which is not noinstr-
  safe. The patch removes the runtime `page_to_phys()` from the guest-
  entry path and uses a precomputed physical address instead.
- Minimal, contained change in the TDX/KVM code. No ABI changes; all
  updates are internal to TDX vCPU state and seamcall wrappers.

Key Changes
- Precompute and store the TDVPR physical address:
  - Adds `phys_addr_t tdvpr_pa;` to `struct tdx_vp` to hold
    `page_to_phys(tdvpr_page)` for reuse in noinstr code:
    arch/x86/include/asm/tdx.h:171.
  - Computes and assigns the field during vCPU init, with an explicit
    comment explaining noinstr constraints: arch/x86/kvm/vmx/tdx.c:2936.
  - Clears the field on free/error paths to avoid stale use:
    arch/x86/kvm/vmx/tdx.c:855, arch/x86/kvm/vmx/tdx.c:3004.
- Make the guest entry truly noinstr:
  - `tdh_vp_enter()` now uses the precomputed `td->tdvpr_pa` and stays
    within noinstr constraints: arch/x86/virt/vmx/tdx/tdx.c:1518.
  - Also removes the `__flatten` remnant and wraps the seamcall with the
    cache-dirty helper, aligning with other TDX seamcall usage.
- Replace page->phys conversions with the precomputed value at all sites
  that use the TDVPR:
  - Updated callers pass `vp->tdvpr_pa` instead of recomputing:
    arch/x86/virt/vmx/tdx/tdx.c:1581, 1650, 1706, 1752, 1769, 1782.
  - Removes the now-redundant inline helper that did `page_to_phys()`
    for TDVPR.

Why This Fits Stable
- User impact: Fixes potential WARN/BUG and undefined behavior from
  invoking non-noinstr code in a noinstr entry path for TDX guests. This
  can affect real deployments using debug/instrumented kernels and is
  correctness-critical for a guest entry path.
- Scope and risk: Small, straightforward refactor; adds one cached field
  and replaces callers to use it. Memory lifetime is well-defined (page
  is allocated at init and reclaimed at teardown), and the physical
  address of a page is stable; zeroing on teardown/error prevents stale
  usage.
- No feature or architectural changes; KVM/TDX only. No user-visible ABI
  changes. The seamcall helper infrastructure (`__seamcall_dirty_cache`,
  `__seamcall_saved_ret`) is already present in this subsystem.
- Reviewed and tested upstream (Reviewed-by/Tested-by tags), and
  consistent with prior attempts to fix noinstr issues (this replaces
  earlier, more fragile approaches like `__flatten`).

Conclusion
- This is a low-risk, correctness fix to a critical guest-entry path,
  improving noinstr compliance. It should be backported to stable
  kernels that have TDX support.

 arch/x86/include/asm/tdx.h  |  2 ++
 arch/x86/kvm/vmx/tdx.c      |  9 +++++++++
 arch/x86/virt/vmx/tdx/tdx.c | 21 ++++++++-------------
 3 files changed, 19 insertions(+), 13 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 0922265c6bdcb..17a051d9c9398 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -169,6 +169,8 @@ struct tdx_td {
 struct tdx_vp {
 	/* TDVP root page */
 	struct page *tdvpr_page;
+	/* precalculated page_to_phys(tdvpr_page) for use in noinstr code */
+	phys_addr_t tdvpr_pa;
 
 	/* TD vCPU control structure: */
 	struct page **tdcx_pages;
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index d91d9d6bb26c1..987c0eb10545c 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -861,6 +861,7 @@ void tdx_vcpu_free(struct kvm_vcpu *vcpu)
 	if (tdx->vp.tdvpr_page) {
 		tdx_reclaim_control_page(tdx->vp.tdvpr_page);
 		tdx->vp.tdvpr_page = 0;
+		tdx->vp.tdvpr_pa = 0;
 	}
 
 	tdx->state = VCPU_TD_STATE_UNINITIALIZED;
@@ -2940,6 +2941,13 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 		return -ENOMEM;
 	tdx->vp.tdvpr_page = page;
 
+	/*
+	 * page_to_phys() does not work in 'noinstr' code, like guest
+	 * entry via tdh_vp_enter(). Precalculate and store it instead
+	 * of doing it at runtime later.
+	 */
+	tdx->vp.tdvpr_pa = page_to_phys(tdx->vp.tdvpr_page);
+
 	tdx->vp.tdcx_pages = kcalloc(kvm_tdx->td.tdcx_nr_pages, sizeof(*tdx->vp.tdcx_pages),
 			       	     GFP_KERNEL);
 	if (!tdx->vp.tdcx_pages) {
@@ -3002,6 +3010,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 	if (tdx->vp.tdvpr_page)
 		__free_page(tdx->vp.tdvpr_page);
 	tdx->vp.tdvpr_page = 0;
+	tdx->vp.tdvpr_pa = 0;
 
 	return ret;
 }
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 3ea6f587c81a3..b54581a795f5b 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1502,11 +1502,6 @@ static inline u64 tdx_tdr_pa(struct tdx_td *td)
 	return page_to_phys(td->tdr_page);
 }
 
-static inline u64 tdx_tdvpr_pa(struct tdx_vp *td)
-{
-	return page_to_phys(td->tdvpr_page);
-}
-
 /*
  * The TDX module exposes a CLFLUSH_BEFORE_ALLOC bit to specify whether
  * a CLFLUSH of pages is required before handing them to the TDX module.
@@ -1518,9 +1513,9 @@ static void tdx_clflush_page(struct page *page)
 	clflush_cache_range(page_to_virt(page), PAGE_SIZE);
 }
 
-noinstr __flatten u64 tdh_vp_enter(struct tdx_vp *td, struct tdx_module_args *args)
+noinstr u64 tdh_vp_enter(struct tdx_vp *td, struct tdx_module_args *args)
 {
-	args->rcx = tdx_tdvpr_pa(td);
+	args->rcx = td->tdvpr_pa;
 
 	return __seamcall_dirty_cache(__seamcall_saved_ret, TDH_VP_ENTER, args);
 }
@@ -1581,7 +1576,7 @@ u64 tdh_vp_addcx(struct tdx_vp *vp, struct page *tdcx_page)
 {
 	struct tdx_module_args args = {
 		.rcx = page_to_phys(tdcx_page),
-		.rdx = tdx_tdvpr_pa(vp),
+		.rdx = vp->tdvpr_pa,
 	};
 
 	tdx_clflush_page(tdcx_page);
@@ -1650,7 +1645,7 @@ EXPORT_SYMBOL_GPL(tdh_mng_create);
 u64 tdh_vp_create(struct tdx_td *td, struct tdx_vp *vp)
 {
 	struct tdx_module_args args = {
-		.rcx = tdx_tdvpr_pa(vp),
+		.rcx = vp->tdvpr_pa,
 		.rdx = tdx_tdr_pa(td),
 	};
 
@@ -1706,7 +1701,7 @@ EXPORT_SYMBOL_GPL(tdh_mr_finalize);
 u64 tdh_vp_flush(struct tdx_vp *vp)
 {
 	struct tdx_module_args args = {
-		.rcx = tdx_tdvpr_pa(vp),
+		.rcx = vp->tdvpr_pa,
 	};
 
 	return seamcall(TDH_VP_FLUSH, &args);
@@ -1752,7 +1747,7 @@ EXPORT_SYMBOL_GPL(tdh_mng_init);
 u64 tdh_vp_rd(struct tdx_vp *vp, u64 field, u64 *data)
 {
 	struct tdx_module_args args = {
-		.rcx = tdx_tdvpr_pa(vp),
+		.rcx = vp->tdvpr_pa,
 		.rdx = field,
 	};
 	u64 ret;
@@ -1769,7 +1764,7 @@ EXPORT_SYMBOL_GPL(tdh_vp_rd);
 u64 tdh_vp_wr(struct tdx_vp *vp, u64 field, u64 data, u64 mask)
 {
 	struct tdx_module_args args = {
-		.rcx = tdx_tdvpr_pa(vp),
+		.rcx = vp->tdvpr_pa,
 		.rdx = field,
 		.r8 = data,
 		.r9 = mask,
@@ -1782,7 +1777,7 @@ EXPORT_SYMBOL_GPL(tdh_vp_wr);
 u64 tdh_vp_init(struct tdx_vp *vp, u64 initial_rcx, u32 x2apicid)
 {
 	struct tdx_module_args args = {
-		.rcx = tdx_tdvpr_pa(vp),
+		.rcx = vp->tdvpr_pa,
 		.rdx = initial_rcx,
 		.r8 = x2apicid,
 	};

---

## [4] Huang, Kai — 2025-10-26
*Subject: Re: [PATCH AUTOSEL 6.17] x86/kexec: Disable kexec/kdump on platforms
 with TDX partial write erratum*

On Sat, 2025-10-25 at 11:58 -0400, Sasha Levin wrote:
> From: Kai Huang <kai.huang@intel.com>
> 

[...]

> ---
> 

Hi,

I don't think we should backport this for 6.17 stable.  Kexec/kdump and
TDX are mutually exclusive in Kconfig in 6.17, therefore it's not possible
for TDX to impact kexec/kdump.

This patch is part of the series which enables kexec/kdump together with
TDX in Kconfig (which landed in 6.18) and should not be backported alone.

---

## [5] Huang, Kai — 2025-10-26
*Subject: Re: [PATCH AUTOSEL 6.17] x86/virt/tdx: Mark memory cache state
 incoherent when making SEAMCALL*

On Sat, 2025-10-25 at 11:59 -0400, Sasha Levin wrote:
> From: Kai Huang <kai.huang@intel.com>
> 
[...]

> ---
> 


Hi,

I don't think we should backport this for 6.17 stable.  Kexec/kdump and
TDX are mutually exclusive in Kconfig in 6.17, therefore it's not possible
for TDX to impact kexec/kdump.

This patch is part of the series which enables kexec/kdump together with
TDX in Kconfig (which landed in 6.18) and should not be backported alone.

---

## [6] Sasha Levin — 2025-10-28
*Subject: Re: [PATCH AUTOSEL 6.17] x86/virt/tdx: Mark memory cache state
 incoherent when making SEAMCALL*

On Sun, Oct 26, 2025 at 10:25:02PM +0000, Huang, Kai wrote:
>On Sat, 2025-10-25 at 11:59 -0400, Sasha Levin wrote:
>> From: Kai Huang <kai.huang@intel.com>

I'll drop it, thanks for the review!

---

## [7] Huang, Kai — 2025-11-03
*Subject: Re: [PATCH AUTOSEL 6.17] x86/kexec: Disable kexec/kdump on platforms
 with TDX partial write erratum*

On Sun, 2025-10-26 at 22:24 +0000, Huang, Kai wrote:
> On Sat, 2025-10-25 at 11:58 -0400, Sasha Levin wrote:
> > From: Kai Huang <kai.huang@intel.com>

Hi Sasha,

Just a reminder that this patch should be dropped from stable kernel too
(just in case you missed, since I didn't get any further notice).

---

## [8] Sasha Levin — 2025-11-04
*Subject: Re: [PATCH AUTOSEL 6.17] x86/kexec: Disable kexec/kdump on platforms
 with TDX partial write erratum*

On Mon, Nov 03, 2025 at 09:26:38AM +0000, Huang, Kai wrote:
>On Sun, 2025-10-26 at 22:24 +0000, Huang, Kai wrote:
>> On Sat, 2025-10-25 at 11:58 -0400, Sasha Levin wrote:

Now dropped, thanks!

---

## [9] Huang, Kai — 2025-11-04
*Subject: RE: [PATCH AUTOSEL 6.17] x86/kexec: Disable kexec/kdump on platforms
 with TDX partial write erratum*

> >Hi Sasha,
> >

Thanks!

---
