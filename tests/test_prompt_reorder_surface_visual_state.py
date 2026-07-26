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

"""Verify atomic reorder surface visual state ownership."""

from PySide6.QtCore import QRect

from substitute.presentation.editor.prompt_editor.projection.reorder_surface_visual_state import (
    PromptReorderSurfaceVisualContext,
    PromptReorderSurfaceVisualPublication,
    PromptReorderSurfaceVisualStateOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_visual_snapshot import (
    PromptReorderProjectionPaintSnapshot,
    PromptReorderProjectionSnapshotKey,
)


def _snapshot() -> PromptReorderProjectionPaintSnapshot:
    """Return one deterministic suppression snapshot identity."""

    return PromptReorderProjectionPaintSnapshot(
        key=PromptReorderProjectionSnapshotKey(
            source_revision=3,
            viewport_rect=QRect(0, 0, 320, 180),
            scroll_offset=0,
            font_key="font",
            palette_key=7,
            preview_generation=11,
            geometry_generation=13,
            segment_index=2,
            mode="preview",
        ),
        fragments=(),
        source_ranges=((0, 5),),
        content_key=("alpha",),
    )


def _context() -> PromptReorderSurfaceVisualContext:
    """Return one deterministic receiving projection identity."""

    return PromptReorderSurfaceVisualContext(
        source_revision=3,
        viewport_rect=QRect(0, 0, 320, 180),
        scroll_offset=0,
        preview_generation=11,
    )


def test_surface_visual_owner_publishes_chrome_and_suppression_atomically() -> None:
    """One prepared input should cause one immutable state revision."""

    owner = PromptReorderSurfaceVisualStateOwner()
    snapshot = _snapshot()
    publication = PromptReorderSurfaceVisualPublication(
        mode="preview",
        chips=(),
        suppression_snapshots_by_index={2: snapshot},
    )

    assert owner.publish(publication, context=_context()) is True
    state = owner.state
    assert state.revision == 1
    assert state.mode == "preview"
    assert state.chips == ()
    assert state.suppression_snapshots_by_index == {2: snapshot}
    assert state.suppression_snapshots_by_index[2] is snapshot
    assert state.chrome_snapshot is None


def test_surface_visual_owner_reuses_exact_suppression_without_allocation() -> None:
    """An identical prepared input should retain state and mapping identity."""

    owner = PromptReorderSurfaceVisualStateOwner()
    snapshot = _snapshot()
    publication = PromptReorderSurfaceVisualPublication(
        mode="preview",
        chips=(),
        suppression_snapshots_by_index={2: snapshot},
    )
    owner.publish(publication, context=_context())
    state = owner.state

    assert owner.publish(publication, context=_context()) is False
    assert owner.state is state
    assert (
        owner.state.suppression_snapshots_by_index
        is state.suppression_snapshots_by_index
    )


def test_surface_visual_owner_rejects_equal_but_stale_snapshot_identity() -> None:
    """A distinct snapshot object must publish even when values compare equal."""

    owner = PromptReorderSurfaceVisualStateOwner()
    first = _snapshot()
    owner.publish(
        PromptReorderSurfaceVisualPublication(
            mode="preview",
            chips=(),
            suppression_snapshots_by_index={2: first},
        ),
        context=_context(),
    )

    replacement = _snapshot()
    assert replacement == first
    assert replacement is not first
    assert (
        owner.publish(
            PromptReorderSurfaceVisualPublication(
                mode="preview",
                chips=(),
                suppression_snapshots_by_index={2: replacement},
            ),
            context=_context(),
        )
        is True
    )
    assert owner.state.revision == 2
    assert owner.state.suppression_snapshots_by_index[2] is replacement


def test_surface_visual_owner_publishes_atomic_preview_teardown_once() -> None:
    """Preview teardown should clear all prepared surface state in one revision."""

    owner = PromptReorderSurfaceVisualStateOwner()
    owner.publish(
        PromptReorderSurfaceVisualPublication(
            mode="preview",
            chips=(),
            suppression_snapshots_by_index={2: _snapshot()},
        ),
        context=_context(),
    )
    empty_publication = PromptReorderSurfaceVisualPublication(
        mode="live",
        chips=(),
        suppression_snapshots_by_index={},
    )

    assert owner.publish(empty_publication, context=_context()) is True
    assert owner.state.revision == 2
    assert owner.state.mode == "live"
    assert owner.state.chips == ()
    assert owner.state.suppression_snapshots_by_index == {}
    cleared_state = owner.state
    assert owner.publish(empty_publication, context=_context()) is False
    assert owner.state is cleared_state
