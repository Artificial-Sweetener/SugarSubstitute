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

"""Tests for caret-owned autocomplete preview reconciliation."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.presentation.editor.prompt_editor.autocomplete_preview_state import (
    PromptAutocompletePreviewState,
)
from substitute.presentation.editor.prompt_editor.projection.caret_autocomplete_preview_coordinator import (
    PromptCaretAutocompletePreviewCoordinator,
)


@dataclass(slots=True)
class _CaretPreviewHostRecorder:
    """Record caret autocomplete preview coordination calls."""

    preview_state: PromptAutocompletePreviewState | None = None
    clear_count: int = 0
    active_rebuild_count: int = 0

    def current_autocomplete_preview_state(
        self,
    ) -> PromptAutocompletePreviewState | None:
        """Return recorded preview state."""

        return self.preview_state

    def clear_autocomplete_preview_state(self) -> None:
        """Record authoritative preview clearing."""

        self.clear_count += 1
        self.preview_state = None

    def rebuild_active_projection_for_autocomplete_preview(self) -> None:
        """Record active projection rebuilds."""

        self.active_rebuild_count += 1


def test_caret_preview_coordinator_clears_preview_after_cursor_moves_away() -> None:
    """Caret movement away from preview origin clears through the preview owner."""

    host = _CaretPreviewHostRecorder(
        preview_state=PromptAutocompletePreviewState(
            source_position=45,
            suffix_text=" basket",
        )
    )
    coordinator = PromptCaretAutocompletePreviewCoordinator(host)

    coordinator.reconcile_after_caret_state_change(
        cursor_position=8,
        selection_is_empty=True,
    )

    assert host.preview_state is None
    assert host.clear_count == 1
    assert host.active_rebuild_count == 0


def test_caret_preview_coordinator_clears_preview_after_selection_starts() -> None:
    """Selection cannot keep inline autocomplete preview alive."""

    host = _CaretPreviewHostRecorder(
        preview_state=PromptAutocompletePreviewState(
            source_position=45,
            suffix_text=" basket",
        )
    )
    coordinator = PromptCaretAutocompletePreviewCoordinator(host)

    coordinator.reconcile_after_caret_state_change(
        cursor_position=45,
        selection_is_empty=False,
    )

    assert host.preview_state is None
    assert host.clear_count == 1
    assert host.active_rebuild_count == 0


def test_caret_preview_coordinator_rebuilds_when_preview_still_matches_caret() -> None:
    """A same-position caret refresh rebuilds instead of clearing valid preview."""

    preview_state = PromptAutocompletePreviewState(
        source_position=45,
        suffix_text=" basket",
    )
    host = _CaretPreviewHostRecorder(preview_state=preview_state)
    coordinator = PromptCaretAutocompletePreviewCoordinator(host)

    coordinator.reconcile_after_caret_state_change(
        cursor_position=45,
        selection_is_empty=True,
    )

    assert host.preview_state == preview_state
    assert host.clear_count == 0
    assert host.active_rebuild_count == 1
