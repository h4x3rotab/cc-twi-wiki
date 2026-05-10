---
title: 'EAT Profile for Device Attestation'
date: 2025-07-18
last_reply: 2025-07-18
message_count: 1
participants: ['Mathieu Poirier']
---

## [1] Mathieu Poirier — 2025-07-18

Hi all,

There have already been some discussions on presenting SPDM
certificates and measurements to user space [1][2] but to the best of
my knowledge, a standard representation of that information for
attestation by an external verifier does not exist.

The work presented in [3] is a proposal aiming to address that by
defining an Evidence claims format that is generic, extensible and
architecture agnostic.  The definition supports SPDM-compliant and
legacy PCIe devices, with room for any number of expansions to
accommodate other bus and protocols as they emerge.  The current
proposal targets device assignment for TEEs but can also be used in a
CMA-SPDM context.  The EAT presented in [3] can be used in a
stand-alone way or embedded in a platform token as needed.

I was hoping to discuss this at the KVM forum but my proposal was not
accepted.  Since Plumbers is 5 months away I decided to start the
conversation on this mailing list.

Best regards,
Mathieu

[1]. https://lpc.events/event/18/contributions/1955/attachments/1396/3026/PCI_Authentication_Slides.pdf
[2]. https://lore.kernel.org/all/cover.1719771133.git.lukas@wunner.de/
[3]. https://datatracker.ietf.org/doc/html/draft-poirier-rats-eat-da

---
