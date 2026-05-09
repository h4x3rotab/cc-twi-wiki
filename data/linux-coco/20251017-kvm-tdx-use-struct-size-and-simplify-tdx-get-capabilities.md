---
title: 'KVM: TDX: Use struct_size and simplify tdx_get_capabilities'
date: 2025-10-17
last_reply: 2025-11-18
message_count: 2
participants: ['Thorsten Blum', 'Sean Christopherson']
---

## [1] Thorsten Blum — 2025-10-17

Retrieve the number of user entries with get_user() first and return
-E2BIG early if 'user_caps' is too small to fit 'caps'.

Allocate memory for 'caps' only after checking the user buffer's number
of entries, thus removing two gotos and the need for premature freeing.

Use struct_size() instead of manually calculating the number of bytes to
allocate for 'caps', including the nested flexible array.

Finally, copy 'caps' to user space with a single copy_to_user() call.

Signed-off-by: Thorsten Blum <thorsten.blum@linux.dev>
---
Compile-tested only.
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

## [2] Sean Christopherson — 2025-11-18
*Subject: Re: [PATCH] KVM: TDX: Use struct_size and simplify tdx_get_capabilities*

On Fri, 17 Oct 2025 23:39:14 +0200, Thorsten Blum wrote:
> Retrieve the number of user entries with get_user() first and return
> -E2BIG early if 'user_caps' is too small to fit 'caps'.

Applied to kvm-x86 tdx, with Rick's tags and suggested fixups from the RESEND[*]
(I had already applied the original patches, and now that these have been in
linux-next for a while, I don't want to modify the hashes just to change the
patch Link).

[*] https://lore.kernel.org/all/20251112171630.3375-1-thorsten.blum@linux.dev

[1/2] KVM: TDX: Check size of user's kvm_tdx_capabilities array before allocating
      https://github.com/kvm-x86/linux/commit/11b79f8318ae
[2/2] KVM: TDX: Use struct_size to simplify tdx_get_capabilities()
      https://github.com/kvm-x86/linux/commit/398180f93cf3

--
https://github.com/kvm-x86/linux/tree/next

---
