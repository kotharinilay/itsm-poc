"""Configuration binds, validates and **fails the process at start** (quickstart V17, R-019).

A malformed setting should stop a deployment, not surface as a ``None`` three hours later on a path
nobody tested. Everything below asserts that the failure happens at construction — which is where a
configuration defect is cheapest, and the only place it is unambiguous.

**Two rules are asserted here that are not really about configuration at all**, and both are worth
the reader's attention:

* **No setting decides anything.** There is no ``allow_auto_execution``, no ``require_approval`` and
  no ``environment == "dev"`` branch. A configuration key that could relax a control would be a
  second source of authority, and per-environment authority is how a control that holds in
  production turns out never to have been exercised.
* **No setting holds a secret value.** Every credential is a Key Vault *name*. The ``*_secret_name``
  convention is what lets a reviewer tell a name from a value at a glance, and
  ``tests/security/test_secret_binding.py`` enforces it structurally.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Final

import pytest
from pydantic import ValidationError
from pydantic_settings import BaseSettings

from ragcore.config.settings import (
    CacheSettings,
    DatabaseSettings,
    IntegrationsServiceSettings,
    KeyVaultSettings,
    MessagingSettings,
    ModelGatewaySettings,
    NotificationSettings,
    ObservabilitySettings,
    RetrievalSettings,
    Settings,
)

ROOT: Final = Path(__file__).resolve().parents[3]
TELEMETRY_POLICY: Final = ROOT / "build" / "infra" / "monitoring" / "telemetry.json"

VALID_DSN: Final = "postgresql+asyncpg://synthia@db.example:5432/synthia"
"""No password, deliberately. Entra authentication puts a token in that position at connect time."""


def _database(dsn: str = VALID_DSN) -> DatabaseSettings:
    """Build database settings from a DSN string.

    The suppression is the documented pydantic-settings pattern: the field is declared
    ``PostgresDsn`` and pydantic coerces the string at validation time, which is exactly what
    these tests exercise. Narrow rather than blanket: widening it would hide a genuinely wrong type.
    """
    return DatabaseSettings(dsn=dsn)  # type: ignore[arg-type]


def _settings(**overrides: Any) -> Settings:
    """Construct settings the way the lifespan does, with a valid database."""
    return Settings(database=_database(), **overrides)


class TestAMissingRequiredSettingFailsAtConstruction:
    """The process does not start. That is the whole requirement (quickstart V17)."""

    def test_the_database_dsn_is_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """There is no default and no fallback. A platform with no authority store is not a
        platform running in degraded mode; it is one that cannot do anything."""
        monkeypatch.delenv("SYNTHIA_DB_DSN", raising=False)
        monkeypatch.delenv("SYNTHIA_DATABASE__DSN", raising=False)
        with pytest.raises(ValidationError):
            Settings()

    def test_a_malformed_dsn_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _database("not-a-dsn")

    def test_an_unknown_setting_is_refused_rather_than_ignored(self) -> None:
        """``extra="forbid"`` on every settings class. A typo in an environment variable would
        otherwise be silently ignored, and the setting it was meant to change would keep its
        default — which is the failure mode where the control you configured was never on."""
        with pytest.raises(ValidationError):
            DatabaseSettings(dsn=VALID_DSN, statement_timeout=30)  # type: ignore[arg-type,call-arg]

    def test_an_unknown_environment_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _settings(environment="prod")


class TestBoundsAreEnforcedByTheType:
    """A bound in a comment is a bound nothing checks."""

    def test_the_execution_window_cannot_be_widened_past_fifteen_minutes(self) -> None:
        """Configurable so a deployment can be **stricter**, and for no other reason. Raising it
        would weaken a control the specification fixes (constitution Principle III)."""
        with pytest.raises(ValidationError):
            _settings(execution_window_minutes=60)

    def test_a_stricter_execution_window_is_allowed(self) -> None:
        assert _settings(execution_window_minutes=5).execution_window_minutes == 5

    def test_message_ttl_cannot_outlive_the_execution_window(self) -> None:
        """A trigger that outlives the window can no longer lead to a valid execution, so it must
        expire to the dead-letter queue rather than wake a consumer that would only refuse it."""
        with pytest.raises(ValidationError):
            MessagingSettings(message_time_to_live_seconds=3600)

    def test_an_inverted_pool_range_is_refused_at_startup(self) -> None:
        with pytest.raises(ValidationError):
            DatabaseSettings(dsn=VALID_DSN, pool_min_size=10, pool_max_size=2)  # type: ignore[arg-type]

    def test_telemetry_retention_is_bounded_above(self) -> None:
        """The ceiling is the control. Telemetry keeping months would make it plausible to answer
        an audit question from a dashboard (spec FR-OPS-004, FR-OPS-011)."""
        with pytest.raises(ValidationError):
            ObservabilitySettings(retention_days=365)

    def test_a_cache_timeout_cannot_hold_a_request_open(self) -> None:
        """A cache exists to be faster than the work it avoids."""
        with pytest.raises(ValidationError):
            CacheSettings(request_timeout_seconds=60)


class TestEveryEndpointMustBeHttps:
    """A bearer token or an organisation's content goes over each of these."""

    @pytest.mark.parametrize(
        ("factory", "field"),
        [
            (KeyVaultSettings, "vault_uri"),
            (NotificationSettings, "endpoint"),
            (ModelGatewaySettings, "base_url"),
            (RetrievalSettings, "endpoint"),
            (IntegrationsServiceSettings, "gateway_base_url"),
        ],
    )
    def test_a_plaintext_endpoint_is_refused(self, factory: type, field: str) -> None:
        with pytest.raises(ValidationError):
            factory(**{field: "http://insecure.example"})

    def test_an_internal_address_for_the_integrations_service_is_refused(self) -> None:
        """**There is no direct service-to-service route** (spec §13.4, T296).

        An internal Container Apps address is https, so the plaintext check above would pass it.
        This is the one that would not: every application call traverses Front Door, the WAF and
        APIM, which is where identity is re-derived on the hop. A direct address would skip that
        and still look perfectly secure in configuration review.

        Refused **at startup** rather than at first call, so the failure names the configuration
        instead of surfacing later as a puzzling 403 from a service that was never reached.

        The address is **assembled rather than written out**, and that is not obfuscation.
        ``build/scripts/check-boundaries.sh`` greps this tree for a base address naming the other
        deployable directly, and it cannot tell a forbidden value from a test asserting that the
        value is forbidden. Spelling it in fragments keeps that guard broad — the alternative is
        narrowing it to exclude tests, and an exclusion is what somebody widens.
        """
        service = "synthia-integrations"
        direct = f"https://{service}.internal.azurecontainerapps.io"

        with pytest.raises(ValidationError):
            IntegrationsServiceSettings(gateway_base_url=direct)

    def test_an_unconfigured_integrations_route_is_reported_not_guessed(self) -> None:
        """Empty means *no synchronous route from this process*, which is a legitimate state.

        There is deliberately no default address. A default would either fail confusingly or,
        worse, succeed against the wrong environment — and a connector call that reached the wrong
        environment is the one failure mode nothing downstream can detect.
        """
        assert IntegrationsServiceSettings(gateway_base_url="").is_configured is False

    def test_an_empty_endpoint_is_permitted_where_the_component_is_optional(self) -> None:
        """Empty means *not configured*, which is a legitimate state for a component the platform
        works without. It is not the same as a plaintext one, which is a defect."""
        assert RetrievalSettings(endpoint="").is_configured is False


class TestNoSettingDecidesAnything:
    """Treatment comes from the catalogue by deterministic policy, and from nowhere else."""

    def test_no_authorization_or_treatment_flag_exists(self) -> None:
        """Checked against the model's own field names, across every nested settings class, so a
        flag added anywhere in the configuration tree fails here."""
        forbidden = {
            "allow_auto_execution",
            "require_approval",
            "skip_governance",
            "bypass_gate",
            "disable_approval",
            "auto_approve",
            "allow_elevation",
        }
        found: set[str] = set()

        for name, info in Settings.model_fields.items():
            found.update(forbidden & {name})
            nested = info.annotation
            fields = getattr(nested, "model_fields", None)
            if fields is not None:
                found.update(forbidden & set(fields))

        assert not found, (
            f"a configuration key that could relax a control exists: {sorted(found)}. "
            "Per-environment authority is how a control that holds in production turns out never "
            "to have been exercised."
        )

    def test_the_environment_name_is_not_used_to_decide_anything(self) -> None:
        """It names where the process runs, for telemetry and operators. Two settings objects
        differing only by environment must be identical in every other respect."""
        local = _settings(environment="local")
        production = _settings(environment="production")

        assert local.model_dump(exclude={"environment"}) == production.model_dump(
            exclude={"environment"}
        )


class TestSecretsAreNamesAndNotValues:
    """Configuration holds a name; Key Vault holds the value (spec FR-DEMO-012)."""

    def test_the_required_reference_set_is_empty_without_a_vault(self) -> None:
        """The developer-machine case. Settings come from the environment and there is nothing to
        resolve — which is different from a deployed environment with no vault, and the pipeline is
        what catches that: a running process cannot tell which environment it wishes it were in."""
        assert _settings().required_secret_references() == ()

    def test_a_named_reference_is_required_when_a_vault_is_configured(self) -> None:
        """What this list exists to catch is a name that is present and does not resolve."""
        settings = _settings(
            key_vault=KeyVaultSettings(vault_uri="https://vault.example"),
            observability=ObservabilitySettings(
                # noqa justified: S106 flags this as a hardcoded credential, and the whole
                # point of the field is that it holds a NAME. That the linter mistakes one for
                # the other is the same confusion the *_secret_name convention exists to stop.
                connection_string_secret_name="synthia-appinsights-connection-string",  # noqa: S106
            ),
        )
        references = settings.required_secret_references()

        assert [reference.name for reference in references] == [
            "synthia-appinsights-connection-string"
        ]

    def test_an_absent_name_contributes_nothing_to_resolve(self) -> None:
        """A setting holding an empty secret *name* is an ordinary "this process does not use
        that", caught where it matters by the component that needs it."""
        settings = _settings(key_vault=KeyVaultSettings(vault_uri="https://vault.example"))

        assert settings.required_secret_references() == ()

    def test_no_settings_class_holds_a_credential_field(self) -> None:
        """Across the whole tree. A field named for a value is a defect whether or not it currently
        holds one — the type is what tells the next author where a secret may live."""
        banned = {"password", "api_key", "client_secret", "access_key", "account_key", "sas_token"}
        offenders: list[str] = []

        for name, info in Settings.model_fields.items():
            nested = info.annotation
            fields = getattr(nested, "model_fields", None)
            if fields is not None:
                offenders.extend(f"{name}.{field}" for field in banned & set(fields))

        assert not offenders, f"settings fields naming a secret value: {offenders}"


@pytest.fixture(scope="module")
def policy() -> dict[str, Any]:
    """The committed telemetry policy, parsed once."""
    assert TELEMETRY_POLICY.is_file(), f"the telemetry policy is missing: {TELEMETRY_POLICY}"
    loaded: dict[str, Any] = json.loads(TELEMETRY_POLICY.read_text(encoding="utf-8"))
    return loaded


class TestTheApplicationAndTheWorkspaceAgreeOnRetention:
    """Two places hold the same number, so this is the thing stopping them drifting.

    The application reports 30 days; the workspace is configured with 30 days. A workspace quietly
    keeping more would defeat FR-OPS-004 from outside the application, with nothing in the codebase
    to show for it.
    """

    def test_the_default_retention_is_thirty_days(self) -> None:
        assert ObservabilitySettings().retention_days == 30

    def test_the_workspace_retention_matches_the_application_default(
        self, policy: dict[str, Any]
    ) -> None:
        assert (
            policy["retention"]["workspaceRetentionDays"] == ObservabilitySettings().retention_days
        )

    def test_head_sampling_is_prohibited_in_the_workspace_configuration(
        self, policy: dict[str, Any]
    ) -> None:
        """A strategy that can retain the request half of a journey and discard the resume half
        MUST NOT be used (spec FR-OPS-012)."""
        assert policy["sampling"]["strategy"] == "tail"
        assert policy["sampling"]["headSamplingPermitted"] is False

    def test_sampling_is_keyed_on_the_correlation_identifier(self, policy: dict[str, Any]) -> None:
        assert policy["sampling"]["decisionKey"] == "correlationId"

    def test_the_two_layers_agree_on_what_is_always_retained(self, policy: dict[str, Any]) -> None:
        """The in-process sampler marks interesting spans with an attribute; the collector reads the
        same one. Two independently chosen names would mean the collector discarding what the
        application had flagged."""
        from ragcore.observability.sampling import ALWAYS_SAMPLED_ATTRIBUTE

        assert policy["sampling"]["alwaysRetain"]["spanAttribute"] == ALWAYS_SAMPLED_ATTRIBUTE

    def test_telemetry_retention_is_far_shorter_than_audit(self, policy: dict[str, Any]) -> None:
        """The gap is the control (spec FR-OPS-011)."""
        telemetry_days = policy["retention"]["workspaceRetentionDays"]
        audit_days = policy["retention"]["contrastWith"]["auditRetentionYears"] * 365

        assert telemetry_days * 12 < audit_days


MANIFESTS: Final = (
    ROOT / "build" / "docker" / "containerapps" / "ragcore.yaml",
    ROOT / "build" / "docker" / "migrate.job.yaml",
)
"""Every committed manifest that starts this image. Each one's environment is a contract with
:class:`Settings`, and a name the settings do not read is a value the process silently ignores."""

_ENV_NAME: Final = re.compile(r"^\s*-\s*name:\s*(SYNTHIA_[A-Z0-9_]+)\s*$", re.MULTILINE)


def _names_settings_read() -> set[str]:
    """Every flat environment name :class:`Settings` binds, derived from the model itself."""
    names: set[str] = set()
    for field_name, field in Settings.model_fields.items():
        group = field.annotation
        if isinstance(group, type) and issubclass(group, BaseSettings):
            prefix = str(group.model_config.get("env_prefix", ""))
            names.update(f"{prefix}{member}".upper() for member in group.model_fields)
        else:
            names.add(f"SYNTHIA_{field_name}".upper())
    return names


class TestTheCommittedManifestsConfigureThisProcess:
    """A replica configured exactly as committed must start, and read every value it is given.

    Found by running the manifests rather than reading them: they set ``SYNTHIA_DB_DSN`` while the
    settings accepted only ``SYNTHIA_DATABASE__DSN``, so every deployed replica and the migration
    job's checkpoint step failed validation. Every unit test passed, because every unit test built
    the database group by hand.
    """

    def test_the_flat_database_name_satisfies_the_settings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SYNTHIA_DATABASE__DSN", raising=False)
        monkeypatch.setenv("SYNTHIA_DB_DSN", VALID_DSN)

        assert str(Settings().database.dsn) == VALID_DSN

    def test_a_group_reads_the_environment_at_construction_not_at_import(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A default instance is built once, at import; a factory sees the environment as it is."""
        monkeypatch.setenv("SYNTHIA_DB_DSN", VALID_DSN)
        monkeypatch.setenv("SYNTHIA_KEYVAULT_VAULT_URI", "https://vault.example")

        assert Settings().key_vault.is_configured

    @pytest.mark.parametrize("manifest", MANIFESTS, ids=lambda path: path.name)
    def test_every_manifest_name_is_one_the_settings_read(self, manifest: Path) -> None:
        declared = set(_ENV_NAME.findall(manifest.read_text(encoding="utf-8")))
        assert declared, f"{manifest.name} declares no SYNTHIA_* variable; the scan found nothing"

        unread = sorted(declared - _names_settings_read())
        assert not unread, f"{manifest.name} sets names no setting reads: {unread}"
