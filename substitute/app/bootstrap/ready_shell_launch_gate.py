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

"""Gate ready-shell launch attempts and emit prompt-safe startup traces."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.app.bootstrap.startup_trace import trace_mark


@dataclass(slots=True)
class ReadyShellLaunchGateState:
    """Track whether the ready-shell launch sequence already started."""

    launch_started: bool = False


def try_begin_ready_shell_launch(
    state: ReadyShellLaunchGateState,
    *,
    startup_cancelled: bool,
    shell_frame_present: bool,
    no_comfy: bool,
    target_mode: object,
    target_host: str,
    target_port: int,
) -> bool:
    """Return whether ready-shell launch may start, updating launch state."""

    trace_mark(
        "ready_shell.launch.enter",
        startup_cancelled=startup_cancelled,
        ready_shell_launch_started=state.launch_started,
        shell_frame_present=shell_frame_present,
        no_comfy=no_comfy,
        target_mode=target_mode,
        target_host=target_host,
        target_port=target_port,
    )
    if startup_cancelled or state.launch_started or shell_frame_present:
        trace_mark(
            "ready_shell.launch.skipped",
            startup_cancelled=startup_cancelled,
            ready_shell_launch_started=state.launch_started,
            shell_frame_present=shell_frame_present,
        )
        return False
    state.launch_started = True
    return True


__all__ = [
    "ReadyShellLaunchGateState",
    "try_begin_ready_shell_launch",
]
