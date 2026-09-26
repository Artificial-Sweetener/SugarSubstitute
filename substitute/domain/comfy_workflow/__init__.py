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

"""Expose direct Comfy workflow domain models and graph services."""

from .api_graph_builder import ComfyApiGraphBuildError, ComfyApiGraphBuilder
from .cube_analysis import CanonicalCubeGraphAnalysis
from .cube_reorder import apply_cached_cube_reorder
from .cube_projection import (
    CubeGraphInstance,
    CubeGraphProjection,
    CubeGraphSegment,
)
from .models import DirectWorkflowState, NodeActivationStorage, ProjectedCubeDocument
from .node_inventory import (
    PersistedNodepackHint,
    WorkflowNodeInventoryItem,
    workflow_node_inventory,
)
from .node_classes import executable_node_classes
from .node_roles import WorkflowNodeExecutionRole
from .output_manifest import (
    AuthoredOutputSink,
    ComfyOutputDiscovery,
    ComfyOutputSocket,
    DirectOutputSource,
    DirectWorkflowGenerationPlan,
    DirectWorkflowOutputManifest,
    is_terminal_output_sink,
)
from .workflow_converter import ComfyWorkflowConversionError, ComfyWorkflowConverter

__all__ = [
    "ComfyApiGraphBuildError",
    "ComfyApiGraphBuilder",
    "ComfyOutputDiscovery",
    "ComfyOutputSocket",
    "ComfyWorkflowConversionError",
    "ComfyWorkflowConverter",
    "CanonicalCubeGraphAnalysis",
    "apply_cached_cube_reorder",
    "CubeGraphInstance",
    "CubeGraphProjection",
    "CubeGraphSegment",
    "AuthoredOutputSink",
    "DirectOutputSource",
    "DirectWorkflowGenerationPlan",
    "DirectWorkflowOutputManifest",
    "DirectWorkflowState",
    "executable_node_classes",
    "NodeActivationStorage",
    "PersistedNodepackHint",
    "ProjectedCubeDocument",
    "WorkflowNodeExecutionRole",
    "WorkflowNodeInventoryItem",
    "workflow_node_inventory",
    "is_terminal_output_sink",
]
