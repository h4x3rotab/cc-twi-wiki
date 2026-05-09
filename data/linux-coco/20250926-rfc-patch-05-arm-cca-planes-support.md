---
title: '[RFC PATCH 0/5] Arm CCA planes support'
date: 2025-09-26
last_reply: 2025-09-26
message_count: 6
participants: ['Steven Price']
---

## [1] Steven Price — 2025-09-26

The Arm CCA (Confidential Compute Architecture) RMM version 1.1
specification[1] adds support for a concept of "planes". This allows a
realm to be divided into multiple execution environments with memory
separation between them (while still sharing the same IPA to PA
translations). There's an overview on the Arm website[2].

The TF-RMM project[3] recently merged support for planes to their "main"
branch and this an early preview of the corresponding Linux changes to
support the feature. Note you need to enable the (experimental) RMM_V1_1
configuration option to enable this feature.

This series is based on the v10 posting of the CCA host support
series[4] and is also available as a git tree:

  https://gitlab.arm.com/linux-arm/linux-cca.git/ cca/planes/rfc-v1

A hacked up version of kvmtool to launch a realm guest with an extra
plan is available here:

  https://gitlab.arm.com/linux-arm/kvmtool-cca.git/ cca/planes/rfc-v1

Note:
   The kvmtool support is a hack - it simply (unconditionally) enables a
   single extra plane (for a total of two planes: P0 and P1). This
   should obviously be a configuration option and should support other
   numbers of planes. But it gives an easy way of testing the support
   for auxiliary RTTs while running a single guest image (i.e. leaving
   P1 empty).

This series was written against the RMM v1.1 alp14 specification. Those
who are following things closely will know we're up to alp16, however
there are no major changes affecting planes between these two versions.
The spec is still alpha, so there may well be changes in the future.

[1] https://developer.arm.com/-/cdn-downloads/permalink/Architectures/Armv9/DEN0137_1.1-alp14.zip
[2] https://developer.arm.com/documentation/den0125/400/Arm-CCA-Extensions#md239-arm-cca-extensions__realm-planes
[3] https://www.trustedfirmware.org/projects/tf-rmm/
[4] https://lore.kernel.org/r/20250820145606.180644-1-steven.price%40arm.com

Steven Price (5):
  arm64: RME: Add SMC definitions introduced in RMM v1.1
  arm64: RME: Handle auxiliary RTT trees
  arm64: RME: Support RMI_EXIT_S2AP_CHANGE
  arm64: rme: Allocate AUX RTT PGDs and VMIDs
  arm64: RME: Support num_aux_places & rtt_tree_pp realm parameters

 arch/arm64/include/asm/kvm_rme.h  |   13 +-
 arch/arm64/include/asm/rmi_cmds.h | 1104 +++++++++++++++++++++++++++--
 arch/arm64/include/asm/rmi_smc.h  |  121 +++-
 arch/arm64/include/uapi/asm/kvm.h |   12 +
 arch/arm64/kvm/mmu.c              |   15 +-
 arch/arm64/kvm/rme-exit.c         |   33 +-
 arch/arm64/kvm/rme.c              |  441 +++++++++++-
 7 files changed, 1618 insertions(+), 121 deletions(-)

---

## [2] Steven Price — 2025-09-26
*Subject: [RFC PATCH 1/5] arm64: RME: Add SMC definitions introduced in RMM v1.1*

RMM v1.1 adds a bunch of new SMCs for planes and device assignment.
Add the new SMC definitions including wrapper functions.

The definitions are based on DEN0137 version 1.1-alp14.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/include/asm/rmi_cmds.h | 1104 +++++++++++++++++++++++++++--
 arch/arm64/include/asm/rmi_smc.h  |  121 +++-
 2 files changed, 1146 insertions(+), 79 deletions(-)

diff --git a/arch/arm64/include/asm/rmi_cmds.h b/arch/arm64/include/asm/rmi_cmds.h
index ef53147c1984..cfeddf4a6ed1 100644
--- a/arch/arm64/include/asm/rmi_cmds.h
+++ b/arch/arm64/include/asm/rmi_cmds.h
@@ -142,6 +142,244 @@ static inline int rmi_granule_undelegate(unsigned long phys)
 	return res.a0;
 }
 
+/**
+ * rmi_mec_set_private() - Change state of a MEC to private
+ * @mecid: Memory Encryption Context Idenifier
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_mec_set_private(unsigned long mecid)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_MEC_SET_PRIVATE, mecid, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_mec_set_shared() - Change state of a MEC to shared
+ * @mecid: Memory Encryption Context Identifier
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_mec_set_shared(unsigned long mecid)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_MEC_SET_SHARED, mecid, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_pdev_abort() - Abort device communication associated with a PDEV
+ * @pdev_ptr: PA of the PDEV
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_pdev_abort(unsigned long pdev_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_ABORT, pdev_ptr, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_pdev_aux_count() - Get number of auxiliary granules required for a PDEV
+ * @flags: PDEV flags
+ * @out_aux_count: Number of auxiliary granules required
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_pdev_aux_count(unsigned long flags,
+				     unsigned long *out_aux_count)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_AUX_COUNT, flags, &res);
+
+	*out_aux_count = res.a1;
+	return res.a0;
+}
+
+/**
+ * rmi_pdev_communicate() - Perform device communication associated with a PDEV
+ * @pdev_ptr: PA of the PDEV
+ * @data_ptr: PA of the communication data structure
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_pdev_communicate(unsigned long pdev_ptr,
+				       unsigned long data_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_COMMUNICATE, pdev_ptr, data_ptr,
+			     &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_pdev_create() - Create a PDEV
+ * @pdev_ptr: PA of the PDEV
+ * @params_ptr: PA of PDEV parameters
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_pdev_create(unsigned long pdev_ptr,
+				  unsigned long params_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_CREATE, pdev_ptr, params_ptr, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_pdev_destroy() - Destroy a PDEV
+ * @pdev_ptr: PA of the PDEV
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_pdev_destroy(unsigned long pdev_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_DESTROY, pdev_ptr, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_pdev_get_state() - Get state of a PDEV
+ * @pdev_ptr: PA of the PDEV
+ * @out_state: PDEV state
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_pdev_get_state(unsigned long pdev_ptr,
+				     unsigned long *out_state)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_GET_STATE, pdev_ptr, &res);
+
+	*out_state = res.a1;
+	return res.a0;
+}
+
+/**
+ * rmi_pdev_ide_key_refresh() - Refresh keys ina n IDE connection
+ * @pdev_ptr: PA of the PDEV
+ * @coh: Select coherent or non-coherent IDE stream
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_pdev_ide_key_refresh(unsigned long pdev_ptr,
+					   unsigned long coh)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_IDE_KEY_REFRESH, pdev_ptr, coh, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_pdev_ide_reset() - Reset the IDE link of a PDEV
+ * @pdev_ptr: PA of the PDEV
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_pdev_ide_reset(unsigned long pdev_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_IDE_RESET, pdev_ptr, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_pdev_p2p_connect() - Create a P2P stream between two PDEVs
+ * @stream_ptr: PA of the P2P_STREAM object
+ * @pdev_1_ptr: PA of the first PDEV object
+ * @pdev_2_ptr: PA of the second PDEV object
+ * @ide_sid: IDE stream ID
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_pdev_p2p_connect(unsigned long stream_ptr,
+				       unsigned long pdev_1_ptr,
+				       unsigned long pdev_2_ptr,
+				       unsigned long ide_sid)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_P2P_CONNECT, stream_ptr,
+			     pdev_1_ptr, pdev_2_ptr, ide_sid, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_pdev_p2p_disconnect() - Destroy a P2P stream between two PDEVs
+ * @stream_ptr: PA of the P2P_STREAM object
+ * @pdev_1_ptr: PA of the first PDEV object
+ * @pdev_2_ptr: PA of the second PDEV object
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_pdev_p2p_disconnect(unsigned long stream_ptr,
+					  unsigned long pdev_1_ptr,
+					  unsigned long pdev_2_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_P2P_DISCONNECT, stream_ptr,
+			     pdev_1_ptr, pdev_2_ptr, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_pdev_set_pubkey() - Provide public key associated with a PDEV
+ * @pdev_ptr: PA of the PDEV
+ * @params_ptr: PA of the key parameters
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_pdev_set_pubkey(unsigned long pdev_ptr,
+				      unsigned long params_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_SET_PUBKEY, pdev_ptr, params_ptr,
+			     &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_pdev_stop() - Stop a PDEV
+ * @pdev_ptr: PA of the PDEV
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_pdev_stop(unsigned long pdev_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PDEV_STOP, pdev_ptr, &res);
+
+	return res.a0;
+}
+
 /**
  * rmi_psci_complete() - Complete pending PSCI command
  * @calling_rec: PA of the calling REC
@@ -165,6 +403,76 @@ static inline int rmi_psci_complete(unsigned long calling_rec,
 	return res.a0;
 }
 
+/**
+ * rmi_psmmu_irq_notify() - Notify the RM of an SMMU interrupt
+ * @psmmu: PA of the PSMMU
+ * @irq: SMMU IRQ
+ * @out_action: Action required by host
+ * @out_rd: PA of RD
+ * @out_vsmmu: PA of VSMMU
+ * @out_msi_addr: MSI address
+ * @out_msi_data: MSI data
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_psmmu_irq_notify(unsigned long psmmu,
+				       unsigned long irq,
+				       unsigned long *out_action,
+				       unsigned long *out_rd,
+				       unsigned long *out_vsmmu,
+				       unsigned long *out_msi_addr,
+				       unsigned long *out_msi_data)
+{
+	struct arm_smccc_1_2_regs regs = {
+		SMC_RMI_PSMMU_IRQ_NOTIFY,
+		psmmu,
+		irq
+	};
+
+	arm_smccc_1_2_smc(&regs, &regs);
+
+	*out_action = regs.a1;
+	*out_rd = regs.a2;
+	*out_vsmmu = regs.a3;
+	*out_msi_addr = regs.a4;
+	*out_msi_data = regs.a5;
+
+	return regs.a0;
+}
+
+/**
+ * rmi_psmmu_msi_config() - Program the MSI config for SMMU
+ * @psmmu: PA of PSMMU
+ * @gerr_addr: MSI address of the GERROR interrupt
+ * @gerr_data: MSI data of the GERROR interrupt
+ * @eventq_addr: MSI address of the EVENTQ interrupt
+ * @eventq_data: MSI data of the EVENTQ interrupt
+ * @priq_addr: MSI address of the PRIQ interrupt
+ * @priq_data: MSI data of the PRIQ interrupt
+ *
+ * Programs the MSI configuration for the realm side of the physical SMMU.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_psmmu_msi_config(unsigned long psmmu,
+				       unsigned long gerr_addr,
+				       unsigned long gerr_data,
+				       unsigned long eventq_addr,
+				       unsigned long eventq_data,
+				       unsigned long priq_addr,
+				       unsigned long priq_data)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_PSMMU_MSI_CONFIG, psmmu,
+			     gerr_data, gerr_data,
+			     eventq_addr, eventq_data,
+			     priq_addr, priq_data,
+			     &res);
+
+	return res.a0;
+}
+
 /**
  * rmi_realm_activate() - Active a realm
  * @rd: PA of the RD
@@ -297,49 +605,51 @@ static inline int rmi_rec_enter(unsigned long rec, unsigned long run_ptr)
 }
 
 /**
- * rmi_rtt_create() - Creates an RTT
+ * rmi_rtt_aux_create() - Creates an auxiliary RTT
  * @rd: PA of the RD
  * @rtt: PA of the target RTT
  * @ipa: Base of the IPA range described by the RTT
- * @level: Depth of the RTT within the tree
- *
- * Creates an RTT (Realm Translation Table) at the specified level for the
- * translation of the specified address within the realm.
+ * @level: RTT level
+ * @index: RTT tree index
  *
  * Return: RMI return code
  */
-static inline int rmi_rtt_create(unsigned long rd, unsigned long rtt,
-				 unsigned long ipa, long level)
+static inline int rmi_rtt_aux_create(unsigned long rd,
+				     unsigned long rtt,
+				     unsigned long ipa,
+				     long level,
+				     unsigned long index)
 {
 	struct arm_smccc_res res;
 
-	arm_smccc_1_1_invoke(SMC_RMI_RTT_CREATE, rd, rtt, ipa, level, &res);
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_AUX_CREATE, rd, rtt, ipa, level, index,
+			     &res);
 
 	return res.a0;
 }
 
 /**
- * rmi_rtt_destroy() - Destroy an RTT
+ * rmi_rtt_aux_destroy() - Destroys an auxiliary RTT
  * @rd: PA of the RD
- * @ipa: Base of the IPA range described by the RTT
- * @level: Depth of the RTT within the tree
- * @out_rtt: Pointer to write the PA of the RTT which was destroyed
- * @out_top: Pointer to write the top IPA of non-live RTT entries
+ * @ipa: Base of the IPA range describe dby the RTT
+ * @level: RTT level
+ * @index: RTT tree index
+ * @out_rtt: PA of the RTT which was destroyed
+ * @out_top: Top IPA of non-live RTT entries
  *
- * Destroys an RTT. The RTT must be non-live, i.e. none of the entries in the
- * table are in ASSIGNED or TABLE state.
- *
- * Return: RMI return code.
+ * Return: RMI return code
  */
-static inline int rmi_rtt_destroy(unsigned long rd,
-				  unsigned long ipa,
-				  long level,
-				  unsigned long *out_rtt,
-				  unsigned long *out_top)
+static inline int rmi_rtt_aux_destroy(unsigned long rd,
+				      unsigned long ipa,
+				      long level,
+				      unsigned long index,
+				      unsigned long *out_rtt,
+				      unsigned long *out_top)
 {
 	struct arm_smccc_res res;
 
-	arm_smccc_1_1_invoke(SMC_RMI_RTT_DESTROY, rd, ipa, level, &res);
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_AUX_DESTROY, rd, ipa, level, index,
+			     &res);
 
 	if (out_rtt)
 		*out_rtt = res.a1;
@@ -350,23 +660,24 @@ static inline int rmi_rtt_destroy(unsigned long rd,
 }
 
 /**
- * rmi_rtt_fold() - Fold an RTT
+ * rmi_rtt_aux_fold() - Destroy a homogeneous auxility RTT
  * @rd: PA of the RD
  * @ipa: Base of the IPA range described by the RTT
- * @level: Depth of the RTT within the tree
- * @out_rtt: Pointer to write the PA of the RTT which was destroyed
- *
- * Folds an RTT. If all entries with the RTT are 'homogeneous' the RTT can be
- * folded into the parent and the RTT destroyed.
+ * @level: RTT level
+ * @index: RTT tree index
+ * @out_rtt: PA of the RTT which was destroyed
  *
  * Return: RMI return code
  */
-static inline int rmi_rtt_fold(unsigned long rd, unsigned long ipa,
-			       long level, unsigned long *out_rtt)
+static inline int rmi_rtt_aux_fold(unsigned long rd,
+				   unsigned long ipa,
+				   long level,
+				   unsigned long index,
+				   unsigned long *out_rtt)
 {
 	struct arm_smccc_res res;
 
-	arm_smccc_1_1_invoke(SMC_RMI_RTT_FOLD, rd, ipa, level, &res);
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_AUX_FOLD, rd, ipa, level, index, &res);
 
 	if (out_rtt)
 		*out_rtt = res.a1;
@@ -375,75 +686,254 @@ static inline int rmi_rtt_fold(unsigned long rd, unsigned long ipa,
 }
 
 /**
- * rmi_rtt_init_ripas() - Set RIPAS for new realm
+ * rmi_rtt_aux_map_protected() - Create a protected mapping in an aux RTT
  * @rd: PA of the RD
- * @base: Base of target IPA region
- * @top: Top of target IPA region
- * @out_top: Top IPA of range whose RIPAS was modified
- *
- * Sets the RIPAS of a target IPA range to RAM, for a realm in the NEW state.
+ * @ipa: IPA in the target realm
+ * @index: RTT tree index
+ * @out_state: State of RTT entry which caused command to fail
+ * @out_ripas: RIPAS of RTT entry which caused command to fail
  *
  * Return: RMI return code
  */
-static inline int rmi_rtt_init_ripas(unsigned long rd, unsigned long base,
-				     unsigned long top, unsigned long *out_top)
+static inline int rmi_rtt_aux_map_protected(unsigned long rd,
+					    unsigned long ipa,
+					    unsigned long index,
+					    unsigned long *out_state,
+					    unsigned long *out_ripas)
 {
-	struct arm_smccc_res res;
+	struct arm_smccc_1_2_regs regs = {
+		SMC_RMI_RTT_AUX_MAP_PROTECTED,
+		rd, ipa, index
+	};
 
-	arm_smccc_1_1_invoke(SMC_RMI_RTT_INIT_RIPAS, rd, base, top, &res);
+	arm_smccc_1_2_smc(&regs, &regs);
 
-	if (out_top)
-		*out_top = res.a1;
+	if (out_state)
+		*out_state = regs.a1;
+	if (out_ripas)
+		*out_ripas = regs.a2;
 
-	return res.a0;
+	return regs.a0;
 }
 
 /**
- * rmi_rtt_map_unprotected() - Map NS granules into a realm
+ * rmi_rtt_aux_map_unprotected() - Create an unprotected mapping in an aux RTT
  * @rd: PA of the RD
- * @ipa: Base IPA of the mapping
- * @level: Depth within the RTT tree
- * @desc: RTTE descriptor
- *
- * Create a mapping from an Unprotected IPA to a Non-secure PA.
+ * @ipa: IPA in the target realm
+ * @index: RTT tree index
  *
  * Return: RMI return code
  */
-static inline int rmi_rtt_map_unprotected(unsigned long rd,
-					  unsigned long ipa,
-					  long level,
-					  unsigned long desc)
+static inline int rmi_rtt_aux_map_unprotected(unsigned long rd,
+					      unsigned long ipa,
+					      unsigned long index)
 {
 	struct arm_smccc_res res;
 
-	arm_smccc_1_1_invoke(SMC_RMI_RTT_MAP_UNPROTECTED, rd, ipa, level,
-			     desc, &res);
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_AUX_MAP_UNPROTECTED, rd, ipa, index,
+			     &res);
 
 	return res.a0;
 }
 
 /**
- * rmi_rtt_read_entry() - Read an RTTE
+ * rmi_rtt_aux_unmap_protected() - Remove a protected mapping in an aux RTT
  * @rd: PA of the RD
- * @ipa: IPA for which to read the RTTE
- * @level: RTT level at which to read the RTTE
- * @rtt: Output structure describing the RTTE
- *
- * Reads a RTTE (Realm Translation Table Entry).
+ * @ipa: IPA in the target realm
+ * @index: RTT tree index
+ * @out_top: Top IPA of non-live RTT entry
  *
  * Return: RMI return code
  */
-static inline int rmi_rtt_read_entry(unsigned long rd, unsigned long ipa,
-				     long level, struct rtt_entry *rtt)
+static inline int rmi_rtt_aux_unmap_protected(unsigned long rd,
+					      unsigned long ipa,
+					      unsigned long index,
+					      unsigned long *out_top)
 {
-	struct arm_smccc_1_2_regs regs = {
-		SMC_RMI_RTT_READ_ENTRY,
-		rd, ipa, level
-	};
+	struct arm_smccc_res res;
 
-	arm_smccc_1_2_invoke(&regs, &regs);
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_AUX_UNMAP_PROTECTED, rd, ipa, index,
+			     &res);
 
-	rtt->walk_level = regs.a1;
+	if (out_top)
+		*out_top = res.a1;
+
+	return res.a0;
+}
+
+/**
+ * rmi_rtt_aux_unmap_unprotected() - Remove an unprotected mapping in an aux RTT
+ * @rd: PA of the RD
+ * @ipa: IPA in the target realm
+ * @index: RTT tree index
+ * @out_top: Top IPA of non-live RTT entry
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rtt_aux_unmap_unprotected(unsigned long rd,
+						unsigned long ipa,
+						unsigned long index,
+						unsigned long *out_top)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_AUX_UNMAP_UNPROTECTED, rd, ipa, index,
+			     &res);
+
+	if (out_top)
+		*out_top = res.a1;
+
+	return res.a0;
+}
+
+/**
+ * rmi_rtt_create() - Creates an RTT
+ * @rd: PA of the RD
+ * @rtt: PA of the target RTT
+ * @ipa: Base of the IPA range described by the RTT
+ * @level: Depth of the RTT within the tree
+ *
+ * Creates an RTT (Realm Translation Table) at the specified level for the
+ * translation of the specified address within the realm.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rtt_create(unsigned long rd, unsigned long rtt,
+				 unsigned long ipa, long level)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_CREATE, rd, rtt, ipa, level, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_rtt_destroy() - Destroy an RTT
+ * @rd: PA of the RD
+ * @ipa: Base of the IPA range described by the RTT
+ * @level: Depth of the RTT within the tree
+ * @out_rtt: Pointer to write the PA of the RTT which was destroyed
+ * @out_top: Pointer to write the top IPA of non-live RTT entries
+ *
+ * Destroys an RTT. The RTT must be non-live, i.e. none of the entries in the
+ * table are in ASSIGNED or TABLE state.
+ *
+ * Return: RMI return code.
+ */
+static inline int rmi_rtt_destroy(unsigned long rd,
+				  unsigned long ipa,
+				  long level,
+				  unsigned long *out_rtt,
+				  unsigned long *out_top)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_DESTROY, rd, ipa, level, &res);
+
+	if (out_rtt)
+		*out_rtt = res.a1;
+	if (out_top)
+		*out_top = res.a2;
+
+	return res.a0;
+}
+
+/**
+ * rmi_rtt_fold() - Fold an RTT
+ * @rd: PA of the RD
+ * @ipa: Base of the IPA range described by the RTT
+ * @level: Depth of the RTT within the tree
+ * @out_rtt: Pointer to write the PA of the RTT which was destroyed
+ *
+ * Folds an RTT. If all entries with the RTT are 'homogeneous' the RTT can be
+ * folded into the parent and the RTT destroyed.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rtt_fold(unsigned long rd, unsigned long ipa,
+			       long level, unsigned long *out_rtt)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_FOLD, rd, ipa, level, &res);
+
+	if (out_rtt)
+		*out_rtt = res.a1;
+
+	return res.a0;
+}
+
+/**
+ * rmi_rtt_init_ripas() - Set RIPAS for new realm
+ * @rd: PA of the RD
+ * @base: Base of target IPA region
+ * @top: Top of target IPA region
+ * @out_top: Top IPA of range whose RIPAS was modified
+ *
+ * Sets the RIPAS of a target IPA range to RAM, for a realm in the NEW state.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rtt_init_ripas(unsigned long rd, unsigned long base,
+				     unsigned long top, unsigned long *out_top)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_INIT_RIPAS, rd, base, top, &res);
+
+	if (out_top)
+		*out_top = res.a1;
+
+	return res.a0;
+}
+
+/**
+ * rmi_rtt_map_unprotected() - Map NS granules into a realm
+ * @rd: PA of the RD
+ * @ipa: Base IPA of the mapping
+ * @level: Depth within the RTT tree
+ * @desc: RTTE descriptor
+ *
+ * Create a mapping from an Unprotected IPA to a Non-secure PA.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rtt_map_unprotected(unsigned long rd,
+					  unsigned long ipa,
+					  long level,
+					  unsigned long desc)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_MAP_UNPROTECTED, rd, ipa, level,
+			     desc, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_rtt_read_entry() - Read an RTTE
+ * @rd: PA of the RD
+ * @ipa: IPA for which to read the RTTE
+ * @level: RTT level at which to read the RTTE
+ * @rtt: Output structure describing the RTTE
+ *
+ * Reads a RTTE (Realm Translation Table Entry).
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rtt_read_entry(unsigned long rd, unsigned long ipa,
+				     long level, struct rtt_entry *rtt)
+{
+	struct arm_smccc_1_2_regs regs = {
+		SMC_RMI_RTT_READ_ENTRY,
+		rd, ipa, level
+	};
+
+	arm_smccc_1_2_invoke(&regs, &regs);
+
+	rtt->walk_level = regs.a1;
 	rtt->state = regs.a2 & 0xFF;
 	rtt->desc = regs.a3;
 	rtt->ripas = regs.a4 & 0xFF;
@@ -478,6 +968,38 @@ static inline int rmi_rtt_set_ripas(unsigned long rd, unsigned long rec,
 	return res.a0;
 }
 
+/**
+ * rmi_rtt_set_s2ap() - Change the S2AP of a target IPA range
+ * @rd: PA of the RD
+ * @rec_ptr: PA of the target REC
+ * @base: Base of target IPA region
+ * @top: Top of target IPA region
+ * @out_top: Top IPA of range whose S2AP was modified
+ * @out_rtt_tree: Index of RTT tree in which base alignment check failed
+ *
+ * Completes a request made by the realm to change the S2AP of a target IPA
+ * range.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_rtt_set_s2ap(unsigned long rd, unsigned long rec_ptr,
+				   unsigned long base, unsigned long top,
+				   unsigned long *out_top,
+				   unsigned long *out_rtt_tree)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_RTT_SET_S2AP, rd, rec_ptr, base, top,
+			     &res);
+
+	if (out_top)
+		*out_top = res.a1;
+	if (out_rtt_tree)
+		*out_rtt_tree = res.a2;
+
+	return res.a0;
+}
+
 /**
  * rmi_rtt_unmap_unprotected() - Remove a NS mapping
  * @rd: PA of the RD
@@ -505,4 +1027,444 @@ static inline int rmi_rtt_unmap_unprotected(unsigned long rd,
 	return res.a0;
 }
 
+/**
+ * rmi_vdev_abort() - Abort device communication associated with a VDEV
+ * @vdev_ptr: PA of the VDEV
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_vdev_abort(unsigned long vdev_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_ABORT, vdev_ptr, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_vdev_aux_count() - Get number of aux granules required for a VDEV
+ * @pdev_flags: PDEV flags
+ * @vdev_flags: VDEV flags
+ * @out_aux_count: Number of auxiliary granules required
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_vdev_aux_count(unsigned long pdev_flags,
+				     unsigned long vdev_flags,
+				     unsigned long *out_aux_count)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_AUX_COUNT, pdev_flags, vdev_flags,
+			     &res);
+
+	*out_aux_count = res.a1;
+	return res.a0;
+}
+
+/**
+ * rmi_vdev_communicate() - Perform device communication with a VDEV
+ * @pdev_ptr: PA of the PDEV
+ * @vdev_ptr: PA of the VDEV
+ * @data_ptr: PA of the comms data structure
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_vdev_communicate(unsigned long pdev_ptr,
+				       unsigned long vdev_ptr,
+				       unsigned long data_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_COMMUNICATE, pdev_ptr, vdev_ptr,
+			     data_ptr, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_vdev_complete() - Complete a pending VDEV request
+ * @rec_ptr: PA of the REC
+ * @vdev_ptr: PA of the VDEV
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_vdev_complete(unsigned long rec_ptr,
+				    unsigned long vdev_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_COMPLETE, rec_ptr, vdev_ptr, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_vdev_create() - Create a VDEV
+ * @rd: PA of the RD
+ * @pdev_ptr: PA of the PDEV
+ * @vdev_ptr: PA of the VDEV
+ * @params_ptr: PA of VDEV parameters
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_vdev_create(unsigned long rd,
+				  unsigned long pdev_ptr,
+				  unsigned long vdev_ptr,
+				  unsigned long params_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_CREATE, rd, pdev_ptr, vdev_ptr,
+			     params_ptr, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_vdev_destroy() - Destroy a VDEV
+ * @rd: PA of the RD
+ * @pdev_ptr: PA of the PDEV
+ * @vdev_ptr: PA of the VDEV
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_vdev_destroy(unsigned long rd,
+				   unsigned long pdev_ptr,
+				   unsigned long vdev_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_DESTROY, rd, pdev_ptr, vdev_ptr,
+			     &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_vdev_get_interface_report() - Get VDEV interface report
+ * @rd: PA of the RD
+ * @vdev_ptr: PA of the VDEV
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_vdev_get_interface_report(unsigned long rd,
+						unsigned long vdev_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_GET_INTERFACE_REPORT, rd, vdev_ptr,
+			     &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_vdev_get_measurements() - Get VDEV measurements
+ * @rd: PA of the RD
+ * @vdev_ptr: PA of the VDEV
+ * @params_ptr: PA of VDEV parameters
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_vdev_get_measurements(unsigned long rd,
+					    unsigned long vdev_ptr,
+					    unsigned long params_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_GET_MEASUREMENTS, rd, vdev_ptr,
+			     params_ptr, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_vdev_get_state() - Get state of a VDEV
+ * @vdev_ptr: PA of the VDEV
+ * @out_state: VDEV state
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_vdev_get_state(unsigned long vdev_ptr,
+				     unsigned long *out_state)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_GET_STATE, vdev_ptr, &res);
+
+	*out_state = res.a1;
+	return res.a0;
+}
+
+/**
+ * rmi_vdev_lock() - Lock VDEV
+ * @rd: PA of the RD
+ * @vdev_ptr: PA of the VDEV
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_vdev_lock(unsigned long rd,
+				unsigned long vdev_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_LOCK, rd, vdev_ptr, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_vdev_map() - Maps device memory
+ * @rd: PA of the RD for the target realm
+ * @vdev_ptr: PA of the VDEV
+ * @ipa: IPA at which the memory will be mapped in the target realm
+ * @level: RTT level
+ * @addr: PA of the target device memory
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_vdev_map(unsigned long rd, unsigned long vdev_ptr,
+			       unsigned long ipa, long level,
+			       unsigned long addr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_MAP, rd, vdev_ptr, ipa, level, addr,
+			     &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_vdev_p2p_bind() - Create a P2P binding between two VDEVs
+ * @stream_ptr: PA of the P2P_STREAM object
+ * @rd: PA of the RD
+ * @rec_ptr: PA of the target REC
+ * @pdev_1_ptr: PA of the first PDEV object
+ * @pdev_2_ptr: PA of the second PDEV object
+ * @vdev_1_ptr: PA of the first VDEV object
+ * @vdev_2_ptr: PA of the second VDEV object
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_vdev_p2p_bind(unsigned long stream_ptr,
+				    unsigned long rd,
+				    unsigned long rec_ptr,
+				    unsigned long pdev_1_ptr,
+				    unsigned long pdev_2_ptr,
+				    unsigned long vdev_1_ptr,
+				    unsigned long vdev_2_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_P2P_BIND, stream_ptr, rd, rec_ptr,
+			     pdev_1_ptr, pdev_2_ptr,
+			     vdev_1_ptr, vdev_2_ptr, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_vdev_p2p_unbind() - Remove a P2P binding between two VDEVs
+ * @stream_ptr: PA of the P2P_STREAM object
+ * @rd: PA of the RD
+ * @rec_ptr: PA of the target REC
+ * @pdev_1_ptr: PA of the first PDEV object
+ * @pdev_2_ptr: PA of the second PDEV object
+ * @vdev_1_ptr: PA of the first VDEV object
+ * @vdev_2_ptr: PA of the second VDEV object
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_vdev_p2p_unbind(unsigned long stream_ptr,
+				      unsigned long rd,
+				      unsigned long rec_ptr,
+				      unsigned long pdev_1_ptr,
+				      unsigned long pdev_2_ptr,
+				      unsigned long vdev_1_ptr,
+				      unsigned long vdev_2_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_P2P_UNBIND, stream_ptr, rd, rec_ptr,
+			     pdev_1_ptr, pdev_2_ptr,
+			     vdev_1_ptr, vdev_2_ptr, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_vdev_start() - Start a VDEV
+ * @rd: PA of the RD
+ * @vdev_ptr: PA of the VDEV
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_vdev_start(unsigned long rd, unsigned long vdev_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_START, rd, vdev_ptr, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_vdev_unlock() - Unlock a VDEV
+ * @rd: PA of the RD
+ * @vdev_ptr: PA of the VDEV
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_vdev_unlock(unsigned long rd, unsigned long vdev_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_UNLOCK, rd, vdev_ptr, &res);
+
+	return res.a0;
+}
+
+/**
+ * rmi_vdev_unmap() - Unmap device memory
+ * @rd: PA of the RD which owns the target device memory
+ * @vdev_ptr: PA of the VDEV
+ * @ipa: IPA at which the memory is mapped in the target realm
+ * @level: RTT level
+ * @out_pa: PA of the device memory which was unmapped
+ * @out_top: Top IPA of non-live RTT entries
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_vdev_unmap(unsigned long rd, unsigned long vdev_ptr,
+				 unsigned long ipa, long level,
+				 unsigned long *out_pa, unsigned long *out_top)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_UNMAP, rd, vdev_ptr, ipa, level,
+			     &res);
+
+	if (out_pa)
+		*out_pa = res.a1;
+	if (out_top)
+		*out_top = res.a2;
+
+	return res.a0;
+}
+
+/**
+ * rmi_vdev_validate_mapping() - Complete a request to valid mappings
+ * @rd: PA of the RD for the target realm
+ * @rec_ptr: PA of the target REC
+ * @pdev_ptr: PA of the PDEV
+ * @vdev_ptr: PA of the VDEV
+ * @base: Base of target IPA region
+ * @top: Top of target IPA region
+ * @out_top: Top IPA of range whose RIPAS was modified
+ *
+ * Completes a request made by the realm to validate mappings to device memory
+ * from a target IPA range.
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_vdev_validate_mapping(unsigned long rd,
+					    unsigned long rec_ptr,
+					    unsigned long pdev_ptr,
+					    unsigned long vdev_ptr,
+					    unsigned long base,
+					    unsigned long top,
+					    unsigned long *out_top)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VDEV_VALIDATE_MAPPING, rd, rec_ptr,
+			     pdev_ptr, vdev_ptr, base, top, &res);
+
+	if (out_top)
+		*out_top = res.a1;
+
+	return res.a0;
+}
+
+/** rmi_vsmmu_create() - Create a VSMMU
+ * @rd: PA of the RD
+ * @vsmmu_ptr: PA of the VSMMU
+ * @params_ptr: PA of VSMMU parameters
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_vsmmu_create(unsigned long rd,
+				   unsigned long vsmmu_ptr,
+				   unsigned long params_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VSMMU_CREATE, rd, vsmmu_ptr,
+			     params_ptr, &res);
+
+	return res.a0;
+}
+
+/** rmi_vsmmu_destroy() - Destroy a VSMMU
+ * @rd: PA of the RD
+ * @vsmmu_ptr: PA of the VSMMU
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_vsmmu_destroy(unsigned long rd,
+				    unsigned long vsmmu_ptr)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VSMMU_DESTROY, rd, vsmmu_ptr, &res);
+
+	return res.a0;
+}
+
+/** rmi_vsmmu_map() - Create a VSMMU mapping
+ * @rd: PA of the RD
+ * @vsmmu_ptr: PA of the VSMMU
+ * @ipa: IPA at which to create the mapping
+ * @level: RTT level
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_vsmmu_map(unsigned long rd,
+				unsigned long vsmmu_ptr,
+				unsigned long ipa,
+				long level)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VSMMU_MAP, rd, vsmmu_ptr, ipa, level,
+			     &res);
+
+	return res.a0;
+}
+
+/** rmi_vsmmu_unmap() - Remove a VSMMU mapping
+ * @rd: PA of the RD
+ * @ipa: IPA at which to remove the mapping
+ * @vsmmu_ptr: PA of the VSMMU
+ * @out_top: Top IPA of non-live RTT entries
+ *
+ * Return: RMI return code
+ */
+static inline int rmi_vsmmu_unmap(unsigned long rd,
+				  unsigned long ipa,
+				  unsigned long vsmmu_ptr,
+				  unsigned long *out_top)
+{
+	struct arm_smccc_res res;
+
+	arm_smccc_1_1_invoke(SMC_RMI_VSMMU_UNMAP, rd, ipa, vsmmu_ptr, &res);
+
+	if (out_top)
+		*out_top = res.a1;
+	return res.a0;
+}
+
 #endif /* __ASM_RMI_CMDS_H */
diff --git a/arch/arm64/include/asm/rmi_smc.h b/arch/arm64/include/asm/rmi_smc.h
index 1000368f1bca..11d45d2c0c52 100644
--- a/arch/arm64/include/asm/rmi_smc.h
+++ b/arch/arm64/include/asm/rmi_smc.h
@@ -24,7 +24,7 @@
 #define SMC_RMI_DATA_CREATE		SMC_RMI_CALL(0x0153)
 #define SMC_RMI_DATA_CREATE_UNKNOWN	SMC_RMI_CALL(0x0154)
 #define SMC_RMI_DATA_DESTROY		SMC_RMI_CALL(0x0155)
-
+#define SMC_RMI_PDEV_AUX_COUNT		SMC_RMI_CALL(0x0156)
 #define SMC_RMI_REALM_ACTIVATE		SMC_RMI_CALL(0x0157)
 #define SMC_RMI_REALM_CREATE		SMC_RMI_CALL(0x0158)
 #define SMC_RMI_REALM_DESTROY		SMC_RMI_CALL(0x0159)
@@ -34,19 +34,63 @@
 #define SMC_RMI_RTT_CREATE		SMC_RMI_CALL(0x015d)
 #define SMC_RMI_RTT_DESTROY		SMC_RMI_CALL(0x015e)
 #define SMC_RMI_RTT_MAP_UNPROTECTED	SMC_RMI_CALL(0x015f)
-
+#define SMC_RMI_VDEV_AUX_COUNT		SMC_RMI_CALL(0x0160)
 #define SMC_RMI_RTT_READ_ENTRY		SMC_RMI_CALL(0x0161)
 #define SMC_RMI_RTT_UNMAP_UNPROTECTED	SMC_RMI_CALL(0x0162)
-
+#define SMC_RMI_VDEV_VALIDATE_MAPPING	SMC_RMI_CALL(0x0163)
 #define SMC_RMI_PSCI_COMPLETE		SMC_RMI_CALL(0x0164)
 #define SMC_RMI_FEATURES		SMC_RMI_CALL(0x0165)
 #define SMC_RMI_RTT_FOLD		SMC_RMI_CALL(0x0166)
 #define SMC_RMI_REC_AUX_COUNT		SMC_RMI_CALL(0x0167)
 #define SMC_RMI_RTT_INIT_RIPAS		SMC_RMI_CALL(0x0168)
 #define SMC_RMI_RTT_SET_RIPAS		SMC_RMI_CALL(0x0169)
+#define SMC_RMI_VSMMU_CREATE		SMC_RMI_CALL(0x016a)
+#define SMC_RMI_VSMMU_DESTROY		SMC_RMI_CALL(0x016b)
+#define SMC_RMI_VSMMU_MAP		SMC_RMI_CALL(0x016c)
+#define SMC_RMI_VSMMU_UNMAP		SMC_RMI_CALL(0x016d)
+#define SMC_RMI_PSMMU_MSI_CONFIG	SMC_RMI_CALL(0x016e)
+#define SMC_RMI_PSMMU_IRQ_NOTIFY	SMC_RMI_CALL(0x016f)
+
+#define SMC_RMI_PDEV_P2P_CONNECT	SMC_RMI_CALL(0x0171)
+#define SMC_RMI_VDEV_MAP		SMC_RMI_CALL(0x0172)
+#define SMC_RMI_VDEV_UNMAP		SMC_RMI_CALL(0x0173)
+#define SMC_RMI_PDEV_ABORT		SMC_RMI_CALL(0x0174)
+#define SMC_RMI_PDEV_COMMUNICATE	SMC_RMI_CALL(0x0175)
+#define SMC_RMI_PDEV_CREATE		SMC_RMI_CALL(0x0176)
+#define SMC_RMI_PDEV_DESTROY		SMC_RMI_CALL(0x0177)
+#define SMC_RMI_PDEV_GET_STATE		SMC_RMI_CALL(0x0178)
+#define SMC_RMI_PDEV_IDE_RESET		SMC_RMI_CALL(0x0179)
+#define SMC_RMI_PDEV_IDE_KEY_REFRESH	SMC_RMI_CALL(0x017a)
+#define SMC_RMI_PDEV_SET_PUBKEY		SMC_RMI_CALL(0x017b)
+#define SMC_RMI_PDEV_STOP		SMC_RMI_CALL(0x017c)
+#define SMC_RMI_RTT_AUX_CREATE		SMC_RMI_CALL(0x017d)
+#define SMC_RMI_RTT_AUX_DESTROY		SMC_RMI_CALL(0x017e)
+#define SMC_RMI_RTT_AUX_FOLD		SMC_RMI_CALL(0x017f)
+#define SMC_RMI_RTT_AUX_MAP_PROTECTED	SMC_RMI_CALL(0x0180)
+#define SMC_RMI_RTT_AUX_MAP_UNPROTECTED	SMC_RMI_CALL(0x0181)
+#define SMC_RMI_PDEV_P2P_DISCONNECT	SMC_RMI_CALL(0x0182)
+#define SMC_RMI_RTT_AUX_UNMAP_PROTECTED	SMC_RMI_CALL(0x0183)
+#define SMC_RMI_RTT_AUX_UNMAP_UNPROTECTED SMC_RMI_CALL(0x0184)
+#define SMC_RMI_VDEV_ABORT		SMC_RMI_CALL(0x0185)
+#define SMC_RMI_VDEV_COMMUNICATE	SMC_RMI_CALL(0x0186)
+#define SMC_RMI_VDEV_CREATE		SMC_RMI_CALL(0x0187)
+#define SMC_RMI_VDEV_DESTROY		SMC_RMI_CALL(0x0188)
+#define SMC_RMI_VDEV_GET_STATE		SMC_RMI_CALL(0x0189)
+#define SMC_RMI_VDEV_UNLOCK		SMC_RMI_CALL(0x018a)
+#define SMC_RMI_RTT_SET_S2AP		SMC_RMI_CALL(0x018b)
+#define SMC_RMI_MEC_SET_SHARED		SMC_RMI_CALL(0x018c)
+#define SMC_RMI_MEC_SET_PRIVATE		SMC_RMI_CALL(0x018d)
+#define SMC_RMI_VDEV_COMPLETE		SMC_RMI_CALL(0x018e)
+
+#define SMC_RMI_VDEV_GET_INTERFACE_REPORT SMC_RMI_CALL(0x01d0)
+#define SMC_RMI_VDEV_GET_MEASUREMENTS	SMC_RMI_CALL(0x01d1)
+#define SMC_RMI_VDEV_LOCK		SMC_RMI_CALL(0x01d2)
+#define SMC_RMI_VDEV_START		SMC_RMI_CALL(0x01d3)
+#define SMC_RMI_VDEV_P2P_BIND		SMC_RMI_CALL(0x01d4)
+#define SMC_RMI_VDEV_P2P_UNBIND		SMC_RMI_CALL(0x01d5)
 
 #define RMI_ABI_MAJOR_VERSION	1
-#define RMI_ABI_MINOR_VERSION	0
+#define RMI_ABI_MINOR_VERSION	1
 
 #define RMI_ABI_VERSION_GET_MAJOR(version) ((version) >> 16)
 #define RMI_ABI_VERSION_GET_MINOR(version) ((version) & 0xFFFF)
@@ -64,11 +108,15 @@
 #define RMI_ERROR_REALM		2
 #define RMI_ERROR_REC		3
 #define RMI_ERROR_RTT		4
+#define RMI_ERROR_NOT_SUPPORTED	5
+#define RMI_ERROR_DEVICE	6
+#define RMI_ERROR_RTT_AUX	7
 
 enum rmi_ripas {
 	RMI_EMPTY = 0,
 	RMI_RAM = 1,
 	RMI_DESTROYED = 2,
+	RMI_DEV = 3,
 };
 
 #define RMI_NO_MEASURE_CONTENT	0
@@ -86,11 +134,31 @@ enum rmi_ripas {
 #define RMI_FEATURE_REGISTER_0_HASH_SHA_512	BIT(33)
 #define RMI_FEATURE_REGISTER_0_GICV3_NUM_LRS	GENMASK(37, 34)
 #define RMI_FEATURE_REGISTER_0_MAX_RECS_ORDER	GENMASK(41, 38)
-#define RMI_FEATURE_REGISTER_0_Reserved		GENMASK(63, 42)
+#define RMI_FEATURE_REGISTER_0_DA		BIT(42)
+#define RMI_FEATURE_REGISTER_0_RTT_PLANE	GENMASK(44, 43)
+#define RMI_FEATURE_REGISTER_0_MAX_NUM_AUX_PLANES GENMASK(48, 45)
+#define RMI_FEATURE_REGISTER_0_RTT_S2AP_INDIRECT BIT(49)
+#define RMI_FEATURE_REGISTER_0_Reserved		GENMASK(63, 50)
+
+#define RMI_RTT_PLANE_AUX		0
+#define RMI_RTT_PLANE_AUX_SINGLE	1
+#define RMI_RTT_PLANE_SINGLE		2
 
 #define RMI_REALM_PARAM_FLAG_LPA2		BIT(0)
 #define RMI_REALM_PARAM_FLAG_SVE		BIT(1)
 #define RMI_REALM_PARAM_FLAG_PMU		BIT(2)
+#define RMI_REALM_PARAM_FLAG_DA			BIT(3)
+#define RMI_REALM_PARAM_FLAG_LFA_POLICY		GENMASK(6, 5)
+
+#define RMI_REALM_PARAM_FLAG1_RTT_TREE_PP	BIT(0)
+#define RMI_REALM_PARAM_FLAG1_RTT_S2AP_ENCODING	BIT(1)
+#define RMI_REALM_PARAM_FLAG1_ATS		BIT(2)
+
+#define RMI_BASE_PERM_NOACCESS_INDEX	0
+#define RMI_BASE_PERM_RO_INDEX		1
+#define RMI_BASE_PERM_WO_INDEX		2
+#define RMI_BASE_PERM_RW_INDEX		3
+#define RMI_BASE_PERM_RW_puX_INDEX	4
 
 /*
  * Note many of these fields are smaller than u64 but all fields have u64
@@ -106,11 +174,15 @@ struct realm_params {
 			u64 num_wps;
 			u64 pmu_num_ctrs;
 			u64 hash_algo;
+			u64 num_aux_planes;
 		};
 		u8 padding0[0x400];
 	};
 	union { /* 0x400 */
-		u8 rpv[64];
+		struct {
+			u8 rpv[64];
+			u64 ats_plane;
+		};
 		u8 padding1[0x400];
 	};
 	union { /* 0x800 */
@@ -119,8 +191,18 @@ struct realm_params {
 			u64 rtt_base;
 			s64 rtt_level_start;
 			u64 rtt_num_start;
+			u64 flags1;
+			u64 mecid;
 		};
-		u8 padding2[0x800];
+		u8 padding2[0x700];
+	};
+	union { /* 0xf00 */
+		u16 aux_vmid[3];
+		u8 padding3[0x80];
+	};
+	union { /* 0xf80 */
+		u64 aux_rtt_base[3];
+		u8 padding4[0x80];
 	};
 };
 
@@ -165,6 +247,9 @@ struct rec_params {
 #define REC_ENTER_FLAG_TRAP_WFI		BIT(2)
 #define REC_ENTER_FLAG_TRAP_WFE		BIT(3)
 #define REC_ENTER_FLAG_RIPAS_RESPONSE	BIT(4)
+#define REC_ENTER_FLAG_S2AP_RESPONSE	BIT(5)
+#define REC_ENTER_FLAG_DEV_MEM_RESPONSE	BIT(6)
+#define REC_ENTER_FLAG_FORCE_P0		BIT(7)
 
 #define REC_RUN_GPRS			31
 #define REC_MAX_GIC_NUM_LRS		16
@@ -204,6 +289,10 @@ struct rec_enter {
 #define RMI_EXIT_RIPAS_CHANGE		0x04
 #define RMI_EXIT_HOST_CALL		0x05
 #define RMI_EXIT_SERROR			0x06
+#define RMI_EXIT_S2AP_CHANGE		0x07
+#define RMI_EXIT_VDEV_REQUEST		0x08
+#define RMI_EXIT_VDEV_COMM		0x09
+#define RMI_EXIT_DEV_MEM_MAP		0x0a
 
 struct rec_exit {
 	union { /* 0x000 */
@@ -215,6 +304,8 @@ struct rec_exit {
 			u64 esr;
 			u64 far;
 			u64 hpfar;
+			u64 rtt_tree;
+			s64 rtt_level;
 		};
 		u8 padding1[0x100];
 	};
@@ -246,11 +337,25 @@ struct rec_exit {
 			u64 ripas_top;
 			u8 ripas_value;
 			u8 padding8[7];
+			u64 padding_518;
+			u64 s2ap_base;
+			u64 s2ap_top;
+			u64 vdev_id;
 		};
 		u8 padding5[0x100];
 	};
 	union { /* 0x600 */
-		u16 imm;
+		struct {
+			u16 imm;
+			u16 padding_602;
+			u32 padding_604;
+			u64 plane;
+			u64 vdev;
+			u64 vdev_action;
+			u64 dev_mem_base;
+			u64 dev_mem_top;
+			u64 dev_mem_pa;
+		};
 		u8 padding6[0x100];
 	};
 	union { /* 0x700 */

---

## [3] Steven Price — 2025-09-26
*Subject: [RFC PATCH 2/5] arm64: RME: Handle auxiliary RTT trees*

When a guest is executing with multiple planes, then faults from a plane
other than a primary plane can indicate that there are missing entries
in the auxiliary RTT trees that need to be populated. Handle this by
allocating the necessary tables.

The auxiliary trees also need to be handled when tearing down realm
resources, so in these cases iterate over the auxiliary trees to
perform the same operations as in the primary tree.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/include/asm/kvm_rme.h |   6 +
 arch/arm64/kvm/mmu.c             |  15 ++-
 arch/arm64/kvm/rme-exit.c        |   6 +-
 arch/arm64/kvm/rme.c             | 206 +++++++++++++++++++++++++++++--
 4 files changed, 213 insertions(+), 20 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index 3ed04b309cda..e5c0c8274bf8 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -54,6 +54,8 @@ enum realm_state {
  * @num_aux: The number of auxiliary pages required by the RMM
  * @vmid: VMID to be used by the RMM for the realm
  * @ia_bits: Number of valid Input Address bits in the IPA
+ * @num_aux_planes: Number of auxiliary planes
+ * @rtt_tree_pp: True if each plane has its own RTT tree
  */
 struct realm {
 	enum realm_state state;
@@ -64,6 +66,8 @@ struct realm {
 	unsigned long num_aux;
 	unsigned int vmid;
 	unsigned int ia_bits;
+	unsigned int num_aux_planes;
+	bool rtt_tree_pp;
 };
 
 /**
@@ -107,6 +111,8 @@ int kvm_rec_enter(struct kvm_vcpu *vcpu);
 int kvm_rec_pre_enter(struct kvm_vcpu *vcpu);
 int handle_rec_exit(struct kvm_vcpu *vcpu, int rec_run_status);
 
+int realm_aux_map(struct kvm_vcpu *vcpu, phys_addr_t ipa);
+
 void kvm_realm_unmap_range(struct kvm *kvm,
 			   unsigned long ipa,
 			   unsigned long size,
diff --git a/arch/arm64/kvm/mmu.c b/arch/arm64/kvm/mmu.c
index a36ece6c3bf2..a433926e214b 100644
--- a/arch/arm64/kvm/mmu.c
+++ b/arch/arm64/kvm/mmu.c
@@ -1502,11 +1502,12 @@ static bool kvm_vma_mte_allowed(struct vm_area_struct *vma)
 	return vma->vm_flags & VM_MTE_ALLOWED;
 }
 
-static int realm_map_ipa(struct kvm *kvm, phys_addr_t ipa,
+static int realm_map_ipa(struct kvm_vcpu *vcpu, phys_addr_t ipa,
 			 kvm_pfn_t pfn, unsigned long map_size,
 			 enum kvm_pgtable_prot prot,
 			 struct kvm_mmu_memory_cache *memcache)
 {
+	struct kvm *kvm = vcpu->kvm;
 	struct realm *realm = &kvm->arch.realm;
 
 	/*
@@ -1517,6 +1518,14 @@ static int realm_map_ipa(struct kvm *kvm, phys_addr_t ipa,
 	if (WARN_ON(!(prot & KVM_PGTABLE_PROT_W)))
 		return -EFAULT;
 
+	if (vcpu->arch.rec.run->exit.rtt_tree > 0) {
+		int ret;
+
+		ret = realm_aux_map(vcpu, ipa);
+		if (ret <= 0)
+			return ret;
+	}
+
 	ipa = ALIGN_DOWN(ipa, PAGE_SIZE);
 	if (!kvm_realm_is_private_address(realm, ipa))
 		return realm_map_non_secure(realm, ipa, pfn, map_size,
@@ -1571,7 +1580,7 @@ static int private_memslot_fault(struct kvm_vcpu *vcpu,
 		return ret;
 
 	/* FIXME: Should be able to use bigger than PAGE_SIZE mappings */
-	ret = realm_map_ipa(kvm, fault_ipa, pfn, PAGE_SIZE, KVM_PGTABLE_PROT_W,
+	ret = realm_map_ipa(vcpu, fault_ipa, pfn, PAGE_SIZE, KVM_PGTABLE_PROT_W,
 			    memcache);
 	if (!ret)
 		return 1; /* Handled */
@@ -1917,7 +1926,7 @@ static int user_mem_abort(struct kvm_vcpu *vcpu, phys_addr_t fault_ipa,
 		prot &= ~KVM_NV_GUEST_MAP_SZ;
 		ret = KVM_PGT_FN(kvm_pgtable_stage2_relax_perms)(pgt, fault_ipa, prot, flags);
 	} else if (kvm_is_realm(kvm)) {
-		ret = realm_map_ipa(kvm, fault_ipa, pfn, vma_pagesize,
+		ret = realm_map_ipa(vcpu, fault_ipa, pfn, vma_pagesize,
 				    prot, memcache);
 	} else {
 		ret = KVM_PGT_FN(kvm_pgtable_stage2_map)(pgt, fault_ipa, vma_pagesize,
diff --git a/arch/arm64/kvm/rme-exit.c b/arch/arm64/kvm/rme-exit.c
index 1a8ca7526863..04c8af8642af 100644
--- a/arch/arm64/kvm/rme-exit.c
+++ b/arch/arm64/kvm/rme-exit.c
@@ -44,11 +44,7 @@ static int rec_exit_sync_dabt(struct kvm_vcpu *vcpu)
 
 static int rec_exit_sync_iabt(struct kvm_vcpu *vcpu)
 {
-	struct realm_rec *rec = &vcpu->arch.rec;
-
-	vcpu_err(vcpu, "Unhandled instruction abort (ESR: %#llx).\n",
-		 rec->run->exit.esr);
-	return -ENXIO;
+	return kvm_handle_guest_abort(vcpu);
 }
 
 static int rec_exit_sys_reg(struct kvm_vcpu *vcpu)
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 299473298720..c420546d26f3 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -225,6 +225,17 @@ static int realm_rtt_create(struct realm *realm,
 	return rmi_rtt_create(virt_to_phys(realm->rd), phys, addr, level);
 }
 
+static int realm_rtt_aux_create(struct realm *realm,
+				unsigned long addr,
+				int level,
+				phys_addr_t phys,
+				int rtt_tree_idx)
+{
+	addr = ALIGN_DOWN(addr, rme_rtt_level_mapsize(level - 1));
+	return rmi_rtt_aux_create(virt_to_phys(realm->rd), phys, addr, level,
+				  rtt_tree_idx);
+}
+
 static int realm_rtt_fold(struct realm *realm,
 			  unsigned long addr,
 			  int level,
@@ -244,13 +255,17 @@ static int realm_rtt_fold(struct realm *realm,
 
 static int realm_rtt_destroy(struct realm *realm, unsigned long addr,
 			     int level, phys_addr_t *rtt_granule,
-			     unsigned long *next_addr)
+			     unsigned long *next_addr, int rtt_tree_idx)
 {
 	unsigned long out_rtt;
 	int ret;
 
-	ret = rmi_rtt_destroy(virt_to_phys(realm->rd), addr, level,
-			      &out_rtt, next_addr);
+	if (rtt_tree_idx == 0)
+		ret = rmi_rtt_destroy(virt_to_phys(realm->rd), addr, level,
+				      &out_rtt, next_addr);
+	else
+		ret = rmi_rtt_aux_destroy(virt_to_phys(realm->rd), addr, level,
+					  rtt_tree_idx, &out_rtt, next_addr);
 
 	*rtt_granule = out_rtt;
 
@@ -289,8 +304,44 @@ static int realm_create_rtt_levels(struct realm *realm,
 	return 0;
 }
 
+static int realm_create_rtt_aux_levels(struct realm *realm,
+				       unsigned long ipa,
+				       int level,
+				       int max_level,
+				       int tree_idx,
+				       struct kvm_mmu_memory_cache *mc)
+{
+	if (level == max_level)
+		return 0;
+	if (tree_idx == 0)
+		return realm_create_rtt_levels(realm, ipa,
+					       level, max_level, mc);
+
+	while (level++ < max_level) {
+		phys_addr_t rtt = alloc_delegated_granule(mc);
+		int ret;
+
+		if (rtt == PHYS_ADDR_MAX)
+			return -ENOMEM;
+
+		ret = realm_rtt_aux_create(realm, ipa, level, rtt, tree_idx);
+
+		if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT_AUX &&
+		    RMI_RETURN_INDEX(ret) == level - 1) {
+			/* The RTT already exists, continue */
+			continue;
+		} else if (RMI_RETURN_STATUS(ret) != RMI_SUCCESS) {
+			free_delegated_granule(rtt);
+			return -ENXIO;
+		}
+	}
+
+	return 0;
+}
+
 static int realm_tear_down_rtt_level(struct realm *realm, int level,
-				     unsigned long start, unsigned long end)
+				     unsigned long start, unsigned long end,
+				     int rtt_tree_idx)
 {
 	ssize_t map_size;
 	unsigned long addr, next_addr;
@@ -315,20 +366,22 @@ static int realm_tear_down_rtt_level(struct realm *realm, int level,
 			ret = realm_tear_down_rtt_level(realm,
 							level + 1,
 							addr,
-							min(next_addr, end));
+							min(next_addr, end),
+							rtt_tree_idx);
 			if (ret)
 				return ret;
 			continue;
 		}
 
 		ret = realm_rtt_destroy(realm, addr, level,
-					&rtt_granule, &next_addr);
+					&rtt_granule, &next_addr, rtt_tree_idx);
 
 		switch (RMI_RETURN_STATUS(ret)) {
 		case RMI_SUCCESS:
 			free_rtt(rtt_granule);
 			break;
 		case RMI_ERROR_RTT:
+		case RMI_ERROR_RTT_AUX:
 			if (next_addr > addr) {
 				/* Missing RTT, skip */
 				break;
@@ -354,7 +407,8 @@ static int realm_tear_down_rtt_level(struct realm *realm, int level,
 			ret = realm_tear_down_rtt_level(realm,
 							level + 1,
 							addr,
-							next_addr);
+							next_addr,
+							rtt_tree_idx);
 			if (ret)
 				return ret;
 			/*
@@ -372,15 +426,52 @@ static int realm_tear_down_rtt_level(struct realm *realm, int level,
 	return 0;
 }
 
-static int realm_tear_down_rtt_range(struct realm *realm,
-				     unsigned long start, unsigned long end)
+static void realm_unmap_aux_unprotected(struct realm *realm,
+					unsigned long start,
+					unsigned long end,
+					int rtt_tree_idx)
 {
+	unsigned long rd = virt_to_phys(realm->rd);
+	unsigned long next;
+	int ret;
+
+	while (start < end) {
+		ret = rmi_rtt_aux_unmap_unprotected(rd, start, rtt_tree_idx,
+						    &next);
+
+		if (WARN_ON(ret))
+			return;
+
+		start = next;
+	}
+}
+
+static void realm_tear_down_rtt_range(struct realm *realm, u32 ia_bits,
+				      int rtt_tree_idx)
+{
+	int ret;
+	int sl = get_start_level(realm);
+	unsigned long end = 1UL << ia_bits;
+
+	if (rtt_tree_idx) {
+		unsigned long start = end >> 1;
+
+		/*
+		 * AUX trees cannot destroy the RTTs in the unprotected region,
+		 * instead we must unmap the region.
+		 */
+		realm_unmap_aux_unprotected(realm, start, end, rtt_tree_idx);
+		end = start;
+	}
+
 	/*
 	 * Root level RTTs can only be destroyed after the RD is destroyed. So
 	 * tear down everything below the root level
 	 */
-	return realm_tear_down_rtt_level(realm, get_start_level(realm) + 1,
-					 start, end);
+	ret = realm_tear_down_rtt_level(realm, sl + 1,
+					0, end, rtt_tree_idx);
+
+	WARN_ON(ret);
 }
 
 /*
@@ -443,7 +534,14 @@ void kvm_realm_destroy_rtts(struct kvm *kvm, u32 ia_bits)
 {
 	struct realm *realm = &kvm->arch.realm;
 
-	WARN_ON(realm_tear_down_rtt_range(realm, 0, (1UL << ia_bits)));
+	if (realm->rtt_tree_pp) {
+		int idx;
+
+		for (idx = 1; idx <= realm->num_aux_planes; idx++)
+			realm_tear_down_rtt_range(realm, ia_bits, idx);
+	}
+
+	realm_tear_down_rtt_range(realm, ia_bits, 0);
 }
 
 static int realm_destroy_private_granule(struct realm *realm,
@@ -476,6 +574,17 @@ static int realm_destroy_private_granule(struct realm *realm,
 			return -ENXIO;
 		}
 		goto retry;
+	} else if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT_AUX) {
+		int idx;
+
+		WARN_ON(!realm->rtt_tree_pp);
+
+		for (idx = 1; idx <= realm->num_aux_planes; idx++) {
+			ret = rmi_rtt_aux_unmap_protected(rd, ipa, idx, NULL);
+			if (WARN_ON(ret))
+				return -1;
+		}
+		goto retry;
 	} else if (WARN_ON(ret)) {
 		return -ENXIO;
 	}
@@ -1100,6 +1209,79 @@ static int populate_region(struct kvm *kvm,
 	return ret;
 }
 
+/*
+ * Return values:
+ *  0: Success
+ *  1: Primary RTT is invalid at IPA
+ * <0: Error
+ */
+int realm_aux_map(struct kvm_vcpu *vcpu, phys_addr_t ipa)
+{
+	int ret;
+	int level, max_level;
+	struct kvm_mmu_memory_cache *mc = &vcpu->arch.mmu_page_cache;
+	struct realm *realm = &vcpu->kvm->arch.realm;
+	phys_addr_t rd = virt_to_phys(realm->rd);
+	unsigned long rtt_tree_idx = vcpu->arch.rec.run->exit.rtt_tree;
+
+	kvm_mmu_topup_memory_cache(mc, kvm_mmu_cache_min_pages(vcpu->arch.hw_mmu));
+
+loop:
+	if (kvm_realm_is_private_address(realm, ipa)) {
+		ret = rmi_rtt_aux_map_protected(rd, ipa, rtt_tree_idx,
+						NULL, NULL);
+	} else {
+		int sl = get_start_level(realm);
+		unsigned long esr = vcpu->arch.rec.run->exit.esr;
+
+		if (WARN_ON(!esr_is_data_abort(esr) ||
+			    !esr_fsc_is_translation_fault(esr)))
+			return -EINVAL;
+
+		if ((esr & ESR_ELx_FSC) != ESR_ELx_FSC_FAULT_L(sl)) {
+			/*
+			 * Unprotected AUX RTT trees are shared. So if the
+			 * level is not at the start level the fault must be
+			 * due to a missing primary RTT (not an AUX RTT).
+			 */
+			return 1;
+		}
+		/* For the AUX RTT the IPA needs aligning to the start level. */
+		ipa = ALIGN_DOWN(ipa, rme_rtt_level_mapsize(sl));
+		ret = rmi_rtt_aux_map_unprotected(rd, ipa, rtt_tree_idx);
+	}
+
+	switch (RMI_RETURN_STATUS(ret)) {
+	case RMI_SUCCESS:
+		return 0;
+	case RMI_ERROR_RTT:
+		return 1;
+	case RMI_ERROR_RTT_AUX:
+		/*
+		 * Attempt to create RTTs and try again.
+		 * Try to block level first.
+		 */
+		level = RMI_RETURN_INDEX(ret);
+		if (level < RMM_RTT_BLOCK_LEVEL)
+			max_level = RMM_RTT_BLOCK_LEVEL;
+		else
+			max_level = RMM_RTT_MAX_LEVEL;
+
+		ret = realm_create_rtt_aux_levels(realm, ipa,
+						  level, max_level,
+						  rtt_tree_idx, mc);
+		if (WARN_ON(ret))
+			return -EIO;
+		goto loop;
+	default:
+		WARN_ON(1);
+		ret = -EIO;
+	}
+
+	WARN_ON(1);
+	return -EIO;
+}
+
 static int kvm_populate_realm(struct kvm *kvm,
 			      struct arm_rme_populate_realm *args)
 {

---

## [4] Steven Price — 2025-09-26
*Subject: [RFC PATCH 3/5] arm64: RME: Support RMI_EXIT_S2AP_CHANGE*

If the primary plane of a realm wishes to change the access permissions
of memory for the other planes then this causes an exit to the normal
world. KVM then must complete the request using RMI_RTT_SET_S2AP which
may fail if there are missing RTTs. In this case KVM must allocate the
missing RTTs and retry.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/include/asm/kvm_rme.h |  3 +++
 arch/arm64/kvm/rme-exit.c        | 27 +++++++++++++++++++++++++++
 arch/arm64/kvm/rme.c             | 25 +++++++++++++++++++++----
 3 files changed, 51 insertions(+), 4 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index e5c0c8274bf8..934b30a8e607 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -112,6 +112,9 @@ int kvm_rec_pre_enter(struct kvm_vcpu *vcpu);
 int handle_rec_exit(struct kvm_vcpu *vcpu, int rec_run_status);
 
 int realm_aux_map(struct kvm_vcpu *vcpu, phys_addr_t ipa);
+int kvm_realm_set_s2ap(struct kvm_vcpu *vcpu,
+		       unsigned long start,
+		       unsigned long end);
 
 void kvm_realm_unmap_range(struct kvm *kvm,
 			   unsigned long ipa,
diff --git a/arch/arm64/kvm/rme-exit.c b/arch/arm64/kvm/rme-exit.c
index 04c8af8642af..b7e615f7b3a9 100644
--- a/arch/arm64/kvm/rme-exit.c
+++ b/arch/arm64/kvm/rme-exit.c
@@ -112,6 +112,31 @@ static int rec_exit_ripas_change(struct kvm_vcpu *vcpu)
 	return -EFAULT;
 }
 
+static int rec_exit_s2ap_change(struct kvm_vcpu *vcpu)
+{
+	struct kvm *kvm = vcpu->kvm;
+	struct realm *realm = &kvm->arch.realm;
+	struct realm_rec *rec = &vcpu->arch.rec;
+	unsigned long base = rec->run->exit.s2ap_base;
+	unsigned long top = rec->run->exit.s2ap_top;
+	int ret = -EINVAL;
+
+	if (kvm_realm_is_private_address(realm, base) &&
+	    kvm_realm_is_private_address(realm, top)) {
+		kvm_mmu_topup_memory_cache(&vcpu->arch.mmu_page_cache,
+					   kvm_mmu_cache_min_pages(vcpu->arch.hw_mmu));
+		write_lock(&kvm->mmu_lock);
+		ret = kvm_realm_set_s2ap(vcpu, base, top);
+		write_unlock(&kvm->mmu_lock);
+	}
+
+	WARN_RATELIMIT(ret && ret != -ENOMEM,
+		       "Unable to satisfy SET_S2AP for %#lx - %#lx\n",
+		       base, top);
+
+	return 1;
+}
+
 static int rec_exit_host_call(struct kvm_vcpu *vcpu)
 {
 	int i;
@@ -192,6 +217,8 @@ int handle_rec_exit(struct kvm_vcpu *vcpu, int rec_run_ret)
 		return rec_exit_psci(vcpu);
 	case RMI_EXIT_RIPAS_CHANGE:
 		return rec_exit_ripas_change(vcpu);
+	case RMI_EXIT_S2AP_CHANGE:
+		return rec_exit_s2ap_change(vcpu);
 	case RMI_EXIT_HOST_CALL:
 		return rec_exit_host_call(vcpu);
 	}
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index c420546d26f3..fa39a8393d53 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -1329,6 +1329,7 @@ static int kvm_populate_realm(struct kvm *kvm,
 enum ripas_action {
 	RIPAS_INIT,
 	RIPAS_SET,
+	SET_S2AP,
 };
 
 static int ripas_change(struct kvm *kvm,
@@ -1348,12 +1349,13 @@ static int ripas_change(struct kvm *kvm,
 		rec_phys = virt_to_phys(vcpu->arch.rec.rec_page);
 		memcache = &vcpu->arch.mmu_page_cache;
 
-		WARN_ON(action != RIPAS_SET);
+		WARN_ON(action == RIPAS_INIT);
 	} else {
 		WARN_ON(action != RIPAS_INIT);
 	}
 
 	while (ipa < end) {
+		unsigned long rtt_tree_idx = 0;
 		unsigned long next;
 
 		switch (action) {
@@ -1364,21 +1366,27 @@ static int ripas_change(struct kvm *kvm,
 			ret = rmi_rtt_set_ripas(rd_phys, rec_phys, ipa, end,
 						&next);
 			break;
+		case SET_S2AP:
+			ret = rmi_rtt_set_s2ap(rd_phys, rec_phys, ipa, end,
+					       &next, &rtt_tree_idx);
+			break;
 		}
 
 		switch (RMI_RETURN_STATUS(ret)) {
 		case RMI_SUCCESS:
 			ipa = next;
 			break;
-		case RMI_ERROR_RTT: {
+		case RMI_ERROR_RTT:
+		case RMI_ERROR_RTT_AUX: {
 			int err_level = RMI_RETURN_INDEX(ret);
 			int level = find_map_level(realm, ipa, end);
 
 			if (err_level >= level)
 				return -EINVAL;
 
-			ret = realm_create_rtt_levels(realm, ipa, err_level,
-						      level, memcache);
+			ret = realm_create_rtt_aux_levels(realm, ipa, err_level,
+							  level, rtt_tree_idx,
+							  memcache);
 			if (ret)
 				return ret;
 			/* Retry with the RTT levels in place */
@@ -1396,6 +1404,15 @@ static int ripas_change(struct kvm *kvm,
 	return 0;
 }
 
+int kvm_realm_set_s2ap(struct kvm_vcpu *vcpu,
+		       unsigned long start,
+		       unsigned long end)
+{
+	struct kvm *kvm = vcpu->kvm;
+
+	return ripas_change(kvm, vcpu, start, end, SET_S2AP, NULL);
+}
+
 static int realm_set_ipa_state(struct kvm_vcpu *vcpu,
 			       unsigned long start,
 			       unsigned long end,

---

## [5] Steven Price — 2025-09-26
*Subject: [RFC PATCH 4/5] arm64: rme: Allocate AUX RTT PGDs and VMIDs*

If using multiple planes then the auxiliary trees also need PGDs
allocating for them. Each plane also needs its own VMID.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/include/asm/kvm_rme.h |   4 +-
 arch/arm64/kvm/rme.c             | 133 +++++++++++++++++++++++++++----
 2 files changed, 122 insertions(+), 15 deletions(-)

diff --git a/arch/arm64/include/asm/kvm_rme.h b/arch/arm64/include/asm/kvm_rme.h
index 934b30a8e607..a9dc24a53c65 100644
--- a/arch/arm64/include/asm/kvm_rme.h
+++ b/arch/arm64/include/asm/kvm_rme.h
@@ -53,6 +53,7 @@ enum realm_state {
  * @params: Parameters for the RMI_REALM_CREATE command
  * @num_aux: The number of auxiliary pages required by the RMM
  * @vmid: VMID to be used by the RMM for the realm
+ * @aux_pgd: The PGDs for the auxiliary planes
  * @ia_bits: Number of valid Input Address bits in the IPA
  * @num_aux_planes: Number of auxiliary planes
  * @rtt_tree_pp: True if each plane has its own RTT tree
@@ -64,7 +65,8 @@ struct realm {
 	struct realm_params *params;
 
 	unsigned long num_aux;
-	unsigned int vmid;
+	unsigned int vmid[4];
+	void *aux_pgd[3];
 	unsigned int ia_bits;
 	unsigned int num_aux_planes;
 	bool rtt_tree_pp;
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index fa39a8393d53..6cb938957510 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -782,10 +782,17 @@ static int realm_create_rd(struct kvm *kvm)
 	params->rtt_level_start = get_start_level(realm);
 	params->rtt_num_start = rtt_num_start;
 	params->rtt_base = kvm->arch.mmu.pgd_phys;
-	params->vmid = realm->vmid;
+	params->vmid = realm->vmid[0];
+	for (int plane = 0; plane < realm->num_aux_planes; plane++)
+		params->aux_vmid[plane] = realm->vmid[plane + 1];
 	params->num_bps = SYS_FIELD_GET(ID_AA64DFR0_EL1, BRPs, dfr0);
 	params->num_wps = SYS_FIELD_GET(ID_AA64DFR0_EL1, WRPs, dfr0);
 
+	if (realm->rtt_tree_pp) {
+		for (int plane = 0; plane < realm->num_aux_planes; plane++)
+			params->aux_rtt_base[plane] = virt_to_phys(realm->aux_pgd[plane]);
+	}
+
 	if (kvm->arch.arm_pmu) {
 		params->pmu_num_ctrs = kvm->arch.nr_pmu_counters;
 		params->flags |= RMI_REALM_PARAM_FLAG_PMU;
@@ -1483,25 +1490,117 @@ static int rme_vmid_init(void)
 	return 0;
 }
 
-static int rme_vmid_reserve(void)
+static int rme_vmids_reserve(unsigned int *vmids, int count)
 {
-	int ret;
+	int ret = 0;
+	int vmid;
+	int i;
 	unsigned int vmid_count = 1 << kvm_get_vmid_bits();
 
 	spin_lock(&rme_vmid_lock);
-	ret = bitmap_find_free_region(rme_vmid_bitmap, vmid_count, 0);
+	for (i = 0; i < count; i++) {
+		vmid = bitmap_find_free_region(rme_vmid_bitmap, vmid_count, 0);
+		if (vmid < 0) {
+			while (i > 0) {
+				i--;
+				bitmap_release_region(rme_vmid_bitmap,
+						      vmids[i], 0);
+			}
+			ret = -EBUSY;
+			break;
+		}
+		vmids[i] = vmid;
+	}
 	spin_unlock(&rme_vmid_lock);
 
 	return ret;
 }
 
-static void rme_vmid_release(unsigned int vmid)
+static void rme_vmids_release(unsigned int *vmids, int count)
 {
+	int i;
+
 	spin_lock(&rme_vmid_lock);
-	bitmap_release_region(rme_vmid_bitmap, vmid, 0);
+	for (i = 0; i < count; i++)
+		bitmap_release_region(rme_vmid_bitmap, vmids[i], 0);
 	spin_unlock(&rme_vmid_lock);
 }
 
+static void rme_free_aux_pgds(struct kvm *kvm)
+{
+	size_t pgd_size = kvm_pgtable_stage2_pgd_size(kvm->arch.mmu.vtcr);
+	struct realm *realm = &kvm->arch.realm;
+	int plane, i;
+
+	for (plane = 0; plane < realm->num_aux_planes; plane++) {
+		phys_addr_t pgd_phys;
+		int ret = 0;
+
+		if (!realm->aux_pgd[plane])
+			continue;
+
+		pgd_phys = virt_to_phys(realm->aux_pgd[plane]);
+
+		for (i = 0; i < pgd_size; i += RMM_PAGE_SIZE) {
+			phys_addr_t table_phys = pgd_phys + i;
+
+			if (WARN_ON(rmi_granule_undelegate(table_phys))) {
+				ret = -ENXIO;
+				break;
+			}
+		}
+		if (ret == 0)
+			free_pages_exact(realm->aux_pgd[plane], pgd_size);
+	}
+}
+
+static int rme_alloc_aux_pgds(struct kvm *kvm)
+{
+	size_t pgd_size = kvm_pgtable_stage2_pgd_size(kvm->arch.mmu.vtcr);
+	struct realm *realm = &kvm->arch.realm;
+	phys_addr_t pgd_phys;
+	void *aux_pages;
+	int plane, i;
+	int ret;
+
+	for (plane = 0; plane < realm->num_aux_planes; plane++) {
+		aux_pages = alloc_pages_exact(pgd_size,
+					      GFP_KERNEL_ACCOUNT | __GFP_ZERO);
+		if (!aux_pages) {
+			ret = -ENOMEM;
+			goto err_alloc;
+		}
+		realm->aux_pgd[plane] = aux_pages;
+
+		pgd_phys = virt_to_phys(realm->aux_pgd[plane]);
+
+		for (i = 0; i < pgd_size; i += RMM_PAGE_SIZE) {
+			if (rmi_granule_delegate(pgd_phys + i)) {
+				ret = -ENXIO;
+				goto err_delegate;
+			}
+		}
+	}
+	return 0;
+
+err_delegate:
+	while (i > 0) {
+		i -= RMM_PAGE_SIZE;
+
+		if (WARN_ON(rmi_granule_undelegate(pgd_phys + i))) {
+			/* Leak the pages */
+			goto err_undelegate_failed;
+		}
+	}
+
+	free_pages_exact(realm->aux_pgd[plane], pgd_size);
+err_undelegate_failed:
+	realm->aux_pgd[plane] = NULL;
+err_alloc:
+	rme_free_aux_pgds(kvm);
+	return ret;
+}
+
 static int kvm_create_realm(struct kvm *kvm)
 {
 	struct realm *realm = &kvm->arch.realm;
@@ -1510,16 +1609,17 @@ static int kvm_create_realm(struct kvm *kvm)
 	if (kvm_realm_is_created(kvm))
 		return -EEXIST;
 
-	ret = rme_vmid_reserve();
-	if (ret < 0)
+	ret = rme_vmids_reserve(realm->vmid, realm->num_aux_planes + 1);
+	if (ret)
 		return ret;
-	realm->vmid = ret;
+
+	ret = rme_alloc_aux_pgds(kvm);
+	if (ret)
+		goto error_release_vmids;
 
 	ret = realm_create_rd(kvm);
-	if (ret) {
-		rme_vmid_release(realm->vmid);
-		return ret;
-	}
+	if (ret)
+		goto error_release_vmids;
 
 	WRITE_ONCE(realm->state, REALM_STATE_NEW);
 
@@ -1528,6 +1628,10 @@ static int kvm_create_realm(struct kvm *kvm)
 	realm->params = NULL;
 
 	return 0;
+
+error_release_vmids:
+	rme_vmids_release(realm->vmid, realm->num_aux_planes + 1);
+	return ret;
 }
 
 static int config_realm_hash_algo(struct realm *realm,
@@ -1649,7 +1753,8 @@ void kvm_destroy_realm(struct kvm *kvm)
 		realm->rd = NULL;
 	}
 
-	rme_vmid_release(realm->vmid);
+	rme_free_aux_pgds(kvm);
+	rme_vmids_release(realm->vmid, realm->num_aux_planes + 1);
 
 	for (i = 0; i < pgd_size; i += RMM_PAGE_SIZE) {
 		phys_addr_t pgd_phys = kvm->arch.mmu.pgd_phys + i;

---

## [6] Steven Price — 2025-09-26
*Subject: [RFC PATCH 5/5] arm64: RME: Support num_aux_places & rtt_tree_pp realm parameters*

CCA planes provides new parameters to the VMM:
 - num_aux_planes defines the number of extra planes
 - rtt_tree_pp controls whether each plane has it's own page table tree,
   of if they share one tree.

Signed-off-by: Steven Price <steven.price@arm.com>
---
 arch/arm64/include/uapi/asm/kvm.h | 12 +++++
 arch/arm64/kvm/rme.c              | 77 +++++++++++++++++++++++++++++--
 2 files changed, 86 insertions(+), 3 deletions(-)

diff --git a/arch/arm64/include/uapi/asm/kvm.h b/arch/arm64/include/uapi/asm/kvm.h
index 9b5d67ecbc5e..1d83da0f3aaa 100644
--- a/arch/arm64/include/uapi/asm/kvm.h
+++ b/arch/arm64/include/uapi/asm/kvm.h
@@ -440,6 +440,8 @@ enum {
 /* List of configuration items accepted for KVM_CAP_ARM_RME_CONFIG_REALM */
 #define ARM_RME_CONFIG_RPV			0
 #define ARM_RME_CONFIG_HASH_ALGO		1
+#define ARM_RME_CONFIG_NUM_AUX_PLANES		2
+#define ARM_RME_CONFIG_RTT_TREE_PP		3
 
 #define ARM_RME_CONFIG_HASH_ALGO_SHA256		0
 #define ARM_RME_CONFIG_HASH_ALGO_SHA512		1
@@ -459,6 +461,16 @@ struct arm_rme_config {
 			__u32	hash_algo;
 		};
 
+		/* cfg == ARM_RME_CONFIG_NUM_AUX_PLANES */
+		struct {
+			__u32	num_aux_planes;
+		};
+
+		/* cfg == ARM_RME_CONFIG_RTT_TREE_PP */
+		struct {
+			__u32	rtt_tree_pp;
+		};
+
 		/* Fix the size of the union */
 		__u8	reserved[256];
 	};
diff --git a/arch/arm64/kvm/rme.c b/arch/arm64/kvm/rme.c
index 6cb938957510..fca305da1843 100644
--- a/arch/arm64/kvm/rme.c
+++ b/arch/arm64/kvm/rme.c
@@ -43,6 +43,28 @@ bool kvm_rme_supports_sve(void)
 	return rme_has_feature(RMI_FEATURE_REGISTER_0_SVE_EN);
 }
 
+static bool kvm_rme_supports_rtt_tree_single(void)
+{
+	int i = u64_get_bits(rmm_feat_reg0, RMI_FEATURE_REGISTER_0_RTT_PLANE);
+
+	switch (i) {
+	case RMI_RTT_PLANE_AUX:
+		return false;
+	case RMI_RTT_PLANE_AUX_SINGLE:
+	case RMI_RTT_PLANE_SINGLE:
+		return true;
+	default:
+		WARN(1, "Unknown encoding for RMI_FEATURE_REGISTER_0_RTT_PLANE: %#x", i);
+	}
+	return false;
+}
+
+static unsigned int rme_get_max_num_aux_planes(void)
+{
+	return u64_get_bits(rmm_feat_reg0,
+			    RMI_FEATURE_REGISTER_0_MAX_NUM_AUX_PLANES);
+}
+
 static int rmi_check_version(void)
 {
 	struct arm_smccc_res res;
@@ -1077,6 +1099,14 @@ int realm_map_protected(struct realm *realm,
 	return -ENXIO;
 }
 
+static unsigned long pi_index_to_s2tte(unsigned long idx)
+{
+	return FIELD_PREP(BIT(PTE_PI_IDX_0), (idx >> 0) & 1) |
+	       FIELD_PREP(BIT(PTE_PI_IDX_1), (idx >> 1) & 1) |
+	       FIELD_PREP(BIT(PTE_PI_IDX_2), (idx >> 2) & 1) |
+	       FIELD_PREP(BIT(PTE_PI_IDX_3), (idx >> 3) & 1);
+}
+
 int realm_map_non_secure(struct realm *realm,
 			 unsigned long ipa,
 			 kvm_pfn_t pfn,
@@ -1101,9 +1131,17 @@ int realm_map_non_secure(struct realm *realm,
 		 * so for now we permit both read and write.
 		 */
 		unsigned long desc = phys |
-				     PTE_S2_MEMATTR(MT_S2_FWB_NORMAL) |
-				     KVM_PTE_LEAF_ATTR_LO_S2_S2AP_R |
-				     KVM_PTE_LEAF_ATTR_LO_S2_S2AP_W;
+				     PTE_S2_MEMATTR(MT_S2_FWB_NORMAL);
+		/*
+		 * FIXME: Read+Write permissions for now, and no support yet
+		 * for setting RMI_REALM_PARAM_FLAG1_RTT_S2AP_ENCODING
+		 */
+		if (1)
+			desc |= KVM_PTE_LEAF_ATTR_LO_S2_S2AP_R |
+				KVM_PTE_LEAF_ATTR_LO_S2_S2AP_W;
+		else
+			desc |= pi_index_to_s2tte(RMI_BASE_PERM_RW_INDEX);
+
 		ret = rmi_rtt_map_unprotected(rd, ipa, map_level, desc);
 
 		if (RMI_RETURN_STATUS(ret) == RMI_ERROR_RTT) {
@@ -1653,6 +1691,33 @@ static int config_realm_hash_algo(struct realm *realm,
 	return 0;
 }
 
+static int config_num_aux_planes(struct realm *realm,
+				 struct arm_rme_config *cfg)
+{
+	if (cfg->num_aux_planes > rme_get_max_num_aux_planes())
+		return -EINVAL;
+
+	realm->num_aux_planes = cfg->num_aux_planes;
+	realm->params->num_aux_planes = cfg->num_aux_planes;
+
+	return 0;
+}
+
+static int config_rtt_tree_pp(struct realm *realm,
+			      struct arm_rme_config *cfg)
+{
+	if (!kvm_rme_supports_rtt_tree_single() && !cfg->rtt_tree_pp)
+		return -EINVAL;
+
+	realm->rtt_tree_pp = !!cfg->rtt_tree_pp;
+	if (realm->rtt_tree_pp)
+		realm->params->flags1 |= RMI_REALM_PARAM_FLAG1_RTT_TREE_PP;
+	else
+		realm->params->flags1 &= ~RMI_REALM_PARAM_FLAG1_RTT_TREE_PP;
+
+	return 0;
+}
+
 static int kvm_rme_config_realm(struct kvm *kvm, struct kvm_enable_cap *cap)
 {
 	struct arm_rme_config cfg;
@@ -1672,6 +1737,12 @@ static int kvm_rme_config_realm(struct kvm *kvm, struct kvm_enable_cap *cap)
 	case ARM_RME_CONFIG_HASH_ALGO:
 		r = config_realm_hash_algo(realm, &cfg);
 		break;
+	case ARM_RME_CONFIG_NUM_AUX_PLANES:
+		r = config_num_aux_planes(realm, &cfg);
+		break;
+	case ARM_RME_CONFIG_RTT_TREE_PP:
+		r = config_rtt_tree_pp(realm, &cfg);
+		break;
 	default:
 		r = -EINVAL;
 	}

---
