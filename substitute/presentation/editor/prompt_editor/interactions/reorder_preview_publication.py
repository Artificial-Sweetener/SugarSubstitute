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

"""Own scheduled reorder-preview construction and atomic publication."""

from __future__ import annotations

from collections.abc import Callable

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.reorder.preview_sync import (
    PromptReorderPreviewSyncContext,
    PromptReorderPreviewSyncState,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from ..projection.observability import (
    log_reorder_drag_timing,
    reorder_drag_started_at,
)
from ..projection.reorder_preview import PromptReorderPreviewState
from ..projection.reorder_preview_state_builder import (
    PromptReorderPreviewBuildRequest,
    PromptReorderPreviewStateBuilder,
)
from ..projection.reorder_projection_snapshot_provider import (
    PromptReorderPreviewProjectionProvider,
)
from .reorder_interaction_metrics import PromptReorderInteractionMetricsOwner
from .reorder_overlay_port import (
    PromptReorderOverlayPort,
    PromptReorderPreviewBuildFactsPort,
    PromptReorderPreviewSyncContextPort,
)
from .reorder_preview_sync import PromptReorderPreviewSyncController

_EMPTY_SYNC_CONTEXT = PromptReorderPreviewSyncContext(
    gesture_id=None,
    event_id=None,
    pointer_active=False,
    dragged_segment_index=None,
    base_drag_layout_ready=False,
    requires_immediate_drag_geometry=False,
    requires_initial_landing_shadow=False,
)


def _ignore_preview_sync_decision(_immediate: bool) -> None:
    """Ignore scheduler diagnostics when no reorder session is bound."""


class PromptReorderPreviewPublicationOwner:
    """Coordinate one bounded preview schedule and publication transaction."""

    DEFAULT_INTERVAL_MS = 16

    def __init__(
        self,
        *,
        clear_preview_state: Callable[[], None],
        current_document_view: Callable[[], PromptDocumentView],
        publish_preview_state: Callable[[PromptReorderPreviewState | None], None],
        source_identity: Callable[[], PromptSourceIdentity | None],
        viewport_width: Callable[[], int],
        document_service: PromptDocumentService,
        projection_provider: PromptReorderPreviewProjectionProvider,
        metrics: PromptReorderInteractionMetricsOwner,
        interval_ms: int,
    ) -> None:
        """Store stable inputs and construct the sole preview scheduler."""

        self._clear_preview_state = clear_preview_state
        self._current_document_view = current_document_view
        self._publish_preview_state = publish_preview_state
        self._source_identity = source_identity
        self._viewport_width = viewport_width
        self._projection_provider = projection_provider
        self._metrics = metrics
        self._state_builder = PromptReorderPreviewStateBuilder(
            document_service=document_service,
            projection_provider=projection_provider,
        )
        self._overlay: PromptReorderOverlayPort | None = None
        self._build_facts: PromptReorderPreviewBuildFactsPort | None = None
        self._sync_context: PromptReorderPreviewSyncContextPort | None = None
        self._publishing = False
        self._scheduler = PromptReorderPreviewSyncController(
            interval_ms=interval_ms,
            run_sync=self._sync_bound_session,
            pointer_revision=self._current_pointer_work_unit_id,
            record_scheduler_event=self._record_scheduler_event,
        )

    @property
    def publishing(self) -> bool:
        """Return whether editor and overlay state are publishing atomically."""

        return self._publishing

    @property
    def has_bound_session(self) -> bool:
        """Return whether one overlay session supplies preview authorities."""

        return self._overlay is not None

    @property
    def state(self) -> PromptReorderPreviewSyncState:
        """Return immutable scheduling state for diagnostics and focused tests."""

        return self._scheduler.state

    def bind_session(
        self,
        *,
        overlay: PromptReorderOverlayPort,
        build_facts: PromptReorderPreviewBuildFactsPort,
        sync_context: PromptReorderPreviewSyncContextPort,
    ) -> None:
        """Adopt one composed overlay session as the publication source."""

        self._overlay = overlay
        self._build_facts = build_facts
        self._sync_context = sync_context

    def unbind_session(self) -> None:
        """Release all authorities belonging to the finished overlay session."""

        self._overlay = None
        self._build_facts = None
        self._sync_context = None

    def has_pending(self) -> bool:
        """Return whether the latest-wins scheduler holds pending work."""

        return self._scheduler.has_pending()

    def reset(self, *, reason: str) -> None:
        """Clear painted state and cached projections for a new session."""

        self._clear_preview_state()
        self._projection_provider.clear_cache(reason=reason)

    def schedule(self, *, reason: str = "preview_changed") -> None:
        """Schedule one latest-wins preview publication."""

        overlay = self._overlay
        self._scheduler.schedule(
            reason=reason,
            context=self._current_sync_context(),
            record_decision=(
                _ignore_preview_sync_decision
                if overlay is None
                else self._metrics.record_preview_sync_decision
            ),
            record_elapsed=(
                None if overlay is None else self._metrics.record_preview_sync_elapsed
            ),
        )

    def flush(
        self,
        *,
        reason: str | None = None,
        forced: bool = False,
    ) -> None:
        """Publish the latest pending revision immediately."""

        overlay = self._overlay
        self._scheduler.flush_pending(
            reason=reason,
            forced=forced,
            context=self._current_sync_context(),
            record_elapsed=(
                None if overlay is None else self._metrics.record_preview_sync_elapsed
            ),
        )

    def close(self, *, reason: str) -> None:
        """Stop scheduling and clear projection cache for a finished session."""

        self._scheduler.clear()
        self._projection_provider.clear_cache(reason=reason)

    def clear_cache(self, *, reason: str) -> None:
        """Invalidate projection snapshots after an external source change."""

        self._projection_provider.clear_cache(reason=reason)

    def clear_published_state(self) -> None:
        """Clear the editor's preview after its covering overlay has closed."""

        self._clear_preview_state()

    def _sync_bound_session(self) -> None:
        """Build and atomically publish the currently bound overlay preview."""

        started_at = reorder_drag_started_at()
        overlay = self._overlay
        build_facts = self._build_facts
        if overlay is None or build_facts is None:
            self._clear_preview_state()
            log_reorder_drag_timing(
                "interaction.sync_preview.no_overlay",
                started_at=started_at,
                reason=self._scheduler.active_reason,
            )
            return

        overlay.flush_pending_autoscroll_invalidation(
            reason="autoscroll_coalesced_preview_sync"
        )
        facts = build_facts.snapshot()
        source_identity = self._source_identity()
        publication = self._state_builder.build(
            PromptReorderPreviewBuildRequest(
                document_view=self._current_document_view(),
                preview_layout_view=facts.preview_layout_view,
                base_drag_layout_view=facts.base_drag_layout_view,
                preview_reorder_state=facts.preview_reorder_state,
                base_drag_reorder_state=facts.base_drag_reorder_state,
                ordered_chip_indices=facts.ordered_chip_indices,
                dragged_segment_index=facts.dragged_segment_index,
                drop_target=facts.drop_target,
                source_revision=(
                    0 if source_identity is None else source_identity.source_revision
                ),
                viewport_width=self._viewport_width(),
                gesture_id=self._metrics.gesture_id,
                event_id=self._metrics.event_id,
                reason=self._scheduler.active_reason,
            ),
            record_render_plan_elapsed=self._metrics.record_render_plan_elapsed,
        )
        self._publishing = True
        try:
            if publication.preview_state is None:
                self._clear_preview_state()
            else:
                self._publish_preview_state(publication.preview_state)
            overlay.set_preview_snapshot(
                publication.preview_snapshot,
                base_drag_snapshot=publication.base_drag_snapshot,
                ordered_chip_indices=publication.ordered_chip_indices,
            )
        finally:
            self._publishing = False

    def _current_sync_context(self) -> PromptReorderPreviewSyncContext:
        """Return one composed scheduling generation or the immutable empty value."""

        owner = self._sync_context
        return _EMPTY_SYNC_CONTEXT if owner is None else owner.snapshot()

    def _current_pointer_work_unit_id(self) -> int | None:
        """Return the pointer revision only while a session is bound."""

        return None if self._overlay is None else self._metrics.work_unit_id

    def _record_scheduler_event(self, event: str) -> None:
        """Record scheduler classifications only for a bound session."""

        if self._overlay is not None:
            self._metrics.record_preview_scheduler(event)


__all__ = [
    "PromptReorderPreviewPublicationOwner",
]
