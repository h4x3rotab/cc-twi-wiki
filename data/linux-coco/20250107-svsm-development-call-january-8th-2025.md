---
title: 'SVSM Development Call January 8th, 2025'
date: 2025-01-07
last_reply: 2025-01-09
message_count: 5
participants: ['Jörg Rödel', 'Dionna Amalie Glaze', 'James Bottomley']
---

## [1] Jörg Rödel — 2025-01-07

Hi,

Happy new year everyone!

Here is the usual call for agenda items for the first SVSM development
call in 2025.  Please send me any agenda items you have in mind or raise
them in the meeting.

I have one item on the agenda so far:

	* IGVM support for QEMU.

Details of the meeting (GMeet and Calendar links, meeting time) can be
found in our governance repository at:

	https://github.com/coconut-svsm/governance

The meeting will be recorded and the recording eventually published.

See you all there.

Regards,

	J�rg

---

## [2] Dionna Amalie Glaze — 2025-01-07
*Subject: Re: [svsm-devel] SVSM Development Call January 8th, 2025*

On Tue, Jan 7, 2025 at 7:55 AM Jörg Rödel <joro@8bytes.org> wrote:
>
> Hi,

Regarding this, I'd like to make sure we cover the topic of MSFT
donating the IGVM spec and implementation to the CCC for appropriate
open governance. We're institutionally blocked without a significant
approval chain to provide code to competitor companies.
Keeping the tools Coconut-SVSM and Qemu uses under Microsoft is an
inversion of power, even with the MIT license.

>
> Details of the meeting (GMeet and Calendar links, meeting time) can be

---

## [3] James Bottomley — 2025-01-07
*Subject: Re: [svsm-devel] SVSM Development Call January 8th, 2025*

On Tue, 2025-01-07 at 08:26 -0800, Dionna Amalie Glaze wrote:
> On Tue, Jan 7, 2025 at 7:55 AM Jörg Rödel <joro@8bytes.org> wrote:
> > 

The spec isn't really separated from the code: it's all one thing.  I
think in principle this document along side code is a good thing and we
want to keep it that way, so you're in effect asking to move this
entire repo:

https://github.com/microsoft/igvm

The IGVM format is designed to be useful beyond simply confidential
computing for multiple different virtual machine images, so even if we
were to move it, I'm not sure the CCC would be the best place to
guarantee that universality.

>  We're institutionally blocked without a significant approval chain
> to provide code to competitor companies.

This sounds a bit like an internal Google problem; I may be able to
help you with this, but I think it's been a while since I engaged
Google legal on open source.  However, the main argument for you to
deploy is that for open source the whole point is to collaborate with
your competitors in the open and you should be empowered to do that.

>  Keeping the tools Coconut-SVSM and Qemu uses under Microsoft is an
> inversion of power, even with the MIT license.

You mean simply by hosting it under our external github account?  It's
where we incubate all our open source projects that accept outside
contributions (and where we hope to openly demonstrate stewardship
worthy of community trust) and I believe Google does something similar.
All corporations tread this fine line: if the project accretes a
vibrant community, we'd likely be happy to move it elsewhere, but we
equally don't want to be accused of simply throwing code over the wall,
which is why we incubate projects to see how they progress.

Regards,

James

---

## [4] Dionna Amalie Glaze — 2025-01-07
*Subject: Re: [svsm-devel] SVSM Development Call January 8th, 2025*

On Tue, Jan 7, 2025 at 3:08 PM James Bottomley
<James.Bottomley@hansenpartnership.com> wrote:
>
> On Tue, 2025-01-07 at 08:26 -0800, Dionna Amalie Glaze wrote:

For now, though for disparate implementations across openvmm, qemu,
Vanadium, EC2, we should expect implementations to diverge without a
forum under a body like the Linux Foundation for folks from different
companies to meet in a legally-blessed way. I asked for a way to
bundle signed reference values to be added to the spec last year, and
I can't easily propose an implementation without director or VP
approval.

> think in principle this document along side code is a good thing and we
> want to keep it that way, so you're in effect asking to move this

I understand. But see below that I don't often get a "yes" to these requests.

> >  Keeping the tools Coconut-SVSM and Qemu uses under Microsoft is an
> > inversion of power, even with the MIT license.

:) I expected a "go kick rocks".
It's commendable, what Microsoft has done for the past 6 years at
least with openenclave, openhcl, openvmm, igvm, etc.
I've barked up that tree here for 7 years and been told no, open
source good will isn't dollars.
I personally agree with everything you said, but had to ask for the
company line.

> Regards,
>

---

## [5] Jörg Rödel — 2025-01-09
*Subject: Re: [svsm-devel] SVSM Development Call January 8th, 2025*

Minutes from yesterdays meeting are now posted in this PR:

	https://github.com/coconut-svsm/governance/pull/40

Regards,

	Joerg

---
