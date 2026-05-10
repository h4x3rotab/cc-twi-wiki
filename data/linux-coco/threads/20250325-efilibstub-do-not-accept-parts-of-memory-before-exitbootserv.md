---
title: 'efi/libstub: Do not accept parts of memory before ExitBootServices()'
date: 2025-03-25
last_reply: 2025-04-02
message_count: 12
participants: ['Ard Biesheuvel', 'Kirill A. Shutemov', 'Ard Biesheuvel', 'Tom Lendacky']
---

## [1] Ard Biesheuvel — 2025-03-25

From: Ard Biesheuvel <ardb@kernel.org>

Currently, setup_e820() in the x86 EFI stub records unaccepted memory in
the associated bitmap, which has a 2 MiB granularity. To avoid
ambiguities, any unaccepted region that is not aligned to 2 MiB will be
partially accepted upfront, so that all regions recorded into the bitmap
are aligned to the bitmap's granularity.

On SEV-SNP, this results in calls into the SEV support code before it is
initialized, and crucially, before ExitBootServices() is called, which
means that the firmware is still in charge at that point, and
initializing the SEV support code is not even permitted.

So instead, round the unaccepted regions outwards, so that all
unaccepted memory is recorded as such in the bitmap, along with possibly
some pages that have already been accepted. This is less efficient in
theory, but should rarely occur -and therefore not matter- in practice.

Cc: Tom Lendacky <thomas.lendacky@amd.com>,
Cc: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
Cc: Borislav Petkov <bp@alien8.de>,
Cc: Dionna Amalie Glaze <dionnaglaze@google.com>,
Cc: Kevin Loughlin <kevinloughlin@google.com>
Fixes: 745e3ed85f71 ("efi/libstub: Implement support for unaccepted memory")
Signed-off-by: Ard Biesheuvel <ardb@kernel.org>
---
 drivers/firmware/efi/libstub/unaccepted_memory.c | 75 ++++----------------
 1 file changed, 14 insertions(+), 61 deletions(-)

diff --git a/drivers/firmware/efi/libstub/unaccepted_memory.c b/drivers/firmware/efi/libstub/unaccepted_memory.c
index 757dbe734a47..8d783fda5ce3 100644
--- a/drivers/firmware/efi/libstub/unaccepted_memory.c
+++ b/drivers/firmware/efi/libstub/unaccepted_memory.c
@@ -88,86 +88,39 @@ efi_status_t allocate_unaccepted_bitmap(__u32 nr_desc,
 
 /*
  * The accepted memory bitmap only works at unit_size granularity.  Take
- * unaligned start/end addresses and either:
- *  1. Accepts the memory immediately and in its entirety
- *  2. Accepts unaligned parts, and marks *some* aligned part unaccepted
+ * unaligned start/end addresses and round them outwards, so that unaccepted
+ * memory is never misidentified as already accepted.
  *
  * The function will never reach the bitmap_set() with zero bits to set.
  */
 void process_unaccepted_memory(u64 start, u64 end)
 {
 	u64 unit_size = unaccepted_table->unit_size;
-	u64 unit_mask = unaccepted_table->unit_size - 1;
 	u64 bitmap_size = unaccepted_table->size;
 
-	/*
-	 * Ensure that at least one bit will be set in the bitmap by
-	 * immediately accepting all regions under 2*unit_size.  This is
-	 * imprecise and may immediately accept some areas that could
-	 * have been represented in the bitmap.  But, results in simpler
-	 * code below
-	 *
-	 * Consider case like this (assuming unit_size == 2MB):
-	 *
-	 * | 4k | 2044k |    2048k   |
-	 * ^ 0x0        ^ 2MB        ^ 4MB
-	 *
-	 * Only the first 4k has been accepted. The 0MB->2MB region can not be
-	 * represented in the bitmap. The 2MB->4MB region can be represented in
-	 * the bitmap. But, the 0MB->4MB region is <2*unit_size and will be
-	 * immediately accepted in its entirety.
-	 */
-	if (end - start < 2 * unit_size) {
-		arch_accept_memory(start, end);
-		return;
-	}
-
-	/*
-	 * No matter how the start and end are aligned, at least one unaccepted
-	 * unit_size area will remain to be marked in the bitmap.
-	 */
-
-	/* Immediately accept a <unit_size piece at the start: */
-	if (start & unit_mask) {
-		arch_accept_memory(start, round_up(start, unit_size));
-		start = round_up(start, unit_size);
-	}
-
-	/* Immediately accept a <unit_size piece at the end: */
-	if (end & unit_mask) {
-		arch_accept_memory(round_down(end, unit_size), end);
-		end = round_down(end, unit_size);
-	}
+	start = round_down(start, unit_size);
+	end   = round_up(end, unit_size);
 
 	/*
-	 * Accept part of the range that before phys_base and cannot be recorded
+	 * Ignore the range before phys_base that cannot be recorded
 	 * into the bitmap.
 	 */
-	if (start < unaccepted_table->phys_base) {
-		arch_accept_memory(start,
-				   min(unaccepted_table->phys_base, end));
+	if (start < unaccepted_table->phys_base)
 		start = unaccepted_table->phys_base;
-	}
-
-	/* Nothing to record */
-	if (end < unaccepted_table->phys_base)
-		return;
 
 	/* Translate to offsets from the beginning of the bitmap */
 	start -= unaccepted_table->phys_base;
 	end -= unaccepted_table->phys_base;
 
-	/* Accept memory that doesn't fit into bitmap */
-	if (end > bitmap_size * unit_size * BITS_PER_BYTE) {
-		unsigned long phys_start, phys_end;
-
-		phys_start = bitmap_size * unit_size * BITS_PER_BYTE +
-			     unaccepted_table->phys_base;
-		phys_end = end + unaccepted_table->phys_base;
+	/*
+	 * Disregard unaccepted memory that did not exist yet when the bitmap
+	 * was dimensioned and allocated. This shouldn't happen in practice.
+	 */
+	end = min(end, bitmap_size * unit_size * BITS_PER_BYTE);
 
-		arch_accept_memory(phys_start, phys_end);
-		end = bitmap_size * unit_size * BITS_PER_BYTE;
-	}
+	/* Nothing to record */
+	if (end <= start)
+		return;
 
 	/*
 	 * 'start' and 'end' are now both unit_size-aligned.

---

## [2] Kirill A. Shutemov — 2025-03-25
*Subject: Re: [PATCH] efi/libstub: Do not accept parts of memory before
 ExitBootServices()*

On Tue, Mar 25, 2025 at 10:16:15AM +0100, Ard Biesheuvel wrote:
> From: Ard Biesheuvel <ardb@kernel.org>
> 

NAK.

It opens us for double-accept attacks:

https://lore.kernel.org/all/zuz27i7ffrsa3hksveuroxpwxos5qx65py23gvupaadizwrsss@uhb6ye4j2eqn/

---

## [3] Ard Biesheuvel — 2025-03-25
*Subject: Re: [PATCH] efi/libstub: Do not accept parts of memory before ExitBootServices()*

On Tue, 25 Mar 2025 at 13:36, Kirill A. Shutemov
<kirill.shutemov@linux.intel.com> wrote:
>
> On Tue, Mar 25, 2025 at 10:16:15AM +0100, Ard Biesheuvel wrote:

So what fix are you proposing? The code is currently broken.

---

## [4] Kirill A. Shutemov — 2025-03-25
*Subject: Re: [PATCH] efi/libstub: Do not accept parts of memory before
 ExitBootServices()*

On Tue, Mar 25, 2025 at 01:41:04PM +0100, Ard Biesheuvel wrote:
> On Tue, 25 Mar 2025 at 13:36, Kirill A. Shutemov
> <kirill.shutemov@linux.intel.com> wrote:

I don't know SEV specifics, but I wounder how BIOS itself accepts the
memory?

Since the problem happens before ExitBootServices(), can we allocate this
memory range with EFI API and free it back?

---

## [5] Ard Biesheuvel — 2025-03-25
*Subject: Re: [PATCH] efi/libstub: Do not accept parts of memory before ExitBootServices()*

On Tue, 25 Mar 2025 at 13:59, Kirill A. Shutemov
<kirill.shutemov@linux.intel.com> wrote:
>
> On Tue, Mar 25, 2025 at 01:41:04PM +0100, Ard Biesheuvel wrote:

That is an implementation detail, so it doesn't really matter. The
firmware owns the platform, and is therefore in charge of
communicating with the hypervisor and/or the VMM, and the code running
in the EFI stub should not go behind its back and communicate
directly.

> Since the problem happens before ExitBootServices(), can we allocate this
> memory range with EFI API and free it back?

In principle, yes - we could allocate these misaligned chunks as
EfiLoaderData, and it wouldn't even be necessary to free them, as they
would become available to the OS automatically.

But doing this in setup_e820() is tricky, because every page
allocation modifies the EFI memory map, and we may have to restart
from the beginning. And there is no guarantee that some asynchronous
event in the firmware context does not attempt to allocate some pages,
in a way that might result in another misaligned unaccepted region.

So ideally, firmware would adopt the same granularity when accepting
memory, and we wouldn't have this problem. (Or maybe this is why
nobody noticed until I found it by inspection?)

---

## [6] Kirill A. Shutemov — 2025-03-25
*Subject: Re: [PATCH] efi/libstub: Do not accept parts of memory before
 ExitBootServices()*

On Tue, Mar 25, 2025 at 02:09:54PM +0100, Ard Biesheuvel wrote:
> > Since the problem happens before ExitBootServices(), can we allocate this
> > memory range with EFI API and free it back?

Looking again at the code, setup_e820() (and therefore
process_unaccepted_memory()) called after efi_exit_boot_services() in
exit_boot(), so we can't use EFI API to allocate memory.

And it bring us back to the issue being platform-specific. It should be
able to accept memory in principle.

I remember testing TDX boot with ridiculously large unit_size, like 256M.
And accept logic worked fine for me.

> So ideally, firmware would adopt the same granularity when accepting
> memory, and we wouldn't have this problem. (Or maybe this is why

It would be nice, yes, but we need to deal with requirements in current
spec.

---

## [7] Ard Biesheuvel — 2025-03-25
*Subject: Re: [PATCH] efi/libstub: Do not accept parts of memory before ExitBootServices()*

On Tue, 25 Mar 2025 at 14:44, Kirill A. Shutemov
<kirill.shutemov@linux.intel.com> wrote:
>
> On Tue, Mar 25, 2025 at 02:09:54PM +0100, Ard Biesheuvel wrote:

Ah yes, I misremembered that. It also means that it is fine in
principle to take over the communication with the hypervisor.

However, this is still tricky, because on SEV-SNP, accepting memory
appears to rely on the GHCB page based communication being enabled,
and this involves mapping it down to a single page so the C bit can be
cleared. It would be nice if we could simply use the MSR based
protocol for accepting memory.

> And it bring us back to the issue being platform-specific. It should be
> able to accept memory in principle.

Indeed.

> I remember testing TDX boot with ridiculously large unit_size, like 256M.
> And accept logic worked fine for me.

Yeah :-(

---

## [8] Tom Lendacky — 2025-03-25
*Subject: Re: [PATCH] efi/libstub: Do not accept parts of memory before
 ExitBootServices()*

On 3/25/25 09:39, Ard Biesheuvel wrote:
> On Tue, 25 Mar 2025 at 14:44, Kirill A. Shutemov
> <kirill.shutemov@linux.intel.com> wrote:

We can probably do something along this line since there is an existing
function, __page_state_change(), that performs MSR protocol PSC. If we
change the arch_accept_memory() calls in process_unaccepted_memory() to
arch_accept_memory_early() then we can differentiate between this early
alignment setup timeframe. The early function can also use
sev_get_status() instead of sev_snp_enabled().

Let me mess around with it a bit and see what I come up with.

Thanks,
Tom

> 
>> And it bring us back to the issue being platform-specific. It should be

---

## [9] Ard Biesheuvel — 2025-03-26
*Subject: Re: [PATCH] efi/libstub: Do not accept parts of memory before ExitBootServices()*

On Tue, 25 Mar 2025 at 17:30, Tom Lendacky <thomas.lendacky@amd.com> wrote:
>
> On 3/25/25 09:39, Ard Biesheuvel wrote:

Cheers.

So IIUC, it would be sufficient to check sev_get_status() against
MSR_AMD64_SEV_SNP_ENABLED, and use the PSC MSR to transition each
unaccepted page that is in the misaligned head or tail of the region
to private.

Pardon my ignorance, but does that mean that in principle,
sev_enable() et al could be deferred to early startup of the kernel
proper (where the other SEV startup code lives) ?

We have been playing whack-a-mole with PIC codegen issues there, and
so it might make sense to consolidate that logic into a single [PIC]
chunk of code that is somewhat isolated from the rest of the code
(like the kernel/pi code on arm64)

---

## [10] Tom Lendacky — 2025-04-01
*Subject: Re: [PATCH] efi/libstub: Do not accept parts of memory before
 ExitBootServices()*

On 3/26/25 04:28, Ard Biesheuvel wrote:
> On Tue, 25 Mar 2025 at 17:30, Tom Lendacky <thomas.lendacky@amd.com> wrote:
>>

This is what I came up with below. @Ard and @Kirill, let me know if it
looks ok to you and, if so, I'll submit a formal patch where we can work
on naming, etc.

> 
> So IIUC, it would be sufficient to check sev_get_status() against

I'm not sure if it can be. There is a bunch of code in the sev_enable()
path that I'm not sure can be moved. I'd have to look a lot closer to
determine that.

Thanks,
Tom

> 
> We have been playing whack-a-mole with PIC codegen issues there, and

diff --git a/arch/x86/boot/compressed/mem.c b/arch/x86/boot/compressed/mem.c
index dbba332e4a12..b115a73ca25e 100644
--- a/arch/x86/boot/compressed/mem.c
+++ b/arch/x86/boot/compressed/mem.c
@@ -32,19 +32,42 @@ static bool early_is_tdx_guest(void)
 	return is_tdx;
 }
 
-void arch_accept_memory(phys_addr_t start, phys_addr_t end)
+static bool is_sev_snp_enabled(bool early)
+{
+	return early ? early_sev_snp_enabled() : sev_snp_enabled();
+}
+
+static void __arch_accept_memory(phys_addr_t start, phys_addr_t end, bool early)
 {
 	/* Platform-specific memory-acceptance call goes here */
 	if (early_is_tdx_guest()) {
 		if (!tdx_accept_memory(start, end))
 			panic("TDX: Failed to accept memory\n");
-	} else if (sev_snp_enabled()) {
-		snp_accept_memory(start, end);
+	} else if (is_sev_snp_enabled(early)) {
+		/*
+		 * Calls when memory acceptance is being setup require SNP
+		 * to use the GHCB protocol because the current pagetable
+		 * mappings can't change the early GHCB page to shared.
+		 */
+		if (early)
+			snp_accept_memory_early(start, end);
+		else
+			snp_accept_memory(start, end);
 	} else {
 		error("Cannot accept memory: unknown platform\n");
 	}
 }
 
+void arch_accept_memory(phys_addr_t start, phys_addr_t end)
+{
+	__arch_accept_memory(start, end, false);
+}
+
+void arch_accept_memory_early(phys_addr_t start, phys_addr_t end)
+{
+	__arch_accept_memory(start, end, true);
+}
+
 bool init_unaccepted_memory(void)
 {
 	guid_t guid = LINUX_EFI_UNACCEPTED_MEM_TABLE_GUID;
diff --git a/arch/x86/boot/compressed/sev.c b/arch/x86/boot/compressed/sev.c
index bb55934c1cee..162484d662f1 100644
--- a/arch/x86/boot/compressed/sev.c
+++ b/arch/x86/boot/compressed/sev.c
@@ -157,6 +157,12 @@ static int svsm_perform_call_protocol(struct svsm_call *call)
 	return ret;
 }
 
+/* Used before sev_enable() has been called during unaccepted memory init */
+bool early_sev_snp_enabled(void)
+{
+	return sev_get_status() & MSR_AMD64_SEV_SNP_ENABLED;
+}
+
 bool sev_snp_enabled(void)
 {
 	return sev_status & MSR_AMD64_SEV_SNP_ENABLED;
@@ -164,10 +170,7 @@ bool sev_snp_enabled(void)
 
 static void __page_state_change(unsigned long paddr, enum psc_op op)
 {
-	u64 val;
-
-	if (!sev_snp_enabled())
-		return;
+	u64 val, msr;
 
 	/*
 	 * If private -> shared then invalidate the page before requesting the
@@ -176,6 +179,9 @@ static void __page_state_change(unsigned long paddr, enum psc_op op)
 	if (op == SNP_PAGE_STATE_SHARED)
 		pvalidate_4k_page(paddr, paddr, false);
 
+	/* Save the current GHCB MSR value */
+	msr = sev_es_rd_ghcb_msr();
+
 	/* Issue VMGEXIT to change the page state in RMP table. */
 	sev_es_wr_ghcb_msr(GHCB_MSR_PSC_REQ_GFN(paddr >> PAGE_SHIFT, op));
 	VMGEXIT();
@@ -185,6 +191,9 @@ static void __page_state_change(unsigned long paddr, enum psc_op op)
 	if ((GHCB_RESP_CODE(val) != GHCB_MSR_PSC_RESP) || GHCB_MSR_PSC_RESP_VAL(val))
 		sev_es_terminate(SEV_TERM_SET_LINUX, GHCB_TERM_PSC);
 
+	/* Restore the GHCB MSR value */
+	sev_es_wr_ghcb_msr(msr);
+
 	/*
 	 * Now that page state is changed in the RMP table, validate it so that it is
 	 * consistent with the RMP entry.
@@ -195,11 +204,17 @@ static void __page_state_change(unsigned long paddr, enum psc_op op)
 
 void snp_set_page_private(unsigned long paddr)
 {
+	if (!sev_snp_enabled())
+		return;
+
 	__page_state_change(paddr, SNP_PAGE_STATE_PRIVATE);
 }
 
 void snp_set_page_shared(unsigned long paddr)
 {
+	if (!sev_snp_enabled())
+		return;
+
 	__page_state_change(paddr, SNP_PAGE_STATE_SHARED);
 }
 
@@ -261,6 +276,11 @@ static phys_addr_t __snp_accept_memory(struct snp_psc_desc *desc,
 	return pa;
 }
 
+/*
+ * The memory acceptance support uses the boot GHCB page to perform
+ * the required page state change operation before validating the
+ * pages.
+ */
 void snp_accept_memory(phys_addr_t start, phys_addr_t end)
 {
 	struct snp_psc_desc desc = {};
@@ -275,6 +295,23 @@ void snp_accept_memory(phys_addr_t start, phys_addr_t end)
 		pa = __snp_accept_memory(&desc, pa, end);
 }
 
+/*
+ * The early version of memory acceptance is needed when being called
+ * from the EFI stub driver. The pagetable manipulation to mark the
+ * boot GHCB page as shared can't be performed at this stage, so use
+ * the GHCB page state change MSR protocol instead.
+ */
+void snp_accept_memory_early(phys_addr_t start, phys_addr_t end)
+{
+	phys_addr_t pa;
+
+	pa = start;
+	while (pa < end) {
+		__page_state_change(pa, SNP_PAGE_STATE_PRIVATE);
+		pa += PAGE_SIZE;
+	}
+}
+
 void sev_es_shutdown_ghcb(void)
 {
 	if (!boot_ghcb)
diff --git a/arch/x86/boot/compressed/sev.h b/arch/x86/boot/compressed/sev.h
index fc725a981b09..8a135c9c043a 100644
--- a/arch/x86/boot/compressed/sev.h
+++ b/arch/x86/boot/compressed/sev.h
@@ -10,13 +10,17 @@
 
 #ifdef CONFIG_AMD_MEM_ENCRYPT
 
+bool early_sev_snp_enabled(void);
 bool sev_snp_enabled(void);
 void snp_accept_memory(phys_addr_t start, phys_addr_t end);
+void snp_accept_memory_early(phys_addr_t start, phys_addr_t end);
 
 #else
 
+static inline bool early_sev_snp_enabled(void) { return false; }
 static inline bool sev_snp_enabled(void) { return false; }
 static inline void snp_accept_memory(phys_addr_t start, phys_addr_t end) { }
+static inline void snp_accept_memory_early(phys_addr_t start, phys_addr_t end) { }
 
 #endif
 
diff --git a/drivers/firmware/efi/libstub/efistub.h b/drivers/firmware/efi/libstub/efistub.h
index d96d4494070d..676aa30df52e 100644
--- a/drivers/firmware/efi/libstub/efistub.h
+++ b/drivers/firmware/efi/libstub/efistub.h
@@ -1233,5 +1233,6 @@ efi_status_t allocate_unaccepted_bitmap(__u32 nr_desc,
 void process_unaccepted_memory(u64 start, u64 end);
 void accept_memory(phys_addr_t start, unsigned long size);
 void arch_accept_memory(phys_addr_t start, phys_addr_t end);
+void arch_accept_memory_early(phys_addr_t start, phys_addr_t end);
 
 #endif
diff --git a/drivers/firmware/efi/libstub/unaccepted_memory.c b/drivers/firmware/efi/libstub/unaccepted_memory.c
index 757dbe734a47..1955eddc85f1 100644
--- a/drivers/firmware/efi/libstub/unaccepted_memory.c
+++ b/drivers/firmware/efi/libstub/unaccepted_memory.c
@@ -118,7 +118,7 @@ void process_unaccepted_memory(u64 start, u64 end)
 	 * immediately accepted in its entirety.
 	 */
 	if (end - start < 2 * unit_size) {
-		arch_accept_memory(start, end);
+		arch_accept_memory_early(start, end);
 		return;
 	}
 
@@ -129,13 +129,13 @@ void process_unaccepted_memory(u64 start, u64 end)
 
 	/* Immediately accept a <unit_size piece at the start: */
 	if (start & unit_mask) {
-		arch_accept_memory(start, round_up(start, unit_size));
+		arch_accept_memory_early(start, round_up(start, unit_size));
 		start = round_up(start, unit_size);
 	}
 
 	/* Immediately accept a <unit_size piece at the end: */
 	if (end & unit_mask) {
-		arch_accept_memory(round_down(end, unit_size), end);
+		arch_accept_memory_early(round_down(end, unit_size), end);
 		end = round_down(end, unit_size);
 	}
 
@@ -144,8 +144,8 @@ void process_unaccepted_memory(u64 start, u64 end)
 	 * into the bitmap.
 	 */
 	if (start < unaccepted_table->phys_base) {
-		arch_accept_memory(start,
-				   min(unaccepted_table->phys_base, end));
+		arch_accept_memory_early(start,
+					 min(unaccepted_table->phys_base, end));
 		start = unaccepted_table->phys_base;
 	}
 
@@ -165,7 +165,7 @@ void process_unaccepted_memory(u64 start, u64 end)
 			     unaccepted_table->phys_base;
 		phys_end = end + unaccepted_table->phys_base;
 
-		arch_accept_memory(phys_start, phys_end);
+		arch_accept_memory_early(phys_start, phys_end);
 		end = bitmap_size * unit_size * BITS_PER_BYTE;
 	}

---

## [11] Ard Biesheuvel — 2025-04-01
*Subject: Re: [PATCH] efi/libstub: Do not accept parts of memory before ExitBootServices()*

On Tue, 1 Apr 2025 at 18:51, Tom Lendacky <thomas.lendacky@amd.com> wrote:
>
> On 3/26/25 04:28, Ard Biesheuvel wrote:

Thanks for putting this together.

Some questions below.

> >
> > So IIUC, it would be sufficient to check sev_get_status() against

Why is the latter test not suitable early on? Simply because
sev_status is not initialized yet?

> +}
> +

I think it would be better to structure this slightly differently.
I'll have a stab at this myself and get back to you.

> +                       snp_accept_memory_early(start, end);
> +               else

Could you explain how the below code now knows how to decide whether
to use the MSR protocol or the GHCB page based one?

>         /*
>          * If private -> shared then invalidate the page before requesting the

Nit: please make this

for (phys_addr_t pa = start; pa < end; pa += PAGE_SIZE)

and drop the braces

> +               __page_state_change(pa, SNP_PAGE_STATE_PRIVATE);
> +               pa += PAGE_SIZE;

---

## [12] Tom Lendacky — 2025-04-02
*Subject: Re: [PATCH] efi/libstub: Do not accept parts of memory before
 ExitBootServices()*

On 4/1/25 13:45, Ard Biesheuvel wrote:
> On Tue, 1 Apr 2025 at 18:51, Tom Lendacky <thomas.lendacky@amd.com> wrote:
>>

Right. I was following the example of calling sev_get_status() before
sev_enable() has been invoked.

> 
>> +}

Sounds good.

> 
>> +                       snp_accept_memory_early(start, end);

The __page_state_change() routine only performs the MSR protocol version
of a page state change, no decision is made between the two at this stage.

> 
>>         /*

Doh! Yes.

> 
>> +               __page_state_change(pa, SNP_PAGE_STATE_PRIVATE);

---
