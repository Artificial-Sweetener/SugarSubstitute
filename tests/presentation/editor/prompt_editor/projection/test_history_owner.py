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

"""Test mounted prompt projection history ownership."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from tests.support.prompt_editor.projection_engine_support import ensure_qapp
from tests.support.prompt_editor.projection_surface_factory import (
    new_projection_surface,
    surface_source_commands,
)
from tests.support.prompt_editor.projection_surface_support import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)


def test_mounted_history_owner_captures_projection_state_and_signals(
    widgets: list[QWidget],
) -> None:
    """Publish undo restoration state and availability through one owner."""

    ensure_qapp()
    surface = new_projection_surface()
    widgets.append(surface)
    surface_source_commands(surface).set_source_text("alpha")
    surface.set_cursor_positions(cursor_position=4, anchor_position=1)
    undo_availability: list[bool] = []
    redo_availability: list[bool] = []
    surface.undoAvailableChanged.connect(undo_availability.append)
    surface.redoAvailableChanged.connect(redo_availability.append)

    payload = surface.history.undo_restoration_payload()
    surface.history.emit_undo_available_changed(True)
    surface.history.emit_redo_available_changed(False)

    assert payload.cursor_state.source_position == 4
    assert payload.anchor_state.source_position == 1
    assert payload.document_view.source_text == "alpha"
    assert payload.layout_checkpoint is not None
    assert surface.history.clipboard_history_actions is not None
    assert undo_availability == [True]
    assert redo_availability == [False]
