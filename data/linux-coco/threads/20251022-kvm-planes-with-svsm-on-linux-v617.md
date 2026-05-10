---
title: 'KVM Planes with SVSM on Linux v6.17'
date: 2025-10-22
last_reply: 2025-10-23
message_count: 3
participants: ['Jörg Rödel', 'Christoph Hellwig', 'Paolo Bonzini']
---

## [1] Jörg Rödel — 2025-10-22

Hi all,

This morning I pushed out my current Linux and QEMU branches which support
running COCONUT-SVSM on AMD SEV-SNP based on kernel v6.17 and the original KVM
Planes patch-set from Paolo.

The branches are here:

	Linux: https://github.com/coconut-svsm/linux/tree/svsm-planes-v6.17

	QEMU: https://github.com/coconut-svsm/qemu/tree/svsm-planes-v6.17

I know I promised that to be at this point by end of September, but things
didn't quite work out that way. Apologies for that.

The intent here is to show the current state of the work and let everyone try
it and provide feedback, although some fundamental changes still need to
happen (more on that below).

I also decided against sending out patch-sets, as it does not make much sense
to foster review of code that is known to fundamentally change still. If people
see value in seeing the patches on mailing lists, please let me know.

How to run it
-------------

The code can be built as usual, QEMU needs to have IGVM and KVM support
included in order to run COCONUT-SVSM.

The most important change is at the QEMU command line. With the branch above,
the skeleton is:

qemu-system-x86_64 \
   -enable-kvm \
   -cpu EPYC-v4 \
   -machine q35,confidential-guest-support=sev0,memory-backend=ram1,igvm-cfg=igvm0,kernel-irqchip=split,device-plane=2 \
   -object memory-backend-memfd,id=ram1,size=32G,share=true \
   -object sev-snp-guest,id=sev0,cbitpos=51,reduced-phys-bits=1 \
   -object igvm-cfg,id=igvm0,file=coconut-qemu.igvm \

Please note the changes to the machine specification:

	- `kernel-irqchip=split` The code I pushed out only works with IRQ chip
	  in split mode.

	- `device-plane=2` A new property defines the plane which controls
	  devices. This is important so that QEMU can send IRQs to the correct
	  plane. As COCONUT-SVSM currently always runs the guest on plane 2,
	  the value of the property must also be 2.

Known Issues
------------

During development of the KVM changes it became pretty to me that having one
`struct kvm_vcpu` object per plane causes several problems. The problems all
boil down to the fact that this approach introduces false unsharing of state
which needs to be per-VCPU instead of per-Plane. I worked around these problems
where needed to get things running, it can be seen in several patches in the
Linux branch.

But my changes do by far not cover all state which needs to be shared but is
now factually unshared between planes. The result is that people will likely
run into issues with the code above once leaving the beaten track I tested.

The changes on the `struct kvm` object are correct, there is still one for all
planes with a separate per-plane structure that holds the per-plane state.

Next Steps
----------

To turn this into a stable and upstreamable feature the first next step is to
update the base patches to use only one `struct kvm_vcpu` object for all planes
and factor out per-plane state into a separate struct. Then the SEV-SNP
specific changes will be rebased on-top.

Happy testing!

Regards,

	Joerg

---

## [2] Christoph Hellwig — 2025-10-23
*Subject: Re: KVM Planes with SVSM on Linux v6.17*

On Wed, Oct 22, 2025 at 10:35:28AM +0200, J�rg R�del wrote:
> Hi all,
> 

Can you explain what this alphabet-soup even means?

---

## [3] Paolo Bonzini — 2025-10-23
*Subject: Re: KVM Planes with SVSM on Linux v6.17*

On 10/23/25 17:08, Christoph Hellwig wrote:
> On Wed, Oct 22, 2025 at 10:35:28AM +0200, Jörg Rödel wrote:
>> Hi all,

With pleasure :)

- SEV-SNP: virtualization feature to encrypt VM memory (SEV) and also 
protect from attacks from the hypervisor (SNP), by matching the 
hypervisor's page tables against a reverse page mapping (from host 
physical to guest physical address) maintained by processor firmware in 
collaboration with the guest

- VMPL (bonus): SNP feature to create privilege levels within a single 
VM, for example to manage persistent secrets.  The firmware at VMPL0 can 
hold secrets that even the guest OS at VMPL1+ cannot access.

- KVM planes: KVM feature to  create privilege levels within a single 
VM, including VMPLs

- SVSM (Secure VM Service Module): privileged firmware running at VMPL0

- COCONUT-SVSM: one implementation of SVSM

Paolo

---
