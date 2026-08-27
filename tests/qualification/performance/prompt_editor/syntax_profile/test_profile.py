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

"""Tests for prompt-editor performance syntax-profile helpers."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.devtools.prompt_editor_performance import (
    syntax_profile as syntax_profile_module,
)
from substitute.devtools.prompt_editor_performance.syntax_profile import (
    prompt_syntax_profile,
)


FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "tests",
    "tools",
)


def test_prompt_editor_performance_syntax_profile_imports_no_qt_or_tests() -> None:
    """Keep syntax-profile helpers reusable outside Qt and test processes."""

    source_path = Path(syntax_profile_module.__file__).resolve()
    imported_modules = _imported_module_names(
        ast.parse(source_path.read_text(encoding="utf-8"))
    )

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_prompt_syntax_profile_returns_default_when_empty() -> None:
    """Preserve the default syntax profile for empty benchmark input."""

    profile = prompt_syntax_profile()

    assert profile.enabled_syntaxes == ("emphasis", "wildcard", "lora")


def test_prompt_syntax_profile_returns_explicit_syntax_tuple() -> None:
    """Preserve explicit syntax order for benchmark scenarios."""

    profile = prompt_syntax_profile("emphasis", "wildcard", "lora")

    assert profile.enabled_syntaxes == ("emphasis", "wildcard", "lora")


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from one Python source tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
