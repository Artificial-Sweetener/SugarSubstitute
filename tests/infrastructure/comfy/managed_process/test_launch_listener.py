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

"""Test managed-listener adoption and containment decisions."""

from __future__ import annotations

from pathlib import Path
import subprocess
import threading
from typing import Any
import pytest
from substitute.domain.onboarding import (
    ComfyEndpoint,
)
from substitute.infrastructure.comfy import (
    managed_launcher,
)
from substitute.infrastructure.comfy.managed_process_metadata import (
    ManagedProcessMetadata,
)
from substitute.infrastructure.comfy.managed_process_probe import (
    ManagedListenerProbeResult,
    ManagedListenerStatus,
)
from substitute.infrastructure.comfy.managed_process_registry import (
    ManagedProcessRegistry,
)
from substitute.infrastructure.comfy.managed_startup_monitor import (
    ManagedStartupReadinessResult,
)

from tests.infrastructure.comfy.managed_process.launch_support import (
    _record_termination,
    _use_integrated_manager_runtime,  # noqa: F401 - register imported autouse fixture.
    _write_launchable_workspace,
)
from tests.infrastructure.comfy.managed_process.threaded_task_support import (
    _managed_task_factory,
)


def test_background_start_reuses_healthy_owned_listener_without_spawning(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed startup should reuse a healthy owned listener instead of spawning again."""

    registry = ManagedProcessRegistry(tmp_path)
    metadata = registry.save(
        ManagedProcessMetadata(
            pid=999,
            host="127.0.0.1",
            port=8188,
            workspace_path=tmp_path / "comfyui",
        )
    )
    status_lines: list[str] = []
    monkeypatch.setattr(
        managed_launcher,
        "probe_managed_listener",
        lambda **kwargs: ManagedListenerProbeResult(
            status=ManagedListenerStatus.OWNED_HEALTHY,
            reason="healthy",
            listener_pid=999,
            metadata=metadata,
        ),
    )
    popen_calls: list[list[str]] = []

    def _fake_popen(command: list[str], **kwargs: Any) -> Any:
        popen_calls.append(command)
        return object()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    state = managed_launcher.start_managed_comfy_background(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=tmp_path / "comfyui",
        runtime_state_dir=tmp_path,
        on_status=status_lines.append,
        launch_task_factory=_managed_task_factory,
        process_pump_task_factory=_managed_task_factory,
    )
    state.wait_until_finished(timeout=2)

    assert state.proc is None
    assert state.metadata == metadata
    assert status_lines == ["Reusing the existing managed ComfyUI instance."]
    assert popen_calls == []


def test_background_start_returns_before_listener_probe_completes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed background startup should not run listener probing before returning."""

    probe_entered = threading.Event()
    release_probe = threading.Event()

    def probe_managed_listener(**_kwargs: object) -> ManagedListenerProbeResult:
        """Block inside the fake probe until the test confirms startup returned."""

        probe_entered.set()
        assert release_probe.wait(timeout=2)
        return ManagedListenerProbeResult(
            status=ManagedListenerStatus.ABSENT,
            reason="absent",
        )

    monkeypatch.setattr(
        managed_launcher,
        "probe_managed_listener",
        probe_managed_listener,
    )
    _write_launchable_workspace(tmp_path / "comfyui")
    monkeypatch.setattr(
        managed_launcher,
        "wait_for_managed_startup_ready",
        lambda **kwargs: ManagedStartupReadinessResult(ready=False),
    )

    class _SpawnedProcess:
        """Provide the minimal subprocess handle used by managed startup."""

        pid = 789
        stdout = None

    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: _SpawnedProcess(),
    )

    state = managed_launcher.start_managed_comfy_background(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=tmp_path / "comfyui",
        runtime_state_dir=tmp_path,
        launch_task_factory=_managed_task_factory,
        process_pump_task_factory=_managed_task_factory,
    )

    assert probe_entered.wait(timeout=2)
    assert state.is_finished is False
    release_probe.set()
    state.wait_until_finished(timeout=2)


def test_background_start_reaps_stale_owned_listener_before_spawn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed startup should terminate a stale owned listener before spawning again."""

    registry = ManagedProcessRegistry(tmp_path)
    stale_metadata = registry.save(
        ManagedProcessMetadata(
            pid=456,
            host="127.0.0.1",
            port=8188,
            workspace_path=tmp_path / "comfyui",
        )
    )
    probe_results = [
        ManagedListenerProbeResult(
            status=ManagedListenerStatus.OWNED_STALE,
            reason="stale",
            metadata=stale_metadata,
        ),
        ManagedListenerProbeResult(
            status=ManagedListenerStatus.ABSENT,
            reason="absent",
        ),
    ]
    monkeypatch.setattr(
        managed_launcher,
        "probe_managed_listener",
        lambda **kwargs: probe_results.pop(0),
    )
    killed_pids: list[int | None] = []
    monkeypatch.setattr(
        managed_launcher,
        "kill_managed_comfy_metadata",
        lambda metadata, **kwargs: _record_termination(
            killed_pids,
            None if metadata is None else metadata.pid,
        ),
    )
    _write_launchable_workspace(tmp_path / "comfyui")
    monkeypatch.setattr(
        managed_launcher,
        "wait_for_managed_startup_ready",
        lambda **kwargs: ManagedStartupReadinessResult(ready=False),
    )

    class _SpawnedProcess:
        """Provide the minimal subprocess handle used by managed startup."""

        pid = 789
        stdout = None

    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: _SpawnedProcess(),
    )

    state = managed_launcher.start_managed_comfy_background(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=tmp_path / "comfyui",
        runtime_state_dir=tmp_path,
        launch_task_factory=_managed_task_factory,
        process_pump_task_factory=_managed_task_factory,
    )
    state.wait_until_finished(timeout=2)

    assert killed_pids == [456]


def test_background_start_refuses_foreign_listener(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed startup should fail closed when a foreign process owns the endpoint."""

    log_lines: list[str] = []
    monkeypatch.setattr(
        managed_launcher,
        "probe_managed_listener",
        lambda **kwargs: ManagedListenerProbeResult(
            status=ManagedListenerStatus.FOREIGN,
            reason="foreign",
            listener_pid=777,
        ),
    )

    state = managed_launcher.start_managed_comfy_background(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=tmp_path / "comfyui",
        runtime_state_dir=tmp_path,
        on_log=log_lines.append,
        launch_task_factory=_managed_task_factory,
        process_pump_task_factory=_managed_task_factory,
    )
    state.wait_until_finished(timeout=2)

    assert state.proc is None
    assert any("foreign listener" in line for line in log_lines)
