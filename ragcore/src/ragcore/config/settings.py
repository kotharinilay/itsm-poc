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

    max_delivery_count: int = Field(default=10, ge=1)
    """The dispatch ceiling. A row past it is marked undispatchable and surfaced to a human."""


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

    request_timeout_seconds: float = Field(default=60.0, gt=0)
    """**Every outbound call carries an explicit timeout** (research R-020).

    Specific to this platform rather than general hygiene: one call without a timeout can hold
    work past its fifteen-minute expiry, turning a slow dependency into an expired approval.
    """


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
    """Sampling is decided per correlated journey, not per span (spec FR-OPS-012)."""


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
    messaging: MessagingSettings = MessagingSettings()
    gateway: ModelGatewaySettings = ModelGatewaySettings()
    observability: ObservabilitySettings = ObservabilitySettings()

    execution_window_minutes: int = Field(default=15, ge=1, le=15)
    """The execution validity window (constitution Principle III).

    Bounded **above** as well as below. It is configurable so a deployment can be stricter and
    for no other reason; raising it past fifteen minutes would weaken a control the specification
    fixes, so the type does not allow it.
    """


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
