---
title: '[PATCH v4] virt: tdx-guest: Handle GetQuote request error code'
date: 2024-12-12
last_reply: 2024-12-12
message_count: 1
participants: ['Mikko Ylinen']
---

## [1] Mikko Ylinen — 2024-12-12

Hi,

On Thu, Apr 11, 2024 at 02:22:50AM +0000, Kuppuswamy Sathyanarayanan wrote:
> The tdx-guest driver marshals quote requests via hypercall to have a
> quoting enclave sign attestation evidence about the current state of

Would it be possible to get this queued?

I had the same fix implemented as I ran into the same issue but then
noticed this had already been sent out.

One possible improvement here could be to add a reason for the error
to make it more consistent with the other error paths above:

pr_err("GetQuote failed, status:%llx\n", quote_buf->status);

Anyway, it works as expected as it is so:

Tested-by: Mikko Ylinen <mikko.ylinen@linux.intel.com>

-- Mikko

---
