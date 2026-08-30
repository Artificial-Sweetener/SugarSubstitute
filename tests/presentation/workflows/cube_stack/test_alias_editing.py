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

"""Cube stack alias-editing contracts."""

from __future__ import annotations

import importlib

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from tests.presentation.workflows.qt_support import _ensure_qapp
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_cube_item_rename_uses_alias_editor_and_keeps_display_text() -> None:
    """Cube rename should use the cube alias editor without mutating display text."""
    app = _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    first = stack.addTab("a", "SDXL/Text to Image")
    stack.show()
    app.processEvents()

    first._startRename()
    wait_for_qt_condition(first.alias_editor.isVisible)

    assert first.alias_editor.isVisible()
    assert first.rename_editor.isHidden()
    assert first.text() == "SDXL/Text to Image"
    assert first.alias_editor.text() == "SDXL/Text to Image"
    assert first._visual_state().editing_primary_text is True

    stack.close()
    stack.deleteLater()


def test_cube_item_alias_editor_geometry_matches_primary_text_row() -> None:
    """Alias editor geometry should match the painted primary cube text row."""
    app = _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")
    item_mod = importlib.import_module("substitute.presentation.workflows.cube_item")

    stack = mod.CubeStack(None)
    first = stack.addTab("a", "SDXL/Text to Image")
    stack.show()
    app.processEvents()

    first.setCloseButtonDisplayMode(mod.CubeCloseButtonDisplayMode.ALWAYS)
    first._sync_close_button_visibility()
    assert not first.closeButton.isHidden()
    app.processEvents()

    first._startRename()
    app.processEvents()

    expected_primary_rect, _secondary_rect = item_mod.CubeCardVisual.text_row_rects(
        first._textRect()
    )
    assert first.closeButton.isHidden()
    assert first.alias_editor.geometry() == expected_primary_rect.toAlignedRect()

    stack.close()
    stack.deleteLater()


def test_cube_item_alias_editor_accept_emits_existing_stack_signal() -> None:
    """Committing the alias editor should use the existing cube rename signal flow."""
    app = _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    first = stack.addTab("a", "SDXL/Text to Image")
    rename_calls: list[tuple[str, str]] = []
    stack.cubeRenameRequested.connect(
        lambda old_key, new_name: rename_calls.append((old_key, new_name))
    )
    stack.show()
    app.processEvents()

    first._startRename()
    first.alias_editor.setText("Flux/Image to Image")
    QTest.keyClick(first.alias_editor, Qt.Key.Key_Return)

    assert rename_calls == [("a", "Flux/Image to Image")]
    assert first.alias_editor.isHidden()
    assert first.rename_editor.isHidden()

    stack.close()
    stack.deleteLater()


def test_cube_item_alias_editor_commits_when_card_background_is_clicked() -> None:
    """Clicking outside the primary text editor should commit the cube alias."""
    app = _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    first = stack.addTab("a", "SDXL/Text to Image")
    rename_calls: list[tuple[str, str]] = []
    stack.cubeRenameRequested.connect(
        lambda old_key, new_name: rename_calls.append((old_key, new_name))
    )
    stack.show()
    app.processEvents()

    first._startRename()
    first.alias_editor.setText("Flux/Image to Image")
    QTest.mouseClick(
        first,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(4, first.height() // 2),
    )
    app.processEvents()

    assert rename_calls == [("a", "Flux/Image to Image")]
    assert first.alias_editor.isHidden()
    assert first.alias_editor.isEditing() is False

    stack.close()
    stack.deleteLater()


def test_cube_item_alias_editor_escape_leaves_alias_unchanged() -> None:
    """Cancelling cube alias editing should leave the item and stack signal untouched."""
    app = _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    first = stack.addTab("a", "SDXL/Text to Image")
    rename_calls: list[tuple[str, str]] = []
    stack.cubeRenameRequested.connect(
        lambda old_key, new_name: rename_calls.append((old_key, new_name))
    )
    stack.show()
    app.processEvents()

    first._startRename()
    first.alias_editor.setText("Flux/Image to Image")
    QTest.keyClick(first.alias_editor, Qt.Key.Key_Escape)

    assert first.text() == "SDXL/Text to Image"
    assert first.alias_editor.text() == "SDXL/Text to Image"
    assert first.alias_editor.isHidden()
    assert rename_calls == []

    stack.close()
    stack.deleteLater()


def test_cube_stack_begin_alias_editing_requires_expanded_item() -> None:
    """Route-key editing should start only after compact mode is cleared."""
    app = _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    first = stack.addTab("a", "SDXL/Text to Image")
    stack.show()
    app.processEvents()

    stack.setCompact(True)
    app.processEvents()

    assert stack.begin_alias_editing("a") is False
    assert first.alias_editor.isHidden()

    stack.finishCompactTransition(False)
    app.processEvents()

    assert stack.begin_alias_editing("a") is True
    assert first.alias_editor.isVisible()

    stack.close()
    stack.deleteLater()


def test_cube_alias_editing_finished_emits_original_route_key() -> None:
    """Alias edit completion should preserve the route key captured at edit start."""
    app = _ensure_qapp()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    stack = mod.CubeStack(None)
    first = stack.addTab("a", "SDXL/Text to Image")
    finished: list[str] = []
    stack.aliasEditingFinished.connect(finished.append)
    stack.show()
    app.processEvents()

    assert stack.begin_alias_editing("a") is True
    first.setRouteKey("resolved-after-commit")
    first.alias_editor.cancel()
    app.processEvents()

    assert finished == ["a"]

    stack.close()
    stack.deleteLater()
