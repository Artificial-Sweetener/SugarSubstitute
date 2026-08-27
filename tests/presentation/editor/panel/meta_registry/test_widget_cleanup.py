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

"""Verify MetaRegistry cleanup and absent-context refresh behavior."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from pytest import MonkeyPatch

from substitute.presentation.editor.panel.meta_registry import MetaRegistry

from .support import ComboDouble, ParentWidgetDouble


def test_cleanup_dead_widgets_removes_invalid_or_parentless_combos(
    monkeypatch: MonkeyPatch,
) -> None:
    """Cleanup should keep only combos that are valid and still parented."""

    registry = MetaRegistry(SimpleNamespace())
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.meta_registry.isValid",
        lambda combo: bool(combo.valid),
    )
    alive = ComboDouble(parent_obj=object(), parent_widget_obj=None, valid=True)
    dead_invalid = ComboDouble(parent_obj=object(), parent_widget_obj=None, valid=False)
    dead_orphan = ComboDouble(parent_obj=None, parent_widget_obj=None, valid=True)
    widget_map = {("a", 1): alive, ("b", 2): dead_invalid, ("c", 3): dead_orphan}

    registry._cleanup_dead_widgets(widget_map)

    assert widget_map == {("a", 1): alive}


def test_update_link_widgets_skips_when_panel_has_no_stack_context(
    monkeypatch: MonkeyPatch,
) -> None:
    """Updater should no-op when cube state or stack order is unavailable."""

    panel = SimpleNamespace(
        _cube_states={},
        _stack_order=[],
        node_definition_gateway=object(),
    )
    registry = MetaRegistry(panel)
    calls: list[bool] = []
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.meta_registry.isValid",
        lambda combo: bool(combo.valid),
    )
    widget_map = {
        ("A", "node"): ComboDouble(
            parent_obj=object(),
            parent_widget_obj=ParentWidgetDouble("layout"),
            valid=True,
        )
    }

    def _record_setup(*_args: object, **_kwargs: object) -> None:
        """Record an unexpected setup invocation."""

        calls.append(True)

    registry._update_link_widgets(widget_map, _record_setup, add_label=False)

    assert calls == []


def test_update_link_widgets_for_cube_filters_by_cube_alias(
    monkeypatch: MonkeyPatch,
) -> None:
    """Cube-scoped updater should refresh only matching widget-map entries."""

    panel = SimpleNamespace(
        _cube_states={
            "A": SimpleNamespace(buffer={"nodes": {"n1": {"inputs": {}}}}),
            "B": SimpleNamespace(buffer={"nodes": {"n2": {"inputs": {}}}}),
        },
        _stack_order=["A", "B"],
        node_definition_gateway=object(),
    )
    registry = MetaRegistry(panel)
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.meta_registry.isValid",
        lambda combo: bool(combo.valid),
    )
    widget_map = {
        ("A", "n1"): ComboDouble(
            parent_obj=object(),
            parent_widget_obj=ParentWidgetDouble("layout-a"),
            valid=True,
        ),
        ("B", "n2"): ComboDouble(
            parent_obj=object(),
            parent_widget_obj=ParentWidgetDouble("layout-b"),
            valid=True,
        ),
    }
    captured: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def _setup_func(*args: object, **kwargs: object) -> None:
        """Record one setup call for its inspected semantic arguments."""

        captured.append((args, kwargs))

    registry._update_link_widgets_for_cube(widget_map, _setup_func, "A")

    assert len(captured) == 1
    call, kwargs = captured[0]
    assert call[2:4] == ("A", "n1")
    all_buffers = cast(dict[str, object], call[4])
    assert all_buffers["B"] == panel._cube_states["B"].buffer
    assert call[5] == "layout-a"
    assert kwargs["node_definition_gateway"] is panel.node_definition_gateway
