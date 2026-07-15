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

"""Tests for concrete startup diagnostics resource factories."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.app.bootstrap.startup_diagnostics_resources import (
    create_startup_diagnostics_collector,
    create_startup_diagnostics_ignore_repository,
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
RESOURCES_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_diagnostics_resources.py"
)
FORBIDDEN_DIAGNOSTICS_RESOURCE_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "subprocess",
    "substitute.infrastructure.comfy.process_manager",
)


def test_create_startup_diagnostics_collector_returns_transcript_collector() -> None:
    """Diagnostics collector factory should return the managed-startup collector."""

    collector = create_startup_diagnostics_collector()

    assert collector.transcript() == ()


def test_create_startup_diagnostics_ignore_repository_uses_context_directory(
    tmp_path: Path,
) -> None:
    """Ignore repository factory should persist below the context diagnostics dir."""

    context = _context(tmp_path)
    repository = create_startup_diagnostics_ignore_repository(context)
    fingerprints = frozenset({"incident-a"})

    repository.save_ignored_fingerprints(fingerprints)

    assert repository.load_ignored_fingerprints() == fingerprints
    assert any(context.diagnostics_dir.iterdir())


def test_startup_diagnostics_resources_import_no_forbidden_boundaries() -> None:
    """Diagnostics resource factories should avoid UI and process-manager imports."""

    imported_modules = _imported_module_names(RESOURCES_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_DIAGNOSTICS_RESOURCE_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_diagnostics_resource_construction() -> None:
    """Startup should not instantiate diagnostics resources directly."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    managed_ready_runtime_source = MANAGED_READY_RUNTIME_SOURCE.read_text(
        encoding="utf-8"
    )

    assert "run_startup_shell_flow(" in source
    assert "create_startup_managed_ready_runtime_resources(" not in source
    assert "create_startup_diagnostics_collector()" not in source
    assert "create_startup_diagnostics_ignore_repository(" not in source
    assert "create_startup_diagnostics_collector()" in managed_ready_runtime_source
    assert (
        "create_startup_diagnostics_ignore_repository(context)"
        in managed_ready_runtime_source
    )
    assert "ComfyStartupDiagnosticsCollector()" not in source
    assert "FileStartupDiagnosticsIgnoreRepository(" not in source


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
        comfy_target=ComfyTargetConfiguration(
            mode=ComfyTargetMode.MANAGED_LOCAL,
            endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
            workspace_path=tmp_path / "ComfyUI",
            install_owned=True,
            launch_owned=True,
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
