---
title: 'KVM: TDX: Allow in place TDX.PAGE.ADD'
date: 2025-11-05
last_reply: 2025-11-05
message_count: 1
participants: ['Ira Weiny']
---

## [1] Ira Weiny — 2025-11-05

As promised in the PUCK call today here is the patch I spoke of.  The
commit message is out of date.  I was building/testing this on top of
the old TDX selftest series.

This is untested but compiles on Linus upstream.

I looked through my notes and found that I was concerned with how to
force an unmap after conversion.  With what we discussed today I don't
think that will be an issue any longer.  The conversion to private prior
to TDX init should (could?) take care of that.  I'll have to look more
once the gmemm populate series and Michaels stuff is posted.

Finally, after Michaels lifting of GUP to gmem this should be unneeded.
But it shows that TDX will be fine.

<old commit message>

TDX.PAGE.ADD can convert a page in place with data.

With the addition of mmap and shared/private convertibility within
guest_memfd it is no longer necessary to provide source data pages from
which to copy data into an encrypted page.

Also some code, such as is in the selftests, do not require any specific
data be placed in test pages.  So one can skip the allocation of a
source page all together.

Allow source data pages to be specified as NULL and allow the TDX module
to encrypt the destination page in place.

Not-yet-signed-off-by: Ira Weiny <ira.weiny@intel.com>
---
Signed-off-by: Ira Weiny <ira.weiny@intel.com>
---
 arch/x86/kvm/vmx/tdx.c | 20 +++++++++++++-------
 1 file changed, 13 insertions(+), 7 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 0a49c863c811..8056d896f0ba 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -3181,11 +3181,15 @@ static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 	 * Get the source page if it has been faulted in. Return failure if the
 	 * source page has been swapped out or unmapped in primary memory.
 	 */
-	ret = get_user_pages_fast((unsigned long)src, 1, 0, &src_page);
-	if (ret < 0)
-		return ret;
-	if (ret != 1)
-		return -ENOMEM;
+	if (src) {
+		ret = get_user_pages_fast((unsigned long)src, 1, 0, &src_page);
+		if (ret < 0)
+			return ret;
+		if (ret != 1)
+			return -ENOMEM;
+	} else {
+		src_page = pfn_to_page(pfn);
+	}
 
 	ret = kvm_tdp_map_page(vcpu, gpa, error_code, &level);
 	if (ret < 0)
@@ -3228,7 +3232,8 @@ static int tdx_gmem_post_populate(struct kvm *kvm, gfn_t gfn, kvm_pfn_t pfn,
 	}
 
 out:
-	put_page(src_page);
+	if (src)
+		put_page(src_page);
 	return ret;
 }
 
@@ -3289,7 +3294,8 @@ static int tdx_vcpu_init_mem_region(struct kvm_vcpu *vcpu, struct kvm_tdx_cmd *c
 			break;
 		}
 
-		region.source_addr += PAGE_SIZE;
+		if (region.source_addr)
+			region.source_addr += PAGE_SIZE;
 		region.gpa += PAGE_SIZE;
 		region.nr_pages--;
 

---
base-commit: 17d85f33a83b84e7d36bc3356614ae06c90e7a08
change-id: 20251105-tdx-init-in-place-842496310dc5

Best regards,
--  
Ira Weiny <ira.weiny@intel.com>

---
