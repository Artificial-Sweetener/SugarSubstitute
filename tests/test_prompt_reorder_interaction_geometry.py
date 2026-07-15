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

"""Cover projection-owned prompt reorder interaction geometry boundaries."""

from __future__ import annotations

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptLineDropTarget,
    PromptReorderGapView,
    PromptReorderDropTarget,
    PromptReorderLayoutView,
    PromptReorderPreviewSnapshot,
    PromptReorderRowView,
    PromptReorderStateView,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_chip_geometry import (
    PromptReorderChipGeometrySnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementId,
    PromptReorderPlacementSnapshot,
)


class _FakeLayoutPolicy:
    """Provide deterministic reorder layouts for geometry-owner tests."""

    def build_base_drag_layout_view_from_layout(
        self,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView,
        *,
        dragged_segment_index: int,
    ) -> PromptReorderLayoutView:
        """Return the supplied layout without changing semantic order."""

        _ = document_view
        _ = dragged_segment_index
        return layout_view

    def build_base_drag_reorder_state_from_state(
        self,
        state_view: PromptReorderStateView,
        *,
        dragged_segment_index: int,
    ) -> PromptReorderStateView:
        """Return state with the dragged chip removed."""

        remaining = tuple(
            index
            for index in state_view.ordered_chip_indices
            if index != dragged_segment_index
        )
        return PromptReorderStateView(
            ordered_chip_indices=remaining,
            separator_slots=state_view.separator_slots[: max(0, len(remaining) - 1)],
            has_trailing_comma=state_view.has_trailing_comma,
        )

    def build_preview_drop_reorder_state_from_state(
        self,
        document_view: PromptDocumentView,
        state_view: PromptReorderStateView,
        *,
        current_layout_view: PromptReorderLayoutView,
        base_drag_layout_view: PromptReorderLayoutView | None,
        dragged_segment_index: int,
        drop_target: PromptReorderDropTarget,
    ) -> PromptReorderStateView:
        """Return state matching the fake preview layout order."""

        layout_view = self.build_preview_drop_layout_view_from_layout(
            document_view,
            current_layout_view,
            dragged_segment_index=dragged_segment_index,
            drop_target=drop_target,
        )
        _ = base_drag_layout_view
        ordered = self.reorder_layout_chip_indices(layout_view)
        return PromptReorderStateView(
            ordered_chip_indices=ordered,
            separator_slots=state_view.separator_slots[: max(0, len(ordered) - 1)],
            has_trailing_comma=state_view.has_trailing_comma,
        )

    def build_preview_drop_layout_view_from_layout(
        self,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView,
        *,
        dragged_segment_index: int,
        drop_target: PromptReorderDropTarget,
    ) -> PromptReorderLayoutView:
        """Return a simple layout that reflects the requested insertion index."""

        _ = document_view
        assert isinstance(drop_target, PromptLineDropTarget)
        remaining = [
            index
            for row in layout_view.rows
            for index in row.chip_indices
            if index != dragged_segment_index
        ]
        next_indices = [*remaining]
        next_indices.insert(drop_target.insertion_index, dragged_segment_index)
        return PromptReorderLayoutView(
            rows=(
                PromptReorderRowView(
                    row_index=drop_target.row_index,
                    chip_indices=tuple(next_indices),
                ),
            ),
            gaps=layout_view.gaps,
        )

    def reorder_layout_chip_indices(
        self,
        layout_view: PromptReorderLayoutView,
    ) -> tuple[int, ...]:
        """Return the flattened layout order."""

        return tuple(index for row in layout_view.rows for index in row.chip_indices)


class _UnusedGeometryHost:
    """Satisfy the geometry host protocol for identity-only tests."""

    def reorder_preview_chip_geometry_snapshot(
        self,
        *,
        snapshot: PromptReorderPreviewSnapshot,
        layout_view: PromptReorderLayoutView,
    ) -> PromptReorderChipGeometrySnapshot:
        """Reject unexpected snapshot requests in identity-only tests."""

        _ = snapshot
        _ = layout_view
        raise AssertionError("preview chip geometry should not be requested")

    def reorder_base_drag_chip_geometry_snapshot(
        self,
        *,
        snapshot: PromptReorderPreviewSnapshot,
        layout_view: PromptReorderLayoutView,
    ) -> PromptReorderChipGeometrySnapshot:
        """Reject unexpected base-drag snapshot requests in identity-only tests."""

        _ = snapshot
        _ = layout_view
        raise AssertionError("base-drag chip geometry should not be requested")

    def reorder_base_drag_placement_snapshot(
        self,
        *,
        snapshot: PromptReorderPreviewSnapshot,
        layout_view: PromptReorderLayoutView,
    ) -> PromptReorderPlacementSnapshot:
        """Reject unexpected placement snapshot requests in identity-only tests."""

        _ = snapshot
        _ = layout_view
        raise AssertionError("placement geometry should not be requested")

    def reorder_placement_at_rect(
        self,
        drag_rect: QRectF,
        *,
        snapshot: PromptReorderPlacementSnapshot,
        active_placement_id: PromptReorderPlacementId | None,
    ) -> PromptReorderPlacementGeometry | None:
        """Reject unexpected hit testing in identity-only tests."""

        _ = drag_rect
        _ = snapshot
        _ = active_placement_id
        raise AssertionError("placement hit testing should not be requested")


def _document_view(source_text: str) -> PromptDocumentView:
    """Return a minimal prompt document view for geometry identity tests."""

    return PromptDocumentView(
        source_text=source_text,
        segments=(),
        emphasis_spans=(),
        wildcard_spans=(),
        lora_spans=(),
        syntax_spans=(),
        has_trailing_comma=False,
    )


def _layout_view() -> PromptReorderLayoutView:
    """Return a minimal one-row reorder layout."""

    return PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(0, 1, 2)),),
        gaps=(
            PromptReorderGapView(
                gap_index=0,
                separator_text=", ",
                blank_line_count=0,
            ),
        ),
    )


def _state_view() -> PromptReorderStateView:
    """Return a minimal authoritative reorder state."""

    return PromptReorderStateView(
        ordered_chip_indices=(0, 1, 2),
        separator_slots=(", ", ", "),
        has_trailing_comma=False,
    )


def test_phase25_4_reorder_geometry_owner_rejects_stale_preview_identity() -> None:
    """Preview geometry freshness is rejected by owner identity, not overlay repair."""

    owner = PromptReorderInteractionGeometry(
        layout_policy=_FakeLayoutPolicy(),
        geometry_host=_UnusedGeometryHost(),
    )
    layout_view = _layout_view()
    owner.set_session(
        _document_view("alpha, beta, gamma"),
        layout_view,
        _state_view(),
        ordered_indices=(0, 1, 2),
    )
    owner.base_drag_layout_view = layout_view
    owner.preview_layout_view = layout_view
    target = PromptLineDropTarget(row_index=0, insertion_index=1)
    owner.preview_geometry_target_identity = owner.preview_target_identity_for_target(
        dragged_segment_index=0,
        target=target,
        viewport_identity=("viewport", 320, 180, 0),
    )
    assert owner.preview_geometry_target_identity is not None
    identity_context = owner.preview_target_identity_context(
        owner.preview_geometry_target_identity,
        prefix="preview_geometry_target",
    )
    assert "alpha, beta, gamma" not in repr(identity_context)

    assert owner.preview_geometry_matches_target(
        dragged_segment_index=0,
        target=target,
        viewport_identity=("viewport", 320, 180, 0),
    )
    assert not owner.preview_geometry_matches_target(
        dragged_segment_index=0,
        target=PromptLineDropTarget(row_index=0, insertion_index=2),
        viewport_identity=("viewport", 320, 180, 0),
    )
    assert not owner.preview_geometry_matches_target(
        dragged_segment_index=1,
        target=target,
        viewport_identity=("viewport", 320, 180, 0),
    )
    assert not owner.preview_geometry_matches_target(
        dragged_segment_index=0,
        target=target,
        viewport_identity=("viewport", 320, 180, 12),
    )

    owner.document_view = _document_view("alpha, beta, gamma, delta")
    assert not owner.preview_geometry_matches_target(
        dragged_segment_index=0,
        target=target,
        viewport_identity=("viewport", 320, 180, 0),
    )
