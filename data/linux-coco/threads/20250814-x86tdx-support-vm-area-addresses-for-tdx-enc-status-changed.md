---
title: 'x86/tdx: support VM area addresses for tdx_enc_status_changed'
date: 2025-08-14
last_reply: 2025-08-18
message_count: 6
participants: ['Shixuan Zhao', 'Kiryl Shutsemau', 'Sathyanarayanan Kuppuswamy', 'Michael Kelley']
---

## [1] Shixuan Zhao — 2025-08-14

Currently tdx_enc_status_changed uses __pa which will only accept
addresses within the linear mapping. This patch allows memory allocated
in the VM area to be used.

For VM area addresses, we do it page-by-page since there's no guarantee
that the physical pages are contiguous. If, however, the entire range
falls within the linear mapping, we provide a fast path that do the
entire range just like the current version so that the performance
would remain roughly the same as current.

Signed-off-by: Shixuan Zhao <shixuan.zhao@hotmail.com>
---
Hi,

I recently ran into a problem where tdx_enc_status_changed was not
implemented to handle memory mapped in the kernel VM area (e.g., ioremap
or vmalloc). I have created a patch that tries to fix this problem. The
overall idea is to keep a fast path for the current __pa-based routine
if the range falls within the linear mapping, otherwise fall to a page-by-
page page table walk for those in the VM area.

It's the first time I'm submitting a patch to the kernel so although I've
done the RTFM, feel free to discuss or point out anything improper.

Thanks,
Shixuan

 arch/x86/coco/tdx/tdx.c | 42 ++++++++++++++++++++++++++++++++++-------
 1 file changed, 35 insertions(+), 7 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 7b2833705..c56cd429f 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -957,15 +957,11 @@ static bool tdx_map_gpa(phys_addr_t start, phys_addr_t end, bool enc)
 }
 
 /*
- * Inform the VMM of the guest's intent for this physical page: shared with
- * the VMM or private to the guest.  The VMM is expected to change its mapping
- * of the page in response.
+ * Helper that works on a paddr range for tdx_enc_status_changed
  */
-static bool tdx_enc_status_changed(unsigned long vaddr, int numpages, bool enc)
+static bool tdx_enc_status_changed_phys(phys_addr_t start, phys_addr_t end,
+					bool enc)
 {
-	phys_addr_t start = __pa(vaddr);
-	phys_addr_t end   = __pa(vaddr + numpages * PAGE_SIZE);
-
 	if (!tdx_map_gpa(start, end, enc))
 		return false;
 
@@ -976,6 +972,38 @@ static bool tdx_enc_status_changed(unsigned long vaddr, int numpages, bool enc)
 	return true;
 }
 
+/*
+ * Inform the VMM of the guest's intent for this vaddr range: shared with
+ * the VMM or private to the guest.  The VMM is expected to change its mapping
+ * of the page in response.
+ */
+static bool tdx_enc_status_changed(unsigned long vaddr, int numpages, bool enc)
+{
+	unsigned long va_iter;
+	unsigned long end_va = vaddr + numpages * PAGE_SIZE;
+	phys_addr_t start_pa, end_pa;
+
+	/* fast path when the entire range is within linear mapping */
+	if (virt_addr_valid((void *)vaddr) &&
+	    virt_addr_valid((void *)end_va)) {
+		start_pa = __pa(vaddr);
+		end_pa = __pa(end_va);
+
+		return tdx_enc_status_changed_phys(start_pa, end_pa, enc);
+	}
+
+	/* use page table walk for memory in VM area */
+	for (va_iter = vaddr; va_iter < end_va; va_iter += PAGE_SIZE) {
+		start_pa = slow_virt_to_phys((void *)va_iter);
+		end_pa = start_pa + PAGE_SIZE;
+
+		if (!tdx_enc_status_changed_phys(start_pa, end_pa, enc))
+			return false;
+	}
+
+	return true;
+}
+
 static int tdx_enc_status_change_prepare(unsigned long vaddr, int numpages,
 					 bool enc)
 {

---

## [2] Kiryl Shutsemau — 2025-08-15
*Subject: Re: [PATCH] x86/tdx: support VM area addresses for
 tdx_enc_status_changed*

On Thu, Aug 14, 2025 at 10:34:02PM -0400, Shixuan Zhao wrote:
> Currently tdx_enc_status_changed uses __pa which will only accept
> addresses within the linear mapping. This patch allows memory allocated

Could you tell more about use-case?

I am not sure we ever want to convert vmalloc()ed memory to shared as it
will result in fracturing direct mapping.

And it seems to the wrong layer to make it. If we really need to go
this pass (I am not convinced) it has to be done in set_memory.c

Sathya, I remember you did something similar for REPORT, right?

---

## [3] Sathyanarayanan Kuppuswamy — 2025-08-15
*Subject: Re: [PATCH] x86/tdx: support VM area addresses for
 tdx_enc_status_changed*

On 8/15/25 9:43 AM, Kiryl Shutsemau wrote:
> On Thu, Aug 14, 2025 at 10:34:02PM -0400, Shixuan Zhao wrote:
>> Currently tdx_enc_status_changed uses __pa which will only accept

Yes, we attempted something similar for Quote buffer allocation.

https://patchew.org/linux/20220609025220.2615197-1-sathyanarayanan.kuppuswamy@linux.intel.com/20220609025220.2615197-4-sathyanarayanan.kuppuswamy@linux.intel.com/

Our approach was to create an alias virtual mapping for the Quote buffer to
avoid modifying direct map page attributes. However, we eventually dropped
this idea due to the complexity of keeping the alias mapping in sync, as well
as issues with load_unaligned_zeropad().

Related discussion can be found in,

https://patchew.org/linux/20220609025220.2615197-1-sathyanarayanan.kuppuswamy@linux.intel.com/20220609025220.2615197-5-sathyanarayanan.kuppuswamy@linux.intel.com/

>

---

## [4] Shixuan Zhao — 2025-08-15
*Subject: Re: [PATCH] x86/tdx: support VM area addresses for tdx_enc_status_changed*

Sorry got the Message ID wrong. Resending it.

> Could you tell more about use-case?

So basically I'm writing a project involving a kernel module that
communicates with the host which we plan to do it via a shared buffer.
That shared buffer has to be marked as shared so that the hypervisor can
read it. The shared buffer needs a fixed physical address in our case so
we reserved a range and did ioremap for it.

> I am not sure we ever want to convert vmalloc()ed memory to shared as it
> will result in fracturing direct mapping.

Currently in this patch, linear mapping memory will still be handled in
the old way so there's technically no change to existing behaviour. These
memory ranges are still mapped in a whole chunk instead of page-by-page It
merely added a fall back path for vmalloc'ed or ioremap'ed or whatever
mapping that's not in the linear mapping.

tdx_enc_status_changed is called by set_memory_decrypted/encrypted which
takes vmalloc'ed addresses just fine on other platforms like SEV. It would
be an exception for TDX to not support VM area mappings.

> And it seems to the wrong layer to make it. If we really need to go
> this pass (I am not convinced) it has to be done in set_memory.c

set_memory_decrypted handles vmalloc'ed memory. It's just that on TDX it
has to call the TDX-specific enc_status_change_finish which is
tdx_enc_status_changed that does not handle vmalloc'ed memory. This
means that when people call the set_memory_decrypted with a vmalloc'ed,
it will fail on TDX but will succeed in other platforms (e.g., SEV).

Thanks,
Shixuan

---

## [5] Michael Kelley — 2025-08-17
*Subject: RE: [PATCH] x86/tdx: support VM area addresses for
 tdx_enc_status_changed*

From: Shixuan Zhao <shixuan.zhao@hotmail.com> Sent: Thursday, August 14, 2025 7:34 PM
> 
> Currently tdx_enc_status_changed uses __pa which will only accept

Dexuan Cui submitted a patch to do this about a year ago [1]. The patch has
a long history, including being part of a larger patch set in an earlier version.
It appears that it still had an issue when the discussion stopped, and the patch
was never picked up.

Dexuan's use case was TDX guests running on Hyper-V, and the Hyper-V
synthetic networking driver (netvsc) needing to mark a 16 MiB vmalloc()'ed
receive buffer area as shared. But that use case applied only when running
without a paravisor, and it may have gone on the back-burner because
of Azure/Hyper-V CoCo guests always running with a paravisor.

Adding Dexuan to this thread in case he has additional insight into why his
patch didn't go forward.

Michael Kelley

[1] https://lore.kernel.org/lkml/20240708183946.3991-1-decui@microsoft.com/

> 
> For VM area addresses, we do it page-by-page since there's no guarantee

---

## [6] Kiryl Shutsemau — 2025-08-18
*Subject: Re: [PATCH] x86/tdx: support VM area addresses for
 tdx_enc_status_changed*

On Fri, Aug 15, 2025 at 02:18:34PM -0400, Shixuan Zhao wrote:
> Sorry got the Message ID wrong. Resending it.
> 

So on the host side it is going non-contiguous. Is it going to be some
kind of scatter-gather? Seems inefficient.

What sizes are we talking about? When do you allocate it?

If it is small enough and/or allocated early enough I would rather go
with guest physically contiguous. 

> > I am not sure we ever want to convert vmalloc()ed memory to shared as it
> > will result in fracturing direct mapping.

You cannot leave the same GPAs mapped as private in the direct mapping
as it will cause unrecoverable SEPT violation when someone would touch
this memory. For instance, load_unaligned_zeropad()

> tdx_enc_status_changed is called by set_memory_decrypted/encrypted which
> takes vmalloc'ed addresses just fine on other platforms like SEV. It would

I don't know SEV specifics, but with TDX, I don't want to add support
for vmalloc, unless it is a must. It requires fracturing direct mapping
and we need really strong reason to do this.

---
