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

"""Verify atomic source-revision publication and invalidation behavior."""

from __future__ import annotations

import pytest

from substitute.presentation.editor.prompt_editor.core.editing.source_buffer import (
    PromptSourceSnapshot,
)

from .commit_builders import _source_change_publication
from .source_change_host import _SourceChangeHost


@pytest.mark.parametrize(
    ("deferrable_projection", "expected_clear_count"),
    ((False, 1), (True, 0)),
)
def test_source_change_publication_invalidates_exact_dependent_state(
    monkeypatch: pytest.MonkeyPatch,
    *,
    deferrable_projection: bool,
    expected_clear_count: int,
) -> None:
    """Publish identity once while preserving only valid deferred overlays."""

    host = _SourceChangeHost()
    clear_count = 0

    def record_clear() -> None:
        """Record transient-overlay invalidation."""

        nonlocal clear_count
        clear_count += 1

    monkeypatch.setattr(host._transient_edit_overlays, "clear", record_clear)
    owner = _source_change_publication(host)
    snapshot = PromptSourceSnapshot(source_text="alphax", source_revision=8)

    identity = owner.publish(
        deferrable_projection=deferrable_projection,
        source_snapshot=snapshot,
        clear_diagnostic_fragment_cache=False,
    )

    assert identity is host._editor_state.source_identity
    assert identity.source_revision == 8
    assert host._editor_state.source is snapshot
    assert clear_count == expected_clear_count
    assert host.input_method_source_changes == 1
    assert host.reorder_source_changes == 1
    assert host.render_source_changes == [False]
    assert host.marked_source_changes == [(deferrable_projection, 8)]
