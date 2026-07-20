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

"""Expose typed node-behavior models, resolution helpers, and runtime engine APIs."""

from __future__ import annotations

from .defaults import (
    host_field_behavior_patch,
    host_node_behavior_patch,
    is_prompt_node_name,
)
from .engine import (
    EditorBehaviorContext,
    compute_card_decisions,
    compute_all_hidden_keys,
    compute_editor_behavior,
    compute_hidden_field_keys,
    compute_reveal_entries,
)
from .inference import (
    infer_model_patch_switch,
    infer_node_behavior_patch,
    infer_sampler_worker_node,
    multiline_string_input_keys,
    normalize_prompt_label,
    prompt_role_from_label,
)
from .models import (
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
    FieldLabelSource,
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
)
from .resolver import (
    merge_card_behavior_patches,
    merge_field_behavior_patches,
    merge_node_behavior_patches,
    resolve_node_behavior,
)
from .prompt_behavior_patch import prompt_node_behavior_patch
from .prompt_context_resolver import PromptGraphContextResolver
from .prompt_graph import (
    PromptAmbiguityReason,
    PromptDetectionResult,
    PromptEvidence,
    PromptEvidenceKind,
    PromptFieldLocator,
    PromptGraphContext,
    PromptRoleAmbiguity,
    PromptRoleDetection,
    PromptSinkLocator,
)
from .prompt_graph_analyzer import PromptGraphAnalyzer

__all__ = [
    "ActivationDefault",
    "ActivationSwitchRole",
    "ActivationSwitchSource",
    "CardBehavior",
    "CardBehaviorPatch",
    "CardDecision",
    "CardMode",
    "CollapseMode",
    "EditorBehaviorContext",
    "EnabledSwitchPolicy",
    "FieldBehavior",
    "FieldBehaviorPatch",
    "FieldLabelSource",
    "FieldPresentation",
    "LabelMode",
    "NodeBehaviorContext",
    "NodeBehaviorPatch",
    "NodeActivationOverride",
    "NodeActivationPolicy",
    "NodeDisplayDecision",
    "NodeVisibilityOverride",
    "OverrideBehavior",
    "OverrideBehaviorPatch",
    "OverridePinPolicy",
    "PackageBehaviorPatch",
    "PromptFieldBehavior",
    "PromptFieldBehaviorPatch",
    "PromptAmbiguityReason",
    "PromptDetectionResult",
    "PromptEvidence",
    "PromptEvidenceKind",
    "PromptFieldLocator",
    "PromptGraphContext",
    "PromptGraphContextResolver",
    "PromptGraphAnalyzer",
    "PromptRole",
    "PromptRoleAmbiguity",
    "PromptRoleDetection",
    "PromptSinkLocator",
    "ResolvedNodeBehavior",
    "RevealMenuEntry",
    "RevealMode",
    "RowMode",
    "TitleControl",
    "VisibilityRule",
    "compute_card_decisions",
    "compute_all_hidden_keys",
    "compute_editor_behavior",
    "compute_hidden_field_keys",
    "compute_reveal_entries",
    "host_field_behavior_patch",
    "host_node_behavior_patch",
    "infer_model_patch_switch",
    "infer_node_behavior_patch",
    "infer_sampler_worker_node",
    "multiline_string_input_keys",
    "normalize_prompt_label",
    "prompt_role_from_label",
    "prompt_node_behavior_patch",
    "is_prompt_node_name",
    "merge_card_behavior_patches",
    "merge_field_behavior_patches",
    "merge_node_behavior_patches",
    "resolve_node_behavior",
]
