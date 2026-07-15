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

"""Tests for prompt-safe prompt projection observability helpers."""

from __future__ import annotations

import logging
import time

import pytest
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor

from substitute.presentation.editor.prompt_editor.projection.observability import (
    log_projection_timing,
    log_reorder_drag_event,
    log_reorder_drag_timing,
    projection_observability_started_at,
    reorder_drag_color_context,
    reorder_drag_point_context,
    reorder_drag_rect_context,
)

_LOGGER_NAME = (
    "sugarsubstitute.presentation.editor.prompt_editor.projection.observability"
)


def test_projection_timing_logs_prompt_safe_source_metrics(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Projection timing should expose source metrics without source text."""

    caplog.set_level(logging.DEBUG, logger=_LOGGER_NAME)

    elapsed_ms = log_projection_timing(
        "source_change.prepare_document_view",
        started_at=time.perf_counter() - 0.001,
        text_length=42,
        emit_text_changed=True,
    )

    assert elapsed_ms >= 0.0
    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    assert "source_change.prepare_document_view" in messages[0]
    assert "elapsed_ms=" in messages[0]
    assert "text_length=42" in messages[0]
    assert "emit_text_changed=True" in messages[0]
    assert "source_text" not in messages[0].lower()


def test_projection_timing_logs_apply_path_without_payloads(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Projection apply diagnostics should log decisions, not prompt content."""

    caplog.set_level(logging.DEBUG, logger=_LOGGER_NAME)

    log_projection_timing(
        "incremental_apply.source_change",
        started_at=projection_observability_started_at(),
        text_length=11,
        apply_path="incremental",
        fast_projection_applied=True,
        wrap_reflow_deferred=False,
        incremental_plain_edit_attempted=True,
    )

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    assert "incremental_apply.source_change" in messages[0]
    assert "apply_path=incremental" in messages[0]
    assert "fast_projection_applied=True" in messages[0]
    assert "wrap_reflow_deferred=False" in messages[0]
    assert "incremental_plain_edit_attempted=True" in messages[0]


@pytest.mark.parametrize(
    "unsafe_field_name",
    [
        "prompt_text",
        "source_text",
        "selected_text",
        "token_payload",
        "trigger_words",
        "file_path",
        "api_key",
        "authorization_header",
        "cookie_value",
        "credential_name",
        "exception_message",
        "field_value",
        "raw_exception",
    ],
)
def test_projection_timing_rejects_content_bearing_field_names(
    unsafe_field_name: str,
) -> None:
    """Projection source/rebuild logs should reject prompt-sensitive fields."""

    with pytest.raises(ValueError, match="not prompt-safe"):
        log_projection_timing(
            "source_change.prepare_document_view",
            started_at=projection_observability_started_at(),
            **{unsafe_field_name: "leak"},
        )


def test_projection_timing_rejects_content_bearing_event_names() -> None:
    """Projection event names should not describe prompt content."""

    with pytest.raises(ValueError, match="not prompt-safe"):
        log_projection_timing(
            "source_text.probe",
            started_at=projection_observability_started_at(),
            text_length=1,
        )


def test_reorder_drag_event_logs_prompt_safe_debug_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Reorder event logging should preserve useful metrics without prompt content."""

    caplog.set_level(logging.DEBUG, logger=_LOGGER_NAME)

    log_reorder_drag_event(
        "preview_scheduler.ran",
        gesture_id=7,
        event_id=9,
        source_revision=42,
        segment_text_length=23,
        selected=True,
        chip_geometry_has_path=False,
        cache_hit=False,
    )

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    assert "preview_scheduler.ran" in messages[0]
    assert "gesture_id=7" in messages[0]
    assert "source_revision=42" in messages[0]
    assert "segment_text_length=23" in messages[0]
    assert "selected=True" in messages[0]
    assert "chip_geometry_has_path=False" in messages[0]
    assert "prompt_text" not in messages[0].lower()
    assert "selected_text" not in messages[0].lower()


def test_reorder_drag_timing_logs_elapsed_ms_and_returns_duration(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Reorder timing should expose duration as a metric, not content."""

    caplog.set_level(logging.DEBUG, logger=_LOGGER_NAME)

    elapsed_ms = log_reorder_drag_timing(
        "surface.rebuild_reorder_projection.total",
        started_at=time.perf_counter() - 0.001,
        gesture_id=3,
        text_length=11,
        render_plan_lora_span_count=2,
    )

    assert elapsed_ms >= 0.0
    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    assert "surface.rebuild_reorder_projection.total" in messages[0]
    assert "elapsed_ms=" in messages[0]
    assert "text_length=11" in messages[0]
    assert "render_plan_lora_span_count=2" in messages[0]


def test_reorder_drag_timing_accepts_projection_count_metrics(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Projection count metrics should remain loggable without prompt content."""

    caplog.set_level(logging.DEBUG, logger=_LOGGER_NAME)

    log_reorder_drag_timing(
        "surface.build_reorder_projection_snapshot.layout",
        started_at=time.perf_counter() - 0.001,
        gesture_id=5,
        run_count=8,
        token_count=13,
        segment_count=3,
        text_fragment_count=21,
        inline_object_count=2,
    )

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    assert "run_count=8" in messages[0]
    assert "token_count=13" in messages[0]
    assert "segment_count=3" in messages[0]
    assert "text_fragment_count=21" in messages[0]
    assert "inline_object_count=2" in messages[0]
    assert "prompt_text" not in messages[0].lower()
    assert "selected_text" not in messages[0].lower()


def test_reorder_drag_event_accepts_selected_state_label(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Selected-state event labels should not be treated as selected text."""

    caplog.set_level(logging.DEBUG, logger=_LOGGER_NAME)

    log_reorder_drag_event(
        "placement_hit.selected",
        gesture_id=11,
        selected=True,
    )

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    assert "placement_hit.selected" in messages[0]
    assert "selected=True" in messages[0]


@pytest.mark.parametrize(
    "event_name",
    [
        "anomaly.active_target_without_visual",
        "anomaly.chip_geometry_empty_path",
        "anomaly.placement_duplicate_target",
        "anomaly.target_changed_without_preview_update",
        "drag_move.target_update",
        "drop_target.blank_line_selected",
        "drop_target.changed_rebuild_path",
        "drop_target.no_change_fast_path",
        "drop_target.resolve",
        "drop_target.visual_lane_selected",
        "landing_preview.skipped_no_active_target",
        "landing_preview.target_alignment",
        "preview_shadow.rejected_stale_target",
        "target_visual.marker_rect",
    ],
)
def test_reorder_drag_event_accepts_structural_target_labels(
    event_name: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Structural target/path event labels should remain valid diagnostics."""

    caplog.set_level(logging.DEBUG, logger=_LOGGER_NAME)

    log_reorder_drag_event(event_name, gesture_id=12, target_changed=True)

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    assert event_name in messages[0]
    assert "target_changed=True" in messages[0]


def test_reorder_drag_event_accepts_structural_target_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Target context fields should log structural geometry, never prompt content."""

    caplog.set_level(logging.DEBUG, logger=_LOGGER_NAME)

    log_reorder_drag_event(
        "drop_target.resolve",
        active_target_kind="PromptLineDropTarget",
        expected_preview_target_dragged_segment_index=2,
        expected_preview_target_source_layout_key="layout(width=320)",
        expected_preview_target_target_kind="PromptLineDropTarget",
        expected_preview_target_target_row_index=1,
        actual_geometry_has_path=True,
        landing_geometry_has_path=False,
        previous_target_kind="none",
        target_hit_left="10.00",
        target_hit_center_y="15.00",
        target_anchor_center_x="12.00",
        target_landing_center_dx="0.00",
        visual_target_count=4,
    )

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    assert "drop_target.resolve" in messages[0]
    assert "active_target_kind=PromptLineDropTarget" in messages[0]
    assert "actual_geometry_has_path=True" in messages[0]
    assert "landing_geometry_has_path=False" in messages[0]
    assert "expected_preview_target_target_row_index=1" in messages[0]
    assert "target_hit_center_y=15.00" in messages[0]
    assert "target_landing_center_dx=0.00" in messages[0]
    assert "prompt_text" not in messages[0].lower()
    assert "selected_text" not in messages[0].lower()


def test_reorder_drag_event_accepts_structural_source_position_metrics(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Source-position metrics should remain distinct from raw source text."""

    caplog.set_level(logging.DEBUG, logger=_LOGGER_NAME)

    log_reorder_drag_event(
        "drop_target.resolve",
        placement_source_before=4,
        placement_source_after=8,
        chip_geometry_source_start=4,
        chip_geometry_source_end=8,
        chip_geometry_source_length=4,
    )

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    assert "placement_source_before=4" in messages[0]
    assert "chip_geometry_source_end=8" in messages[0]
    assert "chip_geometry_source_length=4" in messages[0]
    assert "source_text" not in messages[0].lower()


def test_reorder_drag_event_accepts_structural_shadow_origin(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Held-shadow origin labels should remain loggable without raw source fields."""

    caplog.set_level(logging.DEBUG, logger=_LOGGER_NAME)

    log_reorder_drag_event(
        "preview_shadow.held_size_captured",
        held_shadow_origin="live_chip_geometry",
        shadow_origin="chip_widget",
        held_shadow_width="24.00",
        held_shadow_height="16.00",
    )

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    assert "held_shadow_origin=live_chip_geometry" in messages[0]
    assert "shadow_origin=chip_widget" in messages[0]
    assert "held_shadow_source" not in messages[0]
    assert " source=" not in messages[0]


def test_reorder_drag_timing_accepts_structural_autoscroll_positions(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Autoscroll diagnostics should log scrollbar positions, not value payloads."""

    caplog.set_level(logging.DEBUG, logger=_LOGGER_NAME)

    log_reorder_drag_timing(
        "autoscroll.step",
        started_at=time.perf_counter() - 0.001,
        scrollbar_position=12,
        previous_position=12,
        next_position=36,
        scrollbar_minimum=0,
        scrollbar_maximum=240,
    )

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    assert "scrollbar_position=12" in messages[0]
    assert "previous_position=12" in messages[0]
    assert "next_position=36" in messages[0]
    assert "scrollbar_value" not in messages[0]
    assert "previous_value" not in messages[0]


@pytest.mark.parametrize(
    "unsafe_field_name",
    [
        "prompt_text",
        "source",
        "held_shadow_source",
        "selected_text",
        "selected_prompt_text",
        "scrollbar_value",
        "previous_value",
        "token_value",
        "trigger_words",
        "api_key",
        "authorization_header",
        "cookie_value",
        "credential_name",
        "file_path",
        "exception_message",
        "field_value",
        "raw_exception",
    ],
)
def test_reorder_drag_logging_rejects_content_bearing_field_names(
    unsafe_field_name: str,
) -> None:
    """Reorder logs should reject field names that can carry prompt or secret data."""

    with pytest.raises(ValueError, match="not prompt-safe"):
        log_reorder_drag_event("safe.event", **{unsafe_field_name: "leak"})


def test_reorder_drag_logging_rejects_content_bearing_event_names() -> None:
    """Reorder logs should reject event labels that describe prompt content."""

    with pytest.raises(ValueError, match="not prompt-safe"):
        log_reorder_drag_event("prompt.text.probe", gesture_id=1)


def test_reorder_drag_geometry_contexts_are_prompt_safe_metrics() -> None:
    """Geometry context helpers should emit coordinates, dimensions, and color data only."""

    point_context = reorder_drag_point_context(QPointF(12.345, 67.891), prefix="point")
    rect_context = reorder_drag_rect_context(QRectF(1.2, 3.4, 5.6, 7.8), prefix="rect")
    color_context = reorder_drag_color_context(QColor(1, 2, 3, 4), prefix="color")

    assert point_context == {"point_x": "12.35", "point_y": "67.89"}
    assert rect_context == {
        "rect_left": "1.20",
        "rect_top": "3.40",
        "rect_width": "5.60",
        "rect_height": "7.80",
        "rect_center_x": "4.00",
        "rect_center_y": "7.30",
    }
    assert color_context == {
        "color_red": 1,
        "color_green": 2,
        "color_blue": 3,
        "color_alpha": 4,
        "color_hex_argb": "#04010203",
    }
