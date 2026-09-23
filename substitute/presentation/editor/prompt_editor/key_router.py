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

"""Route prompt-editor keyboard input across interaction and surface owners."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from .interactions import PromptInteractionController
from .projection.surface import PromptProjectionSurface


@dataclass(frozen=True, slots=True)
class PromptEditorKeyBindings:
    """Declare the complete keyboard-routing boundary."""

    handle_feature_key_press: Callable[[QKeyEvent], bool]
    handle_feature_key_release: Callable[[QKeyEvent], bool]
    publish_emphasis_shortcut: Callable[[], None]
    clear_autocomplete_for_non_text_key: Callable[[], None]
    publish_post_key_press: Callable[[QKeyEvent], None]
    handle_surface_key_press: Callable[[QKeyEvent], None]
    handle_surface_key_release: Callable[[QKeyEvent], None]


@dataclass(frozen=True, slots=True)
class PromptEditorKeyRouter:
    """Own keyboard precedence between features and projection editing."""

    bindings: PromptEditorKeyBindings

    def handle_key_press(self, event: QKeyEvent) -> None:
        """Route one key press and publish only valid post-edit feature work."""

        if self.bindings.handle_feature_key_press(event):
            return
        self.bindings.handle_surface_key_press(event)
        if not event.isAccepted():
            return
        if _emphasis_shortcut_should_mute_autocomplete(event):
            self.bindings.publish_emphasis_shortcut()
            return
        if _accepted_key_should_skip_autocomplete_post_refresh(event):
            self.bindings.clear_autocomplete_for_non_text_key()
            return
        self.bindings.publish_post_key_press(event)

    def handle_key_release(self, event: QKeyEvent) -> None:
        """Route one key release through feature and projection owners."""

        if self.bindings.handle_feature_key_release(event):
            return
        self.bindings.handle_surface_key_release(event)
        if not event.isAccepted():
            event.ignore()


def build_prompt_editor_key_router(
    interaction: PromptInteractionController,
    surface: PromptProjectionSurface,
) -> PromptEditorKeyRouter:
    """Bind production feature and projection owners to keyboard routing."""

    return PromptEditorKeyRouter(
        PromptEditorKeyBindings(
            handle_feature_key_press=interaction.handle_key_press,
            handle_feature_key_release=interaction.handle_key_release,
            publish_emphasis_shortcut=interaction.handle_emphasis_shortcut_accepted,
            clear_autocomplete_for_non_text_key=(
                interaction.clear_autocomplete_for_non_text_key_from_keymap
            ),
            publish_post_key_press=interaction.handle_post_key_press,
            handle_surface_key_press=surface.keyPressEvent,
            handle_surface_key_release=surface.keyReleaseEvent,
        )
    )


def _emphasis_shortcut_should_mute_autocomplete(event: QKeyEvent) -> bool:
    """Return whether an accepted key belongs to keyboard emphasis changes."""

    modifiers = event.modifiers()
    if not bool(modifiers & Qt.KeyboardModifier.ControlModifier):
        return False
    disallowed_modifiers = (
        Qt.KeyboardModifier.ShiftModifier
        | Qt.KeyboardModifier.AltModifier
        | Qt.KeyboardModifier.MetaModifier
    )
    if bool(modifiers & disallowed_modifiers):
        return False
    return event.key() in {Qt.Key.Key_Up, Qt.Key.Key_Down}


def _accepted_key_should_skip_autocomplete_post_refresh(event: QKeyEvent) -> bool:
    """Return whether an accepted non-text key must not reopen autocomplete."""

    return event.key() in {Qt.Key.Key_Escape, Qt.Key.Key_Tab}


__all__ = [
    "PromptEditorKeyBindings",
    "PromptEditorKeyRouter",
    "build_prompt_editor_key_router",
]
