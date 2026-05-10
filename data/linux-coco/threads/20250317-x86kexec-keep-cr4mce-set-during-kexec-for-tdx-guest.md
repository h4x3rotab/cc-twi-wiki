---
title: '[PATCHv9 05/17] x86/kexec: Keep CR4.MCE set during kexec for\n TDX guest'
date: 2025-03-17
last_reply: 2025-03-17
message_count: 4
participants: ['David Woodhouse', 'Kirill A. Shutemov']
---

## [1] David Woodhouse — 2025-03-17

On Thu, 2024-04-04 at 12:32 +0300, Kirill A. Shutemov wrote:
> On Thu, Apr 04, 2024 at 10:40:34AM +1300, Huang, Kai wrote:
> > 

And yet v12 of the patch which became commit de60613173df does
precisely that.

It uses the original contents of CR4 which are stored in %r13 (instead
of building a completely new set of bits for CR4 as before). So it
would never have *cleared* the CR4.MCE bit now anyway... what it does
is explicitly *set* the bit even if it wasn't set before?

This is what got committed, and I think we can just drop the
ALTERNATIVE line completely because it's redundant in the case that
CR4.MCE was already set, and *wrong* in the case that it wasn't already
set?

@@ -145,14 +147,15 @@ SYM_CODE_START_LOCAL_NOALIGN(identity_mapped)
         * Set cr4 to a known state:
         *  - physical address extension enabled
         *  - 5-level paging, if it was enabled before
+        *  - Machine check exception on TDX guest, if it was enabled before.
+        *    Clearing MCE might not be allowed in TDX guests, depending on setup.
+        *
+        * Use R13 that contains the original CR4 value, read in relocate_kernel().
+        * PAE is always set in the original CR4.
         */
-       movl    $X86_CR4_PAE, %eax
-       testq   $X86_CR4_LA57, %r13
-       jz      .Lno_la57
-       orl     $X86_CR4_LA57, %eax
-.Lno_la57:
-
-       movq    %rax, %cr4
+       andl    $(X86_CR4_PAE | X86_CR4_LA57), %r13d
+       ALTERNATIVE "", __stringify(orl $X86_CR4_MCE, %r13d), X86_FEATURE_TDX_GUEST
+       movq    %r13, %cr4
 
        /* Flush the TLB (needed?) */
        movq    %r9, %cr3

---

## [2] Kirill A. Shutemov — 2025-03-17
*Subject: Re: [PATCHv9 05/17] x86/kexec: Keep CR4.MCE set during kexec for TDX
 guest*

On Mon, Mar 17, 2025 at 09:27:16AM +0000, David Woodhouse wrote:
> On Thu, 2024-04-04 at 12:32 +0300, Kirill A. Shutemov wrote:
> > On Thu, Apr 04, 2024 at 10:40:34AM +1300, Huang, Kai wrote:

But we AND R13 against $(X86_CR4_PAE | X86_CR4_LA57). We will lose MCE if
drop the ALTERNATIVE.

And we don't want MCE to be enabled during kexec for !TDX_GUEST:

https://lore.kernel.org/all/1144340e-dd95-ee3b-dabb-579f9a65b3c7@citrix.com/

I think we should patch AND instruction to include X86_CR4_MCE on
TDX_GUEST:

diff --git a/arch/x86/kernel/relocate_kernel_64.S b/arch/x86/kernel/relocate_kernel_64.S
index b44d8863e57f..f6c552a39815 100644
--- a/arch/x86/kernel/relocate_kernel_64.S
+++ b/arch/x86/kernel/relocate_kernel_64.S
@@ -148,8 +148,8 @@ SYM_CODE_START_LOCAL_NOALIGN(identity_mapped)
 	 * Use R13 that contains the original CR4 value, read in relocate_kernel().
 	 * PAE is always set in the original CR4.
 	 */
-	andl	$(X86_CR4_PAE | X86_CR4_LA57), %r13d
-	ALTERNATIVE "", __stringify(orl $X86_CR4_MCE, %r13d), X86_FEATURE_TDX_GUEST
+	ALTERNATIVE __stringify(andl	$(X86_CR4_PAE | X86_CR4_LA57), %r13d), \
+		    __stringify(andl	$(X86_CR4_PAE | X86_CR4_LA57 | X86_CR4_MCE), %r13d), X86_FEATURE_TDX_GUEST
 	movq	%r13, %cr4
 
 	/* Flush the TLB (needed?) */

---

## [3] David Woodhouse — 2025-03-17

On Mon, 2025-03-17 at 13:03 +0200, Kirill A. Shutemov wrote:
> On Mon, Mar 17, 2025 at 09:27:16AM +0000, David Woodhouse wrote:
> > On Thu, 2024-04-04 at 12:32 +0300, Kirill A. Shutemov wrote:

Ah, yes.

> And we don't want MCE to be enabled during kexec for !TDX_GUEST:
> 

Actually now I've added proper exception handling in relocate_kernel
perhaps we could rethink that. But that's for the future.

> I think we should patch AND instruction to include X86_CR4_MCE on
> TDX_GUEST:

Yeah... although the reason I'm looking at this is because I want to
kill the ALTERNATIVE so that I can move the relocate_kernel() function
into a data section:
https://lore.kernel.org/all/20241218212326.44qff3i5n6cxuu5d@jpoimboe/

So I think I'll do it like this instead:

diff --git a/arch/x86/include/asm/kexec.h b/arch/x86/include/asm/kexec.h
index 5081d0b9e290..bd9fc22a6be2 100644
--- a/arch/x86/include/asm/kexec.h
+++ b/arch/x86/include/asm/kexec.h
@@ -65,6 +65,7 @@ extern gate_desc kexec_debug_idt[];
 extern unsigned char kexec_debug_exc_vectors[];
 extern uint16_t kexec_debug_8250_port;
 extern unsigned long kexec_debug_8250_mmio32;
+extern uint32_t kexec_preserve_cr4_bits;
 #endif
 
 /*
diff --git a/arch/x86/kernel/machine_kexec_64.c b/arch/x86/kernel/machine_kexec_64.c
index 7abc7aa0261b..016862d2b544 100644
--- a/arch/x86/kernel/machine_kexec_64.c
+++ b/arch/x86/kernel/machine_kexec_64.c
@@ -353,6 +353,22 @@ int machine_kexec_prepare(struct kimage *image)
 	kexec_va_control_page = (unsigned long)control_page;
 	kexec_pa_table_page = (unsigned long)__pa(image->arch.pgd);
 
+	/*
+	 * The relocate_kernel assembly code sets CR4 to a subset of the bits
+	 * which were set during kernel runtime, including only:
+	 *  - physical address extension (which is always set in kernel)
+	 *  - 5-level paging (if it's enabled)
+	 *  - Machine check exception on TDX guests
+	 *
+	 * Clearing MCE may not be allowed in TDX guests, but it *should* be
+	 * cleared in the general case. Because of the conditional nature of
+	 * that, pass the set of bits in from the kernel for relocate_kernel
+	 * to do a simple 'andl' with them.
+	 */
+	kexec_preserve_cr4_bits = X86_CR4_PAE | X86_CR4_LA57;
+	if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST))
+		kexec_preserve_cr4_bits |= X86_CR4_MCE;
+
 	if (image->type == KEXEC_TYPE_DEFAULT)
 		kexec_pa_swap_page = page_to_pfn(image->swap_page) << PAGE_SHIFT;
 
diff --git a/arch/x86/kernel/relocate_kernel_64.S b/arch/x86/kernel/relocate_kernel_64.S
index 4f8b7d318025..576b7bbdd55e 100644
--- a/arch/x86/kernel/relocate_kernel_64.S
+++ b/arch/x86/kernel/relocate_kernel_64.S
@@ -41,6 +41,7 @@ SYM_DATA(kexec_pa_swap_page, .quad 0)
 SYM_DATA_LOCAL(pa_backup_pages_map, .quad 0)
 SYM_DATA(kexec_debug_8250_mmio32, .quad 0)
 SYM_DATA(kexec_debug_8250_port, .word 0)
+SYM_DATA(kexec_preserve_cr4_bits, .long 0)
 
 	.balign 16
 SYM_DATA_START_LOCAL(kexec_debug_gdt)
@@ -183,17 +184,12 @@ SYM_CODE_START_LOCAL_NOALIGN(identity_mapped)
 	movq	%rax, %cr0
 
 	/*
-	 * Set cr4 to a known state:
-	 *  - physical address extension enabled
-	 *  - 5-level paging, if it was enabled before
-	 *  - Machine check exception on TDX guest, if it was enabled before.
-	 *    Clearing MCE might not be allowed in TDX guests, depending on setup.
+	 * Set CR4 to a known state, using the bitmask which was set in
+	 * machine_kexec_prepare().
 	 *
 	 * Use R13 that contains the original CR4 value, read in relocate_kernel().
-	 * PAE is always set in the original CR4.
 	 */
-	andl	$(X86_CR4_PAE | X86_CR4_LA57), %r13d
-	ALTERNATIVE "", __stringify(orl $X86_CR4_MCE, %r13d), X86_FEATURE_TDX_GUEST
+	andl	kexec_preserve_cr4_bits(%rip), %r13d
 	movq	%r13, %cr4
 
 	/* Flush the TLB (needed?) */

---

## [4] Kirill A. Shutemov — 2025-03-17
*Subject: Re: [PATCHv9 05/17] x86/kexec: Keep CR4.MCE set during kexec for TDX
 guest*

On Mon, Mar 17, 2025 at 11:32:42AM +0000, David Woodhouse wrote:
> > And we don't want MCE to be enabled during kexec for !TDX_GUEST:
> > 

There still going to be a gap once the new kernel is started until it gets
proper exception handling in place.

> > I think we should patch AND instruction to include X86_CR4_MCE on
> > TDX_GUEST:

Looks good to me. Thanks for the cleanup you are doing!

---
