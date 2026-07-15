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

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, TextIO, cast

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from substitute.app.bootstrap.splash_process import (
    _backdrop_mode_from_arg,
    _handle_cancel_requested,
    _theme_mode_from_arg,
)
from substitute.app.bootstrap.theme import configure_theme
from substitute.presentation.resources.app_icon import application_icon
from substitute.shared.qfluentwidgets_banner import (
    suppress_qfluentwidgets_import_banner,
)
from sugarsubstitute_shared.launch_splash import (
    SplashSessionMessage,
    SplashSessionServer,
    splash_cancel_signal_path,
)


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
        """Emit one authenticated message for GUI-thread handling."""

        self._bridge.message_received.emit(message)


def main(argv: list[str] | None = None) -> int:
    """Start the visible splash and serve authenticated local session messages."""

    args = _parse_args(sys.argv[1:] if argv is None else argv)
    app = QApplication.instance()
    if app is None:
        app = QApplication([sys.argv[0]])
    app = cast(QApplication, app)

    with suppress_qfluentwidgets_import_banner():
        configure_theme(
            theme_mode=_theme_mode_from_arg(args.theme_mode),
            accent_color=args.accent_color or "#E91E63",
        )
        app.setWindowIcon(application_icon())
        from substitute.presentation.shell.splash_window import SplashWindow

        splash = SplashWindow(backdrop_mode=_backdrop_mode_from_arg(args.backdrop_mode))

    bridge = SplashSessionQtBridge()
    bridge.message_received.connect(
        lambda message: _handle_session_message(message, splash=splash, app=app)
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
    splash.show()
    _write_ready_message(stream=sys.stdout, server=server)

    timeout_timer = QTimer()
    if args.maximum_lifetime_seconds > 0:
        timeout_timer.setSingleShot(True)
        timeout_timer.setInterval(int(args.maximum_lifetime_seconds * 1000))
        timeout_timer.timeout.connect(app.quit)
        timeout_timer.start()

    try:
        return int(app.exec())
    finally:
        server.close()


def _handle_session_message(
    message: SplashSessionMessage,
    *,
    splash: Any,
    app: QApplication,
) -> None:
    """Apply one authenticated shared-session message to the visible splash."""

    if message.message_type == "close":
        splash.close()
        app.quit()
        return
    if message.line:
        splash.append_log(message.line)


def _write_ready_message(*, stream: TextIO, server: SplashSessionServer) -> None:
    """Write the session spec to stdout for the launcher parent."""

    spec = server.spec
    payload = {
        "type": "ready",
        "endpoint": spec.endpoint,
        "token": spec.token,
        "host_pid": spec.host_pid,
    }
    stream.write(json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n")
    stream.flush()


def _handle_shared_cancel_requested(
    *,
    app: QApplication,
    stream: TextIO,
    server: SplashSessionServer,
) -> None:
    """Signal startup cancellation for direct and handed-off splash clients."""

    try:
        splash_cancel_signal_path(server.spec).write_text("cancel\n", encoding="utf-8")
    except OSError:
        pass
    _handle_cancel_requested(app=app, stream=stream)


def _clear_stale_cancel_signal(*, server: SplashSessionServer) -> None:
    """Remove any stale cancel flag left by a previous session using this token."""

    try:
        splash_cancel_signal_path(server.spec).unlink(missing_ok=True)
    except OSError:
        pass


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse shared splash host process arguments."""

    parser = argparse.ArgumentParser(description="Run SugarSubstitute splash host.")
    parser.add_argument("--theme-mode", type=str, required=False)
    parser.add_argument("--accent-color", type=str, required=False)
    parser.add_argument("--backdrop-mode", type=str, required=False)
    parser.add_argument("--maximum-lifetime-seconds", type=float, default=1800.0)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "QtSplashSessionMessageHandler",
    "SplashSessionQtBridge",
    "main",
]
