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

"""Tests for startup installation environment preparation."""

from __future__ import annotations

import ast
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TypeVar, cast

from substitute.app.bootstrap.startup_environment import (
    StartupEnvironment,
    prepare_startup_environment,
)
from substitute.domain.onboarding import (
    BootstrapRoute,
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    ReadinessAssessment,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_environment.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
FORBIDDEN_ENVIRONMENT_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "subprocess",
)
_T = TypeVar("_T")


def test_prepare_startup_environment_migrates_before_readiness(
    tmp_path: Path,
) -> None:
    """Managed workspace migration should run before readiness assessment."""

    context = _managed_context(tmp_path)
    events: list[str] = []
    timer = _RecordingTimer(events)
    readiness = ReadinessAssessment(route=BootstrapRoute.REPAIR, issues=())
    bundle = _ServiceBundle(events, readiness)
    migrated_workspaces: list[Path] = []

    environment = prepare_startup_environment(
        explicit_install_root=tmp_path,
        startup_timer=cast(Any, timer),
        resolve_root=lambda root: _record(events, "resolve", root or tmp_path),
        load_persisted_context=lambda _root: _record(events, "load_persisted", context),
        build_service_bundle=lambda _root: cast(
            Any, _record(events, "build_bundle", bundle)
        ),
        create_default_context=lambda _root: _record(events, "create_default", context),
        migrate_managed_workspace_layout=lambda workspace: _record_migration(
            events,
            migrated_workspaces,
            workspace,
        ),
    )

    assert environment == StartupEnvironment(
        install_root=tmp_path,
        service_bundle=cast(Any, bundle),
        readiness_assessment=readiness,
        installation_context=context,
    )
    assert migrated_workspaces == [context.managed_comfy_dir]
    assert events.index("migrate_workspace") < events.index("assess_readiness")
    assert "create_default" not in events


def test_prepare_startup_environment_uses_default_context_when_missing(
    tmp_path: Path,
) -> None:
    """Startup should create a default route context when no persisted context exists."""

    default_context = _remote_context(tmp_path)
    readiness = ReadinessAssessment(route=BootstrapRoute.ONBOARDING, issues=())
    events: list[str] = []

    environment = prepare_startup_environment(
        explicit_install_root=tmp_path,
        startup_timer=cast(Any, _RecordingTimer(events)),
        resolve_root=lambda root: root or tmp_path,
        load_persisted_context=lambda _root: None,
        build_service_bundle=lambda _root: cast(Any, _ServiceBundle(events, readiness)),
        create_default_context=lambda _root: _record(
            events, "create_default", default_context
        ),
        migrate_managed_workspace_layout=lambda _workspace: False,
    )

    assert environment.installation_context is default_context
    assert environment.readiness_assessment is readiness
    assert "create_default" in events


def test_startup_environment_imports_no_forbidden_boundaries() -> None:
    """Environment preparation should stay free of Qt, presentation, and subprocess."""

    imported_modules = _imported_module_names(ENVIRONMENT_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_ENVIRONMENT_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_onboarding_package_exports_do_not_eagerly_import_flow_stack() -> None:
    """Onboarding package imports should not pull route-only services into startup."""

    command = [
        sys.executable,
        "-c",
        (
            "import sys\n"
            "from substitute.application.onboarding import BootstrapReadinessService\n"
            "_ = BootstrapReadinessService\n"
            "for name in ("
            "'substitute.application.onboarding.flow_service',"
            "'substitute.application.onboarding.preference_setup_service'"
            "):\n"
            "    assert name not in sys.modules, name\n"
        ),
    ]

    subprocess.run(command, check=True)


def test_installation_context_helpers_do_not_import_preference_stack(
    tmp_path: Path,
) -> None:
    """Startup context helpers should avoid route-only preference services."""

    command = [
        sys.executable,
        "-c",
        (
            "import sys\n"
            "from pathlib import Path\n"
            "from substitute.app.bootstrap.installation_context import "
            "create_default_installation_context, load_persisted_installation_context\n"
            f"root = Path({str(tmp_path)!r})\n"
            "assert load_persisted_installation_context(root) is None\n"
            "create_default_installation_context(root)\n"
            "for name in ("
            "'substitute.application.civitai',"
            "'substitute.application.danbooru',"
            "'substitute.application.generation',"
            "'substitute.application.onboarding.preference_setup_service',"
            "'substitute.application.prompt_editor'"
            "):\n"
            "    assert name not in sys.modules, name\n"
        ),
    ]

    subprocess.run(command, check=True)


def test_startup_facade_delegates_environment_preparation() -> None:
    """Startup should not own install-context loading or readiness assessment."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")

    assert "prepare_startup_environment(" in source
    assert "resolve_installation_root(" not in source
    assert "load_persisted_installation_context(" not in source
    assert "build_onboarding_service_bundle(" not in source
    assert "create_default_installation_context(" not in source
    assert "ManagedWorkspaceLayoutMigrationService(" not in source
    assert "migrate_nested_workspace_layout" not in source


class _RecordingTimer:
    """Record startup phase entry for environment tests."""

    def __init__(self, events: list[str]) -> None:
        """Store the shared event sink."""

        self._events = events

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        """Record one entered startup phase."""

        self._events.append(name)
        yield


class _ReadinessService:
    """Readiness service test double."""

    def __init__(
        self,
        events: list[str],
        assessment: ReadinessAssessment,
    ) -> None:
        """Store readiness result and event sink."""

        self._events = events
        self._assessment = assessment

    def assess(self) -> ReadinessAssessment:
        """Record readiness assessment and return the configured route."""

        self._events.append("assess_readiness")
        return self._assessment


class _ServiceBundle(SimpleNamespace):
    """Onboarding service bundle test double."""

    def __init__(
        self,
        events: list[str],
        assessment: ReadinessAssessment,
    ) -> None:
        """Expose the readiness service used by environment preparation."""

        super().__init__(readiness_service=_ReadinessService(events, assessment))


def _managed_context(tmp_path: Path) -> InstallationContext:
    """Build a launch-owned managed context for migration tests."""

    context = _remote_context(tmp_path)
    return InstallationContext(
        installation=context.installation,
        runtime=context.runtime,
        comfy_target=ComfyTargetConfiguration(
            mode=ComfyTargetMode.MANAGED_LOCAL,
            endpoint=context.comfy_target.endpoint,
            workspace_path=context.installation.default_managed_comfy_dir,
            install_owned=True,
            launch_owned=True,
        ),
    )


def _remote_context(tmp_path: Path) -> InstallationContext:
    """Build one remote installation context for environment tests."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.REMOTE,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=None,
        install_owned=False,
        launch_owned=False,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=target,
    )


def _record(events: list[str], event: str, value: _T) -> _T:
    """Record one event and return the supplied value."""

    events.append(event)
    return value


def _record_migration(
    events: list[str],
    migrated_workspaces: list[Path],
    workspace: Path,
) -> bool:
    """Record one managed workspace migration call."""

    events.append("migrate_workspace")
    migrated_workspaces.append(workspace)
    return True


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
