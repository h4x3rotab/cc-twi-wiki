---
title: 'KVM: TDX: Use struct_size and simplify tdx_get_capabilities'
date: 2025-11-12
last_reply: 2025-11-13
message_count: 8
participants: ['Thorsten Blum', 'Edgecombe, Rick P', 'Sean Christopherson']
---

## [1] Thorsten Blum — 2025-11-12

Retrieve the number of user entries with get_user() first and return
-E2BIG early if 'user_caps' is too small to fit 'caps'.

Allocate memory for 'caps' only after checking the user buffer's number
of entries, thus removing two gotos and the need for premature freeing.

Use struct_size() instead of manually calculating the number of bytes to
allocate for 'caps', including the nested flexible array.

Finally, copy 'caps' to user space with a single copy_to_user() call.

Signed-off-by: Thorsten Blum <thorsten.blum@linux.dev>
---
 arch/x86/kvm/vmx/tdx.c | 32 ++++++++++++--------------------
 1 file changed, 12 insertions(+), 20 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 0a49c863c811..23d638b4a003 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2282,37 +2282,29 @@ static int tdx_get_capabilities(struct kvm_tdx_cmd *cmd)
 	if (cmd->flags)
 		return -EINVAL;
 
-	caps = kzalloc(sizeof(*caps) +
-		       sizeof(struct kvm_cpuid_entry2) * td_conf->num_cpuid_config,
-		       GFP_KERNEL);
-	if (!caps)
-		return -ENOMEM;
-
 	user_caps = u64_to_user_ptr(cmd->data);
-	if (get_user(nr_user_entries, &user_caps->cpuid.nent)) {
-		ret = -EFAULT;
-		goto out;
-	}
+	ret = get_user(nr_user_entries, &user_caps->cpuid.nent);
+	if (ret)
+		return ret;
 
-	if (nr_user_entries < td_conf->num_cpuid_config) {
-		ret = -E2BIG;
-		goto out;
-	}
+	if (nr_user_entries < td_conf->num_cpuid_config)
+		return -E2BIG;
+
+	caps = kzalloc(struct_size(caps, cpuid.entries,
+				   td_conf->num_cpuid_config), GFP_KERNEL);
+	if (!caps)
+		return -ENOMEM;
 
 	ret = init_kvm_tdx_caps(td_conf, caps);
 	if (ret)
 		goto out;
 
-	if (copy_to_user(user_caps, caps, sizeof(*caps))) {
+	if (copy_to_user(user_caps, caps, struct_size(caps, cpuid.entries,
+						      caps->cpuid.nent))) {
 		ret = -EFAULT;
 		goto out;
 	}
 
-	if (copy_to_user(user_caps->cpuid.entries, caps->cpuid.entries,
-			 caps->cpuid.nent *
-			 sizeof(caps->cpuid.entries[0])))
-		ret = -EFAULT;
-
 out:
 	/* kfree() accepts NULL. */
 	kfree(caps);

---

## [2] Edgecombe, Rick P — 2025-11-12
*Subject: Re: [PATCH RESEND] KVM: TDX: Use struct_size and simplify
 tdx_get_capabilities*

On Wed, 2025-11-12 at 18:16 +0100, Thorsten Blum wrote:

kvm x86 logs are suggested to start with a short summary of the patch. Maybe:

Simplify the logic for copying the KVM_TDX_CAPABILITIES struct to userspace.


It looks like you are conducting a treewide pattern matching cleanup?

> > Retrieve the number of user entries with get_user() first and return
> > -E2BIG early if 'user_caps' is too small to fit 'caps'.

In the handling of get_user(nr_user_entries, &user_caps->cpuid.nent), the old
code forced -EFAULT, this patch doesn't. But it leaves the copy_to_user()'s to
still force EFAULT. Why?


Tested-by: Rick Edgecombe <rick.p.edgecombe@intel.com> (really the TDX CI)

> > 
> > Signed-off-by: Thorsten Blum <thorsten.blum@linux.dev>

---

## [3] Sean Christopherson — 2025-11-12
*Subject: Re: [PATCH RESEND] KVM: TDX: Use struct_size and simplify tdx_get_capabilities*

On Wed, Nov 12, 2025, Rick P Edgecombe wrote:
> On Wed, 2025-11-12 at 18:16 +0100, Thorsten Blum wrote:
> 

Yeah, I have this locally as two separate patches:

  KVM: TDX: Use struct_size to simplify tdx_get_capabilities()
  KVM: TDX: Check size of user's kvm_tdx_capabilities array before allocating

Your CI caught me just in time; I applied this locally last week, but haven't
fully pushed it to kvm-x86 yet. :-)

> It looks like you are conducting a treewide pattern matching cleanup?
> 

I'll tweak it to explicitly return -EFAULT.  Doesn't matter terribly, but KVM's
standard pattern is to explicitly return -EFAULT.

> Tested-by: Rick Edgecombe <rick.p.edgecombe@intel.com> (really the TDX CI)

---

## [4] Thorsten Blum — 2025-11-12
*Subject: Re: [PATCH RESEND] KVM: TDX: Use struct_size and simplify
 tdx_get_capabilities*

On 12. Nov 2025, at 20:59, Edgecombe, Rick P wrote:
> It looks like you are conducting a treewide pattern matching cleanup?

Just a few instances here and there, but not really treewide.

> In the handling of get_user(nr_user_entries, &user_caps->cpuid.nent), the old
> code forced -EFAULT, this patch doesn't. But it leaves the copy_to_user()'s to

get_user() already returns -EFAULT and the error can just be forwarded,
whereas copy_to_user() returns the number of bytes that could not be
copied and we must return -EFAULT manually.

> Tested-by: Rick Edgecombe <rick.p.edgecombe@intel.com> (really the TDX CI)

Thanks,
Thorsten

---

## [5] Edgecombe, Rick P — 2025-11-13
*Subject: Re: [PATCH RESEND] KVM: TDX: Use struct_size and simplify
 tdx_get_capabilities*

On Wed, 2025-11-12 at 12:24 -0800, Sean Christopherson wrote:
> Your CI caught me just in time; I applied this locally last week, but haven't
> fully pushed it to kvm-x86 yet. :-)

The TDX CI tracks some upstream branches. Is there one in kvm_x86 tree that
would be useful? It's not foolproof enough to warrant sending out automated
mails. But we monitor it and might notice TDX specific issues. Ideally we would
not be chasing generic bugs in like scratch code not headed upstream or
something.

---

## [6] Sean Christopherson — 2025-11-13
*Subject: Re: [PATCH RESEND] KVM: TDX: Use struct_size and simplify tdx_get_capabilities*

On Thu, Nov 13, 2025, Rick P Edgecombe wrote:
> On Wed, 2025-11-12 at 12:24 -0800, Sean Christopherson wrote:
> > Your CI caught me just in time; I applied this locally last week, but haven't

Assuming you're tracking linux-next, I wouldn't bother adding kvm-x86 as kvm-x86/next
is fed into linux-next.  I do push to topic branches, e.g. kvm-x86/tdx, before
merging to kvm-x86/next, but at best you might "gain" a day or two, and the entire
reason I do "half" pushes is so that I can run everything through my testing
before "officially" publishing it to the world.

All in all, explicitly tracking anything kvm-x86 would likely be a net negative.

---

## [7] Edgecombe, Rick P — 2025-11-13
*Subject: Re: [PATCH RESEND] KVM: TDX: Use struct_size and simplify
 tdx_get_capabilities*

On Thu, 2025-11-13 at 08:29 -0800, Sean Christopherson wrote:
> Assuming you're tracking linux-next, I wouldn't bother adding kvm-x86 as kvm-x86/next
> is fed into linux-next.  I do push to topic branches, e.g. kvm-x86/tdx, before

Yea, linux-next and Linus releases. Ok, we'll leave it. I was just thinking
about your lack of TDX testing setup, and wondering if it could help. All good.

---

## [8] Sean Christopherson — 2025-11-13
*Subject: Re: [PATCH RESEND] KVM: TDX: Use struct_size and simplify tdx_get_capabilities*

On Thu, Nov 13, 2025, Rick P Edgecombe wrote:
> On Thu, 2025-11-13 at 08:29 -0800, Sean Christopherson wrote:
> > Assuming you're tracking linux-next, I wouldn't bother adding kvm-x86 as kvm-x86/next

Heh, I appreciate the offer, but you probably shouldn't encourage my laziness at
this point :-)

---
