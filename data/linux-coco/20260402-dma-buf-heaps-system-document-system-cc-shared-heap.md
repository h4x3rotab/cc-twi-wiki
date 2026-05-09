---
title: 'dma-buf: heaps: system: document system_cc_shared heap'
date: 2026-04-02
last_reply: 2026-04-07
message_count: 3
participants: ['Jiri Pirko', 'T.J. Mercier']
---

## [1] Jiri Pirko — 2026-04-02

From: Jiri Pirko <jiri@nvidia.com>

Document the system_cc_shared dma-buf heap that was introduced
recently. Describe its purpose, availability conditions and
relation to confidential computing VMs.

Signed-off-by: Jiri Pirko <jiri@nvidia.com>
---
 Documentation/userspace-api/dma-buf-heaps.rst | 8 ++++++++
 1 file changed, 8 insertions(+)

diff --git a/Documentation/userspace-api/dma-buf-heaps.rst b/Documentation/userspace-api/dma-buf-heaps.rst
index 05445c83b79a..591732393e7d 100644
--- a/Documentation/userspace-api/dma-buf-heaps.rst
+++ b/Documentation/userspace-api/dma-buf-heaps.rst
@@ -16,6 +16,14 @@ following heaps:
 
  - The ``system`` heap allocates virtually contiguous, cacheable, buffers.
 
+ - The ``system_cc_shared`` heap allocates virtually contiguous, cacheable,
+   buffers using shared (decrypted) memory. It is only present on
+   confidential computing (CoCo) VMs where memory encryption is active
+   (e.g., AMD SEV, Intel TDX). The allocated pages have the encryption
+   bit cleared, making them accessible for device DMA without TDISP
+   support. On non-CoCo VMs configurations, this heap is
+   not registered.
+
  - The ``default_cma_region`` heap allocates physically contiguous,
    cacheable, buffers. Only present if a CMA region is present. Such a
    region is usually created either through the kernel commandline

---

## [2] T.J. Mercier — 2026-04-06
*Subject: Re: [PATCH] dma-buf: heaps: system: document system_cc_shared heap*

On Thu, Apr 2, 2026 at 7:11 AM Jiri Pirko <jiri@resnulli.us> wrote:
>
> From: Jiri Pirko <jiri@nvidia.com>

"non-CoCo VM configurations"

> +   not registered.

Doesn't seem like you need to wrap this line.

with that: Reviewed-by: T.J.Mercier <tjmercier@google.com>

> +
>   - The ``default_cma_region`` heap allocates physically contiguous,

Each paragraph starting with '-' confused me for a second there. Those
aren't part of the diff. :)

---

## [3] Jiri Pirko — 2026-04-07
*Subject: Re: [PATCH] dma-buf: heaps: system: document system_cc_shared heap*

Mon, Apr 06, 2026 at 10:20:33PM +0200, tjmercier@google.com wrote:
>On Thu, Apr 2, 2026 at 7:11 AM Jiri Pirko <jiri@resnulli.us> wrote:
>>

Okay. Thanks!


>
>> +

---
