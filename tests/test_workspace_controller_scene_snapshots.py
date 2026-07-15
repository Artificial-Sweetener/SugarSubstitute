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

"""Tests for WorkspaceController single scene snapshot behavior."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Mapping, cast

import pytest

from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.domain.links.prompt_endpoints import PromptEndpoint, PromptEndpointIndex
from substitute.domain.node_behavior import PromptRole
from tests.workspace_controller_generation_support import (
    SeedRandomizationRecorder,
    replace_seed_randomizer,
)
from tests.workspace_controller_test_support import import_workspace_controller_module


def test_build_scene_generation_snapshot_materializes_selected_scene(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Single-scene snapshot capture should serialize only the requested scene."""

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

    def _serialize_workflow_to_sugar_script(
        candidate: object,
        *,
        prompt_field_overrides: Mapping[tuple[str, str, str], object] | None = None,
    ) -> str:
        """Record prompt values serialized for the selected scene."""

        order.append("serialize")
        candidate_workflow = cast(Any, candidate)
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
    view.input_mask_save_controller = SimpleNamespace(
        flush_dirty_associated_masks_before_generation=_flush_dirty_masks,
    )
    view.input_canvas_presenter = SimpleNamespace(
        reconcile_active_input_canvas_image=lambda: order.append("reconcile"),
    )

    snapshot = controller.build_scene_generation_snapshot("portrait")

    assert order == ["flush", "reconcile", "randomize", "serialize"]
    assert snapshot.workflow_name == "Recipe - portrait"
    assert snapshot.positive_prompt_preview == "quality studio portrait"
    assert snapshot.scene_run_id is not None
    assert snapshot.scene_key == "portrait"
    assert snapshot.scene_title == "portrait"
    assert snapshot.scene_order == 0
    assert snapshot.scene_count == 2
    assert serialized_prompts == [
        ("quality\n\nstudio portrait", "bad anatomy\n\nextra fingers")
    ]
