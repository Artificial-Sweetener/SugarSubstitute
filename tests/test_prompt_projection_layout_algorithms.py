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

"""Pure tests for prompt projection layout algorithms."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from substitute.presentation.editor.prompt_editor.projection import (
    layout_engine as projection_layout_module,
)
from substitute.presentation.editor.prompt_editor.projection.line_layout import (
    tag_keep_source_ranges_for_layout,
)


class _Rect:
    """Minimal rect stand-in for layout reflow decisions."""

    def __init__(self, right_edge: float) -> None:
        """Store the right edge returned to the layout algorithm."""

        self._right_edge = right_edge

    def right(self) -> float:
        """Return the configured right edge."""

        return self._right_edge


def test_projection_layout_algorithms_import_no_qt_or_application_services() -> None:
    """Pure layout algorithm tests must not gain presentation or app dependencies."""

    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_roots = {
        "PySide6",
        "qfluentwidgets",
        "substitute.application",
        "tests.prompt_projection_test_helpers",
        "tests.prompt_projection_surface_test_helpers",
    }
    forbidden_imports = tuple(
        imported
        for imported in _imported_modules(tree)
        if any(
            imported == forbidden or imported.startswith(f"{forbidden}.")
            for forbidden in forbidden_roots
        )
    )

    assert forbidden_imports == ()


def test_projection_layout_infers_edited_tag_keep_range_from_source_text() -> None:
    """Optimistic segment drops must not bypass kept-tag reflow safety."""

    source_text = "alpha beta, test test test, omega"
    edited_word_start = source_text.index("test test test") + len("test test ")
    line = SimpleNamespace(
        source_start=edited_word_start,
        source_content_start=edited_word_start,
        source_content_end=len(source_text),
        rect=_Rect(64.0),
    )
    document_view = SimpleNamespace(
        source_text=source_text,
        segments=(),
    )

    requires_reflow = projection_layout_module._plain_edit_requires_tag_keep_reflow(  # noqa: SLF001
        cast(Any, document_view),
        previous_source_text=source_text,
        lines=(cast(Any, line),),
        line=cast(Any, line),
        line_index=0,
        edit_start=edited_word_start + 2,
        edit_end=edited_word_start + 2,
        replacement_text="x",
        source_delta=1,
        width_delta=1.0,
        content_right=10000.0,
    )

    assert requires_reflow is True


def test_projection_layout_keeps_short_tag_from_source_text() -> None:
    """Short comma tags should be inferred directly from source text."""

    source_text = (
        "test test test, test test test test test, "
        "test test test, test test test, test,"
    )
    document_view = SimpleNamespace(
        source_text=source_text,
        segments=(),
    )

    assert (0, len("test test test,")) in tag_keep_source_ranges_for_layout(
        cast(Any, document_view)
    )


def test_projection_layout_does_not_keep_partial_tag_at_probe_limit() -> None:
    """A bounded reflow probe must not treat its artificial cutoff as a tag end."""

    source_text = "alpha beta, gamma delta, omega"
    source_limit = source_text.index("gamma delta") + len("gamma")
    document_view = SimpleNamespace(
        source_text=source_text,
        segments=(),
    )

    ranges = tag_keep_source_ranges_for_layout(
        cast(Any, document_view),
        source_limit=source_limit,
    )

    assert ranges == ((0, len("alpha beta,")),)


def _imported_modules(tree: ast.AST) -> tuple[str, ...]:
    """Return fully qualified module names imported by a parsed Python file."""

    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
            continue
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append(node.module)
    return tuple(modules)
