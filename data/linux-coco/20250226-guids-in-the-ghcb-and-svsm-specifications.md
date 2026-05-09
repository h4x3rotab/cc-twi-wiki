---
title: 'GUIDs in the GHCB and SVSM specifications'
date: 2025-02-26
last_reply: 2025-03-25
message_count: 3
participants: ['Tom Lendacky', 'Dionna Amalie Glaze']
---

## [1] Tom Lendacky — 2025-02-26

All,

There has been some talk about how the GUIDs in the GHCB and SVSM
specifications should be encoded [1]. The term GUID brings encoding
ambiguity with it.

- RFC 4122 specifies the format of a GUID/UUID and the encodingas
network byte order.

- The UEFI specification says that their GUID format is that of RFC
4122, but that the encoding is different. UEFI has time_low, time_mid,
and time_hi_and_version as little-endian encoded.

Given this, the GHCB and SVSM specifications need to be updated to
specify the expected encoding of the GUIDs.

The GHCB specification will add that the certificate GUIDs follow RFC
4122 in format and encoding (network byte order). This is based on
existing users and tools that have already (likely) been using network
byte order.

The SVSM specification, however, because support has already been added
to the Linux kernel using guid library APIs, will follow RFC 4122 in
format with an encoding of time_low, time_mid, and time_hi_and_version
as little-endian. In Linux, the guid library APIs are guid_parse(),
guid_gen(), etc.

If there are no objections, I'll make those changes.

Thanks,
Tom

[1] https://github.com/coconut-svsm/svsm/pull/541#discussion_r1963201009

---

## [2] Dionna Amalie Glaze — 2025-03-25
*Subject: Re: GUIDs in the GHCB and SVSM specifications*

On Wed, Feb 26, 2025 at 2:40 PM Tom Lendacky <thomas.lendacky@amd.com> wrote:
>
> All,

What we know is that the service GUID is in little endian order, but
what we don't know is if the GUID table of the attest all services
protocol should be the same as is provided in GHCB (big endian).
I haven't heard back on the other thread about a more general
principle that maybe we should follow little-endian in and big-endian
out at least for GUIDs, since reports still use little endian numbers.
I'm writing up the implementation of the GUID table serializer right
now, and it'd be nice to know it can have the same test vectors as the
GUID table marshaling/unmarshaling code I have in go-sev-guest.

>
> Thanks,

---

## [3] Dionna Amalie Glaze — 2025-03-25
*Subject: Re: GUIDs in the GHCB and SVSM specifications*

On Tue, Mar 25, 2025 at 11:50 AM Dionna Amalie Glaze
<dionnaglaze@google.com> wrote:
>
> On Wed, Feb 26, 2025 at 2:40 PM Tom Lendacky <thomas.lendacky@amd.com> wrote:

I suppose nevermind since the headers are slightly different, the
parsers are incompatible. I'll use little endian.

> >
> > Thanks,

---
