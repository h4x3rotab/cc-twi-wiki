---
title: 'x86/tdx: Fix data leak in mmio_read()'
date: 2024-08-26
last_reply: 2024-08-26
message_count: 3
participants: ['Kirill A. Shutemov', 'Dave Hansen']
---

## [1] Kirill A. Shutemov — 2024-08-26

The mmio_read() function makes a TDVMCALL to retrieve MMIO data for an
address from the VMM.

Sean noticed that mmio_read() unintentionally exposes the value of an
initialized variable on the stack to the VMM.

Do not send the original value of *val to the VMM.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reported-by: Sean Christopherson <seanjc@google.com>
Fixes: 31d58c4e557d ("x86/tdx: Handle in-kernel MMIO")
Cc: stable@vger.kernel.org # v5.19+
---
 arch/x86/coco/tdx/tdx.c | 1 -
 1 file changed, 1 deletion(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 078e2bac2553..da8b66dce0da 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -389,7 +389,6 @@ static bool mmio_read(int size, unsigned long addr, unsigned long *val)
 		.r12 = size,
 		.r13 = EPT_READ,
 		.r14 = addr,
-		.r15 = *val,
 	};
 
 	if (__tdx_hypercall(&args))

---

## [2] Dave Hansen — 2024-08-26
*Subject: Re: [PATCH] x86/tdx: Fix data leak in mmio_read()*

On 8/26/24 05:53, Kirill A. Shutemov wrote:
> The mmio_read() function makes a TDVMCALL to retrieve MMIO data for an
> address from the VMM.

The key to this is that 'val' is only used for the _return_ value, right?

---

## [3] Kirill A. Shutemov — 2024-08-26
*Subject: Re: [PATCH] x86/tdx: Fix data leak in mmio_read()*

On Mon, Aug 26, 2024 at 09:41:49AM -0700, Dave Hansen wrote:
> On 8/26/24 05:53, Kirill A. Shutemov wrote:
> > The mmio_read() function makes a TDVMCALL to retrieve MMIO data for an

Correct.

---
