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

"""Verify prompt reorder projection cache instrumentation contracts."""

from __future__ import annotations


from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.reorder.views import (
    PromptLineDropTarget,
)

from tests.support.prompt_editor.projection_engine_support import surface_for

from .support import (
    _build_reorder_preview_state,
    _counter_delta,
    _create_prompt_editor,
    _ensure_qapp,
    _process_events,
)


def test_reorder_surface_projection_rebuild_counter_tracks_cache_misses(
    widgets: list[QWidget],
) -> None:
    """Projection counters should increment when preview snapshots are rebuilt."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha, beta, gamma")
    surface = surface_for(box)
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    surface.reset_reorder_geometry_cache_counters()
    before = surface.reorder_geometry_cache_counters()

    surface.set_reorder_preview_state(preview_state)
    _process_events(app)

    after = surface.reorder_geometry_cache_counters()

    assert _counter_delta(before, after, "preview_projection_cache_miss_count") == 1
    assert _counter_delta(before, after, "projection_snapshot_rebuild_count") == 2


def test_reorder_surface_preview_projection_cache_hit_avoids_rebuild(
    widgets: list[QWidget],
) -> None:
    """Preview projection cache hits should not rebuild projection snapshots."""

    app = _ensure_qapp()
    box = _create_prompt_editor(widgets, text="alpha, beta, gamma")
    surface = surface_for(box)
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    surface.reset_reorder_geometry_cache_counters()
    surface.set_reorder_preview_state(preview_state)
    _process_events(app)

    before_hit = surface.reorder_geometry_cache_counters()
    surface.set_reorder_preview_state(preview_state)
    _process_events(app)
    after_hit = surface.reorder_geometry_cache_counters()

    assert (
        _counter_delta(
            before_hit, after_hit, "preview_projection_active_cache_hit_count"
        )
        == 1
    )
    assert (
        _counter_delta(before_hit, after_hit, "projection_snapshot_rebuild_count") == 0
    )
    assert (
        _counter_delta(before_hit, after_hit, "preview_projection_cache_miss_count")
        == 0
    )
