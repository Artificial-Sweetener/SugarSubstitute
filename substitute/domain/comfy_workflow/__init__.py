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
from .models import DirectWorkflowState, NodeActivationStorage
from .node_classes import executable_node_classes
from .node_roles import WorkflowNodeExecutionRole
from .output_manifest import (
    AuthoredImageSink,
    ComfyImageOutputDiscovery,
    ComfyOutputSocket,
    DirectImageOutputSource,
    DirectWorkflowGenerationPlan,
    DirectWorkflowOutputManifest,
    is_terminal_image_output_sink,
)
from .workflow_converter import ComfyWorkflowConversionError, ComfyWorkflowConverter

__all__ = [
    "ComfyApiGraphBuildError",
    "ComfyApiGraphBuilder",
    "ComfyImageOutputDiscovery",
    "ComfyOutputSocket",
    "ComfyWorkflowConversionError",
    "ComfyWorkflowConverter",
    "AuthoredImageSink",
    "DirectImageOutputSource",
    "DirectWorkflowGenerationPlan",
    "DirectWorkflowOutputManifest",
    "DirectWorkflowState",
    "executable_node_classes",
    "NodeActivationStorage",
    "WorkflowNodeExecutionRole",
    "is_terminal_image_output_sink",
]
