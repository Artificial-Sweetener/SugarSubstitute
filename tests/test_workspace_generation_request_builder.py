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

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    LiveNodeDefinitionError,
    MissingLiveNodeDefinition,
)
from substitute.application.workflows import CubeRuntimeIssueSource
from substitute.domain.node_behavior import NodeDisplayDecision
from substitute.domain.recipes.sugar_ast import GlobalOverrideSerializationScope
from substitute.presentation.shell.workspace_generation_request_builder import (
    GenerationWorkflowPruneReport,
    activation_node_keys_by_alias,
    active_behavior_snapshot,
    active_global_override_scopes,
    build_generation_request_for_view,
    editor_panel_for_workflow,
    errored_cube_aliases,
    generation_request_from_workflow_state,
    node_payload_has_authored_bypass,
    preflight_live_node_definitions,
    pruned_workflow_for_generation,
    workflow_issue_pruning_service,
    workflow_buffer_nodes_for_alias,
    workflow_stack_order,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_generation_request_builder.py"
)
WORKSPACE_CONTROLLER_SOURCE = (
    PROJECT_ROOT / "substitute" / "presentation" / "shell" / "workspace_controller.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.shell.workspace_controller",
    "substitute.presentation.shell.workspace_generation_controller",
)


def _imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_activation_node_keys_follow_authored_defaults() -> None:
    """Generation activation lists should be deltas from authored defaults."""

    workflow = SimpleNamespace(
        cubes={
            "A": SimpleNamespace(
                buffer={
                    "nodes": {
                        "revealed_enabled_bypass": {"mode": 4},
                        "revealed_disabled_bypass": {"mode": 4},
                        "normal_disabled": {},
                    }
                }
            )
        }
    )
    behavior_snapshot = EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={},
        card_decisions_by_alias={
            "A": {
                "revealed_enabled_bypass": NodeDisplayDecision(
                    visible=True,
                    enabled=True,
                    reason="explicit:enabled",
                ),
                "revealed_disabled_bypass": NodeDisplayDecision(
                    visible=True,
                    enabled=False,
                    reason="explicit:revealed",
                ),
                "normal_disabled": NodeDisplayDecision(
                    visible=True,
                    enabled=False,
                    reason="explicit:disabled",
                ),
            }
        },
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )

    enabled, disabled = activation_node_keys_by_alias(behavior_snapshot, workflow)

    assert enabled == {"A": ("revealed_enabled_bypass",)}
    assert disabled == {"A": ("normal_disabled",)}


def test_activation_node_keys_keep_hidden_active_schedule_node_enabled() -> None:
    """Hidden active infrastructure nodes should not serialize disable overrides."""

    workflow = SimpleNamespace(
        cubes={
            "A": SimpleNamespace(
                buffer={
                    "nodes": {
                        "schedule_encode_prompts": {
                            "class_type": (
                                "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl"
                            ),
                            "inputs": {},
                        },
                    }
                }
            )
        }
    )
    behavior_snapshot = EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={},
        card_decisions_by_alias={
            "A": {
                "schedule_encode_prompts": NodeDisplayDecision(
                    visible=False,
                    enabled=True,
                    reason="policy:override-hide",
                    revealable=False,
                ),
            }
        },
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )

    enabled, disabled = activation_node_keys_by_alias(behavior_snapshot, workflow)

    assert enabled == {}
    assert disabled == {}


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


def test_build_generation_request_for_view_flushes_then_reconciles() -> None:
    """Request orchestration should flush dirty masks before canvas reconciliation."""

    order: list[str] = []
    workflow = SimpleNamespace(cubes={}, stack_order=[])

    def flush_dirty_masks() -> bool:
        """Record mask flush ordering and report success."""

        order.append("flush")
        return True

    view = SimpleNamespace(
        input_mask_save_controller=SimpleNamespace(
            flush_dirty_associated_masks_before_generation=flush_dirty_masks
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
        dirty_mask_error=lambda: AssertionError("unexpected dirty mask failure"),
        live_node_preflight_error=lambda error: AssertionError(error),
        empty_workflow_error=lambda: AssertionError("unexpected empty workflow"),
    )

    assert order == ["flush", "reconcile"]
    assert request.workflow_id == "wf-a"
    assert request.workflow_name == "Recipe"
    assert request.workflow is workflow


def test_build_generation_request_for_view_blocks_dirty_mask_failure() -> None:
    """Dirty mask persistence failure should stop request construction."""

    expected_error = RuntimeError("dirty mask failed")
    reconciled: list[str] = []
    view = SimpleNamespace(
        input_mask_save_controller=SimpleNamespace(
            flush_dirty_associated_masks_before_generation=lambda: False
        ),
    )

    try:
        build_generation_request_for_view(
            view=view,
            workflow_id="wf-a",
            reconcile_active_input_canvas_image=lambda: reconciled.append("called"),
            dirty_mask_error=lambda: expected_error,
            live_node_preflight_error=lambda error: AssertionError(error),
            empty_workflow_error=lambda: AssertionError("unexpected empty workflow"),
        )
    except RuntimeError as error:
        assert error is expected_error
    else:
        raise AssertionError("expected dirty mask preflight error")

    assert reconciled == []


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
        input_mask_save_controller=SimpleNamespace(
            flush_dirty_associated_masks_before_generation=lambda: True
        ),
        editor_panels={"wf-a": _Panel()},
        active_editor_panel=None,
    )

    try:
        build_generation_request_for_view(
            view=view,
            workflow_id="wf-a",
            reconcile_active_input_canvas_image=lambda: reconciled.append("called"),
            dirty_mask_error=lambda: AssertionError("unexpected dirty mask failure"),
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
        input_mask_save_controller=SimpleNamespace(
            flush_dirty_associated_masks_before_generation=lambda: True
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
        dirty_mask_error=lambda: AssertionError("unexpected dirty mask failure"),
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


def test_pruned_workflow_for_generation_omits_errored_cubes() -> None:
    """Workflow pruning should omit errored cubes and report safe diagnostics."""

    workflow = SimpleNamespace(
        stack_order=["A", "Errored"],
        cubes={"A": object(), "Errored": object()},
    )
    reports: list[GenerationWorkflowPruneReport] = []

    pruned = pruned_workflow_for_generation(
        view=SimpleNamespace(node_behavior_service=None),
        workflow=workflow,
        workflow_id="wf-a",
        workflow_name="Recipe",
        errored_aliases=("Errored",),
        empty_workflow_error=lambda: AssertionError("unexpected empty workflow"),
        omission_logger=reports.append,
    )
    pruned_workflow = cast(Any, pruned)

    assert pruned is not workflow
    assert pruned_workflow.stack_order == ["A"]
    assert tuple(pruned_workflow.cubes) == ("A",)
    assert reports == [
        GenerationWorkflowPruneReport(
            workflow_id="wf-a",
            workflow_name="Recipe",
            omitted_cube_aliases=("Errored",),
            remaining_cube_count=1,
        )
    ]


def test_pruned_workflow_for_generation_fails_when_all_cubes_errored() -> None:
    """Workflow pruning should fail closed when no generation cubes remain."""

    workflow = SimpleNamespace(
        stack_order=["Errored"],
        cubes={"Errored": object()},
    )
    expected_error = RuntimeError("empty")

    try:
        pruned_workflow_for_generation(
            view=SimpleNamespace(node_behavior_service=None),
            workflow=workflow,
            workflow_id="wf-a",
            workflow_name="Recipe",
            errored_aliases=("Errored",),
            empty_workflow_error=lambda: expected_error,
        )
    except RuntimeError as error:
        assert error is expected_error
    else:
        raise AssertionError("expected empty workflow error")


def test_workflow_stack_order_returns_tuple() -> None:
    """Workflow stack-order lookup should normalize missing and list values."""

    assert workflow_stack_order(SimpleNamespace(stack_order=["A", "B"])) == ("A", "B")
    assert workflow_stack_order(SimpleNamespace()) == ()


def test_preflight_live_node_definitions_registers_cube_issue() -> None:
    """Cube-attributed live metadata failures should be registered as recoverable."""

    register_calls: list[
        tuple[LiveNodeDefinitionError, str, CubeRuntimeIssueSource]
    ] = []

    class _Panel:
        """Raise and register a cube-attributed live metadata error."""

        def hydrate_node_definitions_for_projection(self, *, reason: str) -> None:
            """Raise a cube-attributed metadata failure from generation preflight."""

            assert reason == "generation_preflight"
            raise LiveNodeDefinitionError(
                operation="hydrate generation node definitions",
                missing_definitions=(
                    MissingLiveNodeDefinition(
                        class_type="SimpleSyrup.Detailer",
                        cube_aliases=("CubeA",),
                        node_names=("detailer",),
                    ),
                ),
            )

        def register_projection_live_node_definition_error(
            self,
            error: LiveNodeDefinitionError,
            *,
            reason: str,
            source: CubeRuntimeIssueSource,
        ) -> bool:
            """Record the recoverable issue registration request."""

            register_calls.append((error, reason, source))
            return True

    preflight_live_node_definitions(
        view=SimpleNamespace(
            editor_panels={"wf-a": _Panel()},
            active_editor_panel=None,
        ),
        workflow_id="wf-a",
        preflight_error=lambda error: AssertionError(error),
    )

    assert len(register_calls) == 1
    _error, reason, source = register_calls[0]
    assert reason == "generation_preflight"
    assert source == CubeRuntimeIssueSource.PROJECTION


def test_preflight_live_node_definitions_raises_preflight_error() -> None:
    """Unowned live metadata failures should fail generation preflight."""

    class _Panel:
        """Raise an unowned live metadata error."""

        def hydrate_node_definitions_for_projection(self, *, reason: str) -> None:
            """Raise a metadata failure from generation preflight."""

            assert reason == "generation_preflight"
            raise LiveNodeDefinitionError(
                operation="hydrate generation node definitions",
                missing_definitions=(
                    MissingLiveNodeDefinition(class_type="SimpleSyrup.Detailer"),
                ),
            )

    expected_error = RuntimeError("preflight failed")

    try:
        preflight_live_node_definitions(
            view=SimpleNamespace(
                editor_panels={"wf-a": _Panel()},
                active_editor_panel=None,
            ),
            workflow_id="wf-a",
            preflight_error=lambda _error: expected_error,
        )
    except RuntimeError as error:
        assert error is expected_error
        assert isinstance(error.__cause__, LiveNodeDefinitionError)
    else:
        raise AssertionError("expected preflight error")


def test_preflight_live_node_definitions_logs_missing_panel() -> None:
    """Missing editor panels should skip preflight through the provided logger."""

    logged: list[str] = []

    preflight_live_node_definitions(
        view=SimpleNamespace(editor_panels={}, active_editor_panel=object()),
        workflow_id="wf-a",
        preflight_error=lambda error: AssertionError(error),
        missing_panel_logger=logged.append,
    )

    assert logged == ["wf-a"]


def test_workspace_generation_request_builder_imports_no_concrete_boundaries() -> None:
    """Request builder helpers should not import Qt or concrete controllers."""

    forbidden_imports = tuple(
        sorted(
            imported_module
            for imported_module in _imported_module_names(SOURCE_PATH)
            if imported_module.startswith(FORBIDDEN_IMPORT_PREFIXES)
        )
    )

    assert forbidden_imports == ()


def test_workspace_controller_no_longer_owns_activation_delta_helpers() -> None:
    """Workspace controller should delegate request-building helper policy."""

    source = WORKSPACE_CONTROLLER_SOURCE.read_text(encoding="utf-8")

    assert "def _activation_node_keys_by_alias(" not in source
    assert "def _workflow_buffer_nodes_for_alias(" not in source
    assert "def _node_payload_has_authored_bypass(" not in source
    assert "def _active_behavior_snapshot(" not in source
    assert "def _editor_panel_for_workflow(" not in source
    assert "def _active_global_override_scopes(" not in source
    assert "def _errored_cube_aliases(" not in source
    assert "def _workflow_issue_pruning_service(" not in source
    assert "def _pruned_workflow_for_generation(" not in source
    assert "def _preflight_live_node_definitions(" not in source
    assert "def _build_generation_request_profiled(" not in source
