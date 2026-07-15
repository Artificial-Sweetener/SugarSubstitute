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

"""Verify prompt-safe reorder telemetry wrappers and context builders."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import pytest
from PySide6.QtCore import QPointF, QRect, QRectF
from PySide6.QtGui import QColor

from substitute.application.prompt_editor import PromptLineDropTarget
from substitute.presentation.editor.prompt_editor.overlays.chip_painter import (
    PromptChipPaintStyle,
)
from substitute.presentation.editor.prompt_editor.overlays.chip_visuals import (
    PromptChipVisual,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_telemetry import (
    PromptReorderTelemetry,
)
from substitute.presentation.editor.prompt_editor.projection.observability import (
    log_reorder_drag_event,
)

_TELEMETRY_LOGGER_NAME = (
    "sugarsubstitute.presentation.editor.prompt_editor.overlays.reorder_telemetry"
)


@dataclass(frozen=True, slots=True)
class _HeldShadowMetricsDouble:
    """Carry the held-shadow attributes consumed by telemetry tests."""

    chip_index: int
    normalized_bubble_rects: tuple[QRectF, ...]
    chrome_bounds: QRectF
    hotspot_bounds: QRectF
    source: str
    low_confidence: bool = False


def _chip_visual() -> PromptChipVisual:
    """Build one deterministic visual with multiple bubble rects."""

    return PromptChipVisual(
        bubble_rects=(QRectF(1.0, 2.0, 12.0, 6.0), QRectF(2.0, 10.0, 10.0, 6.0)),
        fragment_union_rect=QRectF(1.0, 2.0, 12.0, 14.0),
        hotspot_rect=QRect(0, 1, 14, 18),
        slot_before=QPointF(1.0, 5.0),
        slot_after=QPointF(13.0, 5.0),
        marker_height=14.0,
    )


def test_raw_reorder_observability_remains_strict_for_unsafe_fields() -> None:
    """Raw projection observability should still reject prompt-bearing field names."""

    with pytest.raises(ValueError, match="not prompt-safe"):
        log_reorder_drag_event("safe.event", prompt_text="leak")


def test_interaction_event_wrapper_warns_without_raising_for_validation_failures(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Interaction telemetry should not break gestures for instrumentation mistakes."""

    telemetry = PromptReorderTelemetry()
    caplog.set_level(logging.WARNING, logger=_TELEMETRY_LOGGER_NAME)

    telemetry.log_event(
        "safe.event",
        gesture_id=7,
        event_id=9,
        prompt_text="leak",
    )

    assert len(caplog.records) == 1
    assert "reorder.telemetry_validation_failed" in caplog.text
    assert "telemetry_event_fingerprint=" in caplog.text
    assert "field_name_fingerprints=" in caplog.text
    assert "unsafe_field_name_count=1" in caplog.text
    assert "leak" not in caplog.text
    assert "prompt_text" not in caplog.text


def test_interaction_timing_wrapper_returns_elapsed_after_validation_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Timing wrappers should preserve caller control flow after safe-field failure."""

    telemetry = PromptReorderTelemetry()
    caplog.set_level(logging.WARNING, logger=_TELEMETRY_LOGGER_NAME)

    elapsed_ms = telemetry.log_timing(
        "safe.event",
        started_at=time.perf_counter() - 0.001,
        selected_prompt_text="leak",
    )

    assert elapsed_ms >= 0.0
    assert "reorder.telemetry_validation_failed" in caplog.text
    assert "leak" not in caplog.text
    assert "selected_prompt_text" not in caplog.text


def test_interaction_wrapper_warning_does_not_log_unsafe_names_or_events(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Validation warnings should not serialize rejected names or event strings."""

    telemetry = PromptReorderTelemetry()
    caplog.set_level(logging.WARNING, logger=_TELEMETRY_LOGGER_NAME)

    telemetry.log_event(
        "prompt.some private content",
        **{
            "gesture_id": 7,
            "prompt_private_content": 1,
            "api_key_private_content": 2,
        },
    )

    assert "reorder.telemetry_validation_failed" in caplog.text
    assert "telemetry_event_fingerprint=" in caplog.text
    assert "telemetry_event_name_state=unsafe" in caplog.text
    assert "unsafe_field_name_count=2" in caplog.text
    assert "some private content" not in caplog.text
    assert "prompt_private_content" not in caplog.text
    assert "api_key_private_content" not in caplog.text


def test_interaction_wrapper_does_not_swallow_non_validation_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only known prompt-safe validation failures should be suppressed."""

    telemetry = PromptReorderTelemetry()

    def raise_runtime_error(_event: str, **_context: object) -> None:
        """Simulate a non-validation logging failure."""

        raise RuntimeError("unexpected logger failure")

    monkeypatch.setattr(
        "substitute.presentation.editor.prompt_editor.overlays.reorder_telemetry."
        "log_reorder_drag_event",
        raise_runtime_error,
    )

    with pytest.raises(RuntimeError, match="unexpected logger failure"):
        telemetry.log_event("safe.event", gesture_id=1)


def test_interaction_wrapper_does_not_swallow_unrelated_value_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validation suppression should not hide arbitrary ValueError failures."""

    telemetry = PromptReorderTelemetry()

    def raise_value_error(_event: str, **_context: object) -> None:
        """Simulate an unrelated value failure from a dependency."""

        raise ValueError("unrelated failure")

    monkeypatch.setattr(
        "substitute.presentation.editor.prompt_editor.overlays.reorder_telemetry."
        "log_reorder_drag_event",
        raise_value_error,
    )

    with pytest.raises(ValueError, match="unrelated failure"):
        telemetry.log_event("safe.event", gesture_id=1)


def test_reorder_structural_context_builders_stay_prompt_safe(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Extracted context builders should emit structural metrics only."""

    telemetry = PromptReorderTelemetry()
    visual = _chip_visual()
    style = PromptChipPaintStyle(
        fill_color=QColor(1, 2, 3, 4),
        border_color=QColor(5, 6, 7, 8),
        outline_width=1.25,
        opacity=0.75,
        outline_only=True,
    )
    held_shadow = _HeldShadowMetricsDouble(
        chip_index=3,
        normalized_bubble_rects=visual.bubble_rects,
        chrome_bounds=QRectF(0.0, 0.0, 14.0, 18.0),
        hotspot_bounds=QRectF(1.0, 2.0, 12.0, 14.0),
        source="live_chip_geometry",
    )

    caplog.set_level(
        logging.DEBUG,
        logger="sugarsubstitute.presentation.editor.prompt_editor.projection.observability",
    )
    log_reorder_drag_event(
        "drop_target.resolve",
        **telemetry.target_context(
            PromptLineDropTarget(row_index=1, insertion_index=2),
            prefix="active_target",
        ),
        **telemetry.style_context(style, prefix="landing_style"),
        **telemetry.visual_context(visual, prefix="landing_visual"),
        **telemetry.held_shadow_context(held_shadow),
        **telemetry.visual_delta_context(visual, visual, prefix="landing_delta"),
    )

    assert "PromptLineDropTarget" in caplog.text
    assert "live_chip_geometry" in caplog.text
    assert "prompt_text" not in caplog.text.lower()
    assert "selected_text" not in caplog.text.lower()


def test_reorder_pointer_sampling_keeps_target_changes_visible() -> None:
    """Repeated pointer events should sample, while target changes always log."""

    telemetry = PromptReorderTelemetry(pointer_sample_interval=5)

    assert telemetry.should_log_pointer_event(move_count=1, target_changed=False)
    assert not telemetry.should_log_pointer_event(move_count=4, target_changed=False)
    assert telemetry.should_log_pointer_event(move_count=5, target_changed=False)
    assert telemetry.should_log_pointer_event(move_count=4, target_changed=True)
