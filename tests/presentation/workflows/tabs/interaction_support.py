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

"""Build workflow-tab pointer and menu interaction probes."""

from __future__ import annotations

import importlib
from typing import Any, cast

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from substitute.presentation.widgets.menu_model import (
    MenuItem,
    MenuModel,
    MenuSeparator,
)
from tests.presentation.workflows.qt_support import (
    _clear_gui_stubs,
    _ensure_qapp,
)


def _workflow_tabs_module() -> Any:
    """Import the real workflow tab module for interaction tests."""

    _clear_gui_stubs()
    return importlib.import_module(
        "substitute.presentation.workflows.workflow_tabs_view"
    )


def _tabbar() -> Any:
    """Build a visible movable workflow tab bar with three tabs."""

    app = _ensure_qapp()
    mod = _workflow_tabs_module()
    tabbar = mod.TabBar(None)
    tabbar.resize(520, 44)
    tabbar.addTab("wf-a", "A")
    tabbar.addTab("wf-b", "B")
    tabbar.addTab("wf-c", "C")
    tabbar.setMovable(True)
    tabbar.show()
    app.processEvents()
    return tabbar


def _mouse_event(
    event_type: QEvent.Type,
    pos: QPoint,
    *,
    button: Qt.MouseButton,
    buttons: Qt.MouseButton,
) -> QMouseEvent:
    """Create a mouse event at one tab-bar-local position."""

    return QMouseEvent(
        event_type,
        QPointF(pos),
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )


def _tab_center(tabbar: Any, index: int) -> QPoint:
    """Return the center point for a workflow tab slot."""

    rect = tabbar.tabRect(index)
    assert rect is not None
    return cast(QPoint, rect.center())


def _empty_tab_bar_pos(tabbar: Any) -> QPoint:
    """Return a stable point in empty workflow tab-row space."""

    return QPoint(max(0, tabbar.width() - 8), tabbar.height() // 2)


def _install_context_menu_probe(monkeypatch: pytest.MonkeyPatch) -> "_MenuProbe":
    """Patch workflow tab menus with a non-rendering capture probe."""

    probe = _MenuProbe()
    mod = _workflow_tabs_module()
    monkeypatch.setattr(
        mod,
        "QFluentMenuRenderer",
        lambda *args, **kwargs: _MenuProbeRenderer(probe),
    )
    return probe


class _MenuProbe:
    """Capture workflow-tab context menu actions without showing a popup."""

    def __init__(self) -> None:
        """Initialize empty captured menu state."""

        self.labels: list[str] = []
        self.actions: list[Any] = []
        self.exec_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def addAction(self, action: Any) -> None:
        """Record one menu action."""

        self.actions.append(action)
        self.labels.append(str(action.text()))

    def addSeparator(self) -> None:
        """Record a separator in action order."""

        self.labels.append("---")

    def exec(self, *args: object, **kwargs: object) -> None:
        """Record menu execution without rendering."""

        self.exec_calls.append((args, kwargs))

    def action(self, text: str) -> Any:
        """Return the captured action matching text."""

        for action in self.actions:
            if action.text() == text:
                return action
        raise AssertionError(f"Missing action: {text}")


class _ProbeAction:
    """Record one rendered menu item for workflow tab interaction tests."""

    def __init__(self, item: MenuItem) -> None:
        """Store item state for assertions and callback dispatch."""

        self._item = item

    def text(self) -> str:
        """Return the action label."""

        return self._item.label

    def isEnabled(self) -> bool:  # noqa: N802
        """Return whether the rendered action is enabled."""

        return self._item.enabled

    def trigger(self) -> None:
        """Dispatch the rendered item callback when enabled."""

        if self._item.enabled and self._item.callback is not None:
            self._item.callback()


class _MenuProbeRenderer:
    """Render shared menu models into a workflow tab menu probe."""

    def __init__(self, probe: _MenuProbe) -> None:
        """Store the probe that receives rendered rows."""

        self._probe = probe

    def render(self, model: MenuModel) -> _MenuProbe:
        """Populate and return the probe menu."""

        for entry in model.entries:
            if isinstance(entry, MenuItem):
                self._probe.addAction(_ProbeAction(entry))
            elif isinstance(entry, MenuSeparator):
                self._probe.addSeparator()
        return self._probe
