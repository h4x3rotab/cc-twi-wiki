---
topic_id: 115127912
subject: "Fw: MCP binding could be improved with Confidential Computing"
participants: ["Mark Novak"]
first_post: 2025-09-08
last_post: 2025-09-08
message_count: 1
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/fw_mcp_binding_could_be/115127912
---

# Fw: MCP binding could be improved with Confidential Computing

## Message 1 (#82) — Mark Novak — 2025-09-08 10:31 UTC

Forgot to cross-post as it is of interest to both SIGs.

[toggle quoted message
Show quoted text](#quoted-256923105)

---

**From:** Mark Novak <Mark.Novak@...>  
**Sent:** Monday, September 8, 2025 3:30 AM  
**To:** attestation@... <attestation@...>  
**Subject:** MCP binding could be improved with Confidential Computing

This issue was brought to my attention. Note that in the absence of TEEs, binding of MCP must be to a device.

<https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1415>

|  |  |
| --- | --- |
|  | [SEP-1415: HTTP Message Signing for MCP Client Authentication](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1415)  This SEP proposes adding HTTP Message Signing (RFC 9421) as an optional client authentication method for MCP. This provides cryptographic proof of possession, enabling MCP Servers to establish authenticated sessions with clients without relying solely on bearer tokens. The proposal maintains full ...  github.com |

|  |  |
| --- | --- |
|  | [SEP-1415: HTTP Message Signing for MCP Client Authentication](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1415)  This SEP proposes adding HTTP Message Signing (RFC 9421) as an optional client authentication method for MCP. This provides cryptographic proof of possession, enabling MCP Servers to establish authenticated sessions with clients without relying solely on bearer tokens. The proposal maintains full ...  github.com |

contentLoaded(false, function() {
$('#quoted-256923105').on('show.bs.collapse', function() {
$('#qlabel-256923105').text("Hide quoted text");
})
$('#quoted-256923105').on('hide.bs.collapse', function() {
$('#qlabel-256923105').text("Show quoted text");
})
});
