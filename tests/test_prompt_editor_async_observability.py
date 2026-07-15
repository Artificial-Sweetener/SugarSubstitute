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

"""Tests for prompt-safe prompt-editor async observability helpers."""

from __future__ import annotations

import logging

import pytest

from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAsyncRequest,
    PromptAsyncRequestContext,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptFreshnessDecision,
    PromptFreshnessMismatch,
    log_prompt_async_warning,
    prompt_async_context_log_fields,
    prompt_async_freshness_log_fields,
    prompt_async_identity_log_fields,
    prompt_async_outcome_log_fields,
    prompt_async_request_log_fields,
)


def test_async_identity_log_fields_include_allowed_prompt_safe_identity() -> None:
    """Identity log fields should expose only boundary-owned identifiers."""

    identity = PromptAsyncResultIdentity(
        request_id=7,
        editor_session_id="session",
        source_revision=12,
        source_length=44,
        feature_profile_id="feature-profile",
        scene_context_id="scene",
        cube_context_id="cube",
        query_identity=("tag", 3),
        cancellation_generation=2,
    )

    fields = prompt_async_identity_log_fields(identity)

    assert fields == {
        "request_id": 7,
        "editor_session_id": "session",
        "source_revision": 12,
        "source_length": 44,
        "feature_profile_id": "feature-profile",
        "scene_context_id": "scene",
        "cube_context_id": "cube",
        "query_identity": ("tag", 3),
        "cancellation_generation": 2,
    }


def test_async_request_log_fields_merge_safe_context_fields() -> None:
    """Request log fields should include operation, reason, identities, and metrics."""

    request = PromptAsyncRequest(
        identity=PromptAsyncResultIdentity(
            request_id=8,
            source_revision=13,
            source_length=55,
        ),
        context=PromptAsyncRequestContext(
            operation="semantic_refresh",
            reason="text_changed",
            safe_fields=(
                ("coalesced_count", 2),
                ("queued_age_ms", "3.500"),
            ),
        ),
        work=lambda _token: 1,
    )

    fields = prompt_async_request_log_fields(request)

    assert fields["operation"] == "semantic_refresh"
    assert fields["reason"] == "text_changed"
    assert fields["request_id"] == 8
    assert fields["source_revision"] == 13
    assert fields["source_length"] == 55
    assert fields["coalesced_count"] == 2
    assert fields["queued_age_ms"] == "3.500"


@pytest.mark.parametrize(
    "unsafe_name",
    [
        "prompt_text",
        "source_text",
        "selected_prompt_text",
        "selected_text",
        "token_payload",
        "trigger_words",
        "local_path",
        "api_key",
        "authorization_header",
        "cookie_value",
        "credential_name",
        "exception_message",
        "field_value",
        "raw_exception",
        "random_label",
    ],
)
def test_async_context_log_fields_reject_unsafe_or_unrecognized_fields(
    unsafe_name: str,
) -> None:
    """Context field validation should reject prompt text, secrets, and unknown data."""

    context = PromptAsyncRequestContext(
        operation="autocomplete",
        reason="query",
        safe_fields=((unsafe_name, "unsafe"),),
    )

    with pytest.raises(ValueError, match="prompt-safe"):
        prompt_async_context_log_fields(context)


def test_async_outcome_log_fields_record_status_without_error_message() -> None:
    """Failed outcome logs should include error type without serializing messages."""

    error = RuntimeError("contains prompt content that must not be logged")
    outcome: PromptAsyncTaskOutcome[int] = PromptAsyncTaskOutcome(
        identity=PromptAsyncResultIdentity(request_id=9),
        context=PromptAsyncRequestContext(
            operation="diagnostics",
            reason="source_changed",
        ),
        error=error,
    )

    fields = prompt_async_outcome_log_fields(outcome)

    assert fields["outcome_status"] == "failed"
    assert fields["error_type"] == "RuntimeError"
    assert "contains prompt content" not in repr(fields)


def test_async_freshness_log_fields_include_drop_reason_and_mismatch_names() -> None:
    """Freshness log fields should summarize stale outcomes without prompt content."""

    decision = PromptFreshnessDecision(
        is_fresh=False,
        drop_reason="identity_mismatch",
        mismatches=(
            PromptFreshnessMismatch(
                field_name="source_revision",
                expected=12,
                actual=11,
            ),
        ),
    )

    fields = prompt_async_freshness_log_fields(decision)

    assert fields == {
        "fresh": False,
        "drop_reason": "identity_mismatch",
        "freshness_mismatch_count": 1,
        "freshness_mismatch_fields": "source_revision",
    }


def test_async_warning_logging_preserves_traceback_without_error_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Warning helper should preserve exception context without serializing messages."""

    logger = logging.getLogger("tests.prompt_async_observability")
    caplog.set_level(logging.WARNING, logger=logger.name)
    error = RuntimeError("prompt text should stay out")

    log_prompt_async_warning(
        logger,
        "prompt_async.failed",
        error=error,
        operation="semantic_refresh",
        reason="task_error",
        source_length=32,
    )

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.exc_info is not None
    assert "error_type=RuntimeError" in record.message
    assert "source_length=32" in record.message
    assert "prompt text should stay out" not in record.message
