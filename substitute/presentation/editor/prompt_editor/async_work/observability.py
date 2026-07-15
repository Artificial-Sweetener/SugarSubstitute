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

"""Build prompt-safe async log context for prompt-editor background work."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from typing import Literal, TypeVar

from substitute.shared.logging.logger import log_debug, log_warning

from .execution import (
    PromptAsyncRequest,
    PromptAsyncRequestContext,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
)
from .stale_result_guard import PromptFreshnessDecision

TResult = TypeVar("TResult")
PromptAsyncOutcomeStatus = Literal["completed", "cancelled", "failed"]

_ALLOWED_CONTEXT_FIELD_NAMES = frozenset(
    {
        "active_task_count",
        "cache_size",
        "cancellation_reason",
        "cancellation_generation",
        "coalesced_count",
        "current_source_length",
        "document_lora_span_count",
        "drop_reason",
        "duration_ms",
        "elapsed_ms",
        "editor_session_id",
        "error_type",
        "feature_profile_id",
        "fresh",
        "freshness_mismatch_count",
        "freshness_mismatch_fields",
        "operation",
        "outcome_status",
        "pending_document_view_present",
        "pending_render_plan_present",
        "cube_context_id",
        "query_identity",
        "query_result_count",
        "queued_age_ms",
        "reason",
        "render_plan_lora_span_count",
        "request_id",
        "request_count",
        "result_count",
        "scene_context_id",
        "source_length",
        "source_revision",
        "stale_outcome",
    }
)
_ALLOWED_CONTEXT_SUFFIXES = (
    "_count",
    "_duration_ms",
    "_elapsed_ms",
    "_generation",
    "_identity",
    "_length",
    "_ms",
    "_present",
    "_reason",
    "_revision",
    "_status",
)
_FORBIDDEN_FIELD_FRAGMENTS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "exception",
    "file",
    "password",
    "path",
    "prompt",
    "secret",
    "selected",
    "source",
    "text",
    "token",
    "trigger",
    "value",
)
_TEXT_LENGTH_FIELD_NAMES = frozenset({"current_source_length", "source_length"})


def prompt_async_identity_log_fields(
    identity: PromptAsyncResultIdentity,
) -> dict[str, object]:
    """Return prompt-safe structured fields from async result identity."""

    return {
        "request_id": identity.request_id,
        "editor_session_id": identity.editor_session_id,
        "source_revision": identity.source_revision,
        "source_length": identity.source_length,
        "feature_profile_id": identity.feature_profile_id,
        "scene_context_id": identity.scene_context_id,
        "cube_context_id": identity.cube_context_id,
        "query_identity": identity.query_identity,
        "cancellation_generation": identity.cancellation_generation,
    }


def prompt_async_context_log_fields(
    context: PromptAsyncRequestContext,
) -> dict[str, object]:
    """Return prompt-safe structured fields from one async request context."""

    fields: dict[str, object] = {
        "operation": context.operation,
        "reason": context.reason,
    }
    fields.update(_validated_context_fields(context.safe_fields))
    return fields


def prompt_async_request_log_fields(
    request: PromptAsyncRequest[TResult],
) -> dict[str, object]:
    """Return prompt-safe structured fields from one async request."""

    return {
        **prompt_async_identity_log_fields(request.identity),
        **prompt_async_context_log_fields(request.context),
    }


def prompt_async_outcome_log_fields(
    outcome: PromptAsyncTaskOutcome[TResult],
) -> dict[str, object]:
    """Return prompt-safe structured fields from one async task outcome."""

    fields = {
        **prompt_async_identity_log_fields(outcome.identity),
        **prompt_async_context_log_fields(outcome.context),
        "outcome_status": _outcome_status(outcome),
    }
    if outcome.error is not None:
        fields.update(prompt_async_error_log_fields(outcome.error))
    return fields


def prompt_async_freshness_log_fields(
    decision: PromptFreshnessDecision,
) -> dict[str, object]:
    """Return prompt-safe structured fields from a freshness decision."""

    return {
        "fresh": decision.is_fresh,
        "drop_reason": decision.drop_reason,
        "freshness_mismatch_count": len(decision.mismatches),
        "freshness_mismatch_fields": ",".join(
            mismatch.field_name for mismatch in decision.mismatches
        ),
    }


def prompt_async_error_log_fields(error: BaseException) -> dict[str, object]:
    """Return prompt-safe error fields without serializing exception messages."""

    return {"error_type": type(error).__name__}


def log_prompt_async_debug(
    logger: logging.Logger,
    event: str,
    **safe_fields: object,
) -> None:
    """Log a debug async event after validating prompt-safe context fields."""

    log_debug(logger, event, **_validated_context_fields(safe_fields.items()))


def log_prompt_async_warning(
    logger: logging.Logger,
    event: str,
    *,
    error: BaseException | None = None,
    **safe_fields: object,
) -> None:
    """Log a warning async event with prompt-safe fields and optional traceback."""

    fields = _validated_context_fields(safe_fields.items())
    if error is not None:
        fields.update(prompt_async_error_log_fields(error))
        logged_error = _PromptAsyncLoggedError(type(error).__name__).with_traceback(
            error.__traceback__
        )
        exc_info = (type(logged_error), logged_error, error.__traceback__)
        logger.warning(_format_log_message(event, fields), exc_info=exc_info)
        return
    log_warning(logger, event, **fields)


def _validated_context_fields(
    fields: Mapping[str, object] | Iterable[tuple[str, object]],
) -> dict[str, object]:
    """Validate prompt-safe context field names before logging."""

    if isinstance(fields, Mapping):
        items: Iterable[tuple[str, object]] = fields.items()
    else:
        items = fields

    validated: dict[str, object] = {}
    for field_name, value in items:
        _require_prompt_safe_field_name(field_name)
        validated[field_name] = value
    return validated


def _require_prompt_safe_field_name(field_name: str) -> None:
    """Reject context field names likely to carry prompt content or secrets."""

    normalized = field_name.strip().lower().replace("-", "_")
    if not normalized:
        raise ValueError("log field name must not be blank.")
    if normalized in _TEXT_LENGTH_FIELD_NAMES:
        return
    if normalized in _ALLOWED_CONTEXT_FIELD_NAMES:
        return
    forbidden_fragments = [
        fragment for fragment in _FORBIDDEN_FIELD_FRAGMENTS if fragment in normalized
    ]
    if forbidden_fragments:
        raise ValueError(f"log field is not prompt-safe: {field_name}")
    if normalized.endswith(_ALLOWED_CONTEXT_SUFFIXES):
        return
    raise ValueError(f"log field is not recognized as prompt-safe: {field_name}")


class _PromptAsyncLoggedError(RuntimeError):
    """Carry traceback context without serializing original exception text."""


def _outcome_status(
    outcome: PromptAsyncTaskOutcome[TResult],
) -> PromptAsyncOutcomeStatus:
    """Return one compact status label for a task outcome."""

    if outcome.cancelled:
        return "cancelled"
    if outcome.error is not None:
        return "failed"
    return "completed"


def _format_log_message(event: str, context: Mapping[str, object]) -> str:
    """Format a warning message without using the generic context serializer."""

    if not context:
        return event
    suffix = " ".join(f"{key}={value}" for key, value in sorted(context.items()))
    return f"{event} | {suffix}"


__all__ = [
    "PromptAsyncOutcomeStatus",
    "log_prompt_async_debug",
    "log_prompt_async_warning",
    "prompt_async_context_log_fields",
    "prompt_async_error_log_fields",
    "prompt_async_freshness_log_fields",
    "prompt_async_identity_log_fields",
    "prompt_async_outcome_log_fields",
    "prompt_async_request_log_fields",
]
