---
title: 'SVSM Development Call September 25th, 2024'
date: 2024-09-25
last_reply: 2024-09-26
message_count: 3
participants: ['Jörg Rödel', 'Tom Dohrmann']
---

## [1] Jörg Rödel — 2024-09-25

Hi,

Here is the usual call for agenda items for this weeks SVSM development
call. Please send me any agenda items you have in mind or raise them in
the meeting.

I will give an update about what happened at LPC and KVM Forum related
to the COCONUT-SVSM project for those who were not there. Of course
others that were there are free to chime in on this :)

Details of the meeting (GMeet and Calendar links, meeting time) can be
found in our governance repository at:

	https://github.com/coconut-svsm/governance

The meeting will be recorded and the recording eventually published.

See you all there.

Regards,

	J�rg

---

## [2] Tom Dohrmann — 2024-09-25
*Subject: Re: SVSM Development Call September 25th, 2024*

Hi Joerg,

I'd like to talk about splitting up the stage2 and svsm targets into 
separate crates. Currently, both share a very large amount of code 
through lib.rs. This has a couple notable downsides:

1. stage2 is unnecessarily bloated.
2. We can't have stage2 or svsm-specific APIs in the shared code.
3. publicly exposing all modules in lib.rs hides a lot of dead-code 
warnings.

Regards,
Tom

On 9/25/24 09:34, Jörg Rödel wrote:
> Hi,
>

---

## [3] Jörg Rödel — 2024-09-26
*Subject: Re: [svsm-devel] SVSM Development Call September 25th, 2024*

The PR with the minutes is now posted:

	https://github.com/coconut-svsm/governance/pull/28

Feel free to suggest changes as needed.

Regards,

	Joerg

---
