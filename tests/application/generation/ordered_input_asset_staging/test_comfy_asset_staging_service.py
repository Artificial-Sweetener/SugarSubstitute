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

"""Contract tests for generation asset staging and payload projection."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from substitute.application.generation import ComfyAssetStagingService
from substitute.application.generation.input_asset_staging_plan_service import (
    InputAssetStagingPlanService,
)
from substitute.application.workflows.input_asset_field_service import (
    InputAssetFieldService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
)
from substitute.application.workflows import WorkflowAssetService
from substitute.domain.common import JsonObject
from substitute.domain.generation import ComfyStagedAsset
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.domain.comfy_workflow import DirectWorkflowState


class _FakeStager:
    """Record staged files and return deterministic Comfy input values."""

    def __init__(self) -> None:
        self.calls: list[tuple[Path, str, str, str]] = []

    def stage_file_for_load_image(
        self,
        *,
        source_path: Path,
        target_subfolder: str,
        content_hash: str,
        node_class: str,
    ) -> ComfyStagedAsset:
        self.calls.append((source_path, target_subfolder, content_hash, node_class))
        return ComfyStagedAsset(
            source_path=source_path,
            execution_value=f"{target_subfolder}/{source_path.name}",
            operation="uploaded",
        )


class _DefinitionGateway:
    """Return deterministic live definitions for custom upload nodes."""

    def __init__(self, definitions: dict[str, JsonObject]) -> None:
        """Store definitions by backend class name."""

        self._definitions = definitions
        self.cached_calls: list[str] = []

    def get_node_definition(self, node_class: str) -> JsonObject:
        """Return one cached custom definition."""

        self.cached_calls.append(node_class)
        return self._definitions.get(node_class, {})

    def get_required_node_definition(self, node_class: str) -> JsonObject:
        """Return one required definition through the same fixture source."""

        return self._definitions.get(node_class, {})


def test_stage_payload_rewrites_load_image_paths_without_mutating_authoring_payload(
    tmp_path: Path,
) -> None:
    """Generation staging should rewrite only the execution payload copy."""

    image_path = tmp_path / "input.png"
    image_path.write_bytes(b"image")
    payload: JsonObject = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": str(image_path)},
        },
        "2": {
            "class_type": "KSampler",
            "inputs": {},
        },
    }
    stager = _FakeStager()

    result = ComfyAssetStagingService(stager=stager).stage_payload(
        workflow_payload=payload,
        workflow_id="wf-1",
        workflow_name="Workflow 1",
    )

    original_node = cast(JsonObject, payload["1"])
    original_inputs = cast(JsonObject, original_node["inputs"])
    staged_node = cast(JsonObject, result.workflow_payload["1"])
    staged_inputs = cast(JsonObject, staged_node["inputs"])
    assert original_inputs["image"] == str(image_path)
    assert staged_inputs["image"] == f"substitute/wf-1/{image_path.name}"
    assert result.failures == ()
    assert len(result.staged_assets) == 1
    assert stager.calls[0][0] == image_path
    assert stager.calls[0][1] == "substitute/wf-1"
    assert stager.calls[0][3] == "LoadImage"


def test_stage_payload_rewrites_only_execution_node_class_for_authorized_assets(
    tmp_path: Path,
) -> None:
    """Local authorization should leave the authored core node contract untouched."""

    image_path = tmp_path / "input.png"
    image_path.write_bytes(b"image")
    payload: JsonObject = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": str(image_path)},
        }
    }

    class _AuthorizedStager(_FakeStager):
        """Return an opaque token and execution-only backend node class."""

        def stage_file_for_load_image(
            self,
            *,
            source_path: Path,
            target_subfolder: str,
            content_hash: str,
            node_class: str,
        ) -> ComfyStagedAsset:
            """Record the core class and return authorized execution data."""

            self.calls.append((source_path, target_subfolder, content_hash, node_class))
            return ComfyStagedAsset(
                source_path=source_path,
                execution_value="opaque-token",
                operation="authorized",
                execution_node_class="SubstituteBackendLoadImage",
            )

    result = ComfyAssetStagingService(stager=_AuthorizedStager()).stage_payload(
        workflow_payload=payload,
        workflow_id="wf-1",
        workflow_name="Workflow 1",
    )

    original_node = cast(JsonObject, payload["1"])
    staged_node = cast(JsonObject, result.workflow_payload["1"])
    staged_inputs = cast(JsonObject, staged_node["inputs"])
    assert original_node["class_type"] == "LoadImage"
    assert staged_node["class_type"] == "SubstituteBackendLoadImage"
    assert staged_inputs["image"] == "opaque-token"


def test_stage_payload_reports_missing_local_load_image_file() -> None:
    """Missing local file references should fail before queueing generation."""

    payload: JsonObject = {
        "7": {
            "class_type": "LoadImageMask",
            "inputs": {"image": "E:/missing/mask.png"},
        }
    }

    result = ComfyAssetStagingService(stager=_FakeStager()).stage_payload(
        workflow_payload=payload,
        workflow_id="wf-1",
        workflow_name="Workflow 1",
    )

    assert result.staged_assets == ()
    assert len(result.failures) == 1
    assert result.failures[0].node_id == "7"
    assert result.failures[0].node_class == "LoadImageMask"


def test_stage_payload_reports_required_load_image_without_selection() -> None:
    """Empty image-loader values should fail before queueing generation."""

    payload: JsonObject = {
        "7": {
            "class_type": "LoadImage",
            "inputs": {},
        }
    }

    result = ComfyAssetStagingService(stager=_FakeStager()).stage_payload(
        workflow_payload=payload,
        workflow_id="wf-1",
        workflow_name="Workflow 1",
    )

    assert result.staged_assets == ()
    assert len(result.failures) == 1
    assert result.failures[0].node_id == "7"
    assert result.failures[0].node_class == "LoadImage"
    assert result.failures[0].input_name == "image"
    assert result.failures[0].message == "Required image input has no selected image."


def test_stage_payload_resolves_project_relative_load_image_mask(
    tmp_path: Path,
) -> None:
    """Project mask filenames should stage from Substitute's project mask folder."""

    mask_path = tmp_path / "Recipe" / "masks" / "input_mask.png"
    mask_path.parent.mkdir(parents=True)
    mask_path.write_bytes(b"mask")
    payload: JsonObject = {
        "7": {
            "class_type": "LoadImageMask",
            "inputs": {"image": "input_mask.png"},
        }
    }
    stager = _FakeStager()

    result = ComfyAssetStagingService.with_projects_dir(
        stager=stager,
        projects_dir=tmp_path,
    ).stage_payload(
        workflow_payload=payload,
        workflow_id="wf-1",
        workflow_name="Recipe",
    )

    staged_node = cast(JsonObject, result.workflow_payload["7"])
    staged_inputs = cast(JsonObject, staged_node["inputs"])
    assert stager.calls[0][0] == mask_path
    assert staged_inputs["image"] == "substitute/wf-1/input_mask.png"
    assert result.failures == ()


def test_stage_payload_uses_red_channel_for_project_grayscale_masks(
    tmp_path: Path,
) -> None:
    """Substitute-owned grayscale project masks should execute through red channel."""

    mask_path = tmp_path / "Recipe" / "masks" / "input_mask.png"
    mask_path.parent.mkdir(parents=True)
    mask_path.write_bytes(b"mask")
    payload: JsonObject = {
        "7": {
            "class_type": "LoadImageMask",
            "inputs": {"image": "input_mask.png", "channel": "alpha"},
        }
    }

    result = ComfyAssetStagingService.with_projects_dir(
        stager=_FakeStager(),
        projects_dir=tmp_path,
    ).stage_payload(
        workflow_payload=payload,
        workflow_id="wf-1",
        workflow_name="Recipe",
    )

    original_node = cast(JsonObject, payload["7"])
    original_inputs = cast(JsonObject, original_node["inputs"])
    staged_node = cast(JsonObject, result.workflow_payload["7"])
    staged_inputs = cast(JsonObject, staged_node["inputs"])
    assert original_inputs["channel"] == "alpha"
    assert staged_inputs["channel"] == "red"
    assert result.failures == ()


def test_stage_payload_preserves_channel_for_non_project_load_image_masks(
    tmp_path: Path,
) -> None:
    """Arbitrary local mask files should keep the user's selected Comfy channel."""

    mask_path = tmp_path / "external_mask.png"
    mask_path.write_bytes(b"mask")
    payload: JsonObject = {
        "7": {
            "class_type": "LoadImageMask",
            "inputs": {"image": str(mask_path), "channel": "alpha"},
        }
    }

    result = ComfyAssetStagingService.with_projects_dir(
        stager=_FakeStager(),
        projects_dir=tmp_path / "projects",
    ).stage_payload(
        workflow_payload=payload,
        workflow_id="wf-1",
        workflow_name="Recipe",
    )

    staged_node = cast(JsonObject, result.workflow_payload["7"])
    staged_inputs = cast(JsonObject, staged_node["inputs"])
    assert staged_inputs["channel"] == "alpha"
    assert result.failures == ()


def test_stage_payload_reports_missing_project_mask_asset(tmp_path: Path) -> None:
    """Project mask refs should fail before queueing when their file is missing."""

    workflow = WorkflowState(
        cubes={
            "Inpaint": CubeState(
                cube_id="Inpaint",
                version="1.0",
                alias="Inpaint",
                original_cube={},
                buffer={
                    "nodes": {
                        "load_image_as_mask": {
                            "class_type": "LoadImageMask",
                            "inputs": {"image": "missing_mask.png"},
                        },
                        "consumer": {
                            "class_type": "Consumer",
                            "inputs": {"mask": ["load_image_as_mask", 0]},
                        },
                    }
                },
            )
        },
        stack_order=["Inpaint"],
    )
    assert WorkflowAssetService().associate_project_input_mask(
        workflow,
        section_key="Inpaint",
        node_name="load_image_as_mask",
        field_key="image",
        relative_path="missing_mask.png",
    )
    payload: JsonObject = {
        "7": {
            "class_type": "LoadImageMask",
            "inputs": {"image": "missing_mask.png"},
            "_meta": {"title": "Inpaint.load_image_as_mask"},
        }
    }

    result = ComfyAssetStagingService.with_projects_dir(
        stager=_FakeStager(),
        projects_dir=tmp_path,
    ).stage_payload(
        workflow_payload=payload,
        workflow_id="wf-1",
        workflow_name="Recipe",
        workflow=workflow,
    )

    assert result.staged_assets == ()
    assert len(result.failures) == 1
    assert result.failures[0].source_value == "missing_mask.png"


def test_direct_custom_upload_fields_stage_through_semantic_plan(
    tmp_path: Path,
) -> None:
    """Custom direct image and mask upload fields should stage without name rules."""

    image_path = tmp_path / "photo.png"
    mask_path = tmp_path / "stencil.png"
    image_path.write_bytes(b"photo")
    mask_path.write_bytes(b"stencil")
    graph: JsonObject = {
        "nodes": {
            "10": {
                "class_type": "PhotoPicker",
                "inputs": {"photo_path": str(image_path)},
            },
            "11": {
                "class_type": "StencilPicker",
                "inputs": {"stencil_path": str(mask_path)},
            },
            "12": {
                "class_type": "Consumer",
                "inputs": {"pixels": ["10", 0], "mask": ["11", 0]},
            },
        }
    }
    workflow = WorkflowState(
        direct_workflow=DirectWorkflowState(
            source_path=tmp_path / "workflow.json",
            source_workflow=graph,
            buffer=graph,
        )
    )
    definitions: dict[str, JsonObject] = {
        "PhotoPicker": {
            "input": {
                "required": {"photo_path": (["photo.png"], {"image_upload": True})}
            },
            "output": ["IMAGE"],
        },
        "StencilPicker": {
            "input": {
                "required": {"stencil_path": (["mask.png"], {"image_upload": True})}
            },
            "output": ["MASK"],
        },
        "Consumer": {
            "input": {"required": {"pixels": ("IMAGE",), "mask": ("MASK",)}},
            "output": [],
        },
    }
    definition_gateway = _DefinitionGateway(definitions)
    definition_service = WorkflowNodeDefinitionService(definition_gateway)
    staging_plan_service = InputAssetStagingPlanService(
        WorkflowGraphSectionService(),
        InputAssetFieldService(definition_service),
    )
    prompt = cast(JsonObject, graph["nodes"])

    result = ComfyAssetStagingService(
        stager=_FakeStager(),
        input_asset_staging_plan_service=staging_plan_service,
    ).stage_payload(
        workflow_payload=prompt,
        workflow_id="wf-direct",
        workflow_name="Direct",
        workflow=workflow,
    )

    assert result.failures == ()
    assert len(result.staged_assets) == 2
    staged_photo = cast(JsonObject, result.workflow_payload["10"])
    staged_stencil = cast(JsonObject, result.workflow_payload["11"])
    assert cast(JsonObject, staged_photo["inputs"])["photo_path"] == (
        "substitute/wf-direct/photo.png"
    )
    assert cast(JsonObject, staged_stencil["inputs"])["stencil_path"] == (
        "substitute/wf-direct/stencil.png"
    )


def test_mask_only_canvas_backing_surface_is_never_injected_or_staged(
    tmp_path: Path,
) -> None:
    """Synthetic canvas ownership must remain outside the authored Comfy prompt."""

    mask_path = tmp_path / "region-mask.png"
    mask_path.write_bytes(b"mask")
    nodes: JsonObject = {
        "mask": {
            "class_type": "StencilPicker",
            "inputs": {"stencil_path": str(mask_path)},
        },
        "region": {
            "class_type": "RegionalCondition",
            "inputs": {"mask": ["mask", 0]},
        },
        "root": {
            "class_type": "NoiseRoot",
            "inputs": {"width": 1024, "height": 768},
        },
        "sampler": {
            "class_type": "Sampler",
            "inputs": {
                "latent_image": ["root", 0],
                "positive": ["region", 0],
            },
        },
    }
    graph: JsonObject = {"nodes": nodes}
    workflow = WorkflowState(
        direct_workflow=DirectWorkflowState(
            source_path=tmp_path / "regional.json",
            source_workflow=graph,
            buffer=graph,
        )
    )
    definitions: dict[str, JsonObject] = {
        "StencilPicker": {
            "input": {
                "required": {
                    "stencil_path": (
                        ["region-mask.png"],
                        {"image_upload": True},
                    )
                }
            },
            "output": ["MASK"],
        },
        "RegionalCondition": {
            "input": {"required": {"mask": ("MASK",)}},
            "output": ["CONDITIONING"],
        },
        "NoiseRoot": {
            "input": {"required": {"width": ("INT",), "height": ("INT",)}},
            "output": ["LATENT"],
        },
        "Sampler": {
            "input": {
                "required": {
                    "latent_image": ("LATENT",),
                    "positive": ("CONDITIONING",),
                }
            },
            "output": ["LATENT"],
        },
    }
    definition_service = WorkflowNodeDefinitionService(_DefinitionGateway(definitions))
    staging_plan_service = InputAssetStagingPlanService(
        WorkflowGraphSectionService(),
        InputAssetFieldService(definition_service),
    )
    stager = _FakeStager()

    result = ComfyAssetStagingService(
        stager=stager,
        input_asset_staging_plan_service=staging_plan_service,
    ).stage_payload(
        workflow_payload=nodes,
        workflow_id="wf-regional",
        workflow_name="Regional",
        workflow=workflow,
    )

    assert set(result.workflow_payload) == set(nodes)
    assert not any(
        node_id.startswith("@synthetic/") for node_id in result.workflow_payload
    )
    assert [call[0] for call in stager.calls] == [mask_path]
    assert len(result.staged_assets) == 1
    assert result.failures == ()


def test_stage_payload_preserves_ordered_prompt_by_region_mask_batch(
    tmp_path: Path,
) -> None:
    """Ordered staging must change only the compiler-authored literal values."""

    mask_root = tmp_path / "Regional" / "masks"
    mask_root.mkdir(parents=True)
    first_path = mask_root / "first.png"
    second_path = mask_root / "second.png"
    first_path.write_bytes(b"first")
    second_path.write_bytes(b"second")
    graph: JsonObject = {
        "nodes": {
            "load_mask_batch": {
                "class_type": "SimpleSyrup.LoadMaskBatch",
                "inputs": {"image": ["first.png", "second.png"], "channel": "alpha"},
            },
            "consumer": {
                "class_type": "RegionalSampler",
                "inputs": {"region_masks": ["load_mask_batch", 0]},
            },
        }
    }
    workflow = WorkflowState(
        cubes={
            "Region": CubeState(
                cube_id="Prompt by Region.cube",
                version="3.2.0",
                alias="Region",
                original_cube=graph,
                buffer=graph,
            )
        },
        stack_order=["Region"],
    )
    definitions: dict[str, JsonObject] = {
        "SimpleSyrup.LoadMaskBatch": {
            "input": {
                "required": {
                    "image": ["LIST", {"image_upload": True, "allow_batch": True}],
                    "channel": ["LIST"],
                }
            },
            "output": ["MASK"],
        },
        "RegionalSampler": {
            "input": {"required": {"region_masks": ["MASK", {}]}},
            "output": ["LATENT"],
        },
    }
    definition_gateway = _DefinitionGateway(definitions)
    definition_service = WorkflowNodeDefinitionService(definition_gateway)
    scalar_stager = _FakeStager()
    stager = _FakeStager()
    service = ComfyAssetStagingService.with_projects_dir(
        stager=scalar_stager,
        ordered_stager=stager,
        projects_dir=tmp_path,
        input_asset_staging_plan_service=InputAssetStagingPlanService(
            WorkflowGraphSectionService(),
            InputAssetFieldService(definition_service),
        ),
    )
    payload: JsonObject = {
        "42": {
            "class_type": "SimpleSyrup.LoadMaskBatch",
            "inputs": {
                "image": {"__value__": ["first.png", "second.png"]},
                "channel": "alpha",
            },
            "_meta": {"title": "Region.load_mask_batch"},
        }
    }

    result = service.stage_payload(
        workflow_payload=payload,
        workflow_id="wf-regional",
        workflow_name="Regional",
        workflow=workflow,
    )

    staged_node = cast(JsonObject, result.workflow_payload["42"])
    staged_inputs = cast(JsonObject, staged_node["inputs"])
    assert set(result.workflow_payload) == {"42"}
    assert staged_node["class_type"] == "SimpleSyrup.LoadMaskBatch"
    assert staged_node["_meta"] == {"title": "Region.load_mask_batch"}
    assert staged_inputs == {
        "image": {
            "__value__": [
                "substitute/wf-regional/first.png",
                "substitute/wf-regional/second.png",
            ]
        },
        "channel": "alpha",
    }
    assert [call[0] for call in stager.calls] == [first_path, second_path]
    assert [call[3] for call in stager.calls] == [
        "SimpleSyrup.LoadMaskBatch",
        "SimpleSyrup.LoadMaskBatch",
    ]
    assert result.failures == ()
    assert scalar_stager.calls == []
    assert "SimpleSyrup.LoadMaskBatch" in definition_gateway.cached_calls


def test_stage_payload_resolves_nested_generation_mask_paths_from_project(
    tmp_path: Path,
) -> None:
    """Generated ordered masks should resolve beneath their project mask root."""

    mask_root = tmp_path / "Regional" / "masks"
    first_path = mask_root / ".generation" / "mask-a" / "1.png"
    second_path = mask_root / ".generation" / "mask-b" / "1.png"
    first_path.parent.mkdir(parents=True)
    second_path.parent.mkdir(parents=True)
    first_path.write_bytes(b"first")
    second_path.write_bytes(b"second")
    graph: JsonObject = {
        "nodes": {
            "load_mask_batch": {
                "class_type": "SimpleSyrup.LoadMaskBatch",
                "inputs": {
                    "image": [
                        ".generation/mask-a/1.png",
                        ".generation/mask-b/1.png",
                    ],
                    "channel": "red",
                },
            },
            "consumer": {
                "class_type": "RegionalSampler",
                "inputs": {"region_masks": ["load_mask_batch", 0]},
            },
        }
    }
    workflow = WorkflowState(
        cubes={
            "Region": CubeState(
                cube_id="Prompt by Region.cube",
                version="3.2.0",
                alias="Region",
                original_cube=graph,
                buffer=graph,
            )
        },
        stack_order=["Region"],
    )
    definitions: dict[str, JsonObject] = {
        "SimpleSyrup.LoadMaskBatch": {
            "input": {
                "required": {
                    "image": ["LIST", {"image_upload": True, "allow_batch": True}],
                    "channel": ["LIST"],
                }
            },
            "output": ["MASK"],
        },
        "RegionalSampler": {
            "input": {"required": {"region_masks": ["MASK", {}]}},
            "output": ["LATENT"],
        },
    }
    stager = _FakeStager()
    service = ComfyAssetStagingService.with_projects_dir(
        stager=stager,
        ordered_stager=stager,
        projects_dir=tmp_path,
        input_asset_staging_plan_service=InputAssetStagingPlanService(
            WorkflowGraphSectionService(),
            InputAssetFieldService(
                WorkflowNodeDefinitionService(_DefinitionGateway(definitions))
            ),
        ),
    )

    result = service.stage_payload(
        workflow_payload={
            "42": {
                "class_type": "SimpleSyrup.LoadMaskBatch",
                "inputs": {
                    "image": {
                        "__value__": [
                            ".generation/mask-a/1.png",
                            ".generation/mask-b/1.png",
                        ]
                    },
                    "channel": "red",
                },
                "_meta": {"title": "Region.load_mask_batch"},
            }
        },
        workflow_id="wf-regional",
        workflow_name="Regional",
        workflow=workflow,
    )

    assert result.failures == ()
    assert [call[0] for call in stager.calls] == [first_path, second_path]
