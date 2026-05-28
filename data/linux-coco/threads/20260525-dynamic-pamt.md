---
title: 'Dynamic PAMT'
date: 2026-05-25
last_reply: 2026-05-26
message_count: 14
participants: ['Rick Edgecombe', 'Chao Gao']
---

## [1] Rick Edgecombe — 2026-05-25

Hi,

This is next revision of Dynamic PAMT TDX series, which I’m calling v6 in 
order to differentiate it from Sean’s giant MMU refactor/DPAMT/Huge-page 
series which he called v5 [0]. But things are not quite linear, because 
that v5 didn’t include the feedback from v4 [1].

So this version is the conflict resolution of:
 1. Comments on Dynamic PAMT v4
 2. Sean changes in Dynamic PAMT v4 -> Sean Mega v5
 3. Feedback to Sean’s v5

For Dynamic PAMT background, please refer to [2].

This series is pretty mature at this point, however with 2 pre-req series 
still on the list (more on that below under "Base"), I can't ask for it to 
be merged at this point. So I'm hoping to collect some Acks and RB's in 
the meantime and then it can have a smooth path once those other series 
land. Please especially consider any reviewabiliy concerns on the tip side 
that can be ironed out in the meantime.

Changes
=======

Sean’s mega v5
--------------
This had a bunch of MMU refactor work, which did:
 a. TDX MMU refactor that generally pushed more TDX knowledge into TDX.c
    out of the core MMU. This covered the needs of both DPAMT and huge
    pages.
 b. Redid the solution for installing DPAMT backing for the pages the MMU
    uses for the S-EPT operations.
 c. Some huge page changes that I’ll skip here.

(a) has been split into another series [3]. After long discussions on v5, 
the changes for (b) were rolled back to the original solution in v4. 
Sean’s v5 included him trying to do Kai’s idea and running into trouble, 
then a second new idea which also was found to have issues on review of 
v5. By my count we have had at least 4 or 5 ideas by smart people that led 
us back to the same solution of keeping a cache of pages and adjusting the 
DPAMT right before give the page to the TDX module. I, again, think that 
we should either accept the current solution or get started on going back 
to change the arch in order to make it more workable for this problem.

Dropping Non-Required Changes
-----------------------------
In the interest of finally clearing these patches, I dropped everything I 
could out of the series.

The most significant thing dropped was the optimization around the 
refcount allocation. It is a good thing to drop because it is not required 
to make Dynamic PAMT useful as a memory optimization. And there is room 
for debate on how far to optimize the last little bit of memory usage. 

To recap, the kernel implementation keeps a kernel side refcount for each 
2MB of the physical memory. The non-optimized version just uses a single 
vmalloc to cover the range from 0 to max_pfn. In the worst case this is 
8GB of memory. The optimization tried to not allocate refcounts for the 
sparse ranges that didn't have any RAM.

For a simple small server with mostly physical contiguous RAM and no CXL
complications, the basic implementation should be close to optimal anyway.
And for big servers, an 8GB allocation is going to have less impact. In
the end Dynamic PAMT *is* an optimization that we will force on as a
good default option. Even with all the optimizations we could throw at it,
if the system is 100% TDs, Dynamic PAMT could come out slightly behind. So
judgment on good defaults is needed regardless.

Consider a couple simple examples of TDX enabled, but no TDs, and the 
non-optimized refcount solution:
Machine                    PAMT (GB)   DPAMT (GB)   Savings/(Loss)
256GB (max_pfn at 256GB)   1.02        0.01         100x
256GB (max_pfn at maxpa)   1.02        8.01         (8x)
2TB   (max_pfn at 2TB)     8.19        0.08         99x
2TB   (max_pfn at maxpa)   8.19        8.08         1x

The weird server loses a little bit, but not nearly as much as the normal 
ones gain. Still enough benefit in general to make Dynamic PAMT a 
worthwhile default setting. So let's start with the simplest solution, 
which is an improvement in most cases. And then separate out the refcount 
optimization discussion for later.

Besides that, I dropped the error cleanups. As I was implementing the last 
discussion, I found it a bit awkward in some places. Also I noticed that 
Dave did not fully agree to that proposal either. So it's a continual 
source of style controversy and we can separate it out from the Dynamic 
PAMT work.

I did not drop the optimization that uses the refcounts to avoid taking 
the global lock in tdx_pamt_get/put() because I considered it critical for 
making Dynamic PAMT default on. It is more about avoid regressing KVM EPT 
violation contention, and not about squeezing out more memory savings from 
Dynamic PAMT.

Regarding whether we could strip more out of the series if we made this a
boot time kernel parameter. I think it's possible to drop "x86/virt/tdx:
Allocate reference counters for PAMT memory" and "x86/virt/tdx: Allocate
reference counters for PAMT memory" and still have something that is
functional. I didn't go that route for this revision because making the
feature optional seemed like too much of a divergence from past discussion.
But it is an option if this series seems like too much to digest at once.

AI use in this revision
=======================
While AI enhanced development is still relatively new to the kernel world,
I wanted to share a bit about how this series was generated. For both
consideration in reviewing, and also maybe people might find it
interesting. This was my first time using AI for serious kernel work, so
it was kind of a micromanaged evaluation type use. I used an opus model
with a dump of the many mail threads and a description of how they were
related. Since the previous discussion was pretty disordered, I had it try
to catch any feedback that was missed or conflicted for each patch. And it
caught a few that I had missed. I also used it to turn some of the
feedback into code changes, and to heavily scrutinize the concurrency
logic in tdx_pamt_get/put(). I used it to suggest some log changes too,
but had to edit most of those pretty heavily. Lastly, I used the Chris
Meson and Sashiko review prompts to review the series, which generated a
few changes. All this experimentation generated quite a few Assisted-by
tags, which now feels kinda excessive...

Base
====
This is based on v2 of the MMU refactor series Yan posted a few weeks ago 
[3], which is itself based on the struct page to pfn conversion series[4]. 
A full stack branch can be found here: [5].

Testing
=======
This series was tested in the usual suite, but also with the optimization
patch removed.

[0] https://lore.kernel.org/kvm/20260129011517.3545883-1-seanjc@google.com/
[1] https://lore.kernel.org/kvm/20251121005125.417831-1-rick.p.edgecombe@intel.com/
[2] https://lore.kernel.org/kvm/20250918232224.2202592-1-rick.p.edgecombe@intel.com/
[3] https://lore.kernel.org/kvm/20260509075201.4077-1-yan.y.zhao@intel.com/
[4] https://lore.kernel.org/kvm/20260430014852.24183-1-yan.y.zhao@intel.com/
[5] https://github.com/intel-staging/tdx/tree/dpamt_v6

Kiryl Shutsemau (9):
  x86/virt/tdx: Allocate page bitmap for Dynamic PAMT
  x86/virt/tdx: Add tdx_alloc/free_control_page() helpers
  x86/virt/tdx: Allocate ref counts for Dynamic PAMT memory
  x86/virt/tdx: Handle concurrent callers in tdx_pamt_get/put()
  x86/virt/tdx: Optimize tdx_pamt_get/put()
  KVM: TDX: Allocate PAMT memory for TD and vCPU control structures
  KVM: TDX: Get/put PAMT pages when (un)mapping private memory
  x86/virt/tdx: Enable Dynamic PAMT
  Documentation/x86: Add documentation for TDX's Dynamic PAMT

Rick Edgecombe (2):
  x86/virt/tdx: Simplify tdmr_get_pamt_sz()
  x86/tdx: Add APIs to support Dynamic PAMT ops from KVM's fault path

 Documentation/arch/x86/tdx.rst              |  22 +
 arch/x86/include/asm/kvm-x86-ops.h          |   1 +
 arch/x86/include/asm/kvm_host.h             |   2 +
 arch/x86/include/asm/tdx.h                  |  38 ++
 arch/x86/include/asm/tdx_global_metadata.h  |   3 +
 arch/x86/kvm/mmu/mmu.c                      |   4 +
 arch/x86/kvm/vmx/tdx.c                      | 100 +++--
 arch/x86/kvm/vmx/tdx.h                      |   2 +
 arch/x86/virt/vmx/tdx/tdx.c                 | 445 +++++++++++++++++---
 arch/x86/virt/vmx/tdx/tdx.h                 |   5 +-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c |  21 +-
 11 files changed, 544 insertions(+), 99 deletions(-)

---

## [2] Rick Edgecombe — 2026-05-25
*Subject: [PATCH v6 01/11] x86/virt/tdx: Simplify tdmr_get_pamt_sz()*

For each memory region that the TDX module might use (called TDMR), three
separate traditional PAMT allocations are needed. One for each supported
page size (1GB, 2MB, 4KB). These store information on each page in the
TDMR. In Linux, they are allocated out of one physically contiguous block,
in order to more efficiently use some internal TDX module book keeping
resources. So some simple math is needed to break the single large
allocation into three smaller allocations for each page size.

There are some commonalities in the math needed to calculate the base and
size for each smaller allocation, and so an effort was made to share logic
across the three. Unfortunately doing this turned out unnaturally tortured,
with a loop iterating over the three page sizes, only to call into a
function with cases statement for each page size. In the future Dynamic
PAMT will add more logic that is special to the 4KB page size, making the
benefit of the math sharing even more questionable.

Three is not a very high number, so get rid of the loop and just duplicate
the small calculation three times. In doing so, setup for future Dynamic
PAMT changes.

Since the loop that iterates over it is gone, further simplify the code by
dropping the array of intermediate size and base storage. Just store the
values to their final locations. Accept the small complication of having
to clear tdmr->pamt_4k_base in the error path, so that tdmr_do_pamt_func()
will not try to operate on the TDMR struct when attempting to free it.

Assisted-by: GitHub Copilot:claude-opus-4-6 Claude:claude-opus-4-7
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v6:
 - Drop {} by moving a comment (Binbin)
 - Log tweaks

v4:
 - Just refer to global var instead of passing pamt_entry_size around
   (Xiaoyao)
 - Remove setting pamt_4k_base to zero, because it already is zero.
   Adjust the comment appropriately (Kai)

v3:
 - New patch
---
 arch/x86/virt/vmx/tdx/tdx.c | 93 ++++++++++++-------------------------
 1 file changed, 29 insertions(+), 64 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 967482ae3c801..487f389f52f4b 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -516,31 +516,21 @@ static __init int fill_out_tdmrs(struct list_head *tmb_list,
  * Calculate PAMT size given a TDMR and a page size.  The returned
  * PAMT size is always aligned up to 4K page boundary.
  */
-static __init unsigned long tdmr_get_pamt_sz(struct tdmr_info *tdmr, int pgsz,
-					     u16 pamt_entry_size)
+static __init unsigned long tdmr_get_pamt_sz(struct tdmr_info *tdmr, int pgsz)
 {
 	unsigned long pamt_sz, nr_pamt_entries;
+	const int tdx_pg_size_shift[] = { PAGE_SHIFT, PMD_SHIFT, PUD_SHIFT };
+	const u16 pamt_entry_size[TDX_PS_NR] = {
+		tdx_sysinfo.tdmr.pamt_4k_entry_size,
+		tdx_sysinfo.tdmr.pamt_2m_entry_size,
+		tdx_sysinfo.tdmr.pamt_1g_entry_size,
+	};
 
-	switch (pgsz) {
-	case TDX_PS_4K:
-		nr_pamt_entries = tdmr->size >> PAGE_SHIFT;
-		break;
-	case TDX_PS_2M:
-		nr_pamt_entries = tdmr->size >> PMD_SHIFT;
-		break;
-	case TDX_PS_1G:
-		nr_pamt_entries = tdmr->size >> PUD_SHIFT;
-		break;
-	default:
-		WARN_ON_ONCE(1);
-		return 0;
-	}
+	nr_pamt_entries = tdmr->size >> tdx_pg_size_shift[pgsz];
+	pamt_sz = nr_pamt_entries * pamt_entry_size[pgsz];
 
-	pamt_sz = nr_pamt_entries * pamt_entry_size;
 	/* TDX requires PAMT size must be 4K aligned */
-	pamt_sz = ALIGN(pamt_sz, PAGE_SIZE);
-
-	return pamt_sz;
+	return PAGE_ALIGN(pamt_sz);
 }
 
 /*
@@ -578,28 +568,21 @@ static __init int tdmr_get_nid(struct tdmr_info *tdmr, struct list_head *tmb_lis
  * within @tdmr, and set up PAMTs for @tdmr.
  */
 static __init int tdmr_set_up_pamt(struct tdmr_info *tdmr,
-				   struct list_head *tmb_list,
-				   u16 pamt_entry_size[])
+				   struct list_head *tmb_list)
 {
-	unsigned long pamt_base[TDX_PS_NR];
-	unsigned long pamt_size[TDX_PS_NR];
-	unsigned long tdmr_pamt_base;
 	unsigned long tdmr_pamt_size;
 	struct page *pamt;
-	int pgsz, nid;
-
+	int nid;
 	nid = tdmr_get_nid(tdmr, tmb_list);
 
 	/*
 	 * Calculate the PAMT size for each TDX supported page size
 	 * and the total PAMT size.
 	 */
-	tdmr_pamt_size = 0;
-	for (pgsz = TDX_PS_4K; pgsz < TDX_PS_NR; pgsz++) {
-		pamt_size[pgsz] = tdmr_get_pamt_sz(tdmr, pgsz,
-					pamt_entry_size[pgsz]);
-		tdmr_pamt_size += pamt_size[pgsz];
-	}
+	tdmr->pamt_4k_size = tdmr_get_pamt_sz(tdmr, TDX_PS_4K);
+	tdmr->pamt_2m_size = tdmr_get_pamt_sz(tdmr, TDX_PS_2M);
+	tdmr->pamt_1g_size = tdmr_get_pamt_sz(tdmr, TDX_PS_1G);
+	tdmr_pamt_size = tdmr->pamt_4k_size + tdmr->pamt_2m_size + tdmr->pamt_1g_size;
 
 	/*
 	 * Allocate one chunk of physically contiguous memory for all
@@ -607,26 +590,18 @@ static __init int tdmr_set_up_pamt(struct tdmr_info *tdmr,
 	 * in overlapped TDMRs.
 	 */
 	pamt = alloc_contig_pages(tdmr_pamt_size >> PAGE_SHIFT, GFP_KERNEL,
-			nid, &node_online_map);
+				  nid, &node_online_map);
+
+	/*
+	 * tdmr->pamt_4k_base is still zero so the error
+	 * path of the caller will skip freeing the pamt.
+	 */
 	if (!pamt)
 		return -ENOMEM;
 
-	/*
-	 * Break the contiguous allocation back up into the
-	 * individual PAMTs for each page size.
-	 */
-	tdmr_pamt_base = page_to_pfn(pamt) << PAGE_SHIFT;
-	for (pgsz = TDX_PS_4K; pgsz < TDX_PS_NR; pgsz++) {
-		pamt_base[pgsz] = tdmr_pamt_base;
-		tdmr_pamt_base += pamt_size[pgsz];
-	}
-
-	tdmr->pamt_4k_base = pamt_base[TDX_PS_4K];
-	tdmr->pamt_4k_size = pamt_size[TDX_PS_4K];
-	tdmr->pamt_2m_base = pamt_base[TDX_PS_2M];
-	tdmr->pamt_2m_size = pamt_size[TDX_PS_2M];
-	tdmr->pamt_1g_base = pamt_base[TDX_PS_1G];
-	tdmr->pamt_1g_size = pamt_size[TDX_PS_1G];
+	tdmr->pamt_4k_base = page_to_phys(pamt);
+	tdmr->pamt_2m_base = tdmr->pamt_4k_base + tdmr->pamt_4k_size;
+	tdmr->pamt_1g_base = tdmr->pamt_2m_base + tdmr->pamt_2m_size;
 
 	return 0;
 }
@@ -657,10 +632,7 @@ static __init void tdmr_do_pamt_func(struct tdmr_info *tdmr,
 	tdmr_get_pamt(tdmr, &pamt_base, &pamt_size);
 
 	/* Do nothing if PAMT hasn't been allocated for this TDMR */
-	if (!pamt_size)
-		return;
-
-	if (WARN_ON_ONCE(!pamt_base))
+	if (!pamt_base)
 		return;
 
 	pamt_func(pamt_base, pamt_size);
@@ -686,14 +658,12 @@ static __init void tdmrs_free_pamt_all(struct tdmr_info_list *tdmr_list)
 
 /* Allocate and set up PAMTs for all TDMRs */
 static __init int tdmrs_set_up_pamt_all(struct tdmr_info_list *tdmr_list,
-					struct list_head *tmb_list,
-					u16 pamt_entry_size[])
+				 struct list_head *tmb_list)
 {
 	int i, ret = 0;
 
 	for (i = 0; i < tdmr_list->nr_consumed_tdmrs; i++) {
-		ret = tdmr_set_up_pamt(tdmr_entry(tdmr_list, i), tmb_list,
-				pamt_entry_size);
+		ret = tdmr_set_up_pamt(tdmr_entry(tdmr_list, i), tmb_list);
 		if (ret)
 			goto err;
 	}
@@ -970,18 +940,13 @@ static __init int construct_tdmrs(struct list_head *tmb_list,
 				  struct tdmr_info_list *tdmr_list,
 				  struct tdx_sys_info_tdmr *sysinfo_tdmr)
 {
-	u16 pamt_entry_size[TDX_PS_NR] = {
-		sysinfo_tdmr->pamt_4k_entry_size,
-		sysinfo_tdmr->pamt_2m_entry_size,
-		sysinfo_tdmr->pamt_1g_entry_size,
-	};
 	int ret;
 
 	ret = fill_out_tdmrs(tmb_list, tdmr_list);
 	if (ret)
 		return ret;
 
-	ret = tdmrs_set_up_pamt_all(tdmr_list, tmb_list, pamt_entry_size);
+	ret = tdmrs_set_up_pamt_all(tdmr_list, tmb_list);
 	if (ret)
 		return ret;

---

## [3] Rick Edgecombe — 2026-05-25
*Subject: [PATCH v6 02/11] x86/virt/tdx: Allocate page bitmap for Dynamic PAMT*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

The TDX Physical Address Metadata Table (PAMT) holds data about the
physical memory used by TDX, and must be allocated by the kernel during
TDX module initialization.

The exact size of the required PAMT memory is determined by the TDX module
and may vary between TDX module versions. Currently it is approximately
0.4% of the system memory. This is a significant commitment, especially if
it is not known upfront whether the machine will run any TDX guests.

Each memory region that the TDX module might use needs three separate PAMT
allocations. One for each supported page size (1GB, 2MB, 4KB). The
TDX module supports a new feature designed to reduce PAMT overhead called
Dynamic PAMT. At a high level, Dynamic PAMT still has the 1GB and 2MB
levels allocated on TDX module initialization, but the 4KB level is
allocated dynamically during runtime.

However, in the details, Dynamic PAMT still needs some smaller per 4KB
page scoped data (currently it is 1 bit per page). The TDX module exposes
the number of bits as a separate piece of metadata than the 4KB static
allocation for regular PAMT. Although the size is enumerated differently,
it is handed to the TDX module in the same way the 4KB page size PAMT
allocation is for regular, non-dynamic PAMT.

Begin to implement Dynamic PAMT in the kernel by reading the bits-per-page
needed for Dynamic PAMT. Calculate the size needed for the bitmap,
and use it instead of the 4KB size determined for normal PAMT, in the case
of Dynamic PAMT.

Unlike the existing metadata reading code, this code is not generated by a
script. So adjust the comment to be more generic. Also, start to adopt a
more normal kernel code style without the tenary statements and if
conditionals assignments that the auto generated code has.

Assisted-by: Sashiko:claude-opus-4-6
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Co-developed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v6:
 - Improve comment (Binbin)
 - Log tweaks
 - Mark tdmr_get_pamt_bitmap_sz() __init in response to upstream
   changes
 - Switch to more normal kernel code style, even though it differs from
   the existing auto generated code.
---
 arch/x86/include/asm/tdx.h                  |  5 +++++
 arch/x86/include/asm/tdx_global_metadata.h  |  3 +++
 arch/x86/virt/vmx/tdx/tdx.c                 | 19 ++++++++++++++++++-
 arch/x86/virt/vmx/tdx/tdx_global_metadata.c | 21 ++++++++++++++++++++-
 4 files changed, 46 insertions(+), 2 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 503f9a3f46d61..82dc27aecf297 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -149,6 +149,11 @@ static __always_inline u64 sc_retry(sc_func_t func, u64 fn,
 const char *tdx_dump_mce_info(struct mce *m);
 const struct tdx_sys_info *tdx_get_sysinfo(void);
 
+static inline bool tdx_supports_dynamic_pamt(const struct tdx_sys_info *sysinfo)
+{
+	return false; /* To be enabled when kernel is ready */
+}
+
 int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
diff --git a/arch/x86/include/asm/tdx_global_metadata.h b/arch/x86/include/asm/tdx_global_metadata.h
index 40689c8dc67eb..88040ddb51af4 100644
--- a/arch/x86/include/asm/tdx_global_metadata.h
+++ b/arch/x86/include/asm/tdx_global_metadata.h
@@ -21,6 +21,9 @@ struct tdx_sys_info_tdmr {
 	u16 pamt_4k_entry_size;
 	u16 pamt_2m_entry_size;
 	u16 pamt_1g_entry_size;
+
+	/* Optional metadata, if Dynamic PAMT is supported */
+	u8  pamt_page_bitmap_entry_bits;
 };
 
 struct tdx_sys_info_td_ctrl {
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 487f389f52f4b..9ebd192cb5c17 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -512,6 +512,18 @@ static __init int fill_out_tdmrs(struct list_head *tmb_list,
 	return 0;
 }
 
+static __init unsigned long tdmr_get_pamt_bitmap_sz(struct tdmr_info *tdmr)
+{
+	unsigned long pamt_sz, nr_pamt_entries;
+	int bits_per_entry;
+
+	bits_per_entry = tdx_sysinfo.tdmr.pamt_page_bitmap_entry_bits;
+	nr_pamt_entries = tdmr->size >> PAGE_SHIFT;
+	pamt_sz = DIV_ROUND_UP(nr_pamt_entries * bits_per_entry, BITS_PER_BYTE);
+
+	return PAGE_ALIGN(pamt_sz);
+}
+
 /*
  * Calculate PAMT size given a TDMR and a page size.  The returned
  * PAMT size is always aligned up to 4K page boundary.
@@ -579,7 +591,12 @@ static __init int tdmr_set_up_pamt(struct tdmr_info *tdmr,
 	 * Calculate the PAMT size for each TDX supported page size
 	 * and the total PAMT size.
 	 */
-	tdmr->pamt_4k_size = tdmr_get_pamt_sz(tdmr, TDX_PS_4K);
+	if (tdx_supports_dynamic_pamt(&tdx_sysinfo)) {
+		/* With Dynamic PAMT, PAMT_4K is replaced with a bitmap */
+		tdmr->pamt_4k_size = tdmr_get_pamt_bitmap_sz(tdmr);
+	} else {
+		tdmr->pamt_4k_size = tdmr_get_pamt_sz(tdmr, TDX_PS_4K);
+	}
 	tdmr->pamt_2m_size = tdmr_get_pamt_sz(tdmr, TDX_PS_2M);
 	tdmr->pamt_1g_size = tdmr_get_pamt_sz(tdmr, TDX_PS_1G);
 	tdmr_pamt_size = tdmr->pamt_4k_size + tdmr->pamt_2m_size + tdmr->pamt_1g_size;
diff --git a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
index c7db393a9cfb1..7e8e913463be1 100644
--- a/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
+++ b/arch/x86/virt/vmx/tdx/tdx_global_metadata.c
@@ -1,6 +1,6 @@
 // SPDX-License-Identifier: GPL-2.0
 /*
- * Automatically generated functions to read TDX global metadata.
+ * Functions to read TDX global metadata.
  *
  * This file doesn't compile on its own as it lacks of inclusion
  * of SEAMCALL wrapper primitive which reads global metadata.
@@ -33,6 +33,18 @@ static __init int get_tdx_sys_info_features(struct tdx_sys_info_features *sysinf
 	return ret;
 }
 
+static __init int get_tdx_sys_info_tdmr_dpamt(struct tdx_sys_info_tdmr *sysinfo_tdmr)
+{
+	int ret;
+	u64 val;
+
+	ret = read_sys_metadata_field(0x9100000100000013, &val);
+	if (!ret)
+		sysinfo_tdmr->pamt_page_bitmap_entry_bits = val;
+
+	return ret;
+}
+
 static __init int get_tdx_sys_info_tdmr(struct tdx_sys_info_tdmr *sysinfo_tdmr)
 {
 	int ret = 0;
@@ -116,5 +128,12 @@ static __init int get_tdx_sys_info(struct tdx_sys_info *sysinfo)
 	ret = ret ?: get_tdx_sys_info_td_ctrl(&sysinfo->td_ctrl);
 	ret = ret ?: get_tdx_sys_info_td_conf(&sysinfo->td_conf);
 
+	/*
+	 * Don't treat a module that doesn't support Dynamic PAMT
+	 * as a failure. Only read the metadata optionally.
+	 */
+	if (!ret && tdx_supports_dynamic_pamt(sysinfo))
+		ret = get_tdx_sys_info_tdmr_dpamt(&sysinfo->tdmr);
+
 	return ret;
 }

---

## [4] Rick Edgecombe — 2026-05-25
*Subject: [PATCH v6 03/11] x86/virt/tdx: Add tdx_alloc/free_control_page() helpers*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

Add helpers to use when allocating or preparing pages that are handed to
the TDX-Module for use as control/S-EPT pages, and thus need Dynamic PAMT
adjustments.

The TDX module tracks some state for each page of physical memory that it
might use. It calls this state the PAMT. It includes separate state for
each page size a physical page could be utilized at within the TDX module
(1GB, 2MB, 4KB). In Dynamic PAMT, only the 4KB page size state is
allocated dynamically. So for pages that TDX will use as 2MB physically
contiguous pages, Dynamic PAMT backing is not needed.

KVM will need to hand pages to the TDX module that it will use at 4KB
granularity. So these pages will need Dynamic PAMT backing added before
they are used by the TDX module, and removed afterwards.

Add tdx_alloc_control_page() and tdx_free_control_page() to handle both
page allocation and Dynamic PAMT installation. Make them behave like
normal alloc/free functions where allocation can fail in the case of no
memory, but free (with any necessary Dynamic PAMT release) always
succeeds. Do this so they can support the existing TDX flows that require
teardowns to succeed.

Also create tdx_pamt_get/put() to handle installing Dynamic PAMT 4KB
backing for pages that are already allocated (such as KVM's use of S-EPT
page tables or guest private memory). Have them take a pfn instead of a
struct page, as future changes will want to use these helpers for guest
pages which are tracked by PFN.

Don't CLFLUSH the Dynamic PAMT pages handed to the TDX module, as is done
for some other SEAMCALLs, as the TDX docs specify that this is only
needed on "TD private memory or TD control structure page".

Since these allocations will be easily user triggerable, account the
memory.

Leave logic to handle concurrency issues for future changes.

Assisted-by: GitHub Copilot:claude-opus-4-6 Claude:claude-opus-4-7 Sashiko:claude-opus-4-6
Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Co-developed-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
Co-developed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v6:
The major change was to split out the concurrency stuff into a future
patch. It makes it easier to explain in the log. This one is the basic
functionality. Then the simple version of the concurrency and why in the
next patch. Also, to get rid of the dynamically sized DPAMT backing
support which was not based on a formal spec.

Details:
 - Split out concurrency stuff into next patch because the log was too long
 - Switch to fixed size pamt page arrays (Nikolay)
 - Rename tdx_alloc_page()/tdx_free_page() to tdx_alloc_control_page()/
   tdx_free_control_page() to reflect control/S-EPT purpose (Sean)
 - Take gfp from the caller in tdx_alloc_control_page() (Sean)
 - Narrow external API: make tdx_pamt_get()/tdx_pamt_put() static and
   export only tdx_alloc_control_page()/tdx_free_control_page() (note:
   dropped inline helpers since the discussion on Sean's series resulted
   in them not being needed)
 - Switch EXPORT_SYMBOL_GPL to EXPORT_SYMBOL_FOR_KVM (Sean)
 - Use WARN_ON_ONCE() instead of pr_err() for TDX module failures (Sean)
 - Fold alloc_pamt_array()/free_pamt_array() helpers back in and fix the
   error-unwind index bug (dpamt_pages[i] -> [j])
 - Adjustments after struct page->pfn
 - Adjustments from dropping error helper patches
 - Make the free error paths more normal
 - Drop gfp_t arg in tdx_alloc_control_page(). In the Sean mega v5, it
   was really needed because the kvm_mmu_memory_cache had a gfp_t it
   needed something to do with. But this was still weird because that
   version didn't handle allocating the DPAMT pages as the gfp_t. And in
   the end all the callers pass GFP_KERNEL_ACCOUNT. So just drop the arg.
 - Log tweaks
---
 arch/x86/include/asm/tdx.h  |   7 ++
 arch/x86/virt/vmx/tdx/tdx.c | 159 ++++++++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h |   2 +
 3 files changed, 168 insertions(+)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 82dc27aecf297..74e75db5728c7 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -37,6 +37,7 @@
 
 #include <uapi/asm/mce.h>
 #include <asm/tdx_global_metadata.h>
+#include <linux/mm.h>
 #include <linux/pgtable.h>
 
 /*
@@ -160,6 +161,12 @@ void tdx_guest_keyid_free(unsigned int keyid);
 
 void tdx_quirk_reset_paddr(unsigned long base, unsigned long size);
 
+/* Number PAMT pages to be provided to TDX module per 2MB region of PA */
+#define TDX_DPAMT_ENTRY_PAGE_CNT 2
+
+struct page *tdx_alloc_control_page(void);
+void tdx_free_control_page(struct page *page);
+
 struct tdx_td {
 	/* TD root structure: */
 	struct page *tdr_page;
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 9ebd192cb5c17..9e0812d87ab06 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1919,6 +1919,165 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, kvm_pfn_t pfn)
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_phymem_page_wbinvd_hkid);
 
+static int alloc_pamt_array(struct page **pamt_pages)
+{
+	int i, j;
+
+	for (i = 0; i < TDX_DPAMT_ENTRY_PAGE_CNT; i++) {
+		pamt_pages[i] = alloc_page(GFP_KERNEL_ACCOUNT);
+		if (!pamt_pages[i])
+			goto err;
+	}
+
+	return 0;
+err:
+	for (j = 0; j < i; j++)
+		__free_page(pamt_pages[j]);
+	return -ENOMEM;
+}
+
+static void free_pamt_array(struct page **pamt_pages)
+{
+	for (int i = 0; i < TDX_DPAMT_ENTRY_PAGE_CNT; i++) {
+		/*
+		 * Reset pages unconditionally to cover cases
+		 * where they were passed to the TDX module.
+		 */
+		tdx_quirk_reset_paddr(page_to_phys(pamt_pages[i]), PAGE_SIZE);
+
+		__free_page(pamt_pages[i]);
+	}
+}
+
+/*
+ * Calculate the arg needed for operating on the DPAMT backing for
+ * a given 4KB page.
+ */
+static u64 pamt_2mb_arg(kvm_pfn_t pfn)
+{
+	unsigned long hpa_2mb = ALIGN_DOWN(pfn << PAGE_SHIFT, PMD_SIZE);
+
+	return hpa_2mb | TDX_PS_2M;
+}
+
+/* Add PAMT backing for the given page. */
+static u64 tdh_phymem_pamt_add(kvm_pfn_t pfn, struct page **pamt_pages)
+{
+	struct tdx_module_args args = {
+		.rcx = pamt_2mb_arg(pfn),
+		.rdx = page_to_phys(pamt_pages[0]),
+		.r8 = page_to_phys(pamt_pages[1]),
+	};
+
+	return seamcall(TDH_PHYMEM_PAMT_ADD, &args);
+}
+
+/* Remove PAMT backing for the given page. */
+static u64 tdh_phymem_pamt_remove(kvm_pfn_t pfn, struct page **pamt_pages)
+{
+	struct tdx_module_args args = {
+		.rcx = pamt_2mb_arg(pfn),
+	};
+	u64 ret;
+
+	ret = seamcall_ret(TDH_PHYMEM_PAMT_REMOVE, &args);
+	if (ret)
+		return ret;
+
+	/* Copy PAMT pages out of the struct per the TDX ABI */
+	pamt_pages[0] = phys_to_page(args.rdx);
+	pamt_pages[1] = phys_to_page(args.r8);
+
+	return 0;
+}
+
+/* Allocate PAMT memory for the given page */
+static int tdx_pamt_get(kvm_pfn_t pfn)
+{
+	struct page *pamt_pages[TDX_DPAMT_ENTRY_PAGE_CNT];
+	u64 tdx_status;
+	int ret;
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return 0;
+
+	ret = alloc_pamt_array(pamt_pages);
+	if (ret)
+		return ret;
+
+	tdx_status = tdh_phymem_pamt_add(pfn, pamt_pages);
+	if (tdx_status != TDX_SUCCESS) {
+		ret = -EIO;
+		goto out_free;
+	}
+
+	return 0;
+out_free:
+	free_pamt_array(pamt_pages);
+	return ret;
+}
+
+/* Free PAMT memory for the given page */
+static void tdx_pamt_put(kvm_pfn_t pfn)
+{
+	struct page *pamt_pages[TDX_DPAMT_ENTRY_PAGE_CNT] = {};
+	u64 tdx_status;
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return;
+
+	tdx_status = tdh_phymem_pamt_remove(pfn, pamt_pages);
+
+	/*
+	 * Don't free pamt_pages as it could hold garbage when
+	 * tdh_phymem_pamt_remove() fails.  Don't panic/BUG_ON(), as
+	 * there is no risk of data corruption, but do yell loudly as
+	 * failure indicates a kernel bug, memory is being leaked, and
+	 * the dangling PAMT entry may cause future operations to fail.
+	 */
+	if (WARN_ON_ONCE(tdx_status != TDX_SUCCESS))
+		return;
+
+	free_pamt_array(pamt_pages);
+}
+
+/*
+ * Return a page that can be gifted to the TDX-Module for use as a "control"
+ * page, i.e. pages that are used for control and S-EPT structures for a given
+ * TDX guest, and bound to said guest's HKID and thus obtain TDX protections,
+ * including PAMT tracking.
+ */
+struct page *tdx_alloc_control_page(void)
+{
+	struct page *page;
+
+	page = alloc_page(GFP_KERNEL_ACCOUNT);
+	if (!page)
+		return NULL;
+
+	if (tdx_pamt_get(page_to_pfn(page))) {
+		__free_page(page);
+		return NULL;
+	}
+
+	return page;
+}
+EXPORT_SYMBOL_FOR_KVM(tdx_alloc_control_page);
+
+/*
+ * Free a page that was gifted to the TDX-Module for use as a control/S-EPT
+ * page. After this, the page is no longer protected by TDX.
+ */
+void tdx_free_control_page(struct page *page)
+{
+	if (!page)
+		return;
+
+	tdx_pamt_put(page_to_pfn(page));
+	__free_page(page);
+}
+EXPORT_SYMBOL_FOR_KVM(tdx_free_control_page);
+
 #ifdef CONFIG_KEXEC_CORE
 void tdx_cpu_flush_cache_for_kexec(void)
 {
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index dde219c823b41..8c39dde347cc2 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -46,6 +46,8 @@
 #define TDH_PHYMEM_PAGE_WBINVD		41
 #define TDH_VP_WR			43
 #define TDH_SYS_CONFIG			45
+#define TDH_PHYMEM_PAMT_ADD		58
+#define TDH_PHYMEM_PAMT_REMOVE		59
 
 /*
  * SEAMCALL leaf:

---

## [5] Rick Edgecombe — 2026-05-25
*Subject: [PATCH v6 04/11] x86/virt/tdx: Allocate ref counts for Dynamic PAMT memory*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

The PAMT memory holds metadata for all possible TDX protected memory. Each
physical address range is covered by PAMT entries at three levels (1GB,
2MB, 4KB). With Dynamic PAMT, the 4KB range of PAMT is allocated on
demand. The kernel supplies the TDX module with page pairs to store the
4KB entries, which cover 2MB of host physical memory. The kernel must
provide this page pair before using pages from the range for TDX. If this
is not done, SEAMCALLs that give the pages to be protected by the TDX module
will fail.

Allocate reference counters for every 2MB range to track TDX memory usage.
This can be used to handle concurrent get/put callers, in order to
accurately determine when the dynamic 4KB level of Dynamic PAMT needs to
be allocated and when it can be freed.

This allocation will currently consume 2 MB for every 1 TB of address
space from 0 to max_pfn. The allocation size will depend on how the RAM is
physically laid out. In a worst case scenario where the entire 52-bit
address space is covered this would be 8GB. Then the DPAMT refcount
allocations could hypothetically cause the savings from Dynamic PAMT to go
negative on exotic platforms with sparse, small amounts of memory.

Future changes could reduce this refcount overhead to be only allocating
refcounts for physical ranges that contain memory that TDX can use.
However, this is left for future work.

Assisted-by: Sashiko:claude-opus-4-6 GitHub Copilot:claude-opus-4-6 Sashiko:claude-opus-4-6
Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Co-developed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v6:
 - Remove confusing reference to allocating PAMT memory in
   pamt_refcounts comment. (Yan)
 - Rename "metadata" function names that really deal with refcounts, as
   metadata already has a different meaning in TDX.
 - Move tdx_find_pamt_refcount() to this patch to aid in reviewability

v4:
 - Log typo (Binbin)
 - round correctly when computing PAMT refcount size (Binbin)
 - Zero refcount vmalloc allocation (Note: This got replaced in
   optimization patch with a zero-ed allocation, but this showed up in
   testing with the optimization patches removed. Since it's fixed
   before this code is exercised, it's not a bisectability issue, but fix
   it anyway.)

v3:
 - Split out lazily populate optimization to next patch (Dave)
 - Add comment around pamt_refcounts (Dave)
 - Improve log
---
 arch/x86/virt/vmx/tdx/tdx.c | 54 ++++++++++++++++++++++++++++++++++++-
 1 file changed, 53 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 9e0812d87ab06..6658a6be6697c 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -30,6 +30,7 @@
 #include <linux/suspend.h>
 #include <linux/syscore_ops.h>
 #include <linux/idr.h>
+#include <linux/vmalloc.h>
 #include <asm/page.h>
 #include <asm/special_insns.h>
 #include <asm/msr-index.h>
@@ -52,6 +53,14 @@ static DEFINE_PER_CPU(bool, tdx_lp_initialized);
 
 static struct tdmr_info_list tdx_tdmr_list;
 
+/*
+ * On a machine with Dynamic PAMT, the kernel maintains a reference counter
+ * for every 2M range. The counter indicates how many users there are for
+ * the PAMT memory of the 2M range. The kernel allocates PAMT refcounts at
+ * initialization.
+ */
+static atomic_t *pamt_refcounts;
+
 /* All TDX-usable memory regions.  Protected by mem_hotplug_lock. */
 static LIST_HEAD(tdx_memlist);
 
@@ -254,6 +263,43 @@ static struct syscore tdx_syscore = {
 	.ops = &tdx_syscore_ops,
 };
 
+/*
+ * Allocate PAMT reference counters for all physical memory.
+ *
+ * It consumes 2MiB for every 1TiB of physical memory.
+ */
+static int init_pamt_refcounts(void)
+{
+	size_t size = DIV_ROUND_UP(max_pfn, PTRS_PER_PTE) * sizeof(*pamt_refcounts);
+
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return 0;
+
+	pamt_refcounts = __vmalloc(size, GFP_KERNEL | __GFP_ZERO);
+	if (!pamt_refcounts)
+		return -ENOMEM;
+
+	return 0;
+}
+
+static void free_pamt_refcounts(void)
+{
+	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
+		return;
+
+	vfree(pamt_refcounts);
+	pamt_refcounts = NULL;
+}
+
+/* Find PAMT refcount for a given physical address */
+static atomic_t * __maybe_unused tdx_find_pamt_refcount(unsigned long pfn)
+{
+	/* Find which PMD a PFN is in. */
+	unsigned long index = pfn >> (PMD_SHIFT - PAGE_SHIFT);
+
+	return &pamt_refcounts[index];
+}
+
 /*
  * Add a memory region as a TDX memory block.  The caller must make sure
  * all memory regions are added in address ascending order and don't
@@ -1151,10 +1197,14 @@ static __init int init_tdx_module(void)
 	 */
 	get_online_mems();
 
-	ret = build_tdx_memlist(&tdx_memlist);
+	ret = init_pamt_refcounts();
 	if (ret)
 		goto out_put_tdxmem;
 
+	ret = build_tdx_memlist(&tdx_memlist);
+	if (ret)
+		goto err_free_pamt_refcounts;
+
 	/* Allocate enough space for constructing TDMRs */
 	ret = alloc_tdmr_list(&tdx_tdmr_list, &tdx_sysinfo.tdmr);
 	if (ret)
@@ -1204,6 +1254,8 @@ static __init int init_tdx_module(void)
 	free_tdmr_list(&tdx_tdmr_list);
 err_free_tdxmem:
 	free_tdx_memlist(&tdx_memlist);
+err_free_pamt_refcounts:
+	free_pamt_refcounts();
 	goto out_put_tdxmem;
 }

---

## [6] Rick Edgecombe — 2026-05-25
*Subject: [PATCH v6 05/11] x86/virt/tdx: Handle concurrent callers in tdx_pamt_get/put()*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

tdx_pamt_get()/tdx_pamt_put() unconditionally add or remove Dynamic PAMT
backing for the 2MB region covering the passed pfn. However, multiple
callers can concurrently operate on 4KB pages that fall within the same
2MB region. When this happens only one Dynamic PAMT page pair needs to be
installed to cover the 2MB range. And when one page is freed, the Dynamic
PAMT backing cannot be freed until all pages in the range are no longer in
use. Make the helpers handle these races internally.

Use the per-2MB refcounts from previous changes to track how many 4KB
pages are in use within each region. Gate the actual Dynamic PAMT add and
remove on refcount transitions (0->1 and 1->0). Serialize the refcount
check and SEAMCALL with a global spinlock so the read-decide-act sequence
is atomic. This also avoids TDX module BUSY errors, as Dynamic PAMT add
and remove SEAMCALLs take an internal TDX module locks at 2MB granularity,
so simultaneous attempts on the same region would conflict.

The lock is global and heavyweight. Use simple conditional logic to keep
correctness obvious. This will be optimized in a later change.

Assisted-by: GitHub Copilot:claude-opus-4-6 Claude:claude-opus-4-7
Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Co-developed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v6:
 - Split from "x86/virt/tdx: Add tdx_alloc/free_control_page() helpers"
 - Return 0 instead of ret to be clearer (Binbin)
 - Clarify log (Nikolay)
 - Justify why the patch is not optimized in response to comments by
   (Nikolay)
 - Move tdx_find_pamt_refcount() to faciliate patch re-order
 - Adjustments from dropping error helper patches
 - Log tweaks
---
 arch/x86/virt/vmx/tdx/tdx.c | 72 ++++++++++++++++++++++++++++---------
 1 file changed, 56 insertions(+), 16 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 6658a6be6697c..50333eb96efa6 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2043,10 +2043,14 @@ static u64 tdh_phymem_pamt_remove(kvm_pfn_t pfn, struct page **pamt_pages)
 	return 0;
 }
 
-/* Allocate PAMT memory for the given page */
+/* Serializes adding/removing PAMT memory */
+static DEFINE_SPINLOCK(pamt_lock);
+
+/* Bump PAMT refcount for the given page and allocate PAMT memory if needed */
 static int tdx_pamt_get(kvm_pfn_t pfn)
 {
 	struct page *pamt_pages[TDX_DPAMT_ENTRY_PAGE_CNT];
+	atomic_t *pamt_refcount;
 	u64 tdx_status;
 	int ret;
 
@@ -2057,10 +2061,26 @@ static int tdx_pamt_get(kvm_pfn_t pfn)
 	if (ret)
 		return ret;
 
-	tdx_status = tdh_phymem_pamt_add(pfn, pamt_pages);
-	if (tdx_status != TDX_SUCCESS) {
-		ret = -EIO;
-		goto out_free;
+	pamt_refcount = tdx_find_pamt_refcount(pfn);
+
+	scoped_guard(spinlock, &pamt_lock) {
+		/*
+		 * If the pamt page is already added (i.e. refcount >= 1),
+		 * then just increment the refcount.
+		 */
+		if (atomic_read(pamt_refcount)) {
+			atomic_inc(pamt_refcount);
+			goto out_free;
+		}
+
+		/* Try to add the pamt page and take the refcount 0->1. */
+		tdx_status = tdh_phymem_pamt_add(pfn, pamt_pages);
+		if (WARN_ON_ONCE(tdx_status != TDX_SUCCESS)) {
+			ret = -EIO;
+			goto out_free;
+		}
+
+		atomic_set(pamt_refcount, 1);
 	}
 
 	return 0;
@@ -2069,26 +2089,46 @@ static int tdx_pamt_get(kvm_pfn_t pfn)
 	return ret;
 }
 
-/* Free PAMT memory for the given page */
+/*
+ * Drop PAMT refcount for the given page and free PAMT memory if it is no
+ * longer needed.
+ */
 static void tdx_pamt_put(kvm_pfn_t pfn)
 {
 	struct page *pamt_pages[TDX_DPAMT_ENTRY_PAGE_CNT] = {};
+	atomic_t *pamt_refcount;
 	u64 tdx_status;
 
 	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
 		return;
 
-	tdx_status = tdh_phymem_pamt_remove(pfn, pamt_pages);
+	pamt_refcount = tdx_find_pamt_refcount(pfn);
 
-	/*
-	 * Don't free pamt_pages as it could hold garbage when
-	 * tdh_phymem_pamt_remove() fails.  Don't panic/BUG_ON(), as
-	 * there is no risk of data corruption, but do yell loudly as
-	 * failure indicates a kernel bug, memory is being leaked, and
-	 * the dangling PAMT entry may cause future operations to fail.
-	 */
-	if (WARN_ON_ONCE(tdx_status != TDX_SUCCESS))
-		return;
+	scoped_guard(spinlock, &pamt_lock) {
+		/*
+		 * If the there are more than 1 references on the pamt page,
+		 * don't remove it yet. Just decrement the refcount.
+		 */
+		if (atomic_read(pamt_refcount) > 1) {
+			atomic_dec(pamt_refcount);
+			return;
+		}
+
+		/* Try to remove the pamt page and take the refcount 1->0. */
+		tdx_status = tdh_phymem_pamt_remove(pfn, pamt_pages);
+
+		/*
+		 * Don't free pamt_pages as it could hold garbage when
+		 * tdh_phymem_pamt_remove() fails.  Don't panic/BUG_ON(), as
+		 * there is no risk of data corruption, but do yell loudly as
+		 * failure indicates a kernel bug, memory is being leaked, and
+		 * the dangling PAMT entry may cause future operations to fail.
+		 */
+		if (WARN_ON_ONCE(tdx_status != TDX_SUCCESS))
+			return;
+
+		atomic_set(pamt_refcount, 0);
+	}
 
 	free_pamt_array(pamt_pages);
 }

---

## [7] Rick Edgecombe — 2026-05-25
*Subject: [PATCH v6 06/11] x86/virt/tdx: Optimize tdx_pamt_get/put()*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

The Dynamic PAMT get/put helpers use a global spinlock to serialize all
refcount updates and SEAMCALL invocations. This gives correct behavior for
concurrent callers, but leads to contention. It is especially bad from the
KVM side, which is designed to allow faulting in EPT under a shared lock.
With the global spinlock, not only is the lock an exclusive one, but it is
for all TDs instead of just a single one.

But taking the global lock each time is actually unnecessary. Only the 0->1
and 1->0 refcount transitions actually need the lock (to pair with
SEAMCALLs that actually add and remove with the Dynamic PAMT pages). The
common case of incrementing or decrementing a non-zero refcount can be
done locklessly.

So create a fast and slow path. Check the refcount outside the lock and
only take it for the slowpath (0->1 and 1->0 transitions).

On the put side make the refcount adjustment and lock taking atomic so if
a 'get' happens between them, it doesn't cause the Dynamic PAMT to be
freed incorrectly. On the get side there is no technique for doing the
refcount adjustment and lock atomically, so check the refcount again
inside the lock.

Assisted-by: GitHub Copilot:claude-opus-4-6
Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Co-developed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v6:
 - Fix "tdx_pamt_add()" typo to "tdx_pamt_get()" in lost-race comment
 - Fix error path bug: set ret = -EIO and use WARN_ON_ONCE() instead of
   pr_err() for unexpected PAMT.ADD failures (Sean)
 - Use "set the refcount 0->1" wording to match atomic_set() usage
 - Wrap comments to 80 columns
 - Switch to atomic_dec_and_lock() and remove handling of races that are
   no longer needed as a result. Adjust comments as appropriate. (Dave)
 - Adjustments from dropping error helper patches
v4:
 - Use atomic_set() in the HPA_RANGE_NOT_FREE case (Kiryl)
 - Log, comment typos (Binbin)
 - Move PAMT page allocation after refcount check in tdx_pamt_get() to
   avoid an alloc/free in the common path.

v3:
 - Split out optimization from “x86/virt/tdx: Add tdx_alloc/free_page() helpers”
 - Remove edge case handling that I could not find a reason for
 - Write log
---
 arch/x86/virt/vmx/tdx/tdx.c | 102 +++++++++++++++++++++---------------
 1 file changed, 61 insertions(+), 41 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 50333eb96efa6..c41c632a4cdf2 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -2057,32 +2057,50 @@ static int tdx_pamt_get(kvm_pfn_t pfn)
 	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))
 		return 0;
 
+	pamt_refcount = tdx_find_pamt_refcount(pfn);
+
+	/*
+	 * If the pamt page is already added (i.e. refcount >= 1),
+	 * then just increment the refcount.
+	 */
+	if (atomic_inc_not_zero(pamt_refcount))
+		return 0;
+
 	ret = alloc_pamt_array(pamt_pages);
 	if (ret)
 		return ret;
 
-	pamt_refcount = tdx_find_pamt_refcount(pfn);
+	spin_lock(&pamt_lock);
 
-	scoped_guard(spinlock, &pamt_lock) {
-		/*
-		 * If the pamt page is already added (i.e. refcount >= 1),
-		 * then just increment the refcount.
-		 */
-		if (atomic_read(pamt_refcount)) {
-			atomic_inc(pamt_refcount);
-			goto out_free;
-		}
-
-		/* Try to add the pamt page and take the refcount 0->1. */
-		tdx_status = tdh_phymem_pamt_add(pfn, pamt_pages);
-		if (WARN_ON_ONCE(tdx_status != TDX_SUCCESS)) {
-			ret = -EIO;
-			goto out_free;
-		}
-
-		atomic_set(pamt_refcount, 1);
+	/*
+	 * Unlike tdx_pamt_put() which uses atomic_dec_and_lock() to
+	 * atomically handle the 1->0 transition, the get side has no
+	 * equivalent combined primitive for 0->1. Recheck under the
+	 * lock since another get may have already done the 0->1
+	 * transition after both saw atomic_inc_not_zero() fail.
+	 */
+	if (atomic_read(pamt_refcount)) {
+		atomic_inc(pamt_refcount);
+		spin_unlock(&pamt_lock);
+		goto out_free;
 	}
 
+	tdx_status = tdh_phymem_pamt_add(pfn, pamt_pages);
+	if (tdx_status == TDX_SUCCESS) {
+		/*
+		 * The refcount is zero, and this locked path is the
+		 * only way to increase it from 0->1.
+		 */
+		atomic_set(pamt_refcount, 1);
+	} else {
+		WARN_ON_ONCE(1);
+		ret = -EIO;
+		spin_unlock(&pamt_lock);
+		goto out_free;
+	}
+
+	spin_unlock(&pamt_lock);
+
 	return 0;
 out_free:
 	free_pamt_array(pamt_pages);
@@ -2104,32 +2122,34 @@ static void tdx_pamt_put(kvm_pfn_t pfn)
 
 	pamt_refcount = tdx_find_pamt_refcount(pfn);
 
-	scoped_guard(spinlock, &pamt_lock) {
+	/*
+	 * If there is more than 1 reference on the pamt page, don't
+	 * remove it yet. Just decrement the refcount.
+	 */
+	if (!atomic_dec_and_lock(pamt_refcount, &pamt_lock))
+		return;
+
+	tdx_status = tdh_phymem_pamt_remove(pfn, pamt_pages);
+
+	/*
+	 * Don't free pamt_pages as it could hold garbage when
+	 * tdh_phymem_pamt_remove() fails.  Don't panic/BUG_ON(), as
+	 * there is no risk of data corruption, but do yell loudly as
+	 * failure indicates a kernel bug, memory is being leaked, and
+	 * the dangling PAMT entry may cause future operations to fail.
+	 */
+	if (WARN_ON_ONCE(tdx_status != TDX_SUCCESS)) {
 		/*
-		 * If the there are more than 1 references on the pamt page,
-		 * don't remove it yet. Just decrement the refcount.
+		 * atomic_dec_and_lock() already decremented it to 0,
+		 * but the PAMT entry still exists since REMOVE failed.
 		 */
-		if (atomic_read(pamt_refcount) > 1) {
-			atomic_dec(pamt_refcount);
-			return;
-		}
-
-		/* Try to remove the pamt page and take the refcount 1->0. */
-		tdx_status = tdh_phymem_pamt_remove(pfn, pamt_pages);
-
-		/*
-		 * Don't free pamt_pages as it could hold garbage when
-		 * tdh_phymem_pamt_remove() fails.  Don't panic/BUG_ON(), as
-		 * there is no risk of data corruption, but do yell loudly as
-		 * failure indicates a kernel bug, memory is being leaked, and
-		 * the dangling PAMT entry may cause future operations to fail.
-		 */
-		if (WARN_ON_ONCE(tdx_status != TDX_SUCCESS))
-			return;
-
-		atomic_set(pamt_refcount, 0);
+		atomic_set(pamt_refcount, 1);
+		spin_unlock(&pamt_lock);
+		return;
 	}
 
+	spin_unlock(&pamt_lock);
+
 	free_pamt_array(pamt_pages);
 }

---

## [8] Rick Edgecombe — 2026-05-25
*Subject: [PATCH v6 07/11] KVM: TDX: Allocate PAMT memory for TD and vCPU control structures*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

Use control page helpers for allocating and freeing TD control structures,
such these operations can work for Dynamic PAMT.

The TDX module tracks some state for each page of physical memory that it
might use. It calls this state the PAMT. It includes separate state for
each page size a physical page could be utilized at within the TDX module
(1GB, 2MB, 4KB). In Dynamic PAMT, only the 4KB page size state is
allocated dynamically. So the kernel must install PAMT backing for each 4KB
page before gifting it to the TDX module, and tear it down after the page
is reclaimed.

TD-scoped control pages (TDR, TDCS) and vCPU-scoped control pages (TDVPR,
TDCX) are all handed to the TDX module at 4KB page size and are therefore
subject to this requirement. Replace the raw alloc_page()/__free_page()
calls for these pages with tdx_alloc/free_control_page().

Switching between special Dynamic PAMT operations or normal page
alloc/free operations is handled internally in
tdx_alloc/free_control_page(). So don't check for Dynamic PAMT around these
calls. Just call them unconditionally. Similarly, drop the NULL checks
before freeing, as tdx_free_control_page() handles NULL internally.

No functional change intended when Dynamic PAMT is not in use.

Assisted-by: GitHub Copilot:claude-opus-4-6 Claude:claude-opus-4-7
Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[sean: handle alloc+free+reclaim in one patch]
Co-developed-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
[Rick: enhance log]
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
 arch/x86/kvm/vmx/tdx.c | 35 ++++++++++++++---------------------
 1 file changed, 14 insertions(+), 21 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 2539107e0ad3d..3e67e2471ffe3 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -362,7 +362,7 @@ static void tdx_reclaim_control_page(struct page *ctrl_page)
 	if (tdx_reclaim_page(ctrl_page))
 		return;
 
-	__free_page(ctrl_page);
+	tdx_free_control_page(ctrl_page);
 }
 
 struct tdx_flush_vp_arg {
@@ -599,7 +599,7 @@ static void tdx_reclaim_td_control_pages(struct kvm *kvm)
 
 	tdx_quirk_reset_paddr(page_to_phys(kvm_tdx->td.tdr_page), PAGE_SIZE);
 
-	__free_page(kvm_tdx->td.tdr_page);
+	tdx_free_control_page(kvm_tdx->td.tdr_page);
 	kvm_tdx->td.tdr_page = NULL;
 }
 
@@ -2444,7 +2444,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 
 	ret = -ENOMEM;
 
-	tdr_page = alloc_page(GFP_KERNEL_ACCOUNT);
+	tdr_page = tdx_alloc_control_page();
 	if (!tdr_page)
 		goto free_hkid;
 
@@ -2458,7 +2458,7 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 		goto free_tdr;
 
 	for (i = 0; i < kvm_tdx->td.tdcs_nr_pages; i++) {
-		tdcs_pages[i] = alloc_page(GFP_KERNEL_ACCOUNT);
+		tdcs_pages[i] = tdx_alloc_control_page();
 		if (!tdcs_pages[i])
 			goto free_tdcs;
 	}
@@ -2576,10 +2576,8 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 teardown:
 	/* Only free pages not yet added, so start at 'i' */
 	for (; i < kvm_tdx->td.tdcs_nr_pages; i++) {
-		if (tdcs_pages[i]) {
-			__free_page(tdcs_pages[i]);
-			tdcs_pages[i] = NULL;
-		}
+		tdx_free_control_page(tdcs_pages[i]);
+		tdcs_pages[i] = NULL;
 	}
 	if (!kvm_tdx->td.tdcs_pages)
 		kfree(tdcs_pages);
@@ -2594,16 +2592,13 @@ static int __tdx_td_init(struct kvm *kvm, struct td_params *td_params,
 	free_cpumask_var(packages);
 
 free_tdcs:
-	for (i = 0; i < kvm_tdx->td.tdcs_nr_pages; i++) {
-		if (tdcs_pages[i])
-			__free_page(tdcs_pages[i]);
-	}
+	for (i = 0; i < kvm_tdx->td.tdcs_nr_pages; i++)
+		tdx_free_control_page(tdcs_pages[i]);
 	kfree(tdcs_pages);
 	kvm_tdx->td.tdcs_pages = NULL;
 
 free_tdr:
-	if (tdr_page)
-		__free_page(tdr_page);
+	tdx_free_control_page(tdr_page);
 	kvm_tdx->td.tdr_page = NULL;
 
 free_hkid:
@@ -2933,7 +2928,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 	int ret, i;
 	u64 err;
 
-	page = alloc_page(GFP_KERNEL_ACCOUNT);
+	page = tdx_alloc_control_page();
 	if (!page)
 		return -ENOMEM;
 	tdx->vp.tdvpr_page = page;
@@ -2953,7 +2948,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 	}
 
 	for (i = 0; i < kvm_tdx->td.tdcx_nr_pages; i++) {
-		page = alloc_page(GFP_KERNEL_ACCOUNT);
+		page = tdx_alloc_control_page();
 		if (!page) {
 			ret = -ENOMEM;
 			goto free_tdcx;
@@ -2975,7 +2970,7 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 			 * method, but the rest are freed here.
 			 */
 			for (; i < kvm_tdx->td.tdcx_nr_pages; i++) {
-				__free_page(tdx->vp.tdcx_pages[i]);
+				tdx_free_control_page(tdx->vp.tdcx_pages[i]);
 				tdx->vp.tdcx_pages[i] = NULL;
 			}
 			return -EIO;
@@ -3003,16 +2998,14 @@ static int tdx_td_vcpu_init(struct kvm_vcpu *vcpu, u64 vcpu_rcx)
 
 free_tdcx:
 	for (i = 0; i < kvm_tdx->td.tdcx_nr_pages; i++) {
-		if (tdx->vp.tdcx_pages[i])
-			__free_page(tdx->vp.tdcx_pages[i]);
+		tdx_free_control_page(tdx->vp.tdcx_pages[i]);
 		tdx->vp.tdcx_pages[i] = NULL;
 	}
 	kfree(tdx->vp.tdcx_pages);
 	tdx->vp.tdcx_pages = NULL;
 
 free_tdvpr:
-	if (tdx->vp.tdvpr_page)
-		__free_page(tdx->vp.tdvpr_page);
+	tdx_free_control_page(tdx->vp.tdvpr_page);
 	tdx->vp.tdvpr_page = NULL;
 	tdx->vp.tdvpr_pa = 0;

---

## [9] Rick Edgecombe — 2026-05-25
*Subject: [PATCH v6 08/11] x86/tdx: Add APIs to support Dynamic PAMT ops from KVM's fault path*

When handling an EPT violation, KVM holds a spinlock while manipulating
the EPT. Before entering the spinlock it doesn't know how many EPT page
tables will need to be installed or whether a huge page will be used. For
this reason it allocates a worst case number of page tables that it might
need as part of servicing the EPT violation.

Under Dynamic PAMT these pre-allocated pages will potentially need to have
Dynamic PAMT backing pages installed for them. KVM already has helpers to
manage topping up page caches before taking the MMU lock, but they cannot be
passed from KVM to arch/x86 code.

The problem of how and when to install the DPAMT backing pages for the
pages given to the TDX module during the fault path has had a lot of
design attempts.
 - Extracting KVM's MMU caches requires too much inlined code added to
   headers.
 - A few varieties of installing Dynamic PAMT backing when allocating the
   S-EPT page tables. [0][1]
 - Using mempool_t to transfer the pages between KVM and arch/x86 doesn't
   work because it is the component is designed more around maintaining a
   pool of pages, rather than topping up a continually drained cache.

So don't do these as they all had various problems. Instead just create a
small simple data structure to use for handing a pre-allocated list of
pages between KVM and arch/x86 code. Model this on KVM's existing MMU
memory caches.

Add a tdx_pamt_cache arg to tdx_pamt_get() so it can draw pages from a
cache when needed. Not all DPAMT page installations will happen under
spinlock, for example control pages. So have tdx_pamt_get() maintain the
existing behavior of allocating from the page allocator when NULL is
passed for the struct tdx_pamt_cache arg. This prevents excess allocations
for cases where it can be avoided.

Export the new helpers for KVM.

Assisted-by: GitHub Copilot:claude-opus-4-6 Claude:claude-opus-4-7
Co-developed-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Link: https://lore.kernel.org/kvm/de05853257e9cc66998101943f78a4b7e6e3d741.camel@intel.com/ [0]
Link: https://lore.kernel.org/kvm/aYprxnSHKHUtk7pt@google.com/ [1]
---
v6:
 - Filled out log from Sean's series
---
 arch/x86/include/asm/tdx.h  | 17 ++++++++++
 arch/x86/virt/vmx/tdx/tdx.c | 65 +++++++++++++++++++++++++++++++++----
 2 files changed, 76 insertions(+), 6 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 74e75db5728c7..191da84bbf2a1 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -155,6 +155,23 @@ static inline bool tdx_supports_dynamic_pamt(const struct tdx_sys_info *sysinfo)
 	return false; /* To be enabled when kernel is ready */
 }
 
+/* Simple structure for pre-allocating Dynamic PAMT pages outside of locks. */
+struct tdx_pamt_cache {
+	struct list_head page_list;
+	int cnt;
+};
+
+static inline void tdx_init_pamt_cache(struct tdx_pamt_cache *cache)
+{
+	INIT_LIST_HEAD(&cache->page_list);
+	cache->cnt = 0;
+}
+
+void tdx_free_pamt_cache(struct tdx_pamt_cache *cache);
+int tdx_topup_pamt_cache(struct tdx_pamt_cache *cache, unsigned long npages);
+int tdx_pamt_get(kvm_pfn_t pfn, struct tdx_pamt_cache *cache);
+void tdx_pamt_put(kvm_pfn_t pfn);
+
 int tdx_guest_keyid_alloc(void);
 u32 tdx_get_nr_guest_keyids(void);
 void tdx_guest_keyid_free(unsigned int keyid);
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index c41c632a4cdf2..3544794fb092a 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1971,12 +1971,33 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hkid, kvm_pfn_t pfn)
 }
 EXPORT_SYMBOL_FOR_KVM(tdh_phymem_page_wbinvd_hkid);
 
-static int alloc_pamt_array(struct page **pamt_pages)
+static struct page *tdx_alloc_page_pamt_cache(struct tdx_pamt_cache *cache)
+{
+	struct page *page;
+
+	page = list_first_entry_or_null(&cache->page_list, struct page, lru);
+	if (page) {
+		list_del(&page->lru);
+		cache->cnt--;
+	}
+
+	return page;
+}
+
+static struct page *alloc_dpamt_page(struct tdx_pamt_cache *cache)
+{
+	if (cache)
+		return tdx_alloc_page_pamt_cache(cache);
+
+	return alloc_page(GFP_KERNEL_ACCOUNT);
+}
+
+static int alloc_pamt_array(struct page **pamt_pages, struct tdx_pamt_cache *cache)
 {
 	int i, j;
 
 	for (i = 0; i < TDX_DPAMT_ENTRY_PAGE_CNT; i++) {
-		pamt_pages[i] = alloc_page(GFP_KERNEL_ACCOUNT);
+		pamt_pages[i] = alloc_dpamt_page(cache);
 		if (!pamt_pages[i])
 			goto err;
 	}
@@ -2047,7 +2068,7 @@ static u64 tdh_phymem_pamt_remove(kvm_pfn_t pfn, struct page **pamt_pages)
 static DEFINE_SPINLOCK(pamt_lock);
 
 /* Bump PAMT refcount for the given page and allocate PAMT memory if needed */
-static int tdx_pamt_get(kvm_pfn_t pfn)
+int tdx_pamt_get(kvm_pfn_t pfn, struct tdx_pamt_cache *cache)
 {
 	struct page *pamt_pages[TDX_DPAMT_ENTRY_PAGE_CNT];
 	atomic_t *pamt_refcount;
@@ -2066,7 +2087,7 @@ static int tdx_pamt_get(kvm_pfn_t pfn)
 	if (atomic_inc_not_zero(pamt_refcount))
 		return 0;
 
-	ret = alloc_pamt_array(pamt_pages);
+	ret = alloc_pamt_array(pamt_pages, cache);
 	if (ret)
 		return ret;
 
@@ -2106,12 +2127,13 @@ static int tdx_pamt_get(kvm_pfn_t pfn)
 	free_pamt_array(pamt_pages);
 	return ret;
 }
+EXPORT_SYMBOL_FOR_KVM(tdx_pamt_get);
 
 /*
  * Drop PAMT refcount for the given page and free PAMT memory if it is no
  * longer needed.
  */
-static void tdx_pamt_put(kvm_pfn_t pfn)
+void tdx_pamt_put(kvm_pfn_t pfn)
 {
 	struct page *pamt_pages[TDX_DPAMT_ENTRY_PAGE_CNT] = {};
 	atomic_t *pamt_refcount;
@@ -2152,6 +2174,37 @@ static void tdx_pamt_put(kvm_pfn_t pfn)
 
 	free_pamt_array(pamt_pages);
 }
+EXPORT_SYMBOL_FOR_KVM(tdx_pamt_put);
+
+void tdx_free_pamt_cache(struct tdx_pamt_cache *cache)
+{
+	struct page *page;
+
+	while ((page = tdx_alloc_page_pamt_cache(cache)))
+		__free_page(page);
+}
+EXPORT_SYMBOL_FOR_KVM(tdx_free_pamt_cache);
+
+int tdx_topup_pamt_cache(struct tdx_pamt_cache *cache, unsigned long npages)
+{
+	if (WARN_ON_ONCE(!tdx_supports_dynamic_pamt(&tdx_sysinfo)))
+		return 0;
+
+	npages *= TDX_DPAMT_ENTRY_PAGE_CNT;
+
+	while (cache->cnt < npages) {
+		struct page *page = alloc_page(GFP_KERNEL_ACCOUNT);
+
+		if (!page)
+			return -ENOMEM;
+
+		list_add(&page->lru, &cache->page_list);
+		cache->cnt++;
+	}
+
+	return 0;
+}
+EXPORT_SYMBOL_FOR_KVM(tdx_topup_pamt_cache);
 
 /*
  * Return a page that can be gifted to the TDX-Module for use as a "control"
@@ -2167,7 +2220,7 @@ struct page *tdx_alloc_control_page(void)
 	if (!page)
 		return NULL;
 
-	if (tdx_pamt_get(page_to_pfn(page))) {
+	if (tdx_pamt_get(page_to_pfn(page), NULL)) {
 		__free_page(page);
 		return NULL;
 	}

---

## [10] Rick Edgecombe — 2026-05-25
*Subject: [PATCH v6 09/11] KVM: TDX: Get/put PAMT pages when (un)mapping private memory*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

Add Dynamic PAMT support to KVM's S-EPT MMU by "getting" a PAMT page when
adding guest memory (PAGE.ADD or PAGE.AUG), and "putting" the page when
removing guest memory (PAGE.REMOVE).

To access the per-vCPU PAMT caches without plumbing @vcpu throughout the
TDP MMU, begrudgingly use kvm_get_running_vcpu() to get the vCPU, and bug
the VM if KVM attempts to set an S-EPT leaf without an active vCPU.  KVM
only supports creating _new_ mappings in page (pre)fault paths, all of
which require an active vCPU.

The PAMT memory holds metadata for TDX-protected memory. With Dynamic
PAMT, PAMT_4K is allocated on demand. The kernel supplies the TDX module
with a few pages that cover 2M of host physical memory.

Releases are balanced via tdx_pamt_put(): every control-page free goes
through tdx_free_control_page(), and guest data pages are put directly on
the successful tdh_mem_page_remove() path and in the
tdx_mem_page_add/aug() error path.

Assisted-by: Sashiko:claude-opus-4-6 GitHub Copilot:claude-opus-4-6 Claude:claude-opus-4-7
Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Co-developed-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
Co-developed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v6:
 - Don't have topup op take a min param (Yan, Sean)
 - Make log match style of the rest of the series
 - Adjustments from dropping error helper patches
---
 arch/x86/include/asm/kvm-x86-ops.h |  1 +
 arch/x86/include/asm/kvm_host.h    |  2 +
 arch/x86/kvm/mmu/mmu.c             |  4 ++
 arch/x86/kvm/vmx/tdx.c             | 65 ++++++++++++++++++++++++++----
 arch/x86/kvm/vmx/tdx.h             |  2 +
 5 files changed, 66 insertions(+), 8 deletions(-)

diff --git a/arch/x86/include/asm/kvm-x86-ops.h b/arch/x86/include/asm/kvm-x86-ops.h
index 10ccf6ea9d9a2..320f1d30edacc 100644
--- a/arch/x86/include/asm/kvm-x86-ops.h
+++ b/arch/x86/include/asm/kvm-x86-ops.h
@@ -97,6 +97,7 @@ KVM_X86_OP_OPTIONAL_RET0(get_mt_mask)
 KVM_X86_OP(load_mmu_pgd)
 KVM_X86_OP_OPTIONAL_RET0(set_external_spte)
 KVM_X86_OP_OPTIONAL(free_external_spt)
+KVM_X86_OP_OPTIONAL_RET0(topup_external_cache)
 KVM_X86_OP(has_wbinvd_exit)
 KVM_X86_OP(get_l2_tsc_offset)
 KVM_X86_OP(get_l2_tsc_multiplier)
diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index 6b28dd387bc61..bfe92e993a212 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -1898,6 +1898,8 @@ struct kvm_x86_ops {
 	/* Update external page tables for page table about to be freed. */
 	void (*free_external_spt)(struct kvm *kvm, struct kvm_mmu_page *sp);
 
+	int (*topup_external_cache)(struct kvm_vcpu *vcpu, int min_nr_spts);
+
 
 	bool (*has_wbinvd_exit)(void);
 
diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index 892246204435c..2a48fc7fccc11 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -607,6 +607,10 @@ static int mmu_topup_memory_caches(struct kvm_vcpu *vcpu, bool maybe_indirect)
 					       PT64_ROOT_MAX_LEVEL);
 		if (r)
 			return r;
+
+		r = kvm_x86_call(topup_external_cache)(vcpu, PT64_ROOT_MAX_LEVEL);
+		if (r)
+			return r;
 	}
 	r = kvm_mmu_topup_memory_cache(&vcpu->arch.mmu_shadow_page_cache,
 				       PT64_ROOT_MAX_LEVEL);
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 3e67e2471ffe3..ee073cacafbec 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -685,6 +685,8 @@ int tdx_vcpu_create(struct kvm_vcpu *vcpu)
 	if (!irqchip_split(vcpu->kvm))
 		return -EINVAL;
 
+	tdx_init_pamt_cache(&tdx->pamt_cache);
+
 	fpstate_set_confidential(&vcpu->arch.guest_fpu);
 	vcpu->arch.apic->guest_apic_protected = true;
 	INIT_LIST_HEAD(&tdx->vt.pi_wakeup_list);
@@ -870,6 +872,8 @@ void tdx_vcpu_free(struct kvm_vcpu *vcpu)
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
 	int i;
 
+	tdx_free_pamt_cache(&tdx->pamt_cache);
+
 	if (vcpu->cpu != -1) {
 		KVM_BUG_ON(tdx->state == VCPU_TD_STATE_INITIALIZED, vcpu->kvm);
 		tdx_flush_vp_on_cpu(vcpu);
@@ -1611,6 +1615,16 @@ void tdx_load_mmu_pgd(struct kvm_vcpu *vcpu, hpa_t root_hpa, int pgd_level)
 	td_vmcs_write64(to_tdx(vcpu), SHARED_EPT_POINTER, root_hpa);
 }
 
+static int tdx_topup_external_pamt_cache(struct kvm_vcpu *vcpu, int min_nr_spts)
+{
+	/*
+	 * Don't cover the root SPT, but cover a possible 4KB private
+	 * page in addition to the SPTs. So -1 to exclude the root
+	 * SPT, and +1 for the guest page cancel out.
+	 */
+	return tdx_topup_pamt_cache(&to_tdx(vcpu)->pamt_cache, min_nr_spts);
+}
+
 static int tdx_mem_page_add(struct kvm *kvm, gfn_t gfn, enum pg_level level,
 			    kvm_pfn_t pfn)
 {
@@ -1669,16 +1683,29 @@ static struct page *tdx_spte_to_sept_pt(struct kvm *kvm, gfn_t gfn,
 static int tdx_sept_map_nonleaf_spte(struct kvm *kvm, gfn_t gfn,
 				     enum pg_level level, u64 new_spte)
 {
+	struct kvm_vcpu *vcpu = kvm_get_running_vcpu();
+	struct vcpu_tdx *tdx = to_tdx(vcpu);
 	gpa_t gpa = gfn_to_gpa(gfn);
 	u64 err, entry, level_state;
 	struct page *sept_pt;
+	int ret;
+
+	if (KVM_BUG_ON(!vcpu, kvm))
+		return -EIO;
 
 	sept_pt = tdx_spte_to_sept_pt(kvm, gfn, new_spte, level);
 	if (!sept_pt)
 		return -EIO;
 
+	ret = tdx_pamt_get(page_to_pfn(sept_pt), &tdx->pamt_cache);
+	if (ret)
+		return ret;
+
 	err = tdh_mem_sept_add(&to_kvm_tdx(kvm)->td, gpa, level, sept_pt,
 			       &entry, &level_state);
+	if (err)
+		tdx_pamt_put(page_to_pfn(sept_pt));
+
 	if (unlikely(tdx_operand_busy(err)))
 		return -EBUSY;
 
@@ -1691,8 +1718,14 @@ static int tdx_sept_map_nonleaf_spte(struct kvm *kvm, gfn_t gfn,
 static int tdx_sept_map_leaf_spte(struct kvm *kvm, gfn_t gfn, enum pg_level level,
 				  u64 new_spte)
 {
+	struct kvm_vcpu *vcpu = kvm_get_running_vcpu();
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
 	kvm_pfn_t pfn = spte_to_pfn(new_spte);
+	struct vcpu_tdx *tdx = to_tdx(vcpu);
+	int ret;
+
+	if (KVM_BUG_ON(!vcpu, kvm))
+		return -EIO;
 
 	/* TODO: handle large pages. */
 	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
@@ -1700,6 +1733,10 @@ static int tdx_sept_map_leaf_spte(struct kvm *kvm, gfn_t gfn, enum pg_level leve
 
 	WARN_ON_ONCE((new_spte & VMX_EPT_RWX_MASK) != VMX_EPT_RWX_MASK);
 
+	ret = tdx_pamt_get(pfn, &tdx->pamt_cache);
+	if (ret)
+		return ret;
+
 	/*
 	 * Ensure pre_fault_allowed is read by kvm_arch_vcpu_pre_fault_memory()
 	 * before kvm_tdx->state.  Userspace must not be allowed to pre-fault
@@ -1712,10 +1749,15 @@ static int tdx_sept_map_leaf_spte(struct kvm *kvm, gfn_t gfn, enum pg_level leve
 	 * If the TD isn't finalized/runnable, then userspace is initializing
 	 * the VM image via KVM_TDX_INIT_MEM_REGION; ADD the page to the TD.
 	 */
-	if (unlikely(kvm_tdx->state != TD_STATE_RUNNABLE))
-		return tdx_mem_page_add(kvm, gfn, level, pfn);
+	if (likely(kvm_tdx->state == TD_STATE_RUNNABLE))
+		ret = tdx_mem_page_aug(kvm, gfn, level, pfn);
+	else
+		ret = tdx_mem_page_add(kvm, gfn, level, pfn);
 
-	return tdx_mem_page_aug(kvm, gfn, level, pfn);
+	if (ret)
+		tdx_pamt_put(pfn);
+
+	return ret;
 }
 
 /*
@@ -1812,6 +1854,7 @@ static int tdx_sept_remove_leaf_spte(struct kvm *kvm, gfn_t gfn,
 		return -EIO;
 
 	tdx_quirk_reset_paddr(PFN_PHYS(pfn), PAGE_SIZE);
+	tdx_pamt_put(pfn);
 	return 0;
 }
 
@@ -1855,6 +1898,8 @@ static int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn, u64 old_spte,
  */
 static void tdx_sept_free_private_spt(struct kvm *kvm, struct kvm_mmu_page *sp)
 {
+	struct page *sept_pt = virt_to_page(sp->external_spt);
+
 	/*
 	 * KVM doesn't (yet) zap page table pages in mirror page table while
 	 * TD is active, though guest pages mapped in mirror page table could be
@@ -1868,15 +1913,15 @@ static void tdx_sept_free_private_spt(struct kvm *kvm, struct kvm_mmu_page *sp)
 	 * the page to prevent the kernel from accessing the encrypted page.
 	 */
 	if (KVM_BUG_ON(is_hkid_assigned(to_kvm_tdx(kvm)), kvm) ||
-	    tdx_reclaim_page(virt_to_page(sp->external_spt)))
+	    tdx_reclaim_page(sept_pt))
 		goto out;
 
 	/*
-	 * Immediately free the S-EPT page because RCU-time free is unnecessary
-	 * after TDH.PHYMEM.PAGE.RECLAIM ensures there are no outstanding
-	 * readers.
+	 * Immediately free the S-EPT page as the TDX subsystem doesn't support
+	 * freeing pages from RCU callbacks, and more importantly because
+	 * TDH.PHYMEM.PAGE.RECLAIM ensures there are no outstanding readers.
 	 */
-	free_page((unsigned long)sp->external_spt);
+	tdx_free_control_page(sept_pt);
 out:
 	sp->external_spt = NULL;
 }
@@ -3468,6 +3513,10 @@ int __init tdx_hardware_setup(void)
 
 	vt_x86_ops.set_external_spte = tdx_sept_set_private_spte;
 	vt_x86_ops.free_external_spt = tdx_sept_free_private_spt;
+
+	if (tdx_supports_dynamic_pamt(tdx_sysinfo))
+		vt_x86_ops.topup_external_cache = tdx_topup_external_pamt_cache;
+
 	vt_x86_ops.protected_apic_has_interrupt = tdx_protected_apic_has_interrupt;
 	return 0;
 
diff --git a/arch/x86/kvm/vmx/tdx.h b/arch/x86/kvm/vmx/tdx.h
index b5cd2ffb303e5..47334a5a74eab 100644
--- a/arch/x86/kvm/vmx/tdx.h
+++ b/arch/x86/kvm/vmx/tdx.h
@@ -73,6 +73,8 @@ struct vcpu_tdx {
 
 	u64 map_gpa_next;
 	u64 map_gpa_end;
+
+	struct tdx_pamt_cache pamt_cache;
 };
 
 void tdh_vp_rd_failed(struct vcpu_tdx *tdx, char *uclass, u32 field, u64 err);

---

## [11] Rick Edgecombe — 2026-05-25
*Subject: [PATCH v6 10/11] x86/virt/tdx: Enable Dynamic PAMT*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

The Physical Address Metadata Table (PAMT) holds TDX metadata for
physical memory and must be allocated by the kernel during TDX module
initialization. Dynamic PAMT is a TDX module feature that can reduce this
memory use by allocating part of the PAMT dynamically.

All pieces are in place to Enable Dynamic PAMT if it is supported.
Determine if the TDX module supports it by checking the 'features0' bit
exposed by the TDX module.

The TDX module also exposes information about whether the *system* (and
not the module) supports Dynamic PAMT.

The TDX module documentation describes how PAMT works internally. To allow
the last level to be dynamically allocated, it uses a 3 level tree
structure, not unlike page tables. Like page tables, it has a maximum
address space that it can cover. This address space can be covered in 48
bits. If the host physical address space is higher than this, than the
TDX module can't guarantee the tree will be able to cover the TDX memory.

The TDX module exposes this system support via metadata stating the
minimum number of HKIDs that need to be available in order for Dynamic
PAMT to be usable. The reasoning appears to be that more HKIDs can shrink
the "real" addressable physical address bits enough to make the 48 bit
Dynamic PAMT limit workable on high physical address width HW. However,
the docs also clearly explain the 48 bit limit and how this fits into the
Dymamic PAMT tree constraints.

The handy x86_phys_bits value is already read and adjusted for keyid bits.
So just compare that against 48 instead of reading more metadata and
burdening the code with the more tenuous connection to minimum HKID bits.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Co-developed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v6:
 - After Nikolai pointed out that the TDX docs actually have the Dynamic
   PAMT pages-per-2MB region fixed at 2 instead of variable sized, I
   checked over the docs more closely looking for anything else that might
   have been missed. Spotted this 48 bit physical address bit check in the
   docs, so added it.
---
 arch/x86/include/asm/tdx.h  | 11 ++++++++++-
 arch/x86/virt/vmx/tdx/tdx.c | 11 +++++++++--
 arch/x86/virt/vmx/tdx/tdx.h |  3 ---
 3 files changed, 19 insertions(+), 6 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 191da84bbf2a1..187014686df3e 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -33,6 +33,10 @@
 #define TDX_SUCCESS		0ULL
 #define TDX_RND_NO_ENTROPY	0x8000020300000000ULL
 
+/* Bit definitions of TDX_FEATURES0 metadata field */
+#define TDX_FEATURES0_NO_RBP_MOD		BIT_ULL(18)
+#define TDX_FEATURES0_DYNAMIC_PAMT		BIT_ULL(36)
+
 #ifndef __ASSEMBLER__
 
 #include <uapi/asm/mce.h>
@@ -152,7 +156,12 @@ const struct tdx_sys_info *tdx_get_sysinfo(void);
 
 static inline bool tdx_supports_dynamic_pamt(const struct tdx_sys_info *sysinfo)
 {
-	return false; /* To be enabled when kernel is ready */
+	/*
+	 * The TDX Module's internal Dynamic PAMT tree structure can't
+	 * handle physical addresses with more than 48 bits.
+	 */
+	return sysinfo->features.tdx_features0 & TDX_FEATURES0_DYNAMIC_PAMT &&
+	       boot_cpu_data.x86_phys_bits <= 48;
 }
 
 /* Simple structure for pre-allocating Dynamic PAMT pages outside of locks. */
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 3544794fb092a..75140511571bf 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1028,8 +1028,9 @@ static __init int construct_tdmrs(struct list_head *tmb_list,
 	return ret;
 }
 
-static __init int config_tdx_module(struct tdmr_info_list *tdmr_list,
-				    u64 global_keyid)
+#define TDX_SYS_CONFIG_DYNAMIC_PAMT	BIT(16)
+
+static __init int config_tdx_module(struct tdmr_info_list *tdmr_list, u64 global_keyid)
 {
 	struct tdx_module_args args = {};
 	u64 *tdmr_pa_array;
@@ -1056,6 +1057,12 @@ static __init int config_tdx_module(struct tdmr_info_list *tdmr_list,
 	args.rcx = __pa(tdmr_pa_array);
 	args.rdx = tdmr_list->nr_consumed_tdmrs;
 	args.r8 = global_keyid;
+
+	if (tdx_supports_dynamic_pamt(&tdx_sysinfo)) {
+		pr_info("Enable Dynamic PAMT\n");
+		args.r8 |= TDX_SYS_CONFIG_DYNAMIC_PAMT;
+	}
+
 	ret = seamcall_prerr(TDH_SYS_CONFIG, &args);
 
 	/* Free the array as it is not required anymore. */
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 8c39dde347cc2..68a68468fbeb6 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -86,9 +86,6 @@ struct tdmr_info {
 	DECLARE_FLEX_ARRAY(struct tdmr_reserved_area, reserved_areas);
 } __packed __aligned(TDMR_INFO_ALIGNMENT);
 
-/* Bit definitions of TDX_FEATURES0 metadata field */
-#define TDX_FEATURES0_NO_RBP_MOD	BIT(18)
-
 /*
  * Do not put any hardware-defined TDX structure representations below
  * this comment!

---

## [12] Rick Edgecombe — 2026-05-25
*Subject: [PATCH v6 11/11] Documentation/x86: Add documentation for TDX's Dynamic PAMT*

From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>

Expand TDX documentation to include information on the Dynamic PAMT
feature.

The new section explains PAMT support in the TDX module and how Dynamic
PAMT affects the kernel memory use.

Assisted-by: Sashiko:claude-opus-4-6 GitHub Copilot:claude-opus-4-6 Claude:claude-opus-4-7
Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Co-developed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
---
v6:
 - Add missing word (Binbin)
 - Use "::" instead of ":"
 - Make format of dmesg example accurate

v3:
 - Trim down docs to be about things that user cares about, instead
   of development history and other details like this.
---
 Documentation/arch/x86/tdx.rst | 22 ++++++++++++++++++++++
 1 file changed, 22 insertions(+)

diff --git a/Documentation/arch/x86/tdx.rst b/Documentation/arch/x86/tdx.rst
index ff6b110291bc6..ce026a88b6f78 100644
--- a/Documentation/arch/x86/tdx.rst
+++ b/Documentation/arch/x86/tdx.rst
@@ -73,6 +73,28 @@ initialize::
 
   [..] virt/tdx: TDX-Module initialization failed ...
 
+Dynamic PAMT
+------------
+
+PAMT is memory that the TDX module needs to keep data about each page
+(think like struct page). It needs to be handed to the TDX module for its
+exclusive use. For normal PAMT, this is installed when the TDX module
+is first loaded and comes to about 0.4% of system memory.
+
+Dynamic PAMT is a TDX feature that allows VMM to allocate part of the
+PAMT as needed (the parts for tracking 4KB size pages). The other page
+sizes (1GB and 2MB) are still allocated statically at the time of
+TDX module initialization. This reduces the amount of memory that TDX
+uses while TDs are not in use.
+
+When Dynamic PAMT is in use, dmesg shows it like::
+
+  [..] virt/tdx: Enable Dynamic PAMT
+  [..] virt/tdx: 10092 KB allocated for PAMT
+  [..] virt/tdx: TDX-Module initialized
+
+Dynamic PAMT is enabled automatically if supported.
+
 TDX Interaction to Other Kernel Components
 ------------------------------------------

---

## [13] Chao Gao — 2026-05-26
*Subject: Re: [PATCH v6 06/11] x86/virt/tdx: Optimize tdx_pamt_get/put()*

On Mon, May 25, 2026 at 07:35:10PM -0700, Rick Edgecombe wrote:
>@@ -2057,32 +2057,50 @@ static int tdx_pamt_get(kvm_pfn_t pfn)
> 	if (!tdx_supports_dynamic_pamt(&tdx_sysinfo))

This converts the scoped_guard() added by the previous patch to
explicit lock/unlock and goto. It would reduce code churn if the
previous patch used that form directly.

>-		/*
>-		 * If the pamt page is already added (i.e. refcount >= 1),

Ditto

>+	/*
>+	 * If there is more than 1 reference on the pamt page, don't

---

## [14] Edgecombe, Rick P — 2026-05-26
*Subject: Re: [PATCH v6 06/11] x86/virt/tdx: Optimize tdx_pamt_get/put()*

On Tue, 2026-05-26 at 16:57 +0800, Chao Gao wrote:
> > -	scoped_guard(spinlock, &pamt_lock) {
> 

Yea, it's a good point. I actually debated doing it, but decided not to because
the scoped version is cleaner for the non-optimized version. But for
reviewability, never doing the scoped version is probably better.

---
