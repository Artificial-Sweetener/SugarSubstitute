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

"""Contracts for prompt projection session and transient state."""

from __future__ import annotations


from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.application.ports import PromptWildcardResolution
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.projection.builder import (
    PromptProjectionBuilder,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
    PromptTransientNeutralEmphasisOwner,
)

from .support import _build_projection
from tests.support.prompt_editor.autocomplete_support import prompt_syntax_profile
from tests.support.prompt_editor.projection_engine_support import (
    StaticPromptWildcardCatalogGateway,
)


def test_projection_builder_marks_active_tokens_and_respects_expanded_session_ranges() -> (
    None
):
    """Active tokens should be tagged, and expanded spans should remain raw source."""

    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(StaticPromptWildcardCatalogGateway({}))
    document_view = document_service.build_document_view("(cat:1.05), dog")
    render_plan = syntax_service.build_render_plan(
        document_view,
        prompt_syntax_profile("emphasis", "wildcard"),
    )
    builder = PromptProjectionBuilder()

    active_projection = builder.build_projection(
        document_view,
        render_plan,
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
        active_span_range=(0, 10),
    )
    expanded_session = PromptProjectionSession(expanded_source_range=(0, 10))
    expanded_projection = builder.build_projection(
        document_view,
        render_plan,
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=expanded_session,
        active_span_range=(0, 10),
    )

    assert active_projection.tokens[0].active is True
    assert expanded_projection.tokens == ()
    assert expanded_projection.projection_text == "(cat:1.05), dog"


def test_projection_builder_marks_decorations_for_accent_feedback_ranges() -> None:
    """Builder should tag only requested syntax shells for decoration accent feedback."""

    projection = _build_projection(
        "(cat:1.05), {animal|1}, (dog:1.10)",
        decoration_accent_ranges=((0, 10), (12, 22)),
    )

    assert projection.tokens[0].decoration_accented is True
    assert projection.tokens[1].decoration_accented is True
    assert projection.tokens[2].decoration_accented is False


def test_projection_builder_exposes_internal_caret_stops_for_emphasis_and_wildcards() -> (
    None
):
    """Decorated source-backed content should expose its exact caret boundaries."""

    projection = _build_projection(
        "(cat:1.05), {animal}",
        wildcard_resolutions={
            ("animal", "simple", None): PromptWildcardResolution(
                identifier="animal",
                wildcard_form="simple",
                exists=True,
            ),
        },
    )

    emphasis_token = projection.tokens[0]
    wildcard_token = projection.tokens[1]
    emphasis_states = [
        stop.state
        for stop in projection.caret_map.stops
        if stop.state.token_id == emphasis_token.token_id
    ]
    wildcard_states = [
        stop.state
        for stop in projection.caret_map.stops
        if stop.state.token_id == wildcard_token.token_id
    ]

    assert [state.source_position for state in emphasis_states] == [0, 1, 2, 3, 4, 10]
    assert [state.source_position for state in wildcard_states] == list(range(12, 21))


def test_projection_builder_can_project_transient_neutral_emphasis_without_source_syntax() -> (
    None
):
    """A transient neutral shell should project as emphasis while source text stays plain."""

    session = PromptProjectionSession()
    session.set_transient_neutral_emphasis(
        content_start=0,
        content_end=3,
        owner=PromptTransientNeutralEmphasisOwner.CARET,
    )

    projection = _build_projection("cat", session=session)

    assert projection.source_text == "cat"
    assert len(projection.tokens) == 1
    token = projection.tokens[0]
    assert token.kind is PromptProjectionTokenKind.EMPHASIS
    assert token.synthetic is True
    assert token.display_text == "cat"
    assert token.value_text == "1.00"
    assert token.content_range == (0, 3)


def test_real_weight_supersedes_stale_neutral_preview_after_wheel_step() -> None:
    """Publish one real token when a prior neutral preview still overlaps it."""

    session = PromptProjectionSession()
    session.set_transient_neutral_emphasis(
        content_start=0,
        content_end=3,
        owner=PromptTransientNeutralEmphasisOwner.OVERLAY,
    )

    projection = _build_projection("(cat:0.95)", session=session)

    assert len(projection.tokens) == 1
    assert projection.tokens[0].synthetic is False
    assert projection.tokens[0].value_text == "0.95"


def test_neutral_preview_inside_real_emphasis_remains_nested() -> None:
    """Keep a deliberate neutral inner preview inside a weighted phrase."""

    session = PromptProjectionSession()
    session.set_transient_neutral_emphasis(
        content_start=1,
        content_end=4,
        owner=PromptTransientNeutralEmphasisOwner.OVERLAY,
    )

    projection = _build_projection("(cat dog:1.15)", session=session)

    assert [token.value_text for token in projection.tokens] == ["1.15", "1.00"]
    assert projection.tokens[0].synthetic is False
    assert projection.tokens[1].synthetic is True
