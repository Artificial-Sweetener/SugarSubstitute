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

"""Verify the prompt-editor async-work package public contract."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor import async_work


def test_async_work_exports_execution_and_dispatch_boundary_types() -> None:
    """Expose the complete async-work boundary from its package owner."""

    expected_exports = {
        "PromptAsyncOutcomeStatus",
        "PromptAsyncRequest",
        "PromptAsyncRequestContext",
        "PromptAsyncResultIdentity",
        "PromptAsyncTaskOutcome",
        "PromptScheduledLoraSignature",
        "PromptAutocompleteTriggerWordResult",
        "PromptEditorCancellationController",
        "PromptEditorCancellationSource",
        "PromptEditorCancellationToken",
        "PromptEditorDebouncer",
        "PromptEditorExecutor",
        "PromptFreshnessDecision",
        "PromptFreshnessField",
        "PromptFreshnessMismatch",
        "PromptEditorMainThreadDispatcher",
        "PromptEditorRequestChannel",
        "PromptStaleResultGuard",
        "PromptEditorTaskHandle",
        "PromptEditorTaskExecutor",
        "PromptLatestWinsRequestChannel",
        "PromptLoraThumbnailPreloadResult",
        "PromptLoraThumbnailPreloader",
        "PromptScheduledLoraContextCacheKey",
        "PromptScheduledLoraContext",
        "PromptScheduledLoraContextCoordinator",
        "PromptScheduledLoraContextProvider",
        "PromptScheduledLoraContextRequest",
        "PromptScheduledLoraResolver",
        "PromptSemanticRefreshController",
        "PromptSemanticRefreshHost",
        "PromptSemanticRefreshRequest",
        "PromptSemanticRefreshResult",
        "QtDanbooruUrlImportDispatcher",
        "QtPromptEditorDebouncer",
        "QtPromptEditorMainThreadDispatcher",
        "autocomplete_suggestion_from_trigger_word",
        "build_prompt_editor_executor",
        "build_prompt_scheduled_lora_context_coordinator",
        "build_prompt_semantic_refresh_controller",
        "build_semantic_refresh_result",
        "log_prompt_async_debug",
        "log_prompt_async_warning",
        "prompt_async_context_log_fields",
        "prompt_async_error_log_fields",
        "prompt_async_freshness_log_fields",
        "prompt_async_identity_log_fields",
        "prompt_async_outcome_log_fields",
        "prompt_async_request_log_fields",
        "scheduled_lora_signature",
        "semantic_refresh_request_context",
    }

    assert set(async_work.__all__) == expected_exports
    for export_name in expected_exports:
        assert getattr(async_work, export_name) is not None
