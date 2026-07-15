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

"""Tests for prompt projection reorder preview surface behavior."""

from __future__ import annotations

import os
from dataclasses import replace
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QRegion
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptDocumentView,
    PromptLineDropTarget,
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.projection.layout_engine import (
    PromptProjectionLayout,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry import (
    layout_view_key,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_preview import (
    PromptReorderPreviewState,
    PromptReorderProjectionSnapshot,
)
from tests.prompt_autocomplete_test_helpers import prompt_syntax_profile
from tests.prompt_projection_test_helpers import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.prompt_projection_surface_test_helpers import (
    install_lora_wildcard_prompt_state,
    new_projection_surface,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "projection surface tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def _build_reorder_preview_state(
    text: str,
    *,
    dragged_chip_index: int,
    drop_target: PromptLineDropTarget,
) -> PromptReorderPreviewState:
    """Build one fully resolved reorder preview state from prompt-editor services."""

    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(StaticPromptWildcardCatalogGateway({}))
    syntax_profile = prompt_syntax_profile("emphasis", "wildcard")
    document_view = document_service.build_document_view(text)
    preview_layout_view = document_service.build_preview_drop_layout_view(
        document_view,
        dragged_segment_index=dragged_chip_index,
        drop_target=drop_target,
    )
    preview_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        preview_layout_view,
    )
    base_drag_layout_view = document_service.build_base_drag_layout_view(
        document_view,
        dragged_segment_index=dragged_chip_index,
    )
    base_drag_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        base_drag_layout_view,
    )
    preview_document_view = document_service.build_document_view(preview_snapshot.text)
    preview_render_plan = syntax_service.build_render_plan(
        preview_document_view,
        syntax_profile,
    )
    base_drag_document_view = document_service.build_document_view(
        base_drag_snapshot.text
    )
    base_drag_render_plan = syntax_service.build_render_plan(
        base_drag_document_view,
        syntax_profile,
    )
    return PromptReorderPreviewState(
        preview_snapshot=PromptReorderProjectionSnapshot(
            document_view=preview_document_view,
            render_plan=preview_render_plan,
            chip_rendered_ranges_by_index=preview_snapshot.chip_rendered_ranges_by_index,
            chip_owned_ranges_by_index=preview_snapshot.chip_owned_ranges_by_index,
            gap_ranges_by_index=preview_snapshot.gap_ranges_by_index,
        ),
        base_drag_snapshot=PromptReorderProjectionSnapshot(
            document_view=base_drag_document_view,
            render_plan=base_drag_render_plan,
            chip_rendered_ranges_by_index=base_drag_snapshot.chip_rendered_ranges_by_index,
            chip_owned_ranges_by_index=base_drag_snapshot.chip_owned_ranges_by_index,
            gap_ranges_by_index=base_drag_snapshot.gap_ranges_by_index,
        ),
        ordered_chip_indices=tuple(
            document_service.reorder_layout_chip_indices(preview_layout_view)
        ),
        dragged_chip_index=dragged_chip_index,
        preview_layout_key=layout_view_key(preview_layout_view),
        base_drag_layout_key=layout_view_key(base_drag_layout_view),
        active_drop_target_identity=(
            "line",
            drop_target.row_index,
            drop_target.insertion_index,
        ),
    )


def test_projection_surface_switches_to_reorder_preview_text_and_exposes_preview_queries(
    widgets: list[QWidget],
) -> None:
    """Preview state should replace live paint ownership without mutating the live document."""

    prompt_text = "alpha, beta, gamma"
    box = show_prompt_editor(
        widgets,
        text=prompt_text,
        width=320,
    )
    surface = surface_for(box)
    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(prompt_text)
    preview_layout_view = document_service.build_preview_drop_layout_view(
        document_view,
        dragged_segment_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    base_drag_layout_view = document_service.build_base_drag_layout_view(
        document_view,
        dragged_segment_index=1,
    )
    preview_state = _build_reorder_preview_state(
        prompt_text,
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    surface.set_reorder_preview_state(preview_state)

    preview_document = surface._reorder_preview_projection.preview_document  # noqa: SLF001
    assert preview_document is not None
    assert preview_document.source_text == "beta, alpha, gamma"
    assert surface.projection_document().source_text == "alpha, beta, gamma"
    beta_range = preview_state.preview_snapshot.chip_rendered_ranges_by_index[1]
    assert surface.reorder_preview_fragments(
        start=beta_range[0],
        end=beta_range[1],
    )
    preview_chip_snapshot = surface.reorder_preview_chip_geometry_snapshot(
        snapshot=preview_state.preview_snapshot,
        layout_view=preview_layout_view,
    )
    assert preview_chip_snapshot.geometries_by_chip_index[1].chip_index == 1
    preview_paint_snapshots = surface.reorder_preview_chip_projection_paint_snapshots(
        chip_geometry_snapshot=preview_chip_snapshot,
        chip_owned_ranges_by_index=(
            preview_state.preview_snapshot.chip_owned_ranges_by_index
        ),
    )
    beta_paint_snapshot = preview_paint_snapshots[1]
    assert beta_paint_snapshot.key.segment_index == 1
    assert beta_paint_snapshot.key.mode == "preview"
    assert (
        beta_paint_snapshot.source_ranges
        == (preview_state.preview_snapshot.chip_owned_ranges_by_index[1])
    )
    assert beta_paint_snapshot.text_fragments
    assert surface.reorder_preview_cursor_rect(beta_range[0]).isEmpty() is False
    base_drag_snapshot = preview_state.base_drag_snapshot
    assert base_drag_snapshot is not None
    base_range = base_drag_snapshot.chip_rendered_ranges_by_index[0]
    assert surface.reorder_base_drag_fragments(
        start=base_range[0],
        end=base_range[1],
    )
    base_chip_snapshot = surface.reorder_base_drag_chip_geometry_snapshot(
        snapshot=base_drag_snapshot,
        layout_view=base_drag_layout_view,
    )
    assert base_chip_snapshot.geometries_by_chip_index[0].chip_index == 0
    assert surface.reorder_base_drag_cursor_rect(base_range[0]).isEmpty() is False


def test_projection_surface_builds_reorder_layout_with_width_before_projection(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reorder preview layout should never rebuild projection at default 1px width."""

    box = show_prompt_editor(
        widgets,
        text="alpha, beta, gamma",
        width=320,
    )
    surface = surface_for(box)
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    observed_widths: list[float] = []
    original_one_pass = PromptProjectionLayout.set_projection_and_text_width

    def record_one_pass(
        self: PromptProjectionLayout,
        projection_document: PromptProjectionDocument,
        text_width: float,
        *,
        prompt_document_view: PromptDocumentView | None = None,
    ) -> None:
        """Record reorder layout widths before preserving production behavior."""

        observed_widths.append(text_width)
        original_one_pass(
            self,
            projection_document,
            text_width,
            prompt_document_view=prompt_document_view,
        )

    def fail_two_step_projection(
        self: PromptProjectionLayout,
        projection_document: PromptProjectionDocument,
        *,
        prompt_document_view: PromptDocumentView | None = None,
    ) -> None:
        """Fail if reorder layout construction regresses to the two-step API."""

        _ = self, projection_document, prompt_document_view
        raise AssertionError("reorder layout must set width before projection")

    monkeypatch.setattr(
        PromptProjectionLayout,
        "set_projection_and_text_width",
        record_one_pass,
    )
    monkeypatch.setattr(
        PromptProjectionLayout, "set_projection", fail_two_step_projection
    )

    surface.set_reorder_preview_state(preview_state)

    assert len(observed_widths) == 2
    assert all(width > 16.0 for width in observed_widths)


def test_projection_surface_reuses_stable_reorder_projections(
    widgets: list[QWidget],
) -> None:
    """Stable preview and base-drag projections should not rebuild repeatedly."""

    box = show_prompt_editor(
        widgets,
        text="alpha, beta, gamma",
        width=320,
    )
    surface = surface_for(box)
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    assert preview_state.base_drag_snapshot is not None

    surface.reset_reorder_geometry_cache_counters()
    surface.set_reorder_preview_state(preview_state)
    after_first_set = surface.reorder_geometry_cache_counters()
    surface.set_reorder_preview_state(preview_state)
    after_second_set = surface.reorder_geometry_cache_counters()

    assert after_first_set["projection_snapshot_rebuild_count"] == 2
    assert after_second_set["projection_snapshot_rebuild_count"] == 2
    assert after_second_set["preview_projection_active_cache_hit_count"] == 1


def test_projection_surface_reorder_projection_context_includes_active_target_identity(
    widgets: list[QWidget],
) -> None:
    """Surface delegation should pass preview target identity into service cache keys."""

    surface = new_projection_surface()
    widgets.append(surface)
    install_lora_wildcard_prompt_state(surface, "alpha, beta, gamma")
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    changed_target_state = replace(
        preview_state,
        active_drop_target_identity=("line", 0, 2),
    )

    surface.reset_reorder_geometry_cache_counters()
    surface.set_reorder_preview_state(preview_state)
    before_changed_target = surface.reorder_geometry_cache_counters()
    surface.set_reorder_preview_state(changed_target_state)
    after_changed_target = surface.reorder_geometry_cache_counters()

    assert cast(int, after_changed_target["projection_snapshot_rebuild_count"]) == (
        cast(int, before_changed_target["projection_snapshot_rebuild_count"]) + 1
    )


def test_projection_surface_reuses_reorder_preview_projection_lru_for_revisited_targets(
    widgets: list[QWidget],
) -> None:
    """Revisited preview targets should reuse cached projection layouts."""

    box = show_prompt_editor(
        widgets,
        text="alpha, beta, gamma",
        width=320,
    )
    surface = surface_for(box)
    preview_state_a = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    preview_state_b = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )
    assert preview_state_a.base_drag_snapshot is not None
    assert preview_state_b.base_drag_snapshot is not None

    surface.reset_reorder_geometry_cache_counters()
    surface.set_reorder_preview_state(preview_state_a)
    surface.set_reorder_preview_state(preview_state_b)
    before_revisit = surface.reorder_geometry_cache_counters()
    surface.set_reorder_preview_state(preview_state_a)
    after_revisit = surface.reorder_geometry_cache_counters()

    assert before_revisit["projection_snapshot_rebuild_count"] == 3
    assert after_revisit["projection_snapshot_rebuild_count"] == 3
    assert after_revisit["preview_projection_lru_cache_hit_count"] == 1


def test_projection_surface_reorder_preview_projection_lru_invalidates_on_clear(
    widgets: list[QWidget],
) -> None:
    """Clearing reorder preview state should discard cached preview layouts."""

    box = show_prompt_editor(
        widgets,
        text="alpha, beta, gamma",
        width=320,
    )
    surface = surface_for(box)
    preview_state_a = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    preview_state_b = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )

    surface.set_reorder_preview_state(preview_state_a)
    surface.set_reorder_preview_state(preview_state_b)
    surface.clear_reorder_preview_state()
    surface.reset_reorder_geometry_cache_counters()
    surface.set_reorder_preview_state(preview_state_a)
    counters = surface.reorder_geometry_cache_counters()

    assert counters["projection_snapshot_rebuild_count"] == 2
    assert counters["preview_projection_cache_miss_count"] == 1


def test_projection_surface_reorder_preview_projection_lru_survives_scroll_geometry_clear(
    widgets: list[QWidget],
) -> None:
    """Scroll-only geometry invalidation should keep preview projection entries."""

    box = show_prompt_editor(
        widgets,
        text="alpha, beta, gamma",
        width=320,
    )
    surface = surface_for(box)
    preview_state_a = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    preview_state_b = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )

    surface.set_reorder_preview_state(preview_state_a)
    surface.set_reorder_preview_state(preview_state_b)
    surface.refresh_scroll()
    before_revisit = surface.reorder_geometry_cache_counters()
    surface.set_reorder_preview_state(preview_state_a)
    after_revisit = surface.reorder_geometry_cache_counters()

    assert (
        after_revisit["projection_snapshot_rebuild_count"]
        == before_revisit["projection_snapshot_rebuild_count"]
    )
    assert cast(int, after_revisit["preview_projection_lru_cache_hit_count"]) == (
        cast(int, before_revisit["preview_projection_lru_cache_hit_count"]) + 1
    )


def test_projection_surface_reorder_preview_projection_lru_invalidates_on_display_mode_change(
    widgets: list[QWidget],
) -> None:
    """Display-mode changes should discard cached preview projection layouts."""

    box = show_prompt_editor(
        widgets,
        text="alpha, beta, gamma",
        width=320,
    )
    surface = surface_for(box)
    preview_state_a = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    preview_state_b = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )

    surface.set_reorder_preview_state(preview_state_a)
    surface.set_reorder_preview_state(preview_state_b)
    surface.set_display_mode(PromptProjectionDisplayMode.RAW)
    before_revisit = surface.reorder_geometry_cache_counters()
    surface.set_reorder_preview_state(preview_state_a)
    after_revisit = surface.reorder_geometry_cache_counters()

    assert cast(int, after_revisit["projection_snapshot_rebuild_count"]) == (
        cast(int, before_revisit["projection_snapshot_rebuild_count"]) + 1
    )


def test_projection_surface_reorder_placement_uses_chip_visual_vertical_affordance(
    widgets: list[QWidget],
) -> None:
    """Placement hit testing should not misclassify a chip-center drag as a blank row."""

    app = ensure_qapp()
    text = "1girl,\n\numbrella,"
    box = show_prompt_editor(
        widgets,
        text=text,
        width=360,
    )
    surface = surface_for(box)
    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(text)
    base_drag_layout_view = document_service.build_base_drag_layout_view(
        document_view,
        dragged_segment_index=1,
    )
    base_drag_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        base_drag_layout_view,
    )
    surface.set_reorder_preview_state(
        _build_reorder_preview_state(
            text,
            dragged_chip_index=1,
            drop_target=PromptLineDropTarget(row_index=0, insertion_index=1),
        )
    )
    process_events(app)
    snapshot = surface.reorder_base_drag_placement_snapshot(
        snapshot=base_drag_snapshot,
        layout_view=base_drag_layout_view,
    )

    placement = surface.reorder_placement_at_rect(
        QRectF(16.0, 8.0, 126.0, 26.0),
        snapshot=snapshot,
        active_placement_id=None,
    )

    assert placement is not None
    assert placement.target == PromptLineDropTarget(row_index=0, insertion_index=1)


def test_projection_surface_reorder_base_drag_geometry_reuses_stable_cache(
    widgets: list[QWidget],
) -> None:
    """Base-drag chip and placement geometry should reuse stable cached snapshots."""

    app = ensure_qapp()
    text = "alpha, beta, gamma"
    box = show_prompt_editor(widgets, text=text, width=360)
    surface = surface_for(box)
    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(text)
    base_drag_layout_view = document_service.build_base_drag_layout_view(
        document_view,
        dragged_segment_index=1,
    )
    base_drag_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        base_drag_layout_view,
    )
    surface.set_reorder_preview_state(
        _build_reorder_preview_state(
            text,
            dragged_chip_index=1,
            drop_target=PromptLineDropTarget(row_index=0, insertion_index=1),
        )
    )
    process_events(app)

    first_chip_snapshot = surface.reorder_base_drag_chip_geometry_snapshot(
        snapshot=base_drag_snapshot,
        layout_view=base_drag_layout_view,
    )
    second_chip_snapshot = surface.reorder_base_drag_chip_geometry_snapshot(
        snapshot=base_drag_snapshot,
        layout_view=base_drag_layout_view,
    )
    first_placement_snapshot = surface.reorder_base_drag_placement_snapshot(
        snapshot=base_drag_snapshot,
        layout_view=base_drag_layout_view,
    )
    second_placement_snapshot = surface.reorder_base_drag_placement_snapshot(
        snapshot=base_drag_snapshot,
        layout_view=base_drag_layout_view,
    )

    assert second_chip_snapshot is first_chip_snapshot
    assert second_placement_snapshot is first_placement_snapshot


def test_projection_surface_reorder_base_drag_geometry_cache_invalidates_on_resize(
    widgets: list[QWidget],
) -> None:
    """Viewport changes should invalidate stable base-drag geometry caches."""

    app = ensure_qapp()
    text = "alpha, beta, gamma"
    box = show_prompt_editor(widgets, text=text, width=360)
    surface = surface_for(box)
    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(text)
    base_drag_layout_view = document_service.build_base_drag_layout_view(
        document_view,
        dragged_segment_index=1,
    )
    base_drag_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        base_drag_layout_view,
    )
    surface.set_reorder_preview_state(
        _build_reorder_preview_state(
            text,
            dragged_chip_index=1,
            drop_target=PromptLineDropTarget(row_index=0, insertion_index=1),
        )
    )
    process_events(app)
    first_chip_snapshot = surface.reorder_base_drag_chip_geometry_snapshot(
        snapshot=base_drag_snapshot,
        layout_view=base_drag_layout_view,
    )

    box.resize(420, box.height())
    process_events(app)
    resized_chip_snapshot = surface.reorder_base_drag_chip_geometry_snapshot(
        snapshot=base_drag_snapshot,
        layout_view=base_drag_layout_view,
    )

    assert resized_chip_snapshot is not first_chip_snapshot


def test_projection_surface_reorder_preview_chip_geometry_reuses_target_cache(
    widgets: list[QWidget],
) -> None:
    """Repeated preview geometry for the same target should hit preview cache."""

    app = ensure_qapp()
    text = "alpha, beta, gamma"
    box = show_prompt_editor(widgets, text=text, width=360)
    surface = surface_for(box)
    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(text)
    preview_layout_view = document_service.build_preview_drop_layout_view(
        document_view,
        dragged_segment_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )
    preview_state = _build_reorder_preview_state(
        text,
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )
    surface.set_reorder_preview_state(preview_state)
    process_events(app)

    first_snapshot = surface.reorder_preview_chip_geometry_snapshot(
        snapshot=preview_state.preview_snapshot,
        layout_view=preview_layout_view,
    )
    second_snapshot = surface.reorder_preview_chip_geometry_snapshot(
        snapshot=preview_state.preview_snapshot,
        layout_view=preview_layout_view,
    )

    assert second_snapshot is first_snapshot


def test_projection_surface_reorder_preview_chip_geometry_reports_chip_reuse(
    widgets: list[QWidget],
) -> None:
    """Preview geometry summaries should expose chip-level reuse, not only misses."""

    app = ensure_qapp()
    text = "alpha, beta, gamma"
    box = show_prompt_editor(widgets, text=text, width=360)
    surface = surface_for(box)
    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(text)
    preview_layout_view = document_service.build_preview_drop_layout_view(
        document_view,
        dragged_segment_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )
    preview_state = _build_reorder_preview_state(
        text,
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )
    surface.set_reorder_preview_state(preview_state)
    process_events(app)
    surface.reset_reorder_geometry_cache_counters()

    first_snapshot = surface.reorder_preview_chip_geometry_snapshot(
        snapshot=preview_state.preview_snapshot,
        layout_view=preview_layout_view,
    )
    second_snapshot = surface.reorder_preview_chip_geometry_snapshot(
        snapshot=preview_state.preview_snapshot,
        layout_view=preview_layout_view,
    )
    counters = surface.reorder_geometry_cache_counters()

    assert second_snapshot is first_snapshot
    assert counters["preview_chip_geometry_reused_chip_count"] == len(
        first_snapshot.geometries_by_chip_index
    )
    assert counters["preview_chip_geometry_rebuilt_chip_count"] == len(
        first_snapshot.geometries_by_chip_index
    )


def test_projection_surface_reorder_placement_exposes_wrapped_visual_line_targets(
    widgets: list[QWidget],
) -> None:
    """A wrapped logical row should expose projection-owned targets on lower visual rows."""

    app = ensure_qapp()
    text = "alpha, beta, gamma, delta, epsilon, zeta"
    box = show_prompt_editor(
        widgets,
        text=text,
        width=190,
    )
    surface = surface_for(box)
    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(text)
    base_drag_layout_view = document_service.build_base_drag_layout_view(
        document_view,
        dragged_segment_index=5,
    )
    base_drag_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        base_drag_layout_view,
    )
    surface.set_reorder_preview_state(
        _build_reorder_preview_state(
            text,
            dragged_chip_index=5,
            drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
        )
    )
    process_events(app)
    snapshot = surface.reorder_base_drag_placement_snapshot(
        snapshot=base_drag_snapshot,
        layout_view=base_drag_layout_view,
    )
    lower_line_placement = next(
        placement
        for placement in snapshot.placements
        if isinstance(placement.target, PromptLineDropTarget)
        and placement.placement_id.visual_line_index > 0
    )

    selected = surface.reorder_placement_at_rect(
        lower_line_placement.hit_rect,
        snapshot=snapshot,
        active_placement_id=None,
    )

    assert selected == lower_line_placement


def test_projection_surface_excludes_dragged_chip_and_separator_from_preview_region(
    widgets: list[QWidget],
) -> None:
    """Preview drawing should suppress both the dragged chip text and its owned separator."""

    box = show_prompt_editor(
        widgets,
        text="alpha, beta, gamma",
        width=320,
    )
    surface = surface_for(box)
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    surface.set_reorder_preview_state(preview_state)

    visible_region = surface._preview_visible_region()  # noqa: SLF001
    assert visible_region is not None
    owned_ranges = preview_state.preview_snapshot.chip_owned_ranges_by_index[1]
    assert len(owned_ranges) == 2
    for start, end in owned_ranges:
        fragments = surface.reorder_preview_fragments(start=start, end=end)
        assert fragments
        for fragment in fragments:
            assert visible_region.intersected(
                QRegion(fragment.toAlignedRect())
            ).isEmpty()


def test_projection_surface_excludes_overlay_painted_preview_chips(
    widgets: list[QWidget],
) -> None:
    """Preview drawing should suppress only chips with fresh overlay snapshots."""

    box = show_prompt_editor(
        widgets,
        text="alpha, beta, gamma",
        width=320,
    )
    surface = surface_for(box)
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    surface.set_reorder_preview_state(preview_state)
    surface.set_reorder_overlay_suppressed_chip_indices(frozenset({2}))

    visible_region = surface._preview_visible_region()  # noqa: SLF001
    assert visible_region is not None
    suppressed_ranges = preview_state.preview_snapshot.chip_owned_ranges_by_index[2]
    for start, end in suppressed_ranges:
        fragments = surface.reorder_preview_fragments(start=start, end=end)
        assert fragments
        for fragment in fragments:
            assert visible_region.intersected(
                QRegion(fragment.toAlignedRect())
            ).isEmpty()

    unsuppressed_ranges = preview_state.preview_snapshot.chip_owned_ranges_by_index[0]
    assert any(
        not visible_region.intersected(QRegion(fragment.toAlignedRect())).isEmpty()
        for start, end in unsuppressed_ranges
        for fragment in surface.reorder_preview_fragments(start=start, end=end)
    )

    surface.set_reorder_overlay_suppressed_chip_indices(frozenset())
    restored_region = surface._preview_visible_region()  # noqa: SLF001
    assert restored_region is not None
    assert any(
        not restored_region.intersected(QRegion(fragment.toAlignedRect())).isEmpty()
        for start, end in suppressed_ranges
        for fragment in surface.reorder_preview_fragments(start=start, end=end)
    )


def test_projection_surface_clears_reorder_preview_state_back_to_live_rendering(
    widgets: list[QWidget],
) -> None:
    """Clearing preview state should restore the live surface queries and layout state."""

    box = show_prompt_editor(
        widgets,
        text="alpha, beta, gamma",
        width=320,
    )
    surface = surface_for(box)
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    surface.set_reorder_preview_state(preview_state)
    surface.clear_reorder_preview_state()

    assert surface._reorder_preview_projection.preview_document is None  # noqa: SLF001
    assert surface._reorder_preview_projection.preview_layout is None  # noqa: SLF001
    assert surface.reorder_preview_fragments(start=0, end=1) == ()
    assert surface.reorder_preview_cursor_rect(0).isEmpty() is True
