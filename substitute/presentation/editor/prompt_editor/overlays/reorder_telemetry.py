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

"""Build prompt-safe telemetry context for reorder overlay interactions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
from typing import Protocol

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor import (
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptReorderDropTarget,
)
from substitute.shared.logging.logger import (
    elapsed_ms_since,
    get_logger,
    log_warning,
)

from ..projection.observability import (
    log_reorder_drag_event,
    log_reorder_drag_timing,
    reorder_drag_color_context,
    reorder_drag_rect_context,
    reorder_drag_target_kind,
)
from .chip_painter import PromptChipPaintStyle
from .chip_visuals import PromptChipVisual

_LOGGER = get_logger("presentation.editor.prompt_editor.overlays.reorder_telemetry")
_VALIDATION_MESSAGE_FRAGMENTS = (
    "prompt-safe",
    "must not be blank",
)
_FORBIDDEN_NAME_FRAGMENTS = (
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


class PromptReorderHeldShadowTelemetry(Protocol):
    """Expose held-shadow metrics needed for prompt-safe telemetry."""

    @property
    def chip_index(self) -> int:
        """Return the segment index represented by the held shadow."""

    @property
    def normalized_bubble_rects(self) -> tuple[QRectF, ...]:
        """Return bubble rects normalized into held-shadow-local coordinates."""

    @property
    def chrome_bounds(self) -> QRectF:
        """Return the held shadow chrome bounds."""

    @property
    def hotspot_bounds(self) -> QRectF:
        """Return the held shadow hotspot bounds."""

    @property
    def source(self) -> str:
        """Return a prompt-safe structural source label."""

    @property
    def low_confidence(self) -> bool:
        """Return whether the shadow metrics came from fallback geometry."""


class PromptReorderTargetVisualTelemetry(Protocol):
    """Expose target hit geometry needed for prompt-safe telemetry."""

    @property
    def hit_rect(self) -> QRectF:
        """Return the prompt-safe target hit rectangle."""


@dataclass(slots=True)
class PromptReorderTelemetry:
    """Own prompt-safe reorder diagnostic context and interaction log wrappers."""

    pointer_sample_interval: int = 20
    _reported_validation_failures: set[tuple[str, tuple[str, ...]]] = field(
        default_factory=set,
        init=False,
    )

    def should_log_pointer_event(
        self,
        *,
        move_count: int,
        target_changed: bool,
    ) -> bool:
        """Return whether one repeated pointer move should emit debug telemetry."""

        if target_changed:
            return True
        if move_count <= 3:
            return True
        return move_count % max(1, self.pointer_sample_interval) == 0

    def log_event(
        self,
        event: str,
        **context: object,
    ) -> None:
        """Log one interaction event without letting validation break gestures."""

        try:
            log_reorder_drag_event(event, **context)
        except ValueError as error:
            if not self._is_prompt_safe_validation_error(error):
                raise
            self._warn_validation_failure(event, context, error)

    def log_timing(
        self,
        event: str,
        *,
        started_at: float,
        **context: object,
    ) -> float:
        """Log timing when valid and always return elapsed interaction duration."""

        try:
            return log_reorder_drag_timing(event, started_at=started_at, **context)
        except ValueError as error:
            if not self._is_prompt_safe_validation_error(error):
                raise
            self._warn_validation_failure(event, context, error)
            return elapsed_ms_since(started_at)

    def log_slow_path_if_needed(
        self,
        event: str,
        *,
        elapsed_ms: float,
        threshold_ms: float,
        gesture_id: int | None,
        event_id: int | None,
        **context: object,
    ) -> None:
        """Emit slow-path diagnostics only when an operation exceeds its budget."""

        if elapsed_ms < threshold_ms:
            return
        slow_context = {
            "gesture_id": gesture_id,
            "event_id": event_id,
            "elapsed_ms": f"{elapsed_ms:.3f}",
            "threshold_ms": f"{threshold_ms:.3f}",
            **context,
        }
        self.log_event(event, **slow_context)
        if event == "slow.drag_move":
            self.log_event("budget.pointer_loop_exceeded", **slow_context)
        elif event == "slow.live_visuals":
            self.log_event("budget.refresh_exceeded", **slow_context)

    def target_context(
        self,
        target: PromptReorderDropTarget | None,
        *,
        prefix: str,
    ) -> dict[str, object]:
        """Return structural target fields for placement diagnostics."""

        context: dict[str, object] = {
            f"{prefix}_kind": reorder_drag_target_kind(target),
        }
        if isinstance(target, PromptLineDropTarget):
            context[f"{prefix}_row_index"] = target.row_index
            context[f"{prefix}_insertion_index"] = target.insertion_index
        elif isinstance(target, PromptGapBlankLineDropTarget):
            context[f"{prefix}_gap_index"] = target.gap_index
            context[f"{prefix}_blank_line_index"] = target.blank_line_index
        return context

    def style_context(
        self,
        style: PromptChipPaintStyle,
        *,
        prefix: str,
    ) -> dict[str, object]:
        """Return paint-style fields needed to diagnose transparent outlines."""

        return {
            f"{prefix}_outline_only": style.outline_only,
            f"{prefix}_outline_width": f"{style.outline_width:.2f}",
            f"{prefix}_opacity": f"{style.opacity:.2f}",
            **reorder_drag_color_context(style.fill_color, prefix=f"{prefix}_fill"),
            **reorder_drag_color_context(
                style.border_color,
                prefix=f"{prefix}_border",
            ),
        }

    def visual_context(
        self,
        visual: PromptChipVisual,
        *,
        prefix: str,
    ) -> dict[str, object]:
        """Return structural geometry fields for one painted chip visual."""

        return {
            f"{prefix}_bubble_count": len(visual.bubble_rects),
            **reorder_drag_rect_context(
                QRectF(visual.hotspot_rect),
                prefix=f"{prefix}_hotspot",
            ),
            **reorder_drag_rect_context(
                visual.fragment_union_rect,
                prefix=f"{prefix}_fragment_union",
            ),
            **reorder_drag_rect_context(
                reorder_visual_bubble_union_rect(visual.bubble_rects),
                prefix=f"{prefix}_chrome",
            ),
        }

    def held_shadow_context(
        self,
        held: PromptReorderHeldShadowTelemetry | None,
    ) -> dict[str, object]:
        """Return prompt-safe fields for cached held-chip shadow metrics."""

        if held is None:
            return {
                "held_shadow_chip_index": None,
                "held_shadow_origin": "none",
                "held_shadow_width": "0.00",
                "held_shadow_height": "0.00",
                "held_shadow_outline_width": "0.00",
                "held_shadow_outline_height": "0.00",
                "held_shadow_chrome_width": "0.00",
                "held_shadow_chrome_height": "0.00",
                "held_shadow_hotspot_width": "0.00",
                "held_shadow_hotspot_height": "0.00",
                "held_shadow_bubble_count": 0,
                "low_confidence_shadow_metrics": False,
            }
        return {
            "held_shadow_chip_index": held.chip_index,
            "held_shadow_origin": held.source,
            "held_shadow_width": f"{held.chrome_bounds.width():.2f}",
            "held_shadow_height": f"{held.chrome_bounds.height():.2f}",
            "held_shadow_outline_width": f"{held.chrome_bounds.width():.2f}",
            "held_shadow_outline_height": f"{held.chrome_bounds.height():.2f}",
            "held_shadow_chrome_width": f"{held.chrome_bounds.width():.2f}",
            "held_shadow_chrome_height": f"{held.chrome_bounds.height():.2f}",
            "held_shadow_hotspot_width": f"{held.hotspot_bounds.width():.2f}",
            "held_shadow_hotspot_height": f"{held.hotspot_bounds.height():.2f}",
            "held_shadow_bubble_count": len(held.normalized_bubble_rects),
            "low_confidence_shadow_metrics": held.low_confidence,
        }

    def target_visual_context(
        self,
        target_visual: PromptReorderTargetVisualTelemetry,
        *,
        prefix: str,
    ) -> dict[str, object]:
        """Return hit-zone and anchor-candidate fields for one target visual."""

        hit_rect = target_visual.hit_rect
        return {
            **reorder_drag_rect_context(hit_rect, prefix=f"{prefix}_hit"),
            f"{prefix}_anchor_left_x": f"{hit_rect.left():.2f}",
            f"{prefix}_anchor_center_x": f"{hit_rect.center().x():.2f}",
            f"{prefix}_anchor_right_x": f"{hit_rect.right():.2f}",
            f"{prefix}_anchor_center_y": f"{hit_rect.center().y():.2f}",
        }

    def visual_delta_context(
        self,
        expected_visual: PromptChipVisual,
        actual_visual: PromptChipVisual,
        *,
        prefix: str,
    ) -> dict[str, object]:
        """Return center and edge deltas between two projected chip visuals."""

        expected_rect = QRectF(expected_visual.hotspot_rect)
        actual_rect = QRectF(actual_visual.hotspot_rect)
        return {
            f"{prefix}_center_dx": (
                f"{actual_rect.center().x() - expected_rect.center().x():.2f}"
            ),
            f"{prefix}_center_dy": (
                f"{actual_rect.center().y() - expected_rect.center().y():.2f}"
            ),
            f"{prefix}_left_dx": f"{actual_rect.left() - expected_rect.left():.2f}",
            f"{prefix}_top_dy": f"{actual_rect.top() - expected_rect.top():.2f}",
            f"{prefix}_width_delta": (
                f"{actual_rect.width() - expected_rect.width():.2f}"
            ),
            f"{prefix}_height_delta": (
                f"{actual_rect.height() - expected_rect.height():.2f}"
            ),
        }

    @staticmethod
    def _is_prompt_safe_validation_error(error: ValueError) -> bool:
        """Return whether a ValueError came from prompt-safe validation."""

        message = str(error)
        return any(fragment in message for fragment in _VALIDATION_MESSAGE_FRAGMENTS)

    def _warn_validation_failure(
        self,
        event: str,
        context: Mapping[str, object],
        error: ValueError,
    ) -> None:
        """Log one coalesced warning without serializing rejected names."""

        field_fingerprints = tuple(
            sorted(
                self._prompt_safe_name_fingerprint(field_name) for field_name in context
            )
        )
        event_fingerprint = self._prompt_safe_name_fingerprint(event)
        warning_key = (event_fingerprint, field_fingerprints)
        if warning_key in self._reported_validation_failures:
            return
        self._reported_validation_failures.add(warning_key)
        log_warning(
            _LOGGER,
            "reorder.telemetry_validation_failed",
            telemetry_event_fingerprint=event_fingerprint,
            telemetry_event_length=len(event),
            telemetry_event_name_state=self._name_state(event),
            field_name_fingerprints=",".join(field_fingerprints),
            field_count=len(context),
            unsafe_field_name_count=sum(
                1 for field_name in context if self._name_state(field_name) == "unsafe"
            ),
            blank_field_name_count=sum(
                1 for field_name in context if self._name_state(field_name) == "blank"
            ),
            error_type=type(error).__name__,
        )

    @staticmethod
    def _prompt_safe_name_fingerprint(name: str) -> str:
        """Return a stable non-reversible diagnostic identity for one log name."""

        digest = hashlib.blake2s(name.encode("utf-8"), digest_size=8)
        return digest.hexdigest()

    @staticmethod
    def _name_state(name: str) -> str:
        """Classify one rejected log name without returning the name itself."""

        normalized = name.strip().lower().replace("-", "_")
        if not normalized:
            return "blank"
        if any(fragment in normalized for fragment in _FORBIDDEN_NAME_FRAGMENTS):
            return "unsafe"
        return "structural"


def reorder_visual_bubble_union_rect(rects: tuple[QRectF, ...]) -> QRectF:
    """Return the union covering one logical chip's visible bubble rects."""

    if not rects:
        return QRectF()
    union_rect = QRectF(rects[0])
    for rect in rects[1:]:
        union_rect = union_rect.united(rect)
    return union_rect


__all__ = [
    "PromptReorderHeldShadowTelemetry",
    "PromptReorderTargetVisualTelemetry",
    "PromptReorderTelemetry",
    "reorder_visual_bubble_union_rect",
]
