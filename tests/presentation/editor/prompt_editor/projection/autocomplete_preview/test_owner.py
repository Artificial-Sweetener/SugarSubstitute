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

"""Tests for authoritative autocomplete preview projection ownership."""

from __future__ import annotations

from dataclasses import dataclass, field

from substitute.presentation.editor.prompt_editor.autocomplete_preview_state import (
    PromptAutocompletePreviewState,
)
from substitute.presentation.editor.prompt_editor.projection.autocomplete_preview_projection_owner import (
    PromptAutocompletePreviewProjectionOwner,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)


@dataclass(slots=True)
class _PreviewProjectionRecorder:
    """Record lower-level projection operations controlled by the preview owner."""

    session: PromptProjectionSession = field(default_factory=PromptProjectionSession)
    stale: bool = False
    flush_count: int = 0
    base_rebuild_count: int = 0
    active_rebuild_count: int = 0
    paint_invalidation_count: int = 0

    def owner(self) -> PromptAutocompletePreviewProjectionOwner:
        """Build an owner from the recorder's explicit projection operations."""

        return PromptAutocompletePreviewProjectionOwner(
            session=self.session,
            flush_pending_projection=self.flush_pending_projection,
            base_projection_is_stale=lambda: self.stale,
            rebuild_base_projection=self.rebuild_base_projection,
            rebuild_active_projection=self.rebuild_active_projection,
            request_repaint=self.request_repaint,
            surface_state=dict,
        )

    def flush_pending_projection(self) -> None:
        """Record pending projection flushes."""

        self.flush_count += 1

    def rebuild_base_projection(self) -> None:
        """Record base projection rebuilds."""

        self.base_rebuild_count += 1

    def rebuild_active_projection(self) -> None:
        """Record active projection rebuilds."""

        self.active_rebuild_count += 1

    def request_repaint(self) -> None:
        """Record preview paint invalidation."""

        self.paint_invalidation_count += 1


def _preview() -> PromptAutocompletePreviewState:
    """Return one stable preview state for owner behavior tests."""

    return PromptAutocompletePreviewState(source_position=8, suffix_text=" basket")


def test_preview_projection_owner_rebuilds_stale_base_before_publish() -> None:
    """Publishing preview flushes pending work and rebuilds stale base geometry."""

    recorder = _PreviewProjectionRecorder(stale=True)
    owner = recorder.owner()
    preview = _preview()

    owner.set_preview_state(preview)

    assert owner.state == preview
    assert recorder.session.autocomplete_preview == preview
    assert recorder.flush_count == 1
    assert recorder.base_rebuild_count == 1
    assert recorder.active_rebuild_count == 1
    assert recorder.paint_invalidation_count == 0


def test_preview_projection_owner_invalidates_paint_on_clear() -> None:
    """Clearing preview always invalidates pixels that may still show ghost text."""

    recorder = _PreviewProjectionRecorder(
        session=PromptProjectionSession(autocomplete_preview=_preview())
    )
    owner = recorder.owner()

    owner.set_preview_state(None)

    assert owner.state is None
    assert recorder.active_rebuild_count == 1
    assert recorder.paint_invalidation_count == 1


def test_preview_projection_owner_invalidates_redundant_clear() -> None:
    """Repeated clear still repaints because stale pixels can outlive state."""

    recorder = _PreviewProjectionRecorder()
    owner = recorder.owner()

    owner.set_preview_state(None)

    assert recorder.active_rebuild_count == 0
    assert recorder.paint_invalidation_count == 1


def test_preview_owner_clears_preview_after_cursor_moves_away() -> None:
    """Caret movement away from preview origin clears through the preview owner."""

    recorder = _PreviewProjectionRecorder(
        session=PromptProjectionSession(autocomplete_preview=_preview())
    )
    owner = recorder.owner()

    owner.reconcile_after_caret_state_change(
        cursor_position=45,
        selection_is_empty=True,
    )

    assert owner.state is None
    assert recorder.active_rebuild_count == 1
    assert recorder.paint_invalidation_count == 1


def test_preview_owner_clears_preview_after_selection_starts() -> None:
    """Selection cannot keep inline autocomplete preview alive."""

    preview = _preview()
    recorder = _PreviewProjectionRecorder(
        session=PromptProjectionSession(autocomplete_preview=preview)
    )
    owner = recorder.owner()

    owner.reconcile_after_caret_state_change(
        cursor_position=preview.source_position,
        selection_is_empty=False,
    )

    assert owner.state is None
    assert recorder.active_rebuild_count == 1
    assert recorder.paint_invalidation_count == 1


def test_preview_owner_rebuilds_when_preview_still_matches_caret() -> None:
    """A same-position caret refresh rebuilds instead of clearing valid preview."""

    preview = _preview()
    recorder = _PreviewProjectionRecorder(
        session=PromptProjectionSession(autocomplete_preview=preview)
    )
    owner = recorder.owner()

    owner.reconcile_after_caret_state_change(
        cursor_position=preview.source_position,
        selection_is_empty=True,
    )

    assert owner.state == preview
    assert recorder.active_rebuild_count == 1
    assert recorder.paint_invalidation_count == 0
