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

"""Contract tests for speculative prompt projection incremental edits."""

from __future__ import annotations


from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.projection.incremental_edit_contracts import (
    PromptProjectionIncrementalEdit,
)
from substitute.presentation.editor.prompt_editor.projection.plain_text_document_editor import (
    PromptPlainTextDocumentEditor,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)


from .support import _scene_projection_document


def test_incremental_scene_title_insert_updates_token_and_later_source_geometry() -> (
    None
):
    """Scene title growth should update its token and shift later scenes locally."""

    previous_text = "**One\nbody\n**Two\nmore"
    insert_at = len("**One")
    next_text = previous_text[:insert_at] + "X" + previous_text[insert_at:]
    editor = PromptPlainTextDocumentEditor()

    result = editor.try_build_plain_text_edit(
        PromptProjectionIncrementalEdit(
            start=insert_at,
            end=insert_at,
            replacement_text="X",
            previous_source_text=previous_text,
            next_source_text=next_text,
        ),
        previous_document=_scene_projection_document(previous_text),
        document_view=PromptDocumentService().build_document_view(next_text),
        render_plan=PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
        active_span_range=None,
        decoration_accent_ranges=(),
        scene_error_keys=frozenset(),
    )

    assert result is not None
    scene_tokens = result.projection_document.tokens
    assert tuple(token.display_text for token in scene_tokens) == ("OneX", "Two")
    assert scene_tokens[0].content_end == len("**OneX")
    assert scene_tokens[1].source_start == previous_text.index("**Two") + 1
    assert result.projection_document.projection_text == "OneX\nbody\nTwo\nmore"
    canonical_document = _scene_projection_document(next_text)
    assert tuple(
        (stop.state.source_position, stop.projection_position, stop.state.placement)
        for stop in result.projection_document.caret_map.stops
    ) == tuple(
        (stop.state.source_position, stop.projection_position, stop.state.placement)
        for stop in canonical_document.caret_map.stops
    )


def test_incremental_scene_title_trailing_space_matches_canonical_projection() -> None:
    """A trailing title space should remain visible without changing semantic text."""

    previous_text = "**scene"
    next_text = f"{previous_text} "
    editor = PromptPlainTextDocumentEditor()

    result = editor.try_build_plain_text_edit(
        PromptProjectionIncrementalEdit(
            start=len(previous_text),
            end=len(previous_text),
            replacement_text=" ",
            previous_source_text=previous_text,
            next_source_text=next_text,
        ),
        previous_document=_scene_projection_document(previous_text),
        document_view=PromptDocumentService().build_document_view(next_text),
        render_plan=PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
        active_span_range=None,
        decoration_accent_ranges=(),
        scene_error_keys=frozenset(),
    )

    assert result is not None
    assert result.projection_document.projection_text == "scene "
    assert result.projection_document.tokens[0].display_text == "scene"
    canonical_document = _scene_projection_document(next_text)
    assert result.projection_document.runs == canonical_document.runs
    assert result.projection_document.tokens == canonical_document.tokens
    assert tuple(result.projection_document.caret_map.stops) == tuple(
        canonical_document.caret_map.stops
    )


def test_incremental_scene_title_boundary_rejects_newline_topology_change() -> None:
    """A newline after a scene title must use the canonical topology builder."""

    previous_text = "**Scene"
    next_text = f"{previous_text}\n"
    editor = PromptPlainTextDocumentEditor()

    result = editor.try_build_plain_text_edit(
        PromptProjectionIncrementalEdit(
            start=len(previous_text),
            end=len(previous_text),
            replacement_text="\n",
            previous_source_text=previous_text,
            next_source_text=next_text,
        ),
        previous_document=_scene_projection_document(previous_text),
        document_view=PromptDocumentService().build_document_view(next_text),
        render_plan=PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
        active_span_range=None,
        decoration_accent_ranges=(),
        scene_error_keys=frozenset(),
    )

    assert result is None


def test_incremental_scene_title_edit_recomputes_duplicate_style() -> None:
    """A local title edit should immediately restyle the newly duplicate scene."""

    previous_text = "**One\nbody\n**Owe\nmore"
    replace_at = previous_text.index("w")
    next_text = previous_text[:replace_at] + "n" + previous_text[replace_at + 1 :]
    editor = PromptPlainTextDocumentEditor()

    result = editor.try_build_plain_text_edit(
        PromptProjectionIncrementalEdit(
            start=replace_at,
            end=replace_at + 1,
            replacement_text="n",
            previous_source_text=previous_text,
            next_source_text=next_text,
        ),
        previous_document=_scene_projection_document(previous_text),
        document_view=PromptDocumentService().build_document_view(next_text),
        render_plan=PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
        active_span_range=None,
        decoration_accent_ranges=(),
        scene_error_keys=frozenset(),
    )

    assert result is not None
    scene_tokens = result.projection_document.tokens
    assert tuple(token.value_text for token in scene_tokens) == ("one", "one")
    assert tuple(token.style_variant for token in scene_tokens) == (
        "scene_title",
        "scene_error",
    )
    assert result.projection_document.projection_text == "One\nbody\nOne\nmore"
