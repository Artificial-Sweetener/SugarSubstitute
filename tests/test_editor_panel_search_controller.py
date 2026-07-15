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

"""Characterize editor-panel search controller ownership."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import cast

from _pytest.monkeypatch import MonkeyPatch
from PySide6.QtCore import QTimer

from substitute.application.editor_search import (
    EditorSearchMode,
    EditorSearchResult,
    EditorSearchService,
)
from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.presentation.editor.panel.search_controller import (
    EditorPanelSearchController,
    EditorPanelSearchHost,
    SearchPromptEditorProtocol,
    SignalConnectorProtocol,
)
from tests.node_behavior_test_helpers import build_behavior_snapshot, cube_state


class _SignalDouble:
    """Record connected callbacks for prompt-editor signal wiring."""

    def __init__(self) -> None:
        """Initialize an empty callback list."""

        self.callbacks: list[Callable[[], None]] = []

    def connect(self, callback: Callable[[], None]) -> None:
        """Record one connected callback."""

        self.callbacks.append(callback)


class _PromptEditorDouble:
    """Provide the prompt-editor surface used by search refresh wiring."""

    def __init__(self) -> None:
        """Initialize dynamic properties and clear-call accounting."""

        self.textChanged: SignalConnectorProtocol = _SignalDouble()
        self.properties: dict[str, object] = {}
        self.clear_count = 0

    def property(self, name: str) -> object:
        """Return one dynamic property value."""

        return self.properties.get(name)

    def setProperty(self, name: str, value: object) -> object:
        """Record one dynamic property update."""

        self.properties[name] = value
        return value

    def clear_search_matches(self) -> None:
        """Record search-match clearing."""

        self.clear_count += 1


class _SnapshotService:
    """Return a supplied behavior snapshot and record build inputs."""

    def __init__(self, snapshot: EditorBehaviorSnapshot) -> None:
        """Store the snapshot returned to controller callers."""

        self.snapshot = snapshot
        self.calls: list[dict[str, object]] = []

    def build_snapshot(
        self,
        *,
        cube_states: Mapping[str, object],
        stack_order: list[str],
        workflow_overrides: Mapping[str, object],
        search_hidden_keys: set[object],
        node_search_text: str | None,
        search_matching_nodes: set[tuple[str, str]] | None,
    ) -> EditorBehaviorSnapshot:
        """Record search-corpus inputs and return the configured snapshot."""

        self.calls.append(
            {
                "cube_states": cube_states,
                "stack_order": stack_order,
                "workflow_overrides": workflow_overrides,
                "search_hidden_keys": search_hidden_keys,
                "node_search_text": node_search_text,
                "search_matching_nodes": search_matching_nodes,
            }
        )
        return self.snapshot


class _SearchHost:
    """Provide the editor-panel host surface consumed by the search controller."""

    def __init__(self, snapshot: EditorBehaviorSnapshot | None = None) -> None:
        """Initialize host state and call accounting."""

        if snapshot is None:
            snapshot = _snapshot_with_prompt_text("dog alpha")
        self.node_behavior_service = _SnapshotService(snapshot)
        self.input_widgets_by_field_key: dict[tuple[str, str, str], object] = {}
        self._cube_states: Mapping[str, object] | None = {"A": object()}
        self._stack_order: list[str] | None = ["A"]
        self._current_node_search_text: str | None = "stale"
        self._current_search_hidden_keys: set[object] = {"seed"}
        self._current_search_matching_nodes: set[tuple[str, str]] | None = {
            ("A", "NodeA")
        }
        self._current_search_result: EditorSearchResult | None = None
        self._current_search: dict[str, object] = {
            "matches": ("stale",),
            "index": 0,
            "needle": "dog",
        }
        self._text_search_refresh_pending = True
        self.field_calls: list[tuple[set[tuple[str, str, str]] | None, bool]] = []
        self.refresh_calls: list[dict[str, object]] = []
        self.cube_scroll_calls: list[tuple[str, bool]] = []
        self.widget_scroll_calls: list[tuple[object, bool]] = []

    def _workflow_overrides(self) -> Mapping[str, object]:
        """Return workflow overrides for snapshot construction."""

        return {"override": True}

    def refresh_node_behavior_state(
        self,
        search_hidden_keys: set[object] | None = None,
        node_search_text: str | None = None,
        search_matching_nodes: set[tuple[str, str]] | None = None,
        *,
        reason: str = "search_changed",
    ) -> None:
        """Record one behavior refresh request."""

        self.refresh_calls.append(
            {
                "search_hidden_keys": search_hidden_keys,
                "node_search_text": node_search_text,
                "search_matching_nodes": search_matching_nodes,
                "reason": reason,
            }
        )

    def set_search_field_match_keys(
        self,
        match_keys: set[tuple[str, str, str]] | None,
        *,
        active: bool,
    ) -> None:
        """Record one field-search publication."""

        self.field_calls.append((match_keys, active))

    def scroll_to_cube(self, cube_alias: str, *, animated: bool = True) -> None:
        """Record one cube reveal request."""

        self.cube_scroll_calls.append((cube_alias, animated))

    def scroll_to_input_widget(self, widget: object, *, animated: bool = True) -> None:
        """Record one input-widget reveal request."""

        self.widget_scroll_calls.append((widget, animated))


def _snapshot_with_prompt_text(text: str) -> EditorBehaviorSnapshot:
    """Build one minimal snapshot with a searchable prompt field."""

    return build_behavior_snapshot(
        cube_states={
            "A": cube_state(
                nodes={
                    "NodeA": {
                        "class_type": "PromptNode",
                        "inputs": {"prompt_template": text},
                    }
                }
            )
        },
        stack_order=["A"],
    )


def _text_search_result(text: str = "dog alpha") -> EditorSearchResult:
    """Return a text-search result for one prompt value."""

    service = EditorSearchService()
    return service.build_result(
        _snapshot_with_prompt_text(text),
        service.build_query(mode=EditorSearchMode.TEXT, raw_text="dog"),
    )


def test_prompt_text_search_refresh_wiring_is_idempotent() -> None:
    """Prompt text refresh wiring should connect one callback per editor."""

    host = _SearchHost()
    controller = EditorPanelSearchController(cast(EditorPanelSearchHost, host))
    prompt_editor = _PromptEditorDouble()

    controller.configure_prompt_text_search_refresh(
        cast(SearchPromptEditorProtocol, prompt_editor)
    )
    controller.configure_prompt_text_search_refresh(
        cast(SearchPromptEditorProtocol, prompt_editor)
    )

    assert prompt_editor.properties["promptTextSearchRefreshTracked"] is True
    assert len(cast(_SignalDouble, prompt_editor.textChanged).callbacks) == 1


def test_text_search_refresh_scheduling_clears_editor_and_coalesces(
    monkeypatch: MonkeyPatch,
) -> None:
    """Text-search refresh scheduling should clear edited ranges and coalesce timers."""

    queued_callbacks: list[Callable[[], None]] = []
    monkeypatch.setattr(
        QTimer,
        "singleShot",
        lambda _delay_ms, callback: queued_callbacks.append(callback),
    )
    host = _SearchHost()
    controller = EditorPanelSearchController(cast(EditorPanelSearchHost, host))
    controller.apply_search_result(_text_search_result())
    prompt_editor = _PromptEditorDouble()

    controller.schedule_text_search_refresh(
        cast(SearchPromptEditorProtocol, prompt_editor)
    )
    controller.schedule_text_search_refresh(
        cast(SearchPromptEditorProtocol, prompt_editor)
    )

    assert prompt_editor.clear_count == 2
    assert host._text_search_refresh_pending is True
    assert len(queued_callbacks) == 1

    queued_callbacks[0]()

    assert host._text_search_refresh_pending is False


def test_clear_search_filters_resets_mirrors_and_visibility() -> None:
    """Clearing search should reset mirrored state and request unfiltered visibility."""

    host = _SearchHost()
    controller = EditorPanelSearchController(cast(EditorPanelSearchHost, host))
    controller.apply_search_result(_text_search_result())

    controller.clear_search_filters()

    assert host._current_node_search_text is None
    assert host._current_search_hidden_keys == set()
    assert host._current_search_matching_nodes is None
    assert host._current_search_result is None
    assert host._current_search == {"matches": (), "index": -1, "needle": ""}
    assert host.field_calls[-1] == (None, False)
    assert host.refresh_calls[-1] == {
        "search_hidden_keys": set(),
        "node_search_text": None,
        "search_matching_nodes": None,
        "reason": "search_changed",
    }


def test_build_search_corpus_snapshot_uses_unfiltered_inputs() -> None:
    """Search corpus snapshots should ignore active search filter mirrors."""

    snapshot = _snapshot_with_prompt_text("dog alpha")
    host = _SearchHost(snapshot=snapshot)
    controller = EditorPanelSearchController(cast(EditorPanelSearchHost, host))

    result = controller.build_search_corpus_snapshot()

    assert result is snapshot
    assert host.node_behavior_service.calls == [
        {
            "cube_states": host._cube_states,
            "stack_order": ["A"],
            "workflow_overrides": {"override": True},
            "search_hidden_keys": set(),
            "node_search_text": None,
            "search_matching_nodes": None,
        }
    ]
