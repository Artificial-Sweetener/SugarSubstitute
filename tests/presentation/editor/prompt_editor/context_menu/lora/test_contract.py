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

"""Verify LoRA scheduling and trigger-word context-menu contracts."""

from __future__ import annotations

from __future__ import annotations
from typing import Any, cast
import pytest
from PySide6.QtGui import QFontMetrics, QTextCursor
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets.components.widgets.menu import (  # type: ignore[import-untyped]
    RoundMenu,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
)
from substitute.application.prompt_editor.lora.scheduled import (
    PromptScheduledLora,
)
from substitute.presentation.editor.prompt_editor.interactions import (
    PromptTriggerWordActionAdapter,
)
from substitute.presentation.editor.prompt_editor.shell.prompt_text_menu import (
    PromptTextMenu,
)
from tests.presentation.editor.prompt_editor.context_menu.mounting import (
    create_lora_prompt_editor,
    ensure_qapp,
    process_events,
)
from tests.presentation.editor.prompt_editor.context_menu.menu_rows import (
    visible_menu_rows as _menu_visual_rows,
)
from tests.presentation.editor.prompt_editor.context_menu.trigger_actions import (
    trigger_words_action_for_lora,
)


def test_prompt_editor_lora_context_menu_preserves_qfluent_text_actions(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """LoRA support should append to QFluent's text menu instead of using Qt's menu."""

    editor = create_lora_prompt_editor(prompt_widgets)
    action_texts: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture the final menu actions without opening a popup."""

        action_texts.extend(action.text() for action in self.menuActions())

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    menu_type = PromptTextMenu
    menu = menu_type(editor, schedule_lora=lambda: None)
    menu.exec(editor.mapToGlobal(editor.rect().center()))

    assert "Cancel" not in action_texts
    assert "Select all" in action_texts
    assert "Rich prompt rendering" in action_texts
    assert "Schedule LoRA" in action_texts
    assert action_texts.index("Rich prompt rendering") > action_texts.index(
        "Select all"
    )
    visual_rows = _menu_visual_rows(menu)
    rich_row = visual_rows.index("Rich prompt rendering")
    schedule_row = visual_rows.index("Schedule LoRA")
    assert visual_rows[schedule_row - 2] == "Select all"
    assert visual_rows[schedule_row - 1] == "<separator>"
    assert visual_rows[schedule_row + 1] == "<separator>"
    assert rich_row == schedule_row + 2


def test_prompt_editor_general_context_menu_nests_single_trigger_action(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """One trigger-word action should still live in the dedicated submenu."""

    editor = create_lora_prompt_editor(prompt_widgets)
    scheduled_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Friendly Midna",
        trained_words=("imp princess",),
        source="cube_field",
    )
    action_texts: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture final menu actions without opening a popup."""

        action_texts.extend(action.text() for action in self.menuActions())

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)

    menu_type = PromptTextMenu
    menu = menu_type(
        editor,
        schedule_lora=lambda: None,
        trigger_word_actions=(
            trigger_words_action_for_lora(
                editor,
                scheduled_lora,
                prompt_text=editor.toPlainText(),
            ),
        ),
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))

    assert "Friendly Midna" not in action_texts
    assert "Insert trigger words" in _menu_visual_rows(menu)
    submenu = next(
        submenu
        for submenu in cast(Any, menu)._subMenus
        if submenu.title() == "Insert trigger words"
    )
    getattr(submenu, "populate_if_needed")()
    trigger_action = submenu.menuActions()[0]
    assert trigger_action.text() == "Friendly Midna"
    assert trigger_action.toolTip() == "Trigger words: Friendly Midna"
    assert action_texts[-2] == "Schedule LoRA"
    assert action_texts[-1] == "Rich prompt rendering"


def test_phase24_1_context_menu_groups_multiple_trigger_actions(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Multiple prepared trigger-word actions should appear in one submenu."""

    editor = create_lora_prompt_editor(prompt_widgets)
    first_action = trigger_words_action_for_lora(
        editor,
        PromptScheduledLora(
            prompt_name="midna",
            backend_value="midna.safetensors",
            display_name="Friendly Midna",
            trained_words=("imp princess",),
            source="cube_field",
        ),
        prompt_text=editor.toPlainText(),
    )
    second_action = trigger_words_action_for_lora(
        editor,
        PromptScheduledLora(
            prompt_name="zelda",
            backend_value="zelda.safetensors",
            display_name="Friendly Zelda",
            trained_words=("wise princess",),
            source="cube_field",
        ),
        prompt_text=editor.toPlainText(),
    )
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)

    menu = PromptTextMenu(
        editor,
        schedule_lora=lambda: None,
        trigger_word_actions=(first_action, second_action),
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))

    visual_rows = _menu_visual_rows(menu)
    assert "Insert trigger words" in visual_rows
    submenu = next(
        submenu
        for submenu in cast(Any, menu)._subMenus
        if submenu.title() == "Insert trigger words"
    )
    populate = getattr(submenu, "populate_if_needed")
    populate()
    assert [action.text() for action in submenu.menuActions()] == [
        "Friendly Midna",
        "Friendly Zelda",
    ]
    assert [
        action.property("promptFullTriggerWordsLabel")
        for action in submenu.menuActions()
    ] == [
        "Trigger words: Friendly Midna",
        "Trigger words: Friendly Zelda",
    ]


def test_prompt_editor_trigger_action_label_elides_to_total_menu_budget(
    prompt_widgets: list[QWidget],
) -> None:
    """Long LoRA names should not make trigger-word context menus wide."""

    editor = create_lora_prompt_editor(prompt_widgets)
    long_name = (
        "Extremely Long CivitAI Friendly LoRA Name With Version Details And "
        "Training Notes That Would Otherwise Blow Out The Context Menu"
    )

    label = PromptTriggerWordActionAdapter(
        action_parent=editor,
        text_insertion_executor=cast(Any, editor)._context_insertion,
        identity_validator=lambda _identity: True,
    ).trigger_words_action_label(long_name)

    metrics = QFontMetrics(QApplication.font())
    assert not label.startswith("Trigger words:")
    assert metrics.horizontalAdvance(label) <= 191
    assert label != long_name


def test_prompt_editor_trigger_action_inserts_provider_words_without_suppression(
    prompt_widgets: list[QWidget],
) -> None:
    """Trigger actions should insert provider words even when prompt has duplicates."""

    app = ensure_qapp()
    editor = create_lora_prompt_editor(prompt_widgets)
    editor.setPlainText("imp_princess, portrait")
    process_events(app)
    cursor = editor.textCursor()
    cursor.setPosition(len(editor.toPlainText()))
    editor.setTextCursor(cursor)
    scheduled_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Friendly Midna",
        trained_words=("imp princess", "twili helmet"),
        source="cube_field",
    )

    action = trigger_words_action_for_lora(
        editor,
        scheduled_lora,
        prompt_text=editor.toPlainText(),
    )
    assert action is not None
    action.trigger()
    process_events(app)

    assert editor.toPlainText() == (
        "imp_princess, portrait, imp princess, twili helmet"
    )


def test_prompt_editor_trigger_action_uses_context_position_without_deleting_blank_line(
    prompt_widgets: list[QWidget],
) -> None:
    """Trigger insertion should not replace a stale caret on a nearby blank line."""

    app = ensure_qapp()
    editor = create_lora_prompt_editor(prompt_widgets)
    editor.setPlainText("alpha,\n\nbeta")
    process_events(app)
    stale_cursor = editor.textCursor()
    stale_cursor.setPosition(7)
    editor.setTextCursor(stale_cursor)
    cast(Any, editor)._set_context_menu_insert_state_for_tests(insert_position=6)

    action = trigger_words_action_for_lora(
        editor,
        PromptScheduledLora(
            prompt_name="midna",
            backend_value="midna.safetensors",
            display_name="Friendly Midna",
            trained_words=("trigger",),
            source="cube_field",
        ),
        prompt_text=editor.toPlainText(),
    )
    assert action is not None
    action.trigger()
    process_events(app)

    assert editor.toPlainText() == "alpha, trigger\n\nbeta"


def test_prompt_editor_trigger_action_ignores_selection_created_by_context_click(
    prompt_widgets: list[QWidget],
) -> None:
    """Context-click blank-line selection should not replace text on insertion."""

    app = ensure_qapp()
    editor = create_lora_prompt_editor(prompt_widgets)
    editor.setPlainText("alpha,\n\nbeta")
    process_events(app)
    incidental_cursor = editor.textCursor()
    incidental_cursor.setPosition(7)
    incidental_cursor.setPosition(8, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(incidental_cursor)
    cast(Any, editor)._set_context_menu_insert_state_for_tests(
        insert_position=6,
        should_replace_selection=False,
    )

    action = trigger_words_action_for_lora(
        editor,
        PromptScheduledLora(
            prompt_name="midna",
            backend_value="midna.safetensors",
            display_name="Friendly Midna",
            trained_words=("trigger",),
            source="cube_field",
        ),
        prompt_text=editor.toPlainText(),
    )
    assert action is not None
    action.trigger()
    process_events(app)

    assert editor.toPlainText() == "alpha, trigger\n\nbeta"


def test_prompt_editor_trigger_action_replaces_selection_like_paste(
    prompt_widgets: list[QWidget],
) -> None:
    """Trigger insertion should replace active selections before using context position."""

    app = ensure_qapp()
    editor = create_lora_prompt_editor(prompt_widgets)
    editor.setPlainText("alpha,\n\nbeta")
    process_events(app)
    cursor = editor.textCursor()
    cursor.setPosition(7)
    cursor.setPosition(8, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    cast(Any, editor)._set_context_menu_insert_state_for_tests(insert_position=6)

    action = trigger_words_action_for_lora(
        editor,
        PromptScheduledLora(
            prompt_name="midna",
            backend_value="midna.safetensors",
            display_name="Friendly Midna",
            trained_words=("trigger",),
            source="cube_field",
        ),
        prompt_text=editor.toPlainText(),
    )
    assert action is not None
    action.trigger()
    process_events(app)

    assert editor.toPlainText() == "alpha,\ntriggerbeta"


def test_prompt_editor_lora_picker_insertion_uses_shared_schedule_text(
    prompt_widgets: list[QWidget],
) -> None:
    """The context picker insertion path should use scheduler-safe default text."""

    app = ensure_qapp()
    editor = create_lora_prompt_editor(prompt_widgets)
    editor.setPlainText("")
    process_events(app)

    cast(Any, editor)._lora_picker_popup_presenter.insert_lora_schedule(
        _lora_item(
            display_name="Friendly Midna",
            basename="raw_midna",
            prompt_name=r"illustrious\characters\safe_midna",
        )
    )
    process_events(app)

    assert editor.toPlainText() == r"<lora:illustrious\characters\safe_midna:1.00>"


def _lora_item(
    *,
    display_name: str = "Midna",
    basename: str = "Midna",
    prompt_name: str = r"illustrious\characters\Midna",
) -> PromptLoraCatalogItem:
    """Return one LoRA catalog item for prompt-editor insertion tests."""

    return PromptLoraCatalogItem(
        display_name=display_name,
        display_subtitle=None,
        prompt_name=prompt_name,
        backend_value=f"{prompt_name}.safetensors",
        relative_path=f"{prompt_name}.safetensors",
        folder=r"illustrious\characters",
        basename=basename,
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="Illustrious",
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=basename.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=" ".join((display_name, basename, prompt_name)).casefold(),
    )
