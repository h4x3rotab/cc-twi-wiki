---
title: 'x86/tdx: Fix port I/O handling bugs'
date: 2026-06-04
last_reply: 2026-06-05
message_count: 7
participants: ['Kiryl Shutsemau (Meta)', 'Binbin Wu']
---

## [1] Kiryl Shutsemau (Meta) — 2026-06-04

Two bugs in the TDX guest port I/O #VE emulation, plus a small helper
extracted from KVM to avoid open-coding partial-register-write logic
in the second fix.

Patch 1 is an off-by-one in the mask used to clip the I/O value:
GENMASK(BITS_PER_BYTE * size, 0) is one bit too wide. Unchanged from
v3 1/2.

Patch 2 lifts KVM's instruction-emulator helper assign_register() out
of arch/x86/kvm/emulate.c into <asm/insn-eval.h>, renamed to
insn_assign_reg(). Dave suggested consolidating rather than adding a
third copy of the same partial-register switch; the body is rewritten
using plain arithmetic (suggested by David Laight) so the helper does
not rely on -fno-strict-aliasing or little-endian byte order. KVM
behaviour is unchanged.

Patch 3 fixes the architectural zero-extension of 32-bit IN: the old
mask-based handle_in() preserves RAX[63:32] after inl, which is wrong.
Now done by calling the helper.

Changes since v3:
  - Patch 1/2 carried over unchanged as 1/3.
  - Helper extracted from KVM (new patch 2/3) and used from
    handle_in() (Dave, David Laight).
  - Reviewed-by tags from v3 2/2 dropped on patch 3/3 because the
    implementation changed substantially. v3 1/2 -> v4 1/3 Rb tags
    preserved (patch unchanged).

v3: https://lore.kernel.org/all/20260527120544.2903923-1-kas@kernel.org/

Kiryl Shutsemau (Meta) (3):
  x86/tdx: Fix off-by-one in port I/O handling
  x86/insn-eval: Add insn_assign_reg() helper
  x86/tdx: Fix zero-extension for 32-bit port I/O

 arch/x86/coco/tdx/tdx.c          | 10 ++++------
 arch/x86/include/asm/insn-eval.h | 25 +++++++++++++++++++++++++
 arch/x86/kvm/emulate.c           | 26 ++++----------------------
 3 files changed, 33 insertions(+), 28 deletions(-)

---

## [2] Kiryl Shutsemau (Meta) — 2026-06-04
*Subject: [PATCH v4 1/3] x86/tdx: Fix off-by-one in port I/O handling*

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

## [3] Kiryl Shutsemau (Meta) — 2026-06-04
*Subject: [PATCH v4 2/3] x86/insn-eval: Add insn_assign_reg() helper*

KVM's instruction emulator has a small helper, assign_register(), that
writes a value into a sub-register with x86 partial-register-write
semantics: 1- and 2-byte writes leave the upper bits of the destination
untouched, 4-byte writes zero-extend to 64 bits, 8-byte writes overwrite
the full register.

The TDX guest #VE handler needs the same logic for port I/O emulation
to get 32-bit zero-extension right. Rather than copy-pasting the helper,
lift it to <asm/insn-eval.h> as insn_assign_reg() so both can use it.

Rewrite the body using arithmetic instead of pointer punning so the
helper does not depend on -fno-strict-aliasing or little-endian byte
order, and add <asm/insn.h> to the header's includes so it builds
standalone in callers that have not pulled it in transitively.

No functional change.

Signed-off-by: Kiryl Shutsemau <kas@kernel.org>
---
 arch/x86/include/asm/insn-eval.h | 25 +++++++++++++++++++++++++
 arch/x86/kvm/emulate.c           | 26 ++++----------------------
 2 files changed, 29 insertions(+), 22 deletions(-)

diff --git a/arch/x86/include/asm/insn-eval.h b/arch/x86/include/asm/insn-eval.h
index 4733e9064ee5..85251e718a77 100644
--- a/arch/x86/include/asm/insn-eval.h
+++ b/arch/x86/include/asm/insn-eval.h
@@ -9,6 +9,7 @@
 #include <linux/compiler.h>
 #include <linux/bug.h>
 #include <linux/err.h>
+#include <asm/insn.h>
 #include <asm/ptrace.h>
 
 #define INSN_CODE_SEG_ADDR_SZ(params) ((params >> 4) & 0xf)
@@ -46,4 +47,28 @@ enum insn_mmio_type insn_decode_mmio(struct insn *insn, int *bytes);
 
 bool insn_is_nop(struct insn *insn);
 
+/*
+ * Write @val into *@reg with x86 partial-register-write semantics: a 1-
+ * or 2-byte write leaves the upper bits of the destination untouched; a
+ * 4-byte write zero-extends to 64 bits (matching IN[BWL], MOV[BWL]
+ * etc.); an 8-byte write overwrites the full register.
+ */
+static inline void insn_assign_reg(unsigned long *reg, u64 val, int bytes)
+{
+	switch (bytes) {
+	case 1:
+		*reg = (*reg & ~0xfful)   | (val & 0xff);
+		break;
+	case 2:
+		*reg = (*reg & ~0xfffful) | (val & 0xffff);
+		break;
+	case 4:
+		*reg = (u32)val;
+		break;
+	case 8:
+		*reg = val;
+		break;
+	}
+}
+
 #endif /* _ASM_X86_INSN_EVAL_H */
diff --git a/arch/x86/kvm/emulate.c b/arch/x86/kvm/emulate.c
index 8013dccb3110..74972c17edb8 100644
--- a/arch/x86/kvm/emulate.c
+++ b/arch/x86/kvm/emulate.c
@@ -24,6 +24,7 @@
 #include "kvm_emulate.h"
 #include <linux/stringify.h>
 #include <asm/debugreg.h>
+#include <asm/insn-eval.h>
 #include <asm/nospec-branch.h>
 #include <asm/ibt.h>
 #include <asm/text-patching.h>
@@ -439,25 +440,6 @@ static void assign_masked(ulong *dest, ulong src, ulong mask)
 	*dest = (*dest & ~mask) | (src & mask);
 }
 
-static void assign_register(unsigned long *reg, u64 val, int bytes)
-{
-	/* The 4-byte case *is* correct: in 64-bit mode we zero-extend. */
-	switch (bytes) {
-	case 1:
-		*(u8 *)reg = (u8)val;
-		break;
-	case 2:
-		*(u16 *)reg = (u16)val;
-		break;
-	case 4:
-		*reg = (u32)val;
-		break;	/* 64b: zero-extend */
-	case 8:
-		*reg = val;
-		break;
-	}
-}
-
 static inline unsigned long ad_mask(struct x86_emulate_ctxt *ctxt)
 {
 	return (1UL << (ctxt->ad_bytes << 3)) - 1;
@@ -505,7 +487,7 @@ register_address_increment(struct x86_emulate_ctxt *ctxt, int reg, int inc)
 {
 	ulong *preg = reg_rmw(ctxt, reg);
 
-	assign_register(preg, *preg + inc, ctxt->ad_bytes);
+	insn_assign_reg(preg, *preg + inc, ctxt->ad_bytes);
 }
 
 static void rsp_increment(struct x86_emulate_ctxt *ctxt, int inc)
@@ -1766,7 +1748,7 @@ static int load_segment_descriptor(struct x86_emulate_ctxt *ctxt,
 
 static void write_register_operand(struct operand *op)
 {
-	return assign_register(op->addr.reg, op->val, op->bytes);
+	return insn_assign_reg(op->addr.reg, op->val, op->bytes);
 }
 
 static int writeback(struct x86_emulate_ctxt *ctxt, struct operand *op)
@@ -2007,7 +1989,7 @@ static int em_popa(struct x86_emulate_ctxt *ctxt)
 		rc = emulate_pop(ctxt, &val, ctxt->op_bytes);
 		if (rc != X86EMUL_CONTINUE)
 			break;
-		assign_register(reg_rmw(ctxt, reg), val, ctxt->op_bytes);
+		insn_assign_reg(reg_rmw(ctxt, reg), val, ctxt->op_bytes);
 		--reg;
 	}
 	return rc;

---

## [4] Kiryl Shutsemau (Meta) — 2026-06-04
*Subject: [PATCH v4 3/3] x86/tdx: Fix zero-extension for 32-bit port I/O*

According to x86 architecture rules, 32-bit operations zero-extend the
result to 64 bits. The current implementation of handle_in() only masks
the lower 32 bits, which preserves the upper 32 bits of RAX when a
32-bit port IN instruction is emulated.

Use insn_assign_reg() to write the result back into RAX with proper
partial-register-write semantics: 1- and 2-byte forms leave the upper
bits untouched, the 4-byte form zero-extends to the full register.

Fixes: 03149948832a ("x86/tdx: Port I/O: Add runtime hypercalls")
Reported-by: Borys Tsyrulnikov <tsyrulnikov.borys@gmail.com>
Link: https://lore.kernel.org/all/CAKw_Dz96rfSQc6Rn+9QBcUFHhmkK+9zu+P=bxowfZwxrATCBRg@mail.gmail.com/
Signed-off-by: Kiryl Shutsemau <kas@kernel.org>
Cc: stable@vger.kernel.org
---
 arch/x86/coco/tdx/tdx.c | 8 +++-----
 1 file changed, 3 insertions(+), 5 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 65119362f9a2..41cc23cc63dd 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -693,8 +693,8 @@ static bool handle_in(struct pt_regs *regs, int size, int port)
 		.r13 = PORT_READ,
 		.r14 = port,
 	};
-	u64 mask = GENMASK(BITS_PER_BYTE * size - 1, 0);
 	bool success;
+	u64 val;
 
 	/*
 	 * Emulate the I/O read via hypercall. More info about ABI can be found
@@ -702,11 +702,9 @@ static bool handle_in(struct pt_regs *regs, int size, int port)
 	 * "TDG.VP.VMCALL<Instruction.IO>".
 	 */
 	success = !__tdx_hypercall(&args);
+	val = success ? args.r11 : 0;
 
-	/* Update part of the register affected by the emulated instruction */
-	regs->ax &= ~mask;
-	if (success)
-		regs->ax |= args.r11 & mask;
+	insn_assign_reg(&regs->ax, val, size);
 
 	return success;
 }

---

## [5] Binbin Wu — 2026-06-05
*Subject: Re: [PATCH v4 1/3] x86/tdx: Fix off-by-one in port I/O handling*

On 6/4/2026 10:46 PM, Kiryl Shutsemau (Meta) wrote:
> handle_in() and handle_out() in arch/x86/coco/tdx/tdx.c use:
> 

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

> ---
>  arch/x86/coco/tdx/tdx.c | 4 ++--

---

## [6] Binbin Wu — 2026-06-05
*Subject: Re: [PATCH v4 3/3] x86/tdx: Fix zero-extension for 32-bit port I/O*

On 6/4/2026 10:47 PM, Kiryl Shutsemau (Meta) wrote:
> According to x86 architecture rules, 32-bit operations zero-extend the
> result to 64 bits. The current implementation of handle_in() only masks

I think the concern sashiko commented in patch 2 is valid.

But for this patch itself,
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>

> ---
>  arch/x86/coco/tdx/tdx.c | 8 +++-----

---

## [7] Kiryl Shutsemau — 2026-06-05
*Subject: Re: [PATCH v4 3/3] x86/tdx: Fix zero-extension for 32-bit port I/O*

On Fri, Jun 05, 2026 at 03:10:39PM +0800, Binbin Wu wrote:
> 
> 

Yeah. I guess I'll just use the KVM implementation verbatim.

Dave, any objections?

---
