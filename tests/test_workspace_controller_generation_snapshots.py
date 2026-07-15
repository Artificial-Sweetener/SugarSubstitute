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

"""Tests for WorkspaceController single generation snapshot behavior."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.domain.links.prompt_endpoints import PromptEndpoint, PromptEndpointIndex
from substitute.domain.node_behavior import PromptRole
from tests.workspace_controller_generation_support import (
    SeedRandomizationRecorder,
    replace_seed_randomizer,
)
from tests.workspace_controller_test_support import import_workspace_controller_module


def test_build_generation_snapshot_randomizes_before_serialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queued snapshot capture should freeze the randomized focused workflow state."""

    mod = import_workspace_controller_module(monkeypatch)
    order: list[str] = []
    workflow = SimpleNamespace(seed="original")

    def _serialize_workflow_to_sugar_script(candidate: object) -> str:
        """Serialize only after seed randomization."""

        order.append("serialize")
        assert candidate is workflow
        assert workflow.seed == "randomized"
        return f"# sugar {workflow.seed}"

    def _flush_dirty_masks() -> bool:
        """Record dirty-mask preflight."""

        order.append("flush")
        return True

    view = SimpleNamespace(
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
        active_editor_panel=None,
        cube_stacks={},
        editor_panels={},
        cube_load_service=SimpleNamespace(),
        cube_stack_service=SimpleNamespace(),
        active_override_manager=None,
        recipe_io_service=SimpleNamespace(
            serialize_workflow_to_sugar_script=_serialize_workflow_to_sugar_script
        ),
        workflow_export_service=SimpleNamespace(),
        _pending_cubes={},
        active_cube_stack=None,
    )
    controller = mod.WorkspaceController(view)
    replace_seed_randomizer(
        controller,
        SeedRandomizationRecorder(
            order,
            mutate=workflow,
            value="randomized",
        ),
    )
    view.input_mask_save_controller = SimpleNamespace(
        flush_dirty_associated_masks_before_generation=_flush_dirty_masks,
    )
    view.input_canvas_presenter = SimpleNamespace(
        reconcile_active_input_canvas_image=lambda: order.append("reconcile"),
    )

    snapshot = controller.build_generation_snapshot()

    assert order == ["flush", "reconcile", "randomize", "serialize"]
    assert snapshot.workflow_id == "wf-a"
    assert snapshot.workflow_name == "Recipe"
    assert snapshot.sugar_script_text == "# sugar randomized"
    assert snapshot.positive_prompt_preview is None


def test_build_generation_snapshot_stores_positive_prompt_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queued snapshot capture should store the semantic Positive Prompt preview."""

    mod = import_workspace_controller_module(monkeypatch)
    workflow = SimpleNamespace(
        stack_order=["Text"],
        cubes={
            "Text": SimpleNamespace(
                buffer={
                    "nodes": {
                        "positive_prompt": {
                            "inputs": {
                                "prompt_template": "  fox\nin\tmoonlight  ",
                            },
                        },
                    },
                },
            ),
        },
    )
    behavior_snapshot = EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={},
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
        prompt_endpoint_index=PromptEndpointIndex.from_endpoints(
            (
                PromptEndpoint(
                    cube_alias="Text",
                    role=PromptRole.POSITIVE,
                    node_name="positive_prompt",
                    field_key="prompt_template",
                ),
            )
        ),
    )
    editor_panel = SimpleNamespace(
        current_behavior_snapshot=lambda: behavior_snapshot,
    )
    received_prompt_endpoint_indexes: list[object] = []

    def _preprocess_workflow(**kwargs: object) -> object:
        """Record prompt endpoint indexes and return the workflow."""

        received_prompt_endpoint_indexes.append(kwargs.get("prompt_endpoint_index"))
        return kwargs["workflow"]

    view = SimpleNamespace(
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
        active_editor_panel=None,
        cube_stacks={},
        editor_panels={"wf-a": editor_panel},
        cube_load_service=SimpleNamespace(),
        cube_stack_service=SimpleNamespace(),
        active_override_manager=None,
        prompt_wildcard_preprocessing_service=SimpleNamespace(
            preprocess_workflow=_preprocess_workflow
        ),
        recipe_io_service=SimpleNamespace(
            serialize_workflow_to_sugar_script=lambda _workflow: "# sugar"
        ),
        workflow_export_service=SimpleNamespace(),
        _pending_cubes={},
        active_cube_stack=None,
    )
    controller = mod.WorkspaceController(view)
    view.input_mask_save_controller = SimpleNamespace(
        flush_dirty_associated_masks_before_generation=lambda: True,
    )
    view.input_canvas_presenter = SimpleNamespace(
        reconcile_active_input_canvas_image=lambda: None,
    )

    snapshot = controller.build_generation_snapshot()

    assert snapshot.positive_prompt_preview == "fox in moonlight"
    assert received_prompt_endpoint_indexes == [behavior_snapshot.prompt_endpoint_index]
