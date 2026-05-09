---
title: 'Unmapping KVM Guest Memory from Host Kernel'
date: 2024-05-13
last_reply: 2024-05-13
message_count: 7
participants: ['Patrick Roy', 'Sean Christopherson', 'Gowans, James', 'Manwaring, Derek']
---

## [1] Patrick Roy — 2024-05-13

Hi all,

On 3/9/24 11:14, Mike Rapoport wrote:

>>> >>> With this in mind, what’s the best way to solve getting guest RAM out of
>>> >>> the direct map? Is memfd_secret integration with KVM the way to go, or

We’ve been playing around with extending guest_memfd to remove guest memory
from the direct map. Removal from direct map aspect is indeed fairly
straight-forward; since we cannot map guest_memfd, we don’t need to worry about
folios without direct map entries getting to places where they will cause
kernel panics.

However, we ran into problems running non-CoCo VMs with guest_memfd for guest
memory, independent of direct map entries being available or not. There’s a
handful of places where a traditional KVM / Userspace setup currently touches
guest memory:

* Loading the Guest Kernel into guest-owned memory
* Instruction fetch from arbitrary guest addresses and guest page table walks  
  for MMIO emulation (for example for IOAPIC accesses)
* kvm-clock
* I/O devices

With guest_memfd, if the guest is running from guest-private memory, these need
to be rethought, since now the memory is unavailable to userspace, and KVM is
not enlightened about guest_memfd’s existance everywhere (when I was
experimenting with this, it generally read garbage data from the shared VMA,
but I think I’ve since seen some patches floating around that would make it
return -EFAULT instead).

CoCo VMs have various methods for working around these: You load a guest kernel
using some “populate on first access” mechanism [1], kvm-clock and I/O is
solved by having the guest mark the relevant address ranges as “shared” ahead
of time [2] and bounce buffering via swiotlb [4], and Intel TDX solves the
instruction emulation problem for MMIO by injecting a #VE and having the guest
do the emulation itself [3].

For non-CoCo VMs, where memory is not encrypted, and the threat model assumes a
trusted host userspace, we would like to avoid changing the VM model so
completely. If we adopt CoCo’s approaches where KVM / Userspace touches guest
memory we would get all the complexity, yet none of the encryption.
Particularly the complexity on the MMIO path seems nasty, but x86 does not
pre-decode instructions on MMIO exits (which are just EPT_VIOLATIONs) like it
does for PIO exits, so I also don’t really see a way around it in the
guest_memfd model.

We’ve played around a lot with allowing userspace mappings of guest_memfd, and
then having KVM internally access guest_memfd via userspace page tables (and
came up with multiple hacky ways to boot simple Linux initrds from
guest_memfd), but this is fairly awkward for two reasons:

1. Now lots of codepaths in KVM end up accessing guest_memfd, which from my
understanding goes against the guest_memfd goal of making machine checks
because of incorrect accesses to TDX memory impossible, and
2. We need to somehow get a userspace mapping of guest_memfd into KVM (a hacky
way I could make this work was setting up kvm_user_memory_region2 with
userspace_addr set to a mmap of guest_memory, which actually "works" for
everything but kvm-clock, but I also realized later that this is just
memfd_secret with extra steps).

We also played around with having KVM access guest_memfd through the direct map
(by temporarily reinserting pages into it when needed), but this again means
lots of KVM code learns about how to access guest RAM via guest_memfd.

There are a few other features we need to support, such as serving page faults
using UFFD, which we are not too sure how to realize with guest_memfd since
UFFD is VMA based (although to me some sort of “UFFD-for-FD” sounds like
something that’d be useful even outside of our guest_memfd usecase).

With these challenges in mind, some variant of memfd_secret continues to look
attractive for the non-CoCo case. Perhaps a variant that supports in-kernel
faults and provides some way for gfn_to_pfn_cache users like kvm-clock to
restore the direct map entries.

Sean, you mentioned that you envision guest_memfd also supporting non-CoCo VMs.
Do you have some thoughts about how to make the above cases work in the
guest_memfd context?

> > --
> > Sincerely yours,

Best,
Patrick

[1]: https://lore.kernel.org/kvm/20240404185034.3184582-1-pbonzini@redhat.com/T/#m4cc08ce3142a313d96951c2b1286eb290c7d1dac
[2]: https://elixir.bootlin.com/linux/latest/source/arch/x86/kernel/kvmclock.c#L227
[3]: https://www.kernel.org/doc/html/next/x86/tdx.html#mmio-handling
[4]: https://www.kernel.org/doc/html/next/x86/tdx.html#shared-memory-conversions

---

## [2] Sean Christopherson — 2024-05-13

On Mon, May 13, 2024, Patrick Roy wrote:

> For non-CoCo VMs, where memory is not encrypted, and the threat model assumes a
> trusted host userspace, we would like to avoid changing the VM model so

Uber nit, modern AMD CPUs do provide the byte stream, though there is at least
one related erratum.  Intel CPUs don't provide the byte stream or pre-decode in
any way.

> pre-decode instructions on MMIO exits (which are just EPT_VIOLATIONs) like it
> does for PIO exits, so I also don’t really see a way around it in the

...

> Sean, you mentioned that you envision guest_memfd also supporting non-CoCo VMs.
> Do you have some thoughts about how to make the above cases work in the

Yes.  The hand-wavy plan is to allow selectively mmap()ing guest_memfd().  There
is a long thread[*] discussing how exactly we want to do that.  The TL;DR is that
the basic functionality is also straightforward; the bulk of the discussion is
around gup(), reclaim, page migration, etc.

[*] https://lore.kernel.org/all/ZdfoR3nCEP3HTtm1@casper.infradead.org

---

## [3] Gowans, James — 2024-05-13

On Mon, 2024-05-13 at 08:39 -0700, Sean Christopherson wrote:
> > Sean, you mentioned that you envision guest_memfd also supporting non-CoCo VMs.
> > Do you have some thoughts about how to make the above cases work in the

I still need to read this long thread, but just a thought on the word
"restricted" here: for MMIO the instruction can be anywhere and
similarly the load/store MMIO data can be anywhere. Does this mean that
for running unmodified non-CoCo VMs with guest_memfd backend that we'll
always need to have the whole of guest memory mmapped?

I guess the idea is that this use case will still be subject to the
normal restriction rules, but for a non-CoCo non-pKVM VM there will be 
no restriction in practice, and userspace will need to mmap everything
always?

It really seems yucky to need to have all of guest RAM mmapped all the
time just for MMIO to work... But I suppose there is no way around that
for Intel x86.

JG

> 
> [*] https://lore.kernel.org/all/ZdfoR3nCEP3HTtm1@casper.infradead.org

---

## [4] Sean Christopherson — 2024-05-13

On Mon, May 13, 2024, James Gowans wrote:
> On Mon, 2024-05-13 at 08:39 -0700, Sean Christopherson wrote:
> > > Sean, you mentioned that you envision guest_memfd also supporting non-CoCo VMs.

Not necessarily, e.g. KVM could re-establish the direct map or mremap() on-demand.
There are variation on that, e.g. if ASI[*] were to ever make it's way upstream,
which is a huge if, then we could have guest_memfd mapped into a KVM-only CR3.

> I guess the idea is that this use case will still be subject to the
> normal restriction rules, but for a non-CoCo non-pKVM VM there will be 

It's not just MMIO.  Nested virtualization, and more specifically shadowing nested
TDP, is also problematic (probably more so than MMIO).  And there are more cases,
i.e. we'll need a generic solution for this.  As above, there are a variety of
options, it's largely just a matter of doing the work.  I'm not saying it's a
trivial amount of work/effort, but it's far from an unsolvable problem.

---

## [5] Gowans, James — 2024-05-13

On Mon, 2024-05-13 at 10:09 -0700, Sean Christopherson wrote:
> On Mon, May 13, 2024, James Gowans wrote:
> > On Mon, 2024-05-13 at 08:39 -0700, Sean Christopherson wrote:

Yes, on-demand mapping in of guest RAM pages is definitely an option. It
sounds quite challenging to need to always go via interfaces which
demand map/fault memory, and also potentially quite slow needing to
unmap and flush afterwards. 

Not too sure what you have in mind with "guest_memfd mapped into KVM-
only CR3" - could you expand?

> > I guess the idea is that this use case will still be subject to the
> > normal restriction rules, but for a non-CoCo non-pKVM VM there will be

I didn't even think of nested virt, but that will absolutely be an even
bigger problem too. MMIO was just the first roadblock which illustrated
the problem.
Overall what I'm trying to figure out is whether there is any sane path
here other than needing to mmap all guest RAM all the time. Trying to
get nested virt and MMIO and whatever else needs access to guest RAM
working by doing just-in-time (aka: on-demand) mappings and unmappings
of guest RAM sounds like a painful game of whack-a-mole, potentially
really bad for performance too.

Do you think we should look at doing this on-demand mapping, or, for
now, simply require that all guest RAM is mmapped all the time and KVM
be given a valid virtual addr for the memslots?
Note that I'm specifically referring to regular non-CoCo non-enlightened
VMs here. For CoCo we definitely need all the cooperative MMIO and
sharing. What we're trying to do here is to get guest RAM out of the
direct map using guest_memfd, and now tackling the knock-on problem of
whether or not to mmap all of guest RAM all the time in userspace.

JG

---

## [6] Sean Christopherson — 2024-05-13

On Mon, May 13, 2024, James Gowans wrote:
> On Mon, 2024-05-13 at 10:09 -0700, Sean Christopherson wrote:
> > On Mon, May 13, 2024, James Gowans wrote:

Remove guest_memfd from the kernel's direct map, e.g. so that the kernel at-large
can't touch guest memory, but have a separate set of page tables that have the
direct map, userspace page tables, _and_ kernel mappings for guest_memfd.  On
KVM_RUN (or vcpu_load()?), switch to KVM's CR3 so that KVM always map/unmap are
free (literal nops).

That's an imperfect solution as IRQs and NMIs will run kernel code with KVM's
page tables, i.e. guest memory would still be exposed to the host kernel.  And
of course we'd need to get buy in from multiple architecturs and maintainers,
etc.

> > > I guess the idea is that this use case will still be subject to the
> > > normal restriction rules, but for a non-CoCo non-pKVM VM there will be

It's a whack-a-mole game that KVM already plays, e.g. for dirty tracking, post-copy
demand paging, etc..  There is still plenty of room for improvement, e.g. to reduce
the number of touchpoints and thus the potential for missed cases.  But KVM more
or less needs to solve this basic problem no matter what, so I don't think that
guest_memfd adds much, if any, burden.

> Do you think we should look at doing this on-demand mapping, or, for
> now, simply require that all guest RAM is mmapped all the time and KVM

I don't think "map everything into userspace" is a viable approach, precisely
because it requires reflecting that back into KVM's memslots, which in turn
means guest_memfd needs to allow gup().  And I don't think we want to allow gup(),
because that opens a rather large can of worms (see the long thread I linked).

Hmm, a slightly crazy idea (ok, maybe wildly crazy) would be to support mapping
all of guest_memfd into kernel address space, but as USER=1 mappings.  I.e. don't
require a carve-out from userspace, but do require CLAC/STAC when access guest
memory from the kernel.  I think/hope that would provide the speculative execution
mitigation properties you're looking for?

Userspace would still have access to guest memory, but it would take a truly
malicious userspace for that to matter.  And when CPUs that support LASS come
along, userspace would be completely unable to access guest memory through KVM's
magic mapping.

This too would require a decent amount of buy-in from outside of KVM, e.g. to
carve out the virtual address range in the kernel.  But the performance overhead
would be identical to the status quo.  And there could be advantages to being
able to identify accesses to guest memory based purely on kernel virtual address.

---

## [7] Manwaring, Derek — 2024-05-13

On 2024-05-13 13:36-0700, Sean Christopherson wrote:
> Hmm, a slightly crazy idea (ok, maybe wildly crazy) would be to support mapping
> all of guest_memfd into kernel address space, but as USER=1 mappings.  I.e. don't

This is interesting. I'm hesitant to rely on SMAP since it can be
enforced too late by the microarchitecture. But Canella, et al. [1] did
say in 2019 that the kernel->user access route seemed to be free of any
"Meltdown" effects. LASS sounds like it will be even stronger, though
it's not clear to me from Intel's programming reference that speculative
scenarios are in scope [2]. AMD does list SMAP specifically as a
feature that can control speculation [3].

I don't see an equivalent read-access control on ARM. It has PXN for
execute. Read access can probably also be controlled?  But I think for
the non-CoCo case we should favor solutions that are less dependent on
hardware-specific protections.

Derek


[1] https://www.usenix.org/system/files/sec19-canella.pdf
[2] https://cdrdv2.intel.com/v1/dl/getContent/671368
[3] https://www.amd.com/content/dam/amd/en/documents/epyc-technical-docs/tuning-guides/software-techniques-for-managing-speculation.pdf

---
