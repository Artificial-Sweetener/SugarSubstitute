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

"""Test authoritative caret geometry selection and coordinate translation."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from PySide6.QtCore import QRectF

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.projection.caret_geometry_owner import (
    PromptCaretGeometryEditorState,
    PromptProjectionCaretGeometryOwner,
)
from substitute.presentation.editor.prompt_editor.projection.caret_state_owner import (
    PromptProjectionCaretStateOwner,
)
from substitute.presentation.editor.prompt_editor.projection.transient_edit_overlays import (
    PromptProjectionTransientCaretGeometry,
    PromptProjectionTransientEditOverlayController,
)


def _owner(
    *,
    state: PromptProjectionCaretStateOwner,
    overlays: PromptProjectionTransientEditOverlayController,
    stale_safe: bool,
    source_identity: PromptSourceIdentity,
    cursor_position: int,
    anchor_position: int,
    scroll_offset: float = 0.0,
) -> PromptProjectionCaretGeometryOwner:
    """Build one geometry owner with deterministic committed geometry."""

    editor_state = cast(
        PromptCaretGeometryEditorState,
        SimpleNamespace(source_identity=source_identity),
    )
    return PromptProjectionCaretGeometryOwner(
        state=state,
        editor_state=editor_state,
        overlays=overlays,
        freshness_is_stale_safe=lambda: stale_safe,
        cursor_position=lambda: cursor_position,
        anchor_position=lambda: anchor_position,
        committed_document_rect=(
            lambda caret_state: QRectF(
                float(caret_state.source_position),
                20.0,
                1.0,
                12.0,
            )
        ),
        scroll_offset=lambda: scroll_offset,
    )


def test_matching_transient_geometry_precedes_affinity_and_committed_layout() -> None:
    """Source-current deferred geometry should remain authoritative until catch-up."""

    source_identity = PromptSourceIdentity(source_revision=3, source_length=6)
    state = PromptProjectionCaretStateOwner(PromptProjectionCaretState(4))
    state.publish(
        cursor_state=PromptProjectionCaretState(4),
        anchor_state=PromptProjectionCaretState(4),
        caret_rect_override=QRectF(40.0, 40.0, 1.0, 12.0),
        reset_preferred_x=True,
    )
    overlays = PromptProjectionTransientEditOverlayController()
    overlays.set_overlays(
        caret_geometry=PromptProjectionTransientCaretGeometry(
            source_identity=source_identity,
            cursor_position=4,
            anchor_position=4,
            document_rect=QRectF(8.0, 9.0, 1.0, 12.0),
            committed_source_identity=PromptSourceIdentity(source_revision=2),
        ),
        insertion_overlay=None,
        deletion_overlay=None,
    )
    owner = _owner(
        state=state,
        overlays=overlays,
        stale_safe=True,
        source_identity=source_identity,
        cursor_position=4,
        anchor_position=4,
    )

    assert owner.current_document_rect() == QRectF(8.0, 9.0, 1.0, 12.0)


def test_stale_transient_geometry_falls_back_to_visual_affinity_override() -> None:
    """Mismatched transient identity should not displace explicit wrap affinity."""

    state = PromptProjectionCaretStateOwner(PromptProjectionCaretState(4))
    override = QRectF(40.0, 40.0, 1.0, 12.0)
    state.publish(
        cursor_state=PromptProjectionCaretState(4),
        anchor_state=PromptProjectionCaretState(4),
        caret_rect_override=override,
        reset_preferred_x=True,
    )
    overlays = PromptProjectionTransientEditOverlayController()
    overlays.set_overlays(
        caret_geometry=PromptProjectionTransientCaretGeometry(
            source_identity=PromptSourceIdentity(source_revision=2),
            cursor_position=4,
            anchor_position=4,
            document_rect=QRectF(8.0, 9.0, 1.0, 12.0),
            committed_source_identity=PromptSourceIdentity(source_revision=1),
        ),
        insertion_overlay=None,
        deletion_overlay=None,
    )
    owner = _owner(
        state=state,
        overlays=overlays,
        stale_safe=True,
        source_identity=PromptSourceIdentity(source_revision=3),
        cursor_position=4,
        anchor_position=4,
    )

    assert owner.current_document_rect() == override


def test_committed_geometry_translates_once_into_viewport_coordinates() -> None:
    """Committed geometry should use logical state and one vertical scroll translation."""

    state = PromptProjectionCaretStateOwner(PromptProjectionCaretState(5))
    owner = _owner(
        state=state,
        overlays=PromptProjectionTransientEditOverlayController(),
        stale_safe=False,
        source_identity=PromptSourceIdentity(source_revision=3),
        cursor_position=5,
        anchor_position=5,
        scroll_offset=7.0,
    )

    assert owner.current_document_rect() == QRectF(5.0, 20.0, 1.0, 12.0)
    assert owner.current_viewport_rect() == QRectF(5.0, 13.0, 1.0, 12.0)
