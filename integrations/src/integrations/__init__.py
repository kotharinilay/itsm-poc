"""Synthia Integrations Service — **the platform's only path to any external system**.

A separate deployable, parallel to RagCore (specification §21.6,
`docs/adr/0007-integration-service-boundary.md`). RagCore reaches it two ways and no other:
synchronously through APIM, and asynchronously over Service Bus. RagCore reaches **no** external
system itself and holds **no** connector credential.

**What this service owns.** The tool catalogue, the connector registry, tenant tool
configuration, access checks, policy checks at execution time, operation execution, the MCP
client, external API calls, credential lookup, result normalization, external idempotency,
execution records, and its own telemetry, audit and trace emission.

**What it does not own, and MUST NOT implement.** User conversation, reasoning, graph
orchestration, **tool selection**, approval waiting, graph interrupt and resume,
**execution-treatment assignment**, **role-set intersection**, the conclusion drawn from
verification, the ticket-close decision, and the **atomic claim** — idempotency boundary 1
belongs with the authority record in RagCore.

**The service executes; it never decides.** It repeats every authority *fact* at the point of effect
so that a mistaken or compromised caller cannot cause an unauthorized effect, and it originates no
authorization — a second policy authority is one that can disagree with the first.

**Layering** (`integrations/tests/architecture/test_layering.py` enforces it):

```text
api → application → domain
policy | catalogue | execution → application → domain
connectors | mcp | credentials | egress | messaging | persistence
                              → implement ports declared in application
credentials ← connectors | mcp      (the ONLY path to a connector secret)
domain imports NOTHING outside the standard library
```
"""

__all__: list[str] = []
