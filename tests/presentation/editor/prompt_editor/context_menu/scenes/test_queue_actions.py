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

"""Verify scene queue actions in prompt context menus."""

from __future__ import annotations

from __future__ import annotations
from typing import Any, cast
import pytest
from PySide6.QtWidgets import QWidget
from qfluentwidgets.components.widgets.menu import (  # type: ignore[import-untyped]
    RoundMenu,
)
from tests.presentation.editor.prompt_editor.context_menu.mounting import (
    create_prompt_editor,
    ensure_qapp,
    process_events,
)
from tests.presentation.editor.prompt_editor.context_menu.event_positions import (
    context_event_for_source_text,
    prepared_context_event_for_source_text,
)


def test_prompt_editor_context_menu_adds_queue_scene_for_queueable_scene(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Right-clicking a queueable scene block should add a scene queue action."""

    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("quality\n**portrait\nportrait text\n**cafe\ncafe text")
    editor.set_queueable_scene_keys(frozenset({"portrait", "cafe"}))
    process_events(ensure_qapp())
    action_texts: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture final menu actions without opening a popup."""

        action_texts.extend(action.text() for action in self.menuActions())

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    cast(Any, editor)._shell_context_menu.show_prompt_context_menu(
        prepared_context_event_for_source_text(editor, "portrait text")
    )

    assert "Queue this scene" in action_texts


def test_prompt_editor_context_menu_omits_queue_scene_for_universal_text(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Right-clicking universal text should not offer scene queueing."""

    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("quality\n**portrait\nportrait text")
    editor.set_queueable_scene_keys(frozenset({"portrait"}))
    process_events(ensure_qapp())
    action_texts: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture final menu actions without opening a popup."""

        action_texts.extend(action.text() for action in self.menuActions())

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    cast(Any, editor)._shell_context_menu.show_prompt_context_menu(
        context_event_for_source_text(editor, "quality")
    )

    assert "Queue this scene" not in action_texts


def test_prompt_editor_context_menu_omits_queue_scene_for_nonqueueable_scene(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Scene syntax should not be enough when workflow analysis rejects the key."""

    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("quality\n**portrait\nportrait text\n**cafe\ncafe text")
    editor.set_queueable_scene_keys(frozenset({"cafe"}))
    process_events(ensure_qapp())
    action_texts: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture final menu actions without opening a popup."""

        action_texts.extend(action.text() for action in self.menuActions())

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    cast(Any, editor)._shell_context_menu.show_prompt_context_menu(
        prepared_context_event_for_source_text(editor, "portrait text")
    )

    assert "Queue this scene" not in action_texts


def test_prompt_editor_queue_scene_action_emits_normalized_scene_key(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Triggering the scene queue action should emit the normalized scene key."""

    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("**Portrait Scene\nportrait text")
    editor.set_queueable_scene_keys(frozenset({"portrait scene"}))
    process_events(ensure_qapp())
    emitted_keys: list[str] = []
    editor.sceneQueueRequested.connect(emitted_keys.append)

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Trigger the queue action without opening a popup."""

        action = next(
            action
            for action in self.menuActions()
            if action.text() == "Queue this scene"
        )
        action.trigger()

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    cast(Any, editor)._shell_context_menu.show_prompt_context_menu(
        prepared_context_event_for_source_text(editor, "portrait text")
    )

    assert emitted_keys == ["portrait scene"]
