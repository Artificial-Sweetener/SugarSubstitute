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

"""Tab and cube-stack characterization fixtures."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(autouse=True)
def _retain_qapplication() -> Iterator[QApplication]:
    """Retain the QApplication wrapper throughout each Qt-backed contract."""

    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    yield app


class _Signal:
    """Simple signal recorder."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def emit(self, *args: object) -> None:
        """Record emitted args."""
        self.calls.append(args)


class _TabItem:
    """Tab item test double."""

    def __init__(self, key: str) -> None:
        self._key = key
        self.deleted = False
        self.visible = True
        self.selected = False
        self._text = key
        self._y = 20
        self._height = 36

    def routeKey(self) -> str:
        """Return route key."""
        return self._key

    def setRouteKey(self, key: str) -> None:
        """Set route key."""
        self._key = key

    def deleteLater(self) -> None:
        """Mark as deleted."""
        self.deleted = True

    def setVisible(self, visible: bool) -> None:
        """Record visibility."""
        self.visible = visible

    def setSelected(self, selected: bool) -> None:
        """Record selected state."""
        self.selected = selected

    def setText(self, text: str) -> None:
        """Set label text."""
        self._text = text

    def y(self) -> int:
        """Return top Y."""
        return self._y

    def height(self) -> int:
        """Return item height."""
        return self._height


class _SlideAnimation:
    """Animation recorder used by CubeStack.setCurrentIndex."""

    def __init__(self) -> None:
        self.stopped = 0
        self.end_value: object | None = None
        self.duration: int | None = None
        self.curve: object | None = None
        self.started = 0

    def stop(self) -> None:
        """Record stop."""
        self.stopped += 1

    def setEndValue(self, value: object) -> None:
        """Record end value."""
        self.end_value = value

    def setDuration(self, duration: int) -> None:
        """Record duration."""
        self.duration = duration

    def setEasingCurve(self, curve: object) -> None:
        """Record curve."""
        self.curve = curve

    def start(self) -> None:
        """Record start."""
        self.started += 1


def _import_workflow_tabs_module() -> Any:
    """Import workflow tab bar module."""
    _clear_gui_stubs()
    return importlib.import_module(
        "substitute.presentation.workflows.workflow_tabs_view"
    )


def _import_stack_panel_module() -> Any:
    """Import cube stack module."""
    _clear_gui_stubs()
    return importlib.import_module("substitute.presentation.workflows.cube_stack_view")


def _clear_gui_stubs() -> None:
    """Drop lightweight GUI stubs so real modules can import cleanly."""
    qtcore = sys.modules.get("PySide6.QtCore")
    if qtcore is not None and not hasattr(qtcore, "Property"):
        for name in list(sys.modules):
            if name == "PySide6" or name.startswith("PySide6."):
                sys.modules.pop(name, None)
    qfw = sys.modules.get("qfluentwidgets")
    if qfw is not None and not hasattr(qfw, "MenuAnimationType"):
        for name in list(sys.modules):
            if name == "qfluentwidgets" or name.startswith("qfluentwidgets."):
                sys.modules.pop(name, None)
    qframe = sys.modules.get("qframelesswindow")
    if qframe is not None and not hasattr(qframe, "WindowEffect"):
        for name in list(sys.modules):
            if name == "qframelesswindow" or name.startswith("qframelesswindow."):
                sys.modules.pop(name, None)
    sys.modules.pop("substitute.presentation.workflows.workflow_tabs_view", None)
    sys.modules.pop("substitute.presentation.workflows.cube_stack_view", None)
    sys.modules.pop("substitute.presentation.workflows.reorderable_tabs_base", None)
    sys.modules.pop("sugarsubstitute_shared.presentation.fluent_tooltips", None)


def _attach_cube_stack_selection_methods(mod: Any, fake: Any) -> None:
    """Attach CubeStack helper methods used by unbound-method test doubles."""

    fake._select_index = lambda index, *, animate_indicator: (
        mod.CubeStack._select_index(
            fake,
            index,
            animate_indicator=animate_indicator,
        )
    )
    fake._sync_indicator_to_current = lambda *, animated: (
        mod.CubeStack._sync_indicator_to_current(fake, animated=animated)
    )
    fake._sync_indicator_overlay = lambda: None
