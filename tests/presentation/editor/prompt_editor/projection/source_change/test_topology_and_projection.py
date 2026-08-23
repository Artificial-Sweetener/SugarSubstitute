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

"""Test topology and projection-rebuild contracts."""

from __future__ import annotations


from .commit_builders import (
    _projection_session,
    _range_commit,
    _source_change_applier,
)
from .source_change_host import _SourceChangeHost


def test_source_change_applier_rebuilds_source_derived_projection_structure() -> None:
    """Scene-like structure changes should bypass stale-safe text deferral."""

    session = _projection_session("alpha")
    commit = _range_commit(
        session,
        start=5,
        end=5,
        replacement_text="x",
    )
    host = _SourceChangeHost()
    host._projection_freshness_controller.can_defer_projection = True
    host.source_edit_requires_canonical_rebuild = True
    applier = _source_change_applier(host)

    applier.apply_edit_commit(commit)

    request = host._edit_pipeline.requests[-1]
    assert request.projection_deferral_reason == "source_projection_topology_changed"
    assert host.source_topology_checks[-1] == ("alpha", "alphax", 5, 5)
    assert host.marked_source_changes[-1] == (
        False,
        commit.next_snapshot.source_revision,
    )
    assert host._editor_state.semantic.document.source_text == "alpha"
    assert host._editor_state.edit_semantic.document.source_text == "alphax"
