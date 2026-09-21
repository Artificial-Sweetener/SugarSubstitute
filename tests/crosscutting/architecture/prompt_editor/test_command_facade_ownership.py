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

"""Enforce focused ownership of the public prompt command boundary."""

from __future__ import annotations

import ast

from .inventory import PROMPT_PRESENTATION_ROOT


COMMAND_FACADE_METHODS = (
    "prompt_command_source_identity",
    "execute_autocomplete_acceptance",
    "execute_diagnostic_action",
    "execute_weight_action",
    "execute_reorder_action",
    "execute_source_replacement",
)


def test_command_facade_exclusively_owns_prepared_command_execution() -> None:
    """Keep prepared command routing out of the mixed QFluent shell."""

    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    facade_source = (PROMPT_PRESENTATION_ROOT / "command_facade.py").read_text(
        encoding="utf-8"
    )
    widget_tree = ast.parse(widget_source)
    editor_class = next(
        node
        for node in widget_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "PromptEditor"
    )

    assert any(
        isinstance(base, ast.Name) and base.id == "PromptEditorCommandFacade"
        for base in editor_class.bases
    )
    for method_name in COMMAND_FACADE_METHODS:
        declaration = f"def {method_name}("
        assert declaration in facade_source
        assert declaration not in widget_source
