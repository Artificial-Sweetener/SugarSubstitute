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

"""Contracts for prompt projection region and scene topology."""

from __future__ import annotations


from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.application.managed_text_assets.wildcard_text_document_semantics import (
    WildcardTextDocumentSemantics,
)
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretPlacement,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    OBJECT_REPLACEMENT_CHARACTER,
    PromptProjectionRunKind,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.projection.builder import (
    PromptProjectionBuilder,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)

from .support import _build_projection
from tests.support.prompt_editor.autocomplete_support import prompt_syntax_profile
from tests.support.prompt_editor.projection_engine_support import (
    StaticPromptWildcardCatalogGateway,
)


def test_projection_builder_emits_non_inline_structural_region_runs() -> None:
    """Projected separators should become structural rows with only edge caret states."""

    projection = _build_projection("global\n[SEP]\nregional")

    separator_token = next(
        token
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.REGION_SEPARATOR
    )
    separator_run = projection.runs_for_token(separator_token.token_id)[0]
    assert separator_run.kind is PromptProjectionRunKind.STRUCTURAL_ROW
    assert separator_run.renderer_key is None
    assert separator_run.display_text == ""
    assert (
        projection.projection_text == f"global\n{OBJECT_REPLACEMENT_CHARACTER}regional"
    )

    leading_state = projection.caret_map.state_for_source_position(
        separator_token.source_start
    )
    trailing_state = projection.caret_map.state_for_source_position(
        separator_token.source_end,
        prefer_after=True,
    )
    assert leading_state.placement is PromptProjectionCaretPlacement.TOKEN_LEADING_EDGE
    assert (
        trailing_state.placement is PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE
    )
    regional_start = separator_token.source_end + 1
    regional_state = projection.caret_map.state_for_source_position(regional_start)
    assert regional_state.source_position == regional_start
    assert regional_state.placement is PromptProjectionCaretPlacement.PLAIN_TEXT
    assert projection.caret_map.next_state(trailing_state) == regional_state
    assert not any(
        stop.state.placement is PromptProjectionCaretPlacement.TOKEN_CONTENT
        and stop.state.token_id == separator_token.token_id
        for stop in projection.caret_map.stops
    )


def test_projection_builder_exposes_terminal_region_input_caret_after_separator() -> (
    None
):
    """A separator-owned newline should end at a plain regional caret stop."""

    text = "global\n[SEP]\n"
    projection = _build_projection(text)

    terminal_state = projection.caret_map.state_for_source_position(len(text))

    assert terminal_state.source_position == len(text)
    assert terminal_state.placement is PromptProjectionCaretPlacement.PLAIN_TEXT
    assert projection.caret_map.resolve_state(terminal_state) == terminal_state


def test_projection_builder_keeps_region_separator_literal_in_raw_mode() -> None:
    """Raw mode should expose exact separator source without structural projection."""

    projection = _build_projection(
        "global\r\n[SEP]\r\nregional",
        display_mode=PromptProjectionDisplayMode.RAW,
    )

    assert projection.projection_text == "global\r\n[SEP]\r\nregional"
    assert not any(
        run.kind is PromptProjectionRunKind.STRUCTURAL_ROW for run in projection.runs
    )
    assert not any(
        token.kind is PromptProjectionTokenKind.REGION_SEPARATOR
        for token in projection.tokens
    )


def test_projection_builder_projects_scene_titles_without_marker_symbol() -> None:
    """Projected scene markers should hide `**` and expose bold title metadata."""

    projection = _build_projection("quality\n**portrait\nstudio portrait")

    scene_token = next(
        token
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.SCENE
    )
    scene_run = next(
        run for run in projection.runs if run.token_id == scene_token.token_id
    )

    assert scene_token.display_text == "portrait"
    assert scene_token.content_range == (10, 18)
    assert scene_token.style_variant == "scene_title"
    assert scene_run.display_text == "portrait"
    assert scene_run.text_style_variant == "scene_title"
    assert "**portrait" not in projection.projection_text
    assert "portrait" in projection.projection_text


def test_projection_builder_preserves_trailing_scene_title_spaces() -> None:
    """Projected scene editing should retain every source-backed title boundary."""

    projection = _build_projection("**scene  ")
    scene_token = next(
        token
        for token in projection.tokens
        if token.kind is PromptProjectionTokenKind.SCENE
    )
    scene_run = next(
        run for run in projection.runs if run.token_id == scene_token.token_id
    )

    assert scene_token.display_text == "scene"
    assert scene_run.display_text == "scene  "
    assert projection.projection_text == "scene  "
    trailing_state = projection.caret_map.state_for_source_position(len("**scene  "))
    assert trailing_state.source_position == len("**scene  ")


def test_projection_builder_keeps_scene_markers_literal_for_wildcard_documents() -> (
    None
):
    """Wildcard semantics should prevent scene-token projection entirely."""

    text = "**portrait\nstudio portrait"
    document_view = PromptDocumentService().build_document_view(text)
    render_plan = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({})
    ).build_render_plan(document_view, prompt_syntax_profile("emphasis", "wildcard"))

    projection = PromptProjectionBuilder(
        document_semantics=WildcardTextDocumentSemantics()
    ).build_projection(
        document_view,
        render_plan,
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
    )

    assert all(
        token.kind is not PromptProjectionTokenKind.SCENE for token in projection.tokens
    )
    assert "**portrait" in projection.projection_text


def test_projection_builder_classifies_only_local_scene_topology_changes() -> None:
    """Scene formation needs canonical projection while title growth does not."""

    builder = PromptProjectionBuilder()

    assert builder.source_edit_requires_canonical_rebuild("**", "**S", start=2, end=2)
    assert not builder.source_edit_requires_canonical_rebuild(
        "**S", "**Sc", start=3, end=3
    )
    assert not builder.source_edit_requires_canonical_rebuild(
        "plain\n**Scene", "plainer\n**Scene", start=5, end=5
    )
    assert builder.source_edit_requires_canonical_rebuild("**S", "**", start=2, end=3)
    assert builder.source_edit_requires_canonical_rebuild(
        "**Scene", "Scene", start=0, end=2
    )


def test_wildcard_projection_topology_ignores_literal_scene_markers() -> None:
    """Scene-disabled documents should retain literal incremental edit behavior."""

    builder = PromptProjectionBuilder(
        document_semantics=WildcardTextDocumentSemantics()
    )

    assert not builder.source_edit_requires_canonical_rebuild(
        "**", "**S", start=2, end=2
    )


def test_projection_builder_marks_duplicate_and_orphan_scene_titles_as_errors() -> None:
    """Invalid scene titles should carry only title-level error style metadata."""

    duplicate_projection = _build_projection("**portrait\none\n**Portrait\ntwo")
    duplicate_scene_tokens = [
        token
        for token in duplicate_projection.tokens
        if token.kind is PromptProjectionTokenKind.SCENE
    ]
    orphan_projection = _build_projection(
        "**hands\ndetail",
        scene_error_keys=frozenset({"hands"}),
    )
    orphan_scene_token = next(
        token
        for token in orphan_projection.tokens
        if token.kind is PromptProjectionTokenKind.SCENE
    )

    assert duplicate_scene_tokens[0].style_variant == "scene_title"
    assert duplicate_scene_tokens[1].style_variant == "scene_error"
    assert orphan_scene_token.style_variant == "scene_error"
