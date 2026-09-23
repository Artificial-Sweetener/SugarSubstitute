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

"""Own display-mode transitions and canonical projection rebuild publication."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRect
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QWidget

from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    prompt_editor_work_event,
)

from ..core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionTransientState,
)
from ..qt_lifecycle import qt_object_is_alive
from .theme import semantic_palette_from_theme
from .applicator import PromptProjectionApplicator, PromptProjectionRebuildResult
from .caret_geometry_owner import PromptProjectionCaretGeometryOwner
from .caret_publication_owner import PromptProjectionCaretPublicationOwner
from .caret_state_owner import PromptProjectionCaretStateOwner
from .display_mode_layout_cache import (
    PromptProjectionDisplayModeLayoutCache,
    PromptProjectionDisplayModeLayoutIdentity,
)
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .frame_state import PromptProjectionEditorState
from .observability import log_projection_timing, projection_observability_started_at
from .render_publication_owner import PromptProjectionRenderPublicationOwner
from .session import PromptProjectionSession


class PromptProjectionRebuildOwner:
    """Own mode-specific layout reuse and complete projection rebuild transactions."""

    def __init__(
        self,
        *,
        surface: QObject,
        viewport: QWidget,
        applicator: PromptProjectionApplicator,
        editor_state: PromptProjectionEditorState,
        session: PromptProjectionSession,
        layout: PromptLayoutEditToFrameCoordinator,
        caret_state: PromptProjectionCaretStateOwner,
        caret_publication: PromptProjectionCaretPublicationOwner,
        caret_geometry: PromptProjectionCaretGeometryOwner,
        render_publication: PromptProjectionRenderPublicationOwner,
        flush_pending_projection: Callable[[str], None],
        cancel_pending_projection: Callable[[], None],
        decoration_accent_ranges: Callable[[], tuple[tuple[int, int], ...]],
        scene_error_keys: Callable[[], frozenset[str]],
        font: Callable[[], QFont],
        palette: Callable[[], QPalette],
        clear_reorder: Callable[[str], None],
        clear_hovered_token: Callable[[], None],
        publish_active_span_range: Callable[[tuple[int, int] | None], None],
        rebuild_active_projection: Callable[[], None],
        prewarm_visible_banners: Callable[[], object],
        invalidate_backing: Callable[[QRect], None],
        ensure_caret_visible: Callable[[], None],
        emit_cursor_position_changed: Callable[[], None],
        active_projection_requires_layout: Callable[[], bool],
        restore_base_projection_layout: Callable[[], None],
    ) -> None:
        """Store the state owners and effects participating in rebuild publication."""

        self._surface = surface
        self._viewport = viewport
        self._applicator = applicator
        self._editor_state = editor_state
        self._session = session
        self._layout = layout
        self._caret_state = caret_state
        self._caret_publication = caret_publication
        self._caret_geometry = caret_geometry
        self._render_publication = render_publication
        self._flush_pending_projection = flush_pending_projection
        self._cancel_pending_projection = cancel_pending_projection
        self._decoration_accent_ranges = decoration_accent_ranges
        self._scene_error_keys = scene_error_keys
        self._font = font
        self._palette = palette
        self._clear_reorder = clear_reorder
        self._clear_hovered_token = clear_hovered_token
        self._publish_active_span_range = publish_active_span_range
        self._rebuild_active_projection = rebuild_active_projection
        self._prewarm_visible_banners = prewarm_visible_banners
        self._invalidate_backing = invalidate_backing
        self._ensure_caret_visible = ensure_caret_visible
        self._emit_cursor_position_changed = emit_cursor_position_changed
        self._active_projection_requires_layout = active_projection_requires_layout
        self._restore_base_projection_layout = restore_base_projection_layout
        self._display_mode = PromptProjectionDisplayMode.PROJECTED
        self._layout_cache = PromptProjectionDisplayModeLayoutCache()

    @property
    def display_mode(self) -> PromptProjectionDisplayMode:
        """Return the currently published projection display mode."""

        return self._display_mode

    def set_display_mode(self, display_mode: PromptProjectionDisplayMode) -> None:
        """Publish another display mode using an exact cached layout when valid."""

        if display_mode is self._display_mode:
            return
        self._flush_pending_projection("set_display_mode")
        layout_identity = (
            PromptProjectionDisplayModeLayoutIdentity.from_projection_state(
                semantic_identity=self._editor_state.projection_semantic.identity,
                session=self._session,
                decoration_accent_ranges=self._decoration_accent_ranges(),
                scene_error_keys=self._scene_error_keys(),
            )
        )
        self._layout_cache.remember(
            self._display_mode,
            self._layout.frame.output,
            self._layout.frame.paint_input,
            identity=layout_identity,
        )
        previous_cursor_state = self._caret_state.cursor_state
        previous_anchor_state = self._caret_state.anchor_state
        self._display_mode = display_mode
        self._clear_reorder("display_mode_changed")
        self._clear_hovered_token()
        restored_projection = self._layout_cache.try_restore(
            display_mode,
            self._layout.frame.output,
            self._layout.frame.paint_input,
            identity=layout_identity,
            expected_source_text=(
                self._editor_state.projection_semantic.document.source_text
            ),
            previous_cursor_state=previous_cursor_state,
            previous_anchor_state=previous_anchor_state,
        )
        if restored_projection is None:
            self._build_and_publish()
        else:
            self._layout.frame.restore(restored_projection.layout_output)
            self._publish_rebuild_result(
                restored_projection.projection_rebuild,
                invalidation_reason="display_mode_layout_restored",
            )
        self._ensure_caret_visible()
        self._emit_cursor_position_changed()
        if not self._active_projection_requires_layout():
            self._restore_base_projection_layout()

    @prompt_editor_work_event(PromptEditorWorkEvent.PROJECTION_REBUILD)
    def rebuild(self) -> None:
        """Rebuild the visible projection and discard mode-layout reuse."""

        self._layout_cache.clear()
        self._build_and_publish()

    def _build_and_publish(self) -> None:
        """Build and publish one canonical projection without cache policy changes."""

        if not qt_object_is_alive(self._surface):
            return
        self._cancel_pending_projection()
        rebuild_started_at = projection_observability_started_at()
        mount_committed_layout = not self._active_projection_requires_layout()
        rebuild_result = self._applicator.rebuild_projection(
            self._editor_state.edit_semantic.document,
            self._editor_state.edit_semantic.render_plan,
            display_mode=self._display_mode,
            session=self._session,
            active_span_range=None,
            decoration_accent_ranges=self._decoration_accent_ranges(),
            scene_error_keys=self._scene_error_keys(),
            transient_state=PromptProjectionTransientState(),
            layout=self._layout,
            font=self._font(),
            palette=self._palette(),
            semantic_palette=semantic_palette_from_theme(),
            previous_cursor_state=self._caret_state.cursor_state,
            previous_anchor_state=self._caret_state.anchor_state,
            mount_committed_layout=mount_committed_layout,
        )
        log_projection_timing(
            "surface.rebuild_projection",
            started_at=rebuild_started_at,
            text_length=len(self._editor_state.edit_semantic.document.source_text),
            display_mode=self._display_mode.value,
            token_count=len(rebuild_result.projection_document.tokens),
            run_count=len(rebuild_result.projection_document.runs),
        )
        self._publish_rebuild_result(
            rebuild_result,
            invalidation_reason="projection_rebuilt",
        )

    def _publish_rebuild_result(
        self,
        rebuild_result: PromptProjectionRebuildResult,
        *,
        invalidation_reason: str,
    ) -> None:
        """Publish one freshly built or exact-restored canonical projection."""

        self._editor_state.publish_projection(rebuild_result.projection_document)
        self._publish_active_span_range(rebuild_result.active_span_range)
        self._render_publication.projection_rebuilt(
            invalidation_reason=invalidation_reason
        )
        self._caret_publication.replace_states(
            cursor_state=rebuild_result.cursor_state,
            anchor_state=rebuild_result.anchor_state,
            clear_caret_rect_override=True,
            reset_preferred_x=False,
        )
        self._rebuild_active_projection()
        self._prewarm_visible_banners()
        self._caret_geometry.clear_transient()
        viewport_rect = self._viewport.rect()
        self._invalidate_backing(viewport_rect)
        self._viewport.update()


__all__ = ["PromptProjectionRebuildOwner"]
