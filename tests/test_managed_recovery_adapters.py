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

"""Tests for concrete managed compatibility recovery startup adapters."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, cast

import pytest

from sugarsubstitute_shared.localization import render_source_application_text

from substitute.app.bootstrap import managed_recovery_adapters
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
from substitute.application.backend_compatibility import (
    BackendCompatibilityResult,
    RuntimeCompatibilityStatus,
)
from substitute.application.comfy_startup_diagnostics import (
    ComfyStartupDiagnosticsCollector,
)
from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyPythonBinding,
    ComfyPythonSelectionSource,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "managed_recovery_adapters.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
MANAGED_READY_RUNTIME_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_runtime.py"
)
FORBIDDEN_ADAPTER_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "subprocess",
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


def test_reconcile_owned_dependencies_for_managed_target_runs_managed_setup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed-local recovery should forward to full managed setup."""

    calls: list[tuple[Path, frozenset[CoreNodepackId], object, object]] = []

    def fake_setup(**kwargs: Any) -> None:
        """Record managed setup arguments and emit through both log ports."""

        calls.append(
            (
                kwargs["workspace"],
                kwargs["refresh_core_nodepacks"],
                kwargs["on_status"],
                kwargs["on_log"],
            )
        )
        kwargs["on_status"]("status")
        kwargs["on_log"]("log")

    monkeypatch.setattr(
        managed_recovery_adapters,
        "ensure_managed_comfy_setup",
        fake_setup,
    )
    logs: list[str] = []

    managed_recovery_adapters.reconcile_owned_comfy_dependencies(
        _target(tmp_path, ComfyTargetMode.MANAGED_LOCAL),
        frozenset({CoreNodepackId.SUGARCUBES}),
        logs.append,
    )

    assert calls == [
        (
            tmp_path / "ComfyUI",
            frozenset({CoreNodepackId.SUGARCUBES}),
            logs.append,
            logs.append,
        )
    ]
    assert logs == ["status", "log"]


def test_reconcile_owned_dependencies_for_attached_target_runs_nodepack_policy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Attached-local recovery should mutate only trusted Substitute nodepacks."""

    core_calls: list[tuple[Path, frozenset[CoreNodepackId], object]] = []
    baseline_calls: list[tuple[Path, object]] = []

    def fake_ensure_core_nodepacks(
        workspace: Path,
        *,
        refresh_nodepacks: frozenset[CoreNodepackId],
        python_executable: Path,
        on_log: object,
    ) -> None:
        """Record core nodepack reconciliation arguments."""

        core_calls.append((workspace, refresh_nodepacks, on_log))
        assert python_executable.name == "python.exe"
        assert callable(on_log)
        on_log("core ready")

    def fake_baseline_maintenance(
        workspace: Path,
        *,
        python_executable: Path,
        on_log: object,
    ) -> None:
        """Record SugarCubes baseline maintenance arguments."""

        baseline_calls.append((workspace, on_log))
        assert python_executable.name == "python.exe"
        assert callable(on_log)
        on_log("baseline ready")

    def fail_managed_setup(**_kwargs: Any) -> None:
        """Fail if attached-local recovery tries to run managed setup."""

        raise AssertionError("attached local target used managed setup")

    monkeypatch.setattr(
        managed_recovery_adapters,
        "ensure_core_comfy_nodepacks",
        fake_ensure_core_nodepacks,
    )
    monkeypatch.setattr(
        managed_recovery_adapters,
        "run_sugarcubes_baseline_maintenance",
        fake_baseline_maintenance,
    )
    monkeypatch.setattr(
        managed_recovery_adapters,
        "ensure_managed_comfy_setup",
        fail_managed_setup,
    )
    monkeypatch.setattr(
        managed_recovery_adapters,
        "ensure_attached_workspace_manager",
        lambda *_args, **_kwargs: None,
    )
    logs: list[str] = []

    managed_recovery_adapters.reconcile_owned_comfy_dependencies(
        _target(tmp_path, ComfyTargetMode.ATTACHED_LOCAL),
        frozenset({CoreNodepackId.SUBSTITUTE_BACKEND}),
        logs.append,
    )

    assert core_calls == [
        (
            tmp_path / "ComfyUI",
            frozenset({CoreNodepackId.SUBSTITUTE_BACKEND}),
            logs.append,
        )
    ]
    assert baseline_calls == [(tmp_path / "ComfyUI", logs.append)]
    assert logs == [
        "Updating Substitute Comfy nodepacks.",
        "core ready",
        "Preparing Base-Cubes dependencies.",
        "baseline ready",
    ]


def test_reconcile_owned_dependencies_rejects_remote_target(tmp_path: Path) -> None:
    """Remote targets should not receive local nodepack mutation."""

    with pytest.raises(RuntimeError, match="launch-owned local workspace"):
        managed_recovery_adapters.reconcile_owned_comfy_dependencies(
            _target(tmp_path, ComfyTargetMode.REMOTE),
            frozenset({CoreNodepackId.SUGARCUBES}),
            lambda _line: None,
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


def test_startup_recovery_adapters_use_live_splash_and_output_stream(
    tmp_path: Path,
) -> None:
    """Startup recovery adapters should read the current splash per callback."""

    first_splash = _Splash()
    second_splash = _Splash()
    splash_state: list[_Splash | None] = [first_splash]
    output_stream = _OutputStream()
    adapters = managed_recovery_adapters.ManagedRecoveryStartupAdapters(
        installation_context=_context(tmp_path),
        splash=lambda: splash_state[0],
        comfy_output_stream=output_stream,
        startup_diagnostics=ComfyStartupDiagnosticsCollector(),
        handle_managed_startup_failure=lambda _incident: None,
        launch_task_factory=cast(Any, _task_factory),
        process_pump_task_factory=cast(Any, _task_factory),
    )

    adapters.append_recovery_message("Updating Substitute BackEnd before opening.")
    splash_state[0] = second_splash
    adapters.emit_recovery_log("setup complete")

    assert first_splash.lines == ["Updating Substitute BackEnd before opening."]
    assert second_splash.lines == ["setup complete"]
    assert output_stream.lines == ["setup complete"]


def test_create_managed_recovery_startup_adapters_returns_adapter(
    tmp_path: Path,
) -> None:
    """Managed recovery startup adapter construction should live in its owner."""

    splash = _Splash()

    adapters = managed_recovery_adapters.create_managed_recovery_startup_adapters(
        installation_context=_context(tmp_path),
        splash=lambda: splash,
        comfy_output_stream=_OutputStream(),
        startup_diagnostics=ComfyStartupDiagnosticsCollector(),
        handle_managed_startup_failure=lambda _incident: None,
        launch_task_factory=cast(Any, _task_factory),
        process_pump_task_factory=cast(Any, _task_factory),
    )

    assert isinstance(
        adapters, managed_recovery_adapters.ManagedRecoveryStartupAdapters
    )
    adapters.append_recovery_message("Recovering managed runtime.")
    assert splash.lines == ["Recovering managed runtime."]


def test_startup_recovery_log_survives_disposed_splash(tmp_path: Path) -> None:
    """Disposed splash logging should not block shell output retention."""

    output_stream = _OutputStream()
    adapters = managed_recovery_adapters.ManagedRecoveryStartupAdapters(
        installation_context=_context(tmp_path),
        splash=lambda: _DisposedSplash(),
        comfy_output_stream=output_stream,
        startup_diagnostics=ComfyStartupDiagnosticsCollector(),
        handle_managed_startup_failure=lambda _incident: None,
        launch_task_factory=cast(Any, _task_factory),
        process_pump_task_factory=cast(Any, _task_factory),
    )

    adapters.emit_recovery_log("late setup line")

    assert output_stream.lines == ["late setup line"]


def test_startup_recovery_failure_builds_runtime_incident(tmp_path: Path) -> None:
    """Recovery failure adapter should build the fatal runtime incident once."""

    diagnostics = ComfyStartupDiagnosticsCollector()
    diagnostics.append_output("captured recovery transcript")
    incidents: list[object] = []
    adapters = managed_recovery_adapters.ManagedRecoveryStartupAdapters(
        installation_context=_context(tmp_path),
        splash=lambda: None,
        comfy_output_stream=_OutputStream(),
        startup_diagnostics=diagnostics,
        handle_managed_startup_failure=incidents.append,
        launch_task_factory=cast(Any, _task_factory),
        process_pump_task_factory=cast(Any, _task_factory),
    )

    adapters.handle_recovery_failure(
        _compatibility(RuntimeCompatibilityStatus.SUGARCUBES_TOO_OLD),
        RuntimeError("recovery failed"),
    )

    incident = incidents[0]
    assert render_source_application_text(getattr(incident, "message")) == (
        "SugarCubes version is incompatible. Required BackEnd: >=1.6.2,<2.0.0. "
        "Required SugarCubes: 0.11.0. recovery failed"
    )
    assert getattr(incident, "log_excerpt") == ("captured recovery transcript",)
    assert getattr(incident, "values")["recovery_attempted"] is True


def test_startup_recovery_relaunch_delegates_to_activation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Recovery relaunch adapter should restart through managed target activation."""

    splash = _Splash()
    output_stream = _OutputStream()
    diagnostics = ComfyStartupDiagnosticsCollector()
    context = _context(tmp_path)
    relaunched_state = object()
    calls: list[dict[str, object]] = []

    def fake_activate_target(**kwargs: object) -> object:
        """Record activation arguments."""

        calls.append(kwargs)
        return relaunched_state

    monkeypatch.setattr(
        managed_recovery_adapters,
        "activate_target",
        fake_activate_target,
    )
    adapters = managed_recovery_adapters.ManagedRecoveryStartupAdapters(
        installation_context=context,
        splash=lambda: splash,
        comfy_output_stream=output_stream,
        startup_diagnostics=diagnostics,
        handle_managed_startup_failure=lambda _incident: None,
        launch_task_factory=cast(Any, _task_factory),
        process_pump_task_factory=cast(Any, _task_factory),
    )

    assert adapters.relaunch_managed_comfy() is relaunched_state
    assert calls == [
        {
            "installation_context": context,
            "splash": splash,
            "comfy_output_stream": output_stream,
            "startup_diagnostics": diagnostics,
            "launch_task_factory": _task_factory,
            "process_pump_task_factory": _task_factory,
        }
    ]


def test_managed_recovery_adapters_import_no_forbidden_boundaries() -> None:
    """Concrete recovery adapters should avoid direct Qt/UI/process-shell imports."""

    imported_modules = _imported_module_names(ADAPTER_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_ADAPTER_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def _task_factory(*_args: object, **_kwargs: object) -> object:
    """Provide a sentinel managed process task factory."""

    return object()


class _ManagedState:
    """Expose managed-state cleanup synchronization for adapter tests."""

    def with_spawn_lock(self, action: Any) -> object:
        """Run the supplied cleanup action immediately."""

        return action()


def test_startup_facade_delegates_managed_recovery_concrete_adapters() -> None:
    """Startup should delegate concrete managed recovery adapter details."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    managed_ready_runtime_source = MANAGED_READY_RUNTIME_SOURCE.read_text(
        encoding="utf-8"
    )

    assert "from concurrent.futures import" not in source
    assert "ensure_managed_comfy_setup" not in source
    assert 'thread_name_prefix="managed-compatibility-recovery"' not in source
    assert "def setup_managed_recovery_comfy" not in source
    assert "def cleanup_managed_recovery_state" not in source
    assert "def append_managed_recovery_message" not in source
    assert "def emit_managed_recovery_log" not in source
    assert "def handle_managed_recovery_failure" not in source
    assert "def relaunch_managed_recovery_comfy" not in source
    assert (
        "managed_ready_runtime.create_managed_recovery_startup_adapters(" not in source
    )
    assert (
        "from substitute.app.bootstrap.managed_recovery_adapters import" not in source
    )
    assert "create_managed_recovery_controller_adapters(" not in source
    assert (
        "create_managed_recovery_controller_adapters(" in managed_ready_runtime_source
    )
    assert "create_managed_recovery_startup_adapters(" in managed_ready_runtime_source
    assert "managed_ready_runtime.managed_recovery_controller_adapters" not in source
    assert (
        "managed_ready_launch.create_managed_compatibility_recovery_controller("
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_managed_compatibility_recovery_controller("
        not in source
    )
    assert "startup_adapters=" not in source
    assert "ManagedRecoveryStartupAdapters(" not in source
    assert "ManagedRecoveryControllerAdapters(" not in source
    assert "create_managed_recovery_executor" not in source
    assert "register_managed_recovery_executor" not in source
    assert "cleanup_managed_recovery_state" not in source
    assert "setup_managed_recovery_comfy" not in source
    assert "confirmed_managed_recovery_termination_status()" not in source


def _context(tmp_path: Path) -> InstallationContext:
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
        comfy_target=_target(tmp_path, ComfyTargetMode.MANAGED_LOCAL),
    )


def _target(tmp_path: Path, mode: ComfyTargetMode) -> ComfyTargetConfiguration:
    """Build one target configuration with normal ownership for its mode."""

    workspace = tmp_path / "ComfyUI"
    binding = (
        ComfyPythonBinding(
            executable=workspace / ".venv" / "Scripts" / "python.exe",
            version="3.13",
            architecture="AMD64",
            prefix=workspace / ".venv",
            base_prefix=workspace / ".venv",
            source=ComfyPythonSelectionSource.DISCOVERED,
        )
        if mode is ComfyTargetMode.ATTACHED_LOCAL
        else None
    )
    return ComfyTargetConfiguration(
        mode=mode,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=None if mode is ComfyTargetMode.REMOTE else workspace,
        install_owned=mode is ComfyTargetMode.MANAGED_LOCAL,
        launch_owned=mode is not ComfyTargetMode.REMOTE,
        python_binding=binding,
    )


def _compatibility(
    status: RuntimeCompatibilityStatus,
) -> BackendCompatibilityResult:
    """Build one incompatible runtime compatibility result."""

    return BackendCompatibilityResult(
        status=status,
        summary="SugarCubes version is incompatible.",
        installed_backend_version="1.6.2",
        required_backend_version=">=1.6.2,<2.0.0",
        installed_sugarcubes_version="0.8.0",
        required_sugarcubes_version="0.11.0",
        repairable=True,
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
        """Initialize empty splash log capture."""

        self.lines: list[str] = []

    def append_log(self, line: str) -> None:
        """Record one splash line."""

        self.lines.append(line)

    def close(self) -> None:
        """Satisfy the launch splash protocol."""


class _DisposedSplash:
    """Raise when late recovery output reaches a disposed splash."""

    def append_log(self, _line: str) -> None:
        """Simulate a disposed splash client."""

        raise RuntimeError("disposed")

    def close(self) -> None:
        """Satisfy the launch splash protocol."""


class _OutputStream:
    """Collect recovery output stream lines."""

    def __init__(self) -> None:
        """Initialize empty output capture."""

        self.lines: list[str] = []

    def append_line(self, line: str) -> None:
        """Record one output line."""

        self.lines.append(line)


class _Submitter:
    """Record runtime submitter close calls."""

    def __init__(self) -> None:
        """Initialize close tracking."""

        self.close_calls = 0

    def close(self) -> None:
        """Record one close request."""

        self.close_calls += 1


class _ExecutionRuntime:
    """Record managed recovery submitter construction."""

    def __init__(self, submitter: _Submitter) -> None:
        """Store the submitter returned by runtime calls."""

        self._submitter = submitter
        self.submitter_calls: list[dict[str, object]] = []

    def submitter(
        self,
        name: str,
        *,
        owner_id: str,
        dispatcher: object,
    ) -> _Submitter:
        """Record one runtime submitter request."""

        self.submitter_calls.append(
            {
                "name": name,
                "owner_id": owner_id,
            }
        )
        assert dispatcher is not None
        return self._submitter
