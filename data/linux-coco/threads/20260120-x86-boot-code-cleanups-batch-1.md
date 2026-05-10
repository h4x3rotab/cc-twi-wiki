---
title: 'x86 boot code cleanups, batch 1'
date: 2026-01-20
last_reply: 2026-01-29
message_count: 50
participants: ['H. Peter Anvin', 'David Laight', 'Uros Bizjak', 'Kiryl Shutsemau', 'Simon Glass', 'Maciej W. Rozycki', 'Borislav Petkov']
---

## [1] H. Peter Anvin — 2026-01-20

From: "H. Peter Anvin" (Intel) <hpa@zytor.com>

Uros Bizjak was kind enough to look over my RFC patchset, and so I
feel confident enough to call this a v1 patchset now.

The difference versus RFC are:

1. Remove .code16 from header.S (Uros Bizjak).

2. Split out the changed handling of the old (ancient by now) command
   pointer protocol into a separate patch - it had accidentally gotten
   mixed into two(!) mostly unrelated patches.

3. Added a missing barrier(); to a20.c, made necessary by having the
   compiler aware of fs/gs memory.

4. While changing a20.c anyway, tidy up and optimize the code a bit.

Again, the only potentially controversial thing here is removing the
options for non-relocatable kernels and building kernels without the
EFI stub. Those configurations should be considered obsolete, and they
don't add any cost to the runtime kernel.

This patchset also includes the removal of the gcc-specific version of
the RELOC_HIDE() macro, by Uros Bizjak, as the other changes in this
patchset makes that possible. Per Uros, this is holding back gcc
development, so it seems pretty important.

I am calling this "batch 1", because I have quite a few more cleanups
still being worked on; this patchset will be a prerequisite for those,
obviously.

This patchset is also available as a git tree:

	git://git.zytor.com/linux/kernel/boot.git hpa/boot1
	https://git.zytor.com/linux/kernel/boot/log/?h=hpa/boot1

The patches are:

    01/14: x86/realmode: remove I/O port paravirtualization
    02/14: x86/realmode: make %gs == 0 an invariant
    03/14: x86/boot: use <linux/compiler.h>
    04/14: x86/boot: modernize the segment structure for the header and setup
    05/14: x86/boot: call puts() from within die()
    06/14: x86/boot: add comment barriers for the different headers
    07/14: x86/boot: factor out the 16-bit startup code from header.S
    08/14: x86: make CONFIG_EFI_STUB unconditional
    09/14: x86/boot: make the relocatable kernel unconditional
    10/14: x86/boot: explicitly put the old command line pointer in header.S
    11/14: x86/boot: use __seg_fs and __seg_gs in the real-mode boot code
    12/14: x86/boot: tweak a20.c for better code generation
    13/14: x86/boot: simplify x86/boot/cmdline.c by using __seg_fs
    14/14: compiler-gcc: Remove obsolete RELOC_HIDE() macro (Uros Bizjak)

--- 
 arch/x86/Kconfig                    |  85 ++++---------------------
 arch/x86/boot/Makefile              |   4 +-
 arch/x86/boot/a20.c                 |  34 +++++-----
 arch/x86/boot/boot.h                | 116 ++++++++++------------------------
 arch/x86/boot/cmdline.c             |  79 ++++++++++++++++++-----
 arch/x86/boot/compressed/Makefile   |   2 -
 arch/x86/boot/compressed/cmdline.c  |  29 ---------
 arch/x86/boot/compressed/error.c    |   2 -
 arch/x86/boot/compressed/head_32.S  |   2 -
 arch/x86/boot/compressed/head_64.S  |   4 --
 arch/x86/boot/{ => compressed}/io.h |   0
 arch/x86/boot/compressed/misc.c     |   8 ---
 arch/x86/boot/compressed/misc.h     |   2 +-
 arch/x86/boot/compressed/tdx.c      |   2 +-
 arch/x86/boot/header.S              | 123 ++++++++----------------------------
 arch/x86/boot/main.c                |  43 ++++++-------
 arch/x86/boot/pm.c                  |   5 +-
 arch/x86/boot/regs.c                |   3 +-
 arch/x86/boot/setup.ld              |  26 ++++----
 arch/x86/boot/start16.S             | 108 +++++++++++++++++++++++++++++++
 arch/x86/boot/video-bios.c          |   5 +-
 arch/x86/boot/video-mode.c          |   5 +-
 arch/x86/boot/video.c               |   7 +-
 arch/x86/realmode/rm/wakemain.c     |   4 --
 arch/x86/realmode/rm/wakeup_asm.S   |  10 +--
 include/linux/compiler-gcc.h        |  25 --------
 include/linux/compiler.h            |   8 +++
 27 files changed, 316 insertions(+), 425 deletions(-)

---

## [2] H. Peter Anvin — 2026-01-20
*Subject: [PATCH v1 01/14] x86/realmode: remove I/O port paravirtualization*

In commit:

eb4ea1ae8f45 x86/boot: Port I/O: Allow to hook up alternative helpers

... paravirtualization hooks were added to (some!) of the port I/O
functions. However, they were only ever used in the 32/64-bit
"compressed" directory, and never made any sense in the real-mode
code, which is notoriously size sensitive.

Without these hooks, <asm/shared/io.h> is usable directly, so mode
io.h into the compressed/ directory and replace "io.h" with
<asm/shared/io.h> for the actual real-mode code.

Signed-off-by: H. Peter Anvin (Intel) <hpa@zytor.com>
---
 arch/x86/boot/boot.h                | 2 +-
 arch/x86/boot/{ => compressed}/io.h | 0
 arch/x86/boot/compressed/misc.h     | 2 +-
 arch/x86/boot/compressed/tdx.c      | 2 +-
 arch/x86/boot/main.c                | 5 +----
 arch/x86/realmode/rm/wakemain.c     | 4 ----
 6 files changed, 4 insertions(+), 11 deletions(-)
 rename arch/x86/boot/{ => compressed}/io.h (100%)

diff --git a/arch/x86/boot/boot.h b/arch/x86/boot/boot.h
index 8e3eab34dff4..f185931283cb 100644
--- a/arch/x86/boot/boot.h
+++ b/arch/x86/boot/boot.h
@@ -18,6 +18,7 @@
 
 #ifndef __ASSEMBLER__
 
+#include <asm/shared/io.h>
 #include <linux/stdarg.h>
 #include <linux/types.h>
 #include <linux/edd.h>
@@ -26,7 +27,6 @@
 #include "bitops.h"
 #include "ctype.h"
 #include "cpuflags.h"
-#include "io.h"
 
 /* Useful macros */
 #define ARRAY_SIZE(x) (sizeof(x) / sizeof(*(x)))
diff --git a/arch/x86/boot/io.h b/arch/x86/boot/compressed/io.h
similarity index 100%
rename from arch/x86/boot/io.h
rename to arch/x86/boot/compressed/io.h
diff --git a/arch/x86/boot/compressed/misc.h b/arch/x86/boot/compressed/misc.h
index fd855e32c9b9..68957e7698ad 100644
--- a/arch/x86/boot/compressed/misc.h
+++ b/arch/x86/boot/compressed/misc.h
@@ -43,8 +43,8 @@
 
 #define BOOT_BOOT_H
 #include "../ctype.h"
-#include "../io.h"
 
+#include "io.h"
 #include "efi.h"
 
 #ifdef CONFIG_X86_64
diff --git a/arch/x86/boot/compressed/tdx.c b/arch/x86/boot/compressed/tdx.c
index 8451d6a1030c..00359dbe1f8c 100644
--- a/arch/x86/boot/compressed/tdx.c
+++ b/arch/x86/boot/compressed/tdx.c
@@ -2,7 +2,7 @@
 
 #include "../cpuflags.h"
 #include "../string.h"
-#include "../io.h"
+#include "io.h"
 #include "error.h"
 
 #include <vdso/limits.h>
diff --git a/arch/x86/boot/main.c b/arch/x86/boot/main.c
index 9d0fea18d3c8..da01ade4959e 100644
--- a/arch/x86/boot/main.c
+++ b/arch/x86/boot/main.c
@@ -15,10 +15,9 @@
 #include "boot.h"
 #include "string.h"
 
+/* Buffer for building the full "zero page" struct boot_params */
 struct boot_params boot_params __attribute__((aligned(16)));
 
-struct port_io_ops pio_ops;
-
 char *HEAP = _end;
 char *heap_end = _end;		/* Default end of heap = no heap */
 
@@ -132,8 +131,6 @@ static void init_heap(void)
 
 void main(void)
 {
-	init_default_io_ops();
-
 	/* First, copy the boot header into the "zeropage" */
 	copy_boot_params();
 
diff --git a/arch/x86/realmode/rm/wakemain.c b/arch/x86/realmode/rm/wakemain.c
index a6f4d8388ad8..1d6437e6d2ba 100644
--- a/arch/x86/realmode/rm/wakemain.c
+++ b/arch/x86/realmode/rm/wakemain.c
@@ -62,12 +62,8 @@ static void send_morse(const char *pattern)
 	}
 }
 
-struct port_io_ops pio_ops;
-
 void main(void)
 {
-	init_default_io_ops();
-
 	/* Kill machine if structures are wrong */
 	if (wakeup_header.real_magic != 0x12345678)
 		while (1)

---

## [3] H. Peter Anvin — 2026-01-20
*Subject: [PATCH v1 02/14] x86/realmode: make %gs == 0 an invariant*

When accessing data that is not "near", either only one segment is
used or one segment is always zero. Leave %gs == 0 at all times
throughout the C code; this reduces the number of segment loads
needed.

Signed-off-by: H. Peter Anvin (Intel) <hpa@zytor.com>
---
 arch/x86/boot/a20.c               | 11 +++++------
 arch/x86/boot/header.S            |  3 +++
 arch/x86/boot/regs.c              |  3 ++-
 arch/x86/boot/video-bios.c        |  5 ++---
 arch/x86/boot/video-mode.c        |  5 ++---
 arch/x86/boot/video.c             |  7 +++----
 arch/x86/realmode/rm/wakeup_asm.S | 10 ++++++----
 7 files changed, 23 insertions(+), 21 deletions(-)

diff --git a/arch/x86/boot/a20.c b/arch/x86/boot/a20.c
index bda042933a05..3ab6cd8eaa31 100644
--- a/arch/x86/boot/a20.c
+++ b/arch/x86/boot/a20.c
@@ -56,20 +56,19 @@ static int a20_test(int loops)
 	int ok = 0;
 	int saved, ctr;
 
-	set_fs(0x0000);
-	set_gs(0xffff);
+	set_fs(0xffff);
 
-	saved = ctr = rdfs32(A20_TEST_ADDR);
+	saved = ctr = rdgs32(A20_TEST_ADDR);
 
 	while (loops--) {
-		wrfs32(++ctr, A20_TEST_ADDR);
+		wrgs32(++ctr, A20_TEST_ADDR);
 		io_delay();	/* Serialize and make delay constant */
-		ok = rdgs32(A20_TEST_ADDR+0x10) ^ ctr;
+		ok = rdfs32(A20_TEST_ADDR+0x10) ^ ctr;
 		if (ok)
 			break;
 	}
 
-	wrfs32(saved, A20_TEST_ADDR);
+	wrgs32(saved, A20_TEST_ADDR);
 	return ok;
 }
 
diff --git a/arch/x86/boot/header.S b/arch/x86/boot/header.S
index 9bea5a1e2c52..bda20395658f 100644
--- a/arch/x86/boot/header.S
+++ b/arch/x86/boot/header.S
@@ -596,6 +596,9 @@ start_of_setup:
 	shrw	$2, %cx
 	rep stosl
 
+# The C code uses %gs == 0 as invariant
+	movw	%ax, %gs
+
 # Jump to C code (should not return)
 	calll	main
 
diff --git a/arch/x86/boot/regs.c b/arch/x86/boot/regs.c
index 55de6b3092b8..54d6dfd129c5 100644
--- a/arch/x86/boot/regs.c
+++ b/arch/x86/boot/regs.c
@@ -22,6 +22,7 @@ void initregs(struct biosregs *reg)
 	reg->eflags |= X86_EFLAGS_CF;
 	reg->ds = ds();
 	reg->es = ds();
+	/* The input values of %cs and %ss are ignored by intcall() */
 	reg->fs = fs();
-	reg->gs = gs();
+	/* %gs == 0 */
 }
diff --git a/arch/x86/boot/video-bios.c b/arch/x86/boot/video-bios.c
index 6eb8c06bc287..e8be64424a40 100644
--- a/arch/x86/boot/video-bios.c
+++ b/arch/x86/boot/video-bios.c
@@ -73,7 +73,6 @@ static int bios_probe(void)
 	if (adapter != ADAPTER_EGA && adapter != ADAPTER_VGA)
 		return 0;
 
-	set_fs(0);
 	crtc = vga_crtc();
 
 	video_bios.modes = GET_HEAP(struct mode_info, 0);
@@ -105,8 +104,8 @@ static int bios_probe(void)
 		mi = GET_HEAP(struct mode_info, 1);
 		mi->mode = VIDEO_FIRST_BIOS+mode;
 		mi->depth = 0;	/* text */
-		mi->x = rdfs16(0x44a);
-		mi->y = rdfs8(0x484)+1;
+		mi->x = rdgs16(0x44a);
+		mi->y = rdgs8(0x484)+1;
 		nmodes++;
 	}
 
diff --git a/arch/x86/boot/video-mode.c b/arch/x86/boot/video-mode.c
index 9ada55dc1ab7..e5b9bc96bd42 100644
--- a/arch/x86/boot/video-mode.c
+++ b/arch/x86/boot/video-mode.c
@@ -119,9 +119,8 @@ static void vga_recalc_vertical(void)
 	u16 crtc;
 	u8 pt, ov;
 
-	set_fs(0);
-	font_size = rdfs8(0x485); /* BIOS: font size (pixels) */
-	rows = force_y ? force_y : rdfs8(0x484)+1; /* Text rows */
+	font_size = rdgs8(0x485); /* BIOS: font size (pixels) */
+	rows = force_y ? force_y : rdgs8(0x484)+1; /* Text rows */
 
 	rows *= font_size;	/* Visible scan lines */
 	rows--;			/* ... minus one */
diff --git a/arch/x86/boot/video.c b/arch/x86/boot/video.c
index 0641c8c46aee..09b810faa5c0 100644
--- a/arch/x86/boot/video.c
+++ b/arch/x86/boot/video.c
@@ -79,12 +79,11 @@ static void store_mode_params(void)
 		video_segment = 0xb800;
 	}
 
-	set_fs(0);
-	font_size = rdfs16(0x485); /* Font size, BIOS area */
+	font_size = rdgs16(0x485); /* Font size, BIOS area */
 	boot_params.screen_info.orig_video_points = font_size;
 
-	x = rdfs16(0x44a);
-	y = (adapter == ADAPTER_CGA) ? 25 : rdfs8(0x484)+1;
+	x = rdgs16(0x44a);
+	y = (adapter == ADAPTER_CGA) ? 25 : rdgs8(0x484)+1;
 
 	if (force_x)
 		x = force_x;
diff --git a/arch/x86/realmode/rm/wakeup_asm.S b/arch/x86/realmode/rm/wakeup_asm.S
index 02d0ba16ae33..a8a8580158d7 100644
--- a/arch/x86/realmode/rm/wakeup_asm.S
+++ b/arch/x86/realmode/rm/wakeup_asm.S
@@ -70,15 +70,17 @@ SYM_CODE_START(wakeup_start)
 	movl	$rm_stack_end, %esp
 	movw	%ax, %ds
 	movw	%ax, %es
-	movw	%ax, %fs
-	movw	%ax, %gs
 
-	lidtl	.Lwakeup_idt
+	xorl	%eax, %eax
+	movw	%ax, %fs
+	movw	%ax, %gs	/* The real mode code requires %gs == 0 */
 
 	/* Clear the EFLAGS */
-	pushl $0
+	pushl	%eax
 	popfl
 
+	lidtl	.Lwakeup_idt
+
 	/* Check header signature... */
 	movl	signature, %eax
 	cmpl	$WAKEUP_HEADER_SIGNATURE, %eax

---

## [4] H. Peter Anvin — 2026-01-20
*Subject: [PATCH v1 03/14] x86/boot: use <linux/compiler.h>*

Include <linux/compiler.h> in arch/x86/boot/boot.h and replace
__attribute__((noreturn)) with __noreturn.

Signed-off-by: H. Peter Anvin (Intel) <hpa@zytor.com>
---
 arch/x86/boot/boot.h | 8 ++++----
 1 file changed, 4 insertions(+), 4 deletions(-)

diff --git a/arch/x86/boot/boot.h b/arch/x86/boot/boot.h
index f185931283cb..1f2b7252e387 100644
--- a/arch/x86/boot/boot.h
+++ b/arch/x86/boot/boot.h
@@ -18,6 +18,7 @@
 
 #ifndef __ASSEMBLER__
 
+#include <linux/compiler.h>
 #include <asm/shared/io.h>
 #include <linux/stdarg.h>
 #include <linux/types.h>
@@ -279,17 +280,16 @@ void console_init(void);
 void query_edd(void);
 
 /* header.S */
-void __attribute__((noreturn)) die(void);
+void __noreturn die(void);
 
 /* memory.c */
 void detect_memory(void);
 
 /* pm.c */
-void __attribute__((noreturn)) go_to_protected_mode(void);
+void __noreturn go_to_protected_mode(void);
 
 /* pmjump.S */
-void __attribute__((noreturn))
-	protected_mode_jump(u32 entrypoint, u32 bootparams);
+void __noreturn protected_mode_jump(u32 entrypoint, u32 bootparams);
 
 /* printf.c */
 int sprintf(char *buf, const char *fmt, ...);

---

## [5] H. Peter Anvin — 2026-01-20
*Subject: [PATCH v1 04/14] x86/boot: modernize the segment structure for the header and setup*

Modernize the segment structure for the EFI and bzImage headers and
the 16-bit setup.

1. The ".bstext" section (EFI header) has not had code in it for a
   while now. Merge it into the .header section.
2. Move the contents of the .signature section to assembly rather than
   the linker script. As a side benefit, the magic number is now
   private to header.S.
3. Add additional asserts to the linker script.
4. Fill gaps in code sections with int3 instead of nop.

Signed-off-by: H. Peter Anvin (Intel) <hpa@zytor.com>
---
 arch/x86/boot/header.S | 27 +++++++++++++++++++--------
 arch/x86/boot/setup.ld | 26 ++++++++++++--------------
 2 files changed, 31 insertions(+), 22 deletions(-)

diff --git a/arch/x86/boot/header.S b/arch/x86/boot/header.S
index bda20395658f..85a21d576f5b 100644
--- a/arch/x86/boot/header.S
+++ b/arch/x86/boot/header.S
@@ -40,7 +40,7 @@ SYSSEG		= 0x1000		/* historical load address >> 4 */
 	.set	falign, 0x200
 
 	.code16
-	.section ".bstext", "ax"
+	.section ".header", "a"
 #ifdef CONFIG_EFI_STUB
 	# "MZ", MS-DOS header
 	.word	IMAGE_DOS_SIGNATURE
@@ -221,15 +221,16 @@ pecompat_fstart:
 		IMAGE_SCN_MEM_WRITE		# Characteristics
 
 	.set	section_count, (. - section_table) / 40
+
 #endif /* CONFIG_EFI_STUB */
 
-	# Kernel attributes; used by setup.  This is part 1 of the
-	# header, from the old boot sector.
+	# hdr should be at address 0x1f1; -2 for the sentinel
+	.org	0x1f1-2, 0xff			# Fill with 0xff
 
-	.section ".header", "a"
 	.globl	sentinel
 sentinel:	.byte 0xff, 0xff        /* Used to detect broken loaders */
 
+	# The bzImage struct setup_header
 	.globl	hdr
 hdr:
 		.byte setup_sects - 1
@@ -240,15 +241,15 @@ vid_mode:	.word SVGA_MODE
 root_dev:	.word 0			/* Default to major/minor 0/0 */
 boot_flag:	.word 0xAA55
 
-	# offset 512, entry point
+	# offset 512, entry point AND struct setup_header length marker
 
 	.globl	_start
 _start:
 		# Explicitly enter this as bytes, or the assembler
-		# tries to generate a 3-byte jump here, which causes
+		# might try to generate a 3-byte jump here, which causes
 		# everything else to push off to the wrong offset.
 		.byte	0xeb		# short (2-byte) jump
-		.byte	start_of_setup-1f
+		.byte	end_of_bzheader-1f
 1:
 
 	# Part 2 of the header, from the old setup.S
@@ -541,9 +542,13 @@ init_size:		.long INIT_SIZE		# kernel initialization size
 handover_offset:	__handover_offset
 kernel_info_offset:	.long ZO_kernel_info
 
+	.globl end_of_bzheader
+end_of_bzheader:
+
 # End of setup header #####################################################
 
 	.section ".entrytext", "ax"
+	.globl start_of_setup
 start_of_setup:
 # Force %es = %ds
 	movw	%ds, %ax
@@ -585,7 +590,8 @@ start_of_setup:
 6:
 
 # Check signature at end of setup
-	cmpl	$0x5a5aaa55, setup_sig
+SETUP_SIGNATURE = 0x5a5aaa55
+	cmpl	$SETUP_SIGNATURE, setup_sig
 	jne	setup_bad
 
 # Zero the bss
@@ -620,3 +626,8 @@ die:
 setup_corrupt:
 	.byte	7
 	.string	"No setup signature found...\n"
+
+	.section ".signature", "a"
+	.balign 4
+setup_sig:
+	.long SETUP_SIGNATURE
diff --git a/arch/x86/boot/setup.ld b/arch/x86/boot/setup.ld
index e1d594a60204..7515ab011783 100644
--- a/arch/x86/boot/setup.ld
+++ b/arch/x86/boot/setup.ld
@@ -10,19 +10,14 @@ ENTRY(_start)
 SECTIONS
 {
 	. = 0;
-	.bstext	: {
-		*(.bstext)
-		. = 495;
-	} =0xffffffff
-
 	.header		: { *(.header) }
-	.entrytext	: { *(.entrytext) }
-	.inittext	: { *(.inittext) }
+	.entrytext	: { *(.entrytext) }	= 0xcccccccc
+	.inittext	: { *(.inittext) }	= 0xcccccccc
 	.initdata	: { *(.initdata) }
 	__end_init = .;
 
-	.text		: { *(.text .text.*) }
-	.text32		: { *(.text32) }
+	.text		: { *(.text .text.*) }	= 0xcccccccc
+	.text32		: { *(.text32) }	= 0xcccccccc
 
 	.pecompat	: { *(.pecompat) }
 	PROVIDE(pecompat_fsize = setup_size - pecompat_fstart);
@@ -40,9 +35,7 @@ SECTIONS
 	.data		: { *(.data*) }
 
 	.signature	: {
-		setup_sig = .;
-		LONG(0x5a5aaa55)
-
+		*(.signature)
 		setup_size = ALIGN(ABSOLUTE(.), 4096);
 		setup_sects = ABSOLUTE(setup_size / 512);
 		ASSERT(setup_sects >= 5, "The setup must be at least 5 sectors in size");
@@ -64,11 +57,16 @@ SECTIONS
 	}
 
 	/*
-	 * The ASSERT() sink to . is intentional, for binutils 2.14 compatibility:
+	 * The ASSERT() sink to . is intentional. A bare ASSERT()
+	 * outside of an output section is believed to have been broken
+	 * in some binutils versions, although it is supposed to have
+	 * been supported since binutils 2.15. Either way, it doesn't hurt,
+	 * so there is no reason to drop it.
 	 */
 	. = ASSERT(_end <= 0x8000, "Setup too big!");
 	. = ASSERT(hdr == 0x1f1, "The setup header has the wrong offset!");
+	. = ASSERT(end_of_bzheader <= 512+2+127, "bzImage header overflow!");
+	. = ASSERT(end_of_bzheader == start_of_setup, "padding bytes between .bzheader and .entrytext!");
 	/* Necessary for the very-old-loader check to work... */
 	. = ASSERT(__end_init <= 5*512, "init sections too big!");
-
 }

---

## [6] H. Peter Anvin — 2026-01-20
*Subject: [PATCH v1 05/14] x86/boot: call puts() from within die()*

Every call to die() has a call to puts() in front of it, which adds
unnecessary code bloat. Move the puts() into die() which, being a
noreturn function, is terminal and allows the compiler to not generate
unnecessary code around it.

Signed-off-by: H. Peter Anvin (Intel) <hpa@zytor.com>
---
 arch/x86/boot/boot.h   | 2 +-
 arch/x86/boot/header.S | 5 +++--
 arch/x86/boot/main.c   | 6 ++----
 arch/x86/boot/pm.c     | 6 ++----
 4 files changed, 8 insertions(+), 11 deletions(-)

diff --git a/arch/x86/boot/boot.h b/arch/x86/boot/boot.h
index 1f2b7252e387..b4eb8405ba55 100644
--- a/arch/x86/boot/boot.h
+++ b/arch/x86/boot/boot.h
@@ -280,7 +280,7 @@ void console_init(void);
 void query_edd(void);
 
 /* header.S */
-void __noreturn die(void);
+void __noreturn die(const char *msg);
 
 /* memory.c */
 void detect_memory(void);
diff --git a/arch/x86/boot/header.S b/arch/x86/boot/header.S
index 85a21d576f5b..5a54d33e51c2 100644
--- a/arch/x86/boot/header.S
+++ b/arch/x86/boot/header.S
@@ -611,14 +611,15 @@ SETUP_SIGNATURE = 0x5a5aaa55
 # Setup corrupt somehow...
 setup_bad:
 	movl	$setup_corrupt, %eax
-	calll	puts
 	# Fall through...
 
 	.globl	die
 	.type	die, @function
 die:
+	calll	puts
+1:
 	hlt
-	jmp	die
+	jmp	1b
 
 	.size	die, .-die
 
diff --git a/arch/x86/boot/main.c b/arch/x86/boot/main.c
index da01ade4959e..ad8869aad6db 100644
--- a/arch/x86/boot/main.c
+++ b/arch/x86/boot/main.c
@@ -143,10 +143,8 @@ void main(void)
 	init_heap();
 
 	/* Make sure we have all the proper CPU support */
-	if (validate_cpu()) {
-		puts("Unable to boot - please use a kernel appropriate for your CPU.\n");
-		die();
-	}
+	if (validate_cpu())
+		die("Unable to boot - please use a kernel appropriate for your CPU.\n");
 
 	/* Tell the BIOS what CPU mode we intend to run in */
 	set_bios_mode();
diff --git a/arch/x86/boot/pm.c b/arch/x86/boot/pm.c
index 5941f930f6c5..3be89ba4b1b3 100644
--- a/arch/x86/boot/pm.c
+++ b/arch/x86/boot/pm.c
@@ -106,10 +106,8 @@ void go_to_protected_mode(void)
 	realmode_switch_hook();
 
 	/* Enable the A20 gate */
-	if (enable_a20()) {
-		puts("A20 gate not responding, unable to boot...\n");
-		die();
-	}
+	if (enable_a20())
+		die("A20 gate not responding, unable to boot...\n");
 
 	/* Reset coprocessor (IGNNE#) */
 	reset_coprocessor();

---

## [7] H. Peter Anvin — 2026-01-20
*Subject: [PATCH v1 06/14] x86/boot: add comment barriers for the different headers*

Add better comment barriers at the top of the PECOFF header and the
bzImage header to make it easier to find the source for the respective
chunks of data.

Signed-off-by: H. Peter Anvin (Intel) <hpa@zytor.com>
---
 arch/x86/boot/header.S | 7 ++++++-
 1 file changed, 6 insertions(+), 1 deletion(-)

diff --git a/arch/x86/boot/header.S b/arch/x86/boot/header.S
index 5a54d33e51c2..d74db02928e6 100644
--- a/arch/x86/boot/header.S
+++ b/arch/x86/boot/header.S
@@ -40,6 +40,9 @@ SYSSEG		= 0x1000		/* historical load address >> 4 */
 	.set	falign, 0x200
 
 	.code16
+
+# EFI PECOFF header ##########################################################
+
 	.section ".header", "a"
 #ifdef CONFIG_EFI_STUB
 	# "MZ", MS-DOS header
@@ -224,6 +227,8 @@ pecompat_fstart:
 
 #endif /* CONFIG_EFI_STUB */
 
+# bzImage header #############################################################
+
 	# hdr should be at address 0x1f1; -2 for the sentinel
 	.org	0x1f1-2, 0xff			# Fill with 0xff
 
@@ -545,7 +550,7 @@ kernel_info_offset:	.long ZO_kernel_info
 	.globl end_of_bzheader
 end_of_bzheader:
 
-# End of setup header #####################################################
+# End of bzImage header ######################################################
 
 	.section ".entrytext", "ax"
 	.globl start_of_setup

---

## [8] H. Peter Anvin — 2026-01-20
*Subject: [PATCH v1 07/14] x86/boot: factor out the 16-bit startup code from header.S*

Move the 16-bit startup code to its own assembly file, instead of
mixing it into header.S. header.S is now a pure data file.

This also means the .code16 directive is no longer needed for this
file.

Signed-off-by: H. Peter Anvin (Intel) <hpa@zytor.com>
---
 arch/x86/boot/Makefile  |   4 +-
 arch/x86/boot/header.S  |  91 +--------------------------------
 arch/x86/boot/start16.S | 108 ++++++++++++++++++++++++++++++++++++++++
 3 files changed, 112 insertions(+), 91 deletions(-)
 create mode 100644 arch/x86/boot/start16.S

diff --git a/arch/x86/boot/Makefile b/arch/x86/boot/Makefile
index 3f9fb3698d66..d7944bf196b9 100644
--- a/arch/x86/boot/Makefile
+++ b/arch/x86/boot/Makefile
@@ -22,8 +22,8 @@ subdir-		:= compressed
 
 setup-y		+= a20.o bioscall.o cmdline.o copy.o cpu.o cpuflags.o cpucheck.o
 setup-y		+= early_serial_console.o edd.o header.o main.o memory.o
-setup-y		+= pm.o pmjump.o printf.o regs.o string.o tty.o video.o
-setup-y		+= video-mode.o version.o
+setup-y		+= pm.o pmjump.o printf.o regs.o start16.o string.o tty.o
+setup-y		+= video.o video-mode.o version.o
 setup-$(CONFIG_X86_APM_BOOT) += apm.o
 
 # The link order of the video-*.o modules can matter.  In particular,
diff --git a/arch/x86/boot/header.S b/arch/x86/boot/header.S
index d74db02928e6..10b2971320f3 100644
--- a/arch/x86/boot/header.S
+++ b/arch/x86/boot/header.S
@@ -25,7 +25,6 @@
 #include "voffset.h"
 #include "zoffset.h"
 
-BOOTSEG		= 0x07C0		/* original address of boot-sector */
 SYSSEG		= 0x1000		/* historical load address >> 4 */
 
 #ifndef SVGA_MODE
@@ -39,8 +38,6 @@ SYSSEG		= 0x1000		/* historical load address >> 4 */
 	.set	salign, 0x1000
 	.set	falign, 0x200
 
-	.code16
-
 # EFI PECOFF header ##########################################################
 
 	.section ".header", "a"
@@ -277,6 +274,7 @@ type_of_loader:	.byte	0		# 0 means ancient bootloader, newer
 					# assigned ids
 
 # flags, unused bits must be zero (RFU) bit within loadflags
+		.globl	loadflags
 loadflags:
 		.byte	LOADED_HIGH	# The kernel is to be loaded high
 
@@ -301,6 +299,7 @@ ramdisk_size:	.long	0		# its size in bytes
 bootsect_kludge:
 		.long	0		# obsolete
 
+		.globl	heap_end_ptr
 heap_end_ptr:	.word	_end+STACK_SIZE-512
 					# (Header version 0x0201 or later)
 					# space from here (exclusive) down to
@@ -551,89 +550,3 @@ kernel_info_offset:	.long ZO_kernel_info
 end_of_bzheader:
 
 # End of bzImage header ######################################################
-
-	.section ".entrytext", "ax"
-	.globl start_of_setup
-start_of_setup:
-# Force %es = %ds
-	movw	%ds, %ax
-	movw	%ax, %es
-	cld
-
-# Apparently some ancient versions of LILO invoked the kernel with %ss != %ds,
-# which happened to work by accident for the old code.  Recalculate the stack
-# pointer if %ss is invalid.  Otherwise leave it alone, LOADLIN sets up the
-# stack behind its own code, so we can't blindly put it directly past the heap.
-
-	movw	%ss, %dx
-	cmpw	%ax, %dx	# %ds == %ss?
-	movw	%sp, %dx
-	je	2f		# -> assume %sp is reasonably set
-
-	# Invalid %ss, make up a new stack
-	movw	$_end, %dx
-	testb	$CAN_USE_HEAP, loadflags
-	jz	1f
-	movw	heap_end_ptr, %dx
-1:	addw	$STACK_SIZE, %dx
-	jnc	2f
-	xorw	%dx, %dx	# Prevent wraparound
-
-2:	# Now %dx should point to the end of our stack space
-	andw	$~3, %dx	# dword align (might as well...)
-	jnz	3f
-	movw	$0xfffc, %dx	# Make sure we're not zero
-3:	movw	%ax, %ss
-	movzwl	%dx, %esp	# Clear upper half of %esp
-	sti			# Now we should have a working stack
-
-# We will have entered with %cs = %ds+0x20, normalize %cs so
-# it is on par with the other segments.
-	pushw	%ds
-	pushw	$6f
-	lretw
-6:
-
-# Check signature at end of setup
-SETUP_SIGNATURE = 0x5a5aaa55
-	cmpl	$SETUP_SIGNATURE, setup_sig
-	jne	setup_bad
-
-# Zero the bss
-	movw	$__bss_start, %di
-	movw	$_end+3, %cx
-	xorl	%eax, %eax
-	subw	%di, %cx
-	shrw	$2, %cx
-	rep stosl
-
-# The C code uses %gs == 0 as invariant
-	movw	%ax, %gs
-
-# Jump to C code (should not return)
-	calll	main
-
-# Setup corrupt somehow...
-setup_bad:
-	movl	$setup_corrupt, %eax
-	# Fall through...
-
-	.globl	die
-	.type	die, @function
-die:
-	calll	puts
-1:
-	hlt
-	jmp	1b
-
-	.size	die, .-die
-
-	.section ".initdata", "a"
-setup_corrupt:
-	.byte	7
-	.string	"No setup signature found...\n"
-
-	.section ".signature", "a"
-	.balign 4
-setup_sig:
-	.long SETUP_SIGNATURE
diff --git a/arch/x86/boot/start16.S b/arch/x86/boot/start16.S
new file mode 100644
index 000000000000..3381dc0f4065
--- /dev/null
+++ b/arch/x86/boot/start16.S
@@ -0,0 +1,108 @@
+/*
+ * start16.S
+ *
+ *	Copyright (C) 1991, 1992 Linus Torvalds
+ *
+ *	Based on bootsect.S and setup.S
+ *	modified by more people than can be counted
+ *
+ *	Rewritten as a common file by H. Peter Anvin (Apr 2007)
+ *
+ * BIG FAT NOTE: We're in real mode using 64k segments.  Therefore segment
+ * addresses must be multiplied by 16 to obtain their respective linear
+ * addresses. To avoid confusion, linear addresses are written using leading
+ * hex while segment addresses are written as segment:offset.
+ *
+ * This code must *immediately* follow the bzImage header, so DO NOT
+ * add alignment directives anywhere in the .entrytext section!
+ */
+
+#include <asm/bootparam.h>
+#include "boot.h"
+
+	.code16
+	.section ".entrytext", "ax"
+	.globl start_of_setup
+start_of_setup:
+# Force %es = %ds
+	movw	%ds, %ax
+	movw	%ax, %es
+	cld
+
+# Apparently some ancient versions of LILO invoked the kernel with %ss != %ds,
+# which happened to work by accident for the old code.  Recalculate the stack
+# pointer if %ss is invalid.  Otherwise leave it alone, LOADLIN sets up the
+# stack behind its own code, so we can't blindly put it directly past the heap.
+
+	movw	%ss, %dx
+	cmpw	%ax, %dx	# %ds == %ss?
+	movw	%sp, %dx
+	je	2f		# -> assume %sp is reasonably set
+
+	# Invalid %ss, make up a new stack
+	movw	$_end, %dx
+	testb	$CAN_USE_HEAP, loadflags
+	jz	1f
+	movw	heap_end_ptr, %dx
+1:	addw	$STACK_SIZE, %dx
+	jnc	2f
+	xorw	%dx, %dx	# Prevent wraparound
+
+2:	# Now %dx should point to the end of our stack space
+	andw	$~3, %dx	# dword align (might as well...)
+	jnz	3f
+	movw	$0xfffc, %dx	# Make sure we're not zero
+3:	movw	%ax, %ss
+	movzwl	%dx, %esp	# Clear upper half of %esp
+	sti			# Now we should have a working stack
+
+# We will have entered with %cs = %ds+0x20, normalize %cs so
+# it is on par with the other segments.
+	pushw	%ds
+	pushw	$6f
+	lretw
+6:
+
+# Check signature at end of setup
+SETUP_SIGNATURE = 0x5a5aaa55
+	cmpl	$SETUP_SIGNATURE, setup_sig
+	jne	setup_bad
+
+# Zero the bss
+	movw	$__bss_start, %di
+	movw	$_end+3, %cx
+	xorl	%eax, %eax
+	subw	%di, %cx
+	shrw	$2, %cx
+	rep stosl
+
+# The C code uses %gs == 0 as invariant
+	movw	%ax, %gs
+
+# Jump to C code (should not return)
+	calll	main
+
+# Setup corrupt somehow...
+setup_bad:
+	movl	$setup_corrupt, %eax
+	# Fall through...
+
+	.globl	die
+	.type	die, @function
+die:
+	calll	puts
+1:
+	hlt
+	jmp	1b
+
+	.size	die, .-die
+
+	.section ".initdata", "a"
+setup_corrupt:
+	.byte	7
+	.string	"No setup signature found...\n"
+
+	.section ".signature", "a"
+	.balign 4
+setup_sig:
+	.long SETUP_SIGNATURE

---

## [9] H. Peter Anvin — 2026-01-20
*Subject: [PATCH v1 08/14] x86: make CONFIG_EFI_STUB unconditional*

The EFI stub code is mature, most current x86 systems require EFI to
boot, and as it is exclusively preboot code, it doesn't affect the
runtime memory footprint at all.

It makes absolutely no sense to omit it anymore, so make it
unconditional.

Signed-off-by: H. Peter Anvin (Intel) <hpa@zytor.com>
---
 arch/x86/Kconfig                  | 14 ++------------
 arch/x86/boot/compressed/Makefile |  2 --
 arch/x86/boot/compressed/error.c  |  2 --
 arch/x86/boot/header.S            |  3 ---
 4 files changed, 2 insertions(+), 19 deletions(-)

diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
index 80527299f859..14e2b00a3815 100644
--- a/arch/x86/Kconfig
+++ b/arch/x86/Kconfig
@@ -907,7 +907,6 @@ config INTEL_TDX_GUEST
 	bool "Intel TDX (Trust Domain Extensions) - Guest Support"
 	depends on X86_64 && CPU_SUP_INTEL
 	depends on X86_X2APIC
-	depends on EFI_STUB
 	depends on PARAVIRT
 	select ARCH_HAS_CC_PLATFORM
 	select X86_MEM_ENCRYPT
@@ -1495,7 +1494,6 @@ config X86_MEM_ENCRYPT
 config AMD_MEM_ENCRYPT
 	bool "AMD Secure Memory Encryption (SME) support"
 	depends on X86_64 && CPU_SUP_AMD
-	depends on EFI_STUB
 	select DMA_COHERENT_POOL
 	select ARCH_USE_MEMREMAP_PROT
 	select INSTRUCTION_DECODER
@@ -1929,18 +1927,10 @@ config EFI
 	  platforms.
 
 config EFI_STUB
-	bool "EFI stub support"
-	depends on EFI
-	select RELOCATABLE
-	help
-	  This kernel feature allows a bzImage to be loaded directly
-	  by EFI firmware without the use of a bootloader.
-
-	  See Documentation/admin-guide/efi-stub.rst for more information.
+       def_bool y
 
 config EFI_HANDOVER_PROTOCOL
 	bool "EFI handover protocol (DEPRECATED)"
-	depends on EFI_STUB
 	default y
 	help
 	  Select this in order to include support for the deprecated EFI
@@ -1957,7 +1947,7 @@ config EFI_HANDOVER_PROTOCOL
 
 config EFI_MIXED
 	bool "EFI mixed-mode support"
-	depends on EFI_STUB && X86_64
+	depends on X86_64
 	help
 	  Enabling this feature allows a 64-bit kernel to be booted
 	  on a 32-bit firmware, provided that your CPU supports 64-bit
diff --git a/arch/x86/boot/compressed/Makefile b/arch/x86/boot/compressed/Makefile
index 68f9d7a1683b..6cbcf01c8bad 100644
--- a/arch/x86/boot/compressed/Makefile
+++ b/arch/x86/boot/compressed/Makefile
@@ -66,11 +66,9 @@ LDFLAGS_vmlinux += -z noexecstack
 ifeq ($(CONFIG_LD_IS_BFD),y)
 LDFLAGS_vmlinux += $(call ld-option,--no-warn-rwx-segments)
 endif
-ifeq ($(CONFIG_EFI_STUB),y)
 # ensure that the static EFI stub library will be pulled in, even if it is
 # never referenced explicitly from the startup code
 LDFLAGS_vmlinux += -u efi_pe_entry
-endif
 LDFLAGS_vmlinux += -T
 
 hostprogs	:= mkpiggy
diff --git a/arch/x86/boot/compressed/error.c b/arch/x86/boot/compressed/error.c
index 19a8251de506..f2d21e57c109 100644
--- a/arch/x86/boot/compressed/error.c
+++ b/arch/x86/boot/compressed/error.c
@@ -24,7 +24,6 @@ void error(char *m)
 }
 
 /* EFI libstub  provides vsnprintf() */
-#ifdef CONFIG_EFI_STUB
 void panic(const char *fmt, ...)
 {
 	static char buf[1024];
@@ -40,4 +39,3 @@ void panic(const char *fmt, ...)
 
 	error(buf);
 }
-#endif
diff --git a/arch/x86/boot/header.S b/arch/x86/boot/header.S
index 10b2971320f3..776bd0631bce 100644
--- a/arch/x86/boot/header.S
+++ b/arch/x86/boot/header.S
@@ -41,7 +41,6 @@ SYSSEG		= 0x1000		/* historical load address >> 4 */
 # EFI PECOFF header ##########################################################
 
 	.section ".header", "a"
-#ifdef CONFIG_EFI_STUB
 	# "MZ", MS-DOS header
 	.word	IMAGE_DOS_SIGNATURE
 	.org	0x38
@@ -222,8 +221,6 @@ pecompat_fstart:
 
 	.set	section_count, (. - section_table) / 40
 
-#endif /* CONFIG_EFI_STUB */
-
 # bzImage header #############################################################
 
 	# hdr should be at address 0x1f1; -2 for the sentinel

---

## [10] H. Peter Anvin — 2026-01-20
*Subject: [PATCH v1 09/14] x86/boot: make the relocatable kernel unconditional*

There is absolutely no valid reason to build a non-relocatable kernel
anymore. It has no effect on the runtime memory footprint since it is
handled entirely in preboot code. Futhermore, the relocatable kernel
is required for EFI stub support.

Remove CONFIG_RELOCATABLE and make the non-relocatable kernel
unconditional.

Signed-off-by: H. Peter Anvin (Intel) <hpa@zytor.com>
---
 arch/x86/Kconfig                   | 71 ++++--------------------------
 arch/x86/boot/compressed/head_32.S |  2 -
 arch/x86/boot/compressed/head_64.S |  4 --
 arch/x86/boot/compressed/misc.c    |  8 ----
 arch/x86/boot/header.S             | 12 +----
 5 files changed, 11 insertions(+), 86 deletions(-)

diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
index 14e2b00a3815..a0fe0349fb77 100644
--- a/arch/x86/Kconfig
+++ b/arch/x86/Kconfig
@@ -2018,61 +2018,16 @@ config PHYSICAL_START
 	help
 	  This gives the physical address where the kernel is loaded.
 
-	  If the kernel is not relocatable (CONFIG_RELOCATABLE=n) then bzImage
-	  will decompress itself to above physical address and run from there.
-	  Otherwise, bzImage will run from the address where it has been loaded
-	  by the boot loader. The only exception is if it is loaded below the
-	  above physical address, in which case it will relocate itself there.
-
-	  In normal kdump cases one does not have to set/change this option
-	  as now bzImage can be compiled as a completely relocatable image
-	  (CONFIG_RELOCATABLE=y) and be used to load and run from a different
-	  address. This option is mainly useful for the folks who don't want
-	  to use a bzImage for capturing the crash dump and want to use a
-	  vmlinux instead. vmlinux is not relocatable hence a kernel needs
-	  to be specifically compiled to run from a specific memory area
-	  (normally a reserved region) and this option comes handy.
-
-	  So if you are using bzImage for capturing the crash dump,
-	  leave the value here unchanged to 0x1000000 and set
-	  CONFIG_RELOCATABLE=y.  Otherwise if you plan to use vmlinux
-	  for capturing the crash dump change this value to start of
-	  the reserved region.  In other words, it can be set based on
-	  the "X" value as specified in the "crashkernel=YM@XM"
-	  command line boot parameter passed to the panic-ed
-	  kernel. Please take a look at Documentation/admin-guide/kdump/kdump.rst
-	  for more details about crash dumps.
-
-	  Usage of bzImage for capturing the crash dump is recommended as
-	  one does not have to build two kernels. Same kernel can be used
-	  as production kernel and capture kernel. Above option should have
-	  gone away after relocatable bzImage support is introduced. But it
-	  is present because there are users out there who continue to use
-	  vmlinux for dump capture. This option should go away down the
-	  line.
+	  If the kernel is loaded at a physical address below this address
+	  by the boot loader it will relocate itself there.
 
-	  Don't change this unless you know what you are doing.
+	  The addresses in the vmlinux and System.map files are based
+	  at this address.
 
-config RELOCATABLE
-	bool "Build a relocatable kernel"
-	default y
-	help
-	  This builds a kernel image that retains relocation information
-	  so it can be loaded someplace besides the default 1MB.
-	  The relocations tend to make the kernel binary about 10% larger,
-	  but are discarded at runtime.
-
-	  One use is for the kexec on panic case where the recovery kernel
-	  must live at a different physical address than the primary
-	  kernel.
-
-	  Note: If CONFIG_RELOCATABLE=y, then the kernel runs from the address
-	  it has been loaded at and the compile time physical address
-	  (CONFIG_PHYSICAL_START) is used as the minimum location.
+	  Don't change this unless you know what you are doing.
 
 config RANDOMIZE_BASE
 	bool "Randomize the address of the kernel image (KASLR)"
-	depends on RELOCATABLE
 	default y
 	help
 	  In support of Kernel Address Space Layout Randomization (KASLR),
@@ -2108,7 +2063,7 @@ config RANDOMIZE_BASE
 # Relocation on x86 needs some additional build support
 config X86_NEED_RELOCS
 	def_bool y
-	depends on RANDOMIZE_BASE || (X86_32 && RELOCATABLE)
+	depends on RANDOMIZE_BASE || X86_32
 	select ARCH_VMLINUX_NEEDS_RELOCS
 
 config PHYSICAL_ALIGN
@@ -2121,17 +2076,9 @@ config PHYSICAL_ALIGN
 	  where kernel is loaded and run from. Kernel is compiled for an
 	  address which meets above alignment restriction.
 
-	  If bootloader loads the kernel at a non-aligned address and
-	  CONFIG_RELOCATABLE is set, kernel will move itself to nearest
-	  address aligned to above value and run from there.
-
-	  If bootloader loads the kernel at a non-aligned address and
-	  CONFIG_RELOCATABLE is not set, kernel will ignore the run time
-	  load address and decompress itself to the address it has been
-	  compiled for and run from there. The address for which kernel is
-	  compiled already meets above alignment restrictions. Hence the
-	  end result is that kernel runs from a physical address meeting
-	  above alignment restrictions.
+	  If bootloader loads the kernel at a non-aligned address the
+	  kernel will move itself upwards to the nearest address
+	  aligned to above value and run from there.
 
 	  On 32-bit this value must be a multiple of 0x2000. On 64-bit
 	  this value must be a multiple of 0x200000.
diff --git a/arch/x86/boot/compressed/head_32.S b/arch/x86/boot/compressed/head_32.S
index 1cfe9802a42f..79d9e2c330ba 100644
--- a/arch/x86/boot/compressed/head_32.S
+++ b/arch/x86/boot/compressed/head_32.S
@@ -82,7 +82,6 @@ SYM_FUNC_START(startup_32)
  * %ebp is calculated to be the address that the kernel will be decompressed to.
  */
 
-#ifdef CONFIG_RELOCATABLE
 	leal	startup_32@GOTOFF(%edx), %ebx
 	movl	BP_kernel_alignment(%esi), %eax
 	decl	%eax
@@ -91,7 +90,6 @@ SYM_FUNC_START(startup_32)
 	andl    %eax, %ebx
 	cmpl	$LOAD_PHYSICAL_ADDR, %ebx
 	jae	1f
-#endif
 	movl	$LOAD_PHYSICAL_ADDR, %ebx
 1:
 
diff --git a/arch/x86/boot/compressed/head_64.S b/arch/x86/boot/compressed/head_64.S
index d9dab940ff62..8a964a4d45c2 100644
--- a/arch/x86/boot/compressed/head_64.S
+++ b/arch/x86/boot/compressed/head_64.S
@@ -143,7 +143,6 @@ SYM_FUNC_START(startup_32)
  * for safe in-place decompression.
  */
 
-#ifdef CONFIG_RELOCATABLE
 	movl	%ebp, %ebx
 	movl	BP_kernel_alignment(%esi), %eax
 	decl	%eax
@@ -152,7 +151,6 @@ SYM_FUNC_START(startup_32)
 	andl	%eax, %ebx
 	cmpl	$LOAD_PHYSICAL_ADDR, %ebx
 	jae	1f
-#endif
 	movl	$LOAD_PHYSICAL_ADDR, %ebx
 1:
 
@@ -312,7 +310,6 @@ SYM_CODE_START(startup_64)
 	 */
 
 	/* Start with the delta to where the kernel will run at. */
-#ifdef CONFIG_RELOCATABLE
 	leaq	startup_32(%rip) /* - $startup_32 */, %rbp
 	movl	BP_kernel_alignment(%rsi), %eax
 	decl	%eax
@@ -321,7 +318,6 @@ SYM_CODE_START(startup_64)
 	andq	%rax, %rbp
 	cmpq	$LOAD_PHYSICAL_ADDR, %rbp
 	jae	1f
-#endif
 	movq	$LOAD_PHYSICAL_ADDR, %rbp
 1:
 
diff --git a/arch/x86/boot/compressed/misc.c b/arch/x86/boot/compressed/misc.c
index 0f41ca0e52c0..0cdc164286fc 100644
--- a/arch/x86/boot/compressed/misc.c
+++ b/arch/x86/boot/compressed/misc.c
@@ -314,12 +314,8 @@ static size_t parse_elf(void *output)
 			if ((phdr->p_align % 0x200000) != 0)
 				error("Alignment of LOAD segment isn't multiple of 2MB");
 #endif
-#ifdef CONFIG_RELOCATABLE
 			dest = output;
 			dest += (phdr->p_paddr - LOAD_PHYSICAL_ADDR);
-#else
-			dest = (void *)(phdr->p_paddr);
-#endif
 			memmove(dest, output + phdr->p_offset, phdr->p_filesz);
 			break;
 		default: /* Ignore other PT_* */ break;
@@ -506,10 +502,6 @@ asmlinkage __visible void *extract_kernel(void *rmode, unsigned char *output)
 	if (heap > ((-__PAGE_OFFSET-(128<<20)-1) & 0x7fffffff))
 		error("Destination address too large");
 #endif
-#ifndef CONFIG_RELOCATABLE
-	if (virt_addr != LOAD_PHYSICAL_ADDR)
-		error("Destination virtual address changed when not relocatable");
-#endif
 
 	debug_putstr("\nDecompressing Linux... ");
 
diff --git a/arch/x86/boot/header.S b/arch/x86/boot/header.S
index 776bd0631bce..2828b25707bb 100644
--- a/arch/x86/boot/header.S
+++ b/arch/x86/boot/header.S
@@ -334,24 +334,16 @@ initrd_addr_max: .long 0x7fffffff
 kernel_alignment:  .long CONFIG_PHYSICAL_ALIGN	#physical addr alignment
 						#required for protected mode
 						#kernel
-#ifdef CONFIG_RELOCATABLE
-relocatable_kernel:    .byte 1
-#else
-relocatable_kernel:    .byte 0
-#endif
+relocatable_kernel:	.byte 1			# Always relocatable
 min_alignment:		.byte MIN_KERNEL_ALIGN_LG2	# minimum alignment
 
 xloadflags:
 #ifdef CONFIG_X86_64
 # define XLF0 XLF_KERNEL_64			/* 64-bit kernel */
-#else
-# define XLF0 0
-#endif
-
-#if defined(CONFIG_RELOCATABLE) && defined(CONFIG_X86_64)
    /* kernel/boot_param/ramdisk could be loaded above 4g */
 # define XLF1 XLF_CAN_BE_LOADED_ABOVE_4G
 #else
+# define XLF0 0
 # define XLF1 0
 #endif

---

## [11] H. Peter Anvin — 2026-01-20
*Subject: [PATCH v1 10/14] x86/boot: explicitly put the old command line pointer in header.S*

Put the location for the old command line pointer into header.S. This
not only makes the layout of the header data more explicit, but it
also removes the need for the absolute_pointer() hack in
arch/x86/boot/main.c.

Signed-off-by: H. Peter Anvin (Intel) <hpa@zytor.com>
---
 arch/x86/boot/header.S |  7 +++++++
 arch/x86/boot/main.c   | 32 ++++++++++++++++----------------
 2 files changed, 23 insertions(+), 16 deletions(-)

diff --git a/arch/x86/boot/header.S b/arch/x86/boot/header.S
index 2828b25707bb..4eb12443dafa 100644
--- a/arch/x86/boot/header.S
+++ b/arch/x86/boot/header.S
@@ -43,6 +43,13 @@ SYSSEG		= 0x1000		/* historical load address >> 4 */
 	.section ".header", "a"
 	# "MZ", MS-DOS header
 	.word	IMAGE_DOS_SIGNATURE
+
+	.org	0x20
+	# Used for the command line protocol in boot protocols 2.00-2.01
+	.globl	old_cmdline
+old_cmdline:
+	.word	0, 0
+
 	.org	0x38
 	#
 	# Offset to the PE header.
diff --git a/arch/x86/boot/main.c b/arch/x86/boot/main.c
index ad8869aad6db..864da3deab18 100644
--- a/arch/x86/boot/main.c
+++ b/arch/x86/boot/main.c
@@ -22,36 +22,36 @@ char *HEAP = _end;
 char *heap_end = _end;		/* Default end of heap = no heap */
 
 /*
- * Copy the header into the boot parameter block.  Since this
- * screws up the old-style command line protocol, adjust by
- * filling in the new-style command line pointer instead.
+ * Copy the header into the boot parameter block.  Since this screws
+ * up the old-style command line protocol (protocol 2.00-2.01), adjust
+ * by filling in the new-style command line pointer instead.
  */
+struct old_cmdline {
+	u16 cl_magic;
+	u16 cl_offset;
+};
+extern const struct old_cmdline old_cmdline;
+
 static void copy_boot_params(void)
 {
-	struct old_cmdline {
-		u16 cl_magic;
-		u16 cl_offset;
-	};
-	const struct old_cmdline * const oldcmd = absolute_pointer(OLD_CL_ADDRESS);
-
 	BUILD_BUG_ON(sizeof(boot_params) != 4096);
 	memcpy(&boot_params.hdr, &hdr, sizeof(hdr));
 
-	if (!boot_params.hdr.cmd_line_ptr && oldcmd->cl_magic == OLD_CL_MAGIC) {
+	if (!boot_params.hdr.cmd_line_ptr &&
+	    old_cmdline.cl_magic == OLD_CL_MAGIC) {
 		/* Old-style command line protocol */
-		u16 cmdline_seg;
+		u32 cmdline_base = 0x90000;
 
 		/*
 		 * Figure out if the command line falls in the region
 		 * of memory that an old kernel would have copied up
 		 * to 0x90000...
 		 */
-		if (oldcmd->cl_offset < boot_params.hdr.setup_move_size)
-			cmdline_seg = ds();
-		else
-			cmdline_seg = 0x9000;
+		if (old_cmdline.cl_offset < boot_params.hdr.setup_move_size)
+			cmdline_base = ds() << 4;
 
-		boot_params.hdr.cmd_line_ptr = (cmdline_seg << 4) + oldcmd->cl_offset;
+		boot_params.hdr.cmd_line_ptr =
+			cmdline_base + old_cmdline.cl_offset;
 	}
 }

---

## [12] H. Peter Anvin — 2026-01-20
*Subject: [PATCH v1 11/14] x86/boot: use __seg_fs and __seg_gs in the real-mode boot code*

All supported versions of gcc support __seg_fs and __seg_gs now.
All supported versions of clang support __seg_fs and __seg_gs too,
except for two bugs (as of clang 21, at least):

1. The %fs: and %gs: prefix does not get emitted in inline assembly.
2. An internal compiler error when addressing symbols directly.

However, none of these are required in the boot code. Furthermore,
this makes it possible to remove the absolute_pointer() hack in the
fs/gs access functions.

This requires adding a barrier() to a20.c, to prevent the compiler
from eliding the load from the aliased memory address.

Remove the unused memcmp_[fg]s() functions.

Finally, ds() is by necessity constant, so mark the function as such.

Signed-off-by: H. Peter Anvin (Intel) <hpa@zytor.com>
---
 arch/x86/boot/a20.c  |  1 +
 arch/x86/boot/boot.h | 81 ++++++++++++++------------------------------
 2 files changed, 27 insertions(+), 55 deletions(-)

diff --git a/arch/x86/boot/a20.c b/arch/x86/boot/a20.c
index 3ab6cd8eaa31..52c3fccdcb70 100644
--- a/arch/x86/boot/a20.c
+++ b/arch/x86/boot/a20.c
@@ -63,6 +63,7 @@ static int a20_test(int loops)
 	while (loops--) {
 		wrgs32(++ctr, A20_TEST_ADDR);
 		io_delay();	/* Serialize and make delay constant */
+		barrier();	/* Compiler won't know about fs/gs overlap */
 		ok = rdfs32(A20_TEST_ADDR+0x10) ^ ctr;
 		if (ok)
 			break;
diff --git a/arch/x86/boot/boot.h b/arch/x86/boot/boot.h
index b4eb8405ba55..4d3549ed7987 100644
--- a/arch/x86/boot/boot.h
+++ b/arch/x86/boot/boot.h
@@ -45,7 +45,7 @@ static inline void io_delay(void)
 
 /* These functions are used to reference data in other segments. */
 
-static inline u16 ds(void)
+static inline __attribute_const__ u16 ds(void)
 {
 	u16 seg;
 	asm("movw %%ds,%0" : "=rm" (seg));
@@ -54,7 +54,7 @@ static inline u16 ds(void)
 
 static inline void set_fs(u16 seg)
 {
-	asm volatile("movw %0,%%fs" : : "rm" (seg));
+	asm volatile("movw %0,%%fs" : : "rm" (seg) : "memory");
 }
 static inline u16 fs(void)
 {
@@ -65,7 +65,7 @@ static inline u16 fs(void)
 
 static inline void set_gs(u16 seg)
 {
-	asm volatile("movw %0,%%gs" : : "rm" (seg));
+	asm volatile("movw %0,%%gs" : : "rm" (seg) : "memory");
 }
 static inline u16 gs(void)
 {
@@ -76,96 +76,67 @@ static inline u16 gs(void)
 
 typedef unsigned int addr_t;
 
+/*
+ * WARNING: as of clang 21, clang has the following two bugs related
+ * to __seg_fs and __seg_gs:
+ *
+ * 1. The %fs: and %gs: prefix does not get emitted in inline assembly.
+ * 2. An internal compiler error when addressing symbols directly.
+ *
+ * Neither of those constructs are currently used in the boot code.
+ * If they ever are, and those bugs still remain, then those bugs will
+ * need to be worked around.
+ */
 static inline u8 rdfs8(addr_t addr)
 {
-	u8 *ptr = (u8 *)absolute_pointer(addr);
-	u8 v;
-	asm volatile("movb %%fs:%1,%0" : "=q" (v) : "m" (*ptr));
-	return v;
+	return *(__seg_fs const u8 *)addr;
 }
 static inline u16 rdfs16(addr_t addr)
 {
-	u16 *ptr = (u16 *)absolute_pointer(addr);
-	u16 v;
-	asm volatile("movw %%fs:%1,%0" : "=r" (v) : "m" (*ptr));
-	return v;
+	return *(__seg_fs const u16 *)addr;
 }
 static inline u32 rdfs32(addr_t addr)
 {
-	u32 *ptr = (u32 *)absolute_pointer(addr);
-	u32 v;
-	asm volatile("movl %%fs:%1,%0" : "=r" (v) : "m" (*ptr));
-	return v;
+	return *(__seg_fs const u32 *)addr;
 }
 
 static inline void wrfs8(u8 v, addr_t addr)
 {
-	u8 *ptr = (u8 *)absolute_pointer(addr);
-	asm volatile("movb %1,%%fs:%0" : "+m" (*ptr) : "qi" (v));
+	*(__seg_fs u8 *)addr = v;
 }
 static inline void wrfs16(u16 v, addr_t addr)
 {
-	u16 *ptr = (u16 *)absolute_pointer(addr);
-	asm volatile("movw %1,%%fs:%0" : "+m" (*ptr) : "ri" (v));
+	*(__seg_fs u16 *)addr = v;
 }
 static inline void wrfs32(u32 v, addr_t addr)
 {
-	u32 *ptr = (u32 *)absolute_pointer(addr);
-	asm volatile("movl %1,%%fs:%0" : "+m" (*ptr) : "ri" (v));
+	*(__seg_fs u32 *)addr = v;
 }
 
 static inline u8 rdgs8(addr_t addr)
 {
-	u8 *ptr = (u8 *)absolute_pointer(addr);
-	u8 v;
-	asm volatile("movb %%gs:%1,%0" : "=q" (v) : "m" (*ptr));
-	return v;
+	return *(__seg_gs const u8 *)addr;
 }
 static inline u16 rdgs16(addr_t addr)
 {
-	u16 *ptr = (u16 *)absolute_pointer(addr);
-	u16 v;
-	asm volatile("movw %%gs:%1,%0" : "=r" (v) : "m" (*ptr));
-	return v;
+	return *(__seg_gs const u16 *)addr;
 }
 static inline u32 rdgs32(addr_t addr)
 {
-	u32 *ptr = (u32 *)absolute_pointer(addr);
-	u32 v;
-	asm volatile("movl %%gs:%1,%0" : "=r" (v) : "m" (*ptr));
-	return v;
+	return *(__seg_gs const u32 *)addr;
 }
 
 static inline void wrgs8(u8 v, addr_t addr)
 {
-	u8 *ptr = (u8 *)absolute_pointer(addr);
-	asm volatile("movb %1,%%gs:%0" : "+m" (*ptr) : "qi" (v));
+	*(__seg_gs u8 *)addr = v;
 }
 static inline void wrgs16(u16 v, addr_t addr)
 {
-	u16 *ptr = (u16 *)absolute_pointer(addr);
-	asm volatile("movw %1,%%gs:%0" : "+m" (*ptr) : "ri" (v));
+	*(__seg_gs u16 *)addr = v;
 }
 static inline void wrgs32(u32 v, addr_t addr)
 {
-	u32 *ptr = (u32 *)absolute_pointer(addr);
-	asm volatile("movl %1,%%gs:%0" : "+m" (*ptr) : "ri" (v));
-}
-
-/* Note: these only return true/false, not a signed return value! */
-static inline bool memcmp_fs(const void *s1, addr_t s2, size_t len)
-{
-	bool diff;
-	asm volatile("fs repe cmpsb"
-		     : "=@ccnz" (diff), "+D" (s1), "+S" (s2), "+c" (len));
-	return diff;
-}
-static inline bool memcmp_gs(const void *s1, addr_t s2, size_t len)
-{
-	bool diff;
-	asm volatile("gs repe cmpsb"
-		     : "=@ccnz" (diff), "+D" (s1), "+S" (s2), "+c" (len));
-	return diff;
+	*(__seg_gs u32 *)addr = v;
 }
 
 /* Heap -- available for dynamic lists. */

---

## [13] H. Peter Anvin — 2026-01-20
*Subject: [PATCH v1 12/14] x86/boot: tweak a20.c for better code generation*

Do some minor tweaks to arch/x86/boot/a20.c for better code
generation, made possible by the __seg_fs/__seg_gs changes.

Move the die() call to a20.c itself; there is no reason to push an
error code upwards just to die() there.

Signed-off-by: H. Peter Anvin (Intel) <hpa@zytor.com>
---
 arch/x86/boot/a20.c  | 24 +++++++++++-------------
 arch/x86/boot/boot.h |  2 +-
 arch/x86/boot/pm.c   |  3 +--
 3 files changed, 13 insertions(+), 16 deletions(-)

diff --git a/arch/x86/boot/a20.c b/arch/x86/boot/a20.c
index 52c3fccdcb70..38a1cad8a553 100644
--- a/arch/x86/boot/a20.c
+++ b/arch/x86/boot/a20.c
@@ -53,24 +53,22 @@ static int empty_8042(void)
 
 static int a20_test(int loops)
 {
-	int ok = 0;
 	int saved, ctr;
 
 	set_fs(0xffff);
 
 	saved = ctr = rdgs32(A20_TEST_ADDR);
 
-	while (loops--) {
+	do {
 		wrgs32(++ctr, A20_TEST_ADDR);
 		io_delay();	/* Serialize and make delay constant */
 		barrier();	/* Compiler won't know about fs/gs overlap */
-		ok = rdfs32(A20_TEST_ADDR+0x10) ^ ctr;
-		if (ok)
+		if (rdfs32(A20_TEST_ADDR+0x10) != ctr)
 			break;
-	}
+	} while (--loops);
 
 	wrgs32(saved, A20_TEST_ADDR);
-	return ok;
+	return loops;
 }
 
 /* Quick test to see if A20 is already enabled */
@@ -125,7 +123,7 @@ static void enable_a20_fast(void)
 
 #define A20_ENABLE_LOOPS 255	/* Number of times to try */
 
-int enable_a20(void)
+void enable_a20(void)
 {
        int loops = A20_ENABLE_LOOPS;
        int kbc_err;
@@ -134,30 +132,30 @@ int enable_a20(void)
 	       /* First, check to see if A20 is already enabled
 		  (legacy free, etc.) */
 	       if (a20_test_short())
-		       return 0;
+		       return;
 
 	       /* Next, try the BIOS (INT 0x15, AX=0x2401) */
 	       enable_a20_bios();
 	       if (a20_test_short())
-		       return 0;
+		       return;
 
 	       /* Try enabling A20 through the keyboard controller */
 	       kbc_err = empty_8042();
 
 	       if (a20_test_short())
-		       return 0; /* BIOS worked, but with delayed reaction */
+		       return; /* BIOS worked, but with delayed reaction */
 
 	       if (!kbc_err) {
 		       enable_a20_kbc();
 		       if (a20_test_long())
-			       return 0;
+			      return;
 	       }
 
 	       /* Finally, try enabling the "fast A20 gate" */
 	       enable_a20_fast();
 	       if (a20_test_long())
-		       return 0;
+		       return;
        }
 
-       return -1;
+       die("A20 gate not responding, unable to boot...\n");
 }
diff --git a/arch/x86/boot/boot.h b/arch/x86/boot/boot.h
index 4d3549ed7987..584c89d0738b 100644
--- a/arch/x86/boot/boot.h
+++ b/arch/x86/boot/boot.h
@@ -167,7 +167,7 @@ void copy_to_fs(addr_t dst, void *src, size_t len);
 void *copy_from_fs(void *dst, addr_t src, size_t len);
 
 /* a20.c */
-int enable_a20(void);
+void enable_a20(void);
 
 /* apm.c */
 int query_apm_bios(void);
diff --git a/arch/x86/boot/pm.c b/arch/x86/boot/pm.c
index 3be89ba4b1b3..e39689ed65ea 100644
--- a/arch/x86/boot/pm.c
+++ b/arch/x86/boot/pm.c
@@ -106,8 +106,7 @@ void go_to_protected_mode(void)
 	realmode_switch_hook();
 
 	/* Enable the A20 gate */
-	if (enable_a20())
-		die("A20 gate not responding, unable to boot...\n");
+	enable_a20();
 
 	/* Reset coprocessor (IGNNE#) */
 	reset_coprocessor();

---

## [14] H. Peter Anvin — 2026-01-20
*Subject: [PATCH v1 13/14] x86/boot: simplify x86/boot/cmdline.c by using __seg_fs*

arch/x86/boot/cmdline.c is compiled in 16, 32, or 64-bit mode. In the
16-bit case it needs to access an out-of-data-segment pointer.

This has been handled in the past by using a *really* ugly wrapper in
the 32/64-bit code combined with an inline function in the 16-bit code.

Using __seg_fs for the real-mode case allows for a much cleaner way of
handling this difference. Futhermore, moving the code for typing and
obtaining the pointer into cmdline.c itself avoids having to create
and push an extra argument, which is particularly inefficient in the
real-mode code as it requires a range check and pushes the argument
count past 3. Furthermore, co-locating this code with the user makes it
a lot clearer what the constraints are on this code, even though it
means using #ifdef _SETUP.

Instead of limit-checking the command line to the real-mode segment
limit, limit-check it to COMMAND_LINE_SIZE (which is always less than
64K, and thus automatically incorporates the real-mode segment limit
check.)

If compiling for 32 bits, trying to add ext_cmd_line_ptr in
get_cmd_line_ptr() is futile as unsigned long, and pointers, are only
32 bits wide. Instead, limit-check the command line pointer and fail
if it is >= 4 GiB, just as the real-mode code fails if the pointer is
>= 1 MiB.

Since the kaslr code depends on get_cmd_line_ptr(), retain it as a
global function.

Signed-off-by: H. Peter Anvin (Intel) <hpa@zytor.com>
---
 arch/x86/boot/boot.h               | 23 +--------
 arch/x86/boot/cmdline.c            | 79 +++++++++++++++++++++++-------
 arch/x86/boot/compressed/cmdline.c | 29 -----------
 3 files changed, 64 insertions(+), 67 deletions(-)

diff --git a/arch/x86/boot/boot.h b/arch/x86/boot/boot.h
index 584c89d0738b..8512db8b3f8e 100644
--- a/arch/x86/boot/boot.h
+++ b/arch/x86/boot/boot.h
@@ -216,27 +216,8 @@ struct biosregs {
 void intcall(u8 int_no, const struct biosregs *ireg, struct biosregs *oreg);
 
 /* cmdline.c */
-int __cmdline_find_option(unsigned long cmdline_ptr, const char *option, char *buffer, int bufsize);
-int __cmdline_find_option_bool(unsigned long cmdline_ptr, const char *option);
-static inline int cmdline_find_option(const char *option, char *buffer, int bufsize)
-{
-	unsigned long cmd_line_ptr = boot_params.hdr.cmd_line_ptr;
-
-	if (cmd_line_ptr >= 0x100000)
-		return -1;      /* inaccessible */
-
-	return __cmdline_find_option(cmd_line_ptr, option, buffer, bufsize);
-}
-
-static inline int cmdline_find_option_bool(const char *option)
-{
-	unsigned long cmd_line_ptr = boot_params.hdr.cmd_line_ptr;
-
-	if (cmd_line_ptr >= 0x100000)
-		return -1;      /* inaccessible */
-
-	return __cmdline_find_option_bool(cmd_line_ptr, option);
-}
+int cmdline_find_option(const char *option, char *buffer, int bufsize);
+int cmdline_find_option_bool(const char *option);
 
 /* cpu.c, cpucheck.c */
 int check_cpu(int *cpu_level_ptr, int *req_level_ptr, u32 **err_flags_ptr);
diff --git a/arch/x86/boot/cmdline.c b/arch/x86/boot/cmdline.c
index 21d56ae83cdf..3f31fcbed673 100644
--- a/arch/x86/boot/cmdline.c
+++ b/arch/x86/boot/cmdline.c
@@ -11,12 +11,59 @@
  */
 
 #include "boot.h"
+#include <asm/setup.h>
+#include <asm/bootparam.h>
 
 static inline int myisspace(u8 c)
 {
 	return c <= ' ';	/* Close enough approximation */
 }
 
+#ifdef _SETUP
+typedef const char __seg_fs *cptr_t;
+static inline cptr_t get_cptr(void)
+{
+	/*
+	 * Note: there is no reason to check ext_cmd_line_ptr here,
+	 * because it falls outside of boot_params.hdr and therefore
+	 * will always be zero when entering through the real-mode
+	 * entry point.
+	 */
+	unsigned long ptr = boot_params.hdr.cmd_line_ptr;
+
+	/*
+	 * The -16 here serves two purposes:
+	 * 1. It means the segbase >= 0x100000 check also doubles as
+	 *    a check for the command line pointer being zero.
+	 * 2. It means this routine won't return a NULL pointer for
+	 *    a valid address; it will always return a pointer in the
+	 *    range 0x10-0x1f inclusive.
+	 */
+	unsigned long segbase = (ptr - 16) & ~15;
+	if (segbase >= 0x100000)
+		return NULL;
+
+	set_fs(segbase >> 4);
+	return (cptr_t)(ptr - segbase);
+}
+#else
+unsigned long get_cmd_line_ptr(void)
+{
+	unsigned long ptr = boot_params_ptr->hdr.cmd_line_ptr;
+	if (sizeof(unsigned long) > 4)
+		ptr += (u64)boot_params_ptr->ext_cmd_line_ptr << 32;
+	else if (boot_params_ptr->ext_cmd_line_ptr)
+		return 0;	/* Inaccessible due to pointer overflow */
+
+	return ptr;
+}
+typedef const char *cptr_t;
+static inline cptr_t get_cptr(void)
+{
+	return (cptr_t)get_cmd_line_ptr();
+}
+#endif
+
 /*
  * Find a non-boolean option, that is, "option=argument".  In accordance
  * with standard Linux practice, if this option is repeated, this returns
@@ -25,9 +72,9 @@ static inline int myisspace(u8 c)
  * Returns the length of the argument (regardless of if it was
  * truncated to fit in the buffer), or -1 on not found.
  */
-int __cmdline_find_option(unsigned long cmdline_ptr, const char *option, char *buffer, int bufsize)
+int cmdline_find_option(const char *option, char *buffer, int bufsize)
 {
-	addr_t cptr;
+	cptr_t cptr, eptr;
 	char c;
 	int len = -1;
 	const char *opptr = NULL;
@@ -39,13 +86,12 @@ int __cmdline_find_option(unsigned long cmdline_ptr, const char *option, char *b
 		st_bufcpy	/* Copying this to buffer */
 	} state = st_wordstart;
 
-	if (!cmdline_ptr)
-		return -1;      /* No command line */
+	cptr = get_cptr();
+	if (!cptr)
+		return -1;	/* No command line or invalid pointer */
+	eptr = cptr + COMMAND_LINE_SIZE - 1;
 
-	cptr = cmdline_ptr & 0xf;
-	set_fs(cmdline_ptr >> 4);
-
-	while (cptr < 0x10000 && (c = rdfs8(cptr++))) {
+	while (cptr < eptr && (c = *cptr++)) {
 		switch (state) {
 		case st_wordstart:
 			if (myisspace(c))
@@ -97,9 +143,9 @@ int __cmdline_find_option(unsigned long cmdline_ptr, const char *option, char *b
  * Returns the position of that option (starts counting with 1)
  * or 0 on not found
  */
-int __cmdline_find_option_bool(unsigned long cmdline_ptr, const char *option)
+int cmdline_find_option_bool(const char *option)
 {
-	addr_t cptr;
+	cptr_t cptr, eptr;
 	char c;
 	int pos = 0, wstart = 0;
 	const char *opptr = NULL;
@@ -109,14 +155,13 @@ int __cmdline_find_option_bool(unsigned long cmdline_ptr, const char *option)
 		st_wordskip,	/* Miscompare, skip */
 	} state = st_wordstart;
 
-	if (!cmdline_ptr)
-		return -1;      /* No command line */
-
-	cptr = cmdline_ptr & 0xf;
-	set_fs(cmdline_ptr >> 4);
+	cptr = get_cptr();
+	if (!cptr)
+		return -1;	/* No command line or invalid pointer */
+	eptr = cptr + COMMAND_LINE_SIZE - 1;
 
-	while (cptr < 0x10000) {
-		c = rdfs8(cptr++);
+	while (cptr <= eptr) {
+		c = *cptr++;
 		pos++;
 
 		switch (state) {
diff --git a/arch/x86/boot/compressed/cmdline.c b/arch/x86/boot/compressed/cmdline.c
index e162d7f59cc5..0d9267a21012 100644
--- a/arch/x86/boot/compressed/cmdline.c
+++ b/arch/x86/boot/compressed/cmdline.c
@@ -1,32 +1,3 @@
 // SPDX-License-Identifier: GPL-2.0
 #include "misc.h"
-
-#include <asm/bootparam.h>
-
-static unsigned long fs;
-static inline void set_fs(unsigned long seg)
-{
-	fs = seg << 4;  /* shift it back */
-}
-typedef unsigned long addr_t;
-static inline char rdfs8(addr_t addr)
-{
-	return *((char *)(fs + addr));
-}
 #include "../cmdline.c"
-unsigned long get_cmd_line_ptr(void)
-{
-	unsigned long cmd_line_ptr = boot_params_ptr->hdr.cmd_line_ptr;
-
-	cmd_line_ptr |= (u64)boot_params_ptr->ext_cmd_line_ptr << 32;
-
-	return cmd_line_ptr;
-}
-int cmdline_find_option(const char *option, char *buffer, int bufsize)
-{
-	return __cmdline_find_option(get_cmd_line_ptr(), option, buffer, bufsize);
-}
-int cmdline_find_option_bool(const char *option)
-{
-	return __cmdline_find_option_bool(get_cmd_line_ptr(), option);
-}

---

## [15] H. Peter Anvin — 2026-01-20
*Subject: [PATCH v1 14/14] compiler-gcc: Remove obsolete RELOC_HIDE() macro*

From: Uros Bizjak <ubizjak@gmail.com>

Remove the RELOC_HIDE() macro from include/linux/compiler-gcc.h.

The GCC specific macro was historically used to workaround very old
compiler bugs (including pre-4.1 ppc64 GCC). These compilers are long
obsolete.

The generic RELOC_HIDE() macro should be used instead.

The removal of the GCC specific macro results in the
following code size reduction:

     text    data     bss     dec     hex filename
  28526453        4823511  737108 34087072        20820a0 vmlinux-old.o
  28520945        4823463  737108 34081516        2080aec vmlinux-new.o

  ./bloat-o-meter vmlinux-old.o vmlinux-new.o
  add/remove: 4/14 grow/shrink: 189/674 up/down: 4433/-7865 (-3432)
  ...
  Total: Before=24103512, After=24100080, chg -0.01%

Signed-off-by: Uros Bizjak <ubizjak@gmail.com>
Cc: Thomas Gleixner <tglx@linutronix.de>
Cc: Ingo Molnar <mingo@kernel.org>
Cc: Borislav Petkov <bp@alien8.de>
Cc: Dave Hansen <dave.hansen@linux.intel.com>
Cc: "H. Peter Anvin" <hpa@zytor.com>
Cc: Linus Torvalds <torvalds@linux-foundation.org>
---
 include/linux/compiler-gcc.h | 25 -------------------------
 include/linux/compiler.h     |  8 ++++++++
 2 files changed, 8 insertions(+), 25 deletions(-)

diff --git a/include/linux/compiler-gcc.h b/include/linux/compiler-gcc.h
index 5de824a0b3d7..081e658754b9 100644
--- a/include/linux/compiler-gcc.h
+++ b/include/linux/compiler-gcc.h
@@ -10,31 +10,6 @@
 		     + __GNUC_MINOR__ * 100	\
 		     + __GNUC_PATCHLEVEL__)
 
-/*
- * This macro obfuscates arithmetic on a variable address so that gcc
- * shouldn't recognize the original var, and make assumptions about it.
- *
- * This is needed because the C standard makes it undefined to do
- * pointer arithmetic on "objects" outside their boundaries and the
- * gcc optimizers assume this is the case. In particular they
- * assume such arithmetic does not wrap.
- *
- * A miscompilation has been observed because of this on PPC.
- * To work around it we hide the relationship of the pointer and the object
- * using this macro.
- *
- * Versions of the ppc64 compiler before 4.1 had a bug where use of
- * RELOC_HIDE could trash r30. The bug can be worked around by changing
- * the inline assembly constraint from =g to =r, in this particular
- * case either is valid.
- */
-#define RELOC_HIDE(ptr, off)						\
-({									\
-	unsigned long __ptr;						\
-	__asm__ ("" : "=r"(__ptr) : "0"(ptr));				\
-	(typeof(ptr)) (__ptr + (off));					\
-})
-
 #if defined(LATENT_ENTROPY_PLUGIN) && !defined(__CHECKER__)
 #define __latent_entropy __attribute__((latent_entropy))
 #endif
diff --git a/include/linux/compiler.h b/include/linux/compiler.h
index 04487c9bd751..6affb7b44be7 100644
--- a/include/linux/compiler.h
+++ b/include/linux/compiler.h
@@ -148,6 +148,14 @@ void ftrace_likely_update(struct ftrace_likely_data *f, int val,
 	= (unsigned long)&sym;
 #endif
 
+/*
+ * This macro obfuscates arithmetic on a variable address so that the compiler
+ * shouldn't recognize the original var, and make assumptions about it.
+ *
+ * This is needed because the C standard makes it undefined to do pointer
+ * arithmetic on "objects" outside their boundaries and compilers assume
+ * this is the case. In particular they assume such arithmetic does not wrap.
+ */
 #ifndef RELOC_HIDE
 # define RELOC_HIDE(ptr, off)					\
   ({ unsigned long __ptr;					\

---

## [16] David Laight — 2026-01-20
*Subject: Re: [PATCH v1 01/14] x86/realmode: remove I/O port
 paravirtualization*

On Tue, 20 Jan 2026 11:53:53 -0800
"H. Peter Anvin" <hpa@zytor.com> wrote:

> In commit:
> 
                                                                  v

	David

> io.h into the compressed/ directory and replace "io.h" with
> <asm/shared/io.h> for the actual real-mode code.

---

## [17] David Laight — 2026-01-20
*Subject: Re: [PATCH v1 02/14] x86/realmode: make %gs == 0 an invariant*

On Tue, 20 Jan 2026 11:53:54 -0800
"H. Peter Anvin" <hpa@zytor.com> wrote:

> When accessing data that is not "near", either only one segment is
> used or one segment is always zero. Leave %gs == 0 at all times
...
> diff --git a/arch/x86/boot/a20.c b/arch/x86/boot/a20.c
> index bda042933a05..3ab6cd8eaa31 100644

Would it be better to wrap that as (say) read_abs_32() since the
objective is to read an absolute address (using the relevant zero segment
register) rather than to read though either fs or gs.

Is this code all running in 32bit linear mode with non-zero cs/ss/ds
segment registers and 'suitable' entries in the GDT?
That mode makes my brain hurt :-)
Or is there a fudge to get 16bit asm from the C.

	David

---

## [18] H. Peter Anvin — 2026-01-20
*Subject: Re: [PATCH v1 02/14] x86/realmode: make %gs == 0 an invariant*

On 2026-01-20 14:40, David Laight wrote:
> 
> Would it be better to wrap that as (say) read_abs_32() since the

The code is running in 16-bit real mode, compiled using -m16.

	-hpa

---

## [19] H. Peter Anvin — 2026-01-20
*Subject: Re: [PATCH v1 02/14] x86/realmode: make %gs == 0 an invariant*

On 2026-01-20 14:40, David Laight wrote:
> 
> Would it be better to wrap that as (say) read_abs_32() since the

To address your specific question, no I don't think that is a good idea, since
it would imply that you can reach an arbitrary linear address, which is
definitely not the case.

At least this way the user has to look at what they are doing, which I think
is a good thing for this specific code.

	-hpa

---

## [20] Uros Bizjak — 2026-01-21
*Subject: Re: [PATCH v1 11/14] x86/boot: use __seg_fs and __seg_gs in the
 real-mode boot code*

On Tue, Jan 20, 2026 at 8:54 PM H. Peter Anvin <hpa@zytor.com> wrote:
>
> All supported versions of gcc support __seg_fs and __seg_gs now.

This particular issue is not due to the compiler not knowing about
fs/gs overlap (if the compiler determines that write and read are to
the same non-volatile address, it would simply remove both, load and
store), but due to the compiler performing load hoisting and store
sinking from the loop. The compiler considers these two addresses as
two different addresses (they are also defined in two different named
address spaces), and optimizes access to them. So, without barrier(),
it simply loads the value from A20_TEST_ADDR and A20_TEST_ADDR+0x10
before the loop, resulting in:

  9:   65 8b 0d 00 02 00 00    mov    %gs:0x200,%ecx
 ...
 16:   64 8b 35 10 02 00 00    mov    %fs:0x210,%esi
 ...
 28:   83 ea 01                sub    $0x1,%edx
 2b:   74 0a                   je     37 <a20_test_ref+0x37>
 2d:   e6 80                   out    %al,$0x80
 2f:   89 d9                   mov    %ebx,%ecx
 31:   29 d1                   sub    %edx,%ecx
 33:   39 ce                   cmp    %ecx,%esi
 35:   74 f1                   je     28 <a20_test_ref+0x28>

The solution with barrier() introduces memory clobber between store
and load, so the compiler is now forced to load and store the values
due to the side effects of the barrier() inbetween. This kind of
works, but is just a workaround for what really happens. In reality,
the value at the test address changes "behind the compiler back", IOW
- variable’s value can change in ways the compiler cannot predict.

My proposal is to use a volatile pointer to an absolute address, so
the unwanted optimizations are suppressed. The generated code is the
same as with barrier(), but now the code tells the compiler that every
read and write to this address must happen exactly as written in the
source code. Before your patch, the accessors were defined with
volatile asm, and this is the place where volatile qualifier matters.
So, my proposed code would read:

#define A20_TEST_ADDR    (4*0x80)

#define A20_TEST_GS (*(volatile __seg_gs u32 *)A20_TEST_ADDR)
#define A20_TEST_FS (*(volatile __seg_fs u32 *)(A20_TEST_ADDR+0x10))

static int a20_test(int loops)
{
    int saved, ctr;

    set_fs(0xffff);

    saved = ctr = A20_TEST_GS;

    do {
        A20_TEST_GS = ++ctr;
        io_delay();    /* Make constant delay */
        if (A20_TEST_FS != ctr)
            break;
    } while (--loops);

    A20_TEST_GS = saved;
    return loops;
}

BR,
Uros.

---

## [21] Uros Bizjak — 2026-01-21
*Subject: Re: [PATCH v1 11/14] x86/boot: use __seg_fs and __seg_gs in the
 real-mode boot code*

On Wed, Jan 21, 2026 at 9:56 AM Uros Bizjak <ubizjak@gmail.com> wrote:
>
> On Tue, Jan 20, 2026 at 8:54 PM H. Peter Anvin <hpa@zytor.com> wrote:

Now also in the form of the attached patch vs. yout git hpa/boot2
branch, tested with gcc-15.2.1 and clang-21.1.8.

BR,
Uros.

diff --git a/arch/x86/boot/a20.c b/arch/x86/boot/a20.c
index 38a1cad8a553..ff51b0ce4dfd 100644
--- a/arch/x86/boot/a20.c
+++ b/arch/x86/boot/a20.c
@@ -48,8 +48,9 @@ static int empty_8042(void)
    used as a test is the int $0x80 vector, which should be safe. */
 
 #define A20_TEST_ADDR	(4*0x80)
-#define A20_TEST_SHORT  32
-#define A20_TEST_LONG	2097152	/* 2^21 */
+
+#define A20_TEST_GS (*(volatile __seg_gs u32 *)A20_TEST_ADDR)
+#define A20_TEST_FS (*(volatile __seg_fs u32 *)(A20_TEST_ADDR+0x10))
 
 static int a20_test(int loops)
 {
@@ -57,20 +58,22 @@ static int a20_test(int loops)
 
 	set_fs(0xffff);
 
-	saved = ctr = rdgs32(A20_TEST_ADDR);
+	saved = ctr = A20_TEST_GS;
 
 	do {
-		wrgs32(++ctr, A20_TEST_ADDR);
-		io_delay();	/* Serialize and make delay constant */
-		barrier();	/* Compiler won't know about fs/gs overlap */
-		if (rdfs32(A20_TEST_ADDR+0x10) != ctr)
+		A20_TEST_GS = ++ctr;
+		io_delay();	/* Make constant delay */
+		if (A20_TEST_FS != ctr)
 			break;
 	} while (--loops);
 
-	wrgs32(saved, A20_TEST_ADDR);
+	A20_TEST_GS = saved;
 	return loops;
 }
 
+#define A20_TEST_SHORT  32
+#define A20_TEST_LONG	2097152	/* 2^21 */
+
 /* Quick test to see if A20 is already enabled */
 static int a20_test_short(void)
 {

---

## [22] Uros Bizjak — 2026-01-21
*Subject: Re: [PATCH v1 02/14] x86/realmode: make %gs == 0 an invariant*

On Tue, Jan 20, 2026 at 8:54 PM H. Peter Anvin <hpa@zytor.com> wrote:
>
> When accessing data that is not "near", either only one segment is

Reviewed-by: Uros Bizjak <ubizjak@gmail.com>

> ---
>  arch/x86/boot/a20.c               | 11 +++++------

---

## [23] Uros Bizjak — 2026-01-21
*Subject: Re: [PATCH v1 03/14] x86/boot: use <linux/compiler.h>*

On Tue, Jan 20, 2026 at 8:54 PM H. Peter Anvin <hpa@zytor.com> wrote:
>
> Include <linux/compiler.h> in arch/x86/boot/boot.h and replace

Reviewed-by: Uros Bizjak <ubizjak@gmail.com>

> ---
>  arch/x86/boot/boot.h | 8 ++++----

---

## [24] Uros Bizjak — 2026-01-21
*Subject: Re: [PATCH v1 05/14] x86/boot: call puts() from within die()*

On Tue, Jan 20, 2026 at 8:54 PM H. Peter Anvin <hpa@zytor.com> wrote:
>
> Every call to die() has a call to puts() in front of it, which adds

Reviewed-by: Uros Bizjak <ubizjak@gmail.com>

> ---
>  arch/x86/boot/boot.h   | 2 +-

---

## [25] Uros Bizjak — 2026-01-21
*Subject: Re: [PATCH v1 07/14] x86/boot: factor out the 16-bit startup code
 from header.S*

On Tue, Jan 20, 2026 at 8:54 PM H. Peter Anvin <hpa@zytor.com> wrote:
>
> Move the 16-bit startup code to its own assembly file, instead of

Reviewed-by: Uros Bizjak <ubizjak@gmail.com>

> ---
>  arch/x86/boot/Makefile  |   4 +-

---

## [26] Uros Bizjak — 2026-01-21
*Subject: Re: [PATCH v1 12/14] x86/boot: tweak a20.c for better code generation*

On Tue, Jan 20, 2026 at 8:54 PM H. Peter Anvin <hpa@zytor.com> wrote:
>
> Do some minor tweaks to arch/x86/boot/a20.c for better code

Acked-by: Uros Bizjak <ubizjak@gmail.com>

> ---
>  arch/x86/boot/a20.c  | 24 +++++++++++-------------

---

## [27] Uros Bizjak — 2026-01-21
*Subject: Re: [PATCH v1 13/14] x86/boot: simplify x86/boot/cmdline.c by using __seg_fs*

On Tue, Jan 20, 2026 at 8:54 PM H. Peter Anvin <hpa@zytor.com> wrote:
>
> arch/x86/boot/cmdline.c is compiled in 16, 32, or 64-bit mode. In the

Acked-by: Uros Bizjak <ubizjak@gmail.com>

> ---
>  arch/x86/boot/boot.h               | 23 +--------

---

## [28] Uros Bizjak — 2026-01-21
*Subject: Re: [PATCH v1 00/14] x86 boot code cleanups, batch 1*

On Tue, Jan 20, 2026 at 8:54 PM H. Peter Anvin <hpa@zytor.com> wrote:

> This patchset also includes the removal of the gcc-specific version of
> the RELOC_HIDE() macro, by Uros Bizjak, as the other changes in this

Not that this issue is holding back GCC *development*, the historic
kludge unnecessarily suppresses optimizations that could be applied by
the compiler to produce better code.

Thanks,
Uros.

---

## [29] David Laight — 2026-01-21
*Subject: Re: [PATCH v1 12/14] x86/boot: tweak a20.c for better code
 generation*

On Tue, 20 Jan 2026 11:54:04 -0800
"H. Peter Anvin" <hpa@zytor.com> wrote:

> Do some minor tweaks to arch/x86/boot/a20.c for better code
> generation, made possible by the __seg_fs/__seg_gs changes.

Can't this code just do:
	sv = *0000:addr;
	val = *ffff:addr+10;
	if (sv != val)
		return 1;
	*0000:addr = ~val;
	io_delay();
	val ^= *ffff:addr+10;
	*0000:addr = sv;
	return val != ~0;

That inverts all bits, inverting one is enough.
No loops needed.

	David

> 
> Signed-off-by: H. Peter Anvin (Intel) <hpa@zytor.com>

---

## [30] Kiryl Shutsemau — 2026-01-21
*Subject: Re: [PATCH v1 01/14] x86/realmode: remove I/O port paravirtualization*

On Tue, Jan 20, 2026 at 11:53:53AM -0800, H. Peter Anvin wrote:
> In commit:
> 

Acked-by: Kiryl Shutsemau <kas@kernel.org>

---

## [31] H. Peter Anvin — 2026-01-21
*Subject: Re: [PATCH v1 11/14] x86/boot: use __seg_fs and __seg_gs in the real-mode boot code*

On January 21, 2026 12:56:39 AM PST, Uros Bizjak <ubizjak@gmail.com> wrote:
>On Tue, Jan 20, 2026 at 8:54 PM H. Peter Anvin <hpa@zytor.com> wrote:
>>

I disagree with that being the preferred solution, and it isn't really the Linux style.

Not only does it require making more changes to the macros, but the barrier() construct is well established in Linux as the way to indicate that a memory variable is subject to examination and/or modification by another system agent, while still being a memory variable. 

It also generally produces better code. 

So no, your analysis is, in my opinion, incorrect in light of the way the Linux memory model is already used.

---

## [32] Uros Bizjak — 2026-01-21
*Subject: Re: [PATCH v1 11/14] x86/boot: use __seg_fs and __seg_gs in the
 real-mode boot code*

On Wed, Jan 21, 2026 at 4:14 PM H. Peter Anvin <hpa@zytor.com> wrote:

> >My proposal is to use a volatile pointer to an absolute address, so
> >the unwanted optimizations are suppressed. The generated code is the

Thanks for explaining to me the Linux way! If this is the case, I will
withdraw my proposed solution.

Best regards,
Uros.

---

## [33] Uros Bizjak — 2026-01-21
*Subject: Re: [PATCH v1 11/14] x86/boot: use __seg_fs and __seg_gs in the
 real-mode boot code*

On Tue, Jan 20, 2026 at 8:54 PM H. Peter Anvin <hpa@zytor.com> wrote:
>
> All supported versions of gcc support __seg_fs and __seg_gs now.

Reviewed-by: Uros Bizjak <ubizjak@gmail.com>

> ---
>  arch/x86/boot/a20.c  |  1 +

---

## [34] Simon Glass — 2026-01-23
*Subject: re: [PATCH v1 08/14] x86: make CONFIG_EFI_STUB unconditional*

Hi Peter,

On Tue, Jan 20, 2026 at 8:54 PM H. Peter Anvin <hpa@zytor.com> wrote:
>
> The EFI stub code is mature, most current x86 systems require EFI to

At least with QEMU the EFI protocol adds quite a lot of overhead.

Is there any actual need for this?

Regards,
Simon

---

## [35] H. Peter Anvin — 2026-01-22
*Subject: re: [PATCH v1 08/14] x86: make CONFIG_EFI_STUB unconditional*

On January 22, 2026 10:57:39 AM PST, Simon Glass <sjg@chromium.org> wrote:
>Hi Peter,
>

Including the EFI stub doesn't mean using EFI to boot is required.

---

## [36] Maciej W. Rozycki — 2026-01-24
*Subject: Re: [PATCH v1 12/14] x86/boot: tweak a20.c for better code
 generation*

On Wed, 21 Jan 2026, David Laight wrote:

> No loops needed.

 A loop is needed because there can be a considerable delay from issuing 
the I/O request to flip the A20 gate till the circuitry responding.  This 
is particularly true with the command issued to the 8042 device, which is 
a microcontroller running its own firmware that needs it time to process 
an incoming request to drive one of the microcontroller's GPIOs.  There 
was a reason for port 0x92 circuitry later added to the PC architecture 
with the IBM PS/2 being called the "fast A20 gate".

  Maciej

---

## [37] H. Peter Anvin — 2026-01-23
*Subject: Re: [PATCH v1 12/14] x86/boot: tweak a20.c for better code generation*

On 2026-01-23 19:00, Maciej W. Rozycki wrote:
> On Wed, 21 Jan 2026, David Laight wrote:
> 

Indeed. I thought I had responded to this already but I hadn't, apparently.

Note that the "long" delay is 2^21 loops! That number wasn't taken out of the
air, either; we found machines that actually needed that many iterations.

In the case where A20 is enabled already, the loop terminates on either the
first or second iteration (the second iteration is when the value at 0x1000200
is exactly 1 higher than the value at 0x200.

Modern machines (Nehalem+) already have A20 enabled, and most machines of the
i686+ generation implement int 0x15 function 0x2401.

	-hpa

---

## [38] David Laight — 2026-01-24
*Subject: Re: [PATCH v1 12/14] x86/boot: tweak a20.c for better code
 generation*

On Fri, 23 Jan 2026 20:24:55 -0800
"H. Peter Anvin" <hpa@zytor.com> wrote:

> On 2026-01-23 19:00, Maciej W. Rozycki wrote:
> > On Wed, 21 Jan 2026, David Laight wrote:

Ok, so you need a loop because it might take ages for the value read from
0x1000200 to change.
But there is no need to keep changing the value.
The comments in the code don't really stress that.

> In the case where A20 is enabled already, the loop terminates on either the
> first or second iteration (the second iteration is when the value at 0x1000200

I know some of the history.
And just read some more of the gory details...

A20 being disabled is there to make a 286 compatible with the older 8086 PCs
and any software that relied on address wrapping (rather than using it to get
an extra ~64kB in real mode).
That would be for dos and win 3.11...

The only 8088 and 286 cpu I used were on IO cards.

> 
> 	-hpa

---

## [39] H. Peter Anvin — 2026-01-24
*Subject: Re: [PATCH v1 12/14] x86/boot: tweak a20.c for better code generation*

On January 24, 2026 3:07:41 PM PST, David Laight <david.laight.linux@gmail.com> wrote:
>On Fri, 23 Jan 2026 20:24:55 -0800
>"H. Peter Anvin" <hpa@zytor.com> wrote:

No, there is a reason to keep changing the value: you have no idea what is currently stored in that memory, *and you have no way of knowing*.

Whatever value you write might purely accidentally be the value that already is stored at that memory location.

---

## [40] H. Peter Anvin — 2026-01-24
*Subject: Re: [PATCH v1 12/14] x86/boot: tweak a20.c for better code generation*

On January 24, 2026 3:16:18 PM PST, "H. Peter Anvin" <hpa@zytor.com> wrote:
>On January 24, 2026 3:07:41 PM PST, David Laight <david.laight.linux@gmail.com> wrote:
>>On Fri, 23 Jan 2026 20:24:55 -0800
The other thing about this code is that performance is irrelevant – it is a busy wait loop! – but consistency (hence the io_delay) and code size matter.

---

## [41] Simon Glass — 2026-01-27
*Subject: Re: [PATCH v1 08/14] x86: make CONFIG_EFI_STUB unconditional*

Hi Peter,

On Fri, 23 Jan 2026 at 13:11, H. Peter Anvin <hpa@zytor.com> wrote:
>
> On January 22, 2026 10:57:39 AM PST, Simon Glass <sjg@chromium.org> wrote:

Yes, understood, but it adds bloat. More importantly it will lead to
people assuming that the stub is always used and thus unwittingly blur
the boundary between the stub and the kernel itself.

What is the actual need for this?

Regards,
Simon

---

## [42] H. Peter Anvin — 2026-01-26
*Subject: Re: [PATCH v1 08/14] x86: make CONFIG_EFI_STUB unconditional*

On 2026-01-26 13:19, Simon Glass wrote:
>>
>> Including the EFI stub doesn't mean using EFI to boot is required.

I would argue that the opposite is more likely: someone inadvertently builds a
kernel without the stub, the bootloader goes down a legacy support path and
things seems to work... except for some platform subtleties.

The bloat is there, but it is small and is only in the on-disk kernel image;
it is zero at runtime.

As such, I don't think this option is a particularly good idea anymore. If
necessary, it could be hidden behind an EXPERT option, but I first wanted to
see who if anyone actually cares in a meaningful way to maintain this option.
Every option, after all, adds maintenance burden.

Note that the BIOS stub is unconditionally compiled and included, and that has
not been an issue.

	-hpa

---

## [43] Simon Glass — 2026-01-27
*Subject: Re: [PATCH v1 08/14] x86: make CONFIG_EFI_STUB unconditional*

Hi Peter,

On Tue, 27 Jan 2026 at 11:21, H. Peter Anvin <hpa@zytor.com> wrote:
>
> On 2026-01-26 13:19, Simon Glass wrote:

What is the maintenance burden here? I could potentially take that on,
but I would first want to understand what is involved.

The use of the word 'legacy' worries me too. Is this patch a step
towards removing the non-EFI path?

Regards,
Simon

---

## [44] H. Peter Anvin — 2026-01-26
*Subject: Re: [PATCH v1 08/14] x86: make CONFIG_EFI_STUB unconditional*

On January 26, 2026 5:44:43 PM PST, Simon Glass <sjg@chromium.org> wrote:
>Hi Peter,
>

Bypassing the firmware stub (BIOS or EFI) is really only appropriate for special user cases, like kexec, because it removes the ability for the kernel to deal with system issues at an early point.

However, kexec needs it, and it's not going to go away. However, that doesn't mean we should encourage this in cases which doesn't need it (no matter what the Grub maintainers tell you.)

Now, if you are using KVM without EFI you are probably doing BIOS boot (regardless of if you know it or not), entering via the BIOS firmware stub.

---

## [45] H. Peter Anvin — 2026-01-26
*Subject: Re: [PATCH v1 08/14] x86: make CONFIG_EFI_STUB unconditional*

On January 26, 2026 5:44:43 PM PST, Simon Glass <sjg@chromium.org> wrote:
>Hi Peter,
>

I just realized you are the U-boot maintainer, so I'm assuming you are thinking of the case where there is no UEFI or BIOS firmware. In that case, just like as for kexec, the current entry point will continue to work, of course. 

What we don't want is having to suffer being on a BIOS or EFI system but not being able to leverage it for the benefit of the kernel. The kernel image is much easier to upgrade.

---

## [46] Simon Glass — 2026-01-27
*Subject: Re: [PATCH v1 08/14] x86: make CONFIG_EFI_STUB unconditional*

Hi Peter,

On Tue, 27 Jan 2026 at 15:55, H. Peter Anvin <hpa@zytor.com> wrote:
>
> On January 26, 2026 5:44:43 PM PST, Simon Glass <sjg@chromium.org> wrote:

(joining the threads)

> Bypassing the firmware stub (BIOS or EFI) is really only appropriate for special user cases, like kexec, because it removes the ability for the kernel to deal with system issues at an early point.

Does this dealing happen in the EFI stub, or later? Are you referring
to ACPI fix-ups or something else?

>
> However, kexec needs it, and it's not going to go away. However, that doesn't mean we should encourage this in cases which doesn't need it (no matter what the Grub maintainers tell you.)

I am thinking of the 64-bit entry point to the kernel. everything
being laid out in memory ready to go.

>
> I just realized you are the U-boot maintainer, so I'm assuming you are thinking of the case where there is no UEFI or BIOS firmware. In that case, just like as for kexec, the current entry point will continue to work, of course.

More generally I am thinking about a simple and clean API for the
kernel that doesn't involve having to provide 30K lines of firmware
code just to boot. The BIOS entry point (if that is what it is called)
is quite close to this ideal, even though I know it has shortcomings.

Regards,
Simon

---

## [47] H. Peter Anvin — 2026-01-26
*Subject: Re: [PATCH v1 08/14] x86: make CONFIG_EFI_STUB unconditional*

On January 26, 2026 7:14:27 PM PST, Simon Glass <sjg@chromium.org> wrote:
>Hi Peter,
>

Yes, I understand. 

The 32/64-bit entrypoints aren't going away; it would be impossible to do so. 

The general rule is: do things as late in the boot process as possible, but no later.

---

## [48] Borislav Petkov — 2026-01-28
*Subject: Re: [PATCH v1 01/14] x86/realmode: remove I/O port paravirtualization*

On Tue, Jan 20, 2026 at 11:53:53AM -0800, H. Peter Anvin wrote:
> In commit:
> 

We do this format for referencing commits:

  eb4ea1ae8f45 ("x86/boot: Port I/O: Allow to hook up alternative helpers")

> ... paravirtualization hooks were added to (some!) of the port I/O
> functions. However, they were only ever used in the 32/64-bit

s/mode/move/

Otherwise, LGTM.

---

## [49] Simon Glass — 2026-01-30
*Subject: Re: [PATCH v1 08/14] x86: make CONFIG_EFI_STUB unconditional*

Hi Peter,

On Tue, 27 Jan 2026 at 16:22, H. Peter Anvin <hpa@zytor.com> wrote:
>
> On January 26, 2026 7:14:27 PM PST, Simon Glass <sjg@chromium.org> wrote:

OK, so 'depend on EXPORT' seems good to me.

> The general rule is: do things as late in the boot process as possible, but no later.
>

Just on this point, I wonder how we should define 'late', in the
context of EFI. For example, if the kernel stub reads a file, meaning
it calls back into Tianocore, it is using both early and late code.

Regards,
Simon

---

## [50] H. Peter Anvin — 2026-01-29
*Subject: Re: [PATCH v1 08/14] x86: make CONFIG_EFI_STUB unconditional*

On January 29, 2026 2:13:13 PM PST, Simon Glass <sjg@chromium.org> wrote:
>Hi Peter,
>

"Early" in this context is before ExitBootServices().

---
