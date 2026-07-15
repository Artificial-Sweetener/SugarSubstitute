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

"""Launch the ready shell when startup is not managing ComfyUI."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.app.bootstrap.startup_trace import trace_mark, trace_span
from substitute.domain.onboarding import InstallationContext
from substitute.shared.logging.logger import get_logger, log_exception

_LOGGER = get_logger("app.bootstrap.no_comfy_ready_shell")


@dataclass(frozen=True)
class NoComfyReadyShellResult:
    """Updated shell/splash state after no-Comfy shell launch."""

    shell_frame: object
    splash: object | None


def launch_no_comfy_ready_shell(
    *,
    context: InstallationContext,
    splash: object | None,
    comfy_output_stream: object,
    shutdown_request: object,
    startup_timer: object,
    runtime_services: object,
    initial_shell_placement: object | None,
    initial_workspace: object | None,
    show_main_window: Callable[..., object],
    attach_gui_reload_command: Callable[[object], None],
) -> NoComfyReadyShellResult:
    """Close splash, show the shell directly, and attach reload commands."""

    if splash is not None:
        try:
            close = getattr(splash, "close")
            close()
        except Exception:
            log_exception(_LOGGER, "Failed to close launch splash")
        splash = None
    with trace_span("ready_shell.no_comfy.show_main_window"):
        shell_frame = show_main_window(
            context,
            comfy_output_stream=comfy_output_stream,
            shutdown_request=shutdown_request,
            startup_timer=startup_timer,
            runtime_services=runtime_services,
            initial_shell_placement=initial_shell_placement,
            initial_workspace=initial_workspace,
        )
    attach_gui_reload_command(shell_frame)
    trace_mark("ready_shell.no_comfy.shown")
    return NoComfyReadyShellResult(shell_frame=shell_frame, splash=splash)


def publish_no_comfy_ready_shell_result(
    result: NoComfyReadyShellResult,
    *,
    set_current_shell: Callable[[object], None],
) -> NoComfyReadyShellResult:
    """Publish no-Comfy shell state to startup shell reload coordination."""

    set_current_shell(result.shell_frame)
    return result


__all__ = [
    "NoComfyReadyShellResult",
    "launch_no_comfy_ready_shell",
    "publish_no_comfy_ready_shell_result",
]
