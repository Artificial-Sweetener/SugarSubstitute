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

"""Test rendered text-search refresh after prompt edits."""

from __future__ import annotations

from types import SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch
from substitute.application.editor_search import (
    EditorSearchMode,
    EditorSearchService,
    TextSearchMatch,
)
from substitute.application.node_behavior import EditorBehaviorSnapshot
from tests.support.node_behavior import build_behavior_snapshot, cube_state

import substitute.presentation.editor.panel.search_controller as mod


class _PromptEditor:
    """Record prompt search highlights and unexpected cursor changes."""

    def __init__(self, *, record_cursor_updates: bool) -> None:
        """Initialize rendered-search observations."""

        self.search_calls: list[tuple[tuple[tuple[int, int], ...], int | None]] = []
        self.clear_count = 0
        self.cursor_updates = 0 if record_cursor_updates else None
        self.last_query_identity: object | None = None

    def clear_search_matches(self) -> None:
        """Record transient search rendering clearing."""

        self.clear_count += 1

    def set_search_matches(
        self,
        matches: tuple[tuple[int, int], ...],
        active_index: int | None,
        *,
        query_identity: object | None = None,
    ) -> None:
        """Record rendered search ranges."""

        self.last_query_identity = query_identity
        self.search_calls.append((matches, active_index))

    def setTextCursor(self, _cursor: object) -> None:  # noqa: N802
        """Record cursor mutation attempts when the contract exposes them."""

        if self.cursor_updates is not None:
            self.cursor_updates += 1


def _behavior_snapshot(prompt_text: str) -> EditorBehaviorSnapshot:
    """Build a searchable one-prompt behavior snapshot."""

    return build_behavior_snapshot(
        cube_states={
            "A": cube_state(
                nodes={
                    "NodeA": {
                        "class_type": "PromptNode",
                        "inputs": {"prompt_template": prompt_text},
                    }
                }
            )
        },
        stack_order=["A"],
    )


def _search_controller(
    initial_snapshot: EditorBehaviorSnapshot,
    updated_snapshot: EditorBehaviorSnapshot,
    prompt: _PromptEditor,
) -> tuple[mod.EditorPanelSearchController, SimpleNamespace]:
    """Prepare an active text search with a replacement behavior snapshot."""

    service = EditorSearchService()
    query = service.build_query(mode=EditorSearchMode.TEXT, raw_text="dog")
    initial_result = service.build_result(initial_snapshot, query)
    panel = SimpleNamespace(
        input_widgets_by_field_key={("A", "NodeA", "prompt_template"): prompt},
        _stack_order=["A"],
        _cube_states={"A": object()},
        node_behavior_service=SimpleNamespace(
            build_snapshot=lambda **_kwargs: updated_snapshot
        ),
        _workflow_overrides=lambda: {},
    )
    controller = mod.EditorPanelSearchController(panel)
    controller._current_search_result = initial_result
    controller._navigation = mod.PanelSearchNavigationState(
        matches=initial_result.navigation_matches,
        index=0,
        needle="dog",
    )
    controller._publish_search_state()
    return controller, panel


def test_text_search_refresh_recomputes_prompt_highlight_offsets(
    monkeypatch: MonkeyPatch,
) -> None:
    """Refreshing text search should rebuild ranges after prompt insertions."""

    monkeypatch.setattr(mod, "PromptEditor", _PromptEditor)
    prompt = _PromptEditor(record_cursor_updates=True)
    controller, panel = _search_controller(
        _behavior_snapshot("dog alpha"),
        _behavior_snapshot("xxdog alpha"),
        prompt,
    )

    controller.refresh_editor_search_result_after_text_change()

    assert prompt.clear_count == 1
    assert prompt.search_calls == [(((2, 3),), 0)]
    assert prompt.cursor_updates == 0
    assert panel._current_search["matches"] == (
        TextSearchMatch("A", "NodeA", "prompt_template", 2, 3),
    )


def test_text_search_refresh_removes_prompt_highlight_when_match_disappears(
    monkeypatch: MonkeyPatch,
) -> None:
    """Refreshing text search should clear stale prompt ranges when no match remains."""

    monkeypatch.setattr(mod, "PromptEditor", _PromptEditor)
    prompt = _PromptEditor(record_cursor_updates=False)
    controller, panel = _search_controller(
        _behavior_snapshot("dog alpha"),
        _behavior_snapshot("cat alpha"),
        prompt,
    )

    controller.refresh_editor_search_result_after_text_change()

    assert prompt.clear_count == 1
    assert prompt.search_calls == []
    assert panel._current_search == {"matches": (), "index": -1, "needle": "dog"}
