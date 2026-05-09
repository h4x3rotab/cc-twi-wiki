---
topic_id: 115809076
subject: "Putting finishing touches on our IETF submission"
participants: ["Mark Novak", "Yogesh Deshpande (Arm)"]
first_post: 2025-10-17
last_post: 2025-10-17
message_count: 3
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/putting_finishing_touches_on/115809076
---

# Putting finishing touches on our IETF submission

## Message 1 (#99) — Mark Novak — 2025-10-17 15:20 UTC

I cleaned up all sequence diagrams and ensured consistency. Thanks Yogesh for creating them in the first place!

I can work on this on the weekend, but I will be traveling all day on Monday and at the mercy of airline internet. If the draft is not submitted on Sunday, I will need someone to commit to submitting it as that's the deadline.

There are a few actions left with only a couple of days left to finish them. Likely incomplete list below:

1. Get rid of placeholders

You will see entries like the ones below:

```
venue:
#  group: WG
#  type: Working Group
#  mail: WG@...
#  arch: https://example.com/WG
```

2. Ensure that the resulting complied text has no obvious issues

How do I do see the generated text that's submission ready? What is the process for submission?

3. Review the sequence diagrams and look for obvious errors, inconsistencies, omissions, areas for improvement

Currently diagrams use "Credential Attributes" and the draft text refers to "Claims". We should probably choose and use one term throughout. Probably not a blocker though as we can always fix that in v2.

4. Check for security issues; don't necessarily have to resolve them, but should at least note them.

I can think of one already: in the flow where Workload requests Credential directly from Credential Authority, and Credential Authority invokes Verifier to obtain Claims about the Workload, how do we handle freshness (nonce)?

5. Fix TODOs

The Variant 1 / Variant 2 has not yet been converted to ASCII.

## Message 2 (#100) — Yogesh Deshpande (Arm) — 2025-10-17 18:43 UTC

I can do the submission on Monday.

Regards,

Yogesh

Sent from
[Outlook for Android](https://aka.ms/AAb9ysg)

[toggle quoted message
Show quoted text](#quoted-258367543)

---

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf
of Mark Novak via lists.confidentialcomputing.io <mark.novak=outlook.com@...>  
**Sent:** Friday, October 17, 2025 4:20:00 PM  
**To:** trustworthy-workload-identity-sig@... <trustworthy-workload-identity-sig@...>  
**Subject:** [Trustworthy-Workload-Identity-SIG] Putting finishing touches on our IETF submission

I cleaned up all sequence diagrams and ensured consistency. Thanks Yogesh for creating them in the first place!

I can work on this on the weekend, but I will be traveling all day on Monday and at the mercy of airline internet. If the draft is not submitted on Sunday, I will need someone to commit to submitting it as that's the deadline.

There are a few actions left with only a couple of days left to finish them. Likely incomplete list below:

1. Get rid of placeholders

You will see entries like the ones below:

```
venue:
#  group: WG
#  type: Working Group
#  mail: WG@...
#  arch: https://example.com/WG
```

2. Ensure that the resulting complied text has no obvious issues

How do I do see the generated text that's submission ready? What is the process for submission?

3. Review the sequence diagrams and look for obvious errors, inconsistencies, omissions, areas for improvement

Currently diagrams use "Credential Attributes" and the draft text refers to "Claims". We should probably choose and use one term throughout. Probably not a blocker though as we can always fix that in v2.

4. Check for security issues; don't necessarily have to resolve them, but should at least note them.

I can think of one already: in the flow where Workload requests Credential directly from Credential Authority, and Credential Authority invokes Verifier to obtain Claims about the Workload, how do we handle freshness (nonce)?

5. Fix TODOs

The Variant 1 / Variant 2 has not yet been converted to ASCII.

IMPORTANT NOTICE: The contents of this email and any attachments are confidential and may also be privileged. If you are not the intended recipient, please notify the sender immediately and do not disclose the contents to any other person, use it for any purpose,
or store or copy the information in any medium. Thank you.

contentLoaded(false, function() {
$('#quoted-258367543').on('show.bs.collapse', function() {
$('#qlabel-258367543').text("Hide quoted text");
})
$('#quoted-258367543').on('hide.bs.collapse', function() {
$('#qlabel-258367543').text("Show quoted text");
})
});

## Message 3 (#101) — Mark Novak — 2025-10-17 21:00 UTC

Ok. Thanks Yogesh. I will monitor my email all weekend in case you have anything you want to discuss.

[toggle quoted message
Show quoted text](#quoted-258372136)

---

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf
of Yogesh Deshpande (Arm) via lists.confidentialcomputing.io <Yogesh.Deshpande=arm.com@...>  
**Sent:** Friday, October 17, 2025 11:42:26 AM  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** Re: [Trustworthy-Workload-Identity-SIG] Putting finishing touches on our IETF submission

I can do the submission on Monday.

Regards,

Yogesh

Sent from
[Outlook for Android](https://aka.ms/AAb9ysg)

---

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf
of Mark Novak via lists.confidentialcomputing.io <mark.novak=outlook.com@...>  
**Sent:** Friday, October 17, 2025 4:20:00 PM  
**To:** trustworthy-workload-identity-sig@... <trustworthy-workload-identity-sig@...>  
**Subject:** [Trustworthy-Workload-Identity-SIG] Putting finishing touches on our IETF submission

I cleaned up all sequence diagrams and ensured consistency. Thanks Yogesh for creating them in the first place!

I can work on this on the weekend, but I will be traveling all day on Monday and at the mercy of airline internet. If the draft is not submitted on Sunday, I will need someone to commit to submitting it as that's the deadline.

There are a few actions left with only a couple of days left to finish them. Likely incomplete list below:

1. Get rid of placeholders

You will see entries like the ones below:

```
venue:
#  group: WG
#  type: Working Group
#  mail: WG@...
#  arch: https://example.com/WG
```

2. Ensure that the resulting complied text has no obvious issues

How do I do see the generated text that's submission ready? What is the process for submission?

3. Review the sequence diagrams and look for obvious errors, inconsistencies, omissions, areas for improvement

Currently diagrams use "Credential Attributes" and the draft text refers to "Claims". We should probably choose and use one term throughout. Probably not a blocker though as we can always fix that in v2.

4. Check for security issues; don't necessarily have to resolve them, but should at least note them.

I can think of one already: in the flow where Workload requests Credential directly from Credential Authority, and Credential Authority invokes Verifier to obtain Claims about the Workload, how do we handle freshness (nonce)?

5. Fix TODOs

The Variant 1 / Variant 2 has not yet been converted to ASCII.

IMPORTANT NOTICE: The contents of this email and any attachments are confidential and may also be privileged. If you are not the intended recipient, please notify the sender immediately and do not disclose the contents to any other person, use it for any purpose,
or store or copy the information in any medium. Thank you.

contentLoaded(false, function() {
$('#quoted-258372136').on('show.bs.collapse', function() {
$('#qlabel-258372136').text("Hide quoted text");
})
$('#quoted-258372136').on('hide.bs.collapse', function() {
$('#qlabel-258372136').text("Show quoted text");
})
});
