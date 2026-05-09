---
title: 'x86/tdx, memory hotplug: Check whole hot-adding memory range for TDX'
date: 2024-10-22
last_reply: 2024-10-22
message_count: 3
participants: ['Huang Ying', 'Oscar Salvador']
---

## [1] Huang Ying — 2024-10-22

On systems with TDX (Trust Domain eXtensions) enabled, current kernel
checks the TDX compatibility of the hot-added memory ranges through a
memory hotplug notifier for each memory_block.  If a memory range
which isn't TDX compatible is hot-added, for example, some CXL memory,
the command line as follows,

  $ echo 1 > /sys/devices/system/node/nodeX/memoryY/online

will report something like,

  bash: echo: write error: Operation not permitted

If pr_debug() is enabled, current kernel will show the error message
like below in the kernel log,

  online_pages [mem 0xXXXXXXXXXX-0xXXXXXXXXXX] failed

Both are too general to root cause the problem.  This may confuse
users.  One solution is to print some error messages in the TDX memory
hotplug notifier.  However, kernel calls memory hotplug notifiers for
each memory block, so this may lead to a large volume of messages in
the kernel log if a large number of memory blocks are onlined with a
script or automatically.  For example, the typical size of memory
block is 128MB on x86_64, when online 64GB CXL memory, 512 messages
will be logged.

Therefore, this patch checks the TDX compatibility of the whole
hot-adding memory range through a newly added architecture specific
function (arch_check_hotplug_memory_range()).  If this patch rejects
the memory hot-adding for TDX compatibility, it will output a kernel
log message like below,

  virt/tdx: Reject hot-adding memory range: 0xXXXXXXXX-0xXXXXXXXX for TDX compatibility.

The target use case is to support CXL memory on TDX enabled systems.
If the CXL memory isn't compatible with TDX, the kernel will reject
the whole CXL memory range.  While the CXL memory can still be used
via devdax interface.

This also makes the original TDX memory hotplug notifier useless, so
this patch deletes it.

Signed-off-by: "Huang, Ying" <ying.huang@intel.com>
Suggested-by: Dan Williams <dan.j.williams@intel.com>
Reviewed-by: Dan Williams <dan.j.williams@intel.com>
Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Acked-by: Kai Huang <kai.huang@intel.com>
Acked-by: David Hildenbrand <david@redhat.com>
Cc: Thomas Gleixner <tglx@linutronix.de>
Cc: Dave Hansen <dave.hansen@linux.intel.com>
Cc: "H. Peter Anvin" <hpa@zytor.com>
Cc: Andy Lutomirski <luto@kernel.org>
Cc: Oscar Salvador <osalvador@suse.de>
---

Changes:

v3:

- Rebased on v6.12-rc4

- Revise the patch description.

- Link to v2: https://lore.kernel.org/linux-mm/20241010074726.1397820-1-ying.huang@intel.com/

v2:

- Collected reviewed-by and acked-by.

- Added comments for tdx_check_hotplug_memory_range(), Thanks David!

- Link to v1: https://lore.kernel.org/lkml/20240930055112.344206-1-ying.huang@intel.com/
---
 arch/x86/include/asm/tdx.h     |  2 ++
 arch/x86/mm/init_64.c          |  6 +++++
 arch/x86/virt/vmx/tdx/tdx.c    | 40 +++++++++++++++-------------------
 include/linux/memory_hotplug.h |  3 +++
 mm/memory_hotplug.c            |  7 +++++-
 5 files changed, 34 insertions(+), 24 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index eba178996d84..6db5da34e4ba 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -116,11 +116,13 @@ static inline u64 sc_retry(sc_func_t func, u64 fn,
 int tdx_cpu_enable(void);
 int tdx_enable(void);
 const char *tdx_dump_mce_info(struct mce *m);
+int tdx_check_hotplug_memory_range(u64 start, u64 size);
 #else
 static inline void tdx_init(void) { }
 static inline int tdx_cpu_enable(void) { return -ENODEV; }
 static inline int tdx_enable(void)  { return -ENODEV; }
 static inline const char *tdx_dump_mce_info(struct mce *m) { return NULL; }
+static inline int tdx_check_hotplug_memory_range(u64 start, u64 size) { return 0; }
 #endif	/* CONFIG_INTEL_TDX_HOST */
 
 #endif /* !__ASSEMBLY__ */
diff --git a/arch/x86/mm/init_64.c b/arch/x86/mm/init_64.c
index ff253648706f..30a4ad4272ce 100644
--- a/arch/x86/mm/init_64.c
+++ b/arch/x86/mm/init_64.c
@@ -55,6 +55,7 @@
 #include <asm/uv/uv.h>
 #include <asm/setup.h>
 #include <asm/ftrace.h>
+#include <asm/tdx.h>
 
 #include "mm_internal.h"
 
@@ -974,6 +975,11 @@ int add_pages(int nid, unsigned long start_pfn, unsigned long nr_pages,
 	return ret;
 }
 
+int arch_check_hotplug_memory_range(u64 start, u64 size)
+{
+	return tdx_check_hotplug_memory_range(start, size);
+}
+
 int arch_add_memory(int nid, u64 start, u64 size,
 		    struct mhp_params *params)
 {
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 4e2b2e2ac9f9..f70b4ebe7cc5 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1388,36 +1388,37 @@ static bool is_tdx_memory(unsigned long start_pfn, unsigned long end_pfn)
 	return false;
 }
 
-static int tdx_memory_notifier(struct notifier_block *nb, unsigned long action,
-			       void *v)
+/*
+ * We don't allow mixture of TDX and !TDX memory in the buddy so we
+ * won't run into trouble when launching encrypted VMs that really
+ * need TDX-capable memory.
+ */
+int tdx_check_hotplug_memory_range(u64 start, u64 size)
 {
-	struct memory_notify *mn = v;
-
-	if (action != MEM_GOING_ONLINE)
-		return NOTIFY_OK;
+	u64 start_pfn = PHYS_PFN(start);
+	u64 end_pfn = PHYS_PFN(start + size);
 
 	/*
 	 * Empty list means TDX isn't enabled.  Allow any memory
-	 * to go online.
+	 * to be hot-added.
 	 */
 	if (list_empty(&tdx_memlist))
-		return NOTIFY_OK;
+		return 0;
 
 	/*
 	 * The TDX memory configuration is static and can not be
-	 * changed.  Reject onlining any memory which is outside of
+	 * changed.  Reject hot-adding any memory which is outside of
 	 * the static configuration whether it supports TDX or not.
 	 */
-	if (is_tdx_memory(mn->start_pfn, mn->start_pfn + mn->nr_pages))
-		return NOTIFY_OK;
+	if (is_tdx_memory(start_pfn, end_pfn))
+		return 0;
 
-	return NOTIFY_BAD;
+	pr_info("Reject hot-adding memory range: %#llx-%#llx for TDX compatibility.\n",
+		start, start + size);
+
+	return -EINVAL;
 }
 
-static struct notifier_block tdx_memory_nb = {
-	.notifier_call = tdx_memory_notifier,
-};
-
 static void __init check_tdx_erratum(void)
 {
 	/*
@@ -1465,13 +1466,6 @@ void __init tdx_init(void)
 		return;
 	}
 
-	err = register_memory_notifier(&tdx_memory_nb);
-	if (err) {
-		pr_err("initialization failed: register_memory_notifier() failed (%d)\n",
-				err);
-		return;
-	}
-
 #if defined(CONFIG_ACPI) && defined(CONFIG_SUSPEND)
 	pr_info("Disable ACPI S3. Turn off TDX in the BIOS to use ACPI S3.\n");
 	acpi_suspend_lowlevel = NULL;
diff --git a/include/linux/memory_hotplug.h b/include/linux/memory_hotplug.h
index b27ddce5d324..c5ba7b909bb4 100644
--- a/include/linux/memory_hotplug.h
+++ b/include/linux/memory_hotplug.h
@@ -140,6 +140,9 @@ extern int try_online_node(int nid);
 
 extern int arch_add_memory(int nid, u64 start, u64 size,
 			   struct mhp_params *params);
+
+extern int arch_check_hotplug_memory_range(u64 start, u64 size);
+
 extern u64 max_mem_size;
 
 extern int mhp_online_type_from_str(const char *str);
diff --git a/mm/memory_hotplug.c b/mm/memory_hotplug.c
index 621ae1015106..c4769f24b1e2 100644
--- a/mm/memory_hotplug.c
+++ b/mm/memory_hotplug.c
@@ -1305,6 +1305,11 @@ int try_online_node(int nid)
 	return ret;
 }
 
+int __weak arch_check_hotplug_memory_range(u64 start, u64 size)
+{
+	return 0;
+}
+
 static int check_hotplug_memory_range(u64 start, u64 size)
 {
 	/* memory range must be block size aligned */
@@ -1315,7 +1320,7 @@ static int check_hotplug_memory_range(u64 start, u64 size)
 		return -EINVAL;
 	}
 
-	return 0;
+	return arch_check_hotplug_memory_range(start, size);
 }
 
 static int online_memory_block(struct memory_block *mem, void *arg)

---

## [2] Oscar Salvador — 2024-10-22
*Subject: Re: [PATCH -V3] x86/tdx, memory hotplug: Check whole hot-adding
 memory range for TDX*

On Tue, Oct 22, 2024 at 11:16:17AM +0800, Huang Ying wrote:
> On systems with TDX (Trust Domain eXtensions) enabled, current kernel
> checks the TDX compatibility of the hot-added memory ranges through a

Acked-by: Oscar Salvador <osalvador@suse.de>

One question below:

...

> +int tdx_check_hotplug_memory_range(u64 start, u64 size)
>  {

Why not using pr_err() here?

I was checking which kind of information level we use when failing at
hot-adding memory, and we seem to be using pr_err(), and pr_debug() when
onlining/offlining.

Not a big deal, and not saying it is wrong, but was just wondering the reasoning
behind.

---

## [3] Huang, Ying — 2024-10-22
*Subject: Re: [PATCH -V3] x86/tdx, memory hotplug: Check whole hot-adding
 memory range for TDX*

Hi, Oscar,

Oscar Salvador <osalvador@suse.de> writes:

> On Tue, Oct 22, 2024 at 11:16:17AM +0800, Huang Ying wrote:
>> On systems with TDX (Trust Domain eXtensions) enabled, current kernel

Thanks!

> One question below:
>

TBH, I have no strong opinion about which log level is more appropriate.
IMHO, it shouldn't be pr_debug() to make it easy for users to root cause
the hot-adding failure.  And, it appears too harsh to use pr_err(),
because there's no program error, etc.  So, I think that something
in-between is more appropriate.  That is, pr_warn(), pr_notice, or
pr_info().  In them, I prefer pr_info() a little.

--
Best Regards,
Huang, Ying

---
