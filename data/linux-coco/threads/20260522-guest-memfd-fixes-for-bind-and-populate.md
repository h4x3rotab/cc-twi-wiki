---
title: 'guest_memfd fixes for bind and populate'
date: 2026-05-22
last_reply: 2026-05-22
message_count: 4
participants: ['Ackerley Tng via B4 Relay']
---

## [1] Ackerley Tng via B4 Relay — 2026-05-22

This series is a group of fixes for the bind and populate flows for
guest_memfd, and fixes some issues reported by Sashiko after reviewing the
guest_memfd in-place conversions series [1] and another fixup series Sean
posted [3].

Sashiko pointed out

+ Possible write to read-only page [1]
    => Fixed in patch 1
+ Signed integer overflow in kvm_gmem_bind() twice: [2][3]
    => Fixed in patch 2
+ Unchecked xa_store_range() [3]
    => Fixed in patch 3

[1] https://lore.kernel.org/all/CA+EHjTwrygfMrZZSw4y7-ry8fidW2x0C7iuF2Q=dnPNHUmNtUg@mail.gmail.com/
[2] https://lore.kernel.org/all/CA+EHjTxcadguOfOo7RpJVtAzcY5JAFZTbrAT_wcN6akMi8gCUg@mail.gmail.com/
[3] https://lore.kernel.org/all/20260522180530.EE9101F00A3E@smtp.kernel.org/

Signed-off-by: Ackerley Tng <ackerleytng@google.com>
---
Ackerley Tng (1):
      KVM: guest_memfd: Handle errors from xa_store_range() when binding

Sean Christopherson (2):
      KVM: guest_memfd: Use write permissions when GUP-ing source pages
      KVM: guest_memfd: Fix possible signed integer overflow

 arch/x86/kvm/svm/sev.c   |  1 +
 arch/x86/kvm/vmx/tdx.c   |  2 +-
 include/linux/kvm_host.h |  3 ++-
 virt/kvm/guest_memfd.c   | 18 ++++++++++--------
 virt/kvm/kvm_mm.h        |  2 +-
 5 files changed, 15 insertions(+), 11 deletions(-)
---
base-commit: b7fbe9a1bf9ee6c967ef77d366ca58c35fcf1887
change-id: 20260522-fix-sev-gmem-post-populate-a36bef7f0698

Best regards,
--
Ackerley Tng <ackerleytng@google.com>

---

## [2] Ackerley Tng via B4 Relay — 2026-05-22
*Subject: [PATCH 1/3] KVM: guest_memfd: Use write permissions when GUP-ing
 source pages*

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
*Subject: [PATCH 2/3] KVM: guest_memfd: Fix possible signed integer overflow*

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
 virt/kvm/kvm_mm.h      | 2 +-
 2 files changed, 4 insertions(+), 5 deletions(-)

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
index 9fcc5d5b7f8d0..23813d74ce709 100644
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

---

## [4] Ackerley Tng via B4 Relay — 2026-05-22
*Subject: [PATCH 3/3] KVM: guest_memfd: Handle errors from xa_store_range()
 when binding*

From: Ackerley Tng <ackerleytng@google.com>

Unhandled errors from xa_store_range() means kvm_gmem_bind() might falsely
reporting success, leading to false assumptions in guest_memfd's lifecycle
later.

Handle these errors by checking and returning the error to the userspace.

Fixes: a7800aa80ea4d ("KVM: Add KVM_CREATE_GUEST_MEMFD ioctl() for guest-specific backing memory")
Signed-off-by: Ackerley Tng <ackerleytng@google.com>
---
 virt/kvm/guest_memfd.c | 5 +++--
 1 file changed, 3 insertions(+), 2 deletions(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index d203135969d13..104f0f3d6a0b3 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -648,6 +648,7 @@ int kvm_gmem_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
 	struct inode *inode;
 	struct file *file;
 	int r = -EINVAL;
+	void *result;
 
 	BUILD_BUG_ON(sizeof(gfn_t) != sizeof(slot->gmem.pgoff));
 
@@ -688,7 +689,7 @@ int kvm_gmem_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
 	if (kvm_gmem_supports_mmap(inode))
 		slot->flags |= KVM_MEMSLOT_GMEM_ONLY;
 
-	xa_store_range(&f->bindings, start, end - 1, slot, GFP_KERNEL);
+	result = xa_store_range(&f->bindings, start, end - 1, slot, GFP_KERNEL);
 	filemap_invalidate_unlock(inode->i_mapping);
 
 	/*
@@ -696,7 +697,7 @@ int kvm_gmem_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
 	 * not the other way 'round.  Active bindings are invalidated if the
 	 * file is closed before memslots are destroyed.
 	 */
-	r = 0;
+	r = xa_is_err(result) ? xa_err(result) : 0;
 err:
 	fput(file);
 	return r;

---
