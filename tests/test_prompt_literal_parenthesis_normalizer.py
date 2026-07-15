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

"""Tests for prompt literal-parenthesis normalization ownership."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.application.prompt_editor import (
    normalize_literal_parentheses_for_storage as facade_normalize_for_storage,
)
from substitute.application.prompt_editor.prompt_literal_parenthesis_normalizer import (
    normalize_literal_parentheses_for_storage,
    normalize_literal_parentheses_for_typed_edit,
)

_FORBIDDEN_IMPORT_ROOTS = {
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.app",
    "substitute.infrastructure",
    "substitute.presentation",
}


def test_literal_parenthesis_normalizer_stabilizes_implicit_emphasis() -> None:
    """Make balanced implicit groups explicit while preserving separators."""

    assert normalize_literal_parentheses_for_storage("alpha (medium), beta") == (
        "alpha (medium:1.10), beta"
    )


def test_literal_parenthesis_normalizer_preserves_plausible_weighted_emphasis() -> None:
    """Keep intentional emphasis shells live during storage normalization."""

    assert (
        normalize_literal_parentheses_for_storage("(painting:1.2)") == "(painting:1.2)"
    )
    assert normalize_literal_parentheses_for_storage("alpha, (painting:1.2)") == (
        "alpha, (painting:1.2)"
    )


def test_literal_parenthesis_normalizer_typed_edit_uses_same_canonical_shape() -> None:
    """Normalize typed implicit groups with the same stable emphasis rules."""

    assert normalize_literal_parentheses_for_typed_edit("alpha (medium)") == (
        "alpha (medium:1.10)"
    )


def test_application_facade_exports_literal_normalizer_owner() -> None:
    """Keep the application facade bound directly to the normalizer owner."""

    assert facade_normalize_for_storage is normalize_literal_parentheses_for_storage


def test_literal_parenthesis_normalizer_has_no_qt_presentation_or_adapter_imports() -> (
    None
):
    """Keep literal-parenthesis normalization portable across host environments."""

    source_path = (
        Path(__file__).parents[1]
        / "substitute"
        / "application"
        / "prompt_editor"
        / "prompt_literal_parenthesis_normalizer.py"
    )
    syntax_tree = ast.parse(source_path.read_text(encoding="utf-8"))

    imported_modules: set[str] = set()
    for node in ast.walk(syntax_tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)

    offenders = sorted(
        imported_module
        for imported_module in imported_modules
        if any(
            imported_module == forbidden_root
            or imported_module.startswith(f"{forbidden_root}.")
            for forbidden_root in _FORBIDDEN_IMPORT_ROOTS
        )
    )

    assert offenders == []
