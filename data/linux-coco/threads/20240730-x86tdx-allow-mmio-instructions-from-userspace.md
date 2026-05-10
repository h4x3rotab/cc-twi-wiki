---
title: 'x86/tdx: Allow MMIO instructions from userspace'
date: 2024-07-30
last_reply: 2024-09-13
message_count: 109
participants: ['Alexey Gladkov (Intel)', 'Thomas Gleixner', 'Kirill A. Shutemov', 'Edgecombe, Rick P', 'Reshetova, Elena', 'Tom Lendacky', 'kernel test robot', 'Dave Hansen', 'Sean Christopherson']
---

## [1] Alexey Gladkov (Intel) — 2024-07-30

Currently, MMIO inside the TDX guest is allowed from kernel space and access
from userspace is denied. This becomes a problem when working with virtual
devices in userspace.

In TDX guest MMIO instructions are emulated in #VE. The kernel code uses special
helpers to access MMIO memory to limit the number of instructions which are
used.

This patchset makes MMIO accessible from userspace. To do this additional checks
were added to ensure that the emulated instruction will not be compromised.


Alexey Gladkov (Intel) (4):
  x86/tdx: Split MMIO read and write operations
  x86/tdx: Add validation of userspace MMIO instructions
  x86/tdx: Allow MMIO from userspace
  x86/tdx: Implement movs for MMIO

 arch/x86/coco/sev/core.c  | 133 ++---------------
 arch/x86/coco/tdx/tdx.c   | 295 +++++++++++++++++++++++++++++++-------
 arch/x86/include/asm/io.h |   3 +
 arch/x86/lib/iomem.c      | 132 +++++++++++++++++
 4 files changed, 390 insertions(+), 173 deletions(-)

---

## [2] Alexey Gladkov (Intel) — 2024-07-30
*Subject: [PATCH v1 1/4] x86/tdx: Split MMIO read and write operations*

To implement MMIO in userspace, additional memory checks need to be
implemented. To avoid overly complicating the handle_mmio() function
and to separate checks from actions, it will be split into two separate
functions for handling read and write operations.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 135 ++++++++++++++++++++++++----------------
 1 file changed, 82 insertions(+), 53 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 078e2bac2553..41b047a08071 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -405,14 +405,90 @@ static bool mmio_write(int size, unsigned long addr, unsigned long val)
 			       EPT_WRITE, addr, val);
 }
 
+static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
+		struct pt_regs *regs, struct ve_info *ve)
+{
+	unsigned long *reg, val;
+
+	switch (mmio) {
+	case INSN_MMIO_WRITE:
+		reg = insn_get_modrm_reg_ptr(insn, regs);
+		if (!reg)
+			return -EINVAL;
+		memcpy(&val, reg, size);
+		if (!mmio_write(size, ve->gpa, val))
+			return -EIO;
+		return insn->length;
+	case INSN_MMIO_WRITE_IMM:
+		val = insn->immediate.value;
+		if (!mmio_write(size, ve->gpa, val))
+			return -EIO;
+		return insn->length;
+	case INSN_MMIO_MOVS:
+		/*
+		 * MMIO was accessed with an instruction that could not be
+		 * decoded or handled properly. It was likely not using io.h
+		 * helpers or accessed MMIO accidentally.
+		 */
+		return -EINVAL;
+	default:
+		WARN_ON_ONCE(1);
+		return -EINVAL;
+	}
+
+	return insn->length;
+}
+
+static int handle_mmio_read(struct insn *insn, enum insn_mmio_type mmio, int size,
+		struct pt_regs *regs, struct ve_info *ve)
+{
+	unsigned long *reg, val;
+	int extend_size;
+	u8 extend_val = 0;
+
+	reg = insn_get_modrm_reg_ptr(insn, regs);
+	if (!reg)
+		return -EINVAL;
+
+	/* Handle reads */
+	if (!mmio_read(size, ve->gpa, &val))
+		return -EIO;
+
+	switch (mmio) {
+	case INSN_MMIO_READ:
+		/* Zero-extend for 32-bit operation */
+		extend_size = size == 4 ? sizeof(*reg) : 0;
+		break;
+	case INSN_MMIO_READ_ZERO_EXTEND:
+		/* Zero extend based on operand size */
+		extend_size = insn->opnd_bytes;
+		break;
+	case INSN_MMIO_READ_SIGN_EXTEND:
+		/* Sign extend based on operand size */
+		extend_size = insn->opnd_bytes;
+		if (size == 1 && val & BIT(7))
+			extend_val = 0xFF;
+		else if (size > 1 && val & BIT(15))
+			extend_val = 0xFF;
+		break;
+	default:
+		WARN_ON_ONCE(1);
+		return -EINVAL;
+	}
+
+	if (extend_size)
+		memset(reg, extend_val, extend_size);
+	memcpy(reg, &val, size);
+	return insn->length;
+}
+
 static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 {
-	unsigned long *reg, val, vaddr;
+	unsigned long vaddr;
 	char buffer[MAX_INSN_SIZE];
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
-	int size, extend_size;
-	u8 extend_val = 0;
+	int size;
 
 	/* Only in-kernel MMIO is supported */
 	if (WARN_ON_ONCE(user_mode(regs)))
@@ -428,12 +504,6 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
-	if (mmio != INSN_MMIO_WRITE_IMM && mmio != INSN_MMIO_MOVS) {
-		reg = insn_get_modrm_reg_ptr(&insn, regs);
-		if (!reg)
-			return -EINVAL;
-	}
-
 	/*
 	 * Reject EPT violation #VEs that split pages.
 	 *
@@ -447,24 +517,15 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (vaddr / PAGE_SIZE != (vaddr + size - 1) / PAGE_SIZE)
 		return -EFAULT;
 
-	/* Handle writes first */
 	switch (mmio) {
 	case INSN_MMIO_WRITE:
-		memcpy(&val, reg, size);
-		if (!mmio_write(size, ve->gpa, val))
-			return -EIO;
-		return insn.length;
 	case INSN_MMIO_WRITE_IMM:
-		val = insn.immediate.value;
-		if (!mmio_write(size, ve->gpa, val))
-			return -EIO;
-		return insn.length;
+	case INSN_MMIO_MOVS:
+		return handle_mmio_write(&insn, mmio, size, regs, ve);
 	case INSN_MMIO_READ:
 	case INSN_MMIO_READ_ZERO_EXTEND:
 	case INSN_MMIO_READ_SIGN_EXTEND:
-		/* Reads are handled below */
-		break;
-	case INSN_MMIO_MOVS:
+		return handle_mmio_read(&insn, mmio, size, regs, ve);
 	case INSN_MMIO_DECODE_FAILED:
 		/*
 		 * MMIO was accessed with an instruction that could not be
@@ -476,38 +537,6 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 		WARN_ONCE(1, "Unknown insn_decode_mmio() decode value?");
 		return -EINVAL;
 	}
-
-	/* Handle reads */
-	if (!mmio_read(size, ve->gpa, &val))
-		return -EIO;
-
-	switch (mmio) {
-	case INSN_MMIO_READ:
-		/* Zero-extend for 32-bit operation */
-		extend_size = size == 4 ? sizeof(*reg) : 0;
-		break;
-	case INSN_MMIO_READ_ZERO_EXTEND:
-		/* Zero extend based on operand size */
-		extend_size = insn.opnd_bytes;
-		break;
-	case INSN_MMIO_READ_SIGN_EXTEND:
-		/* Sign extend based on operand size */
-		extend_size = insn.opnd_bytes;
-		if (size == 1 && val & BIT(7))
-			extend_val = 0xFF;
-		else if (size > 1 && val & BIT(15))
-			extend_val = 0xFF;
-		break;
-	default:
-		/* All other cases has to be covered with the first switch() */
-		WARN_ON_ONCE(1);
-		return -EINVAL;
-	}
-
-	if (extend_size)
-		memset(reg, extend_val, extend_size);
-	memcpy(reg, &val, size);
-	return insn.length;
 }
 
 static bool handle_in(struct pt_regs *regs, int size, int port)

---

## [3] Alexey Gladkov (Intel) — 2024-07-30
*Subject: [PATCH v1 2/4] x86/tdx: Add validation of userspace MMIO instructions*

Instructions from kernel space are considered trusted. If the MMIO
instruction is from userspace it must be checked.

For userspace instructions, it is need to check that the INSN has not
changed at the time of #VE and before the execution of the instruction.

Once the userspace instruction parsed is enforced that the address
points to mapped memory of current process and that address does not
point to private memory.

After parsing the userspace instruction, it is necessary to ensure that:

1. the operation direction (read/write) corresponds to #VE info;
2. the address still points to mapped memory of current process;
3. the address does not point to private memory.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 118 +++++++++++++++++++++++++++++++++++-----
 1 file changed, 105 insertions(+), 13 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 41b047a08071..8c894ee9c245 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -8,6 +8,7 @@
 #include <linux/export.h>
 #include <linux/io.h>
 #include <linux/kexec.h>
+#include <linux/mm.h>
 #include <asm/coco.h>
 #include <asm/tdx.h>
 #include <asm/vmx.h>
@@ -405,6 +406,74 @@ static bool mmio_write(int size, unsigned long addr, unsigned long val)
 			       EPT_WRITE, addr, val);
 }
 
+static inline bool is_private_gpa(u64 gpa)
+{
+	return gpa == cc_mkenc(gpa);
+}
+
+static int get_phys_addr(unsigned long addr, phys_addr_t *phys_addr, bool *writable)
+{
+	unsigned int level;
+	pgd_t *pgdp;
+	pte_t *ptep;
+
+	/*
+	 * Address validation only makes sense for a user process. The lock must
+	 * be obtained before validation can begin.
+	 */
+	mmap_assert_locked(current->mm);
+
+	pgdp = pgd_offset(current->mm, addr);
+
+	if (!pgd_none(*pgdp)) {
+		ptep = lookup_address_in_pgd(pgdp, addr, &level);
+		if (ptep) {
+			unsigned long offset;
+
+			offset = addr & ~page_level_mask(level);
+			*phys_addr = PFN_PHYS(pte_pfn(*ptep));
+			*phys_addr |= offset;
+
+			*writable = pte_write(*ptep);
+
+			return 0;
+		}
+	}
+
+	return -EFAULT;
+}
+
+static int valid_vaddr(struct ve_info *ve, enum insn_mmio_type mmio, int size,
+			unsigned long vaddr)
+{
+	phys_addr_t phys_addr;
+	bool writable = false;
+
+	/* It's not fatal. This can happen due to swap out or page migration. */
+	if (get_phys_addr(vaddr, &phys_addr, &writable) || (ve->gpa != cc_mkdec(phys_addr)))
+		return -EAGAIN;
+
+	/* Check whether #VE info matches the instruction that was decoded. */
+	switch (mmio) {
+	case INSN_MMIO_WRITE:
+	case INSN_MMIO_WRITE_IMM:
+		if (!writable || !(ve->exit_qual & EPT_VIOLATION_ACC_WRITE))
+			return -EFAULT;
+		break;
+	case INSN_MMIO_READ:
+	case INSN_MMIO_READ_ZERO_EXTEND:
+	case INSN_MMIO_READ_SIGN_EXTEND:
+		if (!(ve->exit_qual & EPT_VIOLATION_ACC_READ))
+			return -EFAULT;
+		break;
+	default:
+		WARN_ONCE(1, "Unsupported mmio instruction: %d", mmio);
+		return -EINVAL;
+	}
+
+	return 0;
+}
+
 static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
 		struct pt_regs *regs, struct ve_info *ve)
 {
@@ -488,7 +557,7 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	char buffer[MAX_INSN_SIZE];
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
-	int size;
+	int size, ret;
 
 	/* Only in-kernel MMIO is supported */
 	if (WARN_ON_ONCE(user_mode(regs)))
@@ -504,6 +573,17 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
+	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
+
+	if (user_mode(regs)) {
+		if (mmap_read_lock_killable(current->mm))
+			return -EINTR;
+
+		ret = valid_vaddr(ve, mmio, size, vaddr);
+		if (ret)
+			goto fault;
+	}
+
 	/*
 	 * Reject EPT violation #VEs that split pages.
 	 *
@@ -513,30 +593,39 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	 *
 	 * load_unaligned_zeropad() will recover using exception fixups.
 	 */
-	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
-	if (vaddr / PAGE_SIZE != (vaddr + size - 1) / PAGE_SIZE)
-		return -EFAULT;
+	if (vaddr / PAGE_SIZE != (vaddr + size - 1) / PAGE_SIZE) {
+		ret = -EFAULT;
+		goto fault;
+	}
 
 	switch (mmio) {
 	case INSN_MMIO_WRITE:
 	case INSN_MMIO_WRITE_IMM:
 	case INSN_MMIO_MOVS:
-		return handle_mmio_write(&insn, mmio, size, regs, ve);
+		ret = handle_mmio_write(&insn, mmio, size, regs, ve);
+		break;
 	case INSN_MMIO_READ:
 	case INSN_MMIO_READ_ZERO_EXTEND:
 	case INSN_MMIO_READ_SIGN_EXTEND:
-		return handle_mmio_read(&insn, mmio, size, regs, ve);
+		ret = handle_mmio_read(&insn, mmio, size, regs, ve);
+		break;
 	case INSN_MMIO_DECODE_FAILED:
 		/*
 		 * MMIO was accessed with an instruction that could not be
 		 * decoded or handled properly. It was likely not using io.h
 		 * helpers or accessed MMIO accidentally.
 		 */
-		return -EINVAL;
+		ret = -EINVAL;
+		break;
 	default:
 		WARN_ONCE(1, "Unknown insn_decode_mmio() decode value?");
-		return -EINVAL;
+		ret = -EINVAL;
 	}
+fault:
+	if (user_mode(regs))
+		mmap_read_unlock(current->mm);
+
+	return ret;
 }
 
 static bool handle_in(struct pt_regs *regs, int size, int port)
@@ -680,11 +769,6 @@ static int virt_exception_user(struct pt_regs *regs, struct ve_info *ve)
 	}
 }
 
-static inline bool is_private_gpa(u64 gpa)
-{
-	return gpa == cc_mkenc(gpa);
-}
-
 /*
  * Handle the kernel #VE.
  *
@@ -722,6 +806,14 @@ bool tdx_handle_virt_exception(struct pt_regs *regs, struct ve_info *ve)
 		insn_len = virt_exception_user(regs, ve);
 	else
 		insn_len = virt_exception_kernel(regs, ve);
+
+	/*
+	 * A special case to return to userspace without increasing regs->ip
+	 * to repeat the instruction once again.
+	 */
+	if (insn_len == -EAGAIN)
+		return true;
+
 	if (insn_len < 0)
 		return false;

---

## [4] Alexey Gladkov (Intel) — 2024-07-30
*Subject: [PATCH v1 3/4] x86/tdx: Allow MMIO from userspace*

The MMIO emulation is only allowed for kernel space code. It is carried
out through a special API, which uses only certain instructions.

This does not allow userspace to work with virtual devices.

Allow userspace to use the same instructions as kernel space to access
MMIO. So far, no additional checks have been made.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 42 +++++++++++++++++++++++++++++++----------
 1 file changed, 32 insertions(+), 10 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 8c894ee9c245..26b2e52457be 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -474,6 +474,31 @@ static int valid_vaddr(struct ve_info *ve, enum insn_mmio_type mmio, int size,
 	return 0;
 }
 
+static int decode_insn_struct(struct insn *insn, struct pt_regs *regs)
+{
+	char buffer[MAX_INSN_SIZE];
+
+	if (user_mode(regs)) {
+		int nr_copied = insn_fetch_from_user(regs, buffer);
+
+		if (nr_copied <= 0)
+			return -EFAULT;
+
+		if (!insn_decode_from_regs(insn, regs, buffer, nr_copied))
+			return -EINVAL;
+
+		if (!insn->immediate.got)
+			return -EINVAL;
+	} else {
+		if (copy_from_kernel_nofault(buffer, (void *)regs->ip, MAX_INSN_SIZE))
+			return -EFAULT;
+
+		if (insn_decode(insn, buffer, MAX_INSN_SIZE, INSN_MODE_64))
+			return -EINVAL;
+	}
+	return 0;
+}
+
 static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
 		struct pt_regs *regs, struct ve_info *ve)
 {
@@ -554,20 +579,13 @@ static int handle_mmio_read(struct insn *insn, enum insn_mmio_type mmio, int siz
 static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 {
 	unsigned long vaddr;
-	char buffer[MAX_INSN_SIZE];
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
 	int size, ret;
 
-	/* Only in-kernel MMIO is supported */
-	if (WARN_ON_ONCE(user_mode(regs)))
-		return -EFAULT;
-
-	if (copy_from_kernel_nofault(buffer, (void *)regs->ip, MAX_INSN_SIZE))
-		return -EFAULT;
-
-	if (insn_decode(&insn, buffer, MAX_INSN_SIZE, INSN_MODE_64))
-		return -EINVAL;
+	ret = decode_insn_struct(&insn, regs);
+	if (ret)
+		return ret;
 
 	mmio = insn_decode_mmio(&insn, &size);
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
@@ -763,6 +781,10 @@ static int virt_exception_user(struct pt_regs *regs, struct ve_info *ve)
 	switch (ve->exit_reason) {
 	case EXIT_REASON_CPUID:
 		return handle_cpuid(regs, ve);
+	case EXIT_REASON_EPT_VIOLATION:
+		if (is_private_gpa(ve->gpa))
+			panic("Unexpected EPT-violation on private memory.");
+		return handle_mmio(regs, ve);
 	default:
 		pr_warn("Unexpected #VE: %lld\n", ve->exit_reason);
 		return -EIO;

---

## [5] Alexey Gladkov (Intel) — 2024-07-30
*Subject: [PATCH v1 4/4] x86/tdx: Implement movs for MMIO*

Adapt AMD's implementation of the MOVS instruction. Since the
implementations are similar, it is possible to reuse the code.

MOVS emulation consists of dividing it into a series of read and write
operations, which in turn will be validated separately.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---


I don't really understand the reasoning behind AMD's approach of returning to
userspace after every read/write operation in vc_handle_mmio_movs(). I didn't
change this so as not to break their implementation.

But if this can be changed then the whole vc_handle_mmio_movs() could be used as
a common helper.


 arch/x86/coco/sev/core.c  | 133 ++++----------------------------------
 arch/x86/coco/tdx/tdx.c   |  56 ++++++++++++++--
 arch/x86/include/asm/io.h |   3 +
 arch/x86/lib/iomem.c      | 132 +++++++++++++++++++++++++++++++++++++
 4 files changed, 199 insertions(+), 125 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 082d61d85dfc..3135c89802e9 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -369,72 +369,17 @@ static enum es_result vc_decode_insn(struct es_em_ctxt *ctxt)
 static enum es_result vc_write_mem(struct es_em_ctxt *ctxt,
 				   char *dst, char *buf, size_t size)
 {
-	unsigned long error_code = X86_PF_PROT | X86_PF_WRITE;
+	unsigned long error_code;
+	int ret = __put_iomem(dst, buf, size);
 
-	/*
-	 * This function uses __put_user() independent of whether kernel or user
-	 * memory is accessed. This works fine because __put_user() does no
-	 * sanity checks of the pointer being accessed. All that it does is
-	 * to report when the access failed.
-	 *
-	 * Also, this function runs in atomic context, so __put_user() is not
-	 * allowed to sleep. The page-fault handler detects that it is running
-	 * in atomic context and will not try to take mmap_sem and handle the
-	 * fault, so additional pagefault_enable()/disable() calls are not
-	 * needed.
-	 *
-	 * The access can't be done via copy_to_user() here because
-	 * vc_write_mem() must not use string instructions to access unsafe
-	 * memory. The reason is that MOVS is emulated by the #VC handler by
-	 * splitting the move up into a read and a write and taking a nested #VC
-	 * exception on whatever of them is the MMIO access. Using string
-	 * instructions here would cause infinite nesting.
-	 */
-	switch (size) {
-	case 1: {
-		u8 d1;
-		u8 __user *target = (u8 __user *)dst;
-
-		memcpy(&d1, buf, 1);
-		if (__put_user(d1, target))
-			goto fault;
-		break;
-	}
-	case 2: {
-		u16 d2;
-		u16 __user *target = (u16 __user *)dst;
-
-		memcpy(&d2, buf, 2);
-		if (__put_user(d2, target))
-			goto fault;
-		break;
-	}
-	case 4: {
-		u32 d4;
-		u32 __user *target = (u32 __user *)dst;
-
-		memcpy(&d4, buf, 4);
-		if (__put_user(d4, target))
-			goto fault;
-		break;
-	}
-	case 8: {
-		u64 d8;
-		u64 __user *target = (u64 __user *)dst;
+	if (!ret)
+		return ES_OK;
 
-		memcpy(&d8, buf, 8);
-		if (__put_user(d8, target))
-			goto fault;
-		break;
-	}
-	default:
-		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+	if (ret == -EIO)
 		return ES_UNSUPPORTED;
-	}
 
-	return ES_OK;
+	error_code = X86_PF_PROT | X86_PF_WRITE;
 
-fault:
 	if (user_mode(ctxt->regs))
 		error_code |= X86_PF_USER;
 
@@ -448,71 +393,17 @@ static enum es_result vc_write_mem(struct es_em_ctxt *ctxt,
 static enum es_result vc_read_mem(struct es_em_ctxt *ctxt,
 				  char *src, char *buf, size_t size)
 {
-	unsigned long error_code = X86_PF_PROT;
+	unsigned long error_code;
+	int ret = __get_iomem(src, buf, size);
 
-	/*
-	 * This function uses __get_user() independent of whether kernel or user
-	 * memory is accessed. This works fine because __get_user() does no
-	 * sanity checks of the pointer being accessed. All that it does is
-	 * to report when the access failed.
-	 *
-	 * Also, this function runs in atomic context, so __get_user() is not
-	 * allowed to sleep. The page-fault handler detects that it is running
-	 * in atomic context and will not try to take mmap_sem and handle the
-	 * fault, so additional pagefault_enable()/disable() calls are not
-	 * needed.
-	 *
-	 * The access can't be done via copy_from_user() here because
-	 * vc_read_mem() must not use string instructions to access unsafe
-	 * memory. The reason is that MOVS is emulated by the #VC handler by
-	 * splitting the move up into a read and a write and taking a nested #VC
-	 * exception on whatever of them is the MMIO access. Using string
-	 * instructions here would cause infinite nesting.
-	 */
-	switch (size) {
-	case 1: {
-		u8 d1;
-		u8 __user *s = (u8 __user *)src;
-
-		if (__get_user(d1, s))
-			goto fault;
-		memcpy(buf, &d1, 1);
-		break;
-	}
-	case 2: {
-		u16 d2;
-		u16 __user *s = (u16 __user *)src;
-
-		if (__get_user(d2, s))
-			goto fault;
-		memcpy(buf, &d2, 2);
-		break;
-	}
-	case 4: {
-		u32 d4;
-		u32 __user *s = (u32 __user *)src;
+	if (!ret)
+		return ES_OK;
 
-		if (__get_user(d4, s))
-			goto fault;
-		memcpy(buf, &d4, 4);
-		break;
-	}
-	case 8: {
-		u64 d8;
-		u64 __user *s = (u64 __user *)src;
-		if (__get_user(d8, s))
-			goto fault;
-		memcpy(buf, &d8, 8);
-		break;
-	}
-	default:
-		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+	if (ret == -EIO)
 		return ES_UNSUPPORTED;
-	}
 
-	return ES_OK;
+	error_code = X86_PF_PROT;
 
-fault:
 	if (user_mode(ctxt->regs))
 		error_code |= X86_PF_USER;
 
diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 26b2e52457be..cf209381d63b 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -499,6 +499,53 @@ static int decode_insn_struct(struct insn *insn, struct pt_regs *regs)
 	return 0;
 }
 
+static int handle_mmio_movs(struct insn *insn, struct pt_regs *regs, int size, struct ve_info *ve)
+{
+	unsigned long ds_base, es_base;
+	unsigned char *src, *dst;
+	unsigned char buffer[8];
+	int off, ret;
+	bool rep;
+
+	/*
+	 * The in-kernel code must use a special API that does not use MOVS.
+	 * If the MOVS instruction is received from in-kernel, then something
+	 * is broken.
+	 */
+	WARN_ON_ONCE(!user_mode(regs));
+
+	ds_base = insn_get_seg_base(regs, INAT_SEG_REG_DS);
+	es_base = insn_get_seg_base(regs, INAT_SEG_REG_ES);
+
+	if (ds_base == -1L || es_base == -1L)
+		return -EINVAL;
+
+	rep = insn_has_rep_prefix(insn);
+
+	do {
+		src = ds_base + (unsigned char *) regs->si;
+		dst = es_base + (unsigned char *) regs->di;
+
+		ret = __get_iomem(src, buffer, size);
+		if (ret)
+			return ret;
+
+		ret = __put_iomem(dst, buffer, size);
+		if (ret)
+			return ret;
+
+		off = (regs->flags & X86_EFLAGS_DF) ? -size : size;
+
+		regs->si += off;
+		regs->di += off;
+
+		if (rep)
+			regs->cx -= 1;
+	} while (rep || regs->cx > 0);
+
+	return insn->length;
+}
+
 static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
 		struct pt_regs *regs, struct ve_info *ve)
 {
@@ -520,9 +567,8 @@ static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int si
 		return insn->length;
 	case INSN_MMIO_MOVS:
 		/*
-		 * MMIO was accessed with an instruction that could not be
-		 * decoded or handled properly. It was likely not using io.h
-		 * helpers or accessed MMIO accidentally.
+		 * MOVS is processed through higher level emulation which breaks
+		 * this instruction into a sequence of reads and writes.
 		 */
 		return -EINVAL;
 	default:
@@ -591,6 +637,9 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
+	if (mmio == INSN_MMIO_MOVS)
+		return handle_mmio_movs(&insn, regs, size, ve);
+
 	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
 
 	if (user_mode(regs)) {
@@ -619,7 +668,6 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	switch (mmio) {
 	case INSN_MMIO_WRITE:
 	case INSN_MMIO_WRITE_IMM:
-	case INSN_MMIO_MOVS:
 		ret = handle_mmio_write(&insn, mmio, size, regs, ve);
 		break;
 	case INSN_MMIO_READ:
diff --git a/arch/x86/include/asm/io.h b/arch/x86/include/asm/io.h
index 1d60427379c9..ac01d53466cb 100644
--- a/arch/x86/include/asm/io.h
+++ b/arch/x86/include/asm/io.h
@@ -402,4 +402,7 @@ static inline void iosubmit_cmds512(void __iomem *dst, const void *src,
 	}
 }
 
+int __get_iomem(char *src, char *buf, size_t size);
+int __put_iomem(char *src, char *buf, size_t size);
+
 #endif /* _ASM_X86_IO_H */
diff --git a/arch/x86/lib/iomem.c b/arch/x86/lib/iomem.c
index 5eecb45d05d5..e4919ad22206 100644
--- a/arch/x86/lib/iomem.c
+++ b/arch/x86/lib/iomem.c
@@ -2,6 +2,7 @@
 #include <linux/module.h>
 #include <linux/io.h>
 #include <linux/kmsan-checks.h>
+#include <asm/uaccess.h>
 
 #define movs(type,to,from) \
 	asm volatile("movs" type:"=&D" (to), "=&S" (from):"0" (to), "1" (from):"memory")
@@ -124,3 +125,134 @@ void memset_io(volatile void __iomem *a, int b, size_t c)
 	}
 }
 EXPORT_SYMBOL(memset_io);
+
+int __get_iomem(char *src, char *buf, size_t size)
+{
+	/*
+	 * This function uses __get_user() independent of whether kernel or user
+	 * memory is accessed. This works fine because __get_user() does no
+	 * sanity checks of the pointer being accessed. All that it does is
+	 * to report when the access failed.
+	 *
+	 * Also, this function runs in atomic context, so __get_user() is not
+	 * allowed to sleep. The page-fault handler detects that it is running
+	 * in atomic context and will not try to take mmap_sem and handle the
+	 * fault, so additional pagefault_enable()/disable() calls are not
+	 * needed.
+	 *
+	 * The access can't be done via copy_from_user() here because
+	 * mmio_read_mem() must not use string instructions to access unsafe
+	 * memory. The reason is that MOVS is emulated by the #VC handler by
+	 * splitting the move up into a read and a write and taking a nested #VC
+	 * exception on whatever of them is the MMIO access. Using string
+	 * instructions here would cause infinite nesting.
+	 */
+	switch (size) {
+	case 1: {
+		u8 d1;
+		u8 __user *s = (u8 __user *)src;
+
+		if (__get_user(d1, s))
+			return -EFAULT;
+		memcpy(buf, &d1, 1);
+		break;
+	}
+	case 2: {
+		u16 d2;
+		u16 __user *s = (u16 __user *)src;
+
+		if (__get_user(d2, s))
+			return -EFAULT;
+		memcpy(buf, &d2, 2);
+		break;
+	}
+	case 4: {
+		u32 d4;
+		u32 __user *s = (u32 __user *)src;
+
+		if (__get_user(d4, s))
+			return -EFAULT;
+		memcpy(buf, &d4, 4);
+		break;
+	}
+	case 8: {
+		u64 d8;
+		u64 __user *s = (u64 __user *)src;
+		if (__get_user(d8, s))
+			return -EFAULT;
+		memcpy(buf, &d8, 8);
+		break;
+	}
+	default:
+		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+		return -EIO;
+	}
+
+	return 0;
+}
+
+int __put_iomem(char *dst, char *buf, size_t size)
+{
+	/*
+	 * This function uses __put_user() independent of whether kernel or user
+	 * memory is accessed. This works fine because __put_user() does no
+	 * sanity checks of the pointer being accessed. All that it does is
+	 * to report when the access failed.
+	 *
+	 * Also, this function runs in atomic context, so __put_user() is not
+	 * allowed to sleep. The page-fault handler detects that it is running
+	 * in atomic context and will not try to take mmap_sem and handle the
+	 * fault, so additional pagefault_enable()/disable() calls are not
+	 * needed.
+	 *
+	 * The access can't be done via copy_to_user() here because
+	 * put_iomem() must not use string instructions to access unsafe
+	 * memory. The reason is that MOVS is emulated by the #VC handler by
+	 * splitting the move up into a read and a write and taking a nested #VC
+	 * exception on whatever of them is the MMIO access. Using string
+	 * instructions here would cause infinite nesting.
+	 */
+	switch (size) {
+	case 1: {
+		u8 d1;
+		u8 __user *target = (u8 __user *)dst;
+
+		memcpy(&d1, buf, 1);
+		if (__put_user(d1, target))
+			return -EFAULT;
+		break;
+	}
+	case 2: {
+		u16 d2;
+		u16 __user *target = (u16 __user *)dst;
+
+		memcpy(&d2, buf, 2);
+		if (__put_user(d2, target))
+			return -EFAULT;
+		break;
+	}
+	case 4: {
+		u32 d4;
+		u32 __user *target = (u32 __user *)dst;
+
+		memcpy(&d4, buf, 4);
+		if (__put_user(d4, target))
+			return -EFAULT;
+		break;
+	}
+	case 8: {
+		u64 d8;
+		u64 __user *target = (u64 __user *)dst;
+
+		memcpy(&d8, buf, 8);
+		if (__put_user(d8, target))
+			return -EFAULT;
+		break;
+	}
+	default:
+		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+		return -EIO;
+	}
+
+	return 0;
+}

---

## [6] Thomas Gleixner — 2024-07-30
*Subject: Re: [PATCH v1 1/4] x86/tdx: Split MMIO read and write operations*

On Tue, Jul 30 2024 at 19:35, Alexey Gladkov wrote:
> To implement MMIO in userspace, additional memory checks need to be
> implemented. To avoid overly complicating the handle_mmio() function

It will be split? The patch splits it, no?
>  
> +static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,

Please align the second line argument with the first argument in the
first line.

> +static int handle_mmio_read(struct insn *insn, enum insn_mmio_type mmio, int size,
> +		struct pt_regs *regs, struct ve_info *ve)

https://www.kernel.org/doc/html/latest/process/maintainer-tip.html#variable-declarations

>  static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
>  {

Ditto
  
>  	/* Only in-kernel MMIO is supported */
>  	if (WARN_ON_ONCE(user_mode(regs)))

Thanks,

        tglx

---

## [7] Thomas Gleixner — 2024-07-30
*Subject: Re: [PATCH v1 2/4] x86/tdx: Add validation of userspace MMIO
 instructions*

On Tue, Jul 30 2024 at 19:35, Alexey Gladkov wrote:
>  
> +	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);

fault is really the wrong name for the label because it's the general
return point of the function. 'out' or 'unlock' perhaps?

Thanks,

        tglx

---

## [8] Thomas Gleixner — 2024-07-30
*Subject: Re: [PATCH v1 3/4] x86/tdx: Allow MMIO from userspace*

On Tue, Jul 30 2024 at 19:35, Alexey Gladkov wrote:
> The MMIO emulation is only allowed for kernel space code. It is carried
> out through a special API, which uses only certain instructions.

Reviewed-by: Thomas Gleixner <tglx@linutronix.de>

---

## [9] Thomas Gleixner — 2024-07-30
*Subject: Re: [PATCH v1 4/4] x86/tdx: Implement movs for MMIO*

On Tue, Jul 30 2024 at 19:35, Alexey Gladkov wrote:
> Adapt AMD's implementation of the MOVS instruction. Since the
> implementations are similar, it is possible to reuse the code.

Please split this into two patches:

    1) Splitting out the AMD code
    2) Adding it for Intel
> @@ -369,72 +369,17 @@ static enum es_result vc_decode_insn(struct es_em_ctxt *ctxt)
>  static enum es_result vc_write_mem(struct es_em_ctxt *ctxt,

Variable ordering....
  
> +static int handle_mmio_movs(struct insn *insn, struct pt_regs *regs, int size, struct ve_info *ve)
> +{

Then it should return here and not try to continue, no?

> +int __get_iomem(char *src, char *buf, size_t size)
> +{

One line for the variables is enough

		u8 d1, __user *s = (u8 __user *)src;

No?

> +	case 8: {
> +		u64 d8;

Lacks newline between variable declaration and code.

Thanks,

        tglx

---

## [10] Kirill A. Shutemov — 2024-08-02
*Subject: Re: [PATCH v1 2/4] x86/tdx: Add validation of userspace MMIO
 instructions*

On Tue, Jul 30, 2024 at 07:35:57PM +0200, Alexey Gladkov (Intel) wrote:
> +static int valid_vaddr(struct ve_info *ve, enum insn_mmio_type mmio, int size,
> +			unsigned long vaddr)

I think we need big fat comment here why these checks are needed.

We have ve->gpa and it was valid at the time we got ve_info. But after we
get ve_info, we enable interrupts allowing tlb shootdown and therefore
munmap() in parallel thread of the process.

So by the time we've got here ve->gpa might be unmapped from the process,
the device it belongs to removed from system and something else could be
plugged in its place.

That's why we need to re-check if the GPA is still mapped and writable if
we are going to write to it.

> +
> +	/* Check whether #VE info matches the instruction that was decoded. */

---

## [11] Alexey Gladkov — 2024-08-05
*Subject: Re: [PATCH v1 1/4] x86/tdx: Split MMIO read and write operations*

On Tue, Jul 30, 2024 at 08:31:15PM +0200, Thomas Gleixner wrote:
> On Tue, Jul 30 2024 at 19:35, Alexey Gladkov wrote:
> > To implement MMIO in userspace, additional memory checks need to be

Yes. Sorry for my english. I will reword it.

> >  
> > +static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,

Ok. I will fix the coding style here and in other patches.

> >  static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
> >  {

---

## [12] Alexey Gladkov — 2024-08-05
*Subject: Re: [PATCH v1 2/4] x86/tdx: Add validation of userspace MMIO
 instructions*

On Fri, Aug 02, 2024 at 10:41:17AM +0300, Kirill A. Shutemov wrote:
> On Tue, Jul 30, 2024 at 07:35:57PM +0200, Alexey Gladkov (Intel) wrote:
> > +static int valid_vaddr(struct ve_info *ve, enum insn_mmio_type mmio, int size,

Make sense. I will add bigger comment here.

> > +
> > +	/* Check whether #VE info matches the instruction that was decoded. */

---

## [13] Alexey Gladkov — 2024-08-05
*Subject: Re: [PATCH v1 4/4] x86/tdx: Implement movs for MMIO*

On Tue, Jul 30, 2024 at 08:41:00PM +0200, Thomas Gleixner wrote:
> On Tue, Jul 30 2024 at 19:35, Alexey Gladkov wrote:
> > Adapt AMD's implementation of the MOVS instruction. Since the

Ok. Make sense.

> > @@ -369,72 +369,17 @@ static enum es_result vc_decode_insn(struct es_em_ctxt *ctxt)
> >  static enum es_result vc_write_mem(struct es_em_ctxt *ctxt,

Oops. I miss it. Thanks!

> > +int __get_iomem(char *src, char *buf, size_t size)
> > +{

Yes.

> > +	case 8: {
> > +		u64 d8;

---

## [14] Alexey Gladkov (Intel) — 2024-08-05
*Subject: [PATCH v2 0/5] x86/tdx: Allow MMIO instructions from userspace*

Currently, MMIO inside the TDX guest is allowed from kernel space and access
from userspace is denied. This becomes a problem when working with virtual
devices in userspace.

In TDX guest MMIO instructions are emulated in #VE. The kernel code uses special
helpers to access MMIO memory to limit the number of instructions which are
used.

This patchset makes MMIO accessible from userspace. To do this additional checks
were added to ensure that the emulated instruction will not be compromised.


v2:
- Split into separate patches AMD helpers extraction and MOVS implementation
  code for intel as suggested by Thomas Gleixner.
- Fix coding style issues.


Alexey Gladkov (Intel) (5):
  x86/tdx: Split MMIO read and write operations
  x86/tdx: Add validation of userspace MMIO instructions
  x86/tdx: Allow MMIO from userspace
  x86/tdx: Move MMIO helpers to common library
  x86/tdx: Implement movs for MMIO

 arch/x86/coco/sev/core.c  | 135 ++---------------
 arch/x86/coco/tdx/tdx.c   | 309 +++++++++++++++++++++++++++++++-------
 arch/x86/include/asm/io.h |   3 +
 arch/x86/lib/iomem.c      | 125 +++++++++++++++
 4 files changed, 398 insertions(+), 174 deletions(-)

---

## [15] Alexey Gladkov (Intel) — 2024-08-05
*Subject: [PATCH v2 1/5] x86/tdx: Split MMIO read and write operations*

To implement MMIO in userspace, additional memory checks need to be
implemented. To avoid overly complicating the handle_mmio() function
and to separate checks from actions, it would be better to split this
function into two separate functions to handle read and write
operations.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 136 ++++++++++++++++++++++++----------------
 1 file changed, 83 insertions(+), 53 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 078e2bac2553..af0b6c1cacf7 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -405,14 +405,91 @@ static bool mmio_write(int size, unsigned long addr, unsigned long val)
 			       EPT_WRITE, addr, val);
 }
 
+static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
+			     struct pt_regs *regs, struct ve_info *ve)
+{
+	unsigned long *reg, val;
+
+	switch (mmio) {
+	case INSN_MMIO_WRITE:
+		reg = insn_get_modrm_reg_ptr(insn, regs);
+		if (!reg)
+			return -EINVAL;
+		memcpy(&val, reg, size);
+		if (!mmio_write(size, ve->gpa, val))
+			return -EIO;
+		return insn->length;
+	case INSN_MMIO_WRITE_IMM:
+		val = insn->immediate.value;
+		if (!mmio_write(size, ve->gpa, val))
+			return -EIO;
+		return insn->length;
+	case INSN_MMIO_MOVS:
+		/*
+		 * MMIO was accessed with an instruction that could not be
+		 * decoded or handled properly. It was likely not using io.h
+		 * helpers or accessed MMIO accidentally.
+		 */
+		return -EINVAL;
+	default:
+		WARN_ON_ONCE(1);
+		return -EINVAL;
+	}
+
+	return insn->length;
+}
+
+static int handle_mmio_read(struct insn *insn, enum insn_mmio_type mmio, int size,
+			    struct pt_regs *regs, struct ve_info *ve)
+{
+	unsigned long *reg, val;
+	int extend_size;
+	u8 extend_val;
+
+	reg = insn_get_modrm_reg_ptr(insn, regs);
+	if (!reg)
+		return -EINVAL;
+
+	if (!mmio_read(size, ve->gpa, &val))
+		return -EIO;
+
+	extend_val = 0;
+
+	switch (mmio) {
+	case INSN_MMIO_READ:
+		/* Zero-extend for 32-bit operation */
+		extend_size = size == 4 ? sizeof(*reg) : 0;
+		break;
+	case INSN_MMIO_READ_ZERO_EXTEND:
+		/* Zero extend based on operand size */
+		extend_size = insn->opnd_bytes;
+		break;
+	case INSN_MMIO_READ_SIGN_EXTEND:
+		/* Sign extend based on operand size */
+		extend_size = insn->opnd_bytes;
+		if (size == 1 && val & BIT(7))
+			extend_val = 0xFF;
+		else if (size > 1 && val & BIT(15))
+			extend_val = 0xFF;
+		break;
+	default:
+		WARN_ON_ONCE(1);
+		return -EINVAL;
+	}
+
+	if (extend_size)
+		memset(reg, extend_val, extend_size);
+	memcpy(reg, &val, size);
+	return insn->length;
+}
+
 static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 {
-	unsigned long *reg, val, vaddr;
 	char buffer[MAX_INSN_SIZE];
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
-	int size, extend_size;
-	u8 extend_val = 0;
+	unsigned long vaddr;
+	int size;
 
 	/* Only in-kernel MMIO is supported */
 	if (WARN_ON_ONCE(user_mode(regs)))
@@ -428,12 +505,6 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
-	if (mmio != INSN_MMIO_WRITE_IMM && mmio != INSN_MMIO_MOVS) {
-		reg = insn_get_modrm_reg_ptr(&insn, regs);
-		if (!reg)
-			return -EINVAL;
-	}
-
 	/*
 	 * Reject EPT violation #VEs that split pages.
 	 *
@@ -447,24 +518,15 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (vaddr / PAGE_SIZE != (vaddr + size - 1) / PAGE_SIZE)
 		return -EFAULT;
 
-	/* Handle writes first */
 	switch (mmio) {
 	case INSN_MMIO_WRITE:
-		memcpy(&val, reg, size);
-		if (!mmio_write(size, ve->gpa, val))
-			return -EIO;
-		return insn.length;
 	case INSN_MMIO_WRITE_IMM:
-		val = insn.immediate.value;
-		if (!mmio_write(size, ve->gpa, val))
-			return -EIO;
-		return insn.length;
+	case INSN_MMIO_MOVS:
+		return handle_mmio_write(&insn, mmio, size, regs, ve);
 	case INSN_MMIO_READ:
 	case INSN_MMIO_READ_ZERO_EXTEND:
 	case INSN_MMIO_READ_SIGN_EXTEND:
-		/* Reads are handled below */
-		break;
-	case INSN_MMIO_MOVS:
+		return handle_mmio_read(&insn, mmio, size, regs, ve);
 	case INSN_MMIO_DECODE_FAILED:
 		/*
 		 * MMIO was accessed with an instruction that could not be
@@ -476,38 +538,6 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 		WARN_ONCE(1, "Unknown insn_decode_mmio() decode value?");
 		return -EINVAL;
 	}
-
-	/* Handle reads */
-	if (!mmio_read(size, ve->gpa, &val))
-		return -EIO;
-
-	switch (mmio) {
-	case INSN_MMIO_READ:
-		/* Zero-extend for 32-bit operation */
-		extend_size = size == 4 ? sizeof(*reg) : 0;
-		break;
-	case INSN_MMIO_READ_ZERO_EXTEND:
-		/* Zero extend based on operand size */
-		extend_size = insn.opnd_bytes;
-		break;
-	case INSN_MMIO_READ_SIGN_EXTEND:
-		/* Sign extend based on operand size */
-		extend_size = insn.opnd_bytes;
-		if (size == 1 && val & BIT(7))
-			extend_val = 0xFF;
-		else if (size > 1 && val & BIT(15))
-			extend_val = 0xFF;
-		break;
-	default:
-		/* All other cases has to be covered with the first switch() */
-		WARN_ON_ONCE(1);
-		return -EINVAL;
-	}
-
-	if (extend_size)
-		memset(reg, extend_val, extend_size);
-	memcpy(reg, &val, size);
-	return insn.length;
 }
 
 static bool handle_in(struct pt_regs *regs, int size, int port)

---

## [16] Alexey Gladkov (Intel) — 2024-08-05
*Subject: [PATCH v2 2/5] x86/tdx: Add validation of userspace MMIO instructions*

Instructions from kernel space are considered trusted. If the MMIO
instruction is from userspace it must be checked.

For userspace instructions, it is need to check that the INSN has not
changed at the time of #VE and before the execution of the instruction.

Once the userspace instruction parsed is enforced that the address
points to mapped memory of current process and that address does not
point to private memory.

After parsing the userspace instruction, it is necessary to ensure that:

1. the operation direction (read/write) corresponds to #VE info;
2. the address still points to mapped memory of current process;
3. the address does not point to private memory.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 128 ++++++++++++++++++++++++++++++++++++----
 1 file changed, 115 insertions(+), 13 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index af0b6c1cacf7..95f2ff49728c 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -8,6 +8,7 @@
 #include <linux/export.h>
 #include <linux/io.h>
 #include <linux/kexec.h>
+#include <linux/mm.h>
 #include <asm/coco.h>
 #include <asm/tdx.h>
 #include <asm/vmx.h>
@@ -405,6 +406,84 @@ static bool mmio_write(int size, unsigned long addr, unsigned long val)
 			       EPT_WRITE, addr, val);
 }
 
+static inline bool is_private_gpa(u64 gpa)
+{
+	return gpa == cc_mkenc(gpa);
+}
+
+static int get_phys_addr(unsigned long addr, phys_addr_t *phys_addr, bool *writable)
+{
+	unsigned int level;
+	pgd_t *pgdp;
+	pte_t *ptep;
+
+	/*
+	 * Address validation only makes sense for a user process. The lock must
+	 * be obtained before validation can begin.
+	 */
+	mmap_assert_locked(current->mm);
+
+	pgdp = pgd_offset(current->mm, addr);
+
+	if (!pgd_none(*pgdp)) {
+		ptep = lookup_address_in_pgd(pgdp, addr, &level);
+		if (ptep) {
+			unsigned long offset;
+
+			offset = addr & ~page_level_mask(level);
+			*phys_addr = PFN_PHYS(pte_pfn(*ptep));
+			*phys_addr |= offset;
+
+			*writable = pte_write(*ptep);
+
+			return 0;
+		}
+	}
+
+	return -EFAULT;
+}
+
+static int valid_vaddr(struct ve_info *ve, enum insn_mmio_type mmio, int size,
+		       unsigned long vaddr)
+{
+	phys_addr_t phys_addr;
+	bool writable = false;
+
+	/* It's not fatal. This can happen due to swap out or page migration. */
+	if (get_phys_addr(vaddr, &phys_addr, &writable) || (ve->gpa != cc_mkdec(phys_addr)))
+		return -EAGAIN;
+
+	/*
+	 * Re-check whether #VE info matches the instruction that was decoded.
+	 *
+	 * The ve->gpa was valid at the time ve_info was received. But this code
+	 * executed with interrupts enabled, allowing tlb shootdown and therefore
+	 * munmap() to be executed in the parallel thread.
+	 *
+	 * By the time MMIO emulation is performed, ve->gpa may be already
+	 * unmapped from the process, the device it belongs to removed from
+	 * system and something else could be plugged in its place.
+	 */
+	switch (mmio) {
+	case INSN_MMIO_WRITE:
+	case INSN_MMIO_WRITE_IMM:
+		if (!writable || !(ve->exit_qual & EPT_VIOLATION_ACC_WRITE))
+			return -EFAULT;
+		break;
+	case INSN_MMIO_READ:
+	case INSN_MMIO_READ_ZERO_EXTEND:
+	case INSN_MMIO_READ_SIGN_EXTEND:
+		if (!(ve->exit_qual & EPT_VIOLATION_ACC_READ))
+			return -EFAULT;
+		break;
+	default:
+		WARN_ONCE(1, "Unsupported mmio instruction: %d", mmio);
+		return -EINVAL;
+	}
+
+	return 0;
+}
+
 static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
 			     struct pt_regs *regs, struct ve_info *ve)
 {
@@ -489,7 +568,7 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
 	unsigned long vaddr;
-	int size;
+	int size, ret;
 
 	/* Only in-kernel MMIO is supported */
 	if (WARN_ON_ONCE(user_mode(regs)))
@@ -505,6 +584,17 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
+	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
+
+	if (user_mode(regs)) {
+		if (mmap_read_lock_killable(current->mm))
+			return -EINTR;
+
+		ret = valid_vaddr(ve, mmio, size, vaddr);
+		if (ret)
+			goto unlock;
+	}
+
 	/*
 	 * Reject EPT violation #VEs that split pages.
 	 *
@@ -514,30 +604,39 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	 *
 	 * load_unaligned_zeropad() will recover using exception fixups.
 	 */
-	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
-	if (vaddr / PAGE_SIZE != (vaddr + size - 1) / PAGE_SIZE)
-		return -EFAULT;
+	if (vaddr / PAGE_SIZE != (vaddr + size - 1) / PAGE_SIZE) {
+		ret = -EFAULT;
+		goto unlock;
+	}
 
 	switch (mmio) {
 	case INSN_MMIO_WRITE:
 	case INSN_MMIO_WRITE_IMM:
 	case INSN_MMIO_MOVS:
-		return handle_mmio_write(&insn, mmio, size, regs, ve);
+		ret = handle_mmio_write(&insn, mmio, size, regs, ve);
+		break;
 	case INSN_MMIO_READ:
 	case INSN_MMIO_READ_ZERO_EXTEND:
 	case INSN_MMIO_READ_SIGN_EXTEND:
-		return handle_mmio_read(&insn, mmio, size, regs, ve);
+		ret = handle_mmio_read(&insn, mmio, size, regs, ve);
+		break;
 	case INSN_MMIO_DECODE_FAILED:
 		/*
 		 * MMIO was accessed with an instruction that could not be
 		 * decoded or handled properly. It was likely not using io.h
 		 * helpers or accessed MMIO accidentally.
 		 */
-		return -EINVAL;
+		ret = -EINVAL;
+		break;
 	default:
 		WARN_ONCE(1, "Unknown insn_decode_mmio() decode value?");
-		return -EINVAL;
+		ret = -EINVAL;
 	}
+unlock:
+	if (user_mode(regs))
+		mmap_read_unlock(current->mm);
+
+	return ret;
 }
 
 static bool handle_in(struct pt_regs *regs, int size, int port)
@@ -681,11 +780,6 @@ static int virt_exception_user(struct pt_regs *regs, struct ve_info *ve)
 	}
 }
 
-static inline bool is_private_gpa(u64 gpa)
-{
-	return gpa == cc_mkenc(gpa);
-}
-
 /*
  * Handle the kernel #VE.
  *
@@ -723,6 +817,14 @@ bool tdx_handle_virt_exception(struct pt_regs *regs, struct ve_info *ve)
 		insn_len = virt_exception_user(regs, ve);
 	else
 		insn_len = virt_exception_kernel(regs, ve);
+
+	/*
+	 * A special case to return to userspace without increasing regs->ip
+	 * to repeat the instruction once again.
+	 */
+	if (insn_len == -EAGAIN)
+		return true;
+
 	if (insn_len < 0)
 		return false;

---

## [17] Alexey Gladkov (Intel) — 2024-08-05
*Subject: [PATCH v2 3/5] x86/tdx: Allow MMIO from userspace*

The MMIO emulation is only allowed for kernel space code. It is carried
out through a special API, which uses only certain instructions.

This does not allow userspace to work with virtual devices.

Allow userspace to use the same instructions as kernel space to access
MMIO. So far, no additional checks have been made.

Reviewed-by: Thomas Gleixner <tglx@linutronix.de>
Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 42 +++++++++++++++++++++++++++++++----------
 1 file changed, 32 insertions(+), 10 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 95f2ff49728c..4e2fb9bf83a1 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -484,6 +484,31 @@ static int valid_vaddr(struct ve_info *ve, enum insn_mmio_type mmio, int size,
 	return 0;
 }
 
+static int decode_insn_struct(struct insn *insn, struct pt_regs *regs)
+{
+	char buffer[MAX_INSN_SIZE];
+
+	if (user_mode(regs)) {
+		int nr_copied = insn_fetch_from_user(regs, buffer);
+
+		if (nr_copied <= 0)
+			return -EFAULT;
+
+		if (!insn_decode_from_regs(insn, regs, buffer, nr_copied))
+			return -EINVAL;
+
+		if (!insn->immediate.got)
+			return -EINVAL;
+	} else {
+		if (copy_from_kernel_nofault(buffer, (void *)regs->ip, MAX_INSN_SIZE))
+			return -EFAULT;
+
+		if (insn_decode(insn, buffer, MAX_INSN_SIZE, INSN_MODE_64))
+			return -EINVAL;
+	}
+	return 0;
+}
+
 static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
 			     struct pt_regs *regs, struct ve_info *ve)
 {
@@ -564,21 +589,14 @@ static int handle_mmio_read(struct insn *insn, enum insn_mmio_type mmio, int siz
 
 static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 {
-	char buffer[MAX_INSN_SIZE];
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
 	unsigned long vaddr;
 	int size, ret;
 
-	/* Only in-kernel MMIO is supported */
-	if (WARN_ON_ONCE(user_mode(regs)))
-		return -EFAULT;
-
-	if (copy_from_kernel_nofault(buffer, (void *)regs->ip, MAX_INSN_SIZE))
-		return -EFAULT;
-
-	if (insn_decode(&insn, buffer, MAX_INSN_SIZE, INSN_MODE_64))
-		return -EINVAL;
+	ret = decode_insn_struct(&insn, regs);
+	if (ret)
+		return ret;
 
 	mmio = insn_decode_mmio(&insn, &size);
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
@@ -774,6 +792,10 @@ static int virt_exception_user(struct pt_regs *regs, struct ve_info *ve)
 	switch (ve->exit_reason) {
 	case EXIT_REASON_CPUID:
 		return handle_cpuid(regs, ve);
+	case EXIT_REASON_EPT_VIOLATION:
+		if (is_private_gpa(ve->gpa))
+			panic("Unexpected EPT-violation on private memory.");
+		return handle_mmio(regs, ve);
 	default:
 		pr_warn("Unexpected #VE: %lld\n", ve->exit_reason);
 		return -EIO;

---

## [18] Alexey Gladkov (Intel) — 2024-08-05
*Subject: [PATCH v2 4/5] x86/tdx: Move MMIO helpers to common library*

AMD code has helpers that are used to emulate MOVS instructions. To be
able to reuse this code in the MOVS implementation for intel, it is
necessary to move them to a common location.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/sev/core.c  | 135 ++++----------------------------------
 arch/x86/include/asm/io.h |   3 +
 arch/x86/lib/iomem.c      | 125 +++++++++++++++++++++++++++++++++++
 3 files changed, 142 insertions(+), 121 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 082d61d85dfc..0e10c22c5347 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -369,72 +369,18 @@ static enum es_result vc_decode_insn(struct es_em_ctxt *ctxt)
 static enum es_result vc_write_mem(struct es_em_ctxt *ctxt,
 				   char *dst, char *buf, size_t size)
 {
-	unsigned long error_code = X86_PF_PROT | X86_PF_WRITE;
-
-	/*
-	 * This function uses __put_user() independent of whether kernel or user
-	 * memory is accessed. This works fine because __put_user() does no
-	 * sanity checks of the pointer being accessed. All that it does is
-	 * to report when the access failed.
-	 *
-	 * Also, this function runs in atomic context, so __put_user() is not
-	 * allowed to sleep. The page-fault handler detects that it is running
-	 * in atomic context and will not try to take mmap_sem and handle the
-	 * fault, so additional pagefault_enable()/disable() calls are not
-	 * needed.
-	 *
-	 * The access can't be done via copy_to_user() here because
-	 * vc_write_mem() must not use string instructions to access unsafe
-	 * memory. The reason is that MOVS is emulated by the #VC handler by
-	 * splitting the move up into a read and a write and taking a nested #VC
-	 * exception on whatever of them is the MMIO access. Using string
-	 * instructions here would cause infinite nesting.
-	 */
-	switch (size) {
-	case 1: {
-		u8 d1;
-		u8 __user *target = (u8 __user *)dst;
-
-		memcpy(&d1, buf, 1);
-		if (__put_user(d1, target))
-			goto fault;
-		break;
-	}
-	case 2: {
-		u16 d2;
-		u16 __user *target = (u16 __user *)dst;
-
-		memcpy(&d2, buf, 2);
-		if (__put_user(d2, target))
-			goto fault;
-		break;
-	}
-	case 4: {
-		u32 d4;
-		u32 __user *target = (u32 __user *)dst;
+	unsigned long error_code;
+	int ret;
 
-		memcpy(&d4, buf, 4);
-		if (__put_user(d4, target))
-			goto fault;
-		break;
-	}
-	case 8: {
-		u64 d8;
-		u64 __user *target = (u64 __user *)dst;
+	ret = __put_iomem(dst, buf, size);
+	if (!ret)
+		return ES_OK;
 
-		memcpy(&d8, buf, 8);
-		if (__put_user(d8, target))
-			goto fault;
-		break;
-	}
-	default:
-		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+	if (ret == -EIO)
 		return ES_UNSUPPORTED;
-	}
 
-	return ES_OK;
+	error_code = X86_PF_PROT | X86_PF_WRITE;
 
-fault:
 	if (user_mode(ctxt->regs))
 		error_code |= X86_PF_USER;
 
@@ -448,71 +394,18 @@ static enum es_result vc_write_mem(struct es_em_ctxt *ctxt,
 static enum es_result vc_read_mem(struct es_em_ctxt *ctxt,
 				  char *src, char *buf, size_t size)
 {
-	unsigned long error_code = X86_PF_PROT;
-
-	/*
-	 * This function uses __get_user() independent of whether kernel or user
-	 * memory is accessed. This works fine because __get_user() does no
-	 * sanity checks of the pointer being accessed. All that it does is
-	 * to report when the access failed.
-	 *
-	 * Also, this function runs in atomic context, so __get_user() is not
-	 * allowed to sleep. The page-fault handler detects that it is running
-	 * in atomic context and will not try to take mmap_sem and handle the
-	 * fault, so additional pagefault_enable()/disable() calls are not
-	 * needed.
-	 *
-	 * The access can't be done via copy_from_user() here because
-	 * vc_read_mem() must not use string instructions to access unsafe
-	 * memory. The reason is that MOVS is emulated by the #VC handler by
-	 * splitting the move up into a read and a write and taking a nested #VC
-	 * exception on whatever of them is the MMIO access. Using string
-	 * instructions here would cause infinite nesting.
-	 */
-	switch (size) {
-	case 1: {
-		u8 d1;
-		u8 __user *s = (u8 __user *)src;
-
-		if (__get_user(d1, s))
-			goto fault;
-		memcpy(buf, &d1, 1);
-		break;
-	}
-	case 2: {
-		u16 d2;
-		u16 __user *s = (u16 __user *)src;
+	unsigned long error_code;
+	int ret;
 
-		if (__get_user(d2, s))
-			goto fault;
-		memcpy(buf, &d2, 2);
-		break;
-	}
-	case 4: {
-		u32 d4;
-		u32 __user *s = (u32 __user *)src;
+	ret = __get_iomem(src, buf, size);
+	if (!ret)
+		return ES_OK;
 
-		if (__get_user(d4, s))
-			goto fault;
-		memcpy(buf, &d4, 4);
-		break;
-	}
-	case 8: {
-		u64 d8;
-		u64 __user *s = (u64 __user *)src;
-		if (__get_user(d8, s))
-			goto fault;
-		memcpy(buf, &d8, 8);
-		break;
-	}
-	default:
-		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+	if (ret == -EIO)
 		return ES_UNSUPPORTED;
-	}
 
-	return ES_OK;
+	error_code = X86_PF_PROT;
 
-fault:
 	if (user_mode(ctxt->regs))
 		error_code |= X86_PF_USER;
 
diff --git a/arch/x86/include/asm/io.h b/arch/x86/include/asm/io.h
index 1d60427379c9..ac01d53466cb 100644
--- a/arch/x86/include/asm/io.h
+++ b/arch/x86/include/asm/io.h
@@ -402,4 +402,7 @@ static inline void iosubmit_cmds512(void __iomem *dst, const void *src,
 	}
 }
 
+int __get_iomem(char *src, char *buf, size_t size);
+int __put_iomem(char *src, char *buf, size_t size);
+
 #endif /* _ASM_X86_IO_H */
diff --git a/arch/x86/lib/iomem.c b/arch/x86/lib/iomem.c
index 5eecb45d05d5..23179953eb5a 100644
--- a/arch/x86/lib/iomem.c
+++ b/arch/x86/lib/iomem.c
@@ -2,6 +2,7 @@
 #include <linux/module.h>
 #include <linux/io.h>
 #include <linux/kmsan-checks.h>
+#include <asm/uaccess.h>
 
 #define movs(type,to,from) \
 	asm volatile("movs" type:"=&D" (to), "=&S" (from):"0" (to), "1" (from):"memory")
@@ -124,3 +125,127 @@ void memset_io(volatile void __iomem *a, int b, size_t c)
 	}
 }
 EXPORT_SYMBOL(memset_io);
+
+int __get_iomem(char *src, char *buf, size_t size)
+{
+	/*
+	 * This function uses __get_user() independent of whether kernel or user
+	 * memory is accessed. This works fine because __get_user() does no
+	 * sanity checks of the pointer being accessed. All that it does is
+	 * to report when the access failed.
+	 *
+	 * Also, this function runs in atomic context, so __get_user() is not
+	 * allowed to sleep. The page-fault handler detects that it is running
+	 * in atomic context and will not try to take mmap_sem and handle the
+	 * fault, so additional pagefault_enable()/disable() calls are not
+	 * needed.
+	 *
+	 * The access can't be done via copy_from_user() here because
+	 * mmio_read_mem() must not use string instructions to access unsafe
+	 * memory. The reason is that MOVS is emulated by the #VC handler by
+	 * splitting the move up into a read and a write and taking a nested #VC
+	 * exception on whatever of them is the MMIO access. Using string
+	 * instructions here would cause infinite nesting.
+	 */
+	switch (size) {
+	case 1: {
+		u8 d1, __user *s = (u8 __user *)src;
+
+		if (__get_user(d1, s))
+			return -EFAULT;
+		memcpy(buf, &d1, 1);
+		break;
+	}
+	case 2: {
+		u16 d2, __user *s = (u16 __user *)src;
+
+		if (__get_user(d2, s))
+			return -EFAULT;
+		memcpy(buf, &d2, 2);
+		break;
+	}
+	case 4: {
+		u32 d4, __user *s = (u32 __user *)src;
+
+		if (__get_user(d4, s))
+			return -EFAULT;
+		memcpy(buf, &d4, 4);
+		break;
+	}
+	case 8: {
+		u64 d8, __user *s = (u64 __user *)src;
+
+		if (__get_user(d8, s))
+			return -EFAULT;
+		memcpy(buf, &d8, 8);
+		break;
+	}
+	default:
+		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+		return -EIO;
+	}
+
+	return 0;
+}
+
+int __put_iomem(char *dst, char *buf, size_t size)
+{
+	/*
+	 * This function uses __put_user() independent of whether kernel or user
+	 * memory is accessed. This works fine because __put_user() does no
+	 * sanity checks of the pointer being accessed. All that it does is
+	 * to report when the access failed.
+	 *
+	 * Also, this function runs in atomic context, so __put_user() is not
+	 * allowed to sleep. The page-fault handler detects that it is running
+	 * in atomic context and will not try to take mmap_sem and handle the
+	 * fault, so additional pagefault_enable()/disable() calls are not
+	 * needed.
+	 *
+	 * The access can't be done via copy_to_user() here because
+	 * put_iomem() must not use string instructions to access unsafe
+	 * memory. The reason is that MOVS is emulated by the #VC handler by
+	 * splitting the move up into a read and a write and taking a nested #VC
+	 * exception on whatever of them is the MMIO access. Using string
+	 * instructions here would cause infinite nesting.
+	 */
+	switch (size) {
+	case 1: {
+		u8 d1, __user *target = (u8 __user *)dst;
+
+		memcpy(&d1, buf, 1);
+		if (__put_user(d1, target))
+			return -EFAULT;
+		break;
+	}
+	case 2: {
+		u16 d2, __user *target = (u16 __user *)dst;
+
+		memcpy(&d2, buf, 2);
+		if (__put_user(d2, target))
+			return -EFAULT;
+		break;
+	}
+	case 4: {
+		u32 d4, __user *target = (u32 __user *)dst;
+
+		memcpy(&d4, buf, 4);
+		if (__put_user(d4, target))
+			return -EFAULT;
+		break;
+	}
+	case 8: {
+		u64 d8, __user *target = (u64 __user *)dst;
+
+		memcpy(&d8, buf, 8);
+		if (__put_user(d8, target))
+			return -EFAULT;
+		break;
+	}
+	default:
+		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+		return -EIO;
+	}
+
+	return 0;
+}

---

## [19] Alexey Gladkov (Intel) — 2024-08-05
*Subject: [PATCH v2 5/5] x86/tdx: Implement movs for MMIO*

Add emulation of the MOVS instruction on MMIO regions. MOVS emulation
consists of dividing it into a series of read and write operations,
which in turn will be validated separately.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 57 ++++++++++++++++++++++++++++++++++++++---
 1 file changed, 53 insertions(+), 4 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 4e2fb9bf83a1..8573cb23837e 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -509,6 +509,54 @@ static int decode_insn_struct(struct insn *insn, struct pt_regs *regs)
 	return 0;
 }
 
+static int handle_mmio_movs(struct insn *insn, struct pt_regs *regs, int size, struct ve_info *ve)
+{
+	unsigned long ds_base, es_base;
+	unsigned char *src, *dst;
+	unsigned char buffer[8];
+	int off, ret;
+	bool rep;
+
+	/*
+	 * The in-kernel code must use a special API that does not use MOVS.
+	 * If the MOVS instruction is received from in-kernel, then something
+	 * is broken.
+	 */
+	if (WARN_ON_ONCE(!user_mode(regs)))
+		return -EFAULT;
+
+	ds_base = insn_get_seg_base(regs, INAT_SEG_REG_DS);
+	es_base = insn_get_seg_base(regs, INAT_SEG_REG_ES);
+
+	if (ds_base == -1L || es_base == -1L)
+		return -EINVAL;
+
+	rep = insn_has_rep_prefix(insn);
+
+	do {
+		src = ds_base + (unsigned char *) regs->si;
+		dst = es_base + (unsigned char *) regs->di;
+
+		ret = __get_iomem(src, buffer, size);
+		if (ret)
+			return ret;
+
+		ret = __put_iomem(dst, buffer, size);
+		if (ret)
+			return ret;
+
+		off = (regs->flags & X86_EFLAGS_DF) ? -size : size;
+
+		regs->si += off;
+		regs->di += off;
+
+		if (rep)
+			regs->cx -= 1;
+	} while (rep || regs->cx > 0);
+
+	return insn->length;
+}
+
 static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
 			     struct pt_regs *regs, struct ve_info *ve)
 {
@@ -530,9 +578,8 @@ static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int si
 		return insn->length;
 	case INSN_MMIO_MOVS:
 		/*
-		 * MMIO was accessed with an instruction that could not be
-		 * decoded or handled properly. It was likely not using io.h
-		 * helpers or accessed MMIO accidentally.
+		 * MOVS is processed through higher level emulation which breaks
+		 * this instruction into a sequence of reads and writes.
 		 */
 		return -EINVAL;
 	default:
@@ -602,6 +649,9 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
+	if (mmio == INSN_MMIO_MOVS)
+		return handle_mmio_movs(&insn, regs, size, ve);
+
 	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
 
 	if (user_mode(regs)) {
@@ -630,7 +680,6 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	switch (mmio) {
 	case INSN_MMIO_WRITE:
 	case INSN_MMIO_WRITE_IMM:
-	case INSN_MMIO_MOVS:
 		ret = handle_mmio_write(&insn, mmio, size, regs, ve);
 		break;
 	case INSN_MMIO_READ:

---

## [20] Edgecombe, Rick P — 2024-08-05
*Subject: Re: [PATCH v2 2/5] x86/tdx: Add validation of userspace MMIO
 instructions*

On Mon, 2024-08-05 at 15:29 +0200, Alexey Gladkov (Intel) wrote:
> +       vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
> +

In the case of user MMIO, if the user instruction + MAX_INSN_SIZE straddles a
page, then the "fetch" in the kernel could trigger a #VE. In this case the  
kernel would handle this second #VE as a !user_mode() MMIO I guess.

Would something prevent the same munmap() checks needing to happen for that
second kernel #VE? If not, I wonder if the munmap() protection logic should also
trigger for any userspace range ve->gpa as well.

---

## [21] kirill.shutemov@linux.intel.com — 2024-08-06
*Subject: Re: [PATCH v2 2/5] x86/tdx: Add validation of userspace MMIO
 instructions*

On Mon, Aug 05, 2024 at 10:40:55PM +0000, Edgecombe, Rick P wrote:
> On Mon, 2024-08-05 at 15:29 +0200, Alexey Gladkov (Intel) wrote:
> > +�������vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);

That's an interesting scenario, but I think we are fine.

The fetch is copy_from_user() which is "REP; MOVSB" on all TDX platforms.
Kernel rejects MOVS instruction emulation for !user_mode() with -EFAULT.

---

## [22] Alexey Gladkov — 2024-08-06
*Subject: Re: [PATCH v2 2/5] x86/tdx: Add validation of userspace MMIO
 instructions*

On Tue, Aug 06, 2024 at 10:18:20AM +0300, kirill.shutemov@linux.intel.com wrote:
> On Mon, Aug 05, 2024 at 10:40:55PM +0000, Edgecombe, Rick P wrote:
> > On Mon, 2024-08-05 at 15:29 +0200, Alexey Gladkov (Intel) wrote:

But MOVS will be used only if X86_FEATURE_FSRM feature is present.
Otherwise rep_movs_alternative will be used, which uses MOVB.

I know that X86_FEATURE_FSRM appeared since Ice Lake, but still.

---

## [23] Reshetova, Elena — 2024-08-06
*Subject: RE: [PATCH v2 2/5] x86/tdx: Add validation of userspace MMIO
 instructions*

> On Tue, Aug 06, 2024 at 10:18:20AM +0300, kirill.shutemov@linux.intel.com
> wrote:

This is how the X86_FEATURE_FSRM cpuid bit is treated under TDX:

{
          "MSB": "4",
          "LSB": "4",
          "Field Size": "1",
          "Field Name": "Fast Short REP MOV",
          "Configuration Details": "TD_PARAMS.CPUID_CONFIG",
          "Bit or Field Virtualization Type": "Configured & Native",
          "Virtualization Details": null
        },

Which means VMM has the way to overwrite the native platform value
and set it to "0", so we must account for both cases.

---

## [24] Tom Lendacky — 2024-08-08
*Subject: Re: [PATCH v2 5/5] x86/tdx: Implement movs for MMIO*

On 8/5/24 08:29, Alexey Gladkov (Intel) wrote:
> Add emulation of the MOVS instruction on MMIO regions. MOVS emulation
> consists of dividing it into a series of read and write operations,

You check the address in the non-MOVS case using valid_vaddr(), but you
don't seem to be doing that in the MOVS case, was that intentional?

Thanks,
Tom

> +
>  	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);

---

## [25] Alexey Gladkov — 2024-08-08
*Subject: Re: [PATCH v2 5/5] x86/tdx: Implement movs for MMIO*

On Thu, Aug 08, 2024 at 08:48:26AM -0500, Tom Lendacky wrote:
> On 8/5/24 08:29, Alexey Gladkov (Intel) wrote:
> > Add emulation of the MOVS instruction on MMIO regions. MOVS emulation

The MOVS instruction is allowed only in userspace. The MOVS instruction
is emulated through separate read and write operations, which are in turn
checked by valid_vaddr(). 

> Thanks,
> Tom

---

## [26] Alexey Gladkov (Intel) — 2024-08-08
*Subject: [PATCH v3 6/7] x86/tdx: Add a restriction on access to MMIO address*

In the case of userspace MMIO, if the user instruction + MAX_INSN_SIZE
straddles page, then the "fetch" in the kernel could trigger a #VE. In
this case the kernel would handle this second #VE as a !user_mode() MMIO.
That way, additional address verifications can be avoided.

The scenario of accessing userspace MMIO addresses from kernelspace does
not seem appropriate under normal circumstances. Until there is a
specific usecase for such a scenario it can be disabled.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 9 +++++++++
 1 file changed, 9 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index dfadb085d2d3..5b3421a89998 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -411,6 +411,11 @@ static inline bool is_private_gpa(u64 gpa)
 	return gpa == cc_mkenc(gpa);
 }
 
+static inline bool is_kernel_addr(unsigned long addr)
+{
+	return (long)addr < 0;
+}
+
 static int get_phys_addr(unsigned long addr, phys_addr_t *phys_addr, bool *writable)
 {
 	unsigned int level;
@@ -641,6 +646,7 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	unsigned long vaddr;
 	int size, ret;
 
+
 	ret = decode_insn_struct(&insn, regs);
 	if (ret)
 		return ret;
@@ -661,6 +667,9 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 		ret = valid_vaddr(ve, mmio, size, vaddr);
 		if (ret)
 			goto unlock;
+	} else if (!is_kernel_addr(ve->gla)) {
+		WARN_ONCE(1, "Access to userspace address is not supported");
+		return -EINVAL;
 	}
 
 	/*

---

## [27] Alexey Gladkov (Intel) — 2024-08-08
*Subject: [PATCH v3 7/7] x86/tdx: Avoid crossing the page boundary*

In case the instruction is close to the page boundary, reading
MAX_INSN_SIZE may cross the page boundary. The second page might be
from a different VMA and reading can have side effects.

The problem is that the actual size of the instruction is not known.

The solution might be to try read the data to the end of the page and
try parse it in the hope that the instruction is smaller than the
maximum buffer size.

Co-developed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 30 +++++++++++++++++++++++++-----
 1 file changed, 25 insertions(+), 5 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 5b3421a89998..ea3df77feef0 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -494,16 +494,32 @@ static int decode_insn_struct(struct insn *insn, struct pt_regs *regs)
 	char buffer[MAX_INSN_SIZE];
 
 	if (user_mode(regs)) {
-		int nr_copied = insn_fetch_from_user(regs, buffer);
+		int nr_copied, size;
+		unsigned long ip;
 
-		if (nr_copied <= 0)
+		if (insn_get_effective_ip(regs, &ip))
 			return -EFAULT;
 
-		if (!insn_decode_from_regs(insn, regs, buffer, nr_copied))
-			return -EINVAL;
+		/*
+		 * On the first attempt, read up to MAX_INSN_SIZE, but do not cross a
+		 * page boundary. The second page might be from a different VMA and
+		 * reading can have side effects (i.e. reading from MMIO).
+		 */
+		size = min(MAX_INSN_SIZE, PAGE_SIZE - offset_in_page(ip));
+retry:
+		nr_copied = size - copy_from_user(buffer, (void __user *)ip, size);
+
+		if (nr_copied <= 0)
+			return -EFAULT;
 
-		if (!insn->immediate.got)
+		if (!insn_decode_from_regs(insn, regs, buffer, nr_copied)) {
+			/* If decode failed, try to copy across page boundary */
+			if (size < MAX_INSN_SIZE) {
+				size = MAX_INSN_SIZE;
+				goto retry;
+			}
 			return -EINVAL;
+		}
 	} else {
 		if (copy_from_kernel_nofault(buffer, (void *)regs->ip, MAX_INSN_SIZE))
 			return -EFAULT;
@@ -511,6 +527,10 @@ static int decode_insn_struct(struct insn *insn, struct pt_regs *regs)
 		if (insn_decode(insn, buffer, MAX_INSN_SIZE, INSN_MODE_64))
 			return -EINVAL;
 	}
+
+	if (!insn->immediate.got)
+		return -EINVAL;
+
 	return 0;
 }

---

## [28] Alexey Gladkov — 2024-08-08
*Subject: Re: [PATCH v2 2/5] x86/tdx: Add validation of userspace MMIO
 instructions*

On Mon, Aug 05, 2024 at 10:40:55PM +0000, Edgecombe, Rick P wrote:
> On Mon, 2024-08-05 at 15:29 +0200, Alexey Gladkov (Intel) wrote:
> > +�������vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);

I've added two more patches that should fix the problem. We can try to
avoid crossing the page boundary by first reading the data to the end of
the page and trying to parse it and only if that fails read MAX_INSN_SIZE.

I fixed this locally for tdx because it is required to read and parse the
buffer at the same time.

It's generally worth fixing elsewhere as well. But this I propose to do by
a separate patchset.

---

## [29] Alexey Gladkov — 2024-08-08
*Subject: Re: [PATCH v2 2/5] x86/tdx: Add validation of userspace MMIO
 instructions*

On Tue, Aug 06, 2024 at 11:41:57AM +0000, Reshetova, Elena wrote:
> > On Tue, Aug 06, 2024 at 10:18:20AM +0300, kirill.shutemov@linux.intel.com
> > wrote:

I have added a patch that does not allow access to userspace addresses if
we are in a kernel space context.

---

## [30] Alexey Gladkov — 2024-08-08
*Subject: Re: [PATCH v2 5/5] x86/tdx: Implement movs for MMIO*

On Thu, Aug 08, 2024 at 08:48:26AM -0500, Tom Lendacky wrote:
> On 8/5/24 08:29, Alexey Gladkov (Intel) wrote:
> > Add emulation of the MOVS instruction on MMIO regions. MOVS emulation

Ah. You mean that read/write operations will be performed in kernel space
context and no checks will be made.

I guess you're right.

> Thanks,
> Tom

---

## [31] Alexey Gladkov — 2024-08-16
*Subject: [PATCH v3 00/10] x86/tdx: Allow MMIO instructions from userspace*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Currently, MMIO inside the TDX guest is allowed from kernel space and access
from userspace is denied. This becomes a problem when working with virtual
devices in userspace.

In TDX guest MMIO instructions are emulated in #VE. The kernel code uses special
helpers to access MMIO memory to limit the number of instructions which are
used.

This patchset makes MMIO accessible from userspace. To do this additional checks
were added to ensure that the emulated instruction will not be compromised.


v3:
- Added patches to avoid crossing the page boundary when the instruction is read
  and decoded in the TDX, SEV, UMIP.
- Forbid accessing userspace addresses from kernel space. The exception to this
  is when emulating MOVS instructions.
- Fix address validation during MOVS emulation.

v2:
- Split into separate patches AMD helpers extraction and MOVS implementation
  code for intel as suggested by Thomas Gleixner.
- Fix coding style issues.


Alexey Gladkov (Intel) (10):
  x86/tdx: Split MMIO read and write operations
  x86/tdx: Add validation of userspace MMIO instructions
  x86/tdx: Allow MMIO from userspace
  x86/insn: Read and decode insn without crossing the page boundary
  x86/tdx: Avoid crossing the page boundary
  x86/sev: Avoid crossing the page boundary
  x86/umip: Avoid crossing the page boundary
  x86/tdx: Add a restriction on access to MMIO address
  x86/tdx: Move MMIO helpers to common library
  x86/tdx: Implement movs for MMIO

 arch/x86/coco/sev/core.c         | 147 ++------------
 arch/x86/coco/tdx/tdx.c          | 329 ++++++++++++++++++++++++++-----
 arch/x86/include/asm/insn-eval.h |  15 ++
 arch/x86/include/asm/io.h        |   3 +
 arch/x86/include/asm/processor.h |   4 +
 arch/x86/kernel/umip.c           |   7 +-
 arch/x86/lib/insn-eval.c         |  55 ++++++
 arch/x86/lib/iomem.c             | 125 ++++++++++++
 8 files changed, 498 insertions(+), 187 deletions(-)

---

## [32] Alexey Gladkov — 2024-08-16
*Subject: [PATCH v3 01/10] x86/tdx: Split MMIO read and write operations*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

To implement MMIO in userspace, additional memory checks need to be
implemented. To avoid overly complicating the handle_mmio() function
and to separate checks from actions, it would be better to split this
function into two separate functions to handle read and write
operations.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 136 ++++++++++++++++++++++++----------------
 1 file changed, 83 insertions(+), 53 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 078e2bac2553..af0b6c1cacf7 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -405,14 +405,91 @@ static bool mmio_write(int size, unsigned long addr, unsigned long val)
 			       EPT_WRITE, addr, val);
 }
 
+static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
+			     struct pt_regs *regs, struct ve_info *ve)
+{
+	unsigned long *reg, val;
+
+	switch (mmio) {
+	case INSN_MMIO_WRITE:
+		reg = insn_get_modrm_reg_ptr(insn, regs);
+		if (!reg)
+			return -EINVAL;
+		memcpy(&val, reg, size);
+		if (!mmio_write(size, ve->gpa, val))
+			return -EIO;
+		return insn->length;
+	case INSN_MMIO_WRITE_IMM:
+		val = insn->immediate.value;
+		if (!mmio_write(size, ve->gpa, val))
+			return -EIO;
+		return insn->length;
+	case INSN_MMIO_MOVS:
+		/*
+		 * MMIO was accessed with an instruction that could not be
+		 * decoded or handled properly. It was likely not using io.h
+		 * helpers or accessed MMIO accidentally.
+		 */
+		return -EINVAL;
+	default:
+		WARN_ON_ONCE(1);
+		return -EINVAL;
+	}
+
+	return insn->length;
+}
+
+static int handle_mmio_read(struct insn *insn, enum insn_mmio_type mmio, int size,
+			    struct pt_regs *regs, struct ve_info *ve)
+{
+	unsigned long *reg, val;
+	int extend_size;
+	u8 extend_val;
+
+	reg = insn_get_modrm_reg_ptr(insn, regs);
+	if (!reg)
+		return -EINVAL;
+
+	if (!mmio_read(size, ve->gpa, &val))
+		return -EIO;
+
+	extend_val = 0;
+
+	switch (mmio) {
+	case INSN_MMIO_READ:
+		/* Zero-extend for 32-bit operation */
+		extend_size = size == 4 ? sizeof(*reg) : 0;
+		break;
+	case INSN_MMIO_READ_ZERO_EXTEND:
+		/* Zero extend based on operand size */
+		extend_size = insn->opnd_bytes;
+		break;
+	case INSN_MMIO_READ_SIGN_EXTEND:
+		/* Sign extend based on operand size */
+		extend_size = insn->opnd_bytes;
+		if (size == 1 && val & BIT(7))
+			extend_val = 0xFF;
+		else if (size > 1 && val & BIT(15))
+			extend_val = 0xFF;
+		break;
+	default:
+		WARN_ON_ONCE(1);
+		return -EINVAL;
+	}
+
+	if (extend_size)
+		memset(reg, extend_val, extend_size);
+	memcpy(reg, &val, size);
+	return insn->length;
+}
+
 static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 {
-	unsigned long *reg, val, vaddr;
 	char buffer[MAX_INSN_SIZE];
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
-	int size, extend_size;
-	u8 extend_val = 0;
+	unsigned long vaddr;
+	int size;
 
 	/* Only in-kernel MMIO is supported */
 	if (WARN_ON_ONCE(user_mode(regs)))
@@ -428,12 +505,6 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
-	if (mmio != INSN_MMIO_WRITE_IMM && mmio != INSN_MMIO_MOVS) {
-		reg = insn_get_modrm_reg_ptr(&insn, regs);
-		if (!reg)
-			return -EINVAL;
-	}
-
 	/*
 	 * Reject EPT violation #VEs that split pages.
 	 *
@@ -447,24 +518,15 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (vaddr / PAGE_SIZE != (vaddr + size - 1) / PAGE_SIZE)
 		return -EFAULT;
 
-	/* Handle writes first */
 	switch (mmio) {
 	case INSN_MMIO_WRITE:
-		memcpy(&val, reg, size);
-		if (!mmio_write(size, ve->gpa, val))
-			return -EIO;
-		return insn.length;
 	case INSN_MMIO_WRITE_IMM:
-		val = insn.immediate.value;
-		if (!mmio_write(size, ve->gpa, val))
-			return -EIO;
-		return insn.length;
+	case INSN_MMIO_MOVS:
+		return handle_mmio_write(&insn, mmio, size, regs, ve);
 	case INSN_MMIO_READ:
 	case INSN_MMIO_READ_ZERO_EXTEND:
 	case INSN_MMIO_READ_SIGN_EXTEND:
-		/* Reads are handled below */
-		break;
-	case INSN_MMIO_MOVS:
+		return handle_mmio_read(&insn, mmio, size, regs, ve);
 	case INSN_MMIO_DECODE_FAILED:
 		/*
 		 * MMIO was accessed with an instruction that could not be
@@ -476,38 +538,6 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 		WARN_ONCE(1, "Unknown insn_decode_mmio() decode value?");
 		return -EINVAL;
 	}
-
-	/* Handle reads */
-	if (!mmio_read(size, ve->gpa, &val))
-		return -EIO;
-
-	switch (mmio) {
-	case INSN_MMIO_READ:
-		/* Zero-extend for 32-bit operation */
-		extend_size = size == 4 ? sizeof(*reg) : 0;
-		break;
-	case INSN_MMIO_READ_ZERO_EXTEND:
-		/* Zero extend based on operand size */
-		extend_size = insn.opnd_bytes;
-		break;
-	case INSN_MMIO_READ_SIGN_EXTEND:
-		/* Sign extend based on operand size */
-		extend_size = insn.opnd_bytes;
-		if (size == 1 && val & BIT(7))
-			extend_val = 0xFF;
-		else if (size > 1 && val & BIT(15))
-			extend_val = 0xFF;
-		break;
-	default:
-		/* All other cases has to be covered with the first switch() */
-		WARN_ON_ONCE(1);
-		return -EINVAL;
-	}
-
-	if (extend_size)
-		memset(reg, extend_val, extend_size);
-	memcpy(reg, &val, size);
-	return insn.length;
 }
 
 static bool handle_in(struct pt_regs *regs, int size, int port)

---

## [33] Alexey Gladkov — 2024-08-16
*Subject: [PATCH v3 02/10] x86/tdx: Add validation of userspace MMIO instructions*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Instructions from kernel space are considered trusted. If the MMIO
instruction is from userspace it must be checked.

For userspace instructions, it is need to check that the INSN has not
changed at the time of #VE and before the execution of the instruction.

Once the userspace instruction parsed is enforced that the address
points to mapped memory of current process and that address does not
point to private memory.

After parsing the userspace instruction, it is necessary to ensure that:

1. the operation direction (read/write) corresponds to #VE info;
2. the address still points to mapped memory of current process;
3. the address does not point to private memory.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 128 ++++++++++++++++++++++++++++++++++++----
 1 file changed, 115 insertions(+), 13 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index af0b6c1cacf7..86c22fec97fb 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -8,6 +8,7 @@
 #include <linux/export.h>
 #include <linux/io.h>
 #include <linux/kexec.h>
+#include <linux/mm.h>
 #include <asm/coco.h>
 #include <asm/tdx.h>
 #include <asm/vmx.h>
@@ -405,6 +406,84 @@ static bool mmio_write(int size, unsigned long addr, unsigned long val)
 			       EPT_WRITE, addr, val);
 }
 
+static inline bool is_private_gpa(u64 gpa)
+{
+	return gpa == cc_mkenc(gpa);
+}
+
+static int get_phys_addr(unsigned long addr, phys_addr_t *phys_addr, bool *writable)
+{
+	unsigned int level;
+	pgd_t *pgdp;
+	pte_t *ptep;
+
+	/*
+	 * Address validation only makes sense for a user process. The lock must
+	 * be obtained before validation can begin.
+	 */
+	mmap_assert_locked(current->mm);
+
+	pgdp = pgd_offset(current->mm, addr);
+
+	if (!pgd_none(*pgdp)) {
+		ptep = lookup_address_in_pgd(pgdp, addr, &level);
+		if (ptep) {
+			unsigned long offset;
+
+			offset = addr & ~page_level_mask(level);
+			*phys_addr = PFN_PHYS(pte_pfn(*ptep));
+			*phys_addr |= offset;
+
+			*writable = pte_write(*ptep);
+
+			return 0;
+		}
+	}
+
+	return -EFAULT;
+}
+
+static int valid_vaddr(struct ve_info *ve, enum insn_mmio_type mmio, int size,
+		       unsigned long vaddr)
+{
+	phys_addr_t phys_addr;
+	bool writable = false;
+
+	/* It's not fatal. This can happen due to swap out or page migration. */
+	if (get_phys_addr(vaddr, &phys_addr, &writable) || (ve->gpa != cc_mkdec(phys_addr)))
+		return -EAGAIN;
+
+	/*
+	 * Re-check whether #VE info matches the instruction that was decoded.
+	 *
+	 * The ve->gpa was valid at the time ve_info was received. But this code
+	 * executed with interrupts enabled, allowing tlb shootdown and therefore
+	 * munmap() to be executed in the parallel thread.
+	 *
+	 * By the time MMIO emulation is performed, ve->gpa may be already
+	 * unmapped from the process, the device it belongs to removed from
+	 * system and something else could be plugged in its place.
+	 */
+	switch (mmio) {
+	case INSN_MMIO_WRITE:
+	case INSN_MMIO_WRITE_IMM:
+		if (!writable || !(ve->exit_qual & EPT_VIOLATION_ACC_WRITE))
+			return -EFAULT;
+		break;
+	case INSN_MMIO_READ:
+	case INSN_MMIO_READ_ZERO_EXTEND:
+	case INSN_MMIO_READ_SIGN_EXTEND:
+		if (!(ve->exit_qual & EPT_VIOLATION_ACC_READ))
+			return -EFAULT;
+		break;
+	default:
+		WARN_ONCE(1, "Unsupported mmio instruction: %d", mmio);
+		return -EINVAL;
+	}
+
+	return 0;
+}
+
 static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
 			     struct pt_regs *regs, struct ve_info *ve)
 {
@@ -489,7 +568,7 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
 	unsigned long vaddr;
-	int size;
+	int size, ret;
 
 	/* Only in-kernel MMIO is supported */
 	if (WARN_ON_ONCE(user_mode(regs)))
@@ -505,6 +584,17 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
+	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
+
+	if (current->mm) {
+		if (mmap_read_lock_killable(current->mm))
+			return -EINTR;
+
+		ret = valid_vaddr(ve, mmio, size, vaddr);
+		if (ret)
+			goto unlock;
+	}
+
 	/*
 	 * Reject EPT violation #VEs that split pages.
 	 *
@@ -514,30 +604,39 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	 *
 	 * load_unaligned_zeropad() will recover using exception fixups.
 	 */
-	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
-	if (vaddr / PAGE_SIZE != (vaddr + size - 1) / PAGE_SIZE)
-		return -EFAULT;
+	if (vaddr / PAGE_SIZE != (vaddr + size - 1) / PAGE_SIZE) {
+		ret = -EFAULT;
+		goto unlock;
+	}
 
 	switch (mmio) {
 	case INSN_MMIO_WRITE:
 	case INSN_MMIO_WRITE_IMM:
 	case INSN_MMIO_MOVS:
-		return handle_mmio_write(&insn, mmio, size, regs, ve);
+		ret = handle_mmio_write(&insn, mmio, size, regs, ve);
+		break;
 	case INSN_MMIO_READ:
 	case INSN_MMIO_READ_ZERO_EXTEND:
 	case INSN_MMIO_READ_SIGN_EXTEND:
-		return handle_mmio_read(&insn, mmio, size, regs, ve);
+		ret = handle_mmio_read(&insn, mmio, size, regs, ve);
+		break;
 	case INSN_MMIO_DECODE_FAILED:
 		/*
 		 * MMIO was accessed with an instruction that could not be
 		 * decoded or handled properly. It was likely not using io.h
 		 * helpers or accessed MMIO accidentally.
 		 */
-		return -EINVAL;
+		ret = -EINVAL;
+		break;
 	default:
 		WARN_ONCE(1, "Unknown insn_decode_mmio() decode value?");
-		return -EINVAL;
+		ret = -EINVAL;
 	}
+unlock:
+	if (current->mm)
+		mmap_read_unlock(current->mm);
+
+	return ret;
 }
 
 static bool handle_in(struct pt_regs *regs, int size, int port)
@@ -681,11 +780,6 @@ static int virt_exception_user(struct pt_regs *regs, struct ve_info *ve)
 	}
 }
 
-static inline bool is_private_gpa(u64 gpa)
-{
-	return gpa == cc_mkenc(gpa);
-}
-
 /*
  * Handle the kernel #VE.
  *
@@ -723,6 +817,14 @@ bool tdx_handle_virt_exception(struct pt_regs *regs, struct ve_info *ve)
 		insn_len = virt_exception_user(regs, ve);
 	else
 		insn_len = virt_exception_kernel(regs, ve);
+
+	/*
+	 * A special case to return to userspace without increasing regs->ip
+	 * to repeat the instruction once again.
+	 */
+	if (insn_len == -EAGAIN)
+		return true;
+
 	if (insn_len < 0)
 		return false;

---

## [34] Alexey Gladkov — 2024-08-16
*Subject: [PATCH v3 03/10] x86/tdx: Allow MMIO from userspace*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

The MMIO emulation is only allowed for kernel space code. It is carried
out through a special API, which uses only certain instructions.

This does not allow userspace to work with virtual devices.

Allow userspace to use the same instructions as kernel space to access
MMIO. So far, no additional checks have been made.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 43 +++++++++++++++++++++++++++++++----------
 1 file changed, 33 insertions(+), 10 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 86c22fec97fb..254d5293d25a 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -484,6 +484,32 @@ static int valid_vaddr(struct ve_info *ve, enum insn_mmio_type mmio, int size,
 	return 0;
 }
 
+static int decode_insn_struct(struct insn *insn, struct pt_regs *regs)
+{
+	char buffer[MAX_INSN_SIZE];
+
+	if (user_mode(regs)) {
+		int nr_copied = insn_fetch_from_user(regs, buffer);
+
+		if (nr_copied <= 0)
+			return -EFAULT;
+
+		if (!insn_decode_from_regs(insn, regs, buffer, nr_copied))
+			return -EINVAL;
+	} else {
+		if (copy_from_kernel_nofault(buffer, (void *)regs->ip, MAX_INSN_SIZE))
+			return -EFAULT;
+
+		if (insn_decode(insn, buffer, MAX_INSN_SIZE, INSN_MODE_64))
+			return -EINVAL;
+	}
+
+	if (!insn->immediate.got)
+		return -EINVAL;
+
+	return 0;
+}
+
 static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
 			     struct pt_regs *regs, struct ve_info *ve)
 {
@@ -564,21 +590,14 @@ static int handle_mmio_read(struct insn *insn, enum insn_mmio_type mmio, int siz
 
 static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 {
-	char buffer[MAX_INSN_SIZE];
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
 	unsigned long vaddr;
 	int size, ret;
 
-	/* Only in-kernel MMIO is supported */
-	if (WARN_ON_ONCE(user_mode(regs)))
-		return -EFAULT;
-
-	if (copy_from_kernel_nofault(buffer, (void *)regs->ip, MAX_INSN_SIZE))
-		return -EFAULT;
-
-	if (insn_decode(&insn, buffer, MAX_INSN_SIZE, INSN_MODE_64))
-		return -EINVAL;
+	ret = decode_insn_struct(&insn, regs);
+	if (ret)
+		return ret;
 
 	mmio = insn_decode_mmio(&insn, &size);
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
@@ -774,6 +793,10 @@ static int virt_exception_user(struct pt_regs *regs, struct ve_info *ve)
 	switch (ve->exit_reason) {
 	case EXIT_REASON_CPUID:
 		return handle_cpuid(regs, ve);
+	case EXIT_REASON_EPT_VIOLATION:
+		if (is_private_gpa(ve->gpa))
+			panic("Unexpected EPT-violation on private memory.");
+		return handle_mmio(regs, ve);
 	default:
 		pr_warn("Unexpected #VE: %lld\n", ve->exit_reason);
 		return -EIO;

---

## [35] Alexey Gladkov — 2024-08-16
*Subject: [PATCH v3 04/10] x86/insn: Read and decode insn without crossing the page boundary*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

In case the instruction is close to the page boundary, reading
MAX_INSN_SIZE may cross the page boundary. The second page might be
from a different VMA and reading can have side effects.

The problem is that the actual size of the instruction is not known.

The solution might be to try read the data to the end of the page and
try parse it in the hope that the instruction is smaller than the
maximum buffer size.

Co-developed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/include/asm/insn-eval.h | 15 +++++++++
 arch/x86/lib/insn-eval.c         | 55 ++++++++++++++++++++++++++++++++
 2 files changed, 70 insertions(+)

diff --git a/arch/x86/include/asm/insn-eval.h b/arch/x86/include/asm/insn-eval.h
index 54368a43abf6..160e483bde99 100644
--- a/arch/x86/include/asm/insn-eval.h
+++ b/arch/x86/include/asm/insn-eval.h
@@ -32,6 +32,21 @@ int insn_fetch_from_user_inatomic(struct pt_regs *regs,
 bool insn_decode_from_regs(struct insn *insn, struct pt_regs *regs,
 			   unsigned char buf[MAX_INSN_SIZE], int buf_size);
 
+int insn_fetch_decode_from_user_common(struct insn *insn, struct pt_regs *regs,
+				       bool inatomic);
+
+static inline int insn_fetch_decode_from_user(struct insn *insn,
+					      struct pt_regs *regs)
+{
+	return insn_fetch_decode_from_user_common(insn, regs, false);
+}
+
+static inline int insn_fetch_decode_from_user_inatomic(struct insn *insn,
+						       struct pt_regs *regs)
+{
+	return insn_fetch_decode_from_user_common(insn, regs, true);
+}
+
 enum insn_mmio_type {
 	INSN_MMIO_DECODE_FAILED,
 	INSN_MMIO_WRITE,
diff --git a/arch/x86/lib/insn-eval.c b/arch/x86/lib/insn-eval.c
index 98631c0e7a11..67bfb645df67 100644
--- a/arch/x86/lib/insn-eval.c
+++ b/arch/x86/lib/insn-eval.c
@@ -1668,3 +1668,58 @@ enum insn_mmio_type insn_decode_mmio(struct insn *insn, int *bytes)
 
 	return type;
 }
+
+/**
+ * insn_fetch_decode_from_user_common() - Copy and decode instruction bytes
+ *                                        from user-space memory
+ * @buf:	Array to store the fetched instruction
+ * @regs:	Structure with register values as seen when entering kernel mode
+ * @inatomic	boolean flag whether function is used in atomic context
+ *
+ * Gets the linear address of the instruction and copies the instruction bytes
+ * and decodes the instruction.
+ *
+ * Returns:
+ *
+ * - 0 on success.
+ * - -EFAULT if the copy from userspace fails.
+ * - -EINVAL if the linear address of the instruction could not be calculated.
+ */
+int insn_fetch_decode_from_user_common(struct insn *insn, struct pt_regs *regs,
+				bool inatomic)
+{
+	char buffer[MAX_INSN_SIZE];
+	int nr_copied, size;
+	unsigned long ip;
+
+	if (insn_get_effective_ip(regs, &ip))
+		return -EINVAL;
+
+	/*
+	 * On the first attempt, read up to MAX_INSN_SIZE, but do not cross a
+	 * page boundary. The second page might be from a different VMA and
+	 * reading can have side effects (i.e. reading from MMIO).
+	 */
+	size = min(MAX_INSN_SIZE, PAGE_SIZE - offset_in_page(ip));
+retry:
+	nr_copied = size;
+
+	if (inatomic)
+		nr_copied -= __copy_from_user_inatomic(buffer, (void __user *)ip, size);
+	else
+		nr_copied -= copy_from_user(buffer, (void __user *)ip, size);
+
+	if (nr_copied <= 0)
+		return -EFAULT;
+
+	if (!insn_decode_from_regs(insn, regs, buffer, nr_copied)) {
+		/* If decode failed, try to copy across page boundary */
+		if (size < MAX_INSN_SIZE) {
+			size = MAX_INSN_SIZE;
+			goto retry;
+		}
+		return -EINVAL;
+	}
+
+	return 0;
+}

---

## [36] Alexey Gladkov — 2024-08-16
*Subject: [PATCH v3 05/10] x86/tdx: Avoid crossing the page boundary*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Try to avoid crossing the page boundary to avoid side effects if the
next page belongs to another VMA.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 9 +++------
 1 file changed, 3 insertions(+), 6 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 254d5293d25a..e3d692342603 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -489,13 +489,10 @@ static int decode_insn_struct(struct insn *insn, struct pt_regs *regs)
 	char buffer[MAX_INSN_SIZE];
 
 	if (user_mode(regs)) {
-		int nr_copied = insn_fetch_from_user(regs, buffer);
+		int ret = insn_fetch_decode_from_user(insn, regs);
 
-		if (nr_copied <= 0)
-			return -EFAULT;
-
-		if (!insn_decode_from_regs(insn, regs, buffer, nr_copied))
-			return -EINVAL;
+		if (ret)
+			return ret;
 	} else {
 		if (copy_from_kernel_nofault(buffer, (void *)regs->ip, MAX_INSN_SIZE))
 			return -EFAULT;

---

## [37] Alexey Gladkov — 2024-08-16
*Subject: [PATCH v3 06/10] x86/sev: Avoid crossing the page boundary*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Try to avoid crossing the page boundary to avoid side effects if the
next page belongs to another VMA.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/sev/core.c | 12 ++++--------
 1 file changed, 4 insertions(+), 8 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 082d61d85dfc..b0e8e4264464 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -311,17 +311,16 @@ static int vc_fetch_insn_kernel(struct es_em_ctxt *ctxt,
 
 static enum es_result __vc_decode_user_insn(struct es_em_ctxt *ctxt)
 {
-	char buffer[MAX_INSN_SIZE];
-	int insn_bytes;
+	int ret;
 
-	insn_bytes = insn_fetch_from_user_inatomic(ctxt->regs, buffer);
-	if (insn_bytes == 0) {
+	ret = insn_fetch_decode_from_user_inatomic(&ctxt->insn, ctxt->regs);
+	if (ret == -EFAULT) {
 		/* Nothing could be copied */
 		ctxt->fi.vector     = X86_TRAP_PF;
 		ctxt->fi.error_code = X86_PF_INSTR | X86_PF_USER;
 		ctxt->fi.cr2        = ctxt->regs->ip;
 		return ES_EXCEPTION;
-	} else if (insn_bytes == -EINVAL) {
+	} else if (ret == -EINVAL) {
 		/* Effective RIP could not be calculated */
 		ctxt->fi.vector     = X86_TRAP_GP;
 		ctxt->fi.error_code = 0;
@@ -329,9 +328,6 @@ static enum es_result __vc_decode_user_insn(struct es_em_ctxt *ctxt)
 		return ES_EXCEPTION;
 	}
 
-	if (!insn_decode_from_regs(&ctxt->insn, ctxt->regs, buffer, insn_bytes))
-		return ES_DECODE_FAILED;
-
 	if (ctxt->insn.immediate.got)
 		return ES_OK;
 	else

---

## [38] Alexey Gladkov — 2024-08-16
*Subject: [PATCH v3 07/10] x86/umip: Avoid crossing the page boundary*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Try to avoid crossing the page boundary to avoid side effects if the
next page belongs to another VMA.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/kernel/umip.c | 7 +------
 1 file changed, 1 insertion(+), 6 deletions(-)

diff --git a/arch/x86/kernel/umip.c b/arch/x86/kernel/umip.c
index 5a4b21389b1d..e85c3cafc258 100644
--- a/arch/x86/kernel/umip.c
+++ b/arch/x86/kernel/umip.c
@@ -338,7 +338,6 @@ bool fixup_umip_exception(struct pt_regs *regs)
 	int nr_copied, reg_offset, dummy_data_size, umip_inst;
 	/* 10 bytes is the maximum size of the result of UMIP instructions */
 	unsigned char dummy_data[10] = { 0 };
-	unsigned char buf[MAX_INSN_SIZE];
 	unsigned long *reg_addr;
 	void __user *uaddr;
 	struct insn insn;
@@ -350,11 +349,7 @@ bool fixup_umip_exception(struct pt_regs *regs)
 	 * Give up on emulation if fetching the instruction failed. Should a
 	 * page fault or a #GP be issued?
 	 */
-	nr_copied = insn_fetch_from_user(regs, buf);
-	if (nr_copied <= 0)
-		return false;
-
-	if (!insn_decode_from_regs(&insn, regs, buf, nr_copied))
+	if (insn_fetch_decode_from_user(&insn, regs))
 		return false;
 
 	umip_inst = identify_insn(&insn);

---

## [39] Alexey Gladkov — 2024-08-16
*Subject: [PATCH v3 08/10] x86/tdx: Add a restriction on access to MMIO address*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

In the case of userspace MMIO, if the user instruction + MAX_INSN_SIZE
straddles page, then the "fetch" in the kernel could trigger a #VE. In
this case the kernel would handle this second #VE as a !user_mode() MMIO.
That way, additional address verifications can be avoided.

The scenario of accessing userspace MMIO addresses from kernelspace does
not seem appropriate under normal circumstances. Until there is a
specific usecase for such a scenario it can be disabled.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 11 +++++++++++
 1 file changed, 11 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index e3d692342603..94541ee724db 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -411,6 +411,11 @@ static inline bool is_private_gpa(u64 gpa)
 	return gpa == cc_mkenc(gpa);
 }
 
+static inline bool is_kernel_addr(unsigned long addr)
+{
+	return (long)addr < 0;
+}
+
 static int get_phys_addr(unsigned long addr, phys_addr_t *phys_addr, bool *writable)
 {
 	unsigned int level;
@@ -592,6 +597,7 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	unsigned long vaddr;
 	int size, ret;
 
+
 	ret = decode_insn_struct(&insn, regs);
 	if (ret)
 		return ret;
@@ -600,6 +606,11 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
+	if (!user_mode(regs) && !is_kernel_addr(ve->gla)) {
+		WARN_ONCE(1, "Access to userspace address is not supported");
+		return -EINVAL;
+	}
+
 	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
 
 	if (current->mm) {

---

## [40] Alexey Gladkov — 2024-08-16
*Subject: [PATCH v3 09/10] x86/tdx: Move MMIO helpers to common library*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

AMD code has helpers that are used to emulate MOVS instructions. To be
able to reuse this code in the MOVS implementation for intel, it is
necessary to move them to a common location.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/sev/core.c  | 135 ++++----------------------------------
 arch/x86/include/asm/io.h |   3 +
 arch/x86/lib/iomem.c      | 125 +++++++++++++++++++++++++++++++++++
 3 files changed, 142 insertions(+), 121 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index b0e8e4264464..c154d2587c38 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -365,72 +365,18 @@ static enum es_result vc_decode_insn(struct es_em_ctxt *ctxt)
 static enum es_result vc_write_mem(struct es_em_ctxt *ctxt,
 				   char *dst, char *buf, size_t size)
 {
-	unsigned long error_code = X86_PF_PROT | X86_PF_WRITE;
-
-	/*
-	 * This function uses __put_user() independent of whether kernel or user
-	 * memory is accessed. This works fine because __put_user() does no
-	 * sanity checks of the pointer being accessed. All that it does is
-	 * to report when the access failed.
-	 *
-	 * Also, this function runs in atomic context, so __put_user() is not
-	 * allowed to sleep. The page-fault handler detects that it is running
-	 * in atomic context and will not try to take mmap_sem and handle the
-	 * fault, so additional pagefault_enable()/disable() calls are not
-	 * needed.
-	 *
-	 * The access can't be done via copy_to_user() here because
-	 * vc_write_mem() must not use string instructions to access unsafe
-	 * memory. The reason is that MOVS is emulated by the #VC handler by
-	 * splitting the move up into a read and a write and taking a nested #VC
-	 * exception on whatever of them is the MMIO access. Using string
-	 * instructions here would cause infinite nesting.
-	 */
-	switch (size) {
-	case 1: {
-		u8 d1;
-		u8 __user *target = (u8 __user *)dst;
-
-		memcpy(&d1, buf, 1);
-		if (__put_user(d1, target))
-			goto fault;
-		break;
-	}
-	case 2: {
-		u16 d2;
-		u16 __user *target = (u16 __user *)dst;
-
-		memcpy(&d2, buf, 2);
-		if (__put_user(d2, target))
-			goto fault;
-		break;
-	}
-	case 4: {
-		u32 d4;
-		u32 __user *target = (u32 __user *)dst;
+	unsigned long error_code;
+	int ret;
 
-		memcpy(&d4, buf, 4);
-		if (__put_user(d4, target))
-			goto fault;
-		break;
-	}
-	case 8: {
-		u64 d8;
-		u64 __user *target = (u64 __user *)dst;
+	ret = __put_iomem(dst, buf, size);
+	if (!ret)
+		return ES_OK;
 
-		memcpy(&d8, buf, 8);
-		if (__put_user(d8, target))
-			goto fault;
-		break;
-	}
-	default:
-		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+	if (ret == -EIO)
 		return ES_UNSUPPORTED;
-	}
 
-	return ES_OK;
+	error_code = X86_PF_PROT | X86_PF_WRITE;
 
-fault:
 	if (user_mode(ctxt->regs))
 		error_code |= X86_PF_USER;
 
@@ -444,71 +390,18 @@ static enum es_result vc_write_mem(struct es_em_ctxt *ctxt,
 static enum es_result vc_read_mem(struct es_em_ctxt *ctxt,
 				  char *src, char *buf, size_t size)
 {
-	unsigned long error_code = X86_PF_PROT;
-
-	/*
-	 * This function uses __get_user() independent of whether kernel or user
-	 * memory is accessed. This works fine because __get_user() does no
-	 * sanity checks of the pointer being accessed. All that it does is
-	 * to report when the access failed.
-	 *
-	 * Also, this function runs in atomic context, so __get_user() is not
-	 * allowed to sleep. The page-fault handler detects that it is running
-	 * in atomic context and will not try to take mmap_sem and handle the
-	 * fault, so additional pagefault_enable()/disable() calls are not
-	 * needed.
-	 *
-	 * The access can't be done via copy_from_user() here because
-	 * vc_read_mem() must not use string instructions to access unsafe
-	 * memory. The reason is that MOVS is emulated by the #VC handler by
-	 * splitting the move up into a read and a write and taking a nested #VC
-	 * exception on whatever of them is the MMIO access. Using string
-	 * instructions here would cause infinite nesting.
-	 */
-	switch (size) {
-	case 1: {
-		u8 d1;
-		u8 __user *s = (u8 __user *)src;
-
-		if (__get_user(d1, s))
-			goto fault;
-		memcpy(buf, &d1, 1);
-		break;
-	}
-	case 2: {
-		u16 d2;
-		u16 __user *s = (u16 __user *)src;
+	unsigned long error_code;
+	int ret;
 
-		if (__get_user(d2, s))
-			goto fault;
-		memcpy(buf, &d2, 2);
-		break;
-	}
-	case 4: {
-		u32 d4;
-		u32 __user *s = (u32 __user *)src;
+	ret = __get_iomem(src, buf, size);
+	if (!ret)
+		return ES_OK;
 
-		if (__get_user(d4, s))
-			goto fault;
-		memcpy(buf, &d4, 4);
-		break;
-	}
-	case 8: {
-		u64 d8;
-		u64 __user *s = (u64 __user *)src;
-		if (__get_user(d8, s))
-			goto fault;
-		memcpy(buf, &d8, 8);
-		break;
-	}
-	default:
-		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+	if (ret == -EIO)
 		return ES_UNSUPPORTED;
-	}
 
-	return ES_OK;
+	error_code = X86_PF_PROT;
 
-fault:
 	if (user_mode(ctxt->regs))
 		error_code |= X86_PF_USER;
 
diff --git a/arch/x86/include/asm/io.h b/arch/x86/include/asm/io.h
index 1d60427379c9..ac01d53466cb 100644
--- a/arch/x86/include/asm/io.h
+++ b/arch/x86/include/asm/io.h
@@ -402,4 +402,7 @@ static inline void iosubmit_cmds512(void __iomem *dst, const void *src,
 	}
 }
 
+int __get_iomem(char *src, char *buf, size_t size);
+int __put_iomem(char *src, char *buf, size_t size);
+
 #endif /* _ASM_X86_IO_H */
diff --git a/arch/x86/lib/iomem.c b/arch/x86/lib/iomem.c
index 5eecb45d05d5..23179953eb5a 100644
--- a/arch/x86/lib/iomem.c
+++ b/arch/x86/lib/iomem.c
@@ -2,6 +2,7 @@
 #include <linux/module.h>
 #include <linux/io.h>
 #include <linux/kmsan-checks.h>
+#include <asm/uaccess.h>
 
 #define movs(type,to,from) \
 	asm volatile("movs" type:"=&D" (to), "=&S" (from):"0" (to), "1" (from):"memory")
@@ -124,3 +125,127 @@ void memset_io(volatile void __iomem *a, int b, size_t c)
 	}
 }
 EXPORT_SYMBOL(memset_io);
+
+int __get_iomem(char *src, char *buf, size_t size)
+{
+	/*
+	 * This function uses __get_user() independent of whether kernel or user
+	 * memory is accessed. This works fine because __get_user() does no
+	 * sanity checks of the pointer being accessed. All that it does is
+	 * to report when the access failed.
+	 *
+	 * Also, this function runs in atomic context, so __get_user() is not
+	 * allowed to sleep. The page-fault handler detects that it is running
+	 * in atomic context and will not try to take mmap_sem and handle the
+	 * fault, so additional pagefault_enable()/disable() calls are not
+	 * needed.
+	 *
+	 * The access can't be done via copy_from_user() here because
+	 * mmio_read_mem() must not use string instructions to access unsafe
+	 * memory. The reason is that MOVS is emulated by the #VC handler by
+	 * splitting the move up into a read and a write and taking a nested #VC
+	 * exception on whatever of them is the MMIO access. Using string
+	 * instructions here would cause infinite nesting.
+	 */
+	switch (size) {
+	case 1: {
+		u8 d1, __user *s = (u8 __user *)src;
+
+		if (__get_user(d1, s))
+			return -EFAULT;
+		memcpy(buf, &d1, 1);
+		break;
+	}
+	case 2: {
+		u16 d2, __user *s = (u16 __user *)src;
+
+		if (__get_user(d2, s))
+			return -EFAULT;
+		memcpy(buf, &d2, 2);
+		break;
+	}
+	case 4: {
+		u32 d4, __user *s = (u32 __user *)src;
+
+		if (__get_user(d4, s))
+			return -EFAULT;
+		memcpy(buf, &d4, 4);
+		break;
+	}
+	case 8: {
+		u64 d8, __user *s = (u64 __user *)src;
+
+		if (__get_user(d8, s))
+			return -EFAULT;
+		memcpy(buf, &d8, 8);
+		break;
+	}
+	default:
+		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+		return -EIO;
+	}
+
+	return 0;
+}
+
+int __put_iomem(char *dst, char *buf, size_t size)
+{
+	/*
+	 * This function uses __put_user() independent of whether kernel or user
+	 * memory is accessed. This works fine because __put_user() does no
+	 * sanity checks of the pointer being accessed. All that it does is
+	 * to report when the access failed.
+	 *
+	 * Also, this function runs in atomic context, so __put_user() is not
+	 * allowed to sleep. The page-fault handler detects that it is running
+	 * in atomic context and will not try to take mmap_sem and handle the
+	 * fault, so additional pagefault_enable()/disable() calls are not
+	 * needed.
+	 *
+	 * The access can't be done via copy_to_user() here because
+	 * put_iomem() must not use string instructions to access unsafe
+	 * memory. The reason is that MOVS is emulated by the #VC handler by
+	 * splitting the move up into a read and a write and taking a nested #VC
+	 * exception on whatever of them is the MMIO access. Using string
+	 * instructions here would cause infinite nesting.
+	 */
+	switch (size) {
+	case 1: {
+		u8 d1, __user *target = (u8 __user *)dst;
+
+		memcpy(&d1, buf, 1);
+		if (__put_user(d1, target))
+			return -EFAULT;
+		break;
+	}
+	case 2: {
+		u16 d2, __user *target = (u16 __user *)dst;
+
+		memcpy(&d2, buf, 2);
+		if (__put_user(d2, target))
+			return -EFAULT;
+		break;
+	}
+	case 4: {
+		u32 d4, __user *target = (u32 __user *)dst;
+
+		memcpy(&d4, buf, 4);
+		if (__put_user(d4, target))
+			return -EFAULT;
+		break;
+	}
+	case 8: {
+		u64 d8, __user *target = (u64 __user *)dst;
+
+		memcpy(&d8, buf, 8);
+		if (__put_user(d8, target))
+			return -EFAULT;
+		break;
+	}
+	default:
+		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+		return -EIO;
+	}
+
+	return 0;
+}

---

## [41] Alexey Gladkov — 2024-08-16
*Subject: [PATCH v3 10/10] x86/tdx: Implement movs for MMIO*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Add emulation of the MOVS instruction on MMIO regions. MOVS emulation
consists of dividing it into a series of read and write operations,
which in turn will be validated separately.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c          | 76 +++++++++++++++++++++++++++++---
 arch/x86/include/asm/processor.h |  4 ++
 2 files changed, 73 insertions(+), 7 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 94541ee724db..d7d762bf53dc 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -512,6 +512,62 @@ static int decode_insn_struct(struct insn *insn, struct pt_regs *regs)
 	return 0;
 }
 
+static int handle_mmio_movs(struct insn *insn, struct pt_regs *regs, int size, struct ve_info *ve)
+{
+	unsigned long ds_base, es_base;
+	unsigned char *src, *dst;
+	unsigned char buffer[8];
+	int off, ret;
+	bool rep;
+
+	/*
+	 * The in-kernel code must use a special API that does not use MOVS.
+	 * If the MOVS instruction is received from in-kernel, then something
+	 * is broken.
+	 */
+	if (WARN_ON_ONCE(!user_mode(regs)))
+		return -EFAULT;
+
+	ds_base = insn_get_seg_base(regs, INAT_SEG_REG_DS);
+	es_base = insn_get_seg_base(regs, INAT_SEG_REG_ES);
+
+	if (ds_base == -1L || es_base == -1L)
+		return -EINVAL;
+
+	rep = insn_has_rep_prefix(insn);
+
+	do {
+		src = ds_base + (unsigned char *) regs->si;
+		dst = es_base + (unsigned char *) regs->di;
+
+		current->thread.mmio_emul = (unsigned long) src;
+
+		ret = __get_iomem(src, buffer, size);
+		if (ret)
+			goto out;
+
+		current->thread.mmio_emul = (unsigned long) dst;
+
+		ret = __put_iomem(dst, buffer, size);
+		if (ret)
+			goto out;
+
+		off = (regs->flags & X86_EFLAGS_DF) ? -size : size;
+
+		regs->si += off;
+		regs->di += off;
+
+		if (rep)
+			regs->cx -= 1;
+	} while (rep || regs->cx > 0);
+
+	ret = insn->length;
+out:
+	current->thread.mmio_emul = 0;
+
+	return ret;
+}
+
 static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
 			     struct pt_regs *regs, struct ve_info *ve)
 {
@@ -533,9 +589,8 @@ static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int si
 		return insn->length;
 	case INSN_MMIO_MOVS:
 		/*
-		 * MMIO was accessed with an instruction that could not be
-		 * decoded or handled properly. It was likely not using io.h
-		 * helpers or accessed MMIO accidentally.
+		 * MOVS is processed through higher level emulation which breaks
+		 * this instruction into a sequence of reads and writes.
 		 */
 		return -EINVAL;
 	default:
@@ -597,7 +652,6 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	unsigned long vaddr;
 	int size, ret;
 
-
 	ret = decode_insn_struct(&insn, regs);
 	if (ret)
 		return ret;
@@ -606,9 +660,18 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
+	if (mmio == INSN_MMIO_MOVS)
+		return handle_mmio_movs(&insn, regs, size, ve);
+
 	if (!user_mode(regs) && !is_kernel_addr(ve->gla)) {
-		WARN_ONCE(1, "Access to userspace address is not supported");
-		return -EINVAL;
+		/*
+		 * Access from kernel to userspace addresses is not allowed
+		 * unless it is a nested exception during MOVS emulation.
+		 */
+		if (current->thread.mmio_emul != ve->gla || !current->mm) {
+			WARN_ONCE(1, "Access to userspace address is not supported");
+			return -EINVAL;
+		}
 	}
 
 	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
@@ -639,7 +702,6 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	switch (mmio) {
 	case INSN_MMIO_WRITE:
 	case INSN_MMIO_WRITE_IMM:
-	case INSN_MMIO_MOVS:
 		ret = handle_mmio_write(&insn, mmio, size, regs, ve);
 		break;
 	case INSN_MMIO_READ:
diff --git a/arch/x86/include/asm/processor.h b/arch/x86/include/asm/processor.h
index a75a07f4931f..45136b1b02cc 100644
--- a/arch/x86/include/asm/processor.h
+++ b/arch/x86/include/asm/processor.h
@@ -503,6 +503,10 @@ struct thread_struct {
 	struct thread_shstk	shstk;
 #endif
 
+#ifdef CONFIG_INTEL_TDX_GUEST
+	unsigned long		mmio_emul;
+#endif
+
 	/* Floating point and extended processor state */
 	struct fpu		fpu;
 	/*

---

## [42] kernel test robot — 2024-08-17
*Subject: Re: [PATCH v3 04/10] x86/insn: Read and decode insn without crossing
 the page boundary*

Hi Alexey,

kernel test robot noticed the following build warnings:

[auto build test WARNING on tip/x86/core]
[also build test WARNING on tip/master linus/master v6.11-rc3 next-20240816]
[cannot apply to tip/x86/tdx tip/auto-latest]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Alexey-Gladkov/x86-tdx-Split-MMIO-read-and-write-operations/20240816-222615
base:   tip/x86/core
patch link:    https://lore.kernel.org/r/9704da6a35d62932d464d33b39953fc5b2fd74ea.1723807851.git.legion%40kernel.org
patch subject: [PATCH v3 04/10] x86/insn: Read and decode insn without crossing the page boundary
config: i386-buildonly-randconfig-001-20240817 (https://download.01.org/0day-ci/archive/20240817/202408171001.feB1A8FN-lkp@intel.com/config)
compiler: gcc-12 (Debian 12.2.0-14) 12.2.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20240817/202408171001.feB1A8FN-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202408171001.feB1A8FN-lkp@intel.com/

All warnings (new ones prefixed by >>):

>> arch/x86/lib/insn-eval.c:1690: warning: Function parameter or struct member 'insn' not described in 'insn_fetch_decode_from_user_common'
>> arch/x86/lib/insn-eval.c:1690: warning: Function parameter or struct member 'inatomic' not described in 'insn_fetch_decode_from_user_common'


vim +1690 arch/x86/lib/insn-eval.c

  1671	
  1672	/**
  1673	 * insn_fetch_decode_from_user_common() - Copy and decode instruction bytes
  1674	 *                                        from user-space memory
  1675	 * @buf:	Array to store the fetched instruction
  1676	 * @regs:	Structure with register values as seen when entering kernel mode
  1677	 * @inatomic	boolean flag whether function is used in atomic context
  1678	 *
  1679	 * Gets the linear address of the instruction and copies the instruction bytes
  1680	 * and decodes the instruction.
  1681	 *
  1682	 * Returns:
  1683	 *
  1684	 * - 0 on success.
  1685	 * - -EFAULT if the copy from userspace fails.
  1686	 * - -EINVAL if the linear address of the instruction could not be calculated.
  1687	 */
  1688	int insn_fetch_decode_from_user_common(struct insn *insn, struct pt_regs *regs,
  1689					bool inatomic)
> 1690	{

---

## [43] Kirill A. Shutemov — 2024-08-19
*Subject: Re: [PATCH v3 01/10] x86/tdx: Split MMIO read and write operations*

On Fri, Aug 16, 2024 at 03:43:51PM +0200, Alexey Gladkov wrote:
> From: "Alexey Gladkov (Intel)" <legion@kernel.org>
> 

Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

---

## [44] Kirill A. Shutemov — 2024-08-19
*Subject: Re: [PATCH v3 02/10] x86/tdx: Add validation of userspace MMIO
 instructions*

On Fri, Aug 16, 2024 at 03:43:52PM +0200, Alexey Gladkov wrote:
> From: "Alexey Gladkov (Intel)" <legion@kernel.org>
> 

Well, we cannot really check if the instruction changed under us. We can
only check if the parsed instruction does an MMIO operation that is
allowed for the process.

> 
> Once the userspace instruction parsed is enforced that the address

I don't see where you check 3.

I guess you can add pte_decrypted(pte) check to get_phys_addr().

But I'm not sure it is strictly needed.

> Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
> ---

Too long line?

> +		return -EAGAIN;
> +

Hm. This path will be taken for any MMIO if it is done in context of a
process, even in-kernel only. I don't think we want it. It is useless
overhead.

Use user_mode(regs) instead.

> +		if (mmap_read_lock_killable(current->mm))
> +			return -EINTR;

---

## [45] Kirill A. Shutemov — 2024-08-19
*Subject: Re: [PATCH v3 03/10] x86/tdx: Allow MMIO from userspace*

On Fri, Aug 16, 2024 at 03:43:53PM +0200, Alexey Gladkov wrote:
> From: "Alexey Gladkov (Intel)" <legion@kernel.org>
> 

Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

And you seem to lost Reviewed-by from Thomas:

https://lore.kernel.org/all/874j867mnd.ffs@tglx

---

## [46] Kirill A. Shutemov — 2024-08-19
*Subject: Re: [PATCH v3 04/10] x86/insn: Read and decode insn without crossing
 the page boundary*

On Fri, Aug 16, 2024 at 03:43:54PM +0200, Alexey Gladkov wrote:
> From: "Alexey Gladkov (Intel)" <legion@kernel.org>
> 

I think this and 3 next patches do not belong to this patchset. They
address separate issue that is orthogonal to the patchset goal.

---

## [47] Alexey Gladkov — 2024-08-19
*Subject: Re: [PATCH v3 02/10] x86/tdx: Add validation of userspace MMIO
 instructions*

On Mon, Aug 19, 2024 at 01:39:17PM +0300, Kirill A. Shutemov wrote:
> On Fri, Aug 16, 2024 at 03:43:52PM +0200, Alexey Gladkov wrote:
> > From: "Alexey Gladkov (Intel)" <legion@kernel.org>

We also check that the memory access (read/write) type matches. Yes, we
can't check the instruction itself, but we check the arguments.

> > 
> > Once the userspace instruction parsed is enforced that the address

(ve->gpa != cc_mkdec(phys_addr)

The ve->gpa was checked in the virt_exception_user/kernel().

> 
> > Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>

All patches pass checkpatch without warnings.

> 
> > +		return -EAGAIN;

The kthread do not have a current->mm. As an example:

https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/vfio/vfio_iommu_type1.c#n3053

Also documentation mention this as the way to check a user context:

  (which makes more sense anyway - the test is basically one of "do
  we have a user context", and is generally done by the page fault
  handler and things like that).

https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/Documentation/mm/active_mm.rst#n80

> Use user_mode(regs) instead.

I can't use this. When nested exception happens in the handle_mmio_movs()
the regs will be not in the user mode.

I can make a flag that will be set either for user_mode or if we have a
nested exception.

> > +		if (mmap_read_lock_killable(current->mm))
> > +			return -EINTR;

---

## [48] Alexey Gladkov — 2024-08-19
*Subject: Re: [PATCH v3 03/10] x86/tdx: Allow MMIO from userspace*

On Mon, Aug 19, 2024 at 01:46:34PM +0300, Kirill A. Shutemov wrote:
> On Fri, Aug 16, 2024 at 03:43:53PM +0200, Alexey Gladkov wrote:
> > From: "Alexey Gladkov (Intel)" <legion@kernel.org>

No. I removed it because the patch changed a lot after his review. I
didn't want to mislead anyone.

---

## [49] Alexey Gladkov — 2024-08-19
*Subject: Re: [PATCH v3 04/10] x86/insn: Read and decode insn without crossing
 the page boundary*

On Mon, Aug 19, 2024 at 01:48:11PM +0300, Kirill A. Shutemov wrote:
> On Fri, Aug 16, 2024 at 03:43:54PM +0200, Alexey Gladkov wrote:
> > From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Should I drop them from this patchset and send them after this patchset as
a separate change ?

---

## [50] Kirill A. Shutemov — 2024-08-19
*Subject: Re: [PATCH v3 02/10] x86/tdx: Add validation of userspace MMIO
 instructions*

On Mon, Aug 19, 2024 at 01:48:16PM +0200, Alexey Gladkov wrote:
> On Mon, Aug 19, 2024 at 01:39:17PM +0300, Kirill A. Shutemov wrote:
> > On Fri, Aug 16, 2024 at 03:43:52PM +0200, Alexey Gladkov wrote:

phys_addr doesn't have shared bit. It is masked out on pte_pfn(). That's
the reason you use cc_mkdec() to compare with ve->gpa. Otherwise it would
fail.

> 
> > 

Checkpatch is not the ultimate authority. But I am neither. :P

> > 
> > > +		return -EAGAIN;

I am not talking about kthread. I am talking about initiating MMIO from
kernel, but within a process context. Like, you call an ioctl() on a
device fd and it triggers MMIO in kernel. This scenario would have
current->mm, but it is not userspace MMIO.

> > Use user_mode(regs) instead.
> 

Hm. Yeah. This is ugly. Let me think about it.

---

## [51] Kirill A. Shutemov — 2024-08-19
*Subject: Re: [PATCH v3 04/10] x86/insn: Read and decode insn without crossing
 the page boundary*

On Mon, Aug 19, 2024 at 01:56:05PM +0200, Alexey Gladkov wrote:
> On Mon, Aug 19, 2024 at 01:48:11PM +0300, Kirill A. Shutemov wrote:
> > On Fri, Aug 16, 2024 at 03:43:54PM +0200, Alexey Gladkov wrote:

Yeah. I think so.

---

## [52] Alexey Gladkov — 2024-08-19
*Subject: Re: [PATCH v3 02/10] x86/tdx: Add validation of userspace MMIO
 instructions*

On Mon, Aug 19, 2024 at 03:07:50PM +0300, Kirill A. Shutemov wrote:
> On Mon, Aug 19, 2024 at 01:48:16PM +0200, Alexey Gladkov wrote:
> > On Mon, Aug 19, 2024 at 01:39:17PM +0300, Kirill A. Shutemov wrote:

Ok. I think I've confused myself. I will add pte_decrypted(). 

> 
> > 

Ok. I will use user_mode here and in the movs patch I will add a special
flag to perform checks in case of nested exceptions.

> > > Use user_mode(regs) instead.
> > 

Yes, it's not very good.

---

## [53] Alexey Gladkov — 2024-08-21
*Subject: [PATCH v4 0/6] x86/tdx: Allow MMIO instructions from userspace*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Currently, MMIO inside the TDX guest is allowed from kernel space and access
from userspace is denied. This becomes a problem when working with virtual
devices in userspace.

In TDX guest MMIO instructions are emulated in #VE. The kernel code uses special
helpers to access MMIO memory to limit the number of instructions which are
used.

This patchset makes MMIO accessible from userspace. To do this additional checks
were added to ensure that the emulated instruction will not be compromised.


v4:
- Move patches to avoid crossing the page boundary to separate patchset. They
  address separate issue.
- Check the address only in user context and in case of nested exceptions.
- Fix the check that the address does not point to private memory.

v3:
- Add patches to avoid crossing the page boundary when the instruction is read
  and decoded in the TDX, SEV, UMIP.
- Forbid accessing userspace addresses from kernel space. The exception to this
  is when emulating MOVS instructions.
- Fix address validation during MOVS emulation.

v2:
- Split into separate patches AMD helpers extraction and MOVS implementation
  code for intel as suggested by Thomas Gleixner.
- Fix coding style issues.


Alexey Gladkov (Intel) (6):
  x86/tdx: Split MMIO read and write operations
  x86/tdx: Add validation of userspace MMIO instructions
  x86/tdx: Allow MMIO from userspace
  x86/tdx: Add a restriction on access to MMIO address
  x86/tdx: Move MMIO helpers to common library
  x86/tdx: Implement movs for MMIO

 arch/x86/coco/sev/core.c         | 135 ++----------
 arch/x86/coco/tdx/tdx.c          | 340 ++++++++++++++++++++++++++-----
 arch/x86/include/asm/io.h        |   3 +
 arch/x86/include/asm/processor.h |   4 +
 arch/x86/lib/iomem.c             | 125 ++++++++++++
 5 files changed, 434 insertions(+), 173 deletions(-)

---

## [54] Alexey Gladkov — 2024-08-21
*Subject: [PATCH v4 1/6] x86/tdx: Split MMIO read and write operations*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

To implement MMIO in userspace, additional memory checks need to be
implemented. To avoid overly complicating the handle_mmio() function
and to separate checks from actions, it would be better to split this
function into two separate functions to handle read and write
operations.

Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 136 ++++++++++++++++++++++++----------------
 1 file changed, 83 insertions(+), 53 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 078e2bac2553..af0b6c1cacf7 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -405,14 +405,91 @@ static bool mmio_write(int size, unsigned long addr, unsigned long val)
 			       EPT_WRITE, addr, val);
 }
 
+static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
+			     struct pt_regs *regs, struct ve_info *ve)
+{
+	unsigned long *reg, val;
+
+	switch (mmio) {
+	case INSN_MMIO_WRITE:
+		reg = insn_get_modrm_reg_ptr(insn, regs);
+		if (!reg)
+			return -EINVAL;
+		memcpy(&val, reg, size);
+		if (!mmio_write(size, ve->gpa, val))
+			return -EIO;
+		return insn->length;
+	case INSN_MMIO_WRITE_IMM:
+		val = insn->immediate.value;
+		if (!mmio_write(size, ve->gpa, val))
+			return -EIO;
+		return insn->length;
+	case INSN_MMIO_MOVS:
+		/*
+		 * MMIO was accessed with an instruction that could not be
+		 * decoded or handled properly. It was likely not using io.h
+		 * helpers or accessed MMIO accidentally.
+		 */
+		return -EINVAL;
+	default:
+		WARN_ON_ONCE(1);
+		return -EINVAL;
+	}
+
+	return insn->length;
+}
+
+static int handle_mmio_read(struct insn *insn, enum insn_mmio_type mmio, int size,
+			    struct pt_regs *regs, struct ve_info *ve)
+{
+	unsigned long *reg, val;
+	int extend_size;
+	u8 extend_val;
+
+	reg = insn_get_modrm_reg_ptr(insn, regs);
+	if (!reg)
+		return -EINVAL;
+
+	if (!mmio_read(size, ve->gpa, &val))
+		return -EIO;
+
+	extend_val = 0;
+
+	switch (mmio) {
+	case INSN_MMIO_READ:
+		/* Zero-extend for 32-bit operation */
+		extend_size = size == 4 ? sizeof(*reg) : 0;
+		break;
+	case INSN_MMIO_READ_ZERO_EXTEND:
+		/* Zero extend based on operand size */
+		extend_size = insn->opnd_bytes;
+		break;
+	case INSN_MMIO_READ_SIGN_EXTEND:
+		/* Sign extend based on operand size */
+		extend_size = insn->opnd_bytes;
+		if (size == 1 && val & BIT(7))
+			extend_val = 0xFF;
+		else if (size > 1 && val & BIT(15))
+			extend_val = 0xFF;
+		break;
+	default:
+		WARN_ON_ONCE(1);
+		return -EINVAL;
+	}
+
+	if (extend_size)
+		memset(reg, extend_val, extend_size);
+	memcpy(reg, &val, size);
+	return insn->length;
+}
+
 static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 {
-	unsigned long *reg, val, vaddr;
 	char buffer[MAX_INSN_SIZE];
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
-	int size, extend_size;
-	u8 extend_val = 0;
+	unsigned long vaddr;
+	int size;
 
 	/* Only in-kernel MMIO is supported */
 	if (WARN_ON_ONCE(user_mode(regs)))
@@ -428,12 +505,6 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
-	if (mmio != INSN_MMIO_WRITE_IMM && mmio != INSN_MMIO_MOVS) {
-		reg = insn_get_modrm_reg_ptr(&insn, regs);
-		if (!reg)
-			return -EINVAL;
-	}
-
 	/*
 	 * Reject EPT violation #VEs that split pages.
 	 *
@@ -447,24 +518,15 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (vaddr / PAGE_SIZE != (vaddr + size - 1) / PAGE_SIZE)
 		return -EFAULT;
 
-	/* Handle writes first */
 	switch (mmio) {
 	case INSN_MMIO_WRITE:
-		memcpy(&val, reg, size);
-		if (!mmio_write(size, ve->gpa, val))
-			return -EIO;
-		return insn.length;
 	case INSN_MMIO_WRITE_IMM:
-		val = insn.immediate.value;
-		if (!mmio_write(size, ve->gpa, val))
-			return -EIO;
-		return insn.length;
+	case INSN_MMIO_MOVS:
+		return handle_mmio_write(&insn, mmio, size, regs, ve);
 	case INSN_MMIO_READ:
 	case INSN_MMIO_READ_ZERO_EXTEND:
 	case INSN_MMIO_READ_SIGN_EXTEND:
-		/* Reads are handled below */
-		break;
-	case INSN_MMIO_MOVS:
+		return handle_mmio_read(&insn, mmio, size, regs, ve);
 	case INSN_MMIO_DECODE_FAILED:
 		/*
 		 * MMIO was accessed with an instruction that could not be
@@ -476,38 +538,6 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 		WARN_ONCE(1, "Unknown insn_decode_mmio() decode value?");
 		return -EINVAL;
 	}
-
-	/* Handle reads */
-	if (!mmio_read(size, ve->gpa, &val))
-		return -EIO;
-
-	switch (mmio) {
-	case INSN_MMIO_READ:
-		/* Zero-extend for 32-bit operation */
-		extend_size = size == 4 ? sizeof(*reg) : 0;
-		break;
-	case INSN_MMIO_READ_ZERO_EXTEND:
-		/* Zero extend based on operand size */
-		extend_size = insn.opnd_bytes;
-		break;
-	case INSN_MMIO_READ_SIGN_EXTEND:
-		/* Sign extend based on operand size */
-		extend_size = insn.opnd_bytes;
-		if (size == 1 && val & BIT(7))
-			extend_val = 0xFF;
-		else if (size > 1 && val & BIT(15))
-			extend_val = 0xFF;
-		break;
-	default:
-		/* All other cases has to be covered with the first switch() */
-		WARN_ON_ONCE(1);
-		return -EINVAL;
-	}
-
-	if (extend_size)
-		memset(reg, extend_val, extend_size);
-	memcpy(reg, &val, size);
-	return insn.length;
 }
 
 static bool handle_in(struct pt_regs *regs, int size, int port)

---

## [55] Alexey Gladkov — 2024-08-21
*Subject: [PATCH v4 2/6] x86/tdx: Add validation of userspace MMIO instructions*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Instructions from kernel space are considered trusted. If the MMIO
instruction is from userspace it must be checked.

For userspace instructions, it is need to check that the INSN has not
changed at the time of #VE and before the execution of the instruction.

Once the userspace instruction parsed is enforced that the address
points to mapped memory of current process and that address does not
point to private memory.

After parsing the userspace instruction, it is necessary to ensure that:

1. the operation direction (read/write) corresponds to #VE info;
2. the address still points to mapped memory of current process;
3. the address does not point to private memory.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 131 ++++++++++++++++++++++++++++++++++++----
 1 file changed, 118 insertions(+), 13 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index af0b6c1cacf7..99634e12f9a7 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -8,6 +8,7 @@
 #include <linux/export.h>
 #include <linux/io.h>
 #include <linux/kexec.h>
+#include <linux/mm.h>
 #include <asm/coco.h>
 #include <asm/tdx.h>
 #include <asm/vmx.h>
@@ -405,6 +406,87 @@ static bool mmio_write(int size, unsigned long addr, unsigned long val)
 			       EPT_WRITE, addr, val);
 }
 
+static inline bool is_private_gpa(u64 gpa)
+{
+	return gpa == cc_mkenc(gpa);
+}
+
+static int get_phys_addr(unsigned long addr, phys_addr_t *phys_addr, bool *writable)
+{
+	unsigned int level;
+	pgd_t *pgdp;
+	pte_t *ptep;
+
+	/*
+	 * Address validation only makes sense for a user process. The lock must
+	 * be obtained before validation can begin.
+	 */
+	mmap_assert_locked(current->mm);
+
+	pgdp = pgd_offset(current->mm, addr);
+
+	if (!pgd_none(*pgdp)) {
+		ptep = lookup_address_in_pgd(pgdp, addr, &level);
+		if (ptep) {
+			unsigned long offset;
+
+			if (!pte_decrypted(*ptep))
+				return -EFAULT;
+
+			offset = addr & ~page_level_mask(level);
+			*phys_addr = PFN_PHYS(pte_pfn(*ptep));
+			*phys_addr |= offset;
+
+			*writable = pte_write(*ptep);
+
+			return 0;
+		}
+	}
+
+	return -EFAULT;
+}
+
+static int valid_vaddr(struct ve_info *ve, enum insn_mmio_type mmio, int size,
+		       unsigned long vaddr)
+{
+	phys_addr_t phys_addr;
+	bool writable = false;
+
+	/* It's not fatal. This can happen due to swap out or page migration. */
+	if (get_phys_addr(vaddr, &phys_addr, &writable) || (ve->gpa != cc_mkdec(phys_addr)))
+		return -EAGAIN;
+
+	/*
+	 * Re-check whether #VE info matches the instruction that was decoded.
+	 *
+	 * The ve->gpa was valid at the time ve_info was received. But this code
+	 * executed with interrupts enabled, allowing tlb shootdown and therefore
+	 * munmap() to be executed in the parallel thread.
+	 *
+	 * By the time MMIO emulation is performed, ve->gpa may be already
+	 * unmapped from the process, the device it belongs to removed from
+	 * system and something else could be plugged in its place.
+	 */
+	switch (mmio) {
+	case INSN_MMIO_WRITE:
+	case INSN_MMIO_WRITE_IMM:
+		if (!writable || !(ve->exit_qual & EPT_VIOLATION_ACC_WRITE))
+			return -EFAULT;
+		break;
+	case INSN_MMIO_READ:
+	case INSN_MMIO_READ_ZERO_EXTEND:
+	case INSN_MMIO_READ_SIGN_EXTEND:
+		if (!(ve->exit_qual & EPT_VIOLATION_ACC_READ))
+			return -EFAULT;
+		break;
+	default:
+		WARN_ONCE(1, "Unsupported mmio instruction: %d", mmio);
+		return -EINVAL;
+	}
+
+	return 0;
+}
+
 static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
 			     struct pt_regs *regs, struct ve_info *ve)
 {
@@ -489,7 +571,7 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
 	unsigned long vaddr;
-	int size;
+	int size, ret;
 
 	/* Only in-kernel MMIO is supported */
 	if (WARN_ON_ONCE(user_mode(regs)))
@@ -505,6 +587,17 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
+	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
+
+	if (user_mode(regs)) {
+		if (mmap_read_lock_killable(current->mm))
+			return -EINTR;
+
+		ret = valid_vaddr(ve, mmio, size, vaddr);
+		if (ret)
+			goto unlock;
+	}
+
 	/*
 	 * Reject EPT violation #VEs that split pages.
 	 *
@@ -514,30 +607,39 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	 *
 	 * load_unaligned_zeropad() will recover using exception fixups.
 	 */
-	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
-	if (vaddr / PAGE_SIZE != (vaddr + size - 1) / PAGE_SIZE)
-		return -EFAULT;
+	if (vaddr / PAGE_SIZE != (vaddr + size - 1) / PAGE_SIZE) {
+		ret = -EFAULT;
+		goto unlock;
+	}
 
 	switch (mmio) {
 	case INSN_MMIO_WRITE:
 	case INSN_MMIO_WRITE_IMM:
 	case INSN_MMIO_MOVS:
-		return handle_mmio_write(&insn, mmio, size, regs, ve);
+		ret = handle_mmio_write(&insn, mmio, size, regs, ve);
+		break;
 	case INSN_MMIO_READ:
 	case INSN_MMIO_READ_ZERO_EXTEND:
 	case INSN_MMIO_READ_SIGN_EXTEND:
-		return handle_mmio_read(&insn, mmio, size, regs, ve);
+		ret = handle_mmio_read(&insn, mmio, size, regs, ve);
+		break;
 	case INSN_MMIO_DECODE_FAILED:
 		/*
 		 * MMIO was accessed with an instruction that could not be
 		 * decoded or handled properly. It was likely not using io.h
 		 * helpers or accessed MMIO accidentally.
 		 */
-		return -EINVAL;
+		ret = -EINVAL;
+		break;
 	default:
 		WARN_ONCE(1, "Unknown insn_decode_mmio() decode value?");
-		return -EINVAL;
+		ret = -EINVAL;
 	}
+unlock:
+	if (user_mode(regs))
+		mmap_read_unlock(current->mm);
+
+	return ret;
 }
 
 static bool handle_in(struct pt_regs *regs, int size, int port)
@@ -681,11 +783,6 @@ static int virt_exception_user(struct pt_regs *regs, struct ve_info *ve)
 	}
 }
 
-static inline bool is_private_gpa(u64 gpa)
-{
-	return gpa == cc_mkenc(gpa);
-}
-
 /*
  * Handle the kernel #VE.
  *
@@ -723,6 +820,14 @@ bool tdx_handle_virt_exception(struct pt_regs *regs, struct ve_info *ve)
 		insn_len = virt_exception_user(regs, ve);
 	else
 		insn_len = virt_exception_kernel(regs, ve);
+
+	/*
+	 * A special case to return to userspace without increasing regs->ip
+	 * to repeat the instruction once again.
+	 */
+	if (insn_len == -EAGAIN)
+		return true;
+
 	if (insn_len < 0)
 		return false;

---

## [56] Alexey Gladkov — 2024-08-21
*Subject: [PATCH v4 3/6] x86/tdx: Allow MMIO from userspace*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

The MMIO emulation is only allowed for kernel space code. It is carried
out through a special API, which uses only certain instructions.

This does not allow userspace to work with virtual devices.

Allow userspace to use the same instructions as kernel space to access
MMIO. Additional checks have been added previously.

Reviewed-by: Thomas Gleixner <tglx@linutronix.de>
Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 43 +++++++++++++++++++++++++++++++----------
 1 file changed, 33 insertions(+), 10 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 99634e12f9a7..5d2d07aa08ce 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -487,6 +487,32 @@ static int valid_vaddr(struct ve_info *ve, enum insn_mmio_type mmio, int size,
 	return 0;
 }
 
+static int decode_insn_struct(struct insn *insn, struct pt_regs *regs)
+{
+	char buffer[MAX_INSN_SIZE];
+
+	if (user_mode(regs)) {
+		int nr_copied = insn_fetch_from_user(regs, buffer);
+
+		if (nr_copied <= 0)
+			return -EFAULT;
+
+		if (!insn_decode_from_regs(insn, regs, buffer, nr_copied))
+			return -EINVAL;
+	} else {
+		if (copy_from_kernel_nofault(buffer, (void *)regs->ip, MAX_INSN_SIZE))
+			return -EFAULT;
+
+		if (insn_decode(insn, buffer, MAX_INSN_SIZE, INSN_MODE_64))
+			return -EINVAL;
+	}
+
+	if (!insn->immediate.got)
+		return -EINVAL;
+
+	return 0;
+}
+
 static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
 			     struct pt_regs *regs, struct ve_info *ve)
 {
@@ -567,21 +593,14 @@ static int handle_mmio_read(struct insn *insn, enum insn_mmio_type mmio, int siz
 
 static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 {
-	char buffer[MAX_INSN_SIZE];
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
 	unsigned long vaddr;
 	int size, ret;
 
-	/* Only in-kernel MMIO is supported */
-	if (WARN_ON_ONCE(user_mode(regs)))
-		return -EFAULT;
-
-	if (copy_from_kernel_nofault(buffer, (void *)regs->ip, MAX_INSN_SIZE))
-		return -EFAULT;
-
-	if (insn_decode(&insn, buffer, MAX_INSN_SIZE, INSN_MODE_64))
-		return -EINVAL;
+	ret = decode_insn_struct(&insn, regs);
+	if (ret)
+		return ret;
 
 	mmio = insn_decode_mmio(&insn, &size);
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
@@ -777,6 +796,10 @@ static int virt_exception_user(struct pt_regs *regs, struct ve_info *ve)
 	switch (ve->exit_reason) {
 	case EXIT_REASON_CPUID:
 		return handle_cpuid(regs, ve);
+	case EXIT_REASON_EPT_VIOLATION:
+		if (is_private_gpa(ve->gpa))
+			panic("Unexpected EPT-violation on private memory.");
+		return handle_mmio(regs, ve);
 	default:
 		pr_warn("Unexpected #VE: %lld\n", ve->exit_reason);
 		return -EIO;

---

## [57] Alexey Gladkov — 2024-08-21
*Subject: [PATCH v4 4/6] x86/tdx: Add a restriction on access to MMIO address*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

In the case of userspace MMIO, if the user instruction + MAX_INSN_SIZE
straddles page, then the "fetch" in the kernel could trigger a #VE. In
this case the kernel would handle this second #VE as a !user_mode() MMIO.
That way, additional address verifications can be avoided.

The scenario of accessing userspace MMIO addresses from kernelspace does
not seem appropriate under normal circumstances. Until there is a
specific usecase for such a scenario it can be disabled.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 10 ++++++++++
 1 file changed, 10 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 5d2d07aa08ce..65f65015238a 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -411,6 +411,11 @@ static inline bool is_private_gpa(u64 gpa)
 	return gpa == cc_mkenc(gpa);
 }
 
+static inline bool is_kernel_addr(unsigned long addr)
+{
+	return (long)addr < 0;
+}
+
 static int get_phys_addr(unsigned long addr, phys_addr_t *phys_addr, bool *writable)
 {
 	unsigned int level;
@@ -606,6 +611,11 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
+	if (!user_mode(regs) && !is_kernel_addr(ve->gla)) {
+		WARN_ONCE(1, "Access to userspace address is not supported");
+		return -EINVAL;
+	}
+
 	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
 
 	if (user_mode(regs)) {

---

## [58] Alexey Gladkov — 2024-08-21
*Subject: [PATCH v4 5/6] x86/tdx: Move MMIO helpers to common library*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

AMD code has helpers that are used to emulate MOVS instructions. To be
able to reuse this code in the MOVS implementation for intel, it is
necessary to move them to a common location.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/sev/core.c  | 135 ++++----------------------------------
 arch/x86/include/asm/io.h |   3 +
 arch/x86/lib/iomem.c      | 125 +++++++++++++++++++++++++++++++++++
 3 files changed, 142 insertions(+), 121 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 082d61d85dfc..0e10c22c5347 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -369,72 +369,18 @@ static enum es_result vc_decode_insn(struct es_em_ctxt *ctxt)
 static enum es_result vc_write_mem(struct es_em_ctxt *ctxt,
 				   char *dst, char *buf, size_t size)
 {
-	unsigned long error_code = X86_PF_PROT | X86_PF_WRITE;
-
-	/*
-	 * This function uses __put_user() independent of whether kernel or user
-	 * memory is accessed. This works fine because __put_user() does no
-	 * sanity checks of the pointer being accessed. All that it does is
-	 * to report when the access failed.
-	 *
-	 * Also, this function runs in atomic context, so __put_user() is not
-	 * allowed to sleep. The page-fault handler detects that it is running
-	 * in atomic context and will not try to take mmap_sem and handle the
-	 * fault, so additional pagefault_enable()/disable() calls are not
-	 * needed.
-	 *
-	 * The access can't be done via copy_to_user() here because
-	 * vc_write_mem() must not use string instructions to access unsafe
-	 * memory. The reason is that MOVS is emulated by the #VC handler by
-	 * splitting the move up into a read and a write and taking a nested #VC
-	 * exception on whatever of them is the MMIO access. Using string
-	 * instructions here would cause infinite nesting.
-	 */
-	switch (size) {
-	case 1: {
-		u8 d1;
-		u8 __user *target = (u8 __user *)dst;
-
-		memcpy(&d1, buf, 1);
-		if (__put_user(d1, target))
-			goto fault;
-		break;
-	}
-	case 2: {
-		u16 d2;
-		u16 __user *target = (u16 __user *)dst;
-
-		memcpy(&d2, buf, 2);
-		if (__put_user(d2, target))
-			goto fault;
-		break;
-	}
-	case 4: {
-		u32 d4;
-		u32 __user *target = (u32 __user *)dst;
+	unsigned long error_code;
+	int ret;
 
-		memcpy(&d4, buf, 4);
-		if (__put_user(d4, target))
-			goto fault;
-		break;
-	}
-	case 8: {
-		u64 d8;
-		u64 __user *target = (u64 __user *)dst;
+	ret = __put_iomem(dst, buf, size);
+	if (!ret)
+		return ES_OK;
 
-		memcpy(&d8, buf, 8);
-		if (__put_user(d8, target))
-			goto fault;
-		break;
-	}
-	default:
-		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+	if (ret == -EIO)
 		return ES_UNSUPPORTED;
-	}
 
-	return ES_OK;
+	error_code = X86_PF_PROT | X86_PF_WRITE;
 
-fault:
 	if (user_mode(ctxt->regs))
 		error_code |= X86_PF_USER;
 
@@ -448,71 +394,18 @@ static enum es_result vc_write_mem(struct es_em_ctxt *ctxt,
 static enum es_result vc_read_mem(struct es_em_ctxt *ctxt,
 				  char *src, char *buf, size_t size)
 {
-	unsigned long error_code = X86_PF_PROT;
-
-	/*
-	 * This function uses __get_user() independent of whether kernel or user
-	 * memory is accessed. This works fine because __get_user() does no
-	 * sanity checks of the pointer being accessed. All that it does is
-	 * to report when the access failed.
-	 *
-	 * Also, this function runs in atomic context, so __get_user() is not
-	 * allowed to sleep. The page-fault handler detects that it is running
-	 * in atomic context and will not try to take mmap_sem and handle the
-	 * fault, so additional pagefault_enable()/disable() calls are not
-	 * needed.
-	 *
-	 * The access can't be done via copy_from_user() here because
-	 * vc_read_mem() must not use string instructions to access unsafe
-	 * memory. The reason is that MOVS is emulated by the #VC handler by
-	 * splitting the move up into a read and a write and taking a nested #VC
-	 * exception on whatever of them is the MMIO access. Using string
-	 * instructions here would cause infinite nesting.
-	 */
-	switch (size) {
-	case 1: {
-		u8 d1;
-		u8 __user *s = (u8 __user *)src;
-
-		if (__get_user(d1, s))
-			goto fault;
-		memcpy(buf, &d1, 1);
-		break;
-	}
-	case 2: {
-		u16 d2;
-		u16 __user *s = (u16 __user *)src;
+	unsigned long error_code;
+	int ret;
 
-		if (__get_user(d2, s))
-			goto fault;
-		memcpy(buf, &d2, 2);
-		break;
-	}
-	case 4: {
-		u32 d4;
-		u32 __user *s = (u32 __user *)src;
+	ret = __get_iomem(src, buf, size);
+	if (!ret)
+		return ES_OK;
 
-		if (__get_user(d4, s))
-			goto fault;
-		memcpy(buf, &d4, 4);
-		break;
-	}
-	case 8: {
-		u64 d8;
-		u64 __user *s = (u64 __user *)src;
-		if (__get_user(d8, s))
-			goto fault;
-		memcpy(buf, &d8, 8);
-		break;
-	}
-	default:
-		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+	if (ret == -EIO)
 		return ES_UNSUPPORTED;
-	}
 
-	return ES_OK;
+	error_code = X86_PF_PROT;
 
-fault:
 	if (user_mode(ctxt->regs))
 		error_code |= X86_PF_USER;
 
diff --git a/arch/x86/include/asm/io.h b/arch/x86/include/asm/io.h
index 1d60427379c9..ac01d53466cb 100644
--- a/arch/x86/include/asm/io.h
+++ b/arch/x86/include/asm/io.h
@@ -402,4 +402,7 @@ static inline void iosubmit_cmds512(void __iomem *dst, const void *src,
 	}
 }
 
+int __get_iomem(char *src, char *buf, size_t size);
+int __put_iomem(char *src, char *buf, size_t size);
+
 #endif /* _ASM_X86_IO_H */
diff --git a/arch/x86/lib/iomem.c b/arch/x86/lib/iomem.c
index 5eecb45d05d5..23179953eb5a 100644
--- a/arch/x86/lib/iomem.c
+++ b/arch/x86/lib/iomem.c
@@ -2,6 +2,7 @@
 #include <linux/module.h>
 #include <linux/io.h>
 #include <linux/kmsan-checks.h>
+#include <asm/uaccess.h>
 
 #define movs(type,to,from) \
 	asm volatile("movs" type:"=&D" (to), "=&S" (from):"0" (to), "1" (from):"memory")
@@ -124,3 +125,127 @@ void memset_io(volatile void __iomem *a, int b, size_t c)
 	}
 }
 EXPORT_SYMBOL(memset_io);
+
+int __get_iomem(char *src, char *buf, size_t size)
+{
+	/*
+	 * This function uses __get_user() independent of whether kernel or user
+	 * memory is accessed. This works fine because __get_user() does no
+	 * sanity checks of the pointer being accessed. All that it does is
+	 * to report when the access failed.
+	 *
+	 * Also, this function runs in atomic context, so __get_user() is not
+	 * allowed to sleep. The page-fault handler detects that it is running
+	 * in atomic context and will not try to take mmap_sem and handle the
+	 * fault, so additional pagefault_enable()/disable() calls are not
+	 * needed.
+	 *
+	 * The access can't be done via copy_from_user() here because
+	 * mmio_read_mem() must not use string instructions to access unsafe
+	 * memory. The reason is that MOVS is emulated by the #VC handler by
+	 * splitting the move up into a read and a write and taking a nested #VC
+	 * exception on whatever of them is the MMIO access. Using string
+	 * instructions here would cause infinite nesting.
+	 */
+	switch (size) {
+	case 1: {
+		u8 d1, __user *s = (u8 __user *)src;
+
+		if (__get_user(d1, s))
+			return -EFAULT;
+		memcpy(buf, &d1, 1);
+		break;
+	}
+	case 2: {
+		u16 d2, __user *s = (u16 __user *)src;
+
+		if (__get_user(d2, s))
+			return -EFAULT;
+		memcpy(buf, &d2, 2);
+		break;
+	}
+	case 4: {
+		u32 d4, __user *s = (u32 __user *)src;
+
+		if (__get_user(d4, s))
+			return -EFAULT;
+		memcpy(buf, &d4, 4);
+		break;
+	}
+	case 8: {
+		u64 d8, __user *s = (u64 __user *)src;
+
+		if (__get_user(d8, s))
+			return -EFAULT;
+		memcpy(buf, &d8, 8);
+		break;
+	}
+	default:
+		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+		return -EIO;
+	}
+
+	return 0;
+}
+
+int __put_iomem(char *dst, char *buf, size_t size)
+{
+	/*
+	 * This function uses __put_user() independent of whether kernel or user
+	 * memory is accessed. This works fine because __put_user() does no
+	 * sanity checks of the pointer being accessed. All that it does is
+	 * to report when the access failed.
+	 *
+	 * Also, this function runs in atomic context, so __put_user() is not
+	 * allowed to sleep. The page-fault handler detects that it is running
+	 * in atomic context and will not try to take mmap_sem and handle the
+	 * fault, so additional pagefault_enable()/disable() calls are not
+	 * needed.
+	 *
+	 * The access can't be done via copy_to_user() here because
+	 * put_iomem() must not use string instructions to access unsafe
+	 * memory. The reason is that MOVS is emulated by the #VC handler by
+	 * splitting the move up into a read and a write and taking a nested #VC
+	 * exception on whatever of them is the MMIO access. Using string
+	 * instructions here would cause infinite nesting.
+	 */
+	switch (size) {
+	case 1: {
+		u8 d1, __user *target = (u8 __user *)dst;
+
+		memcpy(&d1, buf, 1);
+		if (__put_user(d1, target))
+			return -EFAULT;
+		break;
+	}
+	case 2: {
+		u16 d2, __user *target = (u16 __user *)dst;
+
+		memcpy(&d2, buf, 2);
+		if (__put_user(d2, target))
+			return -EFAULT;
+		break;
+	}
+	case 4: {
+		u32 d4, __user *target = (u32 __user *)dst;
+
+		memcpy(&d4, buf, 4);
+		if (__put_user(d4, target))
+			return -EFAULT;
+		break;
+	}
+	case 8: {
+		u64 d8, __user *target = (u64 __user *)dst;
+
+		memcpy(&d8, buf, 8);
+		if (__put_user(d8, target))
+			return -EFAULT;
+		break;
+	}
+	default:
+		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+		return -EIO;
+	}
+
+	return 0;
+}

---

## [59] Alexey Gladkov — 2024-08-21
*Subject: [PATCH v4 6/6] x86/tdx: Implement movs for MMIO*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Add emulation of the MOVS instruction on MMIO regions. MOVS emulation
consists of dividing it into a series of read and write operations,
which in turn will be validated separately.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c          | 84 +++++++++++++++++++++++++++++---
 arch/x86/include/asm/processor.h |  4 ++
 2 files changed, 80 insertions(+), 8 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 65f65015238a..d4bec84de034 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -518,6 +518,62 @@ static int decode_insn_struct(struct insn *insn, struct pt_regs *regs)
 	return 0;
 }
 
+static int handle_mmio_movs(struct insn *insn, struct pt_regs *regs, int size, struct ve_info *ve)
+{
+	unsigned long ds_base, es_base;
+	unsigned char *src, *dst;
+	unsigned char buffer[8];
+	int off, ret;
+	bool rep;
+
+	/*
+	 * The in-kernel code must use a special API that does not use MOVS.
+	 * If the MOVS instruction is received from in-kernel, then something
+	 * is broken.
+	 */
+	if (WARN_ON_ONCE(!user_mode(regs)))
+		return -EFAULT;
+
+	ds_base = insn_get_seg_base(regs, INAT_SEG_REG_DS);
+	es_base = insn_get_seg_base(regs, INAT_SEG_REG_ES);
+
+	if (ds_base == -1L || es_base == -1L)
+		return -EINVAL;
+
+	rep = insn_has_rep_prefix(insn);
+
+	do {
+		src = ds_base + (unsigned char *) regs->si;
+		dst = es_base + (unsigned char *) regs->di;
+
+		current->thread.mmio_emul = (unsigned long) src;
+
+		ret = __get_iomem(src, buffer, size);
+		if (ret)
+			goto out;
+
+		current->thread.mmio_emul = (unsigned long) dst;
+
+		ret = __put_iomem(dst, buffer, size);
+		if (ret)
+			goto out;
+
+		off = (regs->flags & X86_EFLAGS_DF) ? -size : size;
+
+		regs->si += off;
+		regs->di += off;
+
+		if (rep)
+			regs->cx -= 1;
+	} while (rep || regs->cx > 0);
+
+	ret = insn->length;
+out:
+	current->thread.mmio_emul = 0;
+
+	return ret;
+}
+
 static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
 			     struct pt_regs *regs, struct ve_info *ve)
 {
@@ -539,9 +595,8 @@ static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int si
 		return insn->length;
 	case INSN_MMIO_MOVS:
 		/*
-		 * MMIO was accessed with an instruction that could not be
-		 * decoded or handled properly. It was likely not using io.h
-		 * helpers or accessed MMIO accidentally.
+		 * MOVS is processed through higher level emulation which breaks
+		 * this instruction into a sequence of reads and writes.
 		 */
 		return -EINVAL;
 	default:
@@ -600,6 +655,7 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 {
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
+	int need_validation;
 	unsigned long vaddr;
 	int size, ret;
 
@@ -611,14 +667,27 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
+	if (mmio == INSN_MMIO_MOVS)
+		return handle_mmio_movs(&insn, regs, size, ve);
+
+	need_validation = user_mode(regs);
+
 	if (!user_mode(regs) && !is_kernel_addr(ve->gla)) {
-		WARN_ONCE(1, "Access to userspace address is not supported");
-		return -EINVAL;
+		/*
+		 * Access from kernel to userspace addresses is not allowed
+		 * unless it is a nested exception during MOVS emulation.
+		 */
+		if (current->thread.mmio_emul != ve->gla || !current->mm) {
+			WARN_ONCE(1, "Access to userspace address is not supported");
+			return -EINVAL;
+		}
+
+		need_validation = 1;
 	}
 
 	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
 
-	if (user_mode(regs)) {
+	if (need_validation) {
 		if (mmap_read_lock_killable(current->mm))
 			return -EINTR;
 
@@ -644,7 +713,6 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	switch (mmio) {
 	case INSN_MMIO_WRITE:
 	case INSN_MMIO_WRITE_IMM:
-	case INSN_MMIO_MOVS:
 		ret = handle_mmio_write(&insn, mmio, size, regs, ve);
 		break;
 	case INSN_MMIO_READ:
@@ -665,7 +733,7 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 		ret = -EINVAL;
 	}
 unlock:
-	if (user_mode(regs))
+	if (need_validation)
 		mmap_read_unlock(current->mm);
 
 	return ret;
diff --git a/arch/x86/include/asm/processor.h b/arch/x86/include/asm/processor.h
index a75a07f4931f..45136b1b02cc 100644
--- a/arch/x86/include/asm/processor.h
+++ b/arch/x86/include/asm/processor.h
@@ -503,6 +503,10 @@ struct thread_struct {
 	struct thread_shstk	shstk;
 #endif
 
+#ifdef CONFIG_INTEL_TDX_GUEST
+	unsigned long		mmio_emul;
+#endif
+
 	/* Floating point and extended processor state */
 	struct fpu		fpu;
 	/*

---

## [60] Kirill A. Shutemov — 2024-08-22
*Subject: Re: [PATCH v4 2/6] x86/tdx: Add validation of userspace MMIO
 instructions*

On Wed, Aug 21, 2024 at 04:24:34PM +0200, Alexey Gladkov wrote:
> From: "Alexey Gladkov (Intel)" <legion@kernel.org>
> 

Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

---

## [61] Kirill A. Shutemov — 2024-08-22
*Subject: Re: [PATCH v4 3/6] x86/tdx: Allow MMIO from userspace*

On Wed, Aug 21, 2024 at 04:24:35PM +0200, Alexey Gladkov wrote:
> From: "Alexey Gladkov (Intel)" <legion@kernel.org>
> 

So, you've picked up Thomas' Reviwed-by, but lost mine? :P

---

## [62] Kirill A. Shutemov — 2024-08-22
*Subject: Re: [PATCH v4 4/6] x86/tdx: Add a restriction on access to MMIO
 address*

On Wed, Aug 21, 2024 at 04:24:36PM +0200, Alexey Gladkov wrote:
> From: "Alexey Gladkov (Intel)" <legion@kernel.org>
> 

It has nothing to do with "straddling page". It's about tricking kernel
into doing MMIO on user address.

For instance, if in response to a syscall, kernel does put_user() and the
target address is MMIO mapping in userspace, current #VE handler threat
this access as kernel MMIO which is wrong and have security implications.

> In
> this case the kernel would handle this second #VE as a !user_mode() MMIO.

Cc: stable@ please.

and this patch has to go ahead of the patchset, targeting x86/urgent
branch.

---

## [63] Kirill A. Shutemov — 2024-08-22
*Subject: Re: [PATCH v4 5/6] x86/tdx: Move MMIO helpers to common library*

On Wed, Aug 21, 2024 at 04:24:37PM +0200, Alexey Gladkov wrote:
> @@ -124,3 +125,127 @@ void memset_io(volatile void __iomem *a, int b, size_t c)
>  	}

This comment (and comment for __put_iomem()) has to be updated to be less
SEV-centric.

> +	 * This function uses __get_user() independent of whether kernel or user
> +	 * memory is accessed. This works fine because __get_user() does no

It is not going to be atomic context for TDX case.

> +	 * allowed to sleep. The page-fault handler detects that it is running
> +	 * in atomic context and will not try to take mmap_sem and handle the

#VC is SEV specific.

> +	 */

---

## [64] Kirill A. Shutemov — 2024-08-22
*Subject: Re: [PATCH v4 6/6] x86/tdx: Implement movs for MMIO*

On Wed, Aug 21, 2024 at 04:24:38PM +0200, Alexey Gladkov wrote:
> From: "Alexey Gladkov (Intel)" <legion@kernel.org>
> 

Please capitalize MOVS in the subject.

> Add emulation of the MOVS instruction on MMIO regions. MOVS emulation
> consists of dividing it into a series of read and write operations,

Commit message is pretty sparse. I think we need to elaborate on the
similarities and differences with SEV implementation. Locking context
difference is important.

> diff --git a/arch/x86/include/asm/processor.h b/arch/x86/include/asm/processor.h
> index a75a07f4931f..45136b1b02cc 100644

Hm. Do we need to track exact target address in the thread struct?
Wouldn't be single bit be enough to allow MMIO to userspace address from a
kernel regs->ip?

There is space for the flag next to iopl_warn.

---

## [65] Alexey Gladkov — 2024-08-24
*Subject: Re: [PATCH v4 6/6] x86/tdx: Implement movs for MMIO*

On Thu, Aug 22, 2024 at 11:28:14AM +0300, Kirill A. Shutemov wrote:
> On Wed, Aug 21, 2024 at 04:24:38PM +0200, Alexey Gladkov wrote:
> > From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Agree.

> > diff --git a/arch/x86/include/asm/processor.h b/arch/x86/include/asm/processor.h
> > index a75a07f4931f..45136b1b02cc 100644

The flag will identify that a nested exception happened, but it will not
be clear which address cause it.

Perhaps you are right and this approach is unnecessarily paranoid. 

> There is space for the flag next to iopl_warn.

Yes, I can use just a flag to identify a nested exception.

---

## [66] Alexey Gladkov — 2024-08-28
*Subject: [PATCH v5 0/6] x86/tdx: Allow MMIO instructions from userspace*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Currently, MMIO inside the TDX guest is allowed from kernel space and access
from userspace is denied. This becomes a problem when working with virtual
devices in userspace.

In TDX guest MMIO instructions are emulated in #VE. The kernel code uses special
helpers to access MMIO memory to limit the number of instructions which are
used.

This patchset makes MMIO accessible from userspace. To do this additional checks
were added to ensure that the emulated instruction will not be compromised.


v5:
- Improve commit messages and comments in commits as suggested by Kirill A. Shutemov.
- To emulate MOVS, instead of storing the entire address, started using a flag.

v4:
- Move patches to avoid crossing the page boundary to separate patchset. They
  address separate issue.
- Check the address only in user context and in case of nested exceptions.
- Fix the check that the address does not point to private memory.

v3:
- Add patches to avoid crossing the page boundary when the instruction is read
  and decoded in the TDX, SEV, UMIP.
- Forbid accessing userspace addresses from kernel space. The exception to this
  is when emulating MOVS instructions.
- Fix address validation during MOVS emulation.

v2:
- Split into separate patches AMD helpers extraction and MOVS implementation
  code for intel as suggested by Thomas Gleixner.
- Fix coding style issues.


Alexey Gladkov (Intel) (6):
  x86/tdx: Split MMIO read and write operations
  x86/tdx: Add validation of userspace MMIO instructions
  x86/tdx: Allow MMIO from userspace
  x86/tdx: Add a restriction on access to MMIO address
  x86/tdx: Move MMIO helpers to common library
  x86/tdx: Implement MOVS for MMIO

 arch/x86/coco/sev/core.c         | 139 ++-----------
 arch/x86/coco/tdx/tdx.c          | 338 ++++++++++++++++++++++++++-----
 arch/x86/include/asm/io.h        |   3 +
 arch/x86/include/asm/processor.h |   3 +
 arch/x86/lib/iomem.c             | 115 +++++++++++
 5 files changed, 429 insertions(+), 169 deletions(-)

---

## [67] Alexey Gladkov — 2024-08-28
*Subject: [PATCH v5 1/6] x86/tdx: Split MMIO read and write operations*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

To implement MMIO in userspace, additional memory checks need to be
implemented. To avoid overly complicating the handle_mmio() function
and to separate checks from actions, it would be better to split this
function into two separate functions to handle read and write
operations.

Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 136 ++++++++++++++++++++++++----------------
 1 file changed, 83 insertions(+), 53 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 078e2bac2553..af0b6c1cacf7 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -405,14 +405,91 @@ static bool mmio_write(int size, unsigned long addr, unsigned long val)
 			       EPT_WRITE, addr, val);
 }
 
+static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
+			     struct pt_regs *regs, struct ve_info *ve)
+{
+	unsigned long *reg, val;
+
+	switch (mmio) {
+	case INSN_MMIO_WRITE:
+		reg = insn_get_modrm_reg_ptr(insn, regs);
+		if (!reg)
+			return -EINVAL;
+		memcpy(&val, reg, size);
+		if (!mmio_write(size, ve->gpa, val))
+			return -EIO;
+		return insn->length;
+	case INSN_MMIO_WRITE_IMM:
+		val = insn->immediate.value;
+		if (!mmio_write(size, ve->gpa, val))
+			return -EIO;
+		return insn->length;
+	case INSN_MMIO_MOVS:
+		/*
+		 * MMIO was accessed with an instruction that could not be
+		 * decoded or handled properly. It was likely not using io.h
+		 * helpers or accessed MMIO accidentally.
+		 */
+		return -EINVAL;
+	default:
+		WARN_ON_ONCE(1);
+		return -EINVAL;
+	}
+
+	return insn->length;
+}
+
+static int handle_mmio_read(struct insn *insn, enum insn_mmio_type mmio, int size,
+			    struct pt_regs *regs, struct ve_info *ve)
+{
+	unsigned long *reg, val;
+	int extend_size;
+	u8 extend_val;
+
+	reg = insn_get_modrm_reg_ptr(insn, regs);
+	if (!reg)
+		return -EINVAL;
+
+	if (!mmio_read(size, ve->gpa, &val))
+		return -EIO;
+
+	extend_val = 0;
+
+	switch (mmio) {
+	case INSN_MMIO_READ:
+		/* Zero-extend for 32-bit operation */
+		extend_size = size == 4 ? sizeof(*reg) : 0;
+		break;
+	case INSN_MMIO_READ_ZERO_EXTEND:
+		/* Zero extend based on operand size */
+		extend_size = insn->opnd_bytes;
+		break;
+	case INSN_MMIO_READ_SIGN_EXTEND:
+		/* Sign extend based on operand size */
+		extend_size = insn->opnd_bytes;
+		if (size == 1 && val & BIT(7))
+			extend_val = 0xFF;
+		else if (size > 1 && val & BIT(15))
+			extend_val = 0xFF;
+		break;
+	default:
+		WARN_ON_ONCE(1);
+		return -EINVAL;
+	}
+
+	if (extend_size)
+		memset(reg, extend_val, extend_size);
+	memcpy(reg, &val, size);
+	return insn->length;
+}
+
 static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 {
-	unsigned long *reg, val, vaddr;
 	char buffer[MAX_INSN_SIZE];
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
-	int size, extend_size;
-	u8 extend_val = 0;
+	unsigned long vaddr;
+	int size;
 
 	/* Only in-kernel MMIO is supported */
 	if (WARN_ON_ONCE(user_mode(regs)))
@@ -428,12 +505,6 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
-	if (mmio != INSN_MMIO_WRITE_IMM && mmio != INSN_MMIO_MOVS) {
-		reg = insn_get_modrm_reg_ptr(&insn, regs);
-		if (!reg)
-			return -EINVAL;
-	}
-
 	/*
 	 * Reject EPT violation #VEs that split pages.
 	 *
@@ -447,24 +518,15 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (vaddr / PAGE_SIZE != (vaddr + size - 1) / PAGE_SIZE)
 		return -EFAULT;
 
-	/* Handle writes first */
 	switch (mmio) {
 	case INSN_MMIO_WRITE:
-		memcpy(&val, reg, size);
-		if (!mmio_write(size, ve->gpa, val))
-			return -EIO;
-		return insn.length;
 	case INSN_MMIO_WRITE_IMM:
-		val = insn.immediate.value;
-		if (!mmio_write(size, ve->gpa, val))
-			return -EIO;
-		return insn.length;
+	case INSN_MMIO_MOVS:
+		return handle_mmio_write(&insn, mmio, size, regs, ve);
 	case INSN_MMIO_READ:
 	case INSN_MMIO_READ_ZERO_EXTEND:
 	case INSN_MMIO_READ_SIGN_EXTEND:
-		/* Reads are handled below */
-		break;
-	case INSN_MMIO_MOVS:
+		return handle_mmio_read(&insn, mmio, size, regs, ve);
 	case INSN_MMIO_DECODE_FAILED:
 		/*
 		 * MMIO was accessed with an instruction that could not be
@@ -476,38 +538,6 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 		WARN_ONCE(1, "Unknown insn_decode_mmio() decode value?");
 		return -EINVAL;
 	}
-
-	/* Handle reads */
-	if (!mmio_read(size, ve->gpa, &val))
-		return -EIO;
-
-	switch (mmio) {
-	case INSN_MMIO_READ:
-		/* Zero-extend for 32-bit operation */
-		extend_size = size == 4 ? sizeof(*reg) : 0;
-		break;
-	case INSN_MMIO_READ_ZERO_EXTEND:
-		/* Zero extend based on operand size */
-		extend_size = insn.opnd_bytes;
-		break;
-	case INSN_MMIO_READ_SIGN_EXTEND:
-		/* Sign extend based on operand size */
-		extend_size = insn.opnd_bytes;
-		if (size == 1 && val & BIT(7))
-			extend_val = 0xFF;
-		else if (size > 1 && val & BIT(15))
-			extend_val = 0xFF;
-		break;
-	default:
-		/* All other cases has to be covered with the first switch() */
-		WARN_ON_ONCE(1);
-		return -EINVAL;
-	}
-
-	if (extend_size)
-		memset(reg, extend_val, extend_size);
-	memcpy(reg, &val, size);
-	return insn.length;
 }
 
 static bool handle_in(struct pt_regs *regs, int size, int port)

---

## [68] Alexey Gladkov — 2024-08-28
*Subject: [PATCH v5 2/6] x86/tdx: Add validation of userspace MMIO instructions*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Instructions from kernel space are considered trusted. If the MMIO
instruction is from userspace it must be checked.

For userspace instructions, it is need to check that the INSN has not
changed at the time of #VE and before the execution of the instruction.

Once the userspace instruction parsed is enforced that the address
points to mapped memory of current process and that address does not
point to private memory.

After parsing the userspace instruction, it is necessary to ensure that:

1. the operation direction (read/write) corresponds to #VE info;
2. the address still points to mapped memory of current process;
3. the address does not point to private memory.

Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 131 ++++++++++++++++++++++++++++++++++++----
 1 file changed, 118 insertions(+), 13 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index af0b6c1cacf7..99634e12f9a7 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -8,6 +8,7 @@
 #include <linux/export.h>
 #include <linux/io.h>
 #include <linux/kexec.h>
+#include <linux/mm.h>
 #include <asm/coco.h>
 #include <asm/tdx.h>
 #include <asm/vmx.h>
@@ -405,6 +406,87 @@ static bool mmio_write(int size, unsigned long addr, unsigned long val)
 			       EPT_WRITE, addr, val);
 }
 
+static inline bool is_private_gpa(u64 gpa)
+{
+	return gpa == cc_mkenc(gpa);
+}
+
+static int get_phys_addr(unsigned long addr, phys_addr_t *phys_addr, bool *writable)
+{
+	unsigned int level;
+	pgd_t *pgdp;
+	pte_t *ptep;
+
+	/*
+	 * Address validation only makes sense for a user process. The lock must
+	 * be obtained before validation can begin.
+	 */
+	mmap_assert_locked(current->mm);
+
+	pgdp = pgd_offset(current->mm, addr);
+
+	if (!pgd_none(*pgdp)) {
+		ptep = lookup_address_in_pgd(pgdp, addr, &level);
+		if (ptep) {
+			unsigned long offset;
+
+			if (!pte_decrypted(*ptep))
+				return -EFAULT;
+
+			offset = addr & ~page_level_mask(level);
+			*phys_addr = PFN_PHYS(pte_pfn(*ptep));
+			*phys_addr |= offset;
+
+			*writable = pte_write(*ptep);
+
+			return 0;
+		}
+	}
+
+	return -EFAULT;
+}
+
+static int valid_vaddr(struct ve_info *ve, enum insn_mmio_type mmio, int size,
+		       unsigned long vaddr)
+{
+	phys_addr_t phys_addr;
+	bool writable = false;
+
+	/* It's not fatal. This can happen due to swap out or page migration. */
+	if (get_phys_addr(vaddr, &phys_addr, &writable) || (ve->gpa != cc_mkdec(phys_addr)))
+		return -EAGAIN;
+
+	/*
+	 * Re-check whether #VE info matches the instruction that was decoded.
+	 *
+	 * The ve->gpa was valid at the time ve_info was received. But this code
+	 * executed with interrupts enabled, allowing tlb shootdown and therefore
+	 * munmap() to be executed in the parallel thread.
+	 *
+	 * By the time MMIO emulation is performed, ve->gpa may be already
+	 * unmapped from the process, the device it belongs to removed from
+	 * system and something else could be plugged in its place.
+	 */
+	switch (mmio) {
+	case INSN_MMIO_WRITE:
+	case INSN_MMIO_WRITE_IMM:
+		if (!writable || !(ve->exit_qual & EPT_VIOLATION_ACC_WRITE))
+			return -EFAULT;
+		break;
+	case INSN_MMIO_READ:
+	case INSN_MMIO_READ_ZERO_EXTEND:
+	case INSN_MMIO_READ_SIGN_EXTEND:
+		if (!(ve->exit_qual & EPT_VIOLATION_ACC_READ))
+			return -EFAULT;
+		break;
+	default:
+		WARN_ONCE(1, "Unsupported mmio instruction: %d", mmio);
+		return -EINVAL;
+	}
+
+	return 0;
+}
+
 static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
 			     struct pt_regs *regs, struct ve_info *ve)
 {
@@ -489,7 +571,7 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
 	unsigned long vaddr;
-	int size;
+	int size, ret;
 
 	/* Only in-kernel MMIO is supported */
 	if (WARN_ON_ONCE(user_mode(regs)))
@@ -505,6 +587,17 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
+	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
+
+	if (user_mode(regs)) {
+		if (mmap_read_lock_killable(current->mm))
+			return -EINTR;
+
+		ret = valid_vaddr(ve, mmio, size, vaddr);
+		if (ret)
+			goto unlock;
+	}
+
 	/*
 	 * Reject EPT violation #VEs that split pages.
 	 *
@@ -514,30 +607,39 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	 *
 	 * load_unaligned_zeropad() will recover using exception fixups.
 	 */
-	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
-	if (vaddr / PAGE_SIZE != (vaddr + size - 1) / PAGE_SIZE)
-		return -EFAULT;
+	if (vaddr / PAGE_SIZE != (vaddr + size - 1) / PAGE_SIZE) {
+		ret = -EFAULT;
+		goto unlock;
+	}
 
 	switch (mmio) {
 	case INSN_MMIO_WRITE:
 	case INSN_MMIO_WRITE_IMM:
 	case INSN_MMIO_MOVS:
-		return handle_mmio_write(&insn, mmio, size, regs, ve);
+		ret = handle_mmio_write(&insn, mmio, size, regs, ve);
+		break;
 	case INSN_MMIO_READ:
 	case INSN_MMIO_READ_ZERO_EXTEND:
 	case INSN_MMIO_READ_SIGN_EXTEND:
-		return handle_mmio_read(&insn, mmio, size, regs, ve);
+		ret = handle_mmio_read(&insn, mmio, size, regs, ve);
+		break;
 	case INSN_MMIO_DECODE_FAILED:
 		/*
 		 * MMIO was accessed with an instruction that could not be
 		 * decoded or handled properly. It was likely not using io.h
 		 * helpers or accessed MMIO accidentally.
 		 */
-		return -EINVAL;
+		ret = -EINVAL;
+		break;
 	default:
 		WARN_ONCE(1, "Unknown insn_decode_mmio() decode value?");
-		return -EINVAL;
+		ret = -EINVAL;
 	}
+unlock:
+	if (user_mode(regs))
+		mmap_read_unlock(current->mm);
+
+	return ret;
 }
 
 static bool handle_in(struct pt_regs *regs, int size, int port)
@@ -681,11 +783,6 @@ static int virt_exception_user(struct pt_regs *regs, struct ve_info *ve)
 	}
 }
 
-static inline bool is_private_gpa(u64 gpa)
-{
-	return gpa == cc_mkenc(gpa);
-}
-
 /*
  * Handle the kernel #VE.
  *
@@ -723,6 +820,14 @@ bool tdx_handle_virt_exception(struct pt_regs *regs, struct ve_info *ve)
 		insn_len = virt_exception_user(regs, ve);
 	else
 		insn_len = virt_exception_kernel(regs, ve);
+
+	/*
+	 * A special case to return to userspace without increasing regs->ip
+	 * to repeat the instruction once again.
+	 */
+	if (insn_len == -EAGAIN)
+		return true;
+
 	if (insn_len < 0)
 		return false;

---

## [69] Alexey Gladkov — 2024-08-28
*Subject: [PATCH v5 3/6] x86/tdx: Allow MMIO from userspace*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

The MMIO emulation is only allowed for kernel space code. It is carried
out through a special API, which uses only certain instructions.

This does not allow userspace to work with virtual devices.

Allow userspace to use the same instructions as kernel space to access
MMIO. Additional checks have been added previously.

Reviewed-by: Thomas Gleixner <tglx@linutronix.de>
Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 43 +++++++++++++++++++++++++++++++----------
 1 file changed, 33 insertions(+), 10 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 99634e12f9a7..5d2d07aa08ce 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -487,6 +487,32 @@ static int valid_vaddr(struct ve_info *ve, enum insn_mmio_type mmio, int size,
 	return 0;
 }
 
+static int decode_insn_struct(struct insn *insn, struct pt_regs *regs)
+{
+	char buffer[MAX_INSN_SIZE];
+
+	if (user_mode(regs)) {
+		int nr_copied = insn_fetch_from_user(regs, buffer);
+
+		if (nr_copied <= 0)
+			return -EFAULT;
+
+		if (!insn_decode_from_regs(insn, regs, buffer, nr_copied))
+			return -EINVAL;
+	} else {
+		if (copy_from_kernel_nofault(buffer, (void *)regs->ip, MAX_INSN_SIZE))
+			return -EFAULT;
+
+		if (insn_decode(insn, buffer, MAX_INSN_SIZE, INSN_MODE_64))
+			return -EINVAL;
+	}
+
+	if (!insn->immediate.got)
+		return -EINVAL;
+
+	return 0;
+}
+
 static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
 			     struct pt_regs *regs, struct ve_info *ve)
 {
@@ -567,21 +593,14 @@ static int handle_mmio_read(struct insn *insn, enum insn_mmio_type mmio, int siz
 
 static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 {
-	char buffer[MAX_INSN_SIZE];
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
 	unsigned long vaddr;
 	int size, ret;
 
-	/* Only in-kernel MMIO is supported */
-	if (WARN_ON_ONCE(user_mode(regs)))
-		return -EFAULT;
-
-	if (copy_from_kernel_nofault(buffer, (void *)regs->ip, MAX_INSN_SIZE))
-		return -EFAULT;
-
-	if (insn_decode(&insn, buffer, MAX_INSN_SIZE, INSN_MODE_64))
-		return -EINVAL;
+	ret = decode_insn_struct(&insn, regs);
+	if (ret)
+		return ret;
 
 	mmio = insn_decode_mmio(&insn, &size);
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
@@ -777,6 +796,10 @@ static int virt_exception_user(struct pt_regs *regs, struct ve_info *ve)
 	switch (ve->exit_reason) {
 	case EXIT_REASON_CPUID:
 		return handle_cpuid(regs, ve);
+	case EXIT_REASON_EPT_VIOLATION:
+		if (is_private_gpa(ve->gpa))
+			panic("Unexpected EPT-violation on private memory.");
+		return handle_mmio(regs, ve);
 	default:
 		pr_warn("Unexpected #VE: %lld\n", ve->exit_reason);
 		return -EIO;

---

## [70] Alexey Gladkov — 2024-08-28
*Subject: [PATCH v5 4/6] x86/tdx: Add a restriction on access to MMIO address*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

For security reasons, access from kernel space to MMIO addresses in
userspace should be restricted. All MMIO operations from kernel space
are considered trusted and are not validated.

For instance, if in response to a syscall, kernel does put_user() and
the target address is MMIO mapping in userspace, current #VE handler
threat this access as kernel MMIO which is wrong and have security
implications.

Cc: stable@vger.kernel.org
Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 10 ++++++++++
 1 file changed, 10 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 5d2d07aa08ce..65f65015238a 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -411,6 +411,11 @@ static inline bool is_private_gpa(u64 gpa)
 	return gpa == cc_mkenc(gpa);
 }
 
+static inline bool is_kernel_addr(unsigned long addr)
+{
+	return (long)addr < 0;
+}
+
 static int get_phys_addr(unsigned long addr, phys_addr_t *phys_addr, bool *writable)
 {
 	unsigned int level;
@@ -606,6 +611,11 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
+	if (!user_mode(regs) && !is_kernel_addr(ve->gla)) {
+		WARN_ONCE(1, "Access to userspace address is not supported");
+		return -EINVAL;
+	}
+
 	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
 
 	if (user_mode(regs)) {

---

## [71] Alexey Gladkov — 2024-08-28
*Subject: [PATCH v5 5/6] x86/tdx: Move MMIO helpers to common library*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

AMD code has helpers that are used to emulate MOVS instructions. To be
able to reuse this code in the MOVS implementation for intel, it is
necessary to move them to a common location.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/sev/core.c  | 139 ++++++--------------------------------
 arch/x86/include/asm/io.h |   3 +
 arch/x86/lib/iomem.c      | 115 +++++++++++++++++++++++++++++++
 3 files changed, 140 insertions(+), 117 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 082d61d85dfc..07e9a6f15fba 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -369,72 +369,24 @@ static enum es_result vc_decode_insn(struct es_em_ctxt *ctxt)
 static enum es_result vc_write_mem(struct es_em_ctxt *ctxt,
 				   char *dst, char *buf, size_t size)
 {
-	unsigned long error_code = X86_PF_PROT | X86_PF_WRITE;
+	unsigned long error_code;
+	int ret;
 
 	/*
-	 * This function uses __put_user() independent of whether kernel or user
-	 * memory is accessed. This works fine because __put_user() does no
-	 * sanity checks of the pointer being accessed. All that it does is
-	 * to report when the access failed.
-	 *
-	 * Also, this function runs in atomic context, so __put_user() is not
-	 * allowed to sleep. The page-fault handler detects that it is running
-	 * in atomic context and will not try to take mmap_sem and handle the
-	 * fault, so additional pagefault_enable()/disable() calls are not
-	 * needed.
-	 *
-	 * The access can't be done via copy_to_user() here because
-	 * vc_write_mem() must not use string instructions to access unsafe
-	 * memory. The reason is that MOVS is emulated by the #VC handler by
-	 * splitting the move up into a read and a write and taking a nested #VC
-	 * exception on whatever of them is the MMIO access. Using string
-	 * instructions here would cause infinite nesting.
+	 * This function runs in atomic context, so __put_iomem() is not allowed
+	 * to sleep. The page-fault handler detects that it is running in atomic
+	 * context and will not try to take mmap_lock and handle the fault, so
+	 * additional pagefault_enable()/disable() calls are not needed.
 	 */
-	switch (size) {
-	case 1: {
-		u8 d1;
-		u8 __user *target = (u8 __user *)dst;
-
-		memcpy(&d1, buf, 1);
-		if (__put_user(d1, target))
-			goto fault;
-		break;
-	}
-	case 2: {
-		u16 d2;
-		u16 __user *target = (u16 __user *)dst;
-
-		memcpy(&d2, buf, 2);
-		if (__put_user(d2, target))
-			goto fault;
-		break;
-	}
-	case 4: {
-		u32 d4;
-		u32 __user *target = (u32 __user *)dst;
-
-		memcpy(&d4, buf, 4);
-		if (__put_user(d4, target))
-			goto fault;
-		break;
-	}
-	case 8: {
-		u64 d8;
-		u64 __user *target = (u64 __user *)dst;
+	ret = __put_iomem(dst, buf, size);
+	if (!ret)
+		return ES_OK;
 
-		memcpy(&d8, buf, 8);
-		if (__put_user(d8, target))
-			goto fault;
-		break;
-	}
-	default:
-		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+	if (ret == -EIO)
 		return ES_UNSUPPORTED;
-	}
 
-	return ES_OK;
+	error_code = X86_PF_PROT | X86_PF_WRITE;
 
-fault:
 	if (user_mode(ctxt->regs))
 		error_code |= X86_PF_USER;
 
@@ -448,71 +400,24 @@ static enum es_result vc_write_mem(struct es_em_ctxt *ctxt,
 static enum es_result vc_read_mem(struct es_em_ctxt *ctxt,
 				  char *src, char *buf, size_t size)
 {
-	unsigned long error_code = X86_PF_PROT;
+	unsigned long error_code;
+	int ret;
 
 	/*
-	 * This function uses __get_user() independent of whether kernel or user
-	 * memory is accessed. This works fine because __get_user() does no
-	 * sanity checks of the pointer being accessed. All that it does is
-	 * to report when the access failed.
-	 *
-	 * Also, this function runs in atomic context, so __get_user() is not
-	 * allowed to sleep. The page-fault handler detects that it is running
-	 * in atomic context and will not try to take mmap_sem and handle the
-	 * fault, so additional pagefault_enable()/disable() calls are not
-	 * needed.
-	 *
-	 * The access can't be done via copy_from_user() here because
-	 * vc_read_mem() must not use string instructions to access unsafe
-	 * memory. The reason is that MOVS is emulated by the #VC handler by
-	 * splitting the move up into a read and a write and taking a nested #VC
-	 * exception on whatever of them is the MMIO access. Using string
-	 * instructions here would cause infinite nesting.
+	 * This function runs in atomic context, so __get_iomem() is not allowed
+	 * to sleep. The page-fault handler detects that it is running in atomic
+	 * context and will not try to take mmap_lock and handle the fault, so
+	 * additional pagefault_enable()/disable() calls are not needed.
 	 */
-	switch (size) {
-	case 1: {
-		u8 d1;
-		u8 __user *s = (u8 __user *)src;
-
-		if (__get_user(d1, s))
-			goto fault;
-		memcpy(buf, &d1, 1);
-		break;
-	}
-	case 2: {
-		u16 d2;
-		u16 __user *s = (u16 __user *)src;
-
-		if (__get_user(d2, s))
-			goto fault;
-		memcpy(buf, &d2, 2);
-		break;
-	}
-	case 4: {
-		u32 d4;
-		u32 __user *s = (u32 __user *)src;
+	ret = __get_iomem(src, buf, size);
+	if (!ret)
+		return ES_OK;
 
-		if (__get_user(d4, s))
-			goto fault;
-		memcpy(buf, &d4, 4);
-		break;
-	}
-	case 8: {
-		u64 d8;
-		u64 __user *s = (u64 __user *)src;
-		if (__get_user(d8, s))
-			goto fault;
-		memcpy(buf, &d8, 8);
-		break;
-	}
-	default:
-		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+	if (ret == -EIO)
 		return ES_UNSUPPORTED;
-	}
 
-	return ES_OK;
+	error_code = X86_PF_PROT;
 
-fault:
 	if (user_mode(ctxt->regs))
 		error_code |= X86_PF_USER;
 
diff --git a/arch/x86/include/asm/io.h b/arch/x86/include/asm/io.h
index 1d60427379c9..ac01d53466cb 100644
--- a/arch/x86/include/asm/io.h
+++ b/arch/x86/include/asm/io.h
@@ -402,4 +402,7 @@ static inline void iosubmit_cmds512(void __iomem *dst, const void *src,
 	}
 }
 
+int __get_iomem(char *src, char *buf, size_t size);
+int __put_iomem(char *src, char *buf, size_t size);
+
 #endif /* _ASM_X86_IO_H */
diff --git a/arch/x86/lib/iomem.c b/arch/x86/lib/iomem.c
index 5eecb45d05d5..3ab146edddea 100644
--- a/arch/x86/lib/iomem.c
+++ b/arch/x86/lib/iomem.c
@@ -2,6 +2,7 @@
 #include <linux/module.h>
 #include <linux/io.h>
 #include <linux/kmsan-checks.h>
+#include <asm/uaccess.h>
 
 #define movs(type,to,from) \
 	asm volatile("movs" type:"=&D" (to), "=&S" (from):"0" (to), "1" (from):"memory")
@@ -124,3 +125,117 @@ void memset_io(volatile void __iomem *a, int b, size_t c)
 	}
 }
 EXPORT_SYMBOL(memset_io);
+
+int __get_iomem(char *src, char *buf, size_t size)
+{
+	/*
+	 * This function uses __get_user() independent of whether kernel or user
+	 * memory is accessed. This works fine because __get_user() does no
+	 * sanity checks of the pointer being accessed. All that it does is
+	 * to report when the access failed.
+	 *
+	 * The access can't be done via copy_from_user() here because
+	 * __get_iomem() must not use string instructions to access unsafe
+	 * memory. The reason is that MOVS is emulated by the exception handler
+	 * for SEV and TDX by splitting the move up into a read and a write
+	 * opetations and taking a nested exception on whatever of them is the
+	 * MMIO access. Using string instructions here would cause infinite
+	 * nesting.
+	 */
+	switch (size) {
+	case 1: {
+		u8 d1, __user *s = (u8 __user *)src;
+
+		if (__get_user(d1, s))
+			return -EFAULT;
+		memcpy(buf, &d1, 1);
+		break;
+	}
+	case 2: {
+		u16 d2, __user *s = (u16 __user *)src;
+
+		if (__get_user(d2, s))
+			return -EFAULT;
+		memcpy(buf, &d2, 2);
+		break;
+	}
+	case 4: {
+		u32 d4, __user *s = (u32 __user *)src;
+
+		if (__get_user(d4, s))
+			return -EFAULT;
+		memcpy(buf, &d4, 4);
+		break;
+	}
+	case 8: {
+		u64 d8, __user *s = (u64 __user *)src;
+
+		if (__get_user(d8, s))
+			return -EFAULT;
+		memcpy(buf, &d8, 8);
+		break;
+	}
+	default:
+		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+		return -EIO;
+	}
+
+	return 0;
+}
+
+int __put_iomem(char *dst, char *buf, size_t size)
+{
+	/*
+	 * This function uses __put_user() independent of whether kernel or user
+	 * memory is accessed. This works fine because __put_user() does no
+	 * sanity checks of the pointer being accessed. All that it does is
+	 * to report when the access failed.
+	 *
+	 * The access can't be done via copy_to_user() here because
+	 * __put_iomem() must not use string instructions to access unsafe
+	 * memory. The reason is that MOVS is emulated by the exception handler
+	 * for SEV and TDX by splitting the move up into a read and a write
+	 * opetations and taking a nested exception on whatever of them is the
+	 * MMIO access. Using string instructions here would cause infinite
+	 * nesting.
+	 */
+	switch (size) {
+	case 1: {
+		u8 d1, __user *target = (u8 __user *)dst;
+
+		memcpy(&d1, buf, 1);
+		if (__put_user(d1, target))
+			return -EFAULT;
+		break;
+	}
+	case 2: {
+		u16 d2, __user *target = (u16 __user *)dst;
+
+		memcpy(&d2, buf, 2);
+		if (__put_user(d2, target))
+			return -EFAULT;
+		break;
+	}
+	case 4: {
+		u32 d4, __user *target = (u32 __user *)dst;
+
+		memcpy(&d4, buf, 4);
+		if (__put_user(d4, target))
+			return -EFAULT;
+		break;
+	}
+	case 8: {
+		u64 d8, __user *target = (u64 __user *)dst;
+
+		memcpy(&d8, buf, 8);
+		if (__put_user(d8, target))
+			return -EFAULT;
+		break;
+	}
+	default:
+		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+		return -EIO;
+	}
+
+	return 0;
+}

---

## [72] Alexey Gladkov — 2024-08-28
*Subject: [PATCH v5 6/6] x86/tdx: Implement MOVS for MMIO*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Add emulation of the MOVS instruction on MMIO regions. MOVS emulation
consists of dividing it into a series of read and write operations,
which in turn will be validated separately.

This implementation is based on the same principle as in SEV. It splits
MOVS into separate read and write operations, which in turn can cause
nested #VEs depending on which of the arguments caused the first #VE.

The difference with the SEV implementation is the execution context. SEV
code is executed in atomic context. Exception handler in TDX is executed
with interrupts enabled. That's why the approach to locking is
different. In TDX, mmap_lock is taken to verify and emulate the
instruction.

Another difference is how the read and write instructions are executed
for MOVS emulation. While in SEV each read/write operation returns to
user space, in TDX these operations are performed from the kernel
context.

It may be possible to achieve more code reuse at this point,
but it would require confirmation from SEV that such a thing wouldn't
break anything.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c          | 82 ++++++++++++++++++++++++++++----
 arch/x86/include/asm/processor.h |  3 ++
 2 files changed, 77 insertions(+), 8 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 65f65015238a..a9b3c6dee9ad 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -518,6 +518,60 @@ static int decode_insn_struct(struct insn *insn, struct pt_regs *regs)
 	return 0;
 }
 
+static int handle_mmio_movs(struct insn *insn, struct pt_regs *regs, int size, struct ve_info *ve)
+{
+	unsigned long ds_base, es_base;
+	unsigned char *src, *dst;
+	unsigned char buffer[8];
+	int off, ret;
+	bool rep;
+
+	/*
+	 * The in-kernel code must use a special API that does not use MOVS.
+	 * If the MOVS instruction is received from in-kernel, then something
+	 * is broken.
+	 */
+	if (WARN_ON_ONCE(!user_mode(regs)))
+		return -EFAULT;
+
+	ds_base = insn_get_seg_base(regs, INAT_SEG_REG_DS);
+	es_base = insn_get_seg_base(regs, INAT_SEG_REG_ES);
+
+	if (ds_base == -1L || es_base == -1L)
+		return -EINVAL;
+
+	current->thread.in_mmio_emul = 1;
+
+	rep = insn_has_rep_prefix(insn);
+
+	do {
+		src = ds_base + (unsigned char *) regs->si;
+		dst = es_base + (unsigned char *) regs->di;
+
+		ret = __get_iomem(src, buffer, size);
+		if (ret)
+			goto out;
+
+		ret = __put_iomem(dst, buffer, size);
+		if (ret)
+			goto out;
+
+		off = (regs->flags & X86_EFLAGS_DF) ? -size : size;
+
+		regs->si += off;
+		regs->di += off;
+
+		if (rep)
+			regs->cx -= 1;
+	} while (rep || regs->cx > 0);
+
+	ret = insn->length;
+out:
+	current->thread.in_mmio_emul = 0;
+
+	return ret;
+}
+
 static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
 			     struct pt_regs *regs, struct ve_info *ve)
 {
@@ -539,9 +593,8 @@ static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int si
 		return insn->length;
 	case INSN_MMIO_MOVS:
 		/*
-		 * MMIO was accessed with an instruction that could not be
-		 * decoded or handled properly. It was likely not using io.h
-		 * helpers or accessed MMIO accidentally.
+		 * MOVS is processed through higher level emulation which breaks
+		 * this instruction into a sequence of reads and writes.
 		 */
 		return -EINVAL;
 	default:
@@ -600,6 +653,7 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 {
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
+	int need_validation;
 	unsigned long vaddr;
 	int size, ret;
 
@@ -611,14 +665,27 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
+	if (mmio == INSN_MMIO_MOVS)
+		return handle_mmio_movs(&insn, regs, size, ve);
+
+	need_validation = user_mode(regs);
+
 	if (!user_mode(regs) && !is_kernel_addr(ve->gla)) {
-		WARN_ONCE(1, "Access to userspace address is not supported");
-		return -EINVAL;
+		/*
+		 * Access from kernel to userspace addresses is not allowed
+		 * unless it is a nested exception during MOVS emulation.
+		 */
+		if (!current->thread.in_mmio_emul || !current->mm) {
+			WARN_ONCE(1, "Access to userspace address is not supported");
+			return -EINVAL;
+		}
+
+		need_validation = 1;
 	}
 
 	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
 
-	if (user_mode(regs)) {
+	if (need_validation) {
 		if (mmap_read_lock_killable(current->mm))
 			return -EINTR;
 
@@ -644,7 +711,6 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	switch (mmio) {
 	case INSN_MMIO_WRITE:
 	case INSN_MMIO_WRITE_IMM:
-	case INSN_MMIO_MOVS:
 		ret = handle_mmio_write(&insn, mmio, size, regs, ve);
 		break;
 	case INSN_MMIO_READ:
@@ -665,7 +731,7 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 		ret = -EINVAL;
 	}
 unlock:
-	if (user_mode(regs))
+	if (need_validation)
 		mmap_read_unlock(current->mm);
 
 	return ret;
diff --git a/arch/x86/include/asm/processor.h b/arch/x86/include/asm/processor.h
index a75a07f4931f..33875a217ed8 100644
--- a/arch/x86/include/asm/processor.h
+++ b/arch/x86/include/asm/processor.h
@@ -486,6 +486,9 @@ struct thread_struct {
 	unsigned long		iopl_emul;
 
 	unsigned int		iopl_warn:1;
+#ifdef CONFIG_INTEL_TDX_GUEST
+	unsigned int		in_mmio_emul:1;
+#endif
 
 	/*
 	 * Protection Keys Register for Userspace.  Loaded immediately on

---

## [73] Kirill A. Shutemov — 2024-08-29
*Subject: Re: [PATCH v5 4/6] x86/tdx: Add a restriction on access to MMIO
 address*

On Wed, Aug 28, 2024 at 12:44:34PM +0200, Alexey Gladkov wrote:
> From: "Alexey Gladkov (Intel)" <legion@kernel.org>
> 

What about this:

------------------------------------8<-----------------------------------

Subject: x86/tdx: Fix "in-kernel MMIO" check

TDX only supports kernel-initiated MMIO operations. The handle_mmio()
function checks if the #VE exception occurred in the kernel and rejects
the operation if it did not.

However, userspace can deceive the kernel into performing MMIO on its
behalf. For example, if userspace can point a syscall to an MMIO address,
syscall does get_user() or put_user() on it, triggering MMIO #VE. The
kernel will treat the #VE as in-kernel MMIO.

Ensure that the target MMIO address is within the kernel before decoding
instruction.

------------------------------------8<-----------------------------------

And please make this patch the first in the patchset. It has to be
backported to stable trees and should have zero dependencies on the rest
of the patchset.

---

## [74] Kirill A. Shutemov — 2024-08-29
*Subject: Re: [PATCH v5 6/6] x86/tdx: Implement MOVS for MMIO*

On Wed, Aug 28, 2024 at 12:44:36PM +0200, Alexey Gladkov wrote:
> From: "Alexey Gladkov (Intel)" <legion@kernel.org>
> 

It looks like SEV only returns to userspace to retry the instruction after
stepping on failed __get_user()/__put_user(), unrolling back to
vc_raw_handle_exception() and handling page fault there.

But I'm not sure what happens with #VC inside vc_read_mem() and
vc_write_mem(). Can the #VC exception be nested? Tom?

---

## [75] Alexey Gladkov — 2024-08-29
*Subject: Re: [PATCH v5 6/6] x86/tdx: Implement MOVS for MMIO*

On Thu, Aug 29, 2024 at 03:44:55PM +0300, Kirill A. Shutemov wrote:
> On Wed, Aug 28, 2024 at 12:44:36PM +0200, Alexey Gladkov wrote:
> > From: "Alexey Gladkov (Intel)" <legion@kernel.org>

In vc_handle_mmio_movs() if regs->cx is not zero we return ES_RETRY. The
vc_handle_mmio(), vc_handle_exitcode() return it as is. In
vc_raw_handle_exception() if vc_handle_exitcode() returns ES_RETRY then we
just return true. So, the ES_RETRY is not further visible.

Or am I missing something?

> 
> But I'm not sure what happens with #VC inside vc_read_mem() and

---

## [76] Alexey Gladkov — 2024-09-06
*Subject: [PATCH v6 0/6] x86/tdx: Allow MMIO instructions from userspace*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Currently, MMIO inside the TDX guest is allowed from kernel space and access
from userspace is denied. This becomes a problem when working with virtual
devices in userspace.

In TDX guest MMIO instructions are emulated in #VE. The kernel code uses special
helpers to access MMIO memory to limit the number of instructions which are
used.

This patchset makes MMIO accessible from userspace. To do this additional checks
were added to ensure that the emulated instruction will not be compromised.


v6:
- Reorder patches and change commit messages.

v5:
- Improve commit messages and comments in commits as suggested by Kirill A. Shutemov.
- To emulate MOVS, instead of storing the entire address, started using a flag.

v4:
- Move patches to avoid crossing the page boundary to separate patchset. They
  address separate issue.
- Check the address only in user context and in case of nested exceptions.
- Fix the check that the address does not point to private memory.

v3:
- Add patches to avoid crossing the page boundary when the instruction is read
  and decoded in the TDX, SEV, UMIP.
- Forbid accessing userspace addresses from kernel space. The exception to this
  is when emulating MOVS instructions.
- Fix address validation during MOVS emulation.

v2:
- Split into separate patches AMD helpers extraction and MOVS implementation
  code for intel as suggested by Thomas Gleixner.
- Fix coding style issues.


Alexey Gladkov (Intel) (6):
  x86/tdx: Fix "in-kernel MMIO" check
  x86/tdx: Split MMIO read and write operations
  x86/tdx: Add validation of userspace MMIO instructions
  x86/tdx: Allow MMIO from userspace
  x86/tdx: Move MMIO helpers to common library
  x86/tdx: Implement MOVS for MMIO

 arch/x86/coco/sev/core.c         | 139 ++-----------
 arch/x86/coco/tdx/tdx.c          | 338 ++++++++++++++++++++++++++-----
 arch/x86/include/asm/io.h        |   3 +
 arch/x86/include/asm/processor.h |   3 +
 arch/x86/lib/iomem.c             | 115 +++++++++++
 5 files changed, 429 insertions(+), 169 deletions(-)

---

## [77] Alexey Gladkov — 2024-09-06
*Subject: [PATCH v6 1/6] x86/tdx: Fix "in-kernel MMIO" check*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

TDX only supports kernel-initiated MMIO operations. The handle_mmio()
function checks if the #VE exception occurred in the kernel and rejects
the operation if it did not.

However, userspace can deceive the kernel into performing MMIO on its
behalf. For example, if userspace can point a syscall to an MMIO address,
syscall does get_user() or put_user() on it, triggering MMIO #VE. The
kernel will treat the #VE as in-kernel MMIO.

Ensure that the target MMIO address is within the kernel before decoding
instruction.

Cc: stable@vger.kernel.org
Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 10 ++++++++++
 1 file changed, 10 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 078e2bac2553..c90d2fdb5fc4 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -405,6 +405,11 @@ static bool mmio_write(int size, unsigned long addr, unsigned long val)
 			       EPT_WRITE, addr, val);
 }
 
+static inline bool is_kernel_addr(unsigned long addr)
+{
+	return (long)addr < 0;
+}
+
 static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 {
 	unsigned long *reg, val, vaddr;
@@ -434,6 +439,11 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 			return -EINVAL;
 	}
 
+	if (!user_mode(regs) && !is_kernel_addr(ve->gla)) {
+		WARN_ONCE(1, "Access to userspace address is not supported");
+		return -EINVAL;
+	}
+
 	/*
 	 * Reject EPT violation #VEs that split pages.
 	 *

---

## [78] Alexey Gladkov — 2024-09-06
*Subject: [PATCH v6 2/6] x86/tdx: Split MMIO read and write operations*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

To implement MMIO in userspace, additional memory checks need to be
implemented. To avoid overly complicating the handle_mmio() function
and to separate checks from actions, it would be better to split this
function into two separate functions to handle read and write
operations.

Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 136 ++++++++++++++++++++++++----------------
 1 file changed, 83 insertions(+), 53 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index c90d2fdb5fc4..eee97dff1eca 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -410,14 +410,91 @@ static inline bool is_kernel_addr(unsigned long addr)
 	return (long)addr < 0;
 }
 
+static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
+			     struct pt_regs *regs, struct ve_info *ve)
+{
+	unsigned long *reg, val;
+
+	switch (mmio) {
+	case INSN_MMIO_WRITE:
+		reg = insn_get_modrm_reg_ptr(insn, regs);
+		if (!reg)
+			return -EINVAL;
+		memcpy(&val, reg, size);
+		if (!mmio_write(size, ve->gpa, val))
+			return -EIO;
+		return insn->length;
+	case INSN_MMIO_WRITE_IMM:
+		val = insn->immediate.value;
+		if (!mmio_write(size, ve->gpa, val))
+			return -EIO;
+		return insn->length;
+	case INSN_MMIO_MOVS:
+		/*
+		 * MMIO was accessed with an instruction that could not be
+		 * decoded or handled properly. It was likely not using io.h
+		 * helpers or accessed MMIO accidentally.
+		 */
+		return -EINVAL;
+	default:
+		WARN_ON_ONCE(1);
+		return -EINVAL;
+	}
+
+	return insn->length;
+}
+
+static int handle_mmio_read(struct insn *insn, enum insn_mmio_type mmio, int size,
+			    struct pt_regs *regs, struct ve_info *ve)
+{
+	unsigned long *reg, val;
+	int extend_size;
+	u8 extend_val;
+
+	reg = insn_get_modrm_reg_ptr(insn, regs);
+	if (!reg)
+		return -EINVAL;
+
+	if (!mmio_read(size, ve->gpa, &val))
+		return -EIO;
+
+	extend_val = 0;
+
+	switch (mmio) {
+	case INSN_MMIO_READ:
+		/* Zero-extend for 32-bit operation */
+		extend_size = size == 4 ? sizeof(*reg) : 0;
+		break;
+	case INSN_MMIO_READ_ZERO_EXTEND:
+		/* Zero extend based on operand size */
+		extend_size = insn->opnd_bytes;
+		break;
+	case INSN_MMIO_READ_SIGN_EXTEND:
+		/* Sign extend based on operand size */
+		extend_size = insn->opnd_bytes;
+		if (size == 1 && val & BIT(7))
+			extend_val = 0xFF;
+		else if (size > 1 && val & BIT(15))
+			extend_val = 0xFF;
+		break;
+	default:
+		WARN_ON_ONCE(1);
+		return -EINVAL;
+	}
+
+	if (extend_size)
+		memset(reg, extend_val, extend_size);
+	memcpy(reg, &val, size);
+	return insn->length;
+}
+
 static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 {
-	unsigned long *reg, val, vaddr;
 	char buffer[MAX_INSN_SIZE];
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
-	int size, extend_size;
-	u8 extend_val = 0;
+	unsigned long vaddr;
+	int size;
 
 	/* Only in-kernel MMIO is supported */
 	if (WARN_ON_ONCE(user_mode(regs)))
@@ -433,12 +510,6 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
-	if (mmio != INSN_MMIO_WRITE_IMM && mmio != INSN_MMIO_MOVS) {
-		reg = insn_get_modrm_reg_ptr(&insn, regs);
-		if (!reg)
-			return -EINVAL;
-	}
-
 	if (!user_mode(regs) && !is_kernel_addr(ve->gla)) {
 		WARN_ONCE(1, "Access to userspace address is not supported");
 		return -EINVAL;
@@ -457,24 +528,15 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (vaddr / PAGE_SIZE != (vaddr + size - 1) / PAGE_SIZE)
 		return -EFAULT;
 
-	/* Handle writes first */
 	switch (mmio) {
 	case INSN_MMIO_WRITE:
-		memcpy(&val, reg, size);
-		if (!mmio_write(size, ve->gpa, val))
-			return -EIO;
-		return insn.length;
 	case INSN_MMIO_WRITE_IMM:
-		val = insn.immediate.value;
-		if (!mmio_write(size, ve->gpa, val))
-			return -EIO;
-		return insn.length;
+	case INSN_MMIO_MOVS:
+		return handle_mmio_write(&insn, mmio, size, regs, ve);
 	case INSN_MMIO_READ:
 	case INSN_MMIO_READ_ZERO_EXTEND:
 	case INSN_MMIO_READ_SIGN_EXTEND:
-		/* Reads are handled below */
-		break;
-	case INSN_MMIO_MOVS:
+		return handle_mmio_read(&insn, mmio, size, regs, ve);
 	case INSN_MMIO_DECODE_FAILED:
 		/*
 		 * MMIO was accessed with an instruction that could not be
@@ -486,38 +548,6 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 		WARN_ONCE(1, "Unknown insn_decode_mmio() decode value?");
 		return -EINVAL;
 	}
-
-	/* Handle reads */
-	if (!mmio_read(size, ve->gpa, &val))
-		return -EIO;
-
-	switch (mmio) {
-	case INSN_MMIO_READ:
-		/* Zero-extend for 32-bit operation */
-		extend_size = size == 4 ? sizeof(*reg) : 0;
-		break;
-	case INSN_MMIO_READ_ZERO_EXTEND:
-		/* Zero extend based on operand size */
-		extend_size = insn.opnd_bytes;
-		break;
-	case INSN_MMIO_READ_SIGN_EXTEND:
-		/* Sign extend based on operand size */
-		extend_size = insn.opnd_bytes;
-		if (size == 1 && val & BIT(7))
-			extend_val = 0xFF;
-		else if (size > 1 && val & BIT(15))
-			extend_val = 0xFF;
-		break;
-	default:
-		/* All other cases has to be covered with the first switch() */
-		WARN_ON_ONCE(1);
-		return -EINVAL;
-	}
-
-	if (extend_size)
-		memset(reg, extend_val, extend_size);
-	memcpy(reg, &val, size);
-	return insn.length;
 }
 
 static bool handle_in(struct pt_regs *regs, int size, int port)

---

## [79] Alexey Gladkov — 2024-09-06
*Subject: [PATCH v6 3/6] x86/tdx: Add validation of userspace MMIO instructions*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Instructions from kernel space are considered trusted. If the MMIO
instruction is from userspace it must be checked.

For userspace instructions, it is need to check that the INSN has not
changed at the time of #VE and before the execution of the instruction.

Once the userspace instruction parsed is enforced that the address
points to mapped memory of current process and that address does not
point to private memory.

After parsing the userspace instruction, it is necessary to ensure that:

1. the operation direction (read/write) corresponds to #VE info;
2. the address still points to mapped memory of current process;
3. the address does not point to private memory.

Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 130 ++++++++++++++++++++++++++++++++++++----
 1 file changed, 117 insertions(+), 13 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index eee97dff1eca..636bf4013ef2 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -8,6 +8,7 @@
 #include <linux/export.h>
 #include <linux/io.h>
 #include <linux/kexec.h>
+#include <linux/mm.h>
 #include <asm/coco.h>
 #include <asm/tdx.h>
 #include <asm/vmx.h>
@@ -410,6 +411,87 @@ static inline bool is_kernel_addr(unsigned long addr)
 	return (long)addr < 0;
 }
 
+static inline bool is_private_gpa(u64 gpa)
+{
+	return gpa == cc_mkenc(gpa);
+}
+
+static int get_phys_addr(unsigned long addr, phys_addr_t *phys_addr, bool *writable)
+{
+	unsigned int level;
+	pgd_t *pgdp;
+	pte_t *ptep;
+
+	/*
+	 * Address validation only makes sense for a user process. The lock must
+	 * be obtained before validation can begin.
+	 */
+	mmap_assert_locked(current->mm);
+
+	pgdp = pgd_offset(current->mm, addr);
+
+	if (!pgd_none(*pgdp)) {
+		ptep = lookup_address_in_pgd(pgdp, addr, &level);
+		if (ptep) {
+			unsigned long offset;
+
+			if (!pte_decrypted(*ptep))
+				return -EFAULT;
+
+			offset = addr & ~page_level_mask(level);
+			*phys_addr = PFN_PHYS(pte_pfn(*ptep));
+			*phys_addr |= offset;
+
+			*writable = pte_write(*ptep);
+
+			return 0;
+		}
+	}
+
+	return -EFAULT;
+}
+
+static int valid_vaddr(struct ve_info *ve, enum insn_mmio_type mmio, int size,
+		       unsigned long vaddr)
+{
+	phys_addr_t phys_addr;
+	bool writable = false;
+
+	/* It's not fatal. This can happen due to swap out or page migration. */
+	if (get_phys_addr(vaddr, &phys_addr, &writable) || (ve->gpa != cc_mkdec(phys_addr)))
+		return -EAGAIN;
+
+	/*
+	 * Re-check whether #VE info matches the instruction that was decoded.
+	 *
+	 * The ve->gpa was valid at the time ve_info was received. But this code
+	 * executed with interrupts enabled, allowing tlb shootdown and therefore
+	 * munmap() to be executed in the parallel thread.
+	 *
+	 * By the time MMIO emulation is performed, ve->gpa may be already
+	 * unmapped from the process, the device it belongs to removed from
+	 * system and something else could be plugged in its place.
+	 */
+	switch (mmio) {
+	case INSN_MMIO_WRITE:
+	case INSN_MMIO_WRITE_IMM:
+		if (!writable || !(ve->exit_qual & EPT_VIOLATION_ACC_WRITE))
+			return -EFAULT;
+		break;
+	case INSN_MMIO_READ:
+	case INSN_MMIO_READ_ZERO_EXTEND:
+	case INSN_MMIO_READ_SIGN_EXTEND:
+		if (!(ve->exit_qual & EPT_VIOLATION_ACC_READ))
+			return -EFAULT;
+		break;
+	default:
+		WARN_ONCE(1, "Unsupported mmio instruction: %d", mmio);
+		return -EINVAL;
+	}
+
+	return 0;
+}
+
 static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
 			     struct pt_regs *regs, struct ve_info *ve)
 {
@@ -494,7 +576,7 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
 	unsigned long vaddr;
-	int size;
+	int size, ret;
 
 	/* Only in-kernel MMIO is supported */
 	if (WARN_ON_ONCE(user_mode(regs)))
@@ -513,6 +595,16 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (!user_mode(regs) && !is_kernel_addr(ve->gla)) {
 		WARN_ONCE(1, "Access to userspace address is not supported");
 		return -EINVAL;
+
+	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
+
+	if (user_mode(regs)) {
+		if (mmap_read_lock_killable(current->mm))
+			return -EINTR;
+
+		ret = valid_vaddr(ve, mmio, size, vaddr);
+		if (ret)
+			goto unlock;
 	}
 
 	/*
@@ -524,30 +616,39 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	 *
 	 * load_unaligned_zeropad() will recover using exception fixups.
 	 */
-	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
-	if (vaddr / PAGE_SIZE != (vaddr + size - 1) / PAGE_SIZE)
-		return -EFAULT;
+	if (vaddr / PAGE_SIZE != (vaddr + size - 1) / PAGE_SIZE) {
+		ret = -EFAULT;
+		goto unlock;
+	}
 
 	switch (mmio) {
 	case INSN_MMIO_WRITE:
 	case INSN_MMIO_WRITE_IMM:
 	case INSN_MMIO_MOVS:
-		return handle_mmio_write(&insn, mmio, size, regs, ve);
+		ret = handle_mmio_write(&insn, mmio, size, regs, ve);
+		break;
 	case INSN_MMIO_READ:
 	case INSN_MMIO_READ_ZERO_EXTEND:
 	case INSN_MMIO_READ_SIGN_EXTEND:
-		return handle_mmio_read(&insn, mmio, size, regs, ve);
+		ret = handle_mmio_read(&insn, mmio, size, regs, ve);
+		break;
 	case INSN_MMIO_DECODE_FAILED:
 		/*
 		 * MMIO was accessed with an instruction that could not be
 		 * decoded or handled properly. It was likely not using io.h
 		 * helpers or accessed MMIO accidentally.
 		 */
-		return -EINVAL;
+		ret = -EINVAL;
+		break;
 	default:
 		WARN_ONCE(1, "Unknown insn_decode_mmio() decode value?");
-		return -EINVAL;
+		ret = -EINVAL;
 	}
+unlock:
+	if (user_mode(regs))
+		mmap_read_unlock(current->mm);
+
+	return ret;
 }
 
 static bool handle_in(struct pt_regs *regs, int size, int port)
@@ -691,11 +792,6 @@ static int virt_exception_user(struct pt_regs *regs, struct ve_info *ve)
 	}
 }
 
-static inline bool is_private_gpa(u64 gpa)
-{
-	return gpa == cc_mkenc(gpa);
-}
-
 /*
  * Handle the kernel #VE.
  *
@@ -733,6 +829,14 @@ bool tdx_handle_virt_exception(struct pt_regs *regs, struct ve_info *ve)
 		insn_len = virt_exception_user(regs, ve);
 	else
 		insn_len = virt_exception_kernel(regs, ve);
+
+	/*
+	 * A special case to return to userspace without increasing regs->ip
+	 * to repeat the instruction once again.
+	 */
+	if (insn_len == -EAGAIN)
+		return true;
+
 	if (insn_len < 0)
 		return false;

---

## [80] Alexey Gladkov — 2024-09-06
*Subject: [PATCH v6 4/6] x86/tdx: Allow MMIO from userspace*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

The MMIO emulation is only allowed for kernel space code. It is carried
out through a special API, which uses only certain instructions.

This does not allow userspace to work with virtual devices.

Allow userspace to use the same instructions as kernel space to access
MMIO. Additional checks have been added previously.

Reviewed-by: Thomas Gleixner <tglx@linutronix.de>
Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 43 +++++++++++++++++++++++++++++++----------
 1 file changed, 33 insertions(+), 10 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 636bf4013ef2..1e391897e34f 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -492,6 +492,32 @@ static int valid_vaddr(struct ve_info *ve, enum insn_mmio_type mmio, int size,
 	return 0;
 }
 
+static int decode_insn_struct(struct insn *insn, struct pt_regs *regs)
+{
+	char buffer[MAX_INSN_SIZE];
+
+	if (user_mode(regs)) {
+		int nr_copied = insn_fetch_from_user(regs, buffer);
+
+		if (nr_copied <= 0)
+			return -EFAULT;
+
+		if (!insn_decode_from_regs(insn, regs, buffer, nr_copied))
+			return -EINVAL;
+	} else {
+		if (copy_from_kernel_nofault(buffer, (void *)regs->ip, MAX_INSN_SIZE))
+			return -EFAULT;
+
+		if (insn_decode(insn, buffer, MAX_INSN_SIZE, INSN_MODE_64))
+			return -EINVAL;
+	}
+
+	if (!insn->immediate.got)
+		return -EINVAL;
+
+	return 0;
+}
+
 static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
 			     struct pt_regs *regs, struct ve_info *ve)
 {
@@ -572,21 +598,14 @@ static int handle_mmio_read(struct insn *insn, enum insn_mmio_type mmio, int siz
 
 static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 {
-	char buffer[MAX_INSN_SIZE];
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
 	unsigned long vaddr;
 	int size, ret;
 
-	/* Only in-kernel MMIO is supported */
-	if (WARN_ON_ONCE(user_mode(regs)))
-		return -EFAULT;
-
-	if (copy_from_kernel_nofault(buffer, (void *)regs->ip, MAX_INSN_SIZE))
-		return -EFAULT;
-
-	if (insn_decode(&insn, buffer, MAX_INSN_SIZE, INSN_MODE_64))
-		return -EINVAL;
+	ret = decode_insn_struct(&insn, regs);
+	if (ret)
+		return ret;
 
 	mmio = insn_decode_mmio(&insn, &size);
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
@@ -786,6 +805,10 @@ static int virt_exception_user(struct pt_regs *regs, struct ve_info *ve)
 	switch (ve->exit_reason) {
 	case EXIT_REASON_CPUID:
 		return handle_cpuid(regs, ve);
+	case EXIT_REASON_EPT_VIOLATION:
+		if (is_private_gpa(ve->gpa))
+			panic("Unexpected EPT-violation on private memory.");
+		return handle_mmio(regs, ve);
 	default:
 		pr_warn("Unexpected #VE: %lld\n", ve->exit_reason);
 		return -EIO;

---

## [81] Alexey Gladkov — 2024-09-06
*Subject: [PATCH v6 5/6] x86/tdx: Move MMIO helpers to common library*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

AMD code has helpers that are used to emulate MOVS instructions. To be
able to reuse this code in the MOVS implementation for intel, it is
necessary to move them to a common location.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/sev/core.c  | 139 ++++++--------------------------------
 arch/x86/include/asm/io.h |   3 +
 arch/x86/lib/iomem.c      | 115 +++++++++++++++++++++++++++++++
 3 files changed, 140 insertions(+), 117 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 082d61d85dfc..07e9a6f15fba 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -369,72 +369,24 @@ static enum es_result vc_decode_insn(struct es_em_ctxt *ctxt)
 static enum es_result vc_write_mem(struct es_em_ctxt *ctxt,
 				   char *dst, char *buf, size_t size)
 {
-	unsigned long error_code = X86_PF_PROT | X86_PF_WRITE;
+	unsigned long error_code;
+	int ret;
 
 	/*
-	 * This function uses __put_user() independent of whether kernel or user
-	 * memory is accessed. This works fine because __put_user() does no
-	 * sanity checks of the pointer being accessed. All that it does is
-	 * to report when the access failed.
-	 *
-	 * Also, this function runs in atomic context, so __put_user() is not
-	 * allowed to sleep. The page-fault handler detects that it is running
-	 * in atomic context and will not try to take mmap_sem and handle the
-	 * fault, so additional pagefault_enable()/disable() calls are not
-	 * needed.
-	 *
-	 * The access can't be done via copy_to_user() here because
-	 * vc_write_mem() must not use string instructions to access unsafe
-	 * memory. The reason is that MOVS is emulated by the #VC handler by
-	 * splitting the move up into a read and a write and taking a nested #VC
-	 * exception on whatever of them is the MMIO access. Using string
-	 * instructions here would cause infinite nesting.
+	 * This function runs in atomic context, so __put_iomem() is not allowed
+	 * to sleep. The page-fault handler detects that it is running in atomic
+	 * context and will not try to take mmap_lock and handle the fault, so
+	 * additional pagefault_enable()/disable() calls are not needed.
 	 */
-	switch (size) {
-	case 1: {
-		u8 d1;
-		u8 __user *target = (u8 __user *)dst;
-
-		memcpy(&d1, buf, 1);
-		if (__put_user(d1, target))
-			goto fault;
-		break;
-	}
-	case 2: {
-		u16 d2;
-		u16 __user *target = (u16 __user *)dst;
-
-		memcpy(&d2, buf, 2);
-		if (__put_user(d2, target))
-			goto fault;
-		break;
-	}
-	case 4: {
-		u32 d4;
-		u32 __user *target = (u32 __user *)dst;
-
-		memcpy(&d4, buf, 4);
-		if (__put_user(d4, target))
-			goto fault;
-		break;
-	}
-	case 8: {
-		u64 d8;
-		u64 __user *target = (u64 __user *)dst;
+	ret = __put_iomem(dst, buf, size);
+	if (!ret)
+		return ES_OK;
 
-		memcpy(&d8, buf, 8);
-		if (__put_user(d8, target))
-			goto fault;
-		break;
-	}
-	default:
-		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+	if (ret == -EIO)
 		return ES_UNSUPPORTED;
-	}
 
-	return ES_OK;
+	error_code = X86_PF_PROT | X86_PF_WRITE;
 
-fault:
 	if (user_mode(ctxt->regs))
 		error_code |= X86_PF_USER;
 
@@ -448,71 +400,24 @@ static enum es_result vc_write_mem(struct es_em_ctxt *ctxt,
 static enum es_result vc_read_mem(struct es_em_ctxt *ctxt,
 				  char *src, char *buf, size_t size)
 {
-	unsigned long error_code = X86_PF_PROT;
+	unsigned long error_code;
+	int ret;
 
 	/*
-	 * This function uses __get_user() independent of whether kernel or user
-	 * memory is accessed. This works fine because __get_user() does no
-	 * sanity checks of the pointer being accessed. All that it does is
-	 * to report when the access failed.
-	 *
-	 * Also, this function runs in atomic context, so __get_user() is not
-	 * allowed to sleep. The page-fault handler detects that it is running
-	 * in atomic context and will not try to take mmap_sem and handle the
-	 * fault, so additional pagefault_enable()/disable() calls are not
-	 * needed.
-	 *
-	 * The access can't be done via copy_from_user() here because
-	 * vc_read_mem() must not use string instructions to access unsafe
-	 * memory. The reason is that MOVS is emulated by the #VC handler by
-	 * splitting the move up into a read and a write and taking a nested #VC
-	 * exception on whatever of them is the MMIO access. Using string
-	 * instructions here would cause infinite nesting.
+	 * This function runs in atomic context, so __get_iomem() is not allowed
+	 * to sleep. The page-fault handler detects that it is running in atomic
+	 * context and will not try to take mmap_lock and handle the fault, so
+	 * additional pagefault_enable()/disable() calls are not needed.
 	 */
-	switch (size) {
-	case 1: {
-		u8 d1;
-		u8 __user *s = (u8 __user *)src;
-
-		if (__get_user(d1, s))
-			goto fault;
-		memcpy(buf, &d1, 1);
-		break;
-	}
-	case 2: {
-		u16 d2;
-		u16 __user *s = (u16 __user *)src;
-
-		if (__get_user(d2, s))
-			goto fault;
-		memcpy(buf, &d2, 2);
-		break;
-	}
-	case 4: {
-		u32 d4;
-		u32 __user *s = (u32 __user *)src;
+	ret = __get_iomem(src, buf, size);
+	if (!ret)
+		return ES_OK;
 
-		if (__get_user(d4, s))
-			goto fault;
-		memcpy(buf, &d4, 4);
-		break;
-	}
-	case 8: {
-		u64 d8;
-		u64 __user *s = (u64 __user *)src;
-		if (__get_user(d8, s))
-			goto fault;
-		memcpy(buf, &d8, 8);
-		break;
-	}
-	default:
-		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+	if (ret == -EIO)
 		return ES_UNSUPPORTED;
-	}
 
-	return ES_OK;
+	error_code = X86_PF_PROT;
 
-fault:
 	if (user_mode(ctxt->regs))
 		error_code |= X86_PF_USER;
 
diff --git a/arch/x86/include/asm/io.h b/arch/x86/include/asm/io.h
index 1d60427379c9..ac01d53466cb 100644
--- a/arch/x86/include/asm/io.h
+++ b/arch/x86/include/asm/io.h
@@ -402,4 +402,7 @@ static inline void iosubmit_cmds512(void __iomem *dst, const void *src,
 	}
 }
 
+int __get_iomem(char *src, char *buf, size_t size);
+int __put_iomem(char *src, char *buf, size_t size);
+
 #endif /* _ASM_X86_IO_H */
diff --git a/arch/x86/lib/iomem.c b/arch/x86/lib/iomem.c
index 5eecb45d05d5..3ab146edddea 100644
--- a/arch/x86/lib/iomem.c
+++ b/arch/x86/lib/iomem.c
@@ -2,6 +2,7 @@
 #include <linux/module.h>
 #include <linux/io.h>
 #include <linux/kmsan-checks.h>
+#include <asm/uaccess.h>
 
 #define movs(type,to,from) \
 	asm volatile("movs" type:"=&D" (to), "=&S" (from):"0" (to), "1" (from):"memory")
@@ -124,3 +125,117 @@ void memset_io(volatile void __iomem *a, int b, size_t c)
 	}
 }
 EXPORT_SYMBOL(memset_io);
+
+int __get_iomem(char *src, char *buf, size_t size)
+{
+	/*
+	 * This function uses __get_user() independent of whether kernel or user
+	 * memory is accessed. This works fine because __get_user() does no
+	 * sanity checks of the pointer being accessed. All that it does is
+	 * to report when the access failed.
+	 *
+	 * The access can't be done via copy_from_user() here because
+	 * __get_iomem() must not use string instructions to access unsafe
+	 * memory. The reason is that MOVS is emulated by the exception handler
+	 * for SEV and TDX by splitting the move up into a read and a write
+	 * opetations and taking a nested exception on whatever of them is the
+	 * MMIO access. Using string instructions here would cause infinite
+	 * nesting.
+	 */
+	switch (size) {
+	case 1: {
+		u8 d1, __user *s = (u8 __user *)src;
+
+		if (__get_user(d1, s))
+			return -EFAULT;
+		memcpy(buf, &d1, 1);
+		break;
+	}
+	case 2: {
+		u16 d2, __user *s = (u16 __user *)src;
+
+		if (__get_user(d2, s))
+			return -EFAULT;
+		memcpy(buf, &d2, 2);
+		break;
+	}
+	case 4: {
+		u32 d4, __user *s = (u32 __user *)src;
+
+		if (__get_user(d4, s))
+			return -EFAULT;
+		memcpy(buf, &d4, 4);
+		break;
+	}
+	case 8: {
+		u64 d8, __user *s = (u64 __user *)src;
+
+		if (__get_user(d8, s))
+			return -EFAULT;
+		memcpy(buf, &d8, 8);
+		break;
+	}
+	default:
+		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+		return -EIO;
+	}
+
+	return 0;
+}
+
+int __put_iomem(char *dst, char *buf, size_t size)
+{
+	/*
+	 * This function uses __put_user() independent of whether kernel or user
+	 * memory is accessed. This works fine because __put_user() does no
+	 * sanity checks of the pointer being accessed. All that it does is
+	 * to report when the access failed.
+	 *
+	 * The access can't be done via copy_to_user() here because
+	 * __put_iomem() must not use string instructions to access unsafe
+	 * memory. The reason is that MOVS is emulated by the exception handler
+	 * for SEV and TDX by splitting the move up into a read and a write
+	 * opetations and taking a nested exception on whatever of them is the
+	 * MMIO access. Using string instructions here would cause infinite
+	 * nesting.
+	 */
+	switch (size) {
+	case 1: {
+		u8 d1, __user *target = (u8 __user *)dst;
+
+		memcpy(&d1, buf, 1);
+		if (__put_user(d1, target))
+			return -EFAULT;
+		break;
+	}
+	case 2: {
+		u16 d2, __user *target = (u16 __user *)dst;
+
+		memcpy(&d2, buf, 2);
+		if (__put_user(d2, target))
+			return -EFAULT;
+		break;
+	}
+	case 4: {
+		u32 d4, __user *target = (u32 __user *)dst;
+
+		memcpy(&d4, buf, 4);
+		if (__put_user(d4, target))
+			return -EFAULT;
+		break;
+	}
+	case 8: {
+		u64 d8, __user *target = (u64 __user *)dst;
+
+		memcpy(&d8, buf, 8);
+		if (__put_user(d8, target))
+			return -EFAULT;
+		break;
+	}
+	default:
+		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+		return -EIO;
+	}
+
+	return 0;
+}

---

## [82] Alexey Gladkov — 2024-09-06
*Subject: [PATCH v6 6/6] x86/tdx: Implement MOVS for MMIO*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Add emulation of the MOVS instruction on MMIO regions. MOVS emulation
consists of dividing it into a series of read and write operations,
which in turn will be validated separately.

This implementation is based on the same principle as in SEV. It splits
MOVS into separate read and write operations, which in turn can cause
nested #VEs depending on which of the arguments caused the first #VE.

The difference with the SEV implementation is the execution context. SEV
code is executed in atomic context. Exception handler in TDX is executed
with interrupts enabled. That's why the approach to locking is
different. In TDX, mmap_lock is taken to verify and emulate the
instruction.

Another difference is how the read and write instructions are executed
for MOVS emulation. While in SEV each read/write operation returns to
user space, in TDX these operations are performed from the kernel
context.

It may be possible to achieve more code reuse at this point,
but it would require confirmation from SEV that such a thing wouldn't
break anything.

Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c          | 83 +++++++++++++++++++++++++++++---
 arch/x86/include/asm/processor.h |  3 ++
 2 files changed, 78 insertions(+), 8 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 1e391897e34f..7e760f03fa1e 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -518,6 +518,60 @@ static int decode_insn_struct(struct insn *insn, struct pt_regs *regs)
 	return 0;
 }
 
+static int handle_mmio_movs(struct insn *insn, struct pt_regs *regs, int size, struct ve_info *ve)
+{
+	unsigned long ds_base, es_base;
+	unsigned char *src, *dst;
+	unsigned char buffer[8];
+	int off, ret;
+	bool rep;
+
+	/*
+	 * The in-kernel code must use a special API that does not use MOVS.
+	 * If the MOVS instruction is received from in-kernel, then something
+	 * is broken.
+	 */
+	if (WARN_ON_ONCE(!user_mode(regs)))
+		return -EFAULT;
+
+	ds_base = insn_get_seg_base(regs, INAT_SEG_REG_DS);
+	es_base = insn_get_seg_base(regs, INAT_SEG_REG_ES);
+
+	if (ds_base == -1L || es_base == -1L)
+		return -EINVAL;
+
+	current->thread.in_mmio_emul = 1;
+
+	rep = insn_has_rep_prefix(insn);
+
+	do {
+		src = ds_base + (unsigned char *) regs->si;
+		dst = es_base + (unsigned char *) regs->di;
+
+		ret = __get_iomem(src, buffer, size);
+		if (ret)
+			goto out;
+
+		ret = __put_iomem(dst, buffer, size);
+		if (ret)
+			goto out;
+
+		off = (regs->flags & X86_EFLAGS_DF) ? -size : size;
+
+		regs->si += off;
+		regs->di += off;
+
+		if (rep)
+			regs->cx -= 1;
+	} while (rep || regs->cx > 0);
+
+	ret = insn->length;
+out:
+	current->thread.in_mmio_emul = 0;
+
+	return ret;
+}
+
 static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
 			     struct pt_regs *regs, struct ve_info *ve)
 {
@@ -539,9 +593,8 @@ static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int si
 		return insn->length;
 	case INSN_MMIO_MOVS:
 		/*
-		 * MMIO was accessed with an instruction that could not be
-		 * decoded or handled properly. It was likely not using io.h
-		 * helpers or accessed MMIO accidentally.
+		 * MOVS is processed through higher level emulation which breaks
+		 * this instruction into a sequence of reads and writes.
 		 */
 		return -EINVAL;
 	default:
@@ -600,6 +653,7 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 {
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
+	int need_validation;
 	unsigned long vaddr;
 	int size, ret;
 
@@ -611,13 +665,27 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
+	if (mmio == INSN_MMIO_MOVS)
+		return handle_mmio_movs(&insn, regs, size, ve);
+
+	need_validation = user_mode(regs);
+
 	if (!user_mode(regs) && !is_kernel_addr(ve->gla)) {
-		WARN_ONCE(1, "Access to userspace address is not supported");
-		return -EINVAL;
+		/*
+		 * Access from kernel to userspace addresses is not allowed
+		 * unless it is a nested exception during MOVS emulation.
+		 */
+		if (!current->thread.in_mmio_emul || !current->mm) {
+			WARN_ONCE(1, "Access to userspace address is not supported");
+			return -EINVAL;
+		}
+
+		need_validation = 1;
+	}
 
 	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
 
-	if (user_mode(regs)) {
+	if (need_validation) {
 		if (mmap_read_lock_killable(current->mm))
 			return -EINTR;
 
@@ -643,7 +711,6 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	switch (mmio) {
 	case INSN_MMIO_WRITE:
 	case INSN_MMIO_WRITE_IMM:
-	case INSN_MMIO_MOVS:
 		ret = handle_mmio_write(&insn, mmio, size, regs, ve);
 		break;
 	case INSN_MMIO_READ:
@@ -664,7 +731,7 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 		ret = -EINVAL;
 	}
 unlock:
-	if (user_mode(regs))
+	if (need_validation)
 		mmap_read_unlock(current->mm);
 
 	return ret;
diff --git a/arch/x86/include/asm/processor.h b/arch/x86/include/asm/processor.h
index a75a07f4931f..33875a217ed8 100644
--- a/arch/x86/include/asm/processor.h
+++ b/arch/x86/include/asm/processor.h
@@ -486,6 +486,9 @@ struct thread_struct {
 	unsigned long		iopl_emul;
 
 	unsigned int		iopl_warn:1;
+#ifdef CONFIG_INTEL_TDX_GUEST
+	unsigned int		in_mmio_emul:1;
+#endif
 
 	/*
 	 * Protection Keys Register for Userspace.  Loaded immediately on

---

## [83] Dave Hansen — 2024-09-06
*Subject: Re: [PATCH v6 0/6] x86/tdx: Allow MMIO instructions from userspace*

On 9/6/24 04:49, Alexey Gladkov wrote:
> Currently, MMIO inside the TDX guest is allowed from kernel space and access
> from userspace is denied. This becomes a problem when working with virtual

Kernel MMIO and User MMIO are very different beasts.

The kernel MMIO instructions are trusted and can be constrained to use a
very limited number of instructions that match the kernel's limited
instruction decoding capability.

Userspace is not constrained in that way.

TDX also doesn't have the option of having the VMM deal with the
instruction emulation.

Before we start down this road, I'd really want to hear from the KVM
folks that having the kernel decode arbitrary user instructions is the
way we want to go.

---

## [84] Sean Christopherson — 2024-09-06
*Subject: Re: [PATCH v6 0/6] x86/tdx: Allow MMIO instructions from userspace*

On Fri, Sep 06, 2024, Dave Hansen wrote:
> On 9/6/24 04:49, Alexey Gladkov wrote:
> > Currently, MMIO inside the TDX guest is allowed from kernel space and access

That's an x86 kernel decision, not a KVM decision.  KVM cares if the guest kernel
has delegated certain permissions to userspace, which is why emulated MMIO is
preferred over hypercalls; the fact that userspace can access an MMIO region
communicates to KVM that the guest kernel has granted userspace the necessary
permissions (by mapping the MMIO region into the user page tables).

But whether or not a particular user/application is trusted by the guest kernel
is firmly out of scope for KVM.  KVM's responsibility is to not undermine the
guest kernel's security/trust model, but KVM doesn't define that model.

Ditto for what behavior is supported/allowed.  The kernel could choose to disallow
userspace MMIO entirely, limit what instructions are supported, etc, in the name
of security, simplicity, or whatever.   Doing so would likely cause friction with
folks that want to run their workloads in an SNP/TDX VM, but that friction is very
much with the guest kernel, not with KVM.

FWIW, emulating MMIO that isn't controlled by the kernel gets to be a bit of a
slippery slope, e.g. there are KVM patches on the list to support emulating AVX
instructions[*].  But, a major use case of any hypervisor is to lift-and-shift
workloads, and so KVM users, developers, and maintainers are quite motivated to
ensure that anything that works on bare metal also works on KVM.

---

## [85] Kirill A. Shutemov — 2024-09-09
*Subject: Re: [PATCH v5 6/6] x86/tdx: Implement MOVS for MMIO*

On Thu, Aug 29, 2024 at 08:40:56PM +0200, Alexey Gladkov wrote:
> On Thu, Aug 29, 2024 at 03:44:55PM +0300, Kirill A. Shutemov wrote:
> > On Wed, Aug 28, 2024 at 12:44:36PM +0200, Alexey Gladkov wrote:

You are right. I didn't see this codepath.

---

## [86] Kirill A. Shutemov — 2024-09-09
*Subject: Re: [PATCH v6 5/6] x86/tdx: Move MMIO helpers to common library*

On Fri, Sep 06, 2024 at 01:50:03PM +0200, Alexey Gladkov wrote:
> From: "Alexey Gladkov (Intel)" <legion@kernel.org>
> 

Acked-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

---

## [87] Kirill A. Shutemov — 2024-09-09
*Subject: Re: [PATCH v6 6/6] x86/tdx: Implement MOVS for MMIO*

On Fri, Sep 06, 2024 at 01:50:04PM +0200, Alexey Gladkov wrote:
> diff --git a/arch/x86/include/asm/processor.h b/arch/x86/include/asm/processor.h
> index a75a07f4931f..33875a217ed8 100644

This ifdeffery doesn't help anybody. Just drop it.

Otherwise looks good to me:

Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

---

## [88] Dave Hansen — 2024-09-10
*Subject: Re: [PATCH v6 1/6] x86/tdx: Fix "in-kernel MMIO" check*

On 9/6/24 04:49, Alexey Gladkov wrote:
> +static inline bool is_kernel_addr(unsigned long addr)
> +{

Should we really be open-coding a "is_kernel_addr" check?  I mean,
TASK_SIZE_MAX is there for a reason.  While I doubt we'd ever change the
positive vs. negative address space convention on 64-bit, I don't see a
good reason to write a 64-bit x86-specific is_kernel_addr() when a more
generic, portable and conventional idiom would do.

So, please use either a:

	addr < TASK_SIZE_MAX

check, or use fault_in_kernel_space() directly.

---

## [89] Kirill A. Shutemov — 2024-09-10
*Subject: Re: [PATCH v6 1/6] x86/tdx: Fix "in-kernel MMIO" check*

On Fri, Sep 06, 2024 at 01:49:59PM +0200, Alexey Gladkov wrote:
> From: "Alexey Gladkov (Intel)" <legion@kernel.org>
> 

Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

---

## [90] Alexey Gladkov — 2024-09-11
*Subject: Re: [PATCH v6 1/6] x86/tdx: Fix "in-kernel MMIO" check*

On Tue, Sep 10, 2024 at 12:54:19PM -0700, Dave Hansen wrote:
> On 9/6/24 04:49, Alexey Gladkov wrote:
> > +static inline bool is_kernel_addr(unsigned long addr)

I took arch/x86/events/perf_event.h:1262 as an example. There is no
special reason in its own function.

> So, please use either a:
> 

I'll use fault_in_kernel_space() since SEV uses it. Thanks.

---

## [91] Kirill A. Shutemov — 2024-09-11
*Subject: Re: [PATCH v6 1/6] x86/tdx: Fix "in-kernel MMIO" check*

On Wed, Sep 11, 2024 at 02:08:47PM +0200, Alexey Gladkov wrote:
> On Tue, Sep 10, 2024 at 12:54:19PM -0700, Dave Hansen wrote:
> > On 9/6/24 04:49, Alexey Gladkov wrote:

Also user_mode() check is redundant until later in the patchset. Move it
to the patch that allows userspace MMIO.

---

## [92] Dave Hansen — 2024-09-11
*Subject: Re: [PATCH v6 0/6] x86/tdx: Allow MMIO instructions from userspace*

On 9/6/24 14:13, Sean Christopherson wrote:
> Ditto for what behavior is supported/allowed.  The kernel could choose to disallow
> userspace MMIO entirely, limit what instructions are supported, etc, in the name

I think by "guest kernel" you really mean "x86 maintainers".  Thanks for
throwing us under the bus, Sean. ;)

I do agree with you, though.  In the process of taking the VMM out of
the TCB, confidential computing has to fill the gap with _something_ and
that something is usually arch-specific code in the guest kernel.

By dragging the KVM folks in here, I was less asking what KVM does per
se and more asking for some advice from the experienced VMM folks.

> FWIW, emulating MMIO that isn't controlled by the kernel gets to be a bit of a
> slippery slope, e.g. there are KVM patches on the list to support emulating AVX

Do you have a link for that AVX discussion?  I searched a bit but came
up empty.

The slippery slope is precisely what I'm worried about.  I suspect the
AVX instructions are a combination of compilers that are increasingly
happy to spit out AVX and users who just want to use whatever the
compiler spits out on "pointers" in their apps that just happen to be
pointed at MMIO.

But before we start digging in to avoid the slippery slope, we really do
need to know more about the friction.  Who are we causing it for and how
bad is it for them?

---

## [93] Sean Christopherson — 2024-09-11
*Subject: Re: [PATCH v6 0/6] x86/tdx: Allow MMIO instructions from userspace*

On Wed, Sep 11, 2024, Dave Hansen wrote:
> On 9/6/24 14:13, Sean Christopherson wrote:
> > Ditto for what behavior is supported/allowed.  The kernel could choose to disallow

Heh, I would argue that you tried to push me under the bus, but I'm slippery fast
and danced out of the way, and you got hit instead :-D

> I do agree with you, though.  In the process of taking the VMM out of
> the TCB, confidential computing has to fill the gap with _something_ and

Gah, of course I forgot to paste the link.

https://lore.kernel.org/all/20240820230431.3850991-1-kbusch@meta.com

> The slippery slope is precisely what I'm worried about.  I suspect the
> AVX instructions are a combination of compilers that are increasingly

Yep.  Based on the original report[*], it sounds like the userspace program is
doing a memcpy(), so it's hard to even argue that userspace is being silly.

[*] https://lore.kernel.org/kvm/20240304145932.4e685a38.alex.williamson@redhat.com

> But before we start digging in to avoid the slippery slope, we really do
> need to know more about the friction.  Who are we causing it for and how

This type of issue will most likely show up in the form of an end customer moving
their workload into a TDX/SNP VM, and that workload crashing despite working just
fine when run in a regular VM.

One "answer" could be to tell users that they need to recompile with AVX+
explicitly disabled, but that's an answer that will make everyone unhappy.  E.g.
customers won't like recompiling, CSPs don't like unhappy customers, and CSPs and
hardware vendors don't want their CoCo solutions to be hard(er) to adopt.

---

## [94] Kirill A. Shutemov — 2024-09-12
*Subject: Re: [PATCH v6 0/6] x86/tdx: Allow MMIO instructions from userspace*

On Wed, Sep 11, 2024 at 09:19:04AM -0700, Sean Christopherson wrote:
> Yep.  Based on the original report[*], it sounds like the userspace program is
> doing a memcpy(), so it's hard to even argue that userspace is being silly.

The kernel does MMIO accesses using special helpers that use well-known
instructions. I believe we should educate userspace to do the same by
rejecting emulation of anything more complex than plain loads and stores.
Otherwise these asks will keep coming.

---

## [95] Dave Hansen — 2024-09-12
*Subject: Re: [PATCH v6 0/6] x86/tdx: Allow MMIO instructions from userspace*

On 9/12/24 02:45, Kirill A. Shutemov wrote:
> On Wed, Sep 11, 2024 at 09:19:04AM -0700, Sean Christopherson wrote:
>> Yep.  Based on the original report[*], it sounds like the userspace program is

My assumption is that folks have VMM-specific kernel drivers and crusty
old userspace that mmap()'s an MMIO region exposed by that driver. They
want to keep their old userspace.

Once we're dictating that specific instructions be used, the old
userspace doesn't work and it needs to be changed. Once it needs to be
changed, then some _other_ new ABI might as well be considered.

Basically:

	New ABI =~ Specific Kernel-mandated Instructions

---

## [96] Kirill A. Shutemov — 2024-09-13
*Subject: Re: [PATCH v6 0/6] x86/tdx: Allow MMIO instructions from userspace*

On Thu, Sep 12, 2024 at 08:49:21AM -0700, Dave Hansen wrote:
> On 9/12/24 02:45, Kirill A. Shutemov wrote:
> > On Wed, Sep 11, 2024 at 09:19:04AM -0700, Sean Christopherson wrote:

If we are going to say "no" to userspace MMIO emulation for TDX, the same
has to be done for SEV. Or we can bring TDX to SEV level and draw the line
there.

SEV and TDX run similar workloads and functional difference in this area
is hard to justify.

---

## [97] Dave Hansen — 2024-09-13
*Subject: Re: [PATCH v6 0/6] x86/tdx: Allow MMIO instructions from userspace*

On 9/13/24 08:53, Kirill A. Shutemov wrote:
>> Basically:
>>

Maybe.  We definitely don't want to put any new restrictions on SEV
because folks would update their kernel and old userspace would break.

Or maybe we start enforcing things at >=SEV-SNP and TDX and just say
that security model has changed too much to allow the old userspace.

---

## [98] Sean Christopherson — 2024-09-13
*Subject: Re: [PATCH v6 0/6] x86/tdx: Allow MMIO instructions from userspace*

On Fri, Sep 13, 2024, Dave Hansen wrote:
> On 9/13/24 08:53, Kirill A. Shutemov wrote:
> >> Basically:

Note, SEV-MEM, a.k.a. the original SEV, isn't in scope because instruction decoding
is still handled by the hypervisor.  SEV-ES is where the guest kernel first gets
involved.

> because folks would update their kernel and old userspace would break.
> 

Heh, that's an outright lie though.  Nothing relevant has changed between SEV-ES
and SEV-SNP that makes old userspace any less secure, or makes it harder for the
kernel to support decoding instructions on SNP vs. ES.

I also don't know that this is for old userspace.  AFAIK, the most common case
for userspace triggering emulated MMIO is when a device is passed to userspace
via VFIO/IOMMUFD, e.g. a la DPDK.

---

## [99] Dave Hansen — 2024-09-13
*Subject: Re: [PATCH v6 0/6] x86/tdx: Allow MMIO instructions from userspace*

On 9/13/24 09:28, Sean Christopherson wrote:
>> because folks would update their kernel and old userspace would break.
>>

The trust model does change, though.

The VMM is still in the guest TCB for SEV-ES because there are *so* many
ways to leverage NPT to compromise a VM.  Yeah, the data isn't in plain
view of the VMM, but that doesn't mean the VMM is out of the TCB.

With SEV-ES, old crusty userspace is doing MMIO to a VMM in the TCB.

With SEV-SNP, old crusty userspace is talking to an untrusted VMM.

I think that's how the security model changes.

> I also don't know that this is for old userspace.  AFAIK, the most common case
> for userspace triggering emulated MMIO is when a device is passed to userspace

Ahh, that would make sense.

It would be nice to hear from those folks _somewhere_ about what their
restrictions are and if they'd ever be able to enforce a subset of the
ISA for MMIO or even (for example) make system calls to do MMIO.

Does it matter to them if all of a sudden the NIC or the NVMe device on
the other side of VFIO is malicious?

---

## [100] Alexey Gladkov — 2024-09-13
*Subject: [PATCH v7 0/6] x86/tdx: Allow MMIO instructions from userspace*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Currently, MMIO inside the TDX guest is allowed from kernel space and access
from userspace is denied. This becomes a problem when working with virtual
devices in userspace.

In TDX guest MMIO instructions are emulated in #VE. The kernel code uses special
helpers to access MMIO memory to limit the number of instructions which are
used.

This patchset makes MMIO accessible from userspace. To do this additional checks
were added to ensure that the emulated instruction will not be compromised.


v7:
- Use fault_in_kernel_space() instead of using your own function as
  suggested by Dave Hansen.
- Drop the unnecessary ifdef CONFIG_INTEL_TDX_GUEST from thread_struct.

v6:
- Reorder patches and change commit messages.

v5:
- Improve commit messages and comments in commits as suggested by Kirill A. Shutemov.
- To emulate MOVS, instead of storing the entire address, started using a flag.

v4:
- Move patches to avoid crossing the page boundary to separate patchset. They
  address separate issue.
- Check the address only in user context and in case of nested exceptions.
- Fix the check that the address does not point to private memory.

v3:
- Add patches to avoid crossing the page boundary when the instruction is read
  and decoded in the TDX, SEV, UMIP.
- Forbid accessing userspace addresses from kernel space. The exception to this
  is when emulating MOVS instructions.
- Fix address validation during MOVS emulation.

v2:
- Split into separate patches AMD helpers extraction and MOVS implementation
  code for intel as suggested by Thomas Gleixner.
- Fix coding style issues.


Alexey Gladkov (Intel) (6):
  x86/tdx: Fix "in-kernel MMIO" check
  x86/tdx: Split MMIO read and write operations
  x86/tdx: Add validation of userspace MMIO instructions
  x86/tdx: Allow MMIO from userspace
  x86/tdx: Move MMIO helpers to common library
  x86/tdx: Implement MOVS for MMIO

 arch/x86/coco/sev/core.c         | 139 ++-----------
 arch/x86/coco/tdx/tdx.c          | 334 ++++++++++++++++++++++++++-----
 arch/x86/include/asm/io.h        |   3 +
 arch/x86/include/asm/processor.h |   1 +
 arch/x86/lib/iomem.c             | 115 +++++++++++
 5 files changed, 423 insertions(+), 169 deletions(-)

---

## [101] Alexey Gladkov — 2024-09-13
*Subject: [PATCH v7 1/6] x86/tdx: Fix "in-kernel MMIO" check*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

TDX only supports kernel-initiated MMIO operations. The handle_mmio()
function checks if the #VE exception occurred in the kernel and rejects
the operation if it did not.

However, userspace can deceive the kernel into performing MMIO on its
behalf. For example, if userspace can point a syscall to an MMIO address,
syscall does get_user() or put_user() on it, triggering MMIO #VE. The
kernel will treat the #VE as in-kernel MMIO.

Ensure that the target MMIO address is within the kernel before decoding
instruction.

Cc: stable@vger.kernel.org
Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 6 ++++++
 1 file changed, 6 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 078e2bac2553..d6e6407e3999 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -16,6 +16,7 @@
 #include <asm/insn-eval.h>
 #include <asm/pgtable.h>
 #include <asm/set_memory.h>
+#include <asm/traps.h>
 
 /* MMIO direction */
 #define EPT_READ	0
@@ -434,6 +435,11 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 			return -EINVAL;
 	}
 
+	if (!fault_in_kernel_space(ve->gla)) {
+		WARN_ONCE(1, "Access to userspace address is not supported");
+		return -EINVAL;
+	}
+
 	/*
 	 * Reject EPT violation #VEs that split pages.
 	 *

---

## [102] Alexey Gladkov — 2024-09-13
*Subject: [PATCH v7 2/6] x86/tdx: Split MMIO read and write operations*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

To implement MMIO in userspace, additional memory checks need to be
implemented. To avoid overly complicating the handle_mmio() function
and to separate checks from actions, it would be better to split this
function into two separate functions to handle read and write
operations.

Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 136 ++++++++++++++++++++++++----------------
 1 file changed, 83 insertions(+), 53 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index d6e6407e3999..008840ac1191 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -406,14 +406,91 @@ static bool mmio_write(int size, unsigned long addr, unsigned long val)
 			       EPT_WRITE, addr, val);
 }
 
+static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
+			     struct pt_regs *regs, struct ve_info *ve)
+{
+	unsigned long *reg, val;
+
+	switch (mmio) {
+	case INSN_MMIO_WRITE:
+		reg = insn_get_modrm_reg_ptr(insn, regs);
+		if (!reg)
+			return -EINVAL;
+		memcpy(&val, reg, size);
+		if (!mmio_write(size, ve->gpa, val))
+			return -EIO;
+		return insn->length;
+	case INSN_MMIO_WRITE_IMM:
+		val = insn->immediate.value;
+		if (!mmio_write(size, ve->gpa, val))
+			return -EIO;
+		return insn->length;
+	case INSN_MMIO_MOVS:
+		/*
+		 * MMIO was accessed with an instruction that could not be
+		 * decoded or handled properly. It was likely not using io.h
+		 * helpers or accessed MMIO accidentally.
+		 */
+		return -EINVAL;
+	default:
+		WARN_ON_ONCE(1);
+		return -EINVAL;
+	}
+
+	return insn->length;
+}
+
+static int handle_mmio_read(struct insn *insn, enum insn_mmio_type mmio, int size,
+			    struct pt_regs *regs, struct ve_info *ve)
+{
+	unsigned long *reg, val;
+	int extend_size;
+	u8 extend_val;
+
+	reg = insn_get_modrm_reg_ptr(insn, regs);
+	if (!reg)
+		return -EINVAL;
+
+	if (!mmio_read(size, ve->gpa, &val))
+		return -EIO;
+
+	extend_val = 0;
+
+	switch (mmio) {
+	case INSN_MMIO_READ:
+		/* Zero-extend for 32-bit operation */
+		extend_size = size == 4 ? sizeof(*reg) : 0;
+		break;
+	case INSN_MMIO_READ_ZERO_EXTEND:
+		/* Zero extend based on operand size */
+		extend_size = insn->opnd_bytes;
+		break;
+	case INSN_MMIO_READ_SIGN_EXTEND:
+		/* Sign extend based on operand size */
+		extend_size = insn->opnd_bytes;
+		if (size == 1 && val & BIT(7))
+			extend_val = 0xFF;
+		else if (size > 1 && val & BIT(15))
+			extend_val = 0xFF;
+		break;
+	default:
+		WARN_ON_ONCE(1);
+		return -EINVAL;
+	}
+
+	if (extend_size)
+		memset(reg, extend_val, extend_size);
+	memcpy(reg, &val, size);
+	return insn->length;
+}
+
 static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 {
-	unsigned long *reg, val, vaddr;
 	char buffer[MAX_INSN_SIZE];
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
-	int size, extend_size;
-	u8 extend_val = 0;
+	unsigned long vaddr;
+	int size;
 
 	/* Only in-kernel MMIO is supported */
 	if (WARN_ON_ONCE(user_mode(regs)))
@@ -429,12 +506,6 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
-	if (mmio != INSN_MMIO_WRITE_IMM && mmio != INSN_MMIO_MOVS) {
-		reg = insn_get_modrm_reg_ptr(&insn, regs);
-		if (!reg)
-			return -EINVAL;
-	}
-
 	if (!fault_in_kernel_space(ve->gla)) {
 		WARN_ONCE(1, "Access to userspace address is not supported");
 		return -EINVAL;
@@ -453,24 +524,15 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (vaddr / PAGE_SIZE != (vaddr + size - 1) / PAGE_SIZE)
 		return -EFAULT;
 
-	/* Handle writes first */
 	switch (mmio) {
 	case INSN_MMIO_WRITE:
-		memcpy(&val, reg, size);
-		if (!mmio_write(size, ve->gpa, val))
-			return -EIO;
-		return insn.length;
 	case INSN_MMIO_WRITE_IMM:
-		val = insn.immediate.value;
-		if (!mmio_write(size, ve->gpa, val))
-			return -EIO;
-		return insn.length;
+	case INSN_MMIO_MOVS:
+		return handle_mmio_write(&insn, mmio, size, regs, ve);
 	case INSN_MMIO_READ:
 	case INSN_MMIO_READ_ZERO_EXTEND:
 	case INSN_MMIO_READ_SIGN_EXTEND:
-		/* Reads are handled below */
-		break;
-	case INSN_MMIO_MOVS:
+		return handle_mmio_read(&insn, mmio, size, regs, ve);
 	case INSN_MMIO_DECODE_FAILED:
 		/*
 		 * MMIO was accessed with an instruction that could not be
@@ -482,38 +544,6 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 		WARN_ONCE(1, "Unknown insn_decode_mmio() decode value?");
 		return -EINVAL;
 	}
-
-	/* Handle reads */
-	if (!mmio_read(size, ve->gpa, &val))
-		return -EIO;
-
-	switch (mmio) {
-	case INSN_MMIO_READ:
-		/* Zero-extend for 32-bit operation */
-		extend_size = size == 4 ? sizeof(*reg) : 0;
-		break;
-	case INSN_MMIO_READ_ZERO_EXTEND:
-		/* Zero extend based on operand size */
-		extend_size = insn.opnd_bytes;
-		break;
-	case INSN_MMIO_READ_SIGN_EXTEND:
-		/* Sign extend based on operand size */
-		extend_size = insn.opnd_bytes;
-		if (size == 1 && val & BIT(7))
-			extend_val = 0xFF;
-		else if (size > 1 && val & BIT(15))
-			extend_val = 0xFF;
-		break;
-	default:
-		/* All other cases has to be covered with the first switch() */
-		WARN_ON_ONCE(1);
-		return -EINVAL;
-	}
-
-	if (extend_size)
-		memset(reg, extend_val, extend_size);
-	memcpy(reg, &val, size);
-	return insn.length;
 }
 
 static bool handle_in(struct pt_regs *regs, int size, int port)

---

## [103] Alexey Gladkov — 2024-09-13
*Subject: [PATCH v7 3/6] x86/tdx: Add validation of userspace MMIO instructions*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Instructions from kernel space are considered trusted. If the MMIO
instruction is from userspace it must be checked.

For userspace instructions, it is need to check that the INSN has not
changed at the time of #VE and before the execution of the instruction.

Once the userspace instruction parsed is enforced that the address
points to mapped memory of current process and that address does not
point to private memory.

After parsing the userspace instruction, it is necessary to ensure that:

1. the operation direction (read/write) corresponds to #VE info;
2. the address still points to mapped memory of current process;
3. the address does not point to private memory.

Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 131 ++++++++++++++++++++++++++++++++++++----
 1 file changed, 118 insertions(+), 13 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 008840ac1191..30651a5af180 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -8,6 +8,7 @@
 #include <linux/export.h>
 #include <linux/io.h>
 #include <linux/kexec.h>
+#include <linux/mm.h>
 #include <asm/coco.h>
 #include <asm/tdx.h>
 #include <asm/vmx.h>
@@ -406,6 +407,87 @@ static bool mmio_write(int size, unsigned long addr, unsigned long val)
 			       EPT_WRITE, addr, val);
 }
 
+static inline bool is_private_gpa(u64 gpa)
+{
+	return gpa == cc_mkenc(gpa);
+}
+
+static int get_phys_addr(unsigned long addr, phys_addr_t *phys_addr, bool *writable)
+{
+	unsigned int level;
+	pgd_t *pgdp;
+	pte_t *ptep;
+
+	/*
+	 * Address validation only makes sense for a user process. The lock must
+	 * be obtained before validation can begin.
+	 */
+	mmap_assert_locked(current->mm);
+
+	pgdp = pgd_offset(current->mm, addr);
+
+	if (!pgd_none(*pgdp)) {
+		ptep = lookup_address_in_pgd(pgdp, addr, &level);
+		if (ptep) {
+			unsigned long offset;
+
+			if (!pte_decrypted(*ptep))
+				return -EFAULT;
+
+			offset = addr & ~page_level_mask(level);
+			*phys_addr = PFN_PHYS(pte_pfn(*ptep));
+			*phys_addr |= offset;
+
+			*writable = pte_write(*ptep);
+
+			return 0;
+		}
+	}
+
+	return -EFAULT;
+}
+
+static int valid_vaddr(struct ve_info *ve, enum insn_mmio_type mmio, int size,
+		       unsigned long vaddr)
+{
+	phys_addr_t phys_addr;
+	bool writable = false;
+
+	/* It's not fatal. This can happen due to swap out or page migration. */
+	if (get_phys_addr(vaddr, &phys_addr, &writable) || (ve->gpa != cc_mkdec(phys_addr)))
+		return -EAGAIN;
+
+	/*
+	 * Re-check whether #VE info matches the instruction that was decoded.
+	 *
+	 * The ve->gpa was valid at the time ve_info was received. But this code
+	 * executed with interrupts enabled, allowing tlb shootdown and therefore
+	 * munmap() to be executed in the parallel thread.
+	 *
+	 * By the time MMIO emulation is performed, ve->gpa may be already
+	 * unmapped from the process, the device it belongs to removed from
+	 * system and something else could be plugged in its place.
+	 */
+	switch (mmio) {
+	case INSN_MMIO_WRITE:
+	case INSN_MMIO_WRITE_IMM:
+		if (!writable || !(ve->exit_qual & EPT_VIOLATION_ACC_WRITE))
+			return -EFAULT;
+		break;
+	case INSN_MMIO_READ:
+	case INSN_MMIO_READ_ZERO_EXTEND:
+	case INSN_MMIO_READ_SIGN_EXTEND:
+		if (!(ve->exit_qual & EPT_VIOLATION_ACC_READ))
+			return -EFAULT;
+		break;
+	default:
+		WARN_ONCE(1, "Unsupported mmio instruction: %d", mmio);
+		return -EINVAL;
+	}
+
+	return 0;
+}
+
 static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
 			     struct pt_regs *regs, struct ve_info *ve)
 {
@@ -490,7 +572,7 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
 	unsigned long vaddr;
-	int size;
+	int size, ret;
 
 	/* Only in-kernel MMIO is supported */
 	if (WARN_ON_ONCE(user_mode(regs)))
@@ -511,6 +593,17 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 		return -EINVAL;
 	}
 
+	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
+
+	if (user_mode(regs)) {
+		if (mmap_read_lock_killable(current->mm))
+			return -EINTR;
+
+		ret = valid_vaddr(ve, mmio, size, vaddr);
+		if (ret)
+			goto unlock;
+	}
+
 	/*
 	 * Reject EPT violation #VEs that split pages.
 	 *
@@ -520,30 +613,39 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	 *
 	 * load_unaligned_zeropad() will recover using exception fixups.
 	 */
-	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
-	if (vaddr / PAGE_SIZE != (vaddr + size - 1) / PAGE_SIZE)
-		return -EFAULT;
+	if (vaddr / PAGE_SIZE != (vaddr + size - 1) / PAGE_SIZE) {
+		ret = -EFAULT;
+		goto unlock;
+	}
 
 	switch (mmio) {
 	case INSN_MMIO_WRITE:
 	case INSN_MMIO_WRITE_IMM:
 	case INSN_MMIO_MOVS:
-		return handle_mmio_write(&insn, mmio, size, regs, ve);
+		ret = handle_mmio_write(&insn, mmio, size, regs, ve);
+		break;
 	case INSN_MMIO_READ:
 	case INSN_MMIO_READ_ZERO_EXTEND:
 	case INSN_MMIO_READ_SIGN_EXTEND:
-		return handle_mmio_read(&insn, mmio, size, regs, ve);
+		ret = handle_mmio_read(&insn, mmio, size, regs, ve);
+		break;
 	case INSN_MMIO_DECODE_FAILED:
 		/*
 		 * MMIO was accessed with an instruction that could not be
 		 * decoded or handled properly. It was likely not using io.h
 		 * helpers or accessed MMIO accidentally.
 		 */
-		return -EINVAL;
+		ret = -EINVAL;
+		break;
 	default:
 		WARN_ONCE(1, "Unknown insn_decode_mmio() decode value?");
-		return -EINVAL;
+		ret = -EINVAL;
 	}
+unlock:
+	if (user_mode(regs))
+		mmap_read_unlock(current->mm);
+
+	return ret;
 }
 
 static bool handle_in(struct pt_regs *regs, int size, int port)
@@ -687,11 +789,6 @@ static int virt_exception_user(struct pt_regs *regs, struct ve_info *ve)
 	}
 }
 
-static inline bool is_private_gpa(u64 gpa)
-{
-	return gpa == cc_mkenc(gpa);
-}
-
 /*
  * Handle the kernel #VE.
  *
@@ -729,6 +826,14 @@ bool tdx_handle_virt_exception(struct pt_regs *regs, struct ve_info *ve)
 		insn_len = virt_exception_user(regs, ve);
 	else
 		insn_len = virt_exception_kernel(regs, ve);
+
+	/*
+	 * A special case to return to userspace without increasing regs->ip
+	 * to repeat the instruction once again.
+	 */
+	if (insn_len == -EAGAIN)
+		return true;
+
 	if (insn_len < 0)
 		return false;

---

## [104] Alexey Gladkov — 2024-09-13
*Subject: [PATCH v7 4/6] x86/tdx: Allow MMIO from userspace*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

The MMIO emulation is only allowed for kernel space code. It is carried
out through a special API, which uses only certain instructions.

This does not allow userspace to work with virtual devices.

Allow userspace to use the same instructions as kernel space to access
MMIO. Additional checks have been added previously.

Reviewed-by: Thomas Gleixner <tglx@linutronix.de>
Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c | 45 +++++++++++++++++++++++++++++++----------
 1 file changed, 34 insertions(+), 11 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 30651a5af180..dffc343e64d7 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -488,6 +488,32 @@ static int valid_vaddr(struct ve_info *ve, enum insn_mmio_type mmio, int size,
 	return 0;
 }
 
+static int decode_insn_struct(struct insn *insn, struct pt_regs *regs)
+{
+	char buffer[MAX_INSN_SIZE];
+
+	if (user_mode(regs)) {
+		int nr_copied = insn_fetch_from_user(regs, buffer);
+
+		if (nr_copied <= 0)
+			return -EFAULT;
+
+		if (!insn_decode_from_regs(insn, regs, buffer, nr_copied))
+			return -EINVAL;
+	} else {
+		if (copy_from_kernel_nofault(buffer, (void *)regs->ip, MAX_INSN_SIZE))
+			return -EFAULT;
+
+		if (insn_decode(insn, buffer, MAX_INSN_SIZE, INSN_MODE_64))
+			return -EINVAL;
+	}
+
+	if (!insn->immediate.got)
+		return -EINVAL;
+
+	return 0;
+}
+
 static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
 			     struct pt_regs *regs, struct ve_info *ve)
 {
@@ -568,27 +594,20 @@ static int handle_mmio_read(struct insn *insn, enum insn_mmio_type mmio, int siz
 
 static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 {
-	char buffer[MAX_INSN_SIZE];
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
 	unsigned long vaddr;
 	int size, ret;
 
-	/* Only in-kernel MMIO is supported */
-	if (WARN_ON_ONCE(user_mode(regs)))
-		return -EFAULT;
-
-	if (copy_from_kernel_nofault(buffer, (void *)regs->ip, MAX_INSN_SIZE))
-		return -EFAULT;
-
-	if (insn_decode(&insn, buffer, MAX_INSN_SIZE, INSN_MODE_64))
-		return -EINVAL;
+	ret = decode_insn_struct(&insn, regs);
+	if (ret)
+		return ret;
 
 	mmio = insn_decode_mmio(&insn, &size);
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
-	if (!fault_in_kernel_space(ve->gla)) {
+	if (!user_mode(regs) && !fault_in_kernel_space(ve->gla)) {
 		WARN_ONCE(1, "Access to userspace address is not supported");
 		return -EINVAL;
 	}
@@ -783,6 +802,10 @@ static int virt_exception_user(struct pt_regs *regs, struct ve_info *ve)
 	switch (ve->exit_reason) {
 	case EXIT_REASON_CPUID:
 		return handle_cpuid(regs, ve);
+	case EXIT_REASON_EPT_VIOLATION:
+		if (is_private_gpa(ve->gpa))
+			panic("Unexpected EPT-violation on private memory.");
+		return handle_mmio(regs, ve);
 	default:
 		pr_warn("Unexpected #VE: %lld\n", ve->exit_reason);
 		return -EIO;

---

## [105] Alexey Gladkov — 2024-09-13
*Subject: [PATCH v7 5/6] x86/tdx: Move MMIO helpers to common library*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

AMD code has helpers that are used to emulate MOVS instructions. To be
able to reuse this code in the MOVS implementation for intel, it is
necessary to move them to a common location.

Acked-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/sev/core.c  | 139 ++++++--------------------------------
 arch/x86/include/asm/io.h |   3 +
 arch/x86/lib/iomem.c      | 115 +++++++++++++++++++++++++++++++
 3 files changed, 140 insertions(+), 117 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 082d61d85dfc..07e9a6f15fba 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -369,72 +369,24 @@ static enum es_result vc_decode_insn(struct es_em_ctxt *ctxt)
 static enum es_result vc_write_mem(struct es_em_ctxt *ctxt,
 				   char *dst, char *buf, size_t size)
 {
-	unsigned long error_code = X86_PF_PROT | X86_PF_WRITE;
+	unsigned long error_code;
+	int ret;
 
 	/*
-	 * This function uses __put_user() independent of whether kernel or user
-	 * memory is accessed. This works fine because __put_user() does no
-	 * sanity checks of the pointer being accessed. All that it does is
-	 * to report when the access failed.
-	 *
-	 * Also, this function runs in atomic context, so __put_user() is not
-	 * allowed to sleep. The page-fault handler detects that it is running
-	 * in atomic context and will not try to take mmap_sem and handle the
-	 * fault, so additional pagefault_enable()/disable() calls are not
-	 * needed.
-	 *
-	 * The access can't be done via copy_to_user() here because
-	 * vc_write_mem() must not use string instructions to access unsafe
-	 * memory. The reason is that MOVS is emulated by the #VC handler by
-	 * splitting the move up into a read and a write and taking a nested #VC
-	 * exception on whatever of them is the MMIO access. Using string
-	 * instructions here would cause infinite nesting.
+	 * This function runs in atomic context, so __put_iomem() is not allowed
+	 * to sleep. The page-fault handler detects that it is running in atomic
+	 * context and will not try to take mmap_lock and handle the fault, so
+	 * additional pagefault_enable()/disable() calls are not needed.
 	 */
-	switch (size) {
-	case 1: {
-		u8 d1;
-		u8 __user *target = (u8 __user *)dst;
-
-		memcpy(&d1, buf, 1);
-		if (__put_user(d1, target))
-			goto fault;
-		break;
-	}
-	case 2: {
-		u16 d2;
-		u16 __user *target = (u16 __user *)dst;
-
-		memcpy(&d2, buf, 2);
-		if (__put_user(d2, target))
-			goto fault;
-		break;
-	}
-	case 4: {
-		u32 d4;
-		u32 __user *target = (u32 __user *)dst;
-
-		memcpy(&d4, buf, 4);
-		if (__put_user(d4, target))
-			goto fault;
-		break;
-	}
-	case 8: {
-		u64 d8;
-		u64 __user *target = (u64 __user *)dst;
+	ret = __put_iomem(dst, buf, size);
+	if (!ret)
+		return ES_OK;
 
-		memcpy(&d8, buf, 8);
-		if (__put_user(d8, target))
-			goto fault;
-		break;
-	}
-	default:
-		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+	if (ret == -EIO)
 		return ES_UNSUPPORTED;
-	}
 
-	return ES_OK;
+	error_code = X86_PF_PROT | X86_PF_WRITE;
 
-fault:
 	if (user_mode(ctxt->regs))
 		error_code |= X86_PF_USER;
 
@@ -448,71 +400,24 @@ static enum es_result vc_write_mem(struct es_em_ctxt *ctxt,
 static enum es_result vc_read_mem(struct es_em_ctxt *ctxt,
 				  char *src, char *buf, size_t size)
 {
-	unsigned long error_code = X86_PF_PROT;
+	unsigned long error_code;
+	int ret;
 
 	/*
-	 * This function uses __get_user() independent of whether kernel or user
-	 * memory is accessed. This works fine because __get_user() does no
-	 * sanity checks of the pointer being accessed. All that it does is
-	 * to report when the access failed.
-	 *
-	 * Also, this function runs in atomic context, so __get_user() is not
-	 * allowed to sleep. The page-fault handler detects that it is running
-	 * in atomic context and will not try to take mmap_sem and handle the
-	 * fault, so additional pagefault_enable()/disable() calls are not
-	 * needed.
-	 *
-	 * The access can't be done via copy_from_user() here because
-	 * vc_read_mem() must not use string instructions to access unsafe
-	 * memory. The reason is that MOVS is emulated by the #VC handler by
-	 * splitting the move up into a read and a write and taking a nested #VC
-	 * exception on whatever of them is the MMIO access. Using string
-	 * instructions here would cause infinite nesting.
+	 * This function runs in atomic context, so __get_iomem() is not allowed
+	 * to sleep. The page-fault handler detects that it is running in atomic
+	 * context and will not try to take mmap_lock and handle the fault, so
+	 * additional pagefault_enable()/disable() calls are not needed.
 	 */
-	switch (size) {
-	case 1: {
-		u8 d1;
-		u8 __user *s = (u8 __user *)src;
-
-		if (__get_user(d1, s))
-			goto fault;
-		memcpy(buf, &d1, 1);
-		break;
-	}
-	case 2: {
-		u16 d2;
-		u16 __user *s = (u16 __user *)src;
-
-		if (__get_user(d2, s))
-			goto fault;
-		memcpy(buf, &d2, 2);
-		break;
-	}
-	case 4: {
-		u32 d4;
-		u32 __user *s = (u32 __user *)src;
+	ret = __get_iomem(src, buf, size);
+	if (!ret)
+		return ES_OK;
 
-		if (__get_user(d4, s))
-			goto fault;
-		memcpy(buf, &d4, 4);
-		break;
-	}
-	case 8: {
-		u64 d8;
-		u64 __user *s = (u64 __user *)src;
-		if (__get_user(d8, s))
-			goto fault;
-		memcpy(buf, &d8, 8);
-		break;
-	}
-	default:
-		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+	if (ret == -EIO)
 		return ES_UNSUPPORTED;
-	}
 
-	return ES_OK;
+	error_code = X86_PF_PROT;
 
-fault:
 	if (user_mode(ctxt->regs))
 		error_code |= X86_PF_USER;
 
diff --git a/arch/x86/include/asm/io.h b/arch/x86/include/asm/io.h
index 1d60427379c9..ac01d53466cb 100644
--- a/arch/x86/include/asm/io.h
+++ b/arch/x86/include/asm/io.h
@@ -402,4 +402,7 @@ static inline void iosubmit_cmds512(void __iomem *dst, const void *src,
 	}
 }
 
+int __get_iomem(char *src, char *buf, size_t size);
+int __put_iomem(char *src, char *buf, size_t size);
+
 #endif /* _ASM_X86_IO_H */
diff --git a/arch/x86/lib/iomem.c b/arch/x86/lib/iomem.c
index 5eecb45d05d5..3ab146edddea 100644
--- a/arch/x86/lib/iomem.c
+++ b/arch/x86/lib/iomem.c
@@ -2,6 +2,7 @@
 #include <linux/module.h>
 #include <linux/io.h>
 #include <linux/kmsan-checks.h>
+#include <asm/uaccess.h>
 
 #define movs(type,to,from) \
 	asm volatile("movs" type:"=&D" (to), "=&S" (from):"0" (to), "1" (from):"memory")
@@ -124,3 +125,117 @@ void memset_io(volatile void __iomem *a, int b, size_t c)
 	}
 }
 EXPORT_SYMBOL(memset_io);
+
+int __get_iomem(char *src, char *buf, size_t size)
+{
+	/*
+	 * This function uses __get_user() independent of whether kernel or user
+	 * memory is accessed. This works fine because __get_user() does no
+	 * sanity checks of the pointer being accessed. All that it does is
+	 * to report when the access failed.
+	 *
+	 * The access can't be done via copy_from_user() here because
+	 * __get_iomem() must not use string instructions to access unsafe
+	 * memory. The reason is that MOVS is emulated by the exception handler
+	 * for SEV and TDX by splitting the move up into a read and a write
+	 * opetations and taking a nested exception on whatever of them is the
+	 * MMIO access. Using string instructions here would cause infinite
+	 * nesting.
+	 */
+	switch (size) {
+	case 1: {
+		u8 d1, __user *s = (u8 __user *)src;
+
+		if (__get_user(d1, s))
+			return -EFAULT;
+		memcpy(buf, &d1, 1);
+		break;
+	}
+	case 2: {
+		u16 d2, __user *s = (u16 __user *)src;
+
+		if (__get_user(d2, s))
+			return -EFAULT;
+		memcpy(buf, &d2, 2);
+		break;
+	}
+	case 4: {
+		u32 d4, __user *s = (u32 __user *)src;
+
+		if (__get_user(d4, s))
+			return -EFAULT;
+		memcpy(buf, &d4, 4);
+		break;
+	}
+	case 8: {
+		u64 d8, __user *s = (u64 __user *)src;
+
+		if (__get_user(d8, s))
+			return -EFAULT;
+		memcpy(buf, &d8, 8);
+		break;
+	}
+	default:
+		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+		return -EIO;
+	}
+
+	return 0;
+}
+
+int __put_iomem(char *dst, char *buf, size_t size)
+{
+	/*
+	 * This function uses __put_user() independent of whether kernel or user
+	 * memory is accessed. This works fine because __put_user() does no
+	 * sanity checks of the pointer being accessed. All that it does is
+	 * to report when the access failed.
+	 *
+	 * The access can't be done via copy_to_user() here because
+	 * __put_iomem() must not use string instructions to access unsafe
+	 * memory. The reason is that MOVS is emulated by the exception handler
+	 * for SEV and TDX by splitting the move up into a read and a write
+	 * opetations and taking a nested exception on whatever of them is the
+	 * MMIO access. Using string instructions here would cause infinite
+	 * nesting.
+	 */
+	switch (size) {
+	case 1: {
+		u8 d1, __user *target = (u8 __user *)dst;
+
+		memcpy(&d1, buf, 1);
+		if (__put_user(d1, target))
+			return -EFAULT;
+		break;
+	}
+	case 2: {
+		u16 d2, __user *target = (u16 __user *)dst;
+
+		memcpy(&d2, buf, 2);
+		if (__put_user(d2, target))
+			return -EFAULT;
+		break;
+	}
+	case 4: {
+		u32 d4, __user *target = (u32 __user *)dst;
+
+		memcpy(&d4, buf, 4);
+		if (__put_user(d4, target))
+			return -EFAULT;
+		break;
+	}
+	case 8: {
+		u64 d8, __user *target = (u64 __user *)dst;
+
+		memcpy(&d8, buf, 8);
+		if (__put_user(d8, target))
+			return -EFAULT;
+		break;
+	}
+	default:
+		WARN_ONCE(1, "%s: Invalid size: %zu\n", __func__, size);
+		return -EIO;
+	}
+
+	return 0;
+}

---

## [106] Alexey Gladkov — 2024-09-13
*Subject: [PATCH v7 6/6] x86/tdx: Implement MOVS for MMIO*

From: "Alexey Gladkov (Intel)" <legion@kernel.org>

Add emulation of the MOVS instruction on MMIO regions. MOVS emulation
consists of dividing it into a series of read and write operations,
which in turn will be validated separately.

This implementation is based on the same principle as in SEV. It splits
MOVS into separate read and write operations, which in turn can cause
nested #VEs depending on which of the arguments caused the first #VE.

The difference with the SEV implementation is the execution context. SEV
code is executed in atomic context. Exception handler in TDX is executed
with interrupts enabled. That's why the approach to locking is
different. In TDX, mmap_lock is taken to verify and emulate the
instruction.

Another difference is how the read and write instructions are executed
for MOVS emulation. While in SEV each read/write operation returns to
user space, in TDX these operations are performed from the kernel
context.

It may be possible to achieve more code reuse at this point,
but it would require confirmation from SEV that such a thing wouldn't
break anything.

Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Signed-off-by: Alexey Gladkov (Intel) <legion@kernel.org>
---
 arch/x86/coco/tdx/tdx.c          | 82 ++++++++++++++++++++++++++++----
 arch/x86/include/asm/processor.h |  1 +
 2 files changed, 75 insertions(+), 8 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index dffc343e64d7..151e63083a13 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -514,6 +514,60 @@ static int decode_insn_struct(struct insn *insn, struct pt_regs *regs)
 	return 0;
 }
 
+static int handle_mmio_movs(struct insn *insn, struct pt_regs *regs, int size, struct ve_info *ve)
+{
+	unsigned long ds_base, es_base;
+	unsigned char *src, *dst;
+	unsigned char buffer[8];
+	int off, ret;
+	bool rep;
+
+	/*
+	 * The in-kernel code must use a special API that does not use MOVS.
+	 * If the MOVS instruction is received from in-kernel, then something
+	 * is broken.
+	 */
+	if (WARN_ON_ONCE(!user_mode(regs)))
+		return -EFAULT;
+
+	ds_base = insn_get_seg_base(regs, INAT_SEG_REG_DS);
+	es_base = insn_get_seg_base(regs, INAT_SEG_REG_ES);
+
+	if (ds_base == -1L || es_base == -1L)
+		return -EINVAL;
+
+	current->thread.in_mmio_emul = 1;
+
+	rep = insn_has_rep_prefix(insn);
+
+	do {
+		src = ds_base + (unsigned char *) regs->si;
+		dst = es_base + (unsigned char *) regs->di;
+
+		ret = __get_iomem(src, buffer, size);
+		if (ret)
+			goto out;
+
+		ret = __put_iomem(dst, buffer, size);
+		if (ret)
+			goto out;
+
+		off = (regs->flags & X86_EFLAGS_DF) ? -size : size;
+
+		regs->si += off;
+		regs->di += off;
+
+		if (rep)
+			regs->cx -= 1;
+	} while (rep || regs->cx > 0);
+
+	ret = insn->length;
+out:
+	current->thread.in_mmio_emul = 0;
+
+	return ret;
+}
+
 static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int size,
 			     struct pt_regs *regs, struct ve_info *ve)
 {
@@ -535,9 +589,8 @@ static int handle_mmio_write(struct insn *insn, enum insn_mmio_type mmio, int si
 		return insn->length;
 	case INSN_MMIO_MOVS:
 		/*
-		 * MMIO was accessed with an instruction that could not be
-		 * decoded or handled properly. It was likely not using io.h
-		 * helpers or accessed MMIO accidentally.
+		 * MOVS is processed through higher level emulation which breaks
+		 * this instruction into a sequence of reads and writes.
 		 */
 		return -EINVAL;
 	default:
@@ -596,6 +649,7 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 {
 	enum insn_mmio_type mmio;
 	struct insn insn = {};
+	int need_validation;
 	unsigned long vaddr;
 	int size, ret;
 
@@ -607,14 +661,27 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	if (WARN_ON_ONCE(mmio == INSN_MMIO_DECODE_FAILED))
 		return -EINVAL;
 
+	if (mmio == INSN_MMIO_MOVS)
+		return handle_mmio_movs(&insn, regs, size, ve);
+
+	need_validation = user_mode(regs);
+
 	if (!user_mode(regs) && !fault_in_kernel_space(ve->gla)) {
-		WARN_ONCE(1, "Access to userspace address is not supported");
-		return -EINVAL;
+		/*
+		 * Access from kernel to userspace addresses is not allowed
+		 * unless it is a nested exception during MOVS emulation.
+		 */
+		if (!current->thread.in_mmio_emul || !current->mm) {
+			WARN_ONCE(1, "Access to userspace address is not supported");
+			return -EINVAL;
+		}
+
+		need_validation = 1;
 	}
 
 	vaddr = (unsigned long)insn_get_addr_ref(&insn, regs);
 
-	if (user_mode(regs)) {
+	if (need_validation) {
 		if (mmap_read_lock_killable(current->mm))
 			return -EINTR;
 
@@ -640,7 +707,6 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 	switch (mmio) {
 	case INSN_MMIO_WRITE:
 	case INSN_MMIO_WRITE_IMM:
-	case INSN_MMIO_MOVS:
 		ret = handle_mmio_write(&insn, mmio, size, regs, ve);
 		break;
 	case INSN_MMIO_READ:
@@ -661,7 +727,7 @@ static int handle_mmio(struct pt_regs *regs, struct ve_info *ve)
 		ret = -EINVAL;
 	}
 unlock:
-	if (user_mode(regs))
+	if (need_validation)
 		mmap_read_unlock(current->mm);
 
 	return ret;
diff --git a/arch/x86/include/asm/processor.h b/arch/x86/include/asm/processor.h
index a75a07f4931f..57605b11b06c 100644
--- a/arch/x86/include/asm/processor.h
+++ b/arch/x86/include/asm/processor.h
@@ -486,6 +486,7 @@ struct thread_struct {
 	unsigned long		iopl_emul;
 
 	unsigned int		iopl_warn:1;
+	unsigned int		in_mmio_emul:1;
 
 	/*
 	 * Protection Keys Register for Userspace.  Loaded immediately on

---

## [107] Dave Hansen — 2024-09-13
*Subject: Re: [PATCH v7 1/6] x86/tdx: Fix "in-kernel MMIO" check*

On 9/13/24 10:05, Alexey Gladkov wrote:
> TDX only supports kernel-initiated MMIO operations. The handle_mmio()
> function checks if the #VE exception occurred in the kernel and rejects

Acked-by: Dave Hansen <dave.hansen@linux.intel.com>

---

## [108] Dave Hansen — 2024-09-13
*Subject: Re: [PATCH v7 1/6] x86/tdx: Fix "in-kernel MMIO" check*

On 9/13/24 10:18, Dave Hansen wrote:
...
>> Ensure that the target MMIO address is within the kernel before decoding
>> instruction.

Oh, and please add these to anything you cc:stable@ on:

Fixes: 31d58c4e557d ("x86/tdx: Handle in-kernel MMIO")

---

## [109] Sean Christopherson — 2024-09-13
*Subject: Re: [PATCH v6 0/6] x86/tdx: Allow MMIO instructions from userspace*

On Fri, Sep 13, 2024, Dave Hansen wrote:
> On 9/13/24 09:28, Sean Christopherson wrote:
> >> because folks would update their kernel and old userspace would break.

I agree to some extent, but as below, this really only holds true if we're talking
about old crusty userspace.  And even then, it's weird to draw the line at the
emulated MMIO boundary, because if crusty old userspace is a security risk, then
the kernel arguably shouldn't have mapped the MMIO address into that userspace in
the first place.

> > I also don't know that this is for old userspace.  AFAIK, the most common case
> > for userspace triggering emulated MMIO is when a device is passed to userspace

---
