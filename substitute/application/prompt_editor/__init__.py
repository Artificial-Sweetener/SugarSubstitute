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

"""Expose prompt-editor application services without eager facade imports."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from substitute.application.prompt_editor.effective_scheduled_lora_provider import (
        EffectiveScheduledLoraProvider,
        ScheduledLoraProvider,
        WorkflowPromptContext,
    )
    from substitute.application.prompt_editor.prompt_autocomplete_queries import (
        PromptAutocompleteFallbackQuery,
        PromptAutocompleteQuery,
        PromptSceneAutocompleteQuery,
        PromptWildcardAutocompleteQuery,
    )
    from substitute.application.prompt_editor.prompt_autocomplete_text import (
        autocomplete_characters_match,
        autocomplete_completion_suffix,
        autocomplete_suffix_without_existing_right_text,
    )
    from substitute.application.prompt_editor.prompt_diagnostic_display_policy import (
        PromptDiagnosticDisplayPolicy,
    )
    from substitute.application.prompt_editor.prompt_diagnostics_models import (
        PromptDiagnostic,
        PromptDiagnosticKind,
        PromptDiagnosticPayload,
        PromptDiagnosticSeverity,
        PromptDiagnosticSnapshot,
        PromptDuplicateSegmentDiagnosticPayload,
        PromptSpellingDiagnosticPayload,
        PromptWildcardDiagnosticPayload,
    )
    from substitute.application.prompt_editor.prompt_diagnostics_service import (
        PromptDiagnosticProvider,
        PromptDiagnosticProviderResult,
        PromptDiagnosticsService,
    )
    from substitute.application.prompt_editor.prompt_document_service import (
        PromptDocumentService,
        blank_line_drop_offsets,
        clear_prompt_document_caches,
        prewarm_prompt_document_views,
    )
    from substitute.application.prompt_editor.prompt_autocomplete_query_service import (
        autocomplete_replacement_text,
        filter_noop_autocomplete_suggestions,
    )
    from substitute.application.prompt_editor.prompt_document_views import (
        PromptDocumentView,
        PromptEmphasisView,
        PromptLoraView,
        PromptReorderChipView,
        PromptSegmentView,
        PromptSyntaxSpanView,
        PromptWildcardView,
    )
    from substitute.application.prompt_editor.prompt_duplicate_segment_diagnostic_provider import (
        PromptDuplicateSegmentDiagnosticProvider,
        normalize_duplicate_prompt_segment,
    )
    from substitute.application.prompt_editor.prompt_duplicate_segment_mutations import (
        PromptDiagnosticTextEdit,
        emphasize_first_duplicate_segment_edits,
        remove_duplicate_segment_edits,
    )
    from substitute.application.prompt_editor.prompt_editor_preference_service import (
        PromptEditorPreferenceService,
    )
    from substitute.application.prompt_editor.prompt_feature_profile_service import (
        PromptFeatureProfileService,
        wildcard_management_prompt_feature_profile,
    )
    from substitute.application.prompt_editor.prompt_feature_registry import (
        PromptFeatureDefinition,
        default_prompt_feature_preferences,
        prompt_feature_definition,
        prompt_feature_definitions,
        prompt_syntax_field_features,
    )
    from substitute.application.prompt_editor.prompt_literal_parenthesis_normalizer import (
        normalize_literal_parentheses_for_storage,
    )
    from substitute.application.prompt_editor.prompt_lora_autocomplete_service import (
        PromptLoraAutocompleteCandidate,
        PromptLoraAutocompleteQuery,
        PromptLoraAutocompleteService,
    )
    from substitute.application.prompt_editor.prompt_lora_catalog_service import (
        PromptLoraCatalogItem,
        PromptLoraCatalogLookup,
        PromptLoraCatalogLookupResult,
        PromptLoraCatalogService,
        PromptLoraCatalogSnapshot,
        PromptLoraThumbnailVariant,
    )
    from substitute.application.prompt_editor.prompt_lora_resolution_service import (
        PromptLoraResolution,
        PromptLoraResolutionService,
        PromptLoraResolutionStatus,
    )
    from substitute.application.prompt_editor.prompt_lora_schedule_service import (
        DEFAULT_LORA_SCHEDULE_WEIGHT,
        PromptLoraScheduleSelection,
        PromptLoraScheduleService,
    )
    from substitute.application.prompt_editor.prompt_mutation_service import (
        PromptMutation,
        PromptMutationService,
    )
    from substitute.application.prompt_editor.prompt_syntax_actions import (
        PromptAdjustEmphasisAction,
        PromptAdjustEmphasisContentAction,
        PromptAdjustLoraWeightAction,
        PromptAdjustWildcardTagAction,
        PromptConsumeSyntaxAction,
        PromptSetEmphasisWeightAction,
        PromptSetEmphasisWeightContentAction,
        PromptSetLoraWeightAction,
        PromptSetWildcardTagAction,
        PromptSyntaxAction,
    )
    from substitute.application.prompt_editor.prompt_reorder_views import (
        PromptGapBlankLineDropTarget,
        PromptLineDropTarget,
        PromptReorderDropTarget,
        PromptReorderGapPlacement,
        PromptReorderGapView,
        PromptReorderLayoutView,
        PromptReorderPreviewSnapshot,
        PromptReorderRowView,
        PromptReorderSessionView,
        PromptReorderStateView,
    )
    from substitute.application.prompt_editor.prompt_scene_analysis_service import (
        PromptSceneAnalysisService,
        PromptSceneDiagnostics,
        PromptSceneWorkflowCube,
        WorkflowScene,
        WorkflowSceneAnalysis,
    )
    from substitute.application.prompt_editor.prompt_scene_projection_service import (
        clear_prompt_scene_projection_cache,
        effective_prompt_text_at_source_position,
        parse_prompt_scene_projection_document,
        prewarm_prompt_scene_projection_documents,
        prompt_scene_key_at_projection_source_position,
    )
    from substitute.application.prompt_editor.prompt_scheduled_lora_service import (
        PromptScheduledLora,
        PromptScheduledLoraService,
        PromptTriggerWordIndex,
        PromptTriggerWordSuggestion,
        scheduled_lora_from_catalog_item,
        scheduled_lora_from_model_catalog_item,
    )
    from substitute.application.prompt_editor.prompt_source_normalization_service import (
        PromptSourceNormalization,
        PromptSourceNormalizationService,
    )
    from substitute.application.prompt_editor.prompt_spellcheck_candidates import (
        PromptSpellcheckCandidateService,
    )
    from substitute.application.prompt_editor.prompt_spellcheck_diagnostic_provider import (
        PromptSpellcheckDiagnosticProvider,
    )
    from substitute.application.prompt_editor.prompt_spellcheck_models import (
        PromptSpellcheckCandidate,
        PromptSpellcheckSnapshot,
        PromptSpellingIssue,
        PromptSpellingSuggestionSet,
    )
    from substitute.application.prompt_editor.prompt_spellcheck_service import (
        PromptSpellcheckService,
    )
    from substitute.application.prompt_editor.prompt_syntax_profile_service import (
        PromptSyntaxProfile,
        PromptSyntaxProfileService,
        prompt_syntax_profile_from_feature_profile,
    )
    from substitute.application.prompt_editor.prompt_syntax_service import (
        PromptEmphasisRendererView,
        PromptLoraRendererSpanView,
        PromptLoraRendererView,
        PromptProjectionInputCacheKey,
        PromptSyntaxRenderPlan,
        PromptSyntaxRendererView,
        PromptSyntaxService,
        PromptWildcardRendererSpanView,
        PromptWildcardRendererView,
        clear_prompt_syntax_render_plan_cache,
    )
    from substitute.application.prompt_editor.prompt_wildcard_diagnostic_provider import (
        PromptWildcardDiagnosticProvider,
    )
    from substitute.domain.prompt import (
        PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
        PromptEditorFeature,
        PromptEditorFeatureProfile,
        PromptEditorPreferences,
        PromptFeatureDecision,
        PromptFeatureDisabledReason,
        PromptWheelAdjustmentMode,
    )

_LAZY_EXPORTS = {
    "PromptAdjustEmphasisAction": (
        "substitute.application.prompt_editor.prompt_syntax_actions"
    ),
    "PromptAdjustEmphasisContentAction": (
        "substitute.application.prompt_editor.prompt_syntax_actions"
    ),
    "PromptAdjustLoraWeightAction": (
        "substitute.application.prompt_editor.prompt_syntax_actions"
    ),
    "PromptAdjustWildcardTagAction": (
        "substitute.application.prompt_editor.prompt_syntax_actions"
    ),
    "autocomplete_replacement_text": (
        "substitute.application.prompt_editor.prompt_autocomplete_query_service"
    ),
    "autocomplete_characters_match": (
        "substitute.application.prompt_editor.prompt_autocomplete_text"
    ),
    "autocomplete_completion_suffix": (
        "substitute.application.prompt_editor.prompt_autocomplete_text"
    ),
    "autocomplete_suffix_without_existing_right_text": (
        "substitute.application.prompt_editor.prompt_autocomplete_text"
    ),
    "clear_prompt_document_caches": (
        "substitute.application.prompt_editor.prompt_document_service"
    ),
    "clear_prompt_scene_projection_cache": (
        "substitute.application.prompt_editor.prompt_scene_projection_service"
    ),
    "clear_prompt_syntax_render_plan_cache": (
        "substitute.application.prompt_editor.prompt_syntax_service"
    ),
    "DEFAULT_LORA_SCHEDULE_WEIGHT": (
        "substitute.application.prompt_editor.prompt_lora_schedule_service"
    ),
    "EffectiveScheduledLoraProvider": (
        "substitute.application.prompt_editor.effective_scheduled_lora_provider"
    ),
    "effective_prompt_text_at_source_position": (
        "substitute.application.prompt_editor.prompt_scene_projection_service"
    ),
    "filter_noop_autocomplete_suggestions": (
        "substitute.application.prompt_editor.prompt_autocomplete_query_service"
    ),
    "normalize_literal_parentheses_for_storage": (
        "substitute.application.prompt_editor.prompt_literal_parenthesis_normalizer"
    ),
    "PromptAutocompleteFallbackQuery": (
        "substitute.application.prompt_editor.prompt_autocomplete_queries"
    ),
    "PromptAutocompleteQuery": (
        "substitute.application.prompt_editor.prompt_autocomplete_queries"
    ),
    "PromptConsumeSyntaxAction": (
        "substitute.application.prompt_editor.prompt_syntax_actions"
    ),
    "PromptDiagnostic": (
        "substitute.application.prompt_editor.prompt_diagnostics_models"
    ),
    "PromptDiagnosticDisplayPolicy": (
        "substitute.application.prompt_editor.prompt_diagnostic_display_policy"
    ),
    "PromptDiagnosticKind": (
        "substitute.application.prompt_editor.prompt_diagnostics_models"
    ),
    "PromptDiagnosticPayload": (
        "substitute.application.prompt_editor.prompt_diagnostics_models"
    ),
    "PromptDiagnosticProvider": (
        "substitute.application.prompt_editor.prompt_diagnostics_service"
    ),
    "PromptDiagnosticProviderResult": (
        "substitute.application.prompt_editor.prompt_diagnostics_service"
    ),
    "PromptDiagnosticsService": (
        "substitute.application.prompt_editor.prompt_diagnostics_service"
    ),
    "PromptDiagnosticSeverity": (
        "substitute.application.prompt_editor.prompt_diagnostics_models"
    ),
    "PromptDiagnosticSnapshot": (
        "substitute.application.prompt_editor.prompt_diagnostics_models"
    ),
    "PromptDiagnosticTextEdit": (
        "substitute.application.prompt_editor.prompt_duplicate_segment_mutations"
    ),
    "PromptDocumentService": (
        "substitute.application.prompt_editor.prompt_document_service"
    ),
    "PromptDocumentView": (
        "substitute.application.prompt_editor.prompt_document_views"
    ),
    "PromptDuplicateSegmentDiagnosticPayload": (
        "substitute.application.prompt_editor.prompt_diagnostics_models"
    ),
    "PromptDuplicateSegmentDiagnosticProvider": (
        "substitute.application.prompt_editor.prompt_duplicate_segment_diagnostic_provider"
    ),
    "PromptEditorFeature": "substitute.domain.prompt",
    "PromptEditorFeatureProfile": "substitute.domain.prompt",
    "PromptEditorPreferenceService": (
        "substitute.application.prompt_editor.prompt_editor_preference_service"
    ),
    "PromptEditorPreferences": "substitute.domain.prompt",
    "PromptWheelAdjustmentMode": "substitute.domain.prompt",
    "PromptEmphasisRendererView": (
        "substitute.application.prompt_editor.prompt_syntax_service"
    ),
    "PromptEmphasisView": (
        "substitute.application.prompt_editor.prompt_document_views"
    ),
    "PromptGapBlankLineDropTarget": (
        "substitute.application.prompt_editor.prompt_reorder_views"
    ),
    "PromptFeatureDefinition": (
        "substitute.application.prompt_editor.prompt_feature_registry"
    ),
    "PromptFeatureDecision": "substitute.domain.prompt",
    "PromptFeatureDisabledReason": "substitute.domain.prompt",
    "PromptFeatureProfileService": (
        "substitute.application.prompt_editor.prompt_feature_profile_service"
    ),
    "PromptLineDropTarget": (
        "substitute.application.prompt_editor.prompt_reorder_views"
    ),
    "PromptLoraView": "substitute.application.prompt_editor.prompt_document_views",
    "PromptLoraAutocompleteCandidate": (
        "substitute.application.prompt_editor.prompt_lora_autocomplete_service"
    ),
    "PromptLoraAutocompleteQuery": (
        "substitute.application.prompt_editor.prompt_lora_autocomplete_service"
    ),
    "PromptLoraAutocompleteService": (
        "substitute.application.prompt_editor.prompt_lora_autocomplete_service"
    ),
    "PromptLoraCatalogItem": (
        "substitute.application.prompt_editor.prompt_lora_catalog_service"
    ),
    "PromptLoraCatalogLookup": (
        "substitute.application.prompt_editor.prompt_lora_catalog_service"
    ),
    "PromptLoraCatalogLookupResult": (
        "substitute.application.prompt_editor.prompt_lora_catalog_service"
    ),
    "PromptLoraCatalogSnapshot": (
        "substitute.application.prompt_editor.prompt_lora_catalog_service"
    ),
    "PromptLoraCatalogService": (
        "substitute.application.prompt_editor.prompt_lora_catalog_service"
    ),
    "PromptLoraResolution": (
        "substitute.application.prompt_editor.prompt_lora_resolution_service"
    ),
    "PromptLoraResolutionService": (
        "substitute.application.prompt_editor.prompt_lora_resolution_service"
    ),
    "PromptLoraResolutionStatus": (
        "substitute.application.prompt_editor.prompt_lora_resolution_service"
    ),
    "PromptLoraThumbnailVariant": (
        "substitute.application.prompt_editor.prompt_lora_catalog_service"
    ),
    "PromptLoraScheduleSelection": (
        "substitute.application.prompt_editor.prompt_lora_schedule_service"
    ),
    "PromptLoraScheduleService": (
        "substitute.application.prompt_editor.prompt_lora_schedule_service"
    ),
    "PromptLoraRendererSpanView": (
        "substitute.application.prompt_editor.prompt_syntax_service"
    ),
    "PromptLoraRendererView": (
        "substitute.application.prompt_editor.prompt_syntax_service"
    ),
    "PromptProjectionInputCacheKey": (
        "substitute.application.prompt_editor.prompt_syntax_service"
    ),
    "PromptMutation": "substitute.application.prompt_editor.prompt_mutation_service",
    "PromptMutationService": (
        "substitute.application.prompt_editor.prompt_mutation_service"
    ),
    "PromptScheduledLora": (
        "substitute.application.prompt_editor.prompt_scheduled_lora_service"
    ),
    "PromptScheduledLoraService": (
        "substitute.application.prompt_editor.prompt_scheduled_lora_service"
    ),
    "PromptSceneAnalysisService": (
        "substitute.application.prompt_editor.prompt_scene_analysis_service"
    ),
    "PromptSceneDiagnostics": (
        "substitute.application.prompt_editor.prompt_scene_analysis_service"
    ),
    "PromptSceneWorkflowCube": (
        "substitute.application.prompt_editor.prompt_scene_analysis_service"
    ),
    "PromptSetEmphasisWeightAction": (
        "substitute.application.prompt_editor.prompt_syntax_actions"
    ),
    "PromptSetEmphasisWeightContentAction": (
        "substitute.application.prompt_editor.prompt_syntax_actions"
    ),
    "PromptSetLoraWeightAction": (
        "substitute.application.prompt_editor.prompt_syntax_actions"
    ),
    "PromptSetWildcardTagAction": (
        "substitute.application.prompt_editor.prompt_syntax_actions"
    ),
    "PromptSourceNormalization": (
        "substitute.application.prompt_editor.prompt_source_normalization_service"
    ),
    "PromptSourceNormalizationService": (
        "substitute.application.prompt_editor.prompt_source_normalization_service"
    ),
    "PromptReorderChipView": (
        "substitute.application.prompt_editor.prompt_document_views"
    ),
    "PromptReorderDropTarget": (
        "substitute.application.prompt_editor.prompt_reorder_views"
    ),
    "PromptReorderGapPlacement": (
        "substitute.application.prompt_editor.prompt_reorder_views"
    ),
    "PromptReorderGapView": (
        "substitute.application.prompt_editor.prompt_reorder_views"
    ),
    "PromptReorderLayoutView": (
        "substitute.application.prompt_editor.prompt_reorder_views"
    ),
    "PromptReorderPreviewSnapshot": (
        "substitute.application.prompt_editor.prompt_reorder_views"
    ),
    "PromptReorderRowView": (
        "substitute.application.prompt_editor.prompt_reorder_views"
    ),
    "PromptReorderSessionView": (
        "substitute.application.prompt_editor.prompt_reorder_views"
    ),
    "PromptReorderStateView": (
        "substitute.application.prompt_editor.prompt_reorder_views"
    ),
    "PromptSceneAutocompleteQuery": (
        "substitute.application.prompt_editor.prompt_autocomplete_queries"
    ),
    "PromptSegmentView": ("substitute.application.prompt_editor.prompt_document_views"),
    "PromptSpellcheckCandidate": (
        "substitute.application.prompt_editor.prompt_spellcheck_models"
    ),
    "PromptSpellcheckCandidateService": (
        "substitute.application.prompt_editor.prompt_spellcheck_candidates"
    ),
    "PromptSpellcheckDiagnosticProvider": (
        "substitute.application.prompt_editor.prompt_spellcheck_diagnostic_provider"
    ),
    "PromptSpellcheckService": (
        "substitute.application.prompt_editor.prompt_spellcheck_service"
    ),
    "PromptSpellcheckSnapshot": (
        "substitute.application.prompt_editor.prompt_spellcheck_models"
    ),
    "PromptSpellingDiagnosticPayload": (
        "substitute.application.prompt_editor.prompt_diagnostics_models"
    ),
    "PromptSpellingIssue": (
        "substitute.application.prompt_editor.prompt_spellcheck_models"
    ),
    "PromptSpellingSuggestionSet": (
        "substitute.application.prompt_editor.prompt_spellcheck_models"
    ),
    "PromptSyntaxAction": (
        "substitute.application.prompt_editor.prompt_syntax_actions"
    ),
    "PromptSyntaxRenderPlan": (
        "substitute.application.prompt_editor.prompt_syntax_service"
    ),
    "PromptSyntaxProfile": (
        "substitute.application.prompt_editor.prompt_syntax_profile_service"
    ),
    "PromptSyntaxProfileService": (
        "substitute.application.prompt_editor.prompt_syntax_profile_service"
    ),
    "prompt_syntax_profile_from_feature_profile": (
        "substitute.application.prompt_editor.prompt_syntax_profile_service"
    ),
    "wildcard_management_prompt_feature_profile": (
        "substitute.application.prompt_editor.prompt_feature_profile_service"
    ),
    "PromptSyntaxRendererView": (
        "substitute.application.prompt_editor.prompt_syntax_service"
    ),
    "PromptSyntaxService": (
        "substitute.application.prompt_editor.prompt_syntax_service"
    ),
    "PromptSyntaxSpanView": (
        "substitute.application.prompt_editor.prompt_document_views"
    ),
    "PromptTriggerWordIndex": (
        "substitute.application.prompt_editor.prompt_scheduled_lora_service"
    ),
    "PromptTriggerWordSuggestion": (
        "substitute.application.prompt_editor.prompt_scheduled_lora_service"
    ),
    "PromptWildcardAutocompleteQuery": (
        "substitute.application.prompt_editor.prompt_autocomplete_queries"
    ),
    "PromptWildcardDiagnosticPayload": (
        "substitute.application.prompt_editor.prompt_diagnostics_models"
    ),
    "PromptWildcardDiagnosticProvider": (
        "substitute.application.prompt_editor.prompt_wildcard_diagnostic_provider"
    ),
    "PromptWildcardRendererSpanView": (
        "substitute.application.prompt_editor.prompt_syntax_service"
    ),
    "PromptWildcardRendererView": (
        "substitute.application.prompt_editor.prompt_syntax_service"
    ),
    "PromptWildcardView": (
        "substitute.application.prompt_editor.prompt_document_views"
    ),
    "PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION": "substitute.domain.prompt",
    "ScheduledLoraProvider": (
        "substitute.application.prompt_editor.effective_scheduled_lora_provider"
    ),
    "WorkflowPromptContext": (
        "substitute.application.prompt_editor.effective_scheduled_lora_provider"
    ),
    "WorkflowScene": (
        "substitute.application.prompt_editor.prompt_scene_analysis_service"
    ),
    "WorkflowSceneAnalysis": (
        "substitute.application.prompt_editor.prompt_scene_analysis_service"
    ),
    "blank_line_drop_offsets": (
        "substitute.application.prompt_editor.prompt_document_service"
    ),
    "default_prompt_feature_preferences": (
        "substitute.application.prompt_editor.prompt_feature_registry"
    ),
    "emphasize_first_duplicate_segment_edits": (
        "substitute.application.prompt_editor.prompt_duplicate_segment_mutations"
    ),
    "normalize_duplicate_prompt_segment": (
        "substitute.application.prompt_editor.prompt_duplicate_segment_diagnostic_provider"
    ),
    "parse_prompt_scene_projection_document": (
        "substitute.application.prompt_editor.prompt_scene_projection_service"
    ),
    "prewarm_prompt_document_views": (
        "substitute.application.prompt_editor.prompt_document_service"
    ),
    "prewarm_prompt_scene_projection_documents": (
        "substitute.application.prompt_editor.prompt_scene_projection_service"
    ),
    "prompt_scene_key_at_projection_source_position": (
        "substitute.application.prompt_editor.prompt_scene_projection_service"
    ),
    "prompt_feature_definition": (
        "substitute.application.prompt_editor.prompt_feature_registry"
    ),
    "prompt_feature_definitions": (
        "substitute.application.prompt_editor.prompt_feature_registry"
    ),
    "prompt_syntax_field_features": (
        "substitute.application.prompt_editor.prompt_feature_registry"
    ),
    "remove_duplicate_segment_edits": (
        "substitute.application.prompt_editor.prompt_duplicate_segment_mutations"
    ),
    "scheduled_lora_from_catalog_item": (
        "substitute.application.prompt_editor.prompt_scheduled_lora_service"
    ),
    "scheduled_lora_from_model_catalog_item": (
        "substitute.application.prompt_editor.prompt_scheduled_lora_service"
    ),
}


def __getattr__(name: str) -> object:
    """Load one exported prompt-editor application symbol on first access."""

    try:
        module_name = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


__all__ = [
    "PromptAdjustEmphasisAction",
    "PromptAdjustEmphasisContentAction",
    "PromptAdjustLoraWeightAction",
    "PromptAdjustWildcardTagAction",
    "autocomplete_replacement_text",
    "autocomplete_characters_match",
    "autocomplete_completion_suffix",
    "autocomplete_suffix_without_existing_right_text",
    "clear_prompt_document_caches",
    "clear_prompt_scene_projection_cache",
    "clear_prompt_syntax_render_plan_cache",
    "DEFAULT_LORA_SCHEDULE_WEIGHT",
    "EffectiveScheduledLoraProvider",
    "effective_prompt_text_at_source_position",
    "filter_noop_autocomplete_suggestions",
    "normalize_literal_parentheses_for_storage",
    "PromptAutocompleteFallbackQuery",
    "PromptAutocompleteQuery",
    "PromptConsumeSyntaxAction",
    "PromptDiagnostic",
    "PromptDiagnosticDisplayPolicy",
    "PromptDiagnosticKind",
    "PromptDiagnosticPayload",
    "PromptDiagnosticProvider",
    "PromptDiagnosticProviderResult",
    "PromptDiagnosticsService",
    "PromptDiagnosticSeverity",
    "PromptDiagnosticSnapshot",
    "PromptDiagnosticTextEdit",
    "PromptDocumentService",
    "PromptDocumentView",
    "PromptDuplicateSegmentDiagnosticPayload",
    "PromptDuplicateSegmentDiagnosticProvider",
    "PromptEditorFeature",
    "PromptEditorFeatureProfile",
    "PromptEditorPreferenceService",
    "PromptEditorPreferences",
    "PromptWheelAdjustmentMode",
    "PromptEmphasisRendererView",
    "PromptEmphasisView",
    "PromptGapBlankLineDropTarget",
    "PromptFeatureDefinition",
    "PromptFeatureDecision",
    "PromptFeatureDisabledReason",
    "PromptFeatureProfileService",
    "PromptLineDropTarget",
    "PromptLoraView",
    "PromptLoraAutocompleteCandidate",
    "PromptLoraAutocompleteQuery",
    "PromptLoraAutocompleteService",
    "PromptLoraCatalogItem",
    "PromptLoraCatalogLookup",
    "PromptLoraCatalogLookupResult",
    "PromptLoraCatalogSnapshot",
    "PromptLoraCatalogService",
    "PromptLoraResolution",
    "PromptLoraResolutionService",
    "PromptLoraResolutionStatus",
    "PromptLoraThumbnailVariant",
    "PromptLoraScheduleSelection",
    "PromptLoraScheduleService",
    "PromptLoraRendererSpanView",
    "PromptLoraRendererView",
    "PromptProjectionInputCacheKey",
    "PromptMutation",
    "PromptMutationService",
    "PromptScheduledLora",
    "PromptScheduledLoraService",
    "PromptSceneAnalysisService",
    "PromptSceneDiagnostics",
    "PromptSceneWorkflowCube",
    "PromptSetEmphasisWeightAction",
    "PromptSetEmphasisWeightContentAction",
    "PromptSetLoraWeightAction",
    "PromptSetWildcardTagAction",
    "PromptSourceNormalization",
    "PromptSourceNormalizationService",
    "PromptReorderChipView",
    "PromptReorderDropTarget",
    "PromptReorderGapPlacement",
    "PromptReorderGapView",
    "PromptReorderLayoutView",
    "PromptReorderPreviewSnapshot",
    "PromptReorderRowView",
    "PromptReorderSessionView",
    "PromptReorderStateView",
    "PromptSceneAutocompleteQuery",
    "PromptSegmentView",
    "PromptSpellcheckCandidate",
    "PromptSpellcheckCandidateService",
    "PromptSpellcheckDiagnosticProvider",
    "PromptSpellcheckService",
    "PromptSpellcheckSnapshot",
    "PromptSpellingDiagnosticPayload",
    "PromptSpellingIssue",
    "PromptSpellingSuggestionSet",
    "PromptSyntaxAction",
    "PromptSyntaxRenderPlan",
    "PromptSyntaxProfile",
    "PromptSyntaxProfileService",
    "prompt_syntax_profile_from_feature_profile",
    "wildcard_management_prompt_feature_profile",
    "PromptSyntaxRendererView",
    "PromptSyntaxService",
    "PromptSyntaxSpanView",
    "PromptTriggerWordIndex",
    "PromptTriggerWordSuggestion",
    "PromptWildcardAutocompleteQuery",
    "PromptWildcardDiagnosticPayload",
    "PromptWildcardDiagnosticProvider",
    "PromptWildcardRendererSpanView",
    "PromptWildcardRendererView",
    "PromptWildcardView",
    "PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION",
    "ScheduledLoraProvider",
    "WorkflowPromptContext",
    "WorkflowScene",
    "WorkflowSceneAnalysis",
    "blank_line_drop_offsets",
    "default_prompt_feature_preferences",
    "emphasize_first_duplicate_segment_edits",
    "normalize_duplicate_prompt_segment",
    "parse_prompt_scene_projection_document",
    "prewarm_prompt_document_views",
    "prewarm_prompt_scene_projection_documents",
    "prompt_scene_key_at_projection_source_position",
    "prompt_feature_definition",
    "prompt_feature_definitions",
    "prompt_syntax_field_features",
    "remove_duplicate_segment_edits",
    "scheduled_lora_from_catalog_item",
    "scheduled_lora_from_model_catalog_item",
]
