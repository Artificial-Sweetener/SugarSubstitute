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

"""Test prompt-widget synchronization from workflow buffers."""

from __future__ import annotations

import importlib
from types import ModuleType, SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch


class _PromptEditor:
    """Expose mutable prompt text and input metadata."""

    def __init__(self, metadata: dict[str, str], text: str) -> None:
        """Initialize prompt widget state."""

        self._metadata = metadata
        self._text = text

    def property(self, name: str) -> object | None:
        """Return Qt-style input metadata."""

        return self._metadata if name == "input_metadata" else None

    def toPlainText(self) -> str:  # noqa: N802
        """Return current prompt text."""

        return self._text

    def setPlainText(self, text: str) -> None:  # noqa: N802
        """Replace prompt text."""

        self._text = text


class _CubeWidget:
    """Expose prompt-editor child discovery."""

    def __init__(self, prompt_editor: _PromptEditor) -> None:
        """Store one prompt editor child."""

        self._prompt_editor = prompt_editor

    def findChildren(self, widget_type: type[_PromptEditor]) -> list[_PromptEditor]:  # noqa: N802
        """Return the prompt editor when requested."""

        return [self._prompt_editor] if widget_type is _PromptEditor else []


def _panel_module() -> ModuleType:
    """Return the production editor-panel module."""

    return importlib.import_module("substitute.presentation.editor.panel.view")


def _field_state_module() -> ModuleType:
    """Return the production field-state controller module."""

    return importlib.import_module(
        "substitute.presentation.editor.panel.field_state_controller"
    )


def test_sync_prompt_editor_values_from_buffers_restores_reused_prompt_widgets(
    monkeypatch: MonkeyPatch,
) -> None:
    """Prompt synchronization should restore reconciled buffer text into reused widgets."""

    panel_module = _panel_module()
    field_state_module = _field_state_module()
    monkeypatch.setattr(field_state_module, "PromptEditor", _PromptEditor)
    prompt_editor = _PromptEditor(
        {
            "cube_alias": "CubeA",
            "node_name": "positive_prompt",
            "key": "prompt_template",
        },
        "stale",
    )
    panel = SimpleNamespace(
        _cube_states={
            "CubeA": SimpleNamespace(
                buffer={
                    "nodes": {
                        "positive_prompt": {
                            "inputs": {"prompt_template": "fresh shared prompt"}
                        }
                    }
                }
            )
        },
        cube_widgets={"CubeA": _CubeWidget(prompt_editor)},
        refresh_prompt_scene_diagnostics=lambda: None,
    )

    panel_module.EditorPanel.sync_prompt_editor_values_from_buffers(panel)

    assert prompt_editor.toPlainText() == "fresh shared prompt"
