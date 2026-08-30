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

"""Test no-op and scroll-behavior contracts."""

from __future__ import annotations


from substitute.presentation.editor.prompt_editor.commands.contracts import (
    PromptEditApplicationState,
)

from .commit_builders import (
    _document_commit,
    _projection_session,
    _range_commit,
    _source_change_applier,
)
from .source_change_host import _SourceChangeHost


def test_source_change_applier_preserves_no_op_source_change_as_cursor_update() -> None:
    """No-op source replacements should not mirror text or emit source signals."""

    session = _projection_session("alpha")
    commit = _range_commit(
        session,
        start=2,
        end=2,
        replacement_text="",
        record_undo=False,
    )
    host = _SourceChangeHost()
    applier = _source_change_applier(host)

    applier.apply_edit_commit(commit)

    assert host.cursor_position_updates == [(2, 2)]
    assert host._source_document_adapter.range_fallback_calls == []
    assert host.textChanged.count == 0
    assert host.cursorPositionChanged.count == 0


def test_source_change_applier_handles_full_source_scroll_and_geometry_warm() -> None:
    """Full-source applications should preserve reset-scroll and warm intents."""

    session = _projection_session("alpha")
    commit = _document_commit(
        session,
        text="omega",
        application_state=PromptEditApplicationState(
            reset_scroll_to_top=True,
            schedule_geometry_reuse_warm_reason="full_source",
        ),
    )
    host = _SourceChangeHost()
    applier = _source_change_applier(host)

    applier.apply_edit_commit(commit)

    assert host._scroll_bar.values == [0]
    assert host.geometry_warm_reasons == ["full_source"]
    assert host._source_document_adapter.range_fallback_calls == [("omega", "alpha", 0)]
    assert host.textChanged.count == 1


def test_source_change_applier_skips_projection_work_for_no_op_document_commit() -> (
    None
):
    """No-op document commits should preserve lineage while applying viewport intent."""

    session = _projection_session("alpha")
    commit = _document_commit(
        session,
        text="alpha",
        application_state=PromptEditApplicationState(
            reset_scroll_to_top=True,
            schedule_geometry_reuse_warm_reason="same_source",
        ),
    )
    host = _SourceChangeHost()
    semantic_identity = host._editor_state.semantic.identity
    projection_identity = host._editor_state.projection.identity
    applier = _source_change_applier(host)

    applier.apply_edit_commit(commit)

    assert host.cursor_position_updates == [(5, 5)]
    assert host._editor_state.semantic.identity is semantic_identity
    assert host._editor_state.projection.identity is projection_identity
    assert host._source_document_adapter.range_fallback_calls == []
    assert host._edit_pipeline.requests == []
    assert host._scroll_bar.values == [0]
    assert host.geometry_warm_reasons == ["same_source"]
    assert host.textChanged.count == 0
