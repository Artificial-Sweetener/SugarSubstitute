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
)
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
