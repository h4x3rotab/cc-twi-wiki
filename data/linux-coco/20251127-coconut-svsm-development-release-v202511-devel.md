---
title: 'COCONUT-SVSM Development Release v2025.11-devel'
date: 2025-11-27
last_reply: 2025-11-27
message_count: 1
participants: ['Jörg Rödel']
---

## [1] Jörg Rödel — 2025-11-27

Hi,

The November development release of COCONUT-SVSM now ready and tagged. This
release features 101 non-merge commits since the October release. Some
highlights of the changes (in no particular order) include:

	* Consuming MADT table via IGVM instead of GWCGF on QEMU. This needs an
	  updated QEMU, so please make sure to use the latest one from the
	  COCONUT-SVSM github project.

	* Some reorganization of repository structure.

	* Build system improvements around building the C parts.

	* IGVM memory map for OVMF support.

	* Improvements to the allocator to allow stage2 to allocate in the
	  kernel heap before kernel is launched (WIP).

	* Updated development plan document.

	* Attestation and verification updates.

	* Other fixes and documentation updates.

Overall this is a pretty solid release, a big Thanks goes out to all
contributors.

As in the previous release, formal verification does still not work. The
reasons it did not work in the October release have been fixed (Thanks!), but
other changes broke it again. We are working on fixing this for the next
release.

Have fun!

Regards,

	Joerg

---
