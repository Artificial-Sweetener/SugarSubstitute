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

"""Verify Prompt by Region authoring through the production service stack."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

from PySide6.QtWidgets import QApplication
from cutecanvas import ExecutionRuntime
import pytest

from substitute.application.cubes import CubeLoadService
from substitute.application.generation import ComfyAssetStagingService
from substitute.application.generation.input_asset_staging_plan_service import (
    InputAssetStagingPlanService,
)
from substitute.application.ports.cube_repository import (
    CubeCatalogRecord,
    CubeDefinitionRecord,
)
from substitute.application.workflows import (
    CanvasIoService,
    InputCanvasPlanService,
    InputCanvasStateService,
    WorkflowInputCanvasService,
)
from substitute.application.workflows.canvas_route_projector_port import (
    create_canvas_session_boundary,
)
from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.application.workflows.regional_prompt_validation_service import (
    RegionalPromptValidationService,
)
from substitute.application.workflows.ordered_mask_graph_value_service import (
    OrderedMaskGraphValueService,
)
from substitute.application.workflows.restored_ordered_mask_collection_service import (
    RestoredOrderedMaskCollectionService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
)
from substitute.domain.common import JsonObject
from substitute.domain.cube_library import CubeSourceMetadata
from substitute.domain.generation import ComfyStagedAsset
from substitute.domain.workflow import ProjectMaskAssetRef, WorkflowState
from substitute.domain.workspace_snapshot import (
    workflow_state_from_json,
    workflow_state_to_json,
)
from substitute.infrastructure.persistence import QtImageStore
from substitute.presentation.canvas.input.input_canvas_view import InputCanvas
from tests.support.qt.lifecycle import destroy_qt_object

_CUBE_ID = "Artificial-Sweetener/Base-Cubes/Anima/Prompt by Region.cube"
_ALIAS = "Anima/Prompt by Region"


class _CubeRepository:
    """Return one canonical Prompt by Region cube document."""

    def __init__(self, record: CubeDefinitionRecord) -> None:
        """Store the only available cube definition."""

        self._record = record

    def load_cube(self, cube_id: str) -> CubeDefinitionRecord:
        """Return the requested current cube definition."""

        assert cube_id == _CUBE_ID
        return self._record

    def load_cube_version(self, cube_id: str, version: str) -> CubeDefinitionRecord:
        """Return the requested persisted cube version."""

        assert (cube_id, version) == (_CUBE_ID, "3.2.0")
        return self._record

    def list_cube_versions(self, cube_id: str) -> tuple[str, ...]:
        """Return the single fixture version."""

        assert cube_id == _CUBE_ID
        return ("3.2.0",)

    def prewarm_cube_version(self, cube_id: str, version: str) -> bool:
        """Accept best-effort warming for the available fixture version."""

        return (cube_id, version) == (_CUBE_ID, "3.2.0")

    def list_available_cubes(self) -> list[CubeCatalogRecord]:
        """Return the single fixture catalog entry."""

        return [
            CubeCatalogRecord(
                cube_id=_CUBE_ID,
                version="3.2.0",
                display_name="Prompt by Region",
            )
        ]


class _DefinitionGateway:
    """Expose exact cube-owned node definitions to graph services."""

    def __init__(self, definitions: Mapping[str, JsonObject]) -> None:
        """Store node definitions by class type."""

        self._definitions = definitions

    def get_node_definition(self, node_class: str) -> JsonObject:
        """Return a definition or an empty mapping for unknown classes."""

        return self._definitions.get(node_class, {})

    def get_required_node_definition(self, node_class: str) -> JsonObject:
        """Return a required definition through the same fixture boundary."""

        return self.get_node_definition(node_class)


class _Stager:
    """Record exact ordered files crossing the Comfy upload boundary."""

    def __init__(self) -> None:
        """Initialize empty staging history."""

        self.paths: list[Path] = []

    def stage_file_for_load_image(
        self,
        *,
        source_path: Path,
        target_subfolder: str,
        content_hash: str,
        node_class: str,
    ) -> ComfyStagedAsset:
        """Return one deterministic execution value for an existing mask file."""

        assert content_hash
        assert node_class == "SimpleSyrup.LoadMaskBatch"
        self.paths.append(source_path)
        return ComfyStagedAsset(
            source_path=source_path,
            execution_value=f"{target_subfolder}/{source_path.name}",
            operation="uploaded",
        )


def test_prompt_by_region_load_author_restore_and_stage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    execution_runtime: ExecutionRuntime,
) -> None:
    """A loaded cube should author latent-sized regions and ordered SEP prompts."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM", "1")
    application = QApplication.instance() or QApplication([])
    definitions = _definitions()
    record = CubeDefinitionRecord(
        cube_id=_CUBE_ID,
        version="3.2.0",
        display_name="Prompt by Region",
        graph=_cube_document(definitions),
        content_hash="sha256:prompt-by-region-integration",
        source=CubeSourceMetadata(kind="local", path="Prompt by Region.cube"),
        artifact_label="Prompt by Region",
        local_path=tmp_path / "Prompt by Region.cube",
    )
    runtime = CubeLoadService(_CubeRepository(record)).build_loaded_cube_runtime(
        _CUBE_ID,
        _ALIAS,
        buffer_patch=None,
        runtime_state=None,
    )
    workflow = WorkflowState(
        cubes={_ALIAS: runtime.cube_state},
        stack_order=[_ALIAS],
    )
    route_boundary = create_canvas_session_boundary()
    canvas = InputCanvas(
        execution_runtime=execution_runtime,
        route_session_boundary=route_boundary,
    )
    canvas.show()
    state_service = InputCanvasStateService(
        input_document=canvas.document,
        input_route_projector=canvas.route_projector,
        canvas_session_boundary=route_boundary,
    )
    definition_service = WorkflowNodeDefinitionService(_DefinitionGateway(definitions))
    graph_sections = WorkflowGraphSectionService()
    endpoint_service = InputAssetEndpointService(definition_service)
    plan_service = InputCanvasPlanService(
        node_definition_service=definition_service,
        endpoint_service=endpoint_service,
    )
    workflow_service = WorkflowInputCanvasService(
        input_canvas_plan_service=plan_service,
        input_canvas_state_service=state_service,
        canvas_io_service=CanvasIoService(image_repository=QtImageStore()),
        graph_section_service=graph_sections,
    )

    results = workflow_service.materialize_loaded_section(
        workflows={"workflow": workflow},
        workflow_id="workflow",
        section_key=_ALIAS,
        workflow_name="Regional Recipe",
        projects_dir=tmp_path,
    )
    application.processEvents()

    assert len(results) == 1
    collection = workflow.canvas.regional_mask_collection((_ALIAS, "load_mask_batch"))
    assert collection is not None
    assert len(collection.entries) == 1
    image_id = collection.entries[0].image_id
    image_path = state_service.input_image_path(image_id)
    assert image_path is not None
    assert QtImageStore().image_dimensions(image_path) == (960, 1344)
    assert canvas.document.image_has_masks(image_id)

    second_mask_id = workflow_service.add_ordered_mask_region(
        workflow=workflow,
        workflow_id="workflow",
        section_key=_ALIAS,
        node_name="load_mask_batch",
        workflow_name="Regional Recipe",
        projects_dir=tmp_path,
    )
    graph_sections.set_input_value(
        workflow,
        section_key=_ALIAS,
        node_name="positive_prompt",
        field_key="value",
        value="global prompt\n[SEP|Foreground]\nfirst region\n[SEP]\nsecond region",
    )

    assert second_mask_id is not None
    assert RegionalPromptValidationService(graph_sections).validate(workflow) == ()
    collection = workflow.canvas.regional_mask_collection((_ALIAS, "load_mask_batch"))
    assert collection is not None
    before_region_ids = [entry.region_id for entry in collection.entries]
    before_mask_ids = [entry.mask_id for entry in collection.entries]
    assert all(
        isinstance(entry.asset_ref, ProjectMaskAssetRef) for entry in collection.entries
    )
    before_paths = [
        cast(ProjectMaskAssetRef, entry.asset_ref).relative_path
        for entry in collection.entries
    ]

    restored = workflow_state_from_json(workflow_state_to_json(workflow))
    restored_collection = restored.canvas.regional_mask_collection(
        (_ALIAS, "load_mask_batch")
    )
    assert restored_collection is not None
    assert [
        entry.region_id for entry in restored_collection.entries
    ] == before_region_ids
    assert [entry.mask_id for entry in restored_collection.entries] == before_mask_ids
    restored_graph = graph_sections.graph(restored, _ALIAS)
    assert restored_graph is not None
    restored_nodes = cast(dict[str, object], restored_graph["nodes"])
    restored_prompt = cast(dict[str, object], restored_nodes["positive_prompt"])
    restored_prompt_inputs = cast(dict[str, object], restored_prompt["inputs"])
    assert restored_prompt_inputs["value"] == (
        "global prompt\n[SEP|Foreground]\nfirst region\n[SEP]\nsecond region"
    )
    graph_sections.set_input_value(
        restored,
        section_key=_ALIAS,
        node_name="load_mask_batch",
        field_key="image",
        value="stale-single-mask.png",
    )
    repaired = RestoredOrderedMaskCollectionService(
        endpoint_service=endpoint_service,
        graph_sections=graph_sections,
        graph_values=OrderedMaskGraphValueService(graph_sections),
    ).reconcile({"workflow": restored})

    assert repaired == 1
    assert (
        graph_sections.input_value(
            restored,
            section_key=_ALIAS,
            node_name="load_mask_batch",
            field_key="image",
        )
        == before_paths
    )

    stager = _Stager()
    staging_service = ComfyAssetStagingService.with_projects_dir(
        stager=stager,
        projects_dir=tmp_path,
        input_asset_staging_plan_service=InputAssetStagingPlanService(
            InputAssetEndpointService(definition_service),
            graph_sections,
        ),
    )
    staging = staging_service.stage_payload(
        workflow_payload={
            "42": {
                "class_type": "SimpleSyrup.LoadMaskBatch",
                "inputs": {
                    "image": {"__value__": before_paths},
                    "channel": "alpha",
                },
                "_meta": {"title": f"{_ALIAS}.load_mask_batch"},
            }
        },
        workflow_id="workflow",
        workflow_name="Regional Recipe",
        workflow=restored,
    )

    assert staging.failures == ()
    assert [path.name for path in stager.paths] == before_paths
    staged_node = cast(JsonObject, staging.workflow_payload["42"])
    staged_inputs = cast(JsonObject, staged_node["inputs"])
    assert set(staging.workflow_payload) == {"42"}
    assert staged_node["class_type"] == "SimpleSyrup.LoadMaskBatch"
    assert staged_inputs == {
        "image": {
            "__value__": [f"substitute/workflow/{path}" for path in before_paths]
        },
        "channel": "alpha",
    }

    assert workflow_service.remove_ordered_mask_region(
        workflow=workflow,
        workflow_id="workflow",
        section_key=_ALIAS,
        node_name="load_mask_batch",
        region_index=0,
    )
    remaining = workflow.canvas.regional_mask_collection((_ALIAS, "load_mask_batch"))
    assert remaining is not None
    assert [entry.mask_id for entry in remaining.entries] == [second_mask_id]
    assert graph_sections.input_value(
        workflow,
        section_key=_ALIAS,
        node_name="load_mask_batch",
        field_key="image",
    ) == [before_paths[1]]
    assert (
        canvas.document.generation_capture.capture(
            image_ids=(image_id,),
            mask_ids=workflow.canvas.mask_ids(),
        )
        is not None
    )
    canvas.close()
    destroy_qt_object(canvas)


def _cube_document(definitions: dict[str, JsonObject]) -> JsonObject:
    """Return the canonical production-shaped regional cube document."""

    return {
        "cube_id": _CUBE_ID,
        "version": "3.2.0",
        "implementation": {
            "nodes": {
                "ksampler": {
                    "class_type": "SimpleSyrup.KSamplerPromptByRegion",
                    "inputs": {
                        "positive": ["schedule_encode_prompts", 1],
                        "negative": ["schedule_encode_prompts", 2],
                        "region_masks": ["load_mask_batch", 0],
                        "latent_image": ["latent_dimensions", 0],
                    },
                },
                "latent_dimensions": {
                    "class_type": "EmptyLatentImage",
                    "inputs": {},
                },
                "load_mask_batch": {
                    "class_type": "SimpleSyrup.LoadMaskBatch",
                    "inputs": {},
                },
                "positive_prompt": {
                    "class_type": "PrimitiveStringMultiline",
                    "inputs": {},
                },
                "negative_prompt": {
                    "class_type": "PrimitiveStringMultiline",
                    "inputs": {},
                },
                "schedule_encode_prompts": {
                    "class_type": (
                        "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl"
                    ),
                    "inputs": {
                        "positive_prompt": ["positive_prompt", 0],
                        "negative_prompt": ["negative_prompt", 0],
                    },
                },
            },
            "inputs": {},
            "outputs": {"output.latent": ["ksampler", 0]},
            "layout": {},
            "definitions": definitions,
            "subgraphs": [],
        },
        "surface": {
            "default_flavor_id": "default",
            "controls": [
                _control("latent_dimensions", "width", "number"),
                _control("latent_dimensions", "height", "number"),
                _control("latent_dimensions", "batch_size", "number"),
                _control("load_mask_batch", "image", "object"),
                _control("load_mask_batch", "channel", "string"),
                _control("positive_prompt", "value", "string"),
                _control("negative_prompt", "value", "string"),
            ],
        },
        "flavors": {
            "authored": [
                {
                    "id": "default",
                    "name": "Default",
                    "values": {
                        "latent_dimensions.width": 960,
                        "latent_dimensions.height": 1344,
                        "latent_dimensions.batch_size": 1,
                        "load_mask_batch.channel": "alpha",
                        "positive_prompt.value": "",
                        "negative_prompt.value": "",
                    },
                }
            ]
        },
    }


def _control(symbol: str, input_name: str, value_type: str) -> JsonObject:
    """Return one canonical cube surface control."""

    class_types = {
        "latent_dimensions": "EmptyLatentImage",
        "load_mask_batch": "SimpleSyrup.LoadMaskBatch",
        "positive_prompt": "PrimitiveStringMultiline",
        "negative_prompt": "PrimitiveStringMultiline",
    }
    return {
        "control_id": f"{symbol}.{input_name}",
        "symbol": symbol,
        "input_name": input_name,
        "label": input_name,
        "class_type": class_types[symbol],
        "value_type": value_type,
    }


def _definitions() -> dict[str, JsonObject]:
    """Return graph semantics needed by canvas planning and staging."""

    return {
        "SimpleSyrup.LoadMaskBatch": {
            "input": {
                "required": {
                    "image": ["LIST"],
                    "channel": ["LIST"],
                }
            },
            "output": ["MASK"],
        },
        "EmptyLatentImage": {
            "input": {
                "required": {
                    "width": ["INT", {"default": 512}],
                    "height": ["INT", {"default": 512}],
                    "batch_size": ["INT", {"default": 1}],
                }
            },
            "output": ["LATENT"],
        },
        "PrimitiveStringMultiline": {
            "input": {"required": {"value": ["STRING", {"multiline": True}]}},
            "output": ["STRING"],
        },
        "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl": {
            "input": {
                "required": {
                    "positive_prompt": ["STRING", {}],
                    "negative_prompt": ["STRING", {}],
                }
            },
            "output": ["MODEL", "CONDITIONING", "CONDITIONING"],
        },
        "SimpleSyrup.KSamplerPromptByRegion": {
            "input": {
                "required": {
                    "positive": ["CONDITIONING", {}],
                    "negative": ["CONDITIONING", {}],
                    "region_masks": ["MASK", {}],
                    "latent_image": ["LATENT", {}],
                }
            },
            "output": ["LATENT"],
        },
    }


__all__ = []
