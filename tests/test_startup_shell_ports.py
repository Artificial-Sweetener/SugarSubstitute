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

"""Tests for concrete shell composition startup port adapters."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.app.bootstrap import composition, startup_shell_ports
from substitute.app.bootstrap.startup_ports import StartupShellCompositionPorts

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SHELL_PORTS_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_shell_ports.py"
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
    "subprocess",
)


def test_create_startup_shell_composition_ports_groups_concrete_ports() -> None:
    """Concrete shell port factory should bind shell composition adapters."""

    ports = startup_shell_ports.create_startup_shell_composition_ports()

    assert isinstance(ports, StartupShellCompositionPorts)
    assert ports.build_main_window is composition.build_main_window
    assert ports.show_main_window is composition.show_main_window
    assert ports.show_built_main_window is composition.show_built_main_window
    assert ports.main_window_for_shell is composition.main_window_widget
    assert (
        ports.build_model_metadata_refresh_service
        is composition.build_model_metadata_refresh_service
    )
    assert ports.is_comfy_http_ready is composition.is_comfy_http_ready


def test_startup_shell_ports_imports_no_forbidden_boundaries() -> None:
    """Shell port binding should avoid Qt, infrastructure, and process imports."""

    imported_modules = _imported_module_names(SHELL_PORTS_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_ADAPTER_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_shell_port_construction() -> None:
    """Startup should request one concrete shell composition port bundle."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    support_graph_source = SUPPORT_GRAPH_SOURCE.read_text(encoding="utf-8")

    assert "create_startup_support_graph(initial_splash=initial_splash)" in source
    assert "create_startup_shell_composition_ports()" not in source
    assert "create_startup_shell_composition_ports()" in support_graph_source
    assert "StartupShellCompositionPorts(" not in source
    assert "build_main_window=composition.build_main_window" not in source
    assert "show_main_window=composition.show_main_window" not in source
    assert "show_built_main_window=composition.show_built_main_window" not in source
    assert "main_window_for_shell=composition.main_window_widget" not in source
    assert "composition.build_model_metadata_refresh_service" not in source
    assert "is_comfy_http_ready=composition.is_comfy_http_ready" not in source


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
