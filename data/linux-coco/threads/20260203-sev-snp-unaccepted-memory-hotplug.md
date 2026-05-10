---
title: 'SEV-SNP Unaccepted Memory Hotplug'
date: 2026-02-03
last_reply: 2026-02-16
message_count: 15
participants: ['Pratik R. Sampat', 'Kiryl Shutsemau', 'David Hildenbrand (arm)']
---

## [1] Pratik R. Sampat — 2026-02-03

Guest memory hot-plug/remove via the QEMU monitor is used by virtual
machines to dynamically scale the memory capacity of a system with
virtually zero downtime to the guest. For confidential VMs, memory has
to be first accepted before it can be used. Add support to accept
memory that has been hot-added and revert back it's state for
hypervisors to be able to use the pages during hot-remove.

Usage (for SNP guests)
----------------------
Step1: Spawn a QEMU SNP guest with the additional parameter of slots and
maximum possible memory, along with the initial memory as below:
"-m X,slots=Y,maxmem=Z".

Step2: Once the guest is booted, launch the qemu monitor and hotplug
the memory as follows:
(qemu) object_add memory-backend-memfd,id=mem1,size=1G
(qemu) device_add pc-dimm,id=dimm1,memdev=mem1

Memory is accepted up-front when added to the guest.

If using auto-onlining by either:
    a) echo online > /sys/devices/system/memory/auto_online_blocks, OR
    b) enable CONFIG_MHP_DEFAULT_ONLINE_TYPE_* while compiling kernel
Memory should show up automatically.

Otherwise, memory can also be onlined by echoing 1 to the newly added
blocks in: /sys/devices/system/memory/memoryXX/online

Step3: memory can be hot-removed via the qemu monitor using:
(qemu) device_remove dimm1
(qemu) object_remove mem1

Tip: Enable the kvm_convert_memory event in QEMU to observe memory
conversions between private and shared during hotplug/remove.

The series is based on
        git.kernel.org/pub/scm/virt/kvm/kvm.git next

Comments and feedback appreciated!

Changelog Patch v3..v4:
-----------------------
https://lore.kernel.org/all/20260128204105.508855-1-prsampat@amd.com/
1. Unconditionally accept all hotplug pages and set bitmap for the ones
   that are in the bit range (Kiryl)
2. Fix implementation similarly for unacceptance and merge
   unaccept_memory() implementation within unaccept_hotplug_memory()
3. Use max()/min() when clamping memory ranges to operate in the
   bitmap (Andrew)
4. Fall through arch_unaccept_memory() for TDX platforms (Kiryl).
   However, retain the panic() similar to arch_accept_memory() since
   it is a can't-happen scenario for other archs.

Changelog Patch v2..v3:
-----------------------
https://lore.kernel.org/all/20260112202300.43546-1-prsampat@amd.com/
1. Account for cold-plugged memory at boot and introduce proper handling
   of the unaccepted bitmap during both hotplug and remove. (Kiryl)
2. #include<asm/unaccepted_memory.h> within memory_hotplug caused build
   failures on non-x86 archs (Andrew). Instead of introducing
   #if-deffery to have arch agnostic fall throughs, create hotplug
   specific helper functions since we now also need to take care of
   managing the bitmaps due to 1. as well.

Changelog RFC..Patch v2:
------------------------
https://lore.kernel.org/all/20251125175753.1428857-1-prsampat@amd.com/
Based on feedback from the RFC, reworked the series to accept memory
upfront on hotplug. This is done for two reasons:
1. Avoids modifying the unaccepted bitmap. Extending the bitmap would
   require either:
   * Dynamically allocating the bitmap, which would need changes to EFI
     struct definitions, or
   * Pre-allocating a larger bitmap to accommodate hotpluggable memory.
     This poses challenges since e820 is parsed before SRAT, which
     contains the actual memory ranges information.
2. There are currently no known use-cases that would benefit from lazy
   acceptance of hotplugged ranges which warrants this additional
   complexity.

Pratik R. Sampat (2):
  mm/memory_hotplug: Add support to accept memory during hot-add
  x86/sev: Add support to unaccept memory after hot-remove

 arch/x86/coco/sev/core.c                 |  13 +++
 arch/x86/include/asm/sev.h               |   2 +
 arch/x86/include/asm/unaccepted_memory.h |  15 ++++
 drivers/firmware/efi/unaccepted_memory.c | 106 +++++++++++++++++++++++
 include/linux/mm.h                       |   9 ++
 mm/memory_hotplug.c                      |   4 +
 6 files changed, 149 insertions(+)

---

## [2] Pratik R. Sampat — 2026-02-03
*Subject: [PATCH v4 1/2] mm/memory_hotplug: Add support to accept memory during hot-add*

Confidential computing guests require memory to be accepted before use.
The unaccepted memory bitmap maintained by firmware does not track
most hotplugged memory ranges apart from system memory annotated to be
cold plugged at boot.

Explicitly validate and transition the newly added memory to a private
state, making it usable by the guest.

Signed-off-by: Pratik R. Sampat <prsampat@amd.com>
---
 drivers/firmware/efi/unaccepted_memory.c | 47 ++++++++++++++++++++++++
 include/linux/mm.h                       |  5 +++
 mm/memory_hotplug.c                      |  2 +
 3 files changed, 54 insertions(+)

diff --git a/drivers/firmware/efi/unaccepted_memory.c b/drivers/firmware/efi/unaccepted_memory.c
index c2c067eff634..359779133cb4 100644
--- a/drivers/firmware/efi/unaccepted_memory.c
+++ b/drivers/firmware/efi/unaccepted_memory.c
@@ -209,6 +209,53 @@ bool range_contains_unaccepted_memory(phys_addr_t start, unsigned long size)
 	return ret;
 }
 
+/*
+ * Unaccepted memory bitmap only covers initial boot memory and not the
+ * hotpluggable range that is part of SRAT parsing. However, some initial memory
+ * with the attribute EFI_MEMORY_HOT_PLUGGABLE can indicate boot time memory
+ * that can be hot-removed. Hence post acceptance, only for that range update
+ * the unaccepted bitmap to reflect this change.
+ */
+void accept_hotplug_memory(phys_addr_t start, unsigned long size)
+{
+	struct efi_unaccepted_memory *unaccepted;
+	unsigned long range_start, range_len;
+	phys_addr_t end = start + size;
+	u64 phys_base, unit_size;
+	unsigned long flags;
+
+	unaccepted = efi_get_unaccepted_table();
+	if (!unaccepted)
+		return;
+
+	/* Accept hotplug range unconditionally */
+	arch_accept_memory(start, end);
+
+	phys_base = unaccepted->phys_base;
+	unit_size = unaccepted->unit_size;
+
+	/* Only update bitmap for the region that is represented by it */
+	if (start >= phys_base + unaccepted->size * unit_size * BITS_PER_BYTE)
+		return;
+
+	start = max(start, phys_base);
+	if (end < phys_base)
+		return;
+
+	start -= phys_base;
+	end -= phys_base;
+
+	/* Make sure not to overrun the bitmap */
+	end = min(end, unaccepted->size * unit_size * BITS_PER_BYTE);
+
+	range_start = start / unit_size;
+	range_len = DIV_ROUND_UP(end, unit_size) - range_start;
+
+	spin_lock_irqsave(&unaccepted_memory_lock, flags);
+	bitmap_clear(unaccepted->bitmap, range_start, range_len);
+	spin_unlock_irqrestore(&unaccepted_memory_lock, flags);
+}
+
 #ifdef CONFIG_PROC_VMCORE
 static bool unaccepted_memory_vmcore_pfn_is_ram(struct vmcore_cb *cb,
 						unsigned long pfn)
diff --git a/include/linux/mm.h b/include/linux/mm.h
index 15076261d0c2..2d3c1ea40606 100644
--- a/include/linux/mm.h
+++ b/include/linux/mm.h
@@ -4504,6 +4504,7 @@ int set_anon_vma_name(unsigned long addr, unsigned long size,
 
 bool range_contains_unaccepted_memory(phys_addr_t start, unsigned long size);
 void accept_memory(phys_addr_t start, unsigned long size);
+void accept_hotplug_memory(phys_addr_t start, unsigned long size);
 
 #else
 
@@ -4517,6 +4518,10 @@ static inline void accept_memory(phys_addr_t start, unsigned long size)
 {
 }
 
+static inline void accept_hotplug_memory(phys_addr_t start, unsigned long size)
+{
+}
+
 #endif
 
 static inline bool pfn_is_unaccepted_memory(unsigned long pfn)
diff --git a/mm/memory_hotplug.c b/mm/memory_hotplug.c
index a63ec679d861..549ccfd190ee 100644
--- a/mm/memory_hotplug.c
+++ b/mm/memory_hotplug.c
@@ -1567,6 +1567,8 @@ int add_memory_resource(int nid, struct resource *res, mhp_t mhp_flags)
 	if (!strcmp(res->name, "System RAM"))
 		firmware_map_add_hotplug(start, start + size, "System RAM");
 
+	accept_hotplug_memory(start, size);
+
 	/* device_online() will take the lock when calling online_pages() */
 	mem_hotplug_done();

---

## [3] Pratik R. Sampat — 2026-02-03
*Subject: [PATCH v4 2/2] x86/sev: Add support to unaccept memory after hot-remove*

Transition memory to the shared state during a hot-remove operation so
that it can be re-used by the hypervisor. This also applies when memory
is intended to be hotplugged back in later, as those pages will need to
be re-accepted after crossing the trust boundary.

Signed-off-by: Pratik R. Sampat <prsampat@amd.com>
---
 arch/x86/coco/sev/core.c                 | 13 ++++++
 arch/x86/include/asm/sev.h               |  2 +
 arch/x86/include/asm/unaccepted_memory.h | 15 ++++++
 drivers/firmware/efi/unaccepted_memory.c | 59 ++++++++++++++++++++++++
 include/linux/mm.h                       |  4 ++
 mm/memory_hotplug.c                      |  2 +
 6 files changed, 95 insertions(+)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 9ae3b11754e6..63d8f44b76eb 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -703,6 +703,19 @@ void snp_accept_memory(phys_addr_t start, phys_addr_t end)
 	set_pages_state(vaddr, npages, SNP_PAGE_STATE_PRIVATE);
 }
 
+void snp_unaccept_memory(phys_addr_t start, phys_addr_t end)
+{
+	unsigned long vaddr, npages;
+
+	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
+		return;
+
+	vaddr = (unsigned long)__va(start);
+	npages = (end - start) >> PAGE_SHIFT;
+
+	set_pages_state(vaddr, npages, SNP_PAGE_STATE_SHARED);
+}
+
 static int vmgexit_ap_control(u64 event, struct sev_es_save_area *vmsa, u32 apic_id)
 {
 	bool create = event != SVM_VMGEXIT_AP_DESTROY;
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 0e6c0940100f..3327de663793 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -514,6 +514,7 @@ bool snp_init(struct boot_params *bp);
 void snp_dmi_setup(void);
 int snp_issue_svsm_attest_req(u64 call_id, struct svsm_call *call, struct svsm_attest_call *input);
 void snp_accept_memory(phys_addr_t start, phys_addr_t end);
+void snp_unaccept_memory(phys_addr_t start, phys_addr_t end);
 u64 snp_get_unsupported_features(u64 status);
 u64 sev_get_status(void);
 void sev_show_status(void);
@@ -623,6 +624,7 @@ static inline int snp_issue_svsm_attest_req(u64 call_id, struct svsm_call *call,
 	return -ENOTTY;
 }
 static inline void snp_accept_memory(phys_addr_t start, phys_addr_t end) { }
+static inline void snp_unaccept_memory(phys_addr_t start, phys_addr_t end) { }
 static inline u64 snp_get_unsupported_features(u64 status) { return 0; }
 static inline u64 sev_get_status(void) { return 0; }
 static inline void sev_show_status(void) { }
diff --git a/arch/x86/include/asm/unaccepted_memory.h b/arch/x86/include/asm/unaccepted_memory.h
index f5937e9866ac..91f01ad0ee03 100644
--- a/arch/x86/include/asm/unaccepted_memory.h
+++ b/arch/x86/include/asm/unaccepted_memory.h
@@ -18,6 +18,21 @@ static inline void arch_accept_memory(phys_addr_t start, phys_addr_t end)
 	}
 }
 
+static inline void arch_unaccept_memory(phys_addr_t start, phys_addr_t end)
+{
+	/*
+	 * TDX platforms do not require the guest to transition pages on remove
+	 * rather expect the VMM to remove the unplugged memory from SEPT
+	 */
+	if (cpu_feature_enabled(X86_FEATURE_TDX_GUEST)) {
+		return;
+	} else if (cc_platform_has(CC_ATTR_GUEST_SEV_SNP)) {
+		snp_unaccept_memory(start, end);
+	} else {
+		panic("Cannot unaccept memory: unknown platform\n");
+	}
+}
+
 static inline struct efi_unaccepted_memory *efi_get_unaccepted_table(void)
 {
 	if (efi.unaccepted == EFI_INVALID_TABLE_ADDR)
diff --git a/drivers/firmware/efi/unaccepted_memory.c b/drivers/firmware/efi/unaccepted_memory.c
index 359779133cb4..d11e7836200a 100644
--- a/drivers/firmware/efi/unaccepted_memory.c
+++ b/drivers/firmware/efi/unaccepted_memory.c
@@ -256,6 +256,65 @@ void accept_hotplug_memory(phys_addr_t start, unsigned long size)
 	spin_unlock_irqrestore(&unaccepted_memory_lock, flags);
 }
 
+/*
+ * Cold-plugged memory used with lazy acceptance may partially set pages to
+ * private. On removal, iterate through the bitmap to unaccept those ranges.
+ * For hotplug ranges beyond the bitmap, unaccept unconditionally.
+ */
+void unaccept_hotplug_memory(phys_addr_t start, unsigned long size)
+{
+	unsigned long range_start, range_end, bitrange_end;
+	phys_addr_t bitmap_end, end = start + size;
+	struct efi_unaccepted_memory *unaccepted;
+	u64 phys_base, unit_size;
+	unsigned long flags;
+
+	unaccepted = efi_get_unaccepted_table();
+	if (!unaccepted)
+		return;
+
+	phys_base = unaccepted->phys_base;
+	unit_size = unaccepted->unit_size;
+	bitmap_end = phys_base + unaccepted->size * unit_size * BITS_PER_BYTE;
+
+	/* Unaccept the entire hotplug range beyond the bitmap immediately */
+	if (start >= bitmap_end) {
+		arch_unaccept_memory(start, end);
+		return;
+	}
+
+	start = max(start, phys_base);
+	if (end < phys_base)
+		return;
+
+	/* Unaccept ranges when start is within the bitmap but end is beyond */
+	if (end > bitmap_end) {
+		arch_unaccept_memory(bitmap_end, end);
+		end = bitmap_end;
+	}
+
+	start -= phys_base;
+	end -= phys_base;
+
+	range_start = start / unit_size;
+	bitrange_end = DIV_ROUND_UP(end, unit_size);
+
+	/* Only unaccept memory that was previously accepted in the bitmap */
+	spin_lock_irqsave(&unaccepted_memory_lock, flags);
+	for_each_clear_bitrange_from(range_start, range_end, unaccepted->bitmap,
+				     bitrange_end) {
+		unsigned long phys_start, phys_end;
+		unsigned long len = range_end - range_start;
+
+		phys_start = range_start * unit_size + phys_base;
+		phys_end = range_end * unit_size + phys_base;
+
+		arch_unaccept_memory(phys_start, phys_end);
+		bitmap_set(unaccepted->bitmap, range_start, len);
+	}
+	spin_unlock_irqrestore(&unaccepted_memory_lock, flags);
+}
+
 #ifdef CONFIG_PROC_VMCORE
 static bool unaccepted_memory_vmcore_pfn_is_ram(struct vmcore_cb *cb,
 						unsigned long pfn)
diff --git a/include/linux/mm.h b/include/linux/mm.h
index 2d3c1ea40606..49b194cddda7 100644
--- a/include/linux/mm.h
+++ b/include/linux/mm.h
@@ -4505,6 +4505,7 @@ int set_anon_vma_name(unsigned long addr, unsigned long size,
 bool range_contains_unaccepted_memory(phys_addr_t start, unsigned long size);
 void accept_memory(phys_addr_t start, unsigned long size);
 void accept_hotplug_memory(phys_addr_t start, unsigned long size);
+void unaccept_hotplug_memory(phys_addr_t start, unsigned long size);
 
 #else
 
@@ -4522,6 +4523,9 @@ static inline void accept_hotplug_memory(phys_addr_t start, unsigned long size)
 {
 }
 
+static inline void unaccept_hotplug_memory(phys_addr_t start, unsigned long size)
+{
+}
 #endif
 
 static inline bool pfn_is_unaccepted_memory(unsigned long pfn)
diff --git a/mm/memory_hotplug.c b/mm/memory_hotplug.c
index 549ccfd190ee..21b87f2af930 100644
--- a/mm/memory_hotplug.c
+++ b/mm/memory_hotplug.c
@@ -2240,6 +2240,8 @@ static int try_remove_memory(u64 start, u64 size)
 
 	mem_hotplug_begin();
 
+	unaccept_hotplug_memory(start, size);
+
 	rc = memory_blocks_have_altmaps(start, size);
 	if (rc < 0) {
 		mem_hotplug_done();

---

## [4] Kiryl Shutsemau — 2026-02-04
*Subject: Re: [PATCH v4 1/2] mm/memory_hotplug: Add support to accept memory
 during hot-add*

On Tue, Feb 03, 2026 at 11:49:45AM -0600, Pratik R. Sampat wrote:
> Confidential computing guests require memory to be accepted before use.
> The unaccepted memory bitmap maintained by firmware does not track

This can be tricky.

If we boot a VM with <4GiB of memory and all of it is pre-accepted by
BIOS, the table will not be allocated.

But it doesn't mean that hotplugged memory above should not be accepted.

I don't think there is a way to detect such cases.

Your check is probably the best we can do, but it means VMs are going to
crash if memory accept is required by no table.

This is ugly situation.

---

## [5] David Hildenbrand (arm) — 2026-02-04
*Subject: Re: [PATCH v4 1/2] mm/memory_hotplug: Add support to accept memory
 during hot-add*

On 2/4/26 12:22, Kiryl Shutsemau wrote:
> On Tue, Feb 03, 2026 at 11:49:45AM -0600, Pratik R. Sampat wrote:
>> Confidential computing guests require memory to be accepted before use.

It's all starting to feel .... very hacky, sorry to say.

This should all be easier. If we expect memory hotplug (SRAT), why can't 
we just allocate the bitmap properly?

---

## [6] David Hildenbrand (arm) — 2026-02-04
*Subject: Re: [PATCH v4 1/2] mm/memory_hotplug: Add support to accept memory
 during hot-add*

>   #endif
>   

I really hate that accepting (and un-accepting) hotplugged memory is 
different to accepting ordinary boot memory.

Is there really no way we can get a reasonable implementation where we 
just call a generic accept_memory() and it will know what to do?

---

## [7] Pratik R. Sampat — 2026-02-04
*Subject: Re: [PATCH v4 1/2] mm/memory_hotplug: Add support to accept memory
 during hot-add*

On 2/4/26 1:59 PM, David Hildenbrand (arm) wrote:
> On 2/4/26 12:22, Kiryl Shutsemau wrote:
>> On Tue, Feb 03, 2026 at 11:49:45AM -0600, Pratik R. Sampat wrote:

Agreed. Breaking hotplug for VMs under 4G is absolutely not the way to go.

Would it be worse if we call arch_accept_memory() if the table doesn't exist?
The table is primarily to operate on the bitmap's entry. We could wrap these
accept calls within an arch check for TDX and SNP guest if the unaccepted table
is NULL. Or, less preferably convert the panic() of the existing
arch_[accept/unaccept]_memory() to a WARN() instead.

> 
> It's all starting to feel .... very hacky, sorry to say.

The unaccepted bitmap allocation happens a lot earlier than SRAT parsing. So to
get the right range, either we have to duplicate some of that parsing logic
earlier, or, replace the memblock allocated bitmap later. The first one is a
bit more hacky, but the second one would require us to the change the original
unaccepted struct from a flexible array to a pointer which might break kexec.

Neither of the approaches seem less intrusive than the other unfortunately.

--Pratik

---

## [8] Pratik R. Sampat — 2026-02-04
*Subject: Re: [PATCH v4 1/2] mm/memory_hotplug: Add support to accept memory
 during hot-add*

On 2/4/26 2:00 PM, David Hildenbrand (arm) wrote:
>>   #endif
>>     static inline bool pfn_is_unaccepted_memory(unsigned long pfn)

Sure, that shouldn't be impossible.

The only reason I initially kept them separate is because we accept and update
the bitmap unconditionally. This mainly applies to cold-plugged memory since
their bitmap state after remove shouldn't matter. However, as we are now
correctly setting the bits in the hot-remove path we should be fine accepting
from the for_each_set_bitrange_from() logic within accept_memory(), I think.

Something like so?

diff --git a/drivers/firmware/efi/unaccepted_memory.c b/drivers/firmware/efi/unaccepted_memory.c
index d11e7836200a..e56adfd382f8 100644
--- a/drivers/firmware/efi/unaccepted_memory.c
+++ b/drivers/firmware/efi/unaccepted_memory.c
@@ -36,6 +36,7 @@ void accept_memory(phys_addr_t start, unsigned long size)
        unsigned long range_start, range_end;
        struct accept_range range, *entry;
        phys_addr_t end = start + size;
+       phys_addr_t bitmap_end;
        unsigned long flags;
        u64 unit_size;

@@ -44,6 +45,21 @@ void accept_memory(phys_addr_t start, unsigned long size)
                return;

        unit_size = unaccepted->unit_size;
+       bitmap_end = unaccepted->phys_base + unaccepted->size * unit_size * BITS_PER_BYTE;
+
+       /* Memory completely beyond bitmap: hotplug memory, accept unconditionally */
+       if (start >= bitmap_end) {
+               arch_accept_memory(start, end);
+               return;
+       }
+
+       /* Memory partially beyond bitmap */
+       if (end > bitmap_end) {
+               arch_accept_memory(bitmap_end, end);
+               end = bitmap_end;
+       }

        /*
         * Only care for the part of the range that is represented

unaccept_hotplug_memory() truly doesn't do anything special for hotplug so I
could just re-name it unaccept_memory().

Thanks!

---

## [9] Kiryl Shutsemau — 2026-02-05
*Subject: Re: [PATCH v4 1/2] mm/memory_hotplug: Add support to accept memory
 during hot-add*

On Wed, Feb 04, 2026 at 09:50:09PM -0600, Pratik R. Sampat wrote:
> 
> 

You are calling arch_accept_memory() on every memory allocation if the
memory is not represented in the bitmap. Hard NAK.

> 
>         /*

---

## [10] Kiryl Shutsemau — 2026-02-05
*Subject: Re: [PATCH v4 1/2] mm/memory_hotplug: Add support to accept memory
 during hot-add*

On Wed, Feb 04, 2026 at 09:50:01PM -0600, Pratik R. Sampat wrote:
> 
> 

I think you try to workaround a lack of proper design. I think the right
way would be to make unaccepted hotpluggable ranges declared upfront in
the EFI memory map, so kernel can allocate bitmap for all of it on boot
and not playing guessing game.

If it required EFI spec modification, let's do it.

---

## [11] David Hildenbrand (Arm) — 2026-02-05
*Subject: Re: [PATCH v4 1/2] mm/memory_hotplug: Add support to accept memory
 during hot-add*

On 2/5/26 11:48, Kiryl Shutsemau wrote:
> On Wed, Feb 04, 2026 at 09:50:09PM -0600, Pratik R. Sampat wrote:
>>

In which scenarios would we not have memory represented in the bitmap? 
Guests with <4 GiB? (how does kexec work?) Anything else?

---

## [12] Kiryl Shutsemau — 2026-02-05
*Subject: Re: [PATCH v4 1/2] mm/memory_hotplug: Add support to accept memory
 during hot-add*

On Thu, Feb 05, 2026 at 04:48:13PM +0100, David Hildenbrand (Arm) wrote:
> On 2/5/26 11:48, Kiryl Shutsemau wrote:
> > On Wed, Feb 04, 2026 at 09:50:09PM -0600, Pratik R. Sampat wrote:

We create the bitmap that covers all unaccepted memory.

What memory is unaccepted is up to BIOS. Current implementation of edk2
accepts the memory in the first 4G range of physical address space. It
means we won't have bitmap for this range (unaccepted->phys_base >= 4G).

If the whole VM is smaller than 4G we won't have the bitmap at all.

We can allocate bitmap for all possible memory. Maybe upto max_possible_pfn?
But we might not know the value in EFI stub. It costs 4k per 64GiB of
physical address space.

Ideally, we want to know on boot:

 - what memory ranges are unaccepted - we have it;
 - what memory range can be removed or added after boot - we don't have it

Then we can allocate bitmap that covers all this memory.

---

## [13] David Hildenbrand (Arm) — 2026-02-05
*Subject: Re: [PATCH v4 1/2] mm/memory_hotplug: Add support to accept memory
 during hot-add*

On 2/5/26 17:08, Kiryl Shutsemau wrote:
> On Thu, Feb 05, 2026 at 04:48:13PM +0100, David Hildenbrand (Arm) wrote:
>> On 2/5/26 11:48, Kiryl Shutsemau wrote:

Good! :)

> 
> What memory is unaccepted is up to BIOS. Current implementation of edk2

Ah, okay, this comes from the BIOS.

> 
> If the whole VM is smaller than 4G we won't have the bitmap at all.

That's what I would do. 4k per 64GiB sounds reasonable.

> 
> Ideally, we want to know on boot:

The SRAT describes memory ranges where we can see hotplug memory. Is 
that too late? We calculate max_possible_pfn based on that.

(don't ask me about special CXL windows and how they are advertised :) )

---

## [14] Kiryl Shutsemau — 2026-02-06
*Subject: Re: [PATCH v4 1/2] mm/memory_hotplug: Add support to accept memory
 during hot-add*

On Thu, Feb 05, 2026 at 06:29:08PM +0100, David Hildenbrand (Arm) wrote:
> > Ideally, we want to know on boot:
> > 

The cleanest way would be to declare the ranges in EFI memory map, not
SRAT. It should be doable.

---

## [15] Pratik R. Sampat — 2026-02-16
*Subject: Re: [PATCH v4 1/2] mm/memory_hotplug: Add support to accept memory
 during hot-add*

On 2/6/26 6:03 AM, Kiryl Shutsemau wrote:
> On Thu, Feb 05, 2026 at 06:29:08PM +0100, David Hildenbrand (Arm) wrote:
>>> Ideally, we want to know on boot:

Got it. I'm speaking to a few EFI folks on how that would work; if we'd
need a new type to specify this or we could piggyback off an existing
type with either the hotpluggable attribute or create a new one.

Thanks,
Pratik

---
