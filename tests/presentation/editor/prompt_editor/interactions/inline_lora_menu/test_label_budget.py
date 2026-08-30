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

"""Test inline LoRA trigger label budget."""

from __future__ import annotations

from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor.interactions import (
    PromptTriggerWordActionAdapter,
)
from tests.presentation.editor.prompt_editor.interactions.inline_lora_menu.support import (
    InsertionExecutor,
    ensure_qapp,
)


def test_inline_lora_presenter_label_elides_to_menu_budget() -> None:
    """Long LoRA names should stay within the established trigger-word width."""

    ensure_qapp()
    adapter = PromptTriggerWordActionAdapter(
        action_parent=QWidget(),
        text_insertion_executor=InsertionExecutor(),
        identity_validator=lambda _identity: True,
    )
    long_name = (
        "Extremely Long CivitAI Friendly LoRA Name With Version Details And "
        "Training Notes That Would Otherwise Blow Out The Context Menu"
    )

    label = adapter.trigger_words_action_label(long_name)

    assert not label.startswith("Trigger words:")
    assert QFontMetrics(QApplication.font()).horizontalAdvance(label) <= 191
    assert label != long_name
