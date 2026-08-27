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

"""Regression coverage for cube-boundary-only input asset staging."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from substitute.application.generation import ComfyAssetStagingService
from substitute.domain.common import JsonObject
from substitute.domain.generation import ComfyStagedAsset
from substitute.domain.workflow import CubeState, WorkflowState


class _RecordingStager:
    """Return deterministic Comfy input names for staged local files."""

    def stage_file_for_load_image(
        self,
        *,
        source_path: Path,
        target_subfolder: str,
        content_hash: str,
        node_class: str,
    ) -> ComfyStagedAsset:
        """Project one source file into its execution-only Comfy namespace."""

        del content_hash, node_class
        return ComfyStagedAsset(
            source_path=source_path,
            execution_value=f"{target_subfolder}/{source_path.name}",
            operation="uploaded",
        )


def test_missing_local_path_is_removed_from_failed_execution_payload() -> None:
    """A failed staging result should retain no executable local path."""

    payload: JsonObject = {
        "1": {
            "class_type": "LoadImageMask",
            "inputs": {"image": "E:/missing/mask.png"},
        }
    }

    result = ComfyAssetStagingService(stager=_RecordingStager()).stage_payload(
        workflow_payload=payload,
        workflow_id="wf-missing",
        workflow_name="Missing",
    )

    failed_node = cast(JsonObject, result.workflow_payload["1"])
    assert cast(JsonObject, failed_node["inputs"])["image"] == ""
    assert len(result.failures) == 1


def test_comfy_input_subfolder_name_remains_native() -> None:
    """A relative Comfy input namespace must not be mistaken for a local path."""

    payload: JsonObject = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": "uploads/session/input.png"},
        }
    }

    result = ComfyAssetStagingService(stager=_RecordingStager()).stage_payload(
        workflow_payload=payload,
        workflow_id="wf-comfy-input",
        workflow_name="Comfy Input",
    )

    staged_node = cast(JsonObject, result.workflow_payload["1"])
    assert cast(JsonObject, staged_node["inputs"])["image"] == (
        "uploads/session/input.png"
    )
    assert result.staged_assets == ()
    assert result.failures == ()


def test_boundary_only_any_load_image_stages_without_internal_consumers(
    tmp_path: Path,
) -> None:
    """Any/Load Image should stage its exported source without mutating authoring."""

    image_path = tmp_path / "boundary.png"
    image_path.write_bytes(b"image")
    graph: JsonObject = {
        "nodes": {
            "load_image": {
                "class_type": "LoadImage",
                "inputs": {"image": str(image_path)},
            }
        },
        "outputs": {"output.image": "load_image"},
    }
    workflow = WorkflowState(
        cubes={
            "Load": CubeState(
                cube_id="Any/Load Image.cube",
                version="1.0.0",
                alias="Load",
                original_cube=graph,
                buffer=graph,
            )
        },
        stack_order=["Load"],
    )
    payload: JsonObject = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": str(image_path)},
            "_meta": {"title": "Load.load_image"},
        }
    }

    result = ComfyAssetStagingService(stager=_RecordingStager()).stage_payload(
        workflow_payload=payload,
        workflow_id="wf-boundary",
        workflow_name="Boundary",
        workflow=workflow,
    )

    staged_node = cast(JsonObject, result.workflow_payload["1"])
    assert cast(JsonObject, staged_node["inputs"])["image"] == (
        "substitute/wf-boundary/boundary.png"
    )
    original_node = cast(JsonObject, payload["1"])
    assert cast(JsonObject, original_node["inputs"])["image"] == str(image_path)
    authored_nodes = cast(JsonObject, graph["nodes"])
    authored_node = cast(JsonObject, authored_nodes["load_image"])
    assert cast(JsonObject, authored_node["inputs"])["image"] == str(image_path)
    assert result.failures == ()
