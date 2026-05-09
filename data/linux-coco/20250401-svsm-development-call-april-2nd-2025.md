---
title: 'SVSM Development Call April 2nd, 2025'
date: 2025-04-01
last_reply: 2025-04-03
message_count: 3
participants: ['Jörg Rödel', 'Dionna Amalie Glaze']
---

## [1] Jörg Rödel — 2025-04-01

Hi,

Here is the usual call for agenda items for the this weeks SVSM
development call.  Please send me any agenda items you have in mind or
raise them in the meeting.

Europe switched to summer time as well, so meeting time is back to
normal for all US participants.

Details of the meeting (GMeet and Calendar links, meeting time) can be
found in our governance repository at:

	https://github.com/coconut-svsm/governance

The meeting will be recorded and the recording eventually published.

See you all there.

Regards,

	J�rg

---

## [2] Dionna Amalie Glaze — 2025-04-01
*Subject: Re: [svsm-devel] SVSM Development Call April 2nd, 2025*

I would like to get a clear go/no-go for the proposed
SVSM_ATTEST_SINGLE_SERVICE_EX addition to the SVSM specification so we
can get the ABI committed for Linux to accept the corresponding
additional WO binary attribute for manifest_selector.

I have patches staged on Linux v6.15-rc7 that I won't post on LKML
until there's agreement of the specification change:
https://github.com/deeglaze/amdese-linux/tree/atssex
For SVSM_ATTEST_PROTOCOL support, we need to first merge the same
memory read/write from/to guest memory
https://github.com/coconut-svsm/svsm/pull/653
Then we can talk about SVSM_ATTEST_SINGLE_SERVICE_EX in
https://github.com/coconut-svsm/svsm/pull/662

On Tue, Apr 1, 2025 at 8:52 AM Jörg Rödel <joro@8bytes.org> wrote:
>
> Hi,



--
-Dionna Glaze, PhD, CISSP, CCSP (she/her)

---

## [3] Jörg Rödel — 2025-04-03
*Subject: Re: [svsm-devel] SVSM Development Call April 2nd, 2025*

Meeting minutes are now ready for review:

	https://github.com/coconut-svsm/governance/pull/51

Have fun!

	Joerg

---
