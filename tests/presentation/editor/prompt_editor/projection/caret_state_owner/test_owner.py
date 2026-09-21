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

"""Test coherent projected-caret state publication."""

from __future__ import annotations

from PySide6.QtCore import QRectF

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.projection.caret_state_owner import (
    PromptProjectionCaretStateOwner,
)


def _state(position: int) -> PromptProjectionCaretState:
    """Build one distinguishable projection caret state."""
    return PromptProjectionCaretState(
        source_position=position,
        placement=PromptProjectionCaretPlacement.PLAIN_TEXT,
    )


def test_interaction_publication_updates_complete_state_and_consumes_affinity() -> None:
    """A committed interaction should atomically replace all coupled caret state."""
    owner = PromptProjectionCaretStateOwner(_state(0))
    owner.set_preferred_x(42.0)
    owner.mark_source_edit_horizontal_movement_origin()
    override = QRectF(1.0, 2.0, 3.0, 4.0)

    owner.publish(
        cursor_state=_state(5),
        anchor_state=_state(2),
        caret_rect_override=override,
        reset_preferred_x=True,
    )
    override.translate(50.0, 50.0)

    assert owner.cursor_state == _state(5)
    assert owner.anchor_state == _state(2)
    assert owner.caret_rect_override == QRectF(1.0, 2.0, 3.0, 4.0)
    assert owner.preferred_x is None
    assert not owner.source_edit_horizontal_movement_origin_is_pending()


def test_source_state_replacement_can_preserve_vertical_navigation_column() -> None:
    """Projection remapping should preserve preferred x unless its caller invalidates it."""
    owner = PromptProjectionCaretStateOwner(_state(0))
    owner.set_preferred_x(19.5)
    owner.publish(
        cursor_state=_state(1),
        anchor_state=_state(1),
        caret_rect_override=QRectF(3.0, 4.0, 1.0, 10.0),
        reset_preferred_x=False,
    )

    owner.replace_states(
        cursor_state=_state(7),
        anchor_state=_state(6),
        clear_caret_rect_override=True,
        reset_preferred_x=False,
    )

    assert owner.cursor_state == _state(7)
    assert owner.anchor_state == _state(6)
    assert owner.caret_rect_override is None
    assert owner.preferred_x == 19.5


def test_source_edit_horizontal_origin_is_consumed_exactly_once() -> None:
    """The wrap-affinity escape marker should affect only the next horizontal move."""
    owner = PromptProjectionCaretStateOwner(_state(0))

    owner.mark_source_edit_horizontal_movement_origin()

    assert owner.consume_source_edit_horizontal_movement_origin()
    assert not owner.consume_source_edit_horizontal_movement_origin()
