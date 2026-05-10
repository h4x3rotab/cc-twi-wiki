---
title: '[Overview] guest_memfd extensions and dependencies 2025-05-15'
date: 2025-05-15
last_reply: 2025-05-15
message_count: 1
participants: ['David Hildenbrand']
---

## [1] David Hildenbrand — 2025-05-15

Hi,

as requested, a quick overview of guest_memfd extensions and their 
relationship/dependencies; this also highlights the order in which 
patches should likely go upstream (current state). Some things will 
likely change, especially the further we go down the dependency chain :)

TL;DR

A
|       +-- Expected dependency
|       |
|       v
+--B--E--F--G
|
+--C
|
+--D
|
+--H--I

As we post stuff that depends on something that is not upstream yet, we 
should (1) tag it as RFC and (2) provide a branch that contains all 
relevant patches.



(A) "Stage 1": Basic mmap support (Fuad) [1]

Allow guest_memfd to mmap'ed and contain "shared" memory. No in-place 
conversion support: either all-shared or all-private. Shared pages can 
be faulted in.


(B) "Stage 2": In-place conversion support (Fuad) [2]

Allow guest_memfd to contain a mixture of shared and private pages, and
converting between shared<->private in-place. Memory attributes 
(shared/private) are managed by guest_memfd instead of KVM.

Depends on (A).


(C) Direct-map removal support (Patrick) [3]

Allow for removal of the directmap of guest_memfd pages/folios.

Depends on (A)


(D) NUMA mempolicy support (Shivank) [4]

Configure the "shared mempolicy" similar to shmem using the VMA.

Depends on (A). But we'll have to be able to mmap any guest_memfd -- 
just all faults must fail for ones that don't support shared memory, so 
might require some tweaks on top of (A).


(E) 1G huge page support (via hugetlb) (Ackerley) [5]

Add support for huge pages obtained from hugetlb, splitting large folios 
to small folios whenever we convert to shared. Need to reassemble large 
folios before handing them back to hugetlb.

I *assume* that further changes are required to make Intel / AMD CoCo 
VMs make use of it -- essentially what (F) and (G) also deal with.

Depends on (B)


(F) AMD huge page support (via the buddy) (Michael) [6]

Add support for huge pages / large folios that we allocate from the 
buddy + preparedness tracking for AMD. In theory, we could add this 
support for "private only" memory, but likely we will just do it 
properly and base it on in-place conversion support.

So, expected to depend on (B), but likely depends to some degree on 
infrastructure being added in (E)


(G) Intel TDX huge page support (via the buddy) (Yan) [7]

Similar to (F) but for TDX.

Depends on (F).


(H) write() support (Nikita) [8]

Allow for using write() to more efficiently preallocate/populate memory 
for "all shared memory" VMs.

Depends on (A)


(I) UFFD-missing support (Nikita) [9]

Support userfaultfd-missing fault handling for guest_memfd.

Depends on (I), but likely could be based on (A) only.



I'm not listing the "factor out guest_memfd from KVM to mm/guestmem.c" / 
"guestmem library" / "guestmem shim" for now [10] as it will likely be 
covered by one of the other items as required.

Also, there is a lot of other planned work ("all shared" VMs can allow 
for not splitting large folios because there is no in-place conversion, 
guest_memfs, ... ).


[1] https://lkml.kernel.org/r/20250513163438.3942405-1-tabba@google.com
[2] https://lore.kernel.org/all/20250328153133.3504118-1-tabba@google.com/
[3] https://lkml.kernel.org/r/20250221160728.1584559-1-roypat@amazon.co.uk
[4] 
https://lore.kernel.org/linux-mm/20250408112402.181574-1-shivankg@amd.com/
[5] 
https://lore.kernel.org/all/cover.1747264138.git.ackerleytng@google.com/T/#u
[6] 
https://lore.kernel.org/all/20241212063635.712877-1-michael.roth@amd.com/T/#u
[7] 
https://lore.kernel.org/all/20250424030033.32635-1-yan.y.zhao@intel.com/T/#u
[8] 
https://lore.kernel.org/kvm/20250303130838.28812-1-kalyazin@amazon.com/T/
[9] 
https://lore.kernel.org/all/20250303133011.44095-1-kalyazin@amazon.com/T/#u
[10] 
https://lore.kernel.org/all/20241113-guestmem-library-v3-0-71fdee85676b@quicinc.com/T/#u

---
