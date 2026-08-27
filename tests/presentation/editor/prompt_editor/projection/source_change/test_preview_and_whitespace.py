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

"""Test preview and whitespace-replacement contracts."""

from __future__ import annotations


from .commit_builders import (
    _projection_session,
    _range_commit,
    _source_change_applier,
)
from .source_change_host import _SourceChangeHost
from .qt_lifecycle import _ensure_qapp


def test_source_change_applier_rebuilds_preview_active_replacements() -> None:
    """Autocomplete preview requires immediate projection for source replacements."""

    _ensure_qapp()
    session = _projection_session("alpha")
    commit = _range_commit(
        session,
        start=5,
        end=5,
        replacement_text="x",
    )
    host = _SourceChangeHost()
    host._projection_freshness_controller.can_defer_projection = True
    host._session.autocomplete_preview = object()
    applier = _source_change_applier(host)

    applier.apply_edit_commit(commit)

    assert host.marked_source_changes == [(False, 8)]
    assert host.autocomplete_preview_clear_count == 1
    assert host._session.autocomplete_preview_updates == [None]
    assert host._source_document_adapter.range_fallback_calls == [
        ("alphax", "alpha", 5)
    ]
    assert host.caret_state_updates == [(6, 6, "fast_source_replace")]
    assert host._transient_edit_overlays.insertion_overlay is None
    assert host.transient_insert_paint_updates == 0
    assert host.transient_delete_paint_updates == 0
    assert host.textChanged.count == 1


def test_source_change_applier_rebuilds_whitespace_replacements() -> None:
    """Whitespace edits require immediate projection to clear stale inline previews."""

    _ensure_qapp()
    session = _projection_session("alpha")
    commit = _range_commit(
        session,
        start=5,
        end=5,
        replacement_text=" ",
    )
    host = _SourceChangeHost()
    host._projection_freshness_controller.can_defer_projection = True
    applier = _source_change_applier(host)

    applier.apply_edit_commit(commit)

    assert host.marked_source_changes == [(False, 8)]
    assert host._source_document_adapter.range_fallback_calls == [
        ("alpha ", "alpha", 5)
    ]
    assert host.caret_state_updates == [(6, 6, "fast_source_replace")]
    assert host._transient_edit_overlays.insertion_overlay is None
    assert host.textChanged.count == 1
