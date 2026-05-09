---
title: 'KVM: guest_memfd: use kvm_gmem_get_index() in more places and smaller cleanups'
date: 2025-09-02
last_reply: 2025-10-11
message_count: 5
participants: ['Shivank Garg', 'David Hildenbrand', 'Sean Christopherson']
---

## [1] Shivank Garg — 2025-09-02

Move kvm_gmem_get_index() to the top of the file and make it available for
use in more places.

Remove redundant initialization of the gmem variable because it's already
initialized.

Replace magic number -1UL with ULONG_MAX.

No functional change intended.

Signed-off-by: Shivank Garg <shivankg@amd.com>
---
Applies cleanly on kvm-next (a6ad54137) and guestmemfd-preview (3d23d4a27).

Changelog:
V2: Incorporate David's suggestions.
V1: https://lore.kernel.org/all/20250901051532.207874-3-shivankg@amd.com


 virt/kvm/guest_memfd.c | 17 +++++++++--------
 1 file changed, 9 insertions(+), 8 deletions(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index b2d6ad80f54c..1299e5e50844 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -44,6 +44,11 @@ static inline kvm_pfn_t folio_file_pfn(struct folio *folio, pgoff_t index)
 	return folio_pfn(folio) + (index & (folio_nr_pages(folio) - 1));
 }
 
+static pgoff_t kvm_gmem_get_index(struct kvm_memory_slot *slot, gfn_t gfn)
+{
+	return gfn - slot->base_gfn + slot->gmem.pgoff;
+}
+
 static int __kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slot,
 				    pgoff_t index, struct folio *folio)
 {
@@ -51,6 +56,7 @@ static int __kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slo
 	kvm_pfn_t pfn = folio_file_pfn(folio, index);
 	gfn_t gfn = slot->base_gfn + index - slot->gmem.pgoff;
 	int rc = kvm_arch_gmem_prepare(kvm, gfn, pfn, folio_order(folio));
+
 	if (rc) {
 		pr_warn_ratelimited("gmem: Failed to prepare folio for index %lx GFN %llx PFN %llx error %d.\n",
 				    index, gfn, pfn, rc);
@@ -107,7 +113,7 @@ static int kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slot,
 	 * checked when creating memslots.
 	 */
 	WARN_ON(!IS_ALIGNED(slot->gmem.pgoff, 1 << folio_order(folio)));
-	index = gfn - slot->base_gfn + slot->gmem.pgoff;
+	index = kvm_gmem_get_index(slot, gfn);
 	index = ALIGN_DOWN(index, 1 << folio_order(folio));
 	r = __kvm_gmem_prepare_folio(kvm, slot, index, folio);
 	if (!r)
@@ -327,8 +333,8 @@ static int kvm_gmem_release(struct inode *inode, struct file *file)
 	 * Zap all SPTEs pointed at by this file.  Do not free the backing
 	 * memory, as its lifetime is associated with the inode, not the file.
 	 */
-	kvm_gmem_invalidate_begin(gmem, 0, -1ul);
-	kvm_gmem_invalidate_end(gmem, 0, -1ul);
+	kvm_gmem_invalidate_begin(gmem, 0, ULONG_MAX);
+	kvm_gmem_invalidate_end(gmem, 0, ULONG_MAX);
 
 	list_del(&gmem->entry);
 
@@ -354,10 +360,6 @@ static inline struct file *kvm_gmem_get_file(struct kvm_memory_slot *slot)
 	return get_file_active(&slot->gmem.file);
 }
 
-static pgoff_t kvm_gmem_get_index(struct kvm_memory_slot *slot, gfn_t gfn)
-{
-	return gfn - slot->base_gfn + slot->gmem.pgoff;
-}
 
 static bool kvm_gmem_supports_mmap(struct inode *inode)
 {
@@ -940,7 +942,6 @@ static struct folio *__kvm_gmem_get_pfn(struct file *file,
 		return ERR_PTR(-EFAULT);
 	}
 
-	gmem = file->private_data;
 	if (xa_load(&gmem->bindings, index) != slot) {
 		WARN_ON_ONCE(xa_load(&gmem->bindings, index));
 		return ERR_PTR(-EIO);

---

## [2] David Hildenbrand — 2025-09-02
*Subject: Re: [PATCH V2 kvm-next] KVM: guest_memfd: use kvm_gmem_get_index() in
 more places and smaller cleanups*

On 02.09.25 10:03, Shivank Garg wrote:
> Move kvm_gmem_get_index() to the top of the file and make it available for
> use in more places.

Reviewed-by: David Hildenbrand <david@redhat.com>

---

## [3] Garg, Shivank — 2025-09-26
*Subject: Re: [PATCH V2 kvm-next] KVM: guest_memfd: use kvm_gmem_get_index() in
 more places and smaller cleanups*

On 9/2/2025 1:42 PM, David Hildenbrand wrote:
> On 02.09.25 10:03, Shivank Garg wrote:
>> Move kvm_gmem_get_index() to the top of the file and make it available for

Gentle ping :)

Thanks,
Shivank

---

## [4] Sean Christopherson — 2025-10-10
*Subject: Re: [PATCH V2 kvm-next] KVM: guest_memfd: use kvm_gmem_get_index() in
 more places and smaller cleanups*

TL;DR: Please split this into three patches, call out the use of
kvm_gmem_get_index() in kvm_gmem_prepare_folio, and unless someone feels strongly
about the ULONG_MAX change, just drop it.

On Tue, Sep 02, 2025, Shivank Garg wrote:
> Move kvm_gmem_get_index() to the top of the file and make it available for
> use in more places.

Not just "in more places", specifically for kvm_gmem_prepare_folio().  And this
also has kvm_gmem_prepare_folio() _use_ the helper.  That detail matters, because
without having actual user, such code movement would be completely arbitrary and
likely pointless churn.  E.g. AFAICT, it's not needed for the NUMA support or
even for the WIP-but-functional in-place conversion patches I have.

> Remove redundant initialization of the gmem variable because it's already
> initialized.

This is quite clearly three distinct patches.  Yes, they're trivial, but that's
exactly why they should be split up: it takes so, so little brain power to review
super trivial patches.  Bundling such patches together almost always increases
the total review cost relative to if they are split up.  I.e. if split, the cost
is A + B + C, but bundled together, the cost is A + B + C + X, where 'X' is the
extra effort it takes to figure out what changes go with what part of the changelog.
And sometimes (and for me, it's the case here), X > A + B + C, which makes for
grumpy reviewers.

Case in point, it took me way too long to spot the new use of kvm_gmem_get_index()
in kvm_gmem_prepare_folio(), due to the noise from the other changes getting in
the way.

More importantly, bundling things together like this makes it an all-or-nothing
proposition.  That matters, because I don't want to take the ULONG_MAX change.
The -1 pattern is meaningful (at least, IMO), as KVM is very specifically
invalidating 0 => 0xffffffff_ffffffff.  I don't love hiding those details behind
ULONG_MAX.  I realize it's a somewhat silly position, because xarray uses ULONG_MAX
for it's terminal value, but it gets weird in the guest_memfd code because @end is
used for both the xarray and for gfn range sent over to KVM.

Amusingly, the -1UL is also technically wrong, because @end is exclusive.  AFAIK
it's not actually possible to populate offset -1, so it's a benign off-by-one,
but I think super duper technically, we would want something absurd like this:

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index cfbb2f1aa1ab..f4d15cda2029 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -231,12 +231,13 @@ static void __kvm_gmem_invalidate_begin(struct gmem_file *f, pgoff_t start,
                                        pgoff_t end,
                                        enum kvm_gfn_range_filter attr_filter)
 {
+       pgoff_t last  = end == -1UL ? ULONG_MAX : end;
        bool flush = false, found_memslot = false;
        struct kvm_memory_slot *slot;
        struct kvm *kvm = f->kvm;
        unsigned long index;
 
-       xa_for_each_range(&f->bindings, index, slot, start, end - 1) {
+       xa_for_each_range(&f->bindings, index, slot, start, last) {
                pgoff_t pgoff = slot->gmem.pgoff;
 
                struct kvm_gfn_range gfn_range = {

> No functional change intended.
> 

Spurious whitespace change.  Yes, a newline should technically be there, but if
we make a change, I would prefer:

	int rc;

	rc = kvm_arch_gmem_prepare(kvm, gfn, pfn, folio_order(folio));
	if (rc) {
		...
	}

So that the check of the return value is tightly couple to the function call that
set the return value.

>  	if (rc) {
>  		pr_warn_ratelimited("gmem: Failed to prepare folio for index %lx GFN %llx PFN %llx error %d.\n",

---

## [5] Garg, Shivank — 2025-10-11
*Subject: Re: [PATCH V2 kvm-next] KVM: guest_memfd: use kvm_gmem_get_index() in
 more places and smaller cleanups*

On 10/10/2025 10:57 PM, Sean Christopherson wrote:
> TL;DR: Please split this into three patches, call out the use of
> kvm_gmem_get_index() in kvm_gmem_prepare_folio, and unless someone feels strongly


Thanks for the detailed feedback and review, Sean.
I didn't think enough about this from a reviewer/maintainer's perspective.
I'll split this up, make suggested changes, drop the ULONG_MAX
change, and rebase on kvm-x86 gmem for v3.

Thanks again,
Shivank

---
