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

"""Prompt editor performance metric models and helpers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, fields

REORDER_GEOMETRY_COUNT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("base_hit", "base_chip_geometry_cache_hit_count"),
    ("base_miss", "base_chip_geometry_cache_miss_count"),
    ("place_hit", "base_placement_cache_hit_count"),
    ("place_miss", "base_placement_cache_miss_count"),
    ("prev_hit", "preview_chip_geometry_cache_hit_count"),
    ("prev_miss", "preview_chip_geometry_cache_miss_count"),
    ("prev_reuse", "preview_chip_geometry_reused_chip_count"),
    ("prev_rebuild", "preview_chip_geometry_rebuilt_chip_count"),
    ("prev_reject", "preview_chip_geometry_reuse_rejected_count"),
)
REORDER_INTERACTION_COUNT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("drag_move", "drag_move_count"),
    ("target_same", "drop_target_no_change_count"),
    ("target_chg", "drop_target_changed_count"),
    ("prev_req", "preview_scheduler_request_count"),
    ("prev_run", "preview_scheduler_run_count"),
    ("prev_full", "preview_geometry_full_count"),
    ("proj_reb", "projection_snapshot_rebuild_count"),
    ("anim_plan", "animation_plan_build_count"),
    ("anim_apply", "animation_plan_applied_count"),
    ("proxy_reb", "drag_proxy_render_state_rebuild_count"),
    ("raster", "raster_build_count"),
    ("rast_hit", "raster_cache_hit_count"),
    ("rast_miss", "raster_cache_miss_count"),
    ("rend_hit", "raster_entries_render_cache_hit_count"),
    ("rend_miss", "raster_entries_render_cache_miss_count"),
    ("land_hit", "landing_paint_cache_hit_count"),
    ("land_miss", "landing_paint_cache_miss_count"),
    ("ptr_work", "pointer_unexpected_work_count"),
    ("alt_open", "alt_open_ms"),
    ("alt_rel", "alt_release_ms"),
    ("max_drag", "max_drag_move_ms"),
    ("max_sync", "max_preview_sync_ms"),
    ("max_live", "max_live_visuals_ms"),
    ("max_plan", "max_render_plan_ms"),
)


@dataclass(slots=True)
class OperationCounter:
    """Collect counts and elapsed milliseconds for one instrumented operation."""

    count: int = 0
    elapsed_ms: float = 0.0

    def record(self, elapsed_ms: float) -> None:
        """Add one measured operation duration."""

        self.count += 1
        self.elapsed_ms += elapsed_ms

    def reset(self) -> None:
        """Clear accumulated count and elapsed time."""

        self.count = 0
        self.elapsed_ms = 0.0


@dataclass(slots=True)
class Instrumentation:
    """Store operation counters used during one benchmark run."""

    projection_rebuild: OperationCounter
    layout_snapshot: OperationCounter
    autocomplete_refresh: OperationCounter
    autocomplete_query_resolution: OperationCounter
    autocomplete_gateway_search: OperationCounter
    wildcard_gateway_search: OperationCounter
    lora_catalog_lookup: OperationCounter
    autocomplete_panel_update: OperationCounter
    autocomplete_lora_wall_update: OperationCounter
    autocomplete_preview_update: OperationCounter
    diagnostics_activation: OperationCounter
    diagnostics_visible_refresh: OperationCounter
    diagnostics_action_prepare: OperationCounter
    context_menu_snapshot: OperationCounter
    context_menu_scene_context: OperationCounter
    context_menu_lora_actions: OperationCounter
    context_menu_segment_snapshot: OperationCounter
    context_menu_danbooru_snapshot: OperationCounter
    context_menu_open: OperationCounter
    reorder_preview_request: OperationCounter
    reorder_preview_run: OperationCounter
    editing_replace_range: OperationCounter
    editing_replace_full_source: OperationCounter
    editing_set_cursor_positions: OperationCounter
    editing_selection: OperationCounter
    editing_paste: OperationCounter
    surface_source_apply: OperationCounter
    projection_fast_insert_applied: OperationCounter
    projection_fast_delete_applied: OperationCounter
    projection_fast_newline_applied: OperationCounter
    projection_incremental_applied: OperationCounter
    projection_incremental_deferred: OperationCounter
    projection_incremental_rejected: OperationCounter
    projection_wrap_deferred: OperationCounter
    projection_fallback_deferred: OperationCounter
    paint_cache_hit: OperationCounter
    paint_cache_miss: OperationCounter
    paint_cache_bypass: OperationCounter
    diagnostic_fragment_lookup: OperationCounter
    diagnostic_cache_preserve: OperationCounter
    diagnostic_cache_clear: OperationCounter
    fill_band_cache_hit: OperationCounter
    fill_band_cache_miss: OperationCounter
    surface_paint_event: OperationCounter
    surface_refresh_geometry: OperationCounter
    surface_refresh_scroll: OperationCounter
    surface_resize_event: OperationCounter
    surface_sync_layout: OperationCounter
    shell_scroll_event: OperationCounter
    shell_geometry_sync: OperationCounter
    shell_layout_surface: OperationCounter
    fill_plane_paint: OperationCounter
    hover_update: OperationCounter
    hover_move: OperationCounter
    focus_in: OperationCounter

    @classmethod
    def create(cls) -> "Instrumentation":
        """Return empty counters for all measured operations."""

        return cls(
            **{
                instrumentation_field.name: OperationCounter()
                for instrumentation_field in fields(cls)
            }
        )

    def reset(self) -> None:
        """Clear all counters so measured rows exclude setup work."""

        for instrumentation_field in fields(self):
            value = getattr(self, instrumentation_field.name)
            if isinstance(value, OperationCounter):
                value.reset()


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    """Store summarized timing results for one scenario."""

    name: str
    characters: int
    operations: int
    average_ms: float
    p95_ms: float
    max_ms: float
    instrumentation: Instrumentation
    extra_counts: dict[str, int | float] = field(default_factory=dict)


def average(values: Sequence[float]) -> float:
    """Return the arithmetic mean for a possibly empty sequence."""

    return sum(values) / len(values) if values else 0.0


def percentile(values: Sequence[float], percentile_rank: int) -> float:
    """Return a nearest-rank percentile for a possibly empty sequence."""

    if not values:
        return 0.0
    ordered = sorted(values)
    index = round(((percentile_rank / 100.0) * (len(ordered) - 1)))
    return ordered[index]


def format_extra_value(value: int | float) -> str:
    """Return a compact table cell for integer counters and millisecond floats."""

    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


__all__ = [
    "Instrumentation",
    "OperationCounter",
    "REORDER_GEOMETRY_COUNT_COLUMNS",
    "REORDER_INTERACTION_COUNT_COLUMNS",
    "ScenarioResult",
    "average",
    "format_extra_value",
    "percentile",
]
