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

"""Verify production prompt-editor mounting through the real shell."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QWidget
import pytest

from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)

from substitute.presentation.editor.panel.view import EditorPanel
from substitute.presentation.editor.prompt_editor import PromptEditor


def test_real_shell_mounts_prompt_editor_through_editor_panel(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Mount the production prompt editor through EditorPanel.load_all_cubes."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text="masterpiece"
    )
    panel = real_shell_scenario.shell.editor_panels[field.workflow.workflow_id]

    assert isinstance(panel, EditorPanel)
    assert isinstance(field.editor, PromptEditor)
    registry = getattr(panel, "input_widgets_by_field_key")
    assert (
        registry[(field.workflow.cube_alias, field.node_name, field.field_key)]
        is field.editor
    )
    assert panel.isAncestorOf(field.editor)
    assert field.editor.property("input_metadata")["cube_alias"] == (
        field.workflow.cube_alias
    )
    real_shell_scenario.input.focus_editor(field)
    assert field.editor.isVisible()


def test_real_shell_uses_composed_prompt_editor_collaborators(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Expose normal prompt-editor collaborators through the mounted shell."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    editor = field.editor

    assert isinstance(getattr(editor, "_surface", None), QWidget)
    assert getattr(editor, "_autocomplete", None) is not None
    assert getattr(editor, "_interaction_controller", None) is not None

    real_shell_scenario.input.type_text(field, "re")
    real_shell_scenario.wait_until(
        lambda: bool(real_shell_scenario.autocomplete_gateway.calls)
    )

    assert real_shell_scenario.autocomplete_gateway.calls[-1][0] == "re"
    assert getattr(editor, "_autocomplete_panel", None) is not None


def test_active_real_shell_does_not_request_reactivation(
    real_shell_scenario: PromptEditorRealShellScenario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preserve child focus by making repeated shell activation idempotent."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    focused_widget = real_shell_scenario.input.focus_editor(field)
    activation_requests: list[str] = []

    def record_activation(name: str) -> Callable[[], None]:
        """Return a spy that records a redundant top-level activation request."""

        return lambda: activation_requests.append(name)

    monkeypatch.setattr(
        real_shell_scenario.shell,
        "raise_",
        record_activation("raise"),
    )
    monkeypatch.setattr(
        real_shell_scenario.shell,
        "activateWindow",
        record_activation("activate"),
    )

    real_shell_scenario.shell.activate_for_input()

    assert QApplication.activeWindow() is real_shell_scenario.shell
    assert QApplication.focusWidget() is focused_widget
    assert activation_requests == []
