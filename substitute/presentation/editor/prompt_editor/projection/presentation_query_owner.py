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

"""Resolve public projection presentation queries from one current frame."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor

from substitute.application.prompt_editor.document.views import PromptSyntaxSpanView

from ..core.projection.document import PromptProjectionDocument
from ..core.projection.tokens import PromptProjectionToken
from ..geometry.models import PromptProjectionSourceLineRect
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .fill_band_cache import PromptFillBandRect
from .fill_band_owner import PromptProjectionFillBandOwner
from .frame_state import PromptProjectionEditorState
from .freshness_controller import PromptProjectionFreshnessController
from .reorder_preview_projection_owner import PromptReorderPreviewProjectionOwner
from .source_line_chrome import PromptSourceLineChrome


class PromptProjectionPresentationQueryOwner:
    """Own read-only projection, token, line, and viewport geometry queries."""

    def __init__(
        self,
        *,
        editor_state: PromptProjectionEditorState,
        active_document: Callable[[], PromptProjectionDocument],
        layout: PromptLayoutEditToFrameCoordinator,
        freshness: PromptProjectionFreshnessController,
        source_line_chrome: PromptSourceLineChrome,
        fill_bands: PromptProjectionFillBandOwner,
        reorder_preview: PromptReorderPreviewProjectionOwner,
        flush_pending_projection: Callable[[str], None],
        viewport_rect: Callable[[], QRectF],
        scroll_offset: Callable[[], float],
        cursor_position: Callable[[], int],
        hovered_token_id: Callable[[], str | None],
        focused_token_id: Callable[[], str | None],
    ) -> None:
        """Bind every authoritative state sampled by presentation queries."""

        self._editor_state = editor_state
        self._active_document = active_document
        self._layout = layout
        self._freshness = freshness
        self._source_line_chrome = source_line_chrome
        self._fill_bands = fill_bands
        self._reorder_preview = reorder_preview
        self._flush_pending_projection = flush_pending_projection
        self._viewport_rect = viewport_rect
        self._scroll_offset = scroll_offset
        self._cursor_position = cursor_position
        self._hovered_token_id = hovered_token_id
        self._focused_token_id = focused_token_id

    @property
    def projection_document(self) -> PromptProjectionDocument:
        """Return the committed token-aware projection document."""

        return self._editor_state.projection.document

    @property
    def active_projection_document(self) -> PromptProjectionDocument:
        """Return the projection currently represented by prepared geometry."""

        return self._active_document()

    def content_height(self) -> float:
        """Return the current prepared or safely cached content height."""

        preview_frame = self._reorder_preview.preview_frame
        if preview_frame is not None:
            return preview_frame.output.snapshot.content_size.height()
        committed_metrics = self._freshness.committed_metrics
        if self._freshness.can_use_committed_passive_metrics():
            assert committed_metrics is not None
            return committed_metrics.content_height
        self._flush_pending_projection("content_height_initial_or_unavailable")
        return self._layout.frame.output.snapshot.content_size.height()

    def text_line_height(self) -> float:
        """Return the row height owned by the prepared layout."""

        return self._layout.frame.output.configuration.metrics.text_line_height

    def source_range_fragments(
        self,
        *,
        start: int,
        end: int,
    ) -> tuple[QRectF, ...]:
        """Return wrapped viewport fragments covering one source range."""

        self._flush_pending_projection("source_range_fragments")
        return self._layout.frame.geometry.selection.source_range_fragments(
            start,
            end,
            viewport_rect=self._viewport_rect(),
            scroll_offset=self._scroll_offset(),
        )

    def source_line_rects(self) -> tuple[PromptProjectionSourceLineRect, ...]:
        """Return visible source-line rectangles from the current geometry."""

        self._flush_pending_projection("source_line_rects")
        return self._source_line_chrome.source_line_rects(
            geometry=self._layout.frame.geometry,
            viewport_rect=self._viewport_rect(),
            scroll_offset=self._scroll_offset(),
        )

    def visible_fill_band_rects(self) -> tuple[PromptFillBandRect, ...]:
        """Return visible alternating prompt fill bands."""

        return self._fill_bands.visible_rects()

    def fill_band_color(self) -> QColor:
        """Return the alternating prompt fill-band color."""

        return self._fill_bands.color()

    def current_source_line_index(self) -> int:
        """Return the source line containing the current caret."""

        self._flush_pending_projection("current_source_line_index")
        return self._source_line_chrome.current_source_line_index(
            geometry=self._layout.frame.geometry,
            cursor_position=self._cursor_position(),
        )

    def active_syntax_span(self) -> PromptSyntaxSpanView | None:
        """Return the syntax span owned by current token focus or the caret."""

        token = self.focused_or_hovered_token(prefer_hovered=False)
        if token is not None:
            return next(
                (
                    span
                    for span in reversed(
                        self._editor_state.projection_semantic.render_plan.syntax_spans
                    )
                    if span.start == token.source_start and span.end == token.source_end
                ),
                None,
            )
        position = self._cursor_position()
        for span in reversed(
            self._editor_state.projection_semantic.render_plan.syntax_spans
        ):
            if span.start < position < span.end:
                return span
        return None

    def hovered_token(self) -> PromptProjectionToken | None:
        """Return the token currently under the pointer."""

        hovered_token_id = self._hovered_token_id()
        if hovered_token_id is None:
            return None
        return self._layout.frame.paint_input.effective_token(hovered_token_id)

    def focused_token(self) -> PromptProjectionToken | None:
        """Return the token currently owning caret focus."""

        return self.projection_document.token_by_id(self._focused_token_id())

    def focused_or_hovered_token(
        self,
        *,
        prefer_hovered: bool,
    ) -> PromptProjectionToken | None:
        """Resolve token focus using the requested pointer precedence."""

        if prefer_hovered:
            hovered_token = self.hovered_token()
            if hovered_token is not None:
                return hovered_token
        focused_token = self.focused_token()
        if focused_token is not None:
            return focused_token
        if not prefer_hovered:
            return self.hovered_token()
        return None

    def active_span_range(self) -> tuple[int, int] | None:
        """Return the source range that should render as active."""

        token = self.focused_or_hovered_token(prefer_hovered=False)
        if token is not None:
            return (token.source_start, token.source_end)
        active_span = self.active_syntax_span()
        if active_span is None:
            return None
        return (active_span.start, active_span.end)

    def token_at_viewport_position(
        self,
        position: QPointF,
    ) -> PromptProjectionToken | None:
        """Return the token painted under one viewport-local point."""

        return self._layout.frame.geometry.tokens.token_at_viewport_position(
            position,
            scroll_offset=self._scroll_offset(),
        )

    def token_anchor_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the viewport-local anchor used by token controls."""

        return self._layout.frame.geometry.tokens.token_anchor_rect(
            token,
            scroll_offset=self._scroll_offset(),
        )

    def token_weight_text_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the viewport-local emphasis weight slot."""

        return self._layout.frame.geometry.tokens.token_weight_text_rect(
            token,
            scroll_offset=self._scroll_offset(),
        )


__all__ = ["PromptProjectionPresentationQueryOwner"]
