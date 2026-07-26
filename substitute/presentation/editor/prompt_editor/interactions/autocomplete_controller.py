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

"""Define autocomplete interaction controller protocol boundaries."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor.debug_probe import (
    autocomplete_probe_state,
    log_prompt_editor_probe,
)
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptAutocompletePanel,
)
from substitute.presentation.widgets.picker_keyboard_navigation import (
    PickerKeyboardAction,
    picker_keyboard_action_for_key,
)
from .autocomplete_acceptance_lifecycle import PromptAutocompleteAcceptanceLifecycle
from .autocomplete_session import (
    PromptAutocompleteDismissReason,
    PromptAutocompleteSessionController,
    PromptAutocompleteSessionState,
)
from .autocomplete_session_publication import PromptAutocompleteSessionPublication


class PromptAutocompleteInputAdapter:
    """Translate Qt autocomplete input and presenter events into owner commands."""

    def __init__(
        self,
        focus_host: QWidget,
        *,
        restore_focus: Callable[[], None],
        acceptance_lifecycle: PromptAutocompleteAcceptanceLifecycle,
        session_publication: PromptAutocompleteSessionPublication,
    ) -> None:
        """Store the editor dependencies and initialize empty autocomplete state."""

        self._focus_host = focus_host
        self._restore_focus = restore_focus
        self._acceptance_lifecycle = acceptance_lifecycle
        self._session_publication = session_publication
        self._session_publication.install_interaction_handlers(
            activation_handler=self._handle_presenter_activation,
            selection_changed_handler=self._handle_presenter_selection_changed,
            visibility_changed_handler=self._handle_presenter_visibility_changed,
        )

    @property
    def panel(self) -> PromptAutocompletePanel | None:
        """Return the live autocomplete panel widget when it exists."""

        return self._session_publication.panel

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """Handle non-text autocomplete controls without interrupting normal typing."""

        log_prompt_editor_probe(
            "autocomplete.handle_key_press.begin",
            key=int(event.key()),
            text=event.text(),
            autocomplete=autocomplete_probe_state(self),
        )
        if not self._has_active_session():
            log_prompt_editor_probe(
                "autocomplete.handle_key_press.end",
                handled=False,
                reason="inactive",
                autocomplete=autocomplete_probe_state(self),
            )
            return False

        modifiers = event.modifiers()
        if modifiers not in (
            Qt.KeyboardModifier.NoModifier,
            Qt.KeyboardModifier.KeypadModifier,
        ):
            log_prompt_editor_probe(
                "autocomplete.handle_key_press.end",
                handled=False,
                reason="modifiers",
                autocomplete=autocomplete_probe_state(self),
            )
            return False

        key = event.key()
        if self._session_publication.session.mode == "lora":
            return self._handle_lora_key_press(key)

        if key == Qt.Key.Key_Down:
            self._session_publication.move_suggestion_selection(1)
            log_prompt_editor_probe(
                "autocomplete.handle_key_press.end",
                handled=True,
                reason="down_selection",
                autocomplete=autocomplete_probe_state(self),
            )
            return True
        if key == Qt.Key.Key_Up:
            self._session_publication.move_suggestion_selection(-1)
            log_prompt_editor_probe(
                "autocomplete.handle_key_press.end",
                handled=True,
                reason="up_selection",
                autocomplete=autocomplete_probe_state(self),
            )
            return True
        if key in {
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
            Qt.Key.Key_Home,
            Qt.Key.Key_End,
        }:
            self.dismiss_autocomplete("caret_left_query")
            log_prompt_editor_probe(
                "autocomplete.handle_key_press.end",
                handled=False,
                reason="horizontal_or_line_key",
                autocomplete=autocomplete_probe_state(self),
            )
            return False
        if key == Qt.Key.Key_Tab:
            self.accept_selection(add_comma=True)
            log_prompt_editor_probe(
                "autocomplete.handle_key_press.end",
                handled=True,
                reason="tab_accept",
                autocomplete=autocomplete_probe_state(self),
            )
            return True
        if key == Qt.Key.Key_Escape:
            self.dismiss_autocomplete("escape")
            log_prompt_editor_probe(
                "autocomplete.handle_key_press.end",
                handled=True,
                reason="escape",
                autocomplete=autocomplete_probe_state(self),
            )
            return True
        log_prompt_editor_probe(
            "autocomplete.handle_key_press.end",
            handled=False,
            reason="unhandled",
            autocomplete=autocomplete_probe_state(self),
        )
        return False

    def accept_selection(self, *, add_comma: bool) -> None:
        """Accept the selected autocomplete suggestion through command wiring."""

        self._acceptance_lifecycle.accept_selection(add_comma=add_comma)

    def accept_scene_selection(self) -> None:
        """Accept the selected workflow scene title through command wiring."""

        self._acceptance_lifecycle.accept_scene_selection()

    def accept_wildcard_selection(self) -> None:
        """Accept the selected wildcard placeholder through command wiring."""

        self._acceptance_lifecycle.accept_wildcard_selection()

    def accept_lora_selection(self) -> None:
        """Accept the selected scheduler-safe LoRA token through command wiring."""

        self._acceptance_lifecycle.accept_lora_selection()

    def activate_suggestion(self, index: int) -> None:
        """Accept the clicked suggestion row and keep focus in the editor."""

        self._acceptance_lifecycle.activate_suggestion(index)
        self._restore_focus()

    def activate_lora_candidate(self, index: int) -> None:
        """Accept the clicked LoRA wall candidate and keep focus in the editor."""

        self._acceptance_lifecycle.activate_lora_candidate(index)
        self._restore_focus()

    def _handle_presenter_activation(
        self,
        intent: object,
    ) -> None:
        """Accept one activation emitted by the presenter-owned overlay."""

        index = getattr(intent, "index", -1)
        if not isinstance(index, int):
            return
        if self._session_publication.session.mode == "lora":
            self.activate_lora_candidate(index)
            return
        self.activate_suggestion(index)

    def _handle_presenter_selection_changed(self, index: int) -> None:
        """Mirror presenter-owned overlay selection into the autocomplete session."""

        if index < 0:
            return
        self._session_publication.select_index(index)
        self._session_publication.publish_inline_completion_preview_if_panel_visible()

    def _handle_presenter_visibility_changed(self, visible: bool) -> None:
        """Clear ghost text as soon as autocomplete presentation is hidden."""

        log_prompt_editor_probe(
            "autocomplete.presenter_visibility_changed",
            visible=visible,
            autocomplete=autocomplete_probe_state(self),
        )
        if not visible:
            self._session_publication.clear_inline_completion_preview()

    def dismiss_autocomplete(
        self,
        reason: PromptAutocompleteDismissReason,
    ) -> None:
        """Hide autocomplete visuals and reset state for one lifecycle reason."""

        log_prompt_editor_probe(
            "autocomplete.dismiss.begin",
            reason=reason,
            autocomplete=autocomplete_probe_state(self),
        )
        if reason == "focus_lost" and self._should_keep_autocomplete_on_focus_loss():
            log_prompt_editor_probe(
                "autocomplete.dismiss.end",
                reason=reason,
                dismissed=False,
                kept_for_focus=True,
                autocomplete=autocomplete_probe_state(self),
            )
            return

        self._session_publication.dismiss_autocomplete(reason)
        log_prompt_editor_probe(
            "autocomplete.dismiss.end",
            reason=reason,
            dismissed=True,
            autocomplete=autocomplete_probe_state(self),
        )

    def _should_keep_autocomplete_on_focus_loss(self) -> bool:
        """Return whether focus loss still belongs to autocomplete interaction."""

        focus_widget = QApplication.focusWidget()
        if focus_widget is self._focus_host or (
            focus_widget is not None and self._focus_host.isAncestorOf(focus_widget)
        ):
            return True

        if self._session_publication.panel_under_mouse():
            return True

        return False

    def refresh_geometry(self) -> None:
        """Reposition the panel and inline preview after editor geometry changes."""

        self._session_publication.refresh_geometry()

    def _handle_lora_key_press(self, key: int) -> bool:
        """Handle keyboard controls for the LoRA media wall mode."""

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return False

        action = picker_keyboard_action_for_key(
            key,
            tab_activates=True,
            escape_dismisses=True,
        )
        if action is PickerKeyboardAction.RIGHT:
            self._session_publication.move_lora_selection("right", 1)
            return True
        if action is PickerKeyboardAction.LEFT:
            self._session_publication.move_lora_selection("left", -1)
            return True
        if action is PickerKeyboardAction.DOWN:
            self._session_publication.move_lora_selection("down", 1)
            return True
        if action is PickerKeyboardAction.UP:
            self._session_publication.move_lora_selection("up", -1)
            return True
        if action is PickerKeyboardAction.ACTIVATE:
            self.accept_lora_selection()
            return True
        if action is PickerKeyboardAction.DISMISS:
            self.dismiss_autocomplete("escape")
            return True
        if key in {Qt.Key.Key_Home, Qt.Key.Key_End}:
            self.dismiss_autocomplete("caret_left_query")
            return False
        return False

    def _has_active_session(self) -> bool:
        """Return whether the current autocomplete session has selectable content."""

        return self._session_publication.has_active_session()

    def has_active_session(self) -> bool:
        """Return whether source edits have an autocomplete session to retarget."""

        return self._has_active_session()


class PromptAutocompleteInputPort(Protocol):
    """Describe Qt autocomplete input operations used by interaction orchestration."""

    @property
    def panel(self) -> PromptAutocompletePanel | None:
        """Return the live autocomplete panel while legacy tests inspect it."""

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """Handle autocomplete-owned non-text key presses."""

    def has_active_session(self) -> bool:
        """Return whether source edits have an autocomplete session to retarget."""

    def accept_selection(self, *, add_comma: bool) -> None:
        """Accept the selected autocomplete suggestion."""

    def accept_scene_selection(self) -> None:
        """Accept the selected scene autocomplete suggestion."""

    def accept_wildcard_selection(self) -> None:
        """Accept the selected wildcard autocomplete suggestion."""

    def accept_lora_selection(self) -> None:
        """Accept the selected LoRA autocomplete suggestion."""

    def activate_suggestion(self, index: int) -> None:
        """Accept the activated suggestion row and restore focus."""

    def activate_lora_candidate(self, index: int) -> None:
        """Accept the activated LoRA candidate and restore focus."""

    def dismiss_autocomplete(
        self,
        reason: PromptAutocompleteDismissReason,
    ) -> None:
        """Dismiss autocomplete state for one explicit lifecycle reason."""

    def refresh_geometry(self) -> None:
        """Reposition autocomplete surfaces after geometry changes."""


__all__ = [
    "PromptAutocompleteInputAdapter",
    "PromptAutocompleteInputPort",
    "PromptAutocompleteSessionController",
    "PromptAutocompleteSessionState",
]
