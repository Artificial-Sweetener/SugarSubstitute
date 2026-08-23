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

"""Read lightweight prompt-editor state for real-shell snapshots and tracing."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.support.prompt_editor.autocomplete_owner_state import (
    autocomplete_owner_state,
)
from tests.support.prompt_editor.autocomplete_support import (
    RecordingPromptAutocompleteGateway,
)
from tests.support.prompt_editor.real_shell.autocomplete_state import (
    autocomplete_panel,
    autocomplete_preview_source_position,
    autocomplete_preview_state,
    autocomplete_preview_suffix,
    expected_ghost_suffix,
)
from tests.support.prompt_editor.real_shell.input_driver import editor_event_widget
from tests.support.prompt_editor.real_shell.models import (
    PromptEditorObservedEvent,
    PromptEditorStateSnapshot,
    PromptEditorVisibleLayoutRow,
    PromptEditorVisibleTextFragment,
    PromptFieldHandle,
)
from tests.support.qt.semantic_wait import wait_for_queued_qt_turn
from tests.support.prompt_editor.real_shell.session import PromptEditorRealShell


def rectangle_tuple(rectangle: QRect) -> tuple[int, int, int, int]:
    """Serialize one Qt rectangle."""

    return rectangle.x(), rectangle.y(), rectangle.width(), rectangle.height()


def global_rectangle_tuple(widget: QWidget | None) -> tuple[int, int, int, int] | None:
    """Serialize one widget geometry in global coordinates."""

    if widget is None:
        return None
    top_left = widget.mapToGlobal(QPoint(0, 0))
    return top_left.x(), top_left.y(), widget.width(), widget.height()


def object_path(widget: QWidget | None) -> str:
    """Return a stable diagnostic ancestry path for one Qt widget."""

    if widget is None:
        return "<none>"
    names: list[str] = []
    current: QWidget | None = widget
    while current is not None:
        object_name = current.objectName()
        names.append(
            type(current).__name__
            if not object_name
            else f"{type(current).__name__}#{object_name}"
        )
        current = current.parentWidget()
    return " <- ".join(names)


def scrollbar_value(widget: QWidget, accessor_name: str) -> int:
    """Return a scrollbar value from a dynamic Qt widget accessor."""

    accessor = getattr(widget, accessor_name, None)
    if not callable(accessor):
        return 0
    scrollbar = accessor()
    value = getattr(scrollbar, "value", None)
    return int(value()) if callable(value) else 0


class PromptEditorSnapshotCapture:
    """Assemble immutable real-shell state snapshots from explicit owner inputs."""

    def __init__(
        self,
        *,
        shell: PromptEditorRealShell,
        autocomplete_gateway: RecordingPromptAutocompleteGateway,
        observed_events: list[PromptEditorObservedEvent],
        projection_state_reader: Callable[[PromptEditor], dict[str, Any]],
    ) -> None:
        """Bind capture to one mounted shell and projection-state boundary."""

        self.shell = shell
        self.autocomplete_gateway = autocomplete_gateway
        self._observed_events = observed_events
        self._projection_state_reader = projection_state_reader

    def capture(
        self,
        field: PromptFieldHandle,
        *,
        label: str,
        settle_cycles: int = 6,
    ) -> PromptEditorStateSnapshot:
        """Capture headless shell, editor, autocomplete, projection diagnostics."""

        if settle_cycles:
            wait_for_queued_qt_turn()

        editor = field.editor

        panel = self.shell.editor_panels[field.workflow.workflow_id]

        viewport = editor.viewport()

        popup = autocomplete_panel(editor)

        cursor = cast(Any, editor).textCursor()

        selected_text = cursor.selectedText()

        selection_start = cursor.selectionStart()

        selection_end = cursor.selectionEnd()

        display_mode = _enum_text(editor.displayMode())

        autocomplete_preview = autocomplete_preview_state(editor)

        autocomplete_state = autocomplete_owner_state(editor)

        projection_state = self._projection_state_reader(editor)

        expected_suffix = expected_ghost_suffix(editor, autocomplete_preview)

        observed_event_start_index = max(0, len(self._observed_events) - 10000)

        recent_observed_events = tuple(
            self._observed_events[observed_event_start_index:]
        )

        popup_global_rect = global_rectangle_tuple(popup)

        popup_visual_visible = bool(popup is not None and popup.isVisible())

        return PromptEditorStateSnapshot(
            label=label,
            source_text=editor.toPlainText(),
            selected_text=selected_text,
            selected_source_text=editor.toPlainText()[selection_start:selection_end],
            selection_range=(selection_start, selection_end),
            selection_rects=cast(
                tuple[tuple[float, float, float, float], ...],
                projection_state["selection_rects"],
            ),
            cursor_position=cursor.position(),
            display_mode=display_mode,
            focus_widget_path=object_path(QApplication.focusWidget()),
            active_window_path=object_path(QApplication.activeWindow()),
            target_event_widget_path=object_path(editor_event_widget(editor)),
            geometries={
                "shell": rectangle_tuple(self.shell.geometry()),
                "panel": rectangle_tuple(panel.geometry()),
                "editor": rectangle_tuple(editor.geometry()),
                "viewport": rectangle_tuple(viewport.geometry()),
                "popup": rectangle_tuple(popup.geometry())
                if popup is not None
                else None,
            },
            global_geometries={
                "shell": global_rectangle_tuple(self.shell),
                "panel": global_rectangle_tuple(panel),
                "editor": global_rectangle_tuple(editor),
                "viewport": global_rectangle_tuple(viewport),
                "popup": popup_global_rect,
            },
            scroll_values={
                "editor_vertical": editor.verticalScrollBar().value(),
                "editor_horizontal": scrollbar_value(editor, "horizontalScrollBar"),
            },
            device_pixel_ratio=float(viewport.devicePixelRatioF()),
            autocomplete_gateway_calls=tuple(self.autocomplete_gateway.calls),
            popup_widget_exists=popup is not None,
            popup_state_visible=bool(popup is not None and popup.isVisible()),
            popup_visual_visible=popup_visual_visible,
            popup_global_rect=popup_global_rect,
            ghost_visual_visible=bool(
                projection_state["autocomplete_ghost_paint_visible_by_owner_state"]
            ),
            expected_ghost_suffix=expected_suffix,
            autocomplete_preview_active=autocomplete_preview is not None,
            autocomplete_preview_suffix=autocomplete_preview_suffix(
                autocomplete_preview
            ),
            autocomplete_preview_source_position=(
                autocomplete_preview_source_position(autocomplete_preview)
            ),
            autocomplete_session_lifecycle=autocomplete_state["lifecycle"],
            autocomplete_session_mode=autocomplete_state["mode"],
            autocomplete_session_selected_index=int(
                autocomplete_state["selected_index"]
            ),
            autocomplete_session_prefix=autocomplete_state["prefix"],
            autocomplete_session_word_start=_optional_int(
                autocomplete_state["word_start"]
            ),
            autocomplete_session_word_end=_optional_int(autocomplete_state["word_end"]),
            autocomplete_session_active_tag_end=_optional_int(
                autocomplete_state["active_tag_end"]
            ),
            autocomplete_session_suggestions=tuple(
                cast(tuple[str, ...], autocomplete_state["suggestions"])
            ),
            autocomplete_has_active_session=bool(autocomplete_state["has_active"]),
            autocomplete_presenter_panel_visible=bool(
                autocomplete_state["presenter_panel_visible"]
            ),
            autocomplete_presenter_panel_under_mouse=bool(
                autocomplete_state["presenter_panel_under_mouse"]
            ),
            autocomplete_source_revision=_optional_int(
                autocomplete_state["source_revision"]
            ),
            autocomplete_snapshot_source_length=_optional_int(
                autocomplete_state["snapshot_source_length"]
            ),
            autocomplete_snapshot_cursor_position=_optional_int(
                autocomplete_state["snapshot_cursor_position"]
            ),
            source_revision=_optional_int(projection_state["source_revision"]),
            semantic_source_revision=_optional_int(
                projection_state["semantic_source_revision"]
            ),
            semantic_revision=_optional_int(projection_state["semantic_revision"]),
            projection_semantic_revision=_optional_int(
                projection_state["projection_semantic_revision"]
            ),
            projection_revision=_optional_int(projection_state["projection_revision"]),
            layout_revision=_optional_int(projection_state["layout_revision"]),
            viewport_revision=_optional_int(projection_state["viewport_revision"]),
            paint_revision=_optional_int(projection_state["paint_revision"]),
            semantic_is_current=bool(projection_state["semantic_is_current"]),
            projection_is_current=bool(projection_state["projection_is_current"]),
            layout_is_current=bool(projection_state["layout_is_current"]),
            paint_is_current=bool(projection_state["paint_is_current"]),
            editing_session_source_revision=_optional_int(
                projection_state["editing_session_source_revision"]
            ),
            editing_session_cursor_position=_optional_int(
                projection_state["editing_session_cursor_position"]
            ),
            editing_session_anchor_position=_optional_int(
                projection_state["editing_session_anchor_position"]
            ),
            document_view_source_text=projection_state["document_view_source_text"],
            document_view_region_separator_count=int(
                projection_state["document_view_region_separator_count"]
            ),
            projection_document_source_text=projection_state[
                "projection_document_source_text"
            ],
            projection_region_separator_count=int(
                projection_state["projection_region_separator_count"]
            ),
            projection_region_separator_ranges=tuple(
                cast(
                    tuple[tuple[int, int], ...],
                    projection_state["projection_region_separator_ranges"],
                )
            ),
            caret_inside_region_separator=bool(
                projection_state["caret_inside_region_separator"]
            ),
            anchor_inside_region_separator=bool(
                projection_state["anchor_inside_region_separator"]
            ),
            region_chrome_divider_count=int(
                projection_state["region_chrome_divider_count"]
            ),
            region_chrome_rail_count=int(projection_state["region_chrome_rail_count"]),
            region_chrome_prepare_count=int(
                projection_state["region_chrome_prepare_count"]
            ),
            region_chrome_visited_line_count=int(
                projection_state["region_chrome_visited_line_count"]
            ),
            active_projection_source_text=projection_state[
                "active_projection_source_text"
            ],
            layout_projection_source_text=projection_state[
                "layout_projection_source_text"
            ],
            projection_text=projection_state["projection_text"],
            active_projection_text=projection_state["active_projection_text"],
            layout_projection_text=projection_state["layout_projection_text"],
            active_projection_layout_required=bool(
                projection_state["active_projection_layout_required"]
            ),
            layout_uses_projection_document=bool(
                projection_state["layout_uses_projection_document"]
            ),
            layout_uses_active_projection_document=bool(
                projection_state["layout_uses_active_projection_document"]
            ),
            paint_cache_key_present=bool(projection_state["paint_cache_key_present"]),
            last_content_paint_result=str(
                projection_state["last_content_paint_result"]
            ),
            last_content_paint_frame_is_current=bool(
                projection_state["last_content_paint_frame_is_current"]
            ),
            paint_cache_identity_matches_render_frame=bool(
                projection_state["paint_cache_identity_matches_render_frame"]
            ),
            paint_cache_source_revision=_optional_int(
                projection_state["paint_cache_source_revision"]
            ),
            paint_cache_projection_document_identity_matches_layout=bool(
                projection_state[
                    "paint_cache_projection_document_identity_matches_layout"
                ]
            ),
            paint_cache_layout_snapshot_identity_matches_layout=bool(
                projection_state["paint_cache_layout_snapshot_identity_matches_layout"]
            ),
            paint_cache_ghosted_run_ids=tuple(
                cast(tuple[str, ...], projection_state["paint_cache_ghosted_run_ids"])
            ),
            autocomplete_ghost_paint_visible_by_owner_state=bool(
                projection_state["autocomplete_ghost_paint_visible_by_owner_state"]
            ),
            projection_freshness=projection_state["projection_freshness"],
            projection_has_pending_update=bool(
                projection_state["projection_has_pending_update"]
            ),
            projection_has_stale_geometry=bool(
                projection_state["projection_has_stale_geometry"]
            ),
            caret_state_source_position=_optional_int(
                projection_state["caret_state_source_position"]
            ),
            anchor_state_source_position=_optional_int(
                projection_state["anchor_state_source_position"]
            ),
            caret_state_placement=str(projection_state["caret_state_placement"]),
            anchor_state_placement=str(projection_state["anchor_state_placement"]),
            caret_map_source_length=_optional_int(
                projection_state["caret_map_source_length"]
            ),
            caret_map_stop_count=_optional_int(
                projection_state["caret_map_stop_count"]
            ),
            caret_preferred_x=_optional_float(projection_state["caret_preferred_x"]),
            caret_rect_override=cast(
                tuple[float, float, float, float] | None,
                projection_state["caret_rect_override"],
            ),
            skip_next_same_source_soft_wrap_move=bool(
                projection_state["skip_next_same_source_soft_wrap_move"]
            ),
            projection_token_count=int(projection_state["projection_token_count"]),
            projection_run_count=int(projection_state["projection_run_count"]),
            layout_line_count=int(projection_state["layout_line_count"]),
            layout_text_fragment_count=int(
                projection_state["layout_text_fragment_count"]
            ),
            layout_inline_object_fragment_count=int(
                projection_state["layout_inline_object_fragment_count"]
            ),
            layout_content_width=float(projection_state["layout_content_width"]),
            layout_content_height=float(projection_state["layout_content_height"]),
            layout_text_width=float(projection_state["layout_text_width"]),
            projection_metrics_text_line_height=_optional_float(
                projection_state["projection_metrics_text_line_height"]
            ),
            projection_metrics_ascent=_optional_float(
                projection_state["projection_metrics_ascent"]
            ),
            projection_metrics_descent=_optional_float(
                projection_state["projection_metrics_descent"]
            ),
            projection_metrics_document_margin=_optional_float(
                projection_state["projection_metrics_document_margin"]
            ),
            projection_metrics_content_left_inset=_optional_float(
                projection_state["projection_metrics_content_left_inset"]
            ),
            projection_metrics_content_height=_optional_float(
                projection_state["projection_metrics_content_height"]
            ),
            shell_natural_height=_optional_int(
                projection_state["shell_natural_height"]
            ),
            shell_effective_height=_optional_int(
                projection_state["shell_effective_height"]
            ),
            shell_minimum_editor_height=_optional_int(
                projection_state["shell_minimum_editor_height"]
            ),
            shell_outer_vertical_padding=_optional_int(
                projection_state["shell_outer_vertical_padding"]
            ),
            shell_document_vertical_padding=_optional_int(
                projection_state["shell_document_vertical_padding"]
            ),
            visible_layout_rows=tuple(
                cast(
                    tuple[PromptEditorVisibleLayoutRow, ...],
                    projection_state["visible_layout_rows"],
                )
            ),
            visible_text_fragments=tuple(
                cast(
                    tuple[PromptEditorVisibleTextFragment, ...],
                    projection_state["visible_text_fragments"],
                )
            ),
            caret_token_id=cast(str | None, projection_state["caret_token_id"]),
            anchor_token_id=cast(str | None, projection_state["anchor_token_id"]),
            caret_token_id_resolves=bool(projection_state["caret_token_id_resolves"]),
            anchor_token_id_resolves=bool(projection_state["anchor_token_id_resolves"]),
            caret_rect=cast(
                tuple[float, float, float, float] | None,
                projection_state["caret_rect"],
            ),
            viewport_rect=cast(
                tuple[int, int, int, int],
                projection_state["viewport_rect"],
            ),
            caret_rect_finite=bool(projection_state["caret_rect_finite"]),
            caret_rect_has_area=bool(projection_state["caret_rect_has_area"]),
            caret_rect_intersects_viewport=bool(
                projection_state["caret_rect_intersects_viewport"]
            ),
            vertical_scroll_minimum=int(projection_state["vertical_scroll_minimum"]),
            vertical_scroll_maximum=int(projection_state["vertical_scroll_maximum"]),
            vertical_scroll_page_step=int(
                projection_state["vertical_scroll_page_step"]
            ),
            horizontal_scroll_minimum=int(
                projection_state["horizontal_scroll_minimum"]
            ),
            horizontal_scroll_maximum=int(
                projection_state["horizontal_scroll_maximum"]
            ),
            horizontal_scroll_page_step=int(
                projection_state["horizontal_scroll_page_step"]
            ),
            transient_caret_geometry_present=bool(
                projection_state["transient_caret_geometry_present"]
            ),
            transient_caret_geometry_valid=bool(
                projection_state["transient_caret_geometry_valid"]
            ),
            transient_insertion_overlay_present=bool(
                projection_state["transient_insertion_overlay_present"]
            ),
            transient_insertion_overlay_valid=bool(
                projection_state["transient_insertion_overlay_valid"]
            ),
            transient_insertion_overlay_source_range=cast(
                tuple[int, int] | None,
                projection_state["transient_insertion_overlay_source_range"],
            ),
            transient_insertion_overlay_viewport_rect=cast(
                tuple[float, float, float, float] | None,
                projection_state["transient_insertion_overlay_viewport_rect"],
            ),
            transient_insertion_overlay_repaint_rect=cast(
                tuple[float, float, float, float] | None,
                projection_state["transient_insertion_overlay_repaint_rect"],
            ),
            transient_deletion_overlay_present=bool(
                projection_state["transient_deletion_overlay_present"]
            ),
            transient_deletion_overlay_valid=bool(
                projection_state["transient_deletion_overlay_valid"]
            ),
            transient_deletion_overlay_source_range=cast(
                tuple[int, int] | None,
                projection_state["transient_deletion_overlay_source_range"],
            ),
            transient_deletion_overlay_viewport_rects=cast(
                tuple[tuple[float, float, float, float], ...],
                projection_state["transient_deletion_overlay_viewport_rects"],
            ),
            transient_deletion_overlay_erase_rects=cast(
                tuple[tuple[float, float, float, float], ...],
                projection_state["transient_deletion_overlay_erase_rects"],
            ),
            transient_deletion_overlay_repaint_rect=cast(
                tuple[float, float, float, float] | None,
                projection_state["transient_deletion_overlay_repaint_rect"],
            ),
            undo_available=bool(projection_state["undo_available"]),
            redo_available=bool(projection_state["redo_available"]),
            undo_depth=int(projection_state["undo_depth"]),
            redo_depth=int(projection_state["redo_depth"]),
            undo_max_depth=int(projection_state["undo_max_depth"]),
            redo_max_depth=int(projection_state["redo_max_depth"]),
            undo_edit_block_depth=int(projection_state["undo_edit_block_depth"]),
            undo_pending_state_present=bool(
                projection_state["undo_pending_state_present"]
            ),
            undo_typing_group_active=bool(projection_state["undo_typing_group_active"]),
            undo_typing_group_last_cursor_position=_optional_int(
                projection_state["undo_typing_group_last_cursor_position"]
            ),
            undo_delete_group_active=bool(projection_state["undo_delete_group_active"]),
            undo_delete_group_key=_optional_int(
                projection_state["undo_delete_group_key"]
            ),
            observed_event_start_index=observed_event_start_index,
            observed_event_end_index=len(self._observed_events),
            recent_observed_events=recent_observed_events,
        )


def _enum_text(value: object) -> str:
    """Return a stable string for one enum-like value."""

    enum_value = getattr(value, "value", None)
    return enum_value if isinstance(enum_value, str) else str(value)


def _optional_int(value: object) -> int | None:
    """Return an integer value when available."""

    return value if isinstance(value, int) else None


def _optional_float(value: object) -> float | None:
    """Return a floating-point value when available."""

    return float(value) if isinstance(value, int | float) else None
