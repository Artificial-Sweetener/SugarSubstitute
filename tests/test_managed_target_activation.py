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

"""Tests for managed Comfy target startup activation."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, cast

import pytest

from substitute.app.bootstrap import managed_target_activation
from substitute.application.comfy_startup_diagnostics import (
    ComfyStartupDiagnosticsCollector,
)
from substitute.domain.comfy_startup_diagnostics import (
    ComfyStartupIncident,
    ComfyStartupIncidentKind,
    ComfyStartupIncidentSeverity,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.infrastructure.comfy import process_manager
from substitute.infrastructure.comfy.managed_process_registry import (
    ManagedProcessRegistry,
)
from substitute.infrastructure.comfy.managed_startup_monitor import (
    ManagedStartupReadinessResult,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ACTIVATION_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "managed_target_activation.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
FORBIDDEN_ACTIVATION_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "subprocess",
)


def test_activate_target_starts_launch_owned_managed_workspace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Launch-owned targets should start managed Comfy and route startup output."""

    captured: dict[str, object] = {}
    fake_state = process_manager.ManagedComfyState(
        registry=ManagedProcessRegistry(tmp_path)
    )

    def _start_managed(**kwargs: object) -> process_manager.ManagedComfyState:
        captured.update(kwargs)
        cast(Any, kwargs["on_log"])("log line")
        cast(Any, kwargs["on_status"])("status line")
        return fake_state

    monkeypatch.setattr(
        process_manager,
        "start_comfyui_background_managed",
        _start_managed,
    )
    splash = _Splash()
    stream = _Stream()
    diagnostics = _Diagnostics()
    context = _context(tmp_path, launch_owned=True)

    state = managed_target_activation.activate_target(
        installation_context=context,
        splash=cast(Any, splash),
        comfy_output_stream=stream,
        startup_diagnostics=cast(ComfyStartupDiagnosticsCollector, diagnostics),
        launch_task_factory=cast(Any, _task_factory),
        process_pump_task_factory=cast(Any, _task_factory),
    )

    assert state is fake_state
    assert captured["endpoint"] == context.comfy_target.endpoint
    assert captured["workspace"] == tmp_path / "ComfyUI"
    assert captured["runtime_state_dir"] == context.runtime_state_dir
    assert captured["diagnostics"] is diagnostics
    assert captured["launch_task_factory"] is _task_factory
    assert captured["process_pump_task_factory"] is _task_factory
    assert splash.lines == [
        "Activating managed_local Comfy target at 127.0.0.1:8188.",
        "log line",
        "status line",
    ]
    assert stream.lines == [
        "Activating managed_local Comfy target at 127.0.0.1:8188.",
        "log line",
        "status line",
    ]
    assert diagnostics.lines == ["log line", "status line"]


def test_activate_target_skips_non_launch_owned_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Attached targets should log activation context without spawning Comfy."""

    starts: list[str] = []
    monkeypatch.setattr(
        process_manager,
        "start_comfyui_background_managed",
        lambda **_kwargs: starts.append("start"),
    )
    splash = _Splash()
    stream = _Stream()

    state = managed_target_activation.activate_target(
        installation_context=_context(tmp_path, launch_owned=False),
        splash=cast(Any, splash),
        comfy_output_stream=stream,
        startup_diagnostics=cast(ComfyStartupDiagnosticsCollector, _Diagnostics()),
        launch_task_factory=cast(Any, _task_factory),
        process_pump_task_factory=cast(Any, _task_factory),
    )

    assert state is None
    assert starts == []
    assert splash.lines == ["Activating managed_local Comfy target at 127.0.0.1:8188."]
    assert stream.lines == ["Activating managed_local Comfy target at 127.0.0.1:8188."]


def test_activate_target_routes_activation_line_without_splash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Pre-theme activation should not require a visible splash reference."""

    fake_state = process_manager.ManagedComfyState(
        registry=ManagedProcessRegistry(tmp_path)
    )
    monkeypatch.setattr(
        process_manager,
        "start_comfyui_background_managed",
        lambda **_kwargs: fake_state,
    )
    stream = _Stream()

    state = managed_target_activation.activate_target(
        installation_context=_context(tmp_path, launch_owned=True),
        splash=None,
        comfy_output_stream=stream,
        startup_diagnostics=cast(ComfyStartupDiagnosticsCollector, _Diagnostics()),
        launch_task_factory=cast(Any, _task_factory),
        process_pump_task_factory=cast(Any, _task_factory),
    )

    assert state is fake_state
    assert stream.lines == ["Activating managed_local Comfy target at 127.0.0.1:8188."]


def test_activate_target_detaches_unresponsive_splash_after_first_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed output should stop retrying a splash endpoint that has gone away."""

    fake_state = process_manager.ManagedComfyState(
        registry=ManagedProcessRegistry(tmp_path)
    )

    def _start_managed(**kwargs: object) -> process_manager.ManagedComfyState:
        """Emit two output records through the activation-owned callbacks."""

        cast(Any, kwargs["on_log"])("first output")
        cast(Any, kwargs["on_log"])("second output")
        return fake_state

    monkeypatch.setattr(
        process_manager,
        "start_comfyui_background_managed",
        _start_managed,
    )
    splash = _FailingAfterActivationSplash()
    stream = _Stream()

    state = managed_target_activation.activate_target(
        installation_context=_context(tmp_path, launch_owned=True),
        splash=cast(Any, splash),
        comfy_output_stream=stream,
        startup_diagnostics=cast(ComfyStartupDiagnosticsCollector, _Diagnostics()),
        launch_task_factory=cast(Any, _task_factory),
        process_pump_task_factory=cast(Any, _task_factory),
    )

    assert state is fake_state
    assert splash.lines == ["Activating managed_local Comfy target at 127.0.0.1:8188."]
    assert splash.failure_count == 1
    assert stream.lines == [
        "Activating managed_local Comfy target at 127.0.0.1:8188.",
        "first output",
        "second output",
    ]


def test_collect_and_fan_out_output_survives_classification_failure() -> None:
    """Output routing should still reach visible sinks if diagnostics fail."""

    splash = _Splash()
    stream = _Stream()

    managed_target_activation.collect_and_fan_out_comfy_output(
        startup_diagnostics=cast(
            ComfyStartupDiagnosticsCollector, _FailingDiagnostics()
        ),
        splash=cast(Any, splash),
        comfy_output_stream=stream,
        line="backend output",
    )

    assert splash.lines == ["backend output"]
    assert stream.lines == ["backend output"]


def test_collect_and_fan_out_output_mirrors_harness_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Harness diagnostics should persist managed Comfy output without UI access."""

    mirror_path = tmp_path / "diagnostics" / "managed-comfy.log"
    monkeypatch.setenv(
        "SUGAR_SUBSTITUTE_STARTUP_HARNESS_COMFY_OUTPUT_LOG",
        str(mirror_path),
    )
    managed_target_activation.collect_and_fan_out_comfy_output(
        startup_diagnostics=cast(ComfyStartupDiagnosticsCollector, _Diagnostics()),
        splash=None,
        comfy_output_stream=_Stream(),
        line="SugarCubes cube library diagnostic event=example ready=True",
    )

    assert (
        mirror_path.read_text(encoding="utf-8")
        == "SugarCubes cube library diagnostic event=example ready=True\n"
    )


def test_collect_and_fan_out_output_mirrors_harness_timeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Harness timeline diagnostics should timestamp managed Comfy output."""

    timeline_path = tmp_path / "diagnostics" / "managed-comfy-timeline.jsonl"
    monkeypatch.setenv(
        "SUGAR_SUBSTITUTE_STARTUP_HARNESS_COMFY_OUTPUT_TIMELINE",
        str(timeline_path),
    )

    managed_target_activation.collect_and_fan_out_comfy_output(
        startup_diagnostics=cast(ComfyStartupDiagnosticsCollector, _Diagnostics()),
        splash=None,
        comfy_output_stream=_Stream(),
        line="Starting server",
    )

    records = [
        json.loads(line)
        for line in timeline_path.read_text(encoding="utf-8").splitlines()
    ]
    assert records == [
        {
            "event": "managed_comfy_output",
            "monotonicNs": records[0]["monotonicNs"],
            "elapsedMs": records[0]["elapsedMs"],
            "line": "Starting server",
        }
    ]
    assert isinstance(records[0]["monotonicNs"], int)
    assert isinstance(records[0]["elapsedMs"], float)


def test_collect_and_fan_out_output_records_harness_fanout_timing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Harness fanout timing should be mirrored at managed startup markers."""

    log_path = tmp_path / "diagnostics" / "managed-comfy.log"
    timeline_path = tmp_path / "diagnostics" / "managed-comfy-timeline.jsonl"
    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    monkeypatch.setenv(
        "SUGAR_SUBSTITUTE_STARTUP_HARNESS_COMFY_OUTPUT_LOG",
        str(log_path),
    )
    monkeypatch.setenv(
        "SUGAR_SUBSTITUTE_STARTUP_HARNESS_COMFY_OUTPUT_TIMELINE",
        str(timeline_path),
    )
    monkeypatch.setattr(managed_target_activation, "_harness_fanout_record_count", 0)
    monkeypatch.setattr(managed_target_activation, "_harness_fanout_total_ms", 0.0)
    monkeypatch.setattr(managed_target_activation, "_harness_fanout_max_ms", 0.0)
    stream = _Stream()

    managed_target_activation.collect_and_fan_out_comfy_output(
        startup_diagnostics=cast(ComfyStartupDiagnosticsCollector, _Diagnostics()),
        splash=None,
        comfy_output_stream=stream,
        line="Starting server",
    )

    log_lines = log_path.read_text(encoding="utf-8").splitlines()
    assert log_lines[0] == "Starting server"
    assert log_lines[1].startswith(
        "Substitute startup diagnostic event=managed_output_fanout_timing "
    )
    assert "record_count=1" in log_lines[1]
    assert "marker=starting_server" in log_lines[1]
    assert stream.lines == ["Starting server"]

    timeline_lines = timeline_path.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in timeline_lines]
    assert [record["line"] for record in records] == [log_lines[0], log_lines[1]]


def test_fan_out_splash_and_shell_output_tolerates_disposed_splash() -> None:
    """Disposed splash widgets should not block shell output history."""

    stream = _Stream()

    managed_target_activation.fan_out_splash_and_shell_output(
        splash=cast(Any, _DisposedSplash()),
        comfy_output_stream=stream,
        line="late output",
    )

    assert stream.lines == ["late output"]


def test_fan_out_splash_and_shell_output_tolerates_disposed_shell_stream() -> None:
    """Disposed shell output streams should not break managed output fan-out."""

    splash = _Splash()

    managed_target_activation.fan_out_splash_and_shell_output(
        splash=cast(Any, splash),
        comfy_output_stream=_DisposedStream(),
        line="late output",
    )

    assert splash.lines == ["late output"]


def test_managed_startup_fatal_incident_reads_state_result() -> None:
    """Managed fatal incident lookup should read the process startup result."""

    incident = ComfyStartupIncident(
        kind=ComfyStartupIncidentKind.PROCESS_EXITED_BEFORE_READY,
        severity=ComfyStartupIncidentSeverity.FATAL,
        title="ComfyUI failed to start",
        message="Process exited.",
        fingerprint="fatal-a",
    )
    state = process_manager.ManagedComfyState(
        registry=ManagedProcessRegistry(Path("E:/state"))
    )
    state.startup_result = ManagedStartupReadinessResult(
        ready=False,
        fatal_incident=incident,
    )

    assert managed_target_activation.managed_startup_fatal_incident(state) is incident
    assert managed_target_activation.managed_startup_fatal_incident(None) is None
    assert managed_target_activation.managed_startup_fatal_incident(object()) is None


def test_managed_target_activation_imports_no_forbidden_boundaries() -> None:
    """Managed activation should stay free of Qt, presentation, and subprocess."""

    imported_modules = _imported_module_names(ACTIVATION_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_ACTIVATION_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_no_longer_owns_managed_target_activation() -> None:
    """Startup should delegate managed target activation helpers."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    managed_ready_runtime_source = (
        PROJECT_ROOT
        / "substitute"
        / "app"
        / "bootstrap"
        / "startup_managed_ready_runtime.py"
    ).read_text(encoding="utf-8")

    assert "def _activate_target" not in source
    assert "def _collect_and_fan_out_comfy_output" not in source
    assert "def _fan_out_splash_and_shell_output" not in source
    assert "def _managed_startup_fatal_incident" not in source
    assert "TerminalOutputStream" not in ACTIVATION_SOURCE.read_text(encoding="utf-8")
    assert "managed_ready_launch.create_target_activation_task(" in launch_source
    assert "managed_ready_runtime.create_target_activation_task(" not in source
    assert "create_ready_shell_target_activation_task(" not in source
    assert "managed_ready_runtime.activate_target" not in source
    assert "fan_out_splash_and_shell_output(" not in source
    assert "managed_startup_fatal_incident(" not in source
    assert "managed_startup_fatal_incident(" in managed_ready_runtime_source


def _task_factory(*_args: object, **_kwargs: object) -> object:
    """Provide a sentinel managed task factory for activation tests."""

    return object()


def _context(tmp_path: Path, *, launch_owned: bool) -> InstallationContext:
    """Build one managed-local installation context."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=ComfyTargetConfiguration(
            mode=ComfyTargetMode.MANAGED_LOCAL,
            endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
            workspace_path=tmp_path / "ComfyUI",
            install_owned=True,
            launch_owned=launch_owned,
        ),
    )


def _imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


class _Splash:
    """Collect splash log lines."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def append_log(self, line: str) -> None:
        """Record one splash log line."""

        self.lines.append(line)


class _DisposedSplash:
    """Raise when late output reaches a disposed splash."""

    def append_log(self, _line: str) -> None:
        """Simulate a disposed splash widget."""

        raise RuntimeError("disposed")


class _FailingAfterActivationSplash:
    """Accept the activation line, then emulate a closed splash IPC endpoint."""

    def __init__(self) -> None:
        """Initialize accepted lines and failed output attempts."""

        self.lines: list[str] = []
        self.failure_count = 0

    def append_log(self, line: str) -> None:
        """Accept setup output and reject every later write as a socket failure."""

        if self.lines:
            self.failure_count += 1
            raise TimeoutError("splash endpoint closed")
        self.lines.append(line)


class _DisposedStream:
    """Raise when late output reaches a disposed shell stream."""

    def append_line(self, _line: str) -> None:
        """Simulate a disposed shell output stream."""

        raise RuntimeError("disposed")


class _Stream:
    """Collect terminal output stream lines."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def append_line(self, line: str) -> None:
        """Record one terminal output line."""

        self.lines.append(line)


class _Diagnostics:
    """Collect classified startup diagnostics lines."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def append_output(self, line: str) -> None:
        """Record one diagnostics line."""

        self.lines.append(line)


class _FailingDiagnostics:
    """Raise during diagnostics classification."""

    def append_output(self, _line: str) -> None:
        """Simulate diagnostics classification failure."""

        raise RuntimeError("classification failed")
