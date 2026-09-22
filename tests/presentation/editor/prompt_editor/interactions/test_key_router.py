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

"""Verify prompt-editor keyboard precedence independently of the Qt shell."""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from substitute.presentation.editor.prompt_editor.key_router import (
    PromptEditorKeyBindings,
    PromptEditorKeyRouter,
)


@dataclass(slots=True)
class _RecordingInteraction:
    """Record keyboard feature routing decisions."""

    consume_press: bool = False
    consume_release: bool = False
    calls: list[str] = field(default_factory=list)

    def handle_key_press(self, _event: QKeyEvent) -> bool:
        """Record feature-first press routing."""

        self.calls.append("press")
        return self.consume_press

    def handle_key_release(self, _event: QKeyEvent) -> bool:
        """Record feature-first release routing."""

        self.calls.append("release")
        return self.consume_release

    def handle_emphasis_shortcut_accepted(self) -> None:
        """Record emphasis shortcut publication."""

        self.calls.append("emphasis")

    def clear_autocomplete_for_non_text_key_from_keymap(self) -> None:
        """Record non-text autocomplete clearing."""

        self.calls.append("clear")

    def handle_post_key_press(self, _event: QKeyEvent) -> None:
        """Record ordinary post-key publication."""

        self.calls.append("post")


@dataclass(slots=True)
class _RecordingSurface:
    """Record projection key routing and control event acceptance."""

    accept_press: bool = True
    accept_release: bool = True
    calls: list[str] = field(default_factory=list)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Record one projection key press."""

        self.calls.append("press")
        event.setAccepted(self.accept_press)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Record one projection key release."""

        self.calls.append("release")
        event.setAccepted(self.accept_release)


def test_autocomplete_consumption_prevents_projection_editing() -> None:
    """A feature-consumed key must never reach the source-editing surface."""

    interaction = _RecordingInteraction(consume_press=True)
    surface = _RecordingSurface()
    router = _router(interaction, surface)

    router.handle_key_press(_press(Qt.Key.Key_Tab))

    assert interaction.calls == ["press"]
    assert surface.calls == []


def test_ignored_projection_key_has_no_post_key_effect() -> None:
    """An unhandled projection key must not refresh feature state."""

    interaction = _RecordingInteraction()
    surface = _RecordingSurface(accept_press=False)
    router = _router(interaction, surface)

    router.handle_key_press(_press(Qt.Key.Key_F1))

    assert interaction.calls == ["press"]
    assert surface.calls == ["press"]


def test_emphasis_shortcut_suppresses_autocomplete_refresh() -> None:
    """Accepted Ctrl+Arrow emphasis edits publish only emphasis completion."""

    interaction = _RecordingInteraction()
    router = _router(interaction, _RecordingSurface())

    router.handle_key_press(
        _press(Qt.Key.Key_Up, modifiers=Qt.KeyboardModifier.ControlModifier)
    )

    assert interaction.calls == ["press", "emphasis"]


def test_accepted_tab_clears_autocomplete_without_refreshing_it() -> None:
    """Accepted Tab must not reopen the autocomplete surface it dismissed."""

    interaction = _RecordingInteraction()
    router = _router(interaction, _RecordingSurface())

    router.handle_key_press(_press(Qt.Key.Key_Tab))

    assert interaction.calls == ["press", "clear"]


def test_accepted_text_key_publishes_post_key_work() -> None:
    """An accepted text edit should publish ordinary post-key feature work."""

    interaction = _RecordingInteraction()
    router = _router(interaction, _RecordingSurface())

    router.handle_key_press(_press(Qt.Key.Key_A, text="a"))

    assert interaction.calls == ["press", "post"]


def test_key_release_uses_feature_first_precedence() -> None:
    """Feature-owned releases bypass the projection surface."""

    interaction = _RecordingInteraction(consume_release=True)
    surface = _RecordingSurface()
    router = _router(interaction, surface)

    router.handle_key_release(_release(Qt.Key.Key_Alt))

    assert interaction.calls == ["release"]
    assert surface.calls == []


def _press(
    key: Qt.Key,
    *,
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
    text: str = "",
) -> QKeyEvent:
    """Create one deterministic key-press event."""

    return QKeyEvent(QEvent.Type.KeyPress, key, modifiers, text)


def _router(
    interaction: _RecordingInteraction,
    surface: _RecordingSurface,
) -> PromptEditorKeyRouter:
    """Bind recording collaborators to the production keyboard router."""

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


def _release(key: Qt.Key) -> QKeyEvent:
    """Create one deterministic key-release event."""

    return QKeyEvent(
        QEvent.Type.KeyRelease,
        key,
        Qt.KeyboardModifier.NoModifier,
    )
