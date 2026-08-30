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

"""Cover bootstrap shell shutdown wiring."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from substitute.app.bootstrap import composition


class _FakeApp:
    """Minimal QApplication stand-in for startup contract tests."""

    def __init__(self, exit_code: int) -> None:
        self._exit_code = exit_code
        self.quit_calls = 0

    def exec(self) -> int:
        """Return configured event-loop exit code."""

        return self._exit_code

    def quit(self) -> None:
        """Record explicit quit requests."""

        self.quit_calls += 1


def test_custom_window_close_event_delegates_to_shutdown_request() -> None:
    """Shell close should route through the coordinated shutdown callback when configured."""

    requested_shutdowns: list[object] = []
    window = cast(Any, composition.CustomWindow.__new__(composition.CustomWindow))
    window._shutdown_request = requested_shutdowns.append
    window._allow_direct_close = False
    event = _FakeCloseEvent()

    composition.CustomWindow.closeEvent(window, event)

    assert event.ignored is True
    assert event.accepted is False
    assert requested_shutdowns == [window]


def test_custom_window_close_event_allows_final_close_after_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shell close should fall back to direct app quit once coordinated shutdown succeeds."""

    fake_app = _FakeApp(exit_code=0)
    base_close_calls: list[object] = []
    window = cast(Any, composition.CustomWindow.__new__(composition.CustomWindow))
    window._shutdown_request = None
    window._allow_direct_close = True
    event = _FakeCloseEvent()

    monkeypatch.setattr(
        "substitute.app.bootstrap.composition.QApplication.instance",
        staticmethod(lambda: fake_app),
    )
    monkeypatch.setattr(
        "substitute.app.bootstrap.composition.SubstituteWindowFrame.closeEvent",
        lambda self, close_event: base_close_calls.append((self, close_event)),
    )

    composition.CustomWindow.closeEvent(window, event)

    assert fake_app.quit_calls == 1
    assert event.accepted is True
    assert base_close_calls == [(window, event)]


def test_custom_window_close_event_allows_reload_disposal_without_app_quit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanctioned reload disposal should bypass shutdown and application quit."""

    requested_shutdowns: list[object] = []
    fake_app = _FakeApp(exit_code=0)
    base_close_calls: list[object] = []
    window = cast(Any, composition.CustomWindow.__new__(composition.CustomWindow))
    window._shutdown_request = requested_shutdowns.append
    window._allow_direct_close = True
    window._quit_application_on_close = False
    event = _FakeCloseEvent()

    monkeypatch.setattr(
        "substitute.app.bootstrap.composition.QApplication.instance",
        staticmethod(lambda: fake_app),
    )
    monkeypatch.setattr(
        "substitute.app.bootstrap.composition.SubstituteWindowFrame.closeEvent",
        lambda self, close_event: base_close_calls.append((self, close_event)),
    )

    composition.CustomWindow.closeEvent(window, event)

    assert requested_shutdowns == []
    assert fake_app.quit_calls == 0
    assert event.accepted is True
    assert base_close_calls == [(window, event)]


def test_show_main_window_closes_generation_execution_on_frame_destroyed() -> None:
    """Shell destruction should close the shared resource lifecycle owner."""

    source = Path(composition.__file__).read_text(encoding="utf-8")

    assert '"generation_job_queue"' in source
    assert '"workspace_generation"' in source
    assert (
        "frame.destroyed.connect(dependencies.shell_resource_lifecycle.shutdown)"
        in source
    )


class _FakeCloseEvent:
    """Provide the minimal close-event surface used by shell close tests."""

    def __init__(self) -> None:
        self.accepted = False
        self.ignored = False

    def accept(self) -> None:
        self.accepted = True

    def ignore(self) -> None:
        self.ignored = True
