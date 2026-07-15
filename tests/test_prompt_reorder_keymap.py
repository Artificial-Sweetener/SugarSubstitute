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

"""Tests for prompt reorder keymap routing."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtCore import Qt

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptMutationService,
)
from substitute.presentation.editor.prompt_editor.models import (
    PromptEditorInteractionMode,
    PromptReorderCancelIntent,
    PromptReorderCommitIntent,
    PromptReorderKeyboardMoveIntent,
    SegmentReorderSession,
)
from tests.prompt_autocomplete_test_helpers import prompt_syntax_profile
from tests.prompt_editor_controller_test_helpers import key_event
from tests.prompt_reorder_interaction_test_helpers import (
    ControllerEditorDouble,
    MenuCursorDouble,
    OverlayDouble,
    autocomplete_double,
    prompt_interaction_controller,
    semantic_refresh_controller_double,
    syntax_renderer_double,
    syntax_service,
)


def test_handle_key_press_enters_reorder_mode_on_alt_only() -> None:
    """Alt enters reorder mode and other modifier chords do not."""

    shown: list[str] = []
    autocomplete_calls: list[object] = []

    def record_autocomplete_key(event: object) -> bool:
        """Record delegated autocomplete key events."""

        autocomplete_calls.append(cast(Any, event).key())
        return False

    autocomplete = SimpleNamespace(
        handle_key_press=record_autocomplete_key,
        refresh_for_query=lambda _query, **_kwargs: None,
        dismiss_autocomplete=lambda _reason: None,
        refresh_geometry=lambda: None,
    )
    controller = _controller_for_reorder_text(
        "alpha, beta",
        autocomplete=autocomplete,
    )
    controller._reorder.enter_segment_reorder_mode = lambda: shown.append("show")

    assert controller.handle_key_press(_key_event(Qt.Key.Key_Alt)) is True
    assert shown == ["show"]

    assert (
        controller.handle_key_press(
            _key_event(
                Qt.Key.Key_Shift,
                modifiers=(
                    Qt.KeyboardModifier.ControlModifier
                    | Qt.KeyboardModifier.ShiftModifier
                ),
            )
        )
        is False
    )
    assert autocomplete_calls == [Qt.Key.Key_Shift]


def test_handle_key_release_on_alt_skips_mutation_when_overlay_order_is_unchanged() -> (
    None
):
    """Alt release closes reorder mode without mutation when nothing moved."""

    editor = ControllerEditorDouble(
        clicked_cursor=MenuCursorDouble(text="alpha, beta", position=7),
        current_cursor=MenuCursorDouble(text="alpha, beta", position=7),
        text="alpha, beta",
    )
    controller = _controller_for_reorder_editor(
        editor,
        mutation_service=PromptMutationService(),
    )
    overlay = OverlayDouble([0, 1], active_segment_index=1, has_reordered=False)
    controller._reorder._segment_overlay = overlay
    controller._reorder._interaction_mode = PromptEditorInteractionMode.SEGMENT_REORDER
    controller._reorder._session_controller.replace_session(
        SegmentReorderSession(
            is_active=True,
            original_ordered_indices=(0, 1),
            current_ordered_indices=(0, 1),
            active_segment_index=1,
            selection_start=7,
            selection_end=7,
        )
    )

    handled = controller.handle_key_release(_key_event(Qt.Key.Key_Alt))

    assert handled is True
    assert editor.toPlainText() == "alpha, beta"
    assert overlay.closed == 1
    assert overlay.deleted == 1
    assert controller.segment_overlay is None
    assert (
        controller._reorder.interaction_mode is PromptEditorInteractionMode.TEXT_EDITING
    )


def test_handle_key_press_escape_cancels_reorder_mode_without_mutation() -> None:
    """Escape cancels reorder mode and restores the captured selection."""

    editor = ControllerEditorDouble(
        clicked_cursor=MenuCursorDouble(text="alpha, beta", position=7),
        current_cursor=MenuCursorDouble(text="alpha, beta", position=0),
        text="alpha, beta",
    )
    controller = _controller_for_reorder_editor(
        editor,
        mutation_service=PromptMutationService(),
    )
    overlay = OverlayDouble([1, 0], active_segment_index=1, has_reordered=True)
    controller._reorder._segment_overlay = overlay
    controller._reorder._interaction_mode = PromptEditorInteractionMode.SEGMENT_REORDER
    controller._reorder._session_controller.replace_session(
        SegmentReorderSession(
            is_active=True,
            original_ordered_indices=(0, 1),
            current_ordered_indices=(0, 1),
            active_segment_index=1,
            selection_start=7,
            selection_end=7,
        )
    )

    handled = controller.handle_key_press(_key_event(Qt.Key.Key_Escape))

    assert handled is True
    assert editor.textCursor().selectionStart() == 7
    assert editor.textCursor().selectionEnd() == 7
    assert overlay.cancel_drag_calls == 1
    assert overlay.closed == 1
    assert overlay.deleted == 1
    assert controller.segment_overlay is None


def test_handle_key_press_routes_arrow_keys_to_overlay_during_reorder_mode() -> None:
    """Reorder mode applies typed arrow-key intents through the controller."""

    autocomplete_calls: list[object] = []

    def record_autocomplete_key(event: object) -> bool:
        """Record unexpected autocomplete key delegation."""

        autocomplete_calls.append(cast(Any, event).key())
        return False

    controller = _controller_for_reorder_text(
        "alpha, beta, gamma",
        autocomplete=SimpleNamespace(
            handle_key_press=record_autocomplete_key,
            refresh_for_query=lambda _query, **_kwargs: None,
            dismiss_autocomplete=lambda _reason: None,
            refresh_geometry=lambda: None,
        ),
    )
    overlay = OverlayDouble([0, 1, 2], active_segment_index=1, has_reordered=False)
    controller._reorder._segment_overlay = overlay
    controller._reorder._interaction_mode = PromptEditorInteractionMode.SEGMENT_REORDER

    assert controller.handle_key_press(_key_event(Qt.Key.Key_Left)) is True
    assert controller.handle_key_press(_key_event(Qt.Key.Key_Right)) is True
    assert controller.handle_key_press(_key_event(Qt.Key.Key_Up)) is True
    assert controller.handle_key_press(_key_event(Qt.Key.Key_Down)) is True

    assert overlay.keyboard_move_calls == ["left", "right", "up", "down"]
    assert autocomplete_calls == []


def test_keymap_routes_reorder_keys_as_typed_intents() -> None:
    """Keymap emits typed reorder intents without reading overlay methods."""

    keymap_mod = importlib.import_module(
        "substitute.presentation.editor.prompt_editor.interactions.keymap"
    )

    class _Host:
        """Record keymap reorder intents for one focused routing test."""

        interaction_mode = PromptEditorInteractionMode.SEGMENT_REORDER

        def __init__(self) -> None:
            """Initialize recorded typed intents."""

            self.cancel_intents: list[PromptReorderCancelIntent] = []
            self.commit_intents: list[PromptReorderCommitIntent] = []
            self.move_intents: list[PromptReorderKeyboardMoveIntent] = []

        def enter_segment_reorder_mode_from_keymap(self) -> None:
            """Fail if reorder entry is requested while already active."""

            raise AssertionError("reorder mode already active")

        def cancel_segment_reorder_mode_from_keymap(
            self,
            intent: PromptReorderCancelIntent,
        ) -> None:
            """Record one cancel intent."""

            self.cancel_intents.append(intent)

        def commit_segment_reorder_mode_from_keymap(
            self,
            intent: PromptReorderCommitIntent,
        ) -> None:
            """Record one commit intent."""

            self.commit_intents.append(intent)

        def move_keyboard_reorder_chip_from_keymap(
            self,
            intent: PromptReorderKeyboardMoveIntent,
        ) -> None:
            """Record one keyboard move intent."""

            self.move_intents.append(intent)

        def handle_autocomplete_key_press_from_keymap(self, event: object) -> bool:
            """Return false for inactive autocomplete paths."""

            _ = event
            return False

        def handle_autocomplete_post_key_press_from_keymap(self, event: object) -> None:
            """Ignore inactive autocomplete paths."""

            _ = event

        def clear_autocomplete_for_emphasis_shortcut_from_keymap(self) -> None:
            """Ignore inactive emphasis autocomplete paths."""

        def flush_semantic_refresh_from_keymap(self, *, reason: str) -> None:
            """Ignore inactive semantic refresh paths."""

            _ = reason

        def clear_keyboard_emphasis_session_from_keymap(self) -> None:
            """Ignore inactive emphasis cleanup paths."""

    host = _Host()
    keymap = keymap_mod.PromptKeymapController(host)

    assert keymap.handle_key_press(_key_event(Qt.Key.Key_Left)) is True
    assert keymap.handle_key_press(_key_event(Qt.Key.Key_Right)) is True
    assert keymap.handle_key_press(_key_event(Qt.Key.Key_Up)) is True
    assert keymap.handle_key_press(_key_event(Qt.Key.Key_Down)) is True
    assert keymap.handle_key_press(_key_event(Qt.Key.Key_Escape)) is True
    assert keymap.handle_key_release(_key_event(Qt.Key.Key_Alt)) is True

    assert [intent.direction for intent in host.move_intents] == [
        "left",
        "right",
        "up",
        "down",
    ]
    assert host.cancel_intents == [PromptReorderCancelIntent(reason="escape")]
    assert host.commit_intents == [PromptReorderCommitIntent(reason="alt_release")]


def _controller_for_reorder_text(
    text: str,
    *,
    autocomplete: object | None = None,
) -> Any:
    """Build a reorder-capable interaction controller for sample prompt text."""

    return _controller_for_reorder_editor(
        ControllerEditorDouble(
            clicked_cursor=MenuCursorDouble(text=text, position=7),
            current_cursor=MenuCursorDouble(text=text, position=7),
            text=text,
        ),
        autocomplete=autocomplete,
    )


def _controller_for_reorder_editor(
    editor: ControllerEditorDouble,
    *,
    autocomplete: object | None = None,
    mutation_service: PromptMutationService | None = None,
) -> Any:
    """Build a reorder-capable interaction controller for one editor double."""

    return prompt_interaction_controller(
        editor,
        autocomplete=autocomplete or autocomplete_double(),
        semantic_refresh_controller=semantic_refresh_controller_double(),
        syntax_renderers=syntax_renderer_double(),
        document_service=PromptDocumentService(),
        mutation_service=mutation_service or PromptMutationService(),
        syntax_service_=syntax_service(),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
    )


def _key_event(
    key: Qt.Key,
    *,
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
) -> Any:
    """Return a minimal key event while preserving Qt enum runtime values."""

    return key_event(cast(int, key), modifiers=modifiers)
