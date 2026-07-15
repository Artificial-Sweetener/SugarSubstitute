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

"""Tests for shell-frame reload behavior when window material changes."""

from __future__ import annotations

from typing import cast

import pytest

from substitute.app.bootstrap import composition
from substitute.presentation.shell.window_frame import ShellBackdropMode


def test_reload_shell_frame_reuses_existing_main_window_and_geometry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backdrop reload should rebuild only the outer shell frame."""

    main_window = _FakeMainWindow()
    old_frame = _FakeExistingFrame()
    attached: list[tuple[object, object]] = []
    stored: list[tuple[object, object]] = []

    monkeypatch.setattr(composition, "main_window_widget", lambda frame: main_window)
    monkeypatch.setattr(
        composition,
        "_resolved_shell_backdrop_mode",
        lambda _runtime: ShellBackdropMode.ACRYLIC,
    )
    monkeypatch.setattr(
        composition,
        "_attach_main_window_to_shell",
        lambda frame, widget: attached.append((frame, widget)),
    )
    monkeypatch.setattr(
        composition,
        "_set_main_window_widget",
        lambda frame, widget: stored.append((frame, widget)),
    )
    monkeypatch.setattr(
        "substitute.presentation.shell.taskbar_progress.create_taskbar_progress_presenter",
        lambda frame: f"presenter:{id(frame)}",
    )
    monkeypatch.setitem(
        cast(dict[str, object], composition.__dict__),
        "CustomWindow",
        _FakeNewFrame,
    )

    new_frame = composition.reload_shell_frame(
        cast(composition.CustomWindow, old_frame)
    )

    assert isinstance(new_frame, _FakeNewFrame)
    assert new_frame.appearance_runtime is old_frame._appearance_runtime
    assert new_frame.backdrop_mode is ShellBackdropMode.ACRYLIC
    assert new_frame.title == "Sugar Substitute"
    assert new_frame.icon == "icon"
    assert new_frame.geometry == "geometry"
    assert new_frame.shown is True
    assert old_frame.hidden is True
    assert old_frame.closed is True
    assert old_frame.deleted is True
    assert old_frame.quit_suppressed is True
    assert old_frame.direct_close_allowed is True
    assert new_frame.close_callbacks == [new_frame.close]
    assert attached == [(new_frame, main_window)]
    assert stored == [(new_frame, main_window)]
    assert main_window.presenters == [f"presenter:{id(new_frame)}"]


def test_reload_shell_frame_returns_existing_frame_when_main_window_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reload should no-op when the current shell has no attached MainWindow."""

    old_frame = _FakeExistingFrame()
    monkeypatch.setattr(composition, "main_window_widget", lambda frame: None)

    assert (
        composition.reload_shell_frame(cast(composition.CustomWindow, old_frame))
        is old_frame
    )


class _FakeMainWindow:
    """Store taskbar presenter updates for shell reload tests."""

    def __init__(self) -> None:
        """Initialize presenter history."""

        self.presenters: list[object] = []
        self.shell_frame_integration_controller = _FakeFrameIntegrationController(
            self.presenters
        )


class _FakeFrameIntegrationController:
    """Store taskbar presenter updates routed through frame integration."""

    def __init__(self, presenters: list[object]) -> None:
        """Store the presenter history sink."""

        self._presenters = presenters

    def set_taskbar_progress_presenter(self, presenter: object) -> None:
        """Record one presenter assigned by the reloaded shell."""

        self._presenters.append(presenter)


class _FakeExistingFrame:
    """Mimic the shell frame API used by the reload helper."""

    def __init__(self) -> None:
        """Initialize geometry and lifecycle state."""

        self._appearance_runtime = object()
        self._shutdown_request = object()
        self.hidden = False
        self.closed = False
        self.deleted = False
        self.quit_suppressed = False
        self.direct_close_allowed = False

    def windowTitle(self) -> str:
        """Return the existing shell title."""

        return "Sugar Substitute"

    def windowIcon(self) -> object:
        """Return the existing shell icon."""

        return "icon"

    def geometry(self) -> object:
        """Return the existing shell geometry."""

        return "geometry"

    def isMaximized(self) -> bool:
        """Report that the shell is not maximized."""

        return False

    def suppress_app_quit_on_close(self) -> None:
        """Record that the reload helper suppressed application quit on close."""

        self.quit_suppressed = True

    def allow_direct_close(self) -> None:
        """Record that reload disposal can bypass coordinated shutdown."""

        self.direct_close_allowed = True

    def hide(self) -> None:
        """Record that the old frame was hidden."""

        self.hidden = True

    def close(self) -> None:
        """Record that the old frame was closed."""

        self.closed = True

    def deleteLater(self) -> None:
        """Record that the old frame was scheduled for deletion."""

        self.deleted = True


class _FakeNewFrame:
    """Capture new shell construction during reload tests."""

    def __init__(
        self,
        *,
        appearance_runtime: object,
        shutdown_request: object,
        backdrop_mode: ShellBackdropMode | None,
    ) -> None:
        """Store constructor arguments for assertions."""

        self.appearance_runtime = appearance_runtime
        self.shutdown_request = shutdown_request
        self.backdrop_mode = backdrop_mode
        self.title: str | None = None
        self.icon: object | None = None
        self.geometry: object | None = None
        self.shown = False
        self.maximized = False
        self.close_callbacks: list[object] = []
        self.titleBar = _FakeTitleBar(self.close_callbacks)

    def setWindowTitle(self, title: str) -> None:
        """Record the assigned shell title."""

        self.title = title

    def setWindowIcon(self, icon: object) -> None:
        """Record the assigned shell icon."""

        self.icon = icon

    def setGeometry(self, geometry: object) -> None:
        """Record the assigned shell geometry."""

        self.geometry = geometry

    def show(self) -> None:
        """Record that the new frame was shown."""

        self.shown = True

    def showMaximized(self) -> None:
        """Record that the new frame was shown maximized."""

        self.maximized = True

    def close(self) -> None:
        """Provide a close target for titlebar wiring assertions."""


class _FakeTitleBar:
    """Expose the close button surface used by shell wiring."""

    def __init__(self, callbacks: list[object]) -> None:
        """Store the callback sink for close-button signal connections."""

        self.closeBtn = _FakeCloseButton(callbacks)


class _FakeCloseButton:
    """Expose the clicked signal surface used by shell wiring."""

    def __init__(self, callbacks: list[object]) -> None:
        """Store the callback sink for clicked connections."""

        self.clicked = _FakeSignal(callbacks)


class _FakeSignal:
    """Record connected callbacks without Qt signal dependencies."""

    def __init__(self, callbacks: list[object]) -> None:
        """Store the callback sink for signal connections."""

        self._callbacks = callbacks

    def connect(self, callback: object) -> None:
        """Record one connected callback."""

        self._callbacks.append(callback)
