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

"""Resolve pointer and drag-selection targets over immutable geometry."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QFont

from ..projection.metrics import PromptProjectionMetrics
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
)
from ..projection.region_caret_navigation import (
    resolve_region_separator_line_caret_state,
)
from ..projection.tokens import PromptProjectionInlineObjectRendererRegistry
from ..layout.models import (
    PromptProjectionInlineObjectFragment,
    PromptProjectionLayoutSnapshot,
    PromptProjectionLineCaretStopSnapshot,
    PromptProjectionLineSnapshot,
    PromptProjectionTextFragment,
)
from .caret_navigation import PromptCaretNavigation
from .models import (
    PromptProjectionCaretHit,
    PromptProjectionDragSelectionTarget,
)
from .state import PromptProjectionGeometryInput


@dataclass(frozen=True, slots=True)
class PromptHitTester:
    """Resolve pointer geometry from one immutable layout input."""

    input: PromptProjectionGeometryInput
    _caret: PromptCaretNavigation

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
    def _metrics(self) -> PromptProjectionMetrics:
        """Return the captured font metrics."""

        return self.input.metrics

    @property
    def inline_object_renderers(self) -> PromptProjectionInlineObjectRendererRegistry:
        """Return the stable inline renderer registry."""

        return self.input.inline_object_renderers

    def hit_test(
        self,
        viewport_position: QPointF,
        *,
        scroll_offset: float,
        preferred_line_index: int | None = None,
    ) -> PromptProjectionCaretState:
        """Resolve one viewport point to a logical caret."""

        return self._hit_test_from_geometry(
            viewport_position,
            scroll_offset=scroll_offset,
            preferred_line_index=preferred_line_index,
        )

    def caret_hit_test(
        self,
        viewport_position: QPointF,
        *,
        scroll_offset: float,
        preferred_line_index: int | None = None,
    ) -> PromptProjectionCaretHit:
        """Resolve one viewport point to logical and visual caret state."""

        return self._caret_hit_test_from_geometry(
            viewport_position,
            scroll_offset=scroll_offset,
            preferred_line_index=preferred_line_index,
        )

    def resolve_drag_selection_endpoint(
        self,
        viewport_position: QPointF,
        *,
        scroll_offset: float,
        anchor_line_index: int | None = None,
        preferred_line_index: int | None = None,
    ) -> PromptProjectionDragSelectionTarget:
        """Resolve one wrapped-line drag-selection endpoint."""

        return self._resolve_drag_selection_endpoint_from_geometry(
            viewport_position,
            scroll_offset=scroll_offset,
            anchor_line_index=anchor_line_index,
            preferred_line_index=preferred_line_index,
        )

    def _hit_test_from_geometry(
        self,
        viewport_position: QPointF,
        *,
        scroll_offset: float,
        preferred_line_index: int | None = None,
    ) -> PromptProjectionCaretState:
        """Return the logical caret state implied by one viewport-local pointer point."""

        return self.caret_hit_test(
            viewport_position,
            scroll_offset=scroll_offset,
            preferred_line_index=preferred_line_index,
        ).state

    def _caret_hit_test_from_geometry(
        self,
        viewport_position: QPointF,
        *,
        scroll_offset: float,
        preferred_line_index: int | None = None,
    ) -> PromptProjectionCaretHit:
        """Return the logical and visual caret target for one pointer point."""

        document_position = QPointF(
            viewport_position.x(),
            viewport_position.y() + scroll_offset,
        )
        object_fragment = self._snapshot.inline_object_fragment_at(document_position)
        if object_fragment is not None:
            run = self._projection_document.run_by_id(object_fragment.run_id)
            token = self._projection_document.token_by_id(object_fragment.token_id)
            if run is not None and token is not None:
                renderer = self.inline_object_renderers.renderer_for(
                    object_fragment.renderer_key
                )
                if renderer is not None:
                    state = self._projection_document.caret_map.resolve_state(
                        renderer.hit_test_caret_state(
                            run,
                            token,
                            object_fragment.rect,
                            document_position,
                            base_font=self._base_font,
                        )
                    )
                    return PromptProjectionCaretHit(
                        state=state,
                        document_rect=self._inline_object_caret_rect_for_state(
                            object_fragment,
                            state,
                        ),
                    )

        line_index = self._line_index_for_pointer_y(
            document_position.y(),
            preferred_line_index=preferred_line_index,
        )
        if line_index is None:
            return PromptProjectionCaretHit(
                state=PromptProjectionCaretState(source_position=0),
                document_rect=QRectF(
                    0.0,
                    self._document_margin,
                    1.0,
                    self._metrics.text_line_height,
                ),
            )

        line = self._snapshot.lines[line_index]
        line_hit = self._line_text_fragment_caret_hit(line, document_position)
        if line_hit is not None:
            return line_hit

        line_caret_stop = self._line_caret_stop_nearest_x(line, document_position.x())
        if line_caret_stop is not None:
            return self._line_caret_stop_hit(
                line,
                line_caret_stop,
                x_position=document_position.x(),
            )

        return self._nearest_document_caret_hit(document_position)

    def _resolve_drag_selection_endpoint_from_geometry(
        self,
        viewport_position: QPointF,
        *,
        scroll_offset: float,
        anchor_line_index: int | None = None,
        preferred_line_index: int | None = None,
    ) -> PromptProjectionDragSelectionTarget:
        """Resolve one drag-selection endpoint using wrapped-line row progression."""

        document_position = QPointF(
            viewport_position.x(),
            viewport_position.y() + scroll_offset,
        )
        line_index = self._drag_line_index_for_pointer_y(
            document_position.y(),
            anchor_line_index=anchor_line_index,
            preferred_line_index=preferred_line_index,
        )
        if line_index is None:
            return PromptProjectionDragSelectionTarget(
                state=self._nearest_document_caret_state(document_position),
                line_index=None,
            )

        line = self._snapshot.lines[line_index]
        line_caret_stop = self._drag_line_caret_stop_for_x(
            line,
            document_position.x(),
            direction=_drag_direction(
                anchor_line_index=anchor_line_index,
                line_index=line_index,
            ),
        )
        if line_caret_stop is None:
            return PromptProjectionDragSelectionTarget(
                state=self._nearest_document_caret_state(document_position),
                line_index=line_index,
            )

        return PromptProjectionDragSelectionTarget(
            state=self._projection_document.caret_map.resolve_state(
                self._projection_document.caret_map.state_for_projection_position(
                    line_caret_stop.projection_position
                )
            ),
            line_index=line_index,
        )

    def _line_index_for_pointer_y(
        self,
        y_position: float,
        *,
        preferred_line_index: int | None,
    ) -> int | None:
        """Resolve one pointer y-coordinate to the best matching visual line index."""

        containing_indices = [
            line_index
            for line_index, line in enumerate(self._snapshot.lines)
            if (line.top - 1.0) <= y_position <= ((line.top + line.height) + 1.0)
        ]
        if containing_indices:
            if (
                preferred_line_index is not None
                and preferred_line_index in containing_indices
            ):
                return preferred_line_index
            return containing_indices[0]

        best_line_index: int | None = None
        best_distance: float | None = None
        for line_index, line in enumerate(self._snapshot.lines):
            distance = self._axis_distance(
                axis_value=y_position,
                start=line.top,
                end=line.top + line.height,
            )
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_line_index = line_index
                continue
            if (
                distance == best_distance
                and preferred_line_index is not None
                and line_index == preferred_line_index
            ):
                best_line_index = line_index
        return best_line_index

    def _drag_line_index_for_pointer_y(
        self,
        y_position: float,
        *,
        anchor_line_index: int | None,
        preferred_line_index: int | None,
    ) -> int | None:
        """Resolve the wrapped line that should own one drag-selection pointer y."""

        if not self._snapshot.lines:
            return None
        for line_index, line in enumerate(self._snapshot.lines):
            line_bottom = line.top + line.height
            if line.top <= y_position < line_bottom:
                return line_index
            if (
                line_index == len(self._snapshot.lines) - 1
                and y_position == line_bottom
            ):
                return line_index

        best_line_index: int | None = None
        best_distance: float | None = None
        best_center_distance: float | None = None
        direction = _drag_direction(
            anchor_line_index=anchor_line_index,
            line_index=preferred_line_index,
        )
        for line_index, line in enumerate(self._snapshot.lines):
            distance = self._axis_distance(
                axis_value=y_position,
                start=line.top,
                end=line.top + line.height,
            )
            center_distance = abs((line.top + (line.height / 2.0)) - y_position)
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_center_distance = center_distance
                best_line_index = line_index
                continue
            if distance > best_distance:
                continue
            if (
                best_center_distance is not None
                and center_distance < best_center_distance
            ):
                best_center_distance = center_distance
                best_line_index = line_index
                continue
            if (
                center_distance == best_center_distance
                and preferred_line_index is not None
                and line_index == preferred_line_index
            ):
                best_line_index = line_index
                continue
            if (
                center_distance == best_center_distance
                and direction is not None
                and best_line_index is not None
                and (
                    (direction > 0 and line_index > best_line_index)
                    or (direction < 0 and line_index < best_line_index)
                )
            ):
                best_line_index = line_index
        return best_line_index

    def _inline_object_caret_rect_for_state(
        self,
        fragment: PromptProjectionInlineObjectFragment,
        state: PromptProjectionCaretState,
    ) -> QRectF:
        """Return the fragment-local caret rect matching one renderer hit state."""

        projection_position = (
            self._projection_document.caret_map.projection_position_for_state(state)
        )
        line_index = self._caret.line_index_for_document_y(fragment.rect.center().y())
        if line_index is not None:
            for caret_stop in self._snapshot.lines[line_index].caret_stops:
                if caret_stop.projection_position == projection_position:
                    return QRectF(caret_stop.rect)
        return self._caret.cursor_rect(state, scroll_offset=0.0)

    def _line_text_fragment_caret_hit(
        self,
        line: PromptProjectionLineSnapshot,
        document_position: QPointF,
    ) -> PromptProjectionCaretHit | None:
        """Return the source-backed text-fragment caret hit inside one resolved line."""

        for fragment in line.fragments:
            if not isinstance(fragment, PromptProjectionTextFragment):
                continue
            if not fragment.rect.contains(document_position):
                continue
            run = self._projection_document.run_by_id(fragment.run_id)
            if run is None or not run.source_backed:
                continue
            slot_index = self._nearest_boundary_index(fragment, document_position.x())
            document_rect = QRectF(
                fragment.rect.left() + fragment.boundary_offsets[slot_index],
                line.top,
                1.0,
                line.height,
            )
            if fragment.token_id is not None:
                state = self._projection_document.caret_map.resolve_state(
                    PromptProjectionCaretState(
                        source_position=fragment.source_positions[slot_index],
                        placement=PromptProjectionCaretPlacement.TOKEN_CONTENT,
                        token_id=fragment.token_id,
                        run_id=run.run_id,
                        token_slot=self._token_slot_for_text_fragment(
                            run,
                            fragment,
                            slot_index,
                        ),
                    )
                )
                return PromptProjectionCaretHit(
                    state=state,
                    document_rect=document_rect,
                )
            state = self._projection_document.caret_map.resolve_state(
                self._projection_document.caret_map.state_for_projection_position(
                    fragment.projection_start + slot_index,
                    prefer_after=document_position.x()
                    >= (fragment.rect.left() + fragment.boundary_offsets[slot_index]),
                )
            )
            return PromptProjectionCaretHit(
                state=state,
                document_rect=document_rect,
            )
        return None

    def _line_caret_stop_hit(
        self,
        line: PromptProjectionLineSnapshot,
        caret_stop: PromptProjectionLineCaretStopSnapshot,
        *,
        x_position: float,
    ) -> PromptProjectionCaretHit:
        """Return the caret hit represented by one line-local caret stop."""

        state = self._projection_document.caret_map.resolve_state(
            self._projection_document.caret_map.state_for_projection_position(
                caret_stop.projection_position,
                prefer_after=x_position >= caret_stop.rect.center().x(),
            )
        )
        state = resolve_region_separator_line_caret_state(
            self._projection_document.caret_map,
            state,
            line_source_start=line.source_start,
            line_source_end=line.source_end,
        )
        return PromptProjectionCaretHit(
            state=state,
            document_rect=QRectF(caret_stop.rect),
        )

    @staticmethod
    def _line_caret_stop_nearest_x(
        line: PromptProjectionLineSnapshot,
        x_position: float,
    ) -> PromptProjectionLineCaretStopSnapshot | None:
        """Return the closest line-local caret stop to one document x-coordinate."""

        if not line.caret_stops:
            return None
        return min(
            line.caret_stops,
            key=lambda caret_stop: abs(caret_stop.rect.center().x() - x_position),
        )

    @staticmethod
    def _drag_line_caret_stop_for_x(
        line: PromptProjectionLineSnapshot,
        x_position: float,
        *,
        direction: int | None,
    ) -> PromptProjectionLineCaretStopSnapshot | None:
        """Return the drag caret stop that matches the row-transition direction."""

        if not line.caret_stops:
            return None
        if direction is None or direction == 0:
            return PromptHitTester._line_caret_stop_nearest_x(
                line,
                x_position,
            )
        if direction > 0:
            last_caret_stop = line.caret_stops[-1]
            if x_position > last_caret_stop.rect.left():
                return last_caret_stop
            downward_stops = (
                line.caret_stops[:-1] if len(line.caret_stops) > 1 else line.caret_stops
            )
            for caret_stop in reversed(downward_stops):
                if x_position >= caret_stop.rect.left():
                    return caret_stop
            return downward_stops[0]
        for caret_stop in line.caret_stops:
            if x_position <= caret_stop.rect.left():
                return caret_stop
        return line.caret_stops[-1]

    def _nearest_document_caret_state(
        self,
        document_position: QPointF,
    ) -> PromptProjectionCaretState:
        """Return the globally nearest caret state when no visual line can resolve the point."""

        return self._nearest_document_caret_hit(document_position).state

    def _nearest_document_caret_hit(
        self,
        document_position: QPointF,
    ) -> PromptProjectionCaretHit:
        """Return the globally nearest caret hit when no visual line can resolve the point."""

        nearest_projection_position: int | None = None
        nearest_distance: float | None = None
        for (
            projection_position,
            caret_rect,
        ) in self._snapshot.caret_rects_by_projection_position.items():
            dx = caret_rect.center().x() - document_position.x()
            dy = caret_rect.center().y() - document_position.y()
            distance = (dx * dx) + (dy * dy)
            if nearest_distance is None or distance < nearest_distance:
                nearest_distance = distance
                nearest_projection_position = projection_position
        if nearest_projection_position is None:
            return PromptProjectionCaretHit(
                state=PromptProjectionCaretState(source_position=0),
                document_rect=QRectF(
                    0.0,
                    self._document_margin,
                    1.0,
                    self._metrics.text_line_height,
                ),
            )
        nearest_rect = self._snapshot.caret_rects_by_projection_position[
            nearest_projection_position
        ]
        state = self._projection_document.caret_map.resolve_state(
            self._projection_document.caret_map.state_for_projection_position(
                nearest_projection_position,
                prefer_after=document_position.x() >= nearest_rect.center().x(),
            )
        )
        return PromptProjectionCaretHit(
            state=state,
            document_rect=QRectF(nearest_rect),
        )

    @staticmethod
    def _axis_distance(*, axis_value: float, start: float, end: float) -> float:
        """Return the distance from one axis coordinate to one closed interval."""

        if axis_value < start:
            return start - axis_value
        if axis_value > end:
            return axis_value - end
        return 0.0

    def _nearest_boundary_index(
        self,
        fragment: PromptProjectionTextFragment,
        x_position: float,
    ) -> int:
        """Return the nearest boundary index inside one text fragment."""

        return min(
            range(len(fragment.boundary_offsets)),
            key=lambda boundary_index: abs(
                (fragment.rect.left() + fragment.boundary_offsets[boundary_index])
                - x_position
            ),
        )

    def _token_slot_for_text_fragment(
        self,
        run: PromptProjectionRun,
        fragment: PromptProjectionTextFragment,
        slot_index: int,
    ) -> int:
        """Return the token-content slot implied by one text-fragment boundary."""

        return (fragment.projection_start - run.projection_start) + slot_index


def _drag_direction(
    *, anchor_line_index: int | None, line_index: int | None
) -> int | None:
    """Return the wrapped-line drag direction implied by one anchor and target line."""

    if anchor_line_index is None or line_index is None:
        return None
    if line_index > anchor_line_index:
        return 1
    if line_index < anchor_line_index:
        return -1
    return 0


__all__ = ["PromptHitTester"]
