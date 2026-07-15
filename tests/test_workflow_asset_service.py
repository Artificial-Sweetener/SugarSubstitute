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

"""Contract tests for workflow asset association ownership."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from substitute.application.workflows import WorkflowAssetService
from substitute.domain.common import JsonObject
from substitute.domain.workflow import (
    CubeState,
    LocalFileAssetRef,
    ProjectMaskAssetRef,
    WorkflowState,
)


def test_associate_local_input_image_updates_graph_and_persisted_asset_ref() -> None:
    """Input image changes should update the authoring graph and asset metadata."""

    workflow = WorkflowState(
        cubes={
            "Inpaint": CubeState(
                cube_id="inpaint",
                version="1.0",
                alias="Inpaint",
                original_cube={},
                buffer={
                    "nodes": {
                        "load_image": {
                            "class_type": "LoadImage",
                            "inputs": {"image": "default.png"},
                        }
                    }
                },
            )
        }
    )

    associated = WorkflowAssetService().associate_local_input_image(
        workflow,
        cube_alias="Inpaint",
        node_name="load_image",
        image_path=Path("E:/images/selected.png"),
    )

    assert associated is True
    cube_state = workflow.cubes["Inpaint"]
    nodes = cast(dict[str, JsonObject], cube_state.buffer["nodes"])
    load_image = nodes["load_image"]
    inputs = cast(JsonObject, load_image["inputs"])
    assert inputs["image"] == "E:\\images\\selected.png"
    assert cube_state.dirty is True
    asset_refs = cast(JsonObject, workflow.metadata["asset_refs"])
    input_images = cast(JsonObject, asset_refs["input_images"])
    assert input_images["Inpaint:load_image"] == {
        "kind": "local_file",
        "path": "E:\\images\\selected.png",
    }


def test_input_image_asset_ref_falls_back_to_existing_graph_value() -> None:
    """Graph values without metadata should still expose a useful asset ref."""

    workflow = WorkflowState(
        cubes={
            "Inpaint": CubeState(
                cube_id="inpaint",
                version="1.0",
                alias="Inpaint",
                original_cube={},
                buffer={
                    "nodes": {
                        "load_image": {
                            "class_type": "LoadImage",
                            "inputs": {"image": "E:/images/legacy.png"},
                        }
                    }
                },
            )
        }
    )

    asset_ref = WorkflowAssetService().input_image_asset_ref(
        workflow,
        cube_alias="Inpaint",
        node_name="load_image",
    )

    assert asset_ref == LocalFileAssetRef(path="E:/images/legacy.png")


def test_associate_project_input_mask_updates_graph_and_persisted_asset_ref() -> None:
    """Input-bound masks should persist as Substitute-owned project mask refs."""

    workflow = WorkflowState(
        cubes={
            "Inpaint": CubeState(
                cube_id="inpaint",
                version="1.0",
                alias="Inpaint",
                original_cube={},
                buffer={
                    "nodes": {
                        "load_image_as_mask": {
                            "class_type": "LoadImageMask",
                            "inputs": {"image": "default.png"},
                        }
                    }
                },
            )
        }
    )

    associated = WorkflowAssetService().associate_project_input_mask(
        workflow,
        cube_alias="Inpaint",
        node_name="load_image_as_mask",
        relative_path="test__2160x3072__Inpaint__load_image_as_mask.png",
    )

    assert associated is True
    cube_state = workflow.cubes["Inpaint"]
    nodes = cast(dict[str, JsonObject], cube_state.buffer["nodes"])
    load_mask = nodes["load_image_as_mask"]
    inputs = cast(JsonObject, load_mask["inputs"])
    assert inputs["image"] == "test__2160x3072__Inpaint__load_image_as_mask.png"
    assert cube_state.dirty is True
    asset_refs = cast(JsonObject, workflow.metadata["asset_refs"])
    input_masks = cast(JsonObject, asset_refs["input_masks"])
    assert input_masks["Inpaint:load_image_as_mask"] == {
        "kind": "project_mask",
        "relative_path": "test__2160x3072__Inpaint__load_image_as_mask.png",
    }
    assert WorkflowAssetService().input_mask_asset_ref(
        workflow,
        cube_alias="Inpaint",
        node_name="load_image_as_mask",
    ) == ProjectMaskAssetRef(
        relative_path="test__2160x3072__Inpaint__load_image_as_mask.png"
    )


def test_associate_local_input_mask_updates_graph_and_persisted_asset_ref() -> None:
    """User-selected masks should persist as local file refs."""

    workflow = WorkflowState(
        cubes={
            "Inpaint": CubeState(
                cube_id="inpaint",
                version="1.0",
                alias="Inpaint",
                original_cube={},
                buffer={
                    "nodes": {
                        "load_image_as_mask": {
                            "class_type": "LoadImageMask",
                            "inputs": {"image": "default.png"},
                        }
                    }
                },
            )
        }
    )

    associated = WorkflowAssetService().associate_local_input_mask(
        workflow,
        cube_alias="Inpaint",
        node_name="load_image_as_mask",
        mask_path=Path("E:/masks/selected.png"),
    )

    assert associated is True
    cube_state = workflow.cubes["Inpaint"]
    nodes = cast(dict[str, JsonObject], cube_state.buffer["nodes"])
    load_mask = nodes["load_image_as_mask"]
    inputs = cast(JsonObject, load_mask["inputs"])
    assert inputs["image"] == "E:\\masks\\selected.png"
    asset_refs = cast(JsonObject, workflow.metadata["asset_refs"])
    input_masks = cast(JsonObject, asset_refs["input_masks"])
    assert input_masks["Inpaint:load_image_as_mask"] == {
        "kind": "local_file",
        "path": "E:\\masks\\selected.png",
    }
    assert WorkflowAssetService().input_mask_asset_ref(
        workflow,
        cube_alias="Inpaint",
        node_name="load_image_as_mask",
    ) == LocalFileAssetRef(path="E:\\masks\\selected.png")
