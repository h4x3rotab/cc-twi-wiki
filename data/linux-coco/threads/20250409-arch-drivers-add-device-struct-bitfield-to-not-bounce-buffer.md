---
title: '[PATCH hyperv-next 5/6] arch, drivers: Add device struct\n bitfield to not bounce-buffer'
date: 2025-04-09
last_reply: 2025-04-10
message_count: 6
participants: ['Dan Williams', 'Michael Kelley', 'Christoph Hellwig', 'Jason Gunthorpe']
---

## [1] Dan Williams — 2025-04-09

[ add linux-coco ]

Roman Kisel wrote:
> 
> 

One would hope that no one is building a modern device with trusted I/O
capability, *and* with a swiotlb addressing dependency. However, I agree
that a non-shared swiotlb would be needed in such a scenario.

Otherwise the policy around "a device should not even be allowed to
bounce buffer any private page" is a userspace responsibility to either
not load the driver, not release secrets to this CVM, or otherwise make
sure the device is only ever bounce buffering private memory that does
not contain secrets.

> > Also whatever we do for this really wants to tie in with the nascent 
> > TDISP stuff as well, since we definitely don't want to end up with more 

The name and location of a flag bit is not the issue, it is the common
expectation of how and when that flag is set.

tl;dr Linux likely needs a "private_accepted" flag for devices

Like Christoph said, a driver really has no business opting itself into
different DMA addressing domains. For TDISP we are also being careful to
make sure that flipping a device from shared to private is a suitably
violent event. This is because the Linux DMA layer does not have a
concept of allowing a device to have mappings from two different
addressing domains simultaneously.

In the current TDISP proposal, a device starts in shared mode and only
after validating all of the launch state of the CVM, device
measurements, and a device interface report is it granted access to
private memory. Without dumping a bunch of golden measurement data into
the kernel that validation can really only be performed by userspace.

Enter this vmbus proposal that wants to emulate devices with a paravisor
that is presumably within the TCB at launch, but the kernel can not
really trust that until a "launch state of the CVM + paravisor"
attestation event.

Like PCIe TDISP the capability of this device to access private memory
is a property of the bus and the iommu. However, acceptance of the
device into private operation is a willful policy action. It needs to
validate not only the device provenance and state, but also the Linux
DMA layer requirements of not holding shared or swiotlb mappings over
the "entry into private mode operation" event.

All that said, I would advocate to require a userspace driven "device
accept" event for all devices, not just TDISP, that want to enter
private operation. Maybe later circle back to figure out if there is a
lingering need for accepting devices via golden measurement, or other
means, to skip the userpace round-trip dependency.

A "private_capable" flag might also make sense, but that is really a
property of a bus that need not be carried necessarily in 'struct
device'.

So for this confidential vmbus SCSI device to mesh with the mechanisms
needed for TDISP I would expect it continues to launch in swiotlb mode
by default. Export an attribute via hv_bus->dev_groups to indicate that
the device is "private_capable" and then require userspace to twiddle a
private_accepted flag with some safety for in-flight DMA.

---

## [2] Michael Kelley — 2025-04-10
*Subject: RE: [PATCH hyperv-next 5/6] arch, drivers: Add device struct bitfield
 to not bounce-buffer*

From: Dan Williams <dan.j.williams@intel.com> Sent: Wednesday, April 9, 2025 4:30 PM
> 
> [ add linux-coco ]

To flesh this out the swiotlb aspect a bit, once a TDISP device has
gone private, how does it prevent the DMA layer from ever doing
bounce buffering through the swiotlb? My understanding is that
the DMA layer doesn't make any promises to not do bounce buffering.
Given the vagaries of memory alignment, perhaps add in a virtual
IOMMU, etc., it seems like a device driver can't necessarily predict
what DMA operations might result in bounce buffering. Does TDISP
anticipate needing a formal way to tell the DMA layer "don't bounce
buffer"? (and return an error instead?) Or would there be a separate
swiotlb memory pool that is private memory so that bounce buffer
could be done when necessary and still maintain confidentiality?

Just wondering if there's any thinking on this topic ...

Thanks,

Michael

---

## [3] Christoph Hellwig — 2025-04-10

On Wed, Apr 09, 2025 at 04:30:17PM -0700, Dan Williams wrote:
> > Thanks, I should've highlighted that facet most certainly!
> 

Hope is never a good idea when dealing with hardware :(  PCIe already
requires no addressing limitations, and programming interface specs
like NVMe double down on that.  But at least one big hyperscaler still
managed to build such a device.

Also even if the periphal device is not addressing limited, the root
port or interconnect might still be, we've seen quite a lot of that.

---

## [4] Jason Gunthorpe — 2025-04-10

On Thu, Apr 10, 2025 at 09:23:54AM +0200, Christoph Hellwig wrote:
> On Wed, Apr 09, 2025 at 04:30:17PM -0700, Dan Williams wrote:
> > > Thanks, I should've highlighted that facet most certainly!

Still it would be very obnoxious for someone to build a CC VM platform
where CC DMA devices can't access all the guest physical memory in the
CC address map :\

Keeping in mind that that the CC address map is being created by using
the CPU MMU and the CPU IOMMU so it is entirely virtual and can be
configured to match most problems the devices might have.

Too much memory would be the main issue..

IMHO I wouldn't implement secure SWIOTLB until someone does such a
foolish thing, and I'd make them do the work as some kind of pennance
:P

Jason

---

## [5] Jason Gunthorpe — 2025-04-10

On Wed, Apr 09, 2025 at 04:30:17PM -0700, Dan Williams wrote:

> Like Christoph said, a driver really has no business opting itself into
> different DMA addressing domains. For TDISP we are also being careful to

And this is a very important point, several of the architectures have
two completely independent iommu tables, and maybe even completely
different IOMMU instances for trusted and non-trusted DMA traffic.

I expect configurations where trusted traffic is translated through
the vIOMMU while non-trusted traffic is locked to an identity
translation.

There are more issue here than just swiotlb :\

> A "private_capable" flag might also make sense, but that is really a
> property of a bus that need not be carried necessarily in 'struct

However it works, it should be done before the driver is probed and
remain stable for the duration of the driver attachment. From the
iommu side the correct iommu domain, on the correct IOMMU instance to
handle the expected traffic should be setup as the DMA API's iommu
domain.

Jason

---

## [6] Dan Williams — 2025-04-10
*Subject: RE: [PATCH hyperv-next 5/6] arch, drivers: Add device struct
 bitfield to not bounce-buffer*

Michael Kelley wrote:
> From: Dan Williams <dan.j.williams@intel.com> Sent: Wednesday, April 9, 2025 4:30 PM
[..]
> > Like PCIe TDISP the capability of this device to access private memory
> > is a property of the bus and the iommu. However, acceptance of the

I expect step 1 is just add some rude errors / safety for attempting to
convert the mode of a device while it has any DMA mappings established,
and explicit failures for attempts to fallback to swiotlb for
'private_accepted' devices.

The easiest way to enforce that a device does not cross the
shared/private boundary while DMA mappings are live is to simply not
allow that transition while a driver is bound (i.e. "dev->driver" is
non-NULL).

---
