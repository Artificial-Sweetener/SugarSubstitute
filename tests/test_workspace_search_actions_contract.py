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

"""Contract tests for extracted workspace search actions."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

from substitute.application.editor_search import EditorSearchMode


def _import_module():
    """Import the workspace search actions module."""

    return importlib.import_module(
        "substitute.presentation.shell.workspace_search_actions"
    )


def test_on_context_search_changed_delegates_to_application_search_service() -> None:
    """Search actions should parse and apply one application-owned search result."""

    mod = _import_module()
    service_calls: list[tuple[str, object]] = []
    applied_results: list[object] = []
    search_result = SimpleNamespace(
        query=SimpleNamespace(mode=EditorSearchMode.NODE),
        navigation_matches=("match",),
    )

    class _Service:
        def build_query(self, *, mode, raw_text):
            service_calls.append(("query", (mode, raw_text)))
            return SimpleNamespace(mode=mode, raw_text=raw_text)

        def build_result(self, snapshot, query):
            service_calls.append(("result", (snapshot, query)))
            return search_result

    panel = SimpleNamespace(
        build_search_corpus_snapshot=lambda: "snapshot",
        apply_search_result=lambda result: (
            applied_results.append(result),
            setattr(panel, "_current_search", {"matches": ("match",)}),
        ),
    )
    view = SimpleNamespace(
        active_editor_panel=panel,
        active_override_manager=None,
        contextSearchBox=SimpleNamespace(
            set_navigation_enabled=lambda enabled: service_calls.append(
                ("nav", enabled)
            )
        ),
    )
    actions = mod.WorkspaceSearchActions(view)
    actions._search_service = _Service()

    actions.on_context_search_changed("Node", 'ksampler "fox"')

    assert service_calls == [
        ("query", (EditorSearchMode.NODE, 'ksampler "fox"')),
        (
            "result",
            (
                "snapshot",
                SimpleNamespace(mode=EditorSearchMode.NODE, raw_text='ksampler "fox"'),
            ),
        ),
        ("nav", True),
    ]
    assert applied_results == [search_result]


def test_on_search_closed_clears_active_editor_filters() -> None:
    """Closing the search box should clear editor search filters."""

    mod = _import_module()
    calls: list[str] = []
    view = SimpleNamespace(
        active_editor_panel=SimpleNamespace(
            clear_search_filters=lambda: calls.append("cleared")
        ),
        active_override_manager=None,
        contextSearchBox=SimpleNamespace(),
    )

    mod.WorkspaceSearchActions(view).on_search_closed()

    assert calls == ["cleared"]
