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

"""Prompt editor performance benchmark table reporting."""

from __future__ import annotations

from collections.abc import Sequence

from substitute.devtools.prompt_editor_performance.metrics import (
    REORDER_GEOMETRY_COUNT_COLUMNS,
    REORDER_INTERACTION_COUNT_COLUMNS,
    ScenarioResult,
    format_extra_value,
)

_HEADER = (
    "scenario",
    "chars",
    "ops",
    "avg_ms",
    "p95_ms",
    "max_ms",
    "rebuilds",
    "layout_ms",
    "ac_ms",
    "query_ms",
    "tag_gateway",
    "wildcard",
    "lora",
    "panel_ms",
    "lora_wall",
    "ghost_ms",
    "diag_ms",
    "menu_ms",
    "menu_scene",
    "menu_lora",
    "menu_seg",
    "menu_dan",
    "reorder_req",
    "reorder_run",
    "edit_range",
    "full_src",
    "cursor_set",
    "selection",
    "paste",
    "source_apply",
    "fast_i",
    "fast_d",
    "fast_nl",
    "inc_ok",
    "inc_def",
    "inc_rej",
    "wrap_def",
    "fb_def",
    "p_hit",
    "p_miss",
    "p_byp",
    "diag_frag",
    "diag_pres",
    "diag_clear",
    "fill_hit",
    "fill_miss",
    "paint_evt",
    "surf_geom",
    "surf_scroll",
    "surf_resize",
    "sync_layout",
    "shell_scroll",
    "shell_geom",
    "shell_layout",
    "fill_paint",
    "hover_evt",
    "hover_move",
    "focus_in",
    *tuple(label for label, _key in REORDER_GEOMETRY_COUNT_COLUMNS),
    *tuple(label for label, _key in REORDER_INTERACTION_COUNT_COLUMNS),
)
_COLUMN_WIDTHS = (
    26,
    7,
    5,
    8,
    8,
    8,
    8,
    10,
    8,
    9,
    11,
    8,
    7,
    9,
    8,
    9,
    8,
    8,
    10,
    9,
    8,
    8,
    11,
    11,
    10,
    8,
    10,
    9,
    7,
    12,
    7,
    7,
    7,
    7,
    7,
    7,
    8,
    6,
    6,
    6,
    9,
    9,
    10,
    8,
    9,
    9,
    8,
    9,
    9,
    10,
    10,
    11,
    11,
    11,
    12,
    10,
    12,
    10,
    9,
    10,
    8,
    10,
    8,
    9,
    10,
    12,
    11,
    *tuple(10 for _ in REORDER_INTERACTION_COUNT_COLUMNS),
)


def print_results(results: Sequence[ScenarioResult]) -> None:
    """Print one compact prompt-safe result table for all scenarios."""

    for row in result_table_rows(results):
        print(row)


def result_table_rows(results: Sequence[ScenarioResult]) -> tuple[str, ...]:
    """Return formatted prompt-safe result table rows for all scenarios."""

    rows = [format_table_row(_HEADER, _COLUMN_WIDTHS)]
    for result in results:
        rows.append(format_table_row(_result_cells(result), _COLUMN_WIDTHS))
    return tuple(rows)


def format_table_row(cells: Sequence[str], widths: Sequence[int]) -> str:
    """Return one aligned prompt-safe benchmark table row."""

    return " ".join(
        cell.ljust(width) if index == 0 else cell.rjust(width)
        for index, (cell, width) in enumerate(zip(cells, widths, strict=True))
    )


def _result_cells(result: ScenarioResult) -> tuple[str, ...]:
    """Return all printable cells for one benchmark result."""

    counters = result.instrumentation
    diagnostics_ms = (
        counters.diagnostics_activation.elapsed_ms
        + counters.diagnostics_visible_refresh.elapsed_ms
        + counters.diagnostics_action_prepare.elapsed_ms
    )
    menu_ms = (
        counters.context_menu_snapshot.elapsed_ms
        + counters.context_menu_open.elapsed_ms
    )
    return (
        result.name,
        str(result.characters),
        str(result.operations),
        f"{result.average_ms:.2f}",
        f"{result.p95_ms:.2f}",
        f"{result.max_ms:.2f}",
        str(counters.projection_rebuild.count),
        f"{counters.layout_snapshot.elapsed_ms:.2f}",
        f"{counters.autocomplete_refresh.elapsed_ms:.2f}",
        f"{counters.autocomplete_query_resolution.elapsed_ms:.2f}",
        str(counters.autocomplete_gateway_search.count),
        str(counters.wildcard_gateway_search.count),
        str(counters.lora_catalog_lookup.count),
        f"{counters.autocomplete_panel_update.elapsed_ms:.2f}",
        str(counters.autocomplete_lora_wall_update.count),
        f"{counters.autocomplete_preview_update.elapsed_ms:.2f}",
        f"{diagnostics_ms:.2f}",
        f"{menu_ms:.2f}",
        f"{counters.context_menu_scene_context.elapsed_ms:.2f}",
        f"{counters.context_menu_lora_actions.elapsed_ms:.2f}",
        f"{counters.context_menu_segment_snapshot.elapsed_ms:.2f}",
        f"{counters.context_menu_danbooru_snapshot.elapsed_ms:.2f}",
        str(counters.reorder_preview_request.count),
        str(counters.reorder_preview_run.count),
        str(counters.editing_replace_range.count),
        str(counters.editing_replace_full_source.count),
        str(counters.editing_set_cursor_positions.count),
        str(counters.editing_selection.count),
        str(counters.editing_paste.count),
        str(counters.surface_source_apply.count),
        str(counters.projection_fast_insert_applied.count),
        str(counters.projection_fast_delete_applied.count),
        str(counters.projection_fast_newline_applied.count),
        str(counters.projection_incremental_applied.count),
        str(counters.projection_incremental_deferred.count),
        str(counters.projection_incremental_rejected.count),
        str(counters.projection_wrap_deferred.count),
        str(counters.projection_fallback_deferred.count),
        str(counters.paint_cache_hit.count),
        str(counters.paint_cache_miss.count),
        str(counters.paint_cache_bypass.count),
        str(counters.diagnostic_fragment_lookup.count),
        str(counters.diagnostic_cache_preserve.count),
        str(counters.diagnostic_cache_clear.count),
        str(counters.fill_band_cache_hit.count),
        str(counters.fill_band_cache_miss.count),
        str(counters.surface_paint_event.count),
        str(counters.surface_refresh_geometry.count),
        str(counters.surface_refresh_scroll.count),
        str(counters.surface_resize_event.count),
        str(counters.surface_sync_layout.count),
        str(counters.shell_scroll_event.count),
        str(counters.shell_geometry_sync.count),
        str(counters.shell_layout_surface.count),
        str(counters.fill_plane_paint.count),
        str(counters.hover_update.count),
        str(counters.hover_move.count),
        str(counters.focus_in.count),
        *(
            format_extra_value(result.extra_counts.get(counter_key, 0))
            for _label, counter_key in REORDER_GEOMETRY_COUNT_COLUMNS
        ),
        *(
            format_extra_value(result.extra_counts.get(counter_key, 0))
            for _label, counter_key in REORDER_INTERACTION_COUNT_COLUMNS
        ),
    )


__all__ = [
    "format_table_row",
    "print_results",
    "result_table_rows",
]
