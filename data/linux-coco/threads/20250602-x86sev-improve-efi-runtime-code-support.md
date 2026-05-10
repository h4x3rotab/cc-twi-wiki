---
title: 'x86/sev: improve efi runtime code support.'
date: 2025-06-02
last_reply: 2025-06-26
message_count: 11
participants: ['Gerd Hoffmann', 'Tom Lendacky', 'Borislav Petkov']
---

## [1] Gerd Hoffmann — 2025-06-02

v2 changes:
 - rebase to latest master.
 - update error message (Dionna).
 - more details in the commit message (Borislav).

Gerd Hoffmann (2):
  x86/sev/vc: fix efi runtime instruction emulation
  x86/sev: let sev_es_efi_map_ghcbs map the caa pages too

 arch/x86/include/asm/sev.h     |  4 ++--
 arch/x86/coco/sev/core.c       | 14 ++++++++++++--
 arch/x86/coco/sev/vc-handle.c  |  3 ++-
 arch/x86/platform/efi/efi_64.c |  4 ++--
 4 files changed, 18 insertions(+), 7 deletions(-)

---

## [2] Gerd Hoffmann — 2025-06-02
*Subject: [PATCH v2 1/2] x86/sev/vc: fix efi runtime instruction emulation*

In case efi_mm is active go use the userspace instruction decoder which
supports fetching instructions from active_mm.  This is needed to make
instruction emulation work for EFI runtime code, so it can use cpuid
and rdmsr.

EFI runtime code uses the cpuid instruction to gather information about
the environment it is running in, such as SEV being enabled or not, and
choose (if needed) the SEV code path for ioport access.

EFI runtime code uses the rdmsr instruction to get the location of the
CAA page (see SVSM spec, section 4.2 - "Post Boot").

Signed-off-by: Gerd Hoffmann <kraxel@redhat.com>
---
 arch/x86/coco/sev/vc-handle.c | 3 ++-
 1 file changed, 2 insertions(+), 1 deletion(-)

diff --git a/arch/x86/coco/sev/vc-handle.c b/arch/x86/coco/sev/vc-handle.c
index 0989d98da130..01c78182da88 100644
--- a/arch/x86/coco/sev/vc-handle.c
+++ b/arch/x86/coco/sev/vc-handle.c
@@ -17,6 +17,7 @@
 #include <linux/mm.h>
 #include <linux/io.h>
 #include <linux/psp-sev.h>
+#include <linux/efi.h>
 #include <uapi/linux/sev-guest.h>
 
 #include <asm/init.h>
@@ -180,7 +181,7 @@ static enum es_result __vc_decode_kern_insn(struct es_em_ctxt *ctxt)
 
 static enum es_result vc_decode_insn(struct es_em_ctxt *ctxt)
 {
-	if (user_mode(ctxt->regs))
+	if (user_mode(ctxt->regs) || current->active_mm == &efi_mm)
 		return __vc_decode_user_insn(ctxt);
 	else
 		return __vc_decode_kern_insn(ctxt);

---

## [3] Gerd Hoffmann — 2025-06-02
*Subject: [PATCH v2 2/2] x86/sev: let sev_es_efi_map_ghcbs map the caa pages too*

OVMF EFI firmware needs access to the CAA page to do SVSM protocol
calls.  So add that to sev_es_efi_map_ghcbs and also rename the function
to reflect the additional job it is doing now.

Signed-off-by: Gerd Hoffmann <kraxel@redhat.com>
---
 arch/x86/include/asm/sev.h     |  4 ++--
 arch/x86/coco/sev/core.c       | 14 ++++++++++++--
 arch/x86/platform/efi/efi_64.c |  4 ++--
 3 files changed, 16 insertions(+), 6 deletions(-)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 58e028d42e41..6e0ef192f23b 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -445,7 +445,7 @@ static __always_inline void sev_es_nmi_complete(void)
 	    cc_platform_has(CC_ATTR_GUEST_STATE_ENCRYPT))
 		__sev_es_nmi_complete();
 }
-extern int __init sev_es_efi_map_ghcbs(pgd_t *pgd);
+extern int __init sev_es_efi_map_ghcbs_caas(pgd_t *pgd);
 extern void sev_enable(struct boot_params *bp);
 
 /*
@@ -556,7 +556,7 @@ static inline void sev_es_ist_enter(struct pt_regs *regs) { }
 static inline void sev_es_ist_exit(void) { }
 static inline int sev_es_setup_ap_jump_table(struct real_mode_header *rmh) { return 0; }
 static inline void sev_es_nmi_complete(void) { }
-static inline int sev_es_efi_map_ghcbs(pgd_t *pgd) { return 0; }
+static inline int sev_es_efi_map_ghcbs_caas(pgd_t *pgd) { return 0; }
 static inline void sev_enable(struct boot_params *bp) { }
 static inline int pvalidate(unsigned long vaddr, bool rmp_psize, bool validate) { return 0; }
 static inline int rmpadjust(unsigned long vaddr, bool rmp_psize, unsigned long attrs) { return 0; }
diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index fbc1215d2746..7ab9fc0ea180 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -1054,11 +1054,13 @@ int __init sev_es_setup_ap_jump_table(struct real_mode_header *rmh)
  * This is needed by the OVMF UEFI firmware which will use whatever it finds in
  * the GHCB MSR as its GHCB to talk to the hypervisor. So make sure the per-cpu
  * runtime GHCBs used by the kernel are also mapped in the EFI page-table.
+ *
+ * When running under SVSM the CCA page is needed too, so map it as well.
  */
-int __init sev_es_efi_map_ghcbs(pgd_t *pgd)
+int __init sev_es_efi_map_ghcbs_caas(pgd_t *pgd)
 {
 	struct sev_es_runtime_data *data;
-	unsigned long address, pflags;
+	unsigned long address, pflags, pflags_enc;
 	int cpu;
 	u64 pfn;
 
@@ -1066,6 +1068,7 @@ int __init sev_es_efi_map_ghcbs(pgd_t *pgd)
 		return 0;
 
 	pflags = _PAGE_NX | _PAGE_RW;
+	pflags_enc = cc_mkenc(pflags);
 
 	for_each_possible_cpu(cpu) {
 		data = per_cpu(runtime_data, cpu);
@@ -1075,6 +1078,13 @@ int __init sev_es_efi_map_ghcbs(pgd_t *pgd)
 
 		if (kernel_map_pages_in_pgd(pgd, pfn, address, 1, pflags))
 			return 1;
+
+		address = per_cpu(svsm_caa_pa, cpu);
+		if (address) {
+			pfn = address >> PAGE_SHIFT;
+			if (kernel_map_pages_in_pgd(pgd, pfn, address, 1, pflags_enc))
+				return 1;
+		}
 	}
 
 	return 0;
diff --git a/arch/x86/platform/efi/efi_64.c b/arch/x86/platform/efi/efi_64.c
index e7e8f77f77f8..97e8032db45d 100644
--- a/arch/x86/platform/efi/efi_64.c
+++ b/arch/x86/platform/efi/efi_64.c
@@ -216,8 +216,8 @@ int __init efi_setup_page_tables(unsigned long pa_memmap, unsigned num_pages)
 	 * When SEV-ES is active, the GHCB as set by the kernel will be used
 	 * by firmware. Create a 1:1 unencrypted mapping for each GHCB.
 	 */
-	if (sev_es_efi_map_ghcbs(pgd)) {
-		pr_err("Failed to create 1:1 mapping for the GHCBs!\n");
+	if (sev_es_efi_map_ghcbs_caas(pgd)) {
+		pr_err("Failed to create 1:1 mapping for the GHCBs and CAAs!\n");
 		return 1;
 	}

---

## [4] Tom Lendacky — 2025-06-23
*Subject: Re: [PATCH v2 1/2] x86/sev/vc: fix efi runtime instruction emulation*

On 6/2/25 05:50, Gerd Hoffmann wrote:
> In case efi_mm is active go use the userspace instruction decoder which
> supports fetching instructions from active_mm.  This is needed to make

A comment before this would be good. Something like:

/*
 * User instruction decoding is also required for the EFI runtime. Even
 * though EFI runtime is running in kernel mode, it uses special EFI
 * virtual address mappings that require the use of efi_mm to properly
 * address and decode.
 */

Might be too verbose, but that's the general idea.

Thanks,
Tom

>  		return __vc_decode_user_insn(ctxt);
>  	else

---

## [5] Borislav Petkov — 2025-06-23
*Subject: Re: [PATCH v2 1/2] x86/sev/vc: fix efi runtime instruction emulation*

I have this now:

From: Gerd Hoffmann <kraxel@redhat.com>
Date: Mon, 2 Jun 2025 12:50:48 +0200
Subject: [PATCH] x86/sev: Fix EFI runtime instruction emulation

In case efi_mm is active use the userspace instruction decoder which
supports fetching instructions from active_mm.  This is needed to make
instruction emulation work for EFI runtime code, so it can use CPUID and
RDMSR.

EFI runtime code uses the CPUID instruction to gather information about
the environment it is running in, such as SEV being enabled or not, and
choose (if needed) the SEV code path for ioport access.

EFI runtime code uses the RDMSR instruction to get the location of the
CAA page (see SVSM spec, section 4.2 - "Post Boot").

The big picture behind this is that the kernel needs to be able to
properly handle #VC exceptions that come from EFI runtime services.
Since EFI runtime services have a special page table mapping for the EFI
virtual address space, the efi_mm context must be used when decoding
instructions during #VC handling.

  [ bp: Massage and extend commit message with more backstory, add
    clarifying comment from Tom. ]

Signed-off-by: Gerd Hoffmann <kraxel@redhat.com>
Signed-off-by: Borislav Petkov (AMD) <bp@alien8.de>
Link: https://lore.kernel.org/20250602105050.1535272-2-kraxel@redhat.com
---
 arch/x86/coco/sev/vc-handle.c | 8 +++++++-
 1 file changed, 7 insertions(+), 1 deletion(-)

diff --git a/arch/x86/coco/sev/vc-handle.c b/arch/x86/coco/sev/vc-handle.c
index 0989d98da130..e498a8965939 100644
--- a/arch/x86/coco/sev/vc-handle.c
+++ b/arch/x86/coco/sev/vc-handle.c
@@ -17,6 +17,7 @@
 #include <linux/mm.h>
 #include <linux/io.h>
 #include <linux/psp-sev.h>
+#include <linux/efi.h>
 #include <uapi/linux/sev-guest.h>
 
 #include <asm/init.h>
@@ -178,9 +179,14 @@ static enum es_result __vc_decode_kern_insn(struct es_em_ctxt *ctxt)
 		return ES_OK;
 }
 
+/*
+ * User instruction decoding is also required for the EFI runtime. Even though
+ * EFI runtime is running in kernel mode, it uses special EFI virtual address
+ * mappings that require the use of efi_mm to properly address and decode.
+ */
 static enum es_result vc_decode_insn(struct es_em_ctxt *ctxt)
 {
-	if (user_mode(ctxt->regs))
+	if (user_mode(ctxt->regs) || current->active_mm == &efi_mm)
 		return __vc_decode_user_insn(ctxt);
 	else
 		return __vc_decode_kern_insn(ctxt);

---

## [6] Borislav Petkov — 2025-06-24
*Subject: Re: [PATCH v2 2/2] x86/sev: let sev_es_efi_map_ghcbs map the caa
 pages too*

I got this now:

---
From: Gerd Hoffmann <kraxel@redhat.com>
Date: Mon, 2 Jun 2025 12:50:49 +0200
Subject: [PATCH] x86/sev: Let sev_es_efi_map_ghcbs() map the caa pages too

OVMF EFI firmware needs access to the CAA page to do SVSM protocol calls. For
example, when the SVSM implements an EFI variable store, such calls will be
necessary.

So add that to sev_es_efi_map_ghcbs() and also rename the function to reflect
the additional job it is doing now.

  [ bp: Massage. ]

Signed-off-by: Gerd Hoffmann <kraxel@redhat.com>
Signed-off-by: Borislav Petkov (AMD) <bp@alien8.de>
Link: https://lore.kernel.org/20250602105050.1535272-3-kraxel@redhat.com
---
 arch/x86/coco/sev/core.c       | 15 +++++++++++++--
 arch/x86/include/asm/sev.h     |  4 ++--
 arch/x86/platform/efi/efi_64.c |  4 ++--
 3 files changed, 17 insertions(+), 6 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 8375ca7fbd8a..6af3e94ba0ee 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -1045,11 +1045,13 @@ int __init sev_es_setup_ap_jump_table(struct real_mode_header *rmh)
  * This is needed by the OVMF UEFI firmware which will use whatever it finds in
  * the GHCB MSR as its GHCB to talk to the hypervisor. So make sure the per-cpu
  * runtime GHCBs used by the kernel are also mapped in the EFI page-table.
+ *
+ * When running under SVSM the CCA page is needed too, so map it as well.
  */
-int __init sev_es_efi_map_ghcbs(pgd_t *pgd)
+int __init sev_es_efi_map_ghcbs_caas(pgd_t *pgd)
 {
+	unsigned long address, pflags, pflags_enc;
 	struct sev_es_runtime_data *data;
-	unsigned long address, pflags;
 	int cpu;
 	u64 pfn;
 
@@ -1057,6 +1059,7 @@ int __init sev_es_efi_map_ghcbs(pgd_t *pgd)
 		return 0;
 
 	pflags = _PAGE_NX | _PAGE_RW;
+	pflags_enc = cc_mkenc(pflags);
 
 	for_each_possible_cpu(cpu) {
 		data = per_cpu(runtime_data, cpu);
@@ -1066,6 +1069,14 @@ int __init sev_es_efi_map_ghcbs(pgd_t *pgd)
 
 		if (kernel_map_pages_in_pgd(pgd, pfn, address, 1, pflags))
 			return 1;
+
+		address = per_cpu(svsm_caa_pa, cpu);
+		if (!address)
+			return 1;
+
+		pfn = address >> PAGE_SHIFT;
+		if (kernel_map_pages_in_pgd(pgd, pfn, address, 1, pflags_enc))
+			return 1;
 	}
 
 	return 0;
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index fbb616fcbfb8..5b809f0ef207 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -446,7 +446,7 @@ static __always_inline void sev_es_nmi_complete(void)
 	    cc_platform_has(CC_ATTR_GUEST_STATE_ENCRYPT))
 		__sev_es_nmi_complete();
 }
-extern int __init sev_es_efi_map_ghcbs(pgd_t *pgd);
+extern int __init sev_es_efi_map_ghcbs_caas(pgd_t *pgd);
 extern void sev_enable(struct boot_params *bp);
 
 /*
@@ -554,7 +554,7 @@ static inline void sev_es_ist_enter(struct pt_regs *regs) { }
 static inline void sev_es_ist_exit(void) { }
 static inline int sev_es_setup_ap_jump_table(struct real_mode_header *rmh) { return 0; }
 static inline void sev_es_nmi_complete(void) { }
-static inline int sev_es_efi_map_ghcbs(pgd_t *pgd) { return 0; }
+static inline int sev_es_efi_map_ghcbs_caas(pgd_t *pgd) { return 0; }
 static inline void sev_enable(struct boot_params *bp) { }
 static inline int pvalidate(unsigned long vaddr, bool rmp_psize, bool validate) { return 0; }
 static inline int rmpadjust(unsigned long vaddr, bool rmp_psize, unsigned long attrs) { return 0; }
diff --git a/arch/x86/platform/efi/efi_64.c b/arch/x86/platform/efi/efi_64.c
index e7e8f77f77f8..97e8032db45d 100644
--- a/arch/x86/platform/efi/efi_64.c
+++ b/arch/x86/platform/efi/efi_64.c
@@ -216,8 +216,8 @@ int __init efi_setup_page_tables(unsigned long pa_memmap, unsigned num_pages)
 	 * When SEV-ES is active, the GHCB as set by the kernel will be used
 	 * by firmware. Create a 1:1 unencrypted mapping for each GHCB.
 	 */
-	if (sev_es_efi_map_ghcbs(pgd)) {
-		pr_err("Failed to create 1:1 mapping for the GHCBs!\n");
+	if (sev_es_efi_map_ghcbs_caas(pgd)) {
+		pr_err("Failed to create 1:1 mapping for the GHCBs and CAAs!\n");
 		return 1;
 	}

---

## [7] Gerd Hoffmann — 2025-06-25
*Subject: Re: [PATCH v2 2/2] x86/sev: let sev_es_efi_map_ghcbs map the caa
 pages too*

>  	for_each_possible_cpu(cpu) {
>  		data = per_cpu(runtime_data, cpu);

The kernel allocates the caa page(s) only when running under svsm, see
alloc_runtime_data(), so this is not correct.  I think we either have to
return to the original behavior of only doing something in case address
is not NULL, or wrap the caa code block into a 'if (snp_vmpl) { ... }',
following what alloc_runtime_data() is doing.

take care,
  Gerd

---

## [8] Borislav Petkov — 2025-06-25
*Subject: Re: [PATCH v2 2/2] x86/sev: let sev_es_efi_map_ghcbs map the caa
 pages too*

On Wed, Jun 25, 2025 at 01:52:58PM +0200, Gerd Hoffmann wrote:
> The kernel allocates the caa page(s) only when running under svsm, see
> alloc_runtime_data(), so this is not correct.  I think we either have to

Yes, we're doing something only when the address is not NULL.

Or maybe I'm missing what you're trying to tell me...

---

## [9] Gerd Hoffmann — 2025-06-25
*Subject: Re: [PATCH v2 2/2] x86/sev: let sev_es_efi_map_ghcbs map the caa
 pages too*

On Wed, Jun 25, 2025 at 02:40:16PM +0200, Borislav Petkov wrote:
> On Wed, Jun 25, 2025 at 01:52:58PM +0200, Gerd Hoffmann wrote:
> > The kernel allocates the caa page(s) only when running under svsm, see

This is inside a loop, so returning in case the caa address is NULL will
skip ghcb setup for all but the first CPU.

take care,
  Gerd

---

## [10] Borislav Petkov — 2025-06-25
*Subject: Re: [PATCH v2 2/2] x86/sev: let sev_es_efi_map_ghcbs map the caa
 pages too*

On Wed, Jun 25, 2025 at 03:21:47PM +0200, Gerd Hoffmann wrote:
> This is inside a loop, so returning in case the caa address is NULL will
> skip ghcb setup for all but the first CPU.

Then you should not piggyback on this loop but map the CAs in a separate step,
only when a SVSM is running.

And even then we should think about allowing to continue if not all CAs map
successfully.

Thx.

---

## [11] Gerd Hoffmann — 2025-06-26
*Subject: Re: [PATCH v2 2/2] x86/sev: let sev_es_efi_map_ghcbs map the caa
 pages too*

On Wed, Jun 25, 2025 at 04:29:36PM +0200, Borislav Petkov wrote:
> On Wed, Jun 25, 2025 at 03:21:47PM +0200, Gerd Hoffmann wrote:
> > This is inside a loop, so returning in case the caa address is NULL will

v3 sent.

take care,
  Gerd

---
