---
topic_id: 114663896
subject: "Conceptual Message Wrapper (CMW) IETF draft from RATS"
participants: ["Mark Novak"]
first_post: 2025-08-12
last_post: 2025-08-12
message_count: 1
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/conceptual_message_wrapper/114663896
---

# Conceptual Message Wrapper (CMW) IETF draft from RATS

## Message 1 (#69) — Mark Novak — 2025-08-12 11:28 UTC

Forwarding from the RATS mailing list. This may be a valuable building block for TWI. We can discuss when we meet today.

Internet-Draft draft-ietf-rats-msg-wrap-17.txt is now available. It is a work  
item of the Remote ATtestation ProcedureS (RATS) WG of the IETF.  
  
   Title:   RATS Conceptual Messages Wrapper (CMW)  
   Authors: Henk Birkholz  
            Ned Smith  
            Thomas Fossati  
            Hannes Tschofenig  
            Dionna Glaze  
   Name:    draft-ietf-rats-msg-wrap-17.txt  
   Pages:   39  
   Dates:   2025-08-12  
  
Abstract:  
  
   The Remote Attestation Procedures architecture (RFC 9334) defines  
   several types of conceptual messages, such as Evidence, Attestation  
   Results, Endorsements, and Reference Values.  These messages can  
   appear in different formats and be transported via various protocols.  
  
   This document introduces the Conceptual Message Wrapper (CMW) that  
   provides a common structure to encapsulate these messages.  It  
   defines a dedicated CBOR tag, corresponding JSON Web Token (JWT) and  
   CBOR Web Token (CWT) claims, and an X.509 extension.  
  
   This allows CMWs to be used in CBOR-based protocols, web APIs using  
   JWTs and CWTs, and PKIX artifacts like X.509 certificates.  
   Additionally, the draft defines a media type and a CoAP content  
   format to transport CMWs over protocols like HTTP, MIME, and CoAP.  
  
   The goal is to improve the interoperability and flexibility of remote  
   attestation protocols.  By introducing a shared message format like  
   the CMW, we can consistently support different attestation message  
   types, evolve message serialization formats without breaking  
   compatibility, and avoid having to redefine how messages are handled  
   in each protocol.  
  
The IETF datatracker status page for this Internet-Draft is:  
<https://datatracker.ietf.org/doc/draft-ietf-rats-msg-wrap/>  
  
There is also an HTML version available at:  
<https://www.ietf.org/archive/id/draft-ietf-rats-msg-wrap-17.html>  
  
A diff from the previous version is available at:  
<https://author-tools.ietf.org/iddiff?url2=draft-ietf-rats-msg-wrap-17>  
  
Internet-Drafts are also available by rsync at:  
rsync.ietf.org::internet-drafts
