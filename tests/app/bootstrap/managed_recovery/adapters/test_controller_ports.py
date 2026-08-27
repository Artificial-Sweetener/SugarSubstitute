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

"""Exercise one managed-recovery adapter behavior owner."""

from __future__ import annotations
from typing import Any, cast
import pytest
from substitute.app.bootstrap import managed_recovery_adapters
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry

from .support import (
    _ExecutionRuntime,
    _ManagedState,
    _Submitter,
)


def test_managed_recovery_submitter_registers_for_startup_cleanup() -> None:
    """Managed recovery submitters should be retained by startup resources."""

    registry = StartupResourceRegistry()
    submitter = _Submitter()

    managed_recovery_adapters.register_managed_recovery_submitter(
        registry,
        cast(Any, submitter),
    )
    registry.shutdown_all()

    assert len(registry.startup_diagnostics_tasks) == 1
    assert submitter.close_calls == 1


def test_create_managed_recovery_controller_adapters_groups_concrete_ports() -> None:
    """Managed recovery controller adapters should expose concrete startup ports."""

    registry = StartupResourceRegistry()
    submitter = _Submitter()
    execution_runtime = _ExecutionRuntime(submitter)
    adapters = managed_recovery_adapters.create_managed_recovery_controller_adapters(
        startup_resources=registry,
        execution_runtime=execution_runtime,
        execution_dispatcher_factory=lambda: object(),
    )
    created_submitter = adapters.submitter_factory()
    adapters.register_submitter(created_submitter)

    assert isinstance(
        adapters,
        managed_recovery_adapters.ManagedRecoveryControllerAdapters,
    )
    assert created_submitter is cast(object, submitter)
    assert execution_runtime.submitter_calls == [
        {
            "name": "startup",
            "owner_id": "managed_compatibility_recovery",
        }
    ]
    assert len(registry.startup_diagnostics_tasks) == 1
    assert (
        adapters.cleanup_state
        is managed_recovery_adapters.cleanup_managed_recovery_state
    )
    assert (
        adapters.reconcile_owned_comfy_dependencies
        is managed_recovery_adapters.reconcile_owned_comfy_dependencies
    )
    assert adapters.confirmed_termination_status == (
        managed_recovery_adapters.confirmed_managed_recovery_termination_status()
    )


def test_cleanup_managed_recovery_state_uses_process_manager(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Managed cleanup adapter should delegate to the infrastructure process manager."""

    state = _ManagedState()
    cleanup_result = object()
    calls: list[object | None] = []

    def fake_kill(received_state: object | None) -> object:
        """Record the managed state passed to cleanup."""

        calls.append(received_state)
        return cleanup_result

    monkeypatch.setattr(
        "substitute.app.bootstrap.managed_recovery_adapters."
        "process_manager.kill_comfyui_state",
        fake_kill,
    )

    assert (
        managed_recovery_adapters.cleanup_managed_recovery_state(state)
        is cleanup_result
    )
    assert calls == [state]
