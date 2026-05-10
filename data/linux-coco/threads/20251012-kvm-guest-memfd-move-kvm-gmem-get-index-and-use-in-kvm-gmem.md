---
title: 'KVM: guest_memfd: move kvm_gmem_get_index() and use in kvm_gmem_prepare_folio()'
date: 2025-10-12
last_reply: 2025-10-20
message_count: 9
participants: ['Shivank Garg', 'Sean Christopherson']
---

## [1] Shivank Garg — 2025-10-12

Move kvm_gmem_get_index() to the top of the file so that it can be used
in kvm_gmem_prepare_folio() to replace the open-coded calculation.

No functional change intended.

Reviewed-by: David Hildenbrand <david@redhat.com>
Signed-off-by: Shivank Garg <shivankg@amd.com>
---

Changelog:
V3:
- Split into distinct patches per Sean's feedback, drop whitespace and
  ULONG_MAX change.
V2:
- https://lore.kernel.org/all/20250902080307.153171-2-shivankg@amd.com
- Incorporate David's suggestions.
V1:
- https://lore.kernel.org/all/20250901051532.207874-3-shivankg@amd.com

 virt/kvm/guest_memfd.c | 12 ++++++------
 1 file changed, 6 insertions(+), 6 deletions(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index fbca8c0972da..22dacf49a04d 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -25,6 +25,11 @@ static inline kvm_pfn_t folio_file_pfn(struct folio *folio, pgoff_t index)
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
@@ -78,7 +83,7 @@ static int kvm_gmem_prepare_folio(struct kvm *kvm, struct kvm_memory_slot *slot,
 	 * checked when creating memslots.
 	 */
 	WARN_ON(!IS_ALIGNED(slot->gmem.pgoff, 1 << folio_order(folio)));
-	index = gfn - slot->base_gfn + slot->gmem.pgoff;
+	index = kvm_gmem_get_index(slot, gfn);
 	index = ALIGN_DOWN(index, 1 << folio_order(folio));
 	r = __kvm_gmem_prepare_folio(kvm, slot, index, folio);
 	if (!r)
@@ -335,11 +340,6 @@ static inline struct file *kvm_gmem_get_file(struct kvm_memory_slot *slot)
 	return get_file_active(&slot->gmem.file);
 }
 
-static pgoff_t kvm_gmem_get_index(struct kvm_memory_slot *slot, gfn_t gfn)
-{
-	return gfn - slot->base_gfn + slot->gmem.pgoff;
-}
-
 static bool kvm_gmem_supports_mmap(struct inode *inode)
 {
 	const u64 flags = (u64)inode->i_private;

---

## [2] Shivank Garg — 2025-10-12
*Subject: [PATCH V3 kvm-x86/gmem 2/2] KVM: guest_memfd: remove redundant gmem variable initialization*

Remove redundant initialization of gmem in __kvm_gmem_get_pfn() as it is
already initialized at the top of the function.

No functional change intended.

Reviewed-by: David Hildenbrand <david@redhat.com>
Signed-off-by: Shivank Garg <shivankg@amd.com>
---

Changelog:
V3:
- Split into distinct patches per Sean's feedback, drop whitespace and
  ULONG_MAX change.
V2:
- https://lore.kernel.org/all/20250902080307.153171-2-shivankg@amd.com
- Incorporate David's suggestions.
V1:
- https://lore.kernel.org/all/20250901051532.207874-3-shivankg@amd.com

 virt/kvm/guest_memfd.c | 1 -
 1 file changed, 1 deletion(-)

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 22dacf49a04d..caa87efc8f7a 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -668,7 +668,6 @@ static struct folio *__kvm_gmem_get_pfn(struct file *file,
 		return ERR_PTR(-EFAULT);
 	}
 
-	gmem = file->private_data;
 	if (xa_load(&gmem->bindings, index) != slot) {
 		WARN_ON_ONCE(xa_load(&gmem->bindings, index));
 		return ERR_PTR(-EIO);

---

## [3] Sean Christopherson — 2025-10-13
*Subject: Re: [PATCH V3 kvm-x86/gmem 1/2] KVM: guest_memfd: move
 kvm_gmem_get_index() and use in kvm_gmem_prepare_folio()*

FWIW, there's no need to put the base (target?) branch in the subject.  The
branch name is often incomplete information; by the time someone goes to apply
the patch, the branch may have changed significantly, or maybe have even been
deleted, e.g. I use ephemeral topic branch for kvm-x86 that get deleted once
their content is merge to kvm/next.

From Documentation/process/maintainer-kvm-x86.rst, my strong preference is that
contributors always use kvm-x86/next as the base branch,

  Base Tree/Branch
  ~~~~~~~~~~~~~~~~
  Fixes that target the current release, a.k.a. mainline, should be based on
  ``git://git.kernel.org/pub/scm/virt/kvm/kvm.git master``.  Note, fixes do not
  automatically warrant inclusion in the current release.  There is no singular
  rule, but typically only fixes for bugs that are urgent, critical, and/or were
  introduced in the current release should target the current release.
  
  Everything else should be based on ``kvm-x86/next``, i.e. there is no need to
  select a specific topic branch as the base.  If there are conflicts and/or
  dependencies across topic branches, it is the maintainer's job to sort them
  out.
  
  The only exception to using ``kvm-x86/next`` as the base is if a patch/series
  is a multi-arch series, i.e. has non-trivial modifications to common KVM code
  and/or has more than superficial changes to other architectures' code.  Multi-
  arch patch/series should instead be based on a common, stable point in KVM's
  history, e.g. the release candidate upon which ``kvm-x86 next`` is based.  If
  you're unsure whether a patch/series is truly multi-arch, err on the side of
  caution and treat it as multi-arch, i.e. use a common base.

and then use the --base option with git format-patch to capture the exact hash.

  Git Base
  ~~~~~~~~
  If you are using git version 2.9.0 or later (Googlers, this is all of you!),
  use ``git format-patch`` with the ``--base`` flag to automatically include the
  base tree information in the generated patches.
  
  Note, ``--base=auto`` works as expected if and only if a branch's upstream is
  set to the base topic branch, e.g. it will do the wrong thing if your upstream
  is set to your personal repository for backup purposes.  An alternative "auto"
  solution is to derive the names of your development branches based on their
  KVM x86 topic, and feed that into ``--base``.  E.g. ``x86/pmu/my_branch_name``,
  and then write a small wrapper to extract ``pmu`` from the current branch name
  to yield ``--base=x/pmu``, where ``x`` is whatever name your repository uses to
  track the KVM x86 remote.

My pushes to kvm-x86/next are always --force pushes (it's rebuilt like linux-next,
though far less frequently), but when pushing, I also push a persistent tag so
that the exact object for each incarnation of kvm-x86/next is reachable.  Combined
with --base, that makes it easy to apply a patch/series even months/years after
the fact (assuming I didn't screw up or forget the tag).

---

## [4] Sean Christopherson — 2025-10-13
*Subject: Re: [PATCH V3 kvm-x86/gmem 1/2] KVM: guest_memfd: move
 kvm_gmem_get_index() and use in kvm_gmem_prepare_folio()*

On Mon, Oct 13, 2025, Sean Christopherson wrote:
> FWIW, there's no need to put the base (target?) branch in the subject.  The
> branch name is often incomplete information; by the time someone goes to apply

Oh, right, this is a funky situation though due to kvm-x86/gmem not yet being
folded into kvm-x86/next.  So yeah, calling out the base branch is helpful in
that case, but providing the --base commit is still preferred (and of course,
they don't have to be mutually exclusive).

>   Base Tree/Branch
>   ~~~~~~~~~~~~~~~~

---

## [5] Garg, Shivank — 2025-10-14
*Subject: Re: [PATCH V3 kvm-x86/gmem 1/2] KVM: guest_memfd: move
 kvm_gmem_get_index() and use in kvm_gmem_prepare_folio()*

On 10/13/2025 11:46 PM, Sean Christopherson wrote:
> On Mon, Oct 13, 2025, Sean Christopherson wrote:
>> FWIW, there's no need to put the base (target?) branch in the subject.  The

Thanks for the detailed explanation on --base usage. I wasn't aware of this 
flag and will use it going forward.

I see you've already merged these changes into kvm-x86/gmem. Should I resend 
these patches with kvm-x86/next and --base, or is the current version sufficient?

Thank you,
Shivank

---

## [6] Sean Christopherson — 2025-10-14
*Subject: Re: [PATCH V3 kvm-x86/gmem 1/2] KVM: guest_memfd: move
 kvm_gmem_get_index() and use in kvm_gmem_prepare_folio()*

On Tue, Oct 14, 2025, Shivank Garg wrote:
> On 10/13/2025 11:46 PM, Sean Christopherson wrote:
> I see you've already merged these changes into kvm-x86/gmem.

Yep.  I need to do testing (not really of these patches, but of other things I've
applied), and then you'll see the "official" thank you mails.

> Should I resend these patches with kvm-x86/next and --base, or is the current
> version sufficient?

Current version is sufficient, thanks!

---

## [7] Sean Christopherson — 2025-10-15
*Subject: Re: [PATCH V3 kvm-x86/gmem 1/2] KVM: guest_memfd: move
 kvm_gmem_get_index() and use in kvm_gmem_prepare_folio()*

On Sun, 12 Oct 2025 07:16:06 +0000, Shivank Garg wrote:
> Move kvm_gmem_get_index() to the top of the file so that it can be used
> in kvm_gmem_prepare_folio() to replace the open-coded calculation.

Applied to kvm-x86 gmem, thanks!

[1/2] KVM: guest_memfd: move kvm_gmem_get_index() and use in kvm_gmem_prepare_folio()
      https://github.com/kvm-x86/linux/commit/6cae60a1f507
[2/2] KVM: guest_memfd: remove redundant gmem variable initialization
      https://github.com/kvm-x86/linux/commit/54eb8ea478b1

--
https://github.com/kvm-x86/linux/tree/next

---

## [8] Garg, Shivank — 2025-10-16
*Subject: Re: [PATCH V3 kvm-x86/gmem 1/2] KVM: guest_memfd: move
 kvm_gmem_get_index() and use in kvm_gmem_prepare_folio()*

On 10/15/2025 11:32 PM, Sean Christopherson wrote:
> On Sun, 12 Oct 2025 07:16:06 +0000, Shivank Garg wrote:
>> Move kvm_gmem_get_index() to the top of the file so that it can be used

Thank you :)

Best Regards,
Shivank

---

## [9] Sean Christopherson — 2025-10-20
*Subject: Re: [PATCH V3 kvm-x86/gmem 1/2] KVM: guest_memfd: move
 kvm_gmem_get_index() and use in kvm_gmem_prepare_folio()*

On Wed, Oct 15, 2025, Sean Christopherson wrote:
> On Sun, 12 Oct 2025 07:16:06 +0000, Shivank Garg wrote:
> > Move kvm_gmem_get_index() to the top of the file so that it can be used

FYI, I rebased these onto 6.18-rc2 to avoid a silly merge.  New hashes:

[1/2] KVM: guest_memfd: move kvm_gmem_get_index() and use in kvm_gmem_prepare_folio()
      https://github.com/kvm-x86/linux/commit/049e560d4f47
[2/2] KVM: guest_memfd: remove redundant gmem variable initialization
      https://github.com/kvm-x86/linux/commit/3f1078a445d9

---
