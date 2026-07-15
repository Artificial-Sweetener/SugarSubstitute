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

"""Expose application node-behavior services and runtime-state models."""

from __future__ import annotations

from .behavior_service import (
    NodeBehaviorRuntimeState,
    NodeBehaviorService,
)
from .field_classification import NodeFieldKind, classify_node_field
from .list_value_resolver import (
    ListValueResolution,
    extract_live_list_default,
    extract_live_list_options,
    is_choice_field_type,
    resolve_live_list_value,
    unresolved_choice_options_reason,
)
from .live_definition_authority import (
    LiveNodeDefinitionAuthority,
    LiveNodeDefinitionError,
    LiveNodeFieldDefinition,
    MissingLiveNodeDefinition,
)
from .model_backed_node_detector import ModelBackedNodeDetector
from .models import EditorBehaviorSnapshot, FieldValueSource, ResolvedFieldSpec
from .node_card_order import (
    node_title_for_order,
    order_node_cards,
    prompt_priority_nodes,
    wired_node_order,
)
from .node_definition_hydration_service import EditorNodeDefinitionHydrationService
from .node_definition_requirements import (
    NodeDefinitionRequirement,
    required_node_definition_classes_for_editor_projection,
    required_node_definition_requirements_for_editor_projection,
)
from substitute.domain.node_behavior.dimension_fields import (
    DimensionFieldPair,
    infer_dimension_field_pairs,
)
from substitute.domain.node_behavior import (
    ActivationDefault,
    ActivationSwitchRole,
    ActivationSwitchSource,
    CardBehavior,
    CardBehaviorPatch,
    CardDecision,
    CardMode,
    CollapseMode,
    EnabledSwitchPolicy,
    FieldBehavior,
    FieldBehaviorPatch,
    FieldPresentation,
    LabelMode,
    NodeBehaviorContext,
    NodeBehaviorPatch,
    NodeActivationOverride,
    NodeActivationPolicy,
    NodeDisplayDecision,
    NodeVisibilityOverride,
    OverrideBehavior,
    OverrideBehaviorPatch,
    OverridePinPolicy,
    PackageBehaviorPatch,
    PromptFieldBehavior,
    PromptFieldBehaviorPatch,
    PromptRole,
    ResolvedNodeBehavior,
    RevealMenuEntry,
    RevealMode,
    RowMode,
    TitleControl,
    VisibilityRule,
    compute_all_hidden_keys,
    host_node_behavior_patch,
    infer_model_patch_switch,
    infer_sampler_worker_node,
    resolve_node_behavior,
)

__all__ = [
    "ActivationDefault",
    "ActivationSwitchRole",
    "ActivationSwitchSource",
    "CardBehavior",
    "CardBehaviorPatch",
    "CardDecision",
    "CardMode",
    "CollapseMode",
    "DimensionFieldPair",
    "EnabledSwitchPolicy",
    "EditorBehaviorSnapshot",
    "EditorNodeDefinitionHydrationService",
    "extract_live_list_default",
    "extract_live_list_options",
    "FieldBehavior",
    "FieldBehaviorPatch",
    "FieldPresentation",
    "FieldValueSource",
    "LabelMode",
    "ListValueResolution",
    "LiveNodeDefinitionAuthority",
    "LiveNodeDefinitionError",
    "LiveNodeFieldDefinition",
    "MissingLiveNodeDefinition",
    "NodeBehaviorContext",
    "NodeBehaviorPatch",
    "NodeDefinitionRequirement",
    "NodeActivationOverride",
    "NodeActivationPolicy",
    "NodeDisplayDecision",
    "NodeVisibilityOverride",
    "NodeFieldKind",
    "OverrideBehavior",
    "OverrideBehaviorPatch",
    "OverridePinPolicy",
    "NodeBehaviorRuntimeState",
    "NodeBehaviorService",
    "node_title_for_order",
    "ModelBackedNodeDetector",
    "order_node_cards",
    "PackageBehaviorPatch",
    "prompt_priority_nodes",
    "PromptFieldBehavior",
    "PromptFieldBehaviorPatch",
    "PromptRole",
    "ResolvedNodeBehavior",
    "RevealMenuEntry",
    "RevealMode",
    "ResolvedFieldSpec",
    "RowMode",
    "resolve_live_list_value",
    "required_node_definition_classes_for_editor_projection",
    "required_node_definition_requirements_for_editor_projection",
    "unresolved_choice_options_reason",
    "classify_node_field",
    "TitleControl",
    "VisibilityRule",
    "compute_all_hidden_keys",
    "host_node_behavior_patch",
    "infer_dimension_field_pairs",
    "infer_model_patch_switch",
    "infer_sampler_worker_node",
    "resolve_node_behavior",
    "is_choice_field_type",
    "wired_node_order",
]
