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

"""Verify installation layout migration application services."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.application.onboarding.installation_layout_migration_service import (
    ManagedWorkspaceLayoutMigrationService,
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
SERVICE_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "application"
    / "onboarding"
    / "installation_layout_migration_service.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
FORBIDDEN_SERVICE_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
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


def test_managed_workspace_migration_runs_for_launch_owned_target(
    tmp_path: Path,
) -> None:
    """Launch-owned managed targets should run the supplied migration port."""

    context = _installation_context(tmp_path, launch_owned=True)
    migrated_workspaces: list[Path] = []
    service = ManagedWorkspaceLayoutMigrationService(
        migrate_nested_workspace_layout=lambda workspace: _record_migration(
            migrated_workspaces,
            workspace,
            migrated=True,
        )
    )

    assert service.migrate(context) is True
    assert migrated_workspaces == [context.managed_comfy_dir]


def test_managed_workspace_migration_skips_non_owned_or_missing_targets(
    tmp_path: Path,
) -> None:
    """Migration should fail closed unless the target owns a concrete workspace."""

    migrated_workspaces: list[Path] = []
    service = ManagedWorkspaceLayoutMigrationService(
        migrate_nested_workspace_layout=lambda workspace: _record_migration(
            migrated_workspaces,
            workspace,
            migrated=True,
        )
    )

    assert service.migrate(None) is False
    assert service.migrate(_installation_context(tmp_path, launch_owned=False)) is False
    assert (
        service.migrate(
            _installation_context(
                tmp_path,
                launch_owned=True,
                workspace_path=None,
            )
        )
        is False
    )
    assert migrated_workspaces == []


def test_managed_workspace_migration_returns_port_result(tmp_path: Path) -> None:
    """Migration result should reflect whether the adapter changed the workspace."""

    context = _installation_context(tmp_path, launch_owned=True)
    service = ManagedWorkspaceLayoutMigrationService(
        migrate_nested_workspace_layout=lambda _workspace: False
    )

    assert service.migrate(context) is False


def test_managed_workspace_migration_service_imports_no_forbidden_boundaries() -> None:
    """Application migration policy should not import infrastructure or Qt."""

    imported_modules = _imported_module_names(SERVICE_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_SERVICE_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_no_longer_owns_managed_workspace_migration_policy() -> None:
    """Startup should delegate managed workspace migration policy."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")

    assert "def _migrate_managed_workspace_layout" not in source
    assert "migrate_nested_workspace_layout(workspace)" not in source
    assert "Migrated legacy nested managed ComfyUI workspace layout" not in source


def _installation_context(
    tmp_path: Path,
    *,
    launch_owned: bool,
    workspace_path: Path | None | object = object(),
) -> InstallationContext:
    """Build an installation context for migration policy tests."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    resolved_workspace = (
        installation.default_managed_comfy_dir
        if not isinstance(workspace_path, Path) and workspace_path is not None
        else workspace_path
    )
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=resolved_workspace,
        install_owned=launch_owned,
        launch_owned=launch_owned,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=target,
    )


def _record_migration(
    calls: list[Path],
    workspace: Path,
    *,
    migrated: bool,
) -> bool:
    """Record a migration adapter call and return its configured result."""

    calls.append(workspace)
    return migrated
