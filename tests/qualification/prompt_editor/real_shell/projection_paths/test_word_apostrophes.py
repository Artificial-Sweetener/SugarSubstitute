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

"""Preserve rich prompt spans after loading or typing a trailing word apostrophe."""

from collections import Counter

from PySide6.QtCore import Qt
import pytest

from tests.support.prompt_editor.projection_engine_support import surface_for
from tests.support.prompt_editor.real_shell.models import PromptFieldHandle
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)

_SOURCE = r"(before:1.21), jack-o' challenge, <lora:ANIMA\retro:1.00>, (after:-1.00)"


@pytest.mark.parametrize("typed", (False, True), ids=("restored", "keyboard"))
def test_word_apostrophe_keeps_loras_and_weights_through_shell_transitions(
    real_shell_scenario: PromptEditorRealShellScenario, typed: bool
) -> None:
    """Keep source punctuation and later rich spans through editing and tab reuse."""
    initial = _SOURCE.replace("jack-o'", "jack-o") if typed else _SOURCE
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=initial)
    if typed:
        real_shell_scenario.input.set_source_cursor_position(
            field, initial.index("jack-o") + len("jack-o")
        )
        real_shell_scenario.input.press_key(field, Qt.Key.Key_Apostrophe, text="'")
    _assert_rich_spans(real_shell_scenario, field)

    field = real_shell_scenario.workflows.workflow_round_trip(field)
    _assert_rich_spans(real_shell_scenario, field)
    real_shell_scenario.input.set_rich_rendering(field, enabled=False)
    assert field.editor.toPlainText() == _SOURCE
    real_shell_scenario.input.set_rich_rendering(field, enabled=True)
    _assert_rich_spans(real_shell_scenario, field)


def _assert_rich_spans(
    scenario: PromptEditorRealShellScenario, field: PromptFieldHandle
) -> None:
    """Wait for semantic projection and require the exact authored source."""
    expected = {"emphasis": 2, "lora": 1}
    scenario.wait_until(
        lambda: (
            Counter(
                token.kind.value
                for token in surface_for(field.editor).projection_document().tokens
            )
            == expected
            and scenario.snapshots.capture(
                field, label="word-apostrophe-settling", settle=False
            ).projection_is_current
        ),
        description="rich spans after word apostrophe",
    )
    snapshot = scenario.snapshots.capture(field, label="word-apostrophe-rich")
    assert snapshot.source_text == _SOURCE
    assert field.editor.richPromptRenderingEnabled()
    assert snapshot.projection_is_current
