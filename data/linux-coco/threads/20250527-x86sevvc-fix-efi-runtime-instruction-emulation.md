---
title: 'x86/sev/vc: fix efi runtime instruction emulation'
date: 2025-05-27
last_reply: 2025-06-02
message_count: 8
participants: ['Gerd Hoffmann', 'Borislav Petkov', 'Dionna Amalie Glaze']
---

## [1] Gerd Hoffmann — 2025-05-27

In case efi_mm is active go use the userspace instruction decoder which
supports fetching instructions from active_mm.  This is needed to make
instruction emulation work for EFI runtime code, so it can use cpuid
and rdmsr.

Signed-off-by: Gerd Hoffmann <kraxel@redhat.com>
---
 arch/x86/coco/sev/core.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 36beaac713c1..145f594d7e6b 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -346,7 +346,7 @@ static enum es_result __vc_decode_kern_insn(struct es_em_ctxt *ctxt)
 
 static enum es_result vc_decode_insn(struct es_em_ctxt *ctxt)
 {
-	if (user_mode(ctxt->regs))
+	if (user_mode(ctxt->regs) || current->active_mm == &efi_mm)
 		return __vc_decode_user_insn(ctxt);
 	else
 		return __vc_decode_kern_insn(ctxt);

---

## [2] Gerd Hoffmann — 2025-05-27
*Subject: [PATCH 2/2] x86/sev: let sev_es_efi_map_ghcbs map the caa pages too*

OVMF EFI firmware needs access to the CAA page to do SVSM protocol
calls.  So add that to sev_es_efi_map_ghcbs and also rename the function
to reflect the additional job it is doing now.

Signed-off-by: Gerd Hoffmann <kraxel@redhat.com>
---
 arch/x86/coco/sev/core.c       | 14 ++++++++++++--
 arch/x86/include/asm/sev.h     |  4 ++--
 arch/x86/platform/efi/efi_64.c |  2 +-
 3 files changed, 15 insertions(+), 5 deletions(-)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 145f594d7e6b..1cf2a8757ad6 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -1466,11 +1466,13 @@ int __init sev_es_setup_ap_jump_table(struct real_mode_header *rmh)
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
 
@@ -1478,6 +1480,7 @@ int __init sev_es_efi_map_ghcbs(pgd_t *pgd)
 		return 0;
 
 	pflags = _PAGE_NX | _PAGE_RW;
+	pflags_enc = cc_mkenc(pflags);
 
 	for_each_possible_cpu(cpu) {
 		data = per_cpu(runtime_data, cpu);
@@ -1487,6 +1490,13 @@ int __init sev_es_efi_map_ghcbs(pgd_t *pgd)
 
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
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index ba7999f66abe..6b4f8b55e214 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -410,7 +410,7 @@ static __always_inline void sev_es_nmi_complete(void)
 	    cc_platform_has(CC_ATTR_GUEST_STATE_ENCRYPT))
 		__sev_es_nmi_complete();
 }
-extern int __init sev_es_efi_map_ghcbs(pgd_t *pgd);
+extern int __init sev_es_efi_map_ghcbs_caas(pgd_t *pgd);
 extern void sev_enable(struct boot_params *bp);
 
 /*
@@ -491,7 +491,7 @@ static inline void sev_es_ist_enter(struct pt_regs *regs) { }
 static inline void sev_es_ist_exit(void) { }
 static inline int sev_es_setup_ap_jump_table(struct real_mode_header *rmh) { return 0; }
 static inline void sev_es_nmi_complete(void) { }
-static inline int sev_es_efi_map_ghcbs(pgd_t *pgd) { return 0; }
+static inline int sev_es_efi_map_ghcbs_caas(pgd_t *pgd) { return 0; }
 static inline void sev_enable(struct boot_params *bp) { }
 static inline int pvalidate(unsigned long vaddr, bool rmp_psize, bool validate) { return 0; }
 static inline int rmpadjust(unsigned long vaddr, bool rmp_psize, unsigned long attrs) { return 0; }
diff --git a/arch/x86/platform/efi/efi_64.c b/arch/x86/platform/efi/efi_64.c
index a4b4ebd41b8f..1136c576831f 100644
--- a/arch/x86/platform/efi/efi_64.c
+++ b/arch/x86/platform/efi/efi_64.c
@@ -215,7 +215,7 @@ int __init efi_setup_page_tables(unsigned long pa_memmap, unsigned num_pages)
 	 * When SEV-ES is active, the GHCB as set by the kernel will be used
 	 * by firmware. Create a 1:1 unencrypted mapping for each GHCB.
 	 */
-	if (sev_es_efi_map_ghcbs(pgd)) {
+	if (sev_es_efi_map_ghcbs_caas(pgd)) {
 		pr_err("Failed to create 1:1 mapping for the GHCBs!\n");
 		return 1;
 	}

---

## [3] Borislav Petkov — 2025-05-27
*Subject: Re: [PATCH 1/2] x86/sev/vc: fix efi runtime instruction emulation*

On Tue, May 27, 2025 at 04:45:44PM +0200, Gerd Hoffmann wrote:
> In case efi_mm is active go use the userspace instruction decoder which
> supports fetching instructions from active_mm.  This is needed to make

Can you pls explain what the use cases for this and your next patch are?

We'd like to add them to our test pile.

Thx.

---

## [4] Dionna Amalie Glaze — 2025-05-27
*Subject: Re: [PATCH 2/2] x86/sev: let sev_es_efi_map_ghcbs map the caa pages too*

> index a4b4ebd41b8f..1136c576831f 100644
> --- a/arch/x86/platform/efi/efi_64.c

nit: update error to reflect the expanded scope?

>                 return 1;
>         }

---

## [5] Gerd Hoffmann — 2025-05-28
*Subject: Re: [PATCH 2/2] x86/sev: let sev_es_efi_map_ghcbs map the caa pages
 too*

On Tue, May 27, 2025 at 09:44:34AM -0700, Dionna Amalie Glaze wrote:
> > index a4b4ebd41b8f..1136c576831f 100644
> > --- a/arch/x86/platform/efi/efi_64.c

Yep, missed that, will fix for v2.

take care,
  Gerd

---

## [6] Gerd Hoffmann — 2025-05-28
*Subject: Re: [PATCH 1/2] x86/sev/vc: fix efi runtime instruction emulation*

On Tue, May 27, 2025 at 06:21:51PM +0200, Borislav Petkov wrote:
> On Tue, May 27, 2025 at 04:45:44PM +0200, Gerd Hoffmann wrote:
> > In case efi_mm is active go use the userspace instruction decoder which

Use case is coconut-svsm providing an uefi variable store and edk2
runtime code doing svsm protocol calls to send requests to the svsm
variable store.  edk2 needs a caa page mapping and a working rdmsr
instruction for that.

Another less critical but useful case is edk2 debug logging to qemu
debugcon port.  That needs a working cpuid instruction because edk2
uses that to figure whenever sev is active and adapt ioport access
accordingly.

> We'd like to add them to our test pile.

That is a bit difficult right now because there are a number of pieces
which need to fall into place before this is easily testable.  You need:

 * host kernel with vmplanes patch series (for snp vmpl support).
 * coconut svsm with uefi variable store patches.
 * edk2 patches so it talks to svsm for variable access.
 * igvm support patches for qemu.

Hope I didn't forgot something ...

take care,
  Gerd

---

## [7] Borislav Petkov — 2025-05-30
*Subject: Re: [PATCH 1/2] x86/sev/vc: fix efi runtime instruction emulation*

On Wed, May 28, 2025 at 09:38:24AM +0200, Gerd Hoffmann wrote:
> Use case is coconut-svsm providing an uefi variable store and edk2
> runtime code doing svsm protocol calls to send requests to the svsm

Yeah, I'd like for those justifications be in the commit messages please.

> > We'd like to add them to our test pile.
> 

So why are you sending those for the kernel now is so many other things are
still moving?

What if something in those things change? Then you need to touch those
again...

---

## [8] Gerd Hoffmann — 2025-06-02
*Subject: Re: [PATCH 1/2] x86/sev/vc: fix efi runtime instruction emulation*

On Fri, May 30, 2025 at 01:02:33AM +0200, Borislav Petkov wrote:
> On Wed, May 28, 2025 at 09:38:24AM +0200, Gerd Hoffmann wrote:
> > Use case is coconut-svsm providing an uefi variable store and edk2

Ok

> > > We'd like to add them to our test pile.
> > 

Well, the need for instruction emulation to work for uefi runtime code
and the need to have access to the caa page is not going to change even
if details of edk2 <=> svsm protocol communication will be updated.

take care,
  Gerd

---
