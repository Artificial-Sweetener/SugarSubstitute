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

"""Cover complete prompt reorder autoscroll invalidation ownership."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF
from PySide6.QtWidgets import QApplication, QScrollBar, QWidget

from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
from substitute.presentation.editor.prompt_editor.interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_autoscroll import (
    PromptReorderAutoscrollOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_gesture_controller import (
    PromptReorderGestureController,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_telemetry import (
    PromptReorderTelemetry,
)


@pytest.fixture()
def widgets() -> Iterator[list[QWidget]]:
    """Track and dispose widgets created during one autoscroll test."""

    created: list[QWidget] = []
    yield created
    app = _ensure_qapp()
    for widget in reversed(created):
        widget.close()
        widget.deleteLater()
    app.processEvents()


class _Animation:
    """Record scroll-boundary animation settlement."""

    def __init__(self) -> None:
        """Initialize no settlement requests."""

        self.reasons: list[str] = []

    def settle(self, *, reason: str) -> None:
        """Record one settlement reason."""

        self.reasons.append(reason)


class _RefreshIdentity:
    """Count broad refresh invalidations."""

    def __init__(self) -> None:
        """Initialize no invalidations."""

        self.invalidation_count = 0

    def invalidate_refresh(self) -> None:
        """Record one scroll-driven invalidation."""

        self.invalidation_count += 1


class _PreviewEvents:
    """Count coalesced preview-layout notifications."""

    def __init__(self) -> None:
        """Initialize no notifications."""

        self.count = 0

    def emit_preview_layout_changed(self) -> None:
        """Record one preview-layout notification."""

        self.count += 1


class _TargetTransition:
    """Record pointer refreshes and optionally change the gesture target."""

    def __init__(
        self,
        gesture: PromptReorderGestureController,
        *,
        change_target: bool = False,
    ) -> None:
        """Store gesture authority and transition behavior."""

        self._gesture = gesture
        self._change_target = change_target
        self.positions: list[QPointF] = []
        self.emit_flags: list[bool] = []

    def update(
        self,
        local_pointer: QPointF,
        *,
        emit_preview_changed: bool = True,
    ) -> bool:
        """Record one refresh and apply the configured semantic change."""

        self.positions.append(QPointF(local_pointer))
        self.emit_flags.append(emit_preview_changed)
        if not self._change_target:
            return False
        self._gesture.set_active_drop_target(
            PromptLineDropTarget(row_index=0, insertion_index=1)
        )
        return True


class _GeometryRefresh:
    """Record broad geometry refresh requests."""

    def __init__(self) -> None:
        """Initialize no requests."""

        self.reasons: list[str] = []

    def __call__(self, *, reason: str) -> None:
        """Record one refresh reason."""

        self.reasons.append(reason)


def test_autoscroll_step_coalesces_without_synchronous_geometry_refresh(
    widgets: list[QWidget],
) -> None:
    """A moved tick should invalidate once without rebuilding geometry inline."""

    scrollbar, parent = _scrollbar(widgets, value=10)
    animation = _Animation()
    refresh_identity = _RefreshIdentity()
    preview_events = _PreviewEvents()
    geometry_refresh = _GeometryRefresh()
    owner = _owner(
        parent=parent,
        scrollbar=scrollbar,
        animation=animation,
        refresh_identity=refresh_identity,
        preview_events=preview_events,
        geometry_refresh=geometry_refresh,
    )

    owner.update_for_pointer(QPoint(50, 99))
    owner.apply_step_for_tests()

    assert scrollbar.value() == 34
    assert owner.counters()["autoscroll_pending_invalidation_count"] == 1
    assert animation.reasons == ["autoscroll_step"]
    assert refresh_identity.invalidation_count == 1
    assert preview_events.count == 1
    assert geometry_refresh.reasons == []


def test_autoscroll_flush_applies_latest_invalidation_and_target_refresh(
    widgets: list[QWidget],
) -> None:
    """One flush should consume the latest scroll and refresh the target once."""

    scrollbar, parent = _scrollbar(widgets, value=10)
    gesture = PromptReorderGestureController()
    animation = _Animation()
    geometry_refresh = _GeometryRefresh()
    transition = _TargetTransition(gesture, change_target=True)
    owner = _owner(
        parent=parent,
        scrollbar=scrollbar,
        gesture=gesture,
        animation=animation,
        geometry_refresh=geometry_refresh,
        target_transition=transition,
    )

    owner.update_for_pointer(QPoint(50, 99))
    owner.apply_step_for_tests()
    owner.apply_step_for_tests()

    assert owner.flush_pending_invalidation(reason="pointer_drop") is True
    assert owner.flush_pending_invalidation(reason="already_flushed") is False
    assert geometry_refresh.reasons == ["pointer_drop"]
    assert transition.positions == [QPointF(50, 99)]
    assert transition.emit_flags == [False]
    assert animation.reasons == [
        "autoscroll_step",
        "autoscroll_step",
        "autoscroll_flush:pointer_drop",
    ]
    counters = owner.counters()
    assert counters["autoscroll_schedule_count"] == 2
    assert counters["autoscroll_coalesced_count"] == 1
    assert counters["autoscroll_flush_count"] == 1
    assert counters["autoscroll_target_refresh_count"] == 1
    assert counters["autoscroll_pending_invalidation_count"] == 0


def test_autoscroll_noop_step_does_not_invalidate(
    widgets: list[QWidget],
) -> None:
    """A tick at the scrollbar boundary should remain entirely cheap."""

    scrollbar, parent = _scrollbar(widgets, value=100)
    animation = _Animation()
    refresh_identity = _RefreshIdentity()
    preview_events = _PreviewEvents()
    geometry_refresh = _GeometryRefresh()
    owner = _owner(
        parent=parent,
        scrollbar=scrollbar,
        animation=animation,
        refresh_identity=refresh_identity,
        preview_events=preview_events,
        geometry_refresh=geometry_refresh,
    )

    owner.update_for_pointer(QPoint(50, 99))
    owner.apply_step_for_tests()

    assert scrollbar.value() == 100
    assert owner.counters()["autoscroll_noop_step_count"] == 1
    assert owner.counters()["autoscroll_pending_invalidation_count"] == 0
    assert animation.reasons == []
    assert refresh_identity.invalidation_count == 0
    assert preview_events.count == 0
    assert geometry_refresh.reasons == []


def _owner(
    *,
    parent: QWidget,
    scrollbar: QScrollBar,
    gesture: PromptReorderGestureController | None = None,
    animation: _Animation | None = None,
    refresh_identity: _RefreshIdentity | None = None,
    preview_events: _PreviewEvents | None = None,
    geometry_refresh: _GeometryRefresh | None = None,
    target_transition: _TargetTransition | None = None,
) -> PromptReorderAutoscrollOwner:
    """Return one fully wired production autoscroll owner."""

    gesture = gesture or PromptReorderGestureController()
    animation = animation or _Animation()
    refresh_identity = refresh_identity or _RefreshIdentity()
    preview_events = preview_events or _PreviewEvents()
    geometry_refresh = geometry_refresh or _GeometryRefresh()
    target_transition = target_transition or _TargetTransition(gesture)
    metrics = PromptReorderInteractionMetricsOwner()
    return PromptReorderAutoscrollOwner(
        parent=parent,
        scrollbar_provider=lambda: scrollbar,
        overlay_height_provider=lambda: 100,
        map_global_to_overlay=lambda point: point,
        refresh_geometry=lambda reason: geometry_refresh(reason=reason),
        settle_animation=lambda reason: animation.settle(reason=reason),
        invalidate_refresh=refresh_identity.invalidate_refresh,
        gesture=gesture,
        update_target=lambda local_pointer, emit_preview_changed: (
            target_transition.update(
                local_pointer,
                emit_preview_changed=emit_preview_changed,
            )
        ),
        emit_preview_layout_changed=preview_events.emit_preview_layout_changed,
        metrics=metrics,
        diagnostics=PromptReorderInteractionDiagnosticsOwner(
            telemetry=PromptReorderTelemetry(),
            metrics=metrics,
        ),
    )


def _scrollbar(
    widgets: list[QWidget],
    *,
    value: int,
) -> tuple[QScrollBar, QWidget]:
    """Return one bounded scrollbar and tracked parent widget."""

    _ensure_qapp()
    parent = QWidget()
    scrollbar = QScrollBar(parent)
    scrollbar.setRange(0, 100)
    scrollbar.setValue(value)
    widgets.append(parent)
    return scrollbar, parent


def _ensure_qapp() -> QApplication:
    """Return a running Qt application for reorder autoscroll tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)
