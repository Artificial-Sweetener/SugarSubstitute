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

"""Cover immutable reorder visual-session publication."""

from __future__ import annotations

import pytest

from substitute.application.prompt_editor.document.views import PromptReorderChipView
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_session import (
    PromptReorderVisualSessionOwner,
)


def test_visual_session_replaces_segment_and_source_facts_atomically() -> None:
    """Each session replacement should publish immutable coherent visual facts."""

    owner = PromptReorderVisualSessionOwner()
    first = owner.set_session(
        chips=(_segment(0), _segment(1)),
        source_identity=PromptSourceIdentity(source_revision=7, source_length=10),
    )

    assert first.revision == 1
    assert first.ordered_indices == (0, 1)
    assert owner.segment(1) is first.segments_by_index[1]
    assert owner.source_revision == 7
    with pytest.raises(TypeError):
        first.segments_by_index[2] = _segment(2)  # type: ignore[index]

    second = owner.set_session(
        chips=(_segment(2),),
        source_identity=PromptSourceIdentity(source_revision=8, source_length=5),
    )

    assert second.revision == 2
    assert tuple(second.segments_by_index) == (2,)
    assert owner.segment(0) is None
    assert first.segments_by_index.keys() == {0, 1}


def _segment(index: int) -> PromptReorderChipView:
    """Return one stable semantic chip view."""

    start = index * 5
    return PromptReorderChipView(
        index=index,
        partition_index=0,
        text=f"tag{index}",
        serialized_text=f"tag{index}",
        display_text=f"tag{index}",
        display_source_start=start,
        display_source_end=start + 4,
        selection_start=start,
        selection_end=start + 4,
        separator_text_after="",
        has_separator_after=False,
    )
