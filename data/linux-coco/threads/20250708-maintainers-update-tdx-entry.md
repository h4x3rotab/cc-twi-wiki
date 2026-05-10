---
title: 'MAINTAINERS: Update TDX entry'
date: 2025-07-08
last_reply: 2025-07-09
message_count: 11
participants: ['Kirill A. Shutemov', 'Dave Hansen', 'Sean Christopherson', 'Xiaoyao Li']
---

## [1] Kirill A. Shutemov — 2025-07-08

The patchset updates the TDX entry in MAINTAINERS:

  - Add missing TDX files to the list, including KVM enabling;
  - Add Rick Edgecombe as a reviewer;
  - Update my email address.

Paolo, Sean, are you okay for TDX KVM stuff to be covered by the same
MAINTAINERS entry?

I don't see a reason why not, but I want to double-check.

Kirill A. Shutemov (3):
  MAINTAINERS: Update the file list in the TDX entry.
  MAINTAINERS: Add Rick Edgecombe as a TDX reviewer
  MAINTAINERS: Update Kirill Shutemov's email address

 .mailmap    |  1 +
 MAINTAINERS | 15 +++++++++++----
 2 files changed, 12 insertions(+), 4 deletions(-)

---

## [2] Kirill A. Shutemov — 2025-07-08
*Subject: [PATCH 1/3] MAINTAINERS: Update the file list in the TDX entry.*

Include files that were previously missed in the TDX entry file list.
It also includes the recently added KVM enabling.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 MAINTAINERS | 12 +++++++++---
 1 file changed, 9 insertions(+), 3 deletions(-)

diff --git a/MAINTAINERS b/MAINTAINERS
index 993ab3d3fde9..8071871ea59c 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -26952,12 +26952,18 @@ L:	linux-coco@lists.linux.dev
 S:	Supported
 T:	git git://git.kernel.org/pub/scm/linux/kernel/git/tip/tip.git x86/tdx
 F:	Documentation/ABI/testing/sysfs-devices-virtual-misc-tdx_guest
+F:	Documentation/arch/x86/tdx.rst
+F:	Documentation/virt/coco/tdx-guest.rst
+F:	Documentation/virt/kvm/x86/intel-tdx.rst
 F:	arch/x86/boot/compressed/tdx*
+F:	arch/x86/boot/compressed/tdcall.S
 F:	arch/x86/coco/tdx/
-F:	arch/x86/include/asm/shared/tdx.h
-F:	arch/x86/include/asm/tdx.h
+F:	arch/x86/include/asm/shared/tdx*
+F:	arch/x86/include/asm/tdx*
+F:	arch/x86/kvm/vmx/tdx*
 F:	arch/x86/virt/vmx/tdx/
-F:	drivers/virt/coco/tdx-guest
+F:	drivers/virt/coco/tdx-guest/
+F:	tools/testing/selftests/tdx/
 
 X86 VDSO
 M:	Andy Lutomirski <luto@kernel.org>

---

## [3] Kirill A. Shutemov — 2025-07-08
*Subject: [PATCH 2/3] MAINTAINERS: Add Rick Edgecombe as a TDX reviewer*

Rick worked extensively to enable TDX in KVM. He will continue to work
on TDX and should be involved in discussions regarding TDX.

Add Rick as a TDX reviewer.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 MAINTAINERS | 1 +
 1 file changed, 1 insertion(+)

diff --git a/MAINTAINERS b/MAINTAINERS
index 8071871ea59c..b0363770450f 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -26947,6 +26947,7 @@ F:	arch/x86/kernel/unwind_*.c
 X86 TRUST DOMAIN EXTENSIONS (TDX)
 M:	Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
 R:	Dave Hansen <dave.hansen@linux.intel.com>
+R:	Rick Edgecombe <rick.p.edgecombe@intel.com>
 L:	x86@kernel.org
 L:	linux-coco@lists.linux.dev
 S:	Supported

---

## [4] Kirill A. Shutemov — 2025-07-08
*Subject: [PATCH 3/3] MAINTAINERS: Update Kirill Shutemov's email address*

Update MAINTAINERS to use my @kernel.org email address.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 .mailmap    | 1 +
 MAINTAINERS | 2 +-
 2 files changed, 2 insertions(+), 1 deletion(-)

diff --git a/.mailmap b/.mailmap
index b0ace71968ab..85ad46d20220 100644
--- a/.mailmap
+++ b/.mailmap
@@ -416,6 +416,7 @@ Kenneth W Chen <kenneth.w.chen@intel.com>
 Kenneth Westfield <quic_kwestfie@quicinc.com> <kwestfie@codeaurora.org>
 Kiran Gunda <quic_kgunda@quicinc.com> <kgunda@codeaurora.org>
 Kirill Tkhai <tkhai@ya.ru> <ktkhai@virtuozzo.com>
+Kirill A. Shutemov <kas@kernel.org> <kirill.shutemov@linux.intel.com>
 Kishon Vijay Abraham I <kishon@kernel.org> <kishon@ti.com>
 Konrad Dybcio <konradybcio@kernel.org> <konrad.dybcio@linaro.org>
 Konrad Dybcio <konradybcio@kernel.org> <konrad.dybcio@somainline.org>
diff --git a/MAINTAINERS b/MAINTAINERS
index b0363770450f..d7da3e22f4d9 100644
--- a/MAINTAINERS
+++ b/MAINTAINERS
@@ -26945,7 +26945,7 @@ F:	arch/x86/kernel/stacktrace.c
 F:	arch/x86/kernel/unwind_*.c
 
 X86 TRUST DOMAIN EXTENSIONS (TDX)
-M:	Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
+M:	Kirill A. Shutemov <kas@kernel.org>
 R:	Dave Hansen <dave.hansen@linux.intel.com>
 R:	Rick Edgecombe <rick.p.edgecombe@intel.com>
 L:	x86@kernel.org

---

## [5] Dave Hansen — 2025-07-08
*Subject: Re: [PATCH 1/3] MAINTAINERS: Update the file list in the TDX entry.*

On 7/8/25 03:19, Kirill A. Shutemov wrote:
> @@ -26952,12 +26952,18 @@ L:	linux-coco@lists.linux.dev
>  S:	Supported

That file list is getting a bit long, but it _is_ the truth.

It's also adding some arch/x86/kvm/vmx/ files, but I assume Sean and
Paolo will welcome having some more people cc'd on those patches. The
hyper-v folks have a similar entry.

I'll plan to apply this as-is unless someone screams.

---

## [6] Sean Christopherson — 2025-07-08
*Subject: Re: [PATCH 1/3] MAINTAINERS: Update the file list in the TDX entry.*

On Tue, Jul 08, 2025, Dave Hansen wrote:
> On 7/8/25 03:19, Kirill A. Shutemov wrote:
> > @@ -26952,12 +26952,18 @@ L:	linux-coco@lists.linux.dev

What about adding

K:	tdx

instead of listing each file individually?  That might also help clarify what's
up for cases where there is overlap, e.g. with KVM, to convey that this is a
"secondary" entry of sorts.

> It's also adding some arch/x86/kvm/vmx/ files, but I assume Sean and
> Paolo will welcome having some more people cc'd on those patches. The

No objection from me.

> I'll plan to apply this as-is unless someone screams.

---

## [7] Dave Hansen — 2025-07-08
*Subject: Re: [PATCH 1/3] MAINTAINERS: Update the file list in the TDX entry.*

On 7/8/25 07:24, Sean Christopherson wrote:
>> That file list is getting a bit long, but it _is_ the truth.
> What about adding

Good idea. There are a couple of "tdx" things in the tree that aren't
TDX, but:

N:	tdx
K:	\b(tdx)

seems like it might be a _bit_ more precise. I don't see any filenames
with "tdx" in them that are false positives.

---

## [8] Xiaoyao Li — 2025-07-09
*Subject: Re: [PATCH 1/3] MAINTAINERS: Update the file list in the TDX entry.*

On 7/8/2025 6:19 PM, Kirill A. Shutemov wrote:
> Include files that were previously missed in the TDX entry file list.
> It also includes the recently added KVM enabling.

Side topic:

Could we add kvm maillist to the "L:" ?

So that KVM people can be aware of the changes on TDX.

> Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
> ---

---

## [9] Dave Hansen — 2025-07-08
*Subject: Re: [PATCH 1/3] MAINTAINERS: Update the file list in the TDX entry.*

On 7/8/25 20:31, Xiaoyao Li wrote:
> On 7/8/2025 6:19 PM, Kirill A. Shutemov wrote:
>> Include files that were previously missed in the TDX entry file list.

Sure, but send another patch please.

---

## [10] Kirill A. Shutemov — 2025-07-09
*Subject: Re: [PATCH 1/3] MAINTAINERS: Update the file list in the TDX entry.*

On Tue, Jul 08, 2025 at 09:26:21PM -0700, Dave Hansen wrote:
> On 7/8/25 20:31, Xiaoyao Li wrote:
> > On 7/8/2025 6:19 PM, Kirill A. Shutemov wrote:

Xiaoyao, do you want to send a patch, or should I?

---

## [11] Xiaoyao Li — 2025-07-09
*Subject: Re: [PATCH 1/3] MAINTAINERS: Update the file list in the TDX entry.*

On 7/9/2025 9:31 PM, Kirill A. Shutemov wrote:
> On Tue, Jul 08, 2025 at 09:26:21PM -0700, Dave Hansen wrote:
>> On 7/8/25 20:31, Xiaoyao Li wrote:

I just sent the patch.

Thanks!

---
