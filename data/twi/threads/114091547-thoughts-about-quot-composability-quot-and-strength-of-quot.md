---
topic_id: 114091547
subject: "Thoughts about &quot;Composability&quot; and strength of &quot;Couplings&quot;"
participants: ["Manu Fontaine", "Mark Novak"]
first_post: 2025-07-10
last_post: 2025-07-15
message_count: 3
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/thoughts_about/114091547
---

# Thoughts about &quot;Composability&quot; and strength of &quot;Couplings&quot;

## Message 1 (#60) — Manu Fontaine — 2025-07-10 22:20 UTC

Unfortunately, I won't be able to attend next week's TWI meeting (or the next as I will be at the IETF meeting too). I wanted to capture some thoughts regarding what we discussed earlier this week.

I think we agreed that identifying a workload from the perspective of a relying party is more than just verifying its attestation evidence. Whether it is provenance or geolocation information, the challenge is about “composability” of workload “attributes” across multiple authoritative information sources. It’s also about the provenance and integrity of all the reference values necessary to verify each of them, and hence the strength of the authentication of the sources, too.  
  
It’s the totality of these attributes and reference values (and their provenance and integrity) that gives the workload its own individuality and integrity, i.e. its “identity”. The challenge then becomes about the strength of the “couplings/bindings” between these various workload attributes, reference values, and one or more long-lived workload Identifiers/Aliases. This means that the identity of the workload does not lie within the workload itself, but in some “workload identity registry”. The cryptographic evidence is the way the workload authenticates itself to its “authentication server” (i.e. its verifier getting reference values from a registry).  
  
The equivalent for SPIFFE is the SPIRE server, and it’s obvious that a compromised SPIRE server results in catastrophic failures. So in our TWI reference architecture, we should specify that verifiers and registries must run in TEEs, too. Otherwise, it would inherently undermine all the efforts that go into using TEEs for the workloads. Which makes sense in a recursive kind of way, as the verifiers and registry are workloads, too. They fall squarely within the TWI scope.

Hope this makes sense, let me know what you think. Thanks, be well.

Manu

## Message 2 (#61) — Mark Novak — 2025-07-10 22:47 UTC

Thank you for the summary, Manu.

Our overriding priority is ability to deploy whatever we architect. So, for instance, if I trust my CSP for geolocation claim, then that’s a risk I’m willing to accept — so long as it does not affect the claims about the code in the TEE that I’m attesting.
So when I say this is Payroll App running in Greece, I trust my chip vendor and my Verifier for the Payroll App part of the claim, and I trust my CSP for the Greece part, and of course not vice versa. I may run the Verifier myself in a locked cage with armed
guards, or I may trust my CSP’s assurances — again, the choice is mine as a customer how I want to go about it. We can certainly make recommendations, but if we over-constrain the recommendations, many (most?) customers won’t be able to follow them and our
efforts would be for naught.

Get [Outlook for iOS](https://aka.ms/o0ukef)

[toggle quoted message
Show quoted text](#quoted-254738178)

---

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf
of Manu Fontaine via lists.confidentialcomputing.io <manu=hushmesh.com@...>  
**Sent:** Thursday, July 10, 2025 3:20:03 PM  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** [Trustworthy-Workload-Identity-SIG] Thoughts about "Composability" and strength of "Couplings"

Unfortunately, I won't be able to attend next week's TWI meeting (or the next as I will be at the IETF meeting too). I wanted to capture some thoughts regarding what we discussed earlier this week.

I think we agreed that identifying a workload from the perspective of a relying party is more than just verifying its attestation evidence. Whether it is provenance or geolocation information, the challenge is about “composability” of workload “attributes”
across multiple authoritative information sources. It’s also about the provenance and integrity of all the reference values necessary to verify each of them, and hence the strength of the authentication of the sources, too.  
  
It’s the totality of these attributes and reference values (and their provenance and integrity) that gives the workload its own individuality and integrity, i.e. its “identity”. The challenge then becomes about the strength of the “couplings/bindings” between
these various workload attributes, reference values, and one or more long-lived workload Identifiers/Aliases. This means that the identity of the workload does not lie within the workload itself, but in some “workload identity registry”. The cryptographic
evidence is the way the workload authenticates itself to its “authentication server” (i.e. its verifier getting reference values from a registry).  
  
The equivalent for SPIFFE is the SPIRE server, and it’s obvious that a compromised SPIRE server results in catastrophic failures. So in our TWI reference architecture, we should specify that verifiers and registries must run in TEEs, too. Otherwise, it would
inherently undermine all the efforts that go into using TEEs for the workloads. Which makes sense in a recursive kind of way, as the verifiers and registry are workloads, too. They fall squarely within the TWI scope.

Hope this makes sense, let me know what you think. Thanks, be well.

Manu

contentLoaded(false, function() {
$('#quoted-254738178').on('show.bs.collapse', function() {
$('#qlabel-254738178').text("Hide quoted text");
})
$('#quoted-254738178').on('hide.bs.collapse', function() {
$('#qlabel-254738178').text("Show quoted text");
})
});

## Message 3 (#62) — Manu Fontaine — 2025-07-15 13:21 UTC

Thanks Mark, comments inline below.

> Thank you for the summary, Manu.
>
> Our overriding priority is ability to deploy whatever we architect.

Manu: 100% agree, of course, and we practice what we preach. Some exciting news:

<https://www.linkedin.com/posts/manufontaine_the-mesh-is-becoming-the-secure-by-design-activity-7350454582835068928-2cEu>

> So, for instance, if I trust my CSP for geolocation claim, then that’s a risk I’m willing to accept — so long as it does not affect the claims about the code in the TEE that I’m attesting.
> So when I say this is Payroll App

Manu: May I suggest we consider different types of workloads? Payroll does not tease out the full set of capabilities that Confidential Computing brings to a decentralized identity, authentication, authorization, and key management workload, for instance. And yet, these are the 4 cornerstones of information security for everything else, so I suggest we start with that?

running in Greece, I trust my chip vendor and my Verifier for the Payroll App part of the claim, and I trust my CSP for the Greece part, and of course not vice versa. I may run the Verifier myself in a locked cage with armed
guards

Manu: That may be true for JPM (not practical for most companies), but by doing that you force your customers to trust you more than could be achieved.

, or I may trust my CSP’s assurances — again, the choice is mine as a customer how I want to go about it.

Manu: How about your customers' interest in minimizing trust? Confidential Computing is very much a Public Benefit technology.

We can certainly make recommendations, but if we over-constrain the recommendations, many (most?) customers won’t be able to follow them and our
efforts would be for naught.

Manu: My perspective is that the CCC Reference Architecture should illustrate the end state of what a Confidential Internet would look like (to demonstrate why we should strive for it, why it's worth it), and then relax constraints to create a guided, practical migration path to accommodate legacy. Most companies won't build it themselves anyway. They will want to buy a solution, which we will be happy to sell them.

And just like you recommended that all CC technologies should include sealing in their roadmap, our CCC Reference Architecture should also serve as the North Star of what future CC chips can do. For instance, we also believe that "protection in use" should be through encryption, and the Reference Architecture is an opportunity to articulate why.

I'm currently at an "agentic web" workshop at MIT, and it's abundantly clear that Confidential Computing is the necessary technology to solve identity, key management (wallets), provenance, integrity, confidentiality, and privacy for high-value agents (not necessarily AI) transacting on behalf of other entities (people, orgs, things, other agents...)

See you in Madrid next week! I look forward to meeting you (and everyone) in person.

M

> Get [Outlook for iOS](https://aka.ms/o0ukef)
>
> ---
>
> **From:** [Trustworthy-Workload-Identity-SIG@...](mailto:Trustworthy-Workload-Identity-SIG@...) <[Trustworthy-Workload-Identity-SIG@...](mailto:Trustworthy-Workload-Identity-SIG@...)> on behalf
> of Manu Fontaine via [lists.confidentialcomputing.io](http://lists.confidentialcomputing.io) <manu=[hushmesh.com@...](mailto:hushmesh.com@...)>  
> **Sent:** Thursday, July 10, 2025 3:20:03 PM  
> **To:** [Trustworthy-Workload-Identity-SIG@...](mailto:Trustworthy-Workload-Identity-SIG@...) <[Trustworthy-Workload-Identity-SIG@...](mailto:Trustworthy-Workload-Identity-SIG@...)>  
> **Subject:** [Trustworthy-Workload-Identity-SIG] Thoughts about "Composability" and strength of "Couplings"
>
> Unfortunately, I won't be able to attend next week's TWI meeting (or the next as I will be at the IETF meeting too). I wanted to capture some thoughts regarding what we discussed earlier this week.
>
> I think we agreed that identifying a workload from the perspective of a relying party is more than just verifying its attestation evidence. Whether it is provenance or geolocation information, the challenge is about “composability” of workload “attributes”
> across multiple authoritative information sources. It’s also about the provenance and integrity of all the reference values necessary to verify each of them, and hence the strength of the authentication of the sources, too.  
>   
> It’s the totality of these attributes and reference values (and their provenance and integrity) that gives the workload its own individuality and integrity, i.e. its “identity”. The challenge then becomes about the strength of the “couplings/bindings” between
> these various workload attributes, reference values, and one or more long-lived workload Identifiers/Aliases. This means that the identity of the workload does not lie within the workload itself, but in some “workload identity registry”. The cryptographic
> evidence is the way the workload authenticates itself to its “authentication server” (i.e. its verifier getting reference values from a registry).  
>   
> The equivalent for SPIFFE is the SPIRE server, and it’s obvious that a compromised SPIRE server results in catastrophic failures. So in our TWI reference architecture, we should specify that verifiers and registries must run in TEEs, too. Otherwise, it would
> inherently undermine all the efforts that go into using TEEs for the workloads. Which makes sense in a recursive kind of way, as the verifiers and registry are workloads, too. They fall squarely within the TWI scope.
>
> Hope this makes sense, let me know what you think. Thanks, be well.
>
> Manu
