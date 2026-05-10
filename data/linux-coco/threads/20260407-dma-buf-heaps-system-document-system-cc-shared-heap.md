---
title: 'dma-buf: heaps: system: document system_cc_shared heap'
date: 2026-04-07
last_reply: 2026-04-10
message_count: 3
participants: ['Jiri Pirko', 'Sumit Semwal', 'Marek Szyprowski']
---

## [1] Jiri Pirko — 2026-04-07

From: Jiri Pirko <jiri@nvidia.com>

Document the system_cc_shared dma-buf heap that was introduced
recently. Describe its purpose, availability conditions and
relation to confidential computing VMs.

Signed-off-by: Jiri Pirko <jiri@nvidia.com>
Reviewed-by: T.J.Mercier <tjmercier@google.com>
---
 Documentation/userspace-api/dma-buf-heaps.rst | 7 +++++++
 1 file changed, 7 insertions(+)

diff --git a/Documentation/userspace-api/dma-buf-heaps.rst b/Documentation/userspace-api/dma-buf-heaps.rst
index 05445c83b79a..f56b743cdb36 100644
--- a/Documentation/userspace-api/dma-buf-heaps.rst
+++ b/Documentation/userspace-api/dma-buf-heaps.rst
@@ -16,6 +16,13 @@ following heaps:
 
  - The ``system`` heap allocates virtually contiguous, cacheable, buffers.
 
+ - The ``system_cc_shared`` heap allocates virtually contiguous, cacheable,
+   buffers using shared (decrypted) memory. It is only present on
+   confidential computing (CoCo) VMs where memory encryption is active
+   (e.g., AMD SEV, Intel TDX). The allocated pages have the encryption
+   bit cleared, making them accessible for device DMA without TDISP
+   support. On non-CoCo VM configurations, this heap is not registered.
+
  - The ``default_cma_region`` heap allocates physically contiguous,
    cacheable, buffers. Only present if a CMA region is present. Such a
    region is usually created either through the kernel commandline

---

## [2] Sumit Semwal — 2026-04-10
*Subject: Re: [PATCH v2] dma-buf: heaps: system: document system_cc_shared heap*

Hello Jiri,

On Tue, 7 Apr 2026 at 14:56, Jiri Pirko <jiri@resnulli.us> wrote:
>
> From: Jiri Pirko <jiri@nvidia.com>

Thank you for the patch!

Marek: Since you're taking the dependent patches through your tree,
could you please use:
Acked-by: Sumit Semwal <sumit.semwal@linaro.org>

and take this as well?

Thanks and Best regards,
Sumit.
> ---
>  Documentation/userspace-api/dma-buf-heaps.rst | 7 +++++++

---

## [3] Marek Szyprowski — 2026-04-10
*Subject: Re: [PATCH v2] dma-buf: heaps: system: document system_cc_shared
 heap*

On 10.04.2026 14:14, Sumit Semwal wrote:
> On Tue, 7 Apr 2026 at 14:56, Jiri Pirko <jiri@resnulli.us> wrote:
>> From: Jiri Pirko <jiri@nvidia.com>

Yes, sure. Applied to dma-mapping-for-next. Thanks!

Best regards

---
