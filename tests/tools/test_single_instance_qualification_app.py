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

"""Verify deterministic timing controls for packaged launch qualification."""

from collections.abc import Callable
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace
from typing import Any, cast

import pytest

from tools.single_instance_qualification_app import (
    APPLICATION_EXIT_AFTER_INVOCATIONS_ENV,
    APPLICATION_REGISTRATION_DELAY_ENV,
    APPLICATION_REGISTRATION_GATE_ENV,
    APPLICATION_WINDOW_CONSTRUCTION_GATE_ENV,
    _delay_application_registration,
    _schedule_splash_close_after_surface_paint,
    _wait_at_application_registration_gate,
    _wait_at_window_construction_gate,
    application_prewindow_marker_path,
    application_prewindow_release_path,
    application_preregistration_claim_path,
    application_preregistration_marker_path,
    application_preregistration_release_path,
    main,
)
from sugarsubstitute_shared.crash_reporting.protocol import CleanExitOutcome
from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation
from sugarsubstitute_shared.launch_splash.session import SplashSessionSpec


def test_application_registration_delay_is_explicit_and_one_shot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Delay only the selected qualification child registration."""

    observed: list[tuple[float, int]] = []
    marker_path = application_preregistration_marker_path(tmp_path)
    process_sleep = time.sleep

    def observe_preregistration(delay: float) -> None:
        """Capture the disposable synchronization marker during the delay."""

        assert time.sleep is process_sleep
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
        observed.append((delay, payload["pid"]))

    sleep: Callable[[float], None] = observe_preregistration
    monkeypatch.setenv(APPLICATION_REGISTRATION_DELAY_ENV, "1.25")
    monkeypatch.setattr(
        "tools.single_instance_qualification_app.time",
        SimpleNamespace(sleep=sleep, monotonic=time.monotonic),
    )

    _delay_application_registration(tmp_path)
    _delay_application_registration(tmp_path)

    assert observed == [(1.25, os.getpid())]


def test_window_construction_gate_starts_after_registration_and_releases_explicitly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Synchronize the pre-window process phase without clock assertions."""

    marker_path = application_prewindow_marker_path(tmp_path)
    release_path = application_prewindow_release_path(tmp_path)
    observed_pids: list[int] = []

    def release_after_observing_marker(_interval: float) -> None:
        """Prove the process phase before releasing window construction."""

        payload = json.loads(marker_path.read_text(encoding="utf-8"))
        observed_pids.append(payload["pid"])
        release_path.write_text("release", encoding="utf-8")

    monkeypatch.setenv(APPLICATION_WINDOW_CONSTRUCTION_GATE_ENV, "1")
    monkeypatch.setattr(
        "tools.single_instance_qualification_app.time",
        SimpleNamespace(sleep=release_after_observing_marker, monotonic=time.monotonic),
    )

    _wait_at_window_construction_gate(tmp_path)

    assert observed_pids == [os.getpid()]
    assert not release_path.exists()


def test_application_registration_gate_releases_explicitly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Synchronize the pre-registration process phase without a timed delay."""

    marker_path = application_preregistration_marker_path(tmp_path)
    release_path = application_preregistration_release_path(tmp_path)
    observed_pids: list[int] = []

    def release_after_observing_marker(_interval: float) -> None:
        """Prove the process phase before releasing registration."""

        payload = json.loads(marker_path.read_text(encoding="utf-8"))
        observed_pids.append(payload["pid"])
        release_path.write_text("release", encoding="utf-8")

    monkeypatch.setenv(APPLICATION_REGISTRATION_GATE_ENV, "1")
    monkeypatch.setattr(
        "tools.single_instance_qualification_app.time",
        SimpleNamespace(sleep=release_after_observing_marker, monotonic=time.monotonic),
    )

    _wait_at_application_registration_gate(tmp_path)

    assert observed_pids == [os.getpid()]
    assert not release_path.exists()
    assert application_preregistration_claim_path(tmp_path).is_file()

    monkeypatch.setenv(APPLICATION_REGISTRATION_GATE_ENV, "1")
    _wait_at_application_registration_gate(tmp_path)

    assert observed_pids == [os.getpid()]


def test_qualification_child_records_applied_splash_close(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The replacement surface must close and observe its adopted splash."""

    callbacks: list[Callable[[], None]] = []
    spec = SplashSessionSpec(
        host="127.0.0.1",
        port=54321,
        token="x" * 32,
        host_pid=1234,
    )

    class _AcknowledgedClient:
        """Report an applied close message without opening a socket."""

        def __init__(self, received_spec: SplashSessionSpec) -> None:
            """Require the exact adopted session identity."""

            assert received_spec == spec

        def close(self) -> bool:
            """Report host-side message application."""

            return True

    monkeypatch.setattr(
        "tools.single_instance_qualification_app.splash_session_from_args",
        lambda _arguments: spec,
    )
    monkeypatch.setattr(
        "tools.single_instance_qualification_app.SocketSplashSessionClient",
        _AcknowledgedClient,
    )
    monkeypatch.setattr(
        "tools.single_instance_qualification_app.run_after_surface_paint",
        lambda _window, callback: callbacks.append(callback),
    )

    _schedule_splash_close_after_surface_paint(
        ["main.py"],
        tmp_path,
        cast(Any, object()),
    )
    adoption_path = next(
        (tmp_path / "user" / "qualification-splash-adoptions").glob("*.json")
    )
    assert json.loads(adoption_path.read_text(encoding="utf-8")) == {
        "app_pid": os.getpid(),
        "close_acknowledged": None,
        "splash_host_pid": 1234,
    }

    callbacks[0]()

    assert json.loads(adoption_path.read_text(encoding="utf-8")) == {
        "app_pid": os.getpid(),
        "close_acknowledged": True,
        "splash_host_pid": 1234,
    }


def test_qualification_child_authenticates_requested_clean_close(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deliberate qualification exit must satisfy crash supervision."""

    lifecycle_messages: list[tuple[str, CleanExitOutcome, int]] = []
    observers: list[Callable[[ApplicationInvocation], None] | None] = [None]

    class _CrashContext:
        """Record the qualification child's authenticated lifecycle messages."""

        def write_exit_intent(
            self,
            outcome: CleanExitOutcome,
            *,
            process_id: int,
        ) -> None:
            """Record controlled-exit intent."""

            lifecycle_messages.append(("intent", outcome, process_id))

        def write_exit_receipt(
            self,
            outcome: CleanExitOutcome,
            *,
            process_id: int,
        ) -> None:
            """Record completed cleanup."""

            lifecycle_messages.append(("receipt", outcome, process_id))

    class _Application:
        """Drive one invocation through the qualification event-loop boundary."""

        def __init__(self, _arguments: list[str]) -> None:
            """Initialize an active deterministic event loop."""

            self.quit_requested = False

        def exec(self) -> int:
            """Deliver one secondary invocation and return after close."""

            observer = observers[0]
            assert observer is not None
            observer(
                ApplicationInvocation(
                    arguments=("SugarSubstitute.exe",),
                    working_directory=str(tmp_path),
                )
            )
            assert self.quit_requested is True
            return 0

        def quit(self) -> None:
            """Record the requested event-loop exit."""

            self.quit_requested = True

    class _Window:
        """Provide the minimal qualification surface contract."""

        def setWindowTitle(self, _title: str) -> None:
            """Accept the qualification title."""

        def resize(self, _width: int, _height: int) -> None:
            """Accept the qualification size."""

        def show(self) -> None:
            """Expose the qualification surface."""

        def update(self) -> None:
            """Accept the requested paint update."""

    class _Control:
        """Represent an active application-instance control channel."""

        def request_restart(self) -> bool:
            """Reject unused restart requests."""

            return False

    def capture_control(
        *,
        invocation_observer: Callable[[ApplicationInvocation], None],
    ) -> _Control:
        """Capture the observer registered by the qualification child."""

        observers[0] = invocation_observer
        return _Control()

    monkeypatch.setenv(APPLICATION_EXIT_AFTER_INVOCATIONS_ENV, "1")
    monkeypatch.setattr(
        "tools.single_instance_qualification_app.application_launch_install_root",
        lambda _arguments, app_root: tmp_path,
    )
    monkeypatch.setattr(
        "tools.single_instance_qualification_app.CrashRunContext.from_environment",
        lambda: _CrashContext(),
    )
    monkeypatch.setattr(
        "tools.single_instance_qualification_app.QApplication", _Application
    )
    monkeypatch.setattr("tools.single_instance_qualification_app.QWidget", _Window)
    monkeypatch.setattr(
        "tools.single_instance_qualification_app.start_application_instance_control",
        capture_control,
    )
    monkeypatch.setattr(
        "tools.single_instance_qualification_app.stop_application_instance_control",
        lambda: None,
    )
    monkeypatch.setattr(
        "tools.single_instance_qualification_app.schedule_main_shell_readiness_receipt",
        lambda _window: True,
    )
    monkeypatch.setattr(
        "tools.single_instance_qualification_app._schedule_splash_close_after_surface_paint",
        lambda _arguments, _root, _window: None,
    )
    monkeypatch.setattr(
        "tools.single_instance_qualification_app._surface_evidence",
        lambda _window: {"visible": True},
    )
    monkeypatch.setattr(
        "tools.single_instance_qualification_app.run_after_surface_paint",
        lambda _window, callback: callback(),
    )
    monkeypatch.setattr(
        "tools.single_instance_qualification_app.QTimer.singleShot",
        lambda _milliseconds, _callback: None,
    )

    assert main(["qualification-app"]) == 0
    assert lifecycle_messages == [
        ("intent", CleanExitOutcome.CLOSED, os.getpid()),
        ("receipt", CleanExitOutcome.CLOSED, os.getpid()),
    ]
