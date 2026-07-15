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

"""Provide reusable geometry helpers for prompt editor presentation surfaces."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, cast

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize
from PySide6.QtGui import QTextBlock, QTextDocument, QTextLine
from PySide6.QtWidgets import QScrollBar, QWidget

_DEFAULT_PANEL_GAP = 6
_DEFAULT_PANEL_MARGIN = 4
_DEFAULT_BADGE_GAP = 6.0
_DEFAULT_BADGE_MARGIN = 6.0


class _ViewportTextSurface(Protocol):
    """Describe the editor APIs required for prompt overlay geometry helpers."""

    def document(self) -> QTextDocument:
        """Return the live QTextDocument used by the editor."""

    def viewport(self) -> QWidget:
        """Return the editor viewport used for local overlay coordinates."""

    def verticalScrollBar(self) -> QScrollBar:
        """Return the editor scrollbar used for viewport-to-document mapping."""


def autocomplete_panel_host(editor: QWidget) -> QWidget:
    """Return the non-clipping host used for the autocomplete panel."""

    window = editor.window()
    if isinstance(window, QWidget) and window is not editor:
        return window
    parent = editor.parentWidget()
    if parent is not None:
        return parent
    return editor


def map_rect_to_host(
    source_widget: QWidget,
    rect: QRect,
    host: QWidget,
) -> QRect:
    """Map one widget-local rectangle into host coordinates."""

    top_left = host.mapFromGlobal(source_widget.mapToGlobal(rect.topLeft()))
    return QRect(top_left, rect.size())


def map_rectf_to_host(
    source_widget: QWidget,
    rect: QRectF,
    host: QWidget,
) -> QRectF:
    """Map one widget-local floating rectangle into host coordinates."""

    top_left = host.mapFromGlobal(source_widget.mapToGlobal(rect.topLeft().toPoint()))
    return QRectF(QPointF(top_left), rect.size())


def map_cursor_rect_to_host(
    viewport: QWidget,
    cursor_rect: QRect,
    host: QWidget,
) -> QRect:
    """Map one viewport-local caret rect into the supplied host widget."""

    return map_rect_to_host(viewport, cursor_rect, host)


def map_viewport_rect_to_overlay_parent(
    viewport: QWidget,
    overlay_parent: QWidget,
) -> QRect:
    """Map the full viewport bounds into the overlay parent's coordinates."""

    return map_rect_to_host(viewport, viewport.rect(), overlay_parent)


def reorder_overlay_content_rect(editor: _ViewportTextSurface) -> QRect:
    """Return the viewport-local text content rect used by reorder chips."""

    document_margin = max(0, int(round(editor.document().documentMargin())))
    return (
        editor.viewport()
        .rect()
        .adjusted(
            document_margin,
            document_margin,
            -document_margin,
            0,
        )
    )


def flow_layout_rects(
    item_sizes: Sequence[QSize],
    *,
    content_rect: QRect,
    horizontal_spacing: int,
    vertical_spacing: int | None = None,
) -> tuple[QRect, ...]:
    """Lay out wrapped preview-chip rects inside one viewport-local content rect."""

    if not item_sizes:
        return ()

    spacing_y = horizontal_spacing if vertical_spacing is None else vertical_spacing
    line_left = content_rect.left()
    line_top = content_rect.top()
    line_height = 0
    right_edge = content_rect.left() + max(1, content_rect.width())
    max_item_width = max(1, content_rect.width())
    rects: list[QRect] = []

    for size in item_sizes:
        width = min(max_item_width, max(1, size.width()))
        height = max(1, size.height())
        needs_wrap = line_height > 0 and (line_left + width) > right_edge
        if needs_wrap:
            line_left = content_rect.left()
            line_top += line_height + spacing_y
            line_height = 0

        rects.append(QRect(line_left, line_top, width, height))
        line_left += width + horizontal_spacing
        line_height = max(line_height, height)

    return tuple(rects)


def flow_layout_insertion_index(
    item_rects: Sequence[QRect],
    *,
    point: QPoint,
) -> int:
    """Return the wrapped flow insertion index implied by one viewport-local point."""

    if not item_rects:
        return 0

    rows: list[list[tuple[int, QRect]]] = []
    for index, rect in enumerate(item_rects):
        if not rows or rows[-1][0][1].top() != rect.top():
            rows.append([])
        rows[-1].append((index, rect))

    target_row = min(
        rows,
        key=lambda row: abs(row[0][1].center().y() - point.y()),
    )
    for item_index, rect in target_row:
        if point.x() <= rect.center().x():
            return item_index
    return target_row[-1][0] + 1


def compute_autocomplete_panel_rect(
    host: QWidget,
    anchor_rect: QRect,
    panel_size: QSize,
    *,
    gap: int = _DEFAULT_PANEL_GAP,
    margin: int = _DEFAULT_PANEL_MARGIN,
) -> QRect:
    """Place the autocomplete panel near the caret without clipping outside the host."""

    panel_width = min(panel_size.width(), max(1, host.width() - (margin * 2)))
    left = max(
        margin,
        min(
            anchor_rect.left(),
            max(margin, host.width() - panel_width - margin),
        ),
    )
    top, panel_height = _autocomplete_panel_vertical_geometry(
        host_height=host.height(),
        anchor_rect=anchor_rect,
        preferred_height=panel_size.height(),
        gap=gap,
        margin=margin,
    )
    return QRect(left, top, panel_width, panel_height)


def _autocomplete_panel_vertical_geometry(
    *,
    host_height: int,
    anchor_rect: QRect,
    preferred_height: int,
    gap: int,
    margin: int,
) -> tuple[int, int]:
    """Return a side-capped panel top and height that reserve the active text line."""

    usable_bottom = max(margin + 1, host_height - margin)
    anchor_top = anchor_rect.top()
    anchor_bottom = anchor_rect.top() + max(1, anchor_rect.height())
    below_top = anchor_bottom + gap
    above_bottom = anchor_top - gap
    available_below = max(0, usable_bottom - below_top)
    available_above = max(0, above_bottom - margin)
    target_height = max(1, preferred_height)

    if _autocomplete_panel_should_place_below(
        available_below=available_below,
        available_above=available_above,
        target_height=target_height,
    ):
        if available_below > 0:
            return below_top, min(target_height, available_below)
    elif available_above > 0:
        height = min(target_height, available_above)
        return above_bottom - height, height

    height = min(target_height, max(1, usable_bottom - margin))
    top = max(margin, min(below_top, usable_bottom - height))
    return top, height


def _autocomplete_panel_should_place_below(
    *,
    available_below: int,
    available_above: int,
    target_height: int,
) -> bool:
    """Return whether below placement has the best usable space for the panel."""

    if available_below >= target_height:
        return True
    if available_above >= target_height:
        return False
    return available_below >= available_above


def source_range_to_viewport_fragments(
    editor: _ViewportTextSurface,
    *,
    start: int,
    end: int,
) -> tuple[QRectF, ...]:
    """Return wrapped viewport-local fragments for one half-open source range."""

    if hasattr(editor, "source_range_fragments"):
        return cast(
            tuple[QRectF, ...],
            getattr(editor, "source_range_fragments")(start=start, end=end),
        )
    return document_source_range_fragments(
        editor.document(),
        start=start,
        end=end,
        viewport_rect=QRectF(editor.viewport().rect()),
        scroll_offset=float(editor.verticalScrollBar().value()),
    )


def source_range_to_host_fragments(
    editor: _ViewportTextSurface,
    *,
    start: int,
    end: int,
    host: QWidget,
) -> tuple[QRectF, ...]:
    """Return wrapped host-local fragments for one half-open source range."""

    viewport = editor.viewport()
    return tuple(
        map_rectf_to_host(viewport, fragment, host)
        for fragment in source_range_to_viewport_fragments(
            editor,
            start=start,
            end=end,
        )
    )


def document_source_range_fragments(
    document: QTextDocument,
    *,
    start: int,
    end: int,
    viewport_rect: QRectF,
    scroll_offset: float = 0.0,
) -> tuple[QRectF, ...]:
    """Return laid-out fragments for one source range in the supplied document."""

    _ = document.documentLayout().documentSize()
    if end <= start:
        return ()

    block = document.findBlock(start)
    if not block.isValid():
        return ()

    fragments: list[QRectF] = []
    while block.isValid():
        block_start = block.position()
        if block_start >= end:
            break

        block_end = block_start + len(block.text())
        local_start = max(start, block_start) - block_start
        local_end = min(end, block_end) - block_start
        if local_end > local_start:
            fragments.extend(
                _block_source_range_fragments(
                    document=document,
                    block=block,
                    range_start=local_start,
                    range_end=local_end,
                    scroll_offset=scroll_offset,
                    viewport_rect=viewport_rect,
                )
            )

        if block_end >= end:
            break
        block = block.next()

    return tuple(fragments)


def document_cursor_line_rect(
    document: QTextDocument,
    *,
    position: int,
    viewport_rect: QRectF,
    scroll_offset: float = 0.0,
) -> QRectF | None:
    """Return the viewport-local line rect containing one document cursor position."""

    _ = document.documentLayout().documentSize()
    block = document.findBlock(position)
    if not block.isValid():
        return None

    layout = block.layout()
    if layout is None or layout.lineCount() == 0:
        return None

    block_rect = document.documentLayout().blockBoundingRect(block)
    block_top = block_rect.top() - scroll_offset
    block_local_position = max(0, position - block.position())

    for line_index in range(layout.lineCount()):
        line = layout.lineAt(line_index)
        line_start = line.textStart()
        line_end = line_start + line.textLength()
        if not line_start <= block_local_position <= line_end:
            continue

        line_rect = QRectF(
            viewport_rect.left(),
            block_top + line.y(),
            viewport_rect.width(),
            line.height(),
        )
        visible_rect = line_rect.intersected(viewport_rect)
        if visible_rect.isEmpty():
            return None
        return visible_rect

    return None


def emphasis_badge_anchor_rect(
    fragments: tuple[QRectF, ...],
) -> QRectF | None:
    """Return the preferred badge anchor rect for one rendered emphasis span."""

    if not fragments:
        return None
    return QRectF(fragments[-1])


def emphasis_weight_anchor_rect(
    fragments: tuple[QRectF, ...],
) -> QRectF | None:
    """Return the host-local anchor rect used for rendered emphasis weight controls."""

    if not fragments:
        return None
    fragment_rect = QRectF(fragments[-1])
    visual_top = fragment_rect.top() + fragment_rect.height() * 0.03
    visual_height = max(1.0, fragment_rect.height() * 0.48)
    return QRectF(
        fragment_rect.left(),
        visual_top,
        fragment_rect.width(),
        visual_height,
    )


def stacked_triangle_control_rects(
    *,
    anchor_rect: QRectF,
    host_rect: QRectF,
    control_width: float,
    control_height: float,
    vertical_gap: float,
    margin: float = _DEFAULT_BADGE_MARGIN,
) -> tuple[QRectF, QRectF]:
    """Return clamped host-local up/down control rects around one weight anchor."""

    clamped_width = max(1.0, min(control_width, host_rect.width() - margin * 2.0))
    clamped_height = max(1.0, control_height)
    center_x = anchor_rect.center().x() - clamped_width / 2.0
    left = max(
        host_rect.left() + margin,
        min(center_x, host_rect.right() - clamped_width - margin),
    )

    top_rect = QRectF(
        left,
        anchor_rect.top() - clamped_height - vertical_gap,
        clamped_width,
        clamped_height,
    )
    bottom_rect = QRectF(
        left,
        anchor_rect.bottom() + vertical_gap,
        clamped_width,
        clamped_height,
    )

    if top_rect.top() < host_rect.top() + margin:
        top_rect.moveTop(host_rect.top() + margin)
    if bottom_rect.bottom() > host_rect.bottom() - margin:
        bottom_rect.moveBottom(host_rect.bottom() - margin)

    return top_rect, bottom_rect


def _block_source_range_fragments(
    *,
    document: QTextDocument,
    block: QTextBlock,
    range_start: int,
    range_end: int,
    scroll_offset: float,
    viewport_rect: QRectF,
) -> list[QRectF]:
    """Return viewport-local fragments for one range contained within one block."""

    layout = block.layout()
    if layout is None or layout.lineCount() == 0:
        return []

    block_rect = document.documentLayout().blockBoundingRect(block)
    block_top = block_rect.top() - scroll_offset
    block_left = block_rect.left() + document.documentMargin()
    fragments: list[QRectF] = []

    for line_index in range(layout.lineCount()):
        line = layout.lineAt(line_index)
        line_start = line.textStart()
        line_end = line_start + line.textLength()
        fragment_start = max(range_start, line_start)
        fragment_end = min(range_end, line_end)
        if fragment_end <= fragment_start:
            continue

        start_x = _cursor_x(line, fragment_start)
        end_x = _cursor_x(line, fragment_end)
        fragment_rect = QRectF(
            block_left + start_x,
            block_top + line.y(),
            max(1.0, end_x - start_x),
            line.height(),
        )
        visible_rect = fragment_rect.intersected(viewport_rect)
        if visible_rect.width() > 0.0 and visible_rect.height() > 0.0:
            fragments.append(visible_rect)

    return fragments


def _cursor_x(line: QTextLine, position: int) -> float:
    """Return the x coordinate for one block-local cursor position."""

    cursor_x = line.cursorToX(position)
    if isinstance(cursor_x, tuple):
        return float(cast(float, cursor_x[0]))
    return float(cast(float, cursor_x))
