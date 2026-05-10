---
title: 'x86/mm: fix lookup_address() to handle physical memory holes in direct mapping'
date: 2024-06-28
last_reply: 2024-07-02
message_count: 15
participants: ['Ashish Kalra', 'Edgecombe, Rick P', 'Tom Lendacky', 'Jürgen Groß']
---

## [1] Ashish Kalra — 2024-06-28

From: Ashish Kalra <ashish.kalra@amd.com>

lookup_address_in_pgd_attr() at pte level it is simply returning
pte_offset_kernel() and there does not seem to be a check for
returning NULL if pte_none().

Fix lookup_address_in_pgd_attr() to add check for pte_none()
after pte_offset_kernel() and return NULL if it is true.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/mm/pat/set_memory.c | 7 ++++++-
 1 file changed, 6 insertions(+), 1 deletion(-)

diff --git a/arch/x86/mm/pat/set_memory.c b/arch/x86/mm/pat/set_memory.c
index 443a97e515c0..be8b5bf3bc3f 100644
--- a/arch/x86/mm/pat/set_memory.c
+++ b/arch/x86/mm/pat/set_memory.c
@@ -672,6 +672,7 @@ pte_t *lookup_address_in_pgd_attr(pgd_t *pgd, unsigned long address,
 	p4d_t *p4d;
 	pud_t *pud;
 	pmd_t *pmd;
+	pte_t *pte;
 
 	*level = PG_LEVEL_256T;
 	*nx = false;
@@ -717,7 +718,11 @@ pte_t *lookup_address_in_pgd_attr(pgd_t *pgd, unsigned long address,
 	*nx |= pmd_flags(*pmd) & _PAGE_NX;
 	*rw &= pmd_flags(*pmd) & _PAGE_RW;
 
-	return pte_offset_kernel(pmd, address);
+	pte = pte_offset_kernel(pmd, address);
+	if (pte_none(*pte))
+		return NULL;
+
+	return pte;
 }
 
 /*

---

## [2] Edgecombe, Rick P — 2024-06-28
*Subject: Re: [PATCH] x86/mm: fix lookup_address() to handle physical memory
 holes in direct mapping*

On Fri, 2024-06-28 at 20:52 +0000, Ashish Kalra wrote:
> diff --git a/arch/x86/mm/pat/set_memory.c b/arch/x86/mm/pat/set_memory.c
> index 443a97e515c0..be8b5bf3bc3f 100644

The other levels check for pXX_none() before adjusting *level. Not sure what the
effect would be, but I think it should be the same behavior for all.

---

## [3] Kalra, Ashish — 2024-06-28
*Subject: Re: [PATCH] x86/mm: fix lookup_address() to handle physical memory
 holes in direct mapping*

On 6/28/2024 3:58 PM, Edgecombe, Rick P wrote:
> On Fri, 2024-06-28 at 20:52 +0000, Ashish Kalra wrote:
>> diff --git a/arch/x86/mm/pat/set_memory.c b/arch/x86/mm/pat/set_memory.c

If we are returning NULL, why should adjusting *level matter.

Thanks, Ashish

---

## [4] Tom Lendacky — 2024-06-28
*Subject: Re: [PATCH] x86/mm: fix lookup_address() to handle physical memory
 holes in direct mapping*

On 6/28/24 15:58, Edgecombe, Rick P wrote:
> On Fri, 2024-06-28 at 20:52 +0000, Ashish Kalra wrote:
>> diff --git a/arch/x86/mm/pat/set_memory.c b/arch/x86/mm/pat/set_memory.c

Agreed. It should follow the same logic as the previous checks.

It looks like the *nx and *rw should be updated, too, right? That seems to
be missing from the change that added them.

Thanks,
Tom

---

## [5] Edgecombe, Rick P — 2024-06-28
*Subject: Re: [PATCH] x86/mm: fix lookup_address() to handle physical memory
 holes in direct mapping*

On Fri, 2024-06-28 at 16:22 -0500, Kalra, Ashish wrote:
> > > @@ -717,7 +718,11 @@ pte_t *lookup_address_in_pgd_attr(pgd_t *pgd,
> > > unsigned

Well, I think symmetry is enough of a reason, but actually it should be ok.

I was looking at this diff compared to my working tree, but this tip commit
(which is about that scenario) makes it set *level before checking none for all
of them:
https://lore.kernel.org/lkml/171871930159.10875.16081839197437299007.tip-bot2@tip-bot2/

So sorry, nevermind.

---

## [6] Tom Lendacky — 2024-06-28
*Subject: Re: [PATCH] x86/mm: fix lookup_address() to handle physical memory
 holes in direct mapping*

On 6/28/24 16:33, Edgecombe, Rick P wrote:
> On Fri, 2024-06-28 at 16:22 -0500, Kalra, Ashish wrote:
>>>> @@ -717,7 +718,11 @@ pte_t *lookup_address_in_pgd_attr(pgd_t *pgd,

Ditto for me.

Thanks,
Tom

> (which is about that scenario) makes it set *level before checking none for all
> of them:

---

## [7] Jürgen Groß — 2024-06-29
*Subject: Re: [PATCH] x86/mm: fix lookup_address() to handle physical memory
 holes in direct mapping*

On 28.06.24 22:52, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Please have a look at the comment above lookup_address(). You should not
break the documented behavior without verifying that no caller is relying
on the current behavior. If this is fine, please update the comment.


Juergen

> 
> Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>

---

## [8] Tom Lendacky — 2024-06-29
*Subject: Re: [PATCH] x86/mm: fix lookup_address() to handle physical memory
 holes in direct mapping*

On 6/29/24 05:20, Jürgen Groß wrote:
> On 28.06.24 22:52, Ashish Kalra wrote:
>> From: Ashish Kalra <ashish.kalra@amd.com>

This brings up a point from my other reply. The comment says that it
returns "the effective NX and RW bits of all page table levels", but in
fact NX and RW are not updated for the PTE. Since the comment says all
page table levels, shouldn't they be updated with the PTE values, too?

Thanks,
Tom

> 
>

---

## [9] Jürgen Groß — 2024-06-29
*Subject: Re: [PATCH] x86/mm: fix lookup_address() to handle physical memory
 holes in direct mapping*

On 29.06.24 17:16, Tom Lendacky wrote:
> On 6/29/24 05:20, Jürgen Groß wrote:
>> On 28.06.24 22:52, Ashish Kalra wrote:

Hmm, the comment could need some clarifications.

It returns the effective NX and RW bits of the levels above the PTE. Reason is
that the function is used in case the NX/RW bits of a PTE are updated, so the
PTE settings are not always really important.


Juergen

---

## [10] Kalra, Ashish — 2024-07-01
*Subject: Re: [PATCH] x86/mm: fix lookup_address() to handle physical memory
 holes in direct mapping*

On 6/29/2024 5:20 AM, Jürgen Groß wrote:
> On 28.06.24 22:52, Ashish Kalra wrote:
>> From: Ashish Kalra <ashish.kalra@amd.com>
I don't get that, in this case the PTE does not exist, so as per the comments here lookup_address() should have returned NULL.

Thanks, Ashish

>
>>

---

## [11] Jürgen Groß — 2024-07-01
*Subject: Re: [PATCH] x86/mm: fix lookup_address() to handle physical memory
 holes in direct mapping*

On 01.07.24 19:57, Kalra, Ashish wrote:
> 
> On 6/29/2024 5:20 AM, Jürgen Groß wrote:

There is a PTE, but it is all 0.

There is no _valid_ PTE. No PTE would mean that the related PMD entry (or any
other higher level entry) is invalid.

Remember that the W^X checking needs to be performed _before_ a new PTE is
written.


Juergen

---

## [12] Kalra, Ashish — 2024-07-01
*Subject: Re: [PATCH] x86/mm: fix lookup_address() to handle physical memory
 holes in direct mapping*

On 7/1/2024 1:38 PM, Jürgen Groß wrote:
> On 01.07.24 19:57, Kalra, Ashish wrote:
>>

Then what is the caller supposed to do in this case ?

As the return from lookup_address() is non-NULL in this case, accessing it causes a fatal #PF.

Is the caller supposed to add the check for a valid PTE using pte_none(*pte) ?

Thanks, Ashish

>
> Remember that the W^X checking needs to be performed _before_ a new PTE is

---

## [13] Edgecombe, Rick P — 2024-07-01
*Subject: Re: [PATCH] x86/mm: fix lookup_address() to handle physical memory
 holes in direct mapping*

On Mon, 2024-07-01 at 13:59 -0500, Kalra, Ashish wrote:
> 
> Then what is the caller supposed to do in this case ?

I did a quick look at the callers, and some do their own check for pte_none().
But some don't. Some also assume the return can't be NULL.

Can you elaborate on your goal for this change? Just a cleanup?

---

## [14] Kalra, Ashish — 2024-07-01
*Subject: Re: [PATCH] x86/mm: fix lookup_address() to handle physical memory
 holes in direct mapping*

On 7/1/2024 2:13 PM, Edgecombe, Rick P wrote:
> On Mon, 2024-07-01 at 13:59 -0500, Kalra, Ashish wrote:
>> Then what is the caller supposed to do in this case ?

Hit this issue while implementing and testing SNP guest kexec.

So trying to understand if need a generic fix for this issue or do i need to add my own check for pte_none() ?

Thanks, Ashish

---

## [15] Jürgen Groß — 2024-07-02
*Subject: Re: [PATCH] x86/mm: fix lookup_address() to handle physical memory
 holes in direct mapping*

On 01.07.24 21:39, Kalra, Ashish wrote:
> 
> On 7/1/2024 2:13 PM, Edgecombe, Rick P wrote:

Please add a check for pte_none() after calling lookup_address().


Juergen

---
