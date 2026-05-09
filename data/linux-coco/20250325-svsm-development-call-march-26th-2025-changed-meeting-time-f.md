---
title: 'SVSM Development Call March 26th, 2025 (Changed meeting time for US)'
date: 2025-03-25
last_reply: 2025-03-31
message_count: 4
participants: ['Jörg Rödel', 'Dionna Amalie Glaze']
---

## [1] Jörg Rödel — 2025-03-25

Hi,

The US is already on summer time and Europe still not until the end of
this week. So again, the SVSM call will be an hour later in the US this
week. Next week timing is back to normal.

Otherwise:

Here is the usual call for agenda items for the this weeks SVSM
development call.  Please send me any agenda items you have in mind or
raise them in the meeting.

Details of the meeting (GMeet and Calendar links, meeting time) can be
found in our governance repository at:

	https://github.com/coconut-svsm/governance

The meeting will be recorded and the recording eventually published.

See you all there.

Regards,

	J�rg

---

## [2] Jörg Rödel — 2025-03-26
*Subject: Re: [svsm-devel] SVSM Development Call March 26th, 2025 (Changed
 meeting time for US)*

Hey again,

On Tue, Mar 25, 2025 at 05:56:53PM +0100, J�rg R�del wrote:
> Here is the usual call for agenda items for the this weeks SVSM
> development call.  Please send me any agenda items you have in mind or

Just a notice that I want to bring the status of some of the PRs to the
agenda today, namely:

	- #259 SVSM: require SNP restricted injection
	  (Can we require restricted injection on SNP?)
	- #528 Attestation driver and proxy (with KBS attestation)
	  (How to solve the stack usage problem?)
	- #541 svsm: add SVSM VTPM Service Attestation
	  (Any dependencies regarding the ongoing attestation report
	   format changes?)
	- #635 virtio-blk storage via mmio using virtio-drivers [v3]
	  (Any blockers, maybe generic MMIO routine support?)

See you in the meeting :)

Regards,

	Joerg

---

## [3] Dionna Amalie Glaze — 2025-03-26
*Subject: Re: [svsm-devel] SVSM Development Call March 26th, 2025 (Changed
 meeting time for US)*

On Wed, Mar 26, 2025 at 8:07 AM Jörg Rödel <joro@8bytes.org> wrote:
>
> Hey again,

I won't be at the entire meeting, so
https://github.com/deeglaze/svsm/tree/attestsrv has my current
reworking of Geoffrey's PR.
Generally I'm not confident about how either of us are reading and
writing guest memory. We need something like Rust-for-linux's
uaccess::UserSlice.

>         - #635 virtio-blk storage via mmio using virtio-drivers [v3]
>           (Any blockers, maybe generic MMIO routine support?)

---

## [4] Jörg Rödel — 2025-03-31
*Subject: Re: [svsm-devel] SVSM Development Call March 26th, 2025 (Changed
 meeting time for US)*

Took a bit longer due to me being in Berlin for OC3 and the weekend, but
here are finally the minutes from last weeks SVSM development call:

	https://github.com/coconut-svsm/governance/pull/50

Have fun!


	Joerg

---
