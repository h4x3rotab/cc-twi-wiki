---
title: '[PATCH] x86/tdx: support VM area addresses for tdx_enc_status_changed'
date: 2025-08-15
last_reply: 2025-08-15
message_count: 1
participants: ['Shixuan Zhao']
---

## [1] Shixuan Zhao — 2025-08-15

> Could you tell more about use-case?

So basically I'm writing a project involving a kernel module that
communicates with the host which we plan to do it via a shared buffer.
That shared buffer has to be marked as shared so that the hypervisor can
read it. The shared buffer needs a fixed physical address in our case so
we reserved a range and did ioremap for it.

> I am not sure we ever want to convert vmalloc()ed memory to shared as it
> will result in fracturing direct mapping.

Currently in this patch, linear mapping memory will still be handled in
the old way so there's technically no change to existing behaviour. These
memory ranges are still mapped in a whole chunk instead of page-by-page It
merely added a fall back path for vmalloc'ed or ioremap'ed or whatever
mapping that's not in the linear mapping.

tdx_enc_status_changed is called by set_memory_decrypted/encrypted which
takes vmalloc'ed addresses just fine on other platforms like SEV. It would
be an exception for TDX to not support VM area mappings.

> And it seems to the wrong layer to make it. If we really need to go
> this pass (I am not convinced) it has to be done in set_memory.c

set_memory_decrypted handles vmalloc'ed memory. It's just that on TDX it
has to call the TDX-specific enc_status_change_finish which is
tdx_enc_status_changed that does not handle vmalloc'ed memory. This
means that when people call the set_memory_decrypted with a vmalloc'ed,
it will fail on TDX but will succeed in other platforms (e.g., SEV).

Thanks,
Shixuan

---
