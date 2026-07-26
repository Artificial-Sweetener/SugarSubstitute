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
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.state.editor_state import (
    PromptEditorDocumentState,
)
from substitute.presentation.editor.prompt_editor.core.state.semantic_state import (
    PromptEditorSemanticSnapshot,
)
from substitute.presentation.editor.prompt_editor.qt_lifecycle import qt_object_is_alive
from substitute.shared.logging.logger import (
    get_logger,
    log_warning_exception,
)

from .applicator import PromptProjectionApplicator
from .frame_state import PromptProjectionFrameStatePublisher
from .freshness_controller import (
    PromptProjectionFreshnessBlockers,
    PromptProjectionFreshnessController,
)
from .edit_pipeline_contracts import PromptProjectionApplyPath
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .prompt_state_projection_strategy import PromptStateProjectionStrategy
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
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
    _active_projection_document: PromptProjectionDocument
    _display_mode: PromptProjectionDisplayMode
    _session: PromptProjectionSession
    _scene_error_keys: frozenset[str]
    _cursor_state: PromptProjectionCaretState
    _anchor_state: PromptProjectionCaretState
    _caret_visibility_prompt_state_revision: int | None
    _last_rendered_active_span_range: tuple[int, int] | None
    _layout: PromptLayoutEditToFrameCoordinator

    @property
    def _editor_state(
        self,
    ) -> PromptEditorDocumentState[
        PromptDocumentView,
        PromptSyntaxRenderPlan,
        PromptProjectionDocument,
    ]:
        """Return the revisioned prompt document state."""

    @property
    def cursor_position(self) -> int:
        """Return the current source cursor position."""

    @property
    def anchor_position(self) -> int:
        """Return the current source anchor position."""

    def viewport(self) -> QWidget:
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

    def __init__(
        self,
        host: PromptProjectionPromptStateHost,
        *,
        frame_state: PromptProjectionFrameStatePublisher,
        strategy: PromptStateProjectionStrategy,
    ) -> None:
        """Create an applier around a projection surface sink."""

        self._host = host
        self._frame_state = frame_state
        self._strategy = strategy

    def set_prompt_state(
        self,
        snapshot: PromptEditorSemanticSnapshot,
    ) -> PromptProjectionPromptStateApplyOutcome:
        """Apply or schedule a prepared prompt-state snapshot."""

        host = self._host
        document_view = snapshot.document
        render_plan = snapshot.render_plan
        if not qt_object_is_alive(cast(QObject, host)):
            return PromptProjectionPromptStateApplyOutcome(
                apply_path=PromptProjectionApplyPath.DROPPED_STALE,
                source_revision=host._editor_state.source.source_revision,
            )
        projection_semantic = host._editor_state.projection_semantic
        source_changed = (
            document_view.source_text != projection_semantic.document.source_text
        )
        semantics_changed = (
            render_plan.document_semantics_identity
            != projection_semantic.render_plan.document_semantics_identity
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
        previous_snapshot = projection_semantic
        if (
            document_view is projection_semantic.document
            and render_plan is projection_semantic.render_plan
            and host._editor_state.projection.document.source_text
            == document_view.source_text
        ):
            host._projection_freshness_controller.clear_pending_after_immediate_apply()
            self._publish_rebased_projection_lineage(snapshot)
            host._log_projection_state_event(
                "prompt_projection_state.applied",
                document_view=document_view,
                render_plan=render_plan,
                source_changed=False,
                can_schedule_safe_typing=can_schedule_safe_typing,
                can_schedule_metadata=can_schedule_metadata,
                apply_path="identity_rebase",
            )
            return PromptProjectionPromptStateApplyOutcome(
                apply_path=PromptProjectionApplyPath.PAINT_ONLY,
                source_revision=host._editor_state.source.source_revision,
            )
        if can_schedule_safe_typing:
            host._projection_freshness_controller.schedule_safe_typing_update(
                snapshot=snapshot,
                previous_snapshot=previous_snapshot,
            )
            host._log_projection_state_event(
                "prompt_projection_state.scheduled",
                document_view=document_view,
                render_plan=render_plan,
                source_changed=source_changed,
                can_schedule_safe_typing=can_schedule_safe_typing,
                can_schedule_metadata=can_schedule_metadata,
                apply_path="scheduled_safe_typing",
                update_source_revision=host._editor_state.source.source_revision,
            )
            return PromptProjectionPromptStateApplyOutcome(
                apply_path=PromptProjectionApplyPath.SCHEDULED,
                source_revision=host._editor_state.source.source_revision,
                update_source_revision=host._editor_state.source.source_revision,
            )
        if (
            not source_changed
            and render_plan != projection_semantic.render_plan
            and render_plan.syntax_spans == projection_semantic.render_plan.syntax_spans
            and host._editor_state.projection.document.source_text
            == document_view.source_text
            and can_schedule_metadata
        ):
            host._projection_freshness_controller.schedule_metadata_update(
                snapshot=snapshot,
            )
            host._log_projection_state_event(
                "prompt_projection_state.scheduled",
                document_view=document_view,
                render_plan=render_plan,
                source_changed=source_changed,
                can_schedule_safe_typing=can_schedule_safe_typing,
                can_schedule_metadata=can_schedule_metadata,
                apply_path="scheduled_metadata",
                update_source_revision=host._editor_state.source.source_revision,
            )
            return PromptProjectionPromptStateApplyOutcome(
                apply_path=PromptProjectionApplyPath.SCHEDULED,
                source_revision=host._editor_state.source.source_revision,
                update_source_revision=host._editor_state.source.source_revision,
            )
        if (
            not source_changed
            and not semantics_changed
            and render_plan.syntax_spans == projection_semantic.render_plan.syntax_spans
            and host._editor_state.projection.document.source_text
            == document_view.source_text
            and host._projection_freshness_controller.has_pending_update()
        ):
            host._log_projection_state_event(
                "prompt_projection_state.scheduled",
                document_view=document_view,
                render_plan=render_plan,
                source_changed=source_changed,
                can_schedule_safe_typing=can_schedule_safe_typing,
                can_schedule_metadata=can_schedule_metadata,
                apply_path="scheduled_pending_projection",
                update_source_revision=host._editor_state.source.source_revision,
            )
            return PromptProjectionPromptStateApplyOutcome(
                apply_path=PromptProjectionApplyPath.SCHEDULED,
                source_revision=host._editor_state.source.source_revision,
                update_source_revision=host._editor_state.source.source_revision,
            )
        if (
            not source_changed
            and not semantics_changed
            and render_plan.syntax_spans == projection_semantic.render_plan.syntax_spans
            and host._projection_freshness_controller.has_pending_update()
            and host._projection_freshness_controller.has_stale_projection_geometry()
        ):
            host._projection_freshness_controller.schedule_safe_typing_update(
                snapshot=snapshot,
                previous_snapshot=previous_snapshot,
            )
            host._log_projection_state_event(
                "prompt_projection_state.scheduled",
                document_view=document_view,
                render_plan=render_plan,
                source_changed=source_changed,
                can_schedule_safe_typing=can_schedule_safe_typing,
                can_schedule_metadata=can_schedule_metadata,
                apply_path="scheduled_stale_projection",
                update_source_revision=host._editor_state.source.source_revision,
            )
            return PromptProjectionPromptStateApplyOutcome(
                apply_path=PromptProjectionApplyPath.SCHEDULED,
                source_revision=host._editor_state.source.source_revision,
                update_source_revision=host._editor_state.source.source_revision,
            )
        if (
            not source_changed
            and not semantics_changed
            and render_plan.syntax_spans == projection_semantic.render_plan.syntax_spans
            and host._editor_state.projection.document.source_text
            == document_view.source_text
        ):
            host._projection_freshness_controller.clear_pending_after_immediate_apply()
            self._publish_rebased_projection_lineage(snapshot)
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
                source_revision=host._editor_state.source.source_revision,
            )
        if self.try_apply_prompt_state_without_geometry_rebuild(
            snapshot,
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
                source_revision=host._editor_state.source.source_revision,
            )
        host._projection_freshness_controller.clear_pending_after_immediate_apply()
        return self.apply_prompt_state_projection(snapshot)

    def try_apply_prompt_state_without_geometry_rebuild(
        self,
        snapshot: PromptEditorSemanticSnapshot,
        *,
        source_changed: bool,
    ) -> bool:
        """Apply prompt state directly when projection geometry is identical."""

        host = self._host
        document_view = snapshot.document
        render_plan = snapshot.render_plan
        if (
            render_plan.document_semantics_identity
            != host._editor_state.projection_semantic.render_plan.document_semantics_identity
        ):
            return False
        if (
            render_plan.syntax_spans
            != host._editor_state.projection_semantic.render_plan.syntax_spans
        ):
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
                current_document=host._editor_state.projection.document,
                frame=host._layout.frame,
            )
        )
        if result is None:
            return False

        host._visible_scroll_bar()
        host._projection_freshness_controller.clear_pending_after_immediate_apply()
        host._editor_state.stage_edit_semantic(snapshot)
        host._editor_state.publish_projection(result.projection_document)
        host._last_rendered_active_span_range = result.active_span_range
        host._active_projection_document = host._editor_state.projection.document
        self._frame_state.publish_layout(host._layout.frame.output)
        self._frame_state.publish_prepared_paint(
            host._layout.frame.output,
            host._layout.frame.paint_state,
        )
        self._apply_pending_auto_exact_weight_edit()
        host.viewport().update()
        return True

    def _publish_rebased_projection_lineage(
        self,
        snapshot: PromptEditorSemanticSnapshot,
    ) -> None:
        """Rebind unchanged projection and geometry to equivalent semantic state."""

        host = self._host
        projection_document = host._editor_state.projection.document
        host._editor_state.stage_edit_semantic(snapshot)
        host._editor_state.publish_projection(projection_document)
        host._active_projection_document = projection_document
        self._frame_state.publish_layout(host._layout.frame.output)
        self._frame_state.publish_prepared_paint(
            host._layout.frame.output,
            host._layout.frame.paint_state,
        )

    def apply_scheduled_projection_update(
        self,
        update: PendingProjectionUpdate,
    ) -> PromptProjectionPromptStateApplyOutcome:
        """Apply one scheduled prompt projection update if it is current."""

        host = self._host
        if not qt_object_is_alive(cast(QObject, host)):
            return PromptProjectionPromptStateApplyOutcome(
                apply_path=PromptProjectionApplyPath.DROPPED_STALE,
                source_revision=host._editor_state.source.source_revision,
                update_source_revision=update.source_revision,
            )
        if update.source_revision != host._editor_state.source.source_revision:
            host._log_projection_state_event(
                "prompt_projection_state.dropped",
                document_view=update.document_view,
                render_plan=update.render_plan,
                source_changed=(
                    update.document_view.source_text
                    != host._editor_state.projection_semantic.document.source_text
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
                source_revision=host._editor_state.source.source_revision,
                update_source_revision=update.source_revision,
            )
        host._visible_scroll_bar()
        try:
            if update.reason == "safe_typing":
                applied_without_rebuild = (
                    self.try_apply_prompt_state_without_geometry_rebuild(
                        update.snapshot,
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
                        source_revision=host._editor_state.source.source_revision,
                        update_source_revision=update.source_revision,
                    )
            return self.apply_prompt_state_projection(
                update.snapshot,
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
                current_source_revision=host._editor_state.source.source_revision,
            )
            return PromptProjectionPromptStateApplyOutcome(
                apply_path=PromptProjectionApplyPath.FAILED,
                source_revision=host._editor_state.source.source_revision,
                update_source_revision=update.source_revision,
            )

    def apply_prompt_state_projection(
        self,
        snapshot: PromptEditorSemanticSnapshot,
        *,
        previous_render_plan_for_fast_path: PromptSyntaxRenderPlan | None = None,
        update_source_revision: int | None = None,
    ) -> PromptProjectionPromptStateApplyOutcome:
        """Apply semantic prompt state through incremental-first fallbacks."""

        host = self._host
        document_view = snapshot.document
        render_plan = snapshot.render_plan
        if not qt_object_is_alive(cast(QObject, host)):
            return PromptProjectionPromptStateApplyOutcome(
                apply_path=PromptProjectionApplyPath.DROPPED_STALE,
                source_revision=host._editor_state.source.source_revision,
                update_source_revision=update_source_revision,
            )
        host._visible_scroll_bar()
        previous_snapshot = host._editor_state.projection_semantic
        previous_projection = host._editor_state.projection
        previous_document_view = previous_snapshot.document
        previous_render_plan = previous_snapshot.render_plan
        host._editor_state.stage_edit_semantic(snapshot)
        fast_insert_applied = False
        scheduled_incremental_applied = False
        refresh_caret_visibility = (
            host._caret_visibility_prompt_state_revision
            == host._editor_state.source.source_revision
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
            fast_insert_applied = self._strategy.try_trailing_insert(
                document_view=document_view,
                render_plan=render_plan,
                previous_render_plan=previous_fast_render_plan,
            )
            if not fast_insert_applied:
                scheduled_incremental_applied = self._strategy.try_incremental(
                    previous_text=previous_projection.document.source_text,
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
                source_revision=host._editor_state.source.source_revision,
                update_source_revision=update_source_revision,
            )
        except Exception as error:
            host._editor_state.restore_projection(previous_projection)
            host._editor_state.restore_projection_semantic(previous_snapshot)
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
        if pending.source_text != host._editor_state.projection.document.source_text:
            host._session.clear_pending_auto_exact_weight_edit()
            return
        for token in host._editor_state.projection.document.tokens:
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
