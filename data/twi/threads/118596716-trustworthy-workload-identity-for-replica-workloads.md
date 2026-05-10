---
topic_id: 118596716
subject: "Trustworthy Workload Identity for Replica Workloads"
participants: ["Mark Novak"]
first_post: 2026-03-31
last_post: 2026-04-14
message_count: 4
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/trustworthy_workload_identity/118596716
---

# Trustworthy Workload Identity for Replica Workloads

## Message 1 (#140) — Mark Novak — 2026-03-31 14:04 UTC

Dan,

The TWI SIG has completed a major milestone by finalizing v1.0 of our "TWI Profile for Replica Workloads". See attached. Replica workloads represent the lion's share of cloud-based computing, encompassing confidential VMs, containers and serverless functions
that share identity with their replicas.

We would like to present this work to the CCC TAC. The goal of the presentation would be to solicit input form consortium members on the contents of the document, but, more importantly, get to a point where this proposal is implemented by the CSPs and solution
vendors. Until this is done, the proposal is just words on paper.

We believe that workload identity is the key ingredient for identity-based zero trust, the full potential of which can be unlocked with confidential computing.

As far as timing, any date starting April 16 can work. Ideally participants would be given a chance to review the document beforehand.

## Message 2 (#146) — Mark Novak — 2026-04-14 02:29 UTC

Dan,

Gentle ping as I have not heard from you. If you did respond, I must have missed it.

[toggle quoted message
Show quoted text](#quoted-264763146)

---

**From:** Mark Novak <Mark.Novak@...>  
**Sent:** Tuesday, March 31, 2026 11:04 AM  
**To:** Dan Middleton <dan.middleton.software@...>; trustworthy-workload-identity-sig@... <trustworthy-workload-identity-sig@...>  
**Subject:** Trustworthy Workload Identity for Replica Workloads

Dan,

The TWI SIG has completed a major milestone by finalizing v1.0 of our "TWI Profile for Replica Workloads". See attached. Replica workloads represent the lion's share of cloud-based computing, encompassing confidential VMs, containers and serverless functions
that share identity with their replicas.

We would like to present this work to the CCC TAC. The goal of the presentation would be to solicit input form consortium members on the contents of the document, but, more importantly, get to a point where this proposal is implemented by the CSPs and solution
vendors. Until this is done, the proposal is just words on paper.

We believe that workload identity is the key ingredient for identity-based zero trust, the full potential of which can be unlocked with confidential computing.

As far as timing, any date starting April 16 can work. Ideally participants would be given a chance to review the document beforehand.

contentLoaded(false, function() {
$('#quoted-264763146').on('show.bs.collapse', function() {
$('#qlabel-264763146').text("Hide quoted text");
})
$('#quoted-264763146').on('hide.bs.collapse', function() {
$('#qlabel-264763146').text("Show quoted text");
})
});

## Message 3 (#148) — Mark Novak — 2026-04-14 15:34 UTC

Yes, this Thursday is an option, but ideally during the first hour of the meeting, as I may have a conflict in the second hour.

[toggle quoted message
Show quoted text](#quoted-264779059)

---

**From:** Dan Middleton <dan.middleton.software@...>  
**Sent:** Tuesday, April 14, 2026 8:11 AM  
**To:** Mark Novak <Mark.Novak@...>; Alec Fernandez <alfernandez@...>; support@... <support@...>  
**Cc:** trustworthy-workload-identity-sig@... <trustworthy-workload-identity-sig@...>  
**Subject:** Re: Trustworthy Workload Identity for Replica Workloads

Hi Mark,  
  
Sorry about the delay. Yes, we definitely want to see the presentation.

If this Thursday is still an option let us know. I think we may not get Gramine this week as originally intended so we may have time.

Thanks,  
Dan

  

On Mon, Apr 13, 2026 at 9:29 PM Mark Novak <[Mark.Novak@...](mailto:Mark.Novak@...)> wrote:

> Dan,
>
> Gentle ping as I have not heard from you. If you did respond, I must have missed it.
>
> ---
>
> **From:** Mark Novak <[Mark.Novak@...](mailto:Mark.Novak@...)>  
> **Sent:** Tuesday, March 31, 2026 11:04 AM  
> **To:** Dan Middleton <[dan.middleton.software@...](mailto:dan.middleton.software@...)>;
> [trustworthy-workload-identity-sig@...](mailto:trustworthy-workload-identity-sig@...) <[trustworthy-workload-identity-sig@...](mailto:trustworthy-workload-identity-sig@...)>  
> **Subject:** Trustworthy Workload Identity for Replica Workloads
>
> Dan,
>
> The TWI SIG has completed a major milestone by finalizing v1.0 of our "TWI Profile for Replica Workloads". See attached. Replica workloads represent the lion's share of cloud-based computing, encompassing confidential VMs, containers and serverless functions
> that share identity with their replicas.
>
> We would like to present this work to the CCC TAC. The goal of the presentation would be to solicit input form consortium members on the contents of the document, but, more importantly, get to a point where this proposal is implemented by the CSPs and solution
> vendors. Until this is done, the proposal is just words on paper.
>
> We believe that workload identity is the key ingredient for identity-based zero trust, the full potential of which can be unlocked with confidential computing.
>
> As far as timing, any date starting April 16 can work. Ideally participants would be given a chance to review the document beforehand.

contentLoaded(false, function() {
$('#quoted-264779059').on('show.bs.collapse', function() {
$('#qlabel-264779059').text("Hide quoted text");
})
$('#quoted-264779059').on('hide.bs.collapse', function() {
$('#qlabel-264779059').text("Show quoted text");
})
});

## Message 4 (#149) — Mark Novak — 2026-04-14 18:35 UTC

Fifteen minutes to cover the basics. If people want to discuss — another fifteen.

[toggle quoted message
Show quoted text](#quoted-264786524)

---

**From:** Alec Fernandez <alfernandez@...>  
**Sent:** Tuesday, April 14, 2026 10:43:22 AM  
**To:** Mark Novak <Mark.Novak@...>; Dan Middleton <dan.middleton.software@...>; support@... <support@...>  
**Cc:** trustworthy-workload-identity-sig@... <trustworthy-workload-identity-sig@...>  
**Subject:** RE: Trustworthy Workload Identity for Replica Workloads

Hey Mark,

 

Good to hear from you.  How much time do you need to cover this topic?  
  
-Alec

 

**From:** Mark Novak <Mark.Novak@...>
  
**Sent:** Tuesday, April 14, 2026 11:34 AM  
**To:** Dan Middleton <dan.middleton.software@...>; Alec Fernandez <alfernandez@...>; support@...  
**Cc:** trustworthy-workload-identity-sig@...  
**Subject:** [EXTERNAL] Re: Trustworthy Workload Identity for Replica Workloads

Yes, this Thursday is an option, but ideally during the first hour of the meeting, as I may have a conflict in the second hour.

---

**From:** Dan Middleton <[dan.middleton.software@...](mailto:dan.middleton.software@...)>  
**Sent:** Tuesday, April 14, 2026 8:11 AM  
**To:** Mark Novak <[Mark.Novak@...](mailto:Mark.Novak@...)>; Alec Fernandez <[alfernandez@...](mailto:alfernandez@...)>;
[support@...](mailto:support@...) <[support@...](mailto:support@...)>  
**Cc:** [trustworthy-workload-identity-sig@...](mailto:trustworthy-workload-identity-sig@...) <[trustworthy-workload-identity-sig@...](mailto:trustworthy-workload-identity-sig@...)>  
**Subject:** Re: Trustworthy Workload Identity for Replica Workloads

Hi Mark,  
  
Sorry about the delay. Yes, we definitely want to see the presentation.

If this Thursday is still an option let us know. I think we may not get Gramine this week as originally intended so we may have time.

Thanks,  
Dan

On Mon, Apr 13, 2026 at 9:29 PM Mark Novak <[Mark.Novak@...](mailto:Mark.Novak@...)> wrote:

> Dan,
>
> Gentle ping as I have not heard from you. If you did respond, I must have missed it.
>
> ---
>
> **From:** Mark Novak <[Mark.Novak@...](mailto:Mark.Novak@...)>  
> **Sent:** Tuesday, March 31, 2026 11:04 AM  
> **To:** Dan Middleton <[dan.middleton.software@...](mailto:dan.middleton.software@...)>;
> [trustworthy-workload-identity-sig@...](mailto:trustworthy-workload-identity-sig@...) <[trustworthy-workload-identity-sig@...](mailto:trustworthy-workload-identity-sig@...)>  
> **Subject:** Trustworthy Workload Identity for Replica Workloads
>
> Dan,
>
> The TWI SIG has completed a major milestone by finalizing v1.0 of our "TWI Profile for Replica Workloads". See attached. Replica workloads represent the lion's
> share of cloud-based computing, encompassing confidential VMs, containers and serverless functions that share identity with their replicas.
>
> We would like to present this work to the CCC TAC. The goal of the presentation would be to solicit input form consortium members on the contents of the document,
> but, more importantly, get to a point where this proposal is implemented by the CSPs and solution vendors. Until this is done, the proposal is just words on paper.
>
> We believe that workload identity is the key ingredient for identity-based zero trust, the full potential of which can be unlocked with confidential computing.
>
> As far as timing, any date starting April 16 can work. Ideally participants would be given a chance to review the document beforehand.

contentLoaded(false, function() {
$('#quoted-264786524').on('show.bs.collapse', function() {
$('#qlabel-264786524').text("Hide quoted text");
})
$('#quoted-264786524').on('hide.bs.collapse', function() {
$('#qlabel-264786524').text("Show quoted text");
})
});
