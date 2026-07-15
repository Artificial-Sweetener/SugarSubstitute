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

"""Tests for prompt interaction activity windows used by UI schedulers."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget
import pytest

from substitute.presentation.shell.prompt_interaction_activity import (
    PromptInteractionActivityTracker,
)


class PromptEditor(QWidget):
    """PromptEditor-named widget double for ancestor detection tests."""


class SegmentReorderOverlay(QWidget):
    """SegmentReorderOverlay-named widget double for ancestor detection tests."""


def test_prompt_interaction_activity_is_active_inside_configured_window() -> None:
    """Prompt interaction activity should stay active only inside its window."""

    now = 10.0
    tracker = PromptInteractionActivityTracker(
        active_window_ms=250,
        clock=lambda: now,
    )

    assert not tracker.is_prompt_interaction_active()
    assert tracker.ms_since_last_prompt_interaction() is None

    tracker.record_prompt_interaction()

    assert tracker.is_prompt_interaction_active()
    assert tracker.ms_since_last_prompt_interaction() == 0.0

    now = 10.2

    assert tracker.is_prompt_interaction_active()
    assert tracker.ms_since_last_prompt_interaction() == pytest.approx(200.0)

    now = 10.251

    assert not tracker.is_prompt_interaction_active()
    assert tracker.ms_since_last_prompt_interaction() == pytest.approx(251.0)


def test_repeated_prompt_interactions_extend_activity_window() -> None:
    """Repeated interactions should anchor the active window to the latest event."""

    now = 20.0
    tracker = PromptInteractionActivityTracker(
        active_window_ms=100,
        clock=lambda: now,
    )

    tracker.record_prompt_interaction()
    now = 20.08
    tracker.record_prompt_interaction()
    now = 20.15

    assert tracker.is_prompt_interaction_active()
    assert tracker.ms_since_last_prompt_interaction() == pytest.approx(70.0)

    now = 20.181

    assert not tracker.is_prompt_interaction_active()
    assert tracker.ms_since_last_prompt_interaction() == pytest.approx(101.0)


def test_keypress_under_prompt_editor_records_interaction() -> None:
    """Keypresses inside the prompt editor subtree should mark interaction active."""

    _app()
    now = 30.0
    tracker = PromptInteractionActivityTracker(clock=lambda: now)
    editor = PromptEditor()
    child = QWidget(editor)

    tracker.eventFilter(child, QEvent(QEvent.Type.KeyPress))

    assert tracker.is_prompt_interaction_active()


def test_mouse_drag_under_reorder_overlay_records_interaction() -> None:
    """Mouse moves with a held button inside reorder overlay should count as activity."""

    _app()
    now = 40.0
    tracker = PromptInteractionActivityTracker(clock=lambda: now)
    editor = PromptEditor()
    overlay = SegmentReorderOverlay(editor)

    tracker.eventFilter(
        overlay,
        QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(1.0, 1.0),
            QPointF(1.0, 1.0),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        ),
    )

    assert tracker.is_prompt_interaction_active()


def test_passive_mouse_move_does_not_record_interaction() -> None:
    """Passive hover should not keep generation and canvas work throttled."""

    _app()
    now = 50.0
    tracker = PromptInteractionActivityTracker(clock=lambda: now)
    editor = PromptEditor()

    tracker.eventFilter(
        editor,
        QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(1.0, 1.0),
            QPointF(1.0, 1.0),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        ),
    )

    assert not tracker.is_prompt_interaction_active()


def test_wheel_under_prompt_editor_records_interaction() -> None:
    """Wheel events in prompt editor should count because they can adjust tokens."""

    _app()
    now = 60.0
    tracker = PromptInteractionActivityTracker(clock=lambda: now)
    editor = PromptEditor()

    tracker.eventFilter(editor, QEvent(QEvent.Type.Wheel))

    assert tracker.is_prompt_interaction_active()


def _app() -> QApplication:
    """Return the active QApplication for widget-backed interaction tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])
