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

"""Verify application-owned reorder commit request freshness policy."""

import pytest

from substitute.application.prompt_editor.reorder.commit import (
    PromptReorderLayoutCommitRequest,
)
from substitute.application.prompt_editor.reorder.views import PromptReorderStateView


@pytest.mark.parametrize(
    ("prepared_revision", "prepared_length", "expected"),
    (
        (None, None, True),
        (3, None, True),
        (3, 11, True),
        (4, 11, False),
        (3, 12, False),
    ),
)
def test_reorder_commit_request_matches_prepared_source(
    prepared_revision: int | None,
    prepared_length: int | None,
    expected: bool,
) -> None:
    """Freshness should require every source component captured by the request."""

    request = PromptReorderLayoutCommitRequest(
        selected_chip_index=1,
        reorder_state=_reorder_state(),
        source_revision=prepared_revision,
        source_length=prepared_length,
    )

    assert request.source_matches(source_revision=3, source_length=11) is expected


def test_reorder_commit_request_keeps_application_values_without_conversion() -> None:
    """The editing adapter should receive the exact immutable reorder state."""

    reorder_state = _reorder_state()
    request = PromptReorderLayoutCommitRequest(
        selected_chip_index=1,
        reorder_state=reorder_state,
        source_revision=3,
        source_length=11,
        selection_start_offset_within_selected_chip=2,
        selection_end_offset_within_selected_chip=4,
    )

    assert request.reorder_state is reorder_state
    assert request.selected_chip_index == 1
    assert request.selection_start_offset_within_selected_chip == 2
    assert request.selection_end_offset_within_selected_chip == 4


@pytest.mark.parametrize(
    ("source_revision", "source_length"),
    (
        (None, 11),
        (-1, None),
        (3, -1),
    ),
)
def test_reorder_commit_request_rejects_invalid_source_identity(
    source_revision: int | None,
    source_length: int | None,
) -> None:
    """Invalid prepared identities should fail before reaching editing execution."""

    with pytest.raises(ValueError):
        PromptReorderLayoutCommitRequest(
            selected_chip_index=1,
            reorder_state=_reorder_state(),
            source_revision=source_revision,
            source_length=source_length,
        )


def _reorder_state() -> PromptReorderStateView:
    """Return one minimal authoritative reorder state."""

    return PromptReorderStateView(
        ordered_chip_indices=(1, 0),
        separator_slots=(", ",),
        has_trailing_comma=False,
    )
