---
title: '[RFC PATCH 00/12] Private MMIO support for private assigned dev'
date: 2025-05-09
last_reply: 2026-05-07
message_count: 42
participants: ['Alexey Kardashevskiy', 'Xu Yilun', 'Jason Gunthorpe', 'Zhi Wang', 'Baolu Lu']
---

## [1] Alexey Kardashevskiy — 2025-05-09

Ping?
Also, since there is pushback on 01/12 "dma-buf: Introduce dma_buf_get_pfn_unlocked() kAPI", what is the plan now? Thanks,


On 29/4/25 17:50, Alexey Kardashevskiy wrote:
> 
> 

> 
>

---

## [2] Xu Yilun — 2025-05-09

On Fri, May 09, 2025 at 01:04:58PM +1000, Alexey Kardashevskiy wrote:
> Ping?

Sorry for late reply from vacation.

> Also, since there is pushback on 01/12 "dma-buf: Introduce dma_buf_get_pfn_unlocked() kAPI", what is the plan now? Thanks,

As disscussed in the thread, this kAPI is not well considered but IIUC
the concept of "importer mapping" is still valid. We need more
investigation about all the needs - P2P, CC memory, private bus
channel, and work out a formal API.

However in last few months I'm focusing on high level TIO flow - TSM
framework, IOMMUFD based bind/unbind, so no much progress here and is
still using this temporary kAPI. But as long as "importer mapping" is
alive, the dmabuf fd for KVM is still valid and we could enable TIO
based on that.

> 
> 

Sorry, not yet. I'm trying to solve this ... same for the QEMU tree.

> > > Also, is there somewhere a QEMU tree using this? I am trying to use this new DMA_BUF feature and this require quite some not so obvious plumbing. Thanks,
> > 

Yes, QEMU needs change. 08/12 "vfio/pci: Create host unaccessible dma-buf for private device“
adds a new flag VFIO_REGION_INFO_FLAG_PRIVATE to indicate user could
create dmabuf on this region.

I'm also not very serious about QEMU changes now, just FYI:

I use VFIO_REGION_INFO_FLAG_PRIVATE flag to revive region->mmaps.

int vfio_region_setup(Object *obj, VFIODevice *vbasedev, VFIORegion *region,
	...

+        if (region->flags & VFIO_REGION_INFO_FLAG_PRIVATE) {
+            region->nr_mmaps = 1;
+            region->mmaps = g_new0(VFIOMmap, region->nr_mmaps);
+            region->mmaps[0].offset = 0;
+            region->mmaps[0].size = region->size;
+            region->mmaps[0].dmabuf_fd = -1;
         }

Then in vfio_region_mmap(), use a new memory_region_init_dmabuf() to populate
the MR.

int vfio_region_mmap(VFIORegion *region)

+        if (use_dmabuf) {
+            /* create vfio dmabuf fd */
+            ret = vfio_create_dmabuf(region->vbasedev, region->nr,
+                                     region->mmaps[i].offset,
+                                     region->mmaps[i].size);
+            if (ret < 0) {
+                goto sub_unmap;
+            }
+
+            region->mmaps[i].dmabuf_fd = ret;
+
+            name = g_strdup_printf("%s dmabuf[%d]",
+                                   memory_region_name(region->mem), i);
+            memory_region_init_dmabuf(&region->mmaps[i].mem,
+                                             memory_region_owner(region->mem),
+                                             name, region->mmaps[i].size,
+                                             region->mmaps[i].dmabuf_fd);
+            g_free(name);
+        } else {

Thanks,
Yilun

---

## [3] Xu Yilun — 2025-05-10

On Fri, May 09, 2025 at 07:12:46PM +0800, Xu Yilun wrote:
> On Fri, May 09, 2025 at 01:04:58PM +1000, Alexey Kardashevskiy wrote:
> > Ping?

Oh I forgot to mention I moved the dmabuf creation from VFIO to IOMMUFD
recently, the IOCTL is against iommufd_device. According to Jason's
opinion [1], TSM bind/unbind should be called against iommufd_device,
then I need to do the same for dmabuf.  This is because Intel TDX
Connect enforces a specific operation sequence between TSM unbind & MMIO
unmap:

  1. STOP TDI via TDISP message STOP_INTERFACE
  2. Private MMIO unmap from Secure EPT
  3. Trusted Device Context Table cleanup for the TDI
  4. TDI ownership reclaim and metadata free

That makes TSM unbind & dmabuf closely correlated and should be managed
by the same kernel component.

IIUC, the suggested flow is VFIO receives a CC capable flag and propagate
to IOMMUFD, which means VFIO hand over device's MMIO management & CC
management to IOMMUFD.

[1]: https://lore.kernel.org/all/20250306182614.GF354403@ziepe.ca/

Thanks,
Yilun

---

## [4] Jason Gunthorpe — 2025-05-09

On Sat, May 10, 2025 at 12:28:48AM +0800, Xu Yilun wrote:
> On Fri, May 09, 2025 at 07:12:46PM +0800, Xu Yilun wrote:
> > On Fri, May 09, 2025 at 01:04:58PM +1000, Alexey Kardashevskiy wrote:

I'm surprised by this.. iommufd shouldn't be doing PCI stuff, it is
just about managing the translation control of the device.

> According to Jason's
> opinion [1], TSM bind/unbind should be called against iommufd_device,

So your issue is you need to shoot down the dmabuf during vPCI device
destruction?

VFIO also needs to shoot down the MMIO during things like FLR

I don't think moving to iommufd really fixes it, it sounds like you
need more coordination between the two parts??

Jason

---

## [5] Xu Yilun — 2025-05-10

On Fri, May 09, 2025 at 03:43:18PM -0300, Jason Gunthorpe wrote:
> On Sat, May 10, 2025 at 12:28:48AM +0800, Xu Yilun wrote:
> > On Fri, May 09, 2025 at 07:12:46PM +0800, Xu Yilun wrote:

I have a little difficulty to understand. Is TSM bind PCI stuff? To me
it is. Host sends PCI TDISP messages via PCI DOE to put the device in
TDISP LOCKED state, so that device behaves differently from before. Then
why put it in IOMMUFD?

Or "managing the translation control" means IOMMUFD provides the TSM
bind/unbind uAPI and call into VFIO driver for real TSM bind
implementation?

> 
> > According to Jason's

I assume "vPCI device" refers to assigned device in both shared mode &
prvate mode. So no, I need to shoot down the dmabuf during TSM unbind,
a.k.a. when assigned device is converting from private to shared.
Then recover the dmabuf after TSM unbind. The device could still work
in VM in shared mode. 

> 
> VFIO also needs to shoot down the MMIO during things like FLR

Yes, when moving to iommufd, VFIO needs extra kAPIs to inform IOMMUFD
about the shooting down. But FLR or MSE toggle also breaks TSM bind
state. As long as we put TSM bind in IOMMUFD, anyway the coordination
is needed.

What I really want is, one SW component to manage MMIO dmabuf, secure
iommu & TSM bind/unbind. So easier coordinate these 3 operations cause
these ops are interconnected according to secure firmware's requirement.
Otherwise e.g. for TDX, when device is TSM bound (IOMMUFD controls
bind) and VFIO wants FLR, VFIO revokes dmabuf first then explode.

Safe way is one SW component manages all these "pre-FLR" stuffs, let's say
IOMMUFD, it firstly do TSM unbind, let the platform TSM driver decides
the correct operation sequence (TDISP, dmabuf for private MMIO mapping,
secure dma). After TSM unbind, it's a shared device and IOMMUFD have no
worry to revoke dmabuf as needed.

Maybe I could send a patchset to illustrate...

Thanks,
Yilun

> 
> Jason

---

## [6] Alexey Kardashevskiy — 2025-05-12

On 10/5/25 13:47, Xu Yilun wrote:
> On Fri, May 09, 2025 at 03:43:18PM -0300, Jason Gunthorpe wrote:
>> On Sat, May 10, 2025 at 12:28:48AM +0800, Xu Yilun wrote:


"TSM bind" sets up the CPU side of it, it binds a VM to a piece of IOMMU on the host CPU. The device does not know about the VM, it just enables/disables encryption by a request from the CPU (those start/stop interface commands). And IOMMUFD won't be doing DOE, the platform driver (such as AMD CCP) will. Nothing to do for VFIO here.

We probably should notify VFIO about the state transition but I do not know VFIO would want to do in response.


> Or "managing the translation control" means IOMMUFD provides the TSM
> bind/unbind uAPI and call into VFIO driver for real TSM bind


This SW component is QEMU. It knows about FLRs and other config space things, it can destroy all these IOMMUFD objects and talk to VFIO too, I've tried, so far it is looking easier to manage. Thanks,


> Otherwise e.g. for TDX, when device is TSM bound (IOMMUFD controls
> bind) and VFIO wants FLR, VFIO revokes dmabuf first then explode.

---

## [7] Jason Gunthorpe — 2025-05-12

On Mon, May 12, 2025 at 07:30:21PM +1000, Alexey Kardashevskiy wrote:

> > > I'm surprised by this.. iommufd shouldn't be doing PCI stuff, it is
> > > just about managing the translation control of the device.

We have an awkward fit for what CCA people are doing to the various
Linux APIs. Looking somewhat maximally across all the arches a "bind"
for a CC vPCI device creation operation does:

 - Setup the CPU page tables for the VM to have access to the MMIO
 - Revoke hypervisor access to the MMIO
 - Setup the vIOMMU to understand the vPCI device
 - Take over control of some of the IOVA translation, at least for T=1,
   and route to the the vIOMMU
 - Register the vPCI with any attestation functions the VM might use
 - Do some DOE stuff to manage/validate TDSIP/etc

So we have interactions of things controlled by PCI, KVM, VFIO, and
iommufd all mushed together.

iommufd is the only area that already has a handle to all the required
objects:
 - The physical PCI function
 - The CC vIOMMU object
 - The KVM FD
 - The CC vPCI object

Which is why I have been thinking it is the right place to manage
this.

It doesn't mean that iommufd is suddenly doing PCI stuff, no, that
stays in VFIO.

> > > So your issue is you need to shoot down the dmabuf during vPCI device
> > > destruction?

What are you trying to protect with this? Is there some intelism where
you can't have references to encrypted MMIO pages?

> > What I really want is, one SW component to manage MMIO dmabuf, secure
> > iommu & TSM bind/unbind. So easier coordinate these 3 operations cause

Yes, qemu should be sequencing this. The kernel only needs to enforce
any rules required to keep the system from crashing.

Jason

---

## [8] Zhi Wang — 2025-05-13

On Mon, 12 May 2025 11:06:17 -0300
Jason Gunthorpe <jgg@nvidia.com> wrote:

> On Mon, May 12, 2025 at 07:30:21PM +1000, Alexey Kardashevskiy wrote:
> 

I think it is a matter of design choice. The encrypted MMIO page is
related to the TDI context and secure second level translation table
(S-EPT). and S-EPT is related to the confidential VM's context.

AMD and ARM have another level of HW control, together
with a TSM-owned meta table, can simply mask out the access to those
encrypted MMIO pages. Thus, the life cycle of the encrypted mappings in
the second level translation table can be de-coupled from the TDI
unbound. They can be reaped un-harmfully later by hypervisor in another
path.

While on Intel platform, it doesn't have that additional level of
HW control by design. Thus, the cleanup of encrypted MMIO page mapping
in the S-EPT has to be coupled tightly with TDI context destruction in
the TDI unbind process.

If the TDI unbind is triggered in VFIO/IOMMUFD, there has be a
cross-module notification to KVM to do cleanup in the S-EPT.

So shooting down the DMABUF object (encrypted MMIO page) means shooting
down the S-EPT mapping and recovering the DMABUF object means
re-construct the non-encrypted MMIO mapping in the EPT after the TDI is
unbound. 

Z.

> > > What I really want is, one SW component to manage MMIO dmabuf,
> > > secure iommu & TSM bind/unbind. So easier coordinate these 3

---

## [9] Xu Yilun — 2025-05-14

On Mon, May 12, 2025 at 07:30:21PM +1000, Alexey Kardashevskiy wrote:
> 
> 

I didn't fully get your idea, are you defending for "TSM bind is NOT PCI
stuff"? To me it is not true.

TSM bind also sets up the device side. From your patch, it calls
tsm_tdi_bind(), which in turn calls spdm_forward(), I assume it is doing
TDISP LOCK. And TDISP LOCK changes device a lot.

> The device does not know about the VM, it just enables/disables encryption by a request from the CPU (those start/stop interface commands).
> And IOMMUFD won't be doing DOE, the platform driver (such as AMD CCP) will. Nothing to do for VFIO here.

IOMMUFD calls tsm_tdi_bind(), which is an interface doing PCI stuff.

Thanks,
Yilun

> 
> We probably should notify VFIO about the state transition but I do not know VFIO would want to do in response.

---

## [10] Xu Yilun — 2025-05-14

On Mon, May 12, 2025 at 11:06:17AM -0300, Jason Gunthorpe wrote:
> On Mon, May 12, 2025 at 07:30:21PM +1000, Alexey Kardashevskiy wrote:
> 

This is guest side thing, is it? Anything host need to opt-in?

>  - Revoke hypervisor access to the MMIO

VFIO could choose never to mmap MMIO, so in this case nothing to do?

>  - Setup the vIOMMU to understand the vPCI device
>  - Take over control of some of the IOVA translation, at least for T=1,

Intel TDX Connect has a extra requirement for "unbind":

- Revoke KVM page table (S-EPT) for the MMIO only after TDISP
  CONFIG_UNLOCK

Another thing is, seems your term "bind" includes all steps for
shared -> private conversion. But in my mind, "bind" only includes
putting device in TDISP LOCK state & corresponding host setups required
by firmware. I.e "bind" means host lockes down the CC setup, waiting for
guest attestation.

While "unbind" means breaking CC setup, no matter the vPCI device is
already accepted as CC device, or only locked and waiting for attestation.

> 
> So we have interactions of things controlled by PCI, KVM, VFIO, and

Yeah, I see the merit.

> 
> It doesn't mean that iommufd is suddenly doing PCI stuff, no, that

I'm not sure if Alexey's patch [1] illustates your idea. It calls
tsm_tdi_bind() which directly does device stuff, and impacts MMIO.
VFIO doesn't know about this.

I have to interpret this as VFIO firstly hand over device CC features
and MMIO resources to IOMMUFD, so VFIO never cares about them.

[1] https://lore.kernel.org/all/20250218111017.491719-15-aik@amd.com/

> 
> > > > So your issue is you need to shoot down the dmabuf during vPCI device

To keep from crashing, The kernel still needs to enforce some firmware
specific rules. That doesn't reduce the interactions between kernel
components. E.g. for TDX, if VFIO doesn't control "bind" but controls
MMIO, it should refuse FLR or MSE when device is bound. That means VFIO
should at least know from IOMMUFD whether device is bound.

Further more, these rules are platform firmware specific, "QEMU executes
kernel checks" means more SW components should be aware of these rules.
That multiples the effort.

And QEMU can be killed, means if kernel wants to reclaim all the
resources, it still have to deal with the sequencing. And I don't think
it is a good idea that kernel just stales large amount of resources.

Thanks,
Yilun
> 
> Jason

---

## [11] Xu Yilun — 2025-05-14

On Tue, May 13, 2025 at 01:03:15PM +0300, Zhi Wang wrote:
> On Mon, 12 May 2025 11:06:17 -0300
> Jason Gunthorpe <jgg@nvidia.com> wrote:

Thanks for the accurate explanation. Yes, in TDX, the references/mapping
to the encrypted MMIO page means a CoCo-VM owns the MMIO page. So TDX
firmware won't allow the CC vPCI device (which physically owns the MMIO
page) unbind/freed from a CoCo-VM, while the VM still have the S-EPT mapping.

AMD doesn't use KVM page table to track CC ownership, so no need to
interact with KVM.

Thanks,
Yilun

> 
> If the TDI unbind is triggered in VFIO/IOMMUFD, there has be a

---

## [12] Jason Gunthorpe — 2025-05-14

On Wed, May 14, 2025 at 03:02:53PM +0800, Xu Yilun wrote:
> > We have an awkward fit for what CCA people are doing to the various
> > Linux APIs. Looking somewhat maximally across all the arches a "bind"

CPU hypervisor page tables.

> >  - Revoke hypervisor access to the MMIO
> 

Yes, if you do it that way.
 
> >  - Setup the vIOMMU to understand the vPCI device
> >  - Take over control of some of the IOVA translation, at least for T=1,

Maybe you could express this as the S-EPT always has the MMIO mapped
into it as long as the vPCI function is installed to the VM? Is KVM
responsible for the S-EPT?

> Another thing is, seems your term "bind" includes all steps for
> shared -> private conversion. 

Well, I was talking about vPCI creation. I understand that during the
vPCI lifecycle the VM will do "bind" "unbind" which are more or less
switching the device into a T=1 mode. Though I understood on some
arches this was mostly invisible to the hypervisor?

> But in my mind, "bind" only includes
> putting device in TDISP LOCK state & corresponding host setups required

So we will need to have some other API for this that modifies the vPCI
object.

It might be reasonable to have VFIO reach into iommufd to do that on
an already existing iommufd VDEVICE object. A little weird, but we
could probably make that work.

But you have some weird ordering issues here if the S-EPT has to have
the VFIO MMIO then you have to have a close() destruction order that
sees VFIO remove the S-EPT and release the KVM, then have iommufd
destroy the VDEVICE object.

> > It doesn't mean that iommufd is suddenly doing PCI stuff, no, that
> > stays in VFIO.

There is also the PCI layer involved here and maybe PCI should be
participating in managing some of this. Like it makes a bit of sense
that PCI would block the FLR on platforms that require this?

Jason

---

## [13] Zhi Wang — 2025-05-14

On Wed, 14 May 2025 17:47:12 +0800
Xu Yilun <yilun.xu@linux.intel.com> wrote:

> On Tue, May 13, 2025 at 01:03:15PM +0300, Zhi Wang wrote:
> > On Mon, 12 May 2025 11:06:17 -0300

IMHO, I think it might be helpful that you can picture out what are the
minimum requirements (function/life cycle) to the current IOMMUFD TSM
bind architecture:

1.host tsm_bind (preparation) is in IOMMUFD, triggered by QEMU handling
the TVM-HOST call.
2. TDI acceptance is handled in guest_request() to accept the TDI after
the validation in the TVM)

and which part/where need to be modified in the current architecture to
reach there. Try to fold vendor-specific knowledge as much as possible,
but still keep them modular in the TSM driver and let's see how it looks
like. Maybe some example TSM driver code to demonstrate together with
VFIO dma-buf patch.

If some where is extremely hacky in the TSM driver, let's see how they
can be lift to the upper level or the upper call passes more parameters
to them.

Z.

> Thanks,
> Yilun

---

## [14] Alexey Kardashevskiy — 2025-05-15

On 13/5/25 20:03, Zhi Wang wrote:
> On Mon, 12 May 2025 11:06:17 -0300
> Jason Gunthorpe <jgg@nvidia.com> wrote:

QEMU should know about this unbind and can tell KVM about it too. No cross module notification needed, it is not a hot path.


> So shooting down the DMABUF object (encrypted MMIO page) means shooting
> down the S-EPT mapping and recovering the DMABUF object means

This is definitely QEMU's job to re-mmap MMIO to the userspace (as it does for non-trusted devices today) so later on nested page fault could fill the nested PTE. Thanks,


> 
> Z.

---

## [15] Xu Yilun — 2025-05-16

On Wed, May 14, 2025 at 01:33:39PM -0300, Jason Gunthorpe wrote:
> On Wed, May 14, 2025 at 03:02:53PM +0800, Xu Yilun wrote:
> > > We have an awkward fit for what CCA people are doing to the various

Yeah.

> Is KVM responsible for the S-EPT?

Yes.

> 
> > Another thing is, seems your term "bind" includes all steps for

I want to introduce some terms about CC vPCI.

1. "Bind", guest requests host do host side CC setup & put device in
CONFIG_LOCKED state, waiting for attestation. Any further change which
has secuity concern breaks "bind", e.g. reset, touch MMIO, physical MSE,
BAR addr...

2. "Attest", after "bind", guest verifies device evidences (cert,
measurement...).

3. "Accept", after successful attestation, guest do guest side CC setup &
switch the device into T=1 mode (TDISP RUN state)

4. "Unbind", guest requests host put device in CONFIG_UNLOCK state +
remove all CC setup.

> arches this was mostly invisible to the hypervisor?

Attest & Accept can be invisible to hypervisor, or host just help pass
data blobs between guest, firmware & device.

Bind cannot be host agnostic, host should be aware not to touch device
after Bind.

> 
> > But in my mind, "bind" only includes

IIUC, in Alexey's patch ioctl(iommufd, IOMMU_VDEVICE_TSM_BIND) does the
"Bind" thing in host.

> 
> It might be reasonable to have VFIO reach into iommufd to do that on

Mm, Are you proposing an uAPI in VFIO, and a kAPI from VFIO -> IOMMUFD like:

 ioctl(vfio_fd, VFIO_DEVICE_ATTACH_VDEV, vdev_id)
 -> iommufd_device_attach_vdev()
    -> tsm_tdi_bind()

> 
> But you have some weird ordering issues here if the S-EPT has to have

Yeah, by holding kvm reference.

> sees VFIO remove the S-EPT and release the KVM, then have iommufd
> destroy the VDEVICE object.

Regarding VM destroy, TDX Connect has more enforcement, VM could only be
destroyed after all assigned CC vPCI devices are destroyed.

Nowadays, VFIO already holds KVM reference, so we need

close(vfio_fd)
-> iommufd_device_detach_vdev()
   -> tsm_tdi_unbind()
      -> tdi stop
      -> callback to VFIO, dmabuf_move_notify(revoke)
         -> KVM unmap MMIO
      -> tdi metadata remove
-> kvm_put_kvm()
   -> kvm_destroy_vm()


> 
> > > It doesn't mean that iommufd is suddenly doing PCI stuff, no, that

FLR to a bound device is absolutely fine, just break the CC state.
Sometimes it is exactly what host need to stop CC immediately.
The problem is in VFIO's pre-FLR handling so we need to patch VFIO, not
PCI core.

Thanks,
Yilun

> 
> Jason

---

## [16] Zhi Wang — 2025-05-15

On 15.5.2025 13.29, Alexey Kardashevskiy wrote:
> 
> 

Yes. QEMU knows almost everything important, it can do the required flow 
and kernel can enforce the requirements. There shouldn't be problem at 
runtime.

But if QEMU crashes, what are left there are only fd closing paths and 
objects that fds represent in the kernel. The modules those fds belongs 
need to solve the dependencies of tearing down objects without the help 
of QEMU.

There will be private MMIO dmabuf fds, VFIO fds, IOMMU device fd, KVM
fds at that time. Who should trigger the TDI unbind at this time?

I think it should be triggered in the vdevice teardown path in IOMMUfd
fd closing path, as it is where the bind is initiated.

iommufd vdevice tear down (iommu fd closing path)
     ----> tsm_tdi_unbind
         ----> intel_tsm_tdi_unbind
             ...
             ----> private MMIO un-maping in KVM
                 ----> cleanup private MMIO mapping in S-EPT and others
                 ----> signal MMIO dmabuf can be safely removed.
                        ^TVM teardown path (dmabuf uninstall path) checks
                        this state and wait before it can decrease the
                        dmabuf fd refcount
             ...
         ----> KVM TVM fd put
     ----> continue iommufd vdevice teardown.

Also, I think we need:

iommufd vdevice TSM bind
     ---> tsm_tdi_bind
         ----> intel_tsm_tdi_bind
             ...
             ----> KVM TVM fd get
             ...

Z.

> 
>> So shooting down the DMABUF object (encrypted MMIO page) means shooting

---

## [17] Zhi Wang — 2025-05-15

On Thu, 15 May 2025 16:44:47 +0000
Zhi Wang <zhiw@nvidia.com> wrote:

> On 15.5.2025 13.29, Alexey Kardashevskiy wrote:
> > 

ident problem, I mean KVM TVM fd is in tsm_tdi_bind(). I saw your code
has already had it there.

>              ...
>

---

## [18] Jason Gunthorpe — 2025-05-15

On Fri, May 16, 2025 at 12:04:04AM +0800, Xu Yilun wrote:
> > arches this was mostly invisible to the hypervisor?
> 

I'm not sure this is fully true, this could be a Intel thing. When the
vPCI is created the host can already know it shouldn't touch the PCI
device anymore and the secure world would enforce that when it gets a
bind command.

The fact it hasn't been locked out immediately at vPCI creation time
is sort of a detail that doesn't matter, IMHO.

> > It might be reasonable to have VFIO reach into iommufd to do that on
> > an already existing iommufd VDEVICE object. A little weird, but we

Not ATTACH, you wanted BIND. You could have a VFIO_DEVICE_BIND(iommufd
vdevice id)

> > sees VFIO remove the S-EPT and release the KVM, then have iommufd
> > destroy the VDEVICE object.

And KVM destroys the VM?
 
> Nowadays, VFIO already holds KVM reference, so we need
> 

This doesn't happen though, it destroys the normal device (idev) which
the vdevice is stacked on top of. You'd have to make normal device
destruction trigger vdevice destruction

>    -> tsm_tdi_unbind()
>       -> tdi stop

This omits the viommu. It won't get destroyed until the iommufd
closes, so iommufd will be holding the kvm and it will do the final
put.

Jason

---

## [19] Xu Yilun — 2025-05-16

> IMHO, I think it might be helpful that you can picture out what are the
> minimum requirements (function/life cycle) to the current IOMMUFD TSM

I'll try my best to brainstorm and make a flow in ASCII. 

(*) means new feature


      Guest          Guest TSM       QEMU           VFIO            IOMMUFD       host TSM          KVM 
      -----          ---------       ----           ----            -------       --------          ---
1.                                                                               *Connect(IDE)
2.                                 Init vdev            
3.                                *create dmabuf   
4.                                               *export dmabuf                              
5.                                create memslot
6.                                                                                              *import dmabuf
7.                                setup shared DMA
8.                                                                 create hwpt
9.                                               attach hwpt
10.                                  kvm run
11.enum shared dev
12.*Connect(Bind)
13.                  *GHCI Bind
14.                                  *Bind
15                                                                 CC viommu alloc
16.                                                                vdevice allloc
16.                                              *attach vdev
17.                                                               *setup CC viommu
18                                                                 *tsm_bind
19.                                                                                  *bind
20.*Attest
21.               *GHCI get CC info
22.                                 *get CC info
23.                                                                *vdev guest req
24.                                                                                 *guest req
25.*Accept
26.             *GHCI accept MMIO/DMA
27.                                *accept MMIO/DMA
28.                                                               *vdev guest req
29.                                                                                 *guest req
30.                                                                                              *map private MMIO
31.             *GHCI start tdi
32.                                *start tdi
33.                                                               *vdev guest req
34.                                                                                 *guest req
35.Workload...
36.*disconnect(Unbind)
37.              *GHCI unbind
38.                                *Unbind
39.                                            *detach vdev
40.                                                               *tsm_unbind
41.                                                                                 *TDX stop tdi
42.                                                                                 *TDX disable mmio cb
43.                                            *cb dmabuf revoke
44.                                                                                               *unmap private MMIO
45.                                                                                 *TDX disable dma cb
46.                                                              *cb disable CC viommu
47.                                                                                 *TDX tdi free
48.                                                                                 *enable mmio
49.                                            *cb dmabuf recover
50.workable shared dev

TSM unbind is a little verbos & specific to TDX Connect, but SEV TSM could
ignore these callback. Just implement an "unbind" tsm ops.

Thanks,
Yilun

> 
> and which part/where need to be modified in the current architecture to

---

## [20] Jason Gunthorpe — 2025-05-15

On Fri, May 16, 2025 at 02:02:29AM +0800, Xu Yilun wrote:
> > IMHO, I think it might be helpful that you can picture out what are the
> > minimum requirements (function/life cycle) to the current IOMMUFD TSM

open /dev/vfio/XX as a VFIO action

Then VFIO attaches to IOMMUFD as an iommufd action creating the idev

> 3.                                *create dmabuf   
> 4.                                               *export dmabuf                              

viommu and vdevice creation happen before KVM run. The vPCI function
is visible to the guest from the very start, even though it is in T=0
mode. If a platform does not require any special CC steps prior to KVM
run then it just has a NOP for these functions.

What you have here is some new BIND operation against the already
existing vdevice as we discussed earlier.

> 16.                                              *attach vdev
> 17.                                                               *setup CC viommu

This seems reasonable you want to have some generic RPC scheme to
carry messages fro mthe VM to the TSM tunneled through the iommufd
vdevice (because the vdevice has the vPCI ID, the KVM ID, the VIOMMU
id and so on)

> 35.Workload...
> 36.*disconnect(Unbind)

unbind vdev. vdev remains until kvm is stopped.

> 40.                                                               *tsm_unbind
> 41.                                                                                 *TDX stop tdi

I don't know why you'd disable a viommu while the VM is running,
doesn't make sense.

> 47.                                                                                 *TDX tdi free
> 48.                                                                                 *enable mmio

This is a nice chart, it would be good to see a comparable chart for
AMD and ARM

Jason

---

## [21] Xu Yilun — 2025-05-16

On Thu, May 15, 2025 at 02:56:58PM -0300, Jason Gunthorpe wrote:
> On Fri, May 16, 2025 at 12:04:04AM +0800, Xu Yilun wrote:
> > > arches this was mostly invisible to the hypervisor?

I see, SW can define the lock out in a wider range. I suddenly understand
you are considering finish all host side CC setup on viommu_alloc &
vdevice_alloc before KVM run, then "Bind" could host agnostic, and TDISP
LOCK/STOP could also be a guest_request.

Now the problem is for TDX, host cannot be agnostic to LOCK/STOP because
of the KVM MMIO mapping ...

I still have to make VFIO uAPIs for "Bind"/"Unbind"

> 
> > > It might be reasonable to have VFIO reach into iommufd to do that on

Yes.

> 
> > > sees VFIO remove the S-EPT and release the KVM, then have iommufd

Yes.

>  
> > Nowadays, VFIO already holds KVM reference, so we need

I see.

https://lore.kernel.org/all/20250319233111.GE126678@ziepe.ca/

Thanks,
Yilun

> 
> Jason

---

## [22] Xu Yilun — 2025-05-16

On Thu, May 15, 2025 at 04:21:27PM -0300, Jason Gunthorpe wrote:
> On Fri, May 16, 2025 at 02:02:29AM +0800, Xu Yilun wrote:
> > > IMHO, I think it might be helpful that you can picture out what are the

Fine.

> What you have here is some new BIND operation against the already
> existing vdevice as we discussed earlier.

Here it means remove the CC setup for viommu, shared setup is still
kept.

It is still because of the TDX enforcement on Unbind :(

  1. STOP TDI via TDISP message STOP_INTERFACE
  2. Private MMIO unmap from Secure EPT
  3. Trusted Device Context Table cleanup for the TDI
  4. TDI ownership reclaim and metadata free

It is doing Step 3 so that the TDI could finally been removed.

Please also note I does CC viommu setup on "Bind".

Thanks,
Yilun

> 
> > 47.                                                                                 *TDX tdi free

---

## [23] Jason Gunthorpe — 2025-05-16

On Fri, May 16, 2025 at 02:19:45PM +0800, Xu Yilun wrote:
> > I don't know why you'd disable a viommu while the VM is running,
> > doesn't make sense.

That might makes sense for the vPCI function, but not the vIOMMU. A
secure VIOMMU needs to be running at all times while the guest is
running. Perhaps it has no devices it can be used with, but it's
functionality has to be there because a driver in the VM will be
connected to it.

At most "bind" should only tell the already existing secure vIOMMU
that it is allowed to translate for a specific vPCI function.

Jason

---

## [24] Xu Yilun — 2025-05-17

On Fri, May 16, 2025 at 09:49:53AM -0300, Jason Gunthorpe wrote:
> On Fri, May 16, 2025 at 02:19:45PM +0800, Xu Yilun wrote:
> > > I don't know why you'd disable a viommu while the VM is running,

So I think something like:

struct iommufd_vdevice_ops {
	int (*setup_trusted_dma)(struct iommufd_vdevice *vdev); //for Bind
	void (*remove_trusted_dma)(struct iommufd_vdevice *vdev); //for Unbind
};

Thanks,
Yilun

> 
> Jason

---

## [25] Alexey Kardashevskiy — 2025-05-20

On 16/5/25 04:02, Xu Yilun wrote:
>> IMHO, I think it might be helpful that you can picture out what are the
>> minimum requirements (function/life cycle) to the current IOMMUFD TSM


This "attach vdev" - we are still deciding if it goes to IOMMUFD or VFIO, right?


> 17.                                                               *setup CC viommu
> 18                                                                 *tsm_bind


I am not sure I follow the layout here. "start tdi" and "accept MMIO/DMA" are under "QEMU" but QEMU cannot do anything by itself and has to call VFIO or some other driver...

> 35.Workload...
> 36.*disconnect(Unbind)

Is this a case of PCI hotunplug? Or just killing QEMU/shutting down the VM? Or stopping trusting the device and switching it to untrusted mode, to work with SWIOTLB or DiscardManager?

> 37.              *GHCI unbind
> 38.                                *Unbind


... like VFIO and hostTSM - "TDX stop tdi" and "cb dmabuf revoke" are not under QEMU.


> 44.                                                                                               *unmap private MMIO
> 45.                                                                                 *TDX disable dma cb


What is the difference between "cb dmabuf revoke" and "cb dmabuf recover"?


> 50.workable shared dev
> 


Well, something need to clear RMP entries, can be done in the TDI unbind or whenever you will do it.

And the chart applies for AMD too, more or less. Thanks,


> Thanks,
> Yilun

---

## [26] Alexey Kardashevskiy — 2025-05-21

On 16/5/25 02:53, Zhi Wang wrote:
> On Thu, 15 May 2025 16:44:47 +0000
> Zhi Wang <zhiw@nvidia.com> wrote:

This is how I do it now, yes.


>>
>> iommufd vdevice tear down (iommu fd closing path)

This extra signaling is not needed on AMD SEV though - 1) VFIO will destroy this dmabuf on teardown (and it won't care about its RMP state) and 2) the CCP driver will clear RMPs for the device's resources. KVM mapping will die naturally when KVM fd is closed.


>>               ...
>>           ----> KVM TVM fd put

Yup, that's right.

> 
>>               ...

---

## [27] Alexey Kardashevskiy — 2025-05-22

On 16/5/25 02:04, Xu Yilun wrote:
> On Wed, May 14, 2025 at 01:33:39PM -0300, Jason Gunthorpe wrote:
>> On Wed, May 14, 2025 at 03:02:53PM +0800, Xu Yilun wrote:

(implementation note)
AMD SEV moves TDI to RUN at "Attest" as a guest still can avoid encrypted MMIO access and the PSP keeps IOMMU blocked until the guest enables it.

> 4. "Unbind", guest requests host put device in CONFIG_UNLOCK state +
> remove all CC setup.

No, they cannot.

> Bind cannot be host agnostic, host should be aware not to touch device
> after Bind.

Bind actually connects a TDI to a guest, the guest could not possibly do that alone as it does not know/have access to the physical PCI function#0 to do the DOE/SecSPDM messaging, and neither does the PSP.

The non-touching clause (or, more precisely "selectively touching") is about "Attest" and "Accept" when the TDI is in the CONFIG_LOCKED or RUN state. Up to the point when we rather want to block the config space and MSIX BAR access after the TDI is CONFIG_LOCKED/RUN to prevent TDI from going to the ERROR state.


>>
>>> But in my mind, "bind" only includes


I am still not sure what "vPCI" means exactly, a passed through PCI device? Or a piece of vIOMMU handling such device?


>> It might be reasonable to have VFIO reach into iommufd to do that on
>> an already existing iommufd VDEVICE object. A little weird, but we

Can be done by making IOMMUFD/vdevice holding the kvm pointer to ensure tsm_tdi_unbind() is not called before the guest disappeared from the firmware. I seem to be just lucky with the current order of things being destroyed, hmm.


> Nowadays, VFIO already holds KVM reference, so we need
> 

VFIO knows about this enough as we asked it to share MMIO via dmabuf's fd and not via mmap(), otherwise it is the same MMIO, exactly where it was, BARs do not change.

>>>
>>> I have to interpret this as VFIO firstly hand over device CC features

What is a problem here exactly?
FLR by the host which equals to any other PCI error? The guest may or may not be able to handle it, afaik it does not handle any errors now, QEMU just stops the guest.
Or FLR by the guest? Then it knows it needs to do the dance with attest/accept, again.

Thanks,

> 
> Thanks,

---

## [28] Xu Yilun — 2025-05-24

On Thu, May 22, 2025 at 01:45:57PM +1000, Alexey Kardashevskiy wrote:
> 
> 

Good to know. That's why we have these SW defined verbs rather than
reusing TDISP terms.

> > 4. "Unbind", guest requests host put device in CONFIG_UNLOCK state +
> > remove all CC setup.

MM.. TSM driver is the agent of trusted firmware in the OS, so I
excluded it from "hypervisor". TSM driver could parse data blobs and do
whatever requested by trusted firmware.

I want to justify the general guest_request interface, explain why
VIFO/IOMMUFD don't have to maintain the "attest", "accept" states.

> 
> > Bind cannot be host agnostic, host should be aware not to touch device

My understanding is both. When you "Bind" you modifies the physical
device, you may also need to setup a piece of vIOMMU for private
assignement to work.

> 
> > > It might be reasonable to have VFIO reach into iommufd to do that on

tsm_tdi_unbind() *should* be called before guest disappear. For TDX
Connect that is the enforcement. Holding KVM pointer is the effective
way.

> 
> > Nowadays, VFIO already holds KVM reference, so we need

Yes, if you define a SW "lock down" in boarder sense than TDISP LOCKED.
But seems TDX Connect failed to adapt to this solution because it still
needs to handle MMIO invalidation before FLR, see below.

> > > > 
> > > > I have to interpret this as VFIO firstly hand over device CC features

It is about TDX Connect.

According to the dmabuf patchset, the dmabuf needs to be revoked before
FLR. That means KVM unmaps MMIOs when the device is in LOCKED/RUN state.
That is forbidden by TDX Module and will crash KVM. So the safer way is
to unbind the TDI first, then revoke MMIOs, then do FLR.

I'm not sure when p2p dma is involved AMD will have the same issue.
Cause in that case, MMIOs would also be mapped in IOMMU PT and revoke
MMIOs means IOMMU mapping drop. The root cause of the concern is secure
firmware should monitor IOMMU mapping integrity for private assignement
or hypervisor could silently drop trusted DMA writting.

TDX Connect has the wider impact on this issue cause it uses the same
table for KVM S-EPT and Secure IOMMU PT.

Thanks,
Yilun

> Or FLR by the guest? Then it knows it needs to do the dance with attest/accept, again.
>

---

## [29] Xu Yilun — 2025-05-24

On Tue, May 20, 2025 at 08:57:42PM +1000, Alexey Kardashevskiy wrote:
> 
> 

This should be "tsm bind". Seems Jason's suggestion is place the IOCTL
against VFIO, then VFIO reach into IOMMUFD to do the real
pci_tsm_bind().

https://lore.kernel.org/all/20250515175658.GR382960@nvidia.com/

> 
> 

Yes. Call IOCTL(iommufd, IOMMUFD_VDEVICE_GUEST_REQUEST, vdevice_id)

> > 35.Workload...
> > 36.*disconnect(Unbind)

switching to untrusted mode. But I think hotunplug would finally trigger
the same host side behavior, only no need the guest to "echo 0 > connect"

> > 37.              *GHCI unbind
> > 38.                                *Unbind

Correct. These are TDX Module specific requirements, we don't want them
to make the general APIs unnecessary verbose.

> 
> 

revoke revokes private S-EPT mapping, recover means KVM could then do
shared MMIO mapping on EPT.

Thanks,
Yilun

> 
>

---

## [30] Alexey Kardashevskiy — 2025-05-26

On 24/5/25 13:13, Xu Yilun wrote:
> On Thu, May 22, 2025 at 01:45:57PM +1000, Alexey Kardashevskiy wrote:
>>


FLR is something you tell the device to do, how/why would TDX know about it? Or it check the TDI state on every map/unmap (unlikely)?


> So the safer way is
> to unbind the TDI first, then revoke MMIOs, then do FLR.

On AMD, the host can "revoke" at any time, at worst it'll see RMP events from IOMMU. Thanks,


> Cause in that case, MMIOs would also be mapped in IOMMU PT and revoke
> MMIOs means IOMMU mapping drop. The root cause of the concern is secure

---

## [31] Xu Yilun — 2025-05-29

> > > > 
> > > > FLR to a bound device is absolutely fine, just break the CC state.

I'm talking about FLR in VFIO driver. The VFIO driver would zap bar
before FLR. The zapping would trigger KVM unmap MMIOs. See
vfio_pci_zap_bars() for legacy case, and see [1] for dmabuf case.

[1] https://lore.kernel.org/kvm/20250307052248.405803-4-vivek.kasireddy@intel.com/

A pure FLR without zapping bar is absolutely OK.

> Or it check the TDI state on every map/unmap (unlikely)?

Yeah, TDX Module would check TDI state on every unmapping.

> 
> 

Is the RMP event firstly detected by host or guest? If by host,
host could fool guest by just suppress the event. Guest thought the
DMA writting is successful but it is not and may cause security issue.

Thanks,
Yilun

---

## [32] Jason Gunthorpe — 2025-05-29

On Thu, May 29, 2025 at 10:41:15PM +0800, Xu Yilun wrote:

> > On AMD, the host can "revoke" at any time, at worst it'll see RMP
> > events from IOMMU. Thanks,

Is that in scope of the threat model though? Host must not be able to
change DMAs or target them to different memory, but the host can stop
DMA and loose it, surely?

Host controls the PCI memory enable bit, doesn't it?

Jason

---

## [33] Alexey Kardashevskiy — 2025-05-30

On 30/5/25 00:41, Xu Yilun wrote:
>>>>>
>>>>> FLR to a bound device is absolutely fine, just break the CC state.

oh I did not know that we do this zapping, thanks for the pointer. 
> [1] https://lore.kernel.org/kvm/20250307052248.405803-4-vivek.kasireddy@intel.com/
> 

_every_? Reading the state from DOE mailbox is not cheap enough (imho) to do on every unmap.

>>
>>> So the safer way is

Host.

> host could fool guest by just suppress the event. Guest thought the
> DMA writting is successful but it is not and may cause security issue.

An RMP event on the host is an indication that RMP check has failed and DMA to the guest did not complete so the guest won't see new data. Same as other PCI errors really. RMP acts like a firewall, things behind it do not need to know if something was dropped. Thanks,

> 
> Thanks,

---

## [34] Xu Yilun — 2025-05-31

On Thu, May 29, 2025 at 01:29:23PM -0300, Jason Gunthorpe wrote:
> On Thu, May 29, 2025 at 10:41:15PM +0800, Xu Yilun wrote:
> 

This is within the threat model, this is a data integrity issue, not a
DoS issue.  If secure firmware don't care, then no component within the
TCB could be aware of the data loss.

> 
> Host controls the PCI memory enable bit, doesn't it?

That's why DSM should fallback the device to CONFIG_UNLOCKED when memory
enable is toggled, that makes TD/TDI aware of the problem. But for IOMMU
PT blocking, DSM cannot be aware, TSM must do something.

Zhi helps find something in SEV-TIO Firmware Interface SPEC, Section 2.11
which seems to indicate SEV does do something for this.

"If a bound TDI sends a request to the root complex, and the IOMMU detects a fault caused by host
configuration, the root complex fences the ASID from all further I/O to or from that guest. A host
fault is either a host page table fault or an RMP check violation. ASID fencing means that the
IOMMU blocks all further I/O from the root complex to the guest that the TDI was bound, and the
root complex blocks all MMIO accesses by the guest. When a guest writes to MMIO, the write is
silently dropped. When a guest reads from MMIO, the guest reads 1s."

Blocking all TDIs should definitely be avoided. Now I'm more sure Unbind
before DMABUF revoke is necessary.

Thanks,
Yilun

> 
> Jason

---

## [35] Xu Yilun — 2025-05-31

On Fri, May 30, 2025 at 12:29:30PM +1000, Alexey Kardashevskiy wrote:
> 
> 

Sorry for confusing. TDX firmware just checks if STOP TDI firmware call
is executed, will not check the real device state via DOE. That means
even if device has physically exited to UNLOCKED, TDX host should still
call STOP TDI fwcall first, then MMIO unmap.

> 
> > > 

Not really, guest thought the data is changed but it actually doesn't.
I.e. data integrity is broken.

Also please help check if the following relates to this issue:

SEV-TIO Firmware Interface SPEC, Section 2.11

If a bound TDI sends a request to the root complex, and the IOMMU detects a fault caused by host
configuration, the root complex fences the ASID from all further I/O to or from that guest. A host
fault is either a host page table fault or an RMP check violation. ASID fencing means that the
IOMMU blocks all further I/O from the root complex to the guest that the TDI was bound, and the
root complex blocks all MMIO accesses by the guest. When a guest writes to MMIO, the write is
silently dropped. When a guest reads from MMIO, the guest reads 1s.

Thanks,
Yilun

> 
> >

---

## [36] Alexey Kardashevskiy — 2025-06-10

On 31/5/25 02:23, Xu Yilun wrote:
> On Fri, May 30, 2025 at 12:29:30PM +1000, Alexey Kardashevskiy wrote:
>>

I am not following, sorry. Integrity is broken when something untrusted (== other than the SNP guest and the trusted device) manages to write to the guest encrypted memory successfully. If nothing is written - the guest can easily see this and do... nothing? Devices have bugs or spurious interrupts happen, the guest driver should be able to cope with that.
   
> Also please help check if the following relates to this issue:
> 

Right, this is about not letting bad data through, i.e. integrity. Thanks,

> 
> Thanks,

---

## [37] Alexey Kardashevskiy — 2025-06-10

On 14/5/25 13:20, Xu Yilun wrote:
> On Mon, May 12, 2025 at 07:30:21PM +1000, Alexey Kardashevskiy wrote:
>>

It is more IOMMU stuff than PCI and for the PCI part VFIO has nothing to add to this.
> TSM bind also sets up the device side. From your patch, it calls
> tsm_tdi_bind(), which in turn calls spdm_forward(), I assume it is doing
DMA runs, MMIO works, what is that "lot"? Config space access works a bit different but it traps into QEMU anyway and QEMU already knows about all this binding business and can act accordingly.

>> The device does not know about the VM, it just enables/disables encryption by a request from the CPU (those start/stop interface commands).
>> And IOMMUFD won't be doing DOE, the platform driver (such as AMD CCP) will. Nothing to do for VFIO here.

Only forwards messages, no state change in page tables or anywhere in the host kernel really. Thanks,

ps. hard to follow a million of (sub)threads but I am trying, sorry for the delays :)

> 
> Thanks,

---

## [38] Baolu Lu — 2025-06-10

On 6/10/25 12:20, Alexey Kardashevskiy wrote:
> 
> 

Data integrity might not be the most accurate way to describe the
situation here. If I understand correctly, the MMIO mapping was
destroyed before the device was unbound (meaning the guest still sees
the device). When the guest issues a P2P write to the device's MMIO, it
will definitely fail, but the guest won't be aware of this failure.

Imagine this on a bare-metal system: if a P2P access targets a device's
MMIO but the device or platform considers it an illegal access, there
should be a bus error or machine check exception. Alternatively, if the
device supports out-of-band AER, the AER driver should then catch and
process these errors.

Therefore, unbinding the device before MMIO invalidation could generally
avoid this.

Thanks,
baolu

---

## [39] Xu Yilun — 2025-06-10

On Tue, Jun 10, 2025 at 02:20:03PM +1000, Alexey Kardashevskiy wrote:
> 
> 

Integrity is also broken when guest thought the content in some addr was
written to A but it actually stays B.

> If nothing is written - the guest can easily see this and do... nothing?

The guest may not see this only by RMP event, or IOMMU fault, malicious
host could surpress these events.  Yes, guest may later read the addr
and see the trick, but this cannot be ensured. There is no general
contract saying SW must read the addr to ensure DMA write successful.

And DMA to MMIO is the worse case than DMA to memory. SW even cannot
read back the content since MMIO registers may be Write Only.

So you need ASID fence to make guest easily see the DMA Silent Drop.
Intel & ARM also have there own way.

The purpose here is to have a consensus that benigh VMM should avoid
triggering these DMA Silent Drop protections, by "unbind TDI first,
then invalidate MMIO".

Thanks,
Yilun

> Devices have bugs or spurious interrupts happen, the guest driver should be able to cope with that.
> > Also please help check if the following relates to this issue:

---

## [40] Alexey Kardashevskiy — 2026-05-06
*Subject: Re: [RFC PATCH 04/12] vfio/pci: Allow MMIO regions to be exported
 through dma-buf*

Hi!

Let's reignite this topic.

I've been using these patches + QEMU side hacks for 6+ months. And it's been fine until I got a device where MSIX BAR is in a middle of another BAR marked as TEE in the TDISP interface report. And no trusted MSIX yet.

Every time QEMU mmaps a BAR - I request a dmabuf fd from VFIO in QEMU. Since mapping of an entire MSIX BAR is allowed by default, VFIORegion::nr_mmaps==1 and it is an entire BAR.

Problem: KVM memslot mismatches the dmabuf fd size
How: QEMU emulates MSIX table and PBA by adding emulated MemoryRegions on top of the mapped BARs. In the QEMU memory flatview this splits the BAR into 2 or 3 sections (2 if MSIX at the start/end, 3 if in a middle). QEMU tries registering 1 or 2 KVM memory slots for regions outside of MSIX which fails in kvm_vfio_dmabuf_bind() as regions are smaller than the exported dmabuf fd (which is the entire BAR == 32KB).

Solution1: use QEMU x-msix-relocation hack to move MSIX elsewhere - end of some BAR (doubles the bar size so problematic for huge BARs like 512GB+), or another BAR (there may be no available as 3 of 64bit BARs is the limit).

Solution2: modify logic in VFIO dmabuf to allow multiple KVM memory slots per dmabuf. Now it is kvm_memory_slot::dmabuf_attach with no offset into the dmabuf and one kvm_vfio_dmabuf per dma_buf.

Solution3: hack QEMU into smashing a MSIX-containing BAR in vfio_pci_fixup_msix_region. Here is what it does:

0000380004000000-0000380004002fff (prio 0, ramd): 0000:41:04.0 BAR 4 mmaps[0] KVM
0000380004003000-0000380004006fff (prio 0, i/o): msix-table
0000380004007000-0000380004007fff (prio 0, ramd): 0000:41:04.0 BAR 4 mmaps[1] KVM

The problem now is that the TDI report must have the same split of the BAR as the VM is going to validate TEE (==trusted) MMIO ranges and this has to match the QEMU view. Harder than it sounds as the size of MSIX table in bytes is not exactly specified anywhere except the report.

Solution4: the above + modify QEMU to check the TDI report for not reporting MSIX+PBA where QEMU emulates them. The problem is that when QEMU adds emulated MRs - there is no report yet (the report is created later on, some TDISP witchery). So when the device is accepted - QEMU could reinitialize those emulated msix and pba MRs to match the report exactly so the flatview generates correct KVM memory regions and then KVM can work with dmabuf fine.

Any thoughts? what is acceptable for everybody? Thanks,



On 8/1/25 01:27, Xu Yilun wrote:
> From: Vivek Kasireddy <vivek.kasireddy@intel.com>
>

---

## [41] Jason Gunthorpe — 2026-05-06
*Subject: Re: [RFC PATCH 04/12] vfio/pci: Allow MMIO regions to be exported
 through dma-buf*

On Wed, May 06, 2026 at 12:35:42PM +1000, Alexey Kardashevskiy wrote:
> Hi!
> 

Huh? kvm does not care about dmabuf at all? Are you running other
patches to hook kvm and dmabuf?

Putting a slice in a dmabuf is a well understood need for MSI, so I
expect whatever kvm dmabuf interface that gets merged to accomodate
this?

> Solution2: modify logic in VFIO dmabuf to allow multiple KVM memory
> slots per dmabuf. Now it is kvm_memory_slot::dmabuf_attach with no

Yes, when kvm learns to take in a dmabuf it needs to take in a slice,
not the whole buf. Or you need to create multiple dmabufs with the
necessary slices from the VFIO. The upstream vfio dmabuf creation
allows creating it with a slice.

Jason

---

## [42] Alexey Kardashevskiy — 2026-05-07
*Subject: Re: [RFC PATCH 04/12] vfio/pci: Allow MMIO regions to be exported
 through dma-buf*

On 6/5/26 23:16, Jason Gunthorpe wrote:
> On Wed, May 06, 2026 at 12:35:42PM +1000, Alexey Kardashevskiy wrote:
>> Hi!

yup, 06/12 of this patchset.

> Putting a slice in a dmabuf is a well understood need for MSI, so I
> expect whatever kvm dmabuf interface that gets merged to accomodate

good to know.

>> Solution2: modify logic in VFIO dmabuf to allow multiple KVM memory
>> slots per dmabuf. Now it is kvm_memory_slot::dmabuf_attach with no

true but either way dmabuf slicing will be directed by QEMU's msix-table emulation MR and this slicing needs to match the TDISP report so I'll have to teach QEMU these reports, right? I am worried if I miss something obvious, again. Thanks,


ps. I like nntp.lore.kernel.org very much for ability to dig out old stuff and then just reply to it :)

> 
> Jason

---
