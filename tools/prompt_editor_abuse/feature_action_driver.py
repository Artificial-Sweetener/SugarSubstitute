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

"""Invoke diagnostics, picker, and context-menu prompt abuse features."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QCoreApplication, QPointF, Qt
from PySide6.QtGui import QAction, QContextMenuEvent, QMouseEvent
from PySide6.QtWidgets import QWidget
from qfluentwidgets.components.widgets.menu import (  # type: ignore[import-untyped]
    RoundMenu,
)

from .models import PromptAbuseAction
from .source_action_driver import PromptAbuseSourceActionDriver


class PromptAbuseFeatureActionDriver:
    """Own feature invocation and feature-specific observable checkpoints."""

    def __init__(self, *, source_actions: PromptAbuseSourceActionDriver) -> None:
        """Bind context-menu pointer mapping to the source action owner."""

        self._source_actions = source_actions
        self._last_context_actions: tuple[QAction, ...] = ()
        self._last_context_menu_labels: tuple[str, ...] = ()

    def refresh_diagnostics(self, editor: object) -> None:
        """Refresh diagnostics through the production feature controller."""

        cast(Any, editor)._runtime.core.diagnostics.refresh_now()

    def open_lora_picker(self, editor: object) -> None:
        """Open the production LoRA picker and require a visible populated popup."""

        presenter = cast(Any, editor)._lora_picker_popup_presenter
        presenter.open_lora_picker()
        popup = presenter._popup
        if popup is None or not popup.isVisible():
            raise RuntimeError("Prompt abuse LoRA picker did not become visible.")
        snapshot = presenter._data_source.lora_picker_snapshot
        if not snapshot.consumable or not snapshot.items:
            raise RuntimeError("Prompt abuse LoRA picker has no consumable rows.")

    def activate_first_lora_picker_item(self, editor: object) -> None:
        """Activate the first real picker row through its production signal."""

        presenter = cast(Any, editor)._lora_picker_popup_presenter
        popup = presenter._popup
        if popup is None or not popup.isVisible():
            raise RuntimeError("Prompt abuse LoRA picker activation requires a popup.")
        snapshot = presenter._data_source.lora_picker_snapshot
        if not snapshot.items:
            raise RuntimeError("Prompt abuse LoRA picker activation has no row.")
        popup.loraActivated.emit(snapshot.items[0])

    def open_context_menu(self, editor: object, position: int) -> None:
        """Right-click one source boundary and capture the real headless menu."""

        self._dispatch_context_menu(editor, position, trigger_label=None)

    def trigger_context_menu_action(
        self,
        editor: object,
        position: int,
        action_label: str,
    ) -> None:
        """Trigger one exact action from the production-built headless menu."""

        self._dispatch_context_menu(editor, position, trigger_label=action_label)

    def trigger_cached_context_menu_action(self, action_label: str) -> None:
        """Activate one exact row from the most recently captured menu."""

        matching_action = next(
            (
                action
                for action in self._last_context_actions
                if action.text() == action_label
                or action.property("promptFullTriggerWordsLabel") == action_label
            ),
            None,
        )
        if matching_action is None:
            raise RuntimeError(
                f"Missing cached prompt abuse context-menu action {action_label!r}."
            )
        matching_action.trigger()

    def checkpoint_mismatch(self, action: PromptAbuseAction) -> str | None:
        """Return a context-menu mismatch for the action's prepared checkpoint."""

        if action.expected_context_labels is None:
            return None
        missing_labels = tuple(
            label
            for label in action.expected_context_labels
            if label not in self._last_context_menu_labels
        )
        if not missing_labels:
            return None
        return (
            f"context_menu:missing={missing_labels!r}:"
            f"actual={self._last_context_menu_labels!r}"
        )

    def _dispatch_context_menu(
        self,
        editor: object,
        position: int,
        *,
        trigger_label: str | None,
    ) -> None:
        """Build one production menu and optionally activate an exact row."""

        prompt_editor = cast(Any, editor)
        viewport = cast(QWidget, prompt_editor.viewport())
        local_position = self._source_actions.viewport_point_for_source_position(
            prompt_editor, position
        )
        global_position = viewport.mapToGlobal(local_position)
        labels: list[str] = []
        triggered = False
        round_menu_class = cast(Any, RoundMenu)
        original_exec = round_menu_class.exec

        def capture_menu(menu: object, *_args: object, **_kwargs: object) -> None:
            """Capture menu rows without opening a native popup."""

            nonlocal triggered
            _populate_lazy_submenus(menu)
            labels.extend(_menu_action_labels(menu))
            self._last_context_actions = _menu_actions(menu)
            if trigger_label is None:
                return
            matching_action = next(
                (
                    action
                    for action in _menu_actions(menu)
                    if action.text() == trigger_label
                    or action.property("promptFullTriggerWordsLabel") == trigger_label
                ),
                None,
            )
            if matching_action is not None:
                matching_action.trigger()
                triggered = True

        round_menu_class.exec = capture_menu
        try:
            press_event = QMouseEvent(
                QMouseEvent.Type.MouseButtonPress,
                QPointF(local_position),
                QPointF(global_position),
                Qt.MouseButton.RightButton,
                Qt.MouseButton.RightButton,
                Qt.KeyboardModifier.NoModifier,
            )
            QCoreApplication.sendEvent(viewport, press_event)
            context_event = QContextMenuEvent(
                QContextMenuEvent.Reason.Mouse,
                local_position,
                global_position,
            )
            QCoreApplication.sendEvent(viewport, context_event)
        finally:
            round_menu_class.exec = original_exec
        self._last_context_menu_labels = tuple(labels)
        if trigger_label is not None and not triggered:
            raise RuntimeError(
                f"Missing prompt abuse context-menu action {trigger_label!r}."
            )


def _menu_action_labels(menu: object) -> tuple[str, ...]:
    """Return top-level and nested labels from one rendered QFluent menu."""

    labels: list[str] = []
    actions = getattr(menu, "menuActions", None)
    if callable(actions):
        labels.extend(
            action.text() for action in actions() if isinstance(action, QAction)
        )
    for submenu in getattr(menu, "_subMenus", ()):
        labels.extend(_menu_action_labels(submenu))
    return tuple(labels)


def _populate_lazy_submenus(menu: object) -> None:
    """Populate renderer-owned lazy submenus before measuring their actions."""

    for submenu in getattr(menu, "_subMenus", ()):
        populate = getattr(submenu, "populate_if_needed", None)
        if callable(populate):
            populate()


def _menu_actions(menu: object) -> tuple[QAction, ...]:
    """Return every triggerable action from one rendered QFluent menu tree."""

    result: list[QAction] = []
    actions = getattr(menu, "menuActions", None)
    if callable(actions):
        result.extend(action for action in actions() if isinstance(action, QAction))
    for submenu in getattr(menu, "_subMenus", ()):
        result.extend(_menu_actions(submenu))
    return tuple(result)


__all__ = ["PromptAbuseFeatureActionDriver"]
