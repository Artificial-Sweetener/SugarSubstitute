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

"""Contracts for literal parenthesis projection rendering."""

from __future__ import annotations


from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRunKind,
)

from .support import _build_projection


def test_projection_builder_projected_mode_hides_literal_parenthesis_escapes() -> None:
    """Projected mode should hide storage-only paren escapes in plain text runs."""

    projection = _build_projection(r"painting \(medium\)")

    assert projection.display_mode is PromptProjectionDisplayMode.PROJECTED
    assert projection.source_text == r"painting \(medium\)"
    assert projection.projection_text == "painting (medium)"
    assert projection.tokens == ()
    assert len(projection.runs) == 1
    assert projection.runs[0].kind is PromptProjectionRunKind.TEXT
    assert projection.runs[0].display_text == "painting (medium)"


def test_projection_builder_projects_escaped_weight_shape_as_literal_plain_text() -> (
    None
):
    """Escaped weighted-looking groups should stay plain visible text without tokens."""

    projection = _build_projection(r"\(painting:1.2\)")

    assert projection.projection_text == "(painting:1.2)"
    assert projection.tokens == ()
    assert len(projection.runs) == 1
    assert projection.runs[0].kind is PromptProjectionRunKind.TEXT
    assert projection.runs[0].display_text == "(painting:1.2)"


def test_projection_builder_raw_mode_preserves_literal_parenthesis_escapes_verbatim() -> (
    None
):
    """Raw mode should continue to expose the exact stored escaped source text."""

    projection = _build_projection(
        r"painting \(medium\)",
        display_mode=PromptProjectionDisplayMode.RAW,
    )

    assert projection.projection_text == r"painting \(medium\)"
    assert len(projection.runs) == 1
    assert projection.runs[0].display_text == r"painting \(medium\)"
