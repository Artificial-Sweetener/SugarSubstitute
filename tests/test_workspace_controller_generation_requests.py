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

"""Tests for WorkspaceController generation request facade behavior."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    LiveNodeDefinitionError,
    MissingLiveNodeDefinition,
)
from substitute.domain.node_behavior import NodeDisplayDecision
from tests.workspace_controller_test_support import import_workspace_controller_module


def _base_generation_view(
    *,
    workflow: object,
    active_panel: object | None = None,
    editor_panels: dict[str, object] | None = None,
) -> SimpleNamespace:
    """Build the minimal shell view needed by generation request tests."""

    return SimpleNamespace(
        request_reconfigure=lambda: None,
        request_settings=lambda: None,
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        workspace_generation_controller=SimpleNamespace(
            handle_generate_clicked=lambda **_kwargs: None,
            interrupt_generation=lambda: SimpleNamespace(status="sent"),
        ),
        _current_generate_mode="generate",
        get_active_workflow=lambda: workflow,
        input_canvas_shell_adapter=SimpleNamespace(
            resolve_workflow_name=lambda _workflow_id: "Recipe"
        ),
        _randomize_active_seed_boxes=lambda: None,
        _clear_output_for_workflow=lambda _workflow_id: None,
        _on_generation_progress=lambda _progress: None,
        _on_generation_preview=lambda _preview: None,
        _on_generation_output_image=lambda _output: None,
        _on_generation_failure=lambda _failure: None,
        _log_interrupt_failure=lambda _result: None,
        canvas_tabs=SimpleNamespace(canvas_map={}),
        canvas_io_service=SimpleNamespace(),
        workflow_input_canvas_service=SimpleNamespace(),
        workflow_asset_service=SimpleNamespace(),
        add_output_image_signal=SimpleNamespace(emit=lambda *_args: None),
        path_bundle=SimpleNamespace(projects_dir=".", cubes_dir="."),
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0, tabText=lambda _idx: ""
        ),
        active_editor_panel=active_panel,
        cube_stacks={},
        editor_panels=editor_panels or {},
        cube_load_service=SimpleNamespace(),
        cube_stack_service=SimpleNamespace(),
        active_override_manager=None,
        recipe_io_service=SimpleNamespace(),
        workflow_export_service=SimpleNamespace(),
        _pending_cubes={},
        active_cube_stack=None,
    )


def _install_dirty_mask_preflight(view: SimpleNamespace, result: bool) -> None:
    """Install a deterministic dirty-mask preflight result on a view."""

    view.input_mask_save_controller = SimpleNamespace(
        flush_dirty_associated_masks_before_generation=lambda: result,
    )


def _install_input_canvas_reconciliation(
    view: SimpleNamespace,
    callback: Any | None = None,
) -> None:
    """Install active Input canvas reconciliation on a view."""

    view.input_canvas_presenter = SimpleNamespace(
        reconcile_active_input_canvas_image=callback or (lambda: None),
    )


def test_build_generation_request_flushes_dirty_masks_before_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generation request construction should preflight dirty masks first."""

    mod = import_workspace_controller_module(monkeypatch)
    order: list[str] = []
    workflow = object()
    view = _base_generation_view(workflow=workflow)
    controller = mod.WorkspaceController(view)

    def _flush_dirty_masks() -> bool:
        """Record dirty-mask preflight."""

        order.append("flush")
        return True

    view.input_mask_save_controller = SimpleNamespace(
        flush_dirty_associated_masks_before_generation=_flush_dirty_masks,
    )
    _install_input_canvas_reconciliation(view, lambda: order.append("reconcile"))

    request = controller.build_generation_request()

    assert order == ["flush", "reconcile"]
    assert request.workflow is workflow


def test_build_generation_request_blocks_when_live_definition_preflight_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generation should stop when live node-definition hydration fails."""

    mod = import_workspace_controller_module(monkeypatch)
    workflow = object()

    class _Panel:
        """Raise the live metadata error from the generation preflight path."""

        def hydrate_node_definitions_for_projection(self, *, reason: str) -> None:
            """Record the generation reason and raise the metadata failure."""

            assert reason == "generation_preflight"
            raise LiveNodeDefinitionError(
                operation="hydrate generation node definitions",
                missing_definitions=(
                    MissingLiveNodeDefinition(class_type="SimpleSyrup.Detailer"),
                ),
            )

    panel = _Panel()
    view = _base_generation_view(
        workflow=workflow,
        active_panel=panel,
        editor_panels={"wf-a": panel},
    )
    controller = mod.WorkspaceController(view)
    _install_dirty_mask_preflight(view, True)
    _install_input_canvas_reconciliation(
        view,
        lambda: pytest.fail("generation continued after metadata preflight failure"),
    )

    with pytest.raises(mod.GenerationPreflightError) as error_info:
        controller.build_generation_request()

    assert error_info.value.workflow_id == "wf-a"
    assert error_info.value.report_error is False


def test_build_generation_request_captures_activation_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generation requests should carry activation deltas to serialization."""

    mod = import_workspace_controller_module(monkeypatch)
    workflow = SimpleNamespace(
        cubes={
            "Diffusion Upscale": SimpleNamespace(
                buffer={
                    "nodes": {
                        "checkpoint": {"mode": 4},
                        "load_anima": {"mode": 4},
                        "load_upscale_model": {},
                    }
                }
            )
        }
    )
    behavior_snapshot = EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={},
        card_decisions_by_alias={
            "Diffusion Upscale": {
                "checkpoint": NodeDisplayDecision(
                    visible=False,
                    enabled=False,
                    reason="policy:authored-bypass",
                ),
                "load_anima": NodeDisplayDecision(
                    visible=True,
                    enabled=True,
                    reason="explicit:enabled",
                ),
                "load_upscale_model": NodeDisplayDecision(
                    visible=False,
                    enabled=False,
                    reason="explicit:disabled",
                ),
            }
        },
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )
    view = _base_generation_view(
        workflow=workflow,
        editor_panels={
            "wf-a": SimpleNamespace(
                current_behavior_snapshot=lambda: behavior_snapshot,
            )
        },
    )
    controller = mod.WorkspaceController(view)
    _install_dirty_mask_preflight(view, True)
    _install_input_canvas_reconciliation(view)

    request = controller.build_generation_request()

    assert request.enabled_node_keys_by_alias == {"Diffusion Upscale": ("load_anima",)}
    assert request.disabled_node_keys_by_alias == {
        "Diffusion Upscale": ("load_upscale_model",)
    }


def test_build_generation_request_blocks_when_dirty_mask_flush_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generation request construction should fail closed on dirty-mask save failure."""

    mod = import_workspace_controller_module(monkeypatch)
    view = _base_generation_view(workflow=object())
    controller = mod.WorkspaceController(view)
    _install_dirty_mask_preflight(view, False)
    _install_input_canvas_reconciliation(view)

    with pytest.raises(mod.GenerationPreflightError):
        controller.build_generation_request()
