"""Grant the Integrations principal SELECT on the four views its own code already reads.

Revision ID: 0025_integrations_recovery_views
Revises: 0024_integrations_audit_grant

**The service's queries and its grants had drifted apart.** Revision 0021 granted exactly two views
(`vw_tenant_entitlement_v1`, `vw_connector_credential_ref_v1`), but the Integrations Service reads
four more, and PostgreSQL refused every one of them as ``synthia_integrations``:

========================== ================================================= ===================
View                       Read by                                           Requirement
========================== ================================================= ===================
``vw_session_summary_v1``  ``TenantResolver.tenant_for_session``             FR-INTEG-018
``vw_work_item_v1``        ``TenantResolver.tenant_for_work_item``,          FR-INTEG-018/019
                           ``JobRepository.load``
``vw_tenant_v1``           ``JobRepository.load`` (organisation active)      FR-INTEG-019
``vw_governance_catalogue  ``CatalogueRepository`` (catalogue, registered    FR-INTEG-019
_v1``                      version)
========================== ================================================= ===================

Without them the synchronous path cannot recover an organisation from the object a caller names, and
the asynchronous path cannot re-verify tenant status, work state and catalogue version at execution.
Both are MUSTs.

**Why these four and still not the rest.** Revision 0021 kept the service away from the other views
for a stated threat: a component holding connector credentials should not be able to read customer
transcripts or the actor chain. None of these four carries either. `vw_session_summary_v1` has no
message body, `vw_work_item_v1` deliberately omits `target`, `vw_tenant_v1` omits
`retention_overrides`, and `vw_governance_catalogue_v1` holds no tenant data at all. The views that
*do* carry that material — `vw_session_message_v1`, `vw_session_step_v1`, `vw_message_feedback_v1`,
`vw_audit_event_v1`, `vw_approval_queue_v1`, `vw_approval_unexecuted_v1`, `vw_dashboard_rollup_v1` —
stay ungranted, and ``tests/security/test_integration_grants.py`` asserts the refusal for each.

**This revision creates no object.** Grants only, so autogenerate sees no difference.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0025_integrations_recovery_views"
down_revision: str | None = "0024_integrations_audit_grant"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"
INTEGRATIONS = "synthia_integrations"

RECOVERY_VIEWS: tuple[str, ...] = (
    "vw_session_summary_v1",
    "vw_work_item_v1",
    "vw_tenant_v1",
    "vw_governance_catalogue_v1",
)
"""Listed by name rather than imported, so this revision stays a snapshot of what it granted."""

# noqa on the interpolations below for the same reason as revisions 0019, 0021 and 0024: a DCL
# identifier cannot be a bound parameter in PostgreSQL, and every value here is a constant above.


def upgrade() -> None:
    """Grant SELECT on the four recovery views, and nothing else."""
    for view in RECOVERY_VIEWS:
        op.execute(f"GRANT SELECT ON {SCHEMA}.{view} TO {INTEGRATIONS}")  # noqa: S608


def downgrade() -> None:
    """Revoke exactly what the upgrade granted."""
    for view in reversed(RECOVERY_VIEWS):
        op.execute(f"REVOKE SELECT ON {SCHEMA}.{view} FROM {INTEGRATIONS}")  # noqa: S608
