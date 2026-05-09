---
title: '[GIT PULL] Confidential Computing: Attestation fixes for 7.0-rc6'
date: 2026-03-27
last_reply: 2026-03-27
message_count: 2
participants: ['Dan Williams', 'pr-tracker-bot@kernel.org']
---

## [1] Dan Williams — 2026-03-27

Hi Linus, please pull from:

  git://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm tags/tsm-fixes-7.0-rc6

...to receive a fix for the tdx-guest driver. It has appeared in linux-next and
collides with a fix coming from tip/x86/tdx (resolution below). Going forward
all tdx-guest updates should move to the tip/x86/tdx topic, and tsm.git can
remain focused on core attestation report infrastructure.

My conflict resolution matches linux-next's:

diff --cc drivers/virt/coco/tdx-guest/tdx-guest.c
index 23ef3991c4d5,7cee97559ba2..a9ecc46df187
--- a/drivers/virt/coco/tdx-guest/tdx-guest.c
+++ b/drivers/virt/coco/tdx-guest/tdx-guest.c
@@@ -306,12 -309,12 +309,17 @@@ static int tdx_report_new_locked(struc
  		return ret;
  	}
  
 +	if (quote_buf->status != GET_QUOTE_SUCCESS) {
 +		pr_debug("GetQuote request failed, status:%llx\n", quote_buf->status);
 +		return -EIO;
 +	}
 +
- 	buf = kvmemdup(quote_buf->data, quote_buf->out_len, GFP_KERNEL);
+ 	out_len = READ_ONCE(quote_buf->out_len);
+ 
+ 	if (out_len > TDX_QUOTE_MAX_LEN)
+ 		return -EFBIG;
+ 
+ 	buf = kvmemdup(quote_buf->data, out_len, GFP_KERNEL);
  	if (!buf)
  		return -ENOMEM;

---  

The following changes since commit f338e77383789c0cae23ca3d48adcc5e9e137e3c:

  Linux 7.0-rc4 (2026-03-15 13:52:05 -0700)

are available in the Git repository at:

  git://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm tags/tsm-fixes-7.0-rc6

for you to fetch changes up to c3fd16c3b98ed726294feab2f94f876290bf7b61:

  virt: tdx-guest: Fix handling of host controlled 'quote' buffer length (2026-03-20 21:05:50 -0700)

----------------------------------------------------------------
tsm fixes for v7.0-rc6

- Fix a VMM controlled buffer length used to emit TDX attestation
  reports.

----------------------------------------------------------------
Zubin Mithra (1):
      virt: tdx-guest: Fix handling of host controlled 'quote' buffer length

 drivers/virt/coco/tdx-guest/tdx-guest.c | 12 ++++++++++--
 1 file changed, 10 insertions(+), 2 deletions(-)

---

## [2] pr-tracker-bot@kernel.org — 2026-03-27
*Subject: Re: [GIT PULL] Confidential Computing: Attestation fixes for 7.0-rc6*

The pull request you sent on Fri, 27 Mar 2026 13:55:04 -0700:

> git://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm tags/tsm-fixes-7.0-rc6

has been merged into torvalds/linux.git:
https://git.kernel.org/torvalds/c/dd09eb443372f9390d36051d86ebe06e9919aeec

Thank you!

---
