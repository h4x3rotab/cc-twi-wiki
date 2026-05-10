---
title: 'x86/tdx: Make seamcall/tdcall CET-compliant'
date: 2025-10-22
last_reply: 2025-10-22
message_count: 8
participants: ['Nikolay Borisov', 'Huang, Kai', 'Peter Zijlstra']
---

## [1] Nikolay Borisov — 2025-10-22

_seamcall/_ret/_saved_ret can be the target of indirect calls via
sc_retry_prerr/__seamcall_dirty_cache so on machines with CET enabled
such call chains result in a  splat and a BUG():

Missing ENDBR: __seamcall+0x0/0x50
------------[ cut here ]------------
kernel BUG at arch/x86/kernel/cet.c:132!
Oops: invalid opcode: 0000 [#1] SMP NOPTI
CPU: 195 UID: 0 PID: 3525 Comm: (udev-worker) Tainted: G                   n 6.12.0-160000.3.gccf23ce-default #1 PREEMPT(voluntary) SLFO-1.2 (unreleased) c9419bf0caf542825c59d4f407ef13fb3c33bc31
Tainted: [n]=NO_SUPPORT
Hardware name: Intel Corporation D50DNP/D50DNP, BIOS SE5C741.86B.01.02.0002.2408050237 08/05/2024
RIP: 0010:exc_control_protection+0x2c4/0x2d0
Code: d8 b9 09 00 00 00 48 8b 93 80 00 00 00 be 80 00 00 00 48 c7 c7 e5 1c a2 bd e8 c8 4a 34 ff 80 a3 8a 00 00 00 fb e9 11 fe ff ff <0f> 0b 66 2e 0f 1f 84 00 00 00 00 00 90 90 90 90 90 90 90 90 90 90
RSP: 0018:ff6bb6927112f988 EFLAGS: 00010002
RAX: 0000000000000022 RBX: ff6bb6927112f9b8 RCX: 0000000000000000
RDX: 0000000000000000 RSI: ff474944fafa6bc0 RDI: ff474944fafa6bc0
RBP: 0000000000000000 R08: 0000000000000000 R09: ff6bb6927112f778
R10: 0000000000000003 R11: ff474985fbd87e28 R12: 0000000000000003
R13: 0000000000000000 R14: 0000000000000000 R15: 0000000000000000
FS:  00007f3b43ac3900(0000) GS:ff474944faf80000(0000) knlGS:0000000000000000
CS:  0010 DS: 0000 ES: 0000 CR0: 0000000080050033
CR2: 00007f3b419ea000 CR3: 000000c0db9c6006 CR4: 0000000000f73ef0
PKRU: 55555554
Call Trace:
 <TASK>
 ? __die_body.cold+0x14/0x20
 ? die+0x2e/0x50
 ? do_trap+0xca/0x110
 ? do_error_trap+0x65/0x80
 ? exc_control_protection+0x2c4/0x2d0
 ? exc_invalid_op+0x50/0x70
 ? exc_control_protection+0x2c4/0x2d0
 ? asm_exc_invalid_op+0x1a/0x20
 ? exc_control_protection+0x2c4/0x2d0
 ? exc_control_protection+0x280/0x2d0
 asm_exc_control_protection+0x26/0x30
RIP: 0010:__seamcall+0x0/0x50
Code: 44 00 00 bf 07 00 00 00 e8 7d df cb 00 84 c0 74 02 0f 09 c3 cc cc cc cc 66 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 <55> 48 89 f8 48 8b 0e 48 8b 56 08 4c 8b 46 10 4c 8b 4e 18 4c 8b 56
RSP: 0018:ff6bb6927112fa68 EFLAGS: 00010283
RAX: ffffffffbc4c21a0 RBX: ff4749061045b200 RCX: 0000000000000005
RDX: ff6bb6927112fa78 RSI: ff6bb6927112fa78 RDI: 000000000000002d
RBP: 000000000000000a R08: 0000001f7d200000 R09: 0000000080000000
R10: 00b8b77a00000000 R11: 0000000000000400 R12: 8000020300000000
R13: 0000000000000010 R14: 0000000000000000 R15: 0000000000000005
 ? __pfx___seamcall+0x10/0x10
 do_seamcall+0x1a/0x40
 config_tdx_module.constprop.0+0x10a/0x197
 tdx_enable.cold+0x508/0x7e4
 tdx_bringup+0x1c1/0x1280 [kvm_intel f93f40ca63d984c168979eef9c8c2c660b2fd468]
 vt_init+0x1a/0x60 [kvm_intel f93f40ca63d984c168979eef9c8c2c660b2fd468]
 ? __pfx_vt_init+0x10/0x10 [kvm_intel f93f40ca63d984c168979eef9c8c2c660b2fd468]
 do_one_initcall+0x45/0x2f0
 do_init_module+0x90/0x250
 __do_sys_init_module+0x183/0x1c0
 do_syscall_64+0x7d/0x160
 ? __vm_munmap+0xc4/0x160
 ? syscall_exit_to_user_mode+0x32/0x1b0
 ? do_syscall_64+0x89/0x160
 ? sched_balance_trigger+0x66/0x360
 ? __count_memcg_events+0x53/0xf0
 ? handle_mm_fault+0xb9/0x2e0
 ? do_flush_tlb_all+0xe/0x20
 ? __flush_smp_call_function_queue+0x96/0x420
 ? __irq_exit_rcu+0x39/0xe0
 entry_SYSCALL_64_after_hwframe+0x76/0x7e
RIP: 0033:0x7f3b43d1a6be

Fix it by adding an ENBDR in TDX_MODULE_CALL macro to cover all
cases.

Signed-off-by: Nikolay Borisov <nik.borisov@suse.com>
---

The kernel this was observed is a SLE, however it contains the current upstream
TDX patches. And looking at the usptream code the problem persists there as well.

 arch/x86/virt/vmx/tdx/tdxcall.S | 1 +
 1 file changed, 1 insertion(+)

diff --git a/arch/x86/virt/vmx/tdx/tdxcall.S b/arch/x86/virt/vmx/tdx/tdxcall.S
index 016a2a1ec1d6..a2137cd7a669 100644
--- a/arch/x86/virt/vmx/tdx/tdxcall.S
+++ b/arch/x86/virt/vmx/tdx/tdxcall.S
@@ -43,6 +43,7 @@
  * TDH.EXPORT.MEM.
  */
 .macro TDX_MODULE_CALL host:req ret=0 saved=0
+	ENDBR
 	FRAME_BEGIN

 	/* Move Leaf ID to RAX */
--
2.51.1

---

## [2] Huang, Kai — 2025-10-22
*Subject: Re: [PATCH] x86/tdx: Make seamcall/tdcall CET-compliant*

On Wed, 2025-10-22 at 12:36 +0300, Nikolay Borisov wrote:
> _seamcall/_ret/_saved_ret can be the target of indirect calls via
> sc_retry_prerr/__seamcall_dirty_cache so on machines with CET enabled

[...]

> 
> Fix it by adding an ENBDR in TDX_MODULE_CALL macro to cover all

Does your kernel contain commit 0b3bc018e86af ("x86/virt/tdx: Avoid
indirect calls to TDX assembly functions")?

Some history about this commit:

I firstly found __seamcall*() could be indirect calls in some randconfig
when building the kernel, and tried to resolve it by (effectively) adding
ENDBR:

https://lore.kernel.org/lkml/20250604003848.13154-1-kai.huang@intel.com/

Peter suggested that we could use __always_inline to keep compiler from
generating indirect calls (which resulted in the above commit):

https://lore.kernel.org/lkml/20250605145914.GW39944@noisy.programming.kicks-ass.net/

I never met __tdcall*() could be indirect calls, though.

> 
>  arch/x86/virt/vmx/tdx/tdxcall.S | 1 +

---

## [3] Nikolay Borisov — 2025-10-22
*Subject: Re: [PATCH] x86/tdx: Make seamcall/tdcall CET-compliant*

On 10/22/25 13:14, Huang, Kai wrote:
> On Wed, 2025-10-22 at 12:36 +0300, Nikolay Borisov wrote:
>> _seamcall/_ret/_saved_ret can be the target of indirect calls via

Well, adding __always_inline to sc_retry means it will be inlined, but 
inside the body of the function you do have:

__seamcall_dirty_cache (which is also always inlined) but in it you 
have: return func(fn, args);

So you still have this indirect call, no ?


> 
>>

---

## [4] Peter Zijlstra — 2025-10-22
*Subject: Re: [PATCH] x86/tdx: Make seamcall/tdcall CET-compliant*

On Wed, Oct 22, 2025 at 01:21:25PM +0300, Nikolay Borisov wrote:
> 
> 

If you do always-inline, the function argument can be constant
propagated, and thus func will be a known function and not result in an
indirect call.

That is:

void foo(void);

__always_inline void bar(void (*func)(void))
{
	func();
}

void ponies(void)
{
	bar(&foo);
}

The compiler is clever enough to see that is a direct call of foo.

---

## [5] Nikolay Borisov — 2025-10-22
*Subject: Re: [PATCH] x86/tdx: Make seamcall/tdcall CET-compliant*

On 10/22/25 13:30, Peter Zijlstra wrote:
> On Wed, Oct 22, 2025 at 01:21:25PM +0300, Nikolay Borisov wrote:
>>

Thanks, I verified this, turns out we are using an earlier version of 
10df8607bf1a ("x86/virt/tdx: Mark memory cache state incoherent when 
making SEAMCALL")

Which contains do_seamcall instead of __seamcall_dirty_cache and that 
do_seamcall is missing always_inline so likely it's not being inlined.


Apologies for the noise in this case...


Though the fact that this __always_inline interacts with CET is somewhat 
subtle and not very evident from the changelogs.

---

## [6] Peter Zijlstra — 2025-10-22
*Subject: Re: [PATCH] x86/tdx: Make seamcall/tdcall CET-compliant*

On Wed, Oct 22, 2025 at 01:48:11PM +0300, Nikolay Borisov wrote:
> > The compiler is clever enough to see that is a direct call of foo.
> 

0b3bc018e86a ("x86/virt/tdx: Avoid indirect calls to TDX assembly functions")

---

## [7] Nikolay Borisov — 2025-10-22
*Subject: Re: [PATCH] x86/tdx: Make seamcall/tdcall CET-compliant*

On 10/22/25 13:51, Peter Zijlstra wrote:
> On Wed, Oct 22, 2025 at 01:48:11PM +0300, Nikolay Borisov wrote:
>>> The compiler is clever enough to see that is a direct call of foo.

We have that, but as it turns out it's not sufficient, we need 
__seamcall_dirty_cache to also be __always_inline as it also has an 
indirect call in it.

> 
>

---

## [8] Peter Zijlstra — 2025-10-22
*Subject: Re: [PATCH] x86/tdx: Make seamcall/tdcall CET-compliant*

On Wed, Oct 22, 2025 at 02:10:45PM +0300, Nikolay Borisov wrote:
> 
> 

Right, so that commit does the __always_inline and explains why, and
then the other commit just copies the __always_inline.

---
