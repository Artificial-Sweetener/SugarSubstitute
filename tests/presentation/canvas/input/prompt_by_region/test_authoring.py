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
    CubeDefinitionRecord,
)
from substitute.application.workflows import (
    CanvasIoService,
    InputCanvasPlanService,
    WorkflowAssetService,
)
from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.application.workflows.canvas_route_projector_port import (
    create_canvas_session_boundary,
)
from substitute.application.workflows.input_canvas_state_composition import (
    compose_input_canvas_state,
)
from substitute.application.workflows.input_canvas_binding_service import (
    InputCanvasBindingService,
)
from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.application.workflows.input_asset_field_service import (
    InputAssetFieldService,
)
from substitute.application.workflows.input_image_materialization_service import (
    InputImageMaterializationService,
)
from substitute.application.workflows.input_mask_binding_materialization_service import (
    InputMaskBindingMaterializationService,
)
from substitute.application.workflows.input_mask_materialization_service import (
    InputMaskMaterializationService,
)
from substitute.application.workflows.input_section_materialization_service import (
    InputSectionMaterializationService,
)
from substitute.application.workflows.ordered_mask_materialization_service import (
    OrderedMaskMaterializationService,
)
from substitute.application.workflows.ordered_mask_region_authoring_service import (
    OrderedMaskRegionAuthoringService,
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
from substitute.application.workflows.synthetic_input_canvas_surface_service import (
    SyntheticInputCanvasSurfaceService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
)
from substitute.domain.common import JsonObject
from substitute.domain.cube_library import CubeSourceMetadata
from substitute.domain.workflow import ProjectMaskAssetRef, WorkflowState
from substitute.domain.workspace_snapshot import (
    workflow_state_from_json,
    workflow_state_to_json,
)
from substitute.infrastructure.persistence import QtImageStore
from substitute.presentation.canvas.input.input_canvas_view import InputCanvas
from tests.presentation.canvas.input.prompt_by_region.integration_fakes import (
    CUBE_ALIAS as _ALIAS,
    CUBE_ID as _CUBE_ID,
    CubeRepository as _CubeRepository,
    DefinitionGateway as _DefinitionGateway,
    Stager as _Stager,
)
from tests.support.qt.lifecycle import destroy_qt_object


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
    input_state = compose_input_canvas_state(
        document=canvas.document,
        route_projector=canvas.route_projector,
        session_boundary=route_boundary,
        image_registry=CanvasImageRegistry(),
    )
    definition_service = WorkflowNodeDefinitionService(_DefinitionGateway(definitions))
    graph_sections = WorkflowGraphSectionService()
    endpoint_service = InputAssetEndpointService(definition_service)
    plan_service = InputCanvasPlanService(
        node_definition_service=definition_service,
        endpoint_service=endpoint_service,
    )
    bindings = InputCanvasBindingService(
        plans=plan_service,
        graph_sections=graph_sections,
    )
    canvas_io = CanvasIoService(image_repository=QtImageStore())
    workflow_assets = WorkflowAssetService(graph_sections)
    scalar_masks = InputMaskMaterializationService(
        input_masks=input_state.masks,
        canvas_io_service=canvas_io,
        workflow_asset_service=workflow_assets,
        graph_section_service=graph_sections,
    )
    ordered_masks = OrderedMaskMaterializationService(
        input_masks=input_state.masks,
        mask_visuals=input_state.mask_visuals,
        canvas_io_service=canvas_io,
        graph_section_service=graph_sections,
    )
    mask_materialization = InputMaskBindingMaterializationService(
        scalar_service=scalar_masks,
        ordered_service=ordered_masks,
    )
    synthetic_surfaces = SyntheticInputCanvasSurfaceService(
        input_images=input_state.images,
        input_cleanup=input_state.cleanup,
        canvas_io_service=canvas_io,
    )
    image_materialization = InputImageMaterializationService(
        bindings=bindings,
        images=input_state.images,
        canvas_io=canvas_io,
        mask_materialization=mask_materialization,
        workflow_assets=workflow_assets,
        graph_sections=graph_sections,
    )
    section_materialization = InputSectionMaterializationService(
        bindings=bindings,
        images=image_materialization,
        mask_materialization=mask_materialization,
        synthetic_surfaces=synthetic_surfaces,
        graph_sections=graph_sections,
    )
    region_authoring = OrderedMaskRegionAuthoringService(
        binding_resolver=bindings.binding_for_mask,
        ensure_section_materialized=lambda authored_workflow, workflow_id, section_key, workflow_name, projects_dir: (
            section_materialization.materialize_loaded_section(
                workflows={workflow_id: authored_workflow},
                workflow_id=workflow_id,
                section_key=section_key,
                workflow_name=workflow_name,
                projects_dir=projects_dir,
            )
        ),
        input_routes=input_state.routes,
        input_images=input_state.images,
        input_masks=input_state.masks,
        canvas_io_service=canvas_io,
        materialization_service=ordered_masks,
        graph_values=OrderedMaskGraphValueService(graph_sections),
    )

    results = section_materialization.materialize_loaded_section(
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
    image_path = input_state.images.path_for(image_id)
    assert image_path is not None
    assert QtImageStore().image_dimensions(image_path) == (960, 1344)
    assert canvas.document.image_has_masks(image_id)

    second_mask_id = region_authoring.add_region(
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
            graph_sections,
            InputAssetFieldService(definition_service),
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

    assert region_authoring.remove_region(
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
