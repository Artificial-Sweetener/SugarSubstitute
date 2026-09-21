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

"""Own transient projection geometry and reusable paint-state publication."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget

from ..core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
    PromptProjectionInlinePreview,
    PromptProjectionTransientState,
)
from ..core.projection.caret import PromptProjectionSelection
from ..debug_probe import log_prompt_editor_probe
from ..qt_lifecycle import qt_object_is_alive
from .applicator import PromptProjectionApplicator
from .caret_geometry_owner import PromptProjectionCaretGeometryOwner
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .frame_state import (
    PromptProjectionEditorState,
    PromptProjectionFrameStatePublisher,
)
from .freshness_controller import PromptProjectionFreshnessController
from .session import PromptProjectionSession


class PromptActiveProjectionOwner:
    """Own the geometry-bearing projection and its rendered session paint identity."""

    def __init__(
        self,
        *,
        surface: QObject,
        viewport: QWidget,
        applicator: PromptProjectionApplicator,
        editor_state: PromptProjectionEditorState,
        session: PromptProjectionSession,
        layout: PromptLayoutEditToFrameCoordinator,
        frame_state: PromptProjectionFrameStatePublisher,
        freshness: PromptProjectionFreshnessController,
        caret_geometry: PromptProjectionCaretGeometryOwner,
        display_mode: Callable[[], PromptProjectionDisplayMode],
        selection: Callable[[], PromptProjectionSelection],
        cursor_position: Callable[[], int],
        reorder_active: Callable[[], bool],
        active_span_range: Callable[[], tuple[int, int] | None],
        decoration_accent_ranges: Callable[[], tuple[tuple[int, int], ...]],
        scene_error_keys: Callable[[], frozenset[str]],
        synchronize_layout: Callable[[bool], None],
        publish_render_frame: Callable[[], None],
        surface_state: Callable[[], dict[str, object]],
    ) -> None:
        """Store the authoritative state and effects for transient publication."""

        self._surface = surface
        self._viewport = viewport
        self._applicator = applicator
        self._editor_state = editor_state
        self._session = session
        self._layout = layout
        self._frame_state = frame_state
        self._freshness = freshness
        self._caret_geometry = caret_geometry
        self._display_mode = display_mode
        self._selection = selection
        self._cursor_position = cursor_position
        self._reorder_active = reorder_active
        self._active_span_range = active_span_range
        self._decoration_accent_ranges = decoration_accent_ranges
        self._scene_error_keys = scene_error_keys
        self._synchronize_layout = synchronize_layout
        self._publish_render_frame = publish_render_frame
        self._surface_state = surface_state
        self._document = editor_state.projection.document
        self._rendered_active_span_range: tuple[int, int] | None = None

    @property
    def document(self) -> PromptProjectionDocument:
        """Return the projection document currently represented by layout geometry."""

        return self._document

    @property
    def rendered_active_span_range(self) -> tuple[int, int] | None:
        """Return the active span represented by the prepared paint state."""

        return self._rendered_active_span_range

    def publish_rendered_active_span_range(
        self,
        active_span_range: tuple[int, int] | None,
    ) -> None:
        """Record the active span already represented by published paint state."""

        self._rendered_active_span_range = active_span_range

    def use_committed_projection(self) -> None:
        """Adopt the authoritative committed projection as the active document."""

        self._document = self._editor_state.projection.document

    def publish_committed_projection(
        self,
        *,
        active_span_range: tuple[int, int] | None,
    ) -> None:
        """Adopt a committed projection and its already-rendered active span."""

        self.use_committed_projection()
        self.publish_rendered_active_span_range(active_span_range)

    def rebuild(self, *, commit_projection: bool = False) -> None:
        """Publish the current transient projection, rebuilding geometry only when needed."""

        if not qt_object_is_alive(self._surface):
            return
        requires_layout = self.requires_layout()
        log_prompt_editor_probe(
            "surface.rebuild_active_projection.begin",
            commit_projection=commit_projection,
            requires_layout=requires_layout,
            surface=self._surface_state(),
        )
        if not requires_layout:
            self.restore_base_layout()
            self.refresh_paint_state()
            if commit_projection:
                self._synchronize_layout(True)
            log_prompt_editor_probe(
                "surface.rebuild_active_projection.paint_state_only",
                commit_projection=commit_projection,
                surface=self._surface_state(),
            )
            return
        active_span_range = self._current_active_span_range()
        self._rendered_active_span_range = active_span_range
        self._document = self._applicator.build_projection(
            self._editor_state.projection_semantic.document,
            self._editor_state.projection_semantic.render_plan,
            display_mode=self._display_mode(),
            session=self._session,
            active_span_range=active_span_range,
            decoration_accent_ranges=self._decoration_accent_ranges(),
            scene_error_keys=self._scene_error_keys(),
            transient_state=self.transient_state(),
        )
        self._layout.set_projection(
            self._document,
            prompt_document_view=self._editor_state.projection_semantic.document,
        )
        self._synchronize_layout(commit_projection)
        self._viewport.update()
        log_prompt_editor_probe(
            "surface.rebuild_active_projection.end",
            commit_projection=commit_projection,
            surface=self._surface_state(),
        )

    def refresh_paint_state(self) -> None:
        """Refresh geometry-neutral projection paint state from current session state."""

        self._refresh_paint_state_for(self._current_active_span_range())

    def reconcile_active_span(
        self,
        active_span_range: tuple[int, int] | None,
    ) -> None:
        """Publish paint state when the visible active syntax span changes."""

        if active_span_range == self._rendered_active_span_range:
            return
        if self._display_mode() is not PromptProjectionDisplayMode.PROJECTED:
            self._rendered_active_span_range = active_span_range
            return
        self._refresh_paint_state_for(active_span_range)

    def reconcile_current_active_span(self) -> None:
        """Reconcile active-span paint after caret state changes."""

        self.reconcile_active_span(self._current_active_span_range())

    def try_apply_current_session_paint_state(self) -> bool:
        """Apply session-only projection changes when layout geometry is unchanged."""

        result = self._applicator.apply_reusable_projection_paint_state(
            self._editor_state.projection_semantic.document,
            self._editor_state.projection_semantic.render_plan,
            display_mode=self._display_mode(),
            session=self._session,
            active_span_range=self._active_span_range(),
            decoration_accent_ranges=self._decoration_accent_ranges(),
            scene_error_keys=self._scene_error_keys(),
            frame=self._layout.frame,
        )
        if result is None:
            return False
        self._freshness.clear_pending_after_immediate_apply()
        self._editor_state.publish_projection(result.projection_document)
        self.publish_committed_projection(
            active_span_range=result.active_span_range,
        )
        self._frame_state.publish_prepared_paint(
            self._layout.frame.output,
            self._layout.frame.paint_state,
        )
        self._caret_geometry.clear_transient()
        self._publish_render_frame()
        self._viewport.update()
        return True

    def restore_base_layout(self) -> None:
        """Restore canonical geometry after layout-affecting transient state."""

        if (
            self._layout.frame.output.projection_document
            is self._editor_state.projection.document
        ):
            self.use_committed_projection()
            return
        log_prompt_editor_probe(
            "surface.restore_base_projection_layout.begin",
            surface=self._surface_state(),
        )
        self._layout.set_projection(
            self._editor_state.projection.document,
            prompt_document_view=self._editor_state.projection_semantic.document,
        )
        self.use_committed_projection()
        self._synchronize_layout(False)
        self._viewport.update()
        log_prompt_editor_probe(
            "surface.restore_base_projection_layout.end",
            surface=self._surface_state(),
        )

    def requires_layout(self) -> bool:
        """Return whether current temporary projection state changes geometry."""

        transient_state = self.transient_state()
        return (
            transient_state.autocomplete_preview is not None
            or self._session.exact_weight_edit is not None
            or self._session.expanded_source_range is not None
            or self._session.transient_neutral_emphasis is not None
        )

    def transient_state(self) -> PromptProjectionTransientState:
        """Return projection-owned transient state valid for active painting."""

        preview = self._session.autocomplete_preview
        if (
            preview is None
            or not preview.suffix_text
            or not self._selection().is_empty
            or preview.source_position != self._cursor_position()
            or self._reorder_active()
        ):
            return PromptProjectionTransientState()
        return PromptProjectionTransientState(
            autocomplete_preview=PromptProjectionInlinePreview(
                source_position=preview.source_position,
                suffix_text=preview.suffix_text,
            )
        )

    def _refresh_paint_state_for(
        self,
        active_span_range: tuple[int, int] | None,
    ) -> None:
        """Publish reusable paint state for one explicit active span."""

        if not qt_object_is_alive(self._surface):
            return
        self.restore_base_layout()
        log_prompt_editor_probe(
            "surface.refresh_projection_paint_state.begin",
            surface=self._surface_state(),
        )
        result = self._applicator.apply_reusable_projection_paint_state(
            self._editor_state.projection_semantic.document,
            self._editor_state.projection_semantic.render_plan,
            display_mode=self._display_mode(),
            session=self._session,
            active_span_range=active_span_range,
            decoration_accent_ranges=self._decoration_accent_ranges(),
            scene_error_keys=self._scene_error_keys(),
            frame=self._layout.frame,
        )
        if result is None:
            log_prompt_editor_probe(
                "surface.refresh_projection_paint_state.noop",
                surface=self._surface_state(),
            )
            return
        self.publish_committed_projection(
            active_span_range=result.active_span_range,
        )
        self._frame_state.publish_prepared_paint(
            self._layout.frame.output,
            self._layout.frame.paint_state,
        )
        self._publish_render_frame()
        self._viewport.update()
        log_prompt_editor_probe(
            "surface.refresh_projection_paint_state.end",
            surface=self._surface_state(),
        )

    def _current_active_span_range(self) -> tuple[int, int] | None:
        """Return the span eligible for paint in the current display mode."""

        if self._display_mode() is PromptProjectionDisplayMode.RAW:
            return None
        return self._active_span_range()


__all__ = ["PromptActiveProjectionOwner"]
