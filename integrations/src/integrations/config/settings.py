"""Typed configuration, validated at startup. **A name is not a value.**

Every field that could carry secret material is a `*_secret_name` holding a **Key Vault secret
name**, never the secret itself (constitution §Secrets, plan §Authentication rule 5). A settings
type that *could* hold a credential is itself the defect: the shape is what makes the rule
enforceable, because `build/policy/azure-identity.json` scans for the value-shaped variants and
finds nothing to flag.

**Validation happens at startup and fails the process.** An unconfigured vault fails loudly; an
unconfigured allow-list fails *silently by accepting forged identity*, which is why
:class:`EdgeTrustSettings` refuses an empty allow-list rather than defaulting to permissive. The
asymmetry is the whole point — a service that starts in a state it cannot be secure in has already
lost, and it has lost invisibly.

**No environment read happens outside this module.** Business code consumes a settings object; it
never reaches for `os.environ`.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = [
    "EdgeTrustSettings",
    "IntegrationsSettings",
    "ObservabilitySettings",
    "PersistenceSettings",
    "SecretsSettings",
    "ServiceBusSettings",
    "settings",
]

_ENV_PREFIX = "SYNTHIA_INTEGRATIONS_"


class _Base(BaseSettings):
    """Shared settings behaviour: one prefix, no extras, no silent coercion."""

    model_config = SettingsConfigDict(
        env_prefix=_ENV_PREFIX,
        env_nested_delimiter="__",
        extra="forbid",
        frozen=True,
    )


class EdgeTrustSettings(_Base):
    """Gateway provenance. **The allow-list is required and MUST NOT be empty.**

    Attributes:
        gateway_certificate_thumbprints: SHA-256 hashes of the client certificates APIM may
            present. A request whose ingress-forwarded certificate hash is absent from this set
            is **refused** (:mod:`integrations.api.middleware.provenance`).
    """

    gateway_certificate_thumbprints: Annotated[
        frozenset[str],
        Field(
            default=frozenset(),
            description="SHA-256 hashes of accepted APIM client certificates.",
        ),
    ]

    @field_validator("gateway_certificate_thumbprints")
    @classmethod
    def _must_not_be_empty(cls, value: frozenset[str]) -> frozenset[str]:
        """Refuse to start with no accepted certificate.

        Raises:
            ValueError: When the allow-list is empty. **This is deliberate and is not a
                convenience check.** An empty allow-list cannot be distinguished at request time
                from "every certificate is acceptable", so a service that started with one would
                accept a forged identity contract from anywhere and report itself healthy while
                doing it. Failing at startup converts a silent security hole into a loud
                deployment error.
        """
        if not value:
            raise ValueError(
                "at least one gateway certificate thumbprint is required. An empty allow-list "
                "fails open — it accepts any caller's identity contract — so the process refuses "
                "to start rather than serve in a state it cannot be secure in."
            )
        return value


class PersistenceSettings(_Base):
    """PostgreSQL. **Managed identity, never an embedded password.**

    Attributes:
        dsn: The connection string. It MUST NOT carry a password — the constitution's
            no-credential-bearing-connection-string rule, which is the form the violation usually
            takes.
        schema_name: The schema this service owns and writes. It holds **no** write grant on
            `platform` and may update only the result columns of an integration job.
    """

    dsn: Annotated[str, Field(default="", description="PostgreSQL DSN, no embedded credential.")]
    schema_name: Annotated[str, Field(default="integration")] = "integration"

    @field_validator("dsn")
    @classmethod
    def _no_embedded_credential(cls, value: str) -> str:
        """Reject a DSN carrying a password.

        Raises:
            ValueError: When the DSN appears to embed a credential. Managed identity is the
                platform default for PostgreSQL, and a password in the DSN defeats every secret
                rule at once while looking like ordinary configuration.
        """
        if value and "password=" in value.lower():
            raise ValueError(
                "the PostgreSQL DSN MUST NOT embed a password. PostgreSQL is reached by managed "
                "identity; a credential-bearing connection string is the shape this rule exists "
                "to catch."
            )
        return value


class ServiceBusSettings(_Base):
    """The asynchronous seam. **Entra authentication only — no connection string.**

    Attributes:
        namespace: The fully qualified Service Bus namespace.
        command_queue: Where `integration.execute` arrives.
        result_queue: Where `integration.completed` / `integration.failed` are published.
    """

    namespace: Annotated[str, Field(default="")]
    command_queue: Annotated[str, Field(default="synthia-integration-commands")] = (
        "synthia-integration-commands"
    )
    result_queue: Annotated[str, Field(default="synthia-integration-results")] = (
        "synthia-integration-results"
    )


class SecretsSettings(_Base):
    """Key Vault. **The sole source of secret material, reached by managed identity.**

    This service holds the Key Vault role for **connector** credentials; RagCore's identity does
    not, and that role was withdrawn rather than duplicated (plan §Authentication rule 3a).

    Attributes:
        vault_url: The vault this service resolves references against.
    """

    vault_url: Annotated[str, Field(default="")]


class ObservabilitySettings(_Base):
    """Telemetry. **PII-scrubbed, secret-free, and never an answer to an audit question.**

    Attributes:
        service_name: The resource name this service reports under. Distinct from RagCore's, so the
            two are separable in a trace — `FR-DEMO-028` requires it.
        connection_string_secret_name: A Key Vault secret **name**, never a value.
        sample_ratio: Trace sampling, decided per correlated journey rather than per request.
    """

    service_name: Annotated[str, Field(default="synthia-integrations")] = "synthia-integrations"
    connection_string_secret_name: Annotated[str, Field(default="")] = ""
    sample_ratio: Annotated[float, Field(default=1.0, ge=0.0, le=1.0)] = 1.0


class IntegrationsSettings(_Base):
    """The composed configuration surface, bound and validated once at startup."""

    environment: Annotated[str, Field(default="development")] = "development"
    edge_trust: EdgeTrustSettings = Field(default_factory=EdgeTrustSettings)
    persistence: PersistenceSettings = Field(default_factory=PersistenceSettings)
    service_bus: ServiceBusSettings = Field(default_factory=ServiceBusSettings)
    secrets: SecretsSettings = Field(default_factory=SecretsSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)


@lru_cache(maxsize=1)
def settings() -> IntegrationsSettings:
    """Bind and validate configuration exactly once.

    Cached because configuration is immutable for the process lifetime and because binding twice
    would let two halves of the application disagree about what is configured.

    Returns:
        The validated settings.

    Raises:
        pydantic.ValidationError: When configuration is invalid. **Uncaught on purpose** — it
            propagates out of application startup and stops the process, which is what
            "fail fast at start" means (constitution §Configuration validation).
    """
    return IntegrationsSettings()
