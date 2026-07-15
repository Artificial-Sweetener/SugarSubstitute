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

"""Define protocol-only prompt editor async execution boundary types."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass
from typing import Generic, Protocol, TypeAlias, TypeVar

from substitute.application.execution import (
    CancellationToken,
    ExecutionContext,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskStatus,
    TaskTimings,
    TaskWork,
)

TResult = TypeVar("TResult")
PromptEditorCancellationToken: TypeAlias = CancellationToken
PromptAsyncWork: TypeAlias = TaskWork[TResult]

PROMPT_EDITOR_EXECUTION_DOMAIN = "prompt_editor"
PROMPT_EDITOR_EXECUTION_LANE = "prompt_editor"


class PromptEditorTaskHandle(Protocol, Generic[TResult]):
    """Describe a submitted prompt-editor async task."""

    @property
    def identity(self) -> "PromptAsyncResultIdentity":
        """Return the identity associated with this submitted task."""

    @property
    def is_finished(self) -> bool:
        """Return whether the task has finished or been abandoned."""

    @property
    def outcome(self) -> "PromptAsyncTaskOutcome[TResult] | None":
        """Return the completed task outcome when execution has settled."""

    def add_done_callback(
        self,
        callback: Callable[["PromptAsyncTaskOutcome[TResult]"], None],
        *,
        reason: str,
    ) -> None:
        """Publish one callback after this task completes."""

    def cancel(self, *, reason: str) -> None:
        """Request cancellation of this task with a prompt-safe reason."""


class PromptEditorExecutor(Protocol):
    """Submit prompt-editor async work through a replaceable boundary."""

    def submit(
        self,
        request: "PromptAsyncRequest[TResult]",
        *,
        cancellation: PromptEditorCancellationToken,
    ) -> PromptEditorTaskHandle[TResult]:
        """Submit one request and return a handle owned by the execution boundary."""


@dataclass(frozen=True, slots=True)
class PromptAsyncResultIdentity:
    """Carry request identity needed by later stale-result checks."""

    request_id: int
    editor_session_id: Hashable | None = None
    source_revision: int | None = None
    source_length: int | None = None
    feature_profile_id: Hashable | None = None
    scene_context_id: Hashable | None = None
    cube_context_id: Hashable | None = None
    query_identity: Hashable | None = None
    cancellation_generation: int | None = None

    def __post_init__(self) -> None:
        """Reject negative identity components before async code trusts them."""

        _require_non_negative(self.request_id, field_name="request_id")
        _require_optional_non_negative(
            self.source_revision,
            field_name="source_revision",
        )
        _require_optional_non_negative(self.source_length, field_name="source_length")
        _require_optional_non_negative(
            self.cancellation_generation,
            field_name="cancellation_generation",
        )


@dataclass(frozen=True, slots=True)
class PromptAsyncRequestContext:
    """Describe prompt-safe diagnostic context for one async request."""

    operation: str
    reason: str
    safe_fields: tuple[tuple[str, object], ...] = ()

    def __post_init__(self) -> None:
        """Reject blank context labels and unsafe field names."""

        _require_non_blank(self.operation, field_name="operation")
        _require_non_blank(self.reason, field_name="reason")
        for field_name, _value in self.safe_fields:
            _require_non_blank(field_name, field_name="safe_fields field name")


@dataclass(frozen=True, slots=True)
class PromptAsyncRequest(Generic[TResult]):
    """Describe one unit of async work without executing it during construction."""

    identity: PromptAsyncResultIdentity
    context: PromptAsyncRequestContext
    work: PromptAsyncWork[TResult]


@dataclass(frozen=True, slots=True)
class PromptAsyncTaskOutcome(Generic[TResult]):
    """Carry one completed task outcome without raising on publication."""

    identity: PromptAsyncResultIdentity
    context: PromptAsyncRequestContext
    result: TResult | None = None
    error: BaseException | None = None
    cancelled: bool = False

    def __post_init__(self) -> None:
        """Reject outcome states that would make publication ambiguous."""

        if self.cancelled and self.error is not None:
            raise ValueError("cancelled outcomes must not carry an error.")
        if self.cancelled and self.result is not None:
            raise ValueError("cancelled outcomes must not carry a result.")
        if self.error is not None and self.result is not None:
            raise ValueError("failed outcomes must not carry a result.")


def _require_non_negative(value: int, *, field_name: str) -> None:
    """Reject negative integer identity fields."""

    if value < 0:
        raise ValueError(f"{field_name} must be non-negative.")


def _require_optional_non_negative(
    value: int | None,
    *,
    field_name: str,
) -> None:
    """Reject negative optional integer identity fields."""

    if value is not None:
        _require_non_negative(value, field_name=field_name)


def _require_non_blank(value: str, *, field_name: str) -> None:
    """Reject blank request context labels."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank.")


def prompt_task_request_from_async(
    request: PromptAsyncRequest[TResult],
) -> TaskRequest[TResult]:
    """Map a prompt async request into the shared execution request shape."""

    return TaskRequest(
        identity=prompt_task_identity_from_async(request.identity),
        context=prompt_execution_context_from_async(request.context),
        work=request.work,
    )


def prompt_task_identity_from_async(
    identity: PromptAsyncResultIdentity,
) -> TaskIdentity:
    """Map prompt identity fields into generic execution identity parts."""

    parts: list[tuple[str, object]] = []
    for field_name in (
        "editor_session_id",
        "source_revision",
        "source_length",
        "feature_profile_id",
        "scene_context_id",
        "cube_context_id",
        "query_identity",
    ):
        value = getattr(identity, field_name)
        if value is not None:
            parts.append((field_name, value))
    return TaskIdentity(
        request_id=identity.request_id,
        domain=PROMPT_EDITOR_EXECUTION_DOMAIN,
        parts=tuple(parts),
        cancellation_generation=identity.cancellation_generation or 0,
    )


def prompt_async_identity_from_task(
    identity: TaskIdentity,
) -> PromptAsyncResultIdentity:
    """Map generic execution identity back to the prompt async identity shape."""

    if identity.domain != PROMPT_EDITOR_EXECUTION_DOMAIN:
        raise ValueError("task identity does not belong to the prompt editor domain.")
    return PromptAsyncResultIdentity(
        request_id=identity.request_id,
        editor_session_id=identity.field_value("editor_session_id"),
        source_revision=_optional_int_field(identity, "source_revision"),
        source_length=_optional_int_field(identity, "source_length"),
        feature_profile_id=identity.field_value("feature_profile_id"),
        scene_context_id=identity.field_value("scene_context_id"),
        cube_context_id=identity.field_value("cube_context_id"),
        query_identity=identity.field_value("query_identity"),
        cancellation_generation=identity.cancellation_generation,
    )


def prompt_execution_context_from_async(
    context: PromptAsyncRequestContext,
) -> ExecutionContext:
    """Build sanitized generic context for the shared execution lane."""

    return ExecutionContext(
        operation=context.operation,
        reason=context.reason,
        lane=PROMPT_EDITOR_EXECUTION_LANE,
        safe_fields=_approved_generic_safe_fields(context.safe_fields),
    )


def prompt_async_context_from_execution(
    context: ExecutionContext,
) -> PromptAsyncRequestContext:
    """Map generic execution context back to prompt async diagnostic context."""

    return PromptAsyncRequestContext(
        operation=context.operation,
        reason=context.reason,
        safe_fields=context.safe_fields,
    )


def prompt_async_outcome_from_task(
    request: PromptAsyncRequest[TResult],
    outcome: TaskOutcome[TResult],
) -> PromptAsyncTaskOutcome[TResult]:
    """Convert one shared task outcome into the prompt-editor outcome shape."""

    if outcome.status == "cancelled":
        return PromptAsyncTaskOutcome(
            identity=request.identity,
            context=request.context,
            cancelled=True,
        )
    if outcome.status == "failed":
        return PromptAsyncTaskOutcome(
            identity=request.identity,
            context=request.context,
            error=outcome.error,
        )
    return PromptAsyncTaskOutcome(
        identity=request.identity,
        context=request.context,
        result=outcome.result,
    )


def prompt_task_outcome_from_async(
    outcome: PromptAsyncTaskOutcome[TResult],
    *,
    identity: TaskIdentity,
    context: ExecutionContext,
    timings: TaskTimings = TaskTimings(),
) -> TaskOutcome[TResult]:
    """Convert one prompt async outcome into the generic execution outcome shape."""

    status: TaskStatus
    if outcome.cancelled:
        status = "cancelled"
    elif outcome.error is not None:
        status = "failed"
    else:
        status = "succeeded"
    return TaskOutcome(
        identity=identity,
        context=context,
        status=status,
        result=outcome.result if status == "succeeded" else None,
        error=outcome.error if status == "failed" else None,
        timings=timings,
        cancellation_reason="prompt_request_cancelled"
        if status == "cancelled"
        else None,
    )


def _approved_generic_safe_fields(
    safe_fields: tuple[tuple[str, object], ...],
) -> tuple[tuple[str, object], ...]:
    """Keep only prompt fields accepted by generic execution diagnostics."""

    approved_names = {
        "cache_key",
        "generation",
        "operation",
        "request_id",
        "source_length",
        "storage_key",
    }
    return tuple(
        (field_name, value)
        for field_name, value in safe_fields
        if field_name in approved_names
    )


def _optional_int_field(identity: TaskIdentity, field_name: str) -> int | None:
    """Return one optional integer identity part."""

    value = identity.field_value(field_name)
    if value is None:
        return None
    if not isinstance(value, int):
        raise TypeError(f"{field_name} must be an int when present.")
    return value


__all__ = [
    "PROMPT_EDITOR_EXECUTION_DOMAIN",
    "PROMPT_EDITOR_EXECUTION_LANE",
    "PromptAsyncWork",
    "PromptAsyncRequest",
    "PromptAsyncRequestContext",
    "PromptAsyncResultIdentity",
    "PromptAsyncTaskOutcome",
    "PromptEditorCancellationToken",
    "PromptEditorExecutor",
    "PromptEditorTaskHandle",
    "prompt_async_context_from_execution",
    "prompt_async_identity_from_task",
    "prompt_async_outcome_from_task",
    "prompt_execution_context_from_async",
    "prompt_task_identity_from_async",
    "prompt_task_outcome_from_async",
    "prompt_task_request_from_async",
]
