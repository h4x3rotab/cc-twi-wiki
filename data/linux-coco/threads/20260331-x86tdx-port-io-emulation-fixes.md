---
title: 'x86/tdx: Port I/O emulation fixes'
date: 2026-03-31
last_reply: 2026-04-01
message_count: 8
participants: ['Kiryl Shutsemau (Meta)', 'Kuppuswamy Sathyanarayanan', 'Huang, Kai']
---

## [1] Kiryl Shutsemau (Meta) — 2026-03-31

This series addresses two technical inaccuracies in the TDX guest port
I/O emulation code reported by Borys Tsyrulnikov.

The first patch fixes an off-by-one error in the GENMASK() macro usage
where the mask was being calculated as one bit too wide (e.g., 9 bits for
an 8-bit operation).

The second patch ensures that 32-bit port I/O operations (INL) correctly
zero-extend the result to the full 64-bit RAX register, as required by
 the x86 architecture. Currently, the emulation preserves the upper 32
bits of RAX during such operations.

Both issues were introduced in the initial implementation of the runtime
hypercalls for port I/O.

Kiryl Shutsemau (Meta) (2):
  x86/tdx: Fix off-by-one in port I/O handling
  x86/tdx: Fix zero-extension for 32-bit port I/O

 arch/x86/coco/tdx/tdx.c | 17 +++++++++++++----
 1 file changed, 13 insertions(+), 4 deletions(-)

---

## [2] Kiryl Shutsemau (Meta) — 2026-03-31
*Subject: [PATCH 1/2] x86/tdx: Fix off-by-one in port I/O handling*

handle_in() and handle_out() in arch/x86/coco/tdx/tdx.c use:

    u64 mask = GENMASK(BITS_PER_BYTE * size, 0);

GENMASK(h, l) includes bit h. For size=1 (INB), this produces
GENMASK(8, 0) = 0x1FF (9 bits) instead of GENMASK(7, 0) = 0xFF (8
bits). The mask is one bit too wide for all I/O sizes.

Fix the mask calculation.

Fixes: 03149948832a ("x86/tdx: Port I/O: Add runtime hypercalls")
Reported-by: Borys Tsyrulnikov <tsyrulnikov.borys@gmail.com>
Signed-off-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Cc: stable@vger.kernel.org
---
 arch/x86/coco/tdx/tdx.c | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 7b2833705d47..4d7f71d50122 100644
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

## [3] Kiryl Shutsemau (Meta) — 2026-03-31
*Subject: [PATCH 2/2] x86/tdx: Fix zero-extension for 32-bit port I/O*

According to x86 architecture rules, 32-bit operations zero-extend the
result to 64 bits. The current implementation of handle_in() only masks
the lower 32 bits, which preserves the upper 32 bits of RAX when a
32-bit port IN instruction is emulated.

Update handle_in() to zero out the entire RAX register when the I/O size
is 4 bytes to ensure correct zero-extension. For smaller sizes (1 or 2
bytes), continue to preserve the unaffected upper bits.

Fixes: 03149948832a ("x86/tdx: Port I/O: Add runtime hypercalls")
Reported-by: Borys Tsyrulnikov <tsyrulnikov.borys@gmail.com>
Signed-off-by: Kiryl Shutsemau (Meta) <kas@kernel.org>
Cc: stable@vger.kernel.org
---
 arch/x86/coco/tdx/tdx.c | 13 +++++++++++--
 1 file changed, 11 insertions(+), 2 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 4d7f71d50122..b9b9a2d75119 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -703,8 +703,17 @@ static bool handle_in(struct pt_regs *regs, int size, int port)
 	 */
 	success = !__tdx_hypercall(&args);
 
-	/* Update part of the register affected by the emulated instruction */
-	regs->ax &= ~mask;
+	/*
+	 * Update part of the register affected by the emulated instruction.
+	 *
+	 * 32-bit operands generate a 32-bit result, zero-extended to a 64-bit
+	 * result.
+	 */
+	if (size < 4)
+		regs->ax &= ~mask;
+	else
+		regs->ax = 0;
+
 	if (success)
 		regs->ax |= args.r11 & mask;

---

## [4] Kuppuswamy Sathyanarayanan — 2026-03-31
*Subject: Re: [PATCH 1/2] x86/tdx: Fix off-by-one in port I/O handling*

Hi Kirill,

On 3/31/2026 4:24 AM, Kiryl Shutsemau (Meta) wrote:
> handle_in() and handle_out() in arch/x86/coco/tdx/tdx.c use:
> 

LGTM. Can you include a link to the bug report or related discussion in 
the commit log? It will help understand the impact of this issue.

Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>

>  arch/x86/coco/tdx/tdx.c | 4 ++--
>  1 file changed, 2 insertions(+), 2 deletions(-)

---

## [5] Huang, Kai — 2026-03-31
*Subject: Re: [PATCH 1/2] x86/tdx: Fix off-by-one in port I/O handling*

On Tue, 2026-03-31 at 12:24 +0100, Kiryl Shutsemau (Meta) wrote:
> handle_in() and handle_out() in arch/x86/coco/tdx/tdx.c use:
> 

Reviewed-by: Kai Huang <kai.huang@intel.com>

---

## [6] Kuppuswamy Sathyanarayanan — 2026-03-31
*Subject: Re: [PATCH 2/2] x86/tdx: Fix zero-extension for 32-bit port I/O*

Hi Kiril,

On 3/31/2026 4:24 AM, Kiryl Shutsemau (Meta) wrote:
> According to x86 architecture rules, 32-bit operations zero-extend the
> result to 64 bits. The current implementation of handle_in() only masks

If you have bug or discussion link, please include it.

Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>



>  arch/x86/coco/tdx/tdx.c | 13 +++++++++++--
>  1 file changed, 11 insertions(+), 2 deletions(-)

The logic would be more readable as:

	if (size == 4)
		regs->ax = 0;
	else
		regs->ax &= ~mask;

> +
>  	if (success)

---

## [7] Huang, Kai — 2026-03-31
*Subject: Re: [PATCH 2/2] x86/tdx: Fix zero-extension for 32-bit port I/O*

On Tue, 2026-03-31 at 12:24 +0100, Kiryl Shutsemau (Meta) wrote:
> According to x86 architecture rules, 32-bit operations zero-extend the
> result to 64 bits. 

FWIW, the relevant part in the SDM seems to be:

  Chapter 3.4.1.1 General-Purpose Registers in 64-Bit Mode

  ...
  * 32-bit operands generate a 32-bit result, zero-extended to a 64 bit 
    result in the destination general-purpose register.

> The current implementation of handle_in() only masks
> the lower 32 bits, which preserves the upper 32 bits of RAX when a

Reviewed-by: Kai Huang <kai.huang@intel.com>

> ---
>  arch/x86/coco/tdx/tdx.c | 13 +++++++++++--

---

## [8] Kiryl Shutsemau — 2026-04-01
*Subject: Re: [PATCH 1/2] x86/tdx: Fix off-by-one in port I/O handling*

On Tue, Mar 31, 2026 at 02:57:32PM -0700, Kuppuswamy Sathyanarayanan wrote:
> Hi Kirill,
> 

Link: https://lore.kernel.org/all/CAKw_Dz96rfSQc6Rn+9QBcUFHhmkK+9zu+P=bxowfZwxrATCBRg@mail.gmail.com/

It is relevant for both.

---
