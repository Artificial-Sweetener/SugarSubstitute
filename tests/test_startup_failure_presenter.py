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

"""Tests for startup failure modal presentation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from substitute.application.errors import ErrorReport, ErrorReportKind
from substitute.presentation.errors import (
    present_startup_failure_report,
    startup_failure_presenter,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_PORTS_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_managed_ready_ports.py"
)


def test_present_startup_failure_report_uses_temporary_centered_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup failure presentation should own temporary Qt host cleanup."""

    hosts: list[_Host] = []
    presented: list[tuple[object, ErrorReport]] = []
    tool_flag = object()

    monkeypatch.setattr(
        startup_failure_presenter,
        "Qt",
        SimpleNamespace(WindowType=SimpleNamespace(Tool=tool_flag)),
    )
    monkeypatch.setattr(
        startup_failure_presenter,
        "QApplication",
        SimpleNamespace(primaryScreen=lambda: _Screen()),
    )
    monkeypatch.setattr(
        startup_failure_presenter,
        "QWidget",
        lambda: _record_host(hosts),
    )
    monkeypatch.setattr(
        startup_failure_presenter,
        "ErrorPresenter",
        lambda *, parent: _Presenter(parent=parent, presented=presented),
    )
    report = ErrorReport(
        kind=ErrorReportKind.COMFY_CONNECTION,
        title="ComfyUI failed to start",
        message="Backend exited.",
        stage="managed_startup",
    )

    startup_failure_presenter.present_startup_failure_report(report)

    assert len(hosts) == 1
    host = hosts[0]
    assert host.title == "ComfyUI startup failed"
    assert host.window_flags == [(tool_flag, True)]
    assert host.size == (1024, 768)
    assert host.moves == [(548, 156)]
    assert host.shown is True
    assert host.closed is True
    assert host.deleted is True
    assert presented == [(host, report)]


def test_startup_failure_presenter_exports_public_function() -> None:
    """Errors package should expose the startup failure presenter."""

    assert (
        present_startup_failure_report
        is startup_failure_presenter.present_startup_failure_report
    )


def test_startup_facade_no_longer_owns_failure_report_presentation() -> None:
    """Startup should delegate blocking report presentation to presentation errors."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    managed_ready_ports_source = STARTUP_MANAGED_READY_PORTS_SOURCE.read_text(
        encoding="utf-8"
    )

    assert "def _present_startup_failure_report" not in source
    assert "ErrorPresenter" not in source
    assert "present_startup_failure_report=present_startup_failure_report" not in source
    assert (
        "present_startup_failure_report=present_startup_failure_report"
        in managed_ready_ports_source
    )


def _record_host(hosts: list["_Host"]) -> "_Host":
    """Create and record one host widget double."""

    host = _Host()
    hosts.append(host)
    return host


class _Host:
    """Record temporary host widget calls."""

    def __init__(self) -> None:
        self.title = ""
        self.window_flags: list[tuple[object, bool]] = []
        self.size = (0, 0)
        self.moves: list[tuple[int, int]] = []
        self.shown = False
        self.closed = False
        self.deleted = False

    def setWindowTitle(self, title: str) -> None:
        """Record the host title."""

        self.title = title

    def setWindowFlag(self, flag: object, enabled: bool) -> None:
        """Record one host window flag mutation."""

        self.window_flags.append((flag, enabled))

    def resize(self, width: int, height: int) -> None:
        """Record the host dimensions."""

        self.size = (width, height)

    def width(self) -> int:
        """Return the recorded host width."""

        return self.size[0]

    def height(self) -> int:
        """Return the recorded host height."""

        return self.size[1]

    def move(self, x: int, y: int) -> None:
        """Record one host move."""

        self.moves.append((x, y))

    def show(self) -> None:
        """Record host display."""

        self.shown = True

    def close(self) -> None:
        """Record host close."""

        self.closed = True

    def deleteLater(self) -> None:
        """Record deferred host deletion."""

        self.deleted = True


class _Screen:
    """Return fixed screen geometry for centering tests."""

    def availableGeometry(self) -> "_Geometry":
        """Return one fake available desktop geometry."""

        return _Geometry()


class _Geometry:
    """Expose QRect-like geometry values."""

    def left(self) -> int:
        """Return the left edge."""

        return 100

    def top(self) -> int:
        """Return the top edge."""

        return 60

    def width(self) -> int:
        """Return the available width."""

        return 1920

    def height(self) -> int:
        """Return the available height."""

        return 960


class _Presenter:
    """Record startup failure report presentation."""

    def __init__(
        self,
        *,
        parent: object,
        presented: list[tuple[object, ErrorReport]],
    ) -> None:
        self._parent = parent
        self._presented = presented

    def show_error_report(self, report: ErrorReport) -> None:
        """Record one presented report."""

        self._presented.append((self._parent, report))
