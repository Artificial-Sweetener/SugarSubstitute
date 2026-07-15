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

"""Tests for prompt editor performance Qt application bootstrap."""

from __future__ import annotations

import ast
import os
from pathlib import Path

from PySide6.QtWidgets import QApplication
from pytest import MonkeyPatch

from substitute.devtools.prompt_editor_performance.qt_app import (
    configure_offscreen_platform,
    prompt_performance_application,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
QT_APP_MODULE = (
    PROJECT_ROOT / "substitute" / "devtools" / "prompt_editor_performance" / "qt_app.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "tests",
    "tools",
)


def test_prompt_editor_performance_qt_app_imports_no_widgets_or_tools() -> None:
    """Qt app bootstrap must stay independent from presentation and CLI modules."""

    imported_modules = _imported_module_names(
        ast.parse(QT_APP_MODULE.read_text(encoding="utf-8"))
    )

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_configure_offscreen_platform_sets_default(monkeypatch: MonkeyPatch) -> None:
    """Qt platform setup should default benchmark rendering to offscreen."""

    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)

    configure_offscreen_platform()

    assert os.environ["QT_QPA_PLATFORM"] == "offscreen"


def test_configure_offscreen_platform_preserves_explicit_platform(
    monkeypatch: MonkeyPatch,
) -> None:
    """Explicit host platform choices should not be overwritten."""

    monkeypatch.setenv("QT_QPA_PLATFORM", "minimal")

    configure_offscreen_platform()

    assert os.environ["QT_QPA_PLATFORM"] == "minimal"


def test_prompt_performance_application_returns_qapplication() -> None:
    """Application bootstrap should return a reusable QApplication instance."""

    app = prompt_performance_application()

    assert isinstance(app, QApplication)
    assert prompt_performance_application() is app


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return all imported module names from one Python source tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
