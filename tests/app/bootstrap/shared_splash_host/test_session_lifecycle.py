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

"""Prove real shared-host initialization and acknowledged Qt shutdown ordering."""

from __future__ import annotations

from collections.abc import Callable
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Event, Thread
from typing import TextIO, cast
from unittest.mock import patch

import pytest


@pytest.mark.parametrize(
    "scenario", ("theme_first", "animation_first", "theme_failure", "animation_failure")
)
def test_shared_host_initializes_before_readiness_and_acknowledges_close(
    tmp_path: Path, scenario: str
) -> None:
    """Require both startup phases and explicit ACK-owned shutdown in a fresh Qt loop.

    A child process owns QApplication's actual default quit behavior; the shared
    pytest application deliberately disables automatic last-window shutdown.
    The timeout bounds failed cleanup rather than measuring startup performance.
    """
    evidence_path = tmp_path / "session-lifecycle.json"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[4])
    environment["QT_QPA_PLATFORM"] = "offscreen"
    process = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            str(evidence_path),
            scenario,
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )

    assert process.returncode == 0, process.stderr
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["errors"] == [], evidence
    assert evidence["server_closed"] is True, evidence
    assert "watchdog" not in evidence["events"], evidence
    if scenario.endswith("_failure"):
        assert evidence["host_exit_code"] == 1, evidence
        assert evidence["readiness_phases"] == [], evidence
        assert evidence["client_close_results"] == [], evidence
        failure_event = scenario.removesuffix("_failure") + "_failed"
        assert evidence["events"].index(failure_event) < evidence["events"].index(
            "about_to_quit"
        ), evidence
        return
    assert evidence["readiness_phases"] == [["animation", "theme"]], evidence
    assert evidence["client_close_results"] == [True], evidence
    assert evidence["automatic_last_window_quit"] is False, evidence
    assert evidence["splash_hidden_before_explicit_quit"] is True, evidence
    assert evidence["client_ack_before_quit"] is True, evidence
    assert evidence["host_exit_code"] == 0, evidence
    events = evidence["events"]
    first, second = (
        ("theme_completed", "animation_completed")
        if scenario == "theme_first"
        else ("animation_completed", "theme_completed")
    )
    assert events.index(first) < events.index(second) < events.index("ready"), evidence
    assert events.index("server_acknowledged") < events.index("explicit_quit"), evidence
    assert events.index("explicit_quit") < events.index("about_to_quit"), evidence


def _run_host_child(evidence_path: Path, scenario: str) -> None:
    """Exercise production host, socket transport and window with controlled phases."""
    if sys.platform == "darwin":
        from tests.conftest import _install_offscreen_macos_frameless_shim

        _install_offscreen_macos_frameless_shim()

    from PySide6.QtCore import QObject, QTimer
    from PySide6.QtWidgets import QApplication, QWidget

    from substitute.app.bootstrap import shared_splash_host, theme
    from substitute.domain.appearance import AppearanceThemeMode
    from substitute.presentation.shell.splash_window import SplashWindow
    from sugarsubstitute_shared.launch_splash import SocketSplashSessionClient
    from sugarsubstitute_shared.launch_splash.protocol import SplashSessionMessage
    from sugarsubstitute_shared.launch_splash.server import SplashSessionServer

    application = QApplication([])
    completed_phases: set[str] = set()
    readiness_phases: list[list[str]] = []
    client_close_results: list[bool] = []
    events: list[str] = []
    errors: list[str] = []
    observations: dict[str, bool] = {}
    client_finished = Event()
    clients: list[Thread] = []
    pending_theme: list[Callable[[], None]] = []
    original_configure_theme = theme.configure_theme
    original_schedule_theme = theme.schedule_splash_theme
    original_build_animation = cast(
        Callable[[SplashWindow, QWidget], QWidget],
        getattr(SplashWindow, "_build_animated_splash_visual"),
    )
    original_acknowledged_message = shared_splash_host._handle_acknowledged_message
    original_server_close = SplashSessionServer.close

    def configure_theme(*, theme_mode: AppearanceThemeMode, accent_color: str) -> None:
        """Complete real theme work before releasing its production callback."""
        if scenario == "theme_failure":
            events.append("theme_failed")
            raise OSError("Controlled theme initialization failure.")
        original_configure_theme(theme_mode=theme_mode, accent_color=accent_color)
        completed_phases.add("theme")
        events.append("theme_completed")

    def schedule_theme(
        *,
        owner: QObject,
        theme_mode: str | None,
        accent_color: str | None,
        on_complete: Callable[[], None] | None = None,
        on_failure: Callable[[Exception], None] | None = None,
    ) -> None:
        """Control which phase finishes first without substituting readiness logic."""

        def schedule() -> None:
            """Delegate actual theme completion signaling to its production owner."""
            if on_complete is None:
                original_schedule_theme(
                    owner=owner, theme_mode=theme_mode, accent_color=accent_color
                )
            else:
                original_schedule_theme(
                    owner=owner,
                    theme_mode=theme_mode,
                    accent_color=accent_color,
                    on_complete=on_complete,
                    on_failure=on_failure,
                )

        if scenario == "animation_first":
            pending_theme.append(schedule)
        else:
            schedule()

    def build_animation(window: SplashWindow, parent: QWidget) -> QWidget:
        """Observe real animation preparation before its owner signals completion."""
        if scenario == "animation_failure":
            events.append("animation_failed")
            raise OSError("Controlled animation initialization failure.")
        visual = original_build_animation(window, parent)
        completed_phases.add("animation")
        events.append("animation_completed")
        for schedule in pending_theme:
            QTimer.singleShot(0, application, schedule)
        pending_theme.clear()
        return visual

    def publish_ready(*, stream: TextIO, server: SplashSessionServer) -> None:
        """Capture readiness without exposing credentials, then close over real TCP."""
        del stream
        readiness_phases.append(sorted(completed_phases))
        observations["automatic_last_window_quit"] = (
            application.quitOnLastWindowClosed()
        )
        events.append("ready")

        def close() -> None:
            """Observe the real applied-message acknowledgement in another thread."""
            try:
                client_close_results.append(
                    SocketSplashSessionClient(server.spec).close()
                )
            except Exception as error:
                errors.append(type(error).__name__)
            finally:
                client_finished.set()

        client = Thread(target=close, name="splash-lifecycle-close", daemon=True)
        clients.append(client)
        client.start()

    def acknowledge_message(
        message: SplashSessionMessage, *, app: QApplication
    ) -> None:
        """Hold explicit shutdown until the requester has consumed the actual ACK."""
        if message.message_type == "close":
            events.append("server_acknowledged")
            if not client_finished.wait(timeout=10):
                errors.append("client_ack_not_received")
            splashes = tuple(
                window
                for window in app.topLevelWidgets()
                if isinstance(window, SplashWindow)
            )
            observations["splash_hidden_before_explicit_quit"] = bool(splashes) and all(
                not window.isVisible() for window in splashes
            )
            events.append("explicit_quit")
        original_acknowledged_message(message, app=app)

    def observe_quit() -> None:
        """Record whether the real event loop exited before acknowledged shutdown."""
        observations["client_ack_before_quit"] = (
            client_finished.is_set() and client_close_results == [True]
        )
        events.append("about_to_quit")

    def close_server(server: SplashSessionServer) -> None:
        """Verify terminal host paths actually release the real socket server."""
        original_server_close(server)
        observations["server_closed"] = True
        events.append("server_closed")

    def stop_failed_child() -> None:
        """Bound a regressed lifecycle without treating elapsed time as success."""
        events.append("watchdog")
        application.exit(87)

    application.aboutToQuit.connect(observe_quit)
    watchdog = QTimer()
    watchdog.setSingleShot(True)
    watchdog.timeout.connect(stop_failed_child)
    watchdog.start(30_000)
    with (
        patch.object(theme, "configure_theme", configure_theme),
        patch.object(theme, "schedule_splash_theme", schedule_theme),
        patch.object(SplashWindow, "_build_animated_splash_visual", build_animation),
        patch.object(shared_splash_host, "_write_ready_message", publish_ready),
        patch.object(SplashSessionServer, "close", close_server),
        patch.object(
            shared_splash_host, "_handle_acknowledged_message", acknowledge_message
        ),
    ):
        exit_code = shared_splash_host.main(["--backdrop-mode=none"])
    watchdog.stop()
    for client in clients:
        client.join(timeout=10)
        if client.is_alive():
            errors.append("client_thread_not_stopped")
    evidence_path.write_text(
        json.dumps(
            {
                "readiness_phases": readiness_phases,
                "client_close_results": client_close_results,
                "events": events,
                "errors": errors,
                "host_exit_code": exit_code,
                **observations,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    _run_host_child(Path(sys.argv[1]), sys.argv[2])
