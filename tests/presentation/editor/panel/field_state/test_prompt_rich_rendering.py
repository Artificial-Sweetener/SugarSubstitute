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

"""Test prompt editor rich-rendering persistence."""

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


def test_prompt_editor_missing_rich_rendering_state_keeps_default_enabled(
    monkeypatch: MonkeyPatch,
) -> None:
    """Missing prompt rich-rendering UI metadata should keep the default enabled state."""

    _prepare_field_state_module(monkeypatch)
    module = field_state_controller

    class _DirectPromptEditor(PromptEditorBase):
        def __init__(self) -> None:
            self._text = ""
            self._rich_enabled = True
            self._props = {
                "input_metadata": {
                    "node_name": "positive_prompt",
                    "key": "text",
                }
            }
            self.textChanged = _Signal()
            self.richPromptRenderingEnabledChanged = _Signal()

        def property(self, name: str) -> object | None:
            return self._props.get(name)

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, value: str) -> None:
            self._text = value

        def setSourceText(self, value: str) -> None:
            self._text = value

        def richPromptRenderingEnabled(self) -> bool:
            return self._rich_enabled

        def setRichPromptRenderingEnabled(self, enabled: bool) -> None:
            self._rich_enabled = enabled
            self.richPromptRenderingEnabledChanged.emit(enabled)

    prompt_editor = _DirectPromptEditor()
    cube_state = SimpleNamespace(
        buffer={"nodes": {"positive_prompt": {"inputs": {"text": "from-buffer"}}}},
        dirty=False,
        ui={},
    )

    module.wire_prompt_editor_state(_as_prompt_editor(prompt_editor), cube_state)

    assert prompt_editor.richPromptRenderingEnabled() is True
    assert cube_state.dirty is False


def test_prompt_editor_restores_disabled_rich_rendering_without_dirtying(
    monkeypatch: MonkeyPatch,
) -> None:
    """Stored false rich-rendering preference should restore as raw mode state."""

    _prepare_field_state_module(monkeypatch)
    module = field_state_controller

    class _DirectPromptEditor(PromptEditorBase):
        def __init__(self) -> None:
            self._text = ""
            self._rich_enabled = True
            self._props = {
                "input_metadata": {
                    "node_name": "positive_prompt",
                    "key": "text",
                }
            }
            self.textChanged = _Signal()
            self.richPromptRenderingEnabledChanged = _Signal()

        def property(self, name: str) -> object | None:
            return self._props.get(name)

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, value: str) -> None:
            self._text = value

        def setSourceText(self, value: str) -> None:
            self._text = value

        def richPromptRenderingEnabled(self) -> bool:
            return self._rich_enabled

        def setRichPromptRenderingEnabled(self, enabled: bool) -> None:
            self._rich_enabled = enabled
            self.richPromptRenderingEnabledChanged.emit(enabled)

    prompt_editor = _DirectPromptEditor()
    cube_state = SimpleNamespace(
        buffer={"nodes": {"positive_prompt": {"inputs": {"text": "from-buffer"}}}},
        dirty=False,
        ui={
            "prompt_editor_rich_rendering": {
                "positive_prompt.text": False,
            }
        },
    )

    module.wire_prompt_editor_state(_as_prompt_editor(prompt_editor), cube_state)

    assert prompt_editor.richPromptRenderingEnabled() is False
    assert cube_state.dirty is False


def test_prompt_editor_invalid_rich_rendering_state_is_ignored(
    monkeypatch: MonkeyPatch,
) -> None:
    """Invalid rich-rendering UI metadata should not affect prompt editor restore."""

    _prepare_field_state_module(monkeypatch)
    module = field_state_controller

    class _DirectPromptEditor(PromptEditorBase):
        def __init__(self) -> None:
            self._text = ""
            self._rich_enabled = True
            self._props = {
                "input_metadata": {
                    "node_name": "positive_prompt",
                    "key": "text",
                }
            }
            self.textChanged = _Signal()
            self.richPromptRenderingEnabledChanged = _Signal()

        def property(self, name: str) -> object | None:
            return self._props.get(name)

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, value: str) -> None:
            self._text = value

        def setSourceText(self, value: str) -> None:
            self._text = value

        def richPromptRenderingEnabled(self) -> bool:
            return self._rich_enabled

        def setRichPromptRenderingEnabled(self, enabled: bool) -> None:
            self._rich_enabled = enabled
            self.richPromptRenderingEnabledChanged.emit(enabled)

    prompt_editor = _DirectPromptEditor()
    cube_state = SimpleNamespace(
        buffer={"nodes": {"positive_prompt": {"inputs": {"text": "from-buffer"}}}},
        dirty=False,
        ui={
            "prompt_editor_rich_rendering": {
                "positive_prompt.text": "sometimes",
            }
        },
    )

    module.wire_prompt_editor_state(_as_prompt_editor(prompt_editor), cube_state)

    assert prompt_editor.richPromptRenderingEnabled() is True
    assert cube_state.dirty is False


def test_prompt_editor_rich_rendering_changes_update_cube_ui_and_autosave(
    monkeypatch: MonkeyPatch,
) -> None:
    """Prompt rich-rendering changes should persist under cube UI metadata."""

    _prepare_field_state_module(monkeypatch)
    module = field_state_controller

    class _DirectPromptEditor(PromptEditorBase):
        def __init__(self) -> None:
            self._text = "from-buffer"
            self._rich_enabled = True
            self._props = {
                "input_metadata": {
                    "node_name": "positive_prompt",
                    "key": "text",
                }
            }
            self.textChanged = _Signal()
            self.richPromptRenderingEnabledChanged = _Signal()

        def property(self, name: str) -> object | None:
            return self._props.get(name)

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, value: str) -> None:
            self._text = value

        def setSourceText(self, value: str) -> None:
            self._text = value

        def setRichPromptRenderingEnabled(self, enabled: bool) -> None:
            self._rich_enabled = enabled
            self.richPromptRenderingEnabledChanged.emit(enabled)

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
    prompt_editor.setRichPromptRenderingEnabled(False)

    assert cube_state.ui == {
        "prompt_editor_rich_rendering": {
            "positive_prompt.text": False,
        }
    }
    assert cube_state.dirty is True
    assert autosaves == ["autosave"]

    cube_state.dirty = False
    prompt_editor.setRichPromptRenderingEnabled(True)

    assert cube_state.ui == {}
    assert cube_state.dirty is True
    assert autosaves == ["autosave", "autosave"]
