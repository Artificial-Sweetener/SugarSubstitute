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

"""Contract tests for the prompt-editor async execution boundary types."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass
import logging
from typing import Any, cast

import pytest

from substitute.shared.logging.logger import get_logger
from substitute.presentation.editor.prompt_editor import async_work
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAsyncRequest,
    PromptAsyncRequestContext,
    PromptAsyncOutcomeStatus,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorCancellationController,
    PromptEditorCancellationSource,
    PromptEditorDebouncer,
    PromptEditorMainThreadDispatcher,
    PromptEditorRequestChannel,
    PromptEditorTaskExecutor,
    PromptFreshnessDecision,
    PromptFreshnessMismatch,
    PromptSemanticRefreshController,
    PromptSemanticRefreshHost,
    PromptSemanticRefreshRequest,
    PromptSemanticRefreshResult,
    PromptStaleResultGuard,
    PromptLatestWinsRequestChannel,
    QtDanbooruUrlImportDispatcher,
    QtPromptEditorDebouncer,
    QtPromptEditorMainThreadDispatcher,
    build_prompt_editor_executor,
    build_prompt_semantic_refresh_controller,
    build_semantic_refresh_result,
    log_prompt_async_debug,
    log_prompt_async_warning,
    prompt_async_context_log_fields,
    prompt_async_error_log_fields,
    prompt_async_freshness_log_fields,
    prompt_async_identity_log_fields,
    prompt_async_outcome_log_fields,
    prompt_async_request_log_fields,
    semantic_refresh_request_context,
)


def test_async_work_phase4_3_exports_execution_and_dispatch_boundary_types() -> None:
    """The async-work package should expose execution and main-thread dispatch types."""

    assert set(async_work.__all__) == {
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

    assert PromptAsyncOutcomeStatus is not None
    assert PromptEditorCancellationController is not None
    assert PromptEditorCancellationSource is not None
    assert PromptEditorDebouncer is not None
    assert PromptEditorMainThreadDispatcher is not None
    assert PromptEditorRequestChannel is not None
    assert PromptFreshnessDecision is not None
    assert PromptFreshnessMismatch is not None
    assert PromptStaleResultGuard is not None
    assert PromptLatestWinsRequestChannel is not None
    assert PromptSemanticRefreshController is not None
    assert PromptSemanticRefreshHost is not None
    assert PromptSemanticRefreshRequest is not None
    assert PromptSemanticRefreshResult is not None
    assert PromptEditorTaskExecutor is not None
    assert QtPromptEditorDebouncer is not None
    assert QtDanbooruUrlImportDispatcher is not None
    assert QtPromptEditorMainThreadDispatcher is not None
    assert build_prompt_editor_executor is not None
    assert build_prompt_semantic_refresh_controller is not None
    assert build_semantic_refresh_result is not None
    assert log_prompt_async_debug is not None
    assert log_prompt_async_warning is not None
    assert prompt_async_context_log_fields is not None
    assert prompt_async_error_log_fields is not None
    assert prompt_async_freshness_log_fields is not None
    assert prompt_async_identity_log_fields is not None
    assert prompt_async_outcome_log_fields is not None
    assert semantic_refresh_request_context is not None
    assert prompt_async_request_log_fields is not None


@pytest.mark.parametrize(
    "type_object",
    [
        PromptAsyncRequest,
        PromptAsyncRequestContext,
        PromptAsyncResultIdentity,
        PromptAsyncTaskOutcome,
    ],
)
def test_async_execution_value_types_are_frozen_slotted(type_object: object) -> None:
    """Async execution value types should be immutable and memory-stable."""

    assert is_dataclass(type_object)
    assert getattr(type_object, "__slots__", None) is not None

    identity = PromptAsyncResultIdentity(request_id=1)
    with pytest.raises(FrozenInstanceError):
        cast(Any, identity).request_id = 2


@pytest.mark.parametrize(
    ("field_name", "identity_kwargs"),
    [
        ("request_id", {"request_id": -1}),
        ("source_revision", {"request_id": 1, "source_revision": -1}),
        ("source_length", {"request_id": 1, "source_length": -1}),
        (
            "cancellation_generation",
            {"request_id": 1, "cancellation_generation": -1},
        ),
    ],
)
def test_async_result_identity_rejects_negative_integer_fields(
    field_name: str,
    identity_kwargs: dict[str, int],
) -> None:
    """Async result identity should reject invalid revision-like values."""

    with pytest.raises(ValueError, match=field_name):
        PromptAsyncResultIdentity(**identity_kwargs)


@pytest.mark.parametrize(
    ("context_kwargs", "field_name"),
    [
        ({"operation": "", "reason": "text_changed"}, "operation"),
        ({"operation": "semantic_refresh", "reason": "   "}, "reason"),
        (
            {
                "operation": "semantic_refresh",
                "reason": "text_changed",
                "safe_fields": ((" ", 1),),
            },
            "safe_fields field name",
        ),
    ],
)
def test_async_request_context_rejects_blank_prompt_safe_labels(
    context_kwargs: dict[str, object],
    field_name: str,
) -> None:
    """Request context should require meaningful prompt-safe labels."""

    with pytest.raises(ValueError, match=field_name):
        cast(Any, PromptAsyncRequestContext)(**context_kwargs)


def test_async_request_does_not_execute_work_during_construction() -> None:
    """PromptAsyncRequest should store task callables without running them."""

    executed = False

    def work(_token: object) -> int:
        nonlocal executed
        executed = True
        return 7

    request = PromptAsyncRequest(
        identity=PromptAsyncResultIdentity(
            request_id=4,
            editor_session_id="session",
            source_revision=12,
            source_length=32,
            feature_profile_id="features",
            scene_context_id="scene",
            cube_context_id="cube",
            query_identity=("tag", "cat"),
            cancellation_generation=3,
        ),
        context=PromptAsyncRequestContext(
            operation="semantic_refresh",
            reason="text_changed",
            safe_fields=(("source_length", 32),),
        ),
        work=work,
    )

    assert executed is False
    assert request.identity.source_revision == 12
    assert request.context.safe_fields == (("source_length", 32),)
    assert request.work(PromptEditorCancellationSource(generation=1)) == 7
    assert executed is True


def test_async_task_outcome_rejects_ambiguous_states() -> None:
    """Task outcomes should not carry conflicting completion states."""

    identity = PromptAsyncResultIdentity(request_id=1)
    context = PromptAsyncRequestContext(operation="test", reason="unit")

    with pytest.raises(ValueError, match="cancelled"):
        PromptAsyncTaskOutcome(
            identity=identity,
            context=context,
            error=RuntimeError("failed"),
            cancelled=True,
        )
    with pytest.raises(ValueError, match="cancelled"):
        PromptAsyncTaskOutcome(
            identity=identity,
            context=context,
            result=1,
            cancelled=True,
        )
    with pytest.raises(ValueError, match="failed"):
        PromptAsyncTaskOutcome(
            identity=identity,
            context=context,
            result=1,
            error=RuntimeError("failed"),
        )


@pytest.mark.parametrize(
    "unsafe_field_name",
    [
        "prompt_text",
        "selected_prompt_text",
        "selected_text",
        "trigger_words",
        "api_key",
        "local_path",
    ],
)
def test_async_context_log_fields_reject_content_bearing_field_names(
    unsafe_field_name: str,
) -> None:
    """Async observability should reject fields that can contain prompts or secrets."""

    context = PromptAsyncRequestContext(
        operation="semantic_refresh",
        reason="unit",
        safe_fields=((unsafe_field_name, "unsafe"),),
    )

    with pytest.raises(ValueError, match="not prompt-safe"):
        prompt_async_context_log_fields(context)


def test_async_warning_logging_preserves_traceback_without_exception_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Async warnings should keep traceback context without serializing error messages."""

    logger = get_logger("presentation.editor.prompt_editor.async_work.test")
    caplog.set_level(logging.WARNING, logger=logger.name)

    prompt_like_error_message = "prompt secret should not be logged"
    try:
        raise RuntimeError(prompt_like_error_message)
    except RuntimeError as error:
        log_prompt_async_warning(
            logger,
            "async failure",
            error=error,
            request_id=12,
            source_length=33,
        )

    assert "async failure" in caplog.text
    assert "error_type=RuntimeError" in caplog.text
    assert "request_id=12" in caplog.text
    assert "source_length=33" in caplog.text
    assert prompt_like_error_message not in caplog.text
