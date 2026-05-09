---
title: 'Enforce host page-size alignment for shared buffers'
date: 2025-12-21
last_reply: 2026-03-11
message_count: 18
participants: ['Aneesh Kumar K.V (Arm)', 'Suzuki K Poulose', 'Steven Price', 'Jason Gunthorpe', 'Mostafa Saleh']
---

## [1] Aneesh Kumar K.V (Arm) — 2025-12-21

Hi all,

This patch series addresses alignment requirements for buffers shared between
private-memory guests and the host.

When running private-memory guests, the guest kernel must apply additional
constraints when allocating buffers that are shared with the hypervisor. These
shared buffers are also accessed by the host kernel and therefore must be
aligned to the host’s page size.

Architectures such as Arm can tolerate realm physical address space PFNs being
mapped as shared memory, as incorrect accesses are detected and reported as GPC
faults. However, relying on this mechanism alone is unsafe and can still lead to
kernel crashes.

This is particularly likely when guest_memfd allocations are mmapped and
accessed from userspace. Once exposed to userspace, it is not possible to
guarantee that applications will only access the intended 4K shared region
rather than the full 64K page mapped into their address space. Such userspace
addresses may also be passed back into the kernel and accessed via the linear
map, potentially resulting in a GPC fault and a kernel crash.

To address this, the series introduces a new helper, `mem_encrypt_align()`,
which allows callers to enforce the required alignment for shared buffers.

The series is based on:
https://gitlab.arm.com/linux-arm/linux-cca.git cca/topics/cca-tdisp-integration-v2

It includes both arm64 guest and host changes to demonstrate a sample
implementation of `mem_encrypt_align()`, with the goal of making the intent and
usage clear for review.

I also included a fix for direct dma remapped coherent allocations related
memory encryption becuse it is also touching the same area. Based on feedback
here I will split that as a separate patch and can send that out

The series also includes a fix for direct DMA remapped allocations related to
memory encryption, as it touches the same code paths. Based on feedback, I can
split this fix into a separate patch and send it out independently.

Feedback and suggestions are welcome.

Changes from v1:
* Rename the helper to mem_encrypt_align
* Improve the commit message
* Handle DMA allocations from contiguous memory
* Handle DMA allocations from the pool
* swiotlb is still considered unencrypted. Support for an encrypted swiotlb pool
  is left as TODO and is independent of this series.

Aneesh Kumar K.V (Arm) (4):
  swiotlb: dma: its: Enforce host page-size alignment for shared buffers
  coco: guest: arm64: Fetch host IPA change alignment via RHI hostconf
  coco: host: arm64: Handle hostconf RHI calls in kernel
  dma: direct: set decrypted flag for remapped coherent allocations

 arch/arm64/include/asm/mem_encrypt.h |  3 ++
 arch/arm64/include/asm/rhi.h         |  7 ++++
 arch/arm64/include/asm/rsi.h         |  1 +
 arch/arm64/kernel/Makefile           |  2 +-
 arch/arm64/kernel/rhi.c              | 54 ++++++++++++++++++++++++++++
 arch/arm64/kernel/rsi.c              | 13 +++++++
 arch/arm64/kvm/hypercalls.c          | 23 +++++++++++-
 arch/arm64/kvm/rmi.c                 |  4 ---
 arch/arm64/mm/mem_encrypt.c          | 14 ++++++++
 drivers/irqchip/irq-gic-v3-its.c     |  7 ++--
 include/linux/mem_encrypt.h          |  7 ++++
 kernel/dma/contiguous.c              | 10 ++++++
 kernel/dma/direct.c                  | 14 +++++---
 kernel/dma/pool.c                    |  6 ++--
 kernel/dma/swiotlb.c                 | 18 ++++++----
 15 files changed, 161 insertions(+), 22 deletions(-)
 create mode 100644 arch/arm64/kernel/rhi.c

---

## [2] Aneesh Kumar K.V (Arm) — 2025-12-21
*Subject: [PATCH v2 1/4] swiotlb: dma: its: Enforce host page-size alignment for shared buffers*

When running private-memory guests, the guest kernel must apply
additional constraints when allocating buffers that are shared with the
hypervisor.

These shared buffers are also accessed by the host kernel and therefore
must be aligned to the host’s page size.

On non-secure hosts, set_guest_memory_attributes() tracks memory at the
host PAGE_SIZE granularity. This creates a mismatch when the guest
applies attributes at 4K boundaries while the host uses 64K pages. In
such cases, the call returns -EINVAL, preventing the conversion of
memory regions from private to shared.

Architectures such as Arm can tolerate realm physical address space PFNs
being mapped as shared memory, as incorrect accesses are detected and
reported as GPC faults. However, relying on this mechanism is unsafe and
can still lead to kernel crashes.

This is particularly likely when guest_memfd allocations are mmapped and
accessed from userspace. Once exposed to userspace, we cannot guarantee
that applications will only access the intended 4K shared region rather
than the full 64K page mapped into their address space. Such userspace
addresses may also be passed back into the kernel and accessed via the
linear map, resulting in a GPC fault and a kernel crash.

With CCA, although Stage-2 mappings managed by the RMM still operate at
a 4K granularity, shared pages must nonetheless be aligned to the
host-managed page size to avoid the issues described above.

Introduce a new helper, mem_encryp_align(), to allow callers to enforce
the required alignment for shared buffers.

The architecture-specific implementation of mem_encrypt_align() will be
provided in a follow-up patch.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/mem_encrypt.h |  6 ++++++
 arch/arm64/mm/mem_encrypt.c          |  6 ++++++
 drivers/irqchip/irq-gic-v3-its.c     |  7 ++++---
 include/linux/mem_encrypt.h          |  7 +++++++
 kernel/dma/contiguous.c              | 10 ++++++++++
 kernel/dma/direct.c                  |  6 ++++++
 kernel/dma/pool.c                    |  6 ++++--
 kernel/dma/swiotlb.c                 | 18 ++++++++++++------
 8 files changed, 55 insertions(+), 11 deletions(-)

diff --git a/arch/arm64/include/asm/mem_encrypt.h b/arch/arm64/include/asm/mem_encrypt.h
index d77c10cd5b79..b7ac143b81ce 100644
--- a/arch/arm64/include/asm/mem_encrypt.h
+++ b/arch/arm64/include/asm/mem_encrypt.h
@@ -17,6 +17,12 @@ int set_memory_encrypted(unsigned long addr, int numpages);
 int set_memory_decrypted(unsigned long addr, int numpages);
 bool force_dma_unencrypted(struct device *dev);
 
+#define mem_encrypt_align mem_encrypt_align
+static inline size_t mem_encrypt_align(size_t size)
+{
+	return size;
+}
+
 int realm_register_memory_enc_ops(void);
 
 /*
diff --git a/arch/arm64/mm/mem_encrypt.c b/arch/arm64/mm/mem_encrypt.c
index 645c099fd551..deb364eadd47 100644
--- a/arch/arm64/mm/mem_encrypt.c
+++ b/arch/arm64/mm/mem_encrypt.c
@@ -46,6 +46,12 @@ int set_memory_decrypted(unsigned long addr, int numpages)
 	if (likely(!crypt_ops) || WARN_ON(!PAGE_ALIGNED(addr)))
 		return 0;
 
+	if (WARN_ON(!IS_ALIGNED(addr, mem_encrypt_align(PAGE_SIZE))))
+		return 0;
+
+	if (WARN_ON(!IS_ALIGNED(numpages << PAGE_SHIFT, mem_encrypt_align(PAGE_SIZE))))
+		return 0;
+
 	return crypt_ops->decrypt(addr, numpages);
 }
 EXPORT_SYMBOL_GPL(set_memory_decrypted);
diff --git a/drivers/irqchip/irq-gic-v3-its.c b/drivers/irqchip/irq-gic-v3-its.c
index 467cb78435a9..ffb8ef3a1eb3 100644
--- a/drivers/irqchip/irq-gic-v3-its.c
+++ b/drivers/irqchip/irq-gic-v3-its.c
@@ -213,16 +213,17 @@ static gfp_t gfp_flags_quirk;
 static struct page *its_alloc_pages_node(int node, gfp_t gfp,
 					 unsigned int order)
 {
+	unsigned int new_order;
 	struct page *page;
 	int ret = 0;
 
-	page = alloc_pages_node(node, gfp | gfp_flags_quirk, order);
-
+	new_order = get_order(mem_encrypt_align((PAGE_SIZE << order)));
+	page = alloc_pages_node(node, gfp | gfp_flags_quirk, new_order);
 	if (!page)
 		return NULL;
 
 	ret = set_memory_decrypted((unsigned long)page_address(page),
-				   1 << order);
+				   1 << new_order);
 	/*
 	 * If set_memory_decrypted() fails then we don't know what state the
 	 * page is in, so we can't free it. Instead we leak it.
diff --git a/include/linux/mem_encrypt.h b/include/linux/mem_encrypt.h
index 07584c5e36fb..a0b9f6fe5d1a 100644
--- a/include/linux/mem_encrypt.h
+++ b/include/linux/mem_encrypt.h
@@ -54,6 +54,13 @@
 #define dma_addr_canonical(x)		(x)
 #endif
 
+#ifndef mem_encrypt_align
+static inline size_t mem_encrypt_align(size_t size)
+{
+	return size;
+}
+#endif
+
 #endif	/* __ASSEMBLY__ */
 
 #endif	/* __MEM_ENCRYPT_H__ */
diff --git a/kernel/dma/contiguous.c b/kernel/dma/contiguous.c
index d9b9dcba6ff7..35f738c9eee2 100644
--- a/kernel/dma/contiguous.c
+++ b/kernel/dma/contiguous.c
@@ -45,6 +45,7 @@
 #include <linux/dma-map-ops.h>
 #include <linux/cma.h>
 #include <linux/nospec.h>
+#include <linux/dma-direct.h>
 
 #ifdef CONFIG_CMA_SIZE_MBYTES
 #define CMA_SIZE_MBYTES CONFIG_CMA_SIZE_MBYTES
@@ -356,6 +357,15 @@ struct page *dma_alloc_contiguous(struct device *dev, size_t size, gfp_t gfp)
 	int nid = dev_to_node(dev);
 #endif
 
+	/*
+	 * for untrusted device, we require the dma buffers to be aligned to
+	 * the size of allocation. if we can't do that with cma allocation, fail
+	 * cma allocation early.
+	 */
+	if (force_dma_unencrypted(dev))
+		if (get_order(size) > CONFIG_CMA_ALIGNMENT)
+			return NULL;
+
 	/* CMA can be used only in the context which permits sleeping */
 	if (!gfpflags_allow_blocking(gfp))
 		return NULL;
diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index 1f9ee9759426..3448d877c7c6 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -250,6 +250,9 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	    dma_direct_use_pool(dev, gfp))
 		return dma_direct_alloc_from_pool(dev, size, dma_handle, gfp);
 
+	if (force_dma_unencrypted(dev))
+		size = mem_encrypt_align(size);
+
 	/* we always manually zero the memory once we are done */
 	page = __dma_direct_alloc_pages(dev, size, gfp & ~__GFP_ZERO, true);
 	if (!page)
@@ -359,6 +362,9 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 	if (force_dma_unencrypted(dev) && dma_direct_use_pool(dev, gfp))
 		return dma_direct_alloc_from_pool(dev, size, dma_handle, gfp);
 
+	if (force_dma_unencrypted(dev))
+		size = mem_encrypt_align(size);
+
 	page = __dma_direct_alloc_pages(dev, size, gfp, false);
 	if (!page)
 		return NULL;
diff --git a/kernel/dma/pool.c b/kernel/dma/pool.c
index ee45dee33d49..86615e088240 100644
--- a/kernel/dma/pool.c
+++ b/kernel/dma/pool.c
@@ -80,12 +80,13 @@ static int atomic_pool_expand(struct gen_pool *pool, size_t pool_size,
 			      gfp_t gfp)
 {
 	unsigned int order;
+	unsigned int min_encrypt_order = get_order(mem_encrypt_align(PAGE_SIZE));
 	struct page *page = NULL;
 	void *addr;
 	int ret = -ENOMEM;
 
 	/* Cannot allocate larger than MAX_PAGE_ORDER */
-	order = min(get_order(pool_size), MAX_PAGE_ORDER);
+	order = min(get_order(mem_encrypt_align(pool_size)), MAX_PAGE_ORDER);
 
 	do {
 		pool_size = 1 << (PAGE_SHIFT + order);
@@ -94,7 +95,7 @@ static int atomic_pool_expand(struct gen_pool *pool, size_t pool_size,
 							 order, false);
 		if (!page)
 			page = alloc_pages(gfp, order);
-	} while (!page && order-- > 0);
+	} while (!page && order-- > min_encrypt_order);
 	if (!page)
 		goto out;
 
@@ -196,6 +197,7 @@ static int __init dma_atomic_pool_init(void)
 		unsigned long pages = totalram_pages() / (SZ_1G / SZ_128K);
 		pages = min_t(unsigned long, pages, MAX_ORDER_NR_PAGES);
 		atomic_pool_size = max_t(size_t, pages << PAGE_SHIFT, SZ_128K);
+		WARN_ON(!IS_ALIGNED(atomic_pool_size, mem_encrypt_align(PAGE_SIZE)));
 	}
 	INIT_WORK(&atomic_pool_work, atomic_pool_work_fn);
 
diff --git a/kernel/dma/swiotlb.c b/kernel/dma/swiotlb.c
index 0d37da3d95b6..db53dc7bff6a 100644
--- a/kernel/dma/swiotlb.c
+++ b/kernel/dma/swiotlb.c
@@ -319,8 +319,8 @@ static void __init *swiotlb_memblock_alloc(unsigned long nslabs,
 		unsigned int flags,
 		int (*remap)(void *tlb, unsigned long nslabs))
 {
-	size_t bytes = PAGE_ALIGN(nslabs << IO_TLB_SHIFT);
 	void *tlb;
+	size_t bytes = mem_encrypt_align(nslabs << IO_TLB_SHIFT);
 
 	/*
 	 * By default allocate the bounce buffer memory from low memory, but
@@ -328,9 +328,9 @@ static void __init *swiotlb_memblock_alloc(unsigned long nslabs,
 	 * memory encryption.
 	 */
 	if (flags & SWIOTLB_ANY)
-		tlb = memblock_alloc(bytes, PAGE_SIZE);
+		tlb = memblock_alloc(bytes, mem_encrypt_align(PAGE_SIZE));
 	else
-		tlb = memblock_alloc_low(bytes, PAGE_SIZE);
+		tlb = memblock_alloc_low(bytes, mem_encrypt_align(PAGE_SIZE));
 
 	if (!tlb) {
 		pr_warn("%s: Failed to allocate %zu bytes tlb structure\n",
@@ -339,7 +339,7 @@ static void __init *swiotlb_memblock_alloc(unsigned long nslabs,
 	}
 
 	if (remap && remap(tlb, nslabs) < 0) {
-		memblock_free(tlb, PAGE_ALIGN(bytes));
+		memblock_free(tlb, bytes);
 		pr_warn("%s: Failed to remap %zu bytes\n", __func__, bytes);
 		return NULL;
 	}
@@ -461,15 +461,21 @@ int swiotlb_init_late(size_t size, gfp_t gfp_mask,
 		swiotlb_adjust_nareas(num_possible_cpus());
 
 retry:
-	order = get_order(nslabs << IO_TLB_SHIFT);
+	order = get_order(mem_encrypt_align(nslabs << IO_TLB_SHIFT));
 	nslabs = SLABS_PER_PAGE << order;
 
+	WARN_ON(!IS_ALIGNED(order << PAGE_SHIFT, mem_encrypt_align(PAGE_SIZE)));
+	WARN_ON(!IS_ALIGNED(default_nslabs << IO_TLB_SHIFT, mem_encrypt_align(PAGE_SIZE)));
+	WARN_ON(!IS_ALIGNED(IO_TLB_MIN_SLABS << IO_TLB_SHIFT, mem_encrypt_align(PAGE_SIZE)));
+
 	while ((SLABS_PER_PAGE << order) > IO_TLB_MIN_SLABS) {
 		vstart = (void *)__get_free_pages(gfp_mask | __GFP_NOWARN,
 						  order);
 		if (vstart)
 			break;
 		order--;
+		if (order < get_order(mem_encrypt_align(PAGE_SIZE)))
+			break;
 		nslabs = SLABS_PER_PAGE << order;
 		retried = true;
 	}
@@ -573,7 +579,7 @@ void __init swiotlb_exit(void)
  */
 static struct page *alloc_dma_pages(gfp_t gfp, size_t bytes, u64 phys_limit)
 {
-	unsigned int order = get_order(bytes);
+	unsigned int order = get_order(mem_encrypt_align(bytes));
 	struct page *page;
 	phys_addr_t paddr;
 	void *vaddr;

---

## [3] Aneesh Kumar K.V (Arm) — 2025-12-21
*Subject: [PATCH v2 2/4] coco: guest: arm64: Fetch host IPA change alignment via RHI hostconf*

- add RHI hostconf SMC IDs and helper to query version, features, and IPA change alignment
 - derive the realm hypervisor page size during init and abort realm setup on invalid alignment
 - make `mem_encrypt_align()` realign to the host page size for realm guests and export the helper

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/include/asm/mem_encrypt.h |  5 +--
 arch/arm64/include/asm/rhi.h         |  7 ++++
 arch/arm64/include/asm/rsi.h         |  1 +
 arch/arm64/kernel/Makefile           |  2 +-
 arch/arm64/kernel/rhi.c              | 54 ++++++++++++++++++++++++++++
 arch/arm64/kernel/rsi.c              | 13 +++++++
 arch/arm64/mm/mem_encrypt.c          |  8 +++++
 7 files changed, 85 insertions(+), 5 deletions(-)
 create mode 100644 arch/arm64/kernel/rhi.c

diff --git a/arch/arm64/include/asm/mem_encrypt.h b/arch/arm64/include/asm/mem_encrypt.h
index b7ac143b81ce..06d3c30159a2 100644
--- a/arch/arm64/include/asm/mem_encrypt.h
+++ b/arch/arm64/include/asm/mem_encrypt.h
@@ -18,10 +18,7 @@ int set_memory_decrypted(unsigned long addr, int numpages);
 bool force_dma_unencrypted(struct device *dev);
 
 #define mem_encrypt_align mem_encrypt_align
-static inline size_t mem_encrypt_align(size_t size)
-{
-	return size;
-}
+size_t mem_encrypt_align(size_t size);
 
 int realm_register_memory_enc_ops(void);
 
diff --git a/arch/arm64/include/asm/rhi.h b/arch/arm64/include/asm/rhi.h
index a4f56f536876..414d9eab7f65 100644
--- a/arch/arm64/include/asm/rhi.h
+++ b/arch/arm64/include/asm/rhi.h
@@ -86,4 +86,11 @@ enum rhi_tdi_state {
 #define __REC_EXIT_DA_VDEV_MAP		0x6
 #define __RHI_DA_VDEV_SET_TDI_STATE	0x7
 
+unsigned long rhi_get_ipa_change_alignment(void);
+#define RHI_HOSTCONF_VER_1_0		0x10000
+#define RHI_HOSTCONF_VERSION		SMC_RHI_CALL(0x004E)
+
+#define __RHI_HOSTCONF_GET_IPA_CHANGE_ALIGNMENT BIT(0)
+#define RHI_HOSTCONF_FEATURES		SMC_RHI_CALL(0x004F)
+#define RHI_HOSTCONF_GET_IPA_CHANGE_ALIGNMENT	SMC_RHI_CALL(0x0050)
 #endif
diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h
index c197bcc50239..2781d89827eb 100644
--- a/arch/arm64/include/asm/rsi.h
+++ b/arch/arm64/include/asm/rsi.h
@@ -79,5 +79,6 @@ static inline int rsi_set_memory_range_shared(phys_addr_t start,
 }
 
 bool rsi_has_da_feature(void);
+unsigned long realm_get_hyp_pagesize(void);
 
 #endif /* __ASM_RSI_H_ */
diff --git a/arch/arm64/kernel/Makefile b/arch/arm64/kernel/Makefile
index 76f32e424065..fcb67f50ea89 100644
--- a/arch/arm64/kernel/Makefile
+++ b/arch/arm64/kernel/Makefile
@@ -34,7 +34,7 @@ obj-y			:= debug-monitors.o entry.o irq.o fpsimd.o		\
 			   cpufeature.o alternative.o cacheinfo.o		\
 			   smp.o smp_spin_table.o topology.o smccc-call.o	\
 			   syscall.o proton-pack.o idle.o patching.o pi/	\
-			   rsi.o jump_label.o
+			   rsi.o jump_label.o rhi.o
 
 obj-$(CONFIG_COMPAT)			+= sys32.o signal32.o			\
 					   sys_compat.o
diff --git a/arch/arm64/kernel/rhi.c b/arch/arm64/kernel/rhi.c
new file mode 100644
index 000000000000..63360ed392e4
--- /dev/null
+++ b/arch/arm64/kernel/rhi.c
@@ -0,0 +1,54 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/*
+ * Copyright (C) 2025 ARM Ltd.
+ */
+
+#include <asm/rsi.h>
+#include <asm/rhi.h>
+
+/* we need an aligned rhicall for rsi_host_call. slab is not yet ready */
+static struct rsi_host_call hyp_pagesize_rhicall;
+unsigned long rhi_get_ipa_change_alignment(void)
+{
+	long ret;
+	unsigned long ipa_change_align;
+
+	hyp_pagesize_rhicall.imm = 0;
+	hyp_pagesize_rhicall.gprs[0] = RHI_HOSTCONF_VERSION;
+	ret = rsi_host_call(&hyp_pagesize_rhicall);
+	if (ret != RSI_SUCCESS)
+		goto err_out;
+
+	if (hyp_pagesize_rhicall.gprs[0] != RHI_HOSTCONF_VER_1_0)
+		goto err_out;
+
+	hyp_pagesize_rhicall.imm = 0;
+	hyp_pagesize_rhicall.gprs[0] = RHI_HOSTCONF_FEATURES;
+	ret = rsi_host_call(&hyp_pagesize_rhicall);
+	if (ret != RSI_SUCCESS)
+		goto err_out;
+
+	if (!(hyp_pagesize_rhicall.gprs[0] & __RHI_HOSTCONF_GET_IPA_CHANGE_ALIGNMENT))
+		goto err_out;
+
+	hyp_pagesize_rhicall.imm = 0;
+	hyp_pagesize_rhicall.gprs[0] = RHI_HOSTCONF_GET_IPA_CHANGE_ALIGNMENT;
+	ret = rsi_host_call(&hyp_pagesize_rhicall);
+	if (ret != RSI_SUCCESS)
+		goto err_out;
+
+	ipa_change_align = hyp_pagesize_rhicall.gprs[0];
+	/* This error needs special handling in the caller */
+	if (ipa_change_align & (SZ_4K - 1))
+		return 0;
+
+	return ipa_change_align;
+
+err_out:
+	/*
+	 * For failure condition assume host is built with 4K page size
+	 * and hence ipa change alignment can be guest PAGE_SIZE.
+	 */
+	return PAGE_SIZE;
+}
+
diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index aae24009cadb..57de4103be03 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -13,9 +13,12 @@
 #include <asm/io.h>
 #include <asm/mem_encrypt.h>
 #include <asm/rsi.h>
+#include <asm/rhi.h>
 
 static struct realm_config config;
 static u64 rsi_feat_reg0;
+static unsigned long ipa_change_alignment = PAGE_SIZE;
+
 
 unsigned long prot_ns_shared;
 EXPORT_SYMBOL(prot_ns_shared);
@@ -147,6 +150,11 @@ static int realm_ioremap_hook(phys_addr_t phys, size_t size, pgprot_t *prot)
 	return 0;
 }
 
+unsigned long realm_get_hyp_pagesize(void)
+{
+	return ipa_change_alignment;
+}
+
 void __init arm64_rsi_init(void)
 {
 	static_branch_enable(&rsi_init_call_done);
@@ -158,6 +166,11 @@ void __init arm64_rsi_init(void)
 	if (WARN_ON(rsi_get_realm_config(&config)))
 		return;
 
+	ipa_change_alignment = rhi_get_ipa_change_alignment();
+	/* If we don't get a correct alignment response, don't enable realm */
+	if (!ipa_change_alignment)
+		return;
+
 	if (WARN_ON(rsi_features(0, &rsi_feat_reg0)))
 		return;
 
diff --git a/arch/arm64/mm/mem_encrypt.c b/arch/arm64/mm/mem_encrypt.c
index deb364eadd47..6937f753e89d 100644
--- a/arch/arm64/mm/mem_encrypt.c
+++ b/arch/arm64/mm/mem_encrypt.c
@@ -64,3 +64,11 @@ bool force_dma_unencrypted(struct device *dev)
 	return is_realm_world();
 }
 EXPORT_SYMBOL_GPL(force_dma_unencrypted);
+
+size_t mem_encrypt_align(size_t size)
+{
+	if (is_realm_world())
+		return ALIGN(size, realm_get_hyp_pagesize());
+	return size;
+}
+EXPORT_SYMBOL_GPL(mem_encrypt_align);

---

## [4] Aneesh Kumar K.V (Arm) — 2025-12-21
*Subject: [PATCH v2 3/4] coco: host: arm64: Handle hostconf RHI calls in kernel*

- Mark hostconf RHI SMC IDs as handled in the SMCCC filter.
 - Return version/features plus PAGE_SIZE alignment for guest queries.
 - Drop the 4K page-size guard in RMI init now that realm can query IPA
   change alignment size via the hostconf RHI

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 arch/arm64/kvm/hypercalls.c | 23 ++++++++++++++++++++++-
 arch/arm64/kvm/rmi.c        |  4 ----
 2 files changed, 22 insertions(+), 5 deletions(-)

diff --git a/arch/arm64/kvm/hypercalls.c b/arch/arm64/kvm/hypercalls.c
index 70ac7971416c..2861ca9063dd 100644
--- a/arch/arm64/kvm/hypercalls.c
+++ b/arch/arm64/kvm/hypercalls.c
@@ -8,6 +8,7 @@
 
 #include <kvm/arm_hypercalls.h>
 #include <kvm/arm_psci.h>
+#include <asm/rhi.h>
 
 #define KVM_ARM_SMCCC_STD_FEATURES				\
 	GENMASK(KVM_REG_ARM_STD_BMAP_BIT_COUNT - 1, 0)
@@ -77,6 +78,9 @@ static bool kvm_smccc_default_allowed(u32 func_id)
 	 */
 	case ARM_SMCCC_VERSION_FUNC_ID:
 	case ARM_SMCCC_ARCH_FEATURES_FUNC_ID:
+	case RHI_HOSTCONF_VERSION:
+	case RHI_HOSTCONF_FEATURES:
+	case RHI_HOSTCONF_GET_IPA_CHANGE_ALIGNMENT:
 		return true;
 	default:
 		/* PSCI 0.2 and up is in the 0:0x1f range */
@@ -157,7 +161,15 @@ static int kvm_smccc_filter_insert_reserved(struct kvm *kvm)
 			       GFP_KERNEL_ACCOUNT);
 	if (r)
 		goto out_destroy;
-
+	/*
+	 * Don't forward RHI_HOST_CONF related RHI calls
+	 */
+	r = mtree_insert_range(&kvm->arch.smccc_filter,
+			       RHI_HOSTCONF_VERSION, RHI_HOSTCONF_GET_IPA_CHANGE_ALIGNMENT,
+			       xa_mk_value(KVM_SMCCC_FILTER_HANDLE),
+			       GFP_KERNEL_ACCOUNT);
+	if (r)
+		goto out_destroy;
 	return 0;
 out_destroy:
 	mtree_destroy(&kvm->arch.smccc_filter);
@@ -376,6 +388,15 @@ int kvm_smccc_call_handler(struct kvm_vcpu *vcpu)
 	case ARM_SMCCC_TRNG_RND32:
 	case ARM_SMCCC_TRNG_RND64:
 		return kvm_trng_call(vcpu);
+	case RHI_HOSTCONF_VERSION:
+		val[0] = RHI_HOSTCONF_VER_1_0;
+		break;
+	case RHI_HOSTCONF_FEATURES:
+		val[0] = __RHI_HOSTCONF_GET_IPA_CHANGE_ALIGNMENT;
+		break;
+	case RHI_HOSTCONF_GET_IPA_CHANGE_ALIGNMENT:
+		val[0] = PAGE_SIZE;
+		break;
 	default:
 		return kvm_psci_call(vcpu);
 	}
diff --git a/arch/arm64/kvm/rmi.c b/arch/arm64/kvm/rmi.c
index 9957a71d21b1..bd345e051a24 100644
--- a/arch/arm64/kvm/rmi.c
+++ b/arch/arm64/kvm/rmi.c
@@ -1935,10 +1935,6 @@ EXPORT_SYMBOL_GPL(kvm_has_da_feature);
 
 void kvm_init_rmi(void)
 {
-	/* Only 4k page size on the host is supported */
-	if (PAGE_SIZE != SZ_4K)
-		return;
-
 	/* Continue without realm support if we can't agree on a version */
 	if (rmi_check_version())
 		return;

---

## [5] Aneesh Kumar K.V (Arm) — 2025-12-21
*Subject: [PATCH v2 4/4] dma: direct: set decrypted flag for remapped dma allocations*

Devices that are DMA non-coherent and need a remap were skipping
dma_set_decrypted(), leaving buffers encrypted even when the device
requires unencrypted access. Move the call after the remap
branch so both paths mark the allocation decrypted (or fail cleanly)
before use.

Fixes: f3c962226dbe ("dma-direct: clean up the remapping checks in dma_direct_alloc")
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 kernel/dma/direct.c | 8 +++-----
 1 file changed, 3 insertions(+), 5 deletions(-)

diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index 3448d877c7c6..a62dc25524cc 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -271,9 +271,6 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	if (remap) {
 		pgprot_t prot = dma_pgprot(dev, PAGE_KERNEL, attrs);
 
-		if (force_dma_unencrypted(dev))
-			prot = pgprot_decrypted(prot);
-
 		/* remove any dirty cache lines on the kernel alias */
 		arch_dma_prep_coherent(page, size);
 
@@ -284,10 +281,11 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 			goto out_free_pages;
 	} else {
 		ret = page_address(page);
-		if (dma_set_decrypted(dev, ret, size))
-			goto out_leak_pages;
 	}
 
+	if (dma_set_decrypted(dev, ret, size))
+		goto out_leak_pages;
+
 	memset(ret, 0, size);
 
 	if (set_uncached) {

---

## [6] Suzuki K Poulose — 2025-12-21
*Subject: Re: [PATCH v2 3/4] coco: host: arm64: Handle hostconf RHI calls in
 kernel*

On 21/12/2025 16:09, Aneesh Kumar K.V (Arm) wrote:
>   - Mark hostconf RHI SMC IDs as handled in the SMCCC filter.
>   - Return version/features plus PAGE_SIZE alignment for guest queries.

minor nit: this is needed only for the Realms ?

> +	if (r)
> +		goto out_destroy;

For the record, these patches doesn't necessarily solve the Host support
fully. The KVM still needs to support splitting pages for RMM's 4K.

That said, this can be ignored as we rebase the KVM to only support
RMM v2.0, where the Host can set the RMM's Stage2 page size.

Suzuki

> -
>   	/* Continue without realm support if we can't agree on a version */

---

## [7] Aneesh Kumar K.V — 2025-12-22
*Subject: Re: [PATCH v2 3/4] coco: host: arm64: Handle hostconf RHI calls in
 kernel*

Suzuki K Poulose <suzuki.poulose@arm.com> writes:

> On 21/12/2025 16:09, Aneesh Kumar K.V (Arm) wrote:
>>   - Mark hostconf RHI SMC IDs as handled in the SMCCC filter.


That is the kvm forwarding of the RHI hostcalls to VMM. We are updating
smccc filter that the SMCCC FID range [RHI_HOSTCONF_VERSION, RHI_HOSTCONF_GET_IPA_CHANGE_ALIGNMENT]
will be handled by the kernel. This is needed because it is the kernel
that is dropping the below check in kvm_init_rmi().

 	/* Only 4k page size on the host is supported */
	if (PAGE_SIZE != SZ_4K)
 		return;

We want to make sure RHI support and dropping of the above check happens
in the same patch and is part of the kernel. 

>
>> +	if (r)

We already delegate RMM granules and setup stage 2 in rmm with
RMM_PAGE_SIZE. ie, the shared patchset can be used to setup a 64K host
with 4K Realm running on a RMM using 4K RMM granule size.

>
> That said, this can be ignored as we rebase the KVM to only support

-aneesh

---

## [8] Steven Price — 2025-12-22
*Subject: Re: [PATCH v2 1/4] swiotlb: dma: its: Enforce host page-size
 alignment for shared buffers*

On 21/12/2025 16:09, Aneesh Kumar K.V (Arm) wrote:
> When running private-memory guests, the guest kernel must apply
> additional constraints when allocating buffers that are shared with the

Don't you also need to update its_free_pages() in a similar manner so
that the set_memory_encrypted()/free_pages() calls are done with the
same order argument?

Thanks,
Steve

> diff --git a/include/linux/mem_encrypt.h b/include/linux/mem_encrypt.h
> index 07584c5e36fb..a0b9f6fe5d1a 100644

---

## [9] Suzuki K Poulose — 2025-12-22
*Subject: Re: [PATCH v2 4/4] dma: direct: set decrypted flag for remapped dma
 allocations*

On 21/12/2025 16:09, Aneesh Kumar K.V (Arm) wrote:
> Devices that are DMA non-coherent and need a remap were skipping
> dma_set_decrypted(), leaving buffers encrypted even when the device

This would be problematic, isn't it ? We don't support decrypted on a
vmap area for arm64. If we move this down, we might actually use the
vmapped area. Not sure if other archs are fine with "decrypting" a
"vmap" address.

If we map the "vmap" address with pgprot_decrypted, we could go ahead
and further map the linear map (i.e., page_address(page)) decrypted
and get everything working.

Suzuki


> -
>   		/* remove any dirty cache lines on the kernel alias */

---

## [10] Aneesh Kumar K.V — 2025-12-22
*Subject: Re: [PATCH v2 1/4] swiotlb: dma: its: Enforce host page-size
 alignment for shared buffers*

Steven Price <steven.price@arm.com> writes:

> On 21/12/2025 16:09, Aneesh Kumar K.V (Arm) wrote:
>> When running private-memory guests, the guest kernel must apply

Yes, agreed — good point. The free path needs to mirror the allocation
path, so its_free_pages() should use the same order when calling
set_memory_encrypted()/decrypted() and free_pages(). I’ll update it
accordingly to keep the behavior symmetric and consistent. I also
noticed that swiotlb also need similar change.

-aneesh

---

## [11] Aneesh Kumar K.V — 2025-12-23
*Subject: Re: [PATCH v2 4/4] dma: direct: set decrypted flag for remapped dma
 allocations*

Suzuki K Poulose <suzuki.poulose@arm.com> writes:

> On 21/12/2025 16:09, Aneesh Kumar K.V (Arm) wrote:
>> Devices that are DMA non-coherent and need a remap were skipping

We still have the problem w.r.t free

dma_direct_free():

	if (is_vmalloc_addr(cpu_addr)) {
		vunmap(cpu_addr);
	} else {
		if (dma_set_encrypted(dev, cpu_addr, size))
			return;
	}

-aneesh

---

## [12] Suzuki K Poulose — 2025-12-23
*Subject: Re: [PATCH v2 3/4] coco: host: arm64: Handle hostconf RHI calls in
 kernel*

On 22/12/2025 14:37, Aneesh Kumar K.V wrote:
> Suzuki K Poulose <suzuki.poulose@arm.com> writes:
> 

I don't see why that is related to kvm_init_rmi(). My point is,
for non-CCA VMs, RHI_HOST_* are not expected. And given this
filtering is per KVM, we could skip this step for !kvm_is_realm(kvm).



> 
>   	/* Only 4k page size on the host is supported */


Not necessarily, the guest won't run without the above changes. So, all 
your RHI host changes can go in and the final step can be the above
change.(similar to what we do for "enable a Kconfig" once we have put
in all the infrastructure for the feature).

Suzuki

> 
>>

Do you mean the branch that you are basing these changes on ? I thought
we dropped most of those changes from the KVM support. Yes, there are
some left overs from the changes, but we can't run with 64K yet.

> with 4K Realm running on a RMM using 4K RMM granule size.
>

---

## [13] Aneesh Kumar K.V — 2025-12-26
*Subject: Re: [PATCH v2 4/4] dma: direct: set decrypted flag for remapped dma
 allocations*

Aneesh Kumar K.V <aneesh.kumar@kernel.org> writes:

> Suzuki K Poulose <suzuki.poulose@arm.com> writes:
>

How about the below change? 

commit 8261c528961c6959b85de87c5659ce9081dc85b7
Author: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
Date:   Fri Dec 19 14:46:20 2025 +0530

    dma: direct: set decrypted flag for remapped DMA allocations
    
    Devices that are DMA non-coherent and require a remap were skipping
    dma_set_decrypted(), leaving DMA buffers encrypted even when the device
    requires unencrypted access. Move the call after the if (remap) branch
    so that both direct and remapped allocation paths correctly mark the
    allocation as decrypted (or fail cleanly) before use.
    
    If CMA allocations return highmem pages, treat this as an allocation
    error so that dma_direct_alloc() falls back to the standard allocation
    path. This is required because some architectures (e.g. arm64) cannot
    mark vmap addresses as decrypted, and highmem pages necessarily require
    a vmap remap. As a result, such allocations cannot be safely marked
    unencrypted for DMA.
    
    Other architectures (e.g. x86) do not have this limitation, but instead
    of making this architecture-specific, I have made the restriction apply
    when the device requires unencrypted DMA access. This was done for
    simplicity,
    
    Fixes: f3c962226dbe ("dma-direct: clean up the remapping checks in dma_direct_alloc")
    Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>

diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index 7c0b55ca121f..811de37ad81c 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -264,6 +264,15 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 	 * remapped to return a kernel virtual address.
 	 */
 	if (PageHighMem(page)) {
+		/*
+		 * Unencrypted/shared DMA requires a linear-mapped buffer
+		 * address to look up the PFN and set architecture-required PFN
+		 * attributes. This is not possible with HighMem, so return
+		 * failure.
+		 */
+		if (force_dma_unencrypted(dev))
+			goto out_free_pages;
+
 		remap = true;
 		set_uncached = false;
 	}
@@ -284,7 +293,13 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 			goto out_free_pages;
 	} else {
 		ret = page_address(page);
-		if (dma_set_decrypted(dev, ret, size))
+	}
+
+	if (force_dma_unencrypted(dev)) {
+		void *lm_addr;
+
+		lm_addr = page_address(page);
+		if (set_memory_decrypted((unsigned long)lm_addr, PFN_UP(size)))
 			goto out_leak_pages;
 	}
 
@@ -349,8 +364,16 @@ void dma_direct_free(struct device *dev, size_t size,
 	} else {
 		if (IS_ENABLED(CONFIG_ARCH_HAS_DMA_CLEAR_UNCACHED))
 			arch_dma_clear_uncached(cpu_addr, size);
-		if (dma_set_encrypted(dev, cpu_addr, size))
+	}
+
+	if (force_dma_unencrypted(dev)) {
+		void *lm_addr;
+
+		lm_addr = phys_to_virt(dma_to_phys(dev, dma_addr));
+		if (set_memory_encrypted((unsigned long)lm_addr, PFN_UP(size))) {
+			pr_warn_ratelimited("leaking DMA memory that can't be re-encrypted\n");
 			return;
+		}
 	}
 
 	__dma_direct_free_pages(dev, dma_direct_to_page(dev, dma_addr), size);

---

## [14] Jason Gunthorpe — 2026-01-05
*Subject: Re: [PATCH v2 0/4] Enforce host page-size alignment for shared
 buffers*

On Sun, Dec 21, 2025 at 09:39:16PM +0530, Aneesh Kumar K.V (Arm) wrote:
> Hi all,
> 

This explanation makes sense, but to maybe bottom line the requirement
to something very simple..

 In ARM64 the guest shared/private granule size must be >= the
 hypervisor PAGE_SIZE, which may be larger than the VM's natural
 PAGE_SIZE.

Meaning we have to go through an change all the places doing
shared/private stuff to work on a shared/private granual size. I think
this is not just alignment, but allocation size as well?

Jason

---

## [15] Jason Gunthorpe — 2026-01-05
*Subject: Re: [PATCH v2 1/4] swiotlb: dma: its: Enforce host page-size
 alignment for shared buffers*

On Sun, Dec 21, 2025 at 09:39:17PM +0530, Aneesh Kumar K.V (Arm) wrote:
> +#define mem_encrypt_align mem_encrypt_align
> +static inline size_t mem_encrypt_align(size_t size)

IMHO this is the wrong API.

The issue here is not about alignment, it is about the permitted
granule size for shared/private.

On X86 this will be PAGE_SIZE on ARM64 it is
  max(hypervisor_page_size, PAGE_SIZE)

So think the arch helper should simply be

  __pure size_T mem_encrypt_granule_size(void);

> +	if (WARN_ON(!IS_ALIGNED(addr, mem_encrypt_align(PAGE_SIZE))))
> +		return 0;

And then we don't end up with weiro reading stuff like this..

if (WARN_ON(!IS_ALIGNED(addr, mem_encrypt_granule_size())) ||
    WARN_ON(!IS_ALIGNED(numpages, mem_encrypt_granule_size() / PAGE_SIZE)))

Is much more readable..
> @@ -319,8 +319,8 @@ static void __init *swiotlb_memblock_alloc(unsigned long nslabs,
>  		unsigned int flags,

The stuff like this is just ALING(nslabs << IO_TLB_SHIFT, mem_encrypt_granule_size())

etc

Jason

---

## [16] Aneesh Kumar K.V — 2026-01-06
*Subject: Re: [PATCH v2 1/4] swiotlb: dma: its: Enforce host page-size
 alignment for shared buffers*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Sun, Dec 21, 2025 at 09:39:17PM +0530, Aneesh Kumar K.V (Arm) wrote:
>> +#define mem_encrypt_align mem_encrypt_align

I added this helper

>> @@ -319,8 +319,8 @@ static void __init *swiotlb_memblock_alloc(unsigned long nslabs,
>>  		unsigned int flags,

I guess we can still keep mem_encrypt_align so that changes like below
becomes simpler.

-	int page_order = get_order(min_size);
+	int page_order = get_order(mem_encrypt_align(min_size));
 
-aneesh

---

## [17] Aneesh Kumar K.V — 2026-01-06
*Subject: Re: [PATCH v2 0/4] Enforce host page-size alignment for shared buffers*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Sun, Dec 21, 2025 at 09:39:16PM +0530, Aneesh Kumar K.V (Arm) wrote:
>> Hi all,

That is correct. I updated the commit message to

These shared buffers are also accessed by the host kernel and therefore
must be aligned to the host’s page size, and have a size that is a
multiple of the host page size.

-aneesh

---

## [18] Mostafa Saleh — 2026-03-11
*Subject: Re: [PATCH v2 4/4] dma: direct: set decrypted flag for remapped dma
 allocations*

On Fri, Dec 26, 2025 at 02:29:24PM +0530, Aneesh Kumar K.V wrote:
> Aneesh Kumar K.V <aneesh.kumar@kernel.org> writes:
> 

Are there any cases this happened in CCA, the only cases I can see
remap is true are:
- PageHighMem(): Where that fails for CCA
- !dev_is_dma_coherent(): AFAIK, all devices with CCA must have an
  SMMU, so direct DMA is only for virtualized devices which cannot
  be incoherent.

Thanks,
Mostafa

> 
> diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c

---
