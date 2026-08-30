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

"""Test undo-restoration contracts."""

from __future__ import annotations


from substitute.presentation.editor.prompt_editor.core.editing.commands import (
    PromptUndoEdit,
)

from .commit_builders import (
    _projection_session,
    _projection_undo_snapshot,
    _range_commit,
    _source_change_applier,
)
from .source_change_host import _SourceChangeHost


def test_source_change_applier_restores_undo_state_through_ports() -> None:
    """Restore applications should route exact history state through projection ports."""

    session = _projection_session("alpha")
    _range_commit(
        session,
        start=5,
        end=5,
        replacement_text=" beta",
    )
    commit = session.execute(
        PromptUndoEdit(
            current_snapshot=_projection_undo_snapshot("alpha beta"),
        )
    )
    assert commit is not None
    host = _SourceChangeHost()
    applier = _source_change_applier(host)

    applier.apply_edit_commit(commit)

    assert host._source_document_adapter.replacements == ["alpha"]
    assert host._editor_state.semantic.document.source_text == "alpha"
    assert host._session.expanded_source_range == (0, 5)
    assert host.marked_source_changes == [(False, 9)]
    assert host.rebuilds == 0
    assert len(host._edit_pipeline.requests) == 1
    projection_request = host._edit_pipeline.requests[0]
    assert projection_request.previous_source_text == "alpha"
    assert projection_request.text == "alpha"
    assert projection_request.projection_deferral_reason == "history_restore"
    assert host.caret_visibility_checks == 1
    assert host.caret_blink_restarts == 1
    assert host.textChanged.count == 1
    assert host.cursorPositionChanged.count == 1
