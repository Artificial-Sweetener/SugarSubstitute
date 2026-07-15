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

"""Register named editor control builders used by presentation rendering."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("infrastructure.controls.registry")


def _coerce_float(value: object, default: float) -> float:
    """Coerce numeric-like values to float with safe fallback."""

    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _coerce_int(value: object, default: int) -> int:
    """Coerce numeric-like values to int with safe fallback."""

    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


class ControlRegistry:
    """Store named UI control builders for editor presentation overrides."""

    def __init__(self) -> None:
        """Initialize empty control registry."""

        self._builders: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, builder: Callable[..., Any]) -> None:
        """Register or overwrite a builder by control name."""

        self._builders[name] = builder

    def get(self, name: str) -> Callable[..., Any] | None:
        """Return builder for control name or None when unregistered."""

        return self._builders.get(name)


_DEFAULT_REGISTRY: ControlRegistry | None = None


def register_builtin_control_builders(
    float_builder: Callable[[object, object, float, float, float], object],
    int_builder: Callable[[object, object, int, int, int], object],
    color_builder: Callable[..., object],
) -> None:
    """Register builtin editor controls from injected presentation builders."""

    registry = get_registry()

    def spinner_slider_control(
        parent: object,
        value: object,
        constraints: dict[str, object],
        extra: dict[str, object] | None = None,
    ) -> object:
        """Build floating-point slider control with defaults."""

        _ = extra
        min_val = _coerce_float(constraints.get("min"), 0.0)
        max_val = _coerce_float(constraints.get("max"), 1.0)
        step_val = _coerce_float(constraints.get("step"), 0.01)
        return float_builder(parent, value, min_val, max_val, step_val)

    def int_spinner_slider_control(
        parent: object,
        value: object,
        constraints: dict[str, object],
        extra: dict[str, object] | None = None,
    ) -> object:
        """Build integer slider control with defaults."""

        _ = extra
        min_val = _coerce_int(constraints.get("min"), 0)
        max_val = _coerce_int(constraints.get("max"), 100)
        step_val = _coerce_int(constraints.get("step"), 1)
        return int_builder(parent, value, min_val, max_val, step_val)

    def color_slider_control(
        parent: object,
        value: object,
        constraints: dict[str, object],
        extra: dict[str, object] | None = None,
    ) -> object:
        """Build color-gradient slider control using explicit integer mode only."""

        min_val = _coerce_float(constraints.get("min"), 0.0)
        max_val = _coerce_float(constraints.get("max"), 1.0)
        step_val = _coerce_float(constraints.get("step"), 0.01)
        colors: dict[str, object] = {}
        if isinstance(extra, dict):
            raw_colors = extra.get("colors")
            if isinstance(raw_colors, dict):
                colors = raw_colors
        start_color = (
            colors["start"] if isinstance(colors.get("start"), str) else "#007bff"
        )
        end_color = colors["end"] if isinstance(colors.get("end"), str) else "#ffd000"
        integer = bool((extra or {}).get("integer", False))
        return color_builder(
            parent,
            value,
            min_val,
            max_val,
            step_val,
            start_color,
            end_color,
            integer=integer,
        )

    registry.register("spinner_slider", spinner_slider_control)
    registry.register("int_spinner_slider", int_spinner_slider_control)
    registry.register("color_slider", color_slider_control)
    log_debug(_LOGGER, "Registered builtin editor controls")


def get_registry() -> ControlRegistry:
    """Return process-wide control registry singleton."""

    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = ControlRegistry()
    return _DEFAULT_REGISTRY


__all__ = [
    "ControlRegistry",
    "get_registry",
    "register_builtin_control_builders",
]
