---
topic_id: 115104223
subject: "Workload identity for AI agents can’t come soon enough"
participants: ["Manu Fontaine", "Mark Novak"]
first_post: 2025-09-06
last_post: 2025-09-06
message_count: 4
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/workload_identity_for_ai/115104223
---

# Workload identity for AI agents can’t come soon enough

## Message 1 (#78) — Mark Novak — 2025-09-06 19:25 UTC

[https://www.linkedin.com/posts/gadievron\_chatgpt-logged-into-my-linkedin-and-kept-activity-7369621619922628611-51Cy](https://www.linkedin.com/posts/gadievron_chatgpt-logged-into-my-linkedin-and-kept-activity-7369621619922628611-51Cy?utm_source=share&utm_medium=member_ios&rcm=ACoAAAASCg4BsSKPzSkaA6yWh3sm7-juLEMGKGw)

## Message 2 (#79) — Manu Fontaine — 2025-09-06 20:28 UTC

Thanks for sharing, super interesting! Perfect example of why Workload Identity is not enough, though. Personal Agents not only have to have their own "identity", but also must be able to secure credentials and other personal information on behalf of each of the entities they represent. That requires each agent to be able to persist not only its own keychain for its own use, but also a unique keychain for each entity it represents.

Manu

  

On Sat, Sep 6, 2025 at 3:26 PM Mark Novak via [lists.confidentialcomputing.io](http://lists.confidentialcomputing.io) <mark.novak=[outlook.com@...](mailto:outlook.com@...)> wrote:

[toggle quoted message
Show quoted text](#quoted-256876159)

> [https://www.linkedin.com/posts/gadievron\_chatgpt-logged-into-my-linkedin-and-kept-activity-7369621619922628611-51Cy](https://www.linkedin.com/posts/gadievron_chatgpt-logged-into-my-linkedin-and-kept-activity-7369621619922628611-51Cy?utm_source=share&utm_medium=member_ios&rcm=ACoAAAASCg4BsSKPzSkaA6yWh3sm7-juLEMGKGw)

contentLoaded(false, function() {
$('#quoted-256876159').on('show.bs.collapse', function() {
$('#qlabel-256876159').text("Hide quoted text");
})
$('#quoted-256876159').on('hide.bs.collapse', function() {
$('#qlabel-256876159').text("Show quoted text");
})
});

## Message 3 (#80) — Mark Novak — 2025-09-06 20:45 UTC

We should discuss approaches here. Issuing time limited credentials is one option, perhaps there are other approaches.

[toggle quoted message
Show quoted text](#quoted-256876686)

---

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf
of Manu Fontaine via lists.confidentialcomputing.io <manu=hushmesh.com@...>  
**Sent:** Saturday, September 6, 2025 1:27 PM  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** Re: [Trustworthy-Workload-Identity-SIG] Workload identity for AI agents can’t come soon enough

Thanks for sharing, super interesting! Perfect example of why Workload Identity is not enough, though. Personal Agents not only have to have their own "identity", but also must be able to secure credentials and other personal information on behalf of each
of the entities they represent. That requires each agent to be able to persist not only its own keychain for its own use, but also a unique keychain for each entity it represents.

Manu

  

On Sat, Sep 6, 2025 at 3:26 PM Mark Novak via
[lists.confidentialcomputing.io](http://lists.confidentialcomputing.io/) <mark.novak=[outlook.com@...](mailto:outlook.com@...)> wrote:

> [https://www.linkedin.com/posts/gadievron\_chatgpt-logged-into-my-linkedin-and-kept-activity-7369621619922628611-51Cy](https://www.linkedin.com/posts/gadievron_chatgpt-logged-into-my-linkedin-and-kept-activity-7369621619922628611-51Cy?utm_source=share&utm_medium=member_ios&rcm=ACoAAAASCg4BsSKPzSkaA6yWh3sm7-juLEMGKGw)

contentLoaded(false, function() {
$('#quoted-256876686').on('show.bs.collapse', function() {
$('#qlabel-256876686').text("Hide quoted text");
})
$('#quoted-256876686').on('hide.bs.collapse', function() {
$('#qlabel-256876686').text("Show quoted text");
})
});

## Message 4 (#81) — Manu Fontaine — 2025-09-06 21:27 UTC

Yes, let's discuss, as we came to the conclusion that this is only possible with TEEs, which makes it the "killer app" for the CCC. Time limited credentials are not enough. Personal Agents need the ability to secure their own information, and their entities' own private information, so they need unique keychains of symmetric encryption/decryption keys. Much like sealing, but shareable across a cluster of machines running the same workload. That also mitigates the need for a 6-nine verifier and identity provider. See you on Tuesday.

Manu

  

On Sat, Sep 6, 2025 at 4:45 PM Mark Novak via [lists.confidentialcomputing.io](http://lists.confidentialcomputing.io) <mark.novak=[outlook.com@...](mailto:outlook.com@...)> wrote:

[toggle quoted message
Show quoted text](#quoted-256877792)

> We should discuss approaches here. Issuing time limited credentials is one option, perhaps there are other approaches.
>
> ---
>
> **From:** [Trustworthy-Workload-Identity-SIG@...](mailto:Trustworthy-Workload-Identity-SIG@...) <[Trustworthy-Workload-Identity-SIG@...](mailto:Trustworthy-Workload-Identity-SIG@...)> on behalf
> of Manu Fontaine via [lists.confidentialcomputing.io](http://lists.confidentialcomputing.io) <manu=[hushmesh.com@...](mailto:hushmesh.com@...)>  
> **Sent:** Saturday, September 6, 2025 1:27 PM  
> **To:** [Trustworthy-Workload-Identity-SIG@...](mailto:Trustworthy-Workload-Identity-SIG@...) <[Trustworthy-Workload-Identity-SIG@...](mailto:Trustworthy-Workload-Identity-SIG@...)>  
> **Subject:** Re: [Trustworthy-Workload-Identity-SIG] Workload identity for AI agents can’t come soon enough
>
> Thanks for sharing, super interesting! Perfect example of why Workload Identity is not enough, though. Personal Agents not only have to have their own "identity", but also must be able to secure credentials and other personal information on behalf of each
> of the entities they represent. That requires each agent to be able to persist not only its own keychain for its own use, but also a unique keychain for each entity it represents.
>
> Manu
>
>   
>
> On Sat, Sep 6, 2025 at 3:26 PM Mark Novak via
> [lists.confidentialcomputing.io](http://lists.confidentialcomputing.io/) <mark.novak=[outlook.com@...](mailto:outlook.com@...)> wrote:
>
> > [https://www.linkedin.com/posts/gadievron\_chatgpt-logged-into-my-linkedin-and-kept-activity-7369621619922628611-51Cy](https://www.linkedin.com/posts/gadievron_chatgpt-logged-into-my-linkedin-and-kept-activity-7369621619922628611-51Cy?utm_source=share&utm_medium=member_ios&rcm=ACoAAAASCg4BsSKPzSkaA6yWh3sm7-juLEMGKGw)

contentLoaded(false, function() {
$('#quoted-256877792').on('show.bs.collapse', function() {
$('#qlabel-256877792').text("Hide quoted text");
})
$('#quoted-256877792').on('hide.bs.collapse', function() {
$('#qlabel-256877792').text("Show quoted text");
})
});
