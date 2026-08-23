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

"""Test search controller routing through the EditorPanel façade."""

from __future__ import annotations

import importlib
from types import ModuleType, SimpleNamespace


def _panel_module() -> ModuleType:
    """Return the production editor-panel module."""

    return importlib.import_module("substitute.presentation.editor.panel.view")


def test_clear_search_filters_resets_state_and_recomputes_visibility() -> None:
    """Clearing search should reset filters and request an unfiltered recompute."""

    panel_module = _panel_module()
    calls: dict[str, list[object]] = {"field": [], "recompute": []}
    panel = SimpleNamespace(
        _current_node_search_text="ksampler",
        _current_search_hidden_keys={"seed"},
        _current_search_matching_nodes={("A", "NodeA")},
        _current_search_result=object(),
        _current_search={"matches": ("match",), "index": 0, "needle": "dog"},
        _text_search_refresh_pending=True,
        input_widgets_by_field_key={},
        set_search_field_match_keys=lambda match_keys, *, active: calls["field"].append(
            (match_keys, active)
        ),
        refresh_node_behavior_state=lambda **kwargs: calls["recompute"].append(kwargs),
    )

    panel_module.EditorPanel.clear_search_filters(panel)

    assert panel._current_node_search_text is None
    assert panel._current_search_hidden_keys == set()
    assert panel._current_search_matching_nodes is None
    assert panel._current_search_result is None
    assert panel._current_search == {"matches": (), "index": -1, "needle": ""}
    assert panel._text_search_refresh_pending is False
    assert calls["field"] == [(None, False)]
    assert calls["recompute"] == [
        {
            "search_hidden_keys": set(),
            "node_search_text": None,
            "reason": "search_changed",
        }
    ]
