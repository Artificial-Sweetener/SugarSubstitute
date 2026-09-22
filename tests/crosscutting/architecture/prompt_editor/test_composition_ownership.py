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

"""Enforce direct ownership for prompt-editor composition families."""

from __future__ import annotations

import ast

from .inventory import PROMPT_PRESENTATION_ROOT


def _class_methods(path_name: str, class_name: str) -> set[str]:
    """Return directly declared method names for one composition class."""
    path = PROMPT_PRESENTATION_ROOT / "composition" / path_name
    tree = ast.parse(path.read_text(encoding="utf-8"))
    class_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    return {
        node.name
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_projection_and_execution_composition_have_direct_owners() -> None:
    """Keep projection and async construction out of the mixed factory."""
    assert not (PROMPT_PRESENTATION_ROOT / "composition" / "factory.py").exists()
    execution_methods = _class_methods(
        "execution_factory.py",
        "PromptEditorExecutionFactory",
    )
    projection_methods = _class_methods(
        "projection_factory.py",
        "PromptEditorProjectionFactory",
    )

    assert {"build_task_executor", "build_request_channel"} <= execution_methods
    assert "build" in projection_methods

    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    assert "PromptEditorExecutionFactory(" in widget_source
    assert "PromptEditorProjectionFactory(" in widget_source


def test_autocomplete_and_menu_composition_have_direct_owners() -> None:
    """Keep autocomplete and menu construction out of the mixed factory."""
    autocomplete_methods = _class_methods(
        "autocomplete_factory.py",
        "PromptEditorAutocompleteFactory",
    )
    menu_methods = _class_methods("menu_factory.py", "PromptEditorMenuFactory")

    assert "build" in autocomplete_methods
    assert {
        "build_prompt_menu_presenter",
        "build_inline_lora_menu_presenter",
        "build_lora_picker_popup_presenter",
    } <= menu_methods

    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    menu_runtime_source = (
        PROMPT_PRESENTATION_ROOT / "composition" / "menu_runtime.py"
    ).read_text(encoding="utf-8")
    assert "PromptEditorAutocompleteFactory(" in widget_source
    assert "build_prompt_editor_menu_runtime(" in widget_source
    assert "PromptEditorMenuFactory(" in menu_runtime_source
    assert "PromptContextMenuSnapshotAssembler(" in menu_runtime_source
    assert "PromptShellContextMenuController(" in menu_runtime_source
    assert "_shell_context_menu" not in widget_source
    assert "_prompt_menu_presenter" not in widget_source
    assert "_inline_lora_menu_presenter" not in widget_source


def test_syntax_interaction_composition_has_a_direct_owner() -> None:
    """Keep syntax, reorder, and weight construction out of the mixed factory."""
    syntax_methods = _class_methods("syntax_factory.py", "PromptEditorSyntaxFactory")

    assert "build" in syntax_methods

    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    assert "PromptEditorSyntaxFactory(" in widget_source
