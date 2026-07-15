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

"""Tests for queued WorkspaceController snapshot facade behavior."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Mapping, cast

from pytest import MonkeyPatch

from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.domain.links.prompt_endpoints import PromptEndpoint, PromptEndpointIndex
from substitute.domain.node_behavior import PromptRole
from tests.workspace_controller_generation_support import (
    SeedRandomizationRecorder,
    replace_seed_randomizer,
)
from tests.workspace_controller_test_support import import_workspace_controller_module


def test_build_queued_generation_snapshots_materializes_authority_order(
    monkeypatch: MonkeyPatch,
) -> None:
    """Queued Generate should serialize one materialized workflow per scene."""

    mod = import_workspace_controller_module(monkeypatch)
    order: list[str] = []
    workflow = SimpleNamespace(
        stack_order=["Text"],
        cubes={
            "Text": SimpleNamespace(
                buffer={
                    "nodes": {
                        "positive_prompt": {
                            "class_type": "String",
                            "inputs": {
                                "prompt_template": (
                                    "quality\n\n"
                                    "**portrait\n"
                                    "studio portrait\n\n"
                                    "**cafe\n"
                                    "sitting in a cafe"
                                ),
                            },
                        },
                        "negative_prompt": {
                            "class_type": "String",
                            "inputs": {
                                "prompt_template": (
                                    "bad anatomy\n\n**portrait\nextra fingers"
                                ),
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
                PromptEndpoint(
                    cube_alias="Text",
                    role=PromptRole.NEGATIVE,
                    node_name="negative_prompt",
                    field_key="prompt_template",
                ),
            )
        ),
    )
    serialized_prompts: list[tuple[str, str]] = []
    focus_resets: list[tuple[object, str, str | None, int | None]] = []

    def _serialize_workflow_to_sugar_script(
        candidate: object,
        *,
        prompt_field_overrides: Mapping[tuple[str, str, str], object] | None = None,
    ) -> str:
        order.append("serialize")
        candidate_workflow = cast(Any, candidate)
        assert candidate_workflow is not workflow
        nodes = candidate_workflow.cubes["Text"].buffer["nodes"]
        overrides = prompt_field_overrides or {}
        positive = overrides.get(
            ("Text", "positive_prompt", "prompt_template"),
            nodes["positive_prompt"]["inputs"]["prompt_template"],
        )
        negative = overrides.get(
            ("Text", "negative_prompt", "prompt_template"),
            nodes["negative_prompt"]["inputs"]["prompt_template"],
        )
        serialized_prompts.append((cast(str, positive), cast(str, negative)))
        return f"# positive={positive!r}; negative={negative!r}"

    view = SimpleNamespace(
        request_reconfigure=lambda: None,
        request_settings=lambda: None,
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a",
            workflows={"wf-a": object()},
        ),
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
        output_canvas_state_service=SimpleNamespace(
            begin_output_generation=(
                lambda workflows, workflow_id, *, scene_run_id=None, scene_count=None: (
                    focus_resets.append(
                        (workflows, workflow_id, scene_run_id, scene_count)
                    )
                )
            )
        ),
        workflow_input_canvas_service=SimpleNamespace(),
        workflow_asset_service=SimpleNamespace(),
        add_output_image_signal=SimpleNamespace(emit=lambda *_args: None),
        path_bundle=SimpleNamespace(projects_dir=".", cubes_dir="."),
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0, tabText=lambda _idx: ""
        ),
        active_editor_panel=None,
        cube_stacks={},
        editor_panels={
            "wf-a": SimpleNamespace(
                current_behavior_snapshot=lambda: behavior_snapshot,
            )
        },
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
    replace_seed_randomizer(controller, SeedRandomizationRecorder(order))

    def _flush_dirty_associated_masks_before_generation() -> bool:
        order.append("flush")
        return True

    view.input_mask_save_controller = SimpleNamespace(
        flush_dirty_associated_masks_before_generation=(
            _flush_dirty_associated_masks_before_generation
        ),
    )
    view.input_canvas_presenter = SimpleNamespace(
        reconcile_active_input_canvas_image=lambda: order.append("reconcile"),
    )

    snapshots = controller.build_queued_generation_snapshots()

    assert order == ["flush", "reconcile", "randomize", "serialize", "serialize"]
    assert [snapshot.workflow_name for snapshot in snapshots] == [
        "Recipe - portrait",
        "Recipe - cafe",
    ]
    assert len({snapshot.scene_run_id for snapshot in snapshots}) == 1
    assert snapshots[0].scene_run_id is not None
    assert focus_resets == [
        (
            view.workflow_session_service.workflows,
            "wf-a",
            snapshots[0].scene_run_id,
            2,
        )
    ]
    assert [
        (
            snapshot.scene_key,
            snapshot.scene_title,
            snapshot.scene_order,
            snapshot.scene_count,
        )
        for snapshot in snapshots
    ] == [
        ("portrait", "portrait", 0, 2),
        ("cafe", "cafe", 1, 2),
    ]
    assert [snapshot.positive_prompt_preview for snapshot in snapshots] == [
        "quality studio portrait",
        "quality sitting in a cafe",
    ]
    assert serialized_prompts == [
        ("quality\n\nstudio portrait", "bad anatomy\n\nextra fingers"),
        ("quality\n\nsitting in a cafe", "bad anatomy"),
    ]
    assert (
        workflow.cubes["Text"]
        .buffer["nodes"]["positive_prompt"]["inputs"]["prompt_template"]
        .startswith("quality\n\n**portrait")
    )


def test_build_queued_generation_snapshots_uses_single_snapshot_without_scenes(
    monkeypatch: MonkeyPatch,
) -> None:
    """Queued Generate should preserve normal snapshot behavior without scenes."""

    mod = import_workspace_controller_module(monkeypatch)
    order: list[str] = []
    workflow = SimpleNamespace(seed="original")

    def _serialize_workflow_to_sugar_script(candidate: object) -> str:
        order.append("serialize")
        assert candidate is not workflow
        assert cast(Any, candidate).seed == "randomized"
        return f"# sugar {cast(Any, candidate).seed}"

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

    def _flush_dirty_associated_masks_before_generation() -> bool:
        order.append("flush")
        return True

    view.input_mask_save_controller = SimpleNamespace(
        flush_dirty_associated_masks_before_generation=(
            _flush_dirty_associated_masks_before_generation
        ),
    )
    view.input_canvas_presenter = SimpleNamespace(
        reconcile_active_input_canvas_image=lambda: order.append("reconcile"),
    )

    snapshots = controller.build_queued_generation_snapshots()

    assert order == ["flush", "reconcile", "randomize", "serialize"]
    assert len(snapshots) == 1
    assert snapshots[0].workflow_name == "Recipe"
    assert snapshots[0].sugar_script_text == "# sugar randomized"
    assert snapshots[0].scene_run_id is None
    assert snapshots[0].scene_key is None
    assert snapshots[0].scene_title is None
    assert snapshots[0].scene_order is None
    assert snapshots[0].scene_count is None


def test_build_queued_generation_snapshots_uses_single_snapshot_for_one_scene(
    monkeypatch: MonkeyPatch,
) -> None:
    """Queued Generate should fan out only when multiple scenes are runnable."""

    mod = import_workspace_controller_module(monkeypatch)
    order: list[str] = []
    workflow = SimpleNamespace(
        stack_order=["Text"],
        cubes={
            "Text": SimpleNamespace(
                buffer={
                    "nodes": {
                        "positive_prompt": {
                            "class_type": "String",
                            "inputs": {
                                "prompt_template": (
                                    "quality\n\n**portrait\nstudio portrait"
                                ),
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

    def _serialize_workflow_to_sugar_script(candidate: object) -> str:
        order.append("serialize")
        assert candidate is not workflow
        prompt = (
            cast(Any, candidate)
            .cubes["Text"]
            .buffer["nodes"]["positive_prompt"]["inputs"]["prompt_template"]
        )
        return f"# positive={prompt!r}"

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
        editor_panels={
            "wf-a": SimpleNamespace(
                current_behavior_snapshot=lambda: behavior_snapshot,
            )
        },
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
    replace_seed_randomizer(controller, SeedRandomizationRecorder(order))

    def _flush_dirty_associated_masks_before_generation() -> bool:
        order.append("flush")
        return True

    view.input_mask_save_controller = SimpleNamespace(
        flush_dirty_associated_masks_before_generation=(
            _flush_dirty_associated_masks_before_generation
        ),
    )
    view.input_canvas_presenter = SimpleNamespace(
        reconcile_active_input_canvas_image=lambda: order.append("reconcile"),
    )

    snapshots = controller.build_queued_generation_snapshots()

    assert order == ["flush", "reconcile", "randomize", "serialize"]
    assert len(snapshots) == 1
    assert snapshots[0].workflow_name == "Recipe"
    assert "Recipe - portrait" not in snapshots[0].workflow_name
    assert snapshots[0].positive_prompt_preview == "quality **portrait studio portrait"
    assert snapshots[0].scene_run_id is None
    assert snapshots[0].scene_key is None
