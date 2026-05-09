---
title: 'Restrict devmem for confidential VMs'
date: 2025-04-17
last_reply: 2025-05-07
message_count: 21
participants: ['Dan Williams', 'Dave Hansen', 'kernel test robot', 'Nikolay Borisov', 'Naveen N Rao', 'Jianxiong Gao', 'Suzuki K Poulose']
---

## [1] Dan Williams — 2025-04-17

Changes since v2 [1]:
* Drop the new x86_platform_op and just use
  cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT) directly where needed
  (Naveen)
* Make the restriction identical to lockdown and stop playing games with
  devmem_is_allowed()
* Ensure that CONFIG_IO_STRICT_DEVMEM is enabled to avoid conflicting
  mappings for userspace mappings of PCI MMIO.

The original response to Nikolay's report of an SEPT violation triggered
by /dev/mem access to private memory was "let's just turn off /dev/mem".

After some machinations of x86_platform_ops to block a subset of
problematic access, spelunking the history of devmem_is_allowed()
returning "2" to enable some compatibility benefits while blocking
access, and discovering that userspace depends buggy kernel behavior for
mmap(2) of the first 1MB of memory on x86, the proposal has circled back
to "disable /dev/mem".

Require both STRICT_DEVMEM and IO_STRICT_DEVMEM for x86 confidential
guests to close /dev/mem hole while still allowing for userspace
mapping of PCI MMIO as long as the kernel and userspace are not mapping
the range at the same time.

The range_is_allowed() cleanup is not strictly necessary, but might as
well close a 17 year-old "TODO".

---

Dan Williams (2):
      x86/devmem: Remove duplicate range_is_allowed() definition
      x86/devmem: Drop /dev/mem access for confidential guests


 arch/x86/Kconfig          |    4 ++++
 arch/x86/mm/pat/memtype.c |   31 ++++---------------------------
 drivers/char/mem.c        |   27 +++++++++------------------
 include/linux/io.h        |   21 +++++++++++++++++++++
 4 files changed, 38 insertions(+), 45 deletions(-)

base-commit: 0af2f6be1b4281385b618cb86ad946eded089ac8

---

## [2] Dan Williams — 2025-04-17
*Subject: [PATCH v3 1/2] x86/devmem: Remove duplicate range_is_allowed()
 definition*

17 years ago, Venki suggested [1] "A future improvement would be to
avoid the range_is_allowed duplication".

The only thing preventing a common implementation is that
phys_mem_access_prot_allowed() expects the range check to exit
immediately when PAT is disabled [2]. I.e. there is no cache conflict to
manage in that case. This cleanup was noticed on the path to
considering changing range_is_allowed() policy to blanket deny /dev/mem
for private (confidential computing) memory.

Note, however that phys_mem_access_prot_allowed() has long since stopped
being relevant for managing cache-type validation due to [3], and [4].

Commit 0124cecfc85a ("x86, PAT: disable /dev/mem mmap RAM with PAT") [1]
Commit 9e41bff2708e ("x86: fix /dev/mem mmap breakage when PAT is disabled") [2]
Commit 1886297ce0c8 ("x86/mm/pat: Fix BUG_ON() in mmap_mem() on QEMU/i386") [3]
Commit 0c3c8a18361a ("x86, PAT: Remove duplicate memtype reserve in devmem mmap") [4]

Cc: Dave Hansen <dave.hansen@linux.intel.com>
Cc: Ingo Molnar <mingo@kernel.org>
Cc: "Naveen N Rao" <naveen@kernel.org>
Reviewed-by: Nikolay Borisov <nik.borisov@suse.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/mm/pat/memtype.c |   31 ++++---------------------------
 drivers/char/mem.c        |   18 ------------------
 include/linux/io.h        |   21 +++++++++++++++++++++
 3 files changed, 25 insertions(+), 45 deletions(-)

diff --git a/arch/x86/mm/pat/memtype.c b/arch/x86/mm/pat/memtype.c
index 72d8cbc61158..c97b6598f187 100644
--- a/arch/x86/mm/pat/memtype.c
+++ b/arch/x86/mm/pat/memtype.c
@@ -38,6 +38,7 @@
 #include <linux/kernel.h>
 #include <linux/pfn_t.h>
 #include <linux/slab.h>
+#include <linux/io.h>
 #include <linux/mm.h>
 #include <linux/highmem.h>
 #include <linux/fs.h>
@@ -773,38 +774,14 @@ pgprot_t phys_mem_access_prot(struct file *file, unsigned long pfn,
 	return vma_prot;
 }
 
-#ifdef CONFIG_STRICT_DEVMEM
-/* This check is done in drivers/char/mem.c in case of STRICT_DEVMEM */
-static inline int range_is_allowed(unsigned long pfn, unsigned long size)
-{
-	return 1;
-}
-#else
-/* This check is needed to avoid cache aliasing when PAT is enabled */
-static inline int range_is_allowed(unsigned long pfn, unsigned long size)
-{
-	u64 from = ((u64)pfn) << PAGE_SHIFT;
-	u64 to = from + size;
-	u64 cursor = from;
-
-	if (!pat_enabled())
-		return 1;
-
-	while (cursor < to) {
-		if (!devmem_is_allowed(pfn))
-			return 0;
-		cursor += PAGE_SIZE;
-		pfn++;
-	}
-	return 1;
-}
-#endif /* CONFIG_STRICT_DEVMEM */
-
 int phys_mem_access_prot_allowed(struct file *file, unsigned long pfn,
 				unsigned long size, pgprot_t *vma_prot)
 {
 	enum page_cache_mode pcm = _PAGE_CACHE_MODE_WB;
 
+	if (!pat_enabled())
+		return 1;
+
 	if (!range_is_allowed(pfn, size))
 		return 0;
 
diff --git a/drivers/char/mem.c b/drivers/char/mem.c
index 169eed162a7f..48839958b0b1 100644
--- a/drivers/char/mem.c
+++ b/drivers/char/mem.c
@@ -61,29 +61,11 @@ static inline int page_is_allowed(unsigned long pfn)
 {
 	return devmem_is_allowed(pfn);
 }
-static inline int range_is_allowed(unsigned long pfn, unsigned long size)
-{
-	u64 from = ((u64)pfn) << PAGE_SHIFT;
-	u64 to = from + size;
-	u64 cursor = from;
-
-	while (cursor < to) {
-		if (!devmem_is_allowed(pfn))
-			return 0;
-		cursor += PAGE_SIZE;
-		pfn++;
-	}
-	return 1;
-}
 #else
 static inline int page_is_allowed(unsigned long pfn)
 {
 	return 1;
 }
-static inline int range_is_allowed(unsigned long pfn, unsigned long size)
-{
-	return 1;
-}
 #endif
 
 static inline bool should_stop_iteration(void)
diff --git a/include/linux/io.h b/include/linux/io.h
index 6a6bc4d46d0a..0642c7ee41db 100644
--- a/include/linux/io.h
+++ b/include/linux/io.h
@@ -183,4 +183,25 @@ static inline void arch_io_free_memtype_wc(resource_size_t base,
 int devm_arch_io_reserve_memtype_wc(struct device *dev, resource_size_t start,
 				    resource_size_t size);
 
+#ifdef CONFIG_STRICT_DEVMEM
+static inline int range_is_allowed(unsigned long pfn, unsigned long size)
+{
+	u64 from = ((u64)pfn) << PAGE_SHIFT;
+	u64 to = from + size;
+	u64 cursor = from;
+
+	while (cursor < to) {
+		if (!devmem_is_allowed(pfn))
+			return 0;
+		cursor += PAGE_SIZE;
+		pfn++;
+	}
+	return 1;
+}
+#else
+static inline int range_is_allowed(unsigned long pfn, unsigned long size)
+{
+	return 1;
+}
+#endif
 #endif /* _LINUX_IO_H */

---

## [3] Dan Williams — 2025-04-17
*Subject: [PATCH v3 2/2] x86/devmem: Drop /dev/mem access for confidential
 guests*

Nikolay reports [1] that accessing BIOS data (first 1MB of the physical
address space) via /dev/mem results in an SEPT violation.

The cause is ioremap() (via xlate_dev_mem_ptr()) establishes an
unencrypted mapping where the kernel had established an encrypted
mapping previously.

Linux traps read(2) access to the BIOS data area, and returns zero.
However, it turns out the kernel fails to enforce the same via mmap(2).
This is a hole, and unfortunately userspace has learned to exploit it
[2].

This means the kernel either needs a mechanism to ensure consistent
"encrypted" mappings of this /dev/mem mmap() hole, close the hole by
mapping the zero page in the mmap(2) path, block only BIOS data access
and let typical STRICT_DEVMEM protect the rest, or disable /dev/mem
altogether.

The simplest option for now is arrange for /dev/mem to always behave as
if lockdown is enabled for confidential guests. Require confidential
guest userspace to jettison legacy dependencies on /dev/mem similar to
how other legacy mechanisms are jettisoned for confidential operation.
Recall that modern methods for BIOS data access are available like
/sys/firmware/dmi/tables.

Cc: <x86@kernel.org>
Cc: Kees Cook <kees@kernel.org>
Cc: Ingo Molnar <mingo@kernel.org>
Cc: "Naveen N Rao" <naveen@kernel.org>
Cc: Vishal Annapurve <vannapurve@google.com>
Cc: Dave Hansen <dave.hansen@linux.intel.com>
Cc: Kirill Shutemov <kirill.shutemov@linux.intel.com>
Link: https://sources.debian.org/src/libdebian-installer/0.125/src/system/subarch-x86-linux.c/?hl=113#L93 [2]
Reported-by: Nikolay Borisov <nik.borisov@suse.com>
Closes: http://lore.kernel.org/20250318113604.297726-1-nik.borisov@suse.com [1]
Fixes: 9aa6ea69852c ("x86/tdx: Make pages shared in ioremap()")
Cc: <stable@vger.kernel.org>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/Kconfig   |    4 ++++
 drivers/char/mem.c |    9 +++++++++
 2 files changed, 13 insertions(+)

diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
index 4b9f378e05f6..bf4528d9fd0a 100644
--- a/arch/x86/Kconfig
+++ b/arch/x86/Kconfig
@@ -891,6 +891,8 @@ config INTEL_TDX_GUEST
 	depends on X86_X2APIC
 	depends on EFI_STUB
 	depends on PARAVIRT
+	depends on STRICT_DEVMEM
+	depends on IO_STRICT_DEVMEM
 	select ARCH_HAS_CC_PLATFORM
 	select X86_MEM_ENCRYPT
 	select X86_MCE
@@ -1510,6 +1512,8 @@ config AMD_MEM_ENCRYPT
 	bool "AMD Secure Memory Encryption (SME) support"
 	depends on X86_64 && CPU_SUP_AMD
 	depends on EFI_STUB
+	depends on STRICT_DEVMEM
+	depends on IO_STRICT_DEVMEM
 	select DMA_COHERENT_POOL
 	select ARCH_USE_MEMREMAP_PROT
 	select INSTRUCTION_DECODER
diff --git a/drivers/char/mem.c b/drivers/char/mem.c
index 48839958b0b1..f394f941b113 100644
--- a/drivers/char/mem.c
+++ b/drivers/char/mem.c
@@ -595,6 +595,15 @@ static int open_port(struct inode *inode, struct file *filp)
 	if (rc)
 		return rc;
 
+	/*
+	 * Enforce encrypted mapping consistency and avoid unaccepted
+	 * memory conflicts, "lockdown" /dev/mem for confidential
+	 * guests.
+	 */
+	if (IS_ENABLED(CONFIG_STRICT_DEVMEM) &&
+	    cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT))
+		return -EPERM;
+
 	if (iminor(inode) != DEVMEM_MINOR)
 		return 0;

---

## [4] Dave Hansen — 2025-04-17
*Subject: Re: [PATCH v3 1/2] x86/devmem: Remove duplicate range_is_allowed()
 definition*

On 4/17/25 12:12, Dan Williams wrote:
> The only thing preventing a common implementation is that
> phys_mem_access_prot_allowed() expects the range check to exit

Yay, removing duplicated code!

Acked-by: Dave Hansen <dave.hansen@linux.intel.com>

---

## [5] Dave Hansen — 2025-04-17
*Subject: Re: [PATCH v3 2/2] x86/devmem: Drop /dev/mem access for confidential
 guests*

On 4/17/25 12:12, Dan Williams wrote:
...
> +	/*
> +	 * Enforce encrypted mapping consistency and avoid unaccepted
A lot of /dev/mem use seems to be poking at random hardware details like
BIOS internals, ACPI tables or hardware devices. Those all have modern
alternatives. So while I worry that this will make some userspace mad, I
have a hard time imagining that it's _relevant_ userspace on a modern
x86 CoCo platform where that userspace isn't buggy already.

Acked-by: Dave Hansen <dave.hansen@linux.intel.com>

---

## [6] kernel test robot — 2025-04-18
*Subject: Re: [PATCH v3 2/2] x86/devmem: Drop /dev/mem access for confidential
 guests*

Hi Dan,

kernel test robot noticed the following build errors:

[auto build test ERROR on 0af2f6be1b4281385b618cb86ad946eded089ac8]

url:    https://github.com/intel-lab-lkp/linux/commits/Dan-Williams/x86-devmem-Remove-duplicate-range_is_allowed-definition/20250418-031657
base:   0af2f6be1b4281385b618cb86ad946eded089ac8
patch link:    https://lore.kernel.org/r/174491712829.1395340.5054725417641299524.stgit%40dwillia2-xfh.jf.intel.com
patch subject: [PATCH v3 2/2] x86/devmem: Drop /dev/mem access for confidential guests
config: arc-randconfig-001-20250418 (https://download.01.org/0day-ci/archive/20250418/202504180628.qlDJEl1e-lkp@intel.com/config)
compiler: arc-linux-gcc (GCC) 14.2.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20250418/202504180628.qlDJEl1e-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202504180628.qlDJEl1e-lkp@intel.com/

All errors (new ones prefixed by >>):

   drivers/char/mem.c: In function 'open_port':
>> drivers/char/mem.c:604:13: error: implicit declaration of function 'cc_platform_has' [-Wimplicit-function-declaration]
     604 |             cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT))
         |             ^~~~~~~~~~~~~~~
>> drivers/char/mem.c:604:29: error: 'CC_ATTR_GUEST_MEM_ENCRYPT' undeclared (first use in this function)
     604 |             cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT))
         |                             ^~~~~~~~~~~~~~~~~~~~~~~~~
   drivers/char/mem.c:604:29: note: each undeclared identifier is reported only once for each function it appears in


vim +/cc_platform_has +604 drivers/char/mem.c

   586	
   587	static int open_port(struct inode *inode, struct file *filp)
   588	{
   589		int rc;
   590	
   591		if (!capable(CAP_SYS_RAWIO))
   592			return -EPERM;
   593	
   594		rc = security_locked_down(LOCKDOWN_DEV_MEM);
   595		if (rc)
   596			return rc;
   597	
   598		/*
   599		 * Enforce encrypted mapping consistency and avoid unaccepted
   600		 * memory conflicts, "lockdown" /dev/mem for confidential
   601		 * guests.
   602		 */
   603		if (IS_ENABLED(CONFIG_STRICT_DEVMEM) &&
 > 604		    cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT))
   605			return -EPERM;
   606	
   607		if (iminor(inode) != DEVMEM_MINOR)
   608			return 0;
   609	
   610		/*
   611		 * Use a unified address space to have a single point to manage
   612		 * revocations when drivers want to take over a /dev/mem mapped
   613		 * range.
   614		 */
   615		filp->f_mapping = iomem_get_mapping();
   616	
   617		return 0;
   618	}
   619

---

## [7] kernel test robot — 2025-04-18
*Subject: Re: [PATCH v3 2/2] x86/devmem: Drop /dev/mem access for confidential
 guests*

Hi Dan,

kernel test robot noticed the following build errors:

[auto build test ERROR on 0af2f6be1b4281385b618cb86ad946eded089ac8]

url:    https://github.com/intel-lab-lkp/linux/commits/Dan-Williams/x86-devmem-Remove-duplicate-range_is_allowed-definition/20250418-031657
base:   0af2f6be1b4281385b618cb86ad946eded089ac8
patch link:    https://lore.kernel.org/r/174491712829.1395340.5054725417641299524.stgit%40dwillia2-xfh.jf.intel.com
patch subject: [PATCH v3 2/2] x86/devmem: Drop /dev/mem access for confidential guests
config: arm-randconfig-004-20250418 (https://download.01.org/0day-ci/archive/20250418/202504180754.vQCz7zWh-lkp@intel.com/config)
compiler: clang version 21.0.0git (https://github.com/llvm/llvm-project f819f46284f2a79790038e1f6649172789734ae8)
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20250418/202504180754.vQCz7zWh-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202504180754.vQCz7zWh-lkp@intel.com/

All errors (new ones prefixed by >>):

>> drivers/char/mem.c:604:6: error: call to undeclared function 'cc_platform_has'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration]
     604 |             cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT))
         |             ^
>> drivers/char/mem.c:604:22: error: use of undeclared identifier 'CC_ATTR_GUEST_MEM_ENCRYPT'
     604 |             cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT))
         |                             ^
   2 errors generated.


vim +/cc_platform_has +604 drivers/char/mem.c

   586	
   587	static int open_port(struct inode *inode, struct file *filp)
   588	{
   589		int rc;
   590	
   591		if (!capable(CAP_SYS_RAWIO))
   592			return -EPERM;
   593	
   594		rc = security_locked_down(LOCKDOWN_DEV_MEM);
   595		if (rc)
   596			return rc;
   597	
   598		/*
   599		 * Enforce encrypted mapping consistency and avoid unaccepted
   600		 * memory conflicts, "lockdown" /dev/mem for confidential
   601		 * guests.
   602		 */
   603		if (IS_ENABLED(CONFIG_STRICT_DEVMEM) &&
 > 604		    cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT))
   605			return -EPERM;
   606	
   607		if (iminor(inode) != DEVMEM_MINOR)
   608			return 0;
   609	
   610		/*
   611		 * Use a unified address space to have a single point to manage
   612		 * revocations when drivers want to take over a /dev/mem mapped
   613		 * range.
   614		 */
   615		filp->f_mapping = iomem_get_mapping();
   616	
   617		return 0;
   618	}
   619

---

## [8] Dan Williams — 2025-04-18
*Subject: [PATCH v4 2/2] x86/devmem: Drop /dev/mem access for confidential
 guests*

Nikolay reports [1] that accessing BIOS data (first 1MB of the physical
address space) via /dev/mem results in an SEPT violation.

The cause is ioremap() (via xlate_dev_mem_ptr()) establishes an
unencrypted mapping where the kernel had established an encrypted
mapping previously.

Linux traps read(2) access to the BIOS data area, and returns zero.
However, it turns out the kernel fails to enforce the same via mmap(2).
This is a hole, and unfortunately userspace has learned to exploit it
[2].

This means the kernel either needs a mechanism to ensure consistent
"encrypted" mappings of this /dev/mem mmap() hole, close the hole by
mapping the zero page in the mmap(2) path, block only BIOS data access
and let typical STRICT_DEVMEM protect the rest, or disable /dev/mem
altogether.

The simplest option for now is arrange for /dev/mem to always behave as
if lockdown is enabled for confidential guests. Require confidential
guest userspace to jettison legacy dependencies on /dev/mem similar to
how other legacy mechanisms are jettisoned for confidential operation.
Recall that modern methods for BIOS data access are available like
/sys/firmware/dmi/tables.

Cc: <x86@kernel.org>
Cc: Kees Cook <kees@kernel.org>
Cc: Ingo Molnar <mingo@kernel.org>
Cc: "Naveen N Rao" <naveen@kernel.org>
Cc: Vishal Annapurve <vannapurve@google.com>
Cc: Kirill Shutemov <kirill.shutemov@linux.intel.com>
Link: https://sources.debian.org/src/libdebian-installer/0.125/src/system/subarch-x86-linux.c/?hl=113#L93 [2]
Reported-by: Nikolay Borisov <nik.borisov@suse.com>
Closes: http://lore.kernel.org/20250318113604.297726-1-nik.borisov@suse.com [1]
Fixes: 9aa6ea69852c ("x86/tdx: Make pages shared in ioremap()")
Cc: <stable@vger.kernel.org>
Acked-by: Dave Hansen <dave.hansen@linux.intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
Changes since v3
* Fix a 0day kbuild robot report about missing cc_platform.h include.

 arch/x86/Kconfig   |    4 ++++
 drivers/char/mem.c |   10 ++++++++++
 2 files changed, 14 insertions(+)

diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
index 4b9f378e05f6..bf4528d9fd0a 100644
--- a/arch/x86/Kconfig
+++ b/arch/x86/Kconfig
@@ -891,6 +891,8 @@ config INTEL_TDX_GUEST
 	depends on X86_X2APIC
 	depends on EFI_STUB
 	depends on PARAVIRT
+	depends on STRICT_DEVMEM
+	depends on IO_STRICT_DEVMEM
 	select ARCH_HAS_CC_PLATFORM
 	select X86_MEM_ENCRYPT
 	select X86_MCE
@@ -1510,6 +1512,8 @@ config AMD_MEM_ENCRYPT
 	bool "AMD Secure Memory Encryption (SME) support"
 	depends on X86_64 && CPU_SUP_AMD
 	depends on EFI_STUB
+	depends on STRICT_DEVMEM
+	depends on IO_STRICT_DEVMEM
 	select DMA_COHERENT_POOL
 	select ARCH_USE_MEMREMAP_PROT
 	select INSTRUCTION_DECODER
diff --git a/drivers/char/mem.c b/drivers/char/mem.c
index 48839958b0b1..47729606b817 100644
--- a/drivers/char/mem.c
+++ b/drivers/char/mem.c
@@ -30,6 +30,7 @@
 #include <linux/uio.h>
 #include <linux/uaccess.h>
 #include <linux/security.h>
+#include <linux/cc_platform.h>
 
 #define DEVMEM_MINOR	1
 #define DEVPORT_MINOR	4
@@ -595,6 +596,15 @@ static int open_port(struct inode *inode, struct file *filp)
 	if (rc)
 		return rc;
 
+	/*
+	 * Enforce encrypted mapping consistency and avoid unaccepted
+	 * memory conflicts, "lockdown" /dev/mem for confidential
+	 * guests.
+	 */
+	if (IS_ENABLED(CONFIG_STRICT_DEVMEM) &&
+	    cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT))
+		return -EPERM;
+
 	if (iminor(inode) != DEVMEM_MINOR)
 		return 0;

---

## [9] Nikolay Borisov — 2025-04-22
*Subject: Re: [PATCH v4 2/2] x86/devmem: Drop /dev/mem access for confidential
 guests*

On 18.04.25 г. 23:04 ч., Dan Williams wrote:
> Nikolay reports [1] that accessing BIOS data (first 1MB of the physical
> address space) via /dev/mem results in an SEPT violation.

Just confirming - the STRIC_DEVMEM check here is needed in case other 
CoCo technologies i.e ARM's CCA or risc-v tvm doesn't depend on it? 
Because for the x86 world it's redundant since both implementations 
imply STRICT_DEVMEM.


> +
>   	if (iminor(inode) != DEVMEM_MINOR)

---

## [10] Nikolay Borisov — 2025-04-22
*Subject: Re: [PATCH v3 0/2] Restrict devmem for confidential VMs*

On 17.04.25 г. 22:11 ч., Dan Williams wrote:
> Changes since v2 [1]:
> * Drop the new x86_platform_op and just use


Reviewed-by: Nikolay Borisov <nik.borisov@suse.com>

---

## [11] Naveen N Rao — 2025-04-23
*Subject: Re: [PATCH v4 2/2] x86/devmem: Drop /dev/mem access for confidential
 guests*

On Fri, Apr 18, 2025 at 01:04:02PM -0700, Dan Williams wrote:
> Nikolay reports [1] that accessing BIOS data (first 1MB of the physical
> address space) via /dev/mem results in an SEPT violation.

As far as I know, AMD_MEM_ENCRYPT is for the host SME support. Since 
this is for encrypted guests, should the below dependencies be added to 
CONFIG_SEV_GUEST instead?

Tom?

>  	bool "AMD Secure Memory Encryption (SME) support"
>  	depends on X86_64 && CPU_SUP_AMD

Can we use 'select' for the dependency on IO_STRICT_DEVMEM, if not both 
the above?

IO_STRICT_DEVMEM in particular is not enabled by default, so applying 
this patch and doing a 'make olddefconfig' disabled AMD_MEM_ENCRYPT, 
which is not so good. Given that IO_STRICT_DEVMEM only depends on 
STRICT_DEVMEM, I think a 'select' is ok.

>  	select DMA_COHERENT_POOL
>  	select ARCH_USE_MEMREMAP_PROT

Otherwise, this looks good to me.


- Naveen

---

## [12] Dan Williams — 2025-04-23
*Subject: Re: [PATCH v4 2/2] x86/devmem: Drop /dev/mem access for confidential
 guests*

Naveen N Rao wrote:
> On Fri, Apr 18, 2025 at 01:04:02PM -0700, Dan Williams wrote:
> > Nikolay reports [1] that accessing BIOS data (first 1MB of the physical

The placement rationale here was to have the DEVMEM restrictions next to
the ARCH_HAS_CC_PLATFORM 'select' statement which is INTEL_TDX_GUEST
and AMD_MEM_ENCRYPT with SEV_GUEST depending on AMD_MEM_ENCRYPT.

> >  	bool "AMD Secure Memory Encryption (SME) support"
> >  	depends on X86_64 && CPU_SUP_AMD

Agree, that makes sense, and I do not think it will lead to any select
dependency problems given STRICT_DEVMEM is "default y" for x86.

> 
> >  	select DMA_COHERENT_POOL

Thanks Naveen, can I take that as an Acked-by?

---

## [13] Naveen N Rao — 2025-04-24
*Subject: Re: [PATCH v4 2/2] x86/devmem: Drop /dev/mem access for confidential
 guests*

[Actually copy Tom]

On Wed, Apr 23, 2025 at 01:36:33PM -0700, Dan Williams wrote:
> Naveen N Rao wrote:
> > On Fri, Apr 18, 2025 at 01:04:02PM -0700, Dan Williams wrote:

Yes. I tested this and it solves the issue we see with SEV-SNP guest 
userspace access to video ROM range. For this patch:
Acked-by: Naveen N Rao (AMD) <naveen@kernel.org>
Tested-by: Naveen N Rao (AMD) <naveen@kernel.org>


Thanks,
Naveen

---

## [14] Dave Hansen — 2025-04-28
*Subject: Re: [PATCH v3 0/2] Restrict devmem for confidential VMs*

On 4/17/25 12:11, Dan Williams wrote:
>  arch/x86/Kconfig          |    4 ++++
>  arch/x86/mm/pat/memtype.c |   31 ++++---------------------------

This looks like a good idea on multiple levels. We can take it through
tip, but one things that makes me nervous is that neither of the "CHAR
and MISC DRIVERS" supporters are even on cc.

> Arnd Bergmann <arnd@arndb.de> (supporter:CHAR and MISC DRIVERS)
> Greg Kroah-Hartman <gregkh@linuxfoundation.org> (supporter:CHAR and MISC DRIVERS)

I guess arm and powerpc have cc_platform_has() so it's not _completely_
x86 only, either. Acks from those folks would also be appreciated since
it's going to affect them most immediately.

Also, just to confirm, patch 2 can go to stable@ without _any_
dependency on patch 1, right?

---

## [15] Dave Hansen — 2025-04-28
*Subject: Re: [PATCH v4 2/2] x86/devmem: Drop /dev/mem access for confidential
 guests*

On 4/18/25 13:04, Dan Williams wrote:
> Nikolay reports [1] that accessing BIOS data (first 1MB of the physical
> address space) via /dev/mem results in an SEPT violation.

Would most developers reading this know what an "SEPT violation" is or
what its implications are?

This results in an immediate exit from and termination of the TDX guest,
right?

---

## [16] Jianxiong Gao — 2025-04-28
*Subject: Re: [PATCH v4 2/2] x86/devmem: Drop /dev/mem access for confidential guests*

On Mon, Apr 28, 2025 at 8:53 AM Dave Hansen <dave.hansen@intel.com> wrote:
>
> Would most developers reading this know what an "SEPT violation" is or
In most cases yes but it depends on the settings.

If TDX_TD_ATTRIBUTES_SEPT_VE_DISABLE is set then the TDX guest
is terminated immediately.

Otherwise a #VE is generated for the guest to handle.

TDX_TD_ATTRIBUTES_SEPT_VE_DISABLE is disabled by default. See [1].

[1] https://lore.kernel.org/all/20250401130205.2198253-11-xiaoyao.li@intel.com/

---

## [17] Dave Hansen — 2025-04-28
*Subject: Re: [PATCH v4 2/2] x86/devmem: Drop /dev/mem access for confidential
 guests*

On 4/28/25 09:30, Jianxiong Gao wrote:
> On Mon, Apr 28, 2025 at 8:53 AM Dave Hansen <dave.hansen@intel.com> wrote:
>> Would most developers reading this know what an "SEPT violation" is or

There's also disable_sept_ve() in the kernel.

So perhaps I should have said:

	This <normally*> results in an immediate exit from and
	termination of the TDX guest right?

	 * Ignoring debug and other non-production silliness

---

## [18] Dan Williams — 2025-04-28
*Subject: Re: [PATCH v3 0/2] Restrict devmem for confidential VMs*

Dave Hansen wrote:
> On 4/17/25 12:11, Dan Williams wrote:
> >  arch/x86/Kconfig          |    4 ++++

Good catch, just note that until this latest iteration the proposal was
entirely contained to x86 specific support functions like devmem_is_allowed().
So yes, an oversight as this moved to a more general devmem mechanism.

> I guess arm and powerpc have cc_platform_has() so it's not _completely_
> x86 only, either. Acks from those folks would also be appreciated since

I have added Suzuki and Michael for their awareness, but I would not say
acks are needed at this point since to date CC_ATTR_GUEST_MEM_ENCRYPT is
strictly an x86-ism.

For example, the PowerPC implementation of cc_platform_has() has not been
touched since Tom added it. 

Suzuki, Michael, at a minimum the question this patch poses to ARM64 and
PowerPC is whether they are going to allow CONFIG_STRICT_DEVMEM=n, or otherwise
understand that CONFIG_STRICT_DEVMEM=y == LOCKDOWN with
CC_ATTR_GUEST_MEM_ENCRYPT.

> Also, just to confirm, patch 2 can go to stable@ without _any_
> dependency on patch 1, right?

Correct. I will make them independent / unordered patches on the repost.

Next posting to fix the "select" instead of "depends on" dependency
management, h/t Naveen, and clarify the "'crash' vs 'SEPT violation'"
description.

---

## [19] Dave Hansen — 2025-04-28
*Subject: Re: [PATCH v3 0/2] Restrict devmem for confidential VMs*

On 4/28/25 15:48, Dan Williams wrote:
>> I guess arm and powerpc have cc_platform_has() so it's not _completely_
>> x86 only, either. Acks from those folks would also be appreciated since

Ahh, good point. I was just grepping for cc_platform_has(), not
CC_ATTR_GUEST_MEM_ENCRYPT. Unless someone pipes up, I'd agree that acks
aren't required. Thanks for adding them to the cc though.

---

## [20] Suzuki K Poulose — 2025-04-30
*Subject: Re: [PATCH v3 0/2] Restrict devmem for confidential VMs*

Hi Dan

On 28/04/2025 23:48, Dan Williams wrote:
> Dave Hansen wrote:
>> On 4/17/25 12:11, Dan Williams wrote:

For CCA we don't really enforce STRICT_DEVMEM. But we do expect people
to use it for safety reasons, but is not mandatory.

Does that help ?

Suzuki



> 
>> Also, just to confirm, patch 2 can go to stable@ without _any_

---

## [21] kernel test robot — 2025-05-07
*Subject: Re: [PATCH v3 2/2] x86/devmem: Drop /dev/mem access for confidential
 guests*

Hi Dan,

kernel test robot noticed the following build errors:

[auto build test ERROR on 0af2f6be1b4281385b618cb86ad946eded089ac8]

url:    https://github.com/intel-lab-lkp/linux/commits/Dan-Williams/x86-devmem-Remove-duplicate-range_is_allowed-definition/20250419-080713
base:   0af2f6be1b4281385b618cb86ad946eded089ac8
patch link:    https://lore.kernel.org/r/174491712829.1395340.5054725417641299524.stgit%40dwillia2-xfh.jf.intel.com
patch subject: [PATCH v3 2/2] x86/devmem: Drop /dev/mem access for confidential guests
config: openrisc-randconfig-r073-20250428 (https://download.01.org/0day-ci/archive/20250507/202505071309.Aa4vRJxa-lkp@intel.com/config)
compiler: or1k-linux-gcc (GCC) 10.5.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20250507/202505071309.Aa4vRJxa-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202505071309.Aa4vRJxa-lkp@intel.com/

All errors (new ones prefixed by >>):

   drivers/char/mem.c: In function 'open_port':
>> drivers/char/mem.c:604:6: error: implicit declaration of function 'cc_platform_has' [-Werror=implicit-function-declaration]
     604 |      cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT))
         |      ^~~~~~~~~~~~~~~
>> drivers/char/mem.c:604:22: error: 'CC_ATTR_GUEST_MEM_ENCRYPT' undeclared (first use in this function)
     604 |      cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT))
         |                      ^~~~~~~~~~~~~~~~~~~~~~~~~
   drivers/char/mem.c:604:22: note: each undeclared identifier is reported only once for each function it appears in
   cc1: some warnings being treated as errors


vim +/cc_platform_has +604 drivers/char/mem.c

   586	
   587	static int open_port(struct inode *inode, struct file *filp)
   588	{
   589		int rc;
   590	
   591		if (!capable(CAP_SYS_RAWIO))
   592			return -EPERM;
   593	
   594		rc = security_locked_down(LOCKDOWN_DEV_MEM);
   595		if (rc)
   596			return rc;
   597	
   598		/*
   599		 * Enforce encrypted mapping consistency and avoid unaccepted
   600		 * memory conflicts, "lockdown" /dev/mem for confidential
   601		 * guests.
   602		 */
   603		if (IS_ENABLED(CONFIG_STRICT_DEVMEM) &&
 > 604		    cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT))
   605			return -EPERM;
   606	
   607		if (iminor(inode) != DEVMEM_MINOR)
   608			return 0;
   609	
   610		/*
   611		 * Use a unified address space to have a single point to manage
   612		 * revocations when drivers want to take over a /dev/mem mapped
   613		 * range.
   614		 */
   615		filp->f_mapping = iomem_get_mapping();
   616	
   617		return 0;
   618	}
   619

---
