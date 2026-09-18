# AI Gateway — the single model egress

```text
RagCore → AI Gateway → model provider
```

There is no other path, and `RagCore → Azure OpenAI` / `RagCore → Foundry` does not exist. That is
not a convention with a test attached; it is four independent facts, and removing any one of them
still leaves a direct provider call impossible.

| # | Where | What it establishes |
|---|---|---|
| 1 | `build/infra/identity/managed-identities.json` | `id-synthia-ragcore` holds **no Foundry role**. A direct call fails to authenticate even if the code existed. |
| 2 | `ragcore/src/ragcore/model/egress.py` | `ModelEgressPort` is the only shape a model call takes. Its implementations are the gateway client and the local seam. |
| 3 | `ragcore/tests/architecture/test_no_direct_model_call.py` | No provider SDK, endpoint or deployment name appears outside `model/`. |
| 4 | `ragcore/src/ragcore/config/settings.py` | `ModelGatewaySettings` has no `provider`, no `api_key` and no `model_endpoint` field. |

## What lives here and why it is not in the application

| Capability | Requirement | Why the gateway and not RagCore |
|---|---|---|
| Provider routing | §13.5, `FR-OPS-009` | A caller that could name a provider would make changing one a change to every call site. |
| Token metering, provider-neutral | `FR-OPS-008` | Usage must stay comparable across a provider change, so it is counted where the provider is known. |
| Per-organisation budgets and throttles | `FR-OPS-005` | A budget enforced by the caller is a budget the caller can decline to enforce. |
| Semantic cache | `FR-OPS-010` | A cache the application owned would be a second place a response could come from, unattributably. |
| Bidirectional content safety | `FR-EXT-021` | A check in the agent loop is one a new call site forgets. |

The application supplies exactly two things (`model/gateway.py`):
`X-Synthia-Organisation`, which every policy counts against, and `X-Correlation-Id`, which joins a
metered token to a user-visible outcome. It supplies **no model name, no deployment and no
provider**.

## Files

| File | What it is |
|---|---|
| `policy.xml` | The APIM policy, in the order it must run. Each step says why it sits where it does. |
| `providers.json` | The backend pool, the named values, and the cache's transient-only position. The only place a provider is named. |

## Authentication, in both directions

- **RagCore → gateway.** An Entra token minted by `id-synthia-ragcore`, audience
  `{{ai-gateway-audience}}`, validated by `validate-azure-ad-token` against that identity's object
  id. No subscription key and no API key: a key is not tied to a caller, so metering would be
  unattributable and a leak would be a model budget anybody could spend.
- **Gateway → Foundry.** APIM's own managed identity, with the backend credential type set to
  managed identity. `build/policy/azure-identity.json` names `AzureKeyCredential`, `api_key` and
  `OPENAI_API_KEY` as forbidden configuration for the `foundry` resource, and the security tests on
  both stacks scan committed configuration for exactly those shapes.

**No model provider credential exists anywhere in this repository**, in either direction.

## Local development

A developer without a gateway does **not** get a provider client behind an environment branch. They
get `ragcore/src/ragcore/model/local.py` — `LocalDevelopmentEgress`, which implements
the same seam and **calls no model at all**.

```text
SYNTHIA_GATEWAY_BASE_URL set    → AiGatewayEgress        (the gateway)
SYNTHIA_GATEWAY_BASE_URL unset  → LocalDevelopmentEgress (no model, local environment only)
```

The choice is made in one function, `_model_egress` in `ragcore/config/composition.py`, and there is
no third branch. The seam refuses construction outside `environment == "local"`, so a deployment
that lost its gateway setting fails to start rather than quietly answering with placeholder text and
metering nothing.

What it returns is honest: the completion says in plain words that no model was called, and the
embedding is a sixteen-dimension hash — deterministic, so retrieval tests repeat, and obviously not
a real embedding to anyone who looks at it.

## Ordering

Two orderings in `policy.xml` are load-bearing and are the ones most likely to be "tidied":

1. **Inbound content safety runs before the semantic cache lookup.** `FR-OPS-010` requires that a
   cached response not bypass the checks a fresh response passes. Reversing these would let a prompt
   that should have been blocked be answered from cache.
2. **The budget check runs before the backend call, with `estimate-prompt-tokens="true"`.** Checking
   after the call would have already spent the tokens it was refusing to spend.

## Throttles are not failures

`llm-token-limit` answers `429` for a rate limit and `403` for an exhausted quota. The application
maps both to `ModelBudgetExceededError`, and the user is told the request was **limited** — never
that it failed (`FR-OPS-006`). This is why that error is its own type rather than a status code the
caller inspects.

## Redis

The semantic cache's store, and **transient only** (constitution Principle IV). It is never an
authority and never a durable record: every entry carries a TTL, no sample flow reads it, and a lost
cache costs model calls and nothing else. It is partitioned by organisation through the policy's
`vary-by` — without that, a completion produced for one organisation could be served to another,
which is a cross-tenant leak no database-level isolation would catch.
