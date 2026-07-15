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

"""Tests for startup runtime compatibility composition."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.app.bootstrap.runtime_compatibility import (
    EndpointBackendCompatibilityChecker,
    ManagedStartupCompatibilityAssessor,
    create_endpoint_backend_compatibility_checker,
    create_managed_startup_compatibility_assessor,
)
from substitute.application.backend_compatibility import (
    BackendCompatibilityResult,
    RuntimeCompatibilityStatus,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
SUPPORT_GRAPH_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_support_graph.py"
)
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
MANAGED_READY_PORTS_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_managed_ready_ports.py"
)
RUNTIME_COMPATIBILITY_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "runtime_compatibility.py"
)
FORBIDDEN_RUNTIME_COMPATIBILITY_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "subprocess",
    "substitute.infrastructure.external",
    "substitute.infrastructure.comfy.process_manager",
)


def test_create_endpoint_backend_compatibility_checker_returns_checker() -> None:
    """Runtime compatibility factory should bind the current runtime mode."""

    checker = create_endpoint_backend_compatibility_checker()

    assert isinstance(checker, EndpointBackendCompatibilityChecker)


def test_managed_startup_compatibility_assessor_waits_for_comfy_state(
    tmp_path: Path,
) -> None:
    """Managed startup compatibility should not run before Comfy is launched."""

    target = _target(tmp_path)
    compatibility = _compatibility(RuntimeCompatibilityStatus.COMPATIBLE)
    checker = _Checker(compatibility)
    comfy_state: list[object | None] = [None]
    assessor = ManagedStartupCompatibilityAssessor(
        comfy_state=lambda: comfy_state[0],
        checker=checker,
        target=target,
    )

    assert assessor.assess() is None

    comfy_state[0] = object()

    assert assessor.assess() is compatibility
    assert checker.targets == [target]


def test_create_managed_startup_compatibility_assessor_returns_assessor(
    tmp_path: Path,
) -> None:
    """Managed compatibility assessor construction should live in its owner."""

    target = _target(tmp_path)
    checker = _Checker(_compatibility(RuntimeCompatibilityStatus.COMPATIBLE))

    assessor = create_managed_startup_compatibility_assessor(
        comfy_state=lambda: object(),
        checker=checker,
        target=target,
    )

    assert isinstance(assessor, ManagedStartupCompatibilityAssessor)
    result = assessor.assess()

    assert result is not None
    assert result.status is RuntimeCompatibilityStatus.COMPATIBLE


def test_runtime_compatibility_imports_no_forbidden_boundaries() -> None:
    """Runtime compatibility composition should avoid UI and process-manager imports."""

    imported_modules = _top_level_imported_module_names(RUNTIME_COMPATIBILITY_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_RUNTIME_COMPATIBILITY_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_runtime_compatibility_checker() -> None:
    """Startup should request compatibility checking through the runtime owner."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    managed_ready_runtime_source = MANAGED_READY_RUNTIME_SOURCE.read_text(
        encoding="utf-8"
    )
    managed_ready_ports_source = MANAGED_READY_PORTS_SOURCE.read_text(encoding="utf-8")
    support_graph_source = SUPPORT_GRAPH_SOURCE.read_text(encoding="utf-8")

    assert "create_startup_support_graph(initial_splash=initial_splash)" in source
    assert "create_startup_managed_ready_factory_ports()" not in source
    assert "create_startup_managed_ready_factory_ports()" in support_graph_source
    assert "create_runtime_compatibility_checker=(" not in source
    assert "create_endpoint_backend_compatibility_checker" not in source
    assert "create_runtime_compatibility_checker=(" in managed_ready_ports_source
    assert "create_endpoint_backend_compatibility_checker" in managed_ready_ports_source
    assert "run_startup_shell_flow(" in source
    assert "create_startup_managed_ready_runtime_resources(" not in source
    assert "managed_ready_ports.create_runtime_compatibility_checker()" not in source
    assert (
        "managed_ready_ports.create_runtime_compatibility_checker()"
        in managed_ready_runtime_source
    )
    assert "managed_ready_runtime.managed_startup_compatibility_assessor" not in source
    assert "managed_ready_launch.bind_startup_readiness_controller(" in launch_source
    assert "managed_ready_runtime.bind_startup_readiness_controller(" not in source
    assert "create_managed_startup_compatibility_assessor(" not in source
    assert (
        "create_managed_startup_compatibility_assessor(" in managed_ready_runtime_source
    )
    assert "ManagedStartupCompatibilityAssessor(" not in source
    assert "def assess_managed_startup_compatibility" not in source
    assert "BackendCompatibilityResult" not in source
    assert "EndpointBackendCompatibilityChecker(" not in source
    assert "ApplicationRuntimeModeService.from_environment()" not in source


def _target(tmp_path: Path) -> ComfyTargetConfiguration:
    """Build one managed target for runtime compatibility tests."""

    return ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=tmp_path / "ComfyUI",
        install_owned=True,
        launch_owned=True,
    )


def _compatibility(
    status: RuntimeCompatibilityStatus,
) -> BackendCompatibilityResult:
    """Build one runtime compatibility result."""

    return BackendCompatibilityResult(
        status=status,
        summary="Runtime is compatible.",
    )


def _top_level_imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported at module load time by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


class _Checker:
    """Record runtime compatibility target assessments."""

    def __init__(self, result: BackendCompatibilityResult) -> None:
        """Store the compatibility result to return."""

        self._result = result
        self.targets: list[ComfyTargetConfiguration] = []

    def assess_target(
        self,
        target: ComfyTargetConfiguration,
    ) -> BackendCompatibilityResult:
        """Record one target assessment."""

        self.targets.append(target)
        return self._result
