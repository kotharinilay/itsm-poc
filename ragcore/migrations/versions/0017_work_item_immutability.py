"""work_item authority fields, made immutable at the database permission boundary.

Revision ID: 0017_work_item_immutability
Revises: 0016_ingestion_run

**This is the structural control, not a convention** (constitution Principle III, spec FR-EXEC-008).
Six fields carry authority: ``tenant_id``, ``session_id``, ``requested_by_oid``, ``case_reference``,
``governed_action`` and ``target``. An application-side check protects only the code paths that
remember to call it; a trigger protects the row from every path, including a migration, a console
session and a future repository nobody has written yet.

**Three of the six are write-once rather than never-writable.** ``case_reference`` is set when the
triage gate fires, ``governed_action`` and ``target`` when an operation is proposed. The rule is
therefore *null may become a value; a value may never become a different value, and may never
return to null* — which is what makes retargeting approved work impossible rather than merely
prohibited. The other three are set at insert and never change at all.

Why a trigger rather than column-level ``REVOKE``: PostgreSQL's column privileges would block the
legitimate first write as well as the illegitimate second, and splitting the insert across two
principals to work around that would put DDL-adjacent rights on a runtime path.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0017_work_item_immutability"
down_revision: str | None = "0016_ingestion_run"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "platform"

# `IS DISTINCT FROM` rather than `<>`: a null on either side makes `<>` yield null, which is not
# true, which would let exactly the null-to-value-to-null transition this guard exists to stop.
CREATE_FUNCTION = """
CREATE FUNCTION platform.work_item_authority_is_immutable()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
        RAISE EXCEPTION
            'work_item.tenant_id is immutable (work_item_id=%)', OLD.work_item_id
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    IF NEW.session_id IS DISTINCT FROM OLD.session_id THEN
        RAISE EXCEPTION
            'work_item.session_id is immutable (work_item_id=%)', OLD.work_item_id
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    IF NEW.requested_by_oid IS DISTINCT FROM OLD.requested_by_oid THEN
        RAISE EXCEPTION
            'work_item.requested_by_oid is immutable (work_item_id=%)', OLD.work_item_id
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    IF OLD.case_reference IS NOT NULL
       AND NEW.case_reference IS DISTINCT FROM OLD.case_reference THEN
        RAISE EXCEPTION
            'work_item.case_reference is immutable once set (work_item_id=%)', OLD.work_item_id
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    IF OLD.governed_action IS NOT NULL
       AND NEW.governed_action IS DISTINCT FROM OLD.governed_action THEN
        RAISE EXCEPTION
            'work_item.governed_action is immutable once set (work_item_id=%)', OLD.work_item_id
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    IF OLD.target IS NOT NULL AND NEW.target IS DISTINCT FROM OLD.target THEN
        RAISE EXCEPTION
            'work_item.target is immutable once set (work_item_id=%)', OLD.work_item_id
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    RETURN NEW;
END;
$$
"""

CREATE_TRIGGER = """
CREATE TRIGGER work_item_authority_is_immutable
BEFORE UPDATE ON platform.work_item
FOR EACH ROW
EXECUTE FUNCTION platform.work_item_authority_is_immutable()
"""


def upgrade() -> None:
    """Install the guard."""
    op.execute(CREATE_FUNCTION)
    op.execute(CREATE_TRIGGER)


def downgrade() -> None:
    """Remove it. The trigger first, so the function is unreferenced when it is dropped."""
    op.execute("DROP TRIGGER work_item_authority_is_immutable ON platform.work_item")
    op.execute("DROP FUNCTION platform.work_item_authority_is_immutable()")
