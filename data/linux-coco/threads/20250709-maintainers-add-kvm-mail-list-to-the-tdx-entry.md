---
title: 'MAINTAINERS: Add KVM mail list to the TDX entry'
date: 2025-07-09
last_reply: 2025-07-09
message_count: 3
participants: ['Xiaoyao Li', 'Sean Christopherson', 'Kirill A . Shutemov']
---

## [1] Xiaoyao Li — 2025-07-09

KVM is the primary user of TDX within the kernel, and it is KVM that
provides support for running TDX guests.

Add the KVM mailing list to the TDX entry so that KVM people can be
informed of proposed changes and updates related to TDX.

Signed-off-by: Xiaoyao Li <xiaoyao.li@intel.com>
---
 MAINTAINERS | 1 +
 1 file changed, 1 insertion(+)

diff --git a/MAINTAINERS b/MAINTAINERS
index 0c1d245bf7b8..f1fb15729460 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -26907,6 +26907,7 @@ M:	Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
 R:	Dave Hansen <dave.hansen@linux.intel.com>
 L:	x86@kernel.org
 L:	linux-coco@lists.linux.dev
+L:	kvm@vger.kernel.org
 S:	Supported
 T:	git git://git.kernel.org/pub/scm/linux/kernel/git/tip/tip.git x86/tdx
 F:	Documentation/ABI/testing/sysfs-devices-virtual-misc-tdx_guest

---

## [2] Sean Christopherson — 2025-07-09
*Subject: Re: [PATCH] MAINTAINERS: Add KVM mail list to the TDX entry*

On Wed, Jul 09, 2025, Xiaoyao Li wrote:
> KVM is the primary user of TDX within the kernel, and it is KVM that
> provides support for running TDX guests.

Acked-by: Sean Christopherson <seanjc@google.com>

---

## [3] Kirill A . Shutemov — 2025-07-09
*Subject: Re: [PATCH] MAINTAINERS: Add KVM mail list to the TDX entry*

On Wed, Jul 09, 2025 at 10:10:35PM +0800, Xiaoyao Li wrote:
> KVM is the primary user of TDX within the kernel, and it is KVM that
> provides support for running TDX guests.

Acked-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>

---
