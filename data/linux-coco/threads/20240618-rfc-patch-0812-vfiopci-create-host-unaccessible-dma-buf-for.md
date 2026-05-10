---
title: '[RFC PATCH 08/12] vfio/pci: Create host unaccessible dma-buf for\n private device'
date: 2024-06-18
last_reply: 2025-04-29
message_count: 95
participants: ['Xu Yilun', 'Christian König', 'Jason Gunthorpe', 'Simona Vetter', 'Leon Romanovsky', 'Christoph Hellwig', 'Alexey Kardashevskiy', 'Baolu Lu', 'Dan Williams']
---

## [1] Xu Yilun — 2024-06-18

On Mon, Jan 13, 2025 at 12:49:35PM -0400, Jason Gunthorpe wrote:
> On Sat, Jan 11, 2025 at 11:48:06AM +0800, Xu Yilun wrote:
> 

Yes, it is in early stage and open to discuss.

> 
> What I'm talking abou there is that you will tell the secure world to

Yes.

> is needed so the secure world can prepare anything it needs prior to
> starting the VM.

OK. From Dan's patchset there are some touch point for vendor tsm
drivers to do secure world preparation. e.g. pci_tsm_ops::probe().

Maybe we could move to Dan's thread for discussion.

https://lore.kernel.org/linux-coco/173343739517.1074769.13134786548545925484.stgit@dwillia2-xfh.jf.intel.com/

> Setting up secure vIOMMU emulation, for instance. I

I think this could be done at VM late bind time.

> expect ARM will need this, I'd be surprised if AMD actually doesn't in
> the full scenario with secure viommu.

AFAICS, AMD needs secure viommu.

> 
> It should not be a surprise to the secure world after the VM has

With some pre-VM stage touch point, it wouldn't be all of a sudden.

> secure. This should all be pre-arranged as possible before starting

But our current implementation is not to prepare as much as possible,
but only necessary, so most of the secure work for vPCI function is done
at late bind time.

Thank,
Yilun

> the VM, even if alot of steps happen after the VM starts running (or
> maybe don't happen at all).

---

## [2] Xu Yilun — 2024-06-20
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Thu, Jan 16, 2025 at 06:33:48AM +0100, Christoph Hellwig wrote:
> On Wed, Jan 15, 2025 at 09:34:19AM -0400, Jason Gunthorpe wrote:
> > > Or do you mean some that don't have pages associated with them, and

One part of dma-buf is the fd-based machanism for exporters to share
buffers across devices & subsystems, while still have buffer's lifetime
controlled by exporters.  Another part is the way the importers use
the buffer (i.e. the dma_addr_t based kAPI).

The fd-based exporting machanism is what we want to dmaareuse for buffer
sharing. But we are pursuing some extended buffer sharing and DMA usage
which doesn't fit into existing DMA API mapping, e.g. for GPA/userspace
IOVA accessing, or IIUC other side channel DMA, multi-channel DMA ...

Thanks,
Yilun

---

## [3] Xu Yilun — 2024-06-21
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Thu, Jan 16, 2025 at 04:13:13PM +0100, Christian König wrote:
>    Am 15.01.25 um 18:09 schrieb Jason Gunthorpe:
> 

Dealing with CPU mapping and resource invalidation is a little hard, but is
resolvable, by using other types of locks. And I guess for now dma-buf
exporters should always handle this CPU mapping VS. invalidation contention if
they support mmap().

It is resolvable so with some invalidation notify, a decent importers could
also handle the contention well.

IIUC now the only concern is importer device drivers are easier to do
something wrong, so move CPU mapping things to exporter. But most of the
exporters are also device drivers, why they are smarter?

And there are increasing mapping needs, today exporters help handle CPU primary
mapping, tomorrow should they also help on all other mappings? Clearly it is
not feasible. So maybe conditionally give trust to some importers.

Thanks,
Yilun

---

## [4] Xu Yilun — 2024-06-24

On Fri, Jan 17, 2025 at 09:25:23AM -0400, Jason Gunthorpe wrote:
> On Fri, Jan 17, 2025 at 09:57:40AM +0800, Baolu Lu wrote:
> > On 1/15/25 21:01, Jason Gunthorpe wrote:

I also expect this.

> 
> From that perspective it does make sense that any cVM related APIs,

Firstly I think VFIO should support putting device into *LOCKED* state.
From LOCKED to RUN, there are many evidence fetching and attestation
things that only guest cares. I don't think VFIO needs to opt-in.

But that doesn't impact this concern. I actually think VFIO should
provide 'bind' uAPI to support these device side configuration things
rather than iommufd uAPI. IIUC iommufd should only do the setup on
IOMMU side.

The switching of TDISP state to LOCKED involves device side
differences that should be awared by the device owner, VFIO driver.

E.g. as we previously mentioned, to check if all MMIOs are never mapped.

Another E.g. invalidate MMIOs when device is to be LOCKED, some Pseudo
Code:

@@ -1494,7 +1494,15 @@ static int vfio_pci_ioctl_tsm_bind(struct vfio_pci_core_device *vdev,
        if (!kvm)
                return -ENOENT;

+       down_write(&vdev->memory_lock);
+       vfio_pci_dma_buf_move(vdev, true);
+
        ret = pci_tsm_dev_bind(pdev, kvm, &bind.intf_id);
+
+       if (__vfio_pci_memory_enabled(vdev))
+               vfio_pci_dma_buf_move(vdev, false);
+       up_write(&vdev->memory_lock);


BTW, we may still need viommu/vdevice APIs during 'bind', if some IOMMU
side configurations are required by secure world. TDX does have some.

> without involving KVM or cVMs.

It may not be feasible for all vendors. I believe AMD would have one
firmware call that requires cVM handle *AND* move device into LOCKED
state. It really depends on firmware implementation.

So I'm expecting a coarse TSM verb pci_tsm_dev_bind() for vendors to do
any host side preparation and put device into LOCKED state.

> 
> > Intel TDX connect implementation also needs a reference to the kvm

I believe this is still Based on the general EPT sharing idea, is it?

There are several major reasons for the objection. In general, KVM now
has many "page non-present" tricks in EPT, which are not applicable to
IOPT. If shared, KVM has to take IOPT concerns into account, which is
quite a burden for KVM maintaining.

> secure EPT in the secure world and not directly managed by Linux?

Yes, the secure EPT is in the secure world and managed by TDX firmware.
Now a SW Mirror Secure EPT is introduced in KVM and managed by KVM
directly, and KVM will finally use firmware calls to propagate Mirror
Secure EPT changes to secure EPT.

Secure EPT are controlled by TDX module, basically KVM cannot play any
of the tricks. And TDX firmware should ensure any SEPT setting would be
applicable for Secure IOPT. I hope this could remove most of the
concerns.

I remember we've talked about SEPT sharing architechture for TDX TIO
before, but didn't get information back from KVM folks. Not sure how
things will go. Maybe will find out when we have some patches posted.

Thanks,
Yilun

> 
> AFAIK AMD is going to mirror the iommu page table like today.

---

## [5] Xu Yilun — 2024-06-25

On Mon, Jan 20, 2025 at 09:25:25AM -0400, Jason Gunthorpe wrote:
> On Mon, Jun 24, 2024 at 03:59:53AM +0800, Xu Yilun wrote:
> > > But it also seems to me that VFIO should be able to support putting

Interesting Question. I've never thought about native TIO before.

And you are also thinking about VFIO usage in CoCo-VM. So I believe
VFIO could be able to support putting the device into the RUN state,
but no need a uAPI for that, this happens when VFIO works as a TEE
attester.

In different cases, VFIO plays different roles:

1. TEE helper, but itself is out of TEE.
2. TEE attester, it is within the TEE.
3. TEE user, it is within the TEE.

As a TEE helper, it works on a untrusted device and help put the device
in LOCKED state, waiting for attestation. For VM use case, VM acts as the
attester to do attestation and move device into trusted/RUN state (lets
say 'accept'). The attestation and accept could be direct talks between
attester and device (maybe via TSM sysfs node), because from
LOCKED -> RUN VFIO doesn't change its way of handling device so seems
no need to introduce extra uAPIs and complexity just for passing the
talks. That's my expectation of VFIO's responsibility as a TEE
helper - serve until LOCKED, no care about the rest, UNLOCK rollbacks
everything.

I imagine in bare metal, if DPDK works as an attester (within TEE) and
VFIO still as a TEE helper (out of TEE), this model seems still work.



When VFIO works as a TEE user in VM, it means an attester (e.g. PCI
subsystem) has already moved the device to RUN state. So VFIO & DPDK
are all TEE users, no need to manipulate TDISP state between them.
AFAICS, this is the most preferred TIO usage in CoCo-VM.

When VFIO works as a TEE attester in VM, it means the VM's PCI
subsystem leaves the attestation work to device drivers. VFIO should do
the attestation and accept before pass through to DPDK, again no need to
manipulate TDISP state between them.

I image the possibility TIO happens on bare metal, that a device is
configured as waiting for attestation by whatever kernel module, then
PCI subsystem or VFIO try to attest, accept and use it, just the same as
in CoCo VM.

> 
> > > without involving KVM or cVMs.

You are talking about VFIO in CoCo-VM as an attester, then definiately
yes.

> 
> > I believe AMD would have one firmware call that requires cVM handle

Yes.

Thanks,
Yilun

> 
> Jason

---

## [6] Xu Yilun — 2025-01-07
*Subject: [RFC PATCH 00/12] Private MMIO support for private assigned dev*

This series is based on an earlier kvm-coco-queue version (v6.12-rc2)
which includes all basic TDX patches.

The series is to start the early stage discussion of the private MMIO
handling for Coco-VM, which is part of the Private Device
Assignment (aka TEE-IO, TIO) enabling. There are already some
disscusion about the context of TIO:

https://lore.kernel.org/linux-coco/173343739517.1074769.13134786548545925484.stgit@dwillia2-xfh.jf.intel.com/
https://lore.kernel.org/all/20240823132137.336874-1-aik@amd.com/

Private MMIOs are resources owned by Private assigned devices. Like
private memory, they are also not intended to be accessed by host, only
accessible by Coco-VM via some secondary MMUs (e.g. Secure EPT). This
series is for KVM to map these MMIO resources without firstly mapping
into the host. For this purpose, This series uses the FD based MMIO
resources for secure mapping, and the dma-buf is chosen as the FD based
backend, just like guest_memfd for private memory. Patch 6 in this
series has more detailed description.


Patch 1 changes dma-buf core, expose a new kAPI for importers to get
dma-buf's PFN without DMA mapping. KVM could use this kAPI to build
GPA -> HPA mapping in KVM MMU.

Patch 2-4 are from Jason & Vivek, allow vfio-pci to export MMIO
resources as dma-buf. The original series are for native P2P DMA and
focus on p2p DMA mapping opens. I removed these p2p DMA mapping code
just to focus the early stage discussion of private MMIO. The original
series:

https://lore.kernel.org/all/0-v2-472615b3877e+28f7-vfio_dma_buf_jgg@nvidia.com/
https://lore.kernel.org/kvm/20240624065552.1572580-1-vivek.kasireddy@intel.com/

Patch 5 is the implementation of get_pfn() callback for vfio dma-buf
exporter.

Patch 6-7 is about KVM supports the private MMIO memory slot backed by
vfio dma-buf.

Patch 8-10 is about how KVM verifies the user provided dma-buf fd
eligible for private MMIO slot.

Patch 11-12 is the example of how KVM TDX setup the Secure EPT for
private MMIO.


TODOs:

- Follow up the evolving of original VFIO dma-buf series.
- Follow up the evolving of basic TDX patches.


Vivek Kasireddy (3):
  vfio: Export vfio device get and put registration helpers
  vfio/pci: Share the core device pointer while invoking feature
    functions
  vfio/pci: Allow MMIO regions to be exported through dma-buf

Xu Yilun (9):
  dma-buf: Introduce dma_buf_get_pfn_unlocked() kAPI
  vfio/pci: Support get_pfn() callback for dma-buf
  KVM: Support vfio_dmabuf backed MMIO region
  KVM: x86/mmu: Handle page fault for vfio_dmabuf backed MMIO
  vfio/pci: Create host unaccessible dma-buf for private device
  vfio/pci: Export vfio dma-buf specific info for importers
  KVM: vfio_dmabuf: Fetch VFIO specific dma-buf data for sanity check
  KVM: x86/mmu: Export kvm_is_mmio_pfn()
  KVM: TDX: Implement TDX specific private MMIO map/unmap for SEPT

 Documentation/virt/kvm/api.rst     |   7 +
 arch/x86/include/asm/tdx.h         |   3 +
 arch/x86/kvm/mmu.h                 |   1 +
 arch/x86/kvm/mmu/mmu.c             |  25 ++-
 arch/x86/kvm/mmu/spte.c            |   3 +-
 arch/x86/kvm/vmx/tdx.c             |  57 +++++-
 arch/x86/virt/vmx/tdx/tdx.c        |  52 ++++++
 arch/x86/virt/vmx/tdx/tdx.h        |   3 +
 drivers/dma-buf/dma-buf.c          |  90 ++++++++--
 drivers/vfio/device_cdev.c         |   9 +-
 drivers/vfio/pci/Makefile          |   1 +
 drivers/vfio/pci/dma_buf.c         | 273 +++++++++++++++++++++++++++++
 drivers/vfio/pci/vfio_pci_config.c |  22 ++-
 drivers/vfio/pci/vfio_pci_core.c   |  64 +++++--
 drivers/vfio/pci/vfio_pci_priv.h   |  27 +++
 drivers/vfio/pci/vfio_pci_rdwr.c   |   3 +
 drivers/vfio/vfio_main.c           |   2 +
 include/linux/dma-buf.h            |  13 ++
 include/linux/kvm_host.h           |  25 ++-
 include/linux/vfio.h               |  22 +++
 include/linux/vfio_pci_core.h      |   1 +
 include/uapi/linux/kvm.h           |   1 +
 include/uapi/linux/vfio.h          |  34 +++-
 virt/kvm/Kconfig                   |   6 +
 virt/kvm/Makefile.kvm              |   1 +
 virt/kvm/kvm_main.c                |  32 +++-
 virt/kvm/kvm_mm.h                  |  19 ++
 virt/kvm/vfio_dmabuf.c             | 151 ++++++++++++++++
 28 files changed, 896 insertions(+), 51 deletions(-)
 create mode 100644 drivers/vfio/pci/dma_buf.c
 create mode 100644 virt/kvm/vfio_dmabuf.c

---

## [7] Xu Yilun — 2025-01-07
*Subject: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked() kAPI*

Introduce a new API for dma-buf importer, also add a dma_buf_ops
callback for dma-buf exporter. This API is for subsystem importers who
map the dma-buf to some user defined address space, e.g. for IOMMUFD to
map the dma-buf to userspace IOVA via IOMMU page table, or for KVM to
map the dma-buf to GPA via KVM MMU (e.g. EPT).

Currently dma-buf is only used to get DMA address for device's default
domain by using kernel DMA APIs. But for these new use-cases, importers
only need the pfn of the dma-buf resource to build their own mapping
tables. So the map_dma_buf() callback is not mandatory for exporters
anymore. Also the importers could choose not to provide
struct device *dev on dma_buf_attach() if they don't call
dma_buf_map_attachment().

Like dma_buf_map_attachment(), the importer should firstly call
dma_buf_attach/dynamic_attach() then call dma_buf_get_pfn_unlocked().
If the importer choose to do dynamic attach, it also should handle the
dma-buf move notification.

Only the unlocked version of dma_buf_get_pfn is implemented for now,
just because no locked version is used for now.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>

---
IIUC, Only get_pfn() is needed but no put_pfn(). The whole dma-buf is
de/referenced at dma-buf attach/detach time.

Specifically, for static attachment, the exporter should always make
memory resource available/pinned on first dma_buf_attach(), and
release/unpin memory resource on last dma_buf_detach(). For dynamic
attachment, the exporter could populate & invalidate the memory
resource at any time, it's OK as long as the importers follow dma-buf
move notification. So no pinning is needed for get_pfn() and no
put_pfn() is needed.
---
 drivers/dma-buf/dma-buf.c | 90 +++++++++++++++++++++++++++++++--------
 include/linux/dma-buf.h   | 13 ++++++
 2 files changed, 86 insertions(+), 17 deletions(-)

diff --git a/drivers/dma-buf/dma-buf.c b/drivers/dma-buf/dma-buf.c
index 7eeee3a38202..83d1448b6dcc 100644
--- a/drivers/dma-buf/dma-buf.c
+++ b/drivers/dma-buf/dma-buf.c
@@ -630,10 +630,10 @@ struct dma_buf *dma_buf_export(const struct dma_buf_export_info *exp_info)
 	size_t alloc_size = sizeof(struct dma_buf);
 	int ret;
 
-	if (WARN_ON(!exp_info->priv || !exp_info->ops
-		    || !exp_info->ops->map_dma_buf
-		    || !exp_info->ops->unmap_dma_buf
-		    || !exp_info->ops->release))
+	if (WARN_ON(!exp_info->priv || !exp_info->ops ||
+		    (!!exp_info->ops->map_dma_buf != !!exp_info->ops->unmap_dma_buf) ||
+		    (!exp_info->ops->map_dma_buf && !exp_info->ops->get_pfn) ||
+		    !exp_info->ops->release))
 		return ERR_PTR(-EINVAL);
 
 	if (WARN_ON(exp_info->ops->cache_sgt_mapping &&
@@ -909,7 +909,10 @@ dma_buf_dynamic_attach(struct dma_buf *dmabuf, struct device *dev,
 	struct dma_buf_attachment *attach;
 	int ret;
 
-	if (WARN_ON(!dmabuf || !dev))
+	if (WARN_ON(!dmabuf))
+		return ERR_PTR(-EINVAL);
+
+	if (WARN_ON(dmabuf->ops->map_dma_buf && !dev))
 		return ERR_PTR(-EINVAL);
 
 	if (WARN_ON(importer_ops && !importer_ops->move_notify))
@@ -941,7 +944,7 @@ dma_buf_dynamic_attach(struct dma_buf *dmabuf, struct device *dev,
 	 */
 	if (dma_buf_attachment_is_dynamic(attach) !=
 	    dma_buf_is_dynamic(dmabuf)) {
-		struct sg_table *sgt;
+		struct sg_table *sgt = NULL;
 
 		dma_resv_lock(attach->dmabuf->resv, NULL);
 		if (dma_buf_is_dynamic(attach->dmabuf)) {
@@ -950,13 +953,16 @@ dma_buf_dynamic_attach(struct dma_buf *dmabuf, struct device *dev,
 				goto err_unlock;
 		}
 
-		sgt = __map_dma_buf(attach, DMA_BIDIRECTIONAL);
-		if (!sgt)
-			sgt = ERR_PTR(-ENOMEM);
-		if (IS_ERR(sgt)) {
-			ret = PTR_ERR(sgt);
-			goto err_unpin;
+		if (dmabuf->ops->map_dma_buf) {
+			sgt = __map_dma_buf(attach, DMA_BIDIRECTIONAL);
+			if (!sgt)
+				sgt = ERR_PTR(-ENOMEM);
+			if (IS_ERR(sgt)) {
+				ret = PTR_ERR(sgt);
+				goto err_unpin;
+			}
 		}
+
 		dma_resv_unlock(attach->dmabuf->resv);
 		attach->sgt = sgt;
 		attach->dir = DMA_BIDIRECTIONAL;
@@ -1119,7 +1125,8 @@ struct sg_table *dma_buf_map_attachment(struct dma_buf_attachment *attach,
 
 	might_sleep();
 
-	if (WARN_ON(!attach || !attach->dmabuf))
+	if (WARN_ON(!attach || !attach->dmabuf ||
+		    !attach->dmabuf->ops->map_dma_buf))
 		return ERR_PTR(-EINVAL);
 
 	dma_resv_assert_held(attach->dmabuf->resv);
@@ -1195,7 +1202,8 @@ dma_buf_map_attachment_unlocked(struct dma_buf_attachment *attach,
 
 	might_sleep();
 
-	if (WARN_ON(!attach || !attach->dmabuf))
+	if (WARN_ON(!attach || !attach->dmabuf ||
+		    !attach->dmabuf->ops->map_dma_buf))
 		return ERR_PTR(-EINVAL);
 
 	dma_resv_lock(attach->dmabuf->resv, NULL);
@@ -1222,7 +1230,8 @@ void dma_buf_unmap_attachment(struct dma_buf_attachment *attach,
 {
 	might_sleep();
 
-	if (WARN_ON(!attach || !attach->dmabuf || !sg_table))
+	if (WARN_ON(!attach || !attach->dmabuf ||
+		    !attach->dmabuf->ops->unmap_dma_buf || !sg_table))
 		return;
 
 	dma_resv_assert_held(attach->dmabuf->resv);
@@ -1254,7 +1263,8 @@ void dma_buf_unmap_attachment_unlocked(struct dma_buf_attachment *attach,
 {
 	might_sleep();
 
-	if (WARN_ON(!attach || !attach->dmabuf || !sg_table))
+	if (WARN_ON(!attach || !attach->dmabuf ||
+		    !attach->dmabuf->ops->unmap_dma_buf || !sg_table))
 		return;
 
 	dma_resv_lock(attach->dmabuf->resv, NULL);
@@ -1263,6 +1273,52 @@ void dma_buf_unmap_attachment_unlocked(struct dma_buf_attachment *attach,
 }
 EXPORT_SYMBOL_NS_GPL(dma_buf_unmap_attachment_unlocked, "DMA_BUF");
 
+/**
+ * dma_buf_get_pfn_unlocked -
+ * @attach:	[in]	attachment to get pfn from
+ * @pgoff:	[in]	page offset of the buffer against the start of dma_buf
+ * @pfn:	[out]	returns the pfn of the buffer
+ * @max_order	[out]	returns the max mapping order of the buffer
+ */
+int dma_buf_get_pfn_unlocked(struct dma_buf_attachment *attach,
+			     pgoff_t pgoff, u64 *pfn, int *max_order)
+{
+	struct dma_buf *dmabuf = attach->dmabuf;
+	int ret;
+
+	if (WARN_ON(!attach || !attach->dmabuf ||
+		    !attach->dmabuf->ops->get_pfn))
+		return -EINVAL;
+
+	/*
+	 * Open:
+	 *
+	 * When dma_buf is dynamic but dma_buf move is disabled, the buffer
+	 * should be pinned before use, See dma_buf_map_attachment() for
+	 * reference.
+	 *
+	 * But for now no pin is intended inside dma_buf_get_pfn(), otherwise
+	 * need another API to unpin the dma_buf. So just fail out this case.
+	 */
+	if (dma_buf_is_dynamic(attach->dmabuf) &&
+	    !IS_ENABLED(CONFIG_DMABUF_MOVE_NOTIFY))
+		return -ENOENT;
+
+	dma_resv_lock(attach->dmabuf->resv, NULL);
+	ret = dmabuf->ops->get_pfn(attach, pgoff, pfn, max_order);
+	/*
+	 * Open:
+	 *
+	 * Is dma_resv_wait_timeout() needed? I assume no. The DMA buffer
+	 * content synchronization could be done when the buffer is to be
+	 * mapped by importer.
+	 */
+	dma_resv_unlock(attach->dmabuf->resv);
+
+	return ret;
+}
+EXPORT_SYMBOL_NS_GPL(dma_buf_get_pfn_unlocked, "DMA_BUF");
+
 /**
  * dma_buf_move_notify - notify attachments that DMA-buf is moving
  *
@@ -1662,7 +1718,7 @@ static int dma_buf_debug_show(struct seq_file *s, void *unused)
 		attach_count = 0;
 
 		list_for_each_entry(attach_obj, &buf_obj->attachments, node) {
-			seq_printf(s, "\t%s\n", dev_name(attach_obj->dev));
+			seq_printf(s, "\t%s\n", attach_obj->dev ? dev_name(attach_obj->dev) : NULL);
 			attach_count++;
 		}
 		dma_resv_unlock(buf_obj->resv);
diff --git a/include/linux/dma-buf.h b/include/linux/dma-buf.h
index 36216d28d8bd..b16183edfb3a 100644
--- a/include/linux/dma-buf.h
+++ b/include/linux/dma-buf.h
@@ -194,6 +194,17 @@ struct dma_buf_ops {
 	 * if the call would block.
 	 */
 
+	/**
+	 * @get_pfn:
+	 *
+	 * This is called by dma_buf_get_pfn(). It is used to get the pfn
+	 * of the buffer positioned by the page offset against the start of
+	 * the dma_buf. It can only be called if @attach has been called
+	 * successfully.
+	 */
+	int (*get_pfn)(struct dma_buf_attachment *attach, pgoff_t pgoff,
+		       u64 *pfn, int *max_order);
+
 	/**
 	 * @release:
 	 *
@@ -629,6 +640,8 @@ dma_buf_map_attachment_unlocked(struct dma_buf_attachment *attach,
 void dma_buf_unmap_attachment_unlocked(struct dma_buf_attachment *attach,
 				       struct sg_table *sg_table,
 				       enum dma_data_direction direction);
+int dma_buf_get_pfn_unlocked(struct dma_buf_attachment *attach,
+			     pgoff_t pgoff, u64 *pfn, int *max_order);
 
 int dma_buf_mmap(struct dma_buf *, struct vm_area_struct *,
 		 unsigned long);

---

## [8] Xu Yilun — 2025-01-07
*Subject: [RFC PATCH 02/12] vfio: Export vfio device get and put registration helpers*

From: Vivek Kasireddy <vivek.kasireddy@intel.com>

These helpers are useful for managing additional references taken
on the device from other associated VFIO modules.

Original-patch-by: Jason Gunthorpe <jgg@nvidia.com>
Signed-off-by: Vivek Kasireddy <vivek.kasireddy@intel.com>
---
 drivers/vfio/vfio_main.c | 2 ++
 include/linux/vfio.h     | 2 ++
 2 files changed, 4 insertions(+)

diff --git a/drivers/vfio/vfio_main.c b/drivers/vfio/vfio_main.c
index 1fd261efc582..620a3ee5d04d 100644
--- a/drivers/vfio/vfio_main.c
+++ b/drivers/vfio/vfio_main.c
@@ -171,11 +171,13 @@ void vfio_device_put_registration(struct vfio_device *device)
 	if (refcount_dec_and_test(&device->refcount))
 		complete(&device->comp);
 }
+EXPORT_SYMBOL_GPL(vfio_device_put_registration);
 
 bool vfio_device_try_get_registration(struct vfio_device *device)
 {
 	return refcount_inc_not_zero(&device->refcount);
 }
+EXPORT_SYMBOL_GPL(vfio_device_try_get_registration);
 
 /*
  * VFIO driver API
diff --git a/include/linux/vfio.h b/include/linux/vfio.h
index 000a6cab2d31..2258b0585330 100644
--- a/include/linux/vfio.h
+++ b/include/linux/vfio.h
@@ -279,6 +279,8 @@ static inline void vfio_put_device(struct vfio_device *device)
 int vfio_register_group_dev(struct vfio_device *device);
 int vfio_register_emulated_iommu_dev(struct vfio_device *device);
 void vfio_unregister_group_dev(struct vfio_device *device);
+bool vfio_device_try_get_registration(struct vfio_device *device);
+void vfio_device_put_registration(struct vfio_device *device);
 
 int vfio_assign_device_set(struct vfio_device *device, void *set_id);
 unsigned int vfio_device_set_open_count(struct vfio_device_set *dev_set);

---

## [9] Xu Yilun — 2025-01-07
*Subject: [RFC PATCH 03/12] vfio/pci: Share the core device pointer while invoking feature functions*

From: Vivek Kasireddy <vivek.kasireddy@intel.com>

There is no need to share the main device pointer (struct vfio_device *)
with all the feature functions as they only need the core device
pointer. Therefore, extract the core device pointer once in the
caller (vfio_pci_core_ioctl_feature) and share it instead.

Signed-off-by: Vivek Kasireddy <vivek.kasireddy@intel.com>
---
 drivers/vfio/pci/vfio_pci_core.c | 30 +++++++++++++-----------------
 1 file changed, 13 insertions(+), 17 deletions(-)

diff --git a/drivers/vfio/pci/vfio_pci_core.c b/drivers/vfio/pci/vfio_pci_core.c
index 1ab58da9f38a..c3269d708411 100644
--- a/drivers/vfio/pci/vfio_pci_core.c
+++ b/drivers/vfio/pci/vfio_pci_core.c
@@ -300,11 +300,9 @@ static int vfio_pci_runtime_pm_entry(struct vfio_pci_core_device *vdev,
 	return 0;
 }
 
-static int vfio_pci_core_pm_entry(struct vfio_device *device, u32 flags,
+static int vfio_pci_core_pm_entry(struct vfio_pci_core_device *vdev, u32 flags,
 				  void __user *arg, size_t argsz)
 {
-	struct vfio_pci_core_device *vdev =
-		container_of(device, struct vfio_pci_core_device, vdev);
 	int ret;
 
 	ret = vfio_check_feature(flags, argsz, VFIO_DEVICE_FEATURE_SET, 0);
@@ -321,12 +319,10 @@ static int vfio_pci_core_pm_entry(struct vfio_device *device, u32 flags,
 }
 
 static int vfio_pci_core_pm_entry_with_wakeup(
-	struct vfio_device *device, u32 flags,
+	struct vfio_pci_core_device *vdev, u32 flags,
 	struct vfio_device_low_power_entry_with_wakeup __user *arg,
 	size_t argsz)
 {
-	struct vfio_pci_core_device *vdev =
-		container_of(device, struct vfio_pci_core_device, vdev);
 	struct vfio_device_low_power_entry_with_wakeup entry;
 	struct eventfd_ctx *efdctx;
 	int ret;
@@ -377,11 +373,9 @@ static void vfio_pci_runtime_pm_exit(struct vfio_pci_core_device *vdev)
 	up_write(&vdev->memory_lock);
 }
 
-static int vfio_pci_core_pm_exit(struct vfio_device *device, u32 flags,
+static int vfio_pci_core_pm_exit(struct vfio_pci_core_device *vdev, u32 flags,
 				 void __user *arg, size_t argsz)
 {
-	struct vfio_pci_core_device *vdev =
-		container_of(device, struct vfio_pci_core_device, vdev);
 	int ret;
 
 	ret = vfio_check_feature(flags, argsz, VFIO_DEVICE_FEATURE_SET, 0);
@@ -1486,11 +1480,10 @@ long vfio_pci_core_ioctl(struct vfio_device *core_vdev, unsigned int cmd,
 }
 EXPORT_SYMBOL_GPL(vfio_pci_core_ioctl);
 
-static int vfio_pci_core_feature_token(struct vfio_device *device, u32 flags,
-				       uuid_t __user *arg, size_t argsz)
+static int vfio_pci_core_feature_token(struct vfio_pci_core_device *vdev,
+				       u32 flags, uuid_t __user *arg,
+				       size_t argsz)
 {
-	struct vfio_pci_core_device *vdev =
-		container_of(device, struct vfio_pci_core_device, vdev);
 	uuid_t uuid;
 	int ret;
 
@@ -1517,16 +1510,19 @@ static int vfio_pci_core_feature_token(struct vfio_device *device, u32 flags,
 int vfio_pci_core_ioctl_feature(struct vfio_device *device, u32 flags,
 				void __user *arg, size_t argsz)
 {
+	struct vfio_pci_core_device *vdev =
+		container_of(device, struct vfio_pci_core_device, vdev);
+
 	switch (flags & VFIO_DEVICE_FEATURE_MASK) {
 	case VFIO_DEVICE_FEATURE_LOW_POWER_ENTRY:
-		return vfio_pci_core_pm_entry(device, flags, arg, argsz);
+		return vfio_pci_core_pm_entry(vdev, flags, arg, argsz);
 	case VFIO_DEVICE_FEATURE_LOW_POWER_ENTRY_WITH_WAKEUP:
-		return vfio_pci_core_pm_entry_with_wakeup(device, flags,
+		return vfio_pci_core_pm_entry_with_wakeup(vdev, flags,
 							  arg, argsz);
 	case VFIO_DEVICE_FEATURE_LOW_POWER_EXIT:
-		return vfio_pci_core_pm_exit(device, flags, arg, argsz);
+		return vfio_pci_core_pm_exit(vdev, flags, arg, argsz);
 	case VFIO_DEVICE_FEATURE_PCI_VF_TOKEN:
-		return vfio_pci_core_feature_token(device, flags, arg, argsz);
+		return vfio_pci_core_feature_token(vdev, flags, arg, argsz);
 	default:
 		return -ENOTTY;
 	}

---

## [10] Xu Yilun — 2025-01-07
*Subject: [RFC PATCH 04/12] vfio/pci: Allow MMIO regions to be exported through dma-buf*

From: Vivek Kasireddy <vivek.kasireddy@intel.com>

This is a reduced version of Vivek's series [1]. Removed the
dma_buf_ops.attach/map/unmap_dma_buf/mmap() as they are not necessary
in this series, also because of the WIP p2p dma mapping opens [2]. Just
focus on the private MMIO get PFN function in this early stage.

>From Jason Gunthorpe:
"dma-buf has become a way to safely acquire a handle to non-struct page
memory that can still have lifetime controlled by the exporter. Notably
RDMA can now import dma-buf FDs and build them into MRs which allows for
PCI P2P operations. Extend this to allow vfio-pci to export MMIO memory
from PCI device BARs.

The patch design loosely follows the pattern in commit
db1a8dd916aa ("habanalabs: add support for dma-buf exporter") except this
does not support pinning.

Instead, this implements what, in the past, we've called a revocable
attachment using move. In normal situations the attachment is pinned, as a
BAR does not change physical address. However when the VFIO device is
closed, or a PCI reset is issued, access to the MMIO memory is revoked.

Revoked means that move occurs, but an attempt to immediately re-map the
memory will fail. In the reset case a future move will be triggered when
MMIO access returns. As both close and reset are under userspace control
it is expected that userspace will suspend use of the dma-buf before doing
these operations, the revoke is purely for kernel self-defense against a
hostile userspace."

[1] https://lore.kernel.org/kvm/20240624065552.1572580-4-vivek.kasireddy@intel.com/
[2] https://lore.kernel.org/all/IA0PR11MB7185FDD56CFDD0A2B8D21468F83B2@IA0PR11MB7185.namprd11.prod.outlook.com/

Original-patch-by: Jason Gunthorpe <jgg@nvidia.com>
Signed-off-by: Vivek Kasireddy <vivek.kasireddy@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/vfio/pci/Makefile          |   1 +
 drivers/vfio/pci/dma_buf.c         | 223 +++++++++++++++++++++++++++++
 drivers/vfio/pci/vfio_pci_config.c |  22 ++-
 drivers/vfio/pci/vfio_pci_core.c   |  20 ++-
 drivers/vfio/pci/vfio_pci_priv.h   |  25 ++++
 include/linux/vfio_pci_core.h      |   1 +
 include/uapi/linux/vfio.h          |  29 ++++
 7 files changed, 316 insertions(+), 5 deletions(-)
 create mode 100644 drivers/vfio/pci/dma_buf.c

diff --git a/drivers/vfio/pci/Makefile b/drivers/vfio/pci/Makefile
index cf00c0a7e55c..0cfdc9ede82f 100644
--- a/drivers/vfio/pci/Makefile
+++ b/drivers/vfio/pci/Makefile
@@ -2,6 +2,7 @@
 
 vfio-pci-core-y := vfio_pci_core.o vfio_pci_intrs.o vfio_pci_rdwr.o vfio_pci_config.o
 vfio-pci-core-$(CONFIG_VFIO_PCI_ZDEV_KVM) += vfio_pci_zdev.o
+vfio-pci-core-$(CONFIG_DMA_SHARED_BUFFER) += dma_buf.o
 obj-$(CONFIG_VFIO_PCI_CORE) += vfio-pci-core.o
 
 vfio-pci-y := vfio_pci.o
diff --git a/drivers/vfio/pci/dma_buf.c b/drivers/vfio/pci/dma_buf.c
new file mode 100644
index 000000000000..1d5f46744922
--- /dev/null
+++ b/drivers/vfio/pci/dma_buf.c
@@ -0,0 +1,223 @@
+// SPDX-License-Identifier: GPL-2.0-only
+/* Copyright (c) 2024, NVIDIA CORPORATION & AFFILIATES.
+ */
+#include <linux/dma-buf.h>
+#include <linux/dma-resv.h>
+
+#include "vfio_pci_priv.h"
+
+MODULE_IMPORT_NS("DMA_BUF");
+
+struct vfio_pci_dma_buf {
+	struct dma_buf *dmabuf;
+	struct vfio_pci_core_device *vdev;
+	struct list_head dmabufs_elm;
+	unsigned int nr_ranges;
+	struct vfio_region_dma_range *dma_ranges;
+	bool revoked;
+};
+
+static void vfio_pci_dma_buf_unpin(struct dma_buf_attachment *attachment)
+{
+}
+
+static int vfio_pci_dma_buf_pin(struct dma_buf_attachment *attachment)
+{
+	/*
+	 * Uses the dynamic interface but must always allow for
+	 * dma_buf_move_notify() to do revoke
+	 */
+	return -EINVAL;
+}
+
+static int vfio_pci_dma_buf_get_pfn(struct dma_buf_attachment *attachment,
+				    pgoff_t pgoff, u64 *pfn, int *max_order)
+{
+	/* TODO */
+	return -EOPNOTSUPP;
+}
+
+static void vfio_pci_dma_buf_release(struct dma_buf *dmabuf)
+{
+	struct vfio_pci_dma_buf *priv = dmabuf->priv;
+
+	/*
+	 * Either this or vfio_pci_dma_buf_cleanup() will remove from the list.
+	 * The refcount prevents both.
+	 */
+	if (priv->vdev) {
+		down_write(&priv->vdev->memory_lock);
+		list_del_init(&priv->dmabufs_elm);
+		up_write(&priv->vdev->memory_lock);
+		vfio_device_put_registration(&priv->vdev->vdev);
+	}
+	kfree(priv);
+}
+
+static const struct dma_buf_ops vfio_pci_dmabuf_ops = {
+	.pin = vfio_pci_dma_buf_pin,
+	.unpin = vfio_pci_dma_buf_unpin,
+	.get_pfn = vfio_pci_dma_buf_get_pfn,
+	.release = vfio_pci_dma_buf_release,
+};
+
+static int check_dma_ranges(struct vfio_pci_dma_buf *priv, u64 *dmabuf_size)
+{
+	struct vfio_region_dma_range *dma_ranges = priv->dma_ranges;
+	struct pci_dev *pdev = priv->vdev->pdev;
+	resource_size_t bar_size;
+	int i;
+
+	for (i = 0; i < priv->nr_ranges; i++) {
+		/*
+		 * For PCI the region_index is the BAR number like
+		 * everything else.
+		 */
+		if (dma_ranges[i].region_index >= VFIO_PCI_ROM_REGION_INDEX)
+			return -EINVAL;
+
+		bar_size = pci_resource_len(pdev, dma_ranges[i].region_index);
+		if (!bar_size)
+			return -EINVAL;
+
+		if (!dma_ranges[i].offset && !dma_ranges[i].length)
+			dma_ranges[i].length = bar_size;
+
+		if (!IS_ALIGNED(dma_ranges[i].offset, PAGE_SIZE) ||
+		    !IS_ALIGNED(dma_ranges[i].length, PAGE_SIZE) ||
+		    dma_ranges[i].length > bar_size ||
+		    dma_ranges[i].offset >= bar_size ||
+		    dma_ranges[i].offset + dma_ranges[i].length > bar_size)
+			return -EINVAL;
+
+		*dmabuf_size += dma_ranges[i].length;
+	}
+
+	return 0;
+}
+
+int vfio_pci_core_feature_dma_buf(struct vfio_pci_core_device *vdev, u32 flags,
+				  struct vfio_device_feature_dma_buf __user *arg,
+				  size_t argsz)
+{
+	struct vfio_device_feature_dma_buf get_dma_buf;
+	struct vfio_region_dma_range *dma_ranges;
+	DEFINE_DMA_BUF_EXPORT_INFO(exp_info);
+	struct vfio_pci_dma_buf *priv;
+	u64 dmabuf_size = 0;
+	int ret;
+
+	ret = vfio_check_feature(flags, argsz, VFIO_DEVICE_FEATURE_GET,
+				 sizeof(get_dma_buf));
+	if (ret != 1)
+		return ret;
+
+	if (copy_from_user(&get_dma_buf, arg, sizeof(get_dma_buf)))
+		return -EFAULT;
+
+	dma_ranges = memdup_array_user(&arg->dma_ranges,
+				       get_dma_buf.nr_ranges,
+				       sizeof(*dma_ranges));
+	if (IS_ERR(dma_ranges))
+		return PTR_ERR(dma_ranges);
+
+	priv = kzalloc(sizeof(*priv), GFP_KERNEL);
+	if (!priv) {
+		kfree(dma_ranges);
+		return -ENOMEM;
+	}
+
+	priv->vdev = vdev;
+	priv->nr_ranges = get_dma_buf.nr_ranges;
+	priv->dma_ranges = dma_ranges;
+
+	ret = check_dma_ranges(priv, &dmabuf_size);
+	if (ret)
+		goto err_free_priv;
+
+	if (!vfio_device_try_get_registration(&vdev->vdev)) {
+		ret = -ENODEV;
+		goto err_free_priv;
+	}
+
+	exp_info.ops = &vfio_pci_dmabuf_ops;
+	exp_info.size = dmabuf_size;
+	exp_info.flags = get_dma_buf.open_flags;
+	exp_info.priv = priv;
+
+	priv->dmabuf = dma_buf_export(&exp_info);
+	if (IS_ERR(priv->dmabuf)) {
+		ret = PTR_ERR(priv->dmabuf);
+		goto err_dev_put;
+	}
+
+	/* dma_buf_put() now frees priv */
+	INIT_LIST_HEAD(&priv->dmabufs_elm);
+	down_write(&vdev->memory_lock);
+	dma_resv_lock(priv->dmabuf->resv, NULL);
+	priv->revoked = !__vfio_pci_memory_enabled(vdev);
+	list_add_tail(&priv->dmabufs_elm, &vdev->dmabufs);
+	dma_resv_unlock(priv->dmabuf->resv);
+	up_write(&vdev->memory_lock);
+
+	/*
+	 * dma_buf_fd() consumes the reference, when the file closes the dmabuf
+	 * will be released.
+	 */
+	return dma_buf_fd(priv->dmabuf, get_dma_buf.open_flags);
+
+err_dev_put:
+	vfio_device_put_registration(&vdev->vdev);
+err_free_priv:
+	kfree(dma_ranges);
+	kfree(priv);
+	return ret;
+}
+
+void vfio_pci_dma_buf_move(struct vfio_pci_core_device *vdev, bool revoked)
+{
+	struct vfio_pci_dma_buf *priv;
+	struct vfio_pci_dma_buf *tmp;
+
+	lockdep_assert_held_write(&vdev->memory_lock);
+
+	list_for_each_entry_safe(priv, tmp, &vdev->dmabufs, dmabufs_elm) {
+		/*
+		 * Returns true if a reference was successfully obtained.
+		 * The caller must interlock with the dmabuf's release
+		 * function in some way, such as RCU, to ensure that this
+		 * is not called on freed memory.
+		 */
+		if (!get_file_rcu(&priv->dmabuf->file))
+			continue;
+
+		if (priv->revoked != revoked) {
+			dma_resv_lock(priv->dmabuf->resv, NULL);
+			priv->revoked = revoked;
+			dma_buf_move_notify(priv->dmabuf);
+			dma_resv_unlock(priv->dmabuf->resv);
+		}
+		dma_buf_put(priv->dmabuf);
+	}
+}
+
+void vfio_pci_dma_buf_cleanup(struct vfio_pci_core_device *vdev)
+{
+	struct vfio_pci_dma_buf *priv;
+	struct vfio_pci_dma_buf *tmp;
+
+	down_write(&vdev->memory_lock);
+	list_for_each_entry_safe(priv, tmp, &vdev->dmabufs, dmabufs_elm) {
+		if (!get_file_rcu(&priv->dmabuf->file))
+			continue;
+		dma_resv_lock(priv->dmabuf->resv, NULL);
+		list_del_init(&priv->dmabufs_elm);
+		priv->vdev = NULL;
+		priv->revoked = true;
+		dma_buf_move_notify(priv->dmabuf);
+		dma_resv_unlock(priv->dmabuf->resv);
+		vfio_device_put_registration(&vdev->vdev);
+		dma_buf_put(priv->dmabuf);
+	}
+	up_write(&vdev->memory_lock);
+}
diff --git a/drivers/vfio/pci/vfio_pci_config.c b/drivers/vfio/pci/vfio_pci_config.c
index ea2745c1ac5e..5cc200e15edc 100644
--- a/drivers/vfio/pci/vfio_pci_config.c
+++ b/drivers/vfio/pci/vfio_pci_config.c
@@ -589,10 +589,12 @@ static int vfio_basic_config_write(struct vfio_pci_core_device *vdev, int pos,
 		virt_mem = !!(le16_to_cpu(*virt_cmd) & PCI_COMMAND_MEMORY);
 		new_mem = !!(new_cmd & PCI_COMMAND_MEMORY);
 
-		if (!new_mem)
+		if (!new_mem) {
 			vfio_pci_zap_and_down_write_memory_lock(vdev);
-		else
+			vfio_pci_dma_buf_move(vdev, true);
+		} else {
 			down_write(&vdev->memory_lock);
+		}
 
 		/*
 		 * If the user is writing mem/io enable (new_mem/io) and we
@@ -627,6 +629,8 @@ static int vfio_basic_config_write(struct vfio_pci_core_device *vdev, int pos,
 		*virt_cmd &= cpu_to_le16(~mask);
 		*virt_cmd |= cpu_to_le16(new_cmd & mask);
 
+		if (__vfio_pci_memory_enabled(vdev))
+			vfio_pci_dma_buf_move(vdev, false);
 		up_write(&vdev->memory_lock);
 	}
 
@@ -707,12 +711,16 @@ static int __init init_pci_cap_basic_perm(struct perm_bits *perm)
 static void vfio_lock_and_set_power_state(struct vfio_pci_core_device *vdev,
 					  pci_power_t state)
 {
-	if (state >= PCI_D3hot)
+	if (state >= PCI_D3hot) {
 		vfio_pci_zap_and_down_write_memory_lock(vdev);
-	else
+		vfio_pci_dma_buf_move(vdev, true);
+	} else {
 		down_write(&vdev->memory_lock);
+	}
 
 	vfio_pci_set_power_state(vdev, state);
+	if (__vfio_pci_memory_enabled(vdev))
+		vfio_pci_dma_buf_move(vdev, false);
 	up_write(&vdev->memory_lock);
 }
 
@@ -900,7 +908,10 @@ static int vfio_exp_config_write(struct vfio_pci_core_device *vdev, int pos,
 
 		if (!ret && (cap & PCI_EXP_DEVCAP_FLR)) {
 			vfio_pci_zap_and_down_write_memory_lock(vdev);
+			vfio_pci_dma_buf_move(vdev, true);
 			pci_try_reset_function(vdev->pdev);
+			if (__vfio_pci_memory_enabled(vdev))
+				vfio_pci_dma_buf_move(vdev, true);
 			up_write(&vdev->memory_lock);
 		}
 	}
@@ -982,7 +993,10 @@ static int vfio_af_config_write(struct vfio_pci_core_device *vdev, int pos,
 
 		if (!ret && (cap & PCI_AF_CAP_FLR) && (cap & PCI_AF_CAP_TP)) {
 			vfio_pci_zap_and_down_write_memory_lock(vdev);
+			vfio_pci_dma_buf_move(vdev, true);
 			pci_try_reset_function(vdev->pdev);
+			if (__vfio_pci_memory_enabled(vdev))
+				vfio_pci_dma_buf_move(vdev, true);
 			up_write(&vdev->memory_lock);
 		}
 	}
diff --git a/drivers/vfio/pci/vfio_pci_core.c b/drivers/vfio/pci/vfio_pci_core.c
index c3269d708411..f69eda5956ad 100644
--- a/drivers/vfio/pci/vfio_pci_core.c
+++ b/drivers/vfio/pci/vfio_pci_core.c
@@ -287,6 +287,8 @@ static int vfio_pci_runtime_pm_entry(struct vfio_pci_core_device *vdev,
 	 * semaphore.
 	 */
 	vfio_pci_zap_and_down_write_memory_lock(vdev);
+	vfio_pci_dma_buf_move(vdev, true);
+
 	if (vdev->pm_runtime_engaged) {
 		up_write(&vdev->memory_lock);
 		return -EINVAL;
@@ -370,6 +372,8 @@ static void vfio_pci_runtime_pm_exit(struct vfio_pci_core_device *vdev)
 	 */
 	down_write(&vdev->memory_lock);
 	__vfio_pci_runtime_pm_exit(vdev);
+	if (__vfio_pci_memory_enabled(vdev))
+		vfio_pci_dma_buf_move(vdev, false);
 	up_write(&vdev->memory_lock);
 }
 
@@ -690,6 +694,8 @@ void vfio_pci_core_close_device(struct vfio_device *core_vdev)
 #endif
 	vfio_pci_core_disable(vdev);
 
+	vfio_pci_dma_buf_cleanup(vdev);
+
 	mutex_lock(&vdev->igate);
 	if (vdev->err_trigger) {
 		eventfd_ctx_put(vdev->err_trigger);
@@ -1234,7 +1240,10 @@ static int vfio_pci_ioctl_reset(struct vfio_pci_core_device *vdev,
 	 */
 	vfio_pci_set_power_state(vdev, PCI_D0);
 
+	vfio_pci_dma_buf_move(vdev, true);
 	ret = pci_try_reset_function(vdev->pdev);
+	if (__vfio_pci_memory_enabled(vdev))
+		vfio_pci_dma_buf_move(vdev, false);
 	up_write(&vdev->memory_lock);
 
 	return ret;
@@ -1523,6 +1532,8 @@ int vfio_pci_core_ioctl_feature(struct vfio_device *device, u32 flags,
 		return vfio_pci_core_pm_exit(vdev, flags, arg, argsz);
 	case VFIO_DEVICE_FEATURE_PCI_VF_TOKEN:
 		return vfio_pci_core_feature_token(vdev, flags, arg, argsz);
+	case VFIO_DEVICE_FEATURE_DMA_BUF:
+		return vfio_pci_core_feature_dma_buf(vdev, flags, arg, argsz);
 	default:
 		return -ENOTTY;
 	}
@@ -2098,6 +2109,7 @@ int vfio_pci_core_init_dev(struct vfio_device *core_vdev)
 	INIT_LIST_HEAD(&vdev->dummy_resources_list);
 	INIT_LIST_HEAD(&vdev->ioeventfds_list);
 	INIT_LIST_HEAD(&vdev->sriov_pfs_item);
+	INIT_LIST_HEAD(&vdev->dmabufs);
 	init_rwsem(&vdev->memory_lock);
 	xa_init(&vdev->ctx);
 
@@ -2480,11 +2492,17 @@ static int vfio_pci_dev_set_hot_reset(struct vfio_device_set *dev_set,
 	 * cause the PCI config space reset without restoring the original
 	 * state (saved locally in 'vdev->pm_save').
 	 */
-	list_for_each_entry(vdev, &dev_set->device_list, vdev.dev_set_list)
+	list_for_each_entry(vdev, &dev_set->device_list, vdev.dev_set_list) {
+		vfio_pci_dma_buf_move(vdev, true);
 		vfio_pci_set_power_state(vdev, PCI_D0);
+	}
 
 	ret = pci_reset_bus(pdev);
 
+	list_for_each_entry(vdev, &dev_set->device_list, vdev.dev_set_list)
+		if (__vfio_pci_memory_enabled(vdev))
+			vfio_pci_dma_buf_move(vdev, false);
+
 	vdev = list_last_entry(&dev_set->device_list,
 			       struct vfio_pci_core_device, vdev.dev_set_list);
 
diff --git a/drivers/vfio/pci/vfio_pci_priv.h b/drivers/vfio/pci/vfio_pci_priv.h
index 5e4fa69aee16..d27f383f3931 100644
--- a/drivers/vfio/pci/vfio_pci_priv.h
+++ b/drivers/vfio/pci/vfio_pci_priv.h
@@ -101,4 +101,29 @@ static inline bool vfio_pci_is_vga(struct pci_dev *pdev)
 	return (pdev->class >> 8) == PCI_CLASS_DISPLAY_VGA;
 }
 
+#ifdef CONFIG_DMA_SHARED_BUFFER
+int vfio_pci_core_feature_dma_buf(struct vfio_pci_core_device *vdev, u32 flags,
+				  struct vfio_device_feature_dma_buf __user *arg,
+				  size_t argsz);
+void vfio_pci_dma_buf_cleanup(struct vfio_pci_core_device *vdev);
+void vfio_pci_dma_buf_move(struct vfio_pci_core_device *vdev, bool revoked);
+#else
+static int
+vfio_pci_core_feature_dma_buf(struct vfio_pci_core_device *vdev, u32 flags,
+			      struct vfio_device_feature_dma_buf __user *arg,
+			      size_t argsz)
+{
+	return -ENOTTY;
+}
+
+static inline void vfio_pci_dma_buf_cleanup(struct vfio_pci_core_device *vdev)
+{
+}
+
+static inline void vfio_pci_dma_buf_move(struct vfio_pci_core_device *vdev,
+					 bool revoked)
+{
+}
+#endif
+
 #endif
diff --git a/include/linux/vfio_pci_core.h b/include/linux/vfio_pci_core.h
index fbb472dd99b3..da5d8955ae56 100644
--- a/include/linux/vfio_pci_core.h
+++ b/include/linux/vfio_pci_core.h
@@ -94,6 +94,7 @@ struct vfio_pci_core_device {
 	struct vfio_pci_core_device	*sriov_pf_core_dev;
 	struct notifier_block	nb;
 	struct rw_semaphore	memory_lock;
+	struct list_head	dmabufs;
 };
 
 /* Will be exported for vfio pci drivers usage */
diff --git a/include/uapi/linux/vfio.h b/include/uapi/linux/vfio.h
index c8dbf8219c4f..f43dfbde7352 100644
--- a/include/uapi/linux/vfio.h
+++ b/include/uapi/linux/vfio.h
@@ -1458,6 +1458,35 @@ struct vfio_device_feature_bus_master {
 };
 #define VFIO_DEVICE_FEATURE_BUS_MASTER 10
 
+/**
+ * Upon VFIO_DEVICE_FEATURE_GET create a dma_buf fd for the
+ * regions selected.
+ *
+ * For struct struct vfio_device_feature_dma_buf, open_flags are the typical
+ * flags passed to open(2), eg O_RDWR, O_CLOEXEC, etc. nr_ranges is the total
+ * number of dma_ranges that comprise the dmabuf.
+ *
+ * For struct vfio_region_dma_range, region_index/offset/length specify a slice
+ * of the region to create the dmabuf from, if both offset & length are 0 then
+ * the whole region is used.
+ *
+ * Return: The fd number on success, -1 and errno is set on failure.
+ */
+struct vfio_region_dma_range {
+	__u32	region_index;
+	__u32	__pad;
+	__u64	offset;
+	__u64	length;
+};
+
+struct vfio_device_feature_dma_buf {
+	__u32	open_flags;
+	__u32	nr_ranges;
+	struct vfio_region_dma_range dma_ranges[];
+};
+
+#define VFIO_DEVICE_FEATURE_DMA_BUF 11
+
 /* -------- API for Type1 VFIO IOMMU -------- */
 
 /**

---

## [11] Xu Yilun — 2025-01-07
*Subject: [RFC PATCH 05/12] vfio/pci: Support get_pfn() callback for dma-buf*

Implement get_pfn() callback for exported MMIO resources.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/vfio/pci/dma_buf.c | 30 ++++++++++++++++++++++++++++--
 1 file changed, 28 insertions(+), 2 deletions(-)

diff --git a/drivers/vfio/pci/dma_buf.c b/drivers/vfio/pci/dma_buf.c
index 1d5f46744922..ad12cfb85099 100644
--- a/drivers/vfio/pci/dma_buf.c
+++ b/drivers/vfio/pci/dma_buf.c
@@ -33,8 +33,34 @@ static int vfio_pci_dma_buf_pin(struct dma_buf_attachment *attachment)
 static int vfio_pci_dma_buf_get_pfn(struct dma_buf_attachment *attachment,
 				    pgoff_t pgoff, u64 *pfn, int *max_order)
 {
-	/* TODO */
-	return -EOPNOTSUPP;
+	struct vfio_pci_dma_buf *priv = attachment->dmabuf->priv;
+	struct vfio_region_dma_range *dma_ranges = priv->dma_ranges;
+	u64 offset = pgoff << PAGE_SHIFT;
+	int i;
+
+	dma_resv_assert_held(priv->dmabuf->resv);
+
+	if (priv->revoked)
+		return -ENODEV;
+
+	if (offset >= priv->dmabuf->size)
+		return -EINVAL;
+
+	for (i = 0; i < priv->nr_ranges; i++) {
+		if (offset < dma_ranges[i].length)
+			break;
+
+		offset -= dma_ranges[i].length;
+	}
+
+	*pfn = PHYS_PFN(pci_resource_start(priv->vdev->pdev, dma_ranges[i].region_index) +
+			dma_ranges[i].offset + offset);
+
+	/* TODO: large page mapping is yet to be supported */
+	if (max_order)
+		*max_order = 0;
+
+	return 0;
 }
 
 static void vfio_pci_dma_buf_release(struct dma_buf *dmabuf)

---

## [12] Xu Yilun — 2025-01-07
*Subject: [RFC PATCH 06/12] KVM: Support vfio_dmabuf backed MMIO region*

Extend KVM_SET_USER_MEMORY_REGION2 to support mapping vfio_dmabuf
backed MMIO region into a guest.

The main purpose of this change is for KVM to map MMIO resources
without firstly mapping into the host, similar to what is done in
guest_memfd. The immediate use case is for CoCo VMs to support private
MMIO.

Similar to private guest memory, private MMIO is also not intended to be
accessed by host. The host access to private MMIO would be rejected by
private devices (known as TDI in TDISP spec) and cause the TDI exit the
secure state. The further impact to the system may vary according to
device implementation. The TDISP spec doesn't mandate any error
reporting or logging, the TLP may be handled as an Unsupported Request,
or just be dropped. In my test environment, an AER NonFatalErr is
reported and no further impact. So from HW perspective, disallowing
host access to private MMIO is not that critical but nice to have.

But stick to find pfn via userspace mapping while allowing the pfn been
privately mapped conflicts with the private mapping concept. And it
virtually allows userspace to map any address as private. Before
fault in, KVM cannot distinguish if a userspace addr is for private
MMIO and safe to host access.

Rely on userspace mapping also means private MMIO mapping should follow
userspace mapping change via mmu_notifier. This conflicts with the
current design that mmu_notifier never impacts private mapping. It also
makes no sense to support mmu_notifier just for private MMIO, private
MMIO mapping should be fixed when CoCo-VM accepts the private MMIO, any
following mapping change without guest permission should be invalid.

So the choice here is to eliminate userspace mapping and switch to use
the FD based MMIO resources.

There is still need to switch the memory attribute (shared <-> private)
for private MMIO, when guest switches the device attribute between
shared & private. Unlike memory, MMIO region has only one physical
backend so it is a bit like in-place conversion, which for private
memory, requires much effort on how to invalidate user mapping when
converting to private. But for MMIO, it is expected that VMM never
needs to access assigned MMIO for feature emulation, so always disallow
userspace MMIO mapping and use FD based MMIO resources for 'private
capable' MMIO region.

The dma-buf is chosen as the FD based backend, it meets the need for KVM
to aquire the non-struct page memory that can still have lifetime
controlled by VFIO. It provides the option to disallow userspace mmap as
long as the exporter doesn't provide dma_buf_ops.mmap() callback. The
concern is it now just supports mapping into device's default_domain via
DMA APIs. Some clue I can found to extend dma-buf APIs for subsystems
like IOMMUFD [1] or KVM. The adding of dma_buf_get_pfn_unlocked() in this
series is for this purpose.

An alternative is VFIO provides a dedicated FD for KVM. But considering
IOMMUFD may use dma-buf for MMIO mapping [2], it is better to have a
unified export mechanism for the same purpose in VFIO.

Open: Currently store the dmabuf fd parameter in
kvm_userspace_memory_region2::guest_memfd. It may be confusing but avoids
introducing another API format for IOCTL(KVM_SET_USER_MEMORY_REGION3).

[1] https://lore.kernel.org/all/YwywgciH6BiWz4H1@nvidia.com/
[2] https://lore.kernel.org/kvm/14-v4-0de2f6c78ed0+9d1-iommufd_jgg@nvidia.com/

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 Documentation/virt/kvm/api.rst |   7 ++
 include/linux/kvm_host.h       |  18 +++++
 include/uapi/linux/kvm.h       |   1 +
 virt/kvm/Kconfig               |   6 ++
 virt/kvm/Makefile.kvm          |   1 +
 virt/kvm/kvm_main.c            |  32 +++++++--
 virt/kvm/kvm_mm.h              |  19 +++++
 virt/kvm/vfio_dmabuf.c         | 125 +++++++++++++++++++++++++++++++++
 8 files changed, 205 insertions(+), 4 deletions(-)
 create mode 100644 virt/kvm/vfio_dmabuf.c

diff --git a/Documentation/virt/kvm/api.rst b/Documentation/virt/kvm/api.rst
index 7911da34b9fd..f6199764a768 100644
--- a/Documentation/virt/kvm/api.rst
+++ b/Documentation/virt/kvm/api.rst
@@ -6304,6 +6304,13 @@ state.  At VM creation time, all memory is shared, i.e. the PRIVATE attribute
 is '0' for all gfns.  Userspace can control whether memory is shared/private by
 toggling KVM_MEMORY_ATTRIBUTE_PRIVATE via KVM_SET_MEMORY_ATTRIBUTES as needed.
 
+Userspace can set KVM_MEM_VFIO_DMABUF in flags to indicate the memory region is
+backed by a userspace unmappable dma_buf exported by VFIO. The backend resource
+is one piece of MMIO region of the device. The slot is unmappable so it is
+allowed to be converted to private. KVM binds the memory region to a given
+dma_buf fd range of [0, memory_size]. For now, the dma_buf fd is filled in
+'guest_memfd' field, and the guest_memfd_offset must be 0;
+
 S390:
 ^^^^^
 
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index 0a141685872d..871d927485a5 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -606,6 +606,10 @@ struct kvm_memory_slot {
 		pgoff_t pgoff;
 	} gmem;
 #endif
+
+#ifdef CONFIG_KVM_VFIO_DMABUF
+	struct dma_buf_attachment *dmabuf_attach;
+#endif
 };
 
 static inline bool kvm_slot_can_be_private(const struct kvm_memory_slot *slot)
@@ -2568,4 +2572,18 @@ static inline int kvm_enable_virtualization(void) { return 0; }
 static inline void kvm_disable_virtualization(void) { }
 #endif
 
+#ifdef CONFIG_KVM_VFIO_DMABUF
+int kvm_vfio_dmabuf_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
+			    gfn_t gfn, kvm_pfn_t *pfn, int *max_order);
+#else
+static inline int kvm_vfio_dmabuf_get_pfn(struct kvm *kvm,
+					  struct kvm_memory_slot *slot,
+					  gfn_t gfn, kvm_pfn_t *pfn,
+					  int *max_order);
+{
+	KVM_BUG_ON(1, kvm);
+	return -EIO;
+}
+#endif
+
 #endif
diff --git a/include/uapi/linux/kvm.h b/include/uapi/linux/kvm.h
index 1dae36cbfd52..4f5b5def182a 100644
--- a/include/uapi/linux/kvm.h
+++ b/include/uapi/linux/kvm.h
@@ -51,6 +51,7 @@ struct kvm_userspace_memory_region2 {
 #define KVM_MEM_LOG_DIRTY_PAGES	(1UL << 0)
 #define KVM_MEM_READONLY	(1UL << 1)
 #define KVM_MEM_GUEST_MEMFD	(1UL << 2)
+#define KVM_MEM_VFIO_DMABUF	(1UL << 3)
 
 /* for KVM_IRQ_LINE */
 struct kvm_irq_level {
diff --git a/virt/kvm/Kconfig b/virt/kvm/Kconfig
index 54e959e7d68f..68fff3fb1841 100644
--- a/virt/kvm/Kconfig
+++ b/virt/kvm/Kconfig
@@ -115,6 +115,7 @@ config KVM_PRIVATE_MEM
 config KVM_GENERIC_PRIVATE_MEM
        select KVM_GENERIC_MEMORY_ATTRIBUTES
        select KVM_PRIVATE_MEM
+       select KVM_VFIO_DMABUF
        bool
 
 config HAVE_KVM_ARCH_GMEM_PREPARE
@@ -124,3 +125,8 @@ config HAVE_KVM_ARCH_GMEM_PREPARE
 config HAVE_KVM_ARCH_GMEM_INVALIDATE
        bool
        depends on KVM_PRIVATE_MEM
+
+config KVM_VFIO_DMABUF
+       bool
+       select DMA_SHARED_BUFFER
+       select DMABUF_MOVE_NOTIFY
diff --git a/virt/kvm/Makefile.kvm b/virt/kvm/Makefile.kvm
index 724c89af78af..c08e98f13f65 100644
--- a/virt/kvm/Makefile.kvm
+++ b/virt/kvm/Makefile.kvm
@@ -13,3 +13,4 @@ kvm-$(CONFIG_HAVE_KVM_IRQ_ROUTING) += $(KVM)/irqchip.o
 kvm-$(CONFIG_HAVE_KVM_DIRTY_RING) += $(KVM)/dirty_ring.o
 kvm-$(CONFIG_HAVE_KVM_PFNCACHE) += $(KVM)/pfncache.o
 kvm-$(CONFIG_KVM_PRIVATE_MEM) += $(KVM)/guest_memfd.o
+kvm-$(CONFIG_KVM_VFIO_DMABUF) += $(KVM)/vfio_dmabuf.o
diff --git a/virt/kvm/kvm_main.c b/virt/kvm/kvm_main.c
index 4a13de82479d..c9342d88f06c 100644
--- a/virt/kvm/kvm_main.c
+++ b/virt/kvm/kvm_main.c
@@ -938,6 +938,8 @@ static void kvm_free_memslot(struct kvm *kvm, struct kvm_memory_slot *slot)
 {
 	if (slot->flags & KVM_MEM_GUEST_MEMFD)
 		kvm_gmem_unbind(slot);
+	else if (slot->flags & KVM_MEM_VFIO_DMABUF)
+		kvm_vfio_dmabuf_unbind(slot);
 
 	kvm_destroy_dirty_bitmap(slot);
 
@@ -1526,13 +1528,19 @@ static void kvm_replace_memslot(struct kvm *kvm,
 static int check_memory_region_flags(struct kvm *kvm,
 				     const struct kvm_userspace_memory_region2 *mem)
 {
+	u32 private_mask = KVM_MEM_GUEST_MEMFD | KVM_MEM_VFIO_DMABUF;
+	u32 private_flag = mem->flags & private_mask;
 	u32 valid_flags = KVM_MEM_LOG_DIRTY_PAGES;
 
+	/* private flags are mutually exclusive. */
+	if (private_flag & (private_flag - 1))
+		return -EINVAL;
+
 	if (kvm_arch_has_private_mem(kvm))
-		valid_flags |= KVM_MEM_GUEST_MEMFD;
+		valid_flags |= private_flag;
 
 	/* Dirty logging private memory is not currently supported. */
-	if (mem->flags & KVM_MEM_GUEST_MEMFD)
+	if (private_flag)
 		valid_flags &= ~KVM_MEM_LOG_DIRTY_PAGES;
 
 	/*
@@ -1540,8 +1548,7 @@ static int check_memory_region_flags(struct kvm *kvm,
 	 * read-only memslots have emulated MMIO, not page fault, semantics,
 	 * and KVM doesn't allow emulated MMIO for private memory.
 	 */
-	if (kvm_arch_has_readonly_mem(kvm) &&
-	    !(mem->flags & KVM_MEM_GUEST_MEMFD))
+	if (kvm_arch_has_readonly_mem(kvm) && !private_flag)
 		valid_flags |= KVM_MEM_READONLY;
 
 	if (mem->flags & ~valid_flags)
@@ -2044,6 +2051,21 @@ int __kvm_set_memory_region(struct kvm *kvm,
 		r = kvm_gmem_bind(kvm, new, mem->guest_memfd, mem->guest_memfd_offset);
 		if (r)
 			goto out;
+	} else if (mem->flags & KVM_MEM_VFIO_DMABUF) {
+		if (mem->guest_memfd_offset) {
+			r = -EINVAL;
+			goto out;
+		}
+
+		/*
+		 * Open: May be confusing that store the dmabuf fd parameter in
+		 * kvm_userspace_memory_region2::guest_memfd. But this avoids
+		 * introducing another format for
+		 * IOCTL(KVM_SET_USER_MEMORY_REGIONX).
+		 */
+		r = kvm_vfio_dmabuf_bind(kvm, new, mem->guest_memfd);
+		if (r)
+			goto out;
 	}
 
 	r = kvm_set_memslot(kvm, old, new, change);
@@ -2055,6 +2077,8 @@ int __kvm_set_memory_region(struct kvm *kvm,
 out_unbind:
 	if (mem->flags & KVM_MEM_GUEST_MEMFD)
 		kvm_gmem_unbind(new);
+	else if (mem->flags & KVM_MEM_VFIO_DMABUF)
+		kvm_vfio_dmabuf_unbind(new);
 out:
 	kfree(new);
 	return r;
diff --git a/virt/kvm/kvm_mm.h b/virt/kvm/kvm_mm.h
index acef3f5c582a..faefc252c337 100644
--- a/virt/kvm/kvm_mm.h
+++ b/virt/kvm/kvm_mm.h
@@ -93,4 +93,23 @@ static inline void kvm_gmem_unbind(struct kvm_memory_slot *slot)
 }
 #endif /* CONFIG_KVM_PRIVATE_MEM */
 
+#ifdef CONFIG_KVM_VFIO_DMABUF
+int kvm_vfio_dmabuf_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
+			 unsigned int fd);
+void kvm_vfio_dmabuf_unbind(struct kvm_memory_slot *slot);
+#else
+static inline int kvm_vfio_dmabuf_bind(struct kvm *kvm,
+				       struct kvm_memory_slot *slot,
+				       unsigned int fd);
+{
+	WARN_ON_ONCE(1);
+	return -EIO;
+}
+
+static inline void kvm_vfio_dmabuf_unbind(struct kvm_memory_slot *slot)
+{
+	WARN_ON_ONCE(1);
+}
+#endif /* CONFIG_KVM_VFIO_DMABUF */
+
 #endif /* __KVM_MM_H__ */
diff --git a/virt/kvm/vfio_dmabuf.c b/virt/kvm/vfio_dmabuf.c
new file mode 100644
index 000000000000..c427ab39c68a
--- /dev/null
+++ b/virt/kvm/vfio_dmabuf.c
@@ -0,0 +1,125 @@
+// SPDX-License-Identifier: GPL-2.0
+#include <linux/dma-buf.h>
+#include <linux/kvm_host.h>
+#include <linux/vfio.h>
+
+#include "kvm_mm.h"
+
+MODULE_IMPORT_NS("DMA_BUF");
+
+struct kvm_vfio_dmabuf {
+	struct kvm *kvm;
+	struct kvm_memory_slot *slot;
+};
+
+static void kv_dmabuf_move_notify(struct dma_buf_attachment *attach)
+{
+	struct kvm_vfio_dmabuf *kv_dmabuf = attach->importer_priv;
+	struct kvm_memory_slot *slot = kv_dmabuf->slot;
+	struct kvm *kvm = kv_dmabuf->kvm;
+	bool flush = false;
+
+	struct kvm_gfn_range gfn_range = {
+		.start = slot->base_gfn,
+		.end = slot->base_gfn + slot->npages,
+		.slot = slot,
+		.may_block = true,
+		.attr_filter = KVM_FILTER_PRIVATE | KVM_FILTER_SHARED,
+	};
+
+	KVM_MMU_LOCK(kvm);
+	kvm_mmu_invalidate_begin(kvm);
+	flush |= kvm_mmu_unmap_gfn_range(kvm, &gfn_range);
+	if (flush)
+		kvm_flush_remote_tlbs(kvm);
+
+	kvm_mmu_invalidate_end(kvm);
+	KVM_MMU_UNLOCK(kvm);
+}
+
+static const struct dma_buf_attach_ops kv_dmabuf_attach_ops = {
+	.allow_peer2peer = true,
+	.move_notify = kv_dmabuf_move_notify,
+};
+
+int kvm_vfio_dmabuf_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
+			 unsigned int fd)
+{
+	size_t size = slot->npages << PAGE_SHIFT;
+	struct dma_buf_attachment *attach;
+	struct kvm_vfio_dmabuf *kv_dmabuf;
+	struct dma_buf *dmabuf;
+	int ret;
+
+	dmabuf = dma_buf_get(fd);
+	if (IS_ERR(dmabuf))
+		return PTR_ERR(dmabuf);
+
+	if (size != dmabuf->size) {
+		ret = -EINVAL;
+		goto err_dmabuf;
+	}
+
+	kv_dmabuf = kzalloc(sizeof(*kv_dmabuf), GFP_KERNEL);
+	if (!kv_dmabuf) {
+		ret = -ENOMEM;
+		goto err_dmabuf;
+	}
+
+	kv_dmabuf->kvm = kvm;
+	kv_dmabuf->slot = slot;
+	attach = dma_buf_dynamic_attach(dmabuf, NULL, &kv_dmabuf_attach_ops,
+					kv_dmabuf);
+	if (IS_ERR(attach)) {
+		ret = PTR_ERR(attach);
+		goto err_kv_dmabuf;
+	}
+
+	slot->dmabuf_attach = attach;
+
+	return 0;
+
+err_kv_dmabuf:
+	kfree(kv_dmabuf);
+err_dmabuf:
+	dma_buf_put(dmabuf);
+	return ret;
+}
+
+void kvm_vfio_dmabuf_unbind(struct kvm_memory_slot *slot)
+{
+	struct dma_buf_attachment *attach = slot->dmabuf_attach;
+	struct kvm_vfio_dmabuf *kv_dmabuf;
+	struct dma_buf *dmabuf;
+
+	if (WARN_ON_ONCE(!attach))
+		return;
+
+	kv_dmabuf = attach->importer_priv;
+	dmabuf = attach->dmabuf;
+	dma_buf_detach(dmabuf, attach);
+	kfree(kv_dmabuf);
+	dma_buf_put(dmabuf);
+}
+
+/*
+ * The return value matters. If return -EFAULT, userspace will try to do
+ * page attribute (shared <-> private) conversion.
+ */
+int kvm_vfio_dmabuf_get_pfn(struct kvm *kvm, struct kvm_memory_slot *slot,
+			    gfn_t gfn, kvm_pfn_t *pfn, int *max_order)
+{
+	struct dma_buf_attachment *attach = slot->dmabuf_attach;
+	pgoff_t pgoff = gfn - slot->base_gfn;
+	int ret;
+
+	if (WARN_ON_ONCE(!attach))
+		return -EFAULT;
+
+	ret = dma_buf_get_pfn_unlocked(attach, pgoff, pfn, max_order);
+	if (ret)
+		return -EIO;
+
+	return 0;
+}
+EXPORT_SYMBOL_GPL(kvm_vfio_dmabuf_get_pfn);

---

## [13] Xu Yilun — 2025-01-07
*Subject: [RFC PATCH 07/12] KVM: x86/mmu: Handle page fault for vfio_dmabuf backed MMIO*

Add support for resolving page faults on vfio_dmabuf backed MMIO. This
is to support private MMIO for private assigned devices (known as TDI
in TDISP spec).

Private MMIOs are set to KVM as vfio_dmabuf typed memory slot, which is
another type of can-be-private memory slot just like the gmem slot.
Like gmem slot, KVM needs to map its GFN as shared or private based on
the current state of the GFN's memory attribute. When page fault
happens for private MMIO but private <-> shared conversion is needed,
KVM still exits to userspace with exit reason KVM_EXIT_MEMORY_FAULT and
toggles KVM_MEMORY_EXIT_FLAG_PRIVATE. Unlike gmem slot, vfio_dmabuf
slot has only one backend MMIO resource, the switching of GFN's
attribute won't change the way of getting PFN, the vfio_dmabuf specific
way, kvm_vfio_dmabuf_get_pfn().

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 arch/x86/kvm/mmu/mmu.c   | 25 +++++++++++++++++++++++--
 include/linux/kvm_host.h |  7 ++++++-
 2 files changed, 29 insertions(+), 3 deletions(-)

diff --git a/arch/x86/kvm/mmu/mmu.c b/arch/x86/kvm/mmu/mmu.c
index 713ca857f2c2..90ca54fee22f 100644
--- a/arch/x86/kvm/mmu/mmu.c
+++ b/arch/x86/kvm/mmu/mmu.c
@@ -4341,8 +4341,13 @@ static int kvm_mmu_faultin_pfn_private(struct kvm_vcpu *vcpu,
 		return -EFAULT;
 	}
 
-	r = kvm_gmem_get_pfn(vcpu->kvm, fault->slot, fault->gfn, &fault->pfn,
-			     &fault->refcounted_page, &max_order);
+	if (kvm_slot_is_vfio_dmabuf(fault->slot))
+		r = kvm_vfio_dmabuf_get_pfn(vcpu->kvm, fault->slot, fault->gfn,
+					    &fault->pfn, &max_order);
+	else
+		r = kvm_gmem_get_pfn(vcpu->kvm, fault->slot, fault->gfn,
+				     &fault->pfn, &fault->refcounted_page,
+				     &max_order);
 	if (r) {
 		kvm_mmu_prepare_memory_fault_exit(vcpu, fault);
 		return r;
@@ -4363,6 +4368,22 @@ static int __kvm_mmu_faultin_pfn(struct kvm_vcpu *vcpu,
 	if (fault->is_private)
 		return kvm_mmu_faultin_pfn_private(vcpu, fault);
 
+	/* vfio_dmabuf slot is also applicable for shared mapping */
+	if (kvm_slot_is_vfio_dmabuf(fault->slot)) {
+		int max_order, r;
+
+		r = kvm_vfio_dmabuf_get_pfn(vcpu->kvm, fault->slot, fault->gfn,
+					    &fault->pfn, &max_order);
+		if (r)
+			return r;
+
+		fault->max_level = min(kvm_max_level_for_order(max_order),
+				       fault->max_level);
+		fault->map_writable = !(fault->slot->flags & KVM_MEM_READONLY);
+
+		return RET_PF_CONTINUE;
+	}
+
 	foll |= FOLL_NOWAIT;
 	fault->pfn = __kvm_faultin_pfn(fault->slot, fault->gfn, foll,
 				       &fault->map_writable, &fault->refcounted_page);
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index 871d927485a5..966a5a247c6b 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -614,7 +614,12 @@ struct kvm_memory_slot {
 
 static inline bool kvm_slot_can_be_private(const struct kvm_memory_slot *slot)
 {
-	return slot && (slot->flags & KVM_MEM_GUEST_MEMFD);
+	return slot && (slot->flags & (KVM_MEM_GUEST_MEMFD | KVM_MEM_VFIO_DMABUF));
+}
+
+static inline bool kvm_slot_is_vfio_dmabuf(const struct kvm_memory_slot *slot)
+{
+	return slot && (slot->flags & KVM_MEM_VFIO_DMABUF);
 }
 
 static inline bool kvm_slot_dirty_track_enabled(const struct kvm_memory_slot *slot)

---

## [14] Xu Yilun — 2025-01-07
*Subject: [RFC PATCH 08/12] vfio/pci: Create host unaccessible dma-buf for private device*

Add a flag for ioctl(VFIO_DEVICE_BIND_IOMMUFD) to mark a device as
for private assignment. For these private assigned devices, disallow
host accessing their MMIO resources.

Since the MMIO regions for private assignment are not accessible from
host, remove the VFIO_REGION_INFO_FLAG_MMAP/READ/WRITE for these
regions, instead add a new VFIO_REGION_INFO_FLAG_PRIVATE flag to
indicate users should create dma-buf for MMIO mapping in KVM MMU.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/vfio/device_cdev.c       |  9 ++++++++-
 drivers/vfio/pci/vfio_pci_core.c | 14 ++++++++++++++
 drivers/vfio/pci/vfio_pci_priv.h |  2 ++
 drivers/vfio/pci/vfio_pci_rdwr.c |  3 +++
 include/linux/vfio.h             |  1 +
 include/uapi/linux/vfio.h        |  5 ++++-
 6 files changed, 32 insertions(+), 2 deletions(-)

diff --git a/drivers/vfio/device_cdev.c b/drivers/vfio/device_cdev.c
index bb1817bd4ff3..919285c1cd7a 100644
--- a/drivers/vfio/device_cdev.c
+++ b/drivers/vfio/device_cdev.c
@@ -75,7 +75,10 @@ long vfio_df_ioctl_bind_iommufd(struct vfio_device_file *df,
 	if (copy_from_user(&bind, arg, minsz))
 		return -EFAULT;
 
-	if (bind.argsz < minsz || bind.flags || bind.iommufd < 0)
+	if (bind.argsz < minsz || bind.iommufd < 0)
+		return -EINVAL;
+
+	if (bind.flags & ~(VFIO_DEVICE_BIND_IOMMUFD_PRIVATE))
 		return -EINVAL;
 
 	/* BIND_IOMMUFD only allowed for cdev fds */
@@ -118,6 +121,9 @@ long vfio_df_ioctl_bind_iommufd(struct vfio_device_file *df,
 		goto out_close_device;
 
 	device->cdev_opened = true;
+	if (bind.flags & VFIO_DEVICE_BIND_IOMMUFD_PRIVATE)
+		device->is_private = true;
+
 	/*
 	 * Paired with smp_load_acquire() in vfio_device_fops::ioctl/
 	 * read/write/mmap
@@ -151,6 +157,7 @@ void vfio_df_unbind_iommufd(struct vfio_device_file *df)
 		return;
 
 	mutex_lock(&device->dev_set->lock);
+	device->is_private = false;
 	vfio_df_close(df);
 	vfio_device_put_kvm(device);
 	iommufd_ctx_put(df->iommufd);
diff --git a/drivers/vfio/pci/vfio_pci_core.c b/drivers/vfio/pci/vfio_pci_core.c
index f69eda5956ad..11c735dfe1f7 100644
--- a/drivers/vfio/pci/vfio_pci_core.c
+++ b/drivers/vfio/pci/vfio_pci_core.c
@@ -1005,6 +1005,12 @@ static int vfio_pci_ioctl_get_info(struct vfio_pci_core_device *vdev,
 	return copy_to_user(arg, &info, minsz) ? -EFAULT : 0;
 }
 
+bool is_vfio_pci_bar_private(struct vfio_pci_core_device *vdev, int bar)
+{
+	/* Any mmap supported bar can be used as vfio dmabuf */
+	return vdev->bar_mmap_supported[bar] && vdev->vdev.is_private;
+}
+
 static int vfio_pci_ioctl_get_region_info(struct vfio_pci_core_device *vdev,
 					  struct vfio_region_info __user *arg)
 {
@@ -1035,6 +1041,11 @@ static int vfio_pci_ioctl_get_region_info(struct vfio_pci_core_device *vdev,
 			break;
 		}
 
+		if (is_vfio_pci_bar_private(vdev, info.index)) {
+			info.flags = VFIO_REGION_INFO_FLAG_PRIVATE;
+			break;
+		}
+
 		info.flags = VFIO_REGION_INFO_FLAG_READ |
 			     VFIO_REGION_INFO_FLAG_WRITE;
 		if (vdev->bar_mmap_supported[info.index]) {
@@ -1735,6 +1746,9 @@ int vfio_pci_core_mmap(struct vfio_device *core_vdev, struct vm_area_struct *vma
 	u64 phys_len, req_len, pgoff, req_start;
 	int ret;
 
+	if (vdev->vdev.is_private)
+		return -EINVAL;
+
 	index = vma->vm_pgoff >> (VFIO_PCI_OFFSET_SHIFT - PAGE_SHIFT);
 
 	if (index >= VFIO_PCI_NUM_REGIONS + vdev->num_regions)
diff --git a/drivers/vfio/pci/vfio_pci_priv.h b/drivers/vfio/pci/vfio_pci_priv.h
index d27f383f3931..2b61e35145fd 100644
--- a/drivers/vfio/pci/vfio_pci_priv.h
+++ b/drivers/vfio/pci/vfio_pci_priv.h
@@ -126,4 +126,6 @@ static inline void vfio_pci_dma_buf_move(struct vfio_pci_core_device *vdev,
 }
 #endif
 
+bool is_vfio_pci_bar_private(struct vfio_pci_core_device *vdev, int bar);
+
 #endif
diff --git a/drivers/vfio/pci/vfio_pci_rdwr.c b/drivers/vfio/pci/vfio_pci_rdwr.c
index 66b72c289284..e385f7f63414 100644
--- a/drivers/vfio/pci/vfio_pci_rdwr.c
+++ b/drivers/vfio/pci/vfio_pci_rdwr.c
@@ -242,6 +242,9 @@ ssize_t vfio_pci_bar_rw(struct vfio_pci_core_device *vdev, char __user *buf,
 	struct resource *res = &vdev->pdev->resource[bar];
 	ssize_t done;
 
+	if (is_vfio_pci_bar_private(vdev, bar))
+		return -EINVAL;
+
 	if (pci_resource_start(pdev, bar))
 		end = pci_resource_len(pdev, bar);
 	else if (bar == PCI_ROM_RESOURCE &&
diff --git a/include/linux/vfio.h b/include/linux/vfio.h
index 2258b0585330..e99d856c6cd8 100644
--- a/include/linux/vfio.h
+++ b/include/linux/vfio.h
@@ -69,6 +69,7 @@ struct vfio_device {
 	struct iommufd_device *iommufd_device;
 	u8 iommufd_attached:1;
 #endif
+	u8 is_private:1;
 	u8 cdev_opened:1;
 #ifdef CONFIG_DEBUG_FS
 	/*
diff --git a/include/uapi/linux/vfio.h b/include/uapi/linux/vfio.h
index f43dfbde7352..6a1c703e3185 100644
--- a/include/uapi/linux/vfio.h
+++ b/include/uapi/linux/vfio.h
@@ -275,6 +275,7 @@ struct vfio_region_info {
 #define VFIO_REGION_INFO_FLAG_WRITE	(1 << 1) /* Region supports write */
 #define VFIO_REGION_INFO_FLAG_MMAP	(1 << 2) /* Region supports mmap */
 #define VFIO_REGION_INFO_FLAG_CAPS	(1 << 3) /* Info supports caps */
+#define VFIO_REGION_INFO_FLAG_PRIVATE	(1 << 4) /* Region supports private MMIO */
 	__u32	index;		/* Region index */
 	__u32	cap_offset;	/* Offset within info struct of first cap */
 	__aligned_u64	size;	/* Region size (bytes) */
@@ -904,7 +905,8 @@ struct vfio_device_feature {
  * VFIO_DEVICE_BIND_IOMMUFD - _IOR(VFIO_TYPE, VFIO_BASE + 18,
  *				   struct vfio_device_bind_iommufd)
  * @argsz:	 User filled size of this data.
- * @flags:	 Must be 0.
+ * @flags:	 Optional device initialization flags:
+ *		 VFIO_DEVICE_BIND_IOMMUFD_PRIVATE:	for private assignment
  * @iommufd:	 iommufd to bind.
  * @out_devid:	 The device id generated by this bind. devid is a handle for
  *		 this device/iommufd bond and can be used in IOMMUFD commands.
@@ -921,6 +923,7 @@ struct vfio_device_feature {
 struct vfio_device_bind_iommufd {
 	__u32		argsz;
 	__u32		flags;
+#define VFIO_DEVICE_BIND_IOMMUFD_PRIVATE	(1 << 0)
 	__s32		iommufd;
 	__u32		out_devid;
 };

---

## [15] Xu Yilun — 2025-01-07
*Subject: [RFC PATCH 09/12] vfio/pci: Export vfio dma-buf specific info for importers*

VFIO dma-buf supports exporting host unaccessible MMIO regions for
private assignment. Export this info by attaching VFIO specific
dma-buf data in struct dma_buf::priv. Provide a helper
vfio_dma_buf_get_data() for importers to fetch these data.

The exported host unaccessible info are for importers to decide if the
dma-buf is good to use. KVM only allows host unaccessible MMIO regions
for private MMIO slot. But it is expected other importers (e.g. RDMA
driver, IOMMUFD) may also use the dma-buf machanism for P2P in native
or non-CoCo VM, in which cases host unaccessible is not required.

Also export struct kvm * handler attached to the vfio device. This
allows KVM to do another sanity check. MMIO should only be assigned to
a CoCo VM if its owner device is already assigned to the same VM.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 drivers/vfio/pci/dma_buf.c | 24 ++++++++++++++++++++++++
 include/linux/vfio.h       | 19 +++++++++++++++++++
 2 files changed, 43 insertions(+)

diff --git a/drivers/vfio/pci/dma_buf.c b/drivers/vfio/pci/dma_buf.c
index ad12cfb85099..ad984f2c22fc 100644
--- a/drivers/vfio/pci/dma_buf.c
+++ b/drivers/vfio/pci/dma_buf.c
@@ -9,6 +9,8 @@
 MODULE_IMPORT_NS("DMA_BUF");
 
 struct vfio_pci_dma_buf {
+	struct vfio_dma_buf_data export_data;
+
 	struct dma_buf *dmabuf;
 	struct vfio_pci_core_device *vdev;
 	struct list_head dmabufs_elm;
@@ -156,6 +158,14 @@ int vfio_pci_core_feature_dma_buf(struct vfio_pci_core_device *vdev, u32 flags,
 	priv->vdev = vdev;
 	priv->nr_ranges = get_dma_buf.nr_ranges;
 	priv->dma_ranges = dma_ranges;
+	/*
+	 * KVM expects private dma_buf. An private dma_buf must not
+	 * support dma_buf_ops.map_dma_buf/mmap/vmap(). The exporter must also
+	 * ensure no side channel access for the backend resource, e.g.
+	 * vfio_device_ops.mmap() should not be supported.
+	 */
+	priv->export_data.is_private = vdev->vdev.is_private;
+	priv->export_data.kvm = vdev->vdev.kvm;
 
 	ret = check_dma_ranges(priv, &dmabuf_size);
 	if (ret)
@@ -247,3 +257,17 @@ void vfio_pci_dma_buf_cleanup(struct vfio_pci_core_device *vdev)
 	}
 	up_write(&vdev->memory_lock);
 }
+
+/*
+ * Only vfio/pci implements this, so put the helper here for now.
+ */
+struct vfio_dma_buf_data *vfio_dma_buf_get_data(struct dma_buf *dmabuf)
+{
+	struct vfio_pci_dma_buf *priv = dmabuf->priv;
+
+	if (dmabuf->ops != &vfio_pci_dmabuf_ops)
+		return ERR_PTR(-EINVAL);
+
+	return &priv->export_data;
+}
+EXPORT_SYMBOL_GPL(vfio_dma_buf_get_data);
diff --git a/include/linux/vfio.h b/include/linux/vfio.h
index e99d856c6cd8..fd7669e5b276 100644
--- a/include/linux/vfio.h
+++ b/include/linux/vfio.h
@@ -9,6 +9,7 @@
 #define VFIO_H
 
 
+#include <linux/dma-buf.h>
 #include <linux/iommu.h>
 #include <linux/mm.h>
 #include <linux/workqueue.h>
@@ -370,4 +371,22 @@ int vfio_virqfd_enable(void *opaque, int (*handler)(void *, void *),
 void vfio_virqfd_disable(struct virqfd **pvirqfd);
 void vfio_virqfd_flush_thread(struct virqfd **pvirqfd);
 
+/*
+ * DMA-buf - generic
+ */
+struct vfio_dma_buf_data {
+	bool is_private;
+	struct kvm *kvm;
+};
+
+#if IS_ENABLED(CONFIG_DMA_SHARED_BUFFER) && IS_ENABLED(CONFIG_VFIO_PCI_CORE)
+struct vfio_dma_buf_data *vfio_dma_buf_get_data(struct dma_buf *dmabuf);
+#else
+static inline
+struct vfio_dma_buf_data *vfio_dma_buf_get_data(struct dma_buf *dmabuf)
+{
+	return NULL;
+}
+#endif
+
 #endif /* VFIO_H */

---

## [16] Xu Yilun — 2025-01-07
*Subject: [RFC PATCH 10/12] KVM: vfio_dmabuf: Fetch VFIO specific dma-buf data for sanity check*

Fetch VFIO specific dma-buf data to see if the dma-buf is eligible to
be assigned to CoCo VM as private MMIO.

KVM expects host unaccessible dma-buf for private MMIO mapping. So need
the exporter provide this information. VFIO also provides the
struct kvm *kvm handler for KVM to check if the owner device of the
MMIO region is already assigned to the same CoCo VM.

Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>
---
 virt/kvm/vfio_dmabuf.c | 26 ++++++++++++++++++++++++++
 1 file changed, 26 insertions(+)

diff --git a/virt/kvm/vfio_dmabuf.c b/virt/kvm/vfio_dmabuf.c
index c427ab39c68a..26e01b815ebf 100644
--- a/virt/kvm/vfio_dmabuf.c
+++ b/virt/kvm/vfio_dmabuf.c
@@ -12,6 +12,22 @@ struct kvm_vfio_dmabuf {
 	struct kvm_memory_slot *slot;
 };
 
+static struct vfio_dma_buf_data *kvm_vfio_dma_buf_get_data(struct dma_buf *dmabuf)
+{
+	struct vfio_dma_buf_data *(*fn)(struct dma_buf *dmabuf);
+	struct vfio_dma_buf_data *ret;
+
+	fn = symbol_get(vfio_dma_buf_get_data);
+	if (!fn)
+		return ERR_PTR(-ENOENT);
+
+	ret = fn(dmabuf);
+
+	symbol_put(vfio_dma_buf_get_data);
+
+	return ret;
+}
+
 static void kv_dmabuf_move_notify(struct dma_buf_attachment *attach)
 {
 	struct kvm_vfio_dmabuf *kv_dmabuf = attach->importer_priv;
@@ -48,6 +64,7 @@ int kvm_vfio_dmabuf_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
 	size_t size = slot->npages << PAGE_SHIFT;
 	struct dma_buf_attachment *attach;
 	struct kvm_vfio_dmabuf *kv_dmabuf;
+	struct vfio_dma_buf_data *data;
 	struct dma_buf *dmabuf;
 	int ret;
 
@@ -60,6 +77,15 @@ int kvm_vfio_dmabuf_bind(struct kvm *kvm, struct kvm_memory_slot *slot,
 		goto err_dmabuf;
 	}
 
+	data = kvm_vfio_dma_buf_get_data(dmabuf);
+	if (IS_ERR(data))
+		goto err_dmabuf;
+
+	if (!data->is_private || data->kvm != kvm) {
+		ret = -EINVAL;
+		goto err_dmabuf;
+	}
+
 	kv_dmabuf = kzalloc(sizeof(*kv_dmabuf), GFP_KERNEL);
 	if (!kv_dmabuf) {
 		ret = -ENOMEM;

---

## [17] Xu Yilun — 2025-01-07
*Subject: [RFC PATCH 11/12] KVM: x86/mmu: Export kvm_is_mmio_pfn()*

From: Xu Yilun <yilun.xu@intel.com>

Export kvm_is_mmio_pfn() for KVM TDX to decide which seamcall should be
used to setup SEPT leaf entry.

TDX Module requires tdh_mem_page_aug() for memory page setup,
and tdh_mmio_map() for MMIO setup.

Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@intel.com>
---
 arch/x86/kvm/mmu.h      | 1 +
 arch/x86/kvm/mmu/spte.c | 3 ++-
 2 files changed, 3 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kvm/mmu.h b/arch/x86/kvm/mmu.h
index e40097c7e8d4..23ff0e6c9ef6 100644
--- a/arch/x86/kvm/mmu.h
+++ b/arch/x86/kvm/mmu.h
@@ -102,6 +102,7 @@ void kvm_mmu_sync_roots(struct kvm_vcpu *vcpu);
 void kvm_mmu_sync_prev_roots(struct kvm_vcpu *vcpu);
 void kvm_mmu_track_write(struct kvm_vcpu *vcpu, gpa_t gpa, const u8 *new,
 			 int bytes);
+bool kvm_is_mmio_pfn(kvm_pfn_t pfn);
 
 static inline int kvm_mmu_reload(struct kvm_vcpu *vcpu)
 {
diff --git a/arch/x86/kvm/mmu/spte.c b/arch/x86/kvm/mmu/spte.c
index e819d16655b6..0a9a81afba93 100644
--- a/arch/x86/kvm/mmu/spte.c
+++ b/arch/x86/kvm/mmu/spte.c
@@ -105,7 +105,7 @@ u64 make_mmio_spte(struct kvm_vcpu *vcpu, u64 gfn, unsigned int access)
 	return spte;
 }
 
-static bool kvm_is_mmio_pfn(kvm_pfn_t pfn)
+bool kvm_is_mmio_pfn(kvm_pfn_t pfn)
 {
 	if (pfn_valid(pfn))
 		return !is_zero_pfn(pfn) && PageReserved(pfn_to_page(pfn)) &&
@@ -125,6 +125,7 @@ static bool kvm_is_mmio_pfn(kvm_pfn_t pfn)
 				     pfn_to_hpa(pfn + 1) - 1,
 				     E820_TYPE_RAM);
 }
+EXPORT_SYMBOL_GPL(kvm_is_mmio_pfn);
 
 /*
  * Returns true if the SPTE has bits that may be set without holding mmu_lock.

---

## [18] Xu Yilun — 2025-01-07
*Subject: [RFC PATCH 12/12] KVM: TDX: Implement TDX specific private MMIO map/unmap for SEPT*

Implement TDX specific private MMIO map/unmap in existing TDP MMU hooks.

Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
Signed-off-by: Xu Yilun <yilun.xu@linux.intel.com>

---
TODO: This patch is still based on the earlier kvm-coco-queue version
(v6.13-rc2). Will follow up the latest SEAMCALL wrapper change. [1]

[1] https://lore.kernel.org/all/20250101074959.412696-1-pbonzini@redhat.com/
---
 arch/x86/include/asm/tdx.h  |  3 ++
 arch/x86/kvm/vmx/tdx.c      | 57 +++++++++++++++++++++++++++++++++++--
 arch/x86/virt/vmx/tdx/tdx.c | 52 +++++++++++++++++++++++++++++++++
 arch/x86/virt/vmx/tdx/tdx.h |  3 ++
 4 files changed, 113 insertions(+), 2 deletions(-)

diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index 01409a59224d..7d158bbf79f4 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -151,6 +151,9 @@ u64 tdh_mem_page_remove(u64 tdr, u64 gpa, u64 level, u64 *rcx, u64 *rdx);
 u64 tdh_phymem_cache_wb(bool resume);
 u64 tdh_phymem_page_wbinvd_tdr(u64 tdr);
 u64 tdh_phymem_page_wbinvd_hkid(u64 hpa, u64 hkid);
+u64 tdh_mmio_map(u64 tdr, u64 gpa, u64 level, u64 hpa, u64 *rcx, u64 *rdx);
+u64 tdh_mmio_block(u64 tdr, u64 gpa, u64 level, u64 *rcx, u64 *rdx);
+u64 tdh_mmio_unmap(u64 tdr, u64 gpa, u64 level, u64 *rcx, u64 *rdx);
 #else
 static inline void tdx_init(void) { }
 static inline int tdx_cpu_enable(void) { return -ENODEV; }
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 69ef9c967fbf..9b43a2ee2203 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1576,6 +1576,29 @@ static int tdx_mem_page_aug(struct kvm *kvm, gfn_t gfn,
 	return 0;
 }
 
+static int tdx_mmio_map(struct kvm *kvm, gfn_t gfn,
+			enum pg_level level, kvm_pfn_t pfn)
+{
+	int tdx_level = pg_level_to_tdx_sept_level(level);
+	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
+	hpa_t hpa = pfn_to_hpa(pfn);
+	gpa_t gpa = gfn_to_gpa(gfn);
+	u64 entry, level_state;
+	u64 err;
+
+	err = tdh_mmio_map(kvm_tdx->tdr_pa, gpa, tdx_level, hpa,
+			   &entry, &level_state);
+	if (unlikely(err & TDX_OPERAND_BUSY))
+		return -EBUSY;
+
+	if (KVM_BUG_ON(err, kvm)) {
+		pr_tdx_error_2(TDH_MMIO_MAP, err, entry, level_state);
+		return -EIO;
+	}
+
+	return 0;
+}
+
 /*
  * KVM_TDX_INIT_MEM_REGION calls kvm_gmem_populate() to get guest pages and
  * tdx_gmem_post_populate() to premap page table pages into private EPT.
@@ -1610,6 +1633,9 @@ int tdx_sept_set_private_spte(struct kvm *kvm, gfn_t gfn,
 	if (KVM_BUG_ON(level != PG_LEVEL_4K, kvm))
 		return -EINVAL;
 
+	if (kvm_is_mmio_pfn(pfn))
+		return tdx_mmio_map(kvm, gfn, level, pfn);
+
 	/*
 	 * Because guest_memfd doesn't support page migration with
 	 * a_ops->migrate_folio (yet), no callback is triggered for KVM on page
@@ -1647,6 +1673,20 @@ static int tdx_sept_drop_private_spte(struct kvm *kvm, gfn_t gfn,
 	if (KVM_BUG_ON(!is_hkid_assigned(kvm_tdx), kvm))
 		return -EINVAL;
 
+	if (kvm_is_mmio_pfn(pfn)) {
+		do {
+			err = tdh_mmio_unmap(kvm_tdx->tdr_pa, gpa, tdx_level,
+					     &entry, &level_state);
+		} while (unlikely(err == TDX_ERROR_SEPT_BUSY));
+
+		if (KVM_BUG_ON(err, kvm)) {
+			pr_tdx_error_2(TDH_MMIO_UNMAP, err, entry, level_state);
+			return -EIO;
+		}
+
+		return 0;
+	}
+
 	do {
 		/*
 		 * When zapping private page, write lock is held. So no race
@@ -1715,7 +1755,7 @@ int tdx_sept_link_private_spt(struct kvm *kvm, gfn_t gfn,
 }
 
 static int tdx_sept_zap_private_spte(struct kvm *kvm, gfn_t gfn,
-				     enum pg_level level)
+				     enum pg_level level, kvm_pfn_t pfn)
 {
 	int tdx_level = pg_level_to_tdx_sept_level(level);
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
@@ -1725,6 +1765,19 @@ static int tdx_sept_zap_private_spte(struct kvm *kvm, gfn_t gfn,
 	/* For now large page isn't supported yet. */
 	WARN_ON_ONCE(level != PG_LEVEL_4K);
 
+	if (kvm_is_mmio_pfn(pfn)) {
+		err = tdh_mmio_block(kvm_tdx->tdr_pa, gpa, tdx_level,
+				     &entry, &level_state);
+		if (unlikely(err == TDX_ERROR_SEPT_BUSY))
+			return -EAGAIN;
+		if (KVM_BUG_ON(err, kvm)) {
+			pr_tdx_error_2(TDH_MMIO_BLOCK, err, entry, level_state);
+			return -EIO;
+		}
+
+		return 0;
+	}
+
 	err = tdh_mem_range_block(kvm_tdx->tdr_pa, gpa, tdx_level, &entry, &level_state);
 	if (unlikely(err == TDX_ERROR_SEPT_BUSY))
 		return -EAGAIN;
@@ -1816,7 +1869,7 @@ int tdx_sept_remove_private_spte(struct kvm *kvm, gfn_t gfn,
 	if (KVM_BUG_ON(!is_hkid_assigned(to_kvm_tdx(kvm)), kvm))
 		return -EINVAL;
 
-	ret = tdx_sept_zap_private_spte(kvm, gfn, level);
+	ret = tdx_sept_zap_private_spte(kvm, gfn, level, pfn);
 	if (ret)
 		return ret;
 
diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 57195cf0d832..3b2109877a39 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -1951,3 +1951,55 @@ u64 tdh_phymem_page_wbinvd_hkid(u64 hpa, u64 hkid)
 	return seamcall(TDH_PHYMEM_PAGE_WBINVD, &args);
 }
 EXPORT_SYMBOL_GPL(tdh_phymem_page_wbinvd_hkid);
+
+u64 tdh_mmio_map(u64 tdr, u64 gpa, u64 level, u64 hpa, u64 *rcx, u64 *rdx)
+{
+	struct tdx_module_args args = {
+		.rcx = gpa | level,
+		.rdx = tdr,
+		.r8 = hpa,
+	};
+	u64 ret;
+
+	ret = tdx_seamcall_sept(TDH_MMIO_MAP, &args);
+
+	*rcx = args.rcx;
+	*rdx = args.rdx;
+
+	return ret;
+}
+EXPORT_SYMBOL_GPL(tdh_mmio_map);
+
+u64 tdh_mmio_block(u64 tdr, u64 gpa, u64 level, u64 *rcx, u64 *rdx)
+{
+	struct tdx_module_args args = {
+		.rcx = gpa | level,
+		.rdx = tdr,
+	};
+	u64 ret;
+
+	ret = tdx_seamcall_sept(TDH_MMIO_BLOCK, &args);
+
+	*rcx = args.rcx;
+	*rdx = args.rdx;
+
+	return ret;
+}
+EXPORT_SYMBOL_GPL(tdh_mmio_block);
+
+u64 tdh_mmio_unmap(u64 tdr, u64 gpa, u64 level, u64 *rcx, u64 *rdx)
+{
+	struct tdx_module_args args = {
+		.rcx = gpa | level,
+		.rdx = tdr,
+	};
+	u64 ret;
+
+	ret = tdx_seamcall_sept(TDH_MMIO_UNMAP, &args);
+
+	*rcx = args.rcx;
+	*rdx = args.rdx;
+
+	return ret;
+}
+EXPORT_SYMBOL_GPL(tdh_mmio_unmap);
diff --git a/arch/x86/virt/vmx/tdx/tdx.h b/arch/x86/virt/vmx/tdx/tdx.h
index 58d5754dcb4d..a83a90a043a5 100644
--- a/arch/x86/virt/vmx/tdx/tdx.h
+++ b/arch/x86/virt/vmx/tdx/tdx.h
@@ -49,6 +49,9 @@
 #define TDH_VP_WR			43
 #define TDH_PHYMEM_PAGE_WBINVD		41
 #define TDH_SYS_CONFIG			45
+#define TDH_MMIO_MAP			158
+#define TDH_MMIO_BLOCK			159
+#define TDH_MMIO_UNMAP			160
 
 /*
  * SEAMCALL leaf:

---

## [19] Christian König — 2025-01-08
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

Am 07.01.25 um 15:27 schrieb Xu Yilun:
> Introduce a new API for dma-buf importer, also add a dma_buf_ops
> callback for dma-buf exporter. This API is for subsystem importers who

As far as I can see I have to fundamentally reject this whole approach.

It's intentional DMA-buf design that we don't expose struct pages nor 
PFNs to the importer. Essentially DMA-buf only transports DMA addresses.

In other words the mapping is done by the exporter and *not* the importer.

What we certainly can do is to annotate those DMA addresses to a better 
specify in which domain they are applicable, e.g. if they are PCIe bus 
addresses or some inter device bus addresses etc...

But moving the functionality to map the pages/PFNs to DMA addresses into 
the importer is an absolutely clear NO-GO.

Regards,
Christian.

>   So the map_dma_buf() callback is not mandatory for exporters
> anymore. Also the importers could choose not to provide

---

## [20] Jason Gunthorpe — 2025-01-08
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Wed, Jan 08, 2025 at 09:01:46AM +0100, Christian König wrote:
> Am 07.01.25 um 15:27 schrieb Xu Yilun:
> > Introduce a new API for dma-buf importer, also add a dma_buf_ops

Oh?

Having the importer do the mapping is the correct way to operate the
DMA API and the new API that Leon has built to fix the scatterlist
abuse in dmabuf relies on importer mapping as part of it's
construction.

Why on earth do you want the exporter to map? That is completely
backwards and unworkable in many cases. The disfunctional P2P support
in dmabuf is like that principally because of this.

That said, I don't think get_pfn() is an especially good interface,
but we will need to come with something that passes the physical pfn
out.

Jason

---

## [21] Jason Gunthorpe — 2025-01-08

On Tue, Jan 07, 2025 at 10:27:15PM +0800, Xu Yilun wrote:
> Add a flag for ioctl(VFIO_DEVICE_BIND_IOMMUFD) to mark a device as
> for private assignment. For these private assigned devices, disallow

Why? Shouldn't the VMM simply not call mmap? Why does the kernel have
to enforce this?

Jason

---

## [22] Christian König — 2025-01-08
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

Am 08.01.25 um 14:23 schrieb Jason Gunthorpe:
> On Wed, Jan 08, 2025 at 09:01:46AM +0100, Christian König wrote:
>> Am 07.01.25 um 15:27 schrieb Xu Yilun:

Exactly on that I strongly disagree on.

DMA-buf works by providing DMA addresses the importer can work with and 
*NOT* the underlying location of the buffer.

> Why on earth do you want the exporter to map?

Because the exporter owns the exported buffer and only the exporter 
knows to how correctly access it.

> That is completely backwards and unworkable in many cases. The disfunctional P2P support
> in dmabuf is like that principally because of this.

No, that is exactly what we need.

Using the scatterlist to transport the DMA addresses was clearly a 
mistake, but providing the DMA addresses by the exporter has proved many 
times to be the right approach.

Keep in mind that the exported buffer is not necessary memory, but can 
also be MMIO or stuff which is only accessible through address space 
windows where you can't create a PFN nor struct page for.

> That said, I don't think get_pfn() is an especially good interface,
> but we will need to come with something that passes the physical pfn

No, physical pfn is absolutely not a good way of passing the location of 
data around because it is limited to what the CPU sees as address space.

We have use cases where DMA-buf transports the location of CPU invisible 
data which only the involved devices can see.

Regards,
Christian.

>
> Jason

---

## [23] Jason Gunthorpe — 2025-01-08
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Wed, Jan 08, 2025 at 02:44:26PM +0100, Christian König wrote:

> > Having the importer do the mapping is the correct way to operate the
> > DMA API and the new API that Leon has built to fix the scatterlist

The expectation is that the DMA API will be used to DMA map (most)
things, and the DMA API always works with a physaddr_t/pfn
argument. Basically, everything that is not a private address space
should be supported by improving the DMA API. We are on course for
finally getting all the common cases like P2P and MMIO solved
here. That alone will take care of alot.

For P2P cases we are going toward (PFN + P2P source information) as
input to the DMA API. The additional "P2P source information" provides
a good way for co-operating drivers to represent private address
spaces as well. Both importer and exporter can have full understanding
what is being mapped and do the correct things, safely.

So, no, we don't loose private address space support when moving to
importer mapping, in fact it works better because the importer gets
more information about what is going on.

I have imagined a staged approach were DMABUF gets a new API that
works with the new DMA API to do importer mapping with "P2P source
information" and a gradual conversion.

Exporter mapping falls down in too many cases already:

1) Private addresses spaces don't work fully well because many devices
need some indication what address space is being used and scatter list
can't really properly convey that. If the DMABUF has a mixture of CPU
and private it becomes a PITA

2) Multi-path PCI can require the importer to make mapping decisions
unique to the device and program device specific information for the
multi-path. We are doing this in mlx5 today and have hacks because
DMABUF is destroying the information the importer needs to choose the
correct PCI path.

3) Importing devices need to know if they are working with PCI P2P
addresses during mapping because they need to do things like turn on
ATS on their DMA. As for multi-path we have the same hacks inside mlx5
today that assume DMABUFs are always P2P because we cannot determine
if things are P2P or not after being DMA mapped.

4) TPH bits needs to be programmed into the importer device but are
derived based on the NUMA topology of the DMA target. The importer has
no idea what the DMA target actually was because the exporter mapping
destroyed that information.

5) iommufd and kvm are both using CPU addresses without DMA. No
exporter mapping is possible

Jason

---

## [24] Christian König — 2025-01-08
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

Am 08.01.25 um 15:58 schrieb Jason Gunthorpe:
> On Wed, Jan 08, 2025 at 02:44:26PM +0100, Christian König wrote:
>

Well, from experience the DMA API has failed more often than it actually 
worked in the way required by drivers.

Especially that we tried to hide architectural complexity in there 
instead of properly expose limitations to drivers is not something I 
consider a good design approach.

So I see putting even more into that extremely critical.

> For P2P cases we are going toward (PFN + P2P source information) as
> input to the DMA API. The additional "P2P source information" provides

I can say from experience that this is clearly not going to work for all 
use cases.

It would mean that we have to pull a massive amount of driver specific 
functionality into the DMA API.

Things like programming access windows for PCI BARs is completely driver 
specific and as far as I can see can't be part of the DMA API without 
things like callbacks.

With that in mind the DMA API would become a mid layer between different 
drivers and that is really not something you are suggesting, isn't it?

> So, no, we don't loose private address space support when moving to
> importer mapping, in fact it works better because the importer gets

Well, sounds like I wasn't able to voice my concern. Let me try again:

We should not give importers information they don't need. Especially not 
information about the backing store of buffers.

So that importers get more information about what's going on is a bad thing.

> I have imagined a staged approach were DMABUF gets a new API that
> works with the new DMA API to do importer mapping with "P2P source

To make it clear as maintainer of that subsystem I would reject such a 
step with all I have.

We have already gone down that road and it didn't worked at all and was 
a really big pain to pull people back from it.

> Exporter mapping falls down in too many cases already:
>

Correct, yes. That's why I said that scatterlist was a bad choice for 
the interface.

But exposing the backing store to importers and then let them do 
whatever they want with it sounds like an even worse idea.

> 2) Multi-path PCI can require the importer to make mapping decisions
> unique to the device and program device specific information for the

That's why the exporter gets the struct device of the importer so that 
it can plan how those accesses are made. Where exactly is the problem 
with that?

When you have an use case which is not covered by the existing DMA-buf 
interfaces then please voice that to me and other maintainers instead of 
implementing some hack.

> 3) Importing devices need to know if they are working with PCI P2P
> addresses during mapping because they need to do things like turn on

Why would you need ATS on PCI P2P and not for system memory accesses?

> 4) TPH bits needs to be programmed into the importer device but are
> derived based on the NUMA topology of the DMA target. The importer has

Yeah, but again that is completely intentional.

I assume you mean TLP processing hints when you say TPH and those should 
be part of the DMA addresses provided by the exporter.

That an importer tries to look behind the curtain and determines the 
NUMA placement and topology themselves is clearly a no-go from the 
design perspective.

> 5) iommufd and kvm are both using CPU addresses without DMA. No
> exporter mapping is possible

We have customers using both KVM and XEN with DMA-buf, so I can clearly 
confirm that this isn't true.

Regards,
Christian.

>
> Jason

---

## [25] Jason Gunthorpe — 2025-01-08
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Wed, Jan 08, 2025 at 04:25:54PM +0100, Christian König wrote:
> Am 08.01.25 um 15:58 schrieb Jason Gunthorpe:
> > On Wed, Jan 08, 2025 at 02:44:26PM +0100, Christian König wrote:

The DMA API has been static and very hard to change in these ways for
a long time. I think Leon's new API will break through this and we
will be able finally address these issues.

> > For P2P cases we are going toward (PFN + P2P source information) as
> > input to the DMA API. The additional "P2P source information" provides

That isn't what I mean. There are two distinct parts, the means to
describe the source (PFN + P2P source information) that is compatible
with the DMA API, and the DMA API itself that works with a few general
P2P source information types.

Private source information would be detected by co-operating drivers
and go down driver private paths. It would be rejected by other
drivers. This broadly follows how the new API is working.

So here I mean you can use the same PFN + Source API between importer
and exporter and the importer can simply detect the special source and
do the private stuff. It is not shifting things under the DMA API, it
is building along side it using compatible design approaches. You
would match the source information, cast it to a driver structure, do
whatever driver math is needed to compute the local DMA address and
then write it to the device. Nothing is hard or "not going to work"
here.

> > So, no, we don't loose private address space support when moving to
> > importer mapping, in fact it works better because the importer gets

I strongly disagree because we are suffering today in mlx5 because of
this viewpoint. You cannot predict in advance what importers are going
to need. I already listed many examples where it does not work today
as is.

> > I have imagined a staged approach were DMABUF gets a new API that
> > works with the new DMA API to do importer mapping with "P2P source

This is unexpected, so you want to just leave dmabuf broken? Do you
have any plan to fix it, to fix the misuse of the DMA API, and all
the problems I listed below? This is a big deal, it is causing real
problems today.

If it going to be like this I think we will stop trying to use dmabuf
and do something simpler for vfio/kvm/iommufd :(

> We have already gone down that road and it didn't worked at all and
> was a really big pain to pull people back from it.

Nobody has really seriously tried to improve the DMA API before, so I
don't think this is true at all.

> > Exporter mapping falls down in too many cases already:
> > 

You keep saying this without real justification. To me it is a nanny
style of API design. But also I don't see how you can possibly fix the
above without telling the importer alot more information.

> > 2) Multi-path PCI can require the importer to make mapping decisions
> > unique to the device and program device specific information for the

A single struct device does not convey the multipath options. We have
multiple struct devices (and multiple PCI endpoints) doing DMA
concurrently under one driver.

Multipath always needs additional meta information in the importer
side to tell the device which path to select. A naked dma address is
not sufficient.

Today we guess that DMABUF will be using P2P and hack to choose a P2P
struct device to pass the exporter. We need to know what is in the
dmabuf before we can choose which of the multiple struct devices the
driver has to use for DMA mapping.

But even simple CPU centric cases we will eventually want to select
the proper NUMA local PCI channel matching struct device for CPU only
buffers.

> When you have an use case which is not covered by the existing DMA-buf
> interfaces then please voice that to me and other maintainers instead of

Do you have any suggestion for any of this then? We have a good plan
to fix this stuff and more. Many experts in their fields have agreed
on the different parts now. We haven't got to dmabuf because I had no
idea there would be an objection like this.

> > 3) Importing devices need to know if they are working with PCI P2P
> > addresses during mapping because they need to do things like turn on

ATS has a significant performance cost. It is mandatory for PCI P2P,
but ideally should be avoided for CPU memory.

> > 4) TPH bits needs to be programmed into the importer device but are
> > derived based on the NUMA topology of the DMA target. The importer has

Yes, but is not part of the DMA addresses.

> That an importer tries to look behind the curtain and determines the NUMA
> placement and topology themselves is clearly a no-go from the design

I strongly disagree, this is important. Drivers need this information
in a future TPH/UIO/multipath PCI world.

> > 5) iommufd and kvm are both using CPU addresses without DMA. No
> > exporter mapping is possible

Today they are mmaping the dma-buf into a VMA and then using KVM's
follow_pfn() flow to extract the CPU pfn from the PTE. Any mmapable
dma-buf must have a CPU PFN.

Here Xu implements basically the same path, except without the VMA
indirection, and it suddenly not OK? Illogical.

Jason

---

## [26] Xu Yilun — 2025-01-09

On Wed, Jan 08, 2025 at 09:30:26AM -0400, Jason Gunthorpe wrote:
> On Tue, Jan 07, 2025 at 10:27:15PM +0800, Xu Yilun wrote:
> > Add a flag for ioctl(VFIO_DEVICE_BIND_IOMMUFD) to mark a device as

MM.. maybe I should not say 'host', instead 'userspace'.

I think the kernel part VMM (KVM) has the responsibility to enforce the
correct behavior of the userspace part VMM (QEMU). QEMU has no way to
touch private memory/MMIO intentionally or accidently. IIUC that's one
of the initiative guest_memfd is introduced for private memory. Private
MMIO follows.

Thanks,
Yilun

> 
> Jason

---

## [27] Xu Yilun — 2025-01-09
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

> > > 5) iommufd and kvm are both using CPU addresses without DMA. No
> > > exporter mapping is possible

Yes, the final target for KVM is still the CPU PFN, just with the help
of CPU mapping table.

I also found the xen gntdev-dmabuf is calculating pfn from mapped
sgt.

From Christion's point, I assume only sgl->dma_address should be
used by importers but in fact not. More importers are 'abusing' sg dma
helpers.

That said there are existing needs for importers to know more about the
real buffer resource, for mapping, or even more than mapping,
e.g. dmabuf_imp_grant_foreign_access()

Thanks,
Yilun

---

## [28] Simona Vetter — 2025-01-08
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Wed, Jan 08, 2025 at 12:22:27PM -0400, Jason Gunthorpe wrote:
> On Wed, Jan 08, 2025 at 04:25:54PM +0100, Christian K�nig wrote:
> > Am 08.01.25 um 15:58 schrieb Jason Gunthorpe:

As the gal who help edit the og dma-buf spec 13 years ago, I think adding
pfn isn't a terrible idea. By design, dma-buf is the "everything is
optional" interface. And in the beginning, even consistent locking was
optional, but we've managed to fix that by now :-/

Where I do agree with Christian is that stuffing pfn support into the
dma_buf_attachment interfaces feels a bit much wrong.

> > We have already gone down that road and it didn't worked at all and
> > was a really big pain to pull people back from it.

Aside, I really hope this finally happens!

> > > 3) Importing devices need to know if they are working with PCI P2P
> > > addresses during mapping because they need to do things like turn on

Huh, I didn't know that. And yeah kinda means we've butchered the pci p2p
stuff a bit I guess ...

> > > 5) iommufd and kvm are both using CPU addresses without DMA. No
> > > exporter mapping is possible

So the big difference is that for follow_pfn() you need mmu_notifier since
the mmap might move around, whereas with pfn smashed into
dma_buf_attachment you need dma_resv_lock rules, and the move_notify
callback if you go dynamic.

So I guess my first question is, which locking rules do you want here for
pfn importers?

If mmu notifiers is fine, then I think the current approach of follow_pfn
should be ok. But if you instead dma_resv_lock rules (or the cpu mmap
somehow is an issue itself), then I think the clean design is create a new
separate access mechanism just for that. It would be the 5th or so (kernel
vmap, userspace mmap, dma_buf_attach and driver private stuff like
virtio_dma_buf.c where you access your buffer with a uuid), so really not
a big deal.

And for non-contrived exporters we might be able to implement the other
access methods in terms of the pfn method generically, so this wouldn't
even be a terrible maintenance burden going forward. And meanwhile all the
contrived exporters just keep working as-is.

The other part is that cpu mmap is optional, and there's plenty of strange
exporters who don't implement. But you can dma map the attachment into
plenty devices. This tends to mostly be a thing on SoC devices with some
very funky memory. But I guess you don't care about these use-case, so
should be ok.

I couldn't come up with a good name for these pfn users, maybe
dma_buf_pfn_attachment? This does _not_ have a struct device, but maybe
some of these new p2p source specifiers (or a list of those which are
allowed, no idea how this would need to fit into the new dma api).

Cheers, Sima

---

## [29] Xu Yilun — 2025-01-09
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Wed, Jan 08, 2025 at 07:44:54PM +0100, Simona Vetter wrote:
> On Wed, Jan 08, 2025 at 12:22:27PM -0400, Jason Gunthorpe wrote:
> > On Wed, Jan 08, 2025 at 04:25:54PM +0100, Christian König wrote:

So it could a dmabuf interface like mmap/vmap()? I was also wondering
about that. But finally I start to use dma_buf_attachment interface
because of leveraging existing buffer pin and move_notify.

> 
> > > We have already gone down that road and it didn't worked at all and

follow_pfn() is unwanted for private MMIO, so dma_resv_lock.

> 
> If mmu notifiers is fine, then I think the current approach of follow_pfn

cpu mmap() is an issue, this series is aimed to eliminate userspace
mapping for private MMIO resources.

> separate access mechanism just for that. It would be the 5th or so (kernel
> vmap, userspace mmap, dma_buf_attach and driver private stuff like

OK, will think more about that.

Thanks,
Yilun

> 
> And for non-contrived exporters we might be able to implement the other

---

## [30] Xu Yilun — 2025-01-09
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

>  So I guess my first question is, which locking rules do you want here for
>  pfn importers?

I'm trying to make exporter give out PFN with lifetime control via
move_notify() in this series. May not be conceptually correct but seems
possible.

> 
> 

OK, I can start from here.

It is about the Secure guest, or CoCo VM. The memory and MMIOs assigned
to this kind of guest is unaccessable to host itself, by leveraging HW
encryption & access control technology (e.g. Intel TDX, AMD SEV-SNP ...).
This is to protect the tenant data being stolen by CSP itself.

The impact is when host accesses the encrypted region, bad things
happen to system, e.g. memory corruption, MCE. Kernel is trying to
mitigate most of the impact by alloc and assign user unmappable memory
resources (private memory) to guest, which prevents userspace
accidents. guest_memfd is the private memory provider that only allows
for KVM to position the page/pfn by fd + offset and create secondary
page table (EPT, NPT...), no host mapping, no VMA, no mmu_notifier. But
the lifecycle of the private memory is still controlled by guest_memfd.
When fallocate(fd, PUNCH_HOLE), the memory resource is revoked and KVM
is notified to unmap corresponding EPT.

The further thought is guest_memfd is also suitable for normal guest.
It makes no sense VMM must build host mapping table before guest access.

Now I'm trying to seek a similar way for private MMIO. A MMIO resource
provider that is exported as an fd. It controls the lifecycle of the
MMIO resource and notify KVM when revoked. dma-buf seems to be a good
provider which have done most of the work, only need to extend the
memory resource seeking by fd + offset.

> 
>  separate access mechanism just for that. It would be the 5th or so (kernel

Folow_pfn & mmu_notifier won't work here, cause no VMA, no host mapping
table.

Thanks,
Yilun
>    with MMIO mappings and P2P. And that required exactly zero DMA-buf changes
>    :)

---

## [31] Christian König — 2025-01-09
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

Answering on my reply once more as pure text mail.

I love AMDs mail servers.

Cheers,
Christian.

Am 09.01.25 um 09:04 schrieb Christian König:
> Am 08.01.25 um 20:22 schrieb Xu Yilun:
>> On Wed, Jan 08, 2025 at 07:44:54PM +0100, Simona Vetter wrote:

---

## [32] Leon Romanovsky — 2025-01-09
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Thu, Jan 09, 2025 at 10:10:01AM +0100, Christian K�nig wrote:
> Am 08.01.25 um 17:22 schrieb Jason Gunthorpe:
> > [SNIP]

IMHO, you and Jason give different meaning to word "driver" in this
discussion. It is upto to the subsystems to decide how to provide new
API to the end drivers. Worth to read this LWN article first.

Dancing the DMA two-step - https://lwn.net/Articles/997563/

> 
> Do you have pointers to this new API?

Latest version is here - https://lore.kernel.org/all/cover.1734436840.git.leon@kernel.org/
Unfortunately, I forgot to copy/paste cover letter but it can be seen in
previous version https://lore.kernel.org/all/cover.1733398913.git.leon@kernel.org/.

The most complex example is block layer implementation which hides DMA API from
block drivers. https://lore.kernel.org/all/cover.1730037261.git.leon@kernel.org/

Thanks

---

## [33] Jason Gunthorpe — 2025-01-09

On Thu, Jan 09, 2025 at 12:57:58AM +0800, Xu Yilun wrote:
> On Wed, Jan 08, 2025 at 09:30:26AM -0400, Jason Gunthorpe wrote:
> > On Tue, Jan 07, 2025 at 10:27:15PM +0800, Xu Yilun wrote:

Okay, but then why is it a flag like that? I'm expecting a much
broader system here to make the VFIO device into a confidential device
(like setup the TDI) where we'd have to enforce the private things,
communicate with some secure world to assign it, and so on.

I want to see a fuller solution to the CC problem in VFIO before we
can be sure what is the correct UAPI. In other words, make the
VFIO device into a CC device should also prevent mmaping it and so on.

So, I would take this out and defer VFIO enforcment to a series which
does fuller CC enablement of VFIO.

The precursor work should just be avoiding requiring a VMA when
installing VFIO MMIO into the KVM and IOMMU stage 2 mappings. Ie by
using a FD to get the CPU pfns into iommufd and kvm as you are
showing.

This works just fine for non-CC devices anyhow and is the necessary
building block for making a TDI interface in VFIO.

Jason

---

## [34] Xu Yilun — 2025-01-10

On Thu, Jan 09, 2025 at 10:40:51AM -0400, Jason Gunthorpe wrote:
> On Thu, Jan 09, 2025 at 12:57:58AM +0800, Xu Yilun wrote:
> > On Wed, Jan 08, 2025 at 09:30:26AM -0400, Jason Gunthorpe wrote:

This flag is a prerequisite for setting up TDI, or part of the
requirement to make a "TDI capable" assigned device. It prevents the
userspace mapping at the first place, even as a shared device.

We want the device firstly appear as a shared device in CoCo-VM, then
do TDI setup (via a tsm verb "bind"). This late bind approach avoids
changing the CoCo VM startup routine. In contrast, early bind would
easily be broken, especially if bios is not aware of the TDI rule.

So then we face with the shared <-> private device conversion in CoCo VM,
and in turn shared <-> private MMIO conversion. MMIO region has only one
physical backend so it is a bit like in-place conversion which is
complicated. I wanna simply the MMIO conversion routine based on the fact
that VMM never needs to access assigned MMIO for feature emulation, so
always disallow userspace MMIO mapping during the whole lifecycle. That's
why the flag is introduced.

Patch 6 has similar discription.

> broader system here to make the VFIO device into a confidential device
> (like setup the TDI) where we'd have to enforce the private things,

I plan to introduce a new VFIO ioctl to setup the TDI.

> communicate with some secure world to assign it, and so on.

Yes, the new VFIO ioctl will communicate with PCI TSM.

> 
> I want to see a fuller solution to the CC problem in VFIO before we

MM.. I have something but need more preparation. Whether send out or
make a public repo, I'll discuss with internal.

> can be sure what is the correct UAPI. In other words, make the
> VFIO device into a CC device should also prevent mmaping it and so on.

My idea is prevent mmaping first, then allow VFIO device into CC dev (TDI).

> 
> So, I would take this out and defer VFIO enforcment to a series which

Yes. It carries out the idea of "KVM maps MMIO resources without firstly
mapping into the host" even for normal VM. That's why I think it could
be an independent patchset.

Thanks,
Yilun

> building block for making a TDI interface in VFIO.
>

---

## [35] Jason Gunthorpe — 2025-01-10

On Fri, Jan 10, 2025 at 12:40:28AM +0800, Xu Yilun wrote:

> So then we face with the shared <-> private device conversion in CoCo VM,
> and in turn shared <-> private MMIO conversion. MMIO region has only one

The VMM can simply not map it if for these cases. As part of the TDI
flow the kernel can validate it is not mapped.
 
> > can be sure what is the correct UAPI. In other words, make the
> > VFIO device into a CC device should also prevent mmaping it and so on.

I think you need to start the TDI process much earlier. Some arches
are going to need work to prepare the TDI before the VM is started.

The other issue here is that Intel is somewhat different from others
and when we build uapi for TDI it has to accommodate everyone.

> Yes. It carries out the idea of "KVM maps MMIO resources without firstly
> mapping into the host" even for normal VM. That's why I think it could

Yes, just remove this patch and other TDI focused stuff. Just
infrastructure to move to FD based mapping instead of VMA.

Jason

---

## [36] Simona Vetter — 2025-01-10
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Thu, Jan 09, 2025 at 01:56:02AM +0800, Xu Yilun wrote:
> > > > 5) iommufd and kvm are both using CPU addresses without DMA. No
> > > > exporter mapping is possible

See the comment, it's ok because it's a fake device with fake iommu and
the xen code has special knowledge to peek behind the curtain.
-Sima
 
> From Christion's point, I assume only sgl->dma_address should be
> used by importers but in fact not. More importers are 'abusing' sg dma

---

## [37] Simona Vetter — 2025-01-10
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Thu, Jan 09, 2025 at 07:06:48AM +0800, Xu Yilun wrote:
> >  So I guess my first question is, which locking rules do you want here for
> >  pfn importers?

So if I'm getting this right, what you need from a functional pov is a
dma_buf_tdx_mmap? Because due to tdx restrictions, the normal dma_buf_mmap
is not going to work I guess?

Also another thing that's a bit tricky is that kvm kinda has a 3rd dma-buf
memory model:
- permanently pinned dma-buf, they never move
- dynamic dma-buf, they move through ->move_notify and importers can remap
- revocable dma-buf, which thus far only exist for pci mmio resources

Since we're leaning even more on that 3rd model I'm wondering whether we
should make it something official. Because the existing dynamic importers
do very much assume that re-acquiring the memory after move_notify will
work. But for the revocable use-case the entire point is that it will
never work.

I feel like that's a concept we need to make explicit, so that dynamic
importers can reject such memory if necessary.

So yeah there's a bunch of tricky lifetime questions that need to be
sorted out with proper design I think, and the current "let's just use pfn
directly" proposal hides them all under the rug. I agree with Christian
that we need a bit more care here.
-Sima

> 
> >

---

## [38] Jason Gunthorpe — 2025-01-10
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Fri, Jan 10, 2025 at 08:24:22PM +0100, Simona Vetter wrote:
> On Thu, Jan 09, 2025 at 01:56:02AM +0800, Xu Yilun wrote:
> > > > > 5) iommufd and kvm are both using CPU addresses without DMA. No

        /*
         * Now convert sgt to array of gfns without accessing underlying pages.
         * It is not allowed to access the underlying struct page of an sg table
         * exported by DMA-buf, but since we deal with special Xen dma device here
         * (not a normal physical one) look at the dma addresses in the sg table
         * and then calculate gfns directly from them.
         */
        for_each_sgtable_dma_page(sgt, &sg_iter, 0) {
                dma_addr_t addr = sg_page_iter_dma_address(&sg_iter);
                unsigned long pfn = bfn_to_pfn(XEN_PFN_DOWN(dma_to_phys(dev, addr)));

*barf*

Can we please all agree that is a horrible abuse of the DMA API and
lets not point it as some acceptable "solution"? KVM and iommufd do
not have fake struct devices with fake iommus.

Jason

---

## [39] Jason Gunthorpe — 2025-01-10
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Fri, Jan 10, 2025 at 08:34:55PM +0100, Simona Vetter wrote:

> So if I'm getting this right, what you need from a functional pov is a
> dma_buf_tdx_mmap? Because due to tdx restrictions, the normal dma_buf_mmap

Don't want something TDX specific!

There is a general desire, and CC is one, but there are other
motivations like performance, to stop using VMAs and mmaps as a way to
exchanage memory between two entities. Instead we want to use FDs.

We now have memfd and guestmemfd that are usable with
memfd_pin_folios() - this covers pinnable CPU memory.

And for a long time we had DMABUF which is for all the other wild
stuff, and it supports movable memory too.

So, the normal DMABUF semantics with reservation locking and move
notifiers seem workable to me here. They are broadly similar enough to
the mmu notifier locking that they can serve the same job of updating
page tables.

> Also another thing that's a bit tricky is that kvm kinda has a 3rd dma-buf
> memory model:

I would like to see the importers be able to discover which one is
going to be used, because we have RDMA cases where we can support 1
and 3 but not 2.

revocable doesn't require page faulting as it is a terminal condition.

> Since we're leaning even more on that 3rd model I'm wondering whether we
> should make it something official. Because the existing dynamic importers

> I feel like that's a concept we need to make explicit, so that dynamic
> importers can reject such memory if necessary.

It strikes me as strange that HW can do page faulting, so it can
support #2, but it can't handle a non-present fault?

> So yeah there's a bunch of tricky lifetime questions that need to be
> sorted out with proper design I think, and the current "let's just use pfn

I don't think these two things are connected. The lifetime model that
KVM needs to work with the EPT, and that VFIO needs for it's MMIO,
definately should be reviewed and evaluated.

But it is completely orthogonal to allowing iommufd and kvm to access
the CPU PFN to use in their mapping flows, instead of the
dma_addr_t.

What I want to get to is a replacement for scatter list in DMABUF that
is an array of arrays, roughly like:

  struct memory_chunks {
      struct memory_p2p_provider *provider;
      struct bio_vec addrs[];
  };
  int (*dmabuf_get_memory)(struct memory_chunks **chunks, size_t *num_chunks);

This can represent all forms of memory: P2P, private, CPU, etc and
would be efficient with the new DMA API.

This is similar to the structure BIO has, and it composes nicely with
a future pin_user_pages() and memfd_pin_folios().

Jason

---

## [40] Jason Gunthorpe — 2025-01-10
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Thu, Jan 09, 2025 at 09:09:46AM +0100, Christian König wrote:
> Answering on my reply once more as pure text mail.

It is hard to do anything with your HTML mails :\

> > Well you were also the person who mangled the struct page pointers in
> > the scatterlist because people were abusing this and getting a bloody

But alot of this is because scatterlist is too limited, you actually
can't correctly describe anything except struct page backed CPU memory
in a scatterlist.

As soon as we can correctly describe everything in a datastructure
these issues go away - or at least turn into a compatability
exchange problem.

> > > > Where I do agree with Christian is that stuffing pfn support into the
> > > > dma_buf_attachment interfaces feels a bit much wrong.

Huh? 

mmu notifiers are for tracking changes to VMAs

pin/move_notify are for tracking changes the the underlying memory of
a DMABUF.

How does sharing the PFN vs DMA addre effect the pin/move_notify
lifetime rules at all?

> > > > > > > 3) Importing devices need to know if they are working with PCI P2P
> > > > > > > addresses during mapping because they need to do things like turn on

I should say "mandatory on some configurations"

If you need the iommu turned on, and you have a PCI switch in your
path, then ATS allows you to have full P2P bandwidth and retain full
IOMMU security.

> > We have tons of production systems using PCI P2P without ATS. And it's
> > the first time I hear that.

It is situational and topologically dependent. We have very large
number of deployed systems now that rely on ATS for PCI P2P.

> > As Sima explained you either have follow_pfn() and mmu_notifier or you
> > have DMA addresses and dma_resv lock / dma_fence.

Certainly I never imagined there would be no liftime, I expect
anything coming out of the dmabuf interface to use the dma_resv lock,
fence and move_notify for lifetime managament, regardless of how the
target memory is described.

> > > > separate access mechanism just for that. It would be the 5th or so (kernel
> > > > vmap, userspace mmap, dma_buf_attach and driver private stuff like

> > I don't fully understand your use case, but I think it's quite likely
> > that we already have that working.

In Intel CC systems you cannot mmap secure memory or the system will
take a machine check.

You have to convey secure memory inside a FD entirely within the
kernel so that only an importer that understands how to handle secure
memory (such as KVM) is using it to avoid machine checking.

The patch series here should be thought of as the first part of this,
allowing PFNs to flow without VMAs. IMHO the second part of preventing
machine checks is not complete.

In the approach I have been talking about the secure memory would be
represented by a p2p_provider structure that is incompatible with
everything else. For instance importers that can only do DMA would
simply cleanly fail when presented with this memory.

Jason

---

## [41] Xu Yilun — 2025-01-11

On Fri, Jan 10, 2025 at 09:31:16AM -0400, Jason Gunthorpe wrote:
> On Fri, Jan 10, 2025 at 12:40:28AM +0800, Xu Yilun wrote:
> 

That's a good point. I can try on that.

>  
> > > can be sure what is the correct UAPI. In other words, make the

Could you elaborate more on that? AFAICS Intel & AMD are all good on
"late bind", but not sure for other architectures. This relates to the
definition of TSM verbs and is the right time we collect the needs for
Dan's series.

> 
> The other issue here is that Intel is somewhat different from others

Sure, this is the aim for PCI TSM core, and VFIO as a PCI TSM user
should not be TDX awared.

> 
> > Yes. It carries out the idea of "KVM maps MMIO resources without firstly

Yes.

Thanks,
Yilun

> 
> Jason

---

## [42] Xu Yilun — 2025-01-13
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Fri, Jan 10, 2025 at 04:38:38PM -0400, Jason Gunthorpe wrote:
> On Fri, Jan 10, 2025 at 08:34:55PM +0100, Simona Vetter wrote:
> 

I'm not sure if the word 'mmap' is proper here.

It is kind of like the mapping from (FD+offset) to backend memory,
which is directly provided by memory provider, rather than via VMA
and cpu page table.  Basically VMA & cpu page table are for host to
access the memory, but VMM/host doesn't access most of the guest
memory, so why must build them.

> > is not going to work I guess?
> 

Exactly.

> 
> We now have memfd and guestmemfd that are usable with

Yes. With this new sharing model, the lifecycle of the shared memory/pfn/Page
is directly controlled by dma-buf exporter, not by CPU mapping. So I also
think reservation lock & move_notify works well for lifecycle control,
no conflict (nothing to do) with follow_pfn() & mmu_notifier.

> 
> > Also another thing that's a bit tricky is that kvm kinda has a 3rd dma-buf

Maybe we need to specify which object the API is operating on,
struct dma_buf, or struct dma_buf_attachment, or a new attachment.

I think:

  int (*dmabuf_get_memory)(struct dma_buf_attachment *attach, struct memory_chunks **chunks, size_t *num_chunks);

works, but maybe a new attachment is conceptually more clear to
importers and harder to abuse?

Thanks,
Yilun

> 
> This can represent all forms of memory: P2P, private, CPU, etc and

---

## [43] Jason Gunthorpe — 2025-01-13

On Sat, Jan 11, 2025 at 11:48:06AM +0800, Xu Yilun wrote:

> > > > can be sure what is the correct UAPI. In other words, make the
> > > > VFIO device into a CC device should also prevent mmaping it and so on.

I'm not sure about this, the topic has been confused a bit, and people
often seem to  misunderstand what the full scenario actually is. :\

What I'm talking abou there is that you will tell the secure world to
create vPCI function that has the potential to be secure "TDI run"
down the road. The VM will decide when it reaches the run state. This
is needed so the secure world can prepare anything it needs prior to
starting the VM. Setting up secure vIOMMU emulation, for instance. I
expect ARM will need this, I'd be surprised if AMD actually doesn't in
the full scenario with secure viommu.

It should not be a surprise to the secure world after the VM has
started that suddenly it learns about a vPCI function that wants to be
secure. This should all be pre-arranged as possible before starting
the VM, even if alot of steps happen after the VM starts running (or
maybe don't happen at all).

Jason

---

## [44] Jason Gunthorpe — 2025-01-14

On Tue, Jun 18, 2024 at 07:28:43AM +0800, Xu Yilun wrote:

> > is needed so the secure world can prepare anything it needs prior to
> > starting the VM.

I think Dan's series is different, any uapi from that series should
not be used in the VMM case. We need proper vfio APIs for the VMM to
use. I would expect VFIO to be calling some of that infrastructure.

Really, I don't see a clear sense of how this will look yet. AMD
provided some patches along these lines, I have not seem ARM and Intel
proposals yet, not do I sense there is alignment.

> > Setting up secure vIOMMU emulation, for instance. I
> 

The vIOMMU needs to be setup before the VM boots

> > secure. This should all be pre-arranged as possible before starting
> 

That's fine too, but both options need to be valid.

Jason

---

## [45] Simona Vetter — 2025-01-14
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Fri, Jan 10, 2025 at 04:38:38PM -0400, Jason Gunthorpe wrote:
> On Fri, Jan 10, 2025 at 08:34:55PM +0100, Simona Vetter wrote:
> 

Yeah raw pfn is fine with me too. It might come with more "might not work
on this dma-buf" restrictions, but I can't think of a practical one right
now.

> > Also another thing that's a bit tricky is that kvm kinda has a 3rd dma-buf
> > memory model:

Yeah this is why I think we should separate the dynamic from the revocable
use-cases clearly, because mixing them is going to result in issues.

> > Since we're leaning even more on that 3rd model I'm wondering whether we
> > should make it something official. Because the existing dynamic importers

I guess it's not a kernel issue, but userspace might want to know whether
this dma-buf could potentially nuke the entire gpu context. Because that's
what you get when we can't patch up a fault, which is the difference
between a recovable dma-buf and a dynamic dma-buf.

E.g. if a compositor gets a dma-buf it assumes that by just binding that
it will not risk gpu context destruction (unless you're out of memory and
everything is on fire anyway, and it's ok to die). But if a nasty client
app supplies a revocable dma-buf, then it can shot down the higher
priviledged compositor gpu workload with precision. Which is not great, so
maybe existing dynamic gpu importers should reject revocable dma-buf.
That's at least what I had in mind as a potential issue.

> > So yeah there's a bunch of tricky lifetime questions that need to be
> > sorted out with proper design I think, and the current "let's just use pfn

Since you mention pin here, I think that's another aspect of the revocable
vs dynamic question. Dynamic buffers are expected to sometimes just move
around for no reason, and importers must be able to cope.

For recovable exporters/importers I'd expect that movement is not
happening, meaning it's pinned until the single terminal revocation. And
maybe I read the kvm stuff wrong, but it reads more like the latter to me
when crawling through the pfn code.

Once we have the lifetime rules nailed then there's the other issue of how
to describe the memory, and my take for that is that once the dma-api has
a clear answer we'll just blindly adopt that one and done.

And currently with either dynamic attachments and dma_addr_t or through
fishing the pfn from the cpu pagetables there's some very clearly defined
lifetime and locking rules (which kvm might get wrong, I've seen some
discussions fly by where it wasn't doing a perfect job with reflecting pte
changes, but that was about access attributes iirc). If we add something
new, we need clear rules and not just "here's the kvm code that uses it".
That's how we've done dma-buf at first, and it was a terrible mess of
mismatched expecations.
-Sima

---

## [46] Jason Gunthorpe — 2025-01-14
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Tue, Jan 14, 2025 at 03:44:04PM +0100, Simona Vetter wrote:

> E.g. if a compositor gets a dma-buf it assumes that by just binding that
> it will not risk gpu context destruction (unless you're out of memory and

I see, so it is not that they can't handle a non-present fault it is
just that the non-present effectively turns into a crash of the
context and you want to avoid the crash. It makes sense to me to
negotiate this as part of the API.

> > This is similar to the structure BIO has, and it composes nicely with
> > a future pin_user_pages() and memfd_pin_folios().

Yes, and we have importers that can tolerate dynamic and those that
can't. Though those that can't tolerate it can often implement revoke.

I view your list as a cascade:
 1) Fully pinned can never be changed so long as the attach is present
 2) Fully pinned, but can be revoked. Revoked is a fatal condition and
    the importer is allowed to experience an error
 3) Fully dynamic and always present. Support for move, and
    restartable fault, is required

Today in RDMA we ask the exporter if it is 1 or 3 and allow different
things. I've seen the GPU side start to offer 1 more often as it has
significant performance wins.

> For recovable exporters/importers I'd expect that movement is not
> happening, meaning it's pinned until the single terminal revocation. And

kvm should be fully faultable and it should be able handle move. It
handles move today using the mmu notifiers after all.

kvm would need to interact with the dmabuf reservations on its page
fault path.

iommufd cannot be faultable and it would only support revoke. For VFIO
revoke would not be fully terminal as VFIO can unrevoke too
(sigh).  If we make revoke special I'd like to eventually include
unrevoke for this reason.

> Once we have the lifetime rules nailed then there's the other issue of how
> to describe the memory, and my take for that is that once the dma-api has

This is what I hope, we are not there yet, first Leon's series needs
to get merged then we can start on making the DMA API P2P safe without
any struct page. From there it should be clear what direction things
go in.

DMABUF would return pfns annotated with whatever matches the DMA API,
and the importer would be able to inspect the PFNs to learn
information like their P2Pness, CPU mappability or whatever.

I'm pushing for the extra struct, and Christoph has been thinking
about searching a maple tree on the PFN. We need to see what works best.

> And currently with either dynamic attachments and dma_addr_t or through
> fishing the pfn from the cpu pagetables there's some very clearly defined

Wouldn't surprise me, mmu notifiers are very complex all around. We've
had bugs already where the mm doesn't signal the notifiers at the
right points.

> If we add something
> new, we need clear rules and not just "here's the kvm code that uses it".

Yes, that would be wrong. It should be self defined within dmabuf and
kvm should adopt to it, move semantics and all.

My general desire is to move all of RDMA's MR process away from
scatterlist and work using only the new DMA API. This will save *huge*
amounts of memory in common workloads and be the basis for non-struct
page DMA support, including P2P.

Jason

---

## [47] Simona Vetter — 2025-01-15
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Tue, Jan 14, 2025 at 01:31:03PM -0400, Jason Gunthorpe wrote:
> On Tue, Jan 14, 2025 at 03:44:04PM +0100, Simona Vetter wrote:
> 

Yup.

> > > This is similar to the structure BIO has, and it composes nicely with
> > > a future pin_user_pages() and memfd_pin_folios().

I'm not entirely sure a cascade is the right thing or whether we should
have importers just specify bitmask of what is acceptable to them. But
that little detail aside this sounds like what I was thinking of.

> > For recovable exporters/importers I'd expect that movement is not
> > happening, meaning it's pinned until the single terminal revocation. And

I think for 90% of exporters pfn would fit, but there's some really funny
ones where you cannot get a cpu pfn by design. So we need to keep the
pfn-less interfaces around. But ideally for the pfn-capable exporters we'd
have helpers/common code that just implements all the other interfaces.

I'm not worried about the resulting fragmentation, because dma-buf is the
"everythig is optional" api. We just need to make sure we have really
clear semantic api contracts, like with the revocable vs dynamic/moveable
distinction. Otherwise things go boom when an importer gets an unexpected
dma-buf fd, and we pass this across security boundaries a lot.

> I'm pushing for the extra struct, and Christoph has been thinking
> about searching a maple tree on the PFN. We need to see what works best.

Ack.

I feel like we have a plan here. Summary from my side:

- Sort out pin vs revocable vs dynamic/moveable semantics, make sure
  importers have no surprises.

- Adopt whatever new dma-api datastructures pops out of the dma-api
  reworks.

- Add pfn based memory access as yet another optional access method, with
  helpers so that exporters who support this get all the others for free.

I don't see a strict ordering between these, imo should be driven by
actual users of the dma-buf api.

Already done:

- dmem cgroup so that we can resource control device pinnings just landed
  in drm-next for next merge window. So that part is imo sorted and we can
  charge ahead with pinning into device memory without all the concerns
  we've had years ago when discussing that for p2p dma-buf support.

  But there might be some work so that we can p2p pin without requiring
  dynamic attachments only, I haven't checked whether that needs
  adjustment in dma-buf.c code or just in exporters.

Anything missing?

I feel like this is small enough that m-l archives is good enough. For
some of the bigger projects we do in graphics we sometimes create entries
in our kerneldoc with wip design consensus and things like that. But
feels like overkill here.

> My general desire is to move all of RDMA's MR process away from
> scatterlist and work using only the new DMA API. This will save *huge*

Yeah a more memory efficient structure than the scatterlist would be
really nice. That would even benefit the very special dma-buf exporters
where you cannot get a pfn and only the dma_addr_t, altough most of those
(all maybe even?) have contig buffers, so your scatterlist has only one
entry. But it would definitely be nice from a design pov.

Aside: A way to more efficiently create compressed scatterlists would be
neat too, because a lot of drivers hand-roll that and it's a bit brittle
and kinda silly to duplicate. With compressed I mean just a single entry
for a contig range, in practice thanks to huge pages/folios and allocators
trying to hand out contig ranges if there's plenty of memory that saves a
lot of memory too. But currently it's a bit a pain to construct these
efficiently, mostly it's just a two-pass approach and then trying to free
surplus memory or krealloc to fit. Also I don't have good ideas here, but
dma-api folks might have some from looking at too many things that create
scatterlists.
-Sima

---

## [48] Christoph Hellwig — 2025-01-15
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce
 dma_buf_get_pfn_unlocked() kAPI*

On Wed, Jan 15, 2025 at 09:55:29AM +0100, Simona Vetter wrote:
> I think for 90% of exporters pfn would fit, but there's some really funny
> ones where you cannot get a cpu pfn by design. So we need to keep the

There is no way to have dma address without a PFN in Linux right now.
How would you generate them?  That implies you have an IOMMU that can
generate IOVAs for something that doesn't have a physical address at
all.

Or do you mean some that don't have pages associated with them, and
thus have pfn_valid fail on them?  They still have a PFN, just not
one that is valid to use in most of the Linux MM.

---

## [49] Christian König — 2025-01-15
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

Am 10.01.25 um 21:54 schrieb Jason Gunthorpe:
> [SNIP]
>>> I don't fully understand your use case, but I think it's quite likely

That's a rather interesting use case, but not something I consider 
fitting for the DMA-buf interface.

See DMA-buf in meant to be used between drivers to allow DMA access on 
shared buffers.

What you try to do here instead is to give memory in the form of a file 
descriptor to a client VM to do things like CPU mapping and giving it to 
drivers to do DMA etc...

As far as I can see this memory is secured by some kind of MMU which 
makes sure that even the host CPU can't access it without causing a 
machine check exception.

That sounds more something for the TEE driver instead of anything 
DMA-buf should be dealing with.

Regards,
Christian.

>
> Jason

---

## [50] Alexey Kardashevskiy — 2025-01-15

On 15/1/25 00:35, Jason Gunthorpe wrote:
> On Tue, Jun 18, 2024 at 07:28:43AM +0800, Xu Yilun wrote:
> 

Something like this experiment?

https://github.com/aik/linux/commit/ce052512fb8784e19745d4cb222e23cabc57792e

Thanks,

> 
> Really, I don't see a clear sense of how this will look yet. AMD

---

## [51] Jason Gunthorpe — 2025-01-15

On Wed, Jan 15, 2025 at 11:57:05PM +1100, Alexey Kardashevskiy wrote:
> On 15/1/25 00:35, Jason Gunthorpe wrote:
> > On Tue, Jun 18, 2024 at 07:28:43AM +0800, Xu Yilun wrote:

Yeah, maybe, though I don't know which of vfio/iommufd/kvm should be
hosting those APIs, the above does seem to be a reasonable direction.

When the various fds are closed I would expect the kernel to unbind
and restore the device back.

Jason

---

## [52] Jason Gunthorpe — 2025-01-15
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Wed, Jan 15, 2025 at 10:32:34AM +0100, Christoph Hellwig wrote:
> On Wed, Jan 15, 2025 at 09:55:29AM +0100, Simona Vetter wrote:
> > I think for 90% of exporters pfn would fit, but there's some really funny

He is talking about private interconnect hidden inside clusters of
devices.

Ie the system may have many GPUs and those GPUs have their own private
interconnect between them. It is not PCI, and packets don't transit
through the CPU SOC at all, so the IOMMU is not involved.

DMA can happen on that private interconnect, but from a Linux
perspective it is not DMA API DMA, and the addresses used to describe
it are not part of the CPU address space. The initiating device will
have a way to choose which path the DMA goes through when setting up
the DMA.

Effectively if you look at one of these complex GPU systems you will
have a physical bit of memory, say HBM memory located on the GPU. Then
from an OS perspective we have a whole bunch of different
representations/addresses of that very same memory. A Grace/Hopper
system would have at least three different addresses (ZONE_MOVABLE, a
PCI MMIO aperture, and a global NVLink address). Each different
address effectively represents a different physical interconnect
multipath, and an initiator may have three different routes/addresses
available to reach the same physical target memory.

Part of what DMABUF needs to do is pick which multi-path will be used
between expoter/importer.

So, the hack today has the DMABUF exporter GPU driver understand the
importer is part of the private interconnect and then generate a
scatterlist with a NULL sg_page, but a sg_dma_addr that encodes the
private global address on the hidden interconnect. Somehow the
importer knows this has happened and programs its HW to use the
private path.

Jason

---

## [53] Jason Gunthorpe — 2025-01-15
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Wed, Jan 15, 2025 at 10:38:00AM +0100, Christian König wrote:
> Am 10.01.25 um 21:54 schrieb Jason Gunthorpe:
> > [SNIP]

To recast the problem statement, it is basically the same as your
device private interconnects. There are certain devices that
understand how to use this memory, and if they work together they can
access it.
 
> See DMA-buf in meant to be used between drivers to allow DMA access on
> shared buffers.

They are shared, just not with everyone :)
 
> What you try to do here instead is to give memory in the form of a file
> descriptor to a client VM to do things like CPU mapping and giving it to

How is this paragraph different from the first? It is a shared buffer
that we want real DMA and CPU "DMA" access to. It is "private" so
things that don't understand the interconnect rules cannot access it.

> That sounds more something for the TEE driver instead of anything DMA-buf
> should be dealing with.

Has nothing to do with TEE.

Jason

---

## [54] Christian König — 2025-01-15
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

Explicitly replying as text mail once more.

I just love the AMD mails servers :(

Christian.

Am 15.01.25 um 14:45 schrieb Christian König:
> Am 15.01.25 um 14:38 schrieb Jason Gunthorpe:
>> On Wed, Jan 15, 2025 at 10:38:00AM +0100, Christian König wrote:

---

## [55] Jason Gunthorpe — 2025-01-15
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Wed, Jan 15, 2025 at 02:46:56PM +0100, Christian König wrote:
> Explicitly replying as text mail once more.
> 

:( This is hard

> > Yeah, but it's private to the exporter. And a very fundamental rule of
> > DMA-buf is that the exporter is the one in control of things.

I've said a few times now, I don't think we can build the kind of
buffer sharing framework we need to solve all the problems with this
philosophy. It is also inefficient with the new DMA API.

I think it is backwards looking and we need to move forwards with
fixing the fundamental API issues which motivated that design.

> > So for example it is illegal for an importer to setup CPU mappings to a
> > buffer. That's why we have dma_buf_mmap() which redirects mmap()

Like this, in a future no-scatter list world I would want to make this
safe. The importer will have enough information to know if CPU
mappings exist and are safe to use under what conditions.

There is no reason the importer should not be able to CPU access
memory that is HW permitted to be CPU accessible.

If the importer needs CPU access and the exporter cannot provide it
then the attachment simply fails.

Saying CPU access is banned 100% of the time is not a helpful position
when we have use cases that need it.

> > As far as I can see that is really not an use case which fits DMA-buf in
> > any way.

I really don't want to make a dmabuf2 - everyone would have to
implement it, including all the GPU drivers if they want to work with
RDMA. I don't think this makes any sense compared to incrementally
evolving dmabuf with more optional capabilities.

> > > > That sounds more something for the TEE driver instead of anything DMA-buf
> > > > should be dealing with.

The Linux TEE framework is not used as part of confidential compute.

CC already has guest memfd for holding it's private CPU memory.

This is about confidential MMIO memory.

This is also not just about the KVM side, the VM side also has issues
with DMABUF and CC - only co-operating devices can interact with the
VM side "encrypted" memory and there needs to be a negotiation as part
of all buffer setup what the mutual capability is. :\ swiotlb hides
some of this some times, but confidential P2P is currently unsolved.

Jason

---

## [56] Christian König — 2025-01-15
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

Sending it as text mail to the mailing lists once more :(

Christian.

Am 15.01.25 um 15:29 schrieb Christian König:
> Am 15.01.25 um 15:14 schrieb Jason Gunthorpe:
>> On Wed, Jan 15, 2025 at 02:46:56PM +0100, Christian König wrote:

---

## [57] Jason Gunthorpe — 2025-01-15
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Wed, Jan 15, 2025 at 03:30:47PM +0100, Christian König wrote:

> > Those rules are not something we cam up with because of some limitation
> > of the DMA-API, but rather from experience working with different device

I would say it stems from the use of scatter list. You do not have
enough information exchanged between exporter and importer to
implement something sane and correct. At that point being restrictive
is a reasonable path.

Because of scatterlist developers don't have APIs that correctly solve
the problems they want to solve, so of course things get into a mess.

> > Applying and enforcing those restrictions is absolutely mandatory must
> > have for extending DMA-buf.

You said to come to the maintainers with the problems, here are the
problems. Your answer is don't use dmabuf.

That doesn't make the problems go away :(

> > > I really don't want to make a dmabuf2 - everyone would have to
> > > implement it, including all the GPU drivers if they want to work with

You'd need to be much more concrete and technical in your objections
to cause a rejection. "We tried something else before and it didn't
work" won't cut it.

There is a very simple problem statement here, we need a FD handle for
various kinds of memory, with a lifetime model that fits a couple of
different use cases. The exporter and importer need to understand what
type of memory it is and what rules apply to working with it. The
required importers are more general that just simple PCI DMA.

I feel like this is already exactly DMABUF's mission.

Besides, you have been saying to go do this in TEE or whatever, how is
that any different from dmabuf2?

> > > > > > > That sounds more something for the TEE driver instead of anything DMA-buf
> > > > > > > should be dealing with.

What do you mean? guest memfd is the result of years of negotiation in
the mm and x86 arch subsystems :( It is used like a normal memfd, and
we now have APIs in KVM and iommufd to directly intake and map from a
memfd. I expect guestmemfd will soon grow some more generic
dmabuf-like lifetime callbacks to avoid pinning - it already has some
KVM specific APIs IIRC.

But it is 100% exclusively focused on CPU memory and nothing else.

> > > This is about confidential MMIO memory.
> > 

In this case Xu is exporting MMIO from VFIO and importing to KVM and
iommufd.

> > This is also not just about the KVM side, the VM side also has issues
> > with DMABUF and CC - only co-operating devices can interact with the

I doubt that. It is complex and not fully solved in the core code
today. Many scenarios do not work correctly, devices don't even exist
yet that can exercise the hard paths. This is a future problem :(

Jason

---

## [58] Jason Gunthorpe — 2025-01-15
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Wed, Jan 15, 2025 at 05:34:23PM +0100, Christian König wrote:
>    Granted, let me try to improve this.
>    Here is a real world example of one of the issues we ran into and why

But this, fundamentally, is importers creating attachments and then
*ignoring the lifetime rules of DMABUF*. If you created an attachment,
got a move and *ignored the move* because you put the PFN in your own
VMA, then you are not following the attachment lifetime rules!

To implement this safely the driver would need to use
unma_mapping_range() on the driver VMA inside the move callback, and
hook into the VMA fault callback to re-attach the dmabuf.

This is where I get into trouble with your argument. It is not that
the API has an issue, or that the rules of the API are not logical and
functional.

You are arguing that even a logical and functional API will be
mis-used by some people and that reviewers will not catch
it.

Honestly, I don't think that is consistent with the kernel philosophy.

We should do our best to make APIs that are had to mis-use, but if we
can't achieve that it doesn't mean we stop and give up on problems,
we go into the world of APIs that can be mis-used and we are supposed
to rely on the reviewer system to catch it.

>    You can already turn both a TEE allocated buffer as well as a memfd
>    into a DMA-buf. So basically TEE and memfd already provides different

>    In other words if you want to do things like direct I/O to block or
>    network devices you can mmap() your memfd and do this while at the same

I guess, but this still requires creating a dmabuf2 type thing with
very similar semantics and then shimming dmabuf2 to 1 for DRM consumers.

I don't see how it addresses your fundamental concern that the
semantics we want are an API that is too easy for drivers to abuse.

And being more functional and efficient we'd just see people wanting
to use dmabuf2 directly instead of bothering with 1.

>    separate file descriptor representing the private MMIO which iommufd
>    and KVM uses but you can turn it into a DMA-buf whenever you need to

Well, it would end up just being used everywhere. I think one person
wanted to use this with DRM drivers for some reason, but RDMA would
use the dmabuf2 directly because it will be much more efficient than
using scatterlist.

Honestly, I'd much rather extend dmabuf and see DRM institute some
rule that DRM drivers may not use XYZ parts of the improvement. Like
maybe we could use some symbol namespaces to really enforce it
eg. MODULE_IMPORT_NS(DMABUF_NOT_FOR_DRM_USAGE)

Some of the improvements we want like the revoke rules for lifetime
seem to be agreeable.

Block the API that gives you the non-scatterlist attachment. Only
VFIO/RDMA/kvm/iommufd will get to implement it.

> In this case Xu is exporting MMIO from VFIO and importing to KVM and
> iommufd.

And KVM. We need to get the CPU address into KVM and IOMMU page
tables. It must go through a private FD path and not a VMA because of
the CC rules about machine check I mentioned earlier. The private FD
must have a lifetime model to ensure we don't UAF the PCIe BAR memory.

Someone else had some use case where they wanted to put the VFIO MMIO
PCIe BAR into a DMABUF and ship it into a GPU driver for
somethingsomething virtualization but I didn't understand it.

>    Let's just say that both the ARM guys as well as the GPU people already
>    have some pretty "interesting" ways of doing digital rights management

Well, that is TEE stuff, TEE and CC are not the same thing, though
they have some high level conceptual overlap.

In a certain sense CC is a TEE that is built using KVM instead of the
TEE subsystem. Using KVM and integrating with the MM brings a whole
set of unique challenges that TEE got to avoid.. 

Jason

---

## [59] Christoph Hellwig — 2025-01-16
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce
 dma_buf_get_pfn_unlocked() kAPI*

On Wed, Jan 15, 2025 at 09:34:19AM -0400, Jason Gunthorpe wrote:
> > Or do you mean some that don't have pages associated with them, and
> > thus have pfn_valid fail on them?  They still have a PFN, just not

So how is this in any way relevant to dma_buf which operates on
a dma_addr_t right now and thus by definition can't be used for
these?

---

## [60] Jason Gunthorpe — 2025-01-16
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Thu, Jan 16, 2025 at 06:33:48AM +0100, Christoph Hellwig wrote:
> On Wed, Jan 15, 2025 at 09:34:19AM -0400, Jason Gunthorpe wrote:
> > > Or do you mean some that don't have pages associated with them, and

Oh, well since this private stuff exists the DRM folks implemented it
and used dmabuf to hook it together tough the uAPI. To make it work it
abuses scatterlist and dma_addr_t to carry this other information.

Thus the pushback in this thread we can't naively fixup dmabuf because
this non-dma_addr_t abuse exists and is uAPI. So it also needs some
improved architecture to move forward :\

Basically, the scatterlist in dmabuf API does not follow any of the
normal rules scatterlist should follow. It is not using the semantics
of dma_addr_t even though that is the type. It is really just an array
of addr/len pairs - we can't reason about it in the normal way :(

Jason

---

## [61] Jason Gunthorpe — 2025-01-16
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Thu, Jan 16, 2025 at 04:13:13PM +0100, Christian König wrote:
>> But this, fundamentally, is importers creating attachments and then
>> *ignoring the lifetime rules of DMABUF*. If you created an attachment,

I feel that it is a bit pedantic to say DMA and CPU are somehow
different. The DMABUF API gives you a scatterlist, it is reasonable to
say that move invalidates the entire scatterlist, CPU and DMA equally.

>    This semantics doesn't work well for CPU mappings because you need to
>    hold the reservation lock to make sure that the information stay valid

Sure, I imagine hooking up a VMA is hard - but that doesn't change my
point. The semantics can be reasonable and well defined.

>    Yeah and exactly that is something we don't want to allow because it
>    means that every importer need to get things right to prevent exporters

You can make the same argument about the DMA address. We should just
get rid of DMABUF entirely because people are going to mis-use it and
wrongly implement the invalidation callback.

I have no idea why GPU drivers want to implement mmap of dmabuf, that
seems to be a uniquely GPU thing. We are not going to be doing stuff
like that in KVM and other places. And we can implement the
invalidation callback with correct locking. Why should we all be
punished because DRM drivers seem to have this weird historical mmap
problem?

I don't think that is a reasonable way to approach building a general
purpose linux kernel API.
 
>    Well it's not miss-used, it's just a very bad design decision to let
>    every importer implement functionality which actually belong into a

Well, this is the problem. Sure it may be that importers should not
implement mmap - but using the PFN side address is needed for more
than just mmap!

DMA mapping belongs in the importer, and the new DMA API makes this
even more explicit by allowing the importer alot of options to
optimize the process of building the HW datastructures. Scatterlist
and the enforeced represetation of the DMA list is very inefficient
and we are working to get rid of it. It isn't going to be replaced by
any sort of list of DMA addresses though.

If you really disagree you can try to convince the NVMe people to give
up their optimizations the new DMA API allows so DRM can prevent this
code-review problem.

I also want the same optimizations in RDMA, and I am also not
convinced giving them up is a worthwhile tradeoff.

>    Why would you want to do a dmabuf2 here?

Because I need the same kind of common framework. I need to hook VFIO
to RDMA as well. I need to fix RDMA to have working P2P in all
cases. I need to hook KVM virtual device stuff to iommufd. Someone
else need VFIO to hook into DRM.

How many different times do I need to implement a buffer sharing
lifetime model? No, we should not make a VFIO specific thing, we need
a general tool to do this properly and cover all the different use
cases. That's "dmabuf2" or whatever you want to call it. There are
more than enough use cases to justify doing this. I think this is a
bad idea, we do not need two things, we should have dmabuf to handle
all the use cases people have, not just DRMs.

>    I don't mind improving the scatterlist approach in any way possible.
>    I'm just rejecting things which we already tried and turned out to be a

This is not welcomed, having lists of DMA addresses is inefficient and
does not match the direction of the DMA API. We are trying very hard
to completely remove the lists of DMA addresses in common fast paths.

>    But exposing PFNs and letting the importers created their DMA mappings
>    themselves and making CPU mappings themselves is an absolutely clear

Again, this is what we must have to support the new DMA API, the KVM
and IOMMUFD use cases I mentioned.

>> In this case Xu is exporting MMIO from VFIO and importing to KVM and
>> iommufd.

Yeah, and KVM. And RMDA.

>    Then create an interface between VFIO and KVM/iommufd which allows to
>    pass data between these two.

I have no idea what this means. We'd need a new API linked to DMABUF
that would be optional and used by this part of the world. As I said
above we could protect it with some module namespace so you can keep
it out of DRM. If you can agree to that then it seems fine..

> > Someone else had some use case where they wanted to put the VFIO MMIO
> > PCIe BAR into a DMABUF and ship it into a GPU driver for

No, it isn't. Christoph is blocking DMABUF in VFIO because he does not
want to scatterlist abuses that dmabuf is doing to proliferate.  We
already have some ARM systems where the naive way typical DMABUF
implementations are setting up P2P does not work. Those systems have
PCI offset.

Getting this to be "perfectly supported" is why we are working on all
these aspects to improve the DMA API and remove the scatterlist
abuses.

>> In a certain sense CC is a TEE that is built using KVM instead of the
>> TEE subsystem. Using KVM and integrating with the MM brings a whole

TEE broadly has Linux launch a secure world that does some private
work. The secure worlds tend to be very limited, they are not really
VMs and they don't run full Linux inside

CC broadly has the secure world exist at boot and launch Linux and
provide services to Linux. The secure world enforces memory isolation
on Linux and generates faults on violations. KVM is the gateway to
launch new secure worlds and the secure worlds are full VMs with all
the device emulation and more.

It CC is much more like xen with it's hypervisor and DOM0 concepts.

From this perspective, the only thing that matters is that CC secure
memory is different and special - it is very much like your private
memory concept. Only special places that understand it and have the
right HW capability can use it. All the consumers need a CPU address
to program their HW because of how the secure world security works.

Jason

---

## [62] Baolu Lu — 2025-01-17

On 1/15/25 21:01, Jason Gunthorpe wrote:
> On Wed, Jan 15, 2025 at 11:57:05PM +1100, Alexey Kardashevskiy wrote:
>> On 15/1/25 00:35, Jason Gunthorpe wrote:

I am curious about the value of tsm binding against an iomnufd_vdevice
instead of the physical iommufd_device.

It is likely that the kvm pointer should be passed to iommufd during the
creation of a viommu object. If my recollection is correct, the arm
smmu-v3 needs it to obtain the vmid to setup the userspace event queue:

struct iommufd_viommu *arm_vsmmu_alloc(struct device *dev,
                                        struct iommu_domain *parent,
                                        struct iommufd_ctx *ictx,
                                        unsigned int viommu_type)
{

[...]

         /* FIXME Move VMID allocation from the S2 domain allocation to 
here */
         vsmmu->vmid = s2_parent->s2_cfg.vmid;

         return &vsmmu->core;
}

Intel TDX connect implementation also needs a reference to the kvm
pointer to obtain the secure EPT information. This is crucial because
the CPU's page table must be shared with the iommu. I am not sure
whether the amd architecture has a similar requirement.

---
baolu

---

## [63] Jason Gunthorpe — 2025-01-17

On Fri, Jan 17, 2025 at 09:57:40AM +0800, Baolu Lu wrote:
> On 1/15/25 21:01, Jason Gunthorpe wrote:
> > On Wed, Jan 15, 2025 at 11:57:05PM +1100, Alexey Kardashevskiy wrote:

Interesting question
 
> It is likely that the kvm pointer should be passed to iommufd during the
> creation of a viommu object. 

Yes, I fully expect this

> If my recollection is correct, the arm
> smmu-v3 needs it to obtain the vmid to setup the userspace event queue:

Right now it will use a VMID unrelated to KVM. BTM support on ARM will
require syncing the VMID with KVM.

AMD and Intel may require the KVM for some reason as well.

For CC I'm expecting the KVM fd to be the handle for the cVM, so any
RPCs that want to call into the secure world need the KVM FD to get
the cVM's identifier. Ie a "bind to cVM" RPC will need the PCI
information and the cVM's handle.

From that perspective it does make sense that any cVM related APIs,
like "bind to cVM" would be against the VDEVICE where we have a link
to the VIOMMU which has the KVM. On the iommufd side the VIOMMU is
part of the object hierarchy, but does not necessarily have to force a
vIOMMU to appear in the cVM.

But it also seems to me that VFIO should be able to support putting
the device into the RUN state without involving KVM or cVMs.

> Intel TDX connect implementation also needs a reference to the kvm
> pointer to obtain the secure EPT information. This is crucial because

I thought kvm folks were NAKing this sharing entirely? Or is the
secure EPT in the secure world and not directly managed by Linux?

AFAIK AMD is going to mirror the iommu page table like today.

ARM, I suspect, will not have an "EPT" under Linux control, so
whatever happens will be hidden in their secure world.

Jason

---

## [64] Simona Vetter — 2025-01-17
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Thu, Jan 16, 2025 at 12:07:47PM -0400, Jason Gunthorpe wrote:
> On Thu, Jan 16, 2025 at 04:13:13PM +0100, Christian K�nig wrote:
> >> But this, fundamentally, is importers creating attachments and then

dma-buf doesn't even give you a scatterlist, there's dma-buf which truly
are just handles that are 100% device specific.

It really is the "everything is optional" interface. And yes we've had
endless amounts of fun where importers tried to peek behind the curtain,
largely because scatterlists didn't cleanly separate the dma_addr_t from
the struct page side of things. So I understand Christian's concerns here.

But that doesn't mean we cannot add another interface that does allow
importers to peek behind the curtiain. As long as we don't make a mess and
confuse importers, and ideally have compat functions so that existing
importers can deal with pfn exporters too it's all fine with me.

And I also don't see an issue with reasonable pfn semantics that would
prevent a generic mmap implementation on top of that, so that
dma_buf_mmap() just works for those. The mmu notifier pain is when you
consume mmaps/vma in a generic way, but implementing mmap with the current
dma_resv locking is dead easy. Unless I've missed something nonobvious and
just made a big fool of myself :-)

What we cannot demand is that all existing dma-buf exporters switch over
to the pfn interfaces. But hey it's the everything optional interface, the
only things is guarantees are
- fixed length
- no copying
- refcounting and yay it only took 10 years: consistent locking rules

So I really don't understand Christian's fundamental opposition here.

Cheers, Sima

> >    This semantics doesn't work well for CPU mappings because you need to
> >    hold the reservation lock to make sure that the information stay valid

---

## [65] Simona Vetter — 2025-01-17
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Wed, Jan 15, 2025 at 11:06:53AM +0100, Christian K�nig wrote:
> Am 15.01.25 um 09:55 schrieb Simona Vetter:
> > > > If we add something

This proposal isn't about forcing existing exporters to allow importers to
do new stuff. That stays as-is, because it would break things.

It's about adding yet another interface to get at the underlying data, and
we have tons of those already. The only difference is that if we don't
butcher the design, we'll be able to implement all the existing dma-buf
interfaces on top of this new pfn interface, for some neat maximal
compatibility.

But fundamentally there's never been an expectation that you can take any
arbitrary dma-buf and pass it any arbitrary importer, and that is must
work. The fundamental promise is that if it _does_ work, then
- it's zero copy
- and fast, or as fast as we can make it

I don't see this any different than all the much more specific prposals
and existing code, where a subset of importers/exporters have special
rules so that e.g. gpu interconnect or vfio uuid based sharing works.
pfn-based sharing is just yet another flavor that exists to get the max
amount of speed out of interconnects.

Cheers, Sima

> 
> The semantics for things like pin vs revocable vs dynamic/moveable seems

---

## [66] Baolu Lu — 2025-01-20

On 1/17/25 21:25, Jason Gunthorpe wrote:
>> If my recollection is correct, the arm
>> smmu-v3 needs it to obtain the vmid to setup the userspace event queue:

Yea, from that perspective, treating the vDEVICE object as the primary
focus for the uAPIs of cVMs is more reasonable. This simplifies the
iommu drivers by eliminating the need to verify hardware capabilities
and compatibilities within each callback. Everything could be done in
one shot when allocating the vDEVICE object.

> 
> But it also seems to me that VFIO should be able to support putting

Then, it appears that BIND ioctl should be part of VFIO uAPI.

>> Intel TDX connect implementation also needs a reference to the kvm
>> pointer to obtain the secure EPT information. This is crucial because

Yes, previous idea of *generic* EPT sharing was objected by the kvm
folks. The primary concern, as I understand it, is that KVM has many
"page non-present" tricks in EPT, which are not applicable to IOPT.
Consequently, KVM must now consider IOPT requirements when sharing the
EPT with the IOMMU, which presents a significant maintenance burden for
the KVM folks.

> secure EPT in the secure world and not directly managed by Linux?
But Secure EPT is managed by the TDX module within the secure world.
Crucially, KVM does not involve any such mechanisms. The firmware
guarantees that any Secure EPT configuration will be applicable to
Secure IOPT. This approach may alleviate concerns raised by the KVM
community.

> AFAIK AMD is going to mirror the iommu page table like today.
> 

Intel also does not have an EPT under Linux control. The KVM has a
mirrored page table and syncs it with the secure EPT managed by firmware
every time it is updated through the ABIs defined by the firmware.

Thanks,
baolu

---

## [67] Alexey Kardashevskiy — 2025-01-20

On 18/1/25 00:25, Jason Gunthorpe wrote:
> On Fri, Jan 17, 2025 at 09:57:40AM +0800, Baolu Lu wrote:
>> On 1/15/25 21:01, Jason Gunthorpe wrote:

And keep KVM fd open until unbind? Or just for the short time to call 
the PSP?

>  From that perspective it does make sense that any cVM related APIs,
> like "bind to cVM" would be against the VDEVICE where we have a link

Well, in my sketch it "appears" as an ability to make GUEST TIO REQUEST 
calls (guest <-> secure FW protocol).

> But it also seems to me that VFIO should be able to support putting
> the device into the RUN state without involving KVM or cVMs.

AMD's TDI bind handler in the PSP wants a guest handle ("GCTX") and a 
guest device BDFn, and VFIO has no desire to dive into this KVM business 
beyond IOMMUFD.

And then this GUEST TIO REQUEST which is used for 1) enabling secure 
part of IOMMU (so it relates to IOMMUFD)  2) enabling secure MMIO (which 
is more VFIO business).

We can do all sorts of things but the lifetime of these entangled 
objects is tricky sometimes. Thanks,


>> Intel TDX connect implementation also needs a reference to the kvm
>> pointer to obtain the secure EPT information. This is crucial because

---

## [68] Christian König — 2025-01-20
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

Am 17.01.25 um 15:42 schrieb Simona Vetter:
> On Wed, Jan 15, 2025 at 11:06:53AM +0100, Christian König wrote:
>> [SNIP]

That sounds like you missed my concern.

When an exporter and an importer agree that they want to exchange PFNs 
instead of DMA addresses then that is perfectly fine.

The problems start when you define the semantics how those PFNs, DMA 
address, private bus addresses, whatever is echanged different to what 
we have documented for DMA-buf.

This semantics is very well defined for DMA-buf now, because that is 
really important or otherwise things usually seem to work under testing 
(e.g. without memory pressure) and then totally fall apart in production 
environments.

In other words we have defined what lock you need to hold when calling 
functions, what a DMA fence is, when exchanged addresses are valid etc...

> But fundamentally there's never been an expectation that you can take any
> arbitrary dma-buf and pass it any arbitrary importer, and that is must

Please take another look at what is proposed here. The function is 
called dma_buf_get_pfn_*unlocked* !

This is not following DMA-buf semantics for exchanging addresses and 
keeping them valid, but rather something more like userptrs.

Inserting PFNs into CPU (or probably also IOMMU) page tables have a 
different semantics than what DMA-buf usually does, because as soon as 
the address is written into the page table it is made public. So you 
need some kind of mechanism to make sure that this addr you made public 
stays valid as long as it is public.

The usual I/O operation we encapsulate with DMA-fences have a 
fundamentally different semantics because we have the lock which 
enforces that stuff stays valid and then have a DMA-fence which notes 
how long the stuff needs to stay valid for an operation to complete.

Regards,
Christian.

>
> Cheers, Sima

---

## [69] Jason Gunthorpe — 2025-01-20

On Mon, Jun 24, 2024 at 03:59:53AM +0800, Xu Yilun wrote:
> > But it also seems to me that VFIO should be able to support putting
> > the device into the RUN state

VFIO is not just about running VMs. If someone wants to run DPDK on
VFIO they should be able to get the device into a RUN state and work
with secure memory without requiring a KVM. Yes there are many steps
to this, but we should imagine how it can work.

> > without involving KVM or cVMs.
> 

It must be. A CC guest with an in kernel driver can definately get the
PCI device into RUN, so VFIO running in the guest should be able as
well.

> I believe AMD would have one firmware call that requires cVM handle
> *AND* move device into LOCKED state. It really depends on firmware

IMHO, you would not use the secure firmware if you are not using VMs.

> Yes, the secure EPT is in the secure world and managed by TDX firmware.
> Now a SW Mirror Secure EPT is introduced in KVM and managed by KVM

If the secure world managed it then the secure world can have rules
that work with the IOMMU as well..

Jason

---

## [70] Jason Gunthorpe — 2025-01-20

On Mon, Jan 20, 2025 at 08:45:51PM +1100, Alexey Kardashevskiy wrote:

> > For CC I'm expecting the KVM fd to be the handle for the cVM, so any
> > RPCs that want to call into the secure world need the KVM FD to get

iommufd will keep the KVM fd alive so long as the vIOMMU object
exists. Other uses for kvm require it to work like this.

> > But it also seems to me that VFIO should be able to support putting
> > the device into the RUN state without involving KVM or cVMs.

As in my other email, VFIO is not restricted to running VMs, useful
things should be available to apps like DPDK.

There is a use case for using TDISP and getting devices up into an
ecrypted/attested state on pure bare metal without any KVM, VFIO
should work in that use case too.

Jason

---

## [71] Christian König — 2025-01-20
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

Am 21.06.24 um 00:02 schrieb Xu Yilun:
> On Thu, Jan 16, 2025 at 04:13:13PM +0100, Christian König wrote:
>>     Am 15.01.25 um 18:09 schrieb Jason Gunthorpe:

That doesn't work like this.

See page tables updates under DMA-buf works by using the same locking 
approach for both the validation and invalidation side. In other words 
we hold the same lock while inserting and removing entries into/from the 
page tables.

That this here should be an unlocked API means that can only use it with 
pre-allocated and hard pinned memory without any chance to invalidate it 
while running. Otherwise you can never be sure of the validity of the 
address information you got from the exporter.

> IIUC now the only concern is importer device drivers are easier to do
> something wrong, so move CPU mapping things to exporter. But most of the

Exporters always use their invalidation code path no matter if they are 
exporting their buffers for other to use or if they are stand alone.

If you do the invalidation on the importer side you always need both 
exporter and importer around to test it.

Additional to that we have much more importers than exporters. E.g. a 
lot of simple drivers only import DMA-heap buffers and never exports 
anything.

> And there are increasing mapping needs, today exporters help handle CPU primary
> mapping, tomorrow should they also help on all other mappings? Clearly it is

Why should that be necessary? Exporters *must* know what somebody does 
with their buffers.

If you have an use case the exporter doesn't support in their mapping 
operation then that use case most likely doesn't work in the first place.

For example direct I/O is enabled/disabled by exporters on their CPU 
mappings based on if that works correctly for them. And importer simply 
doesn't know if they should use vm_insert_pfn() or vm_insert_page().

We could of course implement that logic into each importer to chose 
between the different approaches, but than each importer gains logic it 
only exercises with a specific exporter. And that doesn't seem to be a 
good idea at all.

Regards,
Christian.

>
> Thanks,

---

## [72] Jason Gunthorpe — 2025-01-20
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Mon, Jan 20, 2025 at 01:14:12PM +0100, Christian König wrote:

What is going wrong with your email? You replied to Simona, but
Simona Vetter <simona.vetter@ffwll.ch> is dropped from the To/CC
list??? I added the address back, but seems like a weird thing to
happen.

> Please take another look at what is proposed here. The function is called
> dma_buf_get_pfn_*unlocked* !

I don't think Simona and I are defending the implementation in this
series. This series needs work.

We have been talking about what the implementation should be. I think
we've all been clear on the idea that the DMA buf locking rules should
apply to any description of the memory, regardless of if the address
are CPU, DMA, or private.

I agree that the idea of any "get unlocked" concept seems nonsensical
and wrong within dmabuf.

> Inserting PFNs into CPU (or probably also IOMMU) page tables have a
> different semantics than what DMA-buf usually does, because as soon as the

Not really.

The KVM/CPU is fully compatible with move semantics, it has
restartable page faults and can implement dmabuf's move locking
scheme. It can use the resv lock, the fences, move_notify and so on to
implement it. It is a bug if this series isn't doing that.

The iommu cannot support move semantics. It would need the existing
pin semantics (ie we call dma_buf_pin() and don't support
move_notify). To work with VFIO we would need to formalize the revoke
semantics that Simona was discussing.

We already implement both of these modalities in rdma, the locking API
is fine and workable with CPU pfns just as well.

I've imagined a staged flow here:

 1) The new DMA API lands
 2) We improve the new DMA API to be fully struct page free, including
    setting up P2P
 3) VFIO provides a dmbuf exporter using the new DMA API's P2P
    support. We'd have to continue with the scatterlist hacks for now.
    VFIO would be a move_notify exporter. This should work with RDMA
 4) RDMA works to drop scatterlist from its internal flows and use the
    new DMA API instead.
 5) VFIO/RDMA implement a new non-scatterlist DMABUF op to
    demonstrate the post-scatterlist world and deprecate the scatterlist
    hacks.
 6) We add revoke semantics to dmabuf, and VFIO/RDMA implements them
 7) iommufd can import a pinnable revokable dmabuf using CPU pfns
    through the non-scatterlist op.
 8) Relevant GPU drivers implement the non-scatterlist op and RDMA
    removes support for the deprecated scatterlist hacks.

Xu's series has jumped ahead a bit and is missing infrastructure to
build it properly.

Jason

---

## [73] Simona Vetter — 2025-01-20
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Mon, Jan 20, 2025 at 01:59:01PM -0400, Jason Gunthorpe wrote:
> On Mon, Jan 20, 2025 at 01:14:12PM +0100, Christian K�nig wrote:
> What is going wrong with your email? You replied to Simona, but

Might also be funny mailing list stuff, depending how you get these. I
read mails over lore and pretty much ignore cc (unless it's not also on
any list, since those tend to be security issues) because I get cc'ed on
way too much stuff for that to be a useful signal.

> > Please take another look at what is proposed here. The function is called
> > dma_buf_get_pfn_*unlocked* !

Yeah this current series is good for kicking off the discussions, it's
defo not close to anything we can merge.

> We have been talking about what the implementation should be. I think
> we've all been clear on the idea that the DMA buf locking rules should

Yeah I'm not worried about cpu mmap locking semantics. drm/ttm is a pretty
clear example that you can implement dma-buf mmap with the rules we have,
except the unmap_mapping_range might need a bit fudging with a separate
address_space.

For cpu mmaps I'm more worried about the arch bits in the pte, stuff like
caching mode or encrypted memory bits and things like that. There's
vma->vm_pgprot, but it's a mess. But maybe this all is an incentive to
clean up that mess a bit.

> The iommu cannot support move semantics. It would need the existing
> pin semantics (ie we call dma_buf_pin() and don't support

I thought iommuv2 (or whatever linux calls these) has full fault support
and could support current move semantics. But yeah for iommu without
fault support we need some kind of pin or a newly formalized revoke model.

> We already implement both of these modalities in rdma, the locking API
> is fine and workable with CPU pfns just as well.

Sounds pretty reasonable as a first sketch of a proper plan. Of course
fully expecting that no plan ever survives implementation intact :-)

Cheers, Sima

> 
> Xu's series has jumped ahead a bit and is missing infrastructure to

---

## [74] Jason Gunthorpe — 2025-01-20
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Mon, Jan 20, 2025 at 07:50:23PM +0100, Simona Vetter wrote:
> On Mon, Jan 20, 2025 at 01:59:01PM -0400, Jason Gunthorpe wrote:
> > On Mon, Jan 20, 2025 at 01:14:12PM +0100, Christian König wrote:

Oh I see, you are sending a Mail-followup-to header that excludes your
address, so you don't get any emails at all.. My mutt is dropping you
as well.

> Yeah I'm not worried about cpu mmap locking semantics. drm/ttm is a pretty
> clear example that you can implement dma-buf mmap with the rules we have,

From my perspective the mmap thing is a bit of a side/DRM-only thing
as nothing I'm interested in wants to mmap dmabuf into a VMA.

However, I think if you have locking rules that can fit into a VMA
fault path and link move_notify to unmap_mapping_range() then you've
got a pretty usuable API.

> For cpu mmaps I'm more worried about the arch bits in the pte, stuff like
> caching mode or encrypted memory bits and things like that. There's

I'm convinced we need meta-data along with pfns, there is too much
stuff that needs more information than just the address. Cachability,
CC encryption, exporting device, etc. This is a topic to partially
cross when we talk about how to fully remove struct page requirements
from the new DMA API.

I'm hoping we can get to something where we describe not just how the
pfns should be DMA mapped, but also can describe how they should be
CPU mapped. For instance that this PFN space is always mapped
uncachable, in CPU and in IOMMU.

We also have current bugs in the iommu/vfio side where we are fudging
CC stuff, like assuming CPU memory is encrypted (not always true) and
that MMIO is non-encrypted (not always true)

> I thought iommuv2 (or whatever linux calls these) has full fault support
> and could support current move semantics. But yeah for iommu without

No, this is HW dependent, including PCI device, and I'm aware of no HW
that fully implements this in a way that could be useful to implement
arbitary move semantics for VFIO..

Jason

---

## [75] Simona Vetter — 2025-01-21
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Mon, Jan 20, 2025 at 03:48:04PM -0400, Jason Gunthorpe wrote:
> On Mon, Jan 20, 2025 at 07:50:23PM +0100, Simona Vetter wrote:
> > On Mon, Jan 20, 2025 at 01:59:01PM -0400, Jason Gunthorpe wrote:

I guess we could just skip mmap on these pfn exporters, but it also means
a bit more boilerplate. At least the device mapping / dma_buf_attachment
side should be doable with just the pfn and the new dma-api?

> However, I think if you have locking rules that can fit into a VMA
> fault path and link move_notify to unmap_mapping_range() then you've

I was pondering whether dma_mmap and friends would be a good place to
prototype this and go for a fully generic implementation. But then even
those have _wc/_uncached variants.

If you go into arch specific stuff, then x86 does have wc/uc/... tracking,
but only for memory (set_page_wc and friends iirc). And you can bypass it
if you know what you're doing.

> We also have current bugs in the iommu/vfio side where we are fudging
> CC stuff, like assuming CPU memory is encrypted (not always true) and

tbf CC pte flags I just don't grok at all. I've once tried to understand
what current exporters and gpu drivers do and just gave up. But that's
also a bit why I'm worried here because it's an enigma to me.

> > I thought iommuv2 (or whatever linux calls these) has full fault support
> > and could support current move semantics. But yeah for iommu without

Hm I thought we've had at least prototypes floating around of device fault
repair, but I guess that only works with ATS/pasid stuff and not general
iommu traffic from devices. Definitely needs some device cooperation since
the timeouts of a full fault are almost endless.
-Sima

---

## [76] Jason Gunthorpe — 2025-01-21
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Tue, Jan 21, 2025 at 05:11:32PM +0100, Simona Vetter wrote:
> On Mon, Jan 20, 2025 at 03:48:04PM -0400, Jason Gunthorpe wrote:
> > On Mon, Jan 20, 2025 at 07:50:23PM +0100, Simona Vetter wrote:

I have been assuming that dmabuf mmap remains unchanged, that
exporters will continue to implement that mmap() callback as today.

My main interest has been what data structure is produced in the
attach APIs.

Eg today we have a struct dma_buf_attachment that returns a sg_table.

I'm expecting some kind of new data structure, lets call it "physical
list" that is some efficient coding of meta/addr/len tuples that works
well with the new DMA API. Matthew has been calling this thing phyr..

So, I imagine, struct dma_buf_attachment gaining an optional
feature negotiation and then we have in dma_buf_attachment:

        union {
              struct sg_table *sgt;
	      struct physical_list *phyr;
	};

That's basicaly it, an alternative to scatterlist that has a clean
architecture.

Now, if you are asking if the current dmabuf mmap callback can be
improved with the above? Maybe? phyr should have the neccessary
information inside it to populate a VMA - eventually even fully
correctly with all the right cachable/encrypted/forbidden/etc flags.

So, you could imagine that exporters could just have one routine to
generate the phyr list and that goes into the attachment, goes into
some common code to fill VMA PTEs, and some other common code that
will convert it into the DMABUF scatterlist. If performance is not a
concern with these data structure conversions it could be an appealing
simplification.

And yes, I could imagine the meta information being descriptive enough
to support the private interconnect cases, the common code could
detect private meta information and just cleanly fail.

> At least the device mapping / dma_buf_attachment
> side should be doable with just the pfn and the new dma-api?

Yes, that would be my first goal post. Figure out some meta
information and a container data structure that allows struct
page-less P2P mapping through the new DMA API.

> > I'm hoping we can get to something where we describe not just how the
> > pfns should be DMA mapped, but also can describe how they should be

Given that the inability to correctly DMA map P2P MMIO without struct
page is a current pain point and current source of hacks in dmabuf
exporters, I wanted to make resolving that a priority.

However, if you mean what I described above for "fully generic [dmabuf
mmap] implementation", then we'd have the phyr datastructure as a
dependency to attempt that work.

phyr, and particularly the meta information, has a number of
stakeholders. I was thinking of going first with rdma's memory
registration flow because we are now pretty close to being able to do
such a big change, and it can demonstrate most of the requirements.

But that doesn't mean mmap couldn't go concurrently on the same agreed
datastructure if people are interested.

> > We also have current bugs in the iommu/vfio side where we are fudging
> > CC stuff, like assuming CPU memory is encrypted (not always true) and

For CC, inside the secure world, is some information if each PFN
inside the VM is 'encrypted' or not. Any VM PTE (including the IOPTEs)
pointing at the PFN must match the secure world's view of
'encrypted'. The VM can ask the secure world to change its view at
runtime.

The way CC has been bolted on to the kernel so far laregly hides this
from drivers, so it is troubled to tell in driver code if the PFN you
have is 'encrypted' or not. Right now the general rule (that is not
always true) is that struct page CPU memory is encrypted and
everything else is decrypted.

So right now, you can mostly ignore it and the above assumption
largely happens for you transparently.

However, soon we will have encrypted P2P MMIO which will stress this
hiding strategy.

> > > I thought iommuv2 (or whatever linux calls these) has full fault support
> > > and could support current move semantics. But yeah for iommu without

Yes, exactly. What all real devices I'm aware have done is make a
subset of their traffic work with ATS and PRI, but not all their
traffic. Without *all* traffic you can't make any generic assumption
in the iommu that a transient non-present won't be fatal to the
device.

Stuff like dmabuf move semantics rely on transient non-present being
non-disruptive...

Jason

---

## [77] Jason Gunthorpe — 2025-01-21

On Tue, Jun 25, 2024 at 05:12:10AM +0800, Xu Yilun wrote:

> When VFIO works as a TEE user in VM, it means an attester (e.g. PCI
> subsystem) has already moved the device to RUN state. So VFIO & DPDK

No, unfortunately. Part of the motivation to have the devices be
unlocked when the VM starts is because there is an expectation that a
driver in the VM will need to do untrusted operations to boot up the
device before it can be switched to the run state.

So any vfio use case needs to imagine that VFIO starts with an
untrusted device, does stuff to it, then pushes everything through to
run. The exact mirror as what a kernel driver should be able to do.

How exactly all this very complex stuff works, I have no idea, but
this is what I've understood is the target. :\

Jason

---

## [78] Xu Yilun — 2025-01-22
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Mon, Jan 20, 2025 at 02:44:13PM +0100, Christian König wrote:
> Am 21.06.24 um 00:02 schrieb Xu Yilun:
> > On Thu, Jan 16, 2025 at 04:13:13PM +0100, Christian König wrote:

Not sure what's the issue it causes, maybe I don't get why "you can't
hold a lock while returning from a page fault".

> 
> That this here should be an unlocked API means that can only use it with

Then importers can use a locked version to get pfn, and manually use
dma_resv lock only to ensure the PFN validity during page table setup.
Importers could detect the PFN will be invalid via move notify and
remove page table entries. Then find the new PFN next time page fault
happens.

IIUC, Simona mentions drm/ttm is already doing it this way.

I'm not trying to change the CPU mmap things for existing drivers, just
to ensure importer mapping is possible with faultable MMU. I wanna KVM
MMU (also faultable) to work in this importer mapping way.

Thanks,
Yilun

---

## [79] Xu Yilun — 2025-01-22

On Tue, Jan 21, 2025 at 01:43:03PM -0400, Jason Gunthorpe wrote:
> On Tue, Jun 25, 2024 at 05:12:10AM +0800, Xu Yilun wrote:
> 

I assume these operations are device specific.

> device before it can be switched to the run state.
> 

I have concern that VFIO has to do device specific stuff. Our current
expectation is a specific device driver deals with the untrusted
operations, then user writes a 'bind' device sysfs node which detaches
the driver for untrusted, do the attestation and accept, and try match
the driver for trusted (e.g. VFIO).

Thanks,
Yilun

> run. The exact mirror as what a kernel driver should be able to do.
>

---

## [80] Simona Vetter — 2025-01-22
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Tue, Jan 21, 2025 at 01:36:33PM -0400, Jason Gunthorpe wrote:
> On Tue, Jan 21, 2025 at 05:11:32PM +0100, Simona Vetter wrote:
> > On Mon, Jan 20, 2025 at 03:48:04PM -0400, Jason Gunthorpe wrote:

I'm kinda leaning towards entirely separate dma-buf interfaces for the new
phyr stuff, because I fear that adding that to the existing ones will only
make the chaos worse. But that aside sounds all reasonable, and even that
could just be too much worry on my side and mixing phyr into existing
attachments (with a pile of importer/exporter flags probably) is fine.

For the existing dma-buf importers/exporters I'm kinda hoping for a pure
dma_addr_t based list eventually. Going all the way to a phyr based
approach for everyone might be too much churn, there's some real bad cruft
there. It's not going to work for every case, but it covers a lot of them
and might be less pain for existing importers.

But in theory it should be possible to use phyr everywhere eventually, as
long as there's no obviously api-rules-breaking way to go from a phyr back to
a struct page even when that exists.

> > At least the device mapping / dma_buf_attachment
> > side should be doable with just the pfn and the new dma-api?

Yeah cpu mmap needs a lot more, going with a very limited p2p use-case
first only makes sense.

> > > We also have current bugs in the iommu/vfio side where we are fudging
> > > CC stuff, like assuming CPU memory is encrypted (not always true) and

It's already breaking with stuff like virtual gpu drivers, vmwgfx is
fiddling around with these bits (at least last I tried to understand this
all) and I think a few others do too.

> > > > I thought iommuv2 (or whatever linux calls these) has full fault support
> > > > and could support current move semantics. But yeah for iommu without

Ah now I get it, at the iommu level you have to pessimistically assume
whether a device can handle a fault, and none can for all traffic. I was
thinking too much about the driver level where generally the dma-buf you
importer are only used for the subset of device functions that can cope
with faults on many devices.

Cheers, Sima

---

## [81] Jason Gunthorpe — 2025-01-22

On Wed, Jan 22, 2025 at 12:32:56PM +0800, Xu Yilun wrote:
> On Tue, Jan 21, 2025 at 01:43:03PM -0400, Jason Gunthorpe wrote:
> > On Tue, Jun 25, 2024 at 05:12:10AM +0800, Xu Yilun wrote:

Yes

> > device before it can be switched to the run state.
> > 

I don't see this as working, VFIO will FLR the device which will
destroy anything that was done prior.

VFIO itself has to do the sequence and the VFIO userspace has to
contain the device specific stuff.

The bind/unbind dance for untrusted->trusted would need to be
internalized in VFIO without unbinding. The main motivation for the
bind/unbind flow was to manage the DMA API, which VFIO does not use.

Jason

---

## [82] Jason Gunthorpe — 2025-01-22
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Wed, Jan 22, 2025 at 12:04:19PM +0100, Simona Vetter wrote:

> I'm kinda leaning towards entirely separate dma-buf interfaces for the new
> phyr stuff, because I fear that adding that to the existing ones will only

Lets see when some patches come up, if importers have to deal with
several formats a single attach interface would probably be simpler
for them..

> For the existing dma-buf importers/exporters I'm kinda hoping for a pure
> dma_addr_t based list eventually. 

IMHO the least churn would be to have the old importers call a helper
(perhaps implicitly in the core code) to convert phyr into a dma
mapped scatterlist and then just keep using their existing code
exactly as is.

Performance improvement would come from importers switching to use the
new dma api internally and avoiding the scatterlist allocation, but
even the extra alocation is not so bad.

Then, perhaps, and I really hesitate to say this, but perhaps to ease
the migration we could store a dma mapped list in a phyr using the
meta information. That would allow a dmabuf scatterlist exporter to be
converted to a phyr with a helper. The importer would have to have a
special path to detect the dma mapped mode and skip the normal
mapping.

The point would be to let maintained drivers use the new data
structures and flows easily and still interoperate with older
drivers. Otherwise we have to somehow build parallel scatterlist and
phyr code flows into importers :\

> Going all the way to a phyr based
> approach for everyone might be too much churn, there's some real bad cruft

I'd hope we can reach every case.. But I don't know what kind of
horrors you guys have :)

> But in theory it should be possible to use phyr everywhere eventually, as
> long as there's no obviously api-rules-breaking way to go from a phyr back to

I'd say getting a struct page is a perfectly safe operation, from a
phyr API perspective.

The dmabuf issue seems to be entirely about following the locking
rules, an importer is not allowed to get a struct page and switch from
reservation locking to page refcount locking.

I get the appeal for DRM of blocking struct page use because that
directly prevents the above. But, in RDMA I want to re-use the same
phyr datastructure for tracking pin_user_pages() CPU memory, and I
must get the struct page back so I can put_user_page() it when done.

Perhaps we can find some compromise where the phyr data structure has
some kind of flag 'disable struct page' and then the
phyr_entry_to_page() API will WARN_ON() or something like that.

> > However, soon we will have encrypted P2P MMIO which will stress this
> > hiding strategy.

IMHO, most places I've seen touching this out side arch code feel very
hacky. :\

Jason

---

## [83] Christian König — 2025-01-22
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

Am 22.01.25 um 12:04 schrieb Simona Vetter:
> On Tue, Jan 21, 2025 at 01:36:33PM -0400, Jason Gunthorpe wrote:
>> On Tue, Jan 21, 2025 at 05:11:32PM +0100, Simona Vetter wrote:

I'm having all kind of funny phenomena with AMDs mail servers since 
coming back from xmas vacation.

 From the news it looks like Outlook on Windows has a new major security 
issue where just viewing a mail can compromise the system and my 
educated guess is that our IT guys went into panic mode because of this 
and has changed something.

>> [SNIP]
>> I have been assuming that dmabuf mmap remains unchanged, that

That sounds really really good to me because that was my major concern 
when you noted that you want to have PFNs to build up KVM page tables.

But you don't want to handle mmap() on your own, you basically don't 
want to have a VMA for this stuff at all, correct?

>> My main interest has been what data structure is produced in the
>> attach APIs.

I would not use a data structure at all. Instead we should have 
something like an iterator/cursor based approach similar to what the new 
DMA API is doing.

>> So, I imagine, struct dma_buf_attachment gaining an optional
>> feature negotiation and then we have in dma_buf_attachment:

I would rather suggest something like dma_buf_attachment() gets offset 
and size to map and returns a cursor object you can use to get your 
address, length and access attributes.

And then you can iterate over this cursor and fill in your importer data 
structure with the necessary information.

This way neither the exporter nor the importer need to convert their 
data back and forth between their specific representations of the 
information.

>> Now, if you are asking if the current dmabuf mmap callback can be
>> improved with the above? Maybe? phyr should have the neccessary

That won't work like this.

See the exporter needs to be informed about page faults on the VMA to 
eventually wait for operations to end and sync caches.

Otherwise we either potentially allow access to freed up or re-used 
memory or run into issues with device cache coherency.

>> So, you could imagine that exporters could just have one routine to
>> generate the phyr list and that goes into the attachment, goes into

I lean into the other direction.

Dmitry and Thomas have done a really good job at cleaning up all the 
interaction between dynamic and static exporters / importers.

Especially that we now have consistent locking for map_dma_buf() and 
unmap_dma_buf() should make that transition rather straight forward.

> For the existing dma-buf importers/exporters I'm kinda hoping for a pure
> dma_addr_t based list eventually. Going all the way to a phyr based

The point is we have use cases that won't work without exchanging DMA 
addresses any more.

For example we have cases with multiple devices are in the same IOMMU 
domain and re-using their DMA address mappings.

> But in theory it should be possible to use phyr everywhere eventually, as
> long as there's no obviously api-rules-breaking way to go from a phyr back to

I would rather say we should stick to DMA addresses as much as possible.

What we can do is to add an address space description to the addresses, 
e.g. if it's a PCIe BUS addr in IOMMU domain X, or of it's a device 
private bus addr or in the case of sharing with iommufd and KVM PFNs.

Regards,
Christian.

>>> At least the device mapping / dma_buf_attachment
>>> side should be doable with just the pfn and the new dma-api?

---

## [84] Jason Gunthorpe — 2025-01-22
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Wed, Jan 22, 2025 at 02:29:09PM +0100, Christian König wrote:

> I'm having all kind of funny phenomena with AMDs mail servers since coming
> back from xmas vacation.

:(

A few years back our IT fully migrated our email to into Office 365
cloud and gave up all the crazy half on-prem stuff they were
doing. The mail started working fully perfectly after that, as long as
you use MS's servers directly :\

> But you don't want to handle mmap() on your own, you basically don't want to
> have a VMA for this stuff at all, correct?

Right, we have no interest in mmap, VMAs or struct page in
rdma/kvm/iommu.
 
> > > My main interest has been what data structure is produced in the
> > > attach APIs.

I'm certainly open to this idea. There may be some technical
challenges, it is a big change from scatterlist today, and
function-pointer-per-page sounds like bad performance if there are
alot of pages..

RDMA would probably have to stuff this immediately into something like
a phyr anyhow because it needs to fully extent the thing being mapped
to figure out what the HW page size and geometry should be - that
would be trivial though, and a RDMA problem.

> > > Now, if you are asking if the current dmabuf mmap callback can be
> > > improved with the above? Maybe? phyr should have the neccessary

Note I said "populate a VMA", ie a helper to build the VMA PTEs only.

> See the exporter needs to be informed about page faults on the VMA to
> eventually wait for operations to end and sync caches.

All of this would still have to be provided outside in the same way as
today.

> For example we have cases with multiple devices are in the same IOMMU domain
> and re-using their DMA address mappings.

IMHO this is just another flavour of "private" address flow between
two cooperating drivers.

It is not a "dma address" in the sense of a dma_addr_t that was output
from the DMA API. I think that subtle distinction is very
important. When I say pfn/dma address I'm really only talking about
standard DMA API flows, used by generic drivers.

IMHO, DMABUF needs a private address "escape hatch", and cooperating
drivers should do whatever they want when using that flow. The address
is *fully private*, so the co-operating drivers can do whatever they
want. iommu_map in exporter and pass an IOVA? Fine! pass a PFN and
iommu_map in the importer? Also fine! Private is private.

> > But in theory it should be possible to use phyr everywhere eventually, as
> > long as there's no obviously api-rules-breaking way to go from a phyr back to

I remain skeptical of this.. Aside from all the technical reasons I
already outlined..

I think it is too much work to have the exporters conditionally build
all sorts of different representations of the same thing depending on
the importer. Like having alot of DRM drivers generate both a PFN and
DMA mapped list in their export code doesn't sound very appealing to
me at all.

It makes sense that a driver would be able to conditionally generate
private and generic based on negotiation, but IMHO, not more than one
flavour of generic..

Jason

---

## [85] Christian König — 2025-01-22
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

Am 22.01.25 um 15:37 schrieb Jason Gunthorpe:
>>>> My main interest has been what data structure is produced in the
>>>> attach APIs.

Well that's the point. The inporter is not cooperating here.

The importer doesn't have the slightest idea that he is sharing it's DMA 
addresses with the exporter.

All the importer gets is when you want to access this information use 
this address here.

> It is not a "dma address" in the sense of a dma_addr_t that was output
> from the DMA API. I think that subtle distinction is very

Well from experience I can say that it is actually the other way around.

We have a very limited number of exporters and a lot of different 
importers. So having complexity in the exporter instead of the importer 
is absolutely beneficial.

PFN is the special case, in other words this is the private address 
passed around. And I will push hard to not support that in the DRM 
drivers nor any DMA buf heap.

> It makes sense that a driver would be able to conditionally generate
> private and generic based on negotiation, but IMHO, not more than one

I still strongly think that the exporter should talk with the DMA API to 
setup the access path for the importer and *not* the importer directly.

Regards,
Christian.

>
> Jason

---

## [86] Xu Yilun — 2025-01-23

On Wed, Jan 22, 2025 at 08:55:12AM -0400, Jason Gunthorpe wrote:
> On Wed, Jan 22, 2025 at 12:32:56PM +0800, Xu Yilun wrote:
> > On Tue, Jan 21, 2025 at 01:43:03PM -0400, Jason Gunthorpe wrote:

I don't have a complete idea yet. But the goal is not to make any
existing driver seamlessly work with secure device. It is to provide a
generic way for bind/attestation/accept, and may save driver's effort
if they don't care about this startup process. There are plenty of
operations that a driver can't do to a secure device, FLR is one of
them. The TDISP SPEC has described some general rules but some are even
device specific.

So I think a driver (including VFIO) expects change to support trusted
device, but may not have to cover bind/attestation/accept flow.

Thanks,
Yilun

> 
> The bind/unbind dance for untrusted->trusted would need to be

---

## [87] Jason Gunthorpe — 2025-01-23

On Thu, Jan 23, 2025 at 03:41:58PM +0800, Xu Yilun wrote:

> I don't have a complete idea yet. But the goal is not to make any
> existing driver seamlessly work with secure device. It is to provide a

You can FLR a secure device, it just has to be re-secured and
re-attested after. Otherwise no VFIO for you.

> So I think a driver (including VFIO) expects change to support trusted
> device, but may not have to cover bind/attestation/accept flow.

I expect changes, but not fundamental ones. VFIO will still have to
FLR devices as part of it's security architecture.

The entire flow needs to have options for drivers to be involved in
the flow, somehow.

Jason

---

## [88] Jason Gunthorpe — 2025-01-23
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Wed, Jan 22, 2025 at 03:59:11PM +0100, Christian König wrote:
> > > For example we have cases with multiple devices are in the same IOMMU domain
> > > and re-using their DMA address mappings.

If the private address relies on a shared iommu_domain controlled by
the driver, then yes, the importer MUST be cooperating. For instance,
if you send the same private address into RDMA it will explode because
it doesn't have any notion of shared iommu_domain mappings, and it
certainly doesn't setup any such shared domains.

> The importer doesn't have the slightest idea that he is sharing it's DMA
> addresses with the exporter.

Of course it does. The importer driver would have had to explicitly
set this up! The normal kernel behavior is that all drivers get
private iommu_domains controled by the DMA API. If your driver is
doing something else *it did it deliberately*.

Some of that mess in tegra host1x around this area is not well
structured, it should not be implicitly setting up domains for
drivers. It is old code that hasn't been updated to use the new iommu
subsystem approach for driver controled non-DMA API domains.

The new iommu architecture has the probing driver disable the DMA API
and can then manipulate its iommu domain however it likes, safely. Ie
the probing driver is aware and particiapting in disabling the DMA
API.

Again, either you are using the DMA API and you work in generic ways
with generic devices or it is "private" and only co-operating drivers
can interwork with private addresses. A private address must not ever
be sent to a DMA API using driver and vice versa.

IMHO this is an important architecture point and why Christoph was
frowning on abusing dma_addr_t to represent things that did NOT come
out of the DMA API.

> We have a very limited number of exporters and a lot of different importers.
> So having complexity in the exporter instead of the importer is absolutely

Isn't every DRM driver both an importer and exporter? That is what I
was expecting at least..

> I still strongly think that the exporter should talk with the DMA API to
> setup the access path for the importer and *not* the importer directly.

It is contrary to the design of the new API which wants to co-optimize
mapping and HW setup together as one unit.

For instance in RDMA we want to hint and control the way the IOMMU
mapping works in the DMA API to optimize the RDMA HW side. I can't do
those optimizations if I'm not in control of the mapping.

The same is probably true on the GPU side too, you want IOVAs that
have tidy alignment with your PTE structure, but only the importer
understands its own HW to make the correct hints to the DMA API.

Jason

---

## [89] Christian König — 2025-01-23
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

Sending it as text mail once more.

Am 23.01.25 um 15:32 schrieb Christian König:
> Am 23.01.25 um 14:59 schrieb Jason Gunthorpe:
>> On Wed, Jan 22, 2025 at 03:59:11PM +0100, Christian König wrote:

---

## [90] Jason Gunthorpe — 2025-01-23
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Thu, Jan 23, 2025 at 03:35:21PM +0100, Christian König wrote:
> Sending it as text mail once more.
> 

I don't know, you are the one saying the drivers have special shared
iommu_domains so DMA BUF need some special design to accommodate it.

I'm aware that DRM drivers do directly call into the iommu subsystem
and do directly manage their own IOVA. I assumed this is what you were
talkinga bout. See below.

> > The domain is owned and assigned by the PCI subsystem under Linux.

That domain is *exclusively* owned by the DMA API and is only accessed
via maps created by DMA API calls.

If you are using the DMA API correctly then all of this is abstracted
and none of it matters to you. There is no concept of "shared domains"
in the DMA API. 

You call the DMA API, you get a dma_addr_t that is valid for a
*single* device, you program it in HW. That is all. There is no reason
to dig deeper than this.
 
> > > > The importer doesn't have the slightest idea that he is sharing it's DMA
> > > > addresses with the exporter.

No, the opposite. The iommu subsystem tries to maximally isolate
devices up to the HW limit.

On server platforms every device is expected to get its own iommu domain.

> > Especially multi function devices get only a single IOMMU domain.

Only if the PCI HW doesn't support ACS.

This is all DMA API internal details you shouldn't even be talking
about at the DMA BUF level. It is all hidden and simply does not
matter to DMA BUF at all.

> > > The new iommu architecture has the probing driver disable the DMA API
> > > and can then manipulate its iommu domain however it likes, safely. Ie

I am talking about DRM drivers that HAVE to manage their own for some
reason I don't know. eg:

drivers/gpu/drm/nouveau/nvkm/engine/device/tegra.c:             tdev->iommu.domain = iommu_domain_alloc(&platform_bus_type);
drivers/gpu/drm/msm/msm_iommu.c:        domain = iommu_paging_domain_alloc(dev);
drivers/gpu/drm/rockchip/rockchip_drm_drv.c:    private->domain = iommu_paging_domain_alloc(private->iommu_dev);
drivers/gpu/drm/tegra/drm.c:            tegra->domain = iommu_paging_domain_alloc(dma_dev);
drivers/gpu/host1x/dev.c:               host->domain = iommu_paging_domain_alloc(host->dev);

Normal simple drivers should never be calling these functions!

If you are calling these functions you are not using the DMA API, and,
yes, some cases like tegra n1x are actively sharing these special
domains across multiple devices and drivers.

If you want to pass an IOVA in one of these special driver-created
domains then it would be some private address in DMABUF that only
works on drivers that have understood they attached to these manually
created domains. No DMA API involvement here.

> > > > I still strongly think that the exporter should talk with the DMA API to
> > > > setup the access path for the importer and *not* the importer directly.

Actually it is storage that motivates this. It is just pointless to
allocate a dma_addr_t list in the fast path when you don't need
it. You can stream the dma_addr_t directly into HW structures that are
necessary and already allocated.

> > > For instance in RDMA we want to hint and control the way the IOMMU
> > > mapping works in the DMA API to optimize the RDMA HW side. I can't do

dma-iommu.c chooses an IOVA alignment based on its own reasoning that
is not always compatible with the HW. The HW can optimize if the IOVA
alignment meets certain restrictions. Much like page tables in a GPU.

> > > The same is probably true on the GPU side too, you want IOVAs that
> > > have tidy alignment with your PTE structure, but only the importer

It wouild be in the DMA API, just the per-mapping portion of the API.

Same as the multipath, the ATS, and more. It is all per-mapping
descisions of the executing HW, not global decisions or something
like.

Jason

---

## [91] Jason Gunthorpe — 2025-01-23
*Subject: Re: [RFC PATCH 01/12] dma-buf: Introduce dma_buf_get_pfn_unlocked()
 kAPI*

On Thu, Jan 23, 2025 at 04:48:29PM +0100, Christian König wrote:
>    No, no there are much more cases where drivers simply assume that they
>    are in the same iommu domain for different devices. 

This is an illegal assumption and invalid way to use the DMA API. Do
not do that, do not architect things in DMABUF to permit that.

The dma_addr_t out of the DMA API is only usable by the device passed
in, period full stop. If you want to use it with two devices then call
the DMA API twice.

>    E.g. that different
>    PCI endpoints can use the same dma_addr_t.

>    For example those classic sound devices for HDMI audio on graphics
>    cards work like this. 

Yes, I recall this weird AMD issue as well. IIRC the solution is not
clean or "correct". :( I vaugely recall it was caused by a HW bug...

>    Well it might never been documented but I know of quite a bunch of
>    different cases that assume that a DMA addr will just ultimately work

Again, illegal assumption, breaks the abstraction.

>> This is all DMA API internal details you shouldn't even be talking
>> about at the DMA BUF level. It is all hidden and simply does not

Call the DMA API multiple times, once per device. That is the only
correct way to handle this today. DMABUF is already architected like
this, each and every attach should be dma mapping and generating a
scatterlist for every unique importing device.

Improving it to somehow avoid the redundant DMA API map would require
new DMA API work.

Do NOT randomly assume that devices share dma_addr_t, there is no
architected way to ever discover this, it is a complete violation of
all the API abstractions.

>> If you want to pass an IOVA in one of these special driver-created
>> domains then it would be some private address in DMABUF that only

Your AMD ALSA weirdness is not using custom iommu_domains (nor should
it), it is a different problem.

> dma-iommu.c chooses an IOVA alignment based on its own reasoning that
> is not always compatible with the HW. The HW can optimize if the IOVA

How do you propose to do this per-mapping operation without having the
HW driver actually call the mapping operation?

> > Same as the multipath, the ATS, and more. It is all per-mapping
> > descisions of the executing HW, not global decisions or something

Not fully yet (though some multipath is supported), but I want to
slowly move in this direction to solve all of these problems we
have :(

Jason

---

## [92] Dan Williams — 2025-03-11

[ My ears have been burning for a couple months regarding this thread
  and I have finally had the chance to circle back and read through all
  the discussion on PATCH 01/12 and this PATCH 08/12, pardon the latency
  while I addressed some CXL backlog ]

Jason Gunthorpe wrote:
> On Mon, Jan 20, 2025 at 08:45:51PM +1100, Alexey Kardashevskiy wrote:
> 

Are you sure you are not confusing the use case for native PCI CMA plus
PCIe IDE *without* PCIe TDISP? In other words validate device
measurements over a secure session and set up link encryption, but not
enable DMA to private memory. Without a cVM there is no private memory
for the device to talk to in the TDISP run state, but you can certainly
encrypt the PCIe link.

However that pretty much only gets you an extension of a secure session
to a PCIe link state. It does not enable end-to-end MMIO and DMA
integrity+confidentiality.

Note that to my knowledge all but the Intel TEE I/O implementation
disallow routing T=0 traffic over IDE. The host bridge only accepts T=1
traffic over IDE to private memory which is not this "without any KVM"
use case.

The uapi proposed in the PCI/TSM series [1] is all about the setup of PCI
CMA + PCIe IDE without KVM as a precuror to all the VFIO + KVM + IOMMUFD
work needed to get the TDI able to publish private MMIO and DMA to
private memory.

[1]: http://lore.kernel.org/174107245357.1288555.10863541957822891561.stgit@dwillia2-xfh.jf.intel.com

---

## [93] Jason Gunthorpe — 2025-03-17

On Tue, Mar 11, 2025 at 06:37:13PM -0700, Dan Williams wrote:

> > There is a use case for using TDISP and getting devices up into an
> > ecrypted/attested state on pure bare metal without any KVM, VFIO

Oh maybe, who knows with all this complexity :\

I see there is a crossover point, once you start getting T=1 traffic
then you need a KVM handle to process it, yes, but everything prior to
T=0, including all the use cases with T=0 IDE, attestation and so on,
still need to be working.

> In other words validate device measurements over a secure session
> and set up link encryption, but not enable DMA to private

Right. But can you do that all without touching tdisp?

> However that pretty much only gets you an extension of a secure session
> to a PCIe link state. It does not enable end-to-end MMIO and DMA

But that is the point, right? You want to bind your IDE encryption to
the device attestation and get all of those things. I thought you
needed some TDISP for that?
 
> Note that to my knowledge all but the Intel TEE I/O implementation
> disallow routing T=0 traffic over IDE.

I'm not sure that will hold up long term, I hear alot of people
talking about using IDE to solve all kinds of PCI problems that have
nothing to do with CC.

> The uapi proposed in the PCI/TSM series [1] is all about the setup of PCI
> CMA + PCIe IDE without KVM as a precuror to all the VFIO + KVM + IOMMUFD

That seems reasonable

Jason

---

## [94] Alexey Kardashevskiy — 2025-04-29
*Subject: Re: [RFC PATCH 00/12] Private MMIO support for private assigned dev*

On 8/1/25 01:27, Xu Yilun wrote:
> This series is based on an earlier kvm-coco-queue version (v6.12-rc2)

Has this been pushed somewhere public? The patchset does not apply on top of v6.12-rc2, for example (I fixed locally).
Also, is there somewhere a QEMU tree using this? I am trying to use this new DMA_BUF feature and this require quite some not so obvious plumbing. Thanks,


> which includes all basic TDX patches.
>

---

## [95] Alexey Kardashevskiy — 2025-04-29
*Subject: Re: [RFC PATCH 00/12] Private MMIO support for private assigned dev*

On 29/4/25 16:48, Alexey Kardashevskiy wrote:
> On 8/1/25 01:27, Xu Yilun wrote:
>> This series is based on an earlier kvm-coco-queue version (v6.12-rc2)


More to the point, to make it work, QEMU needs to register VFIO MMIO BAR with KVM_SET_USER_MEMORY_REGION2 which passes slot->guest_memfd to KVM which essentially comes from VFIORegion->mmaps[0].mem->ram_block->guest_memfd. But since you disabled mmap for private MMIO, there is no MR which QEMU would even try registering as KVM memslot and there are many ways to fix it. I took a shortcut and reenabled mmap() but wonder what exactly you did. Makes sense? Thanks,


> 
>> which includes all basic TDX patches.

---
