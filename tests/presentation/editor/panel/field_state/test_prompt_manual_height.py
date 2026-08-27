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

"""Test prompt editor manual-height persistence."""

from __future__ import annotations

from pytest import MonkeyPatch

from types import SimpleNamespace


from tests.presentation.editor.panel.field_state.support import (
    _Signal,
    _as_prompt_editor,
    _prepare_field_state_module,
    PromptEditorBase,
    field_state_controller,
)


def test_bind_node_widget_state_restores_prompt_editor_manual_height(
    monkeypatch: MonkeyPatch,
) -> None:
    """Prompt widget wiring should apply stored manual height without dirtying restore."""

    _prepare_field_state_module(monkeypatch)
    module = field_state_controller
    monkeypatch.setattr(
        module,
        "QTimer",
        SimpleNamespace(singleShot=lambda _delay, callback: callback()),
    )

    class _DirectPromptEditor(PromptEditorBase):
        def __init__(self) -> None:
            self._text = ""
            self._manual_height: int | None = None
            self._props: dict[str, object] = {}
            self.textChanged = _Signal()
            self.manualScrollHeightChanged = _Signal()

        def property(self, name: str) -> object | None:
            return self._props.get(name)

        def setProperty(self, name: str, value: object) -> None:
            self._props[name] = value

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, value: str) -> None:
            self._text = value

        def setManualScrollHeight(self, height: int | None) -> None:
            self._manual_height = height
            self.manualScrollHeightChanged.emit(height)

        def manualScrollHeight(self) -> int | None:
            return self._manual_height

    prompt_editor = _DirectPromptEditor()
    autosaves: list[str] = []
    cube_state = SimpleNamespace(
        buffer={"nodes": {"positive_prompt": {"inputs": {"text": "from-buffer"}}}},
        dirty=False,
        ui={
            "prompt_editor_manual_heights": {
                "positive_prompt.text": 260,
            }
        },
    )

    module.bind_node_widget_state(
        prompt_editor,
        cube_state,
        {"node_name": "positive_prompt", "key": "text"},
        manual_prompt_height_changed=lambda: autosaves.append("autosave"),
    )

    assert prompt_editor.manualScrollHeight() == 260
    assert cube_state.dirty is False
    assert autosaves == []


def test_prompt_editor_manual_height_changes_update_cube_ui_and_autosave(
    monkeypatch: MonkeyPatch,
) -> None:
    """Manual prompt height changes should persist under cube UI metadata."""

    _prepare_field_state_module(monkeypatch)
    module = field_state_controller

    class _DirectPromptEditor(PromptEditorBase):
        def __init__(self) -> None:
            self._text = "from-buffer"
            self._props = {
                "input_metadata": {
                    "node_name": "positive_prompt",
                    "key": "text",
                }
            }
            self.textChanged = _Signal()
            self.manualScrollHeightChanged = _Signal()

        def property(self, name: str) -> object | None:
            return self._props.get(name)

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, value: str) -> None:
            self._text = value

        def setManualScrollHeight(self, height: int | None) -> None:
            self.manualScrollHeightChanged.emit(height)

    prompt_editor = _DirectPromptEditor()
    autosaves: list[str] = []
    cube_state = SimpleNamespace(
        buffer={"nodes": {"positive_prompt": {"inputs": {"text": "from-buffer"}}}},
        dirty=False,
        ui=None,
    )

    module.wire_prompt_editor_state(
        _as_prompt_editor(prompt_editor),
        cube_state,
        manual_height_changed=lambda: autosaves.append("autosave"),
    )
    prompt_editor.setManualScrollHeight(300)

    assert cube_state.ui == {
        "prompt_editor_manual_heights": {
            "positive_prompt.text": 300,
        }
    }
    assert cube_state.dirty is True
    assert autosaves == ["autosave"]


def test_prompt_editor_manual_height_clearing_removes_cube_ui_entry(
    monkeypatch: MonkeyPatch,
) -> None:
    """Clearing manual prompt height should remove the field-specific UI value."""

    _prepare_field_state_module(monkeypatch)
    module = field_state_controller
    monkeypatch.setattr(
        module,
        "QTimer",
        SimpleNamespace(singleShot=lambda _delay, callback: callback()),
    )

    class _DirectPromptEditor(PromptEditorBase):
        def __init__(self) -> None:
            self._text = "from-buffer"
            self._props = {
                "input_metadata": {
                    "node_name": "positive_prompt",
                    "key": "text",
                }
            }
            self.textChanged = _Signal()
            self.manualScrollHeightChanged = _Signal()

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
        ui={
            "prompt_editor_manual_heights": {
                "positive_prompt.text": 300,
            }
        },
    )

    module.wire_prompt_editor_state(_as_prompt_editor(prompt_editor), cube_state)
    prompt_editor.manualScrollHeightChanged.emit(None)

    assert cube_state.ui == {}
    assert cube_state.dirty is True


def test_prompt_editor_invalid_stored_manual_height_is_ignored(
    monkeypatch: MonkeyPatch,
) -> None:
    """Invalid persisted manual height values should not affect the prompt editor."""

    _prepare_field_state_module(monkeypatch)
    module = field_state_controller
    monkeypatch.setattr(
        module,
        "QTimer",
        SimpleNamespace(singleShot=lambda _delay, callback: callback()),
    )

    class _DirectPromptEditor(PromptEditorBase):
        def __init__(self) -> None:
            self._text = ""
            self._manual_height: int | None = None
            self._props: dict[str, object] = {}
            self.textChanged = _Signal()
            self.manualScrollHeightChanged = _Signal()

        def property(self, name: str) -> object | None:
            return self._props.get(name)

        def setProperty(self, name: str, value: object) -> None:
            self._props[name] = value

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, value: str) -> None:
            self._text = value

        def setManualScrollHeight(self, height: int | None) -> None:
            self._manual_height = height
            self.manualScrollHeightChanged.emit(height)

        def manualScrollHeight(self) -> int | None:
            return self._manual_height

    prompt_editor = _DirectPromptEditor()
    cube_state = SimpleNamespace(
        buffer={"nodes": {"positive_prompt": {"inputs": {"text": "from-buffer"}}}},
        dirty=False,
        ui={
            "prompt_editor_manual_heights": {
                "positive_prompt.text": "tall",
            }
        },
    )

    module.bind_node_widget_state(
        prompt_editor,
        cube_state,
        {"node_name": "positive_prompt", "key": "text"},
    )

    assert prompt_editor.manualScrollHeight() is None
    assert cube_state.dirty is False
