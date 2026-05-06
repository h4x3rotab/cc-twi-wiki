---
topic_id: 113326321
subject: "Trustworthy Composability"
participants: ["Manu Fontaine"]
first_post: 2025-05-27
last_post: 2025-05-27
message_count: 1
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/trustworthy_composability/113326321
---

# Trustworthy Composability

## Message 1 (#38) — Manu Fontaine — 2025-05-27 14:24 UTC

Mark, below are the "trustworthy composability" bullet points I had sent to David last week. I don't think I'll be able to attend the attestation SIG next week, but I will try. Thanks.

Manu

  
  

---------- Forwarded message ---------  
From: **Manu Fontaine** <[Manu@...](mailto:Manu@...)>  
Date: Tue, May 20, 2025 at 10:59 AM  
Subject: Trustworthy Composability  
To: <[david.quigley@...](mailto:david.quigley@...)>

  
  

David, thanks for offering to help, here is my train of thoughts:

- Confidential Computing enables orders-of-magnitude stronger security than non-CC alternatives (smallest attack surface + chip-level verifiability)

- The ultimate "relying parties" (consumers, patients, citizens, warfighters...) rely on composite computing services, i.e. the trustworthiness of end-user experiences depends on the trustworthiness of a whole composition of workloads.

- "Trustworthiness" for end-users means authenticity, confidentiality, and privacy, i.e. properties that can be delivered particularly well with CC but that can be instantly damaged by a single non-CC "weak link".

- This means that the eventual state of a "Trustworthy World" is one where all workloads are trustworthy, per our TWI definition.

- This means that the mechanism by which we create "Trustworthy Compositions" of trustworthy workloads must itself preserve the security strength of the individual component workloads.

- Therefore, while WIMSE starts from a non-TWI world in which composability is not particularly critical today, it should ensure "Trustworthy Composability" from the start as the standard should not inherently weaken the security strength of the eventual "Trustworthy World" end-goal.

I slapped these bullet points in ChatGPT and it gave me this:

Confidential Computing (CC) represents a foundational shift in secure computing, offering orders-of-magnitude stronger assurances than traditional non-CC approaches. By minimizing the attack surface and enabling chip-level attestation and verification, CC provides hardware-rooted security guarantees that software-only or perimeter-based models cannot match. These characteristics make CC a uniquely powerful tool for protecting sensitive workloads and data in increasingly adversarial environments.

In practice, end-users—including consumers, patients, citizens, and mission-critical personnel—interact not with isolated workloads, but with composite computing services. The trustworthiness of these user experiences depends not just on individual system components, but on the trustworthiness of the entire composition of workloads. For end-users, trustworthiness means authenticity, confidentiality, and privacy—core properties that CC is particularly well-suited to enforce. However, these properties can be easily and instantly compromised by the inclusion of a single weak link—a weak com—within a larger service.

Thus, achieving a "Trustworthy World" requires that *all* workloads in a system be independently trustworthy, aligning with the principles outlined in the Trustworthy Workload Integrity (TWI) model. To that end, the composition mechanisms by which trustworthy workloads are composed into larger services must themselves preserve the trustworthiness and security strength of the individual components. Trustworthy Composability is not merely a desirable feature—it is a necessary condition for scaling trust to the full ecosystem level.

While WIMSE originates in a landscape where composability mechanisms are not particularly weaker than individual workloads, it is essential that it anticipate and support trustworthy composability from the start. If we envision a future where all workloads are trustworthy, the composability mechanisms must not become the point at which security is weakened. Instead, it must maintain the strong CC security posture of the workloads it integrates. By building in Trustworthy Composability from the outset, we ensure that the foundations of a future Trustworthy World are not only secure, but sustainable.

Hope this makes sense, happy to discuss if you have questions, please add/modify/delete as you see fit! Thanks for taking it from here.

Sincerely,

Manu Fontaine

Hushmesh Founder and CEO

[redacted-phone]
