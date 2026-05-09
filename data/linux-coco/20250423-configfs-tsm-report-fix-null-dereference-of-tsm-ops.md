---
title: 'configfs-tsm-report: Fix NULL dereference of tsm_ops'
date: 2025-04-23
last_reply: 2025-04-30
message_count: 7
participants: ['Dan Williams', 'Sathyanarayanan Kuppuswamy', 'Huang, Kai']
---

## [1] Dan Williams — 2025-04-23

Unlike sysfs, the lifetime of configfs objects is controlled by
userspace. There is no mechanism for the kernel to find and delete all
created config-items. Instead, the configfs-tsm-report mechanism has an
expectation that tsm_unregister() can happen at any time and cause
established config-item access to start failing.

That expectation is not fully satisfied. While tsm_report_read(),
tsm_report_{is,is_bin}_visible(), and tsm_report_make_item() safely fail
if tsm_ops have been unregistered, tsm_report_privlevel_store()
tsm_report_provider_show() fail to check for ops registration. Add the
missing checks for tsm_ops having been removed.

Now, in supporting the ability for tsm_unregister() to always succeed,
it leaves the problem of what to do with lingering config-items. The
expectation is that the admin that arranges for the ->remove() (unbind)
of the ${tsm_arch}-guest driver is also responsible for deletion of all
open config-items. Until that deletion happens, ->probe() (reload /
bind) of the ${tsm_arch}-guest driver fails.

This allows for emergency shutdown / revocation of attestation
interfaces, and requires coordinated restart.

Fixes: 70e6f7e2b985 ("configfs-tsm: Introduce a shared ABI for attestation reports")
Cc: stable@vger.kernel.org
Cc: Suzuki K Poulose <suzuki.poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Cc: Sami Mujawar <sami.mujawar@arm.com>
Cc: Borislav Petkov (AMD) <bp@alien8.de>
Cc: Tom Lendacky <thomas.lendacky@amd.com>
Cc: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Reported-by: Cedric Xing <cedric.xing@intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/virt/coco/tsm.c |   26 +++++++++++++++++++++++++-
 1 file changed, 25 insertions(+), 1 deletion(-)

diff --git a/drivers/virt/coco/tsm.c b/drivers/virt/coco/tsm.c
index 9432d4e303f1..096f4f7c0c11 100644
--- a/drivers/virt/coco/tsm.c
+++ b/drivers/virt/coco/tsm.c
@@ -15,6 +15,7 @@
 static struct tsm_provider {
 	const struct tsm_ops *ops;
 	void *data;
+	atomic_t count;
 } provider;
 static DECLARE_RWSEM(tsm_rwsem);
 
@@ -92,6 +93,10 @@ static ssize_t tsm_report_privlevel_store(struct config_item *cfg,
 	if (rc)
 		return rc;
 
+	guard(rwsem_write)(&tsm_rwsem);
+	if (!provider.ops)
+		return -ENXIO;
+
 	/*
 	 * The valid privilege levels that a TSM might accept, if it accepts a
 	 * privilege level setting at all, are a max of TSM_PRIVLEVEL_MAX (see
@@ -101,7 +106,6 @@ static ssize_t tsm_report_privlevel_store(struct config_item *cfg,
 	if (provider.ops->privlevel_floor > val || val > TSM_PRIVLEVEL_MAX)
 		return -EINVAL;
 
-	guard(rwsem_write)(&tsm_rwsem);
 	rc = try_advance_write_generation(report);
 	if (rc)
 		return rc;
@@ -115,6 +119,10 @@ static ssize_t tsm_report_privlevel_floor_show(struct config_item *cfg,
 					       char *buf)
 {
 	guard(rwsem_read)(&tsm_rwsem);
+
+	if (!provider.ops)
+		return -ENXIO;
+
 	return sysfs_emit(buf, "%u\n", provider.ops->privlevel_floor);
 }
 CONFIGFS_ATTR_RO(tsm_report_, privlevel_floor);
@@ -217,6 +225,9 @@ CONFIGFS_ATTR_RO(tsm_report_, generation);
 static ssize_t tsm_report_provider_show(struct config_item *cfg, char *buf)
 {
 	guard(rwsem_read)(&tsm_rwsem);
+	if (!provider.ops)
+		return -ENXIO;
+
 	return sysfs_emit(buf, "%s\n", provider.ops->name);
 }
 CONFIGFS_ATTR_RO(tsm_report_, provider);
@@ -421,12 +432,20 @@ static struct config_item *tsm_report_make_item(struct config_group *group,
 	if (!state)
 		return ERR_PTR(-ENOMEM);
 
+	atomic_inc(&provider.count);
 	config_item_init_type_name(&state->cfg, name, &tsm_report_type);
 	return &state->cfg;
 }
 
+static void tsm_report_drop_item(struct config_group *group, struct config_item *item)
+{
+	config_item_put(item);
+	atomic_dec(&provider.count);
+}
+
 static struct configfs_group_operations tsm_report_group_ops = {
 	.make_item = tsm_report_make_item,
+	.drop_item = tsm_report_drop_item,
 };
 
 static const struct config_item_type tsm_reports_type = {
@@ -459,6 +478,11 @@ int tsm_register(const struct tsm_ops *ops, void *priv)
 		return -EBUSY;
 	}
 
+	if (atomic_read(&provider.count)) {
+		pr_err("configfs/tsm not empty\n");
+		return -EBUSY;
+	}
+
 	provider.ops = ops;
 	provider.data = priv;
 	return 0;

---

## [2] Sathyanarayanan Kuppuswamy — 2025-04-23
*Subject: Re: [PATCH] configfs-tsm-report: Fix NULL dereference of tsm_ops*

On 4/23/25 2:01 PM, Dan Williams wrote:
> Unlike sysfs, the lifetime of configfs objects is controlled by
> userspace. There is no mechanism for the kernel to find and delete all

Looks good to me

Reviewed-by: Kuppuswamy Sathyanarayanan 
<sathyanarayanan.kuppuswamy@linux.intel.com>
>   drivers/virt/coco/tsm.c |   26 +++++++++++++++++++++++++-
>   1 file changed, 25 insertions(+), 1 deletion(-)


Nit: I think adding the provider ops name will make the debug log clear.


> +		return -EBUSY;
> +	}

---

## [3] Dan Williams — 2025-04-23
*Subject: Re: [PATCH] configfs-tsm-report: Fix NULL dereference of tsm_ops*

Sathyanarayanan Kuppuswamy wrote:
> 
> On 4/23/25 2:01 PM, Dan Williams wrote:

Thanks!

[..]
> >   static const struct config_item_type tsm_reports_type = {
> > @@ -459,6 +478,11 @@ int tsm_register(const struct tsm_ops *ops, void *priv)

Recall though that the ->name field is a tsm_ops property. At this point
tsm_ops is already unregistered. Even if we kept the name around by
strdup() at register time the name does not help solving the conflict,
only rmdir of the created configs-item unblocks the next registration.

---

## [4] Sathyanarayanan Kuppuswamy — 2025-04-24
*Subject: Re: [PATCH] configfs-tsm-report: Fix NULL dereference of tsm_ops*

On 4/23/25 8:07 PM, Dan Williams wrote:
> Sathyanarayanan Kuppuswamy wrote:
>> On 4/23/25 2:01 PM, Dan Williams wrote:

Makes sense.

---

## [5] Huang, Kai — 2025-04-29
*Subject: Re: [PATCH] configfs-tsm-report: Fix NULL dereference of tsm_ops*

On Wed, 2025-04-23 at 14:01 -0700, Dan Williams wrote:
> Unlike sysfs, the lifetime of configfs objects is controlled by
> userspace. There is no mechanism for the kernel to find and delete all

Still, is it better to print some message in tsm_unregister() to tell that some
items have not been deleted?

> 
> Fixes: 70e6f7e2b985 ("configfs-tsm: Introduce a shared ABI for attestation reports")

Reviewed-by: Kai Huang <kai.huang@intel.com>

> ---
>  drivers/virt/coco/tsm.c |   26 +++++++++++++++++++++++++-

A minor thing:

I see tsm_report_read() returns -ENOTTY in the similar case:

static ssize_t tsm_report_read(struct tsm_report *report, void *buf,           
                               size_t count, enum tsm_data_select select)      
{       
	...
        
        /* slow path, report may need to be regenerated... */                  
        guard(rwsem_write)(&tsm_rwsem);                                        
        ops = provider.ops;                                                    
        if (!ops)                                                              
                return -ENOTTY;

Should it be changed to -ENXIO for consistency?

---

## [6] Dan Williams — 2025-04-28
*Subject: Re: [PATCH] configfs-tsm-report: Fix NULL dereference of tsm_ops*

Huang, Kai wrote:
> On Wed, 2025-04-23 at 14:01 -0700, Dan Williams wrote:
> > Unlike sysfs, the lifetime of configfs objects is controlled by

Sounds reasonable.

> > 
> > Fixes: 70e6f7e2b985 ("configfs-tsm: Introduce a shared ABI for attestation reports")

Also seems reasonable, will fixup.

---

## [7] Dan Williams — 2025-04-30
*Subject: [PATCH v2] configfs-tsm-report: Fix NULL dereference of tsm_ops*

Unlike sysfs, the lifetime of configfs objects is controlled by
userspace. There is no mechanism for the kernel to find and delete all
created config-items. Instead, the configfs-tsm-report mechanism has an
expectation that tsm_unregister() can happen at any time and cause
established config-item access to start failing.

That expectation is not fully satisfied. While tsm_report_read(),
tsm_report_{is,is_bin}_visible(), and tsm_report_make_item() safely fail
if tsm_ops have been unregistered, tsm_report_privlevel_store()
tsm_report_provider_show() fail to check for ops registration. Add the
missing checks for tsm_ops having been removed.

Now, in supporting the ability for tsm_unregister() to always succeed,
it leaves the problem of what to do with lingering config-items. The
expectation is that the admin that arranges for the ->remove() (unbind)
of the ${tsm_arch}-guest driver is also responsible for deletion of all
open config-items. Until that deletion happens, ->probe() (reload /
bind) of the ${tsm_arch}-guest driver fails.

This allows for emergency shutdown / revocation of attestation
interfaces, and requires coordinated restart.

Fixes: 70e6f7e2b985 ("configfs-tsm: Introduce a shared ABI for attestation reports")
Cc: stable@vger.kernel.org
Cc: Suzuki K Poulose <suzuki.poulose@arm.com>
Cc: Steven Price <steven.price@arm.com>
Cc: Sami Mujawar <sami.mujawar@arm.com>
Cc: Borislav Petkov (AMD) <bp@alien8.de>
Cc: Tom Lendacky <thomas.lendacky@amd.com>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Reported-by: Cedric Xing <cedric.xing@intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
Changes since v1:
- Report leftover config items on tsm_unregister() (Kai)

 drivers/virt/coco/tsm.c | 31 +++++++++++++++++++++++++++++--
 1 file changed, 29 insertions(+), 2 deletions(-)

diff --git a/drivers/virt/coco/tsm.c b/drivers/virt/coco/tsm.c
index 9432d4e303f1..8a638bc34d4a 100644
--- a/drivers/virt/coco/tsm.c
+++ b/drivers/virt/coco/tsm.c
@@ -15,6 +15,7 @@
 static struct tsm_provider {
 	const struct tsm_ops *ops;
 	void *data;
+	atomic_t count;
 } provider;
 static DECLARE_RWSEM(tsm_rwsem);
 
@@ -92,6 +93,10 @@ static ssize_t tsm_report_privlevel_store(struct config_item *cfg,
 	if (rc)
 		return rc;
 
+	guard(rwsem_write)(&tsm_rwsem);
+	if (!provider.ops)
+		return -ENXIO;
+
 	/*
 	 * The valid privilege levels that a TSM might accept, if it accepts a
 	 * privilege level setting at all, are a max of TSM_PRIVLEVEL_MAX (see
@@ -101,7 +106,6 @@ static ssize_t tsm_report_privlevel_store(struct config_item *cfg,
 	if (provider.ops->privlevel_floor > val || val > TSM_PRIVLEVEL_MAX)
 		return -EINVAL;
 
-	guard(rwsem_write)(&tsm_rwsem);
 	rc = try_advance_write_generation(report);
 	if (rc)
 		return rc;
@@ -115,6 +119,10 @@ static ssize_t tsm_report_privlevel_floor_show(struct config_item *cfg,
 					       char *buf)
 {
 	guard(rwsem_read)(&tsm_rwsem);
+
+	if (!provider.ops)
+		return -ENXIO;
+
 	return sysfs_emit(buf, "%u\n", provider.ops->privlevel_floor);
 }
 CONFIGFS_ATTR_RO(tsm_report_, privlevel_floor);
@@ -217,6 +225,9 @@ CONFIGFS_ATTR_RO(tsm_report_, generation);
 static ssize_t tsm_report_provider_show(struct config_item *cfg, char *buf)
 {
 	guard(rwsem_read)(&tsm_rwsem);
+	if (!provider.ops)
+		return -ENXIO;
+
 	return sysfs_emit(buf, "%s\n", provider.ops->name);
 }
 CONFIGFS_ATTR_RO(tsm_report_, provider);
@@ -284,7 +295,7 @@ static ssize_t tsm_report_read(struct tsm_report *report, void *buf,
 	guard(rwsem_write)(&tsm_rwsem);
 	ops = provider.ops;
 	if (!ops)
-		return -ENOTTY;
+		return -ENXIO;
 	if (!report->desc.inblob_len)
 		return -EINVAL;
 
@@ -421,12 +432,20 @@ static struct config_item *tsm_report_make_item(struct config_group *group,
 	if (!state)
 		return ERR_PTR(-ENOMEM);
 
+	atomic_inc(&provider.count);
 	config_item_init_type_name(&state->cfg, name, &tsm_report_type);
 	return &state->cfg;
 }
 
+static void tsm_report_drop_item(struct config_group *group, struct config_item *item)
+{
+	config_item_put(item);
+	atomic_dec(&provider.count);
+}
+
 static struct configfs_group_operations tsm_report_group_ops = {
 	.make_item = tsm_report_make_item,
+	.drop_item = tsm_report_drop_item,
 };
 
 static const struct config_item_type tsm_reports_type = {
@@ -459,6 +478,11 @@ int tsm_register(const struct tsm_ops *ops, void *priv)
 		return -EBUSY;
 	}
 
+	if (atomic_read(&provider.count)) {
+		pr_err("configfs/tsm/report not empty\n");
+		return -EBUSY;
+	}
+
 	provider.ops = ops;
 	provider.data = priv;
 	return 0;
@@ -470,6 +494,9 @@ int tsm_unregister(const struct tsm_ops *ops)
 	guard(rwsem_write)(&tsm_rwsem);
 	if (ops != provider.ops)
 		return -EBUSY;
+	if (atomic_read(&provider.count))
+		pr_warn("\"%s\" unregistered with items present in configfs/tsm/report\n",
+			provider.ops->name);
 	provider.ops = NULL;
 	provider.data = NULL;
 	return 0;

base-commit: 8ffd015db85fea3e15a77027fda6c02ced4d2444

---
