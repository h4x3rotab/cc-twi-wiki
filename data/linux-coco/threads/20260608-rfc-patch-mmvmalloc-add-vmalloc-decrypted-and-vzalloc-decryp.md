---
title: '[RFC PATCH] mm/vmalloc: add vmalloc_decrypted() and\n vzalloc_decrypted()'
date: 2026-06-08
last_reply: 2026-06-16
message_count: 8
participants: ['Catalin Marinas', 'Jason Gunthorpe', 'Michael Kelley']
---

## [1] Catalin Marinas — 2026-06-08

+ linux-coco, Suzuki (for the arm64 behaviour)

On Thu, May 21, 2026 at 01:58:34PM -0700, Kameron Carr wrote:
> In confidential computing environments (arm64 CCA, x86 SEV/TDX), guest
> memory is encrypted by default and must be explicitly transitioned to a

There are a few Sashiko comments worth reviewing:

https://sashiko.dev/#/patchset/20260521205834.1012925-1-kameroncarr@linux.microsoft.com

[...]
> +/*
> + * Re-encrypt the linear-map alias of all pages backing a VM_DECRYPTED area.

I think we still have the vmalloc aliases at this point as we lazily
reclaim them. We should call vm_unmap_aliases() before
vm_pages_encrypt(). It matches the x86 __set_memory_enc_pgtable() as
well with the explicit call to vm_unmap_aliases().

The vrealloc() path may have some issues as well but I haven't looked in
detail. Not sure it actually re-allocs decrypted pages. The simplest is
to reject vrealloc() for such vms until we have a use-case.

> +/**
> + * vzalloc_decrypted - allocate zeroed virtually contiguous decrypted memory

Talking to Suzuki, the small window between set_memory_decrypted() and
memset() potentially exposing stale data is safe, at least for Arm CCA
as the memory would be scrubbed (there are other places in the kernel
where we do something similar). I assume that's also the case for other
architectures, although not sure what pKVM does.

---

## [2] Jason Gunthorpe — 2026-06-11

On Mon, Jun 08, 2026 at 04:37:02PM +0100, Catalin Marinas wrote:
> > +/**
> > + * vzalloc_decrypted - allocate zeroed virtually contiguous decrypted memory

It seems like a poor practice though, this should probably be
re-organized to use __GFP_ZERO so things are ordered sensibly.

But what is the purpose of this? I guess some hyperv thing - but
shouldn't we have a more structured way to "DMA map" things for the
hypervisor instead of stuff like this? Why can't you use
dma_alloc_coherent() which actually gives you an address that is
sensible to pass to the hypervisor?

Jason

---

## [3] Catalin Marinas — 2026-06-12

On Thu, Jun 11, 2026 at 08:49:54AM -0300, Jason Gunthorpe wrote:
> On Mon, Jun 08, 2026 at 04:37:02PM +0100, Catalin Marinas wrote:
> > > +/**

__GFP_ZERO doesn't work if the intermediate set_memory_decrypted()
mangles the data (e.g. changes encryption keys) and it no longer reads
as zeros.

> But what is the purpose of this? I guess some hyperv thing - but
> shouldn't we have a more structured way to "DMA map" things for the

IIRC netvsc_init_buf() uses vzalloc() to allocate some memory and that
buffer ends up in set_memory_decrypted() via vmbus_establish_gpadl().
arm64 does not support changing the decrypted/shared attributed of
vmalloc mappings and I don't think we should add it. Better to just
allocate it properly upfront.

We might be able to use the DMA API but we won't get something like
vmalloc() - physically non-contiguous. I think dma_alloc_noncontiguous()
just falls back to dma_direct_alloc_pages() in the absence of an iommu.

---

## [4] Jason Gunthorpe — 2026-06-12

On Fri, Jun 12, 2026 at 06:49:28PM +0100, Catalin Marinas wrote:
> On Thu, Jun 11, 2026 at 08:49:54AM -0300, Jason Gunthorpe wrote:
> > On Mon, Jun 08, 2026 at 04:37:02PM +0100, Catalin Marinas wrote:

I thought arches are either preserving the memory content or zeroing
it, you are saying some arch leaves it as garbage? I'd argue that's an
arch bug and they should clear it in their path.

Otherwise this sharp edge is not documented and we have many other
places getting it wrong, eg system_heap_allocate() doesn't re-zero the
memory after decrypting it.

> > But what is the purpose of this? I guess some hyperv thing - but
> > shouldn't we have a more structured way to "DMA map" things for the

Sure
 
> We might be able to use the DMA API but we won't get something like
> vmalloc() - physically non-contiguous. 

The entry point is dma_alloc_noncontiguous() and you get a scatterlist
back.

> I think dma_alloc_noncontiguous() just falls back to
> dma_direct_alloc_pages() in the absence of an iommu.

In all cases you get a scatterlist with a CPU list and a DMA
list. iommu gives a smaller DMA list.

If you want a vmap then you can feed that CPU page list from the sgl
into vmap().

A dma_alloc_noncontiguous_vmap() helper would not be hard to make, and
IMHO, would make alot more sense for hyperv to treat the memory access
from the hypervisor as "DMA" instead of trying to re-invent the DMA
API.. :\

HCH was already saying we should not be allowing drivers to use
set_memory_decrypted() at all, and hyperv is the biggest non-core user
right now...

Jason

---

## [5] Michael Kelley — 2026-06-12
*Subject: RE: [RFC PATCH] mm/vmalloc: add vmalloc_decrypted() and
 vzalloc_decrypted()*

From: Jason Gunthorpe <jgg@ziepe.ca> Sent: Friday, June 12, 2026 11:18 AM
> 
> On Fri, Jun 12, 2026 at 06:49:28PM +0100, Catalin Marinas wrote:

AMD SEV-SNP leaves the memory contents as garbage after an encryption
or decryption state change. On the flip side, my understanding has been
that TDX zeroes the memory (or at least has an option to do so) after
such a state change, though a couple of AI chats say TDX also leaves
garbage. To be sure, I'd have to run an experiment to check in a TDX
guest on Hyper-V.

> 
> Otherwise this sharp edge is not documented and we have many other

In the Hyper-V code that uses set_memory_decrypted()/encrypted(),
there's always an explicit call to set the memory to zero afterwards.

Michael

> 
> > > But what is the purpose of this? I guess some hyperv thing - but

---

## [6] Jason Gunthorpe — 2026-06-15

On Fri, Jun 12, 2026 at 07:06:00PM +0000, Michael Kelley wrote:

> > I thought arches are either preserving the memory content or zeroing
> > it, you are saying some arch leaves it as garbage? I'd argue that's an

So there are many bugs then if the pre-zero is lost and you have to
zero it again. Even swiotlb doesn't reliably zero it's pools in the
right order under these rules, though alloc coherent does get it
right at least.

IMHO this is too sketchy to be usable and optimizing for AMD is not
the right call, IMHO.

> > Otherwise this sharp edge is not documented and we have many other
> > places getting it wrong, eg system_heap_allocate() doesn't re-zero the

Good for it, maybe next time improve the APIs :(

Even more compelling that hyper-v should be using the dma api..

Jason

---

## [7] Catalin Marinas — 2026-06-16

On Fri, Jun 12, 2026 at 03:18:07PM -0300, Jason Gunthorpe wrote:
> On Fri, Jun 12, 2026 at 06:49:28PM +0100, Catalin Marinas wrote:
> > On Thu, Jun 11, 2026 at 08:49:54AM -0300, Jason Gunthorpe wrote:
[...]
> > > But what is the purpose of this? I guess some hyperv thing - but
> > > shouldn't we have a more structured way to "DMA map" things for the

Yes but not scattered pages unless there's an iommu behind. Anyway,
that's an implementation detail, something like
dma_alloc_noncontiguous_vmap() could allocate scattered pages as a
fallback.

> > I think dma_alloc_noncontiguous() just falls back to
> > dma_direct_alloc_pages() in the absence of an iommu.

That's a good aim longer term. I'm not familiar with hyper-v but I think
it needs a mix of private or shared allocations depending on whether a
paravisor is present. That's handled by the vmbus code and the
information is encoded in the vmbus_channel objects.

Currently, something like netvsc_init_buf() just does a vzalloc() and
passes it down to vmbus_establish_gpadl() which knows how to interpret
the channel encryption status. I assume with the vzalloc_decrypted()
API, that info needs to be interpreted at the netvsc_init_buf() level to
know which allocation to call.

If we move towards a dma_alloc_noncontiguous_vmap() API we need vmbus to
encode the encryption requirement in the hv_device::device somehow so
that force_dma_unencrypted() knows what do return. We have the
DMA_ATTR_CC_SHARED but that's not interpreted on the DMA alloc path, so
there's a bit more work needed on the DMA API I think (not sure whether
Aneesh's series covers any of this).

---

## [8] Jason Gunthorpe — 2026-06-16

On Tue, Jun 16, 2026 at 07:17:33PM +0100, Catalin Marinas wrote:

> > The entry point is dma_alloc_noncontiguous() and you get a scatterlist
> > back.

Oh I never noticed it deliberately returns only a single dma entry. I
think that could be optionally weakened without alot of trouble

There is also dma_vmap_noncontiguous() already, so I think the main
framework is there, though it seems like it needs a a bit mmore features.

> Currently, something like netvsc_init_buf() just does a vzalloc() and
> passes it down to vmbus_establish_gpadl() which knows how to interpret

But it doesn't end at alloc does it? hyperv will still have to reach
into the vmap and convert it into an appropriate IPA to pass to the
hypervisor. That really needs to use the arch helpers the DMA API has
and those should not be called by any sort of driver environment like
hyperv.

> If we move towards a dma_alloc_noncontiguous_vmap() API we need vmbus to
> encode the encryption requirement in the hv_device::device somehow so

Yes, they would have to act like PCI and mark in-TEE and out of-TEE
struct devices properly so the DMA API knows what to do instead of
open coding a copy of all this logic in hyperv.

> We have the DMA_ATTR_CC_SHARED but that's not interpreted on the DMA
> alloc path, 

It is to describe memory that was deliberately allocated as decrypted,
not to control allocation choices.

> so there's a bit more work needed on the DMA API I think (not sure
> whether Aneesh's series covers any of this).

I don't think it does directly. It largely sets the stage to properly
allow a struct device to opt out of force_dma_unencrypted() so we get
support a T=1 PCI device.

Jason

---
