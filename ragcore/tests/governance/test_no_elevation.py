"""No catalogue entry can be created or activated with ``requires_elevation = true``.

ADR-0004 leaves elevation out of this release, and "left out" has to mean something stronger than
"nobody has written one yet". Three independent refusals stand between an elevated operation and
execution, and this file asserts each of them separately, because each fails in a different way and
a suite that proved only one would be satisfied by the weakest:

1. **The database refuses the row.** ``governance_record`` carries a ``CHECK`` constraint,
   ``alpha_permits_no_elevation``. This is the one that holds against a migration, a data load, a
   psql session and anything else that writes SQL.
2. **The record refuses to be built.** :class:`~ragcore.governance.catalogue.CatalogueRecord`
   raises, so a row that somehow got past the constraint — a restored dump, a future migration that
   dropped it — cannot become something governance will act on.
3. **Policy refuses the treatment.** ``assign_treatment`` maps an elevated entry to ``NOT_ALLOWED``
   with its own reason, so even a record that existed could not be authorized.

The redundancy is the intent, and it is not belt-and-braces for its own sake: constraint 1 is
invisible to a unit test, constraint 3 is invisible to anything holding a malformed record, and 2 is
the only one that catches a row that is already in the table.

Marked ``governance``: *proves treatment comes from the catalogue, never from model output*.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy import CheckConstraint, Table

from ragcore.domain.governance import CapabilityKind, ExecutionTreatment, RiskTier
from ragcore.domain.identifiers import OperationIdentity, PrincipalId
from ragcore.domain.proposal import ProposedOperation
from ragcore.domain.roles import RoleSet, StaffRole
from ragcore.governance import gate
from ragcore.governance.catalogue import (
    CatalogueRecord,
    ElevationNotPermittedError,
    record_from_row,
)
from ragcore.governance.fixtures import REFERENCE_FIXTURES
from ragcore.governance.gate import GateDisposition, GateReason, GateRequest
from ragcore.governance.policy import TreatmentReason, assign_treatment
from ragcore.persistence import models
from tests.support.fakes import FIXED_NOW, admitted_tenant

pytestmark = pytest.mark.governance

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations" / "versions"


class _ElevatedRow:
    """A row claiming elevation, as a restored dump or a dropped constraint would produce one."""

    catalogue_id = "test.elevated"
    version = 1
    kind = CapabilityKind.ACTION
    default_treatment = ExecutionTreatment.AUTO
    accepted_roles = ["technician"]
    is_reference_fixture = False
    requires_elevation = True
    risk_tier = RiskTier.LOW_IMPACT
    commands = None
    content_hash = None
    verification_tool = None


class TestTheDatabaseRefusesTheRow:
    """The constraint that holds against anything writing SQL, including a migration."""

    def test_the_check_constraint_is_declared_on_the_model(self) -> None:
        table = cast(Table, models.GovernanceRecord.__table__)
        constraints = {str(constraint.name) for constraint in table.constraints}

        # The naming convention prefixes a check constraint with `ck_<table>_`, so the declared
        # name is a suffix of the resolved one. Matched on the suffix rather than the whole string
        # so a convention change does not read as a missing constraint.
        assert any(name.endswith("alpha_permits_no_elevation") for name in constraints), (
            "governance_record lost its elevation CHECK constraint. It is the only refusal that "
            "applies to a plain SQL INSERT."
        )

    def test_the_constraint_holds_the_column_false_rather_than_merely_bounding_it(self) -> None:
        """``requires_elevation = false``, not ``IN (true, false)`` or a nullable column.

        Read as text because the assertion is about what was written: a constraint that permitted
        both values would satisfy "a constraint exists" and prohibit nothing.
        """
        table = cast(Table, models.GovernanceRecord.__table__)
        declared = next(
            str(cast(CheckConstraint, constraint).sqltext)
            for constraint in table.constraints
            if str(constraint.name or "").endswith("alpha_permits_no_elevation")
        )

        assert "requires_elevation = false" in declared.replace("  ", " ").lower()

    def test_the_column_is_not_nullable(self) -> None:
        """A NULL is neither true nor false, and a ``CHECK`` passes on NULL."""
        table = cast(Table, models.GovernanceRecord.__table__)
        assert not table.c.requires_elevation.nullable

    def test_a_migration_created_the_constraint(self) -> None:
        """The model declaring it is not the same as the deployed database holding it."""
        found = any(
            "alpha_permits_no_elevation" in path.read_text(encoding="utf-8")
            for path in MIGRATIONS.glob("*.py")
        )

        assert found, (
            "no migration under migrations/versions/ mentions alpha_permits_no_elevation. A "
            "constraint that exists only on the model is a constraint the database does not have."
        )


class TestTheRecordRefusesToBeBuilt:
    """The refusal that catches a row already in the table."""

    def test_constructing_an_elevated_record_raises(self) -> None:
        with pytest.raises(ElevationNotPermittedError):
            CatalogueRecord(
                identity=OperationIdentity("test.elevated", 1),
                treatment=ExecutionTreatment.AUTO,
                accepted_roles=RoleSet.of(StaffRole.TECHNICIAN),
                kind=CapabilityKind.ACTION,
                risk_tier=RiskTier.LOW_IMPACT,
                is_reference_fixture=False,
                requires_elevation=True,
            )

    def test_an_elevated_row_cannot_be_read_into_a_record(self) -> None:
        """The path a restored dump would actually take."""
        with pytest.raises(ElevationNotPermittedError):
            record_from_row(_ElevatedRow())

    def test_the_refusal_is_not_a_silent_correction(self) -> None:
        """It raises rather than coercing the flag to false.

        Coercion would be worse than either alternative: the operation would execute, the audit
        record would say it was never elevated, and nobody would be able to tell that a row
        claiming elevation had ever been in the catalogue.
        """
        with pytest.raises(ElevationNotPermittedError) as raised:
            record_from_row(_ElevatedRow())

        assert "ADR-0004" in str(raised.value)

    @pytest.mark.parametrize("treatment", list(ExecutionTreatment))
    def test_no_treatment_makes_elevation_acceptable(self, treatment: ExecutionTreatment) -> None:
        """Including ``STAFF_APPROVAL`` — a human cannot approve their way past this."""
        with pytest.raises(ElevationNotPermittedError):
            CatalogueRecord(
                identity=OperationIdentity("test.elevated", 1),
                treatment=treatment,
                accepted_roles=RoleSet.of(StaffRole.TECHNICIAN),
                kind=CapabilityKind.ACTION,
                risk_tier=RiskTier.LOW_IMPACT,
                is_reference_fixture=False,
                requires_elevation=True,
            )


class TestPolicyRefusesTheTreatment:
    """The third refusal: even a record that existed could not be authorized."""

    def test_an_elevated_entry_is_not_allowed(self) -> None:
        """Asserted against a stand-in, because a real record cannot be constructed.

        The stand-in is the point of the test: policy must not depend on the record type having
        already refused, or the two checks become one check written twice.
        """

        class Elevated:
            identity = OperationIdentity("test.elevated", 1)
            treatment = ExecutionTreatment.AUTO
            accepted_roles = RoleSet.of(StaffRole.TECHNICIAN)
            kind = CapabilityKind.ACTION
            is_reference_fixture = False
            requires_elevation = True

        decision = assign_treatment(Elevated(), is_entitled=True)

        assert decision.treatment is ExecutionTreatment.NOT_ALLOWED
        assert decision.reason is TreatmentReason.ELEVATION_REFUSED

    def test_the_gate_refuses_it_and_does_not_offer_it_for_approval(self) -> None:
        """``NOT_ALLOWED`` is not askable. Surfacing it to a queue would invite an approval."""

        class Elevated:
            identity = OperationIdentity("test.elevated", 1)
            treatment = ExecutionTreatment.STAFF_APPROVAL
            accepted_roles = RoleSet.of(StaffRole.TECHNICIAN)
            kind = CapabilityKind.ACTION
            is_reference_fixture = False
            requires_elevation = True

        outcome = gate.evaluate(
            GateRequest(
                tenant=admitted_tenant(),
                proposal=ProposedOperation(identity=OperationIdentity("test.elevated", 1)),
                entry=Elevated(),
                is_entitled=True,
                requester=PrincipalId(uuid4()),
                now=FIXED_NOW,
            )
        )

        assert outcome.disposition is GateDisposition.REFUSE
        assert outcome.reason is GateReason.TREATMENT_REFUSES
        assert outcome.treatment_reason is TreatmentReason.ELEVATION_REFUSED
        assert outcome.suspends_on is None


class TestNothingShippedClaimsElevation:
    """The rule applied to what is actually in the repository."""

    def test_no_reference_fixture_requires_elevation(self) -> None:
        for record in REFERENCE_FIXTURES:
            assert not record.requires_elevation, f"{record.identity} claims elevation"

    def test_no_module_sets_the_flag_true(self) -> None:
        """A source sweep, because the next elevated entry will be written before it is inserted."""
        source_root = Path(inspect.getsourcefile(gate) or "").resolve().parents[1]
        offenders = [
            path.relative_to(source_root)
            for path in source_root.rglob("*.py")
            if "requires_elevation=True" in path.read_text(encoding="utf-8").replace(" ", "")
        ]

        assert not offenders, (
            f"these modules construct an entry requiring elevation: {offenders}. This release "
            f"permits none (ADR-0004)."
        )
