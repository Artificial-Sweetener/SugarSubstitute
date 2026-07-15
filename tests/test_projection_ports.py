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

"""Verify editor projection port boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.presentation.editor.panel import projection_ports


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PORTS_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_ports.py"
)
COORDINATOR_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_coordinator.py"
)
FORBIDDEN_PORT_IMPORT_PREFIXES = (
    "PySide6",
    "qpane",
    "qfluentwidgets",
    "qframelesswindow",
)


def _imported_module_names(source_path: Path) -> set[str]:
    """Return all imported module names from one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_projection_ports_exposes_editor_refresh_panel_protocol() -> None:
    """Projection ports should expose the panel surface without importing the coordinator."""

    assert projection_ports.EditorRefreshPanelProtocol.__name__ == (
        "EditorRefreshPanelProtocol"
    )


def test_projection_ports_do_not_import_qt_or_widget_libraries() -> None:
    """Projection ports should remain portable across Qt bindings."""

    forbidden_imports = tuple(
        sorted(
            imported_module
            for imported_module in _imported_module_names(PORTS_SOURCE)
            if imported_module.startswith(FORBIDDEN_PORT_IMPORT_PREFIXES)
        )
    )

    assert forbidden_imports == ()


def test_projection_coordinator_does_not_own_port_protocol_definitions() -> None:
    """Projection coordinator should import shared ports instead of owning them."""

    source = COORDINATOR_SOURCE.read_text(encoding="utf-8")

    assert "class WidgetProtocol" not in source
    assert "class CubeSectionSessionWidgetProtocol" not in source
    assert "class LayoutItemProtocol" not in source
    assert "class LayoutProtocol" not in source
    assert "class SignalProtocol" not in source
    assert "class ScrollBarProtocol" not in source
    assert "class ScrollAreaProtocol" not in source
    assert "class EditorRefreshPanelProtocol" not in source
