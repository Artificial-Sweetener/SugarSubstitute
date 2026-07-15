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

"""Provide prompt-safe panel projection lifecycle observability helpers."""

from __future__ import annotations

from collections.abc import Mapping
import time

from substitute.shared.logging.logger import (
    elapsed_ms_since,
    get_logger,
    log_debug,
    log_info,
    log_warning,
)

_LOGGER = get_logger("presentation.editor.panel.projection_observability")
_SAFE_PANEL_PROJECTION_EVENT_NAMES = frozenset(
    {
        "full_projection.start",
        "full_projection.complete",
        "full_projection.live_complete",
        "full_projection.projected_complete",
        "hidden_build.cube_step",
        "hidden_build.scheduled",
        "hidden_build.session_complete",
        "hidden_build.first_usable",
        "hidden_build.section_ready",
        "hidden_build.section_started",
        "preparation.behavior_snapshot",
        "preparation.hydrate_node_definitions",
        "preparation.link_state_refresh",
        "preparation.prompt_link_reconciliation",
        "choice_factory.combo_prepare_items",
        "choice_factory.combo_resolve_options",
        "choice_factory.model_picker_construct",
        "model_choice.literal_snapshot",
        "model_choice.snapshot_options",
        "node_card.build_fields",
        "node_card.built",
        "node_card.create_title_row",
        "node_card.field_factory",
        "node_card.field_prepared",
        "node_card.field_wired",
        "node_card.snapshot_panel",
        "prompt_context.profile_cache_build",
        "prompt_context.profile_cache_hit",
        "prompt_context.profile_cache_miss",
        "prompt_context.profile_cache_reset",
        "prompt_context.projection_begin",
        "prompt_context.projection_clear",
        "prompt_context.snapshot_cubes",
        "prompt_context.snapshot_overrides",
        "prompt_factory.editor_construct",
        "prompt_factory.initial_text_assigned",
        "render_reconciler.projected_cube_revealed",
        "visible_commit.completed",
        "visible_commit.retry_scheduled",
    }
)
_SAFE_PANEL_PROJECTION_FIELD_NAMES = frozenset(
    {
        "active_workflow_id",
        "behavior_snapshot_present",
        "build_delay_ms",
        "build_state",
        "built_card_count",
        "busy_started",
        "cache_entry_count",
        "context_source",
        "cube_alias",
        "cube_count",
        "cube_section_count",
        "deferred_node_count",
        "elapsed_ms",
        "errored_cube_count",
        "error_type",
        "existing_widget_count",
        "field_spec_count",
        "field_spec_node_count",
        "field_key",
        "field_type",
        "final_section_revealed",
        "finished",
        "first_usable_card",
        "has_lora_catalog",
        "has_rows",
        "has_segment_presets",
        "has_spellcheck_service",
        "has_title_controls",
        "model_kind",
        "node_class",
        "node_class_type",
        "node_count",
        "node_index",
        "node_name",
        "option_count",
        "ordered_widget_count",
        "override_count",
        "panel_visible",
        "pending_build_count",
        "presentation",
        "previous_entry_count",
        "projection_aliases",
        "projection_context_present",
        "projection_mode",
        "reason",
        "readiness",
        "refresh_mode",
        "remaining_cube_count",
        "result_type",
        "retry_attempts",
        "retry_limit",
        "retry_scheduled",
        "skipped_card_count",
        "slow_threshold_ms",
        "stack_order_count",
        "stale_reason",
        "text_length",
        "visible_group_count",
        "widget_type",
        "workflow_id",
    }
)
_SAFE_PANEL_PROJECTION_SUFFIXES = (
    "_count",
    "_delay_ms",
    "_elapsed_ms",
    "_id",
    "_index",
    "_mode",
    "_present",
    "_reason",
    "_scheduled",
    "_state",
    "_threshold_ms",
    "_visible",
)
_FORBIDDEN_FIELD_FRAGMENTS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "exception",
    "file",
    "password",
    "path",
    "prompt",
    "secret",
    "selected",
    "source",
    "text",
    "token",
    "trigger",
    "value",
)


def panel_projection_observability_started_at() -> float:
    """Return a monotonic timestamp for one measured panel projection operation."""

    return time.perf_counter()


def log_panel_projection_event(
    event: str,
    *,
    level: str = "debug",
    **context: object,
) -> None:
    """Log one prompt-safe panel projection lifecycle event."""

    _require_prompt_safe_panel_projection_event_name(event)
    _log_panel_projection(level, event, _validated_panel_projection_context(context))


def log_panel_projection_timing(
    event: str,
    *,
    started_at: float,
    level: str = "debug",
    **context: object,
) -> float:
    """Log and return elapsed milliseconds for one panel projection event."""

    _require_prompt_safe_panel_projection_event_name(event)
    elapsed_ms = elapsed_ms_since(started_at)
    timing_context = _validated_panel_projection_context(context)
    timing_context["elapsed_ms"] = f"{elapsed_ms:.3f}"
    _log_panel_projection(level, event, timing_context)
    return elapsed_ms


def _log_panel_projection(
    level: str,
    event: str,
    context: Mapping[str, object],
) -> None:
    """Dispatch one validated panel projection log event."""

    if level == "info":
        log_info(_LOGGER, event, **context)
        return
    if level == "warning":
        log_warning(_LOGGER, event, **context)
        return
    log_debug(_LOGGER, event, **context)


def _validated_panel_projection_context(
    context: Mapping[str, object],
) -> dict[str, object]:
    """Return context fields after rejecting prompt-sensitive field names."""

    validated: dict[str, object] = {}
    for field_name, value in context.items():
        _require_prompt_safe_panel_projection_field_name(field_name)
        validated[field_name] = value
    return validated


def _require_prompt_safe_panel_projection_event_name(event: str) -> None:
    """Reject blank or content-bearing panel projection event names."""

    normalized = event.strip().lower().replace("-", "_")
    if not normalized:
        raise ValueError("panel projection log event name must not be blank.")
    if normalized in _SAFE_PANEL_PROJECTION_EVENT_NAMES:
        return
    if any(fragment in normalized for fragment in _FORBIDDEN_FIELD_FRAGMENTS):
        raise ValueError(f"panel projection log event is not prompt-safe: {event}")


def _require_prompt_safe_panel_projection_field_name(field_name: str) -> None:
    """Reject panel projection context fields that may carry prompt content."""

    normalized = field_name.strip().lower().replace("-", "_")
    if not normalized:
        raise ValueError("panel projection log field name must not be blank.")
    if normalized in _SAFE_PANEL_PROJECTION_FIELD_NAMES:
        return
    if any(fragment in normalized for fragment in _FORBIDDEN_FIELD_FRAGMENTS):
        raise ValueError(f"panel projection log field is not prompt-safe: {field_name}")
    if normalized.endswith(_SAFE_PANEL_PROJECTION_SUFFIXES):
        return
    raise ValueError(
        f"panel projection log field is not recognized as prompt-safe: {field_name}"
    )


__all__ = [
    "log_panel_projection_event",
    "log_panel_projection_timing",
    "panel_projection_observability_started_at",
]
