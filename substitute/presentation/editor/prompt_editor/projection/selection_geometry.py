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

"""Own source-backed caret, selection, and source-range projection geometry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QRectF

from .model import PromptProjectionCaretState, PromptProjectionSelection

if TYPE_CHECKING:
    from .layout_engine import PromptProjectionLayout


@dataclass(frozen=True, slots=True)
class PromptProjectionVerticalCaretTarget:
    """Describe one vertical caret destination resolved by visual-line affinity."""

    state: PromptProjectionCaretState
    rect: QRectF


@dataclass(frozen=True, slots=True)
class PromptProjectionHorizontalCaretTarget:
    """Describe one horizontal caret destination resolved by visual-line affinity."""

    state: PromptProjectionCaretState
    rect: QRectF


@dataclass(frozen=True, slots=True)
class PromptProjectionSourceLineRect:
    """Describe one viewport-local logical source line row."""

    line_index: int
    rect: QRectF


@dataclass(frozen=True, slots=True)
class PromptProjectionSelectionGeometry:
    """Route source-backed geometry requests through the projection layout state."""

    layout: PromptProjectionLayout

    def selection_rects(
        self,
        selection: PromptProjectionSelection | None,
    ) -> tuple[QRectF, ...]:
        """Return projection-aligned document rects for one source-backed selection."""

        return self.layout._selection_rects_from_geometry(selection)  # noqa: SLF001

    def cursor_rect(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        scroll_offset: float = 0.0,
    ) -> QRectF:
        """Return the viewport-local caret rect for one logical caret state."""

        return self.layout._cursor_rect_from_geometry(  # noqa: SLF001
            caret_state,
            scroll_offset=scroll_offset,
        )

    def source_line_rects(
        self,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[PromptProjectionSourceLineRect, ...]:
        """Return visible viewport rects for newline-delimited source lines."""

        return self.layout._source_line_rects_from_geometry(  # noqa: SLF001
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )

    def source_range_fragments(
        self,
        start: int,
        end: int,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Return wrapped viewport fragments for one raw source range."""

        return self.layout._source_range_fragments_from_geometry(  # noqa: SLF001
            start,
            end,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )

    def vertical_caret_target(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        direction: int,
        preferred_x: float,
        current_line_index: int | None = None,
    ) -> PromptProjectionVerticalCaretTarget | None:
        """Resolve one vertical caret target using adjacent-line or edge-clamp rules."""

        return self.layout._vertical_caret_target_from_geometry(  # noqa: SLF001
            caret_state,
            direction=direction,
            preferred_x=preferred_x,
            current_line_index=current_line_index,
        )

    def horizontal_soft_wrap_transition(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        direction: int,
        current_rect: QRectF,
    ) -> PromptProjectionHorizontalCaretTarget | None:
        """Return a same-source horizontal move across a soft-wrap boundary."""

        return self.layout._horizontal_soft_wrap_transition_from_geometry(  # noqa: SLF001
            caret_state,
            direction=direction,
            current_rect=current_rect,
        )

    def horizontal_line_edge_affinity(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        direction: int,
        origin_rect: QRectF,
    ) -> QRectF | None:
        """Return the origin row's edge rect when a move lands on a wrap edge."""

        return self.layout._horizontal_line_edge_affinity_from_geometry(  # noqa: SLF001
            caret_state,
            direction=direction,
            origin_rect=origin_rect,
        )

    def horizontal_line_local_adjacent_target(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        direction: int,
        current_rect: QRectF,
    ) -> PromptProjectionHorizontalCaretTarget | None:
        """Return the adjacent caret stop on the current visual line."""

        return self.layout._horizontal_line_local_adjacent_target_from_geometry(  # noqa: SLF001
            caret_state,
            direction=direction,
            current_rect=current_rect,
        )


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
    "PromptProjectionHorizontalCaretTarget",
    "PromptProjectionSelectionGeometry",
    "PromptProjectionSourceLineRect",
    "PromptProjectionVerticalCaretTarget",
    "merge_same_row_rects",
    "rects_nearly_equal",
    "selection_paints_changed",
]
