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

"""Tests for the editor-panel cube registry controller."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType, SimpleNamespace

import pytest

from substitute.presentation.editor.panel.cube_registry import EditorCubeRegistry


class _Widget:
    """Minimal Qt-style widget double with dynamic properties."""

    def __init__(self, props: dict[str, object] | None = None) -> None:
        """Store mutable dynamic property values."""

        self._props = dict(props or {})
        self._current_cube_alias: str | None = None

    def property(self, name: str) -> object:
        """Return one dynamic property by name."""

        return self._props.get(name)

    def setProperty(self, name: str, value: object) -> None:
        """Set one dynamic property value."""

        self._props[name] = value


class _Label:
    """Minimal label double that records visible text."""

    def __init__(self) -> None:
        """Initialize the recorded text."""

        self.text = ""

    def setText(self, text: str) -> None:
        """Record the visible label text."""

        self.text = text


def _host(**overrides: object) -> SimpleNamespace:
    """Build a complete registry host double."""

    defaults: dict[str, object] = {
        "cube_headers": {},
        "cube_positions": {},
        "cube_widgets": {},
        "cube_sections": {},
        "row_widgets": {},
        "col_widgets": {},
        "input_widgets_by_field_key": {},
        "card_wrappers": {},
        "sampler_link_widgets": {},
        "scheduler_link_widgets": {},
        "_cube_visibility_btns": {},
        "_cube_visibility_menus": {},
        "_cube_states": None,
        "_stack_order": None,
        "_node_card_mode_controller": SimpleNamespace(rename_alias=lambda *_args: None),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_registry_orders_buffers_and_snapshots_by_stack_order() -> None:
    """Registry snapshots should expose stack-ordered cube buffers."""

    cube_a = SimpleNamespace(buffer={"nodes": {"a": {}}})
    cube_b = SimpleNamespace(buffer={"nodes": {"b": {}}})
    panel = _host(
        _cube_states={"A": cube_a, "B": cube_b},
        _stack_order=["B", "Missing", "A"],
        cube_widgets={"A": object(), "B": object()},
        cube_sections={"A": object(), "B": object()},
        card_wrappers={("A", "Node"): object()},
    )

    registry = EditorCubeRegistry(panel)

    assert list(registry.ordered_buffers()) == ["B", "A"]
    assert registry.current_cube_entries_for_projection() == [
        ("B", cube_b),
        ("A", cube_a),
    ]
    snapshot = registry.snapshot()
    assert snapshot.stack_order == ("B", "Missing", "A")
    assert list(snapshot.buffers) == ["B", "A"]
    assert snapshot.cube_states is panel._cube_states
    assert snapshot.card_wrappers is panel.card_wrappers


def test_registry_projection_buffers_keep_mapping_buffers_only() -> None:
    """Projection buffers should skip cube states without mapping buffers."""

    mapped_buffer: Mapping[str, object] = MappingProxyType({"nodes": {}})
    panel = _host(
        _cube_states={
            "Mapped": SimpleNamespace(buffer=mapped_buffer),
            "Text": SimpleNamespace(buffer="not-a-buffer"),
        },
        _stack_order=["Mapped", "Text"],
    )

    assert EditorCubeRegistry(panel).ordered_projection_buffers() == {
        "Mapped": mapped_buffer
    }


def test_registry_card_wrapper_cleanup_ignores_stale_owner() -> None:
    """Wrapper removal should not remove a newer registered wrapper."""

    panel = _host(card_wrappers={})
    registry = EditorCubeRegistry(panel)
    stale_wrapper = object()
    current_wrapper = object()

    registry.register_card_wrapper("Cube", "Node", stale_wrapper)
    registry.register_card_wrapper("Cube", "Node", current_wrapper)
    registry.remove_card_wrapper_if_current("Cube", "Node", stale_wrapper)

    assert panel.card_wrappers[("Cube", "Node")] is current_wrapper

    registry.remove_card_wrapper_if_current("Cube", "Node", current_wrapper)

    assert ("Cube", "Node") not in panel.card_wrappers


def test_registry_rename_cube_alias_migrates_widget_maps_and_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alias rename should rewrite every cube-owned registry key."""

    import substitute.presentation.editor.panel.cube_registry as registry_module

    monkeypatch.setattr(
        registry_module,
        "cube_section_title",
        lambda alias, cube_state: (
            f"Pretty {alias}"
            + (" bypassed" if getattr(cube_state, "bypassed", False) else "")
        ),
    )

    mode_renames: list[tuple[str, str]] = []
    label = _Label()
    row_widget = _Widget({"input_metadata": {"cube_alias": "old"}})
    col_widget = _Widget({"input_metadata": {"cube_alias": "old"}})
    input_widget = _Widget({"input_metadata": {"cube_alias": "old"}})
    card_wrapper = _Widget()
    card_wrapper._current_cube_alias = "old"
    cube_section = object()
    sampler_widget = object()
    scheduler_widget = object()
    cube_state = SimpleNamespace(buffer={"nodes": {}})
    other_state = SimpleNamespace(buffer={"nodes": {}})
    panel = _host(
        cube_headers={"old": label},
        cube_positions={"old": 12},
        cube_widgets={"old": object()},
        cube_sections={"old": cube_section},
        row_widgets={("old", "Node", "field"): (None, row_widget)},
        col_widgets={("old", "Node", "field"): (None, col_widget)},
        input_widgets_by_field_key={("old", "Node", "field"): input_widget},
        card_wrappers={("old", "Node"): card_wrapper},
        sampler_link_widgets={("old", "KSampler"): sampler_widget},
        scheduler_link_widgets={("old", "KSampler"): scheduler_widget},
        _cube_visibility_btns={"old": object()},
        _cube_visibility_menus={"old": object()},
        _cube_states={"old": cube_state, "other": other_state},
        _stack_order=["old", "other"],
        _node_card_mode_controller=SimpleNamespace(
            rename_alias=lambda old, new: mode_renames.append((old, new))
        ),
    )

    EditorCubeRegistry(panel).rename_cube_alias("old", "new")

    assert label.text == "Pretty new"
    assert "old" not in panel.cube_headers
    assert panel.cube_sections["new"] is cube_section
    assert ("new", "Node", "field") in panel.row_widgets
    assert ("new", "Node", "field") in panel.col_widgets
    assert ("new", "Node", "field") in panel.input_widgets_by_field_key
    assert row_widget.property("input_metadata") == {"cube_alias": "new"}
    assert col_widget.property("input_metadata") == {"cube_alias": "new"}
    assert input_widget.property("input_metadata") == {"cube_alias": "new"}
    assert panel.card_wrappers[("new", "Node")] is card_wrapper
    assert card_wrapper.property("cube_alias") == "new"
    assert card_wrapper._current_cube_alias == "new"
    assert panel.sampler_link_widgets[("new", "KSampler")] is sampler_widget
    assert panel.scheduler_link_widgets[("new", "KSampler")] is scheduler_widget
    assert "new" in panel._cube_visibility_btns
    assert "new" in panel._cube_visibility_menus
    assert panel._cube_states == {"other": other_state, "new": cube_state}
    assert panel._stack_order == ["new", "other"]
    assert mode_renames == [("old", "new")]


def test_registry_refresh_cube_header_uses_current_bypass_state() -> None:
    """Header refresh should derive the bypass suffix from current cube state."""

    label = _Label()
    cube_state = SimpleNamespace(buffer={"nodes": {}}, bypassed=False)
    panel = _host(
        cube_headers={"Anima/Text to Image": label},
        _cube_states={"Anima/Text to Image": cube_state},
    )
    registry = EditorCubeRegistry(panel)

    registry.refresh_cube_header("Anima/Text to Image")
    cube_state.bypassed = True
    registry.refresh_cube_header("Anima/Text to Image")

    assert label.text == "Anima/Text to Image (bypassed)"
