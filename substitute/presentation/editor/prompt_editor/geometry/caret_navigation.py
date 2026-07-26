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

"""Resolve caret rectangles and visual-line navigation."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF

from ..projection.metrics import PromptProjectionMetrics
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from ..layout.models import (
    PromptProjectionLayoutSnapshot,
    PromptProjectionLineCaretStopSnapshot,
    PromptProjectionLineSnapshot,
)
from .models import (
    PromptProjectionHorizontalCaretTarget,
    PromptProjectionVerticalCaretTarget,
)
from .source_lines import source_line_ranges
from .state import PromptProjectionGeometryInput


@dataclass(frozen=True, slots=True)
class PromptCaretNavigation:
    """Resolve caret geometry from one immutable layout input."""

    input: PromptProjectionGeometryInput

    @property
    def _projection_document(self) -> PromptProjectionDocument:
        """Return the immutable projected document."""

        return self.input.projection_document

    @property
    def _snapshot(self) -> PromptProjectionLayoutSnapshot:
        """Return the immutable layout snapshot."""

        return self.input.layout_snapshot

    @property
    def _document_margin(self) -> float:
        """Return the captured document inset."""

        return self.input.document_margin

    @property
    def _metrics(self) -> PromptProjectionMetrics:
        """Return the captured font metrics."""

        return self.input.metrics

    def caret_rect_for_projection_position(self, projection_position: int) -> QRectF:
        """Return the prepared rect for one projection caret position."""

        return self._caret_rect_for_projection_position(projection_position)

    def cursor_rect(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        scroll_offset: float = 0.0,
    ) -> QRectF:
        """Return the viewport-local rect for one logical caret."""

        return self._cursor_rect_from_geometry(
            caret_state,
            scroll_offset=scroll_offset,
        )

    def horizontal_soft_wrap_transition(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        direction: int,
        current_rect: QRectF,
    ) -> PromptProjectionHorizontalCaretTarget | None:
        """Resolve a horizontal move across one soft-wrap boundary."""

        return self._horizontal_soft_wrap_transition_from_geometry(
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
        """Resolve the origin row affinity for one wrap-edge move."""

        return self._horizontal_line_edge_affinity_from_geometry(
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
        """Resolve the adjacent caret stop on one visual line."""

        return self._horizontal_line_local_adjacent_target_from_geometry(
            caret_state,
            direction=direction,
            current_rect=current_rect,
        )

    def vertical_caret_target(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        direction: int,
        preferred_x: float,
        current_line_index: int | None = None,
    ) -> PromptProjectionVerticalCaretTarget | None:
        """Resolve one vertical caret destination."""

        return self._vertical_caret_target_from_geometry(
            caret_state,
            direction=direction,
            preferred_x=preferred_x,
            current_line_index=current_line_index,
        )

    def _cursor_rect_from_geometry(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        scroll_offset: float = 0.0,
    ) -> QRectF:
        """Return the viewport-local caret rect for one logical caret state."""

        resolved_state = self._projection_document.caret_map.resolve_state(caret_state)
        projection_position = (
            self._projection_document.caret_map.projection_position_for_state(
                resolved_state
            )
        )
        rect = self._caret_rect_for_projection_position(projection_position)
        return rect.translated(0.0, -scroll_offset)

    def line_index_for_document_y(self, y_position: float) -> int | None:
        """Return the wrapped-line index owning one document-local y coordinate."""

        for line_index, line in enumerate(self._snapshot.lines):
            line_bottom = line.top + line.height
            if (line.top - 1.0) <= y_position <= (line_bottom + 1.0):
                return line_index
        return None

    def source_position_at_visual_line_content_end(self, source_position: int) -> bool:
        """Return whether a source position sits at a visual line content end."""

        for line in self._snapshot.lines:
            if line.source_content_end == source_position:
                return True
        return False

    def _horizontal_soft_wrap_transition_from_geometry(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        direction: int,
        current_rect: QRectF,
    ) -> PromptProjectionHorizontalCaretTarget | None:
        """Return a same-source horizontal move across a soft-wrap boundary."""

        if direction not in (-1, 1):
            raise ValueError("Horizontal caret movement direction must be -1 or 1.")
        line_index = self.line_index_for_document_y(current_rect.center().y())
        if line_index is None:
            return None
        line = self._snapshot.lines[line_index]
        if not line.caret_stops:
            return None
        resolved_state = self._projection_document.caret_map.resolve_state(caret_state)
        projection_position = (
            self._projection_document.caret_map.projection_position_for_state(
                resolved_state
            )
        )
        current_stop = self._line_caret_stop_for_projection_position(
            line,
            projection_position,
        )
        if current_stop is None:
            return None
        if direction > 0:
            if current_stop is not line.caret_stops[-1]:
                return None
            if line_index + 1 >= len(self._snapshot.lines):
                return None
            next_line = self._snapshot.lines[line_index + 1]
            if (
                not next_line.caret_stops
                or next_line.caret_stops[0].projection_position != projection_position
            ):
                return None
            return PromptProjectionHorizontalCaretTarget(
                state=resolved_state,
                rect=QRectF(next_line.caret_stops[0].rect),
            )

        if current_stop is not line.caret_stops[0] or line_index <= 0:
            return None
        previous_line = self._snapshot.lines[line_index - 1]
        if (
            not previous_line.caret_stops
            or previous_line.caret_stops[-1].projection_position != projection_position
        ):
            return None
        return PromptProjectionHorizontalCaretTarget(
            state=resolved_state,
            rect=QRectF(previous_line.caret_stops[-1].rect),
        )

    def _horizontal_line_edge_affinity_from_geometry(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        direction: int,
        origin_rect: QRectF,
    ) -> QRectF | None:
        """Return the origin row's edge rect when a source move lands on a wrap edge."""

        if direction not in (-1, 1):
            raise ValueError("Horizontal caret movement direction must be -1 or 1.")
        line_index = self.line_index_for_document_y(origin_rect.center().y())
        if line_index is None:
            return None
        line = self._snapshot.lines[line_index]
        if not line.caret_stops:
            return None
        resolved_state = self._projection_document.caret_map.resolve_state(caret_state)
        projection_position = (
            self._projection_document.caret_map.projection_position_for_state(
                resolved_state
            )
        )
        if (
            direction > 0
            and line.caret_stops[-1].projection_position == projection_position
        ):
            return QRectF(line.caret_stops[-1].rect)
        if (
            direction < 0
            and line.caret_stops[0].projection_position == projection_position
        ):
            return QRectF(line.caret_stops[0].rect)
        return None

    def _horizontal_line_local_adjacent_target_from_geometry(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        direction: int,
        current_rect: QRectF,
    ) -> PromptProjectionHorizontalCaretTarget | None:
        """Return the adjacent caret stop on the current visual line."""

        if direction not in (-1, 1):
            raise ValueError("Horizontal caret movement direction must be -1 or 1.")
        line_index = self.line_index_for_document_y(current_rect.center().y())
        if line_index is None:
            return None
        line = self._snapshot.lines[line_index]
        if not line.caret_stops:
            return None
        resolved_state = self._projection_document.caret_map.resolve_state(caret_state)
        projection_position = (
            self._projection_document.caret_map.projection_position_for_state(
                resolved_state
            )
        )
        adjacent_state = (
            self._projection_document.caret_map.next_state(resolved_state)
            if direction > 0
            else self._projection_document.caret_map.previous_state(resolved_state)
        )
        # Token edges and content boundaries can share one visible x-position.
        if (
            adjacent_state != resolved_state
            and self._projection_document.caret_map.projection_position_for_state(
                adjacent_state
            )
            == projection_position
        ):
            return PromptProjectionHorizontalCaretTarget(
                state=adjacent_state,
                rect=self.cursor_rect(adjacent_state, scroll_offset=0.0),
            )
        current_stop_index = self._line_caret_stop_index_for_projection_position(
            line,
            projection_position,
            current_rect=current_rect,
        )
        if current_stop_index is None:
            return None
        target_stop_index = current_stop_index + direction
        if target_stop_index < 0 or target_stop_index >= len(line.caret_stops):
            return None
        target_stop = line.caret_stops[target_stop_index]
        target_state = (
            self._projection_document.caret_map.state_for_projection_position(
                target_stop.projection_position,
                prefer_after=direction > 0,
            )
        )
        return PromptProjectionHorizontalCaretTarget(
            state=self._projection_document.caret_map.resolve_state(target_state),
            rect=QRectF(target_stop.rect),
        )

    def _caret_rect_for_projection_position(self, projection_position: int) -> QRectF:
        """Return a caret rect without falling back to document origin for live lines."""

        try:
            return QRectF(
                self._snapshot.caret_rects_by_projection_position[projection_position]
            )
        except KeyError:
            pass
        nearest_stop = self._nearest_line_caret_stop_for_projection_position(
            projection_position
        )
        if nearest_stop is not None:
            return QRectF(nearest_stop.rect)
        return QRectF(
            0.0,
            self._document_margin,
            1.0,
            self._metrics.text_line_height,
        )

    @staticmethod
    def _line_caret_stop_for_projection_position(
        line: PromptProjectionLineSnapshot,
        projection_position: int,
    ) -> PromptProjectionLineCaretStopSnapshot | None:
        """Return the line-local caret stop for one projection boundary."""

        for caret_stop in line.caret_stops:
            if caret_stop.projection_position == projection_position:
                return caret_stop
        return None

    @staticmethod
    def _line_caret_stop_index_for_projection_position(
        line: PromptProjectionLineSnapshot,
        projection_position: int,
        *,
        current_rect: QRectF,
    ) -> int | None:
        """Return the line-local stop index nearest to the current visual rect."""

        nearest_index: int | None = None
        nearest_distance: float | None = None
        for index, caret_stop in enumerate(line.caret_stops):
            if caret_stop.projection_position != projection_position:
                continue
            distance = abs(caret_stop.rect.center().x() - current_rect.center().x())
            if nearest_distance is None or distance < nearest_distance:
                nearest_index = index
                nearest_distance = distance
        return nearest_index

    def _nearest_line_caret_stop_for_projection_position(
        self,
        projection_position: int,
    ) -> PromptProjectionLineCaretStopSnapshot | None:
        """Return the nearest line-local caret stop by projection distance."""

        nearest_stop: PromptProjectionLineCaretStopSnapshot | None = None
        nearest_distance: int | None = None
        for line in self._snapshot.lines:
            for caret_stop in line.caret_stops:
                distance = abs(caret_stop.projection_position - projection_position)
                if nearest_distance is None or distance < nearest_distance:
                    nearest_distance = distance
                    nearest_stop = caret_stop
        return nearest_stop

    def source_line_index_for_position(self, source_position: int) -> int:
        """Return the newline-delimited source line containing one cursor position."""

        source_text = self._projection_document.source_text
        clamped_position = max(0, min(source_position, len(source_text)))
        for line_index, (source_start, source_end) in enumerate(
            source_line_ranges(source_text)
        ):
            if source_start <= clamped_position < source_end:
                return line_index
            if source_start == source_end == clamped_position:
                return line_index
        return max(0, len(source_line_ranges(source_text)) - 1)

    def _vertical_caret_target_from_geometry(
        self,
        caret_state: PromptProjectionCaretState,
        *,
        direction: int,
        preferred_x: float,
        current_line_index: int | None = None,
    ) -> PromptProjectionVerticalCaretTarget | None:
        """Resolve one vertical caret target using adjacent-line or edge-clamp rules."""

        if direction not in (-1, 1):
            raise ValueError("Vertical caret movement direction must be -1 or 1.")

        if not self._snapshot.lines:
            return None

        resolved_state = self._projection_document.caret_map.resolve_state(caret_state)
        if current_line_index is None:
            current_line_index = self.line_index_for_document_y(
                self.cursor_rect(resolved_state, scroll_offset=0.0).center().y()
            )
        if current_line_index is None:
            return None

        target_line_index = current_line_index + direction
        while (
            0 <= target_line_index < len(self._snapshot.lines)
            and not self._snapshot.lines[target_line_index].caret_stops
        ):
            target_line_index += direction
        if not 0 <= target_line_index < len(self._snapshot.lines):
            target_line_index = current_line_index

        target_line = self._snapshot.lines[target_line_index]
        if not target_line.caret_stops:
            return None

        if target_line_index == current_line_index:
            target_stop = (
                target_line.caret_stops[0]
                if direction < 0
                else target_line.caret_stops[-1]
            )
        else:
            target_stop = min(
                target_line.caret_stops,
                key=lambda caret_stop: abs(caret_stop.rect.center().x() - preferred_x),
            )
        target_state = (
            self._projection_document.caret_map.state_for_projection_position(
                target_stop.projection_position,
                prefer_after=preferred_x >= target_stop.rect.center().x(),
            )
        )
        return PromptProjectionVerticalCaretTarget(
            state=self._projection_document.caret_map.resolve_state(target_state),
            rect=QRectF(target_stop.rect),
        )


__all__ = ["PromptCaretNavigation"]
