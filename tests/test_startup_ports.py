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

"""Tests for typed startup port bundles."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

from substitute.app.bootstrap.startup_ports import (
    StartupManagedReadyFactoryPorts,
    StartupRuntimeCompatibilityCheckerProtocol,
    StartupShellCompositionPorts,
)
from substitute.app.bootstrap.startup_model_metadata import (
    ModelMetadataUpdateSignalBridgeProtocol,
)
from substitute.application.comfy_startup_diagnostics import (
    ComfyStartupDiagnosticsCollector,
)
from substitute.application.ports.startup_diagnostics_ignore_repository import (
    StartupDiagnosticsIgnoreRepository,
)
from substitute.domain.comfy_startup_diagnostics import ComfyStartupIncident
from substitute.domain.onboarding import InstallationContext

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_PORTS_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_ports.py"
)
MANAGED_READY_RUNTIME_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_runtime.py"
)
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
STARTUP_READY_SHELL_LAUNCH_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_ready_shell_launch.py"
)
FORBIDDEN_PORT_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_startup_shell_composition_ports_expose_shell_callables() -> None:
    """Startup shell ports should retain the exact callable collaborators."""

    build_main_window = _CallablePort("build_main_window")
    show_main_window = _CallablePort("show_main_window")
    show_built_main_window = _CallablePort("show_built_main_window")
    main_window_for_shell = _CallablePort("main_window_for_shell")
    build_model_metadata_refresh_service = _CallablePort(
        "build_model_metadata_refresh_service"
    )
    is_comfy_http_ready = _ReadinessPort()

    ports = StartupShellCompositionPorts(
        build_main_window=build_main_window,
        show_main_window=show_main_window,
        show_built_main_window=show_built_main_window,
        main_window_for_shell=main_window_for_shell,
        build_model_metadata_refresh_service=build_model_metadata_refresh_service,
        is_comfy_http_ready=is_comfy_http_ready,
    )

    context = cast(InstallationContext, object())

    assert ports.build_main_window() == "build_main_window"
    assert ports.show_main_window() == "show_main_window"
    assert ports.show_built_main_window() == "show_built_main_window"
    assert ports.main_window_for_shell(object()) == "main_window_for_shell"
    assert (
        ports.build_model_metadata_refresh_service(context)
        == "build_model_metadata_refresh_service"
    )
    assert ports.is_comfy_http_ready("127.0.0.1", 8188) is True


def test_startup_managed_ready_factory_ports_expose_factory_callables() -> None:
    """Managed-ready factory ports should retain concrete startup adapters."""

    collector = cast(ComfyStartupDiagnosticsCollector, object())
    ignore_repository = cast(StartupDiagnosticsIgnoreRepository, object())
    compatibility_checker = cast(
        StartupRuntimeCompatibilityCheckerProtocol,
        _CompatibilityChecker(),
    )
    recovery_bridge = object()
    metadata_bridge = cast(ModelMetadataUpdateSignalBridgeProtocol, object())
    failure_report = object()
    readiness_incident = cast(ComfyStartupIncident, object())
    compatibility_incident = cast(ComfyStartupIncident, object())
    activation_result = object()
    fatal_incident = cast(ComfyStartupIncident, object())
    presented_reports: list[object] = []

    ports = StartupManagedReadyFactoryPorts(
        create_startup_diagnostics_collector=lambda: collector,
        create_startup_diagnostics_ignore_repository=lambda _context: ignore_repository,
        create_runtime_compatibility_checker=lambda: compatibility_checker,
        create_managed_compatibility_recovery_bridge=lambda: recovery_bridge,
        create_model_metadata_update_bridge=lambda _parent: metadata_bridge,
        request_startup_diagnostics_titlebar_update=lambda **_kwargs: True,
        activate_target=lambda **_kwargs: activation_result,
        managed_startup_fatal_incident=lambda _state: fatal_incident,
        present_startup_failure_report=presented_reports.append,
        build_startup_failure_report=lambda **_kwargs: failure_report,
        build_startup_readiness_timeout_incident=lambda **_kwargs: readiness_incident,
        build_startup_runtime_compatibility_incident=lambda **_kwargs: (
            compatibility_incident
        ),
    )
    context = cast(InstallationContext, object())

    assert ports.create_startup_diagnostics_collector() is collector
    assert (
        ports.create_startup_diagnostics_ignore_repository(context) is ignore_repository
    )
    assert ports.create_runtime_compatibility_checker() is compatibility_checker
    assert ports.create_managed_compatibility_recovery_bridge() is recovery_bridge
    assert ports.create_model_metadata_update_bridge(object()) is metadata_bridge
    assert ports.request_startup_diagnostics_titlebar_update() is True
    assert ports.activate_target() is activation_result
    assert ports.managed_startup_fatal_incident(object()) is fatal_incident
    ports.present_startup_failure_report(failure_report)
    assert presented_reports == [failure_report]
    assert ports.build_startup_failure_report() is failure_report
    assert ports.build_startup_readiness_timeout_incident() is readiness_incident
    assert (
        ports.build_startup_runtime_compatibility_incident() is compatibility_incident
    )


def test_startup_ports_imports_no_forbidden_boundaries() -> None:
    """Startup port bundles should stay free of Qt, presentation, and process APIs."""

    imported_modules = _imported_module_names(STARTUP_PORTS_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_PORT_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_uses_shell_composition_port_bundle() -> None:
    """Startup should adapt shell composition through one typed port bundle."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    support_graph_source = SUPPORT_GRAPH_SOURCE.read_text(encoding="utf-8")
    ready_launch_source = STARTUP_READY_SHELL_LAUNCH_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    assert "create_startup_support_graph(initial_splash=initial_splash)" in source
    assert "create_startup_shell_composition_ports()" not in source
    assert "create_startup_shell_composition_ports()" in support_graph_source
    assert "StartupShellCompositionPorts(" not in source
    assert "show_main_window=shell_ports.show_main_window" in ready_launch_source
    assert "build_main_window=self.shell_ports.build_main_window" in launch_source
    assert (
        "show_built_main_window=self.shell_ports.show_built_main_window"
        in launch_source
    )
    assert (
        "main_window_for_shell=self.shell_ports.main_window_for_shell" in launch_source
    )
    assert "readiness_probe=self.shell_ports.is_comfy_http_ready" in launch_source
    assert (
        "self.shell_ports.build_model_metadata_refresh_service(context)"
        in launch_source
    )
    assert "build_main_window=composition.build_main_window" not in source
    assert "show_main_window=composition.show_main_window" not in source
    assert "show_built_main_window=composition.show_built_main_window" not in source
    assert "main_window_for_shell=composition.main_window_widget" not in source
    assert "lambda host, port: composition.is_comfy_http_ready(" not in source
    assert "composition.build_model_metadata_refresh_service(context)" not in source


def test_startup_facade_uses_managed_ready_factory_port_bundle() -> None:
    """Startup should adapt managed-ready factories through one typed bundle."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    support_graph_source = SUPPORT_GRAPH_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    managed_ready_runtime_source = MANAGED_READY_RUNTIME_SOURCE.read_text(
        encoding="utf-8"
    )

    assert "create_startup_support_graph(initial_splash=initial_splash)" in source
    assert "create_startup_managed_ready_factory_ports()" not in source
    assert "create_startup_managed_ready_factory_ports()" in support_graph_source
    assert "StartupManagedReadyFactoryPorts(" not in source
    assert "run_startup_shell_flow(" in source
    assert "create_startup_managed_ready_runtime_resources(" not in source
    assert (
        "managed_ready_ports.create_startup_diagnostics_collector()"
        in managed_ready_runtime_source
    )
    assert (
        "managed_ready_ports.create_startup_diagnostics_ignore_repository(context)"
        in managed_ready_runtime_source
    )
    assert (
        "managed_ready_ports.create_runtime_compatibility_checker()"
        in managed_ready_runtime_source
    )
    assert (
        "managed_ready_ports.create_managed_compatibility_recovery_bridge()"
        in managed_ready_runtime_source
    )
    assert "managed_ready_ports.create_startup_diagnostics_collector()" not in source
    assert (
        "managed_ready_ports.create_startup_diagnostics_ignore_repository(context)"
        not in source
    )
    assert "managed_ready_ports.create_runtime_compatibility_checker()" not in source
    assert (
        "managed_ready_ports.create_managed_compatibility_recovery_bridge()"
        not in source
    )
    assert "managed_ready_launch.create_metadata_bridge_task(" in launch_source
    assert "managed_ready_runtime.create_metadata_bridge_task(" not in source
    assert "managed_ready_runtime.create_model_metadata_update_bridge" not in source
    assert (
        "bridge_factory=managed_ready_runtime.create_model_metadata_update_bridge"
        not in source
    )
    assert "managed_ready_ports.create_model_metadata_update_bridge" not in source
    assert (
        "managed_ready_ports.create_model_metadata_update_bridge"
        in managed_ready_runtime_source
    )
    assert "request_update=(" not in source
    assert (
        "request_update=(" in managed_ready_runtime_source
        and "managed_ready_ports.request_startup_diagnostics_titlebar_update"
        in managed_ready_runtime_source
    )
    assert "managed_ready_runtime.activate_target" not in source
    assert "managed_ready_launch.create_target_activation_task" in launch_source
    assert "managed_ready_runtime.create_target_activation_task" not in source
    assert "managed_ready_ports.activate_target" not in source
    assert "managed_ready_ports.activate_target" in managed_ready_runtime_source
    assert "managed_ready_runtime.managed_startup_fatal_incident" not in source
    assert "managed_ready_launch.create_show_gate_task(" in launch_source
    assert "managed_ready_runtime.create_show_gate_task" not in source
    assert "managed_ready_ports.managed_startup_fatal_incident" not in source
    assert (
        "managed_ready_ports.managed_startup_fatal_incident"
        in managed_ready_runtime_source
    )
    assert "managed_ready_runtime.present_startup_failure_report" not in source
    assert "managed_ready_launch.create_failure_queue" in launch_source
    assert "managed_ready_runtime.create_failure_queue" not in source
    assert "managed_ready_ports.present_startup_failure_report" not in source
    assert (
        "managed_ready_ports.present_startup_failure_report"
        in managed_ready_runtime_source
    )
    assert "build_report=managed_ready_ports.build_startup_failure_report" not in source
    assert (
        "build_report=managed_ready_ports.build_startup_failure_report"
        in managed_ready_runtime_source
    )
    assert (
        "managed_ready_ports.build_startup_readiness_timeout_incident"
        in managed_ready_runtime_source
    )
    assert (
        "managed_ready_ports.build_startup_runtime_compatibility_incident"
        in managed_ready_runtime_source
    )
    assert "managed_ready_ports.build_startup_readiness_timeout_incident" not in source
    assert (
        "managed_ready_ports.build_startup_runtime_compatibility_incident" not in source
    )
    assert "startup_diagnostics = create_startup_diagnostics_collector()" not in source
    assert (
        "create_startup_diagnostics_ignore_repository(\n            context"
        not in source
    )
    assert "create_endpoint_backend_compatibility_checker" not in source
    assert "create_managed_compatibility_recovery_bridge=(" not in source
    assert "create_model_metadata_update_bridge=" not in source
    assert "request_startup_diagnostics_titlebar_update=(" not in source
    assert "activate_target=activate_target" not in source
    assert "managed_startup_fatal_incident=managed_startup_fatal_incident" not in source
    assert "present_startup_failure_report=present_startup_failure_report" not in source
    assert "build_startup_failure_report=build_startup_failure_report" not in source


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


class _CallablePort:
    """Return its name when invoked."""

    def __init__(self, name: str) -> None:
        """Store the port name."""

        self._name = name

    def __call__(self, *_args: object, **_kwargs: object) -> str:
        """Return the configured name."""

        return self._name


class _ReadinessPort:
    """Record a positive HTTP readiness response."""

    def __call__(self, _host: str, _port: int) -> bool:
        """Return one ready result."""

        return True


class _CompatibilityChecker:
    """Represent a managed runtime compatibility checker."""

    def assess_target(self, _target: object) -> object:
        """Return one compatibility assessment."""

        return object()
