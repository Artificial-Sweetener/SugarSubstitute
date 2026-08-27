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

"""Test LoRA metadata publication through the EditorPanel façade."""

from __future__ import annotations

import importlib
from types import ModuleType, SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch


def _panel_module() -> ModuleType:
    """Return the production editor-panel module."""

    return importlib.import_module("substitute.presentation.editor.panel.view")


def _controller_module() -> ModuleType:
    """Return the production LoRA metadata controller module."""

    return importlib.import_module(
        "substitute.presentation.editor.panel.lora_metadata_refresh_controller"
    )


def test_refresh_visible_lora_metadata_counts_dirty_visible_prompt_editors(
    monkeypatch: MonkeyPatch,
) -> None:
    """EditorPanel should count only prompt editors that refresh lazily."""

    panel_module = _panel_module()
    controller_module = _controller_module()

    class _PromptEditor:
        def __init__(self, refreshed: bool) -> None:
            self.refreshed = refreshed
            self.calls = 0

        def refresh_lora_metadata_if_visible(self) -> bool:
            self.calls += 1
            return self.refreshed

    monkeypatch.setattr(controller_module, "PromptEditor", _PromptEditor)
    visible_editor = _PromptEditor(True)
    hidden_editor = _PromptEditor(False)
    panel = SimpleNamespace(
        findChildren=lambda widget_type: (
            [visible_editor, hidden_editor] if widget_type is _PromptEditor else []
        )
    )

    refreshed_count = panel_module.EditorPanel.refresh_visible_lora_metadata(panel)

    assert refreshed_count == 1
    assert visible_editor.calls == 1
    assert hidden_editor.calls == 1


def test_mark_lora_metadata_dirty_marks_prompt_editors(
    monkeypatch: MonkeyPatch,
) -> None:
    """EditorPanel dirty marking should not rebuild prompt projection state."""

    panel_module = _panel_module()
    controller_module = _controller_module()

    class _PromptEditor:
        def __init__(self) -> None:
            self.mark_calls = 0

        def mark_lora_metadata_dirty(self) -> None:
            self.mark_calls += 1

    monkeypatch.setattr(controller_module, "PromptEditor", _PromptEditor)
    first_editor = _PromptEditor()
    second_editor = _PromptEditor()
    panel = SimpleNamespace(
        findChildren=lambda widget_type: (
            [first_editor, second_editor] if widget_type is _PromptEditor else []
        )
    )

    panel_module.EditorPanel.mark_lora_metadata_dirty(panel)

    assert first_editor.mark_calls == 1
    assert second_editor.mark_calls == 1
