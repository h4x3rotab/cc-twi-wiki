---
title: 'MAINTAINERS: rectify file entries in TRUSTED SECURITY MODULE (TSM) INFRASTRUCTURE'
date: 2025-05-09
last_reply: 2025-05-13
message_count: 2
participants: ['Lukas Bulwahn', 'Dan Williams']
---

## [1] Lukas Bulwahn — 2025-05-09

From: Lukas Bulwahn <lukas.bulwahn@redhat.com>

Commit 7515f45c1652 ("coco/guest: Move shared guest CC infrastructure to
drivers/virt/coco/guest/") moves drivers/virt/coco/tsm.c to
drivers/virt/coco/guest/report.c, and adjusts the file entry in TRUSTED
SECURITY MODULE (TSM) INFRASTRUCTURE.

However, commit b9e22b35d459 ("tsm-mr: Add TVM Measurement Register
support") also touches that section, leading to some unintended state with
the two concurrent changes of these two commits, i.e., entry
drivers/virt/coco/tsm*.c is still in place, where it should have been
deleted. Note that the existing file entry drivers/virt/coco/tsm*.c is not
needed, as the files are after their renaming in drivers/virt/coco/guest/,
and there is already a file entry in this section for that directory.

Rectify this section appropriately.

Further, commit f6953f1f9ec4 ("tsm-mr: Add tsm-mr sample code") adds
example code to samples/tsm-mr/, but in the MAINTAINERS section, it refers
to the non-existing directory samples/tsm/. So, rectify that file entry to
the existing intended location as well.

Signed-off-by: Lukas Bulwahn <lukas.bulwahn@redhat.com>
---
 MAINTAINERS | 3 +--
 1 file changed, 1 insertion(+), 2 deletions(-)

diff --git a/MAINTAINERS b/MAINTAINERS
index 6dbdf02d6b0c..e8a21d6f89f8 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -24991,9 +24991,8 @@ S:	Maintained
 F:	Documentation/ABI/testing/configfs-tsm-report
 F:	Documentation/driver-api/coco/
 F:	drivers/virt/coco/guest/
-F:	drivers/virt/coco/tsm*.c
 F:	include/linux/tsm*.h
-F:	samples/tsm/
+F:	samples/tsm-mr/
 
 TRUSTED SERVICES TEE DRIVER
 M:	Balint Dobszay <balint.dobszay@arm.com>

---

## [2] Dan Williams — 2025-05-13
*Subject: Re: [PATCH] MAINTAINERS: rectify file entries in TRUSTED SECURITY
 MODULE (TSM) INFRASTRUCTURE*

Lukas Bulwahn wrote:
> From: Lukas Bulwahn <lukas.bulwahn@redhat.com>
> 

Thanks, Lukas!

I ended up redoing the merge with this fixup and crediting you there:

https://git.kernel.org/pub/scm/linux/kernel/git/devsec/tsm.git/commit/?h=next&id=15ff5d0e90bb

---
