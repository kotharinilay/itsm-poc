# RagCore LangGraph Visual Flow

This diagram is derived from `ragcore/src/ragcore/graph/builder.py` and the node modules under
`ragcore/src/ragcore/graph/nodes`. It shows the compiled control shape, not a speculative product
workflow.

## Control Graph

```mermaid
flowchart TD
    start([START]) --> intake[intake]
    intake --> converse[converse]
    converse --> retrieve[retrieve]

    clarify[[clarify<br/>interrupt: clarification]]
    clarify --> retrieve

    retrieve --> ground[ground]
    ground --> guardrail{guardrail}
    guardrail -- continue --> propose[propose]
    guardrail -- closed_declined or escalated --> close[close]

    propose --> classify[classify]
    classify -- proposal exists --> govern{govern}
    classify -- no proposal --> end_noop([END])

    govern -- proceed --> execute[execute]
    govern -- suspend_for_consent --> await_consent[[await_consent<br/>interrupt: consent]]
    govern -- suspend_for_approval --> await_approval[[await_approval<br/>interrupt: approval]]
    govern -- refuse --> close

    await_consent -- resume, read durable consent --> govern
    await_approval -- resume, read durable approval --> govern

    execute --> verify[verify]
    verify --> end_exec([END])
    close --> end_close([END])

    classDef interrupt fill:#fff1d6,stroke:#b7791f,color:#2d1b00,stroke-width:2px;
    classDef gate fill:#e8f3ff,stroke:#2b6cb0,color:#102a43,stroke-width:2px;
    classDef terminal fill:#eef2f7,stroke:#64748b,color:#0f172a;
    class clarify,await_consent,await_approval interrupt;
    class guardrail,govern gate;
    class start,end_noop,end_exec,end_close terminal;
```

Note: `builder.py` registers `clarify` and defines `clarify -> retrieve`, but the current builder
does not define an incoming edge from `converse` or any router into `clarify`. In the current graph
shape, the clarification interrupt node is present but unreachable.

## Runtime Flow

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant Host as RunHost
    participant Graph as LangGraph
    participant Retrieval
    participant Catalogue
    participant Gate as Governance Gate
    participant Decisions as Consent/Approval Stores
    participant Tool as Tool Execution

    Client->>Host: stream_turn(context, turn state)
    Host->>Graph: invoke compiled graph with RunContext
    Graph->>Graph: intake, converse
    Graph->>Retrieval: retrieve tenant-scoped context
    Retrieval-->>Graph: retrieved evidence
    Graph->>Graph: ground, guardrail

    alt guardrail declines or escalates
        Graph->>Graph: close
        Graph-->>Host: done
    else request continues
        Graph->>Graph: propose, classify
        Graph->>Catalogue: lookup operation and entitlement
        Catalogue-->>Graph: catalogue entry and entitlement
        Graph->>Decisions: read standing durable decision, if any
        Decisions-->>Graph: consent, approval, or none
        Graph->>Gate: evaluate proposal deterministically

        alt gate proceeds
            Graph->>Tool: execute governed capability
            Tool-->>Graph: execution result and verification claim
            Graph->>Graph: verify node currently performs no extra work
            Graph-->>Host: done
        else gate requires end-user consent
            Graph-->>Host: interrupt consent
            Host-->>Client: SSE interrupt
            Client->>Host: resume trigger after consent API writes row
            Host->>Graph: resume
            Graph->>Decisions: read durable consent
            Graph->>Gate: re-evaluate current authority
        else gate requires staff approval
            Graph-->>Host: interrupt approval
            Host-->>Client: SSE interrupt
            Client->>Host: resume trigger after staff API writes row
            Host->>Graph: resume
            Graph->>Decisions: read durable approval
            Graph->>Gate: re-evaluate current authority
        else gate refuses
            Graph->>Graph: close
            Graph-->>Host: done
        end
    end
```

## Node Responsibilities

| Node | Writes or changes | External reads/calls | Routes to |
|---|---|---|---|
| `intake` | Triage-derived `session_state`, `work_item_id` mirror | Deterministic triage over conversation; `RunContext.work_item_id` | `converse` |
| `converse` | `session_state = resolving` | None in current scaffold | `retrieve` |
| `clarify` | Appends end-user answer, clears interrupt | Suspends via LangGraph interrupt | `retrieve` |
| `retrieve` | Appends `retrieved` evidence | Tenant-scoped retrieval port | `ground` |
| `ground` | `grounding` assessment | Confidence logic over retrieved evidence | `guardrail` |
| `guardrail` | May set `closed_declined` or `escalated` | Deterministic scope classifier | `propose` or `close` |
| `propose` | No write in current scaffold; later model output lands in `proposal` | None in current scaffold | `classify` |
| `classify` | `classification` | Operation catalogue and entitlement | `govern` or `END` |
| `govern` | `governance`, `pending_interrupt` | Catalogue, entitlement, durable consent/approval | `execute`, `await_consent`, `await_approval`, or `close` |
| `await_consent` | Mirrors durable consent decision, clears interrupt | Suspends, then reads consent repository | `govern` |
| `await_approval` | Mirrors durable staff verdict, clears interrupt | Suspends, then reads approval repository | `govern` |
| `execute` | Sealed `execution` and `verification` records | Tool execution port | `verify` |
| `verify` | No write in current scaffold | None in current scaffold | `END` |
| `close` | Clears pending interrupt and closes session path | None | `END` |

## Authority Flow

```mermaid
flowchart LR
    subgraph RunContext["RunContext: trusted per invocation, not checkpointed"]
        tenant[tenant]
        requester[requester]
        session_id[session_id]
        work_item_id[work_item_id]
        correlation_id[correlation_id]
    end

    subgraph State["AgentState: durable working checkpoint"]
        conversation[conversation]
        retrieved[retrieved]
        grounding[grounding]
        proposal[proposal]
        classification[classification]
        governance[governance<br/>treatment cannot widen]
        decision[decision<br/>first valid mirror wins]
        execution[execution<br/>write once]
        verification[verification<br/>write once]
    end

    subgraph DurableAuthority["Durable authority records"]
        work[work item]
        consent[consent row]
        approval[approval row]
        catalogue[catalogue and entitlement]
    end

    tenant --> retrieve_dep[retrieval]
    requester --> Gate
    work_item_id --> work

    conversation --> proposal
    retrieved --> grounding
    proposal --> Gate
    catalogue --> Gate
    consent --> Gate
    approval --> Gate
    Gate --> governance

    governance -- only proceed path --> execution
    execution --> verification
    consent -. mirrored for rendering .-> decision
    approval -. mirrored for rendering .-> decision
```

The important security property is structural: `execute` has exactly one incoming control edge,
from `govern` through `route_after_govern`. Retrieval, proposal, classification, and human resume
payloads cannot route directly to execution.

## Branch Summary

| Branch point | Condition source | Possible outcomes |
|---|---|---|
| `_route_after_guardrail` | `session_state` written by `guardrail` | `propose` unless session is `closed_declined` or `escalated`; otherwise `close` |
| `_route_after_propose` | Presence of `proposal` | `govern` when a proposal exists; `END` for conversational/no-op turns |
| `route_after_govern` | `governance.disposition` from deterministic gate | `execute`, `await_consent`, `await_approval`, or `close` |

## Flow Invariants

- Guardrail withholds or passes through; it does not authorize.
- Classification is a catalogue reading; governance re-reads catalogue data before deciding.
- Consent and approval interrupt nodes ignore resume payload authority and re-read durable rows.
- Consent and approval route back to `govern`, never forward to `execute`.
- `execution` and `verification` state channels are write-once.
- Governance treatment may become stricter on re-evaluation, but not more permissive.
