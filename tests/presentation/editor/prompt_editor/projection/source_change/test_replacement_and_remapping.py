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

"""Test source replacement and semantic-remapping contracts."""

from __future__ import annotations


from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.application.prompt_editor.document.view_mapper import (
    prompt_document_view_from_domain,
)
from substitute.domain.prompt.document.parser import parse_prompt_document
from substitute.presentation.editor.prompt_editor.core.editing.source_buffer import (
    PromptSourceSnapshot,
)
from substitute.presentation.editor.prompt_editor.core.state.editor_state import (
    PromptEditorState,
)

from .commit_builders import (
    _projection_session,
    _range_commit,
    _source_change_applier,
)
from .source_change_host import _SourceChangeHost
from .projection_state import _ProjectionDocument


def test_source_change_applier_applies_source_replacement_through_ports() -> None:
    """Committed replacement should update mirror, caret, diagnostics, and signals."""

    session = _projection_session("alpha")
    commit = _range_commit(
        session,
        start=5,
        end=5,
        replacement_text=" beta",
    )
    host = _SourceChangeHost()
    applier = _source_change_applier(host)

    applier.apply_edit_commit(commit)

    assert host.marked_source_changes == [(False, 8)]
    assert host._source_document_adapter.font_syncs == 1
    assert host._source_document_adapter.range_fallback_calls == [
        ("alpha beta", "alpha", 5)
    ]
    assert host._mouse_handler.cleared == 1
    assert host.caret_state_updates == [(10, 10, "fast_source_replace")]
    assert host.textChanged.count == 1
    assert host.cursorPositionChanged.count == 1
    assert host.horizontal_origin_marks == 1


def test_source_change_applier_uses_semantic_remapper_for_optimistic_state() -> None:
    """Immediate source changes should consume the pure semantic remap service."""

    session = _projection_session("alpha")
    commit = _range_commit(
        session,
        start=5,
        end=5,
        replacement_text="!",
    )
    host = _SourceChangeHost()
    host._projection_freshness_controller.deferral_reason = (
        "plain_single_character_requires_layout"
    )
    host._session.expanded_source_range = (0, 5)
    applier = _source_change_applier(host)

    applier.apply_edit_commit(commit)

    assert host._editor_state.semantic.document.source_text == "alpha"
    assert host._editor_state.edit_semantic.document.source_text == "alpha!"
    assert host._editor_state.semantic.render_plan.renderer_views == ()
    assert host._session.expanded_source_range == (0, 6)
    request = host._edit_pipeline.requests[-1]
    assert not request.direct_deferred_feedback_allowed
    assert request.wrap_reflow_deferrable


def test_source_change_applier_does_not_stack_unrepresented_wrap_deferral() -> None:
    """Do not defer again when semantic state was already behind live source."""

    session = _projection_session("alpha")
    first_commit = _range_commit(
        session,
        start=5,
        end=5,
        replacement_text="<",
    )
    host = _SourceChangeHost()
    applier = _source_change_applier(host)
    applier.apply_edit_commit(first_commit)
    host._projection_freshness_controller.deferral_reason = (
        "plain_single_character_requires_layout"
    )
    second_commit = _range_commit(
        session,
        start=6,
        end=6,
        replacement_text="h",
    )

    applier.apply_edit_commit(second_commit)

    request = host._edit_pipeline.requests[-1]
    assert not request.direct_deferred_feedback_allowed
    assert not request.wrap_reflow_deferrable


def test_source_change_applier_uses_applied_normalized_edit_for_region_topology() -> (
    None
):
    """Normalized separator completion should publish every region immediately."""

    source = "global\n[SEP]\n[SEPregional"
    completion_position = source.index("regional")
    session = _projection_session(source)
    commit = _range_commit(
        session,
        start=completion_position,
        end=completion_position,
        replacement_text="]",
        exact_source=False,
    )
    host = _SourceChangeHost()
    host._editor_state = PromptEditorState[
        PromptDocumentView,
        PromptSyntaxRenderPlan,
        _ProjectionDocument,
        object,
        object,
    ](
        source=PromptSourceSnapshot(source_text=source, source_revision=7),
        semantic_document=prompt_document_view_from_domain(
            parse_prompt_document(source)
        ),
        render_plan=host._editor_state.semantic.render_plan,
        projection_document=_ProjectionDocument(source),
    )
    applier = _source_change_applier(host)

    applier.apply_edit_commit(commit)

    normalized_source = "global\n[SEP]\n[SEP]\nregional"
    request = host._edit_pipeline.requests[-1]
    assert request.source_edit_start == completion_position
    assert request.source_edit_end == completion_position
    assert request.source_edit_replacement_text == "]\n"
    assert host._editor_state.semantic.document.source_text == source
    assert host._editor_state.edit_semantic.document.source_text == normalized_source
    projection_document = host._editor_state.edit_semantic.document
    assert len(projection_document.region_structure.separators) == 2
    assert len(projection_document.region_structure.partitions) == 3
    assert host._source_document_adapter.range_fallback_calls == [
        (normalized_source, source, completion_position)
    ]
