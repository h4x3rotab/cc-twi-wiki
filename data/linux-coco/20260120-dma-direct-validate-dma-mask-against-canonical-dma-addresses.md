---
title: 'dma-direct: Validate DMA mask against canonical DMA addresses'
date: 2026-01-20
last_reply: 2026-01-21
message_count: 20
participants: ['Aneesh Kumar K.V (Arm)', 'kernel test robot', 'Suzuki K Poulose', 'Robin Murphy', 'Jason Gunthorpe']
---

## [1] Aneesh Kumar K.V (Arm) — 2026-01-20

On systems that apply an address encryption tag or mask to DMA addresses,
DMA mask validation must be performed against the canonical DMA address.
Using a non-canonical (e.g. encrypted or unencrypted) DMA address
can incorrectly fail capability checks, since architecture-specific
encryption bits are not part of the device’s actual DMA addressing
capability. For example, arm64 adds PROT_NS_SHARED to unencrypted DMA
addresses.

Fix this by validating device DMA masks against __phys_to_dma(), ensuring
that the architecture encryption mask does not influence the check.

Fixes: b66e2ee7b6c8 ("dma: Introduce generic dma_addr_*crypted helpers")
Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 kernel/dma/direct.c | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)

diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index 8e04f72baaa3..a5639e9415f5 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -580,12 +580,12 @@ int dma_direct_supported(struct device *dev, u64 mask)
 
 	/*
 	 * This check needs to be against the actual bit mask value, so use
-	 * phys_to_dma_unencrypted() here so that the SME encryption mask isn't
+	 * __phys_to_dma() here so that the arch specific encryption mask isn't
 	 * part of the check.
 	 */
 	if (IS_ENABLED(CONFIG_ZONE_DMA))
 		min_mask = min_t(u64, min_mask, zone_dma_limit);
-	return mask >= phys_to_dma_unencrypted(dev, min_mask);
+	return mask >= __phys_to_dma(dev, min_mask);
 }
 
 static const struct bus_dma_region *dma_find_range(struct device *dev,

---

## [2] Aneesh Kumar K.V (Arm) — 2026-01-20
*Subject: [PATCH 2/2] dma-direct: Make phys_to_dma() pick encrypted vs unencrypted per device*

On systems that apply an address encryption tag/mask to DMA addresses, the
choice of encrypted vs unencrypted DMA address is device-dependent (e.g.
TDISP trusted devices vs non-trusted devices).

Teach phys_to_dma() to make this choice based on
force_dma_unencrypted(dev), and convert dma-direct users to call
phys_to_dma() directly. With this in place, drop phys_to_dma_direct() as
redundant.

Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
---
 include/linux/dma-direct.h | 18 +++++++++++-------
 kernel/dma/direct.c        | 20 ++++++--------------
 2 files changed, 17 insertions(+), 21 deletions(-)

diff --git a/include/linux/dma-direct.h b/include/linux/dma-direct.h
index c249912456f9..e2e3a08373a1 100644
--- a/include/linux/dma-direct.h
+++ b/include/linux/dma-direct.h
@@ -90,17 +90,21 @@ static inline dma_addr_t phys_to_dma_unencrypted(struct device *dev,
 {
 	return dma_addr_unencrypted(__phys_to_dma(dev, paddr));
 }
-/*
- * If memory encryption is supported, phys_to_dma will set the memory encryption
- * bit in the DMA address, and dma_to_phys will clear it.
- * phys_to_dma_unencrypted is for use on special unencrypted memory like swiotlb
- * buffers.
- */
-static inline dma_addr_t phys_to_dma(struct device *dev, phys_addr_t paddr)
+
+static inline dma_addr_t phys_to_dma_encrypted(struct device *dev,
+					       phys_addr_t paddr)
 {
 	return dma_addr_encrypted(__phys_to_dma(dev, paddr));
 }
 
+static inline dma_addr_t phys_to_dma(struct device *dev, phys_addr_t paddr)
+{
+
+	if (force_dma_unencrypted(dev))
+		return phys_to_dma_unencrypted(dev, paddr);
+	return phys_to_dma_encrypted(dev, paddr);
+}
+
 static inline phys_addr_t dma_to_phys(struct device *dev, dma_addr_t dma_addr)
 {
 	phys_addr_t paddr;
diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
index a5639e9415f5..59d7d9e15e17 100644
--- a/kernel/dma/direct.c
+++ b/kernel/dma/direct.c
@@ -23,14 +23,6 @@
  */
 u64 zone_dma_limit __ro_after_init = DMA_BIT_MASK(24);
 
-static inline dma_addr_t phys_to_dma_direct(struct device *dev,
-		phys_addr_t phys)
-{
-	if (force_dma_unencrypted(dev))
-		return phys_to_dma_unencrypted(dev, phys);
-	return phys_to_dma(dev, phys);
-}
-
 static inline struct page *dma_direct_to_page(struct device *dev,
 		dma_addr_t dma_addr)
 {
@@ -40,7 +32,7 @@ static inline struct page *dma_direct_to_page(struct device *dev,
 u64 dma_direct_get_required_mask(struct device *dev)
 {
 	phys_addr_t phys = (phys_addr_t)(max_pfn - 1) << PAGE_SHIFT;
-	u64 max_dma = phys_to_dma_direct(dev, phys);
+	u64 max_dma = phys_to_dma(dev, phys);
 
 	return (1ULL << (fls64(max_dma) - 1)) * 2 - 1;
 }
@@ -69,7 +61,7 @@ static gfp_t dma_direct_optimal_gfp_mask(struct device *dev, u64 *phys_limit)
 
 bool dma_coherent_ok(struct device *dev, phys_addr_t phys, size_t size)
 {
-	dma_addr_t dma_addr = phys_to_dma_direct(dev, phys);
+	dma_addr_t dma_addr = phys_to_dma(dev, phys);
 
 	if (dma_addr == DMA_MAPPING_ERROR)
 		return false;
@@ -178,7 +170,7 @@ static void *dma_direct_alloc_from_pool(struct device *dev, size_t size,
 	page = dma_alloc_from_pool(dev, size, &ret, gfp, dma_coherent_ok);
 	if (!page)
 		return NULL;
-	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page));
+	*dma_handle = phys_to_dma(dev, page_to_phys(page));
 	return ret;
 }
 
@@ -196,7 +188,7 @@ static void *dma_direct_alloc_no_mapping(struct device *dev, size_t size,
 		arch_dma_prep_coherent(page, size);
 
 	/* return the page pointer as the opaque cookie */
-	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page));
+	*dma_handle = phys_to_dma(dev, page_to_phys(page));
 	return page;
 }
 
@@ -311,7 +303,7 @@ void *dma_direct_alloc(struct device *dev, size_t size,
 			goto out_encrypt_pages;
 	}
 
-	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page));
+	*dma_handle = phys_to_dma(dev, page_to_phys(page));
 	return ret;
 
 out_encrypt_pages:
@@ -392,7 +384,7 @@ struct page *dma_direct_alloc_pages(struct device *dev, size_t size,
 	if (dma_set_decrypted(dev, ret, size))
 		goto out_leak_pages;
 	memset(ret, 0, size);
-	*dma_handle = phys_to_dma_direct(dev, page_to_phys(page));
+	*dma_handle = phys_to_dma(dev, page_to_phys(page));
 	return page;
 out_leak_pages:
 	return NULL;

---

## [3] kernel test robot — 2026-01-20
*Subject: Re: [PATCH 2/2] dma-direct: Make phys_to_dma() pick encrypted vs
 unencrypted per device*

Hi Aneesh,

kernel test robot noticed the following build errors:

[auto build test ERROR on linus/master]
[also build test ERROR on v6.19-rc6 next-20260119]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Aneesh-Kumar-K-V-Arm/dma-direct-Make-phys_to_dma-pick-encrypted-vs-unencrypted-per-device/20260120-145025
base:   linus/master
patch link:    https://lore.kernel.org/r/20260120064255.179425-2-aneesh.kumar%40kernel.org
patch subject: [PATCH 2/2] dma-direct: Make phys_to_dma() pick encrypted vs unencrypted per device
config: arm-allnoconfig (https://download.01.org/0day-ci/archive/20260120/202601201747.22JsrCCp-lkp@intel.com/config)
compiler: clang version 22.0.0git (https://github.com/llvm/llvm-project 9b8addffa70cee5b2acc5454712d9cf78ce45710)
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20260120/202601201747.22JsrCCp-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202601201747.22JsrCCp-lkp@intel.com/

All errors (new ones prefixed by >>):

   In file included from kernel/dma/mapping.c:19:
   In file included from kernel/dma/direct.h:10:
>> include/linux/dma-direct.h:103:6: error: call to undeclared function 'force_dma_unencrypted'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration]
     103 |         if (force_dma_unencrypted(dev))
         |             ^
   include/linux/dma-direct.h:103:6: note: did you mean 'phys_to_dma_unencrypted'?
   include/linux/dma-direct.h:88:26: note: 'phys_to_dma_unencrypted' declared here
      88 | static inline dma_addr_t phys_to_dma_unencrypted(struct device *dev,
         |                          ^
      89 |                                                 phys_addr_t paddr)
      90 | {
      91 |         return dma_addr_unencrypted(__phys_to_dma(dev, paddr));
      92 | }
      93 | 
      94 | static inline dma_addr_t phys_to_dma_encrypted(struct device *dev,
      95 |                                                phys_addr_t paddr)
      96 | {
      97 |         return dma_addr_encrypted(__phys_to_dma(dev, paddr));
      98 | }
      99 | 
     100 | static inline dma_addr_t phys_to_dma(struct device *dev, phys_addr_t paddr)
     101 | {
     102 | 
     103 |         if (force_dma_unencrypted(dev))
         |             ~~~~~~~~~~~~~~~~~~~~~
         |             phys_to_dma_unencrypted
>> include/linux/dma-direct.h:125:20: error: conflicting types for 'force_dma_unencrypted'
     125 | static inline bool force_dma_unencrypted(struct device *dev)
         |                    ^
   include/linux/dma-direct.h:103:6: note: previous implicit declaration is here
     103 |         if (force_dma_unencrypted(dev))
         |             ^
   2 errors generated.


vim +/force_dma_unencrypted +103 include/linux/dma-direct.h

   102	
 > 103		if (force_dma_unencrypted(dev))
   104			return phys_to_dma_unencrypted(dev, paddr);
   105		return phys_to_dma_encrypted(dev, paddr);
   106	}
   107	
   108	static inline phys_addr_t dma_to_phys(struct device *dev, dma_addr_t dma_addr)
   109	{
   110		phys_addr_t paddr;
   111	
   112		dma_addr = dma_addr_canonical(dma_addr);
   113		if (dev->dma_range_map)
   114			paddr = translate_dma_to_phys(dev, dma_addr);
   115		else
   116			paddr = dma_addr;
   117	
   118		return paddr;
   119	}
   120	#endif /* !CONFIG_ARCH_HAS_PHYS_TO_DMA */
   121	
   122	#ifdef CONFIG_ARCH_HAS_FORCE_DMA_UNENCRYPTED
   123	bool force_dma_unencrypted(struct device *dev);
   124	#else
 > 125	static inline bool force_dma_unencrypted(struct device *dev)
   126	{
   127		return false;
   128	}
   129	#endif /* CONFIG_ARCH_HAS_FORCE_DMA_UNENCRYPTED */
   130

---

## [4] Suzuki K Poulose — 2026-01-20
*Subject: Re: [PATCH 1/2] dma-direct: Validate DMA mask against canonical DMA
 addresses*

On 20/01/2026 06:42, Aneesh Kumar K.V (Arm) wrote:
> On systems that apply an address encryption tag or mask to DMA addresses,
> DMA mask validation must be performed against the canonical DMA address.


> Signed-off-by: Aneesh Kumar K.V (Arm) <aneesh.kumar@kernel.org>
> ---

This is wrong, isn't it ? For e.g., for CCA, even though the "Flag" is
added to the PA, it is really part of the actual "PA" and thus must be
checked against the full PA ?

Suzuki


>   }
>

---

## [5] kernel test robot — 2026-01-20
*Subject: Re: [PATCH 2/2] dma-direct: Make phys_to_dma() pick encrypted vs
 unencrypted per device*

Hi Aneesh,

kernel test robot noticed the following build errors:

[auto build test ERROR on linus/master]
[also build test ERROR on v6.19-rc6 next-20260119]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Aneesh-Kumar-K-V-Arm/dma-direct-Make-phys_to_dma-pick-encrypted-vs-unencrypted-per-device/20260120-145025
base:   linus/master
patch link:    https://lore.kernel.org/r/20260120064255.179425-2-aneesh.kumar%40kernel.org
patch subject: [PATCH 2/2] dma-direct: Make phys_to_dma() pick encrypted vs unencrypted per device
config: alpha-allnoconfig (https://download.01.org/0day-ci/archive/20260120/202601201857.7LKBY5dB-lkp@intel.com/config)
compiler: alpha-linux-gcc (GCC) 15.2.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20260120/202601201857.7LKBY5dB-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202601201857.7LKBY5dB-lkp@intel.com/

All errors (new ones prefixed by >>):

   In file included from kernel/dma/direct.h:10,
                    from kernel/dma/mapping.c:19:
   include/linux/dma-direct.h: In function 'phys_to_dma':
>> include/linux/dma-direct.h:103:13: error: implicit declaration of function 'force_dma_unencrypted'; did you mean 'phys_to_dma_unencrypted'? [-Wimplicit-function-declaration]
     103 |         if (force_dma_unencrypted(dev))
         |             ^~~~~~~~~~~~~~~~~~~~~
         |             phys_to_dma_unencrypted
   include/linux/dma-direct.h: At top level:
>> include/linux/dma-direct.h:125:20: error: conflicting types for 'force_dma_unencrypted'; have 'bool(struct device *)' {aka '_Bool(struct device *)'}
     125 | static inline bool force_dma_unencrypted(struct device *dev)
         |                    ^~~~~~~~~~~~~~~~~~~~~
   include/linux/dma-direct.h:103:13: note: previous implicit declaration of 'force_dma_unencrypted' with type 'int()'
     103 |         if (force_dma_unencrypted(dev))
         |             ^~~~~~~~~~~~~~~~~~~~~


vim +103 include/linux/dma-direct.h

   102	
 > 103		if (force_dma_unencrypted(dev))
   104			return phys_to_dma_unencrypted(dev, paddr);
   105		return phys_to_dma_encrypted(dev, paddr);
   106	}
   107	
   108	static inline phys_addr_t dma_to_phys(struct device *dev, dma_addr_t dma_addr)
   109	{
   110		phys_addr_t paddr;
   111	
   112		dma_addr = dma_addr_canonical(dma_addr);
   113		if (dev->dma_range_map)
   114			paddr = translate_dma_to_phys(dev, dma_addr);
   115		else
   116			paddr = dma_addr;
   117	
   118		return paddr;
   119	}
   120	#endif /* !CONFIG_ARCH_HAS_PHYS_TO_DMA */
   121	
   122	#ifdef CONFIG_ARCH_HAS_FORCE_DMA_UNENCRYPTED
   123	bool force_dma_unencrypted(struct device *dev);
   124	#else
 > 125	static inline bool force_dma_unencrypted(struct device *dev)
   126	{
   127		return false;
   128	}
   129	#endif /* CONFIG_ARCH_HAS_FORCE_DMA_UNENCRYPTED */
   130

---

## [6] kernel test robot — 2026-01-20
*Subject: Re: [PATCH 1/2] dma-direct: Validate DMA mask against canonical DMA
 addresses*

Hi Aneesh,

kernel test robot noticed the following build errors:

[auto build test ERROR on linus/master]
[also build test ERROR on v6.19-rc6 next-20260119]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Aneesh-Kumar-K-V-Arm/dma-direct-Make-phys_to_dma-pick-encrypted-vs-unencrypted-per-device/20260120-145025
base:   linus/master
patch link:    https://lore.kernel.org/r/20260120064255.179425-1-aneesh.kumar%40kernel.org
patch subject: [PATCH 1/2] dma-direct: Validate DMA mask against canonical DMA addresses
config: powerpc-allnoconfig (https://download.01.org/0day-ci/archive/20260120/202601201822.0I4WAqVW-lkp@intel.com/config)
compiler: powerpc-linux-gcc (GCC) 15.2.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20260120/202601201822.0I4WAqVW-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202601201822.0I4WAqVW-lkp@intel.com/

All errors (new ones prefixed by >>):

   kernel/dma/direct.c: In function 'dma_direct_supported':
>> kernel/dma/direct.c:564:24: error: implicit declaration of function '__phys_to_dma'; did you mean 'phys_to_dma'? [-Wimplicit-function-declaration]
     564 |         return mask >= __phys_to_dma(dev, min_mask);
         |                        ^~~~~~~~~~~~~
         |                        phys_to_dma


vim +564 kernel/dma/direct.c

   543	
   544	int dma_direct_supported(struct device *dev, u64 mask)
   545	{
   546		u64 min_mask = (max_pfn - 1) << PAGE_SHIFT;
   547	
   548		/*
   549		 * Because 32-bit DMA masks are so common we expect every architecture
   550		 * to be able to satisfy them - either by not supporting more physical
   551		 * memory, or by providing a ZONE_DMA32.  If neither is the case, the
   552		 * architecture needs to use an IOMMU instead of the direct mapping.
   553		 */
   554		if (mask >= DMA_BIT_MASK(32))
   555			return 1;
   556	
   557		/*
   558		 * This check needs to be against the actual bit mask value, so use
   559		 * __phys_to_dma() here so that the arch specific encryption mask isn't
   560		 * part of the check.
   561		 */
   562		if (IS_ENABLED(CONFIG_ZONE_DMA))
   563			min_mask = min_t(u64, min_mask, zone_dma_limit);
 > 564		return mask >= __phys_to_dma(dev, min_mask);
   565	}
   566

---

## [7] Robin Murphy — 2026-01-20
*Subject: Re: [PATCH 1/2] dma-direct: Validate DMA mask against canonical DMA
 addresses*

On 2026-01-20 9:59 am, Suzuki K Poulose wrote:
> On 20/01/2026 06:42, Aneesh Kumar K.V (Arm) wrote:
>> On systems that apply an address encryption tag or mask to DMA addresses,

Yes, it's much the same as for AMD SEV (albeit the other way round) - 
the encryption/decryption bit is part of the DMA address because it 
needs to be driven by the device, so it is crucial that the device's DMA 
mask is capable of expressing that.

Hence, as I think we've discussed before, for CCA we can't really 
support 32-bit devices doing DMA to shared pages at all, unless the 
whole VM is limited to a 31-bit IPA space.

Thanks,
Robin.

> 
> Suzuki

---

## [8] Jason Gunthorpe — 2026-01-20
*Subject: Re: [PATCH 1/2] dma-direct: Validate DMA mask against canonical DMA
 addresses*

On Tue, Jan 20, 2026 at 12:12:54PM +0530, Aneesh Kumar K.V (Arm) wrote:
> On systems that apply an address encryption tag or mask to DMA addresses,
> DMA mask validation must be performed against the canonical DMA address.

Huh?

static inline dma_addr_t phys_to_dma_direct(struct device *dev,
                phys_addr_t phys)
{
        if (force_dma_unencrypted(dev))
                return phys_to_dma_unencrypted(dev, phys);
        return phys_to_dma(dev, phys);
}

dma_addr_t swiotlb_map(struct device *dev, phys_addr_t paddr, size_t size,
                enum dma_data_direction dir, unsigned long attrs)
{
[..]

        /* Ensure that the address returned is DMA'ble */
        dma_addr = phys_to_dma_unencrypted(dev, swiotlb_addr);
[..]
        return dma_addr;
}

The check in dma_direct_supported() is checking if the device's HW
capability can contain the range of dma_addr_t's the DMA API will
generate. Since it above is generating dma_addr_t's with the
PROT_NS_SHARED set, it is correct to check it against the mask.

If the IOVA does not contain PROT_NS_SHARED then I would expect all of
the above to be removed too?

Can you please explain what the probem is better?

I just had a long talk with our internal people about this very
subject and they were adament that the ARM design had the T=0 SMMU S2
configured so that the IOVA starts at PROT_NS_SHARED, not 0. I am
against this, I think it is a bad choice, and this patch is showing
exactly why :)

IMHO you should map the T=0 S2 so that the IOVA starts at 0 and we
don't add PROT_NS_SHARED to the IOVA anyhwere.

This logic is going to be wrong for T=1 DMA to private memory though.

Jason

---

## [9] Aneesh Kumar K.V — 2026-01-20
*Subject: Re: [PATCH 1/2] dma-direct: Validate DMA mask against canonical DMA
 addresses*

Suzuki K Poulose <suzuki.poulose@arm.com> writes:

> On 20/01/2026 06:42, Aneesh Kumar K.V (Arm) wrote:
>> On systems that apply an address encryption tag or mask to DMA addresses,

That is true only when the device is operating in untrusted mode?. For a
trusted device that mask is valid mask right?

-aneesh

---

## [10] Aneesh Kumar K.V — 2026-01-20
*Subject: Re: [PATCH 1/2] dma-direct: Validate DMA mask against canonical DMA
 addresses*

Robin Murphy <robin.murphy@arm.com> writes:

> On 2026-01-20 9:59 am, Suzuki K Poulose wrote:
>> On 20/01/2026 06:42, Aneesh Kumar K.V (Arm) wrote:

Commit c92a54cfa0257e8ffd66b2a17d49e9c0bd4b769f explains these details.

I was wondering whether the DMA-enable operation should live outside the
set_mask operation. Conceptually, set_mask should be derived purely from
max_pfn, while the DMA enablement path could additionally verify whether
the device requires access to an alias address, depending on whether it
is operating in trusted or untrusted mode?

>
> Hence, as I think we've discussed before, for CCA we can't really 

-aneesh

---

## [11] Suzuki K Poulose — 2026-01-20
*Subject: Re: [PATCH 1/2] dma-direct: Validate DMA mask against canonical DMA
 addresses*

On 20/01/2026 14:18, Aneesh Kumar K.V wrote:
> Suzuki K Poulose <suzuki.poulose@arm.com> writes:
> 

Irrespective of the mode in which the device is operating, the DMA
address must include the fully qualified "{I}PA" address, right ?
i.e., "the Unencrypted" bit is only a software construct and the full
PA must be used, irrespective of the mode of the device.

Suzuki

> 
> -aneesh

---

## [12] Jason Gunthorpe — 2026-01-20
*Subject: Re: [PATCH 1/2] dma-direct: Validate DMA mask against canonical DMA
 addresses*

On Tue, Jan 20, 2026 at 02:39:14PM +0000, Suzuki K Poulose wrote:
> > > > diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c
> > > > index 8e04f72baaa3..a5639e9415f5 100644

But you could make an argument that a trusted device won't DMA to
shared memory, ie it would SWIOTLB to private memory if that is
required.

Otherwise these two limitations will exclude huge numbers of real
devices from working with ARM CCA at all.

Jason

---

## [13] Aneesh Kumar K.V — 2026-01-20
*Subject: Re: [PATCH 1/2] dma-direct: Validate DMA mask against canonical DMA
 addresses*

Jason Gunthorpe <jgg@ziepe.ca> writes:

> On Tue, Jan 20, 2026 at 12:12:54PM +0530, Aneesh Kumar K.V (Arm) wrote:
>> On systems that apply an address encryption tag or mask to DMA addresses,

There is no specific problem identified. The motivation for this change
is to ensure that the trusted device mask check is accurate.

>
> I just had a long talk with our internal people about this very

But how will we support a trusted device access to both shared and
private memory? Commit  7d953a06241624ee2efb172d037a4168978f4147 goes
into some details w.r.t why PROT_NS_SHARED was added to dma_addr_t.

>
> This logic is going to be wrong for T=1 DMA to private memory though.

-aneesh

---

## [14] Jason Gunthorpe — 2026-01-20
*Subject: Re: [PATCH 1/2] dma-direct: Validate DMA mask against canonical DMA
 addresses*

On Tue, Jan 20, 2026 at 08:55:43PM +0530, Aneesh Kumar K.V wrote:
> > The check in dma_direct_supported() is checking if the device's HW
> > capability can contain the range of dma_addr_t's the DMA API will

Well, don't break untrusted in the process, and please explain
motivation in commit messages in future. Why things are being changed
is very important information.

> > I just had a long talk with our internal people about this very
> > subject and they were adament that the ARM design had the T=0 SMMU S2

The IO translation path used by trusted and untrusted devices are
completely different. You don't need a T=0 device to have the same S2
as a T=1 device. The commit doesn't explain anything, it is just
documenting the poor S2 conventions that CCA already adopted.

What should be done is that the T=0 untrusted translation path, which
can *never* access private memory anyhow, simply puts what the CPU
sees as the PROT_NS_SHARED region starting at IOVA 0. This path is
setup by the host VMM (ie qemu) and HW can support whatever
translation you want. There is no use case to ever not set
PROT_NS_SHARED for T=1 DMA so why break so many real devices by
requiring this useless bit?

The T=1 trusted translation path should have the RMM setup the S2 so
it mirrors the CPU S2 with the private memory at 0 and the shared
starting at PROT_NS_SHARED. An address width limited device would then
be unable to access shared memory without bouncing through private
memory with SWIOTLB, but it can probably access all the private
memory. The existing SWIOTLB address limit bouncing machinery is
designed to mitigate exactly this condition so it can be used to
bounce buffer from private memory to shared if that use case ever
comes up.

Given this little mistake has already happened I'd suggest that the
VMM/qemu be changed to double map the same T=0 space to both 0 and
PROT_NS_SHARED, and have a discovery bit in the guest that it is
allowed to use 0 based IOVA for T=0 DMA.

Then you can fixuup the DMA API calls so that:
 1) If an old VMM continue to use PROT_NS_SHARED for T=0 and continue
    to check it against the DMA limit, de-supporting address width
    limited HW
 2) If a new VMM drop PROT_NS_SHARED for T=0 and check it. Since
    everything must use SWIOTLB ensure that SWIOTLB allocated addresses
    within the device support range, as it already is able to do.
 3) For a T=1 device assume it will not DMA to shared memory, we don't
    have any way to describe that in the DMA API right now. Check the
    native physical address against the limit and SWIOTLB bounce to
    private memory for outside the limit.

This way CCA would work on alot more actual HW :\

Jason

---

## [15] Robin Murphy — 2026-01-20
*Subject: Re: [PATCH 1/2] dma-direct: Validate DMA mask against canonical DMA
 addresses*

On 2026-01-20 3:11 pm, Jason Gunthorpe wrote:
> On Tue, Jan 20, 2026 at 02:39:14PM +0000, Suzuki K Poulose wrote:
>>>>> diff --git a/kernel/dma/direct.c b/kernel/dma/direct.c

I don't think we can assume that any arbitrary trusted device is *never* 
going to want to access shared memory in the Realm IPA space, and while 
it might technically be possible for a private SWIOTLB buffer to handle 
that, we currently only have infrastructure that assumes the opposite 
(i.e. that SWIOTLB buffers are shared for bouncing untrusted DMA to/from 
private memory). Thus for now, saying we can only promise to support DMA 
if the device can access the whole IPA space itself is accurate.

> Otherwise these two limitations will exclude huge numbers of real
> devices from working with ARM CCA at all.

Pretty sure the dependency on TDISP wins in that regard ;)

However, assuming that Realms and RMMs might eventually come up with 
their own attestation mechanisms for on-chip non-PCIe devices (and such 
devices continue to have crippled DMA capabilities) then the fact is 
still that DA requires an SMMU for S2, so at worst there should always 
be the possibility for an RMM to offer S1 SMMU support to the Realm, 
we're just not there yet.

Thanks,
Robin.

---

## [16] Jason Gunthorpe — 2026-01-20
*Subject: Re: [PATCH 1/2] dma-direct: Validate DMA mask against canonical DMA
 addresses*

On Tue, Jan 20, 2026 at 05:11:27PM +0000, Robin Murphy wrote:
> > But you could make an argument that a trusted device won't DMA to
> > shared memory, ie it would SWIOTLB to private memory if that is

Well, I can say it isn't supported with the DMA API we have today, so
that's not *never* but at least for the present moment assuming that
only private addresses are used with DMA would be consistent with the
overall kernel capability.

Certainly I think we have use cases for mixing traffic, and someone
here is looking at what it would take to extend things to actually
make it possible to reach into arbitrary shared memory with the DMA
API..

>  and while it might technically be possible for a private SWIOTLB
> buffer to handle that, we currently only have infrastructure that

We also don't support T=1 devices with the current kernel either, and
the required behavior is exactly what a normal non-CC kernel does
today. Basically, SWIOTLB should not be allocating or using shared
memory with a T=1 device at all, and I think that is a important thing
to have in the code for security.

Anyhow, I'm just saying either you keep the limit as we have now or if
the limit is relaxed for T=1 then it would make sense to fixup SWIOTLB
to do traditional bouncing to avoid high (shared) addresses.

> Thus for now, saying we can only promise to support DMA if the
> device can access the whole IPA space itself is accurate.

Right, that is where things are right now, and I don't think we should
move away from those code limitations unless there are mitigations
like bouncing..

> > Otherwise these two limitations will exclude huge numbers of real
> > devices from working with ARM CCA at all.

You can use existing T=0 devices without TDISP

And bolting a TDISP capable PCI IP onto a device with an addressing
limit probably isn't going to fix the addressing limit. :(

> However, assuming that Realms and RMMs might eventually come up with their
> own attestation mechanisms for on-chip non-PCIe devices (and such devices

The fabric isn't the only issue here, and even "PCIe" appearing
devices don't necessarily run over real-PCIe and may have limited
fabrics.

There are enough important devices out there that have internal
limitations, like registers and data structures that just cannot store
the full 64 bit address space. HW folks have a big $$ incentive
to take shortcuts like this..

> then the fact is still that DA requires an SMMU for S2, so at worst
> there should always be the possibility for an RMM to offer S1 SMMU

Having a S1 would help a T=1 device, but it doesn't do anything for
the T=0 devices.

The other answer is to expect the VMM to limit the IPA size so that
the IO devices can reach the full address space.

Jason

---

## [17] Robin Murphy — 2026-01-20
*Subject: Re: [PATCH 1/2] dma-direct: Validate DMA mask against canonical DMA
 addresses*

On 2026-01-20 5:54 pm, Jason Gunthorpe wrote:
> On Tue, Jan 20, 2026 at 05:11:27PM +0000, Robin Murphy wrote:
>>> But you could make an argument that a trusted device won't DMA to

Indeed those are essentially all the same points I was making too - even 
a T=1 device must support the full IPA range today, because if any 
generated DMA address led to trying to use SWIOTLB via the current code 
that would go horrifically wrong in ways likely to leak private data, or 
at best fault at S2 and/or corrupt Realm memory (and at worst, all 3).

>> Thus for now, saying we can only promise to support DMA if the
>> device can access the whole IPA space itself is accurate.

Fair enough, guess I shall temper my optimism...

>> then the fact is still that DA requires an SMMU for S2, so at worst
>> there should always be the possibility for an RMM to offer S1 SMMU

If we have an SMMU we have an SMMU - S1 for T=0 devices is just regular 
VFIO/IOMMUFD in Non-Secure VA/IPA space, for which the VMM doesn't need 
the RMM's help. I've long been taking it for granted that that one's a 
non-issue ;)

The only thing we can't easily handle (and would rather avoid) is S1 
translation for T=0 traffic from T=1 devices, since that would require 
the Realm OS to comprehend the notion of a single device attached to two 
different vSMMUs at once. Rather, to be workable I think we'd need to 
keep the T=0 and T=1 states described as distinct devices - which 
*could* then each be associated with "shared" (VMM-provided) and 
"private" (RMM-provided) vSMMU instances respectively - and leave it as 
the Realm driver's problem if it wants to coordinate enabling and using 
both at the same time, kinda like the link aggregation model.

Thanks,
Robin.

> The other answer is to expect the VMM to limit the IPA size so that
> the IO devices can reach the full address space.

---

## [18] Robin Murphy — 2026-01-20
*Subject: Re: [PATCH 1/2] dma-direct: Validate DMA mask against canonical DMA
 addresses*

On 2026-01-20 2:25 pm, Aneesh Kumar K.V wrote:
> Robin Murphy <robin.murphy@arm.com> writes:
> 

See x86's force_dma_unencrypted() implementation - the reason dma-direct 
doesn't need to be so strict for that is because things are the right 
way round that it can always fall back to shared/untrusted DMA as the 
general case, and a device can only access an encrypted page directly if 
it *can* drive the SME bit in the input address to trigger the inline 
encryption engine.

For CCA we have rather the opposite, where dma-direct requires a device 
to be able to address any IPA directly to be sure of working at all, but 
if we do happen to have a stage 1 IOMMU then we could rely on that to 
map smaller IOVAs to the upper IPA space.

> I was wondering whether the DMA-enable operation should live outside the
> set_mask operation. Conceptually, set_mask should be derived purely from

No, the point of the set_mask check is "is this mask big enough to 
accommodate any *DMA address* we might need to give the device?" - that 
includes offsets, magic bits, magic bits encoded as fake offsets (yes 
you, Raspberry Pi...) and whatever else might comprise an actual DMA 
address as handed off to the hardware. It is *not* directly a "can this 
device DMA to all RAM we know about?" check - that is in the assumption 
that if necessary the SWIOTLB buffer will be reachable at a <=32-bit DMA 
address, and thus we should not *need* to give >32-bit addresses to 
devices. It is only that assumption which fundamentally falls apart for 
CCA (with more than 2GB of IPA space, at least).

Thanks,
Robin.

---

## [19] Jason Gunthorpe — 2026-01-20
*Subject: Re: [PATCH 1/2] dma-direct: Validate DMA mask against canonical DMA
 addresses*

On Tue, Jan 20, 2026 at 06:47:02PM +0000, Robin Murphy wrote:
> > > then the fact is still that DA requires an SMMU for S2, so at worst
> > > there should always be the possibility for an RMM to offer S1 SMMU

Well, sort of. Yes that's all true, but since the T=0 vSMMU cannot
access private memory it will not work properly with the current
driver in Linux which doesn't know how to allocate shared memory for
the page table.

> The only thing we can't easily handle (and would rather avoid) is S1
> translation for T=0 traffic from T=1 devices, since that would require the

Yes, so far the general consensus I've heard is that this will not be
done, the vSMMU presented to the VM will only handle T=1 traffic and
the OS must assume that T=0 traffic is identity.

Given those two reasons my general take is that we will not see a T=0
vSMMU in ccVMs at all.

>  Rather, to be workable I think we'd need to keep the T=0 and T=1
> states described as distinct devices - which *could* then each be

Hopefully we don't need to do this :(

The current thought is that there would be only one device and when it
is in T=0 mode the OS knows the linked iommu is not being used on
ARM. IIRC AMD and Intel do not have this quirk.

Sadly there are use cases for a TDISP device to do T=0 DMA before it
reaches the run state.

Jason

---

## [20] Aneesh Kumar K.V — 2026-01-21
*Subject: Re: [PATCH 1/2] dma-direct: Validate DMA mask against canonical DMA
 addresses*

Robin Murphy <robin.murphy@arm.com> writes:

> On 2026-01-20 2:25 pm, Aneesh Kumar K.V wrote:
>> Robin Murphy <robin.murphy@arm.com> writes:

We need the below change then? commit 91ef26f914171cf753330f13724fd9142b5b1640
discuss some hardware that is broken with the usage of phys_to_dma conversion. 

modified   kernel/dma/direct.c
@@ -14,6 +14,7 @@
 #include <linux/set_memory.h>
 #include <linux/slab.h>
 #include <linux/pci-p2pdma.h>
+#include <linux/cc_platform.h>
 #include "direct.h"
 
 /*
@@ -579,17 +580,23 @@ int dma_direct_mmap(struct device *dev, struct vm_area_struct *vma,
 
 int dma_direct_supported(struct device *dev, u64 mask)
 {
-	u64 min_mask = (max_pfn - 1) << PAGE_SHIFT;
+	u64 min_mask = DMA_BIT_MASK(32);
 
 	/*
-	 * Because 32-bit DMA masks are so common we expect every architecture
-	 * to be able to satisfy them - either by not supporting more physical
-	 * memory, or by providing a ZONE_DMA32.  If neither is the case, the
-	 * architecture needs to use an IOMMU instead of the direct mapping.
+	 * Only do the conversion for CC platform, to be compatible
+	 * commit 91ef26f914171cf753330f13724fd9142b5b1640
 	 */
-	if (mask >= DMA_BIT_MASK(32))
+	if (cc_platform_has(CC_ATTR_MEM_ENCRYPT))
+		min_mask = phys_to_dma_unencrypted(dev, min_mask);
+
+	/*
+	 * if we support ZONE_DMA32 and device mask can cover the DMA32 range,
+	 * then we can support direct dma for any max_pfn value using swiotlb.
+	 */
+	if (IS_ENABLED(CONFIG_ZONE_DMA32) && mask >= min_mask)
 		return 1;
 
+	min_mask = (max_pfn - 1) << PAGE_SHIFT;
 	/*
 	 * This check needs to be against the actual bit mask value, so use
 	 * __phys_to_dma() here so that the arch specific encryption mask isn't


-aneesh

---
