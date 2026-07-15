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

"""Verify optional Qt message tracing ownership."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.app.bootstrap.qt_message_trace import (
    FONT_WARNING_SNIPPET,
    QT_MESSAGE_TRACE_ENV,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
QT_MESSAGE_TRACE_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "qt_message_trace.py"
)
FORBIDDEN_QT_TRACE_IMPORT_PREFIXES = (
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.infrastructure.comfy.process_manager",
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


def test_qt_message_trace_imports_only_qt_trace_boundaries() -> None:
    """Qt message tracing may own Qt handler installation but not broader startup."""

    imported_modules = _imported_module_names(QT_MESSAGE_TRACE_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_QT_TRACE_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_no_longer_owns_qt_message_trace_policy() -> None:
    """The startup facade should delegate optional Qt message trace installation."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")

    assert "def install_qt_message_trace_handler" not in source
    assert "qInstallMessageHandler" not in source
    assert QT_MESSAGE_TRACE_ENV not in source
    assert FONT_WARNING_SNIPPET not in source
