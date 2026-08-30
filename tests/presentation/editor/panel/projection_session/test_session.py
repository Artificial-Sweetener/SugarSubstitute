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

"""Tests for extracted editor panel projection session ownership."""

from __future__ import annotations

from substitute.presentation.editor.panel.projection_session import (
    ActiveProjectionSession,
    ActiveProjectionSessionRegistry,
    PendingInsertCompletion,
    PendingProjectionCompletion,
    ProjectionCompletionRegistry,
)


def test_active_projection_registry_rejects_stale_session_after_cancel() -> None:
    """Cancelling an active session must make later freshness checks fail."""

    registry = ActiveProjectionSessionRegistry()
    cleared: list[str] = []
    session = registry.start(
        workflow_id="workflow",
        cube_entries=[("Cube", object())],
        supersede_existing=lambda *_args: None,
        session_cleared=lambda _session, reason: cleared.append(reason),
        discard_pending_visible_commit=lambda _reason: None,
    )
    cancelled: list[str] = []

    assert registry.is_current(session)

    assert registry.cancel(
        session,
        reason="test_cancel",
        cancel_session=lambda _session, reason: cancelled.append(reason),
    )

    assert not registry.is_current(session)
    assert registry.active_session is None
    assert cancelled == ["test_cancel"]


def test_completion_registry_transfers_matching_superseded_callbacks() -> None:
    """Superseded sessions transfer matching callbacks and cancel stale ones."""

    registry = ProjectionCompletionRegistry()
    transferred_insert = PendingInsertCompletion(
        workflow_id="workflow",
        cube_alias="Keep",
        token=object(),
        completion_phase="complete",
        on_complete=lambda: None,
        reason="old",
    )
    cancelled_insert = PendingInsertCompletion(
        workflow_id="workflow",
        cube_alias="Drop",
        token=object(),
        completion_phase="complete",
        on_complete=lambda: None,
        reason="old",
    )
    transferred_projection = PendingProjectionCompletion(
        workflow_id="workflow",
        aliases=frozenset({"Keep"}),
        on_complete=lambda: None,
        reason="old",
    )
    cancelled_projection = PendingProjectionCompletion(
        workflow_id="workflow",
        aliases=frozenset({"Drop"}),
        on_complete=lambda: None,
        reason="old",
    )
    old_session = ActiveProjectionSession(
        workflow_id="workflow",
        aliases={"Keep", "Drop"},
        token=object(),
        claimed_completions=[transferred_insert, cancelled_insert],
        projection_completions=[transferred_projection, cancelled_projection],
    )
    replacement_session = ActiveProjectionSession(
        workflow_id="workflow",
        aliases={"Keep"},
        token=object(),
        claimed_completions=[],
        projection_completions=[],
    )

    result = registry.transfer_from_superseded_session(
        old_session,
        replacement_session=replacement_session,
        reason="superseded",
    )

    assert result.transferred_insert_count == 1
    assert result.cancelled_insert_count == 1
    assert result.transferred_projection_count == 1
    assert result.cancelled_projection_count == 1
    assert replacement_session.claimed_completions == [transferred_insert]
    assert replacement_session.projection_completions == [transferred_projection]
    assert not transferred_insert.resolved
    assert cancelled_insert.resolved
    assert not transferred_projection.resolved
    assert cancelled_projection.resolved


def test_completion_registry_resolves_callbacks_once() -> None:
    """Resolved callbacks must not run more than once."""

    registry = ProjectionCompletionRegistry()
    calls: list[str] = []
    completion = PendingInsertCompletion(
        workflow_id="workflow",
        cube_alias="Cube",
        token=object(),
        completion_phase="first_usable",
        on_complete=lambda: calls.append("insert"),
        reason="test",
    )

    registry.resolve_insert_completions((completion,), reason="first")
    registry.resolve_insert_completions((completion,), reason="second")

    assert calls == ["insert"]
