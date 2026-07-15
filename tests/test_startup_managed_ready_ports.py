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

"""Tests for concrete managed-ready startup port adapters."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.app.bootstrap import startup_managed_ready_ports
from substitute.app.bootstrap.managed_target_activation import (
    activate_target,
    managed_startup_fatal_incident,
)
from substitute.app.bootstrap.runtime_compatibility import (
    create_endpoint_backend_compatibility_checker,
)
from substitute.app.bootstrap.startup_diagnostics_request import (
    request_startup_diagnostics_titlebar_update,
)
from substitute.app.bootstrap.startup_diagnostics_resources import (
    create_startup_diagnostics_collector,
    create_startup_diagnostics_ignore_repository,
)
from substitute.app.bootstrap.startup_model_metadata_bridge import (
    create_model_metadata_update_bridge,
)
from substitute.app.bootstrap.startup_ports import StartupManagedReadyFactoryPorts
from substitute.app.bootstrap.startup_signal_bridges import (
    create_managed_compatibility_recovery_bridge,
)
from substitute.application.comfy_startup_diagnostics import (
    build_startup_failure_report,
    build_startup_readiness_timeout_incident,
    build_startup_runtime_compatibility_incident,
)
from substitute.presentation.errors.startup_failure_presenter import (
    present_startup_failure_report,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANAGED_READY_PORTS_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_managed_ready_ports.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
SUPPORT_GRAPH_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_support_graph.py"
)
FORBIDDEN_ADAPTER_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.infrastructure",
    "substitute.presentation.shell",
    "subprocess",
)


def test_create_startup_managed_ready_factory_ports_groups_concrete_ports() -> None:
    """Concrete managed-ready port factory should bind the startup adapters."""

    ports = startup_managed_ready_ports.create_startup_managed_ready_factory_ports()

    assert isinstance(ports, StartupManagedReadyFactoryPorts)
    assert (
        ports.create_startup_diagnostics_collector
        is create_startup_diagnostics_collector
    )
    assert (
        ports.create_startup_diagnostics_ignore_repository
        is create_startup_diagnostics_ignore_repository
    )
    assert (
        ports.create_runtime_compatibility_checker
        is create_endpoint_backend_compatibility_checker
    )
    assert (
        ports.create_managed_compatibility_recovery_bridge
        is create_managed_compatibility_recovery_bridge
    )
    assert (
        ports.create_model_metadata_update_bridge is create_model_metadata_update_bridge
    )
    assert (
        ports.request_startup_diagnostics_titlebar_update
        is request_startup_diagnostics_titlebar_update
    )
    assert ports.activate_target is activate_target
    assert ports.managed_startup_fatal_incident is managed_startup_fatal_incident
    assert ports.present_startup_failure_report is present_startup_failure_report
    assert ports.build_startup_failure_report is build_startup_failure_report
    assert (
        ports.build_startup_readiness_timeout_incident
        is build_startup_readiness_timeout_incident
    )
    assert (
        ports.build_startup_runtime_compatibility_incident
        is build_startup_runtime_compatibility_incident
    )


def test_startup_managed_ready_ports_imports_no_forbidden_boundaries() -> None:
    """Managed-ready port adapters should avoid Qt and infrastructure imports."""

    imported_modules = _imported_module_names(MANAGED_READY_PORTS_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_ADAPTER_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_managed_ready_port_construction() -> None:
    """Startup should request one concrete managed-ready port bundle."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    support_graph_source = SUPPORT_GRAPH_SOURCE.read_text(encoding="utf-8")

    assert "create_startup_support_graph(initial_splash=initial_splash)" in source
    assert "create_startup_managed_ready_factory_ports()" not in source
    assert "create_startup_managed_ready_factory_ports()" in support_graph_source
    assert "StartupManagedReadyFactoryPorts(" not in source
    assert "create_runtime_compatibility_checker=(" not in source
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
