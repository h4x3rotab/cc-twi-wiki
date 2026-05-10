---
title: 'x86/tdx: Enable #VE reduction feature'
date: 2024-12-02
last_reply: 2024-12-03
message_count: 2
participants: ['Kirill A. Shutemov', 'Nikolay Borisov']
---

## [1] Kirill A. Shutemov — 2024-12-02

Originally, #VE was defined as the TDX behavior in order to support
paravirtualization of x86 features that can’t be virtualized by the TDX
module. The intention is that if guest software wishes to use such a
feature, it implements some logic to support this. This logic resides in
the #VE exception handler it may work in cooperation with the host VMM.

Theoretically, the guest TD’s #VE handler was supposed to act as a "TDX
enlightenment agent" inside the TD. However, in practice, the #VE
handler is simplistic:

  - #VE on CPUID is handled by returning all-0 to the code which
    executed CPUID. In many cases, an all-0 value is not the correct
    value, and may cause improper operation.

  - #VE on RDMSR is handled by requesting the MSR value from the host
    VMM. This is prone to security issues since the host VMM is
    untrusted. It may also be functionally incorrect in case the
    expected operation is to paravirtualize some CPU functionality.

Newer TDX module provides REDUCE_VE feature. When enabled, it
drastically cuts cases when guests receives #VE on MSR and CPUID
accesses. Behaviour of a specific MSR or CPUID leaf/sub-leaf is defined
in the TDX spec.

Enable REDUCE_VE. It brings TDX guest behaviour less odd, bring it
closer to an architectural.

Note that enabling of the feature doesn't eliminate need in #VE handler
for CPUID and MSR accesses. Some MSRs still generate #VE (notably
APIC-related) and kernel needs CPUID #VE handler to ask VMM for leafs in
hypervisor range.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/coco/tdx/tdx.c           | 14 +++++++++++++-
 arch/x86/include/asm/shared/tdx.h |  1 +
 2 files changed, 14 insertions(+), 1 deletion(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 0d9b090b4880..7285502f3048 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -274,6 +274,11 @@ static void enable_cpu_topology_enumeration(void)
 	tdg_vm_wr(TDCS_TD_CTLS, TD_CTLS_ENUM_TOPOLOGY, TD_CTLS_ENUM_TOPOLOGY);
 }
 
+static bool enable_reduce_ve(void)
+{
+	return !tdg_vm_wr(TDCS_TD_CTLS, TD_CTLS_REDUCE_VE, TD_CTLS_REDUCE_VE);
+}
+
 static void tdx_setup(u64 *cc_mask)
 {
 	struct tdx_module_args args = {};
@@ -305,7 +310,14 @@ static void tdx_setup(u64 *cc_mask)
 	tdg_vm_wr(TDCS_NOTIFY_ENABLES, 0, -1ULL);
 
 	disable_sept_ve(td_attr);
-	enable_cpu_topology_enumeration();
+
+	/*
+	 * Enabling REDUCE_VE includes ENUM_TOPOLOGY.
+	 *
+	 * Try to enable REDUCE_VE. If it fails, try to enable ENUM_TOPOLOGY.
+	 */
+	if (!enable_reduce_ve())
+		enable_cpu_topology_enumeration();
 }
 
 /*
diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index 89f7fcade8ae..a878c7e8347b 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -31,6 +31,7 @@
 /* TDCS_TD_CTLS bits */
 #define TD_CTLS_PENDING_VE_DISABLE	BIT_ULL(0)
 #define TD_CTLS_ENUM_TOPOLOGY		BIT_ULL(1)
+#define TD_CTLS_REDUCE_VE		BIT_ULL(3)
 
 /* TDX hypercall Leaf IDs */
 #define TDVMCALL_MAP_GPA		0x10001

---

## [2] Nikolay Borisov — 2024-12-03
*Subject: Re: [PATCH] x86/tdx: Enable #VE reduction feature*

On 2.12.24 г. 9:24 ч., Kirill A. Shutemov wrote:
> Originally, #VE was defined as the TDX behavior in order to support
> paravirtualization of x86 features that can’t be virtualized by the TDX

Reviewed-by: Nikolay Borisov <nik.borisov@suse.com>


<snip>

---
