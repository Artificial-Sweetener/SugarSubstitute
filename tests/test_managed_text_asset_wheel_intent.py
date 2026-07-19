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

"""Wheel-intent coverage for managed text asset prompt editors."""

from __future__ import annotations

import os

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.prompt_editor import (
    wildcard_management_prompt_feature_profile,
)
from substitute.domain.prompt import PromptWheelAdjustmentMode
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.presentation.managed_text_assets import NumberedPromptEditorFrame
from substitute.presentation.editor.prompt_editor.runtime_services import (
    PromptEditorRuntimeServices,
)
from tests.prompt_autocomplete_test_helpers import EmptyPromptAutocompleteGateway
from tests.prompt_projection_test_helpers import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
    process_events,
    surface_for,
    token_weight_controls_for,
)
from tests.execution_test_helpers import immediate_prompt_task_executor_factory

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "managed prompt editor wheel tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def _frame(
    wheel_adjustment_mode: PromptWheelAdjustmentMode = (
        PromptWheelAdjustmentMode.HOVER_DWELL
    ),
) -> NumberedPromptEditorFrame:
    """Create a numbered prompt editor frame with wildcard-management features."""

    return NumberedPromptEditorFrame(
        prompt_runtime_services=PromptEditorRuntimeServices(
            autocomplete_gateway=EmptyPromptAutocompleteGateway(),
            wildcard_catalog_gateway=StaticPromptWildcardCatalogGateway({}),
            prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
        ),
        prompt_feature_profile=wildcard_management_prompt_feature_profile(),
        wheel_adjustment_mode=wheel_adjustment_mode,
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


def _first_emphasis_token(editor: PromptEditor) -> PromptProjectionToken:
    """Return the first emphasis token from a prompt editor."""

    for token in surface_for(editor).projection_document().tokens:
        if token.kind is PromptProjectionTokenKind.EMPHASIS:
            return token
    raise AssertionError("expected emphasis token")


def _first_numeric_wildcard_token(editor: PromptEditor) -> PromptProjectionToken:
    """Return the first numeric wildcard token from a prompt editor."""

    for token in surface_for(editor).projection_document().tokens:
        if token.kind is PromptProjectionTokenKind.WILDCARD:
            assert token.wildcard_can_step_tag is True
            return token
    raise AssertionError("expected numeric wildcard token")


def _reveal_numeric_token_controls(
    editor: PromptEditor,
    token: PromptProjectionToken,
) -> QPoint:
    """Reveal numeric token controls without waiting for wheel dwell."""

    app = ensure_qapp()
    controls = token_weight_controls_for(editor)
    token_rect = surface_for(editor).token_anchor_rect(token)
    assert token_rect is not None
    token_point = token_rect.center().toPoint()
    reset_point = QPoint(
        max(1, editor.viewport().width() - 3),
        max(1, editor.viewport().height() - 3),
    )
    QTest.mouseMove(editor.viewport(), reset_point)
    process_events(app, cycles=8)
    QTest.mouseMove(editor.viewport(), token_point)
    process_events(app, cycles=8)
    controls._set_pointer_from_viewport(QPointF(token_point))  # noqa: SLF001
    controls._record_wheel_intent_pointer_from_viewport(  # noqa: SLF001
        _hover_mouse_move(editor.viewport(), token_point)
    )
    controls.refresh_geometry()
    process_events(app, cycles=8)
    return token_point


def test_numbered_prompt_editor_emphasis_wheel_requires_dwell() -> None:
    """Managed prompt emphasis wheel edits should require token dwell."""

    app = ensure_qapp()
    frame = _frame()
    frame.resize(520, 300)
    frame.show()
    frame.setPlainText("(cat:1.20)")
    process_events(app, cycles=8)
    editor = frame.editor()
    token = _first_emphasis_token(editor)
    token_point = _reveal_numeric_token_controls(editor, token)

    premature_event = _wheel_event_at_viewport_point(
        editor.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(editor.viewport(), premature_event)
    process_events(app)

    assert frame.toPlainText() == "(cat:1.20)"
    assert not premature_event.isAccepted()

    QTest.qWait(450)
    process_events(app, cycles=8)
    allowed_event = _wheel_event_at_viewport_point(
        editor.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(editor.viewport(), allowed_event)
    process_events(app)

    assert frame.toPlainText() != "(cat:1.20)"
    assert allowed_event.isAccepted()

    frame.close()
    frame.deleteLater()
    process_events(app)


def test_numbered_prompt_editor_numeric_wildcard_wheel_requires_dwell() -> None:
    """Managed prompt numeric wildcard wheel edits should require token dwell."""

    app = ensure_qapp()
    frame = _frame()
    frame.resize(520, 300)
    frame.show()
    frame.setPlainText("{animal|2}")
    process_events(app, cycles=8)
    editor = frame.editor()
    token = _first_numeric_wildcard_token(editor)
    token_point = _reveal_numeric_token_controls(editor, token)

    premature_event = _wheel_event_at_viewport_point(
        editor.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(editor.viewport(), premature_event)
    process_events(app)

    assert frame.toPlainText() == "{animal|2}"
    assert not premature_event.isAccepted()

    QTest.qWait(450)
    process_events(app, cycles=8)
    allowed_event = _wheel_event_at_viewport_point(
        editor.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(editor.viewport(), allowed_event)
    process_events(app)

    assert frame.toPlainText() != "{animal|2}"
    assert allowed_event.isAccepted()

    frame.close()
    frame.deleteLater()
    process_events(app)


def test_numbered_prompt_editor_scroll_still_works_without_token_mutation() -> None:
    """Focused managed prompts should scroll without authorizing token wheel edits."""

    app = ensure_qapp()
    frame = _frame()
    frame.resize(520, 260)
    frame.show()
    frame.setPlainText(
        "(cat:1.20)\n" + "\n".join(f"line {index}" for index in range(35))
    )
    process_events(app, cycles=8)
    editor = frame.editor()
    token = _first_emphasis_token(editor)
    token_point = _reveal_numeric_token_controls(editor, token)
    editor.setFocus()
    process_events(app)
    scrollbar = editor.verticalScrollBar()
    scrollbar.setValue(0)

    focused_token_event = _wheel_event_at_viewport_point(
        editor.viewport(),
        token_point,
        angle_delta_y=-120,
    )
    QApplication.sendEvent(editor.viewport(), focused_token_event)
    process_events(app)

    assert frame.toPlainText().startswith("(cat:1.20)")
    assert scrollbar.value() > 0
    assert focused_token_event.isAccepted()

    frame.close()
    frame.deleteLater()
    process_events(app)


def test_numbered_prompt_editor_focus_required_blocks_hover_dwell_emphasis_wheel() -> (
    None
):
    """Managed prompt emphasis wheel edits should ignore dwell in focus-required mode."""

    app = ensure_qapp()
    frame = _frame(PromptWheelAdjustmentMode.FOCUS_REQUIRED)
    frame.resize(520, 300)
    frame.show()
    frame.setPlainText("(cat:1.20)")
    process_events(app, cycles=8)
    editor = frame.editor()
    token = _first_emphasis_token(editor)
    token_point = _reveal_numeric_token_controls(editor, token)

    QTest.qWait(450)
    process_events(app, cycles=8)
    blocked_event = _wheel_event_at_viewport_point(
        editor.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(editor.viewport(), blocked_event)
    process_events(app)

    assert frame.toPlainText() == "(cat:1.20)"
    assert not blocked_event.isAccepted()

    frame.close()
    frame.deleteLater()
    process_events(app)


def test_numbered_prompt_editor_focus_required_allows_clicked_emphasis_wheel() -> None:
    """Managed prompt emphasis wheel edits should work after token click activation."""

    app = ensure_qapp()
    frame = _frame(PromptWheelAdjustmentMode.FOCUS_REQUIRED)
    frame.resize(520, 300)
    frame.show()
    frame.setPlainText("(cat:1.20)")
    process_events(app, cycles=8)
    editor = frame.editor()
    token = _first_emphasis_token(editor)
    token_point = _reveal_numeric_token_controls(editor, token)

    editor.setFocus()
    process_events(app, cycles=4)
    QTest.mouseClick(
        editor.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        token_point,
    )
    process_events(app, cycles=8)
    allowed_event = _wheel_event_at_viewport_point(
        editor.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(editor.viewport(), allowed_event)
    process_events(app)

    assert frame.toPlainText() != "(cat:1.20)"
    assert allowed_event.isAccepted()

    frame.close()
    frame.deleteLater()
    process_events(app)


def test_numbered_prompt_editor_focus_required_allows_clicked_numeric_wildcard_wheel() -> (
    None
):
    """Managed prompt wildcard tag wheel edits should work after token click activation."""

    app = ensure_qapp()
    frame = _frame(PromptWheelAdjustmentMode.FOCUS_REQUIRED)
    frame.resize(520, 300)
    frame.show()
    frame.setPlainText("{animal|2}")
    process_events(app, cycles=8)
    editor = frame.editor()
    token = _first_numeric_wildcard_token(editor)
    token_point = _reveal_numeric_token_controls(editor, token)

    QTest.mouseClick(
        editor.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        token_point,
    )
    process_events(app)
    allowed_event = _wheel_event_at_viewport_point(
        editor.viewport(),
        token_point,
        angle_delta_y=120,
    )
    QApplication.sendEvent(editor.viewport(), allowed_event)
    process_events(app)

    assert frame.toPlainText() != "{animal|2}"
    assert allowed_event.isAccepted()

    frame.close()
    frame.deleteLater()
    process_events(app)
