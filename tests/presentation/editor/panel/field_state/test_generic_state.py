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

"""Test generic field-state restoration and dirty marking."""

from __future__ import annotations

from pytest import MonkeyPatch

from types import SimpleNamespace


from tests.presentation.editor.panel.field_state.support import (
    _Signal,
    _prepare_field_state_module,
    field_state_controller,
)


def test_set_buffer_value_and_dirty_respects_node_state_keys(
    monkeypatch: MonkeyPatch,
) -> None:
    """Node-state keys write to node root, not to inputs."""
    _prepare_field_state_module(monkeypatch)
    module = field_state_controller
    cube_state = SimpleNamespace(
        buffer={"nodes": {"node": {"enabled": True, "inputs": {"steps": 20}}}},
        dirty=False,
    )

    module.set_buffer_value_and_dirty(cube_state, "node", "enabled", False)

    assert cube_state.buffer["nodes"]["node"]["enabled"] is False
    assert cube_state.buffer["nodes"]["node"]["inputs"]["steps"] == 20
    assert cube_state.dirty is True


def test_wire_widget_state_restores_buffer_value_and_writes_on_change(
    monkeypatch: MonkeyPatch,
) -> None:
    """Generic wiring restores from buffer and marks dirty on changed value."""
    _prepare_field_state_module(monkeypatch)
    module = field_state_controller

    signal = _Signal()
    widget = SimpleNamespace(
        value=0,
        _props={"input_metadata": {"node_name": "node", "key": "steps"}},
    )
    widget.property = lambda name: widget._props.get(name)
    cube_state = SimpleNamespace(
        buffer={"nodes": {"node": {"inputs": {"steps": 10}}}},
        dirty=False,
    )

    module.wire_widget_state(
        widget,
        cube_state,
        get_val_func=lambda w: w.value,
        set_val_func=lambda w, v: setattr(w, "value", v),
        signal=signal,
    )

    assert widget.value == 10
    signal.emit(12)
    assert cube_state.buffer["nodes"]["node"]["inputs"]["steps"] == 12
    assert cube_state.dirty is True


def test_wire_widget_state_keeps_dirty_false_for_unchanged_value(
    monkeypatch: MonkeyPatch,
) -> None:
    """Generic widget writes should not dirty the cube when the value is unchanged."""

    _prepare_field_state_module(monkeypatch)
    module = field_state_controller
    signal = _Signal()
    widget = SimpleNamespace(
        value=10,
        _props={"input_metadata": {"node_name": "node", "key": "steps"}},
    )
    widget.property = lambda name: widget._props.get(name)
    cube_state = SimpleNamespace(
        buffer={"nodes": {"node": {"inputs": {"steps": 10}}}},
        dirty=False,
    )

    module.wire_widget_state(
        widget,
        cube_state,
        get_val_func=lambda w: w.value,
        set_val_func=lambda w, v: setattr(w, "value", v),
        signal=signal,
    )
    signal.emit(10)

    assert cube_state.buffer["nodes"]["node"]["inputs"]["steps"] == 10
    assert cube_state.dirty is False


def test_wire_widget_state_prefers_resolved_display_fallback_for_initial_restore(
    monkeypatch: MonkeyPatch,
) -> None:
    """Live fallback displays should not be overwritten by raw blank buffer values."""

    _prepare_field_state_module(monkeypatch)
    module = field_state_controller

    signal = _Signal()
    widget = SimpleNamespace(
        value=0,
        _props={
            "input_metadata": {
                "node_name": "node",
                "key": "steps",
                "resolved_value": 0,
                "value_source": "live_default",
            }
        },
    )
    widget.property = lambda name: widget._props.get(name)
    cube_state = SimpleNamespace(
        buffer={"nodes": {"node": {"inputs": {"steps": ""}}}},
        dirty=False,
    )

    module.wire_widget_state(
        widget,
        cube_state,
        get_val_func=lambda w: w.value,
        set_val_func=lambda w, v: setattr(w, "value", v),
        signal=signal,
    )

    assert widget.value == 0
    assert cube_state.buffer["nodes"]["node"]["inputs"]["steps"] == ""
    assert cube_state.dirty is False
