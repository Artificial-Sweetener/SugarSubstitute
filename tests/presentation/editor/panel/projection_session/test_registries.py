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

"""Focused tests for projection session and completion registries."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

import substitute.presentation.editor.panel.projection_session as projection_session
from substitute.presentation.editor.panel.projection_session import (
    ActiveProjectionSession,
    ActiveProjectionSessionRegistry,
    PendingInsertCompletion,
    ProjectionCompletionRegistry,
)


def test_active_projection_session_registry_tracks_current_alias_ownership() -> None:
    """Active session ownership should be workflow and alias scoped."""

    registry = ActiveProjectionSessionRegistry()
    calls: list[str] = []

    session = registry.start(
        workflow_id="workflow-a",
        cube_entries=[("A", object()), ("B", object())],
        supersede_existing=lambda _old, _new, _reason: calls.append("supersede"),
        session_cleared=lambda _session, reason: calls.append(f"clear:{reason}"),
        discard_pending_visible_commit=lambda reason: calls.append(f"discard:{reason}"),
    )

    assert registry.active_session is session
    assert registry.is_current(session)
    assert registry.owns(workflow_id="workflow-a", cube_alias="A") is session
    assert registry.owns(workflow_id="workflow-b", cube_alias="A") is None
    assert registry.owns(workflow_id="workflow-a", cube_alias="C") is None
    assert calls == ["discard:superseded_by_new_full_projection"]

    assert registry.clear(session, reason="finished")
    assert registry.active_session is None
    assert not registry.is_current(session)
    assert registry.owns(workflow_id="workflow-a", cube_alias="A") is None


def test_active_projection_session_registry_supersedes_current_session() -> None:
    """Starting a replacement should resolve and clear only the prior active session."""

    registry = ActiveProjectionSessionRegistry()
    calls: list[str] = []

    first = registry.start(
        workflow_id="workflow-a",
        cube_entries=[("A", object())],
        supersede_existing=lambda _old, _new, _reason: calls.append("supersede"),
        session_cleared=lambda _session, reason: calls.append(f"clear:{reason}"),
        discard_pending_visible_commit=lambda reason: calls.append(f"discard:{reason}"),
    )

    def _supersede(
        old_session: object,
        new_session: object,
        reason: str,
    ) -> None:
        """Record replacement callback routing and transfer claimed callbacks."""

        calls.append(f"supersede:{reason}")
        new_claimed = cast(
            list[object],
            getattr(new_session, "claimed_completions"),
        )
        old_claimed = cast(
            list[object],
            getattr(old_session, "claimed_completions"),
        )
        new_claimed.extend(old_claimed)

    first.claimed_completions.append(
        PendingInsertCompletion(
            workflow_id="workflow-a",
            cube_alias="A",
            token=object(),
            completion_phase="complete",
            on_complete=lambda: None,
            reason="incremental_insert",
        )
    )
    second = registry.start(
        workflow_id="workflow-a",
        cube_entries=[("A", object())],
        supersede_existing=_supersede,
        session_cleared=lambda _session, reason: calls.append(f"clear:{reason}"),
        discard_pending_visible_commit=lambda reason: calls.append(f"discard:{reason}"),
    )

    assert first.resolved
    assert registry.active_session is second
    assert registry.is_current(second)
    assert second.claimed_completions == first.claimed_completions
    assert calls == [
        "discard:superseded_by_new_full_projection",
        "supersede:superseded_by_new_full_projection",
        "clear:superseded_by_new_full_projection",
        "discard:superseded_by_new_full_projection",
    ]


def test_active_projection_session_registry_resolve_and_cancel_are_once_only() -> None:
    """Resolve and cancel transitions should clear active ownership once."""

    registry = ActiveProjectionSessionRegistry()
    calls: list[str] = []
    session = registry.start(
        workflow_id="workflow-a",
        cube_entries=[("A", object())],
        supersede_existing=lambda _old, _new, _reason: calls.append("supersede"),
        session_cleared=lambda _session, reason: calls.append(f"clear:{reason}"),
        discard_pending_visible_commit=lambda reason: calls.append(f"discard:{reason}"),
    )

    assert registry.resolve(
        session,
        reason="projection_complete",
        resolve_session=lambda _session, reason: calls.append(f"resolve:{reason}"),
    )
    assert not registry.resolve(
        session,
        reason="projection_complete_again",
        resolve_session=lambda _session, reason: calls.append(f"resolve:{reason}"),
    )
    assert registry.active_session is None

    cancel_session = registry.start(
        workflow_id="workflow-a",
        cube_entries=[("B", object())],
        supersede_existing=lambda _old, _new, _reason: calls.append("supersede"),
        session_cleared=lambda _session, reason: calls.append(f"clear:{reason}"),
        discard_pending_visible_commit=lambda reason: calls.append(f"discard:{reason}"),
    )
    assert registry.cancel(
        cancel_session,
        reason="projection_cancelled",
        cancel_session=lambda _session, reason: calls.append(f"cancel:{reason}"),
    )
    assert not registry.cancel(
        cancel_session,
        reason="projection_cancelled_again",
        cancel_session=lambda _session, reason: calls.append(f"cancel:{reason}"),
    )
    assert registry.active_session is None
    assert calls == [
        "discard:superseded_by_new_full_projection",
        "resolve:projection_complete",
        "discard:superseded_by_new_full_projection",
        "cancel:projection_cancelled",
    ]


def test_projection_completion_registry_registers_and_forgets_pending_insert() -> None:
    """Pending insert completions should be owned by workflow, alias, and token."""

    registry = ProjectionCompletionRegistry()
    token = object()
    calls: list[str] = []

    registry.register_pending_insert(
        workflow_id="workflow-a",
        cube_alias="A",
        token=token,
        completion_phase="complete",
        on_complete=lambda: calls.append("complete"),
    )
    key = registry.pending_insert_key("workflow-a", "A")
    assert key in registry.pending_insert_completions

    registry.forget_pending_insert(
        workflow_id="workflow-a",
        cube_alias="A",
        token=object(),
        reason="wrong_token",
    )
    assert key in registry.pending_insert_completions

    registry.forget_pending_insert(
        workflow_id="workflow-a",
        cube_alias="A",
        token=token,
        reason="reported",
    )
    assert registry.pending_insert_completions == {}
    assert calls == []


def test_projection_completion_registry_same_alias_replacement_cancels_prior_insert() -> (
    None
):
    """New pending insert ownership should cancel an older same-alias token."""

    registry = ProjectionCompletionRegistry()
    first_token = object()
    second_token = object()
    calls: list[str] = []

    registry.register_pending_insert(
        workflow_id="workflow-a",
        cube_alias="A",
        token=first_token,
        completion_phase="complete",
        on_complete=lambda: calls.append("first"),
    )
    key = registry.pending_insert_key("workflow-a", "A")
    first_completion = registry.pending_insert_completions[key]

    registry.register_pending_insert(
        workflow_id="workflow-a",
        cube_alias="A",
        token=second_token,
        completion_phase="first_usable",
        on_complete=lambda: calls.append("second"),
    )

    assert first_completion.resolved
    assert calls == []
    second_completion = registry.pending_insert_completions[key]
    assert second_completion.token is second_token
    assert second_completion.completion_phase == "first_usable"


def test_projection_completion_registry_supersedes_only_node_definition_inserts() -> (
    None
):
    """Only node-definition invalidation should preserve pending insert callbacks."""

    registry = ProjectionCompletionRegistry()
    transferable_token = object()
    cancelled_token = object()

    registry.register_pending_insert(
        workflow_id="workflow-a",
        cube_alias="A",
        token=transferable_token,
        completion_phase="complete",
        on_complete=lambda: None,
    )
    assert registry.mark_pending_insert_superseded(
        workflow_id="workflow-a",
        cube_alias="A",
        token=transferable_token,
        reason="node_definition_changed",
    )
    transferable = registry.pending_insert_completions[
        registry.pending_insert_key("workflow-a", "A")
    ]
    assert transferable.superseded_reason == "node_definition_changed"

    registry.cancel_pending_insert(
        workflow_id="workflow-a",
        cube_alias="A",
        token=transferable_token,
        reason="scheduled_insert_cancelled",
        cancel_superseded=False,
    )
    assert registry.pending_insert_key("workflow-a", "A") in (
        registry.pending_insert_completions
    )

    registry.register_pending_insert(
        workflow_id="workflow-a",
        cube_alias="B",
        token=cancelled_token,
        completion_phase="complete",
        on_complete=lambda: None,
    )
    assert not registry.mark_pending_insert_superseded(
        workflow_id="workflow-a",
        cube_alias="B",
        token=cancelled_token,
        reason="cube_removed",
    )
    assert registry.pending_insert_key("workflow-a", "B") not in (
        registry.pending_insert_completions
    )


def test_projection_completion_registry_claims_and_attaches_insert_completions() -> (
    None
):
    """Insert completions should move from pending map to active session ownership."""

    registry = ProjectionCompletionRegistry()
    token = object()
    session = ActiveProjectionSession(
        workflow_id="workflow-a",
        aliases={"A", "B"},
        token=object(),
        claimed_completions=[],
        projection_completions=[],
    )

    registry.register_pending_insert(
        workflow_id="workflow-a",
        cube_alias="A",
        token=token,
        completion_phase="complete",
        on_complete=lambda: None,
    )
    assert (
        registry.claim_pending_insert_for_projection(
            workflow_id="workflow-a",
            cube_alias="A",
            token=object(),
            reason="stale_projection",
            projection_session=session,
        )
        is None
    )
    claimed = registry.claim_pending_insert_for_projection(
        workflow_id="workflow-a",
        cube_alias="A",
        token=token,
        reason="stale_projection",
        projection_session=session,
    )

    assert claimed is session.claimed_completions[0]
    assert claimed.superseded_reason == "stale_projection"
    assert registry.pending_insert_completions == {}

    registry.attach_insert_to_active_projection(
        session=session,
        workflow_id="workflow-a",
        cube_alias="B",
        completion_phase="first_usable",
        on_complete=lambda: None,
        reason="active_full_projection",
    )
    attached = session.claimed_completions[1]
    assert attached.token is session.token
    assert attached.superseded_reason == "active_full_projection"


def test_projection_completion_registry_transfers_and_resolves_session_callbacks() -> (
    None
):
    """Superseded projection callbacks should transfer only when identity matches."""

    registry = ProjectionCompletionRegistry()
    calls: list[str] = []
    old_session = ActiveProjectionSession(
        workflow_id="workflow-a",
        aliases={"A", "B"},
        token=object(),
        claimed_completions=[],
        projection_completions=[],
    )
    replacement_session = ActiveProjectionSession(
        workflow_id="workflow-a",
        aliases={"A"},
        token=object(),
        claimed_completions=[],
        projection_completions=[],
    )
    old_session.claimed_completions.extend(
        [
            PendingInsertCompletion(
                workflow_id="workflow-a",
                cube_alias="A",
                token=object(),
                completion_phase="complete",
                on_complete=lambda: calls.append("insert-a"),
                reason="active_full_projection",
            ),
            PendingInsertCompletion(
                workflow_id="workflow-a",
                cube_alias="B",
                token=object(),
                completion_phase="complete",
                on_complete=lambda: calls.append("insert-b"),
                reason="active_full_projection",
            ),
        ]
    )
    registry.register_projection_completion(
        old_session,
        workflow_id="workflow-a",
        aliases={"A"},
        on_complete=lambda: calls.append("projection-a"),
        reason="restore",
    )
    registry.register_projection_completion(
        old_session,
        workflow_id="workflow-a",
        aliases={"A", "B"},
        on_complete=lambda: calls.append("projection-ab"),
        reason="restore",
    )

    result = registry.transfer_from_superseded_session(
        old_session,
        replacement_session=replacement_session,
        reason="replacement",
    )
    registry.resolve_session(replacement_session, reason="complete")
    registry.resolve_session(replacement_session, reason="complete_again")

    assert result == projection_session.ProjectionCompletionTransferResult(
        transferred_insert_count=1,
        cancelled_insert_count=1,
        transferred_projection_count=1,
        cancelled_projection_count=1,
    )
    assert calls == ["insert-a", "projection-a"]
    assert old_session.claimed_completions[1].resolved
    assert old_session.projection_completions[1].resolved


def test_projection_session_registries_remain_qt_free() -> None:
    """Projection session registries must not import Qt or concrete panel widgets."""

    module_path = Path("substitute/presentation/editor/panel/projection_session.py")
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    forbidden_import_roots = {
        "PySide6",
        "qfluentwidgets",
        "qframelesswindow",
    }
    forbidden_import_parts = {
        "widgets",
        "node_card",
    }

    for node in ast.walk(tree):
        imported_name = ""
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_name = alias.name
                assert imported_name.split(".")[0] not in forbidden_import_roots
                assert not any(
                    part in imported_name.split(".") for part in forbidden_import_parts
                )
        elif isinstance(node, ast.ImportFrom):
            imported_name = node.module or ""
            assert imported_name.split(".")[0] not in forbidden_import_roots
            assert not any(
                part in imported_name.split(".") for part in forbidden_import_parts
            )


def test_projection_coordinator_no_longer_defines_pending_insert_wrappers() -> None:
    """Pending insert completion calls should go directly to the registry owner."""

    module_path = Path("substitute/presentation/editor/panel/projection_coordinator.py")
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    class_methods: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_methods[node.name] = {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }

    coordinator_methods = class_methods["EditorPanelProjectionCoordinator"]
    assert "_pending_insert_key" not in coordinator_methods
    assert "_register_pending_insert_completion" not in coordinator_methods
    assert "_forget_pending_insert_completion" not in coordinator_methods
    assert "_cancel_pending_insert_completion" not in coordinator_methods
    assert "_mark_pending_insert_completion_superseded" not in coordinator_methods
    assert "_attach_insert_completion_to_active_projection" not in coordinator_methods
    assert "_pending_insert_completions" not in coordinator_methods


def test_projection_coordinator_no_longer_defines_completion_registry_wrappers() -> (
    None
):
    """Completion registry operations should not reappear as coordinator wrappers."""

    module_path = Path("substitute/presentation/editor/panel/projection_coordinator.py")
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    class_methods: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_methods[node.name] = {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }

    coordinator_methods = class_methods["EditorPanelProjectionCoordinator"]
    removed_wrappers = {
        "_register_projection_completion",
        "_claim_pending_insert_completion_for_projection",
        "_claim_superseded_insert_completions",
        "_resolve_claimed_insert_completions",
        "_resolve_projection_completions",
        "_cancel_claimed_insert_completions",
        "_cancel_projection_completions",
    }
    assert coordinator_methods.isdisjoint(removed_wrappers)
