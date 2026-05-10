---
title: 'KVM: TDX: Allow userspace to return errors to guest for MAPGPA'
date: 2026-01-14
last_reply: 2026-01-15
message_count: 9
participants: ['Sagi Shahar', 'Xiaoyao Li', 'Binbin Wu', 'Sean Christopherson']
---

## [1] Sagi Shahar — 2026-01-14

From: Vishal Annapurve <vannapurve@google.com>

MAPGPA request from TDX VMs gets split into chunks by KVM using a loop
of userspace exits until the complete range is handled.

In some cases userspace VMM might decide to break the MAPGPA operation
and continue it later. For example: in the case of intrahost migration
userspace might decide to continue the MAPGPA operation after the
migrration is completed.

Allow userspace to signal to TDX guests that the MAPGPA operation should
be retried the next time the guest is scheduled.

Signed-off-by: Vishal Annapurve <vannapurve@google.com>
Co-developed-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Sagi Shahar <sagis@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 8 +++++++-
 1 file changed, 7 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 2d7a4d52ccfb..3244064b1a04 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1189,7 +1189,13 @@ static int tdx_complete_vmcall_map_gpa(struct kvm_vcpu *vcpu)
 	struct vcpu_tdx *tdx = to_tdx(vcpu);
 
 	if (vcpu->run->hypercall.ret) {
-		tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_INVALID_OPERAND);
+		if (vcpu->run->hypercall.ret == -EBUSY)
+			tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_RETRY);
+		else if (vcpu->run->hypercall.ret == -EINVAL)
+			tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_INVALID_OPERAND);
+		else
+			return -EINVAL;
+
 		tdx->vp_enter_args.r11 = tdx->map_gpa_next;
 		return 1;
 	}

---

## [2] Xiaoyao Li — 2026-01-14
*Subject: Re: [PATCH] KVM: TDX: Allow userspace to return errors to guest for
 MAPGPA*

On 1/14/2026 8:30 AM, Sagi Shahar wrote:
> From: Vishal Annapurve <vannapurve@google.com>
> 

It's incorrect to return -EINVAL here. The -EINVAL will eventually be 
returned to userspace for the VCPU_RUN ioctl. It certainly breaks 
userspace. So it needs to be

	if (vcpu->run->hypercall.ret == -EBUSY)
		tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_RETRY);
	else
		tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_INVALID_OPERAND);

But I'm not sure if such change breaks the userspace ABI that if needs 
to be opted-in.

---

## [3] Binbin Wu — 2026-01-14
*Subject: Re: [PATCH] KVM: TDX: Allow userspace to return errors to guest for
 MAPGPA*

On 1/14/2026 10:59 AM, Xiaoyao Li wrote:
> On 1/14/2026 8:30 AM, Sagi Shahar wrote:
>> From: Vishal Annapurve <vannapurve@google.com>

How does the guest differentiate it from a retry due to pending events?
Will the guest retry immediately after returning back to the guest in this case?


>>
>> Signed-off-by: Vishal Annapurve <vannapurve@google.com>

---

## [4] Sean Christopherson — 2026-01-14
*Subject: Re: [PATCH] KVM: TDX: Allow userspace to return errors to guest for MAPGPA*

On Wed, Jan 14, 2026, Xiaoyao Li wrote:
> On 1/14/2026 8:30 AM, Sagi Shahar wrote:
> > From: Vishal Annapurve <vannapurve@google.com>

migration

> > Allow userspace to signal to TDX guests that the MAPGPA operation should
> > be retried the next time the guest is scheduled.

To Xiaoyao's point, changes like this either need new uAPI, or a detailed
explanation in the changelog of why such uAPI isn't deemed necessary.

> > Signed-off-by: Vishal Annapurve <vannapurve@google.com>
> > Co-developed-by: Sagi Shahar <sagis@google.com>

It's not incorrect, just potentially a breaking change.

> The -EINVAL will eventually be
> returned to userspace for the VCPU_RUN ioctl. It certainly breaks userspace.

It _might_ break userspace.  It certainly changes KVM's ABI, but if no userspace
actually utilizes the existing ABI, then userspace hasn't been broken.

And unless I'm missing something, QEMU _still_ doesn't set hypercall.ret.  E.g.
see this code in __tdx_map_gpa().

	/*
	 * In principle this should have been -KVM_ENOSYS, but userspace (QEMU <=9.2)
	 * assumed that vcpu->run->hypercall.ret is never changed by KVM and thus that
	 * it was always zero on KVM_EXIT_HYPERCALL.  Since KVM is now overwriting
	 * vcpu->run->hypercall.ret, ensuring that it is zero to not break QEMU.
	 */
	tdx->vcpu.run->hypercall.ret = 0;

AFAICT, QEMU kills the VM if anything goes wrong.

So while I initially had the exact same reaction of "this is a breaking change
and needs to be opt-in", we might actually be able to get away with just making
the change (assuming no other VMMs care, or are willing to change themselves).

> So it needs to be
> 

No, because assuming everything except -EBUSY translates to
TDVMCALL_STATUS_INVALID_OPERAND paints KVM back into the same corner its already
in.  What I care most about is eliminating KVM's assumption that a non-zero
hypercall.ret means TDVMCALL_STATUS_INVALID_OPERAND.

For the new ABI, I see two options:

 1. Translate -errno as done in this patch.
 2. Propagate hypercall.ret directly to the TDVMCALL return code, i.e. let
    userspace set any return code it wants.

#1 has the downside of needing KVM changes and new uAPI every time a new return
code is supported.

#2 has the downside of preventing KVM from establishing its own ABI around the
return code, and making the return code vendor specific.  E.g. if KVM ever wanted
to do something in response to -EBUSY beyond propagating the error to the guest,
then we can't reasonably do that with #2.

Whatever we do, I want to change snp_complete_psc_msr() and snp_complete_one_psc()
in the same patch, so that whatever ABI we establish is common to TDX and SNP.

See also https://lore.kernel.org/all/Zn8YM-s0TRUk-6T-@google.com.

> But I'm not sure if such change breaks the userspace ABI that if needs to be
> opted-in.

---

## [5] Sean Christopherson — 2026-01-14
*Subject: Re: [PATCH] KVM: TDX: Allow userspace to return errors to guest for MAPGPA*

+Mike

On Wed, Jan 14, 2026, Sean Christopherson wrote:
> On Wed, Jan 14, 2026, Xiaoyao Li wrote:
> > On 1/14/2026 8:30 AM, Sagi Shahar wrote:

Aha!  Finally.  I *knew* we had discussed this more recently.  The SNP series to
add KVM_EXIT_SNP_REQ_CERTS uses a similar pattern.  Note its intentional use of
positive values, because that's what userspace sees in errno.  This code should
do the same.  Oh, and we need to choose between EAGAIN and EBUSY...

	switch (READ_ONCE(vcpu->run->snp_req_certs.ret)) {
	case 0:
		return snp_handle_guest_req(svm, control->exit_info_1,
					    control->exit_info_2);
	case ENOSPC:
		vcpu->arch.regs[VCPU_REGS_RBX] = vcpu->run->snp_req_certs.npages;
		return snp_req_certs_err(svm, SNP_GUEST_VMM_ERR_INVALID_LEN);
	case EAGAIN:
		return snp_req_certs_err(svm, SNP_GUEST_VMM_ERR_BUSY);
	case EIO:
		return snp_req_certs_err(svm, SNP_GUEST_VMM_ERR_GENERIC);
	default:
		break;
	}


https://lore.kernel.org/all/20260109231732.1160759-2-michael.roth@amd.com

---

## [6] Sagi Shahar — 2026-01-14
*Subject: Re: [PATCH] KVM: TDX: Allow userspace to return errors to guest for MAPGPA*

On Wed, Jan 14, 2026 at 9:57 AM Sean Christopherson <seanjc@google.com> wrote:
>
> On Wed, Jan 14, 2026, Xiaoyao Li wrote:

Is there a better source of truth for whether QEMU uses hypercall.ret
or just point to this comment in the commit message.

>
> > So it needs to be

---

## [7] Sagi Shahar — 2026-01-14
*Subject: Re: [PATCH] KVM: TDX: Allow userspace to return errors to guest for MAPGPA*

On Wed, Jan 14, 2026 at 3:48 PM Sean Christopherson <seanjc@google.com> wrote:
>
> +Mike

I think EAGAIN makes more sense semantically in this case. So
something like this?

-               tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_INVALID_OPERAND);
+               if (vcpu->run->hypercall.ret == EAGAIN)
+                       tdvmcall_set_return_code(vcpu, TDVMCALL_STATUS_RETRY);
+               else if (vcpu->run->hypercall.ret == EINVAL)
+                       tdvmcall_set_return_code(vcpu,
TDVMCALL_STATUS_INVALID_OPERAND);
+               else
+                       return -EINVAL;
+

>
> https://lore.kernel.org/all/20260109231732.1160759-2-michael.roth@amd.com

---

## [8] Xiaoyao Li — 2026-01-15
*Subject: Re: [PATCH] KVM: TDX: Allow userspace to return errors to guest for
 MAPGPA*

On 1/15/2026 9:21 AM, Sagi Shahar wrote:
> On Wed, Jan 14, 2026 at 9:57 AM Sean Christopherson <seanjc@google.com> wrote:
>>

No version of QEMU touches hypercall.ret, from the source code.

I suggest not mentioning the comment, because it only tells QEMU expects 
vcpu->run->hypercall.ret to be 0 on KVM_EXIT_HYPERCALL. What matters is 
QEMU never sets vcpu->run->hypercall.ret to a non-zero value after 
handling KVM_EXIT_HYPERCALL. I think you can just describe the fact that 
QEMU never set vcpu->run->hypercall.ret to a non-zero value in the 
commit message.

---

## [9] Sean Christopherson — 2026-01-15
*Subject: Re: [PATCH] KVM: TDX: Allow userspace to return errors to guest for MAPGPA*

On Thu, Jan 15, 2026, Xiaoyao Li wrote:
> On 1/15/2026 9:21 AM, Sagi Shahar wrote:
> > On Wed, Jan 14, 2026 at 9:57 AM Sean Christopherson <seanjc@google.com> wrote:

+1.  We can't _guarantee_ changing the behavior won't break userspace, e.g. in
theory, someone could be running a fork of QEMU in production that explicitly
sets hypercall.ret to some weird value.  Or someone could be running a VMM we
don't even know about.  I.e. there is no single source of truth, all we can do
is explain why we have high confidence that the ABI change won't break anything.

---
