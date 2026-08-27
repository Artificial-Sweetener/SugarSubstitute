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

"""Characterize infrastructure control-registry behavior."""

from __future__ import annotations

import pytest
from pytest import MonkeyPatch

from substitute.infrastructure.controls import registry as control_registry
from substitute.infrastructure.controls.registry import ControlRegistry


@pytest.fixture
def empty_registry(monkeypatch: MonkeyPatch) -> ControlRegistry:
    """Provide a fresh registry while restoring the process registry afterward."""

    monkeypatch.setattr(control_registry, "_DEFAULT_REGISTRY", None)
    return control_registry.get_registry()


def test_get_registry_is_singleton_and_custom_register_roundtrip(
    empty_registry: ControlRegistry,
) -> None:
    """Preserve registrations through the process-local registry singleton."""

    registry_again = control_registry.get_registry()

    assert empty_registry is registry_again

    marker = object()

    def custom_builder(*_args: object, **_kwargs: object) -> object:
        """Return the test marker for every custom-control invocation."""

        return marker

    empty_registry.register("custom_control", custom_builder)
    custom_control = registry_again.get("custom_control")

    assert custom_control is not None
    assert custom_control() is marker


def test_builtin_builder_registration_uses_injected_factories(
    empty_registry: ControlRegistry,
) -> None:
    """Wire default controls through the supplied presentation factories."""

    calls: dict[str, list[tuple[object, ...]]] = {
        "float": [],
        "int": [],
        "color": [],
    }

    def float_factory(
        parent: object,
        value: object,
        min_value: float,
        max_value: float,
        step_value: float,
    ) -> object:
        """Record floating slider construction arguments."""

        calls["float"].append((parent, value, min_value, max_value, step_value))
        return "float-widget"

    def int_factory(
        parent: object,
        value: object,
        min_value: int,
        max_value: int,
        step_value: int,
    ) -> object:
        """Record integer slider construction arguments."""

        calls["int"].append((parent, value, min_value, max_value, step_value))
        return "int-widget"

    def color_factory(
        parent: object,
        value: object,
        min_value: float,
        max_value: float,
        step_value: float,
        start_color: str,
        end_color: str,
        integer: bool = False,
    ) -> object:
        """Record color-slider construction arguments."""

        calls["color"].append(
            (
                parent,
                value,
                min_value,
                max_value,
                step_value,
                start_color,
                end_color,
                integer,
            )
        )
        return "color-widget"

    control_registry.register_builtin_control_builders(
        float_builder=float_factory,
        int_builder=int_factory,
        color_builder=color_factory,
    )

    float_control = empty_registry.get("spinner_slider")
    integer_control = empty_registry.get("int_spinner_slider")
    color_control = empty_registry.get("color_slider")

    assert float_control is not None
    assert integer_control is not None
    assert color_control is not None
    assert float_control("p", 0.2, {"min": 0, "max": 2, "step": 0.5}) == "float-widget"
    assert integer_control("p", 3, {"min": 1, "max": 9, "step": 2}) == "int-widget"
    assert (
        color_control(
            "p",
            7,
            {"min": 0, "max": 10, "step": 1},
            {"colors": {"start": "#111111", "end": "#eeeeee"}, "integer": True},
        )
        == "color-widget"
    )

    assert calls["float"][0][2:] == (0.0, 2.0, 0.5)
    assert calls["int"][0][2:] == (1, 9, 2)
    assert calls["color"][0][-1] is True


def test_color_slider_defaults_to_float_mode_for_fractional_constraints(
    empty_registry: ControlRegistry,
) -> None:
    """Keep a color slider fractional when its constraints are fractional."""

    calls: list[tuple[object, ...]] = []

    def float_factory(
        _parent: object,
        _value: object,
        _min_value: float,
        _max_value: float,
        _step_value: float,
    ) -> object:
        """Provide an unused floating-slider builder."""

        return "float-widget"

    def int_factory(
        _parent: object,
        _value: object,
        _min_value: int,
        _max_value: int,
        _step_value: int,
    ) -> object:
        """Provide an unused integer-slider builder."""

        return "int-widget"

    def color_factory(
        parent: object,
        value: object,
        min_value: float,
        max_value: float,
        step_value: float,
        start_color: str,
        end_color: str,
        integer: bool = False,
    ) -> object:
        """Record the color-slider mode selected by the registry."""

        calls.append(
            (
                parent,
                value,
                min_value,
                max_value,
                step_value,
                start_color,
                end_color,
                integer,
            )
        )
        return "color-widget"

    control_registry.register_builtin_control_builders(
        float_builder=float_factory,
        int_builder=int_factory,
        color_builder=color_factory,
    )
    color_control = empty_registry.get("color_slider")

    assert color_control is not None
    assert (
        color_control(
            "p",
            0,
            {"min": -10.0, "max": 10.0, "step": 0.05},
            {"colors": {"start": "#111111", "end": "#eeeeee"}},
        )
        == "color-widget"
    )
    assert calls == [
        ("p", 0, -10.0, 10.0, 0.05, "#111111", "#eeeeee", False),
    ]
