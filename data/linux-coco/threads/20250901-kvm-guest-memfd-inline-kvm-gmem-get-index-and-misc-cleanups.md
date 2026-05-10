---
title: 'KVM: guest_memfd: Inline kvm_gmem_get_index() and misc cleanups'
date: 2025-09-01
last_reply: 2025-09-01
message_count: 2
participants: ['Shivank Garg', 'David Hildenbrand']
---

## [1] Shivank Garg — 2025-09-01

Move kvm_gmem_get_index() to the top of the file and mark it inline.

Also clean up __kvm_gmem_get_pfn() by deferring gmem variable
declaration until after the file pointer check, avoiding unnecessary
initialization.

Replace magic number -1UL with ULONG_MAX.

No functional change intended.

Signed-off-by: Shivank Garg <shivankg@amd.com>
---

Applies cleanly on kvm-next (a6ad54137) and guestmemfd-preview (3d23d4a27).

 virt/kvm/guest_memfd.c | 18 ++++++++++--------
 1 file changed, 10 insertions(+), 8 deletions(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 08a6bc7d25b6..537f297a53cd 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -25,6 +25,11 @@ static inline kvm_pfn_t folio_file_pfn(struct folio *folio, pgoff_t index)
 	return folio_pfn(folio) + (index & (folio_nr_pages(folio) - 1));
 }
 
+static inline pgoff_t kvm_gmem_get_index(struct kvm_memory_slot *slot, gfn_t gfn)
+{
+	return gfn - slot->base_gfn + slot->gmem.pgoff;
+}
+
 static int __kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slot,
 				    pgoff_t index, struct folio *folio)
 {
@@ -32,6 +37,7 @@ static int __kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slo
 	kvm_pfn_t pfn = folio_file_pfn(folio, index);
 	gfn_t gfn = slot->base_gfn + index - slot->gmem.pgoff;
 	int rc = kvm_arch_gmem_prepare(kvm, gfn, pfn, folio_order(folio));
+
 	if (rc) {
 		pr_warn_ratelimited("gmem: Failed to prepare folio for index %lx GFN %llx PFN %llx error %d.\n",
 				    index, gfn, pfn, rc);
@@ -78,7 +84,7 @@ static int kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slot,
 	 * checked when creating memslots.
 	 */
 	WARN_ON(!IS_ALIGNED(slot->gmem.pgoff, 1 << folio_order(folio)));
-	index = gfn - slot->base_gfn + slot->gmem.pgoff;
+	index = kvm_gmem_get_index(slot, gfn);
 	index = ALIGN_DOWN(index, 1 << folio_order(folio));
 	r = __kvm_gmem_prepare_folio(kvm, slot, index, folio);
 	if (!r)
@@ -280,8 +286,8 @@ static int kvm_gmem_release(struct inode *inode, struct file *file)
 	 * Zap all SPTEs pointed at by this file.  Do not free the backing
 	 * memory, as its lifetime is associated with the inode, not the file.
 	 */
-	kvm_gmem_invalidate_begin(gmem, 0, -1ul);
-	kvm_gmem_invalidate_end(gmem, 0, -1ul);
+	kvm_gmem_invalidate_begin(gmem, 0, ULONG_MAX);
+	kvm_gmem_invalidate_end(gmem, 0, ULONG_MAX);
 
 	list_del(&gmem->entry);
 
@@ -307,10 +313,6 @@ static inline struct file *kvm_gmem_get_file(struct kvm_memory_slot *slot)
 	return get_file_active(&slot->gmem.file);
 }
 
-static pgoff_t kvm_gmem_get_index(struct kvm_memory_slot *slot, gfn_t gfn)
-{
-	return gfn - slot->base_gfn + slot->gmem.pgoff;
-}
 
 static bool kvm_gmem_supports_mmap(struct inode *inode)
 {
@@ -637,7 +639,7 @@ static struct folio *__kvm_gmem_get_pfn(struct file *file,
 					bool *is_prepared, int *max_order)
 {
 	struct file *gmem_file = READ_ONCE(slot->gmem.file);
-	struct kvm_gmem *gmem = file->private_data;
+	struct kvm_gmem *gmem;
 	struct folio *folio;
 
 	if (file != gmem_file) {

---

## [2] David Hildenbrand — 2025-09-01
*Subject: Re: [PATCH kvm-next 1/1] KVM: guest_memfd: Inline
 kvm_gmem_get_index() and misc cleanups*

On 01.09.25 07:15, Shivank Garg wrote:
> Move kvm_gmem_get_index() to the top of the file and mark it inline.

The marking of "inline" is not really required. A modern compiler can 
figure itself out that there is benefit in just inlining it.

I would rephrase the subject as

"KVM: guest_memfd: use kvm_gmem_get_index() in more places and smaller
  cleanups"

> 
> Also clean up __kvm_gmem_get_pfn() by deferring gmem variable

The compiler will figure that out. It's rather "No need to initialize 
'gmem' in __kvm_gmem_get_pfn() because we are already initializing it a 
second time, before using it."

However, I would rather drop the "gmem = file->private_data;" instead, 
because the compiler will optimize this either way.

---
