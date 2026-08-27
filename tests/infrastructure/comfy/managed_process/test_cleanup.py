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

"""Tests for one managed ComfyUI process behavior owner."""

from __future__ import annotations

from __future__ import annotations
from pathlib import Path
from typing import cast
import pytest
from substitute.app.bootstrap import lifecycle
from substitute.app.bootstrap.lifecycle import ManagedComfyCleanupOutcome
from substitute.infrastructure.comfy import (
    managed_launcher,
    process_manager,
)
from substitute.infrastructure.comfy.managed_process_metadata import (
    ManagedProcessMetadata,
)
from substitute.infrastructure.comfy.managed_process_registry import (
    ManagedProcessRegistry,
)
from substitute.infrastructure.comfy.managed_process_containment import (
    ManagedProcessHandle,
)
from substitute.infrastructure.comfy.managed_shutdown import (
    ManagedProcessTerminationResult,
    ManagedProcessTerminationStatus,
)


class _FakeProcess:
    """Provide the minimal Popen surface used by lifecycle tests."""

    def __init__(self, pid: int, returncode: int | None = None) -> None:
        self.pid = pid
        self._returncode = returncode

    def poll(self) -> int | None:
        """Return the configured process exit status."""

        return self._returncode


def _managed_state(
    tmp_path: Path,
    *,
    process: ManagedProcessHandle | None,
    metadata: ManagedProcessMetadata | None,
) -> managed_launcher.ManagedComfyState:
    """Build one concrete managed state for lifecycle tests."""

    state = managed_launcher.ManagedComfyState(
        registry=ManagedProcessRegistry(tmp_path)
    )
    state.proc = process
    state.metadata = metadata
    state.containment_handle = None
    state.containment_mode = None if metadata is None else metadata.containment_mode
    return state


def test_cleanup_handler_requests_stop_and_kills_owned_process_once(
    tmp_path: Path,
) -> None:
    """Cleanup should be idempotent and terminate the owned process only once."""

    state = _managed_state(
        tmp_path,
        process=cast(ManagedProcessHandle, _FakeProcess(200)),
        metadata=ManagedProcessMetadata(
            pid=200,
            host="127.0.0.1",
            port=8188,
            workspace_path=tmp_path / "comfyui",
        ),
    )
    killed_states: list[managed_launcher.ManagedComfyState | None] = []
    cleanup = lifecycle.create_cleanup_handler(
        lambda: state,
        lambda current_state: _record_cleanup_state(killed_states, current_state),
    )

    first_result = cleanup()
    second_result = cleanup()

    assert state.stop_requested is True
    assert killed_states == [state]
    assert first_result.cleanup_ran is True
    assert first_result.outcome is ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS
    assert second_result == first_result


def test_cleanup_handler_retries_after_uncertain_result(tmp_path: Path) -> None:
    """Retry should re-run cleanup after an uncertain result instead of caching it."""

    state = _managed_state(
        tmp_path,
        process=cast(ManagedProcessHandle, _FakeProcess(200)),
        metadata=ManagedProcessMetadata(
            pid=200,
            host="127.0.0.1",
            port=8188,
            workspace_path=tmp_path / "comfyui",
        ),
    )
    outcomes = [
        ManagedProcessTerminationStatus.TERMINATION_UNCONFIRMED,
        ManagedProcessTerminationStatus.TERMINATED_CONFIRMED,
    ]
    cleanup = lifecycle.create_cleanup_handler(
        lambda: state,
        lambda current_state: _record_cleanup_state(
            [],
            current_state,
            termination_status=outcomes.pop(0),
        ),
    )

    first_result = cleanup()
    second_result = cleanup()

    assert first_result.outcome is ManagedComfyCleanupOutcome.UNCERTAIN_SUCCESS
    assert second_result.outcome is ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS


def test_cleanup_handler_skip_future_cleanup_returns_bypass_result(
    tmp_path: Path,
) -> None:
    """Force-close should bypass any later cleanup hook execution."""

    state = _managed_state(
        tmp_path,
        process=cast(ManagedProcessHandle, _FakeProcess(200)),
        metadata=ManagedProcessMetadata(
            pid=200,
            host="127.0.0.1",
            port=8188,
            workspace_path=tmp_path / "comfyui",
        ),
    )
    cleanup = lifecycle.create_cleanup_handler(
        lambda: state,
        lambda current_state: _record_cleanup_state([], current_state),
    )

    cleanup.skip_future_cleanup()
    result = cleanup()

    assert result.cleanup_ran is False
    assert result.outcome is ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED


def test_cleanup_handler_without_managed_state_maps_to_no_action_required() -> None:
    """Missing managed state should map to the lifecycle no-action outcome."""

    cleanup = lifecycle.create_cleanup_handler(
        lambda: None,
        lambda current_state: _record_cleanup_state([], current_state),
    )

    result = cleanup()

    assert result.outcome is ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED


def test_cleanup_handler_maps_termination_timeout_to_failure(tmp_path: Path) -> None:
    """Termination command failure should map to the lifecycle failure outcome."""

    state = _managed_state(
        tmp_path,
        process=cast(ManagedProcessHandle, _FakeProcess(200)),
        metadata=ManagedProcessMetadata(
            pid=200,
            host="127.0.0.1",
            port=8188,
            workspace_path=tmp_path / "comfyui",
        ),
    )
    cleanup = lifecycle.create_cleanup_handler(
        lambda: state,
        lambda current_state: _record_cleanup_state(
            [],
            current_state,
            termination_status=ManagedProcessTerminationStatus.TERMINATION_COMMAND_FAILED,
        ),
    )

    result = cleanup()

    assert result.outcome is ManagedComfyCleanupOutcome.FAILURE


def test_cleanup_handler_maps_unexpected_exception_to_failure(tmp_path: Path) -> None:
    """Unexpected cleanup exceptions should map to the lifecycle failure outcome."""

    state = _managed_state(
        tmp_path,
        process=cast(ManagedProcessHandle, _FakeProcess(200)),
        metadata=ManagedProcessMetadata(
            pid=200,
            host="127.0.0.1",
            port=8188,
            workspace_path=tmp_path / "comfyui",
        ),
    )

    def _raise_failure(
        current_state: managed_launcher.ManagedComfyState | None,
    ) -> process_manager.ManagedComfyStateCleanupResult:
        _ = current_state
        raise RuntimeError("boom")

    cleanup = lifecycle.create_cleanup_handler(lambda: state, _raise_failure)

    result = cleanup()

    assert result.outcome is ManagedComfyCleanupOutcome.FAILURE


def test_kill_comfyui_state_clears_registry_when_process_dies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """State-based cleanup should clear ownership metadata after a successful kill."""

    registry = ManagedProcessRegistry(tmp_path)
    metadata = registry.save(
        ManagedProcessMetadata(
            pid=321,
            host="127.0.0.1",
            port=8188,
            workspace_path=tmp_path / "comfyui",
        )
    )
    state = managed_launcher.ManagedComfyState(registry=registry)
    state.metadata = metadata
    state.containment_mode = metadata.containment_mode
    monkeypatch.setattr(
        process_manager,
        "kill_managed_comfy_metadata",
        lambda metadata, **kwargs: ManagedProcessTerminationResult(
            status=ManagedProcessTerminationStatus.TERMINATED_CONFIRMED,
            pid=None if metadata is None else metadata.pid,
            attempted=True,
            user_safe_detail="Shutdown finished cleanly.",
            diagnostic_detail="terminated",
        ),
    )

    result = process_manager.kill_comfyui_state(state)

    assert registry.load() is None
    assert result.registry_cleared is True
    assert (
        result.termination_status
        is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
    )


def test_kill_comfyui_state_keeps_registry_when_termination_is_not_verified(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """State cleanup should preserve ownership metadata when verification fails."""

    registry = ManagedProcessRegistry(tmp_path)
    metadata = registry.save(
        ManagedProcessMetadata(
            pid=654,
            host="127.0.0.1",
            port=8188,
            workspace_path=tmp_path / "comfyui",
        )
    )
    state = managed_launcher.ManagedComfyState(registry=registry)
    state.metadata = metadata
    state.containment_mode = metadata.containment_mode
    monkeypatch.setattr(
        process_manager,
        "kill_managed_comfy_metadata",
        lambda metadata, **kwargs: ManagedProcessTerminationResult(
            status=ManagedProcessTerminationStatus.TERMINATION_UNCONFIRMED,
            pid=None if metadata is None else metadata.pid,
            attempted=True,
            user_safe_detail=(
                "Shutdown could not be confirmed before the verification timeout."
            ),
            diagnostic_detail="SUCCESS: sent termination",
            verification_timed_out=True,
        ),
    )

    result = process_manager.kill_comfyui_state(state)

    assert registry.load() == metadata
    assert result.registry_cleared is False
    assert (
        result.termination_status
        is ManagedProcessTerminationStatus.TERMINATION_UNCONFIRMED
    )
    assert result.termination is not None
    assert result.termination.verification_timed_out is True


def _record_cleanup_state(
    calls: list[managed_launcher.ManagedComfyState | None],
    current_state: managed_launcher.ManagedComfyState | None,
    *,
    termination_status: ManagedProcessTerminationStatus = (
        ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
    ),
) -> process_manager.ManagedComfyStateCleanupResult:
    """Record one cleanup request and return a successful typed result."""

    calls.append(current_state)
    metadata = None if current_state is None else current_state.metadata
    process = None if current_state is None else current_state.proc
    pid = (
        process.pid
        if process is not None
        else (metadata.pid if metadata is not None else None)
    )
    host = metadata.host if metadata is not None else None
    port = metadata.port if metadata is not None else None
    workspace = metadata.workspace_path if metadata is not None else None
    return process_manager.ManagedComfyStateCleanupResult(
        pid=pid,
        host=host,
        port=port,
        workspace=workspace,
        managed_resource_present=current_state is not None,
        live_process_present=process is not None,
        metadata_present=metadata is not None,
        used_persisted_metadata=False,
        termination_attempted=True,
        registry_cleared=False,
        termination=ManagedProcessTerminationResult(
            status=termination_status,
            pid=pid,
            attempted=True,
            verification_timed_out=(
                termination_status
                is ManagedProcessTerminationStatus.TERMINATION_UNCONFIRMED
            ),
            user_safe_detail=(
                "Shutdown finished cleanly."
                if termination_status
                is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
                else "Shutdown could not be confirmed before the verification timeout."
            ),
            diagnostic_detail="terminated",
        ),
        termination_status=termination_status,
        user_safe_detail=(
            "Shutdown finished cleanly."
            if termination_status
            is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
            else "Shutdown could not be confirmed before the verification timeout."
        ),
        diagnostic_detail="terminated",
    )
