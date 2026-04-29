---
topic_id: 113881043
subject: "General comment on Pull Request 33"
participants: ["Mark Novak", "Mateusz Bronk"]
first_post: 2025-06-28
last_post: 2025-06-29
message_count: 3
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/general_comment_on_pull/113881043
---

# General comment on Pull Request 33

## Message 1 (#48) — Mark Novak — 2025-06-28 16:38 UTC

I've reviewed the pull request #33: <https://github.com/confidential-computing/twi-wimse/pull/33>

My comment is that the content of the text is fine -- for TWI Reference Architecture.

For the Informational Draft I'm afraid this text risks causing a lot of damage to our cause. Let me explain.

Our goal here is to get WIMSE to consider including key extensions demanded by confidential computing. And — very importantly — do it in a way that does NOT disrupt WIMSE reference architecture beyond what is \*\*absolutely unavoidable\*\*.

In that spirit, provenance that we care about mentioning is the unique ID of the Credential, and we can easily leave the still-ambiguous details about what to do with this provenance ID to those Relying Parties who care about such things and are willing to
engage in a TBD dance with the credential issuer to follow up on provenance. That much we can state in our draft. We can easily do a separate informational draft later (for IETF 124) for how a relying party might want to deal with Provenance.

The one thing we MUST get out of WIMSE is agreement at IETF 123 to invert the trust relationship between the workload and its hosting environment, where the workload does not trust the hosting environment to attest itself and instead must rely on RATS style
attestation.

The other thing that would be good to get is compound attestation combining workload and platform claims. They are already working on it in the context of geofencing, and we should push for an architectural design that works for us too. Very important, but
still-secondary goal, falling short of critical importance in the immediate term.

But reading the proposed text of PR33, one can sense that we're introducing the massive amount of work into WIMSE to deal with provenance — and I'm very concerned that it would cause our more important extensions to WIMSE architecture to be rejected. As it
stands right now, provenance rides on unique credential ID and is thus a zero-change extension.

Thoughts?

## Message 2 (#49) — Mateusz Bronk — 2025-06-29 10:23 UTC

Thank you for the review, Mark.

My primary intent behind PR#33 was to reorganize the provenance-related content already present in the draft, to be consistent with updated definitions.

I am however now leaning to agree this may be a little too much for a WIMSE-facing document, creating a false impression that we require changes in their architecture to support provenance.

Since provenance is generally considered out-of-scope for WIMSE group charter (<https://datatracker.ietf.org/doc/charter-ietf-wimse/>), we may indeed be better off not mentioning too much detail at this time.

In order to drive attention to the areas we \*really\* need eyeballs on, I'd propose the following alternative:

1. Keep the new definitions inside the I-D (so that we're precise in our conversations)
2. Move the entire "Provenance" section to TWI Reference architecture (intact, with all sub-chapters, including the types of metadata we consider of value)
3. In the IETF 123 draft, replace the now-removed section with a generic statement to the effect of:
   * *"""The provenance metadata required for a Trustworthy Workload Identity is compatible with existing WIMSE architecture [I-D.draft-ietf-wimse-arch].***The WIMSE data formats and protocol [**I-D.*draft-ietf-wimse-s2s-protocol] support unique identifiers of the identity credentials (for example, a "jti" claim of the Workload Identity Token) and allow for extending the credential claims already.    
     This will allow to bind TWI Workload Provenance and Workload Credential Provenance metadata to them without requiring any changes to WIMSE."""***We can wordsmith the above of course and even add a "*for context see <link to TWI Reference Arch.>*", but the emphasis should be on "we care about provenance, but don't request anything of WIMSE in this regard at this time"

WDYT?

Separately, regarding:

> In that spirit, provenance that we care about mentioning is the unique ID of the Credential, and we can easily leave the still-ambiguous details about what to do with this provenance ID to those Relying Parties who care about such things and are willing to engage in a TBD dance with the credential issuer to follow up on provenance.

I'm OK with mentioning the unique ID of Credential, but not entirely aligned to this sentence.

Granted, a provenance record \*can\* be "*externally*" associated with the unique ID of the Credential, I do not think we've reached internal consensus of this being THE (only) way of doing it and I don't want to create an impression this is our hard requirement towards WIMSE to have such unique identifiers always embedded in the Credentials (today's "jti" claims are OPTIONAL) or that we've picked an by-ID association mechanism already.

For example, I believe an "externally" associated provenance can work even in the absence of a "jti"-like claim (this is because every unique digital record can be fingerprinted - ie. by hash - regardless of whether it contains an identifier or not).

Not to mention, a notable alternative to what I call an "external" provenance binding, is for the creator to embed a provenance locator (or even a some of the provenance claims) inside the credential itself. It may have benefits for environments where the relying party (or the Verifier) is expected to routinely inspect provenance during regular operation (not to have to reach for it async.).

In fact, in the future, we may need to request new IANA identifiers for provenance related claims or even author a separate internet draft for provenance handling alone (I doubt WIMSE would be the group we target with that, though).

All in all, given WIMSE arch. is not prescriptive in this area and, thus, flexible, I prefer to keep it vague with "no changes required" not to create an impression we have already decided on the exact method our provenance records will associate.

This would allow us to proceed with the discussion at our own pace - possibly arriving at the "by-unique-ID" variant eventually, but keeping all our options open in the interim.

Thanks,

Mateusz

## Message 3 (#50) — Mark Novak — 2025-06-29 13:02 UTC

I mostly agree. I think the only provenance related definition we need in the IETF draft is the one we had originally: the credential unique ID with a brief explanation of how it is to be used, and even a mention that the exact mechanism is a future TBD. That's
the only one affecting the credential use and therefore the only one that affects WIMSE. We already reference the TWI SIG charter from the draft, and all the other definitions can go there so interested parties can read that. I cannot stress highly enough
how important it is to keep the focus where the focus belongs.

[toggle quoted message
Show quoted text](#quoted-254308937)

---

**From:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...> on behalf of Mateusz Bronk via lists.confidentialcomputing.io <mateusz.bronk=intel.com@...>  
**Sent:** Sunday, June 29, 2025 3:23 AM  
**To:** Trustworthy-Workload-Identity-SIG@... <Trustworthy-Workload-Identity-SIG@...>  
**Subject:** Re: [Trustworthy-Workload-Identity-SIG] General comment on Pull Request 33

Thank you for the review, Mark.

My primary intent behind PR#33 was to reorganize the provenance-related content already present in the draft, to be consistent with updated definitions.

I am however now leaning to agree this may be a little too much for a WIMSE-facing document, creating a false impression that we require changes in their architecture to support provenance.

Since provenance is generally considered out-of-scope for WIMSE group charter (<https://datatracker.ietf.org/doc/charter-ietf-wimse/>),
we may indeed be better off not mentioning too much detail at this time.

In order to drive attention to the areas we \*really\* need eyeballs on, I'd propose the following alternative:

1. Keep the new definitions inside the I-D (so that we're precise in our conversations)
2. Move the entire "Provenance" section to TWI Reference architecture (intact, with all sub-chapters, including the types of metadata we consider of value)
3. In the IETF 123 draft, replace the now-removed section with a generic statement to the effect of:

* *"""The provenance metadata required for a Trustworthy Workload Identity is compatible with existing WIMSE architecture [I-D.draft-ietf-wimse-arch].  
  The WIMSE data formats and protocol [I-D.draft-ietf-wimse-s2s-protocol] support unique identifiers of the identity credentials (for example, a "jti" claim of the Workload Identity Token) and allow for extending the credential claims already.   
  This will allow to bind TWI Workload Provenance and Workload Credential Provenance metadata to them without requiring any changes to WIMSE."""*We can wordsmith the above of course and even add a "*for context see <link to TWI Reference Arch.>*", but the emphasis should be on "we care about provenance, but don't request anything of WIMSE in this regard at this time"

WDYT?

Separately, regarding:

> In that spirit, provenance that we care about mentioning is the unique ID of the Credential, and we can easily leave the still-ambiguous details about what to do with this provenance ID to those Relying Parties who care about such things and are willing to
> engage in a TBD dance with the credential issuer to follow up on provenance.

I'm OK with mentioning the unique ID of Credential, but not entirely aligned to this sentence.

Granted, a provenance record \*can\* be "*externally*" associated with the unique ID of the Credential, I do not think we've reached internal consensus of this being THE (only) way of doing it and I don't want to create an impression this is our hard
requirement towards WIMSE to have such unique identifiers always embedded in the Credentials (today's "jti" claims are OPTIONAL) or that we've picked an by-ID association mechanism already.

For example, I believe an "externally" associated provenance can work even in the absence of a "jti"-like claim (this is because every unique digital record can be fingerprinted - ie. by hash - regardless of whether it contains an identifier or not).

Not to mention, a notable alternative to what I call an "external" provenance binding, is for the creator to embed a provenance locator (or even a some of the provenance claims) inside the credential itself. It may have benefits for environments where
the relying party (or the Verifier) is expected to routinely inspect provenance during regular operation (not to have to reach for it async.).

In fact, in the future, we may need to request new IANA identifiers for provenance related claims or even author a separate internet draft for provenance handling alone (I doubt WIMSE would be the group we target with that, though).

All in all, given WIMSE arch. is not prescriptive in this area and, thus, flexible, I prefer to keep it vague with "no changes required" not to create an impression we have already decided on the exact method our provenance records will associate.

This would allow us to proceed with the discussion at our own pace - possibly arriving at the "by-unique-ID" variant eventually, but keeping all our options open in the interim.

Thanks,

Mateusz

contentLoaded(false, function() {
$('#quoted-254308937').on('show.bs.collapse', function() {
$('#qlabel-254308937').text("Hide quoted text");
})
$('#quoted-254308937').on('hide.bs.collapse', function() {
$('#qlabel-254308937').text("Show quoted text");
})
});
