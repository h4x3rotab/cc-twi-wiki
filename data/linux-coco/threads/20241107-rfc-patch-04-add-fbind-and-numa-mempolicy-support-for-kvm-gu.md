---
title: '[RFC PATCH 0/4] Add fbind() and NUMA mempolicy support for KVM\n guest_memfd'
date: 2024-11-07
last_reply: 2024-11-11
message_count: 6
participants: ['Shivank Garg', 'Matthew Wilcox', 'Paolo Bonzini', 'Vlastimil Babka', 'David Hildenbrand']
---

## [1] Shivank Garg — 2024-11-07

Hi Matthew,

On 11/6/2024 12:25 AM, Matthew Wilcox wrote:
> On Tue, Nov 05, 2024 at 04:45:45PM +0000, Shivank Garg wrote:
>> This patch series introduces fbind() syscall to support NUMA memory
guest_memfd doesn't have VMAs and hence can't store policy information in
VMA and use vma_alloc_folio_noprof() that fetches mpol from VMA.

The folio allocation path from guest_memfd typically looks like this...

kvm_gmem_get_folio
  filemap_grab_folio
    __filemap_get_folio
      filemap_alloc_folio
        __folio_alloc_node_noprof
          -> goes to the buddy allocator

Hence, I am trying to have a version of filemap_alloc_folio() that takes an mpol.


Thanks,
Shivank

---

## [2] Matthew Wilcox — 2024-11-07

On Thu, Nov 07, 2024 at 02:24:20PM +0530, Shivank Garg wrote:
> The folio allocation path from guest_memfd typically looks like this...
> 

It only takes that path if cpuset_do_page_mem_spread() is true.  Is the
real problem that you're trying to solve that cpusets are being used
incorrectly?

Backing up, it seems like you want to make a change to the page cache,
you've had a long discussion with people who aren't the page cache
maintainer, and you all understand the pros and cons of everything,
and here you are dumping a solution on me without talking to me, even
though I was at Plumbers, you didn't find me to tell me I needed to go
to your talk.

So you haven't explained a damned thing to me, and I'm annoyed at you.
Do better.  Starting with your cover letter.

---

## [3] Shivank Garg — 2024-11-08

On 11/7/2024 8:40 PM, Matthew Wilcox wrote:
> On Thu, Nov 07, 2024 at 02:24:20PM +0530, Shivank Garg wrote:
>> The folio allocation path from guest_memfd typically looks like this...

Hi Matthew,

I apologize for any misunderstanding and not providing adequate context.

To clarify:
- You may recall this work from its earlier iteration as an
  IOCTL-based approach, where you provided valuable review comments [1].
- I was not physically present at LPC. The discussion happened through
  the mailing list [2] and lobby discussion with my colleagues who visited
  Vienna.
- Based on feedback, particularly regarding the suggestion to consider
  fbind() as a more generic solution, we shifted to the current approach.

I posted this as *RFC* specifically to gather feedback on the feasibility of
this approach and to ensure I'm heading in the right direction.

Would you be willing to help me understand:
1. What additional information would be helpful to you and other reviewers?
2. How cpusets can be used correctly to fix this? (your point on
   cpuset_do_page_mem_spread() is interesting and I'll investigate it more
   thoroughly to understand).

I'll work on improving the cover letter to better explain the problem space
and proposed solution.

Thank you for the valuable feedback.

[1] https://lore.kernel.org/linux-mm/ZuimLtrpv1dXczf5@casper.infradead.org
[2] https://lore.kernel.org/linux-mm/ZvEga7srKhympQBt@intel.com

Best regards,
Shivank

---

## [4] Paolo Bonzini — 2024-11-08

On 11/7/24 16:10, Matthew Wilcox wrote:
> On Thu, Nov 07, 2024 at 02:24:20PM +0530, Shivank Garg wrote:
>> The folio allocation path from guest_memfd typically looks like this...

If it's false it's not very different, it goes to alloc_pages_noprof(). 
Then it respects the process's policy, but the policy is not 
customizable without mucking with state that is global to the process.

Taking a step back: the problem is that a VM can be configured to have 
multiple guest-side NUMA nodes, each of which will pick memory from the 
right NUMA node in the host.  Without a per-file operation it's not 
possible to do this on guest_memfd.  The discussion was whether to use 
ioctl() or a new system call.  The discussion ended with the idea of 
posting a *proposal* asking for *comments* as to whether the system call 
would be useful in general beyond KVM.

Commenting on the system call itself I am not sure I like the 
file_operations entry, though I understand that it's the simplest way to 
implement this in an RFC series.  It's a bit surprising that fbind() is 
a total no-op for everything except KVM's guest_memfd.

Maybe whatever you pass to fbind() could be stored in the struct file *, 
and used as the default when creating VMAs; as if every mmap() was 
followed by an mbind(), except that it also does the right thing with 
MAP_POPULATE for example.  Or maybe that's a horrible idea?

Adding linux-api to get input; original thread is at
https://lore.kernel.org/kvm/20241105164549.154700-1-shivankg@amd.com/.

Paolo

> Backing up, it seems like you want to make a change to the page cache,
> you've had a long discussion with people who aren't the page cache

---

## [5] Vlastimil Babka — 2024-11-11

On 11/8/24 18:31, Paolo Bonzini wrote:
> On 11/7/24 16:10, Matthew Wilcox wrote:
>> On Thu, Nov 07, 2024 at 02:24:20PM +0530, Shivank Garg wrote:

mbind() manpage has this:

       The  specified  policy  will  be  ignored  for  any MAP_SHARED
mappings in the specified memory range.  Rather the pages will be allocated
according to the memory policy of the thread that caused the page to be
allocated. Again, this may not be the thread that called mbind().

So that seems like we're not very keen on having one user of a file set a
policy that would affect other users of the file?

Now the next paragraph of the manpage says that shmem is different, and
guest_memfd is more like shmem than a regular file.

My conclusion from that is that fbind() might be too broad and we don't want
this for actual filesystem-backed files? And if it's limited to guest_memfd,
it shouldn't be an fbind()?

> Adding linux-api to get input; original thread is at
> https://lore.kernel.org/kvm/20241105164549.154700-1-shivankg@amd.com/.

---

## [6] David Hildenbrand — 2024-11-11

On 11.11.24 12:02, Vlastimil Babka wrote:
> On 11/8/24 18:31, Paolo Bonzini wrote:
>> On 11/7/24 16:10, Matthew Wilcox wrote:

I recall discussing that a couple of times in the context of QEMU. I 
have some faint recollection that the manpage is a bit imprecise:

IIRC, hugetlb also ends up using the VMA policy for MAP_SHARED mappings 
during faults (huge_node()->get_vma_policy()) -- but in contrast to 
shmem, it doesn't end up becoming the "shared" policy for the file, used 
when accessed through other VMAs.

> 
> So that seems like we're not very keen on having one user of a file set a

For VMs in QEMU we really want to configure the policy once in the main 
process and have all other processes (e.g., vhost-user) not worry about 
that when they mmap() guest memory.

With shmem this works by "shared policy" design (below). For hugetlb, we 
rely on the fact that mbind()+MADV_POPULATE_WRITE allows us to 
preallocate NUMA-aware. So with hugetlb we really preallocate all guest 
RAM to guarantee the NUMA placement.

It would not be the worst idea to have a clean interface to configure 
file-range policies instead of having this weird shmem mbind() behavior 
and the hugetlb hack.

Having that said, other filesystem are rarely used for backing VMs, at 
least in combination with NUMA. So nobody really cared that much for now.

Maybe fbind() would primarily only be useful for in-memory filesystems 
(shmem/hugetlb/guest_memfd).

> 
> Now the next paragraph of the manpage says that shmem is different, and

I was just once again diving into how mbind() on shmem is handled. And 
in fact, mbind() will call vma->set_policy() to update the per 
file-range policy. I wonder why we didn't do the same for hugetlb ... 
but of course, hugetlb must be special in any possible way.

Not saying it's the best idea, but as we are talking about mmap support 
of guest_memfd (only allowing to fault in shared/faultable pages), one 
*could* look into implementing mbind()+vma->set_policy() for guest_memfd 
similar to how shmem handles it.

It would require a (temporary) dummy VMA in the worst case (all private 
memory).

It sounds a bit weird, though, to require a VMA to configure this, 
though. But at least it's similar to what shmem does ...

---
