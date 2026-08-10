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

"""Verify workflow-owned Input canvas interaction applicability."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.application.workflows.input_canvas_interaction_profile_service import (
    InputCanvasInteractionProfileService,
)
from substitute.application.workflows.input_canvas_plan_service import (
    InputCanvasPlanService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
)
from substitute.domain.common import JsonObject
from substitute.domain.workflow import (
    CubeState,
    InputCanvasInteractionCapability,
    WorkflowState,
)


def test_authored_surface_grants_raster_analysis_source() -> None:
    """An exact authored image identity should authorize raster analysis."""

    workflow, image_id = _workflow_with_surface(authored=True)

    profile = _service().profile_for(workflow, image_id)

    assert profile.supports(InputCanvasInteractionCapability.RASTER_ANALYSIS_SOURCE)


def test_synthetic_surface_excludes_raster_analysis_source() -> None:
    """A synthetic mask canvas should not claim an underlying raster source."""

    workflow, image_id = _workflow_with_surface(authored=False)

    profile = _service().profile_for(workflow, image_id)

    assert not profile.supports(InputCanvasInteractionCapability.RASTER_ANALYSIS_SOURCE)


def test_missing_or_stale_surface_identity_fails_closed() -> None:
    """Absent workflow and stale canvas entries must expose no interactions."""

    workflow, image_id = _workflow_with_surface(authored=True)
    workflow.canvas.image_entries.clear()
    service = _service()

    assert service.profile_for(None, image_id).capabilities == frozenset()
    assert service.profile_for(workflow, image_id).capabilities == frozenset()
    assert service.profile_for(workflow, None).capabilities == frozenset()


def test_ambiguous_image_entry_identity_fails_closed() -> None:
    """One document image claimed by multiple inputs must not gain authority."""

    workflow, image_id = _workflow_with_surface(authored=True)
    workflow.canvas.bind_image("Authored:stale-second-owner", image_id)

    profile = _service().profile_for(workflow, image_id)

    assert profile.capabilities == frozenset()


def test_surface_planning_failure_clears_interaction_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transient planning failure must not retain a prior raster capability."""

    workflow, image_id = _workflow_with_surface(authored=True)
    plans, graphs = _authorities()
    service = InputCanvasInteractionProfileService(
        input_canvas_plan_service=plans,
        graph_section_service=graphs,
    )

    def fail_plan(_section_key: str, _graph: object) -> object:
        """Simulate unavailable graph-planning evidence."""

        raise RuntimeError("definition projection unavailable")

    monkeypatch.setattr(plans, "build_plan", fail_plan)

    assert service.profile_for(workflow, image_id).capabilities == frozenset()


def _service() -> InputCanvasInteractionProfileService:
    """Build the interaction resolver with production graph authorities."""

    plans, graphs = _authorities()
    return InputCanvasInteractionProfileService(
        input_canvas_plan_service=plans,
        graph_section_service=graphs,
    )


def _workflow_with_surface(*, authored: bool) -> tuple[WorkflowState, UUID]:
    """Build one workflow and bind its planned surface to a document image."""

    alias = "Authored" if authored else "Synthetic"
    nodes: dict[str, object]
    if authored:
        nodes = {
            "image": {
                "class_type": "LoadImage",
                "inputs": {"image": "source.png"},
            },
            "consumer": {
                "class_type": "PreviewImage",
                "inputs": {"images": ["image", 0]},
            },
        }
    else:
        nodes = {
            "mask": {
                "class_type": "LoadImageMask",
                "inputs": {"image": "mask.png"},
            },
            "latent": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": 768, "height": 1024, "batch_size": 1},
            },
            "region": {
                "class_type": "RegionalCondition",
                "inputs": {"mask": ["mask", 0]},
            },
            "consumer": {
                "class_type": "Sampler",
                "inputs": {
                    "positive": ["region", 0],
                    "latent_image": ["latent", 0],
                },
            },
        }
    cube = CubeState(
        cube_id=f"{alias}.cube",
        version="1",
        alias=alias,
        original_cube={},
        buffer={"nodes": nodes},
    )
    workflow = WorkflowState(cubes={alias: cube}, stack_order=[alias])
    plans, graphs = _authorities()
    graph = graphs.graph(workflow, alias)
    assert graph is not None
    plan = plans.build_plan(alias, graph)
    assert len(plan.surfaces) == 1
    image_id = uuid4()
    workflow.canvas.bind_image(plan.surfaces[0].input_key, image_id)
    return workflow, image_id


def _authorities() -> tuple[InputCanvasPlanService, WorkflowGraphSectionService]:
    """Build production graph and Input surface planning authorities."""

    definitions = WorkflowNodeDefinitionService(_DefinitionGateway())
    return (
        InputCanvasPlanService(
            node_definition_service=definitions,
            endpoint_service=InputAssetEndpointService(definitions),
        ),
        WorkflowGraphSectionService(),
    )


class _DefinitionGateway:
    """Provide deterministic graph definitions for interaction profiles."""

    _definitions: dict[str, JsonObject] = {
        "LoadImage": {
            "input": {
                "required": {
                    "image": [
                        "STRING",
                        {"image_upload": True, "image_folder": "input"},
                    ]
                }
            },
            "output": ["IMAGE"],
        },
        "PreviewImage": {
            "input": {"required": {"images": ["IMAGE", {}]}},
            "output": [],
        },
        "LoadImageMask": {
            "input": {
                "required": {
                    "image": [
                        "STRING",
                        {"image_upload": True, "image_folder": "input"},
                    ]
                }
            },
            "output": ["MASK"],
        },
        "RegionalCondition": {
            "input": {"required": {"mask": ["MASK", {}]}},
            "output": ["CONDITIONING"],
        },
        "EmptyLatentImage": {
            "input": {
                "required": {
                    "width": ["INT", {"min": 16, "step": 8}],
                    "height": ["INT", {"min": 16, "step": 8}],
                    "batch_size": ["INT", {}],
                }
            },
            "output": ["LATENT"],
        },
        "Sampler": {
            "input": {
                "required": {
                    "latent_image": ["LATENT", {}],
                    "positive": ["CONDITIONING", {}],
                }
            },
            "output": ["LATENT"],
        },
    }

    def get_node_definition(self, node_class: str) -> JsonObject:
        """Return one cached node definition."""

        return self._definitions.get(node_class, {})

    def get_required_node_definition(self, node_class: str) -> JsonObject:
        """Return one required node definition."""

        return self.get_node_definition(node_class)
