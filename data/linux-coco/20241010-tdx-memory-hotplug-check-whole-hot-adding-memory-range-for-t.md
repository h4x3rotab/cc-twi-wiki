---
title: 'tdx, memory hotplug: Check whole hot-adding memory range for TDX'
date: 2024-10-10
last_reply: 2024-10-11
message_count: 8
participants: ['Huang Ying', 'David Hildenbrand']
---

## [1] Huang Ying — 2024-10-10

On systems with TDX (Trust Domain eXtensions) enabled, memory ranges
hot-added must be checked for compatibility by TDX.  This is currently
implemented through memory hotplug notifiers for each memory_block.
If a memory range which isn't TDX compatible is hot-added, for
example, some CXL memory, the command line as follows,

  $ echo 1 > /sys/devices/system/node/nodeX/memoryY/online

will report something like,

  bash: echo: write error: Operation not permitted

If pr_debug() is enabled, the error message like below will be shown
in the kernel log,

  online_pages [mem 0xXXXXXXXXXX-0xXXXXXXXXXX] failed

Both are too general to root cause the problem.  This will confuse
users.  One solution is to print some error messages in the TDX memory
hotplug notifier.  However, memory hotplug notifiers are called for
each memory block, so this may lead to a large volume of messages in
the kernel log if a large number of memory blocks are onlined with a
script or automatically.  For example, the typical size of memory
block is 128MB on x86_64, when online 64GB CXL memory, 512 messages
will be logged.

Therefore, in this patch, the whole hot-adding memory range is checked
for TDX compatibility through a newly added architecture specific
function (arch_check_hotplug_memory_range()).  If rejected, the memory
hot-adding will be aborted with a proper kernel log message.  Which
looks like something as below,

  virt/tdx: Reject hot-adding memory range: 0xXXXXXXXX-0xXXXXXXXX for TDX compatibility.

The target use case is to support CXL memory on TDX enabled systems.
If the CXL memory isn't compatible with TDX, the whole CXL memory
range hot-adding will be rejected.  While the CXL memory can still be
used via devdax interface.

This also makes the original TDX memory hotplug notifier useless, so
delete it.

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

## [2] David Hildenbrand — 2024-10-10
*Subject: Re: [PATCH -V2] tdx, memory hotplug: Check whole hot-adding memory
 range for TDX*

>   extern u64 max_mem_size;
>   

BTW, I remember that "__weak" doesn't always behave the way it would 
seem, which is the reason we're usually using

#define arch_check_hotplug_memory_range arch_check_hotplug_memory_range

#ifndef arch_check_hotplug_memory_range
...
#endif


Not that I remember the details, just that it can result in rather 
surprising outcomes (e.g., the wrong function getting called).

---

## [3] Huang, Ying — 2024-10-11
*Subject: Re: [PATCH -V2] tdx, memory hotplug: Check whole hot-adding memory
 range for TDX*

David Hildenbrand <david@redhat.com> writes:

>>   extern u64 max_mem_size;
>>     extern int mhp_online_type_from_str(const char *str);

I can replace __weak with #define/#ifndef.

However, it appears that "__weak" is still widely used now.

$ grep __weak -r mm kernel init | wc -l
231

--
Best Regards,
Huang, Ying

---

## [4] David Hildenbrand — 2024-10-11
*Subject: Re: [PATCH -V2] tdx, memory hotplug: Check whole hot-adding memory
 range for TDX*

On 11.10.24 03:27, Huang, Ying wrote:
> David Hildenbrand <david@redhat.com> writes:
> 

Probably better to avoid new ones. See also 
Documentation/dev-tools/checkpatch.rst

I assume checkpatch.pl should complain as well?

---

## [5] Huang, Ying — 2024-10-11
*Subject: Re: [PATCH -V2] tdx, memory hotplug: Check whole hot-adding memory
 range for TDX*

David Hildenbrand <david@redhat.com> writes:

> On 11.10.24 03:27, Huang, Ying wrote:
>> David Hildenbrand <david@redhat.com> writes:

Sure.  Will do that in the future versions.

> See also
> Documentation/dev-tools/checkpatch.rst

Double checked again.  It doesn't complain for that.

--
Best Regards,
Huang, Ying

---

## [6] David Hildenbrand — 2024-10-11
*Subject: Re: [PATCH -V2] tdx, memory hotplug: Check whole hot-adding memory
 range for TDX*

On 11.10.24 10:51, Huang, Ying wrote:
> David Hildenbrand <david@redhat.com> writes:
> 

Indeed, it only checks for usage of "weak" for *declarations*. So maybe 
it's fine after all and I am misremembering things. So just leave it as 
is for the time being.

---

## [7] David Hildenbrand — 2024-10-11
*Subject: Re: [PATCH -V2] tdx, memory hotplug: Check whole hot-adding memory
 range for TDX*

On 11.10.24 11:48, David Hildenbrand wrote:
> On 11.10.24 10:51, Huang, Ying wrote:
>> David Hildenbrand <david@redhat.com> writes:

For completeness, this is the issue I remembered:

commit 65d9a9a60fd71be964effb2e94747a6acb6e7015
Author: Naveen N Rao <naveen@kernel.org>
Date:   Fri Jul 1 13:04:04 2022 +0530

     kexec_file: drop weak attribute from functions
     
     As requested
     (http://lkml.kernel.org/r/87ee0q7b92.fsf@email.froward.int.ebiederm.org),
     this series converts weak functions in kexec to use the #ifdef approach.
     
     Quoting the 3e35142ef99fe ("kexec_file: drop weak attribute from
     arch_kexec_apply_relocations[_add]") changelog:
     
     : Since commit d1bcae833b32f1 ("ELF: Don't generate unused section symbols")
     : [1], binutils (v2.36+) started dropping section symbols that it thought
     : were unused.  This isn't an issue in general, but with kexec_file.c, gcc
     : is placing kexec_arch_apply_relocations[_add] into a separate
     : .text.unlikely section and the section symbol ".text.unlikely" is being
     : dropped.  Due to this, recordmcount is unable to find a non-weak symbol in
     : .text.unlikely to generate a relocation record against.

---

## [8] Huang, Ying — 2024-10-11
*Subject: Re: [PATCH -V2] tdx, memory hotplug: Check whole hot-adding memory
 range for TDX*

David Hildenbrand <david@redhat.com> writes:

> On 11.10.24 11:48, David Hildenbrand wrote:
>> On 11.10.24 10:51, Huang, Ying wrote:

Good to know this, Thanks!

--
Best Regards,
Huang, Ying

---
