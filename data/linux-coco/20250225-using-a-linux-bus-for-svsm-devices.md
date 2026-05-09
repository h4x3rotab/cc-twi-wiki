---
title: 'Using a linux bus for SVSM devices'
date: 2025-02-25
last_reply: 2025-02-26
message_count: 4
participants: ['James Bottomley', 'Stefano Garzarella']
---

## [1] James Bottomley — 2025-02-25

It looks like I'm not going to make the next SVSM meeting, so here is a
brain dump on how the linux bus type for virtio works.  Basically it's
a capsule for matching (and automatically finding driver modules) for
discovered devices.

The way we should use it is pretty much the same as virtio (see
drivers/virtio/virtio.c for the bus definitions).  There's also a nice
series of blog posts which documents this:

https://www.redhat.com/en/blog/virtio-devices-and-drivers-overview-headjack-and-phone
https://www.redhat.com/en/blog/virtqueues-and-virtio-ring-how-data-travels

The only real difference is the configuration signalling, which is done
over a pluggable configuration interface (which is either mmio, vdpa or
pci).  The SVSM only signals over the architectural mailbox API as
defined by the SVSM API Spec, so we don't need to bother with the
config_ops and can use a simple static C based API instead.

So I would say we copy virtio bus type, pretty much, with the standard
groups, match/probe/remove and uevent for driver binding and put it
under the drivers/virt/coco (or we could go with a new
drivers/virt/svsm).  Next we simply need a defined API for calling into
the SVSM (so something like the AMD abstraction which hides the calling
convention) which we define in a header instead of using config_ops. 
The body of the API would vary between architectures, so the
implementation would likely be in architecture specific code.

The only other question is what we do about device IDs.  I'm strongly
tempted simply to use strings, but all the other code does use fixed
length ids, so we could probably follow virtio_device_id except have a
single u32 for device_id (I've no idea what virtio uses vendor_id for
since every driver I've looked at leaves it as a wildcard).

The final thing would be to think about interrupts, but since the TPM
driver is strictly request/response, we can defer that until we know if
the observability driver will need them or not.

Regards,

James

---

## [2] Stefano Garzarella — 2025-02-26
*Subject: Re: [svsm-devel] Using a linux bus for SVSM devices*

Hi James,

On Tue, 25 Feb 2025 at 20:27, James Bottomley <James.Bottomley@hansenpartnership.com> wrote:
>
> It looks like I'm not going to make the next SVSM meeting, so here is a

Yes, I also never saw the vendor_id populated with anything other than 
VIRTIO_DEV_ANY_ID.

>
> The final thing would be to think about interrupts, but since the TPM

Thanks for this report!

IIUC the SVSM vTPM driver will be the first one using the new bus.
Since I have the new version almost ready (need to finish writing better 
commit descriptions), do you think I should post it in any case as RFC, 
or better to wait to include also the SVSM bus?

The current version is here [1] but it still uses platform devices, even 
though I removed one as requested during the review of the previous 
version.

If no one is working on the new SVSM bus or planning to (don't want to 
step on anyone's toes), I can try adding something to that branch and 
send an RFC here.

Thanks,
Stefano

[1] https://github.com/stefano-garzarella/linux/commits/vtpm-svsm-upstream/

---

## [3] James Bottomley — 2025-02-26
*Subject: Re: [svsm-devel] Using a linux bus for SVSM devices*

On Wed, 2025-02-26 at 15:04 +0100, Stefano Garzarella wrote:
[...]
> IIUC the SVSM vTPM driver will be the first one using the new bus.
> Since I have the new version almost ready (need to finish writing

So on this, yes, it's always wise to post early and often, particularly
where there's a discussion about where the code is going.  Seeing
updated code helps people frame arguments.

Just on the platform device: Greg seems to be going on an anti-platform
device bender at the moment

https://lore.kernel.org/linux-usb/2025021023-sandstorm-precise-9f5d@gregkh/

So you may need to humour him and use his faux bus instead.

> If no one is working on the new SVSM bus or planning to (don't want
> to step on anyone's toes), I can try adding something to that branch

I was going to do an RFC in my copious free time, but I've no objection
at all to someone else doing it...

Regards,

James

---

## [4] Stefano Garzarella — 2025-02-26
*Subject: Re: [svsm-devel] Using a linux bus for SVSM devices*

On Wed, 26 Feb 2025 at 15:34, James Bottomley <James.Bottomley@hansenpartnership.com> wrote:
>
> On Wed, 2025-02-26 at 15:04 +0100, Stefano Garzarella wrote:

Got it ;-)

>
> Just on the platform device: Greg seems to be going on an anti-platform

I see, thanks for sharing!

Currently, I have
- module_platform_driver_probe(tpm_svsm_driver, tpm_svsm_probe) in
  drivers/char/tpm/tpm_svsm.c since they asked to keep tpm drivers in
  drivers/char/tpm
- platform_device_register(&tpm_svsm_device) in arch/x86/coco/sev/core.c
  to load it

I'll check if I can use the faux bus in this case.

>
> > If no one is working on the new SVSM bus or planning to (don't want

If I can do something (probably next week), I'll let you know!

Thanks,
Stefano

---
