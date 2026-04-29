---
topic_id: 114723280
subject: "AR4SI draft from RATS"
participants: ["Mark Novak"]
first_post: 2025-08-15
last_post: 2025-08-15
message_count: 1
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/ar4si_draft_from_rats/114723280
---

# AR4SI draft from RATS

## Message 1 (#71) — Mark Novak — 2025-08-15 18:45 UTC

Please take a look at this IETF draft. It is a very different approach to conveying attester identity than the one I've been advocating, being far richer in the level of detail about the attester that it allows one to convey. The flip side of this of course
is that it allows for very rich relying party authorization policies. It is unclear to me if it is compatible with WIMSE.

We can discuss at the next TWI SIG meeting. It is best if you review it before the meeting.

Internet-Draft draft-ietf-rats-ar4si-09.txt is now available. It is a work  
item of the Remote ATtestation ProcedureS (RATS) WG of the IETF.  
  
   Title:   Attestation Results for Secure Interactions  
   Authors: Eric Voit  
            Henk Birkholz  
            Thomas Hardjono  
            Thomas Fossati  
            Vincent Scarlata  
   Name:    draft-ietf-rats-ar4si-09.txt  
   Pages:   39  
   Dates:   2025-08-15  
  
Abstract:  
  
   This document defines reusable Attestation Result information elements.  When these elements are offered to Relying Parties as    Evidence, different aspects of Attester trustworthiness can be evaluated.  Additionally, where the Relying Party is interfacing
with a heterogeneous mix of Attesting Environment and Verifier types, consistent policies can be applied to subsequent information exchange between each Attester and the Relying Party.  
  
   This document also defines two serialisations of the proposed  
   information model, utilising CBOR and JSON.  
  
The IETF datatracker status page for this Internet-Draft is:  
<https://datatracker.ietf.org/doc/draft-ietf-rats-ar4si/>  
  
There is also an HTML version available at:  
<https://www.ietf.org/archive/id/draft-ietf-rats-ar4si-09.html>  
  
A diff from the previous version is available at:  
<https://author-tools.ietf.org/iddiff?url2=draft-ietf-rats-ar4si-09>  
  
Internet-Drafts are also available by rsync at:  
rsync.ietf.org::internet-drafts
