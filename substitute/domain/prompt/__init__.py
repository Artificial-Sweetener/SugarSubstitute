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

"""Expose prompt-domain models, parsing, serialization, and mutations."""

from __future__ import annotations

from .models import (
    EmphasisSpan,
    LoraSpan,
    PromptDocument,
    PromptMutationResult,
    PromptSegment,
    SourceRange,
    SyntaxSpan,
    WildcardSpan,
)
from .wildcard_models import (
    PromptWildcardCsvSource,
    PromptWildcardPlaceholder,
    PromptWildcardReplacementDetail,
    PromptWildcardResolution,
    PromptWildcardTextSource,
)
from .wildcard_syntax import (
    PromptWildcardActivatorStyle,
    PromptWildcardDelimiter,
    PromptWildcardSyntaxProfile,
    validate_custom_wildcard_delimiters,
)
from .features import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
    PromptFeatureDecision,
    PromptFeatureDisabledReason,
)
from .operations import (
    adjust_lora_weight,
    decrease_emphasis,
    increase_emphasis,
    reorder_segments,
    replace_span_content,
    set_emphasis_weight,
    set_lora_weight,
    unwrap_neutral_emphasis,
)
from .preferences import (
    PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
    PromptEditorPreferences,
    PromptWheelAdjustmentMode,
)
from .parser import parse_prompt_document
from .scenes import (
    PROMPT_SCENE_MARKER,
    PromptSceneBlock,
    PromptSceneDocument,
    PromptSceneMarker,
    materialize_scene_prompt,
    normalize_scene_title,
    parse_prompt_scene_document,
    scene_block_at_source_position,
)
from .reorder_chips import (
    PromptReorderChip,
    PromptReorderEnvelope,
    PromptReorderSerialization,
    build_reorder_chips,
    build_reorder_state_from_chips,
    serialize_reorder_chip,
    serialize_reorder_state_for_chips,
)
from .reorder_layout import (
    PromptDerivedGap,
    PromptDerivedRow,
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptReorderDropTarget,
    PromptReorderState,
    apply_blank_line_drop_target_to_state,
    apply_drop_target_to_state,
    apply_line_drop_target_to_state,
    apply_reorder_drop_target,
    blank_line_drop_offsets,
    build_base_drag_state,
    build_reorder_state,
    derive_rows_and_gaps,
    serialize_reorder_state,
    split_gap_for_blank_line_insert,
)
from .serializer import (
    normalize_reorder_separator_text,
    serialize_prompt_document,
    serialize_segments,
)
from .syntax import SyntaxKind, WildcardForm
from .weight_formatting import PROMPT_WEIGHT_PRECISION, format_prompt_weight
from .weight_normalization import PromptWeightNormalization, normalize_prompt_weights

__all__ = [
    "EmphasisSpan",
    "PromptDerivedGap",
    "PromptDerivedRow",
    "PromptGapBlankLineDropTarget",
    "PromptLineDropTarget",
    "PromptWeightNormalization",
    "LoraSpan",
    "PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION",
    "PROMPT_SCENE_MARKER",
    "PromptReorderDropTarget",
    "PromptReorderState",
    "PromptDocument",
    "PromptEditorFeature",
    "PromptEditorFeatureProfile",
    "PromptEditorPreferences",
    "PromptWheelAdjustmentMode",
    "PromptFeatureDecision",
    "PromptFeatureDisabledReason",
    "PromptMutationResult",
    "PromptSceneBlock",
    "PromptSceneDocument",
    "PromptSceneMarker",
    "PromptReorderChip",
    "PromptReorderEnvelope",
    "PromptReorderSerialization",
    "PromptSegment",
    "PromptWildcardActivatorStyle",
    "PromptWildcardCsvSource",
    "PromptWildcardDelimiter",
    "PromptWildcardPlaceholder",
    "PromptWildcardReplacementDetail",
    "PromptWildcardResolution",
    "PromptWildcardSyntaxProfile",
    "PromptWildcardTextSource",
    "PROMPT_WEIGHT_PRECISION",
    "SourceRange",
    "SyntaxKind",
    "SyntaxSpan",
    "WildcardForm",
    "WildcardSpan",
    "apply_blank_line_drop_target_to_state",
    "apply_drop_target_to_state",
    "apply_line_drop_target_to_state",
    "apply_reorder_drop_target",
    "adjust_lora_weight",
    "blank_line_drop_offsets",
    "build_base_drag_state",
    "build_reorder_chips",
    "build_reorder_state",
    "build_reorder_state_from_chips",
    "decrease_emphasis",
    "derive_rows_and_gaps",
    "format_prompt_weight",
    "increase_emphasis",
    "normalize_reorder_separator_text",
    "normalize_prompt_weights",
    "materialize_scene_prompt",
    "normalize_scene_title",
    "parse_prompt_document",
    "parse_prompt_scene_document",
    "reorder_segments",
    "replace_span_content",
    "scene_block_at_source_position",
    "set_emphasis_weight",
    "set_lora_weight",
    "serialize_reorder_chip",
    "serialize_reorder_state",
    "serialize_reorder_state_for_chips",
    "serialize_prompt_document",
    "serialize_segments",
    "split_gap_for_blank_line_insert",
    "unwrap_neutral_emphasis",
    "validate_custom_wildcard_delimiters",
]
