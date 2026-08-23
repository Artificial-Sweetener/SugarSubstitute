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

"""Mount weighted prompt editors and drive their observable interactions."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

from PySide6.QtCore import QPoint, QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QTextCursor, QWheelEvent
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptTokenWeightControls,
)
from tests.support.execution import immediate_prompt_task_executor_factory
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)
from tests.support.prompt_editor.projection_engine_support import (
    token_weight_controls_for,
    ensure_qapp,
    process_events,
    surface_for,
)
from tests.support.qt.lifecycle import destroy_widget_roots
from tests.support.qt.semantic_wait import wait_for_qt_condition


def effective_token_for_paint(
    surface: object,
    token: PromptProjectionToken,
) -> PromptProjectionToken:
    """Return the token with geometry-neutral paint state applied."""

    layout = cast(Any, surface)._layout
    return cast(
        PromptProjectionToken,
        layout.frame.paint_input.effective_token(token.token_id) or token,
    )


def widget_roots() -> Iterator[list[QWidget]]:
    """Track widgets created during one projection emphasis contract test."""

    created: list[QWidget] = []
    yield created
    destroy_widget_roots(created)


def set_cursor_position(box: PromptEditor, position: int) -> None:
    """Move the prompt-editor caret to one raw source position."""

    app = ensure_qapp()
    cursor = box.textCursor()
    cursor.setPosition(position, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    process_events(app)


def wait_for_hide_linger_timeout(controls: PromptTokenWeightControls) -> None:
    """Wait for the overlay-owned linger timer to report its semantic completion."""

    gestures = cast(Any, controls)._gestures
    timer = cast(QTimer, gestures.hide_timeout)
    timeout = QSignalSpy(timer.timeout)

    assert timeout.wait(timer.interval() + 1_000)


def emphasis_token_for(
    box: PromptEditor,
    *,
    index: int = 0,
) -> PromptProjectionToken:
    """Return one collapsed emphasis token from the live projection document."""

    surface = surface_for(box)
    tokens = [
        effective_token_for_paint(surface, token)
        for token in surface.projection_document().tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    ]
    assert len(tokens) > index
    return tokens[index]


def lora_token_for(
    box: PromptEditor,
    *,
    index: int = 0,
) -> PromptProjectionToken:
    """Return one collapsed LoRA token from the live projection document."""

    surface = surface_for(box)
    tokens = [
        effective_token_for_paint(surface, token)
        for token in surface.projection_document().tokens
        if token.kind is PromptProjectionTokenKind.LORA
    ]
    assert len(tokens) > index
    return tokens[index]


def show_lora_prompt_editor(
    widgets: list[QWidget],
    *,
    text: str,
    width: int,
    height: int = 340,
) -> PromptEditor:
    """Create, show, and populate one prompt editor with LoRA syntax enabled."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(max(240, width + 48), height)
    box = PromptEditor(
        host,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=prompt_syntax_profile("emphasis", "wildcard", "lora"),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    box.setGeometry(20, 20, width, box.minimumEditorHeight())
    host.show()
    host.activateWindow()
    box.show()
    box.setFocus()
    box.setPlainText(text)
    process_events(app)
    widgets.extend([host, box])
    return box


def token_rect_for(box: PromptEditor, token: PromptProjectionToken) -> QRectF:
    """Return the viewport-local rect occupied by one collapsed projection token."""

    token_rect = surface_for(  # noqa: SLF001
        box
    )._layout.frame.geometry.tokens.token_rect(
        token,
        scroll_offset=float(box.verticalScrollBar().value()),
    )
    assert token_rect is not None
    return token_rect


def anchor_rect_for(box: PromptEditor, token: PromptProjectionToken) -> QRectF:
    """Return the viewport-local anchor rect used by one emphasis token."""

    anchor_rect = surface_for(box).token_anchor_rect(token)
    assert anchor_rect is not None
    return anchor_rect


def weight_rect_for(box: PromptEditor, token: PromptProjectionToken) -> QRectF:
    """Return the viewport-local painted number rect used for exact weight editing."""

    weight_rect = surface_for(box).token_weight_text_rect(token)
    assert weight_rect is not None
    return weight_rect


def reveal_emphasis_controls(
    box: PromptEditor,
    token: PromptProjectionToken,
) -> PromptTokenWeightControls:
    """Reveal emphasis controls with a deterministic hover sequence."""

    controls = token_weight_controls_for(box)
    reset_point = QPoint(
        max(1, box.viewport().width() - 3), max(1, box.viewport().height() - 3)
    )
    QTest.mouseMove(box.viewport(), reset_point)
    QTest.mouseMove(box.viewport(), anchor_rect_for(box, token).center().toPoint())
    controls.refresh_geometry()
    wait_for_qt_condition(
        lambda: (
            (visible_token := controls.visible_token) is not None
            and visible_token.token_id == token.token_id
        )
    )
    return controls


def click_control_rect(overlay: QWidget, host_rect: QRectF) -> None:
    """Click the center of one host-local control rect."""

    app = ensure_qapp()
    local_point = overlay.mapFromParent(host_rect.center().toPoint())
    QTest.mouseClick(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        local_point,
    )
    process_events(app)


def start_exact_weight_edit(
    box: PromptEditor,
    token: PromptProjectionToken,
) -> PromptTokenWeightControls:
    """Start exact weight editing by double clicking the painted number only."""

    app = ensure_qapp()
    controls = token_weight_controls_for(box)
    if (
        controls.visible_token is not None
        and controls.visible_token.token_id == token.token_id
        and controls._weight_hit_rect is not None  # noqa: SLF001
    ):
        weight_point = controls.mapFromParent(
            controls._weight_hit_rect.center().toPoint()  # noqa: SLF001
        )
        click_target: QWidget = controls
    else:
        weight_point = weight_rect_for(box, token).center().toPoint()
        click_target = box.viewport()
    QTest.mouseClick(click_target, Qt.MouseButton.LeftButton, pos=weight_point)
    process_events(app, cycles=2)
    QTest.mouseClick(click_target, Qt.MouseButton.LeftButton, pos=weight_point)
    process_events(app, cycles=4)
    return controls


def exact_weight_edit_token(box: PromptEditor) -> PromptProjectionToken | None:
    """Return the projection-owned token currently carrying exact edit state."""

    return surface_for(box).exact_weight_edit_token()


def wheel_widget_at_point(
    widget: QWidget,
    *,
    local_point: QPoint,
    angle_delta_y: int,
) -> bool:
    """Send one wheel event to the supplied widget-local position."""

    app = ensure_qapp()
    global_point = widget.mapToGlobal(local_point)
    wheel_event = QWheelEvent(
        QPointF(local_point),
        QPointF(global_point),
        QPoint(0, 0),
        QPoint(0, angle_delta_y),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    QApplication.sendEvent(widget, wheel_event)
    process_events(app)
    return wheel_event.isAccepted()


def point_outside_token(box: PromptEditor, token: PromptProjectionToken) -> QPoint:
    """Return a same-row viewport point safely outside one rendered token."""

    token_rect = token_rect_for(box, token)
    return QPoint(
        min(box.viewport().width() - 4, int(token_rect.right()) + 80),
        int(token_rect.center().y()),
    )


def shell_viewport_for(box: PromptEditor) -> QWidget:
    """Return the outer prompt viewport that can receive first wheel events."""

    return cast(QWidget, getattr(box, "_shell_viewport")())
