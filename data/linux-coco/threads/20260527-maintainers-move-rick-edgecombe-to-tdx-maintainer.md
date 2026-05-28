---
title: 'MAINTAINERS: Move Rick Edgecombe to TDX maintainer'
date: 2026-05-27
last_reply: 2026-05-27
message_count: 1
participants: ['Rick Edgecombe']
---

## [1] Rick Edgecombe — 2026-05-27

Per some offline discussion with Kiryl, he could use some help on the TDX
host side. I have worked on the TDX host side for the past few years
including wrangling the initial KVM support, and can help with this.

I am already listed as TDX reviewer. Move it to maintainer.

Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Cc: Kiryl Shutsemau <kas@kernel.org>
Cc: Dave Hansen <dave.hansen@linux.intel.com>
---
 MAINTAINERS | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/MAINTAINERS b/MAINTAINERS
index 882214b0e7db5..a838ff047d891 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -28943,8 +28943,8 @@ F:	arch/x86/kernel/unwind_*.c
 
 X86 TRUST DOMAIN EXTENSIONS (TDX)
 M:	Kiryl Shutsemau <kas@kernel.org>
+M:	Rick Edgecombe <rick.p.edgecombe@intel.com>
 R:	Dave Hansen <dave.hansen@linux.intel.com>
-R:	Rick Edgecombe <rick.p.edgecombe@intel.com>
 L:	x86@kernel.org
 L:	linux-coco@lists.linux.dev
 L:	kvm@vger.kernel.org

---
