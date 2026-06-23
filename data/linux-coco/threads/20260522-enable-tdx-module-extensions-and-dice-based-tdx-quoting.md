---
title: 'Enable TDX Module Extensions and DICE-based TDX Quoting'
date: 2026-05-22
last_reply: 2026-06-16
message_count: 113
participants: ['Xu Yilun', 'Tony Lindgren', 'Xiaoyao Li', 'Sohil Mehta', 'Kiryl Shutsemau', 'Edgecombe, Rick P', 'Kishen Maloor', 'Adrian Hunter', 'Dan Williams (nvidia)', 'Peter Fang', 'Dave Hansen']
---

## [1] Xu Yilun — 2026-05-22

This posting is just to collect initial review.

Sean, Paolo, Dave please feel free to ignore for now. Sean, especially
the x86 KVM stuff is only here as an example for the init code, and not
ready for review.

Kiryl and Dan, we are trying to get acks for the first 4 patches of the
series so they can be serve as a settled base for all the other work
that uses Extensions. Please review the first 4 patches and treat the
later ones as an example for the Extensions initialization.

== Why it's being posted ==

The TDX Module is introducing a new concept called "TDX Module
Extensions", and several upcoming features depend on them. The
Extensions need some extra setup at TDX module init time, and the code
to do this is expected to be somewhat generic.

We want to get the basics of this TDX module extensions piece sorted so
that all of the extension-based work can build on it. This series
includes those basics, and an example usage called DICE-based TDX
Quoting. Only the first 4 patches are about initializing the TDX module
Extensions. I'd like some review on them. The later DICE patches are
just included to serve as a usage example for the TDX module extension
code.

The first 4 patches will eventually need an ack by an x86 maintainer, so
please review with that in mind.

== Overview ==

TDX Module introduces the "TDX Module Extensions" to support long
running / hard-irq preemptible flows inside. This makes TDX Module
capable of handling complex tasks through "Extension SEAMCALLs".

TDX Module allows some add-on features to use the Extension. The first
feature to use Extensions is DICE-based TDX Quoting [1]. DICE is an
industry-standard, certificate-backed attestation framework that layers
evidence through a chain of certificates.

This series adds infrastructure to enable the Extensions and then
implement DICE-based TDX Quoting.

The Extensions consumes relatively large amount of memory (~50MB). So it
is designed to be off by default. It must be enabled after basic TDX
Module initialization and when add-on features require it. To enable
the Extensions, host first adds extra memory to TDX Module via a
SEAMCALL (TDH.EXT.MEM.ADD), then uses another SEAMCALL (TDH.EXT.INIT) to
initialize Extensions, and then some add-on features, e.g. DICE, could
use Extension SEAMCALLs for work. Note that host can never get the added
memory back.

Theoretically, the Extensions doesn't need to be enabled right after
basic TDX initialization. It could be enabled right before the first
Extension SEAMCALL is issued. That would save or postpone memory usage.
But it isn't worth the complexity, the needs for the Extensions are vast
but the savings are little for a typical TDX capable system (about
0.001% of memory). So the Linux decision is to just enable it along with
the basic TDX.

This series has 2 distinct parts:

  Patches  1-4:  TDX Module Extensions enabling
  Patches  5-15: DICE-based TDX Quoting, primarily Peter's work.

== Some history ==

The TDX Module Extensions part was first posted along with TDX
Connect [2]. Now this part is remarkably smaller because we've removed
the generic tdx_page_array abstraction for HPA_LIST_INFO. TDX Module
Extensions is the first user of HPA_LIST_INFO, and doesn't use it in a
typical way (HPA_LIST_INFO can only hold at most 2MB memory). There
isn't enough justification to make the abstraction in this series. A
possible plan is to rebuild tdx_page_array iteratively when more use
cases arise.

== Misc ==

This series is based on tip/x86/tdx [3], because we need a small
being-merged patch [4] before our work.


Link: https://cdrdv2.intel.com/v1/dl/getContent/874303 # [1]
Link: https://lore.kernel.org/all/20260327160132.2946114-1-yilun.xu@linux.intel.com/ # [2]
Link: https://git.kernel.org/pub/scm/linux/kernel/git/tip/tip.git/log/?h=x86/tdx # [3]
Link: https://patch.msgid.link/20260402-fuller_tdx_kexec_support-v3-1-34438d7094bf@intel.com # [4]


Peter Fang (10):
  x86/virt/tdx: Move tdx_tdr_pa() up in the file
  x86/virt/tdx: Initialize Quoting extension during bringup
  x86/virt/tdx: Prepare Quote buffer during extension bringup
  x86/virt/tdx: Add interface to check Quoting availability
  x86/virt/tdx: Add interface to generate a Quote
  x86/tdx: Move and rename Quote request structure
  KVM: TDX: Factor out userspace return path from tdx_get_quote()
  KVM: TDX: Add in-kernel Quote generation
  KVM: TDX: Support event-notify interrupts only with userspace quoting
  x86/virt/tdx: Enable TDX Quoting extension

Xu Yilun (5):
  x86/virt/tdx: Read global metadata for TDX Module Extensions
  x86/virt/tdx: Add extra memory to TDX Module for Extensions
  x86/virt/tdx: Make TDX Module initialize Extensions
  x86/virt/tdx: Enable the Extensions right after basic TDX Module init
  x86/virt/tdx: Embed version info in SEAMCALL leaf function definitions

 Documentation/virt/kvm/api.rst              |   8 +-
 arch/x86/include/asm/tdx.h                  |  34 ++
 arch/x86/include/asm/tdx_global_metadata.h  |  11 +
 arch/x86/kvm/vmx/tdx.h                      |   6 +
 arch/x86/virt/vmx/tdx/tdx.h                 |  32 +-
 arch/x86/kvm/vmx/tdx.c                      | 176 ++++++++-
 arch/x86/virt/vmx/tdx/tdx.c                 | 387 +++++++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |  27 ++
 drivers/virt/coco/tdx-guest/tdx-guest.c     |  25 +-
 virt/kvm/kvm_main.c                         |   1 +
 10 files changed, 655 insertions(+), 52 deletions(-)


base-commit: 5209e5bfe5cab593476c3e7754e42c5e47ce36de

---

## [2] Xu Yilun — 2026-05-22
*Subject: [PATCH 01/15] x86/virt/tdx: Read global metadata for TDX Module Extensions*

Add reading of the global metadata for TDX Module Extensions.

TDX Module Extensions is an add-on feature enumerated by TDX_FEATURES0.
But for the Module's integrity, Linux requires that all features that a
Module advertises must have a complete, valid set of metadata, and the
validation must succeed at core TDX initialization time.

Check TDX_FEATURES0 before reading these metadata. If a feature is
advertised, a failure in reading associated metadata causes the entire
TDX initialization to fail, otherwise skip.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/include/asm/tdx_global_metadata.h  |  6 ++++++
 arch/x86/virt/vmx/tdx/tdx.h                 |  1 +
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c | 16 ++++++++++++++++
 3 files changed, 23 insertions(+)

diff --git a/arch/x86/include/asm/tdx_global_metadata.h b/arch/x86/include/asm/tdx_global_metadata.h
index 40689c8dc67e..533afe50a3f1 100644
--- a/arch/x86/include/asm/tdx_global_metadata.h
+++ b/arch/x86/include/asm/tdx_global_metadata.h
@@ -40,12 +40,18 @@ struct tdx_sys_info_td_conf {
 	u64 cpuid_config_values[128][2];
 };
 
+struct tdx_sys_info_ext {
+	u16 memory_pool_required_pages;
+	u8 ext_required;
+};
+
 struct tdx_sys_info {
 	struct tdx_sys_info_version version;
 	struct tdx_sys_info_features features;
 	struct tdx_sys_info_tdmr tdmr;
 	struct tdx_sys_info_td_ctrl td_ctrl;
 	struct tdx_sys_info_td_conf td_conf;
+	struct tdx_sys_info_ext ext;
 };
 
 #endif
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index e2cf2dd48755..a5eec8e3cc71 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -87,6 +87,7 @@ struct tdmr_info {
 
 /* Bit definitions of TDX_FEATURES0 metadata field */
 #define TDX_FEATURES0_NO_RBP_MOD	BIT(18)
+#define TDX_FEATURES0_EXT		BIT_ULL(39)
 
 /*
  * Do not put any hardware-defined TDX structure representations below
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index c7db393a9cfb..3d3b56ef3d2f 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -100,6 +100,19 @@ static __init int get_tdx_sys_info_td_conf(struct tdx_sys_info_td_conf *sysinfo_
 	return ret;
 }
 
+static __init int get_tdx_sys_info_ext(struct tdx_sys_info_ext *sysinfo_ext)
+{
+	int ret = 0;
+	u64 val;
+
+	if (!ret && !(ret = read_sys_metadata_field(0x3100000100000000, &val)))
+		sysinfo_ext->memory_pool_required_pages = val;
+	if (!ret && !(ret = read_sys_metadata_field(0x3100000000000001, &val)))
+		sysinfo_ext->ext_required = val;
+
+	return ret;
+}
+
 static __init int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 {
 	int ret = 0;
@@ -116,5 +129,8 @@ static __init int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 	ret = ret ?: get_tdx_sys_info_td_ctrl(&sysinfo->td_ctrl);
 	ret = ret ?: get_tdx_sys_info_td_conf(&sysinfo->td_conf);
 
+	if (sysinfo->features.tdx_features0 & TDX_FEATURES0_EXT)
+		ret = ret ?: get_tdx_sys_info_ext(&sysinfo->ext);
+
 	return ret;
 }

---

## [3] Xu Yilun — 2026-05-22
*Subject: [PATCH 02/15] x86/virt/tdx: Add extra memory to TDX Module for Extensions*

TDX Module introduces a new concept called "TDX Module Extensions" to
support long running / hard-irq preemptible flows inside. This makes TDX
Module capable of handling complex tasks through "Extension SEAMCALLs".
Adding more memory to TDX Module is the first step to enable Extensions.

Currently, TDX Module memory use is relatively static. But, the
Extensions need to use memory more dynamically. While 'static' here
means the kernel provides necessary amount of memory to TDX Module for
its basic functionalities, 'dynamic' means extra memory is needed only
if new add-on features are to be enabled. So add a new memory feeding
process backed by a new SEAMCALL TDH.EXT.MEM.ADD.

The process is mostly the same as adding PAMT. The kernel queries TDX
Module how much memory needed, allocates it, hands it over, and never
gets it back.

TDH.EXT.MEM.ADD uses a new parameter type HPA_LIST_INFO to provide
control (private) pages to TDX Module. This type represents a list of
pages for TDX Module to access. It needs a 'root page' which contains
the list of HPAs of the pages. It collapses the HPA of the root page
and the number of valid HPAs into a 64 bit raw value for SEAMCALL
parameters. The root page is always a medium, TDX Module never keeps
the root page.

Introduce a tdx_clflush_hpa_list() helper to flush shared cache before
SEAMCALL, to avoid shared cache writeback damaging these private pages.

For now, TDX Module Extensions consumes relatively large amount of
memory (~50MB). Use contiguous page allocation to avoid permanently
fragment too much memory. Print the allocation amount on TDX Module
Extensions initialization for visibility.

Co-developed-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.h |   1 +
 arch/x86/virt/vmx/tdx/tdx.c | 118 ++++++++++++++++++++++++++++++++++++
 2 files changed, 119 insertions(+)

diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index a5eec8e3cc71..2335f88bbb10 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -46,6 +46,7 @@
 #define TDH_PHYMEM_PAGE_WBINVD		41
 #define TDH_VP_WR			43
 #define TDH_SYS_CONFIG			45
+#define TDH_EXT_MEM_ADD			61
 #define TDH_SYS_DISABLE			69
 
 /*
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index c0c6281b08a5..622399d8da68 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -31,6 +31,7 @@
 #include <linux/syscore_ops.h>
 #include <linux/idr.h>
 #include <linux/kvm_types.h>
+#include <linux/bitfield.h>
 #include <asm/page.h>
 #include <asm/special_insns.h>
 #include <asm/msr-index.h>
@@ -1179,6 +1180,123 @@ static __init int init_tdmrs(struct tdmr_info_list *tdmr_list)
 	return 0;
 }
 
+static void tdx_clflush_hpa_list(struct page *root, unsigned int nr_pages)
+{
+	u64 *entries = page_to_virt(root);
+	int i;
+
+	for (i = 0; i < nr_pages; i++)
+		clflush_cache_range(__va(entries[i]), PAGE_SIZE);
+}
+
+#define HPA_LIST_INFO_FIRST_ENTRY	GENMASK_U64(11, 3)
+#define HPA_LIST_INFO_PFN		GENMASK_U64(51, 12)
+#define HPA_LIST_INFO_LAST_ENTRY	GENMASK_U64(63, 55)
+
+static u64 to_hpa_list_info(struct page *root, unsigned int nr_pages)
+{
+	return FIELD_PREP(HPA_LIST_INFO_FIRST_ENTRY, 0) |
+	       FIELD_PREP(HPA_LIST_INFO_PFN, page_to_pfn(root)) |
+	       FIELD_PREP(HPA_LIST_INFO_LAST_ENTRY, nr_pages - 1);
+}
+
+static int tdx_ext_mem_add(struct page *root, unsigned int nr_pages)
+{
+	struct tdx_module_args args = {
+		.rcx = to_hpa_list_info(root, nr_pages),
+	};
+	u64 r;
+
+	tdx_clflush_hpa_list(root, nr_pages);
+
+	do {
+		/*
+		 * TDH_EXT_MEM_ADD is designed to use output parameter RCX to
+		 * override/update input parameter RCX, so the caller doesn't
+		 * have to do manual parameter update on retry call.
+		 */
+		r = seamcall_ret(TDH_EXT_MEM_ADD, &args);
+	} while (r == TDX_INTERRUPTED_RESUMABLE);
+
+	if (r != TDX_SUCCESS)
+		return -EFAULT;
+
+	return 0;
+}
+
+static int tdx_ext_mem_setup(void)
+{
+	unsigned int nr_pages;
+	struct page *page;
+	u64 *root;
+	unsigned int i;
+	int ret;
+
+	nr_pages = tdx_sysinfo.ext.memory_pool_required_pages;
+	/*
+	 * memory_pool_required_pages == 0 means no need to add pages,
+	 * skip the memory setup.
+	 */
+	if (!nr_pages)
+		return 0;
+
+	root = kzalloc(PAGE_SIZE, GFP_KERNEL);
+	if (!root)
+		return -ENOMEM;
+
+	page = alloc_contig_pages(nr_pages, GFP_KERNEL, numa_mem_id(),
+				  &node_online_map);
+	if (!page) {
+		ret = -ENOMEM;
+		goto out_free_root;
+	}
+
+	for (i = 0; i < nr_pages;) {
+		unsigned int nents = min(nr_pages - i,
+					 PAGE_SIZE / sizeof(*root));
+		int j;
+
+		for (j = 0; j < nents; j++)
+			root[j] = page_to_phys(page + i + j);
+
+		ret = tdx_ext_mem_add(virt_to_page(root), nents);
+		/*
+		 * No SEAMCALLs to reclaim the added pages. For simple error
+		 * handling, leak all pages.
+		 */
+		WARN_ON_ONCE(ret);
+		if (ret)
+			break;
+
+		i += nents;
+	}
+
+	/*
+	 * Extensions memory can't be reclaimed once added, print out the
+	 * amount, stop tracking it and free the root page, no matter success
+	 * or failure.
+	 */
+	pr_info("%lu KB allocated for TDX Module Extensions\n",
+		nr_pages * PAGE_SIZE / 1024);
+
+out_free_root:
+	kfree(root);
+
+	return ret;
+}
+
+static int __maybe_unused init_tdx_ext(void)
+{
+	if (!(tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_EXT))
+		return 0;
+
+	/* No feature requires TDX Module Extensions. */
+	if (!tdx_sysinfo.ext.ext_required)
+		return 0;
+
+	return tdx_ext_mem_setup();
+}
+
 static __init int init_tdx_module(void)
 {
 	int ret;

---

## [4] Xu Yilun — 2026-05-22
*Subject: [PATCH 03/15] x86/virt/tdx: Make TDX Module initialize Extensions*

After providing all required memory to TDX Module, initialize TDX
Module Extensions via TDH.EXT.INIT, so Extension-SEAMCALLs can be used.

Co-developed-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.h |  1 +
 arch/x86/virt/vmx/tdx/tdx.c | 24 +++++++++++++++++++++++-
 2 files changed, 24 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 2335f88bbb10..c5bffd118145 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -46,6 +46,7 @@
 #define TDH_PHYMEM_PAGE_WBINVD		41
 #define TDH_VP_WR			43
 #define TDH_SYS_CONFIG			45
+#define TDH_EXT_INIT			60
 #define TDH_EXT_MEM_ADD			61
 #define TDH_SYS_DISABLE			69
 
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 622399d8da68..ff2b96c20d2b 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1200,6 +1200,22 @@ static u64 to_hpa_list_info(struct page *root, unsigned int nr_pages)
 	       FIELD_PREP(HPA_LIST_INFO_LAST_ENTRY, nr_pages - 1);
 }
 
+/* Initialize the TDX Module Extensions then Extension-SEAMCALLs can be used */
+static int tdx_ext_init(void)
+{
+	struct tdx_module_args args = {};
+	u64 r;
+
+	do {
+		r = seamcall(TDH_EXT_INIT, &args);
+	} while (r == TDX_INTERRUPTED_RESUMABLE);
+
+	if (r != TDX_SUCCESS)
+		return -EFAULT;
+
+	return 0;
+}
+
 static int tdx_ext_mem_add(struct page *root, unsigned int nr_pages)
 {
 	struct tdx_module_args args = {
@@ -1287,6 +1303,8 @@ static int tdx_ext_mem_setup(void)
 
 static int __maybe_unused init_tdx_ext(void)
 {
+	int ret;
+
 	if (!(tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_EXT))
 		return 0;
 
@@ -1294,7 +1312,11 @@ static int __maybe_unused init_tdx_ext(void)
 	if (!tdx_sysinfo.ext.ext_required)
 		return 0;
 
-	return tdx_ext_mem_setup();
+	ret = tdx_ext_mem_setup();
+	if (ret)
+		return ret;
+
+	return tdx_ext_init();
 }
 
 static __init int init_tdx_module(void)

---

## [5] Xu Yilun — 2026-05-22
*Subject: [PATCH 04/15] x86/virt/tdx: Enable the Extensions right after basic TDX Module init*

The detailed initialization flow for TDX Module Extensions has been
fully implemented. Enable the flow after basic TDX Module
initialization.

Theoretically, the Extensions doesn't need to be enabled right after
basic TDX initialization. It could be enabled right before the first
Extension SEAMCALL is issued. That would save or postpone memory usage.
But it isn't worth the complexity, the needs for the Extensions are vast
but the savings are little for a typical TDX capable system (about
0.001% of memory). So the Linux decision is to just enable it along with
the basic TDX.

Note that the Extensions initialization flow will still not start if no
add-on features require Extensions. The enabling of add-on features will
be in later patches. Until then, the system hasn't consumed extra memory.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 16 ++++++++++------
 1 file changed, 10 insertions(+), 6 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index ff2b96c20d2b..dad5ec642723 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1180,7 +1180,7 @@ static __init int init_tdmrs(struct tdmr_info_list *tdmr_list)
 	return 0;
 }
 
-static void tdx_clflush_hpa_list(struct page *root, unsigned int nr_pages)
+static __init void tdx_clflush_hpa_list(struct page *root, unsigned int nr_pages)
 {
 	u64 *entries = page_to_virt(root);
 	int i;
@@ -1193,7 +1193,7 @@ static void tdx_clflush_hpa_list(struct page *root, unsigned int nr_pages)
 #define HPA_LIST_INFO_PFN		GENMASK_U64(51, 12)
 #define HPA_LIST_INFO_LAST_ENTRY	GENMASK_U64(63, 55)
 
-static u64 to_hpa_list_info(struct page *root, unsigned int nr_pages)
+static __init u64 to_hpa_list_info(struct page *root, unsigned int nr_pages)
 {
 	return FIELD_PREP(HPA_LIST_INFO_FIRST_ENTRY, 0) |
 	       FIELD_PREP(HPA_LIST_INFO_PFN, page_to_pfn(root)) |
@@ -1201,7 +1201,7 @@ static u64 to_hpa_list_info(struct page *root, unsigned int nr_pages)
 }
 
 /* Initialize the TDX Module Extensions then Extension-SEAMCALLs can be used */
-static int tdx_ext_init(void)
+static __init int tdx_ext_init(void)
 {
 	struct tdx_module_args args = {};
 	u64 r;
@@ -1216,7 +1216,7 @@ static int tdx_ext_init(void)
 	return 0;
 }
 
-static int tdx_ext_mem_add(struct page *root, unsigned int nr_pages)
+static __init int tdx_ext_mem_add(struct page *root, unsigned int nr_pages)
 {
 	struct tdx_module_args args = {
 		.rcx = to_hpa_list_info(root, nr_pages),
@@ -1240,7 +1240,7 @@ static int tdx_ext_mem_add(struct page *root, unsigned int nr_pages)
 	return 0;
 }
 
-static int tdx_ext_mem_setup(void)
+static __init int tdx_ext_mem_setup(void)
 {
 	unsigned int nr_pages;
 	struct page *page;
@@ -1301,7 +1301,7 @@ static int tdx_ext_mem_setup(void)
 	return ret;
 }
 
-static int __maybe_unused init_tdx_ext(void)
+static __init int init_tdx_ext(void)
 {
 	int ret;
 
@@ -1373,6 +1373,10 @@ static __init int init_tdx_module(void)
 	if (ret)
 		goto err_reset_pamts;
 
+	ret = init_tdx_ext();
+	if (ret)
+		goto err_reset_pamts;
+
 	pr_info("%lu KB allocated for PAMT\n", tdmrs_count_pamt_kb(&tdx_tdmr_list));
 
 out_put_tdxmem:

---

## [6] Xu Yilun — 2026-05-22
*Subject: [RFC PATCH 05/15] x86/virt/tdx: Move tdx_tdr_pa() up in the file*

From: Peter Fang <peter.fang@intel.com>

Move the tdx_tdr_pa() in preparation for upcoming changes to use them
during TDX bringup.

No functional change intended.

Signed-off-by: Peter Fang <peter.fang@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 10 +++++-----
 1 file changed, 5 insertions(+), 5 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index dad5ec642723..67758adefb4a 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1200,6 +1200,11 @@ static __init u64 to_hpa_list_info(struct page *root, unsigned int nr_pages)
 	       FIELD_PREP(HPA_LIST_INFO_LAST_ENTRY, nr_pages - 1);
 }
 
+static inline u64 tdx_tdr_pa(struct tdx_td *td)
+{
+	return page_to_phys(td->tdr_page);
+}
+
 /* Initialize the TDX Module Extensions then Extension-SEAMCALLs can be used */
 static __init int tdx_ext_init(void)
 {
@@ -1725,11 +1730,6 @@ void tdx_guest_keyid_free(unsigned int keyid)
 }
 EXPORT_SYMBOL_FOR_KVM(tdx_guest_keyid_free);
 
-static inline u64 tdx_tdr_pa(struct tdx_td *td)
-{
-	return page_to_phys(td->tdr_page);
-}
-
 /*
  * The TDX module exposes a CLFLUSH_BEFORE_ALLOC bit to specify whether
  * a CLFLUSH of pages is required before handing them to the TDX module.

---

## [7] Xu Yilun — 2026-05-22
*Subject: [RFC PATCH 06/15] x86/virt/tdx: Initialize Quoting extension during bringup*

From: Peter Fang <peter.fang@intel.com>

Initialize the Quoting extension and fetch its metadata during TDX
bringup.

Because Quoting is an optional TDX feature, do not let its
initialization failures cause TDX bringup to fail.

This patch does not include the opt-in portion of the initialization.
It mainly lays the groundwork for TDX Quoting support. Opt-in will be
added in a follow-up patch once the feature can be properly used by the
system.

Signed-off-by: Peter Fang <peter.fang@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/include/asm/tdx_global_metadata.h  |  5 ++++
 arch/x86/virt/vmx/tdx/tdx.h                 |  1 +
 arch/x86/virt/vmx/tdx/tdx.c                 | 29 ++++++++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c | 11 ++++++++
 4 files changed, 45 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/tdx_global_metadata.h b/arch/x86/include/asm/tdx_global_metadata.h
index 533afe50a3f1..04f515cd4c1d 100644
--- a/arch/x86/include/asm/tdx_global_metadata.h
+++ b/arch/x86/include/asm/tdx_global_metadata.h
@@ -45,6 +45,10 @@ struct tdx_sys_info_ext {
 	u8 ext_required;
 };
 
+struct tdx_sys_info_quote {
+	u32 max_quote_size;
+};
+
 struct tdx_sys_info {
 	struct tdx_sys_info_version version;
 	struct tdx_sys_info_features features;
@@ -52,6 +56,7 @@ struct tdx_sys_info {
 	struct tdx_sys_info_td_ctrl td_ctrl;
 	struct tdx_sys_info_td_conf td_conf;
 	struct tdx_sys_info_ext ext;
+	struct tdx_sys_info_quote quote;
 };
 
 #endif
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index c5bffd118145..3849f4f9cc78 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -49,6 +49,7 @@
 #define TDH_EXT_INIT			60
 #define TDH_EXT_MEM_ADD			61
 #define TDH_SYS_DISABLE			69
+#define TDH_QUOTE_INIT			100
 
 /*
  * SEAMCALL leaf:
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 67758adefb4a..fb84fb6d952b 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1205,6 +1205,22 @@ static inline u64 tdx_tdr_pa(struct tdx_td *td)
 	return page_to_phys(td->tdr_page);
 }
 
+static void tdx_quote_init(void)
+{
+	struct tdx_module_args args = {};
+	u64 r;
+
+	do {
+		r = seamcall(TDH_QUOTE_INIT, &args);
+	} while (r == TDX_INTERRUPTED_RESUMABLE);
+
+	if (r)
+		return;
+
+	/* Quoting metadata is valid only after initialization */
+	get_tdx_sys_info_quote(&tdx_sysinfo.quote);
+}
+
 /* Initialize the TDX Module Extensions then Extension-SEAMCALLs can be used */
 static __init int tdx_ext_init(void)
 {
@@ -1306,6 +1322,13 @@ static __init int tdx_ext_mem_setup(void)
 	return ret;
 }
 
+static int init_tdx_ext_features(void)
+{
+	tdx_quote_init();
+
+	return 0;
+}
+
 static __init int init_tdx_ext(void)
 {
 	int ret;
@@ -1321,7 +1344,11 @@ static __init int init_tdx_ext(void)
 	if (ret)
 		return ret;
 
-	return tdx_ext_init();
+	ret = tdx_ext_init();
+	if (ret)
+		return ret;
+
+	return init_tdx_ext_features();
 }
 
 static __init int init_tdx_module(void)
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index 3d3b56ef3d2f..f9cc2dd02caf 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -113,6 +113,17 @@ static __init int get_tdx_sys_info_ext(struct tdx_sys_info_ext *sysinfo_ext)
 	return ret;
 }
 
+static int get_tdx_sys_info_quote(struct tdx_sys_info_quote *sysinfo_quote)
+{
+	int ret = 0;
+	u64 val;
+
+	if (!ret && !(ret = read_sys_metadata_field(0x2300000200000002, &val)))
+		sysinfo_quote->max_quote_size = val;
+
+	return ret;
+}
+
 static __init int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 {
 	int ret = 0;

---

## [8] Xu Yilun — 2026-05-22
*Subject: [RFC PATCH 07/15] x86/virt/tdx: Prepare Quote buffer during extension bringup*

From: Peter Fang <peter.fang@intel.com>

The host uses a Quote buffer to communicate with the TDX module when
generating Quotes. Because the Quote buffer is shared with TDX guests,
prepare the required metadata during Quoting extension bringup.

This mostly involves determining the physical addresses of the Quote
buffer pages and arranging them in the HPA_LINKED_LIST format defined by
the Intel TDX Module ABI specification.

Signed-off-by: Peter Fang <peter.fang@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 85 ++++++++++++++++++++++++++++++++++++-
 1 file changed, 84 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index fb84fb6d952b..9d04293394d7 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -32,6 +32,7 @@
 #include <linux/idr.h>
 #include <linux/kvm_types.h>
 #include <linux/bitfield.h>
+#include <linux/vmalloc.h>
 #include <asm/page.h>
 #include <asm/special_insns.h>
 #include <asm/msr-index.h>
@@ -61,6 +62,13 @@ static LIST_HEAD(tdx_memlist);
 static struct tdx_sys_info tdx_sysinfo __ro_after_init;
 static bool tdx_module_initialized __ro_after_init;
 
+static struct quote_data {
+	void *buf;
+	u64 buf_len;
+	u64 *hpa_list;
+	phys_addr_t hpa_list_pa;
+} quote_data;
+
 typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);
 
 static inline void seamcall_err(u64 fn, u64 err, struct tdx_module_args *args)
@@ -1205,9 +1213,78 @@ static inline u64 tdx_tdr_pa(struct tdx_td *td)
 	return page_to_phys(td->tdr_page);
 }
 
+#define HPAS_PER_PAGE			(PAGE_SIZE / sizeof(u64))
+
+static int tdx_quote_create_buf(unsigned int nr_pages, struct quote_data *qdata)
+{
+	unsigned long pfn;
+	u64 qlist_npages;
+	int err, i, j;
+	u64 *qlist;
+	void *qbuf;
+
+	if (!nr_pages)
+		return -EINVAL;
+
+	/* The last entry of a linked list page points to the next page	*/
+	qlist_npages = (u64)DIV_ROUND_UP(nr_pages, HPAS_PER_PAGE - 1);
+
+	qlist = vmalloc_array(qlist_npages, PAGE_SIZE);
+	if (!qlist) {
+		err = -ENOMEM;
+		goto out_err;
+	}
+
+	/*
+	 * Make sure unfilled entries are always -1, which means NULL in TDX.
+	 * Only the last page needs to be filled. All the other pages will be
+	 * fully populated.
+	 */
+	memset((u8 *)qlist + (qlist_npages - 1) * PAGE_SIZE, 0xff, PAGE_SIZE);
+
+	qbuf = vcalloc(nr_pages, PAGE_SIZE);
+	if (!qbuf) {
+		err = -ENOMEM;
+		goto out_err;
+	}
+
+	/* Populate HPA_LINKED_LIST as per TDX ABI spec */
+	for (i = 0, j = 0; j < nr_pages; i++) {
+		if ((i % HPAS_PER_PAGE) == HPAS_PER_PAGE - 1) {
+			/*
+			 * The last entry always points to the next page. The
+			 * address of the following entry must be on next page's
+			 * boundary.
+			 */
+			pfn = vmalloc_to_pfn(&qlist[i + 1]);
+			qlist[i] = PFN_PHYS(pfn);
+			continue;
+		}
+
+		pfn = vmalloc_to_pfn((u8 *)qbuf + j * PAGE_SIZE);
+		qlist[i] = PFN_PHYS(pfn);
+		j++;
+	}
+
+	qdata->buf = qbuf;
+	qdata->buf_len = (u64)nr_pages * PAGE_SIZE;
+	qdata->hpa_list = qlist;
+
+	pfn = vmalloc_to_pfn(qlist);
+	qdata->hpa_list_pa = PFN_PHYS(pfn);
+
+	return 0;
+
+out_err:
+	vfree(qlist);
+
+	return err;
+}
+
 static void tdx_quote_init(void)
 {
 	struct tdx_module_args args = {};
+	unsigned int nr_quote_pages;
 	u64 r;
 
 	do {
@@ -1218,7 +1295,13 @@ static void tdx_quote_init(void)
 		return;
 
 	/* Quoting metadata is valid only after initialization */
-	get_tdx_sys_info_quote(&tdx_sysinfo.quote);
+	if (get_tdx_sys_info_quote(&tdx_sysinfo.quote))
+		return;
+
+	nr_quote_pages = PAGE_ALIGN(tdx_sysinfo.quote.max_quote_size) /
+			 PAGE_SIZE;
+	if (tdx_quote_create_buf(nr_quote_pages, &quote_data))
+		pr_err("Failed to create quote buffer\n");
 }
 
 /* Initialize the TDX Module Extensions then Extension-SEAMCALLs can be used */

---

## [9] Xu Yilun — 2026-05-22
*Subject: [RFC PATCH 08/15] x86/virt/tdx: Add interface to check Quoting availability*

From: Peter Fang <peter.fang@intel.com>

KVM needs to know if the Quoting extension is available to determine
whether userspace must be involved in Quote generation.

Since the Quote buffer is always created during Quoting extension
bringup, checking whether the buffer exists is sufficient.

Signed-off-by: Peter Fang <peter.fang@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/include/asm/tdx.h  |  2 ++
 arch/x86/virt/vmx/tdx/tdx.c | 15 +++++++++++++++
 2 files changed, 17 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 15eac89b0afb..7b257088aa1e 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -176,6 +176,8 @@ struct tdx_vp {
 	struct page **tdcx_pages;
 };
 
+bool tdx_quote_enabled(void);
+
 static inline u64 mk_keyed_paddr(u16 hkid, struct page *page)
 {
 	u64 ret;
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 9d04293394d7..b305fa5aab5c 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1213,6 +1213,21 @@ static inline u64 tdx_tdr_pa(struct tdx_td *td)
 	return page_to_phys(td->tdr_page);
 }
 
+/**
+ * tdx_quote_enabled() - Check whether TDX Quoting extension is available
+ *
+ * Return: %true if the Quoting extension is available, otherwise %false.
+ */
+bool tdx_quote_enabled(void)
+{
+	/*
+	 * No need for locking here. The quote buffer is initialized as part of
+	 * core TDX bringup, which comes before KVM is ready for userspace.
+	 */
+	return !!quote_data.buf;
+}
+EXPORT_SYMBOL_FOR_KVM(tdx_quote_enabled);
+
 #define HPAS_PER_PAGE			(PAGE_SIZE / sizeof(u64))
 
 static int tdx_quote_create_buf(unsigned int nr_pages, struct quote_data *qdata)

---

## [10] Xu Yilun — 2026-05-22
*Subject: [RFC PATCH 09/15] x86/virt/tdx: Add interface to generate a Quote*

From: Peter Fang <peter.fang@intel.com>

Use the TDX Quoting extension's TDH.QUOTE.GET SEAMCALL to generate a
Quote. Since the interface is shared across all KVM instances,
serialize access to the SEAMCALL buffer with a mutex.

Allocate and return a per-call buffer containing the generated Quote so
callers don't need to size the Quote buffer themselves. The caller is
responsible for freeing the returned buffer.

Signed-off-by: Peter Fang <peter.fang@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/include/asm/tdx.h  |  2 +
 arch/x86/virt/vmx/tdx/tdx.h |  1 +
 arch/x86/virt/vmx/tdx/tdx.c | 82 +++++++++++++++++++++++++++++++++++++
 3 files changed, 85 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 7b257088aa1e..bc512a00a0d0 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -177,6 +177,8 @@ struct tdx_vp {
 };
 
 bool tdx_quote_enabled(void);
+void *tdx_quote_generate(struct tdx_td *td, void *in_data, u32 in_data_len,
+			 u32 *quote_len);
 
 static inline u64 mk_keyed_paddr(u16 hkid, struct page *page)
 {
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 3849f4f9cc78..01a7d7d8ada9 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -49,6 +49,7 @@
 #define TDH_EXT_INIT			60
 #define TDH_EXT_MEM_ADD			61
 #define TDH_SYS_DISABLE			69
+#define TDH_QUOTE_GET			98
 #define TDH_QUOTE_INIT			100
 
 /*
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index b305fa5aab5c..821f677e9a86 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -62,6 +62,8 @@ static LIST_HEAD(tdx_memlist);
 static struct tdx_sys_info tdx_sysinfo __ro_after_init;
 static bool tdx_module_initialized __ro_after_init;
 
+static DEFINE_MUTEX(tdx_quote_lock);
+
 static struct quote_data {
 	void *buf;
 	u64 buf_len;
@@ -1228,6 +1230,86 @@ bool tdx_quote_enabled(void)
 }
 EXPORT_SYMBOL_FOR_KVM(tdx_quote_enabled);
 
+#define QUOTE_ID_MASK		GENMASK_U64(47, 32)
+
+static u64 tdx_quote_get(struct tdx_td *td, u64 in_data_pa, u64 in_data_len,
+			 u64 hpa_list_pa, u64 total_len, u64 *quote_len)
+{
+	struct tdx_module_args args = {
+		.rcx = tdx_tdr_pa(td),
+		/* Don't bother specifying the quote id */
+		.rdx = QUOTE_ID_MASK & (u64)-1,
+		.r8 = in_data_pa,
+		.r9 = in_data_len,
+		.r10 = hpa_list_pa,
+		.r11 = total_len,
+	};
+	u64 r;
+
+	do {
+		r = seamcall_ret(TDH_QUOTE_GET, &args);
+	} while (r == TDX_INTERRUPTED_RESUMABLE);
+
+	*quote_len = args.rcx;
+
+	return r;
+}
+
+/**
+ * tdx_quote_generate() - Generate a quote for a TD
+ * @td: The TD to generate the quote for.
+ * @in_data: Input data for the quote request.
+ * @in_data_len: Size of the input data in bytes.
+ * @quote_len: Returned size of the generated quote in bytes.
+ *
+ * Use the TDX Quoting extension to generate a TD quote. Pass the input data
+ * through the shared quote buffer and return the quote.
+ *
+ * Return: Newly allocated quote buffer or %NULL on failure.
+ * The caller must free the returned buffer with kvfree().
+ */
+void *tdx_quote_generate(struct tdx_td *td, void *in_data, u32 in_data_len,
+			 u32 *quote_len)
+{
+	void *quote_dup = NULL;
+	u64 r, out_len;
+
+	if (!tdx_quote_enabled())
+		return NULL;
+
+	/* TDH.QUOTE.GET expects the input data to fit in a page */
+	if (in_data_len > PAGE_SIZE)
+		return NULL;
+
+	mutex_lock(&tdx_quote_lock);
+
+	/*
+	 * Use the first page of the quote buffer for input data. The buffer
+	 * must be at least one page in size. @in_data may not be page-aligned,
+	 * but TDH.QUOTE.GET expects page-aligned addresses.
+	 */
+	memcpy(quote_data.buf, in_data, (size_t)in_data_len);
+
+	r = tdx_quote_get(td, quote_data.hpa_list[0], (u64)in_data_len,
+			  quote_data.hpa_list_pa, quote_data.buf_len, &out_len);
+	if (r || !out_len || out_len > quote_data.buf_len)
+		goto out;
+
+	/*
+	 * The quote buffer is a shared resource, so use it only for the
+	 * SEAMCALL and copy the data out as soon as possible.
+	 */
+	quote_dup = kvmemdup(quote_data.buf, out_len, GFP_KERNEL);
+
+out:
+	mutex_unlock(&tdx_quote_lock);
+
+	*quote_len = (u32)out_len;
+
+	return quote_dup;
+}
+EXPORT_SYMBOL_FOR_KVM(tdx_quote_generate);
+
 #define HPAS_PER_PAGE			(PAGE_SIZE / sizeof(u64))
 
 static int tdx_quote_create_buf(unsigned int nr_pages, struct quote_data *qdata)

---

## [11] Xu Yilun — 2026-05-22
*Subject: [RFC PATCH 10/15] x86/tdx: Move and rename Quote request structure*

From: Peter Fang <peter.fang@intel.com>

struct tdx_quote_buf is currently used only by the guest, but the Quote
buffer format will also be needed by the host for in-kernel Quote
generation. Move the definition to tdx.h so it can be shared by both.

Rename the struct to tdx_quote_req to better reflect its purpose.

Signed-off-by: Peter Fang <peter.fang@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/include/asm/tdx.h              | 21 +++++++++++++++++++++
 drivers/virt/coco/tdx-guest/tdx-guest.c | 25 +++----------------------
 2 files changed, 24 insertions(+), 22 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index bc512a00a0d0..945e6817abb2 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -96,6 +96,27 @@ static inline long tdx_kvm_hypercall(unsigned int nr, unsigned long p1,
 }
 #endif /* CONFIG_INTEL_TDX_GUEST && CONFIG_KVM_GUEST */
 
+#if defined(CONFIG_INTEL_TDX_GUEST) || defined(CONFIG_KVM_INTEL_TDX)
+/* struct tdx_quote_req: Format of Quote request message.
+ * @version: Quote format version, filled by TD.
+ * @status: Status code of Quote request, filled by VMM.
+ * @in_len: Length of TDREPORT, filled by TD.
+ * @out_len: Length of Quote data, filled by VMM.
+ * @data: Quote data on output or TDREPORT on input.
+ *
+ * More details of Quote request message can be found in TDX
+ * Guest-Host Communication Interface (GHCI) for Intel TDX 1.0,
+ * section titled "TDG.VP.VMCALL<GetQuote>"
+ */
+struct tdx_quote_req {
+	u64 version;
+	u64 status;
+	u32 in_len;
+	u32 out_len;
+	u8 data[];
+};
+#endif /* CONFIG_INTEL_TDX_GUEST || CONFIG_KVM_INTEL_TDX */
+
 #ifdef CONFIG_INTEL_TDX_HOST
 u64 __seamcall(u64 fn, struct tdx_module_args *args);
 u64 __seamcall_ret(u64 fn, struct tdx_module_args *args);
diff --git a/drivers/virt/coco/tdx-guest/tdx-guest.c b/drivers/virt/coco/tdx-guest/tdx-guest.c
index a9ecc46df187..d0ddbbc98fb8 100644
--- a/drivers/virt/coco/tdx-guest/tdx-guest.c
+++ b/drivers/virt/coco/tdx-guest/tdx-guest.c
@@ -171,26 +171,7 @@ static void tdx_mr_deinit(const struct attribute_group *mr_grp)
 #define GET_QUOTE_SUCCESS		0
 #define GET_QUOTE_IN_FLIGHT		0xffffffffffffffff
 
-#define TDX_QUOTE_MAX_LEN		(GET_QUOTE_BUF_SIZE - sizeof(struct tdx_quote_buf))
-
-/* struct tdx_quote_buf: Format of Quote request buffer.
- * @version: Quote format version, filled by TD.
- * @status: Status code of Quote request, filled by VMM.
- * @in_len: Length of TDREPORT, filled by TD.
- * @out_len: Length of Quote data, filled by VMM.
- * @data: Quote data on output or TDREPORT on input.
- *
- * More details of Quote request buffer can be found in TDX
- * Guest-Host Communication Interface (GHCI) for Intel TDX 1.0,
- * section titled "TDG.VP.VMCALL<GetQuote>"
- */
-struct tdx_quote_buf {
-	u64 version;
-	u64 status;
-	u32 in_len;
-	u32 out_len;
-	u8 data[];
-};
+#define TDX_QUOTE_MAX_LEN		(GET_QUOTE_BUF_SIZE - sizeof(struct tdx_quote_req))
 
 /* Quote data buffer */
 static void *quote_data;
@@ -250,7 +231,7 @@ static void *alloc_quote_buf(void)
  * or error code after processing is complete. So wait till the status
  * changes from GET_QUOTE_IN_FLIGHT or the request being timed out.
  */
-static int wait_for_quote_completion(struct tdx_quote_buf *quote_buf, u32 timeout)
+static int wait_for_quote_completion(struct tdx_quote_req *quote_buf, u32 timeout)
 {
 	int i = 0;
 
@@ -269,7 +250,7 @@ static int wait_for_quote_completion(struct tdx_quote_buf *quote_buf, u32 timeou
 static int tdx_report_new_locked(struct tsm_report *report, void *data)
 {
 	u8 *buf;
-	struct tdx_quote_buf *quote_buf = quote_data;
+	struct tdx_quote_req *quote_buf = quote_data;
 	struct tsm_report_desc *desc = &report->desc;
 	u32 out_len;
 	int ret;

---

## [12] Xu Yilun — 2026-05-22
*Subject: [RFC PATCH 11/15] KVM: TDX: Factor out userspace return path from tdx_get_quote()*

From: Peter Fang <peter.fang@intel.com>

Separate the logic that returns GetQuote to userspace so that
tdx_get_quote() can be extended to support in-kernel quote generation.

No functional change intended.

Signed-off-by: Peter Fang <peter.fang@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/kvm/vmx/tdx.c | 25 ++++++++++++++++---------
 1 file changed, 16 insertions(+), 9 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index ed12805bbb44..9f7c39e0d4b5 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1524,6 +1524,20 @@ static int tdx_complete_simple(struct kvm_vcpu *vcpu)
 	return 1;
 }
 
+static int tdx_get_quote_user(struct kvm_vcpu *vcpu, u64 gpa, u64 size)
+{
+	vcpu->run->exit_reason = KVM_EXIT_TDX;
+	vcpu->run->tdx.flags = 0;
+	vcpu->run->tdx.nr = TDVMCALL_GET_QUOTE;
+	vcpu->run->tdx.get_quote.ret = TDVMCALL_STATUS_SUBFUNC_UNSUPPORTED;
+	vcpu->run->tdx.get_quote.gpa = gpa;
+	vcpu->run->tdx.get_quote.size = size;
+
+	vcpu->arch.complete_userspace_io = tdx_complete_simple;
+
+	return 0;
+}
+
 static int tdx_get_quote(struct kvm_vcpu *vcpu)
 {
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
@@ -1536,16 +1550,9 @@ static int tdx_get_quote(struct kvm_vcpu *vcpu)
 		return 1;
 	}
 
-	vcpu->run->exit_reason = KVM_EXIT_TDX;
-	vcpu->run->tdx.flags = 0;
-	vcpu->run->tdx.nr = TDVMCALL_GET_QUOTE;
-	vcpu->run->tdx.get_quote.ret = TDVMCALL_STATUS_SUBFUNC_UNSUPPORTED;
-	vcpu->run->tdx.get_quote.gpa = gpa & ~gfn_to_gpa(kvm_gfn_direct_bits(tdx->vcpu.kvm));
-	vcpu->run->tdx.get_quote.size = size;
-
-	vcpu->arch.complete_userspace_io = tdx_complete_simple;
+	gpa &= ~gfn_to_gpa(kvm_gfn_direct_bits(vcpu->kvm));
 
-	return 0;
+	return tdx_get_quote_user(vcpu, gpa, size);
 }
 
 static int tdx_setup_event_notify_interrupt(struct kvm_vcpu *vcpu)

---

## [13] Xu Yilun — 2026-05-22
*Subject: [RFC PATCH 12/15] KVM: TDX: Add in-kernel Quote generation*

From: Peter Fang <peter.fang@intel.com>

Provide an in-kernel path for TDX Quote generation when handling
TDG.VP.VMCALL<GetQuote>, without requiring an exit to userspace.

Use the core TDX API when the TDX Quoting extension is available. For
simplicity, each KVM guest checks for availability only once during
initialization. KVM does not handle Quoting service disruptions.

Signed-off-by: Peter Fang <peter.fang@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/include/asm/tdx.h |   9 +++
 arch/x86/kvm/vmx/tdx.h     |   6 ++
 arch/x86/kvm/vmx/tdx.c     | 135 ++++++++++++++++++++++++++++++++++++-
 virt/kvm/kvm_main.c        |   1 +
 4 files changed, 150 insertions(+), 1 deletion(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 945e6817abb2..5863d6748100 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -115,6 +115,15 @@ struct tdx_quote_req {
 	u32 out_len;
 	u8 data[];
 };
+
+#define TDX_QUOTE_REQ_HDR_SIZE		(offsetof(struct tdx_quote_req, data))
+
+/*
+ * TDG.VP.VMCALL<GetQuote> Status Codes
+ */
+#define TDX_QUOTE_STATUS_SUCCESS	0x0000000000000000ULL
+#define TDX_QUOTE_STATUS_ERROR		0x8000000000000000ULL
+#define TDX_QUOTE_STATUS_UNAVAILABLE	0x8000000000000001ULL
 #endif /* CONFIG_INTEL_TDX_GUEST || CONFIG_KVM_INTEL_TDX */
 
 #ifdef CONFIG_INTEL_TDX_HOST
diff --git a/arch/x86/kvm/vmx/tdx.h b/arch/x86/kvm/vmx/tdx.h
index ac8323a68b16..18c93e80c0ec 100644
--- a/arch/x86/kvm/vmx/tdx.h
+++ b/arch/x86/kvm/vmx/tdx.h
@@ -47,6 +47,12 @@ struct kvm_tdx {
 	 * Set/unset is protected with kvm->mmu_lock.
 	 */
 	bool wait_for_sept_zap;
+
+	/*
+	 * Whether to get TDX quote directly in kernel, without exiting to
+	 * userspace.
+	 */
+	bool get_quote_in_kernel;
 };
 
 /* TDX module vCPU states */
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 9f7c39e0d4b5..bade046da5a1 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1538,11 +1538,133 @@ static int tdx_get_quote_user(struct kvm_vcpu *vcpu, u64 gpa, u64 size)
 	return 0;
 }
 
+static bool write_quote_status_to_guest(struct kvm_vcpu *vcpu, u64 status,
+					gpa_t gpa)
+{
+	if (kvm_vcpu_write_guest(vcpu,
+				 gpa + offsetof(struct tdx_quote_req, status),
+				 &status, sizeof(status)))
+		return false;
+
+	return true;
+}
+
+static bool write_quote_to_guest(struct kvm_vcpu *vcpu, void *quote_data,
+				 u32 quote_len, gpa_t gpa)
+{
+	if (kvm_vcpu_write_guest(vcpu,
+				 gpa + TDX_QUOTE_REQ_HDR_SIZE,
+				 quote_data, quote_len))
+		return false;
+
+	if (kvm_vcpu_write_guest(vcpu,
+				 gpa + offsetof(struct tdx_quote_req, out_len),
+				 &quote_len, sizeof(quote_len)))
+		return false;
+
+	return true;
+}
+
+static u64 __get_quote_kernel(struct kvm_vcpu *vcpu, struct tdx_quote_req *req,
+			      size_t req_len, gpa_t req_gpa, size_t total_len)
+{
+	struct tdx_td *td = &to_kvm_tdx(vcpu->kvm)->td;
+
+	/* Only support version 1 as defined in the GHCI spec */
+	if (req->version != 1)
+		return TDX_QUOTE_STATUS_ERROR;
+
+	if ((size_t)req->in_len + TDX_QUOTE_REQ_HDR_SIZE > req_len)
+		return TDX_QUOTE_STATUS_ERROR;
+
+	/* The caller frees the quote data */
+	void *quote_data __free(kvfree) =
+		tdx_quote_generate(td, req->data, req->in_len, &req->out_len);
+
+	if (!quote_data)
+		return TDX_QUOTE_STATUS_UNAVAILABLE;
+
+	if ((size_t)req->out_len + TDX_QUOTE_REQ_HDR_SIZE > total_len)
+		return TDX_QUOTE_STATUS_ERROR;
+
+	if (!write_quote_to_guest(vcpu, quote_data, req->out_len, req_gpa))
+		return TDX_QUOTE_STATUS_ERROR;
+
+	return TDX_QUOTE_STATUS_SUCCESS;
+}
+
+static u64 tdx_get_quote_check_args(struct kvm_vcpu *vcpu, u64 gpa, u64 size)
+{
+	gfn_t gfn_start, gfn_end;
+	u64 end;
+
+	if (!size)
+		return TDVMCALL_STATUS_INVALID_OPERAND;
+
+	if (!PAGE_ALIGNED(gpa) || !PAGE_ALIGNED(size))
+		return TDVMCALL_STATUS_ALIGN_ERROR;
+
+	if (check_add_overflow(gpa, size, &end))
+		return TDVMCALL_STATUS_INVALID_OPERAND;
+
+	gfn_start = gpa_to_gfn(gpa);
+	gfn_end = gpa_to_gfn(end);
+
+	/*
+	 * Reject if the guest didn't explicitly convert its quote pages to
+	 * shared.
+	 */
+	if (!kvm_range_has_memory_attributes(vcpu->kvm, gfn_start, gfn_end,
+					     KVM_MEMORY_ATTRIBUTE_PRIVATE, 0))
+		return TDVMCALL_STATUS_INVALID_OPERAND;
+
+	return TDVMCALL_STATUS_SUCCESS;
+}
+
+static int tdx_get_quote_kernel(struct kvm_vcpu *vcpu, u64 gpa, u64 size)
+{
+	void *first_page = NULL;
+	u64 err, qerr;
+
+	err = tdx_get_quote_check_args(vcpu, gpa, size);
+	if (err != TDVMCALL_STATUS_SUCCESS)
+		goto out;
+
+	err = TDVMCALL_STATUS_INVALID_OPERAND;
+
+	first_page = kmalloc(PAGE_SIZE, GFP_KERNEL);
+	if (!first_page)
+		goto out;
+
+	/*
+	 * Read the first GetQuote page for its header + in_data. The check
+	 * above ensures that this GetQuote message is at least one page in
+	 * size. in_data spanning more than a page is not supported.
+	 */
+	if (kvm_vcpu_read_guest(vcpu, gpa, first_page, PAGE_SIZE))
+		goto out;
+
+	qerr = __get_quote_kernel(vcpu, first_page, PAGE_SIZE,
+				  (gpa_t)gpa, size);
+
+	if (write_quote_status_to_guest(vcpu, qerr, (gpa_t)gpa) &&
+	    qerr == TDX_QUOTE_STATUS_SUCCESS)
+		err = TDVMCALL_STATUS_SUCCESS;
+
+out:
+	kfree(first_page);
+	tdvmcall_set_return_code(vcpu, err);
+
+	return 1;
+}
+
 static int tdx_get_quote(struct kvm_vcpu *vcpu)
 {
+	struct kvm_tdx *kvm_tdx = to_kvm_tdx(vcpu->kvm);
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
 	u64 gpa = tdx->vp_enter_args.r12;
 	u64 size = tdx->vp_enter_args.r13;
+	int ret;
 
 	/* The gpa of buffer must have shared bit set. */
 	if (vt_is_tdx_private_gpa(vcpu->kvm, gpa)) {
@@ -1552,7 +1674,12 @@ static int tdx_get_quote(struct kvm_vcpu *vcpu)
 
 	gpa &= ~gfn_to_gpa(kvm_gfn_direct_bits(vcpu->kvm));
 
-	return tdx_get_quote_user(vcpu, gpa, size);
+	if (kvm_tdx->get_quote_in_kernel)
+		ret = tdx_get_quote_kernel(vcpu, gpa, size);
+	else
+		ret = tdx_get_quote_user(vcpu, gpa, size);
+
+	return ret;
 }
 
 static int tdx_setup_event_notify_interrupt(struct kvm_vcpu *vcpu)
@@ -2751,6 +2878,12 @@ static int tdx_td_init(struct kvm *kvm, struct kvm_tdx_cmd *cmd)
 	else
 		kvm->arch.gfn_direct_bits = TDX_SHARED_BIT_PWL_4;
 
+	/*
+	 * Check only once at TD creation. If the quoting service gets disrupted
+	 * during TD runtime, let the user handle it.
+	 */
+	kvm_tdx->get_quote_in_kernel = tdx_quote_enabled();
+
 	kvm_tdx->state = TD_STATE_INITIALIZED;
 out:
 	/* kfree() accepts NULL. */
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index 89489996fbc1..599f88a13071 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -2461,6 +2461,7 @@ bool kvm_range_has_memory_attributes(struct kvm *kvm, gfn_t start, gfn_t end,
 
 	return true;
 }
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_range_has_memory_attributes);
 
 static __always_inline void kvm_handle_gfn_range(struct kvm *kvm,
 						 struct kvm_mmu_notifier_range *range)

---

## [14] Xu Yilun — 2026-05-22
*Subject: [RFC PATCH 13/15] KVM: TDX: Support event-notify interrupts only with userspace quoting*

From: Peter Fang <peter.fang@intel.com>

Tie userspace SetupEventNotifyInterrupt support to userspace Quote
generation. Delivering event-notify interrupts via userspace breaks if
KVM never exits to userspace in the first place.

No known guest currently requires event-notify interrupt support, so
defer adding in-kernel support for now. Linux TDX guests use polling
only.

Update the KVM API Documentation to reflect the change.

Signed-off-by: Peter Fang <peter.fang@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 Documentation/virt/kvm/api.rst |  8 +++++++-
 arch/x86/kvm/vmx/tdx.c         | 20 +++++++++++++++++---
 2 files changed, 24 insertions(+), 4 deletions(-)

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index 52bbbb553ce1..8a02745a36ee 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -7335,6 +7335,9 @@ inputs and outputs of the TDVMCALL.  Currently the following values of
    queued successfully, the TDX guest can poll the status field in the
    shared-memory area to check whether the Quote generation is completed or
    not. When completed, the generated Quote is returned via the same buffer.
+   If the host kernel generates Quotes through the TDX Quoting service provided
+   by the TDX module, KVM processes the GetQuote request and it will not appear
+   in userspace.  KVM only supports version 1 of the GetQuote request.
 
  * ``TDVMCALL_GET_TD_VM_CALL_INFO``: the guest has requested the support
    status of TDVMCALLs.  The output values for the given leaf should be
@@ -7342,7 +7345,10 @@ inputs and outputs of the TDVMCALL.  Currently the following values of
    field of the union.
 
  * ``TDVMCALL_SETUP_EVENT_NOTIFY_INTERRUPT``: the guest has requested to
-   set up a notification interrupt for vector ``vector``.
+   set up a notification interrupt for vector ``vector``.  Since this TDVMCALL
+   is used to optimize ``TDVMCALL_GET_QUOTE``, KVM disables this support in
+   userspace VMM if ``TDVMCALL_GET_QUOTE`` is completely handled in the kernel.
+   KVM may add kernel support for this in the future.
 
 KVM may add support for more values in the future that may cause a userspace
 exit, even without calls to ``KVM_ENABLE_CAP`` or similar.  In this case,
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index bade046da5a1..5aebbec7fa6e 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -185,7 +185,7 @@ static void td_init_cpuid_entry2(struct kvm_cpuid_entry2 *entry, unsigned char i
 	tdx_clear_unsupported_cpuid(entry);
 }
 
-#define TDVMCALLINFO_SETUP_EVENT_NOTIFY_INTERRUPT	BIT(1)
+#define TDVMCALLINFO_SETUP_EVENT_NOTIFY_INTERRUPT	BIT_ULL(1)
 
 static int init_kvm_tdx_caps(const struct tdx_sys_info_td_conf *td_conf,
 			     struct kvm_tdx_capabilities *caps)
@@ -202,8 +202,15 @@ static int init_kvm_tdx_caps(const struct tdx_sys_info_td_conf *td_conf,
 
 	caps->cpuid.nent = td_conf->num_cpuid_config;
 
-	caps->user_tdvmcallinfo_1_r11 =
-		TDVMCALLINFO_SETUP_EVENT_NOTIFY_INTERRUPT;
+	/*
+	 * Don't advertise userspace event-notify interrupt support if TDX
+	 * quoting service is enabled, as quote generation will be done entirely
+	 * in the kernel. Support in the kernel can be added later if needed.
+	 */
+	if (!tdx_quote_enabled()) {
+		caps->user_tdvmcallinfo_1_r11 |=
+			TDVMCALLINFO_SETUP_EVENT_NOTIFY_INTERRUPT;
+	}
 
 	for (i = 0; i < td_conf->num_cpuid_config; i++)
 		td_init_cpuid_entry2(&caps->cpuid.entries[i], i);
@@ -1684,9 +1691,16 @@ static int tdx_get_quote(struct kvm_vcpu *vcpu)
 
 static int tdx_setup_event_notify_interrupt(struct kvm_vcpu *vcpu)
 {
+	struct kvm_tdx *kvm_tdx = to_kvm_tdx(vcpu->kvm);
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
 	u64 vector = tdx->vp_enter_args.r12;
 
+	/* See init_kvm_tdx_caps() for comments */
+	if (kvm_tdx->get_quote_in_kernel) {
+		tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_SUBFUNC_UNSUPPORTED);
+		return 1;
+	}
+
 	if (vector < 32 || vector > 255) {
 		tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_INVALID_OPERAND);
 		return 1;

---

## [15] Xu Yilun — 2026-05-22
*Subject: [RFC PATCH 14/15] x86/virt/tdx: Embed version info in SEAMCALL leaf function definitions*

Embed version information in SEAMCALL leaf function definitions rather
than let the caller open code them. For now, only TDH.VP.INIT is
involved.

Don't bother the caller to choose the SEAMCALL version if unnecessary.
New version SEAMCALLs are guaranteed to be backward compatible, so
ideally kernel doesn't need to keep version history and only uses the
latest version SEAMCALLs.

The concern is some old TDX Modules don't recognize new version
SEAMCALLs. Multiple SEAMCALL versions co-exist when kernel should
support these old Modules. As time goes by, the old Modules deprecate
and old version SEAMCALL definitions should disappear.

The old TDX Modules that only support TDH.VP.INIT v0 are all deprecated,
so only provide the latest (v1) definition.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.h | 23 ++++++++++++++---------
 arch/x86/virt/vmx/tdx/tdx.c |  4 ++--
 2 files changed, 16 insertions(+), 11 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 01a7d7d8ada9..10aff23cd01f 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -2,6 +2,7 @@
 #ifndef _X86_VIRT_TDX_H
 #define _X86_VIRT_TDX_H
 
+#include <linux/bitfield.h>
 #include <linux/bits.h>
 
 /*
@@ -11,6 +12,18 @@
  * architectural definitions come first.
  */
 
+/*
+ * SEAMCALL leaf:
+ *
+ * Bit 15:0	Leaf number
+ * Bit 23:16	Version number
+ */
+#define SEAMCALL_LEAF			GENMASK(15, 0)
+#define SEAMCALL_VER			GENMASK(23, 16)
+
+#define SEAMCALL_LEAF_VER(l, v)		(FIELD_PREP(SEAMCALL_LEAF, l) | \
+					 FIELD_PREP(SEAMCALL_VER, v))
+
 /*
  * TDX module SEAMCALL leaf functions
  */
@@ -31,7 +44,7 @@
 #define TDH_VP_CREATE			10
 #define TDH_MNG_KEY_FREEID		20
 #define TDH_MNG_INIT			21
-#define TDH_VP_INIT			22
+#define TDH_VP_INIT			SEAMCALL_LEAF_VER(22, 1)
 #define TDH_PHYMEM_PAGE_RDMD		24
 #define TDH_VP_RD			26
 #define TDH_PHYMEM_PAGE_RECLAIM		28
@@ -52,14 +65,6 @@
 #define TDH_QUOTE_GET			98
 #define TDH_QUOTE_INIT			100
 
-/*
- * SEAMCALL leaf:
- *
- * Bit 15:0	Leaf number
- * Bit 23:16	Version number
- */
-#define TDX_VERSION_SHIFT		16
-
 /* TDX page types */
 #define	PT_NDA		0x0
 #define	PT_RSVD		0x1
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 821f677e9a86..f7600f930c6e 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2217,8 +2217,8 @@ u64 tdh_vp_init(struct tdx_vp *vp, u64 initial_rcx, u32 x2apicid)
 		.r8 = x2apicid,
 	};
 
-	/* apicid requires version == 1. */
-	return seamcall(TDH_VP_INIT | (1ULL << TDX_VERSION_SHIFT), &args);
+	/* apicid requires version == 1. See TDH_VP_INIT definition.*/
+	return seamcall(TDH_VP_INIT, &args);
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_vp_init);

---

## [16] Xu Yilun — 2026-05-22
*Subject: [RFC PATCH 15/15] x86/virt/tdx: Enable TDX Quoting extension*

From: Peter Fang <peter.fang@intel.com>

Enable the TDX Quoting feature via TDH.SYS.CONFIG when supported by the
TDX module.

The TDX Quoting extension generates TDX attestation Quotes via a
SEAMCALL, without using a discrete Quoting engine.

TDX Module supports add-on TDX features (e.g. TDX Quoting & TDX Module
Extensions) that should be manually enabled by host. It extends
TDH.SYS.CONFIG for host to choose to enable them on bootup.

Call TDH.SYS.CONFIG with a new bitmap input parameter to specify which
features to enable. The bitmap uses the same definitions as
TDX_FEATURES0. But note not all bits in TDX_FEATURES0 are valid for
configuration, e.g. TDX Module Extensions is a service that supports TDX
Quoting, it is implicitly enabled when TDX Quoting is enabled. Setting
TDX_FEATURES0_EXT in the bitmap has no effect.

TDX Module advances the version of TDH.SYS.CONFIG for the change, so
use the latest version (v1) for add-on feature enabling. But supporting
existing Modules which only support v0 is still necessary until they are
deprecated. In fact, it is unlikely that TDH.SYS.CONFIG ever needs to
change again and the code would stay in v1. So there is little value
in worrying about deprecating v0 to save a couple lines of code in 5-7
years when these original TDX platforms sunset.

TDX Module updates global metadata when add-on features are enabled.
Host should update the cached tdx_sysinfo to reflect these changes.

Co-developed-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
Signed-off-by: Peter Fang <peter.fang@intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.h |  4 +++-
 arch/x86/virt/vmx/tdx/tdx.c | 24 ++++++++++++++++++++++--
 2 files changed, 25 insertions(+), 3 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 10aff23cd01f..524a14c01aa6 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -58,7 +58,8 @@
 #define TDH_PHYMEM_CACHE_WB		40
 #define TDH_PHYMEM_PAGE_WBINVD		41
 #define TDH_VP_WR			43
-#define TDH_SYS_CONFIG			45
+#define TDH_SYS_CONFIG_V0		45
+#define TDH_SYS_CONFIG			SEAMCALL_LEAF_VER(TDH_SYS_CONFIG_V0, 1)
 #define TDH_EXT_INIT			60
 #define TDH_EXT_MEM_ADD			61
 #define TDH_SYS_DISABLE			69
@@ -97,6 +98,7 @@ struct tdmr_info {
 /* Bit definitions of TDX_FEATURES0 metadata field */
 #define TDX_FEATURES0_NO_RBP_MOD	BIT(18)
 #define TDX_FEATURES0_EXT		BIT_ULL(39)
+#define TDX_FEATURES0_QUOTE		BIT_ULL(50)
 
 /*
  * Do not put any hardware-defined TDX structure representations below
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index f7600f930c6e..86e5b7ad19b3 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1049,6 +1049,7 @@ static __init int construct_tdmrs(struct list_head *tmb_list,
 static __init int config_tdx_module(struct tdmr_info_list *tdmr_list,
 				    u64 global_keyid)
 {
+	u64 seamcall_fn = TDH_SYS_CONFIG_V0;
 	struct tdx_module_args args = {};
 	u64 *tdmr_pa_array;
 	size_t array_sz;
@@ -1074,8 +1075,22 @@ static __init int config_tdx_module(struct tdmr_info_list *tdmr_list,
 	args.rcx = __pa(tdmr_pa_array);
 	args.rdx = tdmr_list->nr_consumed_tdmrs;
 	args.r8 = global_keyid;
-	ret = seamcall_prerr(TDH_SYS_CONFIG, &args);
 
+	if (tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_QUOTE) {
+		args.r9 |= TDX_FEATURES0_QUOTE;
+		/* These parameters require version >= 1 */
+		seamcall_fn = TDH_SYS_CONFIG;
+	}
+
+	ret = seamcall_prerr(seamcall_fn, &args);
+	if (ret)
+		goto free_tdmr;
+
+	/* enabling TDX Quoting may change tdx_sysinfo, update it */
+	if (tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_QUOTE)
+		ret = get_tdx_sys_info(&tdx_sysinfo);
+
+free_tdmr:
 	/* Free the array as it is not required anymore. */
 	kfree(tdmr_pa_array);
 
@@ -1384,12 +1399,17 @@ static void tdx_quote_init(void)
 	unsigned int nr_quote_pages;
 	u64 r;
 
+	if (!(tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_QUOTE))
+		return;
+
 	do {
 		r = seamcall(TDH_QUOTE_INIT, &args);
 	} while (r == TDX_INTERRUPTED_RESUMABLE);
 
-	if (r)
+	if (r) {
+		pr_err("Failed to enable quoting extension: 0x%llx\n", r);
 		return;
+	}
 
 	/* Quoting metadata is valid only after initialization */
 	if (get_tdx_sys_info_quote(&tdx_sysinfo.quote))

---

## [17] Tony Lindgren — 2026-05-25
*Subject: Re: [RFC PATCH 15/15] x86/virt/tdx: Enable TDX Quoting extension*

On Fri, May 22, 2026 at 11:41:28AM +0800, Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> 

This should be made clearer IMO. How about mention that get_tdx_sys_info()
needs to get called again to reload the TDX module global metadata?
 
> --- a/arch/x86/virt/vmx/tdx/tdx.c
> +++ b/arch/x86/virt/vmx/tdx/tdx.c

The comment above helps, but the change in the handling will be easy to
miss.

> +free_tdmr:
>  	/* Free the array as it is not required anymore. */

So I think it would be good to also add a comment to get_tdx_sys_info()
to make it easier for folks to follow that it may get called multiple
times.

Regards,

Tony

---

## [18] Tony Lindgren — 2026-05-25
*Subject: Re: [PATCH 04/15] x86/virt/tdx: Enable the Extensions right after
 basic TDX Module init*

On Fri, May 22, 2026 at 11:41:17AM +0800, Xu Yilun wrote:
> The detailed initialization flow for TDX Module Extensions has been
> fully implemented. Enable the flow after basic TDX Module

Looking at patch 15/15, we need to reload the TDX module metadata at least
for the attestation. We need to do that early, so to me it seems that
everything can be just tagged __init from the start.

So you can just call init_tdx_ext() in patch 3/15, and this patch is not
needed at all?

Regards,

Tony

---

## [19] Xiaoyao Li — 2026-05-25
*Subject: Re: [PATCH 01/15] x86/virt/tdx: Read global metadata for TDX Module
 Extensions*

On 5/22/2026 11:41 AM, Xu Yilun wrote:
> Add reading of the global metadata for TDX Module Extensions.
> 

> But for the Module's integrity, Linux requires that all features that a
> Module advertises must have a complete, valid set of metadata, 

I doubt on this.

1. Is it a must that any new feature introduces new metadata field?

2. Linux only cares the integrity for the features it uses, not for all 
the features.

> and the
> validation must succeed at core TDX initialization time.

I'm not sure why we need to explain the behavior when the reading fails. 
It's not different to other existing fields.

Instead, I think you can explain why we need to check TDX_FEATURES0_EXT 
at first.

Anyway, I don't read it as a good changelog. It event doesn't tell what 
the added fields are and why we need them.

---

## [20] Xiaoyao Li — 2026-05-25
*Subject: Re: [PATCH 01/15] x86/virt/tdx: Read global metadata for TDX Module
 Extensions*

On 5/22/2026 11:41 AM, Xu Yilun wrote:
...
> +static __init int get_tdx_sys_info_ext(struct tdx_sys_info_ext *sysinfo_ext)
> +{

Is it correct to read "memory_pool_required_pages" and "ext_required" so 
early in get_tdx_sys_info()? get_tdx_sys_info() is called before 
config_tdx_module() which calls TDH.SYS.CONFIG.

If I read the TDX module base spec correctly, the amount of memory for 
extensions and EXT_REQUIRED field depends on the enabled features, which 
is determined by TDH.SYS.CONFIG/TDH.SYS.UPDATE ?

>   	return ret;
>   }

---

## [21] Xiaoyao Li — 2026-05-25
*Subject: Re: [PATCH 04/15] x86/virt/tdx: Enable the Extensions right after
 basic TDX Module init*

On 5/22/2026 11:41 AM, Xu Yilun wrote:
> The detailed initialization flow for TDX Module Extensions has been
> fully implemented. Enable the flow after basic TDX Module



> Note that the Extensions initialization flow will still not start if no
> add-on features require Extensions. The enabling of add-on features will

based on the above, how about putting this patch before patch 02 and 03? 
so that we can eliminate the churn of add "__init" and the 
"__maybe_unused " in patch 02.

To be more safer, we can even make the code as

static bool tdx_supports_extension(void)
{
	/* To be enabled when kernel is ready. */
	return false;
}

static __init int init_tdx_ext(void)
{
	if (!tdx_supports_extension())
		return 0;

	/* No feature requires TDX Module Extensions. */
	if (!tdx_sysinfo.ext.ext_required)
		return 0;
}

and after all the pieces implemented, we can change 
tdx_supports_extension() to

static bool tdx_supports_extension(void)
{
	/* To be enabled when kernel is ready. */
	return !!(tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_EXT);
}

> Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
> ---

---

## [22] Xiaoyao Li — 2026-05-25
*Subject: Re: [PATCH 02/15] x86/virt/tdx: Add extra memory to TDX Module for
 Extensions*

On 5/22/2026 11:41 AM, Xu Yilun wrote:
> TDX Module introduces a new concept called "TDX Module Extensions" to
> support long running / hard-irq preemptible flows inside. This makes TDX

Is the page flush only needed when CLFLUSH_BEFORE_ALLOC is true?

If so, it inherits the same decision to always flush as what 
tdx_clflush_page() did. Then, any chance we can use tdx_clflush_page() 
here so that we have a single central place of the comment to explain 
the kernel design decision.

> +}
> +

---

## [23] Xiaoyao Li — 2026-05-25
*Subject: Re: [PATCH 03/15] x86/virt/tdx: Make TDX Module initialize Extensions*

On 5/22/2026 11:41 AM, Xu Yilun wrote:
> After providing all required memory to TDX Module, initialize TDX
> Module Extensions via TDH.EXT.INIT, so Extension-SEAMCALLs can be used.

Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>

> ---
>   arch/x86/virt/vmx/tdx/tdx.h |  1 +

---

## [24] Xiaoyao Li — 2026-05-25
*Subject: Re: [RFC PATCH 14/15] x86/virt/tdx: Embed version info in SEAMCALL
 leaf function definitions*

On 5/22/2026 11:41 AM, Xu Yilun wrote:
> Embed version information in SEAMCALL leaf function definitions rather
> than let the caller open code them. For now, only TDH.VP.INIT is

how about

#define TDH_VP_INIT			22
#define TDH_VP_INIT_V1			SEAMCALL_LEAF_VER(TDH_VP_INIT, 1)

and use TDH_VP_INIT_V1 below?

>   #define TDH_PHYMEM_PAGE_RDMD		24
>   #define TDH_VP_RD			26

---

## [25] Xiaoyao Li — 2026-05-25
*Subject: Re: [RFC PATCH 15/15] x86/virt/tdx: Enable TDX Quoting extension*

On 5/25/2026 1:17 PM, Tony Lindgren wrote:
> On Fri, May 22, 2026 at 11:41:28AM +0800, Xu Yilun wrote:
>> From: Peter Fang <peter.fang@intel.com>

Ah ha! This patch answers my comment to patch 1:
https://lore.kernel.org/all/956fa1e6-2920-4b2e-8037-d4b9d812ae53@intel.com/

sysinfo_ext->memory_pool_required_pages and sysinfo_ext->ext_required 
will be updated after extensions are enabled by TDH.SYS.CONFIG.

Patch 06 in this series already reads the tdx_sys_info_quote out of 
get_tdx_sys_info(), which mean get_tdx_sys_info() doesn't ensure all the 
global metadata will be update again.

So how about move the read of memory_pool_required_pages and 
ext_required out of get_tdx_sys_info() and put them after 
TDH.SYS.CONFIG, so that we don't need call get_tdx_sys_info() again?

>> --- a/arch/x86/virt/vmx/tdx/tdx.c
>> +++ b/arch/x86/virt/vmx/tdx/tdx.c

---

## [26] Tony Lindgren — 2026-05-26
*Subject: Re: [RFC PATCH 15/15] x86/virt/tdx: Enable TDX Quoting extension*

On Mon, May 25, 2026 at 06:51:27PM +0800, Xiaoyao Li wrote:
> On 5/25/2026 1:17 PM, Tony Lindgren wrote:
> > On Fri, May 22, 2026 at 11:41:28AM +0800, Xu Yilun wrote:

Sounds like a good idea to me.

---

## [27] Xu Yilun — 2026-05-26
*Subject: Re: [RFC PATCH 15/15] x86/virt/tdx: Enable TDX Quoting extension*

On Mon, May 25, 2026 at 06:51:27PM +0800, Xiaoyao Li wrote:
> On 5/25/2026 1:17 PM, Tony Lindgren wrote:
> > On Fri, May 22, 2026 at 11:41:28AM +0800, Xu Yilun wrote:

Yes, I'm good to it. I hesitated to move them out in case we need some
central control on global data. But now I see there is already a
precedent:

https://lore.kernel.org/kvm/20260520133909.409394-22-chao.gao@intel.com/

Once we've agreed on moving add-on data reading out of get_tdx_sys_info(),
we don't have to read them after TDH.SYS.CONFIG, read them when really
needed. How about the following, that makes the Extension part in this
series self-contained.

----8<----

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 86e5b7ad19b3..b729c1f5ab9e 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1536,6 +1536,10 @@ static __init int init_tdx_ext(void)
        if (!(tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_EXT))
                return 0;

+       ret = get_tdx_sys_info_ext(&tdx_sysinfo.ext);
+       if (ret)
+               return ret;
+
        /* No feature requires TDX Module Extensions. */
        if (!tdx_sysinfo.ext.ext_required)
                return 0;
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index f9cc2dd02caf..e7d9e0c4b604 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -140,8 +140,5 @@ static __init int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
        ret = ret ?: get_tdx_sys_info_td_ctrl(&sysinfo->td_ctrl);
        ret = ret ?: get_tdx_sys_info_td_conf(&sysinfo->td_conf);

-       if (sysinfo->features.tdx_features0 & TDX_FEATURES0_EXT)
-               ret = ret ?: get_tdx_sys_info_ext(&sysinfo->ext);
-
        return ret;
 }

---

## [28] Xiaoyao Li — 2026-05-27
*Subject: Re: [RFC PATCH 15/15] x86/virt/tdx: Enable TDX Quoting extension*

On 5/26/2026 11:45 PM, Xu Yilun wrote:
> On Mon, May 25, 2026 at 06:51:27PM +0800, Xiaoyao Li wrote:
>> On 5/25/2026 1:17 PM, Tony Lindgren wrote:

Actually below is what I meant after TDH.SYS.CONFIG.

And I think we can re-order the patches of enabling TDX extensions by 
moving the patch 04 as the first one.

> ----8<----
>

---

## [29] Xu Yilun — 2026-05-27
*Subject: Re: [PATCH 02/15] x86/virt/tdx: Add extra memory to TDX Module for
 Extensions*

> > +static void tdx_clflush_hpa_list(struct page *root, unsigned int nr_pages)
> > +{

Yes it is basically the same as tdx_clflush_page().

> tdx_clflush_page() did. Then, any chance we can use tdx_clflush_page() here

But I don't think we should convert hpa/page/va back and forth just for
re-using one line of code.

> so that we have a single central place of the comment to explain the kernel
> design decision.

How about I add a comment here to connect this wrapper to
tdx_clflush_page():

/*
 * Unconditionally flush the pages regardless of CLFLUSH_BEFORE_ALLOC. Inherit
 * the same decision as tdx_clflush_page().
 */
static void tdx_clflush_hpa_list(struct page *root, unsigned int nr_pages)
...

---

## [30] Xu Yilun — 2026-05-27
*Subject: Re: [PATCH 04/15] x86/virt/tdx: Enable the Extensions right after
 basic TDX Module init*

On Mon, May 25, 2026 at 09:00:32AM +0300, Tony Lindgren wrote:
> On Fri, May 22, 2026 at 11:41:17AM +0800, Xu Yilun wrote:
> > The detailed initialization flow for TDX Module Extensions has been

I'm good to it. The Extension initialization will not start without
add-on features anyway. Let me move the patch as the first one to avoid
tag churn.

---

## [31] Sohil Mehta — 2026-05-26
*Subject: Re: [PATCH 00/15] Enable TDX Module Extensions and DICE-based TDX
 Quoting*

Hello,

On 5/21/2026 8:41 PM, Xu Yilun wrote:

> The first 4 patches will eventually need an ack by an x86 maintainer, so
> please review with that in mind.

I am looking at this from an x86 reviewer perspective with limited prior
TDX knowledge.

> == Overview ==
> 

Can we explain a bit more about why these extensions are needed or what
would happen if the kernel didn't enable them? I ran the series through
an LLM for my curiosity. I think something on the below lines might be a
good addition for the cover letter itself.

(Please verify)

The TDX module's normal SEAMCALLs are designed to be short,
non-preemptible operations. However, some newer features (like
DICE-based TDX Quoting) require complex, potentially long-running
computations that can't complete within the tight constraints of a
single non-preemptible SEAMCALL.

The "TDX Module Extensions" solve this by introducing "Extension
SEAMCALLs" — a new class of SEAMCALLs that are:

* Long-running — they may take significant time to complete (e.g.,
cryptographic operations for attestation/quoting).

* Hard-IRQ preemptible — they can be interrupted by hardware interrupts
and later resumed, so they don't monopolize the CPU or cause
unacceptable interrupt latency.

Without this mechanism, complex operations like generating DICE
attestation quotes would either block interrupts for too long
(unacceptable for a host kernel) or wouldn't be possible inside the TDX
module at all. The Extensions give the TDX module a way to handle these
heavyweight tasks while remaining cooperative with the host's
interrupt/scheduling model.

> 
> TDX Module allows some add-on features to use the Extension. 

s/Module/module throughout the series.

The existing kernel code predominantly uses the lower case TDX "module".


> The first feature to use Extensions is DICE-based TDX Quoting [1].
> DICE is an industry-standard, certificate-backed attestation

I think enabling it by default on TDX platforms (with the module
extension) might make sense. But the explanation here is slightly
confusing.

You said earlier that "The Extensions consumes relatively large amount
of memory (~50MB)" so they must be off by default. Later you say that
"..the saving are little .."

Are you saying that the dynamic enabling of the extensions is not worth
it or the dynamic allocation of the memory needed to support them?

In addition, could you briefly describe the complexity we are trading off?

> This series has 2 distinct parts:
>

---

## [32] Sohil Mehta — 2026-05-26
*Subject: Re: [PATCH 01/15] x86/virt/tdx: Read global metadata for TDX Module
 Extensions*

On 5/21/2026 8:41 PM, Xu Yilun wrote:
> Add reading of the global metadata for TDX Module Extensions.
> 

The top comments in tdx_global_metadata.h and tdx_global_metadata.c say
that these files are autogenerated. I believe the script lives outside
the tree. Is there a plan to merge the script?

The generated code is optimized for space instead of readability. Also,
I see odd uncommented assignments u64 => u8/u16 all over the file. I am
assuming the upper bits are expected to be zero.

The patch is hard to review without the script. Can you post a link to
the updated script that led to this patch?


>  3 files changed, 23 insertions(+)
> 

The name ext_required seems like a boolean. It is also used like a
boolean later.
	if (!tdx_sysinfo.ext.ext_required)
		return 0;

But, IIUC, is it actually a mask that lists any feature that needs
extensions to work correctly? If so, it would be good to give it a name
that reflects its usage. Maybe:
features_requiring_ext or something better

As Xiaoyao mentioned, the struct requires a better explanation in the
commit log.

> +};

...

>  static __init int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
>  {

Other metadata reads aren't gated on feature checking. Is this check
manually added or autogenerated. If manually added, it should have a
code comment clarifying that.

> +		ret = ret ?: get_tdx_sys_info_ext(&sysinfo->ext);
> +

---

## [33] Xiaoyao Li — 2026-05-27
*Subject: Re: [PATCH 02/15] x86/virt/tdx: Add extra memory to TDX Module for
 Extensions*

On 5/27/2026 11:47 AM, Xu Yilun wrote:
>>> +static void tdx_clflush_hpa_list(struct page *root, unsigned int nr_pages)
>>> +{

Because we want/need to flush page as late as possible so that the page 
flush needs to happen right before SEAMCALL?

How about we pass in the struct page * and number into tdx_ext_mem_add() 
and construct the root page inside it?

>> so that we have a single central place of the comment to explain the kernel
>> design decision.

It works either. I don't have strong preference. Let's see if anyone 
else say something about it.

---

## [34] Xu Yilun — 2026-05-27
*Subject: Re: [RFC PATCH 14/15] x86/virt/tdx: Embed version info in SEAMCALL
 leaf function definitions*

> >   /*
> >    * TDX module SEAMCALL leaf functions

I'm trying to avoid a _Vx postfix if unnecessary. Don't make callers
have to choose between versions. The main MACRO should always point to
the latest version since later versions are backward compatible.

The next patch is an exception. I've found there is no public TDX Module
release available for TDH.SYS.CONFIG v1. I expect people just use the
un-versioned MACRO for development, but have to keep the explicitly
versioned _V0 macro for compatibility for now.

---

## [35] Xu Yilun — 2026-05-27
*Subject: Re: [PATCH 01/15] x86/virt/tdx: Read global metadata for TDX Module
 Extensions*

On Tue, May 26, 2026 at 11:05:48PM -0700, Sohil Mehta wrote:
> On 5/21/2026 8:41 PM, Xu Yilun wrote:
> > Add reading of the global metadata for TDX Module Extensions.

No, the plan of auto-generating is deprecated. Now we switch to manual
update.

> 
> The generated code is optimized for space instead of readability. Also,

Yes, it is. A new plan is to refactor the file in future.

> the updated script that led to this patch?
> 

No it is just a bool about Extentions needs to be initialized or not.

> extensions to work correctly? If so, it would be good to give it a name
> that reflects its usage. Maybe:

Will do. I also plan to change the patch organization: instead of the
old auto-generated patch splitting style, I will switch to a human-readable
style and fold these metadata readings directly into the patches that
actually use them (e.g., DPAMT and TDX Runtime Update).

---

## [36] Xu Yilun — 2026-05-27
*Subject: Re: [PATCH 02/15] x86/virt/tdx: Add extra memory to TDX Module for
 Extensions*

On Wed, May 27, 2026 at 02:38:27PM +0800, Xiaoyao Li wrote:
> On 5/27/2026 11:47 AM, Xu Yilun wrote:
> > > > +static void tdx_clflush_hpa_list(struct page *root, unsigned int nr_pages)

I think so. Let the flushing be part of the tdh call semantic.

> 
> How about we pass in the struct page * and number into tdx_ext_mem_add() and

I assume you don't suggest allocate root page inside the call, then we
need 3 parameters for the HPA_LIST_INFO:

  struct page *, unsigned int nr_pages, struct page *root

which I think too much.

I think your concern is to try not to introduce another tdx_clflush_
variant, but I believe this will happen, pfn based memory description is
on the way:

https://lore.kernel.org/all/20260430014929.24210-1-yan.y.zhao@intel.com/

---

## [37] Xiaoyao Li — 2026-05-27
*Subject: Re: [RFC PATCH 14/15] x86/virt/tdx: Embed version info in SEAMCALL
 leaf function definitions*

On 5/27/2026 2:45 PM, Xu Yilun wrote:
>>>    /*
>>>     * TDX module SEAMCALL leaf functions

I don't agree.

The later versions are backwards compatible, but the later versions 
might not be supported by the loaded TDX module.

Usually the callers will have to choose between versions due to the TDX 
module being used varies, just like the case in the next patch.

We can make TDH_VP_INIT represent the v1 as this patch because Linux 
mandates v1 when the code was merged. So it can be made the default.

> The next patch is an exception. I've found there is no public TDX Module
> release available for TDH.SYS.CONFIG v1. I expect people just use the

---

## [38] Xiaoyao Li — 2026-05-27
*Subject: Re: [PATCH 02/15] x86/virt/tdx: Add extra memory to TDX Module for
 Extensions*

On 5/27/2026 3:32 PM, Xu Yilun wrote:
> On Wed, May 27, 2026 at 02:38:27PM +0800, Xiaoyao Li wrote:
>> On 5/27/2026 11:47 AM, Xu Yilun wrote:

yeah, sort of.

> I think your concern is to try not to introduce another tdx_clflush_
> variant, but I believe this will happen, pfn based memory description is

I don't object the variant of tdx_clflush_hpa_list(), but suggest if 
tdx_clflush_page() can be used instead of raw clflush_cache_range()

Maybe we can try to put tdx_clflush_hpa_list() along with 
tdx_clflush_page() and tdx_clflush_pfn()? This way, I think we can save 
the separate comment.

---

## [39] Xu Yilun — 2026-05-27
*Subject: Re: [PATCH 00/15] Enable TDX Module Extensions and DICE-based TDX
 Quoting*

> > == Overview ==
> > 

I'm good to these detailed description. I'll add them to the
cover-letter.

> 
> > 

OK.

> 
> 

Sorry maybe I should say "the firmware design is: 1. Off by default.
2. Must be enabled after basic TDX module ...". I'll try to update the
words.

> "..the saving are little .."

Because for security purpose, these add-on features are always needed,
even if not all of them, so Extensions will most likely be enabled.

And even if someone switched them off all and saved the memory, compared
to the memory of a typical TDX capable system (lets say 1TB), the saving
is still little (0.001%).

> 
> Are you saying that the dynamic enabling of the extensions is not worth

The dynamic enabling of the Extensions is not worth.

> it or the dynamic allocation of the memory needed to support them?
> 

If we delay the Extensions initialization to the first Extension
SEAMCALL, we need to maintain additional TDX state machine for
lifecycle, and we need mechanisms to synchronize parallel Extension
enabling request from multiple callers.

---

## [40] Xu Yilun — 2026-05-27
*Subject: Re: [RFC PATCH 14/15] x86/virt/tdx: Embed version info in SEAMCALL
 leaf function definitions*

On Wed, May 27, 2026 at 03:44:45PM +0800, Xiaoyao Li wrote:
> On 5/27/2026 2:45 PM, Xu Yilun wrote:
> > > >    /*

No, we don't choose SEAMCALL versions based on TDX module versions. The
next patch is an exception, if by the time of merging there are releases
support TDX_SYS_CONFIG v1, I'd rather delete TDX_SYS_CONFIG_V0.

---

## [41] Kiryl Shutsemau — 2026-05-27
*Subject: Re: [PATCH 01/15] x86/virt/tdx: Read global metadata for TDX Module
 Extensions*

On Mon, May 25, 2026 at 02:54:40PM +0800, Xiaoyao Li wrote:
> On 5/22/2026 11:41 AM, Xu Yilun wrote:
> ...

This is my read too. Looks like we need a separate step after
config_tdx_module() to readout config-dependatant metadata.

---

## [42] Sohil Mehta — 2026-05-27
*Subject: Re: [PATCH 00/15] Enable TDX Module Extensions and DICE-based TDX
 Quoting*

On 5/27/2026 3:38 AM, Xu Yilun wrote:
> 
> Because for security purpose, these add-on features are always needed,

A cover letter is a good place to explain such nuances, alternate
approaches, and tradeoffs.

> And even if someone switched them off all and saved the memory, compared
> to the memory of a typical TDX capable system (lets say 1TB), the saving

In this case percentages make it harder to understand. Does it need a
fixed amount of memory (~50MB) irrespective of the feature or the number
of features? If so, it would be good to mention that.


>> In addition, could you briefly describe the complexity we are trading off?
> 

This would be good to include in the cover as well.

---

## [43] Sohil Mehta — 2026-05-27
*Subject: Re: [PATCH 01/15] x86/virt/tdx: Read global metadata for TDX Module
 Extensions*

On 5/27/2026 12:11 AM, Xu Yilun wrote:

>>> +struct tdx_sys_info_ext {
>>> +	u16 memory_pool_required_pages;
How does the kernel know which features need Extensions? Is there any
hardware enumeration or the kernel just keeps a static list?

---

## [44] Xu Yilun — 2026-05-28
*Subject: Re: [PATCH 01/15] x86/virt/tdx: Read global metadata for TDX Module
 Extensions*

On Wed, May 27, 2026 at 10:17:36AM -0700, Sohil Mehta wrote:
> On 5/27/2026 12:11 AM, Xu Yilun wrote:
> 

There is no HW enumeration, mm... seems this is an important reason that
we don't delay the Extensions enabling, kernel doesn't have to keep in
mind which features need Extensions.

---

## [45] Xu Yilun — 2026-05-28
*Subject: Re: [PATCH 01/15] x86/virt/tdx: Read global metadata for TDX Module
 Extensions*

On Wed, May 27, 2026 at 04:35:36PM +0100, Kiryl Shutsemau wrote:
> On Mon, May 25, 2026 at 02:54:40PM +0800, Xiaoyao Li wrote:
> > On 5/22/2026 11:41 AM, Xu Yilun wrote:

Yes.

> 
> This is my read too. Looks like we need a separate step after


The timing for when metadata becomes valid is now variable, e.g., the
TDX QUOTING metadata is only valid after TDH.QUOTE.INIT [1].

Based on recent discussion, I think we should introduce runtime metadata
reading interfaces for specific metadata sets as needed, rather than
another catch-all step right after config_tdx_module(). See [2] for the
proposed approach for Extensions metadata.

[1]: https://lore.kernel.org/all/20260522034128.3144354-7-yilun.xu@linux.intel.com/
[2]: https://lore.kernel.org/all/ahXAL41ZmIDHmgfu@yilunxu-OptiPlex-7050/

---

## [46] Xu Yilun — 2026-05-28
*Subject: Re: [PATCH 00/15] Enable TDX Module Extensions and DICE-based TDX
 Quoting*

On Wed, May 27, 2026 at 10:09:41AM -0700, Sohil Mehta wrote:
> On 5/27/2026 3:38 AM, Xu Yilun wrote:
> > 

No the memory needed varies depends on the feature or the number of
features. But currently I see the total requirement is ~50MB.

Yes I can drop the percentage, just state the amount in MB.

> 
> 

Yes.

---

## [47] Sohil Mehta — 2026-05-28
*Subject: Re: [PATCH 00/15] Enable TDX Module Extensions and DICE-based TDX
 Quoting*

On 5/27/2026 9:52 PM, Xu Yilun wrote:

> No the memory needed varies depends on the feature or the number of
> features. But currently I see the total requirement is ~50MB.
This is important consideration when defining the default policy. Could
you please elaborate on how this will scale in the future?

How are the memory requirements expected to grow with additional features?

Let's say a future platform has a lot more features and needs
significantly more memory. Wouldn't loading a legacy kernel with this
default policy lead to excessive wastage?

Maybe I am missing something obvious. The struct in patch 1,
memory_pool_required_pages is u16. So, will the Extensions support never
require more than 256MB?

---

## [48] Edgecombe, Rick P — 2026-05-28
*Subject: Re: [PATCH 01/15] x86/virt/tdx: Read global metadata for TDX Module
 Extensions*

On Fri, 2026-05-22 at 11:41 +0800, Xu Yilun wrote:
> +struct tdx_sys_info_ext {
> +	u16 memory_pool_required_pages;

> +	u8 ext_required;

The docs say this is a bool.

> +};
> +

---

## [49] Edgecombe, Rick P — 2026-05-28
*Subject: Re: [PATCH 01/15] x86/virt/tdx: Read global metadata for TDX Module
 Extensions*

On Thu, 2026-05-28 at 12:25 +0800, Xu Yilun wrote:
> > > 
> > > If I read the TDX module base spec correctly, the amount of memory for

Yea It is going to get confusing as to which metadata is populated at which
step. And if anything updates it.

I'm not sure we need to have all the metadata stored permanently. Some of the
metadata is needed for KVM and someday TSM. But a lot of it is onetime internal
use. There is some handiness in referring to a global var, but also those
reference add confusion as to when it got populated.

We only use ext_required, max_quote_size and memory_pool_required_pages each
once. So why not just read them to the stack and leave them out of struct
tdx_sys_info? Making it so there is not confusion of when it was read. And also
saving a global var that is never used again is a bit wrong.

How about for struct tdx_sys_info_ext read it to the stack in init_tdx_ext() and
pass it into init_tdx_ext_features(). For max_quote_size read it where it is
already read, but not into the global struct.

Do you see a problem?

---

## [50] Edgecombe, Rick P — 2026-05-28
*Subject: Re: [PATCH 04/15] x86/virt/tdx: Enable the Extensions right after
 basic TDX Module init*

On Fri, 2026-05-22 at 11:41 +0800, Xu Yilun wrote:
> The detailed initialization flow for TDX Module Extensions has been
> fully implemented.

I'm not sure what this means exactly. Why "detailed". Is that important?

>  Enable the flow after basic TDX Module
> initialization.

The Linux decision is whatever this patch turns out to be after community
review. So for the patch log we just need to justify why it's a good idea, not
not make an argument to defer to authority.

> 
> Note that the Extensions initialization flow will still not start if no

Hmm, this patch reads like we are finally doing the initialization up until this
point. Then it turns out we don't actually light up the new code yet... 

A lot of this diff is adding __init to the function added in the earlier
patches. Do we need to do this? Why not add them as __init in the original
patches?


I think we maybe want to say instead that we are setting up to enable extensions
at TDX module init time, and do the explanation of why. Then without the __init
stuff, the patch is just about the init time decision. Which seems about right
sized.

---

## [51] Edgecombe, Rick P — 2026-05-28
*Subject: Re: [RFC PATCH 05/15] x86/virt/tdx: Move tdx_tdr_pa() up in the file*

On Fri, 2026-05-22 at 11:41 +0800, Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> 

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [52] Edgecombe, Rick P — 2026-05-28
*Subject: Re: [RFC PATCH 06/15] x86/virt/tdx: Initialize Quoting extension
 during bringup*

On Fri, 2026-05-22 at 11:41 +0800, Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> 

Don't say "this patch" in tip logs. The patch is a temporary format, and some
x86 maintainers hate the term in logs.

>  does not include the opt-in portion of the initialization.
> It mainly lays the groundwork for TDX Quoting support. Opt-in will be

This could be imperative mood.

> 
> Signed-off-by: Peter Fang <peter.fang@intel.com>

---

## [53] Edgecombe, Rick P — 2026-05-28
*Subject: Re: [RFC PATCH 07/15] x86/virt/tdx: Prepare Quote buffer during
 extension bringup*

On Fri, 2026-05-22 at 11:41 +0800, Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> 

Can this be put in common terms. This is going to mean nothing to someone
reading this that doesn't already know the feature.

>  Because the Quote buffer is shared with TDX guests,

Why capitalize "Quote"?

> prepare the required metadata during Quoting extension bringup.

What does prepare the required metadata mean?

How does it being shared with TDX guest suggest this? Just that TDX guests will
need them? Is the reason just that only one is needed, so do it during global
init? 

> 
> This mostly involves determining the physical addresses of the Quote

Hmm, I think this should separate the type and variable declaration. It's not a
common pattern. I don't think there is an official rule.

> +
>  typedef void (*sc_err_func_t)(u64 fn, u64 err, struct tdx_module_args *args);

Just return ENOMEM here. vfree() doesn't do any work if passed NULL, but it's
weird flow.

> +	}
> +

Huh?

> +	 * Only the last page needs to be filled. All the other pages will be
> +	 * fully populated.

What are the entries? And what is a -1 in u8? Or is it supposed to be u64?
Please make this a lot clearer.

> +
> +	qbuf = vcalloc(nr_pages, PAGE_SIZE);

Can you maybe just explain this format that you are building in like one
sentence at the beginning of the function? "The quote buffer is passed to the
tdx module in a format that like... (some common terms that have no TDX
jargon)."

> +			pfn = vmalloc_to_pfn(&qlist[i + 1]);
> +			qlist[i] = PFN_PHYS(pfn);

Do we need a vmalloc_to_pa() helper? Maybe put it in terms of tdx format. Like
vmalloc_pfn_to_tdxpa() and keep it here? The tdx update stuff does this a bunch
too.

> +	qdata->hpa_list_pa = PFN_PHYS(pfn);
> +

It only returns -ENOMEM, so do we need the err var?

> +}
> +

How come this patch gets error handling? Why is it needed now when it wasn't
before?

> +
> +	nr_quote_pages = PAGE_ALIGN(tdx_sysinfo.quote.max_quote_size) /

Err... what happens in ENOMEM scenario? NULL pointer later?

>  }
>

---

## [54] Edgecombe, Rick P — 2026-05-28
*Subject: Re: [RFC PATCH 09/15] x86/virt/tdx: Add interface to generate a Quote*

On Fri, 2026-05-22 at 11:41 +0800, Xu Yilun wrote:
> +void *tdx_quote_generate(struct tdx_td *td, void *in_data, u32 in_data_len,
> +			 u32 *quote_len)

Do we really need this check? We can't trust the caller to pass the right size?

> +
> +	mutex_lock(&tdx_quote_lock);


How do these various error conditions happen?

> +		goto out;
> +

So at init time we allocate a vmalloc for the quote and pre-populate the
hpa_list. Then we use it every time and copy the contents to a new vmalloc.
Would it really be that hard to keep the hpa list allocation around, do a
vmalloc here and update the pfn list. Then do get quote on that and pass back
the vmalloc we just allocated? Just feels like global reuse way has extra pieces
in it. Compared to the whole quoting operation, this vmalloc_to_pfn() loop is
probably not very expensive.

> +
> +out:

---

## [55] Xu Yilun — 2026-05-29
*Subject: Re: [PATCH 01/15] x86/virt/tdx: Read global metadata for TDX Module
 Extensions*

> Yea It is going to get confusing as to which metadata is populated at which
> step. And if anything updates it.

I think you mean "pass it into tdx_ext_mem_setup(). Yes, good to me.

> already read, but not into the global struct.

---

## [56] Xu Yilun — 2026-05-30
*Subject: Re: [PATCH 01/15] x86/virt/tdx: Read global metadata for TDX Module
 Extensions*

On Thu, May 28, 2026 at 09:00:12PM +0000, Edgecombe, Rick P wrote:
> On Fri, 2026-05-22 at 11:41 +0800, Xu Yilun wrote:
> > +struct tdx_sys_info_ext {

mm.. OK.  We don't have to follow the auto-generated format now, so bool
is good to me.

> 
> > +};

---

## [57] Xu Yilun — 2026-05-30
*Subject: Re: [PATCH 04/15] x86/virt/tdx: Enable the Extensions right after
 basic TDX Module init*

On Thu, May 28, 2026 at 09:32:08PM +0000, Edgecombe, Rick P wrote:
> On Fri, 2026-05-22 at 11:41 +0800, Xu Yilun wrote:
> > The detailed initialization flow for TDX Module Extensions has been

It's not important. I should re-phrase, The entire initialization flow...

> 
> >  Enable the flow after basic TDX Module

Understood. I'll re-phrase this paragraph according to all the comments,
especially the last sentence.

> 
> > 

Yes. Since the patch doesn't actually light up anything new, I think it
could just be the first patch of Extensions so add __init at the first
place.

---

## [58] Xu Yilun — 2026-06-01
*Subject: Re: [PATCH 00/15] Enable TDX Module Extensions and DICE-based TDX
 Quoting*

On Thu, May 28, 2026 at 12:50:34PM -0700, Sohil Mehta wrote:
> On 5/27/2026 9:52 PM, Xu Yilun wrote:
> 

I queried the TDX module team, and the answer is they almost grow
linear. I measured the only feature - PCIe Link encryption (SPDM) - on
my hand again, the precise memory consumption is now 35M.

In the foreseeable future, the features are SPDM, DICE & TD Migration,
so will cost ~105M at most. I think the number still works with the
default policy.

> 
> Let's say a future platform has a lot more features and needs

A legacy kernel won't consume Extensions memory. The Extensions memory
is only required by TDX module when add-ons features are explicitly
configured via TDH.SYS.CONFIG [1]. For legacy kernel, no add-on features
configured so no memory consumption.

But yes, if the features grow rapidly out of expectation, may need new
options to switch something off. I think if we discuss later when the
need actually arises.

[1]: https://lore.kernel.org/all/20260522034128.3144354-16-yilun.xu@linux.intel.com/

> 
> Maybe I am missing something obvious. The struct in patch 1,

Good catch. TDX module team admitted this is an issue. They want to
increase the size to 4 bytes for future.

---

## [59] Sohil Mehta — 2026-06-01
*Subject: Re: [PATCH 00/15] Enable TDX Module Extensions and DICE-based TDX
 Quoting*

>>
>> Let's say a future platform has a lot more features and needs

So, the TDX module will only report memory_pool_required_pages for
add-on features that have been configured by the kernel? This would be
good to clarify in the cover letter.

> For legacy kernel, no add-on features configured so no memory
> consumption.

I was referring to the first kernel that has support for one TDX
extension. I am mainly trying to ensure that a kernel with support for
one TDX extension only consumes memory for that feature (even when it is
loaded on a hardware platform that supports multiple TDX extensions).

> But yes, if the features grow rapidly out of expectation, may need new
> options to switch something off. I think if we discuss later when the

---

## [60] Xu Yilun — 2026-06-02
*Subject: Re: [PATCH 00/15] Enable TDX Module Extensions and DICE-based TDX
 Quoting*

On Mon, Jun 01, 2026 at 01:17:59PM -0700, Sohil Mehta wrote:
> 
> >>

Correct.

> good to clarify in the cover letter.

Will do.

> 
> > For legacy kernel, no add-on features configured so no memory

Yes. The first kernel that supports for one add-on feature will only
consume memory for that feature. The other HW/FW supported features
will not be configured so will not consume extra memory.

I think I should refactor the cover-letter and changelogs based on all
these comments. Thanks for all the inputs that help me see what missed.

> 
> > But yes, if the features grow rapidly out of expectation, may need new

---

## [61] Tony Lindgren — 2026-06-05
*Subject: Re: [PATCH 03/15] x86/virt/tdx: Make TDX Module initialize Extensions*

On Fri, May 22, 2026 at 11:41:16AM +0800, Xu Yilun wrote:
> --- a/arch/x86/virt/vmx/tdx/tdx.c
> +++ b/arch/x86/virt/vmx/tdx/tdx.c

How about "Initialize the TDX Module Extensions for Extension-SEAMCALLs"
above for the comment?

Other than that:

Reviewed-by: Tony Lindgren <tony.lindgren@linux.intel.com>

---

## [62] Kishen Maloor — 2026-06-06
*Subject: Re: [PATCH 00/15] Enable TDX Module Extensions and DICE-based TDX
 Quoting*

On 5/21/26 8:41 PM, Xu Yilun wrote:
> ...
> This series has 2 distinct parts:
Perhaps the extensions enabling patches could be organized more simply as
these three?

1. Add TDX extensions metadata structure and accessor
2. Add TDH.EXT.MEM.ADD
3. Add TDH.EXT.INIT and wire extensions init into init_tdx_module()

This introduces the SEAMCALLs and lets the wiring land with the patch
that completes the init flow, avoiding a separate "enable" patch.

---

## [63] Kishen Maloor — 2026-06-06
*Subject: Re: [PATCH 02/15] x86/virt/tdx: Add extra memory to TDX Module for
 Extensions*

On 5/21/26 8:41 PM, Xu Yilun wrote:
> TDX Module introduces a new concept called "TDX Module Extensions" to
> support long running / hard-irq preemptible flows inside. This makes TDX

The retry loop compares the full return value against TDX_INTERRUPTED_RESUMABLE. Should
it mask with TDX_SEAMCALL_STATUS_MASK first, in case the module sets any
lower detail bits?

Ditto for TDH.EXT.INIT in patch 3.

> +
> +	if (r != TDX_SUCCESS)

The SEAMCALL takes a scatter list (HPA_LIST_INFO), so the module
doesn't require contiguity. If the goal is just to avoid scattering
pages across many 2MB regions, maybe dense, 2MB-aligned allocations should
achieve that without a single pool-wide contiguous block.

> +	if (!page) {
> +		ret = -ENOMEM;

Would it be better to allocate per-batch (i.e. one root page's worth
at a time) rather than the whole pool up front?

That way an intermediate TDH.EXT.MEM.ADD failure wouldn't leak
all nr_pages. Also, a batch is up to 512 pages (= 2MB) and its allocation
could be 2MB-aligned, addressing your fragmentation concern.

> +
> +		ret = tdx_ext_mem_add(virt_to_page(root), nents);

Could this be named init_tdx_extensions() instead to disambiguate
from tdx_ext_init() in patch 3?

> +{
> +	if (!(tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_EXT))

---

## [64] Kishen Maloor — 2026-06-06
*Subject: Re: [PATCH 04/15] x86/virt/tdx: Enable the Extensions right after
 basic TDX Module init*

On 5/21/26 8:41 PM, Xu Yilun wrote:
> The detailed initialization flow for TDX Module Extensions has been
> fully implemented. Enable the flow after basic TDX Module

Is it a reasonable policy to fail TDX bringup entirely upon failing
initialization of extensions (which are "add-on features")?

The handling of tdx_quote_init() in Patch 6 suggests a more
best-effort approach.

> +
>   	pr_info("%lu KB allocated for PAMT\n", tdmrs_count_pamt_kb(&tdx_tdmr_list));

---

## [65] Kishen Maloor — 2026-06-06
*Subject: Re: [RFC PATCH 15/15] x86/virt/tdx: Enable TDX Quoting extension*

On 5/21/26 8:41 PM, Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> 

Is it necessary to add _Vx macros when multiple versions can co-exist?

Just wondering if it would be cleaner in the following way?

- Leave the macros set at the current (non-deprecated) baseline version.
- Select vX using SEAMCALL_LEAF_VER() in config_tdx_module() when a vX feature
   is enabled.

u64 seamcall_fn = TDH_SYS_CONFIG;
...
if (tdx_sysinfo.features.tdx_features0 & TDX_FEATURES0_QUOTE) {
...
     seamcall_fn = SEAMCALL_LEAF_VER(TDH_SYS_CONFIG, 1);

> +#define TDH_SYS_CONFIG			SEAMCALL_LEAF_VER(TDH_SYS_CONFIG_V0, 1)
>   #define TDH_EXT_INIT			60

---

## [66] Xu Yilun — 2026-06-08
*Subject: Re: [PATCH 00/15] Enable TDX Module Extensions and DICE-based TDX
 Quoting*

On Sat, Jun 06, 2026 at 09:36:41PM -0700, Kishen Maloor wrote:
> On 5/21/26 8:41 PM, Xu Yilun wrote:
> > ...

Yes, several comments point to a same concern for patch organization - no
need a separate "enable" patch. Also a more sound justfication to me is,
the Extension will not actually been enabled until an add-on feature is
explicitly configured (See patch #15). So we could add steps in nature
order without worrying the incomplete flow breaks the kernel.

My reordering is:

 1. Add a placeholder for Extension initialization to hook into
    init_tdx_module(). Give a chance to explain the considerations of
    the enable-at-boot-up policy.

 2. Detect if Extension is required based on the metadata, if no, skip.
    So no side effect for following steps.

 3. Add TDH.EXT.MEM.ADD

 4. Add TDH.EXT.INIT
>

---

## [67] Xu Yilun — 2026-06-08
*Subject: Re: [PATCH 02/15] x86/virt/tdx: Add extra memory to TDX Module for
 Extensions*

> > +static int tdx_ext_mem_add(struct page *root, unsigned int nr_pages)
> > +{

mm.. there is an existing case for TDX_INTERRUPTED_RESUMABLE which
doesn't do the mask:

  err = tdh_phymem_cache_wb(resume);
  switch (err) {
	case TDX_INTERRUPTED_RESUMABLE:
		continue;

I believe we don't mask it. TDX_INTERRUPTED_RESUMABLE should not carry
any lower bits according to its bit definition, if it does it's a
problem we should not skip.

> 
> Ditto for TDH.EXT.INIT in patch 3.

So IIUC allocating 2MB by 2MB has the pros:

  - Larger chance to get the memory.
  - Less memory waste when TDH.EXT.MEM.ADD failed.

and the cons:

  - Still fragment 4M & 1G memory region.


I think first of all we should focus on the normal path when Extension is
successfully initialized and memory is added, note these memory can
never be reclaimed in this case, so memory fragmentation becomes the
primary considration.

And in TDX platform, the TDH.EXT.MEM.ADD failure is not expected to
happen, which means the TDX module is buggy and from Confidential
Computing POV we should not continue, we should change to a new module
and reboot. So less memory waste doesn't matter much actually.

Then, the Extension initialization is done at bootup time. We can get
the memory in big chance. If we really can't, it is a signal that the
system is not well configured for TDX, and failing earlier isn't such
a bad thing to me.

So for now I still think alloc_contig_pages() is better than 2M-by-2M
allocation.

> 
> > +

Yes, good to me.

I'm changing all Extensions to Extension, cause the SPEC says "TDX
Module Extension". So I'll use init_tdx_extension().

Thanks,
Yilun

---

## [68] Xu Yilun — 2026-06-08
*Subject: Re: [PATCH 04/15] x86/virt/tdx: Enable the Extensions right after
 basic TDX Module init*

> > +static __init int init_tdx_ext(void)
> >   {

mm.. I think TDX Extension is not strictly an add-on feature from OS
POV. It is still a fundamental TDX infrastructure. Host should not
look into the Module and create substates like Base-good-Extension-bad or
both-good. There are some considerations:

 - Extension cannot be explicitly configured by TDH.SYS.CONFIG, it is
   implicitly configured by TDX Module if an add-on feature requires it.

 - There is no enumeration of which SEAMCALLs are Extension-SEAMCALLs so
   Base-good-Extension-bad actually brings more chaos later.

So the series is making all effort to make TDX bringup a stateless
process, no intermediate state.

> 
> The handling of tdx_quote_init() in Patch 6 suggests a more

TDX Quoting is however a clear self-contained add-on feature from OS POV.
Though I'm not sure if a TDX platform is still a safe TCB with DICE
available but failed, and good for "best-effort" policy? Maybe Peter
could answer.
>

---

## [69] Xu Yilun — 2026-06-08
*Subject: Re: [RFC PATCH 15/15] x86/virt/tdx: Enable TDX Quoting extension*

> > diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
> > index 10aff23cd01f..524a14c01aa6 100644

My perference is to have the most simple rule for the unversioned macro.
And leave all workarounds to _Vx macros, they will eventually been
removed or deprecated.

Anyway this patch is not expected to merge with this series, maybe we
will have a public release with V1 supported when it is to be merged,
then we don't have to make such a hard choice.

> 
> u64 seamcall_fn = TDH_SYS_CONFIG;

---

## [70] Adrian Hunter — 2026-06-08
*Subject: Re: [PATCH 00/15] Enable TDX Module Extensions and DICE-based TDX
 Quoting*

On 22/05/2026 06:41, Xu Yilun wrote:
> This posting is just to collect initial review.
> 

For me it would be easier to understand by starting higher level,
like:

"TDX Module Extensions enables optional but important TDX features
 - such as DICE-based attestation quoting, TDX Connect, and live
migration - that require substantially more processing time than
core TDX operations, and also additional memory."

Also I would find it helpful to clarify how "TDX Module Extensions"
enhances interruptibility for Extension SEAMCALLs compared with
regular SEAMCALLs, since "hard-irq preemptible flows" had me
initially thinking along the wrong lines.

> 
> TDX Module allows some add-on features to use the Extension. The first

---

## [71] Adrian Hunter — 2026-06-09
*Subject: Re: [PATCH 01/15] x86/virt/tdx: Read global metadata for TDX Module
 Extensions*

On 22/05/2026 06:41, Xu Yilun wrote:
> Add reading of the global metadata for TDX Module Extensions.

For tip, isn't the expectation to explain the context first.  The
very first patch, might be a good place to explain a bit about
TDX Module Extensions in general.

> 
> TDX Module Extensions is an add-on feature enumerated by TDX_FEATURES0.

---

## [72] Adrian Hunter — 2026-06-09
*Subject: Re: [PATCH 02/15] x86/virt/tdx: Add extra memory to TDX Module for
 Extensions*

On 22/05/2026 06:41, Xu Yilun wrote:
> +static int tdx_ext_mem_add(struct page *root, unsigned int nr_pages)
> +{

Kishon already mentioned checking only the status

> +
> +	if (r != TDX_SUCCESS)

Similarly could this also be TDX_EXT_MEMORY_POOL_FULL?

> +		return -EFAULT;
> +

---

## [73] Adrian Hunter — 2026-06-09
*Subject: Re: [PATCH 03/15] x86/virt/tdx: Make TDX Module initialize Extensions*

On 22/05/2026 06:41, Xu Yilun wrote:
> +/* Initialize the TDX Module Extensions then Extension-SEAMCALLs can be used */

Reads slightly better without "the", so taking Tony's suggestion
one word less:

"Initialize TDX Module Extensions for Extension-SEAMCALLs"

> +static int tdx_ext_init(void)
> +{

There seems to be TDX_PREV_FEATURES_ENABLED which is unused,
but could it turn up here?

> +		return -EFAULT;
> +
Otherwise:

Reviewed-by: Adrian Hunter <adrian.hunter@intel.com>

---

## [74] Xu Yilun — 2026-06-10
*Subject: Re: [PATCH 01/15] x86/virt/tdx: Read global metadata for TDX Module
 Extensions*

On Tue, Jun 09, 2026 at 04:06:50PM +0300, Adrian Hunter wrote:
> On 22/05/2026 06:41, Xu Yilun wrote:
> > Add reading of the global metadata for TDX Module Extensions.

Yes. I'm trying to add a long context for the first patch but was
suggested to move to cover-letter. I think I can add a brief
introduction at the beginning:

  TDX module introduces a new concept caled "TDX module Extension" to
  support long running / hard-irq preemptible flows inside. ...

---

## [75] Xu Yilun — 2026-06-10
*Subject: Re: [PATCH 02/15] x86/virt/tdx: Add extra memory to TDX Module for
 Extensions*

On Tue, Jun 09, 2026 at 04:38:31PM +0300, Adrian Hunter wrote:
> On 22/05/2026 06:41, Xu Yilun wrote:
> > +static int tdx_ext_mem_add(struct page *root, unsigned int nr_pages)

Could you elaborate on why we should mask? I assume the mask is only
needed when the lower bits ([31:0]) are defined to contain extra
information. TDX_INTERRUPTED_RESUMABLE is not the case so we could make
the code change simpler.

And if some non-zero bits appears there, it is a Module bug that we
should not skip.

> 
> > +

I don't think we should pass the case. The Module provides the number of
required pages via metadata, host follows and feeds pages but the Module
said "Sorry, I'm already full". This is inconsistent behavior that we
should call out.

> 
> > +		return -EFAULT;

---

## [76] Adrian Hunter — 2026-06-10
*Subject: Re: [PATCH 02/15] x86/virt/tdx: Add extra memory to TDX Module for
 Extensions*

On 10/06/2026 08:13, Xu Yilun wrote:
> On Tue, Jun 09, 2026 at 04:38:31PM +0300, Adrian Hunter wrote:
>> On 22/05/2026 06:41, Xu Yilun wrote:

Agreed

> 
>>

TDX_EXT_MEMORY_POOL_FULL is not an error code. It is a success code,
so the question is whether it will ever show up on, say, the very last
TDH_EXT_MEM_ADD.

> 
>>

---

## [77] Xu Yilun — 2026-06-10
*Subject: Re: [PATCH 02/15] x86/virt/tdx: Add extra memory to TDX Module for
 Extensions*

> >>> +	if (r != TDX_SUCCESS)
> >>

It will not show up. I got from Module team that it shows up when the
poll is already full and host still adds more pages.

---

## [78] Xu Yilun — 2026-06-10
*Subject: Re: [PATCH 03/15] x86/virt/tdx: Make TDX Module initialize Extensions*

On Tue, Jun 09, 2026 at 06:14:22PM +0300, Adrian Hunter wrote:
> On 22/05/2026 06:41, Xu Yilun wrote:
> > +/* Initialize the TDX Module Extensions then Extension-SEAMCALLs can be used */

OK, included.

> 
> > +static int tdx_ext_init(void)

“Yes, but not now.” from Module team. It is some future thing
under discussion.

---

## [79] Adrian Hunter — 2026-06-11
*Subject: Re: [RFC PATCH 05/15] x86/virt/tdx: Move tdx_tdr_pa() up in the file*

On 22/05/2026 06:41, Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> 

them -> it

---

## [80] Adrian Hunter — 2026-06-11
*Subject: Re: [RFC PATCH 06/15] x86/virt/tdx: Initialize Quoting extension
 during bringup*

On 22/05/2026 06:41, Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> 

Is there a reason Linux needs to support TDX with failed Quote
extension initialization?

> +static void tdx_quote_init(void)
> +{

Elsewhere it tends to be:

	if (r != TDX_SUCCESS)

> +		return;
> +

---

## [81] Adrian Hunter — 2026-06-11
*Subject: Re: [RFC PATCH 09/15] x86/virt/tdx: Add interface to generate a Quote*

On 22/05/2026 06:41, Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> 

Isn't the concurrency configurable, so supporting only 1 instance
is a decision of the software implementation, not a TDX limitation?

> +static u64 tdx_quote_get(struct tdx_td *td, u64 in_data_pa, u64 in_data_len,
> +			 u64 hpa_list_pa, u64 total_len, u64 *quote_len)

Need to explain why

> +		.rdx = QUOTE_ID_MASK & (u64)-1,
> +		.r8 = in_data_pa,

...

> +	r = tdx_quote_get(td, quote_data.hpa_list[0], (u64)in_data_len,
> +			  quote_data.hpa_list_pa, quote_data.buf_len, &out_len);

Is r != TDX_SUCCESS more consistent

> +		goto out;

---

## [82] Adrian Hunter — 2026-06-11
*Subject: Re: [RFC PATCH 10/15] x86/tdx: Move and rename Quote request
 structure*

On 22/05/2026 06:41, Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> 

Seems inconsistent to rename the struct but not the variable names

>  {
>  	int i = 0;

Please note, the timeout condition in wait_for_quote_completion() is
broken, in that the final value of i is timeout + 1 not timeout.
Since you are in the same area, that needs fixing that too.

>  
> @@ -269,7 +250,7 @@ static int wait_for_quote_completion(struct tdx_quote_buf *quote_buf, u32 timeou

---

## [83] Adrian Hunter — 2026-06-11
*Subject: Re: [RFC PATCH 13/15] KVM: TDX: Support event-notify interrupts only
 with userspace quoting*

On 22/05/2026 06:41, Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> 

Breaks how exactly?

Seems like a TDX guest has no way to know whether the VMM will use
the Event Notify Interrupt anyway, so it cannot rely upon it, so
it should already handle the case when the interrupt does not fire.

> 
> No known guest currently requires event-notify interrupt support, so

If no guest is using it, then why does it need special treatment?

> 
> Update the KVM API Documentation to reflect the change.

There is an Attestation section in Documentation/virt/kvm/x86/intel-tdx.rst
that could be updated too.

> +                  KVM only supports version 1 of the GetQuote request.

Is that relevant here?

>  
>   * ``TDVMCALL_GET_TD_VM_CALL_INFO``: the guest has requested the support

Is that really necessary?

>  
>  KVM may add support for more values in the future that may cause a userspace

---

## [84] Adrian Hunter — 2026-06-12
*Subject: Re: [RFC PATCH 14/15] x86/virt/tdx: Embed version info in SEAMCALL
 leaf function definitions*

On 22/05/2026 06:41, Xu Yilun wrote:
> Embed version information in SEAMCALL leaf function definitions rather
> than let the caller open code them. For now, only TDH.VP.INIT is

> @@ -31,7 +44,7 @@
>  #define TDH_VP_CREATE			10

FWIW I find the macro a bit ugly, and hiding the version number in
the leaf number macro a little counter-intuitive compared with setting
it at the call site.  It anyway needs some explanation at the call site.

> @@ -2217,8 +2217,8 @@ u64 tdh_vp_init(struct tdx_vp *vp, u64 initial_rcx, u32 x2apicid)
>  		.r8 = x2apicid,

Now the reader has to go look at TDH_VP_INIT.

---

## [85] Dan Williams (nvidia) — 2026-06-12
*Subject: Re: [PATCH 00/15] Enable TDX Module Extensions and DICE-based TDX
 Quoting*

Xu Yilun wrote:
> This posting is just to collect initial review.
> 

The internal implementation details of extension seamcalls buries the
lead on why this mechanism is important, why Linux should care, and why
this brings TDX in line with the other major CC architectures. Something
like:

===
To date, SEAMCALLs have been short lived routines that monopolize the
CPU for their duration. This limits their utility for implementing
higher order security protocols or pushes complexity into Linux. The
Linux appetite for ingesting complexity is low, so TDX now adds a new
class of SEAMCALLs that are preemptible and resumable. This capability
enables higher order service APIs to carry out a security protocol like
"establish an SPDM session".

The TDX "Extension SEAMCALL" capability is akin to ARM CCA's "Stateful
RMI Operations (SRO)", and achieves similar externalized complexity
relief as a dedicated hardware coprocessor like AMD SEV-SNP. The
mechanism is "give the service environment some memory", "invoke the
service API", and "continue invoking until complete". All protocol state
is internal the service API.

The simplest class of extension SEAMCALLs to support are in support of
"DICE-based TDX Quoting", a service to turn guest launch attestation
reports into a document that can be externally verified.
===

> TDX Module allows some add-on features to use the Extension. The first
> feature to use Extensions is DICE-based TDX Quoting [1]. DICE is an

This confuses the TDX design with the Linux design, and sets up "50MB" as
something to be quibbled with. The Linux design is turn on all the
features that Linux knows about all the time. Unless and until the "any
available, all the time" becomes untenable it just simplifies the init
flow to not play piecemeal games. Await evidence to change the simple
policy. Suffice to say the cost of this policy will burn 10s of
megabytes.

> It must be enabled after basic TDX
> Module initialization and when add-on features require it. To enable

No need to talk about details not in this series. I would maybe just
note that quoting is the simplest first consumer and was chosen as the
lead vehicle over TDX Connect previously posted in case anyone asks.

---

## [86] Dan Williams (nvidia) — 2026-06-12
*Subject: Re: [PATCH 01/15] x86/virt/tdx: Read global metadata for TDX Module
 Extensions*

Xu Yilun wrote:
> Add reading of the global metadata for TDX Module Extensions.
> 

Others already commented on the patch ordering, so I will just comment
on the changelog to recommend referring back to the "any available
extension, all the time" implementation policy rather than saying "Linux
requires" which is ambiguous.

The patch reordering will make it more clear that
memory_pool_required_pages scales based on the number of features that
Linux grows enabling for at configuration time.

---

## [87] Dan Williams (nvidia) — 2026-06-12
*Subject: Re: [PATCH 02/15] x86/virt/tdx: Add extra memory to TDX Module for
 Extensions*

Xu Yilun wrote:
> TDX Module introduces a new concept called "TDX Module Extensions" to
> support long running / hard-irq preemptible flows inside. This makes TDX

Like I said on the cover, I think "long running hard-irq preemptible"
invites more questions that it answers. The service calls are not "long
running" on their own. I think it is sufficient to say they are
resumable unlike typical calls that run to completion while monopolizing
the CPU.

> Currently, TDX Module memory use is relatively static. But, the
> Extensions need to use memory more dynamically. While 'static' here

Rick commented on this as well, but a simpler way to say it is
extensions receive a one time memory pool allocation at init time.  The
extension uses that pool as its baseline for its own internal state and
data for the service APIs it offers.

> The process is mostly the same as adding PAMT. The kernel queries TDX
> Module how much memory needed, allocates it, hands it over, and never

I mention below, but I do not think the reader cares that the TDX Module
calls an array of physical addresses a "root" page.

> 
> Introduce a tdx_clflush_hpa_list() helper to flush shared cache before

To be clear I believe there is a low chance of fragmentation given this
allocation happening early. However, at 10s of MB the benefit of
isolating blocks of PFNs that will never be returned, it makes to not
use the buddy allocator for that.

> Co-developed-by: Zhenzhong Duan <zhenzhong.duan@intel.com>
> Signed-off-by: Zhenzhong Duan <zhenzhong.duan@intel.com>

I think this "root" term is a holdover from the complicated TDX Connect
case where it might sometimes be this odd "singleton" object? You could
just make it this for actual type safety.

struct tdx_hpa_list {
	u64 phys[PAGE_SIZE/sizeof(u64)];
}

> +
> +	page = alloc_contig_pages(nr_pages, GFP_KERNEL, numa_mem_id(),

This looks wrong, sizeof(struct page)?, or size of physical address?

Becomes less error prone if you do:

min(nr_pages - i, ARRAY_SIZE(hpa_list->phys))

> +		int j;
> +

You can declare j in the for loop.

> +			root[j] = page_to_phys(page + i + j);
> +

Perhaps to be friendlier to folks without the source code in front of
them drop the comment and do:

WARN(ret, "Fatal: TDX Module failed (%d) to accept memory, stranded %ld pages\n", ret, nr_pages)

...the once flavor not needed, right? It's toast at this point.

---

## [88] Dan Williams (nvidia) — 2026-06-12
*Subject: Re: [RFC PATCH 06/15] x86/virt/tdx: Initialize Quoting extension
 during bringup*

Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> 

Is this micro-optimization worth it? What are the classes of quote-init
failures vs just make the policy be anything in the module must init.

> This patch does not include the opt-in portion of the initialization.
> It mainly lays the groundwork for TDX Quoting support. Opt-in will be

It is unconditionally calling quote init even if the feature is not
present. Is that not a problem?

---

## [89] Dan Williams (nvidia) — 2026-06-12
*Subject: Re: [RFC PATCH 10/15] x86/tdx: Move and rename Quote request
 structure*

Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> 

Drop the ifdef guards.

There is no cost to allowing a data structure to be defined
unconditionally. Usually the ifdef guards are to prevent compilation
errors when symbols do not resolve.

Otherwise looks ok.

Reviewed-by: Dan Williams <djbw@kernel.org>

---

## [90] Dan Williams (nvidia) — 2026-06-12
*Subject: Re: [PATCH 04/15] x86/virt/tdx: Enable the Extensions right after
 basic TDX Module init*

Xu Yilun wrote:
> The detailed initialization flow for TDX Module Extensions has been
> fully implemented. Enable the flow after basic TDX Module

No real point in rehashing the rationale for the "any available, all the
time" policy yet again especially when this directly conflicts with the
"relatively large amount" comment in the original cover letter.

Otherwise I agree with the proposed reordering of this initial series.

In general though, no big showstoppers for me in this first 4.

---

## [91] Dan Williams (nvidia) — 2026-06-12
*Subject: Re: [RFC PATCH 12/15] KVM: TDX: Add in-kernel Quote generation*

Xu Yilun wrote:
> From: Peter Fang <peter.fang@intel.com>
> 
[..]
> +static u64 __get_quote_kernel(struct kvm_vcpu *vcpu, struct tdx_quote_req *req,
> +			      size_t req_len, gpa_t req_gpa, size_t total_len)

No, it is freed by cleanup as far as I can see

> +	void *quote_data __free(kvfree) =

...this shadows the global "quote_data". A global really should be
properly namespaced.

---

## [92] Xu Yilun — 2026-06-13
*Subject: Re: [RFC PATCH 14/15] x86/virt/tdx: Embed version info in SEAMCALL
 leaf function definitions*

On Fri, Jun 12, 2026 at 08:47:26AM +0300, Adrian Hunter wrote:
> On 22/05/2026 06:41, Xu Yilun wrote:
> > Embed version information in SEAMCALL leaf function definitions rather

We actually discussed about this and realized we don't need to keep
version. This is because:

  1. Newer version SEAMCALLs are always compatible with older ones.
  2. System security requires us to stop using an older TDX module when
     there is a newer one. So don't try to support an older TDX module
     which doesn't understand newer version SEAMCALLs.

https://lore.kernel.org/all/ca331aa3-6304-4e07-9ed9-94dc69726382@intel.com/

> 
> > @@ -2217,8 +2217,8 @@ u64 tdh_vp_init(struct tdx_vp *vp, u64 initial_rcx, u32 x2apicid)

mm.. I think I should just delete the comment.

---

## [93] Peter Fang — 2026-06-14
*Subject: Re: [PATCH 04/15] x86/virt/tdx: Enable the Extensions right after
 basic TDX Module init*

On Mon, Jun 08, 2026 at 06:12:35PM +0800, Xu Yilun wrote:
> 
> > 

The DICE extension is just one of the ways to generate a Quote for the
guest. If DICE is not available, TDX can fall back to the existing
userspace SGX Quoting flow. So I think a best-effort approach makes
sense here.

> >

---

## [94] Peter Fang — 2026-06-14
*Subject: Re: [RFC PATCH 05/15] x86/virt/tdx: Move tdx_tdr_pa() up in the file*

On Thu, Jun 11, 2026 at 07:21:17PM +0300, Adrian Hunter wrote:
> On 22/05/2026 06:41, Xu Yilun wrote:
> > From: Peter Fang <peter.fang@intel.com>

Ack. Thanks for catching this.

>

---

## [95] Peter Fang — 2026-06-14
*Subject: Re: [RFC PATCH 06/15] x86/virt/tdx: Initialize Quoting extension
 during bringup*

On Thu, May 28, 2026 at 02:35:49PM -0700, Edgecombe, Rick P wrote:
> On Fri, 2026-05-22 at 11:41 +0800, Xu Yilun wrote:
> > From: Peter Fang <peter.fang@intel.com>

Thanks, will fix in the next revision.

> 
> >  does not include the opt-in portion of the initialization.

Will fix this as well.

> 
> >

---

## [96] Peter Fang — 2026-06-14
*Subject: Re: [RFC PATCH 06/15] x86/virt/tdx: Initialize Quoting extension
 during bringup*

On Thu, Jun 11, 2026 at 07:22:18PM +0300, Adrian Hunter wrote:
> On 22/05/2026 06:41, Xu Yilun wrote:
> > From: Peter Fang <peter.fang@intel.com>

The Quoting extension is not the only way to get TD Quotes. If this
extension fails, the host can still fall back to the legacy SGX-based
Quoting in userspace. I think the decision to actually fall back can be
left to userspace at that point.

> 
> > +static void tdx_quote_init(void)

Good catch. I'll fix this. Thanks!

>

---

## [97] Peter Fang — 2026-06-14
*Subject: Re: [RFC PATCH 06/15] x86/virt/tdx: Initialize Quoting extension
 during bringup*

On Fri, Jun 12, 2026 at 05:00:11PM -0700, Dan Williams (nvidia) wrote:
> Xu Yilun wrote:
> > From: Peter Fang <peter.fang@intel.com>

Since there is a fallback option to do the Quoting in userspace, I think
it is probably not worth shooting down TDX entirely over quote-init
failures.

The quote-init failures can come from:

  1. Quoting init SEAMCALL failures, which look pretty opaque to the
     kernel and there's not much it can do about it.
  2. Quoting buffer allocation failures, which *are* understood by the
     kernel, and it could maybe try something else. Right now, we just
     treat it the same as 1.

This is helpful because I think the question of "what if the Quoting
extension fails" has come up enough times that it warrants some
explanation in the patch log. Thanks.

> 
> > This patch does not include the opt-in portion of the initialization.

Good question... I should reorder the patches so this looks more
straightforward. I enable everything in patch 15 (including the check
for the Quoting feature) and I think that just creates confusion for
folks looking at this patch.

>

---

## [98] Peter Fang — 2026-06-14
*Subject: Re: [RFC PATCH 07/15] x86/virt/tdx: Prepare Quote buffer during
 extension bringup*

On Thu, May 28, 2026 at 03:30:36PM -0700, Edgecombe, Rick P wrote:
> On Fri, 2026-05-22 at 11:41 +0800, Xu Yilun wrote:
> > From: Peter Fang <peter.fang@intel.com>

I'll add more background in common terms here.

> 
> >  Because the Quote buffer is shared with TDX guests,

This is again the balance between using common terms vs TDX language. In
general, TDX docs capitalize terms a lot. TDX attestation docs always
refer to the attestation blob as "Quotes".

I mainly went with "Quotes" in the logs because that term has already
been used everywhere in the tdx-guest code/logs (see tdx-guest.c). So I
wanted to preserve some consistency at least in the logs. In the added
host code and prints, I'm starting to just use "quotes" because that
seems to be the more common convention in the TDX host code. I'm happy
to make adjustments if this doesn't make sense.

> 
> > prepare the required metadata during Quoting extension bringup.

That's a poor choice of word on my part. I'll rephrase it in the next
revision. I mainly just wanted to convey "prepare struct quote_data".

> 
> How does it being shared with TDX guest suggest this? Just that TDX guests will

Yes, that's exactly it. I'll make it clearer.

> 
> > +static struct quote_data {

Sure, I'll fix this.

> 
> > +	qlist = vmalloc_array(qlist_npages, PAGE_SIZE);

Will do.

> 
> > +	}

I'll add more explanation here (see below).

> 
> > +	 * Only the last page needs to be filled. All the other pages will be

Yeah I was trying to create all-1 u64 entries. This is pretty
under-commented. I'll redo the comments.

> 
> > +	/* Populate HPA_LINKED_LIST as per TDX ABI spec */

Will do. This part is pretty under-commented as well.

> 
> > +	qdata->buf = qbuf;

That's a really good idea. I'll do that.

> 
> > +	qdata->hpa_list_pa = PFN_PHYS(pfn);

Good point. I think I had some other errors that I later removed. I'll
just return -ENOMEM directly here.

> 
> > +}

Previously, get_tdx_sys_info_quote() just happened to be the last
statement in tdx_quote_init() so getting an error didn't require an
early return. tdx_quote_init() wasn't doing much at the time. But now
the code can't see a valid max_quote_size if get_tdx_sys_info_quote()
fails.

> 
> > +

Yes. struct quote_data remains uninitialized so it will have NULL
pointers. All the added APIs will take this into account so there won't
be NULL pointer accesses.

> 
> >  }

---

## [99] Peter Fang — 2026-06-14
*Subject: Re: [RFC PATCH 09/15] x86/virt/tdx: Add interface to generate a Quote*

On Thu, May 28, 2026 at 03:30:45PM -0700, Edgecombe, Rick P wrote:
> > +
> > +	/* TDH.QUOTE.GET expects the input data to fit in a page */

There is a similar check for this in_data_len on the KVM side in patch
12, but it is for a different reason. The check in KVM is to make sure
it maps valid guest memory pages into the kernel, while here we make
sure it complies with the SEAMCALL API. That said, the KVM check does
make the check here kinda redundant... I can remove this for simplicity.

> 
> > +

"r" is a SEAMCALL error just like any other SEAMCALL. If r == 0
(SUCCESS), there is no documented scenario for when "!out_len" or
"out_len > quote_data.buf_len" would occur. I would assume these would
be TDX module bugs.

The reason I check the last 2 conditions is mainly to protect the
kernel:

  - "!out_len" will cause kvmemdup() to return ZERO_SIZE_PTR
  - "out_len > quote_data.buf_len" will cause out-of-bounds memory
    access in kvmemdup()

> 
> > +		goto out;

Hm interesting idea. But a Quote buffer could be close to 4MB in the worst
case. Let's say max_quote_size is 3MB, that's 768 vmalloc_to_pfn() calls
each time... That sounds a bit excessive right?

The extra bits mainly come from using kvmemdup() I think. Having to use
kvfree() on it does feel a bit annoying but that was the tradeoff I
made...

>

---

## [100] Peter Fang — 2026-06-14
*Subject: Re: [RFC PATCH 09/15] x86/virt/tdx: Add interface to generate a Quote*

On Thu, Jun 11, 2026 at 08:15:50PM +0300, Adrian Hunter wrote:
> On 22/05/2026 06:41, Xu Yilun wrote:
> > From: Peter Fang <peter.fang@intel.com>

Ah yes, I should document that. I'll put that in the patch log.

> 
> > +static u64 tdx_quote_get(struct tdx_td *td, u64 in_data_pa, u64 in_data_len,

Will do. It's because we use whatever the default Quote ID is.

> 
> ...

Yep I can fix that. Thanks.

>

---

## [101] Peter Fang — 2026-06-14
*Subject: Re: [RFC PATCH 10/15] x86/tdx: Move and rename Quote request
 structure*

On Thu, Jun 11, 2026 at 08:16:37PM +0300, Adrian Hunter wrote:
> > -static int wait_for_quote_completion(struct tdx_quote_buf *quote_buf, u32 timeout)
> > +static int wait_for_quote_completion(struct tdx_quote_req *quote_buf, u32 timeout)

Good catch, I'll fix that.

> 
> >  {

Thanks for catching that. This needs to be fixed. We can submit a
separate guest-only patch.

>

---

## [102] Peter Fang — 2026-06-14
*Subject: Re: [RFC PATCH 10/15] x86/tdx: Move and rename Quote request
 structure*

On Fri, Jun 12, 2026 at 05:04:05PM -0700, Dan Williams (nvidia) wrote:
> >  }
> >  #endif /* CONFIG_INTEL_TDX_GUEST && CONFIG_KVM_GUEST */

Will do, thanks for the review Dan!

---

## [103] Peter Fang — 2026-06-14
*Subject: Re: [RFC PATCH 12/15] KVM: TDX: Add in-kernel Quote generation*

On Fri, Jun 12, 2026 at 05:20:31PM -0700, Dan Williams (nvidia) wrote:
> [..]
> > +static u64 __get_quote_kernel(struct kvm_vcpu *vcpu, struct tdx_quote_req *req,

Ah makes sense. I'll fix it up.

> 
> > +	void *quote_data __free(kvfree) =

Good point... I'll fix the naming. Thanks.

---

## [104] Peter Fang — 2026-06-14
*Subject: Re: [RFC PATCH 13/15] KVM: TDX: Support event-notify interrupts only
 with userspace quoting*

On Thu, Jun 11, 2026 at 10:36:52PM +0300, Adrian Hunter wrote:
> On 22/05/2026 06:41, Xu Yilun wrote:
> > From: Peter Fang <peter.fang@intel.com>

Hm that's an interesting point. But isn't the whole point of
SetupEventNotifyInterrupt to set up a contract with the host VMM? The
GHCI spec is quite loose about this.

If we say "the host VMM is not required to honor this contract", then
maybe this doesn't truly break anything. But then this stance kind of
makes this whole feature moot, or at least not very useful?

Not adding this patch feels like making this problem worse, right?
Because now we will have platforms that won't ever fire these
interrupts, and the host still tells the guest SetupEventNotifyInterrupt
is supported.

> 
> > 

Just to maintain status quo basically. Seems like previously there was
some interest in adding this support to the guest at some point. This
patch simply turns off this feature when quoting is not done in
userspace. But platforms that do quoting in userspace (e.g. don't
support DICE extension) can observe the same behavior as today, if/when
such a guest comes into existence.

> 
> > 

Can you please point me to it? I couldn't find that section in that
file.

> 
> > +                  KVM only supports version 1 of the GetQuote request.

Documenting this came up during some internal discussions. But yeah it
looks a bit out of place. I can remove it.

> 
> >  

I think this is related to the discussion above about how hard host VMM
should try to honor the SetupEventNotifyInterrupt contract.

>

---

## [105] Adrian Hunter — 2026-06-15
*Subject: Re: [RFC PATCH 13/15] KVM: TDX: Support event-notify interrupts only
 with userspace quoting*

>>> @@ -7335,6 +7335,9 @@ inputs and outputs of the TDVMCALL.  Currently the following values of
>>>     queued successfully, the TDX guest can poll the status field in the

Sorry, got he file name wrong: Documentation/arch/x86/tdx.rst

---

## [106] Xu Yilun — 2026-06-15
*Subject: Re: [PATCH 00/15] Enable TDX Module Extensions and DICE-based TDX
 Quoting*

> The internal implementation details of extension seamcalls buries the
> lead on why this mechanism is important, why Linux should care, and why

I may not include the ARM/AMD examples, not sure I can explain them
well.

> mechanism is "give the service environment some memory", "invoke the
> service API", and "continue invoking until complete". All protocol state

[...]

> > The Extensions consumes relatively large amount of memory (~50MB). So it
> > is designed to be off by default.

[...]

> 
> > == Some history ==

Good to me, will include most of them, thanks.

---

## [107] Xu Yilun — 2026-06-15
*Subject: Re: [PATCH 01/15] x86/virt/tdx: Read global metadata for TDX Module
 Extensions*

> > Check TDX_FEATURES0 before reading these metadata. If a feature is
> > advertised, a failure in reading associated metadata causes the entire

Agree.

---

## [108] Xu Yilun — 2026-06-15
*Subject: Re: [PATCH 02/15] x86/virt/tdx: Add extra memory to TDX Module for
 Extensions*

On Fri, Jun 12, 2026 at 04:49:36PM -0700, Dan Williams (nvidia) wrote:
> Xu Yilun wrote:
> > TDX Module introduces a new concept called "TDX Module Extensions" to

Yes, I'll drop long running, keep preemptible and resumable.

> 
> > Currently, TDX Module memory use is relatively static. But, the

Good to me.

> > For now, TDX Module Extensions consumes relatively large amount of
> > memory (~50MB). Use contiguous page allocation to avoid permanently

Agree. I'll change it as:

For now, TDX module extensions consume tens of megabytes memory that
will never be returned to host. Use contiguous page allocation to
isolate these large blocks entirely, avoiding permanent memory
fragmentation and reducing buddy allocator efficiency. Print ...


> > +	u64 *root;

...

> > +	root = kzalloc(PAGE_SIZE, GFP_KERNEL);
> > +	if (!root)

Agree. I really don't have to introduce a new "root" page term. The SPEC
says "The HPA_LIST is a 4KB page which contains a list of HPAs", so
hpa_list page is a good name.

> case where it might sometimes be this odd "singleton" object? You could
> just make it this for actual type safety.

OK, let me try.

> > +		ret = tdx_ext_mem_add(virt_to_page(root), nents);
> > +		/*

Yes no need the 'once'.

Since I'll print all memory for the extensions anyway below. I'll use:

	WARN(ret, "Fatal: TDX Module rejected (%d) memory for extensions, stranded all pages\n",
	     ret);

Thanks,
Yilun

---

## [109] Dave Hansen — 2026-06-15
*Subject: Re: [PATCH 00/15] Enable TDX Module Extensions and DICE-based TDX
 Quoting*

On 6/15/26 08:22, Xu Yilun wrote:
>> The TDX "Extension SEAMCALL" capability is akin to ARM CCA's "Stateful
>> RMI Operations (SRO)", and achieves similar externalized complexity

I actually think they're pretty important proof points. One of the big
challenges as a maintainer evaluating these things is judging the
solution itself.

Is this architecture a good one? Is it overly complex? Are the avenues
for simplification?

If five vendors pop up all with similar problems and solutions, then
it's a pretty good bet that they're all on the right track. But, if
there are four going one direction and one going off by itself, it's a
sign that the errant one might need a course correction.

It would honestly be worth your time to go *talk* to the AMD and ARM
folks and ensure that you are all on the same page. Last I checked, they
seemed to be at least halfway reasonable human beings and don't bite.
Let me know if I can help with some introductions.

---

## [110] Xu Yilun — 2026-06-15
*Subject: Re: [PATCH 04/15] x86/virt/tdx: Enable the Extensions right after
 basic TDX Module init*

On Fri, Jun 12, 2026 at 05:08:48PM -0700, Dan Williams (nvidia) wrote:
> Xu Yilun wrote:
> > The detailed initialization flow for TDX Module Extensions has been

Agree. Will remove the section which is copied from cover letter.

> 
> Otherwise I agree with the proposed reordering of this initial series.

Thanks for the review!

---

## [111] Dave Hansen — 2026-06-15
*Subject: Re: [PATCH 01/15] x86/virt/tdx: Read global metadata for TDX Module
 Extensions*

On 6/12/26 15:20, Dan Williams (nvidia) wrote:
>> Check TDX_FEATURES0 before reading these metadata. If a feature is
>> advertised, a failure in reading associated metadata causes the entire

One other note on this: the current Linux policy of "any available
extension, all the time" is the simplest possible functional policy. If
Linux has one policy, I think that's the one it should have.

That said, I'm open to the idea that users might desire other policies.
We should absolutely explore them another day in another series.

---

## [112] Peter Fang — 2026-06-15
*Subject: Re: [RFC PATCH 13/15] KVM: TDX: Support event-notify interrupts only
 with userspace quoting*

On Mon, Jun 15, 2026 at 07:39:01AM +0300, Adrian Hunter wrote:
> >>> @@ -7335,6 +7335,9 @@ inputs and outputs of the TDVMCALL.  Currently the following values of
> >>>     queued successfully, the TDX guest can poll the status field in the

Thanks a lot for the pointers! It definitely needs to be updated.

>

---

## [113] Xu Yilun — 2026-06-16
*Subject: Re: [PATCH 00/15] Enable TDX Module Extensions and DICE-based TDX
 Quoting*

On Mon, Jun 15, 2026 at 08:57:09AM -0700, Dave Hansen wrote:
> On 6/15/26 08:22, Xu Yilun wrote:
> >> The TDX "Extension SEAMCALL" capability is akin to ARM CCA's "Stateful

OK, I can include this section that Dan provides.

> challenges as a maintainer evaluating these things is judging the
> solution itself.

Yes, I queried ARM/AMD TDISP folks offline and CCed them in this thread.
Correct me if anything wrong:

AFAIK, AMD firmware run on an external physical core (PSP), firmware call
execution won't occupy host CPU, and the two partners communicate
asynchronously, so no worry about interruptibility and preemptibility.

From Alexey:

  "The AMD CPU puts a request in a queue, writes to doorbell, and wait for
   an interrupt. The PSP (a separate physical core) will see this, handle,
   put the data in the CPU memory (if needed), trigger the interrupt. Done.
   The host CPU can be rescheduled while waiting"


ARM SRO is something I don't familiar with. ARM has no co-processor for
CC, host invokes RMI and trap into RMM for secure execution, stateless
RMI blocks interrupt so should be short lived. This is very similar to
Intel SEAMCALL.

Stateful RMI, however, from their RMM 2.0bet1 SPEC [1] B4.3.2 Stateful
RMI operations, could be used "When an RMI operation cannot be completed
within an IMPLEMENTATION DEFINED time limit". It is "guaranteed to yield
within an IMPLEMENTATION DEFINED time limit from the point at which an
interrupt becomes pending." I see it tries to solve the same problem as
extension SEAMCALLs.

I see SRO is WIP in [2], and is used for TDISP [3].

[1] https://developer.arm.com/documentation/den0137/2-0bet1/
[2] https://lore.kernel.org/all/20260318155413.793430-49-steven.price@arm.com/
[3] https://lore.kernel.org/all/20260427065121.916615-3-aneesh.kumar@kernel.org/

---
