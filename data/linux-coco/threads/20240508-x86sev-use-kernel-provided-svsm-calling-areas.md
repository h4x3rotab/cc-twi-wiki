---
title: '[PATCH v4 05/15] x86/sev: Use kernel provided SVSM Calling Areas'
date: 2024-05-08
last_reply: 2024-05-31
message_count: 32
participants: ['Borislav Petkov', 'Tom Lendacky']
---

## [1] Borislav Petkov — 2024-05-08

On Wed, Apr 24, 2024 at 10:58:01AM -0500, Tom Lendacky wrote:
> +static int __svsm_msr_protocol(struct svsm_call *call)

All those protocol functions need a verb in the name:

__svsm_do_msr_protocol
__svsm_do_ghcb_protocol

or something slicker than the silly "do".

> +{
> +	u64 val, resp;

Do that assignment above, at declaration.

> +	issue_svsm_call(call, &pending);
> +

The MSR SVSM protocol is supposed to restore the MSR? A comment pls.

> +
> +	if (pending)

s/ != 0//

> +		return -EINVAL;
> +

rax_out is u64, your function returns int because of the negative
values. But then it'll truncate the u64 in the success case.

> +}
> +

As above.

> +	issue_svsm_call(call, &pending);
> +

As above.

> +}
> +

s/A flag used //

and above.

> +	       * used instead of the boot SVSM CA.
> +	       *

Why the "__" prefix?

I gon't see a svsm_get_caa() variant...

> +{
> +	return sev_cfg.cas_initialized ? this_cpu_read(svsm_caa)

svsm_issue_protocol_call() or whatnot...

Btw, can all this svsm guest gunk live simply in a separate file? Or is
it going to need a lot of sev.c stuff exported through an internal.h
header?

Either that or prefix all SVSM handling functions with "svsm_" so that
there's at least some visibility which is which.

> +{
> +	struct ghcb_state state;

Uff, conditional locking.

What's wrong with using local_irq_save/local_irq_restore?

> +
> +	if (sev_cfg.ghcbs_initialized)

...

> @@ -2095,6 +2188,50 @@ static __head struct cc_blob_sev_info *find_cc_blob(struct boot_params *bp)
>  	return cc_info;

svsm_setup

> +{
> +	struct svsm_call call = {};

You set up stuff above and now you bail out?

Judging by setup_svsm_ca() you don't really need that vmpl var but you
can check

	if (!boot_svsm_caa)
		return;

to determine whether a SVSM was detected.

> +
> +	/*

s/the //

> +	 * RIP-relative addressing.
> +	 */

Huh, setup_svsm_ca() already assigned those...

>  bool __head snp_init(struct boot_params *bp)
>  {

Are we doing that now?

---

## [2] Tom Lendacky — 2024-05-08

On 5/8/24 03:05, Borislav Petkov wrote:
> On Wed, Apr 24, 2024 at 10:58:01AM -0500, Tom Lendacky wrote:
>> +static int __svsm_msr_protocol(struct svsm_call *call)

ok, maybe __perform_svsm_msr_protocol or such.

> 
>> +{

Ok

> 
>> +	issue_svsm_call(call, &pending);

Ok, I'll put it above the read where val is assigned.

> 
>> +

Ok

> 
>> +		return -EINVAL;

I'll fix that and return 0 here and check the rax_out value on the return.

> 
>> +}

Yep

> 
>> +	issue_svsm_call(call, &pending);

Ditto.

> 
>> +}

Sure

> 
>> +	       * used instead of the boot SVSM CA.

There probably was at one point and I missed removing the "__" prefix. 
I'll take care of that.

> 
>> +{

There's quite a bit of interaction so I'll make sure to prefix everything.

> 
>> +{

The paravirt versions of local_irq_save and local_irq_restore can't be 
used as early as this routine is called.

> 
>> +

Yep

> 
>> +{

setup_svsm_ca() is what sets the vmpl variable. So nothing will have 
been setup if the VMPL is zero, in which case we don't continue on.

> 
> Judging by setup_svsm_ca() you don't really need that vmpl var but you

Yes, but the vmpl var will be used for attestation requests, sysfs, etc.

> 
>> +

hmmm... CA is Calling Area, so

   "get the Calling Area address using RIP-relative"
   "get Calling Area address using RIP-relative..."

The first one sound more correct to me.

> 
>> +	 * RIP-relative addressing.

setup_svsm_ca() assigned the ones from the secrets page. The kernel now 
switches to using its own CA.

> 
>>   bool __head snp_init(struct boot_params *bp)

Looks like a leftover change... will remove it.

Thanks,
Tom

>

---

## [3] Tom Lendacky — 2024-05-08

On 5/8/24 14:13, Tom Lendacky wrote:
> On 5/8/24 03:05, Borislav Petkov wrote:
>> On Wed, Apr 24, 2024 at 10:58:01AM -0500, Tom Lendacky wrote:

>>> diff --git a/arch/x86/mm/mem_encrypt_amd.c 
>>> b/arch/x86/mm/mem_encrypt_amd.c

Ah, there is a change in there. I guess I misunderstood your question 
because the change was cutoff from the reply. Anyway, yes, as far as I 
know, we should be doing that.

Thanks,
Tom

> 
> Thanks,

---

## [4] Borislav Petkov — 2024-05-08

On Wed, May 08, 2024 at 02:13:17PM -0500, Tom Lendacky wrote:
> ok, maybe __perform_svsm_msr_protocol or such.

We'll bikeshed it in the coming weeks.

> There's quite a bit of interaction so I'll make sure to prefix everything.

Ack.

> The paravirt versions of local_irq_save and local_irq_restore can't be used
> as early as this routine is called.

tglx says you should do native_local_irq_save()/.._restore() helpers
just like the arch_local_irq_save()/..._restore() ones but use only
native_ functions without the paravirt gunk.

In a prepatch pls.

> > > +	struct svsm_call call = {};
> > > +	int ret;

You still assign

        /*
         * The CA is identity mapped when this routine is called, both by the
         * decompressor code and the early kernel code.
         */
        boot_svsm_caa = (struct svsm_ca *)caa;
        boot_svsm_caa_pa = caa;

regardless of vmpl.

I think you should assign those only when vmpl != 0.

Otherwise the code is confusing.

> > Judging by setup_svsm_ca() you don't really need that vmpl var but you
> > can check

I guess that comes later in the patchset...

> > Huh, setup_svsm_ca() already assigned those...
> 

Comment pls.

Thx.

---

## [5] Tom Lendacky — 2024-05-08

On 5/8/24 14:58, Borislav Petkov wrote:
> On Wed, May 08, 2024 at 02:13:17PM -0500, Tom Lendacky wrote:
>> ok, maybe __perform_svsm_msr_protocol or such.

:)

> 
>> There's quite a bit of interaction so I'll make sure to prefix everything.

Will do.

> 
>>>> +	struct svsm_call call = {};

If we're not running at VMPL0 (based on the RMPADJUST check) and if the 
SVSM doesn't advertise a non-zero VMPL value, we will self-terminate. So 
those values are only set if we are not running at VMPL0 and the SVSM 
has provided a non-zero value to us.

I'm going to turn the function into a bool function so that the call 
becomes:

	if (!svsm_setup_caa(cc_info))
		return;

> 
> I think you should assign those only when vmpl != 0.

I do. I think you're missing the RMPADJUST check that causes the 
function to return early if we're running at VMPL0.

> 
> Otherwise the code is confusing.

There's a block comment above it all, but maybe it isn't clear enough. 
I'll rework it.

Thanks,
Tom

> 
> Thx.

---

## [6] Borislav Petkov — 2024-05-17
*Subject: Re: [PATCH v4 04/15] x86/sev: Check for the presence of an SVSM in
 the SNP Secrets page*

On Thu, May 02, 2024 at 10:29:02AM -0500, Tom Lendacky wrote:
> PAGE_ALIGNED and IS_ALIGNED are from two separate header files (mm.h and
> align.h) which seems like a lot of extra changes for just one check.

No, pls put them in a single shared/mm.h header. And no, those are not
a lot of extra changes - those are changes which are moving the code in
the right direction and we do them sooner rather than later, otherwise
they'd pile up and we'll never be able to find time to do them - sev.c
movement attempt case-in-point.

> Not sure I agree. I'd prefer to keep the comment here because it is
> specific to this rmpadjust() call. See below.

Just don't replicate some versions of the same comment all over the
place. Do one big comment which explains which RMPADJUST has to do with
VMPL levels - perhaps over the insn - and then refer to it from the
other places after adding the specific explanations for them.

> Right. Not sure about the "cannot", more like "must not." The specification
> states that the guest should run at a VMPL other than 0. If an SVSM starts

Yeah, well, you do terminate the guest if it is running at VMPL 0 *in*
the presence of a SVSM so it is a "must not". Ok.

---

## [7] Borislav Petkov — 2024-05-17

On Wed, May 08, 2024 at 03:09:02PM -0500, Tom Lendacky wrote:
> If we're not running at VMPL0 (based on the RMPADJUST check) and if the SVSM
> doesn't advertise a non-zero VMPL value, we will self-terminate. So those

Sure, I guess I'm misled by the

	if (bla)
		sev_es_terminate()

which is a function call but I need to read its name to realize that
after that point we're either terminated or we have all the stuff
required to run on a SVSM.

> I do. I think you're missing the RMPADJUST check that causes the function to
> return early if we're running at VMPL0.

Yap.

---

## [8] Tom Lendacky — 2024-05-20
*Subject: Re: [PATCH v4 04/15] x86/sev: Check for the presence of an SVSM in
 the SNP Secrets page*

On 5/17/24 10:58, Borislav Petkov wrote:
> On Thu, May 02, 2024 at 10:29:02AM -0500, Tom Lendacky wrote:
>> PAGE_ALIGNED and IS_ALIGNED are from two separate header files (mm.h and

So this will be a new shared directory in the top level include 
directory (as PAGE_ALIGNED is defined in include/linux/mm.h), not just 
in the arch/x86/include directory like the others (io.h, msr.h and 
tdx.h). Is that what you want?

Thanks,
Tom

> 
>> Not sure I agree. I'd prefer to keep the comment here because it is

---

## [9] Borislav Petkov — 2024-05-22
*Subject: Re: [PATCH v4 04/15] x86/sev: Check for the presence of an SVSM in
 the SNP Secrets page*

On Mon, May 20, 2024 at 08:57:43AM -0500, Tom Lendacky wrote:
> So this will be a new shared directory in the top level include directory
> (as PAGE_ALIGNED is defined in include/linux/mm.h), not just in the

You can actually do this - it is a lot easier and still clean:

diff --git a/arch/x86/boot/compressed/sev.c b/arch/x86/boot/compressed/sev.c
index cb771b380a6b..5ee53a7a060e 100644
--- a/arch/x86/boot/compressed/sev.c
+++ b/arch/x86/boot/compressed/sev.c
@@ -12,7 +12,6 @@
  */
 #include "misc.h"
 
-#include <linux/mm.h>
 #include <asm/bootparam.h>
 #include <asm/pgtable_types.h>
 #include <asm/sev.h>
diff --git a/arch/x86/kernel/sev-shared.c b/arch/x86/kernel/sev-shared.c
index 46ea4e5e118a..bd4bbb30ef0c 100644
--- a/arch/x86/kernel/sev-shared.c
+++ b/arch/x86/kernel/sev-shared.c
@@ -1329,7 +1329,12 @@ static void __head setup_svsm_ca(const struct cc_blob_sev_info *cc_info)
 	vmpl = secrets_page->svsm_guest_vmpl;
 
 	caa = secrets_page->svsm_caa;
-	if (!PAGE_ALIGNED(caa))
+
+	/*
+	 * Open-code PAGE_ALIGNED() to avoid pulling in the world and
+	 * more by including linux/mm.h.
+	 */
+	if (caa & (PAGE_SIZE - 1))
 		sev_es_terminate(SEV_TERM_SET_LINUX, GHCB_TERM_SVSM_CAA);
 
 	/*

---

## [10] Tom Lendacky — 2024-05-22
*Subject: Re: [PATCH v4 04/15] x86/sev: Check for the presence of an SVSM in
 the SNP Secrets page*

On 5/22/24 10:27, Borislav Petkov wrote:
> On Mon, May 20, 2024 at 08:57:43AM -0500, Tom Lendacky wrote:
>> So this will be a new shared directory in the top level include directory

Or what I originally proposed:

	if (!IS_ALIGNED(caa, PAGE_SIZE))

Which also works without including mm.h.

Thanks,
Tom

>   		sev_es_terminate(SEV_TERM_SET_LINUX, GHCB_TERM_SVSM_CAA);
>

---

## [11] Borislav Petkov — 2024-05-22
*Subject: Re: [PATCH v4 04/15] x86/sev: Check for the presence of an SVSM in
 the SNP Secrets page*

On Wed, May 22, 2024 at 11:15:28AM -0500, Tom Lendacky wrote:
> Or what I originally proposed:
> 

It works because of the same nasty reason:

$ make arch/x86/boot/compressed/sev.i
  CALL    scripts/checksyscalls.sh
  DESCEND objtool
  INSTALL libsubcmd_headers
  CPP     arch/x86/boot/compressed/sev.i
$ grep align.h arch/x86/boot/compressed/sev.i
# 1 "./include/linux/align.h" 1

The include hell pulls in that linux/ namespace header into the
decompressor. Which it should not to.

So no, please use the open-coded thing. I probably should start
untangling the decompressor slowly and do small sets because otherwise
this'll never get split properly.

;-\

---

## [12] Borislav Petkov — 2024-05-22
*Subject: Re: [PATCH v4 06/15] x86/sev: Perform PVALIDATE using the SVSM when
 not at VMPL0*

On Wed, Apr 24, 2024 at 10:58:02AM -0500, Tom Lendacky wrote:
> The PVALIDATE instruction can only be performed at VMPL0. An SVSM will
> be present when running at VMPL1 or a lower privilege level.

s/when running/when the guest itself is running/

> When an SVSM is present, use the SVSM_CORE_PVALIDATE call to perform
> memory validation instead of issuing the PVALIDATE instruction directly.

This all talks more about what this is doing and I'm missing the "why".

It sounds like when you're running a SVSM under the guest, you cannot
use PVALIDATE but the SVSM should do it for you. And you should start
with that.

The rest/details should be visible from the diff.

> Signed-off-by: Tom Lendacky <thomas.lendacky@amd.com>
> ---

Function name needs a verb.

> +{
> +	struct ghcb *ghcb;

That is a bool so put a "false" in there.

>  	/* Issue VMGEXIT to change the page state in RMP table. */
>  	sev_es_wr_ghcb_msr(GHCB_MSR_PSC_REQ_GFN(paddr >> PAGE_SHIFT, op));

Ditto, but "true".

>  void snp_set_page_private(unsigned long paddr)
> @@ -256,6 +284,15 @@ void sev_es_shutdown_ghcb(void)

s/The boot_ghcb value /This is used/

> +	 * protocol or the GHCB shared page to perform a GHCB request. Since the
> +	 * GHCB page is being changed to encrypted, it can't be used to perform

Are we being lazy again? :)

So I know the below is bigger than two silly forward declarations but
forward declarations are a sign that our source code placement is
lacking and if we keep piling on that, it'll become a mess soon. And
guess who gets to mop up after y'all who don't have time to do it
because you have to enable features? :-\

So in order to avoid that, we'll re-position it to where we think it'll
be better going forward.

Btw, this is the second time, at least, where I think that that
sev-shared.c thing is starting to become more of a nuisance than a code
savings thing but I don't have a better idea for it yet.

So let's extend that ifdeffery at the top which provides things which
are called the same but defined differently depending on whether we're
in the decompressor or kernel proper.

IOW, something like this, ontop:

diff --git a/arch/x86/boot/compressed/sev.c b/arch/x86/boot/compressed/sev.c
index 32a1e98ffaa9..9d89fc67574b 100644
--- a/arch/x86/boot/compressed/sev.c
+++ b/arch/x86/boot/compressed/sev.c
@@ -130,16 +130,6 @@ static bool fault_in_kernel_space(unsigned long address)
 /* Include code for early handlers */
 #include "../../kernel/sev-shared.c"
 
-static struct svsm_ca *__svsm_get_caa(void)
-{
-	return boot_svsm_caa;
-}
-
-static u64 __svsm_get_caa_pa(void)
-{
-	return boot_svsm_caa_pa;
-}
-
 static int svsm_protocol(struct svsm_call *call)
 {
 	struct ghcb *ghcb;
diff --git a/arch/x86/kernel/sev-shared.c b/arch/x86/kernel/sev-shared.c
index b415b10a0823..b4f1fd780925 100644
--- a/arch/x86/kernel/sev-shared.c
+++ b/arch/x86/kernel/sev-shared.c
@@ -11,20 +11,6 @@
 
 #include <asm/setup_data.h>
 
-#ifndef __BOOT_COMPRESSED
-#define error(v)			pr_err(v)
-#define has_cpuflag(f)			boot_cpu_has(f)
-#define sev_printk(fmt, ...)		printk(fmt, ##__VA_ARGS__)
-#define sev_printk_rtl(fmt, ...)	printk_ratelimited(fmt, ##__VA_ARGS__)
-#else
-#undef WARN
-#define WARN(condition, format...)	(!!(condition))
-#define sev_printk(fmt, ...)
-#define sev_printk_rtl(fmt, ...)
-#undef vc_forward_exception
-#define vc_forward_exception(c)		panic("SNP: Hypervisor requested exception\n")
-#endif
-
 /*
  * SVSM related information:
  *   When running under an SVSM, the VMPL that Linux is executing at must be
@@ -40,8 +26,47 @@ static u8 vmpl __ro_after_init;
 static struct svsm_ca *boot_svsm_caa __ro_after_init;
 static u64 boot_svsm_caa_pa __ro_after_init;
 
-static struct svsm_ca *__svsm_get_caa(void);
-static u64 __svsm_get_caa_pa(void);
+#ifdef __BOOT_COMPRESSED
+
+#undef WARN
+#define WARN(condition, format...)	(!!(condition))
+#define sev_printk(fmt, ...)
+#define sev_printk_rtl(fmt, ...)
+#undef vc_forward_exception
+#define vc_forward_exception(c)		panic("SNP: Hypervisor requested exception\n")
+
+static struct svsm_ca *__svsm_get_caa(void)
+{
+	return boot_svsm_caa;
+}
+
+static u64 __svsm_get_caa_pa(void)
+{
+	return boot_svsm_caa_pa;
+}
+
+#else /* __BOOT_COMPRESSED */
+
+#define error(v)			pr_err(v)
+#define has_cpuflag(f)			boot_cpu_has(f)
+#define sev_printk(fmt, ...)		printk(fmt, ##__VA_ARGS__)
+#define sev_printk_rtl(fmt, ...)	printk_ratelimited(fmt, ##__VA_ARGS__)
+
+static DEFINE_PER_CPU(struct svsm_ca *, svsm_caa);
+
+static struct svsm_ca *__svsm_get_caa(void)
+{
+	return sev_cfg.cas_initialized ? this_cpu_read(svsm_caa)
+				       : boot_svsm_caa;
+}
+
+static u64 __svsm_get_caa_pa(void)
+{
+	return sev_cfg.cas_initialized ? this_cpu_read(svsm_caa_pa)
+				       : boot_svsm_caa_pa;
+}
+
+#endif /* __BOOT_COMPRESSED */
 
 /* I/O parameters for CPUID-related helpers */
 struct cpuid_leaf {
diff --git a/arch/x86/kernel/sev.c b/arch/x86/kernel/sev.c
index bb6455ff45a2..db895a7a9401 100644
--- a/arch/x86/kernel/sev.c
+++ b/arch/x86/kernel/sev.c
@@ -138,7 +138,6 @@ static struct svsm_ca boot_svsm_ca_page __aligned(PAGE_SIZE);
 
 static DEFINE_PER_CPU(struct sev_es_runtime_data*, runtime_data);
 static DEFINE_PER_CPU(struct sev_es_save_area *, sev_vmsa);
-static DEFINE_PER_CPU(struct svsm_ca *, svsm_caa);
 static DEFINE_PER_CPU(u64, svsm_caa_pa);
 
 struct sev_config {
@@ -616,18 +615,6 @@ static __always_inline void vc_forward_exception(struct es_em_ctxt *ctxt)
 /* Include code shared with pre-decompression boot stage */
 #include "sev-shared.c"
 
-static struct svsm_ca *__svsm_get_caa(void)
-{
-	return sev_cfg.cas_initialized ? this_cpu_read(svsm_caa)
-				       : boot_svsm_caa;
-}
-
-static u64 __svsm_get_caa_pa(void)
-{
-	return sev_cfg.cas_initialized ? this_cpu_read(svsm_caa_pa)
-				       : boot_svsm_caa_pa;
-}
-
 static noinstr void __sev_put_ghcb(struct ghcb_state *state)
 {
 	struct sev_es_runtime_data *data;

> +
>  /* I/O parameters for CPUID-related helpers */

You get the idea...

>  static bool __init sev_es_check_cpu_features(void)
>  {

There are those silly wrappers again. Kill it pls.

> +
> +static int svsm_pvalidate_4k_page(unsigned long paddr, bool validate)

Will there ever be a pvalidate_2M_page?

If so, then you need to redesign this to have a lower-level helper

	__svsm_pvalidate_page(... ,size, );

and the 4K and 2M things call it.

> +{
> +	struct svsm_pvalidate_call *pvalidate_call;

Too long:

	struct svsm_pvalidate_call *pvl_call;

> +	struct svsm_call call = {};

I guess this needs to be

	struct svsm_call svsm_call = {};

so that you know what kind of call it is - you have two.

> +	u64 pvalidate_call_pa;
> +	unsigned long flags;

Yeah, this'll change.

> +	call.caa = __svsm_get_caa();
> +

That's almost a page worth of data, we don't zero it. How sensitive
would this be if the SVSM sees some old data?

Or we trust the SVSM and all is good?

> +	pvalidate_call_pa = __svsm_get_caa_pa() + offsetof(struct svsm_ca, svsm_buffer);
> +

	if (vmpl)
		ret = svsm_pvalidate_4k_page(paddr, validate);
	else
		ret = pvalidate(vaddr, RMP_PG_SIZE_4K, validate);

No need for silly wrappers.

> +
> +	if (ret) {

shorten to "pvl_call" or so.

> +	struct svsm_pvalidate_entry *pe;

See, like this. :-P

> +	unsigned int call_count, i;
> +	struct svsm_call call = {};

As above.

> +	/* Calculate how many entries the CA buffer can hold */
> +	call_count = sizeof(call.caa->svsm_buffer);

Or you simply memset the whole thing and be safe.

> +	for (i = 0; i <= desc->hdr.end_entry; i++) {
> +		e = &desc->entries[i];

You did that above before the loop. Looks weird doing it again.

> +			for (; pfn <= pfn_end; pfn++) {
> +				pe = &pvalidate_call->entry[pvalidate_call->entries];

I have no clue what's going on in this function. Sounds like it needs
splitting. And commenting too. Like the loop body should be something
like svsm_pvalidate_entry() or so.

And then that second loop wants to be a separate function too as it is
calling the SVSM protocol again.

> +
> +		if (ret != SVSM_SUCCESS) {

And here it is again. If anything, splitting and comments are needed
here at least.

...

Thx.

---

## [13] Tom Lendacky — 2024-05-22
*Subject: Re: [PATCH v4 06/15] x86/sev: Perform PVALIDATE using the SVSM when
 not at VMPL0*

On 5/22/24 13:24, Borislav Petkov wrote:
> On Wed, Apr 24, 2024 at 10:58:02AM -0500, Tom Lendacky wrote:
>> The PVALIDATE instruction can only be performed at VMPL0. An SVSM will

It's sort of there in the first two paragraphs. I'll re-word it.

> 
> It sounds like when you're running a SVSM under the guest, you cannot

Yep, taken care of based on an earlier patch.

> 
>> +{

Ok

> 
>>   	/* Issue VMGEXIT to change the page state in RMP table. */

Ok

> 
>>   void snp_set_page_private(unsigned long paddr)

Ok

> 
>> +	 * protocol or the GHCB shared page to perform a GHCB request. Since the

I'll do a pre-patch that moves and reverses the __BOOT_COMPRESSED ifdef 
and then re-apply and adjust the patches based on this.

> 
>>   static bool __init sev_es_check_cpu_features(void)

Done.

> 
>> +

Not really. There is a multi page state change request structure that 
can be a mix of page sizes and will operate in large groups by looping 
through the entries.

> 
> If so, then you need to redesign this to have a lower-level helper

Sure.

> 
>> +	struct svsm_call call = {};

Ok.

> 
>> +	u64 pvalidate_call_pa;

Right.

> 
>> +	call.caa = __svsm_get_caa();

Correct. The SVSM can look at all of the guest memory anyway.

> 
>> +	pvalidate_call_pa = __svsm_get_caa_pa() + offsetof(struct svsm_ca, svsm_buffer);

Right, changing that from previous comment. But are you also asking that 
the if / else style be used?

> 
>> +

Ok

> 
>> +	struct svsm_pvalidate_entry *pe;

Yep.

> 
>> +	/* Calculate how many entries the CA buffer can hold */

We could, but that is clearing a 4K page each time... and the SVSM will 
still rely on the entries and next values.

> 
>> +	for (i = 0; i <= desc->hdr.end_entry; i++) {

It's because we have to break down the 2MB page into multiple 4K calls 
now. So we start over and enter 512 4K entries.

> 
>> +			for (; pfn <= pfn_end; pfn++) {

Sure, I'll add more comments or expand the comment above.

> 
> And then that second loop wants to be a separate function too as it is

That's because you can only pass a certain number of entries to the SVSM 
to handle at one time. If the kernel is in the process of validating, 
say, 1,000 entries, but the CA can only hold 511 at a time, then after 
it reaches the 511th entry, the SVSM must be called. Upon return, the 
kernel resets the CA area and builds up the entries in there again, 
calling the SVSM again when the area is again full or we reach the last 
entry to be validated.

I'll add more detail in the comments.

Thanks,
Tom

> 
> ...

---

## [14] Borislav Petkov — 2024-05-27
*Subject: Re: [PATCH v4 06/15] x86/sev: Perform PVALIDATE using the SVSM when
 not at VMPL0*

On Wed, May 22, 2024 at 04:14:54PM -0500, Tom Lendacky wrote:
> Right, changing that from previous comment. But are you also asking that the
> if / else style be used?

Yeah, please. It is trivial and thus more readable this way.

> Sure, I'll add more comments or expand the comment above.

Yes, and pls split it into helpers. Those bunch of nested loops are
kinda begging to be separate function helpers.

> That's because you can only pass a certain number of entries to the SVSM to
> handle at one time. If the kernel is in the process of validating, say,

Yeah, that "portioning" must be explained there.

Thx.

---

## [15] Borislav Petkov — 2024-05-27
*Subject: Re: [PATCH v4 07/15] x86/sev: Use the SVSM to create a vCPU when not
 in VMPL0*

On Wed, Apr 24, 2024 at 10:58:03AM -0500, Tom Lendacky wrote:
> -static int snp_set_vmsa(void *va, bool vmsa)
> +static int base_snp_set_vmsa(void *va, bool vmsa)

s/base_/__/

The svsm_-prefixed ones are already a good enough distinction...

>  {
>  	u64 attrs;
								  ^^^^^^^^^^^

bool create_vmsa or so, to denote what this arg means.

> +{
> +	struct svsm_call call = {};

Why do you even need helpers if you're not going to use them somewhere
else? Just put the whole logic inside snp_set_vmsa().

> +}
> +

	/* If an SVSM is present, the SVSM per-CPU CAA will be !NULL. */

Shorter.

---

## [16] Borislav Petkov — 2024-05-27
*Subject: Re: [PATCH v4 08/15] x86/sev: Provide SVSM discovery support*

On Wed, Apr 24, 2024 at 10:58:04AM -0500, Tom Lendacky wrote:
> The SVSM specification documents an alternative method of discovery for
> the SVSM using a reserved CPUID bit and a reserved MSR.

Yes, and all your code places where you do

	if (vmpl)

to check whether the guest is running over a SVSM should do the CPUID
check. We should not be hardcoding the VMPL level to mean a SVSM is
present.

> 
> For the CPUID support, the SNP CPUID table is updated to set bit 28 of

s/is updated/update the.../

> the EAX register of the 0x8000001f leaf when an SVSM is present. This bit
> has been reserved for use in this capacity.

X86_FEATURE_SVSM is better right?

And then we might even want to show it in /proc/cpuinfo here to really
say that we're running over a SVSM as that might be useful info. Think
alternate injection support for one.

>  /* AMD-defined Extended Feature 2 EAX, CPUID level 0x80000021 (EAX), word 20 */
>  #define X86_FEATURE_NO_NESTED_DATA_BP	(20*32+ 0) /* "" No Nested Data Breakpoints */

No need for that helper. And you can reuse the exit_info_1 assignment.
Diff ontop:

diff --git a/arch/x86/kernel/sev.c b/arch/x86/kernel/sev.c
index 40eb547d0d6c..7a248d66227e 100644
--- a/arch/x86/kernel/sev.c
+++ b/arch/x86/kernel/sev.c
@@ -1326,31 +1326,25 @@ int __init sev_es_efi_map_ghcbs(pgd_t *pgd)
 	return 0;
 }
 
-static enum es_result vc_handle_svsm_caa_msr(struct es_em_ctxt *ctxt)
-{
-	struct pt_regs *regs = ctxt->regs;
-
-	/* Writes to the SVSM CAA msr are ignored */
-	if (ctxt->insn.opcode.bytes[1] == 0x30)
-		return ES_OK;
-
-	regs->ax = lower_32_bits(this_cpu_read(svsm_caa_pa));
-	regs->dx = upper_32_bits(this_cpu_read(svsm_caa_pa));
-
-	return ES_OK;
-}
-
 static enum es_result vc_handle_msr(struct ghcb *ghcb, struct es_em_ctxt *ctxt)
 {
 	struct pt_regs *regs = ctxt->regs;
 	enum es_result ret;
 	u64 exit_info_1;
 
-	if (regs->cx == MSR_SVSM_CAA)
-		return vc_handle_svsm_caa_msr(ctxt);
-
 	/* Is it a WRMSR? */
-	exit_info_1 = (ctxt->insn.opcode.bytes[1] == 0x30) ? 1 : 0;
+	exit_info_1 = !!(ctxt->insn.opcode.bytes[1] == 0x30);
+
+	if (regs->cx == MSR_SVSM_CAA) {
+		/* Writes to the SVSM CAA msr are ignored */
+		if (exit_info_1)
+			return ES_OK;
+
+		regs->ax = lower_32_bits(this_cpu_read(svsm_caa_pa));
+		regs->dx = upper_32_bits(this_cpu_read(svsm_caa_pa));
+
+		return ES_OK;
+	}
 
 	ghcb_set_rcx(ghcb, regs->cx);
 	if (exit_info_1) {

---

## [17] Borislav Petkov — 2024-05-27
*Subject: Re: [PATCH v4 09/15] x86/sev: Provide guest VMPL level to userspace*

On Wed, Apr 24, 2024 at 10:58:05AM -0500, Tom Lendacky wrote:
> Requesting an attestation report from userspace involves providing the
> VMPL level for the report. Currently any value from 0-3 is valid because

So what is the use case here: you create the attestation report *on* the
running guest and as part of that, the script which does that should do

cat /sys/.../sev/vmpl

?

But then sev-guest does some VMPL including into some report:

struct snp_report_req {
        /* user data that should be included in the report */
        __u8 user_data[SNP_REPORT_USER_DATA_SIZE];

        /* The vmpl level to be included in the report */
        __u32 vmpl;

Why do you need this and can't use sev-guest?

> +static int __init sev_sysfs_init(void)
> +{

In the main hierarchy?!

This is a x86 CPU thing, so if anything, it should be under
/sys/devices/system/cpu/

---

## [18] Tom Lendacky — 2024-05-28
*Subject: Re: [PATCH v4 07/15] x86/sev: Use the SVSM to create a vCPU when not
 in VMPL0*

On 5/27/24 07:33, Borislav Petkov wrote:
> On Wed, Apr 24, 2024 at 10:58:03AM -0500, Tom Lendacky wrote:
>> -static int snp_set_vmsa(void *va, bool vmsa)

Ok.

> 
> The svsm_-prefixed ones are already a good enough distinction...

Ok. I'll change it on the original function, too.

> 
>> +{

I just think it's easier to follow, with specific functions for the 
situation and less indentation. But if you want, I can put it all in one 
function.

> 
>> +}

Yep.

Thanks,
Tom

>

---

## [19] Tom Lendacky — 2024-05-28
*Subject: Re: [PATCH v4 08/15] x86/sev: Provide SVSM discovery support*

On 5/27/24 08:10, Borislav Petkov wrote:
> On Wed, Apr 24, 2024 at 10:58:04AM -0500, Tom Lendacky wrote:
>> The SVSM specification documents an alternative method of discovery for

The alternative method is really meant for things like UEFI runtime 
services (which uses the kernels #VC handler), not the kernel directly.

Some of those checks have to be made very early, I'll see if it is 
feasible to rely on the CPUID check / cpu_feature_enabled() support.

We can separate out SVSM vs VMPL, but if the kernel isn't running at 
VMPL0 then it requires that an SVSM be present.

> 
>>

Ok.

> 
>> the EAX register of the 0x8000001f leaf when an SVSM is present. This bit

Yep, will do.

> 
>>   /* AMD-defined Extended Feature 2 EAX, CPUID level 0x80000021 (EAX), word 20 */

I'll incorporate this, but probably won't change the way exit_info_1 is 
assigned.

Thanks,
Tom

> 
> diff --git a/arch/x86/kernel/sev.c b/arch/x86/kernel/sev.c

---

## [20] Tom Lendacky — 2024-05-28
*Subject: Re: [PATCH v4 09/15] x86/sev: Provide guest VMPL level to userspace*

On 5/27/24 08:51, Borislav Petkov wrote:
> On Wed, Apr 24, 2024 at 10:58:05AM -0500, Tom Lendacky wrote:
>> Requesting an attestation report from userspace involves providing the

The vmpl value is input from user-space.

The SNP spec allows the VMPL that is put in the attestation report to be 
numerically equal to or higher than the current VMPL (which is 
determined based on the VMPCK key that is used). So this is to let 
userspace know that it shouldn't request a value numerically smaller 
than what is reported in sysfs in order to avoid failure of the request.

> 
>> +static int __init sev_sysfs_init(void)

I can move it there. Or what about creating a coco folder under 
/sys/kernel/? This would then create /sys/kernel/coco/sev/?

Thanks,
Tom

>

---

## [21] Borislav Petkov — 2024-05-30
*Subject: Re: [PATCH v4 09/15] x86/sev: Provide guest VMPL level to userspace*

On May 28, 2024 11:08:35 PM GMT+02:00, Tom Lendacky <thomas.lendacky@amd.com> wrote:
>I can move it there. Or what about creating a coco folder under /sys/kernel/? This would then create /sys/kernel/coco/sev/?
>

Sysfs hierarchy is special - can't just add stuff willy nilly. This doc hints at that:

https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/Documentation/filesystems/sysfs.rst

And then those things get documented here:

https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/Documentation/ABI

and supported forever and ever until the end of time.

So the usage needs to be precisely documented and weighed whether we really need it...

Thx.

---

## [22] Borislav Petkov — 2024-05-31
*Subject: Re: [PATCH v4 07/15] x86/sev: Use the SVSM to create a vCPU when not
 in VMPL0*

On Tue, May 28, 2024 at 03:28:28PM -0500, Tom Lendacky wrote:
> I just think it's easier to follow, with specific functions for the
> situation and less indentation. But if you want, I can put it all in one

Well, if the function were huge and hard to read sure, but right now it
is simple and with single indentation level. There's the other side of
having too many small helpers, leading into not seeing the flow. The
logic we should follow is: if the function is big and fat and has too
many indentation levels, you split into smaller functions.

The "Functions" section in Documentation/process/coding-style.rst has
some blurb on the matter.

---

## [23] Borislav Petkov — 2024-05-31
*Subject: Re: [PATCH v4 08/15] x86/sev: Provide SVSM discovery support*

On Tue, May 28, 2024 at 03:57:10PM -0500, Tom Lendacky wrote:
> The alternative method is really meant for things like UEFI runtime services
> (which uses the kernels #VC handler), not the kernel directly.

Put that in the commit message.

> We can separate out SVSM vs VMPL, but if the kernel isn't running at VMPL0
> then it requires that an SVSM be present.

Ok, I guess the two things are identical.

> I'll incorporate this, but probably won't change the way exit_info_1 is
> assigned.

Oh, but we love our '!!' construct:

git grep -E '\s!![^!]' *.[ch] | wc -l
7776

At least so many, my pattern is not precise.

---

## [24] Borislav Petkov — 2024-05-31
*Subject: Re: [PATCH v4 10/15] virt: sev-guest: Choose the VMPCK key based on
 executing VMPL*

On Wed, Apr 24, 2024 at 10:58:06AM -0500, Tom Lendacky wrote:
> +int snp_get_vmpl(void)
> +{

The vmpl doesn't change after init, right?

If so, you can make that vmpl variable __ro_after_init and drop yet
another parrotting accessor.

> -static u32 vmpck_id;
> -module_param(vmpck_id, uint, 0444);

Can the driver figure out the vmpck_id from the kernel directly instead
of having to supply it with a module param?

This is yet another silly module param which you have to go and engineer
into the loading and have to know what you're doing.

If you can automate that, then it is a win-win thing.

Thx.

---

## [25] Borislav Petkov — 2024-05-31
*Subject: Re: [PATCH v4 14/15] x86/sev: Extend the config-fs attestation
 support for an SVSM*

On Wed, Apr 24, 2024 at 10:58:10AM -0500, Tom Lendacky wrote:
> +/*
> + * The SVSM Attestation related structures

"svsm_loc" should be enough.

> +	u64 pa;
> +	u32 len;

Can we shorten all "attestion" to "atst" or "attest"?

> +	struct svsm_location_entry report_buffer;
> +	struct svsm_location_entry nonce;

report_buf;
nonce;
manifest_buf;
certs_buf;

Please shorten all those.

> +	/* For attesting a single service */
> +	u8 service_guid[16];

manifest_ver;

> +	u8 rsvd[4];
> +};

...

> +static void update_attestation_input(struct svsm_call *call, struct svsm_attestation_call *input)
> +{

"propagate"

> +	if (call->rcx_out != call->rcx)
> +		input->manifest_buffer.len = call->rcx_out;

This looks like BIOS code. The only thing that's missing is the
CamelCase. :-)

int snp_issue_svsm_attest_req(u64 call_id, struct svsm_attest_call *input_call)

Now that's more like it!

> +{
> +	struct svsm_attestation_call *attest_call;

	struct svsm_attest_call *atst_call;

> +	struct svsm_call call = {};
> +	unsigned long flags;

...

> +static int sev_svsm_report_new(struct tsm_report *report, void *data)
> +{

Prose. Shorter pls.

> +	struct svsm_attestation_call attest_call = {};
> +	struct tsm_desc *desc = &report->desc;

...

---

## [26] Borislav Petkov — 2024-05-31
*Subject: Re: [PATCH v4 15/15] x86/sev: Allow non-VMPL0 execution when an SVSM
 is present*

On Wed, Apr 24, 2024 at 10:58:11AM -0500, Tom Lendacky wrote:
> @@ -624,8 +626,12 @@ void sev_enable(struct boot_params *bp)
>  		 * modifies permission bits, it is still ok to do so currently because Linux

Let's make that more readable:

diff --git a/arch/x86/boot/compressed/sev.c b/arch/x86/boot/compressed/sev.c
index fb1e60165cd1..157f749faba0 100644
--- a/arch/x86/boot/compressed/sev.c
+++ b/arch/x86/boot/compressed/sev.c
@@ -610,8 +610,10 @@ void sev_enable(struct boot_params *bp)
 	 * features.
 	 */
 	if (sev_status & MSR_AMD64_SEV_SNP_ENABLED) {
-		u64 hv_features = get_hv_features();
+		u64 hv_features;
+		int rmpadj_ret;
 
+		hv_features = get_hv_features();
 		if (!(hv_features & GHCB_HV_FT_SNP))
 			sev_es_terminate(SEV_TERM_SET_GEN, GHCB_SNP_UNSUPPORTED);
 
@@ -626,11 +628,15 @@ void sev_enable(struct boot_params *bp)
 		 * modifies permission bits, it is still ok to do so currently because Linux
 		 * SNP guests running at VMPL0 only run at VMPL0, so VMPL1 or higher
 		 * permission mask changes are a don't-care.
-		 *
+		 */
+		rmpadj_ret = rmpadjust((unsigned long)&boot_ghcb_page, RMP_PG_SIZE_4K, 1);
+
+		/*
 		 * Running at VMPL0 is not required if an SVSM is present and the hypervisor
 		 * supports the required SVSM GHCB events.
 		 */
-		if (rmpadjust((unsigned long)&boot_ghcb_page, RMP_PG_SIZE_4K, 1) &&
+
+		if (rmpadj_ret &&
 		    !(vmpl && (hv_features & GHCB_HV_FT_SNP_MULTI_VMPL)))
 			sev_es_terminate(SEV_TERM_SET_LINUX, GHCB_TERM_NOT_VMPL0);
 	}

> -static int __init report_cpuid_table(void)
> +static void __init report_cpuid_table(void)

Zap one more silly helper:

diff --git a/arch/x86/kernel/sev.c b/arch/x86/kernel/sev.c
index 7955c024d5d7..ff5a32b0b21c 100644
--- a/arch/x86/kernel/sev.c
+++ b/arch/x86/kernel/sev.c
@@ -2356,32 +2356,23 @@ static void dump_cpuid_table(void)
  * sort of indicator, and there's not really any other good place to do it,
  * so do it here.
  */
-static void __init report_cpuid_table(void)
+static int __init report_snp_info(void)
 {
 	const struct snp_cpuid_table *cpuid_table = snp_cpuid_get_table();
 
 	if (!cpuid_table->count)
-		return;
+		return 0;
 
 	pr_info("Using SNP CPUID table, %d entries present.\n",
 		cpuid_table->count);
 
 	if (sev_cfg.debug)
 		dump_cpuid_table();
-}
 
-static void __init report_vmpl_level(void)
-{
 	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
-		return;
+		return 0;
 
 	pr_info("SNP running at VMPL%u.\n", vmpl);
-}
-
-static int __init report_snp_info(void)
-{
-	report_vmpl_level();
-	report_cpuid_table();
 
 	return 0;
 }

---

## [27] Tom Lendacky — 2024-05-31
*Subject: Re: [PATCH v4 10/15] virt: sev-guest: Choose the VMPCK key based on
 executing VMPL*

On 5/31/24 07:55, Borislav Petkov wrote:
> On Wed, Apr 24, 2024 at 10:58:06AM -0500, Tom Lendacky wrote:
>> +int snp_get_vmpl(void)

It already is __ro_after_init.

> another parrotting accessor.

The sev-guest driver needs to access it. Given it is a driver/module, I 
created the accessor rather than mark the variable EXPORT_SYMBOL_GPL(). 
Your call, I'm fine with either.

> 
>> -static u32 vmpck_id;

Yes, the driver can and does figure it out. However, this module parameter 
was added in the off chance the default VMPCK gets wiped. Then you can 
reload the driver and use a different (less privileged) VMPCK.

Thanks,
Tom

> 
> This is yet another silly module param which you have to go and engineer

---

## [28] Tom Lendacky — 2024-05-31
*Subject: Re: [PATCH v4 14/15] x86/sev: Extend the config-fs attestation
 support for an SVSM*

On 5/31/24 08:16, Borislav Petkov wrote:
> On Wed, Apr 24, 2024 at 10:58:10AM -0500, Tom Lendacky wrote:
>> +/*

Ok

> 
>> +	u64 pa;

Will shorten to attest.

> 
>> +	struct svsm_location_entry report_buffer;

Ok.

> 
>> +	/* For attesting a single service */

Yep.

> 
>> +	u8 rsvd[4];

Fixed.

> 
>> +	if (call->rcx_out != call->rcx)

Ok.

> 
>> +{

Ok, I'll use 'ac'

> 
>> +	struct svsm_call call = {};

Ok.

Thanks,
Tom

> 
>> +	struct svsm_attestation_call attest_call = {};

---

## [29] Borislav Petkov — 2024-05-31
*Subject: Re: [PATCH v4 10/15] virt: sev-guest: Choose the VMPCK key based on
 executing VMPL*

On Fri, May 31, 2024 at 01:36:06PM -0500, Tom Lendacky wrote:
> The sev-guest driver needs to access it. Given it is a driver/module, I
> created the accessor rather than mark the variable EXPORT_SYMBOL_GPL(). Your

Yeah, if the variable doesn't change after init, then you don't really
need an accessor.

> Yes, the driver can and does figure it out. However, this module parameter
> was added in the off chance the default VMPCK gets wiped. Then you can

Is that what the text over snp_disable_vmpck() is alluding to?

Or where are we documenting this intended use?

Thx.

---

## [30] Tom Lendacky — 2024-05-31
*Subject: Re: [PATCH v4 15/15] x86/sev: Allow non-VMPL0 execution when an SVSM
 is present*

On 5/31/24 09:54, Borislav Petkov wrote:
> On Wed, Apr 24, 2024 at 10:58:11AM -0500, Tom Lendacky wrote:
>> @@ -624,8 +626,12 @@ void sev_enable(struct boot_params *bp)

Will do.

> 
> diff --git a/arch/x86/boot/compressed/sev.c b/arch/x86/boot/compressed/sev.c

But I'll probably just call this 'ret'.

>   
> +		hv_features = get_hv_features();

Well you can't return in this case, just not report/dump the CPUID info. 
So I'll remove the helpers and adjust accordingly.

Thanks,
Tom

>   
>   	pr_info("Using SNP CPUID table, %d entries present.\n",

---

## [31] Tom Lendacky — 2024-05-31
*Subject: Re: [PATCH v4 10/15] virt: sev-guest: Choose the VMPCK key based on
 executing VMPL*

On 5/31/24 14:03, Borislav Petkov wrote:
> On Fri, May 31, 2024 at 01:36:06PM -0500, Tom Lendacky wrote:
>> The sev-guest driver needs to access it. Given it is a driver/module, I

Yes, I believe so.

> 
> Or where are we documenting this intended use?

It probably should have been documented above the module parameter itself 
and/or in the sev-guest documentation. Those can be done as part of this 
patch or separate, whichever is preferred.

Thanks,
Tom

> 
> Thx.

---

## [32] Borislav Petkov — 2024-05-31
*Subject: Re: [PATCH v4 10/15] virt: sev-guest: Choose the VMPCK key based on
 executing VMPL*

On Fri, May 31, 2024 at 02:34:37PM -0500, Tom Lendacky wrote:
> It probably should have been documented above the module parameter itself
> and/or in the sev-guest documentation. Those can be done as part of this

Yeah, pls do it while you're touching that area.

Thx.

---
