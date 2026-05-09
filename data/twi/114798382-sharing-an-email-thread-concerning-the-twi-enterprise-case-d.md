---
topic_id: 114798382
subject: "Sharing an email thread concerning the TWI Enterprise Case document. If you are new to the world of regulated enterprises, you may learn a few things."
participants: ["Mark Novak"]
first_post: 2025-08-20
last_post: 2025-08-20
message_count: 1
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/sharing_an_email_thread/114798382
---

# Sharing an email thread concerning the TWI Enterprise Case document. If you are new to the world of regulated enterprises, you may learn a few things.

## Message 1 (#73) — Mark Novak — 2025-08-20 12:48 UTC

Mark Novak (Google Docs) <comments-noreply@...> wrote:  
    > Mark Novak  
    > This need not be an external regulation (regulators won't mandate anything  
    > that is in broad use and ready for deployment). The CCC's GRC SIG is  
    > chiseling away at this working with UK's ICO, with CSA via CCM v4.1 (check  
    > the new CEK-03), etc. But internally to a firm we may still have a policy  
    > that uses data-in-use protection to narrow the audit scope.  
  
So who is the relying party if it's an internal policy?

[MN] The payroll database is the relying party for the Payment Disbursement workload.  
  
    > To summarize,  
    > this is a bit of a forward looking scenario, but one that's becoming more and  
    > more real. We, for instance, already use data-in-use protection for reducing  
    > the scope of PCI-DSS audits.  
  
This presents a few problems.  
The first is that the policy winds up unclear if it's internal only.  
This matters: because it means that you can't easily have a Third Party  
Verifier.  The criteria are not clear enough, and that also means that your  
entire set of needed claims are unique.  Will the relevant suppliers and  
clouds work with your unique needs?  Is your checkbook big enough?

[MN] The checkbook is insultingly, disgustingly big. That's not a compliment to my employer. On a more serious note, Governance encompasses everything from state (California), federal (FedRamp), state (Singapore), industry (PCI-DSS) and business specific (B2B
contract) policies and regulations. The criteria are actually very clear: you figure out what measurements correspond to which identities, and the trick is to expose these identities in the industry standard mechanisms. Both JWTs (WITs in WIMSE parlance) and
x.509 certificates are great for that.  
  
So you wind up being the Verifier.  That turns into "pinky swear".  
Can you actually get access to all the Endorsements and References Values you  
need?  Did you buy 1,000,000 Intel Xeons this year?  Nope. No NDA. No values  
for you.  But, the point is that Amazon \*did\*, and so they will get what they need.

[MN] We may have a contract with Microsoft for keeping their servers up-to-date, and for our internal datacenters, we have our own management infrastructure that keeps track of what constitutes compliant hardware. That takes care of hardware reference values.
For software reference values, we will hook up to CI/CD pipelines, VM image repositories and the like. We need flexibility as to which Verifiers we use, but for Microsoft it's likely going be the Microsoft Attestation Service. Likewise for AWS and GCP. That's
not to say it's an exclusive choice: as other offerings come on-line, we should be able to use those. For own own datacenter, we'll also choose a Verifier that we are going to operate ourselves (my prediction, might end up being a third-party offering). The
Architecture should not prevent any choice.  
  
So, you can hire KPMG/Deloite/etc. to operate the Verifier.  
It's a good business for them: if they can scale it to many.  
They need it to scale so that they can get Intel and AMD to give them access  
to the values.

[MN] I can't see it being a third-party service operated by a consultancy like Deloitte; I see no analog of it being done for other sources of truth we use, like Active Directory or DNS, but future will tell.  
  
If there is a regulation, then there is a regulator.  
It seems natural that the regulator should operate the Verifier.

[MN] Absolutely not. Regulators may dictate (in very general terms) that we govern identities, but they don't run CAs. Verisign is not a regulator, but we may trust it in some scenarios. We are subject to over 100 regulators worldwide, so details vary greatly
between them.

(Even if the actual operation is contracted out)  
If the Verifier does not enforce the regulation, then it's not the RP or the Attester's fault.  
It's the regulator's fault.  That places the liability squarely where it belongs.  
Will regulators like this at first?  Of course not.

[MN] Eventually such things get sorted out under SOC3 or similar governance frameworks.  
  
--  
]               Never tell me the odds!                 | ipv6 mesh networks [  
]   Michael Richardson, Sandelman Software Works        |    IoT architect   [  
]     mcr@...  <http://www.sandelman.ca/>        |   ruby on rails    [
