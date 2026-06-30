---
topic_id: 119596145
subject: "Agenda for Tuesday June 2 2026"
participants: ["Mark Novak"]
first_post: 2026-06-01
last_post: 2026-06-01
message_count: 1
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/agenda_for_tuesday_june_2/119596145
---

# Agenda for Tuesday June 2 2026

## Message 1 (#176) — Mark Novak — 2026-06-01 16:55 UTC

We have three different directions currently and we need to converge and submit something coherent to the IETF.

Here are the three directions:

1. The TWI SIG IETF draft around replica workloads:
   <https://drive.google.com/drive/u/0/folders/1YslF8Yh6TKtdHjj9kIlN_hvfUcpYkPCO>
2. The draft text that Michael Richardson put in his repo:
   <https://github.com/mcr/twi-rats/blob/mcr-henk-revisit/draft-bdnr-rats-trustworthy-credentials.md>
3. The Identity Bridge blueprint from the CCC TAC:
   <https://docs.google.com/document/d/1yUhUqtXkyVYYRr5QGHGI2Wfz8O9HJy--Xf97zAX2ZKg/edit?tab=t.0>

(3) is new to me, I just learned about it in the last few weeks and it, in my opinion, overemphasizes (short-lived) bearer tokens and still requires Relying Parties to change.

(2) is in github and can be rendered into a draft, but is a fairly radical departure, if content if not in spirit, from (1).

I suggest that longer-term, we converge all three, bringing (3) into the TWI fold, but for the short-term, as in June, we start with the current content in (1) and bring in ideas from (2) and (3) as necessary to have something to present at the IETF.

I made some changes to (1) to incorporate key new ideas from (2), such as support for both passport and background check models, and introduce the role of "Credential Broker" or "Key Broker" into the diagram. I am also open, upon discussion in the SIG, to bring
short-lived bearer tokens into the fold, though bearer tokens are antithetical to TWI as we've been thinking about it until now.

Expect a spirited discussion tomorrow. I hope to see many/most of you there.

Update on my schedule: I am going offline on June 25 until July 6, so unless we drive the text to a form that can be submitted to IETF by June 25, someone else will need to take it over the line. I will still be in Vienna to present this in person.
