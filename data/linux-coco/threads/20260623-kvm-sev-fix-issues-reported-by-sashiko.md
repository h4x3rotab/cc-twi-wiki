---
title: 'kvm: sev: Fix issues reported by Sashiko'
date: 2026-06-23
last_reply: 2026-06-26
message_count: 9
participants: ['Jörg Rödel', 'Sean Christopherson', 'Tom Lendacky']
---

## [1] Jörg Rödel — 2026-06-23

From: Joerg Roedel <joerg.roedel@amd.com>

Hi,

On the post of my direct-VMSA patch-set Sashiko reported a few real
pre-existing issues in the SEV-SNP launch_update code. This patch-set
addresses three of them:

	* Fix user-triggerable WARN_ON on LAUNCH_UPDATE path.

	* Check that CPUID pages are writable before writing error
	  information to it.

	* Fix kunmap_local() order.

Please review.

-Joerg

Joerg Roedel (4):
  kvm: sev: Fix user-space triggerable WARN_ON on snp_launch_update path
  kvm: sev: Unmap pages in correct order in sev_gmem_post_populate()
  KVM: guest_memfd: Add `write` parameter to kvm_gmem_populate()
  kvm: sev: Acquire a writeable page reference for CPUID pages

 arch/x86/kvm/svm/sev.c   | 15 +++++++++++++--
 arch/x86/kvm/vmx/tdx.c   |  2 +-
 include/linux/kvm_host.h |  4 +++-
 virt/kvm/guest_memfd.c   |  4 ++--
 4 files changed, 19 insertions(+), 6 deletions(-)

---

## [2] Jörg Rödel — 2026-06-23
*Subject: [PATCH 1/4] kvm: sev: Fix user-space triggerable WARN_ON on snp_launch_update path*

From: Joerg Roedel <joerg.roedel@amd.com>

Sashiko reported on an unrelated patch:

  [Severity: High]
  This is a pre-existing issue, but can a host userspace process trigger a
  kernel warning by passing a NULL user address (uaddr = 0) here?

  If params.uaddr is 0, src becomes NULL and passes the PAGE_ALIGNED(src)
  check. kvm_gmem_populate() skips fetching the user page and passes
  src_page = NULL to sev_gmem_post_populate().

  That function then unconditionally evaluates:

  WARN_ON_ONCE(sev_populate_args->type != KVM_SEV_SNP_PAGE_TYPE_ZERO &&
               !src_page)

  Since the type isn't ZERO, won't this allow an unprivileged user to spam
  the kernel log?

The assessment is correct, so check for this condition earlier in the
snp_launch_update() path to avoid the WARN_ON_ONCE.

Fixes: dee5a47cc7a45 ("KVM: SEV: Add KVM_SEV_SNP_LAUNCH_UPDATE command")
Signed-off-by: Joerg Roedel <joerg.roedel@amd.com>
---
 arch/x86/kvm/svm/sev.c | 7 +++++++
 1 file changed, 7 insertions(+)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 6c6a6d663e29..41dcba5180ca 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2438,6 +2438,13 @@ static int snp_launch_update(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	if (!PAGE_ALIGNED(src))
 		return -EINVAL;
 
+	/*
+	 * Make sure user-mode did not pass NULL as src with
+	 * type != KVM_SEV_SNP_PAGE_TYPE_ZERO.
+	 */
+	if (src == NULL && params.type != KVM_SEV_SNP_PAGE_TYPE_ZERO)
+		return -EINVAL;
+
 	npages = params.len / PAGE_SIZE;
 
 	/*

---

## [3] Jörg Rödel — 2026-06-23
*Subject: [PATCH 2/4] kvm: sev: Unmap pages in correct order in sev_gmem_post_populate()*

From: Joerg Roedel <joerg.roedel@amd.com>

The kmap_local() interface requires unmapping of pages in reverse
order of mapping.

Fixes: 2a62345b3052 ("KVM: guest_memfd: GUP source pages prior to populating guest memory")
Signed-off-by: Joerg Roedel <joerg.roedel@amd.com>
---
 arch/x86/kvm/svm/sev.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 41dcba5180ca..f09d15f68964 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2360,8 +2360,8 @@ static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 
 		memcpy(dst_vaddr, src_vaddr, PAGE_SIZE);
 
-		kunmap_local(src_vaddr);
 		kunmap_local(dst_vaddr);
+		kunmap_local(src_vaddr);
 	}
 
 	ret = rmp_make_private(pfn, gfn << PAGE_SHIFT, PG_LEVEL_4K,

---

## [4] Jörg Rödel — 2026-06-23
*Subject: [PATCH 3/4] KVM: guest_memfd: Add `write` parameter to kvm_gmem_populate()*

From: Joerg Roedel <joerg.roedel@amd.com>

The call-path of kvm_gmem_populate() might subsequently write to the
page provided by user-space. This is used to provide detailed error
information in case the page population failed.

But since kvm_gmem_populate() only acquires a read-only reference to
the user-space page via get_user_pages_fast(), the error information
might be written to a read-only page later on.

Add a parameter to kvm_gmem_populate() to optionally acquire a
writeable reference to the source page to make sure page permissions
can be enforced.

Signed-off-by: Joerg Roedel <joerg.roedel@amd.com>
---
 arch/x86/kvm/svm/sev.c   | 2 +-
 arch/x86/kvm/vmx/tdx.c   | 2 +-
 include/linux/kvm_host.h | 4 +++-
 virt/kvm/guest_memfd.c   | 4 ++--
 4 files changed, 7 insertions(+), 5 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index f09d15f68964..dab8109edf26 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2475,7 +2475,7 @@ static int snp_launch_update(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	sev_populate_args.sev_fd = argp->sev_fd;
 	sev_populate_args.type = params.type;
 
-	count = kvm_gmem_populate(kvm, params.gfn_start, src, npages,
+	count = kvm_gmem_populate(kvm, params.gfn_start, src, npages, 0,
 				  sev_gmem_post_populate, &sev_populate_args);
 	if (count < 0) {
 		argp->error = sev_populate_args.fw_error;
diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 04ce321ebdf3..46b1d84fddf2 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -3185,7 +3185,7 @@ static int tdx_vcpu_init_mem_region(struct kvm_vcpu *vcpu, struct kvm_tdx_cmd *c
 		};
 		gmem_ret = kvm_gmem_populate(kvm, gpa_to_gfn(region.gpa),
 					     u64_to_user_ptr(region.source_addr),
-					     1, tdx_gmem_post_populate, &arg);
+					     1, 0, tdx_gmem_post_populate, &arg);
 		if (gmem_ret < 0) {
 			ret = gmem_ret;
 			break;
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index 4c14aee1fb06..622c0b04d8c3 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -2581,6 +2581,8 @@ int kvm_arch_gmem_prepare(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn, int max_ord
  *       (passed to @post_populate, and incremented on each iteration
  *       if not NULL). Must be page-aligned.
  * @npages: number of pages to copy from userspace-buffer
+ * @write: user-space provided buffer must be writable. The function
+ *	 will acquire a writable reference when set to 1.
  * @post_populate: callback to issue for each gmem page that backs the GPA
  *                 range
  * @opaque: opaque data to pass to @post_populate callback
@@ -2597,7 +2599,7 @@ typedef int (*kvm_gmem_populate_cb)(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 				    struct page *page, void *opaque);
 
 long kvm_gmem_populate(struct kvm *kvm, gfn_t gfn, void __user *src, long npages,
-		       kvm_gmem_populate_cb post_populate, void *opaque);
+		       int write, kvm_gmem_populate_cb post_populate, void *opaque);
 #endif
 
 #ifdef CONFIG_HAVE_KVM_ARCH_GMEM_INVALIDATE
diff --git a/virt/kvm/guest_memfd.c b/virt/kvm/guest_memfd.c
index 69c9d6d546b2..7a245a402a1b 100644
--- a/virt/kvm/guest_memfd.c
+++ b/virt/kvm/guest_memfd.c
@@ -859,7 +859,7 @@ static long __kvm_gmem_populate(struct kvm *kvm, struct kvm_memory_slot *slot,
 }
 
 long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long npages,
-		       kvm_gmem_populate_cb post_populate, void *opaque)
+		       int write, kvm_gmem_populate_cb post_populate, void *opaque)
 {
 	struct kvm_memory_slot *slot;
 	int ret = 0;
@@ -893,7 +893,7 @@ long kvm_gmem_populate(struct kvm *kvm, gfn_t start_gfn, void __user *src, long
 		if (src) {
 			unsigned long uaddr = (unsigned long)src + i * PAGE_SIZE;
 
-			ret = get_user_pages_fast(uaddr, 1, 0, &src_page);
+			ret = get_user_pages_fast(uaddr, 1, write, &src_page);
 			if (ret < 0)
 				break;
 			if (ret != 1) {

---

## [5] Jörg Rödel — 2026-06-23
*Subject: [PATCH 4/4] kvm: sev: Acquire a writeable page reference for CPUID pages*

From: Joerg Roedel <joerg.roedel@amd.com>

When the PSP checks on a user-provided CPUID page fail KVM will write
back the detailed error information to the user-provided buffer.

Make sure this buffer is actually writable to not write the errors to
a read-only page.

Fixes: 2a62345b3052 ("KVM: guest_memfd: GUP source pages prior to populating guest memory")
Signed-off-by: Joerg Roedel <joerg.roedel@amd.com>
---
 arch/x86/kvm/svm/sev.c | 6 +++++-
 1 file changed, 5 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index dab8109edf26..5fd08d34be3f 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2415,6 +2415,7 @@ static int snp_launch_update(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	struct kvm_memory_slot *memslot;
 	long npages, count;
 	void __user *src;
+	int write;
 
 	if (!sev_snp_guest(kvm) || !sev->snp_context)
 		return -EINVAL;
@@ -2475,7 +2476,10 @@ static int snp_launch_update(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	sev_populate_args.sev_fd = argp->sev_fd;
 	sev_populate_args.type = params.type;
 
-	count = kvm_gmem_populate(kvm, params.gfn_start, src, npages, 0,
+	/* Acquire a write-reference for CPUID pages as kernel might write to it */
+	write = params.type == KVM_SEV_SNP_PAGE_TYPE_CPUID;
+
+	count = kvm_gmem_populate(kvm, params.gfn_start, src, npages, write,
 				  sev_gmem_post_populate, &sev_populate_args);
 	if (count < 0) {
 		argp->error = sev_populate_args.fw_error;

---

## [6] Sean Christopherson — 2026-06-23
*Subject: Re: [PATCH 3/4] KVM: guest_memfd: Add `write` parameter to kvm_gmem_populate()*

On Tue, Jun 23, 2026, Jörg Rödel wrote:
> From: Joerg Roedel <joerg.roedel@amd.com>
> 

Already fixed, commit f13e90059908 ("KVM: SEV: Pin source page for write when
adding CPUID data for SNP guest").

---

## [7] Sean Christopherson — 2026-06-23
*Subject: Re: [PATCH 1/4] kvm: sev: Fix user-space triggerable WARN_ON on
 snp_launch_update path*

Please capitalize the scope, i.e. "KVM: SEV:".

On Tue, Jun 23, 2026, Jörg Rödel wrote:
> From: Joerg Roedel <joerg.roedel@amd.com>
> 

Use Reported-by: + Closes to capture Sashiko's effecitve bug report instead of
copy+pasting the finding.  There's no reason to treat Sashiko any differently
than any other bot.

> The assessment is correct, so check for this condition earlier in the
> snp_launch_update() path to avoid the WARN_ON_ONCE.

Meh, that's pretty obvious from the code.

> +	 */
> +	if (src == NULL && params.type != KVM_SEV_SNP_PAGE_TYPE_ZERO)

I think I'd prefer this over checking for KVM_SEV_SNP_PAGE_TYPE_ZERO twice,
especially since the PAGE_ALIGNED() check for the NULL pointer case is rather
weird.

	if (params.type == KVM_SEV_SNP_PAGE_TYPE_ZERO)
		src = NULL;
	else if (!params.uaddr || !PAGE_ALIGNED(params.uaddr))
		return -EINVAL;
	else
		src = u64_to_user_ptr(params.uaddr);


> +		return -EINVAL;

Gah, we created quite the mess for ourselves.  TDX returns -EOPNOTSUPP instead
of -EINVAL, I guess as a placeholder for in-place conversion?  I don't care which
error code is returned, but I do want KVM to be consistent.

We should also adjust TDX to pre-check the source address, because checking only
in the post-populate flow subtly relies on tdx_vcpu_init_mem_region() returning
immediately on error.  If that weren't the case (ignoring for the moment that
continuing on would be nonsensical), KVM would advace the address by PAGE_SIZE
and suddenly a NULL userspace address becomes non-NULL.

I also think it makes sense to drop the WARN in sev_gmem_post_populate(), it's
completely redundant once this bug is fixed.

Ugh, and both SNP and TDX fail to account for tags, and fail to check for
striding into kernel space.  Which I suppose is fine, since gup() handles those
correctly.  And I don't see a strong argument for disallowing tagged addresses,
because unlike the userspace address for memslots, KVM doesn't keep the address
around long-term.

So over two patches, the below?  I can send a v2, I've already got changelogs
written (I was fiddling around with extracting and reusing kvm_set_memory_region()'s
checks on the userspace address+size, but as above, convinced myself that KVM
should continue to allow tagged addresses for SNP and TDX).

---
 arch/x86/kvm/svm/sev.c | 11 +++++------
 1 file changed, 5 insertions(+), 6 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 74fb15551e83..621a2eaa58f2 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2330,9 +2330,6 @@ static int sev_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 	int level;
 	int ret;
 
-	if (WARN_ON_ONCE(sev_populate_args->type != KVM_SEV_SNP_PAGE_TYPE_ZERO && !src_page))
-		return -EINVAL;
-
 	ret = snp_lookup_rmpentry((u64)pfn, &assigned, &level);
 	if (ret || assigned) {
 		pr_debug("%s: Failed to ensure GFN 0x%llx RMP entry is initial shared state, ret: %d assigned: %d\n",
@@ -2421,10 +2418,12 @@ static int snp_launch_update(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	     params.type != KVM_SEV_SNP_PAGE_TYPE_CPUID))
 		return -EINVAL;
 
-	src = params.type == KVM_SEV_SNP_PAGE_TYPE_ZERO ? NULL : u64_to_user_ptr(params.uaddr);
-
-	if (!PAGE_ALIGNED(src))
+	if (params.type == KVM_SEV_SNP_PAGE_TYPE_ZERO)
+		src = NULL;
+	else if (!params.uaddr || !PAGE_ALIGNED(params.uaddr))
 		return -EINVAL;
+	else
+		src = u64_to_user_ptr(params.uaddr);
 
 	npages = params.len / PAGE_SIZE;

---
 arch/x86/kvm/vmx/tdx.c | 7 ++-----
 1 file changed, 2 insertions(+), 5 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index ffe9d0db58c5..b0ec054732b9 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -3198,9 +3198,6 @@ static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 	if (KVM_BUG_ON(kvm_tdx->page_add_src, kvm))
 		return -EIO;
 
-	if (!src_page)
-		return -EOPNOTSUPP;
-
 	kvm_tdx->page_add_src = src_page;
 	ret = kvm_tdp_mmu_map_private_pfn(arg->vcpu, gfn, pfn);
 	kvm_tdx->page_add_src = NULL;
@@ -3247,8 +3244,8 @@ static int tdx_vcpu_init_mem_region(struct kvm_vcpu *vcpu, struct kvm_tdx_cmd *c
 	if (copy_from_user(&region, u64_to_user_ptr(cmd->data), sizeof(region)))
 		return -EFAULT;
 
-	if (!PAGE_ALIGNED(region.source_addr) || !PAGE_ALIGNED(region.gpa) ||
-	    !region.nr_pages ||
+	if (!PAGE_ALIGNED(region.source_addr) || !region.source_addr ||
+	    !PAGE_ALIGNED(region.gpa) || !region.nr_pages ||
 	    region.gpa + (region.nr_pages << PAGE_SHIFT) <= region.gpa ||
 	    !vt_is_tdx_private_gpa(kvm, region.gpa) ||
 	    !vt_is_tdx_private_gpa(kvm, region.gpa + (region.nr_pages << PAGE_SHIFT) - 1))
--

---

## [8] Tom Lendacky — 2026-06-26
*Subject: Re: [PATCH 1/4] kvm: sev: Fix user-space triggerable WARN_ON on
 snp_launch_update path*

On 6/23/26 04:15, Jörg Rödel wrote:
> From: Joerg Roedel <joerg.roedel@amd.com>
> 

It would only be one warning that is emitted, "spam the kernel log" sounds
like you could fill it with warnings. And I would say that the severity is
only "High" should the kernel be configured with PANIC_ON_WARN.

> 
> The assessment is correct, so check for this condition earlier in the

I'm not positive, but isn't it technically possible that the userspace
virtual address can be 0? In which case, should this be fixed in the
kvm_gmem_populate() API with maybe a new parameter that indicates whether
src is valid or not?

Thanks,
Tom

> 
> Fixes: dee5a47cc7a45 ("KVM: SEV: Add KVM_SEV_SNP_LAUNCH_UPDATE command")

---

## [9] Sean Christopherson — 2026-06-26
*Subject: Re: [PATCH 1/4] kvm: sev: Fix user-space triggerable WARN_ON on
 snp_launch_update path*

On Fri, Jun 26, 2026, Tom Lendacky wrote:
> On 6/23/26 04:15, Jörg Rödel wrote:
> > From: Joerg Roedel <joerg.roedel@amd.com>

Yeah, ignore any and all complaints about panic_on_warn=1 leading to DoS.

https://lore.kernel.org/all/CABgObfZJV5hU_7WoPWLRH3-EvKts%2BUBZOwtCXmwVZYJP8dDo2A@mail.gmail.com

> > The assessment is correct, so check for this condition earlier in the
> > snp_launch_update() path to avoid the WARN_ON_ONCE.

Yep, though it requires an explicit opt-in.

  config DEFAULT_MMAP_MIN_ADDR
	int "Low address space to protect from user allocation"
	depends on MMU
	default 4096
	help
	  This is the portion of low virtual memory which should be protected
	  from userspace allocation.  Keeping a user from writing to low pages
	  can help reduce the impact of kernel NULL pointer bugs.

	  For most ppc64 and x86 users with lots of address space
	  a value of 65536 is reasonable and should cause no problems.
	  On arm and other archs it should not be higher than 32768.
	  Programs which use vm86 functionality or have some need to map
	  this low address space will need CAP_SYS_RAWIO or disable this
	  protection by setting the value to 0.

	  This value can be changed after boot using the
	  /proc/sys/vm/mmap_min_addr tunable.

> In which case, should this be fixed in the kvm_gmem_populate() API with maybe
> a new parameter that indicates whether src is valid or not?

Nah, treating 0/NULL as invalid is perfectly acceptable.  It doesn't work today,
i.e. there's no risk of breaking anyone, and just because userspace can use VA=0
for other things doesn't mean KVM needs to support that for all of its uAPI
surface.

FWIW, I was initially opposed to using 0/NULL to mean "invalid", and even called
it ridiculous, but David W. convinced me that accepting 0/NULL in modern KVM uAPI
would violate the principle of least surprise.  So now I get to claim using NULL
to mean invalid as my own original idea ;-)

https://lore.kernel.org/all/a2cfad68277cae67791f07646c842672593a8dca.camel@infradead.org

---
