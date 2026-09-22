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

"""Verify prompt-editor host event precedence independently of the shell."""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, Qt
from PySide6.QtGui import QContextMenuEvent, QFocusEvent, QKeyEvent, QMouseEvent

from substitute.presentation.editor.prompt_editor.host_event_router import (
    PromptEditorHostEventBindings,
    PromptEditorHostEventRouter,
)


@dataclass(slots=True)
class _Recorder:
    """Record observable event-routing outcomes."""

    calls: list[str] = field(default_factory=list)
    chrome_result: bool | None = None
    context_result: bool = True

    def focus_in(self) -> None:
        """Record surface focus entry."""

        self.calls.append("focus_in")

    def focus_out(self, reason: Qt.FocusReason) -> None:
        """Record surface focus departure."""

        self.calls.append(f"focus_out:{reason.name}")

    def key_press(self, _event: QKeyEvent) -> None:
        """Record a surface key press."""

        self.calls.append("key_press")

    def key_release(self, _event: QKeyEvent) -> None:
        """Record a surface key release."""

        self.calls.append("key_release")

    def chrome(self, _watched: QObject, _event: QEvent) -> bool | None:
        """Record chrome routing and return its configured decision."""

        self.calls.append("chrome")
        return self.chrome_result

    def context_press(self) -> None:
        """Record a right-button context-menu press."""

        self.calls.append("context_press")

    def context_menu(self, _event: QContextMenuEvent) -> bool:
        """Record context-menu forwarding."""

        self.calls.append("context_menu")
        return self.context_result


def test_surface_keyboard_events_precede_chrome_routing() -> None:
    """Projection keyboard events are consumed without entering chrome policy."""

    router, recorder, surface, _, _ = _router()

    result = router.route(
        surface,
        QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_A,
            Qt.KeyboardModifier.NoModifier,
            "a",
        ),
    )

    assert result is True
    assert recorder.calls == ["key_press"]


def test_surface_focus_events_publish_then_continue_to_qt() -> None:
    """Projection focus publication returns false without chrome duplication."""

    router, recorder, surface, _, _ = _router()

    result = router.route(
        surface,
        QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.TabFocusReason),
    )

    assert result is False
    assert recorder.calls == ["focus_out:TabFocusReason"]


def test_chrome_decision_precedes_context_menu_routing() -> None:
    """A decisive chrome result prevents duplicate viewport handling."""

    router, recorder, _, shell_viewport, _ = _router(chrome_result=True)

    result = router.route(
        shell_viewport,
        QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint()),
    )

    assert result is True
    assert recorder.calls == ["chrome"]


def test_viewport_context_gesture_records_press_then_forwards_menu() -> None:
    """Right press state is captured before the later context-menu event."""

    router, recorder, _, _, content_viewport = _router()
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(),
        Qt.MouseButton.RightButton,
        Qt.MouseButton.RightButton,
        Qt.KeyboardModifier.NoModifier,
    )

    assert router.route(content_viewport, press) is None
    result = router.route(
        content_viewport,
        QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint()),
    )

    assert result is True
    assert recorder.calls == [
        "chrome",
        "context_press",
        "chrome",
        "context_menu",
    ]


def _router(
    *,
    chrome_result: bool | None = None,
) -> tuple[PromptEditorHostEventRouter, _Recorder, QObject, QObject, QObject]:
    """Build one router with distinct watched objects and recording callbacks."""

    recorder = _Recorder(chrome_result=chrome_result)
    surface = QObject()
    shell_viewport = QObject()
    content_viewport = QObject()
    return (
        PromptEditorHostEventRouter(
            PromptEditorHostEventBindings(
                surface=surface,
                shell_viewport=shell_viewport,
                content_viewport=content_viewport,
                handle_focus_in=recorder.focus_in,
                schedule_focus_out_cleanup=recorder.focus_out,
                handle_key_press=recorder.key_press,
                handle_key_release=recorder.key_release,
                handle_chrome_event=recorder.chrome,
                record_context_menu_press=recorder.context_press,
                forward_context_menu=recorder.context_menu,
            )
        ),
        recorder,
        surface,
        shell_viewport,
        content_viewport,
    )
