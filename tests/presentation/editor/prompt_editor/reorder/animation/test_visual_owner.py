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

"""Verify coherent combined reorder animation publication."""

from __future__ import annotations


from PySide6.QtCore import QRectF

from substitute.presentation.editor.prompt_editor.overlays.reorder_animation_visual_owner import (
    PromptReorderAnimationVisualOwner,
    PromptReorderHeldChipAnimationTarget,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_animation import (
    PromptReorderAnimationTarget,
)
from tests.presentation.editor.prompt_editor.reorder.animation.presenter_support import (
    _host_with_chips,
    _presenter_plan,
    _process_events,
)


def test_animation_visual_owner_publishes_held_and_displacement_atomically() -> None:
    """Pointer and paint consumers should observe one combined frame revision."""

    app, host, _chips = _host_with_chips()
    published_revisions: list[int] = []
    owner_holder: list[PromptReorderAnimationVisualOwner] = []

    def capture_publication() -> None:
        """Record the exact revision published after presenter batching."""

        published_revisions.append(owner_holder[0].publication.revision)

    try:
        owner = PromptReorderAnimationVisualOwner(
            parent=host,
            frame_callback=capture_publication,
        )
        owner_holder.append(owner)
        plan = _presenter_plan(
            generation=1,
            changed_targets=(
                PromptReorderAnimationTarget(
                    segment_index=0,
                    start_rect=QRectF(0.0, 0.0, 20.0, 10.0),
                    target_rect=QRectF(40.0, 0.0, 20.0, 10.0),
                    target_visible=True,
                ),
            ),
        )

        owner.apply_plan(
            plan,
            held_target=PromptReorderHeldChipAnimationTarget(
                generation=1,
                segment_index=1,
                start_rect=QRectF(24.0, 0.0, 20.0, 10.0),
                target_rect=QRectF(64.0, 0.0, 20.0, 10.0),
            ),
        )
        publication = owner.publication

        assert published_revisions == [1]
        assert set(publication.displacement_rects_by_index) == {0}
        assert set(publication.held_rects_by_index) == {1}
        assert set(publication.paint_rects_by_index) == {0, 1}

        owner.cancel(reason="test")

        assert published_revisions == [1, 2]
        assert not owner.publication.paint_rects_by_index
    finally:
        host.close()
        host.deleteLater()
        _process_events(app)
