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

"""Test direct prompt-editor field-state dispatch."""

from __future__ import annotations

from pytest import MonkeyPatch

from types import SimpleNamespace


from tests.presentation.editor.panel.field_state.support import (
    _Signal,
    _prepare_field_state_module,
    PromptEditorBase,
    field_state_controller,
)


def test_wire_any_widget_state_uses_direct_prompt_editor_type_dispatch(
    monkeypatch: MonkeyPatch,
) -> None:
    """Generic wiring should recognize PromptEditor via its concrete type, not a string check."""

    _prepare_field_state_module(monkeypatch)
    module = field_state_controller

    class _DirectPromptEditor(PromptEditorBase):
        def __init__(self) -> None:
            self._text = "ui-default"
            self._props = {
                "input_metadata": {
                    "node_name": "positive_prompt",
                    "key": "text",
                }
            }
            self.textChanged = _Signal()

        def property(self, name: str) -> object | None:
            return self._props.get(name)

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, value: str) -> None:
            self._text = value

    prompt_editor = _DirectPromptEditor()
    cube_state = SimpleNamespace(
        buffer={"nodes": {"positive_prompt": {"inputs": {"text": "from-buffer"}}}},
        dirty=False,
    )

    module.wire_any_widget_state(prompt_editor, cube_state)

    assert prompt_editor.toPlainText() == "from-buffer"

    prompt_editor.setPlainText("updated prompt")
    prompt_editor.textChanged.emit()

    assert cube_state.buffer["nodes"]["positive_prompt"]["inputs"]["text"] == (
        "updated prompt"
    )
    assert cube_state.dirty is True
