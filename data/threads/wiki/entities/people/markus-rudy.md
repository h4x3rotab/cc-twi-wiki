---
title: Markus Rudy
description: Engineer at Edgeless Systems. Newer SIG voice; provided the most substantive technical critique of the early Vienna draft on the day it was shared.
date: 2026-04-29
tags: [people, edgeless-systems, vienna-critic]
---

**Markus Rudy**, Edgeless Systems (`mr@edgeless.systems`). First appears in the archive on the [Vienna submission](../drafts/vienna-submission.md) thread on 2026-04-24, where he provided the day-of critique that is shaping the SIG's pre-Vienna deliberations[^vienna].

[^vienna]: 118990275-early-draft-of-the-vienna-submission.md

## The Vienna critique

Two threads of pushback on Mark's early Vienna draft[^vienna]:

1. **The RATS architecture doesn't need amending.** "Nothing in the existing RATS model prescribes what the RP should do with the attestation results, and maybe that's a good thing? You are already free to implement an RP with your requirement." Mark's response: in practice, vendors don't, because there's no architectural guidance — *implementors look at RATS, see no guidance, and do not provide this option*.
2. **Skip the RUP entirely.** "If you already have a classical IdP that these RUPs rely on, you only need to make that IdP CC-aware […] The RUPs never need to learn about CC." Mark's response: those CC-aware IdPs are *nowhere to be found* — there is currently no way to integrate SPIFFE with CC, so the architecture extension is what unblocks vendor implementations.

This is the live design dispute the SIG is working through ahead of Vienna 2026.

## See also

- [Vienna submission](../drafts/vienna-submission.md)
- [RATS-Unaware Relying Parties](../../concepts/rats-unaware-relying-parties.md)
