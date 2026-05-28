---
title: 'x86/tdx: Port I/O emulation fixes'
date: 2026-05-27
last_reply: 2026-05-27
message_count: 6
participants: ['Kiryl Shutsemau (Meta)', 'Edgecombe, Rick P', 'Dave Hansen']
---

## [1] Kiryl Shutsemau (Meta) — 2026-05-27

This series addresses two technical inaccuracies in the TDX guest port
I/O emulation code reported by Borys Tsyrulnikov.

The first patch fixes an off-by-one error in the GENMASK() macro usage
where the mask was being calculated as one bit too wide (e.g. 9 bits for
an 8-bit operation).

The second patch ensures that 32-bit port I/O operations (INL) correctly
zero-extend the result to the full 64-bit RAX register, as required by
the x86 architecture. Currently, the emulation preserves the upper 32
bits of RAX during such operations.

Both issues were introduced in the initial implementation of the runtime
hypercalls for port I/O.

v1: https://lore.kernel.org/all/20260331112430.71425-1-kas@kernel.org/
v2: https://lore.kernel.org/all/20260428125632.129770-1-kas@kernel.org/

Changes in v3:
  - Expand the comment in patch 2 with a table describing which RAX
    bits each IN form writes vs preserves, clarifying why the 32-bit
    case needs to clear RAX[63:32] (Dave Hansen).
  - Rebase onto v7.1-rc5.

Changes in v2:
  - Rephrase the size check in handle_in() as "if (size == 4)" for
    readability (Kuppuswamy)
  - Add Link: to the bug report on both patches (Kuppuswamy)
  - Collect Reviewed-by tags (Kai Huang, Kuppuswamy Sathyanarayanan)
  - Rebase onto v7.1-rc1

Kiryl Shutsemau (Meta) (2):
  x86/tdx: Fix off-by-one in port I/O handling
  x86/tdx: Fix zero-extension for 32-bit port I/O

 arch/x86/coco/tdx/tdx.c | 25 +++++++++++++++++++++----
 1 file changed, 21 insertions(+), 4 deletions(-)


base-commit: e7ae89a0c97ce2b68b0983cd01eda67cf373517d

---

## [2] Kiryl Shutsemau (Meta) — 2026-05-27
*Subject: [PATCH v3 1/2] x86/tdx: Fix off-by-one in port I/O handling*

handle_in() and handle_out() in arch/x86/coco/tdx/tdx.c use:

    u64 mask = GENMASK(BITS_PER_BYTE * size, 0);

GENMASK(h, l) includes bit h. For size=1 (INB), this produces
GENMASK(8, 0) = 0x1FF (9 bits) instead of GENMASK(7, 0) = 0xFF (8
bits). The mask is one bit too wide for all I/O sizes.

Fix the mask calculation.

Fixes: 03149948832a ("x86/tdx: Port I/O: Add runtime hypercalls")
Reported-by: Borys Tsyrulnikov <tsyrulnikov.borys@gmail.com>
Link: https://lore.kernel.org/all/CAKw_Dz96rfSQc6Rn+9QBcUFHhmkK+9zu+P=bxowfZwxrATCBRg@mail.gmail.com/
Signed-off-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Cc: stable@vger.kernel.org
---
 arch/x86/coco/tdx/tdx.c | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 186915a17c50..65119362f9a2 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -693,7 +693,7 @@ static bool handle_in(struct pt_regs *regs, int size, int port)
 		.r13 = PORT_READ,
 		.r14 = port,
 	};
-	u64 mask = GENMASK(BITS_PER_BYTE * size, 0);
+	u64 mask = GENMASK(BITS_PER_BYTE * size - 1, 0);
 	bool success;
 
 	/*
@@ -713,7 +713,7 @@ static bool handle_in(struct pt_regs *regs, int size, int port)
 
 static bool handle_out(struct pt_regs *regs, int size, int port)
 {
-	u64 mask = GENMASK(BITS_PER_BYTE * size, 0);
+	u64 mask = GENMASK(BITS_PER_BYTE * size - 1, 0);
 
 	/*
 	 * Emulate the I/O write via hypercall. More info about ABI can be found

---

## [3] Kiryl Shutsemau (Meta) — 2026-05-27
*Subject: [PATCH v3 2/2] x86/tdx: Fix zero-extension for 32-bit port I/O*

According to x86 architecture rules, 32-bit operations zero-extend the
result to 64 bits. The current implementation of handle_in() only masks
the lower 32 bits, which preserves the upper 32 bits of RAX when a
32-bit port IN instruction is emulated.

Update handle_in() to zero out the entire RAX register when the I/O size
is 4 bytes to ensure correct zero-extension. For smaller sizes (1 or 2
bytes), continue to preserve the unaffected upper bits.

Fixes: 03149948832a ("x86/tdx: Port I/O: Add runtime hypercalls")
Reported-by: Borys Tsyrulnikov <tsyrulnikov.borys@gmail.com>
Link: https://lore.kernel.org/all/CAKw_Dz96rfSQc6Rn+9QBcUFHhmkK+9zu+P=bxowfZwxrATCBRg@mail.gmail.com/
Signed-off-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Cc: stable@vger.kernel.org
---
 arch/x86/coco/tdx/tdx.c | 21 +++++++++++++++++++--
 1 file changed, 19 insertions(+), 2 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 65119362f9a2..58feca419326 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -703,8 +703,25 @@ static bool handle_in(struct pt_regs *regs, int size, int port)
 	 */
 	success = !__tdx_hypercall(&args);
 
-	/* Update part of the register affected by the emulated instruction */
-	regs->ax &= ~mask;
+	/*
+	 * IN writes the result into a sub-register of RAX. Only the
+	 * 32-bit form zero-extends; the smaller forms leave the upper
+	 * bits untouched:
+	 *
+	 *   insn  dest  size  bits written     bits preserved
+	 *   inb   AL    1     RAX[ 7: 0]       RAX[63: 8]
+	 *   inw   AX    2     RAX[15: 0]       RAX[63:16]
+	 *   inl   EAX   4     RAX[63: 0]       (none, zero-extended)
+	 *
+	 * 'mask' only covers the low 'size' bytes, which is exactly the
+	 * range affected for size 1 and 2. For size 4 the write also
+	 * clears RAX[63:32], so widen the clear-mask.
+	 */
+	if (size == 4)
+		regs->ax = 0;
+	else
+		regs->ax &= ~mask;
+
 	if (success)
 		regs->ax |= args.r11 & mask;

---

## [4] Edgecombe, Rick P — 2026-05-27
*Subject: Re: [PATCH v3 1/2] x86/tdx: Fix off-by-one in port I/O handling*

On Wed, 2026-05-27 at 13:05 +0100, Kiryl Shutsemau (Meta) wrote:
> handle_in() and handle_out() in arch/x86/coco/tdx/tdx.c use:
> 

Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [5] Edgecombe, Rick P — 2026-05-27
*Subject: Re: [PATCH v3 2/2] x86/tdx: Fix zero-extension for 32-bit port I/O*

On Wed, 2026-05-27 at 13:05 +0100, Kiryl Shutsemau (Meta) wrote:
> +	/*
> +	 * IN writes the result into a sub-register of RAX. Only the

We are working on getting the GHCI spec amended to clarify who is supposed to do
this zero-extending and masking, host or guest. For this and the similar
tdvmcalls. The process involves getting all VMMs in agreement.

Today I think the spec doesn't say to *not* do it, so I think it is reasonable
to merge this, but there is some small risk of complications depending on how
that discussion goes.

> +	 *
> +	 * 'mask' only covers the low 'size' bytes, which is exactly the

---

## [6] Dave Hansen — 2026-05-27
*Subject: Re: [PATCH v3 2/2] x86/tdx: Fix zero-extension for 32-bit port I/O*

On 5/27/26 05:05, Kiryl Shutsemau (Meta) wrote:
...
> -	/* Update part of the register affected by the emulated instruction */
> -	regs->ax &= ~mask;

Is there any way we could do this with fewer comments and more code?

I mean, there's only three cases. Why have;

	u64 mask = GENMASK(BITS_PER_BYTE * size - 1, 0);

When there are only 3 possible cases:

	1 => 0xf
	2 => 0xff
	4 => 0xffff

and one of those cases needs a special case on top of it.

Maybe something like this?

	/* Clear out part of RAX so part of args.r11 can be OR'd in: */
	switch (size) {
	case 1:
		/* inb consumes lower 8 bits of r11: */
		regs->ax &= ~GENMASK_ULL(7, 0);
		args.r11 &=  GENMASK_ULL(7, 0);
		break;
	case 2:
		/* inw consumes lower 16 bits of r11: */
		regs->ax &= ~GENMASK_ULL(15, 0);
		args.r11 &=  GENMASK_ULL(15, 0);
		break;
	case 4:
		/* inl is weird and zeros the whole register: */
		regs->ax &= ~GENMASK_ULL(63, 0);
		/* But only consumes 32-bits from r11: */
		args.r11 &=  GENMASK_ULL(31, 0);
		break;
	default:
		/* Probable TDX module bug. Illegal in[bwl] size: */
		WARN_ON_ONCE(1);
		success = 0;
	}

	if (success)
		regs->ax |= args.r11;

It might need a temporary variable for args.r11, but you get the point.
That's basically the data from the comment but written as code.

---
