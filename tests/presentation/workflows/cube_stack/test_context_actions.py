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

"""Cube stack context and close-action contracts."""

from __future__ import annotations

import importlib

import pytest
from PySide6.QtCore import QPoint
from substitute.presentation.widgets.menu_model import MenuItem, MenuModel
from tests.presentation.workflows.qt_support import (
    _clear_gui_stubs,
    _ensure_qapp,
)


def test_cube_item_context_menu_exposes_duplicate_and_remove_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cube context menu should expose persistence, duplicate, and removal actions."""
    _ensure_qapp()
    _clear_gui_stubs()
    item_mod = importlib.import_module("substitute.presentation.workflows.cube_item")

    class FakeAction:
        """Capture one rendered cube item context-menu action."""

        def __init__(self, item: MenuItem) -> None:
            """Store item state for assertions and trigger dispatch."""

            self._item = item

        def text(self) -> str:
            """Return the rendered action label."""

            return self._item.label

        def trigger(self) -> None:
            """Invoke the rendered action callback."""

            if self._item.callback is not None:
                self._item.callback()

    class FakeRoundMenu:
        """Capture actions added to a cube item context menu."""

        instances: list["FakeRoundMenu"] = []

        def __init__(self, *, parent: object) -> None:
            self.parent = parent
            self.actions: list[FakeAction] = []
            self.exec_calls: list[object] = []
            FakeRoundMenu.instances.append(self)

        def addAction(self, action: FakeAction) -> None:
            """Record one menu action."""

            self.actions.append(action)

        def exec(self, global_pos: object, **kwargs: object) -> None:
            """Record menu execution without showing a popup."""

            self.exec_calls.append((global_pos, kwargs))

    class FakeRenderer:
        """Render shared menu models into fake cube context menus."""

        def __init__(self, *, parent: object) -> None:
            """Store the menu parent for fake menu construction."""

            self._parent = parent

        def render(self, model: MenuModel) -> FakeRoundMenu:
            """Return a fake menu populated from shared menu items."""

            menu = FakeRoundMenu(parent=self._parent)
            for entry in model.entries:
                if isinstance(entry, MenuItem):
                    menu.addAction(FakeAction(entry))
            return menu

    monkeypatch.setattr(item_mod, "QFluentMenuRenderer", FakeRenderer)

    item = item_mod.CubeItem("A", None, None)
    closed_calls: list[bool] = []
    duplicate_calls: list[bool] = []
    persistence_calls: list[bool] = []
    item.closed.connect(lambda: closed_calls.append(True))
    item.duplicateRequested.connect(lambda _item: duplicate_calls.append(True))
    item.outputPersistenceToggleRequested.connect(
        lambda _item: persistence_calls.append(True)
    )

    item._showContextMenu(QPoint(0, 0))

    menu = FakeRoundMenu.instances[0]
    assert [action.text() for action in menu.actions] == [
        "Don't save outputs",
        "Rename",
        "Duplicate",
        "Bypass",
        "Remove",
    ]

    menu.actions[0].trigger()
    menu.actions[2].trigger()
    menu.actions[4].trigger()

    assert persistence_calls == [True]
    assert duplicate_calls == [True]
    assert closed_calls == [True]

    item.close()
    item.deleteLater()


def test_cube_item_close_button_uses_square_hover_target() -> None:
    """Cube X button hover chrome should be a tight square around the icon."""
    _ensure_qapp()
    _clear_gui_stubs()
    mod = importlib.import_module("substitute.presentation.workflows.cube_stack_view")

    item = mod.CubeItem("A", None, None)

    assert item.closeButton.width() == mod.CUBE_ITEM_CLOSE_BUTTON_SIZE
    assert item.closeButton.height() == mod.CUBE_ITEM_CLOSE_BUTTON_SIZE

    item.close()
    item.deleteLater()
