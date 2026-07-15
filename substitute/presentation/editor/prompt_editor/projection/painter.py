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

"""Paint prepared prompt projection layout snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPalette, QRegion

from .model import PromptProjectionRun, PromptProjectionSelection
from .snapshot import (
    PromptProjectionInlineObjectFragment,
    PromptProjectionLineSnapshot,
    PromptProjectionTextFragment,
)
from .text_style import projection_text_run_font

if TYPE_CHECKING:
    from .layout_engine import PromptProjectionLayout


class PromptProjectionPainter:
    """Render one prepared projection layout without discovering editor state."""

    def __init__(self, layout: PromptProjectionLayout) -> None:
        """Store the prepared layout consumed by paint operations."""

        self._layout = layout

    def draw(
        self,
        painter: QPainter,
        *,
        selection: PromptProjectionSelection | None,
        scroll_offset: float,
        clip_rect: QRectF,
        excluded_region: QRegion | None = None,
    ) -> None:
        """Paint the visible projection using snapshot-backed geometry only."""

        painter.save()
        try:
            text_paint_styles: dict[str, _TextFragmentPaintStyle] = {}
            painter.translate(0.0, -scroll_offset)
            document_clip = clip_rect.translated(0.0, scroll_offset)
            painter.setClipRect(document_clip)
            if excluded_region is not None:
                painter.setClipRegion(
                    excluded_region.translated(0, int(round(scroll_offset))),
                    Qt.ClipOperation.IntersectClip,
                )
            self.paint_selection(selection, painter)
            for line in _visible_lines(
                self._layout._snapshot.lines,
                document_clip=document_clip,
            ):
                for fragment in line.fragments:
                    if isinstance(fragment, PromptProjectionTextFragment):
                        self._paint_text_fragment(
                            painter,
                            fragment,
                            selection=selection,
                            paint_styles=text_paint_styles,
                        )
                        continue
                    self.paint_inline_object_fragment(
                        painter,
                        fragment,
                        selection=selection,
                    )
        finally:
            painter.restore()

    def paint_selection(
        self,
        selection: PromptProjectionSelection | None,
        painter: QPainter,
    ) -> None:
        """Paint source-backed selection backgrounds through layout geometry."""

        if selection is None or selection.is_empty:
            return

        highlight_color = self._layout._palette.color(QPalette.ColorRole.Highlight)
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(highlight_color)
        for rect in self._layout.selection_rects(selection):
            painter.drawRect(rect)
        painter.restore()

    def paint_inline_object_fragment(
        self,
        painter: QPainter,
        fragment: PromptProjectionInlineObjectFragment,
        *,
        selection: PromptProjectionSelection | None = None,
    ) -> None:
        """Paint one realized inline object through its registered renderer."""

        run = self._layout.effective_run_for_paint(fragment.run_id)
        token = self._layout.effective_token_for_paint(fragment.token_id)
        if run is None or token is None:
            return
        renderer = self._layout.inline_object_renderers.renderer_for(
            fragment.renderer_key
        )
        if renderer is None:
            return
        renderer.paint_inline_object(
            painter,
            fragment.rect,
            run,
            token,
            base_font=self._layout._base_font,
            palette=self._layout._palette,
            selected=self._layout._inline_object_fragment_is_selected(
                fragment, selection
            ),
        )

    def font_for_fragment(self, fragment: PromptProjectionTextFragment) -> QFont:
        """Return the font variant used to paint one text fragment."""

        run = self._layout.effective_run_for_paint(fragment.run_id)
        if run is None:
            return QFont(self._layout._base_font)
        return projection_text_run_font(run, self._layout._base_font)

    def text_color_for_fragment(
        self,
        fragment: PromptProjectionTextFragment,
    ) -> QColor:
        """Return the foreground color used to paint one text fragment."""

        run = self._layout.effective_run_for_paint(fragment.run_id)
        if run is None:
            return QColor(self._layout._palette.color(QPalette.ColorRole.Text))
        return self._text_color_for_run(run)

    def _paint_text_fragment(
        self,
        painter: QPainter,
        fragment: PromptProjectionTextFragment,
        *,
        selection: PromptProjectionSelection | None,
        paint_styles: dict[str, _TextFragmentPaintStyle],
    ) -> None:
        """Paint one text fragment with active-span and selection-aware colors."""

        paint_style = self._text_fragment_paint_style(fragment, paint_styles)
        if paint_style is None:
            return
        selection_bounds = self._layout._text_fragment_selection_bounds(
            fragment, selection
        )

        painter.setFont(paint_style.font)
        if selection_bounds is None:
            painter.setPen(paint_style.color)
            painter.drawText(
                QPointF(fragment.rect.left(), fragment.baseline), fragment.text
            )
            return

        selected_color = QColor(
            self._layout._palette.color(QPalette.ColorRole.HighlightedText)
        )
        selected_start, selected_end = selection_bounds
        for chunk_start, chunk_end, color in (
            (0, selected_start, paint_style.color),
            (selected_start, selected_end, selected_color),
            (selected_end, len(fragment.text), paint_style.color),
        ):
            if chunk_end <= chunk_start:
                continue
            painter.setPen(color)
            painter.drawText(
                QPointF(
                    fragment.rect.left() + fragment.boundary_offsets[chunk_start],
                    fragment.baseline,
                ),
                fragment.text[chunk_start:chunk_end],
            )

    def _text_fragment_paint_style(
        self,
        fragment: PromptProjectionTextFragment,
        paint_styles: dict[str, _TextFragmentPaintStyle],
    ) -> _TextFragmentPaintStyle | None:
        """Return cached paint state for one text fragment's projection run."""

        if fragment.run_id is None:
            return None
        paint_style = paint_styles.get(fragment.run_id)
        if paint_style is not None:
            return paint_style
        run = self._layout.effective_run_for_paint(fragment.run_id)
        if run is None:
            return None
        paint_style = _TextFragmentPaintStyle(
            font=projection_text_run_font(run, self._layout._base_font),
            color=self._text_color_for_run(run),
        )
        paint_styles[fragment.run_id] = paint_style
        return paint_style

    def _text_color_for_run(self, run: PromptProjectionRun) -> QColor:
        """Return the foreground color used to paint one projection run."""

        if run.ghosted:
            return QColor(
                self._layout._palette.color(QPalette.ColorRole.PlaceholderText)
            )
        if run.text_style_variant == "scene_error":
            if self._layout._semantic_palette is not None:
                error = self._layout._semantic_palette.error_foreground
                return QColor(error.red, error.green, error.blue)
            return QColor(self._layout._palette.color(QPalette.ColorRole.Text))
        return QColor(self._layout._palette.color(QPalette.ColorRole.Text))


@dataclass(frozen=True, slots=True)
class _TextFragmentPaintStyle:
    """Cache painter state shared by text fragments in one projection run."""

    font: QFont
    color: QColor


def _visible_lines(
    lines: tuple[PromptProjectionLineSnapshot, ...],
    *,
    document_clip: QRectF,
) -> tuple[PromptProjectionLineSnapshot, ...]:
    """Return lines whose vertical span intersects the current paint clip."""

    clip_top = document_clip.top()
    clip_bottom = document_clip.bottom()
    return tuple(
        line
        for line in lines
        if line.top <= clip_bottom and line.top + line.height >= clip_top
    )
