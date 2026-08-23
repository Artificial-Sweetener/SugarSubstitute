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

"""Test alias-scoped projection lifecycle removal."""

from __future__ import annotations

import importlib
from types import ModuleType, SimpleNamespace


class _Widget:
    """Identify one cube widget in removal assertions."""


def _coordinator_module() -> ModuleType:
    """Return the production projection coordinator module."""

    return importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )


def test_remove_cube_clears_alias_state_and_invalidates_projection() -> None:
    """Removing a cube should clear alias-scoped panel state without touching others."""

    coordinator_module = _coordinator_module()
    removed_widgets: list[object] = []
    runtime_issue_clears: list[str] = []
    visibility_refreshes: list[dict[str, object]] = []
    projection_invalidations: list[str] = []
    meta_registry_calls: list[str] = []
    removed_widget = _Widget()
    kept_widget = _Widget()
    panel = SimpleNamespace(
        cube_widgets={"CubeA": removed_widget, "CubeB": kept_widget},
        cube_sections={"CubeA": removed_widget, "CubeB": kept_widget},
        cube_headers={"CubeA": object(), "CubeB": object()},
        card_wrappers={("CubeA", "node"): object(), ("CubeB", "node"): object()},
        input_widgets_by_field_key={
            ("CubeA", "node", "field"): object(),
            ("CubeB", "node", "field"): object(),
        },
        row_widgets={
            ("CubeA", "node", "field"): object(),
            ("CubeB", "node", "field"): object(),
        },
        col_widgets={
            ("CubeA", "node", "field"): object(),
            ("CubeB", "node", "field"): object(),
        },
        _last_card_decisions={"CubeA": object(), "CubeB": object()},
        _last_hidden_field_keys={
            ("CubeA", "node", "field"),
            ("CubeB", "node", "field"),
        },
        meta_registry=SimpleNamespace(
            remove_node_link_cube=lambda alias: meta_registry_calls.append(alias)
        ),
        clear_cube_runtime_issues=runtime_issue_clears.append,
        _remove_cube_widget_from_layout=removed_widgets.append,
        refresh_node_behavior_state=lambda **kwargs: visibility_refreshes.append(
            dict(kwargs)
        ),
    )
    coordinator = coordinator_module.EditorPanelProjectionCoordinator(panel)
    coordinator.invalidate_projection = lambda *, reason: (
        projection_invalidations.append(reason)
    )

    coordinator.remove_cube("CubeA")

    assert runtime_issue_clears == ["CubeA"]
    assert removed_widgets == [removed_widget]
    assert panel.cube_widgets == {"CubeB": kept_widget}
    assert panel.cube_sections == {"CubeB": kept_widget}
    assert set(panel.card_wrappers) == {("CubeB", "node")}
    assert set(panel.input_widgets_by_field_key) == {("CubeB", "node", "field")}
    assert panel._last_hidden_field_keys == {("CubeB", "node", "field")}
    assert meta_registry_calls == ["CubeA"]
    assert visibility_refreshes == [
        {"reason": "cube_removed", "use_cached_snapshot": False}
    ]
    assert projection_invalidations == ["cube_removed"]
