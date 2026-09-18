"""Configuration. Pydantic Settings owns it; environment reads never scatter into business code.

**Validated at startup, so a missing value fails the process** (research R-019). A malformed
setting should stop a deployment, not surface as a ``None`` three hours later on a path nobody
tested. Construction happens once, in the lifespan handler, and a failure there is a container
that does not start — which is where a configuration defect is cheapest.

**No secret value is ever held here.** Every credential is a *reference* — a Key Vault secret
name — resolved through managed identity at the point of use. The constitution's rule is
absolute: no credential in source, in tests, or in committed local configuration. The types below
enforce the readable half of that: a field named ``*_secret_name`` holds a name, and a reviewer
seeing a value in one knows immediately that something is wrong.

**Nothing here decides anything.** There is no ``allow_auto_execution`` flag, no
``require_approval`` toggle and no ``environment == "dev"`` branch. Treatment comes from the
catalogue by deterministic policy; a configuration key that could relax it would be a second
source of authority, and per-environment authority is how a control that holds in production
turns out never to have been exercised.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ragcore.config.secrets import SecretRef


class DatabaseSettings(BaseSettings):
    """PostgreSQL — the single authority for platform durable state.

    One DSN. The checkpointer derives its own connection string from this one by pinning a
    ``search_path`` (:func:`~ragcore.graph.checkpointer.checkpointer_dsn`), rather than taking a
    second setting: two DSNs is how the checkpoint tables end up in a different database from the
    work items that authorize them.
    """

    model_config = SettingsConfigDict(env_prefix="SYNTHIA_DB_", extra="forbid", frozen=True)

    dsn: PostgresDsn
    """The platform database. Resolved from Key Vault in every deployed environment."""

    statement_timeout_seconds: float = Field(default=30.0, gt=0)
    """Upper bound on a single statement. No unbounded query reaches a shared database."""

    pool_min_size: int = Field(default=1, ge=0)
    pool_max_size: int = Field(default=10, ge=1)

    @field_validator("pool_max_size")
    @classmethod
    def _max_at_least_min(cls, value: int, info: ValidationInfo) -> int:
        """Reject an inverted pool range at startup rather than at first connection.

        Raises:
            ValueError: When the ceiling is below the floor — a container that would fail on its
                first connection attempt instead fails to start.
        """
        minimum = info.data.get("pool_min_size")
        if isinstance(minimum, int) and value < minimum:
            raise ValueError(f"pool_max_size ({value}) is below pool_min_size ({minimum})")
        return value


class MessagingSettings(BaseSettings):
    """Azure Service Bus — the verdict-to-execution seam.

    The queue exists so the approving request returns before execution runs, and so at-least-once
    delivery, message expiry and dead-lettering are properties of the transport rather than of a
    function call (contracts/triggers.md).
    """

    model_config = SettingsConfigDict(env_prefix="SYNTHIA_BUS_", extra="forbid", frozen=True)

    namespace: str = ""
    """Fully qualified namespace. Authenticated by managed identity — there is no key setting."""

    trigger_queue: str = "synthia-triggers"

    integration_command_queue: str = "synthia-integration-commands"
    """Where RagCore dispatches authorized work to the Integrations Service (ADR-0007).

    **A separate queue, not a separate outbox.** One dispatcher, one retry policy and one
    dead-letter story serve every message this deployable publishes; what differs is the
    destination. The queues are separate because their lifecycles are: a dead-lettered command
    means *approved work never ran*, which is a governance failure, while a dead-lettered trigger
    means a resume was lost. Mixing them makes that triage ambiguous
    (``build/infra/messaging/queues.json``).
    """

    integration_result_queue: str = "synthia-integration-results"
    """Where the Integrations Service reports outcomes back.

    **RagCore consumes this queue and never publishes to it.** It holds Receiver and not Sender
    (``build/infra/messaging/queues.json``), and the asymmetry is a control: a compromised
    orchestrator that could publish ``integration.completed`` could fabricate a successful outcome
    for work that never ran. Named here because the consumer needs it, not because anything in this
    process sends to it.
    """

    max_delivery_count: int = Field(default=10, ge=1)
    """The dispatch ceiling. A row past it is marked undispatchable and surfaced to a human."""

    message_time_to_live_seconds: int = Field(default=900, ge=1, le=900)
    """Message expiry, bounded **above** at the execution window's fifteen minutes.

    A trigger that outlives the window can no longer lead to a valid execution, so it must expire to
    the dead-letter queue rather than wake a consumer that would only refuse it. Bounded by the type
    rather than by a comment: a longer TTL would create the appearance of pending work that can
    never complete, which is the failure mode the ceiling exists to prevent
    (``contracts/triggers.md`` §Delivery semantics).
    """

    dispatch_batch_size: int = Field(default=50, ge=1, le=500)
    """How many undispatched rows one dispatcher pass claims.

    Bounded so a backlog is drained in bounded passes rather than one unbounded query that holds a
    transaction open across thousands of rows.
    """


class ModelGatewaySettings(BaseSettings):
    """The AI Gateway — the sole model egress.

    **Every model call passes through here**, reasoning and embeddings alike, and no component
    reaches a provider directly (constitution §Model access). There is deliberately no
    ``provider``, no ``api_key`` and no ``model_endpoint`` field: a service that could name a
    provider is a service that could bypass the gateway's metering, budgets and content safety.
    """

    model_config = SettingsConfigDict(env_prefix="SYNTHIA_GATEWAY_", extra="forbid", frozen=True)

    base_url: str = ""
    """The gateway. The only outbound model destination this platform knows."""

    entra_scope: str = ""
    """The Entra scope this process requests when calling the gateway.

    A scope, not a credential: it names what the caller is asking to reach and grants nothing by
    itself. The bearer is minted on demand by the shared managed identity
    (:mod:`ragcore.infrastructure.azure_credentials`), so there is no standing secret here either.

    Named ``entra_scope`` rather than anything containing "token": ``tests/security/
    test_secret_binding.py`` treats such a name as a field that holds secret material, and it is
    right to — the convention is what lets a reviewer tell a name from a value at a glance, and an
    exception granted for one harmless field is the exception the next one inherits.

    Empty means the gateway is reached unauthenticated, which is legitimate only on a developer
    machine — and on a developer machine the gateway is usually absent altogether and the local
    development seam serves the call instead.
    """

    request_timeout_seconds: float = Field(default=60.0, gt=0)
    """**Every outbound call carries an explicit timeout** (research R-020).

    Specific to this platform rather than general hygiene: one call without a timeout can hold
    work past its fifteen-minute expiry, turning a slow dependency into an expired approval.
    """

    @field_validator("base_url")
    @classmethod
    def _must_be_https(cls, value: str) -> str:
        """Refuse a plaintext gateway at startup.

        Raises:
            ValueError: When set and not ``https``. The request carries an Entra token and an
                organisation's prompt content; sending either over plaintext hands both to anyone
                watching.
        """
        if value and not value.startswith("https://"):
            raise ValueError(
                f"the AI Gateway base URL must be https, got {value!r}. Model requests carry a "
                "bearer token and organisation content."
            )
        return value

    @property
    def is_configured(self) -> bool:
        """Whether a gateway is configured for this process.

        When it is not, the composition root selects the local development seam — which calls no
        model — rather than any provider. **There is no third option**, which is the single-egress
        rule holding at the point where it is most tempting to add one.
        """
        return bool(self.base_url)


class RetrievalSettings(BaseSettings):
    """Azure AI Search — the **derived** grounding index.

    Derived, not authoritative (constitution Principle IV): a lost index is rebuilt by re-running
    ingestion, never restored from a backup. Nothing here is a source of truth, and nothing
    retrieved through it confers authority.

    **No key field, and there will not be one.** Both the admin and the query key are
    application-owned credentials; ``build/policy/azure-identity.json`` names
    ``AzureKeyCredential``,
    ``admin key``, ``query key`` and ``api-key`` as forbidden configuration for this resource. The
    service is reached with an Entra token through managed identity, and the role granted is
    ``Search Index Data Reader`` — index authoring belongs to ingestion and is not granted to the
    retrieval path.
    """

    model_config = SettingsConfigDict(env_prefix="SYNTHIA_SEARCH_", extra="forbid", frozen=True)

    endpoint: str = ""
    """The search service endpoint, for example ``https://synthia.search.windows.net``.

    Empty disables retrieval rather than failing at startup: a scaffold with no index still reaches
    every outcome, and the grounding node reports an absence of evidence rather than inventing it.
    """

    index_name: str = "synthia-knowledge"

    request_timeout_seconds: float = Field(default=15.0, gt=0)
    """Shorter than the model timeout on purpose: retrieval runs before reasoning, inside the same
    window, and a slow index should surface as thin grounding rather than as expired work."""

    @field_validator("endpoint")
    @classmethod
    def _must_be_https(cls, value: str) -> str:
        """Refuse a plaintext endpoint at startup.

        Raises:
            ValueError: When set and not ``https``.
        """
        if value and not value.startswith("https://"):
            raise ValueError(
                f"the AI Search endpoint must be https, got {value!r}. The query carries a bearer "
                "token and an organisation filter."
            )
        return value

    @property
    def is_configured(self) -> bool:
        """Whether an index is configured for this process."""
        return bool(self.endpoint)


class IntegrationsServiceSettings(BaseSettings):
    """Where the **Integrations Service** is reached. The one outbound address left in this class.

    **This replaced `IntegrationSettings`, and the replacement is the boundary** (T296, ADR-0007).
    That class held third-party addresses — a ServiceNow instance, a Graph base URL, a list of MCP
    servers — and RagCore no longer has any business knowing where those systems are. Knowing an
    address is not itself an authorization, but it is the first thing a direct call needs, and code
    that can name a destination is code someone can later point at it.

    What is left is a **sibling platform service**, reached exactly like any other application call:
    through Front Door, the WAF and APIM (spec §13.4). There is no internal address here and no
    credential — the hop authenticates with managed identity on the workload audience, and APIM
    re-derives identity on it.

    **There is no per-organisation secret in this class and there is no longer one anywhere in
    RagCore.** Connector credentials are resolved by the Integrations Service alone, against a vault
    role RagCore's identity no longer holds (spec `FR-INTEG-017`, `SC-DEMO-020`).
    """

    model_config = SettingsConfigDict(
        env_prefix="SYNTHIA_INTEGRATIONS_", extra="forbid", frozen=True
    )

    gateway_base_url: str = ""
    """The **public edge** address of the gateway fronting the Integrations Service.

    Empty means this process performs no synchronous integration call. Honest rather than
    convenient: a default pointing somewhere would be a default that either fails confusingly or,
    worse, succeeds against the wrong environment.
    """

    request_timeout_seconds: float = Field(default=15.0, gt=0)
    """The bound on one synchronous hop.

    Sized for a call that now traverses two services rather than one, and still well inside the
    fifteen-minute execution window — a timeout longer than the window would let a call outlive the
    authority that permitted it.
    """

    @field_validator("gateway_base_url")
    @classmethod
    def _must_be_the_edge(cls, value: str) -> str:
        """Refuse an address that is not the public edge.

        Raises:
            ValueError: When set and not ``https``, or when it names an internal Container Apps
                address. Refused **at startup** rather than at first call, so the failure names the
                configuration instead of surfacing later as a puzzling 403 from a service that was
                never actually reached.
        """
        if value and not value.startswith("https://"):
            raise ValueError(f"the Integrations Service address must be https, got {value!r}.")
        if ".internal." in value:
            raise ValueError(
                "the Integrations Service address names an internal address. Every application "
                "call traverses Front Door, the WAF and APIM; there is no direct "
                "service-to-service route (spec §13.4)."
            )
        return value

    @property
    def is_configured(self) -> bool:
        """Whether a synchronous route to the Integrations Service exists for this process."""
        return bool(self.gateway_base_url)


class NotificationSettings(BaseSettings):
    """Azure SignalR — the realtime leaf.

    **There is no access-key field here, and there will not be one.** The data plane is reached with
    an Entra token for ``https://signalr.azure.com/.default``, obtained through managed identity
    (``build/policy/azure-identity.json``, resource ``signalr``, which names ``AccessKey`` as
    forbidden configuration). A key would also be a standing credential that grants the ability to
    push to every client of the service, which is a wide blast radius for a channel that is supposed
    to carry no authority at all.

    The endpoint is an address, not a credential: knowing it permits nothing without a token.
    """

    model_config = SettingsConfigDict(env_prefix="SYNTHIA_SIGNALR_", extra="forbid", frozen=True)

    endpoint: str = ""
    """The service endpoint, for example ``https://synthia.service.signalr.net``.

    Empty disables realtime delivery rather than failing: a notification is a leaf on every
    consequential path, so a scaffold without one still reaches every outcome — the client learns
    it by reading back through the API instead. That is the same property the platform promises
    users, exercised by configuration.
    """

    hub: str = "synthia"

    @field_validator("endpoint")
    @classmethod
    def _must_be_https(cls, value: str) -> str:
        """Refuse a plaintext endpoint at startup.

        Raises:
            ValueError: When set and not ``https``. The token is a bearer credential in transit;
                sending it over plaintext hands it to anyone watching.
        """
        if value and not value.startswith("https://"):
            raise ValueError(
                f"endpoint must be an absolute https URI, got {value!r}. The data-plane token is "
                "a bearer credential and is not sent over plaintext."
            )
        return value

    @property
    def is_configured(self) -> bool:
        """Whether realtime delivery is available in this process."""
        return bool(self.endpoint)


class CacheSettings(BaseSettings):
    """Redis — **transient only**, and never an authority (constitution Principle IV).

    **There is no password field here and there will not be one.**
    ``build/policy/azure-identity.json`` names ``password`` and ``access key`` as forbidden
    configuration for this resource. Entra authentication presents the token in the password
    position, minted per connection by the managed identity
    (:mod:`ragcore.infrastructure.azure_credentials`), so the value that goes there is never
    configuration.

    Empty ``host`` disables caching rather than failing. That is a supported deployed state as well
    as the developer-machine one: the platform's correctness does not depend on the cache, no sample
    flow reads it, and a process running without one takes the path every caller takes after an
    eviction.
    """

    model_config = SettingsConfigDict(env_prefix="SYNTHIA_REDIS_", extra="forbid", frozen=True)

    host: str = ""
    """The cache host name, for example ``synthia.redis.cache.windows.net``. An address, not a
    credential: knowing it permits nothing without a token."""

    port: int = Field(default=10000, ge=1, le=65535)
    """The TLS data-plane port. Azure Managed Redis uses 10000; Azure Cache for Redis uses 6380."""

    identity_object_id: str = ""
    """The managed identity's object id, sent as the Redis username.

    An identifier, not a secret. Redis Entra authentication expects the principal's object id in the
    username position and the access token in the password position; what the principal may actually
    do is decided by the access policy assigned to it on the cache.
    """

    request_timeout_seconds: float = Field(default=2.0, gt=0, le=10)
    """Deliberately short, and bounded above.

    A cache exists to be faster than the work it avoids. A lookup that can block for ten seconds has
    already cost more than recomputing, and a cache that can hold a request open is one that can
    take the platform down — which is not a property a transient store is allowed to have.
    """

    @property
    def is_configured(self) -> bool:
        """Whether a cache is available to this process."""
        return bool(self.host)


class ObservabilitySettings(BaseSettings):
    """Telemetry. Separate from audit, and never a substitute for it.

    **Telemetry MUST NOT answer a question audit is responsible for** (spec FR-OPS-004). They
    have different retention, different guarantees and different consumers, which is why audit
    has its own port and does not appear in this class.
    """

    model_config = SettingsConfigDict(env_prefix="SYNTHIA_OTEL_", extra="forbid", frozen=True)

    service_name: str = "ragcore"
    connection_string_secret_name: str = ""
    """Key Vault secret *name*, never a connection string. See the module docstring."""

    trace_sample_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
    """The proportion of **ordinary journeys** retained.

    Sampling is decided per correlated journey, not per span (spec FR-OPS-012):
    :mod:`ragcore.observability.sampling` derives the decision from the correlation identifier, so a
    journey that suspends and resumes hours later in another process reaches the same answer without
    the two halves sharing anything. **Head sampling is prohibited** — it decides at the first span,
    before the journey is known to be interesting, and routinely keeps the request half of an
    approval and discards the resume half.

    This ratio never applies to a trace carrying an error, a governance denial or an approval. Those
    are retained regardless (plan §Telemetry retention and sampling), which is why a low value here
    is safe: what it discards is the ordinary.
    """

    retention_days: int = Field(default=30, ge=1, le=90)
    """Telemetry retention, **bounded above at 90 days** (spec FR-OPS-011).

    Bounded by the type rather than by a comment, because the ceiling is what makes FR-OPS-004
    enforceable in practice. Audit keeps seven years; telemetry keeping months would make it
    plausible to answer an audit question from a dashboard, and the answer would be wrong in a way
    nobody could see — sampled, unretained after the window, and never intended to be authoritative.

    The value here is what the process reports and what the workspace is configured with
    (``build/infra/monitoring/telemetry.json``). The two are asserted to agree, because a workspace
    silently keeping more than this would defeat the rule from outside the application.
    """


class EdgeTrustSettings(BaseSettings):
    """How this process proves a request arrived through APIM.

    **APIM is the identity/trust boundary.** This service consumes the closed ``X-Idp-*`` contract
    and never parses a token, which is only safe while it can tell an APIM-stamped header from one
    a caller typed. The certificate hash below is what tells it apart
    (:mod:`ragcore.api.middleware.provenance`, ``build/policy/edge-trust.json``).

    **Required, with no default and no environment branch.** Every other setting in this module has
    a defensible empty state; this one does not. An unconfigured vault fails loudly on the first
    secret it needs, whereas an unconfigured allow-list fails *silently*, by accepting forged
    identity, and produces a service that looks perfectly healthy. There is therefore no local
    bypass — which matches how identity is already treated here, since a developer running this
    process directly must already supply the five ``X-Idp-*`` headers by hand.

    **Not secret material.** A thumbprint is the hash of a public certificate, so it is ordinary
    configuration rather than a Key Vault reference. Naming it ``*_secret_name`` would wrongly
    suggest that keeping it quiet was load-bearing.
    """

    model_config = SettingsConfigDict(env_prefix="SYNTHIA_EDGE_", extra="forbid", frozen=True)

    gateway_certificate_thumbprints: str = ""
    """SHA-256 hashes of the accepted gateway client certificates, comma-separated.

    Comma-separated because rotation is an overlap: both the outgoing and the incoming hash sit here
    while APIM is cut over, so there is no instant at which neither is accepted.
    """

    @field_validator("gateway_certificate_thumbprints")
    @classmethod
    def _must_be_hex_digests(cls, value: str) -> str:
        """Refuse a malformed allow-list at startup rather than at first request.

        Raises:
            ValueError: When an entry is not a 64-character hex SHA-256 digest. A truncated or
                colon-formatted thumbprint pasted from a certificate viewer would otherwise match
                nothing, and a control that matches nothing rejects every request — an outage
                whose cause is a formatting difference nobody can see.
        """
        for entry in value.split(","):
            candidate = entry.strip().strip('"').replace(":", "").lower()
            if not candidate:
                continue
            if len(candidate) != 64 or any(
                character not in "0123456789abcdef" for character in candidate
            ):
                raise ValueError(
                    "each gateway certificate thumbprint must be a 64-character hex SHA-256 "
                    f"digest, got one of length {len(candidate)}"
                )
        return value


class KeyVaultSettings(BaseSettings):
    """Where secret material comes from. **The only source there is.**

    There is deliberately no client-secret and no certificate-path setting here: a credential
    configured to *read* the vault would be a standing secret living outside the vault, which is
    precisely the problem the vault exists to remove. The vault is reached through managed identity
    (:mod:`ragcore.infrastructure.azure_credentials`) and through nothing else.
    """

    model_config = SettingsConfigDict(env_prefix="SYNTHIA_KEYVAULT_", extra="forbid", frozen=True)

    vault_uri: str = ""
    """The vault URI, or empty to resolve no secrets from a vault.

    Empty is legitimate on a developer machine, where settings come from the environment. It is not
    a supported deployed configuration, and the deployment pipeline is what enforces that — a
    running process cannot tell which environment it wishes it were in.
    """

    @field_validator("vault_uri")
    @classmethod
    def _must_be_https(cls, value: str) -> str:
        """Refuse a plaintext vault URI at startup.

        Raises:
            ValueError: When the URI is set and is not ``https``. A secret fetched over plaintext is
                a secret in transit to anybody watching, and the SDK's own failure for this names
                neither the setting nor the file it came from.
        """
        if value and not value.startswith("https://"):
            raise ValueError(
                f"vault_uri must be an absolute https URI, got {value!r}. "
                "Secret material is not fetched over plaintext."
            )
        return value

    @property
    def is_configured(self) -> bool:
        """Whether a vault is configured for this process."""
        return bool(self.vault_uri)


class Settings(BaseSettings):
    """Application settings, validated at startup so a missing value fails the process."""

    model_config = SettingsConfigDict(
        env_prefix="SYNTHIA_",
        env_nested_delimiter="__",
        env_file=None,
        extra="forbid",
        frozen=True,
    )

    environment: Literal["local", "development", "staging", "production"] = "local"
    """Deployment environment name.

    **Never used to make an authorization decision.** It names where the process is running, for
    telemetry and for operators. A treatment, a role or an entitlement that varied by environment
    would mean the control exercised in testing is not the control running in production.
    """

    database: DatabaseSettings
    edge_trust: EdgeTrustSettings = EdgeTrustSettings()
    key_vault: KeyVaultSettings = KeyVaultSettings()
    messaging: MessagingSettings = MessagingSettings()
    notifications: NotificationSettings = NotificationSettings()
    gateway: ModelGatewaySettings = ModelGatewaySettings()
    retrieval: RetrievalSettings = RetrievalSettings()
    integrations: IntegrationsServiceSettings = IntegrationsServiceSettings()
    cache: CacheSettings = CacheSettings()
    observability: ObservabilitySettings = ObservabilitySettings()

    execution_window_minutes: int = Field(default=15, ge=1, le=15)
    """The execution validity window (constitution Principle III).

    Bounded **above** as well as below. It is configurable so a deployment can be stricter and
    for no other reason; raising it past fifteen minutes would weaken a control the specification
    fixes, so the type does not allow it.
    """

    def required_secret_references(self) -> tuple[SecretRef, ...]:
        """Every secret this process cannot start without.

        **Declared here rather than discovered at the point of use.** A secret resolved lazily fails
        on whichever request first needed it, in whichever replica happened to serve it — a
        configuration defect wearing the costume of an intermittent outage. Resolving the whole set
        at startup turns that into a deployment that does not start.

        A setting holding an empty secret *name* contributes nothing here: the name being absent is
        an ordinary "this process does not use that" and is caught, where it matters, by the
        component that needs it. What this list exists to catch is a name that is present and does
        not resolve.

        Returns:
            The references, in declaration order. Empty when no vault is configured, which is the
            developer-machine case.
        """
        if not self.key_vault.is_configured:
            return ()

        names = (self.observability.connection_string_secret_name,)
        return tuple(SecretRef(name) for name in names if name)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the validated settings singleton.

    Cached because settings are immutable for the life of the process and constructing them twice
    would mean two objects that could, after an environment change, disagree.

    Returns:
        The settings instance, constructed and validated on first call.
    """
    # `Settings()` reads every field from the environment; mypy sees the required `database`
    # field and no argument for it. The suppression is narrow and is the documented
    # pydantic-settings pattern — widening it would hide a genuinely missing field.
    return Settings()  # type: ignore[call-arg]
