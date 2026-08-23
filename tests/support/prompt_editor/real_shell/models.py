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

"""Describe observable state from production-mounted prompt-editor scenarios."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from substitute.domain.workflow import CubeState
from substitute.presentation.editor.prompt_editor import PromptEditor


@dataclass(frozen=True, slots=True)
class PromptWorkflowHandle:
    """Identify one prompt workflow mounted in the real shell."""

    alias: str
    workflow_id: str
    cube_alias: str
    cube_state: CubeState


@dataclass(frozen=True, slots=True)
class PromptFieldHandle:
    """Identify one real prompt editor field inside a rendered node card."""

    workflow: PromptWorkflowHandle
    node_name: str
    field_key: str
    editor: PromptEditor


@dataclass(frozen=True, slots=True)
class PromptEditorKeyRoute:
    """Record the visible and state route around one real Qt key action."""

    key_name: str
    text: str
    modifiers: str
    focus_before: str
    focus_after: str
    active_window_before: str
    active_window_after: str
    source_before: str
    source_after: str
    cursor_before: int
    cursor_after: int
    dropdown_visible_before: bool
    dropdown_visible_after: bool
    ghost_visible_before: bool
    ghost_visible_after: bool
    inserted_text: str


@dataclass(frozen=True, slots=True)
class PromptEditorTraceAction:
    """Describe one replayable editor action."""

    kind: str
    value: str
    key: int | None = None
    modifiers: int = 0


@dataclass(frozen=True, slots=True)
class PromptEditorTrace:
    """Record a deterministic sequence of user-like prompt editor actions."""

    actions: tuple[PromptEditorTraceAction, ...]
    seed: int | None = None


@dataclass(frozen=True, slots=True)
class PromptEditorObservedEvent:
    """Record one production owner call observed by the harness."""

    index: int
    owner: str
    method: str
    source_before: str
    source_after: str
    cursor_before: int
    cursor_after: int
    preview_before: str
    preview_after: str
    session_before: str
    session_after: str
    panel_before: str
    panel_after: str
    result: str


@dataclass(frozen=True, slots=True)
class PromptSceneProjectionTimelineSample:
    """Record scene projection state after one input or event-loop boundary."""

    label: str
    elapsed_ms: float
    source_text: str
    document_view_source_text: str
    projection_text: str
    scene_titles: tuple[str, ...]
    projection_freshness: str
    projection_has_pending_update: bool
    semantic_refresh_pending: bool
    semantic_refresh_active: bool
    cursor_position: int
    focus_active: bool
    focus_widget_path: str


@dataclass(frozen=True, slots=True)
class PromptProjectionTypingPathProbe:
    """Record projection apply paths selected during one typed text sequence."""

    typed_text: str
    elapsed_ms: float
    canonical_rebuild_count: int
    apply_paths: tuple[str, ...]
    incremental_rejection_reasons: tuple[str, ...]
    layout_rejection_reasons: tuple[str, ...]
    source_text: str
    projection_text: str
    scene_titles: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PromptSourceLineChromeRenderProbe:
    """Capture rendered source-line colors and the layout that supplied them."""

    label: str
    reorder_overlay_active: bool
    projection_preview_active: bool
    line_colors: tuple[tuple[int, tuple[int, int, int, int]], ...]


@dataclass(frozen=True, slots=True)
class PromptReorderRenderedLayoutSnapshot:
    """Capture the active reorder render frame as geometry-comparable facts."""

    label: str
    preview_active: bool
    source_text: str
    projection_text: str
    content_size: tuple[float, float]
    line_rects: tuple[tuple[float, float, float, float], ...]
    fragments: tuple[tuple[str, str, tuple[float, float, float, float]], ...]
    region_divider_lines: tuple[tuple[float, float, float, float], ...]
    region_rail_lines: tuple[tuple[float, float, float, float], ...]
    region_stroke_lines: tuple[tuple[float, float, float, float], ...]


@dataclass(frozen=True, slots=True)
class PromptReorderChipChromeSnapshot:
    """Capture exact paint ownership and border style for one reorder chip."""

    label: str
    segment_index: int
    paint_owners: tuple[str, ...]
    border_colors: tuple[tuple[int, int, int, int], ...]
    animation_override_active: bool
    unsafe_transient: bool


@dataclass(frozen=True, slots=True)
class PromptEditorContextMenuTrace:
    """Record one real-shell context-menu opening and optional action trigger."""

    source_before: str
    source_after: str
    clicked_text: str
    click_source_position: int | None
    menu_rows: tuple[str, ...]
    submenu_rows: tuple[tuple[str, tuple[str, ...]], ...]
    trigger_action_texts: tuple[str, ...]
    trigger_action_full_labels: tuple[str, ...]
    triggered_action_text: str | None
    lora_snapshot_readiness_before: str
    lora_snapshot_unavailable_before: str | None
    lora_snapshot_action_count_before: int
    lora_snapshot_readiness_after: str
    lora_snapshot_unavailable_after: str | None
    lora_snapshot_action_count_after: int
    cached_scheduled_lora_count_before: int | None
    cached_scheduled_lora_count_after: int | None
    event_dispatch_elapsed_ms: float = 0.0
    menu_exec_elapsed_ms: float = 0.0
    menu_population_elapsed_ms: float = 0.0
    captured_menu_row_count: int = 0
    captured_submenu_row_count: int = 0
    captured_action_count: int = 0


@dataclass(frozen=True, slots=True)
class PromptInlineLoraMenuProbe:
    """Capture one production inline-LoRA token menu presentation."""

    menu_rows: tuple[str, ...]
    trigger_action_texts: tuple[str, ...]
    trigger_action_full_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PromptSegmentScopeProbe:
    """Capture every owner boundary feeding the save-segment dialog."""

    candidate_kind: str | None
    candidate_value: str | None
    active_snapshot_readiness: str
    active_snapshot_reason: str | None
    active_snapshot_item_value: str | None
    active_snapshot_family_labels: tuple[str, ...]
    editor_snapshot_readiness: str
    editor_snapshot_reason: str | None
    editor_scope_titles: tuple[str, ...]
    editor_scope_full_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PromptSegmentDialogProbe:
    """Capture the exact scope payload passed to the production dialog runner."""

    title: str
    selected_text: str
    scope_titles: tuple[str, ...]
    scope_full_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PromptEditorVisibleLayoutRow:
    """Record one visible projection row in viewport coordinates."""

    row_index: int
    source_start: int
    source_end: int
    document_top: float
    viewport_top: float
    height: float
    text: str
    has_inline_object: bool = False
    is_structural: bool = False
    expected_height: float | None = None
    expected_text_baseline: float | None = None


@dataclass(frozen=True, slots=True)
class PromptEditorVisibleTextFragment:
    """Record one visible projection text fragment in viewport coordinates."""

    fragment_index: int
    source_start: int
    source_end: int
    document_rect: tuple[float, float, float, float]
    viewport_rect: tuple[float, float, float, float]
    document_baseline: float
    viewport_baseline: float
    text: str
    expected_document_baseline: float | None = None
    expected_viewport_baseline: float | None = None
    expected_height: float | None = None


@dataclass(frozen=True, slots=True)
class PromptEditorStateSnapshot:
    """Capture prompt editor geometry plus code-level diagnostic owner state."""

    label: str
    source_text: str
    selected_text: str
    selected_source_text: str
    selection_range: tuple[int, int]
    selection_rects: tuple[tuple[float, float, float, float], ...]
    cursor_position: int
    display_mode: str
    focus_widget_path: str
    active_window_path: str
    target_event_widget_path: str
    geometries: Mapping[str, tuple[int, int, int, int] | None]
    global_geometries: Mapping[str, tuple[int, int, int, int] | None]
    scroll_values: Mapping[str, int]
    device_pixel_ratio: float
    autocomplete_gateway_calls: tuple[tuple[str, int], ...]
    popup_widget_exists: bool
    popup_state_visible: bool
    popup_visual_visible: bool
    popup_global_rect: tuple[int, int, int, int] | None
    ghost_visual_visible: bool
    expected_ghost_suffix: str
    autocomplete_preview_active: bool
    autocomplete_preview_suffix: str
    autocomplete_preview_source_position: int | None
    autocomplete_session_lifecycle: str
    autocomplete_session_mode: str
    autocomplete_session_selected_index: int
    autocomplete_session_prefix: str
    autocomplete_session_word_start: int | None
    autocomplete_session_word_end: int | None
    autocomplete_session_active_tag_end: int | None
    autocomplete_session_suggestions: tuple[str, ...]
    autocomplete_has_active_session: bool
    autocomplete_presenter_panel_visible: bool
    autocomplete_presenter_panel_under_mouse: bool
    autocomplete_source_revision: int | None
    autocomplete_snapshot_source_length: int | None
    autocomplete_snapshot_cursor_position: int | None
    source_revision: int | None
    semantic_source_revision: int | None
    semantic_revision: int | None
    projection_semantic_revision: int | None
    projection_revision: int | None
    layout_revision: int | None
    viewport_revision: int | None
    paint_revision: int | None
    semantic_is_current: bool
    projection_is_current: bool
    layout_is_current: bool
    paint_is_current: bool
    editing_session_source_revision: int | None
    editing_session_cursor_position: int | None
    editing_session_anchor_position: int | None
    document_view_source_text: str
    document_view_region_separator_count: int
    projection_document_source_text: str
    projection_region_separator_count: int
    projection_region_separator_ranges: tuple[tuple[int, int], ...]
    caret_inside_region_separator: bool
    anchor_inside_region_separator: bool
    region_chrome_divider_count: int
    region_chrome_rail_count: int
    region_chrome_prepare_count: int
    region_chrome_visited_line_count: int
    active_projection_source_text: str
    layout_projection_source_text: str
    projection_text: str
    active_projection_text: str
    layout_projection_text: str
    active_projection_layout_required: bool
    layout_uses_projection_document: bool
    layout_uses_active_projection_document: bool
    paint_cache_key_present: bool
    last_content_paint_result: str
    last_content_paint_frame_is_current: bool
    paint_cache_identity_matches_render_frame: bool
    paint_cache_source_revision: int | None
    paint_cache_projection_document_identity_matches_layout: bool
    paint_cache_layout_snapshot_identity_matches_layout: bool
    paint_cache_ghosted_run_ids: tuple[str, ...]
    autocomplete_ghost_paint_visible_by_owner_state: bool
    projection_freshness: str
    projection_has_pending_update: bool
    projection_has_stale_geometry: bool
    caret_state_source_position: int | None
    anchor_state_source_position: int | None
    caret_state_placement: str
    anchor_state_placement: str
    caret_map_source_length: int | None
    caret_map_stop_count: int | None
    caret_preferred_x: float | None
    caret_rect_override: tuple[float, float, float, float] | None
    skip_next_same_source_soft_wrap_move: bool
    projection_token_count: int
    projection_run_count: int
    layout_line_count: int
    layout_text_fragment_count: int
    layout_inline_object_fragment_count: int
    layout_content_width: float
    layout_content_height: float
    layout_text_width: float
    projection_metrics_text_line_height: float | None
    projection_metrics_ascent: float | None
    projection_metrics_descent: float | None
    projection_metrics_document_margin: float | None
    projection_metrics_content_left_inset: float | None
    projection_metrics_content_height: float | None
    shell_natural_height: int | None
    shell_effective_height: int | None
    shell_minimum_editor_height: int | None
    shell_outer_vertical_padding: int | None
    shell_document_vertical_padding: int | None
    visible_layout_rows: tuple[PromptEditorVisibleLayoutRow, ...]
    visible_text_fragments: tuple[PromptEditorVisibleTextFragment, ...]
    caret_token_id: str | None
    anchor_token_id: str | None
    caret_token_id_resolves: bool
    anchor_token_id_resolves: bool
    caret_rect: tuple[float, float, float, float] | None
    viewport_rect: tuple[int, int, int, int]
    caret_rect_finite: bool
    caret_rect_has_area: bool
    caret_rect_intersects_viewport: bool
    vertical_scroll_minimum: int
    vertical_scroll_maximum: int
    vertical_scroll_page_step: int
    horizontal_scroll_minimum: int
    horizontal_scroll_maximum: int
    horizontal_scroll_page_step: int
    transient_caret_geometry_present: bool
    transient_caret_geometry_valid: bool
    transient_insertion_overlay_present: bool
    transient_insertion_overlay_valid: bool
    transient_insertion_overlay_source_range: tuple[int, int] | None
    transient_insertion_overlay_viewport_rect: tuple[float, float, float, float] | None
    transient_insertion_overlay_repaint_rect: tuple[float, float, float, float] | None
    transient_deletion_overlay_present: bool
    transient_deletion_overlay_valid: bool
    transient_deletion_overlay_source_range: tuple[int, int] | None
    transient_deletion_overlay_viewport_rects: tuple[
        tuple[float, float, float, float], ...
    ]
    transient_deletion_overlay_erase_rects: tuple[
        tuple[float, float, float, float], ...
    ]
    transient_deletion_overlay_repaint_rect: tuple[float, float, float, float] | None
    undo_available: bool
    redo_available: bool
    undo_depth: int
    redo_depth: int
    undo_max_depth: int
    redo_max_depth: int
    undo_edit_block_depth: int
    undo_pending_state_present: bool
    undo_typing_group_active: bool
    undo_typing_group_last_cursor_position: int | None
    undo_delete_group_active: bool
    undo_delete_group_key: int | None
    observed_event_start_index: int
    observed_event_end_index: int
    recent_observed_events: tuple[PromptEditorObservedEvent, ...]


@dataclass(frozen=True, slots=True)
class PromptEditorAbuseFinding:
    """Record one visible-symptom failure from a seeded abuse campaign."""

    symptom: str
    owner_hypothesis: str
    action_index: int
    source_before: str
    source_after: str
    artifact_path: str


@dataclass(frozen=True, slots=True)
class PromptEditorAbuseReport:
    """Summarize one seeded real-shell prompt editor abuse campaign."""

    seed: int
    sizes: tuple[tuple[int, int], ...]
    action_count: int
    findings: tuple[PromptEditorAbuseFinding, ...]
    suspicious_successes: tuple[str, ...]
    grouped_failures: Mapping[str, tuple[str, ...]]
    report_path: Path
