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

"""Architecture boundary tests for the Comfy websocket listener facade."""

from __future__ import annotations

import ast
from pathlib import Path

_LISTENER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "websocket_listener.py"
)


def test_websocket_listener_imports_no_qt_or_presentation_modules() -> None:
    """The infrastructure listener must stay independent of Qt presentation code."""

    tree = ast.parse(_LISTENER_MODULE.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)

    forbidden_prefixes = (
        "PySide6",
        "qfluentwidgets",
        "qframelesswindow",
        "substitute.presentation",
    )
    assert {
        module for module in imported_modules if module.startswith(forbidden_prefixes)
    } == set()
