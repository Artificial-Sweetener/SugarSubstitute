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

"""Contract tests for complete in-workflow cube duplication."""

from __future__ import annotations

from typing import Any, cast

from substitute.application.cubes import CubeStackService
from substitute.application.workflows.cube_duplication_service import (
    CubeDuplicationService,
)
from substitute.domain.cube_library import CubeUpdatePolicy
from substitute.domain.generation.seed_control import SeedControlState, SeedMode
from substitute.domain.recipes.sugar_script_parser import (
    parse_sugar_script_document,
)
from substitute.domain.recipes.recipe_buffers import strip_recipe_buffers
from tests.sugar_serialization_test_helpers import serialize_sugar_script
from substitute.domain.workflow import CubeState, WorkflowState


class _LinkReconciler:
    """Record duplication link reconciliation inputs without changing buffers."""

    def __init__(self) -> None:
        """Initialize captured reconciliation calls."""

        self.transitions: list[tuple[list[str], list[str]]] = []
        self.sanitized_orders: list[list[str]] = []

    def reconcile_transition(
        self,
        *,
        previous_cube_states: dict[str, CubeState],
        previous_stack_order: list[str],
        current_cube_states: dict[str, CubeState],
        current_stack_order: list[str],
    ) -> None:
        """Capture previous and current stack order."""

        assert list(previous_cube_states) == previous_stack_order
        assert list(current_cube_states) == current_stack_order
        self.transitions.append((previous_stack_order, current_stack_order))

    def sanitize_current_state(
        self,
        *,
        cube_states: dict[str, CubeState],
        stack_order: list[str],
    ) -> None:
        """Capture the final stack order."""

        assert list(cube_states) == stack_order
        self.sanitized_orders.append(stack_order)


def _source_cube(alias: str = "Portrait") -> CubeState:
    """Build one fully populated mutable source cube."""

    return CubeState(
        cube_id="Owner/Portrait.cube",
        version="2.1.0",
        alias=alias,
        original_cube={"nodes": {"Prompt": {"inputs": {"text": "default"}}}},
        buffer={
            "nodes": {
                "Prompt": {
                    "inputs": {"text": "current prompt"},
                    "node_link": {"from_cube": "Anchor", "from_node": "Prompt"},
                },
                "Image": {"inputs": {"image": "E:/assets/input.png"}},
            }
        },
        display_name="Portrait Generator",
        undo_stack=[{"nodes": {"Prompt": {"inputs": {"text": "old"}}}}],
        redo_stack=[{"nodes": {"Prompt": {"inputs": {"text": "new"}}}}],
        dirty=True,
        ui={"prompt_editor_rich_rendering": {"Prompt.text": True}},
        field_control_states={"Prompt": {"seed": SeedControlState(SeedMode.FIXED)}},
        update_policy=CubeUpdatePolicy.FOLLOW_LATEST,
        bypassed=True,
    )


def _service(reconciler: _LinkReconciler) -> CubeDuplicationService:
    """Build the duplication service with deterministic collaborators."""

    return CubeDuplicationService(
        cube_stack_service=CubeStackService(),
        link_reconciler=reconciler,
    )


def test_duplicate_cube_appends_unique_complete_independent_copy() -> None:
    """Duplication should preserve every cube field and append a unique alias."""

    source = _source_cube()
    workflow = WorkflowState(cubes={"Portrait": source}, stack_order=["Portrait"])
    reconciler = _LinkReconciler()

    result = _service(reconciler).duplicate_cube(workflow, "Portrait")

    assert result is not None
    duplicate = result.duplicate_state
    assert result.duplicate_alias == "Portrait 2"
    assert result.added_index == 1
    assert workflow.stack_order == ["Portrait", "Portrait 2"]
    assert workflow.cubes["Portrait 2"] is duplicate
    assert workflow.metadata == {}
    assert duplicate is not source
    assert duplicate.alias == "Portrait 2"
    assert duplicate.cube_id == source.cube_id
    assert duplicate.version == source.version
    assert duplicate.display_name == source.display_name
    assert duplicate.dirty is True
    assert duplicate.update_policy is CubeUpdatePolicy.FOLLOW_LATEST
    assert duplicate.bypassed is True
    assert duplicate.original_cube == source.original_cube
    assert duplicate.buffer == source.buffer
    assert duplicate.undo_stack == source.undo_stack
    assert duplicate.redo_stack == source.redo_stack
    assert duplicate.ui == source.ui
    assert duplicate.field_control_states == source.field_control_states
    assert reconciler.transitions == [(["Portrait"], ["Portrait", "Portrait 2"])]
    assert reconciler.sanitized_orders == [["Portrait", "Portrait 2"]]

    duplicate.buffer["nodes"]["Prompt"]["inputs"]["text"] = "duplicate edit"  # type: ignore[index]
    duplicate.undo_stack.append({"extra": True})
    assert source.buffer["nodes"]["Prompt"]["inputs"]["text"] == "current prompt"  # type: ignore[index]
    assert len(source.undo_stack) == 1


def test_duplicate_cube_copies_alias_keyed_asset_metadata() -> None:
    """Image and mask asset references should be independently re-keyed."""

    workflow = WorkflowState(
        cubes={"Portrait": _source_cube()},
        stack_order=["Portrait"],
        metadata={
            "asset_refs": {
                "input_images": {
                    "Portrait:Image": {"kind": "local_file", "path": "input.png"}
                },
                "input_masks": {
                    "Portrait:Mask": {
                        "kind": "project_mask",
                        "relative_path": "mask.png",
                    }
                },
            }
        },
    )

    result = _service(_LinkReconciler()).duplicate_cube(workflow, "Portrait")

    assert result is not None
    refs = workflow.metadata["asset_refs"]
    assert isinstance(refs, dict)
    images = refs["input_images"]
    masks = refs["input_masks"]
    assert isinstance(images, dict)
    assert isinstance(masks, dict)
    assert images["Portrait 2:Image"] == images["Portrait:Image"]
    assert masks["Portrait 2:Mask"] == masks["Portrait:Mask"]
    assert images["Portrait 2:Image"] is not images["Portrait:Image"]
    assert masks["Portrait 2:Mask"] is not masks["Portrait:Mask"]
    assert result.asset_associations.input_image_count == 1
    assert result.asset_associations.input_mask_count == 1


def test_duplicate_cube_continues_numeric_alias_series_and_preserves_links() -> None:
    """A duplicate of a suffixed linked cube should use the next series alias."""

    source = _source_cube("Portrait 2")
    workflow = WorkflowState(
        cubes={"Portrait": _source_cube(), "Portrait 2": source},
        stack_order=["Portrait", "Portrait 2"],
    )

    result = _service(_LinkReconciler()).duplicate_cube(workflow, "Portrait 2")

    assert result is not None
    assert result.duplicate_alias == "Portrait 3"
    nodes = cast(dict[str, Any], result.duplicate_state.buffer["nodes"])
    prompt = nodes["Prompt"]
    assert isinstance(prompt, dict)
    assert prompt["node_link"] == {
        "from_cube": "Anchor",
        "from_node": "Prompt",
    }


def test_duplicate_cube_missing_source_is_noop() -> None:
    """A stale duplicate request should leave the workflow unchanged."""

    workflow = WorkflowState(cubes={"Portrait": _source_cube()})
    reconciler = _LinkReconciler()

    result = _service(reconciler).duplicate_cube(workflow, "Missing")

    assert result is None
    assert list(workflow.cubes) == ["Portrait"]
    assert workflow.stack_order == []
    assert reconciler.transitions == []
    assert reconciler.sanitized_orders == []


def test_duplicate_cube_round_trips_through_recipe_persistence() -> None:
    """The appended alias and current prompt should survive recipe serialization."""

    source = _source_cube()
    workflow = WorkflowState(cubes={"Portrait": source}, stack_order=["Portrait"])
    result = _service(_LinkReconciler()).duplicate_cube(workflow, "Portrait")
    assert result is not None

    script = serialize_sugar_script(
        strip_recipe_buffers(workflow.stack_order, cast(Any, workflow.cubes)),
        workflow.stack_order,
    )
    restored = parse_sugar_script_document(script)

    assert list(restored.buffers) == ["Portrait", "Portrait 2"]
    restored_nodes = cast(dict[str, Any], restored.buffers["Portrait 2"]["nodes"])
    duplicate_prompt = cast(dict[str, Any], restored_nodes["Prompt"])
    duplicate_inputs = cast(dict[str, Any], duplicate_prompt["inputs"])
    assert duplicate_inputs["text"] == "current prompt"
