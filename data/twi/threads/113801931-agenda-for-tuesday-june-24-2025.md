---
topic_id: 113801931
subject: "Agenda for Tuesday June 24 2025"
participants: ["Manu Fontaine", "Mark Novak"]
first_post: 2025-06-24
last_post: 2025-06-24
message_count: 2
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/agenda_for_tuesday_june_24/113801931
---

# Agenda for Tuesday June 24 2025

## Message 1 (#45) — Mark Novak — 2025-06-24 03:37 UTC

Hello everyone!

Tomorrow is our second-to-last meeting to put finishing touches on our ID. I have a couple of pull requests in place that I would like to discuss, there's some outstanding work from last week that needs filling in, and we need a solid landing plan.

Separately, I reviewed the latest , and have some thoughts I'd like to briefly discuss.

|  |  |
| --- | --- |
|  | [draft-klspa-wimse-verifiable-geo-fence/draft-lkspa-wimse-verifiable-geo-fence.md at main · nedmsmith/draft-klspa-wimse-verifiable-geo-fence](https://github.com/nedmsmith/draft-klspa-wimse-verifiable-geo-fence/blob/main/draft-lkspa-wimse-verifiable-geo-fence.md)  Location afinity for workloads. Contribute to nedmsmith/draft-klspa-wimse-verifiable-geo-fence development by creating an account on GitHub.  github.com |

Finally, as a preview of things I'd like to start tackling after the IETF draft authoring, there is this
[proposal](https://openssf.org/blog/2025/04/04/launch-of-model-signing-v1-0-openssf-ai-ml-working-group-secures-the-machine-learning-supply-chain/)from OpenSSF on model signing. It would be good to look it over and discuss as it relates to a possible input into agentic workflow identity (click through to the  link for actual details).

|  |  |
| --- | --- |
|  | [sigstore/model-transparency: Supply chain security for ML - GitHub](https://github.com/sigstore/model-transparency)  After installing the package, the CLI can be used via either python -m model\_signing <args> or by calling the binary directly, model\_signing <args>.. Users that don't want to install the package, but want to test this using the repository can do the same using Hatch via hatch run python -m model\_signing <args>.. For the remainder of the section, we would use model\_signing <args> method.  github.com |

See you soon!

## Message 2 (#46) — Manu Fontaine — 2025-06-24 09:31 UTC

Hi Mark.

Unfortunately I will not be able to attend this week's meeting either as I will be participating in NIST's "Metrology for Digital Twins: Connecting CHIPS Metrology and SMART USA" event.

Agentic identity, authentication, authorization, and key management are critical for trustworthy digital twins, and "trustworthy composability" is essential for twin workflows, systems of systems, and supply chains. It's the same patterns everywhere.

Thanks, see you next week!

Manu

  

On Mon, Jun 23, 2025, 11:37 PM Mark Novak via [lists.confidentialcomputing.io](http://lists.confidentialcomputing.io) <mark.novak=[outlook.com@...](mailto:outlook.com@...)> wrote:

[toggle quoted message
Show quoted text](#quoted-254122583)

> Hello everyone!
>
> Tomorrow is our second-to-last meeting to put finishing touches on our ID. I have a couple of pull requests in place that I would like to discuss, there's some outstanding work from last week that needs filling in, and we need a solid landing plan.
>
> Separately, I reviewed the latest , and have some thoughts I'd like to briefly discuss.
>
> |  |  |
> | --- | --- |
> |  | [draft-klspa-wimse-verifiable-geo-fence/draft-lkspa-wimse-verifiable-geo-fence.md at main · nedmsmith/draft-klspa-wimse-verifiable-geo-fence](https://github.com/nedmsmith/draft-klspa-wimse-verifiable-geo-fence/blob/main/draft-lkspa-wimse-verifiable-geo-fence.md)  Location afinity for workloads. Contribute to nedmsmith/draft-klspa-wimse-verifiable-geo-fence development by creating an account on GitHub.  [github.com](http://github.com) |
>
> Finally, as a preview of things I'd like to start tackling after the IETF draft authoring, there is this
> [proposal](https://openssf.org/blog/2025/04/04/launch-of-model-signing-v1-0-openssf-ai-ml-working-group-secures-the-machine-learning-supply-chain/)from OpenSSF on model signing. It would be good to look it over and discuss as it relates to a possible input into agentic workflow identity (click through to the  link for actual details).
>
> |  |  |
> | --- | --- |
> |  | [sigstore/model-transparency: Supply chain security for ML - GitHub](https://github.com/sigstore/model-transparency)  After installing the package, the CLI can be used via either python -m model\_signing <args> or by calling the binary directly, model\_signing <args>.. Users that don't want to install the package, but want to test this using the repository can do the same using Hatch via hatch run python -m model\_signing <args>.. For the remainder of the section, we would use model\_signing <args> method.  [github.com](http://github.com) |
>
> See you soon!

contentLoaded(false, function() {
$('#quoted-254122583').on('show.bs.collapse', function() {
$('#qlabel-254122583').text("Hide quoted text");
})
$('#quoted-254122583').on('hide.bs.collapse', function() {
$('#qlabel-254122583').text("Show quoted text");
})
});
