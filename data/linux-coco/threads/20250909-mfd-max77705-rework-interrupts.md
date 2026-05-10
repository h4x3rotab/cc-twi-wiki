---
title: 'mfd: max77705: rework interrupts'
date: 2025-09-09
last_reply: 2025-09-16
message_count: 2
participants: ['Dzmitry Sankouski', 'Lee Jones']
---

## [1] Dzmitry Sankouski — 2025-09-09

Current implementation describes only MFD's own topsys interrupts.
However, max77705 has a register which indicates interrupt source, i.e.
it acts as an interrupt controller. There's 4 interrupt sources in
max77705: topsys, charger, fuelgauge, usb type-c manager.

Setup max77705 MFD parent as an interrupt controller. Delete topsys
interrupts because currently unused.

Remove shared interrupt flag, because we're are an interrupt controller
now, and subdevices should request interrupts from us.

Fixes: c8d50f029748 ("mfd: Add new driver for MAX77705 PMIC")

Signed-off-by: Dzmitry Sankouski <dsankouski@gmail.com>
---
Max77705 has a register, which indicates, who is triggering irq. There
may be 4 irq sources in max77705: charger, fuelgauge, usb type-c
manager ic, and so-called 'topsys'. Hence, max77705 mfd parent device is
an interrupt controller. This series implements interrupt controller in
max77705 mfd.
---
Changes in v3:
- remove shared flag
- Link to v2: https://lore.kernel.org/r/20250907-max77705-fix_interrupt_handling-v2-1-79b86662f983@gmail.com

Changes in v2:
- remove unused interrupt declarations
- Link to v1: https://lore.kernel.org/r/20250831-max77705-fix_interrupt_handling-v1-1-73e078012e51@gmail.com
---
Changes to v2:
- delete topsys interrupts declarations
Changes to v3:
- remove shared irq flag, and describe why in commit msg
---
 drivers/mfd/max77705.c | 35 ++++++++++++++---------------------
 1 file changed, 14 insertions(+), 21 deletions(-)

diff --git a/drivers/mfd/max77705.c b/drivers/mfd/max77705.c
index 6b263bacb8c2..62dbc63efa8d 100644
--- a/drivers/mfd/max77705.c
+++ b/drivers/mfd/max77705.c
@@ -61,21 +61,21 @@ static const struct regmap_config max77705_regmap_config = {
 	.max_register = MAX77705_PMIC_REG_USBC_RESET,
 };
 
-static const struct regmap_irq max77705_topsys_irqs[] = {
-	{ .mask = MAX77705_SYSTEM_IRQ_BSTEN_INT, },
-	{ .mask = MAX77705_SYSTEM_IRQ_SYSUVLO_INT, },
-	{ .mask = MAX77705_SYSTEM_IRQ_SYSOVLO_INT, },
-	{ .mask = MAX77705_SYSTEM_IRQ_TSHDN_INT, },
-	{ .mask = MAX77705_SYSTEM_IRQ_TM_INT, },
+static const struct regmap_irq max77705_irqs[] = {
+	{ .mask = MAX77705_SRC_IRQ_CHG, },
+	{ .mask = MAX77705_SRC_IRQ_TOP, },
+	{ .mask = MAX77705_SRC_IRQ_FG, },
+	{ .mask = MAX77705_SRC_IRQ_USBC, },
 };
 
-static const struct regmap_irq_chip max77705_topsys_irq_chip = {
-	.name		= "max77705-topsys",
-	.status_base	= MAX77705_PMIC_REG_SYSTEM_INT,
-	.mask_base	= MAX77705_PMIC_REG_SYSTEM_INT_MASK,
+static const struct regmap_irq_chip max77705_irq_chip = {
+	.name		= "max77705",
+	.status_base	= MAX77705_PMIC_REG_INTSRC,
+	.ack_base	= MAX77705_PMIC_REG_INTSRC,
+	.mask_base	= MAX77705_PMIC_REG_INTSRC_MASK,
 	.num_regs	= 1,
-	.irqs		= max77705_topsys_irqs,
-	.num_irqs	= ARRAY_SIZE(max77705_topsys_irqs),
+	.irqs		= max77705_irqs,
+	.num_irqs	= ARRAY_SIZE(max77705_irqs),
 };
 
 static int max77705_i2c_probe(struct i2c_client *i2c)
@@ -110,19 +110,12 @@ static int max77705_i2c_probe(struct i2c_client *i2c)
 
 	ret = devm_regmap_add_irq_chip(dev, max77705->regmap,
 					i2c->irq,
-					IRQF_ONESHOT | IRQF_SHARED, 0,
-					&max77705_topsys_irq_chip,
+					IRQF_ONESHOT, 0,
+					&max77705_irq_chip,
 					&irq_data);
 	if (ret)
 		return dev_err_probe(dev, ret, "Failed to add IRQ chip\n");
 
-	/* Unmask interrupts from all blocks in interrupt source register */
-	ret = regmap_update_bits(max77705->regmap,
-				 MAX77705_PMIC_REG_INTSRC_MASK,
-				 MAX77705_SRC_IRQ_ALL, (unsigned int)~MAX77705_SRC_IRQ_ALL);
-	if (ret < 0)
-		return dev_err_probe(dev, ret, "Could not unmask interrupts in INTSRC\n");
-
 	domain = regmap_irq_get_domain(irq_data);
 
 	ret = devm_mfd_add_devices(dev, PLATFORM_DEVID_NONE,

---
base-commit: be5d4872e528796df9d7425f2bd9b3893eb3a42c
change-id: 20250831-max77705-fix_interrupt_handling-0889cee6936d

Best regards,

---

## [2] Lee Jones — 2025-09-16
*Subject: Re: (subset) [PATCH v3] mfd: max77705: rework interrupts*

On Tue, 09 Sep 2025 21:23:07 +0300, Dzmitry Sankouski wrote:
> Current implementation describes only MFD's own topsys interrupts.
> However, max77705 has a register which indicates interrupt source, i.e.

Applied, thanks!

[1/1] mfd: max77705: rework interrupts
      commit: e3f56377ff69b0944da8780f2c5a14f10de71c13

--
Lee Jones [李琼斯]

---
