---
title: 'coco/guest: Constify struct configfs_item_operations and configfs_group_operations'
date: 2025-12-14
last_reply: 2025-12-14
message_count: 1
participants: ['Christophe JAILLET']
---

## [1] Christophe JAILLET — 2025-12-14

'struct configfs_item_operations' and 'configfs_group_operations' are not
modified in this driver.

Constifying these structures moves some data to a read-only section, so
increases overall security, especially when the structure holds some
function pointers.

On a x86_64, with allmodconfig:
Before:
======
   text	   data	    bss	    dec	    hex	filename
  13784	   6864	    128	  20776	   5128	drivers/virt/coco/guest/report.o

After:
=====
   text	   data	    bss	    dec	    hex	filename
  14040	   6608	    128	  20776	   5128	drivers/virt/coco/guest/report.o

Signed-off-by: Christophe JAILLET <christophe.jaillet@wanadoo.fr>
---
Compile tested only.

This change is possible since commits f2f36500a63b and f7f78098690d.
---
 drivers/virt/coco/guest/report.c | 6 +++---
 1 file changed, 3 insertions(+), 3 deletions(-)

diff --git a/drivers/virt/coco/guest/report.c b/drivers/virt/coco/guest/report.c
index d3d18fc22bc2..77f8dc3ca088 100644
--- a/drivers/virt/coco/guest/report.c
+++ b/drivers/virt/coco/guest/report.c
@@ -376,7 +376,7 @@ static void tsm_report_item_release(struct config_item *cfg)
 	kfree(state);
 }
 
-static struct configfs_item_operations tsm_report_item_ops = {
+static const struct configfs_item_operations tsm_report_item_ops = {
 	.release = tsm_report_item_release,
 };
 
@@ -406,7 +406,7 @@ static bool tsm_report_is_bin_visible(struct config_item *item,
 	return provider.ops->report_bin_attr_visible(n);
 }
 
-static struct configfs_group_operations tsm_report_attr_group_ops = {
+static const struct configfs_group_operations tsm_report_attr_group_ops = {
 	.is_visible = tsm_report_is_visible,
 	.is_bin_visible = tsm_report_is_bin_visible,
 };
@@ -443,7 +443,7 @@ static void tsm_report_drop_item(struct config_group *group, struct config_item
 	atomic_dec(&provider.count);
 }
 
-static struct configfs_group_operations tsm_report_group_ops = {
+static const struct configfs_group_operations tsm_report_group_ops = {
 	.make_item = tsm_report_make_item,
 	.drop_item = tsm_report_drop_item,
 };

---
