---
topic_id: 115008881
subject: "TWI Reference Architecture &lt;---&gt; Mesh blueprint"
participants: ["Manu Fontaine"]
first_post: 2025-09-01
last_post: 2025-09-01
message_count: 1
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/twi_reference_architecture/115008881
---

# TWI Reference Architecture &lt;---&gt; Mesh blueprint

## Message 1 (#74) — Manu Fontaine — 2025-09-01 14:56 UTC

Hello everyone,

In preparation for our discussion tomorrow, here is our perspective on how the blueprint of the Mesh can inform the CCC TWI Reference Architecture:

- We showed that a foundational blueprint exists to automate the establishment of cryptographic relationships between any two entities across domains, with no privileged insider whatsoever.

- The backbone of this blueprint is a hierarchical and recursive Attester/Verifier network that also acts as decentralized, tamper-proof, and confidential registry. Verified software agents can then be deployed as the leaves of this backbone to adapt and connect to varying types of entities (such as workloads, but also people, orgs, IoT...).

- This approach inherently solves the composition problem, as a verified "composite verifier agent" can retrieve attestation evidence from multiple equally-verified "entity verifier agents" for entities of various types. The deployment of new agents is itself verified through a verified "Factory Agent" connecting to the CI/CD pipeline, and a verified "Deployment Agent" that deploys verified executables.

- For durability, scalability, and resiliency reasons, it is essential that each agent have its own local, private, confidential, and tamper-proof registry to relax uptime requirements on the Attester/Verifier network itself.

- This implies that the Attester/Verifier network not only acts as a Certificate Authority for the agents, but also as a hierarchical, recursive, decentralized identity and key management system to enable Agents to gain access to their own encryption keys upon successful verification (similar to sealing, but across a cluster of TEEs running the same code).

- This blueprint is made possible by the use of cryptographic identifiers (StemIDs), which is only possible thanks to Confidential Computing (which is why we submit that the CCC should embrace it and co-operate it).

- Our perspective is that this is also the necessary architecture for true "personal agency" for all types of entities, which we believe will become necessary for the upcoming agentic internet.

I have attached the slides to this email, and I saw that [last week's meeting video is now available](https://youtu.be/44yCqLJGxsw) on the CCC YT channel. Happy to answer any questions, just meshage at [m.sh](https://m.sh) :)

Sincerely,

Manu Fontaine

Hushmesh Founder and CEO
