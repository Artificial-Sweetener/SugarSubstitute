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

"""Enforce bounded prompt-editor owner work independently of wall-clock load."""

from __future__ import annotations

from collections.abc import Mapping

from .models import PromptAbuseActionOwnerDelta

_DIRECT_REORDER_MOVE_COUNTERS = frozenset(
    {
        "autoscroll_pointer_update_count",
        "drag_move_count",
        "drop_target_changed_count",
        "drop_target_no_change_count",
        "instrumented_reorder_preview_request_count",
        "max_drag_move_ms",
        "preview_scheduler_request_count",
        "target_change_count",
    }
)
_QUEUED_REORDER_LIMITS: Mapping[str, float] = {
    "animation_plan_applied_count": 1.0,
    "animation_plan_build_count": 1.0,
    "preview_geometry_full_count": 1.0,
    "preview_projection_full_layout_count": 1.0,
    "preview_projection_incremental_layout_count": 2.0,
    "preview_scheduler_run_count": 1.0,
    "projection_snapshot_rebuild_count": 2.0,
}
_FORBIDDEN_POINTER_COUNTERS = frozenset(
    {
        "autoscroll_invalidation_count",
        "drag_proxy_render_state_invalidation_count",
        "drag_proxy_render_state_rebuild_count",
        "pointer_base_cache_miss_count",
        "pointer_full_refresh_count",
        "pointer_paint_request_count",
        "pointer_preview_rebuild_count",
        "pointer_unexpected_work_count",
        "preview_geometry_full_count",
        "preview_scheduler_run_count",
        "projection_snapshot_rebuild_count",
    }
)
_CANVAS_FORBIDDEN_COUNTERS = frozenset(
    {
        "instrumented_document_view_build_count",
        "instrumented_editing_paste_count",
        "instrumented_editing_replace_range_count",
        "instrumented_editing_replace_full_source_count",
        "instrumented_layout_snapshot_count",
        "instrumented_projection_document_build_count",
        "instrumented_projection_rebuild_count",
        "instrumented_surface_source_apply_count",
        "instrumented_syntax_render_plan_build_count",
        "region_chrome_prepare_count",
    }
)
_PASSIVE_FORBIDDEN_COUNTERS = frozenset(
    {
        "instrumented_diagnostic_cache_clear_count",
        "instrumented_document_view_build_count",
        "instrumented_editing_paste_count",
        "instrumented_editing_replace_full_source_count",
        "instrumented_editing_replace_range_count",
        "instrumented_layout_snapshot_count",
        "instrumented_projection_document_build_count",
        "instrumented_projection_rebuild_count",
        "instrumented_surface_source_apply_count",
        "instrumented_syntax_render_plan_build_count",
        "region_chrome_prepare_count",
    }
)
_EDIT_LIMITS: Mapping[str, float] = {
    "instrumented_document_view_build_count": 1.0,
    "instrumented_editing_replace_range_count": 1.0,
    "instrumented_layout_snapshot_count": 1.0,
    "instrumented_projection_rebuild_count": 1.0,
    "instrumented_surface_source_apply_count": 1.0,
    "instrumented_syntax_render_plan_build_count": 1.0,
    "region_chrome_prepare_count": 1.0,
}
_DANBOORU_IMPORT_EDIT_LIMITS: Mapping[str, float] = {
    "instrumented_danbooru_import_apply_count": 1.0,
    "instrumented_document_view_build_count": 2.0,
    "instrumented_editing_replace_range_count": 2.0,
    "instrumented_layout_snapshot_count": 2.0,
    "instrumented_projection_document_build_count": 2.0,
    "instrumented_projection_rebuild_count": 2.0,
    "instrumented_surface_source_apply_count": 2.0,
    "instrumented_syntax_render_plan_build_count": 2.0,
    "region_chrome_prepare_count": 2.0,
}
_EDIT_APPLIED_PATH_COUNTERS = frozenset(
    {
        "instrumented_projection_fast_delete_applied_count",
        "instrumented_projection_fast_insert_applied_count",
        "instrumented_projection_fast_newline_applied_count",
        "instrumented_projection_incremental_applied_count",
        "instrumented_projection_incremental_deferred_count",
    }
)
_QUEUED_CORE_LIMITS: Mapping[str, float] = {
    "instrumented_document_view_build_count": 1.0,
    "instrumented_layout_snapshot_count": 1.0,
    "instrumented_projection_document_build_count": 1.0,
    "instrumented_projection_rebuild_count": 1.0,
    "instrumented_syntax_render_plan_build_count": 1.0,
    "region_chrome_prepare_count": 1.0,
}
_QUEUED_AUTOCOMPLETE_CORE_LIMITS: Mapping[str, float] = {
    "instrumented_autocomplete_preview_update_count": 1.0,
    "instrumented_document_view_build_count": 1.0,
    "instrumented_layout_snapshot_count": 2.0,
    "instrumented_projection_document_build_count": 2.0,
    "instrumented_projection_rebuild_count": 1.0,
    "instrumented_syntax_render_plan_build_count": 1.0,
    "region_chrome_prepare_count": 1.0,
}
_QUEUED_REORDER_CORE_LIMITS: Mapping[str, float] = {
    "instrumented_document_view_build_count": 2.0,
    "instrumented_layout_snapshot_count": 4.0,
    "instrumented_projection_document_build_count": 2.0,
    "instrumented_projection_rebuild_count": 1.0,
    "instrumented_reorder_preview_run_count": 1.0,
    "instrumented_syntax_render_plan_build_count": 2.0,
    "region_chrome_prepare_count": 2.0,
}
_PASSIVE_AUTOCOMPLETE_LIMITS: Mapping[str, float] = {
    "instrumented_autocomplete_preview_update_count": 1.0,
    "instrumented_layout_snapshot_count": 1.0,
    "instrumented_projection_document_build_count": 1.0,
}
_PASSIVE_AUTOCOMPLETE_ALLOWED_COUNTERS = frozenset(
    {
        "instrumented_layout_snapshot_count",
        "instrumented_projection_document_build_count",
    }
)
_PASSIVE_DIAGNOSTIC_PUBLISH_LIMITS: Mapping[str, float] = {
    "instrumented_diagnostic_cache_clear_count": 1.0,
    "instrumented_diagnostics_visible_publish_count": 1.0,
}
_PASSIVE_DIAGNOSTIC_PUBLISH_ALLOWED_COUNTERS = frozenset(
    _PASSIVE_DIAGNOSTIC_PUBLISH_LIMITS
)
_PASSIVE_DEFERRED_FLUSH_LIMITS: Mapping[str, float] = {
    "instrumented_diagnostic_cache_clear_count": 1.0,
    "instrumented_document_view_build_count": 1.0,
    "instrumented_layout_snapshot_count": 1.0,
    "instrumented_projection_document_build_count": 1.0,
    "instrumented_projection_pending_flush_applied_count": 1.0,
    "instrumented_projection_rebuild_count": 1.0,
    "instrumented_syntax_render_plan_build_count": 1.0,
    "region_chrome_prepare_count": 1.0,
}
_PASSIVE_DEFERRED_FLUSH_ALLOWED_COUNTERS = frozenset(_PASSIVE_DEFERRED_FLUSH_LIMITS)
_RESIZE_LIMITS: Mapping[str, float] = {
    "instrumented_layout_snapshot_count": 1.0,
    "instrumented_surface_resize_event_count": 1.0,
    "region_chrome_prepare_count": 1.0,
}
_RESIZE_FORBIDDEN_COUNTERS = frozenset(
    {
        "instrumented_document_view_build_count",
        "instrumented_editing_paste_count",
        "instrumented_editing_replace_full_source_count",
        "instrumented_editing_replace_range_count",
        "instrumented_projection_document_build_count",
        "instrumented_projection_rebuild_count",
        "instrumented_surface_source_apply_count",
        "instrumented_syntax_render_plan_build_count",
    }
)
_WORKFLOW_ROUND_TRIP_LIMITS: Mapping[str, float] = {
    "instrumented_document_view_build_count": 2.0,
    "instrumented_editing_replace_full_source_count": 1.0,
    "instrumented_layout_snapshot_count": 6.0,
    "instrumented_projection_document_build_count": 4.0,
    "instrumented_projection_rebuild_count": 2.0,
    "instrumented_syntax_render_plan_build_count": 2.0,
}
_DISPLAY_MODE_LIMITS: Mapping[str, float] = {
    "instrumented_document_view_build_count": 1.0,
    "instrumented_layout_snapshot_count": 1.0,
    "instrumented_projection_document_build_count": 1.0,
    "instrumented_projection_rebuild_count": 1.0,
    "instrumented_syntax_render_plan_build_count": 1.0,
    "region_chrome_prepare_count": 1.0,
}


def prompt_abuse_structural_violations(
    action_owner_deltas: tuple[PromptAbuseActionOwnerDelta, ...],
) -> tuple[str, ...]:
    """Return actionable violations of operation-local owner-work budgets."""

    violations: list[str] = []
    for delta in action_owner_deltas:
        action_kind = delta.label.partition(":")[0]
        counters = dict(delta.counter_deltas)
        if action_kind == "reorder_drag_move":
            violations.extend(_direct_reorder_move_violations(delta, counters))
        elif action_kind in {"event_turn", "drain_events"}:
            violations.extend(_queued_reorder_work_violations(delta, counters))
            violations.extend(
                _counter_limit_violations(
                    delta,
                    counters,
                    _queued_core_limits(counters),
                )
            )
        elif action_kind == "canvas_round_trip":
            violations.extend(
                _forbidden_counter_violations(
                    delta,
                    counters,
                    _CANVAS_FORBIDDEN_COUNTERS,
                )
            )
        elif action_kind == "workflow_round_trip":
            violations.extend(
                _counter_limit_violations(
                    delta,
                    counters,
                    _WORKFLOW_ROUND_TRIP_LIMITS,
                )
            )
        elif action_kind == "resize":
            violations.extend(
                _forbidden_counter_violations(
                    delta,
                    counters,
                    _RESIZE_FORBIDDEN_COUNTERS,
                )
            )
            violations.extend(
                _counter_limit_violations(delta, counters, _RESIZE_LIMITS)
            )
        elif action_kind == "display_mode":
            violations.extend(
                _counter_limit_violations(delta, counters, _DISPLAY_MODE_LIMITS)
            )
        elif _is_passive_editor_action(delta.label):
            if counters.get(
                "instrumented_projection_pending_flush_applied_count",
                0.0,
            ):
                violations.extend(
                    _forbidden_counter_violations(
                        delta,
                        counters,
                        (
                            _PASSIVE_FORBIDDEN_COUNTERS
                            - _PASSIVE_DEFERRED_FLUSH_ALLOWED_COUNTERS
                        ),
                    )
                )
                violations.extend(
                    _counter_limit_violations(
                        delta,
                        counters,
                        _PASSIVE_DEFERRED_FLUSH_LIMITS,
                    )
                )
            elif counters.get(
                "instrumented_autocomplete_preview_update_count",
                0.0,
            ):
                violations.extend(
                    _forbidden_counter_violations(
                        delta,
                        counters,
                        (
                            _PASSIVE_FORBIDDEN_COUNTERS
                            - _PASSIVE_AUTOCOMPLETE_ALLOWED_COUNTERS
                        ),
                    )
                )
                violations.extend(
                    _counter_limit_violations(
                        delta,
                        counters,
                        _PASSIVE_AUTOCOMPLETE_LIMITS,
                    )
                )
            elif counters.get(
                "instrumented_diagnostics_visible_publish_count",
                0.0,
            ):
                violations.extend(
                    _forbidden_counter_violations(
                        delta,
                        counters,
                        (
                            _PASSIVE_FORBIDDEN_COUNTERS
                            - _PASSIVE_DIAGNOSTIC_PUBLISH_ALLOWED_COUNTERS
                        ),
                    )
                )
                violations.extend(
                    _counter_limit_violations(
                        delta,
                        counters,
                        _PASSIVE_DIAGNOSTIC_PUBLISH_LIMITS,
                    )
                )
            else:
                violations.extend(
                    _forbidden_counter_violations(
                        delta,
                        counters,
                        _PASSIVE_FORBIDDEN_COUNTERS,
                    )
                )
        if _is_edit_action(delta.label):
            violations.extend(_edit_action_violations(delta, counters))
    return tuple(dict.fromkeys(violations))


def _is_navigation_key(label: str) -> bool:
    """Return whether one measured key action is caret-only navigation."""

    return any(
        label.startswith(f"key:'{key_name}'")
        for key_name in (
            "left",
            "right",
            "up",
            "down",
            "home",
            "end",
            "shift_left",
            "shift_right",
            "shift_up",
            "shift_down",
            "shift_home",
            "shift_end",
            "copy",
            "select_all",
        )
    )


def _is_passive_editor_action(label: str) -> bool:
    """Return whether one action must not change source or rebuild editor state."""

    action_kind = label.partition(":")[0]
    return action_kind in {
        "mouse_caret",
        "mouse_drag_selection",
        "move_cursor",
        "request_paint",
        "scroll",
        "select",
    } or _is_navigation_key(label)


def _is_edit_action(label: str) -> bool:
    """Return whether one action may perform one bounded source edit."""

    action_kind = label.partition(":")[0]
    return action_kind in {"paste", "type"} or any(
        label.startswith(f"key:'{key_name}'")
        for key_name in ("backspace", "cut", "delete", "enter")
    )


def _edit_action_violations(
    delta: PromptAbuseActionOwnerDelta,
    counters: Mapping[str, float],
) -> tuple[str, ...]:
    """Require one user edit to remain single-source and single-strategy work."""

    danbooru_import_count = counters.get(
        "instrumented_danbooru_import_apply_count",
        0.0,
    )
    limits = _DANBOORU_IMPORT_EDIT_LIMITS if danbooru_import_count else _EDIT_LIMITS
    violations = list(_counter_limit_violations(delta, counters, limits))
    if not danbooru_import_count:
        canonical_document_count = counters.get(
            "instrumented_document_view_build_count",
            0.0,
        )
        violations.extend(
            _maximum_counter_violations(
                delta,
                counters,
                counter_name="instrumented_projection_document_build_count",
                maximum=min(2.0, canonical_document_count + 1.0),
            )
        )
    violations.extend(
        _maximum_counter_violations(
            delta,
            counters,
            counter_name="instrumented_editing_replace_full_source_count",
            maximum=0.0,
        )
    )
    if delta.label.partition(":")[0] == "paste":
        violations.extend(
            _maximum_counter_violations(
                delta,
                counters,
                counter_name="instrumented_editing_paste_count",
                maximum=1.0,
            )
        )
    applied_path_count = sum(
        counters.get(counter_name, 0.0) for counter_name in _EDIT_APPLIED_PATH_COUNTERS
    )
    if applied_path_count > 1.0:
        violations.append(
            _violation(
                delta,
                "projection_applied_path_count",
                expected="<=1",
                actual=applied_path_count,
            )
        )
    return tuple(violations)


def _queued_core_limits(counters: Mapping[str, float]) -> Mapping[str, float]:
    """Return the core budget matching one explicit queued-work owner."""

    if counters.get("instrumented_reorder_preview_run_count", 0.0):
        return _QUEUED_REORDER_CORE_LIMITS
    if counters.get("instrumented_autocomplete_preview_update_count", 0.0):
        return _QUEUED_AUTOCOMPLETE_CORE_LIMITS
    return _QUEUED_CORE_LIMITS


def _counter_limit_violations(
    delta: PromptAbuseActionOwnerDelta,
    counters: Mapping[str, float],
    limits: Mapping[str, float],
) -> tuple[str, ...]:
    """Return violations for one named set of maximum owner-work budgets."""

    violations: list[str] = []
    for counter_name, maximum in limits.items():
        violations.extend(
            _maximum_counter_violations(
                delta,
                counters,
                counter_name=counter_name,
                maximum=maximum,
            )
        )
    return tuple(violations)


def _forbidden_counter_violations(
    delta: PromptAbuseActionOwnerDelta,
    counters: Mapping[str, float],
    forbidden_counters: frozenset[str],
) -> tuple[str, ...]:
    """Return violations for counters forbidden on one operation path."""

    return tuple(
        _violation(delta, counter_name, expected="0", actual=actual)
        for counter_name in sorted(forbidden_counters)
        if (actual := counters.get(counter_name, 0.0)) != 0.0
    )


def _direct_reorder_move_violations(
    delta: PromptAbuseActionOwnerDelta,
    counters: Mapping[str, float],
) -> tuple[str, ...]:
    """Require one pointer move to remain geometry-only and single-pass."""

    violations: list[str] = []
    violations.extend(
        _exact_counter_violations(
            delta,
            counters,
            counter_name="drag_move_count",
            expected=1.0,
        )
    )
    violations.extend(
        _maximum_counter_violations(
            delta,
            counters,
            counter_name="autoscroll_pointer_update_count",
            maximum=1.0,
        )
    )
    instrumented_preview_requests = counters.get(
        "instrumented_reorder_preview_request_count"
    )
    if instrumented_preview_requests is not None:
        preview_requests = counters.get("preview_scheduler_request_count", 0.0)
        if instrumented_preview_requests != preview_requests:
            violations.append(
                _violation(
                    delta,
                    "instrumented_reorder_preview_request_count",
                    expected=_format_number(preview_requests),
                    actual=instrumented_preview_requests,
                )
            )
    changed = counters.get("drop_target_changed_count", 0.0)
    unchanged = counters.get("drop_target_no_change_count", 0.0)
    if changed + unchanged != 1.0:
        violations.append(
            _violation(
                delta,
                "drop_target_decision_count",
                expected="1",
                actual=changed + unchanged,
            )
        )
    violations.extend(
        _maximum_counter_violations(
            delta,
            counters,
            counter_name="preview_scheduler_request_count",
            maximum=1.0,
        )
    )
    violations.extend(
        _maximum_counter_violations(
            delta,
            counters,
            counter_name="target_change_count",
            maximum=1.0,
        )
    )
    target_changes = counters.get("target_change_count", 0.0)
    if target_changes != changed:
        violations.append(
            _violation(
                delta,
                "target_change_count",
                expected=_format_number(changed),
                actual=target_changes,
            )
        )
    for counter_name in sorted(_FORBIDDEN_POINTER_COUNTERS):
        actual = counters.get(counter_name, 0.0)
        if actual != 0.0:
            violations.append(
                _violation(delta, counter_name, expected="0", actual=actual)
            )
    for counter_name, actual in sorted(counters.items()):
        if (
            actual == 0.0
            or counter_name in _DIRECT_REORDER_MOVE_COUNTERS
            or counter_name in _FORBIDDEN_POINTER_COUNTERS
        ):
            continue
        violations.append(
            _violation(
                delta,
                f"unexpected_counter:{counter_name}",
                expected="0",
                actual=actual,
            )
        )
    return tuple(violations)


def _queued_reorder_work_violations(
    delta: PromptAbuseActionOwnerDelta,
    counters: Mapping[str, float],
) -> tuple[str, ...]:
    """Require one queued turn to publish at most one coalesced preview unit."""

    if not any(counter_name in counters for counter_name in _QUEUED_REORDER_LIMITS):
        return ()
    violations: list[str] = []
    for counter_name, maximum in _QUEUED_REORDER_LIMITS.items():
        violations.extend(
            _maximum_counter_violations(
                delta,
                counters,
                counter_name=counter_name,
                maximum=maximum,
            )
        )
    for counter_name in sorted(_FORBIDDEN_POINTER_COUNTERS):
        if not counter_name.startswith("pointer_"):
            continue
        actual = counters.get(counter_name, 0.0)
        if actual != 0.0:
            violations.append(
                _violation(delta, counter_name, expected="0", actual=actual)
            )
    return tuple(violations)


def _exact_counter_violations(
    delta: PromptAbuseActionOwnerDelta,
    counters: Mapping[str, float],
    *,
    counter_name: str,
    expected: float,
) -> tuple[str, ...]:
    """Return one violation when a counter differs from its exact budget."""

    actual = counters.get(counter_name, 0.0)
    if actual == expected:
        return ()
    return (
        _violation(
            delta,
            counter_name,
            expected=_format_number(expected),
            actual=actual,
        ),
    )


def _maximum_counter_violations(
    delta: PromptAbuseActionOwnerDelta,
    counters: Mapping[str, float],
    *,
    counter_name: str,
    maximum: float,
) -> tuple[str, ...]:
    """Return one violation when a counter exceeds its bounded budget."""

    actual = counters.get(counter_name, 0.0)
    if actual <= maximum:
        return ()
    return (
        _violation(
            delta,
            counter_name,
            expected=f"<={_format_number(maximum)}",
            actual=actual,
        ),
    )


def _violation(
    delta: PromptAbuseActionOwnerDelta,
    counter_name: str,
    *,
    expected: str,
    actual: float,
) -> str:
    """Format one stable structural-budget diagnostic for reports and CI."""

    return (
        "structural_budget:"
        f"action={delta.action_index}:"
        f"unit={delta.unit_index}:"
        f"label={delta.label}:"
        f"counter={counter_name}:"
        f"expected={expected}:"
        f"actual={_format_number(actual)}"
    )


def _format_number(value: float) -> str:
    """Format integral counters without hiding non-integral diagnostic values."""

    return str(int(value)) if value.is_integer() else f"{value:g}"


__all__ = ["prompt_abuse_structural_violations"]
