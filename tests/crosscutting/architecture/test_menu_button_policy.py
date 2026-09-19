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

"""Verify static ownership of presentation menu-button lifecycles."""

from __future__ import annotations

from pathlib import Path

from tools.architecture_governance.menu_button_policy import (
    MenuButtonViolation,
    discover_menu_button_violations,
)


def _scan(tmp_path: Path, source: str) -> tuple[MenuButtonViolation, ...]:
    """Scan one authored presentation module through the production checker."""

    path = tmp_path / "substitute/presentation/example.py"
    path.parent.mkdir(parents=True)
    path.write_text(source, encoding="utf-8")
    return discover_menu_button_violations(tmp_path, (path,))


def test_raw_qfluent_menu_button_import_is_rejected(tmp_path: Path) -> None:
    """New menu controls must enter through the toggle-aware adapters."""

    violations = _scan(
        tmp_path,
        "from qfluentwidgets import DropDownPushButton\n",
    )

    assert [(item.rule, item.line) for item in violations] == [("MENU001", 1)]


def test_qualified_qfluent_menu_button_construction_is_rejected(
    tmp_path: Path,
) -> None:
    """Qualified imports must not provide a route around shared adapters."""

    violations = _scan(
        tmp_path,
        "import qfluentwidgets as qfw\nbutton = qfw.DropDownPushButton()\n",
    )

    assert [(item.rule, item.line) for item in violations] == [("MENU001", 2)]


def test_raw_menu_attachment_is_rejected(tmp_path: Path) -> None:
    """Callers must not bypass shared lifecycle tracking during attachment."""

    violations = _scan(
        tmp_path,
        "def attach(button, menu):\n    button.setMenu(menu)\n",
    )

    assert [(item.rule, item.line) for item in violations] == [("MENU002", 2)]


def test_direct_button_menu_open_path_is_rejected(tmp_path: Path) -> None:
    """A clicked handler must not directly render and execute a Fluent menu."""

    violations = _scan(
        tmp_path,
        """
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer

class Surface:
    def bind(self):
        self.button.clicked.connect(self._open_actions)

    def _open_actions(self):
        menu = QFluentMenuRenderer(parent=self.button).render(self.model)
        menu.exec(self.position)
""",
    )

    assert [(item.rule, item.line) for item in violations] == [("MENU003", 6)]


def test_direct_menu_exec_signal_connection_is_rejected(tmp_path: Path) -> None:
    """Directly connecting a menu executor must not evade handler analysis."""

    violations = _scan(
        tmp_path,
        "def bind(button, menu):\n    button.clicked.connect(menu.exec)\n",
    )

    assert [(item.rule, item.line) for item in violations] == [("MENU003", 2)]


def test_transitive_button_menu_open_path_is_rejected(tmp_path: Path) -> None:
    """Moving popup execution behind a local helper must not evade ownership."""

    violations = _scan(
        tmp_path,
        """
from qfluentwidgets import RoundMenu

class Surface:
    def __init__(self):
        self.menu = RoundMenu()
        self.button.clicked.connect(self._request_actions)

    def _request_actions(self):
        self._show_actions()

    def _show_actions(self):
        self.menu.exec(self.position)
""",
    )

    assert [(item.rule, item.line) for item in violations] == [("MENU003", 7)]


def test_context_menu_execution_is_not_a_button_violation(tmp_path: Path) -> None:
    """Right-click context menus remain independent of button toggle semantics."""

    violations = _scan(
        tmp_path,
        """
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer

class Surface:
    def contextMenuEvent(self, event):
        menu = QFluentMenuRenderer(parent=self).render(self.model)
        menu.exec(event.globalPos())
""",
    )

    assert violations == ()


def test_shared_controller_binding_is_allowed(tmp_path: Path) -> None:
    """The approved controller is the sole ordinary-button menu entrypoint."""

    violations = _scan(
        tmp_path,
        """
from substitute.presentation.widgets.menu_button_controller import MenuButtonController

class Surface:
    def __init__(self):
        self.controller = MenuButtonController(
            self.button,
            menu_position=self.position,
        )
        self.controller.set_menu_factory(self._build_menu)
""",
    )

    assert violations == ()
