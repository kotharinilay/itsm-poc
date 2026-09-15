# 0004. Endpoint script distribution, privilege level, and result attestation

- **Status:** Accepted
- **Date:** 2026-09-15
- **Deciders:** Platform architecture owner
- **Answers:** Specification open items **OQ-03**, **OQ-04**, **OQ-05**
- **Related:** [0002 — Approval API placement and graph resume path](0002-approval-api-placement-and-graph-resume.md)

## Context and Problem Statement

The Desktop app is, in the specification's own words, *"the platform's only execution path inside a
customer network"* and *"the highest-value target in the architecture"* (§18.6, §35.4). §18.6
establishes the controls that exist — server-side decision, platform-owned versioned catalogue, no
client policy, authenticated instruction fetch bound to the work item, mandatory consent, full command
disclosure in the approval payload, verification against real state — and then names three controls
that do **not** yet exist:

| Open item | Question |
|---|---|
| **OQ-03** | Are catalogue scripts pre-deployed with the client, fetched per execution, or both? How does the client verify integrity and provenance? |
| **OQ-04** | May a catalogue script run elevated on the endpoint, and under what treatment? |
| **OQ-05** | How much does the platform trust a result posted back by the Desktop app? |

§35.4 attaches a shipping gate to them: *"The Alpha build should not ship endpoint execution of
elevated or destructive catalogue entries until they are decided."* This ADR decides them, adopting
the specification's recommended answers in §40 with the implementation detail those answers imply.

## Decision Drivers

- The endpoint runs inside a customer network and is outside platform control. Constitution
  Principle VII: no client is a security boundary.
- A script executes with the signed-in user's local authority. The blast radius is the user's machine.
- Whatever a human approved must be exactly what executes. Anything less makes the approval
  meaningless.
- Desktop execution already requires the user present within the fifteen-minute window (§18.6), so
  connectivity at execution time can be assumed.
- The platform must not claim to know more than it does (constitution Principle VIII).

## Decision Outcome

### OQ-03 — Fetch per execution, hash-verified, no local cache

Scripts are **fetched per execution** over the authenticated Customer API, bound to the work item.
There is **no local script cache**, and scripts are not pre-deployed with the client.

A local cache is rejected outright: it can drift from the catalogue, it is writable by anything with
local access, and it turns "execute catalogue entry X" into "execute whatever is in the cache under
the name X". Removing it removes the whole class.

The authorized execution instruction binds **four** values, and the client executes only if all four
match what it fetched:

```text
work item id  +  catalogue entry id  +  entry version  +  content hash
```

The content hash is computed server-side over the exact command set, and that same command set is what
the approval payload disclosed to the human (§18.6). This is the property that matters: **the hash
binds what was approved to what is executed.** A mismatch aborts before execution and records a
security audit event.

Handling is confined to the **Electron main process**. The renderer never receives the script body,
the instruction, or the hash. The preload exposes a narrow typed `contextBridge` surface —
"execute the authorized instruction for work item W", nothing more — and the main process validates
every IPC message against it.

**Residual gap, stated plainly.** The script and its hash arrive over the same authenticated channel
from the same platform. The hash therefore protects against transport corruption and local tampering
between fetch and execution; it does **not** protect against a compromised platform API, which could
serve a malicious script and a matching hash. Closing that requires a detached signature made with a
Key Vault signing key and verified against a public key pinned in the Electron main process, so that
compromising the API alone is insufficient. That is recorded as a GA item below, not as an Alpha
control, and it must not be described as one.

### OQ-04 — No elevation in Alpha

Catalogue entries MUST declare `requires_elevation`. In Alpha the only permitted value is `false`.

- **Server-side (the boundary):** catalogue validation rejects the creation or activation of any entry
  requesting elevation. The Governance Service will not issue an execution instruction for one.
- **Client-side (a backstop, not a boundary):** the Electron main process refuses any instruction
  carrying an elevation flag. Per Principle VII this check is defence in depth and is never the thing
  relied upon.

Scripts run strictly as the signed-in user, never elevated, never under a service account.

When elevation is eventually introduced, it carries `STAFF_APPROVAL` **unconditionally** — regardless
of what the control gate would otherwise assign — and requires a separate decision before it ships.

Honouring the §35.4 gate, Alpha additionally ships **no destructive catalogue entries**: entries are
limited to risk tiers that are read-only or safely reversible on the endpoint. The taxonomy of what
counts as destructive is listed as unresolved below, and until it exists the conservative reading
applies — if an entry's reversibility is unclear, it does not ship.

### OQ-05 — A client result is a claim, not proof

A result posted back by the Desktop app is **a claim**. §18.6 already states that a successful exit
code alone is not proof of resolution; this makes the consequence explicit in the audit record.

The verify stage attempts server-side confirmation through a read tool, and every execution is
recorded with one of three verification outcomes:

| Outcome | Meaning | Consequence |
|---|---|---|
| `server_confirmed` | A server-side read tool confirmed the effect | Reported as resolved |
| `client_attested` | No server-side read path exists for this effect | Reported as **reported complete, not independently verified**. MUST NOT be presented to the user or to ServiceNow as confirmed resolution |
| `contradicted` | A server-side read disagreed with the claim | Treated as a failure. Stops the run, records on the case, escalates |

Catalogue entries SHOULD declare the read tool that verifies them. An entry with no verification path
can only ever produce `client_attested`, and that is a reason to scrutinise it in review rather than a
property to accept quietly.

## Consequences

**Positive.** The approved command set and the executed command set are cryptographically bound. The
cache-drift and stale-script classes are eliminated rather than mitigated. Alpha's endpoint blast
radius is bounded to non-elevated, non-destructive operations running as the user. Audit records state
what the platform actually knows rather than what the endpoint reported.

**Negative / accepted.**

- **Offline execution is impossible.** No cache means no connectivity, no execution. Acceptable because
  desktop execution already requires the user present within the fifteen-minute window.
- A per-execution fetch adds a round trip to a latency-sensitive path.
- `client_attested` outcomes will be common early, because verification read tools arrive with the use
  cases. This is visible weakness rather than hidden weakness, which is the intent.
- Integrity rests on the platform API's own trustworthiness until signing lands.

## Unresolved

- **Script signing for GA.** A detached signature from a Key Vault key, verified against a public key
  pinned in the Electron main process. This is the residual gap in OQ-03 above and should be decided
  before endpoint execution expands beyond Alpha's non-destructive entries.
- **The "destructive" taxonomy.** What makes a catalogue entry destructive or irreversible on an
  endpoint, and how that maps to risk tiers. Needed before the §35.4 gate can be lifted.
- **Per-entry verification tools.** Which read tool confirms which catalogue entry. This arrives with
  UC-01 through UC-12 and cannot be specified ahead of them (constitution Principle IX).
- Whether a `client_attested` outcome should itself require staff review before the case is closed.

## More Information

- `Synthia-Platform-Specification.md` §18.6, §31.6, §35.4, and §40 OQ-03 / OQ-04 / OQ-05.
- Constitution Principles III, VII, VIII and IX; Section 2 Electron standards.
