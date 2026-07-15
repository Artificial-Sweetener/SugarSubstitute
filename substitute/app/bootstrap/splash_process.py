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

"""Run the internal launch splash helper process."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
from collections.abc import Callable
from typing import Any, TextIO, cast

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from substitute.app.bootstrap.theme import configure_theme
from substitute.domain.appearance import AppearanceThemeMode
from substitute.application.execution import (
    CancellationToken,
    ExecutionContext,
    TaskIdentity,
)
from substitute.app.bootstrap.standalone_long_lived_execution import (
    StandaloneLongLivedExecutionOwner,
)
from substitute.presentation.resources.app_icon import application_icon
from substitute.presentation.shell.window_frame import ShellBackdropMode
from substitute.shared.qfluentwidgets_banner import (
    suppress_qfluentwidgets_import_banner,
)

_PARENT_POLL_INTERVAL_MS = 1000
_SYNCHRONIZE = 0x00100000
_WAIT_OBJECT_0 = 0x00000000
_WAIT_TIMEOUT = 0x00000102


class SplashMessageBridge(QObject):
    """Bridge stdin reader messages onto the Qt GUI thread."""

    message_received = Signal(dict)
    input_closed = Signal()


class _SplashProcessDispatcher:
    """Publish helper reader callbacks directly inside the helper process."""

    def publish(self, callback: Callable[[], None], *, reason: str) -> None:
        """Run one long-lived task callback immediately."""

        _ = reason
        callback()


def main(argv: list[str] | None = None) -> int:
    """Run the splash helper process until the parent or IPC requests exit."""

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
    splash.cancelRequested.connect(
        lambda: _handle_cancel_requested(app=app, stream=sys.stdout)
    )
    splash.show()

    bridge = SplashMessageBridge()
    bridge.message_received.connect(
        lambda message: _handle_message(message, splash=splash, app=app)
    )
    bridge.input_closed.connect(app.quit)

    helper_execution = StandaloneLongLivedExecutionOwner(
        dispatcher=_SplashProcessDispatcher()
    )
    message_reader = helper_execution.start(
        identity=TaskIdentity(
            request_id=1,
            domain="launch_splash_stdin_reader",
        ),
        context=ExecutionContext(
            operation="launch_splash_stdin_reader",
            reason="launch_splash_helper_stdin",
            lane="process_pump",
        ),
        work=lambda cancellation: _read_messages(
            stream=sys.stdin,
            bridge=bridge,
            cancellation=cancellation,
        ),
        thread_name="substitute-launch-splash-stdin",
    )

    parent_timer = QTimer()
    parent_timer.setInterval(_PARENT_POLL_INTERVAL_MS)
    parent_timer.timeout.connect(
        lambda: app.quit() if not parent_process_is_alive(args.parent_pid) else None
    )
    parent_timer.start()

    exit_code = int(app.exec())
    message_reader.stop(reason="splash_helper_exit")
    return exit_code


def decode_splash_message(line: str) -> dict[str, str] | None:
    """Decode one newline-delimited JSON splash IPC message."""

    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    message_type = payload.get("type")
    if not isinstance(message_type, str):
        return None
    message: dict[str, str] = {"type": message_type}
    line_value = payload.get("line")
    if isinstance(line_value, str):
        message["line"] = line_value
    return message


def encode_splash_helper_event(message: dict[str, str]) -> str:
    """Return one compact helper-to-parent splash event."""

    return json.dumps(message, ensure_ascii=True, separators=(",", ":"))


def parent_process_is_alive(parent_pid: int) -> bool:
    """Return whether the helper parent process still exists."""

    if parent_pid <= 0:
        return False
    if os.name == "nt":
        return _windows_process_is_alive(parent_pid)
    try:
        os.kill(parent_pid, 0)
    except OSError:
        return False
    return True


def _read_messages(
    *,
    stream: TextIO,
    bridge: SplashMessageBridge,
    cancellation: CancellationToken,
) -> None:
    """Read helper IPC messages and emit them to the GUI-thread bridge."""

    for line in stream:
        if cancellation.is_cancelled:
            return
        message = decode_splash_message(line)
        if message is not None:
            bridge.message_received.emit(message)
    bridge.input_closed.emit()


def _handle_message(
    message: dict[str, str],
    *,
    splash: Any,
    app: QApplication,
) -> None:
    """Apply one splash IPC message to the helper UI."""

    message_type = message.get("type")
    if message_type == "close":
        splash.close()
        app.quit()
        return
    if message_type in {"log", "status", "fatal"}:
        line = message.get("line", "")
        if line:
            splash.append_log(line)


def _handle_cancel_requested(*, app: QApplication, stream: TextIO) -> None:
    """Notify the parent process that the user canceled startup loading."""

    try:
        stream.write(encode_splash_helper_event({"type": "cancel"}) + "\n")
        stream.flush()
    except OSError:
        pass
    app.quit()


def _windows_process_is_alive(pid: int) -> bool:
    """Return whether one Windows process handle is still signaled as running."""

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(_SYNCHRONIZE, False, pid)
    if not handle:
        return False
    try:
        wait_result = kernel32.WaitForSingleObject(handle, 0)
        return bool(wait_result == _WAIT_TIMEOUT)
    finally:
        kernel32.CloseHandle(handle)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse helper command-line arguments."""

    parser = argparse.ArgumentParser(description="Run Sugar Substitute launch splash.")
    parser.add_argument("--parent-pid", type=int, required=True)
    parser.add_argument("--theme-mode", type=str, required=False)
    parser.add_argument("--accent-color", type=str, required=False)
    parser.add_argument("--backdrop-mode", type=str, required=False)
    return parser.parse_args(argv)


def _theme_mode_from_arg(raw_value: str | None) -> AppearanceThemeMode:
    """Return one appearance theme mode parsed from a helper CLI argument."""

    if raw_value is None:
        return AppearanceThemeMode.DARK
    try:
        return AppearanceThemeMode(raw_value)
    except ValueError:
        return AppearanceThemeMode.DARK


def _backdrop_mode_from_arg(raw_value: str | None) -> ShellBackdropMode | None:
    """Return one shell backdrop mode parsed from a helper CLI argument."""

    if raw_value is None:
        return ShellBackdropMode.MICA
    if raw_value == "none":
        return None
    if raw_value == ShellBackdropMode.ACRYLIC.value:
        return ShellBackdropMode.ACRYLIC
    return ShellBackdropMode.MICA


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "decode_splash_message",
    "encode_splash_helper_event",
    "main",
    "parent_process_is_alive",
]
