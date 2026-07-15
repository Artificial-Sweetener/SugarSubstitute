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

"""Cover shell progress overlay geometry outside MainWindow."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from substitute.presentation.shell.progress_overlay_controller import (
    ProgressOverlayController,
)


class _Point:
    """Minimal point object for menu-bar map results."""

    def __init__(self, x: int, y: int) -> None:
        """Store point coordinates."""

        self._x = x
        self._y = y

    def x(self) -> int:
        """Return the x coordinate."""

        return self._x

    def y(self) -> int:
        """Return the y coordinate."""

        return self._y


class _ProgressOverlay:
    """Progress overlay double that records geometry writes."""

    def __init__(self) -> None:
        """Initialize recorded geometry calls."""

        self.geometry_calls: list[tuple[int, int, int, int]] = []

    def height(self) -> int:
        """Return deterministic overlay height."""

        return 6

    def setGeometry(self, x: int, y: int, width: int, height: int) -> None:
        """Record geometry writes."""

        self.geometry_calls.append((x, y, width, height))


def test_position_progress_overlay_aligns_workflow_bar_to_menu_bar_bottom() -> None:
    """Progress overlay positioning should align the workflow bar with the menu edge."""

    class _MenuBar:
        """Menu-bar double with deterministic mapped top and bottom edges."""

        def __init__(self) -> None:
            """Initialize mapped point lookup."""

            self.points = {
                (0, 0): _Point(14, 22),
                (0, 40): _Point(14, 62),
            }

        def mapTo(self, _parent: object, point: Any) -> _Point:
            """Map local points into shell coordinates."""

            return self.points[(point.x(), point.y())]

        def height(self) -> int:
            """Return menu-bar height."""

            return 40

        def width(self) -> int:
            """Return menu-bar width."""

            return 520

    overlay = _ProgressOverlay()
    shell = SimpleNamespace(
        menu_bar=_MenuBar(),
        progressOverlay=overlay,
        workflowOverlayBar=SimpleNamespace(height=lambda: 3),
    )

    ProgressOverlayController(shell).position_progress_overlay()

    assert overlay.geometry_calls == [(14, 59, 520, 6)]


def test_position_progress_overlay_uses_layout_width_when_menu_width_is_stale() -> None:
    """Progress overlay should not keep a tiny pre-layout toolbar width."""

    class _MenuBar:
        """Menu-bar double that reports stale width but valid mapped y positions."""

        def mapTo(self, _parent: object, point: Any) -> _Point:
            """Map local points into shell coordinates."""

            return _Point(0, 40 if point.y() else 0)

        def height(self) -> int:
            """Return menu-bar height."""

            return 40

        def width(self) -> int:
            """Return stale menu-bar width."""

            return 160

    overlay = _ProgressOverlay()
    shell = SimpleNamespace(
        menu_bar=_MenuBar(),
        progressOverlay=overlay,
        workflowOverlayBar=SimpleNamespace(height=lambda: 3),
        centralWidget=lambda: SimpleNamespace(width=lambda: 900),
        width=lambda: 920,
    )

    ProgressOverlayController(shell).position_progress_overlay()

    assert overlay.geometry_calls == [(0, 37, 900, 6)]
