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

"""Test panel text-search navigation behavior."""

from __future__ import annotations

import importlib
from types import ModuleType, SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch
from substitute.application.editor_search import TextSearchMatch


def _panel_module() -> ModuleType:
    """Return the production editor-panel module."""

    return importlib.import_module("substitute.presentation.editor.panel.view")


def _search_module() -> ModuleType:
    """Return the production editor-panel search controller module."""

    return importlib.import_module(
        "substitute.presentation.editor.panel.search_controller"
    )


def test_search_and_select_cycles_matches_and_updates_scroll_targets() -> None:
    """Search navigation should cycle matches in stable order."""

    panel_module = _panel_module()
    search_module = _search_module()

    class _LineEdit:
        def __init__(self) -> None:
            self.selections: list[tuple[int, int]] = []
            self.deselect_count = 0

        def setSelection(self, start: int, length: int) -> None:  # noqa: N802
            self.selections.append((start, length))

        def deselect(self) -> None:
            self.deselect_count += 1

    first = _LineEdit()
    second = _LineEdit()
    matches = (
        TextSearchMatch("CubeA", "NodeA", "field_a", 4, 3),
        TextSearchMatch("CubeA", "NodeA", "field_b", 0, 3),
    )
    cube_scroll_calls: list[tuple[str, bool]] = []
    widget_scroll_calls: list[tuple[object, bool]] = []
    panel = SimpleNamespace(
        input_widgets_by_field_key={
            ("CubeA", "NodeA", "field_a"): first,
            ("CubeA", "NodeA", "field_b"): second,
        },
        scroll_to_cube=lambda alias, animated=True: cube_scroll_calls.append(
            (alias, animated)
        ),
        scroll_to_input_widget=lambda widget, animated=True: widget_scroll_calls.append(
            (widget, animated)
        ),
    )
    controller = search_module.EditorPanelSearchController(panel)
    controller._navigation = search_module.PanelSearchNavigationState(
        matches=matches,
        index=-1,
        needle="dog",
    )
    controller._publish_search_state()
    panel._search_controller = controller

    panel_module.EditorPanel.search_and_select(panel, "dog", direction="next")
    panel_module.EditorPanel.search_and_select(panel, "dog", direction="next")
    panel_module.EditorPanel.search_and_select(panel, "", direction="next")

    assert first.selections[0] == (4, 3)
    assert second.selections[0] == (0, 3)
    assert panel._current_search == {"matches": (), "index": -1, "needle": ""}
    assert cube_scroll_calls[:2] == [("CubeA", True), ("CubeA", True)]
    assert widget_scroll_calls[0][0] is first
    assert widget_scroll_calls[1][0] is second
    assert first.deselect_count >= 1
    assert second.deselect_count >= 1


def test_search_and_select_includes_prompt_widgets_and_clears_prompt_selection(
    monkeypatch: MonkeyPatch,
) -> None:
    """Prompt-widget navigation should select and clear cursor search ranges."""

    panel_module = _panel_module()
    search_module = _search_module()

    class _PromptCursor:
        def __init__(self) -> None:
            self.selection_start = 0
            self.selection_length = 0
            self.clear_count = 0

        def setPosition(self, position: int, _mode: object = None) -> None:  # noqa: N802
            self.selection_start = position
            self.selection_length = 0

        def movePosition(
            self,
            _direction: object,
            _mode: object = None,
            length: int = 0,
        ) -> None:  # noqa: N802
            self.selection_length = length

        def clearSelection(self) -> None:  # noqa: N802
            self.selection_length = 0
            self.clear_count += 1

    class _PromptEditor:
        def __init__(self) -> None:
            self._cursor = _PromptCursor()
            self.applied_selections: list[tuple[int, int]] = []
            self.clear_count = 0

        def textCursor(self) -> _PromptCursor:  # noqa: N802
            return self._cursor

        def setTextCursor(self, cursor: _PromptCursor) -> None:  # noqa: N802
            self._cursor = cursor
            self.applied_selections.append(
                (cursor.selection_start, cursor.selection_length)
            )
            self.clear_count = cursor.clear_count

        def clear_search_matches(self) -> None:
            """Satisfy the search-editor rendering contract."""

    monkeypatch.setattr(search_module, "PromptEditor", _PromptEditor)
    monkeypatch.setattr(
        search_module,
        "QTextCursor",
        SimpleNamespace(
            MoveOperation=SimpleNamespace(Right="right"),
            MoveMode=SimpleNamespace(KeepAnchor="keep"),
        ),
    )

    prompt = _PromptEditor()
    cube_scroll_calls: list[tuple[str, bool]] = []
    widget_scroll_calls: list[tuple[object, bool]] = []
    panel = SimpleNamespace(
        input_widgets_by_field_key={("CubeA", "NodeA", "prompt_template"): prompt},
        scroll_to_cube=lambda alias, animated=True: cube_scroll_calls.append(
            (alias, animated)
        ),
        scroll_to_input_widget=lambda widget, animated=True: widget_scroll_calls.append(
            (widget, animated)
        ),
    )
    controller = search_module.EditorPanelSearchController(panel)
    controller._navigation = search_module.PanelSearchNavigationState(
        matches=(TextSearchMatch("CubeA", "NodeA", "prompt_template", 4, 3),),
        index=-1,
        needle="dog",
    )
    controller._publish_search_state()
    panel._search_controller = controller

    panel_module.EditorPanel.search_and_select(panel, "dog", direction="next")

    assert panel._current_search["needle"] == "dog"
    assert prompt.applied_selections[-1] == (4, 3)
    assert cube_scroll_calls == [("CubeA", True)]
    assert widget_scroll_calls == [(prompt, True)]

    panel_module.EditorPanel.search_and_select(panel, "", direction="next")

    assert prompt.clear_count >= 1
    assert panel._current_search == {"matches": (), "index": -1, "needle": ""}
