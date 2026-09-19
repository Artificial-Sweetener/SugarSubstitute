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

"""Cover bootstrap application and splash identity."""

from __future__ import annotations

import importlib
import types
from typing import Any, cast

import pytest

from substitute.app.bootstrap import composition
from substitute.app.bootstrap import crash_aware_application


def test_create_application_sets_shared_app_icon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """QApplication should receive the shared app identity icon at creation."""

    icon = object()
    construction_order: list[str] = []

    class _FakeApplication:
        def __init__(self, argv: list[str]) -> None:
            """Store QApplication construction arguments."""

            construction_order.append("qapplication")
            self.argv = argv
            self.window_icon: object | None = None
            self.quit_on_last_window_closed: bool | None = None

        def setWindowIcon(self, assigned_icon: object) -> None:
            """Record the assigned process window icon."""

            self.window_icon = assigned_icon

        def setQuitOnLastWindowClosed(self, value: bool) -> None:
            """Record the configured Qt quit policy."""

            self.quit_on_last_window_closed = value

    monkeypatch.setattr(composition, "application_icon", lambda: icon)
    monkeypatch.setattr(
        composition,
        "configure_windows_app_user_model_id",
        lambda: construction_order.append("app_user_model_id"),
    )
    monkeypatch.setattr(
        crash_aware_application,
        "CrashAwareApplication",
        _FakeApplication,
    )

    app = cast(Any, composition.create_application(("main.py",)))

    assert construction_order == ["app_user_model_id", "qapplication"]
    assert app.argv == ["main.py"]
    assert app.window_icon is icon
    assert app.quit_on_last_window_closed is True


def test_configure_windows_app_user_model_id_calls_windows_shell_api() -> None:
    """Windows startup identity should use the configured AppUserModelID."""

    calls: list[str] = []

    class _FakeShell32:
        def SetCurrentProcessExplicitAppUserModelID(self, app_id: str) -> int:
            """Record the requested AppUserModelID."""

            calls.append(app_id)
            return 0

    composition.configure_windows_app_user_model_id(
        platform="win32",
        shell32=_FakeShell32(),
    )

    assert calls == [composition.WINDOWS_APP_USER_MODEL_ID]


def test_configure_windows_app_user_model_id_noops_off_windows() -> None:
    """Non-Windows platforms should never touch the Windows shell API."""

    calls: list[str] = []

    class _FakeShell32:
        def SetCurrentProcessExplicitAppUserModelID(self, app_id: str) -> int:
            """Record unexpected shell API calls."""

            calls.append(app_id)
            return 0

    composition.configure_windows_app_user_model_id(
        platform="linux",
        shell32=_FakeShell32(),
    )

    assert calls == []


def test_configure_windows_app_user_model_id_can_be_disabled_for_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The shell identity call should be suppressible in test worker processes."""

    shell_lookups: list[str] = []
    monkeypatch.setenv(composition.DISABLE_WINDOWS_APP_USER_MODEL_ID_ENV, "1")
    monkeypatch.setattr(
        composition,
        "_windows_shell32",
        lambda: shell_lookups.append("called"),
    )

    composition.configure_windows_app_user_model_id(platform="win32")

    assert shell_lookups == []


def test_create_splash_window_uses_shared_app_icon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Splash creation should pass the shared app icon into the splash window."""

    icon = object()

    class _FakeSplashWindow:
        def __init__(self, *, icon: object) -> None:
            """Record the splash icon argument."""

            self.icon = icon
            self.centered = False
            self.shown = False

        def center_on_screen(self) -> None:
            """Record splash centering."""

            self.centered = True

        def show(self) -> None:
            """Record splash reveal."""

            self.shown = True

    fake_module = types.SimpleNamespace(SplashWindow=_FakeSplashWindow)
    monkeypatch.setattr(composition, "application_icon", lambda: icon)
    monkeypatch.setattr(importlib, "import_module", lambda _name: fake_module)

    splash = composition.create_splash_window()

    assert isinstance(splash, _FakeSplashWindow)
    assert splash.icon is icon
    assert splash.centered is True
    assert splash.shown is True
