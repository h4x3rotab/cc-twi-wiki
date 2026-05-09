---
title: 'Allow individual features to be locked down'
date: 2025-03-21
last_reply: 2025-04-13
message_count: 9
participants: ['Nikolay Borisov', 'sergeh@kernel.org', 'Paul Moore', 'Dan Williams']
---

## [1] Nikolay Borisov — 2025-03-21

This simple change allows usecases where someone might want to  lock only specific
feature at a finer granularity than integrity/confidentiality levels allows.
The first likely user of this is the CoCo subsystem where certain features will be
disabled.

Nikolay Borisov (2):
  lockdown: Switch implementation to using bitmap
  lockdown/kunit: Introduce kunit tests

 security/lockdown/Kconfig         |  5 +++
 security/lockdown/Makefile        |  1 +
 security/lockdown/lockdown.c      | 24 +++++++++-----
 security/lockdown/lockdown_test.c | 55 +++++++++++++++++++++++++++++++
 4 files changed, 77 insertions(+), 8 deletions(-)
 create mode 100644 security/lockdown/lockdown_test.c

--
2.43.0

---

## [2] Nikolay Borisov — 2025-03-21
*Subject: [PATCH 1/2] lockdown: Switch implementation to using bitmap*

Tracking the lockdown at the depth granularity rather than at the
individual is somewhat inflexible as it provides an "all or nothing"
approach. Instead there are use cases where it  will be useful to be
able to lockdown individual features - TDX for example wants to disable
access to just /dev/mem.

To accommodate this use case switch the internal implementation to using
a bitmap so that individual lockdown features can be turned on. At the
same time retain the existing semantic where
INTEGRITY_MAX/CONFIDENTIALITY_MAX are treated as wildcards meaning "lock
everything below me".

Signed-off-by: Nikolay Borisov <nik.borisov@suse.com>
---
 security/lockdown/lockdown.c | 19 ++++++++++++-------
 1 file changed, 12 insertions(+), 7 deletions(-)

diff --git a/security/lockdown/lockdown.c b/security/lockdown/lockdown.c
index cf83afa1d879..5014d18c423f 100644
--- a/security/lockdown/lockdown.c
+++ b/security/lockdown/lockdown.c
@@ -10,12 +10,13 @@
  * 2 of the Licence, or (at your option) any later version.
  */
 
+#include <linux/bitmap.h>
 #include <linux/security.h>
 #include <linux/export.h>
 #include <linux/lsm_hooks.h>
 #include <uapi/linux/lsm.h>
 
-static enum lockdown_reason kernel_locked_down;
+static DECLARE_BITMAP(kernel_locked_down, LOCKDOWN_CONFIDENTIALITY_MAX);
 
 static const enum lockdown_reason lockdown_levels[] = {LOCKDOWN_NONE,
 						 LOCKDOWN_INTEGRITY_MAX,
@@ -26,10 +27,15 @@ static const enum lockdown_reason lockdown_levels[] = {LOCKDOWN_NONE,
  */
 static int lock_kernel_down(const char *where, enum lockdown_reason level)
 {
-	if (kernel_locked_down >= level)
-		return -EPERM;
 
-	kernel_locked_down = level;
+	if (level > LOCKDOWN_CONFIDENTIALITY_MAX)
+		return -EINVAL;
+
+	if (level == LOCKDOWN_INTEGRITY_MAX || level == LOCKDOWN_CONFIDENTIALITY_MAX)
+		bitmap_set(kernel_locked_down, 1, level);
+	else
+		bitmap_set(kernel_locked_down, level, 1);
+
 	pr_notice("Kernel is locked down from %s; see man kernel_lockdown.7\n",
 		  where);
 	return 0;
@@ -62,13 +68,12 @@ static int lockdown_is_locked_down(enum lockdown_reason what)
 		 "Invalid lockdown reason"))
 		return -EPERM;
 
-	if (kernel_locked_down >= what) {
+	if (test_bit(what, kernel_locked_down)) {
 		if (lockdown_reasons[what])
 			pr_notice_ratelimited("Lockdown: %s: %s is restricted; see man kernel_lockdown.7\n",
 				  current->comm, lockdown_reasons[what]);
 		return -EPERM;
 	}
-
 	return 0;
 }
 
@@ -105,7 +110,7 @@ static ssize_t lockdown_read(struct file *filp, char __user *buf, size_t count,
 		if (lockdown_reasons[level]) {
 			const char *label = lockdown_reasons[level];
 
-			if (kernel_locked_down == level)
+			if (test_bit(level, kernel_locked_down))
 				offset += sprintf(temp+offset, "[%s] ", label);
 			else
 				offset += sprintf(temp+offset, "%s ", label);

---

## [3] Nikolay Borisov — 2025-03-21
*Subject: [PATCH 2/2] lockdown/kunit: Introduce kunit tests*

Add a bunch of tests to ensure lockdown's conversion to bitmap hasn't
regressed it.

Signed-off-by: Nikolay Borisov <nik.borisov@suse.com>
---
 security/lockdown/Kconfig         |  5 +++
 security/lockdown/Makefile        |  1 +
 security/lockdown/lockdown.c      |  5 ++-
 security/lockdown/lockdown_test.c | 55 +++++++++++++++++++++++++++++++
 4 files changed, 65 insertions(+), 1 deletion(-)
 create mode 100644 security/lockdown/lockdown_test.c

diff --git a/security/lockdown/Kconfig b/security/lockdown/Kconfig
index e84ddf484010..5fb750da1f8c 100644
--- a/security/lockdown/Kconfig
+++ b/security/lockdown/Kconfig
@@ -6,6 +6,11 @@ config SECURITY_LOCKDOWN_LSM
 	  Build support for an LSM that enforces a coarse kernel lockdown
 	  behaviour.
 
+config SECURITY_LOCKDOWN_LSM_TEST
+	tristate "Test lockdown functionality" if !KUNIT_ALL_TESTS
+	depends on SECURITY_LOCKDOWN_LSM && KUNIT
+	default KUNIT_ALL_TESTS
+
 config SECURITY_LOCKDOWN_LSM_EARLY
 	bool "Enable lockdown LSM early in init"
 	depends on SECURITY_LOCKDOWN_LSM
diff --git a/security/lockdown/Makefile b/security/lockdown/Makefile
index e3634b9017e7..f35d90e39f1c 100644
--- a/security/lockdown/Makefile
+++ b/security/lockdown/Makefile
@@ -1 +1,2 @@
 obj-$(CONFIG_SECURITY_LOCKDOWN_LSM) += lockdown.o
+obj-$(CONFIG_SECURITY_LOCKDOWN_LSM_TEST) += lockdown_test.o
diff --git a/security/lockdown/lockdown.c b/security/lockdown/lockdown.c
index 5014d18c423f..412184121279 100644
--- a/security/lockdown/lockdown.c
+++ b/security/lockdown/lockdown.c
@@ -25,7 +25,10 @@ static const enum lockdown_reason lockdown_levels[] = {LOCKDOWN_NONE,
 /*
  * Put the kernel into lock-down mode.
  */
-static int lock_kernel_down(const char *where, enum lockdown_reason level)
+#if !IS_ENABLED(CONFIG_KUNIT)
+static
+#endif
+int lock_kernel_down(const char *where, enum lockdown_reason level)
 {
 
 	if (level > LOCKDOWN_CONFIDENTIALITY_MAX)
diff --git a/security/lockdown/lockdown_test.c b/security/lockdown/lockdown_test.c
new file mode 100644
index 000000000000..0b4184a40111
--- /dev/null
+++ b/security/lockdown/lockdown_test.c
@@ -0,0 +1,55 @@
+#include <linux/security.h>
+#include <kunit/test.h>
+
+int lock_kernel_down(const char *where, enum lockdown_reason level);
+
+static void lockdown_test_invalid_level(struct kunit *test)
+{
+	KUNIT_EXPECT_EQ(test, -EINVAL, lock_kernel_down("TEST", LOCKDOWN_CONFIDENTIALITY_MAX+1));
+}
+
+static void lockdown_test_depth_locking(struct kunit *test)
+{
+	KUNIT_EXPECT_EQ(test, 0, lock_kernel_down("TEST", LOCKDOWN_INTEGRITY_MAX));
+	for (int i = 1; i < LOCKDOWN_INTEGRITY_MAX; i++) {
+		KUNIT_EXPECT_EQ_MSG(test, -EPERM, security_locked_down(i), "at i=%d", i);
+	}
+
+	KUNIT_EXPECT_EQ(test, -EPERM, security_locked_down(LOCKDOWN_INTEGRITY_MAX));
+}
+
+static void lockdown_test_individual_level(struct kunit *test)
+{
+	KUNIT_EXPECT_EQ(test, 0, lock_kernel_down("TEST", LOCKDOWN_PERF));
+	KUNIT_EXPECT_EQ(test, -EPERM, security_locked_down(LOCKDOWN_PERF));
+	/* Ensure adjacent levels are untouched */
+	KUNIT_EXPECT_EQ(test, 0, security_locked_down(LOCKDOWN_TRACEFS));
+	KUNIT_EXPECT_EQ(test, 0, security_locked_down(LOCKDOWN_DBG_READ_KERNEL));
+}
+
+static void lockdown_test_no_downgrade(struct kunit *test)
+{
+	KUNIT_EXPECT_EQ(test, 0, lock_kernel_down("TEST", LOCKDOWN_CONFIDENTIALITY_MAX));
+	KUNIT_EXPECT_EQ(test, 0, lock_kernel_down("TEST", LOCKDOWN_INTEGRITY_MAX));
+	/*
+	 * Ensure having locked down to a lower leve after a higher level
+	 * lockdown nothing is lost
+	 */
+	KUNIT_EXPECT_EQ(test, -EPERM, security_locked_down(LOCKDOWN_TRACEFS));
+}
+
+static struct kunit_case lockdown_tests[] = {
+	KUNIT_CASE(lockdown_test_invalid_level),
+	KUNIT_CASE(lockdown_test_depth_locking),
+	KUNIT_CASE(lockdown_test_individual_level),
+	KUNIT_CASE(lockdown_test_no_downgrade),
+	{}
+};
+
+static struct kunit_suite lockdown_test_suite = {
+	.name = "lockdown test",
+	.test_cases = lockdown_tests,
+};
+kunit_test_suite(lockdown_test_suite);
+
+MODULE_LICENSE("GPL");

---

## [4] sergeh@kernel.org — 2025-03-21
*Subject: Re: [PATCH 1/2] lockdown: Switch implementation to using bitmap*

On Fri, Mar 21, 2025 at 12:24:20PM +0200, Nikolay Borisov wrote:
> Tracking the lockdown at the depth granularity rather than at the
> individual is somewhat inflexible as it provides an "all or nothing"

Reviewed-by: Serge Hallyn <sergeh@kernel.org>

but one comment below

> ---
>  security/lockdown/lockdown.c | 19 ++++++++++++-------

Context here is:

static ssize_t lockdown_read(struct file *filp, char __user *buf, size_t count,
                             loff_t *ppos)
{
        char temp[80] = "";
        int i, offset = 0;

        for (i = 0; i < ARRAY_SIZE(lockdown_levels); i++) {
                enum lockdown_reason level = lockdown_levels[i];

...

>  		if (lockdown_reasons[level]) {
>  			const char *label = lockdown_reasons[level];

Right now this is still just looping over the lockdown_levels, and so
it can't get longer than "none [integrity] [confidentiality]" which fits
easily into the 80 chars of temp.  But I'm worried that someone will
change this loop i a way that violates that.  Could you just switch
this to a snprintf that checks its result for < 0 and >= n , or some
other sanity check?

>  				offset += sprintf(temp+offset, "[%s] ", label);
>  			else

---

## [5] Paul Moore — 2025-03-21
*Subject: Re: [PATCH 0/2] Allow individual features to be locked down*

On Fri, Mar 21, 2025 at 6:24 AM Nikolay Borisov <nik.borisov@suse.com> wrote:
>
> This simple change allows usecases where someone might want to  lock only specific

Hi Nikolay,

Thanks for the patches!  With the merge window opening in a few days,
it is too late to consider this for the upcoming merge window so
realistically this patchset is two weeks out and I'm hopeful we'll
have a dedicated Lockdown maintainer by then so I'm going to defer the
ultimate decision on acceptance to them.

---

## [6] Nikolay Borisov — 2025-04-09
*Subject: Re: [PATCH 1/2] lockdown: Switch implementation to using bitmap*

On 21.03.25 г. 22:34 ч., sergeh@kernel.org wrote:
> On Fri, Mar 21, 2025 at 12:24:20PM +0200, Nikolay Borisov wrote:
>> Tracking the lockdown at the depth granularity rather than at the

How about the following:

diff --git a/security/lockdown/lockdown.c b/security/lockdown/lockdown.c
index 412184121279..47b47c4f7b98 100644
--- a/security/lockdown/lockdown.c
+++ b/security/lockdown/lockdown.c
@@ -114,9 +114,9 @@ static ssize_t lockdown_read(struct file *filp, char __user *buf, size_t count,
                         const char *label = lockdown_reasons[level];
  
                         if (test_bit(level, kernel_locked_down))
-                               offset += sprintf(temp+offset, "[%s] ", label);
+                               offset += snprintf(temp+offset, 80-offset, "[%s] ", label);
                         else
-                               offset += sprintf(temp+offset, "%s ", label);
+                               offset += snprintf(temp+offset, 80-offset, "%s ", label);
                 }
         }

It prevents buffer overflow but doesn't prevent buffer truncation.

> 
>>   				offset += sprintf(temp+offset, "[%s] ", label);

---

## [7] Dan Williams — 2025-04-09
*Subject: Re: [PATCH 0/2] Allow individual features to be locked down*

Paul Moore wrote:
> On Fri, Mar 21, 2025 at 6:24 AM Nikolay Borisov <nik.borisov@suse.com> wrote:
> >

The patches in this thread proposed to selectively disable /dev/mem
independent of all the other lockdown mitigations. That goal can be
achieved with more precision with this proposed patch:

http://lore.kernel.org/67f5b75c37143_71fe2949b@dwillia2-xfh.jf.intel.com.notmuch

---

## [8] Nikolay Borisov — 2025-04-09
*Subject: Re: [PATCH 0/2] Allow individual features to be locked down*

On 9.04.25 г. 18:45 ч., Dan Williams wrote:
> Paul Moore wrote:
>> On Fri, Mar 21, 2025 at 6:24 AM Nikolay Borisov <nik.borisov@suse.com> wrote:


True, however I think increasing the granularity of the lockdown 
subsystem merits its own discussion, notwithstanding COCO use case.

---

## [9] Paul Moore — 2025-04-13
*Subject: Re: [PATCH 0/2] Allow individual features to be locked down*

On Fri, Mar 21, 2025 at 5:13 PM Paul Moore <paul@paul-moore.com> wrote:
> On Fri, Mar 21, 2025 at 6:24 AM Nikolay Borisov <nik.borisov@suse.com> wrote:
> >

FYI, I expect we'll see something on the mailing list related to this soon.

---
