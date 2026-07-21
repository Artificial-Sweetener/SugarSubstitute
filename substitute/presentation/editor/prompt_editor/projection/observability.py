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

"""Provide prompt-safe projection and reorder observability helpers."""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from itertools import count
import time

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor

from substitute.application.prompt_editor import (
    PromptLoraRendererView,
    PromptSyntaxRenderPlan,
)
from substitute.shared.logging.logger import elapsed_ms_since, get_logger, log_debug

_LOGGER = get_logger("presentation.editor.prompt_editor.projection.observability")
_REORDER_DRAG_GESTURE_IDS = count(1)
_SAFE_PROJECTION_EVENT_NAMES = frozenset(
    {
        "incremental_apply.source_change",
        "source_change.immediate_projection",
        "source_change.prepare_document_view",
        "source_change.qtext_document",
        "surface.rebuild_projection",
    }
)
_SAFE_PROJECTION_FIELD_NAMES = frozenset(
    {
        "apply_path",
        "display_mode",
        "emit_text_changed",
        "fast_projection_applied",
        "incremental_plain_edit_attempted",
        "run_count",
        "text_length",
        "token_count",
        "wrap_reflow_deferred",
    }
)
_SAFE_TEXT_METRIC_FIELD_NAMES = frozenset(
    {
        "has_text_payload",
        "segment_text_length",
        "text_fragment_count",
        "text_length",
    }
)
_SAFE_COUNT_METRIC_FIELD_NAMES = frozenset(
    {
        "inline_object_count",
        "run_count",
        "segment_count",
        "text_fragment_count",
        "token_count",
    }
)
_SAFE_REORDER_EVENT_NAMES = frozenset(
    {
        "anomaly.chip_geometry_empty_path",
        "anomaly.active_target_without_visual",
        "anomaly.placement_duplicate_target",
        "anomaly.target_changed_without_preview_update",
        "drag_move.target_update",
        "drop_target.blank_line",
        "drop_target.blank_line_selected",
        "drop_target.changed.chip_geometry",
        "drop_target.changed.paint_request",
        "drop_target.changed.preview_layout",
        "drop_target.changed.preview_signal",
        "drop_target.changed_rebuild_path",
        "drop_target.no_change_fast_path",
        "drop_target.no_lane",
        "drop_target.no_lanes",
        "drop_target.placement_none",
        "drop_target.resolve",
        "drop_target.row_slot",
        "drop_target.total",
        "drop_target.visual_lane_selected",
        "landing_preview.skipped_no_active_target",
        "landing_preview.target_alignment",
        "placement_hit.selected",
        "preview_shadow.rejected_stale_target",
        "target_visual.marker_rect",
        "target_visual.marker_skipped",
        "target_visual.marker_skipped_landing_geometry",
        "target_visual.marker_skipped_pending_fallback",
    }
)
_SAFE_SELECTED_METRIC_FIELD_NAMES = frozenset({"selected"})
_SAFE_PATH_METRIC_FIELD_NAMES = frozenset({"chip_geometry_has_path"})
_SAFE_REORDER_REVISION_FIELD_NAMES = frozenset({"source_revision"})
_SAFE_REORDER_CACHE_FIELD_NAMES = frozenset({"cache_source"})
_SAFE_SOURCE_POSITION_FIELD_SUFFIXES = (
    "_source_after",
    "_source_before",
    "_source_end",
    "_source_length",
    "_source_start",
)
_SAFE_TARGET_METRIC_FIELD_NAMES = frozenset(
    {
        "active_target_kind",
        "committed_target_kind",
        "commit_target_kind",
        "drop_target_changed_count",
        "drop_target_no_change_count",
        "duplicate_target_count",
        "duplicate_targets",
        "ending_target_kind",
        "expected_preview_target_dragged_segment_index",
        "expected_preview_target_kind",
        "expected_preview_target_source_layout_key",
        "has_active_target",
        "landing_center_to_target_center_dx",
        "landing_center_to_target_center_dy",
        "landing_left_to_target_left_dx",
        "landing_right_to_target_right_dx",
        "last_landing_target_kind",
        "next_target_kind",
        "preview_fresh_for_target",
        "preview_target_identity_matches",
        "previous_target_kind",
        "preview_geometry_target_dragged_segment_index",
        "preview_geometry_target_kind",
        "preview_geometry_target_source_layout_key",
        "target_change_count",
        "target_changed",
        "target_elapsed_ms",
        "target_kind",
        "target_anchor_center_x",
        "target_anchor_center_y",
        "target_anchor_left_x",
        "target_anchor_right_x",
        "target_bubble_count",
        "target_landing_center_dx",
        "target_landing_center_dy",
        "visual_target_count",
    }
)
_SAFE_TARGET_CONTEXT_SUFFIXES = frozenset(
    {
        "_target_blank_line_index",
        "_target_gap_index",
        "_target_insertion_index",
        "_target_kind",
        "_target_row_index",
    }
)
_SAFE_TARGET_RECT_PREFIXES = frozenset({"target_hit"})
_SAFE_RECT_FIELD_SUFFIXES = frozenset(
    {
        "center_x",
        "center_y",
        "height",
        "left",
        "top",
        "width",
    }
)
_FORBIDDEN_LOG_FIELD_FRAGMENTS = (
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


def render_plan_lora_span_count(render_plan: PromptSyntaxRenderPlan) -> int:
    """Return renderer-ready LoRA span count for projection diagnostics."""

    renderer_view = render_plan.renderer_view_for_kind("lora")
    if not isinstance(renderer_view, PromptLoraRendererView):
        return 0
    return len(renderer_view.lora_spans)


def next_reorder_drag_gesture_id() -> int:
    """Return a process-local gesture identifier for one drag gesture."""

    return next(_REORDER_DRAG_GESTURE_IDS)


def reorder_drag_started_at() -> float:
    """Return a monotonic timestamp for one measured reorder operation."""

    return time.perf_counter()


def projection_observability_started_at() -> float:
    """Return a monotonic timestamp for one measured projection operation."""

    return time.perf_counter()


def log_projection_timing(
    event: str,
    *,
    started_at: float,
    **context: object,
) -> float:
    """Log and return elapsed milliseconds for one prompt-safe projection event."""

    _require_prompt_safe_projection_event_name(event)
    elapsed_ms = elapsed_ms_since(started_at)
    timing_context = _validated_projection_context_fields(context)
    timing_context["elapsed_ms"] = f"{elapsed_ms:.3f}"
    log_debug(_LOGGER, event, **timing_context)
    return elapsed_ms


def log_reorder_drag_event(event: str, **context: object) -> None:
    """Log one prompt-safe reorder diagnostic event at debug level."""

    _require_prompt_safe_event_name(event)
    log_debug(_LOGGER, event, **_validated_reorder_context_fields(context))


def log_reorder_drag_timing(
    event: str,
    *,
    started_at: float,
    **context: object,
) -> float:
    """Log and return elapsed milliseconds for one prompt-safe reorder operation."""

    _require_prompt_safe_event_name(event)
    elapsed_ms = elapsed_ms_since(started_at)
    timing_context = _validated_reorder_context_fields(context)
    timing_context["elapsed_ms"] = f"{elapsed_ms:.3f}"
    log_debug(_LOGGER, event, **timing_context)
    return elapsed_ms


def reorder_drag_target_kind(target: object | None) -> str:
    """Return a stable short label for one typed reorder target."""

    if target is None:
        return "none"
    return target.__class__.__name__


def reorder_drag_point_context(point: QPointF, *, prefix: str) -> dict[str, str]:
    """Return compact rounded coordinate context for one placement point."""

    return {
        f"{prefix}_x": f"{point.x():.2f}",
        f"{prefix}_y": f"{point.y():.2f}",
    }


def reorder_drag_color_context(color: QColor, *, prefix: str) -> dict[str, object]:
    """Return compact RGBA context for one diagnostic color value."""

    return {
        f"{prefix}_red": color.red(),
        f"{prefix}_green": color.green(),
        f"{prefix}_blue": color.blue(),
        f"{prefix}_alpha": color.alpha(),
        f"{prefix}_hex_argb": color.name(QColor.NameFormat.HexArgb),
    }


def reorder_drag_rect_context(rect: QRectF, *, prefix: str) -> dict[str, str]:
    """Return compact rounded rectangle context for one placement area."""

    return {
        f"{prefix}_left": f"{rect.left():.2f}",
        f"{prefix}_top": f"{rect.top():.2f}",
        f"{prefix}_width": f"{rect.width():.2f}",
        f"{prefix}_height": f"{rect.height():.2f}",
        f"{prefix}_center_x": f"{rect.center().x():.2f}",
        f"{prefix}_center_y": f"{rect.center().y():.2f}",
    }


def _validated_reorder_context_fields(
    context: Mapping[str, object],
) -> dict[str, object]:
    """Return reorder context fields after rejecting prompt-sensitive names."""

    validated: dict[str, object] = {}
    for field_name, value in context.items():
        _require_prompt_safe_field_name(field_name)
        validated[field_name] = value
    return validated


def _validated_projection_context_fields(
    context: Mapping[str, object],
) -> dict[str, object]:
    """Return source/rebuild context fields after rejecting unsafe names."""

    validated: dict[str, object] = {}
    for field_name, value in context.items():
        _require_prompt_safe_projection_field_name(field_name)
        validated[field_name] = value
    return validated


@lru_cache(maxsize=None)
def _require_prompt_safe_projection_event_name(event: str) -> None:
    """Reject blank or content-bearing projection event names before logging."""

    normalized = event.strip().lower().replace("-", "_")
    if not normalized:
        raise ValueError("projection log event name must not be blank.")
    if normalized in _SAFE_PROJECTION_EVENT_NAMES:
        return
    if any(fragment in normalized for fragment in _FORBIDDEN_LOG_FIELD_FRAGMENTS):
        raise ValueError(f"projection log event is not prompt-safe: {event}")


@lru_cache(maxsize=None)
def _require_prompt_safe_projection_field_name(field_name: str) -> None:
    """Reject projection context fields that may carry prompt content or secrets."""

    normalized = field_name.strip().lower().replace("-", "_")
    if not normalized:
        raise ValueError("projection log field name must not be blank.")
    if normalized in _SAFE_PROJECTION_FIELD_NAMES:
        return
    if normalized in _SAFE_COUNT_METRIC_FIELD_NAMES:
        return
    if normalized in _SAFE_TEXT_METRIC_FIELD_NAMES:
        return
    if normalized.endswith("_text_length"):
        return
    if any(fragment in normalized for fragment in _FORBIDDEN_LOG_FIELD_FRAGMENTS):
        raise ValueError(f"projection log field is not prompt-safe: {field_name}")


@lru_cache(maxsize=None)
def _require_prompt_safe_event_name(event: str) -> None:
    """Reject blank or content-bearing reorder event names before logging."""

    normalized = event.strip().lower().replace("-", "_")
    if not normalized:
        raise ValueError("reorder log event name must not be blank.")
    if normalized in _SAFE_REORDER_EVENT_NAMES:
        return
    if any(fragment in normalized for fragment in _FORBIDDEN_LOG_FIELD_FRAGMENTS):
        raise ValueError(f"reorder log event is not prompt-safe: {event}")


@lru_cache(maxsize=None)
def _require_prompt_safe_field_name(field_name: str) -> None:
    """Reject reorder context fields that may carry prompt content or secrets."""

    normalized = field_name.strip().lower().replace("-", "_")
    if not normalized:
        raise ValueError("reorder log field name must not be blank.")
    if normalized in _SAFE_COUNT_METRIC_FIELD_NAMES:
        return
    if normalized in _SAFE_TEXT_METRIC_FIELD_NAMES:
        return
    if normalized.endswith("_text_length"):
        return
    if normalized in _SAFE_SELECTED_METRIC_FIELD_NAMES:
        return
    if normalized in _SAFE_PATH_METRIC_FIELD_NAMES:
        return
    if normalized.endswith("_geometry_has_path"):
        return
    if normalized in _SAFE_REORDER_REVISION_FIELD_NAMES:
        return
    if normalized in _SAFE_REORDER_CACHE_FIELD_NAMES:
        return
    if normalized.endswith(_SAFE_SOURCE_POSITION_FIELD_SUFFIXES):
        return
    if normalized in _SAFE_TARGET_METRIC_FIELD_NAMES:
        return
    if _is_safe_target_context_field(normalized):
        return
    if any(fragment in normalized for fragment in _FORBIDDEN_LOG_FIELD_FRAGMENTS):
        raise ValueError(f"reorder log field is not prompt-safe: {field_name}")


def _is_safe_target_context_field(normalized: str) -> bool:
    """Return whether a target-bearing field is structural drag telemetry."""

    if any(normalized.endswith(suffix) for suffix in _SAFE_TARGET_CONTEXT_SUFFIXES):
        return True
    for prefix in _SAFE_TARGET_RECT_PREFIXES:
        if any(
            normalized == f"{prefix}_{suffix}" for suffix in _SAFE_RECT_FIELD_SUFFIXES
        ):
            return True
    return False


__all__ = [
    "log_projection_timing",
    "log_reorder_drag_event",
    "log_reorder_drag_timing",
    "next_reorder_drag_gesture_id",
    "projection_observability_started_at",
    "render_plan_lora_span_count",
    "reorder_drag_color_context",
    "reorder_drag_point_context",
    "reorder_drag_rect_context",
    "reorder_drag_started_at",
    "reorder_drag_target_kind",
]
