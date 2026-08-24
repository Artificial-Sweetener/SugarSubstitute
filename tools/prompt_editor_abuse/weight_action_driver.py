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

"""Drive weighted prompt tokens through production pointer interaction owners."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


class PromptWeightActionDriver:
    """Own weighted-token pointer state and abuse action delivery."""

    def __init__(self) -> None:
        """Track editors whose first wheel action activated token focus."""

        self._wheel_activated_editor_ids: set[int] = set()

    def wheel(self, editor: object, direction: str) -> None:
        """Wheel the first weighted token through viewport pointer hit testing."""

        prompt_editor = cast(PromptEditor, editor)
        surface = cast(Any, prompt_editor)._surface
        token = _first_weighted_token(prompt_editor)
        weight_rect = surface.token_weight_text_rect(token)
        if weight_rect is None:
            raise RuntimeError("Prompt abuse wheel token has no visible geometry.")
        viewport = prompt_editor.viewport()
        local_position = weight_rect.center().toPoint()
        global_position = viewport.mapToGlobal(local_position)
        if id(prompt_editor) not in self._wheel_activated_editor_ids:
            QTest.mouseClick(
                viewport,
                Qt.MouseButton.LeftButton,
                pos=local_position,
                delay=0,
            )
            self._wheel_activated_editor_ids.add(id(prompt_editor))
        angle_delta = 120 if direction == "up" else -120
        event = QWheelEvent(
            QPointF(local_position),
            QPointF(global_position),
            QPoint(),
            QPoint(0, angle_delta),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        QApplication.sendEvent(viewport, event)
        if not event.isAccepted():
            raise RuntimeError("Prompt abuse weighted-token wheel was not accepted.")

    def step(self, editor: object, direction: str) -> None:
        """Click one pop-out weight arrow through the production overlay route."""

        prompt_editor = cast(PromptEditor, editor)
        token = _first_weighted_token(prompt_editor)
        controls = prompt_editor._token_weight_control_overlay
        _reveal_weight_controls(prompt_editor, token)
        control_rect = (
            controls.increase_rect if direction == "up" else controls.decrease_rect
        )
        if control_rect is None or not controls.isVisible():
            raise RuntimeError("Prompt abuse weight controls did not become visible.")
        QTest.mouseClick(
            controls,
            Qt.MouseButton.LeftButton,
            pos=controls.mapFromParent(control_rect.center().toPoint()),
            delay=0,
        )

    def edit_exact(self, editor: object, value: str) -> None:
        """Double-click and commit one exact weight through pointer routing."""

        prompt_editor = cast(PromptEditor, editor)
        token = _first_weighted_token(prompt_editor)
        surface = cast(Any, prompt_editor)._surface
        _reveal_weight_controls(prompt_editor, token)
        weight_rect = surface.token_weight_text_rect(token)
        if weight_rect is None:
            raise RuntimeError(
                "Prompt abuse exact-weight token has no visible geometry."
            )
        viewport = prompt_editor.viewport()
        global_position = viewport.mapToGlobal(weight_rect.center().toPoint())
        target = prompt_editor._token_weight_control_overlay
        QTest.mouseDClick(
            target,
            Qt.MouseButton.LeftButton,
            pos=target.mapFromGlobal(global_position),
            delay=0,
        )
        if not surface.exact_weight_edit_active():
            raise RuntimeError(
                "Prompt abuse exact-weight double click was not accepted."
            )
        key_target = QApplication.focusWidget() or surface
        QTest.keyClicks(key_target, value, delay=0)
        QTest.keyClick(key_target, Qt.Key.Key_Return, delay=0)


def _first_weighted_token(prompt_editor: PromptEditor) -> PromptProjectionToken:
    """Return the first projected emphasis or LoRA token."""

    surface = cast(Any, prompt_editor)._surface
    token = next(
        (
            candidate
            for candidate in surface.projection_document().tokens
            if candidate.kind.value in {"emphasis", "lora"}
        ),
        None,
    )
    if token is None:
        raise RuntimeError("Prompt abuse pointer action requires a weighted token.")
    return cast(PromptProjectionToken, token)


def _reveal_weight_controls(
    prompt_editor: PromptEditor,
    token: PromptProjectionToken,
) -> None:
    """Reveal token controls through real pointer routing and owner-state proof."""

    surface = cast(Any, prompt_editor)._surface
    anchor_rect = surface.token_anchor_rect(token)
    if anchor_rect is None:
        raise RuntimeError("Prompt abuse weighted token has no control anchor.")
    viewport = prompt_editor.viewport()
    controls = prompt_editor._token_weight_control_overlay
    reset_point = QPoint(
        max(1, viewport.width() - 3),
        max(1, viewport.height() - 3),
    )
    QTest.mouseMove(viewport, reset_point, delay=0)
    QTest.mouseMove(viewport, anchor_rect.center().toPoint(), delay=0)
    controls.refresh_geometry()

    def controls_are_visible() -> bool:
        """Return whether the requested token owns complete control geometry."""

        visible_token = controls.visible_token
        return bool(
            visible_token is not None
            and visible_token.token_id == token.token_id
            and controls.increase_rect is not None
            and controls.decrease_rect is not None
            and controls.isVisible()
        )

    wait_for_qt_condition(
        controls_are_visible,
        description="weighted-token controls to publish visible geometry",
        state=lambda: {
            "requested_token_id": token.token_id,
            "visible_token_id": (
                None
                if controls.visible_token is None
                else controls.visible_token.token_id
            ),
            "increase_rect": controls.increase_rect,
            "decrease_rect": controls.decrease_rect,
            "overlay_visible": controls.isVisible(),
            "viewport_visible": viewport.isVisible(),
        },
    )


__all__ = ["PromptWeightActionDriver"]
