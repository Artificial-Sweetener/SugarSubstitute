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

"""Test managed ComfyUI launch requests and runtime contracts."""

from __future__ import annotations

from pathlib import Path
from typing import cast
import pytest
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ManagedRuntimeConfiguration,
)
from substitute.infrastructure.comfy import (
    managed_launcher,
)
from substitute.infrastructure.comfy.managed_process_probe import (
    ManagedListenerProbeResult,
    ManagedListenerStatus,
)
from substitute.infrastructure.comfy.managed_startup_monitor import (
    ManagedStartupReadinessResult,
)
from substitute.infrastructure.comfy.managed_validation import (
    workspace_main_path,
    workspace_python_path,
)
from substitute.infrastructure.onboarding.file_managed_runtime_repository import (
    FileManagedRuntimeConfigurationRepository,
)

from tests.infrastructure.comfy.managed_process.launch_support import (
    _record_launch_request,
    _use_integrated_manager_runtime,  # noqa: F401 - register imported autouse fixture.
    _write_launchable_workspace,
)
from tests.infrastructure.comfy.managed_process.threaded_task_support import (
    _managed_task_factory,
)


def test_normal_managed_launch_never_runs_setup_reconciliation(tmp_path: Path) -> None:
    """Ordinary launch should start the installed runtime without mutating it."""

    workspace = _write_launchable_workspace(tmp_path / "comfyui")
    python_executable = workspace_python_path(workspace)

    resolved = managed_launcher._resolve_launch_python(
        workspace=workspace,
        python_executable=None,
    )

    assert resolved == python_executable
    source = Path(managed_launcher.__file__).read_text(encoding="utf-8")
    assert "ensure_managed_comfy_setup" not in source
    assert "prepare_attached_comfy_setup" not in source
    assert "startup_revalidation" not in source


def test_normal_managed_launch_fails_closed_when_workspace_is_incomplete(
    tmp_path: Path,
) -> None:
    """Ordinary launch should route incomplete setup to recovery without mutation."""

    workspace = tmp_path / "comfyui"

    with pytest.raises(FileNotFoundError) as error:
        managed_launcher._resolve_launch_python(
            workspace=workspace,
            python_executable=None,
        )

    assert error.value.args == (workspace_main_path(workspace),)
    assert workspace.exists() is False


def test_background_start_uses_utf8_for_managed_output_stream(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed background launch should preserve raw Comfy stdout control codes."""

    monkeypatch.setattr(
        managed_launcher,
        "probe_managed_listener",
        lambda **kwargs: ManagedListenerProbeResult(
            status=ManagedListenerStatus.ABSENT,
            reason="absent",
        ),
    )
    _write_launchable_workspace(tmp_path / "comfyui")
    monkeypatch.setattr(
        managed_launcher,
        "wait_for_managed_startup_ready",
        lambda **kwargs: ManagedStartupReadinessResult(ready=False),
    )
    observed_request: dict[str, object] = {}

    class _SpawnedProcess:
        """Provide the minimal subprocess handle used by managed startup."""

        pid = 790
        stdout = None

        def poll(self) -> int | None:
            """Behave like a still-running process handle for lifecycle tests."""

            return None

    monkeypatch.setattr(
        managed_launcher,
        "launch_managed_process",
        lambda **kwargs: _record_launch_request(
            observed_request,
            kwargs["request"],
            _SpawnedProcess(),
        ),
    )

    state = managed_launcher.start_managed_comfy_background(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=tmp_path / "comfyui",
        runtime_state_dir=tmp_path,
        launch_task_factory=_managed_task_factory,
        process_pump_task_factory=_managed_task_factory,
    )
    state.wait_until_finished(timeout=2)

    assert observed_request["capture_output"] is True
    command = cast(tuple[str, ...], observed_request["command"])
    assert command[-1] == "--enable-manager"
    assert isinstance(observed_request["env"], dict)
    env = cast(dict[str, str], observed_request["env"])
    assert env["PYTHONIOENCODING"] == "utf-8"
    assert env["SUGARSUBSTITUTE_SKIP_TTS_INSTALLER"] == "1"
    assert env["CM_USE_PYGIT2"] == "1"


def test_background_start_launches_force_cpu_runtime_with_comfy_cpu_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A managed CPU-only Torch runtime must launch ComfyUI in CPU mode."""

    workspace = _write_launchable_workspace(tmp_path / "comfyui")
    FileManagedRuntimeConfigurationRepository(tmp_path).save(
        ManagedRuntimeConfiguration(
            workspace_path=str(workspace.resolve()),
            force_cpu_mode=True,
        )
    )
    monkeypatch.setattr(
        managed_launcher,
        "probe_managed_listener",
        lambda **kwargs: ManagedListenerProbeResult(
            status=ManagedListenerStatus.ABSENT,
            reason="absent",
        ),
    )
    monkeypatch.setattr(
        managed_launcher,
        "wait_for_managed_startup_ready",
        lambda **kwargs: ManagedStartupReadinessResult(ready=False),
    )
    observed_request: dict[str, object] = {}

    class _SpawnedProcess:
        """Provide the minimal process handle used by managed startup."""

        pid = 791
        stdout = None

        def poll(self) -> int | None:
            """Behave like a still-running managed process."""

            return None

    monkeypatch.setattr(
        managed_launcher,
        "launch_managed_process",
        lambda **kwargs: _record_launch_request(
            observed_request,
            kwargs["request"],
            _SpawnedProcess(),
        ),
    )

    state = managed_launcher.start_managed_comfy_background(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=workspace,
        runtime_state_dir=tmp_path,
        launch_task_factory=_managed_task_factory,
        process_pump_task_factory=_managed_task_factory,
    )
    state.wait_until_finished(timeout=2)

    command = cast(tuple[str, ...], observed_request["command"])
    assert "--cpu" in command


@pytest.mark.parametrize("install_target", ["windows_cpu", "linux_cpu"])
def test_background_start_preserves_historical_cpu_target_launch_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    install_target: str,
) -> None:
    """Historical CPU targets must retain ComfyUI CPU mode after an update."""

    workspace = _write_launchable_workspace(tmp_path / "comfyui")
    FileManagedRuntimeConfigurationRepository(tmp_path).save(
        ManagedRuntimeConfiguration(
            workspace_path=str(workspace.resolve()),
            install_target=install_target,
            force_cpu_mode=False,
        )
    )
    monkeypatch.setattr(
        managed_launcher,
        "probe_managed_listener",
        lambda **kwargs: ManagedListenerProbeResult(
            status=ManagedListenerStatus.ABSENT,
            reason="absent",
        ),
    )
    monkeypatch.setattr(
        managed_launcher,
        "wait_for_managed_startup_ready",
        lambda **kwargs: ManagedStartupReadinessResult(ready=False),
    )
    observed_request: dict[str, object] = {}

    class _SpawnedProcess:
        """Provide the minimal process handle used by managed startup."""

        pid = 792
        stdout = None

        def poll(self) -> int | None:
            """Behave like a still-running managed process."""

            return None

    monkeypatch.setattr(
        managed_launcher,
        "launch_managed_process",
        lambda **kwargs: _record_launch_request(
            observed_request,
            kwargs["request"],
            _SpawnedProcess(),
        ),
    )

    state = managed_launcher.start_managed_comfy_background(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=workspace,
        runtime_state_dir=tmp_path,
        launch_task_factory=_managed_task_factory,
        process_pump_task_factory=_managed_task_factory,
    )
    state.wait_until_finished(timeout=2)

    command = cast(tuple[str, ...], observed_request["command"])
    assert "--cpu" in command


def test_background_start_traces_managed_startup_phases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed background launch should trace the work hidden behind activation."""

    events: list[str] = []

    class _TraceSpan:
        """Record deterministic span entry and exit events."""

        def __init__(self, name: str) -> None:
            self._name = name

        def __enter__(self) -> None:
            events.append(f"span:start:{self._name}")

        def __exit__(self, *_exc: object) -> None:
            events.append(f"span:end:{self._name}")

    def trace_mark(event: str, **_fields: object) -> None:
        """Record one trace mark."""

        events.append(event)

    def trace_span(event: str, **_fields: object) -> _TraceSpan:
        """Record one trace span."""

        return _TraceSpan(event)

    monkeypatch.setattr(managed_launcher, "trace_mark", trace_mark)
    monkeypatch.setattr(managed_launcher, "trace_span", trace_span)
    monkeypatch.setattr(
        managed_launcher,
        "probe_managed_listener",
        lambda **kwargs: ManagedListenerProbeResult(
            status=ManagedListenerStatus.ABSENT,
            reason="absent",
        ),
    )
    _write_launchable_workspace(tmp_path / "comfyui")
    monkeypatch.setattr(
        managed_launcher,
        "wait_for_managed_startup_ready",
        lambda **kwargs: ManagedStartupReadinessResult(ready=True),
    )

    class _SpawnedProcess:
        """Provide the minimal subprocess handle used by managed startup."""

        pid = 790
        stdout = None

        def poll(self) -> int | None:
            """Behave like a still-running process handle for lifecycle tests."""

            return None

    monkeypatch.setattr(
        managed_launcher,
        "launch_managed_process",
        lambda **kwargs: _record_launch_request(
            {},
            kwargs["request"],
            _SpawnedProcess(),
        ),
    )

    state = managed_launcher.start_managed_comfy_background(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=tmp_path / "comfyui",
        runtime_state_dir=tmp_path,
        launch_task_factory=_managed_task_factory,
        process_pump_task_factory=_managed_task_factory,
    )
    state.wait_until_finished(timeout=2)

    assert events == [
        "managed_comfy.startup_task.start",
        "span:start:managed_comfy.resolve_listener",
        "span:end:managed_comfy.resolve_listener",
        "span:start:managed_comfy.resolve_launch_workspace",
        "span:end:managed_comfy.resolve_launch_workspace",
        "span:start:managed_comfy.launch_process",
        "span:end:managed_comfy.launch_process",
        "managed_comfy.process_launched",
        "span:start:managed_comfy.wait_ready",
        "span:end:managed_comfy.wait_ready",
        "managed_comfy.wait_ready.result",
    ]
