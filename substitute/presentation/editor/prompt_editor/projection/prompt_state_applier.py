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

"""Apply prepared prompt state through projection-owned controllers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

from PySide6.QtCore import QObject
from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.qt_lifecycle import qt_object_is_alive
from substitute.shared.logging.logger import (
    get_logger,
    log_warning_exception,
)

from .applicator import PromptProjectionApplicator
from .freshness_controller import (
    PromptProjectionFreshnessBlockers,
    PromptProjectionFreshnessController,
)
from .incremental_apply_controller import (
    PromptProjectionApplyPath,
    PromptProjectionIncrementalApplyController,
    PromptProjectionApplyViewport,
)
from .layout_engine import PromptProjectionLayout
from .model import (
    PromptProjectionCaretState,
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from .session import PromptProjectionSession
from .update_scheduler import PendingProjectionUpdate

_LOGGER = get_logger("presentation.editor.prompt_editor.projection_prompt_state")


@dataclass(frozen=True, slots=True)
class PromptProjectionPromptStateApplyOutcome:
    """Describe how one prompt-state update was handled."""

    apply_path: PromptProjectionApplyPath
    source_revision: int
    update_source_revision: int | None = None


class PromptProjectionPromptStateHost(Protocol):
    """Expose surface-owned sinks needed for prompt-state application."""

    _projection_applicator: PromptProjectionApplicator
    _projection_freshness_controller: PromptProjectionFreshnessController
    _incremental_apply_controller: PromptProjectionIncrementalApplyController
    _document_view: PromptDocumentView
    _render_plan: PromptSyntaxRenderPlan
    _projection_document: PromptProjectionDocument
    _active_projection_document: PromptProjectionDocument
    _display_mode: PromptProjectionDisplayMode
    _session: PromptProjectionSession
    _scene_error_keys: frozenset[str]
    _source_revision: int
    _cursor_state: PromptProjectionCaretState
    _anchor_state: PromptProjectionCaretState
    _caret_visibility_prompt_state_revision: int | None
    _last_rendered_active_span_range: tuple[int, int] | None
    _layout: PromptProjectionLayout

    @property
    def cursor_position(self) -> int:
        """Return the current source cursor position."""

    @property
    def anchor_position(self) -> int:
        """Return the current source anchor position."""

    def viewport(self) -> PromptProjectionApplyViewport:
        """Return the projection viewport sink."""

    def _visible_scroll_bar(self) -> object:
        """Ensure scrollbar state is available before projection changes."""

    def _active_span_range(self) -> tuple[int, int] | None:
        """Return the active source span range."""

    def _decoration_accent_ranges(self) -> tuple[tuple[int, int], ...]:
        """Return source ranges that should receive decoration accents."""

    def _projection_freshness_blockers(self) -> PromptProjectionFreshnessBlockers:
        """Return current projection modes that block source-state scheduling."""

    def _log_projection_state_event(
        self,
        event_name: str,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        source_changed: bool,
        can_schedule_safe_typing: bool,
        can_schedule_metadata: bool,
        apply_path: str,
        update_source_revision: int | None = None,
    ) -> None:
        """Emit one projection state diagnostic event."""

    def _ensure_caret_visible(self) -> None:
        """Ensure the committed caret is visible."""

    def _rebuild_projection(self) -> None:
        """Run the surface-owned full projection rebuild sink."""

    def _rebuild_active_projection(self, *, commit_projection: bool = False) -> None:
        """Rebuild the active projection document after committed state changes."""

    def start_exact_weight_edit(self, token: PromptProjectionToken) -> None:
        """Start exact weight editing for one projected token."""

    def update_exact_weight_edit(
        self,
        *,
        buffer_text: str,
        caret_index: int,
        select_all: bool,
    ) -> None:
        """Update the active exact weight edit buffer."""


class PromptProjectionPromptStateApplier:
    """Own prompt-state scheduling and apply-path selection."""

    def __init__(self, host: PromptProjectionPromptStateHost) -> None:
        """Create an applier around a projection surface sink."""

        self._host = host

    def set_prompt_state(
        self,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
    ) -> PromptProjectionPromptStateApplyOutcome:
        """Apply or schedule a prepared prompt-state snapshot."""

        host = self._host
        if not qt_object_is_alive(cast(QObject, host)):
            return PromptProjectionPromptStateApplyOutcome(
                apply_path=PromptProjectionApplyPath.DROPPED_STALE,
                source_revision=host._source_revision,
            )
        source_changed = document_view.source_text != host._document_view.source_text
        semantics_changed = (
            render_plan.document_semantics_identity
            != host._render_plan.document_semantics_identity
        )
        can_schedule_safe_typing = (
            host._projection_freshness_controller.can_schedule_prompt_state_projection(
                host._projection_freshness_blockers()
            )
        )
        can_schedule_metadata = host._projection_freshness_controller.can_schedule_metadata_prompt_state_projection(
            host._projection_freshness_blockers()
        )
        host._log_projection_state_event(
            "prompt_projection_state.received",
            document_view=document_view,
            render_plan=render_plan,
            source_changed=source_changed,
            can_schedule_safe_typing=can_schedule_safe_typing,
            can_schedule_metadata=can_schedule_metadata,
            apply_path="received",
        )
        if can_schedule_safe_typing:
            previous_document_view = host._document_view
            previous_render_plan = host._render_plan
            host._document_view = document_view
            host._render_plan = render_plan
            host._projection_freshness_controller.schedule_safe_typing_update(
                document_view=document_view,
                render_plan=render_plan,
                source_revision=host._source_revision,
                previous_document_view=previous_document_view,
                previous_render_plan=previous_render_plan,
            )
            host._log_projection_state_event(
                "prompt_projection_state.scheduled",
                document_view=document_view,
                render_plan=render_plan,
                source_changed=source_changed,
                can_schedule_safe_typing=can_schedule_safe_typing,
                can_schedule_metadata=can_schedule_metadata,
                apply_path="scheduled_safe_typing",
                update_source_revision=host._source_revision,
            )
            return PromptProjectionPromptStateApplyOutcome(
                apply_path=PromptProjectionApplyPath.SCHEDULED,
                source_revision=host._source_revision,
                update_source_revision=host._source_revision,
            )
        if (
            not source_changed
            and document_view == host._document_view
            and render_plan != host._render_plan
            and can_schedule_metadata
        ):
            host._projection_freshness_controller.schedule_metadata_update(
                document_view=document_view,
                render_plan=render_plan,
                source_revision=host._source_revision,
            )
            host._log_projection_state_event(
                "prompt_projection_state.scheduled",
                document_view=document_view,
                render_plan=render_plan,
                source_changed=source_changed,
                can_schedule_safe_typing=can_schedule_safe_typing,
                can_schedule_metadata=can_schedule_metadata,
                apply_path="scheduled_metadata",
                update_source_revision=host._source_revision,
            )
            return PromptProjectionPromptStateApplyOutcome(
                apply_path=PromptProjectionApplyPath.SCHEDULED,
                source_revision=host._source_revision,
                update_source_revision=host._source_revision,
            )
        if (
            not source_changed
            and not semantics_changed
            and render_plan.syntax_spans == host._render_plan.syntax_spans
            and host._projection_document.source_text == document_view.source_text
            and host._projection_freshness_controller.has_pending_update()
        ):
            host._document_view = document_view
            host._render_plan = render_plan
            host._log_projection_state_event(
                "prompt_projection_state.scheduled",
                document_view=document_view,
                render_plan=render_plan,
                source_changed=source_changed,
                can_schedule_safe_typing=can_schedule_safe_typing,
                can_schedule_metadata=can_schedule_metadata,
                apply_path="scheduled_pending_projection",
                update_source_revision=host._source_revision,
            )
            return PromptProjectionPromptStateApplyOutcome(
                apply_path=PromptProjectionApplyPath.SCHEDULED,
                source_revision=host._source_revision,
                update_source_revision=host._source_revision,
            )
        if (
            not source_changed
            and not semantics_changed
            and render_plan.syntax_spans == host._render_plan.syntax_spans
            and host._projection_freshness_controller.has_pending_update()
            and host._projection_freshness_controller.has_stale_projection_geometry()
        ):
            previous_document_view = host._document_view
            previous_render_plan = host._render_plan
            host._document_view = document_view
            host._render_plan = render_plan
            host._projection_freshness_controller.schedule_safe_typing_update(
                document_view=document_view,
                render_plan=render_plan,
                source_revision=host._source_revision,
                previous_document_view=previous_document_view,
                previous_render_plan=previous_render_plan,
            )
            host._log_projection_state_event(
                "prompt_projection_state.scheduled",
                document_view=document_view,
                render_plan=render_plan,
                source_changed=source_changed,
                can_schedule_safe_typing=can_schedule_safe_typing,
                can_schedule_metadata=can_schedule_metadata,
                apply_path="scheduled_stale_projection",
                update_source_revision=host._source_revision,
            )
            return PromptProjectionPromptStateApplyOutcome(
                apply_path=PromptProjectionApplyPath.SCHEDULED,
                source_revision=host._source_revision,
                update_source_revision=host._source_revision,
            )
        if (
            not source_changed
            and not semantics_changed
            and render_plan.syntax_spans == host._render_plan.syntax_spans
            and host._projection_document.source_text == document_view.source_text
        ):
            host._projection_freshness_controller.clear_pending_after_immediate_apply()
            host._document_view = document_view
            host._render_plan = render_plan
            host._log_projection_state_event(
                "prompt_projection_state.applied",
                document_view=document_view,
                render_plan=render_plan,
                source_changed=source_changed,
                can_schedule_safe_typing=can_schedule_safe_typing,
                can_schedule_metadata=can_schedule_metadata,
                apply_path="paint_only",
            )
            return PromptProjectionPromptStateApplyOutcome(
                apply_path=PromptProjectionApplyPath.PAINT_ONLY,
                source_revision=host._source_revision,
            )
        if self.try_apply_prompt_state_without_geometry_rebuild(
            document_view,
            render_plan,
            source_changed=source_changed,
        ):
            host._log_projection_state_event(
                "prompt_projection_state.applied",
                document_view=document_view,
                render_plan=render_plan,
                source_changed=source_changed,
                can_schedule_safe_typing=can_schedule_safe_typing,
                can_schedule_metadata=can_schedule_metadata,
                apply_path="paint_only",
            )
            return PromptProjectionPromptStateApplyOutcome(
                apply_path=PromptProjectionApplyPath.PAINT_ONLY,
                source_revision=host._source_revision,
            )
        host._projection_freshness_controller.clear_pending_after_immediate_apply()
        return self.apply_prompt_state_projection(document_view, render_plan)

    def try_apply_prompt_state_without_geometry_rebuild(
        self,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        *,
        source_changed: bool,
    ) -> bool:
        """Apply prompt state directly when projection geometry is identical."""

        host = self._host
        if (
            render_plan.document_semantics_identity
            != host._render_plan.document_semantics_identity
        ):
            return False
        if render_plan.syntax_spans != host._render_plan.syntax_spans:
            return False
        active_span_range = host._active_span_range()
        result = (
            host._projection_applicator.apply_prompt_state_without_geometry_rebuild(
                document_view,
                render_plan,
                source_changed=source_changed,
                display_mode=host._display_mode,
                session=host._session,
                active_span_range=active_span_range,
                decoration_accent_ranges=host._decoration_accent_ranges(),
                scene_error_keys=host._scene_error_keys,
                current_document=host._projection_document,
                layout=host._layout,
            )
        )
        if result is None:
            return False

        host._visible_scroll_bar()
        host._projection_freshness_controller.clear_pending_after_immediate_apply()
        host._document_view = document_view
        host._render_plan = render_plan
        host._projection_document = result.projection_document
        host._last_rendered_active_span_range = result.active_span_range
        host._active_projection_document = host._projection_document
        self._apply_pending_auto_exact_weight_edit()
        host.viewport().update()
        return True

    def apply_scheduled_projection_update(
        self,
        update: PendingProjectionUpdate,
    ) -> PromptProjectionPromptStateApplyOutcome:
        """Apply one scheduled prompt projection update if it is current."""

        host = self._host
        if not qt_object_is_alive(cast(QObject, host)):
            return PromptProjectionPromptStateApplyOutcome(
                apply_path=PromptProjectionApplyPath.DROPPED_STALE,
                source_revision=host._source_revision,
                update_source_revision=update.source_revision,
            )
        if update.source_revision != host._source_revision:
            host._log_projection_state_event(
                "prompt_projection_state.dropped",
                document_view=update.document_view,
                render_plan=update.render_plan,
                source_changed=(
                    update.document_view.source_text != host._document_view.source_text
                ),
                can_schedule_safe_typing=host._projection_freshness_controller.can_schedule_prompt_state_projection(
                    host._projection_freshness_blockers()
                ),
                can_schedule_metadata=(
                    host._projection_freshness_controller.can_schedule_metadata_prompt_state_projection(
                        host._projection_freshness_blockers()
                    )
                ),
                apply_path="drop_revision_mismatch",
                update_source_revision=update.source_revision,
            )
            return PromptProjectionPromptStateApplyOutcome(
                apply_path=PromptProjectionApplyPath.DROPPED_STALE,
                source_revision=host._source_revision,
                update_source_revision=update.source_revision,
            )
        host._visible_scroll_bar()
        try:
            if update.reason == "safe_typing":
                applied_without_rebuild = (
                    self.try_apply_prompt_state_without_geometry_rebuild(
                        update.document_view,
                        update.render_plan,
                        source_changed=False,
                    )
                )
                if applied_without_rebuild:
                    host._log_projection_state_event(
                        "prompt_projection_state.applied",
                        document_view=update.document_view,
                        render_plan=update.render_plan,
                        source_changed=False,
                        can_schedule_safe_typing=(
                            host._projection_freshness_controller.can_schedule_prompt_state_projection(
                                host._projection_freshness_blockers()
                            )
                        ),
                        can_schedule_metadata=(
                            host._projection_freshness_controller.can_schedule_metadata_prompt_state_projection(
                                host._projection_freshness_blockers()
                            )
                        ),
                        apply_path="paint_only",
                        update_source_revision=update.source_revision,
                    )
                    return PromptProjectionPromptStateApplyOutcome(
                        apply_path=PromptProjectionApplyPath.PAINT_ONLY,
                        source_revision=host._source_revision,
                        update_source_revision=update.source_revision,
                    )
            return self.apply_prompt_state_projection(
                update.document_view,
                update.render_plan,
                previous_render_plan_for_fast_path=update.previous_render_plan,
                update_source_revision=update.source_revision,
            )
        except Exception as error:
            log_warning_exception(
                _LOGGER,
                "Scheduled prompt projection update failed",
                error=error,
                reason=update.reason,
                source_revision=update.source_revision,
                current_source_revision=host._source_revision,
            )
            if (
                update.previous_document_view is not None
                and update.previous_render_plan is not None
            ):
                host._document_view = update.previous_document_view
                host._render_plan = update.previous_render_plan
            return PromptProjectionPromptStateApplyOutcome(
                apply_path=PromptProjectionApplyPath.FAILED,
                source_revision=host._source_revision,
                update_source_revision=update.source_revision,
            )

    def apply_prompt_state_projection(
        self,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        *,
        previous_render_plan_for_fast_path: PromptSyntaxRenderPlan | None = None,
        update_source_revision: int | None = None,
    ) -> PromptProjectionPromptStateApplyOutcome:
        """Apply semantic prompt state through incremental-first fallbacks."""

        host = self._host
        if not qt_object_is_alive(cast(QObject, host)):
            return PromptProjectionPromptStateApplyOutcome(
                apply_path=PromptProjectionApplyPath.DROPPED_STALE,
                source_revision=host._source_revision,
                update_source_revision=update_source_revision,
            )
        host._visible_scroll_bar()
        previous_document_view = host._document_view
        previous_render_plan = host._render_plan
        host._document_view = document_view
        host._render_plan = render_plan
        fast_insert_applied = False
        scheduled_incremental_applied = False
        refresh_caret_visibility = (
            host._caret_visibility_prompt_state_revision == host._source_revision
        )
        try:
            host._session.collapse_if_cursor_left_token(
                document_view,
                selection_start=min(host.cursor_position, host.anchor_position),
                selection_end=max(host.cursor_position, host.anchor_position),
            )
            previous_fast_render_plan = (
                previous_render_plan_for_fast_path or previous_render_plan
            )
            if host._incremental_apply_controller.can_apply_fast_trailing_insert_for_prompt_state(
                render_plan,
                previous_render_plan=previous_fast_render_plan,
            ):
                fast_insert_applied = host._incremental_apply_controller.try_apply_fast_trailing_plain_insert_projection(
                    document_view=document_view,
                    render_plan=render_plan,
                )
            if not fast_insert_applied:
                scheduled_incremental_applied = host._incremental_apply_controller.try_apply_scheduled_incremental_prompt_state_projection(
                    document_view=document_view,
                    render_plan=render_plan,
                    previous_render_plan=previous_fast_render_plan,
                )
            if not fast_insert_applied and not scheduled_incremental_applied:
                host._rebuild_projection()
            apply_path = (
                PromptProjectionApplyPath.FAST_TRAILING
                if fast_insert_applied
                else (
                    PromptProjectionApplyPath.INCREMENTAL
                    if scheduled_incremental_applied
                    else PromptProjectionApplyPath.FULL_REBUILD
                )
            )
            host._log_projection_state_event(
                "prompt_projection_state.applied",
                document_view=document_view,
                render_plan=render_plan,
                source_changed=(
                    document_view.source_text != previous_document_view.source_text
                ),
                can_schedule_safe_typing=host._projection_freshness_controller.can_schedule_prompt_state_projection(
                    host._projection_freshness_blockers()
                ),
                can_schedule_metadata=(
                    host._projection_freshness_controller.can_schedule_metadata_prompt_state_projection(
                        host._projection_freshness_blockers()
                    )
                ),
                apply_path=apply_path.value,
                update_source_revision=update_source_revision,
            )
            if refresh_caret_visibility:
                host._ensure_caret_visible()
                host._caret_visibility_prompt_state_revision = None
            if fast_insert_applied or scheduled_incremental_applied:
                host._rebuild_active_projection(commit_projection=True)
            self._apply_pending_auto_exact_weight_edit()
            return PromptProjectionPromptStateApplyOutcome(
                apply_path=apply_path,
                source_revision=host._source_revision,
                update_source_revision=update_source_revision,
            )
        except Exception as error:
            host._document_view = previous_document_view
            host._render_plan = previous_render_plan
            log_warning_exception(
                _LOGGER,
                "Prompt projection state apply failed",
                error=error,
                source_length=len(document_view.source_text),
                previous_source_length=len(previous_document_view.source_text),
            )
            raise

    def _apply_pending_auto_exact_weight_edit(self) -> None:
        """Start exact edit for a token created by typed literal reclassification."""

        host = self._host
        pending = host._session.pending_auto_exact_weight_edit
        if pending is None:
            return
        if pending.source_text != host._projection_document.source_text:
            host._session.clear_pending_auto_exact_weight_edit()
            return
        for token in host._projection_document.tokens:
            if (
                token.kind is not PromptProjectionTokenKind.EMPHASIS
                or token.content_start is None
                or token.content_end is None
                or token.value_text is None
            ):
                continue
            weight_start = token.content_end + 1
            weight_end = token.source_end - 1
            if not weight_start <= pending.cursor_position <= weight_end:
                continue
            caret_index = max(
                0,
                min(len(token.value_text), pending.cursor_position - weight_start),
            )
            host.start_exact_weight_edit(token)
            host.update_exact_weight_edit(
                buffer_text=token.value_text,
                caret_index=caret_index,
                select_all=False,
            )
            return
        host._session.clear_pending_auto_exact_weight_edit()


__all__ = [
    "PromptProjectionPromptStateApplier",
    "PromptProjectionPromptStateApplyOutcome",
    "PromptProjectionPromptStateHost",
]
