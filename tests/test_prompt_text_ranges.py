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

"""Tests for prompt-editor bounded text range helpers."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.application.prompt_editor.prompt_text_ranges import (
    line_end_within_bounds,
    line_start_within_bounds,
    line_visible_start,
    trim_horizontal_end,
    trim_horizontal_start,
)

_FORBIDDEN_IMPORT_ROOTS = {
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
}


def test_trim_horizontal_start_skips_spaces_and_tabs_inside_bounds() -> None:
    """Skip horizontal leading whitespace without crossing the end."""

    assert trim_horizontal_start("alpha, \t beta", 6, 14) == 9
    assert trim_horizontal_start("alpha, \t ", 6, 9) == 9


def test_trim_horizontal_end_skips_spaces_and_tabs_inside_bounds() -> None:
    """Skip horizontal trailing whitespace without crossing the start."""

    assert trim_horizontal_end("alpha, beta\t  ", 7, 14) == 11
    assert trim_horizontal_end("alpha, \t ", 6, 9) == 6


def test_line_start_within_bounds_uses_latest_line_break_after_lower_bound() -> None:
    """Respect CR, LF, and the supplied lower bound."""

    text = "root\n  alpha\rbeta"

    assert line_start_within_bounds(text, lower_bound=0, position=text.index("b")) == 13
    assert line_start_within_bounds(text, lower_bound=6, position=10) == 6


def test_line_end_within_bounds_uses_earliest_line_break_before_upper_bound() -> None:
    """Stop at the nearest CR or LF inside the upper bound."""

    text = "alpha\r\nbeta\ngamma"

    assert line_end_within_bounds(text, position=0, upper_bound=len(text)) == 5
    assert line_end_within_bounds(text, position=7, upper_bound=len(text)) == 11
    assert line_end_within_bounds(text, position=12, upper_bound=len(text)) == len(text)


def test_line_visible_start_skips_horizontal_whitespace_before_caret() -> None:
    """Stop at the caret when the line is blank so far."""

    text = "alpha\n\t  beta"
    line_start = text.index("\t")

    assert line_visible_start(text, line_start=line_start, position=len(text)) == 9
    assert line_visible_start(text, line_start=line_start, position=line_start + 2) == 8


def test_prompt_text_ranges_has_no_qt_or_presentation_imports() -> None:
    """Keep text range helpers portable across Qt bindings and non-Qt hosts."""

    source_path = (
        Path(__file__).parents[1]
        / "substitute"
        / "application"
        / "prompt_editor"
        / "prompt_text_ranges.py"
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
