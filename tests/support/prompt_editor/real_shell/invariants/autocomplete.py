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

"""Validate autocomplete ownership, session state, and popup geometry."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.support.prompt_editor.real_shell.models import PromptEditorStateSnapshot


def preview_violations(snapshot: PromptEditorStateSnapshot) -> tuple[str, ...]:
    """Return invariant violations for projection-owned autocomplete preview."""

    violations: list[str] = []
    source_position = snapshot.autocomplete_preview_source_position
    if source_position is None:
        violations.append("autocomplete_preview_missing_source_position")
        return tuple(violations)
    if not 0 <= source_position <= len(snapshot.source_text):
        violations.append(
            "autocomplete_preview_source_position_out_of_bounds:"
            f"{source_position}:{len(snapshot.source_text)}"
        )
    if source_position != snapshot.cursor_position:
        violations.append(
            "autocomplete_preview_not_at_cursor:"
            f"{source_position}:{snapshot.cursor_position}"
        )
    if source_prefix_ends_with_delimiter(snapshot.source_text, source_position):
        violations.append("autocomplete_preview_after_source_delimiter")
    if not snapshot.autocomplete_has_active_session:
        violations.append("autocomplete_preview_without_active_session")
    if not snapshot.autocomplete_presenter_panel_visible:
        violations.append("autocomplete_preview_without_presenter_panel")
    if not snapshot.popup_state_visible:
        violations.append("autocomplete_preview_without_visible_popup_widget")
    if not snapshot.autocomplete_preview_suffix:
        violations.append("autocomplete_preview_empty_suffix")
    return tuple(violations)


def session_violations(snapshot: PromptEditorStateSnapshot) -> tuple[str, ...]:
    """Return invariant violations for autocomplete lifecycle/session state."""

    violations: list[str] = []
    suggestion_count = len(snapshot.autocomplete_session_suggestions)
    if snapshot.autocomplete_session_lifecycle not in {"active", "refreshing"}:
        violations.append(
            "autocomplete_active_session_invalid_lifecycle:"
            f"{snapshot.autocomplete_session_lifecycle}"
        )
    if snapshot.autocomplete_session_mode not in {"tag", "scene", "wildcard", "lora"}:
        violations.append(
            "autocomplete_active_session_invalid_mode:"
            f"{snapshot.autocomplete_session_mode}"
        )
    if snapshot.autocomplete_session_mode != "lora" and suggestion_count <= 0:
        violations.append("autocomplete_active_session_without_suggestions")
    if snapshot.autocomplete_session_mode != "lora" and not (
        0 <= snapshot.autocomplete_session_selected_index < suggestion_count
    ):
        violations.append(
            "autocomplete_selected_index_out_of_bounds:"
            f"{snapshot.autocomplete_session_selected_index}:{suggestion_count}"
        )
    if snapshot.autocomplete_session_mode in {"tag", "scene", "wildcard"}:
        _append_word_range_violations(snapshot, violations)
    active_tag_end = snapshot.autocomplete_session_active_tag_end
    if active_tag_end is not None and not 0 <= active_tag_end <= len(
        snapshot.source_text
    ):
        violations.append(
            "autocomplete_session_active_tag_end_out_of_bounds:"
            f"{active_tag_end}:{len(snapshot.source_text)}"
        )
    return tuple(violations)


def popup_geometry_violations(snapshot: PromptEditorStateSnapshot) -> tuple[str, ...]:
    """Return invariant violations for autocomplete popup geometry."""

    violations: list[str] = []
    popup_rect = snapshot.popup_global_rect
    viewport_rect = snapshot.global_geometries.get("viewport")
    if popup_rect is None:
        violations.append("visible_popup_missing_global_rect")
        return tuple(violations)
    if not integer_rect_has_area(popup_rect):
        violations.append(f"visible_popup_global_rect_invalid:{popup_rect}")
    if viewport_rect is None:
        violations.append("visible_popup_missing_viewport_global_rect")
        return tuple(violations)
    if not integer_rect_has_area(viewport_rect):
        violations.append(f"visible_popup_viewport_global_rect_invalid:{viewport_rect}")
    if not popup_rect_is_anchored_to_viewport(
        popup_rect=popup_rect,
        viewport_rect=viewport_rect,
    ):
        violations.append(
            f"visible_popup_not_anchored_to_editor:{popup_rect}:{viewport_rect}"
        )
    return tuple(violations)


def dismissal_owner_violations(
    *,
    before: PromptEditorStateSnapshot,
    after: PromptEditorStateSnapshot,
    action_name: str,
) -> tuple[str, ...]:
    """Return missing owner-path evidence for autocomplete preview dismissal."""

    transition_events = tuple(
        event
        for event in after.recent_observed_events
        if before.observed_event_end_index
        <= event.index
        < after.observed_event_end_index
    )
    violations: list[str] = []
    preview_owner_clear = any(
        event.owner == "autocomplete preview projection owner"
        and event.method == "set_preview_state"
        and event.preview_before != "<none>"
        and event.preview_after == "<none>"
        for event in transition_events
    )
    if not preview_owner_clear:
        violations.append(f"{action_name}_dismissal_without_preview_owner_clear")
    paint_invalidation = any(
        event.owner == "projection source and caret owner"
        and event.method == "invalidate_autocomplete_preview_paint"
        for event in transition_events
    )
    if not paint_invalidation:
        violations.append(f"{action_name}_dismissal_without_preview_paint_invalidation")
    if action_name == "caret" and not any(
        event.owner == "caret autocomplete preview coordinator"
        and event.method == "reconcile_after_caret_state_change"
        for event in transition_events
    ):
        violations.append("caret_dismissal_without_preview_reconciliation_owner")
    return tuple(violations)


def stale_observation(snapshot: PromptEditorStateSnapshot) -> str:
    """Describe autocomplete state in a dismissal failure artifact."""

    return (
        f"preview_active={snapshot.autocomplete_preview_active}, "
        f"preview_suffix={snapshot.autocomplete_preview_suffix!r}, "
        f"active_session={snapshot.autocomplete_has_active_session}, "
        "presenter_panel_visible="
        f"{snapshot.autocomplete_presenter_panel_visible}, "
        f"source={snapshot.source_text!r}, "
        f"projection={snapshot.projection_text!r}, "
        f"active_projection={snapshot.active_projection_text!r}, "
        f"layout_projection={snapshot.layout_projection_text!r}, "
        "layout_uses_projection_document="
        f"{snapshot.layout_uses_projection_document}, "
        f"paint_cache_key_present={snapshot.paint_cache_key_present}, "
        "paint_cache_ghosted_run_ids="
        f"{snapshot.paint_cache_ghosted_run_ids}"
    )


def _append_word_range_violations(
    snapshot: PromptEditorStateSnapshot,
    violations: list[str],
) -> None:
    """Validate source range ownership for tag, scene, and wildcard sessions."""

    word_start = snapshot.autocomplete_session_word_start
    word_end = snapshot.autocomplete_session_word_end
    if word_start is None or word_end is None:
        violations.append("autocomplete_session_missing_word_range")
    elif not 0 <= word_start <= word_end <= len(snapshot.source_text):
        violations.append(
            "autocomplete_session_word_range_out_of_bounds:"
            f"{word_start}:{word_end}:{len(snapshot.source_text)}"
        )
    elif word_end != snapshot.cursor_position:
        violations.append(
            "autocomplete_session_word_end_not_at_cursor:"
            f"{word_end}:{snapshot.cursor_position}"
        )


def source_prefix_ends_with_delimiter(source_text: str, source_position: int) -> bool:
    """Return whether a preview starts after a hard tag-query delimiter."""

    return source_position > 0 and source_text[source_position - 1] in ",\r\n"


def integer_rect_has_area(rect: tuple[int, int, int, int]) -> bool:
    """Return whether one serialized integer rect has positive area."""

    return rect[2] > 0 and rect[3] > 0


def popup_rect_is_anchored_to_viewport(
    *,
    popup_rect: tuple[int, int, int, int],
    viewport_rect: tuple[int, int, int, int],
) -> bool:
    """Return whether a popup remains plausibly anchored to its editor viewport."""

    popup_x, popup_y, popup_width, popup_height = popup_rect
    viewport_x, viewport_y, viewport_width, viewport_height = viewport_rect
    popup_right = popup_x + popup_width
    viewport_right = viewport_x + viewport_width
    return (
        popup_right >= viewport_x - 64
        and popup_x <= viewport_right + 64
        and popup_y >= viewport_y - 512
        and popup_y <= viewport_y + viewport_height + 512
        and popup_height <= max(viewport_height, 1) + 512
    )
