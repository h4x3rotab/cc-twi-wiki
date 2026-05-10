---
title: 'SEV-SNP Unaccepted Memory Hotplug'
date: 2026-01-28
last_reply: 2026-01-29
message_count: 12
participants: ['Pratik R. Sampat', 'Andrew Morton', 'Dave Hansen', 'Kiryl Shutsemau']
---

## [1] Pratik R. Sampat — 2026-01-28

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

Step3: memory can be hot-removed using the qemu monitor using:
(qemu) device_remove dimm1
(qemu) object_remove mem1

Tip: Enable the kvm_convert_memory event in QEMU to observe memory
conversions between private and shared during hotplug/remove.

The series is based on
        git.kernel.org/pub/scm/virt/kvm/kvm.git next

Comments and feedback appreciated!

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

 arch/x86/coco/sev/core.c                 | 13 +++++
 arch/x86/include/asm/sev.h               |  2 +
 arch/x86/include/asm/unaccepted_memory.h |  9 +++
 drivers/firmware/efi/unaccepted_memory.c | 74 ++++++++++++++++++++++++
 include/linux/mm.h                       | 14 +++++
 mm/memory_hotplug.c                      |  4 ++
 6 files changed, 116 insertions(+)

---

## [2] Pratik R. Sampat — 2026-01-28
*Subject: [PATCH v3 1/2] mm/memory_hotplug: Add support to accept memory during hot-add*

Confidential computing guests require memory to be accepted before use.
The unaccepted memory bitmap maintained by firmware does not track
most hotplugged memory ranges apart from system memory annotated to be
cold plugged at boot.

Explicitly validate and transition the newly added memory to a private
state, making it usable by the guest.

Signed-off-by: Pratik R. Sampat <prsampat@amd.com>
---
 drivers/firmware/efi/unaccepted_memory.c | 18 ++++++++++++++++++
 include/linux/mm.h                       |  5 +++++
 mm/memory_hotplug.c                      |  2 ++
 3 files changed, 25 insertions(+)

diff --git a/drivers/firmware/efi/unaccepted_memory.c b/drivers/firmware/efi/unaccepted_memory.c
index c2c067eff634..5a4c8b0f56c8 100644
--- a/drivers/firmware/efi/unaccepted_memory.c
+++ b/drivers/firmware/efi/unaccepted_memory.c
@@ -209,6 +209,24 @@ bool range_contains_unaccepted_memory(phys_addr_t start, unsigned long size)
 	return ret;
 }
 
+/*
+ * Unaccepted memory bitmap only covers initial boot memory and not the
+ * hotpluggable range that is part of SRAT parsing. However, some initial memory
+ * with the attribute EFI_MEMORY_HOT_PLUGGABLE can indicate boot time memory
+ * that can be hot-removed. Hence, handle acceptance in accordance with the
+ * unaccepted bitmap. Otherwise, perform the state change for the memory range
+ * up-front.
+ */
+void accept_hotplug_memory(phys_addr_t start, unsigned long size)
+{
+	if (range_contains_unaccepted_memory(start, size)) {
+		accept_memory(start, size);
+		return;
+	}
+
+	arch_accept_memory(start, start + size);
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

## [3] Pratik R. Sampat — 2026-01-28
*Subject: [PATCH v3 2/2] x86/sev: Add support to unaccept memory after hot-remove*

Transition memory to the shared state during a hot-remove operation so
that it can be re-used by the hypervisor. This also applies when memory
is intended to be hotplugged back in later, as those pages will need to
be re-accepted after crossing the trust boundary.

Signed-off-by: Pratik R. Sampat <prsampat@amd.com>
---
 arch/x86/coco/sev/core.c                 | 13 ++++++
 arch/x86/include/asm/sev.h               |  2 +
 arch/x86/include/asm/unaccepted_memory.h |  9 ++++
 drivers/firmware/efi/unaccepted_memory.c | 56 ++++++++++++++++++++++++
 include/linux/mm.h                       |  9 ++++
 mm/memory_hotplug.c                      |  2 +
 6 files changed, 91 insertions(+)

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
index f5937e9866ac..8715be843e65 100644
--- a/arch/x86/include/asm/unaccepted_memory.h
+++ b/arch/x86/include/asm/unaccepted_memory.h
@@ -18,6 +18,15 @@ static inline void arch_accept_memory(phys_addr_t start, phys_addr_t end)
 	}
 }
 
+static inline void arch_unaccept_memory(phys_addr_t start, phys_addr_t end)
+{
+	if (cc_platform_has(CC_ATTR_GUEST_SEV_SNP)) {
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
index 5a4c8b0f56c8..9f1d594dba33 100644
--- a/drivers/firmware/efi/unaccepted_memory.c
+++ b/drivers/firmware/efi/unaccepted_memory.c
@@ -157,6 +157,52 @@ void accept_memory(phys_addr_t start, unsigned long size)
 	spin_unlock_irqrestore(&unaccepted_memory_lock, flags);
 }
 
+void unaccept_memory(phys_addr_t start, unsigned long size)
+{
+	unsigned long range_start, range_end, bitrange_end;
+	struct efi_unaccepted_memory *unaccepted;
+	phys_addr_t end = start + size;
+	u64 unit_size, phys_base;
+	unsigned long flags;
+
+	unaccepted = efi_get_unaccepted_table();
+	if (!unaccepted)
+		return;
+
+	phys_base = unaccepted->phys_base;
+	unit_size = unaccepted->unit_size;
+
+	if (start < unaccepted->phys_base)
+		start = unaccepted->phys_base;
+	if (end < unaccepted->phys_base)
+		return;
+
+	start -= phys_base;
+	end -= phys_base;
+
+	/* Make sure not to overrun the bitmap */
+	if (end > unaccepted->size * unit_size * BITS_PER_BYTE)
+		end = unaccepted->size * unit_size * BITS_PER_BYTE;
+
+	range_start = start / unit_size;
+	bitrange_end = DIV_ROUND_UP(end, unit_size);
+
+	/* Only unaccept memory that was previously accepted in the range */
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
 bool range_contains_unaccepted_memory(phys_addr_t start, unsigned long size)
 {
 	struct efi_unaccepted_memory *unaccepted;
@@ -227,6 +273,16 @@ void accept_hotplug_memory(phys_addr_t start, unsigned long size)
 	arch_accept_memory(start, start + size);
 }
 
+void unaccept_hotplug_memory(phys_addr_t start, unsigned long size)
+{
+	if (range_contains_unaccepted_memory(start, size)) {
+		unaccept_memory(start, size);
+		return;
+	}
+
+	arch_unaccept_memory(start, start + size);
+}
+
 #ifdef CONFIG_PROC_VMCORE
 static bool unaccepted_memory_vmcore_pfn_is_ram(struct vmcore_cb *cb,
 						unsigned long pfn)
diff --git a/include/linux/mm.h b/include/linux/mm.h
index 2d3c1ea40606..faefaa9b92c6 100644
--- a/include/linux/mm.h
+++ b/include/linux/mm.h
@@ -4504,7 +4504,9 @@ int set_anon_vma_name(unsigned long addr, unsigned long size,
 
 bool range_contains_unaccepted_memory(phys_addr_t start, unsigned long size);
 void accept_memory(phys_addr_t start, unsigned long size);
+void unaccept_memory(phys_addr_t start, unsigned long size);
 void accept_hotplug_memory(phys_addr_t start, unsigned long size);
+void unaccept_hotplug_memory(phys_addr_t start, unsigned long size);
 
 #else
 
@@ -4518,10 +4520,17 @@ static inline void accept_memory(phys_addr_t start, unsigned long size)
 {
 }
 
+static inline void unaccept_memory(phys_addr_t start, unsigned long size)
+{
+}
+
 static inline void accept_hotplug_memory(phys_addr_t start, unsigned long size)
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

## [4] Andrew Morton — 2026-01-28
*Subject: Re: [PATCH v3 2/2] x86/sev: Add support to unaccept memory after
 hot-remove*

On Wed, 28 Jan 2026 14:41:05 -0600 "Pratik R. Sampat" <prsampat@amd.com> wrote:

> Transition memory to the shared state during a hot-remove operation so
> that it can be re-used by the hypervisor. This also applies when memory

Seems severe.  Dropping a WARN() and continuing would be preferred.

What exactly happened here?  Am I correct in thinking that the check in
snp_unaccept_memory() makes this a cant-happen?

> --- a/drivers/firmware/efi/unaccepted_memory.c
> +++ b/drivers/firmware/efi/unaccepted_memory.c

max()?

> +	if (end < unaccepted->phys_base)
> +		return;

min()?

If you like min() and max().  Sometimes I find them annoying - need to mentally
expand them to figure out what's going on.

> +	range_start = start / unit_size;
> +	bitrange_end = DIV_ROUND_UP(end, unit_size);

---

## [5] Dave Hansen — 2026-01-28
*Subject: Re: [PATCH v3 2/2] x86/sev: Add support to unaccept memory after
 hot-remove*

On 1/28/26 12:41, Pratik R. Sampat wrote:
> +static inline void arch_unaccept_memory(phys_addr_t start, phys_addr_t end)
> +{

This panic() is pretty nasty.

Can't we just disable memory hotplug up front if it's:

	!cc_platform_has(CC_ATTR_GUEST_SEV_SNP)

?

---

## [6] Pratik R. Sampat — 2026-01-28
*Subject: Re: [PATCH v3 2/2] x86/sev: Add support to unaccept memory after
 hot-remove*

Hi Dave, Andrew

On 1/28/26 3:08 PM, Andrew Morton wrote:
> On Wed, 28 Jan 2026 14:41:05 -0600 "Pratik R. Sampat" <prsampat@amd.com> wrote:
> 

You're right, a WARN() is probably more appropriate here.

Based on my rudimentary understanding of TDX from Kiryl, TDX module is
what maintains this metadata for the HPA.

So, maybe the WARN could just be:
"Cannot unaccept memory: VMM responsible for unaccepting memory" for
TDX? Or, we could let it fall-through for TDX (if and when there is
support for that)

>> --- a/drivers/firmware/efi/unaccepted_memory.c
>> +++ b/drivers/firmware/efi/unaccepted_memory.c

Same! :-)
That is why I just aped the implementation from its counterpart
accept_memory() but can definitely do it this way and shave off a couple 
of lines.

Thanks,
--Pratik

> 
>> +	range_start = start / unit_size;

---

## [7] Kiryl Shutsemau — 2026-01-29
*Subject: Re: [PATCH v3 1/2] mm/memory_hotplug: Add support to accept memory
 during hot-add*

On Wed, Jan 28, 2026 at 02:41:04PM -0600, Pratik R. Sampat wrote:
> Confidential computing guests require memory to be accepted before use.
> The unaccepted memory bitmap maintained by firmware does not track

No. This is buggy. The memory has to be accepted regardless of state in
the bitmap. If the memory is ever unplugged the bitmap state is not
relevant.

So, accept it unconditionally and mark the memory accepted in the
bitmap.

> +
> +	arch_accept_memory(start, start + size);

---

## [8] Kiryl Shutsemau — 2026-01-29
*Subject: Re: [PATCH v3 2/2] x86/sev: Add support to unaccept memory after
 hot-remove*

On Wed, Jan 28, 2026 at 01:15:06PM -0800, Dave Hansen wrote:
> On 1/28/26 12:41, Pratik R. Sampat wrote:
> > +static inline void arch_unaccept_memory(phys_addr_t start, phys_addr_t end)

I don't understand SEV-SNP situation, but I don't think we need to do
anything on unplug for TDX. We should expect the unplugged memory to be
removed from SEPT. If VMM doesn't do this, it is effectively DoS and we
don't protect against DoS in CoCo.

Converting the memory to shared will do no good for us.

---

## [9] Pratik R. Sampat — 2026-01-29
*Subject: Re: [PATCH v3 1/2] mm/memory_hotplug: Add support to accept memory
 during hot-add*

Hi Kiryl,

On 1/29/26 4:35 AM, Kiryl Shutsemau wrote:
> On Wed, Jan 28, 2026 at 02:41:04PM -0600, Pratik R. Sampat wrote:
>> Confidential computing guests require memory to be accepted before use.

I see. This makes sense for acceptance since device_del would always fully
unplug it.

I still might need to keep a version of bitmap handling in unaccept considering
the case where partially accepted (lazy) memory is removed.
For SNP, pvalidate is not an idempotent operation and we must only rescind
the state for the bits that were previously accepted.

Also, now that I stare at the unaccept_hotplug_memory implementation, I realize
calling range_contains_unaccepted_memory() is plain wrong. I should rather be
looking at the ranges and handling the bitmap + unacceptance.
I'll be sure to clean that up in the next iteration as well.

Thanks,
--Pratik

> 
>> +

---

## [10] Pratik R. Sampat — 2026-01-29
*Subject: Re: [PATCH v3 2/2] x86/sev: Add support to unaccept memory after
 hot-remove*

On 1/29/26 4:40 AM, Kiryl Shutsemau wrote:
> On Wed, Jan 28, 2026 at 01:15:06PM -0800, Dave Hansen wrote:
>> On 1/28/26 12:41, Pratik R. Sampat wrote:

In that case a fall through for TDX (with a comment explaining why) and
panic for rest may be the way to go?

>

---

## [11] Dave Hansen — 2026-01-29
*Subject: Re: [PATCH v3 2/2] x86/sev: Add support to unaccept memory after
 hot-remove*

On 1/29/26 09:32, Pratik R. Sampat wrote:
> In that case a fall through for TDX (with a comment explaining why) and
> panic for rest may be the way to go?

No. panic() is an absolute last resort. It's almost never the way to go.

What else can we do to ensure we never reach this code if the platform
doesn't support memory un-acceptance?

---

## [12] Pratik R. Sampat — 2026-01-29
*Subject: Re: [PATCH v3 2/2] x86/sev: Add support to unaccept memory after
 hot-remove*

On 1/29/26 11:39 AM, Dave Hansen wrote:
> On 1/29/26 09:32, Pratik R. Sampat wrote:
>> In that case a fall through for TDX (with a comment explaining why) and

The panic() here similar to its existing arch_accept_memory() counterpart is
mostly to guard against a cant-happen scenario (unless Kiryl had a different
intention writing the initial hook). It is called from functions that compile
this in only if CONFIG_UNACCEPTED_MEMORY is enabled. TDX and SNP are the only
two users of it today.

---
