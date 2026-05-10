---
title: 'SEV-SNP Unaccepted Memory Hotplug'
date: 2026-01-12
last_reply: 2026-01-14
message_count: 17
participants: ['Pratik R. Sampat', 'Andrew Morton', 'kernel test robot', 'Kiryl Shutsemau', 'David Hildenbrand (Red Hat)']
---

## [1] Pratik R. Sampat — 2026-01-12

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
  mm/memory_hotplug: Add support to unaccept memory after hot-remove

 arch/x86/coco/sev/core.c                 | 13 +++++++++++++
 arch/x86/include/asm/sev.h               |  2 ++
 arch/x86/include/asm/unaccepted_memory.h |  9 +++++++++
 mm/memory_hotplug.c                      |  7 +++++++
 4 files changed, 31 insertions(+)

---

## [2] Pratik R. Sampat — 2026-01-12
*Subject: [PATCH v2 1/2] mm/memory_hotplug: Add support to accept memory during hot-add*

Confidential computing guests require memory to be accepted before use.
The unaccepted memory bitmap maintained by firmware does not track
hotplugged memory ranges.

Call arch_accept_memory() during the hot-add path to explicitly validate
and transition the newly added memory to a private state, making it
usable by the guest.

Signed-off-by: Pratik R. Sampat <prsampat@amd.com>
---
 mm/memory_hotplug.c | 4 ++++
 1 file changed, 4 insertions(+)

diff --git a/mm/memory_hotplug.c b/mm/memory_hotplug.c
index a63ec679d861..8cfbf0541430 100644
--- a/mm/memory_hotplug.c
+++ b/mm/memory_hotplug.c
@@ -38,6 +38,7 @@
 #include <linux/node.h>
 
 #include <asm/tlbflush.h>
+#include <asm/unaccepted_memory.h>
 
 #include "internal.h"
 #include "shuffle.h"
@@ -1567,6 +1568,9 @@ int add_memory_resource(int nid, struct resource *res, mhp_t mhp_flags)
 	if (!strcmp(res->name, "System RAM"))
 		firmware_map_add_hotplug(start, start + size, "System RAM");
 
+	if (IS_ENABLED(CONFIG_UNACCEPTED_MEMORY))
+		arch_accept_memory(start, start + size);
+
 	/* device_online() will take the lock when calling online_pages() */
 	mem_hotplug_done();

---

## [3] Pratik R. Sampat — 2026-01-12
*Subject: [PATCH v2 2/2] mm/memory_hotplug: Add support to unaccept memory after hot-remove*

Transition memory to the shared state during a hot-remove operation so
that it can be re-used by the hypervisor. This also applies when memory
is intended to be hotplugged back in later, as those pages will need to
be re-accepted after crossing the trust boundary.

Signed-off-by: Pratik R. Sampat <prsampat@amd.com>
---
 arch/x86/coco/sev/core.c                 | 13 +++++++++++++
 arch/x86/include/asm/sev.h               |  2 ++
 arch/x86/include/asm/unaccepted_memory.h |  9 +++++++++
 mm/memory_hotplug.c                      |  3 +++
 4 files changed, 27 insertions(+)

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
diff --git a/mm/memory_hotplug.c b/mm/memory_hotplug.c
index 8cfbf0541430..718f729cf687 100644
--- a/mm/memory_hotplug.c
+++ b/mm/memory_hotplug.c
@@ -2242,6 +2242,9 @@ static int try_remove_memory(u64 start, u64 size)
 
 	mem_hotplug_begin();
 
+	if (IS_ENABLED(CONFIG_UNACCEPTED_MEMORY))
+		arch_unaccept_memory(start, start + size);
+
 	rc = memory_blocks_have_altmaps(start, size);
 	if (rc < 0) {
 		mem_hotplug_done();

---

## [4] Andrew Morton — 2026-01-12
*Subject: Re: [PATCH v2 1/2] mm/memory_hotplug: Add support to accept memory
 during hot-add*

On Mon, 12 Jan 2026 14:22:59 -0600 "Pratik R. Sampat" <prsampat@amd.com> wrote:

> Confidential computing guests require memory to be accepted before use.
> The unaccepted memory bitmap maintained by firmware does not track

This only exists for x86!

Otherwise, the mm/ changes are minimal so I volunteer this patchset
for the x86 tree ;)

---

## [5] Pratik R. Sampat — 2026-01-12
*Subject: Re: [PATCH v2 1/2] mm/memory_hotplug: Add support to accept memory
 during hot-add*

On 1/12/26 3:04 PM, Andrew Morton wrote:
> On Mon, 12 Jan 2026 14:22:59 -0600 "Pratik R. Sampat" <prsampat@amd.com> wrote:
> 

Ah, I missed that entirely. Thanks for catching that.

Probably not the best option to have a generic unaccepted_memory.h as well.
Maybe, I should have arch_[un]accept_memory() definitions within mm.h wrapped
within CONFIG_UNACCEPTED_MEMORY instead so that its cleaner.

> 
> Otherwise, the mm/ changes are minimal so I volunteer this patchset

Ack!

--Pratik

---

## [6] Andrew Morton — 2026-01-12
*Subject: Re: [PATCH v2 1/2] mm/memory_hotplug: Add support to accept memory
 during hot-add*

On Mon, 12 Jan 2026 16:23:37 -0600 "Pratik R. Sampat" <prsampat@amd.com> wrote:

> 
> 

Something like that.

The idiomatic Linus way is to use

#ifndef arch_accept_memory
#define arch_accept_memory ...
#endif

Lots of prior art here:

	grep -r include/linux "ifndef arch_"


Oh, arch_get_idle_state_flags() got it all wrong.

	#ifdef CONFIG_ACPI_PROCESSOR_IDLE
	#ifndef arch_get_idle_state_flags
	static inline unsigned int arch_get_idle_state_flags(u32 arch_flags)
	{
		return 0;
	}
	#endif
	#endif /* CONFIG_ACPI_PROCESSOR_IDLE */

- shouldn't have needed "ifdef CONFIG_ACPI_PROCESSOR_IDLE"

- should have appended

	#define arch_get_idle_state_flags arch_get_idle_state_flags

  in case cpp hit the same lines a second time.

---

## [7] kernel test robot — 2026-01-13
*Subject: Re: [PATCH v2 1/2] mm/memory_hotplug: Add support to accept memory
 during hot-add*

Hi Pratik,

kernel test robot noticed the following build errors:

[auto build test ERROR on akpm-mm/mm-everything]
[also build test ERROR on tip/x86/core linus/master v6.19-rc5 next-20260109]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Pratik-R-Sampat/mm-memory_hotplug-Add-support-to-accept-memory-during-hot-add/20260113-042631
base:   https://git.kernel.org/pub/scm/linux/kernel/git/akpm/mm.git mm-everything
patch link:    https://lore.kernel.org/r/20260112202300.43546-2-prsampat%40amd.com
patch subject: [PATCH v2 1/2] mm/memory_hotplug: Add support to accept memory during hot-add
config: s390-randconfig-001-20260113 (https://download.01.org/0day-ci/archive/20260113/202601131156.Kfi0QLIm-lkp@intel.com/config)
compiler: s390-linux-gcc (GCC) 8.5.0
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20260113/202601131156.Kfi0QLIm-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202601131156.Kfi0QLIm-lkp@intel.com/

All errors (new ones prefixed by >>):

>> mm/memory_hotplug.c:41:10: fatal error: asm/unaccepted_memory.h: No such file or directory
    #include <asm/unaccepted_memory.h>
             ^~~~~~~~~~~~~~~~~~~~~~~~~
   compilation terminated.


vim +41 mm/memory_hotplug.c

    39	
    40	#include <asm/tlbflush.h>
  > 41	#include <asm/unaccepted_memory.h>
    42

---

## [8] Pratik R. Sampat — 2026-01-12
*Subject: Re: [PATCH v2 1/2] mm/memory_hotplug: Add support to accept memory
 during hot-add*

On 1/12/26 4:43 PM, Andrew Morton wrote:
> On Mon, 12 Jan 2026 16:23:37 -0600 "Pratik R. Sampat" <prsampat@amd.com> wrote:
> 

Got it. Thanks for clearing that up. I'll make sure to do it this way
in the next iteration.

--Pratik

---

## [9] kernel test robot — 2026-01-13
*Subject: Re: [PATCH v2 1/2] mm/memory_hotplug: Add support to accept memory
 during hot-add*

Hi Pratik,

kernel test robot noticed the following build errors:

[auto build test ERROR on akpm-mm/mm-everything]
[also build test ERROR on tip/x86/core linus/master v6.19-rc5 next-20260109]
[If your patch is applied to the wrong git tree, kindly drop us a note.
And when submitting patch, we suggest to use '--base' as documented in
https://git-scm.com/docs/git-format-patch#_base_tree_information]

url:    https://github.com/intel-lab-lkp/linux/commits/Pratik-R-Sampat/mm-memory_hotplug-Add-support-to-accept-memory-during-hot-add/20260113-042631
base:   https://git.kernel.org/pub/scm/linux/kernel/git/akpm/mm.git mm-everything
patch link:    https://lore.kernel.org/r/20260112202300.43546-2-prsampat%40amd.com
patch subject: [PATCH v2 1/2] mm/memory_hotplug: Add support to accept memory during hot-add
config: s390-defconfig (https://download.01.org/0day-ci/archive/20260113/202601131632.NrQzg2Wm-lkp@intel.com/config)
compiler: clang version 22.0.0git (https://github.com/llvm/llvm-project 9b8addffa70cee5b2acc5454712d9cf78ce45710)
reproduce (this is a W=1 build): (https://download.01.org/0day-ci/archive/20260113/202601131632.NrQzg2Wm-lkp@intel.com/reproduce)

If you fix the issue in a separate patch/commit (i.e. not just a new version of
the same patch/commit), kindly add following tags
| Reported-by: kernel test robot <lkp@intel.com>
| Closes: https://lore.kernel.org/oe-kbuild-all/202601131632.NrQzg2Wm-lkp@intel.com/

All errors (new ones prefixed by >>):

>> mm/memory_hotplug.c:41:10: fatal error: 'asm/unaccepted_memory.h' file not found
      41 | #include <asm/unaccepted_memory.h>
         |          ^~~~~~~~~~~~~~~~~~~~~~~~~
   1 error generated.


vim +41 mm/memory_hotplug.c

    39	
    40	#include <asm/tlbflush.h>
  > 41	#include <asm/unaccepted_memory.h>
    42

---

## [10] Kiryl Shutsemau — 2026-01-13
*Subject: Re: [PATCH v2 2/2] mm/memory_hotplug: Add support to unaccept memory
 after hot-remove*

On Mon, Jan 12, 2026 at 02:23:00PM -0600, Pratik R. Sampat wrote:
> Transition memory to the shared state during a hot-remove operation so
> that it can be re-used by the hypervisor. This also applies when memory

Hm. What happens when we hot-remove memory that was there at the boot
and there's bitmap space for it?

Also, I'm not sure why it is needed. At least in TDX case, VMM can pull
the memory from under guest at any time without a warning. Coverting
memory to shared shouldn't make a difference as along as re-adding the
same GPA range triggers accept.

---

## [11] Pratik R. Sampat — 2026-01-13
*Subject: Re: [PATCH v2 2/2] mm/memory_hotplug: Add support to unaccept memory
 after hot-remove*

On 1/13/2026 4:28 AM, Kiryl Shutsemau wrote:
> On Mon, Jan 12, 2026 at 02:23:00PM -0600, Pratik R. Sampat wrote:
>> Transition memory to the shared state during a hot-remove operation so

While hotplug ranges gotten from SRAT don't seem to overlap with the
conventional ranges in the unaccepted table, EFI_MEMORY_HOT_PLUGGABLE
attribute could indicate boot time memory that could be hot-removed. I
could potentially unset the bitmap first, if the bit exists and then
unaccept.

Similarly, I could also check if the bitmap is large enough to set the
bit before I call arch_accept_memory() (This may not really be needed 
though).

> Also, I'm not sure why it is needed. At least in TDX case, VMM can pull
> the memory from under guest at any time without a warning. Coverting

That makes sense. The only scenario where we could run into trouble on
SNP platforms is when we redo a qemu device_add after a device_del
without first removing the memory object entirely since same-state
transitions result in guest termination.

This means we must always follow a device_del with an object_del on
removal. Otherwise, the onus would then be on the VMM to transition
the memory back to shared before re-adding it to the guest.

However, if this flow is not a concern to begin with then I could
probably just drop this patch?

--Pratik

---

## [12] Kiryl Shutsemau — 2026-01-13
*Subject: Re: [PATCH v2 2/2] mm/memory_hotplug: Add support to unaccept memory
 after hot-remove*

On Tue, Jan 13, 2026 at 11:10:21AM -0600, Pratik R. Sampat wrote:
> 
> 

This seems to be one-of-many possible ways of VMM to get guest terminated.
DoS is not in something confidential computing aims to prevent.

> However, if this flow is not a concern to begin with then I could
> probably just drop this patch?

Yes, please.

---

## [13] Pratik R. Sampat — 2026-01-13
*Subject: Re: [PATCH v2 2/2] mm/memory_hotplug: Add support to unaccept memory
 after hot-remove*

On 1/13/26 11:53 AM, Kiryl Shutsemau wrote:
> On Tue, Jan 13, 2026 at 11:10:21AM -0600, Pratik R. Sampat wrote:
>>

Putting more thought into it, memory unacceptance on remove may be required
after all at least for SNP platforms.

Consider a scenario:
* Guest accepts a GPA say G1, mapped to a host physical address H1.
* We attempt to hot-remove the memory. If the guest does not unaccept the memory
  now then G1 to H1 mapping within the RMP will still exist.
* Then if the hypervisor later hot-adds the memory to G1, it will be now mapped
  to H3 and this new mapping will be accepted.

This will essentially mean that we have 2 RMP entries: One for H1 and another
for H3 mapped for G1 which are both validated / accepted which can then be
swapped at will and compromise integrity.

--Pratik
>

---

## [14] David Hildenbrand (Red Hat) — 2026-01-14
*Subject: Re: [PATCH v2 1/2] mm/memory_hotplug: Add support to accept memory
 during hot-add*

On 1/12/26 21:22, Pratik R. Sampat wrote:
> Confidential computing guests require memory to be accepted before use.
> The unaccepted memory bitmap maintained by firmware does not track

As discussed, for things like virtio-mem or the HV-balloon this might be 
the wrong thing to do, but I don't expect these mechanisms to be used in 
CoCo environments just yet (and doing so would require enabling work for 
them).

So I'm fine with this for now.

---

## [15] Kiryl Shutsemau — 2026-01-14
*Subject: Re: [PATCH v2 2/2] mm/memory_hotplug: Add support to unaccept memory
 after hot-remove*

On Tue, Jan 13, 2026 at 12:22:33PM -0600, Pratik R. Sampat wrote:
> 
> 

I don't know much about SEV, but I assume RMP is similar to PAMT in TDX
where TDX module maintains metadata for host physical memory.

What side problems do you for guest here?

I probably miss something, but it seems to be VMM problem, no? I mean if
VMM doesn't update RMP on replacing one HPA to another for the GPA, it
is bug in VMM housekeeping. Guest is not responsible for this.

---

## [16] Pratik R. Sampat — 2026-01-14
*Subject: Re: [PATCH v2 1/2] mm/memory_hotplug: Add support to accept memory
 during hot-add*

On 1/14/26 4:30 AM, David Hildenbrand (Red Hat) wrote:
> On 1/12/26 21:22, Pratik R. Sampat wrote:
>> Confidential computing guests require memory to be accepted before use.

Ack.

> So I'm fine with this for now.
> 

Thanks!

---

## [17] Pratik R. Sampat — 2026-01-14
*Subject: Re: [PATCH v2 2/2] mm/memory_hotplug: Add support to unaccept memory
 after hot-remove*

On 1/14/26 4:47 AM, Kiryl Shutsemau wrote:
> On Tue, Jan 13, 2026 at 12:22:33PM -0600, Pratik R. Sampat wrote:
>>

Right, the problem is that we do not inherently trust the host to make change.
That is why in my understanding, the guest is responsible for validating and
rescinding those pages.

--Pratik

---
