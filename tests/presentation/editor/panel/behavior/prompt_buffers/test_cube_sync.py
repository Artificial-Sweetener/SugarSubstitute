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

"""Test editor-panel prompt-buffer synchronization contracts."""

from __future__ import annotations

import importlib
from types import ModuleType, SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch


class _PromptEditorDouble:
    """Store prompt metadata and mutable text."""

    def __init__(self, metadata: dict[str, object], text: str) -> None:
        """Initialize metadata and text."""

        self._metadata = metadata
        self._text = text

    def property(self, name: str) -> object | None:
        """Return Qt-style input metadata."""

        return self._metadata if name == "input_metadata" else None

    def toPlainText(self) -> str:  # noqa: N802
        """Return the current prompt text."""

        return self._text

    def setPlainText(self, text: str) -> None:  # noqa: N802
        """Replace the current prompt text."""

        self._text = text


class _CubeWidgetDouble:
    """Expose prompt-editor children for one cube."""

    def __init__(self, children: list[_PromptEditorDouble]) -> None:
        """Initialize with the owned prompt editors."""

        self._children = children

    def findChildren(self, _widget_type: object) -> list[_PromptEditorDouble]:  # noqa: N802
        """Return the owned prompt editors."""

        return list(self._children)


def _panel_module() -> ModuleType:
    """Return the production editor-panel module."""

    return importlib.import_module("substitute.presentation.editor.panel.view")


def test_sync_prompt_editor_values_for_cube_updates_only_target_cube(
    monkeypatch: MonkeyPatch,
) -> None:
    """Cube-scoped prompt sync should not mutate unrelated cube widgets."""

    module = _panel_module()
    field_state_module = importlib.import_module(
        "substitute.presentation.editor.panel.field_state_controller"
    )
    monkeypatch.setattr(field_state_module, "PromptEditor", _PromptEditorDouble)
    target_prompt = _PromptEditorDouble(
        {
            "cube_alias": "A",
            "node_name": "prompt",
            "key": "text",
        },
        "old",
    )
    unrelated_prompt = _PromptEditorDouble(
        {
            "cube_alias": "B",
            "node_name": "prompt",
            "key": "text",
        },
        "unchanged",
    )
    panel = SimpleNamespace(
        _cube_states={
            "A": SimpleNamespace(
                buffer={"nodes": {"prompt": {"inputs": {"text": "new text"}}}}
            ),
            "B": SimpleNamespace(
                buffer={"nodes": {"prompt": {"inputs": {"text": "other text"}}}}
            ),
        },
        cube_widgets={
            "A": _CubeWidgetDouble([target_prompt]),
            "B": _CubeWidgetDouble([unrelated_prompt]),
        },
        refresh_prompt_scene_diagnostics=lambda: None,
    )

    module.EditorPanel.sync_prompt_editor_values_for_cube(panel, "A")

    assert target_prompt.toPlainText() == "new text"
    assert unrelated_prompt.toPlainText() == "unchanged"
