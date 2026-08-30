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

"""Test workspace search action coordination."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.application.editor_search import EditorSearchMode


from tests.presentation.shell.search_actions.support import (
    _import_module,
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
        def build_query(
            self,
            *,
            mode: EditorSearchMode,
            raw_text: str,
        ) -> object:
            """Record and return the parsed search query."""

            service_calls.append(("query", (mode, raw_text)))
            return SimpleNamespace(mode=mode, raw_text=raw_text)

        def build_result(self, snapshot: object, query: object) -> object:
            """Record and return the application search result."""

            service_calls.append(("result", (snapshot, query)))
            return search_result

    class _Panel:
        _current_search: dict[str, tuple[str, ...]]

        def build_search_corpus_snapshot(self) -> str:
            """Return the deterministic test search corpus."""

            return "snapshot"

        def apply_search_result(self, result: object) -> None:
            """Record the result and expose its navigation matches."""

            applied_results.append(result)
            self._current_search = {"matches": ("match",)}

    panel = _Panel()
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
