"""Model access. **The only thing left under this name, and deliberately so** (T296, ADR-0007).

Every connector that once lived here — ServiceNow, Microsoft Graph, OneLogin, Duo, the MCP client
and the per-organisation credential resolver — now belongs to the Integrations Service. RagCore
reaches no customer system; it calls that service through APIM, or dispatches over Service Bus.

**`model/` stays, and that is not an exception being carved out.** Model egress and content safety
are *reasoning*, not integration: the AI Gateway is a platform destination RagCore owns, in the same
class as its own derived index, not a customer system behind a per-organisation credential. The
distinction that decides what may live here is not "does it make an HTTP call" but "whose system is
at the other end".

The shared outbound transport and the boundary-validation rules moved to :mod:`ragcore.egress`,
because leaving them under a package named ``integrations`` would keep suggesting connectors belong
here.
"""
