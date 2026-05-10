---
title: '[RFC PATCH v2 07/22] coco/tsm: Add tsm and tsm-host modules'
date: 2025-05-14
last_reply: 2025-05-29
message_count: 4
participants: ['Zhi Wang', 'Alexey Kardashevskiy']
---

## [1] Zhi Wang — 2025-05-14

On Tue, 18 Feb 2025 22:09:54 +1100
Alexey Kardashevskiy <aik@amd.com> wrote:

> The TSM module is a library to create sysfs nodes common for
> hypervisors and VMs. It also provides helpers to parse interface

I would suggest that we have separate header files for spec
definitions. E.g. tdisp_defs and spdm_defs.h. from the maintainability
perspective.

> +/*
> + * Measurement block as defined in SPDM DSP0274.

....

> +struct tsm_hv_ops {
> +	int (*dev_connect)(struct tsm_dev *tdev, void *private_data);

1) Looks we have two more callbacks besides TDI verbs, I think they are
fine to be in TSM driver ops.

For guest_request(), anyway, we need an entry point for QEMU to
reach the TSM services in the kernel. Looks like almost all the platform
(Intel/AMD/ARM) have TVM-HOST paths, which will exit to QEMU from KVM,
and QEMU reaches the TSM services and return to the TVM. I think they
can all leverage the entry point (IOMMUFD) via the guest request ioctl.
And IOMMUFD almost have all the stuff QEMU needs.

Or we would end up with QEMU reaches to different entry points in
per-vendor code path, which was not preferable, backing to the
period when enabling CC in QEMU.

2) Also, it is better that we have separate the tsm_guest and tsm_host
headers since the beginning. 

3) How do you trigger the TDI_BIND from the guest in the late-bind
model? Was looking at tsm_vm_ops, but seems not found yet.

> +struct tsm_subsys {
> +	struct device dev;

Can this replace a lock? refcount is to track the life cycle,
lock is to avoid racing. Think that we just pass here tdev->bound
== 0, take the spdm_mutex and request the TSM to talk to the device
for disconnection, while someone is calling tdi_bind and pass the
tdev->connected check and waiting for the spdm_mutex to do the
tdi_bind. The device might see a TDI_BIND after a DEVICE_DISCONNECT.

Z.
> +	mutex_lock(&tdev->spdm_mutex);
> +	while (1) {

> +
> +void tsm_dev_free(struct tsm_dev *tdev)

---

## [2] Zhi Wang — 2025-05-15
*Subject: Re: [RFC PATCH v2 15/22] KVM: X86: Handle private MMIO as shared*

On Tue, 18 Feb 2025 22:10:02 +1100
Alexey Kardashevskiy <aik@amd.com> wrote:

> Currently private MMIO nested page faults are not expected so when
> such fault occurs, KVM tries moving the faulted page from private to

Let's fold this in a macro and make this more informative with comments.

>  	foll |= FOLL_NOWAIT;

---

## [3] Alexey Kardashevskiy — 2025-05-29
*Subject: Re: [RFC PATCH v2 15/22] KVM: X86: Handle private MMIO as shared*

On 15/5/25 18:18, Zhi Wang wrote:
> On Tue, 18 Feb 2025 22:10:02 +1100
> Alexey Kardashevskiy <aik@amd.com> wrote:

Rather than this, https://lore.kernel.org/r/20250107142719.179636-1-yilun.xu@linux.intel.com  seems to be the way to go. Thanks,


> 
>>   	foll |= FOLL_NOWAIT;

---

## [4] Alexey Kardashevskiy — 2025-05-29

On 15/5/25 04:39, Zhi Wang wrote:
> On Tue, 18 Feb 2025 22:09:54 +1100
> Alexey Kardashevskiy <aik@amd.com> wrote:

True as this shares bits and pieces with Lukas'es CMA.

>> +/*
>> + * Measurement block as defined in SPDM DSP0274.

+1.

> 3) How do you trigger the TDI_BIND from the guest in the late-bind
> model? Was looking at tsm_vm_ops, but seems not found yet.

It is implicit - to trigger TDI_BIND, the SNP VM needs to request TDI info (via GHCB) which exits to QEMU and QEMU then binds the TDI (if not bound already). This is made so in assumption that the VM is not just curious "what devices can be possibly trused" (the VM knows it from the PCIe capability) so it works.

How exactly the VM is going to trigger is a big questions, right now I have a hack to do that when the guest driver enables bus master and the TSM module(s) need to be loaded first. (we discussed elsewhere, just keeping it here for a record).



>> +struct tsm_subsys {
>> +	struct device dev;

You're right, requires fixing. Thanks,


> 
> Z.

---
