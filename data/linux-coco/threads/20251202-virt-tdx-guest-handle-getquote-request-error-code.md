---
title: 'virt: tdx-guest: Handle GetQuote request error code'
date: 2025-12-02
last_reply: 2025-12-04
message_count: 7
participants: ['Kuppuswamy Sathyanarayanan', 'Dave Hansen']
---

## [1] Kuppuswamy Sathyanarayanan — 2025-12-02

The tdx-guest driver sends Quote requests to the quoting enclave via a
hypercall to obtain attestation evidence for the current TD state.
Quote generation can fail in two ways: a hypercall failure, or a Quote
failure that occurs after the VMM processes the request. The driver
currently handles only hypercall failures and timeout errors during
Quote processing. Update it to also handle other Quote failures
reported by the VMM (for more details, refer to GHCI spec, v1.5,
March 2023, sec titled "TDG.VP.VMCALL<GetQuote>).

This change does not break the existing ABI behavior. When a Quote
failure occurs, the VMM sets the Quote length to zero. Userspace
already interprets a zero-length Quote as a Quote generation failure.
Returning an explicit error in such cases makes the behavior more
consistent and simplifies error handling in userspace.

Fixes: f4738f56d1dc ("virt: tdx-guest: Add Quote generation support using TSM_REPORTS")
Reported-by: Xiaoyao Li <xiaoyao.li@intel.com>
Closes: https://lore.kernel.org/linux-coco/6bdf569c-684a-4459-af7c-4430691804eb@linux.intel.com/T/#u
Closes: https://github.com/confidential-containers/guest-components/issues/823
Reviewed-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Xiaoyao Li <xiaoyao.li@intel.com>
Acked-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Dan Williams <dan.j.williams@intel.com>
Tested-by: Mikko Ylinen <mikko.ylinen@linux.intel.com>
Signed-off-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
---

Changes since v4:
 * Rebased on top of v6.18-rc1
 * Added Tested-by tag from Mikko.
 * Added more details in commit log to clarify no user impact and also
   link to a related github issue.
 * Added error message for the failed  case.

Changes since v3:
 * Rebased on top of v6.9-rc1
 * Added Dan's Reviewed-by tag.

Changes since v2:
 * Updated the commit log (Dan)
 * Removed pr_err message.

Changes since v1:
 * Updated the commit log (Kirill)

 drivers/virt/coco/tdx-guest/tdx-guest.c | 5 +++++
 1 file changed, 5 insertions(+)

diff --git a/drivers/virt/coco/tdx-guest/tdx-guest.c b/drivers/virt/coco/tdx-guest/tdx-guest.c
index 4e239ec960c9..4e55958184d2 100644
--- a/drivers/virt/coco/tdx-guest/tdx-guest.c
+++ b/drivers/virt/coco/tdx-guest/tdx-guest.c
@@ -304,6 +304,11 @@ static int tdx_report_new_locked(struct tsm_report *report, void *data)
 		return ret;
 	}
 
+	if (quote_buf->status != GET_QUOTE_SUCCESS) {
+		pr_err("GetQuote request failed, status:%llx\n", quote_buf->status);
+		return -EIO;
+	}
+
 	buf = kvmemdup(quote_buf->data, quote_buf->out_len, GFP_KERNEL);
 	if (!buf)
 		return -ENOMEM;

---

## [2] Dave Hansen — 2025-12-02
*Subject: Re: [PATCH v5] virt: tdx-guest: Handle GetQuote request error code*

On 12/2/25 14:22, Kuppuswamy Sathyanarayanan wrote:
> The tdx-guest driver sends Quote requests to the quoting enclave via a
> hypercall to obtain attestation evidence for the current TD state.

I think you're talking about the "GetQuote Status Code" here, right?
That would have been nice to mention. It wasn't exactly trivial to find
because instead of saying what the format of a TDREPORT_STRUCT is, the
docs just call it "format of shared GPA".

> This change does not break the existing ABI behavior. When a Quote
> failure occurs, the VMM sets the Quote length to zero. Userspace
I'm also not seeing a clear problem statement here. What is the end user
visible effect of this "fix"? Why *should* the kernel be parsing this
buffer? Why not not just leave the error handling to userspace?

> Fixes: f4738f56d1dc ("virt: tdx-guest: Add Quote generation support using TSM_REPORTS")
> Reported-by: Xiaoyao Li <xiaoyao.li@intel.com>

Please take a look at:

 https://docs.kernel.org/process/maintainer-tip.html#ordering-of-commit-tags

---

## [3] Kuppuswamy Sathyanarayanan — 2025-12-02
*Subject: Re: [PATCH v5] virt: tdx-guest: Handle GetQuote request error code*

Hi Dave,

Thanks for the review.

On 12/2/2025 2:46 PM, Dave Hansen wrote:
> On 12/2/25 14:22, Kuppuswamy Sathyanarayanan wrote:
>> The tdx-guest driver sends Quote requests to the quoting enclave via a

Yes, that's correct. I am referring to the GetQuote Status Code returned
by TDG.VP.VMCALL<GetQuote>, specifically the error codes that were not
previously checked (GET_QUOTE_ERROR and GET_QUOTE_SERVICE_UNAVAILABLE).

For clarity, I will update the commit description to explicitly refer to
status code table — Table 3-11: TDG.VP.VMCALL<GetQuote> – GetQuote Status
Code.

> 
>> This change does not break the existing ABI behavior. When a Quote


The issue is that, prior to this patch, the kernel silently returned
success for certain Quote failure cases such as when the Quote service
is unavailable or when the VMM reports a processing error. In these
cases, the Quote buffer ends up being empty and userspace is expected
to infer failure indirectly by checking for a zero length Quote. This
behavior is ambiguous and has caused confusion in practice, as reported
in: https://github.com/confidential-containers/guest-components/issues/823

With this patch, all VMM reported Quote failures are explicitly
translated into kernel error returns. This makes failure detection
uniform and simplifies userspace error handling.

The reason the kernel must parse the status field is that the failure
code is only available in the header portion of the shared GPA buffer
populated by the VMM. Userspace currently does not have access to this
header since we only expose the Quote payload itself. Because userspace
cannot directly interpret the VMM status codes, the kernel needs to parse
them and return appropriate generic error codes.

> 
>> Fixes: f4738f56d1dc ("virt: tdx-guest: Add Quote generation support using TSM_REPORTS")

Thanks for pointing this out. I will reorder the commit tags in the next revision.

>

---

## [4] Dave Hansen — 2025-12-02
*Subject: Re: [PATCH v5] virt: tdx-guest: Handle GetQuote request error code*

On 12/2/25 16:00, Kuppuswamy Sathyanarayanan wrote:
> The reason the kernel must parse the status field is that the failure
> code is only available in the header portion of the shared GPA buffer

That's kinda the key to this.

Users are poking at sysfs and expect (near) universal explicit errors.
Are they even doing this from shell scripts most of the time?

Also, please don't just keep tacking gunk onto the changelog. Start
cutting out the cruft, please.

---

## [5] Sathyanarayanan Kuppuswamy — 2025-12-03
*Subject: Re: [PATCH v5] virt: tdx-guest: Handle GetQuote request error code*

Hi Dave,

On 12/2/25 4:03 PM, Dave Hansen wrote:
> On 12/2/25 16:00, Kuppuswamy Sathyanarayanan wrote:
>> The reason the kernel must parse the status field is that the failure

Agreed. I have reworked the commit message to make this the primary
motivation.

>
> Users are poking at sysfs and expect (near) universal explicit errors.

Yes, many users validate the GetQuote flow using simple shell scripts or other
minimal tooling. Since there is no common userspace library for this interface,
each vendor or user typically has their own implementation.

>
> Also, please don't just keep tacking gunk onto the changelog. Start

Got it. How about the following version?

virt: tdx-guest: Return explicit errors for GetQuote failures

TD users often retrieve the Quote through simple libraries or shell
scripts over the configfs interface. In such cases, direct error
returns from the kernel for Quote failures are preferred and simplify
failure detection. Prior to this patch, certain VMM reported GetQuote
failures, such as Quote service unavailability or VMM processing
errors, were silently reported as success with a zero length Quote
buffer. This behavior is ambiguous and makes failure detection
complex.

The VMM reports these failures through the status Code in the header
portion of the shared GPA buffer (refer to GHCI specification v1.5
March 2023, sec titled TDG.VP.VMCALL<GetQuote>, Table 3-10 and Table
3-11 for GPA format and status code details). Userspace does not have
access to this header because only the Quote payload is exposed
through configfs. Therefore, the kernel must parse the status and
translate VMM failures into proper error codes.

Update the TDX guest driver to return explicit kernel errors for all
VMM reported GetQuote failure cases. This preserves existing ABI
behavior because userspace already treats a zero length Quote as a
failure indication. The only change is that such failures now return
explicit error codes instead of silently succeeding.

>

---

## [6] Dave Hansen — 2025-12-03
*Subject: Re: [PATCH v5] virt: tdx-guest: Handle GetQuote request error code*

On 12/3/25 10:04, Sathyanarayanan Kuppuswamy wrote:
> Got it. How about the following version?

Still way too wordy and flowery for my taste.

---

## [7] Sathyanarayanan Kuppuswamy — 2025-12-04
*Subject: Re: [PATCH v5] virt: tdx-guest: Handle GetQuote request error code*

Hi Dave,

On 12/3/25 10:16 AM, Dave Hansen wrote:
> On 12/3/25 10:04, Sathyanarayanan Kuppuswamy wrote:
>> Got it. How about the following version?
Thanks for the feedback. I have trimmed the changelog to a
strict problem and solution format and removed the narrative
wording.

virt: tdx-guest: Return explicit errors for GetQuote failures

Some VMM reported GetQuote failures are currently returned to userspace
as success with a zero length Quote, which makes failure detection
ambiguous.

The VMM failure status is reported in the shared GPA header and is not
visible to userspace. Parse the status in the kernel and return
standard error codes for these failures.

This preserves existing ABI behavior. Userspace already treats a zero
length Quote as failure. It now also receives explicit error codes.

Refer to the GHCI specification v1.5 March 2023, sec titled
TDG.VP.VMCALL<GetQuote>, Table 3-10 and Table 3-11 for details on the
Quote header and status codes.

---
