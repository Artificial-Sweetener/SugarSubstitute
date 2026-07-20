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

"""Tests for bootstrap-owned early launch-splash composition."""

from __future__ import annotations

from pathlib import Path
import time
from typing import Any

from substitute.app.bootstrap import early_launch_splash
from sugarsubstitute_shared.launch_splash import (
    create_splash_session_spec,
    splash_cancel_signal_path,
    splash_session_args,
)


class _Splash:
    """Record early launch-splash calls."""

    def __init__(self) -> None:
        """Create an empty splash call recorder."""

        self.lines: list[str] = []

    def append_log(self, line: str) -> None:
        """Record one splash log line."""

        self.lines.append(line)

    def close(self) -> None:
        """Accept close calls from protocol consumers."""


def test_early_launch_splash_supplies_process_pump_task_factory(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """Early launch splash should use bootstrap-owned process-pump composition."""

    captured: dict[str, object] = {}
    splash = _Splash()

    def _start_shared_launch_splash(
        **kwargs: object,
    ) -> tuple[_Splash, object | None]:
        captured.update(kwargs)
        return splash, None

    monkeypatch.setattr(
        early_launch_splash,
        "start_shared_launch_splash",
        _start_shared_launch_splash,
    )

    started_splash, cancel_relay = early_launch_splash.start_early_launch_splash(
        ["main.py"],
        tmp_path,
        "en",
    )

    assert started_splash is splash
    assert cancel_relay is not None
    assert captured["app_root"] == tmp_path
    assert callable(captured["on_cancel_requested"])
    assert captured["process_pump_task_factory"] is (
        early_launch_splash._create_early_process_pump_task
    )
    assert splash.lines == ["Starting SugarSubstitute."]


def test_early_launch_splash_skips_no_comfy_startup(tmp_path: Path) -> None:
    """No-Comfy startup should not create the early launch splash."""

    assert early_launch_splash.start_early_launch_splash(
        ["main.py", "--no-comfy"],
        tmp_path,
        "en",
    ) == (None, None)


def test_early_launch_splash_skips_startup_harness(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """Startup harness runs should not create desktop splash windows."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")

    assert early_launch_splash.start_early_launch_splash(
        ["main.py"],
        tmp_path,
        "en",
    ) == (None, None)


def test_early_launch_splash_adopts_launcher_session(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """Launcher-provided splash sessions should be adopted before app startup."""

    spec = create_splash_session_spec(port=49152, token="x" * 32, host_pid=1234)
    splash = _Splash()
    adopted_specs: list[object] = []

    def _connect_splash_session(passed_spec: object) -> _Splash:
        """Record the adopted spec and return the fake splash."""

        adopted_specs.append(passed_spec)
        return splash

    monkeypatch.setattr(
        early_launch_splash,
        "_connect_splash_session",
        _connect_splash_session,
    )
    monkeypatch.setattr(
        early_launch_splash,
        "start_shared_launch_splash",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("adoption should not start a second splash")
        ),
    )

    started_splash, cancel_relay = early_launch_splash.start_early_launch_splash(
        ["main.py", *splash_session_args(spec)],
        tmp_path,
        "en",
    )

    assert started_splash is splash
    assert cancel_relay is not None
    assert adopted_specs == [spec]
    assert splash.lines == ["Starting SugarSubstitute."]


def test_early_launch_splash_falls_back_when_adopted_session_write_fails(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """A failed launcher-session write should fall back to the app splash."""

    spec = create_splash_session_spec(port=49152, token="x" * 32, host_pid=1234)
    adopted_splash = _FailingSplash()
    fallback_splash = _Splash()

    monkeypatch.setattr(
        early_launch_splash,
        "_connect_splash_session",
        lambda _spec: adopted_splash,
    )
    monkeypatch.setattr(
        early_launch_splash,
        "start_shared_launch_splash",
        lambda **_kwargs: (fallback_splash, None),
    )

    started_splash, cancel_relay = early_launch_splash.start_early_launch_splash(
        ["main.py", *splash_session_args(spec)],
        tmp_path,
        "en",
    )

    assert started_splash is fallback_splash
    assert cancel_relay is not None
    assert fallback_splash.lines == ["Starting SugarSubstitute."]


def test_early_launch_splash_cancel_signal_reaches_relay(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """Shared host cancel signals should reach the app after session adoption."""

    spec = create_splash_session_spec(port=49152, token="z" * 32, host_pid=1234)
    cancel_path = splash_cancel_signal_path(spec)
    cancel_path.unlink(missing_ok=True)
    splash = _Splash()

    monkeypatch.setattr(
        early_launch_splash,
        "_connect_splash_session",
        lambda _spec: splash,
    )
    monkeypatch.setattr(early_launch_splash, "_CANCEL_SIGNAL_POLL_SECONDS", 0.01)

    _started_splash, cancel_relay = early_launch_splash.start_early_launch_splash(
        ["main.py", *splash_session_args(spec)],
        tmp_path,
        "en",
    )
    assert cancel_relay is not None
    cancel_path.write_text("cancel\n", encoding="utf-8")

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and not cancel_relay.cancel_requested():
        time.sleep(0.01)

    assert cancel_relay.cancel_requested() is True
    cancel_path.unlink(missing_ok=True)


class _FailingSplash:
    """Splash double that fails writes like a dead adopted IPC session."""

    def append_log(self, _line: str) -> None:
        """Raise an OS-level IPC failure."""

        raise OSError("session unavailable")

    def close(self) -> None:
        """Accept close calls from protocol consumers."""
