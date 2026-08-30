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

"""Tests for shell generation request-building policy helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from substitute.presentation.shell.workspace_generation_request_builder import (
    active_behavior_snapshot,
    active_global_override_scopes,
    editor_panel_for_workflow,
    errored_cube_aliases,
    node_payload_has_authored_bypass,
    workflow_issue_pruning_service,
    workflow_buffer_nodes_for_alias,
)


PROJECT_ROOT = Path(__file__).resolve().parents[5]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_generation_request_builder.py"
)


def test_workflow_buffer_nodes_for_alias_returns_serialized_nodes() -> None:
    """Node lookup should return the serialized node mapping for one cube alias."""

    nodes = {"node-a": {"mode": 4}}
    workflow = SimpleNamespace(cubes={"A": SimpleNamespace(buffer={"nodes": nodes})})

    assert workflow_buffer_nodes_for_alias(workflow, "A") is nodes
    assert workflow_buffer_nodes_for_alias(workflow, "missing") == {}


def test_node_payload_has_authored_bypass_accepts_only_integer_mode_four() -> None:
    """Authored bypass detection should reject bools and non-mapping payloads."""

    assert node_payload_has_authored_bypass({"mode": 4})
    assert not node_payload_has_authored_bypass({"mode": True})
    assert not node_payload_has_authored_bypass({"mode": "4"})
    assert not node_payload_has_authored_bypass(None)


def test_editor_panel_for_workflow_prefers_workflow_panel() -> None:
    """Editor panel lookup should prefer the workflow-specific panel."""

    workflow_panel = object()
    active_panel = object()
    view = SimpleNamespace(
        editor_panels={"wf-a": workflow_panel},
        active_editor_panel=active_panel,
    )

    assert editor_panel_for_workflow(view, "wf-a") is workflow_panel
    assert editor_panel_for_workflow(view, "missing") is active_panel


def test_active_behavior_snapshot_reads_workflow_panel_snapshot() -> None:
    """Behavior snapshot lookup should call the selected panel snapshot getter."""

    snapshot = object()
    workflow_panel = SimpleNamespace(current_behavior_snapshot=lambda: snapshot)
    view = SimpleNamespace(
        editor_panels={"wf-a": workflow_panel},
        active_editor_panel=SimpleNamespace(current_behavior_snapshot=lambda: object()),
    )

    assert active_behavior_snapshot(view, "wf-a") is snapshot


def test_active_behavior_snapshot_returns_none_without_snapshot_getter() -> None:
    """Behavior snapshot lookup should tolerate panels without snapshot access."""

    view = SimpleNamespace(editor_panels={}, active_editor_panel=object())

    assert active_behavior_snapshot(view, "wf-a") is None


def test_active_global_override_scopes_reads_manager_scopes() -> None:
    """Override scope lookup should return mapping scopes from the active manager."""

    scopes = {"global": object()}
    view = SimpleNamespace(
        active_override_manager=SimpleNamespace(
            current_serialization_scopes=lambda: scopes
        )
    )

    assert active_global_override_scopes(view) is scopes


def test_active_global_override_scopes_logs_legacy_reasons() -> None:
    """Override scope lookup should report legacy fallback reasons."""

    reasons: list[str] = []
    view_without_manager = SimpleNamespace(active_override_manager=None)
    view_without_getter = SimpleNamespace(active_override_manager=object())

    assert (
        active_global_override_scopes(
            view_without_manager,
            legacy_scope_logger=reasons.append,
        )
        is None
    )
    assert (
        active_global_override_scopes(
            view_without_getter,
            legacy_scope_logger=reasons.append,
        )
        is None
    )
    assert reasons == ["missing_active_override_manager", "missing_scope_getter"]


def test_errored_cube_aliases_prefers_workflow_issue_state() -> None:
    """Errored alias lookup should prefer the workflow issue state owner."""

    view = SimpleNamespace(
        workflow_issue_state=SimpleNamespace(
            errored_aliases=lambda workflow_id: (
                ("IssueStateCube",) if workflow_id == "wf-a" else ()
            )
        ),
        editor_panels={
            "wf-a": SimpleNamespace(cube_runtime_error_aliases=lambda: ("PanelCube",))
        },
        active_editor_panel=None,
    )

    assert errored_cube_aliases(view, "wf-a") == ("IssueStateCube",)


def test_errored_cube_aliases_falls_back_to_editor_panel() -> None:
    """Errored alias lookup should fall back to the selected editor panel."""

    view = SimpleNamespace(
        workflow_issue_state=object(),
        editor_panels={
            "wf-a": SimpleNamespace(cube_runtime_error_aliases=lambda: ("PanelCube",))
        },
        active_editor_panel=None,
    )

    assert errored_cube_aliases(view, "wf-a") == ("PanelCube",)


def test_errored_cube_aliases_returns_empty_without_owner() -> None:
    """Errored alias lookup should tolerate missing issue owners."""

    view = SimpleNamespace(
        workflow_issue_state=object(),
        editor_panels={},
        active_editor_panel=object(),
    )

    assert errored_cube_aliases(view, "wf-a") == ()


def test_workflow_issue_pruning_service_builds_from_node_behavior_service() -> None:
    """Pruning service factory should use shell-owned node behavior ports."""

    view = SimpleNamespace(node_behavior_service=object())
    service = workflow_issue_pruning_service(view)

    assert service is not None
