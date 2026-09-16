"""PostgreSQL holds credential **references**. It never holds a credential.

Credentials for a third-party system are held per organisation and per system, resolved from the
single secret source, and MUST NEVER appear in conversation, the step trail, telemetry or audit
records (spec FR-EXT-016, FR-DEMO-012). The division that makes that workable is:

* ``tenant_entitlement.credential_reference`` — a Key Vault secret **name**, in PostgreSQL.
* Key Vault — the **value**, fetched at the point of use through managed identity.

These run against a real PostgreSQL because the properties are the database's: the entitlement row
is what gates the credential, and ``enabled = false`` resolving nothing is a predicate in a
statement rather than a rule a caller remembers.

**The value never comes back through this path, and that is asserted rather than assumed.** The
repository selects one column and it is the reference; there is no column for a value, so the test
that a value cannot be read is a test about the schema, which is where that guarantee belongs.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ragcore.domain.governance import ExecutionTreatment
from ragcore.domain.identifiers import EntraTenantId, TenantId
from ragcore.domain.tenancy import TenantContext, TenantStatus
from ragcore.integrations.credentials import (
    CredentialNotEntitledError,
    TenantCredentialResolver,
    catalogue_prefix_for,
)
from ragcore.persistence import models
from ragcore.persistence.repositories import EntitlementCredentials
from tests.support.integrations import PLACEHOLDER_SECRET, FakeSecretResolver

pytestmark = pytest.mark.integration

SYSTEM = "onelogin"
CATALOGUE_ID = f"{SYSTEM}.user.read"
REFERENCE = "contoso-onelogin-credential"
"""A secret **name**. Not a secret: it identifies where a value lives and grants nothing."""


async def _organisation(
    sessions: async_sessionmaker[AsyncSession],
    *,
    reference: str | None = REFERENCE,
    enabled: bool = True,
) -> TenantContext:
    """An admitted organisation, entitled to one capability with one credential reference."""
    tenant_id, entra_tid = uuid4(), uuid4()

    async with sessions() as session, session.begin():
        await session.execute(
            insert(models.TENANT_MAPPING).values(
                tenant_id=tenant_id,
                entra_tid=entra_tid,
                display_name="Contoso",
                status=TenantStatus.ACTIVE.value,
            )
        )
        # The catalogue is platform-wide rather than per organisation — which is the point of the
        # entitlement table — so a test with two organisations registers the capability once.
        await session.execute(
            pg_insert(models.GOVERNANCE_RECORD)
            .values(
                catalogue_id=CATALOGUE_ID,
                version=1,
                kind="read",
                default_treatment=ExecutionTreatment.STAFF_APPROVAL.value,
                accepted_roles=["technician"],
                is_reference_fixture=True,
                requires_elevation=False,
                risk_tier="informational",
                commands={"steps": ["read"]},
            )
            .on_conflict_do_nothing()
        )
        await session.execute(
            insert(models.TENANT_ENTITLEMENT).values(
                tenant_id=tenant_id,
                catalogue_id=CATALOGUE_ID,
                enabled=enabled,
                credential_reference=reference,
            )
        )

    return TenantContext.from_admitted_identity(
        TenantId(tenant_id), EntraTenantId(entra_tid), TenantStatus.ACTIVE
    )


class TestTheReferenceIsReadFromTheEntitlement:
    """What PostgreSQL contributes: which organisation may use which system's credential."""

    async def test_it_resolves_the_reference_for_an_entitled_organisation(
        self, sessions: async_sessionmaker[AsyncSession]
    ) -> None:
        tenant = await _organisation(sessions)

        reference = await EntitlementCredentials(sessions).credential_reference(
            tenant, catalogue_prefix_for(SYSTEM)
        )

        assert reference == REFERENCE

    async def test_a_disabled_entitlement_resolves_nothing(
        self, sessions: async_sessionmaker[AsyncSession]
    ) -> None:
        """Revoking an entitlement revokes the ability to authenticate, rather than leaving a
        working credential behind a closed door."""
        tenant = await _organisation(sessions, enabled=False)

        assert (
            await EntitlementCredentials(sessions).credential_reference(
                tenant, catalogue_prefix_for(SYSTEM)
            )
            is None
        )

    async def test_an_entitlement_naming_no_credential_resolves_nothing(
        self, sessions: async_sessionmaker[AsyncSession]
    ) -> None:
        tenant = await _organisation(sessions, reference=None)

        assert (
            await EntitlementCredentials(sessions).credential_reference(
                tenant, catalogue_prefix_for(SYSTEM)
            )
            is None
        )

    async def test_one_organisations_reference_is_invisible_to_another(
        self, sessions: async_sessionmaker[AsyncSession]
    ) -> None:
        """The tenant predicate, on the table that holds the reference. There is no global
        credential and no path to another organisation's."""
        await _organisation(sessions)
        stranger = await _organisation(sessions, reference="other-organisation-credential")

        reference = await EntitlementCredentials(sessions).credential_reference(
            stranger, catalogue_prefix_for(SYSTEM)
        )

        assert reference == "other-organisation-credential"

    async def test_a_different_system_resolves_nothing(
        self, sessions: async_sessionmaker[AsyncSession]
    ) -> None:
        """Credentials are per organisation **and per system**. An entitlement to one system's
        capability is not a credential for another's."""
        tenant = await _organisation(sessions)

        assert (
            await EntitlementCredentials(sessions).credential_reference(
                tenant, catalogue_prefix_for("duo")
            )
            is None
        )


class TestTheValueComesFromKeyVaultAndNowhereElse:
    """The two halves joined: a reference from PostgreSQL, a value from the vault."""

    async def test_the_resolver_looks_up_the_reference_the_row_named(
        self, sessions: async_sessionmaker[AsyncSession]
    ) -> None:
        tenant = await _organisation(sessions)
        secrets = FakeSecretResolver()

        value = await TenantCredentialResolver(EntitlementCredentials(sessions), secrets).resolve(
            tenant, SYSTEM
        )

        assert secrets.resolved == [REFERENCE]
        assert value.reveal() == PLACEHOLDER_SECRET

    async def test_the_resolved_value_refuses_to_render_itself(
        self, sessions: async_sessionmaker[AsyncSession]
    ) -> None:
        """The three ways a secret actually escapes — a log line, a span attribute, an f-string —
        all yield ``<redacted>``."""
        tenant = await _organisation(sessions)

        value = await TenantCredentialResolver(
            EntitlementCredentials(sessions), FakeSecretResolver()
        ).resolve(tenant, SYSTEM)

        assert PLACEHOLDER_SECRET not in str(value)
        assert PLACEHOLDER_SECRET not in repr(value)
        assert PLACEHOLDER_SECRET not in f"{value}"

    async def test_an_organisation_without_an_entitlement_is_refused(
        self, sessions: async_sessionmaker[AsyncSession]
    ) -> None:
        """A refusal rather than ``None``, because the tempting decision about ``None`` — carry on,
        or use a shared credential — is the cross-organisation leak this arrangement prevents."""
        tenant = await _organisation(sessions, reference=None)

        with pytest.raises(CredentialNotEntitledError):
            await TenantCredentialResolver(
                EntitlementCredentials(sessions), FakeSecretResolver()
            ).resolve(tenant, SYSTEM)

    async def test_the_refusal_names_neither_the_reference_nor_a_value(
        self, sessions: async_sessionmaker[AsyncSession]
    ) -> None:
        """Error messages reach logs."""
        tenant = await _organisation(sessions, reference=None)

        with pytest.raises(CredentialNotEntitledError) as raised:
            await TenantCredentialResolver(
                EntitlementCredentials(sessions), FakeSecretResolver()
            ).resolve(tenant, SYSTEM)

        message = str(raised.value)
        assert REFERENCE not in message
        assert PLACEHOLDER_SECRET not in message
        assert SYSTEM in message


class TestPostgreSqlHasNowhereToPutAValue:
    """The schema-level half. The guarantee is structural, not procedural."""

    def test_the_entitlement_table_has_a_reference_column_and_no_value_column(self) -> None:
        columns = set(models.TENANT_ENTITLEMENT.c.keys())

        assert "credential_reference" in columns
        assert not columns & {
            "credential",
            "credential_value",
            "secret",
            "secret_value",
            "password",
            "api_key",
            "access_token",
        }

    def test_no_table_in_the_schema_declares_a_secret_value_column(self) -> None:
        """Across every table, not only this one. A secret value put somewhere else in PostgreSQL
        is still a secret value in PostgreSQL."""
        forbidden = {"password", "secret_value", "api_key", "access_token", "client_secret"}
        offenders = [
            f"{name}.{column}"
            for name, table in models.TABLES_BY_NAME.items()
            for column in table.c.keys()  # noqa: SIM118 — Table.c is not a plain mapping
            if column in forbidden
        ]

        assert not offenders, (
            f"a column named for a secret value exists in PostgreSQL: {offenders}. "
            "Configuration and rows hold references; Key Vault holds values."
        )
