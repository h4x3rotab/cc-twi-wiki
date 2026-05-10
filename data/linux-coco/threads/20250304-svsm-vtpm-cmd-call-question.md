---
title: 'SVSM_VTPM_CMD Call question'
date: 2025-03-04
last_reply: 2025-03-04
message_count: 2
participants: ['Stefano Garzarella', 'Tom Lendacky']
---

## [1] Stefano Garzarella — 2025-03-04

Hi Tom, James,
working on the SVSM side of the vTPM emulation, I'm a bit lost on `8.2 
SVSM_VTPM_CMD Call` section.

In the SVSM code [1] we are assuming that the driver is always using a 
PAGE_SIZE buffer for TPM_SEND_COMMAND request/response, but I can't find 
anything in the spec apart from this:

   It is expected that the request/response structure is large
   enough to hold the expected output of the vTPM request. The vTPM
   request/response buffer will be treated as physically contiguous in
   the guest address space.

IIUC from `Table 16: TPM_SEND_COMMAND Request Structure` the 3rd field 
`TPM Command size (in bytes)` is just the amount of bytes filled with 
the request.

How does SVSM know the total buffer size it can use for response?

Claudio mentioned that in an old discussion, we were thinking of adding 
in the specification that the buffer should always be PAGE_SIZE. This 
would explain the assumption we make in SVSM and also the driver that 
always allocates a page.

If there are any changes already planned for the specification, 
apologies in advance for my confusion.

Thanks,
Stefano

[1] https://github.com/coconut-svsm/svsm/blob/376e4571099ee5e9aab8343c137600e97ebe1b4b/kernel/src/protocols/vtpm.rs#L67

---

## [2] Tom Lendacky — 2025-03-04
*Subject: Re: SVSM_VTPM_CMD Call question*

On 3/4/25 10:16, Stefano Garzarella wrote:
> Hi Tom, James,
> working on the SVSM side of the vTPM emulation, I'm a bit lost on `8.2 

It doesn't. It knows the GPA of where the response is supposed to go and
will write to that location. It was a while ago and I don't recall the
reasoning as to why it was decided to not include the response buffer
size on the request. It may have been related to the TPM code not using
an output length? Which may have been the reason for wording (above) in
the spec.

If it turns out to be a requirement for providing the output buffer
length, we can add a new vTPM protocol call, SVSM_VTPM_CMD_EX or such,
where RDX can hold the length of the request/response buffer.

Thanks,
Tom

> 
> Claudio mentioned that in an old discussion, we were thinking of adding 


> 
> If there are any changes already planned for the specification,

---
