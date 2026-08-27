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

"""Cover bootstrap shell reveal and restored display state."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast

import pytest

from substitute.app.bootstrap import composition
from substitute.application.workspace_state import InitialShellPlacement
from substitute.domain.workspace_snapshot import WindowGeometrySnapshot


def test_show_built_main_window_reapplies_shell_geometry_at_reveal() -> None:
    """Prebuilt shell reveal should not inherit splash-sized hidden geometry."""

    calls: list[tuple[str, int, int] | tuple[str, int, int, int, int] | tuple[str]] = []

    class _FakeScreen:
        def availableGeometry(self) -> object:
            return SimpleNamespace(
                width=lambda: 1920,
                height=lambda: 1080,
                left=lambda: 0,
                top=lambda: 0,
            )

    class _FakeFrame:
        def screen(self) -> _FakeScreen:
            return _FakeScreen()

        def resize(self, width: int, height: int) -> None:
            calls.append(("resize", width, height))

        def move(self, left: int, top: int) -> None:
            calls.append(("move", left, top))

        def show(self) -> None:
            calls.append(("show",))

        def raise_(self) -> None:
            calls.append(("raise",))

        def activateWindow(self) -> None:
            calls.append(("activate",))

    composition.show_built_main_window(cast(Any, _FakeFrame()))

    assert calls[:5] == [
        ("resize", 1632, 918),
        ("move", 144, 81),
        ("show",),
        ("resize", 1632, 918),
        ("move", 144, 81),
    ]
    assert ("raise",) in calls
    assert ("activate",) in calls


def test_show_built_main_window_can_preserve_restored_geometry() -> None:
    """GUI reload reveal should not overwrite geometry restored during hydration."""

    calls: list[tuple[str, int, int] | tuple[str, int, int, int, int] | tuple[str]] = []

    class _FakeScreen:
        def availableGeometry(self) -> object:
            return SimpleNamespace(
                width=lambda: 1920,
                height=lambda: 1080,
                left=lambda: 0,
                top=lambda: 0,
            )

    class _FakeFrame:
        def screen(self) -> _FakeScreen:
            return _FakeScreen()

        def resize(self, width: int, height: int) -> None:
            calls.append(("resize", width, height))

        def move(self, left: int, top: int) -> None:
            calls.append(("move", left, top))

        def show(self) -> None:
            calls.append(("show",))

        def raise_(self) -> None:
            calls.append(("raise",))

        def activateWindow(self) -> None:
            calls.append(("activate",))

    composition.show_built_main_window(
        cast(Any, _FakeFrame()),
        apply_default_geometry=False,
    )

    assert calls == [("show",), ("raise",), ("activate",)]


def test_show_built_main_window_applies_initial_shell_placement_pre_show(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Restored placement should be the first visible shell state."""

    calls: list[tuple[str, int, int, int, int] | tuple[str]] = []
    scheduled: list[tuple[object, ...]] = []

    class _FakeFrame:
        def setGeometry(self, x: int, y: int, width: int, height: int) -> None:
            calls.append(("geometry", x, y, width, height))

        def show(self) -> None:
            calls.append(("show",))

        def showFullScreen(self) -> None:
            calls.append(("fullscreen",))

        def showMaximized(self) -> None:
            calls.append(("maximized",))

        def raise_(self) -> None:
            calls.append(("raise",))

        def activateWindow(self) -> None:
            calls.append(("activate",))

    monkeypatch.setattr(
        composition,
        "_apply_main_window_geometry",
        lambda _frame: calls.append(("fallback",)),
    )
    qt_timer = getattr(composition, "QTimer")
    monkeypatch.setattr(qt_timer, "singleShot", lambda *_args: scheduled.append(_args))

    composition.show_built_main_window(
        cast(Any, _FakeFrame()),
        initial_shell_placement=InitialShellPlacement(
            geometry=WindowGeometrySnapshot(x=11, y=22, width=1234, height=700),
            window_display_state="normal",
            maximized=False,
        ),
    )

    assert calls == [
        ("geometry", 11, 22, 1234, 700),
        ("show",),
        ("raise",),
        ("activate",),
    ]
    assert len(scheduled) == 2
    callback = cast(Callable[[], None], scheduled[0][1])
    callback()
    assert calls == [
        ("geometry", 11, 22, 1234, 700),
        ("show",),
        ("raise",),
        ("activate",),
        ("raise",),
        ("activate",),
    ]


def test_show_built_main_window_restores_maximized_display_state() -> None:
    """Saved maximized state should use the corresponding first show call."""

    calls: list[tuple[str, int, int, int, int] | tuple[str]] = []

    class _FakeFrame:
        def setGeometry(self, x: int, y: int, width: int, height: int) -> None:
            calls.append(("geometry", x, y, width, height))

        def show(self) -> None:
            calls.append(("show",))

        def showFullScreen(self) -> None:
            calls.append(("fullscreen",))

        def showMaximized(self) -> None:
            calls.append(("maximized",))

        def raise_(self) -> None:
            calls.append(("raise",))

        def activateWindow(self) -> None:
            calls.append(("activate",))

    composition.show_built_main_window(
        cast(Any, _FakeFrame()),
        initial_shell_placement=InitialShellPlacement(
            geometry=WindowGeometrySnapshot(x=10, y=20, width=1000, height=600),
            window_display_state="normal",
            maximized=True,
        ),
    )

    assert calls == [
        ("geometry", 10, 20, 1000, 600),
        ("maximized",),
        ("raise",),
        ("activate",),
    ]


def test_show_built_main_window_restores_fullscreen_display_state() -> None:
    """Saved fullscreen state should use the corresponding first show call."""

    calls: list[tuple[str]] = []

    class _FakeFrame:
        def setGeometry(self, _x: int, _y: int, _width: int, _height: int) -> None:
            """Accept optional restored geometry."""

        def show(self) -> None:
            calls.append(("show",))

        def showFullScreen(self) -> None:
            calls.append(("fullscreen",))

        def showMaximized(self) -> None:
            calls.append(("maximized",))

        def raise_(self) -> None:
            calls.append(("raise",))

        def activateWindow(self) -> None:
            calls.append(("activate",))

    composition.show_built_main_window(
        cast(Any, _FakeFrame()),
        initial_shell_placement=InitialShellPlacement(
            geometry=None,
            window_display_state="fullscreen",
            maximized=False,
        ),
    )

    assert calls == [("fullscreen",), ("raise",), ("activate",)]
