---
title: '[PATCH -next RFC 0/4] IMA Root of Trust (RoT) Framework'
date: 2025-06-30
last_reply: 2025-06-30
message_count: 1
participants: ['James Bottomley']
---

## [1] James Bottomley — 2025-06-30

[+cc linux-coco]
On Mon, 2025-06-30 at 20:59 +0800, GONG Ruiqi wrote:
[...]
> This patch set provides an implementation of the aforementioned IMA
> RoT framework, which can facilitate easier adaptation for new devices

This is inventing a separate but parallel system to the Coco TSM one. 
If IMA is going to measure to TDX RTMRs, there should at least be some
integration.  In theory the TSM backend can also do TPMs, so it looks
like it should become what you're calling the ROT for IMA subsystem and
IMA should simply make use of it.

Regards,

James

---
