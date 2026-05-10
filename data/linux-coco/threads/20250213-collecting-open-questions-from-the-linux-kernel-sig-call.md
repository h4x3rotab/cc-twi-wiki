---
title: 'Collecting Open Questions from the Linux Kernel SIG Call'
date: 2025-02-13
last_reply: 2025-02-14
message_count: 2
participants: ['Steve Rutherford', 'James Bottomley']
---

## [1] Steve Rutherford — 2025-02-13

Hi all,

I'd like to aggregate a list of open questions. This list is
definitely incomplete. Please add to it!

* Should there be a standard for common protocols? (But not the
underlying interfaces, since those can not be universally shared)
* What is the correct method for capability discovery with the SVSM?
        + Do we want the SVSM to touch ACPI? (No, but what instead?)
        + Going across the common protocol seems pretty reasonable
* What SVSM capabilities are common and complex enough to warrant
further discussion?
      + Observability?
      + TPM?
* How should the shared code within Linux be organized?

Thanks,
Steve

---

## [2] James Bottomley — 2025-02-14
*Subject: Re: Collecting Open Questions from the Linux Kernel SIG Call*

[added the kvm list because of the similarities to virt]
On Thu, 2025-02-13 at 10:26 -0800, Steve Rutherford wrote:
> Hi all,
> 

Sure, but first I'll reiterate the points I made in the meeting.

> 
> * Should there be a standard for common protocols? (But not the

So on this one, it would be nice if that happened.  However, the way
the world works today is that every hypervisor has its own guest to
host communication protocol, usually embedded in a hypervisor specific
bus and its drivers (and then they each have their own separate drivers
for the same function), so having one more for a new SVSM
virtualization component just follows that trend.

> * What is the correct method for capability discovery with the SVSM?

The current way the SVSM is discovered on AMD is via an MSR, which
seems appropriate for something so deep in virtualization.  

>         + Do we want the SVSM to touch ACPI? (No, but what instead?)

To clarify, the reason we don't use ACPI today is that the ACPI tables
are constructed in OVMF using host information from the KVM fw_config
device which the SVSM doesn't touch.  To allow the SVSM to modify the
ACPI tables, we'd have to make it terminate the fw_config device, pull
in the information and then re-supply it to OVMF in the modified form.
It's not that we can't do that, it's just that it's way less messy not
to do it.

>         + Going across the common protocol seems pretty reasonable
> * What SVSM capabilities are common and complex enough to warrant

Once we accept that the SVSM protocol is really just another
incarnation of the hypervisor bus based guest to host communication
mechanism, I think what we're really asking is what features would we
like to be paravirt.  The two above seem natural.

> * How should the shared code within Linux be organized?

And, given the similarity above, I think where everything goes is
fairly easy.  In our case the discovery mechanism is likely going to be
different between AMD SEV and Intel TDX (and the Arm and RISC-V things
when they come along) it makes sense for the core communication
protocol to sit deep in the arch code, but from there we can expose a
message passing (request/response) API which will look the same for
every architecture and which exposes the basic messages described in
the SVSM protocol document.

Perhaps the only outstanding question is should we have our own bus
like all the other paravirt to hypervisor communication systems?

Regards,

James

---
