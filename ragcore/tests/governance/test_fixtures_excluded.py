"""Reference fixtures are excluded from production, and are never a real defined capability.

`.claude/rules/10-principles.md` **H-2** — reference fixtures are labelled, inert,
production-excluded, and never product. The failure this file guards against is not a bug, it is a
drift: a fixture that was
inert in September quietly becomes the thing a demo runs on in November, and by then nobody
remembers it was a fixture. The three properties that stop that are each asserted here.

**Labelled.** Every record carries ``is_reference_fixture=True`` and an identifier under
``synthia.reference.``, so a fixture is recognisable from a log line, a queue entry or an audit
record without a catalogue lookup.

**Excluded from production configuration.** :func:`~ragcore.governance.fixtures.reference_fixtures`
refuses in a production environment rather than relying on a runbook step. Note the boundary this
respects: it decides whether rows are *installed*, never what a row *means*. No treatment, role or
entitlement varies by environment, and the last test in this file asserts that separately, because
"exclude the fixtures in production" is one careless step away from "relax the gate in
development".

**Never a real capability.** A fixture MUST NOT be counted as a real defined capability,
substituted for one, or allowed to become one (`H-2`.4). The identifier check below keeps the
original scaffold's ``UC-``-prefixed placeholder names out of the fixture set, which is the
concrete form that drift took here.

Marked ``governance``: *proves treatment comes from the catalogue, never from model output*.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from ragcore.config import settings as settings_module
from ragcore.domain.governance import CapabilityKind, ExecutionTreatment
from ragcore.governance import fixtures
from ragcore.governance.fixtures import (
    REFERENCE_FIXTURES,
    REFERENCE_PREFIX,
    ReferenceFixtureInProductionError,
    is_reference_operation,
    reference_fixtures,
)

pytestmark = pytest.mark.governance

NON_PRODUCTION = ("local", "development", "staging")
"""Every environment ``Settings.environment`` permits, except production."""


class TestThereIsOneFixturePerTreatment:
    """Four, and the reason there are four is that the treatments differ."""

    def test_every_treatment_has_exactly_one_fixture(self) -> None:
        """A catalogue holding one entry exercises the lookup and none of the distinctions."""
        by_treatment: dict[ExecutionTreatment, list[str]] = {}

        for record in REFERENCE_FIXTURES:
            by_treatment.setdefault(record.treatment, []).append(str(record.identity))

        assert set(by_treatment) == set(ExecutionTreatment), (
            "missing a fixture for "
            f"{sorted(t.value for t in set(ExecutionTreatment) - set(by_treatment))}"
        )
        for treatment, identities in by_treatment.items():
            assert len(identities) == 1, f"{treatment.value} has {identities}"

    def test_there_are_exactly_four(self) -> None:
        assert len(list(REFERENCE_FIXTURES)) == len(ExecutionTreatment)

    def test_the_not_allowed_fixture_accepts_no_role(self) -> None:
        """An entry naming an approver while being ``NOT_ALLOWED`` would describe somebody who
        could decide. The whole point of that treatment is that the operation is not askable.
        """
        withheld = next(
            record
            for record in REFERENCE_FIXTURES
            if record.treatment is ExecutionTreatment.NOT_ALLOWED
        )
        assert withheld.accepted_roles.is_empty

    def test_the_staff_approval_fixture_names_a_role_somebody_can_hold(self) -> None:
        """Otherwise deterministic policy refuses it and the ``STAFF_APPROVAL`` path is never
        exercised — which would make the fixture set look complete while covering three cases.
        """
        staff = next(
            record
            for record in REFERENCE_FIXTURES
            if record.treatment is ExecutionTreatment.STAFF_APPROVAL
        )
        assert not staff.accepted_roles.is_empty


class TestEveryFixtureIsLabelled:
    """Recognisable without a catalogue lookup, and recognisable two independent ways."""

    def test_every_record_carries_the_flag(self) -> None:
        for record in REFERENCE_FIXTURES:
            assert record.is_reference_fixture, f"{record.identity} is not labelled"

    def test_every_identifier_carries_the_prefix(self) -> None:
        for record in REFERENCE_FIXTURES:
            assert record.identity.catalogue_id.startswith(REFERENCE_PREFIX)

    def test_the_two_labels_never_disagree(self) -> None:
        """The flag is authoritative and the prefix is the cheap answer. They must agree.

        A fixture with the flag and no prefix would be invisible in a log; one with the prefix and
        no flag would be treated as product by the catalogue.
        """
        for record in REFERENCE_FIXTURES:
            assert is_reference_operation(record.identity) == record.is_reference_fixture


class TestEveryFixtureIsInert:
    """Inert means *has no external effect*, not *is not wired up yet*."""

    def test_no_fixture_names_an_external_system(self) -> None:
        for record in REFERENCE_FIXTURES:
            assert record.commands is not None
            assert record.commands["externalSystem"] is None, (
                f"{record.identity} names an external system. A fixture that reaches one is not "
                f"inert, whatever its command set says it does."
            )

    def test_no_fixture_claims_a_verification_tool(self) -> None:
        """There is nothing to verify against, and claiming otherwise claims a confirmation the
        platform could not perform (ADR-0004).
        """
        for record in REFERENCE_FIXTURES:
            assert record.verification_tool is None
            assert not record.can_be_server_confirmed

    def test_every_fixture_discloses_its_command_set_in_full(self) -> None:
        """The disclosure machinery is something a populated catalogue exists to exercise."""
        for record in REFERENCE_FIXTURES:
            assert record.commands
            assert record.content_hash

    def test_the_content_hash_binds_the_disclosed_commands(self) -> None:
        """Recomputed here rather than trusted, because the hash is what an approval binds to."""
        for record in REFERENCE_FIXTURES:
            assert record.content_hash == fixtures._content_hash(dict(record.commands or {}))  # noqa: SLF001

    def test_the_hash_is_stable_across_dictionary_ordering(self) -> None:
        """A hash that varied with insertion order would fail an approval nobody changed."""
        first = fixtures._content_hash({"a": 1, "b": 2})  # noqa: SLF001
        second = fixtures._content_hash({"b": 2, "a": 1})  # noqa: SLF001
        assert first == second

    def test_the_read_fixture_is_the_only_one_that_is_not_an_action(self) -> None:
        """An action that does nothing is still an action: the audit obligations follow the kind."""
        kinds = {record.identity.catalogue_id: record.kind for record in REFERENCE_FIXTURES}
        reads = [name for name, kind in kinds.items() if kind is CapabilityKind.READ]
        assert len(reads) == 1


class TestExcludedFromProductionConfiguration:
    """The exclusion is enforced, not documented."""

    @pytest.mark.parametrize("environment", NON_PRODUCTION)
    def test_the_fixtures_are_available_outside_production(self, environment: str) -> None:
        """The other half of the rule. A loader that refused everywhere would be useless and
        would make the production refusal untestable.
        """
        assert list(reference_fixtures(environment)) == list(REFERENCE_FIXTURES)

    def test_production_raises_rather_than_returning_nothing(self) -> None:
        """An empty catalogue would install nothing and report success, and the next person could
        not tell whether the fixtures were excluded or the seeding step was broken.
        """
        with pytest.raises(ReferenceFixtureInProductionError):
            reference_fixtures("production")

    def test_the_refusal_says_why(self) -> None:
        with pytest.raises(ReferenceFixtureInProductionError) as raised:
            reference_fixtures("production")

        assert "H-2" in str(raised.value)

    def test_the_environment_name_matches_the_settings_literal(self) -> None:
        """A refusal keyed on ``"prod"`` would never fire.

        Read from ``Settings`` so the two cannot drift: the string this module compares against and
        the string a deployed process actually carries are the same string.
        """
        annotation = settings_module.Settings.model_fields["environment"].annotation
        permitted = set(getattr(annotation, "__args__", ()))

        assert fixtures.PRODUCTION_ENVIRONMENT in permitted, (
            f"fixtures.PRODUCTION_ENVIRONMENT is {fixtures.PRODUCTION_ENVIRONMENT!r}, which is not "
            f"one of {sorted(permitted)}. The exclusion would never fire."
        )
        assert set(NON_PRODUCTION) | {fixtures.PRODUCTION_ENVIRONMENT} == permitted, (
            "Settings.environment gained or lost a value. Decide explicitly whether the fixtures "
            "belong in it rather than letting the new environment inherit an answer."
        )


class TestAFixtureIsNeverAUseCase:
    """A fixture is never a real defined capability, and never was one waiting to be finished."""

    def test_no_fixture_is_named_for_a_use_case(self) -> None:
        for record in REFERENCE_FIXTURES:
            catalogue_id = record.identity.catalogue_id.lower()
            assert "uc-" not in catalogue_id and "uc_" not in catalogue_id, (
                f"{record.identity} is named for a use case. A fixture MUST NOT be counted as, "
                f"substituted for, or allowed to become a real defined capability "
                f"(10-principles.md H-2)."
            )

    def test_an_arbitrary_operation_is_not_a_reference_operation(self) -> None:
        """The negative half: the prefix check must actually discriminate."""
        from ragcore.domain.identifiers import OperationIdentity

        assert not is_reference_operation(OperationIdentity("servicenow.close-incident", 1))
        assert is_reference_operation(OperationIdentity(f"{REFERENCE_PREFIX}echo", 1))

    def test_nothing_outside_the_fixtures_module_declares_a_reference_operation(self) -> None:
        """One place declares them, so there is one place to look when counting them.

        A second declaration elsewhere is how a fifth fixture appears without anybody deciding to
        add one.
        """
        source_root = Path(inspect.getsourcefile(fixtures) or "").resolve().parents[1]
        offenders = [
            path.relative_to(source_root)
            for path in source_root.rglob("*.py")
            if path.name != "fixtures.py" and REFERENCE_PREFIX in path.read_text(encoding="utf-8")
        ]

        assert not offenders, f"these modules declare a reference operation: {offenders}"


class TestTheExclusionDoesNotBecomeAnEnvironmentBranch:
    """The rule this file is one careless step away from breaking."""

    def test_no_governance_module_reads_the_environment(self) -> None:
        """Except ``fixtures.py``, and there only to decide whether rows are *installed*.

        A treatment, a role or an entitlement that varied by environment would mean the control
        exercised in testing is not the control running in production.
        """
        package = Path(inspect.getsourcefile(fixtures) or "").resolve().parent
        offenders: list[str] = []

        for path in package.glob("*.py"):
            if path.name == "fixtures.py":
                continue
            text = path.read_text(encoding="utf-8")
            if "environment" in text or "getenv" in text or "os.environ" in text:
                offenders.append(path.name)

        assert not offenders, (
            f"{offenders} reference the environment. Governance decisions must be identical in "
            f"every environment."
        )

    def test_the_fixtures_module_uses_the_environment_only_to_refuse(self) -> None:
        """It never reads it to choose a treatment, a role or an entitlement."""
        source = inspect.getsource(fixtures.reference_fixtures)

        assert "PRODUCTION_ENVIRONMENT" in source
        assert "treatment" not in source
        assert "accepted_roles" not in source
