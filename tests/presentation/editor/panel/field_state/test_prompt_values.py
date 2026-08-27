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

"""Test prompt source value restoration and persistence."""

from __future__ import annotations

from pytest import MonkeyPatch

from types import SimpleNamespace


from tests.presentation.editor.panel.field_state.support import (
    _Signal,
    _prepare_field_state_module,
    PromptEditorBase,
    field_state_controller,
)


def test_bind_node_widget_state_restores_and_persists_prompt_editor_buffer_values(
    monkeypatch: MonkeyPatch,
) -> None:
    """Prompt widgets should restore from the buffer and mark dirty only on real edits."""

    _prepare_field_state_module(monkeypatch)
    module = field_state_controller

    class _DirectPromptEditor(PromptEditorBase):
        def __init__(self) -> None:
            self._text = "ui-default"
            self._props: dict[str, object] = {}
            self.baseline_source_text_calls: list[str] = []
            self.textChanged = _Signal()

        def property(self, name: str) -> object | None:
            return self._props.get(name)

        def setProperty(self, name: str, value: object) -> None:
            self._props[name] = value

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, value: str) -> None:
            self._text = value

        def replaceBaselineSourceText(self, value: str) -> None:
            """Record authoritative buffer restores through the baseline API."""

            self.baseline_source_text_calls.append(value)
            self._text = value

    prompt_editor = _DirectPromptEditor()
    cube_state = SimpleNamespace(
        buffer={"nodes": {"positive_prompt": {"inputs": {"text": "from-buffer"}}}},
        dirty=False,
    )

    module.bind_node_widget_state(
        prompt_editor,
        cube_state,
        {"node_name": "positive_prompt", "key": "text"},
    )

    assert prompt_editor.property("input_metadata") == {
        "node_name": "positive_prompt",
        "key": "text",
    }
    assert prompt_editor.toPlainText() == "from-buffer"
    assert prompt_editor.baseline_source_text_calls == ["from-buffer"]
    assert cube_state.dirty is False

    prompt_editor.setPlainText("from-buffer")
    prompt_editor.textChanged.emit()
    assert cube_state.buffer["nodes"]["positive_prompt"]["inputs"]["text"] == (
        "from-buffer"
    )
    assert cube_state.dirty is False

    prompt_editor.setPlainText("updated prompt")
    prompt_editor.textChanged.emit()
    assert cube_state.buffer["nodes"]["positive_prompt"]["inputs"]["text"] == (
        "updated prompt"
    )
    assert cube_state.dirty is True


def test_bind_node_widget_state_preserves_escaped_prompt_source_verbatim(
    monkeypatch: MonkeyPatch,
) -> None:
    """Prompt widget wiring should restore and persist escaped source text unchanged."""

    _prepare_field_state_module(monkeypatch)
    module = field_state_controller

    class _DirectPromptEditor(PromptEditorBase):
        def __init__(self) -> None:
            self._text = ""
            self._props: dict[str, object] = {}
            self.textChanged = _Signal()

        def property(self, name: str) -> object | None:
            return self._props.get(name)

        def setProperty(self, name: str, value: object) -> None:
            self._props[name] = value

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, value: str) -> None:
            self._text = value

    prompt_editor = _DirectPromptEditor()
    cube_state = SimpleNamespace(
        buffer={
            "nodes": {"positive_prompt": {"inputs": {"text": r"painting \(medium\)"}}}
        },
        dirty=False,
    )

    module.bind_node_widget_state(
        prompt_editor,
        cube_state,
        {"node_name": "positive_prompt", "key": "text"},
    )

    assert prompt_editor.toPlainText() == r"painting \(medium\)"

    prompt_editor.setPlainText(r"vertin \(reverse:1999\)")
    prompt_editor.textChanged.emit()

    assert cube_state.buffer["nodes"]["positive_prompt"]["inputs"]["text"] == (
        r"vertin \(reverse:1999\)"
    )
    assert cube_state.dirty is True
