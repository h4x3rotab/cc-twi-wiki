---
title: 'EAT Profile for Device Attestation (follow-up)'
date: 2025-10-16
last_reply: 2025-10-16
message_count: 1
participants: ['Mathieu Poirier']
---

## [1] Mathieu Poirier — 2025-10-16

Good day to all,

On October 9th Thomas and I presented our proposal for a standard
device claim representation to the CCC Kernel SIG group [1].  The
presentation was based on the current IETF draft [2], that was
introduced to the linux-coco mailing list back in July [3].  Slides
for the presentation are attached and the recording is also available
[4].

Participants in the meeting brought forward interesting points of
views, most notably around the addition of a binary representation of
the PCI config space for legacy devices.  That proposition will be
added to the IEFT draft shortly.  Another issue that was raised is the
representation of Post Quantum Cryptography algorithms as specified in
1.4 of the SPDM specification.  That will be reviewed in the coming
weeks to see if the current draft needs to be amended.  If so, it will
provide the first opportunity to model the evolution of the SPDM
specification.

Perhaps more nebulous is the topic of TDISP artefacts, and whether
they need to be included in the device claims at all.  As of this
writing, artefacts yielded by TDISP messages have been left out
because there was no immediate need.  Is this the right way forward?

I would certainly like to have a conversation on that front with
people developing confidential computing solutions.  I would also like
some feedback on the overall usability of this specification.  Note
that there will also be a presentation on that topic at Plumbers later
this year [5].

Best regards,
Mathieu

[1]. https://confidentialcomputing.io/about/committees/#:~:text=The%20Linux%20Kernel%20SIG%20seeks,and%20reduce%20upstream%20maintenance%20burden.
[2]. https://datatracker.ietf.org/doc/html/draft-poirier-rats-eat-da
[3]. https://lore.kernel.org/linux-coco/CANLsYkwPAFm6L1SvfDFvH+fUcNV775Xop2zmOm-ufWrDWCGEZQ@mail.gmail.com/
[4]. https://www.youtube.com/watch?v=9oWyyxJtpqs
[5]. https://lpc.events/event/19/abstracts/2465/

---
