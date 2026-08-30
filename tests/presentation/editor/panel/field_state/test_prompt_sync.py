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

"""Qualify prompt-buffer synchronization through the field-state owner."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from _pytest.monkeypatch import MonkeyPatch

import substitute.presentation.editor.panel.field_state_controller as field_state_mod
from substitute.presentation.editor.panel.field_state_controller import (
    EditorPanelFieldStateController,
    EditorPanelFieldStateHost,
)


from tests.presentation.editor.panel.field_state.controller_support import (
    _CubeWidgetDouble,
    _PromptEditorDouble,
)


def test_sync_prompt_editor_values_from_buffers_restores_all_cubes(
    monkeypatch: MonkeyPatch,
) -> None:
    """Full prompt sync should restore every prompt widget and refresh diagnostics."""

    monkeypatch.setattr(field_state_mod, "PromptEditor", _PromptEditorDouble)
    first_prompt = _PromptEditorDouble(
        {"cube_alias": "A", "node_name": "prompt", "key": "text"},
        "stale",
    )
    second_prompt = _PromptEditorDouble(
        {"cube_alias": "B", "node_name": "prompt", "key": "text"},
        "unchanged",
    )
    scene_refreshes: list[str] = []
    host = SimpleNamespace(
        _cube_states={
            "A": SimpleNamespace(
                buffer={"nodes": {"prompt": {"inputs": {"text": "fresh"}}}}
            ),
            "B": SimpleNamespace(
                buffer={"nodes": {"prompt": {"inputs": {"text": "unchanged"}}}}
            ),
        },
        cube_widgets={
            "A": _CubeWidgetDouble([first_prompt]),
            "B": _CubeWidgetDouble([second_prompt]),
        },
        refresh_prompt_scene_diagnostics=lambda: scene_refreshes.append("refresh"),
    )

    EditorPanelFieldStateController(
        cast(EditorPanelFieldStateHost, host)
    ).sync_prompt_editor_values_from_buffers()

    assert first_prompt.toPlainText() == "fresh"
    assert first_prompt.baseline_replacements == ["fresh"]
    assert second_prompt.baseline_replacements == []
    assert scene_refreshes == ["refresh"]


def test_sync_prompt_editor_values_for_cube_scans_only_target_cube(
    monkeypatch: MonkeyPatch,
) -> None:
    """Cube-scoped prompt sync should avoid mutating unrelated cube widgets."""

    monkeypatch.setattr(field_state_mod, "PromptEditor", _PromptEditorDouble)
    target_prompt = _PromptEditorDouble(
        {"cube_alias": "A", "node_name": "prompt", "key": "text"},
        "old",
    )
    unrelated_prompt = _PromptEditorDouble(
        {"cube_alias": "B", "node_name": "prompt", "key": "text"},
        "unchanged",
    )
    host = SimpleNamespace(
        _cube_states={
            "A": SimpleNamespace(
                buffer={"nodes": {"prompt": {"inputs": {"text": "new"}}}}
            ),
            "B": SimpleNamespace(
                buffer={"nodes": {"prompt": {"inputs": {"text": "other"}}}}
            ),
        },
        cube_widgets={
            "A": _CubeWidgetDouble([target_prompt]),
            "B": _CubeWidgetDouble([unrelated_prompt]),
        },
        refresh_prompt_scene_diagnostics=lambda: None,
    )

    EditorPanelFieldStateController(
        cast(EditorPanelFieldStateHost, host)
    ).sync_prompt_editor_values_for_cube("A")

    assert target_prompt.toPlainText() == "new"
    assert unrelated_prompt.toPlainText() == "unchanged"
