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

"""Characterization tests for editor control registry behavior."""

from __future__ import annotations

import importlib


def test_get_registry_is_singleton_and_custom_register_roundtrip() -> None:
    """Default registry should be process-singleton and preserve registrations."""
    module = importlib.import_module("substitute.infrastructure.controls.registry")
    module = importlib.reload(module)
    module._DEFAULT_REGISTRY = None

    reg_a = module.get_registry()
    reg_b = module.get_registry()

    assert reg_a is reg_b

    marker = object()
    reg_a.register("custom_control", lambda *_a, **_k: marker)
    assert reg_b.get("custom_control")() is marker


def test_builtin_builder_registration_uses_injected_factories() -> None:
    """Builtins should wire through injected presentation factory functions with defaults."""
    module = importlib.import_module("substitute.infrastructure.controls.registry")
    module = importlib.reload(module)
    module._DEFAULT_REGISTRY = None

    calls = {"float": [], "int": [], "color": []}

    def _float_factory(parent, value, min_val, max_val, step_val):
        calls["float"].append((parent, value, min_val, max_val, step_val))
        return "float-widget"

    def _int_factory(parent, value, min_val, max_val, step_val):
        calls["int"].append((parent, value, min_val, max_val, step_val))
        return "int-widget"

    def _color_factory(
        parent, value, min_val, max_val, step_val, start_color, end_color, integer=False
    ):
        calls["color"].append(
            (
                parent,
                value,
                min_val,
                max_val,
                step_val,
                start_color,
                end_color,
                integer,
            )
        )
        return "color-widget"

    module.register_builtin_control_builders(
        float_builder=_float_factory,
        int_builder=_int_factory,
        color_builder=_color_factory,
    )

    reg = module.get_registry()

    assert (
        reg.get("spinner_slider")("p", 0.2, {"min": 0, "max": 2, "step": 0.5})
        == "float-widget"
    )
    assert (
        reg.get("int_spinner_slider")("p", 3, {"min": 1, "max": 9, "step": 2})
        == "int-widget"
    )
    assert (
        reg.get("color_slider")(
            "p",
            7,
            {"min": 0, "max": 10, "step": 1},
            {"colors": {"start": "#111111", "end": "#eeeeee"}, "integer": True},
        )
        == "color-widget"
    )

    assert calls["float"][0][2:] == (0, 2, 0.5)
    assert calls["int"][0][2:] == (1, 9, 2)
    assert calls["color"][0][-1] is True


def test_color_slider_defaults_to_float_mode_when_constraints_are_fractional() -> None:
    """Color sliders should not infer integer mode from an integer-valued default."""

    module = importlib.import_module("substitute.infrastructure.controls.registry")
    module = importlib.reload(module)
    module._DEFAULT_REGISTRY = None

    calls: list[tuple[object, ...]] = []

    def _float_factory(_parent, _value, _min_val, _max_val, _step_val):
        return "float-widget"

    def _int_factory(_parent, _value, _min_val, _max_val, _step_val):
        return "int-widget"

    def _color_factory(
        parent, value, min_val, max_val, step_val, start_color, end_color, integer=False
    ):
        calls.append(
            (parent, value, min_val, max_val, step_val, start_color, end_color, integer)
        )
        return "color-widget"

    module.register_builtin_control_builders(
        float_builder=_float_factory,
        int_builder=_int_factory,
        color_builder=_color_factory,
    )

    widget = module.get_registry().get("color_slider")(
        "p",
        0,
        {"min": -10.0, "max": 10.0, "step": 0.05},
        {"colors": {"start": "#111111", "end": "#eeeeee"}},
    )

    assert widget == "color-widget"
    assert calls == [
        ("p", 0, -10.0, 10.0, 0.05, "#111111", "#eeeeee", False),
    ]
