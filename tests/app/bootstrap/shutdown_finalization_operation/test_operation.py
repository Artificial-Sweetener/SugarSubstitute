#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Verify durable shutdown finalization ordering and failure boundaries."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import NoReturn, cast

import pytest

from substitute.app.bootstrap.lifecycle import ManagedComfyCleanupResult
from substitute.app.bootstrap.shutdown_finalization_operation import (
    ShutdownFinalizationOperation,
)
from substitute.application.workspace_state import (
    PreparedSessionSave,
    SessionSaveResult,
)
from substitute.domain.session import SESSION_SNAPSHOT_SCHEMA_VERSION, SessionSnapshot
from substitute.domain.workspace_snapshot import WorkspaceSnapshot
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)


def test_shutdown_persists_session_before_managed_cleanup() -> None:
    """Preserve terminal archive and JSON durability before process cleanup."""

    events: list[str] = []
    prepared = _prepared()
    cleanup_result = cast(ManagedComfyCleanupResult, object())
    source_shell = object()
    operation = ShutdownFinalizationOperation(
        prepare_session=lambda source: _record_preparation(
            events,
            prepared,
            source=source,
            expected_source=source_shell,
        ),
        persist_session=lambda value: _record_persistence(events, value),
        cleanup_managed_comfy=lambda: _record_cleanup(events, cleanup_result),
    )

    operation.prepare(source_shell)
    result = operation.run()

    assert result is cleanup_result
    assert events == ["prepare", "persist", "cleanup"]


def test_shutdown_preparation_failure_prevents_cleanup() -> None:
    """Fail closed when terminal owner-thread capture is unavailable."""

    cleanup_calls: list[str] = []
    operation = ShutdownFinalizationOperation(
        prepare_session=lambda _source: _raise(OSError("capture failed")),
        persist_session=lambda _value: _save_result(),
        cleanup_managed_comfy=lambda: _unexpected_cleanup(cleanup_calls),
    )

    operation.prepare(object())

    with pytest.raises(RuntimeError, match="preparation failed"):
        operation.run()
    assert cleanup_calls == []


def test_shutdown_persistence_failure_prevents_cleanup() -> None:
    """Fail closed when terminal state cannot become durable."""

    cleanup_calls: list[str] = []
    operation = ShutdownFinalizationOperation(
        prepare_session=lambda _source: _prepared(),
        persist_session=lambda _value: _raise(OSError("disk full")),
        cleanup_managed_comfy=lambda: _unexpected_cleanup(cleanup_calls),
    )
    operation.prepare(object())

    with pytest.raises(OSError, match="disk full"):
        operation.run()
    assert cleanup_calls == []


def _record_preparation(
    events: list[str],
    prepared: PreparedSessionSave,
    *,
    source: object | None,
    expected_source: object,
) -> PreparedSessionSave:
    """Record and return one prepared save."""

    assert source is expected_source
    events.append("prepare")
    return prepared


def _record_persistence(
    events: list[str],
    prepared: PreparedSessionSave,
) -> SessionSaveResult:
    """Record persistence for the expected prepared value."""

    assert prepared == _prepared()
    events.append("persist")
    return _save_result()


def _record_cleanup(
    events: list[str],
    result: ManagedComfyCleanupResult,
) -> ManagedComfyCleanupResult:
    """Record and return managed cleanup."""

    events.append("cleanup")
    return result


def _unexpected_cleanup(calls: list[str]) -> ManagedComfyCleanupResult:
    """Record an invalid cleanup attempt and fail the test."""

    calls.append("cleanup")
    raise AssertionError("cleanup must not run")


def _raise(error: Exception) -> NoReturn:
    """Raise one configured fixture error."""

    raise error


def _prepared() -> PreparedSessionSave:
    """Build one deterministic prepared save."""

    return PreparedSessionSave(
        snapshot=_snapshot(),
        prerequisites=(),
        reason="shutdown",
        sequence=1,
        suppressed=False,
    )


def _save_result() -> SessionSaveResult:
    """Build one deterministic save result."""

    return SessionSaveResult(
        reason="shutdown",
        elapsed_ms=1.0,
        prerequisite_count=0,
        workflow_count=0,
        persisted=True,
        sequence=1,
    )


def _snapshot() -> SessionSnapshot:
    """Build one deterministic snapshot."""

    return SessionSnapshot(
        schema_version=SESSION_SNAPSHOT_SCHEMA_VERSION,
        captured_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
        workspace=WorkspaceSnapshot(
            schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
            workflows=(),
            tab_order=(),
            active_route="",
            shell_layout=None,
        ),
    )
