---
title: 'crypto/ccp/tsm: Enable the root port after the endpoint'
date: 2026-05-21
last_reply: 2026-05-21
message_count: 1
participants: ['Alexey Kardashevskiy']
---

## [1] Alexey Kardashevskiy — 2026-05-21

The PCIe r7.0, chapter "6.33.8 Other IDE Rules" mandates if selective IDE
is enabled for config requersts, a stream must be enabled on the endpoint
before enabling it on the rootport:

===
For Selective IDE, the Stream must not be used until it has been enabled in
both Partner Ports. For cases where one of the Partner Ports is a Root Port
and Selective IDE for Configuration Requests is enabled, the other
Partner Port must be enabled prior to the Root Port. For other scenarios,
the mechanisms to satisfy this requirement are implementation-specific.
===

Do what the spec says.

Fixes: 4be423572da1 ("crypto/ccp: Implement SEV-TIO PCIe IDE (phase1)")
Signed-off-by: Alexey Kardashevskiy <aik@amd.com>
---
 drivers/crypto/ccp/sev-dev-tsm.c | 10 +++++-----
 1 file changed, 5 insertions(+), 5 deletions(-)

diff --git a/drivers/crypto/ccp/sev-dev-tsm.c b/drivers/crypto/ccp/sev-dev-tsm.c
index b07ae529b591..10549a2cc2ae 100644
--- a/drivers/crypto/ccp/sev-dev-tsm.c
+++ b/drivers/crypto/ccp/sev-dev-tsm.c
@@ -58,13 +58,13 @@ static int stream_enable(struct pci_ide *ide)
 	struct pci_dev *rp = pcie_find_root_port(ide->pdev);
 	int ret;
 
-	ret = pci_ide_stream_enable(rp, ide);
-	if (ret)
+	ret = pci_ide_stream_enable(ide->pdev, ide);
+	if (ret && ret != -ENXIO)
 		return ret;
 
-	ret = pci_ide_stream_enable(ide->pdev, ide);
-	if (ret)
-		pci_ide_stream_disable(rp, ide);
+	ret = pci_ide_stream_enable(rp, ide);
+	if (ret && ret != -ENXIO)
+		pci_ide_stream_disable(ide->pdev, ide);
 
 	return ret;
 }

---
