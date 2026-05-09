---
title: '[PATCH 3/5] KVM: gmem: Hold filemap invalidate lock while\n allocating/preparing folios'
date: 2025-05-19
last_reply: 2025-07-03
message_count: 11
participants: ['Ackerley Tng', 'Yan Zhao', 'Vishal Annapurve', 'Michael Roth']
---

## [1] Ackerley Tng — 2025-05-19

Ackerley Tng <ackerleytng@google.com> writes:

> Yan Zhao <yan.y.zhao@intel.com> writes:
>

This was not fixed in v2 [1], I misunderstood this locking issue.

IIUC kvm_gmem_populate() gets a pfn via __kvm_gmem_get_pfn(), then calls
part of the KVM fault handler to map the pfn into secure EPTs, then
calls the TDX module for the copy+encrypt.

Regarding this lock, seems like KVM'S MMU lock is already held while TDX
does the copy+encrypt. Why must the filemap_invalidate_lock() also be
held throughout the process?

If we don't have to hold the filemap_invalidate_lock() throughout, 

1. Would it be possible to call kvm_gmem_get_pfn() to get the pfn
   instead of calling __kvm_gmem_get_pfn() and managing the lock in a
   loop?

2. Would it be possible to trigger the kvm fault path from
   kvm_gmem_populate() so that we don't rebuild the get_pfn+mapping
   logic and reuse the entire faulting code? That way the
   filemap_invalidate_lock() will only be held while getting a pfn.

[1] https://lore.kernel.org/all/cover.1747264138.git.ackerleytng@google.com/T/

>>> > @@ -819,12 +827,16 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
>>> >  	pgoff_t index = kvm_gmem_get_index(slot, gfn);

---

## [2] Yan Zhao — 2025-05-21

On Mon, May 19, 2025 at 10:04:45AM -0700, Ackerley Tng wrote:
> Ackerley Tng <ackerleytng@google.com> writes:
> 
If kvm_gmem_populate() does not hold filemap invalidate lock around all
requested pages, what value should it return after kvm_gmem_punch_hole() zaps a
mapping it just successfully installed?

TDX currently only holds the read kvm->mmu_lock in tdx_gmem_post_populate() when
CONFIG_KVM_PROVE_MMU is enabled, due to both slots_lock and the filemap
invalidate lock being taken in kvm_gmem_populate().

Looks sev_gmem_post_populate() does not take kvm->mmu_lock either.

I think kvm_gmem_populate() needs to hold the filemap invalidate lock at least
around each __kvm_gmem_get_pfn(), post_populate() and kvm_gmem_mark_prepared().

> If we don't have to hold the filemap_invalidate_lock() throughout, 
> 
The kvm fault path is invoked in TDX's post_populate() callback.
I don't find a good way to move it to kvm_gmem_populate().

> [1] https://lore.kernel.org/all/cover.1747264138.git.ackerleytng@google.com/T/
>

---

## [3] Vishal Annapurve — 2025-06-02

On Tue, May 20, 2025 at 11:49 PM Yan Zhao <yan.y.zhao@intel.com> wrote:
>
> On Mon, May 19, 2025 at 10:04:45AM -0700, Ackerley Tng wrote:

Does TDX need kvm_gmem_populate path just to ensure SEPT ranges are
not zapped during tdh_mem_page_add and tdh_mr_extend operations? Would
holding KVM MMU read lock during these operations sufficient to avoid
having to do this back and forth between TDX and gmem layers?

>
> Looks sev_gmem_post_populate() does not take kvm->mmu_lock either.

---

## [4] Yan Zhao — 2025-06-03

On Mon, Jun 02, 2025 at 06:05:32PM -0700, Vishal Annapurve wrote:
> On Tue, May 20, 2025 at 11:49 PM Yan Zhao <yan.y.zhao@intel.com> wrote:
> >
I think the problem here is because in kvm_gmem_populate(),
"__kvm_gmem_get_pfn(), post_populate(), and kvm_gmem_mark_prepared()"
must be wrapped in filemap invalidate lock (shared or exclusive), right?

Then, in TDX's post_populate() callback, the filemap invalidate lock is held
again by kvm_tdp_map_page() --> ... ->kvm_gmem_get_pfn().


As in kvm_gmem_get_pfn(), the filemap invalidate lock also wraps both
__kvm_gmem_get_pfn() and kvm_gmem_prepare_folio():

filemap_invalidate_lock_shared();
__kvm_gmem_get_pfn();
kvm_gmem_prepare_folio();
filemap_invalidate_unlock_shared(),

I don't find a good reason for kvm_gmem_populate() to release filemap lock
before invoking post_populate().

Could we change the lock to filemap_invalidate_lock_shared() in
kvm_gmem_populate() and relax the warning in commit e918188611f0 ("locking: More
accurate annotations for read_lock()") ?


> > Looks sev_gmem_post_populate() does not take kvm->mmu_lock either.
> >

---

## [5] Vishal Annapurve — 2025-06-03

On Mon, Jun 2, 2025 at 6:34 PM Yan Zhao <yan.y.zhao@intel.com> wrote:
>
> On Mon, Jun 02, 2025 at 06:05:32PM -0700, Vishal Annapurve wrote:

I am contesting the need of kvm_gmem_populate path altogether for TDX.
Can you help me understand what problem does kvm_gmem_populate path
help with for TDX?

---

## [6] Yan Zhao — 2025-06-12

On Tue, Jun 03, 2025 at 11:28:35PM -0700, Vishal Annapurve wrote:
> On Mon, Jun 2, 2025 at 6:34 PM Yan Zhao <yan.y.zhao@intel.com> wrote:
> >
There is a long discussion on the list about this.

Basically TDX needs 3 steps for KVM_TDX_INIT_MEM_REGION.
1. Get the PFN
2. map the mirror page table
3. invoking tdh_mem_page_add().
Holding filemap invalidation lock around the 3 steps helps ensure that the PFN
passed to tdh_mem_page_add() is a valid one.

Rather then revisit it, what about fixing the contention more simply like this?
Otherwise we can revisit the history.
(The code is based on Ackerley's branch
https://github.com/googleprodkernel/linux-cc/commits/wip-tdx-gmem-conversions-hugetlb-2mept-v2, with patch "HACK: filemap_invalidate_lock() only for getting the pfn" reverted).


commit d71956718d061926e5d91e5ecf60b58a0c3b2bad
Author: Yan Zhao <yan.y.zhao@intel.com>
Date:   Wed Jun 11 18:17:26 2025 +0800

    KVM: guest_memfd: Use shared filemap invalidate lock in kvm_gmem_populate()

    Convert kvm_gmem_populate() to use shared filemap invalidate lock. This is
    to avoid deadlock caused by kvm_gmem_populate() further invoking
    tdx_gmem_post_populate() which internally acquires shared filemap
    invalidate lock in kvm_gmem_get_pfn().

    To avoid lockep warning by nested shared filemap invalidate lock,
    avoid holding shared filemap invalidate lock in kvm_gmem_get_pfn() when
    lockdep is enabled.

    Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>

diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 784fc1834c04..ccbb7ceb978a 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -2393,12 +2393,16 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
        struct file *file = kvm_gmem_get_file(slot);
        struct folio *folio;
        bool is_prepared = false;
+       bool get_shared_lock;
        int r = 0;

        if (!file)
                return -EFAULT;

-       filemap_invalidate_lock_shared(file_inode(file)->i_mapping);
+       get_shared_lock = !IS_ENABLED(CONFIG_LOCKDEP) ||
+                         !lockdep_is_held(&file_inode(file)->i_mapping->invalidate_lock);
+       if (get_shared_lock)
+               filemap_invalidate_lock_shared(file_inode(file)->i_mapping);

        folio = __kvm_gmem_get_pfn(file, slot, index, pfn, &is_prepared, max_order);
        if (IS_ERR(folio)) {
@@ -2423,7 +2427,8 @@ int kvm_gmem_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
        else
                folio_put(folio);
 out:
-       filemap_invalidate_unlock_shared(file_inode(file)->i_mapping);
+       if (get_shared_lock)
+               filemap_invalidate_unlock_shared(file_inode(file)->i_mapping);
        fput(file);
        return r;
 }
@@ -2536,7 +2541,7 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
        if (!file)
                return -EFAULT;

-       filemap_invalidate_lock(file->f_mapping);
+       filemap_invalidate_lock_shared(file->f_mapping);

        npages = min_t(ulong, slot->npages - (start_gfn - slot->base_gfn), npages);
        for (i = 0; i < npages; i += npages_to_populate) {
@@ -2587,7 +2592,7 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
                        break;
        }

-       filemap_invalidate_unlock(file->f_mapping);
+       filemap_invalidate_unlock_shared(file->f_mapping);

        fput(file);
        return ret && !i ? ret : i;


If it looks good to you, then for the in-place conversion version of
guest_memfd, there's one remaining issue left: an AB-BA lock issue between the
shared filemap invalidate lock and mm->mmap_lock, i.e.,
- In path kvm_gmem_fault_shared(),
  the lock sequence is mm->mmap_lock --> filemap_invalidate_lock_shared(),
- while in path kvm_gmem_populate(),
  the lock sequence is filemap_invalidate_lock_shared() -->mm->mmap_lock.

We can fix it with below patch. The downside of the this patch is that it
requires userspace to initialize all source pages passed to TDX, which I'm not
sure if everyone likes it. If it cannot land, we still have another option:
disallow the initial memory regions to be backed by the in-place conversion
version of guest_memfd. If this can be enforced, then we can resolve the issue
by annotating the lockdep, indicating that kvm_gmem_fault_shared() and
kvm_gmem_populate() cannot occur on the same guest_memfd, so the two shared
filemap invalidate locks in the two paths are not the same.

Author: Yan Zhao <yan.y.zhao@intel.com>
Date:   Wed Jun 11 18:23:00 2025 +0800

    KVM: TDX: Use get_user_pages_fast_only() in tdx_gmem_post_populate()

    Convert get_user_pages_fast() to get_user_pages_fast_only()
    in tdx_gmem_post_populate().

    Unlike get_user_pages_fast(), which will acquire mm->mmap_lock and fault in
    physical pages after it finds the pages have not already faulted in or have
    been zapped/swapped out, get_user_pages_fast_only() returns directly in
    such cases.

    Using get_user_pages_fast_only() can avoid tdx_gmem_post_populate()
    acquiring mm->mmap_lock, which may cause AB, BA lockdep warning with the
    shared filemap invalidate lock when guest_memfd in-place conversion is
    supported. (In path kvm_gmem_fault_shared(), the lock sequence is
    mm->mmap_lock --> filemap_invalidate_lock_shared(), while in path
    kvm_gmem_populate(), the lock sequence is filemap_invalidate_lock_shared()
    -->mm->mmap_lock).

    Besides, using get_user_pages_fast_only() and returning directly to
    userspace if a page is not present in the primary PTE can help detect a
    careless case that the source pages are not initialized by userspace.
    As initial memory region bypasses guest acceptance, copying an
    uninitialized source page to guest could be harmful and undermine the page
    measurement.

    Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 93c31eecfc60..462390dddf88 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -3190,9 +3190,10 @@ static int tdx_gmem_post_populate_4k(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
         * Get the source page if it has been faulted in. Return failure if the
         * source page has been swapped out or unmapped in primary memory.
         */
-       ret = get_user_pages_fast((unsigned long)src, 1, 0, &src_page);
+       ret = get_user_pages_fast_only((unsigned long)src, 1, 0, &src_page);
        if (ret < 0)
                return ret;
+
        if (ret != 1)
                return -ENOMEM;

---

## [7] Vishal Annapurve — 2025-06-12

On Thu, Jun 12, 2025 at 5:43 AM Yan Zhao <yan.y.zhao@intel.com> wrote:
>
> On Tue, Jun 03, 2025 at 11:28:35PM -0700, Vishal Annapurve wrote:

Indulge me a bit here. If the above flow is modified as follows, will it work?
1. Map the mirror page table
2. Hold the read mmu lock
3. Get the pfn from mirror page table walk
4. Invoke tdh_mem_page_add and mr_extend
5. drop the read mmu lock

If we can solve the initial memory region population this way for TDX
then at least for TDX:
1) Whole kvm_gmem_populate path is avoided
2) No modifications needed for the userspace-guest_memfd interaction
you suggested below.

>
> Rather then revisit it, what about fixing the contention more simply like this?

---

## [8] Michael Roth — 2025-06-13

On Thu, Jun 12, 2025 at 08:40:59PM +0800, Yan Zhao wrote:
> On Tue, Jun 03, 2025 at 11:28:35PM -0700, Vishal Annapurve wrote:
> > On Mon, Jun 2, 2025 at 6:34 PM Yan Zhao <yan.y.zhao@intel.com> wrote:

Hi Yan,

I had been working on some kind of locking scheme that could account for some
potential[1] changes needed to allowing concurrent updating of "preparedness"
state while still allowing for concurrent fault handling. I posted a tree
there in that link with an alternative scheme that's based on rw_semaphore
like filemap invalidate lock, but with some changes to allow the folio
lock to be taken to handle write-side updates to "preparedness" state
instead of needing to take a write-lock.

With that approach (or something similar), it is then possible to drop reliance
on using the filemap invalidate lock in kvm_gmem_get_pfn(), and that I
think would cleanly resolve this particular issue.

However, it was also suggested during the guest_memfd call that we revisit
the need to track preparedness in guest_memfd at all, and resulted in me
posting this rfc[2] that removes preparedness tracking from gmem
completely. That series is based on Ackerley's locking scheme from his
HugeTLBFS series however, which re-uses filemap invalidate rw_semaphore
to protect the shareability state, so you'd hit similar issues with
kvm_gmem_populate().

However, as above (and even more easily so since we don't need to do
anything fancy for concurrent "preparedness" updates), it would be
fairly trivial to replace the use of filemap invalidate lock with a
rw_semaphore that's dedicated to protecting shareability state, which
should make it possible to drop the use of
filemap_invalidate_lock[_shared]() in kvm_gmem_get_pfn().

But your above patch seems like it would at least get things working in
the meantime if there's still some discussion that needs to happen
before we can make a good call on:

  1) whether to continue to use the filemap invalidate or use a dedicated one
     (my 2 cents: use a dedicated lock to we don't have to deal with
     inheriting unintended/unecessary locking dependencies)
  2) whether or not is will be acceptable to drop preparedness-tracking
     from guest_memfd or not
     (my 2 cents: it will make all our lives much happier)
  3) open-code what kvm_gmem_populate() handles currently if we need
     extra flexibility WRT to locking
     (my 2 cents: if it can be avoided it's still nice to gmem
     handle/orchestrate this to some degree)

Thanks,

Mike

[1] https://lore.kernel.org/lkml/20250529054227.hh2f4jmyqf6igd3i@amd.com/
[2] https://lore.kernel.org/kvm/20250613005400.3694904-1-michael.roth@amd.com/

> 
>         folio = __kvm_gmem_get_pfn(file, slot, index, pfn, &is_prepared, max_order);

---

## [9] Michael Roth — 2025-06-13

On Thu, Jun 12, 2025 at 08:40:59PM +0800, Yan Zhao wrote:
> On Tue, Jun 03, 2025 at 11:28:35PM -0700, Vishal Annapurve wrote:
> > On Mon, Jun 2, 2025 at 6:34 PM Yan Zhao <yan.y.zhao@intel.com> wrote:

Since those requirements are already satisfied with kvm_gmem_populate(),
then maybe this issue is more with the fact that tdh_mem_page_add() is
making a separate call to kvm_gmem_get_pfn() even though the callback
has been handed a stable PFN that's protected with the filemap
invalidate lock.

Maybe some variant of kvm_tdp_map_page()/kvm_mmu_do_page_fault() that
can be handed the PFN and related fields up-front rather than grabbing
them later would be a more direct way to solve this? That would give us
more flexibility on the approaches I mentioned in my other response for
how to protect shareability state.

This also seems more correct in the sense that the current path triggers:

  tdx_gmem_post_populate
    kvm_tdp_mmu_page_fault
      kvm_gmem_get_pfn
        kvm_gmem_prepare_folio

even the kvm_gmem_populate() intentially avoids call kvm_gmem_get_pfn() in
favor of __kvm_gmem_get_pfn() specifically to avoid triggering the preparation
hooks, since kvm_gmem_populate() is a special case of preparation that needs
to be handled seperately/differently from the fault-time hooks.

This probably doesn't affect TDX because TDX doesn't make use of prepare
hooks, but since it's complicating things here it seems like we should address
it directly rather than work around it. Maybe it could even be floated as a
patch directly against kvm/next?

Thanks,

Mike

> 
> Rather then revisit it, what about fixing the contention more simply like this?

---

## [10] Yan Zhao — 2025-07-03

On Thu, Jun 12, 2025 at 07:43:45AM -0700, Vishal Annapurve wrote:
> On Thu, Jun 12, 2025 at 5:43 AM Yan Zhao <yan.y.zhao@intel.com> wrote:
> >
Thanks. I posted an RFC [1]. We can discuss there :)

[1] https://lore.kernel.org/lkml/20250703062641.3247-1-yan.y.zhao@intel.com/

---

## [11] Yan Zhao — 2025-07-03

On Fri, Jun 13, 2025 at 01:04:18PM -0500, Michael Roth wrote:
> On Thu, Jun 12, 2025 at 08:40:59PM +0800, Yan Zhao wrote:
> > On Tue, Jun 03, 2025 at 11:28:35PM -0700, Vishal Annapurve wrote:

I prefer Vishal's proposal over this one.

> This also seems more correct in the sense that the current path triggers:
> 
Posted an RFC for discussion.
https://lore.kernel.org/lkml/20250703062641.3247-1-yan.y.zhao@intel.com/

Thanks
Yan

---
