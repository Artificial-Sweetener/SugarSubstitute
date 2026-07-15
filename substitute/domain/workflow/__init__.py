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

"""Expose domain workflow models and stack policy implementations."""

from __future__ import annotations

from substitute.domain.workflow.cube_contract_validator import (
    CubeContractError,
    validate_cube_contract,
)
from substitute.domain.workflow.canvas_models import (
    EditableMaskBinding,
    EditableMaskBindingIndex,
    WorkflowCanvasState,
)
from substitute.domain.workflow.canvas_session import (
    CanvasBoundSession,
    CanvasGenerationIdentity,
    CanvasKind,
    CanvasMutationAuthorization,
    CanvasRouteIdentity,
    CanvasSession,
    CanvasSessionBoundary,
    CanvasSessionRejectionReason,
    CanvasSessionRevision,
    CanvasSessionToken,
    CanvasWorkflowIdentity,
    InputCanvasSession,
    OutputCanvasSession,
)
from substitute.domain.workflow.asset_models import (
    ComfyInputAssetRef,
    LocalFileAssetRef,
    ProjectAssetRef,
    ProjectMaskAssetRef,
    WorkflowAssetKind,
    WorkflowAssetRef,
    workflow_asset_ref_authoring_value,
    workflow_asset_ref_from_json,
    workflow_asset_ref_to_json,
)
from substitute.domain.workflow.models import (
    CubeState,
    ImageMeta,
    OutputCompareSelection,
    OutputCompareState,
    OutputFocusMode,
    WorkflowState,
)
from substitute.domain.workflow.execution_projection import (
    WorkflowExecutionState,
    active_adjacent_alias_pairs,
    active_cube_aliases,
    bypassed_cube_aliases,
    is_cube_bypassed,
)
from substitute.domain.workflow.policies import StackManager

__all__ = [
    "active_adjacent_alias_pairs",
    "active_cube_aliases",
    "bypassed_cube_aliases",
    "CanvasGenerationIdentity",
    "CanvasBoundSession",
    "CanvasKind",
    "CanvasMutationAuthorization",
    "CanvasRouteIdentity",
    "CanvasSession",
    "CanvasSessionBoundary",
    "CanvasSessionRejectionReason",
    "CanvasSessionRevision",
    "CanvasSessionToken",
    "CanvasWorkflowIdentity",
    "ComfyInputAssetRef",
    "CubeContractError",
    "CubeState",
    "EditableMaskBinding",
    "EditableMaskBindingIndex",
    "ImageMeta",
    "InputCanvasSession",
    "LocalFileAssetRef",
    "OutputCompareSelection",
    "OutputCompareState",
    "OutputCanvasSession",
    "OutputFocusMode",
    "ProjectAssetRef",
    "ProjectMaskAssetRef",
    "StackManager",
    "WorkflowAssetKind",
    "WorkflowAssetRef",
    "WorkflowCanvasState",
    "WorkflowExecutionState",
    "WorkflowState",
    "is_cube_bypassed",
    "validate_cube_contract",
    "workflow_asset_ref_authoring_value",
    "workflow_asset_ref_from_json",
    "workflow_asset_ref_to_json",
]
