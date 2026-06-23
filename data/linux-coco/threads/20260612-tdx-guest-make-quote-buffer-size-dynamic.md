---
title: 'tdx-guest: Make Quote buffer size dynamic'
date: 2026-06-12
last_reply: 2026-06-22
message_count: 9
participants: ['Peter Fang', 'Kiryl Shutsemau', 'Xiaoyao Li']
---

## [1] Peter Fang — 2026-06-12

Hi,

This series changes the TDX attestation driver's Quote buffer size from
a fixed constant to a value queried from the TDX module. So effectively:

  s/FIXED_BUF_SIZE/queried_buf_size/g

...in the TDX guest driver.

Terminology
===========

A "TD Quote" is an attestation structure signed with a platform key. It
contains information about a TDX guest and the platform it's running on.

The "Quote buffer" in the TDX guest driver is a memory buffer shared
between the TDX guest and the host VMM to retrieve TD Quotes. It has a
header defined in the GHCI spec [1].

Device Identifier Composition Engine ("DICE") provides a framework for
layering attestation evidence. This replaces the SGX model of contacting
an Intel server to obtain a certificate.

Problem
=======

The fixed-size Quote buffer approach is not sustainable. As
cryptographic algorithms evolve, TD Quote sizes also grow. A previous
commit [2] increased the guest driver's fixed-size Quote buffer to 128
KB to accommodate DICE Quotes, but it may still be insufficient when
those Quotes use post-quantum cryptography (PQC). PQC certificate chains
are roughly 10x-15x larger than conventional ones, which can increase
Quote sizes to several megabytes.

What's in this series
=====================

To avoid changing the driver whenever the Quote buffer becomes too
small, newer TDX modules report their maximum Quote size via a metadata
field. The guest driver uses this value for its Quote buffer when
available. Older TDX modules continue to use the 128 KB buffer.

The changes do not affect configfs-tsm-report ABIs.

Patch 1/2: Add a helper to read the QUOTE_MAX_SIZE metadata field.
Patch 2/2: Replace the fixed Quote buffer size with the queried value,
           when available.

AI use
======

I used AI tools (Claude:claude-opus-4-7, GitHub Copilot:gpt-5.4) to
proofread this cover letter and the changelogs. The series also
underwent AI code review (Claude:claude-opus-4-7), but the feedback was
limited to style suggestions.

[1] Guest Hypervisor Communication Interface (GHCI) Specification,
    Version 1.5, Section "TDG.VP.VMCALL<GetQuote>"
[2] 43185067c6fd ("configfs-tsm-report: tdx_guest: Increase Quote buffer
    size to 128KB")

Kuppuswamy Sathyanarayanan (1):
  virt: tdx-guest: Allocate Quote buffer dynamically

Peter Fang (1):
  x86/tdx: Add helper to query maximum TD Quote size

 arch/x86/coco/tdx/tdx.c                 | 19 +++++++++
 arch/x86/include/asm/shared/tdx.h       |  1 +
 arch/x86/include/asm/tdx.h              |  2 +
 drivers/virt/coco/tdx-guest/tdx-guest.c | 52 ++++++++++++++++++-------
 4 files changed, 60 insertions(+), 14 deletions(-)


base-commit: 4549871118cf616eecdd2d939f78e3b9e1dddc48

---

## [2] Peter Fang — 2026-06-12
*Subject: [PATCH 1/2] x86/tdx: Add helper to query maximum TD Quote size*

TDX attestation blob ("TD Quote") sizes can grow with newer
cryptographic schemes, so guests can no longer rely on a fixed-size
buffer for the Quote.

Newer TDX modules report the maximum TD Quote size via a TD-scope
metadata field. Add a helper to query it instead of exposing tdg_vm_rd()
directly, as it can read arbitrary metadata fields.

Thanks to Xu Yilun for suggesting this.

Assisted-by: Claude:claude-opus-4-7
Assisted-by: GitHub Copilot:gpt-5.4
Signed-off-by: Peter Fang <peter.fang@intel.com>
---
 arch/x86/coco/tdx/tdx.c           | 19 +++++++++++++++++++
 arch/x86/include/asm/shared/tdx.h |  1 +
 arch/x86/include/asm/tdx.h        |  2 ++
 3 files changed, 22 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 186915a17c50..88c66c46e70a 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -197,6 +197,25 @@ u64 tdx_hcall_get_quote(u8 *buf, size_t size)
 }
 EXPORT_SYMBOL_GPL(tdx_hcall_get_quote);
 
+/**
+ * tdx_get_max_quote_size() - Get the maximum TD Quote size
+ *
+ * Read the maximum size of a TD Quote from a 4-byte TD metadata field. The TDX
+ * guest driver uses it to size the buffer for Quote retrieval. Older TDX
+ * modules do not support this field and return an error.
+ *
+ * Return: Maximum Quote size in bytes on success, or 0 on failure.
+ */
+u32 tdx_get_max_quote_size(void)
+{
+	u64 val, ret;
+
+	ret = tdg_vm_rd(TDCS_QUOTE_MAX_SIZE, &val);
+
+	return ret ? 0 : (u32)val;
+}
+EXPORT_SYMBOL_GPL(tdx_get_max_quote_size);
+
 static void __noreturn tdx_panic(const char *msg)
 {
 	struct tdx_module_args args = {
diff --git a/arch/x86/include/asm/shared/tdx.h b/arch/x86/include/asm/shared/tdx.h
index 049638e3da74..2880f493a8e5 100644
--- a/arch/x86/include/asm/shared/tdx.h
+++ b/arch/x86/include/asm/shared/tdx.h
@@ -49,6 +49,7 @@
 /* TDX TD-Scope Metadata. To be used by TDG.VM.WR and TDG.VM.RD */
 #define TDCS_CONFIG_FLAGS		0x1110000300000016
 #define TDCS_TD_CTLS			0x1110000300000017
+#define TDCS_QUOTE_MAX_SIZE		0x9010000200000008
 #define TDCS_NOTIFY_ENABLES		0x9100000000000010
 #define TDCS_TOPOLOGY_ENUM_CONFIGURED	0x9100000000000019
 
diff --git a/arch/x86/include/asm/tdx.h b/arch/x86/include/asm/tdx.h
index a149740b24e8..ac39674c9479 100644
--- a/arch/x86/include/asm/tdx.h
+++ b/arch/x86/include/asm/tdx.h
@@ -72,6 +72,8 @@ int tdx_mcall_extend_rtmr(u8 index, u8 *data);
 
 u64 tdx_hcall_get_quote(u8 *buf, size_t size);
 
+u32 tdx_get_max_quote_size(void);
+
 void __init tdx_dump_attributes(u64 td_attr);
 void __init tdx_dump_td_ctls(u64 td_ctls);

---

## [3] Peter Fang — 2026-06-12
*Subject: [PATCH 2/2] virt: tdx-guest: Allocate Quote buffer dynamically*

From: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>

The TDX attestation driver currently uses a fixed 128 KB Quote buffer
shared with the host VMM. This may be too small for Quotes using schemes
such as post-quantum cryptography (PQC), where certificate chains can
increase the Quote size to several megabytes.

Allocate the Quote buffer based on the size reported by the TDX module
instead of always reserving a fixed-size buffer. This avoids wasting
memory on platforms that do not require larger Quotes. Older platforms
fall back to the default 128 KB buffer.

Because the Quote buffer must be physically contiguous, its size is
bound by the buddy allocator's maximum page order (4 MB), which should
be sufficient for current attestation needs.

struct tdx_quote_buf has a trailing flexible array, so use offsetof()
instead of sizeof() to calculate the header size.

Signed-off-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Assisted-by: Claude:claude-opus-4-7
Assisted-by: GitHub Copilot:gpt-5.4
Signed-off-by: Peter Fang <peter.fang@intel.com>
---
 drivers/virt/coco/tdx-guest/tdx-guest.c | 52 ++++++++++++++++++-------
 1 file changed, 38 insertions(+), 14 deletions(-)

diff --git a/drivers/virt/coco/tdx-guest/tdx-guest.c b/drivers/virt/coco/tdx-guest/tdx-guest.c
index a9ecc46df187..162fb47f3fae 100644
--- a/drivers/virt/coco/tdx-guest/tdx-guest.c
+++ b/drivers/virt/coco/tdx-guest/tdx-guest.c
@@ -163,7 +163,7 @@ static void tdx_mr_deinit(const struct attribute_group *mr_grp)
  * DICE-based attestation uses layered evidence that requires
  * larger Quote size (~100K).
  */
-#define GET_QUOTE_BUF_SIZE		SZ_128K
+#define GET_QUOTE_DEFAULT_BUF_SIZE	SZ_128K
 
 #define GET_QUOTE_CMD_VER		1
 
@@ -171,7 +171,7 @@ static void tdx_mr_deinit(const struct attribute_group *mr_grp)
 #define GET_QUOTE_SUCCESS		0
 #define GET_QUOTE_IN_FLIGHT		0xffffffffffffffff
 
-#define TDX_QUOTE_MAX_LEN		(GET_QUOTE_BUF_SIZE - sizeof(struct tdx_quote_buf))
+#define TDX_QUOTE_BUF_LEN(n)		(offsetof(struct tdx_quote_buf, data) + (n))
 
 /* struct tdx_quote_buf: Format of Quote request buffer.
  * @version: Quote format version, filled by TD.
@@ -192,8 +192,9 @@ struct tdx_quote_buf {
 	u8 data[];
 };
 
-/* Quote data buffer */
+/* Quote data buffer and size */
 static void *quote_data;
+static size_t quote_data_size;
 
 /* Lock to streamline quote requests */
 static DEFINE_MUTEX(quote_lock);
@@ -210,9 +211,8 @@ static long tdx_get_report0(struct tdx_report_req __user *req)
 			     USER_SOCKPTR(req->tdreport));
 }
 
-static void free_quote_buf(void *buf)
+static void free_quote_buf(void *buf, size_t len)
 {
-	size_t len = PAGE_ALIGN(GET_QUOTE_BUF_SIZE);
 	unsigned int count = len >> PAGE_SHIFT;
 
 	if (set_memory_encrypted((unsigned long)buf, count)) {
@@ -223,19 +223,43 @@ static void free_quote_buf(void *buf)
 	free_pages_exact(buf, len);
 }
 
-static void *alloc_quote_buf(void)
+static size_t get_quote_buf_size(void)
 {
-	size_t len = PAGE_ALIGN(GET_QUOTE_BUF_SIZE);
-	unsigned int count = len >> PAGE_SHIFT;
+	size_t buf_sz = GET_QUOTE_DEFAULT_BUF_SIZE;
+	u32 quote_sz;
+
+	quote_sz = tdx_get_max_quote_size();
+
+	if (quote_sz)
+		/* Reported size does not include GetQuote header */
+		buf_sz = TDX_QUOTE_BUF_LEN(quote_sz);
+
+	return PAGE_ALIGN(buf_sz);
+}
+
+static void *alloc_quote_buf(size_t *buflen)
+{
+	unsigned int count;
+	size_t len;
 	void *addr;
 
+	len = get_quote_buf_size();
+
+	/*
+	 * This fails if the requested size exceeds the buddy allocator's
+	 * maximum order (order-10, 4MB).
+	 */
 	addr = alloc_pages_exact(len, GFP_KERNEL | __GFP_ZERO);
 	if (!addr)
 		return NULL;
 
+	count = len >> PAGE_SHIFT;
+
 	if (set_memory_decrypted((unsigned long)addr, count))
 		return NULL;
 
+	*buflen = len;
+
 	return addr;
 }
 
@@ -286,7 +310,7 @@ static int tdx_report_new_locked(struct tsm_report *report, void *data)
 	if (desc->inblob_len != TDX_REPORTDATA_LEN)
 		return -EINVAL;
 
-	memset(quote_data, 0, GET_QUOTE_BUF_SIZE);
+	memset(quote_data, 0, quote_data_size);
 
 	/* Update Quote buffer header */
 	quote_buf->version = GET_QUOTE_CMD_VER;
@@ -297,7 +321,7 @@ static int tdx_report_new_locked(struct tsm_report *report, void *data)
 	if (ret)
 		return ret;
 
-	err = tdx_hcall_get_quote(quote_data, GET_QUOTE_BUF_SIZE);
+	err = tdx_hcall_get_quote(quote_data, quote_data_size);
 	if (err) {
 		pr_err("GetQuote hypercall failed, status:%llx\n", err);
 		return -EIO;
@@ -316,7 +340,7 @@ static int tdx_report_new_locked(struct tsm_report *report, void *data)
 
 	out_len = READ_ONCE(quote_buf->out_len);
 
-	if (out_len > TDX_QUOTE_MAX_LEN)
+	if (TDX_QUOTE_BUF_LEN(out_len) > quote_data_size)
 		return -EFBIG;
 
 	buf = kvmemdup(quote_buf->data, out_len, GFP_KERNEL);
@@ -418,7 +442,7 @@ static int __init tdx_guest_init(void)
 	if (ret)
 		goto deinit_mr;
 
-	quote_data = alloc_quote_buf();
+	quote_data = alloc_quote_buf(&quote_data_size);
 	if (!quote_data) {
 		pr_err("Failed to allocate Quote buffer\n");
 		ret = -ENOMEM;
@@ -432,7 +456,7 @@ static int __init tdx_guest_init(void)
 	return 0;
 
 free_quote:
-	free_quote_buf(quote_data);
+	free_quote_buf(quote_data, quote_data_size);
 free_misc:
 	misc_deregister(&tdx_misc_dev);
 deinit_mr:
@@ -445,7 +469,7 @@ module_init(tdx_guest_init);
 static void __exit tdx_guest_exit(void)
 {
 	tsm_report_unregister(&tdx_tsm_ops);
-	free_quote_buf(quote_data);
+	free_quote_buf(quote_data, quote_data_size);
 	misc_deregister(&tdx_misc_dev);
 	tdx_mr_deinit(tdx_attr_groups[0]);
 }

---

## [4] Kiryl Shutsemau — 2026-06-12
*Subject: Re: [PATCH 1/2] x86/tdx: Add helper to query maximum TD Quote size*

On Fri, Jun 12, 2026 at 04:08:48AM -0700, Peter Fang wrote:
> TDX attestation blob ("TD Quote") sizes can grow with newer
> cryptographic schemes, so guests can no longer rely on a fixed-size

These supposes to be on the same line, no?

Documentation/process/coding-assistants.rst:  Assisted-by: AGENT_NAME:MODEL_VERSION [TOOL1] [TOOL2]

> Signed-off-by: Peter Fang <peter.fang@intel.com>

One nit below, otherwise:

Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>

> ---
>  arch/x86/coco/tdx/tdx.c           | 19 +++++++++++++++++++

Cast is redundant.

> +}
> +EXPORT_SYMBOL_GPL(tdx_get_max_quote_size);

---

## [5] Kiryl Shutsemau — 2026-06-12
*Subject: Re: [PATCH 2/2] virt: tdx-guest: Allocate Quote buffer dynamically*

On Fri, Jun 12, 2026 at 04:08:49AM -0700, Peter Fang wrote:
> @@ -171,7 +171,7 @@ static void tdx_mr_deinit(const struct attribute_group *mr_grp)
>  #define GET_QUOTE_SUCCESS		0

I've got confused by this offsetof(). It is valid, but why not plain
sizeof()?

Otherwise looks okay to me:

Reviewed-by: Kiryl Shutsemau (Meta) <kas@kernel.org>

---

## [6] Xiaoyao Li — 2026-06-12
*Subject: Re: [PATCH 1/2] x86/tdx: Add helper to query maximum TD Quote size*

On 6/12/2026 7:08 PM, Peter Fang wrote:
> TDX attestation blob ("TD Quote") sizes can grow with newer
> cryptographic schemes, so guests can no longer rely on a fixed-size

Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>

I have another nit other than Kiryl's

> ---
>   arch/x86/coco/tdx/tdx.c           | 19 +++++++++++++++++++

Do we need to start to use

EXPORT_SYMBOL_FOR_MODULES(tdx_get_max_quote_size, "tdx-guest") ?

> +
>   static void __noreturn tdx_panic(const char *msg)

---

## [7] Peter Fang — 2026-06-22
*Subject: Re: [PATCH 1/2] x86/tdx: Add helper to query maximum TD Quote size*

On Fri, Jun 12, 2026 at 01:36:16PM +0100, Kiryl Shutsemau wrote:
> > 
> > Assisted-by: Claude:claude-opus-4-7

I see... I actually used two different agents, so looks like they should
be on separate lines instead?

One example that I found:
91e901c65b4d ("um: drivers: call kernel_strrchr() explicitly in
cow_user.c")

  [ ... ]
  Assisted-by: Claude:claude-opus-4-6
  Assisted-by: Codex:gpt-5-4

> 
> > Signed-off-by: Peter Fang <peter.fang@intel.com>

Thanks for the review Kiryl!

> 
> > +u32 tdx_get_max_quote_size(void)

I'll fix that, thanks.

> > +}
> > +EXPORT_SYMBOL_GPL(tdx_get_max_quote_size);

---

## [8] Peter Fang — 2026-06-22
*Subject: Re: [PATCH 1/2] x86/tdx: Add helper to query maximum TD Quote size*

On Fri, Jun 12, 2026 at 10:25:03PM +0800, Xiaoyao Li wrote:
> > 
> > Assisted-by: Claude:claude-opus-4-7

Thanks for the review Xiaoyao!

> 
> I have another nit other than Kiryl's

This makes sense. But can we use a follow-up patch to improve this file
later? Right now there are only EXPORT_SYMBOL_GPL() usages, so using
EXPORT_SYMBOL_FOR_MODULES() here might look inconsistent.

---

## [9] Peter Fang — 2026-06-22
*Subject: Re: [PATCH 2/2] virt: tdx-guest: Allocate Quote buffer dynamically*

On Fri, Jun 12, 2026 at 01:37:38PM +0100, Kiryl Shutsemau wrote:
> On Fri, Jun 12, 2026 at 04:08:49AM -0700, Peter Fang wrote:
> > @@ -171,7 +171,7 @@ static void tdx_mr_deinit(const struct attribute_group *mr_grp)

I recently noticed that using sizeof() on a struct with a trailing
flexible array may not be the cleanest coding style [1], so I took the
chance and improved it. Looking at it again, I see that I can just use
struct_size_t() and not reinvent the wheel... I'll improve this in the
next revision.

> 
> Otherwise looks okay to me:

Thanks Kiryl!

> 
> -- 

[1] https://lore.kernel.org/linux-coco/a52c4701-c99d-48d5-9b63-8eb1c0e589f0@intel.com/

---
