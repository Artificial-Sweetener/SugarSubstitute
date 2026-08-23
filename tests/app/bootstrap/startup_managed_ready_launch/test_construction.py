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

"""Test managed-ready launch construction contracts."""

from __future__ import annotations

from pathlib import Path

from substitute.app.bootstrap.startup_managed_ready_launch import (
    StartupManagedReadyLaunchRuntime,
    create_startup_managed_ready_launch_runtime,
)
from substitute.app.bootstrap.startup_managed_ready_runtime import (
    StartupManagedReadyRuntimeResources,
)
from substitute.app.bootstrap.startup_managed_ready_state import (
    StartupManagedReadyStateBundle,
)
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
from substitute.app.bootstrap.startup_timing import StartupTimer


from .launch_support import (
    _Clock,
    _context,
    _ports,
)


def test_managed_ready_launch_runtime_creates_state_and_resources(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should pair state with runtime resources."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )

    assert isinstance(launch_runtime, StartupManagedReadyLaunchRuntime)
    assert isinstance(launch_runtime.state, StartupManagedReadyStateBundle)
    assert isinstance(launch_runtime.runtime, StartupManagedReadyRuntimeResources)


def test_managed_ready_launch_runtime_binds_trace_fields(tmp_path: Path) -> None:
    """Managed-ready launch assembly should bind state into trace fields."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )

    provider = launch_runtime.create_ready_trace_fields(
        startup_cancelled=lambda: True,
        shell_frame_present=lambda: False,
        provisional_restore_projection_present=lambda: True,
    )
    launch_runtime.state.ready_state.minimum_shell_ready = True
    launch_runtime.state.readiness_controller_state.readiness_attempts = 2
    launch_runtime.state.managed_compatibility_recovery_state.recovery_attempted = True
    launch_runtime.state.pre_show_restore_projection_state.pending = True

    fields = provider()

    assert fields["startup_cancelled"] is True
    assert fields["shell_frame_present"] is False
    assert fields["minimum_shell_ready"] is True
    assert fields["readiness_attempts"] == 2
    assert fields["managed_compatibility_recovery_attempted"] is True
    assert fields["pre_show_restore_projection_pending"] is True
    assert fields["provisional_restore_projection_present"] is True
