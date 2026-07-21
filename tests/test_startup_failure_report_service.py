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

"""Tests for pure startup failure report construction."""

from __future__ import annotations

import ast
from pathlib import Path

from sugarsubstitute_shared.localization import render_source_application_text

from substitute.application.comfy_startup_diagnostics.startup_failure_report_service import (
    build_startup_failure_report,
    build_startup_readiness_timeout_incident,
    build_startup_runtime_compatibility_incident,
)
from substitute.application.backend_compatibility import (
    BackendCompatibilityResult,
    RuntimeCompatibilityStatus,
)
from substitute.application.errors import ErrorReportKind
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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FAILURE_REPORT_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "application"
    / "comfy_startup_diagnostics"
    / "startup_failure_report_service.py"
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
FORBIDDEN_FAILURE_REPORT_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.app.bootstrap",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_startup_failure_report_carries_incident_context(tmp_path: Path) -> None:
    """Failure reports should expose managed startup incident diagnostics."""

    context = _context(tmp_path)
    incident = _incident(log_excerpt=("incident log",))

    report = build_startup_failure_report(
        installation_context=context,
        incident=incident,
        transcript=("startup line",),
    )

    assert report.kind is ErrorReportKind.COMFY_CONNECTION
    assert report.title == "ComfyUI failed to start"
    assert report.message == "ComfyUI exited before it became ready."
    assert report.stage == "managed_startup"
    assert report.exception_type == "RuntimeError"
    assert report.technical_detail == "incident log"
    assert report.runtime.server_logs == "startup line"
    assert report.operation_context is not None
    assert report.operation_context.operation == "managed_comfy_startup"
    assert report.operation_context.path == str(tmp_path / "ComfyUI")
    assert report.operation_context.values["target_mode"] == "managed_local"
    assert report.operation_context.values["host"] == "127.0.0.1"
    assert report.operation_context.values["port"] == 8188
    assert report.operation_context.values["readiness_path"] == "/system_stats"
    assert report.operation_context.values["incident_code"] == "early_exit"


def test_startup_failure_report_bounds_runtime_transcript(tmp_path: Path) -> None:
    """Failure reports should keep runtime logs bounded for modal rendering."""

    transcript = ("x" * 70_000,)

    report = build_startup_failure_report(
        installation_context=_context(tmp_path),
        incident=_incident(),
        transcript=transcript,
    )

    assert report.runtime.server_logs is not None
    assert len(report.runtime.server_logs) == 65_536
    assert report.runtime.server_logs == ("x" * 65_536)


def test_readiness_timeout_incident_records_startup_target(tmp_path: Path) -> None:
    """Readiness timeout incidents should identify the target and probe path."""

    incident = build_startup_readiness_timeout_incident(
        installation_context=_context(tmp_path),
        transcript=("loading custom node",),
    )

    assert incident.kind is ComfyStartupIncidentKind.READINESS_TIMEOUT
    assert incident.severity is ComfyStartupIncidentSeverity.FATAL
    assert incident.title == "ComfyUI failed to start"
    assert (
        incident.message == "ComfyUI did not become ready before the startup timeout."
    )
    assert incident.source == str(tmp_path / "ComfyUI")
    assert incident.log_excerpt == ("loading custom node",)
    assert incident.remediation is not None
    assert "last component" in incident.remediation
    assert incident.values["host"] == "127.0.0.1"
    assert incident.values["port"] == 8188
    assert incident.values["workspace"] == str(tmp_path / "ComfyUI")
    assert incident.values["readiness_path"] == "/system_stats"
    assert incident.fingerprint


def test_runtime_compatibility_incident_records_versions(tmp_path: Path) -> None:
    """Runtime compatibility incidents should carry version facts for repair."""

    incident = build_startup_runtime_compatibility_incident(
        installation_context=_context(tmp_path),
        compatibility=_compatibility(RuntimeCompatibilityStatus.SUGARCUBES_TOO_OLD),
        transcript=("startup log",),
        recovery_attempted=True,
        error=RuntimeError("still incompatible"),
    )

    assert incident.kind is ComfyStartupIncidentKind.RUNTIME_COMPATIBILITY_FAILED
    assert incident.severity is ComfyStartupIncidentSeverity.FATAL
    assert incident.title == "Comfy runtime is incompatible"
    rendered_message = render_source_application_text(incident.message)
    assert "SugarCubes version is incompatible." in rendered_message
    assert "Required BackEnd: >=1.6.2,<2.0.0." in rendered_message
    assert "Required SugarCubes: 0.11.0." in rendered_message
    assert "still incompatible" in rendered_message
    assert incident.exception_type == "RuntimeError"
    assert incident.log_excerpt == ("startup log",)
    assert incident.values["compatibility_status"] == "sugarcubes_too_old"
    assert incident.values["installed_backend_version"] == "1.6.2"
    assert incident.values["required_backend_version"] == ">=1.6.2,<2.0.0"
    assert incident.values["installed_sugarcubes_version"] == "0.8.0"
    assert incident.values["required_sugarcubes_version"] == "0.11.0"
    assert incident.values["recovery_attempted"] is True
    assert incident.values["host"] == "127.0.0.1"
    assert incident.values["port"] == 8188
    assert incident.values["workspace"] == str(tmp_path / "ComfyUI")
    assert "Automatic managed core update was attempted" in (incident.remediation or "")
    assert incident.fingerprint


def test_startup_failure_report_imports_no_forbidden_boundaries() -> None:
    """Failure report construction should stay free of Qt and infrastructure."""

    imported_modules = _imported_module_names(FAILURE_REPORT_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_FAILURE_REPORT_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_no_longer_builds_failure_reports() -> None:
    """The startup facade should delegate managed startup failure report building."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    managed_ready_runtime_source = MANAGED_READY_RUNTIME_SOURCE.read_text(
        encoding="utf-8"
    )

    assert "def _build_startup_failure_report" not in source
    assert "def _build_startup_readiness_timeout_incident" not in source
    assert "def _build_startup_runtime_compatibility_incident" not in source
    assert "def _bounded_report_text" not in source
    assert "create_startup_managed_failure_report_adapter(" not in source
    assert (
        "create_startup_managed_failure_report_adapter(" in managed_ready_runtime_source
    )
    assert "managed_ready_runtime.managed_failure_report_adapter" not in source
    assert "managed_ready_launch.create_failure_queue" in launch_source
    assert "managed_ready_runtime.create_failure_queue" not in source
    assert "StartupManagedFailureReportAdapter(" not in source
    assert "build_startup_failure_report(" not in source
    assert "managed_ready_runtime.create_readiness_failure_adapter(" not in source
    assert "managed_ready_launch.bind_startup_readiness_controller(" in launch_source
    assert "managed_ready_runtime.bind_startup_readiness_controller(" not in source
    assert "build_readiness_failure_adapter(" in managed_ready_runtime_source
    assert "create_startup_readiness_failure_adapter(" not in source
    assert "StartupReadinessFailureAdapter(" not in source
    assert "build_startup_readiness_timeout_incident(" not in source
    assert "build_startup_runtime_compatibility_incident(" not in source


def _context(tmp_path: Path) -> InstallationContext:
    """Build a managed-local installation context for failure reports."""

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
            launch_owned=True,
        ),
    )


def _incident(
    *,
    log_excerpt: tuple[str, ...] = (),
) -> ComfyStartupIncident:
    """Build one fatal managed startup incident."""

    return ComfyStartupIncident(
        kind=ComfyStartupIncidentKind.PROCESS_EXITED_BEFORE_READY,
        severity=ComfyStartupIncidentSeverity.FATAL,
        title="ComfyUI failed to start",
        message="ComfyUI exited before it became ready.",
        source="ComfyUI",
        exception_type="RuntimeError",
        fingerprint="fingerprint",
        log_excerpt=log_excerpt,
        remediation="Review the startup log.",
        values={"incident_code": "early_exit"},
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
