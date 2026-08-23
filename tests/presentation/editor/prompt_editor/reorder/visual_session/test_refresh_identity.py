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

"""Verify session-bounded reorder refresh-identity ownership."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import pytest
from PySide6.QtCore import QRect

from substitute.application.prompt_editor.document.views import PromptReorderChipView
from substitute.presentation.editor.prompt_editor.overlays import (
    reorder_refresh_identity as refresh_identity_module,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_refresh_identity import (
    PromptReorderRefreshIdentityOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_state import (
    PromptReorderOverlayPositionGeometryKey,
)


def test_refresh_identity_hashes_source_once_per_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated refresh-key construction must not rescan unchanged source text."""

    fingerprint_calls = 0
    fingerprint: Callable[[str], tuple[int, str]] = getattr(
        refresh_identity_module,
        "reorder_source_fingerprint",
    )

    def counted_fingerprint(source_text: str) -> tuple[int, str]:
        """Count session fingerprint work while preserving production identity."""

        nonlocal fingerprint_calls
        fingerprint_calls += 1
        return fingerprint(source_text)

    monkeypatch.setattr(
        refresh_identity_module,
        "reorder_source_fingerprint",
        counted_fingerprint,
    )
    owner = PromptReorderRefreshIdentityOwner()
    owner.begin_session("alpha, beta")
    position_key = _position_key()

    first = owner.build_refresh_key(
        position_key=position_key,
        segments_by_index={0: _segment()},
        content_rect=QRect(4, 6, 320, 180),
        geometry_state=PromptReorderInteractionGeometryState(),
        dragged_segment_index=None,
        active_target=None,
    )
    second = owner.build_refresh_key(
        position_key=position_key,
        segments_by_index={0: _segment()},
        content_rect=QRect(4, 6, 320, 180),
        geometry_state=PromptReorderInteractionGeometryState(),
        dragged_segment_index=None,
        active_target=None,
    )

    assert first == second
    assert fingerprint_calls == 1


def test_refresh_identity_owns_publication_and_invalidation_lifecycle() -> None:
    """Position and refresh identities should advance only at publication."""

    owner = PromptReorderRefreshIdentityOwner()
    owner.begin_session("alpha")
    position_key = _position_key()
    refresh_key = owner.build_refresh_key(
        position_key=position_key,
        segments_by_index={0: _segment()},
        content_rect=QRect(4, 6, 320, 180),
        geometry_state=PromptReorderInteractionGeometryState(),
        dragged_segment_index=None,
        active_target=None,
    )

    assert owner.position_changed(position_key) is True
    assert owner.previous_refresh_key is None

    owner.record_publication(
        position_key=position_key,
        refresh_key=refresh_key,
    )

    assert owner.position_changed(position_key) is False
    assert owner.previous_refresh_key == refresh_key

    owner.invalidate_refresh()

    assert owner.position_changed(position_key) is False
    assert owner.previous_refresh_key is None
    assert owner.position_changed(replace(position_key, scroll_offset=12))


def _position_key() -> PromptReorderOverlayPositionGeometryKey:
    """Return one deterministic viewport identity."""

    return PromptReorderOverlayPositionGeometryKey(
        viewport_left=0,
        viewport_top=0,
        viewport_width=340,
        viewport_height=200,
        content_left=4,
        content_top=6,
        content_width=320,
        content_height=180,
        scroll_offset=0,
    )


def _segment() -> PromptReorderChipView:
    """Return one semantic chip identity."""

    return PromptReorderChipView(
        index=0,
        partition_index=0,
        text="alpha",
        serialized_text="alpha",
        display_text="alpha",
        display_source_start=0,
        display_source_end=5,
        selection_start=0,
        selection_end=5,
        separator_text_after="",
        has_separator_after=False,
    )
