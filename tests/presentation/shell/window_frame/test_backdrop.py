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

"""Test shell backdrop selection and native chrome adaptation."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication
import pytest

from substitute.presentation.shell.window_frame import (
    ShellBackdropMode,
    SubstituteWindowFrame,
)
import substitute.presentation.shell.window_frame as window_frame
from tests.support.qt.lifecycle import ensure_qt_application


@pytest.fixture(scope="module", autouse=True)
def backdrop_qt_application() -> Iterator[QApplication]:
    """Keep one worker-local Qt application alive for backdrop tests."""

    application = ensure_qt_application()
    yield application


def _app() -> QApplication:
    """Return the shared QApplication used by frameless-window contract tests."""

    return ensure_qt_application()


def test_shell_frame_backdrop_modes_route_to_expected_native_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backdrop mode selection should map materials and respect dark/light state."""

    effect_calls: list[tuple[str, dict[str, object]]] = []

    def record_mica(_handle: object, **kwargs: object) -> None:
        """Record one fake Mica call."""

        effect_calls.append(("mica", kwargs))

    acrylic_fix_calls: list[object] = []

    def record_acrylic_fix(window: object) -> None:
        """Record acrylic helper routing without invoking Win32 APIs."""

        acrylic_fix_calls.append(window)

    fake_frame = SimpleNamespace(
        _backdrop_mode=ShellBackdropMode.MICA,
        windowEffect=SimpleNamespace(
            setMicaEffect=record_mica,
            setAcrylicEffect=lambda *_args: None,
        ),
        winId=lambda: 123,
        _is_dark_backdrop_enabled=lambda: False,
    )
    monkeypatch.setattr(window_frame, "apply_acrylic_effect", record_acrylic_fix)
    SubstituteWindowFrame._apply_backdrop(cast(Any, fake_frame))
    fake_frame._backdrop_mode = ShellBackdropMode.MICA_ALT
    SubstituteWindowFrame._apply_backdrop(cast(Any, fake_frame))
    fake_frame._backdrop_mode = ShellBackdropMode.ACRYLIC
    SubstituteWindowFrame._apply_backdrop(cast(Any, fake_frame))

    assert effect_calls == [
        ("mica", {"isDarkMode": False, "isAlt": False}),
        ("mica", {"isDarkMode": False, "isAlt": True}),
    ]
    assert acrylic_fix_calls == [fake_frame]


def test_apply_acrylic_effect_applies_native_effect_then_normalizes_chrome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acrylic helper should run the toolkit effect before normalizing chrome."""

    calls: list[tuple[str, object]] = []
    fake_window = SimpleNamespace(
        windowEffect=SimpleNamespace(
            setAcrylicEffect=lambda handle, color: calls.append(
                ("effect", (handle, color))
            )
        ),
        winId=lambda: 123,
    )
    monkeypatch.setattr(
        window_frame,
        "normalize_acrylic_frameless_chrome",
        lambda window: calls.append(("normalize", window)),
    )

    window_frame.apply_acrylic_effect(fake_window)

    assert calls == [
        ("effect", (123, window_frame.ACRYLIC_BLEND_COLOR)),
        ("normalize", fake_window),
    ]


@pytest.mark.parametrize(
    ("dark_theme", "expected_color"),
    [(True, "#202020"), (False, "#f8f8f8")],
)
def test_non_material_shell_paints_an_opaque_theme_surface(
    monkeypatch: pytest.MonkeyPatch,
    dark_theme: bool,
    expected_color: str,
) -> None:
    """Avoid compositor-gray shells when native materials are unavailable."""

    _app()
    monkeypatch.setattr(window_frame, "isDarkTheme", lambda: dark_theme)
    frame = SubstituteWindowFrame(backdrop_mode=None)

    assert frame.autoFillBackground() is True
    assert (
        frame.palette().color(QPalette.ColorRole.Window).name().lower()
        == expected_color
    )

    frame.deleteLater()


def test_normalize_acrylic_frameless_chrome_restores_frameless_resize_bits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acrylic normalization should restore frameless resize bits and refresh."""

    style_before = 0x00C00000 | 0x00080000
    style_updates: list[tuple[int, int, int]] = []
    frame_updates: list[tuple[int, object, int, int, int, int, int]] = []
    flag_updates: list[tuple[object, bool]] = []
    corner_updates: list[int] = []

    fake_win32con = SimpleNamespace(
        GWL_STYLE=-16,
        WS_CAPTION=0x00C00000,
        WS_THICKFRAME=0x00040000,
        WS_MINIMIZEBOX=0x00020000,
        WS_MAXIMIZEBOX=0x00010000,
        SWP_NOMOVE=0x0002,
        SWP_NOSIZE=0x0001,
        SWP_NOZORDER=0x0004,
        SWP_FRAMECHANGED=0x0020,
    )
    fake_win32gui = SimpleNamespace(
        GetWindowLong=lambda hwnd, index: (
            style_before if (hwnd, index) == (123, -16) else 0
        ),
        SetWindowLong=lambda hwnd, index, style: style_updates.append(
            (hwnd, index, style)
        ),
        SetWindowPos=lambda hwnd, insert_after, x, y, cx, cy, flags: (
            frame_updates.append((hwnd, insert_after, x, y, cx, cy, flags))
        ),
    )

    monkeypatch.setattr(window_frame, "_PLATFORM", "win32")
    monkeypatch.setattr(window_frame, "win32con", fake_win32con)
    monkeypatch.setattr(window_frame, "win32gui", fake_win32gui)
    monkeypatch.setattr(
        window_frame,
        "restore_rounded_window_corners",
        lambda window_id: corner_updates.append(int(window_id)),
    )

    fake_window = SimpleNamespace(
        setWindowFlag=lambda flag, enabled: flag_updates.append((flag, enabled)),
        winId=lambda: 123,
    )

    window_frame.normalize_acrylic_frameless_chrome(fake_window)

    assert flag_updates == [(Qt.WindowType.FramelessWindowHint, True)]
    assert style_updates == [
        (
            123,
            -16,
            (
                style_before
                | fake_win32con.WS_THICKFRAME
                | fake_win32con.WS_MINIMIZEBOX
                | fake_win32con.WS_MAXIMIZEBOX
            )
            & ~fake_win32con.WS_CAPTION,
        )
    ]
    assert frame_updates == [
        (
            123,
            None,
            0,
            0,
            0,
            0,
            fake_win32con.SWP_NOMOVE
            | fake_win32con.SWP_NOSIZE
            | fake_win32con.SWP_NOZORDER
            | fake_win32con.SWP_FRAMECHANGED,
        )
    ]
    assert corner_updates == [123]


def test_normalize_acrylic_frameless_chrome_noops_off_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acrylic normalization should be inert outside Windows."""

    calls: list[str] = []
    fake_win32gui = SimpleNamespace(
        GetWindowLong=lambda *_args: calls.append("get"),
        SetWindowLong=lambda *_args: calls.append("set"),
        SetWindowPos=lambda *_args: calls.append("pos"),
    )

    monkeypatch.setattr(window_frame, "_PLATFORM", "linux")
    monkeypatch.setattr(window_frame, "win32gui", fake_win32gui)

    fake_window = SimpleNamespace(
        setWindowFlag=lambda *_args: calls.append("flag"),
        winId=lambda: 123,
    )

    window_frame.normalize_acrylic_frameless_chrome(fake_window)

    assert calls == []


def test_restore_rounded_window_corners_requests_windows_11_rounding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rounded-corner helper should request the standard Win11 round preference."""

    calls: list[tuple[int, int, int, int]] = []

    fake_dwmapi = SimpleNamespace(
        DwmSetWindowAttribute=lambda hwnd, attribute, value, size: calls.append(
            (hwnd, attribute, cast(int, value._obj.value), size)
        )
    )

    monkeypatch.setattr(window_frame, "_PLATFORM", "win32")
    monkeypatch.setattr(window_frame, "_DWMAPI", fake_dwmapi)
    monkeypatch.setattr(window_frame, "_WINDOWS_BUILD", 26200)
    monkeypatch.setattr(window_frame, "_WINDOW_CORNER_ATTRIBUTE", 33)
    monkeypatch.setattr(window_frame, "_WINDOW_CORNER_ROUND", 2)

    window_frame.restore_rounded_window_corners(123)

    assert calls == [(123, 33, 2, 4)]
