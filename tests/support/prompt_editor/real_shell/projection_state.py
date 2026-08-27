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

"""Capture revision, document, cache, caret, and undo state for snapshots."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRect, QRectF

from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.support.prompt_editor.real_shell.projection_layout import (
    _layout_content_size,
    _layout_count,
    _layout_selection_rects,
    _optional_float,
    _optional_int,
    _position_inside_any_range,
    _projection_metrics_content_height,
    _safeenum_value,
    _shell_document_vertical_padding,
    _shell_minimum_editor_height,
    _shell_outer_vertical_padding,
    _surface_selection,
    _token_id_resolves,
    _visible_layout_rows,
    _visible_text_fragments,
)
from tests.support.prompt_editor.real_shell.projection_transients import (
    _rectf_is_finite,
    _rectf_tuple,
    _rectfs_tuple,
    _scrollbar_maximum,
    _scrollbar_minimum,
    _scrollbar_page_step,
    _surface_caret_rect,
    _surface_scroll_offset,
    _transient_deletion_overlay_erase_rects,
    _transient_deletion_overlay_repaint_rect,
    _transient_deletion_overlay_viewport_rects,
    _transient_insertion_overlay_repaint_rect,
    _transient_insertion_overlay_viewport_rect,
    valid_caret_geometry as read_valid_caret_geometry,
    valid_deletion_overlay as read_valid_deletion_overlay,
    valid_insertion_overlay as read_valid_insertion_overlay,
)


def projection_owner_state(editor: PromptEditor) -> dict[str, Any]:
    """Return source, caret, and projection state from the real projection owner."""

    surface = getattr(editor, "_surface", None)
    editor_state = getattr(surface, "editor_state", None)
    revision_graph = getattr(editor_state, "revisions", None)
    semantic_snapshot = getattr(editor_state, "semantic", None)
    edit_semantic_snapshot = getattr(editor_state, "edit_semantic", None)
    projection_semantic_snapshot = getattr(
        editor_state,
        "projection_semantic",
        None,
    )
    projection_snapshot = getattr(editor_state, "projection", None)
    layout_state_snapshot = getattr(editor_state, "layout", None)
    viewport_state_snapshot = getattr(editor_state, "viewport", None)
    paint_state_snapshot = getattr(editor_state, "paint", None)
    semantic_identity = getattr(semantic_snapshot, "identity", None)
    projection_semantic_identity = getattr(
        projection_semantic_snapshot,
        "identity",
        None,
    )
    projection_identity = getattr(projection_snapshot, "identity", None)
    layout_identity = getattr(layout_state_snapshot, "identity", None)
    viewport_identity = getattr(viewport_state_snapshot, "identity", None)
    paint_identity = getattr(paint_state_snapshot, "identity", None)
    editing_session = getattr(surface, "_editing_session", None)
    document_view = getattr(edit_semantic_snapshot, "document", None)
    projection_document = getattr(projection_snapshot, "document", None)
    active_projection_document = (
        surface.active_projection_document() if surface is not None else None
    )
    layout = getattr(surface, "_layout", None)
    prepared_frame = getattr(layout, "frame", None)
    layout_output = getattr(prepared_frame, "output", None)
    layout_geometry = getattr(prepared_frame, "geometry", None)
    layout_configuration = getattr(layout_output, "configuration", None)
    layout_projection_document = getattr(
        layout_output,
        "projection_document",
        None,
    )
    region_chrome = getattr(surface, "_region_chrome", None)
    region_chrome_snapshot_for = getattr(region_chrome, "snapshot_for", None)
    region_chrome_snapshot = (
        region_chrome_snapshot_for(layout_output)
        if callable(region_chrome_snapshot_for) and layout_output is not None
        else None
    )
    render_compositor = getattr(surface, "_render_compositor", None)
    content_cache_snapshot = getattr(
        render_compositor,
        "content_cache_snapshot",
        None,
    )
    paint_cache_key = getattr(content_cache_snapshot, "key", None)
    last_content_paint_result = str(
        getattr(content_cache_snapshot, "last_paint_result", "unpainted")
    )
    last_content_paint_identity = getattr(
        content_cache_snapshot,
        "last_paint_identity",
        None,
    )
    render_frame_owner = getattr(surface, "_render_frame_owner", None)
    render_frame = getattr(render_frame_owner, "frame", None)
    render_frame_paint_identity = getattr(render_frame, "paint_identity", None)
    paint_cache_identity = getattr(paint_cache_key, "paint_identity", None)
    paint_cache_state = (
        getattr(paint_state_snapshot, "state", None)
        if paint_cache_identity == paint_identity
        else None
    )
    ghosted_run_ids = tuple(
        str(run_id) for run_id in getattr(paint_cache_state, "ghosted_run_ids", ())
    )
    projection_session = getattr(surface, "_session", None)
    transient_overlays = getattr(surface, "_transient_edit_overlays", None)
    freshness_controller = getattr(surface, "_projection_freshness_controller", None)
    caret_state = getattr(surface, "_cursor_state", None)
    anchor_state = getattr(surface, "_anchor_state", None)
    caret_map_document = (
        active_projection_document
        if getattr(projection_session, "autocomplete_preview", None) is not None
        else projection_document
    )
    caret_map = getattr(caret_map_document, "caret_map", None)
    caret_preferred_x = getattr(surface, "_preferred_x", None)
    caret_rect_override = getattr(surface, "_caret_rect_override", None)
    freshness = getattr(freshness_controller, "freshness", None)
    pending_update = getattr(freshness_controller, "has_pending_update", None)
    stale_geometry = getattr(
        freshness_controller,
        "has_stale_projection_geometry",
        None,
    )
    has_pending_update = bool(pending_update()) if callable(pending_update) else False
    has_stale_geometry = bool(stale_geometry()) if callable(stale_geometry) else False
    freshness_is_stale_safe = has_stale_geometry
    source_identity = getattr(revision_graph, "source", None)
    source_revision = getattr(source_identity, "source_revision", None)
    insertion_overlay = getattr(transient_overlays, "insertion_overlay", None)
    deletion_overlay = getattr(transient_overlays, "deletion_overlay", None)
    caret_geometry = getattr(transient_overlays, "caret_geometry", None)
    valid_insertion_overlay = read_valid_insertion_overlay(
        transient_overlays=transient_overlays,
        freshness_is_stale_safe=freshness_is_stale_safe,
        source_identity=source_identity,
    )
    valid_deletion_overlay = read_valid_deletion_overlay(
        transient_overlays=transient_overlays,
        freshness_is_stale_safe=freshness_is_stale_safe,
        source_identity=source_identity,
    )
    valid_caret_geometry = read_valid_caret_geometry(
        transient_overlays=transient_overlays,
        freshness_is_stale_safe=freshness_is_stale_safe,
        source_identity=source_identity,
        cursor_position=getattr(caret_state, "source_position", None),
        anchor_position=getattr(anchor_state, "source_position", None),
    )
    selection = _surface_selection(surface)
    selection_rects = _layout_selection_rects(layout_geometry, selection)
    layout_metrics = getattr(layout_configuration, "metrics", None)
    scroll_offset = _surface_scroll_offset(surface)
    insertion_overlay_viewport_rect = _transient_insertion_overlay_viewport_rect(
        transient_overlays=transient_overlays,
        overlay=valid_insertion_overlay,
        metrics=layout_metrics,
        scroll_offset=scroll_offset,
    )
    insertion_overlay_repaint_rect = _transient_insertion_overlay_repaint_rect(
        transient_overlays=transient_overlays,
        overlay=valid_insertion_overlay,
        metrics=layout_metrics,
        scroll_offset=scroll_offset,
    )
    deletion_overlay_viewport_rects = _transient_deletion_overlay_viewport_rects(
        transient_overlays=transient_overlays,
        overlay=valid_deletion_overlay,
        scroll_offset=scroll_offset,
    )
    deletion_overlay_erase_rects = _transient_deletion_overlay_erase_rects(
        transient_overlays=transient_overlays,
        overlay=valid_deletion_overlay,
        scroll_offset=scroll_offset,
    )
    deletion_overlay_repaint_rect = _transient_deletion_overlay_repaint_rect(
        transient_overlays=transient_overlays,
        overlay=valid_deletion_overlay,
        scroll_offset=scroll_offset,
    )
    undo_stack = getattr(editing_session, "_undo_stack", None)
    caret_rect = _surface_caret_rect(surface)
    viewport = surface.viewport() if surface is not None else None
    viewport_rect = viewport.rect() if viewport is not None else QRect()
    vertical_scrollbar = surface.verticalScrollBar() if surface is not None else None
    horizontal_scrollbar = (
        surface.horizontalScrollBar() if surface is not None else None
    )
    layout_content_size = _layout_content_size(layout_output)
    shell_sizing = getattr(editor, "_sizing", None)
    caret_token_id = getattr(caret_state, "token_id", None)
    anchor_token_id = getattr(anchor_state, "token_id", None)
    projection_region_separators = tuple(
        getattr(
            getattr(projection_document, "region_structure", None),
            "separators",
            (),
        )
    )
    projection_region_separator_ranges = tuple(
        (int(separator.token_start), int(separator.token_end))
        for separator in projection_region_separators
    )
    caret_source_position = _optional_int(getattr(caret_state, "source_position", None))
    anchor_source_position = _optional_int(
        getattr(anchor_state, "source_position", None)
    )
    paint_cache_layout_identity = getattr(
        paint_cache_identity,
        "layout",
        None,
    )
    paint_cache_projection_identity = getattr(
        paint_cache_layout_identity,
        "projection",
        None,
    )
    paint_cache_semantic_identity = getattr(
        paint_cache_projection_identity,
        "semantic",
        None,
    )
    paint_cache_source_identity = getattr(
        paint_cache_semantic_identity,
        "source",
        None,
    )
    semantic_source_identity = getattr(semantic_identity, "source", None)
    semantic_revision = getattr(semantic_identity, "semantic_revision", None)
    projection_semantic_revision = getattr(
        projection_semantic_identity,
        "semantic_revision",
        None,
    )
    projection_revision = getattr(
        projection_identity,
        "projection_revision",
        None,
    )
    layout_revision = getattr(layout_identity, "layout_revision", None)
    viewport_revision = getattr(viewport_identity, "viewport_revision", None)
    paint_revision = getattr(paint_identity, "paint_state_revision", None)
    return {
        "source_revision": source_revision,
        "semantic_source_revision": getattr(
            semantic_source_identity,
            "source_revision",
            None,
        ),
        "semantic_revision": semantic_revision,
        "projection_semantic_revision": projection_semantic_revision,
        "projection_revision": projection_revision,
        "layout_revision": layout_revision,
        "viewport_revision": viewport_revision,
        "paint_revision": paint_revision,
        "semantic_is_current": (
            bool(getattr(revision_graph, "semantic_is_current", False))
        ),
        "projection_is_current": (
            bool(getattr(revision_graph, "projection_is_current", False))
        ),
        "layout_is_current": (
            bool(getattr(revision_graph, "layout_is_current", False))
        ),
        "paint_is_current": (bool(getattr(revision_graph, "paint_is_current", False))),
        "editing_session_source_revision": getattr(
            editing_session,
            "source_revision",
            None,
        ),
        "editing_session_cursor_position": getattr(
            editing_session,
            "cursor_position",
            None,
        ),
        "editing_session_anchor_position": getattr(
            editing_session,
            "anchor_position",
            None,
        ),
        "document_view_source_text": str(getattr(document_view, "source_text", "")),
        "document_view_region_separator_count": len(
            getattr(getattr(document_view, "region_structure", None), "separators", ())
        ),
        "projection_document_source_text": str(
            getattr(projection_document, "source_text", "")
        ),
        "projection_region_separator_count": len(projection_region_separators),
        "projection_region_separator_ranges": projection_region_separator_ranges,
        "caret_inside_region_separator": _position_inside_any_range(
            caret_source_position,
            projection_region_separator_ranges,
        ),
        "anchor_inside_region_separator": _position_inside_any_range(
            anchor_source_position,
            projection_region_separator_ranges,
        ),
        "region_chrome_divider_count": len(
            getattr(region_chrome_snapshot, "divider_lines", ())
        ),
        "region_chrome_rail_count": len(
            getattr(region_chrome_snapshot, "rail_lines", ())
        ),
        "region_chrome_prepare_count": int(getattr(region_chrome, "prepare_count", 0)),
        "region_chrome_visited_line_count": int(
            getattr(region_chrome_snapshot, "visited_line_count", 0)
        ),
        "active_projection_source_text": str(
            getattr(active_projection_document, "source_text", "")
        ),
        "layout_projection_source_text": str(
            getattr(layout_projection_document, "source_text", "")
        ),
        "projection_text": str(getattr(projection_document, "projection_text", "")),
        "active_projection_text": str(
            getattr(active_projection_document, "projection_text", "")
        ),
        "layout_projection_text": str(
            getattr(layout_projection_document, "projection_text", "")
        ),
        "active_projection_layout_required": bool(
            surface is not None and surface._active_projection_requires_layout()
        ),
        "layout_uses_projection_document": (
            layout_projection_document is projection_document
        ),
        "layout_uses_active_projection_document": (
            layout_projection_document is active_projection_document
        ),
        "paint_cache_key_present": paint_cache_key is not None,
        "last_content_paint_result": last_content_paint_result,
        "last_content_paint_frame_is_current": (
            last_content_paint_identity is render_frame_paint_identity
            and render_frame_paint_identity is paint_identity
        ),
        "paint_cache_identity_matches_render_frame": (
            paint_cache_key is None
            or paint_cache_identity is last_content_paint_identity
        ),
        "paint_cache_source_revision": getattr(
            paint_cache_source_identity,
            "source_revision",
            None,
        ),
        "paint_cache_projection_document_identity_matches_layout": (
            paint_cache_key is None
            or paint_cache_projection_identity
            == getattr(layout_identity, "projection", None)
        ),
        "paint_cache_layout_snapshot_identity_matches_layout": (
            paint_cache_key is None or paint_cache_layout_identity == layout_identity
        ),
        "paint_cache_ghosted_run_ids": ghosted_run_ids,
        "autocomplete_ghost_paint_visible_by_owner_state": bool(
            (
                layout_projection_document is not None
                and projection_document is not None
                and getattr(layout_projection_document, "projection_text", "")
                != getattr(projection_document, "projection_text", "")
            )
            or ghosted_run_ids
        ),
        "projection_freshness": _safeenum_value(freshness),
        "projection_has_pending_update": bool(has_pending_update),
        "projection_has_stale_geometry": bool(has_stale_geometry),
        "caret_state_source_position": getattr(caret_state, "source_position", None),
        "anchor_state_source_position": getattr(anchor_state, "source_position", None),
        "caret_state_placement": _enum_value_text(
            getattr(caret_state, "placement", None)
        ),
        "anchor_state_placement": _enum_value_text(
            getattr(anchor_state, "placement", None)
        ),
        "caret_map_source_length": getattr(caret_map, "source_length", None),
        "caret_map_stop_count": None
        if caret_map is None
        else len(getattr(caret_map, "stops", ())),
        "selection_rects": _rectfs_tuple(selection_rects),
        "caret_preferred_x": caret_preferred_x
        if isinstance(caret_preferred_x, int | float)
        else None,
        "caret_rect_override": _rectf_tuple(
            caret_rect_override if isinstance(caret_rect_override, QRectF) else None
        ),
        "skip_next_same_source_soft_wrap_move": bool(
            getattr(surface, "_skip_next_same_source_soft_wrap_move", False)
        ),
        "projection_token_count": len(getattr(projection_document, "tokens", ())),
        "projection_run_count": len(getattr(projection_document, "runs", ())),
        "layout_line_count": _layout_count(layout_output, "line_count"),
        "layout_text_fragment_count": _layout_count(
            layout_output,
            "text_fragment_count",
        ),
        "layout_inline_object_fragment_count": _layout_count(
            layout_output,
            "inline_object_fragment_count",
        ),
        "layout_content_width": layout_content_size[0],
        "layout_content_height": layout_content_size[1],
        "layout_text_width": float(getattr(layout_configuration, "text_width", 0.0)),
        "projection_metrics_text_line_height": _optional_float(
            getattr(layout_metrics, "text_line_height", None)
        ),
        "projection_metrics_ascent": _optional_float(
            getattr(layout_metrics, "text_ascent", None)
        ),
        "projection_metrics_descent": _optional_float(
            getattr(layout_metrics, "text_descent", None)
        ),
        "projection_metrics_document_margin": _optional_float(
            getattr(layout_metrics, "document_margin", None)
        ),
        "projection_metrics_content_left_inset": _optional_float(
            getattr(layout_metrics, "content_left_inset", None)
        ),
        "projection_metrics_content_height": _projection_metrics_content_height(
            layout_output=layout_output,
            metrics=layout_metrics,
        ),
        "shell_natural_height": _optional_int(
            getattr(shell_sizing, "_last_natural_height", None)
        ),
        "shell_effective_height": _optional_int(
            getattr(shell_sizing, "_last_effective_height", None)
        ),
        "shell_minimum_editor_height": _shell_minimum_editor_height(shell_sizing),
        "shell_outer_vertical_padding": _shell_outer_vertical_padding(shell_sizing),
        "shell_document_vertical_padding": _shell_document_vertical_padding(
            shell_sizing
        ),
        "visible_layout_rows": _visible_layout_rows(
            layout_output=layout_output,
            metrics=layout_metrics,
            source_text=editor.toPlainText(),
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        ),
        "visible_text_fragments": _visible_text_fragments(
            layout_output=layout_output,
            metrics=layout_metrics,
            source_text=editor.toPlainText(),
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        ),
        "caret_token_id": caret_token_id if isinstance(caret_token_id, str) else None,
        "anchor_token_id": anchor_token_id
        if isinstance(anchor_token_id, str)
        else None,
        "caret_token_id_resolves": _token_id_resolves(
            active_projection_document,
            caret_token_id,
        ),
        "anchor_token_id_resolves": _token_id_resolves(
            active_projection_document,
            anchor_token_id,
        ),
        "caret_rect": _rectf_tuple(caret_rect),
        "viewport_rect": _rect_tuple(viewport_rect),
        "caret_rect_finite": _rectf_is_finite(caret_rect),
        "caret_rect_has_area": bool(
            caret_rect is not None
            and caret_rect.width() >= 1.0
            and caret_rect.height() >= 1.0
        ),
        "caret_rect_intersects_viewport": bool(
            caret_rect is not None
            and QRectF(viewport_rect)
            .adjusted(-4.0, -4.0, 4.0, 4.0)
            .intersects(caret_rect)
        ),
        "vertical_scroll_minimum": _scrollbar_minimum(vertical_scrollbar),
        "vertical_scroll_maximum": _scrollbar_maximum(vertical_scrollbar),
        "vertical_scroll_page_step": _scrollbar_page_step(vertical_scrollbar),
        "horizontal_scroll_minimum": _scrollbar_minimum(horizontal_scrollbar),
        "horizontal_scroll_maximum": _scrollbar_maximum(horizontal_scrollbar),
        "horizontal_scroll_page_step": _scrollbar_page_step(horizontal_scrollbar),
        "transient_caret_geometry_present": caret_geometry is not None,
        "transient_caret_geometry_valid": valid_caret_geometry is not None,
        "transient_insertion_overlay_present": insertion_overlay is not None,
        "transient_insertion_overlay_valid": valid_insertion_overlay is not None,
        "transient_insertion_overlay_source_range": (
            None
            if insertion_overlay is None
            else (
                int(getattr(insertion_overlay, "source_start", 0)),
                int(getattr(insertion_overlay, "source_start", 0))
                + len(str(getattr(insertion_overlay, "text", ""))),
            )
        ),
        "transient_insertion_overlay_viewport_rect": _rectf_tuple(
            insertion_overlay_viewport_rect
        ),
        "transient_insertion_overlay_repaint_rect": _rectf_tuple(
            insertion_overlay_repaint_rect
        ),
        "transient_deletion_overlay_present": deletion_overlay is not None,
        "transient_deletion_overlay_valid": valid_deletion_overlay is not None,
        "transient_deletion_overlay_source_range": (
            None
            if deletion_overlay is None
            else (
                int(getattr(deletion_overlay, "source_start", 0)),
                int(getattr(deletion_overlay, "source_end", 0)),
            )
        ),
        "transient_deletion_overlay_viewport_rects": _rectfs_tuple(
            deletion_overlay_viewport_rects
        ),
        "transient_deletion_overlay_erase_rects": _rectfs_tuple(
            deletion_overlay_erase_rects
        ),
        "transient_deletion_overlay_repaint_rect": _rectf_tuple(
            deletion_overlay_repaint_rect
        ),
        "undo_available": bool(editing_session.can_undo())
        if editing_session is not None
        else False,
        "redo_available": bool(editing_session.can_redo())
        if editing_session is not None
        else False,
        "undo_depth": int(getattr(undo_stack, "undo_depth", 0)),
        "redo_depth": int(getattr(undo_stack, "redo_depth", 0)),
        "undo_max_depth": int(getattr(undo_stack, "_max_undo_states", 0)),
        "redo_max_depth": int(getattr(undo_stack, "_max_redo_states", 0)),
        "undo_edit_block_depth": int(getattr(undo_stack, "edit_block_depth", 0)),
        "undo_pending_state_present": (
            getattr(undo_stack, "_pending_undo_state", None) is not None
        ),
        "undo_typing_group_active": bool(
            getattr(undo_stack, "typing_group_active", False)
        ),
        "undo_typing_group_last_cursor_position": getattr(
            undo_stack,
            "_typing_group_last_cursor_position",
            None,
        ),
        "undo_delete_group_active": bool(
            getattr(undo_stack, "delete_group_active", False)
        ),
        "undo_delete_group_key": getattr(undo_stack, "_delete_group_key", None),
    }


def _rect_tuple(rect: QRect) -> tuple[int, int, int, int]:
    """Serialize one Qt rectangle."""

    return rect.x(), rect.y(), rect.width(), rect.height()


def _enum_value_text(value: object) -> str:
    """Return the stable string payload for one optional enum value."""

    raw_value = getattr(value, "value", value)
    return "" if raw_value is None else str(raw_value)
