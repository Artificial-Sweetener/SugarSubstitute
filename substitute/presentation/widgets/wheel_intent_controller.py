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

"""Install shared deliberate wheel-intent policy on editor widgets."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QElapsedTimer, QEvent, QObject, QPoint, QPointF
from PySide6.QtGui import QCursor, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.prompt_editor import PromptWheelAdjustmentMode
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.widgets.wheel_intent import (
    WheelIntentArbiter,
    WheelIntentTarget,
    WheelIntentTargetKind,
)
from substitute.presentation.widgets import DoubleSpinBox, SeedBox, SpinBox
from substitute.presentation.widgets.wheel_permission import set_wheel_intent_permission

if TYPE_CHECKING:
    from substitute.presentation.editor.prompt_editor.projection.model import (
        PromptProjectionToken,
    )


class WheelIntentController(QObject):
    """Install shared wheel-intent policy on editor-owned widgets."""

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        wheel_adjustment_mode: PromptWheelAdjustmentMode = (
            PromptWheelAdjustmentMode.HOVER_DWELL
        ),
    ) -> None:
        """Create the controller state used by configured widget subtrees."""

        super().__init__(parent)
        self._wheel_adjustment_mode = wheel_adjustment_mode
        self._wheel_intent_clock = QElapsedTimer()
        self._wheel_intent_clock.start()
        self._wheel_intent_arbiter = WheelIntentArbiter()
        self._prompt_weight_pointer_positions: dict[int, QPoint] = {}
        self._active_prompt_weight_targets: dict[int, WheelIntentTarget] = {}
        self._tracked_widgets: list[QWidget] = []

    def configure_widget(self, widget: QWidget) -> None:
        """Attach wheel-intent policy to wheel-capable controls under widget."""

        for tracked_widget in self._wheel_intent_tracking_widgets(widget):
            self._install_wheel_intent_tracking(tracked_widget)
        for wheel_widget in self._wheel_permission_widgets(widget):
            set_wheel_intent_permission(
                wheel_widget,
                self._allow_wheel_event_for_child,
            )
        for prompt_editor in self._prompt_wheel_widgets(widget):
            self._configure_prompt_token_wheel_intent(prompt_editor)

    def clear(self) -> None:
        """Clear transient wheel-intent hover, gesture, and token-pointer state."""

        self._wheel_intent_arbiter.clear_hover()
        self._wheel_intent_arbiter.clear_gesture()
        self._prompt_weight_pointer_positions.clear()
        self._active_prompt_weight_targets.clear()

    def set_wheel_adjustment_mode(
        self,
        mode: PromptWheelAdjustmentMode,
    ) -> None:
        """Apply the wheel adjustment mode and clear stale authorization."""

        if self._wheel_adjustment_mode is mode:
            return
        self._wheel_adjustment_mode = mode
        self.clear()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Record Qt pointer and focus events that affect wheel ownership."""

        if isinstance(watched, QWidget):
            if event.type() == QEvent.Type.MouseMove:
                self._record_wheel_intent_pointer_move(
                    watched,
                    cast(QMouseEvent, event),
                )
            elif event.type() == QEvent.Type.Enter:
                self._record_wheel_intent_pointer_enter(watched)
            elif event.type() == QEvent.Type.FocusIn:
                self._record_wheel_intent_focus_in(watched)
            elif event.type() == QEvent.Type.FocusOut:
                self._clear_wheel_intent_focus_for_widget(watched)
            elif event.type() == QEvent.Type.Leave:
                self._clear_wheel_intent_hover_for_widget(watched)
        return super().eventFilter(watched, event)

    def _wheel_intent_tracking_widgets(self, widget: QWidget) -> tuple[QWidget, ...]:
        """Return widgets whose pointer movement should arm wheel intent."""

        return self._unique_wheel_widgets(
            widget,
            include_prompt_editors=True,
        )

    def _install_wheel_intent_tracking(self, widget: QWidget) -> None:
        """Install pointer tracking once for one widget."""

        if any(tracked_widget is widget for tracked_widget in self._tracked_widgets):
            return
        self._tracked_widgets.append(widget)
        widget.setMouseTracking(True)
        widget.installEventFilter(self)

    def _wheel_permission_widgets(self, widget: QWidget) -> tuple[QWidget, ...]:
        """Return child widgets that ask the controller before consuming wheel."""

        return self._unique_wheel_widgets(
            widget,
            include_prompt_editors=True,
        )

    def _unique_wheel_widgets(
        self,
        widget: QWidget,
        *,
        include_prompt_editors: bool,
    ) -> tuple[QWidget, ...]:
        """Return deduplicated wheel-capable widgets contained by one subtree."""

        widgets: list[QWidget] = []
        direct_types = (
            (SpinBox, DoubleSpinBox, SeedBox, PromptEditor)
            if include_prompt_editors
            else (SpinBox, DoubleSpinBox, SeedBox)
        )
        if isinstance(widget, direct_types):
            widgets.append(widget)
        widgets.extend(widget.findChildren(SpinBox))
        widgets.extend(widget.findChildren(DoubleSpinBox))
        widgets.extend(widget.findChildren(SeedBox))
        if include_prompt_editors:
            widgets.extend(widget.findChildren(PromptEditor))
        unique_widgets: list[QWidget] = []
        seen_ids: set[int] = set()
        for candidate in widgets:
            candidate_id = id(candidate)
            if candidate_id in seen_ids:
                continue
            seen_ids.add(candidate_id)
            unique_widgets.append(candidate)
        return tuple(unique_widgets)

    def _prompt_wheel_widgets(self, widget: QWidget) -> tuple[PromptEditor, ...]:
        """Return prompt editors contained by one configured widget."""

        widgets: list[PromptEditor] = []
        if isinstance(widget, PromptEditor):
            widgets.append(widget)
        widgets.extend(widget.findChildren(PromptEditor))
        unique_widgets: list[PromptEditor] = []
        seen_ids: set[int] = set()
        for candidate in widgets:
            candidate_id = id(candidate)
            if candidate_id in seen_ids:
                continue
            seen_ids.add(candidate_id)
            unique_widgets.append(candidate)
        return tuple(unique_widgets)

    def _configure_prompt_token_wheel_intent(
        self,
        prompt_editor: PromptEditor,
    ) -> None:
        """Attach token-specific wheel intent callbacks to one prompt editor."""

        prompt_editor.set_wheel_intent_token_handlers(
            token_pointer_moved=lambda token, global_position: (
                self._record_prompt_weight_pointer_move(
                    prompt_editor,
                    token,
                    global_position,
                )
            ),
            token_wheel_ready=lambda token, global_position: (
                self._prompt_weight_token_is_ready(
                    prompt_editor,
                    token,
                    global_position,
                )
            ),
            token_wheel_allowed=lambda token, event: (
                self._allow_prompt_weight_wheel_event(
                    prompt_editor,
                    token,
                    event,
                )
            ),
            token_wheel_activated=lambda token, global_position: (
                self._record_prompt_weight_activation(
                    prompt_editor,
                    token,
                    global_position,
                )
            ),
        )

    def _allow_wheel_event_for_child(
        self,
        widget: QWidget,
        event: QWheelEvent,
    ) -> bool:
        """Return whether one child widget may consume a wheel event."""

        _ = event
        target = self._wheel_intent_target_for_widget(widget)
        if not target.can_arm():
            return False
        owner = self._wheel_intent_owner_for_widget(widget)
        if self._wheel_adjustment_mode is PromptWheelAdjustmentMode.FOCUS_REQUIRED:
            return owner is not None and self._owner_or_descendant_has_focus(owner)
        if isinstance(owner, PromptEditor) and owner.hasFocus():
            self._wheel_intent_arbiter.set_active_target(target)
        owner_target = self._wheel_intent_arbiter.wheel_owner_for_event(
            target=target,
            timestamp_ms=self._wheel_intent_now_ms(),
            target_can_accept_wheel=True,
        )
        return owner_target == target

    def _record_wheel_intent_pointer_move(
        self,
        widget: QWidget,
        event: QMouseEvent,
    ) -> None:
        """Record a real pointer move for wheel-intent dwell tracking."""

        self._record_wheel_intent_pointer_arrival(
            widget,
            event.globalPosition().toPoint(),
        )

    def _record_wheel_intent_pointer_enter(self, widget: QWidget) -> None:
        """Record pointer arrival when Qt sends Enter without MouseMove."""

        self._record_wheel_intent_pointer_arrival(widget, QCursor.pos())

    def _record_wheel_intent_pointer_arrival(
        self,
        widget: QWidget,
        global_position: QPoint,
    ) -> None:
        """Record a pointer position that can start dwell tracking."""

        owner = self._wheel_intent_owner_for_widget(widget)
        if self._wheel_adjustment_mode is PromptWheelAdjustmentMode.FOCUS_REQUIRED:
            return
        if isinstance(owner, PromptEditor) and self._prompt_weight_pointer_matches(
            owner,
            global_position,
        ):
            return
        target = self._wheel_intent_target_for_widget(widget)
        if not target.can_arm():
            self._wheel_intent_arbiter.clear_hover()
            return
        self._wheel_intent_arbiter.handle_pointer_move(
            global_position=global_position,
            target=target,
            timestamp_ms=self._wheel_intent_now_ms(),
        )

    def _record_wheel_intent_focus_in(self, widget: QWidget) -> None:
        """Record explicit focus intent for prompt-editor wheel ownership."""

        owner = self._wheel_intent_owner_for_widget(widget)
        if not isinstance(owner, PromptEditor):
            return
        self._wheel_intent_arbiter.set_active_target(
            self._wheel_intent_target_for_widget(owner)
        )

    def _clear_wheel_intent_focus_for_widget(self, widget: QWidget) -> None:
        """Clear explicit focus intent when a prompt editor loses focus."""

        owner = self._wheel_intent_owner_for_widget(widget)
        if not isinstance(owner, PromptEditor):
            return
        self._wheel_intent_arbiter.clear_active_target(
            self._wheel_intent_target_for_widget(owner)
        )
        self._active_prompt_weight_targets.pop(id(owner), None)

    def _clear_wheel_intent_hover_for_widget(self, widget: QWidget) -> None:
        """Clear hover dwell when the pointer leaves a tracked target."""

        owner = self._wheel_intent_owner_for_widget(widget)
        if isinstance(owner, PromptEditor) and id(owner) in (
            self._prompt_weight_pointer_positions
        ):
            return
        target = self._wheel_intent_target_for_widget(widget)
        armed = self._wheel_intent_arbiter.armed_target(
            timestamp_ms=self._wheel_intent_now_ms()
        )
        if armed is None or armed == target:
            self._wheel_intent_arbiter.clear_hover()

    def _wheel_intent_target_for_widget(self, widget: QWidget) -> WheelIntentTarget:
        """Return the wheel-intent target represented by one widget."""

        owner = self._wheel_intent_owner_for_widget(widget)
        if owner is None:
            return WheelIntentTarget.editor_scroll()
        if isinstance(owner, (SpinBox, DoubleSpinBox, SeedBox)):
            return WheelIntentTarget(
                kind=WheelIntentTargetKind.NUMERIC_ADJUSTMENT,
                widget=owner,
                identity=("numeric", id(owner)),
            )
        if isinstance(owner, PromptEditor):
            return WheelIntentTarget(
                kind=WheelIntentTargetKind.PROMPT_SCROLL,
                widget=owner,
                identity=("prompt", id(owner)),
            )
        return WheelIntentTarget.passive()

    def _wheel_intent_owner_for_widget(self, widget: QWidget) -> QWidget | None:
        """Return the nearest wheel-capable owner for one descendant widget."""

        current: QWidget | None = widget
        while current is not None:
            if isinstance(current, (SpinBox, DoubleSpinBox, SeedBox, PromptEditor)):
                return current
            current = current.parentWidget()
        return None

    def _owner_or_descendant_has_focus(self, owner: QWidget) -> bool:
        """Return whether one wheel owner or one of its descendants has focus."""

        focused_widget = QApplication.focusWidget()
        return focused_widget is owner or (
            focused_widget is not None and owner.isAncestorOf(focused_widget)
        )

    def _wheel_intent_now_ms(self) -> int:
        """Return the controller-local timestamp used for wheel intent policy."""

        return int(self._wheel_intent_clock.elapsed())

    def _record_prompt_weight_pointer_move(
        self,
        prompt_editor: PromptEditor,
        token: PromptProjectionToken,
        global_position: QPointF,
    ) -> None:
        """Record a real pointer move over one numeric prompt token."""

        if self._wheel_adjustment_mode is PromptWheelAdjustmentMode.FOCUS_REQUIRED:
            return
        point = global_position.toPoint()
        self._prompt_weight_pointer_positions[id(prompt_editor)] = QPoint(point)
        self._wheel_intent_arbiter.handle_pointer_move(
            global_position=point,
            target=self._prompt_weight_target(prompt_editor, token),
            timestamp_ms=self._wheel_intent_now_ms(),
        )

    def _prompt_weight_pointer_matches(
        self,
        prompt_editor: PromptEditor,
        global_position: QPoint,
    ) -> bool:
        """Return whether a prompt move duplicates token hover tracking."""

        token_position = self._prompt_weight_pointer_positions.get(id(prompt_editor))
        return token_position is not None and token_position == global_position

    def _prompt_weight_token_is_ready(
        self,
        prompt_editor: PromptEditor,
        token: PromptProjectionToken,
        global_position: QPointF,
    ) -> bool:
        """Return whether dwell has made one prompt token ready for wheel input."""

        _ = global_position
        if self._wheel_adjustment_mode is PromptWheelAdjustmentMode.FOCUS_REQUIRED:
            return self._active_prompt_weight_targets.get(
                id(prompt_editor)
            ) == self._prompt_weight_target(prompt_editor, token)
        return self._wheel_intent_arbiter.target_is_armed(
            self._prompt_weight_target(prompt_editor, token),
            timestamp_ms=self._wheel_intent_now_ms(),
        )

    def _allow_prompt_weight_wheel_event(
        self,
        prompt_editor: PromptEditor,
        token: PromptProjectionToken,
        event: QWheelEvent,
    ) -> bool:
        """Return whether one numeric prompt token may consume wheel input."""

        _ = event
        target = self._prompt_weight_target(prompt_editor, token)
        if self._wheel_adjustment_mode is PromptWheelAdjustmentMode.FOCUS_REQUIRED:
            return self._active_prompt_weight_targets.get(id(prompt_editor)) == target
        owner = self._wheel_intent_arbiter.wheel_owner_for_event(
            target=target,
            timestamp_ms=self._wheel_intent_now_ms(),
            target_can_accept_wheel=True,
        )
        return owner == target

    def _record_prompt_weight_activation(
        self,
        prompt_editor: PromptEditor,
        token: PromptProjectionToken,
        global_position: QPointF,
    ) -> None:
        """Record explicit click activation for one numeric prompt token."""

        _ = global_position
        if self._wheel_adjustment_mode is not PromptWheelAdjustmentMode.FOCUS_REQUIRED:
            return
        target = self._prompt_weight_target(prompt_editor, token)
        self._active_prompt_weight_targets[id(prompt_editor)] = target
        self._wheel_intent_arbiter.set_active_target(target)

    def _prompt_weight_target(
        self,
        prompt_editor: PromptEditor,
        token: PromptProjectionToken,
    ) -> WheelIntentTarget:
        """Return the wheel-intent target for one numeric prompt token."""

        return WheelIntentTarget(
            kind=WheelIntentTargetKind.PROMPT_WEIGHT_ADJUSTMENT,
            widget=prompt_editor,
            identity=(
                "prompt_weight",
                id(prompt_editor),
                prompt_editor.prompt_weight_wheel_identity(token),
            ),
        )


__all__ = ["WheelIntentController"]
