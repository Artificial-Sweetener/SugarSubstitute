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

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QRegion

from ..geometry.visible_lines import visible_projection_lines
from ..layout.models import (
    PromptProjectionInlineObjectFragment,
    PromptProjectionTextFragment,
)
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionSelection,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)
from .paint_input import PromptProjectionPaintInput
from .content_selection_layer import PromptProjectionSelectionLayer


class PromptProjectionPainter:
    """Render one prepared projection layout without discovering editor state."""

    def draw(
        self,
        painter: QPainter,
        *,
        paint_input: PromptProjectionPaintInput,
        selection_layer: PromptProjectionSelectionLayer,
        scroll_offset: float,
        clip_rect: QRectF,
        excluded_region: QRegion | None = None,
    ) -> None:
        """Paint the visible projection using snapshot-backed geometry only."""

        layout_snapshot = paint_input.layout_snapshot
        painter.save()
        try:
            painter.translate(0.0, -scroll_offset)
            document_clip = clip_rect.translated(0.0, scroll_offset)
            painter.setClipRect(document_clip)
            if excluded_region is not None:
                painter.setClipRegion(
                    excluded_region.translated(0, int(round(scroll_offset))),
                    Qt.ClipOperation.IntersectClip,
                )
            self.paint_selection(
                painter,
                selection_layer=selection_layer,
            )
            for line in visible_projection_lines(
                layout_snapshot.lines,
                document_top=document_clip.top(),
                document_bottom=document_clip.bottom(),
            ):
                for fragment in line.fragments:
                    if isinstance(fragment, PromptProjectionTextFragment):
                        self._paint_text_fragment(
                            painter,
                            fragment,
                            paint_input=paint_input,
                            selection_layer=selection_layer,
                        )
                        continue
                    self.paint_inline_object_fragment(
                        painter,
                        fragment,
                        paint_input=paint_input,
                        selection_layer=selection_layer,
                    )
        finally:
            painter.restore()

    def paint_selection(
        self,
        painter: QPainter,
        *,
        selection_layer: PromptProjectionSelectionLayer,
    ) -> None:
        """Paint prepared source-backed selection backgrounds."""

        if selection_layer.is_empty:
            return

        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor.fromRgba(selection_layer.background_rgba))
        for rect in selection_layer.backgrounds:
            painter.drawRect(QRectF(rect.left, rect.top, rect.width, rect.height))
        painter.restore()

    def paint_inline_object_fragment(
        self,
        painter: QPainter,
        fragment: PromptProjectionInlineObjectFragment,
        *,
        paint_input: PromptProjectionPaintInput,
        selection_layer: PromptProjectionSelectionLayer,
    ) -> None:
        """Paint one realized inline object through its registered renderer."""

        binding = paint_input.inline_binding(fragment)
        if binding is None:
            return
        binding.renderer.paint_inline_object(
            painter,
            fragment.rect,
            binding.run,
            binding.token,
            base_font=paint_input.base_font,
            palette=paint_input.palette,
            selected=selection_layer.inline_fragment_is_selected(fragment),
        )

    def font_for_fragment(
        self,
        fragment: PromptProjectionTextFragment,
        *,
        paint_input: PromptProjectionPaintInput,
    ) -> QFont:
        """Return the font variant used to paint one text fragment."""

        style = paint_input.text_style(fragment.run_id)
        if style is None:
            return QFont(paint_input.base_text_styles.fallback_font)
        return QFont(style.font)

    def text_color_for_fragment(
        self,
        fragment: PromptProjectionTextFragment,
        *,
        paint_input: PromptProjectionPaintInput,
    ) -> QColor:
        """Return the foreground color used to paint one text fragment."""

        style = paint_input.text_style(fragment.run_id)
        if style is None:
            return QColor(paint_input.base_text_styles.fallback_color)
        return QColor(style.color)

    def inline_object_fragment_is_selected(
        self,
        projection_document: PromptProjectionDocument,
        fragment: PromptProjectionInlineObjectFragment,
        selection: PromptProjectionSelection | None,
    ) -> bool:
        """Return whether one inline object uses selected foreground colors."""

        return _inline_object_fragment_is_selected(
            projection_document.token_by_id(fragment.token_id),
            fragment,
            selection,
        )

    def _paint_text_fragment(
        self,
        painter: QPainter,
        fragment: PromptProjectionTextFragment,
        *,
        paint_input: PromptProjectionPaintInput,
        selection_layer: PromptProjectionSelectionLayer,
    ) -> None:
        """Paint one text fragment with active-span and selection-aware colors."""

        paint_style = paint_input.text_style(fragment.run_id)
        if paint_style is None:
            return
        selection_bounds = selection_layer.text_span(fragment)

        painter.setFont(paint_style.font)
        if selection_bounds is None:
            painter.setPen(paint_style.color)
            painter.drawText(
                QPointF(fragment.rect.left(), fragment.baseline), fragment.text
            )
            return

        selected_color = paint_input.base_text_styles.selected_color
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


def _inline_object_fragment_is_selected(
    token: PromptProjectionToken | None,
    fragment: PromptProjectionInlineObjectFragment,
    selection: PromptProjectionSelection | None,
) -> bool:
    """Return whether one inline object fragment is selected."""

    if selection is None or selection.is_empty:
        return False
    if (
        token is not None
        and selection.start <= token.source_start
        and token.source_end <= selection.end
    ):
        return True
    if len(fragment.source_positions) < 2:
        return False
    source_start = fragment.source_positions[0]
    source_end = fragment.source_positions[-1]
    return selection.start < source_end and source_start < selection.end
