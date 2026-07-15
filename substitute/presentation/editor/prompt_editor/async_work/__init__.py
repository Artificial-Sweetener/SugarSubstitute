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

"""Expose prompt-editor-local async execution boundary protocols."""

from .cancellation import (
    PromptEditorCancellationController,
    PromptEditorCancellationSource,
)
from .debounce import PromptEditorDebouncer, QtPromptEditorDebouncer
from .danbooru_import_dispatcher import QtDanbooruUrlImportDispatcher
from .execution import (
    PromptAsyncRequest,
    PromptAsyncRequestContext,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorCancellationToken,
    PromptEditorExecutor,
    PromptEditorTaskHandle,
)
from .main_thread_dispatcher import (
    PromptEditorMainThreadDispatcher,
    QtPromptEditorMainThreadDispatcher,
)
from .observability import (
    PromptAsyncOutcomeStatus,
    log_prompt_async_debug,
    log_prompt_async_warning,
    prompt_async_context_log_fields,
    prompt_async_error_log_fields,
    prompt_async_freshness_log_fields,
    prompt_async_identity_log_fields,
    prompt_async_outcome_log_fields,
    prompt_async_request_log_fields,
)
from .request_channel import (
    PromptEditorRequestChannel,
    PromptLatestWinsRequestChannel,
)
from .semantic_refresh_controller import (
    PromptSemanticRefreshController,
    PromptSemanticRefreshHost,
    PromptSemanticRefreshRequest,
    build_prompt_semantic_refresh_controller,
    semantic_refresh_request_context,
)
from .scheduled_lora_dispatcher import (
    PromptScheduledLoraSignature,
    PromptAutocompleteTriggerWordResult,
    PromptScheduledLoraContextCacheKey,
    PromptScheduledLoraContext,
    PromptScheduledLoraContextCoordinator,
    PromptScheduledLoraContextProvider,
    PromptScheduledLoraContextRequest,
    PromptScheduledLoraResolver,
    autocomplete_suggestion_from_trigger_word,
    build_prompt_scheduled_lora_context_coordinator,
    scheduled_lora_signature,
)
from .semantic_refresh_result import (
    PromptSemanticRefreshResult,
    build_semantic_refresh_result,
)
from .stale_result_guard import (
    PromptFreshnessDecision,
    PromptFreshnessField,
    PromptFreshnessMismatch,
    PromptStaleResultGuard,
)
from .thumbnail_preloader import (
    PromptLoraThumbnailPreloadResult,
    PromptLoraThumbnailPreloader,
)
from .task_executor import (
    PromptEditorTaskExecutor,
    build_prompt_editor_executor,
)

__all__ = [
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
    "QtPromptEditorDebouncer",
    "QtDanbooruUrlImportDispatcher",
    "QtPromptEditorMainThreadDispatcher",
    "autocomplete_suggestion_from_trigger_word",
    "build_prompt_scheduled_lora_context_coordinator",
    "build_prompt_editor_executor",
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
]
