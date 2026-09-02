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

"""Verify LoRA-aware prompt actions contributed to node-card menus."""

from __future__ import annotations

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.lora.scheduled import PromptScheduledLora
from substitute.presentation.editor.field_actions import FieldActionContext
from substitute.presentation.widgets.menu_model import LazyMenuSubmenu, MenuItem
from tests.presentation.editor.prompt_editor.context_menu.mounting import (
    create_lora_prompt_editor_with_resolver,
)


def test_lora_field_actions_publish_all_semantics_without_edit_commands(
    prompt_widgets: list[QWidget],
) -> None:
    """Expose the complete semantic prompt menu without local edit commands."""

    scheduled_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Friendly Midna",
        trained_words=("imp princess",),
        source="cube_field",
    )
    editor = create_lora_prompt_editor_with_resolver(
        prompt_widgets,
        scheduled_lora_resolver=lambda _prompt: (scheduled_lora,),
    )

    entries = editor.field_action_entries(FieldActionContext(QPoint(20, 30)))
    labels = {
        entry.label
        for entry in entries
        if isinstance(entry, (LazyMenuSubmenu, MenuItem))
    }
    action_ids = {entry.action_id for entry in entries if isinstance(entry, MenuItem)}

    assert {
        "Insert trigger words",
        "Schedule LoRA",
        "Rich prompt rendering",
    }.issubset(labels)
    assert action_ids.isdisjoint(
        {
            "prompt.undo",
            "prompt.redo",
            "prompt.cut",
            "prompt.copy",
            "prompt.paste",
            "prompt.select_all",
        }
    )
