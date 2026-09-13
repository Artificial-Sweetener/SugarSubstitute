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

"""Run the visible launch splash as a shared session host process."""

# ruff: noqa: E402 -- qualification timing intentionally precedes Qt imports.

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import os
import sys
from threading import Event
import time
from typing import TYPE_CHECKING, Any, TextIO, cast

_HOST_MODULE_STARTED_MONOTONIC_NS = time.monotonic_ns()

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

if TYPE_CHECKING:
    from sugarsubstitute_shared.launch_splash.protocol import SplashSessionMessage
    from sugarsubstitute_shared.launch_splash.server import SplashSessionServer


_SURFACE_EVIDENCE_ENV = "SUGAR_SUBSTITUTE_SPLASH_SURFACE_EVIDENCE"
_SURFACE_EVIDENCE_DIRECTORY = "qualification-splash-surfaces"
_REQUESTED_MONOTONIC_NS_ENV = "SUGAR_SUBSTITUTE_SPLASH_REQUESTED_MONOTONIC_NS"
_HOST_PROCESS_REQUESTED_MONOTONIC_NS_ENV = (
    "SUGAR_SUBSTITUTE_SPLASH_HOST_PROCESS_REQUESTED_MONOTONIC_NS"
)
_MESSAGE_APPLICATION_TIMEOUT_SECONDS = 2.0


@dataclass(slots=True)
class _SplashSessionDispatch:
    """Carry one message and its GUI-thread application acknowledgement."""

    message: SplashSessionMessage
    applied: Event = field(default_factory=Event)


class SplashSessionQtBridge(QObject):
    """Forward shared splash session messages onto the Qt GUI thread."""

    message_received = Signal(object)
    invalid_message_received = Signal(str)


class QtSplashSessionMessageHandler:
    """Publish TCP splash-session messages into a Qt bridge."""

    def __init__(self, bridge: SplashSessionQtBridge) -> None:
        """Store the bridge that owns GUI-thread signal delivery."""

        self._bridge = bridge

    def handle_message(self, message: SplashSessionMessage) -> None:
        """Wait until the GUI thread has applied one authenticated message."""

        dispatch = _SplashSessionDispatch(message)
        self._bridge.message_received.emit(dispatch)
        if not dispatch.applied.wait(_MESSAGE_APPLICATION_TIMEOUT_SECONDS):
            raise TimeoutError("Splash GUI did not apply the session message.")


def main(argv: list[str] | None = None) -> int:
    """Start the visible splash and serve authenticated local session messages."""

    main_entered_monotonic_ns = time.monotonic_ns()
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    arguments_parsed_monotonic_ns = time.monotonic_ns()
    app = QApplication.instance()
    if app is None:
        app = QApplication([sys.argv[0]])
    app = cast(QApplication, app)
    application_ready_monotonic_ns = time.monotonic_ns()
    icon_ready_monotonic_ns = time.monotonic_ns()
    from substitute.presentation.shell.splash_window import SplashWindow

    splash_module_ready_monotonic_ns = time.monotonic_ns()

    splash = SplashWindow(
        backdrop_mode=_backdrop_mode_value(args.backdrop_mode),
        theme_mode=args.theme_mode or "dark",
        accent_color=args.accent_color or "#E91E63",
        defer_animation_until_first_paint=True,
    )
    splash_constructed_monotonic_ns = time.monotonic_ns()

    first_paint_monotonic_ns: list[int] = []
    splash.firstFramePainted.connect(
        lambda: (
            first_paint_monotonic_ns.append(time.monotonic_ns())
            if not first_paint_monotonic_ns
            else None
        )
    )
    splash.center_on_screen()
    splash.show()
    app.processEvents()
    _write_surface_evidence(
        app=app,
        splash=splash,
        first_paint_monotonic_ns=(
            first_paint_monotonic_ns[0] if first_paint_monotonic_ns else None
        ),
        phase_monotonic_ns={
            **_environment_phase_monotonic_ns(),
            "host_module_started": _HOST_MODULE_STARTED_MONOTONIC_NS,
            "host_main_entered": main_entered_monotonic_ns,
            "arguments_parsed": arguments_parsed_monotonic_ns,
            "application_ready": application_ready_monotonic_ns,
            "icon_ready": icon_ready_monotonic_ns,
            "splash_module_ready": splash_module_ready_monotonic_ns,
            "splash_constructed": splash_constructed_monotonic_ns,
        },
    )

    from substitute.app.bootstrap.splash_localization import (
        build_splash_localization_runtime,
    )

    localization_runtime = build_splash_localization_runtime(
        app,
        locale_override=args.locale,
    )

    from sugarsubstitute_shared.launch_splash.server import SplashSessionServer

    bridge = SplashSessionQtBridge()
    bridge.message_received.connect(
        lambda dispatch: _apply_session_dispatch(dispatch, splash=splash, app=app)
    )
    bridge.invalid_message_received.connect(
        lambda _reason: None,
    )
    server = SplashSessionServer(
        message_handler=QtSplashSessionMessageHandler(bridge),
        on_invalid_message=lambda error: bridge.invalid_message_received.emit(
            type(error).__name__
        ),
    )
    _clear_stale_cancel_signal(server=server)
    server.start()
    splash.cancelRequested.connect(
        lambda: _handle_shared_cancel_requested(
            app=app,
            stream=sys.stdout,
            server=server,
        )
    )
    _write_ready_message(stream=sys.stdout, server=server)

    timeout_timer = QTimer()
    if args.maximum_lifetime_seconds > 0:
        timeout_timer.setSingleShot(True)
        timeout_timer.setInterval(int(args.maximum_lifetime_seconds * 1000))
        timeout_timer.timeout.connect(
            lambda: _close_splash_and_quit(splash=splash, app=app)
        )
        timeout_timer.start()

    try:
        return int(app.exec())
    finally:
        server.close()
        localization_runtime.manager.close()


def _handle_session_message(
    message: SplashSessionMessage,
    *,
    splash: Any,
    app: QApplication,
) -> None:
    """Apply one authenticated shared-session message to the visible splash."""

    if message.message_type == "close":
        _close_splash_and_quit(splash=splash, app=app)
        return
    if message.message_type == "activate":
        _activate_splash(splash=splash, app=app)
        return
    if message.message_type == "activity":
        if message.activity is not None:
            splash.start_activity(message.activity)
        return
    if message.message_type == "clear_activity":
        splash.clear_activity()
        return
    if message.line:
        splash.append_log(message.line)


def _apply_session_dispatch(
    dispatch: _SplashSessionDispatch,
    *,
    splash: Any,
    app: QApplication,
) -> None:
    """Apply one session message and release its waiting request thread."""

    try:
        _handle_session_message(dispatch.message, splash=splash, app=app)
    finally:
        dispatch.applied.set()


def _close_splash_and_quit(*, splash: Any, app: QApplication) -> None:
    """Stop splash-owned native work before leaving the Qt event loop."""

    splash.close()
    app.quit()


def _activate_splash(*, splash: Any, app: QApplication) -> None:
    """Reveal and foreground the existing startup surface."""

    if splash.isMinimized():
        splash.showNormal()
    elif not splash.isVisible():
        splash.show()
    splash.raise_()
    splash.activateWindow()
    splash.update()
    app.processEvents()


def _write_ready_message(*, stream: TextIO, server: SplashSessionServer) -> None:
    """Write the session spec to stdout for the launcher parent."""

    import json

    spec = server.spec
    payload = {
        "type": "ready",
        "endpoint": spec.endpoint,
        "token": spec.token,
        "host_pid": spec.host_pid,
    }
    stream.write(json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n")
    stream.flush()


def _write_surface_evidence(
    *,
    app: QApplication,
    splash: Any,
    first_paint_monotonic_ns: int | None,
    phase_monotonic_ns: dict[str, int] | None = None,
) -> None:
    """Record offscreen surface facts only for explicit startup qualification."""

    if os.environ.get(_SURFACE_EVIDENCE_ENV) != "1":
        return
    import json
    from pathlib import Path

    top_level_widgets = tuple(app.topLevelWidgets())
    requested_monotonic_ns = _requested_monotonic_ns()
    payload = {
        "first_paint_monotonic_ns": first_paint_monotonic_ns,
        "first_paint_confirmed": first_paint_monotonic_ns is not None,
        "launch_to_first_paint_ms": (
            (first_paint_monotonic_ns - requested_monotonic_ns) / 1_000_000
            if first_paint_monotonic_ns is not None
            and requested_monotonic_ns is not None
            else None
        ),
        "host_pid": os.getpid(),
        "platform_name": app.platformName(),
        "splash_is_visible": bool(splash.isVisible()),
        "top_level_surface_count": len(top_level_widgets),
        "visible_top_level_surface_count": sum(
            widget.isVisible() for widget in top_level_widgets
        ),
        "startup_phase_ms": _startup_phase_durations(
            requested_monotonic_ns=requested_monotonic_ns,
            first_paint_monotonic_ns=first_paint_monotonic_ns,
            phase_monotonic_ns=phase_monotonic_ns or {},
        ),
    }
    evidence_dir = Path.cwd() / "user" / _SURFACE_EVIDENCE_DIRECTORY
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / f"{os.getpid()}.json"
    evidence_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _startup_phase_durations(
    *,
    requested_monotonic_ns: int | None,
    first_paint_monotonic_ns: int | None,
    phase_monotonic_ns: dict[str, int],
) -> dict[str, float]:
    """Return qualification phase offsets relative to the launch request."""

    if requested_monotonic_ns is None:
        return {}
    phases = dict(phase_monotonic_ns)
    if first_paint_monotonic_ns is not None:
        phases["first_paint"] = first_paint_monotonic_ns
    return {
        name: round((timestamp - requested_monotonic_ns) / 1_000_000, 3)
        for name, timestamp in phases.items()
    }


def _requested_monotonic_ns() -> int | None:
    """Return an authenticated qualification launch origin when supplied."""

    raw_value = os.environ.get(_REQUESTED_MONOTONIC_NS_ENV)
    if raw_value is None:
        return None
    try:
        value = int(raw_value)
    except ValueError:
        return None
    return value if value > 0 else None


def _environment_phase_monotonic_ns() -> dict[str, int]:
    """Return valid qualification timestamps inherited from the launcher."""

    raw_value = os.environ.get(_HOST_PROCESS_REQUESTED_MONOTONIC_NS_ENV)
    if raw_value is None:
        return {}
    try:
        value = int(raw_value)
    except ValueError:
        return {}
    return {"host_process_requested": value} if value > 0 else {}


def _handle_shared_cancel_requested(
    *,
    app: QApplication,
    stream: TextIO,
    server: SplashSessionServer,
) -> None:
    """Signal startup cancellation for direct and handed-off splash clients."""

    from substitute.app.bootstrap.splash_cancel import notify_cancel_requested
    from sugarsubstitute_shared.launch_splash.session import splash_cancel_signal_path

    try:
        splash_cancel_signal_path(server.spec).write_text("cancel\n", encoding="utf-8")
    except OSError:
        pass
    notify_cancel_requested(app=app, stream=stream)


def _clear_stale_cancel_signal(*, server: SplashSessionServer) -> None:
    """Remove any stale cancel flag left by a previous session using this token."""

    from sugarsubstitute_shared.launch_splash.session import splash_cancel_signal_path

    try:
        splash_cancel_signal_path(server.spec).unlink(missing_ok=True)
    except OSError:
        pass


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse shared splash host process arguments."""

    from sugarsubstitute_shared.localization.application_message import app_text
    from sugarsubstitute_shared.localization.cli import parse_locale_override

    parser = argparse.ArgumentParser(
        description=app_text("Run SugarSubstitute splash host.")
    )
    parser.add_argument("--theme-mode", type=str, required=False)
    parser.add_argument("--accent-color", type=str, required=False)
    parser.add_argument("--backdrop-mode", type=str, required=False)
    parser.add_argument("--maximum-lifetime-seconds", type=float, default=0.0)
    parser.add_argument("--locale", type=parse_locale_override, default="en")
    return parser.parse_args(argv)


def _backdrop_mode_value(raw_value: str | None) -> str | None:
    """Return the safe raw backdrop value without importing shell policy."""

    if raw_value == "none":
        return None
    return "acrylic" if raw_value == "acrylic" else "mica"


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "QtSplashSessionMessageHandler",
    "SplashSessionQtBridge",
    "main",
]
