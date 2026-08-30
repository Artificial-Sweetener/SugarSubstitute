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
from typing import Any, cast

from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    LiveNodeDefinitionError,
    MissingLiveNodeDefinition,
)
from substitute.domain.node_behavior import NodeDisplayDecision
from substitute.domain.recipes.sugar_ast import GlobalOverrideSerializationScope
from substitute.application.generation.input_generation_errors import (
    InputGenerationPreparationError,
    InputGenerationPreparationFailureKind,
)
from substitute.presentation.shell.workspace_generation_request_builder import (
    GenerationWorkflowPruneReport,
    build_generation_request_for_view,
    generation_request_from_workflow_state,
)


PROJECT_ROOT = Path(__file__).resolve().parents[5]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_generation_request_builder.py"
)


def test_generation_request_from_workflow_state_builds_pruned_request() -> None:
    """Request assembly should prune activation and override state."""

    retained_scope = GlobalOverrideSerializationScope(
        override_key="sampler",
        value="euler",
        mode="partial",
        full_participation=False,
        participant_fields=frozenset(
            {
                ("A", "sampler", "sampler_name"),
                ("Errored", "sampler", "sampler_name"),
            }
        ),
    )
    removed_scope = GlobalOverrideSerializationScope(
        override_key="cfg",
        value=7,
        mode="partial",
        full_participation=False,
        participant_fields=frozenset({("Errored", "sampler", "cfg")}),
    )
    workflow = SimpleNamespace(
        cubes={
            "A": SimpleNamespace(
                buffer={
                    "nodes": {
                        "enabled_from_bypass": {"mode": 4},
                        "disabled_from_default": {},
                    }
                }
            ),
            "Errored": SimpleNamespace(
                buffer={"nodes": {"disabled_errored": {}}},
            ),
        }
    )
    behavior_snapshot = EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={},
        card_decisions_by_alias={
            "A": {
                "enabled_from_bypass": NodeDisplayDecision(
                    visible=True,
                    enabled=True,
                    reason="explicit:enabled",
                ),
                "disabled_from_default": NodeDisplayDecision(
                    visible=False,
                    enabled=False,
                    reason="explicit:disabled",
                ),
            },
            "Errored": {
                "disabled_errored": NodeDisplayDecision(
                    visible=False,
                    enabled=False,
                    reason="explicit:disabled",
                ),
            },
        },
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )
    view = SimpleNamespace(
        node_behavior_service=None,
        active_override_manager=SimpleNamespace(
            current_serialization_scopes=lambda: {
                "sampler": retained_scope,
                "cfg": removed_scope,
            }
        ),
    )

    request = generation_request_from_workflow_state(
        view=view,
        workflow_id="wf-a",
        workflow_name="Recipe",
        workflow=workflow,
        behavior_snapshot=behavior_snapshot,
        errored_aliases=("Errored",),
    )

    assert request.workflow_id == "wf-a"
    assert request.workflow_name == "Recipe"
    assert request.workflow is workflow
    assert request.enabled_node_keys_by_alias == {"A": ("enabled_from_bypass",)}
    assert request.disabled_node_keys_by_alias == {"A": ("disabled_from_default",)}
    assert request.global_override_scopes is not None
    assert tuple(request.global_override_scopes) == ("sampler",)
    assert request.global_override_scopes["sampler"].participant_fields == frozenset(
        {("A", "sampler", "sampler_name")}
    )


def test_build_generation_request_captures_after_canvas_reconciliation() -> None:
    """Request orchestration should bind an exact mask copy after reconciliation."""

    order: list[str] = []
    workflow = SimpleNamespace(cubes={}, stack_order=[])

    def prepare_workflow(*, workflow_id: str, workflow: object) -> object:
        """Record exact snapshot ordering and return the execution copy."""
        assert workflow_id == "wf-a"
        order.append("capture")
        return workflow

    view = SimpleNamespace(
        input_generation_snapshot_service=SimpleNamespace(
            prepare_workflow=prepare_workflow
        ),
        editor_panels={},
        active_editor_panel=object(),
        get_active_workflow=lambda: workflow,
        workflow_issue_state=SimpleNamespace(errored_aliases=lambda _workflow_id: ()),
        input_canvas_shell_adapter=SimpleNamespace(
            resolve_workflow_name=lambda _workflow_id: "Recipe"
        ),
        active_override_manager=None,
        node_behavior_service=None,
    )

    request = build_generation_request_for_view(
        view=view,
        workflow_id="wf-a",
        reconcile_active_input_canvas_image=lambda: order.append("reconcile"),
        input_snapshot_error=lambda: AssertionError(
            "unexpected Input snapshot failure"
        ),
        live_node_preflight_error=lambda error: AssertionError(error),
        empty_workflow_error=lambda: AssertionError("unexpected empty workflow"),
    )

    assert order == ["reconcile", "capture"]
    assert request.workflow_id == "wf-a"
    assert request.workflow_name == "Recipe"
    assert request.workflow is workflow


def test_build_generation_request_for_view_blocks_input_snapshot_failure() -> None:
    """An incoherent Input snapshot should stop request construction."""

    expected_error = RuntimeError("Input snapshot failed")
    reconciled: list[str] = []
    workflow = SimpleNamespace(cubes={}, stack_order=[])
    view = SimpleNamespace(
        input_generation_snapshot_service=SimpleNamespace(
            prepare_workflow=lambda **_kwargs: None
        ),
        editor_panels={},
        active_editor_panel=None,
        get_active_workflow=lambda: workflow,
    )

    try:
        build_generation_request_for_view(
            view=view,
            workflow_id="wf-a",
            reconcile_active_input_canvas_image=lambda: reconciled.append("called"),
            input_snapshot_error=lambda: expected_error,
            live_node_preflight_error=lambda error: AssertionError(error),
            empty_workflow_error=lambda: AssertionError("unexpected empty workflow"),
        )
    except RuntimeError as error:
        assert error is expected_error
    else:
        raise AssertionError("expected Input snapshot preflight error")

    assert reconciled == ["called"]


def test_build_generation_request_preserves_typed_input_failure_as_cause() -> None:
    """Shell preflight should retain the exact failed Input preparation boundary."""

    preparation_error = InputGenerationPreparationError(
        InputGenerationPreparationFailureKind.IMAGE_MATERIALIZATION
    )
    expected_error = RuntimeError("Input preparation failed")

    def prepare_workflow(**_kwargs: object) -> object:
        """Raise the typed failure produced by Input preparation."""

        raise preparation_error

    view = SimpleNamespace(
        input_generation_snapshot_service=SimpleNamespace(
            prepare_workflow=prepare_workflow
        ),
        editor_panels={},
        active_editor_panel=None,
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
    )

    try:
        build_generation_request_for_view(
            view=view,
            workflow_id="wf-a",
            reconcile_active_input_canvas_image=lambda: None,
            input_snapshot_error=lambda: expected_error,
            live_node_preflight_error=lambda error: AssertionError(error),
            empty_workflow_error=lambda: AssertionError("unexpected empty workflow"),
        )
    except RuntimeError as error:
        assert error is expected_error
        assert error.__cause__ is preparation_error
    else:
        raise AssertionError("expected Input preparation preflight error")


def test_build_generation_request_for_view_blocks_live_node_preflight_failure() -> None:
    """Live node-definition failures should stop before canvas reconciliation."""

    expected_error = RuntimeError("live node failed")
    reconciled: list[str] = []

    class _Panel:
        """Raise an unowned live metadata error from generation preflight."""

        def hydrate_node_definitions_for_projection(self, *, reason: str) -> None:
            """Raise the metadata failure."""

            assert reason == "generation_preflight"
            raise LiveNodeDefinitionError(
                operation="hydrate generation node definitions",
                missing_definitions=(
                    MissingLiveNodeDefinition(class_type="SimpleSyrup.Detailer"),
                ),
            )

    view = SimpleNamespace(
        input_generation_snapshot_service=SimpleNamespace(
            prepare_workflow=lambda **kwargs: kwargs["workflow"]
        ),
        editor_panels={"wf-a": _Panel()},
        active_editor_panel=None,
    )

    try:
        build_generation_request_for_view(
            view=view,
            workflow_id="wf-a",
            reconcile_active_input_canvas_image=lambda: reconciled.append("called"),
            input_snapshot_error=lambda: AssertionError(
                "unexpected Input snapshot failure"
            ),
            live_node_preflight_error=lambda _error: expected_error,
            empty_workflow_error=lambda: AssertionError("unexpected empty workflow"),
        )
    except RuntimeError as error:
        assert error is expected_error
        assert isinstance(error.__cause__, LiveNodeDefinitionError)
    else:
        raise AssertionError("expected live node preflight error")

    assert reconciled == []


def test_build_generation_request_for_view_prunes_errored_workflow() -> None:
    """Request orchestration should prune errored cubes before request assembly."""

    workflow = SimpleNamespace(
        stack_order=["A", "Errored"],
        cubes={"A": SimpleNamespace(buffer={"nodes": {}}), "Errored": object()},
    )
    reports: list[GenerationWorkflowPruneReport] = []
    view = SimpleNamespace(
        input_generation_snapshot_service=SimpleNamespace(
            prepare_workflow=lambda **kwargs: kwargs["workflow"]
        ),
        editor_panels={},
        active_editor_panel=object(),
        get_active_workflow=lambda: workflow,
        workflow_issue_state=SimpleNamespace(
            errored_aliases=lambda _workflow_id: ("Errored",)
        ),
        input_canvas_shell_adapter=SimpleNamespace(
            resolve_workflow_name=lambda _workflow_id: "Recipe"
        ),
        active_override_manager=None,
        node_behavior_service=None,
    )

    request = build_generation_request_for_view(
        view=view,
        workflow_id="wf-a",
        reconcile_active_input_canvas_image=lambda: None,
        input_snapshot_error=lambda: AssertionError(
            "unexpected Input snapshot failure"
        ),
        live_node_preflight_error=lambda error: AssertionError(error),
        empty_workflow_error=lambda: AssertionError("unexpected empty workflow"),
        omission_logger=reports.append,
    )

    assert request.workflow is not workflow
    assert cast(Any, request.workflow).stack_order == ["A"]
    assert reports == [
        GenerationWorkflowPruneReport(
            workflow_id="wf-a",
            workflow_name="Recipe",
            omitted_cube_aliases=("Errored",),
            remaining_cube_count=1,
        )
    ]
