---
title: 'x86/sev: improve efi runtime code support.'
date: 2025-06-26
last_reply: 2025-06-27
message_count: 6
participants: ['Gerd Hoffmann', 'Gupta, Pankaj', 'Borislav Petkov']
---

## [1] Gerd Hoffmann — 2025-06-26

v4:
 - address review comments from Ingo.
v3:
 - pick up updates from Borislav
 - add vmpl check to sev_es_efi_map_ghcbs_caas
v2 changes:
 - rebase to latest master.
 - update error message (Dionna).
 - more details in the commit message (Borislav).

Gerd Hoffmann (3):
  x86/sev/vc: fix efi runtime instruction emulation
  x86/sev: fix error handling in sev_es_efi_map_ghcbs_caas()
  x86/sev: Let sev_es_efi_map_ghcbs() map the caa pages too

 arch/x86/include/asm/sev.h     |  4 ++--
 arch/x86/coco/sev/core.c       | 23 +++++++++++++++++++----
 arch/x86/coco/sev/vc-handle.c  |  9 ++++++++-
 arch/x86/platform/efi/efi_64.c |  4 ++--
 4 files changed, 31 insertions(+), 9 deletions(-)

---

## [2] Gerd Hoffmann — 2025-06-26
*Subject: [PATCH v4 1/3] x86/sev/vc: fix efi runtime instruction emulation*

In case efi_mm is active go use the userspace instruction decoder which
supports fetching instructions from active_mm.  This is needed to make
instruction emulation work for EFI runtime code, so it can use cpuid
and rdmsr.

EFI runtime code uses the cpuid instruction to gather information about
the environment it is running in, such as SEV being enabled or not, and
choose (if needed) the SEV code path for ioport access.

EFI runtime code uses the rdmsr instruction to get the location of the
CAA page (see SVSM spec, section 4.2 - "Post Boot").

The big picture behind this is that the kernel needs to be able to
properly handle #VC exceptions that come from EFI runtime services.
Since EFI runtime services have a special page table mapping for the EFI
virtual address space, the efi_mm context must be used when decoding
instructions during #VC handling.

Signed-off-by: Gerd Hoffmann <kraxel@redhat.com>
---
 arch/x86/coco/sev/vc-handle.c | 9 ++++++++-
 1 file changed, 8 insertions(+), 1 deletion(-)

diff --git a/arch/x86/coco/sev/vc-handle.c b/arch/x86/coco/sev/vc-handle.c
index 0989d98da130..faf1fce89ed4 100644
--- a/arch/x86/coco/sev/vc-handle.c
+++ b/arch/x86/coco/sev/vc-handle.c
@@ -17,6 +17,7 @@
 #include <linux/mm.h>
 #include <linux/io.h>
 #include <linux/psp-sev.h>
+#include <linux/efi.h>
 #include <uapi/linux/sev-guest.h>
 
 #include <asm/init.h>
@@ -178,9 +179,15 @@ static enum es_result __vc_decode_kern_insn(struct es_em_ctxt *ctxt)
 		return ES_OK;
 }
 
+/*
+ * User instruction decoding is also required for the EFI runtime. Even though
+ * the EFI runtime is running in kernel mode, it uses special EFI virtual
+ * address mappings that require the use of efi_mm to properly address and
+ * decode.
+ */
 static enum es_result vc_decode_insn(struct es_em_ctxt *ctxt)
 {
-	if (user_mode(ctxt->regs))
+	if (user_mode(ctxt->regs) || mm_is_efi(current->active_mm))
 		return __vc_decode_user_insn(ctxt);
 	else
 		return __vc_decode_kern_insn(ctxt);

---

## [3] Gerd Hoffmann — 2025-06-26
*Subject: [PATCH v4 2/3] x86/sev: fix error handling in sev_es_efi_map_ghcbs_caas()*

Pass up error codes from kernel_map_pages_in_pgd() instead of
returning '1' on failure.

Signed-off-by: Gerd Hoffmann <kraxel@redhat.com>
---
 arch/x86/coco/sev/core.c | 6 ++++--
 1 file changed, 4 insertions(+), 2 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index b6db4e0b936b..3de8c3d2b55d 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -1050,6 +1050,7 @@ int __init sev_es_efi_map_ghcbs(pgd_t *pgd)
 {
 	struct sev_es_runtime_data *data;
 	unsigned long address, pflags;
+	int retval;
 	int cpu;
 	u64 pfn;
 
@@ -1064,8 +1065,9 @@ int __init sev_es_efi_map_ghcbs(pgd_t *pgd)
 		address = __pa(&data->ghcb_page);
 		pfn = address >> PAGE_SHIFT;
 
-		if (kernel_map_pages_in_pgd(pgd, pfn, address, 1, pflags))
-			return 1;
+		retval = kernel_map_pages_in_pgd(pgd, pfn, address, 1, pflags);
+		if (retval != 0)
+			return retval;
 	}
 
 	return 0;

---

## [4] Gerd Hoffmann — 2025-06-26
*Subject: [PATCH v4 3/3] x86/sev: Let sev_es_efi_map_ghcbs() map the caa pages too*

OVMF EFI firmware needs access to the CAA page to do SVSM protocol calls. For
example, when the SVSM implements an EFI variable store, such calls will be
necessary.

So add that to sev_es_efi_map_ghcbs() and also rename the function to reflect
the additional job it is doing now.

Signed-off-by: Gerd Hoffmann <kraxel@redhat.com>
---
 arch/x86/include/asm/sev.h     |  4 ++--
 arch/x86/coco/sev/core.c       | 17 +++++++++++++++--
 arch/x86/platform/efi/efi_64.c |  4 ++--
 3 files changed, 19 insertions(+), 6 deletions(-)

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
index 3de8c3d2b55d..26b96e19f5e1 100644
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
 	struct sev_es_runtime_data *data;
-	unsigned long address, pflags;
+	unsigned long address, pflags, pflags_enc;
 	int retval;
 	int cpu;
 	u64 pfn;
@@ -1058,6 +1060,7 @@ int __init sev_es_efi_map_ghcbs(pgd_t *pgd)
 		return 0;
 
 	pflags = _PAGE_NX | _PAGE_RW;
+	pflags_enc = cc_mkenc(pflags);
 
 	for_each_possible_cpu(cpu) {
 		data = per_cpu(runtime_data, cpu);
@@ -1068,6 +1071,16 @@ int __init sev_es_efi_map_ghcbs(pgd_t *pgd)
 		retval = kernel_map_pages_in_pgd(pgd, pfn, address, 1, pflags);
 		if (retval != 0)
 			return retval;
+
+		if (snp_vmpl) {
+			address = per_cpu(svsm_caa_pa, cpu);
+			if (!address)
+				return 1;
+
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

## [5] Gupta, Pankaj — 2025-06-27
*Subject: Re: [PATCH v4 1/3] x86/sev/vc: fix efi runtime instruction emulation*

> In case efi_mm is active go use the userspace instruction decoder which
> supports fetching instructions from active_mm.  This is needed to make

Reviewed-by: Pankaj Gupta <pankaj.gupta@amd.com>

> ---
>   arch/x86/coco/sev/vc-handle.c | 9 ++++++++-

---

## [6] Borislav Petkov — 2025-06-27
*Subject: Re: [PATCH v4 2/3] x86/sev: fix error handling in
 sev_es_efi_map_ghcbs_caas()*

On Thu, Jun 26, 2025 at 01:40:12PM +0200, Gerd Hoffmann wrote:
> -		if (kernel_map_pages_in_pgd(pgd, pfn, address, 1, pflags))
> -			return 1;

Yeah, I'd understand if it made any sense to propagate the error upwards but
this function is called exactly once by efi_setup_page_tables() and all it
needs to return is success/failure which the caller uses on the spot.

So no point in doing any of that nonsense. I'll zap it from the set.

Thx.

---
