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

"""Tests for prompt reorder cancellation on external text changes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptMutationService,
    PromptSyntaxProfile,
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAsyncRequest,
    PromptAsyncResultIdentity,
    PromptEditorTaskHandle,
    PromptSemanticRefreshController,
    PromptSemanticRefreshRequest,
    PromptSemanticRefreshResult,
    PromptStaleResultGuard,
)
from substitute.presentation.editor.prompt_editor.models import (
    PromptEditorInteractionMode,
    SegmentReorderSession,
)
from tests.prompt_autocomplete_test_helpers import prompt_syntax_profile
from tests.prompt_reorder_interaction_test_helpers import (
    ControllerEditorDouble,
    MenuCursorDouble,
    OverlayDouble,
    autocomplete_double,
    prompt_interaction_controller,
    syntax_renderer_double,
    syntax_service,
)


def test_handle_text_changed_cancels_active_reorder_mode_before_refreshing_prompt_state() -> (
    None
):
    """External text changes invalidate reorder mode before prompt refresh."""

    document_service = PromptDocumentService()
    syntax_profile = prompt_syntax_profile("emphasis", "wildcard")
    resolved_syntax_service = syntax_service()
    controller_holder: list[Any] = []
    semantic_refresh_controller = _semantic_refresh_controller_for_test(
        controller_provider=lambda: controller_holder[0],
        document_service=document_service,
        syntax_service=resolved_syntax_service,
        syntax_profile=syntax_profile,
    )
    editor = ControllerEditorDouble(
        clicked_cursor=MenuCursorDouble(text="alpha, beta", position=0),
        current_cursor=MenuCursorDouble(text="alpha, beta", position=0),
        text="alpha, beta",
    )
    controller = prompt_interaction_controller(
        editor,
        autocomplete=autocomplete_double(),
        semantic_refresh_controller=semantic_refresh_controller,
        syntax_renderers=syntax_renderer_double(),
        document_service=document_service,
        mutation_service=PromptMutationService(),
        syntax_service_=resolved_syntax_service,
        syntax_profile=syntax_profile,
    )
    controller_holder.append(controller)
    semantic_refresh_controller._host = controller._syntax_state
    overlay = OverlayDouble([1, 0], active_segment_index=1, has_reordered=True)
    controller._reorder._segment_overlay = overlay
    controller._reorder._interaction_mode = PromptEditorInteractionMode.SEGMENT_REORDER
    controller._reorder._session_controller.replace_session(
        SegmentReorderSession(
            is_active=True,
            original_ordered_indices=(0, 1),
            current_ordered_indices=(0, 1),
            active_segment_index=1,
            selection_start=0,
            selection_end=0,
        )
    )
    editor.setPlainText("gamma, delta")

    controller.handle_text_changed()
    controller.flush_pending_semantic_refresh(reason="test")

    assert overlay.cancel_drag_calls == 1
    assert overlay.closed == 1
    assert overlay.deleted == 1
    assert controller.segment_overlay is None
    assert controller.document_view.source_text == "gamma, delta"


class _ImmediateSemanticDebouncer:
    """Provide deterministic semantic refresh debounce behavior."""

    def __init__(self) -> None:
        """Initialize pending callback storage."""

        self.pending_callback: Callable[[], None] | None = None

    @property
    def is_pending(self) -> bool:
        """Return whether a semantic refresh callback is queued."""

        return self.pending_callback is not None

    def request(self, callback: Callable[[], None], *, reason: str) -> None:
        """Store the latest semantic refresh callback."""

        _ = reason
        self.pending_callback = callback

    def flush(self, *, reason: str) -> bool:
        """Run the latest callback immediately."""

        _ = reason
        callback = self.pending_callback
        self.pending_callback = None
        if callback is None:
            return False
        callback()
        return True

    def cancel(self, *, reason: str) -> bool:
        """Drop any queued semantic refresh callback."""

        _ = reason
        had_callback = self.pending_callback is not None
        self.pending_callback = None
        return had_callback


class _UnusedSemanticTaskHandle(PromptEditorTaskHandle[PromptSemanticRefreshResult]):
    """Fail if this reorder text-change test submits background work."""

    @property
    def identity(self) -> PromptAsyncResultIdentity:
        """Return no identity because task submission is unexpected."""

        raise AssertionError("semantic refresh task submission was unexpected")

    @property
    def is_finished(self) -> bool:
        """Return no finished state because task submission is unexpected."""

        raise AssertionError("semantic refresh task submission was unexpected")

    def add_done_callback(
        self,
        callback: Callable[..., None],
        *,
        reason: str,
    ) -> None:
        """Fail if task completion is wired for this prepared request."""

        _ = callback, reason
        raise AssertionError("semantic refresh task submission was unexpected")

    def cancel(self, *, reason: str) -> None:
        """Fail if task cancellation is requested for this prepared request."""

        _ = reason
        raise AssertionError("semantic refresh task submission was unexpected")


class _SemanticRequestChannel:
    """Record cancellation while rejecting unexpected task submission."""

    def __init__(self) -> None:
        """Initialize cancellation tracking."""

        self.cancel_reasons: list[str] = []

    def submit_latest(
        self,
        request: PromptAsyncRequest[PromptSemanticRefreshResult],
    ) -> _UnusedSemanticTaskHandle:
        """Fail because handle_text_changed supplies a prepared semantic request."""

        _ = request
        raise AssertionError("semantic refresh task submission was unexpected")

    def cancel_pending(self, *, reason: str) -> None:
        """Record request-channel cancellation."""

        self.cancel_reasons.append(reason)


class _DeferredSemanticRefreshHost:
    """Delegate semantic refresh callbacks to a controller after construction."""

    def __init__(self, controller_provider: Callable[[], Any]) -> None:
        """Store the provider used to resolve the constructed test controller."""

        self._controller_provider = controller_provider

    def current_semantic_source_text(self) -> str:
        """Return the editor source text that semantic refresh must match."""

        return cast(str, self._controller_provider().current_semantic_source_text())

    def current_semantic_document_source_text(self) -> str:
        """Return the source text represented by the current semantic snapshot."""

        return cast(
            str,
            self._controller_provider().current_semantic_document_source_text(),
        )

    def current_semantic_async_identity(
        self,
        *,
        request_id: int,
    ) -> PromptAsyncResultIdentity:
        """Return current editor identity for one semantic refresh request."""

        return cast(
            PromptAsyncResultIdentity,
            self._controller_provider().current_semantic_async_identity(
                request_id=request_id
            ),
        )

    def apply_fresh_semantic_refresh(
        self,
        request: PromptSemanticRefreshRequest,
    ) -> None:
        """Adopt one semantic request after freshness checks pass."""

        self._controller_provider().apply_fresh_semantic_refresh(request)


def _semantic_refresh_controller_for_test(
    *,
    controller_provider: Callable[[], Any],
    document_service: PromptDocumentService,
    syntax_service: PromptSyntaxService,
    syntax_profile: PromptSyntaxProfile,
) -> PromptSemanticRefreshController:
    """Build a semantic refresh controller for reorder text-change behavior."""

    return PromptSemanticRefreshController(
        host=cast(Any, _DeferredSemanticRefreshHost(controller_provider)),
        document_service=document_service,
        syntax_service=syntax_service,
        syntax_profile=syntax_profile,
        request_channel=_SemanticRequestChannel(),
        debouncer=_ImmediateSemanticDebouncer(),
        stale_result_guard=PromptStaleResultGuard(),
    )
