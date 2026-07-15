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

"""Integration coverage for the shared wheel-intent controller."""

from __future__ import annotations

import os

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.domain.prompt import PromptWheelAdjustmentMode
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.presentation.widgets.wheel_intent_controller import (
    WheelIntentController,
)
from substitute.presentation.widgets import SpinBox
from tests.prompt_projection_test_helpers import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
    token_weight_controls_for,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "wheel intent controller Qt tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def _wheel_event(widget: QWidget, *, angle_delta_y: int) -> QWheelEvent:
    """Build one wheel event at the center of a widget."""

    local_point = widget.rect().center()
    return QWheelEvent(
        QPointF(local_point),
        QPointF(widget.mapToGlobal(local_point)),
        QPoint(0, 0),
        QPoint(0, angle_delta_y),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )


def _wheel_event_at_viewport_point(
    widget: QWidget,
    local_point: QPoint,
    *,
    angle_delta_y: int,
) -> QWheelEvent:
    """Build one wheel event at a specific viewport-local point."""

    return QWheelEvent(
        QPointF(local_point),
        QPointF(widget.mapToGlobal(local_point)),
        QPoint(0, 0),
        QPoint(0, angle_delta_y),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )


def _hover_mouse_move(widget: QWidget, local_point: QPoint) -> QMouseEvent:
    """Build one passive hover move event with no pressed buttons."""

    return QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(local_point),
        QPointF(widget.mapToGlobal(local_point)),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _first_numeric_token(box: PromptEditor) -> PromptProjectionToken:
    """Return the first prompt token that exposes numeric wheel controls."""

    for token in surface_for(box).projection_document().tokens:
        if token.kind in {
            PromptProjectionTokenKind.EMPHASIS,
            PromptProjectionTokenKind.LORA,
        }:
            return token
        if (
            token.kind is PromptProjectionTokenKind.WILDCARD
            and token.wildcard_can_step_tag
        ):
            return token
    raise AssertionError("expected numeric prompt token")


def _numeric_tokens(box: PromptEditor) -> tuple[PromptProjectionToken, ...]:
    """Return prompt tokens that expose numeric wheel controls."""

    return tuple(
        token
        for token in surface_for(box).projection_document().tokens
        if token.kind
        in {
            PromptProjectionTokenKind.EMPHASIS,
            PromptProjectionTokenKind.LORA,
        }
        or (
            token.kind is PromptProjectionTokenKind.WILDCARD
            and token.wildcard_can_step_tag
        )
    )


def _numeric_wildcard_token(box: PromptEditor) -> PromptProjectionToken:
    """Return the first numeric wildcard token from a prompt editor."""

    for token in surface_for(box).projection_document().tokens:
        if token.kind is PromptProjectionTokenKind.WILDCARD:
            assert token.wildcard_can_step_tag is True
            return token
    raise AssertionError("expected wildcard token")


def _reveal_numeric_token_controls(
    box: PromptEditor,
    token: PromptProjectionToken,
) -> QPoint:
    """Reveal numeric token controls without waiting for wheel dwell."""

    app = ensure_qapp()
    controls = token_weight_controls_for(box)
    token_rect = surface_for(box).token_anchor_rect(token)
    assert token_rect is not None
    token_point = token_rect.center().toPoint()
    reset_point = QPoint(
        max(1, box.viewport().width() - 3),
        max(1, box.viewport().height() - 3),
    )
    QTest.mouseMove(box.viewport(), reset_point)
    process_events(app, cycles=8)
    QTest.mouseMove(box.viewport(), token_point)
    process_events(app, cycles=8)
    controls._set_pointer_from_viewport(QPointF(token_point))  # noqa: SLF001
    controls._record_wheel_intent_pointer_from_viewport(  # noqa: SLF001
        _hover_mouse_move(box.viewport(), token_point)
    )
    controls.refresh_geometry()
    process_events(app, cycles=8)
    return token_point


def test_controller_gates_spinbox_wheel_until_dwell() -> None:
    """Configured spin boxes should only wheel-adjust after pointer dwell."""

    app = ensure_qapp()
    controller = WheelIntentController()
    spinbox = SpinBox()
    spinbox.setRange(0, 10)
    spinbox.setValue(5)
    controller.configure_widget(spinbox)
    spinbox.show()
    process_events(app)

    QApplication.sendEvent(
        spinbox,
        _hover_mouse_move(spinbox, spinbox.rect().center()),
    )
    process_events(app)
    premature_event = _wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, premature_event)
    process_events(app)

    assert spinbox.value() == 5
    assert not premature_event.isAccepted()

    QTest.qWait(450)
    process_events(app)
    allowed_event = _wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, allowed_event)
    process_events(app)

    assert spinbox.value() == 6
    assert allowed_event.isAccepted()

    spinbox.close()
    spinbox.deleteLater()
    controller.deleteLater()
    process_events(app)


def test_focus_required_spinbox_blocks_hover_dwell_wheel() -> None:
    """Focus-required mode should not let hover dwell authorize spin boxes."""

    app = ensure_qapp()
    controller = WheelIntentController(
        wheel_adjustment_mode=PromptWheelAdjustmentMode.FOCUS_REQUIRED
    )
    spinbox = SpinBox()
    blocker = QWidget()
    blocker.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    spinbox.setRange(0, 10)
    spinbox.setValue(5)
    controller.configure_widget(spinbox)
    spinbox.show()
    blocker.show()
    blocker.setFocus()
    process_events(app)

    QApplication.sendEvent(
        spinbox,
        _hover_mouse_move(spinbox, spinbox.rect().center()),
    )
    QTest.qWait(450)
    process_events(app)
    blocked_event = _wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, blocked_event)
    process_events(app)

    assert spinbox.value() == 5
    assert not blocked_event.isAccepted()

    blocker.close()
    blocker.deleteLater()
    spinbox.close()
    spinbox.deleteLater()
    controller.deleteLater()
    process_events(app)


def test_focus_required_spinbox_allows_focused_wheel() -> None:
    """Focus-required mode should allow focused spin boxes to wheel-adjust."""

    app = ensure_qapp()
    controller = WheelIntentController(
        wheel_adjustment_mode=PromptWheelAdjustmentMode.FOCUS_REQUIRED
    )
    spinbox = SpinBox()
    spinbox.setRange(0, 10)
    spinbox.setValue(5)
    controller.configure_widget(spinbox)
    spinbox.show()
    spinbox.setFocus()
    process_events(app)

    allowed_event = _wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, allowed_event)
    process_events(app)

    assert spinbox.value() == 6
    assert allowed_event.isAccepted()

    spinbox.close()
    spinbox.deleteLater()
    controller.deleteLater()
    process_events(app)


def test_switching_controller_mode_clears_stale_hover_authorization() -> None:
    """Changing to focus-required should drop existing hover authorization."""

    app = ensure_qapp()
    controller = WheelIntentController()
    spinbox = SpinBox()
    blocker = QWidget()
    blocker.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    spinbox.setRange(0, 10)
    spinbox.setValue(5)
    controller.configure_widget(spinbox)
    spinbox.show()
    blocker.show()
    blocker.setFocus()
    process_events(app)

    QApplication.sendEvent(
        spinbox,
        _hover_mouse_move(spinbox, spinbox.rect().center()),
    )
    QTest.qWait(450)
    process_events(app)

    controller.set_wheel_adjustment_mode(PromptWheelAdjustmentMode.FOCUS_REQUIRED)
    blocked_event = _wheel_event(spinbox, angle_delta_y=120)
    QApplication.sendEvent(spinbox, blocked_event)
    process_events(app)

    assert spinbox.value() == 5
    assert not blocked_event.isAccepted()

    blocker.close()
    blocker.deleteLater()
    spinbox.close()
    spinbox.deleteLater()
    controller.deleteLater()
    process_events(app)


def test_controller_gates_prompt_weight_wheel_until_dwell() -> None:
    """Configured prompt emphasis wheel edits should require token dwell."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    controller = WheelIntentController()
    box = show_prompt_editor(widgets, text="(cat:1.20)", width=320)
    controller.configure_widget(box)
    token = _first_numeric_token(box)
    token_point = _reveal_numeric_token_controls(box, token)

    premature_event = _wheel_event_at_viewport_point(
        box.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(box.viewport(), premature_event)
    process_events(app)

    assert box.toPlainText() == "(cat:1.20)"
    assert not premature_event.isAccepted()

    QTest.qWait(450)
    process_events(app, cycles=8)
    allowed_event = _wheel_event_at_viewport_point(
        box.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(box.viewport(), allowed_event)
    process_events(app)

    assert box.toPlainText() != "(cat:1.20)"
    assert allowed_event.isAccepted()

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    controller.deleteLater()
    process_events(app)


def test_focus_required_prompt_scroll_requires_focus() -> None:
    """Focus-required mode should only allow prompt scrolling after focus."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    controller = WheelIntentController(
        wheel_adjustment_mode=PromptWheelAdjustmentMode.FOCUS_REQUIRED
    )
    blocker = QWidget()
    blocker.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    box = show_prompt_editor(
        widgets,
        text="\n".join(f"line {index}" for index in range(30)),
        width=320,
    )
    controller.configure_widget(box)
    blocker.show()
    blocker.setFocus()
    process_events(app)
    scrollbar = box.verticalScrollBar()
    scrollbar.setValue(0)

    blocked_event = _wheel_event(box.viewport(), angle_delta_y=-120)
    QApplication.sendEvent(box.viewport(), blocked_event)
    process_events(app)

    assert scrollbar.value() == 0
    assert not blocked_event.isAccepted()

    box.window().activateWindow()
    box.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
    process_events(app)
    allowed_event = _wheel_event(box.viewport(), angle_delta_y=-120)
    QApplication.sendEvent(box.viewport(), allowed_event)
    process_events(app)

    assert scrollbar.value() > 0
    assert allowed_event.isAccepted()

    blocker.close()
    blocker.deleteLater()
    for widget in widgets:
        widget.close()
        widget.deleteLater()
    controller.deleteLater()
    process_events(app)


def test_focus_required_prompt_weight_blocks_hover_dwell_wheel() -> None:
    """Focus-required mode should ignore token hover dwell for wheel edits."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    controller = WheelIntentController(
        wheel_adjustment_mode=PromptWheelAdjustmentMode.FOCUS_REQUIRED
    )
    box = show_prompt_editor(widgets, text="(cat:1.20)", width=320)
    controller.configure_widget(box)
    token = _first_numeric_token(box)
    token_point = _reveal_numeric_token_controls(box, token)

    QTest.qWait(450)
    process_events(app, cycles=8)
    blocked_event = _wheel_event_at_viewport_point(
        box.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(box.viewport(), blocked_event)
    process_events(app)

    assert box.toPlainText() == "(cat:1.20)"
    assert not blocked_event.isAccepted()

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    controller.deleteLater()
    process_events(app)


def test_focus_required_prompt_weight_allows_after_token_click() -> None:
    """Focus-required mode should wheel-adjust a clicked weighted token."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    controller = WheelIntentController(
        wheel_adjustment_mode=PromptWheelAdjustmentMode.FOCUS_REQUIRED
    )
    box = show_prompt_editor(widgets, text="(cat:1.20)", width=320)
    controller.configure_widget(box)
    token = _first_numeric_token(box)
    token_point = _reveal_numeric_token_controls(box, token)

    QTest.mouseClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        token_point,
    )
    process_events(app)
    allowed_event = _wheel_event_at_viewport_point(
        box.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(box.viewport(), allowed_event)
    process_events(app)

    assert box.toPlainText() != "(cat:1.20)"
    assert allowed_event.isAccepted()

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    controller.deleteLater()
    process_events(app)


def test_focus_required_numeric_wildcard_allows_after_token_click() -> None:
    """Focus-required mode should wheel-adjust a clicked wildcard tag."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    controller = WheelIntentController(
        wheel_adjustment_mode=PromptWheelAdjustmentMode.FOCUS_REQUIRED
    )
    box = show_prompt_editor(widgets, text="{animal|2}", width=320)
    controller.configure_widget(box)
    token = _numeric_wildcard_token(box)
    token_point = _reveal_numeric_token_controls(box, token)

    QTest.mouseClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        token_point,
    )
    process_events(app)
    allowed_event = _wheel_event_at_viewport_point(
        box.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(box.viewport(), allowed_event)
    process_events(app)

    assert box.toPlainText() != "{animal|2}"
    assert allowed_event.isAccepted()

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    controller.deleteLater()
    process_events(app)


def test_focus_required_token_click_does_not_authorize_other_token() -> None:
    """Click activation should only authorize the clicked token target."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    controller = WheelIntentController(
        wheel_adjustment_mode=PromptWheelAdjustmentMode.FOCUS_REQUIRED
    )
    original_text = "(cat:1.20) (dog:1.30)"
    box = show_prompt_editor(widgets, text=original_text, width=420)
    controller.configure_widget(box)
    first_token, second_token = _numeric_tokens(box)
    first_point = _reveal_numeric_token_controls(box, first_token)
    second_rect = surface_for(box).token_anchor_rect(second_token)
    assert second_rect is not None
    second_point = second_rect.center().toPoint()

    QTest.mouseClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        first_point,
    )
    process_events(app)
    blocked_event = _wheel_event_at_viewport_point(
        box.viewport(),
        second_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(box.viewport(), blocked_event)
    process_events(app)

    assert box.toPlainText() == original_text

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    controller.deleteLater()
    process_events(app)


def test_controller_gates_numeric_wildcard_tag_until_dwell() -> None:
    """Configured prompt wildcard tag wheel edits should require token dwell."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    controller = WheelIntentController()
    box = show_prompt_editor(widgets, text="{animal|2}", width=320)
    controller.configure_widget(box)
    token = _numeric_wildcard_token(box)
    token_point = _reveal_numeric_token_controls(box, token)

    premature_event = _wheel_event_at_viewport_point(
        box.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(box.viewport(), premature_event)
    process_events(app)

    assert box.toPlainText() == "{animal|2}"
    assert not premature_event.isAccepted()

    QTest.qWait(450)
    process_events(app, cycles=8)
    allowed_event = _wheel_event_at_viewport_point(
        box.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(box.viewport(), allowed_event)
    process_events(app)

    assert box.toPlainText() != "{animal|2}"
    assert allowed_event.isAccepted()

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    controller.deleteLater()
    process_events(app)


def test_controller_preserves_focused_prompt_scroll_intent() -> None:
    """Focused prompt editors should scroll without hover dwell."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    controller = WheelIntentController()
    box = show_prompt_editor(
        widgets,
        text="\n".join(f"line {index}" for index in range(30)),
        width=320,
    )
    controller.configure_widget(box)
    box.setFocus()
    process_events(app)
    scrollbar = box.verticalScrollBar()
    scrollbar.setValue(0)

    focused_event = _wheel_event(box.viewport(), angle_delta_y=-120)
    QApplication.sendEvent(box.viewport(), focused_event)
    process_events(app)

    assert scrollbar.value() > 0
    assert focused_event.isAccepted()

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    controller.deleteLater()
    process_events(app)


def test_controller_focused_prompt_scroll_does_not_authorize_token_wheel_edit() -> None:
    """Focused prompt scrolling should not bypass token-specific wheel dwell."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    controller = WheelIntentController()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.20)\n" + "\n".join(f"line {index}" for index in range(30)),
        width=320,
    )
    controller.configure_widget(box)
    token = _first_numeric_token(box)
    token_point = _reveal_numeric_token_controls(box, token)
    box.setFocus()
    process_events(app)
    scrollbar = box.verticalScrollBar()
    scrollbar.setValue(0)

    focused_token_event = _wheel_event_at_viewport_point(
        box.viewport(),
        token_point,
        angle_delta_y=-120,
    )
    QApplication.sendEvent(box.viewport(), focused_token_event)
    process_events(app)

    assert box.toPlainText().startswith("(cat:1.20)")
    assert scrollbar.value() > 0
    assert focused_token_event.isAccepted()

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    controller.deleteLater()
    process_events(app)


def test_controller_token_tracking_survives_prompt_scroll_tracking_for_same_move() -> (
    None
):
    """Prompt-scroll tracking should not overwrite token hover ownership."""

    app = ensure_qapp()
    widgets: list[QWidget] = []
    controller = WheelIntentController()
    box = show_prompt_editor(widgets, text="(cat:1.20)", width=320)
    controller.configure_widget(box)
    token = _first_numeric_token(box)
    token_rect = surface_for(box).token_anchor_rect(token)
    assert token_rect is not None
    global_point = box.viewport().mapToGlobal(token_rect.center().toPoint())
    token_target = controller._prompt_weight_target(box, token)  # noqa: SLF001

    controller._record_prompt_weight_pointer_move(  # noqa: SLF001
        box,
        token,
        QPointF(global_point),
    )
    controller._record_wheel_intent_pointer_move(  # noqa: SLF001
        box,
        _hover_mouse_move(box, box.mapFromGlobal(global_point)),
    )
    controller._clear_wheel_intent_hover_for_widget(box)  # noqa: SLF001
    owner = controller._wheel_intent_arbiter.wheel_owner_for_event(  # noqa: SLF001
        target=token_target,
        timestamp_ms=controller._wheel_intent_now_ms() + 400,  # noqa: SLF001
        target_can_accept_wheel=True,
    )

    assert owner == token_target

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    controller.deleteLater()
    process_events(app)
