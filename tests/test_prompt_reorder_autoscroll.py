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

"""Tests for prompt reorder autoscroll timer and invalidation ownership."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QScrollBar, QWidget

from substitute.presentation.editor.prompt_editor.overlays.reorder_autoscroll import (
    PromptReorderAutoscrollContext,
    PromptReorderAutoscrollController,
    PromptReorderAutoscrollInvalidation,
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


def _ensure_qapp() -> QApplication:
    """Return a running Qt application for reorder autoscroll tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_autoscroll_step_emits_scroll_invalidation(
    widgets: list[QWidget],
) -> None:
    """A moved autoscroll tick should emit invalidation instead of preview work."""

    _ensure_qapp()
    parent = QWidget()
    scrollbar = QScrollBar(parent)
    scrollbar.setRange(0, 100)
    scrollbar.setValue(10)
    widgets.append(parent)
    invalidations: list[PromptReorderAutoscrollInvalidation] = []
    controller = PromptReorderAutoscrollController(
        parent=parent,
        scrollbar_provider=lambda: scrollbar,
        overlay_height_provider=lambda: 100,
        map_global_to_overlay=lambda point: point,
        step_callback=invalidations.append,
        context_provider=lambda: PromptReorderAutoscrollContext(
            gesture_id=1,
            event_id=2,
        ),
    )

    controller.update_for_pointer(QPoint(50, 99))
    controller.apply_step_for_tests()

    assert scrollbar.value() == 34
    assert len(invalidations) == 1
    invalidation = invalidations[0]
    assert invalidation.global_position == QPoint(50, 99)
    assert invalidation.direction == 1
    assert invalidation.previous_scroll_position == 10
    assert invalidation.next_scroll_position == 34
    assert invalidation.invalidation_index == 1


def test_autoscroll_noop_step_does_not_emit_invalidation(
    widgets: list[QWidget],
) -> None:
    """A tick at the scrollbar boundary should not invalidate geometry."""

    _ensure_qapp()
    parent = QWidget()
    scrollbar = QScrollBar(parent)
    scrollbar.setRange(0, 100)
    scrollbar.setValue(100)
    widgets.append(parent)
    invalidations: list[PromptReorderAutoscrollInvalidation] = []
    controller = PromptReorderAutoscrollController(
        parent=parent,
        scrollbar_provider=lambda: scrollbar,
        overlay_height_provider=lambda: 100,
        map_global_to_overlay=lambda point: point,
        step_callback=invalidations.append,
        context_provider=lambda: PromptReorderAutoscrollContext(
            gesture_id=None,
            event_id=None,
        ),
    )

    controller.update_for_pointer(QPoint(50, 99))
    controller.apply_step_for_tests()

    assert scrollbar.value() == 100
    assert invalidations == []
    assert controller.counters()["autoscroll_noop_step_count"] == 1
