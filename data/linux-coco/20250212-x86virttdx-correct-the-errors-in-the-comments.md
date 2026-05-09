---
title: 'x86/virt/tdx: Correct the errors in the comments'
date: 2025-02-12
last_reply: 2025-02-13
message_count: 3
participants: ['Jun Miao', 'Kirill A. Shutemov', 'Huang, Kai']
---

## [1] Jun Miao — 2025-02-12

In comment of config_global_keyid(), the "will fail" is duplicate, delete it.

Signed-off-by: Jun Miao <jun.miao@intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 7fdb37387886..2023216a04a9 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -961,8 +961,8 @@ static int do_global_key_config(void *unused)
  * Attempt to configure the global KeyID on all physical packages.
  *
  * This requires running code on at least one CPU in each package.
- * TDMR initialization) will fail will fail if any package in the
- * system has no online CPUs.
+ * TDMR initialization) will fail if any package in the system has
+ * no online CPUs.
  *
  * This code takes no affirmative steps to online CPUs.  Callers (aka.
  * KVM) can ensure success by ensuring sufficient CPUs are online and

---

## [2] Kirill A. Shutemov — 2025-02-12
*Subject: Re: [PATCH] x86/virt/tdx: Correct the errors in the comments*

On Wed, Feb 12, 2025 at 03:58:05PM +0800, Jun Miao wrote:
> In comment of config_global_keyid(), the "will fail" is duplicate, delete it.

  In the comment for config_global_keyid(), the phrase "will fail" is
  duplicated. Remove it.

> Signed-off-by: Jun Miao <jun.miao@intel.com>

Acked-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

---

## [3] Huang, Kai — 2025-02-13
*Subject: Re: [PATCH] x86/virt/tdx: Correct the errors in the comments*

On 13/02/2025 1:01 am, Kirill A. Shutemov wrote:
> On Wed, Feb 12, 2025 at 03:58:05PM +0800, Jun Miao wrote:
>> In comment of config_global_keyid(), the "will fail" is duplicate, delete it.

Acked-by: Kai Huang <kai.huang@intel.com>

---
