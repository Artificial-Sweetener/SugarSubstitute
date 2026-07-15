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

"""Own projection-aware caret movement for prompt editing surfaces."""

from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import QRectF

from ..debug_probe import log_prompt_editor_probe
from .freshness_controller import ProjectionFreshness
from .layout_engine import PromptProjectionLayout
from .model import (
    PromptProjectionCaretState,
    PromptProjectionDocument,
    PromptProjectionSelection,
)
from .selection_geometry import rects_nearly_equal


class PromptProjectionCaretMovementFreshnessController(Protocol):
    """Expose freshness state needed before vertical movement."""

    freshness: ProjectionFreshness


class PromptProjectionCaretMovementHost(Protocol):
    """Expose surface state consumed by projection-aware caret movement."""

    _anchor_state: PromptProjectionCaretState
    _cursor_state: PromptProjectionCaretState
    _layout: PromptProjectionLayout
    _preferred_x: float | None
    _projection_document: PromptProjectionDocument
    _projection_freshness_controller: PromptProjectionCaretMovementFreshnessController
    _skip_next_same_source_soft_wrap_move: bool

    def _current_caret_document_rect(self) -> QRectF:
        """Return the current document-local caret rectangle."""

    def _flush_pending_projection_update(self, *, reason: str) -> None:
        """Flush pending projection work before movement consumes geometry."""

    def _selection(self) -> PromptProjectionSelection:
        """Return the current source selection."""

    def _set_caret_states(
        self,
        *,
        cursor_state: PromptProjectionCaretState,
        anchor_state: PromptProjectionCaretState,
        reset_preferred_x: bool = True,
        caret_rect_override: QRectF | None = None,
        collapse_expanded_token: bool = True,
        reason: str = "generic",
    ) -> None:
        """Commit resolved cursor and anchor states."""


class PromptProjectionCaretMovementController:
    """Move the caret through projected geometry and source caret-map stops."""

    def __init__(self, host: PromptProjectionCaretMovementHost) -> None:
        """Store the surface host whose caret movement this controller owns."""

        self._host = host

    def move_horizontally(self, direction: int, *, keep_anchor: bool) -> None:
        """Move the caret across plain text or collapsed token boundaries."""

        host = self._host
        pre_flush_origin_rect = host._current_caret_document_rect()
        host._flush_pending_projection_update(reason="move_horizontally")
        skip_same_source_soft_wrap_move = host._skip_next_same_source_soft_wrap_move
        host._skip_next_same_source_soft_wrap_move = False
        origin_state = self._movement_origin_state_for_arrow_key(
            direction=direction,
            keep_anchor=keep_anchor,
        )
        selection = host._selection()
        origin_rect = self._movement_origin_rect_for_arrow_key(
            origin_state=origin_state,
            keep_anchor=keep_anchor,
        )
        if not keep_anchor and not selection.is_empty:
            next_cursor_state = origin_state
            caret_rect_override = None
        else:
            local_target = host._layout.horizontal_line_local_adjacent_target(
                origin_state,
                direction=direction,
                current_rect=origin_rect,
            )
            if local_target is not None:
                next_anchor_state = (
                    host._anchor_state if keep_anchor else local_target.state
                )
                host._set_caret_states(
                    cursor_state=local_target.state,
                    anchor_state=next_anchor_state,
                    caret_rect_override=self._visual_affinity_override_for_target(
                        local_target.state,
                        local_target.rect,
                    ),
                )
                return
            visual_target = host._layout.horizontal_soft_wrap_transition(
                origin_state,
                direction=direction,
                current_rect=origin_rect,
            )
            if visual_target is not None:
                if (
                    skip_same_source_soft_wrap_move
                    and visual_target.state.source_position
                    == origin_state.source_position
                ):
                    visual_target = None
                else:
                    if (
                        visual_target.state.source_position
                        == origin_state.source_position
                        and rects_nearly_equal(
                            visual_target.rect,
                            pre_flush_origin_rect,
                        )
                    ):
                        local_target = (
                            host._layout.horizontal_line_local_adjacent_target(
                                origin_state,
                                direction=direction,
                                current_rect=visual_target.rect,
                            )
                        )
                        if local_target is not None:
                            visual_target = local_target
                    next_anchor_state = (
                        host._anchor_state if keep_anchor else visual_target.state
                    )
                    host._set_caret_states(
                        cursor_state=visual_target.state,
                        anchor_state=next_anchor_state,
                        caret_rect_override=self._visual_affinity_override_for_target(
                            visual_target.state,
                            visual_target.rect,
                        ),
                    )
                    return
            next_cursor_state = (
                host._projection_document.caret_map.next_state(origin_state)
                if direction > 0
                else host._projection_document.caret_map.previous_state(origin_state)
            )
            caret_rect_override = host._layout.horizontal_line_edge_affinity(
                next_cursor_state,
                direction=direction,
                origin_rect=origin_rect,
            )
        next_anchor_state = host._anchor_state if keep_anchor else next_cursor_state
        host._set_caret_states(
            cursor_state=next_cursor_state,
            anchor_state=next_anchor_state,
            caret_rect_override=caret_rect_override,
        )

    def move_vertically(self, direction: int, *, keep_anchor: bool) -> None:
        """Move the caret vertically by adjacent visual line and preferred column."""

        host = self._host
        log_prompt_editor_probe(
            "caret_movement.move_vertically.begin",
            controller_id=id(self),
            direction=direction,
            keep_anchor=keep_anchor,
            cursor_source_position=host._cursor_state.source_position,
            anchor_source_position=host._anchor_state.source_position,
            freshness=str(host._projection_freshness_controller.freshness),
        )
        if (
            host._projection_freshness_controller.freshness
            is ProjectionFreshness.UNAVAILABLE
        ):
            host._flush_pending_projection_update(reason="move_vertically")
        origin_state = self._movement_origin_state_for_arrow_key(
            direction=direction,
            keep_anchor=keep_anchor,
        )
        caret_rect = self._movement_origin_rect_for_arrow_key(
            origin_state=origin_state,
            keep_anchor=keep_anchor,
        )
        preferred_x = (
            caret_rect.center().x()
            if host._preferred_x is None or not host._selection().is_empty
            else host._preferred_x
        )
        current_line_index = host._layout.line_index_for_document_y(
            caret_rect.center().y()
        )
        target = host._layout.vertical_caret_target(
            origin_state,
            direction=direction,
            preferred_x=preferred_x,
            current_line_index=current_line_index,
        )
        if target is None:
            log_prompt_editor_probe(
                "caret_movement.move_vertically.end",
                controller_id=id(self),
                direction=direction,
                keep_anchor=keep_anchor,
                moved=False,
                cursor_source_position=host._cursor_state.source_position,
                anchor_source_position=host._anchor_state.source_position,
            )
            return
        target_line_index = host._layout.line_index_for_document_y(
            target.rect.center().y()
        )
        host._preferred_x = (
            target.rect.center().x()
            if target_line_index == current_line_index
            else preferred_x
        )
        next_anchor_state = host._anchor_state if keep_anchor else target.state
        host._set_caret_states(
            cursor_state=target.state,
            anchor_state=next_anchor_state,
            reset_preferred_x=False,
            caret_rect_override=target.rect,
        )
        log_prompt_editor_probe(
            "caret_movement.move_vertically.end",
            controller_id=id(self),
            direction=direction,
            keep_anchor=keep_anchor,
            moved=True,
            cursor_source_position=host._cursor_state.source_position,
            anchor_source_position=host._anchor_state.source_position,
        )

    def _visual_affinity_override_for_target(
        self,
        target_state: PromptProjectionCaretState,
        target_rect: QRectF,
    ) -> QRectF | None:
        """Return a caret override only when target differs from logical layout."""

        layout_rect = self._host._layout.cursor_rect(target_state, scroll_offset=0.0)
        if rects_nearly_equal(target_rect, layout_rect):
            return None
        return QRectF(target_rect)

    def _movement_origin_state_for_arrow_key(
        self,
        *,
        direction: int,
        keep_anchor: bool,
    ) -> PromptProjectionCaretState:
        """Return the caret state that should own one arrow-key move."""

        host = self._host
        selection = host._selection()
        if keep_anchor or selection.is_empty:
            return host._cursor_state
        boundary_position = selection.start if direction < 0 else selection.end
        return host._projection_document.caret_map.state_for_source_position(
            boundary_position,
            prefer_after=direction > 0,
        )

    def _movement_origin_rect_for_arrow_key(
        self,
        *,
        origin_state: PromptProjectionCaretState,
        keep_anchor: bool,
    ) -> QRectF:
        """Return the document-local caret rect to use as one arrow-key origin."""

        host = self._host
        if keep_anchor or host._selection().is_empty:
            return host._current_caret_document_rect()
        return host._layout.cursor_rect(origin_state, scroll_offset=0.0)


__all__ = [
    "PromptProjectionCaretMovementController",
    "PromptProjectionCaretMovementHost",
]
