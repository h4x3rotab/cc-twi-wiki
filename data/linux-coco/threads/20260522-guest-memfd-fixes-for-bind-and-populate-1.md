---
title: 'guest_memfd fixes for bind and populate'
date: 2026-05-22
last_reply: 2026-05-27
message_count: 20
participants: ['Ackerley Tng via B4 Relay', 'Sean Christopherson', 'Ackerley Tng']
---

## [1] Ackerley Tng via B4 Relay — 2026-05-22

This series is a group of fixes for the bind and populate flows for
guest_memfd, and fixes some issues reported by Sashiko after reviewing the
guest_memfd in-place conversions series [1] and another fixup series Sean
posted [3].

Changes in v2:

+ Add patch 4 and 5 to fix more issues, see below
+ Also update stub for kvm_gmem_bind()

Sashiko pointed out

+ Possible write to read-only page [1]
    => Fixed in patch 1
+ Signed integer overflow in kvm_gmem_bind() twice: [2][3]
    => Fixed in patch 2
+ Unchecked xa_store_range() [3]
    => Fixed in patch 3
+ Ordering issue with kmap_* and kunmap_* in sev_gmem_post_populate() [4]
    => Fixed in patch 4
+ Ordering issue with kmap_* and kunmap_* in sev_gmem_post_populate() [5]
    => Fixed in patch 5

[1] https://lore.kernel.org/all/CA+EHjTwrygfMrZZSw4y7-ry8fidW2x0C7iuF2Q=dnPNHUmNtUg@mail.gmail.com/
[2] https://lore.kernel.org/all/CA+EHjTxcadguOfOo7RpJVtAzcY5JAFZTbrAT_wcN6akMi8gCUg@mail.gmail.com/
[3] https://lore.kernel.org/all/20260522180530.EE9101F00A3E@smtp.kernel.org/
[4] https://sashiko.dev/#/patchset/20260507-gmem-inplace-conversion-v6-0-91ab5a8b19a4%40google.com?part=21
[5] https://sashiko.dev/#/patchset/20260522-fix-sev-gmem-post-populate-v1-0-9fc8d6437b65%40google.com?part=1

v1: https://lore.kernel.org/r/20260522-fix-sev-gmem-post-populate-v1-0-9fc8d6437b65@google.com

Signed-off-by: Ackerley Tng <ackerleytng@google.com>
---
Ackerley Tng (3):
      KVM: guest_memfd: Handle errors from xa_store_range() when binding
      KVM: SNP: Fix kunmap_local() unmapping order
      KVM: SNP: Mark source page dirty in sev_gmem_post_populate

Sean Christopherson (2):
      KVM: guest_memfd: Use write permissions when GUP-ing source pages
      KVM: guest_memfd: Fix possible signed integer overflow

 arch/x86/kvm/svm/sev.c   |  6 ++++--
 arch/x86/kvm/vmx/tdx.c   |  2 +-
 include/linux/kvm_host.h |  3 ++-
 virt/kvm/guest_memfd.c   | 24 ++++++++++++++++--------
 virt/kvm/kvm_mm.h        |  4 ++--
 5 files changed, 25 insertions(+), 14 deletions(-)
---
base-commit: b7fbe9a1bf9ee6c967ef77d366ca58c35fcf1887
change-id: 20260522-fix-sev-gmem-post-populate-a36bef7f0698

Best regards,
--
Ackerley Tng <ackerleytng@google.com>

---

## [2] Ackerley Tng via B4 Relay — 2026-05-22
*Subject: [PATCH v2 1/5] KVM: guest_memfd: Use write permissions when
 GUP-ing source pages*

From: Sean Christopherson <seanjc@google.com>

sev_gmem_post_populate() may write to the source page if there was an error
while performing SNP_LAUNCH_UPDATE.

Since GUP requested only reads, there is a chance sev_gmem_post_populate()
could be writing to some read-only page.

sev_gmem_post_populate() will only ever write the source page if the type
of page being LAUNCH_UPDATEd is a CPUID page. Hence, request a writable
page only when loading the CPUID page.

Since TDX never writes to the source page, always pass false to
kvm_gmem_populate().

With this, even if a read-only mapping or the global zero page was provided
as the source page, GUP will do a copy-on-write, making it writable before
the write happens in gvm_post_populate.

Fixes: 2a62345b30529 ("KVM: guest_memfd: GUP source pages prior to populating guest memory")
Signed-off-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Ackerley Tng <ackerleytng@google.com>
---
 arch/x86/kvm/svm/sev.c   | 1 +
 arch/x86/kvm/vmx/tdx.c   | 2 +-
 include/linux/kvm_host.h | 3 ++-
 virt/kvm/guest_memfd.c   | 6 ++++--
 4 files changed, 8 insertions(+), 4 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 940b97d4a8523..2f254c447923e 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2469,6 +2469,7 @@ static int snp_launch_update(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	sev_populate_args.type = params.type;
 
 	count = kvm_gmem_populate(kvm, params.gfn_start, src, npages,
+				  params.type == KVM_SEV_SNP_PAGE_TYPE_CPUID,
 				  sev_gmem_post_populate, &sev_populate_args);
 	if (count < 0) {
 		argp->error = sev_populate_args.fw_error;
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index b8c3d3d8bbfe5..00dcfcbc47f68 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -3185,7 +3185,7 @@ static int tdx_vcpu_init_mem_region(struct kvm_vcpu *vcpu, struct kvm_tdx_cmd *c
 		};
 		gmem_ret = kvm_gmem_populate(kvm, gpa_to_gfn(region.gpa),
 					     u64_to_user_ptr(region.source_addr),
-					     1, tdx_gmem_post_populate, &arg);
+					     1, false, tdx_gmem_post_populate, &arg);
 		if (gmem_ret < 0) {
 			ret = gmem_ret;
 			break;
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index 4c14aee1fb063..2c5ad9a6d5ce8 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -2596,7 +2596,8 @@ int kvm_arch_gmem_prepare(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn, int max_ord
 typedef int (*kvm_gmem_populate_cb)(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 				    struct page *page, void *opaque);
 
-long kvm_gmem_populate(struct kvm *kvm, gfn_t gfn, void __user *src, long npages,
+long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src,
+		       long npages, bool may_writeback_src,
 		       kvm_gmem_populate_cb post_populate, void *opaque);
 #endif
 
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 69c9d6d546b28..07d8db344872b 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -858,7 +858,8 @@ static long __kvm_gmem_populate(struct kvm *kvm, struct kvm_memory_slot *slot,
 	return ret;
 }
 
-long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long npages,
+long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src,
+		       long npages, bool may_writeback_src,
 		       kvm_gmem_populate_cb post_populate, void *opaque)
 {
 	struct kvm_memory_slot *slot;
@@ -892,8 +893,9 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 
 		if (src) {
 			unsigned long uaddr = (unsigned long)src + i * PAGE_SIZE;
+			unsigned int flags = may_writeback_src ? FOLL_WRITE : 0;
 
-			ret = get_user_pages_fast(uaddr, 1, 0, &src_page);
+			ret = get_user_pages_fast(uaddr, 1, flags, &src_page);
 			if (ret < 0)
 				break;
 			if (ret != 1) {

---

## [3] Ackerley Tng via B4 Relay — 2026-05-22
*Subject: [PATCH v2 2/5] KVM: guest_memfd: Fix possible signed integer
 overflow*

From: Sean Christopherson <seanjc@google.com>

The caller, kvm_set_memory_region(), checks for an overflow in an unsigned
u64 guest_memfd_offset. When guest_memfd_offset is passed to kvm_gmem_bind,
it is cast into a signed 64-bit integer.

Hence, a large 64-bit offset could result in a negative loff_t, which could
result in the overflow checks failing.

Make kvm_gmem_bind() take u64 instead of loff_t to consistently deal with
unsigned values to avoid this issue.

Fixes: a7800aa80ea4d ("KVM: Add KVM_CREATE_GUEST_MEMFD ioctl() for guest-specific backing memory")
Signed-off-by: Sean Christopherson <seanjc@google.com>
[Use size_t for size instead of u64]
Signed-off-by: Ackerley Tng <ackerleytng@google.com>
---
 virt/kvm/guest_memfd.c | 7 +++----
 virt/kvm/kvm_mm.h      | 4 ++--
 2 files changed, 5 insertions(+), 6 deletions(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 07d8db344872b..d203135969d13 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -640,9 +640,9 @@ int kvm_gmem_create(struct kvm *kvm, struct kvm_create_guest_memfd *args)
 }
 
 int kvm_gmem_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
-		  unsigned int fd, loff_t offset)
+		  unsigned int fd, u64 offset)
 {
-	loff_t size = slot->npages << PAGE_SHIFT;
+	size_t size = slot->npages << PAGE_SHIFT;
 	unsigned long start, end;
 	struct gmem_file *f;
 	struct inode *inode;
@@ -664,8 +664,7 @@ int kvm_gmem_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
 
 	inode = file_inode(file);
 
-	if (offset < 0 || !PAGE_ALIGNED(offset) ||
-	    offset + size > i_size_read(inode))
+	if (!PAGE_ALIGNED(offset) || offset + size > i_size_read(inode))
 		goto err;
 
 	filemap_invalidate_lock(inode->i_mapping);
diff --git a/virt/kvm/kvm_mm.h b/virt/kvm/kvm_mm.h
index 9fcc5d5b7f8d0..8c2bbfba63424 100644
--- a/virt/kvm/kvm_mm.h
+++ b/virt/kvm/kvm_mm.h
@@ -72,7 +72,7 @@ int kvm_gmem_init(struct module *module);
 void kvm_gmem_exit(void);
 int kvm_gmem_create(struct kvm *kvm, struct kvm_create_guest_memfd *args);
 int kvm_gmem_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
-		  unsigned int fd, loff_t offset);
+		  unsigned int fd, u64 offset);
 void kvm_gmem_unbind(struct kvm_memory_slot *slot);
 #else
 static inline int kvm_gmem_init(struct module *module)
@@ -82,7 +82,7 @@ static inline int kvm_gmem_init(struct module *module)
 static inline void kvm_gmem_exit(void) {};
 static inline int kvm_gmem_bind(struct kvm *kvm,
 					 struct kvm_memory_slot *slot,
-					 unsigned int fd, loff_t offset)
+					 unsigned int fd, u64 offset)
 {
 	WARN_ON_ONCE(1);
 	return -EIO;

---

## [4] Ackerley Tng via B4 Relay — 2026-05-22
*Subject: [PATCH v2 3/5] KVM: guest_memfd: Handle errors from
 xa_store_range() when binding*

From: Ackerley Tng <ackerleytng@google.com>

Unhandled errors from xa_store_range() means kvm_gmem_bind() might falsely
reporting success, leading to false assumptions in guest_memfd's lifecycle
later.

On error, restore the unbound state and return the error to userspace.

Fixes: a7800aa80ea4d ("KVM: Add KVM_CREATE_GUEST_MEMFD ioctl() for guest-specific backing memory")
Signed-off-by: Ackerley Tng <ackerleytng@google.com>
---
 virt/kvm/guest_memfd.c | 11 +++++++++--
 1 file changed, 9 insertions(+), 2 deletions(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index d203135969d13..5b4911ffa208a 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -648,6 +648,7 @@ int kvm_gmem_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
 	struct inode *inode;
 	struct file *file;
 	int r = -EINVAL;
+	void *result;
 
 	BUILD_BUG_ON(sizeof(gfn_t) != sizeof(slot->gmem.pgoff));
 
@@ -688,7 +689,14 @@ int kvm_gmem_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
 	if (kvm_gmem_supports_mmap(inode))
 		slot->flags |= KVM_MEMSLOT_GMEM_ONLY;
 
-	xa_store_range(&f->bindings, start, end - 1, slot, GFP_KERNEL);
+	result = xa_store_range(&f->bindings, start, end - 1, slot, GFP_KERNEL);
+	if (xa_is_err(result)) {
+		r = xa_err(result);
+		xa_store_range(&f->bindings, start, end - 1, NULL, GFP_KERNEL);
+	} else {
+		r = 0;
+	}
+
 	filemap_invalidate_unlock(inode->i_mapping);
 
 	/*
@@ -696,7 +704,6 @@ int kvm_gmem_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
 	 * not the other way 'round.  Active bindings are invalidated if the
 	 * file is closed before memslots are destroyed.
 	 */
-	r = 0;
 err:
 	fput(file);
 	return r;

---

## [5] Ackerley Tng via B4 Relay — 2026-05-22
*Subject: [PATCH v2 4/5] KVM: SNP: Fix kunmap_local() unmapping order*

From: Ackerley Tng <ackerleytng@google.com>

Mappings created with kmap_local_page() or kmap_local_pfn() must be
unmapped in the reverse order they were acquired, following a LIFO
(last-in, first-out) stack-based approach.

In sev_gmem_post_populate(), src_vaddr is mapped first and dst_vaddr is
mapped second. The current code incorrectly calls kunmap_local() for
src_vaddr before dst_vaddr.

Swap the kunmap_local() calls to ensure the mappings are released in the
correct order.

Fixes: 2a62345b3052 ("KVM: guest_memfd: GUP source pages prior to populating guest memory")
Signed-off-by: Ackerley Tng <ackerleytng@google.com>
---
 arch/x86/kvm/svm/sev.c | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 2f254c447923e..dbf75326a40f4 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2360,8 +2360,8 @@ static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 
 		memcpy(dst_vaddr, src_vaddr, PAGE_SIZE);
 
-		kunmap_local(src_vaddr);
 		kunmap_local(dst_vaddr);
+		kunmap_local(src_vaddr);
 	}
 
 	ret = rmp_make_private(pfn, gfn << PAGE_SHIFT, PG_LEVEL_4K,
@@ -2396,8 +2396,8 @@ static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 
 		memcpy(src_vaddr, dst_vaddr, PAGE_SIZE);
 
-		kunmap_local(src_vaddr);
 		kunmap_local(dst_vaddr);
+		kunmap_local(src_vaddr);
 	}
 
 out:

---

## [6] Ackerley Tng via B4 Relay — 2026-05-22
*Subject: [PATCH v2 5/5] KVM: SNP: Mark source page dirty in
 sev_gmem_post_populate*

From: Ackerley Tng <ackerleytng@google.com>

Mark the folio as dirty after copying data into the source page in
sev_gmem_post_populate. After the memcpy, failing to mark the page dirty
can lead to the memory management subsystem discarding the changes if the
page is reclaimed or otherwise processed by the swap subsystem.

Fixes: 2a62345b3052 ("KVM: guest_memfd: GUP source pages prior to populating guest memory")
Signed-off-by: Ackerley Tng <ackerleytng@google.com>
---
 arch/x86/kvm/svm/sev.c | 1 +
 1 file changed, 1 insertion(+)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index dbf75326a40f4..1a361f08c7a3d 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2395,6 +2395,7 @@ static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 		void *dst_vaddr = kmap_local_pfn(pfn);
 
 		memcpy(src_vaddr, dst_vaddr, PAGE_SIZE);
+		folio_mark_dirty(page_folio(src_page));
 
 		kunmap_local(dst_vaddr);
 		kunmap_local(src_vaddr);

---

## [7] Sean Christopherson — 2026-05-26
*Subject: Re: [PATCH v2 2/5] KVM: guest_memfd: Fix possible signed integer overflow*

For shortlogs (and changeloges), when possible, describe the _change_ itself, not
its impact is.	Sometimes "Fix xyz" is the best shortlog, e.g. when fixing build
failures, but here, I would go with:

  KVM: guest_memfd: Treat memslot binding offset+size as unsigned values

for two reasons.  First, it provides a lot more context for future readers, versus 
"Fix possible signed integer overflow" which doesn't even capture what flow is
affected, how the overflow is being fixed, etc.  Second, if the fix is wrong,
incomplete, etc., we don't end up with a follow-up patch that start with "Really
fix ...".

Oh, actually, three reasons.  This doesn't only affect the overflow check.  The
check on a negative offset is flawed, as it means KVM would incorrectly reject
bindings with (comically) large offsets.

LOL, four.  There is no bug.  The size of the memslot is ((1UL << 31) - 1)
pages, i.e. 0x7FF_FFFFF000:

	if (id < KVM_USER_MEM_SLOTS &&
	    (mem->memory_size >> PAGE_SHIFT) > KVM_MEM_MAX_NR_PAGES)
		return -EINVAL;

and so "loff_t size" can never be negative.

As for the offset, the negative check is intentional, because KVM_CREATE_GUEST_MEMFD
takes loff_t for the size, and so an offset that is negative would also be larger
than the size of the file.

I still think it's worth taking unsigned values, because teasing out all of that
information wasn't exactly easy.

On Fri, May 22, 2026, Ackerley Tng wrote:
> From: Sean Christopherson <seanjc@google.com>
> 

Why?  Oh, right, because kvm_memory_slot.npages is an "unsigned long".  The
discrepancy between a u64 for the offset and a size_t for the size is confusing,
as they are both conceptually in the same "domain".

Rather than u64 and size_t, we should use pgoff_t, which is what KVM already uses
as the storage for kvm_memory_slot.gmem.pgoff.

I'll send a new version as a standalone patch.

---

## [8] Sean Christopherson — 2026-05-26
*Subject: Re: [PATCH v2 4/5] KVM: SNP: Fix kunmap_local() unmapping order*

Similar comment on the shortlog as patch two.  "Fix the order" tells the reader
nothing useful, other than the author of the patch thought there was a bug.

  KVM: SEV: Unmap local kmaps in LIFO order, per highmem requirements

No need for a new version, I'll massage when applying.

On Fri, May 22, 2026, Ackerley Tng wrote:
> Mappings created with kmap_local_page() or kmap_local_pfn() must be
> unmapped in the reverse order they were acquired, following a LIFO

It's worth calling out that this is completely benign since SNP is 64-bit only.

---

## [9] Sean Christopherson — 2026-05-26
*Subject: Re: [PATCH v2 1/5] KVM: guest_memfd: Use write permissions when
 GUP-ing source pages*

The shortlog is misleading, bordering on outright wrong.  I think most people
would read it as "ALWAYS Use write permissions when GUP-ing source pages".  I
also think it should be scoped to:

  KVM: SEV:

because this only affects SNP, and IMO is an SNP bug, not a guest_memfd bug.  E.g.

  KVM: SEV: Pin source page for write when adding CPUID data for SNP guest

On Fri, May 22, 2026, Ackerley Tng wrote:
> From: Sean Christopherson <seanjc@google.com>
> 

Avoid referencing function names in changelogs when possible.  Unless the reader
is already familiar with the code, the name is meaningless.  The purpose of the
changelog is to complement the literal patch, not to provide a play-by-play
description.

> while performing SNP_LAUNCH_UPDATE.
> 

Describe changes in human-friendly, conversational language.  And in a way that
doesn't require looking at the patch to understand the changelog: "pass false"
is meaningless without looking at the code to see what flag was added (or exists).

> With this, even if a read-only mapping or the global zero page was provided
> as the source page, GUP will do a copy-on-write, making it writable before

Objection, speculation.  If the mapping is truly read-only, i.e. doesn't allow
writes at all, then GUP will fail.  This is all superfluous information though;
"read-only" is a pretty ubiquitous concept, there's no need to explain it in
gory detail.


I'll rewrite to this when applying:

---
When populating a guest_memfd instance with the initial CPUID data for an
SNP guest, acquire a writable pin on the source page as KVM will write back
the "correct" CPUID information if the userspace provided data is rejected
by trusted firmware.  Because KVM writes to the source page using a kernel
mapping, pinning for read could result in KVM clobbering read-only memory.

Note, well-behaved VMMs are unlikely to be affected, as CPUID information
is almost always dynamically generated by userspace, i.e. it's unlikely for
the CPUID information to be backed by a read-only mapping.
---

> Fixes: 2a62345b30529 ("KVM: guest_memfd: GUP source pages prior to populating guest memory")
> Signed-off-by: Sean Christopherson <seanjc@google.com>

Cc: stable@vger.kernel.org

> Signed-off-by: Ackerley Tng <ackerleytng@google.com>
> ---

---

## [10] Sean Christopherson — 2026-05-26
*Subject: Re: [PATCH v2 3/5] KVM: guest_memfd: Handle errors from
 xa_store_range() when binding*

On Fri, May 22, 2026, Ackerley Tng wrote:
> Unhandled errors from xa_store_range() means kvm_gmem_bind() might falsely
> reporting success, leading to false assumptions in guest_memfd's lifecycle

I would rather go with "xr".  "result" is too generic, e.g. begs the question of
"result of what?"

Actually, I don't think we even need an intermediate variable.

>  	BUILD_BUG_ON(sizeof(gfn_t) != sizeof(slot->gmem.pgoff));
>  

I'm not convinced this is necessary.  Sashiko "asked" the question:

 : If xa_store_range() fails midway through storing a large range (for example,
 : returning -ENOMEM), does it leave the already-processed entries in the
 : f->bindings XArray?
 : 
 : When this error is propagated back, the caller __kvm_set_memory_region()
 : will abort the operation and free the memslot without calling
 : kvm_gmem_unbind().
 : 
 : Since the partial XArray updates aren't rolled back here, could this leave
 : dangling pointers to the freed memslot in f->bindings? If so, when the file
 : is eventually closed, kvm_gmem_release() might iterate over these dangling
 : pointers and write to slot->gmem.file, resulting in a use-after-free.

but I think Sashiko is hallicunating.

If @entry is non-NULL, xa_store_range() pre-creates the entire range, before
storing anything into the range:

		if (entry) {
			unsigned int order = BITS_PER_LONG;
			if (last + 1)
				order = __ffs(last + 1);
			xas_set_order(&xas, last, order);
			xas_create(&xas, true);
			if (xas_error(&xas))
				goto unlock;
		}

Yes, the API handles failure on the subsequent xas_store(), but I can't imagine
that failure is actually, barring garbage input from KVM:

		do {
			xas_set_range(&xas, first, last);
			xas_store(&xas, entry);
			if (xas_error(&xas))
				goto unlock;
			first += xas_size(&xas);
		} while (first <= last);

Purely from a design perspective, providing an API that can fail partway through
under normal operation, with no indication of where failure occured (AFAICT),
would be awful.

> +	} else {
> +		r = 0;

All in all, unless someone proves with a test that I'm wrong, just this?

diff --git virt/kvm/guest_memfd.c virt/kvm/guest_memfd.c
index 0c923fd603fd..c0f5b9565be2 100644
--- virt/kvm/guest_memfd.c
+++ virt/kvm/guest_memfd.c
@@ -688,7 +688,7 @@ int kvm_gmem_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
        if (kvm_gmem_supports_mmap(inode))
                slot->flags |= KVM_MEMSLOT_GMEM_ONLY;
 
-       xa_store_range(&f->bindings, start, end - 1, slot, GFP_KERNEL);
+       r = xa_err(xa_store_range(&f->bindings, start, end - 1, slot, GFP_KERNEL));
        filemap_invalidate_unlock(inode->i_mapping);
 
        /*
@@ -696,7 +696,6 @@ int kvm_gmem_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
         * not the other way 'round.  Active bindings are invalidated if the
         * file is closed before memslots are destroyed.
         */
-       r = 0;
 err:
        fput(file);
        return r;

---

## [11] Sean Christopherson — 2026-05-26
*Subject: Re: [PATCH v2 5/5] KVM: SNP: Mark source page dirty in sev_gmem_post_populate*

On Fri, May 22, 2026, Ackerley Tng wrote:
> Mark the folio as dirty after copying data into the source page in
> sev_gmem_post_populate. After the memcpy, failing to mark the page dirty

I'd rather use set_page_dirty().  I'll fixup when applying, unless someon objects.

>  		kunmap_local(dst_vaddr);
>  		kunmap_local(src_vaddr);

---

## [12] Sean Christopherson — 2026-05-26
*Subject: Re: [PATCH v2 0/5] guest_memfd fixes for bind and populate*

On Fri, May 22, 2026, Ackerley Tng wrote:
> This series is a group of fixes for the bind and populate flows for
> guest_memfd, and fixes some issues reported by Sashiko after reviewing the

In the future, please don't bundle unrelated changes.  The SNP specific changes
are related and should be a series, but the signed integer thing and the lack of
error handling on xa_store_range() are completely unrelated, because the fact
that Sashiko kept complaining about pre-existing issues.

I totally understand why you bundled these together, but that obviously didn't
stop Sashiko from complaining about pre-existing issues, over and over.

Unnecessarily bundling can lead to exactly what's happening here: the three SNP
changes are ready to go, but the two unrelated guest_memfd changes need new
versions.  Which isn't hard to deal with, but it's extra friction that is easily
avoided.

I'll apply the SNP changes, and send a new version of the signed vs. unsigned
issue.  Please send a new version of the xa_store_range() error handling (or
prove that I'm wrong).

Thanks!

---

## [13] Sean Christopherson — 2026-05-27
*Subject: Re: [PATCH v2 0/5] guest_memfd fixes for bind and populate*

On Fri, 22 May 2026 15:46:05 -0700, Ackerley Tng wrote:
> This series is a group of fixes for the bind and populate flows for
> guest_memfd, and fixes some issues reported by Sashiko after reviewing the

Applied 1, 4, and 5 to kvm-x86 sev, with massaged shortlogs+changelogs.

[1/5] KVM: SEV: Pin source page for write when adding CPUID data for SNP guest
      https://github.com/kvm-x86/linux/commit/f13e90059908
[2/5] KVM: guest_memfd: Fix possible signed integer overflow
      [SKIP]
[3/5] KVM: guest_memfd: Handle errors from xa_store_range() when binding
      [SKIP]
[4/5] KVM: SEV: Unmap local kmaps in LIFO order, per highmem requirements
      https://github.com/kvm-x86/linux/commit/138f5f9cbe37
[5/5] KVM: SEV: Mark source page dirty when writing back CPUID data on failure
      https://github.com/kvm-x86/linux/commit/97cd21d57e9b

--
https://github.com/kvm-x86/linux/tree/next

---

## [14] Ackerley Tng — 2026-05-27
*Subject: Re: [PATCH v2 2/5] KVM: guest_memfd: Fix possible signed integer overflow*

Sean Christopherson <seanjc@google.com> writes:

> For shortlogs (and changeloges), when possible, describe the _change_ itself, not
> its impact is.	Sometimes "Fix xyz" is the best shortlog, e.g. when fixing build

Thanks for explaining!

> Oh, actually, three reasons.  This doesn't only affect the overflow check.  The
> check on a negative offset is flawed, as it means KVM would incorrectly reject

Makes sense.

> LOL, four.  There is no bug.  The size of the memslot is ((1UL << 31) - 1)
> pages, i.e. 0x7FF_FFFFF000:

I think the bug was that the sum of offset + size in kvm_gmem_bind()
when interpreted as signed integers could be smaller than
i_size_read(inode) and allow binding.

So IIUC even if size is small (and not negative), nothing catches a
large enough offset where offset + size (interpreted as unsigned
integers) doesn't overflow, but offset + size (interpreted as signed
integers) overflows.

> As for the offset, the negative check is intentional, because KVM_CREATE_GUEST_MEMFD
> takes loff_t for the size, and so an offset that is negative would also be larger

Yup it's still easier this way, and your proposed shortlog is good.

> On Fri, May 22, 2026, Ackerley Tng wrote:
>> From: Sean Christopherson <seanjc@google.com>

I picked size_t more because I thought it was semantically correct to
use the size type for a size. size_t may have different sizes (64 vs
32), but in the comparison offset + size > i_size_read(inode), size is
promoted to 64 bits, and signed inode size is cast to unsigned for
comparison, so I think that works.

pgoff_t is also unsigned, but I think that should be reserved for page
offsets/indices? Is that the way to think when choosing types? What does
"domain" mean above?

> I'll send a new version as a standalone patch.

---

## [15] Ackerley Tng — 2026-05-27
*Subject: Re: [PATCH v2 3/5] KVM: guest_memfd: Handle errors from
 xa_store_range() when binding*

Sean Christopherson <seanjc@google.com> writes:

> On Fri, May 22, 2026, Ackerley Tng wrote:
>> Unhandled errors from xa_store_range() means kvm_gmem_bind() might falsely

Good to go with xr too.

> Actually, I don't think we even need an intermediate variable.
>

When I updated this I kind of just assumed xa_store_range() always
iterates indices (so for a range [0, 10], it would store 11 times), and
an earlier index could be set, and a later store could result in
-ENOMEM.

Since you called this out, I dug into it more.

> If @entry is non-NULL, xa_store_range() pre-creates the entire range, before
> storing anything into the range:

xa_store_range() doesn't actually always iterate: if last + 1 is some
clean power of 2, it'll create a higher order xarray node.

Otherwise, it falls back to creating and storing 1 index/node at a time:
if the above did manage to create an xarray node, xas_error() returns
false, it goes on to the store below.

> Yes, the API handles failure on the subsequent xas_store(), but I can't imagine
> that failure is actually, barring garbage input from KVM:

So if a later xas_create() fails because it runs out of memory, the
earlier stores would have already been committed.

This ignores -EEXIST being returned since earlier in kvm_gmem_bind()
conflicts were already checked.

> Purely from a design perspective, providing an API that can fail partway through
> under normal operation, with no indication of where failure occured (AFAICT),

Do you mean the API of xas_store_range()? xas is updated by
xas_set_range() so that should track the last store. Since the cleanup
is storing NULLs and won't allocate, I thought it would be fine to just
store NULL on the entire range on error.

>> +	} else {
>> +		r = 0;

---

## [16] Ackerley Tng — 2026-05-27
*Subject: Re: [PATCH v2 5/5] KVM: SNP: Mark source page dirty in sev_gmem_post_populate*

Sean Christopherson <seanjc@google.com> writes:

> On Fri, May 22, 2026, Ackerley Tng wrote:
>> Mark the folio as dirty after copying data into the source page in

I was looking for page, dirty but set_page_dirty() somehow escaped my
search. This works, thanks!

>>  		kunmap_local(dst_vaddr);
>>  		kunmap_local(src_vaddr);

---

## [17] Sean Christopherson — 2026-05-27
*Subject: Re: [PATCH v2 2/5] KVM: guest_memfd: Fix possible signed integer overflow*

On Wed, May 27, 2026, Ackerley Tng wrote:
> Sean Christopherson <seanjc@google.com> writes:
> 

Oooh, duh, if @offset is positive, but @offset+size is negative.  Yes, that's a
real bug, confirmed via selftest.  I'll send a fix along with a selftest testcase.

Thanks much!

> >> Fixes: a7800aa80ea4d ("KVM: Add KVM_CREATE_GUEST_MEMFD ioctl() for guest-specific backing memory")
> >> Signed-off-by: Sean Christopherson <seanjc@google.com>

Just to avoid confusion over the definition of an offset/idnex:
  
  * The type of an index into the pagecache.

I.e. it's not the 12-bit offset into a 4KiB page.  Which I'm pretty sure you were
saying as well, just want to ensure we're on the same page.

I like pgoff_t more than size_t because, for KVM, it's really all about addressing
memory, thanks to the offset into guest_memfd being associated 1:1 with a GPA.
It's not perfect, because GPAs are tracked as 64-bit values, whereas the kernel
restricts itself to "unsigned long".  But that's a non-issue in practice since
guest_memfd is 64-bit only.

But conceptually, I like tracking the gmem offset as a pgoff_t to tie it back
to using GPAs to offset/index into gmem.  And for all intents and purposes, gmem
is nothing more than a glorified pagecache :-)

---

## [18] Ackerley Tng — 2026-05-27
*Subject: Re: [PATCH v2 2/5] KVM: guest_memfd: Fix possible signed integer overflow*

Sean Christopherson <seanjc@google.com> writes:

>
> [...snip...]

Wait yes I meant index as in the key if you think of the xarray of the
page cache as a key-value store.

> I like pgoff_t more than size_t because, for KVM, it's really all about addressing
> memory, thanks to the offset into guest_memfd being associated 1:1 with a GPA.

The offset into guest_memfd is associated 1:1 with a GPA, and this
offset is

    offset = index << PAGE_SHIFT

> It's not perfect, because GPAs are tracked as 64-bit values, whereas the kernel
> restricts itself to "unsigned long".  But that's a non-issue in practice since

So we actually want to use u64s for gmem offsets (where offset = index
<< PAGE_SHIFT), and pgoff_t for indices, since indices (aka page
offsets) are semantically the offset, counted in units of pages?

I pulled this conclusion together from filemap-related code like
filemap_add_folio() takes a pgoff_t index, so I thought gmem should
follow that and stick with pgoff_t for index/indices.

---

## [19] Sean Christopherson — 2026-05-27
*Subject: Re: [PATCH v2 2/5] KVM: guest_memfd: Fix possible signed integer overflow*

On Wed, May 27, 2026, Ackerley Tng wrote:
> Sean Christopherson <seanjc@google.com> writes:
> > I like pgoff_t more than size_t because, for KVM, it's really all about addressing

Hrm, poking around, I guess what we really should use for the byte offset is
uoff_t.  My only hesitation to using uoff_t was that it's hardly used anywhere,
but it does seem to fix exactly what we're trying to do.

I don't want to use a raw u64, because I dislike using u{8,16,32,64} (in KVM)
unless something absolutely _must_ be that size (and ideally _exactly_ that size).
Limiting use of raw uNN helps identify fields/variables that correspond to some
hardware asset, versus fields/variables that just need to be "big enough".  It's
not a 100% comprehensive rule of anything, e.g. there are still many "naturally
sized" hardware assets that need to be tracked with "unsigned long", but I still
find it helpful/valuable to highlight hardware-derived fields/variables.

> and pgoff_t for indices, since indices (aka page
> offsets) are semantically the offset, counted in units of pages?

Yeah, I agree the distinction will help us differentiate between byte offsets
and pfn offsets, especially with another compile-time assert to show the
relationship:

	BUILD_BUG_ON(sizeof(gpa_t) != sizeof(offset));
	BUILD_BUG_ON(sizeof(gfn_t) != sizeof(slot->gmem.pgoff));

> I pulled this conclusion together from filemap-related code like
> filemap_add_folio() takes a pgoff_t index, so I thought gmem should

---

## [20] Sean Christopherson — 2026-05-27
*Subject: Re: [PATCH v2 3/5] KVM: guest_memfd: Handle errors from
 xa_store_range() when binding*

On Wed, May 27, 2026, Ackerley Tng wrote:
> Sean Christopherson <seanjc@google.com> writes:
> > On Fri, May 22, 2026, Ackerley Tng wrote:

Ugh, _that's_ what the code is doing?  Argh, I missed that "first" is incremented
by whatever the batch size happened to be.

			first += xas_size(&xas);  <====
		} while (first <= last);

> if the above did manage to create an xarray node, xas_error() returns
> false, it goes on to the store below.

No, I mean xa_store_range().  AFAICT, on failure, it doesn't actually communicate
"where" failure occurred.  That's quite nasty.

> xas is updated by xas_set_range() so that should track the last store. Since
> the cleanup is storing NULLs and won't allocate, I thought it would be fine

Yeah, it's totally fine, and AFAICT the only remotely sane approach.

---
