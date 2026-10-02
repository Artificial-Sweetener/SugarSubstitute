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

"""Protect committed source publication from stale or failed semantic preparation."""

from __future__ import annotations

from typing import Literal

import pytest

from substitute.application.prompt_editor.document.view_mapper import (
    prompt_document_view_from_domain,
)
from substitute.application.prompt_editor.projection.syntax_models import (
    PromptSyntaxRenderPlan,
)
from substitute.domain.prompt.document.parser import parse_prompt_document
from substitute.presentation.editor.prompt_editor.commands.contracts import (
    PromptEditApplicationState,
)
from substitute.presentation.editor.prompt_editor.projection.semantic_remap import (
    PromptProjectionOptimisticPromptState,
    PromptProjectionSemanticRemapper,
)

from .commit_builders import (
    _document_commit,
    _projection_session,
    _range_commit,
    _source_change_applier,
)
from .source_change_host import _SourceChangeHost


@pytest.mark.parametrize("stale_source", ["omega", "(omega)"])
@pytest.mark.parametrize("candidate_origin", ["prepared", "remapped"])
def test_source_publication_rejects_semantics_for_different_source(
    monkeypatch: pytest.MonkeyPatch,
    stale_source: str,
    candidate_origin: Literal["prepared", "remapped"],
) -> None:
    """Reject stale semantic pairs even when their source length happens to match."""

    session = _projection_session("alpha")
    host = _SourceChangeHost()
    stale_document = prompt_document_view_from_domain(
        parse_prompt_document(stale_source)
    )
    stale_render_plan = PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=())
    application_state = None
    if candidate_origin == "prepared":
        application_state = PromptEditApplicationState(
            document_view=stale_document,
            render_plan=stale_render_plan,
        )
    else:

        def stale_remap(
            self: PromptProjectionSemanticRemapper,
            **arguments: object,
        ) -> PromptProjectionOptimisticPromptState:
            """Inject a stale collaborator result at the transaction boundary."""

            assert arguments["next_text"] == "bravo"
            return stale_document, stale_render_plan

        monkeypatch.setattr(
            PromptProjectionSemanticRemapper,
            "optimistic_prompt_state_for_source_edit",
            stale_remap,
        )
    commit = _document_commit(
        session, text="bravo", application_state=application_state
    )

    _source_change_applier(host).apply_edit_commit(commit)

    assert session.source_text == host._editor_state.source.source_text == "bravo"
    semantic = host._editor_state.edit_semantic
    assert semantic.document.source_text == "bravo"
    assert semantic.document is not stale_document
    assert semantic.render_plan is not stale_render_plan
    assert semantic.identity.source is host._editor_state.source_identity
    assert host._source_document_adapter.range_fallback_calls[-1][0] == "bravo"
    assert host._edit_pipeline.requests[-1].text == "bravo"
    assert host.caret_state_updates[-1][:2] == (5, 5)
    assert host.textChanged.count == host.cursorPositionChanged.count == 1


def test_semantic_remapper_failure_finishes_publication_and_allows_later_edit(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Recover a failed optimization without leaving source, caret, or signals behind."""

    session = _projection_session("alpha")
    host = _SourceChangeHost()
    applier = _source_change_applier(host)
    first_commit = _document_commit(session, text="bravo")

    def fail_remap(
        self: PromptProjectionSemanticRemapper,
        **arguments: object,
    ) -> PromptProjectionOptimisticPromptState | None:
        """Fail only the optional semantic remapping boundary."""

        assert arguments["next_text"] == "bravo"
        raise RuntimeError("injected semantic remapping failure")

    with monkeypatch.context() as patch:
        patch.setattr(
            PromptProjectionSemanticRemapper,
            "optimistic_prompt_state_for_source_edit",
            fail_remap,
        )
        applier.apply_edit_commit(first_commit)

    assert session.source_text == host._editor_state.source.source_text == "bravo"
    assert host._editor_state.edit_semantic.document.source_text == "bravo"
    assert host._editor_state.edit_semantic.document.segments == ()
    assert host._source_document_adapter.range_fallback_calls[-1][0] == "bravo"
    assert host._edit_pipeline.requests[-1].text == "bravo"
    assert host.caret_state_updates[-1][:2] == (5, 5)
    assert host.textChanged.count == host.cursorPositionChanged.count == 1
    assert any(record.exc_info is not None for record in caplog.records)

    later_commit = _range_commit(session, start=5, end=5, replacement_text="!")
    applier.apply_edit_commit(later_commit)

    assert session.source_text == host._editor_state.source.source_text == "bravo!"
    semantic = host._editor_state.edit_semantic
    assert semantic.document.source_text == "bravo!"
    assert semantic.identity.source is host._editor_state.source_identity
    assert host._source_document_adapter.range_fallback_calls[-1][0] == "bravo!"
    assert host._edit_pipeline.requests[-1].text == "bravo!"
    assert host.caret_state_updates[-1][:2] == (6, 6)
    assert host.textChanged.count == host.cursorPositionChanged.count == 2
