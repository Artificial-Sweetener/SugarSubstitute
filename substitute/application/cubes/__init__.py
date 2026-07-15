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

"""Application-level cube orchestration services."""

from __future__ import annotations

from substitute.application.cubes.cube_load_service import (
    CubeLoadService,
    LoadedCubeDefinition,
    LoadedCubeRuntime,
)
from substitute.application.cubes.cube_instance_state_transfer import (
    CubeInstanceStateTransferReport,
    CubeInstanceStateTransferResult,
    CubeInstanceStateTransferService,
    structural_patch_keys,
)
from substitute.application.cubes.persisted_input_overlay import (
    PersistedInputOverlayResult,
    overlay_persisted_node_inputs,
)
from substitute.application.cubes.cube_alias_display import (
    CubeAliasDisplayParts,
    cube_alias_body,
    split_cube_alias_prefix,
)
from substitute.application.cubes.cube_mask_binding_service import (
    CubeMaskBindingService,
)
from substitute.application.cubes.cube_picker_models import (
    CubePickerClassification,
    CubePickerEntry,
    CubePickerModelRoleSection,
    CubePickerPackGroup,
    CubePickerRole,
    CubePickerRoleSection,
    CubePickerSection,
    CubePickerViewMode,
    CubeSearchTarget,
    CubeSearchTargetKind,
    CubeSearchTerm,
    build_cube_picker_entries,
    build_cube_picker_model_role_sections,
    build_cube_picker_sections,
    build_cube_search_targets,
    classify_cube_boundaries,
    classify_cube_document,
)
from substitute.application.cubes.cube_stack_alias_planner import (
    CubeStackAliasPlan,
    CubeStackPlannedAlias,
    plan_cube_stack_aliases,
)
from substitute.application.cubes.cube_stack_draft_models import (
    CubeStackDraft,
    CubeStackDraftEntry,
    CubeStackDraftEntrySource,
    CubeStackDraftResult,
    cube_stack_draft,
    cube_stack_draft_entry_from_record,
    cube_stack_draft_from_workflow,
    cube_stack_draft_result,
)
from substitute.application.cubes.cube_stack_service import (
    CubeRenameResolution,
    CubeStackService,
)
from substitute.application.cubes.cube_state_duplicator import CubeStateDuplicator
from substitute.application.cubes.cube_stack_tooltip import (
    CubeStackTooltipMetadata,
    build_cube_stack_tooltip_for_state,
    build_cube_stack_tooltip_text,
    cube_stack_tooltip_metadata_from_state,
)
from substitute.application.cubes.cube_tab_presentation import (
    CubeTabPresentation,
    build_cube_tab_presentation,
)
from substitute.application.cubes.cube_workflow_add_service import (
    CubeAddResult,
    CubeWorkflowAddService,
)

__all__ = [
    "CubeAddResult",
    "CubeAliasDisplayParts",
    "CubeMaskBindingService",
    "CubeLoadService",
    "CubeInstanceStateTransferReport",
    "CubeInstanceStateTransferResult",
    "CubeInstanceStateTransferService",
    "CubePickerClassification",
    "CubeRenameResolution",
    "CubePickerEntry",
    "CubePickerModelRoleSection",
    "CubePickerPackGroup",
    "CubePickerRole",
    "CubePickerRoleSection",
    "CubePickerSection",
    "CubePickerViewMode",
    "CubeSearchTarget",
    "CubeSearchTargetKind",
    "CubeSearchTerm",
    "CubeStackService",
    "CubeStateDuplicator",
    "CubeStackAliasPlan",
    "CubeStackDraft",
    "CubeStackDraftEntry",
    "CubeStackDraftEntrySource",
    "CubeStackDraftResult",
    "CubeStackPlannedAlias",
    "CubeStackTooltipMetadata",
    "CubeTabPresentation",
    "CubeWorkflowAddService",
    "LoadedCubeDefinition",
    "LoadedCubeRuntime",
    "PersistedInputOverlayResult",
    "build_cube_picker_entries",
    "build_cube_picker_model_role_sections",
    "build_cube_picker_sections",
    "build_cube_search_targets",
    "build_cube_stack_tooltip_for_state",
    "build_cube_stack_tooltip_text",
    "build_cube_tab_presentation",
    "classify_cube_boundaries",
    "classify_cube_document",
    "cube_stack_draft",
    "cube_stack_draft_entry_from_record",
    "cube_stack_draft_from_workflow",
    "cube_stack_draft_result",
    "cube_stack_tooltip_metadata_from_state",
    "cube_alias_body",
    "plan_cube_stack_aliases",
    "overlay_persisted_node_inputs",
    "split_cube_alias_prefix",
    "structural_patch_keys",
]
