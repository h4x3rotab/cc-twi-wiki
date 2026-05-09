---
title: 'Restrict devmem for confidential VMs'
date: 2025-04-29
last_reply: 2025-05-01
message_count: 11
participants: ['Dan Williams', 'Greg Kroah-Hartman', 'Arnd Bergmann', 'Dave Hansen']
---

## [1] Dan Williams — 2025-04-29

Changes since v3 [1] (note v4 was a partial re-roll, but more feedback
came in requiring a v5):
- Fix a kbuild robot report for a missing header include of cc_platform.h
- Switch to selecting STRICT_DEVMEM and IOSTRICT_DEVMEM rather than
  "depends on". (Naveen)
- Clarify the "SEPT violation" vs "crash" and other changelog fixups for
  devmem maintainers and other arch maintainers. (Dave)
- Drop patch numbering since patch2 is a fix and has no dependencies on
  patch1

[1]: http://lore.kernel.org/174491711228.1395340.3647010925173796093.stgit@dwillia2-xfh.jf.intel.com

---
The original response to Nikolay's report of a "crash" (unhandled SEPT
violation) triggered by /dev/mem access to private memory was "let's
just turn off /dev/mem".

After some machinations of x86_platform_ops to block a subset of
problematic access, spelunking the history of devmem_is_allowed()
returning "2" to enable some compatibility benefits while blocking
access, and discovering that userspace depends buggy kernel behavior for
mmap(2) of the first 1MB of memory on x86, the proposal has circled back
to "disable /dev/mem".

Require both STRICT_DEVMEM and IO_STRICT_DEVMEM for x86 confidential
guests to close /dev/mem hole while still allowing for userspace
mapping of PCI MMIO as long as the kernel and userspace are not mapping
the range at the same time.

The range_is_allowed() cleanup is not strictly necessary, but might as
well close a 17 year-old "TODO".

Dan Williams (2):
  x86/devmem: Remove duplicate range_is_allowed() definition
  x86/devmem: Drop /dev/mem access for confidential guests

 arch/x86/Kconfig          |  4 ++++
 arch/x86/mm/pat/memtype.c | 31 ++++---------------------------
 drivers/char/mem.c        | 28 ++++++++++------------------
 include/linux/io.h        | 21 +++++++++++++++++++++
 4 files changed, 39 insertions(+), 45 deletions(-)


base-commit: 0af2f6be1b4281385b618cb86ad946eded089ac8

---

## [2] Dan Williams — 2025-04-29
*Subject: [PATCH v5] x86/devmem: Remove duplicate range_is_allowed() definition*

17 years ago, Venki suggested [1] "A future improvement would be to
avoid the range_is_allowed duplication".

The only thing preventing a common implementation is that
phys_mem_access_prot_allowed() expects the range check to exit
immediately when PAT is disabled [2]. I.e. there is no cache conflict to
manage in that case. This cleanup was noticed on the path to
considering changing range_is_allowed() policy to blanket deny /dev/mem
for private (confidential computing) memory.

Note, however that phys_mem_access_prot_allowed() has long since stopped
being relevant for managing cache-type validation due to [3], and [4].

Commit 0124cecfc85a ("x86, PAT: disable /dev/mem mmap RAM with PAT") [1]
Commit 9e41bff2708e ("x86: fix /dev/mem mmap breakage when PAT is disabled") [2]
Commit 1886297ce0c8 ("x86/mm/pat: Fix BUG_ON() in mmap_mem() on QEMU/i386") [3]
Commit 0c3c8a18361a ("x86, PAT: Remove duplicate memtype reserve in devmem mmap") [4]

Cc: Dave Hansen <dave.hansen@linux.intel.com>
Cc: Ingo Molnar <mingo@kernel.org>
Cc: "Naveen N Rao" <naveen@kernel.org>
Reviewed-by: Nikolay Borisov <nik.borisov@suse.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/mm/pat/memtype.c | 31 ++++---------------------------
 drivers/char/mem.c        | 18 ------------------
 include/linux/io.h        | 21 +++++++++++++++++++++
 3 files changed, 25 insertions(+), 45 deletions(-)

diff --git a/arch/x86/mm/pat/memtype.c b/arch/x86/mm/pat/memtype.c
index 72d8cbc61158..c97b6598f187 100644
--- a/arch/x86/mm/pat/memtype.c
+++ b/arch/x86/mm/pat/memtype.c
@@ -38,6 +38,7 @@
 #include <linux/kernel.h>
 #include <linux/pfn_t.h>
 #include <linux/slab.h>
+#include <linux/io.h>
 #include <linux/mm.h>
 #include <linux/highmem.h>
 #include <linux/fs.h>
@@ -773,38 +774,14 @@ pgprot_t phys_mem_access_prot(struct file *file, unsigned long pfn,
 	return vma_prot;
 }
 
-#ifdef CONFIG_STRICT_DEVMEM
-/* This check is done in drivers/char/mem.c in case of STRICT_DEVMEM */
-static inline int range_is_allowed(unsigned long pfn, unsigned long size)
-{
-	return 1;
-}
-#else
-/* This check is needed to avoid cache aliasing when PAT is enabled */
-static inline int range_is_allowed(unsigned long pfn, unsigned long size)
-{
-	u64 from = ((u64)pfn) << PAGE_SHIFT;
-	u64 to = from + size;
-	u64 cursor = from;
-
-	if (!pat_enabled())
-		return 1;
-
-	while (cursor < to) {
-		if (!devmem_is_allowed(pfn))
-			return 0;
-		cursor += PAGE_SIZE;
-		pfn++;
-	}
-	return 1;
-}
-#endif /* CONFIG_STRICT_DEVMEM */
-
 int phys_mem_access_prot_allowed(struct file *file, unsigned long pfn,
 				unsigned long size, pgprot_t *vma_prot)
 {
 	enum page_cache_mode pcm = _PAGE_CACHE_MODE_WB;
 
+	if (!pat_enabled())
+		return 1;
+
 	if (!range_is_allowed(pfn, size))
 		return 0;
 
diff --git a/drivers/char/mem.c b/drivers/char/mem.c
index 169eed162a7f..48839958b0b1 100644
--- a/drivers/char/mem.c
+++ b/drivers/char/mem.c
@@ -61,29 +61,11 @@ static inline int page_is_allowed(unsigned long pfn)
 {
 	return devmem_is_allowed(pfn);
 }
-static inline int range_is_allowed(unsigned long pfn, unsigned long size)
-{
-	u64 from = ((u64)pfn) << PAGE_SHIFT;
-	u64 to = from + size;
-	u64 cursor = from;
-
-	while (cursor < to) {
-		if (!devmem_is_allowed(pfn))
-			return 0;
-		cursor += PAGE_SIZE;
-		pfn++;
-	}
-	return 1;
-}
 #else
 static inline int page_is_allowed(unsigned long pfn)
 {
 	return 1;
 }
-static inline int range_is_allowed(unsigned long pfn, unsigned long size)
-{
-	return 1;
-}
 #endif
 
 static inline bool should_stop_iteration(void)
diff --git a/include/linux/io.h b/include/linux/io.h
index 6a6bc4d46d0a..0642c7ee41db 100644
--- a/include/linux/io.h
+++ b/include/linux/io.h
@@ -183,4 +183,25 @@ static inline void arch_io_free_memtype_wc(resource_size_t base,
 int devm_arch_io_reserve_memtype_wc(struct device *dev, resource_size_t start,
 				    resource_size_t size);
 
+#ifdef CONFIG_STRICT_DEVMEM
+static inline int range_is_allowed(unsigned long pfn, unsigned long size)
+{
+	u64 from = ((u64)pfn) << PAGE_SHIFT;
+	u64 to = from + size;
+	u64 cursor = from;
+
+	while (cursor < to) {
+		if (!devmem_is_allowed(pfn))
+			return 0;
+		cursor += PAGE_SIZE;
+		pfn++;
+	}
+	return 1;
+}
+#else
+static inline int range_is_allowed(unsigned long pfn, unsigned long size)
+{
+	return 1;
+}
+#endif
 #endif /* _LINUX_IO_H */

---

## [3] Dan Williams — 2025-04-29
*Subject: [PATCH v5] x86/devmem: Drop /dev/mem access for confidential guests*

Nikolay reports that accessing BIOS data (first 1MB of the physical
address space) via /dev/mem results in a "crash" / terminated VM
(unhandled SEPT violation). See report [1] for details.

The cause is ioremap() (via xlate_dev_mem_ptr()) establishes an
unencrypted mapping where the kernel had established an encrypted
mapping previously. The CPU enforces mapping consistency with a fault
upon detecting a mismatch. A similar situation arises with devmem access
to "unaccepted" confidential memory. In summary, it is fraught to allow
uncoordinated userspace mapping of confidential memory.

While there is an existing mitigation to simulate and redirect access to
the BIOS data area with STRICT_DEVMEM=y, it is insufficient.
Specifically, STRICT_DEVMEM=y traps read(2) access to the BIOS data
area, and returns a zeroed buffer.  However, it turns out the kernel
fails to enforce the same via mmap(2), and a direct mapping is
established. This is a hole, and unfortunately userspace has learned to
exploit it [2].

This means the kernel either needs: a mechanism to ensure consistent
plus accepted "encrypted" mappings of this /dev/mem mmap() hole, close
the hole by mapping the zero page in the mmap(2) path, block only BIOS
data access and let typical STRICT_DEVMEM protect the rest, or disable
/dev/mem altogether.

The simplest option for now is arrange for /dev/mem to always behave as
if lockdown is enabled for confidential guests. Require confidential
guest userspace to jettison legacy dependencies on /dev/mem similar to
how other legacy mechanisms are jettisoned for confidential operation.
Recall that modern methods for BIOS data access are available like
/sys/firmware/dmi/tables.

Now, this begs the question what to do with PCI sysfs which allows
userspace mappings of confidential MMIO with similar mapping consistency
and acceptance expectations? Here, the existing mitigation of
IO_STRICT_DEVMEM is likely sufficient. The kernel is expected to use
request_mem_region() when toggling the state of MMIO. With
IO_STRICT_DEVMEM that enforces kernel-exclusive access until
release_mem_region(), i.e. mapping conflicts are prevented.

Cc: <x86@kernel.org>
Cc: Kees Cook <kees@kernel.org>
Cc: Ingo Molnar <mingo@kernel.org>
Cc: Vishal Annapurve <vannapurve@google.com>
Cc: Kirill Shutemov <kirill.shutemov@linux.intel.com>
Cc: Arnd Bergmann <arnd@arndb.de>
Cc: Greg Kroah-Hartman <gregkh@linuxfoundation.org>
Cc: Michael Ellerman <mpe@ellerman.id.au>
Cc: Suzuki K Poulose <suzuki.poulose@arm.com>
Link: https://sources.debian.org/src/libdebian-installer/0.125/src/system/subarch-x86-linux.c/?hl=113#L93 [2]
Reported-by: Nikolay Borisov <nik.borisov@suse.com>
Closes: http://lore.kernel.org/20250318113604.297726-1-nik.borisov@suse.com [1]
Fixes: 9aa6ea69852c ("x86/tdx: Make pages shared in ioremap()")
Cc: <stable@vger.kernel.org>
Acked-by: Dave Hansen <dave.hansen@linux.intel.com>
Reviewed-by: Nikolay Borisov <nik.borisov@suse.com>
Acked-by: Naveen N Rao (AMD) <naveen@kernel.org>
Tested-by: Naveen N Rao (AMD) <naveen@kernel.org>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 arch/x86/Kconfig   |  4 ++++
 drivers/char/mem.c | 10 ++++++++++
 2 files changed, 14 insertions(+)

diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
index 4b9f378e05f6..36f11aad1ae5 100644
--- a/arch/x86/Kconfig
+++ b/arch/x86/Kconfig
@@ -891,6 +891,8 @@ config INTEL_TDX_GUEST
 	depends on X86_X2APIC
 	depends on EFI_STUB
 	depends on PARAVIRT
+	select STRICT_DEVMEM
+	select IO_STRICT_DEVMEM
 	select ARCH_HAS_CC_PLATFORM
 	select X86_MEM_ENCRYPT
 	select X86_MCE
@@ -1510,6 +1512,8 @@ config AMD_MEM_ENCRYPT
 	bool "AMD Secure Memory Encryption (SME) support"
 	depends on X86_64 && CPU_SUP_AMD
 	depends on EFI_STUB
+	select STRICT_DEVMEM
+	select IO_STRICT_DEVMEM
 	select DMA_COHERENT_POOL
 	select ARCH_USE_MEMREMAP_PROT
 	select INSTRUCTION_DECODER
diff --git a/drivers/char/mem.c b/drivers/char/mem.c
index 48839958b0b1..47729606b817 100644
--- a/drivers/char/mem.c
+++ b/drivers/char/mem.c
@@ -30,6 +30,7 @@
 #include <linux/uio.h>
 #include <linux/uaccess.h>
 #include <linux/security.h>
+#include <linux/cc_platform.h>
 
 #define DEVMEM_MINOR	1
 #define DEVPORT_MINOR	4
@@ -595,6 +596,15 @@ static int open_port(struct inode *inode, struct file *filp)
 	if (rc)
 		return rc;
 
+	/*
+	 * Enforce encrypted mapping consistency and avoid unaccepted
+	 * memory conflicts, "lockdown" /dev/mem for confidential
+	 * guests.
+	 */
+	if (IS_ENABLED(CONFIG_STRICT_DEVMEM) &&
+	    cc_platform_has(CC_ATTR_GUEST_MEM_ENCRYPT))
+		return -EPERM;
+
 	if (iminor(inode) != DEVMEM_MINOR)
 		return 0;

---

## [4] Greg Kroah-Hartman — 2025-04-30
*Subject: Re: [PATCH v5] x86/devmem: Drop /dev/mem access for confidential
 guests*

On Tue, Apr 29, 2025 at 07:46:22PM -0700, Dan Williams wrote:
> Nikolay reports that accessing BIOS data (first 1MB of the physical
> address space) via /dev/mem results in a "crash" / terminated VM

I hate to ask, but why not force the whole "confidential computing"
stuff to enable IO_STRICT_DEVMEM as well?  I don't see why you would
want a cc guest raw access to devmem, do you?

You kind of mention it above in the last paragraph, but forcing that on
for these guests feels like the best, and simplest, solution overall as
the number of different "is this secure, no really is this secure, no
what about this option" chain of tests that we have in this driver is
getting kind of silly.

OR, why not just force all cc guests to enable a security module that
implements this for them?  :)

thanks,

greg k-h

---

## [5] Greg Kroah-Hartman — 2025-04-30
*Subject: Re: [PATCH v5] x86/devmem: Remove duplicate range_is_allowed()
 definition*

On Tue, Apr 29, 2025 at 07:46:21PM -0700, Dan Williams wrote:
> 17 years ago, Venki suggested [1] "A future improvement would be to
> avoid the range_is_allowed duplication".


Reviewed-by: Greg Kroah-Hartman <gregkh@linuxfoundation.org>

---

## [6] Arnd Bergmann — 2025-04-30
*Subject: Re: [PATCH v5] x86/devmem: Drop /dev/mem access for confidential guests*

On Wed, Apr 30, 2025, at 04:46, Dan Williams wrote:
> While there is an existing mitigation to simulate and redirect access to
> the BIOS data area with STRICT_DEVMEM=y, it is insufficient.

As far as I can tell, this was a deliberate design choice in
commit a4866aa81251 ("mm: Tighten x86 /dev/mem with zeroing reads"),
which did not try to forbid it completely but mainly avoids triggering
the hardened usercopy check.

> The simplest option for now is arrange for /dev/mem to always behave as
> if lockdown is enabled for confidential guests. Require confidential

Restricting /dev/mem further is a good idea, but it would be nice
if that could be done without adding yet another special case.

An even more radical approach would be to just disallow CONFIG_DEVMEM
for any configuration that includes ARCH_HAS_CC_PLATFORM, but that
may go a little too far.

The existing rules that I can see are:

- readl/write is only allowed on actual (lowmem) RAM, not
  on MMIO registers, enforced by valid_phys_addr_range()
- with STRICT_DEVMEM, read/write is disallowed on both
  RAM and MMIO
- an an exception, x86 additionally allows read/write on the
  low 1MB MMIO region and 32-bit PCI MMIO BAR space, with
  a custom xlate_dev_mem_ptr() that calls either memremap()
  or ioremap() on the physical address.
- as another exception from that, the low 1MB on x86 behaves
  like /dev/zero for memory pages when STRICT_DEVMEM
  is set, and ignores conflicting drivers for MMIO registers
- The PowerPC sys_rtas syscall has another exception in
  order to ignore the STRICT_DEVMEM and write to a portion
  of kernel memory to talk to firmware
- on the mmap() side, x86 has another special to allow
  mapping RAM in the first 1MB despite STRICT_DEVMEM

How about changing x86 to work more like the others and
removing the special cases for the first 1MB and for the
32-bit PCI BAR space? If Xorg, and dmidecode are able to
do this differently, maybe the hacks can just go away, or
be guarded by a Kconfig option that is mutually exclusive
with ARCH_HAS_CC_PLATFORM?

> @@ -595,6 +596,15 @@ static int open_port(struct inode *inode, struct 
> file *filp)

The description only talks about /dev/mem, but it looks like this
blocks /dev/port as well. Blocking /dev/port may also be a good
idea, but I don't see why that would be conditional on
CC_ATTR_GUEST_MEM_ENCRYPT.

When CONFIG_DEVMEM=y and CONFIG_STRICT_DEVMEM=n, doesn't this still
have the same problem for CC guests?

     Arnd

---

## [7] Dan Williams — 2025-04-30
*Subject: Re: [PATCH v5] x86/devmem: Drop /dev/mem access for confidential
 guests*

Greg Kroah-Hartman wrote:
> On Tue, Apr 29, 2025 at 07:46:22PM -0700, Dan Williams wrote:
> > Nikolay reports that accessing BIOS data (first 1MB of the physical

This patch at least forces it for x86 CC guests. I was not quite ready
to say any platform that has "select ARCH_HAS_CC_PLATFORM" should get
the same treatment. At the same time, no strong reason *not* to do that.

> You kind of mention it above in the last paragraph, but forcing that on
> for these guests feels like the best, and simplest, solution overall as

True, and this matches what Arnd is saying.

> OR, why not just force all cc guests to enable a security module that
> implements this for them?  :)

Let me take a look at that option as that seems to be where Arnd's
questions are leading me as well.

---

## [8] Dan Williams — 2025-04-30
*Subject: Re: [PATCH v5] x86/devmem: Drop /dev/mem access for confidential
 guests*

Arnd Bergmann wrote:
> On Wed, Apr 30, 2025, at 04:46, Dan Williams wrote:
> > While there is an existing mitigation to simulate and redirect access to

I would say not a "design choice", but rather a known leftover hole that
nobody has had the initiative to close since 2022.

https://lore.kernel.org/all/202204071526.37364B5E3@keescook/

> > The simplest option for now is arrange for /dev/mem to always behave as
> > if lockdown is enabled for confidential guests. Require confidential

Right, for example the policy could go as far as to always require
generic LOCKDOWN_KERNEL for confidential guests, but a distro likely
wants to be able to build confidential guests and bare metal host
kernels from the same kernel config. At a minimum it seems difficult to
get away from a runtime "is_confidential_guest()" check.

The other observation is that generic LOCKDOWN_KERNEL is about
protecting against root being able to compromise platform integrity
where confidential computing is full trust within the TEE, including
root to run amok, and no trust outside that.

> The existing rules that I can see are:
> 

I see the 1MB MMIO special-case in x86::devmem_is_allowed(), but where
is the 32-bit PCI BAR space workaround? Just to make sure I am not
missing a detail here.

Note, this devmem exclusion effort previously went through a phase of
always returning "0" (no access) from x86::devmem_is_allowed() [1]. The
rationale for hacking the special case into open_port() was to maintain
ABI consistency with LOCKDOWN_KERNEL. Right now x86 userspace expects
either LOCKDOWN_KERNEL semantics, or read(2) returns zero and mmap(2) is
unrestricted. If devmem_is_allowed() always says "no" then userspace is
introduced to a new failure mode.

I am open to rip the band-aid off and see what happens, but Robustness
Principle suggested mimicking semantics that LOCKDOWN_KERNEL has already
socialized.

[1]: http://lore.kernel.org/67f8a1a15cc29_7205294d7@dwillia2-xfh.jf.intel.com.notmuch

> > @@ -595,6 +596,15 @@ static int open_port(struct inode *inode, struct 
> > file *filp)

That is more a side effect of wanting to mimic the
security_locked_down(LOCKDOWN_DEV_MEM) behavior. That hook implies all
of /dev/{mem,kmem,port} follow the same policy.

> When CONFIG_DEVMEM=y and CONFIG_STRICT_DEVMEM=n, doesn't this still
> have the same problem for CC guests?

It does, but that's the point. The CC guests that need the exclusion
have "select STRICT_DEVMEM", and *maybe* some CC guest arch could
tolerate raw devmem access.

However, that is unlikely. The observations here and from Greg point to
security_locked_down() should be providing the answer here. Which
completes the full circle back towards Nikolay's original proposal of
allowing lockdown policy to handle a bitmap of options [2].

Nikolay, part of me is glad to have done the full exploration of the
problem space here. I learned something. At the same time it is humbling
to realize I could have saved everyone's time just supporting your
effort. Please pick up your lockdown bitmap proposal and consider this
thread a long-winded Reviewed-by.

[2]: http://lore.kernel.org/20250321102422.640271-1-nik.borisov@suse.com

BTW, you can avoid the IO_STRICT_DEVMEM complexity by including
LOCKDOWN_PCI_ACCESS in the list of LOCKDOWN bits that CC guests always
enable. If someone wants to enable confidential userspace PCI drivers
they can do the work to switch from LOCKDOWN_PCI_ACCESS to
IO_STRICT_DEVMEM.

---

## [9] Arnd Bergmann — 2025-05-01
*Subject: Re: [PATCH v5] x86/devmem: Drop /dev/mem access for confidential guests*

On Thu, May 1, 2025, at 02:56, Dan Williams wrote:
> Arnd Bergmann wrote:
>> On Wed, Apr 30, 2025, at 04:46, Dan Williams wrote:

Ok, I see.

>> The existing rules that I can see are:
>> 

The main difference on x86 is the xlate_dev_mem_ptr() function
that does an extra memremap() of the physical address, everything
else just does a phys_to_virt(). The only other architecture
with an xlate_dev_mem_ptr() implementation is s390, which uses
it to work around the first physical page being different per CPU.
ia64 had something similar to x86 but is gone now.

The other bit of the puzzle is that memremap() on x86 silently
falls back to ioremap() for non-RAM pages. This was originally
added in 2008 commit e045fb2a988a ("x86: PAT avoid aliasing in
/dev/mem read/write"). I'm not sure what happened exactly, but
I suspect that the low 1MB was already mapped at the time
through a cached mapping, while the PCI MMIO hole was perhaps
not mapped. On x86-32, the 32-bit PCI BAR area should not
be included here (since it's above high_memory), but the 16MB
hold may be.

The address is first checked by valid_phys_addr_range(), which
is defined in an architecture specific way, so it's possible that
there are additional architectures on which that includes MMIO
ranges that can be accesses through phys_to_virt(), but I could
not find any.

The default valid_phys_addr_range() just checks against
'high_memory' to see whether the address is in the linear
map. This works on all architectures that don't have holes
in the memory map for MMIO (most of them) or that don't
just ioremap() all MMIO space into the hole (most of the rest).

arm64 and loongarch check memblock allow known RAM both in
the linear map and outside of it, while arm32 and sh explicitly
exclude addresses before PHYS_OFFSET on machines where RAM
does not start at address 0.

       Arnd

---

## [10] Arnd Bergmann — 2025-05-01
*Subject: Re: [PATCH v5] x86/devmem: Drop /dev/mem access for confidential guests*

On Thu, May 1, 2025, at 10:12, Arnd Bergmann wrote:
> On Thu, May 1, 2025, at 02:56, Dan Williams wrote:
>> Arnd Bergmann wrote:

Following up myself after thinking about it some more:
if we remove both the <1MB special case and the memremap()
hack on x86-64 but leave both for x86-32, that would
also avoid the cases that break CC guests, right and
make x86-64 behave exactly like the other architectures,
right?

If there is software that still relies on those hacks, it's
probably very old, and more likely to be on 32-bit systems.
There are many references to /dev/mem in Debian codesearch [1],
but it's usually related to pre-PCIe graphics (svgalib, XFree86,
uvesafb/v86), or it's memory-only accesses that rely on
!CONFIG_STRICT_DEVMEM to read kernel structures.

     Arnd

[1] https://codesearch.debian.net/search?q=%2Fdev%2Fmem&literal=1&perpkg=1

---

## [11] Dave Hansen — 2025-05-01
*Subject: Re: [PATCH v5] x86/devmem: Drop /dev/mem access for confidential
 guests*

On 5/1/25 13:01, Arnd Bergmann wrote:
> If there is software that still relies on those hacks, it's
> probably very old, and more likely to be on 32-bit systems.

I did basically the same exercise a week or two ago. I really didn't see
any examples that concerned me. I completely agree that it looked very
much limited to old, crusty code that either doesn't matter at _all_ or
code that falls back to newer mechanisms on modern
CONFIG_STRICT_DEVMEM=y systems.

---
