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

"""Plan a mask-only regional fixture against isolated live Comfy metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, cast

from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.application.workflows.input_canvas_plan_service import (
    InputCanvasPlanService,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
)
from substitute.domain.workflow import InputCanvasSurfaceKind
from tests.real_comfy_direct_output_harness import ManagedComfyDirectOutputHarness


@dataclass(frozen=True, slots=True)
class RealComfyMaskOnlyCanvasResult:
    """Summarize the live-definition regional Input-canvas plan."""

    surface_count: int
    mask_binding_count: int
    width: int
    height: int
    batch_size: int
    authority_nodes: tuple[str, ...]


def run_real_comfy_mask_only_input_canvas_harness(
    repository_root: Path,
) -> RealComfyMaskOnlyCanvasResult:
    """Load the fixture with isolated live definitions and assert its safe plan."""

    repository_root = repository_root.resolve()
    fixture_path = (
        repository_root
        / "tests"
        / "fixtures"
        / "input_canvas"
        / "regional_mask_only_api.json"
    )
    graph = cast(
        Mapping[str, object],
        json.loads(fixture_path.read_text(encoding="utf-8")),
    )
    with ManagedComfyDirectOutputHarness(repository_root) as managed_comfy:
        definitions = managed_comfy.node_definitions()
        required_classes = {
            "LoadImageMask",
            "ConditioningSetMask",
            "EmptyLatentImage",
            "KSampler",
        }
        missing_classes = required_classes.difference(definitions)
        if missing_classes:
            raise AssertionError(
                f"Managed Comfy is missing required fixture classes: {sorted(missing_classes)}"
            )
        definition_service = WorkflowNodeDefinitionService()
        plan = InputCanvasPlanService(
            node_definition_service=definition_service,
            endpoint_service=InputAssetEndpointService(definition_service),
        ).build_plan(
            "direct",
            graph,
            node_definitions=definitions,
        )

    if len(plan.surfaces) != 1 or len(plan.mask_bindings) != 1:
        raise AssertionError(
            "Regional fixture did not resolve exactly one synthetic surface and mask"
        )
    surface = plan.surfaces[0]
    dimensions = surface.dimensions
    authority = surface.dimension_authority
    if (
        surface.kind is not InputCanvasSurfaceKind.SYNTHETIC
        or dimensions is None
        or authority is None
    ):
        raise AssertionError("Regional fixture did not resolve synthetic dimensions")
    nodes = graph.get("nodes")
    root = nodes.get("4") if isinstance(nodes, Mapping) else None
    inputs = root.get("inputs") if isinstance(root, Mapping) else None
    batch_size = inputs.get("batch_size") if isinstance(inputs, Mapping) else None
    if not isinstance(batch_size, int):
        raise AssertionError("Regional fixture batch size is unavailable")
    return RealComfyMaskOnlyCanvasResult(
        surface_count=len(plan.surfaces),
        mask_binding_count=len(plan.mask_bindings),
        width=dimensions.width,
        height=dimensions.height,
        batch_size=batch_size,
        authority_nodes=authority.node_names,
    )


if __name__ == "__main__":
    print(
        run_real_comfy_mask_only_input_canvas_harness(
            Path(__file__).resolve().parents[1]
        )
    )


__all__ = [
    "RealComfyMaskOnlyCanvasResult",
    "run_real_comfy_mask_only_input_canvas_harness",
]
