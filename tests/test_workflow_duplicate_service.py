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

"""Contract tests for workflow duplication copy semantics."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest

from substitute.application.workflows import WorkflowDuplicateService
from substitute.domain.generation.seed_control import SeedControlState, SeedMode
from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.cube_library import CubeUpdatePolicy
from substitute.domain.workflow import CubeState, OutputFocusMode, WorkflowState


def _cube_state(alias: str) -> CubeState:
    """Build one mutable cube state with nested authoring data."""

    return CubeState(
        cube_id=f"Owner/Repo/{alias}.cube",
        version="1.0.0",
        alias=alias,
        original_cube={"nodes": {"Original": {"inputs": {"value": 1}}}},
        buffer={
            "nodes": {
                "Load": {
                    "class_type": "LoadImage",
                    "inputs": {"image": f"assets/{alias}.png"},
                },
                "Prompt": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": f"{alias} prompt"},
                },
            }
        },
        display_name=f"{alias} Display",
        undo_stack=[{"nodes": {"Prompt": {"inputs": {"text": "old"}}}}],
        redo_stack=[{"nodes": {"Prompt": {"inputs": {"text": "new"}}}}],
        dirty=True,
        ui={
            "source": {"kind": "local", "path": f"E:/cubes/{alias}.cube"},
            "prompt_editor_rich_rendering": {
                "Prompt.text": False,
            },
        },
    )


def _workflow_state() -> WorkflowState:
    """Build one source workflow with durable and volatile state populated."""

    image_id = uuid4()
    mask_id = uuid4()
    output_id = uuid4()
    workflow = WorkflowState(
        cubes={
            "CubeA": _cube_state("CubeA"),
            "CubeB": _cube_state("CubeB"),
        },
        stack_order=["CubeA", "CubeB"],
        metadata={
            "asset_refs": {
                "input_images": {
                    "CubeA:Load": {
                        "kind": "project_asset",
                        "relative_path": "assets/CubeA.png",
                    }
                },
                "input_masks": {
                    "CubeA:Mask": {
                        "kind": "project_mask",
                        "relative_path": "CubeA-mask.png",
                    }
                },
            },
            "title": "Recipe",
        },
        global_overrides={"seed": {"value": 1234, "enabled": True}},
        override_control_states={"seed": SeedControlState(SeedMode.FIXED)},
        global_override_selections={"seed": True, "scheduler": False},
    )
    workflow.cubes["CubeA"].field_control_states = {
        "Prompt": {"seed": SeedControlState(SeedMode.FIXED)}
    }
    workflow.cubes["CubeA"].update_policy = CubeUpdatePolicy.FOLLOW_LATEST
    workflow.cubes["CubeA"].bypassed = True
    workflow.canvas.input_key_map["CubeA:Load"] = image_id
    workflow.canvas.mask_associations[("CubeA", "Mask")] = mask_id
    workflow.canvas.mask_to_image_map[mask_id] = image_id
    workflow.canvas.input_image_uuid = image_id
    workflow.output_image_uuids.append(output_id)
    workflow.output_focus_mode = OutputFocusMode.MANUAL
    workflow.active_output_uuid = output_id
    workflow.active_output_set_index = 4
    workflow.active_output_source_key = "wf-a:output"
    workflow.active_output_scene_key = "portrait"
    workflow.active_output_scene_overview = True
    return workflow


def test_duplicate_workflow_copies_authoring_state() -> None:
    """Duplicate workflow should preserve durable authoring state."""

    source = _workflow_state()

    duplicate = WorkflowDuplicateService().duplicate_workflow(source)

    assert duplicate is not source
    assert duplicate.stack_order == ["CubeA", "CubeB"]
    assert set(duplicate.cubes) == {"CubeA", "CubeB"}
    assert duplicate.cubes["CubeA"].cube_id == source.cubes["CubeA"].cube_id
    assert duplicate.cubes["CubeA"].version == source.cubes["CubeA"].version
    assert duplicate.cubes["CubeA"].alias == "CubeA"
    assert duplicate.cubes["CubeA"].display_name == "CubeA Display"
    assert duplicate.cubes["CubeA"].dirty is True
    assert duplicate.cubes["CubeA"].update_policy is CubeUpdatePolicy.FOLLOW_LATEST
    assert duplicate.cubes["CubeA"].bypassed is True
    assert duplicate.metadata == source.metadata
    assert duplicate.global_overrides == source.global_overrides
    assert duplicate.override_control_states == source.override_control_states
    assert (
        duplicate.cubes["CubeA"].field_control_states
        == source.cubes["CubeA"].field_control_states
    )
    assert duplicate.global_override_selections == source.global_override_selections


def test_duplicate_workflow_deep_copies_mutable_cube_state() -> None:
    """Duplicate cube buffers and history should be independent from the source."""

    source = _workflow_state()
    duplicate = WorkflowDuplicateService().duplicate_workflow(source)
    duplicate_buffer = cast(dict[str, Any], duplicate.cubes["CubeA"].buffer)
    duplicate_nodes = cast(dict[str, Any], duplicate_buffer["nodes"])
    duplicate_prompt = cast(dict[str, Any], duplicate_nodes["Prompt"])
    duplicate_prompt_inputs = cast(dict[str, Any], duplicate_prompt["inputs"])
    duplicate_original = cast(dict[str, Any], duplicate.cubes["CubeA"].original_cube)
    duplicate_original_nodes = cast(dict[str, Any], duplicate_original["nodes"])
    duplicate_original_node = cast(dict[str, Any], duplicate_original_nodes["Original"])
    duplicate_original_inputs = cast(dict[str, Any], duplicate_original_node["inputs"])
    duplicate_undo = cast(dict[str, Any], duplicate.cubes["CubeA"].undo_stack[0])
    duplicate_undo_nodes = cast(dict[str, Any], duplicate_undo["nodes"])
    duplicate_undo_prompt = cast(dict[str, Any], duplicate_undo_nodes["Prompt"])
    duplicate_undo_inputs = cast(dict[str, Any], duplicate_undo_prompt["inputs"])
    duplicate_ui = cast(dict[str, Any], duplicate.cubes["CubeA"].ui)
    duplicate_ui_source = cast(dict[str, Any], duplicate_ui["source"])
    duplicate_rich_rendering = cast(
        dict[str, Any],
        duplicate_ui["prompt_editor_rich_rendering"],
    )

    duplicate_prompt_inputs["text"] = "changed"
    duplicate_original_inputs["value"] = 2
    duplicate_undo_inputs["text"] = "undo changed"
    duplicate.cubes["CubeA"].redo_stack.append({"new": "entry"})
    duplicate_ui_source["path"] = "E:/changed.cube"
    duplicate_rich_rendering["Prompt.text"] = True
    source_buffer = cast(dict[str, Any], source.cubes["CubeA"].buffer)
    source_nodes = cast(dict[str, Any], source_buffer["nodes"])
    source_prompt = cast(dict[str, Any], source_nodes["Prompt"])
    source_prompt_inputs = cast(dict[str, Any], source_prompt["inputs"])
    source_original = cast(dict[str, Any], source.cubes["CubeA"].original_cube)
    source_original_nodes = cast(dict[str, Any], source_original["nodes"])
    source_original_node = cast(dict[str, Any], source_original_nodes["Original"])
    source_original_inputs = cast(dict[str, Any], source_original_node["inputs"])
    source_undo = cast(dict[str, Any], source.cubes["CubeA"].undo_stack[0])
    source_undo_nodes = cast(dict[str, Any], source_undo["nodes"])
    source_undo_prompt = cast(dict[str, Any], source_undo_nodes["Prompt"])
    source_undo_inputs = cast(dict[str, Any], source_undo_prompt["inputs"])

    assert source_prompt_inputs["text"] == "CubeA prompt"
    assert source_original_inputs["value"] == 1
    assert source_undo_inputs["text"] == "old"
    assert source.cubes["CubeA"].redo_stack == [
        {"nodes": {"Prompt": {"inputs": {"text": "new"}}}}
    ]
    assert source.cubes["CubeA"].ui == {
        "source": {"kind": "local", "path": "E:/cubes/CubeA.cube"},
        "prompt_editor_rich_rendering": {
            "Prompt.text": False,
        },
    }


def test_duplicate_direct_workflow_copies_authoring_state_without_runtime() -> None:
    """Direct document duplication should reset live behavior collaborators."""

    source = WorkflowState(
        direct_workflow=DirectWorkflowState(
            source_path=Path("workflows/demo.json"),
            source_workflow={"nodes": [], "links": []},
            buffer={"nodes": {"1": {"class_type": "KSampler", "inputs": {}}}},
            ui={"expanded": {"1": True}, "node_behavior_runtime": object()},
            dirty=True,
        )
    )

    duplicate = WorkflowDuplicateService().duplicate_workflow(source)

    source_direct = source.direct_workflow
    assert source_direct is not None
    assert duplicate.direct_workflow is not None
    assert duplicate.direct_workflow is not source_direct
    assert duplicate.direct_workflow.buffer == source_direct.buffer
    assert duplicate.direct_workflow.buffer is not source_direct.buffer
    assert duplicate.direct_workflow.ui == {"expanded": {"1": True}}
    assert duplicate.direct_workflow.dirty is True


def test_duplicate_workflow_deep_copies_metadata_and_overrides() -> None:
    """Duplicate metadata and overrides should be editable without source mutation."""

    source = _workflow_state()
    duplicate = WorkflowDuplicateService().duplicate_workflow(source)
    duplicate_metadata = cast(dict[str, Any], duplicate.metadata)
    duplicate_asset_refs = cast(dict[str, Any], duplicate_metadata["asset_refs"])
    duplicate_input_images = cast(dict[str, Any], duplicate_asset_refs["input_images"])
    duplicate_load_ref = cast(dict[str, Any], duplicate_input_images["CubeA:Load"])
    duplicate_seed_override = cast(dict[str, Any], duplicate.global_overrides["seed"])
    duplicate.override_control_states["seed"] = SeedControlState(SeedMode.RANDOM)
    duplicate.cubes["CubeA"].field_control_states["Prompt"]["seed"] = SeedControlState(
        SeedMode.RANDOM
    )
    duplicate_override_selections = duplicate.global_override_selections

    duplicate_load_ref["relative_path"] = "assets/changed.png"
    duplicate_seed_override["value"] = 999
    duplicate_override_selections["seed"] = False
    source_metadata = cast(dict[str, Any], source.metadata)
    source_asset_refs = cast(dict[str, Any], source_metadata["asset_refs"])
    source_input_images = cast(dict[str, Any], source_asset_refs["input_images"])
    source_load_ref = cast(dict[str, Any], source_input_images["CubeA:Load"])
    source_seed_override = cast(dict[str, Any], source.global_overrides["seed"])

    assert source_load_ref["relative_path"] == "assets/CubeA.png"
    assert source_seed_override["value"] == 1234
    assert source.override_control_states["seed"].mode == SeedMode.FIXED
    assert (
        source.cubes["CubeA"].field_control_states["Prompt"]["seed"].mode
        == SeedMode.FIXED
    )
    assert source.global_override_selections["seed"] is True


def test_duplicate_workflow_resets_live_canvas_and_output_state() -> None:
    """Duplicate workflow should reset volatile canvas and output session state."""

    source = _workflow_state()

    duplicate = WorkflowDuplicateService().duplicate_workflow(source)

    assert duplicate.canvas.input_key_map == {}
    assert duplicate.canvas.mask_associations == {}
    assert duplicate.canvas.mask_to_image_map == {}
    assert duplicate.canvas.input_image_uuid is None
    assert duplicate.output_image_uuids == []
    assert duplicate.output_focus_mode is OutputFocusMode.AUTOMATIC
    assert duplicate.active_output_uuid is None
    assert duplicate.active_output_set_index == 1
    assert duplicate.active_output_source_key is None
    assert duplicate.active_output_scene_key is None
    assert duplicate.active_output_scene_overview is False


def test_duplicate_workflow_logs_clone_summary(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Workflow duplication should log clone counts and volatile-state resets."""

    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.application.workflows.workflow_duplicate_service",
    )

    WorkflowDuplicateService().duplicate_workflow(_workflow_state())

    assert "Workflow duplicate clone started" in caplog.text
    assert "Workflow duplicate clone completed" in caplog.text
    assert "cube_count=2" in caplog.text
    assert "stack_order_count=2" in caplog.text
    assert "metadata_key_count=2" in caplog.text
    assert "global_override_count=1" in caplog.text
    assert "global_override_selection_count=2" in caplog.text
    assert "canvas_input_reset=True" in caplog.text
    assert "canvas_mask_reset=True" in caplog.text
    assert "output_history_reset=True" in caplog.text


def test_duplicate_workflow_logs_slow_clone_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Workflow duplication should warn when clone duration exceeds threshold."""

    times = iter([0.0, 0.2])
    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.application.workflows.workflow_duplicate_service",
    )

    WorkflowDuplicateService(clock=lambda: next(times)).duplicate_workflow(
        _workflow_state()
    )

    assert "Workflow duplicate clone was slow" in caplog.text
    assert "elapsed_ms=200.000" in caplog.text
