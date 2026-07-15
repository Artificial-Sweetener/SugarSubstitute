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

"""Tests for autocomplete preview projection ownership."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.presentation.editor.prompt_editor.autocomplete_preview_state import (
    PromptAutocompletePreviewState,
)
from substitute.presentation.editor.prompt_editor.projection.autocomplete_preview_projection_owner import (
    PromptAutocompletePreviewProjectionOwner,
)


@dataclass(slots=True)
class _PreviewProjectionHostRecorder:
    """Record preview projection owner host calls."""

    preview_state: PromptAutocompletePreviewState | None = None
    stale: bool = False
    flush_count: int = 0
    base_rebuild_count: int = 0
    active_rebuild_count: int = 0
    paint_invalidation_count: int = 0

    def current_autocomplete_preview_state(
        self,
    ) -> PromptAutocompletePreviewState | None:
        """Return recorded preview state."""

        return self.preview_state

    def set_session_autocomplete_preview_state(
        self,
        preview_state: PromptAutocompletePreviewState | None,
    ) -> None:
        """Record session preview replacement."""

        self.preview_state = preview_state

    def flush_pending_projection_for_autocomplete_preview(self) -> None:
        """Record pending projection flush."""

        self.flush_count += 1

    def base_projection_is_stale_for_autocomplete_preview(self) -> bool:
        """Return recorded stale state."""

        return self.stale

    def rebuild_base_projection_for_autocomplete_preview(self) -> None:
        """Record base projection rebuild."""

        self.base_rebuild_count += 1

    def rebuild_active_projection_for_autocomplete_preview(self) -> None:
        """Record active projection rebuild."""

        self.active_rebuild_count += 1

    def invalidate_autocomplete_preview_paint(self) -> None:
        """Record preview paint invalidation."""

        self.paint_invalidation_count += 1


def test_preview_projection_owner_rebuilds_stale_base_before_publish() -> None:
    """Publishing preview flushes pending work and rebuilds stale base geometry."""

    host = _PreviewProjectionHostRecorder(stale=True)
    owner = PromptAutocompletePreviewProjectionOwner(host)
    preview = PromptAutocompletePreviewState(source_position=8, suffix_text=" basket")

    owner.set_preview_state(preview)

    assert host.preview_state == preview
    assert host.flush_count == 1
    assert host.base_rebuild_count == 1
    assert host.active_rebuild_count == 1
    assert host.paint_invalidation_count == 0


def test_preview_projection_owner_invalidates_paint_on_clear() -> None:
    """Clearing preview always invalidates pixels that may still show ghost text."""

    host = _PreviewProjectionHostRecorder(
        preview_state=PromptAutocompletePreviewState(
            source_position=8,
            suffix_text=" basket",
        )
    )
    owner = PromptAutocompletePreviewProjectionOwner(host)

    owner.set_preview_state(None)

    assert host.preview_state is None
    assert host.active_rebuild_count == 1
    assert host.paint_invalidation_count == 1


def test_preview_projection_owner_invalidates_redundant_clear() -> None:
    """Repeated clear still repaints because stale pixels can outlive state."""

    host = _PreviewProjectionHostRecorder()
    owner = PromptAutocompletePreviewProjectionOwner(host)

    owner.set_preview_state(None)

    assert host.active_rebuild_count == 0
    assert host.paint_invalidation_count == 1
