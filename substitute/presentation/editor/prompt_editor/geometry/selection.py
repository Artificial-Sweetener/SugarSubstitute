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

"""Resolve and compare source-backed selection geometry."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QFontMetricsF

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionSelection,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from ..projection.tokens import PromptProjectionInlineObjectRendererRegistry
from ..layout.models import (
    PromptProjectionLayoutSnapshot,
    PromptProjectionLineCaretStopSnapshot,
    PromptProjectionLineSnapshot,
    PromptProjectionTextFragment,
)
from .state import PromptProjectionGeometryInput
from .token_geometry import PromptTokenGeometry
from .visible_lines import (
    PromptProjectionSourceLineIndex,
    source_range_intersects_visual_line,
    visible_projection_lines,
)


@dataclass(frozen=True, slots=True)
class PromptSelectionGeometry:
    """Resolve selections from one immutable layout input."""

    input: PromptProjectionGeometryInput
    _tokens: PromptTokenGeometry
    _source_lines: PromptProjectionSourceLineIndex = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Index immutable visual lines once for bounded source-range queries."""

        object.__setattr__(
            self,
            "_source_lines",
            PromptProjectionSourceLineIndex(self._snapshot.lines),
        )

    @property
    def _projection_document(self) -> PromptProjectionDocument:
        """Return the immutable projected document."""

        return self.input.projection_document

    @property
    def _snapshot(self) -> PromptProjectionLayoutSnapshot:
        """Return the immutable layout snapshot."""

        return self.input.layout_snapshot

    @property
    def _base_font(self) -> QFont:
        """Return the font captured with this layout."""

        return self.input.base_font

    @property
    def _document_margin(self) -> float:
        """Return the captured document inset."""

        return self.input.document_margin

    @property
    def inline_object_renderers(self) -> PromptProjectionInlineObjectRendererRegistry:
        """Return the stable inline renderer registry."""

        return self.input.inline_object_renderers

    def selection_rects(
        self,
        selection: PromptProjectionSelection | None,
    ) -> tuple[QRectF, ...]:
        """Return document rects for one source-backed selection."""

        return self._selection_rects_from_geometry(selection)

    def source_range_fragments(
        self,
        start: int,
        end: int,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Return wrapped viewport fragments for one raw source range."""

        return self._source_range_fragments_from_geometry(
            start,
            end,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )

    def source_range_document_fragments(
        self,
        start: int,
        end: int,
    ) -> tuple[QRectF, ...]:
        """Return document-space fragments through the indexed owning lines."""

        range_start = max(0, start)
        range_end = max(0, end)
        if range_end <= range_start:
            return ()
        selection = PromptProjectionSelection(range_start, range_end)
        content_rects: list[QRectF] = []
        for line in self._source_lines.lines_intersecting(range_start, range_end):
            content_rects.extend(
                self.source_range_fragments_for_line(
                    line,
                    selection=selection,
                    range_start=range_start,
                    range_end=range_end,
                )
            )
        return tuple(content_rects)

    def text_fragment_selection_bounds(
        self,
        fragment: PromptProjectionTextFragment,
        selection: PromptProjectionSelection | None,
    ) -> tuple[int, int] | None:
        """Return selected local indices for one prepared text fragment."""

        return self._text_fragment_selection_bounds(fragment, selection)

    def _selection_rects_from_geometry(
        self,
        selection: PromptProjectionSelection | None,
    ) -> tuple[QRectF, ...]:
        """Return projection-aligned document rects for one source-backed selection."""

        if selection is None or selection.is_empty:
            return ()
        return self._merged_rects(self._selection_rects_for_selection(selection))

    def _source_range_fragments_from_geometry(
        self,
        start: int,
        end: int,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Return wrapped viewport fragments for one raw source range."""

        visible_lines = visible_projection_lines(
            self._snapshot.lines,
            document_top=viewport_rect.top() + scroll_offset,
            document_bottom=viewport_rect.bottom() + scroll_offset,
        )
        return self._visible_source_range_fragments(
            start,
            end,
            visible_lines=visible_lines,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )

    def _visible_source_range_fragments(
        self,
        start: int,
        end: int,
        *,
        visible_lines: tuple[PromptProjectionLineSnapshot, ...],
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Return viewport fragments by scanning visible lines only."""

        range_start = max(0, start)
        range_end = max(0, end)
        if range_end <= range_start:
            return ()

        selection = PromptProjectionSelection(range_start, range_end)
        content_rects: list[QRectF] = []
        for line in visible_lines:
            if not source_range_intersects_visual_line(
                source_start=range_start,
                source_end=range_end,
                visual_start=line.source_start,
                visual_end=line.source_end,
            ):
                continue
            content_rects.extend(
                self.source_range_fragments_for_line(
                    line,
                    selection=selection,
                    range_start=range_start,
                    range_end=range_end,
                )
            )

        visible_rects: list[QRectF] = []
        for rect in content_rects:
            clipped_rect = rect.translated(0.0, -scroll_offset).intersected(
                viewport_rect
            )
            if clipped_rect.isValid() and not clipped_rect.isEmpty():
                visible_rects.append(clipped_rect)
        return tuple(visible_rects)

    def source_range_fragments_for_line(
        self,
        line: PromptProjectionLineSnapshot,
        *,
        selection: PromptProjectionSelection,
        range_start: int,
        range_end: int,
    ) -> tuple[QRectF, ...]:
        """Return merged document-space fragments from one known visual line."""

        line_content_rects: list[QRectF] = []
        for fragment in line.fragments:
            if isinstance(fragment, PromptProjectionTextFragment):
                selection_bounds = self._text_fragment_selection_bounds(
                    fragment,
                    selection,
                )
                if selection_bounds is None:
                    continue
                start_index, end_index = selection_bounds
                line_content_rects.append(
                    QRectF(
                        fragment.rect.left() + fragment.boundary_offsets[start_index],
                        fragment.rect.top(),
                        max(
                            1.0,
                            fragment.boundary_offsets[end_index]
                            - fragment.boundary_offsets[start_index],
                        ),
                        fragment.rect.height(),
                    )
                )
                continue
            run = self._projection_document.run_by_id(fragment.run_id)
            projection_token = self._projection_document.token_by_id(fragment.token_id)
            if run is None or projection_token is None:
                continue
            renderer = self.inline_object_renderers.renderer_for(fragment.renderer_key)
            if renderer is None:
                continue
            line_content_rects.extend(
                renderer.selection_rects(
                    run,
                    projection_token,
                    fragment.rect,
                    selection_start=range_start,
                    selection_end=range_end,
                    base_font=self._base_font,
                )
            )
        return self._merge_horizontally_touching_rects(line_content_rects)

    def _text_fragment_selection_bounds(
        self,
        fragment: PromptProjectionTextFragment,
        selection: PromptProjectionSelection | None,
    ) -> tuple[int, int] | None:
        """Return the selected local text indices for one text fragment."""

        if selection is None or selection.is_empty:
            return None
        fragment_source_start = fragment.source_positions[0]
        fragment_source_end = fragment.source_positions[-1]
        selected_start = max(selection.start, fragment_source_start)
        selected_end = min(selection.end, fragment_source_end)
        if selected_end <= selected_start:
            return None
        start_index = fragment.source_positions.index(selected_start)
        end_index = fragment.source_positions.index(selected_end)
        return (start_index, end_index)

    def _selection_rects_for_selection(
        self,
        selection: PromptProjectionSelection,
    ) -> tuple[QRectF, ...]:
        """Return the unmerged selection rects covering one raw source range."""

        selection_rects = list(
            self._content_rects_for_source_range(
                start=selection.start,
                end=selection.end,
            )
        )
        selection_rects.extend(
            self._empty_line_selection_rects(
                selection=selection,
            )
        )
        selection_rects.extend(
            self._line_break_selection_rects(
                selection=selection,
            )
        )
        return tuple(selection_rects)

    def _content_rects_for_source_range(
        self,
        *,
        start: int,
        end: int,
    ) -> tuple[QRectF, ...]:
        """Return only visible content rects for one raw source range."""

        range_start = max(0, start)
        range_end = max(0, end)
        if range_end <= range_start:
            return ()

        content_rects: list[QRectF] = []
        fully_selected_token_ids = {
            token.token_id
            for token in self._projection_document.tokens
            if range_start <= token.source_start and token.source_end <= range_end
        }
        for token in self._projection_document.tokens:
            if token.token_id not in fully_selected_token_ids:
                continue
            content_rects.extend(
                QRectF(fragment.rect)
                for fragment in self._tokens.fragments_for_token(token)
            )

        for fragment in self._snapshot.text_fragments:
            if fragment.token_id in fully_selected_token_ids:
                continue
            selection_bounds = self._text_fragment_selection_bounds(
                fragment,
                PromptProjectionSelection(range_start, range_end),
            )
            if selection_bounds is None:
                continue
            start_index, end_index = selection_bounds
            content_rects.append(
                QRectF(
                    fragment.rect.left() + fragment.boundary_offsets[start_index],
                    fragment.rect.top(),
                    max(
                        1.0,
                        fragment.boundary_offsets[end_index]
                        - fragment.boundary_offsets[start_index],
                    ),
                    fragment.rect.height(),
                )
            )

        for object_fragment in self._snapshot.inline_object_fragments:
            if object_fragment.token_id in fully_selected_token_ids:
                continue
            run = self._projection_document.run_by_id(object_fragment.run_id)
            projection_token = self._projection_document.token_by_id(
                object_fragment.token_id
            )
            if run is None or projection_token is None:
                continue
            renderer = self.inline_object_renderers.renderer_for(
                object_fragment.renderer_key
            )
            if renderer is None:
                continue
            content_rects.extend(
                renderer.selection_rects(
                    run,
                    projection_token,
                    object_fragment.rect,
                    selection_start=range_start,
                    selection_end=range_end,
                    base_font=self._base_font,
                )
            )
        return tuple(content_rects)

    def _empty_line_selection_rects(
        self,
        *,
        selection: PromptProjectionSelection,
    ) -> tuple[QRectF, ...]:
        """Return synthetic selection rects for empty wrapped lines in one source range."""

        selection_start = selection.start
        selection_end = selection.end
        if selection_end <= selection_start:
            return ()

        empty_line_highlight_width = self._selection_affordance_width()
        empty_line_rects: list[QRectF] = []
        for line in self._snapshot.lines:
            if line.fragments:
                continue
            if line.source_end <= line.source_start:
                continue
            if not self._empty_line_is_visibly_selected(
                line=line,
                selection=selection,
            ):
                continue
            line_left = (
                line.caret_stops[0].rect.left()
                if line.caret_stops
                else self._document_margin
            )
            empty_line_rects.append(
                QRectF(
                    line_left,
                    line.top,
                    empty_line_highlight_width,
                    line.height,
                )
            )
        return tuple(empty_line_rects)

    def _line_break_selection_rects(
        self,
        *,
        selection: PromptProjectionSelection,
    ) -> tuple[QRectF, ...]:
        """Return explicit selection rects for selected hard line breaks."""

        selection_start = selection.start
        selection_end = selection.end
        if selection_end <= selection_start:
            return ()

        line_break_rects: list[QRectF] = []
        line_break_width = self._selection_affordance_width()
        for line in self._snapshot.lines:
            if not line.fragments:
                continue
            if line.line_break_start is None or line.line_break_end is None:
                continue
            if (
                selection_end <= line.line_break_start
                or line.line_break_end <= selection_start
            ):
                continue
            content_end_stop = self._line_caret_stop_for_source_position(
                line,
                line.source_content_end,
            )
            line_break_left = (
                content_end_stop.rect.left()
                if content_end_stop is not None
                else line.rect.right()
            )
            line_break_rects.append(
                QRectF(
                    line_break_left,
                    line.top,
                    line_break_width,
                    line.height,
                )
            )
        return tuple(line_break_rects)

    def _line_caret_stop_for_source_position(
        self,
        line: PromptProjectionLineSnapshot,
        source_position: int,
    ) -> PromptProjectionLineCaretStopSnapshot | None:
        """Return the line-local caret stop matching one source position."""

        for caret_stop in line.caret_stops:
            state = self._projection_document.caret_map.state_for_projection_position(
                caret_stop.projection_position
            )
            if state.source_position == source_position:
                return caret_stop
        return None

    def _selection_affordance_width(self) -> float:
        """Return the compact width used for invisible selected source spans."""

        return max(
            8.0,
            float(QFontMetricsF(self._base_font).horizontalAdvance(" ")),
        )

    def _empty_line_is_visibly_selected(
        self,
        *,
        line: PromptProjectionLineSnapshot,
        selection: PromptProjectionSelection,
    ) -> bool:
        """Return whether one empty visual line should show selection feedback.

        Empty line feedback follows the moving selection endpoint. A fixed anchor
        at an empty line boundary does not by itself make that line selected.
        """

        if selection.start < line.source_end and line.source_start < selection.end:
            return True
        return (
            selection.anchor_position < line.source_start
            and selection.cursor_position == line.source_start
        )

    def _merged_rects(self, rects: tuple[QRectF, ...]) -> tuple[QRectF, ...]:
        """Merge rects that share one wrapped line and visually touch each other."""

        if not rects:
            return ()
        rects_by_line_index: dict[int, list[QRectF]] = {}
        unassigned_rects: list[QRectF] = []
        for rect in rects:
            line_index = self._line_index_for_rect(rect)
            if line_index is None:
                unassigned_rects.append(QRectF(rect))
                continue
            rects_by_line_index.setdefault(line_index, []).append(QRectF(rect))

        merged_rects: list[QRectF] = []
        for line_index in range(len(self._snapshot.lines)):
            line_rects = rects_by_line_index.get(line_index)
            if not line_rects:
                continue
            merged_rects.extend(self._merge_horizontally_touching_rects(line_rects))
        if unassigned_rects:
            merged_rects.extend(self._merge_rects_by_top_band(unassigned_rects))
        return tuple(merged_rects)

    def _line_index_for_rect(self, rect: QRectF) -> int | None:
        """Return the wrapped-line index that owns the supplied selection rect."""

        rect_center_y = rect.center().y()
        for line_index, line in enumerate(self._snapshot.lines):
            line_bottom = line.top + line.height
            if (line.top - 1.0) <= rect_center_y <= (line_bottom + 1.0):
                return line_index
        return None

    def _merge_horizontally_touching_rects(
        self,
        rects: Sequence[QRectF],
    ) -> tuple[QRectF, ...]:
        """Merge one line's rects when they touch or overlap horizontally."""

        if not rects:
            return ()
        ordered_rects = sorted(rects, key=lambda rect: rect.left())
        merged_rects: list[QRectF] = [QRectF(ordered_rects[0])]
        for rect in ordered_rects[1:]:
            current_rect = merged_rects[-1]
            if rect.left() <= current_rect.right() + 1.0:
                merged_rects[-1] = current_rect.united(rect)
                continue
            merged_rects.append(QRectF(rect))
        return tuple(merged_rects)

    def _merge_rects_by_top_band(
        self,
        rects: Sequence[QRectF],
    ) -> tuple[QRectF, ...]:
        """Merge fallback rects that cannot be assigned to a wrapped line."""

        if not rects:
            return ()
        ordered_rects = sorted(rects, key=lambda rect: (rect.top(), rect.left()))
        merged_rects: list[QRectF] = [QRectF(ordered_rects[0])]
        for rect in ordered_rects[1:]:
            current_rect = merged_rects[-1]
            same_band = (
                abs(current_rect.top() - rect.top()) < 1.0
                and abs(current_rect.height() - rect.height()) < 1.0
            )
            if same_band and rect.left() <= current_rect.right() + 1.0:
                merged_rects[-1] = current_rect.united(rect)
                continue
            merged_rects.append(QRectF(rect))
        return tuple(merged_rects)


def merge_same_row_rects(rects: tuple[QRectF, ...]) -> tuple[QRectF, ...]:
    """Merge erase rectangles that occupy the same visual row."""

    merged: list[QRectF] = []
    for rect in sorted(rects, key=lambda item: (round(item.center().y()), item.left())):
        if not rect.isValid() or rect.isEmpty():
            continue
        if not merged:
            merged.append(QRectF(rect))
            continue
        previous = merged[-1]
        same_row = (
            abs(previous.center().y() - rect.center().y())
            <= max(
                previous.height(),
                rect.height(),
            )
            / 2.0
        )
        touches_previous = rect.left() <= previous.right() + 2.0
        if same_row and touches_previous:
            merged[-1] = previous.united(rect)
            continue
        merged.append(QRectF(rect))
    return tuple(merged)


def rects_nearly_equal(
    first: QRectF, second: QRectF, *, tolerance: float = 1.0
) -> bool:
    """Return whether two caret rects describe the same visual slot."""

    return (
        abs(first.left() - second.left()) <= tolerance
        and abs(first.top() - second.top()) <= tolerance
        and abs(first.width() - second.width()) <= tolerance
        and abs(first.height() - second.height()) <= tolerance
    )


def selection_paints_changed(
    previous_selection: PromptProjectionSelection,
    next_selection: PromptProjectionSelection,
) -> bool:
    """Return whether a selection state change can alter painted selection pixels."""

    if previous_selection.is_empty and next_selection.is_empty:
        return False
    return (
        previous_selection.start != next_selection.start
        or previous_selection.end != next_selection.end
    )


__all__ = [
    "PromptSelectionGeometry",
    "merge_same_row_rects",
    "rects_nearly_equal",
    "selection_paints_changed",
]
