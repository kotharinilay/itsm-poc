"""The eleven published vw_*_v1 views — the read contract.

Revision ID: 0018_published_views
Revises: 0017_work_item_immutability

**The only coupling point between the two deployables** (``contracts/read-views.md``, ADR-0001).
The definitions live in :mod:`ragcore.persistence.views` as ``alembic_utils`` entities, so
``--autogenerate`` proposes a ``create_or_replace`` when one changes rather than letting a view
drift silently away from the file that is supposed to define it.

**This revision imports the view module, and that is a deliberate exception** to the rule that a
migration is a self-contained snapshot. A view is a *replaceable* entity: its current definition is
the whole of its state, there is no data to migrate, and alembic_utils exists precisely so the
definition has one home rather than a copy per revision. Tables are different — those revisions
write their DDL out in full, because a table revision is a step in a history rather than a
statement of the present.

**A view is never altered in place.** A change adds ``_v2`` alongside; ``_v1`` is dropped a release
later once the monolith no longer references it. That is why this revision creates and drops, and
why a future revision will not edit it.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from ragcore.persistence.views import ALL_VIEWS

revision: str = "0018_published_views"
down_revision: str | None = "0017_work_item_immutability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create every published view, in dependency order."""
    for view in ALL_VIEWS:
        op.create_entity(view)


def downgrade() -> None:
    """Drop them in reverse, so a view is never dropped before something selecting from it."""
    for view in reversed(ALL_VIEWS):
        op.drop_entity(view)
