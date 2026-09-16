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

"""Verify floating reorder widgets follow their mounted editor lifetime."""

from typing import cast

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from shiboken6 import isValid

from substitute.presentation.editor.prompt_editor.overlays.reorder_overlay import (
    SegmentReorderOverlay,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)
from tests.support.qt.lifecycle import destroy_qt_object


def test_closed_overlay_can_receive_font_changes_and_reopen(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Keep the floating proxy usable while its hidden overlay remains alive."""
    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text="alpha, beta, gamma"
    )
    real_shell_scenario.input.set_source_cursor_position(field, 2)
    real_shell_scenario.input.focus_editor(field)
    QTest.keyPress(field.editor, Qt.Key.Key_Alt)
    real_shell_scenario.wait_for_queued_delivery()
    overlay = cast(SegmentReorderOverlay, getattr(field.editor, "_segment_overlay"))
    proxy = overlay.drag_proxy_widget()
    overlay.close()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert isValid(proxy)
    font = QFont(overlay.font())
    font.setPointSizeF(font.pointSizeF() + 1)
    overlay.setFont(font)
    overlay.show()
    assert overlay.isVisible()
    assert isValid(proxy)
    QTest.keyRelease(field.editor, Qt.Key.Key_Alt)


def test_destroyed_overlay_releases_proxy_from_surviving_visual_host(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Release the externally parented proxy when its logical owner is destroyed."""
    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text="alpha, beta"
    )
    real_shell_scenario.input.set_source_cursor_position(field, 2)
    real_shell_scenario.input.focus_editor(field)
    QTest.keyPress(field.editor, Qt.Key.Key_Alt)
    real_shell_scenario.wait_for_queued_delivery()
    overlay = cast(SegmentReorderOverlay, getattr(field.editor, "_segment_overlay"))
    proxy = overlay.drag_proxy_widget()
    host = proxy.parentWidget()
    destroy_qt_object(overlay)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert isValid(host)
    assert not isValid(proxy)
