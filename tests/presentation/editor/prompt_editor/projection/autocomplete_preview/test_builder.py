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

"""Contracts for prompt projection autocomplete preview construction."""

from __future__ import annotations


from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
    PromptProjectionInlinePreview,
    PromptProjectionTransientState,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    OBJECT_REPLACEMENT_CHARACTER,
    PromptProjectionRunKind,
)
from substitute.presentation.editor.prompt_editor.projection.builder import (
    PromptProjectionBuilder,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)
from tests.support.prompt_editor.autocomplete_support import prompt_syntax_profile
from tests.support.prompt_editor.projection_engine_support import (
    StaticPromptWildcardCatalogGateway,
)


def test_builder_inserts_autocomplete_preview_as_non_source_backed_run() -> None:
    """Builder-owned ghost runs should reserve projection text without source text."""

    projection = _build_projection(
        "alpha omega",
        transient_state=PromptProjectionTransientState(
            autocomplete_preview=PromptProjectionInlinePreview(
                source_position=len("alpha "),
                suffix_text="bright ",
            )
        ),
    )

    assert projection.source_text == "alpha omega"
    assert projection.projection_text == "alpha bright omega"
    assert [run.display_text for run in projection.runs] == [
        "alpha ",
        "bright ",
        "omega",
    ]
    ghost_run = projection.runs[1]
    assert ghost_run.ghosted is True
    assert ghost_run.source_backed is False
    assert ghost_run.source_start == len("alpha ")
    assert ghost_run.source_end == len("alpha ")
    assert tuple(ghost_run.source_positions) == (6,) * (len("bright ") + 1)


def test_builder_caret_map_skips_autocomplete_preview_text() -> None:
    """Ghost text should not create editable projection caret positions."""

    projection = _build_projection(
        "omega",
        transient_state=PromptProjectionTransientState(
            autocomplete_preview=PromptProjectionInlinePreview(
                source_position=0,
                suffix_text="bright ",
            )
        ),
    )

    caret_state = projection.caret_map.state_for_source_position(0)
    assert projection.projection_text == "bright omega"
    assert projection.caret_map.projection_position_for_state(caret_state) == 0
    assert not projection.caret_map.has_projection_position(len("bright "))


def test_builder_preserves_downstream_token_runs_after_preview() -> None:
    """Autocomplete preview insertion should not rewrite unrelated token runs."""

    projection = _build_projection(
        "alpha (cat:1.05) omega",
        transient_state=PromptProjectionTransientState(
            autocomplete_preview=PromptProjectionInlinePreview(
                source_position=len("alpha "),
                suffix_text="bright ",
            )
        ),
    )

    assert projection.projection_text == (
        "alpha bright "
        + OBJECT_REPLACEMENT_CHARACTER
        + "cat"
        + OBJECT_REPLACEMENT_CHARACTER
        + " omega"
    )
    assert projection.runs[2].kind is PromptProjectionRunKind.INLINE_OBJECT
    assert projection.runs[2].renderer_key == "emphasis_prefix"


def test_builder_omits_preview_inside_collapsed_token() -> None:
    """Collapsed inline objects should not receive parallel ghost placement."""

    projection = _build_projection(
        r"<lora:Unknown\Thing:0.8>",
        transient_state=PromptProjectionTransientState(
            autocomplete_preview=PromptProjectionInlinePreview(
                source_position=len("<lora:Unknown"),
                suffix_text=r"\Thing",
            )
        ),
    )

    assert projection.projection_text == OBJECT_REPLACEMENT_CHARACTER
    assert all(not run.ghosted for run in projection.runs)


def _build_projection(
    text: str,
    *,
    transient_state: PromptProjectionTransientState | None = None,
) -> PromptProjectionDocument:
    """Build a projected document with optional active transient state."""

    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(StaticPromptWildcardCatalogGateway({}))
    document_view = document_service.build_document_view(text)
    render_plan = syntax_service.build_render_plan(
        document_view,
        prompt_syntax_profile("emphasis", "wildcard", "lora"),
    )
    return PromptProjectionBuilder().build_projection(
        document_view,
        render_plan,
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=PromptProjectionSession(),
        transient_state=transient_state,
    )
