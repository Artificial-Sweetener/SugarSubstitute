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

"""Test managed-ready target activation and failure-queue contracts."""

from __future__ import annotations

from pathlib import Path

from substitute.app.bootstrap.startup_managed_ready_launch import (
    create_startup_managed_ready_launch_runtime,
)
from substitute.app.bootstrap.ready_shell_controller import (
    ReadyShellFailureQueue,
    ReadyShellTargetActivationTask,
)
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
from substitute.app.bootstrap.startup_timing import StartupTimer


from .launch_support import (
    _Clock,
    _context,
    _ports,
)


def test_managed_ready_launch_runtime_creates_failure_queue(tmp_path: Path) -> None:
    """Managed-ready launch assembly should expose failure queue construction."""

    comfy_state = object()
    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: comfy_state,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )

    failure_queue = launch_runtime.create_failure_queue(
        is_startup_cancelled=lambda: False,
        mark_startup_cancelled=lambda: None,
        managed_comfy_state=lambda: comfy_state,
        splash=lambda: None,
        cleanup=lambda: None,
        quit_app=lambda: None,
        trace_fields=lambda: {},
        scheduler=lambda _delay, _callback: None,
    )

    assert isinstance(failure_queue, ReadyShellFailureQueue)


def test_managed_ready_launch_runtime_binds_target_activation_state(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should bind ready state into activation."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )
    comfy_states: list[object | None] = []
    task = launch_runtime.create_target_activation_task(
        startup_cancelled=lambda: False,
        splash=lambda: object(),
        comfy_output_stream=object(),
        set_comfy_state=comfy_states.append,
        trace_fields=lambda: {},
    )

    result = task.activate()

    assert isinstance(task, ReadyShellTargetActivationTask)
    assert result.started is True
    assert launch_runtime.state.ready_state.comfy_activation_started is True
    assert comfy_states == [result.comfy_state]
