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

"""Build shared chip geometry for reorder bubbles and drag proxies."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRect, QRectF, QSize

PROMPT_CHIP_BUBBLE_PADDING_X = 4.0
PROMPT_CHIP_BUBBLE_PADDING_Y = 2.0
PROMPT_CHIP_BUBBLE_RADIUS = 9.0
PROMPT_CHIP_HOTSPOT_PADDING_X = 5
PROMPT_CHIP_HOTSPOT_PADDING_Y = 3
PROMPT_CHIP_PROXY_OUTSET = 1.0
PROMPT_CHIP_SAME_LINE_MERGE_GAP = 12.0


@dataclass(frozen=True, slots=True)
class PromptChipVisual:
    """Describe one chip bubble and hotspot geometry snapshot."""

    bubble_rects: tuple[QRectF, ...]
    fragment_union_rect: QRectF
    hotspot_rect: QRect
    slot_before: QPointF
    slot_after: QPointF
    marker_height: float
    preferred_size: QSize | None = None
    text_translation: QPointF | None = None


class PromptChipVisualBuilder:
    """Build editor and proxy chip visuals from rendered text fragments."""

    def build_editor_visual(
        self,
        *,
        fragments: tuple[QRectF, ...],
        content_rect: QRect,
    ) -> PromptChipVisual:
        """Build one editor-local chip visual clamped to the live content rect."""

        bubble_rects = self._coalesce_same_line_bubble_rects(
            tuple(
                self._editor_bubble_rect(fragment, content_rect=content_rect)
                for fragment in fragments
            )
        )
        fragment_union_rect = self._union_rect(fragments)
        first_rect = bubble_rects[0]
        last_rect = bubble_rects[-1]
        return PromptChipVisual(
            bubble_rects=bubble_rects,
            fragment_union_rect=fragment_union_rect,
            hotspot_rect=self._hotspot_rect(bubble_rects),
            slot_before=QPointF(first_rect.left(), first_rect.center().y()),
            slot_after=QPointF(last_rect.right(), last_rect.center().y()),
            marker_height=max(rect.height() for rect in bubble_rects),
        )

    def build_proxy_visual(
        self,
        *,
        fragments: tuple[QRectF, ...],
    ) -> PromptChipVisual:
        """Build one normalized drag-proxy chip visual from local text fragments."""

        proxy_bubble_rects = self._coalesce_same_line_bubble_rects(
            tuple(self._proxy_bubble_rect(fragment) for fragment in fragments)
        )
        painted_bounds = self._union_rect(proxy_bubble_rects).adjusted(
            -PROMPT_CHIP_PROXY_OUTSET,
            -PROMPT_CHIP_PROXY_OUTSET,
            PROMPT_CHIP_PROXY_OUTSET,
            PROMPT_CHIP_PROXY_OUTSET,
        )
        normalized_fragments = tuple(
            fragment.translated(-painted_bounds.left(), -painted_bounds.top())
            for fragment in fragments
        )
        normalized_bubble_rects = tuple(
            bubble_rect.translated(-painted_bounds.left(), -painted_bounds.top())
            for bubble_rect in proxy_bubble_rects
        )
        fragment_union_rect = self._union_rect(normalized_fragments)
        first_rect = normalized_bubble_rects[0]
        last_rect = normalized_bubble_rects[-1]
        return PromptChipVisual(
            bubble_rects=normalized_bubble_rects,
            fragment_union_rect=fragment_union_rect,
            hotspot_rect=self._hotspot_rect(normalized_bubble_rects),
            slot_before=QPointF(first_rect.left(), first_rect.center().y()),
            slot_after=QPointF(last_rect.right(), last_rect.center().y()),
            marker_height=max(rect.height() for rect in normalized_bubble_rects),
            preferred_size=painted_bounds.toAlignedRect().size(),
            text_translation=QPointF(-painted_bounds.left(), -painted_bounds.top()),
        )

    @staticmethod
    def _editor_bubble_rect(fragment: QRectF, *, content_rect: QRect) -> QRectF:
        """Inflate one editor fragment into the painted chip bubble rect."""

        content_bounds = QRectF(content_rect)
        left = max(
            content_bounds.left(), fragment.left() - PROMPT_CHIP_BUBBLE_PADDING_X
        )
        top = max(content_bounds.top(), fragment.top() - PROMPT_CHIP_BUBBLE_PADDING_Y)
        right = min(
            content_bounds.right(),
            fragment.right() + PROMPT_CHIP_BUBBLE_PADDING_X,
        )
        bottom = min(
            content_bounds.bottom(),
            fragment.bottom() + PROMPT_CHIP_BUBBLE_PADDING_Y,
        )
        return QRectF(QPointF(left, top), QPointF(right, bottom))

    @staticmethod
    def _proxy_bubble_rect(fragment: QRectF) -> QRectF:
        """Inflate one proxy fragment into the painted chip bubble rect."""

        return fragment.adjusted(
            -PROMPT_CHIP_BUBBLE_PADDING_X,
            -PROMPT_CHIP_BUBBLE_PADDING_Y,
            PROMPT_CHIP_BUBBLE_PADDING_X,
            PROMPT_CHIP_BUBBLE_PADDING_Y,
        )

    @staticmethod
    def _coalesce_same_line_bubble_rects(
        bubble_rects: tuple[QRectF, ...],
    ) -> tuple[QRectF, ...]:
        """Merge same-line projection pieces that belong to one logical chip."""

        if len(bubble_rects) <= 1:
            return bubble_rects

        ordered_rects = sorted(
            (QRectF(rect) for rect in bubble_rects),
            key=lambda rect: (rect.center().y(), rect.left()),
        )
        rows: list[list[QRectF]] = []
        for rect in ordered_rects:
            for row in rows:
                if PromptChipVisualBuilder._same_visual_line(row[0], rect):
                    row.append(rect)
                    break
            else:
                rows.append([rect])

        coalesced: list[QRectF] = []
        for row in sorted(rows, key=lambda row: min(rect.top() for rect in row)):
            row.sort(key=lambda rect: rect.left())
            current = QRectF(row[0])
            for rect in row[1:]:
                if rect.left() <= current.right() + PROMPT_CHIP_SAME_LINE_MERGE_GAP:
                    current = current.united(rect)
                    continue
                coalesced.append(current)
                current = QRectF(rect)
            coalesced.append(current)
        return tuple(coalesced)

    @staticmethod
    def _same_visual_line(left: QRectF, right: QRectF) -> bool:
        """Return whether two bubble rects share the same projected text row."""

        center_delta = abs(left.center().y() - right.center().y())
        height_floor = max(1.0, min(left.height(), right.height()))
        return center_delta <= height_floor * 0.5

    @staticmethod
    def _union_rect(rects: tuple[QRectF, ...]) -> QRectF:
        """Return the union rect covering the supplied rects."""

        union_rect = QRectF(rects[0])
        for rect in rects[1:]:
            union_rect = union_rect.united(rect)
        return union_rect

    @staticmethod
    def _hotspot_rect(bubble_rects: tuple[QRectF, ...]) -> QRect:
        """Return the padded hotspot rect that should capture pointer interaction."""

        union_rect = PromptChipVisualBuilder._union_rect(bubble_rects)
        return union_rect.adjusted(
            -PROMPT_CHIP_HOTSPOT_PADDING_X,
            -PROMPT_CHIP_HOTSPOT_PADDING_Y,
            PROMPT_CHIP_HOTSPOT_PADDING_X,
            PROMPT_CHIP_HOTSPOT_PADDING_Y,
        ).toAlignedRect()


__all__ = [
    "PROMPT_CHIP_BUBBLE_RADIUS",
    "PromptChipVisual",
    "PromptChipVisualBuilder",
]
