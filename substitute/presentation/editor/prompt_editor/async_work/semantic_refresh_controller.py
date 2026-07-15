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

"""Coordinate stale-safe prompt semantic refresh through async primitives."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from time import perf_counter
from typing import Protocol

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptDocumentView,
    PromptLoraRendererView,
    PromptSyntaxProfile,
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
)
from substitute.shared.logging.logger import get_logger, log_debug

from .debounce import PromptEditorDebouncer, QtPromptEditorDebouncer
from .execution import (
    PromptAsyncRequest,
    PromptAsyncRequestContext,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
)
from .observability import (
    prompt_async_error_log_fields,
    prompt_async_freshness_log_fields,
)
from .request_channel import PromptEditorRequestChannel, PromptLatestWinsRequestChannel
from .stale_result_guard import (
    PromptFreshnessDecision,
    PromptFreshnessField,
    PromptStaleResultGuard,
)
from .task_executor import PromptEditorTaskExecutor
from .semantic_refresh_result import (
    PromptSemanticRefreshResult,
    build_semantic_refresh_result,
)

_LOGGER = get_logger(
    "presentation.editor.prompt_editor.async_work.semantic_refresh_controller"
)
_SEMANTIC_REFRESH_OPERATION = "semantic_refresh"
_TASK_COMPLETION_REASON = "semantic_refresh_task_completed"


@dataclass(frozen=True, slots=True)
class PromptSemanticRefreshRequest:
    """Carry one semantic refresh request without prompt text in log context."""

    identity: PromptAsyncResultIdentity
    reason: str
    source_text: str
    prepared_document_view: PromptDocumentView | None
    prepared_render_plan: PromptSyntaxRenderPlan | None
    coalesced_count: int
    queued_at: float
    submitted_at: float | None = None


class _PromptSemanticRefreshLoggedError(RuntimeError):
    """Carry a prompt-safe task failure message for traceback logging."""


class PromptSemanticRefreshHost(Protocol):
    """Describe the widget-facing callbacks used by semantic refresh."""

    def current_semantic_source_text(self) -> str:
        """Return the editor source text that semantic refresh must match."""

    def current_semantic_document_source_text(self) -> str:
        """Return the source text represented by the current semantic snapshot."""

    def current_semantic_async_identity(
        self,
        *,
        request_id: int,
    ) -> PromptAsyncResultIdentity:
        """Return current editor identity for one semantic refresh request."""

    def apply_fresh_semantic_refresh(
        self,
        request: PromptSemanticRefreshRequest,
    ) -> None:
        """Adopt one request after the controller proves freshness."""


class PromptSemanticRefreshController:
    """Own semantic refresh debounce, execution, cancellation, and freshness."""

    def __init__(
        self,
        *,
        host: PromptSemanticRefreshHost,
        document_service: PromptDocumentService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
        request_channel: PromptEditorRequestChannel[PromptSemanticRefreshResult],
        debouncer: PromptEditorDebouncer,
        stale_result_guard: PromptStaleResultGuard | None = None,
        shutdown_callback: Callable[[], None] | None = None,
    ) -> None:
        """Store collaborators used to schedule semantic refresh work."""

        self._host = host
        self._document_service = document_service
        self._syntax_service = syntax_service
        self._syntax_profile = syntax_profile
        self._request_channel = request_channel
        self._debouncer = debouncer
        self._stale_result_guard = stale_result_guard or PromptStaleResultGuard()
        self._shutdown_callback = shutdown_callback
        self._next_request_id = 0
        self._pending_request: PromptSemanticRefreshRequest | None = None
        self._active_task_identity: PromptAsyncResultIdentity | None = None

    def queue_source_changed(
        self,
        source_text: str,
        *,
        reason: str,
        prepared_document_view: PromptDocumentView | None = None,
        prepared_render_plan: PromptSyntaxRenderPlan | None = None,
    ) -> None:
        """Queue the latest source text for debounced semantic refresh."""

        previous_request = self._pending_request
        request = self._build_request(
            reason=reason,
            source_text=source_text,
            prepared_document_view=prepared_document_view,
            prepared_render_plan=prepared_render_plan,
            coalesced_count=(
                0 if previous_request is None else previous_request.coalesced_count + 1
            ),
        )
        self._pending_request = request
        log_debug(
            _LOGGER,
            "prompt_semantic_refresh.queued",
            reason=reason,
            **semantic_refresh_request_context(request),
            active_task_count=self._active_task_count(),
        )
        self._debouncer.request(
            lambda: self._submit_pending(reason="scheduled"),
            reason=reason,
        )

    def flush(self, *, reason: str) -> None:
        """Synchronously apply the latest semantic refresh when required."""

        self._debouncer.cancel(reason=reason)
        request = self._pending_request
        if request is None:
            source_text = self._host.current_semantic_source_text()
            if source_text == self._host.current_semantic_document_source_text():
                return
            request = self._build_request(
                reason=reason,
                source_text=source_text,
                prepared_document_view=None,
                prepared_render_plan=None,
                coalesced_count=0,
            )
        self._pending_request = None
        self._request_channel.cancel_pending(reason=reason)
        self._active_task_identity = None
        log_debug(
            _LOGGER,
            "prompt_semantic_refresh.flushed",
            reason=reason,
            **semantic_refresh_request_context(request),
            active_task_count=self._active_task_count(),
        )
        self._publish_prepared_request_if_fresh(request)

    def cancel_pending(self, *, reason: str) -> None:
        """Drop queued or active semantic refresh work."""

        self._pending_request = None
        self._debouncer.cancel(reason=reason)
        self._request_channel.cancel_pending(reason=reason)
        self._active_task_identity = None

    def shutdown(self) -> None:
        """Cancel semantic work and release owned execution resources."""

        self.cancel_pending(reason="shutdown")
        if self._shutdown_callback is not None:
            self._shutdown_callback()

    def _submit_pending(self, *, reason: str) -> None:
        """Submit the latest pending semantic refresh through the request channel."""

        request = self._pending_request
        if request is None:
            return
        self._pending_request = None
        if request.prepared_document_view is not None:
            log_debug(
                _LOGGER,
                "prompt_semantic_refresh.submitted",
                reason=reason,
                submit_path="prepared_document_view",
                **semantic_refresh_request_context(request),
                active_task_count=self._active_task_count(),
            )
            self._publish_prepared_request_if_fresh(request)
            return

        submitted_request = replace(request, submitted_at=perf_counter())
        async_request = PromptAsyncRequest[PromptSemanticRefreshResult](
            identity=submitted_request.identity,
            context=PromptAsyncRequestContext(
                operation=_SEMANTIC_REFRESH_OPERATION,
                reason=reason,
                safe_fields=tuple(
                    semantic_refresh_request_context(submitted_request).items()
                ),
            ),
            work=lambda _token: build_semantic_refresh_result(
                source_text=submitted_request.source_text,
                document_service=self._document_service,
                syntax_service=self._syntax_service,
                syntax_profile=self._syntax_profile,
            ),
        )
        handle = self._request_channel.submit_latest(async_request)
        active_request = replace(submitted_request, identity=handle.identity)
        self._active_task_identity = handle.identity
        log_debug(
            _LOGGER,
            "prompt_semantic_refresh.submitted",
            reason=reason,
            submit_path="background_task",
            **semantic_refresh_request_context(active_request),
            active_task_count=self._active_task_count(),
        )
        handle.add_done_callback(
            lambda outcome: self._handle_task_completed(active_request, outcome),
            reason=_TASK_COMPLETION_REASON,
        )

    def _handle_task_completed(
        self,
        request: PromptSemanticRefreshRequest,
        outcome: PromptAsyncTaskOutcome[PromptSemanticRefreshResult],
    ) -> None:
        """Apply a completed semantic refresh result when it is still current."""

        active_identity_for_freshness = self._active_task_identity
        self._clear_active_task_identity_if_current(outcome.identity)
        log_debug(
            _LOGGER,
            "prompt_semantic_refresh.completed",
            **semantic_refresh_request_context(request),
            active_task_count=self._active_task_count(),
        )
        if outcome.cancelled:
            log_debug(
                _LOGGER,
                "prompt_semantic_refresh.dropped",
                drop_reason="cancelled",
                **semantic_refresh_request_context(request),
                active_task_count=self._active_task_count(),
            )
            return
        if outcome.error is not None:
            self._log_task_failure(request=request, error=outcome.error)
            log_debug(
                _LOGGER,
                "prompt_semantic_refresh.dropped",
                drop_reason="task_error",
                **semantic_refresh_request_context(request),
                active_task_count=self._active_task_count(),
                **prompt_async_error_log_fields(outcome.error),
            )
            return
        if outcome.result is None:
            log_debug(
                _LOGGER,
                "prompt_semantic_refresh.dropped",
                drop_reason="invalid_result",
                **semantic_refresh_request_context(request),
                active_task_count=self._active_task_count(),
            )
            return

        result_request = replace(
            request,
            identity=outcome.identity,
            prepared_document_view=outcome.result.document_view,
            prepared_render_plan=outcome.result.render_plan,
        )
        self._publish_prepared_request_if_fresh(
            result_request,
            active_identity=active_identity_for_freshness,
        )

    def _publish_prepared_request_if_fresh(
        self,
        request: PromptSemanticRefreshRequest,
        *,
        active_identity: PromptAsyncResultIdentity | None = None,
    ) -> None:
        """Publish a prepared request only after identity and source checks pass."""

        decision = self._freshness_decision(
            request.identity,
            active_identity=active_identity,
        )
        if not decision.is_fresh:
            log_debug(
                _LOGGER,
                "prompt_semantic_refresh.dropped",
                **semantic_refresh_request_context(request),
                **prompt_async_freshness_log_fields(decision),
                active_task_count=self._active_task_count(),
            )
            return
        current_text = self._host.current_semantic_source_text()
        if current_text != request.source_text:
            log_debug(
                _LOGGER,
                "prompt_semantic_refresh.dropped",
                drop_reason="text_changed",
                current_source_length=len(current_text),
                **semantic_refresh_request_context(request),
                active_task_count=self._active_task_count(),
            )
            return
        self._host.apply_fresh_semantic_refresh(request)
        log_debug(
            _LOGGER,
            "prompt_semantic_refresh.applied",
            **semantic_refresh_request_context(request),
            active_task_count=self._active_task_count(),
        )

    def _freshness_decision(
        self,
        result_identity: PromptAsyncResultIdentity,
        *,
        active_identity: PromptAsyncResultIdentity | None = None,
    ) -> PromptFreshnessDecision:
        """Return whether an async identity still matches current editor state."""

        current_identity = self._host.current_semantic_async_identity(
            request_id=result_identity.request_id
        )
        expected_identity = active_identity or self._active_task_identity
        if expected_identity is not None:
            current_identity = replace(
                current_identity,
                cancellation_generation=expected_identity.cancellation_generation,
            )
        return self._stale_result_guard.validate(
            result_identity=result_identity,
            current_identity=current_identity,
            required_fields=_required_freshness_fields(
                result_identity,
                current_identity,
            ),
        )

    def _build_request(
        self,
        *,
        reason: str,
        source_text: str,
        prepared_document_view: PromptDocumentView | None,
        prepared_render_plan: PromptSyntaxRenderPlan | None,
        coalesced_count: int,
    ) -> PromptSemanticRefreshRequest:
        """Create the next semantic refresh request with current source identity."""

        request_id = self._next_request_id + 1
        self._next_request_id = request_id
        identity = self._host.current_semantic_async_identity(request_id=request_id)
        if identity.source_length is None:
            identity = replace(identity, source_length=len(source_text))
        return PromptSemanticRefreshRequest(
            identity=identity,
            reason=reason,
            source_text=source_text,
            prepared_document_view=prepared_document_view,
            prepared_render_plan=prepared_render_plan,
            coalesced_count=coalesced_count,
            queued_at=perf_counter(),
        )

    def _active_task_count(self) -> int:
        """Return whether the latest submitted semantic task may still publish."""

        return int(self._active_task_identity is not None)

    def _clear_active_task_identity_if_current(
        self,
        identity: PromptAsyncResultIdentity,
    ) -> None:
        """Clear the active task identity after its completion callback starts."""

        if self._active_task_identity == identity:
            self._active_task_identity = None

    def _log_task_failure(
        self,
        *,
        request: PromptSemanticRefreshRequest,
        error: BaseException,
    ) -> None:
        """Log task failure with traceback but without exception text."""

        safe_error = _PromptSemanticRefreshLoggedError(type(error).__name__)
        safe_error = safe_error.with_traceback(error.__traceback__)
        fields = {
            **semantic_refresh_request_context(request),
            **prompt_async_error_log_fields(error),
            "active_task_count": self._active_task_count(),
        }
        suffix = " ".join(f"{key}={value}" for key, value in sorted(fields.items()))
        _LOGGER.warning(
            f"Prompt semantic refresh task failed | {suffix}",
            exc_info=(type(safe_error), safe_error, safe_error.__traceback__),
        )


def build_prompt_semantic_refresh_controller(
    *,
    host: PromptSemanticRefreshHost,
    document_service: PromptDocumentService,
    syntax_service: PromptSyntaxService,
    syntax_profile: PromptSyntaxProfile,
    executor: PromptEditorTaskExecutor,
) -> PromptSemanticRefreshController:
    """Build the Qt-backed semantic refresh controller for production wiring."""

    request_channel: PromptLatestWinsRequestChannel[PromptSemanticRefreshResult] = (
        PromptLatestWinsRequestChannel(executor=executor)
    )
    return PromptSemanticRefreshController(
        host=host,
        document_service=document_service,
        syntax_service=syntax_service,
        syntax_profile=syntax_profile,
        request_channel=request_channel,
        debouncer=QtPromptEditorDebouncer(interval_ms=0),
        stale_result_guard=PromptStaleResultGuard(),
        shutdown_callback=lambda: executor.shutdown(
            wait=False,
            cancel_futures=True,
        ),
    )


def semantic_refresh_request_context(
    request: PromptSemanticRefreshRequest,
) -> dict[str, object]:
    """Return prompt-safe structured context for one semantic refresh request."""

    fields: dict[str, object] = {
        "request_id": request.identity.request_id,
        "request_reason": request.reason,
        "editor_session_id": request.identity.editor_session_id,
        "source_revision": request.identity.source_revision,
        "source_length": len(request.source_text),
        "feature_profile_id": request.identity.feature_profile_id,
        "scene_context_id": request.identity.scene_context_id,
        "cube_context_id": request.identity.cube_context_id,
        "cancellation_generation": request.identity.cancellation_generation,
        "pending_document_view_present": request.prepared_document_view is not None,
        "pending_render_plan_present": request.prepared_render_plan is not None,
        "coalesced_count": request.coalesced_count,
        "queued_age_ms": _rounded_ms(_elapsed_ms_since(request.queued_at)),
        "elapsed_ms": _rounded_ms(_elapsed_ms_since(request.queued_at)),
        "document_lora_span_count": _document_lora_span_count(
            request.prepared_document_view
        ),
        "render_plan_lora_span_count": _render_plan_lora_span_count(
            request.prepared_render_plan
        ),
    }
    if request.submitted_at is not None:
        fields["duration_ms"] = _rounded_ms(_elapsed_ms_since(request.submitted_at))
    return fields


def _required_freshness_fields(
    result_identity: PromptAsyncResultIdentity,
    current_identity: PromptAsyncResultIdentity,
) -> tuple[PromptFreshnessField, ...]:
    """Return the fields available for one semantic freshness proof."""

    fields: list[PromptFreshnessField] = ["request_id", "editor_session_id"]
    if (
        result_identity.source_revision is not None
        or current_identity.source_revision is not None
    ):
        fields.append("source_revision")
    if (
        result_identity.feature_profile_id is not None
        or current_identity.feature_profile_id is not None
    ):
        fields.append("feature_profile_id")
    if (
        result_identity.scene_context_id is not None
        or current_identity.scene_context_id is not None
    ):
        fields.append("scene_context_id")
    if (
        result_identity.cube_context_id is not None
        or current_identity.cube_context_id is not None
    ):
        fields.append("cube_context_id")
    if (
        result_identity.cancellation_generation is not None
        or current_identity.cancellation_generation is not None
    ):
        fields.append("cancellation_generation")
    return tuple(fields)


def _elapsed_ms_since(started_at: float) -> float:
    """Return elapsed milliseconds since a monotonic timestamp."""

    return max(0.0, (perf_counter() - started_at) * 1000.0)


def _rounded_ms(milliseconds: float) -> float:
    """Return a stable millisecond value for prompt-safe logs."""

    return round(milliseconds, 3)


def _document_lora_span_count(document_view: PromptDocumentView | None) -> int:
    """Return the LoRA span count in a document view when available."""

    if document_view is None:
        return 0
    return len(document_view.lora_spans)


def _render_plan_lora_span_count(render_plan: PromptSyntaxRenderPlan | None) -> int:
    """Return the renderer-ready LoRA span count in a render plan when available."""

    if render_plan is None:
        return 0
    renderer_view = render_plan.renderer_view_for_kind("lora")
    if not isinstance(renderer_view, PromptLoraRendererView):
        return 0
    return len(renderer_view.lora_spans)


__all__ = [
    "PromptSemanticRefreshController",
    "PromptSemanticRefreshHost",
    "PromptSemanticRefreshRequest",
    "build_prompt_semantic_refresh_controller",
    "semantic_refresh_request_context",
]
