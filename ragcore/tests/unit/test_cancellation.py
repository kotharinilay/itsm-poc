"""``asyncio.CancelledError`` propagates, and is never swallowed.

Two kinds of test, because one kind alone would not be enough.

**Behavioural** — the helpers in :mod:`ragcore.application.cancellation` do what they claim:
cleanup runs, and the cancellation still reaches the caller.

**Static** — every async function in ``src/`` and ``workers/`` is read for the handler shapes
that would absorb a cancellation. A behavioural test can only cover the paths it exercises, and
the dangerous ``except BaseException`` is usually in the path nobody thought to exercise.
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest

from ragcore.application.cancellation import shielded_cleanup

ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOTS = (ROOT / "src", ROOT / "workers")


class TestShieldedCleanup:
    """Cleanup that survives cancellation, and a cancellation that survives cleanup."""

    async def test_cleanup_runs_on_the_happy_path(self) -> None:
        ran: list[str] = []

        async def cleanup() -> None:
            ran.append("cleanup")

        async with shielded_cleanup(cleanup):
            ran.append("body")

        assert ran == ["body", "cleanup"]

    async def test_cancellation_still_propagates_after_cleanup(self) -> None:
        """The whole point: cleanup is reliable, and the cancellation is not absorbed."""
        ran: list[str] = []

        async def cleanup() -> None:
            ran.append("cleanup")

        async def operation() -> None:
            async with shielded_cleanup(cleanup):
                await asyncio.sleep(3600)

        task = asyncio.create_task(operation())
        await asyncio.sleep(0)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert ran == ["cleanup"]
        assert task.cancelled()

    async def test_cleanup_that_awaits_still_completes(self) -> None:
        """Without the shield this is the classic failure: cleanup cancelled at its own await."""
        ran: list[str] = []

        async def cleanup() -> None:
            await asyncio.sleep(0.01)
            ran.append("cleanup finished")

        async def operation() -> None:
            async with shielded_cleanup(cleanup):
                await asyncio.sleep(3600)

        task = asyncio.create_task(operation())
        await asyncio.sleep(0)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert ran == ["cleanup finished"]

    async def test_a_failing_cleanup_does_not_replace_the_cancellation(self) -> None:
        """The caller needs to know the operation was cancelled, not that cleanup misbehaved."""

        async def cleanup() -> None:
            raise RuntimeError("cleanup blew up")

        async def operation() -> None:
            async with shielded_cleanup(cleanup):
                await asyncio.sleep(3600)

        task = asyncio.create_task(operation())
        await asyncio.sleep(0)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_cleanup_is_abandoned_rather_than_hanging_forever(self) -> None:
        """A shield with no timeout turns one hung cleanup into a task that never finishes."""

        async def cleanup() -> None:
            await asyncio.sleep(3600)

        async def operation() -> None:
            async with shielded_cleanup(cleanup, grace_seconds=0.01):
                await asyncio.sleep(3600)

        task = asyncio.create_task(operation())
        await asyncio.sleep(0)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task


class TestTheGraphPropagatesCancellation:
    """A cancelled turn stops the graph rather than finishing it in the background."""

    async def test_cancelling_a_run_leaves_nothing_executed(self) -> None:
        from uuid import uuid4

        from langgraph.checkpoint.memory import InMemorySaver

        from ragcore.domain.governance import ExecutionTreatment
        from ragcore.domain.identifiers import WorkItemId
        from ragcore.graph.builder import build_graph
        from tests.support.fakes import build_harness

        harness = build_harness()
        identity = harness.catalogue.register(
            "fixture.read.only.thing", treatment=ExecutionTreatment.AUTO
        )
        harness.catalogue.entitle(harness.tenant, identity.catalogue_id)
        compiled = build_graph(harness.deps).compile(checkpointer=InMemorySaver())

        task = asyncio.create_task(
            compiled.ainvoke(
                {
                    "session_state": "conversational",
                    "conversation": [],
                    "retrieved": [],
                    "proposal": {
                        "catalogue_id": identity.catalogue_id,
                        "catalogue_version": 1,
                        "parameters": {},
                        "source": "model",
                        "rationale": "",
                    },
                },
                config={"configurable": {"thread_id": "cancelled"}},
                context=harness.run_context(work_item_id=WorkItemId(uuid4())),
            )
        )
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert harness.execution.invocations == []


class TestNoModuleSwallowsCancellation:
    """Read every async module for the handler shapes that absorb a ``CancelledError``.

    Static rather than behavioural on purpose. ``except BaseException`` in a branch no test
    reaches is exactly the case a behavioural suite misses, and it is one character different
    from the ``except Exception`` that is usually fine.
    """

    def test_no_bare_except_anywhere(self) -> None:
        """A bare ``except:`` catches ``CancelledError`` too. Prohibited outright."""
        offenders = [
            f"{path.relative_to(ROOT)}:{node.lineno}"
            for path in _modules()
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.ExceptHandler) and node.type is None
        ]
        assert not offenders, "bare except found at:\n  " + "\n  ".join(offenders)

    def test_no_handler_catches_base_exception(self) -> None:
        """``except BaseException`` catches cancellation. There is no legitimate use here."""
        offenders = [
            f"{path.relative_to(ROOT)}:{node.lineno}"
            for path in _modules()
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.ExceptHandler) and _names(node.type) & {"BaseException"}
        ]
        assert not offenders, "except BaseException found at:\n  " + "\n  ".join(offenders)

    def test_no_handler_catches_cancelled_error_without_re_raising(self) -> None:
        """Catching it is legitimate — only to run cleanup, and only if it is re-raised."""
        offenders: list[str] = []
        for path in _modules():
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if not isinstance(node, ast.ExceptHandler):
                    continue
                if not _names(node.type) & {"CancelledError"}:
                    continue
                if not any(
                    isinstance(inner, ast.Raise) for inner in ast.walk(ast.Module(node.body, []))
                ):
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
        assert not offenders, "CancelledError caught and not re-raised at:\n  " + "\n  ".join(
            offenders
        )

    def test_nothing_suppresses_base_exception(self) -> None:
        """``contextlib.suppress(BaseException)`` is the same bug wearing a context manager."""
        offenders: list[str] = []
        for path in _modules():
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if not isinstance(node, ast.Call):
                    continue
                target = node.func
                name = (
                    target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")
                )
                if name != "suppress":
                    continue
                caught = {a.id for a in node.args if isinstance(a, ast.Name)}
                if caught & {"BaseException", "CancelledError"}:
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
        assert not offenders, "suppress() swallowing cancellation at:\n  " + "\n  ".join(offenders)

    def test_the_only_shield_is_the_one_that_re_raises(self) -> None:
        """``asyncio.shield`` has exactly one legitimate home, and this is where it lives.

        A shield elsewhere means a cancelled request holding resources until its work finishes
        anyway — which is cancellation that does not cancel.
        """
        users = {
            str(path.relative_to(ROOT)).replace("\\", "/")
            for path in _modules()
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.Attribute) and node.attr == "shield"
        }
        assert users <= {"src/ragcore/application/cancellation.py"}

    def test_there_are_async_modules_to_check(self) -> None:
        """Guards against the three tests above passing because they found nothing."""
        async_modules = [
            path
            for path in _modules()
            if any(
                isinstance(node, ast.AsyncFunctionDef)
                for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            )
        ]
        assert len(async_modules) > 5


def _modules() -> list[Path]:
    """Every Python module under ``src/`` and ``workers/``."""
    return sorted(path for root in SOURCE_ROOTS for path in root.rglob("*.py"))


def _names(node: ast.expr | None) -> set[str]:
    """The exception names one handler catches, whether written singly or as a tuple."""
    if node is None:
        return set()
    if isinstance(node, ast.Tuple):
        return {name for element in node.elts for name in _names(element)}
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, ast.Attribute):
        return {node.attr}
    return set()
