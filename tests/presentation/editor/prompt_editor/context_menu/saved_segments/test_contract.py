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

"""Verify saved prompt-segment actions and dialog contracts."""

from __future__ import annotations

from __future__ import annotations
from typing import Any, cast
import pytest
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QWidget
from qfluentwidgets.components.widgets.menu import (  # type: ignore[import-untyped]
    RoundMenu,
)
from substitute.presentation.editor.prompt_editor.shell.prompt_text_menu import (
    PromptTextMenu,
)
from substitute.presentation.editor.prompt_editor.features.prompt_segment_preset_models import (
    PromptSegmentPresetMenuItem,
    PromptSegmentPresetMenuModel,
    PromptSegmentPresetMenuSection,
)
from tests.presentation.editor.prompt_editor.context_menu.mounting import (
    create_prompt_editor,
)
from tests.presentation.editor.prompt_editor.context_menu.menu_rows import (
    visible_menu_rows as _menu_visual_rows,
)
from tests.presentation.editor.prompt_editor.context_menu.event_positions import (
    context_event_for_source_text,
)
from tests.presentation.editor.prompt_editor.context_menu.saved_segments.mounting import (
    _PromptSegmentPresetSource,
    create_prompt_editor_with_segments,
)


def test_prompt_editor_segment_source_uses_custom_qfluent_menu(
    prompt_widgets: list[QWidget],
) -> None:
    """Saved prompt segment support should route through the custom QFluent menu."""

    editor = create_prompt_editor_with_segments(
        prompt_widgets,
        _PromptSegmentPresetSource(),
    )

    assert cast(Any, editor)._prompt_menu_requires_custom_actions()


def test_prompt_editor_context_menu_adds_save_segment_for_selection(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Selected prompt text should get a first-layer save action."""

    editor = create_prompt_editor(prompt_widgets)
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    action_texts: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture final menu actions without opening a popup."""

        action_texts.extend(action.text() for action in self.menuActions())

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    menu_type = PromptTextMenu
    menu = menu_type(
        editor,
        schedule_lora=lambda: None,
        prompt_segment_model=PromptSegmentPresetMenuModel(),
        save_prompt_segment=lambda: None,
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))

    assert "Save segment as..." in action_texts


def test_prompt_editor_context_menu_groups_prompt_utilities_before_rich_rendering(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Save, Danbooru wiki lookup, and Schedule LoRA should share one section."""

    editor = create_prompt_editor(prompt_widgets)
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)

    menu_type = PromptTextMenu
    menu = menu_type(
        editor,
        schedule_lora=lambda: None,
        selected_prompt_text="long hair",
        save_prompt_segment=lambda: None,
        lookup_danbooru_wiki=lambda: None,
        danbooru_wiki_lookup_enabled=True,
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))

    visual_rows = _menu_visual_rows(menu)
    save_row = visual_rows.index("Save segment as...")
    lookup_row = visual_rows.index("Danbooru wiki lookup")
    schedule_row = visual_rows.index("Schedule LoRA")
    rich_row = visual_rows.index("Rich prompt rendering")
    save_action = next(
        action for action in menu.menuActions() if action.text() == "Save segment as..."
    )
    schedule_action = next(
        action for action in menu.menuActions() if action.text() == "Schedule LoRA"
    )

    assert lookup_row == save_row + 1
    assert schedule_row == lookup_row + 1
    assert visual_rows[schedule_row + 1] == "<separator>"
    assert rich_row == schedule_row + 2
    assert save_action.icon().isNull() is False
    assert schedule_action.icon().isNull() is False


def test_phase24_1_shell_menu_open_records_context_insert_state(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Shell menu open should capture insertion or replacement state cheaply."""

    editor = create_prompt_editor(prompt_widgets)
    observed_insert_states: list[tuple[int | None, bool | None]] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture insert state after shell prepares the prompt menu."""

        _ = self
        insert_state = cast(
            Any, editor
        )._shell_context_menu.consume_context_insert_state()
        observed_insert_states.append(
            (
                insert_state.insert_position,
                insert_state.should_replace_selection,
            )
        )

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    cast(Any, editor)._shell_context_menu.show_prompt_context_menu(
        context_event_for_source_text(editor, "beta")
    )

    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    cast(Any, editor)._set_context_menu_selection_state_for_tests(
        had_selection=True,
        selection_snapshot=(0, 5, "alpha"),
    )
    cast(Any, editor)._shell_context_menu.show_prompt_context_menu(
        context_event_for_source_text(editor, "alpha")
    )

    assert len(observed_insert_states) == 2
    assert observed_insert_states[0][0] is not None
    assert observed_insert_states[0][1] is False
    assert observed_insert_states[1] == (None, True)


def test_prompt_editor_context_menu_uses_cached_segment_menu_model(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Opening the context menu should not list saved segments from the source."""

    source = _PromptSegmentPresetSource(
        PromptSegmentPresetMenuModel(
            sections=(
                PromptSegmentPresetMenuSection(
                    title="Global",
                    presets=(
                        PromptSegmentPresetMenuItem(
                            label="Blue eyes",
                            text="blue eyes",
                            tooltip="blue eyes",
                        ),
                    ),
                ),
            ),
            save_scopes=(),
        )
    )
    editor = create_prompt_editor_with_segments(prompt_widgets, source)
    source.list_calls = 0
    visual_rows: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture built menu rows without opening a popup."""

        visual_rows.extend(_menu_visual_rows(self))

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    cast(Any, editor)._shell_context_menu.show_prompt_context_menu(
        context_event_for_source_text(editor, "alpha")
    )

    assert source.list_calls == 0
    assert "Insert saved segment" in visual_rows
