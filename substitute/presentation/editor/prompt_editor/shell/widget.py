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

"""Define the internal prompt-editor shell owner boundary."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QWidget

from .fill_plane import PromptFillPlaneSurface, update_prompt_fill_backing


@dataclass(frozen=True, slots=True)
class PromptEditorPublicWidgetBoundary:
    """Record public APIs that remain canonical on ``PromptEditor``."""

    shell_methods: tuple[str, ...]
    editing_methods: tuple[str, ...]
    projection_methods: tuple[str, ...]
    feature_methods: tuple[str, ...]
    command_methods: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PromptEditorHostFacadeInventory:
    """Classify every current ``PromptEditor`` method for Phase 20 extraction."""

    public_compatibility: tuple[str, ...]
    lifecycle_signal_owner: tuple[str, ...]
    shell_presentation: tuple[str, ...]
    feature_action_presentation: tuple[str, ...]
    external_action_execution: tuple[str, ...]
    command_source_adapter: tuple[str, ...]
    obsolete_internal_bridge: tuple[str, ...]


PROMPT_EDITOR_PUBLIC_WIDGET_SIGNALS = (
    "textChanged",
    "cursorPositionChanged",
    "undoAvailableChanged",
    "redoAvailableChanged",
    "resized",
    "manualScrollHeightChanged",
    "richPromptRenderingEnabledChanged",
    "sceneQueueRequested",
)


PROMPT_EDITOR_PUBLIC_WIDGET_BOUNDARY = PromptEditorPublicWidgetBoundary(
    shell_methods=(
        "lineHeight",
        "minimumEditorHeight",
        "manualScrollHeight",
        "setManualScrollHeight",
        "sizeHint",
        "minimumSizeHint",
        "setPlaceholderText",
        "placeholderText",
        "setReadOnly",
        "setFocus",
        "hasFocus",
    ),
    editing_methods=(
        "toPlainText",
        "setPlainText",
        "setSourceText",
        "replaceBaselineText",
        "replaceBaselineSourceText",
        "textCursor",
        "setTextCursor",
        "copy",
        "cut",
        "paste",
        "selectAll",
        "undo",
        "redo",
        "canUndo",
        "canRedo",
    ),
    projection_methods=(
        "viewport",
        "verticalScrollBar",
        "document",
        "cursorRect",
        "cursorForPosition",
        "source_line_rects",
        "current_source_line_index",
        "set_source_line_chrome_enabled",
        "set_source_line_content_left_inset",
        "set_scene_error_keys",
        "displayMode",
        "setDisplayMode",
        "richPromptRenderingEnabled",
        "setRichPromptRenderingEnabled",
        "source_range_fragments",
        "set_autocomplete_preview_state",
        "set_reorder_preview_state",
        "clear_reorder_preview_state",
        "reorder_preview_fragments",
        "reorder_live_chip_geometry_snapshot",
        "reorder_preview_chip_geometry_snapshot",
        "reorder_live_chip_projection_paint_snapshots",
        "reorder_preview_chip_projection_paint_snapshots",
        "set_reorder_overlay_suppression_snapshots",
        "set_reorder_surface_chrome",
        "reorder_preview_cursor_rect",
        "reorder_base_drag_fragments",
        "reorder_base_drag_chip_geometry_snapshot",
        "reorder_base_drag_cursor_rect",
        "reorder_base_drag_placement_snapshot",
        "reset_reorder_geometry_cache_counters",
        "reorder_geometry_cache_counters",
        "reorder_placement_at_rect",
    ),
    feature_methods=(
        "set_scene_autocomplete_titles",
        "set_queueable_scene_keys",
        "set_search_matches",
        "clear_search_matches",
        "mark_lora_metadata_dirty",
        "refresh_lora_metadata_if_visible",
        "clear_lora_thumbnail_cache",
    ),
    command_methods=(
        "prompt_command_source_identity",
        "execute_autocomplete_acceptance",
        "execute_diagnostic_action",
        "execute_weight_action",
        "execute_reorder_action",
        "execute_source_replacement",
    ),
)


PROMPT_EDITOR_HOST_FACADE_INVENTORY = PromptEditorHostFacadeInventory(
    public_compatibility=(
        "__init__",
        "_autocomplete_panel",
        "_segment_overlay",
        "_token_weight_control_overlay",
        "viewport",
        "verticalScrollBar",
        "document",
        "lineHeight",
        "minimumEditorHeight",
        "manualScrollHeight",
        "setManualScrollHeight",
        "sizeHint",
        "minimumSizeHint",
        "toPlainText",
        "setPlainText",
        "setSourceText",
        "replaceBaselineText",
        "replaceBaselineSourceText",
        "preloadVisibleLoraBanners",
        "canUndo",
        "canRedo",
        "source_line_rects",
        "current_source_line_index",
        "set_source_line_chrome_enabled",
        "set_source_line_content_left_inset",
        "set_scene_error_keys",
        "set_scene_autocomplete_titles",
        "set_queueable_scene_keys",
        "textCursor",
        "setTextCursor",
        "pulse_emphasis_feedback",
        "set_emphasis_adjustment_session",
        "clear_emphasis_adjustment_session",
        "emphasis_adjustment_session",
        "emphasis_adjustment_session_range",
        "emphasis_adjustment_session_matches_range",
        "prompt_weight_wheel_identity",
        "show_transient_neutral_emphasis",
        "clear_transient_neutral_emphasis",
        "clear_overlay_owned_transient_neutral_emphasis",
        "transient_neutral_emphasis_range",
        "transient_neutral_emphasis_owner",
        "set_emphasis_caret_to_content_boundary",
        "cursorRect",
        "has_pending_projection_update",
        "flush_pending_projection_update",
        "commit_lora_autocomplete_replacement",
        "set_autocomplete_preview_state",
        "set_search_matches",
        "clear_search_matches",
        "displayMode",
        "setDisplayMode",
        "richPromptRenderingEnabled",
        "setRichPromptRenderingEnabled",
        "source_range_fragments",
        "set_reorder_preview_state",
        "clear_reorder_preview_state",
        "set_wheel_intent_token_handlers",
        "reorder_preview_fragments",
        "reorder_live_chip_geometry_snapshot",
        "reorder_preview_chip_geometry_snapshot",
        "reorder_live_chip_projection_paint_snapshots",
        "reorder_preview_chip_projection_paint_snapshots",
        "set_reorder_overlay_suppression_snapshots",
        "set_reorder_surface_chrome",
        "reorder_preview_cursor_rect",
        "reorder_base_drag_fragments",
        "reorder_base_drag_chip_geometry_snapshot",
        "reorder_base_drag_cursor_rect",
        "reorder_base_drag_placement_snapshot",
        "reset_reorder_geometry_cache_counters",
        "reorder_geometry_cache_counters",
        "reorder_placement_at_rect",
        "active_syntax_span",
        "cursorForPosition",
        "replace_document_text",
        "replace_document_text_with_prompt_state",
        "copy",
        "selectAll",
        "cut",
        "paste",
        "undo",
        "redo",
        "modify_emphasis",
        "setPlaceholderText",
        "setReadOnly",
        "placeholderText",
        "setFocus",
        "hasFocus",
        "prompt_surface_handle_wheel_scroll",
        "prompt_surface_wheel_event_is_allowed",
        "forward_wheel_event_to_editor_panel",
        "has_lora_spans_for_metadata",
        "refresh_lora_render_metadata_now",
        "mark_lora_metadata_dirty",
        "refresh_lora_metadata_if_visible",
        "clear_lora_thumbnail_cache",
    ),
    lifecycle_signal_owner=(
        "focusInEvent",
        "focusOutEvent",
        "changeEvent",
        "eventFilter",
        "hideEvent",
        "showEvent",
        "keyPressEvent",
        "keyReleaseEvent",
        "_handle_prompt_key_press",
        "_handle_prompt_key_release",
        "focusNextPrevChild",
        "resizeEvent",
        "moveEvent",
        "mouseReleaseEvent",
        "_handle_surface_text_changed",
        "_handle_surface_syntax_action",
        "_handle_surface_mouse_release",
    ),
    shell_presentation=(
        "_allow_surface_wheel_scroll",
        "_handle_viewport_wheel_event",
        "_forward_wheel_event_to_editor_panel",
        "_ancestor_external_wheel_handler",
        "_prompt_menu_requires_custom_actions",
        "_source_position_for_global_pos",
        "_ancestor_editor_panel",
        "_shell_viewport",
        "_content_viewport_for_chrome",
        "_apply_host_placeholder_for_chrome",
        "_surface_for_chrome",
        "_update_backing_fill_for_chrome",
        "_handle_focus_out_for_chrome",
        "_handle_hide_for_chrome",
        "_handle_move_for_chrome",
        "_host_scrollbar_for_scroll_delegate",
        "_surface_for_scroll_delegate",
        "_shell_padding_fill_plane_for_scroll_delegate",
        "_fill_plane_for_scroll_delegate",
        "_token_weight_controls_for_scroll_delegate",
        "_handle_viewport_scroll_for_scroll_delegate",
        "_handle_resize_for_scroll_delegate",
        "_surface_content_height_for_sizing",
        "_surface_is_alive_for_sizing",
        "_update_sizing_fill_planes",
        "_resize_handle_for_sizing",
    ),
    feature_action_presentation=(
        "_handle_clipboard_paste_completed",
        "_refresh_lora_render_metadata_after_catalog_update",
        "_schedule_lora_metadata_catchup_if_needed",
    ),
    external_action_execution=(),
    command_source_adapter=(
        "prompt_command_source_identity",
        "execute_autocomplete_acceptance",
        "execute_diagnostic_action",
        "execute_weight_action",
        "execute_reorder_action",
        "execute_source_replacement",
    ),
    obsolete_internal_bridge=(
        "_refresh_scene_context_identity",
        "_set_context_menu_insert_state_for_tests",
        "_set_context_menu_selection_state_for_tests",
    ),
)


class PromptEditorShell:
    """Own the prompt-editor shell boundary before behavior moves into shell modules."""

    def __init__(self, *, host: QWidget, shell_viewport: QWidget) -> None:
        """Store shell chrome collaborators without changing runtime behavior."""

        self._host = host
        self._shell_viewport = shell_viewport

    @property
    def host(self) -> QWidget:
        """Return the public widget that remains the canonical editor API."""

        return self._host

    @property
    def shell_viewport(self) -> QWidget:
        """Return the QFluent viewport that hosts prompt-editor chrome."""

        return self._shell_viewport

    @property
    def public_widget_boundary(self) -> PromptEditorPublicWidgetBoundary:
        """Return the public methods that must stay on ``PromptEditor``."""

        return PROMPT_EDITOR_PUBLIC_WIDGET_BOUNDARY

    def update_backing_fill(
        self,
        *,
        rect: QRect,
        surface: PromptFillPlaneSurface,
        fill_plane: QWidget,
        shell_padding_fill_plane: QWidget,
    ) -> None:
        """Repaint shell-owned fill layers for one dirty projection viewport rect."""

        update_prompt_fill_backing(
            rect=rect,
            surface=surface,
            shell_viewport=self._shell_viewport,
            fill_plane=fill_plane,
            shell_padding_fill_plane=shell_padding_fill_plane,
        )


__all__ = [
    "PROMPT_EDITOR_PUBLIC_WIDGET_BOUNDARY",
    "PromptEditorPublicWidgetBoundary",
    "PromptEditorShell",
]
