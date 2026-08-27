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

"""Verify title-row activation across linked and independent modes."""

from __future__ import annotations

from PySide6.QtCore import Qt

from tests.presentation.editor.node_card.mode_controller.support import (
    InteractiveTitleRow,
    RecordingAccordionController,
    create_title_harness,
    independent_decision,
    linked_decision,
)
from tests.presentation.editor.node_card.support import (
    release_title_row,
    row_activation_enabled,
)


def test_independent_mode_restores_accordion_title_activation() -> None:
    """Suppress linked feedback and restore accordion precedence afterward."""

    accordion_controller = RecordingAccordionController()
    harness = create_title_harness(
        collapsible=True,
        has_rows=True,
        accordion_controller=accordion_controller,
    )
    assert isinstance(harness.title_row, InteractiveTitleRow)
    assert harness.enabled_switch is not None
    harness.wrapper.show()
    try:
        harness.apply(linked_decision())
        assert row_activation_enabled(harness.title_row) is False
        assert harness.title_row.cursor().shape() == Qt.CursorShape.ArrowCursor

        harness.apply(independent_decision(enabled=False))
        assert row_activation_enabled(harness.title_row) is True
        assert harness.title_row.cursor().shape() == Qt.CursorShape.PointingHandCursor

        release_title_row(harness.title_row)
        assert accordion_controller.toggle_calls == 1
        assert harness.enabled_switch.isChecked() is False
    finally:
        harness.destroy()


def test_independent_mode_restores_switch_only_title_activation() -> None:
    """Make an independent switch-only title row clickable after linked mode."""

    harness = create_title_harness(collapsible=False, has_rows=False)
    assert isinstance(harness.title_row, InteractiveTitleRow)
    assert harness.enabled_switch is not None
    harness.wrapper.show()
    try:
        harness.apply(linked_decision())
        assert row_activation_enabled(harness.title_row) is False

        harness.apply(independent_decision(enabled=False))
        assert row_activation_enabled(harness.title_row) is True
        release_title_row(harness.title_row)
        assert harness.enabled_switch.isChecked() is True
    finally:
        harness.destroy()
