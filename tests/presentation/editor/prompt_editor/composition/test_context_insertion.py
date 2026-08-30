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

"""Guard direct context-insertion construction ownership."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.presentation.editor.prompt_editor.composition import factory


_FACTORY_PATH = Path(factory.__file__)


def test_context_insertion_composition_receives_only_its_direct_callbacks() -> None:
    """Keep context insertion from rediscovering the public widget through context."""

    module = ast.parse(_FACTORY_PATH.read_text(encoding="utf-8"))
    method = next(
        node
        for node in ast.walk(module)
        if isinstance(node, ast.FunctionDef)
        and node.name == "build_context_insertion_service"
    )
    method_source = ast.get_source_segment(
        _FACTORY_PATH.read_text(encoding="utf-8"), method
    )

    assert method_source is not None
    assert "context.editor" not in method_source
    assert "cast(Any" not in method_source
    assert "cursor_provider=cursor_provider" in method_source
    assert "focus_restorer=focus_restorer" in method_source
    assert "source_text_provider=source_text_provider" in method_source


def test_scene_position_composition_receives_the_direct_source_callback() -> None:
    """Keep scene preparation from recovering prompt source through the widget."""

    source = _FACTORY_PATH.read_text(encoding="utf-8")

    assert "source_text=lambda: cast(Any, context.editor).toPlainText()" not in source
    assert "source_text=source_text_provider" in source
