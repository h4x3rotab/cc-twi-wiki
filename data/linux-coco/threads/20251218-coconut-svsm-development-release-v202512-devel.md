---
title: 'COCONUT-SVSM Development Release v2025.12-devel'
date: 2025-12-18
last_reply: 2025-12-18
message_count: 1
participants: ['Jörg Rödel']
---

## [1] Jörg Rödel — 2025-12-18

Hi,

The last development release of COCONUT-SVSM for this year has been tagged. Due
to the upcoming holidays in the western parts of the world this release
happened a few weeks earlier than ususal and turned out to be smaller as well.

This time it features 47 non-merge commits since the November release, the
changes include (but are not limited to):

	* Fixed formal verification. This has been broken for the last two
	  releases, so I am excited to report that it works again.

	* Rust safety improvements

	* Initial steps towards a UEFI variable store service with merging the
	  SVSM protocol number definition.

	* Fixed the idle-halt loop. It had a bug that could have caused COCONUT
	  to go into halt while another task is runnable.

	* Improvements in x86 platform support.

With verification working again this is a pretty solid release which received a
good amount of testing as well.

A big "Thank You!" goes to the COCONUT-SVSM community for another year of solid
progress on the project due to all the hard work being done. I'd also like to
thank the Technical Steering Committee for all their help and dedication in
managing the project with PR reviews and setting the technical direction.

I wish everyone a restful time with their loved ones, see you all again next
year!

Regards,

	Joerg

---
