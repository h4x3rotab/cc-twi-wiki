---
title: "Add devsec/tsm.git 'next' and 'fixes' branches to linux-next"
date: 2025-04-24
last_reply: 2025-04-28
message_count: 2
participants: ['Dan Williams', 'Stephen Rothwell']
---

## [1] Dan Williams — 2025-04-24

Stephen,

Please add:

	git://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git next

	git://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git fixes

...to linux-next.

This repository contains cross-vendor confidential computing content for
platform "TSM" (TEE Security Manager) functionality. This includes fixes
and ongoing development for the configfs-tsm-report facility, RTMR
support, and PCI Device Security (PCIe TDISP).

These branches merge cleanly with today's linux-next and pass an x86
allmodconfig build. 

The names on Cc: are suitable to add as contacts for issues with these
branches. The bulk of the impact of this tree touches drivers/virt/coco/.

---

## [2] Stephen Rothwell — 2025-04-28
*Subject: Re: Add devsec/tsm.git 'next' and 'fixes' branches to linux-next*

Hi Dan,

On Thu, 24 Apr 2025 22:03:50 -0700 Dan Williams <dan.j.williams@intel.com> wrote:
>
> Please add:

Added from today.

Thanks for adding your subsystem tree as a participant of linux-next.  As
you may know, this is not a judgement of your code.  The purpose of
linux-next is for integration testing and to lower the impact of
conflicts between subsystems in the next merge window. 

You will need to ensure that the patches/commits in your tree/series have
been:
     * submitted under GPL v2 (or later) and include the Contributor's
        Signed-off-by,
     * posted to the relevant mailing list,
     * reviewed by you (or another maintainer of your subsystem tree),
     * successfully unit tested, and 
     * destined for the current or next Linux merge window.

Basically, this should be just what you would send to Linus (or ask him
to fetch).  It is allowed to be rebased if you deem it necessary.

---
